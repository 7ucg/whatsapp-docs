# WhatsApp TCToken & CSToken — Full RE Report
**Version:** 2.26.26.4 | **Date:** 2026-07-16
**Scope:** TCToken and CSToken — what they are, how they work, Android APK internals, Baileys implementation

---

## 1. Overview: What are these tokens?

| Token | Full name | Who issues it | When used | Purpose |
|-------|-----------|--------------|-----------|---------|
| **tctoken** | Trusted Contact Token | WA server | Warm contact (existing relationship) | Proves sender and recipient have prior contact — anti-spam attestation |
| **cstoken** | Cold-Start Token (NCT fallback) | Client (HMAC) | Cold contact (no prior relationship) | Fallback anti-spam signal when no tctoken exists |

**Core rule:** Only one token is ever attached per outgoing message. `tctoken` takes priority. `cstoken` only goes out when no `tctoken` is available.

Both tokens are anti-spam signals. Without either, a first-contact message has no attestation — classic spam signal.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 What it is

A server-issued binary token that attests a trusted relationship between two JIDs. The server generates and distributes it. The client stores and re-sends it. It proves: "this sender has had prior legitimate contact with this recipient."

### 2.2 How it's generated

**Job:** `GeneratePrivacyTokenJob` — job name `"generate-tc-token"`

**Manager:** `PrivacyTokenSendManager` (`C73O`)

**Trigger logic:**
- Called from `C73O.A01()`, `C73O.A02()`, `C73O.A04()`
- Bucket-based batching: Feature-flag **996** controls bucket length in seconds
- SharedPrefs key `"privacy_token_last_batch_time_sec"` tracks last batch time
- Skip if already sent in the current bucket period

**Freshness validation:**
```java
c151666s4 = A0M(userJid);          // load stored token
if (c151666s4 == null || c151666s4.A00 < this.A04.A02()) {
    return null;  // token expired or missing
}
```
Expiry gate defined in `C07740Ze.A02()`.

### 2.3 Storage

**Database tables (`wa.db`):**

```sql
-- Incoming tokens (received from contacts)
CREATE TABLE wa_trusted_contacts (
  jid                      TEXT PRIMARY KEY,
  incoming_tc_token        BLOB,       -- raw token bytes
  incoming_tc_token_timestamp LONG
);

-- Outgoing token tracking
CREATE TABLE wa_trusted_contacts_send (
  jid                      TEXT PRIMARY KEY,
  sent_tc_token_timestamp  LONG,
  real_issue_timestamp     LONG
);
```

**Storage manager:** `C07730Zd` (PrivacyTokenStore)
- In-memory cache: `C07760Zg` ("privacytokendatacache")
- Key methods:
  - `A0P(UserJid, byte[], long)` — store received token
  - `A0Y(UserJid)` — retrieve token for sending
  - `A0M(UserJid)` — read token + timestamp
  - `A0V(UserJid, long)` — update sent timestamp

**Data type:** `C151666s4` holds `(A00=timestamp, A01=byte[] token)`

### 2.4 XMPP stanza (outgoing)

Sent as a dedicated IQ, separate from the message itself, with `xmlns="privacy"`:

```xml
<iq id="[message-id]" to="[recipient-jid]" type="set" xmlns="privacy">
  <tokens>
    <trusted_contact jid="[contact-jid]" type="[type]" t="[unix-timestamp]">
      <token>[binary-token-bytes]</token>
    </trusted_contact>
  </tokens>
</iq>
```

IQ timeout: **32,000ms** (32 seconds). Flag value: `299` (timeout code), `2` (send flag).

**IQ namespace mapping:** `"privacy_token"` → field number **234** in the XMPP token dictionary.

### 2.5 GraphQL integration (BizIntegrityQuery)

When BizIntegrityQuery fires, the tctoken is attached as additional context:

```java
// BizIntegritySignalsGraphQLFetcher
c11970h8A0H = AbstractC35391iO.A0H(c11910h2, strA1E, "tctoken");
C11970h8.A00(c11970h8A0H, String.valueOf(c151666s4.A00), "timestamp");
C5S7.A1L(c11970h8A0H, c5si, "privacy_token");
```

GraphQL fields sent: `tctoken` (the binary token), `timestamp`, `privacy_token` (nested context).

### 2.6 Proto definition

In `JidGroupInfo` proto:
```protobuf
message JidGroupInfo {
  bytes tcToken = 8;
  bytes contactPrimaryIdentityKey = 9;
}
```

---

## 3. CSToken / NCT Token (Cold-Start Token)

### 3.1 What it is

A **client-computed HMAC** over the recipient's LID, keyed with an account-wide salt (`nctSalt`). It's the fallback when no tctoken exists — a first-contact message still carries a token that proves the sender is a legitimate client with a valid salt.

**Formula (verified from WA Web source):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8("<user>@lid"))
```
Output: 32 bytes, raw, no truncation.

### 3.2 NctSalt — where it comes from

The salt is distributed server-side via **App-State-Sync** (same mechanism as message keys / key backup).

**Proto chain:**
```
SyncActionValue (C8MG) {
  field 80: NctSaltSyncAction (C8HG) {
    field 1: bytes salt
  }
}
```

**On receiving this sync action:**
```
App-State patch received
  → SyncActionValue.nctSaltSyncAction.salt
  → C8XP.A04(saltBytes)          // persist to SharedPreferences
  → SharedPrefs key: "nct_salt"  // stored as Base64 string
  → putLong("nct_salt_last_sync_ts", 0L)
```

**Salt generation** (`C57682i2` — NctSaltProvider):
```java
byte[] salt = new byte[32];
SecureRandom.nextBytes(salt);   // server-generated, 32 bytes
C8XP.A04(salt);                  // persist
```

**Sync mutation** (`C177317vA` — NctSaltSyncMutation):
- Takes raw `byte[]` salt
- Wraps into `NctSaltSyncAction` proto
- Injects into `SyncActionValue` at field 80
- Pushed to other devices via App-State

**Trigger:** `C37511mA` — fires on app foreground
- Feature-flag **24915**: enables NCT salt creation
- Feature-flag **26897**: max seconds between re-syncs

### 3.3 Proto fields

```protobuf
// NctSaltSyncAction
message NctSaltSyncAction {
  bytes salt = 1;               // 32-byte salt
}

// SyncActionValue
message SyncActionValue {
  NctSaltSyncAction nctSaltSyncAction = 80;  // NCT_SALT_SYNC_ACTION
}

// ConversationThreadInfo
message ConversationThreadInfo {
  bytes nctSalt = 12;           // per-conversation cached salt
}
```

DB: `"nct_salt"` column registered in wa.db schema (`C08X.java`).

### 3.4 HMAC computation and stanza (Android vs Web)

| Aspect | Android 2.26.26.4 | WA Web |
|--------|------------------|--------|
| Salt sync (NctSaltSyncAction) | ✅ Fully implemented (Proto 80) | ✅ |
| Salt storage | ✅ SharedPrefs `"nct_salt"` | ✅ IndexedDB `"WAWebNctSalt"` |
| HMAC-SHA256 computation | ❌ Not found in Java | ✅ JavaScript |
| Token injection into stanza | ❌ Not found in Java | ✅ `<cstoken>` node |

**Finding:** The HMAC calculation and `<cstoken>` injection are either in native `.so` libraries (JNI) or not yet implemented for Android. Android's role is salt distribution only — the computation seen in WA Web may run natively on Android.

**WA Web stanza output:**
```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

---

## 4. Token Comparison

| | TCToken | CSToken |
|-|---------|---------|
| Issued by | WA server | Client (HMAC) |
| Algorithm | Server-defined (opaque binary) | HMAC-SHA256 |
| Key material | Server-generated | `nctSalt` (from App-State-Sync) |
| Data signed | Not known (opaque) | `utf8("<user>@lid")` |
| Exists when | Prior contact established | Always (if salt synced) |
| Priority | First (tctoken wins) | Fallback only |
| Stanza | `<iq xmlns="privacy">` (separate) | `<cstoken>` in message |
| GraphQL | Sent in BizIntegrityQuery | Not seen in GraphQL |
| Storage | `wa_trusted_contacts` (DB) | SharedPrefs `"nct_salt"` |
| Per-recipient | Yes (one per JID) | No (one salt, computed per recipient) |

---

## 5. Baileys Implementation

### 5.1 TCToken

**Receiving and storing:**
```ts
// In App-State or IQ handler — store incoming token
async function storeTcToken(jid: string, token: Buffer, timestamp: number) {
  // persist to your key-value store
  await authState.keys.set({
    'tc-token': {
      [jid]: { token, timestamp }
    }
  })
}

// Parse incoming <trusted_contact> IQ
sock.ev.on('CB:iq,type:set,xmlns:privacy', async (node) => {
  const tokens = getBinaryNodeChild(node, 'tokens')
  if (!tokens) return
  for (const tc of getBinaryNodeChildren(tokens, 'trusted_contact')) {
    const jid = tc.attrs.jid
    const timestamp = parseInt(tc.attrs.t)
    const tokenNode = getBinaryNodeChild(tc, 'token')
    if (tokenNode?.content) {
      await storeTcToken(jid, Buffer.from(tokenNode.content as Uint8Array), timestamp)
    }
  }
})
```

**Sending with tctoken:**
```ts
async function buildPrivacyTokenIQ(recipientJid: string, authState: AuthenticationState) {
  const stored = await authState.keys.get('tc-token', [recipientJid])
  const entry = stored[recipientJid]
  if (!entry) return null

  return {
    tag: 'iq',
    attrs: { type: 'set', xmlns: 'privacy', to: recipientJid },
    content: [{
      tag: 'tokens',
      attrs: {},
      content: [{
        tag: 'trusted_contact',
        attrs: { jid: recipientJid, type: '1', t: String(entry.timestamp) },
        content: [{
          tag: 'token',
          attrs: {},
          content: entry.token
        }]
      }]
    }]
  }
}

// Call before or after relayMessage for warm contacts
const iq = await buildPrivacyTokenIQ(jid, sock.authState)
if (iq) await sock.query(iq)
```

### 5.2 CSToken

**Capturing nctSalt from App-State-Sync:**
```ts
// In chats.js / app-state mutation handler
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    const salt = Buffer.from(nctSaltAction.salt)
    authState.keys.set({
      'nct-salt': { default: salt }
    })
    logger.info('[nct] salt synced, length:', salt.length)
  }
}
```

**Computing and attaching cstoken:**
```ts
import { createHmac } from 'crypto'

async function buildCsTokenNode(
  recipientLid: string,         // format: "<user>@lid" e.g. "1910@lid"
  authState: AuthenticationState,
  tcTokenBuffer?: Buffer        // existing tctoken if any
): Promise<BinaryNode | null> {
  // tctoken takes priority
  if (tcTokenBuffer?.length) return null

  // need LID format
  if (!recipientLid.endsWith('@lid')) return null

  // load salt
  const saltStore = await authState.keys.get('nct-salt', ['default'])
  const salt = saltStore['default']
  if (!salt) {
    logger.warn('[nct] cstoken requested but no nct salt stored yet')
    return null
  }

  // HMAC-SHA256(salt, utf8("<user>@lid"))
  const cs = createHmac('sha256', salt)
    .update(Buffer.from(recipientLid, 'utf8'))
    .digest()  // 32 bytes, no truncation

  return {
    tag: 'cstoken',
    attrs: {},
    content: cs
  }
}
```

**Integration in relayMessage:**
```ts
// In relayMessage, for 1:1 sends to cold contacts
const is1on1 = !isJidGroup(jid) && !isJidStatusBroadcast(jid)

if (options.cstoken && is1on1) {
  const recipientLid = await resolveLid(jid)   // your LID lookup
  const csNode = await buildCsTokenNode(
    recipientLid,
    sock.authState,
    existingTcToken  // pass if you have one
  )
  if (csNode) {
    stanza.content.push(csNode)
    logger.info('[nct] attached cstoken (nct fallback) for', jid)
  }
}
```

**Resulting stanza:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 Full send flow

```
relayMessage(jid, msg, { cstoken: true })
    │
    ▼
is 1:1 send? → NO → skip token attachment
    │ YES
    ▼
load tc-token from store for this JID
    │
    ├── tctoken found → attach as <iq xmlns="privacy"> (separate IQ), no cstoken
    │
    └── no tctoken (cold contact)
            │
            ▼
        resolve LID for recipient → no LID → log + skip
            │ has LID
            ▼
        load nct-salt from store → missing → log "no salt yet" + skip
            │ salt available
            ▼
        cstoken = HMAC-SHA256(salt, utf8(lid))
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
| **24915** | bool | NCT salt creation enabled |
| **26897** | int (seconds) | Max interval between salt re-syncs |
| **996** | int (seconds) | TCToken batch bucket length |
| `wa_nct_token_send_enabled` | AB-prop (Web) | CSToken send gate (WA Web) |

---

## 7. Error cases and what to watch for

| Symptom | Cause | Fix |
|---------|-------|-----|
| No cstoken attached, normal send | tctoken present (warm contact) | Expected — cstoken only for cold contacts |
| `"no nct salt stored yet"` | App-State-Sync not yet received | Wait / reconnect, sync fires on foreground |
| `"recipient has no LID"` | LID mapping not populated | Ensure LID mapping is built from presence/contacts |
| Server `463` error after send | LID string format wrong | Verify format is `"<user>@lid"` (no device suffix) |
| TCToken IQ not ACK'd | Expired or invalid token | Re-fetch token, discard stale entry |

---

## 8. Key distinctions

- **tctoken** ≠ **privacy_token** at the naming level: `privacy_token` is the GraphQL field name and the XMPP IQ namespace term; `tctoken` is the proto field name and attribute in the stanza. They refer to the same underlying token in different contexts.
- **ACSToken** (`WAACSTokenUtils`) — Privacy Pass blind tokens for Status/Channels crediting. Completely unrelated to anti-spam. Do not confuse.
- **counter_abuse_token** — Server-ACK metadata on mobile. Not a sender-constructed token.
- **nctSalt** is account-wide (same salt for all recipients). The per-recipient differentiation happens in the HMAC input (the recipient's LID).
