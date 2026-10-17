# WhatsApp Reporting — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-17
**Scope:** User/contact, group, channel, status, call and message reporting — SMAX `spam` stanzas, `spam_list`, report types, `spam_flow` entry points, reporting tokens, content upload, report/block UI, report-to-admin, block stanza and reason lists, server errors, client-side abuse signals, Baileys

---

## 1. What reporting is (technically)

A report is one IQ `set` to `s.whatsapp.net` in namespace `spam`. It carries a `spam_list` node (reported entity, reported messages, entry point, business-discovery context). The client re-serializes the reported messages as plaintext protobuf and uploads them together with a reporting token and the key that verifies it. Blocking is a separate stanza (`blocklist`). Report-to-admin is a third, unrelated stanza (`w:g2`).

All statements are static analysis of the decompiled APK. Tier: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved. Nothing here was captured on the wire.

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| IQ builder (multi-purpose, `$t` selects shape) | `C9EN` | builds every report IQ (types 0, 18-23) and many unrelated IQs |
| Reason/entry-point node | `C9E2` | `spam_list` with `spam_flow`, `wi_trace_id`, `is_known_chat`, ... (`xmlns="spam"`) |
| Group setting child | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| Content wrapper | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Misc nodes | `C31084Dfc`, `C31085Dfd` | flags (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Serializer ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, token assembly |
| SMAX manager | `SpamRPCManager` | `A01`-`A06`, one per report kind (package name not obfuscated) |
| Repo | `SpamReportRepo` | routes by JID class, local side effects |
| RPC wrappers | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | package `com.whatsapp.reportinfra.rpc` |
| Origin whitelist | `C9ZJ` | validates the entry point (78 values) |
| UI | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | report dialog, optional block/leave |
| Block executor | `C227489sZ` → `C34631Yx` | `blocklist` IQ |
| Report-to-admin | `RtaXmppClient` | `w:g2` reports queue |
| Token store | `C23070uA` | tables `reporting_info`, `reporting_info_content` |

Names differ per build; every obfuscated name above was resolved in 2.26.41.6 from stable strings (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`).

---

## 2. Report types

### 2.1 Routing (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` branches on the JID class:

| Reported JID | RPC class | `SpamRPCManager` | Builder `$t` | Response class | Log label |
|--------------|-----------|------------------|--------------|----------------|-----------|
| selected status object (`AbstractC31014DeU` non-null) on a newsletter JID | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| user (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| group | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| selected status object on any other JID, or status JID with a message list | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| newsletter/channel | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| event id (string) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| anything else | none | none | none | none | `SpamReportRepo: unrecognized jid` thrown, returned as failure |
| bot chat | none (see 3.3) | none | none | none | `C214999If` |

Other `C9EN` shapes that are not spam reports: `$t=0` report to admins and `$t=1` group setting toggle (section 9), `$t=2` sub-group suggestions, `$t=24/25/26` `status` nodes. The event RPC is called from coroutine lambdas (`AYs`, `Aaa`); the originating UI is unknown (event entry points `event_home_report` / `event_info_report` exist, so event reports are inferred).

### 2.2 Call reports are user reports (found)

`SpamReportRepo.triggerReportCallNonSuspend` (`call_spam_dialog_report` origin) calls `IndividualSpamReportRpc.A00` with no reported `jid`, no messages, and one call item. The call item (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` includes `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` and codec fatal errors. Flag **36386** picks the own-JID form in `to` (`CUC()` vs `Ask()`, inferred LID vs PN). A UI user report with `shouldIncludeCallLogsInReport` adds up to 5 call-log items (`C16430i1.A0B(jid, 5)`).

---

## 3. Client flow

### 3.1 Dialog

`ReportSpamDialogFragment` (bottom dialog). Fragment args (found): `flow` (the entry point string, becomes `spam_flow`), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` loads dialog state.

On confirm, `reportAsSpam$1` runs:

1. Bot chat: skip the RPC (3.3). Otherwise `SpamReportRepo.A02(...)` with the selected message in a one-element list (or none).
2. Success carries an optional report id; error shows toast `str3bf8` (or `C227489sZ.A00`, log `spamreportmanager/spam/report/no-network-cannot-report`). WAM `wam_spam_report_perf` is filled (11.3).
3. Optional extra action `triggerExtraAction$2` (3.2), completion dialog from `H2U` (10.2), local writes (3.3).

### 3.2 Report only vs report + extra action (found)

The checkbox maps to the string `report` (unchecked) or `report_block` (checked), used for analytics (`asd.BaC` vs `BaD`) and the post-report toast. The extra action differs by target:

| Target | Extra action when checked |
|--------|--------------------------|
| user | block via `C227489sZ.A01` → `C34631Yx` `blocklist` IQ (section 8), block reason `null`, entry point = `flow`, `deleteChat` = arg `shouldDeleteChatOnBlock` |
| group | leave-group task (`C98C` / `C9CI`, run with the group JID; leave semantics inferred) |
| channel | hide reported channel locally (`NewsletterReportCompletionListener`, flag **25218**), then newsletter exit/unfollow flow |

The report IQ is sent first; the block/leave runs after the RPC returns, regardless of its outcome (inferred from control flow, no success check before `triggerExtraAction$2`).

### 3.3 Bot chats and local effects (found)

Bot chats skip `SpamReportRepo`: the client calls `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) and treats it as success (`C214999If`); wire form unknown. For other chats `C24120Ab1` case 4 does:

| Step | Effect |
|------|--------|
| no message selected | collects the latest **5** messages of the chat (`C14680f4.A01(..., 5, true)`; system-type rows excluded, no `from_me` filter in this variant) as the reported content |
| user chat | local log `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; flag **20085** gates `H0J.A00(jid, ...)` (purpose unknown) |
| after RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, no check of the RPC result in the visible flow |

---

## 4. Stanza envelope and namespace

### 4.1 The reason node is merged into the IQ (found)

The RPCs do not emit two `spam_list` siblings. The main `spam_list` (jid, messages) and the reason node `C9E2` (an `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>` fragment) are combined with `C10340Uk.A04`, which merges attributes and same-name children (conflicting attribute values or child counts abort the merge). Result:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Evidence: `C9EN` ctors for 18-23 call `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`; `C9E2` case 5 builds `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. The IQ `id` comes from `MessageClientSmaxWrapper.A01()` (`n<hex counter>`, `C10140Tq.A0H`). Send timeout 32000 ms (`A0F(node, id, cont, type, 32000, ...)`); a null response (timeout/delivery failure) becomes `C216549Uq`.

Types 0 and 1 set `xmlns="w:g2"` and `to=<group>` literally; types 18-23 build `<iq type="set">` and rely on the merge for `to` and `xmlns`. The type id passed to the sender is **98** (group, newsletter, event) and **385** (report-to-admin).

### 4.2 Optional siblings merged into `spam_list`

| Node/attr | Source | Gate | Tier |
|-----------|--------|------|------|
| `spam_flow` | `flow` arg normalised by `C9ZJ` | always | found |
| `wi_trace_id` (exactly 24 chars) | `$wiTraceId` of `reportAsSpam$1` | optional | found; value origin unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | flag **22256**; user: address-book check, group: group membership check | found |
| `biz_opt_out` child | `C33446EhE.A07` | business discovery record exists | found (see 8.3) |

---

## 5. Per-type stanzas

`from`/`to` of a `<message>` item: for the user path the anonymous node `C9E4` sets `to=<jid>` when the message is outgoing (`key.fromMe`) and `from=<jid>` otherwise. Counts are builder gates (`AbstractC10350Ul.A07`).

### 5.1 User (type 20)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<userJid>" spam_flow="chat" wi_trace_id="...">   <!-- jid: UserJid or interop jid (C99O) -->
    <message from|to="<userJid>" t id deleted_reason>              <!-- 0..210 items -->
      <raw v="2" local_message_type="<int>" mediatype="<enum>"><proto bytes></raw>
      <content_validation type="e2e_proto_message|mms_retry|plaintext_v3">
        <reporting_token v="<n>"><tag, min 6 bytes></reporting_token>
        <reporting_token_key><key, 16-32 bytes></reporting_token_key>
      </content_validation>
    </message>
    <call .../>                                                    <!-- 0..5 items, section 2.2 -->
    <extension_screen extension_id session_id t name entry_point>  <!-- 0..5, business Flows context (A0B), data child -->
    <biz_opt_out business_discovery_timestamp business_discovery_id business_discovery_entry_point/>
  </spam_list>
</iq>
```

The builder takes three item lists with caps 210 (messages), 5 (call items), 5 (messageless business-flow items, `C33446EhE.A0B`: last 5 entries of the per-business store `messageless_flow_ids_per_business_<jid>`, node `extension_screen`). `jid` is validated against `UserJid` and `C99O` only; no `subject` on this path.

### 5.2 Group (type 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` is **the user who added the reporter to the group**, not the reporter. It is read from the local system message ("me joined") by SQL `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`). Optional. (found)
- `subject` is the group's display name from the contact record (`C06290Dn.A07().A00.A0b`; field meaning inferred), empty string `""` for community parent groups or when no record exists (`Voip.REJECT_REASON_DECLINED` is `""`). It is not a reason. Length gate 0..65536. (found)
- A fourth list in the ctor throws (`getNode`) if non-empty; the RPC passes an empty list.

### 5.3 Newsletter (type 21) and status post (type 22)

```xml
<spam_list jid="<newsletterJid>" subject="<channel name or ''>" spam_flow="newsletter_info_report">
  <message from="<newsletterJid>">...</message>        <!-- 0..65 -->
</spam_list>
<spam_list jid="<statusPosterJid>" spam_flow="status_post_report">
  <message from="<posterJid>">...</message>           <!-- 1..2 items, only the first selected status is passed -->
  <biz_opt_out .../>                                   <!-- optional -->
</spam_list>
```

Newsletter `subject` = channel name (`C2130898y.A0j`), `""` if unknown (found). Status reports use their own token tables `status_reporting_info` / `status_reporting_content`.

### 5.4 Channel status V2 (type 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

The status is identified by `server_id` + timestamp, no uploaded content. The `status` child content (`InterfaceC35700FdB`) is not resolved.

### 5.5 Event (type 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`, no `wi_trace_id` (one-argument `C9E2(String)` path). Message to admins (type 0): section 9.1.

---

## 6. Reported content and tokens

### 6.1 What is uploaded (found)

`C33446EhE.A0A(fmsg, entryPoint)` builds one message item per reported message:

| Part | Detail |
|------|--------|
| `<message>` attrs | `t` (message timestamp, 0..2^53), `id` (stanza id), `from`/`to` jid, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | re-serialized `Message` protobuf (`C30628DTw` with `MessageContextInfo` `C30624DTs`); `local_message_type` = internal message type int |
| `<content_validation>` | token + key (6.2) |
| meta flags | `<edit v="1">` (edited), `<multicast/>` (broadcast flag 64), `<url_number/>` (flag 4), `<url_text/>` (flag 2), template id, `hsm` tid, `iab reported_link`, `original_sender` / `group_history_sender`, `futureproof`/`request`/`send` payment variants (`pay`), `reported_push_name` |
| `<reporting>` child | flag **5718**: built from the message's `reporting_info` rows (`C23070uA.A03`), up to 1000 entries (`C31085Dfd` case 28); per-entry schema not fully read |
| alt carriers | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 values, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

OTP template messages: the `<code>` placeholder in button titles is replaced with the real code before serialization (`AbstractC32303E8u.A00`). View-once: when the message is view-once and already opened/expired and the origin is not `media_viewer` / `view_once_viewer`, `A06` is true and the serialization block is skipped. Whether the item then carries an empty or absent `raw` is inferred (declaration not initialised in the decompile).

Media files are not re-uploaded by this stanza; the serialized message carries the media references (inferred; no upload call found). The stanza holds the plaintext proto and the key together, so the server can read the content: nodes **found**, readability **inferred**.

### 6.2 Reporting token and key (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

Assembled in `C33446EhE.A03` from the stored row (`C34539Ez0`): token bytes (`A05`), version (`A02`), stanza id (`A03`), key (`A07`). If the key is missing it is re-derived: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → native `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (use case id **5**; non-user chats go through `JniBridge` variants). If both the key and a 6-byte token are absent/zero the client logs `ReportingToken/MissingFkAtReport` and uses an all-zero 32-byte key. A missing token returns `null` (`ReportingToken is null`, item has no `content_validation`).

### 6.3 Token lifecycle (found unless noted)

| Stage | Detail |
|-------|--------|
| Outgoing message | builder `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Token = first 16 bytes of `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = message proto with version-dependent field filtering (`A07`, strips selected sub-fields of field 35; reading inferred). Callers of the builder not traced |
| Group history share | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): for type 117 messages `<reporting>` with one child per entry (attr `id`, child `<reporting_token v>`) |
| Incoming message | stanza child `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>` parsed by `C34764F6h` / `C1S0`, flag **5718**; both tag and token optional, tag required |
| Storage | tables `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) and `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`); `message_conditional_reveal.reporting_token_info` (blob); `group_history_share_reporting_info`; `status_reporting_info` |
| History | `WebMessageInfo.reportingTokenInfo` field **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; flag **6578** |
| Cleanup | `reporting_info*` rows deleted when `receive_timestamp` is older than a cutoff (`FP7` case 6); cutoff value not resolved |
| Alt validation node | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

Who issues `reporting_tag` and how the server verifies the token: server side, unknown. The pairing (tag in stanza, token+key in report) is inferred.

---

## 7. `spam_flow` entry points

97 values (found, `C9E2` case 5, order = array order). The `flow` arg is passed through `C9ZJ.A00`, which accepts **78** of them and throws `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` otherwise. All six RPC wrappers call it, and `SpamReportRepo.A02` catches the exception and returns a failure (client-side error, no stanza sent). The 78 are a strict subset of the 97. The 19 values rejected: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. These are probably block-only or other-RPC origins (inferred). `channel_status_report` is in the enum but rejected by `C9ZJ`; which flow the channel-status caller passes is unknown.

| Surface | Values |
|---------|--------|
| Chat / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Spam banners | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| FMX safety cards | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| On-device scam alerts | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Group | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Calls | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Channels / status / events | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Business | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

The `*_suspicious` vs plain choice for FMX cards is made in `C230769yA.A05` from `A0D(userJid)` (contact known or not); that predicate is inferred to be an address-book check. The `server_flagged` variants are chosen by card type; where the server flag comes from is unknown.

`wi_trace_id`: 24-char optional attribute, passed through from the caller; its generator was not found (unknown). It is also a field of WAM `wam_spam_report_perf` (11.3).

---

## 8. Block, reasons and business context

### 8.1 Block IQ (found, `C34631Yx.A0M` area)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` and `entry_point` are only emitted for `action="block"`. `jid` is chosen between the PN and LID forms by a setting check (`zA02` branch; exact rule not fully read); on a block the extra identifier is one of `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. Timeout 20000 ms. Entry points starting with `odml_scam_alert_*` are rewritten to `1_1_spam_banner_block` (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). PSA chats use a different IQ (`xmlns="w:comms:chat"`, `<blocking action>`). Fetch: `type="get"`, optional `<item dhash>`.

### 8.2 Block reasons (found)

Hardcoded string → local int in `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, other = 0. `RunnableC40792Hpk` maps the same strings to a second code set. These ints feed local log calls; whether they reach a server is unknown.

Business block sheet (`C24126Ab7`): server reason map if non-empty, else `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; OTP-template chats: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Business discovery context (found)

`C33446EhE.A07` reads the business-discovery record for the reported JID (store `LA8`): timestamp, id, entry point. Entry point enum (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. It is attached to both reports (`biz_opt_out` under `spam_list`) and blocks. These are the only how-did-this-chat-start signals found in the client.

### 8.4 Report reason lists (found)

Only business ads have a selectable list. `ReportReasonListFragment` starts empty and is filled from `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (response `mobile_config` > `list` with `name`, `v`, `country`). Hardcoded fallback enum (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. When the fallback is used: inferred as server list unavailable. There is no reason picker for ordinary user/group/message reports; the only "reason" on the wire is `spam_flow`.

---

## 9. Report to group admins

### 9.1 Send and fetch (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

No content, token or `spam_flow` is sent; only the message id. Errors only log `Rta::<op>/onError: <code>` or `/onDeliveryFailure: Network Failure`.

### 9.2 Member-report toggle (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (enable) or `<not_allow_admin_reports/>` (disable), smax 384. The nodes are direct children of the IQ, not wrapped in a `group` node. The builder accepts up to four sibling setting nodes in one IQ.

---

## 10. Server response and completion dialogs

### 10.1 Response (found)

Success (`type=result`): child `report` with attribute `id` (max 20 chars) → `C213959Ch.A01` → returned to the UI as the report id. Errors (`<error code text>`), per response class:

| Code | Name | Individual | Group | Newsletter | Status | Status V2 | Event |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 Completion dialogs

`H2U` decides from the report id and gates, then `C5BD` builds the fragment (`arg_report_id`, `arg_is_ad_report`):

| Gate | Dialog |
|------|--------|
| flag **25818**, user chat, message present | `NciiCompletionDialogFragment` |
| flag **6145** | `DsaCompletionDialogFragment` (EU) |
| flag **14249** | `UkOsaCompletionDialogFragment` |
| flags **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

All except NCII need a non-null report id; no id means no dialog.

---

## 11. Abuse signals on the client

### 11.1 What the client sends beyond the content (found)

Entry points with `*_server_flagged_suspicious` mean the card was shown for a chat marked by a signal other than the local contact check; how the client learns that flag is unknown. Sent in reports: `is_known_chat`, `biz_opt_out` (how the business chat began), call items (duration, who ended, terminate reason), business Flows `extension_screen` context, `source` (who added me to the group), `reported_push_name`, forward/broadcast/URL flags on each message, edited flag, view-once state, entry point, optional `wi_trace_id`.

### 11.2 On-device scam detection (found, scoped)

`com.whatsapp.integrityai` runs a downloaded model set (`scam_detection`) on device via ExecuTorch (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; features `mostRecentSenderScore`, `isCountryMismatch`). Outcomes drive warning banners/sheets and the `odml_scam_alert_*` entry points above. A local JSON scan record (`outcome`, `inputs`, `model_info`, `verification`) is written to a `FileStash` when `integrity_warning_report_enabled` (`C57375Pog`). No upload of that record was found (unknown). It is independent of the `spam` report stanza.

### 11.3 Telemetry (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. Error code mapping in `reportAsSpam$1`: cancellation -4, timeout/no response -1, other exception -3, protocol error = IQ error code.

---

## 12. Baileys

Package `baron-baileys-v2` has no report API. Shapes below come from the found nodes and are untested.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

User/group/channel report shapes follow section 5 (one merged `spam_list`, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Why it fails (all inferred) | Cause | Fix |
|--------------|-------|-----|
| error 548 or silent no-op | no valid reporting token/key: Baileys drops the `<reporting>` child of incoming messages and never derives the key | parse `reporting_tag`/`reporting_token` on receive, store per message, derive key from `messageSecret` (use case 5) at report time |
| 400 | `jid` of wrong class (must be user/interop for type 20), item counts above caps, `spam_flow` wrong type | use `spam_flow` strings from section 7; stay under 210 / 5 items |
| rejected IQ | two `spam_list` siblings (reason sent as a second node) instead of one merged node | send one `spam_list` with all attributes |

Both `wi_trace_id` and `is_known_chat` are optional in the builder; whether the server accepts reports with fabricated tokens is unknown.

---

## 13. Error cases

| Symptom | Cause | Tier |
|---------|-------|------|
| toast `str3bf8`, nothing sent | `C9ZJ` rejected the `flow` value (`Invalid BlockSpamReportOrigin value`) | found |
| `unrecognized jid` failure | chat JID is none of user/group/status/newsletter | found |
| report "fails" with no toast | server error 548: `C9ZI.A00` returns the same non-error result object as the bot path | found |
| generic failure toast | 400/403/429/500/501, or timeout (32 s) → `C216549Uq` | found |
| report content missing | view-once opened/expired and origin not a viewer; message has no stored token | found / inferred |
| local state says reported, server rejected | `is_spam_reported` written after the RPC without a visible result check | found (flow), inferred (consequence) |

---

## 14. Key distinctions

| Do not confuse | With |
|----------------|------|
| `spam_list@source` | the reporter. It is the user who added the reporter to the group |
| `spam_list@subject` (group, channel) | a reason. It is the group/channel name |
| `spam_flow` | a report reason. It is the UI surface that triggered the report (97 values) |
| report (xmlns `spam`) | block (xmlns `blocklist`), report-to-admin (xmlns `w:g2`), marketing opt-out (xmlns `optoutlist`, `C31105Dfx`, not analysed further) |
| two `spam_list` nodes | one merged `spam_list` (attributes and children combined) |
| call spam | event spam. Call reports are type 20 with a `call` item; type 18 is `event_id` |
| `reporting_tag` (server-issued, stored on receive) | `reporting_token` (16-byte HMAC, sent with outgoing messages and uploaded in reports) and `reporting_token_key` (derived, uploaded) |
| report-to-admin | report to WhatsApp. Admin report sends only `message_id`; no content, no token |
| `wi_trace_id` (client-sent trace id) | the report id, which the server returns in `<report id>` |
| `report_block` | a wire value. It is a client analytics/toast string; blocking is its own IQ |
| `allow_admin_reports` toggle (`$t=1`) | report-to-admin message (`$t=0`) |

---

## 15. End-to-end flow

```
[User]                  [Client]                                        [WhatsApp server]
  │ Report / Block+Report    │                                               │
  ├────────────────────────▶│ ReportSpamDialogFragment(flow = spam_flow)     │
  │ confirm (+block/leave)   │ reportAsSpam$1                                │
  │                          │  bot chat ──▶ BotMessageHelper/reportUgc      │
  │                          │ SpamReportRepo.A02: route by JID class        │
  │                          │  C9ZJ(flow) ──✗ IllegalArgumentException      │
  │                          │  no message ──▶ last 5 messages from DB       │
  │                          │ serialize msgs (EhE) + token + key,           │
  │                          │ is_known_chat, biz_opt_out, call items        │
  │                          │ C9EN + C9E2 merged into ONE spam_list         │
  │                          │ ── iq set xmlns=spam to=s.whatsapp.net ─────▶│
  │                          │                                   verify token│
  │                          │◀── result <report id> | error 400/403/429/    │
  │                          │    500/501/548 (548 treated as success)       │
  │                          │ WAM wam_spam_report_perf                      │
  │                          │ contacts.is_spam_reported = 1                 │
  │                          │ extra action:                                 │
  │                          │  user ── iq set xmlns=blocklist (block) ────▶│
  │                          │  group ─ leave   channel ─ hide + exit        │
  │◀─ completion dialog (DSA / UK OSA / AU OSA / NCII; needs report id)      │
  │                                                                          │
  │ member: iq set xmlns=w:g2 to=group reports>report{message_id} ──────────▶│
  │ admin : iq get xmlns=w:g2 to=group <reports/> ◀── report > reporter      │
```

---

## 16. Unknown

| Item | Reason |
|------|--------|
| Server-side token verification, `reporting_tag` issuance, how `server_flagged` is decided | server logic, not in the APK |
| Origin of `wi_trace_id` | generator not located in the decompile |
| Event report UI trigger, bot-chat report wire form | only lambda callers (`AYs`, `Aaa`) / `reportUgc` not traced past `C33437Eh4` |
| Flow string the channel-status report caller passes | `channel_status_report` is rejected by `C9ZJ` |
| Cutoff of `reporting_info*` cleanup | caller of `FP7` case 6 not traced |
| Upload of the local scam-scan record | no consumer found |
| Per-entry schema of the per-message `reporting` child and purpose of the flag 20085 call | built from DB rows, consumer logic not read |
| Live acceptance of any stanza in section 12 | no traffic was captured |
