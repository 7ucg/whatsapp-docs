# WhatsApp Group History — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** group history sharing on Android (recent group messages sent to new members): admin setting `member_share_group_history_mode`, sender and receiver eligibility, add / approval join flow and pending job, message selection and limits, `MessageHistoryBundle` (field 70) and `MessageHistoryNotice` (field 102), inner `GroupHistory` proto, bundle media encryption and upload, receiver validation and import, group metadata (participants, LID vs PN addressing, community relations), sender-key use, reporting tokens, companion HistorySync (`HistorySyncConfig`, sync types, on-demand peer operations), feature flags, Baileys

---

## 1. What it is (technically)

Group history sharing lets a group member (admin, or any member if the admin allows it) push a bundle of recent group messages to people who were just added, so the newcomer sees context. It is a normal end-to-end encrypted group message whose payload is a media file (a protobuf of `WebMessageInfo` entries). It is **not** the companion-device HistorySync (section 11), although both share the word "history" and a few capability flags.

All statements come from static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code or resources, **inferred** = deduced from code, **unknown** = not resolved. Obfuscated names were re-resolved in 2.26.41.6 from stable strings (`FMessageGroupHistoryBundleProtobuf`, `GroupHistorySendPermissionChecker`, `PendingSendGroupHistoryJob`, `member_share_group_history_mode`, `Group History`).

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| Bundle message | `C213539Ar` (`FMessageGroupHistoryBundle`), FMessage type **117** | outer media message, `Message.messageHistoryBundle` field **70** |
| Notice message | `C213519Ap` (`FMessageGroupHistoryNotice`), FMessage type **118** | "history was sent" row, `Message.messageHistoryNotice` field **102** |
| Bundle serializer / parser | `C34677F2y` (`FMessageGroupHistoryBundleProtobuf`) | build and validate the outer message |
| Notice serializer / parser | `C34678F2z` (`FMessageGroupHistoryNoticeProtobuf`) | build and validate the notice |
| Bundle builder | `C9mW.A00` (+ `C231239yy`, `FMessageGroupHistoryBundleFactory`) | select, pack, write file, create the media message |
| Message selection | `A0G` (`GroupHistoryMessageManager`) | SQL for count and rows |
| Eligibility | `A1W` (`GroupHistorySendPermissionChecker`), `C230099x1` (gates) | sender / receiver / entry-point checks |
| Pending job | `PendingSendGroupHistoryJob`, `SendGroupHistoryJobRequirement` | durable job after the add |
| Requirement provider | `C197318aR` (`SendGroupHistoryRequirementProvider`) | add / approval events release the job |
| Receiver | `GroupHistoryBundleProcessor`, `GroupHistoryBundleFileProcessor` | download, parse, insert |
| Validators / inserter | `C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg` (`GroupHistoryMessageValidator` / `GroupHistoryMessageInserter`) | per-message checks and DB insert |
| Media type row | `C15530gU.A0F` | `group-history`, `GROUP_HISTORY`, HKDF info `Group History`, id **117** |
| Settings UI | `com.whatsapp.grouphistory.setting.ui.*`, `GroupPermissionsActivity` (`C201678ic`) | amount dialog, footer toggle, permission switch |

Two distinct messages exist per share: the **bundle** (carries the data, sent to the group) and the **notice** (carries only counts and receivers, sent after the bundle left the device, section 5.4).

---

## 2. Group metadata and settings

### 2.1 Group info node (`<group>`, legacy XMPP path `C23201A1a.A0C`)

Parsed by the same helper for `w:g2` queries and group notifications; a MEX/SMAX twin exists (`AbstractC23204A1d`, `AN6`, `C23690AKd`). Only fields relevant here and for addressing:

| Attribute / child | Type | Use |
|-------------------|------|-----|
| `id`, `creation`, `subject`, `s_t`, `s_o`, `s_o_pn`, `creator`, `creator_pn` | attrs | identity; `_pn` twins carry the phone JID next to a LID |
| `addressing_mode` | `lid` or `pn` | stored in `wa_group_admin_settings.addressing_mode`; anything other than `pn` is read as `lid` (`AbstractC268510t`) |
| `<group_history/>` | empty child | boolean presence; stored as `history_enabled`; meaning inferred (feature flag of the group) |
| `<member_share_group_history_mode>` | text | admin setting, 2.4 |
| `<member_add_mode>` | `all_member_add` / other | `member_add_mode` 1 / 0 |
| `parent`, `default_sub_group`, `linked_parent jid`, `general_chat` | children | group type, 2.3 |

### 2.2 Participants and addressing (found)

`<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`):

| Attribute | Use for group history |
|-----------|-----------------------|
| `jid` | participant, LID or PN depending on `addressing_mode`; a PN JID with a `phone_number` attribute is checked for mismatch |
| `lid`, `phone_number` | the other address form; stored through the JID mapping repository |
| `join_time` | positive long (seconds, inferred); stored per participant; basis for "joined too long ago" |
| `group_history_sent` | `"true"` / `"false"`, Boolean; feeds `group_participant_user.group_history_send_state` (mapping inferred, 3.2) |

Receiver and sender lists in the bundle metadata (section 6.2) are JID strings. The job normalises them to the group's addressing mode before use: `PendingSendGroupHistoryJob.A01` maps each receiver to its **LID** when the group is LID-addressed (`C30194DBb.A05`), else maps LID to PN (`C0YH.A0G` / `AbstractC197018Zw.A0Y`). When a participant is added the job accepts both forms (`C0YH.A0J` yields the counterpart) to match the requirement sets. Which form ends up on the wire depends on the group mode (inferred from the mapping code).

### 2.3 Community and parent-group relations

`C23201A1a.A01` classifies a group node: **0** normal, **1** community parent (`parent`), **2** linked sub-group (`linked_parent`), **3** default sub-group (`default_sub_group`), **6** general chat. `A03` reads the parent JID from `linked_parent jid`. `membership_approval_mode` default for sub-groups comes from `parent/default_membership_approval_mode="request_required"`.

Found: `A1W` checks only the **JID type** (types 1 and 2 pass `C0DZ.A0l`: `@g.us` group and the `@temp` group `C99Q`), not the community role. The receiver accepts only type 1 (`C0DZ.A0b`). Whether a parent / announcement group is excluded by server-side or per-group experiment gates (23245 / 30905 are per-group) is unknown. Comment messages (community announcement comments) and association children travel in separate lists (6.1); the receiver drops a comment or child whose parent is not in the bundle (`orphan_parent_not_in_bundle`, `invalid_comment`).

### 2.4 Admin setting `member_share_group_history_mode`

| Wire value | Enum (`EnumC216299Tq`) | Local int | Meaning |
|------------|------------------------|-----------|---------|
| absent / unknown | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` 0 | 0 | not set |
| `admin_share` | `ADMIN_SHARE` 1 | 1 | only admins send history |
| `all_member_share` | `ALL_MEMBER_SHARE` 2 | 2 | any member may send |
| `all_member_share_toggle_on` | `ALL_MEMBER_SHARE_TOGGLE_ON` 3 | 2 | same as 2; variant seen in notifications (distinction inferred) |

Mapping: `AbstractC227759t3.A01(String)` (string to int), `A00(enum)` (enum to int, 2 and 3 to 2).

| Item | Detail (found) |
|------|----------------|
| Set | `GroupPermissionsActivity` switch (`C201678ic.A04`): MEX operation `SetGroupProperty` (client `whatsapp-android-mex`, input class `C204518nF`) with `member_share_group_history_mode` = `ALL_MEMBER_SHARE` or `ADMIN_SHARE`. The same input also carries `allow_admin_reports`, `allow_non_admin_sub_group_creation`, `announcement`, `hidden_group`, `locked`, `member_add_mode`, `member_link_mode`, `membership_approval_mode_enabled`, `participant_label_enabled`, `subject` |
| Notification | group notification (`w:gp2`, inferred) child `member_share_group_history_mode` (`C22270sr`) calls `A0g(actor, group, mode int, ts)`: updates the stored mode and inserts a system message |
| System message | "turned on / off recent history sharing for new members" in six variants (actor `%s`, "Recent history sharing was ...", "You ..."), each with "Tap to change" or "Tap to learn more" |
| History sync | `GroupShareGroupHistoryModeHistorySync` re-creates the system message for companions; `GroupChangeHistoryEnabledHistorySync` does the same for `history_enabled` |
| DB | `wa_group_admin_settings`: `share_group_history_setting_mode`, `group_history_toggle_mode`, `history_enabled`, `earliest_group_history_message_timestamp_ms` |

Meaning of `group_history_toggle_mode` (int, separate from the share mode) is not resolved; the column is read for groups where it is non-zero and `group_state = 0`. UI copy: "Admins can choose if members are allowed to send message history", "Admins control if history is sent", "When adding someone to the group, members have the choice to send up to 100 recent messages".

---

## 3. Eligibility

### 3.1 Sender (`A1W.A03`, found)

| # | Condition | Else |
|---|-----------|------|
| 1 | kill switch **35987** on (sender prerequisites) | `PREREQUISITES_DISABLED` |
| 2 | group JID type 1 or 2 | `GROUP_TYPE_NOT_ELIGIBLE` |
| 3 | group contact row exists | `GROUP_NOT_FOUND` |
| 4 | I am in the group, and either I am admin / superadmin, or (`require_membership_approval` = false and `member_add_mode` = 1 and share mode = 2) | `SENDER_NOT_ELIGIBLE` (log lists the three values) |
| 5 | at least one shareable message exists (`A0G.A00` count > 0) | `NO_SHAREABLE_MESSAGES` (also corrects the stored earliest-timestamp, `A0A`) |
| 6 | per-entry-point gate `A1W.A02` (3.3) | `EXPERIMENT_DISABLED` |

So a plain member can send only in groups where anyone may add members, no approval is needed and the admin enabled `all_member_share`.

### 3.2 Receiver (per added user, found)

| Check | Result code |
|-------|-------------|
| receiver is not a bot (`AbstractC24760wu.A03`) | `RECEIVER_NOT_ELIGIBLE` |
| receiver contact is not "no longer active" (`externalUserState`, `A07`) | `RECEIVER_INACTIVE` |
| participant row exists for (group, user) | `NOT_IN_GROUP` |
| `now - join_time` below flag **30333** (unit not resolved) and `group_history_send_state` is null or 1 | `NOT_NEW_OR_ALREADY_SENT` |

`group_history_send_state` (column of `group_participant_user`, written by `C14850fN.A0R`): 1 = still eligible, 2 = already sent (found from the "already sent" branch and the cancel path that resets 2 to 1). Mapping of the wire attribute `group_history_sent` to the state is inferred.

### 3.3 Gates (`C230099x1`, `A1W.A02`)

Each gate is `global flag OR per-group exposure` (`C41861nA.A04(group, id)`):

| Helper | Global | Per-group id | Use |
|--------|--------|--------------|-----|
| `A01` | **26451** | 30905 | entry point `AFTER_JOIN` |
| `A02` | **15313** | 23245 | send history during add (`A1W.A0B`), also gates `onGroupParticipantsAdded` |
| `A03` | **29973** | 30906 | callers not traced |

Entry points (`C9SA`): `AFTER_JOIN`, `FROM_MENTION`, `FROM_CONTACT_MESSAGE`. `FROM_MENTION` and `FROM_CONTACT_MESSAGE` are additionally tied to kill switches **35554** / **35555** and to gate `A02`. The polarity of the combined check is not resolved (decompile flow is garbled around `A1W.A09`).

---

## 4. Join flow (sender side)

### 4.1 UI entry points (found)

| Entry | Class | What happens |
|-------|-------|--------------|
| Add-members picker | `VoipParticipantPickerFragment` + `GroupHistoryAddMembersSettingFooterView` | footer "Send message history to approved members" with a toggle and a "recent messages" link; tapping opens the amount dialog; toggle state is remembered (`is_group_history_toggled`) |
| Membership approval screen | `GroupMembershipApprovalRequestsFragment` (`C24002AWf`) | same amount dialog before approving |
| Post-join sheet | `GroupHistoryAfterJoinSendBottomSheetFragment` | "Send message history to %1$s?" (one or two names) |
| Mention / shared contact | entry points `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | names only; behaviour not traced |

Confirmation text on first use: "Group history messages are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them." (`group_history_confirmation_dialog_confirmed_times` counter).

### 4.2 Amount options (`C229129vL.A00(n)`, found)

`n` = count from `A0G.A00` (messages that fit the limits in 5.1).

| n | Options |
|---|---------|
| 0 | none ("No message history to view") |
| 1..25 | one option, `n`, flagged "all" ("Last %d (all)") |
| > 25 | `k = min(4, ceil(n/25))`, `step = max(25, n/k)`; options `step`, `2*step`, ... up to `k-1` steps, then `n` (flagged "all" under a size condition on the last step; exact comparison not resolved) |

The list is then reversed by `C0CG.A0Z` (inferred: largest first); the first entry is preselected. A pinned-message disclaimer ("All available pinned messages will be included") is always shown.

### 4.3 Add IQ and event wiring (found)

```xml
<iq xmlns="w:g2" type="set" to="GROUP@g.us" id="…">
  <add>                                       <!-- optional transparency_acknowledged="true" -->
    <participant jid="USER"><privacy>bytes</privacy></participant>   <!-- privacy child optional -->
  </add>
</iq>
```

Found by reading the builder (`C11410Yt`): no history-specific attribute is added to the add request; the history decision is purely local. Events that release the pending job (`C197318aR`, timeout 32 s for the IQ itself):

| Event | Handler | Effect |
|-------|---------|--------|
| History requested | `CCP(params, group, requestId, receivers, nonReceivers, approvedByMe)` | persist `PendingSendGroupHistoryJob`; remember the chosen count in `A08[requestId]`; set `group_history_usage_activated` |
| Add IQ answered | `BfO(C222169gu)` | store the per-request result map |
| Participants added (notification) | `BvD` (only when gate `A02`) | add to "added by me" / "added by others" sets |
| Membership approval answered | `C05(group, user, requestId, approved)` | store approved user (or empty) |

### 4.4 Pending job (`PendingSendGroupHistoryJob`, found)

Fields: `permanentGroupRawJid`, `requestId`, `messageCount`, `lastMessageSortId`, `groupHistoryReceiverRawJids`, `groupHistoryNonReceiverRawJids`, `approvedByMeRawJids`, `jobScheduledServerTimeInMillis`, `expirationTimeInMins`. Persistent job id `group-pending-send-group-history`, requirement `SendGroupHistoryJobRequirement` (all receiver JIDs must parse, else `invalid group history receiver jid`).

| Step | Detail |
|------|--------|
| Requirement met when | job expired; or the add / approval result for `requestId` arrived; or a receiver is in the "added by others" set and not approved by me; or a receiver is now a participant (`A0r`) |
| Expiry | `scheduled + flag 19034` minutes; expired job: cancel, reset participant state 2 to 1 |
| Run | split receivers into already-joined and remaining; remaining go into a **new** pending job (same request id, non-receivers filtered); joined receivers get the bundle (`C9mW.A00`) |
| Bot receivers | a TEE bot receiver (`AbstractC197238aI.A00`) is handled by a separate history-share stamp (`A04`, 5.5) |
| Duplicate guard | `C197318aR.A09` map (group, user) to send time; entries older than `19034` minutes (min 5) are pruned |

---

## 5. Selection, limits and packing

### 5.1 Row selection (`A0G`, `AbstractC494421h.A00`, found)

```sql
SELECT … FROM available_message_view [ / with association join when 24033 ]
WHERE timestamp >= (scheduledTimeMs - flag18406 s)
  AND chat_row_id = ? AND sort_id <= ?                 -- anchor = last message at scheduling time
  AND view_mode IS NOT 1 AND view_mode IS NOT 3
  AND message_type IN (shareable types)                -- from the type registry, BUv()
  AND (association_type IS NULL OR association_type IN (supported))   -- only when 24033
  AND (from_me = 0 OR status NOT IN (-1,0,1,2,7,20,21,22))
  AND (expire_timestamp IS NULL OR expire_timestamp >= now OR keep_in_chat = 1)
ORDER BY sort_id DESC LIMIT n
```

| Parameter | Source |
|-----------|--------|
| `n` | count query uses flag **18405** as LIMIT; the send query uses the user-chosen count |
| window | flag **18406** (seconds) before the scheduling time; UI copy promises "up to 100" messages |
| shareable types | per-FMessage-type registry (`C222979iT.A00`, `C1ZP.BUv()` true), with a per-message override (`C30039D5b`); not enumerated here |
| own messages | only those that left the device (`status` not in the pending / failed set `AbstractC494421h.A00`) |
| ephemeral | expired and not kept messages are skipped |

If a post-join sort id is known (`C14650f0.A05`), the count anchors on it ("post-join query"); otherwise on the newest message ("pre-join query").

### 5.2 Lists in the bundle (found, `C9mW.A00`)

| List | Content | Limit |
|------|---------|-------|
| `messages` | the selected rows (shareable only) | `n` |
| `uncountedAssociatedMessageLists` | children attached to a selected parent (album items, polls, ...), grouped by `(parent key, association type)`; only when **24033** | not counted in `messageCount` |
| `commentMessages` | comments on selected messages (`C14780fG.A02(list, flag 6050, …)`) | flag **6050** (inferred as the cap) |
| `outOfWindowPinnedMessages` | pinned messages older than the oldest selected one; non-media only; filtered by the shareable set | all available (disclaimer string); receiver cap flag **19811** (inferred) |

Association types (`C13O`, 21 values): `FUTURE` 0 (also the fallback), `MEDIA_ALBUM` 1, `BOT_PLUGIN` 2, `EVENT_COVER_IMAGE` 3, `HD_VIDEO_DUAL_UPLOAD` 5, `STATUS_EXTERNAL_RESHARE` 6, `MEDIA_POLL` 7, `POLL_ADD_OPTION` 20, `STREAMED_HD_VIDEO_DUAL_UPLOAD` 22 and further status / sticker / dual-upload kinds.

### 5.3 Packing (found)

1. `GroupHistory` proto (6.1) is serialized to a file with extension `proto` (`File … A0Z(C15530gU.A0F, "proto")`); no compression step was found.
2. A new FMessage of type 117 is created in the group chat with the file as media (`mimetype application/protobuf`) and handed to the normal media-message send pipeline (upload and encryption, section 7).
3. Local fields on the FMessage: message count, oldest timestamp in window (seconds), oldest timestamp overall (min with pinned messages), receivers, non-receivers, packed message list sizes, file size, build time (telemetry).
4. If **24741** is on and the message has no secret, a fresh message secret is generated for it, then per-original-message reporting tokens are computed (section 9).

### 5.4 Notice after send (found, `ANQ.C0M`)

When the bundle reaches status **1** (or **24** when flag **28787** is on) and the notice was not yet sent (`A00 != 1`), the device creates a type-118 notice in the same group with the bundle's counts, timestamps and receivers and sends it (`C33166Ecf.A06`). Every group member receives it; recipients named in `historyReceivers` additionally mark it (`AbstractC30028D4q.A1B`).

### 5.5 TEE bot history share (found, brief)

For a bot receiver, `C9mW.A01` stamps selected messages that carry a message secret with a proof (`AbstractC33322EfC.A02(sender, botJid, "TEE History Share", stanzaId, secret)`) and sends a notice whose `botHistoryShareSyncMetadata` lists `(stanzaId, messageSecretProof)`. See the Meta AI report for bot context: [WA_META_AI.md](./WA_META_AI.md). The bot path does not upload a bundle.

---

## 6. Wire format

### 6.1 Inner file: `GroupHistory` (`DSN`)

| Field | Number | Type | Content |
|-------|--------|------|---------|
| `messages` | **1** | repeated `WebMessageInfo` (`C30626DTu`) | counted messages |
| `uncountedAssociatedMessageLists` | **2** | repeated `UncountedAssociatedMessageList` (`C30578DRy`) | `messages` **1** (repeated WebMessageInfo), `parentMessage` **2** (`MessageKey`, `BD5`), `associationType` **3** (enum `C13O`) |
| `commentMessages` | **3** | repeated `WebMessageInfo` | comments |
| `outOfWindowPinnedMessages` | **4** | repeated `WebMessageInfo` | pins |

The receiver parses the same bytes a second time as `GroupHistoryWithMessageBytes` (`C30576DRw`: same four field numbers; entries `C30543DQp` with `key` **1** (`MessageKey`) and `message` **2** (bytes); association lists `DPH` read as `messages` **1** only). That variant keeps the original serialized bytes per message (used for reporting-token validation and secret handling, inferred).

### 6.2 Outer message: `Message.messageHistoryBundle` (`DT6`, field **70**)

| Field | Number | Type | Value / use |
|-------|--------|------|-------------|
| `mimetype` | **1** | string | must equal `application/protobuf` |
| `fileSha256` | **2** | bytes | 32 bytes, plaintext hash |
| `mediaKey` | **3** | bytes | media key |
| `fileEncSha256` | **4** | bytes | 32 bytes, ciphertext hash |
| `directPath` | **5** | string | upload path; empty is logged, not fatal at parse time |
| `mediaKeyTimestamp` | **6** | int64 | seconds |
| `contextInfo` | **7** | `ContextInfo` | standard |
| `messageHistoryMetadata` | **8** | `MessageHistoryMetadata` (`C30583DSd`) | below |

`MessageHistoryMetadata`:

| Field | Number | Type | Rule on receive |
|-------|--------|------|-----------------|
| `historyReceivers` | **1** | repeated string | at least one; the current user must be listed |
| `oldestMessageTimestampInWindow` | **2** | int64 | present and > 0 |
| `messageCount` | **3** | int64 | present and > 0 |
| `nonHistoryReceivers` | **4** | repeated string | optional |
| `oldestMessageTimestampInBundle` | **5** | int64 | optional (includes pins) |

### 6.3 Notice: `Message.messageHistoryNotice` (`DRY`, field **102**)

`contextInfo` **1**, `messageHistoryMetadata` **2** (same type, required with receivers, timestamp and count rules), `botHistoryShareSyncMetadata` **3** (`C25765B9z`: `botJid` **1**, `historyShareMessages` **3** repeated `BA2` = `stanzaId` **1**, `messageSecretProof` **2**). The lite layout has no field **2** in `C25765B9z`; a cutoff exists only as local state (`C213519Ap.A03`).

### 6.4 Stanza level (found)

| Item | Bundle (117) | Notice (118) |
|------|--------------|--------------|
| stanza `type` | `media` | not media-specific |
| `<enc>` media type | `group_history` (`C30106D7q`; in the allowed enc media-type set `C9E2` / `C33474Ehg`) | none |
| `<meta appdata="…">` | **not set** (`C213539Ar` does not implement `FZF`) | `group_history` (`C213519Ap.AVN`; `F6K` writes it) |
| receiver check | `A0O == "media"` and `A0J == "group_history"` else error 11 | `appdata == group_history` else error 76 |
| `<reporting>` | optional, section 9 | none |

Both checks are skipped when envelope flags `A0V` / `A0U` are set (meaning unresolved). A bundle that arrives with media type `group_history` but without a matching message, and a notice appdata on a foreign type, are rejected by `GroupHistoryBundleDeserializationValidator` / `GroupHistoryNoticeDeserializationValidator` (`F3b` / `F3c`).

### 6.5 `WebMessageInfo` markers (`C30626DTu`, found)

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `isGroupHistoryMessage` | **57** | bool | message was imported from a bundle |
| `reportingTokenInfo` | **62** | message | reporting tag (see the Reporting report) |
| `groupHistoryIndividualMessageInfo` | **74** | `C30549DQv` | `bundleMessageKey` **1** (`MessageKey`), `editedAfterReceivedAsHistory` **2** (bool) |
| `groupHistoryBundleInfo` | **75** | `C30548DQu` | `deprecatedMessageHistoryBundle` **1**, `processState` **2** (enum `EnumC32128E2a`) |

`processState`: `NOT_INJECTED` 0, `INJECTED` 1, `INJECTED_PARTIAL` 2, `INJECTION_FAILED` 3, `INJECTION_FAILED_NO_RETRY` 4, `DEDUPED` 5.

---

## 7. Encryption and media

| Layer | Found |
|-------|-------|
| Message transport | normal group fan-out: the 117 message is encrypted like any group message (sender-key `skmsg` per group plus the usual sender-key distribution to devices). Basics are not repeated here; stanza `<enc>` form is in [WA_CALL_SIGNALING.md](./WA_CALL_SIGNALING.md) section on `<enc>`. Per-device sender-key state lives in `group_participant_device` (`sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket`) |
| Media row | `C15530gU.A0F`: upload type `group-history`, file type `GROUP_HISTORY`, HKDF info `Group History`, id 117 |
| Key / cipher | random media key, HKDF-SHA256 with info `Group History`, AES-256-CBC, HMAC-SHA256 truncated to 10 bytes appended, `fileSha256` / `fileEncSha256` in the proto: the generic scheme in [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) section 6 (80-byte expansion on Android); applied to this type through the common send pipeline (inferred, only the type row was read) |
| Upload URL | `https://<host>/mms/group-history/<hash>?…`; the `mms/<upload type>` composition is found for the table (section 4 of the media report); the literal path for this type was not captured (inferred) |
| Download | standard media download using `mediaKey`, `directPath`, hashes; failure text `GroupHistoryBundleProcessor/download failed for … with reason …` |
| Key reuse | bundle media key is independent of the message keys of the contained messages |

The receiver always works from the proto's `mediaKey`; a bundle whose hashes are not 32 bytes is rejected (`bogus sha-256 hash received`, error 14).

---

## 8. Receiver: validation and import

### 8.1 Parse-time checks (`C34677F2y.CM7`, found)

| Check | Error |
|-------|-------|
| chat JID is a group (`A0l`) | 11 `chatJid is not a group` |
| envelope `media` + enc media type `group_history` | 11 |
| `mimetype == application/protobuf` | 11 |
| `fileSha256`, `mediaKey`, `fileEncSha256`, `mediaKeyTimestamp`, metadata present | 11 |
| `historyReceivers` non-empty, window timestamp > 0, count > 0 | 11 |
| current user in `historyReceivers` (not for own messages) | 11 `current user is not in history receivers list` |
| gate **15311** off | placeholder FMessage `C35281aa` with code **82** ("Update to the latest version of WhatsApp to see it") |
| hash lengths 32 | 14 |

Notice (`C34678F2z`): group chat, appdata, metadata with receivers / timestamp / count; gate **15722** off gives placeholder code **10008**.

### 8.2 Processing (`GroupHistoryBundleProcessor`, found unless marked)

1. Trigger: message added (`C0G`) and again on media state 3 (`C0M`). A candidate is a group chat (type 1), not from me, state 0 or 5, with me in the receiver list, and younger than flag **25910** (unit not resolved; "Message history expired" otherwise).
2. Dedupe (flag **30462**): if a bundle was already processed for the same join session the new one is marked deduped (`deduped_bundle_for_join_session`), UI: "%1$s also sent you message history, which you already got from someone else".
3. Download the media; failure shows "Couldn't download message history from %1$s".
4. Parse file twice (`DSN`, `DRw`); parse failure: `protobuf_parse_failed`.
5. Find the anchor: the latest group join message ("failed to find latest group join message, adding messages before the first message in chat" when none); an anchor that is too old: `anchor_message_too_old`.
6. Validate and insert each message (8.3); associate every inserted row with the bundle (`group_history_bundle_association`: `bundle_message_key_id`, `message_row_id`, `message_sort_id`); mark `isGroupHistoryMessage`.
7. Out-of-window pins: cap (flag **19811**, inferred), apply shared pin state (`applySharedPin`).
8. Apply pending bot history share stamps (`BotHistoryShareHelper`), then telemetry (`group_history_receiver_user_journey`).

Imported rows are placed before the join anchor, so they appear above the "you were added" line (inferred from the anchor logic).

### 8.3 Per-message validation (`C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg`, found)

| Skip reason | Cause |
|-------------|-------|
| `invalid_jid` | `key.remoteJid` differs from the bundle chat |
| `non_hex_id` | `key.id` is not hex only |
| `timestamp_too_old` | `messageTimestamp` not newer than the allowed lower bound (log fields `msgTs`, `allowedTs`, `diff`; bound derived from local state, formula not resolved) |
| `parse_failed`, `pin_not_parsed` | proto of the entry did not parse |
| `not_shareable` | message type not allowed for import |
| `no_local_copy` | shared pin whose message was skipped and is not local |
| `max_limit_reached` | cap reached |
| `timestamp_after_anchor` | message newer than the join anchor |
| `already_exists`, `duplicate`, `expired` | already present locally, duplicate in file, ephemeral expired and not kept |
| `orphan_parent_not_in_bundle`, `invalid_comment` | comment / association child without its parent in the file |
| `insert_exception`, `anchor_messages_failed`, `insert_messages_exception` | local DB errors |

Further: a message needs its `messageSecret` preserved (`messageSecretLost`, `noMessageSecret` logs); the local copy wins when a message exists with different content (`keeping local …`).

Tables touched (found): `group_history_bundle_association` (`bundle_message_key_id`, `message_row_id`, `message_sort_id`), `group_history_share_reporting_info` (`stanza_id`, `reporting_tag`, `send_timestamp`, `added_timestamp`, `reporting_token`, `reporting_token_version`, `is_send`, `validation_policy`), `group_participant_user.group_history_send_state`, `wa_group_admin_settings` (2.4).

---

## 9. Reporting tokens (brief)

Stanza section for a bundle when **24741** is on (`F6C`, `GhsReportingTokenMessageSendStanzaContributor`):

```xml
<reporting>
  <message id="ORIGINAL_STANZA_ID"><reporting_token v="N">16 bytes</reporting_token></message>
  …
</reporting>
```

Token derivation and storage are in [WA_REPORTING.md](./WA_REPORTING.md) (section 6.2); part of the key derivation runs in native code, so the exact bytes are not reproducible from Java alone. On receive, when **5718** and **24742** are on, a missing token for an imported message produces telemetry `GROUP_HISTORY_MESSAGE_MISSING_FROM_PUBLIC_STANZA` (and, with **13063**, an internal diagnostic row); the message is still inserted in that path (inferred from control flow). Whether the server requires tokens: unknown.

---

## 10. HistorySync of companion devices (related, not group history)

Basics of pairing and app-state are in [WA_LINKED_DEVICE_PAIRING.md](./WA_LINKED_DEVICE_PAIRING.md) and [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md). Only what bears on group data:

### 10.1 `HistorySyncConfig` (`C44601rs`, companion advertises; field numbers from the lite layout)

| Field | # | Companion value (found) |
|-------|---|-------------------------|
| `fullSyncDaysLimit`, `fullSyncSizeMbLimit` | 1, 2 | flags **15284**, **15283** |
| `storageQuotaMb`, `initialSyncMaxMessagesPerChat` | 3, 20 | not set in the traced branch |
| `recentSyncDaysLimit` | 5 | 0 |
| `supportMessageAssociation`, `supportHostedGroupMsg`, `supportAddOnHistorySyncMigration` | 14, 11, 13 | true |
| `supportGroupHistory` | 15 | flag **20658** |
| `onDemandReady` / `completeOnDemandReady` | 16 / 18 | `!` flag **18953** / false |
| `thumbnailSyncDaysLimit` | 19 | flag **21217** |
| `supportHatchHistory` / bot channel list | 22 / 23 | flag **26445** / branch on **26614** |
| call log, bot and CAG history, `supportNewsletter`, `supportInlineContacts`, ... | 4, 6-8, 12, 24-27 | true (others false) |

Remaining fields (`supportBizHostedMsg` 9, `supportRecentSyncChunkMessageCountTuning` 10, `supportGuestChat` 17, `supportManusHistory` 21, `supportUniversalReachChat` 26, `supportOmittedConversationIndex` 27) are not detailed here.

### 10.2 Sync types and messages

| Message | Field | Content |
|---------|-------|---------|
| `HistorySync` (`C25838BCy`) | `syncType` **1**, `conversations` **2**, `statusV3Messages` **3**, `chunkOrder` **5**, `progress` **6**, `pushnames` **7**, `globalSettings` **8**, `threadIdUserSecret` **9**, `threadDsTimeframeOffset` **10**, `recentStickers` **11**, `pastParticipants` **12**, `callLogRecords` **13**, `aiWaitListState` **14**, `phoneNumberToLidMappings` **15**, `companionMetaNonce` **16**, `shareableChatIdentifierEncryptionKey` **17**, `accounts` **18**, `nctSalt` **19**, `inlineContacts` **20/21**, `omittedConversations` **23/24** | group conversations travel in `conversations`; `pastParticipants` (**12**) lists former group members |
| `HistorySyncNotification` (`C25834BCt`) | `fileSha256` **1**, `fileLength` **2**, `mediaKey` **3**, `fileEncSha256` **4**, `directPath` **5**, `syncType` **6**, `chunkOrder` **7**, `originalMessageId` **8**, `progress` **9**, `oldestMsgInChunkTimestampSec` **10**, `initialHistBootstrapInlinePayload` **11**, `peerDataRequestSessionId` **12**, `fullHistorySyncOnDemandRequestMetadata` **13**, `encHandle` **14**, `messageAccessStatus` **15** | media-referenced chunk; the payload is `HistorySync` |

Sync types: `INITIAL_BOOTSTRAP` 0, `INITIAL_STATUS_V3` 1, `FULL` 2, `RECENT` 3, `PUSH_NAME` 4, `NON_BLOCKING_DATA` 5, `ON_DEMAND` 6, and in the 9-value enum (`EnumC26456Bdr`) also `NO_HISTORY` 7 and `MESSAGE_ACCESS_STATUS` 8 (`EnumC26449Bdk` is the 7-value variant).

### 10.3 On-demand peer data operations (`EnumC26460Bdv`, found)

| Operation | Id | Request field (`C25823BCh`) | Response field (`C25828BCm`) |
|-----------|----|-----------------------------|------------------------------|
| `HISTORY_SYNC_ON_DEMAND` | 3 | `historySyncOnDemandRequest` **4** (`BCR`: `chatJid` **1**, `oldestMsgId` **2**, `oldestMsgFromMe` **3**, `onDemandMsgCount` **4**, `oldestMsgTimestampMs` **5**, `accountLid` **6**, `supportInlineResponse` **7**) | none defined; history arrives as a `HistorySyncNotification` (inferred) |
| `FULL_HISTORY_SYNC_ON_DEMAND` | 6 | `fullHistorySyncOnDemandRequest` **6** (`BBB`: `requestMetadata` **1** `BBA`, `historySyncConfig` **2**, `fullHistorySyncOnDemandConfig` **3** `C156516k5`: `historyFromTimestamp` **1**, `historyDurationDays` **2**) | `fullHistorySyncOnDemandRequestResponse` **6** |
| `PLACEHOLDER_MESSAGE_RESEND` | 4 | **5** | **4** |
| `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` | 8 | **7** | **8** |

The primary keeps one row per sync in `msg_history_sync` (`device_id`, `sync_type`, `last_processed_msg_row_id`, `oldest_msg_row_id`, `sent_msgs_count`, `chunk_order`, `sent_bytes`, `last_chunk_timestamp`, `status`, `peer_msg_row_id`, `oldest_message_to_sync_row_id`, `session_id`, `size_limit_bytes`, `full_history_on_demand_request_id`, …). Server-side caps on chunk size and message counts are not visible in the client code read here (unknown). No on-demand operation exists specifically for a group's shared history.

### 10.4 Group history on companions

| Item | Found |
|------|-------|
| Capability | `supportGroupHistory` (flag **20658**) in `companion-props`; stored on the primary as `support_group_history` (pairing report, section 6.2); consumer not traced |
| Bundle delivery | the bundle is a normal group message, so every device of a receiver gets it; strings for linked devices ("Open WhatsApp on your phone and visit this group to see it") suggest a placeholder there (inferred) |
| Primary sync build | `BuildHistorySyncParams` (`C33151EcQ`) carries `supportGroupHistory`, `pullGroupHistoryUncountedChildren`, `maxCommentsToAdd`, `supportMessageAssociation`; consumers not traced |
| System messages | share-mode, history-enabled, member-add / link / approval-mode changes are rebuilt for companions by the `Group*HistorySync` classes |

---

## 11. Feature flags and limits

Flag ids are bold; values are server-delivered, compiled defaults were not resolved (UI copy says "up to 100" messages).

| Flag | Type | Controls | Tier |
|------|------|----------|------|
| **35987** | bool | sender prerequisites kill switch | found |
| **15313** / 23245 | bool / group | gate `A02`, send history during add | found |
| **26451** / 30905 | bool / group | gate `A01`, entry point `AFTER_JOIN` | found |
| **29973** / 30906 | bool / group | gate `A03` | found (use unknown) |
| **35554**, **35555** | bool | `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | polarity inferred |
| **18405** | int | LIMIT of the count query (offer size cap) | found |
| **18406** | int, s | look-back window before scheduling time | found |
| **19034** | int, min | pending job expiry, dedupe prune (min 5) | found |
| **30333** | long | maximum time since join for a receiver | found (unit unresolved) |
| **24033** | bool | association lists and association filter | found |
| **6050** | int | comment collection cap | inferred |
| **24741** | bool | build reporting tokens on send | found |
| **28787** | bool | notice trigger status 24 instead of 1 | found |
| **20658** | bool | companion advertises `supportGroupHistory` | found |
| **15311** | bool | receive: bundle accepted (off: placeholder 82) | found |
| **15722** | bool | receive: notice accepted (off: placeholder 10008) | found |
| **30462** | bool | receive: dedupe per join session | found |
| **25910** | long | receive: freshness window of a bundle | found (unit unresolved) |
| **19811** | int | receive: out-of-window pin cap | inferred |
| **24034** / **25037** | bool / int | receive: association-child processing and its int parameter | inferred |
| **26039** | bool | inserter gate (three sites) | found (use unknown) |
| **5718** + **24742** | bool | receive: reporting-token validation | found |
| **13063** | bool | internal diagnostic row on missing token | found |

---

## 12. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| No "send history" option | sender not eligible (3.1), group not LID / PN consistent, or no shareable messages | admin enables `all_member_share`, member add mode `all_member_add`, no approval; or send as admin |
| Receiver shows "Update to the latest version" | gate 15311 / 15722 off or unknown type | none on the client |
| Bundle rejected, error 11 | wrong MIME, envelope type, media type, missing field, me not in `historyReceivers` | build per section 6 |
| Bundle rejected, error 14 | hash not 32 bytes | fix hashes |
| Notice rejected, error 11 / 76 | appdata not `group_history` (parse, 11); notice appdata on another type (validator, 76) | set `appdata=group_history` on type 118 only |
| Messages missing after import | skip reasons in 8.3 (`timestamp_too_old`, `not_shareable`, `invalid_jid`) | keys must be hex ids of the same group |
| "Couldn't download message history" | media download failed (expired `directPath`, key mismatch) | retry; resend |
| Job never runs | add or approval event not seen, receivers never became participants, job expired (19034) | re-add and resend |

---

## 13. Key distinctions

| Do not confuse | With |
|----------------|------|
| Group history bundle (type 117, `application/protobuf`, `group-history`) | companion HistorySync notification (`HistorySyncNotification`, `md-msg-hist`) |
| Bundle (data, no appdata) | notice (counts and receivers, `appdata=group_history`) |
| `member_share_group_history_mode` (who may send) | `group_history_toggle_mode` / `history_enabled` (meaning unresolved) |
| `historyReceivers` (get the data) | `nonHistoryReceivers` (added, not receiving) |
| `oldestMessageTimestampInWindow` (**2**) | `oldestMessageTimestampInBundle` (**5**, includes out-of-window pins) |
| `messages` count (`messageCount`) | uncounted association children and comments |
| `supportGroupHistory` in `HistorySyncConfig` (device capability) | the admin setting |

---

## 14. Baileys (`baron-baileys-v2` 1.5.17)

Only facts read in `src/Utils/group-history.js`, `src/Socket/groups.js`, `src/Socket/messages-recv.js`, `src/Socket/aigroups.js`, `src/Utils/validate-connection.js`, `WAProto/index.js`. Nothing was tested against a server; no failure is claimed.

| Topic | Baileys | Android |
|-------|---------|---------|
| Proto | `GroupHistory`, `GroupHistoryWithMessageBytes`, `GroupHistoryBundleInfo`, `GroupHistoryIndividualMessageInfo`, `Message.messageHistoryBundle`, `messageHistoryNotice`, `HistorySyncConfig.supportGroupHistory` present in `WAProto` | 6 |
| Decoder | `decodeGroupHistory` tries `zlib.inflateSync`, falls back to raw bytes; optional `GroupHistoryWithMessageBytes` mode; `processGroupHistory` normalises the four lists | no compression found on Android; raw protobuf read |
| Receive of the bundle | no code handles `messageHistoryBundle` (media download, validation, insertion) | section 8 |
| Send of the bundle | none | section 5 |
| Companion capability | `supportGroupHistory: true` in the advertised `HistorySyncConfig` | flag 20658 |
| Group setting | `member_share_group_history_mode` read from group metadata; `groupSetProperty(jid, property, value)` over MEX; mex notification `NotificationGroupMemberShareGroupHistoryModePropertyUpdate` emits `groups.update { memberShareHistoryMode }` | 2.4 |
| `aiGroupCreate` | accepts `memberShareGroupHistoryMode` (default `all_member_share`) but does not place it in the create stanza in the code read | not applicable |
| Participant attrs | `group_history_sent`, `join_time` not parsed | 2.2 |
| Addressing | `addressing_mode` read from group node, default `lid` when sending | 2.2 |

Consequence limited to what is read: a Baileys client that advertises `supportGroupHistory` cannot import a received bundle, because no consumer exists in the source. A sender must follow sections 5 to 7 (post-add send, `media` type with enc media type `group_history`, media type `group-history` with HKDF info `Group History`, notice with appdata); whether the server accepts a bundle without `<reporting>` tokens is unknown.

---

## 15. Complete flow

```
[Admin]  switch "Send message history" ─► MEX SetGroupProperty member_share_group_history_mode=ALL_MEMBER_SHARE|ADMIN_SHARE
     │
     ▼
[WA Server]  w:gp2 notification member_share_group_history_mode ─► all members: store mode, system message

[Sender]  add members (picker / approval screen / post-join sheet)
     │   A1W.A09: gate 35987, group type, sender (admin or all_member_share + all_member_add + no approval),
     │            receiver (join age, send_state), shareable messages
     │   A0G.A00 count ─► amount options (<=25 one option, else up to 4)
     ▼
iq set w:g2 <add><participant jid/></add>          (no history attribute)
     │
     ▼
[WA Server]  result ─► BfO / C05 / BvD events ─► PendingSendGroupHistoryJob requirement met
     │
     ▼
[Sender]  A0M: split joined / remaining (remaining re-queued) ─► C9mW.A00
     │   rows: timestamp >= scheduled - 18406 s, sort_id <= anchor, LIMIT n
     │   + association lists (24033) + comments (6050) + out-of-window pins
     │   GroupHistory proto ─► file ─► FMessage 117, mimetype application/protobuf
     ▼
upload  /mms/group-history  (HKDF info "Group History", AES-CBC + HMAC-10)       [WA_MEDIA_UPLOAD]
     │
     ▼
group message  type=media, enc mediatype=group_history, Message.messageHistoryBundle(70)
     │          metadata: receivers, nonReceivers, oldest ts (window / bundle), count
     │          optional <reporting><message id><reporting_token v/></message></reporting> (24741)
     ▼
[Receivers' devices]  C34677F2y checks (group, media, MIME, hashes, me in historyReceivers, gate 15311)
     │   download + decrypt ─► parse DSN / DRw ─► dedupe (30462) ─► anchor = join message
     │   validate each WebMessageInfo (jid, hex id, timestamp, type) ─► insert before anchor
     │   group_history_bundle_association, isGroupHistoryMessage=57
     ▼
[Sender]  bundle status 1 (24 with 28787) ─► notice type 118, appdata group_history, same metadata
     │
     ▼
[All members]  system row "<name> sent message history that starts on <date>"
```

---

## 16. Unknowns

| Item | Status |
|------|--------|
| Server-side acceptance rules, retention, size caps, reporting-token requirement | server side, not observed |
| Default values of 18405, 18406, 19034, 25910, 30333 | server-delivered, defaults not resolved |
| Exact lower bound of `timestamp_too_old` and unit of 25910 / 30333 | not resolved |
| Polarity of `A1W.A02` per entry point; use of gate `A03` and flag 26039 | garbled decompile / not traced |
| Meaning of `group_history_toggle_mode` column and of `<group_history/>` child | names found, semantics inferred only |
| Shareable message type list (`BUv()` registry) | not enumerated |
| Companion rendering of a bundle; consumer of `support_group_history` on the primary | not traced |
| Native part of the reporting-token key derivation | native, not read |
| Traffic | nothing captured; all flows from code |
