# WhatsApp Meta AI — Full RE Report
**Version:** 2.26.26.4 | **Date:** 2026-07-16
**Scope:** Meta AI internals — JID, routing, proto fields, request/response flow, why Baileys fails, fix

---

## 1. What Meta AI is (technically)

Meta AI is not a normal WhatsApp contact. It is a bot with special JIDs, custom proto fields, a JSON-over-metadata protocol for requests, and a streaming response mechanism embedded in regular message metadata. Sending a plain message to the Meta AI JID without these fields results in no response — the server ignores it or rejects it silently.

---

## 2. Meta AI JIDs

| Bot | JID | Status |
|-----|-----|--------|
| **Hatch** | `1807055946647697@s.whatsapp.net` | **Primary (current)** |
| **Manus** | `1807055946647696@s.whatsapp.net` | Legacy |
| **Fallback** | `1807055946647698@s.whatsapp.net` | Fallback |
| **Group** | `165332417282214@s.whatsapp.net` | Group context |

**Routing conversion** (critical): When sending, the client converts the JID:
```
Local:  1807055946647698
Remote: 1807055946647698$1   ← dollar-suffix appended for wire format
```

This conversion happens in `C1A2.A00()` / `C1A2.A01()`. Without it the server does not route the message to the AI backend.

**isMetaAI detection** (client-side):
```java
public boolean isMetaAI(Jid jid) {
  if (jid == MANUS_JID)   return isManusFlagEnabled();   // flag 25119
  if (jid == HATCH_JID)   return isHatchFlagEnabled();   // flag 26189 (primary)
  if (jid == FALLBACK_JID || jid == GROUP_JID) return isMigrationEnabled(); // 27083
  return false;
}
```

---

## 3. Feature Flags

| Flag ID | Name | Controls |
|---------|------|---------|
| **25119** | `ai_bot_integration_enabled` | Manus bot (legacy) |
| **26189** | `ai_hatch_integration_enabled` | Hatch bot (current primary) |
| **27083** | `ai_maiba_wass_migration_receiving_enabled` | Migration receiving |

---

## 4. Proto Fields — What's different from normal messages

### 4.1 WebMessageInfo top-level fields

| Field | Number | Type | Used for |
|-------|--------|------|---------|
| `botInvokeMessage` | **67** | bytes (wrapper) | Bot call — set when invoking Meta AI |
| `botTaskMessage` | **100** | bytes (wrapper) | Bot task actions |
| `botForwardedMessage` | **104** | bytes (wrapper) | Forwarding to Meta AI |
| `richResponseMessage` | **77** | bytes | AI response (text, images, tables, code) |

### 4.2 ContextInfo fields (nested, critical)

| Field | Number | Type | Value |
|-------|--------|------|-------|
| `botMessageInvokerJid` | **58** | string | Your JID (the sender) |
| `isSupportAiMessage` | **70** | bool | **`true`** for all Meta AI messages |
| `supportAiCitations` | **72** | bytes[] | Source citations from AI |
| `botTargetId` | **73** | string | Bot persona target ID |

### 4.3 BotMetadata (class `B2Y`)

| Field | Number | Type | Value |
|-------|--------|------|-------|
| `personaId` | **2** | string | `"meta_ai"` for Meta AI |
| `invokerJid` | **5** | string | Your JID |
| `pluginMetadata` | **3** | B2C | Plugin config (see below) |
| `aiConversationContext` | **20** | bytes | Serialized conversation state |
| `botResponseId` | **26** | string | Response ID (in AI replies) |

### 4.4 PluginMetadata (class `B2C`)

| Field | Number | Type | Value |
|-------|--------|------|-------|
| `provider` | **1** | int32 | Provider ID |
| `pluginType` | **2** | int32 enum | 8=IMAGINE, 9=MEMU, 15=MEMU_AND_IMAGINE |

### 4.5 Action Type enum (MTT)

| Value | Meaning |
|-------|---------|
| `1` | `ASK_META_AI_ACTION` — standard chat |
| `2` | `CREATE_A_TASK_ACTION` |
| `3` | `CREATE_A_POLL_ACTION` |

---

## 5. Request Protocol (how the client sends to Meta AI)

Requests go through `HatchMetadataRequestManager` (`C26654Bv8`). The transport is **not plain XMPP text** — it is a JSON envelope encoded as binary metadata:

```json
{
  "version": 1,
  "type": "req",
  "method": "<method_name>",
  "params": { ... }
}
```

This JSON is binary-encoded and sent as `hatchMetadataSync` bytes inside a standard message. The request manager tracks pending requests in a `ConcurrentHashMap` (field `A02`) keyed by request ID, resolved asynchronously when the response arrives.

**Flow:**
```
relayMessage(metaAiJid, msg, opts)
    │
    ▼
Encode message with:
  ContextInfo.isSupportAiMessage = true
  ContextInfo.botMessageInvokerJid = yourJid
  ContextInfo.botTargetId = personaTargetId
  BotMetadata.personaId = "meta_ai"
  BotMetadata.invokerJid = yourJid
  BotMetadata.aiConversationContext = <state bytes>
  WebMessageInfo.botInvokeMessage = <wrapper>
    │
    ▼
JID conversion: 1807055946647698 → 1807055946647698$1 (wire format)
    │
    ▼
Send via normal XMPP message channel
    │
    ▼
HatchMetadataRequestManager registers pending request
    │
    ▼
Response arrives as hatchMetadataSync bytes in incoming message
```

**No custom XMPP namespace.** There is no `w:ai` or `wa:ai` namespace. All AI metadata rides inside regular message stanzas as opaque bytes.

---

## 6. Response Protocol (how Meta AI replies)

### 6.1 Transport

Responses arrive as **normal WhatsApp messages** with `hatchMetadataSync` bytes in the message metadata — not as separate IQ stanzas, not as a custom namespace, not via MEX GraphQL.

The `hatchMetadataSync` field is in proto class `Azz` and is resolved by `HatchMetadataRequestManager` which matches the response to the pending request via request ID.

### 6.2 Streaming (chunked responses)

Long AI responses come in chunks:

| Field | Type | Meaning |
|-------|------|---------|
| `chunkOrder` | int32 | Sequence number of this chunk |
| `isLastChunk` | bytes | Set on final chunk |
| `clientStreaming` | bytes | Client streaming capability |
| `serverStreaming` | bytes | Server streaming capability |
| `streamingSidecar` | bytes | Streaming metadata sidecar |

The client reassembles chunks in order. The UI shows partial text as chunks arrive (streaming typing effect).

### 6.3 Rich response (field 77)

`richResponseMessage` carries the full structured AI reply:
- Plain text
- Images (image generation via IMAGINE plugin)
- Tables
- Code blocks
- Citations (`supportAiCitations`)

Rendered by `AiRichResponseFooterView` and the `UnifiedResponseActionHandlerFactory` for click actions.

### 6.4 Typing indicator

Standard XMPP Chat State (`xmlns="http://jabber.org/protocol/chatstates"`) — `composing` stanza from the Meta AI JID. No special namespace.

### 6.5 Bot profile sync

The client syncs Meta AI's profile separately from normal contacts via `BotProfileSyncManagerImpl`, running every ~1 minute via `BotProfileForChatListWorker` (WorkManager). It is NOT part of the normal roster sync.

---

## 7. Storage

Meta AI conversation state is NOT stored in the regular `msgstore.db` chat tables. It uses `MetaAiMemoryStore` (extends `AbstractC06790Ud`) with its own persistence layer. SharedPrefs key: `"meta_ai_forward_disclosure_seen"`.

Session management: `MetaAiIncognitoSessionManager` handles incognito/private sessions separately.

---

## 8. Why Baileys doesn't get a response

Most Baileys implementations send a plain text message to the Meta AI JID and wait for a reply. This fails for several reasons:

| Issue | Why it breaks |
|-------|--------------|
| **Wrong or missing JID suffix** | Wire format requires `1807055946647698$1`, not the raw JID |
| **Missing `isSupportAiMessage = true`** | Server filters messages without this ContextInfo flag |
| **Missing `botInvokeMessage` wrapper** | Field 67 in WebMessageInfo must be set |
| **Missing `BotMetadata`** | `personaId = "meta_ai"` and `invokerJid` must be present |
| **Missing `botTargetId`** | Server needs the persona target ID in ContextInfo |
| **Missing `aiConversationContext`** | First message needs empty context bytes; follow-ups need state |
| **Response not parsed** | Reply comes back as `hatchMetadataSync` bytes, not plain text — Baileys standard message handler ignores it |
| **No chunk reassembly** | Streaming responses arrive in chunks; without reassembly only partial or no text is seen |

---

## 9. Baileys Fix — How to implement

### 9.1 Correct JID and wire routing

```ts
const META_AI_JID = '1807055946647697@s.whatsapp.net'  // Hatch (primary)

// Wire format JID (dollar-suffix) — may need to be set as participant/recipient
const META_AI_WIRE_JID = '1807055946647698$1@s.whatsapp.net'
```

### 9.2 Build the message with required proto fields

```ts
import { proto } from 'baron-baileys-v2'

function buildMetaAiMessage(text: string, yourJid: string, conversationContext?: Uint8Array) {
  return {
    // Standard text content
    conversation: text,

    // ContextInfo — critical fields
    contextInfo: {
      isSupportAiMessage: true,              // field 70 — REQUIRED
      botMessageInvokerJid: yourJid,         // field 58 — your JID
      botTargetId: '1807055946647697',       // field 73 — persona target ID
    },

    // BotMetadata — field embedded in message
    // (exact proto embedding depends on your proto version)
    botMetadata: {
      personaId: 'meta_ai',                  // field 2 — REQUIRED
      invokerJid: yourJid,                   // field 5
      aiConversationContext: conversationContext ?? new Uint8Array(0),  // field 20
    }
  }
}
```

### 9.3 Send

```ts
const msg = buildMetaAiMessage('Hello Meta AI', sock.user.id)

await sock.relayMessage(META_AI_JID, { extendedTextMessage: msg }, {
  messageId: generateMessageID()
})
```

### 9.4 Handle the response

The response comes as an incoming message from `META_AI_JID`. Listen for it and parse `hatchMetadataSync` + `richResponseMessage`:

```ts
sock.ev.on('messages.upsert', ({ messages }) => {
  for (const msg of messages) {
    if (msg.key.remoteJid !== META_AI_JID) continue
    if (!msg.message) continue

    // Plain text response
    const text = msg.message.conversation
      || msg.message.extendedTextMessage?.text
      || null

    // Rich response (structured AI reply)
    const rich = msg.message.richResponseMessage
    if (rich) {
      // parse rich response bytes
    }

    // Streaming chunk
    const chunkOrder = (msg.message as any).chunkOrder
    const isLast = (msg.message as any).isLastChunk

    if (text) {
      console.log('[Meta AI]', text)
    }
  }
})
```

### 9.5 Conversation context (follow-up messages)

After the first reply, Meta AI sends back `aiConversationContext` bytes in `BotMetadata`. Store these and send them with every follow-up:

```ts
let conversationCtx: Uint8Array | undefined = undefined

sock.ev.on('messages.upsert', ({ messages }) => {
  for (const msg of messages) {
    if (msg.key.remoteJid !== META_AI_JID) continue
    // Extract updated context from BotMetadata.aiConversationContext (field 20)
    const botMeta = (msg.message as any)?.botMetadata
    if (botMeta?.aiConversationContext?.length) {
      conversationCtx = botMeta.aiConversationContext
    }
  }
})

// Next message:
const msg2 = buildMetaAiMessage('Follow-up question', sock.user.id, conversationCtx)
```

---

## 10. Complete request→response flow

```
[Baileys] buildMetaAiMessage(text)
    │  ContextInfo: isSupportAiMessage=true, botTargetId, botMessageInvokerJid
    │  BotMetadata: personaId="meta_ai", invokerJid, aiConversationContext
    │  WebMessageInfo: botInvokeMessage wrapper
    ▼
[XMPP] Standard message stanza → META_AI_JID (wire: 1807055946647698$1)
    │  No custom namespace — rides normal message channel
    ▼
[WA Server] Routes to Meta AI backend (Hatch)
    │  Validates: isSupportAiMessage, personaId, botTargetId
    │  Rejects silently if missing → no response
    ▼
[Meta AI Backend] Processes query, generates response
    ▼
[WA Server → Client] Incoming message from META_AI_JID
    │  hatchMetadataSync: bytes (JSON response metadata)
    │  richResponseMessage: structured reply (field 77)
    │  chunkOrder + isLastChunk: for streaming
    ▼
[Baileys] messages.upsert event
    │  Parse .conversation / .richResponseMessage
    │  Store new aiConversationContext for next turn
    ▼
[Done] AI response available
```

