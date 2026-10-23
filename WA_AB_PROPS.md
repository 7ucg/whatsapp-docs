# WhatsApp AB Props — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** AB props / feature flags on Android: numeric flag ids and typed default tables, typed readers and read options, MobileConfig layer (Stable IDs, unit types, `params_map_v4_u*`, `MetaConfigFetchMutation`), props sync IQ (`xmlns="abt"`: hash, refresh, refresh_id, delta, expo keys, sampling weights), group-level props, pre-registration props, on-device (offline) experiments, storage on device, exposure logging, override and debug paths, relation to the flag ids cited in other reports, flag catalog by area, Baileys comparison

---

## 1. What it is (technically)

AB props are the client's server-driven feature flags. Every flag is identified only by a numeric **config code** (e.g. `20548`); no flag name exists in the APK. The client ships a typed default table per code, asks the server for overrides over an IQ, stores the answer in SharedPreferences and reads it through one abstract reader class. A second, Meta-derived layer (MobileConfig) runs next to it and can become the source of truth. All statements come from static analysis of the decompiled APK; nothing was captured on the wire. Tiers: **found** = read in code or data, **inferred** = deduced, **unknown** = not resolved. Obfuscated names are per-build and were re-resolved in 2.26.41.6.

| Layer | 2.26.41.6 name | Role |
|-------|----------------|------|
| Reader base | `C00D` (abstract) | typed accessors, caches, exposure, MobileConfig switch |
| Main store | `C08J` (`extends C00D`, prefs `ab-props`) | holds the five default maps, reads all normal flags |
| Pre-chatd store | `C0D9` (prefs `ab-prechatd-props`) | flags fetched over HTTP before the account is connected |
| Private store | `C0ER` (prefs `ab-private-abprop`) | on-device experiment values, same defaults as `C08J` |
| Read options | `C00F` (`AbPropsOptions`) | exposure mode + first-access pinning |
| Typed descriptors | `C054909t` ABPropBoolean, `C055109v` ABPropInt, `C1OT` ABPropFloat, `C055009u` ABPropString, `C055209w` ABPropJson | id + call-site default |
| Sync manager | `C0D2` (`ABPropsManager`) | storage, hash, refresh, backup, pre-chatd update |
| Request / response | `C27646BzW` (request), `C28894Cgv` (response + error) | `<iq xmlns="abt">` |
| Trigger | `RunnableC48591z1` default branch (log `MessageHandler/maybeGetNewAbProps`), `C1S0` handler of `<... abprops/>` | when a fetch is sent |
| Group props | `C41861nA` (`GroupAbPropsManager`), `C502324k` (trigger), `C28900Ch1` (response) | per-group values |
| MobileConfig | `C053409d` (factory), `C054709r` (`InterfaceC054609q`), `C06510El` (Stable-ID table), `C34081Wt` / `C34091Wu` (typed lambdas), `C06460Eg`, `C053809h` (overrides table), `CQN` + `C29448CqB` (fetcher), `C41251mA` (fetch coordinator) | native-backed engine, MEX fetch |
| Exposure | `C42831om`, `BxP`, `C27952CBv`, WAM event `C44051qo` (5504) | exposure keys |
| Offline AB | `C24976ApB`, `C27629BzE`, `C60839RQl`, `ON0` / `ON1` / `C53973OMy`, `ConfigVariable` | local experiment assignment |
| Observers | `C0NE` (3 callbacks), 46 implementers, e.g. `CY8` | react to changed values |

Decisive points:

- The flag id space is one numeric space (max id **39140**, 21,424 ids with a default). `C05Z.A00(n)`, `C1XG.A0I(n)`, IQ type ints and WAM ids are different number spaces (section 12).
- Names never reach the client. Not in the default tables, not in the sync response (`config_code` only), not in a resource.
- There are three parallel sync paths: the `abt` IQ (user level), the `abt` IQ with `group=` (group level), and the MobileConfig MEX fetch (section 4).

---

## 2. Flag model

### 2.1 Types and default tables (found, `C08J`)

Five immutable maps are built in the `C08J` constructor (`buildKeepingLast`, so duplicate puts in the decompile are harmless). Counts are unique ids per map:

| Type | Map | Accessors on `C00D` | Ids | Example |
|------|-----|---------------------|-----|---------|
| bool | `A1A()` | `A15(id)`, `A18(ABPropBoolean)`, `A0E(...)` | 16,668 (1,237 default `true`) | `9667` true |
| int | `A1C()` | `A0b(id)`, `A0f(ABPropInt)`, `A02(...)` | 3,530 | `996` 604800 |
| float | `A1B()` | `A0Z(id)`, `A0a(ABPropFloat)`, `A00(...)` | 177 | `31535` 0.0 |
| string | `A1E()` | `A0j(id)`, `A0n(ABPropString)`, `A08(...)` | 867 | `34350` regex |
| JSON | `A1D()` | `A0p(id)`, `A0r(ABPropJson)`, `A09(...)` | 182 | `21995` `{}` |

No id sits in two maps. Static literal reads (`A15(n)`, `A0b(n)`, `A0j(n)`, `A0Z(n)`, `A0p(n)`): 16,355 call sites in `p000X` and `com`; descriptor reads come on top (construction sites: 492 ABPropBoolean, 482 of them distinct, 259 ABPropInt, 30 ABPropFloat, 66 ABPropString, 12 ABPropJson).

Default resolution (found, `C00D.A0D`, `A01`):

| Step | Rule |
|------|------|
| 1 | value cached in memory for this process |
| 2 | stored server value in prefs `ab-props` under key `String.valueOf(id)` |
| 3 | default from the map of the id's type |
| 4 | call-site default of an ABPropX descriptor (only when the map has no entry) |
| 5 | none: `IllegalArgumentException("Unknown BooleanField: <id>")` (int: `Unknown IntField`) |

For all 482 distinct ABPropBoolean descriptors the id exists in the map and the descriptor's production default equals the map default. `debugDefaultValue` of ABPropBoolean differs from the production default in 182 of them but is read nowhere except in `equals` / `hashCode` / `toString` (smali: the field `A02` is referenced only inside `09t`; the accessors use only id and production default). It has no runtime effect in this build.

### 2.2 Value parsing on store (found, `C0D2.A00`)

| Map of the id | Stored as | Parse |
|---------------|-----------|-------|
| bool | `putBoolean` | `Integer.parseInt(config_value) != 0` (wire form `"1"` / `"0"`) |
| int | `putInt` | `Integer.parseInt` |
| float | `putFloat` | `Float.parseFloat` |
| string | `putString` | as is |
| JSON | `putString` | validated with `new JSONObject(...)`; failure logs `ABPropsManager/invalid format for config; configCode=...` and the prop is not stored |
| id in no map | `putString` | stored as a string; a typed read of such an id has no default and throws (2.1 step 5) |

Unlike the WA Web table (unknown codes dropped), Android keeps unknown codes as strings (found).

### 2.3 Read options (found, `C00F` = `AbPropsOptions`)

| Constant | exposureOptions | firstAccessValue | Used as |
|----------|-----------------|------------------|---------|
| `A03` | WITH_EXPOSURE_LOGGING (1) | false | default for all plain reads (`A15`, `A0b`, ...) |
| `A02` | WITH_EXPOSURE_LOGGING | true | `A19(...)`, `A16`, MobileConfig bootstrap reads |
| `A06` / `A05` | WITHOUT_EXPOSURE_LOGGING (0) | false / true | `A00()` derives them |
| `A04` | WITH_URGENT_EXPOSURE_LOGGING (2) | false | pre-chatd store when flag **24317** is on |

`firstAccessValue = true` pins the first value read in the process in `C00D.A07` (ConcurrentHashMap); later reads of that id return the pinned value even after a sync (found, `C00D.A0D`, `A0i`). Plain reads use the cache `A0P`, which `A0s()` clears after every sync.

### 2.4 Read path and source of truth (found, `C00D.A07` smali; names of the switches inferred from use)

```
read(id)
  ├─ A14() true  (A0E && A0b && !A0S)  and A08 set  and MobileConfig context present
  │      └─► MobileConfig value via C34081Wt/C34091Wu  (Stable ID lookup, C054709r.B6F)
  └─ else
         ├─ legacy value: cache A0P ► prefs "ab-props" ► default map
         └─ if A0E && A0G (shadow): also read MobileConfig and compare (A0C)
```

| Field | Source | Meaning (inferred) |
|-------|--------|--------------------|
| `A0F` | pref `23048` (bool), `C08J` only | MobileConfig initialised for this account |
| `A0E` | `A0F` or pref `27668` (int) > 0 | MobileConfig active (`C08J` only; false for `C0D9`, `C0ER`) |
| `A0b` | pref `24896` | MobileConfig is source of truth |
| `A0S` | pref `25403`, re-read in `A0s()` | override back to the legacy path |
| `A0G` | pref `22646` | shadow comparison on |
| `A0c` | pref `38895` == 1 | per-read cache `A0d` for MobileConfig values |
| `A08` | AtomicBoolean, set in `C054709r.BN4` (MobileConfig init) | MobileConfig ready; only then is the MobileConfig path taken (found); reset in the constructor to false |

All six are AB props themselves, read straight from the prefs file at construction (found). Shadow mode builds a comparison record `N25` and sends a field-stats event (`C56612Vl`, value `mobile_config_inconsistent_value`) sampled 1 in flag **22647** (default 10) (found). When MobileConfig is the source and an id has no Stable ID, the typed lambda returns `false` / `0` / `""` with value source `INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`, not the default map value (found in `C34081Wt`; effect on the 70 default-only ids inferred).

---

## 3. MobileConfig layer

### 3.1 Stable IDs (found, `C06510El.A0J`)

`long[39141]` indexed by config code, 21,380 non-zero entries. `C054709r.B6F(id)` returns the entry (0 = none). 21,354 ids exist in both the default maps and this table; 70 ids are default-only, 26 Stable-ID-only.

| Bits | Field | Evidence |
|------|-------|----------|
| 0-15 | slot index | `C053809h.A00`: `j & 65535`; meaning inferred |
| 32-47 | config index, `0..20780`, one per entry in id order | `C06460Eg.A00`: `(j >>> 32) & 65535`, `C053409d.A08(int)` |
| 48-53 | value type: 1 bool, 2 int, 3 string or JSON, 4 float | cross-tab against the default maps, no exception |
| 54-59 | unit type: 1 SESSIONLESS (564 ids), 2 SESSIONBASED (20,781), 6 GROUP (35) | cross-tab; section 3.2 |
| 60-63 | value `2` iff the bool default is `true` | 1,231 of 1,231 ids; 6 true-default ids have no Stable ID |

### 3.2 Unit types and `params_map_v4_u*` (found)

`assets/params_map_v4_u<N>.txt` is loaded by `N3E` with `N` = MobileConfig unit type (`AbstractC24817AmY.A00`): 0 NULL_VALUE, 1 SESSIONLESS, 2 SESSIONBASED, 3 PAGEID, 4 ADMINID, 6 GROUP, 7 FAMILY_DEVICE_ID, 8 FRLID, 9 AD_ACCOUNT_ID, 10 WEARABLE_DEVICE_OWNER_ID. The suffix is the unit type, not a value width. The native library carries the same format string `params_map_v4_u%d.txt` (`libmobileconfig-jni.so`).

| File | Unit | Entries | Version key | Ids inside the WA code range |
|------|------|---------|-------------|------------------------------|
| `u1` | SESSIONLESS (usable before login) | 575 | 565 | 564 |
| `u2` | SESSIONBASED | 20,844 | 20785 | 20,781 |
| `u4` | ADMINID | 72 | 2 | 0 (ids 112607..121623) |
| `u6` | GROUP | 35 | 35 | 35 |

Entry (8 bytes, two little-endian u32, header layout as in the file: magic `v4`, `0x7fff` check, version key, count, 32-char hash):

| Field | Finding |
|-------|---------|
| `int2 >> 12` | the WA config code: for `u1`/`u2`/`u6` it matches the Stable-ID table (564 / 20,781 / 35 hits) and the default maps; low 12 bits are 0 for all but a few entries |
| `int1` low 16 bits | value-type mask: `0x881` bool, `0x1001` int, `0x1801` string/JSON, `0x2001` float (`u2`); bit 15 set exactly for bool defaults `true` (25 + 1,206 = 1,231) |
| `int1 >> 16` | running slot number (inferred) |
| `u4` ids | outside the WA code range; purpose unknown |

The low 9 bits of `int1` are 1 or 129 only; they are not a parameter id.

The 35 GROUP ids (found): 18205, 23245, 23246, 23397, 23398, 24075, 26013, 26269, 26270, 26862, 27009, 27025, 27247, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 33673, 34075, 34277, 34333, 35211, 35227, 35639, 35772, 36156, 36504, 36505, 37523, 37524, 38082, 38083. Flag **18205** is read per group by `GroupAbPropsManager` (section 4.7).

### 3.3 MobileConfig fetch over MEX (found, `CQN`, `C29448CqB`)

MEX mutation `MetaConfigFetchMutation`, schema `whatsapp-android-www`, doc_id **28207206725568030**, root field `xwa2_mobile_config_fetch`. Input fields set in `CQN`: `api_version`, `fetch_type`, `unit_type`, `unit_id`, `device_id`, `query_hash`, `query_string`, `bln_queries`, `mc_debug_id`, `mobile_app_universe_type`; always null in the paths read: `batch_size`, `bln_li_hashes`, `bool_opt_policy`, `contact_point`. Log: `WAMobileConfigFetcher/fetchWwwConfigs/request unit_type=...`. Response: a config blob handed to the native manager (`onComplete(true, blob)`), plus `ep_refresh_id` and `ab_key`. `ab_key` is stored as `mc_expo:sys:ab_key`.

`C41251mA` (`MobileConfigFetchCoordinatorImpl`) decides when this fetch runs after an AB-props fetch: ABPropInt **36185** (default 0) selects the option: value 2 waits for offline resume (`waiting for offline resume`), every other value fetches now; value 1 checks a stored per-unit fetch version against the `abprops` version (`C054709r.A01`), a delta request compares the app version of the latest handle with `2.26.41.6`. `C054709r.CpO` calls `updateConfigs`, callback log `WAMobileConfigFetcher/updateConfigs() callback: succeeded=`; success stores `last_full_fetch_ms:<unit>:<key>`.

The `<success>` stanza of the login also carries `mc_ep_version` (emergency-push version of MobileConfig) next to `props` and `abprops` (found, `HandlerThreadC12340b0`); consumer not traced.

---

## 4. Props sync

### 4.1 Request (found, `C27646BzW.A00(boolean force, boolean delta, int refreshId)`)

```xml
<iq to="s.whatsapp.net" type="get" id="..." xmlns="abt">
  <props protocol="1" hash="<stored config_hash | empty>" [refresh_id="<last_version>"]/>
</iq>
```

| Attribute | Rule |
|-----------|------|
| `protocol` | constant `1` |
| `hash` | stored `ab_props:sys:config_hash`; empty string when `force` or `delta` is set, or nothing is stored |
| `refresh_id` | only when `delta` is set and `refreshId > 0`; value = stored `ab_props:sys:last_version` |
| send | `MessageClient.A0W(callback, node, id, 220, 32000L)`: IQ request-type int 220, timeout 32,000 ms |

### 4.2 Response (found, `C28894Cgv.CFS`)

```xml
<iq type="result"><props ab_key="..." hash="..." refresh="86400" refresh_id="N" [delta_update="true"]>
  <prop config_code="20548" config_value="1" config_expo_key="..."/>     <!-- one per changed flag -->
  <prop event_code="1094" sampling_weight="N"/>                         <!-- event sampling, no config_code -->
</props><erid>...</erid></iq>
```

| Item | Handling |
|------|----------|
| `config_code` + `config_value` | typed store per 2.2, keyed `String.valueOf(code)` |
| `config_expo_key` | stored as `<code>_expo_key` when non-empty and the value was stored (exposure key of the experiment / group the account sits in; format of the key unknown) |
| `ab_key` | stored `ab_props:sys:config_key`; set as WAM attribute **4473** (both channels) when MobileConfig is not the source |
| `hash` | content hash of the whole set; stored `ab_props:sys:config_hash`; a response without hash and without `delta_update` changes no values |
| `refresh` | seconds, default 86400; stored x 1000 ms in `ab_props:sys:refresh`, floor 600,000 ms; not updated by a delta |
| `refresh_id` | version of the set; stored `ab_props:sys:last_version` (also after a delta) |
| `delta_update="true"` | merge into the existing prefs; hash, key, refresh and `last_refresh_time` are left alone |
| hash present | previous prefs copied to `ab-props-backup` (cleared first) |
| full update (hash present, not delta) | store cleared (keeping `refresh` and `last_exposure_keys`), all props written |
| `event_code` + `sampling_weight` | rows without `config_code`; rewritten into prefs `field-stats-events-sampling` (key = event code, value = weight); code **1094** also sets `app_launch_event_sampling_weight` |
| `<erid>` | encrypted rid: with flag **3664** on it is cleared, with **6084** on and a changed value it is stored as `encrypted_rid` |

After a successful full update: `last_refresh_time` = now (ms), `fetch_app_version` = `2.26.41.6`, error counters reset, observers notified (4.8).

### 4.3 Triggers (found unless marked)

| Trigger | Condition |
|---------|-----------|
| login `<success abprops="N">` (also `props`, `mc_ep_version`) | version `N` > stored `last_version`: request with `force` + `delta` + `refresh_id`; mode DELTA (log `versionMismatch`) |
| same path | `last_refresh_time + refresh < now`, or `now < last_refresh_time` (clock moved back; branch read in smali, the decompile omits the else): normal request with stored hash; mode FULL (log `AB Props too old`) |
| incoming `<... abprops/>` child (routed with the `log` and `push-config` children; parent `ib` inferred) | `forceFetchABPropsAndMobileConfig`: `A00(true, false, 0)` (empty hash, full) when message sending is ready; then MobileConfig `BMu` + `CpO` |
| registration | pre-chatd fetch (4.6); offline assignment (6) |

### 4.4 Refresh interval and errors (found)

| Item | Value |
|------|-------|
| default interval | `ab_props:sys:refresh` default 86,400,000 ms |
| server `refresh` | seconds, x 1000, floor 600,000 ms |
| error codes counted | 207, 304, 400-503 (`C28894Cgv.Brt`); other codes only log `unknown error code` |
| retry accounting | `fetch_attemp_count` +1 per error; at 3 `last_refresh_time` = now and the counter resets, so the next try waits one interval |
| last error | `ab_props:sys:last_error_code`, cleared on success |
| delivery failure (`Bog`) | no-op |

### 4.5 Reads during the fetch window

`<props>` can arrive after the first screens read flags. The first read of an id before data exists uses the default; with `firstAccessValue` pinning (2.3) the pinned default stays for the process (found); registration screens wait with a timeout for online props (log strings `RegisterPhoneViewModel/cancelOnlineAbPropsTimeout`, `OnlineAbpropsAsyncStatus`, found; exact wait unknown).

### 4.6 Pre-chatd props (found, `C44707Jfc`, `C43414Iwr`, `K49`, `C0D2.A08`)

Before the account is connected the registration HTTP client calls `checkPreChatdABProps` (`reg-onboard-abprop-request`) with `ab_hash` (pref `pref_pre_chatd_ab_hash`). The result carries a new hash, an `expConfigs` JSON array of `{config_code, config_value, config_expo_key}`, an `ab_key` and a next-fetch delay (`pref_pre_chatd_ab_next_fetch_time` = now + delay). `C0D2.A08` clears the pre-chatd store (`A04`) and rewrites it with the same typing rules (2.2) into prefs `ab-prechatd-props`. Exposure is kept in `pref_expo_keys` (JSON array of `<expo_key>,<timestamp>`) and sent through the registration funnel log (`abprop_exposure` / `ab_prechatd_exposure`, with `ab_key` from `pref_pre_chatd_ab_key`), not through WAM 5504. Pre-chatd reads use options `A04` (urgent) when flag **24317** is on, else `A03`.

### 4.7 Group-level props (found, `C41861nA`, `C502324k`, `C28900Ch1`)

```xml
<iq to="s.whatsapp.net" type="get" xmlns="abt"><props group="<group jid>" hash="<cached | empty>"/></iq>
```

Same type 220 and 32,000 ms as 4.1. The request attribute array has two entries: `group` and `hash` (smali). Gate: flag **16206** (master) and a group conversation being opened (`COK` / `Bnc`); skipped with `reason=cacheValid` until `_nextRefreshTimeInSeconds`, or `reason=disabled`. Response: `hash`, `refresh` clamped to 600..604,800 s (default 86,400), `refresh_id`, `<prop config_code config_value config_expo_key>`, typed by the same default maps (bool, int, float, otherwise string). The ids are in the shared id space; the GROUP unit type (3.2) marks the 35 ids meant for it, and the flag read for a group is `A04(groupJid, id)`. Reads return `null` when the group has no stored value (caller then falls back, not traced). Keys in the group prefs (`groupAbProps`, name inferred from `C00E`): `<jid>_<id>_value`, `<jid>_<id>_exposureKey`, `<jid>_exposureKeysSet`, `<jid>_nextRefreshTimeInSeconds`, `<jid>_lastRefreshHash`. No JSON type for group values.

### 4.8 Observers (found)

`C0NE` has three callbacks: `BhX` before the new values are written (event 34), `Bfk` and `C2K` after (events 33, 32). Example `CY8` (`PQKeysUploadABPropsObserver`): remembers flag **21198** in `BhX`; if it went `true` to `false` in `Bfk`, it logs `PQ_KEYS_UPLOAD_CODE changed from true to false, deleting all kyber prekeys` and queues `DeleteKyberPreKeysJob`. 46 classes implement `C0NE` (grep count).

---

## 5. Storage on device

| Prefs file / key | Content |
|-----------------|---------|
| `ab-props` (`C08J`, `C0D2.A00`) | `<id>` value, `<id>_expo_key`, and the `ab_props:sys:*` keys below |
| `ab_props:sys:config_hash`, `config_key`, `last_version`, `refresh`, `last_refresh_time`, `fetch_app_version`, `fetch_attemp_count`, `last_error_code` | sync state |
| `ab_props:sys:last_exposure_keys` (string set), `last_daily_expo_key_update` | exposure state |
| `ab_props:sys:private_experimentation_id` | random id for on-device experiments (6) |
| `ab_offline_props:offline_exposure_strings`, `ab_offline_props:offline_exposure_hash_strings` | offline-experiment exposure (in `ab-props`) |
| `ab-props-backup` | copy of the previous store, rewritten on every full update |
| `ab-prechatd-props` | pre-chatd values plus `pref_expo_keys` |
| `ab-private-abprop` | `last_read_time_ms` (updated at most hourly) and private values |
| `mc_expo:sys:ab_key`, `mc_expo:sys:last_exposure_keys`, `mc_expo:sys:last_exposure_keys_without_logging` | MobileConfig-side exposure state |
| `field-stats-events-sampling` | event code to sampling weight |
| `groupAbProps` | group values (4.7) |
| `<dataDir>/mobileconfig/mc_overrides.json`, `id_name_mapping.json` | MobileConfig override table, id-name map (file names found in `C053409d`; absent from the APK) |
| `pref_pre_chatd_ab_hash`, `pref_pre_chatd_ab_key`, `pref_pre_chatd_ab_next_fetch_time`, `pref_is_blocking_prechatd_exposure` | pre-chatd state (registration prefs) |

All files are opened through `C00S.A05(name)` (a `SharedPreferences` handle in the app-private data directory); whether that factory adds encryption or obfuscation was not checked (unknown).

---

## 6. Exposure, experiments, groups

### 6.1 Exposure logging (found)

| Step | Detail |
|------|--------|
| 1 | a read with exposure logging (2.3) calls `A0B(options, this, "<id>_expo_key")` -> `A12` |
| 2 | non-empty expo key not yet in `last_exposure_keys`: added and persisted |
| 3 | main store: `C42831om.A01` posts WAM event **5504** `WamWefrClientExposure` (`wam_wefr_client_exposure`), debounced to at least 1 s; `BxP` calls the WAM runtime (`C0D6.CYl(value, 5029, ...)`; "attribute" inferred from the call shape) with the comma-joined keys (per-source merge when flag **31830** is on) |
| 4 | after a full sync only keys the new response still carries stay in the set |
| 5 | daily resend: on foreground callback `A0A0.BvR`, when more than 24 h passed since `last_daily_expo_key_update` (`sent_with_daily` = true) |
| 6 | pre-chatd: `C27952CBv` pulse thread sends the funnel log (4.6); URGENT mode triggers it immediately |

WAM 5504 fields (Falco names): `dedup_key`, `device_exp_id`, `exposure_key`, `from_metaconfig`, `sent_with_daily`. `device_exp_id` is a string derived from the device identity object (`C09E.A0J().A03()`); derivation not traced (unknown).

### 6.2 Experiment and group ids

| Id | Where | Meaning |
|----|-------|---------|
| `config_expo_key` | per `<prop>` | exposure key of the experiment arm; opaque to the client, only compared and logged |
| `ab_key` | `<props>` attribute | key of the whole assigned set; WAM attribute 4473 |
| `refresh_id` | `<props>` attribute | version of the set; compared with `abprops` of the login `<success>` |
| `hash` | `<props>` attribute | content hash used for "no change" |
| `private_experimentation_id` | local | random id used as unit for on-device experiments |
| `device_id`, `unit_id` | MEX fetch | MobileConfig unit identity |

Server-side targeting (country, cohort, percentage) is not visible; the client only sees the resulting values (unknown).

### 6.3 Sampling weights (found)

The `<prop event_code sampling_weight>` rows feed the field-stats logger: per event a 1-in-N sampling weight. Event **1094** (app launch) is mirrored to `app_launch_event_sampling_weight`. The key is a WAM event code, not a flag id.

---

## 7. Local evaluation, overrides, debug paths

### 7.1 Offline AB (found, `C24976ApB`, `C27629BzE`, `C60839RQl`)

Experiments compiled into the APK (`C60839RQl.A00`, list of `ON0` -> `ON1` -> `C53973OMy` -> `ConfigVariable{id, name, value, type}`) are evaluated against a local user-info map and written into the `ab-props` store with the same typing rules. Conditions (`RM2` tree) may only use the properties `platform`, `app_version`, `app_build`, `release_channel`, `os_version` (`C0ER.A0B`). User-info keys: `device_id`, `app_build`, `release_channel`, `app_version`, `os_version`, `platform`, `country` (SIM country), `private_experimentation_id`. In this beta `app_build` and `release_channel` are the constant `beta`. On assignment the sync keys (`config_hash`, `last_refresh_time`, `fetch_app_version`, `last_version`) are removed so the next online fetch is full, and a critical log `abprops-offline-assigned-after-registration-verified` fires when assignment happens with `registration_state == 3`. Experiment definitions are not enumerated here (unknown).

### 7.2 MobileConfig overrides (found, inferred effect)

`C053809h` loads `mc_overrides.json` (`hasOverridesFile`, `boolOverrideForParam`, `intOverrideForParam`, `stringOverrideForParam`, `doubleOverrideForParam`, keyed by the packed 64-bit Stable ID), `C053409d.getOrCreateOverridesTable` returns it to the engine. Overrides apply to the MobileConfig path only, not to the legacy prefs path. Whether the engine consults the table in a release build is unknown; no evidence of a runtime test.

### 7.3 `override-abprops` deep link (found)

Manifest host `whatsapp-consumer://override-abprops` (exported `DeepLinkActivity` alias). `IJB` maps it to destination id 154. `DeepLinkActivity.A0w` parses the path segment `bugbash` and query parameters `feature_name`, `feature_id`, `category`, `min_app_version`, `ready_to_test_time`, and `variants` (base64 JSON array of `{label, abprops:[{abprop_key, abprop_value}]}`) into `BugBashSession` / `BugBashVariant`. An error reason `abprop_override_not_allowed` exists. No code that writes `abprop_key` / `abprop_value` into any prop store was found: `BugBashVariant` is referenced only by the parser and its serializer, and `bugbash_session` is only read (`C51723Mxj`). Gate condition and apply path are unknown.

### 7.4 Other

| Path | Detail |
|------|--------|
| ABPropBoolean `debugDefaultValue` | declared (182 differ), never read (2.1) |
| Debug UI | `com.whatsapp.backup.debugscreen.BackupAbPropsUiState` (class name only, backup debug screen) |
| Per-read profiler | prefs `31165` (int) and `32010` (bool) feed `C00D.A0H/A0I/A0J` and a counter class (`Pr8`); purpose not resolved |

---

## 8. Flag ids cited in other reports (verified in 2.26.41.6)

Every id was looked up in the default maps and the Stable-ID table. Types are the map types.

| Report | Result |
|--------|--------|
| `WA_BAN_SYSTEM_DEEP_EN.md` | 11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 present, bool default false; 12840 and 20278 are **JSON** maps (defaults match); 31535 / 31536 are **float**, default 0.0. **34166 is not a flag**: no default, no Stable ID; `ContactInfoActivity.A0K = C1XG.A0I(34166)` is an injection id (neighbours 34165, 34168, 34169 are the same kind). 2923 absent (as reported) |
| `WA_TCTOKEN_CSTOKEN.md` | all 16 ids present; defaults: 996 / 865 / 26897 = 604800, 997 / 909 = 4, 3802 / 22012 = 26, 4063 = 0, 20606 = 2000, all bool ids false. `299` is the IQ request-type int of the privacy-token IQ, not a flag |
| `WA_META_AI.md` | 25119, 26189, 27083, 37227, 37852, 37054 bool false; **26190 is JSON**, default `""` |
| `WA_USERNAME.md` | all 18 present with the documented defaults; **34350 is a string map entry** (regex), **21995 a JSON map entry** |
| `WA_USYNC.md` | all 21 flag ids present with the documented defaults (730 = 35, 471 = 1140, 9667 / 33609 / 20988 = true) |

The same code space appears on WA Web: for 11 prop names known from the public WA Web prop table, the Android entry has the same code, type and default (e.g. 22797 JSON `{}`, 32276 string `info_card, list_card`, 26270 int 1209600, 35639 int -1, 12539 bool true, 25071 / 1133 / 23245 / 28357 / 27009 / 6939 bool false) (found for the Android side, inferred for "same prop"). Web-only ids (3042, 30590, 24037, 25322) have no Android default. 12 of the 16 Web group-level ids are the Android GROUP unit ids (3.2).

---

## 9. Naming and categories

| Topic | Finding |
|-------|---------|
| Names | no readable name table found in dex or assets (a search for two known legacy flag names matched only log strings); `id_name_mapping.json` is only a runtime file name in `C053409d` |
| Names in logs | a few log strings reuse names: `PQ_KEYS_UPLOAD_CODE` (21198), `abprop_override_not_allowed`; names from older builds or from WA Web are the only route to semantics |
| Categories | no category field. Structure comes from the unit type (SESSIONLESS 564, SESSIONBASED 20,781, GROUP 35) and the value type |
| Most read | the most read literal ids: **20548** (bool true, 511 sites), **9970** (false, 312), **1107** (false, 151), **12267** (true, 147), **1600** (string `{"allowed_product_type":"none"}`, 146), **27008** (false, 104), **13989** (int 7, 87). Semantics unresolved |

---

## 10. Flag catalog by area (defaults found in `C08J`; use read from the other reports and re-checked here)

### 10.1 Sync and MobileConfig infrastructure

| Flag | Type | Default | Controls |
|------|------|---------|----------|
| **23048** | bool | false | MobileConfig initialised (`A0F`) |
| **27668** | int | 0 | `AbstractC06100Cm.A0E`; > 0 activates MobileConfig (`A0E`) |
| **24896** | bool | false | MobileConfig is source of truth (inferred) |
| **25403** | bool | false | back to legacy source (inferred) |
| **22646** | bool | false | shadow comparison |
| **22647** | int | 10 | shadow-log sampling |
| **38895** | int | 0 | `== 1`: per-read MobileConfig cache |
| **26524**, **28443**, **30441**, **30556** | bool | false | MobileConfig factory options (`CbW`, `BMu`) |
| **26525** | int | 600 | MobileConfig factory option (`CbW`), unit unresolved |
| **26640** | bool | false | MobileConfig init parameter (`BN4`) |
| **35778** / **36185** | int | 0 | init phase / fetch-timing option (`C054709r.APn`, `C41251mA.A00`) |
| **24317** | bool (SESSIONLESS) | false | pre-chatd reads use urgent exposure |
| **31830** | bool | false | per-source merge of exposure attribute 5029 |
| **16206** | bool | false | master gate of group props |
| **18205** | bool (GROUP) | false | per-group read in `GroupAbPropsManager` |
| **3664** / **6084** | bool | false | clear / set `encrypted_rid` |
| **21198** | bool | false | `PQ_KEYS_UPLOAD`: Kyber prekey upload; `true` to `false` deletes them |

### 10.2 Ban and integrity (`WA_BAN_SYSTEM_DEEP_EN.md`)

11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 (bool false); 12840 (JSON `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}`); 20278 (JSON `{"max_messages": 10000, "farthest_time_days": 30}`); 31535 / 31536 (float 0.0).

### 10.3 Privacy token and cstoken (`WA_TCTOKEN_CSTOKEN.md`)

| Flag | Type | Default |
|------|------|---------|
| **996** / **997** | int | 604800 / 4 |
| **865** / **909** | int | 604800 / 4 |
| **4063** | int | 0 |
| **3802** / **22012** | int | 26 / 26 |
| **20605** / **14303** / **15491** | bool | false |
| **20606** | int | 2000 |
| **24915** / **24941** / **18639** / **25253** | bool | false |
| **26897** | int | 604800 |

### 10.4 Meta AI, username, USync

| Report | Flags (default) |
|--------|-----------------|
| `WA_META_AI.md` | **26189**, **27083**, **25119** (no reader), **37227**, **37852**, **37054**: bool false; **26190** JSON `""` |
| `WA_USERNAME.md` | **4745**, **20189**, **23817**, **21199**, **16033**, **8421**, **12402**, **28678**: bool false; **21995** JSON `{}`; **20494** 3, **20459** 35, **34347** 4, **34348** 6, **28127** 30, **29327** 60; **34350** string `^([0-9]{4}\|[A-Z0-9]{6})$` |
| `WA_USYNC.md` | **5751**, **5839**, **20798**, **29769**-**29771**, **9732**, **33432**, **14565**, **26739**, **31261**: bool false; **9667**, **33609**, **20988**: true; **730** 35, **471** 1140, **37780** 0 |

### 10.5 Group level (unit GROUP, 35 ids)

Bool false: 18205, 23245, 23246, 26013, 26269, 26862, 27009, 27025, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 34075, 35211, 35772, 36156, 36504, 36505, 38082, 38083. Int: 26270 (1209600 s = 14 days), 27247 (0), 23397 / 23398 / 24075 / 34277 / 34333 / 35227 / 35639 / 37523 / 37524 (-1). String: 33673 (`none`). Names for 26270, 23245, 23246, 26269, 30905, 30906, 28357, 28358, 27009, 27025, 35639, 35772 come from WA Web (group history and poll settings; inferred).

---

## 11. Baileys (`baron-baileys-v2`, `src/Socket/chats.js`)

| Topic | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| user request | `fetchABProps(protocol='1', hash, refreshId)`: `<props protocol hash? refresh_id?>` in `xmlns="abt"` | same shape; `hash` always present (empty when forced), `refresh_id` only with delta |
| group request | `{ group }` only | `group` + `hash` (smali array of 2) |
| response keys | `reduceBinaryNodeToDictionary(props, 'prop')`: dictionary `config_code` -> `config_value` | typed store; `config_expo_key`, `event_code` rows, `hash`, `refresh`, `refresh_id`, `delta_update` all used |
| lookup | by flag name (`abProps['stella_interop_enabled']`) | by numeric code only |
| legacy props | `fetchProps`: `xmlns="w"` `<props protocol="2" hash>` named props | no builder found; names appear only in the stanza token dictionary (`AbstractC40911lb`) |
| refresh | none (once per connection) | interval + version check + push |

| Symptom | Cause | Fix |
|---------|-------|-----|
| `abProps['<name>']` is `undefined` | the `abt` response carries only `config_code` | key by code; the code space is the one in section 8 |
| a key `undefined` appears in the dictionary | `event_code` / `sampling_weight` rows have no `config_code` | skip rows without `config_code` |
| stale values | no hash / refresh / `refresh_id` handling, no delta | store `hash`, `refresh`, `refresh_id`; send `hash` and `refresh_id` on the next request |
| bool read as truthy string | `config_value` is `"1"` / `"0"` | parse per type (`!= 0`) |

---

## 12. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ABPropsManager/onABPropError; unknown error code: N` | error outside 207 / 304 / 400-503 | none; counter not advanced |
| 3 failed fetches, no retry for a day | `fetch_attemp_count` reached 3, `last_refresh_time` = now | wait one interval or a login `abprops` version bump |
| `AbPropProtocolHelper/onReceiveABProps failed to parse response` (`C49828Lvo`) | malformed `<props>` | exception rethrown, store untouched |
| `ABPropsManager/invalid format for config; configCode=N; value=V` | non-numeric int/float or invalid JSON | that prop is skipped |
| `IllegalArgumentException: Unknown BooleanField: N` | typed read of an id with no map default and no descriptor default | add default; `N` is a config code |
| MobileConfig read returns `false` / `0` / `""` | id has no Stable ID (`INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`) | read through the legacy path |
| `WAMCEvaluation/invalid json format; key=N` | JSON flag value not parseable on the MobileConfig path | empty `JSONObject` returned |
| `GroupAbPropsClient/malformedResponse ... noPropsChild` / `parseFailed` | group response without `<props>` or bad parse | no group value stored |
| `GroupAbProps/fetchSkip reason=cacheValid` / `disabled` | before `_nextRefreshTimeInSeconds` / flag 16206 off | none |
| `ABPreChatdProps/exception ... error add expo key` | corrupt `pref_expo_keys` JSON | key not added |

---

## 13. Key distinctions

| Do not confuse | Detail |
|----------------|--------|
| config code vs injection id | `A15(20548)` is a flag; `C05Z.A00(66)`, `C1XG.A0I(34166)`, `C00C.A02(61)` are dependency ids |
| config code vs IQ request type | `A0W(..., 220, 32000L)` (220 here, 299 in the privacy-token IQ) is a request-type int |
| config code vs WAM ids | 5504 is an event, 5029 and 4473 are WAM attributes, 1094 is an event code in the sampling rows |
| config code vs Stable ID | the code (<= 39140) indexes the table; the Stable ID is a 64-bit MobileConfig specifier |
| `abt` IQ vs `w` props vs DB `props` table | `abt` = numeric AB props; legacy `w` props = named server props; the SQL table `props` = local key-value store |
| user props vs group props | same id space, same maps; group values live in `groupAbProps`, keyed by group jid, unit GROUP |
| `ab_key` vs `config_expo_key` vs `hash` vs `refresh_id` | set key / per-prop experiment key / content hash / version |
| login `abprops` vs `<props refresh_id>` | server's current version vs the version stored from the last answer |
| MEX `MetaConfigFetchMutation` vs `abt` | MobileConfig blob vs legacy numeric props; both run when MobileConfig is active |
| production default vs debug default | only the production default is read |
| first-access pinning vs normal cache | pinned values survive syncs until process end |
| offline assignment vs online | offline experiments write the same store, then force a full online fetch |

---

## 14. Complete flow

```
[Server]            [Login]                 [C0D2 / C27646BzW]               [C08J reads]         [WAM]
   │ <success abprops=N props mc_ep_version>   │                                   │                 │
   ├──────────────────►│ N > last_version? or  │                                   │                 │
   │                   │ last_refresh+refresh<now                                  │                 │
   │                   ├──────────────────────►│ <iq xmlns=abt>                    │                 │
   │◄───────────────────────────────────────── │  <props protocol=1 hash [refresh_id]>             │
   │ <props ab_key hash refresh refresh_id [delta_update]>                          │                 │
   │   <prop config_code config_value config_expo_key/> ... <prop event_code sampling_weight/>      │
   ├──────────────────────────────────────────►│ typed store per id (bool/int/float/string/JSON)   │
   │                                           │ backup, hash, refresh, last_version, ab_key       │
   │                                           ├─ observers BhX ► write ► Bfk / C2K ──────────────►│
   │                                           │ A0s(): clear read cache                           │
   │                                           │                                   │                 │
   │ <ib><abprops/>  (force, empty hash) ─────►│                                   │                 │
   │                                           │                                   │                 │
   │                                      A15(id) / A0b(id) / A0j(id)...           │                 │
   │                                           │          cache ► prefs ► default map ► (descriptor)│
   │                                           │          MobileConfig path if A0E && A0b && !A0S   │
   │                                           │                                   ├ first read ────►│ 5504 exposure
   │                                           │                                   │ + 24 h resend   │ 5029, 4473
   │                                           │                                   │                 │
   │ MEX MetaConfigFetchMutation ◄─────────────┼── C41251mA (option 36185) ────────┤                 │
   │ xwa2_mobile_config_fetch {blob, ep_refresh_id, ab_key} ───► native MobileConfig, Stable IDs    │
   │                                           │                                   │                 │
   │ <iq xmlns=abt><props group hash> (group opened, flag 16206) ► groupAbProps ► A04(groupJid,id)   │
```

---

## 15. Unknowns

| Topic | Reason |
|-------|--------|
| Flag semantics | no names; semantics only where a call site or another report resolves them |
| Server-side assignment | targeting, rollout percentages, experiment definitions are not in the client |
| Parent stanza of the `abprops` push child | handler registered under message code 235; `ib` inferred |
| Link between login `abprops` and the version argument of the trigger | trigger takes an `Integer`; the login parse sets an `AtomicReference`; connection inferred |
| MobileConfig `mc_overrides.json` in release builds | table code exists; no evidence it is consulted or writable by the app user |
| `override-abprops` gate and apply path | `abprop_override_not_allowed` reason exists; no writer into a prop store found |
| `device_exp_id` derivation, `config_expo_key` format | not traced |
| Stable-ID bits 0-15, `u4` unit entries, `int1 >> 16` | meaning not resolved |
| Prefs `31165`, `32010`, flag `35778`, `36185` values 1 / 2 | partly read (`Pr8`, coordinator) |
| Behaviour of the 70 default-only ids under MobileConfig | typed lambda returns zero values (found); effect on features not traced |
| Delta semantics server-side | which props a delta carries |
| Actual traffic and live served values | static analysis only |
