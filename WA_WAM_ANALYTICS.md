# WhatsApp WAM Analytics — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** Android WAM ("WhatsApp Metrics") telemetry — event model (event ids, fields, channels REGULAR / REALTIME / PRIVATE / channel 3), Java logging pipeline, sampling and per-event weights, native runtime (`libwhatsapp.so`), common attributes, on-disk buffers, WAM wire format, regular upload (`w:stats` IQ), private upload (credential IQ + separate transport), `wam_daily` and the daily cron, private-stats ids and rotation, privacy handling, feature flags, notable event families, Baileys comparison, what stays unknown

---

## 1. What WAM is in this build

WAM is a client-side metrics pipeline: typed events are created in Java (or converted from native call stats), sampled, handed to a native runtime that serialises them into binary buffers stored under `files/wam/`, and uploaded to the server. It is outbound telemetry only. Nothing in the chat protocol depends on it. All statements are static analysis of the decompiled APK (`versionCode 264100600`) plus the native strings of `libwhatsapp.so` and the layout of buffer files found in an app data directory of this build. Tiers: **found** = read in code or in a buffer file, **inferred** = deduced, **unknown** = not resolvable statically. Obfuscated names are per build and were re-resolved from stable strings in 2.26.41.6 (log strings, `wam_*` event names, IQ attribute values).

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| Event base class | `C0Fc` | `code`, `samplingRate`, `bufferChannel`, `psId`; abstract `getFieldsMap()` (numeric ids), `getFieldsMapForFalco()` (names), `getEventNameForFalco()`, `validate()` |
| Sampling tuple | `C036300x` | weight tiers; `A00` is the weight used by the sampler |
| Sampling resolver | `C0Fg` + `C06580Fh` | per-event weight override from prefs `field-stats-events-sampling` |
| Logger (WAM runtime facade) | `C06650Fo` (`InterfaceC06640Fn`); `C40098Hdb` fans out to it and to the Java Falco logger `C40099Hdc` | `CNW` post, `CNI` post with sampling, `CXW` flush, `CUj` reset, `CXZ` flush and wait (2500 ms); init in `RunnableC29323CoA` case 33 |
| JNI bridge | `com.whatsapp.wamsys.JniBridge` | `jvidispatch*` Java to native, `jnidispatch*` native to Java |
| Common attributes | `C06590Fi` (`CYl(value, attrId, channel)`), init in `RunnableC29340CoR` case 0 | per-channel global attributes |
| AB-props handler | `C28894Cgv` | parses `<props>` incl. `event_code` / `sampling_weight` |
| Daily event | `C0Fp` (`wam_daily`, id 1158) | device and app state |
| Daily cron | `C28643Ccj` (`WamDailyEventDailyCron`), alarm in `BEL` (`DailyCronAction`) | builds and posts `C0Fp` |
| Call event | `com.whatsapp.fieldstats.events.WamCall` (id 462) | created from native call stats, posted by `C24895Anr` |
| Native runtime | `libwhatsapp.so` (`WAMRuntime`, `WAMBufferStore`, `WAMTransportRegular`, `WAMTransportPrivate`, `WAMPSIDProfile`) | buffers, ids, uploads |

Not WAM, do not confuse (see 17): the Java-side Falco shadow logger (`C40099Hdc`, `FFLogger`), the crash and log uploader tagged `wam-event/<name>`, ACS tokens for other projects, and the `fieldstats` word used by native call stats (`prepare_wa_call_fieldstats`).

Client integrity signals that travel inside WAM (`is_rooted`, `is_genymotion`, `is_whatsapp_plus_user`, attributes 6251 and 10255) are described in [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) and only referenced here.

---

## 2. Event model

### 2.1 Event class (`C0Fc`)

Every event is a generated class; the constructor is `super(code, samplingTuple, bufferChannel, psId)`, e.g. `wam_daily`: `super(1158, new C036300x(1, 1, 1, false), 0, -1)`, `getEventNameForFalco() = "wam_daily"`, `internalFalcoMigrationBatchNumber() = 12`.

| Member | Meaning | Tier |
|--------|---------|------|
| `code` | numeric event id (1158 for `wam_daily`, 460 `wam_login`, 462 `wam_call`, 854 `wam_message_send`) | found |
| `samplingRate` | `C036300x(a, b, c, flag)` is stored as `A02=a, A01=b, A00=b, A03=c`; the sampler uses `A00 = b`. Default `C0Fc.DEFAULT_SAMPLING_RATE = (1, 20, 20)` | found |
| `bufferChannel` | 0..3, see 2.2 | found |
| `psId` | `-1` = not private; otherwise a private-stats key hash, see 2.3 | found |
| `getFieldsMap()` / `getFieldsMapForFalco()` | numeric field id to value (passed to native) / snake_case name to value | found |
| `validate()` | list of violations (`.nonnull` and similar rules), see 3.2 | found |
| `serialize(C3T8)` | body is `throw new NullPointerException("serialize")`; serialisation is native | found |

Fields use Java boxed types (`Boolean`, `Integer`, `Long`, `Double`, `String`). Enums and timers travel as integers (inferred from the attribute setter, which only accepts null / String / Integer / Long / Double / Boolean). `wam_daily` has 218 numeric slots and 205 named slots (13 numeric slots are null-only), identical to the earlier 2.26.35.8 count.

### 2.2 Channels

| `bufferChannel` | Events (parsed) | Name (labels inferred; Java uses plain ints) | Tier |
|-----------------|-----------------|------|------|
| 0 | 824 | REGULAR | found |
| 1 | 8 | REALTIME | found |
| 2 | 168 | PRIVATE (needs a private-stats id, see 2.3) | found |
| 3 | 8 | anonymous realtime private-stats, "RTPS" in native log strings (inferred label) | found / inferred |

Total parsed: 1,008 event classes with distinct ids. The mapping is passed unchanged to native (`jvidispatchIIIIIOO` channel argument 0..3). Any other value throws `IllegalArgumentException("Unsupported channel type")`.

REALTIME events (ids): 2098 `wam_ui_action_real_time`, 5504 `wam_wefr_client_exposure`, 5278 `wam_android_test_realtime`, 6640 `wam_wefr_group_client_exposure`, 6088 `wam_restore_contacts_realtime_event`, 4290 `wam_wa_fs_chat_transfer`, 2872 `wam_xplatform_migration_export`, 6266 `wam_cac_client_event` (found).

Channel 3 events: 5164 `wam_wam_test_anonymous_realtime`, 7312 `wam_mm_signal_undisclosed`, 7352 `wam_mm_signal_realtime`, 6160 `wam_wamo_video_event`, 6158 `wam_wamo_ctwa_1pd_conversion`, 7956 `wam_wamo_promo_pog_impression`, 5712 `wam_wamo_promo_reporting_events`, 7350 `wam_wamo_alv2_link_click` (found). `C06650Fo.A01` drops a channel-3 event unless its code is in two hard-coded arrays (`AbstractC38512Gog.A00` 3 ids, `A01` 5 ids). Those 8 ids are exactly the 8 channel-3 events, so in this build the check drops nothing (inferred from the id sets).

### 2.3 Private-stats ids (`psId`)

| `psId` (int) | Key string in native profile file | Rotation (days) | Events | Tier |
|--------------|-----------------------------------|-----------------|--------|------|
| `-1` | none (not private) | – | 832 (regular + realtime) | found |
| `0` | `none` (buffer global 6005 holds the string `none`) | – | 94 (86 private + 8 channel 3) | found; "none" mapping inferred |
| `113760892` | `default_ps_id` | never (`-1`) | 66 | found |
| `56300709` | `id_pre_metrics` | never (`-1`) | 1 (`wam_ps_app_launch`) | found |
| `248614979` | `id_ttl_daily` | 1 | 4 | found |
| `42196056` / `191000728` | `id_ttl_weekly` / `id_ttl_monthly` | 7 / 30 | 0 | found |
| `37887164` | `id_ttl_90_days` | 90 | 1 (`wam_clock_skew_difference_t`) | found |
| `152546501` | `group_exit_experience_id` | 30 | 4 | found |
| `216763284` | `group_safety_check_id` | 30 | 6 | found |

Key strings and rotation days were read from the eight `WAMMetadataPSIDProfile-*` files (see 6.3), the event counts from the event classes.

### 2.4 Weights across the catalog

Effective schema weight `A00` per event (the event is kept with probability 1/weight and the weight is stored with the event):

| Weight | Events | Typical members |
|--------|--------|-----------------|
| 1 (always) | 826 | `wam_daily`, `wam_registration_complete`, `wam_blocking_funnel` |
| 5 / 10 | 6 / 12 | `wam_message_send` (5), `wam_message_context_menu_actions` (10), `wam_ui_action_real_time` (10) |
| 20 | 135 | `wam_message_delete_actions`, `wam_message_high_retry_count`, all events on `DEFAULT_SAMPLING_RATE` (81) |
| 100 / 200 | 4 / 2 | `wam_login_stage_reliability` (100) |
| 1000 | 17 | `wam_message_stanza_receive`, `wam_call_stanza_receive`, `wam_status_stanza_receive`, `wam_iq_send`, `wam_push_latency`, `wam_db_perf` |
| 10000 | 4 | `wam_receipt_stanza_receive`, `wam_android_profilo_usage`, `wam_android_message_target_perf`, `wam_notification_highlight_result` |

The weight is not a feature switch: the server can override it per event (8.2). One event with a build-constant weight was not binned.

---

## 3. Java logging pipeline

### 3.1 Post path

`CNW` = `CNI(event, null, false)`: resolve weight (8.1), run the channel-3 allowlist (`A01`), then execute runnable `X.1Fc` on the WAM executor (`C06600Fj.A01`):

| Step | Behaviour | Tier |
|------|-----------|------|
| Runtime latch | `C06650Fo.A0K` (`CountDownLatch`) blocks the executor until the common attributes are initialised ("wamruntime/initializeCommonAttributes: runtime initialized") | found |
| Validation | `event.validate()` runs for channels 0 and 1 only (not for the validation event class `C40251kT`). Each violation becomes a `wam_wam_validation_error_event` (id 5560) with the offending event code, a random session value, and `;`-joined rule parts | found |
| Logger modes (`A04`) | `3`: for codes in a configured set writes `traceIdInt` (random 64-bit) into the event by reflection; `10`: for events passing `C06630Fm` (Falco migration batch 1..16, not on a deny list) writes `dedupKey` (random 64-bit); `1` / `3`: additionally post a Falco event (`_test$<name>` / `<name>_shadow`) | found |
| Dispatch | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fieldsMap)` after ensuring the library is loaded | found |
| Log upload trigger | AB string prop **31314** holds `"code:N;code:M"`; if `Random.nextInt(N)==0` for the posted code, the crash and log reporter is asked to upload device logs with tag `wam-event/<falco name>`. This uploads logs, not the WAM buffer | found |

`dedup_key` and `trace_id_int` are fields of the event schema (present in `wam_login`, `wam_app_launch`, `wam_message_send`); they are random per event and are not user identifiers (inferred from the generator).

### 3.2 Validation rules

In `C0Fp` (`wam_daily`) the field `ai_widget_installed` is always reported as a violation because no Java member backs it (rule `daily .nonnull`), and `default_after_read_enabled` when its member is null. Consequence (inferred): every daily event on channel 0 also produces validation events (id 5560).

### 3.3 Flush and lifecycle triggers

| Trigger | Call | Native op | Tier |
|---------|------|-----------|------|
| Connection handler connected | `C0A4.BvO` -> `CKt(0)` | `jvidispatchIIO(4, 0, ctx)` | found |
| Connecting / disconnected | `BvP`, `BvQ` -> `CKt(1)` | `jvidispatchIIO(4, 1, ctx)` | found |
| Offline message processing complete (`XmppStateManager/offlineProcessComplete`, also clears `C0A2.A07`) | `BvR` -> `CXW(false)` only if AB prop **9654** | `jvidispatchIO(10, ctx)` (flush active buffers) | found |
| Explicit flush | `Bba()` -> `CXW(true)`; `CXZ()` flushes and waits up to 2500 ms | `jvidispatchIO(10, ctx)` | found |
| Call end | `C24895Anr.A02` posts `WamCall`, then `Bba()` if the call is flagged or AB prop **16047** | flush | found |
| Re-registration / account removal | `C25100xS` ("RegistrationManager/reregister/rm-me") -> `CUj()` | `jvidispatchIO(12, ctx)` ("wamruntime/resetruntime") | found |

State argument 0/1 is the XMPP connection state mirrored into the native transports (log string "wameta/transport/status - %d"). The meaning of 0 = connected is read from the callback mapping, not from native code (inferred). `C0A2.A04` states: 1 connecting, 2 connected, 3 disconnected, 4 stopped; `A07` is true from connect until offline processing completes, so `A0N()` means "connected and still draining offline messages".

### 3.4 JNI surface

| Direction | Signature | Purpose | Tier |
|-----------|-----------|---------|------|
| Java to native | `jvidispatchIOOOO(0, path, networkSession, ctx, config)` | init runtime (log "WAJContextInitWAMRuntime"), see 4 | found |
| Java to native | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)` | log event | found |
| Java to native | `jvidispatchIIIOO(0, channel, attrId, String, ctx)` / `jvidispatchIIIO(4, channel, attrId, ctx)` / `jvidispatchIIIIO(1, channel, attrId, bool, ctx)` / `jvidispatchIIIDO` / int, long variants | set common attribute (null, string, boolean, double, integer) | found |
| Java to native | `jvidispatchIIO(4, state, ctx)` / `jvidispatchIO(10, ctx)` / `jvidispatchIO(12, ctx)` | connection state / flush / reset | found |
| Java to native | `jvidispatchIOOOO(4, ctx, signedCredential, acsPublicKey, configId)` | result of the credential IQ (all null on failure) | found |
| Native to Java | `jnidispatchIO(6, byte[])` | send one regular buffer as `w:stats` IQ, returns 1 on `result` | found |
| Native to Java | `jnidispatchIO(7, byte[32])` | send the `privatestats` credential request | found |

---

## 4. Runtime initialisation

`RunnableC29323CoA` case 33 builds a config map and calls native init once. Path is `<filesDir>/wam`.

| Config key | AB prop | Type | Likely meaning | Tier |
|------------|---------|------|----------------|------|
| `platform_code` | – | int `2` | Android platform id | found |
| `beacon_probability` | **6977** | int | probability for the native "beaconing" status per event (`WAMBeacon`) | found; meaning inferred |
| `storage_size` | **9822** (x 1024) | long | buffer storage cap (KiB to bytes); native logs "no-enough-storage" and drops events | found; unit inferred |
| `buffer_timeout` | **12399** | int | buffer rotation timer | found; meaning inferred |
| `throttling_percentage` / `throttling_exempt` | **9457** / **9456** | int / string | upload throttling and exempt list | found; meaning inferred, format unknown |
| `enable_extra_logging` | **14310** | bool | verbose native logging | found |
| `enable_ps_upload_v2` | **15205** | bool (only when on) | native "beginning upload v2 logic" on the private transport | found |
| `enable_aggregation` / `aggregation_config` | **11981** / **11982** | bool (only when on) / string | enables `WAGAggregation` with its rules | found; format unknown |

The same call receives a `networkSession` object created by `C25810yb`; its use by the native HTTP wrappers is inferred. Defaults of the AB props are server-delivered and were not resolved.

---

## 5. Common (global) attributes

Global attributes are written by `RunnableC29340CoR` case 0 through `C06590Fi.CYl(value, attrId, channel)` with channels 0..3. A helper sets all four channels at once; others set only 0 and 1. Private channels (2, 3) therefore get a reduced set.

| Attr id | Value source | Channels | Tier |
|---------|--------------|----------|------|
| 3 / 5 | MNC / MCC parsed from `TelephonyManager.getNetworkOperator()` (5 or 6 digits, GSM only) | 0 1 2 3 | found |
| 11 / 1659 / 1657 | platform code `2` / platform code `2` / constant `3` | 0 1 2 3 | found |
| 13 / 15 / 17 / 21 | `Build.MODEL-Build.MANUFACTURER` / `Build.VERSION.RELEASE` (skipped with AB prop **12637**) / app version `2.26.41.6` / `true` (beta flag inferred; hard-coded in this beta APK) | 0 1 2 3 | found |
| 287 / 289 / 495 | `Build.MANUFACTURER` / `Build.MODEL` / a device string (not resolved) | 0 1 | found |
| 655 / 689 / 2617 | device memory and class metrics (`C38271gj`, `IJJ.A02/1048576`, `C38261gi`) | 0 1 2 3 | found; names inferred |
| 4473 | AB config key (`ab_key` from the last `<props>` response, re-set on every AB update) | 0 1 | found |
| 5029 | comma-joined AB experiment exposure ids (`BxP`); with AB prop **31830** a merged map of `ab-props` and `ab-private-abprop` | 0 1; also present in a private buffer (channel 2) | found |
| 6251 / 10255 | app signature check / Play installer flag | 6251: 0 1 2 3; 10255: 0 1 | found, see [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |
| 12017, 12027, 14507, 15265, 15611, 23, 707, 7335, 13293, 23043 | assorted app-state values (12027 boolean from the account state object, 707 `primary_platform_name` only when 12027 is true, 13293 = AB prop **3664**, 15611 WASafe constant (see [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)), 7335 `true` once init hooks ran) | mostly 0 1; 13293 all four | found; meanings inferred or unknown |
| 47 | commit time, int32 seconds, added natively | all | found (buffer file) |
| 6005 | private-stats id value (UUID string or `none`), added natively | private buffers | found (buffer file) |
| 2795, 105 / 6833 | native-added, regular buffers only / value from `C21730rv`, channels 2 and 3 only | 0 / 2 3 | found; meanings unknown |

No phone number, JID or account id is among the common attributes written by Java. The regular transport is tied to the account by the authenticated connection it is sent over (inferred, see 9).

---

## 6. Native storage

Strings from `libwhatsapp.so` (`WAMBufferStoreImpl`, `WAMPSIDProfileStoreImpl`, `WAMPrivateCredentialStoreImpl`, `WAMMetadataStoreImpl`) and the files of an installed 2.26.41.6 data directory agree.

### 6.1 Directory `files/wam/`

| File | Content | Tier |
|------|---------|------|
| `wamt-a-<channel>-0-<seq>` | active buffer, 65,559 bytes (preallocated, zero padded); a native string `wamt-o` suggests rotated buffers (inferred) | found |
| `wam-metadata` | `MTD` v4 container with per-channel counters; the stored next sequence for channel 0 equals the highest file sequence plus one | found; layout inferred |
| `WAMMetadataPSIDProfile-<n>-<keyHash>` | one private-stats profile per key hash (8 files seen) | found |
| `WAMMetadataPrivateCredential-<n>` | stored credential for the private transport (`signed_credential`, key, config id; v2, ~120 bytes) | found; layout inferred |

The third number in the file name is a stream id (log "wameta/buffer/rotated stream id: %d, channel: %d, buffer sequenceNumber: %d"; always `0` in the sample), the last is the buffer sequence.

### 6.2 Buffer file layout

```
off  0   "WMT" 03                      container magic, version 3
off  4   u32 LE  used length           = (end of used data) - 31   (checked in 2 files)
off  8   u32 LE  ?                     counter, meaning unknown
off 12   u32 LE  event count           equals the number of event markers decoded
off 16   u32 LE  ?                     close to the used length (+4, +6, +31 in samples)
off 20   u32     ?                     check value (inferred), algorithm unknown
off 24   "WAM" 05                      WAM header: magic + protocol version 5
off 28   u8  0                         flag byte (0 in all samples)
off 29   u16 LE  buffer sequence       equals the number in the file name
off 31   u8  channel                   0 regular, 2 private in samples
off 32   TLV entries                   globals first, then events
```

Found for every byte listed with a value; fields marked "?" are unknown.

### 6.3 Private-stats profile

`WAMMetadataPSIDProfile-<n>-<keyHash>` (78 to 90 bytes), layout read from all eight files:

```
u8 version(2) │ i32 LE keyHash │ i32 LE rotationDays │ u8 ? │ float64 LE (timestamp, inferred) │ u32 ? (1) │
u32 keyLen │ u32 uuidLen(36) │ key string (e.g. "id_ttl_daily") │ UUID string
```

Rotation days read from the files: -1 (`default_ps_id`, `id_pre_metrics`), 1, 7, 30, 30, 30, 90 (see 2.3). Native strings name the operations `WAMPSIDProfileRotatePSID`, "psid delegated rotation was not persisted" and corruption checks (`invalid rotationInDays`). The UUID is what goes into global 6005 of private buffers. Whether rotation is driven by local time or by the server is unknown.

---

## 7. WAM wire format

Confirmed on real buffers: a decoder written from the tag scheme below parsed globals and events of two buffers (regular and private) without leftovers.

### 7.1 Entry encoding

Each entry is `[tag][field id][payload]`.

| Part | Encoding | Tier |
|------|----------|------|
| Tag low nibble | role: `0` global, `1` event marker, `2` field; OR `0x04` last-in-group; OR `0x08` field id is `u16 LE` instead of `u8` | found |
| Tag high nibble | value type: `0x00` null, `0x10` int 0, `0x20` int 1, `0x30` int8, `0x40` int16 LE, `0x50` int32 LE, `0x60` int64 LE, `0x70` float64 LE, `0x80` string (u8 length), `0x90` string (u16 LE length), `0xA0` string (u32 LE length) | found for int 0/1, int8, int16, int32, string u8 and u16 (all decoded from buffers); the others are inferred from the scheme and the Baileys encoder |
| Integers, strings, byte order | smallest integer form (0 and 1 live in the tag); UTF-8 strings; little-endian everywhere (the stanza codec is big-endian) | found |

### 7.2 Event marker

An event marker is role `1` with the event id as field id. Its value is the sampling weight, stored positive in the buffers: events with schema weight 20 (`wam_secure_file_usage`, `wam_whatsapp_quick_promotion_client_eligibility_waterfall`) carry 20, events with weight 1 carry 1 (found). Fields follow with role `2` (the `0x04` last-field flag was not checked). A global block (role `0`) is written when attributes change, so globals repeat between events (commit time 47 is rewritten many times, found).

The IQ payload is 4 to 126,976 bytes (9). That it equals the buffer from offset 24 (the `WAM` header onward) is not shown by code; it is inferred from the layout and from Baileys sending the same header (15).

---

## 8. Sampling and per-event weights

### 8.1 Resolution (`C0Fg.A00`, simplified)

```
override = prefs(code == 1094 ? "app_launch_event_sampling_weight" : "field-stats-events-sampling"[code], 0)
weight   = override != 0 ? override : schema.A00         // sampler becomes (|w|,|w|,|w|,|w|) for an override
keep     = random.nextInt(sampler.A00) == 0              // 1-in-N; null return = "(dropped)"
```

| Item | Value | Tier |
|------|-------|------|
| Local overrides | prefs file `field-stats-events-sampling` (key = event code) and `app_launch_event_sampling_weight` (event 1094); weight 1 is always kept | found |
| Native guard | "wameta/logger event weight exceeds max, dropped"; the limit is native | found; value unknown |
| Per-call sampling | `WamCall`: `logSampleRatio` field (id 1120) of the event decides the weight, `new C036300x(i, i)` | found |

### 8.2 Server delivery (AB props response)

`C28894Cgv.CFS` handles the AB-props result (`<props>` node). Each `<prop>` child is either a config prop or an event sampling entry:

```
<props ab_key hash refresh refresh_id delta_update>
  <prop config_code config_value config_expo_key/>    -> ab-props
  <prop event_code="854" sampling_weight="5"/>        -> field-stats-events-sampling
</props>
```

When `hash` is non-empty the sampling prefs are cleared and rewritten from all `event_code`/`sampling_weight` pairs; entry 1094 also writes `app_launch_event_sampling_weight` (and removes it when absent). So the server controls per-event weights, and the weights are sent back with each event so the server can scale counts (inferred from the field travelling with the event; server use unknown).

The server therefore shapes WAM through AB props, sampling weights and the private credential; nothing is pushed on the upload IQ itself (the IQ only gets `result`).

---

## 9. Regular upload (`w:stats`)

Native calls `JniBridge.jnidispatchIO(6, bytes)`. Java builds and sends:

```
<iq xmlns="w:stats" to="s.whatsapp.net" type="set" id="..">
  <add t="<unix seconds>">[binary: WAM buffer]</add>
</iq>
```

| Item | Value | Tier |
|------|-------|------|
| Transport | the normal authenticated chat stream (`C10140Tq`), same as any IQ | found |
| `t`, bounds, timeout | `t` = current unix seconds (added only within 1,577,865,600..4,102,473,600); payload checked against 4..126,976 bytes; IQ timeout 32,000 ms (synchronous wait) | found |
| Success | response attribute `type == "result"` -> accounting `C0VI.A02(len, 32)`, return 1 | found |
| Failure | other type or interrupt -> log "FieldStatsXmppImpl/error sending fieldstats IQ", return 0 (native decides retries; "_WAMTransportManagerUploadFailedPermanently" exists) | found |
| Postponed while in a call | return 0 with log "WamJniBridge/upload postponed" if a call is active, unless AB prop **15507** is on, or the call is a group call and AB prop **468** is on | found (decompiler flow, default of the group flag assumed false) |
| Postponed during offline processing | return 0 if `C0A2.A0N()` (connected and offline messages not yet drained) and AB prop **9654** is on; with 9654 off the IQ is sent | found |
| Account link / compression | no account id in the payload, the server sees the authenticated session; no compression on the Java path | inferred / found |

The same prop 9654 enables the flush at `offlineProcessComplete` (3.3). Together: with 9654 on, uploads wait until the offline message queue is drained and a flush runs at that moment (inferred from the two call sites; retry timing after a postponed attempt is native and unknown).

---

## 10. Private upload

Private channels (2 and 3) are not sent as `w:stats`. The native `WAMTransportPrivate` uploads over a separate HTTP transport (`WCIHTTPImpl`) with an anonymous credential. Everything below comes from native log strings and the Java credential handler.

### 10.1 Credential request

```
<iq xmlns="privatestats" to="s.whatsapp.net" type="get" id="..">
  <sign_credential version="1">
    <blinded_credential>[32 bytes]</blinded_credential>
  </sign_credential>
</iq>
```

| Part | Detail | Tier |
|------|--------|------|
| Sender | `JniBridge.jnidispatchIO(7, byte[32])`; error code in the IQ tracker is 239, timeout 32,000 ms | found |
| Response (`KRL.CFS`) | `<sign_credential t=..><signed_credential/><acs_public_key/><config_id/></sign_credential>`; the three byte arrays are handed to native with `jvidispatchIOOOO(4, ctx, ...)`; on error or no response native gets nulls | found |
| Telemetry | event 2242 `wam_sign_credential` (regular channel) with status 3 = failure, 1 = success, and elapsed time | found |
| Verification and storage | native strings "Invalid signature received from server", "fails validation" (the client validates the signature); stored in `WAMMetadataPrivateCredential-<n>`, renewed on 401 ("send failed, renew credentials") | found |
| Scheme | blinded request, signed response, ACS public key: an anonymous credential, so the credential does not link private uploads to the account | inferred |

A separate generic sender `C1N8` uses the same namespace with `<sign_credential version="2">` and `project_name` for other ACS projects (prefs `acs_token_*`); it is not the WAM path.

### 10.2 Upload

| Item | Detail | Tier |
|------|--------|------|
| Endpoints | native logs "url/received", "fetch_endpoints/custom_endpoints - got endpoints: %d", "invalid_ps_endpoint, ignoring"; no URL literal in Java or `libwhatsapp.so` | found; source of the list unknown |
| Failure handling and timer | "try next endpoint", "have next credentials", "401, no more endpoints"; transport timer ("timer/started - interval: %.1f seconds") started on "connection_ready", stopped on "connection_unavailable" | found; interval unknown |
| Realtime private | per-event buffers: "create_buffer/realtime/buffer-created ... event id", "sendsingleeventimpl/realtime" | found |
| Headers, body framing, compression | not visible | unknown |

The Falco logger `C40099Hdc` with mode 9 drops events with channel 2 or 3 or a psId from its own path and counts them as `wa:dropped_private_stats` (found), so private events are not duplicated into that logger (inferred).

---

## 11. `wam_daily` and periodic events

Event id 1158, Falco name `wam_daily`, channel 0, weight 1, 218 numeric / 205 named fields. For the root, emulator, custom-ROM and mod-client fields, see [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md); only the plumbing is recorded here.

### 11.1 Scheduling (found)

| Piece | Detail |
|-------|--------|
| Alarm | `BEL.A01`: next local midnight + random jitter `nextInt(AB prop 5529)` (unit converted by `C20D.A02`), action `com.whatsapp.action.DAILY_CRON` |
| Catch-up | action `com.whatsapp.action.DAILY_CATCHUP_CRON`, retried every 15 minutes while "last_daily_cron" is not from today |
| Guard | skips with "too frequent" if the cron already ran today (pref `last_daily_cron`); skips all crons while a chat transfer is in progress; crons needing the message store are skipped when it is not ready |
| Executor | iterates a DI set of `InterfaceC29983D2n` crons (`Bo5`); `C28643Ccj` (tag `WamDailyEventDailyCron`) runs only when `anonymousClass091.BS3()` (account state, meaning not resolved) |

### 11.2 Population

`C28643Ccj.Bo5` creates `new C0Fp()`, calls `C4k(C0Fp)` on every populator in a DI set (28 files define a `C4k(C0Fp)` populator), then `CNW(c0Fp)` with the default schema weight. The device-flag populator is smali-only in this build (`smali_classes7/X/Cdt.smali`; the decompiler fails on it) and reads and writes the pref `last_daily_event` (wall-clock ms), assigning `time_delta_since_last_event`. The decompiled branch changes the delta only from 0 to 1, so no unit or cadence claim is made for that field. `last_daily_event` is not the scheduler (the alarm in 11.1 is).

The same cron emits a Falco-only event `wam_daily_permission` (sampled): contacts permission status, gallery permission, camera / record-audio / coarse and fine location grants, OS notification setting, address-book sizes, optional thread counts (AB prop **25576**) and `profile_photo_is_set` (AB prop **34207**), `os_version` (found).

### 11.3 Other periodic events

Other app-start and periodic events: 1094 `wam_app_launch` (weight overridable by `app_launch_event_sampling_weight`), 3300 `wam_ps_app_launch` (private, `id_pre_metrics`), 3178 `wam_clock_skew_difference_t` (private, `id_ttl_90_days`), the `*_daily` family (5798 `wam_reaction_daily`, 3680 `wam_polls_daily_stats`; triggers inferred).

---

## 12. Privacy handling

| Aspect | Finding | Tier |
|--------|---------|------|
| Stable ids in batches | no JID or phone number in Java-written common attributes; `dedup_key` and `trace_id_int` are random per event; the regular channel is authenticated by the stream it travels on | found / inferred |
| Private-stats ids | UUID per key in `WAMMetadataPSIDProfile-*`, global 6005 in private buffers; rotation 1, 7, 30, 90 days or never | found |
| Anonymous credential | blinded token signed by the server for private uploads (10.1) | found; unlinkability inferred |
| Hashed and plain ids | hashed-id fields exist (`hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids`, `message_key_hash`, `invited_user_hash`; hash function not traced); JID-typed strings exist too (`reported_jid`, `e2e_sender_jid`; hashing before logging not traced) | found (names), unknown |
| Reset | account removal and re-registration call native reset (`jvidispatchIO(12)`); a reset of PSID profiles by it is not shown | found / unknown |
| User opt-out | no setting, string or flag found that disables WAM; the only consent-like string in resources concerns support diagnostics. A setting may exist in code paths not searched | unknown |
| Server control | per-event weights (8.2), AB props (13), `throttling_*` and `beacon_probability` config (4); algorithms are native | found; unknown |

---

## 13. Feature flags (AB props as read in the code paths above)

| Prop | Type | Controls |
|------|------|----------|
| **9654** | bool | flush at offline-processing complete (3.3); upload postponed while offline messages are draining (9) |
| **15507** / **468** / **16047** | bool | upload not postponed during a call / during a group call / flush after call events |
| **6977**, **9822**, **12399**, **9457**, **9456**, **14310**, **15205**, **11981**, **11982** | mixed | runtime init config keys (section 4) |
| **31314** | string | `"code:N;..."` log-upload trigger rate per event code |
| **5529** | int | daily cron jitter |
| **12637** | bool | skips OS version, manufacturer and companion attributes (15, 287, 21, 12027, 707) |
| **31830** / **25576** / **34207** | bool | merged private AB list in attribute 5029 / optional `wam_daily_permission` fields |
| **34494..34507, 35169, 35170** | – | array in `AbstractC38513Goh.A01` (16 ids, same count as the Falco migration batches 1..16); use inferred |

All values are server-assigned; defaults were not resolved.

---

## 14. Notable event families

Names are Falco names; ids and channels are from the event classes. Field lists are the named fields of `getFieldsMapForFalco()`.

### 14.1 Messages

| Event | id | Ch / weight | Notable fields |
|-------|----|-------------|----------------|
| `wam_message_send` | 854 | 0 / 5 | 89 fields: `message_send_result`, `message_send_t`, `message_type_str`, `e2e_ciphertext_type`, `e2e_ciphertext_version`, `is_pq`, `is_lid`, `retry_count`, `resend_count`, `message_is_forward`, `message_is_fanout`, `message_distribution_type`, `participant_count`, `device_count`, `message_key_hash`, `is_view_once`, ephemerality, edit/revoke, bot and private-AI fields |
| `wam_message_receive` | 450 | 0 / 20 | 58 fields: `message_receive_t0..t2`, `message_queue_time`, `message_is_offline`, `offline_count`, `stanza_process_count`, `padding_bytes_size`, `message_addressing_mode`, `server_addressing_mode`, `session_scope`, sticker and contact-card fields |
| `wam_e2e_message_send` / `_recv` | 476 / 478 | 0 / 20 | `e2e_successful`, `e2e_failure_reason`, `e2e_destination`, `group_encryption_state`, `enc_retry_count`, `pq_receive_gate_state` |
| `wam_e2e_message_decrypt_fail_sender` | 3524 | private (ps `none`) | `e2e_sender_jid`, `e2e_failure_reason`, `retry_count` |

### 14.2 Calls

`WamCall` (id 462, channel 0) is created from native stats (`ConvertFieldStats`, "can not construct com/whatsapp/fieldstats/events/WamCall") and has roughly 1,700 named fields (1,716 `put` sites in the Falco map). `WamJoinableCall` is id 2572. Sampling is `logSampleRatio` (field 1120), and the event is flushed at call end (3.3). Other call events: 2582 `wam_call_stanza_receive` (weight 1000), 3452 `wam_call_critical_events`, 4568 `wam_call_user_journey`. Call signaling itself is in [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md).

### 14.3 Login and registration

| Event | id | Fields |
|-------|----|--------|
| `wam_login` | 460 | `login_result`, `login_t`, `connection_origin`, `connection_t`, `login_dns_resolver`, `login_ip_source`, `login_port`, `login_resolved_pop`, `login_socket_provider`, `noise_protocol_version`, `retry_count`, `server_error_code`, `passive`, `long_connect`, `network_is_vpn`, `android_keystore_state`, `pending_acks_count`, `unprocessed_message_count` (30 slots); see [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) |
| `wam_reg_init` / `wam_registration_complete` | 2046 / 1342 | init timings (`contacts_sync_t`, `groups_init_t`, `total_t`); 30 fields incl. `registration_t`, `addressbook_size`, `contacts_permission_authorization_status`, `device_identifier`, `google_account_list_hashed_reg`, `invited_user_hash`, `is_new_jid`, profile-picture and permission fields |
| `wam_account_encryption_attestation` | 8164 | name suggests attestation outcome (inferred); see [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |

### 14.4 Spam, report, block

Flows are in [WA_REPORTING.md](WA_REPORTING.md) and [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) (`wam_wfacp_ban_action`, id 5028); WAM side:

| Event | id | Channel | Fields |
|-------|----|---------|--------|
| `wam_spam_report_perf` | 6310 | 0 | `report_spam_flow`, `report_status`, `report_attempt_count`, `report_duration_ms`, `report_error_code` |
| `wam_report_conversation_context` | 4608 | 0 | `reported_jid`, `spam_flow`, `estimated_num_messages_sent/received`, `is_chat_maybe_suspicious`, `is_in_addressbook`, `first_entry_point`, `num_call_msgs_to_report` |
| `wam_blocking_funnel` / `wam_reporting_funnel` | 4920 / 4924 | 0 | `block_flow_action`, `hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids` |
| `wam_reporting_token_validation_failure` | 5466 | 0 | `reporting_token_validation_failure_reason`, `reporting_token_version`, `is_part_of_group_history` |
| `wam_reporting_token_validation_failure_sender`, `wam_reporting_token_additional_client_validation` | 6094, 6702 | 2 (`default_ps_id`) | sender-side variants |
| `wam_message_template_blocks` | 3002 | 2 (`default_ps_id`) | business template block reasons |

### 14.5 Experiments

`wam_wefr_client_exposure` (id 5504, realtime) logs exposure with `exposure_key`, `device_exp_id`, `user_lid`, `guest_id`, `is_canonical_ent_present`, `sent_with_daily`. It carries a user LID field (found; server use unknown). `wam_ui_action_real_time` (2098, weight 10) carries only `chatd_internet_connectivity` and `dedup_key`.

---

## 15. Baileys (`baron-baileys-v2`, compared against its source)

Baileys sends WAM buffers with the same IQ as the Android client.

| Aspect | Baileys (`src/Socket/socket.js`, `src/WAM/encode.js`) | Android 2.26.41.6 | Tier |
|--------|--------------------------------------------------------|-------------------|------|
| Upload stanza | `<iq to=s.whatsapp.net xmlns="w:stats" type="set"><add t=…>buffer</add></iq>` | same | found both |
| Header | `"WAM"`, version byte 5, byte 4 = `1`, `u16 BE` sequence at 5, channel `0` at 7 | `"WAM"`, version 5, byte 4 = `0`, `u16 LE` sequence at 29, channel at 31 (in the file with a `WMT` container in front) | found both |
| Value encoding | `0/1` in tag, int8, int16/int32 LE, float64 LE, strings with u8/u16 LE/u32 LE length, wide id flag `0x08` | same bits | found both |
| Event weight | written as `-weight` | stored positive in buffer files | found both |
| Channels, flush | regular only; flush every 30 s and after login, failures only logged | 0..3; native rotation and transports | found |

The difference in sequence byte order and weight sign is not an error proven by this report: Android on-disk files need not equal the bytes the native transport uploads, and the server's parser was not observed. Nothing in the chat code paths read here waits on WAM state; whether the server reacts to a missing or unusual upload is unknown (19).

---

## 16. Error cases

| Symptom | Cause | Fix / note |
|---------|-------|------------|
| Event missing in buffers | weight roll failed (1-in-N), channel-3 allowlist, storage cap, native "weight exceeds max", "have to drop event" | check weight 2.4 and AB props 8.2, 4 |
| Daily event produces validation events | `ai_widget_installed` rule fails for every `wam_daily` (3.2) | expected in this build |
| "WamJniBridge/upload postponed" | call active without 15507 / 468, or offline queue still draining with 9654 | transient; native retries (inferred) |
| "FieldStatsXmppImpl/error sending fieldstats IQ" | IQ error, timeout (32 s) or interrupt | native retry / permanent failure path |
| "Cannot log before WAM runtime is initialized" / "after ... terminated" | native lifecycle order | Java waits on `A0K`; terminate is a native state |
| Private upload fails with 401 | credential rejected | renew via `privatestats` IQ (10.1) |

---

## 17. Key distinctions

| Pair | Difference |
|------|------------|
| WAM vs Falco | WAM events go through the native runtime and buffers; the Java Falco logger (`C40099Hdc`, `FFLogger`) is a parallel path that re-uses the same event classes by Falco name. Falco migration batch 1..16 is per event (`internalFalcoMigrationBatchNumber`) |
| Event weight vs feature flag | weight = 1-in-N sampling and a multiplier sent with the event; flags only gate transport behavior |
| Regular vs private upload | regular = `w:stats` IQ on the chat stream; private = separate HTTP transport with a blinded credential |
| `psId` vs global 6005 | `psId` is a static key hash on the event class; 6005 is a rotating UUID written natively into private buffers |
| Field id vs global id | the numeric spaces overlap (47 is a global; field 47 of an event differs); the tag role disambiguates |
| `wam-event/<name>` vs WAM upload | the former uploads device logs through the crash reporter, the latter uploads metrics buffers |
| On-disk buffer vs wire payload | the file has a `WMT` container and padding; the IQ payload layout is inferred |

---

## 18. Complete flow

```
[App code / native call stats]  new Event(...) / ConvertFieldStats -> WamCall
    ▼
[C06650Fo.CNW / CNI]  weight = override (prefs) or schema A00, keep 1-in-N ; validate (ch 0,1) -> event 5560
    ▼
[WAM executor]  jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)
    ▼
[libwhatsapp.so WAMRuntime]  encode TLV (LE), add globals (47 commit time, 6005 psId UUID, common attrs)
    ▼
[files/wam/wamt-a-<channel>-0-<seq>]  "WMT" container + "WAM" 5 header, 64 KiB
    │  rotate (buffer_timeout) / flush (offline-complete with 9654, Bba, call end, CXZ)
    ├── channel 0, 1 ─────────────────────────────┬── channel 2, 3 ───────────────────────────────┐
    ▼                                             ▼                                              
jnidispatchIO(6, bytes)                       jnidispatchIO(7, 32 bytes blinded token)
    │  postponed in calls / offline drain          │  <iq xmlns="privatestats" type="get">
    ▼                                             ▼
<iq xmlns="w:stats" type="set"><add t=..>     [WA server] signed_credential, acs_public_key, config_id
  bytes</add></iq>  on the chat stream              │  stored, renewed on 401
    ▼                                             ▼
[WA server] type="result" -> return 1         HTTP upload, endpoint list source unknown -> [private-stats backend]

[WA server] <props> response: event_code -> sampling_weight, config_code -> AB props  ──►  prefs (8.2)
[DailyCronAction alarm: next local midnight + jitter(5529)] -> C28643Ccj populates C0Fp (wam_daily 1158) -> CNW (same path, channel 0)
```

---

## 19. Unknowns

| Question | Why unknown |
|----------|-------------|
| Exact bytes of the upload payload versus the buffer file | native transport not disassembled; only IQ bounds seen |
| Compression and header framing of private uploads, endpoint list source | no literal in Java or strings; native HTTP path not traced |
| Native rotation interval, retry schedule, weight maximum, drop rules, beaconing algorithm | stripped native code, no decompiler for the large library used here |
| Meaning of attributes 495, 6833, 2795, 105 and several flag attributes; `WMT` fields at offsets 8, 16, 20; `MTD` fields | sources not resolved, values only |
| Whether any server behavior depends on missing or unusual WAM | server side |
| Hashing of `*_jid` fields; presence of a user-facing opt-out | not traced per event / not found (absence is not proof) |
| Native retry timing, PSID rotation trigger (client time or server instruction), AB prop defaults | native logic not traced; defaults come from server config |
| Trigger of daily crons other than `wam_daily` | only the cron registry and the `wam_daily` cron were read |
