<!-- src-sha1: 2c3f9604f03ccc7f3d3160d18810a86e62b8172f -->
# WhatsApp Pareamento de Dispositivo Vinculado — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** lado do dispositivo primário no pareamento de companion, fluxo de QR, fluxo de número de telefone / código de pareamento, stanzas `pair-device` e `pair-success`, material de chaves, identidade de dispositivo assinada ADV e lista de índices de chave, lista e limites de dispositivos, desvinculação, erros, comparação com Baileys

---

## 1. O que é (tecnicamente)

Um dispositivo vinculado (companion) é um segundo endpoint da mesma conta. O telefone primário o autoriza produzindo uma identidade assinada ADV (account device verification) sobre a chave de identidade do companion. Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Níveis: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido.

Os nomes ofuscados mudam a cada build e foram re-resolvidos a partir de strings estáveis na 2.26.41.6.

| Entidade | Nome na 2.26.41.6 | Função |
|--------|----------------|------|
| Orquestrador de QR/pareamento | `C45850K0w` (prefixo de log `CompanionDeviceQrHandler`) | faz o parse do QR, monta os protos ADV, envia `pair-device` |
| Construtor do IQ `pair-device` | `RunnableC46606KYf` | monta o IQ |
| Helper de requisição/resposta de `pair-device` | `KRI` (`devicePairRequest/*`) | envio, retry, parse de `device` / `companion-props` / dicas de retry |
| Roteador de erros | `C44661Jem` | mapeia o código de erro do servidor para o callback da UI |
| Parser da string do QR | `C45741Jxy` → `C45423Jrn` | payload do QR para dados de pareamento |
| Dados de pareamento parseados | `C44423JaU` | ref, chaves do companion, adv secret, plataforma |
| Util ADV | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, índice de chave, timestamp, montagem e assinatura da lista de índices de chave |
| Atualizador da lista de índices de chave | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | envia a lista assinada ao servidor |
| Verificador ADV | `C24230w2` (`DeviceADVInfoHandler`) | verifica identidades e listas vistas na rede |
| Handler de notificação da lista de dispositivos | classe anônima em `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | notificação `devices` |
| Handler de notificação de link-code | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | notificação id 252 |
| Gerenciador de link-code (primário) | `KZ3` (código de entrada, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | fluxo de código de pareamento |
| Util de criptografia do link-code | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Gerenciador de dispositivos | `C0XQ` (`companion-device-manager`) | listar, logout |
| Helper de remoção | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Wrapper da curva Signal | `C38851hm` | `org.whispersystems.curve25519` provider "best" |
| Classes proto ADV | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | ver seção 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `companion-props` no resultado de `pair-device` |
| Client props | `C43107IrI` | filho `client-props` |
| Tipo de conta/criptografia | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

Existem três modos de entrada na UI do primário (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

O mesmo APK também contém o código de registro do papel de companion (máquina de estados `C0YS`, logs `companion/registration/*`). Está fora do escopo; apenas as partes necessárias para explicar o que o primário recebe são descritas (seção 9.6).

---

## 2. Caminhos de pareamento em resumo

| Caminho | Gatilho no primário | O primário envia | Segredo que liga primário e companion |
|------|--------------------|---------------|----------------------------------------|
| QR | leitura de `https://wa.me/settings/linked_devices#<payload>` (ou `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` do campo 4 do QR |
| Número de telefone + código | `notification` `link_code_companion_reg` estágio `companion_hello`, o usuário digita o código de 8 caracteres | `primary_hello`, depois (após `companion_finish`) o mesmo `pair-device` | `adv secret` derivado de dois resultados X25519 mais um valor aleatório (seção 4.4) |

Ambos os caminhos convergem em um único objeto `C44423JaU` e um único IQ `pair-device` (found: `KYB` monta `C44423JaU` a partir do bundle de `companion_finish` com o mesmo construtor que `C45850K0w.A01` usa para o QR).

---

## 3. Fluxo de QR (lado do primário)

### 3.1 Payload do QR

`C45741Jxy.A01` remove o prefixo `https://wa.me/settings/linked_devices#` ou `whatsapp://settings/linked_devices#` e faz URL-decode do restante. `A02` divide por `,` (found):

| Idx | Conteúdo | Codificação | Uso |
|-----|---------|----------|-----|
| 0 | `ref` | string | referência de pareamento; um ref que começa com `CAPI_` é rejeitado (`invalid ref`) |
| 1 | chave pública do companion | base64 | enviada como `pub-key`, salt da chave de nonce (3.4). Nome inferred: chave estática Noise (`companion_server_auth_key_pub` no caminho de código) |
| 2 | chave de identidade do companion | base64, 32 bytes, o parser antepõe `0x05` (tipo Curve25519) | assinada pela assinatura da conta |
| 3 | `adv secret` | base64 | chave HMAC do wrapper ADV |
| 4 | código de plataforma (opcional) | um caractere | mapeia para um tipo de plataforma; `j` = dispositivo hosted |

- Menos de 3 partes: `qrData/processQR/error/invalid_code parts`. Chave de identidade ou adv secret ausente (QR antigo de 3 campos): `invalid qr code, missing companion identity key or adv secret` → código local **-9**.
- Tabela de caracteres de plataforma (independente de `EnumC26221BZl`, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). É usada apenas na verificação de hosted e em logs (3.2).

### 3.2 Verificações locais antes de enviar qualquer coisa

| Verificação | Código | Código local |
|-------|------|------------|
| O QR tem chave de identidade e adv secret | `C45850K0w.A01` | -9 |
| flag hosted consistente: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| outro pareamento já em andamento (`kri.A0N`, ou o gerenciador de dispositivos companion ocupado) | `A04` | -17 |
| timestamp ADV local válido (`C24270w6.A00() != -1`) | `A04` | -8 |
| companion hosted | `A04`: `Hosted pairing is not supported` | -10 |
| fricção do defense-mode necessária | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (retry com challenges) |

O pareamento hosted é bloqueado no cliente nesta build (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Antes do IQ: limpeza do syncd e índice de chave

1. Se o estado do syncd estiver sujo (`sync-manager/shouldCleanUpSyncdOnPairing`), o app primeiro limpa o syncd e depois continua (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (em `RunnableC46617KYr`):
   - sem rawId ou índice armazenado: novo rawId aleatório, índice 1;
   - nenhum companion vinculado: `rawId + 1`, o índice permanece 1;
   - existem companions: `currentIndex + 1`; em caso de overflow, rawId + 1 e todos os dispositivos sofrem logout (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (seção 5.4).

### 3.4 O que é montado

Em `C45850K0w.A00`, com `E` = chave de identidade do companion (32 B, bruta), `P` = par de chaves de identidade do primário (Curve25519), `S` = adv secret:

| Passo | Operação | Nível |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | assinatura da conta = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; prefixo `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` fica vazio: o companion o adiciona) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = passo 3 serializado, hmac = HMAC-SHA256(key = S, data = bytes do passo 3), accountType}`; para hosted os dados são `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) de `C24270w6.A01`, assinada por `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | chave de nonce `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, embrulhada como filho `pem` | found (derivação); finalidade inferred |
| 7 | `encryption-metadata` opcional (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, de `AuthProofHelper` (criptografia da senha da conta, label `rsa2048`) | found (estrutura); o que comprova é unknown |
| 8 | `client-props` opcional (`C43107IrI`, seção 3.6) | found |

Detalhe do passo 6: o nó `pem` é rotulado com `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 days`, `key_id=1`, mas seu filho carrega `key.getEncoded()` da saída HKDF de 32 bytes (`SecretKeySpec` algorithm `AES-GCM`). O rótulo e o conteúdo não coincidem; o motivo é unknown. O uso no servidor é inferred (o servidor criptografa um nonce por dispositivo para o companion; cf. coluna `companion_meta_nonce`).

### 3.5 O IQ `pair-device` (primário → servidor)

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <pair-device>
    <ref>…</ref>                                    <!-- QR field 0 -->
    <pub-key>…</pub-key>                            <!-- QR field 1 -->
    <device-identity>ADVSignedDeviceIdentityHMAC</device-identity>
    <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
    <client-props>…</client-props>                  <!-- optional -->
    <pem version="1" algorithm="rsa2048"><pem>…</pem><ttl ts_s="432000"/><key_id>1</key_id></pem>
    <encryption-metadata version="1" algorithm="rsa2048">…</encryption-metadata>   <!-- optional -->
    <companion_qr_origin_source>1|2</companion_qr_origin_source>
    <challenges><supported><friction variant="1"/><passkey-create/></supported>
                <completed>…</completed></challenges>                              <!-- optional -->
  </pair-device>
</iq>
```

Found: todos os nomes de filhos, o valor do atributo `ts` (o timestamp da lista de índices de chave), timeout de **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` é `1` para o valor de entrada 3 e `2` para o valor de entrada 5 (o significado dos ints de entrada é unknown). A ordem exata dos filhos e o ramo de `companion_qr_origin_source` estão parcialmente corrompidos pelo decompilador; trate a ordem como não verificada.

### 3.6 `client-props` (`C43107IrI`)

| Campo | Número | Tipo | Definido quando |
|-------|--------|------|-----------|
| `isChatDbLidMigrated` | **1** | bool | migração de LID do chat DB concluída |
| `isSyncdPureLidSession` | **2** | bool | flag syncd pure-LID presente |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | flag de recovery |
| `isHsThumbnailSyncEnabled` | **4** | bool | flag de thumbnail do history-sync |
| `subscriptionSyncPayload` | **5** | bytes | montado quando o md sync está habilitado (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | DB de JID de bot migrado |

### 3.7 Tratamento do resultado (`KRI.CFS`)

Filhos do resultado de sucesso (found):

| Filho | Uso |
|-------|-----|
| `device` attr `jid` | o novo `DeviceJid` do companion; o device id **99** é mapeado para a entrada de plataforma hosted |
| `companion-props` | proto `DeviceProps` (`C43105IrG`): `os` **1** (string), `version` **2** (message), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (message) |
| `retry-ts` attr `ts` | o servidor pede um timestamp mais novo; o app tenta de novo (`RunnableC46585KXj`) |
| `retry-after-challenges` | filhos `friction` (attr `variant`, deve ser `1`, `location` opcional "lat,lon") ou `passkey-create` (attr `created`) |
| `retry-with-method` | filhos `qr-code` ou `shortcake-with-passkeys`; se o segundo estiver presente, a chave de handoff de 32 bytes (HKDF do adv secret, info `shortcake-passkey-handoff-v1`) é guardada (`PairingHandoffKeyHolder`), controlada por um abprop |

Em caso de sucesso, o app armazena o registro de dispositivo `CJY` (string base64 aleatória de 24 bytes, `adv_key_index` = índice atual, `requireFullSync`), salva o timestamp da lista de índices de chave como `adv_timestamp_sec` (`C24270w6.A05`) e inicia o estado de history sync (`C8N`).

Falha de entrega (`Bog`): até **3** retries, atraso `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s) se a flag de retry estiver ligada (found); depois, callback de erro.

---

## 4. Fluxo de número de telefone / código de pareamento (lado do primário)

### 4.1 Passos

| # | Direção | Stanza / ação | Classe |
|---|-----------|-----------------|-------|
| 1 | companion → servidor → primário | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | primário | armazena o hello, mostra notificação push → `CompanionHelloConfirmationActivity` / tela de inserir código | `C10J`, `C77`, `JYJ` |
| 3 | usuário | digita o código de 8 caracteres | `LinkedDevicesEnterCodeActivity` |
| 4 | primário → servidor | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (timeout 120000 ms) |
| 5 | servidor → primário | `notification` `stage=companion_finish` | `C10J` → `KYB` case 0 |
| 6 | primário → servidor | IQ `pair-device` (seção 3.5) | `C45850K0w` |
| 7 | outros estágios | `refresh_code` (o primário pede renovação do código, attr `force_manual_refresh`) | `C10J` |

### 4.2 Notificação `companion_hello` (found)

| Filho | Uso |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | chave X25519 efêmera do companion, embrulhada com o código (4.3) |
| `companion_server_auth_key_pub` | depois se torna o `pub-key` em `pair-device` |
| `link_code_pairing_ref` | ref da sessão (string) |
| `companion_platform_id` | string de id da plataforma |
| `companion_platform_display` | nome de exibição |
| attr `should_show_push_notification` | `true` → notificação push |

Estado mantido (`C77`/`CE4`, JSON em SharedPrefs `companion_reg_with_link_code_companion_hello_info_json`): ref, id da plataforma, chave embrulhada, chave de autenticação do servidor, expiração `now + min(360000, flag 3816 * 1000)` ms. Hello expirado ou ausente → "companion hello is null or expired" (estado de UI 2). Um hello mais novo com ref diferente cancela o ref anterior (`KRJ.A00(oldRef, "true")`).

### 4.3 Código e criptografia de wrap (found)

| Item | Valor |
|------|-------|
| Código | 5 bytes aleatórios → 8 caracteres, 5 bits cada, alfabeto `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 símbolos, sem `0 I O U`) (`K1T.A00`, gerado pelo companion) |
| Código → chave | PBKDF2-HMAC-SHA256, **131072** iterações, 256 bits, senha = caracteres do código, salt = primeiros 32 bytes do blob embrulhado (`K1T.A02`) |
| Chave efêmera embrulhada | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, plaintext = chave pública X25519 de 32 bytes; o comprimento deve ser ≥ 48 |
| Resposta do primário | o primário cria seu próprio par de chaves efêmero e embrulha sua chave pública da mesma forma (salt novo de 32 B, IV de 16 B, mesmo código) |

### 4.4 `primary_hello` e `companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

Filhos da notificação `companion_finish`: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Processamento no primário em `KYB` case 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (armazenado no momento do `primary_hello`).
2. Layout do bundle `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, mínimo de 44 bytes.
3. Chave = HKDF-SHA256(salt = salt do bundle, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Verificações: a identidade do primário deve ser igual à própria chave de identidade; a identidade do companion deve ser igual a `companion_identity_public` da notificação; caso contrário, o ref é descartado e a UI recebe um estado de erro.
6. `adv secret = HKDF-SHA256(salt = 32 zero bytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Chave de handoff = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (também armazenada em `C44423JaU`).
8. `C44423JaU` é montado com `pub-key` = `companion_server_auth_key_pub`, identidade do companion, adv secret → o mesmo IQ `pair-device` do QR.

O ECDH efêmero externo existe (é o IKM do HKDF do passo 3). Uma nota de uma build anterior dizia "no ECDH in this stage"; isso está errado para esta build.

Marcadores de erro no lado do primário: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. Identidade de dispositivo assinada ADV

### 5.1 Campos proto (found, a partir das strings de layout do lite-proto)

| Mensagem | Classe | Campo | Número | Tipo |
|---------|-------|-------|--------|------|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | enum (`EnumC32116E1o`) |
| | | `deviceType` | **5** | enum (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (definido pelo companion) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | uint32 empacotado |
| | | `accountType` | **5** | enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (somente hosted) |

Números de campo e wire types são lidos do message info gerado; os nomes coincidem com as mensagens ADV canônicas. Nomes do enum: `EnumC32116E1o` valores E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Prefixos de assinatura e algoritmos

| Prefixo | Constante | Dados assinados / com MAC | Assinante | Nível |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | assinatura da conta: `‖ details ‖ companion identity pub` | chave de identidade do primário | found |
| `06 05` | `A0G` | variante hosted da assinatura da conta; também antepõe-se aos dados do HMAC para hosted | chave de identidade do primário / adv secret | found |
| `06 01` | `A0H` | assinatura do dispositivo: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | chave de identidade do companion | found (lado de verificação) |
| `06 06` | `A0I` | variante hosted da assinatura do dispositivo | chave de identidade do companion | found (lado de verificação) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | chave de identidade do primário | found |
| `06 07` | `A0K` | atestação non-E2EE ("hybrid") (`AeaUtils`), não é prefixo de lista de índices de chave | chave de identidade do primário | found |

- Primitiva de assinatura: `C38851hm.A00("best")` carrega `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (assinatura de 64 bytes), `A02` = `calculateAgreement`. As chaves têm 32 bytes com byte de tipo `5`. Ou seja, assinaturas Curve25519 da biblioteca curve25519 do Signal (estilo XEdDSA, inferred a partir da biblioteca, não do nome do algoritmo). A escolha do provider nativo vs Java é decidida em runtime (unknown qual é usado em um dado dispositivo).
- HMAC: `HmacSHA256` via `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Lista de índices de chave

`C24270w6.A01` monta `ADVKeyIndexList`; `validIndexes` é um conjunto formado por (found): uma entrada para o slot do primário (valor 0 quando não está em modo companion; condição do ramo inferred), o `adv_key_index` de cada companion armazenado (`CJY.A07`) e `currentIndex`. `A02` assina `06 02 ‖ details`.

`C24250w4.A00` a envia como:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout de 32000 ms. Gate `A02`: flag **477** diferente de zero, companions presentes (ou modo companion), não estar em modo companion. Em caso de falha, `adv_key_index_list_update_retry_count` é incrementado; acima de **5** o app registra `adv-key-index-list-update … fails for more than 5 times` e faz logout de todos os companions (`C24270w6.A03`). O sucesso zera os contadores (`A05`).

### 5.4 Regra do timestamp (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = relógio corrigido por NTP, `srv` = hora do servidor. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. Se `last + 1 > now + 86400`, o valor é inválido (-1, log `getTimestampSec invalid ts`), o que bloqueia o pareamento com o código local -8. Monotônico por conta (found).

### 5.5 Verificação na rede (`C24230w2`)

Para qualquer identidade de dispositivo que o primário vê (próprios e companions de contatos), ele verifica, em ordem (found):

1. chave de identidade do primário conhecida (armazenada, ou `accountSignatureKey` da lista), senão `no primary key`;
2. a chave de identidade do companion faz parse (`0x05`+32 B), senão `invalid companion public key`;
3. assinatura da conta sobre `prefix ‖ details ‖ companion identity`, senão `fail to verify account signature`;
4. assinatura do dispositivo sobre `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (hosted `06 06`), senão o dispositivo é rejeitado;
5. lista de índices de chave: assinatura sobre `06 02 ‖ details` com a chave do primário; o `adv timestamp` da lista deve ser consistente (`advTimestampMismatch`, `advListTimestampInvalid`); um índice de chave recebido divergente reseta o estado local (`incoming key-index not matching local state, resetting`); um índice maior para o mesmo dispositivo já presente descarta a entrada mais antiga (`filterDeviceWithKeyIndexList`).

---

## 6. Lista de dispositivos, registro e limites

### 6.1 Notificação `devices` (o primário recebe)

`notification` com filho `add` ou `remove` (qualquer outro: `unknown type of device notification`). Atributos e filhos (found): `device_hash`, `device_lid_hash` opcional mais `lid`, entradas `device` (jid, índice de chave), `key-index-list` opcional (bytes, attr `ts`, `expected_ts`). Se a notificação tiver o attr `offline`, o usuário é enfileirado para sync posterior; caso contrário, um job de sync é executado (`SyncDeviceNotificationRunnable`). A lista só é aceita se seu timestamp não for mais antigo que o `adv_timestamp_sec` armazenado (`local ts is larger than notification one` caso contrário).

### 6.2 Registro de dispositivo armazenado (tabela `devices`, `C1h8`)

| Grupo | Colunas (found) |
|-------|-----------------|
| Identidade | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Tempo | `last_active`, `login_time`, `logout_time` |
| Sync | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Capacidade | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

Os valores de `platform_type` vêm de `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Limites e flags

| Flag / item | Significado | Nível |
|-------------|---------|------|
| **15550** | inteiro: máximo de dispositivos vinculados (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` bloqueia "vincular um dispositivo"; o leitor de QR recebe o extra `at_device_limit`; `OrbitCompanionLinkActivity` recusa quando atingido) | found (uso); valor padrão unknown (abprop entregue pelo servidor); existe o campo de métrica `md_linked_devices_max_devices_limit` |
| **3816** | segundos de validade do `companion_hello`, limitado a 360 s | found |
| **477** | gate (diferente de zero) para atualizações da lista de índices de chave | found |
| **18193** | adiciona `friction` (variant 1) a `challenges/supported` anunciados | found (uso); efeito no servidor unknown |
| **28161** | adiciona o segundo challenge anunciado (`passkey-create`) | mapeamento inferred (o decompilador perdeu o ramo) |
| **29500** | gate de pareamento hosted usado na verificação de defense-mode | found (leitura), significado inferred |
| **31019** | adiciona o attr `exclude_hosted_companion=true` ao remove-all para alguns motivos | found |

Se o servidor impõe o limite independentemente da verificação do cliente é unknown. O primário não tem timeout de inatividade no cliente para companions no código lido aqui; a expiração no servidor de companions ociosos é unknown.

---

## 7. Desvinculação (lado do primário)

### 7.1 Dispositivo único

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, timeout de 32000 ms. O resultado pode trazer o filho `coex_token` (repassado ao handler de coexistência). Falha de entrega ou erro chama o callback de falha com código -1 (found).

### 7.2 Todos os dispositivos

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Lista local vazia vai direto ao callback de sucesso. Strings de motivo vistas no código: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; a lista pode ser maior, a expressão de origem está truncada).

### 7.3 Gatilhos de desvinculação automática (found)

| Gatilho | Motivo |
|---------|--------|
| atualização da lista de índices de chave falhou mais de 5 vezes | `adv-key-index-list-update`, logout de todos |
| overflow do índice de chave | reset `A03` |
| status ADV inválido / companion desconhecido (`KZD` case 43) | `invalid_adv_status` |
| transição de tipo de conta hosted ↔ E2EE | expulsa todos os dispositivos (log `handleADVMetadata`) |
| o servidor envia notificação `devices` do tipo `remove` | registro local removido (inferred) |
| ação do usuário na tela de dispositivos vinculados / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found para o monitor; caminho de UI inferred) |

A remoção da conta como um todo (`urn:xmpp:whatsapp:account` `remove`) é outro IQ e não tem relação com a desvinculação de companion.

---

## 8. Casos de erro

### 8.1 Códigos do servidor tratados por `C44661Jem.A01`

| Código | Callback | UI | Nível |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | estado "companion too old" | found |
| 404 / 405 / 443 / 445 | `C2w` genérico | mapeamento de strings `C44648JeY`: 405 e 443 têm textos dedicados; 404/405/443/445 compartilham um título | found (strings por id); significado exato de 404/443/445 unknown |
| outros | `C2w` genérico | falha no pareamento | found |

`InstrumentationAuthActivity` nomeia os códigos de resultado 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, senão `PAIRING_FAILED` (found). O mapeamento do 405 do servidor para o caso consumer/SMB é inferred a partir do id da string.

### 8.2 Códigos locais

| Código | Causa | Correção |
|------|-------|-----|
| -8 | timestamp ADV local inválido (relógio vs último ts armazenado + 1) | corrigir a hora do dispositivo; string de UI "invalid device time" |
| -9 | QR sem chave de identidade / adv secret | usar um QR atual |
| -10 | pareamento hosted na build consumer | n/a |
| -13 | divergência entre plataforma e flag hosted | n/a |
| -17 | outro pareamento em andamento | aguardar; a requisição vive até 32 s |
| -20 | o servidor pediu challenges (`retry-after-challenges`) | concluir o challenge de friction / passkey |
| -1 | requisição de remoção não enviada ou falhou | tentar de novo |

### 8.3 Falhas de link-code

| Sintoma (log) | Causa |
|------------|-------|
| `companion hello is null or expired` | código digitado após a expiração (flag 3816, máx. 360 s) |
| `decryption fail` (hello) | código errado (a chave PBKDF2 difere; AES-CTR não tem tag, então um código errado gera uma chave inútil, detectada em passos posteriores; inferred) |
| `primary identity doesn't match` | o bundle foi montado para outra chave de primário |
| `companion identity doesn't match` | a notificação e o bundle divergem |
| `invalid-primary-adv-key-length` / `adv public key is 0` | verificações do papel de companion sobre a chave efêmera do primário |

---

## 9. Distinções principais

### 9.1 Não confundir

| A | B |
|---|---|
| `pair-device` enviado pelo **primário** (este report) | `pair-device` **recebido** por um app em papel de companion (handler `AbstractC40501kw`, id 242, traz os refs do QR) |
| `ADVSignedDeviceIdentity` (assinada, sem HMAC) | `ADVSignedDeviceIdentityHMAC` (o wrapper enviado em `device-identity`) |
| filho `device-identity` de `pair-device` (wrapper HMAC) | filho `device-identity` em stanzas de mensagem enviadas (identidade da conta anexada por um companion; pref `adv_signed_identity`) |
| assinatura da conta (chave do primário, prefixo `06 00`) | assinatura do dispositivo (chave do companion, prefixo `06 01`) |
| prefixo da lista de índices de chave `06 02` | `06 07` (atestação non-E2EE) |
| `pub-key` do QR / `companion_server_auth_key_pub` | chave de identidade do companion (a que recebe a assinatura da conta) |
| `rawId` (id de toda a conta que muda no reset) | `keyIndex` (por companion) |
| caractere de plataforma do QR (`EnumC26332BbY`) | `DeviceProps.platformType` na rede (`EnumC25120ArW`), numeração diferente |

### 9.2 Dispositivo hosted

Device id **99** do JID (`device_id should be 99 for hosted device`), marcador de registro/unpair `hosted_device_pairing`, prefixos de assinatura `06 05` / `06 06`, `exclude_hosted_companion`. O primário se recusa a parear um dispositivo hosted nesta build (local -10). Tudo além dessas strings é unknown.

### 9.3 Shortcake

`retry-with-method` pode listar `shortcake-with-passkeys`; o app então armazena uma chave de handoff e troca a UI. `ShortcakeJni` expõe `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` e `nativeResponderStart/Finish` (found). O transcript do handshake é nativo e não foi decompilado aqui: unknown.

### 9.4 Friction / defense mode

`pair-device` anuncia os challenges suportados e devolve os `completed` no retry. O primário decide localmente exigir friction quando o defense mode está ligado (`C271211x.A0N()`) e o challenge de friction ainda não foi concluído; essa decisão é tomada antes do primeiro IQ (`defense mode friction triggered`). A política do lado do servidor que envia `retry-after-challenges` não é visível (unknown).

### 9.5 Sem atestação do cliente do companion

Nada no payload de pair-device comprova qual software o companion executa: `ref`, `pub-key`, chave de identidade, adv secret e caractere de plataforma são autodeclarados pelo QR. O que as assinaturas comprovam é que esta conta primária autorizou aquela chave de identidade. Qualquer verificação de "cliente oficial" fica no servidor (o veredito 465 só é tratado no cliente).

### 9.6 Código do papel de companion no mesmo APK (resumo)

| Item | Achado |
|------|---------|
| Filhos do IQ `companion_hello` | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; attr `should_show_push_notification` (found, `C0YS`) |
| código | `K1T.A00` base32 de 5 bytes aleatórios (4.3) |
| rotacionar QR | IQ `pair-device-rotate-qr` com attrs `stage` 0/1/2 e `sentinel` opcional, filho `ref` |
| IQs md recebidos | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (ids 242, 243, 266, 278, 279) |
| conteúdo de `pair-success` e resposta `pair-device-sign` do companion | não rastreados nesta build: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Comparado com o código-fonte local; apenas coincidências e uma diferença que foram verificadas dos dois lados.

| Item | APK 2.26.41.6 | `baron-baileys-v2` | Resultado |
|------|---------------|--------------------|--------|
| Payload do QR | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | coincide (4 campos) |
| Derivação do código de pareamento | PBKDF2-SHA256 131072 it., alfabeto `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, mesmo alfabeto (`crypto.js`, `generics.js`) | coincide |
| Key bundle | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, plaintext identity ‖ identity ‖ random32 | mesmo layout (`messages-recv.js`) | coincide |
| adv secret | HKDF(zero salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | coincide |
| Wrapper HMAC | HMAC-SHA256(adv secret, [06 05 para hosted ‖] bytes de ADVSignedDeviceIdentity) | igual (`validate-connection.js`) | coincide |
| Mensagens de assinatura de conta / dispositivo | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | igual | coincide |
| Prefixo hosted da lista de índices de chave | verificador e assinante usam `06 02` para toda lista; `06 07` é o prefixo de atestação non-E2EE | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` usado quando `accountType == HOSTED` (`chats.js`) | **difere**; o fluxo hosted não é exercitado por esta build consumer, então o efeito da diferença é unknown |

Nenhuma afirmação de "por que falha" é feita: um companion Baileys que siga as linhas coincidentes é consistente com o que o primário faz parse aqui; a aceitação pelo servidor não é verificável estaticamente.

---

## 11. Fluxos completos

### 11.1 Fluxo de QR

```
[Companion]  shows QR  https://wa.me/settings/linked_devices#ref,noisePub,identityPub,advSecret[,platform]
     │
     ▼
[Primary]    scan → C45741Jxy.A02 → C45423Jrn → C44423JaU
     │       checks: -9 / -13 / -17 / -8 / -10 ; defense mode → challenges (-20)
     │       incrementCurrentKeyIndex ; ts = C24270w6.A00()
     │       details  = ADVDeviceIdentity{rawId, ts, keyIndex, accountType, deviceType}
     │       accSig   = Curve25519.sign(P.priv, 06 00 ‖ details ‖ companionIdentity)
     │       signed   = ADVSignedDeviceIdentity{details, P.pub, accSig}
     │       wrapper  = ADVSignedDeviceIdentityHMAC{signed, HMAC-SHA256(advSecret, signed)}
     │       list     = ADVSignedKeyIndexList (sig 06 02)
     │       K        = HKDF(salt = noisePub, IKM = advSecret, "Canonical Ent Companion Nonce Encrypt")
     ▼
iq set xmlns=md  <pair-device> ref, pub-key, device-identity, key-index-list ts, client-props, pem, … </pair-device>
     │
     ▼
[WA Server]   (not observed) validates, creates device jid, sends pair-device / pair-success to the companion
     │
     ▼
Result to primary: <device jid/> <companion-props/>   (or retry-ts / retry-after-challenges / retry-with-method / error 465, 496, …)
     │
     ▼
[Primary]    store CJY record, adv_timestamp_sec = list ts, start history sync
     │
     ▼
[Server → Primary]  notification devices add{device_hash, device…, key-index-list ts}  → SyncDeviceNotificationRunnable → verify (5.5)
```

### 11.2 Fluxo de código de pareamento

```
[Companion]  iq link_code_companion_reg stage=companion_hello
     │         wrapped_ephemeral = salt32 ‖ iv16 ‖ AES-CTR(PBKDF2(code, salt), ephPub)
     ▼
[WA Server]  → notification stage=companion_hello  → [Primary] C10J (id 252)
     │                                               store hello (ttl ≤ 360 s), push notification
     │                                               user types 8-char code
     ▼
[Primary]    unwrap companion eph pub ; make own eph pair ; eph = X25519(...)
     │         iq link_code_companion_reg stage=primary_hello
     │             wrapped_primary_ephemeral_pub, primary_identity_pub, link_code_pairing_ref
     ▼
[Companion]  eph = X25519(...) ; bundle = salt32 ‖ nonce12 ‖ GCM(HKDF(eph, salt), companionId ‖ primaryId ‖ random32)
     │         iq stage=companion_finish
     ▼
[WA Server]  → notification stage=companion_finish → [Primary] KYB
     │            decrypt, check both identities, advSecret = HKDF0(eph ‖ DH(id) ‖ random, "adv_secret")
     ▼
[Primary]    pair-device IQ (same as 11.1, pub-key = companion_server_auth_key_pub)
     ▼
(11.1 continues)
```

### 11.3 Desvinculação

```
[Primary UI / auto trigger]
     │   remove-companion-device jid=… reason=…     (or all="true")
     ▼
iq set xmlns=md  →  [WA Server]  →  result (optional coex_token)
     │
     ▼
[Primary]   remove local record, new key-index-list on next update (iq key-index-list ts)
[Server → other devices]  notification devices remove{…}
```
