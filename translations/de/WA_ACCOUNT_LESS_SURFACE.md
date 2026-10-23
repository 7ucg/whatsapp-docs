<!-- src-sha1: 166366154a0dd7893ab70aa91166a96d5a2e788f -->
# WhatsApp Account-lose Angriffsfläche — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** was der Android-Client ohne registrierten Account oder vor Abschluss der Registrierung exponiert — Manifest-Exports (Activities, Aliase, Services, Receiver, Provider), Screens vor der Registrierung und Routing nach Registrierungsstatus, Deep Links und Web-Links, unauthentifizierte HTTP- und Graph-Endpunkte, einkompilierte Host-Tabelle, Support-Formular im ausgeloggten Zustand, Einstiegspunkte für Ban-Status und Einspruch, vor dem Login gesendete Identifier, IPC-Oberflächen für Drittanbieter, was unbekannt bleibt

---

## 1. Was "account-los" in diesem Build bedeutet

Es gibt keinen einheitlichen "Logged-out-Modus". Mehrere voneinander unabhängige Pfade laufen, solange der Client keine User-JID, keine authentifizierte Chat-Session oder eine unvollständige Registrierung hat. Jeder Pfad ersetzt den Account durch ein anderes Credential. Alle Aussagen beruhen auf statischer Analyse der dekompilierten APK (`versionCode 264100600`, target SDK 36, min SDK 23). Auf der Leitung wurde nichts beobachtet. Tiers: **found** = in Code oder Manifest gelesen, **inferred** = aus Code abgeleitet, **unknown** = statisch nicht auflösbar. Defensive Dokumentation: Oberflächen und Kontrollen werden beschrieben, nicht ausgeführt.

Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst.

| Pfad | Credential, das den Account ersetzt | Transport | Hauptklassen (2.26.41.6) |
|------|--------------------------------------|-----------|--------------------------|
| Telefon-Registrierung | keines bis `/v2/register`; Request enthält Noise-Static-Key-Bundle und Geräte-IDs | HTTPS `/v2/*` | `K49`, `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Funnel-Log vor der Nummer | nur Phone-ID (`fdid`) | HTTPS `/v2/pre_pn_client_log` | `PrePnBaseFunnelLogger`, `K49` |
| Pre-Chat-AB-Props | Prefs `ab_key` / `ab_hash` | HTTPS `/v2/reg_onboard_abprop` | `K49.checkPreChatdABProps` |
| Ban-Status / Einspruch | opaker, beim Ban gespeicherter Token + einkompilierter App-Client-Token | HTTPS Graph `graph.<domain>/graphql` | `AbstractC40195HfH`, `C37409GLo`, `C37604GYf`, `C37414GLt` |
| Support-Formular im ausgeloggten Zustand | keines; E-Mail + Freitext + `anid` | HTTPS Multipart-POST | `LoggedOutContactFormActivity`, `C47328KmN` |
| Crash-/Log-Upload | einkompilierter App-Token | HTTPS `crashlogs.whatsapp.net` | `C10V`, `C05640An` |
| Statische Assets | keines | HTTPS GET | `static.whatsapp.net/*` |
| Anonymous-Credential-Graph (ACS / OHAI) | ACS-Token oder OHAI-Key-Config, keine JID | HTTPS `acs.whatsapp.com/graphql` | `C31991Nz`, `R5t`, `N5I` |
| Companion-Registrierung | keines; Noise-Connect mit Null-JID nur hier erlaubt | Noise | `HandlerThreadC12340b0` |
| Eingebauter DNS-Fallback | keines | einkompilierte Tabelle | `AbstractC47101wK`, `C36881dC` |

Hier nicht behandelt, siehe die verlinkten Reports: Registrierungsschritte, OTP-Methoden und Fehlergründe ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) Abschnitt 3); bei der Registrierung gesendete Attestation-Tokens ([WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)); Ban-Zustandsmaschine und Verschlüsselung des Einspruchs ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) Abschnitte 2, 10); Noise-Login und Companion-Registrierung ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)); WAM-Telemetrie ([WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)).

---

## 2. Manifest: exportierte Komponenten

### 2.1 Zahlen (found, `AndroidManifest.xml`, unter `<application>` geparst)

| Typ | Deklariert | Exportiert (explizit `true`; keine mit implizitem Default) |
|------|---------:|----------------------------------------------------------------:|
| `activity` | 828 | 22 |
| `activity-alias` | 33 | 29 (14 sind deaktivierte `AppIcon01..14`-Launcher-Aliase) |
| `service` | 61 | 16 |
| `receiver` | 68 | 19 |
| `provider` | 19 | 11 |
| Summe | 1009 | 97 |

Von den 97 exportierten Einträgen: 20 sind `enabled="false"` (14 Icon-Aliase, Car-App-Service, ADM-Receiver, iOS-Migration-Activity und -Provider, zwei indische UPI-Intent-Receiver); 24 tragen eine `permission` / `readPermission`; 6 sind durch eine WhatsApp-eigene `signature`-Permission geschützt; 56 sind aktiviert und haben keine Manifest-Permission. Jede Prüfung über das Manifest hinaus liegt im Code (Abschnitt 9).

Eigene Permissions (found): `REGISTRATION`, `IDENTITY_VERIFICATION`, `MIGRATION_CONTENT_PROVIDER`, `BROADCAST`, `MAPS_RECEIVE`, `RECEIVE_ADM_MESSAGE`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` sind `protectionLevel="signature"`. `com.whatsapp.sticker.READ` hat kein `protectionLevel` (Default normal).

### 2.2 Einstiegspunkte, die ohne Account laufen

| Komponente | Exportiert | Filter | Warum vor der Registrierung erreichbar |
|-----------|----------|--------|--------------------------------------|
| `com.whatsapp.Main` | ja | `MAIN` / `LAUNCHER`, `MULTIWINDOW_LAUNCHER` | einziger Launcher; routet nach Registrierungsstatus (Abschnitt 3) |
| `com.whatsapp.home.ui.HomeActivity` + Aliase `AcceptInviteLinkActivityDeepLink`, `EventDeepLink`, `HomeActivity` | ja | `chat.whatsapp.com`, `call.whatsapp.com`, `event.whatsapp.com`, `whatsapp://chat`, `call`, `event`, NFC `application/com.whatsapp.chat`, `.join` | in `HomeActivity` selbst keine Registrierungsprüfung gefunden (inferred: eine Basisklasse leitet um, nicht aufgelöst) |
| `DeepLinkActivity` über 4 Aliase | Alias ja, Ziel nein | siehe Abschnitt 4 | Link-Einstiegspunkt |
| `com.whatsapp.deeplink.ui.TpalOAuthRedirectActivity` | ja | `www.whatsapp.com/oauth_account_linking/login_redirect`, `/oauth_account_linking_mobile/login_redirect`, `whatsapp://third_party_oauth` | OAuth-Redirect-Empfänger, `noHistory` |
| `com.whatsapp.cuif.ConsentActivity` | ja | `whatsapp://consent` | liest Extras `flow_name`, `source`, `extra_params`, `device_id`, `app_id`; Verhalten vor der Registrierung nicht aufgelöst |
| `com.whatsapp.Conversation` | ja | `sms:` / `smsto:` `VIEW` / `SENDTO` | Einstieg als System-SMS-Handler |
| `com.whatsapp.accountsync.ProfileActivity`, `CallContactLandingActivity` | ja | `content://com.android.contacts` MIME `vnd.com.whatsapp.profile`, `.voip.call`, `.video.call` | Integration in die Kontakte-App; `CallContactLandingActivity` braucht `CALL_PHONE` |
| `com.whatsapp.registration.ui.RegistrationCompletedReceiver` | ja, `REGISTRATION`-Signature | `com.whatsapp.SMBRegistrationCompleted` | Signal der Schwester-App |
| `com.whatsapp.registration.directmigration.MigrationProviderOrderedBroadcastReceiver`, `MigrationRequesterBroadcastReceiver` | ja, `REGISTRATION`-Signature | Actions `initialMigrationInfoAction`, `recoveryTokenAction`, `setMigrationStateOnProviderSide`, `providerIsLoggedOutAction`, `providerAppMigrationSpaceNeededAction` | Migration Consumer- / SMB-Schwester-App zur Registrierungszeit |
| `MigrationContentProvider`, `DirectMigrationContentProvider` | ja, `readPermission` `MIGRATION_CONTENT_PROVIDER` (signature) | Authorities `com.whatsapp.provider.MigrationContentProvider`, `.DirectMigrationContentProvider` | dieselbe Migration |
| `com.whatsapp.registration.app.verifyphone.SMSRetrieverAppInactiveReceiver` | ja, GMS-`SEND`-Permission | `SMS_RETRIEVED` | SMS-Retriever-Ergebnis bei inaktiver App |
| `com.whatsapp.registration.core.accounttransfer.AccountTransferReceiver` | ja, keine Permission | `com.google.android.gms.auth.START_ACCOUNT_EXPORT` | Code verlangt vor der Aktion einen sicheren Keyguard und eine Feature-Prüfung (found) |
| `com.whatsapp.phoneid.PhoneIdRequestReceiver` | ja, keine Permission | `com.facebook.GET_PHONE_ID` | liefert die Phone-ID an einen vertrauenswürdigen Aufrufer (Abschnitt 9.1) |
| `com.whatsapp.otpmessage.otp.OtpRequestedReceiver`, `OtpIdentityHashRequestedReceiver` | ja, keine Permission | `com.whatsapp.otp.OTP_REQUESTED`, `ID_HASH_REQUESTED` | OTP-Autofill-Handshake für andere Apps (Abschnitt 9.3) |

### 2.3 Weitere exportierte Einträge (nicht registrierungsbezogen, der Vollständigkeit halber aufgeführt)

| Gruppe | Komponenten | Gate |
|-------|------------|------|
| Inhalte von Drittanbietern | `Conversation` (`sms:`-Handler), `ExternalShareAlias` (`SEND`, `SEND_MULTIPLE`, `*/*`), `ContactPicker` (`PICK`, `CREATE_SHORTCUT`), `SetAsProfilePhoto` (`ATTACH_DATA`) | keines im Manifest |
| Sticker | `SendStickerCommandActivity`, `AddThirdPartyStickerPackActivity` (+ Alias), `StickerCommandProvider`, `WhitelistPackQueryContentProvider` | keines im Manifest |
| Meta-Family-IPC | `FamilyAppsCredentialsProvider`, `FamilyAppsUserValuesProvider`, `WaAccountsCenterService` (`com.whatsapp.wfl.OPERATION`), `QuickSendsContactsProvider`, `OrbitSsoProvider`, `OrbitMessagesProvider`, `OrbitCompanionLinkActivity`, `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | Aufruferprüfungen im Code (Abschnitt 9) |
| Geräte-Companions | `WearOsListenerService`, `GarminBindingServiceShim`, `IQGarminBindingService`, `TetheredService`, `WhatsAppCarAppService` (deaktiviert) | keines im Manifest |
| Google-Integration | `BackupNowService`, `BackupStateService`, `OsMigrationAppDataService` (`BACKUP`), `DeferredRestoreBroadcastReceiver` (`BACKUP`), `WakeUpService` (Exposure-Notification-Permission) | teilweise |

Ebenfalls exportiert: Settings-Hooks (`SettingsNotifications`, `SettingsDataUsageActivity`, `AppAuthenticationActivity` Widget-Configure), Anruf-Landing (`SystemDialerCallLandingActivity`, `VoiceMessagingActivity`), Library-Receiver (`WidgetProvider`, `BootReceiver`, `AppUpdatedReceiver`, `ExternalMediaStateReceiver`, `WAFbnsPreloadReceiver`, `FirebaseInstanceIdReceiver`, Work-Manager- und Profile-Install-Einträge hinter `BIND_JOB_SERVICE` / `DUMP`), Pixel-Einträge (`com.google.permission.besties.API`) sowie die deaktivierten indischen UPI- und iOS-Migration-Einträge. `IdentityVerificationActivity` (NFC `application/com.whatsapp.identity.ui`) verlangt die Signature-Permission `IDENTITY_VERIFICATION`.

### 2.4 Nicht exportierte Komponenten vor der Registrierung (found)

Die 806 nicht exportierten Activities enthalten jeden Registrierungs-Screen (Abschnitt 3.2), `LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity`, `BanAppealActivity`, `WfacBanActivity`, `PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`. Drei nicht exportierte Alarm-Receiver steuern Registrierungs-Erinnerungen: `RegRetryVerificationReceiver` (`com.whatsapp.alarm.REGISTRATION_RETRY`, `SMS_RECEIVED_WHILE_INACTIVE`), `OnboardingIncompleteReceiver` (`ONBOARDING_INCOMPLETE`), `EnterPhoneNumberNotificationReceiver` (`ENTER_PHONE_NUMBER`). Nicht exportierte Provider: `FileProvider`, `SecureFileProvider`, `MediaProvider`, `AccountSwitchingContentProvider`, `RestartAppContentProvider`, `InstrumentationProvider` (alle mit `grantUriPermissions`, wo deklariert).

### 2.5 Application-Flags und Netzwerk-Policy (found)

| Eintrag | Wert |
|------|-------|
| `debuggable` | `false` |
| `allowBackup` | `true`, aber `fullBackupContent` und `dataExtractionRules` (Cloud-Backup und Geräteübertragung) schließen alle Domains aus; Cross-Platform-Transfer-Eintrag nur für iOS trägt nur `bundleId` / `teamId` |
| `networkSecurityConfig` base | `cleartextTrafficPermitted="true"`; Trust Anchors `system` und `user` (`overridePins="true"` für User-CAs) |
| Cleartext verboten | `whatsapp.com`, `whatsapp.net`, `wa.me`, `wl.co` (22 SHA-256-Pins, kein Ablauf), `facebook.com`, `instagram.com`, `jiomart.com`, `hatch-api.meta.ai` |
| Pin-Geltungsbereich | das Pin-Set hängt an der Domain-Config `whatsapp.com` / `whatsapp.net` / `wa.me` / `wl.co`; sie erbt die Base-Trust-Anchors, daher gelten Pins nicht für vom Nutzer installierte CAs (Plattformverhalten von `overridePins`) |
| Hosts außerhalb jeder Domain-Config | `gstatic.com` (reCAPTCHA-Key) fällt unter die Base-Config (Cleartext erlaubt; der Code nutzt `https://`) |

---

## 3. Screens vor der Registrierung und Status-Routing

### 3.1 `Main`-Routing nach Registrierungsstatus (found, Smali von `Main.A5W`)

`Main` liest den Registrierungsstatus (`C0Gk.A02()`) und das gespeicherte Objekt des eigenen Accounts. Log-Tags sind stabile Anker.

| Status | Log-Tag | Ziel |
|------:|---------|-------------|
| 2 | `main/me/regname`, `main/no-me/regname` | Registrierungsschritt Namenseingabe (`RegisterName`) |
| 21 | `main/me/wfac ban` | WFAC-Ban-Screen über `HBC.A00` (`WfacBanActivity`) |
| 24, 38 | `main/me/backup otp` | Backup-OTP- / Verifizierungsschritt |
| 41 | `main/me/consent age ban` | Altersbestätigungs-Screen |
| 45 | `main/me/paa onboarding`, `main/no-me/paa onboarding` | Onboarding für abhängige / verwaltete Accounts |
| 50 | `main/me/logged out, going to PrimaryLoginBackActivity` | Login-back-Screen |
| 51 | `main/me/pending login-back verification` | Login-back-Verifizierung (Extra `login_back_verification`) |
| 56 | `main/me/username`, `main/no-me/username` | Username-Schritt |
| beliebig | `main/no-me/first-factor password` | First-Factor-Passwort-Zweig (kein eigenes Account-Objekt) |
| beliebig | `main/invalid/registration state=` | Log bei ungültigem Status |

Dieselbe Methode baut Intents (found) für `VerifyPhoneNumber`, `DeviceConfirmationRegistrationActivity`, `ExportMigrationDataExportedActivity`, `BanAppealActivity` (Extra `launch_source`), `DeleteAccountConfirmation` und den Default-Einstieg `RegisterPhone`. Eine Preference `logged_out_phone_fallback_pending` setzt bei `RegisterPhone` fort (`main/me/logged-out phone fallback resume`). Ein geminteter IDV-Token (`minted_idv_token`, `minted_idvtoken_expiry_time_secs`) wird geprüft, ein abgelaufener oder leerer setzt den Remediation-Flow zurück. Welche numerischen Status welchem serverseitigen Schritt entsprechen, ist aus den Tag-Namen abgeleitet (inferred).

### 3.2 Registrierungs-Screens (found, alle nicht exportiert)

| Gruppe | Activities (`com.whatsapp.registration.app.*`, sofern nicht anders angegeben) |
|-------|--------------------------------------------------------------|
| Einstieg | `EULA` (Tag `eula_screen` / `eula_with_language_selector`), `phonenumberentry.RegisterPhone`, `RegisterAsDependentActivity`, `RegTabletIntroActivity`, `RegTabletChooseOptionActivity` |
| Berechtigungen | `RegPermissionsExplainerActivity`, `RegNotificationPermissionPrimerActivity` |
| Verifizierung | `verifyphone.VerifyPhoneNumber`, `sendsmstowa.SendSmsToWa`, `ManualSmsRequest`, `flashcall.PrimaryFlashCallEducationScreen`, `email.RegisterEmail`, `email.VerifyEmail`, `email.EmailEducationScreen`, `email.UnverifiedEmailSetupRegUpsellActivity`, `email.ConfirmEmailSetupRegUpsellActivity`, `backuptoken.BackupTokenEducationScreen`, `VerifyTwoFactorAuth` |
| Account-Schutz | `accountdefence.DeviceConfirmationRegistrationActivity`, `accountdefence.ui.OldDeviceSecureAccountActivity`, `OldDeviceSecureAccount2FaActivity`, `OldDeviceMoveAccountNoticeActivity` |
| Sperren | `parole.CustomRegistrationBlockActivity`, `downgrade.DowngradeFrictionActivity`, `com.whatsapp.userban.ui.BanAppealActivity` |
| Migration | `directmigration.RestoreFromConsumerDatabaseActivity`, `MigrationStartTransferActivity`, `RequestPermissionFromSisterAppActivity`, `com.whatsapp.migration.transfer.ui.*` |
| Name / Nummernwechsel | `RegisterName`, `phonenumberentry.ChangeNumber*` |
| Companion-Modus | `com.whatsapp.companionmode.registration.ui.RegisterAsCompanionActivity`, `RegisterAsCompanionEnterNumberActivity`, `RegisterAsCompanionLinkCodeActivity`, `CompanionBootstrapActivity`, `CompanionPostLogoutActivity` |
| Ausgeloggt | `logout.ui.PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`, `loginfailure.LogoutMessageActivity` |
| Support | `inappsupport.ui.app.LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity` |

### 3.3 Sprach- und Länderauswahl (found)

| Eintrag | Detail |
|------|--------|
| Sprache | `LanguageSelectorBottomSheet`, geöffnet aus `EULA` (Funnel-Event `language_selected`; Metriken `language_selector_clicked_count`, `language_selector_time_spent` in `K49`); die Settings-seitige `FullScreenLanguageSelectorActivity` ist nicht exportiert |
| Ländernamen | 63 Offline-Tabellen `assets/country_names_<lang>.tsv` (`ISO code<TAB>name`); kein Netzwerk-Lookup für die Auswahl gefunden |
| Nummern-Prefill | `RegisterPhone` nutzt Google-Phone-Number-Hints (`RegisterPhone/launchGooglePNHints`) und einen "Wie lautet meine Nummer"-SIM-Pfad, der eine Telefon-Permission braucht; EULA-Extras `RegisterPhone.phone_number`, `country_code`, `auto_submit_after_prefill`, `one_click_from_eula` |
| Rechtliche Links auf `EULA` | `https://www.whatsapp.com/legal/terms-of-service` oder `/terms`, `privacy-policy` oder `privacy-policies` (Variante je nach Config) |

---

## 4. Deep Links und Web-Links

### 4.1 Einstiegs-Aliase (found)

| Alias | Ziel | Filter |
|-------|--------|---------|
| `TextAndDirectChatDeepLink` | `DeepLinkActivity` | `http(s)://api.whatsapp.com`, `wa.me`; `https://[www.]whatsapp.com` Pfade `/channel`, `/channel_status`, `/updates`, `/aimediainput`, `/aivoice`, `/dl`, `/privacy/disclosure`, `/wamo/status/link-{instagram,facebook}-in-house-ad`; Schemes `whatsapp`, `whatsapp-smb`, `whatsapp-consumer`, `whatsapp-sheet` (Host-Listen, 100+ Hosts) |
| `VerifyOtpDeepLink` | `DeepLinkActivity` | `http(s)://b.whatsapp.com`, `http(s)://v.whatsapp.com` |
| `FoaDeeplinkActivityAliasUniversalLink`, `FoaDeeplinkActivityAliasAppScheme` | `DeepLinkActivity` | kein Filter in diesem Manifest (für die Deep-Link-Library der Meta-Family deklariert) |
| `AcceptInviteLinkActivityDeepLink` | `HomeActivity` | `chat.whatsapp.com` |

`DeepLinkActivity` selbst ist nicht exportiert; jeder externe Pfad läuft über einen Alias. Alle Filter mit `autoVerify="true"` decken nur https-Hosts ab. Mehrere Filter auf `whatsapp`, `whatsapp-consumer`, `whatsapp-smb` tragen sowohl `VIEW` als auch die Custom-Action `com.whatsapp.DEEP_LINK_REDIRECT`, daher beantwortet der Alias einen expliziten Intent mit dieser Action aus jeder App (found: Filterform).

### 4.2 Links, die den Status vor der Registrierung behandeln (found)

| Link | Parser-Anker | Verhalten |
|------|---------------|-----------|
| `https://[www.]whatsapp.com/dl?wsu=<6 digits>` | `IJB.A01`: Pfad `dl`, Query `wsu` passend zu `\d{6}`, Log `DeepLinkHelper/parseUri/web signup uri`, Code **193** | Web-Sign-up-Übergabe; Wert clientseitig nur per Regex validiert |
| `whatsapp://s/signup` (einzelnes Pfadsegment `signup`) | `IJB.A01` Code **216**, gesteuert durch ab-props **25005** oder **25801**; Handler `handleInAppSignupDeepLink` verlangt Scheme `whatsapp` und Query `s` | In-App-Sign-up; loggt über `ApiSignupFlowLogger` mit `signup_id` (Host-`s`-Paarung aus dem Manifest abgeleitet, inferred) |
| `https://v.whatsapp.com/<code>`, `https://b.whatsapp.com/<code>` (letztes Pfadsegment) und `whatsapp://r?c=<code>` | Registrierungszweig von `DeepLinkActivity`, Log `DeepLinkActivity/Registration deeplink/registration state:` | E-Mail-OTP-Link. Status 1 öffnet `RegisterPhone` mit Extra `tapped_sms_link`; Status 2 öffnet `VerifyEmail` mit `email_otp`, `entrypoint`, `session_id`, `challenge_flow=false` und meldet `email_otp_deeplink_redirect_to_register_name`; andere Status leiten zu den Settings um (`settings_verification_email_address_verified`, inferred). Der Code wird als Extra weitergereicht; die Verifizierung läuft serverseitig (unknown) |
| `whatsapp://code-linking?auth=<nonce>` | Code **77**, Handler `maybeStartCodeLinkingFlow`, ab-prop **4560** (`ENABLE_CODE_LINKING_DEEP_LINK_CODE`), Pref `adl_deep_link_nonce` mit einem Fenster von 300000 (Einheit als ms abgeleitet, inferred) | Code-Flow für Linked Devices; übersprungen, wenn das Flag aus ist oder der Nonce älter als das Fenster ist |
| `whatsapp://help/<segment>` | Code **62**; Offline-Zweig loggt `DeepLinkActivity/help/no-connectivity` | Hilfeartikel |
| `whatsapp://support` | Code **30** (aus dem Parser extrahiert; Handler loggt `about/no-connectivity`) | Support- / Info-Screen, braucht Konnektivität |

### 4.3 Das Gate vor der Registrierung

| Anker | Befund | Tier |
|--------|---------|------|
| `DeepLinkActivity/deeplink not allowed before registration/` und Grund `not_allowed_before_registration` | vorhanden; die Reason-Enum bildet den Wert 0 auf diesen String ab; der Erzeuger von Reason 0 für gewöhnliche Links wurde nicht isoliert | found (Strings), unknown (Erzeuger) |
| Handler pro Code | jeder Handler prüft den Registrierungsstatus selbst (Aufrufe `C0Gk.A0C()` / `A02()` in den Switch-Bodies) | found |
| Allowlist der Codes im ausgeloggten Zustand | nicht neu aufgelöst: `C02T` ist in diesem Build ein Serial Executor und `C02U` eine gemeinsame Integer-Konstantenklasse, frühere Klassennamen passen daher nicht | unknown |
| `JXK`-Ergebnis (`code`, `source`, Reason), gebaut von `IJB`, `IJC`, `IJD`, `IJE` | Parser-Ausgabe, konsumiert von `DeepLinkActivity.A0w` | found |

Das Auflösen von Inhalten (Chat, Channel, Verzeichnis) braucht weiterhin einen Account: Gruppen-Einladungs- und `wa.me/<phone>`-Handler nutzen die authentifizierte Session (aus Handler-Namen abgeleitet, inferred; nicht Ende-zu-Ende verfolgt).

---

## 5. Ohne Account kontaktierte Hosts und Endpunkte

### 5.1 Registrierungs-HTTP (found)

16 Pfade, XOR-Key 18 in `AbstractC45307Jps`, alle in 2.26.41.6 neu dekodiert: `/v2/exist`, `/v2/code`, `/v2/register`, `/v2/security`, `/v2/challenge`, `/v2/passkey_auth`, `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop`, `/v2/device_logout_send`, `/v2/device_logout_fetch`, `/v2/wfs`. Zwei weitere Konstanten dekodieren zu `ENC` und `H` (Verwendung unknown). Feldlisten der ersten Gruppe stehen in [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) Abschnitt 3.1. Der Basis-Host `v.whatsapp.net` ist der Name in der einkompilierten Tabelle (5.4); der Code, der Host und Pfad zusammenfügt, liegt in den wamsys- / Kotlin-Stacks und wurde hier nicht gelesen (inferred).

Der Selektor `K49.A0b` wählt den Kotlin-Stack (`KotlinRegistrationBridge`) oder den nativen `wamsys`-Stack; der native Stack muss zuerst gebootstrappt werden (`ensureWamsysForRegBootstrapped`, Fehler `FAIL_TO_INITIALIZE_WAMSYS`).

### 5.2 Weitere HTTPS-Endpunkte (Literal found, Auth wie angegeben)

| Host / URL | Methode | Auth im Code | Aufrufer | Account-los? |
|------------|--------|--------------|--------|---------------|
| `https://www.whatsapp.com/contact/noclient/verification/` | Multipart-POST | keine | `C47328KmN` case 0 (Support-Formular) | ja |
| `https://graph.<pref_graphql_domain>/graphql` (Default `graph.whatsapp.com`) | POST JSON | einkompilierter App-Client-Token im Body `access_token` | `AbstractC40195HfH` und Unterklassen | ja (Ban-Status / Einspruch) |
| `https://crashlogs.whatsapp.net/wa_clb_data`, `/wa_fls_upload_check`, `/wa_profilo_data`, `/whatson_logs_upload` | POST | einkompilierter App-Token (Log-Upload ergänzt `access_token`, `type`, `from_jid`, `ticket_id`, `build_id`) | `C10V`, `C05640An`, `ExceptionsUploadService`, `ProfiloUploadService`, `CM8` | läuft ohne Login; Inhalt von `from_jid` im ausgeloggten Zustand unknown |
| `https://acs.whatsapp.com/graphql` | POST | ACS-Token oder OHAI-Config (keine JID) | `C31991Nz`, `R5t` | ja (de-identifizierte Requests) |
| `https://static.whatsapp.net/wa/static/{downloadable,network_resource,payments/*}`, `/sticker?...`, `/payments/background` | GET | keine | UI-Asset-Loader | ja |
| `https://mmg.whatsapp.net/proxygen/health`, Basis `https://mmg.whatsapp.net` (Config 22436) | GET | keine | Media / Health | ja |
| `https://www.gstatic.com/recaptcha/verify_key/orcas/prod/android/verify_key.txt` | GET | keine | `C44464JbH` (genutzt von `RequestCodeRepository`, `VerifyCodeRepository`, `VerifyPhoneNumber`) | ja (Registrierungs-Captcha) |
| `https://www.whatsapp.com/compliance/xfac/mint` | POST Form | keine gesehen | `CommonRemediationApi` (Alters-Remediation, `minted_idv_token`) | vor der Registrierung erreichbar: unknown |
| `https://www.whatsapp.com/v1/auth/canonical/token/` | POST Form `nonce`, `user_id`, `device_id`, `client_pub_key` | keine | `CanonicalUserCompanionDeviceManager` | Companion- / Linked-Account-Pfad, nicht reine Pre-Registrierung |
| `https://api.whatsapp.net/support/add_bug_attachment` | Multipart-POST | `Authorization: Bearer <token>` | `PostBugAttachmentUploader` (In-App-Bugreport) | nein (Token-gebunden) |
| `https://graph.whatsapp.net/v2.2/maps_configs?...&access_token=` (Default `graph.facebook.com`) | GET | App-Token in der URL | `N6n` Map-Config | Auslöser nicht vor der Registrierung (inferred) |
| `https://api.whatsapp.net/calendar/integrations/` | Request | Session | Kalender-Feature | nein |

Einkompilierte Tokens: Es gibt zwei Facebook-artige Formen, `WA|<app_id>|<secret>` im Default des Graph-Clients und `<app_id>|<secret>` im Log-Uploader. Werte werden hier nicht wiedergegeben. Sie identifizieren die App, nicht einen Nutzer.

### 5.3 DNS- und Konnektivitäts-Bootstrap (found)

| Eintrag | Detail |
|------|--------|
| Einkompilierte Tabelle `AbstractC47101wK` | Host auf IPv4- / IPv6-Liste für 18 Namen: `e1..e16`, `g`, `v` unter `.whatsapp.net` (jeweils mit Zwilling mit abschließendem Punkt); kein Netzwerk nötig |
| `C36881dC` (DnsCache) | Reihenfolge: primärer Resolver, MNS-DNS-Resolver (`DnsCache/resolveViaMnsDns`, der String `v.whatsapp.net` wird in diesem Zweig getestet), sekundärer Resolver, hartkodierte Tabelle; hartkodierte Lookups scheitern mit `no hardcoded ips found for <host>`, wenn die Tabelle keinen Eintrag hat, und werden mit `hardcoded dns resolver disabled` übersprungen, wenn das Option-Bit aus ist |
| Chat-Host | Eintrag `g.whatsapp.net` wird direkt gelesen (`C36881dC.A01`) |

Das Wire-Format des MNS-Resolvers liegt im nativen Code: unknown.

### 5.4 REST-Pfade, die nicht existieren (found negative)

Es wurde kein unauthentifizierter REST-Abruf für Gating oder Config (`/gk`, `/props`, `/config`) gefunden. Experiment-Config vor dem Login kommt über die Registrierungs-HTTP: `/v2/reg_onboard_abprop` (`K49.checkPreChatdABProps`) sendet `ab_hash` aus der Pref `pref_pre_chatd_ab_hash`, `ab_exposure`/`ab_key` aus `pref_pre_chatd_ab_key`, dazu die Gerätefelder aus Abschnitt 7.

---

## 6. Support-Formular im ausgeloggten Zustand (found)

`LoggedOutContactFormActivity` (nicht exportiert) ist der einzige vollständig account-lose Support-Flow in diesem Build.

| Intent-Extra (Präfix `com.whatsapp.inappsupport.ui.app.LoggedOutContactFormActivity.`) | Verwendung |
|------|-----|
| `PhoneNumber`, `CountryCode` | vorausgefüllte Nummer; leerer String, wenn nicht vorhanden |
| `From` | Label des Einstiegspunkts |
| `ServerStatus` | vom Aufrufer übergebener Status-String (inferred: Status des Registrierungsservers) |
| `IsRegistrationVerification` | boolean; bei Erfolg folgt ein weiterer Aufruf (Ziel nicht aufgelöst) |
| `SupportUserContext` (`K8W`) | Einstiegspunkt und CMS-IDs (`Entry point`, `Cms ids`) |

Formularfelder: E-Mail (Vorschlags-Chips `@gmail.com`, `@hotmail.com`, `@icloud.com`, `@outlook.com`, `@yahoo.com`), Beschreibung, bis zu 3 Screenshots aus `MediaStore`.

Absenden (`C47328KmN` case 0, Tag `logged_out_contact_form`, abschließendes Argument 20 mit ungeklärter Bedeutung):

| Teil | Name | Inhalt |
|------|------|---------|
| field | `email` | eingegebene E-Mail |
| field | `message` | Beschreibung |
| field | `platform` | Literal `ANDROID` |
| field | `phone_number` | eingegebene Nummer |
| field | `debug_info` | von `C10V.A08` gebauter Text (Abschnitt 7.3) |
| file | `log_data` | `logs.tar.gz` des Client-Logs (zuvor rotiert und komprimiert) |
| files | `attachment_<n>` | Screenshots, neu als JPEG Qualität 80 kodiert, Grenze 2048 px, nur behalten bei 10 MiB oder weniger |
| extra | `skip_saga_copy=true`, `saga_copy=true`, `pn` | `pn` = Ländercode + Nummer, wenn beide nicht leer sind |

Ergebnis: Der HTTP-Status geht an einen Result-Callback (`C46422KQg`); ein Fehler erscheint als `Server error: <status>` oder `Network error`; bei Erfolg öffnet sich `LoggedOutContactSuccessActivity` (Extra `...Email`). Die genaue Abbildung von Status auf Erfolg wurde nicht gelesen. Der Aufruf ist ein einfacher HTTPS-POST über den App-HTTP-Client; es ist kein GraphQL-Aufruf. Pro Absenden wird eine zufällige `anid`-UUID (7.1) erzeugt.

---

## 7. Vor dem Login gesendete Identifier

### 7.1 Identifier-Tabelle

| Identifier | Wo | Quelle | Hinweise | Tier |
|------------|-------|--------|-------|------|
| `fdid` | `/v2/pre_pn_client_log`, Registrierungs-Requests | `C38141gV.Ax2()`: zufällige `UUID.randomUUID()`, in Prefs als `phoneid_id` + `phoneid_timestamp` gespeichert | bleibt über Registrierungsversuche hinweg bestehen; dieselbe ID liefert `PhoneIdRequestReceiver` | found |
| `fid` | Registrierungs-Requests | `C47381wu.Ax2()`: Prefs `phoneyid_id` + `phoneyid_timestamp`, nur wenn vorhanden als `<id>|<timestamp>` gesendet | sekundäre Family-ID; Erzeuger des Werts nicht verfolgt | found (Verwendung inferred) |
| `anid` | Support-Formular | `C11J.A01()`: `UUID.randomUUID()` pro Aufruf, zusätzlich als WAM-Event geloggt | zufällige ID pro Absenden | found |
| `advertising_id` / `android_advertising_id` | `/v2/exist`, `/v2/code`, `/v2/register`; Funnel-Log | Google-Advertising-ID, wenn verfügbar | aus dem Debug-Log-String des Funnel-Loggers ausgeschlossen | found |
| `authkey`, `e_ident`, `e_keytype`, `e_regid`, `e_skey_id`, `e_skey_val`, `e_skey_sig`, `e_pq_last_resort_{id,val,sig}` | Registrierungs-Requests | `C45446JsB`: Noise-Static-Key des Clients und Signal-Key-Bundle | öffentliches Material | found |
| `gpia` | Registrierungs-Requests | Play-Integrity-Standard-Token, Flag-gesteuert | siehe [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) | found |
| `ab_key`, `ab_hash`, `ab_exposure` | `/v2/exist`, `/v2/pre_pn_client_log`, `/v2/reg_onboard_abprop` | Prefs `pref_pre_chatd_ab_key` / `pref_pre_chatd_ab_hash` | Experiment-Bucket | found |
| `device_country` | Funnel-Log | `TelephonyManager.getSimCountryIso()` in Großbuchstaben, `ZZ` wenn nicht vorhanden | | found |
| `access_token` (App) | Graph, Log-Upload | kompilierte Konstante | App-Identität, kein Nutzer | found |
| `request_token` / `token` | Ban-Status / Einspruch | Pref `wfac_ban_status_token` (Status) und der gespeicherte Appeal-Token | opak, vom Server beim Ban ausgestellt ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md)) | found |
| `from_jid` | Log-Upload | Account-JID, wenn vorhanden | Inhalt im ausgeloggten Zustand unknown | found (Feld), unknown (Wert) |
| `registration_trace_id`, `request_id`, `nonce_encryption_key` | Account-Recovery-Mutation | `AccountRecoveryManager` (Abschnitt 8.2) | | found |

### 7.2 Geräteattribute in Registrierungs-Requests (found, `K49`-Helfer `A0O`, `A0Q`, `A0R`, `A0U`, `A0W`, `A0X`)

`network_radio_type`, `simnum` (`0` / `1`), `hasinrc` (Datei `rc2` vorhanden), `pid` (Prozess-ID), `device_ram`, `sim_type`, `airplane_mode_type`, `cellular_strength` (Signalstufe, Default `5`), `roaming_type`, `preloads_app_manager_id`, `preloads_attribution`, `entrypoint` (`create_paa` oder `suma`), `tos_version` (`5`), `old_phone_number` (Nummernwechsel-Flow). Telemetrie-Metrikschlüssel in derselben Klasse (found, Verwendung im Request nicht bestätigt): `network_operator_name`, `sim_operator_name`, `sim_state`, `read_phone_permission_granted`, `mistyped`, `c2dm_reg_id` (aus Prefs gelesen).

### 7.3 Funnel-Log-Inhalt (found, `PrePnBaseFunnelLogger$sendPrePNFunnelLog$1`)

Bevor eine Nummer existiert, sendet der Client: `current_screen`, `previous_screen` (Pref `pref_previous_screen`, Default `unknown`), `action_taken`, `event_name`, `access_funnel_type=wa`, `app_campaign_download_source`, `is_add_account_flow`, `android_advertising_id`, `ab_key`, `device_country`, `fdid`, die obigen Geräteattribute und `entrypoint`. In Add-Account- oder Logged-out-Fallback-Flows sendet er zusätzlich `primary_logout_session_id` und `number_of_accounts`. Das Senden wird übersprungen, wenn der wamsys-Bootstrap fehlschlägt.

### 7.4 `debug_info` des Support-Formulars (found, `C10V.A08`, JID-Argument ist in diesem Aufruf `null`)

In den Text geschriebene Labels: `useragent`, `Socket Conn`, `Connection`, `Server`, `Datacenter`, `Sim`, `Free Space Built-In` / `Removable`, `Network metered` / `restricted`, `Data roaming`, `Tel roaming`, `Diagnostic Codes`, `ABprops hash state`, `Screen reader`, `Fingerprint eligible`, Backup-Statusfelder, `Is Companion`, `Number of Accounts`, `Mobile Build Id`, `wfl_state`, `isMetaVerified`, `Mistyped` / `Mistyped Last6` / `L Distance` (Vergleich der eingegebenen Nummer mit der SIM-Nummer), dazu Identifier des letzten Anrufs, wenn eine Anrufhistorie existiert. Das Label `entity id` wird nur geschrieben, wenn eine JID übergeben wird, was hier nicht der Fall ist.

---

## 8. Graph- und MEX-Aufrufe ohne User-Session

### 8.1 Graph-Requests mit App-Token (found)

Die Basisklasse `AbstractC40195HfH.CND` baut `https://graph.<A0f()>/graphql` (`A0f()` = Pref `pref_graphql_domain`, Default `whatsapp.com`; die Unterklassen `GEV`, `GEX`, `GET`, `GEW`, `GEU` und die Meta-Account-Familie `C45F` wechseln auf `facebook.com` / `instagram.com`). Body-JSON: Operationsvariablen, `access_token` (kompilierter Token, wenn die Unterklasse keinen übergibt), `doc_id`, `lang`, `Content-Type`. Der Header `X-FB-Request-Analytics-Tags` wird ergänzt, wenn er fehlt.

| Klasse | doc_id | Variablen | Zweck |
|-------|-------:|-----------|---------|
| `C37604GYf` | **4276154569100535** | `app_id` (`dev.app.id`), `request_token` | WFAC-Ban-Status-Poll (`WfacBanRepository/fetchBanStatus`, Token aus Pref `wfac_ban_status_token`) |
| `C37409GLo` | **27883644401256929** oder **4276154569100535** (boolean) | dieselben | Ban-Status über `HG2.A01` |
| `C37414GLt` | **38509456535312323** oder **5473316762755318** (boolean) | `app_id`, `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}`; Klartext `{token, debug_info, description}`, Kontext `WA_INAPP_BAN_APPEALS` | Ban-Einspruch absenden (`C40191HfD`); Details in [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) Abschnitt 10 |
| `C37408GLn` | **5803265299734043** | `app_id`, `client_pub_key` | Zweck unknown (sendet einen Client-Public-Key); Aufrufer nicht verfolgt |
| `C37601GYc`, `GYd`, `GYe` | `GYd` **25453433540999208**, `GYe` **25974020015520396** (`GYc` trägt in der eigenen Klasse keine ID) | `caller_name` `fx_waffle_contextual_pause_account_match`, `wa_waffle_certs`, `fx_waffle_foa_unpause` | Helfer für Meta-Account-Linking |
| `C37605GYg`, `GYh`, `GYi` | **26573478745654327**, **26742313962085910**, **27503298369362501**, **28331348373116386**, **25840634418966704** | Header `IG-Set-Waffle-Graphql-Access-Token`, Key `ACCESS_TOKEN` | Facebook- / Instagram-Account-Linking; ein Token des verknüpften Accounts ist nötig (aus Header- und Key-Namen abgeleitet, inferred) |
| `C37413GLs` | **7236799486398397** | `batches`, `device_model`, `device_os`, `device_os_version`, `event_time`, `is_employee`, `primary_locale` | Client-Event-Batches (aus Variablennamen abgeleitet, inferred) |

Die doc_id 6960707423955525 (eine für ältere Builds berichtete Legacy-Appeal-Mutation-ID) kommt in 2.26.41.6 nicht vor. Die Operationsnamen der Appeal- und Status-Requests werden von diesen Klassen nicht getragen (unknown).

Unterschied zu [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) Abschnitt 10: Für `C37414GLt`, `C37409GLo` und `C37604GYf` ist der Host `graph.<pref_graphql_domain>` (Default `graph.whatsapp.com`); nur die oben aufgeführten Unterklassen überschreiben ihn auf `facebook.com`.

### 8.2 MEX-Operationen mit Call Site zur Registrierungszeit oder im ausgeloggten Zustand (found, Schema `whatsapp-android-mex`)

doc_ids aus `assets/whatsapp-android-mex_client_persist_ids.json` (und den `www`- / `wamo`-Dateien, wo vermerkt).

| Operation | doc_id | Call Site |
|-----------|-------:|-----------|
| `GetAutoConfConfidenceChallenge` | 25578301865133112 | `C40175Het`, `C40196HfI` (Autoconf-Confidence-Ping) |
| `ValidateVerifierConfidence` | 25879669248324812 | `C40196HfI`, `C40197HfJ` |
| `FetchReachoutTimelockQuery` | 25627902213558773 | `RunnableC23952AUh` |
| `RemoveAccountReachoutTimelock` | 25040013452293167 | nicht verfolgt |
| `UserCountryCodeGet` | 25292528387076991 | `MexUserCountryCodeRepository` |
| `MobileConfigFetchQuery` | 29248978061376279 | nicht verfolgt |
| `SubmitAge`, `GetAgeExperience`, `SetAgeExperienceMutation` | 26049558371296621, 26567868986241476, 26051006311231325 | Alters-Flows |
| `TosSetResult` | 25225843213776555 | Annahme der Nutzungsbedingungen |
| `GetWaOldResponse` | 25784374561179853 | Verifizierung über altes Telefon |
| `WWWTriggerAcountRecovery` | 24896267680055094 | `AccountRecoveryManager` (Variablen `nonce_encryption_key`, `use_case`, `registration_trace_id`, `request_id`) |
| `WWWCreateUser`, `WWWDeleteUser`, `WWWGetCertificates` | 8548056818544135, 7989555047767245, 25094190163544446 | Account-Linking |
| `OhaiKeyConfigQuery` | 25069818679280758 | `N5I` (ACS- / OHAI-Bootstrap) |
| `CreateEnforcementAppeal` | 26933630359642347 | Newsletter-Enforcement-Client |
| `NewsletterCreateReportAppeal` (mex), `CreateGroupSuspensionAppealMutation` (www), `WamoReportPromoAppealV2Mutation` (wamo) | 27792557363683798, 25646047815072526, 26867425009592691 | Appeal-Operationen (Account-gebunden; in den Assets vorhanden) |

MEX wird als IQ `xmlns="w:mex"` mit `<query query_id=...>` (`C19370nI`) über die Chat-Verbindung (`WAChatdGraphQLClient`) gesendet. Ob diese Operationen in einer Session ohne Account laufen, ist nicht belegt: siehe 8.3.

### 8.3 Chat-Verbindung ohne JID (found)

`ConnectionThread.connect` (`HandlerThreadC12340b0`) liest die eigene JID; ist sie null, läuft es nur weiter, wenn das Companion-Registrierungs-Flag (`C06830Gm.A02()`) true ist, andernfalls liest es eine zweite JID-Quelle (`Ash()`), und wenn auch diese null ist, loggt es `ConnectionThread/connect/ignored/jid null and not in companion reg` und kehrt zurück. Die Registrierung des Primärtelefons nutzt daher keine Chat-Verbindung mit Null-JID (konsistent mit [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) Abschnitt 6.4). Die Bedeutung der zweiten Quelle ist abgeleitet (inferred; eine gespeicherte oder ausstehende Registrierungs-JID, nicht aufgelöst). Welche Session die MEX-Aufrufe zur Registrierungszeit aus 8.2 trägt, ist unknown.

### 8.4 De-identifizierte Requests (found)

`PandoGraphQLRequest.requireAcsToken()` und `requireOhaiConfig()` werden von `C6GN` gelesen; ein mit `@deidentified` markierter Request ohne ACS-Token oder OHAI-Config wirft eine Exception (`Request was marked with @deidentified, but no ... was provided`). Felder von `AcsOhaiConfig`: Projektname, doc id, `graphQlUrl=https://acs.whatsapp.com/graphql`, surface, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`. Welche Operationen das Flag tragen, ist in den Assets `*_pando_flatbuffer_data.bin` kodiert: unknown.

---

## 9. Exportierte IPC-Oberflächen mit Prüfungen im Code

Alle Einträge sind ohne Manifest-Permission exportiert, sofern nicht anders vermerkt. Dieser Abschnitt listet die im Code gefundenen Kontrollen, kein Urteil über ihre Stärke.

### 9.1 `PhoneIdRequestReceiver` (`com.facebook.GET_PHONE_ID`)

Ein Ordered Broadcast. Der Receiver liest ein `PendingIntent`-Extra `auth` aus den Result-Extras und nimmt `getCreatorPackage()`. Ein Package gilt als vertrauenswürdig, wenn der Hash seines Signing-Zertifikats in einem hartkodierten Allow-Set liegt (`AbstractC28130CKz.A04`, SHA-1 von Signing-Zertifikaten, Werte nicht wiedergegeben; ein zweites SHA-256-Set wird in `CHA.A02` genutzt). Ein vertrauenswürdiger Aufrufer erhält die Phone-ID und ihren Timestamp als Broadcast-Result (`setResult(-1, id, {timestamp})`); ein alternativer Pfad liefert die sekundäre ID, wenn Flag **3651** es erlaubt. Der dekompilierte Kontrollfluss um die Trust-Variable ist unvollständig, daher ist die genaue Rangfolge abgeleitet (inferred).

### 9.2 Family-of-Apps-Provider (found)

| Komponente | Gefundene Kontrollen |
|-----------|----------------|
| `FamilyAppsCredentialsProvider` | `getCallingPackage()`; Handler-Map pro Selection; Aufrufer-UID wird zu einem Zertifikat aufgelöst und gegen das Trusted-Set des Handlers geprüft (`C45775Jyk.A01`); Eignung des Link-Managers (`WfalManager.A00`); Feature-Flags; der Link-Status muss im Eligible-Set des Handlers liegen; liefert einen Cursor mit 3 Spalten (Auth-Proof, Bundle, TTL) aus den Prefs `pref_foa_nta_ipc_bundle_auth_proof`, `pref_foa_nta_ipc_bundle`, `foa_nta_ipc_bundle_ttl`; Fehler bei abgelaufenem oder fehlendem Cache. Auflösung von "NTA" unknown |
| `FamilyAppsUserValuesProvider` | eine Selection `foa_wo_wa_link_eligibility_values`, `getCallingPackage()` wird gelesen |
| `WaAccountsCenterService` | Action `com.whatsapp.wfl.OPERATION`; Klassenrumpf ist im Dekompilat ein Stub (Prüfungen unknown) |
| `QuickSendsContactsProvider` | Validierungsschritte für `getCallingPackage()` werden geloggt (`validation_start` / `validation_end`); liefert verschlüsselte `.enc`-Fotodateien und Kontaktspalten (`obfuscated_chat_id`, `display_name`, `profile_photo_uri`, `photo_key`) |
| `OrbitSsoProvider` (`com.whatsapp.orbit.v2.sso`) | Feature-Flag-Gate; das Caller-Package muss in einer Allow-List stehen (`AbstractC62035Rsx.A00`, sonst `SecurityException ... is not allowlisted`); eine Precondition-Prüfung (`BS3()`) vor jeder Methode; Methoden `get_profile` (liefert `display_name`, `phone_number`, `avatar_uri`, `avatar_mime_type`), `get_accounts`, `get_nonce`, `get_token`; Dateipfad `avatar` nur lesend. Die Allow-List wird in `A01()` nach Package-Name abgeglichen; eine Zertifikatsprüfung, falls vorhanden, steht nicht in dieser Methode (unknown). Was `BS3()` testet, ist als Login-Status abgeleitet (inferred) |
| `OrbitMessagesProvider` (`com.whatsapp.orbitmessages`) | Datei-Öffnen nur im Modus `r`, letztes Segment `media`, `media_handle`-Werte mit Präfix `v1.` werden mit AES-GCM entschlüsselt; Aufruferprüfungen nicht gefunden (unknown) |
| `OrbitCompanionLinkActivity` | liest `getCallingPackage()` und das Extra `qr_data`; Hold- / Consent-Timer; liefert nur das Ergebnis zurück (`return_result_only`) über `CompanionHelloConfirmationActivity` |
| `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | nicht analysiert |

### 9.3 OTP-Handshake (`OtpRequestedReceiver`)

Erwartet ein `PendingIntent`-Extra `_ci_` (Caller-Identität) und eine optionale UUID `request_id` (per Regex geprüft). Hinterlegt das Creator-Package zu einem erzeugten Wert, loggt ein WAM-Event und antwortet, wenn Flag **6617** an ist oder das Package in der Liste aus Config **7050** steht, mit einem Broadcast `com.whatsapp.otp.OTP_HANDSHAKE_CONFIRMATION` an dieses Package, der die `request_id` trägt. Ein fehlendes `PendingIntent` wird abgewiesen (`PendingIntent missing from handshake Intent`). In diesem Receiver wurde keine Registrierungsprüfung gefunden.

### 9.4 `AccountTransferReceiver`

Reagiert nur auf `com.google.android.gms.auth.START_ACCOUNT_EXPORT`, und nur wenn das Gerät einen sicheren Keyguard hat und eine Capability-Prüfung besteht (`AbstractC21360rJ.A01`). Der Export selbst läuft auf einem Background-Executor (`C05X.A02(...).CVx`); Inhalt unknown.

---

## 10. Einstiegspunkte für Ban-Ansicht und Einspruch

| Einstieg | Mechanismus | Evidenz |
|-------|-----------|----------|
| Kaltstart im WFAC-Status | `Main` Status 21 startet `WfacBanActivity` über `HBC.A00` | found (3.1) |
| `BanAppealActivity` | nicht exportiert; gestartet von `Main` (Extra `launch_source`) und vom Permanent-Ban-Flow | found |
| Ban-Status-Poll | Graph, `wfac_ban_status_token`, 5-s-Throttle-Pref `wfac_last_ban_status_fetch_timestamp_ms` | found ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 2.2) |
| Einspruch absenden | Graph mit verschlüsseltem `user_request` (8.1) | found |
| Registrierungs-Antwort | `/v2/register`-Felder `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `custom_block_screen`, `version_upgrade` | found ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) 3.3) |
| Support kontaktieren | `LoggedOutContactFormActivity` (Abschnitt 6), Flag `IsRegistrationVerification` für Registrierungsfehler | found |
| Deep Links | `whatsapp://support`, `whatsapp://help`, `v.whatsapp.com` / `b.whatsapp.com` | found (4.2) |

Die Identität pro Nutzer im Einspruchspfad ist der opake, vom Server ausgestellte Token, keine Telefonnummer und keine Geräte-ID (die oben genannten Token-Feldnamen; Herleitung unknown).

---

## 11. Fehlerfälle und Gotchas

| Symptom | Ursache | Hinweise |
|-------|-------|-------|
| `ConnectionThread/connect/ignored/jid null and not in companion reg` | keine JID und keine Companion-Registrierung | normal vor der Registrierung; die Registrierung nutzt HTTPS |
| `FAIL_TO_INITIALIZE_WAMSYS` | Bootstrap des nativen Stacks fehlgeschlagen (`ensureWamsysForRegBootstrapped`) | Registrierungs-HTTP und Funnel-Log vor der Nummer werden übersprungen |
| `DeepLinkActivity/deeplink not allowed before registration/` | Link-Code durch das Gate blockiert | Allowlist nicht aufgelöst (4.3) |
| `Request was marked with @deidentified, but no ...` | ACS- / OHAI-Config fehlt | Request nicht gesendet |

---

## 12. Wichtige Unterscheidungen

| Nicht verwechseln | Fakt |
|----------------|------|
| Exportiert vs. ohne Account erreichbar | 97 exportierte Einträge; die meisten tun nichts Nützliches, bis ein registrierter Account existiert; nur die Einträge in 2.2 und 4.2 behandeln den Registrierungsstatus |
| App-Token vs. User-Token | der kompilierte `WA|<app_id>|<secret>` identifiziert die App; Ban-Aufrufe ergänzen einen opaken Request-Token, keine User-Session |
| `fdid` vs. Advertising-ID | `fdid` ist eine von der App erzeugte UUID, die eine Neuregistrierung überlebt; die Advertising-ID ist der Google-Wert |
| Support-Formular im ausgeloggten Zustand vs. In-App-Support | das Formular postet mit eingetippten Feldern an `www.whatsapp.com/contact/noclient/verification/`; der In-App-Support nutzt die Session (nicht analysiert) |
| Registrierungs-HTTP vs. Chat-Verbindung | die Registrierung läuft über HTTPS `/v2/*`; ein Chat-Connect mit Null-JID gibt es nur für die Companion-Registrierung |

---

## 13. Kompletter Ablauf

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

## 14. Unbekanntes

| Frage | Warum unknown |
|-------|-------------|
| Welche Link-Codes vor der Registrierung erlaubt sind | Allowlist-Klasse nicht neu aufgelöst; Handler prüfen den Status einzeln, nur vier verfolgt |
| Erzeuger von Reason 0 (`not_allowed_before_registration`) | im großen `DeepLinkActivity`-Switch nicht isoliert |
| Zusammenfügen von Host und Pfad für `/v2/*`, die Konstanten `ENC`, `H` | wamsys- / Kotlin-Request-Builder nicht gelesen |
| Welche Session die MEX-Operationen zur Registrierungszeit trägt | Null-JID-Connect wird außerhalb der Companion-Registrierung abgelehnt; die Quelle `Ash()` ist nicht aufgelöst |
| Inhalt von `from_jid` in Log-Uploads im ausgeloggten Zustand | `AbstractC05620Al.A0G` ist abstrakt |
| Serverseitige Validierung von Tokens, Codes, Appeal-Payloads | Serverseite |
| Operationen mit `@deidentified` | in `*_pando_flatbuffer_data.bin`, kein Schema |
| Bedeutung von "NTA", des Erzeugers der sekundären ID `phoneyid_id`, von `c2dm_reg_id` als Request-Feld | nur Namen |
| Ob `HomeActivity` im nicht registrierten Zustand gestartet werden kann und was sie dann tut | Gate der Basisklasse nicht aufgelöst |
