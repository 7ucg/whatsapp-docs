# WhatsApp Meta AI — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-17
**Scope:** Meta AI internals — JIDs, routing, proto fields, Hatch metadata requests, response rendering, why Baileys fails, fix

---

## 1. What Meta AI is (technically)

Meta AI is a bot contact addressed by special bot JIDs (server `bot`), with bot-specific proto fields on the normal message types and a separate JSON request channel ("Hatch metadata") carried in a `ProtocolMessage`. All statements are static analysis of the decompiled APK. Tier: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved.

Names in this report that were obfuscated in 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) were re-resolved from stable anchors; they do not exist under those names in 2.26.41.6.

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| BotJid | `C24770wv` | JID class, server `"bot"`, type 26, numeric string 1-20 chars, no leading 0 |
| Bot JID constants | `AbstractC34361Xw` | Hatch / Fallback / LID constants and sets |
| JID mapping | `AbstractC24760wu` | bot ↔ LID mapping, outgoing target conversion |
| Gating | `C39311it` | feature-flag gating per JID (`A0E(Jid)`) |
| Hatch request manager | `HF1` (`HatchMetadataRequestManager`) | JSON requests, pending map |
| Hatch proto builder | `Hf6` | builds `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | holds `botMetadata` |
| BotMetadata | `C30615DTj` | per-message bot metadata |
| Bot profile record | `C199348dm` | name, description, persona ID string, thumb |

---

## 2. Meta AI JIDs

### 2.1 JIDs found in the code

| Constant | Class | Role | Tier |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) via `AbstractC34361Xw.A00` | **Hatch**, primary. Default profile built in `C223219iv` from flag payload **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) via `AbstractC34361Xw.A01` | Fallback. Gated by flag 27083 | found |
| `165332417282214` | `C14080dr` (server `"lid"`) via `AbstractC34361Xw.A02` | LID counterpart of `…698` | found |
| `1807055946647696` | none | Manus (legacy in 2.26.26.4): **not present** in 2.26.41.6 | found (absent) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), plus `A01` = `DeviceJid` device 0 | Bot-server JID used as a session/device target for a "bot envelope" (CoEx v2 sync request handler `C53148Nnt` encrypts the sync payload to its primary device, log `coexv2 attached bot envelope`), added to recipient device sets (`C12M`), and treated as a bot sender in retry-receipt handling (`C33020EaI`). Not a chat persona | found (usage); purpose beyond that inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID of the built-in default "Meta AI" profile record (`C9i5.A00`: name `Meta AI`, default intro text). Member of the bot-JID test `AbstractC24760wu.A07` together with the next row | found |
| `867051314767696555` | `AbstractC24760wu.A01` (singleton set, `C24770wv`) | Second member of the `A07` bot-JID test (`A07(jid)` = `C24770wv` equal to `…135992` or in this set); `A07` feeds `AbstractC199328dk.A00` (a JID-class predicate). Further purpose not resolved | found (usage), purpose unknown |
| `17015557208` | `AbstractC24760wu.A04` | Phone user string. `A04(jid)` is true for the LID `165332417282214` or for this phone user; used with `A03` (any `C24770wv` bot JID, or PN in the 13135550000-13135559999 / 13165550000-13165550099 ranges) in `E76.A00` (class 10 vs 1) and in the eligibility predicate `C736539v.ARO`. Reads as the PN identity of Meta AI; what those two consumers do with it is not resolved | found (usage), purpose unknown |

Sets in `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; map `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

JID type: the 2.26.26.4 report listed all four as `@s.whatsapp.net`. In 2.26.41.6 the bot JIDs are `C24770wv` with `getServer() = "bot"`; the group/LID one is `C14080dr` with server `"lid"`. Not `s.whatsapp.net` (found).

Phone-number to bot-FBID table: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, about 200 entries, e.g. `13135550002 → 867051314767696`). Used by `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 Routing conversion

```java
// AbstractC24760wu.A01  (getRemoteTargetJidForOutgoingMessage)
if (A08(jid))   // LID jid with user 165332417282214
    return new C24770wv("1807055946647698");
else            // phone jid
    return C0DZ.A08((UserJid) jid);   // PN -> bot JID via AbstractC199338dl table

// AbstractC24760wu.A00
if (jid is bot "1807055946647698") return new C14080dr("165332417282214");  // bot -> LID
if (jid is bot)                      return C0DZ.A07(userJid);              // bot -> phone jid
```

Found: bot JID `…698` ↔ LID `165332417282214`; phone-number bot contacts map to bot JIDs. The method asserts "needs FBID migration" (found).

### 2.3 The `$1` suffix: changed

The 2.26.26.4 report placed `$1` on the routing JID ("wire format", `C1A2.A00()/A01()`). Not found in 2.26.41.6:
- No routing function appends `$1` to a JID. The conversion in 2.2 produces plain bot JIDs.
- `$1` is appended to the persona ID string stored in the bot profile record: `C24121Ab2` does `personaIdString = botFbid + "$1"`; `C223219iv` hardcodes `"1807055946647697$1"` for the Hatch default profile (found).
- That string (`C199348dm.A0A`) is what `C33473Ehf.A0G` writes into `BotMetadata.personaId` (found).

So `$1` belongs to the persona ID, not to the destination JID.

### 2.4 isMetaAI detection

```java
// C39311it
boolean A02() {                       // Hatch
  if (!BRD() || capability("ai_hatch_integration_enabled")) return flag(26189);
  return false;
}
boolean A0E(Jid jid) {
  if (jid == HATCH_697)                 return A02();
  if (jid == FALLBACK_698 || jid == LID_165332417282214) {
    if (!BRD() || capability("ai_maiba_wass_migration_receiving_enabled")) return flag(27083);
  }
  return false;
}
```

Manus branch (flag 25119) is gone. Meaning of `BRD()` and the capability lookup (`C09L.A04`) not resolved (unknown).

---

## 3. Feature Flags

| Flag ID | Use in 2.26.41.6 | Tier |
|---------|------------------|------|
| **25119** | Appears only in flag tables (`C06510El`, default `false` in `C08J`). No reader found. Old name `ai_bot_integration_enabled` not found as a string | found |
| **26189** | Hatch gate in `C39311it.A02()`. Default `false` (`C08J`) | found |
| **27083** | Fallback / LID gate in `C39311it.A0E()`. Default `false` | found |
| **26190** | JSON config (`name`, `description`, `profile_thumb`) for the default Hatch profile, read in `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. When true, capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) is advertised to Hatch (see 5); `A05` also gates connector telemetry/UI (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Advertises `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); also gates connector availability (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Advertises `HATCH_ARTIFACT_CARD_ENABLED` (79); also read by `HatchSpacesSync` and `C7WL` | found |

Strings `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` are not flag names. They are entries of a feature-string list built from flags 26189 / 27083 in `C25056AqU` (alongside `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` is added unconditionally. Recipient and purpose of the list not verified.

---

## 4. Proto Fields

### 4.1 Message (`C30628DTw`) top-level

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (single field `message` = 1) | Outgoing message wrapped for the bot; set in `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Bot task |
| `botForwardedMessage` | **104** | `BD2` | Wraps a message holding `richResponseMessage`; set in `F3E` |
| `richResponseMessage` | **97** | `DSY` | AI response. Fields: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Present |
| `botGroupParticipantMessage` | **137** | `BD2` | Present |
| `messageContextInfo` | **35** | `C30624DTs` | Carries `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Carries `aiMetadataOperation` (31) |

Field **77** is `commentMessage`, not `richResponseMessage` (the 2.26.26.4 report had 77; wrong for this build, and consistent with the separate richResponseMessage research: 97).

### 4.2 WebMessageInfo (`C30626DTu`), not ContextInfo

The 2.26.26.4 report listed these as ContextInfo fields. In 2.26.41.6 they are on `WebMessageInfo`:

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Set in `C34385EwW` from `C0DZ.A09(userJid)` (primary device user of the invoker) |
| `isSupportAiMessage` | **70** | bool | Set in `C34378EwP.C57` when the message has flag bit `268435456` and a check passes; read back in `C59`. Together with `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Citations |
| `botTargetId` | **73** | string | No writer in the client: `botTargetId_` appears only as the constructor default and in the schema table of `C30626DTu`, never assigned elsewhere (full-source grep) |
| `agentId` | **47** | string | Present, not analysed |

Whether and how these WebMessageInfo fields appear on the wire is not verified (unknown). "`true` for all Meta AI messages" is not supported: it is set per message flag, not unconditionally.

### 4.3 MessageContextInfo (`C30624DTs`)

| Field | Number | Type |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `personaId` | **2** | string | From the bot profile record (`C199348dm.A0A`), e.g. `1807055946647697$1`. Not a fixed `"meta_ai"` |
| `pluginMetadata` | **3** | `DTL` | Plugin config |
| `invokerJid` | **5** | string | Invoker |
| `aiConversationContext` | **20** | bytes | Conversation state |
| `botResponseId` | **26** | string | Response ID |

Other fields present (names from `*_FIELD_NUMBER`, types not read): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` is filled in `C33473Ehf.A0G`; it returns early if the profile has no persona string.

### 4.5 PluginMetadata (`DTL`)

| Field | Number | Type | Value |
|-------|--------|------|-------|
| `provider` | **1** | int32 | Provider ID |
| `pluginType` | **2** | enum `C4E0` | See below |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

`C4E0` constants (value = constructor ordinal; equals proto number is inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. The old 8/9/15 values are unchanged; the enum is larger.

### 4.6 Action oneof (`C61331Rfl`, case enum `EnumC61601RkN`)

| Number | Case | Tier |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

This is a oneof of action fields, not a plain value enum. Where it is embedded is not traced (unknown).

### 4.7 AI metadata operation (Hatch carrier)

| Message | Field | Number | Type |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Request Protocol (Hatch metadata)

Requests are built by `HF1` (`HatchMetadataRequestManager`), coroutine class `HatchMetadataRequestManager$sendRequest$2`. The JSON envelope differs from 2.26.26.4: `method` and `params` are nested under `payload`.

```json
{
  "version": 1,
  "type": "req",
  "payload": {
    "method": "<method_name>",
    "params": { },
    "accepts_encoding": ["gzip"]
  }
}
```

`params` and `accepts_encoding` are optional (found). The request ID is not in the JSON; it is `BB2.requestId` (a random string from `C20F.A0x()`).

Send path (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Pending requests: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) and `HF1.A03` (requestId → `GuR`). Both cleared in `finally`. The 2.26.26.4 report named only one map `A02`.
- Timeout: returns `GDB.A00` and logs `HatchMetadataRequestManager/sendRequest timed out method=`.
- The integer `138` passed to `C37393GKy` is not resolved (unknown).
- Carrier is `ProtocolMessage.aiMetadataOperation` (field 31), not a plain chat message (changed).
- The package `com.whatsapp.bot.infra.message.aimetadata` contains `Ideas*Wire` / `Idea*Wire` classes (found). Their relation to the method names is inferred only; method names were not enumerated.
- The receive side that completes `A04` was not traced. Matching a response to `requestId` is inferred from the `A04` map and `BB2.requestId`.

**No custom XMPP namespace** claim: no `w:ai` / `wa:ai` handling seen in the traced path; absence-based, not re-verified exhaustively.

**Capability advertisement (found, `C33284Eea`):** when the destination is the Hatch JID `…697` (`AbstractC34361Xw.A00`) and a gate passes, the client builds `DPJ` (single repeated enum field `capabilities` = 1, values `EnumC32144E2q`) and `C33473Ehf.A06` stores it in `BotMetadata.capabilityMetadata` (13) of the outgoing message, together with `BotMetadata.timezone` (8) = the device `TimeZone` ID. Capabilities added by gate:

| Gate | Capability (enum number) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

The numbers are the second constructor argument of the enum; that they equal proto numbers is inferred. The enum also lists rich-response capabilities (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Request examples (found, `params` keys read at the call sites; target is the Hatch JID `…697` unless the call site uses the conversation JID):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | built in `HatchIdeasManager$execute$job$1` (keys not read); `onPart` callback attached |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` serialised to JSON; `onPart` callback attached |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` only when non-empty) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Shape of the bytes in `BB2.data` (found shape, example values):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` is written only when the caller's `acceptsGzipResponse` is true; `params` only when non-null. The `onPart` callback is registered in `A03` only when the caller passes one.

**Chat message to the bot (found parts):**
- The outgoing `Message` is re-wrapped into `Message.botInvokeMessage` (`F2K`, `C33284Eea`), the wrapper `BD2` holding the message in field 1. In `F2K` the wrap is skipped (message set directly) when `C13S.A00()` is false, the message's `A10` is false, or flag **10646** is on (found).
- `BotMetadata` is built by `C33473Ehf.A0E` / `A0G`. `A0G` looks up the profile record for the target bot JID (`C199358dn.A06(userJid)`, persona string `C199348dm.A0A`); if that string is empty the method returns without writing bot metadata, otherwise it sets `personaId` (2) and, when present, `suggestedPromptMetadata` (4) and further sub-messages. The persona string is stored when the profile record is created (`C24121Ab2` builds `<id>$1`; `C223219iv` hardcodes `1807055946647697$1` for Hatch). Whether `messageContextInfo` lands on the outer `Message` or on the message inside `botInvokeMessage` was not resolved.
- `botMessageInvokerJid` / `isSupportAiMessage` are set on `WebMessageInfo` by D36 hooks (`C34385EwW`, `C34378EwP`).

---

## 6. Response Protocol

### 6.1 Transport

Not re-verified as stated in 2.26.26.4 ("normal messages with `hatchMetadataSync` bytes", class `Azz`). Found: `hatchMetadataSync` lives in `C25754B9o` inside `ProtocolMessage.aiMetadataOperation`. Hatch responses presumably arrive the same way and match by `requestId` (inferred). Hatch requests are method calls; they are not shown to be the path of normal chat replies.

### 6.2 Streaming / chunks: not supported as described

The 2.26.26.4 table (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) as one Meta AI streaming mechanism is not supported in 2.26.41.6:

| Field | Where it is in 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` field **7** (history-sync notification, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) and `C25838BCy` field **5** (history sync) |
| `isLastChunk` | `C55285Ou6` field **8** (message with `attestationBundles`, `teeModelConfig`, `violationSignal`; TEE-related) |
| `streamingSidecar` | field **18** on image/video/audio messages (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | not found as proto fields |

No chunk reassembly of Meta AI replies found. What exists for Hatch: `GuR(method, onPart)` — an `onPart` callback per request (found); that it carries partial results is inferred from the name.

### 6.3 Rich response (field 97)

`richResponseMessage` (`DSY`) = field **97** on `Message`. Rendering classes exist: `AiRichResponseFooterView` and `UnifiedResponseActionHandlerFactory` (package `com.whatsapp.conversationrow.botrichresponse`) (found). Citations: `WebMessageInfo.supportAiCitations` (72). Content types (images, tables, code) not re-verified here; see the separate richResponseMessage research.

### 6.4 Typing indicator

Outgoing (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): standard XMPP chat state, no custom namespace in the code read.
- Plain case (no mentioned bot, or a bot JID resolved to the default one): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot mentioned in the chat: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Sent through `C10140Tq.A0X` with IQ-type int 4.

Incoming (found, `C40511kx` stanza handler): a `<chatstate>` with a `composing` child (optional `media`) calls the generic composing callback with `from`/`participant`; `paused` calls the paused callback. No bot-specific branch was found in this handler, so a bot-JID `composing` goes through the same path as any contact (inferred; a server-side bot typing stanza was not observed). `BotMetadata.progressIndicatorMetadata` (12) and the capability `PROGRESS_INDICATOR` exist as a separate in-message progress mechanism (names only, not traced).

### 6.5 Bot profile sync

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) schedules `BotProfileForChatListWorker` in `A03()`: a WorkManager request tagged `BotProfileSyncManager` with `setBackoffCriteria(policy, 1, MINUTES)` and a constraint (type value not resolved). The 1 minute is a retry **backoff**, not a period. The 2.26.26.4 "every ~1 minute" is not supported (changed). `A02(groupJid, userJid)` requests a single profile (`requestBotProfileResult`). Not part of normal roster sync (unchanged).

Profile record `C199348dm`: bot type (`C1XY`), jid, display name (`A09`), description (`A07`), persona string (`A0A`), thumbs, timestamp.

### 6.6 Bot type strings

`C718732k.A00(String)` maps: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; anything else becomes `AnonymousClass399(str)`. These are bot-type labels (also used in UI filters), not `BotMetadata.personaId` values (found).

---

## 7. Storage

- `MetaAiMemoryStore`: no class of that name in 2.26.41.6. The equivalent found is a table `meta_ai_memory` created by schema class `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, index `meta_ai_memory_memory_content_index` on `memory_content`. Which database file holds it is not resolved. Related (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; the name says deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (voice call design screen, `C29434Cpx`), capability enums `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), and `BotMetadata.memoryMetadata` (15).
- SharedPrefs key `"meta_ai_forward_disclosure_seen"`: present, boolean, read in `C230589xr.A03` for `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: present at `com.whatsapp.metaai.incognito.infra` (found).
- Separate storage of Meta AI chats outside `msgstore.db` (2.26.26.4, not re-verified): no chat-store class found; `meta_ai_memory` holds memory facts only, so the claim is neither supported nor refuted.

---

## 8. Why Baileys doesn't get a response

All rows are **inferred**: static comparison of the client's requirements with a third-party send path; no live test.

| Issue | Basis in 2.26.41.6 | Tier |
|-------|--------------------|------|
| Wrong target JID type | Bot JIDs use server `bot` (`C24770wv`), not `s.whatsapp.net`; phone-number bots map through a PN→FBID table | found (JID class), inferred (effect) |
| `$1` on the routing JID | Not present. `$1` is on the persona ID string | found |
| Missing `botInvokeMessage` wrapper | Client wraps the outgoing `Message` in field 67 (`F2K`) | found, requirement inferred |
| Missing `messageContextInfo.botMetadata` | Client writes `personaId`, `invokerJid`, etc. into it | found, requirement inferred |
| `personaId = "meta_ai"` | Not what the client sends; it sends the profile persona string (e.g. `1807055946647697$1`) | found |
| Missing `aiConversationContext` | Field 20 of `BotMetadata`; behaviour on first turn unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | WebMessageInfo fields set by client hooks; server requirement unknown | unknown |
| `botTargetId` | No writer in client code | found |
| Reply not parsed | `richResponseMessage` is `Message` field 97 | found |
| Chunk reassembly | Not supported by 2.26.41.6 evidence (see 6.2) | found |

---

## 9. Baileys Fix

No working implementation is claimed. What follows is a structural sketch of where fields live per 2.26.41.6, marked **inferred**; it has not been run against a server.

### 9.1 Target

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Whether the `bot` server string works as a Baileys relay target, and how the server derives the final stanza `to`, is unknown.

### 9.2 Field placement (shape only)

```ts
// inferred shape, field numbers found in 2.26.41.6
const content = {
  botInvokeMessage: {            // Message 67, wrapper with message = 1 (found; wrap is conditional, see 5)
    message: {
      extendedTextMessage: { text }
    }
  },
  // Placement of messageContextInfo (outer Message vs. inner message) is unresolved.
  messageContextInfo: {          // Message 35
    botMetadata: {               // MessageContextInfo 7
      personaId: '1807055946647697$1', // BotMetadata 2: profile persona string (found in C223219iv for Hatch)
      invokerJid: yourJid,             // BotMetadata 5: field exists; writer not read
      timezone: 'Europe/Berlin',       // BotMetadata 8: client sets the TimeZone ID when advertising capabilities (Hatch)
      capabilityMetadata: { capabilities: [/* EnumC32144E2q numbers, Hatch only */] } // BotMetadata 13
      // aiConversationContext (20): field exists; client write not traced, do not invent a value
    }
  }
}
```

- Embedding of `botMetadata` in `messageContextInfo` (field 7) is **found**. `capabilityMetadata` (13) and `timezone` (8) are written by the client only for Hatch destinations (found); their server-side requirement is unknown. Whether the `baron-baileys-v2` proto already has these fields is not checked; if not, the proto must be extended (inferred).
- `isSupportAiMessage` (70) and `botMessageInvokerJid` (58) are `WebMessageInfo` fields. Whether they must be present on the wire is unknown; do not put them in `contextInfo` (that was wrong in 2.26.26.4's report).
- `botTargetId`: no client writer anywhere in the decompiled code (found); do not set it.
- Exact wrapping (`botInvokeMessage.message` containing the real message vs. alongside) follows `F2K` / `C33284Eea` re-wrapping; the exact serialized result was not reproduced (unknown).

### 9.3 Response handling

- Rich replies: `Message.richResponseMessage` is field **97** (found). Parse that, not field 77.
- Remove chunk handling: `chunkOrder` / `isLastChunk` are not Meta AI streaming fields (6.2).
- Hatch `ProtocolMessage.aiMetadataOperation` (31) is the JSON-request channel; plain chat replies are not shown to use it.

### 9.4 Conversation context

`BotMetadata.aiConversationContext` (20) exists. That the server returns updated state in replies and that it must be echoed back is **inferred** (from the field name and the 2.26.26.4 report); not verified.

---

## 10. Flows

### 10.1 Chat message to the bot (found client side, inferred server side)

```
[Client] outgoing Message
    │  F2K / C33284Eea: Message.botInvokeMessage = BD2{ message = original }
    │  C33473Ehf: messageContextInfo.botMetadata{ personaId = profile.A0A, ... }
    │  D36 hooks: WebMessageInfo.botMessageInvokerJid (58), isSupportAiMessage (70)
    ▼
[Routing] AbstractC24760wu.A01: LID 165332417282214 → bot 1807055946647698
    │  phone JID → bot JID via PN→FBID table
    ▼
[WA Server] (not observed; inferred) → Meta AI backend
    ▼
[Client] incoming Message.richResponseMessage (97)  →  AiRichResponseFooterView / UnifiedResponseActionHandlerFactory
```

### 10.2 Hatch metadata request (found client side)

```
[Feature code] HF1.A01(jid, method, params)
    │  requestId = random; A03[requestId] = GuR(method, onPart); A04[requestId] = continuation
    ▼
JSON {"version":1,"type":"req","payload":{"method","params","accepts_encoding"}} → bytes
    ▼
Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
    ▼
[WA Server] (not observed)
    ▼
Response: matched by requestId (inferred) → continuation resumes; timeout → GDB.A00
```

---

## 11. Changes vs 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, flag 25119 | Not present. 25119 only in flag tables, no reader |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 are `bot` server (`C24770wv`); 165332417282214 is `lid` (`C14080dr`) |
| New JID constants | none listed | `1807055946647699` (CoEx v2 bot-envelope / device-set target), `2942131436135992` (default Meta AI profile JID, bot-JID test `A07`), `867051314767696555` (second `A07` member, purpose unknown), `17015557208` (PN of Meta AI, `A04`) |
| `$1` suffix | On routing JID, `C1A2.A00/A01` | Not on JID; appended to persona ID string (`C24121Ab2`, `C223219iv`) |
| Routing conversion | `$1` append | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot via FBID table |
| Flag names 25119/26189/27083 | `ai_*` flag names | Strings are feature-list entries (`C25056AqU`); 26190 = Hatch profile JSON; 37227/37852/37054 gate Hatch capability values 76 / 77 / 79 |
| `richResponseMessage` | Field 77 | Field 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 on "WebMessageInfo" | 67 / 100 / 104 on `Message`; also 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` never written |
| BotMetadata location | "embedded in message" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Profile persona string, e.g. `1807055946647697$1`; `meta_ai` is a bot type label |
| Plugin types | 8, 9, 15 | Same, enum has 18 values (to 17) |
| Action enum | Value enum 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Hatch JSON envelope | `method`, `params` top-level | Nested under `payload`; adds `accepts_encoding` |
| Hatch carrier | Standard message, class `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; adds `bizAiMetadataSync` (2) |
| Pending maps | One (`A02`) | Two: `A04` continuations, `A03` `GuR` part callbacks |
| Streaming fields | One Meta AI chunk table | `chunkOrder` (history sync), `isLastChunk` (TEE message), `streamingSidecar` (media); `clientStreaming`/`serverStreaming` not found |
| Profile sync interval | "every ~1 min" | 1 min is WorkManager backoff, not a period |
| `MetaAiMemoryStore` | Present | Not found by name; table `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) found |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Present | Present |
| Typing indicator (chatstates) | Found | Found: outgoing `<chatstate><composing/></chatstate>`, with `<bot jid/>` when a bot is mentioned (`C199098dN.A01`); incoming `composing`/`paused` via generic handler `C40511kx`, no bot-specific branch |
| Capability advertisement | not documented | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) for Hatch; flags 37227 / 37852 / 37054 map to enum values 76 / 77 / 79 |
| Hatch request examples | not documented | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
