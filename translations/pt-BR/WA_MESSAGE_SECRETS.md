<!-- src-sha1: b8f7c5d44373d4a7bc19be29e7bd26af81a86f85 -->
# WhatsApp Message Secrets — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** `messageSecret` por mensagem (geração, `MessageContextInfo`, armazenamento local, sincronização de histórico), derivação de chave por caso de uso (HKDF), IV/AAD do AES-GCM, add-ons criptografados (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, edições `secretEncryptedMessage`), vinculação de identidade remetente/alvo e retry LID/PN, órfãos e fallbacks de segredo ausente, extensões da stanza `<message>` (atributos, atributos `<enc>`, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, verificação de suporte de companion), feature flags, comparação com Baileys

---

## 1. O que é (tecnicamente)

Toda mensagem que pode mais tarde receber um acompanhamento criptografado carrega um segredo aleatório de 32 bytes em seu próprio payload criptografado de ponta a ponta (`MessageContextInfo.messageSecret`). Um acompanhamento (reação, voto de enquete, resposta de evento, comentário, edição) é criptografado com uma chave derivada desse segredo, do id da mensagem original, do remetente original e do modificador. O servidor retransmite o acompanhamento como uma mensagem E2E comum mas não pode lê-lo nem movê-lo para outro alvo, usuário ou caso de uso sem quebrar a autenticação GCM. Todas as afirmações são análise estática do APK decompilado; nada foi capturado no wire. Tiers: **found** = lido em código, **inferred** = deduzido do código, **unknown** = não resolvido. Nomes obfuscados foram re-resolvidos na 2.26.41.6 a partir de strings estáveis (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, strings de caso de uso, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

A mesma release também define as extensões da stanza `<message>` (seção 10 em diante): atributos e nós filhos que classificam e roteiam uma mensagem mas não carregam seu conteúdo. Eles são agrupados aqui porque `<meta polltype>` / `<meta event_type>` devem concordar com o payload criptografado por segredo (7.4).

| Entidade | Nome na 2.26.41.6 | Papel |
|--------|----------------|------|
| Helper de cripto (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` criptografar, `A04` decriptar (retry de identidade), `A02` resolução de chave-alvo |
| Carregadores de parâmetro de criptografar/decriptar | `C32833ETl` / `C32854EUg` | dados, remetente, chave-alvo, caso de uso/IV, payload, chaves, remetente |
| Derivação de chave | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, salt zero |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | nativo, tag de 16 bytes |
| Provedores de AAD | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (nenhum) | dados adicionais |
| Gerador de segredo | `AbstractC33322EfC.A01` | `SecureRandom`, 32 bytes |
| Armazenamento de segredo (`MessageSecretStore`) / extra em memória | `C35311ad` (tabela `message_secret`) / `C35171aP` na mensagem `C13G` | persistir e carregar |
| Mapeador de chave original (`ReferentialKeyUtil`) | `C43661qB.A03` | chave da mensagem original não editada |
| Handlers de reação | `DU8` (enviar), ramo `F2P` (receber) | `reactionMessage` / `encReactionMessage` |
| Voto de enquete / resposta de evento / comentário | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Edições criptografadas por segredo (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Criação de enquete/evento (segredo obtido no recebimento) | `F2N` / `F2M` | lê `messageSecret` para dentro do FMessage |
| Proto: contexto / mensagem / chave | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Seletor do `type` da stanza | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Contribuidores de stanza de saída | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` flags, `F69` cap, `F6H` padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | constroem filhos de `<message>` |
| Acumulador de `<meta>` | `EZV` (atributos `A01`, filhos `A00`) | um nó `<meta>` |
| Construtor de atributo `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Verificação de suporte de companion | `C34757F6a` + `AbstractC32927EXc` | allowlist de tipo e filho |
| Parsers de spec entrante | `C33474Ehg` (status/regular), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | extração de atributo e filho |
| Evento de erro WAM | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. O segredo por mensagem

### 2.1 Onde ele vive (found)

`MessageContextInfo` (`C30624DTs`) é o campo **35** de `Message` (`C30628DTw`). Campos relevantes aqui:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | mensagem / int | dica de lista de dispositivo (não relacionada a segredo) |
| `messageSecret` | **3** | bytes (32) | segredo por mensagem |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | vida útil do add-on (pin: deve ser 0 para unpin) |
| `botMessageSecret` | **6** | bytes (32) | variante de bot do segredo |
| `botMetadata` | **7** | mensagem | contexto de bot |
| `reportingTokenVersion` | **8** | uint32 | versão do token de relatório desta mensagem |
| `messageAddOnExpiryType` | **9** | enum | expiração do add-on |
| `messageAssociation` | **10** | mensagem | associação |

O carregador de sincronização de histórico `WebMessageInfo` (`C30626DTu`) tem seu próprio campo `messageSecret` **49** (found), usado quando mensagens são exportadas para um novo companion (seção 2.4).

### 2.2 Geração (found, condições parcialmente inferidas)

O segredo é `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). Ele é anexado antes que a mensagem seja serializada:

| Local | Condição |
|-------|-----------|
| `C33166Ecf.A06` (preparar envio) | a mensagem não tem segredo e pelo menos um de: classe de enquete `C13J`; `EZN.A01(msg)` (classe bot/add-on, com flags de tipo de chat **2200**, **11104**, **19303**); gates de classe de chat: grupo com a flag **3143**, lista de transmissão com **3144**, status com **3145**, gate de classe **3146**; `C35201aS.A00` (flag **3142**, chat próprio/bot); mensagem de evento `C213509Ao` |
| `AJ0` (processador de envio) | a versão de token de relatório `C35241aW.A05()` (AB int **8860**, limitada por `AbstractC35301ac.A00`) é não-zero e a classe da mensagem não é excluída por `C35241aW.A02` (status, newsletter, classes de add-on selecionadas) |
| `C72h`, `C34455Exe`, `EPA` | objetos de status (`AbstractC34478Ey1.A0R`) recebem um segredo novo na criação |
| `C33437Eh4` | mensagem de bot "request welcome", apenas quando seu chamador solicita |
| `C9mW` | tipo de mensagem 117, flag **24741**, quando nenhum está presente |

Os predicados por trás de `EZN.A01`, `C35201aS.A00` e os gates `3142`..`3146` não foram totalmente resolvidos; a lista acima diz o que o código verifica, não quais mensagens visíveis ao usuário se qualificam. Mensagens sem segredo não podem receber add-ons criptografados a partir deste cliente (seção 9).

### 2.3 Armazenamento local (found)

`C35311ad` escreve `message_secret(message_row_id, message_secret)` com semântica de substituição (`MessageSecretStore/insertMessageSecret`) e lê a última linha para um `message_row_id`. O FMessage o mantém como extra `C35171aP` (`A0L` define, `A0c` obtém, `A0Q` = não-vazio). Dois processadores em `AbstractC17240jU` (`C35161aO` e um anônimo) o escrevem quando o extra está sujo e o chat se qualifica.

### 2.4 Validação e transferência do lado do recebimento (found)

| Etapa | Comportamento |
|------|------|
| Validador proto `C33475Ehh.A0V` | `message_secret` deve ter exatamente **32** bytes, código de erro **67**; a variante de bot (`bot_message_secret`, grupo `whatsapp_security`) é validada da mesma forma |
| Criação de enquete `F2N` | copia `messageSecret_` para o novo FMessage (`A0L`) |
| Respostas de pergunta de status `C34838F9e` | mesma cópia para `statusQuestionAnswerMessage` |
| Exportação de sincronização de histórico `C34388EwZ.A00` | escreve o segredo armazenado em `WebMessageInfo.messageSecret` (49) |
| Importação de sincronização de histórico `C34388EwZ.C59` | o copia de volta (`A0L`) |
| Comentários `C34387EwY` | reconstrói um `MessageContextInfo` a partir de `WebMessageInfo.messageSecret` para a thread de comentários |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) loga `message_secret_error` **0** = ausente (mapeia para o código de erro 66) ou **1** = comprimento inválido (67) para mensagens que exigem um segredo (`AbstractC33322EfC.A00`: tem a flag e não é a classe `C35281aa`).

---

## 3. Derivação de chave por caso de uso

### 3.1 Fórmula (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract com um salt zero de 32 bytes (`AbstractC38971i1.A00(ikm, salt)`), depois o loop de expand do RFC 5869. Fundamentos de HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) seção 5.1. A saída de 32 bytes é usada como uma chave AES-256 (inferido pelo comprimento; a chamada nativa recebe a chave como `byte[]`).

Entradas:

| Entrada | Fonte | Notas |
|-------|--------|-------|
| `originalMessageId` | id de chave do alvo após `ReferentialKeyUtil` (`C43661qB.A03`) na criptografia; id de chave do `targetMessageKey` do proto na decriptação | para um alvo editado este é o id da mensagem **original** (log `getOriginalKey`) |
| `targetSender` | autor da mensagem original: remetente armazenado (`C12300aw.A01`) | `UserJid`, então sem sufixo de dispositivo (nível de tipo; a forma string `user@server` é inferida) |
| `modifier` | autor do add-on: JID da própria conta (`C09A.A0G`, um LID, retornado por `CUC()` / `Ash()`) ao enviar, o JID remetente do envelope ao receber | |
| `useCase` | string de 3.2 | sem separador entre os quatro componentes |

O próprio JID é um JID de conta LID (`C14080dr`, servidor `lid`, verificação "Invalid LID"). Tanto `AnonymousClass091.Ash()` quanto `CUC()` retornam o mesmo campo.

### 3.2 Strings de caso de uso (found)

| Caso de uso | Carregador | AAD | Literal Java na 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | nenhum | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | nenhum | `F3W` |
| `Event Edit` | `secretEncryptedMessage` tipo 1 | nenhum | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` tipo 2 | nenhum | `F3Y.A00`, apenas com a flag **17811** |
| `Poll Edit` | `secretEncryptedMessage` tipo 4 | nenhum | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` tipo 5 | nenhum | `F3Y.A00` |
| `WASA` | caminho de bot (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | duas etapas, 3.3 |
| `Report Token` | chave de token de relatório | nativo | nenhum literal Java; presente em `libwhatsapp.so`, derivado nativamente (3.4) |

### 3.3 Variante de bot / WASA (found, detalhes inferidos)

Para o caso de uso `WASA` a derivação tem duas etapas e nenhuma string de caso de uso na segunda:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` é o modificador e `jidB` o remoto (chat) JID, que deve ser um `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`); o id é a chave da mensagem atual quando presente, senão a chave alvo (lambda `C33285Eeb.A03`). Contraparte nativa: `WcmBotMessageSecretAPICreateWithMessageSecret`. Contexto do Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Chave de token de relatório (found/inferred)

`C33364Efs.A06` e `C33421Ego` chamam `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: o objeto nativo deriva a chave para o id de caso de uso **5**; o lado Java só passa strings JID brutas. A string `Report Token` existe na biblioteca nativa; o mapeamento do id 5 para essa string é inferido. Token e upload: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. Formato AEAD

| Item | Valor | Tier |
|------|-------|------|
| Cifra | AES-GCM, nativa (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; decriptação `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Chave | 32 bytes da seção 3 | found |
| IV | **12** bytes aleatórios por criptografia (`SecureRandom`); a decriptação rejeita qualquer outro tamanho | found |
| Tag | 16 bytes; a constante 16 é passada em ambas as chamadas; a posição (anexada ao texto cifrado) é inferida a partir da decriptação do Baileys | found/inferred |
| AAD | por caso de uso (3.2); `null` quando o provedor é `C34631F1e` | found |
| Texto plano | o proto interno serializado (tabela 5) | found |
| Saída | tripla `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| Resultado vazio | log `encryption values are invalid`, erro `Encryption using iJniBridge failed` | found |

Retry de voto de enquete: se o voto já mantém IV e payload (`C30957Dd6.A03` / `A04`) o mesmo texto cifrado é reenviado em vez de recriptografado (found, ramo legado de `DUA`).

---

## 5. Carregadores e textos planos

| Carregador (campo em `Message`) | Classe | Campos | Texto plano decriptado |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (limpo antes da criptografia), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (bytes repetidos, hashes de opção) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 desconhecido, 1 vai, 2 não vai, 3 talvez), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `Message` completo (o corpo do comentário); a forma de texto plano é `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | `Message` completo |
| `reactionMessage` **46** | `DSH` | forma de texto plano | reação simples |
| `conditionalRevealMessage` **120** | n/a | não é o esquema de message-secret (seção 14.1) | mensagens agendadas |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. O valor 3 não existe nesta build (`forNumber(3)` retorna null, tratado como desconhecido e rejeitado).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Lado do remetente

### 6.1 Caminho comum (found, `C33285Eeb.A03`)

1. Resolve o FMessage alvo pela chave (`target message not found. Cannot proceed further` -> erro 71).
2. Lê seu segredo de `message_secret`; nulo ou comprimento != 32 -> `message secret missing or invalid` (66).
3. Chave original via `C43661qB.A03` (nulo -> erro 0). Remetente alvo via `C12300aw.A01`.
4. Em um chat 1:1 (`C0DZ.A0k(chat)`) o remetente alvo é convertido para o namespace do modificador: modificador LID e alvo PN -> alvo mapeado de PN para LID; modificador PN e alvo LID -> alvo mapeado de LID para PN. Em grupos sem conversão.
5. Apenas Event Response: flag **15791**, chat 1:1 e um modificador de tipo-conta -> modificador convertido para PN.
6. IV aleatório de 12 bytes, derivar chave (3.1), AES-GCM com o AAD do caso de uso.
7. Construir o `MessageKey` externo a partir do remetente alvo e da chave original (`C32717EOy.A01`); o carregador mantém `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 Por carregador (found)

| Carregador | Gate no envio |
|---------|--------------|
| Reação (`DU8.ADr`) | criptografada **apenas** se o chat é um grupo (`C0DZ.A0l`) com `group_type == 3` (`C0GQ.A0A`; definido em `CMP` a partir de `isDefaultSubgroup_`, ou seja, um subgrupo padrão de comunidade, interpretação inferida) e a flag de contexto de serialização `A09` é false. Em todo outro chat o `reactionMessage` em texto plano é enviado. `ReactionMessage.key` é zerado antes da criptografia (a chave se move para o `targetMessageKey` externo) |
| Voto de enquete (`DUA.ADr`) | flag **6772** ativa: helper compartilhado, sempre criptografado; desativada: ramo inline legado com a mesma derivação e AAD (remetente alvo = próprio LID para enquetes próprias, senão o JID derivado da chave alvo do voto; modificador = próprio LID). `metadata` (`pollNameHash`, `lastEditStanzaId` opcional) é marcado quando a flag **31593** está ativa |
| Resposta de evento (`DU9.ADr`) | sempre criptografada; o `EventResponseMessage` em texto plano tem `response`, `timestampMs`, `extraGuestCount` |
| Comentário (`F3W.ADr`) | sempre criptografado; o texto plano é o `Message` completo do comentário; o alvo é a chave pai de `CommentMessageInfo` |
| Edição criptografada por segredo (`F3Y.C5S`) | apenas quando a mensagem tem info de edição do tipo `E2Q` e o contexto de serialização não é reenviado/órfão; `MESSAGE_EDIT` adicionalmente precisa da flag **17811** (senão `getUseCase` lança exceção). Para edições de mensagens próprias duas linhas de log (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) mostram casos enviados como edições em texto plano; a condição completa (flags **37948**, **35457**) foi perdida na decompilação |

Payloads criptografados por segredo aninhados são rejeitados em ambos os lados (`nested_secret_encrypted_message`).

---

## 7. Lado do receptor

### 7.1 Decriptação (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (modificador) por carregador: próprio LID quando o envelope é meu; enquete: JID do remetente (`c0df` ou `B4g()`); resposta de evento: usuário do chat em 1:1 senão usuário do envelope; comentário: apenas LID (`C0DZ.A0Y`: tipos 18, 19, 25), um remetente PN falha com erro 0; reação: remetente do envelope apenas se for um LID, senão nulo.

### 7.2 Retry de identidade LID/PN (found a estrutura, final inferido)

A primeira tentativa usa os JIDs como dados. Em caso de falha o helper mapeia ambos os JIDs para o outro namespace (`C0YH.A0I` LID->PN, `A0F` PN->LID) e tenta de novo uma vez; se ambos já eram LID ou o mapeamento está ausente o resultado é erro **51** (decriptação falhou). O final decompilado do retry está parcialmente perdido, então o conjunto exato de pares tentados é inferido. A verificação é autenticação GCM: um par errado falha, o correto decripta.

### 7.3 Pai ausente: órfãos (found)

| Carregador | Comportamento quando o pai não é encontrado ou é um placeholder |
|---------|-----------------------------------------------------------|
| Reação | FMessage tipo **56** é armazenado com os bytes brutos do `Message` (`DdA(key, 56, ts).A02`); a decriptação é postergada |
| Voto de enquete | `C30957Dd6.A02 = Message.toByteArray()`; armazenado não decriptado |
| Resposta de evento | `Dd7(key, target, bytes, ts)` armazenado não decriptado |
| Comentário | placeholder `C34671Zb` com a chave pai e linha `-1` |
| Edição criptografada por segredo | `DeD(MessageOrphan)` com tipo de órfão **5**, motivo **1** (pai ausente) ou **2** (placeholder) |

Reprodução quando o pai chega é esperada (órfãos são persistidos com os bytes brutos) mas o gatilho de reprodução não foi rastreado (inferido).

### 7.4 Validação após decriptação (found)

| Caso | Verificação | Falha |
|------|-------|---------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` deve ser `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | tipo `POLL_ADD_OPTION` e um segundo campo de stanza igual a `poll_add_option` (campo não resolvido) | `poll_add_option_stanza_invalid` (76) |
| Edição de evento | mensagem interna tipo 92, chave resultante igual à chave externa | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Edição de enquete | tipo interno 66, ambas as mensagens são enquetes, mesmo tempo final e flags, edições de opção consistentes com as opções armazenadas, timestamp não posterior ao tempo final | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Adicionar opção de enquete | tipo interno 137, o pai é uma enquete, chave alvo igual à chave externa, não posterior ao tempo final | `poll_add_option_past_end_time` |
| Recebimento de edição de enquete | AB int **24886** deve ser não-zero | erro 10016 ("futureproofing") |
| Recebimento de adicionar opção de enquete | AB **25758** deve ser não-zero | erro 10017 |
| Voto de enquete | a seleção deve ser válida para a enquete (`AbstractC33199EdC.A02`); timestamp do voto não posterior ao tempo final da enquete | `poll_update_past_end_time`, `invalid poll vote selection` |
| Metadado de voto de enquete | `pollNameHash` + `lastEditStanzaId` verificados contra a enquete armazenada (`C32977EZa.A01`); "unstamped" quando ausente; incompatibilidade descarta o voto | `poll_update_tc_drop` |
| Formato do voto de enquete | IV exatamente 12 (`poll_update_invalid_vote_enc_iv`), payload presente, timestamp do remetente presente | erro 11 |
| Resposta de evento | chave, IV (12), payload presentes; o pai deve ser uma mensagem de evento ou de revogação do remetente | `parent message is not event message nor sender revoke` |

---

## 8. Vinculação remetente/alvo

| Vinculado pela chave | Efeito |
|------------------|--------|
| Id da mensagem original | um texto cifrado não pode ser reutilizado em outra mensagem |
| JID do remetente alvo | não pode ser atribuído a um autor original diferente |
| JID do modificador | não pode ser reproduzido como add-on de outro usuário |
| String do caso de uso | um texto cifrado de reação não decripta como voto, comentário ou edição |
| AAD (voto de enquete, resposta de evento) | adicionalmente vincula `targetId` e o modificador à tag |

Não vinculado: JID do chat, timestamp, posição do texto cifrado na thread, o número de add-ons anteriores. O `participant`/`from` do envelope é o que o receptor usa como modificador; é autenticado pela sessão E2E, não pelo segredo. Qualquer pessoa que mantenha o segredo original (todo participante que recebeu a mensagem original, em um grupo) pode derivar chaves para qualquer modificador; o esquema previne o redirecionamento do lado do relay, não a impersonação por membros do grupo (inferido da construção).

---

## 9. Fallbacks de segredo ausente (found salvo indicação)

| Situação | Remetente | Receptor |
|-----------|--------|----------|
| O original não tem segredo | a criptografia falha (66); caminho legado de enquete: `invalid message_secret secretSize` | pai presente, segredo nulo: erro **66**, logado para o relator de erros com `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` código 0 |
| Segredo não tem 32 bytes | criptografia rejeitada | erro **67**, código WAM 1 |
| Pai não encontrado | erro de criptografia 71 | armazenado como órfão (7.3) |
| Reação em um chat que não é subgrupo padrão | o `reactionMessage` em texto plano é enviado em vez disso (sem necessidade de segredo) | tratado pelo ramo em texto plano |
| Edição de mensagem sem a flag 17811 | `getUseCase` lança exceção (`unknown message secret encrypted type`, código 0); se o remetente evita o tipo quando a flag está desativada não está resolvido | mesma exceção |
| Decriptação de add-on falha | n/a | o add-on fica oculto/indisponível; nenhum texto de fallback visível encontrado (unknown) |
| Novo companion sem o original | n/a | a sincronização de histórico carrega o segredo em `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | definido em mensagens com info de edição (12.3) | diz ao receptor para não mostrar um placeholder de falha; consumidor da flag não resolvido |

---

## 10. Stanza `<message>`: o que o cliente adiciona

Filhos de saída são construídos por contribuidores independentes (`InterfaceC35538FaZ`) que anexam ao construtor de stanza `C33150EcP`.

### 10.1 Atributos (found)

| Atributo | Produtor/consumidor | Valores/significado |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (a partir do proto): `secretEncryptedMessage` com `EVENT_EDIT` -> `event`, com `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` cai para `text` / `media`; campos de reação (simples ou enc) -> `reaction`; atualização/criação de enquete -> `poll`; `encEventResponseMessage` e evento -> `event` |
| `edit` | specs de recebimento `C33474Ehg` (exige a tag de nó `status`; sua relação com a stanza `<message>` simples não está resolvida), `C23206A1f` (newsletter); acks `AbstractC33465EhX.A05` | `1`, `7`, `8` em `C33474Ehg`; `3` e `8` na spec de newsletter; os acks o ecoam a menos que `0`/vazio; ver 10.2 |
| `category` | stanza, acks, recibos de retry | `peer` seleciona o caminho de mensagem entre pares |
| `device_fanout` | `F6M` | `"false"` em retries 1-para-1 direcionados |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | transporte | identidade/ciclo de vida, não conteúdo |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | parsers de identidade (`AbstractC33466EhY`, `C34763F6g`) | apelidos de PN/LID/username |

### 10.2 Valores de `edit`

| Valor | Contexto | Tier |
|-------|---------|------|
| `1` | edição de uma mensagem enviada (parseado em `C33474Ehg.A0L`) | found |
| `2` | pin no chat: o caminho de recebimento exige a versão de edição interna 2 (`Invalid edited version`) | mapeamento inferido para o atributo |
| `3` | edição de mensagem de newsletter: parseado apenas na spec de newsletter (`C23206A1f.A0G`), e `EWW.A01` define a versão de edição 3 quando o chat é uma newsletter (JID tipo 21, servidor `newsletter`) | found (isso resolve o antigo "3 desconhecido") |
| `7` | revogação pelo remetente (`C33474Ehg.A0M`) | found |
| `8` | exclusão por admin (`C33474Ehg.A0S`, spec de newsletter `A0H`) | found |
| `0` / vazio | mensagem normal; omitido dos acks | found |

A versão de edição interna (`EWW.A01`) é `1` para chats normais e `3` para newsletters; edições de chat normal também definem a flag de ocultação `decrypt-fail` (12.3).

### 10.3 Filhos diretos (found)

| Filho | Produtor | Significado |
|-------|----------|---------|
| `enc` | camada de criptografia | texto cifrado, ver seção 11 |
| `participants` / `to` | `F6E` e fanout | textos cifrados por dispositivo |
| `device-identity` | `F6B` | identidade de dispositivo assinada |
| `registration` | parser `C33474Ehg.A04` | exatamente 4 bytes |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | no máximo AB int **20606** por stanza, ativado por **20605** |
| `cstoken` | `F6G` | token de contato frio |
| `padding` | `F6H` | bytes aleatórios, `retryCount × 1571` de comprimento, flags **8311**, **9209** (`ta_pad` também presente) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (HMAC de 16 bytes), ver [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | seção 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | processador de business `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | nós de flag vazios a partir de uma bitmask no construtor: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | parser | categoria binária opaca (status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` em envios para JID tipo 3 (lista de transmissão, inferido), flags **16656** (emissão) e **13537** (valor) |
| `verified_name` | business | certificado business verificado |
| `unavailable`, `bypassed` | parser | nós marcadores; literal `unavailable` não correspondido na 2.26.41.6 (baseado em constante), semântica não verificada aqui |

---

## 11. Nó `<enc>`

### 11.1 Atributos (found, `AbstractC33466EhY.A09`)

| Atributo | Valor | Condição |
|-----------|-------|-----------|
| `v` | `2` ou `3` | versão do texto cifrado (o parser de recebimento aceita `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | mensagem Signal, mensagem prekey, sender key, `frskmsg`, bot `msmsg`, marcador de texto plano |
| `count` | contagem de retry | omitido quando 0 |
| `mediatype` | ver 11.2 | classificação de mídia/interativo |
| `native_flow_name` | nome do fluxo | mensagens de native-flow |
| `duration` | int >= 0 | localização ao vivo |
| `decrypt-fail` | `hide` | mensagem marcada como ocultável (12.3) |
| `state` | `false` | envios de `pkmsg` sob uma flag no carregador de texto cifrado |
| `session_type` | `pq` | flag de carregador de sessão pós-quântica |
| `bucket` | string | quando definido no carregador de texto cifrado |

Verificações de recebimento (`C33013EaB`): dois nós `<enc>` em uma mensagem devem concordar na contagem de retry e versão de texto cifrado; `enc` em uma newsletter é rejeitado (`Received enc message for newsletters`); `decrypt-fail=hide` só é respeitado quando a categoria não é `peer` e o predicado de chat `C1ZB.A0L` é false.

### 11.2 Valores de `mediatype` aceitos pela spec (found, 37 entradas)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. Enum `native_flow_name` (8 entradas): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. Nó `<meta>`

Todos os atributos e filhos são acumulados em `EZV` pelos handlers que `F6K` chama (por classe de mensagem `FXq.AAl`, por add-on `FZH.AAl`) e emitidos como um único `<meta>` (`C33150EcP.A00`). Um acumulador vazio não emite nada.

### 12.1 Classificadores de operação (found)

| Atributo | Valores | Produtor |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | handlers de enquete |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | handlers de evento |
| `content_type` | `add_on` para a classe de add-on `AbstractC35181aQ` (inclui reações; votos/respostas inferidos) em chats onde `C0DZ.A0U` é false; `status_notify` / `add_on` para notificações de status | `F6K` |
| `type` | `scheduled_message` com `st` (segundos, omitido para a classe de mensagem de desagendamento) e filho `<key rkid="...">` (bytes de chave omitidos para essa classe) | `F6K`, revelação condicional |
| `appdata` | string livre de `FZF.AVN()`; editar appdata é rejeitado | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | mensagem de tag de membro `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (e outros) | `AJR` |
| `message_association_type` | token de associação, mais `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` em uploads de status | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | id/JID pai | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; filho `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, mais strings de ponto de entrada do Meta AI (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` para chats 1:1 sob a flag **36091** (significado não resolvido) | `F6K` |
| `view_once` | `true` para tipos view-once sob a flag **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (tipo de mensagem 108) | `F6K` |
| `share_pn` | `true` (tipo de mensagem 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | roteamento de bot/thread | `F6K` |

### 12.2 Parseado no recebimento (found)

Entradas de `<meta>` que o cliente lê: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (apenas chats de grupo), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (segundos, armazenado em ms), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, e os filhos `mention_source/to`, `mentioned_users/to`. Metas de newsletter adicionam `admin_profile`, `paid_partnership`, `ai_content` (listados a partir do catálogo anterior; não relidos aqui, não verificados). `deprecated_lid_session` está confirmado ausente a partir da 2.26.45.10: um grep exaustivo sem distinção de maiúsculas/minúsculas em toda a árvore decodificada da 2.26.45.10 e WA Business 2.26.45.7 não encontrou nenhuma correspondência exata ou próxima (`found`); inferido ser uma remoção intencional da flag transicional de migração PN→LID, não uma renomeação (`inferred`).

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

O receptor lê o nome do fluxo (`native_flow_name` ou o `name` aninhado), então classifica: `buttons` presente, `list` presente, ou native flow; com um nome e um irmão `hsm` ele se torna um template. Falhas de validação são nomeadas `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: um classificador `biz` que discorda do payload criptografado é uma falha de validação, não um tipo de mensagem diferente. Outros atributos `biz` lidos em outro lugar: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, filho `quality_control` com `decision_source`.

### 13.2 `<bot>` (found)

Saída (`F6M`): atributos `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, filho `tee_routing` (`tee_routing_token`, `tee_ik_id`). Entrada (`C34747F5q`): `<bot edit="full|...">` padrão `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; sem `<meta target_id>` a mensagem não é tratada como uma resposta de bot. Detalhes: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Esquemas relacionados que não são message-secret

### 14.1 Revelação condicional (mensagens agendadas)

`conditionalRevealMessage` (campo **120**) usa uma chave de revelação aleatória separada (`<meta type="scheduled_message" st><key rkid>`); o servidor controla a revelação. Nenhum HKDF a partir de `messageSecret`. Os internos do protocolo de revelação não foram rastreados (unknown).

### 14.2 Token de relatório

`reportingTokenVersion` (campo **8**) e o `<reporting_token>` de 16 bytes usam a chave nativa de caso de uso id 5 (3.4), não HKDF Java. Conteúdo do token: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Verificador de suporte do companion (found)

`CompanionSupportVerifier` (`C34757F6a`, apenas em um companion, atrás de uma flag): mensagens não-`peer` só são aceitas se o `type` estiver em `{text, media, reaction, poll, event}` (ou `pay` com um filho `transaction`/`pay` de remessa) e todo filho direto estiver em `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. Caso contrário loga `unsupported child node=` / `unsupported message type=` e a mensagem é classificada como não suportada no companion. Uma transmissão entre pares com `participants` em um companion é descartada (`received peer broadcast message on companion-mode, dropping`, nack 415/18). O novo filho `cap` e `tctoken`/`cstoken` não estão na lista; onde são tratados antes desta verificação não está resolvido. `unavailable` e `participants` seguem seus próprios caminhos.

---

## 16. Feature flags (ids como lidos nos pontos de chamada; nomes não resolvidos)

| ID | Tipo | Controla |
|----|------|----------|
| **6772** | bool | voto de enquete: helper compartilhado vs. criptografia inline legada |
| **31593** | bool | marcação de `metadata` de voto de enquete |
| **17811** | bool | caso de uso `Message Edit` (envio e recebimento) |
| **37948**, **35457** | bool | condições para embrulhar edições de mensagem próprias |
| **24886** | int | recebimento de edição de enquete (0 = rejeitado, 10016) |
| **25758** | int | recebimento de adicionar opção de enquete (0 = rejeitado, 10017) |
| **15791** | bool | modificador de resposta de evento LID -> PN em chats 1:1 |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | geração de segredo por classe de chat |
| **8860** | int | versão máxima de token de relatório (geração de segredo) |
| **24741** | bool | segredo para tipo de mensagem 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | filho `cap` e seu valor |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool/int | ativação de `tctoken` / limite por stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, leitura de código, nada testado)

Apenas fatos lidos em `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`.

| Tópico | Baileys | Android |
|-------|---------|---------|
| Chave | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | idêntico (3.1) |
| Casos de uso | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, mais `Message Schedule` para o enum 3 | mesmas strings; o valor 3 não está definido na 2.26.41.6 |
| AAD | `id\0modifier` para enquete e evento, vazio para edição/comentário/reação | mesmo |
| Identidade | tenta candidatos PN e LID do criador e modificador, GCM autentica o par correto | mesma ideia (7.2) |
| Segredo ausente | loga, emite a atualização bruta `encReactionMessage`/`pollUpdateMessage`, sem decriptação | armazenado como órfão |
| Geração de segredo | `randomBytes(32)` para enquete, evento e quando `messageContextInfo.messageSecret` está ausente | 2.2 |
| Chave de relatório | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; relatório pulado para reações, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | id nativo 5 (3.4) |
| Lado de envio | nenhum remetente para `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` ou `encCommentMessage` foi encontrado nos arquivos lidos | o Android envia todos os quatro |

Consequência lida do código: o Baileys consegue decriptar acompanhamentos que recebe mas os arquivos lidos não contêm criptografia para eles. Se existe um helper de envio em outro lugar não foi pesquisado.

---

## 18. Casos de erro

| Sintoma | Causa | Correção |
|---------|-------|-----|
| Erro 11 | IV não tem 12 bytes ou payload vazio/campo ausente | verificar `encIv` (campo 3, ou 2 para `PollEncValue`) |
| Erro 51 | namespace errado de JID remetente/alvo (PN vs. LID), id original errado | tentar novamente ambos os namespaces, usar o id da mensagem original (não editada) |
| Voto para uma enquete editada falha | o id de chave deve ser o id da enquete original, não o id da última edição | resolver a chave original |
| Comentário de remetente PN falha | a decriptação do comentário exige um remetente LID | usar o LID |
| Edição de enquete/adicionar opção rejeitada | flags **24886** / **25758** desativadas, ou `polltype` da stanza discorda de `secretEncType` | enviar `<meta polltype>` e tipo correspondentes |
| Mensagem ignorada em um companion | nó filho ou `type` desconhecido | manter-se na allowlist (seção 15) |
| Mensagem `<biz>` não suportada | classificador discorda do payload | derivar o classificador do payload |

---

## 19. Distinções importantes

| Isto | Não isto |
|------|----------|
| `messageSecret` (por mensagem, aleatório, 32 bytes) | chave de mídia, sender key, chave de sincronização de app-state, chave de chamada |
| Chave de caso de uso (HKDF, por alvo/usuário/caso de uso) | o próprio segredo |
| `secretEncryptedMessage` (embrulha um `Message` completo) | `encReactionMessage` (embrulha um `ReactionMessage`) |
| AAD de `Poll Vote` / `Event Response` = id + NUL + modificador | edição/comentário/reação com AAD vazio |
| `targetMessageKey` no carregador externo | `ReactionMessage.key` dentro do texto plano (limpo no envio) |
| `meta polltype` / `event_type` (classificador) | o payload criptografado (conteúdo) |
| Atributo de stanza `edit` | `secretEncType` (caso de uso de criptografia) |
| `decrypt-fail="hide"` em `<enc>` | recibo de retry / nó `retry` |

---

## 20. Fluxo completo (voto de enquete, 1:1 ou grupo)

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

## 21. Incertezas

| Item | Estado |
|------|-------|
| Predicados exatos para `EZN.A01`, `C35201aS.A00`, flags 3142-3146 | gate por classe de chat visto, conjunto visível ao usuário não resolvido |
| Tabela nativa de id de caso de uso (nomes para ids além de 5 = Report Token) | não lida |
| Posição da tag GCM e tamanho da chave AES | inferido de constantes e do Baileys |
| Condição completa para enviar `MESSAGE_EDIT` própria embrulhada vs. simples (flags 37948, 35457) | o decompiler perdeu o fluxo de controle |
| Significado de `acp="2"`, flag de serialização `A09`, segundo campo de stanza de adicionar-opção-de-enquete | não resolvido |
| Consumidor de `decrypt-fail="hide"` no envelope parseado | flag carregada para o envelope, efeito não rastreado |
| Resultado visível ao usuário de um add-on permanentemente não-decriptável | nenhum texto de fallback encontrado |
| `unavailable`, `bypassed` | não re-verificados na 2.26.41.6 |
| `deprecated_lid_session` | confirmado ausente a partir da 2.26.45.10 (grep exaustivo, árvores WhatsApp e WA Business); remoção vs. renomeação é `inferred`, não comprovado |
