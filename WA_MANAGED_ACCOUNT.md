# WhatsApp Managed Account — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** the client-visible "managed account" parental-supervision system (sponsor/dependent linking, roles, age experience, PIN, privacy settings, unlink, w:mex operations, local storage, feature flags); the separate, unrelated signal set for business numbers operated by a Business Solution Provider over the Cloud API (verified-name certificate issuer, host-storage/actual-actors fields, coexistence UI, hosted multi-device account type); how the two are told apart

---

## 1. What "managed" means in this client

Two unrelated systems in 2.26.41.6 use language an outside reader would call "managed account." They share no code, no proto, no w:mex schema. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tier: **found** = read in code or assets, **inferred** = deduced from code, **unknown** = not resolved.

| System | Internal name(s) in code | What is "managed" | Where | Section |
|---|---|---|---|---|
| Parental supervision | `com.whatsapp.managedaccount.*`, `com.whatsapp.pma.*`, `com.whatsapp.pmta.*`; internal codenames **PAA**, **PMA**, **PMTA** (found in package/class/pref names, never expanded in strings) | a minor's ("dependent") own WhatsApp account, supervised by a parent/guardian ("sponsor") account | `w:mex`, local SQLite/SharedPrefs | 2-8 |
| Business-number delegation to a provider | no "BSP" or "tech provider" string anywhere in the client; the UI calls it "a secure service from Meta" or "other companies" | a **business's** WhatsApp number, whose messages are hosted/handled by Meta's cloud infrastructure and/or a third-party provider instead of the business's own device | verified-name certificate (`w:biz`), multi-device "hosted" account type | 9 |

The string resources `str2fc9`/`str3139` ("Managed account"), `str30ae`, `str3109`, `str439d`/`str439f` and the settings screen they belong to are **all** the parental system (section 2). There is no "Managed account" label anywhere in the client for a business run by a BSP; that case is signalled purely through certificate fields and chat/call banners (section 9). This is the key correction to make before using the term: a reverse-engineering note or ticket that says "managed account" about a *business* number is talking about section 9, not about anything named `ManagedAccount*` in code.

---

## 2. Parental supervision: roles and account relationship

### 2.1 Roles

`EnumC08540Ng` (found), with a debug label per constant:

| Role | Debug label | Who |
|---|---|---|
| `NONE` | "None" | no supervision relationship |
| `DEPENDENT` | "Dependent" | the minor's own account |
| `SPONSOR` | "Sponsor" | the parent/guardian account |
| `SPONSOR_ADMIN` | "Sponsor Admin" | a sponsor with elevated rights (exact extra rights not traced) |

The current device's role is read from local state by `SharedPreferencesOnSharedPreferenceChangeListenerC08490Nb.A04()` and cached by `C08530Nf` ("ManagedAccountStartupPreferences", name inferred from its log tag `ManagedAccountStartupPreferences/...`).

### 2.2 The relationship is account-to-account, not device-to-device

The dependent has its **own phone number and its own full WhatsApp registration** (its own primary device, its own multi-device companions if any). The sponsor likewise is a normal, independently registered account. What links them is a server-side record, mirrored locally as:

```
ManagedAccountConnection(
  connectionLid,      // C14080dr — the dependent's LID, found
  role,                // EnumC08540Ng, found
  linkTs,              // long, link creation time, found
  connectionPnJid,     // PhoneUserJid — the dependent's phone-number JID, found
  graduationState,      // C4DV, section 2.3
  ageExperience)        // EnumC96934Gf, section 2.3
```

(`AnonymousClass586`, found; fields confirmed by its `toString`.) There is no pairing QR, no ADV signature, no companion key exchange anywhere in this package — compare the actual companion-device protocol in `WA_LINKED_DEVICE_PAIRING.md` section 5, which is unrelated. The onboarding entry point is a deep link handled by `ManagedAccountSponsorOnboardingViewModel` (package `managedaccount.deeplink`, found), not a scan-based flow.

### 2.3 Age experience and graduation

`EnumC96934Gf` (found): `UNKNOWN`, `U13`, `U16_BR`, `U18_BR`, `U18`, `STANDARD` (Brazil has its own age bands). `A00()` on this enum returns true for `U16_BR`, `U18_BR`, `U18` — the states the code treats as "about to age out."

`C4DV` (graduation state, found): `PRE_GRADUATION`, `GRADUATION`, `PRE_GRADUATION_IMMINENT`, `UNKNOWN`. `ManagedAccountGraduationManager` and its `triggerTeenGraduationEagerly` path (found) move a dependent out of supervision as it approaches/crosses an age threshold; `ManagedAccountPmtaSponsorGraduationNuxActivity` and `ManagedAccountSponsorGraduationNuxActivity` show the sponsor-side NUX for this transition.

`ManagedAccountLinkingRepository.A00` (found) refetches the age experience on an HTTP 409 conflict from the linking call, i.e. the server can reject linking because the stored age experience is stale and the client must re-query `WaAgeExperienceRepository` before retrying.

---

## 3. Linking flow and w:mex operations

### 3.1 Operation catalog

All nine operation names and `doc_id` values below were read directly from `assets/whatsapp-android-mex_client_persist_ids.json` in this build (found) — not inferred from a third-party client. Schema for all nine is `whatsapp-android-mex` (asset key: `whatsapp_mex`).

| Operation | doc_id | Call site found | Variables (this build) |
|---|---|---|---|
| `ManagedAccountInitiateLinkingQuery` | `26671873552498548` | `MexManagedAccountInitiateLinkingApi.A00` | `input:{"dummy": null}` — **no `phone_number`** is sent; a prior assumption that this call carries the dependent's number does not hold for this call site |
| `ManagedAccountQuery` | `27232244463035262` | `ManagedAccountStateSynchronizer.A01` | `input:{"unused": null}` — **no `jid`**; the query is session-bound, not parameterised by JID at this call site |
| `ManagedAccountValidateLinkingQuery` | `35449808311284430` | referenced (name match in assets); variables not traced to a call site in this build | unknown |
| `ManagedAccountAcceptLinkingMutation` | `26708926155457677` | referenced; variables not traced | unknown |
| `ManagedAccountCompleteLinkingMutation` | `26866501363013203` | referenced; variables not traced | unknown |
| `ManagedAccountRevokeLinkingMutation` | `27435058196100677` | referenced; variables not traced | unknown |
| `ManagedAccountSyncActivities` | `26594352680227840` | referenced; variables not traced | unknown |
| `ManagedAccountUpdatePinMutation` | `27653949584193082` | referenced; variables not traced | unknown |
| `ManagedAccountGetSponsorAgeVerificationInfoQuery` | `26433623289634522` | referenced; variables not traced | unknown |

Response bodies beyond generic success/error wrappers were not read for any of the nine; `ManagedAccountInitiateLinkingQuery`'s success result (`C135065o7`, `toString()` literally `"PAA Initiate Linking Success"`, found) carries two strings and an int whose field names are not resolved — almost certainly a linking token/deep-link URL and an expiry, but that is inferred, not read from a named field.

A separate, non-mex path exists: `C14E.java` (`PaaAcceptLinkingIBHandler`) parses an inbound stanza/notification carrying a `sponsor_jid` attribute (found) — this is a server push that prompts the UI, not the `AcceptLinkingMutation`'s own request.

### 3.2 Delivery-failure retry

`MexManagedAccountInitiateLinkingApi.A01` retries the initiate call up to a caller-supplied count on error code **471** ("delivery failure"), logging `MexManagedAccountInitiateLinkingApi/requestSponsorLinkingMaterial delivery failure, retrying` (found).

---

## 4. Device/session model

There is **no companion-style device link** between sponsor and dependent, and none between either account and any WhatsApp-operated infrastructure. Each side is an ordinary, independently registered WhatsApp account (own phone number, own primary device, own optional linked devices under the normal multi-device system described in `WA_LINKED_DEVICE_PAIRING.md`). The supervision relationship is a server-side record keyed by the dependent's LID and phone-number JID (section 2.2), synchronized to both sides over `w:mex`, not a new session, pairing, or ADV identity.

This is a structural difference from the BSP/Cloud-API case in section 9, where the business number's "device" is not a phone at all — see section 9.3 for how that is represented in the existing multi-device model instead.

---

## 5. Settings and permissions

### 5.1 Dependent-side privacy screen

`DependentAccountPrivacyActivity` (found) groups settings into three sections via enum `C9SE`:

| Section | `C9SE` constant | Content |
|---|---|---|
| Visibility | `VISIBILITY` (0) | who can see the dependent's profile info |
| Contact | `CONTACT` (1) | who can contact the dependent |
| Sponsor control | `SPONSOR_CONTROL` (2) | settings the sponsor, not the dependent, controls |

The screen links out to "parental controls" via string `str2fc8`: *"Your account is managed by your parent or guardian. They can make changes in parental controls."* A local pref gate exists for one such control: `privacy_dependent_account_messages` (int, default `1`), read by `C08520Ne.A06()` and only consulted when the account is a sponsor (found) — i.e. who may message the dependent is something the **sponsor's** app state gates, not a value the dependent sets.

### 5.2 Sponsor-side controls

`SponsorControlsHubActivity` (found) is the sponsor's hub, listing dependents (fragment/log tag `"sponsor-controls-dependents"`) with a contact-photo adapter per dependent. `SponsorControlsDependentInfoActivity` opens one dependent's detail. `ManageNotificationsActivity` / `ManageNotificationsFragment` and `ActivityAlertsFragment` / `ManagedAccountDependentActivityAlertHandler` configure and deliver **activity alerts** — notifications to the sponsor about the dependent's app activity (`ManagedAccountSyncActivities`, section 3.1, is the data source, gated by flag **31562** in `ManagedAccountAlertInfoActivity`, found).

### 5.3 PIN

`SponsorPinSetupFragment`, `SponsorPinConfirmFragment`, `ManagedAccountChangePinActivity`/`ManagedAccountChangePinFragment`/`ManagedAccountConfirmChangePinFragment` (found, by class presence) implement sponsor-set PIN creation and change; the mutation is `ManagedAccountUpdatePinMutation` (section 3.1; exact `old_pin`/`new_pin` field names not confirmed in this build — unknown). A dependent-side sync can fail specifically for a missing PIN: `ManagedAccountStateSynchronizer` logs `"ManagedAccountStateSynchronizer/fetchAndSync missing sponsor PIN for child user"` and returns an error result when the server/response type is `C135095oA` (found) — the dependent's state sync depends on the sponsor's PIN being set.

### 5.4 Unlink

`ManagedAccountUnlinkAccountSettingsActivity` (found) shows one of several confirmation texts depending on flags carried in the fragment arguments: `is_pmta` (a distinct "PMTA" sub-variant), `is_teen_dependent`, and whether the dependent has a push name — strings `str49cb`…`str49d3`, e.g. *"Your account will no longer be managed by %1$s"* / *"...by your parent"*. `ManagedAccountRevokeLinkingMutation` (section 3.1) is the wire operation inferred to back this action; the activity itself was not traced calling it directly in this pass.

### 5.5 Reauthentication gate

`ManagedAccountAuthInterstitialActivity` hosts `PmaAuthInterstitialFragment` (package `com.whatsapp.pma.product.dependent.fragments`, found) and is launched with an `extra_auth_entry_point` string — a re-authentication step gating entry into managed-account screens from a given entry point. The exact auth mechanism (device PIN, biometric, account password) was not traced.

### 5.6 Debug surfaces

`ManagedAccountDebugConnectionActivity` and `ManagedAccountDebugPinAuthActivity` exist in this build (found). Nothing in this pass establishes whether they are reachable from release UI or only from an internal/debug build flag (inferred: debug-only, by naming convention and lack of any discovered launch path from production screens).

---

## 6. Storage

| Store | Keys / columns | Content |
|---|---|---|
| Local relationship record | `connectionLid`, `role`, `linkTs`, `connectionPnJid`, `graduationState`, `ageExperience` (section 2.2) | one row per sponsor↔dependent connection |
| SharedPrefs | `paa_graduation_nux_pending`, `paa_sponsor_blocked`, `paa_nux_education_banner_dismissed`, `paa_nux_education_banner_start_timestamp`, `paa_review_privacy_settings_banner_dismissed_dependent_<lid>`, `privacy_dependent_account_messages` | NUX/banner dismissal state, sponsor-blocked flag, the one confirmed dependent-messaging gate |

All keys found verbatim in `C08530Nf`, `ManagedAccountBannerManager`, `C08520Ne`.

---

## 7. UI indicator strings

| String id | Text | Where used |
|---|---|---|
| `str2629` | "Create a parent-managed account" | onboarding entry |
| `str2fc9` / `str3139` | "Managed account" | badge/label |
| `str30ae` | "Managed accounts can't see this message. Learn why" | restricted content |
| `str3109` | "This is a managed account. Learn more" | chat/profile notice |
| `str3751` / `str3752` / `str3754` | ineligibility messages ("isn't eligible for a parent-managed account", "Couldn't create parent-managed account") | onboarding failure |
| `str439d` / `str439f` | "Settings for managed accounts" / "View activity and choose settings for managed accounts" | settings entry point |
| `str2fc8` | "Your account is managed by your parent or guardian..." | `DependentAccountPrivacyActivity` |
| `str49cb`-`str49d3` | unlink confirmation variants | `ManagedAccountUnlinkAccountSettingsActivity` |

`ManagedAccountNotAvailableActivity` and `ManagedAccountAgeUnknownActivity` (found by class name) back two more states — the feature not being offered, and the account's age being undetermined — exact copy not resolved.

---

## 8. Feature flags

| ID | Where | Controls |
|---|---|---|
| **30174** | `C08520Ne.A02`, `ManagedAccountSponsorUpsellActivity` | sponsor-upsell eligibility |
| **31562** | `ManagedAccountAlertInfoActivity` | activity-alerts feature gate |
| **34268** | `C08520Ne.A01` | an additional permission check (role unresolved beyond the gate itself) |
| **16763** | `C08520Ne.A04` | unresolved boolean gate |
| **33355** | `C08520Ne.A05` | unresolved boolean gate, conditioned on dependent or a secondary interface |

---

## 9. Business numbers delegated to a provider (Cloud API / BSP)

This is the system that actually corresponds to "a business account operated on-behalf-of by a provider." It shares no class, proto, or w:mex schema with section 2-8. No string in this build says "BSP," "tech provider," "Business Solution Provider," "on-premises API," or "Cloud API" to the user; the signal is structural.

### 9.1 Verified-name certificate: issuer prefix and `PrivacyMode`

The client stores a local verified-name certificate record per business JID with columns (found, `AbstractC218419al`): `verified_name`, `industry`, `city`, `country`, `verified_level`, `cert_blob`, `identity_unconfirmed_since`, `host_storage`, `actual_actors`, `privacy_mode_ts`. These three last fields are parsed off a `w:biz` stanza's `<biz host_storage="" actual_actors="" privacy_mode_ts=""/>`-style child (found, multiple call sites, e.g. `O0F.java`, `C18670m9.java`, `AbstractC24816AmW.java`) into `AnonymousClass118` ("`PrivacyMode`" per its own `toString()`), whose two integer fields are:

| Field | Values seen in code | Meaning |
|---|---|---|
| `hostStorage` | 0 (default/unset), 1, 2 | which infrastructure stores/relays the business's messages; **inferred** mapping to the public WhatsApp Business Platform terms on-premises (self-hosted) vs. Meta-hosted (Cloud API) vs. a third, dual/transitional state — the client has no named constants for these three values |
| `actualActors` | 0 (default/unset), 1, 2 | who actually operates the account day to day; **inferred** mapping to self-operated vs. operated by a provider — again no named constants in this client |

A second, independently found signal on the same certificate wrapper (`AnonymousClass119.A02()`/`A03()`) reads the certificate's **issuer string** (field `A07`) and classifies it by prefix (found, exact code):

```java
public boolean A01() { return this.A01 == 2; }        // hostStorage == 2
public boolean A02() { return this.A07 != null && this.A07.startsWith("ent:"); }
public boolean A03() { return this.A07 != null && this.A07.startsWith("smb:"); }
```

`"ent:"` and `"smb:"` are the two issuer prefixes this client distinguishes (found, literal strings). `smb:` matches a certificate issued for the regular, self-operated WhatsApp Business app; `ent:` matches a certificate issued for an enterprise/API-integrated path — this is the closest first-party, code-level equivalent of "self-managed business account" vs. "BSP/Cloud-API-managed business account" (mapping of the prefixes to those two real-world categories is **inferred** from the prefixes themselves and from how they are consumed in `AbstractC198638cc.A00`, not from any in-client documentation string).

`AbstractC198638cc.A00` folds the issuer check and a separate boolean (`A09`, meaning unresolved — possibly "certificate missing/revoked", consistent with the user-facing "no longer an official business account" copy in section 9.2) into a 4-valued "client" code (found):

```java
public static final int A00(AnonymousClass119 c) {
    if (c != null) {
        if (c.A09) return 4;
        if (c.A03()) return 2;   // smb: issuer
        if (c.A02()) return 3;   // ent: issuer
    }
    return 1;                    // default / no certificate
}
```

### 9.2 Coexistence banners and `business_state_id`

`C198628cb` ("`BusinessState`" per its `toString()`) combines the certificate's `PrivacyMode` (9.1), the 4-valued "client" code, and an `isVerified` boolean into one flattened integer the UI calls `business_state_id` (found, set from `c198628cb.A02()` in `EncryptionChangeDialogFragment` and read the same way in `PrivacyInfoBottomSheet`/`ContactInfoActivity`). The mapping function pattern-matches 18 explicit `(client, actualActors, hostStorage, flag)` tuples to the ids **0-17**; the full table could not be reconstructed (JADX reports a region-overflow error on this specific method, and several branches are merged by the decompiler), but the following is established directly from the code:

- id **15** is reached whenever the "client" code equals 4 (certificate missing/revoked), regardless of the other fields.
- ids **5, 6, 9, 10** are the only ids reachable when a side-gate method `A05()` (an unrelated block/mute-style check on the chat) is true, and are also reachable through the normal path when `hostStorage == 2` — these consistently drive the plain *"This business uses a secure service from Meta to manage this chat/call"* strings (`str080d`/`str080f`/`str0c9c`/`str0f5a`, found, resource-id-verified call sites in `C23324A5w`/`ContactInfoActivity`).
- ids **16** and **17** are the residual cases (neither a known tuple nor id 15) and drive the "multiple tools" / "no longer an official business account" family of strings (`str38ef`-`str38fb`, `str08b3`-`str08c7`): *"This business has chosen to use multiple tools to chat with its customers... Chats between only you and this business are managed by a secure service from Meta... this business is using the WhatsApp Business app"* — i.e. the **coexistence** state, where the number is reachable both through the Business app on a device and through an API-hosted path at once, gated by flags **12729**, **18047**, **23933**, **7131**, **29343** (found, in `PrivacyInfoBottomSheet`/`ContactInfoActivity`, each selecting between an older and a newer string pair for the same state).

The `remove-companion-device` IQ result in the unrelated multi-device flow can carry a `coex_token` child (`WA_LINKED_DEVICE_PAIRING.md` §7.1) — same "coexistence" concept, consumer not traced from that side either.

### 9.3 Device/session model for a provider-hosted number

A business number fully hosted by Meta (the Cloud API case with no physical device at all) is represented inside the **existing** multi-device system, not a new one:

- account type `HOSTED` (`EnumC32116E1o`, value 1) and device id **99** are reserved for this case (`WA_LINKED_DEVICE_PAIRING.md` §5.1, §9.2).
- the `companion-props.platformType` enumeration that the primary stores for its own linked devices includes the value **23 = `CLOUD_API`** (`WA_LINKED_DEVICE_PAIRING.md` §6.2), alongside **27 = `BUSINESS_BACK_OFFICE`** and **25/26 = `WAIL`/`WASS`** — all business-infrastructure platform types sitting in the same enum as ordinary phones/desktops/web.
- the consumer build in this report actively **refuses** to pair a hosted device from the primary side (local error code **-10**, `WA_LINKED_DEVICE_PAIRING.md` §3.2) — hosted/Cloud-API provisioning is not something this client initiates; it only ever observes the resulting account type and platform markers on accounts that already have it.

No pairing, ADV signature, or companion-key flow for the BSP/Cloud-API relationship itself was found anywhere in this APK; account security's canonical-user/password machinery (`WA_ACCOUNT_SECURITY.md`) and the multi-device identity machinery are both unrelated to how a BSP comes to operate a number — that provisioning happens entirely server-side / on Meta's business platform and leaves no trace in this client beyond the markers above.

### 9.4 Telemetry

The `wam_ts_navigation` logging event (`C1EO`, found) carries three independent business-context booleans per logged navigation: `is_cloudapi`, `is_onpremises`, `is_smb`, plus `is_canonical_ent_present` and `is_meta_ai_thread`. `ChatDescription` (`com.whatsapp.gapenforcement.dto`) separately carries `isEnterpriseBusiness`. Neither class exposes how these booleans are computed beyond what section 9.1/9.2 already describes; they are reporting-only and do not gate any user-visible behaviour in the files read.

---

## 10. Key distinctions

| A | B |
|---|---|
| "Managed account" (`ManagedAccount*`, PAA/PMA/PMTA) — a **minor's own account**, supervised by a parent | a business number **operated by a provider** over Cloud API — no "managed account" string anywhere for this case |
| Sponsor/dependent link: two independent, normally-registered WhatsApp accounts, no device pairing | hosted business number: one account, `accountType=HOSTED`, device id 99, no companion device at all |
| `w:mex` `ManagedAccount*` operations, schema `whatsapp-android-mex` (section 3.1) | verified-name certificate fields over `w:biz` (`host_storage`, `actual_actors`) — different stanza, different schema |
| `business_state_id` coexistence banners (self-managed Business app **and** API-hosted at once) | a purely self-managed business (regular WhatsApp Business app on its own device, issuer prefix `smb:`) |
| `is_smb` telemetry flag (small/medium business using the Business app) | `is_cloudapi` / `is_onpremises` telemetry flags (API-side hosting) |
| `ManagedAccountRevokeLinkingMutation` (ends parental supervision) | `remove-companion-device` (unrelated: removes a linked device; see `WA_LINKED_DEVICE_PAIRING.md` §7) |

---

## 11. Complete flows

### 11.1 Parental supervision: linking a dependent

```
[Sponsor]                                  [Server]                         [Dependent]
   │ deep link / in-app entry                  │                                 │
   ▼                                            │                                 │
ManagedAccountInitiateLinkingQuery (no vars) ──►│
   │◄── linking material (token/URL, expiry)    │
   │  share with dependent (deep link / code)   │
   │                                            │                                 │
   │                                            │◄── dependent opens link ───────│
   │                                            │   ManagedAccountValidateLinkingQuery {linking_token, sponsor_jid} (assets; call site not traced)
   │                                            │   ManagedAccountAcceptLinkingMutation {linking_token} (assets; call site not traced)
   │◄── notification: sponsor_jid (PaaAcceptLinkingIBHandler) ────────────────────│
   │                                            │   ManagedAccountCompleteLinkingMutation {linking_token} (assets; call site not traced)
   ▼                                            │                                 ▼
local ManagedAccountConnection row created on both sides (role=SPONSOR / DEPENDENT, connectionLid, connectionPnJid, linkTs)
   │                                            │                                 │
   ▼                                            │                                 ▼
periodic ManagedAccountQuery (no vars) + ManagedAccountSyncActivities ──────────► sponsor controls hub / activity alerts
```

### 11.2 Business number delegated to a provider: what the peer's client sees

```
[Peer opens a chat/profile/call with the business number]
   │
   ▼
local verified-name cert for that JID: host_storage, actual_actors, privacy_mode_ts, issuer (smb:/ent:)
   │
   ▼
C198628cb.A02() → business_state_id (0-17)
   │
   ├─ id 15 (certificate missing/revoked)          → "no longer an official business account" (str08b3 family)
   ├─ ids 5/6/9/10 (hostStorage==2, or chat-gated)  → "uses a secure service from Meta to manage this chat/call" (str080d/f family)
   └─ ids 16/17 (coexistence residual states)       → "uses multiple tools... Business app AND a secure service from Meta" (str38ef-fb family)
```

---

## 12. Unknowns

| Topic | Reason |
|---|---|
| Full tuple→`business_state_id` table (all 18 values) | decompiler region-overflow on `C198628cb.A02()`; several branches merged |
| Exact numeric meaning of `hostStorage`/`actualActors` beyond the `smb:`/`ent:` issuer-prefix proxy | no named constants in this client; mapping to on-premises/Cloud-API/BSP terms is inferred from public Business Platform terminology, not read from code |
| Variables/response fields of `ManagedAccountValidateLinkingQuery`, `AcceptLinkingMutation`, `CompleteLinkingMutation`, `RevokeLinkingMutation`, `SyncActivities`, `UpdatePinMutation`, `GetSponsorAgeVerificationInfoQuery` | doc_ids confirmed in assets; no call site with variable names found in this build |
| Meaning of `A09` boolean feeding "client" code 4 | consumed only as a gate; no name or comment |
| Extra rights of `SPONSOR_ADMIN` vs `SPONSOR` | role exists; differentiated behaviour not traced |
| Expansion of codenames PAA / PMA / PMTA | never spelled out in strings or comments; usage context only |
| Reachability of `ManagedAccountDebugConnectionActivity`/`DebugPinAuthActivity` from release builds | naming suggests debug-only; no launch path found either way |
| Server-side provisioning of a Cloud-API-hosted number (section 9.3) | entirely server-side; this client never initiates it and only observes resulting markers |
| Whether any client code can distinguish "operated by Meta directly" from "operated by a third-party BSP via Meta's Cloud API" | both appear to collapse into the same `hostStorage`/`actualActors`/platform-type signals; no separate BSP identifier field was found |
| Actual traffic | static analysis only |
