<!-- src-sha1: a94958787eccb3db407fbb92cf700d9a4d424f4a -->
# WhatsApp Subida de medios — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** transferencia de medios en Android: IQ `media_conn` (hosts, auth, ttl, buckets, hosts de respaldo), construcción de URL de subida y descarga y parámetros HTTP, tabla de tipos de medio con cadenas info de HKDF, generación y derivación de la media key, cifrado AES-CBC + HMAC, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, miniaturas, sidecars de streaming para video / audio / imágenes progresivas, subida reanudable, selección de ruta, reintentos y backoff, códigos de error de subida y descarga, recibo de reintento de medios y notificación `mediaretry`, medios de ver una vez y de estados, medios de newsletter (canales), express path, endurecimiento nativo del lado del cliente de los parsers de medios, comparación con Baileys

---

## 1. Qué es (técnicamente)

Los medios nunca viajan dentro del stream de chatd (ver [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Un mensaje lleva solo una referencia protobuf (clave, hashes, `directPath`); los bytes van por conexiones HTTPS separadas hacia hosts de medios. Chatd aporta una sola cosa: el IQ `media_conn`, que entrega nombres de host y un token de autenticación de subida de corta duración. Todas las afirmaciones provienen del análisis estático del APK decompilado y de las bibliotecas nativas desempaquetadas; no se capturó nada en la red. Niveles: **found** = leído en código o strings, **inferred** = deducido, **unknown** = no resuelto.

| Capa | Nombre en 2.26.41.6 | Función |
|------|----------------------|---------|
| Selector de rutas | `RouteSelector` (`C10950Wx`) | guarda el resultado actual de `media_conn`, temporizador de refresco, throttle, fábrica de rutas |
| Parser de `media_conn` | `C43951qe` (handler del resultado IQ), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | parsea `<media_conn>` / `<host>` |
| Proveedor de rutas | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (proveedores estáticos) | elige host por intento, intercambia el token de auth |
| Driver de reintentos | `TransferRetries` (`C44566Jd2`) | bucle de intentos alrededor de una transferencia |
| Tabla de tipos de medio | `MmsType` (`C15530gU`) | por tipo: cadena de path, bytes info de HKDF, id numérico |
| Proveedor de claves | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF de 80 bytes, clave de dominio no E2EE |
| Streams de cifrado | `M2I` (cifrado de salida), `M23` (cifrado de entrada), `P9N` / `P1X` / `P1Y` (MACs de sidecar), `C51101MlN` (descifrado por rango) | AES-CBC + HMAC |
| Driver de subida | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (reutilización de clave), `C57333Po0` (generación de clave + hashes) | hashes, sidecars, orquestación de la subida |
| URL de subida | `C43489Iy4` | `/surface/type/hash?...` |
| URL de descarga | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) subida; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) descarga | transporte |
| Sondeo de reanudación | `HttpResumeCheck` (`C59524QnW`) | pregunta al servidor cuántos bytes tiene |
| Recibo de reintento | `SendMediaErrorReceiptJob`, casos de writer 77 y 327 en `HandlerThreadC21920sG` | solicita la resubida al remitente |
| Notificación de reintento | `MediaRetryNotificationHandler` (`C1S0`, código de notificación 97) | consume la respuesta |
| Nativo | `libwhatsapp.so` (crates Rust de medios, sandboxes RLBox), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | parsers y decodificadores |

Puntos que determinan el resto del reporte:

- Android deriva **80** bytes de la media key (IV 16, cipher key 32, MAC key 32), no 112 (sección 4).
- El path HTTP es `/{surface}/{type}/{urlSafeFileEncSha256}` donde `type` es la cadena `MmsType` del medio (`image`, `ptt`, `md-msg-hist`, ...), no una clase gruesa (sección 8.1).
- El `token` de subida de Android no es el hash del archivo; es un SHA-256 sobre un secreto por instalación y el hash del archivo (sección 8.2).
- Los medios de newsletter (canal) comparten el mismo código pero usan la surface `newsletter` y un token aleatorio; no están cifrados (found para la ruta del artwork, inferred para el resto, sección 13).
- Los hosts de descarga se filtran por un bucket derivado del hash del archivo (sección 9.2).

---

## 2. IQ `media_conn`

### 2.1 Solicitud (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout de 32000 ms. Solo hay una solicitud en vuelo (`inFlightMediaRoutingRequestTime`); una segunda llamada registra `not sending request` y retorna. Un throttle global (`ChatdMediaThrottleManager`) puede suprimir la llamada (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Respuesta (found, `C43951qe.CFS`)

| Nodo / atributo | Tipo | Uso |
|-----------------|------|-----|
| `media_conn@auth` | string, requerido | token de autenticación de subida (parámetro de query `auth`) |
| `@ttl` | segundos | vida útil de la conexión; expiración = hora de envío + ttl * 1000 |
| `@auth_ttl` | segundos | vida útil del token de auth; expiración = hora de envío + auth_ttl * 1000 |
| `@max_buckets` | long, por defecto 0 | módulo para el bucket de descarga (sección 9.2) |
| `@is_new` | int, por defecto 1 | 1 = reemplaza la lista de hosts; en otro caso conserva los hosts anteriores y toma solo token y ttl (`previous hosts retained`) |
| `@id` | string | se guarda como `last_id`, se reenvía en la siguiente solicitud |
| `@max_auto_download_retry` | int, por defecto 3 | presupuesto de reintentos para descargas automáticas |
| `@max_manual_retry` | int, por defecto 3 | presupuesto de reintentos para descargas manuales |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | parseados y cacheados; `ip_token` se usa solo cuando el flag **12149** está activo y `set_ip_token` es true (lugar de consumo: unknown) |
| `host` (repetido) | nodo | una entrada de ruta |

Atributos de `host` (found): `hostname` (requerido), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` o `fallback`; cualquier otro valor se convierte en `primary`), `force_ip` (`"true"`). Hijos: `<upload>`, `<download>`, `<download_buckets>`; los nombres de las etiquetas hijas son las entradas de capacidad. `upload` y `download` conservan solo las etiquetas que aparecen en un conjunto fijo de 34 cadenas de tipo de medio (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, la familia `newsletter-*` y la familia `thumbnail-*`); `download_buckets` se conserva sin filtrar.

Un host de ruta es utilizable solo si su hostname termina en `.whatsapp.net` (`Mms4RouteSupplier.A06`, aplicado también a `fallback_hostname`).

### 2.3 Caché y refresco (found)

| Regla | Valor |
|-------|-------|
| Persistencia | con el flag **149** el resultado se guarda como JSON (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) bajo `route_selector_prefs` / `media_conn`; se carga una vez, se usa solo si el auth aún no expiró |
| Chequeo de refresco | antes de una transferencia: si la conexión o el auth expiran en menos de 120000 ms, se envía un nuevo IQ y se espera hasta 20000 ms (`requestroutesandwaitforauth`) |
| Temporizador | `auth expiry - 60000 ms` tras cada resultado; el primer plano (`BgG`) lo vuelve a armar |
| Fallo de auth | HTTP 401 o 403 en una transferencia dispara un refresco (`onmediatransfererrororresponsecode`), máximo 2 intercambios de token por transferencia (`JW1.A00 < 2`), luego el intento se reintenta con el nuevo `auth` |
| Auth antes del intento | `refreshAuthBeforeAttempt` intercambia por un token más nuevo cuando el cacheado está a menos de 120000 ms de expirar (símbolo de flag `PTU.A0D`) |

### 2.4 Error del IQ (found, `C43951qe.Brt`)

`<error code backoff>` dentro del resultado del IQ:

| Código | Comportamiento |
|--------|----------------|
| 503 | reinicia el throttle de medios; programa el siguiente refresco tras un backoff Fibonacci con jitter (`3/4 * t + rand(t/2)`) |
| 507 con backoff > 0 | aplica throttle a las solicitudes de medios hasta `now + min(backoff, 10800) s` |
| otro / 0 | ignorado |

---

## 3. Tipos de medio y cadenas info de HKDF (found, init estático de `MmsType` `C15530gU`)

Cada `MmsType` contiene una cadena de path (`A02`), una etiqueta corta de tipo de archivo (`A01`, p. ej. `IMG`), los bytes `info` de HKDF (`A03`) y un id numérico (`A00`). Los bytes `info` se usan en bruto como info de HKDF (sin prefijo adicional).

| Info de HKDF | Cadenas de path de `MmsType` |
|--------------|------------------------------|
| `WhatsApp Image Keys` | `image`, `sticker`, `kyc-id`, `biz-cover-photo`, `biz-flows`, `wamo-image`, `newsletter-image`, `newsletter-image-status`, `newsletter-sticker`, `newsletter-music-artwork` |
| `WhatsApp Video Keys` | `video`, `ptv`, `gif`, `wamo-video`, `newsletter-video`, `newsletter-video-status`, `newsletter-ptv`, `newsletter-gif`, `newsletter-gif-status` |
| `WhatsApp Audio Keys` | `audio`, `ptt`, `newsletter-audio`, `newsletter-audio-status`, `newsletter-ptt` |
| `WhatsApp Document Keys` | `document`, `biz-flows`, `maiba-file`, `db`, `newsletter-document` |
| `WhatsApp Image Thumbnail Keys` | `thumbnail-image`, `newsletter-thumbnail-image`, `newsletter-thumbnail-status` |
| `WhatsApp Video Thumbnail Keys` | `thumbnail-video`, `thumbnail-gif`, `newsletter-thumbnail-video` |
| `WhatsApp Document Thumbnail Keys` | `thumbnail-document` |
| `WhatsApp Link Thumbnail Keys` | `thumbnail-link`, `newsletter-thumbnail-link` |
| `WhatsApp Chat Wallpaper Keys` | `chat-wallpaper-image` |
| `WhatsApp App State Keys` | `md-app-state` |
| `WhatsApp History Keys` | `md-msg-hist` |
| `Group History` | `group-history` |
| `WhatsApp Sticker Pack Keys` | `sticker-pack`, `newsletter-sticker-pack` |
| `WhatsApp Sticker Pack Thumbnail Keys` | `thumbnail-sticker-pack`, `newsletter-thumbnail-sticker-pack` |
| `WhatsApp Payment Background Keys` | `payment-bg-image` |
| `WhatsApp Music Artwork Keys` | `music-artwork` |
| `waffle_hkdf_info` | `waffle-image`, `waffle-video`, `waffle-gif` |
| `PAYMENT_DOC_UPLOAD` | `payment-br-document` |
| `ads-image` / `ads-video` | `ads-image` / `ads-video` |

Notas (found): `ptt` y `audio` comparten la info de Audio pero son cadenas de path distintas; `sticker` usa la info de Image; `gif` y `ptv` usan la info de Video; existen varias filas `image` con distintos ids numéricos (1, 23, 25, 37, 42, 44, 57; `sticker` es 20) para distintos puntos de llamada (significado del id: desconocido); `group-history` es la única entrada cuya info no tiene la forma `WhatsApp <X> Keys`. Las fotos de perfil (`ppic`) aparecen solo en el conjunto de capacidades de ruta y en llamadas al generador de descarga, no como `MmsType`.

---

## 4. Media key y derivación

### 4.1 Generación de la clave (found)

| Elemento | Valor |
|----------|-------|
| Media key | 32 bytes aleatorios de `SecureRandom` (`C57333Po0`, `QIh.A0B` es `new SecureRandom()`) |
| Reutilización | `MediaKeyGen/reuse key from message contents` cuando la clave tiene menos de `172800000 ms + SecureRandom.nextInt(86400000)` (2 a 3 días, con jitter), medido contra el timestamp de clave almacenado; las claves más viejas se descartan (`key expired`) y se regeneran |
| Dominio | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `AbstractC38961i0.A00` llamado por `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01` rechaza cualquier otra longitud (`Invalid length of derived secret`). Longitud del texto cifrado: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (bloques con padding PKCS#5 más 10 bytes de MAC).

### 4.3 Media key no E2EE (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (campo **74**, mensaje `DQT`) lleva `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) y `e2eeMediaKey` (**2**). Con el flag **24661** el receptor verifica que la clave del mensaje coincida con el dominio (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); si no coincide, recurre a la clave tal como viene. Qué productos usan el dominio NON_E2EE: unknown.

---

## 5. Cifrado, MAC y hashes

### 5.1 Cifrado (found, `M2I`, `M23`, `N6U`)

| Paso | Detalle |
|------|---------|
| Cifrado | `AES/CBC/PKCS5Padding`, key = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, actualizado primero con el IV y luego con cada byte del texto cifrado; los primeros **10** bytes del digest se anexan al texto cifrado |
| `fileSha256` | SHA-256 sobre el texto plano (stream de digest `P9M` sobre el archivo) |
| `fileEncSha256` | SHA-256 sobre texto cifrado + 10 bytes de MAC |
| Salida | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Lado de descifrado (`P9N`, `M23`): el MAC se verifica sobre IV + texto cifrado y luego se compara con los 10 bytes finales. Descifrado por rango (`C51101MlN`): cuando el inicio del rango no es 0, los primeros 16 bytes leídos se usan como IV (bloque de texto cifrado anterior); los chunks internos usan `AES/CBC/NoPadding`, el chunk final usa PKCS#5 (inferred a partir de la selección del cifrado).

### 5.2 Timestamps y paths

| Campo | Valor |
|-------|-------|
| `mediaKeyTimestamp` | reloj local en milisegundos mantenido en el objeto de clave, escrito al protobuf en segundos (`C20H.A06` = `/1000`) |
| `directPath` | cadena de path devuelta por el servidor, guardada en el mensaje y en la columna de BD `direct_path`; puede llevar parámetros de query (p. ej. se lee `_nc_hot` de ahí) |
| `url` | campo heredado de URL completa; sigue presente en las clases proto y en la respuesta de subida, pero el generador de descarga se construye a partir de `directPath` o del hash (sección 9.1) |

### 5.3 Chequeos optimistas de hash

`MediaUpload/optimistic-hash-fail` y `optimistic-plaintext-hash-fail` (resultado de subida 12) se registran cuando el hash que reporta el servidor difiere del calculado localmente. La subida optimista (cadena de surface `optimistic`) sube antes de confirmar el envío; su protocolo más allá del nombre de la surface: unknown.

---

## 6. Campos de mensajes de medios

Números de campo leídos de las clases protobuf generadas. Los nombres de clase se asocian por la disposición de campos (inferred); los números son found.

| Mensaje (clase) | Números de campo (nombre = número) |
|-----------------|------------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| Bundle de historial (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

Números del contenedor `Message` (`C30628DTw`) (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage` es el campo **21** del contenedor `BD3`.

### 6.1 Miniaturas

| Tipo | Mecanismo (found salvo indicación) |
|------|------------------------------------|
| Inline | bytes `jpegThumbnail` (**16**) en el mensaje (imagen, video, documento); `pngThumbnail` (**16**) en stickers |
| Subida | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (imagen **26-28**, video **21-23**, documento **13-15**); `MmsType` `thumbnail-*` con las infos HKDF de miniatura de la sección 3 |
| Clave | el proto no tiene un campo de clave de miniatura separado, por lo que una miniatura se cifra con la media key de su mensaje (inferred) |
| Generada por el servidor | query de subida `server_thumb_gen=1`; la respuesta de subida puede devolver `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` |
| BD | tabla `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming y sidecars (found)

Un sidecar es una lista de MACs de 10 bytes, una por chunk de texto cifrado, que permite a un reproductor verificar un rango sin leer todo el archivo.

| Elemento | Detalle |
|----------|---------|
| Algoritmo | `P9N.read`: por chunk se inicializa un `HmacSHA256(macKey)` con los **16 bytes de texto cifrado anteriores** (el IV para el primer chunk), se alimenta el chunk y se guardan los primeros 10 bytes del digest |
| Concatenación | `C57228PmG.A00` une todos los MACs de 10 bytes en un solo arreglo de bytes |
| Video / audio | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); tamaño de chunk **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Imagen progresiva | `firstScanSidecar` (**18**) con `firstScanLength` (**19**): un chunk de `ceil(len/16)*16` bytes; `scansSidecar` (**21**) con `scanLengths` (**22**): tamaños de chunk variables (`P1Y`) |
| Sticker | `firstFrameSidecar` (**12**) con `firstFrameLength` (**11**) |
| Ajustes | la prop de servidor `streaming_upload_chunk_size` es un token de diccionario; su efecto: unknown |
| Ausente | estado de descarga 30 `failed_no_sidecar` |
| Streaming del servidor | query de subida `stream=1` y `streaming=riff` juntos (sección 8.1); DASH: `dashManifestUrl` (**33**), `metadataUrl` (**30**) en la respuesta |

---

## 8. Subida

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Parte | Valor |
|-------|-------|
| `surface` | `mms` (normal), `newsletter` (canales), `optimistic` (subida previa al envío); `AbstractC58025Pzy` |
| `type` | cadena de path de `MmsType` (sección 3), p. ej. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | base64 estándar de `fileEncSha256` con `+` a `-` y `/` a `_`; el padding `=` se conserva (`StringUtils.A0B`) |
| `direct_ip` | 1 cuando la authority es una IP (`ip4`, o `[ip6]` entre corchetes), en otro caso 0 |
| `auth` | el token de auth de `media_conn`; se agrega como parámetro de query por `K19.A03` |
| `stream=1`, `streaming=riff` | ambos se establecen cuando la solicitud es una subida en streaming (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | solo para `newsletter-image` / `-status` (flag **11191**) y `newsletter-video` / `-status` (flag **11192**) |
| `server_transcode=1` | `newsletter-video` con id de solicitud 10 y flag **9096** |
| `_nc_rmr=1` | subidas que no son de newsletter (flag de solicitud `A0N`) |
| `_nc_cbep=1` | cuando la solicitud lo permite y el flag **17404** está activo (significado desconocido) |
| `type`, `media_id`, `media_id_upload` | `media_id` = los 63 bits más significativos de un UUID de subida; `media_id_upload` = los 63 bits menos significativos, solo cuando la solicitud tiene entradas extra; `type` es una cadena del llamador (significado: unknown) |

El significado de los nombres de query `_nc_cbep` y `_nc_rmr` es unknown (solo nombres).

### 8.2 Token (found, `C43489Iy4.A00`)

| Caso | Token |
|------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`, nuevo por solicitud, no ligado al archivo |
| Otro | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` son 32 bytes de `SecureRandom`, creados una vez y guardados en preferencias como `upload_token_random_bytes` (base64 sin wrap, sin padding) |

Si `fileEncSha256` no se puede decodificar, el token es solo `SHA-256(installSecret)`. Propósito de la construcción: inferred como una verificación del lado del servidor de que quien sube conoce el hash sin exponerlo en el path.

### 8.3 Solicitud HTTP (found, `HttpsFormPost` `C43478Ixt`)

| Elemento | Valor |
|----------|-------|
| Biblioteca | `HttpsURLConnection` con un `SSLSocketFactory` personalizado; marcador `http_stack = HttpUrlConnection` |
| Método | POST (`setDoOutput(true)` en `HttpURLConnection`; sin llamada explícita al método) |
| Timeouts | connect 15000 ms, read 60000 ms |
| Headers | `Host: <route hostname>` (la authority puede ser una IP), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, opcional `Companion_User_Secret` (argumento de constructor no nulo; semántica de companion inferred) |
| Body (con ruta) | stream de texto cifrado en bruto, un solo archivo (`MMS4 upload only supports a single file`); modo streaming de longitud fija cuando se conoce la longitud, si no chunked (`setChunkedStreamingMode(0)`); buffer de 16384 bytes |
| Body (sin ruta) | `multipart/form-data` heredado con partes `Content-Disposition: form-data` |
| Aborto | ante interrupción del hilo o flag de cancelación el stream se rellena (`UploadRequest/Post streaming padding bytes=`) para completar la longitud declarada (propósito inferred) |
| Respuesta | se leen hasta 1 MiB; HTTP >= 400 devuelve el código, el body va a `onError` |

### 8.4 Respuesta (found, `MediaUploadTransfer` `C59523QnV`)

Claves JSON leídas: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (aceptado solo si coincide con `[A-Za-z0-9-]{1,64}`), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (string JSON anidado con `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. Una respuesta sin `direct_path` no se trata como error por este parser; etapas posteriores fallan con `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Subida reanudable (found)

| Paso | Detalle |
|------|---------|
| Sondeo | misma URL de subida más `resume=1` (`HttpResumeCheck`); respuesta JSON `{"resume": "complete"}` con `url`, `direct_path` (ya subido) o `{"resume": <offset>}` |
| Continuación | POST con `Content-Range: bytes <offset>-*/*`, el stream se salta hasta `<offset>` primero |
| Fallbacks | `ResumeCheck/attempting fallback MMS upload form post`, también tras un error WATLS (TLS) |
| Error de parseo | estado `PBY.A03`, la subida se reinicia |

### 8.6 Proveedor de rutas y reintentos (found, `Mms4RouteSupplier`, `TransferRetries`)

| Regla | Detalle |
|-------|---------|
| Bucle de intentos | `TransferRetries/run attempt = N; route = ...`; una transferencia por ruta; `no routes` termina el bucle |
| Elección de host | host `type=primary` cuyo conjunto de capacidades contiene el tipo de medio; los dos primeros intentos lo usan; los intentos posteriores usan la entrada `type=fallback` y sus campos `fallback_*` (orden inferred a partir de un flujo de control ilegible) |
| Intentos | por defecto 4 (`4 - extra`); con los flags **12545** y **12446** el límite puede sobrescribirse tras el intento 3; `max_auto_download_retry` / `max_manual_retry` (por defecto 3 cada uno) alimentan la cuenta dependiente del modo (mapeo inferred) |
| Retardo | constante de 1000 ms (`RouteSelector.A01`); con el flag **257** e intentos extra, exponencial: base 1000 ms, `2^n`, jitter, tope de 3000 ms |
| Error de auth 401 / 403 | no cuenta como fallo: espera un token más nuevo (presupuesto `A0J`, 20000 ms por defecto), intercambia, reintenta |
| Estado HTTP reintentable | `QKS.A08`: < 400 sí; 400-499 no, salvo 408 con el flag **13748**; >= 500 sí, salvo 505 y 507 |
| Proxy | con un proxy de usuario y el flag **4073** la authority de medios pasa a ser el host del proxy y el puerto de `proxy_media_port` (por defecto 587) |
| Health check | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, connect 15000 ms, read 30000 ms |

---

## 9. Descarga

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

El constructor requiere un hash de medio, un direct path o una referencia cruzada (`media hash, direct path, or cross reference is required`). `mode` es `auto` o `manual`. `_nc_map=whatsapp-nofna` se agrega para los tipos de la lista del servidor `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (prop AB, flag **4836**). La query `auth` se agrega en una ruta con flag (`PTU.A03`) y reemplaza un parámetro `auth` existente. Las fotos de perfil usan el tipo `ppic`; los assets estáticos usan `/wa/static` con `_nc_cat`.

### 9.2 Bucket y elección de host (flujo de control decompilado, parcialmente ilegible)

- Los hosts se filtran por capacidad `download` y por `download_buckets` que contenga la cadena del bucket.
- Bucket `1` cuando el direct path lleva `_nc_hot=<seconds>` más reciente que la ventana del flag **2136**; en otro caso, con el flag **2134** y `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); bucket de respaldo `0`.
- Los tipos de newsletter y los casos con flag omiten la lógica hot / hash.
- El bucket elegido sale como `_nc_cat`.

### 9.3 Solicitud HTTP (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Elemento | Valor |
|----------|-------|
| Método | GET (Tigon o `HttpURLConnection`) |
| Headers | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (condicionado por flag), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (cuando se conoce un ETag) |
| Aceptado | HTTP 200 y 206 |
| Parcial | las previsualizaciones usan un prefijo de 262144 bytes (`Range: bytes=0-262143`) |
| 416 | se trata como completo cuando `Content-Range` es `*/<size>` e iguala el tamaño local; si no, reinicio (flag **29305**) o error |
| Lista de permitidos | con el símbolo de flag `PTU.A04`, el host debe estar en `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` (coincidencia por sufijo) salvo que la URL tenga `category=PSA`; si no, `invalid_url` (8) / log `host not in media CDN allow-list` |

### 9.4 Verificación (found)

El stream de descifrado verifica el MAC; las etapas de hash se mapean a los estados 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; las entradas faltantes se mapean a 26-30 (sección 10.2).

---

## 10. Códigos de error

### 10.1 Manejo de estados HTTP

| Estado | Comportamiento |
|--------|----------------|
| 401, 403 | refresca `media_conn`, intercambia auth, reintenta (máx. 2 intercambios) |
| 408 | reintenta solo con el flag **13748** |
| 416 | ver 9.3 |
| 507 | estado de descarga 12 `throttle`, sin reintento |
| 505 | sin reintento |
| otros 4xx | sin reintento |
| 5xx, < 400 | se reintenta dentro del presupuesto de intentos |

### 10.2 Estado de descarga (found, `QKK` `A03`)

| Código | Nombre | Código | Nombre |
|--------|--------|--------|--------|
| 0 | success | 17 | wamsys_failed |
| 1 | failed_generic | 18 | failed_network |
| 2 | dns_failure | 19 | failed_connect |
| 3 | timeout | 20 | host_switch_required |
| 4 | disk_full | 21 | suspicious_content |
| 5 | too_old | 23 | partial_image_downloaded |
| 6 | resume_failed | 24 | programmatic_cancel |
| 7 | hash_mismatch | 25 | failed_no_client_network |
| 8 | invalid_url | 26 | failed_no_encryption_algorithm |
| 9 | output_stream_fail | 27 | failed_no_encrypted_hash |
| 11 | no_route | 28 | failed_no_media_hash |
| 12 | throttle | 29 | failed_no_media_key |
| 13 | user_cancel | 30 | failed_no_sidecar |
| 14 | prefetch_end | 31 | failed_hash_verification |
| 15 | watls_error | 32 | enc_hash_mismatch |
| 16 | server_error | 34 | deduped |

Los códigos 10, 22, 33 y cualquier otro imprimen `invalid`. `QKK.A04` agrupa 1, 2, 3, 11, 15, 16, 18, 19, 20 y 25 (fallos de tipo red; la etiqueta es inferred).

### 10.3 Resultado de subida (found, nombres de métrica `media_upload_<NAME>`)

| Código | Nombre | Código | Nombre |
|--------|--------|--------|--------|
| 1 | CANCEL | 22 | FAILED_DNS_LOOKUP |
| 2 | FAILED_INSUFFICIENT_SPACE | 23 | FAILED_WAMSYS |
| 3 | FAILED_IO | 24 | FAILED_TOO_LARGE |
| 4 | FAILED_OOM | 25 | ERROR_NO_CLIENT_NETWORK |
| 5 | FAILED_BAD_MEDIA | 26 | HOST_SWITCH_REQUIRED |
| 6 | FAILED_NO_PERMISSIONS | 27 | SKIPPED_EP_NO_PRIMARY_HOST |
| 7 | FAILED_FNF | 28 | FAILED_CRONET |
| 8 | FAILED_SERVER | 29 | FAILED_NO_DIRECT_PATH |
| 9 | FAILED_REQUEST | 30 | FAILED_NO_MEDIA_KEY |
| 10 | FAILED_REQUEST_TIMEOUT | 31 | FAILED_UNKNOWN |
| 11 | FAILED_NOT_FINALIZED | 32 | CANCEL_PROGRAMMATIC |
| 12 | FAILED_OPTIMISTIC_HASH | 33 | FAILED_NO_ROUTE |
| 13 | FAILED_MEDIA_CONN | 34 | FAILED_CANNOT_TRANSCODE |
| 14 | FAILED_OPTIMISTIC_NETWORK_UNSAFE | 35 | FAILED_UNKNOWN_MIMETYPE |
| 15 | FAILED_THROTTLE | 36 | FAILED_SERVER_REJECTED_MEDIA |
| 16 | FAILED_NO_SUCH_ALGORITHM | 37 | FAILED_IO_ENCRYPTION |
| 17 | FAILED_NETWORK | 38 | FAILED_STREAMING_METADATA_TOO_LARGE |
| 18 | FAILED_WATLS | 39 | FAILED_MUSIC_REPORTING |
| 19 | FAILED_URL | 20 / 21 | FAILED_TRANSCODING_UNKNOWN / FAILED_FILE_FORMAT_UNSUPPORTED |

Mapeo de excepciones en `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, otra `IOException` 18 (red caída) o 3, `CancellationException` 1, `C7CL` 21, cualquier otra 31. Tras un resultado no exitoso con 5, 21, 24, 34, 35 o 36 se borran la clave y el hash cacheados (`A0B`, `A0C`).

---

## 11. Reintento de medios (solicitud de resubida)

Cuando una descarga falla porque el objeto ya no existe (típicamente estado 5 `too_old`, o una respuesta de clase 404), el receptor pide al teléfono del remitente que suba de nuevo.

### 11.1 Solicitud: recibo `server-error` (found, `SendMediaErrorReceiptJob`)

| Variante | Writer | Wire |
|----------|--------|------|
| Multi-device (primario propio) | caso 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Heredada | caso 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (sin `rmr`) |

`enc_iv` son 12 bytes aleatorios; `enc_p` se produce de forma nativa (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) a partir de un mensaje que lleva el stanza id. La biblioteca nativa contiene la info HKDF `WhatsApp Media Retry Notification`; AES-GCM con el stanza id como AAD y una clave HKDF de 32 bytes se infiere a partir del IV de 12 bytes y de la implementación de Baileys. Las props de servidor `mms4_media_retry_notification_encryption_enabled` y `mms4_server_error_receipt_encryption_enabled` son tokens de diccionario (efecto inferred: condicionan si se envía `<encrypt>`).

### 11.2 Respuesta: notificación `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Paso | Detalle |
|------|---------|
| Chequeo de cuenta | un `rmr` de otra cuenta registra `cross-account-rmr` y se descarta salvo que el símbolo de flag `PTV.A0F` esté activo |
| Búsqueda | mensaje por `(chat, id, from_me)`; los mensajes que no son de medios registran `message is null or not media` |
| Descifrado | nativo (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); el modelo resultante entrega `directPath` (guardado en el mensaje) y un int de resultado |
| Resultado | `<error code>` sobrescribe el resultado; el handler compara el valor con 2 y 3 (con la numeración del proto público `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferred) |
| Continuación | el downloader recibe el nuevo direct path (`resume reuploading download`); sin un downloader activo el mensaje se encola para descarga automática |
| Reporting | con el flag **5718** el `reporting_token` se guarda para el mensaje |

---

## 12. Medios de ver una vez y de estados

| Tema | Hecho (found) |
|------|---------------|
| Cifrado / transporte | idéntico al de medios normales: mismo `MmsType`, mismo HKDF, mismas URLs; no hay un tipo de ver una vez en la tabla |
| Flag | `viewOnce` es un campo en `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); contenedor `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Reglas locales | el remitente no puede abrir su propio medio de ver una vez (`senders can not view their own media`); las miniaturas de ver una vez las borra `EphemeralUpdateRunnable/deleteViewOnceThumbnails`; un audio de ver una vez sin media key no se envía (`unable to send encrypted media message due to missing mediaKey`) |
| Si el servidor borra el objeto tras verlo | unknown |
| Estado (`status@broadcast`) | usa las filas normales de `MmsType` (image, video, gif, audio) con sus propios ids numéricos; no existe info HKDF `status`; los únicos tipos `*-status` son los de newsletter (sección 13) |
| Límites de estados | los tokens de diccionario `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` son props de servidor (valores: unknown) |
| Descarga de estados | `C59526QnY` contiene una variante `MediaDownload` y una `StatusMediaDownload`; ambas construyen la URL con el mismo generador |

---

## 13. Medios de newsletter (canal)

| Aspecto | Newsletter | Regular |
|---------|-----------|---------|
| Surface en la URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | nombres simples |
| Cifrado | ninguno: el downloader de artwork requiere `artworkEncSha256` solo para contenido que no es de newsletter (`required fields missing - artworkEncSha256 is null for encrypted content`); para otros tipos existe el stream de paso directo `C59535Qnh` (identidad). Las filas `MmsType` aún llevan bytes info de HKDF (sin uso, inferred) |
| Token de subida | aleatorio, no ligado al hash (sección 8.2) | secreto por instalación + hash |
| Filtro de ruta | sin lógica de bucket hot / hash para nombres que empiezan con `newsletter` | lógica de bucket (9.2) |
| `ip_token` de `media_conn` | `ip_token` se aplica en newsletter independientemente de `set_ip_token` (flag **12149**) | solo cuando `set_ip_token` es true |
| Trabajo del servidor | `server_thumb_gen=1` (flags **11191**, **11192**), `server_transcode=1` para video (flag **9096**) | no se establece |
| Flag **27920** | leído en la ruta de newsletter de `C15490gQ`; efecto desconocido | |

---

## 14. Express path y otras variantes de subida

| Variante | Evidencia |
|----------|-----------|
| Express path | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) enviado como mensaje E2E (`FMessageMediaExpressPathNotify`, requiere url, hash y longitud); `ExpressPathDownload` registra `EP gain <ms> <bytes>`; log de subida `Use static route supplier for express path upload`; resultado de subida 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Comportamiento del lado del servidor: unknown |
| Subida optimista | surface `optimistic`; el rechequeo de hash da resultados 12; protocolo: unknown |
| Historial / app state | `md-msg-hist`, `md-app-state` usan el pipeline normal con sus cadenas info |
| Historial de grupo | `group-history`, info `Group History`, mime `application/protobuf` verificado por el receptor (`C34677F2y`); el path sigue la sección 8.1 (`/mms/group-history/...`, inferred a partir de la composición genérica) |

---

## 15. Endurecimiento nativo de los parsers de medios (found, strings y exports de las bibliotecas desempaquetadas)

81 objetos compartidos se desempaquetan del archivo superpack. Los parsers inseguros en memoria de bytes controlados por el atacante están en sandbox o reemplazados por Rust.

| Entrada | Componente | Endurecimiento |
|---------|------------|----------------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp compilado a WebAssembly y reducido a C con wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), wrapper `whatsapp::security::LibwebpSandbox` en un sandbox thread-local; flag de Java `sWebPSandboxEnabled`; log de fallo `sandboxed WebP decode failed: status=%d`; guardas `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib en un sandbox wasm2c / WASI-minrt (`GiflibSandbox`, `wasi::minrt`); clases JNI `SandboxedGifImage`, `SandboxedGifFrame`; guarda `Called memcpy for memory larger than the sandbox` |
| Archivos Ogg / Opus | `libwhatsapp.so` | sandboxes RLBox wasm2c para `libogg.wasm` y `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; log de trap `wasm2c sandbox trap: %s (code=%d)` |
| Parseo de contenedores y streams | crates Rust de `libwhatsapp.so` | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, segmentador DASH, edit lists), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (valores IPTC de digital-source-type como `trainedAlgorithmicMedia`, C2PA) |
| Decodificación AV1 | `libdav1d.so` | dav1d **1.5.1** (cadena de versión); exporta la API `dav1d_*` |
| Codificación AV1 | `libwzav1.so` | versión 2.3.1; exporta solo `wz_encoder_*` y `wz_codec_version*`; sin símbolos de decodificador, por lo que no parsea bitstreams remotos |
| Frames H.264 / H.265 | `MediaCodec` de la plataforma | fuera de la app |

Los parsers en Rust fallan con panics (`assertion failed: ...`, `While parsing field '...' in ...`) en lugar de corrupción de memoria: found como strings, efecto inferred. El sandbox `rlbox` cubre libogg y opusfile en `libwhatsapp.so`; otras bibliotecas usan wasm2c sin el wrapper RLBox (inferred a partir de símbolos). Si cada ruta de medios entrante llega a estos parsers antes de la interacción del usuario: unknown. Comportamiento dinámico (fuzzing, crashes en runtime): no probado.

---

## 16. Feature flags (ids tal como se leen en los puntos de llamada; nombres sin resolver)

| Flag | Dónde | Controla |
|------|-------|----------|
| **149** | `RouteSelector`, `C43951qe` | persistir y recargar `media_conn` en preferencias |
| **257** | ctor de `Mms4RouteSupplier` | objeto de backoff exponencial |
| **258** | `Mms4RouteSupplier.A03` | int: intentos extra para el modo 0 |
| **2134** | `A02` | bucket de descarga basado en hash |
| **2136** | `A02` | ventana de contenido hot (long) |
| **4073** | `A00` | enrutar medios a través del proxy de usuario |
| **4836** | `Mms4DownloadUrlGenerator` | lista de tipos con baja tasa de aciertos (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | manejo del reporting token |
| **9096** | `QBE` | `server_transcode=1` (video de newsletter) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` para imagen / video de newsletter |
| **12149** | `RouteSelector.A0L`, `A03` | usar `ip_token` |
| **12545** / **12446** | `A05` | sobrescribir el límite de intentos tras el intento 3 |
| **13748** | `QKS.A08` | reintentar HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | puntos de entrada de `RouteSelector` | booleano pasado a la selección de ruta como flag de subida (semántica sin resolver) |
| **24661** | `MediaCryptoProvider` | validación del dominio de clave no E2EE |
| **29305** | `PlainDownloadTransfer` | manejo de 416 |
| **37982**, **38437** | `C43481Ixw` | propiedad de Tigon, timeout de solicitud |

---

## 17. Baileys (`baron-baileys-v2`, código fuente leído, nada probado)

| Aspecto | Baileys | Android 2.26.41.6 |
|---------|---------|-------------------|
| Solicitud `media_conn` | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` tiene una variante opcional con `last_id` | siempre `<media_conn>`, con `last_id` cuando existe un id previo |
| Campos parseados | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | no lee `maxContentLengthBytes`; agrega `auth_ttl`, `max_buckets`, `is_new`, `id`, campos de fallback, hijos de capacidad, conteos de reintento, `ip_token` |
| Longitud HKDF | `hkdf(key, 112, {info})`, usa los bytes 0-79 | 80 bytes; los primeros 80 bytes de una salida HKDF no dependen de la longitud solicitada, por lo que IV, cipher key y MAC key son idénticos |
| Cadenas info | `WhatsApp <X> Keys`; `gif` y `ptv` mapean a Video, `ptt` a Audio, `sticker` a Image | mismas cadenas y mapeos |
| Cifrado, MAC, hashes | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` anexado, `fileSha256`, `fileEncSha256` sobre `ct + mac` | igual |
| URL de subida | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Codificación del hash | base64 url-safe, padding `=` eliminado, luego `encodeURIComponent` | base64 url-safe, padding `=` conservado |
| Token | `fileEncSha256` url-safe | `SHA-256(installSecret || fileEncSha256)` (newsletter: aleatorio) |
| Tabla de paths | `sticker` y `thumbnail-link` a `/mms/image`, `ptv` a `/mms/video`, `md-msg-hist` a `/mms/md-app-state`, sin `ptt` | la cadena `MmsType` es el segmento de path: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Headers | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | no se encontró `Origin`; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Reintentos | prueba cada host una vez en orden | proveedor de rutas con intentos, intercambio de token en 401 / 403, sondeo de reanudación |
| Reanudación | ninguna encontrada (`resume=1`, `Content-Range` ausentes) | sondeo `resume=1` y `Content-Range` |
| Sidecars | no se encontró generación de `streamingSidecar`, `firstScanSidecar` ni `scansSidecar` en `src` | generados para video, audio, imágenes progresivas |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | milisegundos internamente, segundos en el proto |
| Recibo de reintento | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = stanza id, IV de 12 bytes, info HKDF `WhatsApp Media Retry Notification` | el caso de writer 327 tiene la misma disposición de nodos; IV de 12 bytes y la cadena info son found; GCM / AAD inferred |
| Mapa de resultados de reintento | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | no aplicable (compara los valores 2 y 3) |

Consecuencias prácticas (solo lectura de código): una subida de Baileys de un objeto `md-msg-hist` usa una cadena de path distinta a la del cliente Android; el base64 con padding en el path es una diferencia visible; cualquier tolerancia del servidor a estas variantes: unknown.

---

## 18. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Subida 401 / 403 | `auth` expirado o reemplazado | refrescar `media_conn`, reenviar con el nuevo `auth` |
| La subida no devuelve `direct_path` | subida rechazada o incompleta | revisar el estado; sondeo de reanudación con `resume=1` |
| Descarga 404 / estado 5 `too_old` | el objeto expiró en el CDN | enviar el recibo `server-error` (sección 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | bytes corruptos o `fileEncSha256` incorrecto | volver a descargar; verificar la fuente del hash |
| Falla la verificación del MAC | media key incorrecta, info HKDF incorrecta (confusión de tipo) o archivo truncado | usar la cadena info del `MmsType` correcto; no reutilizar la info de Image para las filas `sticker-pack` o `ptt` |
| `invalid_url` (8) | host fuera de la lista de permitidos del CDN | aceptar solo los sufijos listados |
| `throttle` (12), HTTP 507 | throttle del servidor | esperar `backoff` segundos (máx. 10800) |
| `no_route` (11) | no hay host utilizable de `media_conn` para el tipo | solicitar `media_conn`, revisar las etiquetas de capacidad |
| `failed_no_media_key` (29), `no_sidecar` (30) | falta un campo del proto | exigir `mediaKey`; sidecar solo para streaming |

---

## 19. Distinciones clave

| No confundir | Hecho |
|--------------|-------|
| Lista de hosts de `media_conn` vs URL de subida | el IQ entrega hosts y un `auth`; el path de la URL, el token y la query se construyen por transferencia |
| `auth` vs `token` | `auth` es el token a nivel de cuenta de `media_conn`; `token` es por archivo |
| HKDF de 80 vs 112 bytes | mismas claves; Android deriva 80 |
| `fileSha256` vs `fileEncSha256` | hash del texto plano vs hash de `ciphertext + mac10` |
| `fileEncSha256` en el path vs `directPath` | el path de subida usa el hash; la descarga usa el `directPath` devuelto por el servidor |
| `mediaKeyTimestamp` vs ventana de reutilización de clave | timestamp en segundos en el wire; ventana de reutilización de 2-3 días en el remitente |
| Sidecar de streaming vs `fileEncSha256` | MACs de 10 bytes por chunk vs hash del archivo completo |
| Reintento de medios vs reenvío | el remitente vuelve a subir el mismo objeto y responde con un nuevo `directPath`; el mensaje no se reenvía |
| Medios de newsletter vs medios regulares | sin cifrar, surface `newsletter`, token aleatorio |
| `libwzav1` vs `libdav1d` | codificador vs decodificador; solo el decodificador parsea datos remotos |

---

## 20. Flujo completo (enviar y recibir una imagen)

```
[Sender app]  pick file → process (resize, strip) → MmsType "image"
     │
     ▼
[RouteSelector]  media_conn fresh? (conn/auth > 120 s left) ── no ──► <iq xmlns="w:m" type="set"><media_conn last_id/></iq>
     │                                                                   │ ◄── auth, ttl, auth_ttl, max_buckets, hosts
     ▼
[Uploader]  mediaKey = 32 B SecureRandom ; okm = HKDF(mediaKey, "WhatsApp Image Keys", 80)
     │  iv | cipherKey | macKey ; AES-CBC encrypt ; mac10 = HMAC(macKey, iv||ct)[0:10]
     │  fileSha256 (plain), fileEncSha256 (ct||mac10) ; optional sidecar / thumbnails
     ▼
[Mms4RouteSupplier]  host: type=primary, upload set has "image"
     │  POST https://host/mms/image/<hash>?direct_ip=0&token=<sha256(secret||hash)>&auth=<auth>
     │      Host, Accept-Encoding: identity, body = ct||mac10   (resume: ?resume=1, Content-Range)
     ▼
[Media server]  (not observed) ──► {"url","direct_path","handle","ts",...}
     │
     ▼
[Sender]  ImageMessage{mediaKey, fileSha256, fileEncSha256, directPath, mediaKeyTimestamp(s), jpegThumbnail, ...}
     │  Signal-encrypted message over chatd
     ▼
[Receiver]  host from media_conn (download set + bucket _nc_cat)
     │  GET https://host<directPath>?direct_ip=0&_nc_cat=<b>&mode=auto
     │      Range: bytes=0-   (200 or 206)
     ▼
[Receiver]  check enc hash → MAC → AES-CBC decrypt → check fileSha256 → store
     │
     ├── object gone (404 / too_old) ──► <receipt type="server-error"><encrypt enc_p enc_iv/><rmr/></receipt>
     │                                         │
     │                                [Sender phone] re-uploads, answers
     │                                         ▼
     └──────────────────────────────── <notification type="mediaretry"><encrypt enc_p enc_iv/></notification>
                                         → new directPath → resume download
```

---

## 21. Desconocidos

| Elemento | Estado |
|----------|--------|
| Comportamiento del servidor (validación de token, deduplicación, vida útil del objeto, borrado de ver una vez) | del lado del servidor |
| Nombres de query `_nc_cbep`, `_nc_rmr`, `type`; flag **21807** y los ids `PTU.*` | nombres o significado sin resolver |
| Ids numéricos en `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | significado sin resolver |
| Cifrado nativo de media-retry (AES-GCM, AAD, longitud de clave) | cadena info found; algoritmo inferred |
| Consumo de `ip_token`, valor de `X-FB-nc-oc`, origen de `Companion_User_Secret` | sin resolver |
| Uso del dominio de media key NON_E2EE | sin resolver |
| Protocolos de express path y de subida optimista | sin resolver |
| Orden exacto de hosts entre intentos y conteos de intentos dependientes del modo | flujo de control decompilado ilegible |
| Qué medio entrante llega a qué parser en sandbox antes de la interacción del usuario | no mapeado |
| Tráfico | nada capturado; sin prueba dinámica |
