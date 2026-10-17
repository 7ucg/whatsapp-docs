# WhatsApp Username — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-17
**Scope:** Username check / set / reserve / delete, username key (PIN), LID relationship, privacy and visibility, w:mex GraphQL operations (doc_ids, variables, responses), notifications, USync lookup, validation rules, feature flags, Baileys notes

---

## 1. What a username is (technically)

A username is a server-side handle bound to an account, used so that a contact can be reached without exposing the phone number. All statements are static analysis of the decompiled APK. Tier: **found** = read in code or assets, **inferred** = deduced from code, **unknown** = not resolved.

The feature is built on three layers:

| Layer | Transport | Used for |
|-------|-----------|----------|
| Self management | `w:mex` IQ, persisted GraphQL (config `whatsapp-android-mex`) | check, set / reserve / delete, get, key (PIN) set / delete, multi-check |
| Lookup of others | USync (`xmlns="usync"`) and the MEX `UsyncQuery` variant | resolve `@username` (+ key) to a LID, fetch the username of a known JID |
| Push | MEX notifications | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Cross-device | app-state sync (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (carries `username`) |

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| Username manager | `C122815Lj` | `UsernameGet`, `UsernameSet` calls, local state update, rate-limit hook |
| Availability check | `C67402tT` | `UsernameCheck` call + response mapping |
| Multi check | `C76333Kg` | `UsernameCheckMulti`, chunks of 10 |
| Key API | `MexUsernamePinProtocolApi` | `UsernamePinSet` (set / delete key) |
| Local state / prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| State enum | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Eligibility mode | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Rate-limit store | `C67942uO` | backoff after 429 / 503 / 529 |
| Local validator | `C82003fB.A04`, `C1187754z` | length, charset, dot rules, regex |
| Key validator | `C1176550d` (+ `AbstractC111284pZ`) | key format |
| Key entry VM | `UsernamePinEntryViewModel` | submit key for a foreign username |
| USync client | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | classic usync stanza builder / parser |
| MEX USync | `C229259vZ`, `O0F` | `UsyncQuery` with `include_username` |
| Notification handlers | `C49822Lvi`, `C49821Lvh`, anon `X.2YG` in `AbstractC20380p4` | set / delete / update |

Naming: the user-facing name of the PIN is **username key** (strings "Username key", "Add a username key to control who can contact you"). Wire and code say `pin`.

---

## 2. MEX operations (doc_ids)

### 2.1 Where the doc_ids live

doc_ids are not literals in `java_src`. The client sends the operation name (`"UsernameSet"`, ...) with the config name `"whatsapp-android-mex"` (found, `C16880is`). The numeric id is read from `assets/whatsapp-android-mex_client_persist_ids.json`: `EnumC17010j7.WHATSAPP_ANDROID_MEX` maps to that file, `C17040jA.CMg(op)` returns the `doc_id` field, `AGb(op)` the `client_doc_id` field (found). Which of the two accessors fills the `query_id` attribute was not traced to the end (unknown); earlier captures on 2.26.26.4 show `query_id` equal to `doc_id`.

doc_ids below are **found** in the asset of 2.26.41.6:

| Operation | doc_id | Type | Call site | Response class |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | none found | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Notes:
- `UsernameGetRecommendationsQuery`: the name occurs only in the asset JSON. No class in `java_src` references it by string (found). Variables and response are unknown.
- The three notification names (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) have no entry in the persist-id asset. They are notification types, not requests (see 7).
- The asset has `operation_name_hash`, `operation_text_hash` and `client_doc_id` per op. Example `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Envelope

Built in `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Field | Rule (code) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | `get` for every operation, including mutations |
| `query_id` attribute | set only if 1 to 20 chars |
| body | JSON `{"queryId": ..., "variables": {...}}`, 1 to 8448000 bytes |
| null variables | `C16770ig.A03(k, null)` and `A02(k, null)` skip the key, so an absent value means the key is not sent |

Wire stanzas of live sessions are not reproduced here; this build was analysed statically only.

---

## 3. Operations in detail

### 3.1 UsernameCheck

Variables (found, `C67402tT.A00`):

| Variable | Type | Condition |
|----------|------|-----------|
| `username` | string | always |
| `include_suggestions` | bool | always (UI passes `false` in the typed-check path `C64H` case 21) |
| `source` | string | only if non-null |
| `session_id` | string | only if non-null |

`source` mapping (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, other -> null (not sent).

Response path (found, `C77183Np` default branch): `data.xwa2_username_check`

| Field | Type | Use |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | read only when `INVALID` |
| `rejection_reasons` | list of `C4G8` | read only when `INVALID` |
| `suggestions_eligible` | bool | defaults to `true` when the field is null |

`C4G8` values (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Mapping: `SUCCESS` -> `C76283Kb` (available); `INVALID` -> `C76303Kd` (unavailable, carries suggestions + reasons); `UNSET` -> neither branch assigns a result (callback gets the previous/null variable; behaviour unknown). Active local backoff -> `C76293Kc` (error with rate-limit code from prefs, see 5.3); the failure callback of the request itself was not read.

Rejection reasons drive the account-linking copy ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). In `C82003fB` any reason other than `UNSET` triggers the local error path with code 40601 (`A08(40601L)`); an empty or `UNSET`-only list shows "Username isn't allowed." The exact control flow around the loop is only partly decompiled (inferred).

### 3.2 UsernameCheckMulti

| Variable | Type | Notes |
|----------|------|-------|
| `usernames` | **list<string>** | array via `A00.A0B("usernames", list)`; the doc_id catalog types it as `str`, the code sends a list |

Batching (`C76333Kg.AG5`): the list is split into the first 10 and the rest; the rest is processed after a delay of flag **29327** (default 60, unit not resolved). Empty list returns an empty map without a request.

Response path `data.xwa2_username_check_multi.results[]` (found): each item has `username` and `response.result` (same `EnumC59782gh`). Mapping: `SUCCESS` -> available, `INVALID` -> unavailable (no suggestions, `suggestions_eligible=false`), anything else -> error. Names missing from the result are marked error.

Consumer: `UsernameAvailabilityCache` stores `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) per name. Purpose (prefetch for Facebook / Instagram username suggestions, string `foa_username_prefetch_cache`) is inferred.

### 3.3 UsernameSet (create / change / reserve / delete)

Variables (found, `C122815Lj.A00`):

| Variable | Type | Condition |
|----------|------|-----------|
| `username` | string | omitted when null (**delete**) |
| `reserved` | bool | always sent |
| `session_id` | string | only if non-empty (`C1YW.A08`) |
| `source` | string | only if the source int is non-null (see 3.1) |
| `pin` | string | only if non-null |

`reserved` is computed, not constant (found). Argument `z` (force) = true gives `false`. Otherwise: current state `ACTIVATED` or `CREATED` gives `false`; current state `RESERVED` or eligibility mode `RESERVATION` gives `true`; all other cases give `false`. So `reserved:true` is sent only for accounts in reservation mode or already holding a reservation.

Delete is a mode of the same operation: `username == null` -> log tag `delete`, otherwise `set` (also in `MexUsernamePinProtocolApi` for the key). With a null username the key `username` is not in the variables (found).

Client-side guard: before sending, if the rate-limit store reports an active backoff, the call fails locally with `username_creation_rate_limit_error_code` and the text "rate limit expiration time not reached" (found, `C122815Lj.A03`).

Success handling (`C122815Lj.A01`, found):

| Condition | Local state written (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username null or empty | `UNSET`, key pref cleared |
| `reserved` was true | `RESERVED` |
| activate flag | `ACTIVATED` |
| else | `ACTIVATED` if state was `ACTIVATED` and name equals the stored name, otherwise `CREATED` |
| `source` int is 1 or 2 | pref `username_set_via_account_linking` = (int == 2) |
| `pin` sent | pref `username_pin` updated |
| teen flag | pref `is_teen_account` = true |

Pref write is `Voip.REJECT_REASON_DECLINED`, which is the empty string `""` in this build (found).

Error handling (`C138725uA` case 2):

| HTTP-like code | Client action |
|----------------|---------------|
| 429, 503, 529 | backoff stored (5.3) |
| 304 | treated as success ("not modified"), local state still updated |
| no connection (`C213639Bb`) | `C4BO` "no network" result |
| other | `C4BN(code, message)` |

### 3.4 UsernameGet

Variables: none (the call builds an empty variable set, found, `C122815Lj.A02`). Marked `@Deprecated`, replaced by a suspend variant.

Response (found, `C138815uJ` case 34): `data.xwa2_username_get.username_info`

| Field | Use |
|-------|-----|
| `username` | stored; empty string if absent |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **the key is returned in clear and stored in the pref `username_pin`**; empty string if absent |

State mapping: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED` if the stored username equals the returned one and local state was `RESERVED` or `ACTIVATED`, else `CREATED`; null state or null `username_info` -> `UNSET`.

Error case 404 from the server clears the local username, key and state (log `clearSelfUsernameData NOT_FOUND`).

Whether the call is used as a heartbeat is unknown; the old note "polling heartbeat" is not supported by this build's code.

### 3.5 UsernamePinSet (username key)

Variables (found): `pin` (string), omitted when null.

| Action | Variables |
|--------|-----------|
| set key | `{"pin": "<key>"}` |
| delete key | `{}` (`A02` calls `A00(null)`) |

Operation name for both is `UsernamePinSet`; there is no separate verify operation. Verification of a foreign key is done in USync (4). Not connected: returns `C213639Bb("UsernamePinSet")` without request.

The key can also ride in `UsernameSet` (`pin` variable). `C81793ej.A0x` uses `UsernameSet` with the existing username and the new `pin` when a username is already stored locally (`A00 != null`), and `UsernamePinSet` otherwise (found).

The response class `C48557LJz` has no field access in the files read; response shape is unknown.

---

## 4. Lookup of other users

### 4.1 Classic USync by username (key flow)

Built in `C18670m9.A06` (jadx failed on this method, read from smali `X/0m9.smali`). Per `C222649hm` request entry: field `A0C` = username, `A0D` = key, `A05` = LID.

Attributes of the contact child (found in smali): `username` always; `lid` when a LID is known locally; `pin` when a key is set. The extra attributes are gated by flag **12402** (default `false`): when the flag is off, only `username` is written (found). The node name `contact` is inferred from the response parser, which reads child `contact` and its `username` attribute (`C18670m9` lines ~969-975).

```xml
<iq xmlns="usync" to="[server]" type="get">
  <usync mode="query" context="interactive" sid="..." index="0" last="true">
    <list>
      <user><contact username="name" lid="LID" pin="KEY"/></user>
    </list>
    <query><contact/> ... </query>
  </usync>
</iq>
```

Entry point: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), called by `submitPinForUsername`. Sync type `EnumC21760rz.A0J`, timeout 32000 ms. The attribute set `contact`, `pin`, `username` is in the log-redaction sets of `AbstractC40921lc` (found).

Local pre-resolve: `A0M.Aol(username)` looks up `lid_row_id` in table `lid_display_name` where `UPPER(username) = UPPER(?)`, newest row first (found, `C1S0`). The LID, if known, goes into the `lid` attribute.

### 4.2 Result evaluation (key entry)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Outcome | Condition |
|---------|-----------|
| correct key | result `UserJid` is a LID (`C14080dr`) |
| wrong key | result has no LID: log `[un-pin] incorrect PIN`, error text "Wrong key entered" |
| no network | `C9qA` code 1 |
| generic infra error | `C9qA` code 2 |
| requestor rate limit | `C225769os.A01` true: "Too many attempts made. Try later." |
| requestee rate limit | `C225769os.A00` true: "This account can't be reached with their key right now..." |

Client-side cached rate-limit check runs first when flag **16033** is on and JSON config **21995** has `enable_key_rate_limit` true (default true): `C30P.A00` against the own LID and against the target username. The username is stripped of `@` (`C0CX.A0i(username, '@')`).

On success the result is a **LID**, the chat is then addressed to the LID (inferred from the `C14080dr` check; the chat-open step was not traced).

### 4.3 Fetch username of a known LID

`C23638AId` (line ~600-650) builds a usync with `<list><user jid="LID"/></list><query><contact/><username/></query>`, mode/context from `EnumC21760rz.A0J` (found). The parser reads `username` as a child of `<usync>` result (`C18670m9` line 586, only when the request asked for it).

### 4.4 MEX USync (`UsyncQuery`)

`C229259vZ.A01` builds `UsyncQuery` (doc_id above). Relevant parts (found):

| Variable | Use |
|----------|-----|
| `query_input[]` | one entry per user: JID (`C493020r.A0C`), optional `client_known_username` (only when username requested and non-empty) |
| `include_username` | bool, set when any entry requests the username |
| `include_lid` | bool, requests `lid_info` |
| `telemetry.context` | lower-cased USync context |

Response per user: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` is polymorphic by type hash: a value type holding `username`, or a status type with `status` of `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED` is logged as "username not allowed to be queried" and clears the stored username; `NO_CHANGE` keeps it. `lid_info.lid_jid` carries the LID.

Gate: `ContactSyncHelper` refuses the MEX path with the log "cantUseMex as username ab prop is off" unless flag **8421** is on when a username is requested (found; default `false`).

---

## 5. Validation, limits, errors

### 5.1 Username format (local)

Validator `C82003fB.A04` (found), checks in this order:

| Order | Check | Error id (`C02U`) | Message string |
|-------|-------|-------------------|----------------|
| 1 | each char in `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | length >= min (flag **20494**, default 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | length <= max (flag **20459**, default 35) | 1 | same string |
| 4 | no leading `.`, no trailing `.`, no `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | at least one ASCII letter | 4 | "Choose a username with at least one letter" |
| 6 | regex (below) | passes or fails with 2 | n/a |

Regex built by `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

Case is not normalised by the validator; the local lookup `Aol` compares with `UPPER()`, so matching is case-insensitive locally (found). Whether the server treats names case-insensitively is unknown. Leading underscore is allowed by the regex; the UI text says "start with a letter", which is stricter than the regex (found, mismatch).

The UI also rejects web links: "Enter only your username, not a web link" (string present, check not traced).

### 5.2 Username key format

`C1176550d.A00` (found): flag **34350** is a regex string, default `^([0-9]{4}|[A-Z0-9]{6})$`. If the flag string is empty, the fallback is exactly four digits. Invalid regex logs `[un-pin] invalid username_key_regex` and accepts anything. Length bounds flags **34347** (min, 4) and **34348** (max, 6) feed only the error message path in `UsernamePinEntryViewModel.A0w`. Server-side rules are unknown.

So the old note "4-digit PIN" is incomplete: the shipped default accepts four digits or six upper-case alphanumerics.

### 5.3 Rate limits and backoff

`C67942uO` (found), active only with flag **28678** (default `false`):

| Item | Value |
|------|-------|
| trigger | `UsernameSet` error 429, 503 or 529 |
| duration | `Retry-After`-like string parsed as int seconds (`C23680AJt.A00`), else flag **28127** (default 30) seconds |
| storage | prefs `username_creation_rate_limit_backoff_expiry` (ms), `username_creation_rate_limit_error_code` |
| effect | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` fail locally until expiry |

### 5.4 Error code to message (`C82003fB.A02`, found)

| Code | Message |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403, 404, 429 | "Couldn't complete your request. Try again." |
| 500, 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406, 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| other | "We couldn't complete your request. Try again." |

40601 to 40603 are in the allowed set `AbstractC111104pH.A01` (only 40603 shown in code read). Their server semantics are unknown beyond the client text.

---

## 6. LID relationship

All found unless marked.

| Fact | Evidence |
|------|----------|
| Username lookups resolve to a **LID**, not to a phone JID | key success test `userJid instanceof C14080dr` (LID class); `lid_info.lid_jid` in MEX usync |
| Local map username -> LID | table `lid_display_name` (columns `username`, `lid_row_id`), query in `C1S0` |
| Notifications identify the user by LID | set / delete handlers parse `LidUserJid` (error text "Failed to parse LidUserJid") |
| Delete notification may carry a phone JID | handler checks `isPnPresent`; with PN present it casts a PN JID and acts, without PN it returns |
| Contact sync action | `ContactAction` has `username` (6) next to `lid_jid` (3), `pn_jid` (5); also `LidContactAction` (`lid_contact`, SyncActionValue field 61) |
| Chat start mode | SyncActionValue field **59** `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Only the sync codec was found; no consumer in UI code (unknown) |
| Companion feature string | when linking a companion the primary adds `username_supported` (flag 4745 or 20189), `username_reservation_only_mode` (20189 only), `username_account_linking_enabled` (flag 21199) to its feature list (`C25056AqU`) |

Inferred: a user that exists only as a username is reachable only through the LID until the owner shares the phone number; the strings "If you continue, your phone number will show in existing username chats and calls" (delete dialog) support this but the PN exposure path was not traced.

---

## 7. Notifications

Handlers extend `AbstractC23194A0r` and are registered in `AbstractC20380p4` (found):

| Notification | Handler | Behaviour |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | payload `xwa2_notify_username_on_change`: reads LID (field hash 107143) and username; stores via `InterfaceC11470Yz.BNU(lid, username)`; if the contact exists and is of the matching kind, refreshes the contact (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | payload `xwa2_notify_username_delete`: reads LID and PN (hash -983979708); with PN present runs the delete update (`C53594Nzh`) |
| `UsernameUpdateNotification` | anon `X.2YG` | reads a base64 hash from the payload, builds a USync request with reason `USERNAME_UPDATE_NOTIFICATION` and `EnumC21760rz.A0Q` (delta-style sync, inferred), log `usync triggered for hash` |

Text shown to the user: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", i.e. the server can reassign a username (revocation, `is_username_revoked` pref, `revocation_banner_dismissed_<username>`).

---

## 8. Feature flags

Flag IDs are AB-prop ids read through `C08J` (defaults from `C08J` tables). All defaults below were read from this build.

| Flag | Type | Default | Controls |
|------|------|---------|----------|
| **4745** | bool | false | primary: username creation (`CREATION` mode); also advertised as `username_supported` |
| **20189** | bool | false | primary: reservation-only mode (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: username features at all (else `DISABLED`) |
| **21199** | bool | false | account linking (FB / IG) enabled, advertised as `username_account_linking_enabled` |
| **16033** | bool | false | master gate for key features (`C79343Xx.A00`): key rate limit, key upsell, WABI username view |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (all default true when the JSON key is absent) |
| **8421** | bool | false | allows MEX `UsyncQuery` for username requests |
| **12402** | bool | false | adds `lid` and `pin` attributes to the usync `contact` node |
| **20494** / **20459** | int | 3 / 35 | min / max username length |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | key regex |
| **34347** / **34348** | int | 4 / 6 | key length bounds (error message) |
| **28678** | bool | false | enables rate-limit backoff store |
| **28127** | int | 30 | default backoff seconds |
| **29327** | int | 60 | delay before second batch of `UsernameCheckMulti` |

Companion eligibility (`C224069kP.A00`, bytecode-level read):

```
companion (identity of the A02 check inferred from the "open WhatsApp on your primary device" strings):
  23817 off, or pref username_reservation_creation_supported_on_primary false  -> DISABLED
  pref username_account_linking_enabled_on_primary true                         -> COMPANION_READ_ONLY
  state RESERVED                                                                -> COMPANION_READ_ONLY
  state not UNSET                                                               -> CREATION
  state UNSET and pref username_reservation_only_mode_on_primary true           -> COMPANION_READ_ONLY
  state UNSET otherwise                                                         -> CREATION
primary:
  4745 on -> CREATION;  else 20189 on -> RESERVATION;  else DISABLED
```

The three `*_on_primary` prefs are read only here; where they are written was not found (unknown).

---

## 9. Privacy and visibility

| Aspect | Finding | Tier |
|--------|---------|------|
| Purpose | "Keep your phone number private with a username"; people who do not have the number saved see the username instead | found (strings) |
| First contact | with a key set, people "you haven't interacted with" must enter the key before contacting the username | found (strings) |
| Key sharing | username share action can include the key (pref `username_share_include_pin`, migrated away in `C138535tr`); strings "Share your username and key" | found |
| Where the number is hidden | community admins and channel admins see the number unless a username is set; channel followers see neither | found (strings) |
| Group / thread telemetry | `has_username`, `has_username_pin`, `is_username_thread` fields in message send telemetry (`DZ1`, `RQG`) | found |
| Key at rest | the own key is returned by `UsernameGet` and stored in plain prefs `username_pin` | found |
| Third-party chats | "Usernames and contacts added to third-party chats will not save to your phone" | found (string) |
| Business | "This username is only available on WhatsApp Business" appears as a rejection text | found (string) |
| Who can query | the MEX usync status `NOT_ALLOWED` shows the server can refuse username disclosure per requester | found (enum), rule unknown |
| Minors | pref `is_teen_account`; parent texts "Your child created the username ..." | found |

Visibility rules enforced by the server (who may resolve a username, key rate limits, reassignment) are unknown from the client.

---

## 10. Baileys notes

The envelope in 2.2 is generic; a Baileys client can build it. This is **inferred**, not tested here.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| Risk | Reason |
|------|--------|
| doc_id drift | ids belong to this build's asset; other builds may differ (unknown) |
| `session_id` | the code sends it when present; whether the server requires the same value for check and set is unknown |
| key attributes | `lid` / `pin` on `contact` are behind flag 12402; the server may ignore them for clients without the flag (unknown) |
| local rules | length, charset and dot rules are client-side; the server rules are unknown |

---

## 11. Key distinctions

| Do not confuse | Difference |
|----------------|------------|
| Username key vs account PIN / 2FA | Username key (`pin` in `UsernamePinSet`, `username_pin` pref) gates first contact via username. It is unrelated to registration 2FA |
| `reserved` variable vs `UsernamePinSet` | `reserved` belongs to `UsernameSet` and marks a reservation; the key has its own op |
| `RESERVED` state | local `C4DU.RESERVED` / server `state=RESERVED` is a held name not yet usable; `ACTIVATED` and `CREATED` are usable |
| Delete | there is no delete op; `UsernameSet` without `username` deletes; key delete is `UsernamePinSet` with `{}` |
| Check result `INVALID` | covers taken, linking-required and format problems; the detail is in `rejection_reasons` |
| Username vs LID | username is a handle; the addressing identity is the LID |
| `source` ints | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; not the same ints as `C02U` error ids |
| doc_id vs `client_doc_id` | both are in the asset; the captured ids equal `doc_id` |
| Notifications vs ops | the three `Username*Notification` types are push handlers, not requests |
| Cross-repo labels | `25975613018777537` is absent from this build's persist-id asset; `25741205615468935` is `GetTextStatusList` in this build. Neither is a username operation here |

---

## 12. End-to-end flow

```
[User]                [Client]                              [Server]
  │ type name           │                                      │
  ▼                     │                                      │
 local validate ────────┤ charset, 3..35, dots, regex (5.1)    │
  │ ok                  ▼                                      │
  │              UsernameCheck {username, include_suggestions,  │
  │                             source, session_id}  ─────────►│
  │                     │◄──── xwa2_username_check {result,    │
  │                     │       suggestions, rejection_reasons}│
  │ SUCCESS             │                                      │
  ▼                     ▼                                      │
 confirm ─────────► UsernameSet {username, reserved,           │
                      session_id, source, [pin]} ─────────────►│
                        │◄──── ok | 304 | 40601..40603 | 429/503/529
                        ▼                                      │
                  write prefs: state, username_pin             │
                  429/503/529 -> backoff (flag 28678)          │
                                                               │
 [Owner sets key] ► UsernamePinSet {pin} | {} (delete) ───────►│

 [Other user, first contact]
  │ enter @name + key
  ▼
 validate key (flag 34350) ► usync contact{username,[lid],[pin]} ──►[Server]
                        │◄──── user jid (LID) | no LID | rate-limit flags
                        ▼
              LID  = open chat addressed to the LID
              none = "Wrong key entered"
              limit = "Too many attempts" / "can't be reached"

 [Server push]
   UsernameSetNotification (lid, username)  -> update local map
   UsernameDeleteNotification (lid, pn)     -> update contact
   UsernameUpdateNotification (hash)        -> usync delta
```

---

## 13. Unknowns

| Topic | Reason |
|-------|--------|
| Exact accessor feeding `query_id` | `doc_id` vs `client_doc_id` consumer not traced to the IQ builder |
| Response shape of `UsernamePinSet`, `UsernameSet` | response classes have no field access in code read |
| `UsernameGetRecommendationsQuery` | no call site, no variables |
| Server-side username and key rules | client only validates locally |
| Meaning of 40601-40603 on the server | only client strings found |
| Origin of `*_on_primary` prefs | no writer found |
| `username_chat_start_mode` effect | no consumer found |
| `UsernameGet` usage pattern (heartbeat) | not supported by code read |
| Chat-open step after a correct key | not traced past the LID check |
| Actual traffic | static analysis only |
