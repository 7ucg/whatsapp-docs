# WhatsApp Ban System — Full RE Report
**Version:** 2.26.26.4 | **Date:** 2026-07-16
**Scope:** Ban flow, WFAC lifecycle, spam signal collection, GraphQL protocol, appeal system, suspicious marking, prevention

---

## 1. Architecture Overview

```
[User action / server event]
         │
         ▼
  BizIntegrityQuery (MEX GraphQL, pull-based)
         │
         ▼
  BizIntegritySignalsManager ──► wa_biz_integrity_signals (SQLite, wa.db)
         │                             ├── is_banned (INT)
         │                             ├── is_suspicious (INT)
         │                             ├── trust_tier (TEXT)
         │                             ├── dhash (TEXT)
         │                             └── integrity_tags (JSON)
         │
         ▼
  WfacManager ──► SharedPreferences
         │             ├── wfac_ban_state = "BANNED" | "CHECKPOINTED" | "UNBANNED"
         │             ├── wfac_ban_violation_type
         │             ├── wfac_ban_violation_reason
         │             └── wfac_ban_status_token
         │
         ▼
  Main.A5D() ──► WfacBanActivity (hard ban UI)
              └─► SpamWarningActivity (pre-ban warning)
              └─► SuspiciousFmxBottomSheetFragment (soft enforcement)
```

**Critical finding:** Bans are NOT communicated via XMPP `<stream:error>`. The entire ban system runs over **MEX GraphQL (pull-based)**. The client polls the server — not the other way around.

---

## 2. Ban State Lifecycle (WFAC)

### 2.1 Four-State Machine

| State | Value | Meaning |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | No local cache |
| `CHECKPOINTED` | 1 | Soft restriction, may require verification |
| `BANNED` | 3 | Hard ban, account restricted, appeal possible |
| `UNBANNED` | 2 | Fully functional |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (0=SPAM, 1=PHISHING, 2=UNDERAGE, ...)
```

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
GraphQL: xwa2_fetch_wa_users (with token)
    │
    ▼
Response parsed by handler (case 3, default branch)
    │
    ├── Parses C209349Xq response
    ├── Stores via SharedPreferences: "wfac_ban_state" = state_string
    └── Error codes 1-4 logged separately; unknown → -1
```

### 2.4 Ban Reset Sequence

On successful appeal or account release (`WfacBanActivity`):
1. Clears: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`
2. Logs user out (finishAffinity)
3. Redirects to login screen

---

## 3. BizIntegrityQuery — GraphQL Protocol

### 3.1 Technical Details

| Parameter | Value |
|-----------|-------|
| Query name | `BizIntegrityQuery` |
| doc_id | `25975613018777537` |
| Schema | `whatsapp-android-mex` |
| Transport | MEX HTTP/2 POST → `/mex/query` |
| JID format | `<shortNum>@lid` (e.g. `1910@lid`) |

### 3.2 Request

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

### 3.3 Response DTO — `BizIntegritySignals` (C39833Hhl)

```
BizIntegritySignals(
  userJid, dhash, fbLinkedPageNumberOfLikes,
  igLinkedPageNumberOfFollowers, isBanned, isSuspicious,
  isSuspiciousStartChat, joinDateMs, phoneCountryCode,
  trustTier, mvFrictionEligibility, integrityTags,
  chatRowId, lastSyncTs, hideSafetyToolsForBusiness
)

Fields:
  integrityTags           → List of IntegrityTagInfo
  userJid                 → UserJid
  hideSafetyToolsForBiz   → Boolean
  isBanned                → Boolean  ← HARD BAN FLAG
  isSuspicious            → Boolean  ← SOFT ENFORCEMENT
  isSuspiciousStartChat   → Boolean
  mvFrictionEligibility   → Boolean
  chatRowId               → Long
  fbLinkedPageLikes       → Long
  igLinkedFollowers       → Long
  joinDateMs              → Long
  lastSyncTs              → Long
  dhash                   → String
  phoneCountryCode        → String
  trustTier               → String: "SUSPICIOUS" | "UNTIERED" | "TRUSTED"
```

### 3.4 IntegrityTags DTO

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
| 11061 | Suspicious account detection trigger |
| 11064 | Start-chat trust signal eligibility (on/off) |
| 11065 | Trust signal cache TTL in seconds (default: 86400 = 24h) |
| 12709 | Device check requirement / whitelist gate |
| 16349 | Enhanced account verification |
| 19893 | FMX card system-message logging |
| 26697 | BizIntegrity v2 |
| 27269 | Split incoming/outgoing message count |
| 34166 | start_chat_trust_signals writer |

---

## 4. Suspicious Marking — When, Why, How, Prevention

> **Core finding:** The client computes NO suspicious decision itself. All flags (`is_suspicious`, `trust_tier`, `isBanned`) come exclusively from the WA server via GraphQL. The client collects metrics, sends them up, and only renders UI based on the server response.

### 4.1 Who decides?

```
Client collects metrics (local):               Server decides:
─────────────────────────────────              ──────────────────────
• dhash (device fingerprint)          ──►      ML model evaluates
• message volume (in/out counts)      ──►      → assigns trust_tier
• country mismatch (number vs. IP)    ──►      → sets is_suspicious
• account age (join_date_ms)          ──►      → assigns integrity_tags
• FB/IG linked (follower counts)      ──►      → sets isBanned
• broadcast behavior                  ──►
• privacy token (TC-token)            ──►      GraphQL response returned
```

The client has **no local threshold** like "more than X messages → suspicious". That decision is 100% server-side.

### 4.2 Trust Tier Hierarchy (server-assigned)

Found in the WhatsApp APK as a compiled enum:

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

### 4.3 Server-ML: What signals are evaluated

The client attaches these data points to the GraphQL request — the server ML evaluates them:

| Signal | What it measures | Risk weight |
|--------|-----------------|-------------|
| `isCountryMismatch` | Sender country ≠ IP country | **Very high** |
| `mostRecentSenderScore` | ML reputation score based on recipient feedback | High |
| `dhash` | Device fingerprint (model + OS + app + number + timezone) | Identifies device across accounts |
| `join_date_ms` | Account age | New accounts = higher risk |
| `phone_country_code` | Country code of registered number | Geo-specific thresholds |
| Message volume | Outgoing/incoming count per time window | Bulk sending detection |
| Broadcast rate | Max 10,000 messages / 30 days | Hard limit |
| FB/IG follower count | Linked social accounts | Protective signal |
| Privacy token | TC-token from feature flag | Optional context |
| `integrity_tags` | Historical violations with timestamps | Cumulative risk |

`isCountryMismatch` and `mostRecentSenderScore` are the two concrete ML features found in the client. Feature flags 31535/31536 control their defaults.

### 4.4 When is the GraphQL check triggered?

**Eligibility gate** — all must be true:
1. Feature flag **11064** enabled
2. Not a business account (business accounts skip the entire check)
3. Not already whitelisted (flag 12709)
4. Cache expired OR no local cache

**Cache TTL:** Feature flag **11065** in seconds — default value **86400 (24 hours)**
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs >= timeout_ms) {
    // cache expired → new GraphQL call required
}
```

**Batch size:** 975 JIDs per GraphQL call

### 4.5 Known integrity_tag values

Only these two string constants were found concretely in the decompiled APK. Additional tags exist server-side and are stored as opaque JSON blobs:

| Tag | Meaning |
|-----|---------|
| `automation_bulk_messaging` | Automated bulk sending detected |
| `spam` | General spam behavior |

### 4.6 What concretely leads to suspicious — inferred from code

Since the client has no local threshold logic, these are the server-evaluated behavioral patterns (derived from which metrics are collected):

| Behavior | Why it's risky | Weight |
|----------|---------------|--------|
| High outgoing vs. incoming (sending only, no replies) | Bulk outreach pattern | Very high |
| Phone country ≠ IP country | `isCountryMismatch = 1.0` | Very high |
| Same dhash on multiple accounts | Device ban trigger | Very high |
| Broadcast > 10,000 recipients / 30 days | Hard limit, immediate flag | High |
| High `mostRecentSenderScore` (recipients reporting) | ML feedback loop | High |
| New account (< 24h, no contacts) | Low credibility | High |
| No FB/IG link + high outbound rate | Missing social proof | Medium |
| Existing integrity_tags | Prior violation effect | Medium–High |
| `is_reach_out = 1` + starting many unknown chats | Cold-contact pattern | Medium |

### 4.7 SpamWarning reason codes (pre-ban warning)

Delivered via intent extra `spam_warning_reason_key`:

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

92 total categories in the APK. The ones directly tied to suspicious state:

| Index | Category | Meaning |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Server-flagged suspicious → FMX block |
| 24 | `chat_fmx_card_block_suspicious` | Chat blocked due to suspicious flag |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Safety tools shown for suspicious |
| 65 | `odml_scam_alert_bottom_sheet_block` | On-device ML scam → block |
| 66 | `odml_scam_alert_bottom_sheet_trust` | On-device ML scam → trust |
| 71 | `one_to_one_spam_banner_block_server_flagged_suspicious` | 1:1 spam banner (server-flagged) |
| 80 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Trust prompt (server-flagged) |
| 84 | `user_initiated_chat_suspicious_banner_block` | Chat-start suspicious banner |
| 90 | `1_1_old_spam_banner_block` | Legacy spam banner |
| 91 | `1_1_spam_banner_report` | 1:1 spam report |

### 4.9 Protection mechanisms — what prevents suspicious marking

Factors that **protect** an account (positively weighted by server ML):

#### A) Business account status — strongest protection
Business accounts skip the **entire** suspicious eligibility check. No GraphQL check for suspicious is performed at all. Feature flag 2923 controls the non-business validation toggle.

#### B) Meta Verified (mvFrictionEligibility)
Field from GraphQL response: `"meta_verified_info.mv_friction_eligibility"`.
Effect: Lower friction thresholds — same actions trigger fewer warnings.

#### C) Linked social accounts (FB/IG)
```
fbLinkedPageNumberOfLikes     > 0  → protective signal
igLinkedPageNumberOfFollowers > 0  → protective signal
```
Higher counts = stronger signal to the server ML.
These are actual counts from the Meta Graph API, not booleans.

#### D) Account age grace period (flags 11064/11065)
```java
// New accounts get a protection window
if (current_time - join_date_ms < timeout_ms) {
    PROTECTION_ACTIVE = true  // no suspicious check
}
```
Default timeout: 86400s (24h) — accounts under 24h old are not checked.

#### E) Whitelist / validation list (flag 12709)
Certain accounts are pre-approved server-side. The client checks `A06(userJid)` — if on the list, the eligibility check returns early without a GraphQL call.

#### F) hideSafetyToolsForBusiness (field from response)
Hides the warning UI for business chats only. Does **not** change the suspicious status. Purely cosmetic.

### 4.10 Prevention — what the code reveals

**Behavioral:**
- Keep outgoing/incoming ratio balanced (not just sending, also receiving)
- No country mismatch: avoid VPN/proxy when the number is from a different country
- Keep broadcast rate under 10,000 / 30 days
- Don't use new accounts for mass outreach immediately (wait out the 24h grace window)
- Don't reuse the same device (dhash) across multiple accounts

**Account quality:**
- Link a real FB/IG account with actual follower counts > 0
- Acquire business account status (skips the eligibility check entirely)
- Meta Verified lowers friction thresholds

**Technical:**
- Send `privacy_token` (TC-token) with each BizIntegrityQuery when the feature flag is active
- Don't reuse dhashes from banned devices — server-side blacklist

**Timing:**
- GraphQL check fires on every chat open when cache > 24h old
- Suspicious status persists in SQLite until the server changes it
- Clearing the local cache doesn't help: the next chat open immediately triggers a new check

---

## 5. Local SQLite Databases

### 5.1 `wa.db` — `wa_biz_integrity_signals`

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
  mv_friction_eligibility           TEXT,
  integrity_tags                    TEXT,     -- JSON array
  chat_row_id                       LONG,
  last_sync_ts                      LONG,
  hide_safety_tools_for_business    INTEGER   -- 0/1
);
```

Writer: `BizIntegritySignalsManager.A08()`
Reader: `BizIntegritySignalsManager.A01(UserJid, boolean)` + in-memory `ConcurrentHashMap` cache

### 5.2 `wa.db` — `start_chat_trust_signals`

```sql
CREATE TABLE start_chat_trust_signals (
  jid                   TEXT PRIMARY KEY,  -- FK to wa_contacts
  is_sender_suspicious  INTEGER,           -- 0/1
  is_sender_new_account INTEGER,           -- 0/1
  created_ts            LONG
);

CREATE TRIGGER start_chat_trust_signals_contact_delete
  BEFORE DELETE ON wa_contacts
  BEGIN DELETE FROM start_chat_trust_signals WHERE jid = old.jid; END;
```

Reader: `C2M7.A0K(UserJid)` → returns `(is_sender_new_account, is_sender_suspicious)` tuple

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

Query label: `"GET_INTEGRITY_CHAT_INFO"` (batch query with `chat_row_id IN (...)`)

---

## 6. Spam Signal Collection (Client-side)

### 6.1 Device fingerprint (dhash)

Primary device-ban vector. Encodes: device model, OS version, app version, phone number, country code, timezone, Android ID, build fingerprint. Stored plaintext in `wa_biz_integrity_signals.dhash`. Server-side blacklist matching.

### 6.2 Message velocity

Metrics collected per time window:
- `incoming_count`: messages with `from_me = 0`
- `incoming_threads_count`: unique `chat_row_id` for received messages
- `outgoing_count`: messages with `from_me = 1`
- `outgoing_threads_count`: unique `chat_row_id` for sent messages
- Time-window binning (daily/hourly)
- Per-contact rate (grouped by JID)
- Deleted message count: `messages_count_after_privacy_token` in `integrity_deleted_chat_message_count`

Feature flag 27269 controls whether incoming/outgoing are counted separately or as a combined total.
Batch size: **975 JIDs** per processing call.

### 6.3 Broadcast limits (business accounts)

Feature config 20278: `{"max_messages": 10000, "farthest_time_days": 30}`
- **Hard limit: 10,000 messages per 30 days**
- Client enforces before send attempt
- Renewal timestamp tracked (`renewal_date`)
- Per-recipient throttling
- Marketing vs. regular broadcast classification

### 6.4 GAP enforcement (Global Abuse Prevention)

Real-time rule evaluation for message delivery gaps. Triggered by marketing message reception (feature flag 14837). Stores `LAST_MARKETING_MESSAGE_TIMESTAMP` in SharedPreferences.

Tracked state:
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

### 6.5 WaFA (Federated Analytics)

Transmitted encrypted via TEE channel with ACS encryption:
- Feature adoption patterns
- App crashes / failures
- Network latency, sync times
- RAM, storage, OS level
- Geofencing, timezone
- Session duration, frequency
- Connection type, signal strength

### 6.6 ML feature extraction (on-device scam detection)

Two concrete features found in the decompiled client:
- `isCountryMismatch` (float 0.0/1.0): sender country ≠ recipient country → **HIGH RISK**
- `mostRecentSenderScore` (float): ML reputation score for sender

Feature flags 31535/31536 control their default values. Results sent to server for secondary ML scoring.

---

## 7. UI Components: Suspicious, Warnings, Ban

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

Trigger conditions:
1. `is_suspicious == 1` → "This contact may be suspicious"
2. `is_suspicious_start_chat == 1` → friction on chat start
3. `is_reach_out == 1` (from `integrity_chat_info`) → phishing/spam marker
4. `chat_fmx_card_block_suspicious == 1` → complete send block

### 7.3 WFAC Hard Ban UI

| Class | Function |
|-------|---------|
| `WfacBanActivity` | Entry point, ban info + appeal button |
| `WfacBanInfoFragment` | Violation details + appeal link |
| `WfacBanDecisionFragment` | User action (appeal submitted) |
| `WfacUnbanDecisionFragment` | Post-appeal confirmation |

Trigger: `Main.A5D()` on SharedPreferences change to `wfac_ban_state = "BANNED"`

### 7.4 SMB Soft Enforcement

Triggered when: `is_suspicious=true`, `is_banned=false`, `integrity_tags` contains `"business_policy_violation"`.

```json
{
  "notification_type": "soft_enforcement",
  "violation_type": 1,
  "severity": "severe",
  "education_url": "https://www.whatsapp.com/...",
  "action_required": false
}
```

### 7.5 FMX Card (Trust Signal Card)

Shown when a chat is opened with a business/unknown contact. Displays FB follower count, IG follower count, account age. System message type 129 created on trigger. Async write to `start_chat_trust_signals` when BizIntegrity is active.

### 7.6 ODML Scam Alert (on-device ML)

Downloadable ML model via ACS token `"WA_ODML"` (TTL: 4 days, cache size: 64). User-toggleable via `ScamDetectionSettingsActivity`. Funnel tracked via session ID / source / entry point intent extras.

---

## 8. XMPP & Stanzas (ban context)

### 8.1 Critical: No XMPP ban signaling

Bans do NOT come via:
- `<stream:error>`
- `<presence type="unavailable">`
- `<failure>` elements
- WebSocket close codes

Bans come ONLY via MEX GraphQL (pull).

### 8.2 XMPP error tokens (binary dictionary)

XMPP stanza names are encoded as integer tokens in binary payloads:

| Token string | Meaning |
|-------------|---------|
| `stream:error` | Stream error container |
| `conflict` | Device conflict |
| `not-authorized` | Auth failed |
| `policy-violation` | Rate limit / policy breach |
| `item-not-found` | Resource not found |
| `server-error` | Generic server error |
| `401` | Unauthorized |
| `403` | Forbidden (ban-related) |

### 8.3 IQ responses for restricted accounts

```xml
<!-- IQ to banned account -->
<iq type="error" id="[request_id]">
  <error type="auth">
    <forbidden xmlns="urn:ietf:params:xml:ns:xmpp-stanzas"/>
    <text>Account restricted</text>
  </error>
</iq>

<!-- Message to banned account -->
<message type="error" from="server">
  <error type="service-unavailable">
    <text>User banned</text>
  </error>
</message>
```

WebSocket stays open. Bans are application-level, not transport-level.

---

## 9. Complete Data Flow (End-to-End)

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
    → Variables: { userJids: ["1910@lid"] }
    → doc_id: 25975613018777537
           │
           ▼
  Response → BizIntegritySignals DTO
           │
    isBanned?
     YES │                     NO │
         ▼                        ▼
  wfac_ban_state="BANNED"    isSuspicious?
  Main.A5D()                  YES │
  WfacBanActivity                 ▼
  (hard ban UI)           SuspiciousFmxBottomSheet
                          SpamWarningActivity
                          (trust_tier="SUSPICIOUS")
           │
           ▼
  wa_biz_integrity_signals (SQLite write)
           │
           ▼
  [User submits appeal]
           │
           ▼
  Noise-encrypt(form_data + "WA_INAPP_BAN_APPEALS")
           │
           ▼
  submitBanAppeal GraphQL mutation
           │
           ▼
  Server review → wfac_ban_state update → WfacUnbanDecisionFragment
```
