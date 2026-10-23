<!-- src-sha1: 95a792ca8e841aadc06a8e3fae785590574c4eba -->
# WhatsApp Transporte Noise — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** Transporte de chat en Android (chatd): endpoints y secuencia de conexión, enrutamiento edge, framing TCP, handshake Noise XX / IK / PQ, verificaciones de la cadena de certificados, ClientPayload (UserAgent, DevicePairingData, connect type / reason), cifrado de transporte y contadores, codificación binaria de nodos, resultado de login y códigos de fallo, keepalive, backoff de reconexión, stream:error, feature flags, transportes relacionados (Tigon HTTP, DistribGW, canal Tigon Noise, MQTT), comparación con Baileys

---

## 1. Qué es (técnicamente)

chatd es la única conexión de larga duración que transporta cada stanza (mensajes, recibos, IQ, presencia, notificaciones). En Android es un socket TCP simple (no WebSocket) que ejecuta un handshake Noise y después frames AES-GCM con prefijo de longitud, cada uno con un nodo codificado en binario. Todas las afirmaciones provienen del análisis estático del APK decompilado; no se capturó nada en la red. Niveles: **found** = leído en el código, **inferred** = deducido, **unknown** = no resuelto. Los nombres ofuscados son específicos de cada build y se volvieron a resolver en 2.26.41.6.

| Capa | Nombre en 2.26.41.6 | Función |
|------|----------------|------|
| Hilo de conexión | `HandlerThreadC12340b0` (log tag `ConnectionThread`) | connect, handshake, login, bucle de lectura, disconnect |
| Secuencia de conexión / DNS | `C37151de` (estados), `C37031dS` (`A0G` avanza, `A0D` fábrica de sockets), `C36881dC`, `AbstractC47101wK` (tabla fija host a IP), `C36821d6` (IPs de respaldo) | qué host / puerto / proxy sigue |
| Driver del handshake | `C38791hg` (logs `NoiseSocket/*`) | bytes de intro, ClientHello, ServerHello, verificación de certificados, ClientFinish |
| Estado Noise | `C38921hv` (+ `C38941hx` hash, `C38981i2` AES-GCM, `AbstractC38961i0` HKDF), `C40331kf` (claves de transporte + contadores) | Java puro |
| E/S de frames, códec de nodos | `C38891hs` / `C38901ht`; `C40411kn` (codificador), `C24610wf` (decodificador), `AbstractC40911lb` (diccionario) | framing, XML binario |
| Protos | `C39211ii`, `C39161id`, `C39231ik`, `C39241il` (handshake); `C24843Amz`, `C24842Amy`, `C24841Amx`, `C25757B9r`, `BC0` (certs); `C38001fP`, `C38051fp`, `C38661hS` (payload) | mensajes de red |
| Confianza, PQ | `AbstractC44011qk` (raíz fijada); `C38811hi`, `AbstractC38821hj`, `AbstractC38831hk`, `C38761hd` (config PQ, claves estáticas del servidor) | identidad del servidor, híbrido ML-KEM-512 |
| Constructor del payload | contribuidores en `AbstractC43901qZ` recopilados por `C37991fK` | ClientPayload |
| Keepalive, timers, reconexión | `C14U` (`ClientPingManager`), `C9EN` (IQ de ping), `HandlerC21850s9`, `C11380Yq` (`MessageHandler`), `C0X9` (backoff) | ping, timeouts, reintento |
| Control entrante | `C40581l4` (`<ib>`), `C40601l6` / `C37961fH.A1B` (`stream:error`) | avisos del servidor |

Puntos que determinan el resto del informe:

- La máquina de estados Noise, HKDF, AES-GCM y el códec de frames son **Java**. Solo Curve25519 (`org.whispersystems.curve25519`, `OpportunisticCurve25519Provider`, nativo con respaldo en Java) y las llamadas ML-KEM (`KEMKeyPair.generateNative`, `KEMSecretKey.decapsulateNative`) son nativos. No hay una implementación nativa de chatd que revertir (found).
- El encabezado de intro es la constante `WA 06 03` en este build (sección 3.1). El entero de versión de protocolo que recibe `C38791hg` está fijado en 6 en su único punto de llamada, por lo que la rama de certificado plano de la versión 5 es inalcanzable en la práctica (found; alcanzabilidad inferred a partir del único punto de llamada con constante).
- `devicePairingData` solo lo envía una conexión sin user JID, lo cual `ConnectionThread` permite únicamente en el registro de companion. No es un artefacto del registro del teléfono primario en este build (sección 6.4).
- Las stanzas salientes en la ruta principal de envío se comprimen con DEFLATE (flags `3`), no solo las entrantes (sección 8.1).

---

## 2. Endpoints y secuencia de conexión

### 2.1 Hosts y puertos (found)

| Host | Dónde | Notas |
|------|-------|-------|
| `g.whatsapp.net` | `C37151de` pasos 5, 9; `C36881dC.A01` (IPs fijas) | host de chat principal |
| `g-fallback.whatsapp.net` | pasos 13, 14 | segundo host |
| `e1` ... `e16.whatsapp.net` | `C37151de.A0F` (16 entradas), pasos 7 y 11 | `ConnectionSequence/getEdgeHost`; elección aleatoria, o el host guardado en el historial |
| tabla de IPs fijas | `AbstractC47101wK.A00`, pasos 6 y 10 | mapea host a lista de IPs, cubre los hosts `eN` y `g.whatsapp.net` |
| lista `<ib><fbip>` | `C40581l4` a `C36821d6.A02` | IPs separadas por comas, persistidas por el gestor de respaldo (entrada de los pasos 2 / 8, inferred) |
| proxy de usuario / SOCKS | paso 12, `C48201yM` | `java.net.Proxy.Type.SOCKS`, timeout de conexión 30000 ms |

Puertos: 443 y 5222 (elección aleatoria por intento, `C37151de.A00`; el constructor además realiza un sorteo que ordena los puertos de los pasos 3 y 4), y 80 para los pasos `:80`. El puerto de la última conexión exitosa se reutiliza cuando el flag **33512** está activo (found).

### 2.2 Estados de la secuencia (found, `C37151de.A02`, avance en `C37031dS.A0G`)

| Paso | Destino |
|------|--------|
| 0 | inicio, elige el primer paso aplicable |
| 1 | `InetSocketAddress` de depuración / override (terminal) |
| 2 | entradas de endpoint suministradas por el servidor con el bit `A04` activo (lista `A0A`), una por una; cada entrada lleva su propio bit TLS `A05` |
| 3, 4 | string de host configurado `A07` en los dos puertos (443 / 5222 en orden aleatorio) |
| 5 | `g.whatsapp.net` en 443 (flag **20801**) o un 443 / 5222 aleatorio |
| 8 | entradas suministradas por el servidor sin el bit `A04` (lista `A09`); el orden de las ramas decompiladas no está claro |
| 9 | `g.whatsapp.net:80` |
| 15 | HISTORY: reintentar el paso / host / puerto guardado por el último éxito (se inserta tras el 9 cuando el paso de historial es válido y el flag **22916** está desactivado) |
| 13, 14 | `g-fallback.whatsapp.net` en 443 / 5222, luego `:80` |
| 6, 10 | IP fija para `g.whatsapp.net`, luego `:80` |
| 7, 11 | host edge aleatorio `eN.whatsapp.net`, luego `:80` |
| 12 | proxy de usuario (terminal) |
| 16 | agotado |

Orden tras el paso 9 (found): 9, [15], 13, 14, 6, 10, 7, 11, 16. El último éxito se guarda en las preferencias `last_successful_connection_step`, `_host`, `_port` (found, `C37031dS.A00`). Los pasos 2 a 4 registran `Skipping sequence ... due to active proxy` mientras hay una config de servicio SOCKS activa y el flag **23630** está desactivado (semántica de omisión inferred).

### 2.3 Socket (found, `C37031dS.A0D`)

| Aspecto | Valor |
|--------|-------|
| Socket | TCP simple; Happy Eyeballs cuando existen direcciones IPv4 e IPv6 (`ConnectionSocketFactory/try_connect/using-happyEyeball`) |
| Envoltura TLS | el bit de config `A07` selecciona un `SSLSocketFactory`; se define por entrada suministrada por el servidor (`A05`), para el paso 1 en el puerto 443 y para hosts edge (paso 7) en el puerto 443. El paso 5 (`g.whatsapp.net`) se crea con el bit desactivado |
| Timeout del socket | 30000 ms establecido mediante `CeF(30000)` (semántica inferred: timeout de lectura) |
| TCP keepalive | `configureTcpKeepalive`: cuando el flag **7831** está activo y el socket lo soporta, se habilita keepalive y se aplican tres enteros de los flags **7832** (por defecto 2), **7833** (por defecto 10), **7834** (por defecto 10) (inactividad / intervalo / cantidad por inferencia) |
| Buffering de salida | cuando el flag **33751** está activo, el escritor se envuelve en un `BufferedOutputStream` para que los bytes de intro y el ClientHello salgan en una sola escritura (found) |

Si los endpoints envueltos en TLS llevan los mismos bytes Noise dentro de TLS es inferred a partir de la ruta de código (`C38791hg` solo recibe streams); existe una métrica llamada `chatd_non_secure_tls_wrapper_resumption` en una lib nativa.

### 2.4 Resolución DNS (found)

`DNSResolutionMethod` se informa en `ClientPayload.dnsSource` (sección 6.5): `SYSTEM`, `GOOGLE`, `HARDCODED`, `OVERRIDE`, `FALLBACK`, `MNS`, `MNS_SECONDARY`, `SOCKS_PROXY`. El flag **13545** (string; valores `secondary`, `hardcoded`, `none` reconocidos por `C37151de.A01`) ajusta la cadena de resolvers. Las respuestas en caché de búsquedas anteriores se usan hasta su expiración antes de una nueva búsqueda (`C36881dC.A03`).

---

## 3. Framing

### 3.1 Bytes antes del primer frame (found, `C38791hg`)

```
[ 'E' 'D' 00 01 | len24 | routing_info ]     only when routing_info is non-empty
[ 'W' 'A' 06 03 ]                             always
[ len24 | HandshakeMessage{clientHello} ]     first frame
```

- Encabezado edge: magic `45 44 00 01` (`C38791hg.A0B`), longitud del blob de 3 bytes big-endian, luego los bytes de `routing_info` (preferencia, base64 sin padding ni saltos de línea; guardada por `C38801hh.A00`, máximo 256 bytes: "The routing info should be smaller than 256 bytes."). Crudo en el socket, fuera de la transcripción Noise.
- Intro: `57 41 06 03` = "WA", protocolo 6, diccionario 3 (`C38791hg.A04`); también el prólogo Noise (4.2). La rama else devuelve `57 41 05 03`, pero el constructor fija la versión en 6.

### 3.2 Estructura del frame (found)

Cada frame es una longitud de 3 bytes big-endian (`AbstractC38721hZ.A04` / `A00`; las escrituras deben ser menores que 2^24, de lo contrario `data too large to write`) seguida del cuerpo: protobuf de handshake durante el handshake, texto cifrado AES-GCM después.

Lector (`C38891hs`): exactamente 3 bytes de longitud, luego el cuerpo. Al leer el ServerHello, tres bytes de longitud iguales al ASCII `GOA` (`47 4F 41`, `C38891hs.A01`) lanzan `X.1sn` (log `socket/goaway`); la ruta de lectura posterior al handshake (`C24610wf.Be0`) no tiene esa verificación. Los frames descifrados vacíos se omiten; un frame descifrado de 1 byte lanza `header only frame received`. Una stanza que supere el límite de tamaño opcional (`InterfaceC40421ko.AqJ`) lanza `C31990DyW` al codificar.

### 3.3 Mensajes de handshake (found, números de campo de las clases protobuf)

| Mensaje (clase) | Campos (número en negrita) |
|-----------------|-------------------------|
| `HandshakeMessage` (`C39211ii`) | clientHello **2**, serverHello **3**, clientFinish **4** |
| `ClientHello` (`C39161id`) | ephemeral **1**, static **2**, payload **3**, useExtended **4**, extendedCiphertext **5**, paddedBytes **6**, sendServerHelloPaddedBytes **7**, simulateXxkemFs **8**, pqMode **9**, extendedEphemeral **10** |
| `ServerHello` (`C39231ik`) | ephemeral **1**, static **2**, payload **3**, extendedStatic **4**, paddingBytes **5**, extendedCiphertext **6** |
| `ClientFinish` (`C39241il`) | static **1**, payload **2**, extendedCiphertext **3**, paddedBytes **4**, simulateXxkemFs **5** |

Setters vistos en el driver: el ClientHello XX completo define `ephemeral` (+ `pqMode` en las variantes PQ); el ClientHello de reanudación define `ephemeral`, `static`, `payload`, `extendedCiphertext`, `extendedEphemeral`, `pqMode`; ClientFinish define `static`, `payload`, `extendedCiphertext`. Los campos de padding y simulate están definidos, pero no se encontró ningún setter en el driver (uso unknown).

---

## 4. Handshake Noise

### 4.1 Nombres de patrón (found, campos estáticos de `C38921hv`)

| Constante | Nombre | Se usa cuando |
|----------|------|-----------|
| `A07` | `Noise_XX_25519_AESGCM_SHA256` (relleno con NUL hasta 32 bytes) | handshake completo, PQ none |
| `A0H` | `Noise_IK_25519_AESGCM_SHA256` (relleno hasta 32) | reanudación con static del servidor en caché, PQ none |
| `A06` | `Noise_XXfallback_25519_AESGCM_SHA256` | IK rechazado por el servidor (4.4) |
| `A0E`, `A0C`, `A08` | `Noise_XXkem_`, `Noise_XXkem-FS_`, `Noise_XXkemEph_` + `25519_MLKEM512_AESGCM_SHA256` | completo, PQ activo |
| `A0F`, `A0D`, `A0G` | `Noise_IKkem+`, `Noise_IKkem-FS+`, `Noise_IKkem2+` + `X25519+MLKEM512+AESGCM256+SHA256` | reanudación, PQ activo |
| `A09`, `A0B`, `A0A` | `Noise_XXkemfallback_`, `Noise_XXkem-FSfallback_`, `Noise_XXkemEphfallback_` + `25519_MLKEM512_AESGCM_SHA256` | fallbacks PQ |

Un nombre de más de 32 bytes se hashea con SHA-256; de lo contrario el valor relleno de 32 bytes es el hash inicial (found, constructor de `C38921hv`).

Configuración PQ (`NoisePQConfig`): modo `NONE` / `ENABLE` / `ENFORCE` (flag **20161**, int: 1 enable, 2 a 4 enforce, otro valor none); variante `IKKEM`, `IKKEM_FS`, `XXKEM_EPH_IKKEM2`, `XXKEM_EPH_ONLY` (flag **34536**, string, por defecto `IKKEM`). Handshake completo: el modo PQ `NONE` usa `A07`; en otro caso la variante `IKKEM_FS` selecciona `A0C`, `XXKEM_EPH_ONLY` y `XXKEM_EPH_IKKEM2` seleccionan `A08`, `IKKEM` selecciona `A0E` (found en el constructor de `C38791hg`). Los nombres `IKkem*` van con la ruta de reanudación; su mapeo exacto de variantes no se trazó.

### 4.2 Estado simétrico (found, `C38921hv`)

```
h  = name (padded, or SHA256(name) if > 32 bytes)         // C38941hx.A00 = name
ck = h                                                    // A02
h  = SHA256(h || prologue)                                // prologue = WA 06 03
mixHash(d):  h = SHA256(h || d)
mixKey(dh):  okm = HKDF-SHA256(salt = ck, ikm = dh, info = none, 64)
             ck  = okm[0:32] ; k = AES-256-GCM key okm[32:64] ; n = 0
encrypt(p):  c = AES-GCM(k, iv = 00000000 || n_be64, aad = h, p) ; n++ ; mixHash(c)
decrypt(c):  p = AES-GCM(k, iv = 00000000 || n_be64, aad = h, c) ; n++ ; mixHash(c)
             (no key yet: encrypt / decrypt pass through and only mixHash)
split():     okm = HKDF-SHA256(salt = ck, ikm = empty, info = none, 64)
             sendKey = okm[0:32] ; recvKey = okm[32:64]
```

HKDF está escrito a mano (`AbstractC38961i0`): extract = `HMAC(key = salt, data = ikm)`, expand con un contador de un byte. IV: 12 bytes, los primeros 4 en cero, los últimos 8 el contador big-endian (`AbstractC38721hZ.A02`). Tag de 128 bits (GCM estilo BouncyCastle `C39061iT`). DH es Curve25519 `calculateAgreement` mediante `C38851hm.A00("best")`.

### 4.3 Secuencia XX completa (found)

| # | Dirección | Contenido | Operaciones de estado |
|---|-----------|---------|------------------|
| 1 | C a S | `ClientHello{ephemeral}` (+ `pqMode` en variantes PQ) | `mixHash(e_c)` |
| 2 | S a C | `ServerHello{ephemeral, static, payload}` | `mixHash(e_s)`; `mixKey(DH(e_c, e_s))`; `s_s = decrypt(static)`; `mixKey(DH(e_c, s_s))`; `cert = decrypt(payload)` |
| 3 | local | verificación de certificados (sección 5) | la clave del cert debe ser igual a `s_s` |
| 4 | C a S | `ClientFinish{static, payload}` | `static = encrypt(s_c)`; `mixKey(DH(s_c, e_s))`; `payload = encrypt(ClientPayload)` |
| 5 | local | split | `sendKey`, `recvKey`, ambos contadores en 0 |

El orden en `C38791hg.A03` (smali) coincide con la transcripción XX estándar. La static del cliente `s_c` y la efímera provienen de pares de claves `C38711hY`; la static la suministra `C38771he.A01` (clave Noise persistente del cliente, "authKey" en los logs de desconexión). Que sea igual a la clave subida en el registro es inferred.

### 4.4 Reanudación (IK) y fallback (found estructura, detalle de pasos inferred)

Cuando existen claves static del servidor en caché (`C38771he.A00` no nulo, `C38761hd`) el driver registra `NoiseSocket/handshakeStart mode=... rs=...` y ejecuta `handshakeResume`: la clave pública static del servidor en caché se incorpora por hash al estado (`C38921hv.A06`), el ClientHello lleva la efímera, la static cifrada del cliente y el `ClientPayload` cifrado en un solo mensaje (sección 3.3). Si el servidor responde con una clave static, el log es `handshakeResume server hello has static key, falling back` y `C38791hg` lanza `X.1t8` con el ServerHello, lo que selecciona los nombres `Noise_XXfallback_*`. La transcripción exacta del fallback es inferred a partir del modificador de fallback estándar de Noise. Las claves static del servidor se persisten tras un login exitoso cuando cambian (`A1m`: clave clásica mediante `Ce3`, clave PQ mediante `Ce2`).

### 4.5 Material post-cuántico (found como presente; detalle de red parcialmente unknown)

- KEM: ML-KEM-512 (string de algoritmo `MLKEM512`, `C38791hg.A0C`). TLV de la clave pública PQ del servidor: tipo `0x02`, longitud 800; encabezado TLV tipo `0x01` que lleva el nombre del algoritmo; TLV del texto cifrado FS tipo `0x04`, longitud 768 (a partir de los strings de error `Expected TLV PK type 0x02`, `length 800`, `Expected TLV header type 0x01`, `Expected FS ciphertext length 768`).
- Encapsulación (`C38921hv.A07`): `KEMPublicKey.A00()` produce texto cifrado + secreto compartido; el texto cifrado pasa por `mixHash`, el secreto compartido por `mixKey`. Decapsulación: `KEMSecretKey.decapsulateNative`.
- Entrega: `<success static_pq_key="base64">` se lee solo cuando el modo PQ no es `NONE` y la variante es `IKKEM_FS` (`A18`); sin ella el log es `handshake missing serverStaticPQ forcing full handshake` (`C38791hg.A01`).

El ancho del campo de longitud del TLV y la ubicación exacta dentro de `ServerHello.payload` no están decodificados. Los nativos ML-KEM provienen de las clases KEM de Signal; no se identificó la biblioteca que los implementa.

---

## 5. Verificación de certificados del servidor (found, `C38791hg.A03`)

La versión de protocolo 6 (el único valor usado) interpreta `ServerHello.payload` como un `CertChain`:

`CertChain` (`C24843Amz`): leaf **1**, intermediate **2**. Cada uno es un `NoiseCertificate` (`C24842Amy`): details **1** (bytes), signature **2** (bytes). `details` se interpreta como `Details` de la cadena (`C24841Amx`): serial **1**, issuerSerial **2**, key **3**, notBefore **4**, notAfter **5**.

Verificaciones (prefijo de log `wa6:`; el orden de evaluación no se recuperó por completo, el método decompilado está incompleto):

1. Ambos `details` se interpretan como `Details` de la cadena.
2. `intermediate.issuerSerial == 0` y `leaf.issuerSerial == intermediate.serial`.
3. `leaf.key` es igual a la static del servidor del handshake `s_s` ("noise certificate key does not match proposed server static key").
4. La firma del intermediate se verifica sobre `intermediate.details` con la clave raíz fijada para el emisor `WhatsAppLongTerm1` (`AbstractC44011qk.A00`).
5. La firma del leaf se verifica sobre `leaf.details` con la `key` del intermediate.

`notBefore` / `notAfter` no se leen en la ruta de la cadena. Un fallo lanza `X.1so` (log `socket/invalid-certificate-exception`).

Raíz fijada (clave pública, found, `AbstractC44011qk.A01`): `142375574d0a587166aae71ebe516437c4a28b73e3695c6ce1f7f9545da8ee6b`.

Forma plana (código muerto con la versión constante 6): `NoiseCertificate{details = 1, signature = 2}` (`C25757B9r`), `Details` plano `{serial = 1, issuer = 2, expires = 3, subject = 4, key = 5}` (`BC0`). El código verifica la única firma contra la clave fijada según el nombre del emisor, compara `key` con `s_s` y rechaza cuando `expires` (segundos) es menor que la hora actual (log `noise certificate expired`).

---

## 6. ClientPayload

### 6.1 Campos (found, `C38001fP`; números tomados del descriptor)

| Campo | Número | Tipo | Definido por, en 2.26.41.6 |
|-------|--------|------|---------------------|
| username | **1** | int64 | parte numérica de usuario del login JID (usuario LID para un login LID) |
| passive | **3** | bool | flag de modo de conexión de la info de sesión (7.2) |
| userAgent | **5** | `UserAgent` | 6.2 |
| webInfo | **6** | `WebInfo` | no definido por los contribuidores leídos |
| pushName | **7** | string | push name de la cuenta, si no está vacío |
| sessionId | **9** | int32 | id de sesión por conexión (`C37121db`) |
| shortConnect | **10** | bool | `C11750a1.A03()` |
| connectType / connectReason | **12** / **13** | enum | 6.5 |
| shards | **14** | repeated int32 | no definido |
| dnsSource | **15** | message | `dnsMethod` **15**, `appCached` **16** |
| connectAttemptCount | **16** | int32 | intentos hasta ahora |
| device | **18** | int32 | modo companion: preferencia `registration_device_id` |
| devicePairingData | **19** | message | 6.3 / 6.4 |
| product | **20** | enum | `WHATSAPP_LID` para un login LID, de lo contrario `WHATSAPP` por defecto |
| oc / lc | **23** / **24** | bool / int32 | `oc`: resultado de la verificación de build o firma (`AbstractC38241gg`, nombre no expandido); `lc`: preferencia `connection_lc` |
| pull | **33** | bool | **nunca definido en este build** (no se encontró ningún escritor) |
| yearClass / memClass | **36** / **37** | int32 | heurísticas de clase de dispositivo (`C38261gi`, `C38271gj`) |
| trafficAnonymization | **40** | enum | `STANDARD` cuando `C17830kT.A0L()`, de lo contrario `OFF` |
| lidDbMigrated | **41** | bool | solo con un user JID y sin companion |
| connectionSequenceInfo | **43** | int32 | contador 0-31 derivado del paso de la secuencia |
| paaLink | **44** | bool | `C0NZ.A02()` |
| preacksCount / processingQueueSize | **45** / **46** | int32 | estado de la cola (flags **20485** / **22413**) |
| pairedPeripherals | **47** | repeated string | `smart_glasses`, `garmin` |
| messageSts | **49** | int64 | marca de tiempo del último mensaje, si se conoce |

Definidos pero no establecidos aquí: fbCat **21**, fbUserAgent **22**, iosAppExtension **30**, fbAppId **31**, fbDeviceId **32**, paddingBytes **34**, interopData **38** (`accountId` **1**, `token` **2**, `enableReadReceipts` **3**), accountType **42**, testIsolationId **48**.

### 6.2 UserAgent (found, `C38051fp`)

| Campo | Número | Valor en este build |
|-------|--------|---------------------|
| platform | **1** | `ANDROID` (0), constante |
| appVersion | **2** | `{primary 1, secondary 2, tertiary 3, quaternary 4}` interpretado desde `2.26.41.6` |
| mcc / mnc | **3** / **4** | `getNetworkOperator()`, por defecto `000` |
| osVersion / manufacturer / device / osBuildNumber | **5** / **6** / **7** / **8** | strings del sistema |
| phoneId | **9** | id a nivel de dispositivo (`C38141gV`) |
| releaseChannel | **10** | `BETA` (1) en este build beta; `RELEASE 0, BETA 1, ALPHA 2, DEBUG 3` |
| localeLanguageIso6391 / localeCountryIso31661Alpha2 | **11** / **12** | se omiten para `zz` / `ZZ` |
| deviceBoard / deviceExpId | **13** / **14** | string de board si no está vacío; id de experimento |
| deviceType | **15** | `PHONE`, `TABLET`, `DESKTOP`, `VR` según la clase de dispositivo |
| deviceModelType | **16** | |
| distributionChannel | **17** | no definido |

`UserAgent.Platform` (`EnumC38071fr`, 0-40): 0 ANDROID, 1 IOS, 10 SMB_ANDROID, 12 SMB_IOS, 13 WINDOWS, 14 WEB, 24 MACOS, 29 WEAROS, 33 IPAD, 35 SMART_GLASSES, 39 WORK_ANDROID, 40 WORK_IOS (los demás se omiten).

### 6.3 DevicePairingRegistrationData (found, `C38661hS`)

Campos de `DevicePairingRegistrationData`: eRegid **1** (id de registro de 4 bytes), eKeytype **2** (`05`), eIdent **3** (clave pública de identidad), eSkeyId **4**, eSkeyVal **5**, eSkeySig **6** (id del signed prekey, pública, firma), buildHash **7**, deviceProps **8** (`DeviceProps` serializado).

`buildHash`: el código calcula `Base64.decode(hexMD5("2.26.41.6"), 0)` (`C00L.A04` devuelve el MD5 hexadecimal en minúsculas de 32 caracteres, que luego se pasa al decodificador base64), lo que da 24 bytes, no el digest de 16 bytes (found tal como se lee).

`DeviceProps` (`C43105IrG`): os **1** (string de OS), version **2** (`AppVersion`), platformType **3**, requireFullSync **4** (= true), historySyncConfig **5**. El bloque de history-sync lo ensambla una clase que registra como `CompanionRegInfoProvider`; sus campos (días / límites de tamaño de full sync, recent sync, thumbnail sync, flags de soporte como call logs, bot history, group history) están controlados por los flags **15284**, **15283**, **21217**, **20658**, **18953**, **26445**, **26614**.

### 6.4 Qué variante se envía (found)

- Login, primario (user JID conocido): username, passive, userAgent, pushName, sessionId, shortConnect, connectType, connectReason, dnsSource, connectAttemptCount, connectionSequenceInfo, lc, oc, yearClass, memClass, trafficAnonymization, lidDbMigrated, messageSts, contadores de cola, paaLink, pairedPeripherals; `product = WHATSAPP_LID` para logins LID.
- Login, companion: lo mismo más `device = registration_device_id`.
- Registro de companion (user JID nulo): sin username; `devicePairingData` (bundle de claves + `DeviceProps`) y `device`.

`ConnectionThread/connect/ignored/jid null and not in companion reg` muestra que un JID nulo se rechaza fuera del registro de companion. El teléfono primario se registra por HTTPS `/v2/*` (ver el informe de account-security); no se encontró ningún uso de `devicePairingData` en el registro primario.

### 6.5 Enums usados (found)

| Enum | Valores |
|------|--------|
| `ConnectReason` (`EnumC38391gv`) | 0 PUSH, 1 USER_ACTIVATED, 2 SCHEDULED, 3 ERROR_RECONNECT, 4 NETWORK_SWITCH, 5 PING_RECONNECT, 6 UNKNOWN |
| `ConnectType` (`EnumC38311gn`) | 0 CELLULAR_UNKNOWN, 1 WIFI_UNKNOWN, 100 EDGE, 101 IDEN, 112 HSPAP; los demás nombres celulares (UMTS, EVDO, GPRS, HSDPA, HSUPA, HSPA, CDMA, ...) toman sus números de constantes indirectas que no se resolvieron |
| `Product` (`EnumC38561hI`) | 0 WHATSAPP, 1 MESSENGER, 2 INTEROP, 3 INTEROP_MSGR, 4 WHATSAPP_LID |
| `DNSResolutionMethod` (`EnumC38321go`) | 0 SYSTEM, 1 GOOGLE, 2 HARDCODED, 3 OVERRIDE, 4 FALLBACK, 5 MNS, 6 MNS_SECONDARY, 7 SOCKS_PROXY |

Connect reason tal como se escribe en este build: por defecto `UNKNOWN`; cuando la marca de tiempo de la info de sesión está dentro de 10 s, el estado 1 da `USER_ACTIVATED`, el estado 2 da `PUSH`. Los demás valores están definidos, pero este contribuidor no los selecciona.

---

## 7. Después del handshake

### 7.1 Resultado del login (found, `HandlerThreadC12340b0.A13`)

Los primeros nodos entrantes se leen en un bucle. `web` solo se acepta cuando se envió un web ref (si no, `web node given during login without any web ref provided`). Cualquier cosa distinta de `web`, `success`, `failure` lanza `unexpected node received during login sequence`.

Atributos de `<success>` leídos:

Atributos leídos: `t` (hora del servidor en segundos, almacenada; un valor no numérico lanza `invalid server time`), `props`, `abprops`, `mc_ep_version` (contadores de versión de config), `lid` (LID de la cuenta, comparado con el LID almacenado; una discrepancia informa `lid-chatd-lid-mismatch`), `pn` (user JID del teléfono), `static_pq_key` (clave PQ del servidor en base64, 4.5).

### 7.2 Modo pasivo vs activo (found)

`passive` en el payload proviene de la info de sesión (`C37981fJ.A0A`); campos de log `forcePassiveMode`, `enablePassiveModeBasedOnQueueSize`, `duplexActive`. Tras el login el cliente sale del modo pasivo con un IQ set construido por `AbstractC44071qq`:

```xml
<iq id="..." xmlns="passive" type="set" to="s.whatsapp.net"><active/></iq>   <!-- or <passive/> -->
```

Los pre-acks se envían primero cuando están en cola (`ConnectionThread/send preacks`). Un timer de 32000 ms (`HandlerC21850s9.A02`) se arma al enviar; si la señal de conexión activa no llega, dispara el motivo 10 (`connection active timeout`).

### 7.3 Boletines de información (found, `C40581l4`)

Hijos de `<ib>` manejados: `edge_routing` (hijo `routing_info`, almacenado, sección 3.1), `fbip` (IPs separadas por comas hacia el gestor de respaldo), `client_expiration` (`t`, segundos, convertido a ms), `dirty`, `offline_preview`, `location`, `notice`, `recovery_nonce`, `safetynet`, `sonar` (`url`), `streamdebug`, `thread_metadata`, `gpia`, `age_experience`, `accept_paa_link`, `peer_device_presence`. `dns_domain` no está presente (ausente en el cliente Android).

---

## 8. Codificación binaria de nodos

### 8.1 Contenido del frame y flags (found, `C40411kn.Csv`, `C24610wf.Be0`)

Tras el descifrado AES-GCM el texto plano comienza con un byte de flags:

| Bit | Significado |
|-----|---------|
| `2` | el resto es un stream zlib (DEFLATE); el decodificador lo descomprime y conserva el byte de flags |
| `1` | fragmentación; el decodificador lanza `server to client stanza fragmentation not supported` |

Codificador: `Csv(node, flags)` con `flags & 2` comprime (`DeflaterOutputStream`) y antepone `02`; de lo contrario escribe un byte de flags `00`. Las rutas de envío principales en `HandlerThreadC12340b0` y el hilo escritor `HandlerThreadC21920sG` llaman a `Csv(node, 3)`, por lo que esas stanzas se comprimen. `Csu(node)` (= flags 1, sin comprimir) se llama desde `C40851lV`, que parece ser el emisor de la etapa de login (inferred). El marcador de fin de stream es `00` + list(1) + token `02` (`Clp`, `xmlstreamend`).

### 8.2 Bytes de etiqueta (found)

| Byte | Nombre | Cuerpo |
|------|------|------|
| 0 | lista vacía / ausente | ninguno |
| 1, 2 | `xmlstreamstart`, `xmlstreamend` | el decodificador los rechaza como strings |
| 3..235 | token de un byte | índice en la tabla `A00` de 236 entradas |
| 236..239 | diccionario 0..3 | 1 byte de índice en `A01[tag - 236]` (256 entradas cada uno) |
| 244 / 247 | JID_INTEROP / AD_JID | `user:str, device:u16, integrator:u16, domain:u8` / `domain:u8, device:u8, user:str` |
| 248 / 249 | LIST_8 / LIST_16 | `count:u8` / `count:u16` |
| 250 | JID_PAIR | `user:str or 00, server:str` |
| 251 / 255 | HEX_8 / NIBBLE_8 | `lenAndOdd:u8` + nibbles empaquetados |
| 252 / 253 / 254 | BINARY_8 / _20 / _32 | `len:u8` / `len:u20` (3 bytes) / `len:u32`, luego bytes |

Las etiquetas 245 y 246 no existen en este códec. Todos los enteros multibyte son big-endian.

### 8.3 Estructura del nodo (found, `C40411kn.A01`)

```
list(size)  description  (key value)*  [content]
size = 1 + 2 * attrCount + (content ? 1 : 0)
```

Un tamaño impar significa sin contenido. Decodificador: cantidad de atributos = `((size - 2) + size % 2) / 2`. El contenido es un blob de bytes (`252 / 253 / 254`) o una lista de hijos. Un nodo con blob e hijos a la vez lanza `more than one source of inner data`. Encabezado de lista: 0 para vacía, 248 por debajo de 256 entradas, 249 por debajo de 65536, de lo contrario `list too long`.

### 8.4 Escalera de strings (found, `C40411kn.A05` / `A06`)

| Posición | Orden de prueba |
|------|-------------|
| description | token, diccionario, JID (si es interpretable), UTF-8 con prefijo de longitud |
| clave de atributo | token, diccionario, UTF-8 |
| valor de atributo | token, diccionario, JID, empaquetado, UTF-8 |
| bytes de contenido | BINARY crudo (`A06(bytes, false)`), nunca tokenizado ni empaquetado |

Empaquetado (`A06` con el flag de empaquetado, solo valores de atributo): longitud menor que 128 y todos los caracteres en `[0-9-.]` da NIBBLE_8 (`255`; `0-9` = 0..9, `-` = 10, `.` = 11); longitud menor que 128 y todos los caracteres en `[0-9A-F]` da HEX_8 (`251`); el bit de longitud impar es `0x80` en el byte de longitud. Las longitudes de 256 en adelante usan BINARY_20 hasta 1 MiB, BINARY_32 más allá. Mapa de nibbles del decodificador: 10 `-`, 11 `.`, 12 `:` (el codificador nunca emite 12).

### 8.5 JIDs (found, `C40411kn.A00`, `C24610wf.A02`)

| JID | Codificación |
|-----|----------|
| usuario interop (`C99O`, tipo 22) | `244, user, device u16, integrator u16, 00`; se decodifica a `{integrator}-{user}[:device]@interop` |
| grupo interop (`C55529Oy6`, tipo 28, servidor `interop.g.us`) | `244, user, 0000, 0000, 02`; el decodificador exige device e integrator en 0 |
| agent o device presente | `247, domainByte, device, user`; bit de domainByte `1` = LID, bit `128` = hosted |
| en otro caso | `250, user (or 00), server` |

Mapeo de servidor de AD_JID: `0` `s.whatsapp.net`, `1` `lid`, `128` `hosted`, `129` `hosted.lid`. Se espera device `99` exactamente cuando el bit hosted está activo; una discrepancia se registra y el JID se acepta igualmente. Los JIDs no conformes lanzan `failed to write jid`.

### 8.6 Diccionario (found, `AbstractC40911lb`)

236 tokens de un byte (el índice 0 es null) y cuatro diccionarios de 256 entradas; la versión del diccionario es el último byte de intro, `03`. Índices re-resueltos en este build:

| Token | Índice | Token | Índice |
|-------|-------|-------|-------|
| `s.whatsapp.net` | 3 | `iq` / `ack` / `message` | 25 / 27 / 19 |
| `type`, `id`, `from`, `to` | 4, 8, 6, 17 | `get` / `set` / `result` / `error` | 41 / 90 / 20 / 168 |
| `routing_info` / `edge_routing` | 39 / 40 | `urn:xmpp:ping` / `ping` / `w:p` | 43 / 86 / 87 |
| `handshake` / `success` | 53 / 76 | `stream:error` / `not-authorized` | 157 / 209 |
| dict 0: `active` / `conflict` / `replaced` / `passive` | 1 / 14 / 17 / 24 | dict 1: `dirty` / `server-error` / `pair-device` | 1 / 145 / 238 |
| dict 2: `failure` / `rate-overlimit` | 60 / 239 | `call` / `usync` / `w:m` | 100 / 121 / 194 |

Algunos tokens de la tabla son constantes Java importadas de otras clases (por ejemplo `enc`); esta lista de índices no los resolvió. Los índices cambian entre builds; no se deben reutilizar entre versiones.

---

## 9. Keepalive y timers

| Timer | Valor | Nivel |
|-------|-------|------|
| Ping del cliente | `<iq type="get" xmlns="w:p" to="s.whatsapp.net"/>` (`C9EN`); la respuesta debe llevar `from`, `id`, `t` en 1577865600..4102473600 y `type="result"` (`C14U`) | found |
| Timeout de ping | `clamp(flag 15103, 8000, 32000)` ms; al expirar `C14R.CY1()` se ejecuta una vez por ping (reacción de reconexión inferred) | found / inferred |
| Intervalo de ping | flag **15270** (primero), **15183** (después); runnable con retardo o alarma `com.whatsapp.alarm.CLIENT_PING_TIMEOUT`, elegido por el flag **6493** | found, valores del lado del servidor |
| Ping del servidor | `<iq type="get" xmlns="urn:xmpp:ping" t="...">` (`AbstractC40501kw`) | found |
| Ack de modo activo | 32000 ms, luego disconnect motivo 10 | found |
| Recibo de mensaje | 45000 ms tras el envío, aún sin confirmar: reconexión motivo 9 (`HandlerC21850s9`) | found |
| Timeout de logout / timeout de socket | 10000 ms / 30000 ms | found |

---

## 10. Reconexión y backoff (found, `C11380Yq.A07`, `C0X9`)

`C11380Yq` programa una reconexión mediante `AlarmManager` (`com.whatsapp.MessageHandler.RECONNECT_ACTION`, extra `connect_reason` 3). La unidad de retardo es 10 s (0x2710 ms en el smali).

| Paso | Regla |
|------|------|
| Contador | `C0X9(1, 17280)`: Fibonacci en unidades, secuencia 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ... limitada a 17280 unidades (48 h) |
| Primer reintento | 0 unidades: `scheduleReconnect/immediate` |
| Jitter | `d = units * 10 s`; retardo uniforme en `[d / 2, 1.5 d)` |
| Límite | cuando el flag del llamador está activo, los retardos superiores a 15 min pasan a 15 min más un offset aleatorio de `-30 .. +29` ms (`backoff clamped to ~15mins`) |
| Reinicio | `A02()` reinicia el contador ante una solicitud de reconexión `reset` |
| Overrides | `force` borra el deadline pendiente; `force_no_ongoing_backoff` omite la espera; `reset` reinicia el contador |
| Sin red | `handleDisconnected/retry/network_unavailable` espera conectividad (alarma `CONNECTIVITY_RETRY_ACTION`) |

Dentro de un intento, la secuencia de conexión de la sección 2.2 recorre hosts y puertos; el backoff se aplica entre intentos fallidos de la conexión completa.

---

## 11. Errores de stream y códigos de fallo

### 11.1 `<failure reason="N">` en el login (found, `A13`)

| Motivo | Manejo | Atributos adicionales leídos |
|--------|----------|-----------------------|
| 5xx | fallo del servidor reintentable, `C45351tB(type 4)` | ninguno |
| 402 | familia de ban; type 13 (code 106 con `appeal_token`), 14 (code 107), 15 (code 109), de lo contrario 2 | `appeal_token`, `code`, `expire`, `message`, `url`, `age_collection` |
| 403 | type 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` |
| 405 | type 3, `expiration_time = t * 1000` | `t` |
| 406 | type 5 | `code` |
| 416 | type 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` |
| otro | type 0 (ruta genérica de logout) | ninguno |

Todo fallo además lee los campos opcionales de UI de logout `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text` / `_url`, `logout_secondary_button_text` / `_url` (`A17`). No se trazó el mapeo de los enteros de tipo a pantallas visibles para el usuario; la semántica de ban de cuentas la cubre el informe de ban.

### 11.2 `<stream:error code="N">` (found, `C40601l6`, `C37961fH.A1B`)

| Caso | Manejo |
|------|----------|
| Cualquier `stream:error` | se registra `ConnectionThreadRequestsImpl/stream/error` con el primer hijo; se publica un mensaje con `errorCode` en `MessageHandler` |
| Código 500-599 | `MessageHandler` define un flag y ejecuta una pasada de reconexión (`onConnectionStreamError`) |
| Hijo `ack` | tratado como ack-kick: se busca la stanza pendiente con ese id, se emiten métricas, la conexión se detiene (se lanza `1t7`) |
| Hijo `conflict type="device_removed"` | solo companion: deregister (`C24100vp.A02`), salvo estado 9 |
| 515 / 516 (ruta companion) | reenviados como mensajes tipados; la rama decompilada para 515 no está clara |
| `<error code="479">` | se informa `smax-invalid` (`SmaxInvalidError`) |
| `<error class="status" id=...>` | hace fallar el callback pendiente de ack de status |

### 11.3 Fallos de handshake y socket (found como log tags, reacciones parcialmente trazadas)

| Log tag | Causa |
|---------|-------|
| `socket/goaway` (`X.1sn`) | los bytes de longitud del ServerHello son iguales a `GOA` |
| `socket/invalid-certificate-exception` (`X.1so`) | falló la verificación de la cadena de certificados (5); llama a `C37031dS.A0C` |
| `socket/disconnect/invalid-server-static-key` (`X.1sp`), `.../authKey` (`X.1sm`) | static del servidor rechazada; problema con la clave static del cliente |
| `socket/disconnect/noise` (`X.1sr`) | excepción de protocolo (datos de handshake inválidos, tamaños TLV); el fallo AEAD `X.1t9` y el error de entrada KEM `X.1tC` se relanzan dentro de esta familia |
| `socket/disconnect/io`, `socket/closed`, `socket/error/EPERM` | errores de E/S, red bloqueada |
| `connect/not-allowed/clock`, `software-expired`, `login-failed`, `quit-flag-set` | compuertas previas a la conexión |
| `ReaderThread/corrupt-stream-error` | stream de nodos inválido; `next-port/corrupt-stream-exception` avanza el puerto |

---

## 12. Feature flags (ids tal como se leen en `AbstractC36791d3` y en los puntos de llamada)

| Id | Tipo | Controla |
|----|------|----------|
| **20161**, **34536** | int, string | modo PQ (1 enable, 2-4 enforce), variante PQ (por defecto `IKKEM`) |
| **38643**, **15716** | string, bool | elección de KEM (`MLKEM768` reconocido), compuerta para ello; efecto sin resolver |
| **33751** | bool | escritor con buffer para intro + ClientHello |
| **22916**, **30712**, **33512** | bool | desactivar el paso HISTORY; cargar el registro del último éxito; reutilizar el puerto almacenado |
| **20801**, **23630**, **24645** | bool | paso 5 fijo en 443; pasos 2-4 bajo config SOCKS; origen de la config de servicio SOCKS |
| **13545** | string | modo de resolver DNS (`secondary` / `hardcoded` / `none`) |
| **7831**-**7834** | bool, ints | habilitación y parámetros de TCP keepalive |
| **15103**, **15270**, **15183**, **6493** | int, bool | timeout de ping, intervalos, método de programación |
| **20485**, **22413** | bool | estado de la cola en el payload |

Todos los valores son del lado del servidor; los valores por defecto son los compilados en las declaraciones de flags.

---

## 13. Otros transportes

| Transporte | Estado en 2.26.41.6 | Nivel |
|-----------|--------------------|------|
| Cliente Tigon HTTP | `com/crossapp/tigonhttp/TigonHttpClient*`, `com/facebook/tigon/**`, `com/whatsapp/infra/tigon/WAHucClient`, auth mediante `WATigonAsyncAuthServiceHolder`; strings de HTTP/2 y HTTP/3 (`MNS/mvfst-mobile`, `MNS/ngtcp2`) en `libwhatsappmerged.so` | clases y strings found; uso por feature inferred |
| DistribGW (DGW) | `com/facebook/distribgw/client/*`, `RequestStreamDGWBuilder`; único registro del lado de la app encontrado: `WaFalcoStreamingRegistration.nativeRegisterStreaming(DGWClient)`; strings `distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, `XPLAT_RS_MQTT`, `XPLAT_RS_STARGATE`, `wa_request_stream` | found; formato de red unknown |
| Cliente MQTT | ninguno; `mqtt` aparece solo en nombres de eventos de analítica y etiquetas de tipo de stream de DGW | found |
| GraphQL sobre chatd | `com.whatsapp.pando.chatd.WAChatdGraphQLClient`, `WAChatdGraphQLCallbacks`, `WATigonMexdServiceHolder` | nombres found; viaja por chatd como ruta w:mex inferred |

### 13.1 Canal Tigon Noise (segundo stack Noise, nativo)

Es un transporte distinto de chatd. La evidencia son strings y nombres de clases, no lógica decompilada.

- Portador: WebSocket sobre el stack de red MNS (`NoiseCarrierWebSocket`, `Stream0Listener`); streams numerados con un stream de control 0 y reensamblado de chunks (`noise.framer.*`).
- Resultados del handshake (`NoiseHandshakeOutcome`): `LEGACY_PEER_VERIFIED`, `PRIVATE_AUTH_PEER_VERIFIED`, `ENROLLMENT_REQUIRED`, `KEY_REQUIRED`, `VERIFICATION_FAILED`; `NoisePrivateAuthMode`: `MIGRATION`, `REQUIRED`; errores como `noise.handshake.attestation_failed`, `chip_binding_rejected`, `private_auth.vm_proof_failed`.
- Attestation: verificador AMD SEV-SNP (`NoiseSevSnpAttestationVerifier`, verificaciones de la cadena VCEK / ASK / ARK, vinculación al chip id); etiquetas `hatch.noise-auth.key.v1`, `.client-proof.v1`, `.vm-proof.v1`.
- Control de demanda: `NoiseConnectionDemandRejectionReason` `OFFLINE`, `BACKGROUND`, `PAUSED`, `SESSION_ENDED`, `RETRY_EXHAUSTED`, `INTERNAL`.
- Usuarios Java: `WaVmHttpTransportImpl`, `NoiseVmConnection` (ruta `/v1/noise`, pasos `hatch-noise status=opening` / `result=ready`), `NoiseGatewayCarrier`. El propósito (HTTP sobre Noise hacia una VM de cómputo confidencial para el navegador del agent) es inferred a partir de los nombres y los strings de attestation.

Nada de esto comparte código con el handshake de chatd de la sección 4; que el nombre de patrón sea igual no implica el mismo framing, prólogo ni payload.

---

## 14. Baileys (`baron-baileys-v2`, confirmado contra su código fuente)

| Aspecto | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Encabezado de intro | `NOISE_WA_HEADER = [87, 65, 6, 3]` | `57 41 06 03` |
| Patrón | `NOISE_MODE = 'Noise_XX_25519_AESGCM_SHA256\0\0\0\0'` | mismo nombre relleno de 32 bytes |
| Cert del servidor | decodifica `CertChain`; firma del leaf verificada con la clave del intermediate; intermediate verificado con la raíz fijada `142375574d0a...da8ee6b`; `issuerSerial` debe ser 0 | misma cadena y los mismos bytes de raíz; el APK además exige `leaf.issuerSerial == intermediate.serial` |
| Edge routing | guarda `routing_info` de `<ib><edge_routing>`; lo agrega como query `ED=<base64url>` en `wss://web.whatsapp.com/ws/chat` | lo guarda (máx. 256 bytes); envía `45 44 00 01 len24 blob` crudo antes de la intro |
| Keepalive | `<iq type="get" xmlns="w:p"/>` sin hijos, intervalo por defecto 30000 ms, timeout de conexión 20000 ms | mismo IQ; intervalo y timeout desde flags del servidor |
| Payload de login | `passive`, `pull` true, `username`, `device`, `connectType WIFI_UNKNOWN`, `connectReason USER_ACTIVATED`, `lidDbMigrated false`, `releaseChannel RELEASE` | sin `pull`, `connectReason` según el estado de sesión, `releaseChannel BETA` en este build |
| Payload de registro | `passive false`, `pull false`, `devicePairingData` | `devicePairingData` solo para la conexión de registro de companion |
| Transporte | frames WebSocket | TCP crudo, frames con longitud de 3 bytes |

Diferencias confirmadas relevantes para un transporte al estilo Android: la pista edge es un parámetro de query en la URL WebSocket en Baileys pero un encabezado crudo antes de la intro en Android; Baileys no exige `leaf.issuerSerial == intermediate.serial`; Baileys envía `pull` y `passive` en true en el login mientras que el payload de Android no tiene `pull`. Baileys conserva la clave static del servidor para una reconexión rápida (un comentario del código menciona `NoiseIkSession`), lo que coincide con la reanudación IK de la sección 4.4 solo en intención; su forma de red no se comparó.

---

## 15. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `GOA` en los primeros tres bytes | goaway del servidor durante el handshake | probar el siguiente endpoint |
| `Handshake message does not contain server hello!` | el primer frame del servidor no es un ServerHello | revisar el prólogo y el encabezado edge |
| `noise certificate key does not match proposed server static key` | la clave del leaf difiere de la static del handshake | verificar la cadena antes de ClientFinish |
| `server to client stanza fragmentation not supported` | bit de flags `1` activo | no soportado por el cliente |
| `unexpected node received during login sequence` | el primer nodo no es `web`, `success`, `failure` | ninguna |
| `noise-pq-static-key-decode-failed` | `static_pq_key` no es base64 válido | clave no almacenada, informado una vez |
| `scheduleReconnect backoff=...` | fallos repetidos | esperar el backoff o forzar una reconexión |

---

## 16. Distinciones clave

| No confundir | Detalle |
|----------------|--------|
| Noise de chatd vs canal Tigon Noise | Java vs nativo, portador TCP vs WebSocket, distinto propósito; el nombre de patrón igual no implica nada sobre el framing ni el payload |
| Encabezado de intro vs encabezado edge | `WA 06 03` se hashea como prólogo; `ED 00 01 len blob` no es parte de la transcripción |
| Host edge `eN.whatsapp.net` vs `routing_info` | los hosts provienen de la secuencia del cliente; `routing_info` es un blob opaco que se reenvía en el encabezado edge |
| `fallback_hostname` / `fallback_ip4` / `fallback_ip6` | atributos de hosts de `media_conn` (CDN), no fallbacks de chatd; los fallbacks de chatd provienen de `<ib><fbip>` y de la tabla fija |
| flag de payload `passive` vs IQ `<passive/>` | el flag se define al conectar; el IQ cambia después a modo activo |
| `devicePairingData` vs registro HTTP | los datos de pairing pertenecen a la conexión de registro de companion |
| Longitud del frame vs tamaño de lista | la longitud de 3 bytes envuelve el texto cifrado; el tamaño de lista cuenta las posiciones del nodo |
| Versión de protocolo vs de diccionario | ambas en la intro: `06` y `03` |
| `stream:error` vs `failure` | `failure` responde al login; `stream:error` puede llegar en cualquier momento |

---

## 17. Flujo completo

```
[Connection thread]  C37031dS.A0G picks step (history, g, g-fallback, hard-coded, eN, proxy)
     │  DNS ─► TCP connect ─► optional TLS wrapper
     ▼
[Client]  write [ED 00 01 len24 routing_info]?  [WA 06 03]        h = SHA256(name) ; h = SHA256(h || WA 06 03)
     │  frame1: HandshakeMessage{clientHello{ephemeral}}           mixHash(e_c)    (resume: + static + payload)
     ▼
[Server]  frame2: serverHello{ephemeral, static, payload}
     │  mixHash(e_s) ; mixKey(ee) ; s_s = decrypt(static) ; mixKey(es) ; cert = decrypt(payload)
     │  CertChain: leaf.key == s_s ; intermediate by pinned root ; leaf by intermediate
     ▼
[Client]  frame3: clientFinish{static = enc(s_c), payload = enc(ClientPayload)}      mixKey(se) ; split
     ▼
[Server]  [len24 | AES-GCM(flags | node)] ─► <success t props abprops lid pn static_pq_key/>  or  <failure reason/>
     ▼
[Client]  <iq xmlns="passive" type="set"><active/></iq> (+ pre-acks) ; steady state both ways, own counter per direction
     │  ping <iq xmlns="w:p"/> ; ib / notification / message / receipt / call ...
     ▼
[Failure]  stream:error / ping timeout / socket error ─► disconnect ─► Fibonacci backoff ─► next attempt
```

---

## 18. Incógnitas

| Elemento | Estado |
|------|--------|
| Tráfico de red de cualquier tipo | no se capturó nada; ningún elemento es `tested` |
| Transcripción de reanudación IK y fallback | estructura found, pasos inferred |
| Ubicación de la clave PQ en `ServerHello.payload`, ancho de longitud del TLV, biblioteca detrás de las llamadas ML-KEM | no decodificado / no identificado |
| Qué llevan los endpoints envueltos en TLS dentro de TLS | inferred a partir de la ruta de código |
| Valores de ping y TCP-keepalive | flags del servidor |
| Enteros de tipo de fallo 0-15 a pantallas del cliente; efecto de los flags **38643**, **15716** | no trazado / sin resolver |
| Campos del payload sin escritor (`webInfo`, `shards`, `fb*`, `accountType`, `testIsolationId`, `paddingBytes`, `pull`) | ninguno encontrado en este build |
| Handshake y framing del canal Tigon Noise; protocolo de red de DGW y sus usuarios | nativo, solo strings |
| Strings del diccionario que son constantes Java importadas (por ejemplo `enc`) | no resueltos en la lista de índices |
