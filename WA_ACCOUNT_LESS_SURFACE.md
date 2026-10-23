# WhatsApp Account-less Surface — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** what the Android client exposes with no registered account or before registration completes — manifest exports (activities, aliases, services, receivers, providers), pre-registration screens and registration-state routing, deep links and web links, unauthenticated HTTP and Graph endpoints, compiled-in host table, logged-out support form, ban status and appeal entry points, identifiers sent before login, third-party IPC surfaces, what stays unknown

---

## 1. What "account-less" means in this build

There is no single "logged-out mode". Several independent paths run while the client holds no user JID, no authenticated chat session, or an unfinished registration. Each path substitutes a different credential for the account. All statements are static analysis of the decompiled APK (`versionCode 264100600`, target SDK 36, min SDK 23). Nothing was observed on the wire. Tiers: **found** = read in code or manifest, **inferred** = deduced from code, **unknown** = not resolvable statically. Defensive documentation: surfaces and controls are described, not exercised.

Obfuscated names are per build and were re-resolved from stable strings in 2.26.41.6.

| Path | Credential that replaces the account | Transport | Main classes (2.26.41.6) |
|------|--------------------------------------|-----------|--------------------------|
| Phone registration | none until `/v2/register`; request carries Noise static key bundle and device ids | HTTPS `/v2/*` | `K49`, `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Pre-number funnel log | phone id (`fdid`) only | HTTPS `/v2/pre_pn_client_log` | `PrePnBaseFunnelLogger`, `K49` |
| Pre-chat AB props | `ab_key` / `ab_hash` prefs | HTTPS `/v2/reg_onboard_abprop` | `K49.checkPreChatdABProps` |
| Ban status / appeal | opaque token stored at ban time + compiled-in app client token | HTTPS Graph `graph.<domain>/graphql` | `AbstractC40195HfH`, `C37409GLo`, `C37604GYf`, `C37414GLt` |
| Logged-out support form | none; email + free text + `anid` | HTTPS multipart POST | `LoggedOutContactFormActivity`, `C47328KmN` |
| Crash / log upload | compiled-in app token | HTTPS `crashlogs.whatsapp.net` | `C10V`, `C05640An` |
| Static assets | none | HTTPS GET | `static.whatsapp.net/*` |
| Anonymous-credential Graph (ACS / OHAI) | ACS token or OHAI key config, no JID | HTTPS `acs.whatsapp.com/graphql` | `C31991Nz`, `R5t`, `N5I` |
| Companion registration | none; null-JID Noise connect allowed only here | Noise | `HandlerThreadC12340b0` |
| Bundled DNS fallback | none | compiled-in table | `AbstractC47101wK`, `C36881dC` |

Not covered here, see the linked reports: registration steps, OTP methods and failure reasons ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) section 3); attestation tokens sent at registration ([WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)); ban state machine and appeal encryption ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) sections 2, 10); Noise login and companion registration ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)); WAM telemetry ([WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)).

---

## 2. Manifest: exported components

### 2.1 Counts (found, `AndroidManifest.xml`, parsed under `<application>`)

| Type | Declared | Exported (explicit `true`; none relied on the implicit default) |
|------|---------:|----------------------------------------------------------------:|
| `activity` | 828 | 22 |
| `activity-alias` | 33 | 29 (14 are disabled `AppIcon01..14` launcher aliases) |
| `service` | 61 | 16 |
| `receiver` | 68 | 19 |
| `provider` | 19 | 11 |
| Total | 1009 | 97 |

Of the 97 exported entries: 20 are `enabled="false"` (14 icon aliases, car-app service, ADM receiver, iOS-migration activity and provider, two India UPI intent receivers); 24 carry a `permission` / `readPermission`; 6 are gated by a WhatsApp-defined `signature` permission; 56 are enabled with no manifest permission. Any check beyond the manifest is in code (section 9).

Custom permissions (found): `REGISTRATION`, `IDENTITY_VERIFICATION`, `MIGRATION_CONTENT_PROVIDER`, `BROADCAST`, `MAPS_RECEIVE`, `RECEIVE_ADM_MESSAGE`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` are `protectionLevel="signature"`. `com.whatsapp.sticker.READ` has no `protectionLevel` (default normal).

### 2.2 Entry points that run with no account

| Component | Exported | Filter | Why it is reachable pre-registration |
|-----------|----------|--------|--------------------------------------|
| `com.whatsapp.Main` | yes | `MAIN` / `LAUNCHER`, `MULTIWINDOW_LAUNCHER` | single launcher; routes by registration state (section 3) |
| `com.whatsapp.home.ui.HomeActivity` + aliases `AcceptInviteLinkActivityDeepLink`, `EventDeepLink`, `HomeActivity` | yes | `chat.whatsapp.com`, `call.whatsapp.com`, `event.whatsapp.com`, `whatsapp://chat`, `call`, `event`, NFC `application/com.whatsapp.chat`, `.join` | no registration check found in `HomeActivity` itself (inferred: a base class redirects, not resolved) |
| `DeepLinkActivity` via 4 aliases | alias yes, target no | see section 4 | link entry point |
| `com.whatsapp.deeplink.ui.TpalOAuthRedirectActivity` | yes | `www.whatsapp.com/oauth_account_linking/login_redirect`, `/oauth_account_linking_mobile/login_redirect`, `whatsapp://third_party_oauth` | OAuth redirect receiver, `noHistory` |
| `com.whatsapp.cuif.ConsentActivity` | yes | `whatsapp://consent` | reads extras `flow_name`, `source`, `extra_params`, `device_id`, `app_id`; pre-registration behaviour not resolved |
| `com.whatsapp.Conversation` | yes | `sms:` / `smsto:` `VIEW` / `SENDTO` | system SMS handler entry |
| `com.whatsapp.accountsync.ProfileActivity`, `CallContactLandingActivity` | yes | `content://com.android.contacts` MIME `vnd.com.whatsapp.profile`, `.voip.call`, `.video.call` | contacts-app integration; `CallContactLandingActivity` needs `CALL_PHONE` |
| `com.whatsapp.registration.ui.RegistrationCompletedReceiver` | yes, `REGISTRATION` signature | `com.whatsapp.SMBRegistrationCompleted` | sister-app signal |
| `com.whatsapp.registration.directmigration.MigrationProviderOrderedBroadcastReceiver`, `MigrationRequesterBroadcastReceiver` | yes, `REGISTRATION` signature | actions `initialMigrationInfoAction`, `recoveryTokenAction`, `setMigrationStateOnProviderSide`, `providerIsLoggedOutAction`, `providerAppMigrationSpaceNeededAction` | consumer / SMB sister-app migration at registration time |
| `MigrationContentProvider`, `DirectMigrationContentProvider` | yes, `readPermission` `MIGRATION_CONTENT_PROVIDER` (signature) | authorities `com.whatsapp.provider.MigrationContentProvider`, `.DirectMigrationContentProvider` | same migration |
| `com.whatsapp.registration.app.verifyphone.SMSRetrieverAppInactiveReceiver` | yes, GMS `SEND` permission | `SMS_RETRIEVED` | SMS Retriever result when the app is inactive |
| `com.whatsapp.registration.core.accounttransfer.AccountTransferReceiver` | yes, no permission | `com.google.android.gms.auth.START_ACCOUNT_EXPORT` | code requires a secure keyguard and a feature check before acting (found) |
| `com.whatsapp.phoneid.PhoneIdRequestReceiver` | yes, no permission | `com.facebook.GET_PHONE_ID` | returns the phone id to a trusted caller (section 9.1) |
| `com.whatsapp.otpmessage.otp.OtpRequestedReceiver`, `OtpIdentityHashRequestedReceiver` | yes, no permission | `com.whatsapp.otp.OTP_REQUESTED`, `ID_HASH_REQUESTED` | OTP autofill handshake for other apps (section 9.3) |

### 2.3 Other exported entries (not registration related, listed for completeness)

| Group | Components | Gate |
|-------|------------|------|
| Third-party content | `Conversation` (`sms:` handler), `ExternalShareAlias` (`SEND`, `SEND_MULTIPLE`, `*/*`), `ContactPicker` (`PICK`, `CREATE_SHORTCUT`), `SetAsProfilePhoto` (`ATTACH_DATA`) | none in manifest |
| Stickers | `SendStickerCommandActivity`, `AddThirdPartyStickerPackActivity` (+ alias), `StickerCommandProvider`, `WhitelistPackQueryContentProvider` | none in manifest |
| Meta family IPC | `FamilyAppsCredentialsProvider`, `FamilyAppsUserValuesProvider`, `WaAccountsCenterService` (`com.whatsapp.wfl.OPERATION`), `QuickSendsContactsProvider`, `OrbitSsoProvider`, `OrbitMessagesProvider`, `OrbitCompanionLinkActivity`, `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | caller checks in code (section 9) |
| Device companions | `WearOsListenerService`, `GarminBindingServiceShim`, `IQGarminBindingService`, `TetheredService`, `WhatsAppCarAppService` (disabled) | none in manifest |
| Google integration | `BackupNowService`, `BackupStateService`, `OsMigrationAppDataService` (`BACKUP`), `DeferredRestoreBroadcastReceiver` (`BACKUP`), `WakeUpService` (exposure notification permission) | partly |

Also exported: settings hooks (`SettingsNotifications`, `SettingsDataUsageActivity`, `AppAuthenticationActivity` widget configure), call landing (`SystemDialerCallLandingActivity`, `VoiceMessagingActivity`), library receivers (`WidgetProvider`, `BootReceiver`, `AppUpdatedReceiver`, `ExternalMediaStateReceiver`, `WAFbnsPreloadReceiver`, `FirebaseInstanceIdReceiver`, work-manager and profile-install entries behind `BIND_JOB_SERVICE` / `DUMP`), Pixel entries (`com.google.permission.besties.API`), and the disabled India UPI and iOS-migration entries. `IdentityVerificationActivity` (NFC `application/com.whatsapp.identity.ui`) requires the signature permission `IDENTITY_VERIFICATION`.

### 2.4 Non-exported pre-registration components (found)

The 806 non-exported activities include every registration screen (section 3.2), `LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity`, `BanAppealActivity`, `WfacBanActivity`, `PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`. Three non-exported alarm receivers drive registration reminders: `RegRetryVerificationReceiver` (`com.whatsapp.alarm.REGISTRATION_RETRY`, `SMS_RECEIVED_WHILE_INACTIVE`), `OnboardingIncompleteReceiver` (`ONBOARDING_INCOMPLETE`), `EnterPhoneNumberNotificationReceiver` (`ENTER_PHONE_NUMBER`). Non-exported providers: `FileProvider`, `SecureFileProvider`, `MediaProvider`, `AccountSwitchingContentProvider`, `RestartAppContentProvider`, `InstrumentationProvider` (all with `grantUriPermissions` where declared).

### 2.5 Application flags and network policy (found)

| Item | Value |
|------|-------|
| `debuggable` | `false` |
| `allowBackup` | `true`, but `fullBackupContent` and `dataExtractionRules` (cloud-backup and device-transfer) exclude all domains; cross-platform transfer entry for iOS only carries `bundleId` / `teamId` |
| `networkSecurityConfig` base | `cleartextTrafficPermitted="true"`; trust anchors `system` and `user` (`overridePins="true"` for user CAs) |
| Cleartext denied | `whatsapp.com`, `whatsapp.net`, `wa.me`, `wl.co` (22 SHA-256 pins, no expiry), `facebook.com`, `instagram.com`, `jiomart.com`, `hatch-api.meta.ai` |
| Pin scope | the pin set sits on the `whatsapp.com` / `whatsapp.net` / `wa.me` / `wl.co` domain-config; it inherits the base trust anchors, so pins do not apply to user-installed CAs (platform behaviour of `overridePins`) |
| Hosts outside any domain-config | `gstatic.com` (reCAPTCHA key) falls under the base config (cleartext permitted; the code uses `https://`) |

---

## 3. Pre-registration screens and state routing

### 3.1 `Main` routing by registration state (found, smali of `Main.A5W`)

`Main` reads the registration state (`C0Gk.A02()`) and the stored own-account object. Log tags are stable anchors.

| State | Log tag | Destination |
|------:|---------|-------------|
| 2 | `main/me/regname`, `main/no-me/regname` | name-entry registration step (`RegisterName`) |
| 21 | `main/me/wfac ban` | WFAC ban screen via `HBC.A00` (`WfacBanActivity`) |
| 24, 38 | `main/me/backup otp` | backup OTP / verification step |
| 41 | `main/me/consent age ban` | age consent screen |
| 45 | `main/me/paa onboarding`, `main/no-me/paa onboarding` | dependent / managed-account onboarding |
| 50 | `main/me/logged out, going to PrimaryLoginBackActivity` | login-back screen |
| 51 | `main/me/pending login-back verification` | login-back verification (extra `login_back_verification`) |
| 56 | `main/me/username`, `main/no-me/username` | username step |
| any | `main/no-me/first-factor password` | first-factor password branch (no own account object) |
| any | `main/invalid/registration state=` | invalid state log |

The same method builds intents (found) for `VerifyPhoneNumber`, `DeviceConfirmationRegistrationActivity`, `ExportMigrationDataExportedActivity`, `BanAppealActivity` (extra `launch_source`), `DeleteAccountConfirmation` and the default `RegisterPhone` entry. A `logged_out_phone_fallback_pending` preference resumes at `RegisterPhone` (`main/me/logged-out phone fallback resume`). A minted IDV token (`minted_idv_token`, `minted_idvtoken_expiry_time_secs`) is checked, and an expired or empty one resets the remediation flow. Which numeric states correspond to which server-side step is inferred from tag names.

### 3.2 Registration screens (found, all non-exported)

| Group | Activities (`com.whatsapp.registration.app.*` unless noted) |
|-------|--------------------------------------------------------------|
| Entry | `EULA` (tag `eula_screen` / `eula_with_language_selector`), `phonenumberentry.RegisterPhone`, `RegisterAsDependentActivity`, `RegTabletIntroActivity`, `RegTabletChooseOptionActivity` |
| Permissions | `RegPermissionsExplainerActivity`, `RegNotificationPermissionPrimerActivity` |
| Verification | `verifyphone.VerifyPhoneNumber`, `sendsmstowa.SendSmsToWa`, `ManualSmsRequest`, `flashcall.PrimaryFlashCallEducationScreen`, `email.RegisterEmail`, `email.VerifyEmail`, `email.EmailEducationScreen`, `email.UnverifiedEmailSetupRegUpsellActivity`, `email.ConfirmEmailSetupRegUpsellActivity`, `backuptoken.BackupTokenEducationScreen`, `VerifyTwoFactorAuth` |
| Account defence | `accountdefence.DeviceConfirmationRegistrationActivity`, `accountdefence.ui.OldDeviceSecureAccountActivity`, `OldDeviceSecureAccount2FaActivity`, `OldDeviceMoveAccountNoticeActivity` |
| Blocks | `parole.CustomRegistrationBlockActivity`, `downgrade.DowngradeFrictionActivity`, `com.whatsapp.userban.ui.BanAppealActivity` |
| Migration | `directmigration.RestoreFromConsumerDatabaseActivity`, `MigrationStartTransferActivity`, `RequestPermissionFromSisterAppActivity`, `com.whatsapp.migration.transfer.ui.*` |
| Name / change number | `RegisterName`, `phonenumberentry.ChangeNumber*` |
| Companion mode | `com.whatsapp.companionmode.registration.ui.RegisterAsCompanionActivity`, `RegisterAsCompanionEnterNumberActivity`, `RegisterAsCompanionLinkCodeActivity`, `CompanionBootstrapActivity`, `CompanionPostLogoutActivity` |
| Logged-out | `logout.ui.PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`, `loginfailure.LogoutMessageActivity` |
| Support | `inappsupport.ui.app.LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity` |

### 3.3 Language and country pickers (found)

| Item | Detail |
|------|--------|
| Language | `LanguageSelectorBottomSheet` opened from `EULA` (funnel event `language_selected`; metrics `language_selector_clicked_count`, `language_selector_time_spent` in `K49`); settings-side `FullScreenLanguageSelectorActivity` is non-exported |
| Country names | 63 offline tables `assets/country_names_<lang>.tsv` (`ISO code<TAB>name`); no network lookup for the picker found |
| Number prefill | `RegisterPhone` uses Google phone-number hints (`RegisterPhone/launchGooglePNHints`) and a "what's my number" SIM path that needs a phone permission; EULA extras `RegisterPhone.phone_number`, `country_code`, `auto_submit_after_prefill`, `one_click_from_eula` |
| Legal links on `EULA` | `https://www.whatsapp.com/legal/terms-of-service` or `/terms`, `privacy-policy` or `privacy-policies` (variant by config) |

---

## 4. Deep links and web links

### 4.1 Entry aliases (found)

| Alias | Target | Filters |
|-------|--------|---------|
| `TextAndDirectChatDeepLink` | `DeepLinkActivity` | `http(s)://api.whatsapp.com`, `wa.me`; `https://[www.]whatsapp.com` paths `/channel`, `/channel_status`, `/updates`, `/aimediainput`, `/aivoice`, `/dl`, `/privacy/disclosure`, `/wamo/status/link-{instagram,facebook}-in-house-ad`; schemes `whatsapp`, `whatsapp-smb`, `whatsapp-consumer`, `whatsapp-sheet` (host lists, 100+ hosts) |
| `VerifyOtpDeepLink` | `DeepLinkActivity` | `http(s)://b.whatsapp.com`, `http(s)://v.whatsapp.com` |
| `FoaDeeplinkActivityAliasUniversalLink`, `FoaDeeplinkActivityAliasAppScheme` | `DeepLinkActivity` | no filter in this manifest (declared for the Meta family deep-link library) |
| `AcceptInviteLinkActivityDeepLink` | `HomeActivity` | `chat.whatsapp.com` |

`DeepLinkActivity` itself is not exported; every external path goes through an alias. All filters with `autoVerify="true"` cover https hosts only. Several filters on `whatsapp`, `whatsapp-consumer`, `whatsapp-smb` carry both `VIEW` and the custom action `com.whatsapp.DEEP_LINK_REDIRECT`, so the alias answers an explicit intent with that action from any app (found: filter shape).

### 4.2 Links that handle pre-registration state (found)

| Link | Parser anchor | Behaviour |
|------|---------------|-----------|
| `https://[www.]whatsapp.com/dl?wsu=<6 digits>` | `IJB.A01`: path `dl`, query `wsu` matching `\d{6}`, log `DeepLinkHelper/parseUri/web signup uri`, code **193** | web sign-up hand-off; value only validated by regex client-side |
| `whatsapp://s/signup` (single path segment `signup`) | `IJB.A01` code **216**, gated by ab-props **25005** or **25801**; handler `handleInAppSignupDeepLink` requires scheme `whatsapp` and query `s` | in-app sign-up; logs through `ApiSignupFlowLogger` with `signup_id` (host `s` pairing inferred from the manifest) |
| `https://v.whatsapp.com/<code>`, `https://b.whatsapp.com/<code>` (last path segment) and `whatsapp://r?c=<code>` | `DeepLinkActivity` registration branch, log `DeepLinkActivity/Registration deeplink/registration state:` | email-OTP link. State 1 opens `RegisterPhone` with extra `tapped_sms_link`; state 2 opens `VerifyEmail` with `email_otp`, `entrypoint`, `session_id`, `challenge_flow=false` and reports `email_otp_deeplink_redirect_to_register_name`; other states redirect to settings (`settings_verification_email_address_verified`, inferred). The code is forwarded as an extra; verification is server-side (unknown) |
| `whatsapp://code-linking?auth=<nonce>` | code **77**, handler `maybeStartCodeLinkingFlow`, ab-prop **4560** (`ENABLE_CODE_LINKING_DEEP_LINK_CODE`), pref `adl_deep_link_nonce` with a 300000 window (unit inferred as ms) | linked-device code flow; skipped when the flag is off or the nonce is older than the window |
| `whatsapp://help/<segment>` | code **62**; offline branch logs `DeepLinkActivity/help/no-connectivity` | help article |
| `whatsapp://support` | code **30** (extracted from the parser; handler logs `about/no-connectivity`) | support / about screen, needs connectivity |

### 4.3 The pre-registration gate

| Anchor | Finding | Tier |
|--------|---------|------|
| `DeepLinkActivity/deeplink not allowed before registration/` and reason `not_allowed_before_registration` | present; the reason enum maps value 0 to that string; the producer of reason 0 for ordinary links was not isolated | found (strings), unknown (producer) |
| Per-code handlers | each handler checks the registration state itself (`C0Gk.A0C()` / `A02()` calls in the switch bodies) | found |
| Allowlist of logged-out codes | not re-resolved: `C02T` is a serial executor in this build and `C02U` is a shared integer-constant class, so earlier class names do not map | unknown |
| `JXK` result (`code`, `source`, reason) built by `IJB`, `IJC`, `IJD`, `IJE` | parser output consumed by `DeepLinkActivity.A0w` | found |

Resolving content (a chat, a channel, a directory) still needs an account: group invite and `wa.me/<phone>` handlers use the authenticated session (inferred from handler names; not traced end to end here).

---

## 5. Hosts and endpoints contacted without an account

### 5.1 Registration HTTP (found)

16 paths, XOR key 18 in `AbstractC45307Jps`, all re-decoded in 2.26.41.6: `/v2/exist`, `/v2/code`, `/v2/register`, `/v2/security`, `/v2/challenge`, `/v2/passkey_auth`, `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop`, `/v2/device_logout_send`, `/v2/device_logout_fetch`, `/v2/wfs`. Two further constants decode to `ENC` and `H` (use unknown). Field lists for the first group are in [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) section 3.1. The base host `v.whatsapp.net` is the name in the compiled-in table (5.4); the code that joins host and path is in the wamsys / Kotlin stacks and was not read here (inferred).

Selector `K49.A0b` chooses the Kotlin stack (`KotlinRegistrationBridge`) or the native `wamsys` stack; the native stack must bootstrap first (`ensureWamsysForRegBootstrapped`, error `FAIL_TO_INITIALIZE_WAMSYS`).

### 5.2 Other HTTPS endpoints (found literal, auth as stated)

| Host / URL | Method | Auth in code | Caller | Account-less? |
|------------|--------|--------------|--------|---------------|
| `https://www.whatsapp.com/contact/noclient/verification/` | multipart POST | none | `C47328KmN` case 0 (support form) | yes |
| `https://graph.<pref_graphql_domain>/graphql` (default `graph.whatsapp.com`) | POST JSON | compiled-in app client token in body `access_token` | `AbstractC40195HfH` and subclasses | yes (ban status / appeal) |
| `https://crashlogs.whatsapp.net/wa_clb_data`, `/wa_fls_upload_check`, `/wa_profilo_data`, `/whatson_logs_upload` | POST | compiled-in app token (log upload adds `access_token`, `type`, `from_jid`, `ticket_id`, `build_id`) | `C10V`, `C05640An`, `ExceptionsUploadService`, `ProfiloUploadService`, `CM8` | runs without login; `from_jid` content when logged out unknown |
| `https://acs.whatsapp.com/graphql` | POST | ACS token or OHAI config (no JID) | `C31991Nz`, `R5t` | yes (de-identified requests) |
| `https://static.whatsapp.net/wa/static/{downloadable,network_resource,payments/*}`, `/sticker?...`, `/payments/background` | GET | none | UI asset loaders | yes |
| `https://mmg.whatsapp.net/proxygen/health`, base `https://mmg.whatsapp.net` (config 22436) | GET | none | media / health | yes |
| `https://www.gstatic.com/recaptcha/verify_key/orcas/prod/android/verify_key.txt` | GET | none | `C44464JbH` (used by `RequestCodeRepository`, `VerifyCodeRepository`, `VerifyPhoneNumber`) | yes (registration captcha) |
| `https://www.whatsapp.com/compliance/xfac/mint` | POST form | none seen | `CommonRemediationApi` (age remediation, `minted_idv_token`) | reachable pre-registration: unknown |
| `https://www.whatsapp.com/v1/auth/canonical/token/` | POST form `nonce`, `user_id`, `device_id`, `client_pub_key` | none | `CanonicalUserCompanionDeviceManager` | companion / linked-account path, not pure pre-registration |
| `https://api.whatsapp.net/support/add_bug_attachment` | multipart POST | `Authorization: Bearer <token>` | `PostBugAttachmentUploader` (in-app bug report) | no (token-bound) |
| `https://graph.whatsapp.net/v2.2/maps_configs?...&access_token=` (default `graph.facebook.com`) | GET | app token in URL | `N6n` map config | trigger not pre-registration (inferred) |
| `https://api.whatsapp.net/calendar/integrations/` | request | session | calendar feature | no |

Compiled-in tokens: two Facebook-style forms exist, `WA|<app_id>|<secret>` in the Graph client default and `<app_id>|<secret>` in the log uploader. Values are not reproduced here. They identify the app, not a user.

### 5.3 DNS and connectivity bootstrap (found)

| Item | Detail |
|------|--------|
| Compiled-in table `AbstractC47101wK` | host to IPv4 / IPv6 list for 18 names: `e1..e16`, `g`, `v` under `.whatsapp.net` (each with a trailing-dot twin); no network needed |
| `C36881dC` (DnsCache) | order of use: primary resolver, MNS DNS resolver (`DnsCache/resolveViaMnsDns`, the string `v.whatsapp.net` is tested in that branch), secondary resolver, hardcoded table; hardcoded lookups fail with `no hardcoded ips found for <host>` when the table has no entry and are skipped with `hardcoded dns resolver disabled` when the option bit is off |
| Chat host | `g.whatsapp.net` entry is read directly (`C36881dC.A01`) |

The MNS resolver wire format lives in native code: unknown.

### 5.4 REST paths that do not exist (found negative)

No unauthenticated REST fetch for gating or config (`/gk`, `/props`, `/config`) was found. Pre-login experiment config does arrive over registration HTTP: `/v2/reg_onboard_abprop` (`K49.checkPreChatdABProps`) sends `ab_hash` from pref `pref_pre_chatd_ab_hash`, `ab_exposure`/`ab_key` from `pref_pre_chatd_ab_key`, plus the device fields of section 7.

---

## 6. Logged-out support form (found)

`LoggedOutContactFormActivity` (non-exported) is the only fully account-less support flow in this build.

| Intent extra (prefix `com.whatsapp.inappsupport.ui.app.LoggedOutContactFormActivity.`) | Use |
|------|-----|
| `PhoneNumber`, `CountryCode` | prefilled number; empty string when absent |
| `From` | entry point label |
| `ServerStatus` | status string passed from the caller (inferred: registration server status) |
| `IsRegistrationVerification` | boolean; on success a follow-up call is made (target unresolved) |
| `SupportUserContext` (`K8W`) | entry point and CMS ids (`Entry point`, `Cms ids`) |

Form fields: email (suggestion chips `@gmail.com`, `@hotmail.com`, `@icloud.com`, `@outlook.com`, `@yahoo.com`), description, up to 3 screenshots picked from `MediaStore`.

Submission (`C47328KmN` case 0, tag `logged_out_contact_form`, trailing argument 20 of unresolved meaning):

| Part | Name | Content |
|------|------|---------|
| field | `email` | typed email |
| field | `message` | description |
| field | `platform` | literal `ANDROID` |
| field | `phone_number` | typed number |
| field | `debug_info` | text built by `C10V.A08` (section 7.3) |
| file | `log_data` | `logs.tar.gz` of the client log (rotated and compressed first) |
| files | `attachment_<n>` | screenshots re-encoded to JPEG quality 80, 2048 px bound, kept only when 10 MiB or smaller |
| extra | `skip_saga_copy=true`, `saga_copy=true`, `pn` | `pn` = country code + number when both are non-empty |

Result: the HTTP status goes to a result callback (`C46422KQg`); a failure surfaces as `Server error: <status>` or `Network error`; success opens `LoggedOutContactSuccessActivity` (extra `...Email`). The exact status-to-success mapping was not read. The call is a plain HTTPS POST through the app HTTP client; it is not a GraphQL call. A random `anid` UUID (7.1) is generated per submission.

---

## 7. Identifiers sent before login

### 7.1 Identifier table

| Identifier | Where | Source | Notes | Tier |
|------------|-------|--------|-------|------|
| `fdid` | `/v2/pre_pn_client_log`, registration requests | `C38141gV.Ax2()`: random `UUID.randomUUID()` stored as `phoneid_id` + `phoneid_timestamp` in prefs | persists across registration attempts; same id is returned by `PhoneIdRequestReceiver` | found |
| `fid` | registration requests | `C47381wu.Ax2()`: prefs `phoneyid_id` + `phoneyid_timestamp`, sent as `<id>|<timestamp>` only when present | secondary family id; producer of the value not traced | found (use inferred) |
| `anid` | support form | `C11J.A01()`: `UUID.randomUUID()` per call, also logged as a WAM event | per-submission random id | found |
| `advertising_id` / `android_advertising_id` | `/v2/exist`, `/v2/code`, `/v2/register`; funnel log | Google advertising id when available | excluded from the debug log string of the funnel logger | found |
| `authkey`, `e_ident`, `e_keytype`, `e_regid`, `e_skey_id`, `e_skey_val`, `e_skey_sig`, `e_pq_last_resort_{id,val,sig}` | registration requests | `C45446JsB`: client Noise static key and Signal key bundle | public material | found |
| `gpia` | registration requests | Play Integrity standard token, flag-gated | see [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) | found |
| `ab_key`, `ab_hash`, `ab_exposure` | `/v2/exist`, `/v2/pre_pn_client_log`, `/v2/reg_onboard_abprop` | prefs `pref_pre_chatd_ab_key` / `pref_pre_chatd_ab_hash` | experiment bucket | found |
| `device_country` | funnel log | `TelephonyManager.getSimCountryIso()` upper-cased, `ZZ` when absent | | found |
| `access_token` (app) | Graph, log upload | compiled constant | app identity, not user | found |
| `request_token` / `token` | ban status / appeal | pref `wfac_ban_status_token` (status) and the stored appeal token | opaque, issued by the server at ban time ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md)) | found |
| `from_jid` | log upload | account JID when present | content when logged out unknown | found (field), unknown (value) |
| `registration_trace_id`, `request_id`, `nonce_encryption_key` | account recovery mutation | `AccountRecoveryManager` (section 8.2) | | found |

### 7.2 Device attributes in registration requests (found, `K49` helpers `A0O`, `A0Q`, `A0R`, `A0U`, `A0W`, `A0X`)

`network_radio_type`, `simnum` (`0` / `1`), `hasinrc` (file `rc2` present), `pid` (process id), `device_ram`, `sim_type`, `airplane_mode_type`, `cellular_strength` (signal level, `5` default), `roaming_type`, `preloads_app_manager_id`, `preloads_attribution`, `entrypoint` (`create_paa` or `suma`), `tos_version` (`5`), `old_phone_number` (change-number flow). Telemetry metric keys in the same class (found, request use not confirmed): `network_operator_name`, `sim_operator_name`, `sim_state`, `read_phone_permission_granted`, `mistyped`, `c2dm_reg_id` (read from prefs).

### 7.3 Funnel log content (found, `PrePnBaseFunnelLogger$sendPrePNFunnelLog$1`)

Before a number exists the client sends: `current_screen`, `previous_screen` (pref `pref_previous_screen`, default `unknown`), `action_taken`, `event_name`, `access_funnel_type=wa`, `app_campaign_download_source`, `is_add_account_flow`, `android_advertising_id`, `ab_key`, `device_country`, `fdid`, the device attributes above and `entrypoint`. In add-account or logged-out-fallback flows it also sends `primary_logout_session_id` and `number_of_accounts`. The send is skipped when the wamsys bootstrap fails.

### 7.4 `debug_info` of the support form (found, `C10V.A08`, JID argument is `null` in this call)

Labels written into the text: `useragent`, `Socket Conn`, `Connection`, `Server`, `Datacenter`, `Sim`, `Free Space Built-In` / `Removable`, `Network metered` / `restricted`, `Data roaming`, `Tel roaming`, `Diagnostic Codes`, `ABprops hash state`, `Screen reader`, `Fingerprint eligible`, backup status fields, `Is Companion`, `Number of Accounts`, `Mobile Build Id`, `wfl_state`, `isMetaVerified`, `Mistyped` / `Mistyped Last6` / `L Distance` (comparison of the typed number with the SIM number), plus last-call identifiers when call history exists. The `entity id` label is only written when a JID is passed, which it is not here.

---

## 8. Graph and MEX calls without a user session

### 8.1 App-token Graph requests (found)

Base class `AbstractC40195HfH.CND` builds `https://graph.<A0f()>/graphql` (`A0f()` = pref `pref_graphql_domain`, default `whatsapp.com`; subclasses `GEV`, `GEX`, `GET`, `GEW`, `GEU` and the `C45F` Meta-account family switch to `facebook.com` / `instagram.com`). Body JSON: operation variables, `access_token` (compiled token when the subclass passes none), `doc_id`, `lang`, `Content-Type`. Header `X-FB-Request-Analytics-Tags` is added when absent.

| Class | doc_id | Variables | Purpose |
|-------|-------:|-----------|---------|
| `C37604GYf` | **4276154569100535** | `app_id` (`dev.app.id`), `request_token` | WFAC ban status poll (`WfacBanRepository/fetchBanStatus`, token from pref `wfac_ban_status_token`) |
| `C37409GLo` | **27883644401256929** or **4276154569100535** (boolean) | same | ban status via `HG2.A01` |
| `C37414GLt` | **38509456535312323** or **5473316762755318** (boolean) | `app_id`, `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}`; plaintext `{token, debug_info, description}`, context `WA_INAPP_BAN_APPEALS` | ban appeal submit (`C40191HfD`); details in [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) section 10 |
| `C37408GLn` | **5803265299734043** | `app_id`, `client_pub_key` | purpose unknown (sends a client public key); caller not traced |
| `C37601GYc`, `GYd`, `GYe` | `GYd` **25453433540999208**, `GYe` **25974020015520396** (`GYc` carries no id in its own class) | `caller_name` `fx_waffle_contextual_pause_account_match`, `wa_waffle_certs`, `fx_waffle_foa_unpause` | Meta account-linking helpers |
| `C37605GYg`, `GYh`, `GYi` | **26573478745654327**, **26742313962085910**, **27503298369362501**, **28331348373116386**, **25840634418966704** | header `IG-Set-Waffle-Graphql-Access-Token`, key `ACCESS_TOKEN` | Facebook / Instagram account-linking; a linked-account token is required (inferred from the header and key names) |
| `C37413GLs` | **7236799486398397** | `batches`, `device_model`, `device_os`, `device_os_version`, `event_time`, `is_employee`, `primary_locale` | client event batches (inferred from variable names) |

The doc_id 6960707423955525 (a legacy appeal mutation id reported for older builds) does not occur in 2.26.41.6. The operation names of the appeal and status requests are not carried by these classes (unknown).

Difference from [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) section 10: for `C37414GLt`, `C37409GLo` and `C37604GYf` the host is `graph.<pref_graphql_domain>` (default `graph.whatsapp.com`); only the subclasses listed above override it to `facebook.com`.

### 8.2 MEX operations with a registration-time or logged-out call site (found, schema `whatsapp-android-mex`)

doc_ids from `assets/whatsapp-android-mex_client_persist_ids.json` (and the `www` / `wamo` files where noted).

| Operation | doc_id | Call site |
|-----------|-------:|-----------|
| `GetAutoConfConfidenceChallenge` | 25578301865133112 | `C40175Het`, `C40196HfI` (autoconf confidence ping) |
| `ValidateVerifierConfidence` | 25879669248324812 | `C40196HfI`, `C40197HfJ` |
| `FetchReachoutTimelockQuery` | 25627902213558773 | `RunnableC23952AUh` |
| `RemoveAccountReachoutTimelock` | 25040013452293167 | not traced |
| `UserCountryCodeGet` | 25292528387076991 | `MexUserCountryCodeRepository` |
| `MobileConfigFetchQuery` | 29248978061376279 | not traced |
| `SubmitAge`, `GetAgeExperience`, `SetAgeExperienceMutation` | 26049558371296621, 26567868986241476, 26051006311231325 | age flows |
| `TosSetResult` | 25225843213776555 | terms acceptance |
| `GetWaOldResponse` | 25784374561179853 | verify via old phone |
| `WWWTriggerAcountRecovery` | 24896267680055094 | `AccountRecoveryManager` (variables `nonce_encryption_key`, `use_case`, `registration_trace_id`, `request_id`) |
| `WWWCreateUser`, `WWWDeleteUser`, `WWWGetCertificates` | 8548056818544135, 7989555047767245, 25094190163544446 | account linking |
| `OhaiKeyConfigQuery` | 25069818679280758 | `N5I` (ACS / OHAI bootstrap) |
| `CreateEnforcementAppeal` | 26933630359642347 | newsletter enforcement client |
| `NewsletterCreateReportAppeal` (mex), `CreateGroupSuspensionAppealMutation` (www), `WamoReportPromoAppealV2Mutation` (wamo) | 27792557363683798, 25646047815072526, 26867425009592691 | appeal operations (account-bound; present in assets) |

MEX is sent as an IQ `xmlns="w:mex"` with `<query query_id=...>` (`C19370nI`) through the chat connection (`WAChatdGraphQLClient`). Whether these operations run on a pre-account session is not established: see 8.3.

### 8.3 Chat connection without a JID (found)

`ConnectionThread.connect` (`HandlerThreadC12340b0`) reads the own JID; when it is null it proceeds only if the companion-registration flag (`C06830Gm.A02()`) is true, otherwise it reads a second JID source (`Ash()`), and if that is also null it logs `ConnectionThread/connect/ignored/jid null and not in companion reg` and returns. Primary-phone registration therefore does not use a null-JID chat connection (consistent with [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) section 6.4). The meaning of the second source is inferred (a stored or pending-registration JID, unresolved). Which session carries the registration-time MEX calls of 8.2 is unknown.

### 8.4 De-identified requests (found)

`PandoGraphQLRequest.requireAcsToken()` and `requireOhaiConfig()` are read by `C6GN`; a request marked `@deidentified` without an ACS token or OHAI config throws (`Request was marked with @deidentified, but no ... was provided`). `AcsOhaiConfig` fields: project name, doc id, `graphQlUrl=https://acs.whatsapp.com/graphql`, surface, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`. Which operations carry the flag is encoded in the `*_pando_flatbuffer_data.bin` assets: unknown.

---

## 9. Exported IPC surfaces with code-level checks

All entries are exported with no manifest permission unless noted. This section lists the controls found in code, not a verdict on their strength.

### 9.1 `PhoneIdRequestReceiver` (`com.facebook.GET_PHONE_ID`)

An ordered broadcast. The receiver reads a `PendingIntent` extra `auth` from the result extras and takes `getCreatorPackage()`. A package is trusted when its signing certificate hash is in a hardcoded allow-set (`AbstractC28130CKz.A04`, SHA-1 of signing certs, values not reproduced; a second SHA-256 set is used in `CHA.A02`). A trusted caller gets the phone id and its timestamp as the broadcast result (`setResult(-1, id, {timestamp})`); an alternate path returns the secondary id when flag **3651** allows. The decompiled control flow around the trust variable is partial, so the exact precedence is inferred.

### 9.2 Family-of-apps providers (found)

| Component | Controls found |
|-----------|----------------|
| `FamilyAppsCredentialsProvider` | `getCallingPackage()`; per-selection handler map; caller UID resolved to a certificate and checked against the handler's trusted set (`C45775Jyk.A01`); link-manager eligibility (`WfalManager.A00`); feature flags; link state must be in the handler's eligible set; returns a 3-column cursor (auth proof, bundle, TTL) from prefs `pref_foa_nta_ipc_bundle_auth_proof`, `pref_foa_nta_ipc_bundle`, `foa_nta_ipc_bundle_ttl`; errors for expired or missing cache. Expansion of "NTA" unknown |
| `FamilyAppsUserValuesProvider` | one selection `foa_wo_wa_link_eligibility_values`, `getCallingPackage()` read |
| `WaAccountsCenterService` | action `com.whatsapp.wfl.OPERATION`; class body is a stub in the decompile (checks unknown) |
| `QuickSendsContactsProvider` | `getCallingPackage()` validation steps logged (`validation_start` / `validation_end`); serves encrypted `.enc` photo files and contact columns (`obfuscated_chat_id`, `display_name`, `profile_photo_uri`, `photo_key`) |
| `OrbitSsoProvider` (`com.whatsapp.orbit.v2.sso`) | feature flag gate; caller package must be in an allow-list (`AbstractC62035Rsx.A00`, otherwise `SecurityException ... is not allowlisted`); a precondition check (`BS3()`) before any method; methods `get_profile` (returns `display_name`, `phone_number`, `avatar_uri`, `avatar_mime_type`), `get_accounts`, `get_nonce`, `get_token`; file path `avatar` read-only. The allow-list is matched by package name in `A01()`; certificate checking, if any, is not in that method (unknown). What `BS3()` tests is inferred as login state |
| `OrbitMessagesProvider` (`com.whatsapp.orbitmessages`) | file opens only with mode `r`, last segment `media`, `media_handle` values prefixed `v1.` decrypted with AES-GCM; caller checks not located (unknown) |
| `OrbitCompanionLinkActivity` | reads `getCallingPackage()` and extra `qr_data`; hold / consent timers; returns the result only (`return_result_only`) via `CompanionHelloConfirmationActivity` |
| `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | not analysed |

### 9.3 OTP handshake (`OtpRequestedReceiver`)

Expects a `PendingIntent` extra `_ci_` (caller identity) and an optional UUID `request_id` (regex checked). Records the creator package against a generated value, logs a WAM event, and, when flag **6617** is on or the package is in the list from config **7050**, answers with a broadcast `com.whatsapp.otp.OTP_HANDSHAKE_CONFIRMATION` to that package carrying the `request_id`. A missing `PendingIntent` is rejected (`PendingIntent missing from handshake Intent`). No registration check was found in this receiver.

### 9.4 `AccountTransferReceiver`

Acts only on `com.google.android.gms.auth.START_ACCOUNT_EXPORT`, only when the device has a secure keyguard and a capability check passes (`AbstractC21360rJ.A01`). The export itself runs on a background executor (`C05X.A02(...).CVx`); content unknown.

---

## 10. Ban view and appeal entry points

| Entry | Mechanism | Evidence |
|-------|-----------|----------|
| Cold start in WFAC state | `Main` state 21 starts `WfacBanActivity` through `HBC.A00` | found (3.1) |
| `BanAppealActivity` | non-exported; started by `Main` (extra `launch_source`) and by the permanent-ban flow | found |
| Ban status poll | Graph, `wfac_ban_status_token`, 5 s throttle pref `wfac_last_ban_status_fetch_timestamp_ms` | found ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 2.2) |
| Appeal submit | Graph with encrypted `user_request` (8.1) | found |
| Registration reply | `/v2/register` fields `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `custom_block_screen`, `version_upgrade` | found ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) 3.3) |
| Contact support | `LoggedOutContactFormActivity` (section 6), flag `IsRegistrationVerification` for registration errors | found |
| Deep links | `whatsapp://support`, `whatsapp://help`, `v.whatsapp.com` / `b.whatsapp.com` | found (4.2) |

The per-user identity of the appeal path is the opaque server-issued token, not a phone number or device id (the token field names above; derivation unknown).

---

## 11. Error cases and gotchas

| Symptom | Cause | Notes |
|---------|-------|-------|
| `ConnectionThread/connect/ignored/jid null and not in companion reg` | no JID and not companion registration | normal before registration; registration uses HTTPS |
| `FAIL_TO_INITIALIZE_WAMSYS` | native stack bootstrap failed (`ensureWamsysForRegBootstrapped`) | registration HTTP and pre-number funnel log are skipped |
| `DeepLinkActivity/deeplink not allowed before registration/` | link code blocked by the gate | allowlist not resolved (4.3) |
| `Request was marked with @deidentified, but no ...` | ACS / OHAI config missing | request not sent |

---

## 12. Key distinctions

| Do not confuse | Fact |
|----------------|------|
| Exported vs reachable without account | 97 exported entries; most do nothing useful until a registered account exists; only the entries in 2.2 and 4.2 have registration-state handling |
| App token vs user token | compiled `WA|<app_id>|<secret>` identifies the app; ban calls add an opaque request token, not a user session |
| `fdid` vs advertising id | `fdid` is an app-generated UUID that survives re-registration; advertising id is the Google value |
| Logged-out support form vs in-app support | the form posts to `www.whatsapp.com/contact/noclient/verification/` with typed fields; in-app support uses the session (not analysed) |
| Registration HTTP vs chat connection | registration is HTTPS `/v2/*`; a null-JID chat connect is only for companion registration |

---

## 13. Complete flow

```
[App launch / link tap]
    │  Main (only launcher)  or  DeepLinkActivity alias (wa.me, whatsapp.com/dl, v|b.whatsapp.com, whatsapp://...)
    ▼
[Main.A5W]  registration state ──► 2 regname │ 21 WFAC ban │ 41 age consent │ 45 PAA │ 50/51 login-back │ 56 username
    │  default
    ▼
[EULA]  language bottom sheet, ToS / privacy links
    │        └── /v2/pre_pn_client_log  (fdid, screens, device attrs, advertising id)   [ab_key via /v2/reg_onboard_abprop]
    ▼
[RegisterPhone]  hints / SIM number / country names (offline)
    │  /v2/exist  (fdid, fid, authkey, e_* key bundle, device attrs, gpia?)
    ▼
[VerifyPhoneNumber]  reCAPTCHA key GET (gstatic) ── /v2/code ── /v2/register
    │                        │
    │                        ├── ok  ──► RegisterName ──► account exists (leaves this report)
    │                        └── fail: violation_type / appeal_token / custom_block_screen
    │                                      │
    │                                      ▼
    │                         [WfacBanActivity / BanAppealActivity]
    │                                 Graph POST graph.whatsapp.com/graphql
    │                                 doc 4276154569100535 | 27883644401256929  (status, request_token)
    │                                 doc 38509456535312323 | 5473316762755318  (appeal, encrypted)
    ▼
[Help needed]
    LoggedOutContactFormActivity ──► POST www.whatsapp.com/contact/noclient/verification/
                                      email, message, platform=ANDROID, phone_number, debug_info, logs.tar.gz, <=3 JPEG
    ▼
[Background, any state]
    crashlogs.whatsapp.net uploads  │  static.whatsapp.net assets  │  acs.whatsapp.com (ACS/OHAI)
    DNS: system ► MNS ► secondary ► compiled table (e1..e16, g, v)
```

---

## 14. Unknowns

| Question | Why unknown |
|----------|-------------|
| Which link codes are allowed before registration | allowlist class not re-resolved; handlers check state individually, only four traced |
| Producer of reason 0 (`not_allowed_before_registration`) | not isolated in the large `DeepLinkActivity` switch |
| Host and path joining for `/v2/*`, `ENC`, `H` constants | wamsys / Kotlin request builders not read |
| Which session carries the registration-time MEX operations | null-JID connect is refused outside companion registration; the `Ash()` source is unresolved |
| Content of `from_jid` in log uploads while logged out | `AbstractC05620Al.A0G` is abstract |
| Server validation of tokens, codes, appeal payloads | server side |
| Operations carrying `@deidentified` | in `*_pando_flatbuffer_data.bin`, no schema |
| Meaning of "NTA", of the secondary id `phoneyid_id` producer, of `c2dm_reg_id` as a request field | names only |
| Whether `HomeActivity` can be launched while unregistered and what it does | base-class gate not resolved |
