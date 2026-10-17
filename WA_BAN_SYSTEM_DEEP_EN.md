# WhatsApp Ban System — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-17
**Scope:** Ban flow, WFAC lifecycle, spam signal collection, GraphQL protocol, appeal system, suspicious marking, prevention

---

## 1. Architecture Overview

```
                         [Server]
                             │
       ┌─────────────────────┴──────────────────────────────┐
       ▼                                                     ▼
XMPP login <failure reason=…>                   MEX GraphQL (pull-based)
(HandlerThreadC12340b0.A13 → C45351tB,            │
 handled in C0ZH.handleMessage)                   ├── BizIntegrityQuery ──► BizIntegritySignalsManager
  │                                               │        └─► wa_biz_integrity_signals (SQLite, wa.db)
  ├─ 403 perm-ban ─► HGB.startPermanentBanFlow    │              ├── is_banned (INT)   (stored; no reader found)
  │      └─► BanAppealActivity (userban.ui)       │              ├── is_suspicious (INT)
  ├─ 416 / 402+code 106|107|109 (underage/U13)    │              ├── trust_tier (TEXT)
  │      └─► WfacManager.startUnderageBanFlow     │              ├── dhash (TEXT, server-supplied, opaque)
  ├─ 402 otherwise ─► SpamWarningActivity         │              ├── is_meta_verified (new in 2.26.41.6 vs report)
  ├─ 405 ─► pref software_forced_expiration (`t`)      │              ├── fmx_business_holdout_group (TEXT, new)
  └─ 406 ─► pref underage_account_banned            │              └── integrity_tags (JSON)
                                                  │
                                                  └── ban-status fetch (xwa2_fetch_wa_users, token)
                                                           └─► WfacBanRepository ──► SharedPreferences
                                                                 ├── wfac_ban_state = "BANNED" | "CHECKPOINTED" | "UNBANNED"
                                                                 ├── wfac_ban_violation_type
                                                                 ├── wfac_ban_violation_reason
                                                                 ├── wfac_ban_violation_source
                                                                 ├── wfac_last_ban_status_fetch_timestamp_ms (new)
                                                                 └── wfac_ban_status_token

  Main.A5W() (2.26.26.4: `Main.A5D()`; reads wfac_ban_state at start, registration state 21, log "main/me/wfac ban")
      └─► WfacBanActivity (hard ban UI; now `com.whatsapp.waffle.wfac.ui`, JADX pkg `p191ui`; intent built by `HBC`)

  SpamWarningActivity (pre-ban warning)       ◄── XMPP <failure reason=402> (C0ZH, type 2)
  SuspiciousFmxBottomSheetFragment (info sheet, opened from the FMX card buttons, see 7.2)
  SMB soft-enforcement banner                 ◄── XMPP business notification `biz_integrity_warning_notification` (see 7.4)
```

**Critical finding (corrected in 2.26.41.6):** ban-state synchronisation (WFAC) is **pull-based over MEX GraphQL**, but ban and warning *events* at connect time arrive over XMPP in the login `<failure>` node (reason 402/403/416/406, section 8.1). The SMB soft-enforcement warning is an XMPP business notification. No ban signalling via `<stream:error>` was found (that handler only deals with `code` 515/516, `conflict type="device_removed"` and `ack` kicks).

---

## 2. Ban State Lifecycle (WFAC)

### 2.1 Four-State Machine

| State | Value | Meaning |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | No local cache (also fallback for any unrecognised string) |
| `CHECKPOINTED` | 1 | Soft restriction, may require verification. Server string `NO_APPEAL_OPENED` is mapped to `CHECKPOINTED` by `AbstractC38371GmM.A00` (new) |
| `BANNED` | 3 | Hard ban, account restricted, appeal possible |
| `UNBANNED` | 2 | Fully functional |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (intent extra 0/1/2 kept, anything else -1; stored only for launch_source 2/3; default -1 via `HLK`; category names for 0/1/2 not found in 2.26.41.6, so the earlier SPAM/PHISHING/UNDERAGE mapping stays unverified)
wfac_last_ban_status_fetch_timestamp_ms → LONG (throttle, new)
```

Prefs wrapper: `HLK` (state getter parses via `C36188FnW.A00`: invalid string throws "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 State Transition Flow

```
Client connects
    │
    ▼
wfac_ban_status_token present? → NO → UNKNOWN_IN_CLIENT (no check)
    │ YES
    ▼
Registration state == 21? (fully registered)
    │ YES
    ▼
GraphQL: xwa2_fetch_wa_users (with token) (still present, `AWS`, `C46770Kc0`)
    │
    ▼
Throttle: skip if last fetch < 5000 ms ago (refreshInterval) or a fetch is in flight (generation counter); 60 s timeout runnable (new)
    │
    ▼
Response parsed by handler `C40191HfD` (obfuscated name 2.26.41.6; response class `C42252Ic7` / `C204538nH`)
    │
    ├── Stores via SharedPreferences: "wfac_ban_state" = state_string (stale generation responses discarded)
    ├── Error codes 1-4 logged separately; unknown → -1 (found, `C40191HfD`)
    └── Writers of `wfac_ban_state`: this handler (server string stored as is, `WfacBanRepository/storeBanState`), and `WfacBanActivity.onCreate` (launch_source 2/3 → "CHECKPOINTED"; launch_source 4 with `appeal_decision` "banned"/"unbanned" → "BANNED"/"UNBANNED"). No code path from `is_banned` (BizIntegrity) to `wfac_ban_state` was found.
```

### 2.4 Ban Reset Sequence

On successful appeal or account release (`WfacBanViewModel.A0x` / `C36188FnW`, resetRegistration):
1. Clears: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`, `wfac_last_ban_status_fetch_timestamp_ms`, `support_ban_appeal_user_banned_from_chat_disconnect` (new)
2. Logs user out (finishAffinity)
3. Redirects to login screen

---

## 3. BizIntegrityQuery — GraphQL Protocol

### 3.1 Technical Details

| Parameter | Value |
|-----------|-------|
| Query name | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (changed; was `25975613018777537`, rotated in 2.26.38.10, confirmed in 2.26.41.6 persist-id catalog; client_doc_id `14769534217004148908396994706`) |
| Schema | `whatsapp-android-mex` |
| Transport | MEX HTTP/2 POST → `/mex/query` |
| JID format | `<shortNum>@lid` (e.g. `1910@lid`) |

### 3.2 Request

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): input object `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`, result class `C48528LIw`. `privacy_token` only added when a gate (`MZ4.A00`) matches and a stored TC-token exists. Response (found, `C51015Mjl`): root `xwa2_fetch_wa_users[]`, per user `integrity_signals_info` with `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers` (sic, literal key), `is_banned`, `is_suspicious`, `is_suspicious_start_chat`, `join_date_ms` (string, parsed to long), `phone_country_code`, `trust_tier` (enum `M5B`), `is_mv_subscribed` (stored as `is_meta_verified`), `meta_verified_info{mv_friction_eligibility}`, `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. The field list below is the 2.26.26.4 reconstruction (inferred, not re-verified; the request-variable shape `$userJids` differs from the 2.26.41.6 input shape):

```graphql
query BizIntegrityQuery($userJids: [ID!]!) {
  bizIntegrityQuery(jids: $userJids) {
    jid
    is_banned
    trust_tier
    is_suspicious
    is_suspicious_start_chat
    integrity_tags { tag, pipelineDS, taggedDates }
    dhash
    phone_country_code
    join_date_ms
    fb_linked_page_number_of_likes
    ig_linked_page_number_of_followers
    mv_friction_eligibility
    hide_safety_tools_for_business
    chat_row_id
    last_sync_ts
  }
}
```

### 3.3 Response DTO — `BizIntegritySignals` (`C51530MtC`; was C39833Hhl in 2.26.26.4)

```
BizIntegritySignals(
  userJid, dhash, fbLinkedPageNumberOfLikes,
  igLinkedPageNumberOfFollowers, isBanned, isSuspicious,
  isSuspiciousStartChat, joinDateMs, phoneCountryCode,
  trustTier, isMetaVerified, mvFrictionEligibility, integrityTags,
  chatRowId, lastSyncTs, hideSafetyToolsForBusiness, fmxBusinessHoldoutGroup
)

Fields:
  integrityTags           → List of IntegrityTagInfo
  userJid                 → UserJid
  hideSafetyToolsForBiz   → Boolean
  isBanned                → Boolean  ← HARD BAN FLAG
  isSuspicious            → Boolean  ← SOFT ENFORCEMENT
  isSuspiciousStartChat   → Boolean
  isMetaVerified          → Boolean  (new)
  mvFrictionEligibility   → Boolean
  fmxBusinessHoldoutGroup → String   (new; stored as fmx_business_holdout_group, purpose unknown)
  chatRowId               → Long
  fbLinkedPageLikes       → Long (stored as REAL)
  igLinkedFollowers       → Long (stored as REAL)
  joinDateMs              → Long (stored as REAL)
  lastSyncTs              → Long
  dhash                   → String
  phoneCountryCode        → String
  trustTier               → String: "SUSPICIOUS" | "UNTIERED" | "TRUSTED"
```

### 3.4 IntegrityTags DTO

(`C51222Mno` list of `C51359MqA`; serialisation in `LwI`, unchanged shape)

```
IntegrityTagInfo {
  tag         → String
  pipelineDS  → Date (originally Long ms)
  taggedDates → List<Date>
}
```

**JSON format in DB:**
```json
[
  {
    "tag": "automation_bulk_messaging",
    "pipelineDS": 1700000000000,
    "taggedDates": [1699000000000, 1699500000000]
  }
]
```

### 3.5 Trigger Events

| Trigger | Usecase string |
|---------|---------------|
| Opening a chat | `"START_CHAT_CONTEXT"` (primary trigger) |
| After sending a message | post-send hook |
| App start / login | background scheduler |

### 3.6 Feature Flags

| Flag ID | Function |
|---------|---------|
| 11061 | Suspicious account detection trigger (`N5r.A03`; present; only evaluated for contacts whose verified-name level starts with `ent:`) |
| 11064 | Start-chat trust signal eligibility (on/off) (`BizIntegritySignalsManager.A04`; present; default false) |
| 11065 | Trust signal cache TTL in seconds (`C51855N0t.A00`; default 86400, found in `C08J`) |
| 12709 | Eligibility for contacts whose business `hostStorage == 2` (`C197628ax.A06`); default false (present) |
| 16349 | Forced-query path in `BizIntegritySignalsManager.A04` (present; default false) |
| 19793 | New in this table: `N5r.A02`, gates reuse of stored signals in `C51855N0t.A02`; purpose inferred from use; default false |
| 12840 | JSON config keyed by violation type, default `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`); consumer not located; purpose inferred from the key names (`max_dismiss_count`, `max_display_days`) and from the type strings used by the SMB soft-enforcement banner (7.4) |
| 19893 | FMX card system-message logging (present, `C198788cr`) |
| 26697 | BizIntegrity v2 (present, `C34735F5e`) |
| 27269 | Split incoming/outgoing message count (present) |
| 34166 | start_chat_trust_signals writer (present, `ContactInfoActivity`) |

In-memory cache in `BizIntegritySignalsManager.A02`: entries valid 60000 ms (found).

---

## 4. Suspicious Marking — When, Why, How, Prevention (re-checked in 2.26.41.6; items that could not be located are marked in place)

> **Core finding:** For the BizIntegrity flags (`is_suspicious`, `trust_tier`, `is_banned`) the client computes nothing: they are parsed from the GraphQL response (`C51015Mjl`) and only rendered. No client-side threshold or scoring for them was found. Separately, an on-device model produces local scam verdicts (`odml_scam_alert_*`, 6.6, 7.6). The BizIntegrity request carries only the queried JIDs, an optional privacy token and a telemetry context (3.2); that the client uploads its local metrics elsewhere is not found.

### 4.1 Who decides?

```
Local inputs on the device (found):             Server response (found, 3.3):
────────────────────────────────                ──────────────────────────────
• message counts (in/out/threads)               • trust_tier
  via N54 logger (6.2)                          • is_suspicious / is_suspicious_start_chat
• on-device features isCountryMismatch,         • is_banned (stored, no reader found)
  mostRecentSenderScore (6.6)                   • integrity_tags, dhash, join_date_ms,
• BizIntegrity request: jid(s) +                  phone_country_code, FB/IG counts,
  optional privacy_token (TC-token)               is_mv_subscribed, mv_friction_eligibility
```

No arrow from the local metrics into the BizIntegrity request exists in the client (3.2). Which server-side signals produce the verdict is not visible from the APK (server-side ML is inferred). The client has **no local threshold** like "more than X messages -> suspicious" for the BizIntegrity flags.

---

### 4.2 Trust Tier Hierarchy (server-assigned)

Found in the WhatsApp APK as a compiled enum (`M5B` in 2.26.41.6; values unchanged):

| Tier | Meaning | Effect |
|------|---------|--------|
| `SUSPICIOUS` | Highest risk — actively flagged | All warnings active, UI friction, possible send block |
| `TIER_0` | Lowest legitimate tier (new accounts) | Elevated friction eligibility |
| `TIER_1` | Standard user | Normal |
| `TIER_2` | Elevated trust | Less friction |
| `TIER_3` | Highest legitimate trust | Minimal friction |
| `UNTIERED` | No assessment | No check applied |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | Unknown | Fallback |

**Code-level check** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 Signals around the verdict

The client does not attach the data points below to the BizIntegrity request (3.2). The table lists where each one appears in the client; whether the server evaluates it is inferred. The "Risk weight" column of the earlier report had no client-side evidence and is dropped.

| Signal | Where it appears in the client (2.26.41.6) | Role |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | on-device feature (`integrityai.impl.InputFeatureProviderImpl`, flag 31535) | Input of the on-device model, not of the request |
| `mostRecentSenderScore` | on-device feature (flag 31536) | Same |
| `dhash` | response field, stored as is | Server-supplied opaque string; no client code composes it (meaning unknown; the report's earlier "device fingerprint" reading is inferred) |
| `join_date_ms`, `phone_country_code` | response fields | Stored; no client threshold |
| FB/IG counts | response fields (`fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers`) | Shown on the FMX card (7.5) |
| `integrity_tags` | response field `{tag, pipeline_date_ms, dates_ms[]}` | Stored as JSON; tag values are opaque to the client |
| Privacy token | request field `privacy_token{tctoken, timestamp}` | Optional, only when gate `MZ4.A00` matches and a TC-token is stored |
| Message volume | local counting (`N54`, 6.2) | Upload to the server not found |
| Broadcast limit | flag 20278 default `{"max_messages": 10000, "farthest_time_days": 30}` | Consumer not located (6.3) |

`isCountryMismatch` and `mostRecentSenderScore` are the two concrete ML features found in the client (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`, 2.26.41.6). Flag 31535 supplies isCountryMismatch, 31536 mostRecentSenderScore (found).

---

### 4.4 When is the GraphQL check triggered?

**Eligibility gate** (found, `BizIntegritySignalsManager.A04`; the queried JID is the chat counterpart):
1. Feature flag **11064** enabled (default false)
2. JID is not of the two excluded types (`AbstractC24760wu.A03/A04`: bot JIDs and a fixed phone-number JID)
3. One of: the contact is an SMB business (`N5r.A06`, verified-name level starts with `smb:`), or flag **12709** is on and the contact's business `hostStorage == 2` (`C197628ax.A06`), or (forced call, `A09`) flag **16349** on and `N5r.A04/A06` holds (`A04` = `!A01 && !SMB && !ENT`; the semantics of helper `N5r.A01` were not resolved, so which non-business JIDs this admits is open)
4. For the non-forced path: cache expired or no local cache (`C51855N0t`)

Correction vs the earlier report: in 2.26.41.6 the regular gate does not skip business accounts, it selects them (SMB or hosted); the forced path (16349) may admit other JIDs. The JADX flow of `A04` is partly restructured, so this reading comes from the decompiled shape plus the helper bodies, not from smali.

**Cache TTL:** Feature flag **11065** in seconds, default **86400 (24 hours)** (found, `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**Batch size:** no 975-JID chunking exists in the GraphQL fetch path (`BizIntegritySignalsManager.A03` passes the JID list on unchanged). The 975 constant belongs to the local SQL message-count batching (6.2).

---

### 4.5 Known integrity_tag values

The strings `automation_bulk_messaging` and `spam` are found in `C35896FgX` and `ViewOnClickListenerC39711HTl`, but there they are compared against the `type` of the SMB soft-enforcement notification (`HAR.A07`, see 7.4), not against `integrity_tags` from the BizIntegrity response. They also appear as the key of the flag 12840 default. The client does not enumerate `integrity_tags` values at all; the JSON blobs are stored opaque. `business_policy_violation` is not present as a string anywhere in java_src, smali, assets or res of 2.26.41.6.

| Tag | Meaning |
|-----|---------|
| `automation_bulk_messaging` | Soft-enforcement notification type (bulk/automated sending); not shown to be an `integrity_tags` value |
| `spam` | Soft-enforcement notification type (spam) |

---

### 4.6 What concretely leads to suspicious — inferred from code

Re-checked in 2.26.41.6: the client contains no logic, threshold or weight for any row below, and the BizIntegrity request carries none of these metrics (3.2). The whole table stays **inferred** (a guess at server-side behaviour from which signals exist in the client). The "New account (< 24h)" row has no support: no account-age check exists in the client (see 4.9 D).

| Behavior | Why it's risky | Weight |
|----------|---------------|--------|
| High outgoing vs. incoming (sending only, no replies) | Bulk outreach pattern | Very high |
| Phone country ≠ IP country | `isCountryMismatch = 1.0` | Very high |
| Same dhash on multiple accounts | Device ban trigger | Very high |
| Broadcast > 10,000 recipients / 30 days | Hard limit, immediate flag | High |
| High `mostRecentSenderScore` (recipients reporting) | ML feedback loop | High |
| New account (< 24h, no contacts) | Low credibility (no client-side age check found) | High |
| No FB/IG link + high outbound rate | Missing social proof | Medium |
| Existing integrity_tags | Prior violation effect | Medium–High |
| `is_reach_out = 1` + starting many unknown chats | Cold-contact pattern | Medium |

### 4.7 SpamWarning reason codes (pre-ban warning)

Unchanged in 2.26.41.6 (`SpamWarningActivity`: default reason 100, expiry default -1; switch on 101, 102, 103, 104, 106, default covers 105/other).

Delivered via intent extra `spam_warning_reason_key`, set from the XMPP login `<failure reason="402">` attribute `code` (>= 100) together with `expire`, `message`, `url` (found, `C0ZH.handleMessage` type 2; see 8.1):

| Code | Trigger | Countdown? |
|------|---------|-----------|
| 101 | Spam activity detected | Yes |
| 102 | Forwarding violation | Yes |
| 103 | Status spam | Yes |
| 104 | Bot forwarding | Yes |
| 105 | General / default | Permanent if expiry = -1 |
| 106 | Other violation | Yes |
| default | Unknown violation | Permanent if expiry = -1, else countdown |

`expiry_in_seconds == -1` + online: immediate finish (server lifted the warning).

### 4.8 SpamFlow categories relevant to suspicious marking

97 categories in the APK (found: `C9E2`, array of 96 entries plus `1_1_spam_banner_report` appended last, indices 0 to 96; the earlier count of 92 and the indices in the table are superseded). The list is serialised by name inside the SMAX node `spam_list` (attribute `spam_flow` per entry, optional `wi_trace_id` of 24 characters), so the index is only the position in the client array, not a wire value. New: `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_suspicious_banner_block/_trust`, `odml_scam_alert_fmx_card_block/_trust`, `biz_spam_banner_block`, `1_1_spam_banner_block`, `chat_fmx_card_block`, `group_spam_banner_report`, `left_group_spam_banner_report`. The ones directly tied to suspicious state:

| Index | Category | Meaning |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Server-flagged suspicious → FMX block |
| 24 | `chat_fmx_card_block_suspicious` | Chat blocked due to suspicious flag |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Safety tools shown for suspicious |
| 70 | `odml_scam_alert_bottom_sheet_block` | On-device ML scam → block |
| 71 | `odml_scam_alert_bottom_sheet_trust` | On-device ML scam → trust |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | 1:1 spam banner (server-flagged) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Trust prompt (server-flagged) |
| 89 | `user_initiated_chat_suspicious_banner_block` | Chat-start suspicious banner |
| 94 | `1_1_old_spam_banner_block` | Legacy spam banner |
| 96 | `1_1_spam_banner_report` | 1:1 spam report |

### 4.9 Protection mechanisms — what the client shows

The earlier "protective factors" list is a server-ML reading that has no client-side backing. What 2.26.41.6 actually contains:

#### A) Business status
Not a skip. The regular eligibility gate selects SMB contacts (and `hostStorage == 2` contacts under flag 12709), see 4.4. Flag 2923 (earlier: "non-business validation toggle") was not located: no flag check with that ID and no config default for it exists in java_src or smali of 2.26.41.6.

#### B) Meta Verified (mvFrictionEligibility)
Response field `meta_verified_info.mv_friction_eligibility` (found, `C51015Mjl`), stored as `mv_friction_eligibility`. `is_mv_subscribed` is stored separately as `is_meta_verified`. The FMX card (`C94p`) reads the flag and, with flag 15735 on, adds a "learn more" link. That lower friction thresholds result is not visible in the client (inferred).

#### C) Linked social accounts (FB/IG)
`fb_linked_page_number_of_likes` and `ig_linked_age_number_of_followers` are parsed as integers (`optInt`) and shown on the FMX card (7.5). They are counts, not booleans (found). That the server weighs them as protective is inferred.

#### D) Account age grace period
Not found. The only age-like comparison is the cache TTL on `last_sync_ts` against flag 11065 (4.4). `join_date_ms` is stored but no grace-window logic exists in the client.

#### E) Whitelist / validation list (flag 12709)
Changed: the check `C197628ax.A06(userJid)` is `hostStorage == 2` on the contact's verified-name record (`AnonymousClass119`), a local property, not a server-side pre-approval list. It makes the contact eligible for the query; it does not return early.

#### F) hideSafetyToolsForBusiness (field from response)
Response field `hide_safety_tools_for_business`, stored in `hide_safety_tools_for_business`. Effect on the UI is not re-traced; the earlier statement that it only hides the warning UI and does not change the suspicious status is unverified.

---

### 4.10 Prevention — what the code reveals

This part is advice derived from the fields above. The client has no logic that confirms any of it; treat every item as **inferred**, except where marked found.

**Behavioral (inferred):**
- Keep outgoing/incoming ratio balanced
- Avoid country mismatch between number and network (the client feeds `isCountryMismatch` to the on-device model, found; server use inferred)
- Stay under the broadcast config of flag 20278 (10,000 messages / 30 days; consumer not located)

**Account quality (inferred):**
- Linked FB/IG counts and Meta Verified are shown or stored by the client (found); their effect on the verdict is inferred
- A new-account window (24h) and dhash blacklisting are not supported by any client code (see 4.9 D and 4.3)

**Technical (found):**
- `privacy_token` (TC-token) is added to the BizIntegrity request only when gate `MZ4.A00` matches and a TC-token is stored

**Timing (found):**
- Cached signals are reused until `last_sync_ts` is older than flag 11065 (default 86400 s); manager keeps an additional 60000 ms memory entry
- Signals persist in `wa_biz_integrity_signals` until overwritten by a new response

---

## 5. Local SQLite Databases

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found, `C53116Nmn`, 17 columns incl. `_id`): adds `is_meta_verified` and `fmx_business_holdout_group`; `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `join_date_ms`, `last_sync_ts` are REAL, `mv_friction_eligibility` and `is_meta_verified` have no stated default. Unique indexes `biz_integrity_signals_jid_index`, `biz_integrity_signals_chat_row_id_index`; trigger `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). Store: `LwI` (labels `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`, `BizIntegritySignalsStore/saveBusinessIntegritySignals`). Schema below is the 2.26.26.4 version.

```sql
CREATE TABLE wa_biz_integrity_signals (
  jid                               TEXT PRIMARY KEY,
  join_date_ms                      LONG,
  trust_tier                        TEXT,     -- "SUSPICIOUS" | "TRUSTED" | ...
  is_suspicious                     INTEGER,  -- 0/1
  is_banned                         INTEGER,  -- 0/1
  dhash                             TEXT,     -- device fingerprint
  phone_country_code                TEXT,
  ig_linked_page_number_of_followers INTEGER,
  fb_linked_page_number_of_likes    INTEGER,
  is_meta_verified                  INTEGER,  -- new in 2.26.41.6
  mv_friction_eligibility           TEXT,
  integrity_tags                    TEXT,     -- JSON array
  chat_row_id                       LONG,
  last_sync_ts                      LONG,
  hide_safety_tools_for_business    INTEGER,  -- 0/1
  fmx_business_holdout_group        TEXT      -- new in 2.26.41.6
);
```

Writer/reader: `LwI` (store), `BizIntegritySignalsManager.A06(UserJid)` reads the in-memory `ConcurrentHashMap` (found: `A06` reads the in-memory map, `A07` reads it with lazy DB load, `A0A` upserts and persists; the 2.26.26.4 names `A08`/`A01` are gone)

### 5.2 `wa.db` — `start_chat_trust_signals`

```sql
CREATE TABLE start_chat_trust_signals (  -- schema `AI0`, columns unchanged (is_sender_suspicious, is_sender_new_account, created_ts); writer `C198788cr`
  jid                   TEXT PRIMARY KEY,  -- FK to wa_contacts
  is_sender_suspicious  INTEGER,           -- 0/1
  is_sender_new_account INTEGER,           -- 0/1
  created_ts            LONG
);

CREATE TRIGGER start_chat_trust_signals_contact_delete
  BEFORE DELETE ON wa_contacts
  BEGIN DELETE FROM start_chat_trust_signals WHERE jid = old.jid; END;
```

Reader: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`; was C2M7.A0K) → returns `(is_sender_new_account, is_sender_suspicious)` tuple

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

Query label: `"GET_INTEGRITY_CHAT_INFO"` (batch query with `chat_row_id IN (...)`), store `C33O`, schema `C08970Ox` (index `integrity_chat_info_chat_row_id_index`, trigger `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). Unchanged.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

Found in 2.26.41.6: schema `AHY` (cols `jid`, `last_delivered_sort_id` LONG, `last_read_sort_id` LONG), unique index `biz_integrity_chat_settings_index` on `jid`, trigger `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). Role unknown.

---

## 6. Spam Signal Collection (Client-side)

(Re-checked in 2.26.41.6; items that could not be located are marked in place.)

### 6.1 dhash

`dhash` is a string in the BizIntegrity response (`integrity_signals_info.dhash`), stored plaintext in `wa_biz_integrity_signals.dhash`. No client code composes it: no device model, OS, app version, number, timezone, Android ID or build-fingerprint input was found, and nothing uploads one. The earlier "device fingerprint / server-side blacklist" description is not supported; the meaning is unknown. Other `dhash` strings in the APK (block list, business opt-out) are unrelated directory hashes.

---

### 6.2 Message velocity

Found: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`, helper `N54`) counts messages locally over a time span for a list of JIDs, with SQL aliases:
- `incoming_count`: messages with `from_me = 0`
- `incoming_threads_count`: unique `chat_row_id` for received messages
- `outgoing_count`: messages with `from_me = 1`
- `outgoing_threads_count`: unique `chat_row_id` for sent messages
- Deleted message count: `messages_count_after_privacy_token` (also `messages_count`, `outgoing_messages_count`) from `integrity_deleted_chat_message_count`

Feature flag 27269 controls whether incoming/outgoing are counted separately or as a combined total (found in the same handler).
Batch size: **975 JIDs** per SQL processing call (found: `C20H.A1A(list, 975)`, a SQLite variable limit chunk, not a network batch).
Not located: daily/hourly binning, per-contact rate; where the counts go after counting is not traced.

---

### 6.3 Broadcast limits (business accounts)

Feature config 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found as default in `C08J`/`C09W`).
- Limit 10,000 messages per 30 days is the config default; the consumer of this JSON (the code that enforces it before a send, `renewal_date`, per-recipient throttling, marketing vs regular classification) was not located: the key strings `max_messages`/`farthest_time_days` occur only in the default tables and `renewal_date` does not occur in java_src.

---

### 6.4 GAP enforcement (Global Abuse Prevention)

Found: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) is skipped when feature flag 14837 is off, and stores `LAST_MARKETING_MESSAGE_TIMESTAMP` in SharedPreferences (`C67902uK`) when a newer marketing message arrives. Flag 25631 gates another trigger path. The expansion "Global Abuse Prevention" is not in the code (unverified naming).

Tracked state (`ChatDescription`, found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Found: package `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`, `WaFaReportScheduler`, `FaReportRunner`, `WaFaReportSubmitter`, `FaTeeConnection`, `FaTeeAcsRepository`, `FaAcsWarmer`). Reports go through a TEE connection authenticated with ACS (`x-acs-token`, `x-acs-configid`, `x-acs-project-name` headers; OHAI public key fetch). Next run time in pref `fa_next_report_run_timestamp`.
Not located: the content of the reports. The metric list of the earlier report (feature adoption, crashes, latency, RAM/storage/OS, geofencing, session data, connection type) was not found as code; report content is config-driven, so it cannot be read from the client.

---

### 6.6 ML feature extraction (on-device scam detection)

Two concrete features found in the decompiled client:
- `isCountryMismatch` (float 0.0/1.0): sender country ≠ recipient country → **HIGH RISK**
- `mostRecentSenderScore` (float): ML reputation score for sender

Feature flags 31535/31536 control their values (found). Results sent to server for secondary ML scoring (inferred).

---

## 7. UI Components: Suspicious, Warnings, Ban

(Re-checked in 2.26.41.6: `SpamWarningActivity` now `com.whatsapp.userban.spamwarning`, `SuspiciousFmxBottomSheetFragment` `com.whatsapp.fmx` plus new subclass `SuspiciousSmbFmxBottomSheetFragment`. Trigger conditions of 7.2, 7.4 and 7.5 are corrected below.)

### 7.1 SpamWarningActivity

Intent parameters:
- `spam_warning_reason_key` (int): reason code
- `expiry_in_seconds`: countdown (-1 = permanent)
- `spam_warning_message_key`: custom text
- `faq_url_key`: FAQ link

Reason codes:

| Code | Meaning |
|------|---------|
| 100 | General spam warning |
| 101 | Spam activity detected |
| 102 | Forwarding violation |
| 103 | Status spam |
| 104 | Bot forwarding |
| 105 | General / permanent |
| 106 | Other violations |

If `expiry_in_seconds != -1` → countdown timer shown.
If `-1` + online → immediate finish (server lifted the warning).

### 7.2 Suspicious FMX Bottom Sheet (`SuspiciousFmxBottomSheetFragment`)

Found: an information sheet ("learn more" links `about-blocking-reporting`, `examples-of-scams`), not a state-driven blocker. It is opened by tapping a suspicious-state button on the FMX card (`C93z.setupSuspiciousButtons`, SMB variant `C94p` opens `SuspiciousSmbFmxBottomSheetFragment`) and from `C512928n` (SMB variant when the contact is a business, `A0T()`), via helpers `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

The four trigger conditions of the earlier report (`is_suspicious == 1`, `is_suspicious_start_chat == 1`, `is_reach_out == 1`, `chat_fmx_card_block_suspicious == 1` as a send block) are not supported: the fragment itself reads none of them, and `chat_fmx_card_block_suspicious` is a SpamFlow category name (4.8), not a stored flag. What is found: the start-chat context is shown when `is_suspicious_start_chat` is true (`StartChatContextUtils`), and the FMX card computes `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 WFAC Hard Ban UI

| Class | Function |
|-------|---------|
| `WfacBanActivity` | Entry point, ban info + appeal button |
| `WfacBanInfoFragment` | Violation details + appeal link |
| `WfacBanDecisionFragment` | User action (appeal submitted) |
| `WfacUnbanDecisionFragment` | Post-appeal confirmation |

Trigger (changed): `Main.A5D()` is gone; its equivalent is `Main.A5W()`, which reads `wfac_ban_state` at start (switch on "UNBANNED" / "BANNED" / "CHECKPOINTED", registration state 21, log "main/me/wfac ban") and starts `WfacBanActivity` through `HBC`. No SharedPreferences change listener was found. `wfac_ban_state` is written by the ban-status fetch handler and by `WfacBanActivity.onCreate` (2.3). The login-failure path (403) opens the older `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`) instead. 2.26.41.6: classes now in `com.whatsapp.waffle.wfac.ui` (also `WfacBanBaseFragment`); activity opened via `HBC` intent helper and `I1T` screen transition (`transitionToScreen`).

### 7.4 SMB Soft Enforcement

Changed: the trigger is not `is_suspicious=true` + `integrity_tags` containing `"business_policy_violation"` (that string does not exist in 2.26.41.6). It is an XMPP business notification (handler `AnonymousClass142`, notification id 202) with child `biz_integrity_warning_notification > violation`:

| Attribute | Use |
|-----------|-----|
| `source` | origin of the violation (required) |
| `type` | violation type, e.g. `automation_bulk_messaging`, `spam` (compared in `C35896FgX`) |
| `severity` | e.g. `"severe"` changes the banner text (`C35896FgX`, `WABIEnforcementEducationFragment`) |
| `policy_url` | link target (required) |
| `priority` | int >= 0 (required) |
| `status` | `active` (stored, counters reset) or `inactive` (removed) |

The client builds an `SMBSoftEnforcementNotification` (`HAR`) with `notificationType` fixed to `"warning"` and `bannerNotificationTimeStamp` = receive time, and persists a JSON array under the preference `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) with the keys below. Per-notification counters are int preferences `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

```json
[{
  "source": "...",
  "type": "automation_bulk_messaging",
  "severity": "severe",
  "notificationType": "warning",
  "policyUrl": "https://...",
  "status": "active",
  "bannerNotificationTimeStamp": 1700000000000,
  "priority": 1
}]
```

The JSON of the earlier report (`notification_type: soft_enforcement`, `violation_type`, `education_url`, `action_required`) is not present in the client. UI: `SMBSoftEnforcementEducationFragment`, `WABIEnforcementEducationFragment` in `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 FMX Card (Trust Signal Card)

Found: a system message of type 129 (`0x81`, `C57172Xr`) is created in `C198788cr` ("Creating FMX card system message for chat", "ContactsProcessor/added contact info message"); flag 19893 only gates an analytics event there. The async write to `start_chat_trust_signals` is gated by `C1P2.A01()` (flag not resolved) and runs through `C65972r0`. The card (`C94p`) renders the FB likes and IG follower counts and the Meta Verified friction flag; `"SUSPICIOUS".equals(trust_tier)` selects the suspicious variant. Account age display and the "business/unknown contact" display condition were not located.

---

### 7.6 ODML Scam Alert (on-device ML)

Downloadable ML model via ACS token `"WA_ODML"` (found in `OdmlModelDownloadClient`, `ODML_MODEL_DOWNLOAD`, id `27301080136160169`, TTL 345600 s = 4 days; cache size 64 not located). User-toggleable via `ScamDetectionSettingsActivity`. Funnel tracked via session ID / source / entry point intent extras.

---

## 8. XMPP & Stanzas (ban context)

(Re-checked in 2.26.41.6 by reading the login and stream-error handlers; section 8.1 is corrected. An earlier 2.26.35.2 check saw no XMPP ban push; that observation is superseded by the login-failure path below.)

### 8.1 Login `<failure>` carries bans and warnings

The earlier claim "bans come only via MEX GraphQL" is wrong for events at connect time. `HandlerThreadC12340b0.A13` reads the login result node; for `<failure>` it takes `reason` (int) and builds a `C45351tB` exception (found):

| `reason` | Type | Attributes read | Client reaction (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | Server error, retry path |
| 402 | 2 (default) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `SpamWarningActivity` with `spam_warning_reason_key` = `code` (>= 100), `expiry_in_seconds`, text, FAQ url |
| 402 + `appeal_token` + `code` 106 | 13 | same | `ContextualAgeCollectionActivity` (extras `appealToken`, `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | same | "U13 Banned PAA Pending" path (managed-account prefs, onboarding) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | Permanent ban: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (after flag 19714 delay in ms) |
| 405 | 3 | `t` (seconds) | Writes pref `software_forced_expiration` |
| 406 | 5 | `code` | Pref `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`; `violation_reason == "u13_checkpoint"` sets `support_ban_appeal_user_banned_from_chat_disconnect` |
| other | 0 | - | Logout ("exception-password" path) |

All failure types also read optional logout UI attributes: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text`, `logout_main_button_url`, `logout_secondary_button_text`, `logout_secondary_button_url`. `location` is read from the node for routing.

`<stream:error>` (companion read interceptor, `C40601l6`): `code` 515 / 516, child `conflict type="device_removed"` (deregister), child `ack` (kick). No ban-specific child was found. `<presence type="unavailable">` and WebSocket close codes were not examined.

### 8.2 XMPP error tokens (binary dictionary)

Dictionary `AbstractC40911lb` (single-byte `A00`, double-byte `A01`). Presence of the earlier table's tokens:

| Token string | In dictionary |
|-------------|---------------|
| `stream:error` | yes |
| `conflict` | yes |
| `not-authorized` | yes |
| `item-not-found` | yes |
| `server-error` | yes |
| `401` | yes |
| `policy-violation` | not found |
| `403` | not found as a token (the `reason` value 403 is read as an int attribute) |

The "Meaning" column of the earlier report (e.g. `403` = "Forbidden (ban-related)") was inferred; only the 403 meaning is now backed by the `<failure>` handling above. Also in the dictionary: `404`, `407`, `failure`, `locked`.

### 8.3 IQ responses for restricted accounts

Not found. Neither the `urn:ietf:params:xml:ns:xmpp-stanzas` namespace nor the texts "Account restricted" / "User banned" exist in java_src or resources of 2.26.41.6, and no `forbidden` / `service-unavailable` tokens are in the dictionary. The XML examples of the earlier report are unverified and should not be relied on (they may be illustrative). Per-IQ error handling (e.g. `item-not-found`, `not-authorized` parsers such as `K3P`, `C23205A1e`) was not traced for restricted accounts.

---

## 9. Complete Data Flow (End-to-End)

(Re-checked in 2.26.41.6: doc_id `28596420510007620`, input shape `query_input`, class names above. The `isBanned` -> `wfac_ban_state` -> `Main.A5D()` arrows of the 2.26.26.4 diagram are removed because no such link exists in the code; see sections 1 and 2.3.)

```
[Open chat / send message]
           │
           ▼
  Check integrity_chat_info (is_reach_out?)
           │
           ▼
  Lookup start_chat_trust_signals (is_sender_suspicious? is_sender_new_account?)
           │
           ▼
  BizIntegritySignalsManager eligibility check — feature flag 11064
           │
    Flag active?
     YES │
         ▼
  BizIntegritySignalsGraphQLFetcher
    → HTTP/2 POST /mex/query
    → Variables: input{query_input:[{jid, privacy_token?}], telemetry{context:"INTERACTIVE"}}
    → doc_id: 28596420510007620
           │
           ▼
  Response → BizIntegritySignals DTO
           │
  wa_biz_integrity_signals (SQLite write, incl. is_banned, is_suspicious)
           │
    is_suspicious_start_chat? ──► start-chat context
    trust_tier == "SUSPICIOUS" ──► suspicious FMX card variant
           │                         └─► tap -> SuspiciousFmxBottomSheet (info only)
           ▼
  (is_banned: stored, no reader found)

  Separate path: XMPP login <failure reason=402|403|416> -> SpamWarningActivity /
  BanAppealActivity / WfacManager; WFAC state: Main.A5W -> WfacBanActivity
           │
           ▼
  [User submits appeal]
           │
           ▼
  Fetch purpose_public_keys (purpose_public_ek/ik/ik_sig, dummy ciphertext/nonce)
           │
           ▼
  Encrypt(form_data JSON {token, debug_info, description}, info "WA_INAPP_BAN_APPEALS", `C37414GLt`)
           │
           ▼
  Graph request to https://<host>.facebook.com/graphql by doc_id (section 10)
           │
           ▼
  Server review → wfac_ban_state update → WfacUnbanDecisionFragment
```

---

## 10. Appeal Request (2.26.41.6)

Found in `C37414GLt`: request `variables` JSON carries `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` and `app_id` (`"dev.app.id"`); plaintext before encryption is `{token, debug_info, description}`; context label `"WA_INAPP_BAN_APPEALS"` (key derivation info). Transport (found, `AbstractC40195HfH`): a plain Facebook Graph POST to `https://<host>.facebook.com/graphql` with `doc_id` and an `access_token` field, not MEX. `C37414GLt` passes `doc_id` **38509456535312323** when `hg3.A04.A00()` is true, otherwise **5473316762755318**. The operation name `submitBanAppeal` does not occur as a string in java_src, smali, assets or res of 2.26.41.6, and neither doc_id is in the project's query catalog, so the name is unverified. Before the submit, `C40191HfD` parses a first response with `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}` that supplies the key material for the encryption.

---

## 11. Changes vs 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| BizIntegrityQuery doc_id | `25975613018777537` | `28596420510007620` (rotated 2.26.38.10) |
| Request shape | `$userJids` list (reconstructed) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| DTO class | `C39833Hhl` | `C51530MtC` (17 fields: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 cols | + `is_meta_verified`, `fmx_business_holdout_group`; counts REAL |
| Store / manager | `BizIntegritySignalsManager.A08/A01` | store `LwI`, schema `C53116Nmn`, manager A02 60 s memory cache |
| start_chat_trust_signals reader | `C2M7.A0K` | `C57342Yp` |
| Trust tier enum | not recorded, 7 values | `M5B`, same 7 values |
| WFAC UI package | `com.whatsapp.waffle.wfac` (flat) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| WFAC prefs | 5 keys | + `wfac_last_ban_status_fetch_timestamp_ms` (5 s refresh throttle), `support_ban_appeal_user_banned_from_chat_disconnect` cleared on reset |
| Ban state parsing | 4 states | same; `NO_APPEAL_OPENED` mapped to `CHECKPOINTED` |
| Flags | 11061/11064/11065/12709/16349/19893/26697/27269/34166 | all present; + 19793 (N5r.A02) |
| SpamWarning codes 100-106 | yes | unchanged |
| integrity_tags | `automation_bulk_messaging`, `spam` | unchanged |
| SpamFlow | 92 categories | 97; `odml_scam_alert_*`, `biz_spam_banner_block`, others added |
| ML features | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | unchanged, in `integrityai.impl.InputFeatureProviderImpl` |
| Broadcast limit 20278 | 10000 / 30 days | unchanged |
| Ban/warning events at connect time | "no XMPP ban signalling" | XMPP login `<failure>`: reason 402 (SpamWarning / U13), 403 (perm ban -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | reacts to `wfac_ban_state` change | gone; `Main.A5W()` reads the state at start (reg state 21) and opens `WfacBanActivity` via `HBC` |
| `wfac_ban_state` writers | not recorded | ban-status fetch handler `C40191HfD`; `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED by launch source); no link from `is_banned` |
| BizIntegrity eligibility | "business accounts skip the check" | selects SMB contacts (`smb:` level) or `hostStorage == 2` (12709); forced path 16349; no 975-JID chunking in the fetch |
| 975 batch | GraphQL batch | local SQL message-count chunk (`N54`) |
| Flag 12709 | server-side whitelist | local `hostStorage == 2` check |
| Flag 2923, 24h account-age grace, `dhash` composition | claimed | not found in 2.26.41.6 |
| `integrity_tags` values | `automation_bulk_messaging`, `spam` | those strings are SMB soft-enforcement notification `type` values, not `integrity_tags` |
| SMB soft enforcement | `business_policy_violation` tag + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`; stored JSON keys `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`; flag 12840 |
| SpamFlow indices/count | 92, e.g. `odml_scam_alert_bottom_sheet_block` = 65 | 97 entries (`C9E2`), same names at shifted indices (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | opened by 4 data conditions | info sheet opened from FMX card buttons / `C512928n` |
| Appeal request | MEX `submitBanAppeal` mutation | Graph `https://<host>.facebook.com/graphql` by doc_id 38509456535312323 / 5473316762755318, preceded by a `purpose_public_keys` fetch; operation name not found |
| `wa_biz_integrity_chat_settings` | not located | found (`AHY`) |
| XMPP error tokens | `policy-violation`, `403` tokens | not in the dictionary; `forbidden`/`service-unavailable` and the 8.3 texts absent |

Still open in 2.26.41.6: category names behind `wfac_ban_violation_source` 0/1/2; consumer of flag 20278 and flag 12840; semantics of helper `N5r.A01`; content of WaFA reports; per-IQ error handling for restricted accounts (8.3); account-age display on the FMX card; flag behind `C1P2.A01()`.
