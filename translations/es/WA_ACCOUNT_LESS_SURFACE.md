<!-- src-sha1: 166366154a0dd7893ab70aa91166a96d5a2e788f -->
# WhatsApp Superficie sin cuenta — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** qué expone el cliente Android sin una cuenta registrada o antes de completar el registro — componentes exportados del manifest (activities, aliases, services, receivers, providers), pantallas previas al registro y enrutamiento por estado de registro, deep links y enlaces web, endpoints HTTP y Graph no autenticados, tabla de hosts compilada, formulario de soporte sin sesión, estado de baneo y puntos de entrada de apelación, identificadores enviados antes del login, superficies IPC de terceros, qué sigue siendo desconocido

---

## 1. Qué significa "sin cuenta" en este build

No existe un único "modo sin sesión". Varias rutas independientes se ejecutan mientras el cliente no tiene un JID de usuario, ni una sesión de chat autenticada, o tiene un registro sin terminar. Cada ruta sustituye la cuenta por una credencial distinta. Todas las afirmaciones son análisis estático del APK decompilado (`versionCode 264100600`, target SDK 36, min SDK 23). No se observó nada en la red. Niveles: **found** = leído en código o manifest, **inferred** = deducido del código, **unknown** = no resoluble de forma estática. Documentación defensiva: se describen superficies y controles, no se ejercitan.

Los nombres ofuscados son específicos de cada build y se re-resolvieron a partir de strings estables en 2.26.41.6.

| Ruta | Credencial que sustituye a la cuenta | Transporte | Clases principales (2.26.41.6) |
|------|--------------------------------------|-----------|--------------------------------|
| Registro por teléfono | ninguna hasta `/v2/register`; la petición lleva el paquete de claves estáticas Noise e ids del dispositivo | HTTPS `/v2/*` | `K49`, `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Log del embudo previo al número | solo el phone id (`fdid`) | HTTPS `/v2/pre_pn_client_log` | `PrePnBaseFunnelLogger`, `K49` |
| AB props previas al chat | prefs `ab_key` / `ab_hash` | HTTPS `/v2/reg_onboard_abprop` | `K49.checkPreChatdABProps` |
| Estado de baneo / apelación | token opaco guardado al momento del baneo + client token de la app compilado | HTTPS Graph `graph.<domain>/graphql` | `AbstractC40195HfH`, `C37409GLo`, `C37604GYf`, `C37414GLt` |
| Formulario de soporte sin sesión | ninguna; email + texto libre + `anid` | HTTPS multipart POST | `LoggedOutContactFormActivity`, `C47328KmN` |
| Subida de crash / logs | token de la app compilado | HTTPS `crashlogs.whatsapp.net` | `C10V`, `C05640An` |
| Assets estáticos | ninguna | HTTPS GET | `static.whatsapp.net/*` |
| Graph con credencial anónima (ACS / OHAI) | token ACS o config de clave OHAI, sin JID | HTTPS `acs.whatsapp.com/graphql` | `C31991Nz`, `R5t`, `N5I` |
| Registro de companion | ninguna; la conexión Noise con JID nulo solo se permite aquí | Noise | `HandlerThreadC12340b0` |
| Fallback DNS incluido | ninguna | tabla compilada | `AbstractC47101wK`, `C36881dC` |

No se cubre aquí, ver los reportes enlazados: pasos del registro, métodos OTP y motivos de fallo ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) sección 3); tokens de atestación enviados en el registro ([WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)); máquina de estados del baneo y cifrado de la apelación ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) secciones 2, 10); login Noise y registro de companion ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)); telemetría WAM ([WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)).

---

## 2. Manifest: componentes exportados

### 2.1 Conteos (found, `AndroidManifest.xml`, analizado bajo `<application>`)

| Tipo | Declarados | Exportados (`true` explícito; ninguno depende del valor implícito por defecto) |
|------|-----------:|-------------------------------------------------------------------------------:|
| `activity` | 828 | 22 |
| `activity-alias` | 33 | 29 (14 son aliases de launcher `AppIcon01..14` deshabilitados) |
| `service` | 61 | 16 |
| `receiver` | 68 | 19 |
| `provider` | 19 | 11 |
| Total | 1009 | 97 |

De las 97 entradas exportadas: 20 son `enabled="false"` (14 aliases de icono, service de car-app, receiver ADM, activity y provider de migración iOS, dos receivers de intent de UPI India); 24 llevan `permission` / `readPermission`; 6 están protegidas por un permiso `signature` definido por WhatsApp; 56 están habilitadas sin permiso en el manifest. Cualquier verificación más allá del manifest está en el código (sección 9).

Permisos personalizados (found): `REGISTRATION`, `IDENTITY_VERIFICATION`, `MIGRATION_CONTENT_PROVIDER`, `BROADCAST`, `MAPS_RECEIVE`, `RECEIVE_ADM_MESSAGE`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` son `protectionLevel="signature"`. `com.whatsapp.sticker.READ` no tiene `protectionLevel` (normal por defecto).

### 2.2 Puntos de entrada que se ejecutan sin cuenta

| Componente | Exportado | Filtro | Por qué es alcanzable antes del registro |
|------------|-----------|--------|------------------------------------------|
| `com.whatsapp.Main` | sí | `MAIN` / `LAUNCHER`, `MULTIWINDOW_LAUNCHER` | único launcher; enruta según el estado de registro (sección 3) |
| `com.whatsapp.home.ui.HomeActivity` + aliases `AcceptInviteLinkActivityDeepLink`, `EventDeepLink`, `HomeActivity` | sí | `chat.whatsapp.com`, `call.whatsapp.com`, `event.whatsapp.com`, `whatsapp://chat`, `call`, `event`, NFC `application/com.whatsapp.chat`, `.join` | no se encontró verificación de registro en `HomeActivity` en sí (inferred: una clase base redirige, no resuelto) |
| `DeepLinkActivity` mediante 4 aliases | alias sí, destino no | ver sección 4 | punto de entrada de enlaces |
| `com.whatsapp.deeplink.ui.TpalOAuthRedirectActivity` | sí | `www.whatsapp.com/oauth_account_linking/login_redirect`, `/oauth_account_linking_mobile/login_redirect`, `whatsapp://third_party_oauth` | receptor de redirección OAuth, `noHistory` |
| `com.whatsapp.cuif.ConsentActivity` | sí | `whatsapp://consent` | lee los extras `flow_name`, `source`, `extra_params`, `device_id`, `app_id`; comportamiento previo al registro no resuelto |
| `com.whatsapp.Conversation` | sí | `sms:` / `smsto:` `VIEW` / `SENDTO` | punto de entrada del manejador de SMS del sistema |
| `com.whatsapp.accountsync.ProfileActivity`, `CallContactLandingActivity` | sí | `content://com.android.contacts` MIME `vnd.com.whatsapp.profile`, `.voip.call`, `.video.call` | integración con la app de contactos; `CallContactLandingActivity` requiere `CALL_PHONE` |
| `com.whatsapp.registration.ui.RegistrationCompletedReceiver` | sí, signature `REGISTRATION` | `com.whatsapp.SMBRegistrationCompleted` | señal de la app hermana |
| `com.whatsapp.registration.directmigration.MigrationProviderOrderedBroadcastReceiver`, `MigrationRequesterBroadcastReceiver` | sí, signature `REGISTRATION` | acciones `initialMigrationInfoAction`, `recoveryTokenAction`, `setMigrationStateOnProviderSide`, `providerIsLoggedOutAction`, `providerAppMigrationSpaceNeededAction` | migración consumer / app hermana SMB durante el registro |
| `MigrationContentProvider`, `DirectMigrationContentProvider` | sí, `readPermission` `MIGRATION_CONTENT_PROVIDER` (signature) | authorities `com.whatsapp.provider.MigrationContentProvider`, `.DirectMigrationContentProvider` | misma migración |
| `com.whatsapp.registration.app.verifyphone.SMSRetrieverAppInactiveReceiver` | sí, permiso GMS `SEND` | `SMS_RETRIEVED` | resultado de SMS Retriever cuando la app está inactiva |
| `com.whatsapp.registration.core.accounttransfer.AccountTransferReceiver` | sí, sin permiso | `com.google.android.gms.auth.START_ACCOUNT_EXPORT` | el código exige un keyguard seguro y una verificación de feature antes de actuar (found) |
| `com.whatsapp.phoneid.PhoneIdRequestReceiver` | sí, sin permiso | `com.facebook.GET_PHONE_ID` | devuelve el phone id a un llamador de confianza (sección 9.1) |
| `com.whatsapp.otpmessage.otp.OtpRequestedReceiver`, `OtpIdentityHashRequestedReceiver` | sí, sin permiso | `com.whatsapp.otp.OTP_REQUESTED`, `ID_HASH_REQUESTED` | handshake de autocompletado OTP para otras apps (sección 9.3) |

### 2.3 Otras entradas exportadas (no relacionadas con el registro, listadas por completitud)

| Grupo | Componentes | Control |
|-------|-------------|---------|
| Contenido de terceros | `Conversation` (manejador de `sms:`), `ExternalShareAlias` (`SEND`, `SEND_MULTIPLE`, `*/*`), `ContactPicker` (`PICK`, `CREATE_SHORTCUT`), `SetAsProfilePhoto` (`ATTACH_DATA`) | ninguno en el manifest |
| Stickers | `SendStickerCommandActivity`, `AddThirdPartyStickerPackActivity` (+ alias), `StickerCommandProvider`, `WhitelistPackQueryContentProvider` | ninguno en el manifest |
| IPC de la familia Meta | `FamilyAppsCredentialsProvider`, `FamilyAppsUserValuesProvider`, `WaAccountsCenterService` (`com.whatsapp.wfl.OPERATION`), `QuickSendsContactsProvider`, `OrbitSsoProvider`, `OrbitMessagesProvider`, `OrbitCompanionLinkActivity`, `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | verificaciones del llamador en el código (sección 9) |
| Dispositivos companion | `WearOsListenerService`, `GarminBindingServiceShim`, `IQGarminBindingService`, `TetheredService`, `WhatsAppCarAppService` (deshabilitado) | ninguno en el manifest |
| Integración con Google | `BackupNowService`, `BackupStateService`, `OsMigrationAppDataService` (`BACKUP`), `DeferredRestoreBroadcastReceiver` (`BACKUP`), `WakeUpService` (permiso de exposure notification) | parcial |

También exportados: hooks de ajustes (`SettingsNotifications`, `SettingsDataUsageActivity`, configure del widget `AppAuthenticationActivity`), aterrizaje de llamadas (`SystemDialerCallLandingActivity`, `VoiceMessagingActivity`), receivers de librerías (`WidgetProvider`, `BootReceiver`, `AppUpdatedReceiver`, `ExternalMediaStateReceiver`, `WAFbnsPreloadReceiver`, `FirebaseInstanceIdReceiver`, entradas de work-manager y profile-install protegidas por `BIND_JOB_SERVICE` / `DUMP`), entradas de Pixel (`com.google.permission.besties.API`) y las entradas deshabilitadas de UPI India y migración iOS. `IdentityVerificationActivity` (NFC `application/com.whatsapp.identity.ui`) requiere el permiso signature `IDENTITY_VERIFICATION`.

### 2.4 Componentes previos al registro no exportados (found)

Las 806 activities no exportadas incluyen todas las pantallas de registro (sección 3.2), `LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity`, `BanAppealActivity`, `WfacBanActivity`, `PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`. Tres alarm receivers no exportados gestionan los recordatorios de registro: `RegRetryVerificationReceiver` (`com.whatsapp.alarm.REGISTRATION_RETRY`, `SMS_RECEIVED_WHILE_INACTIVE`), `OnboardingIncompleteReceiver` (`ONBOARDING_INCOMPLETE`), `EnterPhoneNumberNotificationReceiver` (`ENTER_PHONE_NUMBER`). Providers no exportados: `FileProvider`, `SecureFileProvider`, `MediaProvider`, `AccountSwitchingContentProvider`, `RestartAppContentProvider`, `InstrumentationProvider` (todos con `grantUriPermissions` donde está declarado).

### 2.5 Flags de la aplicación y política de red (found)

| Elemento | Valor |
|----------|-------|
| `debuggable` | `false` |
| `allowBackup` | `true`, pero `fullBackupContent` y `dataExtractionRules` (cloud-backup y device-transfer) excluyen todos los dominios; la entrada de transferencia multiplataforma para iOS solo lleva `bundleId` / `teamId` |
| `networkSecurityConfig` base | `cleartextTrafficPermitted="true"`; trust anchors `system` y `user` (`overridePins="true"` para CAs de usuario) |
| Cleartext denegado | `whatsapp.com`, `whatsapp.net`, `wa.me`, `wl.co` (22 pins SHA-256, sin expiración), `facebook.com`, `instagram.com`, `jiomart.com`, `hatch-api.meta.ai` |
| Alcance de los pins | el conjunto de pins está en el domain-config de `whatsapp.com` / `whatsapp.net` / `wa.me` / `wl.co`; hereda los trust anchors base, por lo que los pins no se aplican a CAs instaladas por el usuario (comportamiento de plataforma de `overridePins`) |
| Hosts fuera de cualquier domain-config | `gstatic.com` (clave reCAPTCHA) cae bajo la config base (cleartext permitido; el código usa `https://`) |

---

## 3. Pantallas previas al registro y enrutamiento por estado

### 3.1 Enrutamiento de `Main` por estado de registro (found, smali de `Main.A5W`)

`Main` lee el estado de registro (`C0Gk.A02()`) y el objeto de cuenta propia almacenado. Los log tags son anclas estables.

| Estado | Log tag | Destino |
|-------:|---------|---------|
| 2 | `main/me/regname`, `main/no-me/regname` | paso de registro de entrada de nombre (`RegisterName`) |
| 21 | `main/me/wfac ban` | pantalla de baneo WFAC mediante `HBC.A00` (`WfacBanActivity`) |
| 24, 38 | `main/me/backup otp` | paso de OTP de backup / verificación |
| 41 | `main/me/consent age ban` | pantalla de consentimiento de edad |
| 45 | `main/me/paa onboarding`, `main/no-me/paa onboarding` | onboarding de cuenta dependiente / gestionada |
| 50 | `main/me/logged out, going to PrimaryLoginBackActivity` | pantalla de login-back |
| 51 | `main/me/pending login-back verification` | verificación de login-back (extra `login_back_verification`) |
| 56 | `main/me/username`, `main/no-me/username` | paso de username |
| cualquiera | `main/no-me/first-factor password` | rama de contraseña de primer factor (sin objeto de cuenta propia) |
| cualquiera | `main/invalid/registration state=` | log de estado inválido |

El mismo método construye intents (found) para `VerifyPhoneNumber`, `DeviceConfirmationRegistrationActivity`, `ExportMigrationDataExportedActivity`, `BanAppealActivity` (extra `launch_source`), `DeleteAccountConfirmation` y la entrada por defecto `RegisterPhone`. Una preferencia `logged_out_phone_fallback_pending` reanuda en `RegisterPhone` (`main/me/logged-out phone fallback resume`). Se verifica un token IDV generado (`minted_idv_token`, `minted_idvtoken_expiry_time_secs`), y uno expirado o vacío reinicia el flujo de remediación. Qué estados numéricos corresponden a qué paso del lado del servidor es inferred a partir de los nombres de los tags.

### 3.2 Pantallas de registro (found, todas no exportadas)

| Grupo | Activities (`com.whatsapp.registration.app.*` salvo indicación) |
|-------|------------------------------------------------------------------|
| Entrada | `EULA` (tag `eula_screen` / `eula_with_language_selector`), `phonenumberentry.RegisterPhone`, `RegisterAsDependentActivity`, `RegTabletIntroActivity`, `RegTabletChooseOptionActivity` |
| Permisos | `RegPermissionsExplainerActivity`, `RegNotificationPermissionPrimerActivity` |
| Verificación | `verifyphone.VerifyPhoneNumber`, `sendsmstowa.SendSmsToWa`, `ManualSmsRequest`, `flashcall.PrimaryFlashCallEducationScreen`, `email.RegisterEmail`, `email.VerifyEmail`, `email.EmailEducationScreen`, `email.UnverifiedEmailSetupRegUpsellActivity`, `email.ConfirmEmailSetupRegUpsellActivity`, `backuptoken.BackupTokenEducationScreen`, `VerifyTwoFactorAuth` |
| Defensa de la cuenta | `accountdefence.DeviceConfirmationRegistrationActivity`, `accountdefence.ui.OldDeviceSecureAccountActivity`, `OldDeviceSecureAccount2FaActivity`, `OldDeviceMoveAccountNoticeActivity` |
| Bloqueos | `parole.CustomRegistrationBlockActivity`, `downgrade.DowngradeFrictionActivity`, `com.whatsapp.userban.ui.BanAppealActivity` |
| Migración | `directmigration.RestoreFromConsumerDatabaseActivity`, `MigrationStartTransferActivity`, `RequestPermissionFromSisterAppActivity`, `com.whatsapp.migration.transfer.ui.*` |
| Nombre / cambio de número | `RegisterName`, `phonenumberentry.ChangeNumber*` |
| Modo companion | `com.whatsapp.companionmode.registration.ui.RegisterAsCompanionActivity`, `RegisterAsCompanionEnterNumberActivity`, `RegisterAsCompanionLinkCodeActivity`, `CompanionBootstrapActivity`, `CompanionPostLogoutActivity` |
| Sin sesión | `logout.ui.PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`, `loginfailure.LogoutMessageActivity` |
| Soporte | `inappsupport.ui.app.LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity` |

### 3.3 Selectores de idioma y país (found)

| Elemento | Detalle |
|----------|---------|
| Idioma | `LanguageSelectorBottomSheet` abierto desde `EULA` (evento de embudo `language_selected`; métricas `language_selector_clicked_count`, `language_selector_time_spent` en `K49`); el `FullScreenLanguageSelectorActivity` del lado de ajustes no está exportado |
| Nombres de países | 63 tablas offline `assets/country_names_<lang>.tsv` (`ISO code<TAB>name`); no se encontró consulta de red para el selector |
| Prellenado del número | `RegisterPhone` usa los hints de número de teléfono de Google (`RegisterPhone/launchGooglePNHints`) y una vía SIM "what's my number" que requiere un permiso de teléfono; extras de EULA `RegisterPhone.phone_number`, `country_code`, `auto_submit_after_prefill`, `one_click_from_eula` |
| Enlaces legales en `EULA` | `https://www.whatsapp.com/legal/terms-of-service` o `/terms`, `privacy-policy` o `privacy-policies` (variante según config) |

---

## 4. Deep links y enlaces web

### 4.1 Aliases de entrada (found)

| Alias | Destino | Filtros |
|-------|---------|---------|
| `TextAndDirectChatDeepLink` | `DeepLinkActivity` | `http(s)://api.whatsapp.com`, `wa.me`; `https://[www.]whatsapp.com` rutas `/channel`, `/channel_status`, `/updates`, `/aimediainput`, `/aivoice`, `/dl`, `/privacy/disclosure`, `/wamo/status/link-{instagram,facebook}-in-house-ad`; esquemas `whatsapp`, `whatsapp-smb`, `whatsapp-consumer`, `whatsapp-sheet` (listas de hosts, más de 100 hosts) |
| `VerifyOtpDeepLink` | `DeepLinkActivity` | `http(s)://b.whatsapp.com`, `http(s)://v.whatsapp.com` |
| `FoaDeeplinkActivityAliasUniversalLink`, `FoaDeeplinkActivityAliasAppScheme` | `DeepLinkActivity` | sin filtro en este manifest (declarados para la librería de deep links de la familia Meta) |
| `AcceptInviteLinkActivityDeepLink` | `HomeActivity` | `chat.whatsapp.com` |

`DeepLinkActivity` en sí no está exportada; toda ruta externa pasa por un alias. Todos los filtros con `autoVerify="true"` cubren solo hosts https. Varios filtros sobre `whatsapp`, `whatsapp-consumer`, `whatsapp-smb` llevan tanto `VIEW` como la acción personalizada `com.whatsapp.DEEP_LINK_REDIRECT`, por lo que el alias responde a un intent explícito con esa acción desde cualquier app (found: forma del filtro).

### 4.2 Enlaces que gestionan el estado previo al registro (found)

| Enlace | Ancla del parser | Comportamiento |
|--------|------------------|----------------|
| `https://[www.]whatsapp.com/dl?wsu=<6 digits>` | `IJB.A01`: ruta `dl`, query `wsu` que cumple `\d{6}`, log `DeepLinkHelper/parseUri/web signup uri`, código **193** | traspaso de sign-up web; el valor solo se valida con regex en el cliente |
| `whatsapp://s/signup` (un solo segmento de ruta `signup`) | `IJB.A01` código **216**, condicionado por ab-props **25005** o **25801**; el handler `handleInAppSignupDeepLink` requiere esquema `whatsapp` y query `s` | sign-up dentro de la app; registra mediante `ApiSignupFlowLogger` con `signup_id` (el emparejamiento del host `s` es inferred del manifest) |
| `https://v.whatsapp.com/<code>`, `https://b.whatsapp.com/<code>` (último segmento de ruta) y `whatsapp://r?c=<code>` | rama de registro de `DeepLinkActivity`, log `DeepLinkActivity/Registration deeplink/registration state:` | enlace de OTP por email. El estado 1 abre `RegisterPhone` con el extra `tapped_sms_link`; el estado 2 abre `VerifyEmail` con `email_otp`, `entrypoint`, `session_id`, `challenge_flow=false` y reporta `email_otp_deeplink_redirect_to_register_name`; otros estados redirigen a ajustes (`settings_verification_email_address_verified`, inferred). El código se reenvía como extra; la verificación es del lado del servidor (unknown) |
| `whatsapp://code-linking?auth=<nonce>` | código **77**, handler `maybeStartCodeLinkingFlow`, ab-prop **4560** (`ENABLE_CODE_LINKING_DEEP_LINK_CODE`), pref `adl_deep_link_nonce` con una ventana de 300000 (unidad inferred como ms) | flujo de código de dispositivo vinculado; se omite cuando el flag está apagado o el nonce es más antiguo que la ventana |
| `whatsapp://help/<segment>` | código **62**; la rama offline registra `DeepLinkActivity/help/no-connectivity` | artículo de ayuda |
| `whatsapp://support` | código **30** (extraído del parser; el handler registra `about/no-connectivity`) | pantalla de soporte / acerca de, requiere conectividad |

### 4.3 La compuerta previa al registro

| Ancla | Hallazgo | Nivel |
|-------|----------|-------|
| `DeepLinkActivity/deeplink not allowed before registration/` y motivo `not_allowed_before_registration` | presente; el enum de motivos asigna el valor 0 a ese string; no se aisló el productor del motivo 0 para enlaces ordinarios | found (strings), unknown (productor) |
| Handlers por código | cada handler verifica por sí mismo el estado de registro (llamadas `C0Gk.A0C()` / `A02()` en los cuerpos del switch) | found |
| Allowlist de códigos sin sesión | no re-resuelta: `C02T` es un serial executor en este build y `C02U` es una clase compartida de constantes enteras, por lo que los nombres de clase anteriores no se corresponden | unknown |
| Resultado `JXK` (`code`, `source`, motivo) construido por `IJB`, `IJC`, `IJD`, `IJE` | salida del parser consumida por `DeepLinkActivity.A0w` | found |

Resolver contenido (un chat, un canal, un directorio) sigue necesitando una cuenta: los handlers de invitación de grupo y de `wa.me/<phone>` usan la sesión autenticada (inferred a partir de los nombres de los handlers; no trazado de extremo a extremo aquí).

---

## 5. Hosts y endpoints contactados sin cuenta

### 5.1 HTTP de registro (found)

16 rutas, clave XOR 18 en `AbstractC45307Jps`, todas re-decodificadas en 2.26.41.6: `/v2/exist`, `/v2/code`, `/v2/register`, `/v2/security`, `/v2/challenge`, `/v2/passkey_auth`, `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop`, `/v2/device_logout_send`, `/v2/device_logout_fetch`, `/v2/wfs`. Otras dos constantes se decodifican como `ENC` y `H` (uso unknown). Las listas de campos del primer grupo están en [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) sección 3.1. El host base `v.whatsapp.net` es el nombre en la tabla compilada (5.4); el código que une host y ruta está en los stacks wamsys / Kotlin y no se leyó aquí (inferred).

El selector `K49.A0b` elige el stack Kotlin (`KotlinRegistrationBridge`) o el stack nativo `wamsys`; el stack nativo debe hacer bootstrap primero (`ensureWamsysForRegBootstrapped`, error `FAIL_TO_INITIALIZE_WAMSYS`).

### 5.2 Otros endpoints HTTPS (literal found, autenticación según se indica)

| Host / URL | Método | Autenticación en el código | Llamador | ¿Sin cuenta? |
|------------|--------|----------------------------|----------|--------------|
| `https://www.whatsapp.com/contact/noclient/verification/` | multipart POST | ninguna | `C47328KmN` case 0 (formulario de soporte) | sí |
| `https://graph.<pref_graphql_domain>/graphql` (por defecto `graph.whatsapp.com`) | POST JSON | client token de la app compilado en el body `access_token` | `AbstractC40195HfH` y subclases | sí (estado de baneo / apelación) |
| `https://crashlogs.whatsapp.net/wa_clb_data`, `/wa_fls_upload_check`, `/wa_profilo_data`, `/whatson_logs_upload` | POST | token de la app compilado (la subida de logs añade `access_token`, `type`, `from_jid`, `ticket_id`, `build_id`) | `C10V`, `C05640An`, `ExceptionsUploadService`, `ProfiloUploadService`, `CM8` | se ejecuta sin login; contenido de `from_jid` sin sesión unknown |
| `https://acs.whatsapp.com/graphql` | POST | token ACS o config OHAI (sin JID) | `C31991Nz`, `R5t` | sí (peticiones de-identified) |
| `https://static.whatsapp.net/wa/static/{downloadable,network_resource,payments/*}`, `/sticker?...`, `/payments/background` | GET | ninguna | cargadores de assets de la UI | sí |
| `https://mmg.whatsapp.net/proxygen/health`, base `https://mmg.whatsapp.net` (config 22436) | GET | ninguna | media / health | sí |
| `https://www.gstatic.com/recaptcha/verify_key/orcas/prod/android/verify_key.txt` | GET | ninguna | `C44464JbH` (usado por `RequestCodeRepository`, `VerifyCodeRepository`, `VerifyPhoneNumber`) | sí (captcha de registro) |
| `https://www.whatsapp.com/compliance/xfac/mint` | POST form | ninguna vista | `CommonRemediationApi` (remediación de edad, `minted_idv_token`) | alcanzable antes del registro: unknown |
| `https://www.whatsapp.com/v1/auth/canonical/token/` | POST form `nonce`, `user_id`, `device_id`, `client_pub_key` | ninguna | `CanonicalUserCompanionDeviceManager` | ruta de companion / cuenta vinculada, no estrictamente previa al registro |
| `https://api.whatsapp.net/support/add_bug_attachment` | multipart POST | `Authorization: Bearer <token>` | `PostBugAttachmentUploader` (reporte de bug in-app) | no (ligado a token) |
| `https://graph.whatsapp.net/v2.2/maps_configs?...&access_token=` (por defecto `graph.facebook.com`) | GET | token de la app en la URL | config de mapas `N6n` | el disparador no es previo al registro (inferred) |
| `https://api.whatsapp.net/calendar/integrations/` | request | sesión | feature de calendario | no |

Tokens compilados: existen dos formas estilo Facebook, `WA|<app_id>|<secret>` en el default del cliente Graph y `<app_id>|<secret>` en el uploader de logs. Los valores no se reproducen aquí. Identifican la app, no a un usuario.

### 5.3 Bootstrap de DNS y conectividad (found)

| Elemento | Detalle |
|----------|---------|
| Tabla compilada `AbstractC47101wK` | host a lista IPv4 / IPv6 para 18 nombres: `e1..e16`, `g`, `v` bajo `.whatsapp.net` (cada uno con un gemelo con punto final); no necesita red |
| `C36881dC` (DnsCache) | orden de uso: resolver primario, resolver DNS MNS (`DnsCache/resolveViaMnsDns`, el string `v.whatsapp.net` se prueba en esa rama), resolver secundario, tabla hardcodeada; las búsquedas hardcodeadas fallan con `no hardcoded ips found for <host>` cuando la tabla no tiene entrada y se omiten con `hardcoded dns resolver disabled` cuando el bit de opción está apagado |
| Host de chat | la entrada `g.whatsapp.net` se lee directamente (`C36881dC.A01`) |

El formato de wire del resolver MNS vive en código nativo: unknown.

### 5.4 Rutas REST que no existen (negativo found)

No se encontró ninguna descarga REST no autenticada para gating o config (`/gk`, `/props`, `/config`). La config de experimentos previa al login sí llega por HTTP de registro: `/v2/reg_onboard_abprop` (`K49.checkPreChatdABProps`) envía `ab_hash` desde la pref `pref_pre_chatd_ab_hash`, `ab_exposure`/`ab_key` desde `pref_pre_chatd_ab_key`, más los campos de dispositivo de la sección 7.

---

## 6. Formulario de soporte sin sesión (found)

`LoggedOutContactFormActivity` (no exportada) es el único flujo de soporte completamente sin cuenta en este build.

| Extra del intent (prefijo `com.whatsapp.inappsupport.ui.app.LoggedOutContactFormActivity.`) | Uso |
|------|-----|
| `PhoneNumber`, `CountryCode` | número prellenado; string vacío si no hay |
| `From` | etiqueta del punto de entrada |
| `ServerStatus` | string de estado pasado por el llamador (inferred: estado del servidor de registro) |
| `IsRegistrationVerification` | booleano; en caso de éxito se hace una llamada posterior (destino sin resolver) |
| `SupportUserContext` (`K8W`) | punto de entrada e ids de CMS (`Entry point`, `Cms ids`) |

Campos del formulario: email (chips de sugerencia `@gmail.com`, `@hotmail.com`, `@icloud.com`, `@outlook.com`, `@yahoo.com`), descripción, hasta 3 capturas de pantalla elegidas desde `MediaStore`.

Envío (`C47328KmN` case 0, tag `logged_out_contact_form`, argumento final 20 de significado sin resolver):

| Parte | Nombre | Contenido |
|-------|--------|-----------|
| field | `email` | email escrito |
| field | `message` | descripción |
| field | `platform` | literal `ANDROID` |
| field | `phone_number` | número escrito |
| field | `debug_info` | texto construido por `C10V.A08` (sección 7.3) |
| file | `log_data` | `logs.tar.gz` del log del cliente (rotado y comprimido antes) |
| files | `attachment_<n>` | capturas recodificadas a JPEG calidad 80, límite de 2048 px, conservadas solo si pesan 10 MiB o menos |
| extra | `skip_saga_copy=true`, `saga_copy=true`, `pn` | `pn` = código de país + número cuando ambos no están vacíos |

Resultado: el estado HTTP va a un callback de resultado (`C46422KQg`); un fallo aparece como `Server error: <status>` o `Network error`; el éxito abre `LoggedOutContactSuccessActivity` (extra `...Email`). No se leyó el mapeo exacto de estado a éxito. La llamada es un POST HTTPS simple a través del cliente HTTP de la app; no es una llamada GraphQL. Se genera un UUID `anid` aleatorio (7.1) por cada envío.

---

## 7. Identificadores enviados antes del login

### 7.1 Tabla de identificadores

| Identificador | Dónde | Origen | Notas | Nivel |
|---------------|-------|--------|-------|-------|
| `fdid` | `/v2/pre_pn_client_log`, peticiones de registro | `C38141gV.Ax2()`: `UUID.randomUUID()` aleatorio guardado como `phoneid_id` + `phoneid_timestamp` en prefs | persiste entre intentos de registro; el mismo id lo devuelve `PhoneIdRequestReceiver` | found |
| `fid` | peticiones de registro | `C47381wu.Ax2()`: prefs `phoneyid_id` + `phoneyid_timestamp`, enviado como `<id>|<timestamp>` solo cuando existe | id familiar secundario; productor del valor no trazado | found (uso inferred) |
| `anid` | formulario de soporte | `C11J.A01()`: `UUID.randomUUID()` por llamada, también registrado como evento WAM | id aleatorio por envío | found |
| `advertising_id` / `android_advertising_id` | `/v2/exist`, `/v2/code`, `/v2/register`; log del embudo | advertising id de Google cuando está disponible | excluido del string de debug log del funnel logger | found |
| `authkey`, `e_ident`, `e_keytype`, `e_regid`, `e_skey_id`, `e_skey_val`, `e_skey_sig`, `e_pq_last_resort_{id,val,sig}` | peticiones de registro | `C45446JsB`: clave estática Noise del cliente y paquete de claves Signal | material público | found |
| `gpia` | peticiones de registro | token estándar de Play Integrity, condicionado por flag | ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) | found |
| `ab_key`, `ab_hash`, `ab_exposure` | `/v2/exist`, `/v2/pre_pn_client_log`, `/v2/reg_onboard_abprop` | prefs `pref_pre_chatd_ab_key` / `pref_pre_chatd_ab_hash` | bucket de experimento | found |
| `device_country` | log del embudo | `TelephonyManager.getSimCountryIso()` en mayúsculas, `ZZ` cuando no hay | | found |
| `access_token` (app) | Graph, subida de logs | constante compilada | identidad de la app, no del usuario | found |
| `request_token` / `token` | estado de baneo / apelación | pref `wfac_ban_status_token` (estado) y el token de apelación almacenado | opaco, emitido por el servidor al momento del baneo ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md)) | found |
| `from_jid` | subida de logs | JID de la cuenta cuando existe | contenido sin sesión unknown | found (campo), unknown (valor) |
| `registration_trace_id`, `request_id`, `nonce_encryption_key` | mutation de recuperación de cuenta | `AccountRecoveryManager` (sección 8.2) | | found |

### 7.2 Atributos del dispositivo en las peticiones de registro (found, helpers de `K49` `A0O`, `A0Q`, `A0R`, `A0U`, `A0W`, `A0X`)

`network_radio_type`, `simnum` (`0` / `1`), `hasinrc` (archivo `rc2` presente), `pid` (id de proceso), `device_ram`, `sim_type`, `airplane_mode_type`, `cellular_strength` (nivel de señal, `5` por defecto), `roaming_type`, `preloads_app_manager_id`, `preloads_attribution`, `entrypoint` (`create_paa` o `suma`), `tos_version` (`5`), `old_phone_number` (flujo de cambio de número). Claves de métricas de telemetría en la misma clase (found, uso en peticiones no confirmado): `network_operator_name`, `sim_operator_name`, `sim_state`, `read_phone_permission_granted`, `mistyped`, `c2dm_reg_id` (leído de prefs).

### 7.3 Contenido del log del embudo (found, `PrePnBaseFunnelLogger$sendPrePNFunnelLog$1`)

Antes de que exista un número el cliente envía: `current_screen`, `previous_screen` (pref `pref_previous_screen`, por defecto `unknown`), `action_taken`, `event_name`, `access_funnel_type=wa`, `app_campaign_download_source`, `is_add_account_flow`, `android_advertising_id`, `ab_key`, `device_country`, `fdid`, los atributos de dispositivo anteriores y `entrypoint`. En flujos de agregar cuenta o de fallback sin sesión también envía `primary_logout_session_id` y `number_of_accounts`. El envío se omite cuando falla el bootstrap de wamsys.

### 7.4 `debug_info` del formulario de soporte (found, `C10V.A08`, el argumento JID es `null` en esta llamada)

Etiquetas escritas en el texto: `useragent`, `Socket Conn`, `Connection`, `Server`, `Datacenter`, `Sim`, `Free Space Built-In` / `Removable`, `Network metered` / `restricted`, `Data roaming`, `Tel roaming`, `Diagnostic Codes`, `ABprops hash state`, `Screen reader`, `Fingerprint eligible`, campos de estado de backup, `Is Companion`, `Number of Accounts`, `Mobile Build Id`, `wfl_state`, `isMetaVerified`, `Mistyped` / `Mistyped Last6` / `L Distance` (comparación del número escrito con el número de la SIM), más identificadores de la última llamada cuando existe historial de llamadas. La etiqueta `entity id` solo se escribe cuando se pasa un JID, lo cual no ocurre aquí.

---

## 8. Llamadas Graph y MEX sin sesión de usuario

### 8.1 Peticiones Graph con token de la app (found)

La clase base `AbstractC40195HfH.CND` construye `https://graph.<A0f()>/graphql` (`A0f()` = pref `pref_graphql_domain`, por defecto `whatsapp.com`; las subclases `GEV`, `GEX`, `GET`, `GEW`, `GEU` y el switch de la familia de cuentas Meta `C45F` cambian a `facebook.com` / `instagram.com`). Body JSON: variables de la operación, `access_token` (token compilado cuando la subclase no pasa ninguno), `doc_id`, `lang`, `Content-Type`. El header `X-FB-Request-Analytics-Tags` se añade cuando falta.

| Clase | doc_id | Variables | Propósito |
|-------|-------:|-----------|-----------|
| `C37604GYf` | **4276154569100535** | `app_id` (`dev.app.id`), `request_token` | sondeo de estado de baneo WFAC (`WfacBanRepository/fetchBanStatus`, token de la pref `wfac_ban_status_token`) |
| `C37409GLo` | **27883644401256929** o **4276154569100535** (booleano) | igual | estado de baneo mediante `HG2.A01` |
| `C37414GLt` | **38509456535312323** o **5473316762755318** (booleano) | `app_id`, `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}`; plaintext `{token, debug_info, description}`, contexto `WA_INAPP_BAN_APPEALS` | envío de apelación de baneo (`C40191HfD`); detalles en [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) sección 10 |
| `C37408GLn` | **5803265299734043** | `app_id`, `client_pub_key` | propósito unknown (envía una clave pública del cliente); llamador no trazado |
| `C37601GYc`, `GYd`, `GYe` | `GYd` **25453433540999208**, `GYe` **25974020015520396** (`GYc` no lleva id en su propia clase) | `caller_name` `fx_waffle_contextual_pause_account_match`, `wa_waffle_certs`, `fx_waffle_foa_unpause` | helpers de vinculación de cuentas Meta |
| `C37605GYg`, `GYh`, `GYi` | **26573478745654327**, **26742313962085910**, **27503298369362501**, **28331348373116386**, **25840634418966704** | header `IG-Set-Waffle-Graphql-Access-Token`, clave `ACCESS_TOKEN` | vinculación de cuentas Facebook / Instagram; se requiere un token de cuenta vinculada (inferred a partir de los nombres del header y la clave) |
| `C37413GLs` | **7236799486398397** | `batches`, `device_model`, `device_os`, `device_os_version`, `event_time`, `is_employee`, `primary_locale` | lotes de eventos del cliente (inferred a partir de los nombres de variables) |

El doc_id 6960707423955525 (un id de mutation de apelación legado reportado para builds antiguos) no aparece en 2.26.41.6. Los nombres de operación de las peticiones de apelación y estado no los llevan estas clases (unknown).

Diferencia con [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) sección 10: para `C37414GLt`, `C37409GLo` y `C37604GYf` el host es `graph.<pref_graphql_domain>` (por defecto `graph.whatsapp.com`); solo las subclases listadas arriba lo sobrescriben a `facebook.com`.

### 8.2 Operaciones MEX con un call site durante el registro o sin sesión (found, esquema `whatsapp-android-mex`)

doc_ids de `assets/whatsapp-android-mex_client_persist_ids.json` (y de los archivos `www` / `wamo` donde se indica).

| Operación | doc_id | Call site |
|-----------|-------:|-----------|
| `GetAutoConfConfidenceChallenge` | 25578301865133112 | `C40175Het`, `C40196HfI` (ping de confianza de autoconf) |
| `ValidateVerifierConfidence` | 25879669248324812 | `C40196HfI`, `C40197HfJ` |
| `FetchReachoutTimelockQuery` | 25627902213558773 | `RunnableC23952AUh` |
| `RemoveAccountReachoutTimelock` | 25040013452293167 | no trazado |
| `UserCountryCodeGet` | 25292528387076991 | `MexUserCountryCodeRepository` |
| `MobileConfigFetchQuery` | 29248978061376279 | no trazado |
| `SubmitAge`, `GetAgeExperience`, `SetAgeExperienceMutation` | 26049558371296621, 26567868986241476, 26051006311231325 | flujos de edad |
| `TosSetResult` | 25225843213776555 | aceptación de términos |
| `GetWaOldResponse` | 25784374561179853 | verificación mediante teléfono antiguo |
| `WWWTriggerAcountRecovery` | 24896267680055094 | `AccountRecoveryManager` (variables `nonce_encryption_key`, `use_case`, `registration_trace_id`, `request_id`) |
| `WWWCreateUser`, `WWWDeleteUser`, `WWWGetCertificates` | 8548056818544135, 7989555047767245, 25094190163544446 | vinculación de cuentas |
| `OhaiKeyConfigQuery` | 25069818679280758 | `N5I` (bootstrap ACS / OHAI) |
| `CreateEnforcementAppeal` | 26933630359642347 | cliente de enforcement de newsletters |
| `NewsletterCreateReportAppeal` (mex), `CreateGroupSuspensionAppealMutation` (www), `WamoReportPromoAppealV2Mutation` (wamo) | 27792557363683798, 25646047815072526, 26867425009592691 | operaciones de apelación (ligadas a la cuenta; presentes en assets) |

MEX se envía como un IQ `xmlns="w:mex"` con `<query query_id=...>` (`C19370nI`) por la conexión de chat (`WAChatdGraphQLClient`). Si estas operaciones se ejecutan en una sesión previa a la cuenta no está establecido: ver 8.3.

### 8.3 Conexión de chat sin JID (found)

`ConnectionThread.connect` (`HandlerThreadC12340b0`) lee el JID propio; cuando es nulo continúa solo si el flag de registro de companion (`C06830Gm.A02()`) es verdadero; de lo contrario lee una segunda fuente de JID (`Ash()`), y si esta también es nula registra `ConnectionThread/connect/ignored/jid null and not in companion reg` y retorna. Por lo tanto, el registro del teléfono primario no usa una conexión de chat con JID nulo (consistente con [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) sección 6.4). El significado de la segunda fuente es inferred (un JID almacenado o de registro pendiente, sin resolver). Qué sesión transporta las llamadas MEX durante el registro de 8.2 es unknown.

### 8.4 Peticiones de-identified (found)

`PandoGraphQLRequest.requireAcsToken()` y `requireOhaiConfig()` los lee `C6GN`; una petición marcada `@deidentified` sin token ACS ni config OHAI lanza una excepción (`Request was marked with @deidentified, but no ... was provided`). Campos de `AcsOhaiConfig`: nombre de proyecto, doc id, `graphQlUrl=https://acs.whatsapp.com/graphql`, surface, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`. Qué operaciones llevan el flag está codificado en los assets `*_pando_flatbuffer_data.bin`: unknown.

---

## 9. Superficies IPC exportadas con verificaciones en el código

Todas las entradas están exportadas sin permiso en el manifest salvo indicación. Esta sección lista los controles encontrados en el código, no un veredicto sobre su solidez.

### 9.1 `PhoneIdRequestReceiver` (`com.facebook.GET_PHONE_ID`)

Un broadcast ordenado. El receiver lee un extra `PendingIntent` `auth` de los extras del resultado y toma `getCreatorPackage()`. Un paquete es de confianza cuando el hash de su certificado de firma está en un allow-set hardcodeado (`AbstractC28130CKz.A04`, SHA-1 de certificados de firma, valores no reproducidos; se usa un segundo set SHA-256 en `CHA.A02`). Un llamador de confianza recibe el phone id y su timestamp como resultado del broadcast (`setResult(-1, id, {timestamp})`); una ruta alterna devuelve el id secundario cuando el flag **3651** lo permite. El flujo de control decompilado alrededor de la variable de confianza es parcial, por lo que la precedencia exacta es inferred.

### 9.2 Providers de la familia de apps (found)

| Componente | Controles encontrados |
|------------|-----------------------|
| `FamilyAppsCredentialsProvider` | `getCallingPackage()`; mapa de handlers por selección; el UID del llamador se resuelve a un certificado y se verifica contra el conjunto de confianza del handler (`C45775Jyk.A01`); elegibilidad del link-manager (`WfalManager.A00`); feature flags; el estado del enlace debe estar en el conjunto elegible del handler; devuelve un cursor de 3 columnas (prueba de autenticación, bundle, TTL) desde las prefs `pref_foa_nta_ipc_bundle_auth_proof`, `pref_foa_nta_ipc_bundle`, `foa_nta_ipc_bundle_ttl`; errores por caché expirada o ausente. Expansión de "NTA" unknown |
| `FamilyAppsUserValuesProvider` | una selección `foa_wo_wa_link_eligibility_values`, lectura de `getCallingPackage()` |
| `WaAccountsCenterService` | acción `com.whatsapp.wfl.OPERATION`; el cuerpo de la clase es un stub en el decompile (verificaciones unknown) |
| `QuickSendsContactsProvider` | pasos de validación de `getCallingPackage()` registrados (`validation_start` / `validation_end`); sirve archivos de foto cifrados `.enc` y columnas de contacto (`obfuscated_chat_id`, `display_name`, `profile_photo_uri`, `photo_key`) |
| `OrbitSsoProvider` (`com.whatsapp.orbit.v2.sso`) | compuerta por feature flag; el paquete llamador debe estar en una allow-list (`AbstractC62035Rsx.A00`, de lo contrario `SecurityException ... is not allowlisted`); una verificación de precondición (`BS3()`) antes de cualquier método; métodos `get_profile` (devuelve `display_name`, `phone_number`, `avatar_uri`, `avatar_mime_type`), `get_accounts`, `get_nonce`, `get_token`; ruta de archivo `avatar` de solo lectura. La allow-list se compara por nombre de paquete en `A01()`; la verificación de certificado, si existe, no está en ese método (unknown). Qué prueba `BS3()` es inferred como estado de login |
| `OrbitMessagesProvider` (`com.whatsapp.orbitmessages`) | los archivos se abren solo con modo `r`, último segmento `media`, valores `media_handle` con prefijo `v1.` descifrados con AES-GCM; verificaciones del llamador no localizadas (unknown) |
| `OrbitCompanionLinkActivity` | lee `getCallingPackage()` y el extra `qr_data`; temporizadores de hold / consentimiento; devuelve solo el resultado (`return_result_only`) mediante `CompanionHelloConfirmationActivity` |
| `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | no analizados |

### 9.3 Handshake OTP (`OtpRequestedReceiver`)

Espera un extra `PendingIntent` `_ci_` (identidad del llamador) y un UUID opcional `request_id` (verificado con regex). Registra el paquete creador contra un valor generado, registra un evento WAM y, cuando el flag **6617** está activo o el paquete está en la lista de la config **7050**, responde con un broadcast `com.whatsapp.otp.OTP_HANDSHAKE_CONFIRMATION` a ese paquete con el `request_id`. Un `PendingIntent` ausente se rechaza (`PendingIntent missing from handshake Intent`). No se encontró verificación de registro en este receiver.

### 9.4 `AccountTransferReceiver`

Actúa solo sobre `com.google.android.gms.auth.START_ACCOUNT_EXPORT`, solo cuando el dispositivo tiene un keyguard seguro y pasa una verificación de capacidad (`AbstractC21360rJ.A01`). La exportación en sí se ejecuta en un executor en segundo plano (`C05X.A02(...).CVx`); contenido unknown.

---

## 10. Vista de baneo y puntos de entrada de apelación

| Entrada | Mecanismo | Evidencia |
|---------|-----------|-----------|
| Arranque en frío en estado WFAC | el estado 21 de `Main` inicia `WfacBanActivity` mediante `HBC.A00` | found (3.1) |
| `BanAppealActivity` | no exportada; iniciada por `Main` (extra `launch_source`) y por el flujo de baneo permanente | found |
| Sondeo de estado de baneo | Graph, `wfac_ban_status_token`, throttle de 5 s en la pref `wfac_last_ban_status_fetch_timestamp_ms` | found ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 2.2) |
| Envío de apelación | Graph con `user_request` cifrado (8.1) | found |
| Respuesta de registro | campos de `/v2/register` `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `custom_block_screen`, `version_upgrade` | found ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) 3.3) |
| Contactar a soporte | `LoggedOutContactFormActivity` (sección 6), flag `IsRegistrationVerification` para errores de registro | found |
| Deep links | `whatsapp://support`, `whatsapp://help`, `v.whatsapp.com` / `b.whatsapp.com` | found (4.2) |

La identidad por usuario de la ruta de apelación es el token opaco emitido por el servidor, no un número de teléfono ni un id de dispositivo (los nombres de campo del token arriba; derivación unknown).

---

## 11. Casos de error y gotchas

| Síntoma | Causa | Notas |
|---------|-------|-------|
| `ConnectionThread/connect/ignored/jid null and not in companion reg` | sin JID y no es registro de companion | normal antes del registro; el registro usa HTTPS |
| `FAIL_TO_INITIALIZE_WAMSYS` | falló el bootstrap del stack nativo (`ensureWamsysForRegBootstrapped`) | se omiten el HTTP de registro y el log del embudo previo al número |
| `DeepLinkActivity/deeplink not allowed before registration/` | código de enlace bloqueado por la compuerta | allowlist no resuelta (4.3) |
| `Request was marked with @deidentified, but no ...` | falta la config ACS / OHAI | petición no enviada |

---

## 12. Distinciones clave

| No confundir | Hecho |
|--------------|-------|
| Exportado vs alcanzable sin cuenta | 97 entradas exportadas; la mayoría no hace nada útil hasta que existe una cuenta registrada; solo las entradas de 2.2 y 4.2 tienen manejo del estado de registro |
| Token de la app vs token de usuario | el `WA|<app_id>|<secret>` compilado identifica a la app; las llamadas de baneo añaden un request token opaco, no una sesión de usuario |
| `fdid` vs advertising id | `fdid` es un UUID generado por la app que sobrevive al re-registro; el advertising id es el valor de Google |
| Formulario de soporte sin sesión vs soporte in-app | el formulario hace POST a `www.whatsapp.com/contact/noclient/verification/` con campos escritos; el soporte in-app usa la sesión (no analizado) |
| HTTP de registro vs conexión de chat | el registro es HTTPS `/v2/*`; una conexión de chat con JID nulo es solo para el registro de companion |

---

## 13. Flujo completo

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

## 14. Desconocidos

| Pregunta | Por qué es desconocido |
|----------|------------------------|
| Qué códigos de enlace se permiten antes del registro | clase de allowlist no re-resuelta; los handlers verifican el estado individualmente, solo cuatro trazados |
| Productor del motivo 0 (`not_allowed_before_registration`) | no aislado en el gran switch de `DeepLinkActivity` |
| Unión de host y ruta para `/v2/*`, constantes `ENC`, `H` | no se leyeron los builders de peticiones de wamsys / Kotlin |
| Qué sesión transporta las operaciones MEX durante el registro | la conexión con JID nulo se rechaza fuera del registro de companion; la fuente `Ash()` está sin resolver |
| Contenido de `from_jid` en subidas de logs sin sesión | `AbstractC05620Al.A0G` es abstracto |
| Validación en el servidor de tokens, códigos y payloads de apelación | lado del servidor |
| Operaciones que llevan `@deidentified` | en `*_pando_flatbuffer_data.bin`, sin esquema |
| Significado de "NTA", del productor del id secundario `phoneyid_id`, de `c2dm_reg_id` como campo de petición | solo nombres |
| Si `HomeActivity` puede lanzarse sin registro y qué hace | compuerta de clase base sin resolver |
