<!-- src-sha1: b8a925dee480430088a421b7aba690bc2f641a5f -->
# WhatsApp Seguridad de la cuenta — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-22
**Alcance:** verificación del número de teléfono sobre una cuenta existente (HTTP de registro `/v2/*`), métodos de segundo factor, PIN de verificación en dos pasos y correo de recuperación, contraseña de la cuenta (envelope `#PWD_WA`, dependencia del usuario canónico), código nativo OPAQUE / VOPRF y a qué sirve realmente, login y gestión de passkeys, dispositivos de confianza, recuperación de cuenta (intercambio de nonce del usuario canónico), soft logout / login-back, operaciones w:mex (doc_ids, variables, raíces de respuesta), feature flags, notas de Baileys

---

## 1. Qué es (técnicamente)

"Seguridad de la cuenta" en el cliente Android no es un único subsistema. Son cinco mecanismos independientes superpuestos al flujo de registro por número de teléfono. Todas las afirmaciones son análisis estático del APK decompilado; nada se capturó en la red. Nivel: **found** = leído en código o assets, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres ofuscados son por build y se volvieron a resolver en 2.26.41.6.

| Mecanismo | Dónde se aplica | Credencial | Clases principales del cliente (2.26.41.6) |
|-----------|---------------------|------------|-------------------------------|
| Verificación del teléfono (OTP) | HTTP de registro, `/v2/exist` → `/v2/code` → `/v2/register` | SMS / voz / flash / dispositivo anterior / OTP por correo / silent auth | `K49` (`RegistrationHttpManager`), `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Segundo factor en el registro | `/v2/register` con reason `security_code`, luego `VerifyTwoFactorAuth` | PIN de 6 dígitos, contraseña de la cuenta, OTP por correo | `VerifyTwoFactorAuth`, `EnumC43759JAu`, `HOZ` |
| Verificación en dos pasos (PIN + correo) | IQ `urn:xmpp:whatsapp:account` `<2fa>` | PIN de 6 dígitos, correo de recuperación opcional | `C1DP` (`TwoFactorAuthManager`), `C1DT` (`TwoFactorXmppMethods`) |
| Contraseña de la cuenta | w:mex (`whatsapp-android-mex`, `whatsapp-android-www`) | 8-20 caracteres, letra + dígito | `PasswordRepository`, `PasswordServerApiImpl`, `CanonicalPasswordService` |
| Passkey (WebAuthn) | `/v2/passkey_auth` en el login; IQ `passkey` o w:mex para la gestión | passkey de plataforma mediante Credential Manager | `PasskeyServerApiImpl`, `PasskeyCreateFlow`, `PasskeyVerifier`, `K15` |
| Dispositivo de confianza | w:mex | registro del lado del servidor con clave en el `ANDROID_ID` hasheado | `TrustedDevicesServerApiImpl`, `RegTrustedDeviceGraphQLHelper` |
| Soft logout / login-back | w:mex | ninguna (flag de estado) | `LogoutManager`, `LogoutPushManager` |
| Recuperación de cuenta | w:mex, usuario canónico de Meta | envelope RSA/AES de un secreto generado por el cliente | `AccountRecoveryManager` |

Dos puntos que deciden todo el reporte:

- La máquina de estados OPAQUE de `libwhatsapp.so` está conectada a la contraseña del **backup cifrado de extremo a extremo** (handlers `encb/*`), no a la contraseña de la cuenta (sección 6).
- La contraseña de la cuenta en este build se crea y se cambia mediante `XfbWaCreatePasswordMutation` / `XfbWaChangePasswordMutation` con un envelope RSA/AES (`#PWD_WA:11`), y solo si la app posee credenciales de usuario canónico de Meta (sección 5).

---

## 2. Transportes y catálogo de operaciones

### 2.1 Cuatro transportes

| Transporte | Uso | Evidencia |
|-----------|----------|----------|
| HTTPS `/v2/<name>` (stack de registro) | verificación del teléfono, segundo factor en el login, aserción de passkey, confirmación de dispositivo | found: constantes de ruta en `AbstractC45307Jps` (sección 3.1) |
| IQ `xmlns="urn:xmpp:whatsapp:account"` | set / check / get de PIN y correo; OTP del correo de la cuenta; username, etc. | found |
| IQ `xmlns="passkey"` (smax ids 125, 126, 129) | start / finish / clear de passkey heredados | found, controlado por los flags 10452 / 10453 / 10461 |
| IQ `xmlns="w:mex"` | todas las operaciones GraphQL de abajo | found |

### 2.2 Envelope w:mex y origen del doc_id

Las variables se envían como JSON. Casi todas las mutations envuelven sus campos en un único objeto: el helper `AbstractC197058a0.A17(obj, vars)` guarda el objeto bajo la clave `input` (found). Excepciones: las dos mutations `Xfb*` de contraseña ponen `encrypted_password` bajo `data` (found); `PasskeyDeleteMutation` también usa `input` (mediante `c16770ig.A00(obj, "input")`).

Los doc_ids no son literales en el código. El cliente envía el nombre de la operación más un nombre de configuración (`whatsapp-android-mex`, `whatsapp-android-www`, `whatsapp-android-facebook-schema`); el id numérico se lee de `assets/whatsapp-android-{mex,www,facebook-schema}_client_persist_ids.json` (found). Cada doc_id de abajo se leyó de esos assets en 2.26.41.6 y el nombre de la operación se comprobó contra un call site. Ninguno es `tested`.

### 2.3 Catálogo de operaciones (con call sites presentes)

Las variables van dentro de `input` salvo indicación contraria. "Raíz" es el nombre del objeto de respuesta que lee el cliente.

| Operación | doc_id | Config | Variables | Raíz y campos leídos |
|-----------|--------|--------|-----------|----------------------|
| `HasPasswordQuery` | `25379221318423478` | mex | ninguna | `xwa2_has_password`: `has_password`, `upgrade_needed` |
| `DeletePasswordMutation` | `27247058691550586` | mex | ninguna | `xwa2_delete_password`: `success`, `twofa_auto_disabled`; el error 409 significa "necesita correo" |
| `GetTwofaQuery` | `27608881388708005` | mex | `device_id` | `xwa2_get_twofa`: `twofa_enabled`, `twofa_methods[]{method,value,state}`, `is_device_trusted`, `latitude`, `longitude` |
| `SetTwofaMutation` | `28092515560345874` | mex | `twofa_enabled` (bool), `device_id` | `xwa2_set_twofa`: `success`, `twofa_already_enabled`, `is_device_trusted` |
| `WaPasswordEncryptionKeyQuery` | `27318258844468227` | www | ninguna | `wa_password_encryption_key`: `public_key` (PEM), `key_id` |
| `XfbWaCreatePasswordMutation` | `36595298760118580` | www | `data.encrypted_password` (no bajo `input`) | `xfb_wa_create_password` (campos de éxito / error no resueltos) |
| `XfbWaChangePasswordMutation` | `27534818572826036` | www | `data.encrypted_password` | `xfb_wa_change_password` |
| `AddTrustedDeviceMutation` | `24522952587403287` | mex | `device_id`, `device_name` | `xwa2_add_trusted_device.list_of_trusted_device[]` |
| `UntrustTrustedDeviceMutation` | `26574930682133620` | mex | `device_id`, `reason` (`"REREG"` en la única llamada) | raíz no resuelta |
| `DeleteTrustedDeviceMutation` | `33867503889559538` | mex | `device_id` | `xwa2_delete_trusted_device` (bool) |
| `GetTrustedDevicesQuery` | `27391232653862770` | mex | `device_id` | `xwa2_get_trusted_devices.list_of_trusted_device[]`: `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` |
| `WhatsappTrustedDeviceRegistration` | `27335489319457030` | facebook-schema | `client_mutation_id`, `payment_type="TRUST_BINDING"`, `platform_trust_token`, `actor_id` / `logging_id` / `product_id` nulos | trust binding de pagos (`RunnableC53437NtS`), no el dispositivo de confianza del login |
| `RegistrationPasskeyStartRegisterMutation` | `25415371271434748` | mex | ninguna | `xwa2_passkey_start_register.credential_create` (string) |
| `RegistrationPasskeyFinishRegisterMutation` | `24611221275218156` | mex | `credential`, `key_attestation` | `xwa2_passkey_finish_register` (bool) |
| `RegistrationPasskeyEnableMutation` | `25147880151540247` | mex | `credential` | `xwa2_passkey_enable` (bool) |
| `RegistrationPasskeyClear` | `25111972538494859` | mex | ninguna | `xwa2_passkey_clear` (bool) |
| `RegistrationPasskeyUpdateClientEncryptionStatusMutation` | `24866837389649930` | mex | `credential`, `status` (true) | `xwa2_passkey_update_client_encryption_status` (bool) |
| `PasskeyListExistResponseQuery` | `26930537423220681` | mex | ninguna | `xwa2_passkey_exist_v2`: `result`, `uuid`, `passkeys[]{credential,create_ts_s,used_ts_s,password_manager,aaguid,usecases,is_disabled}` |
| `PasskeyDeleteMutation` | `25225683640428243` | mex | `credential_ids` (lista) | `xwa2_passkey_delete.credential_ids` |
| `AccountLoginMutation` | `27298465499757127` | mex | `phone_number` (string JID sin procesar) | no se lee |
| `AccountLogoutMutation` | `26863447609979194` | mex | `enabled_biometric` (bool), `phone_number` | no se lee; timeout del cliente de 5 s |
| `WWWTriggerAcountRecovery` | `24896267680055094` | mex | `nonce_encryption_key` (PEM en base64), `use_case`, `registration_trace_id`, `request_id` | el nonce se entrega por notificación (sección 9) |
| `WWWExchangeNonceForAccessToken` | `25727187160203620` | mex | `nonce`, `use_case`, `encrypted_password`, `request_id`, `registration_trace_id` | access token |
| `WWWGetNonceForCompanionDevice` | `24635485196143064` | mex | `fbid`, `nonce_encryption_key`, `encrypted_password`, `request_id`, `registration_trace_id` | usuario canónico del companion |
| `RegAccountTransferVerifyTokenMutation` | `7580940708621318` | mex | `token` | verificación del OTP de transferencia de cuenta, timeout de 60 s |
| `ValidateVerifierConfidence` | `25879669248324812` | mex | `authResponse` (base64) | ping de confianza del autoconf |
| `GetRegistrationUpsells` / `GetDynamicRegistrationUpsells` / `RegistrationDynamicUpsellShown` | `24265038133175291` / `32273353145641323` / `25435755019399064` | mex | shown: `input="PASSKEYS"` (string) | programación de upsells en el registro |

### 2.4 Operaciones en los assets sin call site en este build

Buscadas por nombre en `java_src` y smali; sin referencias (found). Sus variables y respuestas son desconocidas.

| Operación | doc_id |
|-----------|--------|
| `SetPasswordMutation` | `33855141324134176` |
| `CheckPasswordMutation` | `26881928138061632` |
| `PasskeyExistResponseQuery` | `25188064727509430` |
| `PasskeyRequestChallengeMutation` | `26311497405176139` |
| `PasskeyVerifyChallengeMutation` | `26876394218624479` |
| `RegistrationPasskeyDisableMutation` | `27775237998742831` |

En 2.26.41.6 un login con passkey no usa las mutations request / verify; usa `/v2/passkey_auth` (sección 7.1). Las operaciones de passkey de pagos (`PaymentsPasskey*`) y de Brasil (`BrPasskey*`) son superficies separadas y no se cubren.

---

## 3. Verificación del número de teléfono sobre una cuenta existente

### 3.1 Stack de registro y endpoints

`K49` (`RegistrationHttpManager`) construye las peticiones y parsea los resultados. Existen dos stacks HTTP: el bridge de Kotlin (`KotlinRegistrationBridge`, `RetryingHttpClient`) y un cliente nativo `wamsys` al que se llega mediante `AbstractC45509Jtc` y `JniBridge.jvidispatch*`. El selector `K49.A0b` devuelve true si la config 24762 o el flag **24763** está activo (found); las etiquetas de log terminan en `/kotlin` o `/wamsys`.

Las rutas están ofuscadas con XOR 0x12 en `AbstractC45307Jps` y se decodifican a (found):

| Ruta | Función Kotlin | Campos enviados (además de los campos de dispositivo / e2e) |
|------|-----------------|------------------------------------------|
| `/v2/exist` | `performSameDeviceCheck` / `checkIfExists` | `lg`, `cc`, `in`, `foa_backup_token`, `client_capabilities`, `advertising_id`, `context`, `id`, `backup_token` |
| `/v2/challenge` | `challengeRequest` | login challenge; respuesta `login`, `challenge`, `retry_after` |
| `/v2/code` | `generateAuthCode` | `token`, `method`, `context`, `advertising_id`, `clicked_education_link`, `manage_call_permission`, `call_log_permission`, `client_start_message` |
| `/v2/register` | `registerPhoneNumber` | `code`, `auth_response` (bytes), `method`, `context`, `advertising_id`, más entradas del mapa como `security_code`, `reset`, `wipe_token`, `cred_token` |
| `/v2/security` | `verifySecurityCode` | `code`, `reset`, `wipe_token` (ruta heredada, flag 26215 desactivado) |
| `/v2/passkey_auth` | `passkeyAuth` | `lg`, `context`, `credential` (resultado de la aserción) |
| `/v2/device_logout_send`, `/v2/device_logout_fetch` | `sendAccountDefenceDeviceConfirmation`, `fetchAccountDefenceDeviceConfirmation` | `token` |
| `/v2/wfs` | `wfsAuth` | auth Meta SSO ("WFS"), respuesta `login`, `wa_ac_machine_id`, `lid` |
| `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop` | consentimiento, logs de funnel, verificación silenciosa, AB props | no específicos de seguridad |

### 3.2 Pasos

| # | Paso | Evidencia |
|---|------|----------|
| 1 | `/v2/exist` devuelve el estado de la cuenta: qué métodos de OTP son elegibles, tiempos de espera, `second_factor_methods`, `is_device_trusted`, `passkey_auth_challenge`, `password_eligible`, estado de wipe | found (3.3) |
| 2 | Si `passkey_auth_challenge` está presente y no ha expirado, se ofrece el login con passkey (sección 7.1) | found |
| 3 | El usuario elige un método; `/v2/code` con `method` | found |
| 4 | El usuario escribe el OTP; `/v2/register` con `code` y `method` | found |
| 5 | `status=ok` termina el registro (`login`, `lid`, `ent_access_token`, `ent_canonical_fbid` se leen del resultado). `status=fail` con un reason (3.5) | found |
| 6 | El reason `security_code` significa que la cuenta tiene segundo factor: `VerifyTwoFactorAuth` recoge PIN, contraseña u OTP por correo y vuelve a llamar a `/v2/register` (3.6) | nombre del reason found; navegación inferred |
| 7 | Tras el éxito: `RegisterName`, registro de dispositivo de confianza (sección 8), upsell de passkey (sección 7.2) | found |

Una "cuenta existente" no es una API aparte: el servidor responde a `/v2/exist` y `/v2/register` para un número que ya tiene cuenta con el mismo vocabulario de status / reason. Campos como `possible_migration`, `need_chat_restore_pn_verify`, `acc_tr_eligible` (transferencia de cuenta) y `wa_old_eligible` (verificar mediante el teléfono anterior) muestran que el servidor dirige los flujos de cuentas existentes por las mismas dos llamadas (campos found, significado inferred a partir de los nombres).

### 3.3 Campos de respuesta de `/v2/exist` que lee el cliente

| Campo | Tipo | Uso |
|-------|------|-----|
| `status` (`ok`/`fail`), `reason` | string | resultado |
| `login`, `lid` | string | identificadores de cuenta devueltos al cliente (consumidor no trazado) |
| `is_device_trusted` | bool | se guarda como `pref_is_device_trusted`; oculta el checkbox de dispositivo de confianza |
| `second_factor_methods` | array de strings | se guarda como `pref_second_factor_methods`; los valores son strings de wire de `EnumC43759JAu` |
| `passkey_auth_challenge`, `passkey_credential` | string | el challenge se guarda como `reg_passkey_auth_challenge` con un timestamp; pista del id de credencial |
| `password_eligible` | int | elegibilidad para el upsell de contraseña |
| `sms_wait`, `voice_wait`, `wa_old_wait`, `email_otp_wait`, `send_sms_wait`, `silent_auth_wait`, `retry_after` | string | cooldowns por canal |
| `sms_length`, `voice_length`, `wa_old_length`, `email_otp_length` | int | longitud esperada del código |
| `email_otp_eligible`, `wa_old_eligible`, `silent_auth_eligible`, `carrier_silent_auth_eligible`, `send_sms_eligible`, `acc_tr_eligible` | int | elegibilidad del método |
| `email`, `wa_old_device_name` | string | correo enmascarado / etiqueta del dispositivo anterior (enmascarado no verificado) |
| `reset_method`, `wipe_type`, `wipe_token`, `wipe_wait`, `wipe_expiry_time`, `server_time` | mixto | flujo de PIN olvidado (3.7) |
| `fallback_methods`, `recommended_method`, `num_visible_dbs_methods` | array / int | orden de la UI |
| `ent_access_token`, `ent_canonical_fbid` (en `/v2/register`) | string | credenciales del usuario canónico de Meta |
| `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `version_upgrade`, `custom_block_screen` | mixto | pantallas de baneo / actualización (ver reporte de ban) |

### 3.4 Métodos de OTP

La hoja de solicitud de código dirigida por el servidor (`RequestServerDrivenOtpCodeBottomSheetFragment`, `C46760Kbq`) ofrece estos strings de `method` (found): `sms`, `voice`, `flash`, `wa_old`, `email_otp`, `password`, `passkey`, `send_sms`. `silent_auth` y `account transfer` tienen sus propios campos de elegibilidad.

### 3.5 Motivos de fallo de `/v2/register` (parser en `KotlinRegistrationBridge`)

| `reason` | Significado (found: nombre; significado inferred) |
|----------|-----------------------------------------|
| `incorrect` | código incorrecto o PIN incorrecto |
| `security_code` | se requiere segundo factor |
| `second_code`, `device_confirm_or_second_code` | se requiere segundo factor o confirmación de dispositivo |
| `too_many_guesses`, `guessed_too_fast` | límite de intentos; se devuelve `guess_wait` |
| `stale`, `mismatch`, `missing`, `format_wrong` | código expirado / no coincide / ausente / mal formado |
| `sms_required` | hay que verificar por SMS |
| `blocked`, `not_allowed`, `limited_release` | baneado, no permitido, compuerta de despliegue |
| `temporarily_unavailable` | transitorio |
| `challenge` | se requiere una ronda de challenge (`/v2/challenge`) |
| `reset_too_soon` | reset de PIN olvidado solicitado demasiado pronto |
| `consent`, `consent_parent_linking_already_registered` | pantallas de consentimiento |

### 3.6 Métodos de segundo factor

`EnumC43759JAu` (found): `twofac_pin`, `password`, `email_otp`, `oauth_email`, `sms`, `voice`, `flash`, `wipe_full`, `wipe_offline`. Con el flag **28755** la pantalla se guía por `second_factor_methods` ("2FA dinámico", context string `twofac_dynamic`), y "verificar de otra manera" abre `Dynamic2faMethodSelectionBottomSheet`.

`K49.A0o` (`verifySecurityCode`):

| Condición | Wire |
|-----------|------|
| flag 26215 desactivado | heredado: `/v2/security` con `code` (y `reset`, `wipe_token` al hacer reset) |
| flag 26215 activado, method distinto de `password` | `/v2/register` con `security_code` = secreto en claro en el mapa de la petición, `method` |
| flag 26215 activado, method `password` | la contraseña se cifra primero con `HOZ.A08` en `#PWD_WA:11:<epoch>:<blob>` (sección 5.3); el blob se envía en la posición de `code` de `/v2/register`; si el cifrado falla, el QPL reporta `PASSWORD_ENCRYPT_FAILED` |

La clave del envelope proviene de `WaPasswordEncryptionKeyQuery` mediante `CanonicalPasswordService.A04(..., true)` (llamado desde `C47204KjV`, found). Qué campo exacto lleva el blob en el wire se leyó del orden de argumentos del constructor, no de una petición capturada (inferred).

### 3.7 PIN olvidado, wipe y reset por correo

`/v2/exist` o `/v2/register` pueden devolver `reset_method`, `wipe_type` (`offline` o `full`), `wipe_wait` (segundos), `wipe_token`, `wipe_expiry_time`, `server_time` (found). `VerifyTwoFactorAuth.A03` los mapea a cuatro estados (found): 0 no permitido, 1 en cooldown ("0_7 days, offline_info"), 2 `offline` ("7_30"), 3 `full` ("over 30"). La llamada de reset envía `reset=<mode>` y `wipe_token`; `wipe_full` y `wipe_offline` son métodos de segundo factor (3.6). Qué borra el servidor en un wipe `offline` frente a uno `full` es desconocido.

---

## 4. Verificación en dos pasos (PIN) y correo de recuperación

### 4.1 Estado del cliente

`C1DP` (`TwoFactorAuthManager`) guarda el PIN localmente (found): pref `two_factor_auth_code`, opcionalmente cifrado (`two_factor_auth_using_encryption`, descifrado por `C1DP.A01` mediante un helper de keystore). Se usa para un aviso periódico "verifica tu PIN": intervalos de recordatorio 6 h, 12 h, 1 d, 1 d, 3 d, 7 d (`C1DP.A0I`, prefs `two_factor_auth_nag_time`, `two_factor_auth_nag_interval`). Otras prefs: `two_factor_auth_email_set`, `two_factor_auth_dynamic_validated`, `two_factor_auth_last_code_correctness`, `pref_2fa_{sms,voice,flash,email_otp}_wait_time`.

### 4.2 Stanzas IQ (`xmlns="urn:xmpp:whatsapp:account"`, timeout de 32 s)

| Acción | Stanza | Respuesta leída | Clase |
|--------|--------|---------------|-------|
| Obtener estado (smax 114) | `type=get` `<2fa/>` | `<2fa>`: un hijo `code` presente significa PIN establecido; un hijo `email` presente activa `two_factor_auth_email_set` | `C1DT.A00`, `C28896Cgx` |
| Establecer PIN / correo | `type=set` `<2fa><code>PIN</code><email>addr</email></2fa>` (cada hijo es opcional) | el éxito escribe prefs; código de error + texto a los listeners | `C1DP.A07`, `C28899Ch0` |
| Comprobar PIN | `type=get` `<2fa><code>PIN</code></2fa>` | `<2fa>` que contiene `code` significa correcto | ruta de `VerifyTwoFactorAuthCodeDialogFragment`, `HandlerC25225AtN` |

El PIN tiene 6 dígitos (`SetCodeFragment`, comprobación de longitud `== 6`). Set es el tipo 1, confirm es el tipo 2. `Fetch2FAEmailStatusJob` vuelve a leer el estado (32 s) para ver si el correo fue verificado. Si el servidor devuelve más hijos además de `code` / `email` es desconocido.

### 4.3 OTP del correo de la cuenta (separado de `<2fa><email>`)

`C31107Dfz` construye, `KRB` parsea (prefijo de log `EmailVerificationXmppMethods`):

| Paso | Stanza | Respuesta |
|------|--------|----------|
| solicitar OTP | `type=set` `<verify_email><lg/><lc/></verify_email>` (idioma / locale, 2-3 caracteres) | `verify_email.wait_time` |
| verificar OTP | `type=get` `<verify_email><code>NNNNNN</code></verify_email>` (6 caracteres) | `verify_email.code_match` (`true`/`false`), `wait_time` |

La dirección de correo en sí no está en estos stanzas (se establece antes, ruta no trazada). Lo usan `VerifyEmailActivity` y el segundo factor `email_otp`.

### 4.4 PIN frente a contraseña frente a GetTwofa

`GetTwofaQuery` devuelve `twofa_methods[]{method,value,state}`. `PasswordUpsellEligibility` busca los strings `password` y `pin` en esa lista (found). `SetTwofaMutation` se llama solo después de crear una contraseña, en modo best effort, con el id de dispositivo hasheado (sección 5.2); `twofa_auto_enabled` / `twofa_auto_disabled` son los flags de resultado. El PIN en sí nunca se envía por w:mex.

---

## 5. Contraseña de la cuenta

### 5.1 Entidades

| Entidad | Rol |
|--------|------|
| `PasswordRepository` | orquestación: `setPassword`, `getTwofa`, id de dispositivo (`computeDeviceId`) |
| `PasswordServerApiImpl` | `HasPasswordQuery`, `DeletePasswordMutation`, `GetTwofaQuery`, `SetTwofaMutation` |
| `CanonicalPasswordService` | obtención de clave, `A03` crear, `A02` cambiar (mutations `Xfb*`, esquema `whatsapp-android-www`) |
| `HOZ` | cifrado del envelope (`A08` → `#PWD_WA:11`) |
| `PasswordCredentialManager` | guarda la credencial en el Android Credential Manager (`saveCredential`, se omite sin un número E.164) |
| UI | `CreatePasswordActivity`, `ReplacePinWithPasswordActivity`, `PasswordUpgradeFragment`, `SettingsPassword`, `TrustThisDeviceActivity` |

### 5.2 Establecer / cambiar / eliminar

`PasswordRepository.setPassword` primero necesita credenciales canónicas; sin ellas falla con "No canonical credentials available to set password" (found). Es decir, la contraseña se asocia al usuario canónico de Meta, no solo al número de WhatsApp.

```
setPassword(pw, isChange, enableTwofa)
  isChange  -> CanonicalPasswordService.A02  XfbWaChangePasswordMutation
  !isChange -> CanonicalPasswordService.A03  XfbWaCreatePasswordMutation
               then, if enableTwofa: GetTwofa/SetTwofa best effort (device_id = base64(SHA-256(ANDROID_ID)))
each: A04 = key fetch (WaPasswordEncryptionKeyQuery) + HOZ.A08 -> data.encrypted_password
```

`device_id` es `K2M.A01(android_id)` = Base64 (flag 2, sin wrap) del SHA-256 de `Settings.Secure.ANDROID_ID` (found). Delete no envía variables; un código tipo HTTP 409 se mapea a un resultado "bloqueado, necesita correo" (found). Reglas locales en `CreatePasswordActivity`: longitud de 8 a 20, al menos una letra y un dígito, la confirmación debe coincidir (found).

### 5.3 Envelope `#PWD_WA:11` (`HOZ.A02` / `A08`)

```
epoch   = current time in seconds
aesKey  = random 32 B (AES-256)         iv = random 12 B
ct||tag = AES-GCM(aesKey, iv, utf8(secret))    // no AAD on this path
wrapped = RSA/ECB/PKCS1Padding(serverPublicKey, aesKey)
blob    = 0x01 | key_id(1 B) | iv(12) | len(wrapped) as uint16 LE | wrapped | tag(16) | ct
out     = "#PWD_WA:11:" + epoch + ":" + base64(blob, URL_SAFE | NO_WRAP | NO_PADDING)
```

`key_id` debe estar entre 1 y 255 (`CanonicalPasswordService.A01`). La clave RSA se parsea del PEM como X.509 SPKI; la ruta PKCS1 no comprueba el tamaño del módulo (la prueba de ≥ 4096 bits existe solo en `HOZ.A06`, una variante OAEP distinta). El mismo envelope se usa en tres lugares (found): segundo factor del registro (3.6), creación / cambio canónico (5.2) y recuperación (`exchangeNonce`, sección 9, envuelto en el JSON `{version:1,timestamp,password}`).

Otras variantes en `HOZ` (no `#PWD_WA:11`): `A03` y `A06` usan RSA-OAEP-SHA-256 con IV cero y AAD (la ruta Waffle SSO escribe `#PWD_WAFFLE` en `C40069Hd8` / `C40090HdT`).

---

## 6. OPAQUE, VOPRF y el código criptográfico nativo

### 6.1 Qué está presente

| Elemento | Dónde | Nivel |
|------|-------|------|
| `WESOpaqueClientRegistrationStartResult` (.rodata `0xaebae`), `...LoginStartResult` (`0xaebd5`), `...RegistrationFinishResult` (`0xaeda9`), `...LoginFinishResult` (`0xaedd1`), `...RegistrationState` (`0x115042`), `...LoginState` (`0x115072`) | strings de `libwhatsapp.so` | found |
| `OPAQUE_PBKDF2_SALT` (`0x17e129`), `VOPRF06-HashToGroup-` (`0x19465a`), `VOPRF06-Finalize-` (`0x19466f`) | strings de `libwhatsapp.so` | found |
| `org/whispersystems/curve25519/NativeVOPRFExtension` | misma lib; la clase Java tiene `nativeBlind`, `nativeUnBlind`, `nativePcdBlind` | found |
| `libvoprf-ed25519.so`, `libvoprf-ristretto.so` | libs separadas, exportan solo `JNI_OnLoad`; wrappers Java `com.facebook.privacy.acs.VoprfEd25519` / `VoprfRistretto` | found |

### 6.2 Funciones que referencian los strings (arm64, vaddr)

| Función | Tamaño | Contenido | Nivel |
|----------|------|---------|------|
| `fcn.0075a1c0` | 644 B | referencia `VOPRF06-HashToGroup-`; init / update ×6 / finish de SHA-512 de mbedTLS, luego una segunda pasada de SHA-512 | found |
| `fcn.0075b550` | 712 B | referencia `VOPRF06-Finalize-` y `OPAQUE_PBKDF2_SALT`; SHA-512 sobre el transcript de finalize, luego `mbedtls_pkcs5_pbkdf2_hmac` | found |
| `fcn.0075a618`, `fcn.0075ad40` | - | ambas llaman a `fcn.0075b550`, luego `mbedtls_hkdf_extract` + tres `mbedtls_hkdf_expand` (md type `0xb`) | found |
| `fcn.0075a0d4` | - | llama a `fcn.0075a1c0` | found |

Llamada a PBKDF2 en `fcn.0075b550` (desensamblado): longitud de la contraseña `0x40` (64 B, la salida del OPRF), longitud de la sal `0x12` = 18 = longitud de la etiqueta `OPAQUE_PBKDF2_SALT` y el buffer se inicializa desde esa etiqueta, longitud derivada `0x40`, el número de iteraciones lo pasa el llamador (no es una constante en esta función), md type `0xb`. El md type `0xb` equivale a SHA-512 en la numeración de mbedTLS 3.6 (inferred a partir del valor del enum y las longitudes de 64 bytes). Es decir, la salida del OPRF alimenta PBKDF2-HMAC-SHA-512 con la etiqueta ASCII como sal (found para la forma de la llamada, inferred para el hash).

Los roles de las funciones (blind, finalize, registration-finish, login-finish) son inferred a partir de la forma de las llamadas. El grupo / ciphersuite (curva, id añadido a los prefijos `VOPRF06-`), los layouts de bytes de KE1 / KE2 / KE3, el contenido del envelope y la variante de AKE son **unknown**; el código nativo se leyó como desensamblado de las funciones citadas, no decompilado.

### 6.3 Quién lo llama: backup cifrado, no la contraseña de la cuenta

La entrada Java de la máquina de estados es el protocolo de backup cifrado (prefijo de log `encb/`):

| Clase | Rol (found) |
|-------|--------------|
| `EncBackupViewModel` | crea `C61447Rhg` (login handler) con el string de contraseña de backup del usuario |
| `AbstractC62498S8e` | envía los IQ `sendInitRegIq`, `sendBeginRegIq`, `sendFinishRegIq`, `sendInitLoginIq`, `finishLoginOnSuccess`, `sendDeleteAccountIq` (`EncryptedBackupProtocolHelper`) |
| `C62510S8q` (smali `X/S8q`) | handler de respuestas; `jvidispatchOOO(0xb, password, ...)` devuelve el estado de login (`Rtz`), `jvidispatchOO(0x20, state)` el siguiente mensaje |
| `C62511S8r` | respuesta de begin-login: verifica `l2` con `l2_sig` y `ed_pub` (Ed25519), lee `count`, `backoff`, `max_attempts`, luego `jvidispatchOIOOO(1, 100000L, state, ...)` |
| `RunnableC29321Co8` | finish-login: `jvidispatchOIOO(1, 100000L, state, ...)`, lee los campos del modelo, descifra con AES-GCM la clave de backup, construye el proto `C25803BBm` (`backupKeyData_`, `r3_`, `opaqueChallenge_`, `transcript_`) |

`100000` se pasa a las llamadas nativas de finish tanto en register como en login (found). Es probablemente el número de iteraciones de PBKDF2 (inferred: la función nativa lo toma como parámetro). Que estos índices de `jvidispatch` aterricen en el código `WESOpaque*` es inferred a partir de los argumentos (string de contraseña de entrada, objetos de estado entre llamadas, campos `l2` / `r3`) y de la ausencia de cualquier otro consumidor; ningún símbolo Java nombra OPAQUE. El código de la contraseña de la cuenta (sección 5) nunca los toca.

### 6.4 El otro VOPRF: tokens ACS de Meta

`NativeVOPRFExtension` y `libvoprf-ed25519.so` tienen como consumidores Java a `C1N9` (`ACSTokenProviderImpl`, prefijo de log `ACSToken/`) y `KYL`: factor de blinding, token ciego firmado, prueba DLEQ, unblind, secreto compartido (strings found `blinding_factor_string`, `shared_secret_string`, `ACSToken/processSignedBlindedToken`). Las operaciones correspondientes en los assets son `WaAcsGetConfig` (`27388182297440754`) y `WaAcsIssueCredentials` (`26645395115100537`); ninguno de los nombres aparece en el código, por lo que el transporte de la petición del token no está trazado. Es un token de credencial anónima y no un login con contraseña.

### 6.5 Qué significa esto para el "login con contraseña"

| Afirmación | Estado en 2.26.41.6 |
|-------|---------------------|
| El login con contraseña de la cuenta usa OPAQUE | no respaldado por el código: la contraseña se envía como envelope RSA/AES (`#PWD_WA:11`), no se construye ningún mensaje OPAQUE en las rutas leídas; `SetPasswordMutation` y `CheckPasswordMutation` no tienen call site |
| Existe un cliente OPAQUE nativo | found |
| Sirve a la contraseña del backup cifrado | found (llamador Java), vínculo con los símbolos nativos inferred |
| El servidor almacena un verifier en lugar de la contraseña para la contraseña de la cuenta | unknown |

Strings de Java que parecen evidencia de OPAQUE pero no están relacionados (found): `opaqueChallenge_` (proto de bootstrap del backup de arriba), `opaquePayload_` (`C61318RfY`, frame de migración tethered), `OpaqueConfig` / `prefersOpaqueConfig` (config de bitmap en `EnumC167127Ba`), `OpaqueKey(` (`C44715Jfl`, un wrapper de string), `KE1` (`X.KE1` es una clase de Android Compose), `opaque_client_data` (columna de history-sync).

---

## 7. Passkeys (WebAuthn)

### 7.1 Login en el momento del registro

| Paso | Evidencia |
|------|----------|
| `/v2/exist` devuelve `passkey_auth_challenge`; `K15.A03` lo acepta mientras sea más reciente que `SignalCredentialStateController.MAX_RETRY_TIME` | found |
| `PasskeyVerifier.onPasskeyChallengeReceived` ejecuta una aserción de credencial descubrible mediante `androidx.credentials` (`PasskeyLowLevelAndroidApiImpl.loginWithPasskey`); la etapa se mantiene en la pref `passkey_login_stage` | found |
| `K49.A0l` envía el resultado como `credential` a `/v2/passkey_auth` | found |
| Respuesta: `status` (`ok`/`fail`), `reason` (`temporarily_unavailable`, `disabled`), `credential_create` (string), `login`, `cred_token` | found |
| `cred_token` se guarda por número de teléfono en `passkey_disabled_cred_token_map` y se reenvía como `cred_token` en peticiones posteriores cuando el flag **25565** está activo | found; propósito (demostrar que una passkey fue deshabilitada) inferred |

Los resultados del lado del cliente se registran como `passkey_client_login_{cancelled,nopasskey,ineligible,error,success}`. `prepareGetCredential` se usa solo en Android 14+ (SDK 34) y con el flag **21638** (found).

### 7.2 Crear y gestionar

Upsell tras el paso de 2FA: `VerifyTwoFactorAuth.onCheckPasskeyUpsellAfter2FA` usa `PasskeyCreateEducationScreen` o un bottom sheet; el flag **20409** alterna entre el flujo de control y la ruta de quick-promotion (QP), el flag **16591** añade una comprobación de elegibilidad (found).

| Operación | Compuerta MEX | Fallback IQ (`xmlns="passkey"`) |
|-----------|----------|---------------------------------|
| start register | flag **10453** | smax 125, `type=get` |
| finish register | flag **10452** | smax 126, `type=set` |
| clear | flag **10461** | smax 129, `type=set` |
| list / exists, delete, enable, update encryption status | siempre MEX | ninguno |

`credential_create` de start-register se guarda en caché en `passkey_create_challenge`. Finish register envía `credential` y `key_attestation`; el payload de attestation se construye solo si el flag **28809** está activo (base64 de la key attestation, `getKeyAttestationPayload`). El flag **8877** envuelve start / finish en un helper de retry / timeout (`C29707Cw7`, rol inferred). `PasskeyRandomizedDailyCronJob` y `PasskeyExistsCache` refrescan la lista de exists; la respuesta de exists guarda `uuid` en `reg_passkey_exists_uuid`.

### 7.3 PRF y cifrado del lado del cliente

`PasskeyPrfSecrets` usa el input PRF estático `WhatsAppPasskeyStaticPrfInputV1` y guarda una root key derivada de PRF en `prf_derived_root_key.key` (etiqueta de la clave de encapsulación `prf_derived_root_key_file_encapsulation_key`). `RegistrationPasskeyUpdateClientEncryptionStatusMutation` le indica al servidor que la passkey se usa para cifrado del lado del cliente. El consumidor es el flujo de backup cifrado (`VerifyPasskeyFragment`, inferred a partir de la ubicación de la clase).

---

## 8. Dispositivos de confianza

| Elemento | Valor |
|------|-------|
| `device_id` | `Base64(SHA-256(ANDROID_ID))` (sin wrap), `K2M.A01` |
| `device_name` | `<MANUFACTURER>-<MODEL>` (`HO4.A00`) |
| Checkbox | se muestra en `VerifyPhoneNumber` y `VerifyTwoFactorAuth` cuando el flag **30530** está activo y `pref_is_device_trusted` es false; prefs `pref_trusted_device_checkbox_shown` / `_checked` |
| Fin del registro (`RegisterName`) | con opt-in: `AddTrustedDeviceMutation`; sin opt-in: `UntrustTrustedDeviceMutation` con `reason="REREG"` (`C29652Cu9`, found) |
| Ajustes | `TrustedDevicesRepository` lista (`GetTrustedDevicesQuery`) y elimina (`DeleteTrustedDeviceMutation`); `TrustThisDeviceActivity` |
| Efecto | `is_device_trusted` lo devuelven `/v2/exist`, `/v2/register`, `GetTwofa` y `SetTwofa`; el cliente lo usa para omitir el checkbox. Que un dispositivo de confianza omita el aviso de PIN / contraseña es inferred; ningún código del cliente omite el segundo factor |

Las entradas de `list_of_trusted_device[]` llevan `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` (la ubicación del último uso la provee el servidor; cómo se deriva es desconocido).

---

## 9. Recuperación de cuenta (usuario canónico de Meta)

`AccountRecoveryManager` no recupera los chats de WhatsApp ni la cuenta del número de teléfono. Vuelve a crear las credenciales de usuario canónico de Meta de una cuenta vinculada a FB (found).

| Paso | Detalle |
|------|--------|
| Disparador | `maybeRecoverAccount`: sin usuario canónico, o credenciales inválidas; la variante diferida está controlada por el flag **16017** |
| Clave del cliente | genera un par de claves, envía la clave pública (PEM, base64) como `nonce_encryption_key` en `WWWTriggerAcountRecovery` con `use_case`, `registration_trace_id`, `request_id` |
| Nonce | llega por notificación; el timeout produce "Account Recovery Failed due to Nonce notification timeout" |
| Intercambio | `WWWExchangeNonceForAccessToken` con `nonce`, `use_case`, `request_id`, `registration_trace_id`, `encrypted_password` = envelope `#PWD_WA:11` de un secreto aleatorio del cliente dentro del JSON `{version:1,timestamp,password}` |
| Companion | `WWWGetNonceForCompanionDevice`, `WWWTradeNonceForAccessTokens` hacen lo mismo para dispositivos vinculados (`CompanionCanonicalUserNonceManager`, `CompanionCanonicalUserAccessTokenJob`) |
| Relacionados | `WWWValidateCanonicalUser`, `WWWCanonicalUserValid`, `WWWAppGenerateCanonicalNonce` (existen call sites; campos no leídos) |

La grafía `Acount` es propia de WhatsApp. Cuál es el algoritmo de la clave de cifrado del nonce (el par proviene de `N6T.A02`) no está resuelto.

---

## 10. Login y logout

`LogoutManager` implementa un soft logout (multi-cuenta) y la ruta de login-back (found).

| Acción | Wire | Notas |
|--------|------|-------|
| Logout | `AccountLogoutMutation` `{phone_number, enabled_biometric}` | `enabled_biometric` proviene de un ajuste biométrico; timeout de 5 s, luego el logout continúa localmente ("timed out, proceeding with logout") |
| Push | `LogoutPushManager` deshabilita / rehabilita el push GCM (`"re-enable"` al revertir) | found |
| Local | `markCurrentAccountLoggedOut`, `removeLoggedOutAccountWithCleanup`, `deleteGmsBackupState`, UI opcional de borrado de chats (`DeleteChatsOnLogoutDialog`, `LoggedOutChatsFragmentDialog`) | found |
| Login back | `AccountLoginMutation` `{phone_number}`, luego `loginBack` → `actionReconnect`; espera hasta 7 s por la conexión | `PrimaryLoginBackActivity` |

Es un flag de estado del lado del servidor de una configuración multi-cuenta, no el login por número de teléfono de la sección 3 ni la eliminación de un dispositivo vinculado. El flag **28385** se lee en `LogoutManager` (rol sin resolver).

---

## 11. Feature flags

Los IDs van en negrita. Tipos: B = AB prop booleana, C = config. Los nombres no están en el cliente; el rol es lo que el código hace con el flag.

| ID | Dónde | Controla |
|----|-------|----------|
| **24762** (C) / **24763** (B) | `K49.A0b` | stack de registro Kotlin en lugar del `wamsys` nativo |
| **26215** | `K49` verify / reset security code | segundo factor del registro sobre `/v2/register`, habilita el envelope de contraseña; desactivado = `/v2/security` heredado |
| **25565** | `K49.A0M` | enviar el `cred_token` almacenado |
| **28755** | `VerifyTwoFactorAuth` | selección dinámica del método de 2FA desde `second_factor_methods` |
| **30530** | `VerifyPhoneNumber`, `VerifyTwoFactorAuth` | checkbox de dispositivo de confianza |
| **20409** | `VerifyTwoFactorAuth` | upsell de passkey QP post-2FA frente a control |
| **16591** | `VerifyTwoFactorAuth` | comprobación de elegibilidad de passkey antes del upsell |
| **21638** | `PasskeyAndroidApi` | `prepareGetCredential` (Android 14+) |
| **10452** / **10453** / **10461** | `PasskeyServerApiImpl` | MEX en lugar de IQ para finish / start / clear |
| **28809** | `PasskeyServerApiImpl` | payload de key attestation |
| **8877**, **31281** | `PasskeyCreateFlow` | wrapper de retry; ruta alternativa de passkey de pagos (roles inferred) |
| **5156** | `SetCodeFragment` | ofrecer "añadir correo" tras establecer el PIN |
| **5711** | `TwoFactorAuthActivity`, `SetCodeFragment` | solo layout (oculta el indicador de página) |
| **16017** | `AccountRecoveryManager` | procesamiento diferido del nonce |
| **28385** | `LogoutManager` | sin resolver |

---

## 12. Casos de error

| Síntoma | Causa | Solución / nota |
|---------|-------|------------|
| `/v2/register` reason `security_code` o `second_code` | la cuenta tiene segundo factor | enviar PIN / contraseña / OTP por correo mediante `/v2/register` (3.6) |
| `PASSWORD_ENCRYPT_FAILED` (QPL) | falló la obtención de la clave, `key_id` fuera de 1-255, o excepción criptográfica (logs `encryptRegistrationPassword/*`) | reintentar; el cliente aborta el intento |
| `reset_too_soon` | reset de PIN olvidado antes de que transcurriera `wipe_wait` | esperar; estado 1 de la UI |
| `too_many_guesses` / `guessed_too_fast` | límite de intentos de PIN u OTP | esperar `guess_wait` |
| `No canonical credentials available to set password` | no hay usuario canónico de Meta en el dispositivo | completar primero la configuración del usuario canónico |
| Falló la creación / cambio de contraseña | el payload `xfb_wa_*` no fue exitoso; código de error mapeado por `CanonicalPasswordService.A00` | enum de error de la UI `EnumC49982M3j` |
| `DeletePassword` 409 | se requiere el correo de la cuenta antes de eliminar | añadir el correo primero |
| `Account Recovery Failed due to Nonce notification timeout` | no se recibió la notificación | reintentar el disparador |
| `...passwordPublicKeyStr is null` / `passwordKeyIdStr is null` | falta el certificado de cifrado en el intercambio de recuperación | reintentar |
| `LogoutManager/callLogoutApi/timed out` | sin respuesta en 5 s | el logout continúa localmente |
| Passkey: `NoCredentialException`, `NotAllowedError`, GMS demasiado antiguo, falta Play services | fallos de Credential Manager | recurre a otros métodos |

---

## 13. Distinciones clave

| A | B |
|---|---|
| código nativo OPAQUE (contraseña del backup cifrado, IQ `encb/*` con HSM) | contraseña de la cuenta (`XfbWa*` + `#PWD_WA:11`) |
| `libvoprf-*.so` + `NativeVOPRFExtension` (tokens anónimos ACS) | máquina de estados OPAQUE (`WESOpaque*`) |
| PIN (IQ `<2fa>`, 6 dígitos) | contraseña (w:mex, 8-20 caracteres) |
| `<2fa><email>` (correo de recuperación para el reset del PIN) | flujo OTP `<verify_email>` y segundo factor `email_otp` |
| `SetTwofaMutation` (flag por id de dispositivo tras la contraseña) | IQ de establecer PIN |
| Dispositivo de confianza (login, `AddTrustedDeviceMutation`) | `WhatsappTrustedDeviceRegistration` (trust binding de pagos) |
| `AccountLogoutMutation` (soft logout) | desvincular un companion (`remove-companion-device`) y logout por ban |
| `WWWTriggerAcountRecovery` (credenciales del usuario canónico) | wipe por PIN olvidado (`wipe_*`, `/v2/security`) |
| `#PWD_WA:11` (WhatsApp) | `#PWD_WAFFLE` (Waffle SSO) |
| operaciones de `PasskeyServerApiImpl` (passkeys de cuenta) | `PaymentsPasskey*`, `BrPasskey*` |
| `/v2/passkey_auth` (aserción de login) | `PasskeyRequestChallengeMutation` / `PasskeyVerifyChallengeMutation` (sin call site) |

---

## 14. Baileys (`baron-baileys-v2`)

Comparado con `src/Socket/privacy.js` y `src/Socket/registration.js`.

| Elemento | APK 2.26.41.6 | Baileys | Resultado |
|------|---------------|---------|--------|
| doc_ids de dispositivos de confianza, login, logout, contraseñas, passkeys | assets | mismos números | coincide |
| `accountLogin` / `accountLogout` | `input{phone_number}` / `input{phone_number, enabled_biometric}` | igual | coincide |
| `getTrustedDevices` | `input{device_id}` siempre enviado | `{}` | difiere; comportamiento del servidor sin `device_id` desconocido |
| reason por defecto de `untrustTrustedDevice` | `"REREG"` en la única llamada | `'USER_INITIATED'` | difiere, otros reasons desconocidos |
| operaciones de passkey | variables `credential`, `key_attestation`, `credential_ids`; raíces `xwa2_passkey_*` | ninguna implementada en los archivos leídos | usar las formas del APK |
| `SetPassword` / `CheckPassword` | sin call site | solo doc_ids | sin verificar, no confiar en ello |
| cifrado `#PWD_WA:11` | sección 5.3 | no presente en el árbol `src` leído | implementar según la sección 5.3 |

Por qué un cliente independiente falla en estas rutas (inferred, nada probado): los endpoints de registro esperan los campos de petición protegidos e2e que construye la app (`C45446JsB`); las llamadas de contraseña y recuperación necesitan credenciales de usuario canónico; la aserción de passkey necesita un autenticador de plataforma.

---

## 15. Flujos completos

### 15.1 Verificar un número que ya tiene cuenta

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

### 15.2 Establecer un PIN y un correo de recuperación

```
[Client]  IQ get <2fa/> ───────────────► [Server]  <2fa>[<code/>][<email/>]
[Client]  IQ set <2fa><code>NNNNNN</code><email>x</email></2fa> ──► ok | error(code,text)
[Client]  Fetch2FAEmailStatusJob: IQ get <2fa/> until <email> present
[Client]  IQ get <2fa><code>NNNNNN</code></2fa> ──► <2fa><code/></2fa> = correct   (periodic reminder)
```

### 15.3 Crear una contraseña de cuenta

```
[Client]  canonical credentials present? ── no ─► fail
[Client]  WaPasswordEncryptionKeyQuery ──► public_key (PEM), key_id (1..255)
[Client]  HOZ.A08: AES-GCM + RSA-PKCS1 wrap -> "#PWD_WA:11:<epoch>:<blob>"
[Client]  XfbWaCreatePasswordMutation {data:{encrypted_password}} ──► success
[Client]  (best effort) GetTwofaQuery / SetTwofaMutation {input:{twofa_enabled:true, device_id}}
```

---

## 16. Desconocidos

| Tema | Motivo |
|-------|--------|
| Ciphersuite de OPAQUE (grupo, id tras `VOPRF06-`), layouts de KE1 / KE2 / KE3 y del envelope, variante de AKE | nativo, leído solo como desensamblado de 4 funciones |
| Vínculo de los índices `jvidispatch` del backup cifrado con el código `WESOpaque*` | por forma de argumentos, no por símbolo |
| Número de iteraciones de PBKDF2 para el KSF de OPAQUE | pasado como parámetro; `100000` es el literal que pasan los llamadores Java |
| Si alguna ruta envía una contraseña por OPAQUE para la contraseña de la cuenta | no se encontró tal ruta; no se pueden excluir wrappers ocultos tras el dispatch numérico |
| Respuestas de `XfbWa*`, `AccountLogin`, `AccountLogout`, `UntrustTrustedDevice` | raíz y campos no leídos |
| Operaciones sin call site (2.4) | variables y respuestas desconocidas |
| Campo exacto que lleva el blob `#PWD_WA` en `/v2/register` | derivado del orden del constructor |
| Significado de los campos `login`, `lid` devueltos por `/v2/exist` y `/v2/passkey_auth` | consumidores no trazados |
| Efecto de `wipe_full` / `wipe_offline` en el servidor | el cliente solo muestra texto |
| Si un dispositivo de confianza omite el segundo factor | del lado del servidor; sin lógica de omisión en el cliente |
| Algoritmo del par de claves de recuperación (`N6T.A02`) | no leído |
| Roles de los flags 8877, 31281, 28385 | solo compuertas |
| Tráfico real | solo análisis estático |
