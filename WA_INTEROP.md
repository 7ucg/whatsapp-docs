# WhatsApp Interop — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** third-party chat interoperability on Android (DMA style): feature gating and AB flags, consent notice and opt-in, integrator list, interop JID domains and binary JID tag, user discovery (`w:interop` FetchUsers), `w:interop` IQ set, restricted `InteropMessage` plaintext and supported message types, encryption and stanza differences, interop groups (MEX ops, notifications, add-privacy), reachability ping, block and report, storage, error cases, differences from native chats, Baileys comparison

---

## 1. What it is (technically)

Interop lets a WhatsApp account exchange 1:1 messages and group messages with accounts of other messaging apps ("integrators"). The client never talks to those apps. It talks to WhatsApp servers, which expose each third-party account as a synthetic JID in the domain `interop` (groups: `interop.g.us`). All statements come from static analysis of the decompiled APK; nothing was captured on the wire or run against a server. Tiers: **found** = read in code or resources, **inferred** = deduced from code, **unknown** = not resolved. Obfuscated names are per-build and were re-resolved in 2.26.41.6 from stable strings (`InteropOptInManager/`, `InteropChatMessageHandler/`, `IntegratorManager/`, `w:interop`, `integrator_display_name`, `xwa2_interop_*`).

Status in this build:

| Part | State in 2.26.41.6 |
|------|--------------------|
| Code | **Present and complete**: UI (10 activities plus fragments and dialogs), IQ client, MEX group and privacy ops, strict receive pipeline, storage, notification handler |
| Server switch | **Gated off by default**: root AB flag **7495** defaults `false`; every interop flag read in code defaults `false` (section 2) |
| Region | Product text limits it to users with a European Region phone number; **no client-side country check was found** (enforcement inferred server-side, via flag 7495 and the integrator list) |
| Integrators | **None hard-coded**: no integrator name, no fixed integrator id in code, resources or assets; list comes from the server (section 4) |

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| Gate (`InteropRolloutManager`, name inferred from a getter) | `C32001Oa` | `A01` eligible, `A02` eligible and primary, `A00` groups, `A03` unified inbox |
| IQ client / builders / parsers | `DmaInteropRPCManager` (`com.whatsapp.infra.smax.generated.dmainterop.outgoing`); `C31107Dfz` (cases 20-23), `C31106Dfy`; `C214369Ee`, `C9EQ`, `C9EP`, `C214389Eg`, `A1J` | five `w:interop` RPCs, strict schema parse |
| Integrators | `C227409sQ` manager, `C23765ANa` store, `A3X` (`IntegratorInfo`), `InteropUiCache` = `SharedPreferencesOnSharedPreferenceChangeListenerC20390p5` (prefs `interop_ui`) | list, opt-in state, UI cache |
| JIDs | `C99O` user, `C41021lm` device, `C55529Oy6` group, `C9YC` parser; writer `C40411kn.A00`, reader `C24610wf` (tag 244) | section 3 |
| Receive | `ENP` -> `C34471Exu` (`DecryptionCallbackInterop`) -> `C34720F4p` (`InteropChatMessageHandler`); `DTF` (9-field plaintext), `EUQ` (`ParseInteropMessageParams`) | strict pipeline |
| Type registry | `C32718EOz`; `FBN` text, `FBK` image, `FBL` video, `FBJ` GIF, `FBH` audio, `FBI` document, `FBM` reaction, `FBG` unsupported | protobuf <-> FMessage |
| Send | `C33446EhE` (branch), `F6P` (`E2eMessageEncryptor`), `F6K` (`<meta>`) | outgoing |
| Groups / privacy | `InteropGroupsManager`, `C3R2`, smali-only `C3Rb` / `C3Qh`; `C0WQ` (notifications); `InteropPrivacySettingsManager`, `C3Q4` / `C3Q1` / `C29664Cuh` | MEX |
| Opt-in | `C229349vm` (`InteropOptInManager`), `ARH`, `A4N`, `C224669lg` / `C24380wI` (notice), `PaaInteropMigrator` | wizard, consent |
| Ping | anonymous `X.0xL` in `C1S0` (`InteropNotificationHandler`), id 270 in `AbstractC32331E9w` | notification |
| Analytics | `AnonymousClass590` | WAM 6684, 7044, 7168, 6680 |

---

## 2. Feature gating

### 2.1 Gate chain (found, `C32001Oa`)

| Method | Condition | Used for |
|--------|-----------|----------|
| `A01()` | account not a dependent account under age-experience rules (`C14980fa.A00` -> `C08520Ne.A03()` -> `C08530Nf.A03()` false; dependent type `EnumC08540Ng.DEPENDENT`) **and** AB **7495** | everything; chat list folder, badge, compose |
| `A02()` | `A01()` and not a companion (`AnonymousClass091.BRD()` false, i.e. `registration_device_id` is 0) | opt-in manager, settings, integrator selection, notification handler |
| `A00()` | `A01()` and AB **15732** | "New group" entry, group privacy step |
| `A03()` | `A01()` and AB **11479** | unified inbox step and combined inbox |

`InteropSettingsActivity.onResume` (calls `finish()`), `InteropOptInSelectIntegratorsActivity.onCreate`, `InteropOptInManager` and the `w:interop` notification handler re-check `A02()`.

### 2.2 AB flags (found: id, default and call sites; names from an older build's name table, id-matched, **inferred**)

| Flag | Legacy name (inferred) | Default | Read at | Controls |
|------|------------------------|---------|---------|----------|
| **7495** | `IS_USER_INTEROP_ELIGIBLE` | false | `C32001Oa.A01`, `C224669lg.A01`, `C230679y0` (badge), `RunnableC23952AUh` (Home), `C0Y5` | root gate; Home badge state |
| **15732** | `INTEROP_GROUP_MESSAGING_ENABLED` | false | `C32001Oa.A00` | group creation, group privacy step |
| **11479** | `WA_INTEROP_UNIFIED_INBOX_ENABLED` | false | `C32001Oa.A03`; id also registered in `C33251Ee2` | inbox type step, combined inbox |
| **25512** | `INTEROP_CONTACT_MASTER_ENABLED` | false | `C0ZT`, `C51044MkK`, `C201508iH`, `C93z`, `InteropSelectChatTypeActivity` | "New contact" entry, saved interop contacts, name resolution |
| **5760** | `INTEROP_PROTOBUF_VALIDATION_ENABLED` | false | `ENP.A00` | routes interop JIDs to the strict `InteropMessage` pipeline (8.1) |
| **38723** | unnamed | false | `EA0.A00` (descriptor) | sender key distribution inside interop groups (log string `interop_group_skdm_processing_enabled`) |
| **23701** | `DMA_INFLATE_VIEW_ONDEMAND_ANDROID` | true | `C1R9` | on-demand inflation of the chat list interop header |

Defined with defaults but no literal reader found (use unknown): **3953** `INTEROP_CLIENT_UX_ENABLED`, **5759** `INTEROP_BOOTSTRAP_ENABLED`, **6613** `INTEROP_WS8_ENABLED`, **18670** `INTEROP_ADD_GROUP_PARTICIPANT_CLIENT_ENABLED`, **20999**, **11518**, **13532**, **14070** (all false); **22752**, **24016**, **24256**, **23652**, **24275**, **24098** (`DMA_*` UI tuning, all true). Flag **11619** (`ENABLE_DMA_GROUP_JID`) has no entry in the default tables. Mechanism: WA_AB_PROPS.md.

### 2.3 Non-AB gates (found)

- Consent notice **20240306** at stage **160** (`C24380wI.A0D`): settings show the config screen only when accepted, else the opt-in landing screen (5.1).
- Dependent account (`C14980fa`): not eligible; `PaaInteropMigrator` leaves interop groups and resets the notice (5.5).
- Primary device (`A02()`): companions cannot opt in or configure.

---

## 3. Identity: JIDs and domains

### 3.1 Domains (found)

| Kind | Class | JID type | Format | Validation |
|------|-------|----------|--------|------------|
| Interop user | `C99O` (`InteropUserJid`) | **22** | `{integrator}-{account}@interop` | a hyphen (last one splits); integrator 1-3 digits, no leading `0`, parsed as int; account 1-15 digits, no leading `0` |
| Interop device | `C41021lm` | **23** | `{integrator}-{account}:{device}@interop` | device index must be **0**, else `C09B` ("Interop device JIDs must have device index 0") |
| Interop group | `C55529Oy6` (`GroupJid`) | **28** | `{gid}@interop.g.us` | gid 1-20 digits, first digit 1-9, no `-` |

- `C0DZ.A0W` = type 22, `A0X` = 22 or 23 (1:1), `A0V` = 28, `A0U` = `A0X` or `A0V` (any interop chat); used in 128 classes. `C41021lm.getRawString()` always prints `:0`. The factory (`UserJid.JID_FACTORY.A04(str, "interop")`, `C9YC.A00`) throws `C09B` ("Invalid interop JID: ...") on any rule violation.
- Integrator ids in IQ responses are bounded 1-999 (same as the 3-digit rule). Group ids are not the legacy `creator-timestamp` form; MEX group ops take the gid without domain (`InteropGroupsManager.A00` strips `@...`).

### 3.2 Binary token (found)

Tag **244** `JID_INTEROP` (writer `C40411kn.A00`, attribute reader `C24610wf`): string `user` (account id, or gid for groups) -> u16 **device** -> u16 **integrator** -> byte **domain**.

Domain byte: **0** = `interop`, **2** = `interop.g.us`; any other value throws ("invalid domain received for JID_INTEROP tuple"). A group tuple must carry device 0 and integrator 0 (else "invalid interop group jid"). The reader renders domain 0 as `{integrator}-{user}[:{device}]@interop` (device omitted when 0). Tag **245** (a separate interop JID form in other clients) has no handler in this build (grep of `C24610wf` / `C40411kn`).

### 3.3 Mapping and display (found)

| Topic | Fact |
|-------|------|
| LID / PN | `WaJidMapRepository/setJidMapping refused mapping for interop JID`; an interop JID is its own signal address and chat id |
| Name | name source `INTEROP_NAME` (`C0Y7`), value from the contact's `display_name` field (`c06290Dn.A07().A00.A0b`); the message stanza parser reads `notify` and `display_name` for every message (`AbstractC33377Eg6.A02`); use of `display_name` for interop push names inferred |
| Group members | `w:g2` participant parsing keeps the interop JID in the participant record (`C23201A1a` -> `C228499uF.A00(c99o, ...)`), plus `display_name`, `lid`, `phone_number`, `join_time` |
| Profile data | no profile photo or name: "Profile name and photo are not available in third-party chats" (string); integrator icon only (8 MiB cache `cache/interop_image_cache`, loader `interop_image_loader`) |

---

## 4. Integrators

### 4.1 Model (found)

No integrator name, fixed id or identifier-type table exists in code, `res/` or `assets/`; the server decides which integrators exist, their ids, names and group capability. `A3X`: `A00` id, `A03` name, `A02` status (`ONBOARDING`, `ACTIVE`, `REMOVED`), `A04` icon URL, `A05` optedIn, `A01` identifier type (`USERNAME`, `PHONE`, `EMAIL`), `A06` supportsGroupMessaging. Integrator of a JID: `C99O.A00` -> `C227409sQ.A00` -> `A3X`.

### 4.2 Fetch (found, `C31107Dfz` case 20, parser `C214369Ee`)

Request `<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><integrator fetch="all"/></iq>` (`to` = server JID, class `C19380nJ.A00`). Result: `<integrator_list opted_in="true"><integrator id status identifier_type name icon opted_in><features group_messaging/></integrator>...</integrator_list>` (attribute names found; the `features` node shape is inferred from the path `features/group_messaging`).

Attribute map: `status` = `onboarding` / `active` / `removed`; `identifier_type` = `username` / `pn` / `email`; `features` -> `group_messaging` = `true` / `false`; `opted_in` default `true`. Parser limits: 0-999 integrators, id 1-999; an entry without `name` or `icon` is dropped; unknown status or identifier type throws. IQ errors: `bad-request` (400), `internal-server-error` (500) (`A1J.A02` / `A04`).

The refresh coroutine (`C24110Aar` case 34, log `IntegratorManager/refreshIntegrators`) writes the table (5.6) and pref `group_capable_integrators`. Triggers found: opening the opt-in screen; the generic `<ack error>` handler (`C13X`) deletes all `integrator_display_name` rows when an interop 1:1 message is rejected (`C24110Aar` case 35). Other triggers were not resolved.

---

## 5. Consent, opt-in, settings

### 5.1 Consent notice (found)

Notice id **20240306** is a privacy disclosure (`C24380wI`, class `PrivacyDisclosureDataManager`). Stage **160** = accepted (`A0D`); stages 105-399 count as "eligible/shown" (`A02`). `InteropOptInManager.A01` (`C229349vm`):

```
A02() false -> log "interop is not enabled, stop"
notice 20240306 != 160 -> render notice (C32411Pr.A05); ARH.onUserOptedIn sets has_previously_onboarded and continues; dismiss / deny / error stop
else -> InteropOptInSelectIntegratorsActivity(entryPoint)
```

Stage **162** is written by `PaaInteropMigrator` (`C24380wI.A09(null, 20240306, 162, false)`); meaning unknown (not 160, so the notice counts as not accepted afterwards).

### 5.2 Wizard (found, `A4N`, `InteropOptInSelectIntegratorsActivity`)

```
Select integrators (list from table, header "Select the third-party apps you want people to message you from.")
   ▼
[AB 11479] Unified inbox option (COMBINED | SEPARATED) ──► else skip
   ▼
[AB 15732] Group privacy setting ("Who can add me to third-party groups") ──► else skip
   ▼
InteropOptInManager.A01: notice not accepted -> consent notice (5.1); accepted -> straight on
   ▼  onUserOptedIn
SetOptInIntegrators IQ (full list)
```

If the notice is already accepted (editing from settings), the selection screen hides its cancel and continue buttons and `C201718ig.A00` saves directly (save-on-change inferred); inbox type and group privacy are separate rows of the config fragment. The group-privacy step is inferred to end in `A01` (log `BaseInteropOptInViewModel onOptInContinue`). Entry points are an int (`entryPoint`) logged to WAM (5.6).

### 5.3 SetOptInIntegrators (found, `C31107Dfz` case 23, parser `C9EP`)

```xml
<iq type="set" xmlns="w:interop" to="s.whatsapp.net" id=".."><opt_in_integrators><integrator_list>
  <integrator id="12"/> ...      <!-- 0..999 entries, the full desired state -->
</integrator_list></opt_in_integrators></iq>   <!-- result: integrator_list/integrator[@id], each with an optional error child -->
```

Client handling (`C24113Aau` case 40): per-integrator errors are collected; the table is rewritten in one transaction (`opt_in_status` cleared for all, then set for requested minus failed ids). Opt-out has no separate stanza: the opt-out dialogs and the "turn off" path use the same set with a shorter list (inferred from the absence of any other opt-out stanza; the empty-list path was not traced).

UI error mapping (`InteropOptInSelectIntegratorsActivity.A0X`): codes **500**, **810**, **800** -> "Apps can't be saved right now. Please try again later."; any other or null code -> "Apps can't be saved right now."

### 5.4 Settings screens (found, `AndroidManifest.xml`)

Screens (all in `AndroidManifest.xml`): `InteropSettingsActivity` with Main / Optin / Config fragments (landing when the notice is not accepted, else configuration; help FAQ `317021344671277`); `InteropOptInSelectIntegratorsActivity` (apps); `InteropUnifiedInboxOptionActivity` ("Manage inbox", COMBINED vs SEPARATED); `InteropGroupPrivacySettingUpdateActivity` and `...AddBlocklistPickerActivity` (9.4); `InteropReachNotificationSettingsActivity` ("Third-party chat requests", 6.3); `InteropOptOutDialogFragment` / `...IntegratorDialogFragment` ("Turn off third-party chats?"); `InteropConversationsActivity` (folder list); `InteropComposeSelectIntegratorActivity`, `...EnterInfoActivity`, `InteropSelectChatTypeActivity` (new chat / group / contact).

### 5.5 Opt-out and migrator (found)

Opted out: existing chats become read-only (composer banner "Third-party chats are turned off. You can't send messages in this chat, and you won't receive messages."). `PaaInteropMigrator` (`C0q`): runs when the account is a dependent account (`C20K.A1W` = restricted) **and** the notice is accepted; it calls `LeaveInteropGroup` (`groups_to_leave`, response codes in {200, 400, 401, 403, 404, 405} count as done), then writes notice stage 162. "PAA" expansion is inferred (age-experience); the dependent link is found.

### 5.6 Stored state and analytics (found)

| Store | Keys / schema |
|-------|---------------|
| prefs `interop_ui` | `unified_inbox_option` (UNKNOWN / COMBINED / SEPARATED), `who_can_add_me_to_interop_groups` (int), `who_can_add_me_to_interop_groups_hash`, `who_can_add_me_to_interop_groups_deny_list` (set), `optedInIntegratorNames` (set) + per-id name keys, `interop_reach_enabled` (default true), `interop_reach_integrators` (int array), `interop_reach_notifs` (set of `id:name:display_name:t`), `suspended_interop_groups` (set of gids), `has_previously_onboarded`, `group_capable_integrators`; prefs `interop_badge_prefs`: `pref_interop_badge_disabled`, `pref_interop_badge_account_state`, `pref_interop_badge_third_party_chats_state` |
| table `integrator_display_name` | `integrator_id` INTEGER PK, `display_name` TEXT, `status` INTEGER, `icon_path` TEXT default `''`, `opt_in_status` INTEGER default 0, `identifier_type` INTEGER default 0, `group_messaging_supported` INTEGER; index `integrator_opt_in_index` on `opt_in_status` |
| other tables | `wa_block_list_interop` (unique index on `jid`); `wa_address_book` rows with `raw_contact_id = -5` and `jid LIKE '{id}-%@interop'` (`SAVED_INTEROP_CONTACTS`), not written to the phone's contacts |
| WAM | 6684 (banner delivery), 7044 (onboarding flow, session id `InteropOnboardingSessionIdManager`), 7168 (user action), 6680 (third-party inbox); event 1158 carries `interopContactsSize`, `interopContactsSizePerIntegrator` |

---

## 6. `w:interop` IQ set

The five RPCs of `DmaInteropRPCManager` go through `MessageClientSmaxWrapper`; every IQ carries `type`, `xmlns="w:interop"`, `to` = server JID, `id`.

| Operation | Type | Body | Limit | Result |
|-----------|------|------|-------|--------|
| FetchIntegrators | get | `<integrator fetch="all"/>` | - | 4.2 |
| FetchUsers | get | `<users><user external_id integrator_id/></users>` | **1-20 users** | 7.2 |
| SetOptInIntegrators | set | `<opt_in_integrators><integrator_list><integrator id/>` | 0-999 | 5.3 |
| GetReachabilitySettings | get | `<reachability_settings/>` | - | 6.3 |
| SetReachabilitySettings | set | `<reachability_settings enabled="true\|false"><integrator id/>...` | 0-999 | result / error |
| Block / unblock | set | `<blocklist><item action="block\|unblock" jid="{interop JID}"/></blocklist>` | - | result; errors `IQErrorBadRequest`, `IQErrorInternalServerError` |

### 6.1 Block and report (found)

Interop block uses `xmlns="w:interop"` (`C31106Dfy`, helper `C9EF`, log `InteropBlocklistHelper/getInteropBlocklist/error code:`) and table `wa_block_list_interop`. UI: "Blocked in third-party chats"; the block dialog says people blocked on WhatsApp may still reach the user in the third-party app. Report spam uses the generic spam flow (`spam_flow`, `C9E2`) with per-integrator dialog text. Notification routing: `AbstractC32331E9w` maps xmlns `w:interop` to handler id **270**; `EnumC32096E0u.NOTIFICATION_W_INTEROP` = `"w:interop"`.

### 6.2 Ping notification (found, anonymous `X.0xL` in `C1S0`)

`<notification xmlns="w:interop" t=".."><ping display_name=".."><X id=".." name=".."/></ping></notification>` (the tag `X` of the first child of `ping` is not checked by the code).

Only a first child named `ping` is accepted (else log `unknown tag=`). With `A02()` true it appends `id:name:display_name:t` to pref `interop_reach_notifs`, posts a local notification on channel `critical_app_alerts@1` (body "Chatting with people on third-party apps is an optional WhatsApp feature in the European Region.", action "Manage requests", dismiss receiver `InteropNotificationDismissReceiver`) and logs WAM 6684. Server trigger (someone from an integrator tried to reach the user) is inferred from the settings text "Get notified when someone wants to message you from a third-party app."

### 6.3 Reachability (found)

Settings are per **integrator** (children `<integrator id>`, bound 0-999), not per user. `enabled` default is `true` in `interop_reach_enabled`. No presence subscription code for interop JIDs was found (inferred: reachability replaces it).

---

## 7. User discovery

### 7.1 FetchUsers (found, `C31107Dfz` case 21, parser `C9EQ`)

Interop JIDs come only from this IQ; USync has no interop protocol (WA_USYNC.md).

```xml
<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><users>
  <user external_id="alice@example.org" integrator_id="12"/>          <!-- 1..20 -->
</users></iq>
<!-- result -->
<users>
  <user jid="12-105012705411308@interop" external_id=".." normalized_external_id=".." integrator_id="12"/>
  <user external_id=".." normalized_external_id=".." integrator_id="12"><error code="404" text="item-not-found"/></user>
</users>
```

Per-user outcomes: success `user[@jid]` (`C9DG`, jid parsed as `C99O`); `item-not-found` code default **404** (`C9DH`); `forbidden` default **403** (`C9DF`); `internal-server-error` (`C9DE`).

Whole-IQ errors: `bad-request`, `internal-server-error`. Result lists in `C9FA`: not found, forbidden, server error, resolved map `{(external_id, integrator) -> UserJid}`. Request and response both reject 0 or more than **20** users.

### 7.2 Identifier entry and saved contacts (found, `InteropComposeEnterInfoActivity`)

| Identifier type | UI | Value sent as `external_id` |
|-----------------|----|------------------------------|
| `USERNAME` | one field ("Enter Username") | text |
| `PHONE` | country picker + number | country code and number concatenated (per-character filter, rule not traced) |
| `EMAIL` | one field | text |

Flow: choose app (`InteropComposeSelectIntegratorActivity`, opted-in integrators from the table) -> chat type (`InteropSelectChatTypeActivity`: "New chat", "New group" if AB 15732 and integrator supports groups, "New contact" if AB 25512) -> enter id -> FetchUsers -> open chat on the returned JID. Strings: "This user can't be found" (not found), "This user is already a group member" (group add), "Couldn't create the chat. Please try again.".

With AB 25512, `ContactFormActivity.verifyInteropIdentifierAndSave` resolves the id through FetchUsers (`C24113Aau` case 41) and saves a `wa_address_book` row (raw_contact_id -5); "Usernames and contacts added to third-party chats will not save to your phone."

---

## 8. Messaging

### 8.1 Pipeline selection (found)

Decryption (`ENP.A00`): when AB **5760** is on and the chat JID satisfies `A0U` (interop 1:1 or interop group), ciphertext is handled by `C34471Exu` (`DecryptionCallbackInterop`); otherwise the regular callbacks run. Ciphertext types handled by `ENP` are the common ones: **0** (`msg`), **1** (`pkmsg`), **2** (`skmsg`, sender key), **4** (bot path, not interop). So interop uses the same Signal sessions and sender keys as native chats.

```
<message from="12-123[:0]@interop" ..><enc type=pkmsg|msg|skmsg v=2>...</enc></message>
   │  ENP.decryptMessage (Signal / sender key)
   ▼
C34471Exu.handlePlaintext
   │  remove padding (last byte = pad length; empty / zero / >= length fails, log DecryptUtil/removePadding)
   │  C33369Efy.A03(E0T.INTEROP_MESSAGE, ...)          ── message pipeline type "interop_message"
   ▼
C34720F4p (InteropChatMessageHandler)
   │  parse bytes as DTF (InteropMessage subset)
   │  unknown-field check -> failure 70
   │  C32718EOz.A00(EUQ) -> FMessage via type handlers; SKDM (group) processed if AB 38723
   ▼
store, receipt, notification
```

Failure reporting: `C34720F4p.A00` returns `C33063Eaz(reason)` and calls `A0Y(null, key, reason, 491)` on the receipt path; `C34471Exu` calls `C33369Efy.A07(.., 491, reason, ..)` for invalid plaintext. The literal **491** is common to both (meaning unresolved).

### 8.2 `InteropMessage` plaintext subset (found, `DTF`)

The plaintext is **not** the full `Message`. `DTF` declares exactly these fields, numbered like the full `Message`:

| Field | Number | Type | Handler | Notes |
|-------|--------|------|---------|-------|
| `conversation` | **1** | string | `FBN` | plain text |
| `senderKeyDistributionMessage` | **2** | message | `C34720F4p` | group id + axolotl SKDM; group id must equal the chat when the chat is a group |
| `imageMessage` | **3** | message | `FBK` | |
| `extendedTextMessage` | **6** | message | `FBN` | link preview fields |
| `documentMessage` | **7** | message | `FBI` | not when stanza `type` is `medianotify` |
| `audioMessage` | **8** | message | `FBH` | voice notes via `ptt` |
| `videoMessage` | **9** | message | `FBL` (no `gifPlayback`) / `FBJ` (`gifPlayback`) | |
| `reactionMessage` | **46** | message | `FBM` | |
| `ptvMessage` | **66** | message | none found | accepted by the schema and validated for unknown fields; no FMessage parser exists in the registry (video-note receive unresolved) |

The unknown-field check reads the unknown-field count by reflection from `DTF` and from the image, video, PTV, audio, document, extended text and reaction sub-messages; a count of 1 or more returns failure **70**. Fields outside `DTF` therefore fail the message: for example `messageContextInfo` (35), `protocolMessage` (12), sticker, contact, location, poll (inferred from the schema; the effect of a specific field was not exercised).

### 8.3 Supported message types and limits (found)

| Type | Rules enforced on receive (failure reason) |
|------|--------------------------------------------|
| Text, video | `conversation` or `extendedTextMessage.text`, truncated to **65536** chars; link preview only if `matchedText` is a valid URL contained in the text; title and description truncated to 65536; preview type mapped to 0, 1, 4, 5, 6, 7; video and GIF share the media parser `C33395EgO.A05` (`gifPlayback` picks `FBJ`) |
| Image | `mediaKey` required (16); `fileLength` >= 0 (13); `fileSha256` 32 bytes (14); `fileEncSha256` 32 bytes if set (14); mime **only `image/jpeg` or `image/png`** (17); `directPath`, width, height copied; thumbnail triple (direct path, sha, enc sha) optional; progressive scans accepted when 2-20 scan lengths and `scansSidecar` length / 10 equals the count and the sum fits an int |
| Audio | `mediaKey` required (16); `fileLength` > 0 (13); hashes 32 bytes (14); mime must be a known audio type (17); `ptt` flag; `waveform` kept only if 1-192 bytes; `backgroundArgb`; `seconds` |
| Document | `mediaKey` required (16); `fileLength` >= 0 (13); hashes 32 bytes (14); `title` truncated to 65536; JPEG thumbnail kept if it passes the size check |
| Reaction | `key.id` and `key.remoteJid` non-empty; `text` plus a non-zero edit version is rejected (warning `edit version and text message are both set`); `senderTimestampMs` kept; a stanza with `type="reaction"` must yield a reaction message (else failure **76**) |
| Reply / quote | `ContextInfo` with `stanzaId`, `participant`, quoted message (parsed as `DTF` again, `ContextInfoProtobufInterop`), `quotedType`; sender side `InteropContextInfoBuilder` serializes the quoted message recursively |

Not accepted (outside the 9 fields): stickers, contacts, locations, polls, events, templates, view-once. The attachment picker hides the contact, location, poll, event, group status, imagine, payment, pix and remittance entries for interop chats (checks `A0L`, `A0M`, `A0P`, `A0Q`, `A0R`, `A0T`, `A0U`, `A0X` of `ConversationAttachmentContentView`); document, camera, gallery and audio are not gated by interop checks (inferred to remain). Disappearing messages are not supported ("disappearing messages are not supported in third-party chats", also excluded from the default-timer setting). Media bytes travel through the normal WhatsApp media path (key, hashes and `directPath` in the message; download-origin analytics value 15 = `interop`).

### 8.4 Send side (found)

| Step | Behaviour |
|------|-----------|
| Serializer | `C33446EhE`: chat JID type 22/23 (`A0X`) uses the interop serializer (`C32718EOz.A01` with per-type `ADs`, logs `buildE2eInteropMessage`); other chats use the regular builder, so interop **groups** (type 28) take the regular builder |
| Unsupported FMessage class | handler `FBG` -> throws `E3G` 70 before send; wrong class for a handler -> `E3G` 0 |
| Image checks | mime `image/jpeg` or `image/png` else `E3G` 17 (`null` becomes `image/jpeg`); hash not 32 bytes `E3G` 14; missing media key `E3G` 16; stanza contributors `F6B`, `F6G`, `F6I`, `F68`, `F69`, `F6H`, `F6M`, `F6X` have no interop branch (attachment unresolved) |
| Encryptor (`F6P`) | for interop chats (`A0U`) the encryptor skips `C33284Eea.A02` (adds device list metadata through `AbstractC30999De0.A03`, inferred) and skips `paddingBytes` (size from AB 1723) |
| `<meta>` (`F6K`) | `content_type="add_on"` is skipped for interop chats |
| Reporting token (`F6L`) | skipped when the target is an interop device JID |
| Device list / ADV | interop device index is always 0; `DeviceADVInfoHandler` has an interop check at its entry (`C24230w2`, early exit inferred); no multi-device fan-out is possible (inferred: one device per contact) |

Further differences from native messages: interop chats use pipeline type `interop_message` (`E0T`) instead of text / media / reaction types; WAM chat-type value 5 in the decrypt event (`AbstractC33424Egr`) and 6 in the `FNR` event (native 3 / 1); message-secret add-ons (poll votes, encrypted reactions, see WA_MESSAGE_SECRETS.md) are not among the 9 fields, so they cannot reach interop chats (inferred).

---

## 9. Interop groups

### 9.1 Model (found)

A group is `{gid}@interop.g.us` (type 28). Members are WhatsApp accounts (added as **LID** user JIDs; found on the add path, create path inferred the same) and interop JIDs. Group metadata comes from MEX instead of `w:g2`: `C11410Yt.A0F` calls `GroupXmppMethods/sendGetInteropGroupInfo` for type 28. State is `UNSET`, `ACTIVE`, `SUSPENDED`; suspended gids are kept in pref `suspended_interop_groups`. Composer banners: suspended group "You can't send messages to this group because all third-party members have left."; opted out or removed "... because you're no longer a member."

### 9.2 MEX operations (found; doc ids from `assets/whatsapp-android-mex_client_persist_ids.json`)

| Operation | doc_id | Root field | Input | Output / notes |
|-----------|--------|-----------|-------|----------------|
| `GroupsCreateInteropGroup` | `25726817620301611` | `xwa2_interop_group_create` | `input.participants[{jid}]` | `group`: `gid`, `creation_time`, `creator_v2`, `display_name`, `participants_v2`; no subject sent |
| `LeaveInteropGroup` | `25346167795013271` | `xwa2_interop_group_leave` | `input.groups_to_leave[{gid}]` | per group `response_code`; {200, 400, 401, 403, 404, 405} treated as final |
| `AddParticipantsToInteropGroup` | `25732168276369451` | `xwa2_interop_add_participants_to_group` | `input.gid`, `input.participants[{jid}]` | WhatsApp members are mapped PN to LID first; `null` LID aborts the call |
| `QueryInteropGroupInfo` | `32734144032867938` | `xwa2_interop_group_query_by_id` | `group_input.gid` | `state`, `gid`, `creation_time`, `creator_v2`, `participants_v2` |
| `InteropPrivacySettingsQuery` | `24849123668112654` | `xwa2_fetch_wa_users` -> `interop_privacy_settings` | `interop_privacy_settings_query_input{feature, dhash}` for the own LID | `settings_data`, `dhash`, `denied_contacts[{jid}]` |
| `InteropPrivacySettingsUpdate` | `25421856497452763` | `xwa2_interop_privacy_setting_update` | `feature`, `setting` | `success` |
| `InteropPrivacySettingWithContactListUpdate` | `24913399124998598` | `xwa2_interop_privacy_setting_with_contact_list_update` | `contact_list_type`, `contacts`, `dhash` (`none` if absent), `feature`, `setting` | `success` |

Create and add errors surface as "This group couldn't be created" / "Make sure everyone you add to this group has third-party chats turned on." / "A group with these members already exists." (found strings). Creating a group requires at least one user of the chosen integrator ("To create this third-party group, you need to select at least one %1$s user.").

### 9.3 MEX notifications (found, `C0WQ`)

| Notification | Handler | Effect |
|--------------|---------|--------|
| `NotificationInteropGroupCreateUpdate` | `AbstractC23194A0r` branch (log `CreateInteropGroupNotificationHandler/`) | creates the local group from `gid`, creator and participants |
| `NotificationInteropGroupParticipantsUpdate` (`Xwa2NotifyInteropGroupOnParticipantChange`) | `A0B` | adds participants with source `general_chat_auto_add`, removes left participants; returns early (`no updates needed to gid=`) when `C22300su.A15()` is false |
| `NotificationInteropGroupPropertyUpdate` | `A0C` | `state` ACTIVE or SUSPENDED -> `suspended_interop_groups` |

### 9.4 Who can add me (found, feature `GROUPADD`)

`C9U8` setting enum: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `MYCONTACTS`, `MYCONTACTSEXCEPT`, `MYCONTACTS_AND_ENABLED_INTEROP_INTEGRATORS`, `NONE`. The contact-list variant carries the deny list (`contact_list_type`, `contacts`). Text: "You can only be added to third-party chats by people who either use or have selected the same messaging app." The setting is stored per own LID and cached with `dhash`; enforcement is server-side (inferred), the client only presents the setting.

---

## 10. Chat list, thread model, UI

| Item | Fact (found) |
|------|--------------|
| Thread | one chat per interop JID (1:1) or per gid; stored in the normal chat tables; no separate thread table |
| Folder | `InteropConversationsActivity` / `Fragment`; header view `InteropView` in the chat list (`C31071Ju`, log `ChatListInteropChatsDelegate/`); shown when eligible and notice accepted, or when interop chats already exist; hidden when the inbox is COMBINED |
| Inbox mode | SEPARATED: folder inside the main inbox or the "More" menu; COMBINED: interop chats listed in the Chats tab (filter chip `interop` in the chat filters, `THIRD_PARTY_FILTER`) |
| Row / search | integrator name label and icon badge on the avatar; third-party chats are not included in search results |
| Banner / badge | "You're messaging someone outside of WhatsApp. Third-party apps may have different security."; Home badge from `pref_interop_badge_*`, gated by AB 7495 (`C230679y0`) |

---

## 11. Baileys (`baron-baileys-v2` 1.5.17, `src/Socket/interop.js`, `WABinary/decode.js`, source read, nothing tested)

| Topic | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| Integrators | hard-coded `12` (BirdyChat, email) and `13` (Haiket, pn) | none in the client; server list |
| Batch lookup | `INTEROP_BATCH_MAX = 256` | **20** (request builder and response parser) |
| Opt-out | `<opt_out_integrators><integrator_list>` | no such node; opt-in IQ with a shorter list |
| Reachability set | `<reachability_settings enabled><user external_id integrator_id/>` | `<integrator id/>` children |
| Consent | `tos` IQ `trackable id=20240306 result=105`, then `160` | notice 20240306 stage 160 = accepted (found); wire form of the notice IQ not traced |
| Binary JID | tuple 244 reader throws unless domain = 0; tag 245 handled | tag 244 with domain 0 **and** 2 (groups); no tag 245 |
| Notifications | `type="interop"` with `stella_interop_enabled`, `peer_device_presence`, `ig_profile`, fbid | `w:interop` handler id 270 handles only `ping` |
| Send / receive | plain text as `conversation`, reporting token skipped; comment in `Defaults/index.js`: interop receive not implemented | serializer restricted to the 9 fields; strict `InteropMessage` parser; group MEX ids and notifications identical in scope |

Why it fails (inferred from the code compared above):

| Symptom | Cause | Fix |
|---------|-------|-----|
| Decode error on interop group JID | tuple reader rejects domain byte 2 | accept domain 2 -> `{gid}@interop.g.us`, require device and integrator 0 |
| Peer drops the message with an unknown-field failure | any field outside the 9 (for example `messageContextInfo` with a `messageSecret`, `protocolMessage`) fails if the peer runs the same strict parse (inferred; Baileys interop sends were not traced for these fields) | build `Message` with only fields 1, 2, 3, 6, 7, 8, 9, 46 (and 66) |
| Opt-out has no effect | `opt_out_integrators` does not exist in the client | send SetOptInIntegrators with the remaining ids |
| Nothing arrives on companion sessions | interop contacts have device 0 only | keep interop on the primary session |

---

## 12. Error cases

| Symptom | Cause | Where |
|---------|-------|-------|
| Interop screens close immediately or never appear | `C32001Oa.A02()` false: flag 7495 off, dependent account, or companion device | 2.1 |
| "Apps can't be saved right now" | SetOptInIntegrators failure; codes 500 / 810 / 800 get the "try again later" text | 5.3 |
| "This user can't be found" | FetchUsers `item-not-found` (404) | 7.1 |
| Invalid interop JID exception | integrator not 1-3 digits / leading 0, account not 1-15 digits, device index not 0 | 3.1 |
| Group not created / composer disabled | MEX create error or duplicate member set / opted out, group suspended, no longer a member | 9.1, 9.2 |
| Incoming message dropped, reason 70 / 13 / 14 / 16 / 17 / 76 / 26 | unknown field or type without handler / bad size / bad hash length / missing media key / invalid mime / reaction type mismatch / parse exception | 8.2, 8.3 |
| Group SKDM ignored | AB 38723 off (log `sender key distribution message skipped`) | 8.1 |
| Integrator names missing after a send error | ack error wiped `integrator_display_name` | 4.2 |

---

## 13. Key distinctions

| Do not confuse | Fact |
|----------------|------|
| `w:interop` vs USync | contact discovery is FetchUsers on `w:interop` (max 20), not a USync protocol |
| `@interop` / `@interop.g.us` / `@g.us` | user and device, group, native group; an interop JID is never mapped to LID or PN |
| `InteropMessage` vs `Message` | receive accepts 9 fields; send omits context and padding for interop |
| `trusted_contact` privacy token | generic privacy-token job (WA_TCTOKEN_CSTOKEN.md); no interop-specific code was found in this build |
| UPI "interop" | `IndiaUpiInterOpHybridActivity`, `IndiaUpiInteropSendToUpiActivity`, `isInterop` payment note flags are payments features, unrelated |
| Compose / EXIF "interop" | `androidx.compose.ui.viewinterop`, `InteroperabilityIFDPointer` are libraries |
| Eligible vs opted in vs consent | flag 7495 = eligible; `opted_in` per integrator comes from the server; consent = notice 20240306 stage 160 |

---

## 14. Complete flow

```
[User]              [Client]                                   [WA server]              [Integrator app]
  │ Settings > Third-party chats
  ├──────────────────► A02(): flag 7495, primary, not dependent
  │                    notice 20240306 != 160 ──► show ──► accept ──► stage 160
  │ apps (+ inbox type, + group privacy)
  ├──────────────────► SetOptInIntegrators ─────────────────► opted_in list; table rewritten
  │ New chat > app > id
  ├──────────────────► FetchUsers (1..20) ──────────────────► jid 12-<account>@interop / 404 / 403 / 500
  │ send text / image / video / audio / doc / reaction
  ├──────────────────► restricted Message (no context, no padding), Signal encrypt, device 0
  │                    <message to=..@interop> ─────────────► bridge (inferred) ───► [Integrator app]
  │                    <message from=..@interop><enc/> ◄──────────────────────────── reply
  │                    ENP -> DecryptionCallbackInterop -> DTF parse (unknown field -> 70) -> FBx -> FMessage
  │ ◄──────────────── chat row, notification
  │                    <notification xmlns=w:interop><ping/> ◄─ server (trigger inferred)
  │ ◄──────────────── local notification "Manage requests"; reachability per integrator
  │ New group (flag 15732)
  ├──────────────────► GroupsCreateInteropGroup (LID + interop JIDs) ──► gid@interop.g.us
  │                    MEX notifications: create / participants / property; SUSPENDED -> composer blocked
```

---

## 15. Unknowns

| Topic | State |
|-------|-------|
| Wire form of the consent notice IQ | not traced; only stages 160 (accepted) and 162 (written by the migrator) are known |
| Server-side bridge, delivery to the integrator, key handling on that side | not visible in the client; the client uses ordinary Signal sessions and sender keys |
| Identity change / safety number for interop contacts | not traced |
| Calls, polls, edits, revokes, identity change / safety number for interop chats | no interop code path found (no interop string in call code); not traced |
| PTV (`ptvMessage`) receive | field accepted, no parser found |
| Literal 491 in the failure path; error codes 810 / 800; FetchIntegrators triggers other than the opt-in screen | unresolved |
| Readers of flags 3953, 5759, 6613, 18670, 20999, 11518, 13532, 14070 | no literal reader; may be read through descriptors |
| Read receipts toward interop contacts | `ClientPayload.interopData` (field **38**, `C38671hT`: `accountId` 1, `token` 2, `enableReadReceipts` 3) exists in the schema; nothing in this build populates it |
| Whether the server enforces the European Region rule | UI text only; no client check |
