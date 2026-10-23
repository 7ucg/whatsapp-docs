<!-- src-sha1: a948bbebefb4aeb1c2d1bf74123b9dc6e606b08d -->
# WhatsApp Noise Transport — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** transporte de chat no Android (chatd): endpoints e sequência de conexão, roteamento de edge, enquadramento TCP, handshake Noise XX / IK / PQ, verificações da cadeia de certificados, ClientPayload (UserAgent, DevicePairingData, connect type / reason), cifra de transporte e contadores, codificação binária de nós, resultado de login e códigos de falha, keepalive, backoff de reconexão, stream:error, feature flags, transportes relacionados (Tigon HTTP, DistribGW, canal Tigon Noise, MQTT), comparação com o Baileys

---

## 1. O que é (tecnicamente)

chatd é a única conexão de longa duração que transporta toda stanza (mensagens, recibos, IQ, presença, notificações). No Android é um socket TCP simples (não WebSocket) que executa um handshake Noise e depois frames AES-GCM com prefixo de comprimento, cada um contendo um nó codificado em binário. Todas as afirmações vêm da análise estática do APK decompilado; nada foi capturado na rede. Tiers: **found** = lido no código, **inferred** = deduzido, **unknown** = não resolvido. Os nomes ofuscados mudam a cada build e foram re-resolvidos na 2.26.41.6.

| Camada | Nome na 2.26.41.6 | Função |
|--------|-------------------|--------|
| Thread de conexão | `HandlerThreadC12340b0` (tag de log `ConnectionThread`) | conectar, handshake, login, loop de leitura, desconectar |
| Sequência de conexão / DNS | `C37151de` (estados), `C37031dS` (`A0G` avança, `A0D` fábrica de sockets), `C36881dC`, `AbstractC47101wK` (tabela fixa de host para IP), `C36821d6` (IPs de fallback) | qual host / porta / proxy vem a seguir |
| Driver do handshake | `C38791hg` (logs `NoiseSocket/*`) | bytes de intro, ClientHello, ServerHello, verificações de certificado, ClientFinish |
| Estado Noise | `C38921hv` (+ `C38941hx` hash, `C38981i2` AES-GCM, `AbstractC38961i0` HKDF), `C40331kf` (chaves de transporte + contadores) | Java puro |
| E/S de frames, codec de nós | `C38891hs` / `C38901ht`; `C40411kn` (encoder), `C24610wf` (decoder), `AbstractC40911lb` (dicionário) | enquadramento, XML binário |
| Protos | `C39211ii`, `C39161id`, `C39231ik`, `C39241il` (handshake); `C24843Amz`, `C24842Amy`, `C24841Amx`, `C25757B9r`, `BC0` (certificados); `C38001fP`, `C38051fp`, `C38661hS` (payload) | mensagens de rede |
| Confiança, PQ | `AbstractC44011qk` (raiz fixada); `C38811hi`, `AbstractC38821hj`, `AbstractC38831hk`, `C38761hd` (config PQ, chaves estáticas do servidor) | identidade do servidor, híbrido ML-KEM-512 |
| Construtor do payload | contribuidores em `AbstractC43901qZ` coletados por `C37991fK` | ClientPayload |
| Keepalive, timers, reconexão | `C14U` (`ClientPingManager`), `C9EN` (IQ de ping), `HandlerC21850s9`, `C11380Yq` (`MessageHandler`), `C0X9` (backoff) | ping, timeouts, retentativa |
| Controle de entrada | `C40581l4` (`<ib>`), `C40601l6` / `C37961fH.A1B` (`stream:error`) | avisos do servidor |

Pontos que determinam o resto do relatório:

- A máquina de estados Noise, o HKDF, o AES-GCM e o codec de frames são **Java**. Somente Curve25519 (`org.whispersystems.curve25519`, `OpportunisticCurve25519Provider`, nativo com fallback em Java) e as chamadas ML-KEM (`KEMKeyPair.generateNative`, `KEMSecretKey.decapsulateNative`) são nativos. Não há implementação nativa do chatd para fazer engenharia reversa (found).
- O cabeçalho de intro é a constante `WA 06 03` neste build (seção 3.1). O int de versão do protocolo passado a `C38791hg` é fixo em 6 em seu único ponto de chamada, então o ramo de certificado plano da versão 5 é inalcançável na prática (found; alcançabilidade inferred a partir do único ponto de chamada com constante).
- `devicePairingData` é enviado apenas por uma conexão sem JID de usuário, o que `ConnectionThread` permite somente no registro de companion. Não é um artefato de registro do telefone primário neste build (seção 6.4).
- As stanzas de saída no caminho principal de envio são comprimidas com DEFLATE (flags `3`), não apenas as de entrada (seção 8.1).

---

## 2. Endpoints e sequência de conexão

### 2.1 Hosts e portas (found)

| Host | Onde | Observações |
|------|------|-------------|
| `g.whatsapp.net` | `C37151de` passos 5, 9; `C36881dC.A01` (IPs fixos) | host de chat primário |
| `g-fallback.whatsapp.net` | passos 13, 14 | segundo host |
| `e1` ... `e16.whatsapp.net` | `C37151de.A0F` (16 entradas), passos 7 e 11 | `ConnectionSequence/getEdgeHost`; escolha aleatória, ou o host armazenado no histórico |
| tabela de IPs fixos | `AbstractC47101wK.A00`, passos 6 e 10 | mapeia host para lista de IPs, cobre os hosts `eN` e `g.whatsapp.net` |
| lista `<ib><fbip>` | `C40581l4` para `C36821d6.A02` | IPs separados por vírgula, persistidos pelo gerenciador de fallback (entrada dos passos 2 / 8, inferred) |
| proxy do usuário | passo 12 | socket simples ou TLS para o proxy `host:chatPort`, sem handshake de proxy (veja WA_CENSORSHIP_CIRCUMVENTION.md) |
| túnel SOCKS (serviço de proxy) | `C48201yM` (`ConnectionSocketTunnel`), não o passo 12 | `java.net.Proxy.Type.SOCKS`, timeout de conexão 30000 ms |

Portas: 443 e 5222 (escolha aleatória por tentativa, `C37151de.A00`; o construtor também sorteia uma moeda que ordena as portas dos passos 3 e 4) e 80 para os passos `:80`. A porta da última conexão bem-sucedida é reutilizada quando a flag **33512** está ativa (found).

### 2.2 Estados da sequência (found, `C37151de.A02`, avanço em `C37031dS.A0G`)

| Passo | Destino |
|-------|---------|
| 0 | início, escolhe o primeiro passo aplicável |
| 1 | `InetSocketAddress` de debug / override (terminal) |
| 2 | entradas de endpoint fornecidas pelo servidor com o bit `A04` ligado (lista `A0A`), uma a uma; cada entrada traz seu próprio bit TLS `A05` |
| 3, 4 | string de host configurada `A07` nas duas portas (443 / 5222 em ordem aleatória) |
| 5 | `g.whatsapp.net` na 443 (flag **20801**) ou 443 / 5222 aleatória |
| 8 | entradas fornecidas pelo servidor sem o bit `A04` (lista `A09`); a ordem dos ramos decompilados não é clara |
| 9 | `g.whatsapp.net:80` |
| 15 | HISTORY: repete o passo / host / porta armazenados pelo último sucesso (inserido após o 9 quando o passo de histórico é válido e a flag **22916** está desligada) |
| 13, 14 | `g-fallback.whatsapp.net` na 443 / 5222, depois `:80` |
| 6, 10 | IP fixo de `g.whatsapp.net`, depois `:80` |
| 7, 11 | host de edge aleatório `eN.whatsapp.net`, depois `:80` |
| 12 | proxy do usuário (terminal) |
| 16 | esgotado |

Ordem após o passo 9 (found): 9, [15], 13, 14, 6, 10, 7, 11, 16. O último sucesso é armazenado nas preferências `last_successful_connection_step`, `_host`, `_port` (found, `C37031dS.A00`). Os passos 2 a 4 registram `Skipping sequence ... due to active proxy` enquanto uma config de serviço SOCKS está ativa e a flag **23630** está desligada (semântica de skip inferred).

### 2.3 Socket (found, `C37031dS.A0D`)

| Aspecto | Valor |
|---------|-------|
| Socket | TCP simples; Happy Eyeballs quando existem endereços IPv4 e IPv6 (`ConnectionSocketFactory/try_connect/using-happyEyeball`) |
| Wrapper TLS | o bit de config `A07` seleciona uma `SSLSocketFactory`; definido por entrada fornecida pelo servidor (`A05`), para o passo 1 na porta 443 e para hosts de edge (passo 7) na porta 443. O passo 5 (`g.whatsapp.net`) é criado com o bit desligado |
| Timeout do socket | 30000 ms definido via `CeF(30000)` (semântica inferred: timeout de leitura) |
| TCP keepalive | `configureTcpKeepalive`: quando a flag **7831** está ativa e o socket suporta, o keepalive é habilitado e três ints das flags **7832** (padrão 2), **7833** (padrão 10), **7834** (padrão 10) são aplicados (ocioso / intervalo / contagem por inferência) |
| Buffer de saída | quando a flag **33751** está ativa, o writer é envolvido em um `BufferedOutputStream` para que os bytes de intro e o ClientHello saiam em uma única escrita (found) |

Se os endpoints com wrapper TLS carregam os mesmos bytes Noise dentro do TLS é inferred a partir do caminho de código (`C38791hg` recebe apenas streams); existe em uma lib nativa uma métrica chamada `chatd_non_secure_tls_wrapper_resumption`.

### 2.4 Resolução de DNS (found)

`DNSResolutionMethod` é reportado em `ClientPayload.dnsSource` (seção 6.5): `SYSTEM`, `GOOGLE`, `HARDCODED`, `OVERRIDE`, `FALLBACK`, `MNS`, `MNS_SECONDARY`, `SOCKS_PROXY`. A flag **13545** (string; valores `secondary`, `hardcoded`, `none` reconhecidos por `C37151de.A01`) ajusta a cadeia de resolvers. Respostas em cache de consultas anteriores são usadas até expirarem antes de uma nova consulta (`C36881dC.A03`).

---

## 3. Enquadramento

### 3.1 Bytes antes do primeiro frame (found, `C38791hg`)

```
[ 'E' 'D' 00 01 | len24 | routing_info ]     only when routing_info is non-empty
[ 'W' 'A' 06 03 ]                             always
[ len24 | HandshakeMessage{clientHello} ]     first frame
```

- Cabeçalho de edge: magic `45 44 00 01` (`C38791hg.A0B`), comprimento do blob em 3 bytes big-endian, depois os bytes de `routing_info` (preferência, base64 sem padding nem quebra de linha; armazenado por `C38801hh.A00`, máx. 256 bytes: "The routing info should be smaller than 256 bytes."). Bruto no socket, fora do transcript Noise.
- Intro: `57 41 06 03` = "WA", protocolo 6, dicionário 3 (`C38791hg.A04`); também é o prologue Noise (4.2). O ramo else retorna `57 41 05 03`, mas o construtor fixa a versão em 6.

### 3.2 Layout do frame (found)

Todo frame é um comprimento de 3 bytes big-endian (`AbstractC38721hZ.A04` / `A00`; escritas devem ser menores que 2^24, senão `data too large to write`) seguido do corpo: protobuf do handshake durante o handshake, texto cifrado AES-GCM depois.

Leitor (`C38891hs`): exatamente 3 bytes de comprimento, depois o corpo. Ao ler o ServerHello, três bytes de comprimento iguais ao ASCII `GOA` (`47 4F 41`, `C38891hs.A01`) lançam `X.1sn` (log `socket/goaway`); o caminho de leitura pós-handshake (`C24610wf.Be0`) não tem essa verificação. Frames decifrados vazios são ignorados; um frame decifrado de 1 byte lança `header only frame received`. Uma stanza acima do limite opcional de tamanho (`InterfaceC40421ko.AqJ`) lança `C31990DyW` ao codificar.

### 3.3 Mensagens do handshake (found, números de campo das classes protobuf)

| Mensagem (classe) | Campos (número em negrito) |
|-------------------|----------------------------|
| `HandshakeMessage` (`C39211ii`) | clientHello **2**, serverHello **3**, clientFinish **4** |
| `ClientHello` (`C39161id`) | ephemeral **1**, static **2**, payload **3**, useExtended **4**, extendedCiphertext **5**, paddedBytes **6**, sendServerHelloPaddedBytes **7**, simulateXxkemFs **8**, pqMode **9**, extendedEphemeral **10** |
| `ServerHello` (`C39231ik`) | ephemeral **1**, static **2**, payload **3**, extendedStatic **4**, paddingBytes **5**, extendedCiphertext **6** |
| `ClientFinish` (`C39241il`) | static **1**, payload **2**, extendedCiphertext **3**, paddedBytes **4**, simulateXxkemFs **5** |

Setters vistos no driver: o ClientHello XX completo define `ephemeral` (+ `pqMode` nas variantes PQ); o ClientHello de resume define `ephemeral`, `static`, `payload`, `extendedCiphertext`, `extendedEphemeral`, `pqMode`; o ClientFinish define `static`, `payload`, `extendedCiphertext`. Os campos de padding e simulate estão definidos, mas nenhum setter foi encontrado no driver (uso unknown).

---

## 4. Handshake Noise

### 4.1 Nomes de padrão (found, campos estáticos de `C38921hv`)

| Constante | Nome | Usado quando |
|-----------|------|--------------|
| `A07` | `Noise_XX_25519_AESGCM_SHA256` (preenchido com NUL até 32 bytes) | handshake completo, PQ none |
| `A0H` | `Noise_IK_25519_AESGCM_SHA256` (preenchido até 32) | resume com static do servidor em cache, PQ none |
| `A06` | `Noise_XXfallback_25519_AESGCM_SHA256` | IK rejeitado pelo servidor (4.4) |
| `A0E`, `A0C`, `A08` | `Noise_XXkem_`, `Noise_XXkem-FS_`, `Noise_XXkemEph_` + `25519_MLKEM512_AESGCM_SHA256` | completo, PQ ligado |
| `A0F`, `A0D`, `A0G` | `Noise_IKkem+`, `Noise_IKkem-FS+`, `Noise_IKkem2+` + `X25519+MLKEM512+AESGCM256+SHA256` | resume, PQ ligado |
| `A09`, `A0B`, `A0A` | `Noise_XXkemfallback_`, `Noise_XXkem-FSfallback_`, `Noise_XXkemEphfallback_` + `25519_MLKEM512_AESGCM_SHA256` | fallbacks PQ |

Um nome com mais de 32 bytes é hasheado com SHA-256; caso contrário, o valor preenchido de 32 bytes é o hash inicial (found, construtor de `C38921hv`).

Configuração PQ (`NoisePQConfig`): modo `NONE` / `ENABLE` / `ENFORCE` (flag **20161**, int: 1 enable, 2 a 4 enforce, senão none); variante `IKKEM`, `IKKEM_FS`, `XXKEM_EPH_IKKEM2`, `XXKEM_EPH_ONLY` (flag **34536**, string, padrão `IKKEM`). Handshake completo: modo PQ `NONE` usa `A07`; caso contrário a variante `IKKEM_FS` seleciona `A0C`, `XXKEM_EPH_ONLY` e `XXKEM_EPH_IKKEM2` selecionam `A08`, `IKKEM` seleciona `A0E` (found no construtor de `C38791hg`). Os nomes `IKkem*` se associam ao caminho de resume; o mapeamento exato das variantes não foi rastreado.

### 4.2 Estado simétrico (found, `C38921hv`)

```
h  = name (padded, or SHA256(name) if > 32 bytes)         // C38941hx.A00 = name
ck = h                                                    // A02
h  = SHA256(h || prologue)                                // prologue = WA 06 03
mixHash(d):  h = SHA256(h || d)
mixKey(dh):  okm = HKDF-SHA256(salt = ck, ikm = dh, info = none, 64)
             ck  = okm[0:32] ; k = AES-256-GCM key okm[32:64] ; n = 0
encrypt(p):  c = AES-GCM(k, iv = 00000000 || n_be64, aad = h, p) ; n++ ; mixHash(c)
decrypt(c):  p = AES-GCM(k, iv = 00000000 || n_be64, aad = h, c) ; n++ ; mixHash(c)
             (no key yet: encrypt / decrypt pass through and only mixHash)
split():     okm = HKDF-SHA256(salt = ck, ikm = empty, info = none, 64)
             sendKey = okm[0:32] ; recvKey = okm[32:64]
```

O HKDF é escrito à mão (`AbstractC38961i0`): extract = `HMAC(key = salt, data = ikm)`, expand com contador de um byte. IV: 12 bytes, os 4 primeiros zero, os 8 últimos o contador big-endian (`AbstractC38721hZ.A02`). Tag de 128 bits (GCM estilo BouncyCastle `C39061iT`). O DH é Curve25519 `calculateAgreement` via `C38851hm.A00("best")`.

### 4.3 Sequência XX completa (found)

| # | Direção | Conteúdo | Operações de estado |
|---|---------|----------|---------------------|
| 1 | C para S | `ClientHello{ephemeral}` (+ `pqMode` nas variantes PQ) | `mixHash(e_c)` |
| 2 | S para C | `ServerHello{ephemeral, static, payload}` | `mixHash(e_s)`; `mixKey(DH(e_c, e_s))`; `s_s = decrypt(static)`; `mixKey(DH(e_c, s_s))`; `cert = decrypt(payload)` |
| 3 | local | verificações de certificado (seção 5) | a chave no cert deve ser igual a `s_s` |
| 4 | C para S | `ClientFinish{static, payload}` | `static = encrypt(s_c)`; `mixKey(DH(s_c, e_s))`; `payload = encrypt(ClientPayload)` |
| 5 | local | split | `sendKey`, `recvKey`, ambos os contadores 0 |

A ordem em `C38791hg.A03` (smali) corresponde ao transcript XX padrão. O static do cliente `s_c` e o ephemeral vêm de pares de chaves `C38711hY`; o static é fornecido por `C38771he.A01` (chave Noise persistente do cliente, "authKey" nos logs de desconexão). Que ele seja igual à chave enviada no registro é inferred.

### 4.4 Resume (IK) e fallback (estrutura found, detalhe dos passos inferred)

Quando existem chaves estáticas do servidor em cache (`C38771he.A00` não nulo, `C38761hd`), o driver registra `NoiseSocket/handshakeStart mode=... rs=...` e executa `handshakeResume`: a chave pública estática do servidor em cache entra no hash do estado (`C38921hv.A06`), e o ClientHello carrega o ephemeral, o static do cliente cifrado e o `ClientPayload` cifrado em uma única mensagem (seção 3.3). Se o servidor responde com uma chave estática, o log é `handshakeResume server hello has static key, falling back` e `C38791hg` lança `X.1t8` carregando o ServerHello, o que seleciona os nomes `Noise_XXfallback_*`. O transcript exato do fallback é inferred a partir do modificador de fallback padrão do Noise. As chaves estáticas do servidor são persistidas após um login bem-sucedido quando mudam (`A1m`: chave clássica via `Ce3`, chave PQ via `Ce2`).

### 4.5 Material pós-quântico (found como presente; detalhe de rede parcialmente unknown)

- KEM: ML-KEM-512 (string de algoritmo `MLKEM512`, `C38791hg.A0C`). TLV da chave pública PQ do servidor: tipo `0x02`, comprimento 800; tipo de cabeçalho TLV `0x01` carregando o nome do algoritmo; TLV de ciphertext FS tipo `0x04`, comprimento 768 (das strings de erro `Expected TLV PK type 0x02`, `length 800`, `Expected TLV header type 0x01`, `Expected FS ciphertext length 768`).
- Encapsulamento (`C38921hv.A07`): `KEMPublicKey.A00()` gera ciphertext + segredo compartilhado; o ciphertext passa por `mixHash`, o segredo compartilhado por `mixKey`. Decapsulamento: `KEMSecretKey.decapsulateNative`.
- Entrega: `<success static_pq_key="base64">` é lido somente quando o modo PQ não é `NONE` e a variante é `IKKEM_FS` (`A18`); sem ele o log é `handshake missing serverStaticPQ forcing full handshake` (`C38791hg.A01`).

A largura do campo de comprimento do TLV e o posicionamento exato dentro de `ServerHello.payload` não foram decodificados. Os nativos ML-KEM vêm das classes KEM do Signal; a biblioteca que os implementa não foi identificada.

---

## 5. Verificações do certificado do servidor (found, `C38791hg.A03`)

A versão de protocolo 6 (o único valor usado) interpreta `ServerHello.payload` como um `CertChain`:

`CertChain` (`C24843Amz`): leaf **1**, intermediate **2**. Cada um é um `NoiseCertificate` (`C24842Amy`): details **1** (bytes), signature **2** (bytes). `details` é interpretado como `Details` da cadeia (`C24841Amx`): serial **1**, issuerSerial **2**, key **3**, notBefore **4**, notAfter **5**.

Verificações (prefixo de log `wa6:`; ordem de avaliação não totalmente recuperada, o método decompilado está incompleto):

1. Ambos os `details` são interpretados como `Details` da cadeia.
2. `intermediate.issuerSerial == 0` e `leaf.issuerSerial == intermediate.serial`.
3. `leaf.key` é igual ao static do servidor do handshake `s_s` ("noise certificate key does not match proposed server static key").
4. A assinatura do intermediate é verificada sobre `intermediate.details` com a chave raiz fixada para o emissor `WhatsAppLongTerm1` (`AbstractC44011qk.A00`).
5. A assinatura do leaf é verificada sobre `leaf.details` com a `key` do intermediate.

`notBefore` / `notAfter` não são lidos no caminho da cadeia. Uma falha lança `X.1so` (log `socket/invalid-certificate-exception`).

Raiz fixada (chave pública, found, `AbstractC44011qk.A01`): `142375574d0a587166aae71ebe516437c4a28b73e3695c6ce1f7f9545da8ee6b`.

Forma plana (código morto na versão constante 6): `NoiseCertificate{details = 1, signature = 2}` (`C25757B9r`), `Details` plano `{serial = 1, issuer = 2, expires = 3, subject = 4, key = 5}` (`BC0`). O código verifica a assinatura única contra a chave fixada pelo nome do emissor, compara `key` com `s_s` e rejeita quando `expires` (segundos) está abaixo do horário atual (log `noise certificate expired`).

---

## 6. ClientPayload

### 6.1 Campos (found, `C38001fP`; números do descriptor)

| Campo | Número | Tipo | Definido por na 2.26.41.6 |
|-------|--------|------|---------------------------|
| username | **1** | int64 | parte numérica de usuário do JID de login (usuário LID em login LID) |
| passive | **3** | bool | flag de modo de conexão da session info (7.2) |
| userAgent | **5** | `UserAgent` | 6.2 |
| webInfo | **6** | `WebInfo` | não definido pelos contribuidores lidos |
| pushName | **7** | string | push name da conta, se não vazio |
| sessionId | **9** | int32 | id de sessão por conexão (`C37121db`) |
| shortConnect | **10** | bool | `C11750a1.A03()` |
| connectType / connectReason | **12** / **13** | enum | 6.5 |
| shards | **14** | repeated int32 | não definido |
| dnsSource | **15** | message | `dnsMethod` **15**, `appCached` **16** |
| connectAttemptCount | **16** | int32 | tentativas até agora |
| device | **18** | int32 | modo companion: preferência `registration_device_id` |
| devicePairingData | **19** | message | 6.3 / 6.4 |
| product | **20** | enum | `WHATSAPP_LID` em login LID, senão padrão `WHATSAPP` |
| oc / lc | **23** / **24** | bool / int32 | `oc`: resultado da verificação de build ou assinatura (`AbstractC38241gg`, nome não expandido); `lc`: preferência `connection_lc` |
| pull | **33** | bool | **nunca definido neste build** (nenhum writer encontrado) |
| yearClass / memClass | **36** / **37** | int32 | heurísticas de classe do dispositivo (`C38261gi`, `C38271gj`) |
| trafficAnonymization | **40** | enum | `STANDARD` quando `C17830kT.A0L()`, senão `OFF` |
| lidDbMigrated | **41** | bool | somente com JID de usuário e não companion |
| connectionSequenceInfo | **43** | int32 | contador 0-31 derivado do passo da sequência |
| paaLink | **44** | bool | `C0NZ.A02()` |
| preacksCount / processingQueueSize | **45** / **46** | int32 | estado da fila (flags **20485** / **22413**) |
| pairedPeripherals | **47** | repeated string | `smart_glasses`, `garmin` |
| messageSts | **49** | int64 | timestamp da última mensagem, se conhecido |

Definidos, mas não definidos aqui: fbCat **21**, fbUserAgent **22**, iosAppExtension **30**, fbAppId **31**, fbDeviceId **32**, paddingBytes **34**, interopData **38** (`accountId` **1**, `token` **2**, `enableReadReceipts` **3**), accountType **42**, testIsolationId **48**.

### 6.2 UserAgent (found, `C38051fp`)

| Campo | Número | Valor neste build |
|-------|--------|-------------------|
| platform | **1** | `ANDROID` (0), constante |
| appVersion | **2** | `{primary 1, secondary 2, tertiary 3, quaternary 4}` extraído de `2.26.41.6` |
| mcc / mnc | **3** / **4** | `getNetworkOperator()`, padrão `000` |
| osVersion / manufacturer / device / osBuildNumber | **5** / **6** / **7** / **8** | strings do sistema |
| phoneId | **9** | id em nível de dispositivo (`C38141gV`) |
| releaseChannel | **10** | `BETA` (1) neste build beta; `RELEASE 0, BETA 1, ALPHA 2, DEBUG 3` |
| localeLanguageIso6391 / localeCountryIso31661Alpha2 | **11** / **12** | omitidos para `zz` / `ZZ` |
| deviceBoard / deviceExpId | **13** / **14** | string da board se não vazia; id de experimento |
| deviceType | **15** | `PHONE`, `TABLET`, `DESKTOP`, `VR` a partir da classe do dispositivo |
| deviceModelType | **16** | |
| distributionChannel | **17** | não definido |

`UserAgent.Platform` (`EnumC38071fr`, 0-40): 0 ANDROID, 1 IOS, 10 SMB_ANDROID, 12 SMB_IOS, 13 WINDOWS, 14 WEB, 24 MACOS, 29 WEAROS, 33 IPAD, 35 SMART_GLASSES, 39 WORK_ANDROID, 40 WORK_IOS (outros omitidos).

### 6.3 DevicePairingRegistrationData (found, `C38661hS`)

Campos de `DevicePairingRegistrationData`: eRegid **1** (id de registro de 4 bytes), eKeytype **2** (`05`), eIdent **3** (chave pública de identidade), eSkeyId **4**, eSkeyVal **5**, eSkeySig **6** (id do signed prekey, pública, assinatura), buildHash **7**, deviceProps **8** (`DeviceProps` serializado).

`buildHash`: o código calcula `Base64.decode(hexMD5("2.26.41.6"), 0)` (`C00L.A04` retorna o MD5 hexadecimal minúsculo de 32 caracteres, que depois é passado ao decoder base64), resultando em 24 bytes, não nos 16 bytes do digest (found conforme lido).

`DeviceProps` (`C43105IrG`): os **1** (string do SO), version **2** (`AppVersion`), platformType **3**, requireFullSync **4** (= true), historySyncConfig **5**. O bloco de history-sync é montado por uma classe que registra logs como `CompanionRegInfoProvider`; seus campos (dias / limites de tamanho do full sync, recent sync, thumbnail sync, flags de suporte como call logs, bot history, group history) são controlados pelas flags **15284**, **15283**, **21217**, **20658**, **18953**, **26445**, **26614**.

### 6.4 Qual variante é enviada (found)

- Login, primário (JID de usuário conhecido): username, passive, userAgent, pushName, sessionId, shortConnect, connectType, connectReason, dnsSource, connectAttemptCount, connectionSequenceInfo, lc, oc, yearClass, memClass, trafficAnonymization, lidDbMigrated, messageSts, contadores de fila, paaLink, pairedPeripherals; `product = WHATSAPP_LID` em logins LID.
- Login, companion: o mesmo mais `device = registration_device_id`.
- Registro de companion (JID de usuário nulo): sem username; `devicePairingData` (key bundle + `DeviceProps`) e `device`.

`ConnectionThread/connect/ignored/jid null and not in companion reg` mostra que um JID nulo é recusado fora do registro de companion. O telefone primário se registra via HTTPS `/v2/*` (veja o relatório de account-security); nenhum uso de `devicePairingData` no registro primário foi encontrado.

### 6.5 Enums usados (found)

| Enum | Valores |
|------|---------|
| `ConnectReason` (`EnumC38391gv`) | 0 PUSH, 1 USER_ACTIVATED, 2 SCHEDULED, 3 ERROR_RECONNECT, 4 NETWORK_SWITCH, 5 PING_RECONNECT, 6 UNKNOWN |
| `ConnectType` (`EnumC38311gn`) | 0 CELLULAR_UNKNOWN, 1 WIFI_UNKNOWN, 100 EDGE, 101 IDEN, 112 HSPAP; os demais nomes celulares (UMTS, EVDO, GPRS, HSDPA, HSUPA, HSPA, CDMA, ...) recebem seus números de constantes indiretas que não foram resolvidas |
| `Product` (`EnumC38561hI`) | 0 WHATSAPP, 1 MESSENGER, 2 INTEROP, 3 INTEROP_MSGR, 4 WHATSAPP_LID |
| `DNSResolutionMethod` (`EnumC38321go`) | 0 SYSTEM, 1 GOOGLE, 2 HARDCODED, 3 OVERRIDE, 4 FALLBACK, 5 MNS, 6 MNS_SECONDARY, 7 SOCKS_PROXY |

Connect reason conforme escrito neste build: padrão `UNKNOWN`; quando o timestamp da session info está dentro de 10 s, o estado 1 resulta em `USER_ACTIVATED`, o estado 2 resulta em `PUSH`. Os demais valores estão definidos, mas este contribuidor não os seleciona.

---

## 7. Após o handshake

### 7.1 Resultado do login (found, `HandlerThreadC12340b0.A13`)

Os primeiros nós de entrada são lidos em um loop. `web` só é aceito quando um web ref foi enviado (senão `web node given during login without any web ref provided`). Qualquer coisa que não seja `web`, `success`, `failure` lança `unexpected node received during login sequence`.

Atributos de `<success>` lidos:

Atributos lidos: `t` (horário do servidor em segundos, armazenado; não numérico lança `invalid server time`), `props`, `abprops`, `mc_ep_version` (contadores de versão de config), `lid` (LID da conta, comparado com o LID armazenado; divergência reporta `lid-chatd-lid-mismatch`), `pn` (JID de usuário do telefone), `static_pq_key` (chave PQ do servidor em base64, 4.5).

### 7.2 Modo passive vs active (found)

`passive` no payload vem da session info (`C37981fJ.A0A`); campos de log `forcePassiveMode`, `enablePassiveModeBasedOnQueueSize`, `duplexActive`. Após o login o cliente sai do modo passive com um IQ set construído por `AbstractC44071qq`:

```xml
<iq id="..." xmlns="passive" type="set" to="s.whatsapp.net"><active/></iq>   <!-- or <passive/> -->
```

Pre-acks são enviados primeiro quando há enfileirados (`ConnectionThread/send preacks`). Um timer de 32000 ms (`HandlerC21850s9.A02`) é armado no envio; se o sinal de conexão ativa não chega, dispara o motivo 10 (`connection active timeout`).

### 7.3 Boletins de informação (found, `C40581l4`)

Filhos de `<ib>` tratados: `edge_routing` (filho `routing_info`, armazenado, seção 3.1), `fbip` (IPs separados por vírgula para o gerenciador de fallback), `client_expiration` (`t`, segundos, convertidos para ms), `dirty`, `offline_preview`, `location`, `notice`, `recovery_nonce`, `safetynet`, `sonar` (`url`), `streamdebug`, `thread_metadata`, `gpia`, `age_experience`, `accept_paa_link`, `peer_device_presence`. `dns_domain` não está presente (ausente do cliente Android).

---

## 8. Codificação binária de nós

### 8.1 Conteúdo do frame e flags (found, `C40411kn.Csv`, `C24610wf.Be0`)

Após a decifração AES-GCM, o plaintext começa com um byte de flags:

| Bit | Significado |
|-----|-------------|
| `2` | o restante é um stream zlib (DEFLATE); o decoder o descomprime e mantém o byte de flags |
| `1` | fragmentação; o decoder lança `server to client stanza fragmentation not supported` |

Encoder: `Csv(node, flags)` com `flags & 2` comprime (`DeflaterOutputStream`) e prefixa `02`; caso contrário escreve um byte de flags `00`. Os principais caminhos de envio em `HandlerThreadC12340b0` e a thread de escrita `HandlerThreadC21920sG` chamam `Csv(node, 3)`, portanto essas stanzas são comprimidas. `Csu(node)` (= flags 1, não comprimido) é chamado a partir de `C40851lV`, que parece ser o remetente da etapa de login (inferred). O marcador de fim de stream é `00` + list(1) + token `02` (`Clp`, `xmlstreamend`).

### 8.2 Bytes de tag (found)

| Byte | Nome | Corpo |
|------|------|-------|
| 0 | lista vazia / ausente | nenhum |
| 1, 2 | `xmlstreamstart`, `xmlstreamend` | o decoder os rejeita como strings |
| 3..235 | token de um byte | índice na tabela `A00` de 236 entradas |
| 236..239 | dicionário 0..3 | 1 byte de índice em `A01[tag - 236]` (256 entradas cada) |
| 244 / 247 | JID_INTEROP / AD_JID | `user:str, device:u16, integrator:u16, domain:u8` / `domain:u8, device:u8, user:str` |
| 248 / 249 | LIST_8 / LIST_16 | `count:u8` / `count:u16` |
| 250 | JID_PAIR | `user:str or 00, server:str` |
| 251 / 255 | HEX_8 / NIBBLE_8 | `lenAndOdd:u8` + nibbles empacotados |
| 252 / 253 / 254 | BINARY_8 / _20 / _32 | `len:u8` / `len:u20` (3 bytes) / `len:u32`, depois os bytes |

As tags 245 e 246 não existem neste codec. Todos os inteiros de vários bytes são big-endian.

### 8.3 Layout do nó (found, `C40411kn.A01`)

```
list(size)  description  (key value)*  [content]
size = 1 + 2 * attrCount + (content ? 1 : 0)
```

Tamanho ímpar significa sem conteúdo. Decoder: contagem de atributos = `((size - 2) + size % 2) / 2`. O conteúdo é um blob de bytes (`252 / 253 / 254`) ou uma lista de filhos. Um nó com blob e filhos ao mesmo tempo lança `more than one source of inner data`. Cabeçalho de lista: 0 para vazia, 248 abaixo de 256 entradas, 249 abaixo de 65536, senão `list too long`.

### 8.4 Escada de strings (found, `C40411kn.A05` / `A06`)

| Slot | Ordem tentada |
|------|---------------|
| description | token, dicionário, JID (se interpretável), UTF-8 com prefixo de comprimento |
| chave de atributo | token, dicionário, UTF-8 |
| valor de atributo | token, dicionário, JID, empacotado, UTF-8 |
| bytes de conteúdo | BINARY bruto (`A06(bytes, false)`), nunca tokenizado nem empacotado |

Empacotamento (`A06` com a flag de empacotamento, somente valores de atributo): comprimento abaixo de 128 e todos os caracteres em `[0-9-.]` resulta em NIBBLE_8 (`255`; `0-9` = 0..9, `-` = 10, `.` = 11); comprimento abaixo de 128 e todos os caracteres em `[0-9A-F]` resulta em HEX_8 (`251`); o bit de comprimento ímpar é `0x80` no byte de comprimento. Comprimentos de 256 em diante usam BINARY_20 até 1 MiB, BINARY_32 acima disso. Mapa de nibbles do decoder: 10 `-`, 11 `.`, 12 `:` (o encoder nunca emite 12).

### 8.5 JIDs (found, `C40411kn.A00`, `C24610wf.A02`)

| JID | Codificação |
|-----|-------------|
| usuário interop (`C99O`, tipo 22) | `244, user, device u16, integrator u16, 00`; decodifica para `{integrator}-{user}[:device]@interop` |
| grupo interop (`C55529Oy6`, tipo 28, servidor `interop.g.us`) | `244, user, 0000, 0000, 02`; o decoder exige device e integrator 0 |
| agent ou device presente | `247, domainByte, device, user`; bit `1` de domainByte = LID, bit `128` = hosted |
| caso contrário | `250, user (or 00), server` |

Mapeamento de servidor do AD_JID: `0` `s.whatsapp.net`, `1` `lid`, `128` `hosted`, `129` `hosted.lid`. O device `99` é esperado exatamente quando o bit hosted está ligado; uma divergência é registrada em log e o JID continua aceito. JIDs não conformes lançam `failed to write jid`.

### 8.6 Dicionário (found, `AbstractC40911lb`)

236 tokens de um byte (o índice 0 é null) e quatro dicionários de 256 entradas; a versão do dicionário é o último byte de intro, `03`. Índices re-resolvidos neste build:

| Token | Índice | Token | Índice |
|-------|--------|-------|--------|
| `s.whatsapp.net` | 3 | `iq` / `ack` / `message` | 25 / 27 / 19 |
| `type`, `id`, `from`, `to` | 4, 8, 6, 17 | `get` / `set` / `result` / `error` | 41 / 90 / 20 / 168 |
| `routing_info` / `edge_routing` | 39 / 40 | `urn:xmpp:ping` / `ping` / `w:p` | 43 / 86 / 87 |
| `handshake` / `success` | 53 / 76 | `stream:error` / `not-authorized` | 157 / 209 |
| dict 0: `active` / `conflict` / `replaced` / `passive` | 1 / 14 / 17 / 24 | dict 1: `dirty` / `server-error` / `pair-device` | 1 / 145 / 238 |
| dict 2: `failure` / `rate-overlimit` | 60 / 239 | `call` / `usync` / `w:m` | 100 / 121 / 194 |

Alguns tokens da tabela são constantes Java importadas de outras classes (por exemplo `enc`); não foram resolvidos por esta lista de índices. Os índices mudam entre builds; não os reutilize entre versões.

---

## 9. Keepalive e timers

| Timer | Valor | Tier |
|-------|-------|------|
| Ping do cliente | `<iq type="get" xmlns="w:p" to="s.whatsapp.net"/>` (`C9EN`); a resposta deve trazer `from`, `id`, `t` em 1577865600..4102473600 e `type="result"` (`C14U`) | found |
| Timeout do ping | `clamp(flag 15103, 8000, 32000)` ms; no timeout `C14R.CY1()` executa uma vez por ping (reação de reconexão inferred) | found / inferred |
| Intervalo do ping | flag **15270** (primeiro), **15183** (seguintes); runnable com delay ou alarme `com.whatsapp.alarm.CLIENT_PING_TIMEOUT`, escolhido pela flag **6493** | found, valores no servidor |
| Ping do servidor | `<iq type="get" xmlns="urn:xmpp:ping" t="...">` (`AbstractC40501kw`) | found |
| Ack do modo ativo | 32000 ms, depois desconexão motivo 10 | found |
| Recibo de mensagem | 45000 ms após o envio, ainda sem confirmação: reconexão motivo 9 (`HandlerC21850s9`) | found |
| Timeout de logout / timeout do socket | 10000 ms / 30000 ms | found |

---

## 10. Reconexão e backoff (found, `C11380Yq.A07`, `C0X9`)

`C11380Yq` agenda uma reconexão via `AlarmManager` (`com.whatsapp.MessageHandler.RECONNECT_ACTION`, extra `connect_reason` 3). A unidade de delay é 10 s (0x2710 ms no smali).

| Passo | Regra |
|-------|-------|
| Contador | `C0X9(1, 17280)`: Fibonacci em unidades, sequência 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ... limitada a 17280 unidades (48 h) |
| Primeira retentativa | 0 unidades: `scheduleReconnect/immediate` |
| Jitter | `d = units * 10 s`; delay uniforme em `[d / 2, 1.5 d)` |
| Limite | quando a flag do chamador está ligada, delays acima de 15 min viram 15 min mais um offset aleatório de `-30 .. +29` ms (`backoff clamped to ~15mins`) |
| Reset | `A02()` zera o contador em uma requisição de reconexão `reset` |
| Overrides | `force` limpa o deadline pendente; `force_no_ongoing_backoff` pula a espera; `reset` zera o contador |
| Sem rede | `handleDisconnected/retry/network_unavailable` espera por conectividade (alarme `CONNECTIVITY_RETRY_ACTION`) |

Dentro de uma tentativa, a sequência de conexão da seção 2.2 percorre hosts e portas; o backoff se aplica entre tentativas falhas do connect inteiro.

---

## 11. Stream errors e códigos de falha

### 11.1 `<failure reason="N">` no login (found, `A13`)

| Reason | Tratamento | Atributos extras lidos |
|--------|------------|------------------------|
| 5xx | falha de servidor com nova tentativa, `C45351tB(type 4)` | nenhum |
| 402 | família de ban; type 13 (code 106 com `appeal_token`), 14 (code 107), 15 (code 109), senão 2 | `appeal_token`, `code`, `expire`, `message`, `url`, `age_collection` |
| 403 | type 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` |
| 405 | type 3, `expiration_time = t * 1000` | `t` |
| 406 | type 5 | `code` |
| 416 | type 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` |
| outro | type 0 (caminho genérico de logout) | nenhum |

Toda falha também lê os campos opcionais de UI de logout `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text` / `_url`, `logout_secondary_button_text` / `_url` (`A17`). O mapeamento dos ints de type para telas voltadas ao usuário não foi rastreado; a semântica de ban de conta é coberta pelo relatório de ban.

### 11.2 `<stream:error code="N">` (found, `C40601l6`, `C37961fH.A1B`)

| Caso | Tratamento |
|------|------------|
| Qualquer `stream:error` | `ConnectionThreadRequestsImpl/stream/error` registrado com o primeiro filho; uma mensagem com `errorCode` é postada em `MessageHandler` |
| Código 500-599 | `MessageHandler` define uma flag e executa uma passada de reconexão (`onConnectionStreamError`) |
| Filho `ack` | tratado como ack-kick: a stanza pendente com esse id é buscada, métricas são emitidas, a conexão é encerrada (`1t7` lançado) |
| Filho `conflict type="device_removed"` | somente companion: deregister (`C24100vp.A02`), exceto no estado 9 |
| 515 / 516 (caminho companion) | encaminhados como mensagens tipadas; o ramo decompilado do 515 não é claro |
| `<error code="479">` | `smax-invalid` reportado (`SmaxInvalidError`) |
| `<error class="status" id=...>` | faz falhar o callback de ack de status pendente |

### 11.3 Falhas de handshake e socket (found como tags de log, reações parcialmente rastreadas)

| Tag de log | Causa |
|------------|-------|
| `socket/goaway` (`X.1sn`) | bytes de comprimento do ServerHello iguais a `GOA` |
| `socket/invalid-certificate-exception` (`X.1so`) | verificação da cadeia de certificados falhou (5); chama `C37031dS.A0C` |
| `socket/disconnect/invalid-server-static-key` (`X.1sp`), `.../authKey` (`X.1sm`) | static do servidor rejeitado; problema na chave estática do cliente |
| `socket/disconnect/noise` (`X.1sr`) | exceção de protocolo (dados de handshake inválidos, tamanhos de TLV); falha AEAD `X.1t9` e erro de entrada KEM `X.1tC` são relançados nesta família |
| `socket/disconnect/io`, `socket/closed`, `socket/error/EPERM` | erros de E/S, rede bloqueada |
| `connect/not-allowed/clock`, `software-expired`, `login-failed`, `quit-flag-set` | gates pré-conexão |
| `ReaderThread/corrupt-stream-error` | stream de nós inválido; `next-port/corrupt-stream-exception` avança a porta |

---

## 12. Feature flags (ids conforme lidos em `AbstractC36791d3` e pontos de chamada)

| Id | Tipo | Controla |
|----|------|----------|
| **20161**, **34536** | int, string | modo PQ (1 enable, 2-4 enforce), variante PQ (padrão `IKKEM`) |
| **38643**, **15716** | string, bool | escolha do KEM (`MLKEM768` reconhecido), gate para ele; efeito não resolvido |
| **33751** | bool | writer com buffer para intro + ClientHello |
| **22916**, **30712**, **33512** | bool | desabilita o passo HISTORY; carrega o registro do último sucesso; reutiliza a porta armazenada |
| **20801**, **23630**, **24645** | bool | passo 5 fixo em 443; passos 2-4 sob config SOCKS; fonte da config do serviço SOCKS |
| **13545** | string | modo do resolver de DNS (`secondary` / `hardcoded` / `none`) |
| **7831**-**7834** | bool, ints | habilitação e parâmetros do TCP keepalive |
| **15103**, **15270**, **15183**, **6493** | int, bool | timeout do ping, intervalos, método de agendamento |
| **20485**, **22413** | bool | estado da fila no payload |

Todos os valores são do lado do servidor; os padrões são os compilados nas declarações das flags.

---

## 13. Outros transportes

| Transporte | Estado na 2.26.41.6 | Tier |
|------------|---------------------|------|
| Cliente HTTP Tigon | `com/crossapp/tigonhttp/TigonHttpClient*`, `com/facebook/tigon/**`, `com/whatsapp/infra/tigon/WAHucClient`, auth via `WATigonAsyncAuthServiceHolder`; strings HTTP/2 e HTTP/3 (`MNS/mvfst-mobile`, `MNS/ngtcp2`) em `libwhatsappmerged.so` | classes e strings found; uso por feature inferred |
| DistribGW (DGW) | `com/facebook/distribgw/client/*`, `RequestStreamDGWBuilder`; único registro no lado do app encontrado: `WaFalcoStreamingRegistration.nativeRegisterStreaming(DGWClient)`; strings `distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, `XPLAT_RS_MQTT`, `XPLAT_RS_STARGATE`, `wa_request_stream` | found; formato de rede unknown |
| Cliente MQTT | nenhum; `mqtt` aparece apenas em nomes de eventos de analytics e rótulos de tipo de stream do DGW | found |
| GraphQL sobre chatd | `com.whatsapp.pando.chatd.WAChatdGraphQLClient`, `WAChatdGraphQLCallbacks`, `WATigonMexdServiceHolder` | nomes found; trafega sobre chatd como caminho w:mex inferred |

### 13.1 Canal Tigon Noise (segunda pilha Noise, nativa)

Este é um transporte diferente do chatd. A evidência são strings e nomes de classes, não lógica decompilada.

- Carrier: WebSocket sobre a pilha de rede MNS (`NoiseCarrierWebSocket`, `Stream0Listener`); streams numerados com um stream de controle 0 e remontagem de chunks (`noise.framer.*`).
- Resultados do handshake (`NoiseHandshakeOutcome`): `LEGACY_PEER_VERIFIED`, `PRIVATE_AUTH_PEER_VERIFIED`, `ENROLLMENT_REQUIRED`, `KEY_REQUIRED`, `VERIFICATION_FAILED`; `NoisePrivateAuthMode`: `MIGRATION`, `REQUIRED`; erros como `noise.handshake.attestation_failed`, `chip_binding_rejected`, `private_auth.vm_proof_failed`.
- Atestação: verificador AMD SEV-SNP (`NoiseSevSnpAttestationVerifier`, verificações da cadeia VCEK / ASK / ARK, binding de chip id); rótulos `hatch.noise-auth.key.v1`, `.client-proof.v1`, `.vm-proof.v1`.
- Controle de demanda: `NoiseConnectionDemandRejectionReason` `OFFLINE`, `BACKGROUND`, `PAUSED`, `SESSION_ENDED`, `RETRY_EXHAUSTED`, `INTERNAL`.
- Usuários Java: `WaVmHttpTransportImpl`, `NoiseVmConnection` (caminho `/v1/noise`, passos `hatch-noise status=opening` / `result=ready`), `NoiseGatewayCarrier`. A finalidade (HTTP sobre Noise para uma VM de confidential-compute para o agent browser) é inferred a partir dos nomes e das strings de atestação.

Nada aqui compartilha código com o handshake do chatd da seção 4; o nome de padrão igual não significa enquadramento, prologue ou payload iguais.

---

## 14. Baileys (`baron-baileys-v2`, confirmado contra o código-fonte)

| Aspecto | Baileys | Android 2.26.41.6 |
|---------|---------|-------------------|
| Cabeçalho de intro | `NOISE_WA_HEADER = [87, 65, 6, 3]` | `57 41 06 03` |
| Padrão | `NOISE_MODE = 'Noise_XX_25519_AESGCM_SHA256\0\0\0\0'` | mesmo nome preenchido de 32 bytes |
| Cert do servidor | decodifica `CertChain`; assinatura do leaf verificada com a chave do intermediate; intermediate verificado com a raiz fixada `142375574d0a...da8ee6b`; `issuerSerial` deve ser 0 | mesma cadeia e os mesmos bytes da raiz; o APK exige adicionalmente `leaf.issuerSerial == intermediate.serial` |
| Edge routing | armazena `routing_info` de `<ib><edge_routing>`; anexa como query `ED=<base64url>` em `wss://web.whatsapp.com/ws/chat` | armazena (máx. 256 bytes); envia `45 44 00 01 len24 blob` bruto antes do intro |
| Keepalive | `<iq type="get" xmlns="w:p"/>` sem filhos, intervalo padrão 30000 ms, timeout de conexão 20000 ms | mesmo IQ; intervalo e timeout vindos de flags do servidor |
| Payload de login | `passive`, `pull` true, `username`, `device`, `connectType WIFI_UNKNOWN`, `connectReason USER_ACTIVATED`, `lidDbMigrated false`, `releaseChannel RELEASE` | sem `pull`, `connectReason` do estado da sessão, `releaseChannel BETA` neste build |
| Payload de registro | `passive false`, `pull false`, `devicePairingData` | `devicePairingData` somente na conexão de registro de companion |
| Transporte | frames WebSocket | TCP bruto, frames com comprimento de 3 bytes |

Diferenças confirmadas que importam para um transporte no estilo Android: a dica de edge é um parâmetro de query na URL do WebSocket no Baileys, mas um cabeçalho bruto antes do intro no Android; o Baileys não impõe `leaf.issuerSerial == intermediate.serial`; o Baileys envia `pull` e `passive` como true no login, enquanto o payload do Android não tem `pull`. O Baileys mantém a chave estática do servidor para uma reconexão rápida (um comentário no código cita `NoiseIkSession`), correspondendo ao resume IK da seção 4.4 apenas na intenção; sua forma na rede não foi comparada.

---

## 15. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| `GOA` nos três primeiros bytes | goaway do servidor durante o handshake | tentar o próximo endpoint |
| `Handshake message does not contain server hello!` | o primeiro frame do servidor não é um ServerHello | verificar prologue e cabeçalho de edge |
| `noise certificate key does not match proposed server static key` | a chave do leaf difere do static do handshake | verificar a cadeia antes do ClientFinish |
| `server to client stanza fragmentation not supported` | bit `1` das flags ligado | não suportado pelo cliente |
| `unexpected node received during login sequence` | o primeiro nó não é `web`, `success`, `failure` | nenhuma |
| `noise-pq-static-key-decode-failed` | `static_pq_key` não é base64 válido | chave não armazenada, reportado uma vez |
| `scheduleReconnect backoff=...` | falhas repetidas | aguardar o backoff ou forçar uma reconexão |

---

## 16. Distinções importantes

| Não confundir | Detalhe |
|---------------|---------|
| Noise do chatd vs canal Tigon Noise | Java vs nativo, carrier TCP vs WebSocket, finalidade diferente; o nome de padrão igual não implica nada sobre enquadramento ou payload |
| Cabeçalho de intro vs cabeçalho de edge | `WA 06 03` entra no hash como prologue; `ED 00 01 len blob` não faz parte do transcript |
| Host de edge `eN.whatsapp.net` vs `routing_info` | os hosts vêm da sequência do cliente; `routing_info` é um blob opaco reenviado no cabeçalho de edge |
| `fallback_hostname` / `fallback_ip4` / `fallback_ip6` | atributos de hosts de `media_conn` (CDN), não fallbacks do chatd; os fallbacks do chatd vêm de `<ib><fbip>` e da tabela fixa |
| Flag `passive` do payload vs IQ `<passive/>` | flag definida na conexão; o IQ muda para o modo ativo depois |
| `devicePairingData` vs registro HTTP | os dados de pareamento pertencem à conexão de registro de companion |
| Comprimento do frame vs tamanho da lista | o comprimento de 3 bytes envolve o ciphertext; o tamanho da lista conta slots do nó |
| Versão do protocolo vs do dicionário | ambas no intro: `06` e `03` |
| `stream:error` vs `failure` | `failure` responde ao login; `stream:error` pode chegar a qualquer momento |

---

## 17. Fluxo completo

```
[Connection thread]  C37031dS.A0G picks step (history, g, g-fallback, hard-coded, eN, proxy)
     │  DNS ─► TCP connect ─► optional TLS wrapper
     ▼
[Client]  write [ED 00 01 len24 routing_info]?  [WA 06 03]        h = SHA256(name) ; h = SHA256(h || WA 06 03)
     │  frame1: HandshakeMessage{clientHello{ephemeral}}           mixHash(e_c)    (resume: + static + payload)
     ▼
[Server]  frame2: serverHello{ephemeral, static, payload}
     │  mixHash(e_s) ; mixKey(ee) ; s_s = decrypt(static) ; mixKey(es) ; cert = decrypt(payload)
     │  CertChain: leaf.key == s_s ; intermediate by pinned root ; leaf by intermediate
     ▼
[Client]  frame3: clientFinish{static = enc(s_c), payload = enc(ClientPayload)}      mixKey(se) ; split
     ▼
[Server]  [len24 | AES-GCM(flags | node)] ─► <success t props abprops lid pn static_pq_key/>  or  <failure reason/>
     ▼
[Client]  <iq xmlns="passive" type="set"><active/></iq> (+ pre-acks) ; steady state both ways, own counter per direction
     │  ping <iq xmlns="w:p"/> ; ib / notification / message / receipt / call ...
     ▼
[Failure]  stream:error / ping timeout / socket error ─► disconnect ─► Fibonacci backoff ─► next attempt
```

---

## 18. Incógnitas

| Item | Status |
|------|--------|
| Tráfego de rede de qualquer tipo | nada capturado; nenhum item é `tested` |
| Transcript de resume IK e fallback | estrutura found, passos inferred |
| Posicionamento da chave PQ em `ServerHello.payload`, largura do comprimento do TLV, biblioteca por trás das chamadas ML-KEM | não decodificado / não identificada |
| O que os endpoints com wrapper TLS carregam dentro do TLS | inferred a partir do caminho de código |
| Valores de ping e TCP keepalive | flags do servidor |
| Ints de failure type 0-15 para telas do cliente; efeito das flags **38643**, **15716** | não rastreado / não resolvido |
| Campos do payload sem writer (`webInfo`, `shards`, `fb*`, `accountType`, `testIsolationId`, `paddingBytes`, `pull`) | nenhum encontrado neste build |
| Handshake e enquadramento do canal Tigon Noise; protocolo de rede e usuários do DGW | nativo, apenas strings |
| Strings do dicionário que são constantes Java importadas (por exemplo `enc`) | não resolvidas na lista de índices |
