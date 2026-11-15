<!-- src-sha1: a12736ca9c475f1c7c0195dbae0d18d5725a4440 -->
# WhatsApp Upload de Mídia — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** transferência de mídia no Android: IQ `media_conn` (hosts, auth, ttl, buckets, hosts de fallback), construção de URL de upload e download e parâmetros HTTP, tabela de tipo de mídia com strings de info HKDF, geração e derivação de chave de mídia, criptografia AES-CBC + HMAC, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, miniaturas, sidecars de streaming para vídeo / áudio / imagens progressivas, upload retomável, seleção de rota, retry e backoff, códigos de erro de upload e download, recibo de media retry e notificação `mediaretry`, mídia view-once e de status, mídia de newsletter (canal), caminho express, hardening nativo do lado do cliente dos parsers de mídia, comparação com Baileys

---

## 1. O que é (tecnicamente)

Mídia nunca trafega dentro do stream chatd (ver [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Uma mensagem carrega apenas uma referência protobuf (chave, hashes, `directPath`); os bytes vão por conexões HTTPS separadas para hosts de mídia. O chatd fornece uma coisa: o IQ `media_conn` que entrega nomes de host e um token de auth de upload de curta duração. Todas as afirmações vêm de análise estática do APK decompilado e das bibliotecas nativas desempacotadas; nada foi capturado no wire. Tiers: **found** = lido em código ou strings, **inferred** = deduzido, **unknown** = não resolvido.

| Camada | Nome na 2.26.41.6 | Papel |
|-------|----------------|------|
| Seletor de rota | `RouteSelector` (`C10950Wx`) | mantém o resultado atual de `media_conn`, timer de atualização, throttle, fábrica de rotas |
| Parser de `media_conn` | `C43951qe` (handler de resultado IQ), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | faz o parse de `<media_conn>` / `<host>` |
| Fornecedor de rota | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (fornecedores estáticos) | escolhe o host por tentativa, troca o token de auth |
| Driver de retry | `TransferRetries` (`C44566Jd2`) | loop de tentativas em torno de uma transferência |
| Tabela de tipo de mídia | `MmsType` (`C15530gU`) | por tipo: string de caminho, bytes de info HKDF, id numérico |
| Fornecedor de chave | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF de 80 bytes, chave de domínio não-E2EE |
| Streams de cifra | `M2I` (criptografar saída), `M23` (criptografar entrada), `P9N` / `P1X` / `P1Y` (MACs de sidecar), `C51101MlN` (descriptografia por intervalo) | AES-CBC + HMAC |
| Driver de upload | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (reuso de chave), `C57333Po0` (geração de chave + hashes) | hashes, sidecars, orquestração de upload |
| URL de upload | `C43489Iy4` | `/surface/type/hash?...` |
| URL de download | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) upload; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) download | transporte |
| Sondagem de resume | `HttpResumeCheck` (`C59524QnW`) | pergunta ao servidor quantos bytes ele já tem |
| Recibo de retry | `SendMediaErrorReceiptJob`, writer cases 77 e 327 em `HandlerThreadC21920sG` | solicita novo upload do remetente |
| Notificação de retry | `MediaRetryNotificationHandler` (`C1S0`, código de notificação 97) | consome a resposta |
| Nativo | `libwhatsapp.so` (crates de mídia em Rust, sandboxes RLBox), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | parsers e decoders |

Pontos que decidem o resto do relatório:

- O Android deriva **80** bytes da chave de mídia (IV 16, chave de cifra 32, chave MAC 32), não 112 (seção 4).
- O caminho HTTP é `/{surface}/{type}/{urlSafeFileEncSha256}` onde `type` é a string `MmsType` da mídia (`image`, `ptt`, `md-msg-hist`, ...), não uma classe genérica (seção 8.1).
- O `token` de upload do Android não é o hash do arquivo; é um SHA-256 sobre um segredo por instalação e o hash do arquivo (seção 8.2).
- A mídia de newsletter (canal) compartilha o mesmo código mas usa a surface `newsletter` e um token aleatório; é não criptografada (found para o caminho de artwork, inferred para o resto, seção 13).
- Os hosts de download são filtrados por um bucket derivado do hash do arquivo (seção 9.2).

---

## 2. IQ `media_conn`

### 2.1 Requisição (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout de 32000 ms. Apenas uma requisição está em voo (`inFlightMediaRoutingRequestTime`); uma segunda chamada loga `not sending request` e retorna. Um throttle global (`ChatdMediaThrottleManager`) pode suprimir a chamada (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Resposta (found, `C43951qe.CFS`)

| Nó / atributo | Tipo | Uso |
|------------------|------|-----|
| `media_conn@auth` | string, obrigatório | token de auth de upload (parâmetro de query `auth`) |
| `@ttl` | segundos | vida útil da conexão; expiração = hora de envio + ttl * 1000 |
| `@auth_ttl` | segundos | vida útil do token de auth; expiração = hora de envio + auth_ttl * 1000 |
| `@max_buckets` | long, padrão 0 | módulo para o bucket de download (seção 9.2) |
| `@is_new` | int, padrão 1 | 1 = substitui a lista de hosts; caso contrário mantém os hosts anteriores e pega apenas token e ttl (`previous hosts retained`) |
| `@id` | string | armazenado como `last_id`, enviado de volta na próxima requisição |
| `@max_auto_download_retry` | int, padrão 3 | orçamento de retry para downloads automáticos |
| `@max_manual_retry` | int, padrão 3 | orçamento de retry para downloads manuais |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | parseados e cacheados; `ip_token` só é usado quando a flag **12149** está ativa e `set_ip_token` é true (local de consumo: unknown) |
| `host` (repetido) | nó | uma entrada de rota |

Atributos de `host` (found): `hostname` (obrigatório), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` ou `fallback`; qualquer outra coisa se torna `primary`), `force_ip` (`"true"`). Filhos: `<upload>`, `<download>`, `<download_buckets>`; os nomes de tag filhos são as entradas de capability. `upload` e `download` mantêm apenas tags que aparecem em um conjunto fixo de 34 strings de tipo de mídia (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, a família `newsletter-*`, e a família `thumbnail-*`); `download_buckets` é mantido sem filtro.

Um host de rota só é usável se seu hostname terminar em `.whatsapp.net` (`Mms4RouteSupplier.A06`, também aplicado a `fallback_hostname`).

### 2.3 Cache e atualização (found)

| Regra | Valor |
|------|-------|
| Persistir | com a flag **149** o resultado é armazenado como JSON (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) sob `route_selector_prefs` / `media_conn`; carregado uma vez, usado apenas se o auth ainda não expirou |
| Verificação de atualização | antes de uma transferência: se a conexão ou o auth expirarem dentro de 120000 ms, enviar um novo IQ e esperar até 20000 ms (`requestroutesandwaitforauth`) |
| Timer | `expiração do auth - 60000 ms` após cada resultado; foreground (`BgG`) o rearma |
| Falha de auth | HTTP 401 ou 403 em uma transferência dispara uma atualização (`onmediatransfererrororresponsecode`), máx. 2 trocas de token por transferência (`JW1.A00 < 2`), depois a tentativa é refeita com o novo `auth` |
| Auth antes da tentativa | `refreshAuthBeforeAttempt` troca por um token mais novo quando o cacheado está a menos de 120000 ms da expiração (símbolo de flag `PTU.A0D`) |

### 2.4 Erro do IQ (found, `C43951qe.Brt`)

`<error code backoff>` dentro do resultado do IQ:

| Código | Comportamento |
|------|-----------|
| 503 | reseta o throttle de mídia; agenda a próxima atualização após um backoff de Fibonacci com jitter (`3/4 * t + rand(t/2)`) |
| 507 com backoff > 0 | limita as requisições de mídia até `now + min(backoff, 10800) s` |
| outro / 0 | ignorado |

---

## 3. Tipos de mídia e strings de info HKDF (found, inicialização estática de `MmsType` `C15530gU`)

Cada `MmsType` mantém uma string de caminho (`A02`), um rótulo curto de tipo de arquivo (`A01`, ex. `IMG`), os bytes de `info` HKDF (`A03`) e um id numérico (`A00`). Os bytes de `info` são usados brutos como info HKDF (sem prefixo adicional).

| Info HKDF | Strings de caminho `MmsType` |
|-----------|------------------------|
| `WhatsApp Image Keys` | `image`, `sticker`, `kyc-id`, `biz-cover-photo`, `biz-flows`, `wamo-image`, `newsletter-image`, `newsletter-image-status`, `newsletter-sticker`, `newsletter-music-artwork` |
| `WhatsApp Video Keys` | `video`, `ptv`, `gif`, `wamo-video`, `newsletter-video`, `newsletter-video-status`, `newsletter-ptv`, `newsletter-gif`, `newsletter-gif-status` |
| `WhatsApp Audio Keys` | `audio`, `ptt`, `newsletter-audio`, `newsletter-audio-status`, `newsletter-ptt` |
| `WhatsApp Document Keys` | `document`, `biz-flows`, `maiba-file`, `db`, `newsletter-document` |
| `WhatsApp Image Thumbnail Keys` | `thumbnail-image`, `newsletter-thumbnail-image`, `newsletter-thumbnail-status` |
| `WhatsApp Video Thumbnail Keys` | `thumbnail-video`, `thumbnail-gif`, `newsletter-thumbnail-video` |
| `WhatsApp Document Thumbnail Keys` | `thumbnail-document` |
| `WhatsApp Link Thumbnail Keys` | `thumbnail-link`, `newsletter-thumbnail-link` |
| `WhatsApp Chat Wallpaper Keys` | `chat-wallpaper-image` |
| `WhatsApp App State Keys` | `md-app-state` |
| `WhatsApp History Keys` | `md-msg-hist` |
| `Group History` | `group-history` |
| `WhatsApp Sticker Pack Keys` | `sticker-pack`, `newsletter-sticker-pack` |
| `WhatsApp Sticker Pack Thumbnail Keys` | `thumbnail-sticker-pack`, `newsletter-thumbnail-sticker-pack` |
| `WhatsApp Payment Background Keys` | `payment-bg-image` |
| `WhatsApp Music Artwork Keys` | `music-artwork` |
| `waffle_hkdf_info` | `waffle-image`, `waffle-video`, `waffle-gif` |
| `PAYMENT_DOC_UPLOAD` | `payment-br-document` |
| `ads-image` / `ads-video` | `ads-image` / `ads-video` |

Notas (found): `ptt` e `audio` compartilham a info de Audio mas são strings de caminho diferentes; `sticker` usa info de Image; `gif` e `ptv` usam info de Video; várias linhas `image` existem com ids numéricos diferentes (1, 23, 25, 37, 42, 44, 57; `sticker` é 20) para pontos de chamada diferentes (significado do id unknown); `group-history` é a única entrada cuja info não está na forma `WhatsApp <X> Keys`. Fotos de perfil (`ppic`) aparecem apenas no conjunto de capability de rota e nas chamadas do gerador de download, não como um `MmsType`.

---

## 4. Chave de mídia e derivação

### 4.1 Geração de chave (found)

| Item | Valor |
|------|-------|
| Chave de mídia | 32 bytes aleatórios de `SecureRandom` (`C57333Po0`, `QIh.A0B` é `new SecureRandom()`) |
| Reuso | `MediaKeyGen/reuse key from message contents` quando a chave é mais nova que `172800000 ms + SecureRandom.nextInt(86400000)` (2 a 3 dias, com jitter), medido contra o timestamp da chave armazenado; chaves mais antigas são descartadas (`key expired`) e regeneradas |
| Domínio | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `AbstractC38961i0.A00` chamado por `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01` rejeita qualquer outro comprimento (`Invalid length of derived secret`). Comprimento do texto cifrado: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (blocos preenchidos com PKCS#5 mais 10 bytes de MAC).

### 4.3 Chave de mídia não-E2EE (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (campo **74**, mensagem `DQT`) carrega `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) e `e2eeMediaKey` (**2**). Com a flag **24661** o receptor verifica se a chave na mensagem corresponde ao domínio (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); em caso de incompatibilidade ele recorre à chave como fornecida. Quais produtos usam o domínio NON_E2EE: unknown.

---

## 5. Criptografia, MAC e hashes

### 5.1 Cifra (found, `M2I`, `M23`, `N6U`)

| Etapa | Detalhe |
|------|--------|
| Cifra | `AES/CBC/PKCS5Padding`, chave = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, atualizado primeiro com o IV, depois com cada byte do texto cifrado; os primeiros **10** bytes do digest são anexados ao texto cifrado |
| `fileSha256` | SHA-256 sobre o texto plano (stream de digest `P9M` sobre o arquivo) |
| `fileEncSha256` | SHA-256 sobre texto cifrado + 10 bytes de MAC |
| Saída | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Lado da descriptografia (`P9N`, `M23`): o MAC é verificado sobre IV + texto cifrado, depois comparado com os 10 bytes finais. Descriptografia por intervalo (`C51101MlN`): quando o início do intervalo não é 0, os primeiros 16 bytes lidos são usados como IV (bloco de texto cifrado anterior); chunks internos usam `AES/CBC/NoPadding`, o chunk final usa PKCS#5 (inferido a partir da seleção de cifra).

### 5.2 Timestamps e caminhos

| Campo | Valor |
|-------|-------|
| `mediaKeyTimestamp` | relógio local em milissegundos mantido no objeto de chave, escrito no protobuf como segundos (`C20H.A06` = `/1000`) |
| `directPath` | string de caminho retornada pelo servidor, armazenada na mensagem e na coluna do BD `direct_path`; pode carregar parâmetros de query (ex. `_nc_hot` é lido a partir dela) |
| `url` | campo de URL completa legado; ainda presente nas classes proto e na resposta de upload, mas o gerador de download é construído a partir de `directPath` ou do hash (seção 9.1) |

### 5.3 Verificações de hash otimistas

`MediaUpload/optimistic-hash-fail` e `optimistic-plaintext-hash-fail` (resultado de upload 12) são logados quando o hash que o servidor reporta difere do computado localmente. O upload otimista (string de surface `optimistic`) faz upload antes que o envio seja confirmado; seu protocolo além do nome da surface: unknown.

---

## 6. Campos de mensagem de mídia

Números de campo lidos das classes protobuf geradas. Nomes de classe são correspondidos por formato de campo (inferred); os números são found.

| Mensagem (classe) | Números de campo (nome = número) |
|-----------------|-------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| History bundle (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

Números do container `Message` (`C30628DTw`) (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage` é o campo **21** do container `BD3`.

### 6.1 Miniaturas

| Tipo | Mecanismo (found salvo indicação) |
|------|---------------------------------|
| Inline | bytes `jpegThumbnail` (**16**) na mensagem (imagem, vídeo, documento); `pngThumbnail` (**16**) em stickers |
| Enviada | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (imagem **26-28**, vídeo **21-23**, documento **13-15**); `MmsType` `thumbnail-*` com as infos HKDF de Thumbnail da seção 3 |
| Chave | o proto não tem um campo de chave de thumbnail separado, então uma miniatura é criptografada com a chave de mídia de sua mensagem (inferred) |
| Gerada pelo servidor | query de upload `server_thumb_gen=1`; a resposta de upload pode retornar `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` |
| BD | tabela `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming e sidecars (found)

Um sidecar é uma lista de MACs de 10 bytes, um por chunk de texto cifrado, que permite que um player verifique um intervalo sem ler o arquivo inteiro.

| Item | Detalhe |
|------|--------|
| Algoritmo | `P9N.read`: por chunk um `HmacSHA256(macKey)` é inicializado com os **16 bytes de texto cifrado anteriores** (o IV para o primeiro chunk), alimentado com o chunk, e os primeiros 10 bytes do digest são armazenados |
| Concatenação | `C57228PmG.A00` junta todos os MACs de 10 bytes em um único array de bytes |
| Vídeo / áudio | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); tamanho de chunk **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Imagem progressiva | `firstScanSidecar` (**18**) com `firstScanLength` (**19**): um chunk de `ceil(len/16)*16` bytes; `scansSidecar` (**21**) com `scanLengths` (**22**): tamanhos de chunk variáveis (`P1Y`) |
| Sticker | `firstFrameSidecar` (**12**) com `firstFrameLength` (**11**) |
| Configurações | a prop de servidor `streaming_upload_chunk_size` é um token de dicionário; seu efeito: unknown |
| Ausente | status de download 30 `failed_no_sidecar` |
| Streaming do servidor | query de upload `stream=1` e `streaming=riff` juntas (seção 8.1); DASH: `dashManifestUrl` (**33**), `metadataUrl` (**30**) na resposta |

---

## 8. Upload

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Parte | Valor |
|------|-------|
| `surface` | `mms` (normal), `newsletter` (canais), `optimistic` (upload antes do envio); `AbstractC58025Pzy` |
| `type` | string de caminho `MmsType` (seção 3), ex. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | base64 padrão de `fileEncSha256` com `+` para `-` e `/` para `_`; o padding `=` é mantido (`StringUtils.A0B`) |
| `direct_ip` | 1 quando a authority é um IP (`ip4`, ou `[ip6]` entre colchetes), senão 0 |
| `auth` | o token de auth do `media_conn`; adicionado como parâmetro de query por `K19.A03` |
| `stream=1`, `streaming=riff` | ambos definidos quando a requisição é um upload em stream (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | apenas para `newsletter-image` / `-status` (flag **11191**) e `newsletter-video` / `-status` (flag **11192**) |
| `server_transcode=1` | `newsletter-video` com request id 10 e flag **9096** |
| `_nc_rmr=1` | uploads não-newsletter (flag de requisição `A0N`) |
| `_nc_cbep=1` | quando a requisição permite e a flag **17404** está ativa (significado unknown) |
| `type`, `media_id`, `media_id_upload` | `media_id` = 63 bits mais significativos de um UUID de upload; `media_id_upload` = 63 bits menos significativos, apenas quando a requisição tem entradas extra; `type` é uma string do chamador (significado: unknown) |

O significado dos nomes de query `_nc_cbep` e `_nc_rmr` é unknown (apenas nomes).

### 8.2 Token (found, `C43489Iy4.A00`)

| Caso | Token |
|------|------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes de java.util.Random))`, novo a cada requisição, não vinculado ao arquivo |
| Outro | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` é 32 bytes de `SecureRandom`, criado uma vez e armazenado em preferências como `upload_token_random_bytes` (base64 sem wrap, sem padding) |

Se `fileEncSha256` não puder ser decodificado o token é `SHA-256(installSecret)` isoladamente. Propósito da construção: inferido como uma verificação do lado do servidor de que o uploader conhece o hash sem expô-lo no caminho.

### 8.3 Requisição HTTP (found, `HttpsFormPost` `C43478Ixt`)

| Item | Valor |
|------|-------|
| Biblioteca | `HttpsURLConnection` com um `SSLSocketFactory` customizado; marcador `http_stack = HttpUrlConnection` |
| Método | POST (`setDoOutput(true)` em `HttpURLConnection`; nenhuma chamada de método explícita) |
| Timeouts | connect 15000 ms, read 60000 ms |
| Headers | `Host: <route hostname>` (a authority pode ser um IP), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, opcional `Companion_User_Secret` (argumento de construtor não-nulo; semântica de companion inferida) |
| Corpo (rota presente) | stream bruto de texto cifrado, apenas um arquivo (`MMS4 upload only supports a single file`); modo de streaming de comprimento fixo quando o comprimento é conhecido, senão chunked (`setChunkedStreamingMode(0)`); buffer de 16384 bytes |
| Corpo (sem rota) | `multipart/form-data` legado com partes `Content-Disposition: form-data` |
| Abort | em interrupção de thread ou flag de cancelamento o stream é preenchido (`UploadRequest/Post streaming padding bytes=`) para que o comprimento declarado seja completado (propósito inferido) |
| Resposta | até 1 MiB lido; HTTP >= 400 retorna o código, o corpo vai para `onError` |

### 8.4 Resposta (found, `MediaUploadTransfer` `C59523QnV`)

Chaves JSON lidas: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (aceito apenas se corresponder a `[A-Za-z0-9-]{1,64}`), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (string JSON aninhada com `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. Uma resposta sem `direct_path` não é tratada como erro por este parser; etapas posteriores falham com `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Upload retomável (found)

| Etapa | Detalhe |
|------|--------|
| Sondagem | mesma URL de upload mais `resume=1` (`HttpResumeCheck`); resposta JSON `{"resume": "complete"}` com `url`, `direct_path` (já enviado) ou `{"resume": <offset>}` |
| Continuar | POST com `Content-Range: bytes <offset>-*/*`, o stream é pulado para `<offset>` primeiro |
| Fallbacks | `ResumeCheck/attempting fallback MMS upload form post`, também após um erro WATLS (TLS) |
| Erro de parse | status `PBY.A03`, o upload reinicia |

### 8.6 Fornecedor de rota e retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Regra | Detalhe |
|------|--------|
| Loop de tentativa | `TransferRetries/run attempt = N; route = ...`; uma transferência por rota; `no routes` termina o loop |
| Escolha de host | host `type=primary` cujo conjunto de capability contém o tipo de mídia; as primeiras duas tentativas o usam; tentativas posteriores usam a entrada `type=fallback` e seus campos `fallback_*` (ordem inferida de fluxo de controle corrompido) |
| Tentativas | padrão 4 (`4 - extra`); com as flags **12545** e **12446** o limite pode ser sobrescrito após a tentativa 3; `max_auto_download_retry` / `max_manual_retry` (padrão 3 cada) alimentam a contagem dependente do modo (mapeamento inferido) |
| Atraso | constante de 1000 ms (`RouteSelector.A01`); com a flag **257** e tentativas extras, exponencial: base 1000 ms, `2^n`, jitter, limitado a 3000 ms |
| Erro de auth 401 / 403 | não contado como falha: espera por um token mais novo (orçamento `A0J`, padrão 20000 ms), troca, tenta novamente |
| Status HTTP retentável | `QKS.A08`: < 400 sim; 400-499 não, exceto 408 com a flag **13748**; >= 500 sim, exceto 505 e 507 |
| Proxy | com um proxy de usuário e a flag **4073** a authority de mídia se torna o host e porta do proxy a partir de `proxy_media_port` (padrão 587) |
| Verificação de saúde | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, connect 15000 ms, read 30000 ms |

---

## 9. Download

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

O construtor exige um hash de mídia, um caminho direto ou uma referência cruzada (`media hash, direct path, or cross reference is required`). `mode` é `auto` ou `manual`. `_nc_map=whatsapp-nofna` é adicionado para tipos na lista do servidor `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (prop AB, flag **4836**). A query `auth` é adicionada em um caminho com flag (`PTU.A03`) e substitui um parâmetro `auth` existente. Fotos de perfil usam o tipo `ppic`; assets estáticos usam `/wa/static` com `_nc_cat`.

### 9.2 Escolha de bucket e host (fluxo de controle decompilado, parcialmente corrompido)

- Hosts são filtrados pela capability `download` e por `download_buckets` contendo a string do bucket.
- Bucket `1` quando o caminho direto carrega `_nc_hot=<seconds>` mais novo que a janela na flag **2136**; caso contrário, com a flag **2134** e `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); bucket de fallback `0`.
- Tipos de newsletter e casos com flag pulam a lógica hot / hash.
- O bucket escolhido sai como `_nc_cat`.

### 9.3 Requisição HTTP (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Item | Valor |
|------|-------|
| Método | GET (Tigon ou `HttpURLConnection`) |
| Headers | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (com gate de flag), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (quando um ETag é conhecido) |
| Aceito | HTTP 200 e 206 |
| Parcial | previews usam um prefixo de 262144 bytes (`Range: bytes=0-262143`) |
| 416 | tratado como completo quando `Content-Range` é `*/<size>` e é igual ao tamanho local; senão reinicia (flag **29305**) ou erro |
| Allow-list | com o símbolo de flag `PTU.A04`, o host deve estar em `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` (correspondência de sufixo) a menos que a URL tenha `category=PSA`; senão `invalid_url` (8) / log `host not in media CDN allow-list` |

### 9.4 Verificação (found)

O stream de descriptografia verifica o MAC; os estágios de hash mapeiam para os status 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; entradas ausentes mapeiam para 26-30 (seção 10.2).

---

## 10. Códigos de erro

### 10.1 Tratamento de status HTTP

| Status | Comportamento |
|--------|-----------|
| 401, 403 | atualiza `media_conn`, troca o auth, tenta novamente (máx. 2 trocas) |
| 408 | retry apenas com a flag **13748** |
| 416 | ver 9.3 |
| 507 | status de download 12 `throttle`, não retentado |
| 505 | não retentado |
| outro 4xx | não retentado |
| 5xx, < 400 | retentado dentro do orçamento da tentativa |

### 10.2 Status de download (found, `QKK` `A03`)

| Código | Nome | Código | Nome |
|------|------|------|------|
| 0 | success | 17 | wamsys_failed |
| 1 | failed_generic | 18 | failed_network |
| 2 | dns_failure | 19 | failed_connect |
| 3 | timeout | 20 | host_switch_required |
| 4 | disk_full | 21 | suspicious_content |
| 5 | too_old | 23 | partial_image_downloaded |
| 6 | resume_failed | 24 | programmatic_cancel |
| 7 | hash_mismatch | 25 | failed_no_client_network |
| 8 | invalid_url | 26 | failed_no_encryption_algorithm |
| 9 | output_stream_fail | 27 | failed_no_encrypted_hash |
| 11 | no_route | 28 | failed_no_media_hash |
| 12 | throttle | 29 | failed_no_media_key |
| 13 | user_cancel | 30 | failed_no_sidecar |
| 14 | prefetch_end | 31 | failed_hash_verification |
| 15 | watls_error | 32 | enc_hash_mismatch |
| 16 | server_error | 34 | deduped |

Os códigos 10, 22, 33 e qualquer outro imprimem `invalid`. `QKK.A04` agrupa 1, 2, 3, 11, 15, 16, 18, 19, 20 e 25 (falhas do tipo rede; o rótulo é inferido).

### 10.3 Resultado de upload (found, nomes de métrica `media_upload_<NAME>`)

| Código | Nome | Código | Nome |
|------|------|------|------|
| 1 | CANCEL | 22 | FAILED_DNS_LOOKUP |
| 2 | FAILED_INSUFFICIENT_SPACE | 23 | FAILED_WAMSYS |
| 3 | FAILED_IO | 24 | FAILED_TOO_LARGE |
| 4 | FAILED_OOM | 25 | ERROR_NO_CLIENT_NETWORK |
| 5 | FAILED_BAD_MEDIA | 26 | HOST_SWITCH_REQUIRED |
| 6 | FAILED_NO_PERMISSIONS | 27 | SKIPPED_EP_NO_PRIMARY_HOST |
| 7 | FAILED_FNF | 28 | FAILED_CRONET |
| 8 | FAILED_SERVER | 29 | FAILED_NO_DIRECT_PATH |
| 9 | FAILED_REQUEST | 30 | FAILED_NO_MEDIA_KEY |
| 10 | FAILED_REQUEST_TIMEOUT | 31 | FAILED_UNKNOWN |
| 11 | FAILED_NOT_FINALIZED | 32 | CANCEL_PROGRAMMATIC |
| 12 | FAILED_OPTIMISTIC_HASH | 33 | FAILED_NO_ROUTE |
| 13 | FAILED_MEDIA_CONN | 34 | FAILED_CANNOT_TRANSCODE |
| 14 | FAILED_OPTIMISTIC_NETWORK_UNSAFE | 35 | FAILED_UNKNOWN_MIMETYPE |
| 15 | FAILED_THROTTLE | 36 | FAILED_SERVER_REJECTED_MEDIA |
| 16 | FAILED_NO_SUCH_ALGORITHM | 37 | FAILED_IO_ENCRYPTION |
| 17 | FAILED_NETWORK | 38 | FAILED_STREAMING_METADATA_TOO_LARGE |
| 18 | FAILED_WATLS | 39 | FAILED_MUSIC_REPORTING |
| 19 | FAILED_URL | 20 / 21 | FAILED_TRANSCODING_UNKNOWN / FAILED_FILE_FORMAT_UNSUPPORTED |

Mapeamento de exceção em `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, outro `IOException` 18 (rede fora do ar) ou 3, `CancellationException` 1, `C7CL` 21, qualquer outra coisa 31. Após um resultado sem sucesso com 5, 21, 24, 34, 35 ou 36 a chave e o hash cacheados (`A0B`, `A0C`) são limpos.

---

## 11. Media retry (requisição de novo upload)

Quando um download falha porque o objeto desapareceu (tipicamente status 5 `too_old`, ou uma resposta de classe 404), o receptor pede ao telefone do remetente para fazer upload novamente.

### 11.1 Requisição: recibo `server-error` (found, `SendMediaErrorReceiptJob`)

| Variante | Writer | Wire |
|---------|--------|------|
| Multi-dispositivo (próprio primário) | case 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Legado | case 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (sem `rmr`) |

`enc_iv` é 12 bytes aleatórios; `enc_p` é produzido nativamente (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) a partir de uma mensagem que carrega o stanza id. A biblioteca nativa mantém a info HKDF `WhatsApp Media Retry Notification`; AES-GCM com o stanza id como AAD e uma chave HKDF de 32 bytes é inferido a partir do IV de 12 bytes e da implementação Baileys. As props de servidor `mms4_media_retry_notification_encryption_enabled` e `mms4_server_error_receipt_encryption_enabled` são tokens de dicionário (efeito inferido: controla se `<encrypt>` é enviado).

### 11.2 Resposta: notificação `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Etapa | Detalhe |
|------|--------|
| Verificação de conta | `rmr` de outra conta loga `cross-account-rmr` e é descartado a menos que o símbolo de flag `PTV.A0F` esteja ativo |
| Busca | mensagem por `(chat, id, from_me)`; mensagens não-mídia logam `message is null or not media` |
| Descriptografia | nativa (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); o modelo de resultado fornece `directPath` (armazenado na mensagem) e um int de resultado |
| Resultado | `<error code>` sobrescreve o resultado; o handler compara o valor com 2 e 3 (com a numeração pública de proto `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferido) |
| Continuação | o downloader recebe o novo caminho direto (`resume reuploading download`); sem downloader ativo a mensagem é colocada na fila para download automático |
| Relatório | com a flag **5718** o `reporting_token` é armazenado para a mensagem |

---

## 12. Mídia view-once e de status

| Tópico | Fato (found) |
|-------|--------------|
| Cripto / transporte | idêntico à mídia normal: mesmo `MmsType`, mesmo HKDF, mesmas URLs; não existe nenhum tipo view-once na tabela |
| Flag | `viewOnce` é um campo em `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); container `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Regras locais | o remetente não pode abrir sua própria mídia view-once (`senders can not view their own media`); miniaturas view-once são excluídas por `EphemeralUpdateRunnable/deleteViewOnceThumbnails`; um áudio view-once sem chave de mídia não é enviado (`unable to send encrypted media message due to missing mediaKey`) |
| Se o servidor exclui o objeto após a visualização | unknown |
| Status (`status@broadcast`) | usa as linhas `MmsType` normais (imagem, vídeo, gif, áudio) com seus próprios ids numéricos; não existe nenhuma info HKDF `status`; os únicos tipos `*-status` são os de newsletter (seção 13) |
| Limites de status | os tokens de dicionário `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` são props de servidor (valores: unknown) |
| Download de status | `C59526QnY` mantém um `MediaDownload` e uma variante `StatusMediaDownload`; ambos constroem a URL com o mesmo gerador |

---

## 13. Mídia de newsletter (canal)

| Aspecto | Newsletter | Normal |
|--------|-----------|---------|
| Surface na URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | nomes simples |
| Criptografia | nenhuma: o downloader de artwork exige `artworkEncSha256` apenas para conteúdo não-newsletter (`required fields missing - artworkEncSha256 is null for encrypted content`); para outros tipos existe o stream de passagem `C59535Qnh` (identidade). As linhas `MmsType` ainda carregam bytes de info HKDF (não usados, inferred) |
| Token de upload | aleatório, não vinculado ao hash (seção 8.2) | segredo por instalação + hash |
| Filtro de rota | sem lógica de bucket hot / hash para nomes começando com `newsletter` | lógica de bucket (9.2) |
| `ip_token` do `media_conn` | `ip_token` é aplicado para newsletter independentemente de `set_ip_token` (flag **12149**) | apenas quando `set_ip_token` é true |
| Trabalho do servidor | `server_thumb_gen=1` (flags **11191**, **11192**), `server_transcode=1` para vídeo (flag **9096**) | não definido |
| Flag **27920** | lida no caminho de newsletter de `C15490gQ`; efeito unknown | |

---

## 14. Caminho express e outras variantes de upload

| Variante | Evidência |
|---------|----------|
| Caminho express | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) enviada como mensagem E2E (`FMessageMediaExpressPathNotify`, exige url, hash e comprimento); `ExpressPathDownload` loga `EP gain <ms> <bytes>`; log de upload `Use static route supplier for express path upload`; resultado de upload 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Comportamento do lado do servidor: unknown |
| Upload otimista | surface `optimistic`; resultado 12 de reverificação de hash; protocolo: unknown |
| Histórico / app state | `md-msg-hist`, `md-app-state` usam o pipeline normal com suas strings de info |
| Histórico de grupo | `group-history`, info `Group History`, mime `application/protobuf` verificado pelo receptor (`C34677F2y`); caminho segue a seção 8.1 (`/mms/group-history/...`, inferido da composição genérica) |

### 14.1 Envio de tema de papel de parede de chat (novo na 2.26.45.10, found)

Um fluxo "enviar ao chat" de tema por chat trafega por este pipeline genérico sem modificação. Ponto de entrada: `ChatThemeViewModel.sendThemeToChat` (coroutine Kotlin; locals `targetJid`, `sentBundle`, `sharedTheme` de metadados de debug preservados) resolve a fonte de papel de parede escolhida (`DOWNLOADED`, `USER_PROVIDED`, `ANIMATED`, `GRADIENT`, `DEFAULT`, `NONE`) e chama `ChatThemeSettingSenderImpl.A06` → `A01`.

| Etapa | Detalhe (found) |
|------|-----------------|
| Cópia local | o `File` de papel de parede fonte é copiado para o armazenamento do app sob `chat_theme_sent_wallpapers/<uuid>.jpg` |
| Upload | `ChatWallpaperUploader.A00` envolve `MediaUploadCoordinatorImpl.A0G` (o mesmo pipeline `media_conn` → HKDF → AES-CBC → HMAC → POST das seções 1-8 acima), solicitando o modo de criptografia `LX/8cp;->A02`, cujo campo `value` é a string literal `"E2EE"` |
| Cópia do resultado | o resultado do upload (`SGq`) é copiado campo a campo para um descritor genérico de anexo de mídia (`LX/8cr`): string de resultado de upload → direct path, bytes de chave de mídia, um timestamp, e mais três arrays de bytes de hash/HMAC |
| Superfície do setter | o descritor é empurrado através de `LX/1iA` (estende `LX/19i`), a **mesma interface genérica de setter de anexo de mídia** que builders de mensagem de imagem comuns usam; seus campos se alinham posicionalmente com `directPath` (**11**), `mediaKey` (**8**), e os campos de bytes `fileSha256`/`fileEncSha256` (**9**/**12**, seção 6) de `imageMessage` |
| Mimetype | `image/jpeg` é definido explicitamente na mesma chamada |

Isto é enviado a um parceiro de chat real (`targetJid`), não uma sincronização de preferência de exibição apenas local: para temas baseados em imagem, o próprio bitmap do papel de parede é reconvertido e enviado através do caminho de mídia E2EE padrão, então o cliente receptor baixa e descriptografa uma imagem real em vez de aplicar um preset de tema conhecido. Nenhum tipo de mídia de upload personalizado ou sobrescrita de caminho HTTP (diferente do `/mms/group-history` do histórico de grupo, seção 14) foi encontrado para este fluxo — parece reutilizar um `MmsType` existente (provavelmente `image`, não confirmado separadamente).

**Unknown**: o campo `oneof` exato de `Message` que termina carregando este anexo — `LX/19i`/`LX/1iA` são grandes classes base compartilhadas usadas por muitos tipos de mensagem de saída, e o local de alocação concreto além de seus setters não foi alcançado nesta passagem. Também unknown: se uma escolha de tema de cor sólida/sem papel de parede (`DEFAULT`/`NONE`) é enviada de alguma forma, ou permanece apenas local. Nenhum novo tipo de mensagem protobuf ou operação GraphQL/MEX foi encontrado para este recurso (verificado contra os diffs de proto e de query 2.26.41.6→2.26.45.10); a leitura mais defensável é que isto trafega em um campo de mensagem de mídia existente, mais provavelmente o próprio `imageMessage` — **inferred**, não confirmado.

---

## 15. Hardening nativo dos parsers de mídia (found, strings e exports das bibliotecas desempacotadas)

81 shared objects são desempacotados do arquivo superpack. Parsers com memory-unsafety de bytes controlados por atacante são ou colocados em sandbox ou substituídos por Rust.

| Entrada | Componente | Hardening |
|-------|-----------|-----------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp compilado para WebAssembly e rebaixado para C pelo wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), wrapper `whatsapp::security::LibwebpSandbox` em uma sandbox thread-local; flag Java `sWebPSandboxEnabled`; log de falha `sandboxed WebP decode failed: status=%d`; guardas `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib em uma sandbox wasm2c / WASI-minrt (`GiflibSandbox`, `wasi::minrt`); classes JNI `SandboxedGifImage`, `SandboxedGifFrame`; guarda `Called memcpy for memory larger than the sandbox` |
| Arquivos Ogg / Opus | `libwhatsapp.so` | sandboxes RLBox wasm2c para `libogg.wasm` e `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; log de trap `wasm2c sandbox trap: %s (code=%d)` |
| Parse de container e stream | crates Rust de `libwhatsapp.so` | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, segmentador DASH, edit lists), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (valores de digital-source-type IPTC como `trainedAlgorithmicMedia`, C2PA) |
| Decodificação AV1 | `libdav1d.so` | dav1d **1.5.1** (string de versão); exporta a API `dav1d_*` |
| Codificação AV1 | `libwzav1.so` | versão 2.3.1; exporta apenas `wz_encoder_*` e `wz_codec_version*`; nenhum símbolo de decoder, então não faz parse de bitstreams remotos |
| Frames H.264 / H.265 | `MediaCodec` da plataforma | fora do app |

Parsers em Rust falham com panics (`assertion failed: ...`, `While parsing field '...' in ...`) em vez de corrupção de memória: found como strings, efeito inferido. A sandbox `rlbox` cobre libogg e opusfile em `libwhatsapp.so`; outras bibliotecas usam wasm2c sem o wrapper RLBox (inferido a partir dos símbolos). Se todo caminho de mídia entrante alcança esses parsers antes da interação do usuário: unknown. Comportamento dinâmico (fuzzing, crashes em runtime): não testado.

---

## 16. Feature flags (ids como lidos nos pontos de chamada; nomes não resolvidos)

| Flag | Onde | Controla |
|------|-------|----------|
| **149** | `RouteSelector`, `C43951qe` | persistir e recarregar `media_conn` nas preferências |
| **257** | construtor de `Mms4RouteSupplier` | objeto de backoff exponencial |
| **258** | `Mms4RouteSupplier.A03` | int: tentativas extras para o modo 0 |
| **2134** | `A02` | bucket de download baseado em hash |
| **2136** | `A02` | janela de conteúdo hot (long) |
| **4073** | `A00` | rotear mídia através do proxy do usuário |
| **4836** | `Mms4DownloadUrlGenerator` | lista de tipos de baixa taxa de acerto (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | tratamento do token de relatório |
| **9096** | `QBE` | `server_transcode=1` (vídeo de newsletter) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` para imagem / vídeo de newsletter |
| **12149** | `RouteSelector.A0L`, `A03` | usar `ip_token` |
| **12545** / **12446** | `A05` | sobrescrever o limite de tentativas após a tentativa 3 |
| **13748** | `QKS.A08` | retentar HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | pontos de entrada de `RouteSelector` | booleano passado à seleção de rota como a flag de upload (semântica não resolvida) |
| **24661** | `MediaCryptoProvider` | validação de domínio de chave não-E2EE |
| **29305** | `PlainDownloadTransfer` | tratamento de 416 |
| **37982**, **38437** | `C43481Ixw` | propriedade Tigon, timeout de requisição |

---

## 17. Baileys (`baron-baileys-v2`, leitura de código, nada testado)

| Aspecto | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Requisição `media_conn` | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` tem uma variante opcional `last_id` | sempre `<media_conn>`, com `last_id` quando existe um id anterior |
| Campos parseados | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | não lê `maxContentLengthBytes`; adiciona `auth_ttl`, `max_buckets`, `is_new`, `id`, campos de fallback, filhos de capability, contagens de retry, `ip_token` |
| Comprimento HKDF | `hkdf(key, 112, {info})`, usa os bytes 0-79 | 80 bytes; os primeiros 80 bytes de uma saída HKDF não dependem do comprimento solicitado, então IV, chave de cifra e chave MAC são idênticos |
| Strings de info | `WhatsApp <X> Keys`; `gif` e `ptv` mapeiam para Video, `ptt` para Audio, `sticker` para Image | mesmas strings e mapeamentos |
| Cifra, MAC, hashes | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` anexado, `fileSha256`, `fileEncSha256` sobre `ct + mac` | mesmo |
| URL de upload | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Codificação do hash | base64 url-safe, padding `=` removido, depois `encodeURIComponent` | base64 url-safe, padding `=` mantido |
| Token | `fileEncSha256` url-safe | `SHA-256(installSecret || fileEncSha256)` (newsletter: aleatório) |
| Tabela de caminho | `sticker` e `thumbnail-link` para `/mms/image`, `ptv` para `/mms/video`, `md-msg-hist` para `/mms/md-app-state`, sem `ptt` | a string `MmsType` é o segmento de caminho: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Headers | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | nenhum `Origin` encontrado; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | tenta cada host uma vez em ordem | fornecedor de rota com tentativas, troca de token em 401 / 403, sondagem de resume |
| Resume | nenhum encontrado (`resume=1`, `Content-Range` ausentes) | sondagem `resume=1` e `Content-Range` |
| Sidecars | nenhuma geração de `streamingSidecar`, `firstScanSidecar` ou `scansSidecar` encontrada em `src` | gerados para vídeo, áudio, imagens progressivas |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | milissegundos internamente, segundos no proto |
| Recibo de retry | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = stanza id, IV de 12 bytes, info HKDF `WhatsApp Media Retry Notification` | writer case 327 tem o mesmo layout de nó; IV de 12 bytes e a string de info são found; GCM / AAD inferred |
| Mapa de resultado de retry | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | não aplicável (compara os valores 2 e 3) |

Consequências práticas (apenas leitura de código): um upload Baileys de um objeto `md-msg-hist` usa uma string de caminho diferente da do cliente Android; base64 com padding no caminho é uma diferença visível; qualquer tolerância do servidor para essas variantes é unknown.

---

## 18. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|-----|
| Upload 401 / 403 | `auth` expirado ou substituído | atualizar `media_conn`, reenviar com o novo `auth` |
| Upload não retorna `direct_path` | upload rejeitado ou incompleto | verificar status; sondagem de resume com `resume=1` |
| Download 404 / status 5 `too_old` | objeto expirado no CDN | enviar o recibo `server-error` (seção 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | bytes corrompidos ou `fileEncSha256` errado | buscar novamente; verificar a fonte do hash |
| Verificação de MAC falha | chave de mídia errada, info HKDF errada (mistura de tipo), ou arquivo truncado | usar a string de info do `MmsType` correto; não reutilizar info de Image para linhas `sticker-pack` ou `ptt` |
| `invalid_url` (8) | host fora da allow-list do CDN | aceitar apenas os sufixos listados |
| `throttle` (12), HTTP 507 | throttle do servidor | esperar `backoff` segundos (máx. 10800) |
| `no_route` (11) | nenhum host de `media_conn` usável para o tipo | solicitar `media_conn`, verificar as tags de capability |
| `failed_no_media_key` (29), `no_sidecar` (30) | campo proto ausente | exigir `mediaKey`; sidecar apenas para streaming |

---

## 19. Distinções importantes

| Não confundir | Fato |
|----------------|------|
| lista de hosts de `media_conn` vs. URL de upload | o IQ fornece hosts e um `auth`; o caminho, token e query da URL são construídos por transferência |
| `auth` vs. `token` | `auth` é o token de nível de conta do `media_conn`; `token` é por arquivo |
| HKDF 80 vs. 112 bytes | mesmas chaves; o Android deriva 80 |
| `fileSha256` vs. `fileEncSha256` | hash do texto plano vs. hash de `ciphertext + mac10` |
| `fileEncSha256` no caminho vs. `directPath` | o caminho de upload usa o hash; o download usa o `directPath` retornado pelo servidor |
| `mediaKeyTimestamp` vs. janela de reuso de chave | timestamp em segundos no wire; janela de reuso de 2-3 dias no remetente |
| Sidecar de streaming vs. `fileEncSha256` | MACs de 10 bytes por chunk vs. hash do arquivo inteiro |
| Media retry vs. reenvio | o remetente reenvia o mesmo objeto e responde com um novo `directPath`; a mensagem não é reenviada |
| Mídia de newsletter vs. mídia normal | não criptografada, surface `newsletter`, token aleatório |
| `libwzav1` vs. `libdav1d` | encoder vs. decoder; apenas o decoder faz parse de dados remotos |

---

## 20. Fluxo completo (enviar e receber uma imagem)

```
[Sender app]  pick file → process (resize, strip) → MmsType "image"
     │
     ▼
[RouteSelector]  media_conn fresh? (conn/auth > 120 s left) ── no ──► <iq xmlns="w:m" type="set"><media_conn last_id/></iq>
     │                                                                   │ ◄── auth, ttl, auth_ttl, max_buckets, hosts
     ▼
[Uploader]  mediaKey = 32 B SecureRandom ; okm = HKDF(mediaKey, "WhatsApp Image Keys", 80)
     │  iv | cipherKey | macKey ; AES-CBC encrypt ; mac10 = HMAC(macKey, iv||ct)[0:10]
     │  fileSha256 (plain), fileEncSha256 (ct||mac10) ; optional sidecar / thumbnails
     ▼
[Mms4RouteSupplier]  host: type=primary, upload set has "image"
     │  POST https://host/mms/image/<hash>?direct_ip=0&token=<sha256(secret||hash)>&auth=<auth>
     │      Host, Accept-Encoding: identity, body = ct||mac10   (resume: ?resume=1, Content-Range)
     ▼
[Media server]  (not observed) ──► {"url","direct_path","handle","ts",...}
     │
     ▼
[Sender]  ImageMessage{mediaKey, fileSha256, fileEncSha256, directPath, mediaKeyTimestamp(s), jpegThumbnail, ...}
     │  Signal-encrypted message over chatd
     ▼
[Receiver]  host from media_conn (download set + bucket _nc_cat)
     │  GET https://host<directPath>?direct_ip=0&_nc_cat=<b>&mode=auto
     │      Range: bytes=0-   (200 or 206)
     ▼
[Receiver]  check enc hash → MAC → AES-CBC decrypt → check fileSha256 → store
     │
     ├── object gone (404 / too_old) ──► <receipt type="server-error"><encrypt enc_p enc_iv/><rmr/></receipt>
     │                                         │
     │                                [Sender phone] re-uploads, answers
     │                                         ▼
     └──────────────────────────────── <notification type="mediaretry"><encrypt enc_p enc_iv/></notification>
                                         → new directPath → resume download
```

---

## 21. Incertezas

| Item | Status |
|------|--------|
| Comportamento do servidor (validação de token, dedupe, vida útil do objeto, exclusão view-once) | lado do servidor |
| Nomes de query `_nc_cbep`, `_nc_rmr`, `type`; flag **21807** e os ids `PTU.*` | nomes ou significado não resolvidos |
| Ids numéricos em `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | significado não resolvido |
| Cifra nativa de media-retry (AES-GCM, AAD, comprimento de chave) | string de info found; algoritmo inferred |
| Consumo de `ip_token`, valor de `X-FB-nc-oc`, fonte de `Companion_User_Secret` | não resolvido |
| Uso do domínio de chave de mídia NON_E2EE | não resolvido |
| Protocolos de caminho express e upload otimista | não resolvido |
| Ordem exata de host entre tentativas e as contagens de tentativa dependentes do modo | fluxo de controle decompilado corrompido |
| Qual mídia entrante alcança qual parser em sandbox antes da interação do usuário | não mapeado |
| Tráfego | nada capturado; sem teste dinâmico |
