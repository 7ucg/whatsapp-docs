<!-- src-sha1: 7a4b50013c0f196c95c57808469516becf9a34b7 -->
# WhatsApp Message Secrets — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** `messageSecret` por mensagem (geração, `MessageContextInfo`, armazenamento local, history sync), derivação de chave por caso de uso (HKDF), IV / AAD do AES-GCM, add-ons criptografados (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, edições `secretEncryptedMessage`), vínculo de identidade de remetente / alvo e retry LID / PN, órfãos e fallbacks de secret ausente, extensões da stanza `<message>` (atributos, atributos de `<enc>`, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, verificação de suporte do companion), feature flags, comparação com o Baileys

---

## 1. O que é (tecnicamente)

Toda mensagem que pode receber depois um complemento criptografado carrega um secret aleatório de 32 bytes em seu próprio payload criptografado de ponta a ponta (`MessageContextInfo.messageSecret`). Um complemento (reação, voto de enquete, resposta de evento, comentário, edição) é criptografado com uma chave derivada desse secret, do id da mensagem original, do remetente original e do modificador. O servidor retransmite o complemento como uma mensagem E2E comum, mas não consegue lê-lo nem movê-lo para outro alvo, usuário ou caso de uso sem quebrar a autenticação GCM. Todas as afirmações vêm de análise estática do APK decompilado; nada foi capturado na rede. Níveis: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido. Os nomes ofuscados foram re-resolvidos na 2.26.41.6 a partir de strings estáveis (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, strings de caso de uso, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

A mesma versão também define as extensões da stanza `<message>` (da seção 10 em diante): atributos e nós filhos que classificam e roteiam uma mensagem, mas não carregam seu conteúdo. Ficam agrupados aqui porque `<meta polltype>` / `<meta event_type>` precisam concordar com o payload criptografado por secret (7.4).

| Entidade | Nome na 2.26.41.6 | Função |
|----------|-------------------|--------|
| Crypto helper (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` criptografa, `A04` descriptografa (retry de identidade), `A02` resolve a chave do alvo |
| Carregadores de parâmetros de criptografia / descriptografia | `C32833ETl` / `C32854EUg` | dados, remetente, chave do alvo, caso de uso / IV, payload, chaves, remetente |
| Derivação de chave | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, salt zero |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | nativo, tag de 16 bytes |
| Provedores de AAD | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (nenhum) | dados adicionais |
| Gerador de secret | `AbstractC33322EfC.A01` | `SecureRandom`, 32 bytes |
| Secret store (`MessageSecretStore`) / extra em memória | `C35311ad` (tabela `message_secret`) / `C35171aP` na mensagem `C13G` | persistir e transportar |
| Mapeador da chave original (`ReferentialKeyUtil`) | `C43661qB.A03` | chave da mensagem original sem edição |
| Handlers de reação | `DU8` (envio), ramo `F2P` (recebimento) | `reactionMessage` / `encReactionMessage` |
| Voto de enquete / resposta de evento / comentário | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Edições criptografadas por secret (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Criação de enquete / evento (secret obtido no recebimento) | `F2N` / `F2M` | lê `messageSecret` para dentro do FMessage |
| Proto: contexto / mensagem / chave | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Seletor do `type` da stanza | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Contribuidores de saída da stanza | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), flags `F68`, cap `F69`, padding `F6H`, reporting `F6L` / `F6C`, cstoken `F6G`, tctoken `F6I`, device-identity `F6B`, hsm `F6X` | montam filhos de `<message>` |
| Acumulador de `<meta>` | `EZV` (atributos `A01`, filhos `A00`) | um nó `<meta>` |
| Construtor de atributos de `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Verificação de suporte do companion | `C34757F6a` + `AbstractC32927EXc` | allowlist de tipos e filhos |
| Parsers de spec de entrada | `C33474Ehg` (status / regular), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | extração de atributos e filhos |
| Evento WAM de erro | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. O secret por mensagem

### 2.1 Onde fica (found)

`MessageContextInfo` (`C30624DTs`) é o campo **35** de `Message` (`C30628DTw`). Campos relevantes aqui:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | dica de lista de dispositivos (sem relação com o secret) |
| `messageSecret` | **3** | bytes (32) | secret por mensagem |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | duração do add-on (pin: deve ser 0 para desafixar) |
| `botMessageSecret` | **6** | bytes (32) | variante do secret para bot |
| `botMetadata` | **7** | message | contexto do bot |
| `reportingTokenVersion` | **8** | uint32 | versão do reporting token desta mensagem |
| `messageAddOnExpiryType` | **9** | enum | expiração do add-on |
| `messageAssociation` | **10** | message | associação |

O carrier de history sync `WebMessageInfo` (`C30626DTu`) tem seu próprio campo `messageSecret` **49** (found), usado quando mensagens são exportadas para um novo companion (seção 2.4).

### 2.2 Geração (found, condições parcialmente inferred)

O secret é `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). É anexado antes de a mensagem ser serializada:

| Local | Condição |
|-------|----------|
| `C33166Ecf.A06` (preparar envio) | a mensagem não tem secret e pelo menos uma das seguintes: classe de enquete `C13J`; `EZN.A01(msg)` (classe de bot / add-on, com flags de tipo de chat **2200**, **11104**, **19303**); gates por classe de chat: grupo com flag **3143**, lista de transmissão com **3144**, status com **3145**, gate de classe **3146**; `C35201aS.A00` (flag **3142**, chat próprio / bot); mensagem de evento `C213509Ao` |
| `AJ0` (send processor) | a versão do reporting token `C35241aW.A05()` (AB int **8860**, limitada por `AbstractC35301ac.A00`) é diferente de zero e a classe da mensagem não é excluída por `C35241aW.A02` (status, newsletter, classes de add-on selecionadas) |
| `C72h`, `C34455Exe`, `EPA` | objetos de status (`AbstractC34478Ey1.A0R`) recebem um secret novo na criação |
| `C33437Eh4` | mensagem de bot "request welcome", somente quando o chamador pede |
| `C9mW` | mensagem tipo 117, flag **24741**, quando não há nenhum |

Os predicados por trás de `EZN.A01`, `C35201aS.A00` e dos gates `3142`..`3146` não foram totalmente resolvidos; a lista acima diz o que o código verifica, não quais mensagens visíveis ao usuário se qualificam. Mensagens sem secret não podem receber add-ons criptografados deste cliente (seção 9).

### 2.3 Armazenamento local (found)

`C35311ad` grava `message_secret(message_row_id, message_secret)` com semântica de replace (`MessageSecretStore/insertMessageSecret`) e lê a última linha de um `message_row_id`. O FMessage mantém o secret como extra `C35171aP` (`A0L` define, `A0c` obtém, `A0Q` = não vazio). Dois processadores em `AbstractC17240jU` (`C35161aO` e um anônimo) o gravam quando o extra está dirty e o chat se qualifica.

### 2.4 Validação no recebimento e transferência (found)

| Etapa | Comportamento |
|-------|---------------|
| Validador de proto `C33475Ehh.A0V` | `message_secret` deve ter exatamente **32** bytes, código de erro **67**; a variante de bot (`bot_message_secret`, grupo `whatsapp_security`) é validada da mesma forma |
| Criação de enquete `F2N` | copia `messageSecret_` para o novo FMessage (`A0L`) |
| Respostas de pergunta de status `C34838F9e` | mesma cópia para `statusQuestionAnswerMessage` |
| Exportação de history sync `C34388EwZ.A00` | grava o secret armazenado em `WebMessageInfo.messageSecret` (49) |
| Importação de history sync `C34388EwZ.C59` | copia de volta (`A0L`) |
| Comentários `C34387EwY` | reconstrói um `MessageContextInfo` a partir de `WebMessageInfo.messageSecret` para a thread de comentários |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) registra `message_secret_error` **0** = ausente (mapeia para o código de erro 66) ou **1** = tamanho inválido (67) para mensagens que exigem um secret (`AbstractC33322EfC.A00`: tem a flag e não é da classe `C35281aa`).

---

## 3. Derivação de chave por caso de uso

### 3.1 Fórmula (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract com salt zero de 32 bytes (`AbstractC38971i1.A00(ikm, salt)`), depois o loop de expand da RFC 5869. Noções básicas de HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) seção 5.1. A saída de 32 bytes é usada como chave AES-256 (inferred pelo tamanho; a chamada nativa recebe a chave como `byte[]`).

Entradas:

| Entrada | Origem | Observações |
|---------|--------|-------------|
| `originalMessageId` | id da chave do alvo após `ReferentialKeyUtil` (`C43661qB.A03`) ao criptografar; id da chave do proto `targetMessageKey` ao descriptografar | para um alvo editado, é o id da mensagem **original** (log `getOriginalKey`) |
| `targetSender` | autor da mensagem original: remetente armazenado (`C12300aw.A01`) | `UserJid`, portanto sem sufixo de dispositivo (nível de tipo; a forma em string `user@server` é inferred) |
| `modifier` | autor do add-on: JID da própria conta (`C09A.A0G`, um LID, retornado por `CUC()` / `Ash()`) ao enviar, o JID remetente do envelope ao receber | |
| `useCase` | string da 3.2 | sem separador entre os quatro componentes |

O JID próprio é um JID de conta LID (`C14080dr`, servidor `lid`, verificação "Invalid LID"). Tanto `AnonymousClass091.Ash()` quanto `CUC()` retornam o mesmo campo.

### 3.2 Strings de caso de uso (found)

| Caso de uso | Carrier | AAD | Literal Java na 2.26.41.6 |
|-------------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | nenhum | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | nenhum | `F3W` |
| `Event Edit` | `secretEncryptedMessage` tipo 1 | nenhum | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` tipo 2 | nenhum | `F3Y.A00`, somente com a flag **17811** |
| `Poll Edit` | `secretEncryptedMessage` tipo 4 | nenhum | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` tipo 5 | nenhum | `F3Y.A00` |
| `WASA` | caminho de bot (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | dois estágios, 3.3 |
| `Report Token` | chave do reporting token | nativo | sem literal Java; presente em `libwhatsapp.so`, derivado nativamente (3.4) |

### 3.3 Variante bot / WASA (found, detalhes inferred)

Para o caso de uso `WASA` a derivação tem dois estágios e nenhuma string de caso de uso no segundo:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` é o modificador e `jidB` o JID remoto (do chat), que deve ser um `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`); o id é a chave da mensagem atual quando presente, senão a chave do alvo (lambda `C33285Eeb.A03`). Contraparte nativa: `WcmBotMessageSecretAPICreateWithMessageSecret`. Contexto do Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Chave do reporting token (found / inferred)

`C33364Efs.A06` e `C33421Ego` chamam `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: o objeto nativo deriva a chave para o caso de uso de id **5**; o lado Java só repassa as raw strings dos JIDs. A string `Report Token` existe na biblioteca nativa; o mapeamento do id 5 para essa string é inferred. Token e upload: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. Layout do AEAD

| Item | Valor | Nível |
|------|-------|-------|
| Cipher | AES-GCM, nativo (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; descriptografia `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Chave | 32 bytes da seção 3 | found |
| IV | **12** bytes aleatórios por criptografia (`SecureRandom`); a descriptografia rejeita qualquer outro tamanho | found |
| Tag | 16 bytes; a constante 16 é passada nas duas chamadas; a posição (anexada ao ciphertext) é inferred a partir da descriptografia do Baileys | found / inferred |
| AAD | por caso de uso (3.2); `null` quando o provedor é `C34631F1e` | found |
| Plaintext | o proto interno serializado (tabela 5) | found |
| Saída | tripla `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| Resultado vazio | log `encryption values are invalid`, erro `Encryption using iJniBridge failed` | found |

Retry de voto de enquete: se o voto já contém IV e payload (`C30957Dd6.A03` / `A04`), o mesmo ciphertext é reenviado em vez de criptografar de novo (found, ramo legado de `DUA`).

---

## 5. Carriers e plaintexts

| Carrier (campo em `Message`) | Classe | Campos | Plaintext descriptografado |
|------------------------------|--------|--------|----------------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (limpo antes da criptografia), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (bytes repetidos, hashes das opções) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown, 1 going, 2 not going, 3 maybe), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `Message` completa (o corpo do comentário); a forma em plaintext é `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | `Message` completa |
| `reactionMessage` **46** | `DSH` | forma em plaintext | reação simples |
| `conditionalRevealMessage` **120** | n/a | não é o esquema de message-secret (seção 14.1) | mensagens agendadas |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. O valor 3 não existe neste build (`forNumber(3)` retorna null, tratado como desconhecido e rejeitado).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Lado do remetente

### 6.1 Caminho comum (found, `C33285Eeb.A03`)

1. Resolver o FMessage alvo pela chave (`target message not found. Cannot proceed further` -> erro 71).
2. Ler seu secret de `message_secret`; null ou tamanho != 32 -> `message secret missing or invalid` (66).
3. Chave original via `C43661qB.A03` (null -> erro 0). Remetente do alvo via `C12300aw.A01`.
4. Em um chat 1:1 (`C0DZ.A0k(chat)`) o remetente do alvo é convertido para o namespace do modificador: modificador LID e alvo PN -> alvo mapeado de PN para LID; modificador PN e alvo LID -> alvo mapeado de LID para PN. Em grupos não há conversão.
5. Somente Event Response: flag **15791**, chat 1:1 e um modificador de tipo conta -> modificador convertido para PN.
6. IV aleatório de 12 bytes, derivar a chave (3.1), AES-GCM com o AAD do caso de uso.
7. Montar a `MessageKey` externa a partir do remetente do alvo e da chave original (`C32717EOy.A01`); o carrier contém `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 Por carrier (found)

| Carrier | Gate no envio |
|---------|---------------|
| Reação (`DU8.ADr`) | criptografada **somente** se o chat for um grupo (`C0DZ.A0l`) com `group_type == 3` (`C0GQ.A0A`; definido em `CMP` a partir de `isDefaultSubgroup_`, ou seja, um subgrupo padrão de comunidade, interpretação inferred) e a flag de contexto de serialização `A09` for false. Em qualquer outro chat, a `reactionMessage` em plaintext é enviada. `ReactionMessage.key` é anulada antes da criptografia (a chave passa para o `targetMessageKey` externo) |
| Voto de enquete (`DUA.ADr`) | flag **6772** ligada: helper compartilhado, sempre criptografado; desligada: ramo inline legado com a mesma derivação e AAD (remetente do alvo = próprio LID para enquetes próprias, senão o JID derivado da chave do alvo do voto; modificador = próprio LID). `metadata` (`pollNameHash`, `lastEditStanzaId` opcional) é carimbada quando a flag **31593** está ligada |
| Resposta de evento (`DU9.ADr`) | sempre criptografada; o `EventResponseMessage` em plaintext tem `response`, `timestampMs`, `extraGuestCount` |
| Comentário (`F3W.ADr`) | sempre criptografado; o plaintext é a `Message` inteira do comentário; o alvo é a chave pai de `CommentMessageInfo` |
| Edição criptografada por secret (`F3Y.C5S`) | somente quando a mensagem tem informação de edição do tipo `E2Q` e o contexto de serialização não é encaminhado / órfão; `MESSAGE_EDIT` exige adicionalmente a flag **17811** (senão `getUseCase` lança exceção). Para edições de mensagens próprias, duas linhas de log (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) mostram casos enviados como edições simples; a condição completa (flags **37948**, **35457**) foi perdida na decompilação |

Payloads criptografados por secret aninhados são rejeitados nos dois lados (`nested_secret_encrypted_message`).

---

## 7. Lado do receptor

### 7.1 Descriptografia (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (modificador) por carrier: próprio LID quando o envelope é meu; enquete: JID do remetente (`c0df` ou `B4g()`); resposta de evento: usuário do chat em 1:1, senão o usuário do envelope; comentário: somente LID (`C0DZ.A0Y`: tipos 18, 19, 25), um remetente PN falha com erro 0; reação: remetente do envelope somente se for um LID, caso contrário null.

### 7.2 Retry de identidade LID / PN (found estrutura, final inferred)

A primeira tentativa usa os JIDs como recebidos. Em caso de falha, o helper mapeia os dois JIDs para o outro namespace (`C0YH.A0I` LID->PN, `A0F` PN->LID) e tenta uma vez mais; se os dois já eram LID ou o mapeamento está ausente, o resultado é o erro **51** (descriptografia falhou). O final decompilado do retry está parcialmente perdido, então o conjunto exato de pares tentados é inferred. A verificação é a autenticação GCM: um par errado falha, o certo descriptografa.

### 7.3 Pai ausente: órfãos (found)

| Carrier | Comportamento quando o pai não é encontrado ou é um placeholder |
|---------|-----------------------------------------------------------------|
| Reação | FMessage tipo **56** é armazenada com os bytes brutos da `Message` (`DdA(key, 56, ts).A02`); a descriptografia é adiada |
| Voto de enquete | `C30957Dd6.A02 = Message.toByteArray()`; armazenado sem descriptografar |
| Resposta de evento | `Dd7(key, target, bytes, ts)` armazenado sem descriptografar |
| Comentário | placeholder `C34671Zb` com a chave do pai e linha `-1` |
| Edição criptografada por secret | `DeD(MessageOrphan)` com tipo de órfão **5**, motivo **1** (pai ausente) ou **2** (placeholder) |

O replay quando o pai chega é esperado (órfãos são persistidos com os bytes brutos), mas o gatilho do replay não foi rastreado (inferred).

### 7.4 Validação após descriptografar (found)

| Caso | Verificação | Falha |
|------|-------------|-------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` deve ser `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | tipo `POLL_ADD_OPTION` e um segundo campo da stanza igual a `poll_add_option` (campo não resolvido) | `poll_add_option_stanza_invalid` (76) |
| Edição de evento | mensagem interna tipo 92, chave resultante igual à chave externa | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Edição de enquete | interna tipo 66, ambas as mensagens são enquetes, mesmo horário de término e flags, edições de opção consistentes com as opções armazenadas, timestamp não posterior ao horário de término | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Adicionar opção à enquete | interna tipo 137, o pai é uma enquete, chave do alvo igual à chave externa, não posterior ao horário de término | `poll_add_option_past_end_time` |
| Recebimento de edição de enquete | o AB int **24886** deve ser diferente de zero | erro 10016 ("futureproofing") |
| Recebimento de adicionar opção | o AB **25758** deve ser diferente de zero | erro 10017 |
| Voto de enquete | a seleção deve ser válida para a enquete (`AbstractC33199EdC.A02`); timestamp do voto não posterior ao horário de término da enquete | `poll_update_past_end_time`, `invalid poll vote selection` |
| Metadata do voto de enquete | `pollNameHash` + `lastEditStanzaId` verificados contra a enquete armazenada (`C32977EZa.A01`); "unstamped" quando ausente; divergência descarta o voto | `poll_update_tc_drop` |
| Formato do voto de enquete | IV exatamente 12 (`poll_update_invalid_vote_enc_iv`), payload presente, timestamp do remetente presente | erro 11 |
| Resposta de evento | chave, IV (12), payload presentes; o pai deve ser um evento ou uma mensagem de revogação do remetente | `parent message is not event message nor sender revoke` |

---

## 8. Vínculo remetente / alvo

| Vinculado pela chave | Efeito |
|----------------------|--------|
| Id da mensagem original | um ciphertext não pode ser reutilizado em outra mensagem |
| JID do remetente do alvo | não pode ser atribuído a um autor original diferente |
| JID do modificador | não pode ser reproduzido como add-on de outro usuário |
| String do caso de uso | um ciphertext de reação não descriptografa como voto, comentário ou edição |
| AAD (voto de enquete, resposta de evento) | vincula adicionalmente `targetId` e o modificador na tag |

Não vinculados: JID do chat, timestamp, posição do ciphertext na thread, número de add-ons anteriores. O `participant` / `from` do envelope é o que o receptor usa como modificador; ele é autenticado pela sessão E2E, não pelo secret. Qualquer pessoa que possua o secret original (todo participante que recebeu a mensagem original, em um grupo) pode derivar chaves para qualquer modificador; o esquema impede o redirecionamento de alvo pelo relay, não a personificação por membros do grupo (inferred a partir da construção).

---

## 9. Fallbacks de secret ausente (found, salvo indicação)

| Situação | Remetente | Receptor |
|----------|-----------|----------|
| A original não tem secret | a criptografia falha (66); caminho legado de enquete: `invalid message_secret secretSize` | pai presente, secret null: erro **66**, registrado no error reporter com `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` código 0 |
| Secret sem 32 bytes | criptografia rejeitada | erro **67**, código WAM 1 |
| Pai não encontrado | erro de criptografia 71 | armazenado como órfão (7.3) |
| Reação em chat que não é subgrupo padrão | a `reactionMessage` em plaintext é enviada no lugar (sem necessidade de secret) | tratado pelo ramo simples |
| Edição de mensagem sem a flag 17811 | `getUseCase` lança exceção (`unknown message secret encrypted type`, código 0); se o remetente evita o tipo quando a flag está desligada não foi resolvido | mesma exceção |
| Falha ao descriptografar add-on | n/a | o add-on fica oculto / indisponível; nenhum texto de fallback visível encontrado (unknown) |
| Novo companion sem a original | n/a | o history sync carrega o secret em `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | definido em mensagens com informação de edição (12.3) | instrui o receptor a não mostrar placeholder de falha; consumidor da flag não resolvido |

---

## 10. Stanza `<message>`: o que o cliente adiciona

Os filhos de saída são construídos por contribuidores independentes (`InterfaceC35538FaZ`) que se anexam ao construtor de stanza `C33150EcP`.

### 10.1 Atributos (found)

| Atributo | Produtor / consumidor | Valores / significado |
|----------|----------------------|-----------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (a partir do proto): `secretEncryptedMessage` com `EVENT_EDIT` -> `event`, com `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` cai para `text` / `media`; campos de reação (simples ou enc) -> `reaction`; atualização / criação de enquete -> `poll`; `encEventResponseMessage` e evento -> `event` |
| `edit` | specs de recebimento `C33474Ehg` (exige a tag de nó `status`; sua relação com a stanza `<message>` simples não foi resolvida), `C23206A1f` (newsletter); acks `AbstractC33465EhX.A05` | `1`, `7`, `8` em `C33474Ehg`; `3` e `8` na spec de newsletter; os acks o repetem a menos que seja `0` / vazio; ver 10.2 |
| `category` | stanza, acks, retry receipts | `peer` seleciona o caminho de peer message |
| `device_fanout` | `F6M` | `"false"` em retries direcionados one-to-one |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | transporte | identidade / ciclo de vida, não conteúdo |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | parsers de identidade (`AbstractC33466EhY`, `C34763F6g`) | aliases de PN / LID / username |

### 10.2 Valores de `edit`

| Valor | Contexto | Nível |
|-------|----------|-------|
| `1` | edição de uma mensagem enviada (parseado em `C33474Ehg.A0L`) | found |
| `2` | pin no chat: o caminho de recebimento exige a versão de edição interna 2 (`Invalid edited version`) | mapeamento para o atributo inferred |
| `3` | edição de mensagem de newsletter: parseado somente na spec de newsletter (`C23206A1f.A0G`), e `EWW.A01` define a versão de edição 3 quando o chat é uma newsletter (JID tipo 21, servidor `newsletter`) | found (isto resolve o "unknown 3" anterior) |
| `7` | revogação pelo remetente (`C33474Ehg.A0M`) | found |
| `8` | exclusão por admin (`C33474Ehg.A0S`, spec de newsletter `A0H`) | found |
| `0` / vazio | mensagem normal; omitido dos acks | found |

A versão de edição interna (`EWW.A01`) é `1` para chats normais e `3` para newsletters; edições em chats normais também definem a flag de ocultação `decrypt-fail` (12.3).

### 10.3 Filhos diretos (found)

| Filho | Produtor | Significado |
|-------|----------|-------------|
| `enc` | camada de criptografia | ciphertext, ver seção 11 |
| `participants` / `to` | `F6E` e fanout | ciphertexts por dispositivo |
| `device-identity` | `F6B` | identidade de dispositivo assinada |
| `registration` | parser `C33474Ehg.A04` | exatamente 4 bytes |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | no máximo o AB int **20606** por stanza, habilitado por **20605** |
| `cstoken` | `F6G` | token de contato frio |
| `padding` | `F6H` | bytes aleatórios, com tamanho `retryCount × 1571`, flags **8311**, **9209** (`ta_pad` também presente) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (HMAC de 16 bytes), ver [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | seção 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | processador de business `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | nós de flag vazios a partir de um bitmask no construtor: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | parser | categoria binária opaca (status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` em envios para JID tipo 3 (lista de transmissão, inferred), flags **16656** (emitir) e **13537** (valor) |
| `verified_name` | business | certificado de empresa verificada |
| `unavailable`, `bypassed` | parser | nós marcadores; o literal `unavailable` não foi encontrado na 2.26.41.6 (baseado em constante), semântica não verificada aqui |

---

## 11. Nó `<enc>`

### 11.1 Atributos (found, `AbstractC33466EhY.A09`)

| Atributo | Valor | Condição |
|----------|-------|----------|
| `v` | `2` ou `3` | versão do ciphertext (o parser de recebimento aceita `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | mensagem Signal, prekey message, sender key, `frskmsg`, `msmsg` de bot, marcador de plaintext |
| `count` | contagem de retry | omitido quando 0 |
| `mediatype` | ver 11.2 | classificação de mídia / interativa |
| `native_flow_name` | nome do flow | mensagens native-flow |
| `duration` | int >= 0 | localização ao vivo |
| `decrypt-fail` | `hide` | mensagem marcada como ocultável (12.3) |
| `state` | `false` | envios `pkmsg` sob uma flag no carrier de ciphertext |
| `session_type` | `pq` | flag do carrier de sessão pós-quântica |
| `bucket` | string | quando definido no carrier de ciphertext |

Verificações no recebimento (`C33013EaB`): dois nós `<enc>` na mesma mensagem devem concordar em contagem de retry e versão do ciphertext; `enc` em uma newsletter é rejeitado (`Received enc message for newsletters`); `decrypt-fail=hide` é respeitado somente quando a categoria não é `peer` e o predicado de chat `C1ZB.A0L` é false.

### 11.2 Valores de `mediatype` aceitos pela spec (found, 37 entradas)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. Enum de `native_flow_name` (8 entradas): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. Nó `<meta>`

Todos os atributos e filhos são acumulados em `EZV` pelos handlers que `F6K` chama (por classe de mensagem `FXq.AAl`, por add-on `FZH.AAl`) e emitidos como um único `<meta>` (`C33150EcP.A00`). Um acumulador vazio não emite nada.

### 12.1 Classificadores de operação (found)

| Atributo | Valores | Produtor |
|----------|---------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | handlers de enquete |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | handlers de evento |
| `content_type` | `add_on` para a classe de add-on `AbstractC35181aQ` (inclui reações; votos / respostas inferred) em chats onde `C0DZ.A0U` é false; `status_notify` / `add_on` para notificações de status | `F6K` |
| `type` | `scheduled_message` com `st` (segundos, omitido para a classe de mensagem de cancelar agendamento) e filho `<key rkid="...">` (bytes da chave omitidos para essa classe) | `F6K`, conditional reveal |
| `appdata` | string livre de `FZF.AVN()`; editar appdata é rejeitado | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | mensagem de tag de membro `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (e outros) | `AJR` |
| `message_association_type` | token de associação, mais `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` em uploads de status | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | id / JID do pai | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; filho `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, mais strings de ponto de entrada do Meta AI (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` para chats 1:1 sob a flag **36091** (significado não resolvido) | `F6K` |
| `view_once` | `true` para tipos view-once sob a flag **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (mensagem tipo 108) | `F6K` |
| `share_pn` | `true` (mensagem tipo 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | roteamento de bot / thread | `F6K` |

### 12.2 Parseado no recebimento (found)

Entradas de `<meta>` que o cliente lê: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (somente chats de grupo), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (segundos, armazenado em ms), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, e os filhos `mention_source/to`, `mentioned_users/to`. Metas de newsletter acrescentam `admin_profile`, `paid_partnership`, `ai_content` (listados a partir do catálogo anterior; não relidos aqui, não verificados). `deprecated_lid_session` não foi encontrado na 2.26.41.6.

---

## 13. `<biz>`, `<bot>`

### 13.1 `<biz>` (found, `C34748F5r.CM3`)

```xml
<biz native_flow_name="...">                       <!-- or -->
<biz>
  <interactive type="native_flow">
    <native_flow name="..."/>
  </interactive>
  <buttons/> | <list/>
</biz>
<hsm category="..." tag="..."/>                    <!-- sibling, template classification -->
```

O receptor lê o nome do flow (`native_flow_name` ou o `name` aninhado) e depois classifica: `buttons` presente, `list` presente ou native flow; com um nome e um irmão `hsm` ele se torna um template. As falhas de validação se chamam `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: um classificador `biz` que discorda do payload criptografado é uma falha de validação, não um tipo de mensagem diferente. Outros atributos de `biz` lidos em outros pontos: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, filho `quality_control` com `decision_source`.

### 13.2 `<bot>` (found)

Saída (`F6M`): atributos `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, filho `tee_routing` (`tee_routing_token`, `tee_ik_id`). Entrada (`C34747F5q`): `<bot edit="full|...">` padrão `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; sem `<meta target_id>` a mensagem não é tratada como resposta de bot. Detalhes: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Esquemas relacionados que não são message-secret

### 14.1 Conditional reveal (mensagens agendadas)

`conditionalRevealMessage` (campo **120**) usa uma chave de reveal aleatória separada (`<meta type="scheduled_message" st><key rkid>`); o servidor controla o reveal. Sem HKDF a partir de `messageSecret`. Os detalhes internos do protocolo de reveal não foram rastreados (unknown).

### 14.2 Reporting token

`reportingTokenVersion` (campo **8**) e o `<reporting_token>` de 16 bytes usam a chave nativa do caso de uso de id 5 (3.4), não o HKDF em Java. Conteúdo do token: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Verificador de suporte do companion (found)

`CompanionSupportVerifier` (`C34757F6a`, somente em um companion, sob uma flag): mensagens não `peer` são aceitas somente se o `type` estiver em `{text, media, reaction, poll, event}` (ou `pay` com um filho `transaction` / `pay` de remittance) e todo filho direto estiver em `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. Caso contrário, registra `unsupported child node=` / `unsupported message type=` e a mensagem é classificada como não suportada no companion. Um peer broadcast com `participants` em um companion é descartado (`received peer broadcast message on companion-mode, dropping`, nack 415 / 18). O novo filho `cap` e `tctoken` / `cstoken` não estão na lista; onde são tratados antes dessa verificação não foi resolvido. `unavailable` e `participants` seguem seus próprios caminhos.

---

## 16. Feature flags (ids como lidos nos call sites; nomes não resolvidos)

| ID | Tipo | Controla |
|----|------|----------|
| **6772** | bool | voto de enquete: helper compartilhado vs criptografia inline legada |
| **31593** | bool | carimbo de `metadata` do voto de enquete |
| **17811** | bool | caso de uso `Message Edit` (envio e recebimento) |
| **37948**, **35457** | bool | condições para encapsular edições de mensagens próprias |
| **24886** | int | recebimento de edição de enquete (0 = rejeitado, 10016) |
| **25758** | int | recebimento de adicionar opção à enquete (0 = rejeitado, 10017) |
| **15791** | bool | modificador de resposta de evento LID -> PN em chats 1:1 |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | geração de secret por classe de chat |
| **8860** | int | versão máxima do reporting token (geração de secret) |
| **24741** | bool | secret para mensagem tipo 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | filho `cap` e seu valor |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool / int | habilitação do `tctoken` / limite por stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, código-fonte lido, nada testado)

Somente fatos lidos em `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`.

| Tópico | Baileys | Android |
|--------|---------|---------|
| Chave | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | idêntico (3.1) |
| Casos de uso | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, mais `Message Schedule` para o enum 3 | mesmas strings; o valor 3 não está definido na 2.26.41.6 |
| AAD | `id\0modifier` para enquete e evento, vazio para edição / comentário / reação | igual |
| Identidade | tenta candidatos PN e LID de creator e modifier, o GCM autentica o par certo | mesma ideia (7.2) |
| Secret ausente | registra log, emite o update bruto de `encReactionMessage` / `pollUpdateMessage`, sem descriptografar | armazenado como órfão |
| Geração de secret | `randomBytes(32)` para enquete, evento e quando `messageContextInfo.messageSecret` está ausente | 2.2 |
| Chave de reporting | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; reporting ignorado para reações, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | id nativo 5 (3.4) |
| Lado de envio | nenhum remetente para `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` ou `encCommentMessage` foi encontrado nos arquivos lidos | o Android envia os quatro |

Consequência lida no código: o Baileys consegue descriptografar os complementos que recebe, mas os arquivos lidos não contêm criptografia para eles. Não foi pesquisado se existe um helper de envio em outro lugar.

---

## 18. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|----------|
| Erro 11 | IV não tem 12 bytes ou payload vazio / campo ausente | verificar `encIv` (campo 3, ou 2 para `PollEncValue`) |
| Erro 51 | namespace errado do JID de remetente / alvo (PN vs LID), id original errado | tentar os dois namespaces, usar o id da mensagem original (sem edição) |
| Voto em enquete editada falha | o id da chave deve ser o id original da enquete, não o id da última edição | resolver a chave original |
| Comentário de remetente PN falha | a descriptografia de comentário exige um remetente LID | usar o LID |
| Edição de enquete / adicionar opção rejeitada | flags **24886** / **25758** desligadas, ou o `polltype` da stanza discorda de `secretEncType` | enviar `<meta polltype>` e tipo correspondentes |
| Mensagem ignorada em um companion | nó filho ou `type` desconhecido | ficar dentro da allowlist (seção 15) |
| Mensagem `<biz>` não suportada | o classificador discorda do payload | derivar o classificador do payload |

---

## 19. Distinções-chave

| Isto | Não isto |
|------|----------|
| `messageSecret` (por mensagem, aleatório, 32 bytes) | media key, sender key, chave de app-state sync, chave de chamada |
| Chave de caso de uso (HKDF, por alvo / usuário / caso de uso) | o secret em si |
| `secretEncryptedMessage` (encapsula uma `Message` completa) | `encReactionMessage` (encapsula uma `ReactionMessage`) |
| AAD de `Poll Vote` / `Event Response` = id + NUL + modifier | edição / comentário / reação com AAD vazio |
| `targetMessageKey` no carrier externo | `ReactionMessage.key` dentro do plaintext (limpo no envio) |
| `meta polltype` / `event_type` (classificador) | o payload criptografado (conteúdo) |
| atributo de stanza `edit` | `secretEncType` (caso de uso de criptografia) |
| `decrypt-fail="hide"` em `<enc>` | retry receipt / nó `retry` |

---

## 20. Fluxo completo (voto em enquete, 1:1 ou grupo)

```
[Creator]                                            [Server]                      [Voter]
   │ poll creation Message                              │                             │
   │ messageContextInfo.messageSecret = random 32       │                             │
   │ store message_secret[row]                          │                             │
   │ <message type="poll"><meta polltype="creation">────▶────────────────────────────▶ stores secret
   │                                                    │                             │
   │                                                    │      select options (hashes)│
   │                                                    │      secret = store[poll]   │
   │                                                    │      key = HKDF(secret,     │
   │                                                    │        pollId‖creator‖voter │
   │                                                    │        ‖"Poll Vote")        │
   │                                                    │      iv = random 12         │
   │                                                    │      ct = GCM(key, iv,      │
   │                                                    │        PollVoteMessage,     │
   │                                                    │        aad = pollId\0voter) │
   │              <message type="poll"><meta polltype="vote">                         │
   │◀────────────────────────────────────────────────────◀ pollUpdateMessage{key,vote{ct,iv},metadata,ts}
   │ parent found? no -> orphan, keep raw bytes         │                             │
   │ validate end time, enc iv = 12                     │                             │
   │ key = HKDF(secret, pollId‖creator‖voter‖"Poll Vote")                              │
   │ GCM-decrypt, fail -> retry PN/LID pair, else 51    │                             │
   │ check option hashes ⊂ poll options, stamp match    │                             │
   │ apply vote                                         │                             │
```

---

## 21. Unknowns

| Item | Estado |
|------|--------|
| Predicados exatos de `EZN.A01`, `C35201aS.A00`, flags 3142-3146 | gating por classe de chat observado, conjunto visível ao usuário não resolvido |
| Tabela de ids de caso de uso nativos (nomes para ids diferentes de 5 = Report Token) | não lida |
| Posição da tag GCM e tamanho da chave AES | inferred a partir de constantes e do Baileys |
| Condição completa para enviar `MESSAGE_EDIT` próprio encapsulado vs simples (flags 37948, 35457) | o decompilador perdeu o fluxo de controle |
| Significado de `acp="2"`, da flag de serialização `A09`, do segundo campo de stanza de poll-add-option | não resolvido |
| Consumidor de `decrypt-fail="hide"` no envelope parseado | a flag é levada ao envelope, efeito não rastreado |
| Resultado visível ao usuário de um add-on permanentemente indescriptografável | nenhum texto de fallback encontrado |
| `unavailable`, `bypassed`, `deprecated_lid_session` | não reverificado na 2.26.41.6 |
