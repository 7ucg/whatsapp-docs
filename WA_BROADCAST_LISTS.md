# WhatsApp Broadcast Lists — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** classic broadcast lists and status broadcasts on Android: `@broadcast` JID model (list / status / location), list creation, membership limits and recipient rules, `w:b` IQs (get lists, delete list, quota), app-state `business_broadcast_list`, LID migration, local storage, per-recipient clone-on-insert, send stanza (sender-key fan-out, `phash`, `bucketing`, `<cap>`, per-recipient ephemeral settings), ack and receipt aggregation, monthly broadcast quota, spam-warning bans, GAP, `status@broadcast` posting (`SendE2eStatusJob`, parts, manual buckets), status privacy modes, close-friends and custom audiences, status reply / reaction / mention / notify, status tables, feature flags, Baileys comparison

---

## 1. What it is (technically)

Three server `broadcast` JIDs exist. All are "multi-participant" JIDs (`AbstractC20660pZ`, same base as groups) sharing one send pipeline: the sender encrypts once with a sender key and hands the key to every recipient device pairwise. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tier: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved. Nothing here is **tested**. Obfuscated names were re-resolved in 2.26.41.6 from stable strings (`BroadcastListManager/…`, `BroadcastXmppMethods/…`, `StatusParticipantUserManager/…`, `SendE2eStatusJob/…`, table and pref names).

| Entity | JID form | `Jid.getType()` | Class | Role |
|--------|----------|-----------------|-------|------|
| Classic broadcast list | `<id>@broadcast` | 3 | `C99P` | primary-device list, recipients get 1:1 copies |
| Status broadcast | `status@broadcast` | 5 | `C199018dF` | status posts, audience chosen per post |
| Location broadcast | `location@broadcast` | 6 | `BOC` | exists in the JID model; use not traced (live location inferred from the name) |
| Own status pseudo user | `status_me` (local) | 11 | `C0Dh` | local-only alias, not a wire JID (role inferred) |

Out of scope: newsletters (`SendNewsletterStatusJob` is a separate job), Business campaigns and insights, Android OS broadcasts.

| Component | 2.26.41.6 name | Role |
|-----------|----------------|------|
| JID parser / helpers | `C0DJ.A00` / `C0DZ.A0P`, `A0Q`, `A0h` | `broadcast` server: user `location` → `BOC`, `status` → `C199018dF`, else `C99P`; helpers true for any broadcast (3, 5, 6) / list (3) / status (5) |
| List allocator / manager | `C0YJ.A0E` / `A0K` (`BroadcastListManager`) | new list id / add and remove participants |
| LID filter and migration | `C70552yj` (`BroadcastListLidMigrationHelper`), `C0UV` (migration task) | PN → LID |
| Participant manager / store | `C22300su` (`A0j` add, `A0k` remove), `C14850fN` (`ParticipantUserStore`) | shared with groups |
| List IQs | `C18240lQ` (`BroadcastXmppMethods`), `AKU` (result handler), `BroadcastListQuotaProtocol` + `C9EN` | get lists, delete list, quota |
| Quota client | `C720733k` (repository), `C2EX` (view model), `C74823Ej` (message listener) | monthly cap |
| App-state mutation | `C224469lG` (dispatch), `C26057BNq` (`BusinessBroadcastListMutation`) | `business_broadcast_list` |
| Clone-on-insert | `C231399zG` (`BroadcastCloneOnInsertProcessor`), `AJO` | per-recipient local copies |
| Ack / receipts | `C22500tF`, `C22790ti` (`MainMessageStore`), `C269411e` (`MessageStatusStore`) | server ack, receipt split |
| Encryptor / jobs | `F6P` (`E2eMessageEncryptor`), `SendE2EMessageJob`, `SendE2eStatusJob` | sender key, SKDM, stanza build |
| Incoming verifier | `C34757F6a` (`CompanionSupportVerifier`) | drops list copies on companions |
| Status audience | `C11550Zh` (`StatusInfoStore`), `C182877r0` (distribution info), `C23140uH` (`StatusParticipantUserManager`), `C1889082i` (`StatusCustomListStore`), `C23340ub` (bucketing config) | privacy modes, lists, buckets |
| Status privacy sync | `C48386LBh` (`StatusPrivacySyncMutation`), `C49626LsR` (Wire `StatusPrivacyAction`), `M7H` (mode enum) | app-state action 44 |

---

## 2. JID model

### 2.1 Parsing (found)

| Rule | Value |
|------|-------|
| Server | `broadcast` |
| User `status` / `location` | singletons `C199018dF` / `BOC` |
| Any other user | `C99P`: length 1..20, first char `1`..`9`, remaining chars `0`..`9`, else `C09B` is thrown |

The no-leading-zero rule is read from the `C99P` constructor (smali compares against `0x31`/`0x39`, rest `0x30`..`0x39`). A list is not `g.us`, but it reuses the group participant machinery (3.5).

### 2.2 Allocation (found, `C0YJ.A0E`)

The id is `System.currentTimeMillis() / 1000` followed by `@broadcast`, incremented by one second while a list with that id exists locally. Uniqueness is checked against the local chat list only; no server call precedes allocation (no create IQ exists, 3.3). Whether the server accepts an arbitrary id is not determinable statically.

---

## 3. List lifecycle

### 3.1 Creation (found, partly inferred)

```
[Picker]  "New broadcast" (menu item hidden when BRD() = companion mode), max 256 selected
     ▼
createBroadcastList callback (C222519hZ):
     │   C0YJ.A0E()                                allocate <seconds>@broadcast
     │   A0K.A04(jid, users): C70552yj.A00 → LID filter ; C22300su.A0h → local participants ; contact entry (name "")
     ▼
compose flow opens; system message "You created broadcast list "X" with N recipients"
```

`A0K.A04` emits no IQ and no app-state mutation (found). The first server-visible event is the first send to the list JID (4.2); that the server derives list state from it is inferred. The same allocation is reused for newsletter follower invites (`userActionSendNewsletterFollowerInviteMessages`, found).

### 3.2 Membership limits and recipient rules

| Rule | Value | Tier |
|------|-------|------|
| Max recipients | 256: `ContactPickerFragmentKt.A39` rejects `selected.size() > 256` (`Broadcast to a maximum of %d people at a time`); picker bound `min(256, groupLimit - 1)` | found |
| Recipient source | contact picker; permission text `To create a broadcast … allow WhatsApp access to your contacts`; blocked contacts: `To add to broadcast list, unblock %s` | found |
| Receiver must have the sender saved | UI text only (`Only contacts who have you in their address book will receive your broadcast messages.`); enforcement is server-side | found (text), unknown (enforcement) |
| LID addressing | `A0K.A01` always returns `lid`; PN participants without a LID mapping are dropped (`lid-broadcast-filtered-participants`) | found |
| Missing mapping on send | `missing_pn_lid_mapping_for_broadcast`: clone skipped, encryptor throws `E39(device, 4)` | found |
| Empty participant set | `saveGroupParticipants/broadcast_would_be_cleared`; with flag **30111** (default true) stored participants are kept | found |

### 3.3 Server IQs (found)

Only three IQs touch lists. There is no create or edit IQ.

```xml
<!-- restore: BroadcastXmppMethods/sendGetBroadcastLists -->
<iq to="s.whatsapp.net" xmlns="w:b" type="get" id="…"><lists/></iq>
<iq type="result"><lists>
  <list id="1760000000@broadcast" name="Family">
    <recipient jid="<lid>@lid" pn_jid="<pn>@s.whatsapp.net" username="…"/>   <!-- pn_jid, username read for LID recipients -->
  </list>
</lists></iq>

<!-- delete: sendDeleteBroadcastList -->
<iq to="s.whatsapp.net" xmlns="w:b" type="set" id="…"><delete><list id="1760000000@broadcast"/></delete></iq>

<!-- quota (5.1) -->
<iq to="s.whatsapp.net" xmlns="w:b" smax_id="143" type="get" id="…"/>
```

All three use a 32 s timeout. `AKU` (get result) creates, for every `<list>` without a local chat or contact entry, the chat (`A0K.A00`, system message type 9) and a contact entry, and stores the `pn_jid` and `username` maps. Delete is sent by `C18240lQ.A01` and followed by an app-state REMOVE (3.4).

Restore trigger (found): `RegistrationInitializer/shouldrefreshlists` sets pref `refresh_broadcast_lists=true` and sends get-lists (with get-privacy-settings) after registration; `MessageHandlerCallback/ready` repeats it while the pref is true; `AKU` clears it. The server therefore persists lists per account (found by implication). How it learns a list is not visible client-side (unknown, see 3.1).

### 3.4 App-state mutation (found)

| Item | Value |
|------|-------|
| Action | `BusinessBroadcastListAction`, wire name `business_broadcast_list` (`EnumC24865AnN.A0H`, ordinal 62), `SyncActionValue` field **69**, collection `regular`, API version 7 |
| Index | `["business_broadcast_list", "<list jid>"]` |
| Operation | SET on add, remove, rename; REMOVE with `deleted=true`, empty participants, name `""` on list deletion (`A0T`, `syncBusinessBroadcastListRemoval`) |
| Gate | `C12440bB.A0b()` (syncd not blocked or companion-dirty); Business hooks (`storeForBroadcast`, `onAudienceChanged`, `getCustomAudienceFbidForBroadcast`) are absent in this APK |
| Callers | `A0K.A03` / `A05` (add / remove), rename in `BroadcastListChatInfoActivity`, `C24085AaS` (participant set) |
| Apply side | no handler references `EnumC24865AnN.A0H`; only the writer (`C26057BNq`) and the field accessor in `BD4` exist, so consumer apply behaviour is unknown |

| Field | Number | Type | Value / use |
|-------|--------|------|-------------|
| `deleted` | **1** | bool | list removed |
| `participants` | **2** | repeated `BroadcastListParticipant` | audience (`lid_jid` **1** required, `pn_jid` **2**) |
| `list_name` | **3** | string | subject |
| `label_ids` | **4** | repeated string | label audience (alternative to participants, never both) |
| `audience_expression` | **5** | string | dynamic audience (Business) |
| `custom_audience_fbid` | **6** | string | Business only |

Same collection: `BusinessBroadcastCampaignAction` (81), `BusinessBroadcastInsightsAction` (82), `MarketingMessageBroadcastAction` (39); enum-only `BusinessBroadcastAssociationAction` (59) and `BusinessBroadcastAction` (94). Basics: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md).

### 3.5 LID migration, storage, companions

`BroadcastListLidMigrationTask` (`C0UV`) converts each list from PN to LID participants: one usync for missing LIDs (failure logged as `usync_failed`, task proceeds), then `C70552yj.A03` removes the PN participants and adds the LID set in one transaction.

| Store | Content | Tier |
|-------|---------|------|
| `chat` / `chat_view`, `jid.type = 3`, `subject`, `created_timestamp`, `hidden` | the list chat (`C222989iV`) | found |
| `group_participant_user` (`group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `label`, `add_timestamp`), `group_participant_device` | recipients, shared with groups | found |
| `wa_group_admin_settings` (`jid`, `addressing_mode`, `group_state`) | addressing mode per list (telemetry counts `@broadcast` rows) | found |
| `message` columns `broadcast`, `recipient_count`, `participant_hash`, `key_id`, `chat_row_id`, `from_me` | list message and ack data | found |
| `message_broadcast_ephemeral` (`message_row_id`, `shared_secret`) | per-message secret for list disappearing messages | found |

Companions (found): the `New broadcast` / `Broadcast lists` menu items are added only when `BRD()` is false; `C34757F6a` throws `E3A(415, "received peer broadcast message on companion-mode, dropping", 18)` for an own-account list copy that carries `<participants>`; action 69 has no apply handler.

---

## 4. Sending to a list

### 4.1 Local fan-out (found, `C231399zG`)

```java
// A02(msg): msg.fromMe, not one of two excluded message classes, status 0 or 2 (or 4 with flag 26867)
msg.A0Z = true;                                   // message.broadcast = 1
for (recipient : msg.A0A())                       // recipient list stored on the FMessage
    normalized = lidMapper.A0C(recipient);        // null → missing_pn_lid_mapping_for_broadcast, skip
    store.add(cloneFactory.A00(msg, new C1ZA(normalized, msg.key.id, true)));   // own row in the recipient's 1:1 chat
```

| Property | Value |
|----------|-------|
| Message id | identical for the list message and every clone (`key_id` copied, only the chat differs) |
| Counts | `recipient_count` (`FMessage.A06`) on the list row; media file reference count raised by the clone count |
| Duplicates | `SQLiteConstraintException` on an existing clone key is logged and skipped |
| Disappearing messages | clone takes the per-recipient setting from the ephemeral map (keyed by recipient primary device); expiry rows in `message_ephemeral` |

### 4.2 Wire format (found, partly inferred)

One stanza addressed to the list JID (example, attribute values illustrative). Encryption reuses the group path (`F6P` is typed on `AbstractC20660pZ`): one sender-key ciphertext plus per-device sender-key distribution messages. Sender-key and session basics are not repeated here.

```xml
<message to="1760000000@broadcast" type="text" id="3EB0…" t="…" phash="2:AbCdEf==" addressing_mode="lid">
  <participants>
    <to jid="<recipient device jid>"><enc v="2" type="pkmsg|msg" …/></to>   <!-- SKDM wrapped pairwise -->
  </participants>
  <enc v="2" type="skmsg" …/>                                                <!-- message under the sender key -->
  <cap client_capping_ready="true|false"/>                                   <!-- flag 16656 only -->
</message>
```

| Attribute | Source | Notes |
|-----------|--------|-------|
| `to`, `type`, `id`, `t` | chat JID (`C33150EcP.A07`), `AbstractC30999De0.A02`, `C1ZA.A01`, `originalTimestamp` | `to` is the list JID (inferred from the shared builder); `t` only when non-zero |
| `phash` | `groupParticipantHash` | 4.3 |
| `bucketing` | `eva.A05` | `primcomp` when flag **28183** and participant count ≥ **28185** (512); lists (≤ 256) stay unset in practice (inferred) |
| `addressing_mode` | `lid` | omitted for type-28 JIDs |
| `participant`, `recipient`, `recipient_pn`, `peer_recipient_pn`, `peer_recipient_username` | job fields | peer / retry / DSM sends |
| `edit`, `expiration`, `device_fanout="false"`, `privacy_sensitive="1"` | job fields | optional |

Children come from contributors (`InterfaceC35538FaZ.ASY`, `processStanzaNodeParamsUsingNewFramework`). `F69` adds `<cap client_capping_ready="…"/>` for list chats when flag **16656** is on; the value is flag **13537**.

| Step | Detail | Tier |
|------|--------|------|
| Recipient devices | participant manager set minus device types 26 / 27 (`F6P.A07`, hosted devices inferred); for list chats `AxolotlMultiDeviceSessionRequirement` adds the own companion devices (`BPE`: own user, non-primary) to the SKDM target set | found / inferred |
| Sender key name | (own device address, `groupId` string `A0J`); `A0J` is written into `SenderKeyDistributionMessage.groupId`; status `-1002` from `encryptForGroup` = invalid sender key, rotated | found |
| Per-recipient ephemeral blobs | `F6P.A0A` (`buildBroadcastListEphemeralSettings`): for each recipient device missing from the pairwise map (own companions skipped) builds `EphemeralSetting(expiration or afterReadDuration, timestamp)` and encrypts it natively with the message's `shared_secret` (`JniBridge.jvidispatchOOOOOOO`); missing setting throws `E39(device, 4)`. Purpose (per-recipient timers inside one stanza) inferred | found / inferred |
| Own devices | message wrapped in `DeviceSentMessage` with `destinationJid = list` and `phash` of the recipient devices (`C33284Eea.A01`) | found |
| Size | `BoundedStanzaSizeException` → `stanza-too-large` / `large payload` | found |

### 4.3 `phash` (found, `AbstractC44221r5`)

`<version>:` + base64 (`NO_WRAP`, padding kept) of the first 6 bytes of SHA-256 over the sorted recipient devices. Version `2:` hashes `user.0:device@server` strings (flag **16731** false, default); version `3:` hashes the device raw strings (flag **16731** true). Used for group, list and status stanzas.

### 4.4 Ack and receipts (found)

| Event | Handling |
|-------|----------|
| Server ack | `C22500tF` → `C22790ti.A04`: for list chats (not status) updates `message` where `chat_row_id IN (list chat, every clone chat) AND from_me = 1 AND key_id = ?` with `status`, `receipt_server_timestamp`, `recipient_count`; falls back to a scan by `timestamp/from_me/key_id` (`UPDATE_RCV_BROADCAST_SERVER_SQL`, log `message-table-scan`) when the recipient list is shorter than `recipient_count` |
| Recipient receipt | `MessageStatusStore.splitStatusUpdateReceipts`: a receipt for the list key is mapped to the clone `(normalized recipient, same id, fromMe)` and applied to the clone (`broadcast-individual`) and the multi message; status downgrades dropped (`broadcast-statusdowngrade`); unknown clone logs `nosuchmessage for broadcast` |

The summary status rule of the list row and what a recipient's phone shows are unresolved (unknown).

---

## 5. Limits and abuse controls

### 5.1 Monthly broadcast quota (found, consumer path)

```
iq get xmlns=w:b smax_id=143
  → <limits is_heavy_sender="true|false" messages_left="N" total_limit="M"/>
    <timeframe start_ts_s="…" reset_ts_s="…" end_ts_s="…"/>
```

Client range checks: `messages_left` 0..300, `total_limit` 1..300, timestamps 2020-01-01..2100-01-01. Error IQ codes map to client results `400` → 3, `401` → 4, `403` → 5, `500` → 1, other → 0, no connection or delivery failure → 2 (`consumer_broadcast_capping_iq_error_response`).

| Mechanism | Detail |
|-----------|--------|
| Cache | prefs `broadcast_quota_messages_left`, `_message_limit`, `_last_timestamp_fetched_ms`, `_heavy_sender`, `_start_timestamp`, `_end_timestamp`, `_reset_timestamp` |
| Refresh | when time since last fetch exceeds flag **13818** minutes (default 1440) or now ≥ `reset_ts_s` (combination garbled in the decompile, OR inferred) |
| Decrement / increment | `C74823Ej`: per added list message flagged `broadcast` and not in an exempt message-type set (`C2EX.A00`), per message not per recipient; incremented back on deletion of unsent list messages, capped at `total_limit` |
| Pre-send block | predicate in `C20M`: list chat and flags **16585** and **13537** and `messages_left == 0` → send refused, bottom sheet `You've reached the broadcast limit for this month` |
| UI / telemetry | `Send up to %d broadcasts per month`, onboarding sheet for heavy senders (`CappingBroadcastManager`); `wam_broadcast_list` (`blLimit`, `currentBlSends`, `numBlLists`, `broadcastListSize`) |

The cap value is server-provided; only the range check is in the client. Business-side hooks (`isSmbPremiumBroadcastCappingEnabled`) are stubs in this APK.

### 5.2 Spam-warning bans (found)

`SpamWarningActivity` takes a server code (`spam_warning_reason_key`), `expiry_in_seconds`, optional server text and FAQ URL. Codes: **101** messages to people without the sender in their address book, **102** too many blocks, **103** groups with people who do not have the sender saved, **104** same message to too many people, **106** too many messages to a broadcast list; others show the generic terms-of-service ban. Delivery path and the rest of the ban surface: [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md). Thresholds are server-side (unknown).

### 5.3 Config 20278 and GAP

- Config **20278** exists only as a default string `{"max_messages": 10000, "farthest_time_days": 30}` in two default tables. No other reference to `max_messages` / `farthest_time_days` exists in the consumer code, so no reader was found. It is not the consumer list cap (5.1); its use is unknown (Business-side default).
- GAP (`com.whatsapp.gapenforcement`, flag **14837**, default false) is receive-side: `GapEnforcementTrigger.onMarketingMessageReceived` and `RulesManager` evaluate inbox rules for marketing-message threads (`parseMaxMmThreadsInTopInboxSize`, `parseNoConsecutiveInTopInboxSize`, `parseMinNUpdatedP`) and log accuracy results; it does not run on companions and does not limit sends from lists. The acronym expansion is not in the APK (unknown).

---

## 6. status@broadcast

### 6.1 Send pipeline (found)

`SendE2eStatusJob` has a type (`EnumC32060Dzj`): `STATUS` 0 (the post, table `status`), `STATUS_ADD_ON` 1 (reactions and other add-ons, `status_add_on`), `STATUS_NOTIFY` 2 (reply / reshare / mention notifications, `status_notify`). The stanza uses the attribute builder of 4.2 plus `<meta>` contributors (example, attribute values illustrative):

```xml
<message to="status@broadcast" type="media" id="3EB0…" phash="2:…" bucketing="manual" addressing_mode="lid">
  <participants><to jid="<device>"><enc v="2" type="pkmsg|msg"/></to>…</participants>
  <enc v="2" type="skmsg" bucket="f1"/>                      <!-- one per bucket when bucketed -->
  <meta status_setting="contacts" session_scope="status"/>
</message>
```

| Attribute | Accepted values (stanza value sets, `C9E2`) |
|-----------|---------------------------------------------|
| `status_setting` | `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist` |
| `content_type` | `add_on`, `status_notify` |
| `message_association_type` | `av1_video_dual_upload`, `hd_image_dual_upload`, `hd_video_dual_upload`, `hevc_video_dual_upload` |
| `interaction_type` | `question`, `question_reshare` (with `parent_server_id`, `response_server_id`) |
| `bucketing` | `manual`, `primcomp`, `threebuckets` (`threebuckets` only in the value set) |

| Item | Detail |
|------|--------|
| Ack timeout | 300000 ms (`no ack within 300000ms`) |
| Parts | large audiences are split: `status_send_part` (`status_row_id`, `part_code`, `is_first_part`, `device_count`, `state`, `sent_timestamp`, `ack_timestamp`, `error_code`, `stanza_devices_hash`); device tracking in `status_receipt_device` (`uuid`, `receipt_device_jid`, `receipt_device_timestamp`, `primary_device_version`, `part_code`) |
| Group status | `buildGroupStatus called with non-PermanentGroupJid`; `is_group_status`; Message fields 92 / 96 / 103 |
| Build failures | `StatusStanzaBuildFailureReason`: `MISSING_RETRY_CIPHERTEXT`, `TARGETS_UNRESOLVABLE`, `PART_ATTEMPT_PERSISTENCE_FAILED`, `CANONICAL_ACK_PENDING`, `EMPTY_FANOUT`, `NON_CURRENT_BATCH`, `MISSING_SENDER_KEY_CIPHERTEXT`, `UNKNOWN` |
| Job failures | `encryption_limit`, `out_of_memory`, `payload_too_large`, `stanza_error`, `stanza_too_large` (handled when flag **29113** is on), `unrecoverable_error` |

### 6.2 Audience: privacy modes (found)

The audience is resolved on the sender and expanded to explicit recipient devices; the `status_setting` attribute only labels the mode. Local state: `C11550Zh` (prefs `status_distribution`, `status_distribution_modes`, `status_white_list`, `status_black_list`).

| Local mode | Name | `status_setting` | Wire `M7H` (app-state) |
|------------|------|------------------|------------------------|
| 0 | My contacts | `contacts` | `CONTACTS` 2 |
| 1 | Only share with | `allowlist` | `ALLOW_LIST` 0 |
| 2 | My contacts except | `denylist` | `DENY_LIST` 1 |
| 3 | unset fallback of `C182877r0.A01()`; refused by the sync mutation (`StatusPrivacySyncMutation invalid status setting`) | | |
| 4 | custom audience / close friends | `customlist` / `closefriends` (inferred) | `CUSTOM_LIST` 4 (`CLOSE_FRIENDS` 3 exists in the enum, not produced) |

Local-to-wire mapping (found, `C48386LBh.A04`): 1 → 0, 2 → 1, 4 → 4, else 2. Mode names for 0..2 are also logged by the send job as `contacts` / `allowlist` / `denylist`.

Server privacy lists use the `privacy` IQ, category `status` (category name from `AboutStatusPrivacyActivity`):

```xml
<iq to="s.whatsapp.net" xmlns="privacy" type="get" id="…">
  <privacy addressing_mode="lid"><list name="status" value="contact_allowlist|contact_blacklist" dhash="…"/></privacy>
</iq>
<iq xmlns="privacy" type="set"><privacy><category name="status" value="contacts|contact_blacklist|contact_allowlist"/></privacy></iq>
```

(`AbstractC230749y7.A02`, `C228009tS`, `C18260lS.A0P`; get is MEX / SMAX / shadow by flag **23463**, set via MEX when **23639**, else SMAX.)

### 6.3 Custom audiences and close friends (found)

UI strings: `New: Close friends`, `People you include see a purple ring on your status`, `Create audience`, `Choose name & emoji`.

| Item | Value |
|------|-------|
| Table `status_privacy_custom_list` | `row_id` (PK), `list_id` (unique), `name`, `emoji`, `is_selected` (default 0), `member_jids`, `source_group_jids`, `allow_list_selected`; kept in both the message store and the status store (`*_MSGSTORE_DB`, `*_STATUS_DB`) |
| App-state | `status_privacy` (ordinal 38, `regular_high`, field **44**); `StatusPrivacyAction`: `mode` **1**, `user_jid` **2**, `shareToFB` **3**, `shareToIG` **4**, `custom_lists` **5**, `modes` **6**; `StatusCustomList`: `list_id` **1**, `name` **2**, `emoji` **3**, `is_selected` **4**, `user_jid` **5** |
| Per-post record | `status_message_info`: `status_distribution_mode`, `selected_audience_list`, `audience_type`, `status_audience_custom_list_name`, `_emoji` |
| Validation | `StatusParticipantUserManager/validateAudience` (includes a `HAS_STATUS_AUDIENCE` check over `wa_contacts`), `StatusEmptyAudienceGuard` in the composers |

Related: `userStatusMute` (ordinal 23, field 29, `muted`). Multiple simultaneous modes need flag **28731**, the custom-list store **27031** (both default false; status-config helpers `A0F` / `A0I` also gate this, unresolved).

### 6.4 Manual sender-key buckets (found)

| Item | Detail |
|------|--------|
| Table `manual_user_group_bucket` | `row_id`, `user_jid_row_id`, `multi_participant_jid_row_id`, `status_audience`, `bucket`; unique index on user + group |
| Audience names / bucket prefixes | `contacts` → `c`, `close_friends` → `f`, `allow_list` → `a`, `close_friends:<id>` → derived prefix; other names throw `Unknown manual SKB audience name` |
| Store / planning | `ManualBucketStore/assignUsersToBuckets`, `deleteRowsForBuckets`, `getHoldersByBucketForGroup`; `ManualBucketingUtils/planSend`, `trimToEncBudget`; `SenderKeyBucketingRollback/cleanupBucketedState` |
| Flags | **28184** + rollout cap **34545** (0 = all) enable manual bucketing for status (`C23340ub.A01`) |

### 6.5 Reply, reaction, mention, notify (found)

| Interaction | Mechanism |
|-------------|-----------|
| Reply | normal 1:1 message quoting the status (`status_reply`: `status_row_id`, `ref_id`, `reply_timestamp`); `Message.statusQuotedMessage` (field **109**) for question replies |
| Reaction / add-on | job type `STATUS_ADD_ON`; `status_add_on` (`status_row_id`, `type`, `uuid`, `sender_user_jid`, `state`, `sender_timestamp`, `is_revoked`, `content_proto`, `secret`); per-post gates `cannot_receive_reactions`, `can_receive_multi_reactions` |
| Mention | `status_message_info.is_mentioned`, `status_mentions`, `status_mention_source`; `Message.statusMentionMessage` (field **87**) is a single-field wrapper (`message` **1**) unwrapped like `viewOnceMessage` (`C35228FOg`); further semantics inferred |
| Notify | `Message.statusNotificationMessage` (field **98**): `responseMessageKey` **1**, `originalMessageKey` **2**, `type` **3** (1 add yours, 2 reshare, 3 question-answer reshare, 4 group status reply); stored in `status_notify` |
| Related fields | `groupStatusMentionMessage` **92**, `groupStatusMessage` **96**, `groupStatusMessageV2` **103**, `statusQuestionAnswerMessage` **105**, `statusStickerInteractionMessage` **110** |

### 6.6 Status storage (found)

| Table | Key columns |
|-------|-------------|
| `status` (status store) | `uuid`, `sender_user_jid`, `status_info_row_id`, `type`, `timestamp`, `server_receipt_timestamp`, `state`, `secret`, `content_proto`, `origin`, `flags`, `audience_type`, `stanza_xml`, `batch_state` |
| `status` (message store, legacy summary), `status_info` | `jid_row_id` / `chat_jid`, `unseen_count` / `unread_count`, `total_count`, `unread_count_close_friends` |
| `status_message_info` | `message_row_id`, `status_distribution_mode` (3 when unset), mention / reaction / reshare gates, `is_group_status`, `ranking_version`, audience columns (6.3) |
| `status_send_part`, `status_receipt_device`, `manual_user_group_bucket` | send state (6.1, 6.4) |

The two tables named `status` have disjoint columns and live in different databases (inferred from the `MSGSTORE_DB` / `STATUS_DB` labels). Other tables (`status_media_link`, `status_seen_receipt`, `status_ranking*`, `status_interactions*`) are listed by name only.

---

## 7. Feature flags

Ids as read at call sites; defaults from the compiled default tables.

| ID | Default | Controls |
|----|---------|----------|
| **13537** | false | consumer broadcast capping: lists home, quota fetch / decrement, `client_capping_ready` value |
| **16585** | true | block list sends when `messages_left == 0` |
| **16656** | false | adds `<cap client_capping_ready/>` to list stanzas |
| **13818** | 1440 | quota refresh interval (minutes) |
| **15515** | true | capping UI helper (`C33z.A08`, with 13537) |
| **19790** | false | when true, clone-on-insert skips quoted-message mapping |
| **26867** | true | clone-on-insert branch for status-4 sent messages (meaning unresolved) |
| **30111** | true | keep stored list participants when a save would clear them |
| **16731** | false | `phash` variant `3:` instead of `2:` |
| **28183** / **28184** | false / false | `primcomp` bucketing master / manual status bucketing |
| **28185** / **28199** / **34545** | 512 / 2 / 0 | bucketing participant threshold / second int (unresolved) / rollout cap |
| **28731** / **27031** | false / false | multiple status modes / custom list store |
| **29113** | false | stanza-too-large handling for status |
| **23463** / **23639** / **23874** | 0 / false / false | privacy get protocol (1 MEX, 2 shadow, else SMAX) / privacy set via MEX / privacy list fetch path |
| **14837** | false | GAP enforcement |
| **20278** (string) | `{"max_messages": 10000, "farthest_time_days": 30}` | Business broadcast limit default, no consumer reader |

---

## 8. Baileys (`baron-baileys-v2`, checked against its source)

| Area | Implementation | Verdict against 2.26.41.6 |
|------|----------------|---------------------------|
| Status send | `messages-send.js`: `isStatus`, `statusJidList` appended to the participant list, `<meta status_setting session_scope="status">` | matches 6.1 / 6.2; `statusPrivacy` is not validated (valid: `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist`) |
| Audience scale | explicit `statusJidList`, no buckets, no `bucketing` attribute | large audiences hit stanza limits (6.1) |
| Delete list | `deleteBroadcastList`: `w:b` set, `<delete><list id/></delete>` | matches 3.3 |
| Quota | `fetchBroadcastListQuota`: `xmlns="w:biz"` with child `<broadcast_list_quota/>` | request does not match (`w:b`, `smax_id=143`, no child); response parsing matches |
| Get lists / app-state / list send | not implemented / `businessBroadcastListAction` emitted as `settings.update` / `isJidBroadcast` for decoding only | see below |

| Symptom | Cause | Fix |
|---------|-------|-----|
| classic-list send dropped or rejected | lists are primary-device state: companions hide the feature, drop own-account list copies with `participants` (415), no create IQ exists | do not target list JIDs from a companion; send per-recipient 1:1 messages or use `status@broadcast` with `statusJidList` |
| recipients unresolvable | no member lookup for lists on companions; participants are LID-addressed and filtered by mapping | resolve LIDs through usync first |
| quota request errors | wrong namespace | `xmlns="w:b"`, `smax_id` 143, `type="get"`, `to="s.whatsapp.net"` |

Separate 1:1 sends are transport-compatible but are not a classic list (no list chat, shared id or quota).

---

## 9. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `missing_pn_lid_mapping_for_broadcast`, `lid-broadcast-filtered-participants` | recipient PN has no LID mapping | fetch LIDs (usync) before adding or sending |
| 415 `received peer broadcast message on companion-mode` | list copy with `participants` on a companion | expected, companions do not process list sends |
| send blocked, limit sheet | `messages_left == 0` with 13537 and 16585 | wait for `reset_ts_s`, delete unsent list messages |
| ban code 106 | too many messages to a broadcast list | wait for `expiry_in_seconds` |
| `broadcast_would_be_cleared` | participant save with an empty set | flag 30111 keeps participants |
| `EMPTY_FANOUT` | audience resolved to zero devices | fix the audience, `StatusEmptyAudienceGuard` should block earlier |
| `stanza_too_large`, `payload_too_large` | too many devices or payload | parts / buckets (6.1, 6.4), flag 29113 |

---

## 10. Key distinctions

| Do not confuse | Difference |
|----------------|------------|
| List (type 3) vs `status@broadcast` (type 5) | list: stored recipients, per-recipient clones, monthly quota; status: audience per post, no clones, own tables |
| List vs group | same participant store and sender-key path; list is primary-only, recipients are not members and see 1:1 chats |
| Server `w:b` lists vs app-state action 69 | `w:b` restores lists after registration; action 69 is written for sync and has no consumer apply handler |
| Quota (`w:b` smax 143, ≤ 300) vs config 20278 (10,000 / 30 days) | quota is server-provided and UI-enforced; 20278 has no consumer reader |
| Quota vs ban code 106 vs GAP | soft cap with UI / server-issued temporary ban / receive-side inbox rules |
| `privacy` IQ vs custom audiences | IQ holds three server modes; custom lists and close friends are local plus app-state action 44 |

---

## 11. Complete flow

```
[User]  New broadcast → select ≤ 256 contacts
     ▼
[Client]  C0YJ.A0E → <seconds>@broadcast ; A0K.A04 → LID filter, group_participant_user rows
     │     send → message.broadcast = 1 ; C231399zG clones into each recipient chat (same key id)
     │     quota gate: 13537 + 16585, messages_left > 0
     ▼
[SendE2EMessageJob]  F6P: skmsg + SKDM per device (pkmsg/msg) + ephemeral blobs ; DSM to own devices (phash)
     ▼
<message to="<id>@broadcast" phash id><participants>…</participants><enc type="skmsg"/><cap/></message>
     ▼
[WA Server]  (not observed) fan-out, ack
     ▼
ack → C22500tF updates list row + all clones ; receipts → splitStatusUpdateReceipts ; quota decremented on add

[User]  status: choose audience (contacts / allow / deny / close friends / custom)
     ▼
[Client]  validateAudience → StatusEmptyAudienceGuard ; users → LID → devices ; buckets c / f / a when 28184 on
     ▼
[SendE2eStatusJob]  type STATUS ; status_send_part rows ; sender key per bucket
     ▼
<message to="status@broadcast" phash bucketing><participants>…</participants><enc type="skmsg" bucket/><meta status_setting session_scope/></message>
     ▼
[WA Server]  (not observed) ack within 300 s ; viewers reply / react
     ▼
status_add_on / status_notify / status_reply rows ; status_receipt_device bookkeeping
```

---

## 12. Unknowns

| Item | Status |
|------|--------|
| How the server registers a list (only get / delete / quota IQs exist) | send-time registration inferred |
| Server rule that recipients must have the sender saved; list size and quota values | server side (UI text and range checks only) |
| Consumer apply behaviour of app-state action 69 | no handler found |
| What recipients receive for a list message; summary receipt rule of the list row | not visible from the sender |
| Quota refresh combination, exempt message-type set | decompile garbled / not traced |
| Local status mode 3, `threebuckets`, flags 28199, 26867, 15515, status-config `A0F` / `A0I` | unresolved |
| Use of `location@broadcast`; expansion of "GAP" | not traced / not in the APK |
| Traffic | nothing captured |
