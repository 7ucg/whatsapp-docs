<!-- src-sha1: abf07b893763b0d9ab0f43cb7e9b4dab51809e14 -->
# WhatsApp TCToken & CSToken — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** TCToken e CSToken — o que são, como funcionam, internos do APK Android, implementação no Baileys

---

## 1. Visão geral: o que são esses tokens?

| Token | Nome completo | Quem emite | Quando é usado | Finalidade |
|-------|-----------|--------------|-----------|---------|
| **tctoken** | Trusted Contact Token | Servidor WA | Contato "quente" (relação existente) | Comprova que remetente e destinatário têm contato prévio — atestado anti-spam |
| **cstoken** | Cold-Start Token (fallback do NCT) | Cliente (HMAC-SHA256, found no Java do Android) | Contato "frio" (sem tctoken armazenado) | Sinal anti-spam de fallback quando não existe tctoken |

**Regra central (found):** Na stanza de mensagem 1:1, o `cstoken` só é anexado quando o store não contém nenhum tctoken válido para o destinatário (`NctTokenMessageSendStanzaContributor/ skipped - tctoken present`). O `tctoken` é anexado por um contributor separado (`PrivacyTokenMessageSendStanzaContributor`).

Ambos os tokens são sinais anti-spam. O que o servidor faz com eles não é visível a partir do cliente (inferred: limitação de spam / de novos chats, ver `NewChatMessageCappingAsyncInit` como gatilho do salt).

Todos os tokens estão no nível de evidência **found** (leitura estática no JADX da 2.26.41.6), salvo quando marcados como inferred / not re-verified. Nada foi tested em runtime.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 O que é

Um token binário emitido pelo servidor que atesta uma relação de confiança entre dois JIDs. O servidor o gera e distribui. O cliente o armazena e o reenvia. Os bytes do token são opacos para o cliente (dados assinados / algoritmo: unknown).

### 2.2 Como é solicitado / renovado

**Job:** `GeneratePrivacyTokenJob` — nome do job `"generate-tc-token"`. Ele não carrega um token: pede ao servidor que (re)emita um (ver 2.4).

**Manager:** `PrivacyTokenSendManager` (`C230709y3`)

**Lógica de gatilho (found):**
- Pontos de entrada `C230709y3.A01(C14080dr, UserJid)`, `A02(UserJid)`, `A04(UserJid)`; `A05` é um conjunto de dedup de requisições em andamento (`A03` remove dele).
- `A04`: baseado em buckets. A feature flag **996** = tamanho do bucket em segundos (<= 0 registra "Bad bucket configuration" e recua para agora − 15724800 s = 182 dias). O job é ignorado se o timestamp armazenado cair no bucket atual ou em um posterior.
- A chave de SharedPrefs `"privacy_token_last_batch_time_sec"` (lida em `A04` e em `AHP`) registra o horário do último batch. A flag **4063** (int) é um offset de bucket usado junto com ela e com o timestamp de emissão real.
- A flag **14303** (bool) seleciona como o JID é normalizado (`A00`): ligada, `PrivacyTokenStore.A0L` (mapeamento PN → LID); desligada, LID → PN via o JID mapper. A flag **15491** (bool) desativa de forma similar a busca dupla PN/LID no store (`A02`, `A0Q`).

**Validação de frescor (found):**
```java
// C14820fK.A0Y(UserJid)  — token for sending
C9oI c9oI = A0M(userJid);
if (c9oI == null || c9oI.A00 < this.A04.A02()) return null;  // expired or missing
return c9oI.A01;
```
Gate de expiração `C14830fL` (TokenBucketValidity):
- `A02()` (tokens recebidos) = `A00(len=flag 865, validBuckets=flag 909)`
- `A01()` (validade do timestamp de envio) = `min(A00(flag 996, flag 997), A02())`
- `A00(len, n)` = `max((now/len − (n−1)) * len, now − 15724800)` (15724800 s = 182 dias, piso rígido).

### 2.3 Armazenamento

**Tabelas do banco (`wa.db`), criadas por `C23627AHs` / `C23628AHt` (found):**

```sql
-- Incoming tokens (received from contacts)
CREATE TABLE wa_trusted_contacts (
  jid                         TEXT PRIMARY KEY,
  incoming_tc_token           BLOB,
  incoming_tc_token_timestamp LONG
);
CREATE INDEX incoming_tc_token_timestamp_index ON wa_trusted_contacts (incoming_tc_token_timestamp);

-- Outgoing token tracking
CREATE TABLE wa_trusted_contacts_send (
  jid                     TEXT PRIMARY KEY,
  sent_tc_token_timestamp LONG,
  real_issue_timestamp    LONG
);
CREATE INDEX sent_tc_token_timestamp_index ON wa_trusted_contacts_send (sent_tc_token_timestamp);
CREATE INDEX sent_real_issue_timestamp_index ON wa_trusted_contacts_send (real_issue_timestamp);
```
(Os tipos de coluna de `jid` / chave primária não aparecem nas duas classes de schema lidas; a coluna `jid` é usada como chave em todas as queries. Os tipos exatos do DDL são inferred.)

**Storage manager:** `PrivacyTokenStore` (`C14820fK`), acesso ao DB via `C14840fM`
- Cache em memória: `C12420b9(10, "privacytokendatacache")`
- Métodos principais:
  - `A0P(UserJid, byte[], long)` — armazena o token recebido; só sobrescreve se o novo timestamp for mais recente ("UPDATE_RECEIVED_TOKEN_IF_NEWER")
  - `A0Y(UserJid)` — bytes do token para envio (null se expirado)
  - `A0M(UserJid)` — lê token + timestamp
  - `A0O(UserJid)` / `A0N(UserJid)` — `(timestamp, real_issue_timestamp)` do lado de envio (em cache; `A0O` descarta entradas mais antigas que `A04.A01()`)
  - `A0V(UserJid, long)` / `A0W(UserJid, long)` — atualizam o timestamp de envio (`A0V` também zera `real_issue_timestamp`)
  - `A0X(UserJid, Integer)` — verificação de recência da emissão real usando as flags **865** e **3802** / **22012**
  - `A0U()` — popula o cache (chamado por `NewChatMessageCappingAsyncInit` ao ir para foreground)

**Tipos de dados:** `C9oI` = `(A00=timestamp, A01=byte[] token)`; `C220519e9` = `(A00=sent timestamp, A01=Long real_issue_timestamp)`.

### 2.4 Stanzas XMPP

**Requisição de saída (found, `GeneratePrivacyTokenJob.A0M`)** — enviada ao JID do servidor (`C19380nJ.A00`), não ao contato. Não carrega bytes de token; nomeia o contato, o tipo e o timestamp armazenado:

```xml
<iq id="[id]" to="[server]" type="set" xmlns="privacy">
  <tokens>
    <token jid="[contact-jid]" type="trusted_contact" t="[stored-timestamp]"/>
  </tokens>
</iq>
```

Enviada via `A0W(callback, node, id, 299, 32000L)` (`C10140Tq`, `MessageClient`): timeout de **32.000 ms** (found). `299` é o int do tipo de requisição IQ: `A0A` o registra como `MessageClient/sendIqWithCallbackInternal ... type=` e o guarda junto com o callback pendente (found). É um id por tipo de requisição compartilhado por muitos pontos de chamada de IQ (o mesmo slot recebe valores como 1, 2, 14, 114, 237, 254, 264, 415), não uma feature flag. Qual valor nomeia qual requisição não está listado no cliente. Retry do job: `A0O` tenta de novo, a menos que o código do nó de erro seja 4xx. O job aborta ("Token timestamp ... missing or too old to send") se nenhum timestamp de token armazenado for válido.

**Entrada (found, `C1S0` case 4888, handler `X.0vv`)** — registrada para o dictionary token **234** (`"privacy_token"`, tabela `AbstractC32331E9w`):

```xml
<notification from="[contact-jid]" sender_lid="[lid]?" t="[t]">
  <tokens>
    <token type="trusted_contact" t="[unix-timestamp]">[binary-token-bytes]</token>
  </tokens>
</notification>
```
Somente filhos com `type="trusted_contact"` são armazenados; conteúdo ausente lança "required token element to contain data". A chave do store é `sender_lid` se presente, senão `from`. `t` recorre ao `t` do pai. Consulta de timestamp via `A0P`, que ignora tokens que não sejam mais recentes.

**Anexo do tctoken na saída (found)** — bytes do token `1..120` vindos de `PrivacyTokenStore.A0Y`:

| Onde | Classe | Formato |
|-------|-------|-------|
| Stanza de mensagem 1:1 | `PrivacyTokenMessageSendStanzaContributor` (`F6I`) | filho `<tctoken>[bytes]</tctoken>`; se ausente mas esperado, registra `expected token, but missing` e reporta o motivo `C99E.A07`. A flag **20605** alterna para o user JID do dispositivo |
| Fanout multi-device | `AbstractC33466EhY.A01` | `<tctoken>` anexado uma vez por usuário dentro do primeiro nó `<to jid=...>` de dispositivo; limitado pela flag **20605** (bool) e pela flag **20606** (máx. de usuários por stanza) |
| IQ de foto de perfil `w:profile:picture` | `C197098a4.A00` | filho `<picture ...><tctoken>` |
| Presence subscribe | `HandlerThreadC21920sG` case 12 / `C18320lY.A07` | `<presence type="subscribe"><tctoken>` |

### 2.5 Integração com GraphQL

O token armazenado é anexado como contexto adicional em vários inputs GraphQL:

```java
// BizIntegritySignalsGraphQLFetcher / IntegrityFeaturesContextFetcher / C229259vZ / C23694AKh / C20L.A0M
node = GraphQlCallInput("tctoken", base64(token));   // string field
node.put("timestamp", String.valueOf(c9oI.A00));
query_input.put("privacy_token", node);
```

Campos: `tctoken` (token, codificado em Base64 / string), `timestamp`, aninhados em `privacy_token`. Chamadores na 2.26.41.6: BizIntegritySignals, IntegrityFeaturesContext (`use_case INTEGRITY_FEATURES_CONTEXT`), `C229259vZ`, `C23694AKh`, `C20L`.

### 2.6 Definição do proto

Não está em uma mensagem `JidGroupInfo`: não existe classe com esse nome na 2.26.41.6. Os campos do token persistido estão no proto `Conversation` (`BD1`, `id` = 1, `messages` = 2) (found, constantes `*_FIELD_NUMBER`):

| Campo | Número | Tipo |
|-------|--------|------|
| `tcToken` | **21** | bytes |
| `tcTokenTimestamp` | **22** | int64 |
| `contactPrimaryIdentityKey` | **23** | bytes |
| `tcTokenSenderTimestamp` | **28** | int64 |

A afirmação da 2.26.26.4 `JidGroupInfo.tcToken = 8` / `contactPrimaryIdentityKey = 9` não vale para esta build.

---

## 3. CSToken / NCT Token (Cold-Start Token)

### 3.1 O que é

Um **HMAC calculado pelo cliente** sobre a string do JID do destinatário, com chave em um salt de toda a conta (`nctSalt`). É o fallback quando não existe tctoken.

**Fórmula (found, Android `AbstractC38971i1.A00(data, key)`):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8(recipientJid.toString()))
```
Saída: 32 bytes, raw. O código apenas verifica que a string não é vazia (log: `NctTokenGenerator/ recipient LID is empty`), o que sugere que o destinatário é um LID (inferred). A forma exata de entrada `<user>@lid` é uma afirmação exclusiva do WA Web vinda do relatório da 2.26.26.4; não se aplica ao Android e não é verificável a partir do APK.

### 3.2 NctSalt — de onde vem

O salt é gerado localmente no dispositivo primário e distribuído aos companions via **App-State-Sync** e **HistorySync**.

**Geração (found, `NctSaltProvider` = `C67592to.A00()`):**
```java
byte[] salt = loadFromSharedPrefs();            // C2X8.A04()
if (salt == null) {
    if (companionDevice) return null;           // "skipped - companion device"
    salt = new byte[32]; SecureRandom.nextBytes(salt);
    C2X8.A03(salt);                             // persist
    putLong("nct_salt_last_sync_ts", 0L);
}
```
Armazenamento `C2X8`: chave de SharedPrefs `"nct_salt"`, Base64 (`NO_WRAP`). Ou seja, a origem é um `SecureRandom` local no primário (found), não gerado pelo servidor.

**Gatilho (found, `NewChatMessageCappingAsyncInit` = `C2AE`)**: ao ir para foreground / async-init:
- Flag **24915** (bool): habilita a criação e a sincronização do NCT salt.
- Se `nct_salt_last_sync_ts == 0` ou a flag **26897** (int, segundos) > 0 e o tempo decorrido >= esse intervalo: grava o novo `nct_salt_last_sync_ts` e agenda um push do SyncD (`C3MD` case 36 → `SyncdUpdateHelperImpl/syncNctSalt`).

**Mutação de sync (found, `NctSaltSyncMutation` = `C52032Bk`)**: carrega o `byte[]` do salt raw, ação `EnumC24865AnN.A0x` (`"NctSaltSyncAction"`, chave `"nct_salt_sync"`), embrulhada no campo **80** de `SyncActionValue`. Enviada aos companions via `C12440bB.A0U/A0O`.

**Recebimento no companion (found, `NctSaltSyncMutationHandler` em `C0XG`)**: em um companion, `A0S` armazena o salt via `C2X8.A03` ("Received NCT salt from primary, storing"). Handler habilitado pela flag **25253** (bool).

**HistorySync (found, `CMP`)**: `HistorySync.nctSalt` (`C25838BCy.nctSalt_`, bit de presença 512) é armazenado via `C2X8.A03` ("stored NCT salt from history sync"). Número do campo **19** (`C25838BCy.NCT_SALT_FIELD_NUMBER`, found).

### 3.3 Campos de proto

```protobuf
// NctSaltSyncAction (C49554LrH): single field "salt" (ByteString)
message NctSaltSyncAction {
  bytes salt = 1;               // found: the only field; size/serialise helpers are called with tag 1 (C49650Lsp case 28)
}

// SyncActionValue (C49639Lse)
message SyncActionValue {
  NctSaltSyncAction nctSaltSyncAction = 80;  // found: NAq.A03(C49554LrH.A00, nct_salt_sync_action, 80)
}

// HistorySync (C25838BCy)
message HistorySync {
  bytes nctSalt = 19;           // found: NCT_SALT_FIELD_NUMBER = 19
}
```

DB: a coluna `"nct_salt"` está registrada no schema do `wa.db` (`C09E`, entrada `C33501Un("nct_salt", ...)`). O relatório da 2.26.26.4 atribuía `nctSalt = 12` a `ConversationThreadInfo`; não existe classe com esse nome nem campo `nctSalt` fora do HistorySync na 2.26.41.6 (`nctSalt_` está apenas em `C25838BCy`, número 19; `Conversation` `BD1` não tem campo de salt).

### 3.4 Cálculo do HMAC e stanza (Android vs Web)

| Aspecto | Android 2.26.41.6 | WA Web (Web-only, não se aplica ao Android; não verificável a partir do APK) |
|--------|------------------|--------|
| Sync do salt (NctSaltSyncAction) | Implementado (campo 80) | Sim |
| Armazenamento do salt | SharedPrefs `"nct_salt"` | IndexedDB `"WAWebNctSalt"` |
| Cálculo do HMAC-SHA256 | **Found em Java** (`AbstractC38971i1`, `javax.crypto.Mac`) | JavaScript |
| Injeção do token na stanza | **Found em Java** (`NctTokenMessageSendStanzaContributor` = `F6G`) | nó `<cstoken>` |

**Contributor da stanza (found, `F6G.ASY`)**, em ordem:
```
flag 24941 off                    → nothing
recipient not a 1:1 user JID      → skip ("not a 1:1 user JID")
flag 18639 on and recipient is GUEST_E2EE → skip ("guest recipient")
PrivacyTokenStore.A0Y(user) != null → skip ("tctoken present")
recipient string empty            → log "recipient LID is empty", fail
salt == null                      → log "no salt available", fail
else  <cstoken>[32 bytes]</cstoken> appended to the message stanza
```
Qualquer exceção é capturada e registrada (`skipping cstoken due to ...`); o envio continua.

```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

Flag **24941** (bool) = gate de envio do CSToken no Android; **18639** (bool) = exclusão de destinatário guest.

---

## 4. Comparação dos tokens

| | TCToken | CSToken |
|-|---------|---------|
| Emitido por | Servidor WA | Cliente (HMAC) |
| Algoritmo | Definido pelo servidor (binário opaco) | HMAC-SHA256 |
| Material de chave | Gerado pelo servidor | `nctSalt` (`SecureRandom` local, sincronizado via App-State / HistorySync) |
| Dado assinado | Desconhecido (opaco) | `utf8(recipient JID string)` (forma LID inferred) |
| Existe quando | Contato prévio estabelecido, não expirado | Quando existe salt e não há tctoken válido |
| Prioridade | Primeiro (tctoken vence) | Somente fallback |
| Stanza | filho `<tctoken>` na mensagem / nó `<to>` / IQ de foto / presence; IQ de requisição `xmlns="privacy"` ao servidor | filho `<cstoken>` na mensagem |
| GraphQL | Enviado em várias queries de integridade | Não visto no GraphQL |
| Armazenamento | `wa_trusted_contacts` (+ `_send`) no DB | SharedPrefs `"nct_salt"` |
| Por destinatário | Sim (um por JID) | Não (um salt, calculado por destinatário) |

---

## 5. Implementação no Baileys

Tudo nesta seção é orientação de implementação (inferred a partir dos fatos de protocolo acima), não um artefato decompilado. Os formatos de stanza foram ajustados para a 2.26.41.6; o TypeScript não foi tested.

### 5.1 TCToken

**Recebimento e armazenamento:**
```ts
// Incoming tokens arrive as a notification, not an IQ set
// <notification from=jid [sender_lid=lid]><tokens><token type="trusted_contact" t=ts>bytes</token></tokens></notification>
sock.ws.on('CB:notification,type:privacy_token', async (node) => {
  const tokens = getBinaryNodeChild(node, 'tokens')
  if (!tokens) return
  for (const tk of getBinaryNodeChildren(tokens, 'token')) {
    if (tk.attrs.type !== 'trusted_contact') continue
    const jid = node.attrs.sender_lid || node.attrs.from
    const timestamp = parseInt(tk.attrs.t || node.attrs.t)
    if (tk.content) {
      await authState.keys.set({ 'tc-token': { [jid]: { token: Buffer.from(tk.content as Uint8Array), timestamp } } })
    }
  }
})
// Only overwrite when the new timestamp is newer (Android: UPDATE_RECEIVED_TOKEN_IF_NEWER)
```
(O valor do atributo `type` da notification usado no nome do evento é inferred; o handler do Android é indexado pelo dictionary token 234.)

**Envio com tctoken:** anexe os bytes armazenados como filho `<tctoken>` da stanza de mensagem (1..120 bytes), e não como um IQ separado:
```ts
const stored = (await authState.keys.get('tc-token', [recipientJid]))[recipientJid]
if (stored && !isExpired(stored.timestamp)) {
  stanza.content.push({ tag: 'tctoken', attrs: {}, content: stored.token })
}
```

**Renovação (IQ de requisição, formato found no Android):**
```ts
await sock.query({
  tag: 'iq',
  attrs: { type: 'set', xmlns: 'privacy', to: S_WHATSAPP_NET },
  content: [{ tag: 'tokens', attrs: {}, content: [{
    tag: 'token', attrs: { jid: contactJid, type: 'trusted_contact', t: String(storedTimestamp) }
  }]}]
})
```

### 5.2 CSToken

**Captura do nctSalt a partir do App-State-Sync:**
```ts
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    authState.keys.set({ 'nct-salt': { default: Buffer.from(nctSaltAction.salt) } })
  }
}
```
Um cliente de dispositivo primário, em vez disso, criaria 32 bytes aleatórios por conta própria (como faz o `NctSaltProvider`) e enviaria a mutação.

**Cálculo e anexo do cstoken:**
```ts
import { createHmac } from 'crypto'

async function buildCsTokenNode(recipientJid: string, authState: AuthenticationState, tcTokenBuffer?: Buffer) {
  if (tcTokenBuffer?.length) return null          // tctoken takes priority
  const salt = (await authState.keys.get('nct-salt', ['default']))['default']
  if (!salt || !recipientJid) return null
  const cs = createHmac('sha256', salt).update(Buffer.from(recipientJid, 'utf8')).digest() // 32 bytes
  return { tag: 'cstoken', attrs: {}, content: cs }
}
```
`recipientJid` = a string que o Android passa (`Jid.toString()` do destinatário 1:1); o uso da forma LID é inferred.

**Stanza resultante:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 Fluxo completo de envio

```
relayMessage(jid, msg)
    │
    ▼
is 1:1 user JID? → NO → skip token attachment
    │ YES
    ▼
valid tc-token in store for this JID?
    │
    ├── YES → <tctoken> child in stanza, no cstoken
    │
    └── NO (cold contact)
            │
            ▼
        load nct-salt → missing → log "no salt" + skip
            │ salt available
            ▼
        cstoken = HMAC-SHA256(salt, utf8(recipient JID string))
        attach <cstoken> node to message stanza
```

### 5.4 Proto do NctSaltSyncAction (patch de proto do Baileys)

Adicione ao seu proto, se ainda não estiver presente:
```protobuf
message NctSaltSyncAction {
  bytes salt = 1;
}

// In SyncActionValue:
NctSaltSyncAction nctSaltSyncAction = 80;
```

---

## 6. Gating / Feature Flags

| Flag | Valor | Controla |
|------|-------|---------|
| **24915** | bool | Criação + sync do NCT salt habilitados (`C2AE`) |
| **26897** | int (segundos) | Intervalo mínimo entre re-syncs do salt |
| **24941** | bool | Contributor de stanza do CSToken ligado/desligado (`F6G`) |
| **18639** | bool | Ignorar cstoken para destinatários GUEST_E2EE |
| **25253** | bool | Habilita `NctSaltSyncMutationHandler` |
| **996** | int (segundos) | Tamanho do bucket do token enviado (gatilho do job, `C230709y3.A04`; também `C14830fL.A01`) |
| **997** | int | Quantidade de buckets válidos do token enviado (`C14830fL.A01`) |
| **865** / **909** | int | Tamanho do bucket / quantidade de buckets válidos do token recebido (`C14830fL.A02`) |
| **4063** | int | Offset de bucket na verificação de reemissão em `A04` |
| **3802** / **22012** | int | Quantidade de buckets válidos em `A0X` (recência da emissão real) |
| **20605** | bool | tctoken nos nós `<to>` por dispositivo; seleção do user JID do dispositivo em `F6I` |
| **20606** | int | Máx. de usuários com `<tctoken>` por stanza de fanout |
| **14303** / **15491** | bool | Comportamento de normalização PN/LID no manager / store |
| `wa_nct_token_send_enabled` | AB-prop (Web) | Gate de envio do CSToken exclusivo do WA Web; não se aplica ao Android (string ausente do APK; o gate do Android é a flag 24941) |

A semântica das flags é lida a partir do uso; os valores reais no servidor são unknown.

---

## 7. Casos de erro e o que observar

| Sintoma | Causa | Correção |
|---------|-------|-----|
| Nenhum cstoken anexado, envio normal | tctoken presente, flag 24941 off, destinatário guest ou não 1:1 | Esperado (strings de log do Android em 3.4) |
| Log do Android `NctTokenGenerator/ no salt available` | Sem salt no SharedPrefs e o dispositivo é um companion (não pode criar) | Aguardar NctSaltSyncAction / HistorySync |
| Log do Android `recipient LID is empty` | String de JID vazia passada ao gerador | Garantir que o JID do destinatário seja resolvido |
| Erro `463` do servidor após o envio | Formato da string LID errado | (2.26.26.4, not re-verified; sem handler de 463 nos caminhos de envio de mensagem, `F6G`, `AbstractC38971i1` ou job de privacy-token da 2.26.41.6. O único ramo de 463 em nível de app encontrado é o `onError` de criação de grupo em `NewGroup`, não relacionado) |
| `GeneratePrivacyTokenJob` falha | 4xx do servidor não sofre retry; outros erros sofrem retry | Solicitar novamente após a virada do bucket |
| Token armazenado ignorado | Mais antigo que `C14830fL.A02()` ou bucket expirado | Aguardar nova notification `privacy_token` |

---

## 8. Distinções principais

- **tctoken** ≠ **privacy_token** no nível de nomenclatura: `privacy_token` é o campo aninhado do GraphQL, o dictionary token do XMPP (234) e o namespace `xmlns="privacy"`; `tctoken` é o nome do filho na stanza, o campo string do GraphQL e o campo do proto. O mesmo token subjacente em contextos diferentes.
- **ACSToken** — o Android tem um objeto de configuração de ACS token (`C31991Nz`: `docId`, `graphQlUrl` = `https://acs.whatsapp.com/graphql`, `surface`, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`) e `hasAcsToken()` em uma interface relacionada (found). A descrição "Privacy Pass blind tokens para crédito de Status/Channels" e o nome `WAACSTokenUtils` são afirmações exclusivas do WA Web vindas da 2.26.26.4 (não se aplicam ao Android, não verificadas). Nenhuma ligação com o caminho de envio de tctoken/cstoken encontrada.
- **counter_abuse_token** — metadado de ACK do servidor no mobile (string presente na 2.26.41.6: `C37961fH`, `C13X`, coluna de DB em `C09550Rf`). Não é um token construído pelo remetente.
- **nctSalt** é de toda a conta (mesmo salt para todos os destinatários). A diferenciação por destinatário acontece na entrada do HMAC (string do JID do destinatário).
- O IQ `xmlns="privacy"` é uma **requisição ao servidor** que carrega apenas `jid`/`type`/`t`, não um transporte para os bytes do token; os bytes do token trafegam em filhos `<tctoken>` e chegam via notification.

---

## 9. Mudanças vs 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| Send manager | `C73O` | `C230709y3` (pontos de entrada A01/A02/A04 mais o conjunto em andamento A05) |
| Token store / cache | `C07730Zd` / `C07760Zg` | `C14820fK` / `C12420b9` "privacytokendatacache" |
| Tipo de dado do token | `C151666s4` | `C9oI` (token+ts); novo `C220519e9` (sent ts + real_issue ts) |
| Gate de expiração | `C07740Ze.A02()` | `C14830fL.A02()` (flags 865/909; piso de 182 dias); lado de envio A01 (996/997) |
| Nomes de tabela / coluna | `wa_trusted_contacts(_send)` | inalterado; mais 3 índices found |
| Flag 996 / 24915 / 26897 | listadas | inalteradas; muitas flags novas found (ver 6) |
| Chaves de SharedPrefs | `privacy_token_last_batch_time_sec`, `nct_salt`, `nct_salt_last_sync_ts` | inalteradas |
| Formato do IQ tc de saída | `<trusted_contact jid type t><token>bytes</token></trusted_contact>` para o destinatário | `<tokens><token jid type="trusted_contact" t/></tokens>` para o servidor, sem bytes de token (relatório corrigido a partir do código) |
| Timeout do IQ / int de tipo | 32.000 ms / 299 | inalterado; 299 é um id de tipo de requisição IQ, não uma flag |
| Dictionary `privacy_token` | 234 | 234 (handler registrado em 234) |
| Token de entrada | não documentado | handler de notification `X.0vv` (`C1S0` case 4888), `sender_lid` preferido |
| tctoken na stanza de mensagem | não documentado | filho `<tctoken>` via `F6I`; também fanout `<to>` (`AbstractC33466EhY`), IQ de foto, presence |
| tctoken no GraphQL | apenas BizIntegrity | também IntegrityFeaturesContext, `C229259vZ`, `C23694AKh`, `C20L` |
| HMAC do CSToken no Android | não encontrado (talvez nativo) | found em Java: `AbstractC38971i1` + `F6G`; chave salt, dado = string do JID do destinatário |
| Injeção de `<cstoken>` do CSToken no Android | não encontrada | found: `NctTokenMessageSendStanzaContributor` (`F6G`), gates flags 24941 / 18639 |
| Provider do salt | `C57682i2` (redação "gerado pelo servidor") | `C67592to`: 32 bytes de `SecureRandom` local apenas no primário, companions ignoram |
| Mutação de sync do salt | `C177317vA` | `C52032Bk` (ação `nct_salt_sync`); handler `C0XG`, flag 25253 |
| Gatilho do salt | `C37511mA` | `C2AE` (`NewChatMessageCappingAsyncInit`) |
| Salt no HistorySync | não documentado | `HistorySync.nctSalt` (`C25838BCy`) armazenado por `CMP` |
| `nctSalt = 12` em `ConversationThreadInfo` | afirmado | não encontrado; `nctSalt_` existe no HistorySync |
| Campo 80 do SyncActionValue | `C8MG`/`C8HG` | `C49639Lse` / `C49554LrH`, campo 80 confirmado |
| `JidGroupInfo.tcToken = 8`, `contactPrimaryIdentityKey = 9` | afirmado | sem `JidGroupInfo`; `Conversation` (`BD1`): `tcToken` 21, `tcTokenTimestamp` 22, `contactPrimaryIdentityKey` 23, `tcTokenSenderTimestamp` 28 |
| Número de `NctSaltSyncAction.salt` | não informado | 1 (único campo) |
| Número de `HistorySync.nctSalt` | não informado | 19 |
| Int de tipo de IQ `299` | "flag 299" | id de tipo de requisição IQ passado ao `MessageClient`, não uma flag |
| `wa_nct_token_send_enabled`, coluna do WA Web | afirmado | exclusivo do Web, não se aplica ao Android; o gate do Android é a flag 24941 |
| `463` | afirmado | sem ponto de código no caminho de envio; não verificado |
| ACSToken | "string not found" | classe de config ACS `C31991Nz` found (`acs.whatsapp.com/graphql`); descrição de Privacy Pass é exclusiva do Web/não verificada |
