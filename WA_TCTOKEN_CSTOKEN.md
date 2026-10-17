# WhatsApp TCToken & CSToken — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-17
**Scope:** TCToken and CSToken — what they are, how they work, Android APK internals, Baileys implementation

---

## 1. Overview: What are these tokens?

| Token | Full name | Who issues it | When used | Purpose |
|-------|-----------|--------------|-----------|---------|
| **tctoken** | Trusted Contact Token | WA server | Warm contact (existing relationship) | Proves sender and recipient have prior contact — anti-spam attestation |
| **cstoken** | Cold-Start Token (NCT fallback) | Client (HMAC-SHA256, found in Android Java) | Cold contact (no stored tctoken) | Fallback anti-spam signal when no tctoken exists |

**Core rule (found):** In the 1:1 message stanza, `cstoken` is only attached when the store holds no valid tctoken for the recipient (`NctTokenMessageSendStanzaContributor/ skipped - tctoken present`). `tctoken` is attached by a separate contributor (`PrivacyTokenMessageSendStanzaContributor`).

Both tokens are anti-spam signals. What the server does with them is not visible from the client (inferred: spam / new-chat capping, see `NewChatMessageCappingAsyncInit` as the salt trigger).

All tokens are evidence tier **found** (static JADX read of 2.26.41.6) unless marked inferred / not re-verified. Nothing is tested at runtime.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 What it is

A server-issued binary token that attests a trusted relationship between two JIDs. The server generates and distributes it. The client stores and re-sends it. Token bytes are opaque to the client (signed data / algorithm: unknown).

### 2.2 How it's requested / refreshed

**Job:** `GeneratePrivacyTokenJob` — job name `"generate-tc-token"`. It does not carry a token: it asks the server to (re)issue one (see 2.4).

**Manager:** `PrivacyTokenSendManager` (`C230709y3`)

**Trigger logic (found):**
- Entry points `C230709y3.A01(C14080dr, UserJid)`, `A02(UserJid)`, `A04(UserJid)`; `A05` is an in-flight dedup set (`A03` removes from it).
- `A04`: bucket-based. Feature flag **996** = bucket length in seconds (<= 0 logs "Bad bucket configuration" and falls back to now − 15724800 s = 182 days). The job is skipped if the stored timestamp falls in the current bucket or later.
- SharedPrefs key `"privacy_token_last_batch_time_sec"` (read in `A04` and in `AHP`) tracks the last batch time. Flag **4063** (int) is a bucket offset used together with it and the real-issue timestamp.
- Flag **14303** (bool) selects how the JID is normalised (`A00`): when on, `PrivacyTokenStore.A0L` (PN → LID mapping); when off, LID → PN via the JID mapper. Flag **15491** (bool) similarly disables the PN/LID dual-lookup in the store (`A02`, `A0Q`).

**Freshness validation (found):**
```java
// C14820fK.A0Y(UserJid)  — token for sending
C9oI c9oI = A0M(userJid);
if (c9oI == null || c9oI.A00 < this.A04.A02()) return null;  // expired or missing
return c9oI.A01;
```
Expiry gate `C14830fL` (TokenBucketValidity):
- `A02()` (received tokens) = `A00(len=flag 865, validBuckets=flag 909)`
- `A01()` (sent-timestamp validity) = `min(A00(flag 996, flag 997), A02())`
- `A00(len, n)` = `max((now/len − (n−1)) * len, now − 15724800)` (15724800 s = 182 days hard floor).

### 2.3 Storage

**Database tables (`wa.db`), created by `C23627AHs` / `C23628AHt` (found):**

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
(Column types for `jid` / primary key are not shown in the two schema classes read; the `jid` column is used as key in all queries. Exact DDL types are inferred.)

**Storage manager:** `PrivacyTokenStore` (`C14820fK`), DB access via `C14840fM`
- In-memory cache: `C12420b9(10, "privacytokendatacache")`
- Key methods:
  - `A0P(UserJid, byte[], long)` — store received token; only overwrites if the new timestamp is newer ("UPDATE_RECEIVED_TOKEN_IF_NEWER")
  - `A0Y(UserJid)` — token bytes for sending (null if expired)
  - `A0M(UserJid)` — read token + timestamp
  - `A0O(UserJid)` / `A0N(UserJid)` — sent-side `(timestamp, real_issue_timestamp)` (cached; `A0O` drops entries older than `A04.A01()`)
  - `A0V(UserJid, long)` / `A0W(UserJid, long)` — update sent timestamp (`A0V` also nulls `real_issue_timestamp`)
  - `A0X(UserJid, Integer)` — real-issue recency check using flags **865** and **3802** / **22012**
  - `A0U()` — populate cache (called from `NewChatMessageCappingAsyncInit` on foreground)

**Data types:** `C9oI` = `(A00=timestamp, A01=byte[] token)`; `C220519e9` = `(A00=sent timestamp, A01=Long real_issue_timestamp)`.

### 2.4 XMPP stanzas

**Outgoing request (found, `GeneratePrivacyTokenJob.A0M`)** — sent to the server JID (`C19380nJ.A00`), not to the contact. It carries no token bytes; it names the contact, type and the stored timestamp:

```xml
<iq id="[id]" to="[server]" type="set" xmlns="privacy">
  <tokens>
    <token jid="[contact-jid]" type="trusted_contact" t="[stored-timestamp]"/>
  </tokens>
</iq>
```

Sent via `A0W(callback, node, id, 299, 32000L)` (`C10140Tq`, `MessageClient`): timeout **32,000 ms** (found). `299` is the IQ request-type int: `A0A` logs it as `MessageClient/sendIqWithCallbackInternal ... type=` and stores it with the pending callback (found). It is a per-request-kind id shared by many IQ call sites (same slot carries values such as 1, 2, 14, 114, 237, 254, 264, 415), not a feature flag. Which value names which request is not listed in the client. Job retry: `A0O` retries unless the error node code is 4xx. The job aborts ("Token timestamp ... missing or too old to send") if no stored token timestamp is valid.

**Incoming (found, `C1S0` case 4888, handler `X.0vv`)** — registered for dictionary token **234** (`"privacy_token"`, table `AbstractC32331E9w`):

```xml
<notification from="[contact-jid]" sender_lid="[lid]?" t="[t]">
  <tokens>
    <token type="trusted_contact" t="[unix-timestamp]">[binary-token-bytes]</token>
  </tokens>
</notification>
```
Only children with `type="trusted_contact"` are stored; missing content throws "required token element to contain data". Store key is `sender_lid` if present, else `from`. `t` falls back to the parent's `t`. Timestamp lookup via `A0P`, which ignores non-newer tokens.

**Outgoing tctoken attachment (found)** — token bytes `1..120` from `PrivacyTokenStore.A0Y`:

| Where | Class | Shape |
|-------|-------|-------|
| 1:1 message stanza | `PrivacyTokenMessageSendStanzaContributor` (`F6I`) | `<tctoken>[bytes]</tctoken>` child; if missing but expected, logs `expected token, but missing` and reports reason `C99E.A07`. Flag **20605** switches to the device's user JID |
| Multi-device fanout | `AbstractC33466EhY.A01` | `<tctoken>` appended once per user inside the first `<to jid=...>` device node; limited by flag **20605** (bool) and flag **20606** (max users per stanza) |
| Profile-picture IQ `w:profile:picture` | `C197098a4.A00` | `<picture ...><tctoken>` child |
| Presence subscribe | `HandlerThreadC21920sG` case 12 / `C18320lY.A07` | `<presence type="subscribe"><tctoken>` |

### 2.5 GraphQL integration

The stored token is attached as additional context in several GraphQL inputs:

```java
// BizIntegritySignalsGraphQLFetcher / IntegrityFeaturesContextFetcher / C229259vZ / C23694AKh / C20L.A0M
node = GraphQlCallInput("tctoken", base64(token));   // string field
node.put("timestamp", String.valueOf(c9oI.A00));
query_input.put("privacy_token", node);
```

Fields: `tctoken` (token, Base64 / string-encoded), `timestamp`, nested under `privacy_token`. Callers in 2.26.41.6: BizIntegritySignals, IntegrityFeaturesContext (`use_case INTEGRITY_FEATURES_CONTEXT`), `C229259vZ`, `C23694AKh`, `C20L`.

### 2.6 Proto definition

Not in a `JidGroupInfo` message: no class of that name exists in 2.26.41.6. The persisted-token fields are on the `Conversation` proto (`BD1`, `id` = 1, `messages` = 2) (found, `*_FIELD_NUMBER` constants):

| Field | Number | Type |
|-------|--------|------|
| `tcToken` | **21** | bytes |
| `tcTokenTimestamp` | **22** | int64 |
| `contactPrimaryIdentityKey` | **23** | bytes |
| `tcTokenSenderTimestamp` | **28** | int64 |

The 2.26.26.4 claim `JidGroupInfo.tcToken = 8` / `contactPrimaryIdentityKey = 9` does not hold for this build.

---

## 3. CSToken / NCT Token (Cold-Start Token)

### 3.1 What it is

A **client-computed HMAC** over the recipient JID string, keyed with an account-wide salt (`nctSalt`). It is the fallback when no tctoken exists.

**Formula (found, Android `AbstractC38971i1.A00(data, key)`):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8(recipientJid.toString()))
```
Output: 32 bytes, raw. The code only checks that the string is non-empty (log: `NctTokenGenerator/ recipient LID is empty`), which suggests the recipient is a LID (inferred). The exact `<user>@lid` input form is a WA Web-only statement from the 2.26.26.4 report; it is not applicable to Android and not checkable from the APK.

### 3.2 NctSalt — where it comes from

The salt is generated locally on the primary device and distributed to companions via **App-State-Sync** and **HistorySync**.

**Generation (found, `NctSaltProvider` = `C67592to.A00()`):**
```java
byte[] salt = loadFromSharedPrefs();            // C2X8.A04()
if (salt == null) {
    if (companionDevice) return null;           // "skipped - companion device"
    salt = new byte[32]; SecureRandom.nextBytes(salt);
    C2X8.A03(salt);                             // persist
    putLong("nct_salt_last_sync_ts", 0L);
}
```
Storage `C2X8`: SharedPrefs key `"nct_salt"`, Base64 (`NO_WRAP`). So the origin is local `SecureRandom` on the primary (found), not server-generated.

**Trigger (found, `NewChatMessageCappingAsyncInit` = `C2AE`)**: on app foreground / async-init:
- Flag **24915** (bool): enables NCT salt creation and sync.
- If `nct_salt_last_sync_ts == 0` or flag **26897** (int, seconds) > 0 and elapsed >= that interval: write the new `nct_salt_last_sync_ts` and schedule a SyncD push (`C3MD` case 36 → `SyncdUpdateHelperImpl/syncNctSalt`).

**Sync mutation (found, `NctSaltSyncMutation` = `C52032Bk`)**: carries raw `byte[]` salt, action `EnumC24865AnN.A0x` (`"NctSaltSyncAction"`, key `"nct_salt_sync"`), wrapped into `SyncActionValue` field **80**. Pushed to companions via `C12440bB.A0U/A0O`.

**Receive on companion (found, `NctSaltSyncMutationHandler` in `C0XG`)**: when on a companion, `A0S` stores the salt via `C2X8.A03` ("Received NCT salt from primary, storing"). Handler enabled by flag **25253** (bool).

**HistorySync (found, `CMP`)**: `HistorySync.nctSalt` (`C25838BCy.nctSalt_`, presence bit 512) is stored via `C2X8.A03` ("stored NCT salt from history sync"). Field number **19** (`C25838BCy.NCT_SALT_FIELD_NUMBER`, found).

### 3.3 Proto fields

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

DB: `"nct_salt"` column registered in `wa.db` schema (`C09E`, entry `C33501Un("nct_salt", ...)`). The 2.26.26.4 report attributed `nctSalt = 12` to `ConversationThreadInfo`; no class of that name and no `nctSalt` field outside HistorySync exist in 2.26.41.6 (`nctSalt_` is only in `C25838BCy`, number 19; `Conversation` `BD1` has no salt field).

### 3.4 HMAC computation and stanza (Android vs Web)

| Aspect | Android 2.26.41.6 | WA Web (Web-only, not applicable to Android; not checkable from the APK) |
|--------|------------------|--------|
| Salt sync (NctSaltSyncAction) | Implemented (field 80) | Yes |
| Salt storage | SharedPrefs `"nct_salt"` | IndexedDB `"WAWebNctSalt"` |
| HMAC-SHA256 computation | **Found in Java** (`AbstractC38971i1`, `javax.crypto.Mac`) | JavaScript |
| Token injection into stanza | **Found in Java** (`NctTokenMessageSendStanzaContributor` = `F6G`) | `<cstoken>` node |

**Stanza contributor (found, `F6G.ASY`)**, in order:
```
flag 24941 off                    → nothing
recipient not a 1:1 user JID      → skip ("not a 1:1 user JID")
flag 18639 on and recipient is GUEST_E2EE → skip ("guest recipient")
PrivacyTokenStore.A0Y(user) != null → skip ("tctoken present")
recipient string empty            → log "recipient LID is empty", fail
salt == null                      → log "no salt available", fail
else  <cstoken>[32 bytes]</cstoken> appended to the message stanza
```
Any exception is caught and logged (`skipping cstoken due to ...`); the send continues.

```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

Flag **24941** (bool) = CSToken send gate on Android; **18639** (bool) = guest-recipient exclusion.

---

## 4. Token Comparison

| | TCToken | CSToken |
|-|---------|---------|
| Issued by | WA server | Client (HMAC) |
| Algorithm | Server-defined (opaque binary) | HMAC-SHA256 |
| Key material | Server-generated | `nctSalt` (local `SecureRandom`, synced via App-State / HistorySync) |
| Data signed | Not known (opaque) | `utf8(recipient JID string)` (LID form inferred) |
| Exists when | Prior contact established, not expired | When salt exists and no valid tctoken |
| Priority | First (tctoken wins) | Fallback only |
| Stanza | `<tctoken>` child in message / `<to>` node / picture IQ / presence; request IQ `xmlns="privacy"` to server | `<cstoken>` child in message |
| GraphQL | Sent in several integrity queries | Not seen in GraphQL |
| Storage | `wa_trusted_contacts` (+ `_send`) in DB | SharedPrefs `"nct_salt"` |
| Per-recipient | Yes (one per JID) | No (one salt, computed per recipient) |

---

## 5. Baileys Implementation

Everything in this section is implementation guidance (inferred from the protocol facts above), not a decompiled artifact. Stanza shapes are adjusted to 2.26.41.6; the TypeScript is untested.

### 5.1 TCToken

**Receiving and storing:**
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
(The notification `type` attribute value used in the event name is inferred; the Android handler is keyed on dictionary token 234.)

**Sending with tctoken:** attach the stored bytes as a `<tctoken>` child of the message stanza (1..120 bytes), not as a separate IQ:
```ts
const stored = (await authState.keys.get('tc-token', [recipientJid]))[recipientJid]
if (stored && !isExpired(stored.timestamp)) {
  stanza.content.push({ tag: 'tctoken', attrs: {}, content: stored.token })
}
```

**Refreshing (request IQ, shape found on Android):**
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

**Capturing nctSalt from App-State-Sync:**
```ts
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    authState.keys.set({ 'nct-salt': { default: Buffer.from(nctSaltAction.salt) } })
  }
}
```
A primary-device client would instead create 32 random bytes itself (as `NctSaltProvider` does) and push the mutation.

**Computing and attaching cstoken:**
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
`recipientJid` = the string Android passes (`Jid.toString()` of the 1:1 recipient); using the LID form is inferred.

**Resulting stanza:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 Full send flow

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

### 5.4 Proto for NctSaltSyncAction (Baileys proto patch)

Add to your proto if not already present:
```protobuf
message NctSaltSyncAction {
  bytes salt = 1;
}

// In SyncActionValue:
NctSaltSyncAction nctSaltSyncAction = 80;
```

---

## 6. Gating / Feature Flags

| Flag | Value | Controls |
|------|-------|---------|
| **24915** | bool | NCT salt creation + sync enabled (`C2AE`) |
| **26897** | int (seconds) | Min interval between salt re-syncs |
| **24941** | bool | CSToken stanza contributor on/off (`F6G`) |
| **18639** | bool | Skip cstoken for GUEST_E2EE recipients |
| **25253** | bool | Enables `NctSaltSyncMutationHandler` |
| **996** | int (seconds) | Sent-token bucket length (job trigger, `C230709y3.A04`; also `C14830fL.A01`) |
| **997** | int | Valid sent-token bucket count (`C14830fL.A01`) |
| **865** / **909** | int | Received-token bucket length / valid bucket count (`C14830fL.A02`) |
| **4063** | int | Bucket offset in `A04` re-issue check |
| **3802** / **22012** | int | Valid bucket count in `A0X` (real-issue recency) |
| **20605** | bool | tctoken in per-device `<to>` nodes; device-user JID selection in `F6I` |
| **20606** | int | Max users carrying `<tctoken>` per fanout stanza |
| **14303** / **15491** | bool | PN/LID normalisation behaviour in manager / store |
| `wa_nct_token_send_enabled` | AB-prop (Web) | WA Web-only CSToken send gate; not applicable to Android (string absent from the APK; Android gate is flag 24941) |

Flag semantics are read from usage; live server values are unknown.

---

## 7. Error cases and what to watch for

| Symptom | Cause | Fix |
|---------|-------|-----|
| No cstoken attached, normal send | tctoken present, flag 24941 off, guest recipient, or non-1:1 | Expected (Android log strings in 3.4) |
| Android log `NctTokenGenerator/ no salt available` | No salt in SharedPrefs and device is a companion (cannot create) | Wait for NctSaltSyncAction / HistorySync |
| Android log `recipient LID is empty` | Empty JID string passed to generator | Ensure recipient JID is resolved |
| Server `463` error after send | LID string format wrong | (2.26.26.4, not re-verified; no 463 handler in the message-send, `F6G`, `AbstractC38971i1` or privacy-token job paths of 2.26.41.6. The only app-level 463 branch found is the create-group `onError` in `NewGroup`, unrelated) |
| `GeneratePrivacyTokenJob` fails | 4xx from server is not retried; other errors retried | Re-request after bucket rolls over |
| Stored token ignored | Older than `C14830fL.A02()` or bucket expired | Wait for new `privacy_token` notification |

---

## 8. Key distinctions

- **tctoken** ≠ **privacy_token** at the naming level: `privacy_token` is the GraphQL nested field, the XMPP dictionary token (234) and the `xmlns="privacy"` namespace; `tctoken` is the stanza child name, the GraphQL string field and the proto field. Same underlying token in different contexts.
- **ACSToken** — Android has an ACS-token config object (`C31991Nz`: `docId`, `graphQlUrl` = `https://acs.whatsapp.com/graphql`, `surface`, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`) and `hasAcsToken()` on a related interface (found). The "Privacy Pass blind tokens for Status/Channels crediting" description and the `WAACSTokenUtils` name are WA Web-only claims from 2.26.26.4 (not applicable to Android, not verified). No link to the tctoken/cstoken send path found.
- **counter_abuse_token** — Server-ACK metadata on mobile (string present in 2.26.41.6: `C37961fH`, `C13X`, DB column in `C09550Rf`). Not a sender-constructed token.
- **nctSalt** is account-wide (same salt for all recipients). Per-recipient differentiation happens in the HMAC input (recipient JID string).
- The `xmlns="privacy"` IQ is a **request to the server** carrying only `jid`/`type`/`t`, not a transport for the token bytes; token bytes travel in `<tctoken>` children and arrive via notification.

---

## 9. Changes vs 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| Send manager | `C73O` | `C230709y3` (entry points A01/A02/A04 plus in-flight set A05) |
| Token store / cache | `C07730Zd` / `C07760Zg` | `C14820fK` / `C12420b9` "privacytokendatacache" |
| Token data type | `C151666s4` | `C9oI` (token+ts); new `C220519e9` (sent ts + real_issue ts) |
| Expiry gate | `C07740Ze.A02()` | `C14830fL.A02()` (flags 865/909; 182-day floor); sent side A01 (996/997) |
| Table / column names | `wa_trusted_contacts(_send)` | unchanged; plus 3 indexes found |
| Flag 996 / 24915 / 26897 | listed | unchanged; many new flags found (see 6) |
| SharedPrefs keys | `privacy_token_last_batch_time_sec`, `nct_salt`, `nct_salt_last_sync_ts` | unchanged |
| Outgoing tc IQ shape | `<trusted_contact jid type t><token>bytes</token></trusted_contact>` to the recipient | `<tokens><token jid type="trusted_contact" t/></tokens>` to the server, no token bytes (report corrected from code) |
| IQ timeout / type int | 32,000 ms / 299 | unchanged; 299 is an IQ request-type id, not a flag |
| Dictionary `privacy_token` | 234 | 234 (handler registered at 234) |
| Incoming token | not documented | notification handler `X.0vv` (`C1S0` case 4888), `sender_lid` preferred |
| tctoken in message stanza | not documented | `<tctoken>` child via `F6I`; also fanout `<to>` (`AbstractC33466EhY`), picture IQ, presence |
| GraphQL tctoken | BizIntegrity only | also IntegrityFeaturesContext, `C229259vZ`, `C23694AKh`, `C20L` |
| CSToken HMAC on Android | not found (maybe native) | found in Java: `AbstractC38971i1` + `F6G`; key salt, data = recipient JID string |
| CSToken `<cstoken>` injection on Android | not found | found: `NctTokenMessageSendStanzaContributor` (`F6G`), gates flags 24941 / 18639 |
| Salt provider | `C57682i2` ("server-generated" wording) | `C67592to`: local `SecureRandom` 32 bytes on primary only, companions skip |
| Salt sync mutation | `C177317vA` | `C52032Bk` (action `nct_salt_sync`); handler `C0XG`, flag 25253 |
| Salt trigger | `C37511mA` | `C2AE` (`NewChatMessageCappingAsyncInit`) |
| Salt in HistorySync | not documented | `HistorySync.nctSalt` (`C25838BCy`) stored by `CMP` |
| `nctSalt = 12` in `ConversationThreadInfo` | claimed | not found; `nctSalt_` exists in HistorySync |
| SyncActionValue field 80 | `C8MG`/`C8HG` | `C49639Lse` / `C49554LrH`, field 80 confirmed |
| `JidGroupInfo.tcToken = 8`, `contactPrimaryIdentityKey = 9` | claimed | no `JidGroupInfo`; `Conversation` (`BD1`): `tcToken` 21, `tcTokenTimestamp` 22, `contactPrimaryIdentityKey` 23, `tcTokenSenderTimestamp` 28 |
| `NctSaltSyncAction.salt` number | not stated | 1 (only field) |
| `HistorySync.nctSalt` number | not stated | 19 |
| IQ type int `299` | "flag 299" | IQ request-type id passed to `MessageClient`, not a flag |
| `wa_nct_token_send_enabled`, WA Web column | claimed | Web-only, not applicable to Android; Android gate is flag 24941 |
| `463` | claimed | no code site on the send path; unverified |
| ACSToken | "string not found" | ACS config class `C31991Nz` found (`acs.whatsapp.com/graphql`); Privacy Pass description is Web-only/unverified |
