<!-- src-sha1: b8a925dee480430088a421b7aba690bc2f641a5f -->
# WhatsApp Kontosicherheit — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-22
**Umfang:** Verifizierung der Telefonnummer für ein bestehendes Konto (`/v2/*` Registrierungs-HTTP), Second-Factor-Methoden, Zwei-Schritt-Verifizierung mit PIN und Wiederherstellungs-E-Mail, Kontopasswort (`#PWD_WA`-Envelope, Abhängigkeit vom Canonical User), OPAQUE- / VOPRF-Nativcode und wofür er tatsächlich dient, Passkey-Login und -Verwaltung, vertrauenswürdige Geräte, Kontowiederherstellung (Nonce-Austausch des Canonical User), Soft Logout / Login-Back, w:mex-Operationen (doc_ids, Variablen, Response-Roots), Feature-Flags, Baileys-Hinweise

---

## 1. Was es ist (technisch)

"Kontosicherheit" im Android-Client ist kein einzelnes Subsystem. Es sind fünf unabhängige Mechanismen, die auf dem Registrierungsablauf per Telefonnummer aufsetzen. Alle Aussagen beruhen auf statischer Analyse des dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tier: **found** = im Code oder in Assets gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 neu aufgelöst.

| Mechanismus | Wo er durchgesetzt wird | Credential | Wichtigste Client-Klassen (2.26.41.6) |
|-----------|---------------------|------------|-------------------------------|
| Telefon-Verifizierung (OTP) | Registrierungs-HTTP, `/v2/exist` → `/v2/code` → `/v2/register` | SMS / Sprachanruf / Flash / altes Gerät / E-Mail-OTP / Silent Auth | `K49` (`RegistrationHttpManager`), `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Second Factor bei der Registrierung | `/v2/register` Reason `security_code`, danach `VerifyTwoFactorAuth` | 6-stellige PIN, Kontopasswort, E-Mail-OTP | `VerifyTwoFactorAuth`, `EnumC43759JAu`, `HOZ` |
| Zwei-Schritt-Verifizierung (PIN + E-Mail) | IQ `urn:xmpp:whatsapp:account` `<2fa>` | 6-stellige PIN, optionale Wiederherstellungs-E-Mail | `C1DP` (`TwoFactorAuthManager`), `C1DT` (`TwoFactorXmppMethods`) |
| Kontopasswort | w:mex (`whatsapp-android-mex`, `whatsapp-android-www`) | 8-20 Zeichen, Buchstabe + Ziffer | `PasswordRepository`, `PasswordServerApiImpl`, `CanonicalPasswordService` |
| Passkey (WebAuthn) | `/v2/passkey_auth` beim Login; IQ `passkey` oder w:mex für die Verwaltung | Plattform-Passkey über Credential Manager | `PasskeyServerApiImpl`, `PasskeyCreateFlow`, `PasskeyVerifier`, `K15` |
| Vertrauenswürdiges Gerät | w:mex | serverseitiger Eintrag, geschlüsselt über gehashte `ANDROID_ID` | `TrustedDevicesServerApiImpl`, `RegTrustedDeviceGraphQLHelper` |
| Soft Logout / Login-Back | w:mex | keines (Status-Flag) | `LogoutManager`, `LogoutPushManager` |
| Kontowiederherstellung | w:mex, Meta Canonical User | RSA/AES-Envelope eines clientseitig erzeugten Secrets | `AccountRecoveryManager` |

Zwei Punkte, die den gesamten Report entscheiden:

- Die OPAQUE-State-Machine in `libwhatsapp.so` ist an das Passwort des **Ende-zu-Ende-verschlüsselten Backups** (`encb/*`-Handler) gebunden, nicht an das Kontopasswort (Abschnitt 6).
- Das Kontopasswort wird in diesem Build über `XfbWaCreatePasswordMutation` / `XfbWaChangePasswordMutation` mit einem RSA/AES-Envelope (`#PWD_WA:11`) erstellt und geändert, und nur, wenn die App Meta-Canonical-User-Credentials besitzt (Abschnitt 5).

---

## 2. Transporte und Operationskatalog

### 2.1 Vier Transporte

| Transport | Verwendet für | Evidenz |
|-----------|----------|----------|
| HTTPS `/v2/<name>` (Registrierungs-Stack) | Telefon-Verifizierung, Second Factor beim Login, Passkey-Assertion, Gerätebestätigung | found: Pfadkonstanten in `AbstractC45307Jps` (Abschnitt 3.1) |
| IQ `xmlns="urn:xmpp:whatsapp:account"` | PIN / E-Mail setzen, prüfen und abrufen; Konto-E-Mail-OTP; Username usw. | found |
| IQ `xmlns="passkey"` (smax-IDs 125, 126, 129) | Legacy-Passkey start / finish / clear | found, durch Flags 10452 / 10453 / 10461 gesteuert |
| IQ `xmlns="w:mex"` | alle unten aufgeführten GraphQL-Operationen | found |

### 2.2 w:mex-Envelope und doc_id-Quelle

Variablen werden als JSON gesendet. Fast jede Mutation packt ihre Felder in ein Objekt: Der Helper `AbstractC197058a0.A17(obj, vars)` legt das Objekt unter dem Schlüssel `input` ab (found). Ausnahmen: Die beiden `Xfb*`-Passwort-Mutationen legen `encrypted_password` unter `data` ab (found); `PasskeyDeleteMutation` verwendet ebenfalls `input` (über `c16770ig.A00(obj, "input")`).

doc_ids stehen nicht als Literale im Code. Der Client sendet den Operationsnamen plus einen Config-Namen (`whatsapp-android-mex`, `whatsapp-android-www`, `whatsapp-android-facebook-schema`); die numerische ID wird aus `assets/whatsapp-android-{mex,www,facebook-schema}_client_persist_ids.json` gelesen (found). Jede doc_id unten wurde in 2.26.41.6 aus diesen Assets gelesen, und der Operationsname wurde gegen eine Aufrufstelle geprüft. Keine ist `tested`.

### 2.3 Operationskatalog (Aufrufstellen vorhanden)

Variablen liegen innerhalb von `input`, sofern nicht anders angegeben. "Root" ist der vom Client gelesene Name des Response-Objekts.

| Operation | doc_id | Config | Variablen | Root und gelesene Felder |
|-----------|--------|--------|-----------|----------------------|
| `HasPasswordQuery` | `25379221318423478` | mex | keine | `xwa2_has_password`: `has_password`, `upgrade_needed` |
| `DeletePasswordMutation` | `27247058691550586` | mex | keine | `xwa2_delete_password`: `success`, `twofa_auto_disabled`; Fehler 409 bedeutet "braucht E-Mail" |
| `GetTwofaQuery` | `27608881388708005` | mex | `device_id` | `xwa2_get_twofa`: `twofa_enabled`, `twofa_methods[]{method,value,state}`, `is_device_trusted`, `latitude`, `longitude` |
| `SetTwofaMutation` | `28092515560345874` | mex | `twofa_enabled` (bool), `device_id` | `xwa2_set_twofa`: `success`, `twofa_already_enabled`, `is_device_trusted` |
| `WaPasswordEncryptionKeyQuery` | `27318258844468227` | www | keine | `wa_password_encryption_key`: `public_key` (PEM), `key_id` |
| `XfbWaCreatePasswordMutation` | `36595298760118580` | www | `data.encrypted_password` (nicht unter `input`) | `xfb_wa_create_password` (Erfolgs- / Fehlerfelder nicht aufgelöst) |
| `XfbWaChangePasswordMutation` | `27534818572826036` | www | `data.encrypted_password` | `xfb_wa_change_password` |
| `AddTrustedDeviceMutation` | `24522952587403287` | mex | `device_id`, `device_name` | `xwa2_add_trusted_device.list_of_trusted_device[]` |
| `UntrustTrustedDeviceMutation` | `26574930682133620` | mex | `device_id`, `reason` (`"REREG"` im einzigen Aufruf) | Root nicht aufgelöst |
| `DeleteTrustedDeviceMutation` | `33867503889559538` | mex | `device_id` | `xwa2_delete_trusted_device` (bool) |
| `GetTrustedDevicesQuery` | `27391232653862770` | mex | `device_id` | `xwa2_get_trusted_devices.list_of_trusted_device[]`: `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` |
| `WhatsappTrustedDeviceRegistration` | `27335489319457030` | facebook-schema | `client_mutation_id`, `payment_type="TRUST_BINDING"`, `platform_trust_token`, null `actor_id` / `logging_id` / `product_id` | Payments-Trust-Binding (`RunnableC53437NtS`), nicht das Login-Trusted-Device |
| `RegistrationPasskeyStartRegisterMutation` | `25415371271434748` | mex | keine | `xwa2_passkey_start_register.credential_create` (String) |
| `RegistrationPasskeyFinishRegisterMutation` | `24611221275218156` | mex | `credential`, `key_attestation` | `xwa2_passkey_finish_register` (bool) |
| `RegistrationPasskeyEnableMutation` | `25147880151540247` | mex | `credential` | `xwa2_passkey_enable` (bool) |
| `RegistrationPasskeyClear` | `25111972538494859` | mex | keine | `xwa2_passkey_clear` (bool) |
| `RegistrationPasskeyUpdateClientEncryptionStatusMutation` | `24866837389649930` | mex | `credential`, `status` (true) | `xwa2_passkey_update_client_encryption_status` (bool) |
| `PasskeyListExistResponseQuery` | `26930537423220681` | mex | keine | `xwa2_passkey_exist_v2`: `result`, `uuid`, `passkeys[]{credential,create_ts_s,used_ts_s,password_manager,aaguid,usecases,is_disabled}` |
| `PasskeyDeleteMutation` | `25225683640428243` | mex | `credential_ids` (Liste) | `xwa2_passkey_delete.credential_ids` |
| `AccountLoginMutation` | `27298465499757127` | mex | `phone_number` (roher JID-String) | nicht gelesen |
| `AccountLogoutMutation` | `26863447609979194` | mex | `enabled_biometric` (bool), `phone_number` | nicht gelesen; 5 s Client-Timeout |
| `WWWTriggerAcountRecovery` | `24896267680055094` | mex | `nonce_encryption_key` (base64 PEM), `use_case`, `registration_trace_id`, `request_id` | Nonce wird per Notification zugestellt (Abschnitt 9) |
| `WWWExchangeNonceForAccessToken` | `25727187160203620` | mex | `nonce`, `use_case`, `encrypted_password`, `request_id`, `registration_trace_id` | Access Token |
| `WWWGetNonceForCompanionDevice` | `24635485196143064` | mex | `fbid`, `nonce_encryption_key`, `encrypted_password`, `request_id`, `registration_trace_id` | Companion Canonical User |
| `RegAccountTransferVerifyTokenMutation` | `7580940708621318` | mex | `token` | OTP-Prüfung für Kontotransfer, 60 s Timeout |
| `ValidateVerifierConfidence` | `25879669248324812` | mex | `authResponse` (base64) | Autoconf-Confidence-Ping |
| `GetRegistrationUpsells` / `GetDynamicRegistrationUpsells` / `RegistrationDynamicUpsellShown` | `24265038133175291` / `32273353145641323` / `25435755019399064` | mex | shown: `input="PASSKEYS"` (String) | Scheduling der Registrierungs-Upsells |

### 2.4 Operationen in den Assets ohne Aufrufstelle in diesem Build

Per Name in `java_src` und Smali gesucht; keine Referenz (found). Variablen und Responses sind unbekannt.

| Operation | doc_id |
|-----------|--------|
| `SetPasswordMutation` | `33855141324134176` |
| `CheckPasswordMutation` | `26881928138061632` |
| `PasskeyExistResponseQuery` | `25188064727509430` |
| `PasskeyRequestChallengeMutation` | `26311497405176139` |
| `PasskeyVerifyChallengeMutation` | `26876394218624479` |
| `RegistrationPasskeyDisableMutation` | `27775237998742831` |

In 2.26.41.6 verwendet ein Passkey-Login nicht die Request- / Verify-Mutationen, sondern `/v2/passkey_auth` (Abschnitt 7.1). Payments-Passkey-Operationen (`PaymentsPasskey*`) und Brasilien-Passkey-Operationen (`BrPasskey*`) sind separate Oberflächen und nicht abgedeckt.

---

## 3. Verifizierung der Telefonnummer für ein bestehendes Konto

### 3.1 Registrierungs-Stack und Endpunkte

`K49` (`RegistrationHttpManager`) baut Requests und parst Ergebnisse. Es gibt zwei HTTP-Stacks: die Kotlin-Bridge (`KotlinRegistrationBridge`, `RetryingHttpClient`) und einen nativen `wamsys`-Client, erreichbar über `AbstractC45509Jtc` und `JniBridge.jvidispatch*`. Der Selektor `K49.A0b` liefert true, wenn Config 24762 oder Flag **24763** gesetzt ist (found); Log-Tags enden auf `/kotlin` oder `/wamsys`.

Die Pfade sind in `AbstractC45307Jps` mit XOR 0x12 obfuskiert und dekodieren zu (found):

| Pfad | Kotlin-Funktion | Gesendete Felder (neben Geräte- / e2e-Feldern) |
|------|-----------------|------------------------------------------|
| `/v2/exist` | `performSameDeviceCheck` / `checkIfExists` | `lg`, `cc`, `in`, `foa_backup_token`, `client_capabilities`, `advertising_id`, `context`, `id`, `backup_token` |
| `/v2/challenge` | `challengeRequest` | Login-Challenge; Response `login`, `challenge`, `retry_after` |
| `/v2/code` | `generateAuthCode` | `token`, `method`, `context`, `advertising_id`, `clicked_education_link`, `manage_call_permission`, `call_log_permission`, `client_start_message` |
| `/v2/register` | `registerPhoneNumber` | `code`, `auth_response` (Bytes), `method`, `context`, `advertising_id`, dazu Map-Einträge wie `security_code`, `reset`, `wipe_token`, `cred_token` |
| `/v2/security` | `verifySecurityCode` | `code`, `reset`, `wipe_token` (Legacy-Pfad, Flag 26215 aus) |
| `/v2/passkey_auth` | `passkeyAuth` | `lg`, `context`, `credential` (Assertion-Ergebnis) |
| `/v2/device_logout_send`, `/v2/device_logout_fetch` | `sendAccountDefenceDeviceConfirmation`, `fetchAccountDefenceDeviceConfirmation` | `token` |
| `/v2/wfs` | `wfsAuth` | Meta-SSO-Auth ("WFS"), Response `login`, `wa_ac_machine_id`, `lid` |
| `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop` | Consent, Funnel-Logs, Silent Verification, AB-Props | nicht sicherheitsspezifisch |

### 3.2 Schritte

| # | Schritt | Evidenz |
|---|------|----------|
| 1 | `/v2/exist` liefert den Kontostatus: welche OTP-Methoden zulässig sind, Wartezeiten, `second_factor_methods`, `is_device_trusted`, `passkey_auth_challenge`, `password_eligible`, Wipe-Status | found (3.3) |
| 2 | Ist `passkey_auth_challenge` vorhanden und nicht abgelaufen, wird der Passkey-Login angeboten (Abschnitt 7.1) | found |
| 3 | Der Nutzer wählt eine Methode; `/v2/code` mit `method` | found |
| 4 | Der Nutzer tippt das OTP; `/v2/register` mit `code` und `method` | found |
| 5 | `status=ok` beendet die Registrierung (`login`, `lid`, `ent_access_token`, `ent_canonical_fbid` werden aus dem Ergebnis gelesen). `status=fail` mit einem Reason (3.5) | found |
| 6 | Reason `security_code` bedeutet, dass das Konto einen Second Factor hat: `VerifyTwoFactorAuth` sammelt PIN, Passwort oder E-Mail-OTP und ruft `/v2/register` erneut auf (3.6) | Reason-Name found; Navigation inferred |
| 7 | Nach Erfolg: `RegisterName`, Registrierung des vertrauenswürdigen Geräts (Abschnitt 8), Passkey-Upsell (Abschnitt 7.2) | found |

Ein "bestehendes Konto" ist keine separate API: Der Server beantwortet `/v2/exist` und `/v2/register` für eine Nummer, die bereits ein Konto hat, mit demselben Status- / Reason-Vokabular. Felder wie `possible_migration`, `need_chat_restore_pn_verify`, `acc_tr_eligible` (Kontotransfer) und `wa_old_eligible` (Verifizierung über das alte Telefon) zeigen, dass der Server Abläufe für bestehende Konten über dieselben zwei Aufrufe steuert (Felder found, Bedeutung aus Namen inferred).

### 3.3 Vom Client gelesene `/v2/exist`-Response-Felder

| Feld | Typ | Verwendung |
|-------|------|-----|
| `status` (`ok`/`fail`), `reason` | String | Ergebnis |
| `login`, `lid` | String | an den Client zurückgegebene Konto-Identifier (Verbraucher nicht verfolgt) |
| `is_device_trusted` | bool | gespeichert als `pref_is_device_trusted`; blendet die Trusted-Device-Checkbox aus |
| `second_factor_methods` | String-Array | gespeichert als `pref_second_factor_methods`; Werte sind `EnumC43759JAu`-Wire-Strings |
| `passkey_auth_challenge`, `passkey_credential` | String | Challenge gespeichert als `reg_passkey_auth_challenge` mit Zeitstempel; Credential-ID-Hinweis |
| `password_eligible` | int | Eignung für Passwort-Upsell |
| `sms_wait`, `voice_wait`, `wa_old_wait`, `email_otp_wait`, `send_sms_wait`, `silent_auth_wait`, `retry_after` | String | Cooldowns pro Kanal |
| `sms_length`, `voice_length`, `wa_old_length`, `email_otp_length` | int | erwartete Code-Länge |
| `email_otp_eligible`, `wa_old_eligible`, `silent_auth_eligible`, `carrier_silent_auth_eligible`, `send_sms_eligible`, `acc_tr_eligible` | int | Methodeneignung |
| `email`, `wa_old_device_name` | String | maskierte E-Mail / Label des alten Geräts (Maskierung nicht verifiziert) |
| `reset_method`, `wipe_type`, `wipe_token`, `wipe_wait`, `wipe_expiry_time`, `server_time` | gemischt | Forgot-PIN-Ablauf (3.7) |
| `fallback_methods`, `recommended_method`, `num_visible_dbs_methods` | Array / int | UI-Reihenfolge |
| `ent_access_token`, `ent_canonical_fbid` (in `/v2/register`) | String | Meta-Canonical-User-Credentials |
| `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `version_upgrade`, `custom_block_screen` | gemischt | Ban- / Upgrade-Screens (siehe Ban-Report) |

### 3.4 OTP-Methoden

Das serverseitig gesteuerte Code-Anfrage-Sheet (`RequestServerDrivenOtpCodeBottomSheetFragment`, `C46760Kbq`) bietet diese `method`-Strings an (found): `sms`, `voice`, `flash`, `wa_old`, `email_otp`, `password`, `passkey`, `send_sms`. `silent_auth` und `account transfer` haben eigene Eignungsfelder.

### 3.5 `/v2/register`-Fehlergründe (Parser in `KotlinRegistrationBridge`)

| `reason` | Bedeutung (found: Name; Bedeutung inferred) |
|----------|-----------------------------------------|
| `incorrect` | falscher Code oder falsche PIN |
| `security_code` | Second Factor erforderlich |
| `second_code`, `device_confirm_or_second_code` | Second Factor oder Gerätebestätigung erforderlich |
| `too_many_guesses`, `guessed_too_fast` | Ratenlimit für Versuche; `guess_wait` wird zurückgegeben |
| `stale`, `mismatch`, `missing`, `format_wrong` | Code abgelaufen / passt nicht / fehlt / fehlerhaft formatiert |
| `sms_required` | Verifizierung per SMS erforderlich |
| `blocked`, `not_allowed`, `limited_release` | gebannt, nicht erlaubt, Rollout-Gate |
| `temporarily_unavailable` | vorübergehend |
| `challenge` | Challenge-Runde erforderlich (`/v2/challenge`) |
| `reset_too_soon` | Forgot-PIN-Reset zu früh angefordert |
| `consent`, `consent_parent_linking_already_registered` | Consent-Screens |

### 3.6 Second-Factor-Methoden

`EnumC43759JAu` (found): `twofac_pin`, `password`, `email_otp`, `oauth_email`, `sms`, `voice`, `flash`, `wipe_full`, `wipe_offline`. Mit Flag **28755** wird der Screen von `second_factor_methods` gesteuert ("Dynamic 2FA", Context-String `twofac_dynamic`), und "Auf andere Weise verifizieren" öffnet `Dynamic2faMethodSelectionBottomSheet`.

`K49.A0o` (`verifySecurityCode`):

| Bedingung | Wire |
|-----------|------|
| Flag 26215 aus | Legacy: `/v2/security` mit `code` (und `reset`, `wipe_token` beim Zurücksetzen) |
| Flag 26215 an, Methode nicht `password` | `/v2/register` mit `security_code` = Secret im Klartext in der Request-Map, `method` |
| Flag 26215 an, Methode `password` | das Passwort wird zuerst von `HOZ.A08` zu `#PWD_WA:11:<epoch>:<blob>` verschlüsselt (Abschnitt 5.3); der Blob wird an der `code`-Position von `/v2/register` gesendet; schlägt die Verschlüsselung fehl, meldet QPL `PASSWORD_ENCRYPT_FAILED` |

Der Schlüssel für den Envelope kommt von `WaPasswordEncryptionKeyQuery` über `CanonicalPasswordService.A04(..., true)` (aufgerufen aus `C47204KjV`, found). Welches Feld genau den Blob auf der Leitung trägt, wurde aus der Argumentreihenfolge des Konstruktors gelesen, nicht aus einem mitgeschnittenen Request (inferred).

### 3.7 Forgot PIN, Wipe und E-Mail-Reset

`/v2/exist` oder `/v2/register` können `reset_method`, `wipe_type` (`offline` oder `full`), `wipe_wait` (Sekunden), `wipe_token`, `wipe_expiry_time`, `server_time` zurückgeben (found). `VerifyTwoFactorAuth.A03` bildet diese auf vier Zustände ab (found): 0 nicht erlaubt, 1 im Cooldown ("0_7 days, offline_info"), 2 `offline` ("7_30"), 3 `full` ("over 30"). Der Reset-Aufruf sendet `reset=<mode>` und `wipe_token`; `wipe_full` und `wipe_offline` sind Second-Factor-Methoden (3.6). Was der Server bei `offline` bzw. `full` Wipe löscht, ist unknown.

---

## 4. Zwei-Schritt-Verifizierung (PIN) und Wiederherstellungs-E-Mail

### 4.1 Client-Zustand

`C1DP` (`TwoFactorAuthManager`) hält die PIN lokal (found): Pref `two_factor_auth_code`, optional verschlüsselt (`two_factor_auth_using_encryption`, entschlüsselt von `C1DP.A01` über einen Keystore-Helper). Sie wird für eine periodische Aufforderung "PIN bestätigen" verwendet: Nag-Intervalle 6 h, 12 h, 1 d, 1 d, 3 d, 7 d (`C1DP.A0I`, Prefs `two_factor_auth_nag_time`, `two_factor_auth_nag_interval`). Weitere Prefs: `two_factor_auth_email_set`, `two_factor_auth_dynamic_validated`, `two_factor_auth_last_code_correctness`, `pref_2fa_{sms,voice,flash,email_otp}_wait_time`.

### 4.2 IQ-Stanzas (`xmlns="urn:xmpp:whatsapp:account"`, 32 s Timeout)

| Aktion | Stanza | Gelesene Response | Klasse |
|--------|--------|---------------|-------|
| Status abrufen (smax 114) | `type=get` `<2fa/>` | `<2fa>`: vorhandenes Kind `code` bedeutet, dass eine PIN gesetzt ist; vorhandenes Kind `email` setzt `two_factor_auth_email_set` | `C1DT.A00`, `C28896Cgx` |
| PIN / E-Mail setzen | `type=set` `<2fa><code>PIN</code><email>addr</email></2fa>` (jedes Kind optional) | Erfolg schreibt Prefs; Fehlercode + Text an Listener | `C1DP.A07`, `C28899Ch0` |
| PIN prüfen | `type=get` `<2fa><code>PIN</code></2fa>` | `<2fa>` mit `code` bedeutet korrekt | Pfad `VerifyTwoFactorAuthCodeDialogFragment`, `HandlerC25225AtN` |

Die PIN hat 6 Ziffern (`SetCodeFragment`, Längenprüfung `== 6`). Setzen ist Typ 1, Bestätigen ist Typ 2. `Fetch2FAEmailStatusJob` liest den Status erneut (32 s), um zu sehen, ob die E-Mail verifiziert wurde. Ob der Server mehr als die Kinder `code` / `email` zurückgibt, ist unknown.

### 4.3 Konto-E-Mail-OTP (getrennt von `<2fa><email>`)

`C31107Dfz` baut, `KRB` parst (Log-Präfix `EmailVerificationXmppMethods`):

| Schritt | Stanza | Response |
|------|--------|----------|
| OTP anfordern | `type=set` `<verify_email><lg/><lc/></verify_email>` (Sprache / Locale, 2-3 Zeichen) | `verify_email.wait_time` |
| OTP verifizieren | `type=get` `<verify_email><code>NNNNNN</code></verify_email>` (6 Zeichen) | `verify_email.code_match` (`true`/`false`), `wait_time` |

Die E-Mail-Adresse selbst steht nicht in diesen Stanzas (früher gesetzt, Pfad nicht verfolgt). Verwendet von `VerifyEmailActivity` und dem Second Factor `email_otp`.

### 4.4 PIN versus Passwort versus GetTwofa

`GetTwofaQuery` liefert `twofa_methods[]{method,value,state}`. `PasswordUpsellEligibility` prüft auf die Strings `password` und `pin` in dieser Liste (found). `SetTwofaMutation` wird nur aufgerufen, nachdem ein Passwort erstellt wurde, Best Effort, mit der gehashten Geräte-ID (Abschnitt 5.2); `twofa_auto_enabled` / `twofa_auto_disabled` sind die Ergebnis-Flags. Die PIN selbst wird nie über w:mex gesendet.

---

## 5. Kontopasswort

### 5.1 Entitäten

| Entität | Rolle |
|--------|------|
| `PasswordRepository` | Orchestrierung: `setPassword`, `getTwofa`, Geräte-ID (`computeDeviceId`) |
| `PasswordServerApiImpl` | `HasPasswordQuery`, `DeletePasswordMutation`, `GetTwofaQuery`, `SetTwofaMutation` |
| `CanonicalPasswordService` | Key-Abruf, `A03` erstellen, `A02` ändern (`Xfb*`-Mutationen, Schema `whatsapp-android-www`) |
| `HOZ` | Envelope-Verschlüsselung (`A08` → `#PWD_WA:11`) |
| `PasswordCredentialManager` | speichert das Credential im Android Credential Manager (`saveCredential`, übersprungen ohne E.164-Nummer) |
| UI | `CreatePasswordActivity`, `ReplacePinWithPasswordActivity`, `PasswordUpgradeFragment`, `SettingsPassword`, `TrustThisDeviceActivity` |

### 5.2 Setzen / Ändern / Löschen

`PasswordRepository.setPassword` braucht zuerst Canonical-Credentials; ohne sie scheitert es mit "No canonical credentials available to set password" (found). Das Passwort ist also am Meta Canonical User verankert, nicht nur an der WhatsApp-Nummer.

```
setPassword(pw, isChange, enableTwofa)
  isChange  -> CanonicalPasswordService.A02  XfbWaChangePasswordMutation
  !isChange -> CanonicalPasswordService.A03  XfbWaCreatePasswordMutation
               then, if enableTwofa: GetTwofa/SetTwofa best effort (device_id = base64(SHA-256(ANDROID_ID)))
each: A04 = key fetch (WaPasswordEncryptionKeyQuery) + HOZ.A08 -> data.encrypted_password
```

`device_id` ist `K2M.A01(android_id)` = Base64 (Flag 2, kein Wrap) von SHA-256 über `Settings.Secure.ANDROID_ID` (found). Delete sendet keine Variablen; ein HTTP-ähnlicher Code 409 wird auf ein Ergebnis "blockiert, braucht E-Mail" abgebildet (found). Lokale Regeln in `CreatePasswordActivity`: Länge 8 bis 20, mindestens ein Buchstabe und eine Ziffer, Bestätigung muss übereinstimmen (found).

### 5.3 `#PWD_WA:11`-Envelope (`HOZ.A02` / `A08`)

```
epoch   = current time in seconds
aesKey  = random 32 B (AES-256)         iv = random 12 B
ct||tag = AES-GCM(aesKey, iv, utf8(secret))    // no AAD on this path
wrapped = RSA/ECB/PKCS1Padding(serverPublicKey, aesKey)
blob    = 0x01 | key_id(1 B) | iv(12) | len(wrapped) as uint16 LE | wrapped | tag(16) | ct
out     = "#PWD_WA:11:" + epoch + ":" + base64(blob, URL_SAFE | NO_WRAP | NO_PADDING)
```

`key_id` muss 1 bis 255 sein (`CanonicalPasswordService.A01`). Der RSA-Key wird aus dem PEM als X.509 SPKI geparst; der PKCS1-Pfad prüft die Modulgröße nicht (der Test auf ≥ 4096 Bit existiert nur in `HOZ.A06`, einer anderen OAEP-Variante). Derselbe Envelope wird an drei Stellen verwendet (found): Second Factor bei der Registrierung (3.6), Canonical-Erstellung / -Änderung (5.2) und Wiederherstellung (`exchangeNonce`, Abschnitt 9, eingewickelt in JSON `{version:1,timestamp,password}`).

Weitere Varianten in `HOZ` (nicht `#PWD_WA:11`): `A03` und `A06` verwenden RSA-OAEP-SHA-256 mit Zero-IV und AAD (der Waffle-SSO-Pfad schreibt `#PWD_WAFFLE` in `C40069Hd8` / `C40090HdT`).

---

## 6. OPAQUE, VOPRF und der native Krypto-Code

### 6.1 Was vorhanden ist

| Element | Wo | Tier |
|------|-------|------|
| `WESOpaqueClientRegistrationStartResult` (.rodata `0xaebae`), `...LoginStartResult` (`0xaebd5`), `...RegistrationFinishResult` (`0xaeda9`), `...LoginFinishResult` (`0xaedd1`), `...RegistrationState` (`0x115042`), `...LoginState` (`0x115072`) | `libwhatsapp.so`-Strings | found |
| `OPAQUE_PBKDF2_SALT` (`0x17e129`), `VOPRF06-HashToGroup-` (`0x19465a`), `VOPRF06-Finalize-` (`0x19466f`) | `libwhatsapp.so`-Strings | found |
| `org/whispersystems/curve25519/NativeVOPRFExtension` | dieselbe Lib; Java-Klasse hat `nativeBlind`, `nativeUnBlind`, `nativePcdBlind` | found |
| `libvoprf-ed25519.so`, `libvoprf-ristretto.so` | separate Libs, exportieren nur `JNI_OnLoad`; Java-Wrapper `com.facebook.privacy.acs.VoprfEd25519` / `VoprfRistretto` | found |

### 6.2 Funktionen, die die Strings referenzieren (arm64, vaddr)

| Funktion | Größe | Inhalt | Tier |
|----------|------|---------|------|
| `fcn.0075a1c0` | 644 B | referenziert `VOPRF06-HashToGroup-`; mbedTLS SHA-512 init / update ×6 / finish, danach ein zweiter SHA-512-Durchlauf | found |
| `fcn.0075b550` | 712 B | referenziert `VOPRF06-Finalize-` und `OPAQUE_PBKDF2_SALT`; SHA-512 über das Finalize-Transcript, danach `mbedtls_pkcs5_pbkdf2_hmac` | found |
| `fcn.0075a618`, `fcn.0075ad40` | - | rufen beide `fcn.0075b550` auf, danach `mbedtls_hkdf_extract` + drei `mbedtls_hkdf_expand` (md type `0xb`) | found |
| `fcn.0075a0d4` | - | ruft `fcn.0075a1c0` auf | found |

PBKDF2-Aufruf in `fcn.0075b550` (Disassembly): Passwortlänge `0x40` (64 B, die OPRF-Ausgabe), Salt-Länge `0x12` = 18 = Länge des Labels `OPAQUE_PBKDF2_SALT`, und der Buffer wird aus diesem Label initialisiert, abgeleitete Länge `0x40`, Iterationszahl wird vom Aufrufer übergeben (keine Konstante in dieser Funktion), md type `0xb`. Md type `0xb` entspricht SHA-512 in der mbedTLS-3.6-Nummerierung (inferred aus dem Enum-Wert und den 64-Byte-Längen). Die OPRF-Ausgabe speist also PBKDF2-HMAC-SHA-512 mit dem ASCII-Label als Salt (found für die Aufrufform, inferred für den Hash).

Die Rollen der Funktionen (Blind, Finalize, Registration-Finish, Login-Finish) sind aus der Aufrufform inferred. Die Gruppe / Ciphersuite (Kurve, an die `VOPRF06-`-Präfixe angehängte ID), die KE1- / KE2- / KE3-Byte-Layouts, der Envelope-Inhalt und die AKE-Variante sind **unknown**; der native Code wurde als Disassembly der zitierten Funktionen gelesen, nicht dekompiliert.

### 6.3 Wer es aufruft: verschlüsseltes Backup, nicht das Kontopasswort

Der Java-Einstieg für die State-Machine ist das Encrypted-Backup-Protokoll (Log-Präfix `encb/`):

| Klasse | Rolle (found) |
|-------|--------------|
| `EncBackupViewModel` | erzeugt `C61447Rhg` (Login-Handler) mit dem Backup-Passwort-String des Nutzers |
| `AbstractC62498S8e` | sendet die IQs `sendInitRegIq`, `sendBeginRegIq`, `sendFinishRegIq`, `sendInitLoginIq`, `finishLoginOnSuccess`, `sendDeleteAccountIq` (`EncryptedBackupProtocolHelper`) |
| `C62510S8q` (Smali `X/S8q`) | Response-Handler; `jvidispatchOOO(0xb, password, ...)` liefert den Login-Zustand (`Rtz`), `jvidispatchOO(0x20, state)` die nächste Nachricht |
| `C62511S8r` | Begin-Login-Response: verifiziert `l2` mit `l2_sig` und `ed_pub` (Ed25519), liest `count`, `backoff`, `max_attempts`, dann `jvidispatchOIOOO(1, 100000L, state, ...)` |
| `RunnableC29321Co8` | Finish-Login: `jvidispatchOIOO(1, 100000L, state, ...)`, liest die Modellfelder, entschlüsselt den Backup-Key per AES-GCM, baut das Proto `C25803BBm` (`backupKeyData_`, `r3_`, `opaqueChallenge_`, `transcript_`) |

`100000` wird sowohl bei Register als auch bei Login an die nativen Finish-Aufrufe übergeben (found). Es ist die wahrscheinliche PBKDF2-Iterationszahl (inferred: die native Funktion nimmt sie als Parameter). Dass diese `jvidispatch`-Indizes im `WESOpaque*`-Code landen, ist aus den Argumenten (Passwort-String hinein, State-Objekte zwischen den Aufrufen, Felder `l2` / `r3`) und aus dem Fehlen jedes anderen Verbrauchers inferred; kein Java-Symbol nennt OPAQUE. Der Kontopasswort-Code (Abschnitt 5) berührt sie nie.

### 6.4 Das andere VOPRF: Meta-ACS-Tokens

`NativeVOPRFExtension` und `libvoprf-ed25519.so` haben die Java-Verbraucher `C1N9` (`ACSTokenProviderImpl`, Log-Präfix `ACSToken/`) und `KYL`: Blinding Factor, signiertes geblindetes Token, DLEQ-Proof, Unblind, Shared Secret (Strings found: `blinding_factor_string`, `shared_secret_string`, `ACSToken/processSignedBlindedToken`). Passende Operationen in den Assets sind `WaAcsGetConfig` (`27388182297440754`) und `WaAcsIssueCredentials` (`26645395115100537`); keiner der Namen erscheint im Code, daher ist der Transport der Token-Anfrage nicht verfolgt. Das ist ein Anonymous-Credential-Token und kein Passwort-Login.

### 6.5 Was das für den "Passwort-Login" bedeutet

| Behauptung | Status in 2.26.41.6 |
|-------|---------------------|
| Kontopasswort-Login verwendet OPAQUE | vom Code nicht unterstützt: Das Passwort wird als RSA/AES-Envelope (`#PWD_WA:11`) gesendet, in den gelesenen Pfaden wird keine OPAQUE-Nachricht gebaut; `SetPasswordMutation` und `CheckPasswordMutation` haben keine Aufrufstelle |
| Ein nativer OPAQUE-Client existiert | found |
| Er bedient das Passwort des verschlüsselten Backups | found (Java-Aufrufer), Bindung an die nativen Symbole inferred |
| Der Server speichert für das Kontopasswort einen Verifier statt des Passworts | unknown |

Java-Strings, die wie OPAQUE-Evidenz aussehen, aber nichts damit zu tun haben (found): `opaqueChallenge_` (Backup-Bootstrap-Proto oben), `opaquePayload_` (`C61318RfY`, Tethered-Migration-Frame), `OpaqueConfig` / `prefersOpaqueConfig` (Bitmap-Config in `EnumC167127Ba`), `OpaqueKey(` (`C44715Jfl`, ein String-Wrapper), `KE1` (`X.KE1` ist eine Android-Compose-Klasse), `opaque_client_data` (History-Sync-Spalte).

---

## 7. Passkeys (WebAuthn)

### 7.1 Login bei der Registrierung

| Schritt | Evidenz |
|------|----------|
| `/v2/exist` liefert `passkey_auth_challenge`; `K15.A03` akzeptiert sie, solange sie jünger als `SignalCredentialStateController.MAX_RETRY_TIME` ist | found |
| `PasskeyVerifier.onPasskeyChallengeReceived` führt eine Discoverable-Credential-Assertion über `androidx.credentials` aus (`PasskeyLowLevelAndroidApiImpl.loginWithPasskey`); Stage wird im Pref `passkey_login_stage` gehalten | found |
| `K49.A0l` postet das Ergebnis als `credential` an `/v2/passkey_auth` | found |
| Response: `status` (`ok`/`fail`), `reason` (`temporarily_unavailable`, `disabled`), `credential_create` (String), `login`, `cred_token` | found |
| `cred_token` wird pro Telefonnummer in `passkey_disabled_cred_token_map` gespeichert und bei späteren Requests als `cred_token` zurückgesendet, wenn Flag **25565** an ist | found; Zweck (Nachweis, dass ein Passkey deaktiviert wurde) inferred |

Clientseitige Ergebnisse werden als `passkey_client_login_{cancelled,nopasskey,ineligible,error,success}` geloggt. `prepareGetCredential` wird nur auf Android 14+ (SDK 34) und Flag **21638** verwendet (found).

### 7.2 Erstellen und verwalten

Upsell nach dem 2FA-Schritt: `VerifyTwoFactorAuth.onCheckPasskeyUpsellAfter2FA` verwendet `PasskeyCreateEducationScreen` oder ein Bottom Sheet; Flag **20409** schaltet zwischen Control-Ablauf und Quick-Promotion-(QP-)Pfad um, Flag **16591** fügt eine Eignungsprüfung hinzu (found).

| Operation | MEX-Gate | IQ-Fallback (`xmlns="passkey"`) |
|-----------|----------|---------------------------------|
| Start Register | Flag **10453** | smax 125, `type=get` |
| Finish Register | Flag **10452** | smax 126, `type=set` |
| Clear | Flag **10461** | smax 129, `type=set` |
| List / Exists, Delete, Enable, Update Encryption Status | immer MEX | keiner |

`credential_create` aus Start Register wird in `passkey_create_challenge` gecacht. Finish Register sendet `credential` und `key_attestation`; die Attestation-Payload wird nur gebaut, wenn Flag **28809** an ist (base64 der Key Attestation, `getKeyAttestationPayload`). Flag **8877** wickelt Start / Finish in einen Retry- / Timeout-Helper (`C29707Cw7`, Rolle inferred). `PasskeyRandomizedDailyCronJob` und `PasskeyExistsCache` aktualisieren die Exists-Liste; die Exists-Response speichert `uuid` in `reg_passkey_exists_uuid`.

### 7.3 PRF und clientseitige Verschlüsselung

`PasskeyPrfSecrets` verwendet den statischen PRF-Input `WhatsAppPasskeyStaticPrfInputV1` und speichert einen PRF-abgeleiteten Root Key in `prf_derived_root_key.key` (Encapsulation-Key-Label `prf_derived_root_key_file_encapsulation_key`). `RegistrationPasskeyUpdateClientEncryptionStatusMutation` teilt dem Server mit, dass der Passkey für clientseitige Verschlüsselung verwendet wird. Der Verbraucher ist der Encrypted-Backup-Ablauf (`VerifyPasskeyFragment`, inferred aus dem Klassenstandort).

---

## 8. Vertrauenswürdige Geräte

| Element | Wert |
|------|-------|
| `device_id` | `Base64(SHA-256(ANDROID_ID))` (kein Wrap), `K2M.A01` |
| `device_name` | `<MANUFACTURER>-<MODEL>` (`HO4.A00`) |
| Checkbox | angezeigt auf `VerifyPhoneNumber` und `VerifyTwoFactorAuth`, wenn Flag **30530** an ist und `pref_is_device_trusted` false ist; Prefs `pref_trusted_device_checkbox_shown` / `_checked` |
| Abschluss der Registrierung (`RegisterName`) | Opt-in: `AddTrustedDeviceMutation`; kein Opt-in: `UntrustTrustedDeviceMutation` mit `reason="REREG"` (`C29652Cu9`, found) |
| Einstellungen | `TrustedDevicesRepository` listet (`GetTrustedDevicesQuery`) und entfernt (`DeleteTrustedDeviceMutation`); `TrustThisDeviceActivity` |
| Wirkung | `is_device_trusted` wird von `/v2/exist`, `/v2/register`, `GetTwofa` und `SetTwofa` zurückgegeben; der Client nutzt es, um die Checkbox zu überspringen. Dass ein vertrauenswürdiges Gerät die PIN- / Passwort-Abfrage überspringt, ist inferred; kein Client-Code überspringt den Second Factor |

Einträge in `list_of_trusted_device[]` tragen `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` (der Ort der letzten Nutzung kommt vom Server; wie er abgeleitet wird, ist unknown).

---

## 9. Kontowiederherstellung (Meta Canonical User)

`AccountRecoveryManager` stellt weder WhatsApp-Chats noch das Telefonnummer-Konto wieder her. Er erstellt die Meta-Canonical-User-Credentials eines FB-verknüpften Kontos neu (found).

| Schritt | Detail |
|------|--------|
| Trigger | `maybeRecoverAccount`: kein Canonical User oder Credentials ungültig; verzögerte Variante durch Flag **16017** gesteuert |
| Client-Key | erzeugt ein Schlüsselpaar, sendet den Public Key (PEM, base64) als `nonce_encryption_key` in `WWWTriggerAcountRecovery` mit `use_case`, `registration_trace_id`, `request_id` |
| Nonce | kommt per Notification; Timeout erzeugt "Account Recovery Failed due to Nonce notification timeout" |
| Austausch | `WWWExchangeNonceForAccessToken` mit `nonce`, `use_case`, `request_id`, `registration_trace_id`, `encrypted_password` = `#PWD_WA:11`-Envelope eines zufälligen Client-Secrets innerhalb von JSON `{version:1,timestamp,password}` |
| Companion | `WWWGetNonceForCompanionDevice`, `WWWTradeNonceForAccessTokens` tun dasselbe für verknüpfte Geräte (`CompanionCanonicalUserNonceManager`, `CompanionCanonicalUserAccessTokenJob`) |
| Verwandt | `WWWValidateCanonicalUser`, `WWWCanonicalUserValid`, `WWWAppGenerateCanonicalNonce` (Aufrufstellen vorhanden; Felder nicht gelesen) |

Die Schreibweise `Acount` stammt von WhatsApp selbst. Welcher Algorithmus der Nonce-Encryption-Key ist (das Paar kommt von `N6T.A02`), ist nicht aufgelöst.

---

## 10. Login und Logout

`LogoutManager` implementiert einen Soft Logout (Multi-Account) und den Login-Back-Pfad (found).

| Aktion | Wire | Hinweise |
|--------|------|-------|
| Logout | `AccountLogoutMutation` `{phone_number, enabled_biometric}` | `enabled_biometric` aus einer Biometrie-Einstellung; 5 s Timeout, danach läuft der Logout lokal weiter ("timed out, proceeding with logout") |
| Push | `LogoutPushManager` deaktiviert / reaktiviert GCM-Push (`"re-enable"` beim Zurücknehmen) | found |
| Lokal | `markCurrentAccountLoggedOut`, `removeLoggedOutAccountWithCleanup`, `deleteGmsBackupState`, optionale Chat-Lösch-UI (`DeleteChatsOnLogoutDialog`, `LoggedOutChatsFragmentDialog`) | found |
| Login-Back | `AccountLoginMutation` `{phone_number}`, danach `loginBack` → `actionReconnect`; bis zu 7 s auf die Verbindung warten | `PrimaryLoginBackActivity` |

Es ist ein Status-Flag auf der Serverseite eines Multi-Account-Setups, nicht der Telefonnummer-Login aus Abschnitt 3 und nicht das Entfernen eines verknüpften Geräts. Flag **28385** wird in `LogoutManager` gelesen (Rolle nicht aufgelöst).

---

## 11. Feature-Flags

IDs sind fett. Typen: B = boolescher AB-Prop, C = Config. Namen stehen nicht im Client; die Rolle ist das, was der Code mit dem Flag tut.

| ID | Wo | Steuert |
|----|-------|----------|
| **24762** (C) / **24763** (B) | `K49.A0b` | Kotlin-Registrierungs-Stack statt nativem `wamsys` |
| **26215** | `K49` Verify / Reset Security Code | Second Factor bei der Registrierung über `/v2/register`, aktiviert Passwort-Envelope; aus = Legacy `/v2/security` |
| **25565** | `K49.A0M` | gespeichertes `cred_token` senden |
| **28755** | `VerifyTwoFactorAuth` | dynamische 2FA-Methodenauswahl aus `second_factor_methods` |
| **30530** | `VerifyPhoneNumber`, `VerifyTwoFactorAuth` | Trusted-Device-Checkbox |
| **20409** | `VerifyTwoFactorAuth` | QP-Passkey-Upsell nach 2FA vs. Control |
| **16591** | `VerifyTwoFactorAuth` | Passkey-Eignungsprüfung vor dem Upsell |
| **21638** | `PasskeyAndroidApi` | `prepareGetCredential` (Android 14+) |
| **10452** / **10453** / **10461** | `PasskeyServerApiImpl` | MEX statt IQ für Finish / Start / Clear |
| **28809** | `PasskeyServerApiImpl` | Key-Attestation-Payload |
| **8877**, **31281** | `PasskeyCreateFlow` | Retry-Wrapper; alternativer Payments-Passkey-Pfad (Rollen inferred) |
| **5156** | `SetCodeFragment` | "E-Mail hinzufügen" nach PIN-Setzen anbieten |
| **5711** | `TwoFactorAuthActivity`, `SetCodeFragment` | nur Layout (blendet Seitenindikator aus) |
| **16017** | `AccountRecoveryManager` | verzögerte Nonce-Verarbeitung |
| **28385** | `LogoutManager` | nicht aufgelöst |

---

## 12. Fehlerfälle

| Symptom | Ursache | Behebung / Hinweis |
|---------|-------|------------|
| `/v2/register` Reason `security_code` oder `second_code` | Konto hat einen Second Factor | PIN / Passwort / E-Mail-OTP über `/v2/register` senden (3.6) |
| `PASSWORD_ENCRYPT_FAILED` (QPL) | Key-Abruf fehlgeschlagen, `key_id` außerhalb 1-255 oder Krypto-Exception (`encryptRegistrationPassword/*`-Logs) | erneut versuchen; der Client bricht den Versuch ab |
| `reset_too_soon` | Forgot-PIN-Reset vor Ablauf von `wipe_wait` | warten; UI-Zustand 1 |
| `too_many_guesses` / `guessed_too_fast` | Versuchslimit für PIN oder OTP | `guess_wait` abwarten |
| `No canonical credentials available to set password` | kein Meta Canonical User auf dem Gerät | zuerst das Canonical-User-Setup abschließen |
| Passwort erstellen / ändern fehlgeschlagen | `xfb_wa_*`-Payload nicht erfolgreich; Fehlercode von `CanonicalPasswordService.A00` abgebildet | UI-Fehler-Enum `EnumC49982M3j` |
| `DeletePassword` 409 | Konto-E-Mail vor dem Entfernen erforderlich | zuerst E-Mail hinzufügen |
| `Account Recovery Failed due to Nonce notification timeout` | Notification nicht empfangen | Trigger erneut versuchen |
| `...passwordPublicKeyStr is null` / `passwordKeyIdStr is null` | Verschlüsselungszertifikat fehlt im Recovery-Austausch | erneut versuchen |
| `LogoutManager/callLogoutApi/timed out` | keine Response innerhalb von 5 s | Logout läuft lokal weiter |
| Passkey: `NoCredentialException`, `NotAllowedError`, GMS zu alt, Play Services fehlen | Credential-Manager-Fehler | fällt auf andere Methoden zurück |

---

## 13. Wichtige Unterscheidungen

| A | B |
|---|---|
| OPAQUE-Nativcode (Passwort des verschlüsselten Backups, HSM-`encb/*`-IQs) | Kontopasswort (`XfbWa*` + `#PWD_WA:11`) |
| `libvoprf-*.so` + `NativeVOPRFExtension` (anonyme ACS-Tokens) | OPAQUE-State-Machine (`WESOpaque*`) |
| PIN (IQ `<2fa>`, 6 Ziffern) | Passwort (w:mex, 8-20 Zeichen) |
| `<2fa><email>` (Wiederherstellungs-E-Mail für PIN-Reset) | `<verify_email>`-OTP-Ablauf und Second Factor `email_otp` |
| `SetTwofaMutation` (Flag pro Geräte-ID nach Passwort) | PIN-Set-IQ |
| Vertrauenswürdiges Gerät (Login, `AddTrustedDeviceMutation`) | `WhatsappTrustedDeviceRegistration` (Payments-Trust-Binding) |
| `AccountLogoutMutation` (Soft Logout) | Entkoppeln eines Companions (`remove-companion-device`) und Ban-Logout |
| `WWWTriggerAcountRecovery` (Canonical-User-Credentials) | Forgot-PIN-Wipe (`wipe_*`, `/v2/security`) |
| `#PWD_WA:11` (WhatsApp) | `#PWD_WAFFLE` (Waffle SSO) |
| `PasskeyServerApiImpl`-Operationen (Konto-Passkeys) | `PaymentsPasskey*`, `BrPasskey*` |
| `/v2/passkey_auth` (Login-Assertion) | `PasskeyRequestChallengeMutation` / `PasskeyVerifyChallengeMutation` (keine Aufrufstelle) |

---

## 14. Baileys (`baron-baileys-v2`)

Verglichen mit `src/Socket/privacy.js` und `src/Socket/registration.js`.

| Element | APK 2.26.41.6 | Baileys | Ergebnis |
|------|---------------|---------|--------|
| doc_ids für Trusted Devices, Login, Logout, Passwörter, Passkeys | Assets | gleiche Nummern | passt |
| `accountLogin` / `accountLogout` | `input{phone_number}` / `input{phone_number, enabled_biometric}` | gleich | passt |
| `getTrustedDevices` | `input{device_id}` wird immer gesendet | `{}` | weicht ab; Serververhalten ohne `device_id` unknown |
| `untrustTrustedDevice` Default-Reason | `"REREG"` im einzigen Aufruf | `'USER_INITIATED'` | weicht ab, andere Reasons unknown |
| Passkey-Operationen | Variablen `credential`, `key_attestation`, `credential_ids`; Roots `xwa2_passkey_*` | in den gelesenen Dateien keine implementiert | APK-Formen verwenden |
| `SetPassword` / `CheckPassword` | keine Aufrufstelle | nur doc_ids | nicht verifiziert, nicht darauf verlassen |
| `#PWD_WA:11`-Verschlüsselung | Abschnitt 5.3 | im gelesenen `src`-Baum nicht vorhanden | nach Abschnitt 5.3 implementieren |

Warum ein eigenständiger Client auf diesen Pfaden scheitert (inferred, nichts getestet): Registrierungs-Endpunkte erwarten die e2e-geschützten Request-Felder, die die App baut (`C45446JsB`); Passwort- und Recovery-Aufrufe brauchen Canonical-User-Credentials; die Passkey-Assertion braucht einen Plattform-Authenticator.

---

## 15. Vollständige Abläufe

### 15.1 Eine Nummer verifizieren, die bereits ein Konto hat

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

### 15.2 Eine PIN und Wiederherstellungs-E-Mail setzen

```
[Client]  IQ get <2fa/> ───────────────► [Server]  <2fa>[<code/>][<email/>]
[Client]  IQ set <2fa><code>NNNNNN</code><email>x</email></2fa> ──► ok | error(code,text)
[Client]  Fetch2FAEmailStatusJob: IQ get <2fa/> until <email> present
[Client]  IQ get <2fa><code>NNNNNN</code></2fa> ──► <2fa><code/></2fa> = correct   (periodic reminder)
```

### 15.3 Ein Kontopasswort erstellen

```
[Client]  canonical credentials present? ── no ─► fail
[Client]  WaPasswordEncryptionKeyQuery ──► public_key (PEM), key_id (1..255)
[Client]  HOZ.A08: AES-GCM + RSA-PKCS1 wrap -> "#PWD_WA:11:<epoch>:<blob>"
[Client]  XfbWaCreatePasswordMutation {data:{encrypted_password}} ──► success
[Client]  (best effort) GetTwofaQuery / SetTwofaMutation {input:{twofa_enabled:true, device_id}}
```

---

## 16. Unbekanntes

| Thema | Grund |
|-------|--------|
| OPAQUE-Ciphersuite (Gruppe, ID nach `VOPRF06-`), KE1- / KE2- / KE3- und Envelope-Layouts, AKE-Variante | nativ, nur als Disassembly von 4 Funktionen gelesen |
| Bindung der `jvidispatch`-Indizes des verschlüsselten Backups an den `WESOpaque*`-Code | über Argumentform, nicht über Symbol |
| PBKDF2-Iterationszahl für die OPAQUE-KSF | als Parameter übergeben; `100000` ist das Literal, das die Java-Aufrufer übergeben |
| Ob irgendein Pfad ein Kontopasswort über OPAQUE sendet | kein solcher Pfad gefunden; hinter numerischem Dispatch versteckte Wrapper lassen sich nicht ausschließen |
| Responses von `XfbWa*`, `AccountLogin`, `AccountLogout`, `UntrustTrustedDevice` | Root und Felder nicht gelesen |
| Operationen ohne Aufrufstelle (2.4) | Variablen und Responses unbekannt |
| Exaktes Feld, das den `#PWD_WA`-Blob in `/v2/register` trägt | aus Konstruktorreihenfolge abgeleitet |
| Bedeutung der von `/v2/exist` und `/v2/passkey_auth` zurückgegebenen Felder `login`, `lid` | Verbraucher nicht verfolgt |
| Wirkung von `wipe_full` / `wipe_offline` auf dem Server | Client zeigt nur Text |
| Ob ein vertrauenswürdiges Gerät den Second Factor überspringt | serverseitig; keine Client-Skip-Logik |
| Algorithmus des Recovery-Schlüsselpaars (`N6T.A02`) | nicht gelesen |
| Rollen der Flags 8877, 31281, 28385 | nur Gates |
| Tatsächlicher Traffic | nur statische Analyse |
