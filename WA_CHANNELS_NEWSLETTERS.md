# WhatsApp Channels & Newsletters — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** `@newsletter` JID domain and internal "newsletter" naming, follow/unfollow, channel creation, admin roles and handoff, the six `newsletterAdmin*`/`newsletterFollower*`/`newsletterScheduledMessage` proto fields, channel metadata (name, description, picture, verification, state), reactions on posts, view/follower counts, admin invite/revoke/accept flow, GraphQL/MEX newsletter operations (doc_ids), local storage, feature flags, error cases

---

## 1. What it is (technically)

A "channel" is the consumer name for what the client internally calls a **newsletter**: a one-to-many broadcast JID with server-side (non-E2E) storage, a small set of roles (owner/admin/subscriber/guest), and most control-plane operations carried over `w:mex` GraphQL rather than classic XMPP IQs. Content delivery (post fetch, status fetch, scheduled messages, live-update subscription) still uses a dedicated XMPP IQ namespace, `xmlns="newsletter"`. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code, **inferred** = deduced from code, **unknown** = not resolved. Unlike most of this repository's obfuscated-name reports, the client-visible newsletter package (`com.whatsapp.newsletter.*`, 122 files) ships with **readable class and method names** in 2.26.41.6; only shared infra (JID, message proto, IQ builders) is obfuscated and is re-resolved here from stable strings.

Out of scope: classic broadcast lists and `status@broadcast` — see [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md). Contact/device lookup mechanics reused by newsletters (not newsletter-specific) — see [WA_USYNC.md](WA_USYNC.md).

| Entity | Value | Tier |
|--------|-------|------|
| JID server | `newsletter` (e.g. `120363000000000000@newsletter`) | found |
| `Jid.getType()` | **21** | found |
| Encryption | `EnumC14260eC.NON_E2EE` — channel content is **not end-to-end encrypted** | found |
| Local model class | `C2130898y` ("NewsletterInfo"), extends the generic chat row `C14220e7` | found |
| JID class | `C1Y7` (`NewsletterJid`) | found |
| Invite link | `https://whatsapp.com/channel/<invite_code>` | found |
| Local DB table | `newsletter` (columns include `membership`, `invite_code`, indexed) | found |

| Component | 2.26.41.6 name | Role |
|-----------|----------------|------|
| JID parser | `C0DL.A03` (server-string switch), `C1Y7` (JID), `C1Y8` (JID companion/cache) | validates numeric id, no leading zero, builds/caches `C1Y7` |
| JID predicates | `C0DZ.A0a(jid)` = `getType()==21`; `C0DZ.A0M` includes type 21 in the set that also contains groups (18), broadcast list (3), status (5) etc. | isNewsletter / multi-recipient-capable set |
| Local model | `C2130898y` | role, verification, mute, reaction setting, state, counts |
| Roles | `C9U5` (local enum), `C9U4` (wire string enum) | section 4 |
| Metadata job | `BaseMetadataNewsletterGraphqlJob`, `GetNewsletterAdminMetadataJob` | `NewsletterMetadata` / `NewsletterAdminMetadataQuery` |
| Update job | `UpdateNewsletterGraphqlJob` | `NewsletterMetadataUpdate` |
| Create/delete job | under `com.whatsapp.newsletter.editcreate`, `com.whatsapp.newsletter.delete` | `NewsletterCreate(Verified)` / `NewsletterDelete` |
| Message fetch | `GetNewsletterMessagesJob`, `GetNewsletterMessagesUpdatesJob`, `GetNewsletterMyAddOnMessagesJob`, `SendNewsletterMessageJob`, `SendViewReceiptJob` | `com.whatsapp.newsletter.messages.job` |
| Status (channel updates) fetch | `GetNewsletterStatusesJob`, `GetNewsletterStatusUpdatesJob`, `GetStatusMyAddOnsJob` | `com.whatsapp.newsletter.status.job` |
| IQ builder | `C9EN` (`xmlns="newsletter"` constructors), `C9E2` (view-role / child-node value sets) | section 6 |
| Admin invite send | `C9m6` (`UserActionsNewsletterMessaging`), `C213489Am` | section 5.4 |
| Reaction store | `C12H`, `C23768ANd` → table `newsletter_message_reaction` | section 7 |

---

## 2. JID and domain

### 2.1 Parsing (found, `C0DL.A03`)

```java
// X.0DL (C0DL)
public C1Y7 A03(String str, String str2) throws C09B {
    String strTrim = str.trim();
    if (strTrim.isEmpty() || "0".equals(strTrim) || strTrim.indexOf("0") == 0)
        throw new C09B("Identifier must be a valid number starting with non-zero");
    if (!"newsletter".equals(str2)) throw new C09B(...);
    // cache lookup/insert, returns C1Y7(str)
}
```

`C1Y7.getServer()` returns the literal string `"newsletter"`; `getType()` returns `21`. Same no-leading-zero numeric-id rule as other multi-party JID types (groups, broadcast lists — see [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §2.1). The generic JID router `C0DZ.A01` falls through to `C1Y7.A03.A02(str)` as its default case when the string is neither a known singleton, a `UserJid`, nor a `GroupJid` — i.e. `@newsletter` is the fallback domain in that parser (found).

### 2.2 Type-set membership (found, `C0DZ.java`)

```java
public static boolean A0a(Jid jid) { return jid != null && jid.getType() == 21; }   // isNewsletter
public static boolean A0M(Jid jid) {
    int type = jid.getType();
    return type==0||type==1||type==18||type==22||type==3||type==7||type==21||type==26||type==28;
}
```
`A0a` is the dedicated newsletter predicate. `A0M` groups type 21 together with groups (18/22), broadcast list (3), community (7) and others into a broader "multi-participant-capable" set (purpose of the exact grouping not fully traced; inferred to gate shared participant/session machinery).

---

## 3. Follow / unfollow

Following is **not** a stanza subscription; it is a `w:mex` mutation, and the local role (`C9U5`) flips between `GUEST` and `SUBSCRIBED`.

| Operation | doc_id | Variables (found) |
|-----------|--------|--------------------|
| `NewsletterJoin` | `24658527423838739` | `entry_point`, `record`, `recipient_account_id`, `sessions`, `jid`, `fetch_and_validate_vname`, `call_offer`, `request_bottom_sheet_fragment` |
| `NewsletterLeave` | `25758579043742316` | identical shape to `NewsletterJoin` |

Both are built by the same class, `X/RunnableC24381AnW.java` (found). The shared variable set (`entry_point`, `call_offer`, `request_bottom_sheet_fragment`) suggests join/leave reuse a generic "chat action" mutation wrapper also used for calls and bottom-sheet-triggered actions elsewhere in the app (inferred).

Local role transitions on the `C2130898y` ("NewsletterInfo") object:

| Helper | Condition | Meaning |
|--------|-----------|---------|
| `A0p()` | `!muted && role==ADMIN` | is admin |
| `A0q()` | `!muted && (role==ADMIN \|\| role==OWNER)` | is admin or owner |
| `A0r()` | `role==SUBSCRIBED` | is following |
| `A0s()` | `role==GUEST` | not following (used to force `fetch_viewer_metadata=true` on a metadata refresh — found in `BaseMetadataNewsletterGraphqlJob`) |
| `A0u()` | `!muted && role==OWNER` | is owner |

UI error string on follow failure: `str1c0d` "Couldn't follow channel", `str1c0e` "Couldn't follow channel. Check your device's internet connection and try again." (found, `res/values/strings.xml`).

---

## 4. Roles

Two parallel role enums exist: a local persisted enum and a wire string enum used in GraphQL variables/responses.

### 4.1 Local role (found, `C9U5`)

```java
GUEST=0 (A03), SUBSCRIBED=1 (A05), ADMIN=2 (A02), OWNER=3 (A04)
```
`C9U5.A00()` maps ordinal → a priority rank: GUEST→4, SUBSCRIBED→3, ADMIN→2, OWNER→1 (lower = more privileged; purpose — sort order for admin lists — inferred).

### 4.2 Wire role (found, `C9U4`, `serverValue` = enum name)

```
UNSET_OR_UNRECOGNIZED_ENUM_VALUE, ADMIN, GUEST, OWNER, SUBSCRIBER
```
Used as the `view_role` attribute value on the `smax:any` child of newsletter XMPP IQs (section 6) and as the GraphQL `viewer_metadata.role` value (section 8).

### 4.3 Capabilities and handoff

| Action | GraphQL op | doc_id |
|--------|-----------|--------|
| Invite a user as admin | `NewsletterAdminInvite` | `26278681041745438` |
| Revoke a pending admin invite | `NewsletterAdminInviteRevoke` | `24369392486051948` |
| Accept an admin invite | `NewsletterAcceptAdminInvite` | `24934958956134858` |
| Demote an admin | `NewsletterAdminDemote` | `25054538847517281` |
| Transfer ownership | `NewsletterChangeOwner` | `24737692515842078` |
| Admin profiles batch fetch | `NewsletterAdminProfilesQuery` | `28089989690595314` |
| Admin profile update (name/photo) | `NewsletterAdminProfileUpdate` | `25959584293627630` |
| Admin metadata (full, admin-only fields) | `NewsletterAdminMetadataQuery` | `26882701001369256` |
| Capabilities gate | `NewslettersAdminCapabilitiesQuery` | `27579307995002556` |

Admin-invite flow action enum (found, `EnumC215899Sc`, used by `AdminInviteErrorDialog`): `NOT_SUPPORTED=0`, `INVITE=1`, `ACCEPT_INVITE=2`, `REVOKE=3`, `DISMISS=4`.

UI error strings (found): `str0095` "Couldn't accept the admin invite. Please try again.", `str106c`/`str2bed` "Couldn't transfer ownership. Please try again(.)/ later.", `str2300`/`str2abd` "Channel admin invite", `str22fb` "Invite %s as admin?", `str2bd8` "Invite as channel admin".

---

## 5. Admin invite — client-to-client message, not just GraphQL

The admin-invite UX has **two** separate mechanisms that both run: a MEX mutation (`NewsletterAdminInvite`, server-side grant) and a normal end-to-end **1:1 message** carrying the invite payload to the invitee, built independently of MEX.

### 5.1 Proto (found, confirms and extends the `Messages/newsletterAdminInviteMessage` starting material)

`Message.newsletterAdminInviteMessage` — field **78** of `Message` (`C30628DTw`), type `NewsletterAdminInviteMessage` (obfuscated `C30596DSq` in 2.26.41.6; JADX constants on the class itself, not the field number on `Message`, since the admin-invite field constant wasn't in the grepped set — field 78 matches an earlier WAProto.proto reference and is independently corroborated by every other field below resolving exactly as documented):

| Field | Number | Type |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `inviteExpiration` | **5** | int64 |
| `contextInfo` | **6** | `ContextInfo` |

Confirmed field-number constants `CAPTION_FIELD_NUMBER=4`, `CONTEXT_INFO_FIELD_NUMBER=6`, `INVITE_EXPIRATION_FIELD_NUMBER=5`, `JPEG_THUMBNAIL_FIELD_NUMBER=3`, `NEWSLETTER_JID_FIELD_NUMBER=1`, `NEWSLETTER_NAME_FIELD_NUMBER=2` read directly off `C30596DSq` (found) — matches an earlier field map exactly for this version.

### 5.2 Send path (found, `C9m6` = `UserActionsNewsletterMessaging`)

```java
public final void A00(Context context, C1Y7 c1y7, String name, String caption, HashMap userJidToExpiration) {
    byte[] thumbnail = A01(context, c1y7);           // JPEG of the channel picture, quality 80
    for (entry in userJidToExpiration) {
        C213489Am item = new C213489Am(..., 94, ...); // message-type tag 94
        item.A01 = c1y7;          // newsletterJid
        item.A03 = name;          // newsletterName
        item.A00 = entry.value;   // inviteExpiration
        item.A02 = caption;
        item.A0O(thumbnail, false);
        // enqueued as a normal E2E message to the invitee's UserJid
    }
}
```
Log line: `"UserActionsNewsletterMessaging/userActionSendNewsletterAdminInviteMessages"`. One message is sent per invitee, each carrying its own expiration timestamp — i.e. the invite is a **per-recipient E2E message**, while the MEX `NewsletterAdminInvite` op (server-side) is the authoritative grant record (inferred relationship between the two paths; both present in code, order/dependency not traced).

### 5.3 Accept

The invitee's client calls `NewsletterAcceptAdminInvite` (MEX). Its request already carries the full metadata-fetch variable set (`fetch_followers_count`, `fetch_state`, `fetch_verification`, `fetch_viewer_metadata`, …) — accepting an invite and re-fetching the channel's metadata are one round trip (found, variables from `X/AbstractC23610Aaw.java`).

---

## 6. Other newsletter messages: follower invite, admin profile, scheduled

### 6.1 `newsletterFollowerInviteMessage` / `newsletterFollowerInviteMessageV2`

Confirmed in 2.26.41.6 exactly as the starting material states, and independently re-verified here: both `Message` fields exist (`NEWSLETTER_FOLLOWER_INVITE_MESSAGE_FIELD_NUMBER` = **108**, `NEWSLETTER_FOLLOWER_INVITE_MESSAGE_V2_FIELD_NUMBER` = **113**, both found as named constants on `C30628DTw`), and **both map to the identical submessage type**, `C30585DSf`:

| Field | Number | Type |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `contextInfo` | **5** | `ContextInfo` |

Why both field numbers exist for one type is still **unknown** — no behavioral split was found at the Java layer in this pass either (consistent with an earlier finding).

### 6.2 `newsletterAdminProfileMessage` / `newsletterAdminProfileStatusMessage` / `newsletterScheduledMessage`

All three confirmed present as named constants on `C30628DTw` (`NEWSLETTER_ADMIN_PROFILE_MESSAGE_FIELD_NUMBER` = **116**, `NEWSLETTER_ADMIN_PROFILE_STATUS_MESSAGE_FIELD_NUMBER` = **126**, `NEWSLETTER_SCHEDULED_MESSAGE_FIELD_NUMBER` = **132**), and all three resolve to the same generic one-field wrapper type, `BD2` (= `FutureProofMessage`):

```java
public final class BD2 { public C30628DTw message_; }   // field "message", number 1, type Message (recursive)
```

No field-specific render/validator class exists for any of the three (found, matches an earlier note for `newsletterAdminProfileMessage` and `newsletterScheduledMessage`). `newsletterScheduledMessage` does have a dedicated non-message surface: the local table `newsletter_scheduled_message` (`chat_row_id`, `scheduled_server_id`, unique-indexed) and the wire IQ child `<scheduled_messages/>` (section 6.3) — the scheduling *feature* is real and traced; only the `Message.newsletterScheduledMessage` proto field itself stays an unexpanded wrapper.

### 6.3 Related local tables

`newsletter_scheduled_message`, `newsletter_admin_profile` (`chat_row_id`, `admin_profile_id`, `timestamp`) back `NewsletterAdminProfilesQuery`/`NewsletterAdminProfileUpdate` and the scheduling UI respectively (found, `C0SG.java`, `C0S3.java`).

---

## 7. Channel posts: fetch, send, reactions, view counts

### 7.1 XMPP IQ namespace `newsletter` (found, `C9EN`)

Content retrieval and a few write actions use a dedicated IQ namespace, separate from MEX:

```xml
<iq xmlns="newsletter" type="get" to="<jid>@newsletter" id="…">
  <messages count="N">
    <smax:any type="jid" jid="<jid>@newsletter" view_role="admin|guest|owner|subscriber"/>
    <before count="N"/> <!-- or <after count="N"/> -->
  </messages>
</iq>
```

| Child element | Constructor | Purpose |
|---------------|-------------|---------|
| `<messages count/>` + `<before>`/`<after>` | `C9EN(C9EB, C9E2, id, count)` | paginate channel posts |
| `<message_updates count since/>` | `C9EN(C1Y7, C9E8, Long, id, count)` | delta sync of edited/deleted posts |
| `<statuses count/>` | `C9EN(C9E9, C9E2, id, count)` | channel status/update fetch |
| `<status_updates count since/>` | `C9EN(C1Y7, C9EA, Long, id, count)` | delta sync of status posts |
| `<scheduled_messages count/>` | `C9EN(C1Y7, C31085Dfd, id, count)` | pending scheduled posts |
| `<question_responses server_id count/>` (plain and `type="status"`) | `C9EN(...)` | poll/question answers on a post |
| `<my_question_responses server_id/>` | `C9EN(C1Y7, String, long)` | caller's own answers |
| `<my_addons type="status" limit jid/>` | `C9EN(C1Y7, String, int, long)` | caller's own reactions/add-ons |
| `<live_updates/>` (`type="set"`) | `C9EN(C1Y7, String)` | subscribe to live push for a channel |

The `view_role` attribute on `smax:any` carries the caller's own `C9U4` role string (admin/guest/owner/subscriber) with every content-fetch IQ — the server appears to gate response content (e.g. admin-only fields) per-request rather than purely by session state (inferred).

### 7.2 Send (found, `SendNewsletterMessageJob`) and view receipts

Posting to a channel reuses the standard send pipeline (not detailed further here; the job wraps the normal `<message>` stanza machinery). Viewing a post is explicit and separate from delivery/read receipts:

```java
// com.whatsapp.newsletter.messages.job.SendViewReceiptJob
<receipt to="<jid>@newsletter" id="…" type="view">
  <list><item server_id="…"/> …</list>
</receipt>
```
One `view` receipt batches multiple server message ids. This is the mechanism that feeds the per-post **view count** shown in the channel UI (found; the counter itself is server-aggregated — client only reports, never reads back a count via this IQ).

### 7.3 Reactions (found)

Reactions on channel posts are **aggregated, not attributed** in local storage:

```sql
CREATE UNIQUE INDEX newsletter_message_reaction_index
  ON newsletter_message_reaction (message_row_id, reaction);
-- columns include: reaction, reaction_count
```
i.e. one row per `(message, emoji)` pair with a running count, not one row per reacting user — matching the channel UI showing an aggregate count per emoji rather than a list of reactors to ordinary users. `newsletter_my_reaction_orphan_message` (`chat_row_id`, `server_message_id`, unique-indexed) holds the caller's **own** reaction when it arrives before the post it targets, to be reconciled once the post lands.

Who reacted is visible only to admins, via a dedicated MEX query:

| Operation | doc_id | Variables |
|-----------|--------|-----------|
| `NewsletterReactionSendersList` | `25219734117717032` | `server_id` |

Reaction policy is configurable per channel (section 8.2, `reaction_codes`): `ALL`, `BASIC`, `BLOCKLIST`, `NONE` (wire strings, see `C9U3`/`C9TA` below).

### 7.4 Follower / view counts in metadata

`thread_metadata.followers_count` is returned as part of `NewsletterMetadata` (section 8.1). A dedicated paginated op also exists:

| Operation | doc_id | Variables |
|-----------|--------|-----------|
| `NewsletterFollowers` | `25646542368289354` | `newsletter_id`, `count` |

Per-post view counts are not returned by a documented standalone op in this pass; they are inferred to live inside the per-message metadata returned by the `messages`/`message_updates` IQ (section 7.1), which was not expanded further here (unknown exact field name).

---

## 8. Channel metadata (GraphQL response shape)

### 8.1 `NewsletterMetadata` response (found, chain `C208048tR → C208038tQ → C208028tP`, GraphQL node `xwa2_newsletter`)

```
xwa2_newsletter {
  id
  refresh_after_interval_sec
  state { type }                                    // C9UA
  status_metadata { last_status_sent_time, last_status_server_id }
  thread_metadata {
    creation_time
    description { text, id }
    followers_count
    handle
    invite                                           // invite code / link token
    name { text, id }
    picture { direct_path, type, url, id }
    pinned_messages[]
    preview
    settings { reaction_codes { value } }            // C9U3
    verification                                     // EnumC216369Tx
    verification_source                              // EnumC216219Ti
    wamo_sub { plan_id }
  }
  viewer_metadata {
    role                                             // C9U4
    settings[]                                       // { type, value } = EnumC216349Tv / EnumC216359Tw
    wamo_sub_status                                  // EnumC216229Tj
  }
}
```

### 8.2 Enums (found)

| Enum | Values (server-value strings where applicable) |
|------|---|
| `state.type` (`C9UA`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `DELETED`, `GEOSUSPENDED`, `NON_EXISTING`, `SUSPENDED` |
| `verification` (`EnumC216369Tx`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `UNVERIFIED`, `VERIFIED` |
| `verification_source` (`EnumC216219Ti`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `LEGACY_MANUAL_REVIEW`, `META_VERIFIED_SUBSCRIPTION` |
| `viewer_metadata.role` (`C9U4`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ADMIN`, `GUEST`, `OWNER`, `SUBSCRIBER` |
| `wamo_sub_status` (`EnumC216229Tj`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `INACTIVE` |
| `settings[].type` (`EnumC216349Tv`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `MUTE_ADMIN_ACTIVITY`, `MUTE_FOLLOWER_ACTIVITY` |
| `settings[].value` (`EnumC216359Tw`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `OFF`, `ON` |
| `reaction_codes.value` (`C9U3`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `BASIC`, `BLOCKLIST`, `NONE` |

Local mirrors on `C2130898y` ("NewsletterInfo"): verification state `EnumC216079Su` (`NOT_VERIFIED=0`, `VERIFIED=1`), verification source `C9T1` (`UNKNOWN_VERIFICATION_SOURCE=0`, `META_VERIFIED_SUBSCRIPTION=1`, `LEGACY_MANUAL_REVIEW=2`), enforcement state `C9T2` (`NOT_ENFORCED`, `SUSPENDED`, `GEOSUSPENDED` — gated for read behind flag **3877** in `A0w`/`A0x`), local "active" state `C9T3` (`NOT_SET`, `INACTIVE`, `ACTIVE`), migration/creation progress `C9T9` (`NOT_STARTED`, `IN_PROGRESS`, `FAILED`, `COMPLETED`), directory visibility `EnumC216039Sq` (`PUBLIC`, `PRIVATE`) and local reaction setting `C9TA` (`DEFAULT=0`→wire `"BASIC"`, `ALL=1`→`"ALL"`, `NONE=2`→`"NONE"`, `BLOCKLIST=3`→`"BLOCKLIST"` — mapping read from `UpdateNewsletterGraphqlJob.A0M`).

### 8.3 Update (found, `UpdateNewsletterGraphqlJob` → `NewsletterMetadataUpdate`)

```js
// GraphQl input built for doc_id 27150690864552229
updates: {
  description?: string,   // "" clears
  name?: string,
  picture?: base64,        // "" clears
  admin_profiles_enabled?: { settings: { admin_profiles_enabled, reaction_codes: { value: "ALL"|"BASIC"|"NONE"|"BLOCKLIST" } } }
}
newsletter_id: <jid>
fetch_image: true, fetch_preview: true, fetch_name: true,
fetch_viewer_metadata / fetch_state / fetch_verification / fetch_followers_count: <bool, usually mirrors viewer role>
```

### 8.4 Verification UI strings (found)

`str136f` "New verified channel", `str2be2`/`str2be3` "Create verified channel"/icon, `str2c51` "Verified channels", `str2c78` "Your verified badge will be removed from this channel. Your Meta Verified subscription will remain active.", `str2ca9` "Sorry, you cannot change the name of a verified channel from the app. Please contact customer support for assistance." — i.e. verified channels have a server-enforced immutable name (client-side UX only; enforcement side unknown).

---

## 9. GraphQL / MEX newsletter operations (doc_ids)

All doc_ids below were independently re-verified for this build against `assets/whatsapp-android-mex_client_persist_ids.json` inside `WhatsApp_2.26.41.6.apk` (found — doc_ids are static asset entries, not obfuscated, and are stable across the version comparison attempted here). 46 `Newsletter*` operations exist in that asset in total; the ones not detailed elsewhere in this report:

| Operation | doc_id | Purpose (inferred from name/variables) |
|-----------|--------|------------------------------------------|
| `NewsletterCreate` | `27009199332109318` | create a channel |
| `NewsletterCreateVerified` | `27777918425146464` | create a pre-verified channel (privileged accounts) |
| `NewsletterDelete` | `31838460859131915` | delete a channel |
| `NewsletterUpdateVerification` | `27133493439664458` | request/update verification state |
| `NewsletterHide` / `NewsletterUnhide` | `25033614912931367` / `24551592861177484` | directory visibility toggle (local `EnumC216039Sq`) |
| `NewsletterFollowing` | `26856957210673444` | list of channels the account follows |
| `NewsletterDirectoryList` / `Search` / `CategoryPreview` | `27480627564903390` / `27887355094203575` / `27432651036395658` | public directory browsing |
| `NewsletterSimilar` / `NewsletterRecommended` | `36410329795280256` / `26638880912457992` | discovery |
| `NewsletterInsights` | `24672564052397921` | owner/admin analytics |
| `NewsletterPinMessages` / `NewsletterUnpinMessages` | `28521965914059511` / `37386851567568720` | pinned-post management (`message_ids`) |
| `NewsletterBlockUser` | `25106066249006236` | block a follower |
| `NewsletterLogExposures` | `24606408825709914` | directory impression telemetry |
| `NewsletterLinkPreviewCheck` | `24188786150796507` | validate link preview domains in posts |
| `NewsletterPollVoterList` | `24803802869271956` | poll voters on a post (`jid`, `vote_hash`) |
| `NewsletterQuestionResponseStateUpdate` | `24896618076668076` | Q&A moderation state |
| `NewsletterLabelAiContent` / `NewsletterLabelPaidPartnership` | `27470054215955630` / `26221505494211174` | per-post AI-generated / paid-partnership label |
| `NewsletterChangeWamoSub` / `Enable`/`DisableWamoSub` | `25201342542835866` / `25122474967344830` / `31916794074578680` | WhatsApp monetization subscription state |
| `NewsletterUserReports` / `NewsletterCreateReportAppeal` | `27149305681394065` / `27792557363683798` | abuse reporting / appeal |
| `NewsletterEnforcements` / `NewsletterEnforcementAlertStates` | `27089116857425014` / `27640745535604048` | enforcement/suspension state (own `com.whatsapp.newsletterenforcements` package) |
| `NewsletterUpdateUserSetting` | `24935528202764688` | per-user UI pref (e.g. contact-picker tooltip count) |
| `FetchNewsletterRankingFeatures` | `24742757908756088` | ranking signal fetch (directory/recommendation) |

All are `w:mex` IQs (`type="get"`), schema `whatsapp_mex`, transport confirmed by the shared `C16880is`/`TreeWithGraphQL` call pattern seen in §5–8 (found). Response shapes beyond §8's `NewsletterMetadata` were not expanded in this pass (unknown).

---

## 10. Storage

| Table | Key columns (found) |
|-------|----------------------|
| `newsletter` | `membership` (indexed), `invite_code` (indexed) |
| `newsletter_message` | unique on `(chat_row_id, server_message_id)`; `is_autodelete_eligible` (indexed) |
| `newsletter_message_reaction` | unique on `(message_row_id, reaction)`; `reaction`, `reaction_count` |
| `newsletter_my_reaction_orphan_message` | unique on `(chat_row_id, server_message_id)` — caller's own reaction arriving before its target post |
| `newsletter_admin_profile` | unique on `(chat_row_id, admin_profile_id)`; `timestamp` (indexed) |
| `newsletter_subscribers` | indexed on `(chat_row_id, type_of_fetch)` |
| `newsletter_scheduled_message` | unique on `(chat_row_id, scheduled_server_id)` |
| `newsletter_interaction` | indexed on `timestamp_ms` and `(newsletter_jid_row_id, timestamp_ms)` |
| `newsletter_linked_account` | indexed on `chat_row_id` |
| `newsletter_pinned_message` | indexed on `(chat_row_id, pin_timestamp_ms)` |
| `newsletter_media_clear` | unique on `(chat_row_id, media_type)` |

Shared chat infrastructure (`chat`/`chat_view`, `message` core columns) is reused as for any `Jid`-typed chat, same as groups/broadcast lists (see [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §3.5) — not re-detailed here.

---

## 11. Feature flags

IDs as read at call sites in `com.whatsapp.newsletter.*`; defaults not all resolved in this pass (marked where known).

| ID | Controls |
|----|----------|
| **3877** | gates read of the local enforcement-state helpers `A0w`/`A0x` (`SUSPENDED`/`GEOSUSPENDED` checks) on `C2130898y` |
| **1777** | country selector in directory filters |
| **5276** | channel-identity view during newsletter→something migration UI |
| **6445** | `ShareNewsletterInviteLinkActivity` |
| **6618** | `ViewNewsletterProfilePhoto` |
| **7237** | `NewsletterStatusView` |
| **9096** | `SendNewsletterMessageJob` |
| **12989** | `NewsletterDirectoryCategoriesActivity` |
| **15754** | perf-tracker "messages_fetch_end" marker in `GetNewsletterMessagesJob` |
| **17985** | `ForwardCounterAcsRepository` (forwarded-post counter) |
| **19889** | `ForwardCounterApi` |
| **23797** | `NewsletterDescriptionView` |

Exact default values and the gated behavior's full extent were not traced beyond "class is reachable only when the flag is on" (inferred from call-site shape); treat this table as a map of where to look, not confirmed on/off defaults (unknown for most rows).

---

## 12. Error cases

| Symptom | Cause | Fix / expected behavior |
|---------|-------|--------------------------|
| "Couldn't follow channel" (`str1c0d`/`str1c0e`) | `NewsletterJoin` failed or no connectivity | retry; check connection |
| "Couldn't accept the admin invite. Please try again." (`str0095`) | `NewsletterAcceptAdminInvite` failed | retry |
| "Couldn't transfer ownership…" (`str106c`/`str2bed`) | `NewsletterChangeOwner` failed | retry later |
| "Sorry, you cannot change the name of a verified channel from the app." (`str2ca9`) | channel is `VERIFIED`; name immutable client-side | contact support (server-side; unknown exact enforcement) |
| Own reaction has no matching post yet | reaction stanza/event raced the post's own delivery | held in `newsletter_my_reaction_orphan_message` until the post lands, then reconciled |
| `state.type` = `SUSPENDED`/`GEOSUSPENDED` | enforcement action against the channel | content fetch still returns `state`; posting/admin actions presumably blocked server-side (unknown exact gate) |
| `state.type` = `DELETED`/`NON_EXISTING` | channel deleted or never existed | client should drop the local `newsletter` row (apply path not traced) |
| Admin-invite action = `NOT_SUPPORTED` (`EnumC215899Sc`) | invite/accept/revoke attempted in an unsupported context (e.g. role, build) | generic error dialog, no retry button (`str5735`) |

---

## 13. Key distinctions

| Do not confuse | Difference |
|----------------|------------|
| Newsletter (`@newsletter`, type 21) vs broadcast list (`@broadcast`, type 3) | newsletter: server-stored, non-E2E, public follow model, roles; broadcast list: E2E sender-key fan-out to saved contacts only — see [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) |
| `xmlns="newsletter"` IQ vs `w:mex` `Newsletter*` GraphQL ops | IQ = content fetch/paginate/subscribe (messages, statuses, scheduled, live-updates); MEX = metadata, roles, directory, moderation, monetization |
| `newsletterAdminInviteMessage` (E2E 1:1 message, field 78) vs `NewsletterAdminInvite` (MEX mutation) | the message is the per-recipient notification with its own expiration; the MEX op is the server-side grant — both exist, relationship inferred |
| `newsletterFollowerInviteMessage` (field 108) vs `newsletterFollowerInviteMessageV2` (field 113) | identical payload type (`C30585DSf`); duplication reason unknown |
| Local role `C9U5` (GUEST/SUBSCRIBED/ADMIN/OWNER) vs wire role `C9U4` (…GUEST/ADMIN/OWNER/SUBSCRIBER) | same four roles, different ordinal order and different string casing/ordering — do not assume ordinal compatibility |
| `reaction_codes` wire value (`ALL`/`BASIC`/`BLOCKLIST`/`NONE`, from `C9U3`) vs local `C9TA` ordinal-to-string map | local ordinal 0 (`DEFAULT`) serializes to wire string `"BASIC"`, not `"DEFAULT"` |
| Per-post reaction storage (`newsletter_message_reaction`, aggregate count) vs normal message reactions | channels store one row per `(message, emoji)` with a count, not one row per reacting user |

---

## 14. Complete flow

```
[Admin]  create channel
    │   NewsletterCreate / NewsletterCreateVerified (MEX) ──► [WA Server] allocates <id>@newsletter
    ▼
[Admin]  set name/description/picture, reaction policy
    │   UpdateNewsletterGraphqlJob ──► NewsletterMetadataUpdate (MEX)
    ▼
[Admin]  invite co-admin
    │   C9m6: per-recipient E2E message (newsletterAdminInviteMessage, field 78, own expiration)
    │   + NewsletterAdminInvite (MEX, server-side grant)
    ▼
[Invitee]  NewsletterAcceptAdminInvite (MEX) ──► role GUEST/SUBSCRIBED → ADMIN (C9U5)

[User]  discover channel (directory / shared link https://whatsapp.com/channel/<code>)
    ▼
[Client]  NewsletterJoin (MEX) ──► role → SUBSCRIBED
    ▼
[Client]  <iq xmlns="newsletter" type="get"><messages count view_role=subscriber/></iq>
    │◄── posts, paginated by before/after server_id
    ▼
[User]  views post ──► <receipt type="view"><list><item server_id/></list></receipt> (view count)
[User]  reacts ──► newsletter_message_reaction (aggregate count, own reaction may be orphaned until post lands)

[Admin]  moderates: NewsletterReactionSendersList (who reacted), NewsletterBlockUser,
         NewsletterPinMessages/Unpin, NewsletterUpdateVerification, NewsletterChangeOwner
    ▼
[Owner]  delete channel ──► NewsletterDelete (MEX)
```

---

## 15. Unknowns

| Item | Reason |
|------|--------|
| Exact relationship/ordering between the E2E admin-invite message and the MEX `NewsletterAdminInvite` grant | both exist in code; which is authoritative, or whether one triggers the other, not traced |
| Why `newsletterFollowerInviteMessage` (108) and `…V2` (113) share one proto type | no behavioral split found at the Java layer |
| Per-post view-count field name/location in the message-fetch response | inferred to exist inside `messages`/`message_updates` IQ payload; not expanded |
| Server-side enforcement of immutable name on verified channels | client only shows a static error string |
| Full response shape of most MEX ops beyond `NewsletterMetadata` | not read in this pass |
| Default values for most feature flags in §11 | class-reachability only, not confirmed default state |
| Traffic / live server behavior | nothing captured; static analysis only |

---

## 16. Baileys

Not covered: `baron-baileys-v2` (the Baileys fork used as the comparison baseline in this repository's other reports) has no confirmed, verified-against-this-APK newsletter/channel implementation to compare at the time of writing. No Baileys-side code was inspected for this report; adding a Baileys section without checked facts would violate this repository's evidence rules. If/when `baron-baileys-v2` ships newsletter support, this section should be filled in against the JID (type 21, server `newsletter`), the `xmlns="newsletter"` IQs of §7.1, and the MEX doc_ids of §9.
