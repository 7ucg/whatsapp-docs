<!-- src-sha1: d4ba76d600d4bfecb03ea6dfec4064e9d1ae1733 -->
# WhatsApp Stickers — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** proto `Message.StickerMessage` (metadados de imagem/Lottie, flags de avatar/AI/premium, `emojis`, `accessibilityLabel`), sound stickers embutidos (`StickerMessage.audioMessage`), wrappers genéricos `lottieStickerMessage` / `audioStickerMessage`, `stickerPackMessage` (compartilhamento de pack), armazenamento local de sticker pack e o formato ZIP `.was`/Lottie, `stickerSyncRmrMessage` (confirmado ausente), intents de third-party sticker pack e contrato de content provider, provider nativo de geração de sticker por AI, busca local de stickers, feature flags; a criptografia de mídia não é repetida (ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md))

---

## 1. Visão geral

Um "sticker" no Android é um de vários tipos de mensagem de wire mais um grande subsistema de app first-party (loja, recentes locais, busca, geração por AI) e uma superfície pública de integração third-party (intents + content providers). Todos os bytes de mídia (imagem do sticker, ZIP do pack, thumbnails) trafegam pelo mesmo pipeline de mídia criptografada que qualquer outro anexo — ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) seção 3 para as linhas de `MmsType` (`sticker`, `sticker-pack`, `thumbnail-sticker-pack`, `newsletter-sticker`, `newsletter-sticker-pack`).

| Entidade | Campo de `Message` | Wire type | Papel |
|--------|------------------|-----------|------|
| Sticker individual | `stickerMessage` | **26**, `StickerMessage` (`C30611DTf`) | uma imagem/animação de sticker enviada em um chat |
| Sound sticker (embutido) | `StickerMessage.audioMessage` | campo **26** de `StickerMessage`, `oneof audio` → `AudioMessage` | um clipe de voz curto anexado a um envio de sticker |
| Wrapper Lottie | `lottieStickerMessage` | **74**, `FutureProofMessage` (`BD2`) | envelope genérico, o nome sugere um payload específico de Lottie; conteúdo aninhado não resolvido |
| Wrapper audio-sticker | `audioStickerMessage` | **134**, `FutureProofMessage` (`BD2`) | mesmo padrão de envelope genérico, novo nesta build; conteúdo aninhado não resolvido |
| Sticker pack | `stickerPackMessage` | **86**, `StickerPackMessage` (`C30610DTe`) | compartilha/instala um pack (ZIP de stickers) |
| Pedido de sync de sticker | `stickerSyncRmrMessage` | **47** (builds antigas) | **ausente** do proto `Message` na 2.26.41.6 (ver seção 7) |
| Reação de sticker em status | `statusStickerInteractionMessage` | **110**, `StatusStickerInteractionMessage` (`C30560DRg`) | sticker de reação em uma postagem de status; fora do escopo aqui além deste apontamento |
| Add-pack third-party | `Intent` Android | `com.whatsapp.intent.action.ENABLE_STICKER_PACK` | app externo pede ao WhatsApp para importar um pack que ele hospeda |
| Envio third-party | `Intent` Android | `com.whatsapp.intent.action.SEND_STICKER` | app externo entrega um sticker WebP único ao seletor do WhatsApp |
| Contrato de conteúdo do pack | `ContentProvider` (próprio do app externo) | `content://<authority>/metadata`, `/stickers`, `/stickers_asset` | como o WhatsApp lê um pack third-party |
| Geração de sticker por AI | `ContentProvider` (próprio do WhatsApp) | `content://com.whatsapp.provider.sticker_command/generate` | criação de sticker por GenAI no app, consumida via chamadas de content provider, não uma mensagem de chat |

Os níveis seguem `IMPORTANT.md`: **found** = lido diretamente no código decompilado/strings/manifest, **inferred** = deduzido pelo formato do código, **unknown** = não resolvido. Toda a evidência aqui é estática (APK decompilado + manifest); nada foi capturado no wire.

---

## 2. `Message.StickerMessage` (campo 26)

### 2.1 Campos (found, `C30611DTf`)

| Campo | # | Tipo | Uso |
|-------|---|------|-----|
| `url` | 1 | string | URL completa legada |
| `fileSha256` | 2 | bytes | hash do texto puro |
| `fileEncSha256` | 3 | bytes | hash do texto cifrado+MAC, também o hash do caminho de upload |
| `mediaKey` | 4 | bytes | chave de 32 bytes, HKDF info `WhatsApp Image Keys` (pipeline de mídia, não repetido aqui) |
| `mimetype` | 5 | string | `image/webp` para stickers comuns |
| `height` / `width` | 6 / 7 | uint32 | dimensões em pixels |
| `directPath` | 8 | string | caminho de download |
| `fileLength` | 9 | uint64 | tamanho do texto cifrado |
| `mediaKeyTimestamp` | 10 | int64 | segundos |
| `firstFrameLength` / `firstFrameSidecar` | 11 / 12 | uint32 / bytes | sidecar para o primeiro quadro da animação (ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) seção 7) |
| `isAnimated` | 13 | bool | WebP animado |
| `pngThumbnail` | 16 | bytes | thumbnail inline |
| `contextInfo` | 17 | `ContextInfo` | metadados de citação/resposta/anúncio |
| `stickerSentTs` | 18 | int64 | timestamp de envio |
| `isAvatar` | 19 | bool | sticker de avatar |
| `isAiSticker` | 20 | bool | sticker gerado por AI |
| `isLottie` | 21 | bool | o payload do sticker é uma animação Lottie, não um WebP comum (ver seção 4) |
| `accessibilityLabel` | 22 | string | texto para leitor de tela |
| `premium` | 24 | int32 | não resolvido (nenhum consumidor encontrado) |
| `emojis` | 25 | string | **uso found**: tag de busca local, ver seção 9 |
| `audioMessage` | 26 | `AudioMessage` (`oneof audio`) | clipe de sound sticker embutido, ver seção 3 |

Lacunas nos números de campo 14, 15, 23: nenhum campo definido; uso anterior desconhecido. Isso corrige a nota inicial de `Messages/stickerMessage`, que lista `emojis` (25) como o último campo e nem inclui o campo 26 (`audioMessage`) — confirmado presente em `C30611DTf` na 2.26.41.6 (`AUDIO_MESSAGE_FIELD_NUMBER = 26`) e corresponde ao bloco `oneof audio` do proto atual de `baron-baileys-v2`.

### 2.2 Classificação por string de tipo de mensagem (found)

Strings de tipo observadas associadas a um envio de `StickerMessage`/`StickerPackMessage`, coletadas do despacho de analytics (`C21880sC`) e do helper de tipo de sticker: `sticker`, `avatar_sticker`, `genai_sticker`, `1p_sticker`, `user_created_sticker`, `sticker_pack`. `avatar_sticker` e `genai_sticker` vêm de `isAvatar`/`isAiSticker`; `1p_sticker` e `user_created_sticker` se alinham com o enum `StickerPackOrigin` (seção 5), mas a função de decisão exata que escolhe entre `sticker`, `1p_sticker` e `user_created_sticker` não foi isolada nesta passagem (precedência unknown). O Baileys (`messages-send.js`) verifica `isLottie` antes de `isAvatar` ao derivar essa string no lado do cliente; se o Android faz o mesmo não foi confirmado.

### 2.3 `emojis` e `accessibilityLabel` (found, aprimorado a partir do material inicial)

- `emojis` (25): consumido por `EmojiGroupMapper`/`StickerSearchManager` como a string de tag de busca local — confirma seu propósito além do nome do campo (seção 9). Não consultado no servidor.
- `accessibilityLabel` em um *sticker enviado* e `sticker_accessibility_text` em um *sticker de pack third-party* (`StickerContentProviderFetcher`, seção 8) são limitados a **125** caracteres para um sticker estático e **250** para um animado (`ThirdPartyStickerFetcher`, inteiros literais 125/250; o JADX exibe erroneamente o branch de 125 como um campo não relacionado `C30628DTw.SPLIT_PAYMENT_MESSAGE_FIELD_NUMBER` porque esse campo também tem o valor 125 — um artefato de nomenclatura do decompilador, o valor numérico em si é lido diretamente do bytecode).

---

## 3. Sound stickers: `StickerMessage.audioMessage` e `audioStickerMessage` (134)

Dois mecanismos distintos, ambos found, não os confunda:

| Mecanismo | Campo | Evidência |
|-----------|-------|----------|
| Clipe embutido | `StickerMessage.audioMessage` (26, `oneof audio`) | presente em `C30611DTf`; corresponde exatamente ao `WAProto.proto` do `baron-baileys-v2` (`oneof audio { Message.AudioMessage audioMessage = 26; }`) |
| Wrapper independente | `Message.audioStickerMessage` (134, `FutureProofMessage`/`BD2`) | campo novo em `C30628DTw` para a 2.26.41.6, não presente no material inicial de `Messages/`; mesmo padrão de envelope genérico de `lottieStickerMessage` (seção 1), conteúdo aninhado unknown |

O pacote de suporte do cliente `com.whatsapp.stickers.sound` confirma um recurso de autoria de "sound sticker": `StickerOpusEncoder` (`nativeEncode(short[] pcm, String outPath)`, encode Opus nativo de um clipe gravado) e `SoundStickerAudioDownloader` (garante que o áudio anexado seja buscado antes da reprodução, roteando pelo pipeline de mídia comum). Isso é consistente com embutir uma nota de voz curta via campo 26 em vez de (ou junto com) o wrapper mais novo do campo 134.

---

## 4. Formatos de arquivo de sticker

### 4.1 WebP simples e animado (found)

`mimetype = image/webp`; `isAnimated` sinaliza um WebP animado. A decodificação passa pelo libwebp sandboxed da `libstatic-webp.so` (ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) seção 15).

### 4.2 Stickers Lottie — container ZIP `.was` (found, `LottieStickerZipEntrySaver` / `C161836tL`)

Quando `isLottie` está definido, o arquivo de mídia do sticker não é um WebP: é um arquivo ZIP, salvo e lido via `LottieStickerZipEntrySaver`, que deve conter:

| Entrada | Papel |
|-------|------|
| `animation/animation.json` | o JSON de animação Lottie (bodymovin), primário |
| `animation/animation.json.trust_token` | token de confiança/assinatura complementar para o JSON |
| `animation/animation_secondary.json` + `.trust_token` | variante secundária de animação opcional |

Um extrator genérico em nível de pack (`C161826tK`, log tag `StickerPackZipEntrySaver`, nome da classe base `SafeZipEntrySaver`) também restringe as extensões de arquivo extraídas, via allow-list, a `png`, `webp` e `was` — ou seja, a extensão pública de arquivo `.was` ("WhatsApp Animated Sticker") é o marcador em disco/entrada de ZIP para esse container Lottie, verificado contra o MIME declarado (`application/was`) via um content sniffer antes da aceitação.

### 4.3 Limites de extração do ZIP do pack (found, construtor de `C161826tK`)

| Limite | Valor |
|-------|-------|
| Máximo de entradas por ZIP de pack | **65** (hard-coded) |
| Máximo de bytes por entrada | token de dicionário (flag id **1900**, KB) × 1024 |
| Máximo de bytes totais por pack | mesmo token × 1024 × 65 |
| Path traversal | o caminho de destino de cada entrada é canonicalizado e deve resolver dentro do próprio diretório do pack ("Zip entry is attempting to save outside of current directory") antes que qualquer byte seja escrito — proteção zip-slip |
| Entrada rejeitada | excluída após falha na verificação de content-type, registrada como `StickerPackZipEntrySaver/file in zip is not valid` |

Isso corrobora e amplia a nota inicial de `Messages/stickerPackMessage` (que citava "ZIP extraction and file validation" e "validates sticker files reside within extracted ZIP boundaries" da 2.26.34.4 apenas como referência de log, sem os limites).

---

## 5. `Message.StickerPackMessage` (campo 86)

### 5.1 Campos (found, `C30610DTe`) — corresponde ao material inicial e ao `baron-baileys-v2` exatamente

| Campo | # | Tipo |
|-------|---|------|
| `stickerPackId` | 1 | string |
| `name` | 2 | string |
| `publisher` | 3 | string |
| `stickers` | 4 | `Sticker` repetido |
| `fileLength` / `fileSha256` / `fileEncSha256` / `mediaKey` / `directPath` / `mediaKeyTimestamp` | 5, 6, 7, 8, 9, 13 | referência de mídia do ZIP do pack (`MmsType` `sticker-pack`, HKDF info `WhatsApp Sticker Pack Keys`) |
| `caption` | 10 | string |
| `contextInfo` | 11 | `ContextInfo` |
| `packDescription` | 12 | string |
| `trayIconFileName` | 14 | string |
| `thumbnailDirectPath` / `thumbnailSha256` / `thumbnailEncSha256` / `thumbnailHeight` / `thumbnailWidth` | 15–19 | thumbnail do pack (`MmsType` `thumbnail-sticker-pack`) |
| `imageDataHash` | 20 | string |
| `stickerPackSize` | 21 | uint64 |
| `stickerPackOrigin` | 22 | enum `StickerPackOrigin` |

`Sticker` aninhado: `fileName` (1), `isAnimated` (2), `emojis` (3, repetido), `accessibilityLabel` (4), `isLottie` (5), `mimetype` (6), `premium` (7).

`StickerPackOrigin`: `FIRST_PARTY` = 0, `THIRD_PARTY` = 1, `USER_CREATED` = 2.

### 5.2 Armazenamento local (found, `AbstractC149676Ty.java`, `C1888782f.java`, `C0R5.java`)

| Tabela | Colunas |
|-------|---------|
| `message_sticker_pack` | `message_row_id`, `sticker_pack_id`, `pack_name`, `pack_description`, `publisher`, `tray_icon_file_name`, `image_data_hash`, `sticker_pack_size`, `sticker_pack_origin`; indexada em `pack_name` e `publisher` |
| `message_sticker_pack_stickers` | `_id`, `message_row_id`, `file_name`, `is_animated`, `emojis`, `accessibility_label`, `is_lottie`, `mimetype` |

Isso substitui o apontamento do material inicial para a versão 2.26.34.4 (`StickerPackMessageMapper` / `message_sticker_pack`, citado apenas por log string) pela lista concreta de colunas da 2.26.41.6.

---

## 6. `stickerSyncRmrMessage` — confirmado ausente na 2.26.41.6

O campo 47 (`StickerSyncRMRMessage`: `filehash` string repetida, `rmrSource` string, `requestTimestamp` int64) **não** aparece em `C30628DTw` (o container `Message`) na 2.26.41.6: nenhum número de campo 47 mapeia para ele, e nenhuma classe ou string contendo `StickerSyncRMR`/`stickerSyncRmr` existe em nenhum lugar da árvore decompilada. Isso corresponde e amplia a própria observação do material inicial de que o campo já estava ausente na 2.26.36.1 — ele permanece ausente cinco builds depois. Pelo contrato de evidência, isso é uma **ausência observada**, não uma remoção confirmada: se foi renomeado, movido para outro proto, ou removido completamente é unknown.

Uma tabela indexada por `filehash` ainda existe, mas para um propósito não relacionado: `RecentStickerDBStorage` (`C6VB`, `C17460jr`, `C6V8`) rastreia stickers enviados/recebidos localmente por hash de arquivo para a bandeja de recentes — isso é escrituração local, não a mensagem de sync do wire, e não deve ser confundido com ela.

---

## 7. API de sticker pack third-party

Essa é uma superfície de integração pública, documentada por convenção (família de permissão `com.whatsapp.sticker.READ`); tudo a seguir é found no `AndroidManifest.xml` e nas classes que a sustentam.

### 7.1 Superfície do manifest

| Componente | Declaração |
|-----------|-------------|
| Permissão | `com.whatsapp.sticker.READ` — `android:readPermission` obrigatório no próprio content provider de um app third-party antes que o WhatsApp o consulte |
| Activity de add-pack | `com.whatsapp.stickers.ui.thirdpartystickers.AddThirdPartyStickerPackActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.ENABLE_STICKER_PACK` + `category DEFAULT` |
| Alias legado de add-pack | `activity-alias` `com.whatsapp.stickers.thirdpartystickers.AddThirdPartyStickerPackActivity` → mesmo destino (mantido para apps construídos contra o nome de pacote pré-refatoração) |
| Activity de envio de sticker único | `com.whatsapp.stickers.command.send.SendStickerCommandActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.SEND_STICKER` + `category DEFAULT` + `data mimeType="image/webp"` |
| Provider de verificação de whitelist | `com.whatsapp.provider.sticker_whitelist_check` → `WhitelistPackQueryContentProvider`, `exported="true"` |
| Deep link | `whatsapp://stickerpack` (`<data android:host="stickerpack" android:scheme="whatsapp"/>`); a activity/roteamento de destino para esse host específico não foi isolado nesta passagem (unknown) |

### 7.2 Contrato do intent `ENABLE_STICKER_PACK` (found, `AddThirdPartyStickerPackActivity`)

Extras do pedido (`String`): `sticker_pack_id`, `sticker_pack_authority`, `sticker_pack_name`.

Validação antes de qualquer busca:
1. `getCallingActivity()` deve ser não nulo (o intent deve vir de `startActivityForResult`, não de um lançamento tipo broadcast puro).
2. `PackageManager.resolveContentProvider(sticker_pack_authority, …)` deve resolver para um provider.
3. O pacote do provider resolvido deve ser igual ao pacote da activity chamadora — **um app só pode se responsabilizar por authorities que ele mesmo possui**.

Extras de resultado no `Intent` retornado (um destes): `add_successful=true`, `already_added=true`, `validation_error=<string>`, ou `CancelReason.USER_CANCELLED=true` (usuário dispensou o diálogo de adição).

### 7.3 Contrato do content provider de conteúdo do pack (found, `StickerContentProviderFetcher`/`C179697lN`, `C175327dG`)

O WhatsApp lê um pack third-party consultando o *próprio provider do app chamador* na authority informada, condicionado a `readPermission == "com.whatsapp.sticker.READ"` nesse provider:

| URI | Colunas retornadas |
|-----|-------------------|
| `content://<authority>/metadata/<identifier>` | `sticker_pack_identifier`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_icon`, `android_play_store_link`, `ios_app_download_link`, `image_data_version`, `whatsapp_will_not_cache_stickers`, `animated_sticker_pack` |
| `content://<authority>/stickers/<identifier>` | `sticker_file_name`, `sticker_emoji`, `sticker_accessibility_text` |
| `content://<authority>/stickers_asset/<identifier>/<filename>` | stream aberta (ícone de bandeja ou arquivo de sticker individual) |

Validação encontrada no fetcher: `authority`/`identifier` rejeitam caracteres inválidos; `identifier` ≤ 128 caracteres; `sticker_pack_identifier` retornado deve corresponder ao identifier solicitado; nome de arquivo de `sticker_pack_icon` ≤ 128 caracteres; `android_play_store_link` deve conter `play.google.com`, `ios_app_download_link` deve conter `itunes.apple.com` ou `apps.apple.com`; `publisher`/`name` não vazios e ≤ 128 caracteres; id de `tray` não vazio; a contagem de stickers deve ficar dentro de `[flag 17124, flag 17327]` inclusive (limites de token de dicionário, valores numéricos não resolvidos nesta passagem); cada asset de sticker buscado é limitado a **~103424 bytes (101 KB)** para um pack estático ou **~512512 bytes (500,5 KB)** para um pack animado (`Math.min(animated ? 500 : 100, 1024) + 1) * 1024`; streams grandes demais ou ilegíveis são descartadas com o arquivo definido como nulo em vez de abortar o pack inteiro. Um caminho correspondente `app may have been deleted` / `third_party_sticker_app_deleted` trata o desaparecimento do pacote do provider em meio à busca.

Uma flag booleana separada (**13081**) controla se um pack já whitelisted ainda é buscado novamente no content provider ou servido a partir do cache, e a flag **22198** alterna entre um fluxo mais antigo de adição guiado por diálogo síncrono e o roteamento direto para a tela de preview do sticker pack; a flag **13711** seleciona entre duas variantes internas de instalação (`C175327dG.A00` vs `A01`) ao instalar via o caminho de atalho do content provider (seção 7.5) em vez da activity.

### 7.4 Contrato do intent `SEND_STICKER` (found, `SendStickerCommandActivity`)

Dados: uma URI `content://`, do próprio provider do app chamador, cuja authority deve resolver para o mesmo pacote chamador. O arquivo referenciado deve decodificar como exatamente **512×512** WebP e ser ≤ **500000 bytes**; o cliente o re-timbra pelo pipeline normal de sticker (hash, armazenamento, anexo) e anexa estes extras de `Intent` como metadados de pack `Sticker`, se presentes: `sticker_accessibility_text`, `sticker_pack_id`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_ios_store_link`, `sticker_pack_play_store_link` (os dois links de loja são validados com as mesmas verificações de domínio da seção 7.3).

### 7.5 Provider de verificação de whitelist (found, `WhitelistPackQueryContentProvider`)

`content://com.whatsapp.provider.sticker_whitelist_check/<match>?authority=<pkg-authority>&identifier=<pack-id>` — cursor de linha única, coluna única (`result`, `0`/`1`) respondendo "este pack já foi adicionado". A validação do chamador espelha a seção 7.2: o pacote chamador deve ser igual ao pacote que possui a `authority` consultada. Tipo MIME retornado por `getType()`: `vnd.android.cursor.item/vnd.com.whatsapp.provider.sticker_whitelist_check.is_whitelisted`.

### 7.6 Provider interno de comando de sticker (found, `StickerCommandProvider`, `com.whatsapp.provider.sticker_command`, `exported="true"`)

Não é parte do contrato third-party acima — este é o próprio provider do WhatsApp, consultado pelas próprias superfícies de UI/assistente do WhatsApp, com despacho por último segmento de caminho da URI:

| Caminho | Comportamento |
|------|-----------|
| `installPack?authority=&identifier=` | instala um pack pelo mesmo caminho de busca/validação `C175327dG` da seção 7.3, contornando a UI da activity |
| `removePack?authority=&identifier=` | desinstala um pack previamente adicionado |
| `generate?prompt=` | geração de sticker por AI (seção 8); o tamanho do prompt deve ser 3–200 caracteres após o trim |
| `availability` | retorna `{available, consent_required}` para geração de sticker por AI |
| `image/<token>` (via `openFile`) | transmite de volta um PNG/WebP de sticker gerado por token opaco, MIME `image/webp` |

---

## 8. Stickers gerados por AI (found, `AiStickerCommands`, `StickerCommandProvider`)

`isAiSticker` (campo 20) marca um `StickerMessage` como gerado por AI; a string de tipo é `genai_sticker` (seção 2.2). A geração em si é disparada localmente pela UI através do caminho do provider `generate` (7.6): os critérios de elegibilidade (`C174467bs.A00`) e consentimento (`A02`) são verificados antes de qualquer chamada de geração; os resultados voltam como uma lista de `token`s opacos resolvidos posteriormente via `image/<token>`. O backend de geração real (no dispositivo vs. servidor) é unknown a partir desse caminho de código — apenas a instrumentação de elegibilidade/consentimento/token do lado do cliente foi resolvida.

---

## 9. Busca de stickers (found, `StickerSearchManager`, `EmojiGroupMapper`, pacote de sugestão contextual)

Totalmente local, não é uma consulta ao servidor. `StickerSearchManager.A00` recebe uma consulta em texto livre, a resolve para um conjunto de caracteres de emoji via `EmojiGroupMapper`, os junta em uma string separada por espaços, e compara essa string com o campo `emojis` **armazenado localmente** de cada `StickerMessage`/pack `Sticker` (seção 2.3) mais candidatos recém-usados/destacados, dividindo os resultados em buckets de "correspondência exata de emoji" vs. "outros" e truncando para um limite de resultados de token de dicionário (flag **22573**). Uma flag `includeAvatarResults` separadamente controla se stickers de avatar participam, condicionada a sua própria verificação de elegibilidade. Isso confirma — e eleva de "pode conter… unknown" para found — que o campo string `emojis` do proto é a chave do índice de busca do lado do cliente, não apenas uma tag de exibição.

---

## 10. Criptografia de mídia (link, não repetido)

Toda referência de mídia que carrega sticker (`stickerMessage`, `stickerPackMessage`, seus thumbnails) passa pelo pipeline de mídia idêntico documentado em [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md): chave de mídia aleatória de 32 bytes, HKDF-80 (`WhatsApp Image Keys` para `sticker`, `WhatsApp Sticker Pack Keys` para `sticker-pack`, `WhatsApp Sticker Pack Thumbnail Keys` para o thumbnail do pack, o tratamento estilo `WhatsApp Image Thumbnail Keys` não é usado aqui — thumbnails de sticker e de pack têm suas próprias strings de info dedicadas), AES-CBC + HMAC-SHA256 truncado em 10 bytes, `fileSha256`/`fileEncSha256`, hosts emitidos por `media_conn`, e o formato de URL de upload `/mms/<type>/<hash>`. Nada específico de sticker muda isso; ver seções 2–9 daquele relatório para as tabelas completas de derivação, retry e código de erro.

---

## 11. Feature flags (ids como lidos nos pontos de chamada; nomes não resolvidos)

| Flag | Onde | Controla |
|------|-------|----------|
| **1900** | construtor de `C161826tK` | orçamento de tamanho de extração do ZIP do pack por entrada e agregado (KB) |
| **13081** | `AddThirdPartyStickerPackActivity` | re-busca vs. cache para um pack third-party já whitelisted |
| **13711** | `StickerCommandProvider`, `AddThirdPartyStickerPackActivity` | seleciona a variante do caminho de instalação (`C175327dG.A00` vs `A01`) |
| **17124** / **17327** | `StickerContentProviderFetcher` | contagem mín. / máx. de stickers aceita de um pack third-party |
| **22198** | `AddThirdPartyStickerPackActivity` | fluxo de adição assíncrono guiado por diálogo vs. roteamento direto para tela de preview |
| **22573** | `StickerSearchManager` | limite de resultado da busca local |

---

## 12. Baileys (`baron-baileys-v2`, código lido, nada testado)

| Aspecto | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Campos de `Message.StickerMessage` | mesmo conjunto de campos incluindo `audioMessage` (26, `oneof audio`) — o código-fonte do proto corresponde campo a campo ao layout decompilado da 2.26.41.6 | mesmo (seção 2.1) |
| Campos de `Message.StickerPackMessage` | mesmo conjunto de campos (1–22) | mesmo (seção 5.1) |
| Enviando um sticker | `prepareWAMessageMedia({ sticker })` constrói `stickerMessage` pelo caminho genérico de preparação de mídia (`MmsType` `sticker`, Image HKDF info); a opção `stickerAudio` anexa um `audioMessage` preparado em `m.stickerMessage.audioMessage` | mesmo pipeline de mídia conforme [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) seção 17 |
| Enviando um pack | a entrada `stickerPackMessage`/`stickerPack` é passada por `StickerPackMessage.fromObject` sem validação extra | o cliente também valida via o extrator de ZIP e as restrições de BD (seções 5, 6) antes de aceitar um pack que ele mesmo constrói |
| Decodificação | `decode-wa-message.js` mapeia `isAvatar`→`avatar_sticker`, `isAiSticker`/`isGenAI`→`genai_sticker`; `messages-send.js` mapeia `isLottie`→`1p_sticker` antes de `isAvatar`/`sticker` simples ao derivar a string de tipo de saída | mesmas três strings de tipo de mensagem encontradas no despacho de analytics do Android (`avatar_sticker`, `genai_sticker`, mais `1p_sticker`/`user_created_sticker`); ordem de precedência exata do Android não confirmada (seção 2.2) |
| Intents/providers de pack third-party | não implementado — o Baileys não tem superfície de `Intent`/`ContentProvider` do Android | superfície completa, seção 7 |
| Wrappers `lottieStickerMessage` / `audioStickerMessage` | presentes apenas como um campo `FutureProofMessage` puro no proto; nenhum caminho de encoder/decoder dedicado encontrado | mesmo envelope puro, também sem tratamento específico de campo encontrado (seção 3) |

---

## 13. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|-----|
| `ENABLE_STICKER_PACK` retorna `validation_error` "cannot find the provider for authority" | a string `authority` do app third-party não resolve para nenhum provider instalado | o app que publica o sticker pack deve declarar e exportar seu provider sob exatamente essa authority |
| `ENABLE_STICKER_PACK` retorna "does not own authority" | o pacote chamador difere do pacote do provider resolvido | um app só pode se responsabilizar por authorities dentro do próprio pacote |
| Adição de pack falha silenciosamente com "sticker count should be between X and Y" | a consulta `stickers` do pack retornou uma contagem de linhas fora de `[flag 17124, flag 17327]` | mantenha o cursor `/stickers/<id>` third-party dentro dos limites configurados pelo servidor |
| `SafeZipEntrySaver: File being unzipped is too big` / "Too many files to unzip" | o ZIP do pack excede o orçamento de bytes por entrada/agregado ou o limite de 65 entradas | reduza o pack ou divida os stickers entre vários packs |
| `tray image name invalid` / erro de tamanho de nome | `sticker_pack_icon` third-party contém caracteres inválidos ou excede 128 caracteres | sanitize e reduza o nome do arquivo da bandeja |
| `StickerPackZipEntrySaver/file in zip is not valid` | o tipo de conteúdo detectado de uma entrada extraída não corresponde à sua extensão/MIME declarada | envie entradas cujos bytes correspondam de fato a `png`/`webp`/`was` |
| `the sticker is not a 512px WebP` (`SEND_STICKER`) | a imagem do intent de sticker único não é exatamente 512×512 | redimensione antes de enviar o intent |

---

## 14. Distinções importantes

| Não confundir | Fato |
|----------------|------|
| `StickerMessage.audioMessage` (campo 26) vs. `Message.audioStickerMessage` (campo 134) | o primeiro é um `AudioMessage` embutido confirmado dentro de um envio de sticker; o segundo é um campo wrapper de nível superior separado, ainda opaco, novo nesta build |
| `isLottie` (flag por sticker) vs. `Message.lottieStickerMessage` (campo 74 wrapper) | a flag está ligada a um formato de arquivo concreto found (ZIP `.was` com `animation/animation.json`); o payload aninhado do campo wrapper ainda não foi resolvido — não há evidência de que sejam o mesmo mecanismo |
| `stickerSyncRmrMessage` (mensagem de wire, ausente) vs. `RecentStickerDBStorage` (tabela local indexada por `filehash`) | o primeiro não existe mais no wire nesta build; o segundo é escrituração local não relacionada que coincidentemente também indexa por hash de arquivo |
| Contrato de pack third-party (seções 7.2–7.5, provider do app externo) vs. `StickerCommandProvider` (seção 7.6, próprio provider do WhatsApp) | ambos podem "instalar um pack por authority+identifier", mas o primeiro é o WhatsApp *lendo o provider de outro app*, o segundo é o atalho interno do WhatsApp em torno de sua própria UI de activity |
| Geração de sticker por AI (`isAiSticker`, fluxo local de GenAI) vs. apps third-party de AI/sticker | o primeiro é o próprio recurso in-app do WhatsApp atrás do `StickerCommandProvider`; não tem relação com o contrato de content provider third-party |

---

## 15. Fluxo: adicionando um sticker pack third-party

```
[Third-party app]  exports ContentProvider at authority X, readPermission=com.whatsapp.sticker.READ
     │  startActivityForResult(ACTION_ENABLE_STICKER_PACK, extras: sticker_pack_id, sticker_pack_authority=X, sticker_pack_name)
     ▼
[AddThirdPartyStickerPackActivity]  getCallingActivity() != null?
     │  resolveContentProvider(X) exists?  calling package == provider's package?
     ▼  (all pass)
[StickerContentProviderFetcher]  query content://X/metadata/<id>
     │  validate identifier echo, name/publisher length, tray icon name, store links
     ▼
[StickerContentProviderFetcher]  query content://X/stickers/<id>  (sticker_file_name, sticker_emoji, sticker_accessibility_text)
     │  validate count in [flag 17124, flag 17327], accessibility text ≤ 125/250 chars
     ▼
[StickerContentProviderFetcher]  openInputStream content://X/stickers_asset/<id>/<file>  per sticker + tray icon
     │  cap ~101 KB (static) / ~500.5 KB (animated) per asset
     ▼
[Client]  store pack + stickers, mark whitelisted (ThirdPartyWhitelistedPacksStore)
     │
     ▼
[AddThirdPartyStickerPackActivity]  result Intent: add_successful=true | already_added=true | validation_error=<reason>
     │
     ▼
[Third-party app]  onActivityResult()
```

---

## 16. Pontos não resolvidos

| Item | Status |
|------|--------|
| Payload aninhado de `lottieStickerMessage` (74) e `audioStickerMessage` (134) | o campo existe, wrapper genérico `FutureProofMessage`, conteúdo não resolvido |
| Precedência exata do Android para as strings de tipo `sticker` vs. `1p_sticker` vs. `user_created_sticker` | apenas o mapeamento em bytecode de analytics foi encontrado, não a função seletora |
| Campo `premium` (24) em `StickerMessage`/`Sticker` | nenhum consumidor localizado |
| Valores numéricos atrás das flags de token de dicionário 1900, 17124, 17327, 22573 | ids de token encontrados, valores em uso não resolvidos estaticamente |
| Activity de destino do deep link `whatsapp://stickerpack` | host declarado no intent-filter de deep link genérico do manifest; qual tela interna o consome não foi isolado |
| Backend de geração de sticker por AI (no dispositivo vs. servidor) | apenas a instrumentação de elegibilidade/consentimento/token do cliente resolvida |
| Se o servidor impõe seus próprios limites de tamanho/contagem de pack além dos do cliente | lado do servidor, unknown |
| O destino de `stickerSyncRmrMessage` (renomeado, movido, ou removido) | confirmado ausente do proto de wire da 2.26.36.1 até a 2.26.41.6; remoção não confirmada |
| Tráfego | nada capturado; nenhum teste dinâmico |
