# WhatsApp Account Security — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-22
**Scope:** phone-number verification into an existing account (`/v2/*` registration HTTP), second-factor methods, two-step verification PIN and recovery email, account password (`#PWD_WA` envelope, canonical-user dependency), OPAQUE / VOPRF native code and what it actually serves, passkey login and management, trusted devices, account recovery (canonical user nonce exchange), soft logout / login-back, w:mex operations (doc_ids, variables, response roots), feature flags, Baileys notes

---

## 1. What it is (technically)

"Account security" in the Android client is not one subsystem. It is five independent mechanisms layered on the phone-number registration flow. All statements are static analysis of the decompiled APK; nothing was captured on the wire. Tier: **found** = read in code or assets, **inferred** = deduced from code, **unknown** = not resolved. Obfuscated names are per-build and were re-resolved in 2.26.41.6.

| Mechanism | Where it is enforced | Credential | Main client classes (2.26.41.6) |
|-----------|---------------------|------------|-------------------------------|
| Phone verification (OTP) | registration HTTP, `/v2/exist` → `/v2/code` → `/v2/register` | SMS / voice / flash / old device / email OTP / silent auth | `K49` (`RegistrationHttpManager`), `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Second factor at registration | `/v2/register` reason `security_code`, then `VerifyTwoFactorAuth` | 6-digit PIN, account password, email OTP | `VerifyTwoFactorAuth`, `EnumC43759JAu`, `HOZ` |
| Two-step verification (PIN + email) | IQ `urn:xmpp:whatsapp:account` `<2fa>` | 6-digit PIN, optional recovery email | `C1DP` (`TwoFactorAuthManager`), `C1DT` (`TwoFactorXmppMethods`) |
| Account password | w:mex (`whatsapp-android-mex`, `whatsapp-android-www`) | 8-20 chars, letter + digit | `PasswordRepository`, `PasswordServerApiImpl`, `CanonicalPasswordService` |
| Passkey (WebAuthn) | `/v2/passkey_auth` at login; IQ `passkey` or w:mex for management | platform passkey via Credential Manager | `PasskeyServerApiImpl`, `PasskeyCreateFlow`, `PasskeyVerifier`, `K15` |
| Trusted device | w:mex | server-side record keyed by hashed `ANDROID_ID` | `TrustedDevicesServerApiImpl`, `RegTrustedDeviceGraphQLHelper` |
| Soft logout / login-back | w:mex | none (state flag) | `LogoutManager`, `LogoutPushManager` |
| Account recovery | w:mex, Meta canonical user | RSA/AES envelope of a client-generated secret | `AccountRecoveryManager` |

Two points that decide the whole report:

- The OPAQUE state machine in `libwhatsapp.so` is wired to the **end-to-end encrypted backup** password (`encb/*` handlers), not to the account password (section 6).
- The account password in this build is created and changed through `XfbWaCreatePasswordMutation` / `XfbWaChangePasswordMutation` with an RSA/AES envelope (`#PWD_WA:11`), and only if the app holds Meta canonical-user credentials (section 5).

---

## 2. Transports and operation catalog

### 2.1 Four transports

| Transport | Used for | Evidence |
|-----------|----------|----------|
| HTTPS `/v2/<name>` (registration stack) | phone verification, second factor at login, passkey assertion, device confirmation | found: path constants in `AbstractC45307Jps` (section 3.1) |
| IQ `xmlns="urn:xmpp:whatsapp:account"` | PIN / email set, check and get; account-email OTP; username etc. | found |
| IQ `xmlns="passkey"` (smax ids 125, 126, 129) | legacy passkey start / finish / clear | found, gated by flags 10452 / 10453 / 10461 |
| IQ `xmlns="w:mex"` | all GraphQL operations below | found |

### 2.2 w:mex envelope and doc_id source

Variables are sent as JSON. Almost every mutation wraps its fields in one object: helper `AbstractC197058a0.A17(obj, vars)` stores the object under the key `input` (found). Exceptions: the two `Xfb*` password mutations put `encrypted_password` under `data` (found); `PasskeyDeleteMutation` also uses `input` (via `c16770ig.A00(obj, "input")`).

doc_ids are not literals in code. The client sends the operation name plus a config name (`whatsapp-android-mex`, `whatsapp-android-www`, `whatsapp-android-facebook-schema`); the numeric id is read from `assets/whatsapp-android-{mex,www,facebook-schema}_client_persist_ids.json` (found). Every doc_id below was read from those assets in 2.26.41.6 and the operation name was checked against a call site. None is `tested`.

### 2.3 Operation catalog (call sites present)

Variables are inside `input` unless noted. "Root" is the response object name read by the client.

| Operation | doc_id | Config | Variables | Root and fields read |
|-----------|--------|--------|-----------|----------------------|
| `HasPasswordQuery` | `25379221318423478` | mex | none | `xwa2_has_password`: `has_password`, `upgrade_needed` |
| `DeletePasswordMutation` | `27247058691550586` | mex | none | `xwa2_delete_password`: `success`, `twofa_auto_disabled`; error 409 means "needs email" |
| `GetTwofaQuery` | `27608881388708005` | mex | `device_id` | `xwa2_get_twofa`: `twofa_enabled`, `twofa_methods[]{method,value,state}`, `is_device_trusted`, `latitude`, `longitude` |
| `SetTwofaMutation` | `28092515560345874` | mex | `twofa_enabled` (bool), `device_id` | `xwa2_set_twofa`: `success`, `twofa_already_enabled`, `is_device_trusted` |
| `WaPasswordEncryptionKeyQuery` | `27318258844468227` | www | none | `wa_password_encryption_key`: `public_key` (PEM), `key_id` |
| `XfbWaCreatePasswordMutation` | `36595298760118580` | www | `data.encrypted_password` (not under `input`) | `xfb_wa_create_password` (success / error fields not resolved) |
| `XfbWaChangePasswordMutation` | `27534818572826036` | www | `data.encrypted_password` | `xfb_wa_change_password` |
| `AddTrustedDeviceMutation` | `24522952587403287` | mex | `device_id`, `device_name` | `xwa2_add_trusted_device.list_of_trusted_device[]` |
| `UntrustTrustedDeviceMutation` | `26574930682133620` | mex | `device_id`, `reason` (`"REREG"` in the only call) | root not resolved |
| `DeleteTrustedDeviceMutation` | `33867503889559538` | mex | `device_id` | `xwa2_delete_trusted_device` (bool) |
| `GetTrustedDevicesQuery` | `27391232653862770` | mex | `device_id` | `xwa2_get_trusted_devices.list_of_trusted_device[]`: `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` |
| `WhatsappTrustedDeviceRegistration` | `27335489319457030` | facebook-schema | `client_mutation_id`, `payment_type="TRUST_BINDING"`, `platform_trust_token`, null `actor_id` / `logging_id` / `product_id` | payments trust binding (`RunnableC53437NtS`), not the login trusted device |
| `RegistrationPasskeyStartRegisterMutation` | `25415371271434748` | mex | none | `xwa2_passkey_start_register.credential_create` (string) |
| `RegistrationPasskeyFinishRegisterMutation` | `24611221275218156` | mex | `credential`, `key_attestation` | `xwa2_passkey_finish_register` (bool) |
| `RegistrationPasskeyEnableMutation` | `25147880151540247` | mex | `credential` | `xwa2_passkey_enable` (bool) |
| `RegistrationPasskeyClear` | `25111972538494859` | mex | none | `xwa2_passkey_clear` (bool) |
| `RegistrationPasskeyUpdateClientEncryptionStatusMutation` | `24866837389649930` | mex | `credential`, `status` (true) | `xwa2_passkey_update_client_encryption_status` (bool) |
| `PasskeyListExistResponseQuery` | `26930537423220681` | mex | none | `xwa2_passkey_exist_v2`: `result`, `uuid`, `passkeys[]{credential,create_ts_s,used_ts_s,password_manager,aaguid,usecases,is_disabled}` |
| `PasskeyDeleteMutation` | `25225683640428243` | mex | `credential_ids` (list) | `xwa2_passkey_delete.credential_ids` |
| `AccountLoginMutation` | `27298465499757127` | mex | `phone_number` (raw JID string) | not read |
| `AccountLogoutMutation` | `26863447609979194` | mex | `enabled_biometric` (bool), `phone_number` | not read; 5 s client timeout |
| `WWWTriggerAcountRecovery` | `24896267680055094` | mex | `nonce_encryption_key` (base64 PEM), `use_case`, `registration_trace_id`, `request_id` | nonce is delivered by notification (section 9) |
| `WWWExchangeNonceForAccessToken` | `25727187160203620` | mex | `nonce`, `use_case`, `encrypted_password`, `request_id`, `registration_trace_id` | access token |
| `WWWGetNonceForCompanionDevice` | `24635485196143064` | mex | `fbid`, `nonce_encryption_key`, `encrypted_password`, `request_id`, `registration_trace_id` | companion canonical user |
| `RegAccountTransferVerifyTokenMutation` | `7580940708621318` | mex | `token` | account transfer OTP check, 60 s timeout |
| `ValidateVerifierConfidence` | `25879669248324812` | mex | `authResponse` (base64) | autoconf confidence ping |
| `GetRegistrationUpsells` / `GetDynamicRegistrationUpsells` / `RegistrationDynamicUpsellShown` | `24265038133175291` / `32273353145641323` / `25435755019399064` | mex | shown: `input="PASSKEYS"` (string) | registration upsell scheduling |

### 2.4 Operations in the assets without a call site in this build

Searched in `java_src` and smali by name; no reference (found). Their variables and responses are unknown.

| Operation | doc_id |
|-----------|--------|
| `SetPasswordMutation` | `33855141324134176` |
| `CheckPasswordMutation` | `26881928138061632` |
| `PasskeyExistResponseQuery` | `25188064727509430` |
| `PasskeyRequestChallengeMutation` | `26311497405176139` |
| `PasskeyVerifyChallengeMutation` | `26876394218624479` |
| `RegistrationPasskeyDisableMutation` | `27775237998742831` |

In 2.26.41.6 a passkey login does not use the request / verify mutations; it uses `/v2/passkey_auth` (section 7.1). Payments (`PaymentsPasskey*`) and Brazil (`BrPasskey*`) passkey operations are separate surfaces and not covered.

---

## 3. Phone-number verification into an existing account

### 3.1 Registration stack and endpoints

`K49` (`RegistrationHttpManager`) builds requests and parses results. Two HTTP stacks exist: the Kotlin bridge (`KotlinRegistrationBridge`, `RetryingHttpClient`) and a native `wamsys` client reached through `AbstractC45509Jtc` and `JniBridge.jvidispatch*`. Selector `K49.A0b` returns true if config 24762 or flag **24763** is set (found); log tags end in `/kotlin` or `/wamsys`.

Paths are obfuscated with XOR 0x12 in `AbstractC45307Jps` and decode to (found):

| Path | Kotlin function | Fields sent (besides device / e2e fields) |
|------|-----------------|------------------------------------------|
| `/v2/exist` | `performSameDeviceCheck` / `checkIfExists` | `lg`, `cc`, `in`, `foa_backup_token`, `client_capabilities`, `advertising_id`, `context`, `id`, `backup_token` |
| `/v2/challenge` | `challengeRequest` | login challenge; response `login`, `challenge`, `retry_after` |
| `/v2/code` | `generateAuthCode` | `token`, `method`, `context`, `advertising_id`, `clicked_education_link`, `manage_call_permission`, `call_log_permission`, `client_start_message` |
| `/v2/register` | `registerPhoneNumber` | `code`, `auth_response` (bytes), `method`, `context`, `advertising_id`, plus map entries such as `security_code`, `reset`, `wipe_token`, `cred_token` |
| `/v2/security` | `verifySecurityCode` | `code`, `reset`, `wipe_token` (legacy path, flag 26215 off) |
| `/v2/passkey_auth` | `passkeyAuth` | `lg`, `context`, `credential` (assertion result) |
| `/v2/device_logout_send`, `/v2/device_logout_fetch` | `sendAccountDefenceDeviceConfirmation`, `fetchAccountDefenceDeviceConfirmation` | `token` |
| `/v2/wfs` | `wfsAuth` | Meta SSO ("WFS") auth, response `login`, `wa_ac_machine_id`, `lid` |
| `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop` | consent, funnel logs, silent verification, AB props | not security-specific |

### 3.2 Steps

| # | Step | Evidence |
|---|------|----------|
| 1 | `/v2/exist` returns the account state: which OTP methods are eligible, wait times, `second_factor_methods`, `is_device_trusted`, `passkey_auth_challenge`, `password_eligible`, wipe state | found (3.3) |
| 2 | If `passkey_auth_challenge` is present and not expired, the passkey login is offered (section 7.1) | found |
| 3 | User picks a method; `/v2/code` with `method` | found |
| 4 | User types the OTP; `/v2/register` with `code` and `method` | found |
| 5 | `status=ok` ends registration (`login`, `lid`, `ent_access_token`, `ent_canonical_fbid` are read from the result). `status=fail` with a reason (3.5) | found |
| 6 | Reason `security_code` means the account has a second factor: `VerifyTwoFactorAuth` collects PIN, password or email OTP and calls `/v2/register` again (3.6) | reason name found; navigation inferred |
| 7 | After success: `RegisterName`, trusted-device registration (section 8), passkey upsell (section 7.2) | found |

An "existing account" is not a separate API: the server answers `/v2/exist` and `/v2/register` for a number that already has an account with the same status / reason vocabulary. Fields such as `possible_migration`, `need_chat_restore_pn_verify`, `acc_tr_eligible` (account transfer) and `wa_old_eligible` (verify via the old phone) show that the server steers existing-account flows through the same two calls (found fields, meaning inferred from names).

### 3.3 `/v2/exist` response fields read by the client

| Field | Type | Use |
|-------|------|-----|
| `status` (`ok`/`fail`), `reason` | string | outcome |
| `login`, `lid` | string | account identifiers returned to the client (consumer not traced) |
| `is_device_trusted` | bool | stored as `pref_is_device_trusted`; hides the trusted-device checkbox |
| `second_factor_methods` | string array | stored as `pref_second_factor_methods`; values are `EnumC43759JAu` wire strings |
| `passkey_auth_challenge`, `passkey_credential` | string | challenge stored as `reg_passkey_auth_challenge` with a timestamp; credential id hint |
| `password_eligible` | int | password upsell eligibility |
| `sms_wait`, `voice_wait`, `wa_old_wait`, `email_otp_wait`, `send_sms_wait`, `silent_auth_wait`, `retry_after` | string | per-channel cooldowns |
| `sms_length`, `voice_length`, `wa_old_length`, `email_otp_length` | int | expected code length |
| `email_otp_eligible`, `wa_old_eligible`, `silent_auth_eligible`, `carrier_silent_auth_eligible`, `send_sms_eligible`, `acc_tr_eligible` | int | method eligibility |
| `email`, `wa_old_device_name` | string | masked email / old device label (masking not verified) |
| `reset_method`, `wipe_type`, `wipe_token`, `wipe_wait`, `wipe_expiry_time`, `server_time` | mixed | forgot-PIN flow (3.7) |
| `fallback_methods`, `recommended_method`, `num_visible_dbs_methods` | array / int | UI ordering |
| `ent_access_token`, `ent_canonical_fbid` (in `/v2/register`) | string | Meta canonical-user credentials |
| `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `version_upgrade`, `custom_block_screen` | mixed | ban / upgrade screens (see ban report) |

### 3.4 OTP methods

Server-driven code request sheet (`RequestServerDrivenOtpCodeBottomSheetFragment`, `C46760Kbq`) offers these `method` strings (found): `sms`, `voice`, `flash`, `wa_old`, `email_otp`, `password`, `passkey`, `send_sms`. `silent_auth` and `account transfer` have their own eligibility fields.

### 3.5 `/v2/register` failure reasons (parser in `KotlinRegistrationBridge`)

| `reason` | Meaning (found: name; meaning inferred) |
|----------|-----------------------------------------|
| `incorrect` | wrong code or wrong PIN |
| `security_code` | second factor required |
| `second_code`, `device_confirm_or_second_code` | second factor or device confirmation required |
| `too_many_guesses`, `guessed_too_fast` | rate limit on guesses; `guess_wait` returned |
| `stale`, `mismatch`, `missing`, `format_wrong` | code expired / not matching / absent / malformed |
| `sms_required` | must verify via SMS |
| `blocked`, `not_allowed`, `limited_release` | banned, disallowed, rollout gate |
| `temporarily_unavailable` | transient |
| `challenge` | challenge round required (`/v2/challenge`) |
| `reset_too_soon` | forgot-PIN reset requested too early |
| `consent`, `consent_parent_linking_already_registered` | consent screens |

### 3.6 Second-factor methods

`EnumC43759JAu` (found): `twofac_pin`, `password`, `email_otp`, `oauth_email`, `sms`, `voice`, `flash`, `wipe_full`, `wipe_offline`. With flag **28755** the screen is driven by `second_factor_methods` ("dynamic 2FA", context string `twofac_dynamic`), and "verify another way" opens `Dynamic2faMethodSelectionBottomSheet`.

`K49.A0o` (`verifySecurityCode`):

| Condition | Wire |
|-----------|------|
| flag 26215 off | legacy: `/v2/security` with `code` (and `reset`, `wipe_token` when resetting) |
| flag 26215 on, method not `password` | `/v2/register` with `security_code` = secret in clear in the request map, `method` |
| flag 26215 on, method `password` | the password is first encrypted by `HOZ.A08` into `#PWD_WA:11:<epoch>:<blob>` (section 5.3); the blob is sent in the `code` position of `/v2/register`; if encryption fails the QPL reports `PASSWORD_ENCRYPT_FAILED` |

The key for the envelope comes from `WaPasswordEncryptionKeyQuery` via `CanonicalPasswordService.A04(..., true)` (called from `C47204KjV`, found). Which request field exactly carries the blob on the wire was read from the constructor argument order, not from a captured request (inferred).

### 3.7 Forgot PIN, wipe and email reset

`/v2/exist` or `/v2/register` can return `reset_method`, `wipe_type` (`offline` or `full`), `wipe_wait` (seconds), `wipe_token`, `wipe_expiry_time`, `server_time` (found). `VerifyTwoFactorAuth.A03` maps these to four states (found): 0 not allowed, 1 in cooldown ("0_7 days, offline_info"), 2 `offline` ("7_30"), 3 `full` ("over 30"). The reset call sends `reset=<mode>` and `wipe_token`; `wipe_full` and `wipe_offline` are second-factor methods (3.6). What the server deletes on `offline` vs `full` wipe is unknown.

---

## 4. Two-step verification (PIN) and recovery email

### 4.1 Client state

`C1DP` (`TwoFactorAuthManager`) keeps the PIN locally (found): pref `two_factor_auth_code`, optionally encrypted (`two_factor_auth_using_encryption`, decrypted by `C1DP.A01` through a keystore helper). It is used for a periodic "verify your PIN" prompt: nag intervals 6 h, 12 h, 1 d, 1 d, 3 d, 7 d (`C1DP.A0I`, prefs `two_factor_auth_nag_time`, `two_factor_auth_nag_interval`). Other prefs: `two_factor_auth_email_set`, `two_factor_auth_dynamic_validated`, `two_factor_auth_last_code_correctness`, `pref_2fa_{sms,voice,flash,email_otp}_wait_time`.

### 4.2 IQ stanzas (`xmlns="urn:xmpp:whatsapp:account"`, 32 s timeout)

| Action | Stanza | Response read | Class |
|--------|--------|---------------|-------|
| Get status (smax 114) | `type=get` `<2fa/>` | `<2fa>`: child `code` present means PIN set; child `email` present sets `two_factor_auth_email_set` | `C1DT.A00`, `C28896Cgx` |
| Set PIN / email | `type=set` `<2fa><code>PIN</code><email>addr</email></2fa>` (each child optional) | success writes prefs; error code + text to listeners | `C1DP.A07`, `C28899Ch0` |
| Check PIN | `type=get` `<2fa><code>PIN</code></2fa>` | `<2fa>` containing `code` means correct | `VerifyTwoFactorAuthCodeDialogFragment` path, `HandlerC25225AtN` |

The PIN is 6 digits (`SetCodeFragment`, length check `== 6`). Set is type 1, confirm is type 2. `Fetch2FAEmailStatusJob` re-reads status (32 s) to see whether the email got verified. Whether the server returns more than `code` / `email` children is unknown.

### 4.3 Account-email OTP (separate from `<2fa><email>`)

`C31107Dfz` builds, `KRB` parses (log prefix `EmailVerificationXmppMethods`):

| Step | Stanza | Response |
|------|--------|----------|
| request OTP | `type=set` `<verify_email><lg/><lc/></verify_email>` (language / locale, 2-3 chars) | `verify_email.wait_time` |
| verify OTP | `type=get` `<verify_email><code>NNNNNN</code></verify_email>` (6 chars) | `verify_email.code_match` (`true`/`false`), `wait_time` |

The email address itself is not in these stanzas (set earlier, path not traced). Used by `VerifyEmailActivity` and the `email_otp` second factor.

### 4.4 PIN versus password versus GetTwofa

`GetTwofaQuery` returns `twofa_methods[]{method,value,state}`. `PasswordUpsellEligibility` checks for the strings `password` and `pin` in that list (found). `SetTwofaMutation` is called only after a password was created, best effort, with the hashed device id (section 5.2); `twofa_auto_enabled` / `twofa_auto_disabled` are the result flags. The PIN itself is never sent through w:mex.

---

## 5. Account password

### 5.1 Entities

| Entity | Role |
|--------|------|
| `PasswordRepository` | orchestration: `setPassword`, `getTwofa`, device id (`computeDeviceId`) |
| `PasswordServerApiImpl` | `HasPasswordQuery`, `DeletePasswordMutation`, `GetTwofaQuery`, `SetTwofaMutation` |
| `CanonicalPasswordService` | key fetch, `A03` create, `A02` change (`Xfb*` mutations, schema `whatsapp-android-www`) |
| `HOZ` | envelope encryption (`A08` → `#PWD_WA:11`) |
| `PasswordCredentialManager` | saves the credential into the Android Credential Manager (`saveCredential`, skipped without an E.164 number) |
| UI | `CreatePasswordActivity`, `ReplacePinWithPasswordActivity`, `PasswordUpgradeFragment`, `SettingsPassword`, `TrustThisDeviceActivity` |

### 5.2 Set / change / delete

`PasswordRepository.setPassword` first needs canonical credentials; without them it fails with "No canonical credentials available to set password" (found). So the password is attached to the Meta canonical user, not only to the WhatsApp number.

```
setPassword(pw, isChange, enableTwofa)
  isChange  -> CanonicalPasswordService.A02  XfbWaChangePasswordMutation
  !isChange -> CanonicalPasswordService.A03  XfbWaCreatePasswordMutation
               then, if enableTwofa: GetTwofa/SetTwofa best effort (device_id = base64(SHA-256(ANDROID_ID)))
each: A04 = key fetch (WaPasswordEncryptionKeyQuery) + HOZ.A08 -> data.encrypted_password
```

`device_id` is `K2M.A01(android_id)` = Base64 (flag 2, no wrap) of SHA-256 of `Settings.Secure.ANDROID_ID` (found). Delete sends no variables; HTTP-like code 409 maps to a "blocked, needs email" result (found). Local rules in `CreatePasswordActivity`: length 8 to 20, at least one letter and one digit, confirmation must match (found).

### 5.3 `#PWD_WA:11` envelope (`HOZ.A02` / `A08`)

```
epoch   = current time in seconds
aesKey  = random 32 B (AES-256)         iv = random 12 B
ct||tag = AES-GCM(aesKey, iv, utf8(secret))    // no AAD on this path
wrapped = RSA/ECB/PKCS1Padding(serverPublicKey, aesKey)
blob    = 0x01 | key_id(1 B) | iv(12) | len(wrapped) as uint16 LE | wrapped | tag(16) | ct
out     = "#PWD_WA:11:" + epoch + ":" + base64(blob, URL_SAFE | NO_WRAP | NO_PADDING)
```

`key_id` must be 1 to 255 (`CanonicalPasswordService.A01`). The RSA key is parsed from the PEM as an X.509 SPKI; the PKCS1 path does not check the modulus size (the ≥ 4096-bit test exists only in `HOZ.A06`, a different OAEP variant). Same envelope is used in three places (found): registration second factor (3.6), canonical create / change (5.2), and recovery (`exchangeNonce`, section 9, wrapped in JSON `{version:1,timestamp,password}`).

Other variants in `HOZ` (not `#PWD_WA:11`): `A03` and `A06` use RSA-OAEP-SHA-256 with a zero IV and AAD (the Waffle SSO path writes `#PWD_WAFFLE` in `C40069Hd8` / `C40090HdT`).

---

## 6. OPAQUE, VOPRF and the native crypto

### 6.1 What is present

| Item | Where | Tier |
|------|-------|------|
| `WESOpaqueClientRegistrationStartResult` (.rodata `0xaebae`), `...LoginStartResult` (`0xaebd5`), `...RegistrationFinishResult` (`0xaeda9`), `...LoginFinishResult` (`0xaedd1`), `...RegistrationState` (`0x115042`), `...LoginState` (`0x115072`) | `libwhatsapp.so` strings | found |
| `OPAQUE_PBKDF2_SALT` (`0x17e129`), `VOPRF06-HashToGroup-` (`0x19465a`), `VOPRF06-Finalize-` (`0x19466f`) | `libwhatsapp.so` strings | found |
| `org/whispersystems/curve25519/NativeVOPRFExtension` | same lib; Java class has `nativeBlind`, `nativeUnBlind`, `nativePcdBlind` | found |
| `libvoprf-ed25519.so`, `libvoprf-ristretto.so` | separate libs, exports `JNI_OnLoad` only; Java wrappers `com.facebook.privacy.acs.VoprfEd25519` / `VoprfRistretto` | found |

### 6.2 Functions that reference the strings (arm64, vaddr)

| Function | Size | Content | Tier |
|----------|------|---------|------|
| `fcn.0075a1c0` | 644 B | references `VOPRF06-HashToGroup-`; mbedTLS SHA-512 init / update ×6 / finish, then a second SHA-512 pass | found |
| `fcn.0075b550` | 712 B | references `VOPRF06-Finalize-` and `OPAQUE_PBKDF2_SALT`; SHA-512 over the finalize transcript, then `mbedtls_pkcs5_pbkdf2_hmac` | found |
| `fcn.0075a618`, `fcn.0075ad40` | - | both call `fcn.0075b550`, then `mbedtls_hkdf_extract` + three `mbedtls_hkdf_expand` (md type `0xb`) | found |
| `fcn.0075a0d4` | - | calls `fcn.0075a1c0` | found |

PBKDF2 call in `fcn.0075b550` (disassembly): password length `0x40` (64 B, the OPRF output), salt length `0x12` = 18 = length of the label `OPAQUE_PBKDF2_SALT` and the buffer is initialised from that label, derived length `0x40`, iteration count passed in by the caller (not a constant in this function), md type `0xb`. Md type `0xb` equals SHA-512 in the mbedTLS 3.6 numbering (inferred from the enum value and the 64-byte lengths). So the OPRF output feeds PBKDF2-HMAC-SHA-512 with the ASCII label as salt (found for the call shape, inferred for the hash).

Roles of the functions (blind, finalize, registration-finish, login-finish) are inferred from call shape. The group / ciphersuite (curve, id appended to the `VOPRF06-` prefixes), the KE1 / KE2 / KE3 byte layouts, the envelope contents and the AKE variant are **unknown**; the native code was read as disassembly of the cited functions, not decompiled.

### 6.3 Who calls it: encrypted backup, not the account password

The Java entry for the state machine is the encrypted-backup protocol (log prefix `encb/`):

| Class | Role (found) |
|-------|--------------|
| `EncBackupViewModel` | creates `C61447Rhg` (login handler) with the user's backup password string |
| `AbstractC62498S8e` | sends the IQs `sendInitRegIq`, `sendBeginRegIq`, `sendFinishRegIq`, `sendInitLoginIq`, `finishLoginOnSuccess`, `sendDeleteAccountIq` (`EncryptedBackupProtocolHelper`) |
| `C62510S8q` (smali `X/S8q`) | response handler; `jvidispatchOOO(0xb, password, ...)` returns the login state (`Rtz`), `jvidispatchOO(0x20, state)` the next message |
| `C62511S8r` | begin-login response: verifies `l2` with `l2_sig` and `ed_pub` (Ed25519), reads `count`, `backoff`, `max_attempts`, then `jvidispatchOIOOO(1, 100000L, state, ...)` |
| `RunnableC29321Co8` | finish-login: `jvidispatchOIOO(1, 100000L, state, ...)`, reads the model fields, AES-GCM decrypts the backup key, builds the proto `C25803BBm` (`backupKeyData_`, `r3_`, `opaqueChallenge_`, `transcript_`) |

`100000` is passed to the native finish calls in both register and login (found). It is the likely PBKDF2 iteration count (inferred: the native function takes it as a parameter). That these `jvidispatch` indices land in the `WESOpaque*` code is inferred from the arguments (password string in, state objects between calls, `l2` / `r3` fields) and from the absence of any other consumer; no Java symbol names OPAQUE. The account-password code (section 5) never touches them.

### 6.4 The other VOPRF: Meta ACS tokens

`NativeVOPRFExtension` and `libvoprf-ed25519.so` have Java consumers `C1N9` (`ACSTokenProviderImpl`, log prefix `ACSToken/`) and `KYL`: blinding factor, signed blinded token, DLEQ proof, unblind, shared secret (found strings `blinding_factor_string`, `shared_secret_string`, `ACSToken/processSignedBlindedToken`). Matching operations in the assets are `WaAcsGetConfig` (`27388182297440754`) and `WaAcsIssueCredentials` (`26645395115100537`); neither name appears in code, so the transport of the token request is not traced. This is an anonymous-credential token and not a password login.

### 6.5 What this means for "password login"

| Claim | Status in 2.26.41.6 |
|-------|---------------------|
| Account password login uses OPAQUE | not supported by code: the password is sent as an RSA/AES envelope (`#PWD_WA:11`), no OPAQUE message is built in the paths read; `SetPasswordMutation` and `CheckPasswordMutation` have no call site |
| A native OPAQUE client exists | found |
| It serves the encrypted-backup password | found (Java caller), binding to the native symbols inferred |
| Server stores a verifier instead of the password for the account password | unknown |

Java strings that look like OPAQUE evidence but are unrelated (found): `opaqueChallenge_` (backup bootstrap proto above), `opaquePayload_` (`C61318RfY`, tethered migration frame), `OpaqueConfig` / `prefersOpaqueConfig` (bitmap config in `EnumC167127Ba`), `OpaqueKey(` (`C44715Jfl`, a string wrapper), `KE1` (`X.KE1` is an Android Compose class), `opaque_client_data` (history-sync column).

---

## 7. Passkeys (WebAuthn)

### 7.1 Login at registration time

| Step | Evidence |
|------|----------|
| `/v2/exist` returns `passkey_auth_challenge`; `K15.A03` accepts it while younger than `SignalCredentialStateController.MAX_RETRY_TIME` | found |
| `PasskeyVerifier.onPasskeyChallengeReceived` runs a discoverable-credential assertion through `androidx.credentials` (`PasskeyLowLevelAndroidApiImpl.loginWithPasskey`); stage kept in pref `passkey_login_stage` | found |
| `K49.A0l` posts the result as `credential` to `/v2/passkey_auth` | found |
| Response: `status` (`ok`/`fail`), `reason` (`temporarily_unavailable`, `disabled`), `credential_create` (string), `login`, `cred_token` | found |
| `cred_token` is stored per phone number in `passkey_disabled_cred_token_map` and sent back as `cred_token` on later requests when flag **25565** is on | found; purpose (prove a passkey was disabled) inferred |

Client-side outcomes are logged as `passkey_client_login_{cancelled,nopasskey,ineligible,error,success}`. `prepareGetCredential` is used only on Android 14+ (SDK 34) and flag **21638** (found).

### 7.2 Create and manage

Upsell after the 2FA step: `VerifyTwoFactorAuth.onCheckPasskeyUpsellAfter2FA` uses `PasskeyCreateEducationScreen` or a bottom sheet; flag **20409** switches between the control flow and the quick-promotion (QP) path, flag **16591** adds an eligibility check (found).

| Operation | MEX gate | IQ fallback (`xmlns="passkey"`) |
|-----------|----------|---------------------------------|
| start register | flag **10453** | smax 125, `type=get` |
| finish register | flag **10452** | smax 126, `type=set` |
| clear | flag **10461** | smax 129, `type=set` |
| list / exists, delete, enable, update encryption status | always MEX | none |

`credential_create` from start-register is cached in `passkey_create_challenge`. Finish register sends `credential` and `key_attestation`; the attestation payload is built only if flag **28809** is on (base64 of the key attestation, `getKeyAttestationPayload`). Flag **8877** wraps start / finish in a retry / timeout helper (`C29707Cw7`, role inferred). `PasskeyRandomizedDailyCronJob` and `PasskeyExistsCache` refresh the exists list; the exists response stores `uuid` in `reg_passkey_exists_uuid`.

### 7.3 PRF and client-side encryption

`PasskeyPrfSecrets` uses the static PRF input `WhatsAppPasskeyStaticPrfInputV1` and stores a PRF-derived root key in `prf_derived_root_key.key` (encapsulation key label `prf_derived_root_key_file_encapsulation_key`). `RegistrationPasskeyUpdateClientEncryptionStatusMutation` tells the server the passkey is used for client-side encryption. The consumer is the encrypted-backup flow (`VerifyPasskeyFragment`, inferred from the class location).

---

## 8. Trusted devices

| Item | Value |
|------|-------|
| `device_id` | `Base64(SHA-256(ANDROID_ID))` (no wrap), `K2M.A01` |
| `device_name` | `<MANUFACTURER>-<MODEL>` (`HO4.A00`) |
| Checkbox | shown on `VerifyPhoneNumber` and `VerifyTwoFactorAuth` when flag **30530** is on and `pref_is_device_trusted` is false; prefs `pref_trusted_device_checkbox_shown` / `_checked` |
| Registration completion (`RegisterName`) | opted in: `AddTrustedDeviceMutation`; not opted in: `UntrustTrustedDeviceMutation` with `reason="REREG"` (`C29652Cu9`, found) |
| Settings | `TrustedDevicesRepository` lists (`GetTrustedDevicesQuery`) and removes (`DeleteTrustedDeviceMutation`); `TrustThisDeviceActivity` |
| Effect | `is_device_trusted` is returned by `/v2/exist`, `/v2/register`, `GetTwofa` and `SetTwofa`; the client uses it to skip the checkbox. That a trusted device skips the PIN / password prompt is inferred; no client code skips the second factor |

`list_of_trusted_device[]` entries carry `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` (location of last use is server-provided; how it is derived is unknown).

---

## 9. Account recovery (Meta canonical user)

`AccountRecoveryManager` does not recover WhatsApp chats or the phone-number account. It re-creates the Meta canonical-user credentials of an FB-linked account (found).

| Step | Detail |
|------|--------|
| Trigger | `maybeRecoverAccount`: no canonical user, or credentials invalid; deferred variant gated by flag **16017** |
| Client key | generates a key pair, sends the public key (PEM, base64) as `nonce_encryption_key` in `WWWTriggerAcountRecovery` with `use_case`, `registration_trace_id`, `request_id` |
| Nonce | arrives by notification; timeout produces "Account Recovery Failed due to Nonce notification timeout" |
| Exchange | `WWWExchangeNonceForAccessToken` with `nonce`, `use_case`, `request_id`, `registration_trace_id`, `encrypted_password` = `#PWD_WA:11` envelope of a random client secret inside JSON `{version:1,timestamp,password}` |
| Companion | `WWWGetNonceForCompanionDevice`, `WWWTradeNonceForAccessTokens` do the same for linked devices (`CompanionCanonicalUserNonceManager`, `CompanionCanonicalUserAccessTokenJob`) |
| Related | `WWWValidateCanonicalUser`, `WWWCanonicalUserValid`, `WWWAppGenerateCanonicalNonce` (call sites exist; fields not read) |

The spelling `Acount` is WhatsApp's own. What the nonce encryption key algorithm is (the pair comes from `N6T.A02`) is not resolved.

---

## 10. Login and logout

`LogoutManager` implements a soft logout (multi-account) and the login-back path (found).

| Action | Wire | Notes |
|--------|------|-------|
| Logout | `AccountLogoutMutation` `{phone_number, enabled_biometric}` | `enabled_biometric` from a biometric setting; 5 s timeout, then logout proceeds locally ("timed out, proceeding with logout") |
| Push | `LogoutPushManager` disables / re-enables GCM push (`"re-enable"` on revert) | found |
| Local | `markCurrentAccountLoggedOut`, `removeLoggedOutAccountWithCleanup`, `deleteGmsBackupState`, optional chat deletion UI (`DeleteChatsOnLogoutDialog`, `LoggedOutChatsFragmentDialog`) | found |
| Login back | `AccountLoginMutation` `{phone_number}`, then `loginBack` → `actionReconnect`; wait up to 7 s for the connection | `PrimaryLoginBackActivity` |

It is a state flag on the server side of a multi-account setup, not the phone-number login of section 3 and not the removal of a linked device. Flag **28385** is read in `LogoutManager` (role unresolved).

---

## 11. Feature flags

IDs are bold. Types: B = boolean AB prop, C = config. Names are not in the client; the role is what the code does with the flag.

| ID | Where | Controls |
|----|-------|----------|
| **24762** (C) / **24763** (B) | `K49.A0b` | Kotlin registration stack instead of native `wamsys` |
| **26215** | `K49` verify / reset security code | registration second factor over `/v2/register`, enables password envelope; off = legacy `/v2/security` |
| **25565** | `K49.A0M` | send stored `cred_token` |
| **28755** | `VerifyTwoFactorAuth` | dynamic 2FA method selection from `second_factor_methods` |
| **30530** | `VerifyPhoneNumber`, `VerifyTwoFactorAuth` | trusted-device checkbox |
| **20409** | `VerifyTwoFactorAuth` | post-2FA QP passkey upsell vs control |
| **16591** | `VerifyTwoFactorAuth` | passkey eligibility check before upsell |
| **21638** | `PasskeyAndroidApi` | `prepareGetCredential` (Android 14+) |
| **10452** / **10453** / **10461** | `PasskeyServerApiImpl` | MEX instead of IQ for finish / start / clear |
| **28809** | `PasskeyServerApiImpl` | key attestation payload |
| **8877**, **31281** | `PasskeyCreateFlow` | retry wrapper; alternate payments-passkey path (roles inferred) |
| **5156** | `SetCodeFragment` | offer "add email" after PIN set |
| **5711** | `TwoFactorAuthActivity`, `SetCodeFragment` | layout only (hides page indicator) |
| **16017** | `AccountRecoveryManager` | deferred nonce processing |
| **28385** | `LogoutManager` | unresolved |

---

## 12. Error cases

| Symptom | Cause | Fix / note |
|---------|-------|------------|
| `/v2/register` reason `security_code` or `second_code` | account has a second factor | send PIN / password / email OTP via `/v2/register` (3.6) |
| `PASSWORD_ENCRYPT_FAILED` (QPL) | key fetch failed, `key_id` outside 1-255, or crypto exception (`encryptRegistrationPassword/*` logs) | retry; the client aborts the attempt |
| `reset_too_soon` | forgot-PIN reset before `wipe_wait` elapsed | wait; UI state 1 |
| `too_many_guesses` / `guessed_too_fast` | PIN or OTP guess limit | wait `guess_wait` |
| `No canonical credentials available to set password` | no Meta canonical user on the device | complete the canonical-user setup first |
| Password create / change failed | `xfb_wa_*` payload not successful; error code mapped by `CanonicalPasswordService.A00` | UI error enum `EnumC49982M3j` |
| `DeletePassword` 409 | account email required before removal | add email first |
| `Account Recovery Failed due to Nonce notification timeout` | notification not received | retry trigger |
| `...passwordPublicKeyStr is null` / `passwordKeyIdStr is null` | encryption certificate missing in the recovery exchange | retry |
| `LogoutManager/callLogoutApi/timed out` | no response in 5 s | logout continues locally |
| Passkey: `NoCredentialException`, `NotAllowedError`, GMS too old, Play services missing | Credential Manager failures | falls back to other methods |

---

## 13. Key distinctions

| A | B |
|---|---|
| OPAQUE native code (encrypted-backup password, HSM `encb/*` IQs) | account password (`XfbWa*` + `#PWD_WA:11`) |
| `libvoprf-*.so` + `NativeVOPRFExtension` (ACS anonymous tokens) | OPAQUE state machine (`WESOpaque*`) |
| PIN (IQ `<2fa>`, 6 digits) | password (w:mex, 8-20 chars) |
| `<2fa><email>` (recovery email for PIN reset) | `<verify_email>` OTP flow and `email_otp` second factor |
| `SetTwofaMutation` (flag per device id after password) | PIN set IQ |
| Trusted device (login, `AddTrustedDeviceMutation`) | `WhatsappTrustedDeviceRegistration` (payments trust binding) |
| `AccountLogoutMutation` (soft logout) | unlinking a companion (`remove-companion-device`) and ban logout |
| `WWWTriggerAcountRecovery` (canonical user credentials) | forgot-PIN wipe (`wipe_*`, `/v2/security`) |
| `#PWD_WA:11` (WhatsApp) | `#PWD_WAFFLE` (Waffle SSO) |
| `PasskeyServerApiImpl` ops (account passkeys) | `PaymentsPasskey*`, `BrPasskey*` |
| `/v2/passkey_auth` (login assertion) | `PasskeyRequestChallengeMutation` / `PasskeyVerifyChallengeMutation` (no call site) |

---

## 14. Baileys (`baron-baileys-v2`)

Compared against `src/Socket/privacy.js` and `src/Socket/registration.js`.

| Item | APK 2.26.41.6 | Baileys | Result |
|------|---------------|---------|--------|
| doc_ids for trusted devices, login, logout, passwords, passkeys | assets | same numbers | match |
| `accountLogin` / `accountLogout` | `input{phone_number}` / `input{phone_number, enabled_biometric}` | same | match |
| `getTrustedDevices` | `input{device_id}` always sent | `{}` | differs; server behaviour without `device_id` unknown |
| `untrustTrustedDevice` default reason | `"REREG"` in the only call | `'USER_INITIATED'` | differs, other reasons unknown |
| passkey ops | variables `credential`, `key_attestation`, `credential_ids`; roots `xwa2_passkey_*` | none implemented in the files read | use APK shapes |
| `SetPassword` / `CheckPassword` | no call site | doc_ids only | unverified, do not rely on |
| `#PWD_WA:11` encryption | section 5.3 | not present in the `src` tree read | implement from section 5.3 |

Why a standalone client fails on these paths (inferred, nothing tested): registration endpoints expect the e2e-protected request fields the app builds (`C45446JsB`); password and recovery calls need canonical-user credentials; passkey assertion needs a platform authenticator.

---

## 15. Complete flows

### 15.1 Verify a number that already has an account

```
[User]            [Client]                                   [Server]
  │ enter number    │                                           │
  ▼                 ▼                                           │
            POST /v2/exist ───────────────────────────────────►│
                    │◄── methods, waits, second_factor_methods, │
                    │    passkey_auth_challenge, is_device_trusted
  passkey? ─yes──►  Credential Manager assertion                │
                    POST /v2/passkey_auth {credential} ────────►│
                    │◄── status, login, cred_token              │
  no                ▼                                           │
            POST /v2/code {method} ─────────────────────────────►│  OTP sent (sms/voice/flash/wa_old/email_otp)
  type OTP ──►  POST /v2/register {code, method} ───────────────►│
                    │◄── ok | fail(reason)                      │
   reason=security_code / second_code                           │
  PIN / password ─► POST /v2/register {security_code | #PWD_WA blob, method}
                    │◄── ok (login, lid, ent_access_token)      │
                    ▼                                           │
        optional: AddTrustedDeviceMutation | UntrustTrustedDeviceMutation(REREG)
        optional: passkey upsell -> StartRegister -> Credential Manager -> FinishRegister
  forgot PIN ─────► reset=<mode>, wipe_token (after wipe_wait) ─►│
```

### 15.2 Set a PIN and recovery email

```
[Client]  IQ get <2fa/> ───────────────► [Server]  <2fa>[<code/>][<email/>]
[Client]  IQ set <2fa><code>NNNNNN</code><email>x</email></2fa> ──► ok | error(code,text)
[Client]  Fetch2FAEmailStatusJob: IQ get <2fa/> until <email> present
[Client]  IQ get <2fa><code>NNNNNN</code></2fa> ──► <2fa><code/></2fa> = correct   (periodic reminder)
```

### 15.3 Create an account password

```
[Client]  canonical credentials present? ── no ─► fail
[Client]  WaPasswordEncryptionKeyQuery ──► public_key (PEM), key_id (1..255)
[Client]  HOZ.A08: AES-GCM + RSA-PKCS1 wrap -> "#PWD_WA:11:<epoch>:<blob>"
[Client]  XfbWaCreatePasswordMutation {data:{encrypted_password}} ──► success
[Client]  (best effort) GetTwofaQuery / SetTwofaMutation {input:{twofa_enabled:true, device_id}}
```

---

## 16. Unknowns

| Topic | Reason |
|-------|--------|
| OPAQUE ciphersuite (group, id after `VOPRF06-`), KE1 / KE2 / KE3 and envelope layouts, AKE variant | native, read as disassembly of 4 functions only |
| Binding of the encrypted-backup `jvidispatch` indices to the `WESOpaque*` code | by argument shape, not by symbol |
| PBKDF2 iteration count for the OPAQUE KSF | passed as a parameter; `100000` is the literal passed by the Java callers |
| Whether any path sends a password through OPAQUE for the account password | no such path found; wrappers hidden behind numeric dispatch cannot be excluded |
| Responses of `XfbWa*`, `AccountLogin`, `AccountLogout`, `UntrustTrustedDevice` | root and fields not read |
| Operations without call site (2.4) | variables and responses unknown |
| Exact field that carries the `#PWD_WA` blob in `/v2/register` | derived from constructor order |
| Meaning of `login`, `lid` fields returned by `/v2/exist` and `/v2/passkey_auth` | consumers not traced |
| Effect of `wipe_full` / `wipe_offline` on the server | client shows text only |
| Whether a trusted device skips the second factor | server-side; no client skip logic |
| Algorithm of the recovery key pair (`N6T.A02`) | not read |
| Roles of flags 8877, 31281, 28385 | gates only |
| Actual traffic | static analysis only |
