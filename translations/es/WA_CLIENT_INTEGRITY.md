<!-- src-sha1: 4ca6293d8bc9da2aebc5db6f104c88b12dce1bd0 -->
# WhatsApp Integridad del Cliente — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** Integridad y atestación del cliente Android — Keystore key attestation ("blacknoise"), Play Integrity (API estándar en Java y API clásica nativa), biblioteca nativa de tokens WASafe, stanzas `integrity_payload` / `keystore_attestation`, parámetro `gpia` del registro, autoverificación de la firma de la app, flag de fuente de instalación, telemetría de root / emulador / cliente modificado (`wam_daily`), qué está condicionado y qué solo se reporta, qué sigue siendo desconocido

---

## 1. Qué es la "integridad del cliente" en esta build

No existe una única compuerta. El cliente produce varias pruebas y señales independientes; todas se crean en el dispositivo y se envían al servidor. No se encontró código del lado del cliente que se niegue a ejecutarse en un cliente modificado, con root o re-firmado. Todas las afirmaciones son análisis estático del APK decompilado (`versionCode 264100600`). Niveles: **found** = leído en el código, **inferred** = deducido, **unknown** = no resoluble de forma estática.

Los nombres ofuscados son por build y se resolvieron de nuevo a partir de strings estables en 2.26.41.6.

| Mecanismo | Produce | Enviado como | Uso en el servidor |
|-----------|----------|---------|-----------|
| Keystore key attestation, tag de log interno `blacknoise` (`C25730yT`) | Cadena de certificados DER de una clave EC de `AndroidKeyStore` con attestation challenge | stanza `<ib><keystore_attestation>`; entrega a nativo en el registro; rutas de passkey y de emparejamiento de companion | unknown (no observable) |
| Play Integrity, API estándar de Java (`C45007Jkc`) | Standard Integrity token (`gpia`) | parámetro HTTP de registro `gpia`; token de emparejamiento de companion ("md-pairing") | unknown |
| Play Integrity, API clásica nativa (`libwhatsapp.so`, `WAJIntegrityGpiaStatusRequest`) | Classic Integrity token vía JNI | `<ib><integrity_payload>` (sink en Java found; vínculo con el productor nativo inferred) | unknown |
| WASafe (`libwasafe.so`, `libwasafedeps.so`) | Blob cifrado tipo ECIES de datos suministrados por el llamador, base64 | sink unknown | unknown |
| Autoverificación de firma de la app (`AbstractC38241gg`, `C27965CCj`) | valor 0/1 | atributo común de WAM **6251** | unknown |
| Flag de fuente de instalación (`CHH`) | booleano de instalador `com.android.vending` | atributos WAM `install_source_official`, **10255** | unknown |
| Flags de estado del dispositivo (`Cdt` → `C0Fp`) | `is_rooted`, `is_genymotion`, `is_monkeyrunner_running`, `is_using_custom_rom`, `is_whatsapp_plus_user` | evento WAM `wam_daily` | unknown |
| Diagnósticos de soporte (`C00L.A0F`) | tag "rted" | strings de contáctanos / reporte de depuración | solo soporte |

No son atestación de integridad, no confundir (ver 11): `com.whatsapp.integrityai` (detección de estafas en el dispositivo), `bizintegritysignals`, UI de baneo WFAC (`com.whatsapp.waffle.wfac`), vinculación de cuentas (`com.whatsapp.waffle`).

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Keystore attestation | `C25730yT` | par de claves, cadena de certificados, firma (alias `A00`/`A01`, generar `A02`, cadena `A03`, firmar `A07`) |
| Enum de modo de atestación | `C02U` | `C02U.A00` = dinámico, `C02U.A01` = estático |
| Runnable emisor del stanza | `RunnableC48591z1` case 3 vía `C41141ly` | envía `keystore_attestation` |
| Handler de conexión | `A01` en el handler de conexión (`smali/X/0Yq`) | programa `sendKeystoreAttestation` |
| Trabajo en el registro | `C25810yb`, `KZ2` case 39, `K49.A0s` | atestación estática hacia nativo, tag `regtime_ka` |
| Pre-calentamiento de companion | `H1K` (atestación), `H1J` (Play Integrity) | cachea cadena / token para el emparejamiento |
| Wrapper de Play Integrity | `C45007Jkc` | prepare + request de la API estándar |
| HTTP de registro | `K49` | agrega `gpia` a los parámetros de la solicitud |
| Puente JNI | `com.whatsapp.wamsys.JniBridge` | `sendAttestationResult`, callbacks `jnidispatch*`, `wsafeplatform_context` |
| Compuerta de firma | `AbstractC38241gg` | ventana de versión + SHA-1 del certificado de firma |
| Verificador de firma | `C27965CCj` | nombre de paquete + SHA-256 del certificado de firma frente a valores embebidos |
| Future de fuente de instalación | `CHH` | `install_source_official` |
| Evento WAM diario | `C0Fp` (`getEventNameForFalco()` = `wam_daily`) | flags del dispositivo |
| Relleno de flags WAM | `Cdt` (smali) | llena los booleanos de `C0Fp` |
| Helpers de root / emulador | `C00L` | `A0F` root, `A0C` emulador, `A0B` ROM personalizada, `A0D` automatización de pruebas |

---

## 2. Keystore key attestation ("blacknoise")

### 2.1 Generación de claves (`C25730yT.A02`)

Todo condicionado por ab-prop **1934** (`A06()`, por defecto `true`).

| Elemento | Valor | Nivel |
|------|-------|------|
| Keystore | `AndroidKeyStore` | found |
| Propósito de la clave | `4` (`PURPOSE_SIGN`), digests `SHA-256`, `SHA-512`, autenticación de usuario no requerida | found |
| Algoritmo | ab-prop **2076**, por defecto `"EC"`; `"RSA"` agrega padding `PKCS1` | found |
| Algoritmo de firma | ab-prop **2075**, por defecto `"SHA256withECDSA"` | found |
| Base del alias | ab-prop **2074**, por defecto `the_well_of_wishes_awaits_in_the_crypt_of_decay`; respaldo hardcodeado `my_personal_mini_pony` cuando la prop es null | found |
| Alias | dinámico: `<base>[_<suffix>]`; estático: `<base>_static[_<suffix>]`; sufijo = UUID aleatorio guardado en las prefs `ka_key_store_dynamic_alias_suffix` / `ka_key_store_static_alias_suffix`, rotado cuando una regeneración encuentra un sufijo existente | found |
| Validez del certificado | ahora + ab-prop **2079** segundos (por defecto 86400) | found |
| Attestation challenge | se fija solo en SDK >= 24 | found |
| Atestación de propiedades del dispositivo | `setDevicePropertiesAttestationIncluded(true)` en SDK >= 31; ante `ProviderException` se reintenta sin ella (log `blacknoise/disbabling device ids att`) | found |

Estructura del attestation challenge (found):

```
challenge = BE64(unix_seconds) ‖ 0x1F ‖ nonce
nonce     = caller-supplied bytes, else SecureRandom(ab-prop 2078 bytes, default 32)
```

### 2.2 Renovación y limitación

| Pref / prop | Significado | Por defecto | Nivel |
|-------------|---------|---------|------|
| `ka_refresh_ts` + ab-prop **2079** | la clave dinámica se recrea cuando es más antigua que esto | 86400 s | found |
| `ka_static_refresh_ts` + ab-prop **4878** | renovación de la clave estática | 600 s | found |
| `ka_retried_ts` + ab-prop **2427** | dinámico: regeneración intentada demasiado pronto -> log `regeneration attempted too soon, waiting` | 600 s | found |
| `A04()` | elimina ambos alias y pone en cero todas las prefs `ka_*` | – | found |

### 2.3 Cadena de certificados (`C25730yT.A03`)

`keyStore.getCertificateChain(alias)`, cada certificado con `getEncoded()` (DER), concatenados en orden inverso (raíz primero, hoja al final) en un solo array de bytes. Una cadena vacía registra `empty list of certificates found`. Las fallas se reportan al error reporter como `attestation-creation`, `attestation-nocertchain`, `attestation-nosign` (found). Los tiempos se registran como `att-gen` / `att-sign` (found).

### 2.4 Firma (`C25730yT.A07`)

`Signature.getInstance(prop 2075)` sobre un payload del llamador con la clave estática. Entrada de clave ausente -> `attestation-nosign` "cannot sign payload, att pair missing". No se encontraron llamadores de `A07` en el código decompilado (posibles huecos de decompilación); dónde se enviaría una firma es unknown.

### 2.5 Cuatro consumidores de la cadena

| # | Disparador | Modo | Nonce | Sink | Nivel |
|---|---------|------|-------|------|------|
| 1 | Servidor conectado (`handleConnected` en el handler de conexión, nombre de job `sendKeystoreAttestation`) | dinámico (`C02U.A00`) | clave pública estática (Noise) del cliente (`C25710yR.A0H()`) | `<ib><keystore_attestation>chain</keystore_attestation></ib>` vía `C10140Tq.A0X(node, 6)` | found |
| 2 | Registro (`K49.A0s`, job `regtime_ka`, runnable `KZ2` case 39) | estático (`C02U.A01`) | clave pública estática del cliente | `JniBridge.jvidispatchIOO(1, ctx, chain)` hacia nativo, con retry/backoff (ab-props **2863** 1000 ms, **2864** 5 intentos); `K49.A0s` espera hasta la ab-prop **4696** (1880 ms) cuando se le pide | found (uso nativo unknown) |
| 3 | Inicio del registro de companion (`C0YS` `startcompanionreg` -> `H1K.A00`) | dinámico | clave pública estática del cliente | cacheado en `H1K` (campo `A02`), renovado por un helper tipo `KeyAttestationLifetimeManager`; condicionado por las ab-props **6430** (por defecto `true`), **7217** (bucket), intervalo **6431** (600000 ms), reintentos **6433**/**6434** | found (caché); consumidor de los bytes cacheados no resuelto: unknown |
| 4 | API de servidor de passkey (`I16` case 18, `PasskeyServerApiImpl`) | dinámico | bytes provistos por el servidor | devuelto al llamador de passkey | found (lo que hace el llamador es unknown) |

Compuerta del stanza para #1: `A06()` y ab-prop **1935** (por defecto `true`), y como máximo una vez por ab-prop **2067** segundos (por defecto 86400), almacenado en la pref `ka_stanza_sent_ts`. Una cadena nula registra `blacknoise: got null attestation chain in custom stanza` y no envía nada (found).

Forma del stanza (found):

```
<ib>
  <keystore_attestation>[binary: DER certs, root first]</keystore_attestation>
</ib>
```

`keystore_attestation` también es un token de diccionario (segundo diccionario, `AbstractC40911lb.A01[0]`), por lo que se codifica como token en la red (found).

Vinculación: como el nonce en #1 a #3 es la propia clave pública estática Noise del cliente, la extensión de challenge de la cadena de certificados lleva la clave de identidad, atando la clave de hardware a la clave estática de la cuenta (inferred a partir de la elección del nonce; verificación del servidor unknown).

---

## 3. Play Integrity

### 3.1 API estándar de Java (`C45007Jkc`)

| Elemento | Valor | Nivel |
|------|-------|------|
| API | `IntegrityManagerFactory.createStandard` -> `StandardIntegrityManager` | found |
| Número de proyecto en la nube | `293955441834` (`PrepareIntegrityTokenRequest.setCloudProjectNumber`) | found |
| Prepare (`A00(callback, tag)`) | etiquetado con tag; se omite si ya existe un proveedor de tokens; se niega sin red; máx. 5 prepares por 60 s (pref `pref_gpia_prepare_call_count_in_last_interval`) | found |
| Request (`A01(callback, nonce, tag)`) | `StandardIntegrityTokenRequest.setRequestHash(nonce)`; falla con 1003 si no hay proveedor | found |
| Códigos de error internos (`JCX`) | 1001 sin red, 1002 demasiadas llamadas prepare, 1003 no preparado, 1004 timeout (`C47238Kk7`), 1005 sin clave estática (`Kmc`) | found |
| Eventos del error reporter (`GKY`) | `ka_at_md_generate_attestation`, `gpia_at_md_prepare`, `gpia_at_md_generate_attestation` | found |

Sitios de llamada de prepare (found): `RegisterPhone` (tag `register_phone`), `VerifyPhoneNumber` (tag `verify_phone`), emparejamiento de companion (tag `md-pairing`, `H1J`), más una ruta de reintento en `C41354Hz3`.

### 3.2 Parámetro HTTP de registro `gpia`

`K49.A0V` agrega un campo al mapa de la solicitud HTTP de registro:

```java
if (!flag(3753)) return;               // default false
nonce = Base64(static_public_key, NO_PADDING|NO_WRAP);   // C47343Kmc case 48
token = request(nonce, tag="reg");     // timeout ab-prop 4263, default 1800
map.put("gpia", token);
```

| Elemento | Valor | Nivel |
|------|-------|------|
| Compuerta | ab-prop **3753**, por defecto `false` | found |
| Nonce | base64 (flags 3) de la clave pública estática del cliente (`C25710yR.A0H()`); clave nula -> error 1005 | found |
| Agregado en | `checkIfExists` (dos rutas de código), `verifySecurityCode` | found |
| Otras solicitudes (solicitud de código, registro final) | `A0V` no se llama allí en el código decompilado | found (ausencia en la decompilación) |
| Métrica de tiempo | `gpia-param-prepare` | found |

El valor por defecto `false` significa que el parámetro solo se envía cuando el servidor habilita la prop 3753. Si el servidor de registro lo exige: unknown.

### 3.3 Token de emparejamiento de companion

`H1J` (condicionado por `A07(...)`, prop **7006** por defecto `false`, intervalo **7007** = 21600000 ms) hace prepare ("md-pairing") e `I16` case 3 solicita un token con nonce = base64(clave pública estática, flags 3), prop de timeout **7010** (1000 ms). Las fallas se registran como `gpia_at_md_prepare` / `gpia_at_md_generate_attestation`. El consumidor del token no está resuelto (unknown).

### 3.4 API clásica nativa e `integrity_payload`

Strings en `libwhatsapp.so` (found): `WAJIntegrityGpiaStatusRequest`, `WAJIntegrityGpiaStatusRequestAttributes`, `_WAJIntegrityTriggerGPIAWithRequestAttributes`, `_WAJIntegritySendResponseOrRetry`, `_WCAAPIGenerateGPIAParamOnMain`, y firmas JNI para `IntegrityManagerFactory.create(Context)`, `IntegrityTokenRequest.Builder` (`setNonce`, `setCloudProjectNumber`), `IntegrityManager.requestIntegrityToken`. Por tanto, el código nativo maneja Play Integrity (solicitud clásica) por sí mismo mediante JNI.

Sink en Java (found):

```java
// JniBridge.jnidispatch... case 3  (callback "sendAttestationResult")
node = <ib><integrity_payload>{string}</integrity_payload></ib>   // C10140Tq.A0X(node, 194)
metric type "safety-net-attestation", result "success"/"failed"
```

El string de tipo de métrica `safety-net-attestation` es una etiqueta heredada; no se usa ninguna API de SafetyNet (ver 10). La afirmación "el `WAJIntegrityGpiaStatusRequest` nativo produce el string `integrity_payload`" es **inferred** a partir de nombres; la cadena de llamadas dentro del código nativo sin símbolos no se rastreó. Qué dispara una solicitud de estado nativa (agenda del cliente vs solicitud del servidor) es unknown.

El nativo lee ab-props mediante `jnidispatchIII(feature, kind)`; IDs mapeados (found): kind 0: 12->13178, 13->13456, 15->22925, 16->24048; kind 1: 13->13455. `jnidispatchO(1)` devuelve el string de ab-prop **10266** (por defecto vacío). El propósito de estas props es unknown.

### 3.5 Otros usuarios de Play Integrity

| Clase | Uso | Nivel |
|-------|-----|------|
| familia `JK4`, `KM0` | SDK de reCAPTCHA Enterprise (`recaptcha.net`) con su propio `StandardIntegrityManager`; el resultado va al parámetro HTTP `recaptcha` (`K49.A0Z`) cuando está presente | found |
| `KLL`, `KLN`, `C42885In8`… | implementación de integridad de Play Core incluida (código de biblioteca) | found |

---

## 4. Biblioteca nativa WASafe

### 4.1 Lado Java

| Hook | Comportamiento | Nivel |
|------|-----------|------|
| `jnidispatchI(4)` | carga `libwasafe.so` (`"wasafe"`), registra `WCAAPIEnsureSafeLibraryLoaded libwasafe.so load failed` ante `UnsatisfiedLinkError` | found |
| `jnidispatchI(5)` | devuelve la pref `runtime_override` de SharedPreferences `wsafeplatform_context`, si no la constante `1090327562` | found |
| Atributo WAM **15611** | la misma constante, escrita como string `1090327562` en los atributos comunes | found |

El significado de `1090327562` es unknown (candidato: valor de runtime / tipo de detección de WASafe, no verificado).

### 4.2 `libwasafe.so` (14480 bytes, arm64, sin símbolos)

Exporta: `WASafeSignalsCreate`, `WASafeSignalsConfigure`, `WASafeSignalsPrepare`, `WASafeSignalsGetBase64EncodedData`, `WASafeSignalsRelease`, `WASafeStatus`. Importa: libc (`stat`, `rand`, `srand`, `gettimeofday`, `malloc`…) y `WASafeDepsCrypto*` de `libwasafedeps.so`.

| Función | Comportamiento decompilado | Nivel |
|----------|---------------------|------|
| `WASafeSignalsConfigure(x)` | almacena `x` (tipo de detección) en un global, limpia un segundo global | found |
| `WASafeSignalsPrepare()` | escribe la constante de estado `0x1092` en un global; ningún otro trabajo | found |
| `WASafeSignalsGetBase64EncodedData()` | pasa los datos/longitud del contexto por cifrado+base64 (`sub_6a00`) y devuelve `{ptr, len}` | found |

Esta build de `libwasafe.so` no contiene recolección de señales: ni strings de root, depurador, hook, emulador o rutas de archivo, y la única importación del sistema de archivos es `stat`. `libwhatsapp.so` también contiene un string `WASafeSignalsStub` y `WAIntegrityPrepareSafeSignals(WASafeDetectionType)` con tags de log `safesignals/prepare` y `safesignals/generate` (found). De dónde provienen los datos que se cifran es unknown.

### 4.3 `libwasafedeps.so`

Exporta `WASafeDepsCryptoInputCreate`, `...SetServerPublicKey`, `...SetData`, `...EncryptBase64`, `...ResultGetData/GetLength/Release`; importa mbedtls (`ctr_drbg`, `entropy`, `gcm_setkey`, `gcm_crypt_and_tag`). Estructura (found a partir de importaciones y nombres): clave efímera aleatoria, secreto compartido con una clave pública del servidor, AES-GCM, base64. La curva exacta y el KDF no se volvieron a decompilar para esta build; una construcción Curve25519 ECDH + AES-GCM es **inferred**. Valor y rotación de la clave pública del servidor: unknown.

---

## 5. Autoverificación de la firma de la app y fuente de instalación

### 5.1 Compuerta (`AbstractC38241gg.A00`)

```java
long vc = versionCode;
if (vc < 264100600 || vc > 264100608) return 0;          // outside window
sha1 = Base64(SHA-1(signatures[0]), 11);
return "OKD31QX-GP7GT780Psqq8xDb15k".equals(sha1) ? 1 : 0;
```

La ventana de versión empieza en el `versionCode` de esta build (264100600). El resultado se cachea en un static.

### 5.2 Verificador (`C27965CCj.A00(pkg, certBytes)`)

| Paso | Comportamiento | Nivel |
|------|-----------|------|
| 1 | Nombre de paquete enmascarado con XOR con una clave de 5 bytes y comparado con dos arrays de bytes embebidos que decodifican a `com.whatsapp` y `com.whatsapp.w4b` | found |
| 2 | Si el paquete no es ninguno de los dos: devuelve `true` de inmediato | found |
| 3 | Si no, SHA-256 de los bytes del certificado, enmascarado con XOR y comparado con dos valores embebidos de 32 bytes; coincidencia -> `false`, no coincidencia -> `true` | found |

La decompilación de este método falló; los pasos se leyeron del volcado de instrucciones.

### 5.3 Consumidor

Dentro de WAM `initializeCommonAttributes` (runnable `RunnableC29340CoR`):

```java
long r = AbstractC38241gg.A00(ctx);          // 1 only when version window + SHA-1 match
if (r == 1) r = verifier(pkg, cert) ? 0 : 1;
common attribute 6251 = r;                   // 1 = both checks passed, 0 = otherwise
```

Así, **6251 = 1** significa "el certificado de firma coincide con los valores embebidos de WhatsApp" (found); 0 significa discrepancia o build fuera de la ventana (found). El valor solo se reporta en telemetría. Nada en el cliente reacciona a él (no se encontró ninguna ruta de código que lea el resultado para bloquear o degradar). Uso en el servidor: unknown.

### 5.4 Fuente de instalación

`getInstallSourceInfo().getInstallingPackageName()` (SDK >= 30, si no `getInstallerPackageName`) comparado con `com.android.vending` (`C18970md`, `RunnableC29340CoR`): almacenado en el future `CHH.A01`. Reportado como atributo WAM **10255** y como `install_source_official` en conjuntos de atributos de logging (`HO4`, `C08650Nr`, `AbstractC35718FdU`). También el campo `install_source` de `C0Fp` (`wam_daily`). Usos separados de la misma comparación seleccionan el instalador del módulo Voltron (`AbstractC12860bs`) (found). El resultado es telemetría más enrutamiento de descarga de módulos; no se encontró ninguna imposición.

---

## 6. Señales de root, emulador y cliente modificado

### 6.1 Flags de dispositivo de `wam_daily`

`C0Fp` es el evento `wam_daily` (`getEventNameForFalco()`); sus campos siguientes se llenan en `Cdt` (smali). Reportados, no impuestos (found).

| Campo | Fuente | Nivel |
|-------|--------|------|
| `is_rooted` | `C00L.A0F(telephony helper)` | found |
| `is_using_custom_rom` | `C00L.A0B()` (strings de kernel/fabricante/display: cyanogen, debug, Darky, XDAndroid, MIUI…) | found |
| `is_whatsapp_plus_user` | `Class.forName("org.acra.ACRA")` tiene éxito (clase ausente de este APK; típicamente incluida por clientes de terceros) | found (verificación); "típicamente incluida" inferred |
| `is_genymotion` | sondeo de paquete para la región `com.genymotion.superuser` en `Cdt`; condición exacta parcialmente rastreada | found (sondeo), lógica inferred |
| `is_monkeyrunner_running` | fuente no resuelta | unknown |
| `google_play_services_available`, `google_play_services_version`, `install_source` | presentes en el mismo evento | found |

### 6.2 Heurística de root `C00L.A0F`

Static cacheado. Verdadero cuando se cumple cualquiera de: `Build.TAGS` contiene `test-keys`; existe `/system/app/Superuser.apk`; ejecutable `su` en `/system/bin/su` o `/system/xbin/su` (`canExecute`), con logging extra `app/dly`; producto/modelo/fabricante tipo emulador (`sdk`) o sin SIM/telefonía (el flag `z` solo se usa para el sufijo del log, found). Helpers relacionados: `A0C` emulador (marca/dispositivo `generic`, `goldfish`, `ranchu`, `google_sdk`, `Emulator`, `Android SDK built for x86`, `Genymotion`), `A0D` automatización de pruebas (propiedad de sistema `fb.running_sapienz`).

### 6.3 Dónde se consume `A0F`

| Consumidor | Uso | Nivel |
|----------|-----|------|
| constructor de reportes de depuración `C10V` | agrega `DC-RTED` (root) y `DC-BACRM` (ROM personalizada) al texto de diagnóstico | found |
| mapa de diagnósticos de contáctanos `C1Z` | clave `diagnostic` = `rted ` (y `nw-wap ` si `org.acra.ACRA` está presente) | found |
| `C28049CFz` (estado del flujo de verificación) | contexto de contáctanos `register-phone-rtd` en la pantalla de número de teléfono | found |
| `Cdt` | `wam_daily.is_rooted` | found |
| `KH2` (crash reporter `lacrima`) | `ExtraDeviceInfoCollector` escribe el flag de root (`test-keys`, `Superuser.apk`, `su` en `PATH`) en los reportes de fallos | found |

Ninguno de estos bloquea el registro ni la mensajería (found: ninguna rama termina el flujo con estos booleanos). Si el servidor pondera los flags de `wam_daily`: unknown.

### 6.4 No encontrado

| Verificación | Resultado |
|-------|--------|
| Strings de Magisk, Xposed (`de.robv`), Substrate, Frida en el código de WhatsApp (`libwhatsapp.so`, Java) | no encontrado |
| `ro.kernel.qemu`, autoverificación de `FLAG_DEBUGGABLE` | no encontrado |
| Lista de paquetes prohibidos para clientes mod con nombre (GB, FM, Plus) | no encontrado |
| Autoverificación de CRC de dex / assets | no encontrada en esta pasada (no buscada exhaustivamente) |
| Verificación de clave respaldada por hardware (`KeyInfo.isInsideSecureHardware`) en el código de atestación propio de WhatsApp | no encontrada (solo en clases de biblioteca `BinderC48420LDc`, `C51962N8y`) |
| `FetchIntegritySignals`, `IntegrityChallengeResponse`, `relax_integrity_constraints_for_bb_wa_tenured_accounts` | no encontrados en ninguna parte del APK (Java, smali, assets, nativo) |
| API `SafetyNet` | no encontrada |

`isDebuggerConnected` aparece solo en el detector de ANR (`SigquitBasedANRDetector`) y en helpers de fallos.

---

## 7. Feature flags y ab-props

| ID | Valor / por defecto | Controla |
|----|-----------------|----------|
| **1934** | `true` | compuerta maestra de blacknoise (`C25730yT.A06`) |
| **1935** | `true` | enviar el stanza `keystore_attestation` tras conectar |
| **2067** | 86400 | segundos mínimos entre envíos del stanza |
| **2074** | `the_well_of_wishes_awaits_in_the_crypt_of_decay` | base del alias de la clave |
| **2075** | `SHA256withECDSA` | algoritmo de firma |
| **2076** | `EC` | algoritmo de la clave |
| **2078** | 32 | longitud del nonce aleatorio |
| **2079** | 86400 | validez del certificado y segundos de renovación dinámica |
| **2427** | 600 | segundos mínimos entre regeneraciones dinámicas |
| **4878** | 600 | segundos de renovación estática |
| **2863** / **2864** | 1000 / 5 | base de backoff en el registro (ms) / intentos |
| **4696** | 1880 | espera del registro por la atestación (ms) |
| **3753** | `false` | parámetro `gpia` del registro |
| **4263** | 1800 | timeout de la solicitud `gpia` |
| **6430** | `true` | pre-calentamiento de atestación de companion (`H1K`) |
| **6431** | 600000 | antigüedad de la caché de atestación de companion (ms) |
| **6433** / **6434** | 5 / 1000 | intentos / timeout del lifetime-manager de atestación de companion |
| **7217** | 1 | módulo del bucket de atestación de companion |
| **7006** | `false` | pre-calentamiento de Play Integrity de companion (`H1J`) |
| **7007** | 21600000 | antigüedad de la caché de token de companion (ms) |
| **7009** / **7010** | 5 / 1000 | intentos / timeout de Play Integrity de companion |
| **10266** | string vacío | string entregado a nativo mediante `jnidispatchO(1)` |
| **26215** | `false` | ruta alternativa de verifySecurityCode en `K49` (no específica de integridad) |

Los valores por defecto son los compilados; el servidor puede sobrescribir las ab-props (found: tabla de props; valores del servidor unknown).

---

## 8. Casos de error

| Síntoma | Causa | Solución / nota |
|---------|-------|-----------|
| Sin stanza `keystore_attestation` | prop 1934 o 1935 en false; enviado en los últimos 2067 s; cadena nula | por diseño |
| Reporte de error `attestation-creation` | falló la generación de la clave (`ProviderException`, sin TEE) | se reintenta más tarde, limitado por 2427 |
| `attestation-nocertchain` | `getCertificateChain` falló o vacío | – |
| `attestation-nosign` | `A07` llamado sin entrada de clave estática | – |
| `blacknoise/regeneration attempted too soon, waiting` | `ka_retried_ts` dentro de 600 s | esperar |
| `blacknoise: not boostrapped for reg` | `C25810yb.A00` false al momento del registro | atestación omitida para ese registro |
| Play Integrity 1001 / 1002 / 1003 / 1004 / 1005 | sin red / > 5 prepare por 60 s / no preparado / timeout / sin clave estática | códigos internos (`JCX`) |
| `gpia` ausente en la solicitud de registro | prop 3753 false o la solicitud falló (resultado nulo puesto como vacío) | ver 3.2 |
| `libwasafe.so load failed` | `UnsatisfiedLinkError` | solo registrado en log |
| Atributo de firma 6251 = 0 | APK re-firmado, certificado distinto, o build fuera de `264100600..264100608` | solo telemetría |

---

## 9. Baileys / clientes de protocolo

| Elemento | Afirmación | Nivel |
|------|-----------|------|
| Verificaciones del lado de la app | Un cliente de protocolo puro nunca ejecuta nada del código anterior | found (por definición) |
| Stanzas `keystore_attestation` / `integrity_payload` | Un cliente que los omite simplemente no los envía; si el servidor rechaza, limita o marca esas cuentas: unknown | unknown |
| Parámetro de registro `gpia` | Opcional por defecto (prop 3753 `false`); imposición del lado del servidor por región/cuenta: unknown | unknown |
| Falsificación de atestación | La cadena debe tener raíz en las raíces de hardware/Google y llevar el challenge; no hay secreto del cliente que copiar, la validación vive en el servidor | inferred |
| Riesgo conocido | La política del servidor depende de datos que este informe no puede observar (comportamiento, antigüedad de la cuenta) | unknown |

Solución: ninguna derivable de forma estática. Enviar valores fabricados no está respaldado por ninguna evidencia encontrada aquí.

---

## 10. Distinciones clave

| No confundir | Hecho |
|----------------|------|
| string de métrica `safety-net-attestation` vs SafetyNet | solo una etiqueta; el payload proviene de Play Integrity; no existe ninguna API de SafetyNet en el código |
| `keystore_attestation` vs `integrity_payload` | stanzas distintos: cadena de certificados DER (bytes) vs string de token de Play Integrity; productores distintos (Java/Keystore vs nativo/Play) |
| `gpia` de Java (API estándar, request hash) vs GPIA clásico nativo | APIs y sinks distintos (parámetro HTTP vs `<ib>`); construcción del nonce de la variante nativa no rastreada |
| Atestación estática vs dinámica | alias estático `..._static` (registro), alias dinámico (tras conectar, companion, passkey) |
| Nonce | clave pública estática del cliente en tres consumidores; bytes del servidor en el consumidor de passkey |
| `blacknoise` vs WASafe | Keystore attestation (Java) vs biblioteca nativa de blob cifrado |
| WASafe vs "signals" | el `libwasafe.so` de esta build no recolecta nada; el nombre implica señales, el código no |
| 6251 vs 10255 | coincidencia de firma vs instalador de Play |
| `is_whatsapp_plus_user` vs una lista de permitidos de clientes mod | un único sondeo reflectivo de clase; no existe ninguna lista de permitidos |
| `integrityai`, `bizintegritysignals` | funciones de seguridad de contenido / business (detección de estafas, UI de señales de business), no atestación del cliente |
| WFAC / `waffle` | UI de baneo y vinculación de cuentas, no un componente de atestación |
| Reportar vs imponer | todos los resultados de root, emulador, firma e instalador encontrados son telemetría o texto de soporte |

---

## 11. Componentes relacionados que no son atestación del cliente

| Componente | Hechos | Nivel |
|-----------|-------|------|
| `com.whatsapp.integrityai` | `IntegrityAiOrchestrator`, `ScamDetectorImpl`, descarga de modelos (`IntegrityAiModelDownloadCoordinator`, nivel de dispositivo), UI opt-in `ScamDetectionSettingsActivity`; tag del almacén de resultados `IntegrityAi/ScamDetectionResultStore`; un clasificador nativo llamado `kaleidoscope` no se re-verificó en esta build | found (estructura); parte nativa unknown |
| `com.whatsapp.bizintegritysignals` | fetcher de GraphQL y manager de señales de integridad de business mostradas en la UI | found |
| `com.whatsapp.waffle.wfac` | UI de decisión de baneo (`WfacBanActivity`, `WfacBanDecisionFragment`, `WfacUnbanDecisionFragment`) | found |
| `com.whatsapp.waffle.accountlinking` y hermanos | vinculación de cuentas, SSO, crossposting, verificación de edad | found |

---

## 12. Flujo de extremo a extremo

```
[Registration screens: RegisterPhone / VerifyPhoneNumber]
    │  C45007Jkc.A00  prepareIntegrityToken (cloud project 293955441834, tag register_phone / verify_phone)
    │  K49.A0s  "regtime_ka": C25730yT.A03(static)  nonce = static pubkey
    │      └── JniBridge.jvidispatchIOO(1, ctx, chain)  ──►  [native wamsys]  (use unknown)
    ▼
[K49 HTTP: exist / verifySecurityCode]
    │  if ab-prop 3753:  gpia = standard-API token, requestHash = b64(static pubkey)
    ▼
[WA registration server]  (validation not observed)

[Connected session]
    │  handleConnected ─► job "sendKeystoreAttestation"
    │  ab-props 1934 && 1935, once per 86400 s
    │  C25730yT.A03(dynamic, nonce = static pubkey) ─ AndroidKeyStore EC key, challenge = ts ‖ 0x1F ‖ nonce
    ▼
<ib><keystore_attestation>DER chain, root first</keystore_attestation></ib>
    ▼
[WA server]  (use unknown)

[Native libwhatsapp]  WAJIntegrityGpiaStatusRequest ─► classic IntegrityManager via JNI   (inferred link)
    │  JniBridge callback sendAttestationResult
    ▼
<ib><integrity_payload>token</integrity_payload></ib>   (node code 194)
    ▼
[WA server]  (use unknown)

[Companion pairing]
    │  C0YS startcompanionreg ─► H1K (chain cache) + H1J (GPIA token, tag md-pairing)
    ▼  consumer of cached bytes/token: unknown

[Telemetry, daily and common attributes]
    │  6251 signature match, 10255 Play installer, 15611 wasafe constant
    │  wam_daily: is_rooted, is_genymotion, is_using_custom_rom, is_whatsapp_plus_user, install_source
    ▼
[WA server]  (use unknown)
```

---

## 13. Desconocidos

| Pregunta | Por qué es desconocido |
|----------|-------------|
| Validación e imposición en el servidor de cualquier token | lado del servidor, no se observó tráfico |
| Qué dispara `WAJIntegrityGpiaStatusRequest` nativo y cómo se construye el nonce | código nativo sin símbolos no rastreado (no hay decompilador para la biblioteca grande aquí) |
| De dónde provienen los datos de entrada de WASafe y qué significa `1090327562` | no se encontró productor en los nativos sin símbolos |
| Uso nativo de los bytes de atestación del momento del registro | solo es visible la entrada JNI (`jvidispatchIOO(1)`) |
| Consumidores de la cadena cacheada de `H1K` y del token de `H1J` | sitios de llamada no resueltos en el código decompilado |
| Significado de la ab-prop 10266 y de los IDs de feature de `jnidispatchIII` | solo valores |
| Fuente de `is_monkeyrunner_running`, condición exacta de `is_genymotion` | no rastreado |
| Llamadores de `C25730yT.A07` (firma) | ninguno encontrado; posibles huecos de decompilación |
| Si existe alguna imposición para los flags de telemetría | no se encontró rama en el cliente; servidor unknown |
