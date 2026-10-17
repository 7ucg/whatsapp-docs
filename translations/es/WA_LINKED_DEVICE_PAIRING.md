<!-- src-sha1: 2c3f9604f03ccc7f3d3160d18810a86e62b8172f -->
# WhatsApp Emparejamiento de dispositivos vinculados — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** lado del dispositivo primario del emparejamiento de companions, flujo QR, flujo de número de teléfono / código de emparejamiento, stanzas `pair-device` y `pair-success`, material de claves, identidad de dispositivo firmada ADV y lista de key-index, lista y límites de dispositivos, desvinculación, errores, comparación con Baileys

---

## 1. Qué es (técnicamente)

Un dispositivo vinculado (companion) es un segundo endpoint de la misma cuenta. El teléfono primario lo autoriza produciendo una identidad firmada ADV (account device verification) sobre la clave de identidad del companion. Todas las afirmaciones son análisis estático del APK descompilado; no se capturó nada en la red. Nivel: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto.

Los nombres ofuscados son específicos de cada build y se volvieron a resolver a partir de strings estables en 2.26.41.6.

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Orquestador de QR/emparejamiento | `C45850K0w` (prefijo de log `CompanionDeviceQrHandler`) | analiza el QR, construye los protos ADV, envía `pair-device` |
| Constructor del IQ `pair-device` | `RunnableC46606KYf` | construye el IQ |
| Helper de solicitud/respuesta de `pair-device` | `KRI` (`devicePairRequest/*`) | envía, reintenta, analiza `device` / `companion-props` / pistas de reintento |
| Enrutador de errores | `C44661Jem` | asigna el código de error del servidor a un callback de UI |
| Parser de la cadena QR | `C45741Jxy` → `C45423Jrn` | payload del QR a datos de emparejamiento |
| Datos de emparejamiento analizados | `C44423JaU` | ref, claves del companion, adv secret, plataforma |
| ADV util | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, key index, timestamp, construcción y firma de la key-index-list |
| Actualizador de key-index-list | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | envía la lista firmada al servidor |
| Verificador ADV | `C24230w2` (`DeviceADVInfoHandler`) | verifica identidades y listas vistas en la red |
| Handler de notificación de lista de dispositivos | clase anónima en `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | notificación `devices` |
| Handler de notificación de link-code | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | notificación id 252 |
| Gestor de link-code (primario) | `KZ3` (código de entrada, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | flujo de código de emparejamiento |
| Util cripto de link-code | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Gestor de dispositivos | `C0XQ` (`companion-device-manager`) | lista, logout |
| Helper de eliminación | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Wrapper de curva Signal | `C38851hm` | proveedor "best" de `org.whispersystems.curve25519` |
| Clases proto ADV | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | ver sección 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `companion-props` en el resultado de `pair-device` |
| Client props | `C43107IrI` | hijo `client-props` |
| Tipo de cuenta/cifrado | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

Existen tres modos de entrada en la UI del primario (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

El mismo APK contiene también el código de registro del rol companion (máquina de estados `C0YS`, logs `companion/registration/*`). Queda fuera del alcance; solo se describen las partes necesarias para explicar qué recibe el primario (sección 9.6).

---

## 2. Rutas de emparejamiento de un vistazo

| Ruta | Disparador en el primario | El primario envía | Secreto que une primario y companion |
|------|--------------------|---------------|----------------------------------------|
| QR | escaneo de `https://wa.me/settings/linked_devices#<payload>` (o `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` del campo 4 del QR |
| Número de teléfono + código | `notification` `link_code_companion_reg` stage `companion_hello`, el usuario escribe el código de 8 caracteres | `primary_hello`, más tarde (tras `companion_finish`) el mismo `pair-device` | `adv secret` derivado de dos resultados X25519 más un valor aleatorio (sección 4.4) |

Ambas rutas convergen en un objeto `C44423JaU` y un IQ `pair-device` (found: `KYB` construye `C44423JaU` a partir del bundle de `companion_finish` con el mismo constructor que usa `C45850K0w.A01` para el QR).

---

## 3. Flujo QR (lado primario)

### 3.1 Payload del QR

`C45741Jxy.A01` elimina el prefijo `https://wa.me/settings/linked_devices#` o `whatsapp://settings/linked_devices#` y decodifica el resto como URL. `A02` divide por `,` (found):

| Idx | Contenido | Codificación | Uso |
|-----|---------|----------|-----|
| 0 | `ref` | string | referencia de emparejamiento; un ref que empiece por `CAPI_` se rechaza (`invalid ref`) |
| 1 | clave pública del companion | base64 | se envía como `pub-key`, salt de la clave del nonce (3.4). Nombre inferred: clave estática Noise (`companion_server_auth_key_pub` en la ruta de código) |
| 2 | clave de identidad del companion | base64, 32 bytes, el parser antepone `0x05` (tipo Curve25519) | firmada por la firma de la cuenta |
| 3 | `adv secret` | base64 | clave HMAC para el wrapper ADV |
| 4 | código de plataforma (opcional) | un carácter | se asigna a un tipo de plataforma; `j` = dispositivo hosted |

- Menos de 3 partes: `qrData/processQR/error/invalid_code parts`. Falta la clave de identidad o el adv secret (QR antiguo de 3 campos): `invalid qr code, missing companion identity key or adv secret` → código local **-9**.
- Tabla de caracteres de plataforma (independiente de `EnumC26221BZl`, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Solo se usa para la comprobación de hosted y para logging (3.2).

### 3.2 Comprobaciones locales antes de enviar nada

| Comprobación | Código | Código local |
|-------|------|------------|
| el QR tiene clave de identidad y adv secret | `C45850K0w.A01` | -9 |
| flag hosted consistente: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| ya hay otro emparejamiento en curso (`kri.A0N`, o el gestor de companion-device está ocupado) | `A04` | -17 |
| timestamp ADV local válido (`C24270w6.A00() != -1`) | `A04` | -8 |
| companion hosted | `A04`: `Hosted pairing is not supported` | -10 |
| se necesita fricción del defense-mode | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (reintento con challenges) |

El emparejamiento hosted está bloqueado en el cliente en este build (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Antes del IQ: limpieza de syncd y key index

1. Si el estado de syncd está sucio (`sync-manager/shouldCleanUpSyncdOnPairing`), la app primero limpia syncd y luego continúa (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (en `RunnableC46617KYr`):
   - sin rawId ni índice almacenados: nuevo rawId aleatorio, índice 1;
   - sin companions vinculados: `rawId + 1`, el índice se queda en 1;
   - con companions: `currentIndex + 1`; en caso de desbordamiento rawId + 1 y se cierra la sesión de todos los dispositivos (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (sección 5.4).

### 3.4 Qué se construye

En `C45850K0w.A00`, con `E` = clave de identidad del companion (32 B, raw), `P` = par de claves de identidad del primario (Curve25519), `S` = adv secret:

| Paso | Operación | Nivel |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | firma de cuenta = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; prefijo `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` se deja vacío: lo añade el companion) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = paso 3 serializado, hmac = HMAC-SHA256(key = S, data = bytes del paso 3), accountType}`; para hosted los datos son `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) de `C24270w6.A01`, firmada por `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | clave de nonce `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, envuelta como hijo `pem` | found (derivación); propósito inferred |
| 7 | `encryption-metadata` opcional (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, de `AuthProofHelper` (cifrado de la contraseña de la cuenta, etiqueta `rsa2048`) | found (estructura); qué demuestra es unknown |
| 8 | `client-props` opcional (`C43107IrI`, sección 3.6) | found |

Detalle del paso 6: el nodo `pem` está etiquetado `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 days`, `key_id=1`, pero su hijo lleva `key.getEncoded()` de la salida HKDF de 32 bytes (`SecretKeySpec` algoritmo `AES-GCM`). La etiqueta y el contenido no coinciden; el motivo es unknown. El uso en el servidor es inferred (el servidor cifra un nonce por dispositivo para el companion; cf. columna `companion_meta_nonce`).

### 3.5 El IQ `pair-device` (primario → servidor)

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <pair-device>
    <ref>…</ref>                                    <!-- QR field 0 -->
    <pub-key>…</pub-key>                            <!-- QR field 1 -->
    <device-identity>ADVSignedDeviceIdentityHMAC</device-identity>
    <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
    <client-props>…</client-props>                  <!-- optional -->
    <pem version="1" algorithm="rsa2048"><pem>…</pem><ttl ts_s="432000"/><key_id>1</key_id></pem>
    <encryption-metadata version="1" algorithm="rsa2048">…</encryption-metadata>   <!-- optional -->
    <companion_qr_origin_source>1|2</companion_qr_origin_source>
    <challenges><supported><friction variant="1"/><passkey-create/></supported>
                <completed>…</completed></challenges>                              <!-- optional -->
  </pair-device>
</iq>
```

Found: todos los nombres de hijos, el valor del atributo `ts` (el timestamp de la key-index-list), timeout **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` es `1` para el valor de entrada 3 y `2` para el valor de entrada 5 (el significado de los enteros de entrada es unknown). El orden exacto de los hijos y la rama de `companion_qr_origin_source` están parcialmente alterados por el decompilador; tratar el orden como no verificado.

### 3.6 `client-props` (`C43107IrI`)

| Campo | Número | Tipo | Se establece cuando |
|-------|--------|------|-----------|
| `isChatDbLidMigrated` | **1** | bool | migración de LID de la BD de chats completada |
| `isSyncdPureLidSession` | **2** | bool | flag syncd pure-LID presente |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | flag de recuperación |
| `isHsThumbnailSyncEnabled` | **4** | bool | flag de miniaturas de history-sync |
| `subscriptionSyncPayload` | **5** | bytes | se construye cuando md sync está habilitado (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | BD de JIDs de bots migrada |

### 3.7 Manejo del resultado (`KRI.CFS`)

Hijos del resultado de éxito (found):

| Hijo | Uso |
|-------|-----|
| `device` attr `jid` | el nuevo `DeviceJid` del companion; el device id **99** se asigna a la entrada de plataforma hosted |
| `companion-props` | proto `DeviceProps` (`C43105IrG`): `os` **1** (string), `version` **2** (message), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (message) |
| `retry-ts` attr `ts` | el servidor pide un timestamp más reciente; la app reintenta (`RunnableC46585KXj`) |
| `retry-after-challenges` | hijos `friction` (attr `variant`, debe ser `1`, `location` opcional "lat,lon") o `passkey-create` (attr `created`) |
| `retry-with-method` | hijos `qr-code` o `shortcake-with-passkeys`; si está presente el segundo, la clave de handoff de 32 bytes (HKDF del adv secret, info `shortcake-passkey-handoff-v1`) se guarda (`PairingHandoffKeyHolder`), condicionado por un abprop |

En caso de éxito la app almacena el registro de dispositivo `CJY` (string base64 aleatorio de 24 bytes, `adv_key_index` = índice actual, `requireFullSync`), guarda el timestamp de la key-index-list como `adv_timestamp_sec` (`C24270w6.A05`) e inicia el estado de history sync (`C8N`).

Fallo de entrega (`Bog`): hasta **3** reintentos, retardo `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s) si el flag de reintento está activo (found); después, callback de error.

---

## 4. Flujo de número de teléfono / código de emparejamiento (lado primario)

### 4.1 Pasos

| # | Dirección | Stanza / acción | Clase |
|---|-----------|-----------------|-------|
| 1 | companion → servidor → primario | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | primario | almacena el hello, muestra notificación push → `CompanionHelloConfirmationActivity` / pantalla de ingreso de código | `C10J`, `C77`, `JYJ` |
| 3 | usuario | escribe el código de 8 caracteres | `LinkedDevicesEnterCodeActivity` |
| 4 | primario → servidor | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (timeout 120000 ms) |
| 5 | servidor → primario | `notification` `stage=companion_finish` | `C10J` → `KYB` case 0 |
| 6 | primario → servidor | IQ `pair-device` (sección 3.5) | `C45850K0w` |
| 7 | otros stages | `refresh_code` (el primario pide refrescar el código, attr `force_manual_refresh`) | `C10J` |

### 4.2 Notificación `companion_hello` (found)

| Hijo | Uso |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | clave X25519 efímera del companion, envuelta con el código (4.3) |
| `companion_server_auth_key_pub` | más tarde se convierte en el `pub-key` de `pair-device` |
| `link_code_pairing_ref` | ref de sesión (string) |
| `companion_platform_id` | string de id de plataforma |
| `companion_platform_display` | nombre para mostrar |
| attr `should_show_push_notification` | `true` → notificación push |

Estado conservado (`C77`/`CE4`, JSON de SharedPrefs `companion_reg_with_link_code_companion_hello_info_json`): ref, id de plataforma, clave envuelta, clave de autenticación del servidor, expiración `now + min(360000, flag 3816 * 1000)` ms. Un hello expirado o ausente → "companion hello is null or expired" (estado de UI 2). Un hello más reciente con un ref distinto cancela el ref anterior (`KRJ.A00(oldRef, "true")`).

### 4.3 Cripto del código y del wrap (found)

| Elemento | Valor |
|------|-------|
| Código | 5 bytes aleatorios → 8 caracteres, 5 bits cada uno, alfabeto `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 símbolos, sin `0 I O U`) (`K1T.A00`, generado por el companion) |
| Código → clave | PBKDF2-HMAC-SHA256, **131072** iteraciones, 256 bits, password = caracteres del código, salt = primeros 32 bytes del blob envuelto (`K1T.A02`) |
| Clave efímera envuelta | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, plaintext = clave pública X25519 de 32 bytes; la longitud debe ser ≥ 48 |
| Respuesta del primario | el primario crea su propio par de claves efímero, envuelve su clave pública del mismo modo (salt nuevo de 32 B, IV de 16 B, mismo código) |

### 4.4 `primary_hello` y `companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

Hijos de la notificación `companion_finish`: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Procesamiento del primario en `KYB` case 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (almacenado en el momento de `primary_hello`).
2. Layout del bundle `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, mínimo 44 bytes.
3. Clave = HKDF-SHA256(salt = salt del bundle, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Comprobaciones: la identidad del primario debe ser igual a la clave de identidad propia; la identidad del companion debe ser igual a `companion_identity_public` de la notificación; de lo contrario se descarta el ref y la UI recibe un estado de error.
6. `adv secret = HKDF-SHA256(salt = 32 zero bytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Clave de handoff = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (también almacenada en `C44423JaU`).
8. `C44423JaU` se construye con `pub-key` = `companion_server_auth_key_pub`, identidad del companion, adv secret → el mismo IQ `pair-device` que en QR.

El ECDH efímero externo existe (es el IKM del HKDF del paso 3). Una nota de un build anterior decía "no ECDH in this stage"; eso es incorrecto para este build.

Marcadores de error en el lado primario: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. Identidad de dispositivo firmada ADV

### 5.1 Campos proto (found, a partir de los strings de layout lite-proto)

| Mensaje | Clase | Campo | Número | Tipo |
|---------|-------|-------|--------|------|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | enum (`EnumC32116E1o`) |
| | | `deviceType` | **5** | enum (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (lo establece el companion) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | packed uint32 |
| | | `accountType` | **5** | enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (solo hosted) |

Los números de campo y los wire types se leen de la message info generada; los nombres coinciden con los mensajes ADV canónicos. Nombres del enum: valores de `EnumC32116E1o` E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Prefijos de firma y algoritmos

| Prefijo | Constante | Datos firmados / con MAC | Firmante | Nivel |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | firma de cuenta: `‖ details ‖ companion identity pub` | clave de identidad del primario | found |
| `06 05` | `A0G` | variante hosted de la firma de cuenta; también antepuesto a los datos del HMAC en hosted | clave de identidad del primario / adv secret | found |
| `06 01` | `A0H` | firma de dispositivo: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | clave de identidad del companion | found (lado de verificación) |
| `06 06` | `A0I` | variante hosted de la firma de dispositivo | clave de identidad del companion | found (lado de verificación) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | clave de identidad del primario | found |
| `06 07` | `A0K` | atestación non-E2EE ("hybrid") (`AeaUtils`), no es un prefijo de key-index-list | clave de identidad del primario | found |

- Primitiva de firma: `C38851hm.A00("best")` carga `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (firma de 64 bytes), `A02` = `calculateAgreement`. Las claves son de 32 bytes con byte de tipo `5`. Es decir, firmas Curve25519 de la librería curve25519 de Signal (estilo XEdDSA, inferred a partir de la librería, no del nombre del algoritmo). La elección de proveedor nativo vs Java se decide en tiempo de ejecución (unknown cuál se usa en un dispositivo dado).
- HMAC: `HmacSHA256` vía `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Key-index list

`C24270w6.A01` construye `ADVKeyIndexList`; `validIndexes` es un conjunto formado por (found): una entrada para el slot primario (valor 0 cuando no está en modo companion; condición de la rama inferred), el `adv_key_index` de cada companion almacenado (`CJY.A07`) y `currentIndex`. `A02` firma `06 02 ‖ details`.

`C24250w4.A00` la envía como:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout 32000 ms. Puerta `A02`: flag **477** distinto de cero, companions presentes (o modo companion), no en modo companion. En caso de fallo se incrementa `adv_key_index_list_update_retry_count`; por encima de **5** la app registra `adv-key-index-list-update … fails for more than 5 times` y cierra la sesión de todos los companions (`C24270w6.A03`). El éxito borra los contadores (`A05`).

### 5.4 Regla del timestamp (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = reloj corregido por NTP, `srv` = hora del servidor. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. Si `last + 1 > now + 86400` el valor es inválido (-1, se registra `getTimestampSec invalid ts`), lo que bloquea el emparejamiento con el código local -8. Monotónico por cuenta (found).

### 5.5 Verificación en la red (`C24230w2`)

Para cualquier identidad de dispositivo que el primario ve (propia y de companions de contactos) comprueba, en orden (found):

1. clave de identidad del primario conocida (almacenada, o `accountSignatureKey` de la lista), si no `no primary key`;
2. la clave de identidad del companion se analiza (`0x05`+32 B), si no `invalid companion public key`;
3. firma de cuenta sobre `prefix ‖ details ‖ companion identity`, si no `fail to verify account signature`;
4. firma de dispositivo sobre `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (hosted `06 06`), si no el dispositivo se rechaza;
5. key-index-list: firma sobre `06 02 ‖ details` con la clave primaria; el `adv timestamp` de la lista debe ser consistente (`advTimestampMismatch`, `advListTimestampInvalid`); un key index entrante que no coincide reinicia el estado local (`incoming key-index not matching local state, resetting`); un índice mayor para el mismo dispositivo ya presente descarta la entrada más antigua (`filterDeviceWithKeyIndexList`).

---

## 6. Lista de dispositivos, registro y límites

### 6.1 Notificación `devices` (el primario la recibe)

`notification` con hijo `add` o `remove` (cualquier otro: `unknown type of device notification`). Atributos e hijos (found): `device_hash`, `device_lid_hash` opcional más `lid`, entradas `device` (jid, key index), `key-index-list` opcional (bytes, attr `ts`, `expected_ts`). Si la notificación lleva el attr `offline`, el usuario se encola para sincronizar más tarde; de lo contrario se ejecuta un job de sync (`SyncDeviceNotificationRunnable`). La lista solo se acepta si su timestamp no es anterior al `adv_timestamp_sec` almacenado (en caso contrario `local ts is larger than notification one`).

### 6.2 Registro de dispositivo almacenado (tabla `devices`, `C1h8`)

| Grupo | Columnas (found) |
|-------|-----------------|
| Identidad | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Tiempo | `last_active`, `login_time`, `logout_time` |
| Sync | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Capacidades | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

Los valores de `platform_type` provienen de `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Límites y flags

| Flag / elemento | Significado | Nivel |
|-------------|---------|------|
| **15550** | entero: máximo de dispositivos vinculados (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` bloquea "link a device"; el escáner de QR recibe el extra `at_device_limit`; `OrbitCompanionLinkActivity` rechaza cuando se alcanza) | found (uso); valor por defecto unknown (abprop entregado por el servidor); existe el campo de métricas `md_linked_devices_max_devices_limit` |
| **3816** | segundos que `companion_hello` sigue siendo válido, con tope de 360 s | found |
| **477** | puerta (distinto de cero) para actualizaciones de key-index-list | found |
| **18193** | añade `friction` (variant 1) a `challenges/supported` anunciados | found (uso); efecto en el servidor unknown |
| **28161** | añade el segundo challenge anunciado (`passkey-create`) | asignación inferred (el decompilador perdió la rama) |
| **29500** | puerta de emparejamiento hosted usada en la comprobación de defense-mode | found (lectura), significado inferred |
| **31019** | añade el attr `exclude_hosted_companion=true` a remove-all por algunos motivos | found |

Si el servidor aplica el límite de forma independiente a la comprobación del cliente es unknown. El primario no tiene en el código leído ningún timeout de inactividad del lado del cliente para companions; la expiración en el servidor de companions inactivos es unknown.

---

## 7. Desvinculación (lado primario)

### 7.1 Un solo dispositivo

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, timeout 32000 ms. El resultado puede llevar el hijo `coex_token` (pasado al handler de coexistencia). El fallo de entrega o un error llama al callback de fallo con código -1 (found).

### 7.2 Todos los dispositivos

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Una lista local vacía hace cortocircuito al callback de éxito. Strings de motivo vistos en el código: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; la lista puede ser más larga, la expresión de origen está truncada).

### 7.3 Disparadores de desvinculación automática (found)

| Disparador | Motivo |
|---------|--------|
| la actualización de la key-index-list falló más de 5 veces | `adv-key-index-list-update`, logout de todos |
| desbordamiento del key index | reinicio `A03` |
| estado ADV inválido / companion desconocido (`KZD` case 43) | `invalid_adv_status` |
| transición de tipo de cuenta hosted ↔ E2EE | expulsa a todos los dispositivos (log de `handleADVMetadata`) |
| el servidor envía la notificación `devices` de tipo `remove` | registro local eliminado (inferred) |
| acción del usuario en la pantalla de dispositivos vinculados / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found para el monitor; ruta de UI inferred) |

La eliminación de la cuenta en su conjunto (`urn:xmpp:whatsapp:account` `remove`) es un IQ distinto y no está relacionada con la desvinculación de companions.

---

## 8. Casos de error

### 8.1 Códigos del servidor manejados por `C44661Jem.A01`

| Código | Callback | UI | Nivel |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | estado "companion too old" | found |
| 404 / 405 / 443 / 445 | `C2w` genérico | asignación de strings `C44648JeY`: 405 y 443 tienen textos dedicados; 404/405/443/445 comparten un título | found (strings por id); significado exacto de 404/443/445 unknown |
| otro | `C2w` genérico | emparejamiento fallido | found |

`InstrumentationAuthActivity` nombra los códigos de resultado 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, y en otro caso `PAIRING_FAILED` (found). La asignación del 405 del servidor al caso consumer/SMB es inferred a partir del id del string.

### 8.2 Códigos locales

| Código | Causa | Solución |
|------|-------|-----|
| -8 | timestamp ADV local inválido (reloj vs último ts almacenado + 1) | corregir la hora del dispositivo; string de UI "invalid device time" |
| -9 | al QR le falta la clave de identidad / adv secret | usar un QR actual |
| -10 | emparejamiento hosted en build consumer | n/a |
| -13 | discrepancia entre plataforma y flag hosted | n/a |
| -17 | otro emparejamiento en curso | esperar; la solicitud vive hasta 32 s |
| -20 | el servidor pidió challenges (`retry-after-challenges`) | completar el challenge de friction / passkey |
| -1 | solicitud de eliminación no enviada o fallida | reintentar |

### 8.3 Fallos del link-code

| Síntoma (log) | Causa |
|------------|-------|
| `companion hello is null or expired` | código escrito tras la expiración (flag 3816, máx. 360 s) |
| `decryption fail` (hello) | código incorrecto (la clave PBKDF2 difiere; AES-CTR no tiene tag, por lo que un código incorrecto da una clave basura que se detecta en pasos posteriores; inferred) |
| `primary identity doesn't match` | el bundle se construyó para otra clave primaria |
| `companion identity doesn't match` | la notificación y el bundle discrepan |
| `invalid-primary-adv-key-length` / `adv public key is 0` | comprobaciones del rol companion sobre la clave efímera del primario |

---

## 9. Distinciones clave

### 9.1 Qué no confundir

| A | B |
|---|---|
| `pair-device` enviado por el **primario** (este reporte) | `pair-device` **recibido** por una app con rol companion (handler `AbstractC40501kw`, id 242, lleva los refs del QR) |
| `ADVSignedDeviceIdentity` (firmado, sin HMAC) | `ADVSignedDeviceIdentityHMAC` (el wrapper enviado en `device-identity`) |
| hijo `device-identity` de `pair-device` (wrapper HMAC) | hijo `device-identity` en stanzas de mensajes salientes (identidad de cuenta adjuntada por un companion; pref `adv_signed_identity`) |
| firma de cuenta (clave primaria, prefijo `06 00`) | firma de dispositivo (clave del companion, prefijo `06 01`) |
| prefijo de key-index-list `06 02` | `06 07` (atestación non-E2EE) |
| `pub-key` del QR / `companion_server_auth_key_pub` | clave de identidad del companion (la que recibe la firma de cuenta) |
| `rawId` (id a nivel de cuenta que cambia al reiniciar) | `keyIndex` (por companion) |
| carácter de plataforma del QR (`EnumC26332BbY`) | `DeviceProps.platformType` en la red (`EnumC25120ArW`), numeración distinta |

### 9.2 Dispositivo hosted

Device id del JID **99** (`device_id should be 99 for hosted device`), marcador de registro/desemparejamiento `hosted_device_pairing`, prefijos de firma `06 05` / `06 06`, `exclude_hosted_companion`. El primario se niega a emparejar un dispositivo hosted en este build (local -10). Todo lo que vaya más allá de estos strings es unknown.

### 9.3 Shortcake

`retry-with-method` puede listar `shortcake-with-passkeys`; la app entonces almacena una clave de handoff y cambia la UI. `ShortcakeJni` expone `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` y `nativeResponderStart/Finish` (found). La transcripción del handshake es nativa y no se descompiló aquí: unknown.

### 9.4 Friction / defense mode

`pair-device` anuncia los challenges soportados y devuelve los `completed` en el reintento. El primario decide localmente exigir friction cuando el defense mode está activo (`C271211x.A0N()`) y el challenge de friction aún no está completado; esta decisión se toma antes del primer IQ (`defense mode friction triggered`). La política del servidor que envía `retry-after-challenges` no es visible (unknown).

### 9.5 Sin atestación del cliente del companion

Nada en el payload de pair-device demuestra qué software ejecuta el companion: `ref`, `pub-key`, clave de identidad, adv secret y carácter de plataforma son autodeclarados por el QR. Lo que las firmas demuestran es que esta cuenta primaria autorizó esa clave de identidad. Cualquier comprobación de "cliente oficial" es del lado del servidor (el veredicto 465 solo se maneja en el cliente).

### 9.6 Código del rol companion en el mismo APK (breve)

| Elemento | Hallazgo |
|------|---------|
| Hijos del IQ `companion_hello` | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; attr `should_show_push_notification` (found, `C0YS`) |
| código | `K1T.A00` base32 de 5 bytes aleatorios (4.3) |
| rotar QR | IQ `pair-device-rotate-qr` con attrs `stage` 0/1/2 y `sentinel` opcional, hijo `ref` |
| IQs md entrantes | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (ids 242, 243, 266, 278, 279) |
| contenido de `pair-success` y respuesta `pair-device-sign` del companion | no trazado en este build: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Comparado con el código fuente local; solo coincidencias y una diferencia que se comprobaron en ambos lados.

| Elemento | APK 2.26.41.6 | `baron-baileys-v2` | Resultado |
|------|---------------|--------------------|--------|
| Payload del QR | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | coincide (4 campos) |
| Derivación del código de emparejamiento | PBKDF2-SHA256 131072 it., alfabeto `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, mismo alfabeto (`crypto.js`, `generics.js`) | coincide |
| Key bundle | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, plaintext identity ‖ identity ‖ random32 | mismo layout (`messages-recv.js`) | coincide |
| adv secret | HKDF(zero salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | coincide |
| Wrapper HMAC | HMAC-SHA256(adv secret, [06 05 para hosted ‖] bytes de ADVSignedDeviceIdentity) | igual (`validate-connection.js`) | coincide |
| Mensajes de firma de cuenta / dispositivo | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | igual | coincide |
| Prefijo hosted de key-index-list | el verificador y el firmante usan `06 02` para toda lista; `06 07` es el prefijo de atestación non-E2EE | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` usado cuando `accountType == HOSTED` (`chats.js`) | **difiere**; el flujo hosted no se ejercita en este build consumer, por lo que el efecto de la diferencia es unknown |

No se hace ninguna afirmación de "por qué falla": un companion Baileys que siga las filas coincidentes es consistente con lo que el primario analiza aquí; la aceptación por parte del servidor no es verificable de forma estática.

---

## 11. Flujos completos

### 11.1 Flujo QR

```
[Companion]  shows QR  https://wa.me/settings/linked_devices#ref,noisePub,identityPub,advSecret[,platform]
     │
     ▼
[Primary]    scan → C45741Jxy.A02 → C45423Jrn → C44423JaU
     │       checks: -9 / -13 / -17 / -8 / -10 ; defense mode → challenges (-20)
     │       incrementCurrentKeyIndex ; ts = C24270w6.A00()
     │       details  = ADVDeviceIdentity{rawId, ts, keyIndex, accountType, deviceType}
     │       accSig   = Curve25519.sign(P.priv, 06 00 ‖ details ‖ companionIdentity)
     │       signed   = ADVSignedDeviceIdentity{details, P.pub, accSig}
     │       wrapper  = ADVSignedDeviceIdentityHMAC{signed, HMAC-SHA256(advSecret, signed)}
     │       list     = ADVSignedKeyIndexList (sig 06 02)
     │       K        = HKDF(salt = noisePub, IKM = advSecret, "Canonical Ent Companion Nonce Encrypt")
     ▼
iq set xmlns=md  <pair-device> ref, pub-key, device-identity, key-index-list ts, client-props, pem, … </pair-device>
     │
     ▼
[WA Server]   (not observed) validates, creates device jid, sends pair-device / pair-success to the companion
     │
     ▼
Result to primary: <device jid/> <companion-props/>   (or retry-ts / retry-after-challenges / retry-with-method / error 465, 496, …)
     │
     ▼
[Primary]    store CJY record, adv_timestamp_sec = list ts, start history sync
     │
     ▼
[Server → Primary]  notification devices add{device_hash, device…, key-index-list ts}  → SyncDeviceNotificationRunnable → verify (5.5)
```

### 11.2 Flujo de código de emparejamiento

```
[Companion]  iq link_code_companion_reg stage=companion_hello
     │         wrapped_ephemeral = salt32 ‖ iv16 ‖ AES-CTR(PBKDF2(code, salt), ephPub)
     ▼
[WA Server]  → notification stage=companion_hello  → [Primary] C10J (id 252)
     │                                               store hello (ttl ≤ 360 s), push notification
     │                                               user types 8-char code
     ▼
[Primary]    unwrap companion eph pub ; make own eph pair ; eph = X25519(...)
     │         iq link_code_companion_reg stage=primary_hello
     │             wrapped_primary_ephemeral_pub, primary_identity_pub, link_code_pairing_ref
     ▼
[Companion]  eph = X25519(...) ; bundle = salt32 ‖ nonce12 ‖ GCM(HKDF(eph, salt), companionId ‖ primaryId ‖ random32)
     │         iq stage=companion_finish
     ▼
[WA Server]  → notification stage=companion_finish → [Primary] KYB
     │            decrypt, check both identities, advSecret = HKDF0(eph ‖ DH(id) ‖ random, "adv_secret")
     ▼
[Primary]    pair-device IQ (same as 11.1, pub-key = companion_server_auth_key_pub)
     ▼
(11.1 continues)
```

### 11.3 Desvinculación

```
[Primary UI / auto trigger]
     │   remove-companion-device jid=… reason=…     (or all="true")
     ▼
iq set xmlns=md  →  [WA Server]  →  result (optional coex_token)
     │
     ▼
[Primary]   remove local record, new key-index-list on next update (iq key-index-list ts)
[Server → other devices]  notification devices remove{…}
```
