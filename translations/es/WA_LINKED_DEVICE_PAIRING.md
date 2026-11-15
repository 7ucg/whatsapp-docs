<!-- src-sha1: 6458e557973884f0b2c8c175f4607447365f03a6 -->
# WhatsApp Vinculación de Dispositivo Enlazado — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** lado del dispositivo primario de la vinculación de companion, flujo de QR, flujo de número de teléfono/código de pareo, stanzas `pair-device` y `pair-success`, material de clave, identidad de dispositivo firmada ADV y lista de índice de clave, lista y límites de dispositivos, desvinculación, errores, comparación con Baileys

---

## 1. Qué es (técnicamente)

Un dispositivo enlazado (companion) es un segundo endpoint de la misma cuenta. El teléfono primario lo autoriza produciendo una identidad firmada ADV (account device verification) sobre la clave de identidad del companion. Todas las afirmaciones son análisis estático de la APK decompilada; nada se capturó en el cable. Nivel: **found** = leído en código, **inferred** = deducido del código, **unknown** = no resuelto.

Los nombres obfuscados son por build y se re-resolvieron a partir de strings estables en 2.26.41.6.

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Orquestador QR/pareo | `C45850K0w` (prefijo de log `CompanionDeviceQrHandler`) | parsea el QR, construye protos ADV, envía `pair-device` |
| Constructor del IQ `pair-device` | `RunnableC46606KYf` | construye el IQ |
| Ayudante de solicitud/respuesta de `pair-device` | `KRI` (`devicePairRequest/*`) | enviar, reintentar, parsear `device` / `companion-props` / pistas de reintento |
| Enrutador de error | `C44661Jem` | mapea el código de error del servidor al callback de UI |
| Parser de string QR | `C45741Jxy` → `C45423Jrn` | payload de QR a datos de pareo |
| Datos de pareo parseados | `C44423JaU` | ref, claves del companion, secreto adv, plataforma |
| Utilidad ADV | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, índice de clave, marca de tiempo, construcción y firma de lista de índice de clave |
| Actualizador de lista de índice de clave | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | empuja la lista firmada al servidor |
| Verificador ADV | `C24230w2` (`DeviceADVInfoHandler`) | verifica identidades y listas vistas en el cable |
| Manejador de notificación de lista de dispositivos | clase anónima en `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | notificación `devices` |
| Manejador de notificación de código de enlace | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | notificación id 252 |
| Gestor de código de enlace (primario) | `KZ3` (código de entrada, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | flujo de código de pareo |
| Utilidad cripto de código de enlace | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Gestor de dispositivo | `C0XQ` (`companion-device-manager`) | lista, logout |
| Ayudante de eliminación | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Wrapper de curva Signal | `C38851hm` | proveedor "best" de `org.whispersystems.curve25519` |
| Clases proto ADV | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | ver sección 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `companion-props` en el resultado de `pair-device` |
| Props del cliente | `C43107IrI` | hijo `client-props` |
| Tipo de cuenta/cifrado | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

Existen tres modos de entrada en la UI primaria (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

La misma APK también contiene el código de registro del rol companion (máquina de estados `C0YS`, logs `companion/registration/*`). Está fuera de alcance; solo se describen las partes necesarias para explicar lo que recibe el primario (sección 9.6).

---

## 2. Rutas de pareo de un vistazo

| Ruta | Disparador en el primario | El primario envía | Secreto que vincula primario y companion |
|------|--------------------|---------------|----------------------------------------|
| QR | escaneo de `https://wa.me/settings/linked_devices#<payload>` (o `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` del campo 4 del QR |
| Número de teléfono + código | `notification` `link_code_companion_reg` etapa `companion_hello`, el usuario escribe un código de 8 caracteres | `primary_hello`, luego (tras `companion_finish`) el mismo `pair-device` | `adv secret` derivado de dos resultados X25519 más un aleatorio (sección 4.4) |

Ambas rutas convergen en un objeto `C44423JaU` y un IQ `pair-device` (found: `KYB` construye `C44423JaU` desde el bundle de `companion_finish` con el mismo constructor `C45850K0w.A01` que usa para QR).

---

## 3. Flujo QR (lado primario)

### 3.1 Payload de QR

`C45741Jxy.A01` elimina el prefijo `https://wa.me/settings/linked_devices#` o `whatsapp://settings/linked_devices#` y decodifica URL el resto. `A02` divide por `,` (found):

| Idx | Contenido | Codificación | Uso |
|-----|---------|----------|-----|
| 0 | `ref` | string | referencia de pareo; una ref que empieza con `CAPI_` se rechaza (`invalid ref`) |
| 1 | clave pública del companion | base64 | enviada como `pub-key`, salt para la clave de nonce (3.4). Nombre inferred: clave estática Noise (`companion_server_auth_key_pub` en la ruta de código) |
| 2 | clave de identidad del companion | base64, 32 bytes, el parser antepone `0x05` (tipo Curve25519) | firmada por la firma de cuenta |
| 3 | `adv secret` | base64 | clave HMAC para el wrapper ADV |
| 4 | código de plataforma (opcional) | un carácter | mapea a un tipo de plataforma; `j` = dispositivo hosted |

- Menos de 3 partes: `qrData/processQR/error/invalid_code parts`. Clave de identidad o adv secret faltantes (QR antiguo de 3 campos): `invalid qr code, missing companion identity key or adv secret` → código local **-9**.
- Tabla de carácter de plataforma (independiente de `EnumC26221BZl`, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Solo se usa para el chequeo de hosted y logging (3.2).

### 3.2 Chequeos locales antes de enviar nada

| Chequeo | Código | Código local |
|-------|------|------------|
| el QR tiene clave de identidad y adv secret | `C45850K0w.A01` | -9 |
| flag de hosted consistente: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| otro pareo ya corriendo (`kri.A0N`, o el gestor de dispositivo companion ocupado) | `A04` | -17 |
| marca de tiempo ADV local válida (`C24270w6.A00() != -1`) | `A04` | -8 |
| companion hosted | `A04`: `Hosted pairing is not supported` | -10 |
| se necesita fricción de modo defensivo | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (reintentar con desafíos) |

El pareo hosted está bloqueado del lado cliente en este build (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Antes del IQ: limpieza de syncd e índice de clave

1. Si el estado de syncd está sucio (`sync-manager/shouldCleanUpSyncdOnPairing`), la app primero limpia syncd, luego continúa (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (en `RunnableC46617KYr`):
   - sin rawId o índice almacenado: nuevo rawId aleatorio, índice 1;
   - sin companions vinculados: `rawId + 1`, el índice se queda en 1;
   - companions existen: `currentIndex + 1`; en overflow rawId + 1 y todos los dispositivos se desconectan (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (sección 5.4).

### 3.4 Qué se construye

En `C45850K0w.A00`, con `E` = clave de identidad del companion (32 B, cruda), `P` = par de claves de identidad primaria (Curve25519), `S` = adv secret:

| Paso | Operación | Nivel |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | firma de cuenta = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; prefijo `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` queda vacío: el companion lo añade) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = serialized step 3, hmac = HMAC-SHA256(key = S, data = step 3 bytes), accountType}`; para hosted los datos son `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) de `C24270w6.A01`, firmado por `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | clave de nonce `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, envuelta como hijo `pem` | found (derivación); propósito inferred |
| 7 | `encryption-metadata` opcional (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, de `AuthProofHelper` (cifrado de contraseña de cuenta, etiqueta `rsa2048`) | found (estructura); qué prueba es unknown |
| 8 | `client-props` opcional (`C43107IrI`, sección 3.6) | found |

Detalle del paso 6: el nodo `pem` lleva la etiqueta `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 días`, `key_id=1`, pero su hijo lleva `key.getEncoded()` de la salida HKDF de 32 bytes (`SecretKeySpec` algoritmo `AES-GCM`). La etiqueta y el contenido no coinciden; por qué es unknown. El uso del servidor es inferred (el servidor cifra un nonce por dispositivo al companion; cf. columna `companion_meta_nonce`).

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

Found: todos los nombres de hijo, el valor del atributo `ts` (la marca de tiempo de la lista de índice de clave), timeout **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` es `1` para el valor de entrada 3 y `2` para el valor de entrada 5 (el significado de los ints de entrada es unknown). El orden exacto de hijos y la rama de `companion_qr_origin_source` están parcialmente dañados por el decompilador; tratar el orden como no verificado.

### 3.6 `client-props` (`C43107IrI`)

| Campo | Número | Tipo | Fijado cuando |
|-------|--------|------|----------|
| `isChatDbLidMigrated` | **1** | bool | migración de LID de la BD de chat completada |
| `isSyncdPureLidSession` | **2** | bool | flag de sesión LID pura de syncd presente |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | flag de recuperación |
| `isHsThumbnailSyncEnabled` | **4** | bool | flag de miniatura de sincronización de historial |
| `subscriptionSyncPayload` | **5** | bytes | construido cuando la sincronización md está activada (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | JID de bot migrado en la BD |

### 3.7 Manejo del resultado (`KRI.CFS`)

Hijos de resultado exitoso (found):

| Hijo | Uso |
|-------|-----|
| atributo `jid` de `device` | el nuevo `DeviceJid` del companion; el id de dispositivo **99** se mapea a la entrada de plataforma hosted |
| `companion-props` | proto `DeviceProps` (`C43105IrG`): `os` **1** (string), `version` **2** (mensaje), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (mensaje) |
| atributo `ts` de `retry-ts` | el servidor pide una marca de tiempo más nueva; la app reintenta (`RunnableC46585KXj`) |
| `retry-after-challenges` | hijos `friction` (atributo `variant`, debe ser `1`, opcional `location` "lat,lon") o `passkey-create` (atributo `created`) |
| `retry-with-method` | hijos `qr-code` o `shortcake-with-passkeys`; si el segundo está presente, la clave de traspaso de 32 bytes (HKDF del adv secret, info `shortcake-passkey-handoff-v1`) se guarda (`PairingHandoffKeyHolder`), controlado por un abprop |

Con éxito la app almacena el registro de dispositivo `CJY` (string base64 aleatorio de 24 bytes, `adv_key_index` = índice actual, `requireFullSync`), guarda la marca de tiempo de la lista de índice de clave como `adv_timestamp_sec` (`C24270w6.A05`), e inicia el estado de sincronización de historial (`C8N`).

Fallo de entrega (`Bog`): hasta **3** reintentos, retraso `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s) si el flag de reintento está activado (found); luego callback de error.

---

## 4. Flujo de número de teléfono / código de pareo (lado primario)

### 4.1 Pasos

| # | Dirección | Stanza / acción | Clase |
|---|-----------|-----------------|-------|
| 1 | companion → servidor → primario | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | primario | almacena el hello, muestra notificación push → `CompanionHelloConfirmationActivity` / pantalla de entrada de código | `C10J`, `C77`, `JYJ` |
| 3 | usuario | escribe el código de 8 caracteres | `LinkedDevicesEnterCodeActivity` |
| 4 | primario → servidor | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (timeout 120000 ms) |
| 5 | servidor → primario | `notification` `stage=companion_finish` | `C10J` → `KYB` caso 0 |
| 6 | primario → servidor | IQ `pair-device` (sección 3.5) | `C45850K0w` |
| 7 | otras etapas | `refresh_code` (el primario pide refresco de código, atributo `force_manual_refresh`) | `C10J` |

### 4.2 Notificación `companion_hello` (found)

| Hijo | Uso |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | clave efímera X25519 del companion, envuelta con el código (4.3) |
| `companion_server_auth_key_pub` | más tarde se convierte en el `pub-key` en `pair-device` |
| `link_code_pairing_ref` | ref de sesión (string) |
| `companion_platform_id` | string de id de plataforma |
| `companion_platform_display` | nombre visible |
| atributo `should_show_push_notification` | `true` → notificación push |

Estado guardado (`C77`/`CE4`, JSON de SharedPrefs `companion_reg_with_link_code_companion_hello_info_json`): ref, id de plataforma, clave envuelta, clave de auth del servidor, expiración `now + min(360000, flag 3816 * 1000)` ms. Hello expirado o ausente → "companion hello is null or expired" (estado de UI 2). Un hello más nuevo con una ref distinta cancela la ref anterior (`KRJ.A00(oldRef, "true")`).

### 4.3 Código y cripto de envoltura (found)

| Ítem | Valor |
|------|------|
| Código | 5 bytes aleatorios → 8 caracteres, 5 bits cada uno, alfabeto `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 símbolos, sin `0 I O U`) (`K1T.A00`, generado por el companion) |
| Código → clave | PBKDF2-HMAC-SHA256, **131072** iteraciones, 256 bits, contraseña = caracteres del código, salt = primeros 32 bytes del blob envuelto (`K1T.A02`) |
| Clave efímera envuelta | `[salt 32 ‖ IV 16 ‖ ciphertext AES-256-CTR]`, texto plano = clave pública X25519 de 32 bytes; la longitud debe ser ≥ 48 |
| Respuesta del primario | el primario hace su propio par de clave efímera, envuelve su clave pública del mismo modo (salt fresco de 32 B, IV de 16 B, mismo código) |

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

Hijos de la notificación `companion_finish`: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Procesamiento primario en `KYB` caso 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (almacenado en el momento de `primary_hello`).
2. Disposición del bundle `[salt 32 ‖ nonce 12 ‖ ciphertext+tag AES-256-GCM]`, mínimo 44 bytes.
3. Clave = HKDF-SHA256(salt = salt del bundle, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Texto plano = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Chequeos: la identidad primaria debe igualar la propia clave de identidad; la identidad del companion debe igualar `companion_identity_public` de la notificación; de otro modo la ref se descarta y la UI recibe un estado de error.
6. `adv secret = HKDF-SHA256(salt = 32 bytes cero, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Clave de traspaso = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (también almacenada en `C44423JaU`).
8. `C44423JaU` se construye con `pub-key` = `companion_server_auth_key_pub`, identidad del companion, adv secret → mismo IQ `pair-device` que QR.

El ECDH efímero externo existe (es el IKM de HKDF del paso 3). Una nota de un build anterior decía "sin ECDH en esta etapa"; eso es incorrecto para este build.

Marcadores de error del lado primario: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. Identidad de dispositivo firmada ADV

### 5.1 Campos del proto (found, de los strings de disposición del lite-proto)

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
| | | `deviceSignature` | **4** | bytes (fijado por el companion) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | uint32 empaquetado |
| | | `accountType` | **5** | enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (solo hosted) |

Los números de campo y los tipos de cable se leen de la información de mensaje generada; los nombres coinciden con los mensajes ADV canónicos. Nombres de enum: `EnumC32116E1o` valores E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Prefijos de firma y algoritmos

| Prefijo | Constante | Datos firmados/MACeados | Firmante | Nivel |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | firma de cuenta: `‖ details ‖ companion identity pub` | clave de identidad primaria | found |
| `06 05` | `A0G` | variante hosted de la firma de cuenta; también se antepone a los datos del HMAC para hosted | clave de identidad primaria / adv secret | found |
| `06 01` | `A0H` | firma de dispositivo: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | clave de identidad del companion | found (lado verificación) |
| `06 06` | `A0I` | variante hosted de la firma de dispositivo | clave de identidad del companion | found (lado verificación) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | clave de identidad primaria | found |
| `06 07` | `A0K` | atestación no-E2EE ("hybrid") (`AeaUtils`), no un prefijo de lista de índice de clave | clave de identidad primaria | found |

- Primitiva de firma: `C38851hm.A00("best")` carga `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (firma de 64 bytes), `A02` = `calculateAgreement`. Las claves son de 32 bytes con byte de tipo `5`. Así que firmas Curve25519 de la biblioteca curve25519 de Signal (estilo XEdDSA, inferido de la biblioteca, no del nombre del algoritmo). La elección de proveedor nativo vs. Java se decide en runtime (unknown cuál se usa en un dispositivo dado).
- HMAC: `HmacSHA256` vía `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Lista de índice de clave

`C24270w6.A01` construye `ADVKeyIndexList`; `validIndexes` es un conjunto compuesto de (found): una entrada para el slot primario (valor 0 cuando no está en modo companion; condición de rama inferred), el `adv_key_index` de cada companion almacenado (`CJY.A07`), y `currentIndex`. `A02` firma `06 02 ‖ details`.

`C24250w4.A00` lo empuja como:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout 32000 ms. Compuerta `A02`: flag **477** no-cero, companions presentes (o modo companion), no en modo companion. En caso de fallo `adv_key_index_list_update_retry_count` se incrementa; por encima de **5** la app registra `adv-key-index-list-update … fails for more than 5 times` y desconecta todos los companions (`C24270w6.A03`). El éxito limpia los contadores (`A05`).

### 5.4 Regla de marca de tiempo (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = reloj corregido por NTP, `srv` = hora del servidor. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. Si `last + 1 > now + 86400` el valor es inválido (-1, registrado `getTimestampSec invalid ts`), lo cual bloquea el pareo con código local -8. Monótono por cuenta (found).

### 5.5 Verificación en el cable (`C24230w2`)

Para cualquier identidad de dispositivo que el primario ve (propios y companions de contactos) se verifica, en orden (found):

1. clave de identidad primaria conocida (almacenada, o `accountSignatureKey` de la lista), de otro modo `no primary key`;
2. la clave de identidad del companion parsea (`0x05`+32 B), de otro modo `invalid companion public key`;
3. firma de cuenta sobre `prefix ‖ details ‖ companion identity`, de otro modo `fail to verify account signature`;
4. firma de dispositivo sobre `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (hosted `06 06`), de otro modo el dispositivo se rechaza;
5. lista de índice de clave: firma sobre `06 02 ‖ details` con la clave primaria; `adv timestamp` de la lista debe ser consistente (`advTimestampMismatch`, `advListTimestampInvalid`); un índice de clave entrante que no coincide resetea el estado local (`incoming key-index not matching local state, resetting`); un índice mayor para el mismo dispositivo ya presente descarta la entrada más antigua (`filterDeviceWithKeyIndexList`).

---

## 6. Lista de dispositivos, registro y límites

### 6.1 Notificación `devices` (el primario recibe)

`notification` con hijo `add` o `remove` (cualquier otra cosa: `unknown type of device notification`). Atributos e hijos (found): `device_hash`, opcional `device_lid_hash` más `lid`, entradas `device` (jid, índice de clave), opcional `key-index-list` (bytes, atributo `ts`, `expected_ts`). Si la notificación lleva el atributo `offline` el usuario se encola para sincronización posterior; de otro modo corre un job de sincronización (`SyncDeviceNotificationRunnable`). La lista solo se acepta si su marca de tiempo no es más antigua que el `adv_timestamp_sec` almacenado (`local ts is larger than notification one` de otro modo).

### 6.2 Registro de dispositivo almacenado (tabla `devices`, `C1h8`)

| Grupo | Columnas (found) |
|-------|-----------------|
| Identidad | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Tiempo | `last_active`, `login_time`, `logout_time` |
| Sincronización | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Capacidad | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

Los valores de `platform_type` vienen de `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Límites y flags

| Flag / ítem | Significado | Nivel |
|-------------|---------|------|
| **15550** | entero: máximo de dispositivos enlazados (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` bloquea "enlazar un dispositivo"; el escáner QR recibe `at_device_limit` extra; `OrbitCompanionLinkActivity` rechaza al alcanzarlo) | found (uso); valor por defecto unknown (abprop entregado por servidor); existe el campo de métrica `md_linked_devices_max_devices_limit` |
| **3816** | segundos que el `companion_hello` permanece válido, con tope en 360 s | found |
| **477** | compuerta (no-cero) para actualizaciones de lista de índice de clave | found |
| **18193** | añade `friction` (variante 1) a `challenges/supported` anunciado | found (uso); efecto en el servidor unknown |
| **28161** | añade el segundo desafío anunciado (`passkey-create`) | mapeo inferred (el decompilador perdió la rama) |
| **29500** | compuerta de pareo-hosted usada en el chequeo de modo defensivo | found (lectura), significado inferred |
| **31019** | añade el atributo `exclude_hosted_companion=true` al remove-all para algunas razones | found |

Si el servidor aplica el límite independientemente del chequeo del cliente es unknown. El primario no tiene ningún timeout de inactividad del lado cliente para companions en el código leído aquí; la expiración del lado servidor de companions inactivos es unknown.

---

## 7. Desvinculación (lado primario)

### 7.1 Dispositivo único

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, timeout 32000 ms. El resultado puede llevar el hijo `coex_token` (pasado al manejador de coexistencia). El fallo de entrega o error llama al callback de fallo con código -1 (found).

### 7.2 Todos los dispositivos

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Una lista local vacía corta directo al callback de éxito. Strings de razón vistos en código: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; la lista puede ser más larga, la expresión fuente está truncada).

### 7.3 Disparadores automáticos de desvinculación (found)

| Disparador | Razón |
|---------|-------|
| actualización de lista de índice de clave falló más de 5 veces | `adv-key-index-list-update`, desconecta todos |
| overflow de índice de clave | reset de `A03` |
| estado ADV inválido / companion desconocido (`KZD` caso 43) | `invalid_adv_status` |
| transición de tipo de cuenta hosted ↔ E2EE | expulsa todos los dispositivos (log `handleADVMetadata`) |
| el servidor envía notificación `devices` tipo `remove` | registro local eliminado (inferred) |
| acción de usuario en la pantalla de dispositivos enlazados / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found para el monitor; ruta de UI inferred) |

La eliminación de cuenta en su totalidad (`urn:xmpp:whatsapp:account` `remove`) es un IQ distinto y no relacionado con la desvinculación de companion.

---

## 8. Casos de error

### 8.1 Códigos del servidor manejados por `C44661Jem.A01`

| Código | Callback | UI | Nivel |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | estado "companion too old" | found |
| 404 / 405 / 443 / 445 | `C2w` genérico | mapeo de string `C44648JeY`: 405 y 443 tienen textos dedicados; 404/405/443/445 comparten un título | found (strings por id); significado exacto de 404/443/445 unknown |
| otro | `C2w` genérico | pair failed | found |

`InstrumentationAuthActivity` nombra los códigos de resultado 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, de otro modo `PAIRING_FAILED` (found). El mapeo del 405 del servidor al caso consumer/SMB es inferred del id de string.

### 8.2 Códigos locales

| Código | Causa | Arreglo |
|------|-------|-----|
| -8 | marca de tiempo ADV local inválida (reloj vs. última ts almacenada + 1) | corregir la hora del dispositivo; string de UI "invalid device time" |
| -9 | QR sin clave de identidad / adv secret | usar un QR actual |
| -10 | pareo hosted en build consumer | n/a |
| -13 | desajuste entre plataforma y flag hosted | n/a |
| -17 | otro pareo corriendo | esperar; la request vive hasta 32 s |
| -20 | el servidor pidió desafíos (`retry-after-challenges`) | completar el desafío de fricción/passkey |
| -1 | request de eliminación no enviada o fallida | reintentar |

### 8.3 Fallos de código de enlace

| Síntoma (log) | Causa |
|---------------|-------|
| `companion hello is null or expired` | código escrito tras la expiración (flag 3816, máx. 360 s) |
| `decryption fail` (hello) | código incorrecto (la clave PBKDF2 difiere; AES-CTR no tiene tag, así que un código incorrecto da una clave basura, capturada en pasos posteriores; inferred) |
| `primary identity doesn't match` | el bundle se construyó para otra clave primaria |
| `companion identity doesn't match` | la notificación y el bundle no coinciden |
| `invalid-primary-adv-key-length` / `adv public key is 0` | chequeos de rol-companion en la clave efímera primaria |

---

## 9. Distinciones clave

### 9.1 No confundir

| A | B |
|---|---|
| `pair-device` enviado por el **primario** (este informe) | `pair-device` **recibido** por una app en rol companion (manejador `AbstractC40501kw`, id 242, lleva refs para el QR) |
| `ADVSignedDeviceIdentity` (firmado, sin HMAC) | `ADVSignedDeviceIdentityHMAC` (el wrapper enviado en `device-identity`) |
| hijo `device-identity` de `pair-device` (wrapper HMAC) | hijo `device-identity` en stanzas de mensaje salientes (identidad de cuenta adjuntada por un companion; pref `adv_signed_identity`) |
| firma de cuenta (clave primaria, prefijo `06 00`) | firma de dispositivo (clave del companion, prefijo `06 01`) |
| prefijo de lista de índice de clave `06 02` | `06 07` (atestación no-E2EE) |
| `pub-key` del QR / `companion_server_auth_key_pub` | clave de identidad del companion (la que recibe la firma de cuenta) |
| `rawId` (id de toda la cuenta que cambia en un reset) | `keyIndex` (por companion) |
| carácter de plataforma del QR (`EnumC26332BbY`) | `DeviceProps.platformType` del cable (`EnumC25120ArW`), numeración distinta |

### 9.2 Dispositivo hosted

Id de dispositivo del JID **99** (`device_id should be 99 for hosted device`), marcador de registro/desvinculación `hosted_device_pairing`, prefijos de firma `06 05` / `06 06`, `exclude_hosted_companion`. El primario se niega a parear un dispositivo hosted en este build (local -10). Todo más allá de estos strings es unknown.

### 9.3 Shortcake

`retry-with-method` puede listar `shortcake-with-passkeys`; la app entonces almacena una clave de traspaso y cambia la UI. `ShortcakeJni` expone `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` y `nativeResponderStart/Finish` (found). El transcript del handshake es nativo y no fue decompilado aquí: unknown.

#### 9.3a Vinculación silenciosa — vinculación de companion tethered/periférico + migración de época (nuevo en 2.26.45.10, found)

Un **cuarto** mecanismo de pareo, más acotado que los tres anteriores (ADV/QR clásico, pair-code/CRSC, dispositivo hosted): vinculación silenciosa de **companions tethered/periféricos** — wearables y gafas inteligentes, `DeviceProps.platformType` `WEAR_OS` / `AR_WRIST` / `AR_DEVICE` / `SMARTGLASSES`. Paquete `com.whatsapp.instrumentation.product.silentlinking` (`SilentLinkingNativeRegistration`, `SilentLinkingSessionManager$Session`).

**"Silencioso" significa sin escaneo de QR, no sin interacción del usuario.** Los strings de telemetría (found) muestran un flujo de confirmación de código corto: `"code displayed to user"` → `"user confirmed code on primary"` → `"companion registration start"`. El periférico muestra un código corto y el usuario lo confirma en el teléfono — el mismo modelo de presencia de usuario que el flujo de pair-code (§4), solo sin la imagen de QR. El punto de entrada es la UI de upsell de wearable post-llamada (`PostCallWearableUpsellBottomSheet`, `com.whatsapp.calling.wearableupsell`) que alimenta `SilentLinkingVerificationActivity` (`android:exported="false"`, solo interno, sin deep link). El disparador es solo UI del cliente: no se encontró ningún punto de entrada de `AlarmManager`/`WorkManager`/push del servidor en ninguna de las dos clases, y no aparece ninguna lógica de `unlink`/`unpair`/"dispositivo existente" en ninguna parte de ellas — esto establece un enlace, no elimina uno silenciosamente.

`SilentLinkingNativeRegistration` arrienda un slot de registro del canal lateral CRSC v2/v3 existente (`CompanionRegOverSideChannelV2Manager`/`V3Manager`, misma infraestructura que §4) para transportar el registro de identidad resultante. El intercambio de clave del companion real es una familia de protobuf separada, previamente no documentada:

**Familia de envelope RPC Shortcake** (found, nombres/números de campo de smali, no decompilado independientemente a Java):

| Clase | Rol |
|-------|-----|
| `LX/R9f` | Envelope `oneof` de nivel superior: `protocolVersion`(1), `bootstrapAndHello`(2), `finishAndReady`(3), `peripheralAck`(4), `postCommitProofEnvelope`(5), `readinessRequestEnvelope`(6), `readinessResponseEnvelope`(7), `exactCleanupRequest`(8), `exactCleanupReceipt`(9) |
| `LX/RAN` | Bootstrap&Hello: `linkId`(1), `setupAttemptId`(2), `epochId`(3), `purpose`(4), `hnSignPub`(5), `hnEpoch1EphPub`(6, ECDH efímero clásico), `hnMlkemPub`(7, clave pública ML-KEM-768), `protocolVersion`(8), `selectedCapabilities`(9), `migrationContextHash`(10), `hnDeviceSerial`(11) |
| `LX/RA1` | Envelope envuelto en ciphertext Signal: `signalCiphertext`(1), `signalMessageType`(2), `peripheralHello`(3), `signalRequestId`(4), `companionAdvFingerprint`(5), `primarySignalPeerFingerprint`(6) — vincula el handshake a la propia huella de identidad ADV del companion (§5) |
| `LX/RAW` | Segundo envelope `oneof`, lado de migración de época: `rpcRequest`(1), `rpcResponse`(2), `primaryReady`(3), `peripheralAck`(4), `rotationControl`(5), `requestStatus`(6), `migrationPostCommitProof`(7), `migrationStatusRequest`(8), `migrationStatusResponse`(9), `migrationProbeRequest`(10), `migrationProbeResponse`(11) |
| `LX/RUe` | Enum `PERIPHERAL_PROPS_PLATFORM_{UNKNOWN,IOS,ANDROID}` — el propio OS del periférico |

`RAN.hnEpoch1EphPub` (clásico) junto a `RAN.hnMlkemPub` (ML-KEM-768) confirma un **intercambio de clave híbrido ECDH clásico + post-cuántico**, no solo PQ. Este es el **primer mecanismo cripto post-cuántico documentado en este informe**: ML-KEM-768 (FIPS 203 / Kyber-768), corrido a través del `ShortcakeJni` nativo (liboqs `OQS_KEM_ml_kem_768`, envuelto por `KEMPublicKey`/`KEMSecretKey` de libsignal — encontrado por decompilación nativa en una pasada separada, ver `research/2.26.36.1/shortcake-kem-native.md` del brain). Este schema del lado Java es el enmarcado del transcript que el análisis nativo solo había dejado unknown; el handshake Responder-Start/Finish a nivel de byte en sí mismo permanece solo nativo y unknown.

**Etiquetas de contexto HKDF** (found, strings literales en `LX/SdB`, KDF = HMAC-SHA256 / HKDF-SHA256, misma primitiva que el KDF de envoltura de link-code en §4.3): `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_V1`, `WA_TETHERED_EPOCH1_HN_KEY_POP_V1`, `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_HASH_V1`, `WA_TETHERED_EPOCH1_PRIMARY_FINISH_V1`, `WA_TETHERED_EPOCH1_WA_KEY_POP_V1`, `WA_TETHERED_EPOCH1_HYBRID_KX_V1`, `WA_TETHERED_LINK_IDENTITY_CONTEXT_V1`. ("HN" = el lado primario/teléfono; no expandido en ningún lugar del árbol, probablemente "Host/Home Network".)

**Rotación/migración de época (strings found, rol inferred).** `LX/TIR` lleva un vocabulario extenso de error de migración (`"Invalid migration frame version"`, `"Migration epoch mismatch"`, `"Migration shadow serial mismatch"`, `migration_shadow`, etc.), combinado con `RAN.epochId` y los campos de rotación/sonda-de-migración/estado/prueba-post-commit de `RAW`. Leído en conjunto, esto es un **protocolo de rotación de época de clave en segundo plano para un enlace tethered ya establecido** — `SilentLinkingSessionManager$Session` re-invocando periódicamente `SilentLinkingNativeRegistration` para rotar las claves Shortcake bajo un nuevo `epochId`, con sonda/estado/promoción/replay y una ruta de rollback de registro "shadow". Esto es narrativa inferred sobre strings/campos found; no es un mecanismo de recuperación para una sesión companion clásica perdida ni una desvinculación empujada por el servidor. La condición de disparo concreta para un ciclo de rotación, y el transporte de cable exacto para `R9f`/`RAW` (payload de canal lateral CRSC vs. un stanza/IQ dedicado), son unknown.

**Cero relevancia para Baileys/velowa.** Controlado detrás de la cripto nativa `ShortcakeJni` y una activity interna (`exported="false"`) alcanzable solo desde la UI dentro de la app, acotado enteramente a la categoría propia de companion wearable/gafas inteligentes de WhatsApp. No toca el pareo clásico de companion ADV/CRSC (§2-§4, lo que implementa un cliente multi-dispositivo de terceros), y no se encontró ningún mecanismo por el cual desvincularía o re-vincularía silenciosamente un companion Web/Desktop.

### 9.4 Fricción / modo defensivo

`pair-device` anuncia los desafíos soportados y devuelve los `completed` en el reintento. El primario decide localmente requerir fricción cuando el modo defensivo está activado (`C271211x.A0N()`) y el desafío de fricción aún no se ha completado; esta decisión se toma antes del primer IQ (`defense mode friction triggered`). La política del lado servidor que envía `retry-after-challenges` no es visible (unknown).

### 9.5 Sin atestación de cliente del companion

Nada en el payload de pair-device prueba qué software corre el companion: `ref`, `pub-key`, clave de identidad, adv secret y carácter de plataforma son auto-declarados por el QR. Lo que las firmas prueban es que esta cuenta primaria autorizó esa clave de identidad. Cualquier chequeo de "cliente oficial" es del lado servidor (el veredicto 465 solo se maneja del lado cliente).

### 9.6 Código de rol companion en la misma APK (breve)

| Ítem | Hallazgo |
|------|---------|
| Hijos del IQ `companion_hello` | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; atributo `should_show_push_notification` (found, `C0YS`) |
| código | `K1T.A00` base32 de 5 bytes aleatorios (4.3) |
| rotar QR | IQ `pair-device-rotate-qr` con atributos `stage` 0/1/2 y opcional `sentinel`, hijo `ref` |
| IQs md entrantes | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (ids 242, 243, 266, 278, 279) |
| contenido de `pair-success` y respuesta `pair-device-sign` del companion | no rastreado en este build: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Comparado contra el código fuente local; solo coincidencias y una diferencia que se verificaron en ambos lados.

| Ítem | APK 2.26.41.6 | `baron-baileys-v2` | Resultado |
|------|---------------|--------------------|--------|
| Payload de QR | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | coincide (4 campos) |
| Derivación de pair-code | PBKDF2-SHA256 131072 it., alfabeto `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, mismo alfabeto (`crypto.js`, `generics.js`) | coincide |
| Bundle de clave | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, texto plano identidad ‖ identidad ‖ random32 | misma disposición (`messages-recv.js`) | coincide |
| adv secret | HKDF(salt cero, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | coincide |
| Wrapper HMAC | HMAC-SHA256(adv secret, [06 05 para hosted ‖] bytes de ADVSignedDeviceIdentity) | igual (`validate-connection.js`) | coincide |
| Mensajes de firma de cuenta/dispositivo | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | igual | coincide |
| Prefijo de lista de índice de clave hosted | el verificador y el firmante usan `06 02` para cada lista; `06 07` es el prefijo de atestación no-E2EE | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` usado cuando `accountType == HOSTED` (`chats.js`) | **difiere**; el flujo hosted no se ejercita en este build consumer, así que el efecto de la diferencia es unknown |

No se hace ninguna afirmación de "por qué falla": un companion de Baileys que sigue las filas coincidentes es consistente con lo que el primario parsea aquí; la aceptación por el servidor no es verificable estáticamente.

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

### 11.2 Flujo de código de pareo

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
