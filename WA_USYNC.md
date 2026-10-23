# WhatsApp USync — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** USync IQ (`xmlns="usync"`): modes, contexts and sync types, request and response stanza structure, query protocols (contact, sidelist, status, text_status, picture, business, devices, disappearing_mode, lid, username), contact lookup and phone-number discovery, device list sync, key-index and ADV checks, LID mapping, privacy-token enrichment, MEX `UsyncQuery` and per-protocol routing, rate limits and backoff, client triggers, feature flags, Baileys comparison

---

## 1. What it is (technically)

USync is the bulk "who is this user" query. One IQ carries a list of users and a list of protocols (data types); the server answers per user and per protocol. The same stanza shape serves four jobs: address-book upload and download, single phone-number lookups, profile data refresh (status, picture, business, disappearing mode), and device list refresh for message fan-out. All statements come from static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code, **inferred** = deduced, **unknown** = not resolved. Obfuscated names are per-build and were re-resolved in 2.26.41.6.

| Layer | 2.26.41.6 name | Role |
|-------|----------------|------|
| Stanza builder / parser | `C18670m9` (log tag `UniSyncProtocolHelper`): `A06` build, `A07` send, `CFS` result, `Brt` iq error, `Bog` delivery failure | builds `<iq xmlns="usync">`, parses `<usync>` result |
| Request model | `A05` (type + users + options), `A0A` (per-user builder), `C222649hm` (per-user request), `C222589hg` (pending request, one per iq id) | what to ask |
| Sync type | `EnumC21760rz` (30 values), `EnumC21770s0` context, `EnumC21780s1` mode, `EnumC21790s3` scope | `mode` / `context` attribute source |
| Single lookups | `C23638AId` (`ContactQuerySync`) | phone number, JID, username, LID to username |
| Batch sync | `C18580m0` (`ContactSyncHelper`), anonymous callback `X.0m7` | multi-protocol sync, MEX vs classic choice, backoff prefs |
| Public entry points | `C18230lP` (`ContactSyncMethods`), `C21810s5` builder, `C21830s7` request, `C21820s6` protocol set, `EnumC21800s4` reason (77 values) | all features call these |
| Result applier | `N27` (`contactsyncresultupdater`), `C51909N4g` (`ContactSyncDevicesUpdater`) | writes DB, LID map, devices |
| Device / ADV | `C23310uY` (`DeviceSyncManager`), `SyncDevicesJob`, `C24230w2` (`DeviceADVInfoHandler`) | device refresh jobs, key-index verification |
| Privacy enrichment | `C223659jg` (`ProfilePrivacyEnrichmentFetcher`), `C197138a8`, `C197148a9` | tctoken and common group per user |
| MEX variant | `C229259vZ` (`MexUsyncQueryHelper`), `M4I` (route), `M5H` (protocol bit) | `UsyncQuery` and routing |
| Backoff store | `C18800mM`, prefs file `contact_sync_prefs` | `*_sync_backoff`, `*_full_sync_wait` |

Decisive points:

- The Android builder emits ten query children: `contact`, `sidelist`, `status`, `text_status`, `picture`, `business`, `devices`, `disappearing_mode`, `lid`, `username`. It has **no** `bot` child and no feature child (found, all string constants of `A06`). `reachability`, `linked_profiles`, `orgs` and `ddm` exist only in the MEX variant (section 8).
- Android has four modes and ten contexts (section 2); every request carries `sid`, `index="0"`, `last="true"` in the entry points read.
- Users go in `<list>` (normal) or `<side_list>` (contacts outside the address book).
- Profile requests carry a per-user privacy proof (stored tctoken, or a common group JID), see section 7 and WA_TCTOKEN_CSTOKEN.md.
- Username lookups are covered in WA_USERNAME.md; this report only records the shared stanza parts.

---

## 2. Stanza envelope

### 2.1 Request (found, `C18670m9.A06`)

```xml
<iq xmlns="usync" id="0AB1" type="get">                       <!-- `to` added by the sender, inferred -->
  <usync sid="sync_sid_query_<uuid>" index="0" last="true"
         mode="query" context="interactive" [allow_mutation="true"]>
    <query>                                                   <!-- protocol children, section 3 -->
      <contact [addressing_mode="lid"]/> <devices version="2"/> <picture type="preview" size="N"/> ...
    </query>
    <list>      <user jid="..." [common_gid="..."]> per-user children </user> ... </list>
    <side_list> <user jid="LID" pn_jid="PN"> ... </user> ... </side_list>
  </usync>
</iq>
```

| Part | Rule (code) |
|------|-------------|
| iq `id` | `C10140Tq.A0G()`: `"0"` + hex of a counter, wraps at 65536 (logs "iqId too large") |
| `sid` | `AbstractC43461pq.A00(prefix)` = prefix + `_` + random UUID; prefixes `sync_sid_query`, `ContactSyncHelper/sync_sid_<scope>`, `..._mex_profile` |
| `index` / `last` | from the call: `A07` always passes `0` and `true` |
| `mode`, `context` | `EnumC21780s1.modeString`, `EnumC21770s0.contextString` of the sync type |
| `allow_mutation="true"` | set when `A05.A04` is true: built for full / delta types when `C11980aQ.A0G()` holds (meaning not traced) |
| contact child | present when any request asks for contact (`A05.A03`) or when no other protocol is requested |
| REGISTRATION context | sent through `C10140Tq.A0A(...)` instead of `A06(...)` (found); difference not traced |
| Send options | iq timeout argument 32000 ms (`ContactQuerySync`) or 128000 ms (`ContactSyncHelper`); numeric `102` passed to the sender (meaning unknown) |

### 2.2 Modes (found, `EnumC21780s1`)

| `mode` | Meaning |
|--------|---------|
| `full` | complete resync of the scope |
| `delta` | only changes since the last sync |
| `query` | lookup of the listed users, no state change |
| `download` | pull the server-side contact set |

### 2.3 Contexts (found, `EnumC21770s0`)

`metadata`, `registration`, `interactive`, `background`, `notification`, `message`, `add`, `voip`, `snapshot`, `wamo`.

### 2.4 Sync types (found, `EnumC21760rz`)

Name, wire code, context / mode / scope. Codes 10-15 and 17-20 are unused. Scope `PB` = phone book, `SL` = side list, `MP` = multi-protocol query. The code is logged and kept in metrics; the stanza carries only context and mode.

| Names (code) | Context / mode | Scope |
|--------------|----------------|-------|
| `REGISTRATION_FULL` (0) | registration / full | PB+SL |
| `INTERACTIVE_FULL` (1), `INTERACTIVE_DELTA` (2) | interactive / full, delta | PB+SL |
| `BACKGROUND_FULL` (3), `BACKGROUND_DELTA` (4) | background / full, delta | PB+SL |
| `NOTIFICATION_CONTACT` (5) | notification / delta | PB |
| `INTERACTIVE_QUERY` (6), `ADD_QUERY` (9) | interactive / query, add / query | PB |
| `NOTIFICATION_SIDELIST` (7) | notification / query | SL |
| `INTERACTIVE_DELTA_SIDELIST` (8) | interactive / delta | SL |
| `BACKGROUND_QUERY_PICTURES` (16), `BACKGROUND_MULTI_PROTOCOL_QUERY` (21), `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` (22) | background / query | MP |
| `REGISTRATION_COMPANION_MULTI_PROTOCOL_QUERY` (23) | registration / query | MP |
| `INTERACTIVE_MULTI_PROTOCOL_QUERY` (24), `MESSAGE_MULTI_PROTOCOL_QUERY` (25), `VOIP_MULTI_PROTOCOL_QUERY` (26) | interactive, message, voip / query | MP |
| `NOTIFICATION_MULTI_PROTOCOL_QUERY` (27), `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY` (28) | notification / query | MP |
| `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` (29), `WAMO_MULTI_PROTOCOL_QUERY` (38) | message, wamo / query | MP |
| `CONTACT_DONWLOAD` (30, sic) | background / download | PB |
| `CONTACT_FORCE_UPLOAD` (31) | metadata / delta | PB+SL |
| `CONTACT_UPLOAD` (32), `NATIVE_CONTACT_DELTA` (39) | background / delta | PB |
| `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` (33) | background / full | PB |
| `CONTACT_UPLOAD_SNAPSHOT` (34), `CONTACT_DOWNLOAD_SNAPSHOT` (35), `CONTACT_FULL_SYNC_SNAPSHOT` (36) | snapshot / delta, download, full | PB, PB, PB+SL |
| `CONTACT_RESTORE_FULL_SYNC` (37) | background / full | WA address book |

Helpers: `A00()` = delta, `A01()` = full, `A02()` = full and registration. Only `BACKGROUND_QUERY_PICTURES` makes the picture query type `image`; every other type asks for `preview`.

---

## 3. Query protocols

### 3.1 Overview (found)

| Protocol | `<query>` child | Per-user request child | Response child (per user) | Notes |
|----------|-----------------|------------------------|---------------------------|-------|
| contact | `<contact/>` | `<contact>+digits</contact>`, `<contact username=.. lid=.. pin=../>`, `<contact type="delete"/>`, empty `<contact/>` | `<contact type="in\|out\|invalid">text</contact>` | in `<list>` only |
| sidelist | `<sidelist [addressing_mode="lid"]/>` | `<sidelist type="delete"/>` | `<sidelist type=..>` in `<side_list>` | users outside the address book |
| status | `<status/>` | `<status t="secs"/>` when a cached time exists | `<status t code type>text</status>` | About text |
| text_status | `<text_status/>` | none | `<text_status last_update_time ephemeral_duration_sec text><emoji content/></text_status>` | flag **5839** |
| picture | `<picture type="image\|preview" [size="N"]/>` | `<picture id="N"/>` cached id | `<picture id direct_path hash/>` | privacy-enriched |
| business | `<business><verified_name/><profile v="N"/></business>` | `<business><verified_name serial/><profile tag/></business>` | `<business pn_jid><verified_name verified_level host_storage actual_actors privacy_mode_ts>cert</verified_name>...</business>` | `v` = AB **471** & 0x3FFC (default 1140) |
| devices | `<devices version="2"/>` | `<devices device_hash ts expected_ts/>` | `<devices><device-list><device id key-index is_hosted/></device-list><key-index-list ts expected_ts>bytes</key-index-list></devices>` | section 5 |
| disappearing_mode | `<disappearing_mode/>` | none | `<disappearing_mode duration t ephemerality_disabled/>` | `ephemerality_disabled` read only with flag **21235** |
| lid | `<lid/>` | `<lid jid="LID"/>` when the PN user has a known LID | `<lid val="LID"/>` | section 6 |
| username | `<username/>` | `<username username="@known"/>` | `<username>text</username>` or `contact@username` | see WA_USERNAME.md |

Per-user attributes on `<user>`: `jid` (PN or LID), `pn_jid` (side-list entries), `common_gid` (section 7). A user may also contain a `<tctoken>` child holding the stored token bytes. In responses `<user>` also has `pn_jid` and `new_jid`; the parser takes `jid`, falls back to `pn_jid` when `jid` is missing.

### 3.2 Contact (found)

| Form | Condition | Notes |
|------|-----------|-------|
| `<contact>+15550001111</contact>` | phone lookup | the number string is passed through as given by the caller; for JID-based lookups `C23638AId.A05` prefixes `+` when the JID is a phone-number JID and (`C11980aQ.A0M()` / AB **26739** is on, or the type is `ADD_QUERY`) |
| `<contact>15550001111</contact>` | PN user with LID addressing (`C11980aQ.A0L()`, AB **14565**) | digits without `+` |
| `<contact username="u" [lid=".."] [pin=".."]/>` | username lookup | `lid` / `pin` only with AB **12402**, otherwise only `username` |
| `<contact type="delete"/>` | request marked deleted | address-book removal in upload sync |
| `<contact/>` | LID user with no username | placeholder |
| query `<contact addressing_mode="lid"/>` | AB **14565** | LID-addressed contact sync |
| query `metadata_version="3"` | delta type and an internal flag | the flag is only ever assigned from a constant false in the path read, so it is probably never sent (inferred) |

Response `type`: `in` = registered (internal code 1), `out` = not registered (2), `invalid` = number not valid (3); any other value throws a corrupt-stream error. Text content of each `<contact>` is appended to a per-user list.

Result-level `<result><contact version refresh integrity snapshot_recovery>`: `version` kept in the result, `refresh` seconds feed the full-sync wait (section 9), `integrity` is `pass` (default), `pending` or `timelock` (internal 1 / 2 / 3), `snapshot_recovery` (`pending` / `pass`) is read only with flag **22410**.

### 3.3 Status and text status (found)

`<status>` result handling: `type="fail"` with `code` 401 / 403 / 404 = hidden by privacy (internal state 2); other `fail` = failure (0); non-empty text without error = set (1, `t` * 1000 = set time); empty without error and text-status flag off = none (3). State names are inferred.

With flag **5839** on, a `<text_status>` child overrides state 1 / 3: text = `text`, emoji = `<emoji content>` (default "" when absent), set time = `last_update_time` seconds, expiry = set time + `ephemeral_duration_sec` when that is above 0 (state 3). A hidden status (state 2) is a failure node with 401 / 403 / 404, not an empty string.

### 3.4 Picture, business, disappearing mode (found)

| Protocol | Request detail | Response parsing |
|----------|----------------|------------------|
| picture | `type="preview"` plus `size` only when AB `AbstractC36291cD.A06` is above 0 (capped at 300); per-user `id` only when a cached id exists | `id` (int, -1 when no `<picture>`), `direct_path`, `hash` |
| business | `profile v` = `C35756Fe7.A00()` = AB 471 & 16380; per-user `serial` / `tag` only from the local business row | `pn_jid` (fills the PN of a LID user and stores the LID-PN pair), `verified_name`: `verified_level`, `host_storage`, `actual_actors`, `privacy_mode_ts`, node bytes = certificate |

---

## 4. Contact lookup and phone-number discovery

### 4.1 Single lookups (found, `C23638AId`)

| Method | Type | Builds | Result |
|--------|------|--------|--------|
| `A0E(userJid, type, n)` | `INTERACTIVE_QUERY` or `ADD_QUERY` only | user JID + contact, status, picture, business, disappearing_mode, lid, username; devices if **5751**; text_status if **5839** | `C43621q7` |
| `A0C` / `A0A(type, n, number)` | same two types | phone number as `<contact>`; same set (status only when the caller passes true) | `Pair(result, user)` |
| `A0B(type, n, number)` ("Lightweight") | any | phone + contact, lid; devices if **5751** | `Pair` |
| `A0D(type, numbers)` | any | many numbers: contact, status, picture, business, disappearing_mode, lid; text_status if **5839** | array of users |
| `A0F(lid)` | `INTERACTIVE_QUERY` | `<user jid=LID/>` + `<contact/><username/>` | username of a LID |
| `A0G(username, key)` | `INTERACTIVE_QUERY` | username (+ key) as `<contact>`; also status, picture, business, disappearing_mode, lid, username only if **33609** is false, text_status if **5839** | WA_USERNAME.md |

Guards (found): network check (`network_unavailable` result), in-flight dedupe maps keyed by JID or number (second call returns "skip too frequent query", no time window), per-call `sid`, wait up to 32000 ms, then timeout result. With AB **14565** off, a LID JID with a known phone number is rewritten to that number before the request is built (`AbstractC197018Zw.A0Y`; direction inferred from the `+` prefix step that follows).

### 4.2 Result codes (`C43621q7`, names inferred from use)

0 `A04` network unavailable; 1 `A08` skipped (nothing to send or too frequent); 2 `A07` success with changes (contact-removal path); 3 `A06` success; 4 `A03` failure (empty result, timeout, error); 5 `A05` rate limited (result error 429); 6 `A02` exception. `A01()` is true for 1, 2, 3. An empty `<list>` with a contact-protocol error 429 gives 5, any other empty list gives 4.

### 4.3 Which features reach the phone book (found)

| Path | Entry | Type | Protocols (`C21820s6`) |
|------|-------|------|------------------------|
| Background full sync (primary only) | `C18230lP.A0F(reason)` | `BACKGROUND_FULL` | everything except orgs |
| Forced full sync | `A01` helper, periodic job `RunnableC23953AUi` case 23 | `BACKGROUND_FULL`; companion: `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` | contact (`A0J`) or side list (`A0K`); companion: all but contact / side list (`A0D`) |
| Force upload, delta upload, download | `A07(reason)`, `A0G(reason)`, `A0C()` | `CONTACT_FORCE_UPLOAD`, `CONTACT_UPLOAD`, `CONTACT_DONWLOAD` | contact + lid (`A0G`) |
| Native contacts changed | `A0J(reason, jids)` | `NATIVE_CONTACT_DELTA` | all but orgs |
| Delayed post-registration sync | `A0L` (pref `registration_contact_sync_delayed`) | `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` | contact + lid |
| Side contact on first display | `A0E(contact)` | primary: `INTERACTIVE_DELTA_SIDELIST`; companion: `INTERACTIVE_MULTI_PROTOCOL_QUERY` | all but orgs / all but contact, side list, orgs |

Protocol sets (`C21820s6` constants, found): `A0S` username; `A0G` contact + lid; `A0P` status; `A0Q` text status; `A0O` picture; `A0F` business; `A0H` devices; `A0E` business + devices; `A0N` payment; `A0I` disappearing mode; `A0L` lid; `A0M` orgs; `A0D` all but contact, side list, orgs; `A0R` as `A0D` without lid; `A0J` contact + `A0D` set; `A0K` side list + `A0D` set; `A0C` all but orgs. LID is implied when contact or side list is synced.

`C21830s7` (SyncRequest) persists options as JSON: `sync_is_urgent`, `sync_only_if_changed`, `sync_only_if_registered`, `sync_clear_whatsapp_sync_data`, `sync_should_retry` and one `sync_<protocol>` boolean per protocol (found); builder default retry int 5 (meaning inferred).

### 4.4 Notification-driven lookups (found)

The server pushes a hash instead of a number; the client resolves it and runs a query.

| Notification handler | Payload | Sync | Protocols |
|----------------------|---------|------|-----------|
| `AnonymousClass145` (contact update), `add` | up to 2 hash children typed `pn` (default) or `lid`; primary only | `NOTIFICATION_CONTACT` | all but orgs |
| same, update | base64 hash | `NOTIFICATION_SIDELIST` | status, picture, lid, username, text_status |
| `C1S0` status notification | attribute `hash` (base64) | `NOTIFICATION_SIDELIST` (reason `NOTIFICATION_STATUS`) | status only |
| `C1S0` picture notification | attribute `hash` | `NOTIFICATION_SIDELIST` (reason `NOTIFICATION_PICTURE`) | picture only |
| `AnonymousClass142` business notification (jid-less removal with `hash`) | base64 hash | `NOTIFICATION_SIDELIST` (reason `NOTIFICATION_BUSINESS`) | business set (constant not resolved) |

The hash matches local users with `digest(user + "WA_ADD_NOTIF")` compared byte-prefix-wise (`AbstractC43461pq.A04`); digest algorithm is chosen by the caller (not traced). A server-triggered "forced sync" (`RunnableC23951AUg`, reason `SERVER_FORACE_SYNC`) runs `BACKGROUND_FULL` or the companion type.

### 4.5 Contact sync over MEX mutations (found, not USync)

New in the build: Kotlin contact sync (`com.whatsapp.contact.sync.kmp`, `.handler`) uses `w:mex` mutations instead of the usync IQ. Config `whatsapp-android-mex`, doc_ids from the persist-id asset.

| Operation | doc_id | Variables (found) | Response |
|-----------|--------|-------------------|----------|
| `ContactsDeltaSyncMutation` | `28247314474869813` | `context` (`SEARCH`, `OSAB_IMPORT`, `EMAIL_IMPORT`, `QR_SCAN`), `primary_contacts_add[]`, `primary_contacts_remove[]` (`lid`, `modifier` = `BEST_EFFORT_DOWNGRADE_TO_WA_SIDE_CONTACT`, `normalized_phone`), `side_contacts_add[]` | `xwa2_contacts_delta_sync`: `results[]` {`client_cached_lid`, `failed`, `detail` (union: raw_pn / primary_normalized_phone / lid / phone_status; side_status; username_status; email_status; normalized_phone)}, `retry_after_seconds` |
| `PrimaryContactsFullSyncMutation` | `36963099086669113` | not read | not read |
| `SideContactsFullSyncMutation` | `26880700761604398` | `context`, `cursor`, `side_contacts[]` (`client_cached_lid`, `normalized_phone`) paged | `results[]` like above, `retry_after_seconds` |

What gates this path against the usync path was not found (unknown). `retry_after_seconds` is the MEX equivalent of the usync `backoff`.

---

## 5. Device list sync, key index, ADV

### 5.1 Request and response (found)

Request: query child `<devices version="2"/>`; per user `<devices device_hash="H" ts="T" expected_ts="E"/>`, sent only when a hash exists (`ts`, `expected_ts` only when above 0 and `expected_ts` above `ts`). Values come from the local device row (`C15070fj.A07/A00/A04`).

Response per user: `<devices>` either contains an `<error code text>` (user gets state -1, log "parseUser/partial error") or:

| Node | Attributes | Parsed into |
|------|------------|-------------|
| `<device-list><device .../>` | `id` (int), `key-index`, `is_hosted` | `DeviceJid(user, id)` -> key index; a mismatch between the JID's hosted state and `is_hosted` reports `invalid-hosted-flag` |
| `<key-index-list ts expected_ts>` | `ts` (seconds), `expected_ts` (default 0), content bytes | signed key-index list, stored raw |

Result-level `<devices>` may carry `<error>` with backoff (section 9). MEX route: `include_devices` plus `devices{hash, timestamp, expected_timestamp}`; client log labels for dropped results: `devices_dropped_status_error`, `devices_status_indeterminate`, `devices_hash_match_noop`, `devices_dropped_empty_without_hash`, `devices_dropped_no_jid`, `devices_dropped_stale_timestamp`, `devices_dropped_adv_proto_missing`, `devices_dropped_adv_verify_failed`, `devices_dropped_adv_data_update_failed`, `devices_outcome_unset`.

### 5.2 Update checks (found, `C51909N4g`, `C24230w2`)

| Check | Behaviour |
|-------|-----------|
| key-index list empty | "update keyIndex is empty", no update |
| response `ts` older than stored | "timestamp is less than existing one", dropped |
| stale expected-ts retry | response ts below stored, `expected_ts` equals stored ts and stored value older than pref `adv_last_device_job_ts`: logs a usync fetch error and emits WAM event `wam_adv_expected_ts_unavailable` (`C49716Ltt`), returns true (caller effect not traced) |
| new device info | `C51909N4g.A00` clears the stored expected ts when the new ts is at least the stored one; account type derived from the device set (`C9U.A01`) |

### 5.3 ADV signed key-index verification (found, `C24230w2.A07`, `A04`)

| Step | Detail |
|------|--------|
| Parse | key-index bytes -> `ADVSignedKeyIndexList` (`C25786BAu`): `details` (**1**), `account_signature` (**2**), `account_signature_key` (**3**, optional) |
| Public key | primary device identity from the local identity store; if the proto carries `account_signature_key` and it differs from the local key, that key is used and tagged `adv`; with neither key: warning "no primary identity" |
| Signature | verify `account_signature` over `{0x06, 0x02} || details` with the chosen key (`AbstractC30195DBc.A08`); failure logs "fail to verify account signature" and emits a WAM event (`C55912St`, 1 = local key, 2 = adv key) |
| Details | `details` -> `ADVKeyIndexList` (`BCB`): `raw_id` (**1**), `timestamp` (**2**), `current_index` (**3**), `valid_indexes` (**4**), `account_type` (**5**) |
| Timestamp match | `details.timestamp` must equal the `ts` attribute, else "advTimestampMismatch" + WAM event `C2TD`, result rejected |
| Age | if `ts` is older than `min(35, AB 730)` days (default 35) and `valid_indexes` has more than 1 entry: "advListTimestampInvalid", rejected |
| Raw id | `raw_id` different from the stored one: "incoming key-index not matching local state, resetting"; own account on a companion logs `device_self_invalid_index_list`; other users: `C15070fj.A0G(user, "adv_key_index_list_validation_failed")` when no new list was parsed (effect not traced) |
| Filtering | `filterDeviceWithKeyIndexList` (`C24230w2.A08`) keeps a device when it is the primary, or its `key-index` is above 0 and listed in `valid_indexes`; otherwise it is dropped with a WAM event (`C55932Sv`, 1 when the index is 0). A larger stored index only produces a warning |

### 5.4 Device sync jobs (found)

`DeviceSyncManager.A03(jids, type)` queues `SyncDevicesJob` (skips users already in flight; pending users survive restarts in pref `pending_users_to_sync_device`). `syncType` selects the sync type:

| `syncType` | Sync type | Context | Called from (found) |
|------------|-----------|---------|---------------------|
| 0 / default | `INTERACTIVE_MULTI_PROTOCOL_QUERY` | interactive | — |
| 1 | `MESSAGE_MULTI_PROTOCOL_QUERY` | message | `SyncDevicesAndSendInvisibleMessageJob` (group send path `C22300su`, group size between AB 934 and AB 1946, one job per message key) |
| 2 | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | notification | account sync of own devices (`C41431mS`) |
| 3 | `BACKGROUND_MULTI_PROTOCOL_QUERY` | background | incoming message or status whose ADV sender check failed (`DecryptMessageRunnable` / `StatusProcessingRunnable`, log `invalid adv sender`), ADV metadata mismatches (`C24230w2`), pending-user replay |
| 4 | `VOIP_MULTI_PROTOCOL_QUERY` | voip | call encryption setup for a non-primary device (`C1A`, log `voip/encryption/schedule usync`) |
| 5, 6 | `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY`, `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` | notification, message | not traced |

Devices-only requests use `C21820s6.A0H`. `handleADVMetadata` (`C24230w2.A0A`) also triggers a type-3 refresh when an incoming message's ADV metadata reports a hosted account type that disagrees with local state (devices cleared first), or a newer timestamp than stored.

---

## 6. LID mapping

| Mechanism | Detail (found) |
|-----------|----------------|
| `lid` protocol | query `<lid/>`; per-user `<lid jid=known LID/>` only when a PN user already has a stored LID; response `<lid val="LID"/>` stored in the user result |
| Mapping write | `N27.A03(users)`: LID = `new_jid` (if a LID-type JID) else the `lid` result else the user `jid` if it is a LID; PN = `pn_jid` else user `jid` if it is a PN; pairs go to the LID-PN mapping store in one batch |
| Business `pn_jid` | a LID user without PN gets the PN from `<business pn_jid>`; the pair is stored |
| Side list | request users carry `jid` = LID and `pn_jid` = PN when LID addressing is on (`C11940aM.A05`, resolved via `C11500Zc.A00`, flag id not traced); fallbacks log `Sidelist: No LID provided`, `waContact_null`, `usernameLid_null` |
| Missing-LID repair | `MissingLidHandler` (`C32M`): `requestSyncDevicesAndLidIfMissingLids` waits 32000 ms for a `MESSAGE_MULTI_PROTOCOL_QUERY` with the lid protocol before an external entry point proceeds |
| Mapping observer | `ContactJidMapObserver` (`C0ZA`): when a LID-PN pair appears and a deprecated contact exists, adds the replacement contact and queues a `BACKGROUND_DELTA` with reason `LID_REQUEST` |

Why missing LID matters: a PN-only contact cannot be addressed under LID-first sending; the query fills the pair without a full sync (inferred from the call sites).

---

## 7. Privacy enrichment (tctoken, common group)

`ProfilePrivacyEnrichmentFetcher` (`C223659jg.A00`, log label `ContactSyncHelper.privacyEnrichment`) runs over the request list before send. For each user it fetches (a) the stored privacy token with its timestamp (`C14820fK.A0M`, dropped when older than `C14820fK.A04.A02()`), (b) when no valid token exists, a group JID shared with the user (`C197178aC.A04` / bulk search, needs own LID). Result `C197148a9{ token C9oI, commonGroup, flag }`.

| Output | Classic usync | MEX `UsyncQuery` |
|--------|---------------|------------------|
| token | `<tctoken>token bytes</tctoken>` child of `<user>` | `privacy_token{tctoken, timestamp}` |
| common group | `common_gid="..."` attribute on `<user>` | `common_group` |

Applies only to requests that ask for picture or status (AB **9667**, default true), text status (**20798**, default false), devices (**29769**), contact (**29770**), lid (**29771**) (flags default false except 9667). Without a token or a common group the server can still answer but may omit picture or status (inferred; server rule unknown). Token issuance and `cstoken` are in WA_TCTOKEN_CSTOKEN.md.

Related: `PRIVACY_TOKEN_REFRESH` (`C735439k`) issues `BACKGROUND_QUERY_PICTURES` with the picture-only set `A0O` in batches of 10 users (found); that the purpose is to refresh the token association is inferred from the reason name.

---

## 8. MEX `UsyncQuery` and protocol routing

### 8.1 Operation (found, `C229259vZ.A01`)

`w:mex` operation `UsyncQuery`, doc_id `38635300486116501` (persist-id asset), response class `C2IQ`. Envelope as in WA_USERNAME.md 2.2.

| Variable | Source |
|----------|--------|
| `query_input[]` | per user: JID, `client_known_username`, `about_status{dhash}`, `picture{id}`, `business{serial, tag}`, `devices{hash, timestamp, expected_timestamp}`, `privacy_token{tctoken, timestamp}`, `common_group` |
| `telemetry.context` | lower-case context string |
| `include_username`, `include_reachability`, `include_linked_profiles`, `include_lid`, `include_about_status`, `include_picture`, `include_biz`, `include_ddm`, `include_devices`, `include_orgs` | booleans set when any user requests the protocol |
| `picture_field_input` | `type` `IMAGE` or `PREVIEW`, `preview_px` for previews |
| `business_input` | `include_profile`, `include_vname`, `profile_version` |

Not carried over MEX: contact and text_status. MEX-only: reachability, linked profiles, orgs, ddm (disappearing mode). Response details beyond username and lid (WA_USERNAME.md) were not read (unknown).

### 8.2 When MEX is used (found, `C18580m0`)

1. AB **37780** (int, default 0) non-zero: per-protocol routing. High 16 bits = bit mask routed over classic usync (`SMAX`), low 16 bits = mask routed over MEX; `DROP` otherwise. Bits (`M5H`): status 4, picture 8, business 16, devices 32, disappearing_mode 128, username 512, text_status 1024, orgs 2048. Request-level bits 1 (contact), 2 (`C70582ym.A07`, probably side list, inferred) and 256 travel as the "identity" mask. A protocol that the chosen route cannot carry is set to `DROP`: text_status on MEX, orgs on SMAX. The log line is `ContactSyncHelper/read_route type=.. contacts=.. identity=..,.. failed=..`.
2. Otherwise with AB **33432** (default false): classic query for the main request, then a "mex profile follow-up" (`..._mex_profile`) for devices, with a metrics marker annotated with `requested_users`, `is_delta_sync`, outcome `success`, `partial_success`, `no_result`, `timeout`, `exception`, `interrupted`.
3. Otherwise `A0F` decides per request: MEX is refused when the request has contact or text_status ("cantUseMex"), needs AB **9732** for business and AB **8421** for username; the rest may go over MEX (`C229259vZ`), with a 128000 ms wait.

Default state of this build: 37780 = 0, 33432 = false, 9732 = false, 8421 = false, so USync runs over the classic stanza unless a server AB override changes it.

---

## 9. Rate limits, errors, backoff

### 9.1 Error shapes (found)

| Where | Shape | Parsed by |
|-------|-------|-----------|
| iq error | `<iq type="error"><error code backoff/></iq>` | `Brt`: `code`, `backoff` seconds * 1000 capped at 3600000 ms (-1 when absent); calls `BIz(type, sid, code, backoffMs)`, completes the future with null |
| delivery failure | transport callback | `Bog`: future fails with `C216419Uc`; per-JID sync state reset (`C502424l.A01`) |
| protocol error | `<result><PROTO><error code text backoff/></PROTO></result>` | `C18670m9.A01`: `backoff` seconds * 1000, default 7200 s, cap 3600000 ms (1 h); logs `connection/unisynciq/parse/<proto>/error` |
| protocol success | `<PROTO refresh="n"/>` | `refresh` seconds * 1000 |
| user-level partial | `<devices><error code text/></devices>` | state -1, user kept |
| MEX error | GraphQL error, path field `<proto>_info`, optional backoff string | `C229259vZ.A00`: backoff default **7200**, cap 3600000, no * 1000 conversion in this path (units unclear, unknown) |
| username key | codes `42901` (requestor) and `42902` (requestee) in the contact result | `C23638AId.A0G`, see WA_USERNAME.md |

Codes seen in client logic: `429` (rate limit: sync result 5), `503` (global backoff), `42901`, `42902`.

### 9.2 Backoff store (found, prefs file `contact_sync_prefs`, `C18800mM`)

| Key | Written when | Value |
|-----|--------------|-------|
| `contact_sync_backoff` | any iq / contact-protocol error with backoff above 0 (`X.0m7.BIz`, `AO4.BIz`) | now + backoff ms |
| `delta_sync_backoff` | same, mode delta and code 429 | now + backoff |
| `global_backoff_time` | same, code 503 | now + backoff |
| `sidelist_sync_backoff` | `ContactQuerySync` callback `AO2.BIz` on **any** error with backoff above 0 | now + backoff; code 503 also sets `global_backoff_time` (the key name does not match the sync scope; found) |
| `contact_full_sync_wait`, `status_full_sync_wait`, `sidelist_full_sync_wait` | `refresh` attribute of the protocol result | ms; unset = 86400000 (24 h) |
| `status_`, `picture_`, `business_`, `devices_`, `disappearing_mode_`, `lid_`, `username_`, `text_status_`, `reachability_` `sync_backoff` | per-protocol result error backoff in `BJ0` | now + backoff |
| `last_contact_full_sync`, `last_status_full_sync`, `last_sidelist_full_sync` | full sync completion | timestamp |

`C18800mM.A02()` resets contact, sidelist, status, picture, business, devices, delta, disappearing_mode, lid, reachability and global keys to -1; `username_sync_backoff` and `text_status_sync_backoff` are not in that list (found).

Readers found by string search: `reachability_sync_backoff` (`C18580m0`), `text_status_sync_backoff` (`C3MA`), the three `*_full_sync_wait` keys and `last_*_full_sync` (periodic job: a full sync is due when `wait - now + last` is at most 1800000 ms, 30 min). No reader of `contact_sync_backoff`, `delta_sync_backoff`, `global_backoff_time` or the other per-protocol keys was found (unknown whether the check builds the key dynamically).

### 9.3 Local limits (found)

In-flight dedupe: one `querySyncJid` per JID, one phone query per number. Timeouts: 32000 ms single lookup, 128000 ms batch, 180 s for the `C18230lP.A00` callback wait (unbounded when `C11980aQ.A09`). Backoff cap 3600000 ms. Privacy-token refresh batches of 10 users. Server-side per-account and per-number query limits are unknown.

---

## 10. What triggers USync

Reason = `EnumC21800s4` value (client label, used for scheduling and metrics). Type = sync type.

| Client feature | Reason | Type | Protocols |
|----------------|--------|------|-----------|
| Registration finished | `REGISTRATION_FULL` (`C25100xS`, `CJ8`) | `REGISTRATION_FULL` (code 0) | contact set (companion variant not traced) |
| Contacts onboarding | `NC_ONBOARDING` | `A0G` delta upload (`CONTACT_UPLOAD`) | contact + lid |
| Device address book changed (primary only) | `DEVICE_ADDRESS_BOOK_CHANGE` | urgent on-change delta (`C18230lP.A02`) | not traced |
| Periodic and forced full sync | `PERIODIC_FORCE_SYNC`, `FORCE_SYNC` | `BACKGROUND_FULL` | contact / side list |
| Contact picker open | `CONTACT_PICKER_FULL_SYNC`, `CONTACT_PICKER_USYNC_RETRY` | `INTERACTIVE_FULL` | not traced |
| Add contact, new chat by number, deep link, contactless chat | `*_CONTACT_ADD` reasons exist; not tied to the query path | `ADD_QUERY` (`C9AA`) / `INTERACTIVE_QUERY` (`C9AQ`, `C9AY`, `AWR`, `A1P`) | see 4.1 |
| Open a chat with an unsaved user or business | `CONVERSATION_SIDE_CONTACT`, `SIDELIST_REQUEST` | phone query (`INTERACTIVE_QUERY`) when AB **20988** (default true), else `INTERACTIVE_DELTA_SIDELIST` | see 4.1 / 4.3 |
| Send message to broadcast list | `LID_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | lid |
| Group message send (size within AB 934..1946) | `DEVICE_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | devices |
| Incoming message with failed ADV sender check, ADV metadata mismatch | `DEVICE_REQUEST` | `BACKGROUND_MULTI_PROTOCOL_QUERY` | devices |
| Call encryption setup | `DEVICE_REQUEST` | `VOIP_MULTI_PROTOCOL_QUERY` | devices |
| Own account sync | `DEVICE_REQUEST` | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | devices |
| Server push: contact, status, picture, business, username change | `NOTIFICATION_*`, `USERNAME_UPDATE_NOTIFICATION` | `NOTIFICATION_CONTACT` / `NOTIFICATION_SIDELIST` | per notification |
| Disappearing-mode and text-status refresh | `DM_FORCE_REFRESH`, `TEXT_STATUS_FORCE_REFRESH` | `BACKGROUND_MULTI_PROTOCOL_QUERY` (text status also `BACKGROUND_FULL`) | disappearing_mode / text_status |
| Account switch | `ACCOUNT_SWITCH_REFRESH` | `BACKGROUND_FULL` | not traced |
| Privacy token refresh | `PRIVACY_TOKEN_REFRESH` | `BACKGROUND_QUERY_PICTURES` | picture |
| LID-PN mapping change | `LID_REQUEST` | `BACKGROUND_DELTA` | all but orgs |
| Business chat (message added, call) | `BUSINESS_CONTACT_CHAT` (`C0LX`, `RunnableC23932ATn`) | `BACKGROUND_MULTI_PROTOCOL_QUERY` / `VOIP_MULTI_PROTOCOL_QUERY` | not traced |

---

## 11. Feature flags

AB-prop ids as read in the call sites; defaults from the config tables of this build. Flag IDs in bold.

| Flag | Type | Default | Controls |
|------|------|---------|----------|
| **5751** | bool | false | request devices in contact and phone-number queries |
| **5839** | bool | false | text_status protocol (request and parse) |
| **9667** | bool | true | privacy enrichment for picture / status requests |
| **20798** | bool | false | privacy enrichment for text_status |
| **29769**, **29770**, **29771** | bool | false | privacy enrichment for devices, contact, lid requests |
| **9732** | bool | false | business over MEX |
| **8421** | bool | false | username over MEX |
| **37780** | int | 0 | protocol routing masks (high 16 SMAX, low 16 MEX) |
| **33432** | bool | false | split classic query + MEX profile follow-up |
| **12402** | bool | false | `lid` and `pin` on the username `contact` |
| **14565** | bool | false | `addressing_mode="lid"` on contact, digits-only PN text |
| **26739** | bool | false | `+` prefix on phone numbers |
| **471** | int | 1140 | business `profile v` (masked with 0x3FFC) |
| **730** | int | 35 | ADV key-index max age in days (capped at 35) |
| **31261** | bool | false | adds the known `@username` per user (`C223639je`) |
| **33609** | bool | true | when true, the key-entry lookup omits `<username/>` |
| **20988** | bool | true | phone query instead of side-list sync on an unsaved business chat |

---

## 12. Baileys (`baron-baileys-v2`, compared with its `src/WAUSync` and `Socket/socket.js`)

| Topic | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| envelope | `iq to=s.whatsapp.net type=get xmlns=usync` + `usync{context, mode, sid, last="true", index="0"}` | same attributes; `to` implied |
| modes | `query` (default), `delta` | also `full`, `download` |
| contexts | `interactive` (default), `background`, `message`; `voip` appears in its backoff rule | plus `registration`, `notification`, `add`, `voip`, `metadata`, `snapshot`, `wamo` |
| protocols | adds `bot`, `feature`, `sidelist` as a query child | no `bot` / `feature` child; sidelist users go in `<side_list>` |
| contact | `<contact>phone</contact>`, username with `pin` / `lid`, `type` | phone with `+`, `type="delete"`, username |
| status hidden | `code="401"` on `<status>` gives `''` | `type="fail"` with 401 / 403 / 404 |
| privacy proof | `<tctoken>` under the status protocol only, when the user carries a token | `<tctoken>` for picture / status / others and `common_gid` |
| backoff | `error backoff` seconds * 1000, unbounded | capped at 1 h |

| Symptom (inferred) | Cause | Fix |
|--------------------|-------|-----|
| picture / status missing for non-contacts | no tctoken, no `common_gid` | attach stored `<tctoken>` or a shared group JID per user |
| device list rejected | key-index `ts` / `raw_id` checks of section 5.3 | verify `ts` equals the signed `details.timestamp` |
| backoff ignored | Baileys uses server value without cap | cap at 1 h, wait per protocol |

---

## 13. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ContactQuerySync/querySyncJid: rate-limit-error` | contact result error 429, empty list | wait the returned `backoff`, reduce query rate |
| `connection/unisynciq/parse/<proto>/error` | per-protocol error node | store `backoff` for that protocol only |
| `handleSyncContactError ... code=503` | server overload | global backoff, retry later |
| `sidelist-jid-absent-from-response` | server omitted a requested side-list user | client marks the user synced to avoid a loop |
| `contactsyncDevicesupdater/update/verifyADVSignedKeyIndexList fail` | signature, proto or timestamp check failed | device row not updated, refresh queued |

---

## 14. Key distinctions

| Do not confuse | Detail |
|----------------|--------|
| sync type vs reason | type (`EnumC21760rz`) picks mode, context, scope; reason (`EnumC21800s4`) is only a label for scheduling and metrics |
| `list` vs `side_list` | address-book users vs users outside the address book (side contacts) |
| usync vs MEX `UsyncQuery` vs MEX contact mutations | three transports for related data; routing flags in 8.2 and 4.5 |
| `<devices>` result vs signed key index | the device list is not trusted until the signed list verifies (5.3) |
| `refresh` vs `backoff` | `refresh` = how long a good result may be reused, `backoff` = how long to stay away after an error |

---

## 15. Complete flow

```
[Feature]         [ContactSyncMethods]            [UniSync builder / MEX]                [Server]
  │ trigger (10)         │                                  │                               │
  ▼                      ▼                                  │                               │
 reason + type ──► SyncRequest (protocol set, users)        │                               │
                         │ enrich: tctoken / common_gid (7) │                               │
                         │ route per protocol (8)           ▼                               │
                         └──► classic: <iq xmlns=usync><usync sid index last mode context> ─►│
                         └──► MEX: w:mex UsyncQuery {query_input, include_*} ───────────────►│
                                                            │◄── <usync><result> per protocol│
                                                            │     <list> <side_list>         │
                                                            ▼                               │
                    parse: contact in/out, status, picture, business,                       │
                           devices + key-index-list, lid val, username                      │
                                  │                                                         │
        ┌─────────────────────────┼─────────────────────────┐                               │
        ▼                         ▼                         ▼                               │
 devices: verify ADV sig,   LID/PN pairs ──► mapping   result errors: 429 / 503 / backoff   │
 ts, raw_id, valid_indexes  store (N27.A03)            ──► prefs; refresh ──► full_sync_wait │
        │ ok                                                                                │
        ▼                                                                                   │
 device rows updated ──► message fan-out, call setup, side-list chats use the new data      │
```

---

## 16. Unknowns

| Topic | Reason |
|-------|--------|
| `to` attribute of the iq | added by the sender; sender not traced |
| Difference of `C10140Tq.A0A` (registration) vs `A06` | not traced |
| Server rules for query rate, per-number limits, which protocols a requester may read | client sees only error codes |
| Readers of `contact_sync_backoff`, `global_backoff_time`, `delta_sync_backoff` | no string reader found |
| MEX backoff units | no `* 1000` in `C229259vZ.A00` |
| Which route wins in production | all route flags default off in this build; server AB values unknown |
| Actual traffic | static analysis only |
