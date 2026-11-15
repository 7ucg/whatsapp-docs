<!-- src-sha1: a12736ca9c475f1c7c0195dbae0d18d5725a4440 -->
# WhatsApp Subida de Media — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** transferencia de media en Android: IQ `media_conn` (hosts, auth, ttl, buckets, hosts de fallback), construcción de URL de subida y descarga y parámetros HTTP, tabla de tipos de media con strings de info HKDF, generación y derivación de la clave de media, cifrado AES-CBC + HMAC, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, miniaturas, sidecars de streaming para video / audio / imágenes progresivas, subida reanudable, selección de ruta, retry y backoff, códigos de error de subida y descarga, recibo de reintento de media y notificación `mediaretry`, media view-once y de estado, media de newsletter (canal), ruta express, hardening nativo del lado cliente de los parsers de media, comparación con Baileys

---

## 1. Qué es (técnicamente)

El media nunca viaja dentro del stream de chatd (ver [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Un mensaje lleva solo una referencia protobuf (clave, hashes, `directPath`); los bytes van sobre conexiones HTTPS separadas a hosts de media. Chatd suministra una sola cosa: el IQ `media_conn` que entrega nombres de host y un token de auth de subida de corta vida. Todas las afirmaciones vienen de análisis estático de la APK decompilada y de las bibliotecas nativas desempacadas; nada se capturó en el cable. Niveles: **found** = leído en código o strings, **inferred** = deducido, **unknown** = no resuelto.

| Capa | Nombre en 2.26.41.6 | Rol |
|-------|----------------|------|
| Selector de ruta | `RouteSelector` (`C10950Wx`) | guarda el resultado actual de `media_conn`, temporizador de refresco, throttle, fábrica de rutas |
| Parser de `media_conn` | `C43951qe` (manejador de resultado IQ), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | parsea `<media_conn>` / `<host>` |
| Suministrador de ruta | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (suministradores estáticos) | elige host por intento, intercambia el token de auth |
| Conductor de retry | `TransferRetries` (`C44566Jd2`) | bucle de intentos alrededor de una transferencia |
| Tabla de tipo de media | `MmsType` (`C15530gU`) | por tipo: string de ruta, bytes de info HKDF, id numérico |
| Proveedor de clave | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF de 80 bytes, clave de dominio no-E2EE |
| Streams de cifrado | `M2I` (cifrar salida), `M23` (cifrar entrada), `P9N` / `P1X` / `P1Y` (MACs de sidecar), `C51101MlN` (descifrado por rango) | AES-CBC + HMAC |
| Conductor de subida | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (reutilización de clave), `C57333Po0` (generación de clave + hashes) | hashes, sidecars, orquestación de subida |
| URL de subida | `C43489Iy4` | `/surface/type/hash?...` |
| URL de descarga | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) subida; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) descarga | transporte |
| Sonda de reanudación | `HttpResumeCheck` (`C59524QnW`) | pregunta al servidor cuántos bytes tiene |
| Recibo de reintento | `SendMediaErrorReceiptJob`, casos writer 77 y 327 en `HandlerThreadC21920sG` | solicita re-subida al remitente |
| Notificación de reintento | `MediaRetryNotificationHandler` (`C1S0`, código de notificación 97) | consume la respuesta |
| Nativo | `libwhatsapp.so` (crates de media en Rust, sandboxes RLBox), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | parsers y decodificadores |

Puntos que determinan el resto del informe:

- Android deriva **80** bytes de la clave de media (IV 16, clave de cifrado 32, clave MAC 32), no 112 (sección 4).
- La ruta HTTP es `/{surface}/{type}/{urlSafeFileEncSha256}` donde `type` es el string `MmsType` del media (`image`, `ptt`, `md-msg-hist`, ...), no una clase gruesa (sección 8.1).
- El `token` de subida de Android no es el hash del archivo; es un SHA-256 sobre un secreto por instalación y el hash del archivo (sección 8.2).
- El media de newsletter (canal) comparte el mismo código pero usa la superficie `newsletter` y un token aleatorio; no está cifrado (found para la ruta de artwork, inferred para el resto, sección 13).
- Los hosts de descarga se filtran por un bucket derivado del hash del archivo (sección 9.2).

---

## 2. IQ `media_conn`

### 2.1 Solicitud (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout 32000 ms. Solo una solicitud está en vuelo (`inFlightMediaRoutingRequestTime`); una segunda llamada registra `not sending request` y retorna. Un throttle global (`ChatdMediaThrottleManager`) puede suprimir la llamada (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Respuesta (found, `C43951qe.CFS`)

| Nodo / atributo | Tipo | Uso |
|------------------|------|-----|
| `media_conn@auth` | string, requerido | token de auth de subida (parámetro de query `auth`) |
| `@ttl` | segundos | duración de la conexión; expiración = hora de envío + ttl * 1000 |
| `@auth_ttl` | segundos | duración del token de auth; expiración = hora de envío + auth_ttl * 1000 |
| `@max_buckets` | long, por defecto 0 | módulo para el bucket de descarga (sección 9.2) |
| `@is_new` | int, por defecto 1 | 1 = reemplazar la lista de hosts; de otro modo mantener los hosts anteriores y tomar solo token y ttl (`previous hosts retained`) |
| `@id` | string | almacenado como `last_id`, enviado de vuelta en la siguiente solicitud |
| `@max_auto_download_retry` | int, por defecto 3 | presupuesto de reintento para descargas automáticas |
| `@max_manual_retry` | int, por defecto 3 | presupuesto de reintento para descargas manuales |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | parseado y cacheado; `ip_token` se usa solo cuando el flag **12149** está activado y `set_ip_token` es true (sitio de consumo: unknown) |
| `host` (repetido) | nodo | una entrada de ruta |

Atributos de `host` (found): `hostname` (requerido), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` o `fallback`; cualquier otra cosa se convierte en `primary`), `force_ip` (`"true"`). Hijos: `<upload>`, `<download>`, `<download_buckets>`; los nombres de tag hijo son las entradas de capacidad. `upload` y `download` conservan solo tags que aparecen en un conjunto fijo de 34 strings de tipo de media (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, la familia `newsletter-*`, y la familia `thumbnail-*`); `download_buckets` se conserva sin filtrar.

Un host de ruta solo es usable si su hostname termina en `.whatsapp.net` (`Mms4RouteSupplier.A06`, también aplicado a `fallback_hostname`).

### 2.3 Caché y refresco (found)

| Regla | Valor |
|------|-------|
| Persistir | con el flag **149** el resultado se almacena como JSON (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) bajo `route_selector_prefs` / `media_conn`; cargado una vez, usado solo si el auth aún no expiró |
| Chequeo de refresco | antes de una transferencia: si la conexión o el auth expiran dentro de 120000 ms, enviar un nuevo IQ y esperar hasta 20000 ms (`requestroutesandwaitforauth`) |
| Temporizador | `expiración del auth - 60000 ms` tras cada resultado; el foreground (`BgG`) lo rearma |
| Fallo de auth | HTTP 401 o 403 en una transferencia dispara un refresco (`onmediatransfererrororresponsecode`), máximo 2 intercambios de token por transferencia (`JW1.A00 < 2`), luego el intento se reintenta con el nuevo `auth` |
| Auth antes del intento | `refreshAuthBeforeAttempt` intercambia por un token más nuevo cuando el cacheado está dentro de 120000 ms de expirar (símbolo de flag `PTU.A0D`) |

### 2.4 Error del IQ (found, `C43951qe.Brt`)

`<error code backoff>` dentro del resultado del IQ:

| Código | Comportamiento |
|------|-----------|
| 503 | resetea el throttle de media; programa el siguiente refresco tras un backoff Fibonacci con jitter (`3/4 * t + rand(t/2)`) |
| 507 con backoff > 0 | hace throttle de las solicitudes de media hasta `now + min(backoff, 10800) s` |
| otro / 0 | ignorado |

---

## 3. Tipos de media y strings de info HKDF (found, inicialización estática de `MmsType` `C15530gU`)

Cada `MmsType` guarda un string de ruta (`A02`), una etiqueta corta de tipo de archivo (`A01`, p. ej. `IMG`), los bytes `info` HKDF (`A03`) y un id numérico (`A00`). Los bytes `info` se usan crudos como info HKDF (sin prefijo adicional).

| Info HKDF | Strings de ruta de `MmsType` |
|-----------|------------------------|
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

Notas (found): `ptt` y `audio` comparten la info de Audio pero son strings de ruta distintos; `sticker` usa la info de Image; `gif` y `ptv` usan la info de Video; existen varias filas `image` con ids numéricos distintos (1, 23, 25, 37, 42, 44, 57; `sticker` es 20) para distintos call sites (significado del id desconocido); `group-history` es la única entrada cuya info no tiene la forma `WhatsApp <X> Keys`. Las fotos de perfil (`ppic`) aparecen solo en el conjunto de capacidades de ruta y en las llamadas del generador de descarga, no como un `MmsType`.

---

## 4. Clave de media y derivación

### 4.1 Generación de clave (found)

| Ítem | Valor |
|------|-------|
| Clave de media | 32 bytes aleatorios de `SecureRandom` (`C57333Po0`, `QIh.A0B` es `new SecureRandom()`) |
| Reutilización | `MediaKeyGen/reuse key from message contents` cuando la clave es más joven que `172800000 ms + SecureRandom.nextInt(86400000)` (2 a 3 días, con jitter), medido contra la marca de tiempo de clave almacenada; las claves más antiguas se descartan (`key expired`) y se regeneran |
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

`N6U.A01` rechaza cualquier otra longitud (`Invalid length of derived secret`). Longitud del ciphertext: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (bloques con padding PKCS#5 más 10 bytes de MAC).

### 4.3 Clave de media no-E2EE (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (campo **74**, mensaje `DQT`) lleva `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) y `e2eeMediaKey` (**2**). Con el flag **24661** el receptor verifica que la clave en el mensaje coincida con el dominio (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); en caso de desajuste recurre a la clave tal como viene. Qué productos usan el dominio NON_E2EE: unknown.

---

## 5. Cifrado, MAC y hashes

### 5.1 Cifrado (found, `M2I`, `M23`, `N6U`)

| Paso | Detalle |
|------|--------|
| Cifrado | `AES/CBC/PKCS5Padding`, clave = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, actualizado primero con el IV, luego con cada byte del ciphertext; los primeros **10** bytes del digest se añaden al ciphertext |
| `fileSha256` | SHA-256 sobre el texto plano (stream de digest `P9M` sobre el archivo) |
| `fileEncSha256` | SHA-256 sobre ciphertext + 10 bytes de MAC |
| Salida | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Lado de descifrado (`P9N`, `M23`): el MAC se verifica sobre IV + ciphertext, luego se compara con los 10 bytes finales. Descifrado por rango (`C51101MlN`): cuando el inicio del rango no es 0, los primeros 16 bytes leídos se usan como IV (bloque de ciphertext anterior); los chunks internos usan `AES/CBC/NoPadding`, el chunk final usa PKCS#5 (inferido de la selección de cifrado).

### 5.2 Marcas de tiempo y rutas

| Campo | Valor |
|-------|-------|
| `mediaKeyTimestamp` | reloj local en milisegundos guardado en el objeto de clave, escrito al protobuf en segundos (`C20H.A06` = `/1000`) |
| `directPath` | string de ruta devuelto por el servidor, almacenado en el mensaje y en la columna de BD `direct_path`; puede llevar parámetros de query (p. ej. `_nc_hot` se lee de él) |
| `url` | campo de URL completa legacy; todavía presente en las clases proto y en la respuesta de subida, pero el generador de descarga se construye a partir de `directPath` o del hash (sección 9.1) |

### 5.3 Chequeos optimistas de hash

`MediaUpload/optimistic-hash-fail` y `optimistic-plaintext-hash-fail` (resultado de subida 12) se registran cuando el hash que reporta el servidor difiere del calculado localmente. La subida optimista (string de surface `optimistic`) sube antes de que el envío se confirme; su protocolo más allá del nombre de surface: unknown.

---

## 6. Campos del mensaje de media

Números de campo leídos de las clases protobuf generadas. Los nombres de clase se emparejan por disposición de campos (inferido); los números son found.

| Mensaje (clase) | Números de campo (nombre = número) |
|-----------------|-------------------------------|
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

| Tipo | Mecanismo (found salvo que se indique) |
|------|---------------------------------|
| En línea | bytes `jpegThumbnail` (**16**) en el mensaje (imagen, video, documento); `pngThumbnail` (**16**) en stickers |
| Subida | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (imagen **26-28**, video **21-23**, documento **13-15**); `MmsType` `thumbnail-*` con las infos HKDF de Thumbnail de la sección 3 |
| Clave | el proto no tiene un campo de clave de miniatura separado, así que una miniatura se cifra con la clave de media de su mensaje (inferido) |
| Generada por el servidor | query de subida `server_thumb_gen=1`; la respuesta de subida puede devolver `thumbnail_info` = string JSON `{thumbnail_direct_path, thumbnail_sha256}` |
| BD | tabla `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming y sidecars (found)

Un sidecar es una lista de MACs de 10 bytes, uno por chunk de ciphertext, que permite a un reproductor verificar un rango sin leer todo el archivo.

| Ítem | Detalle |
|------|--------|
| Algoritmo | `P9N.read`: por chunk se inicializa un `HmacSHA256(macKey)` con los **16 bytes de ciphertext anteriores** (el IV para el primer chunk), se le alimenta el chunk, y se almacenan los primeros 10 bytes del digest |
| Concatenación | `C57228PmG.A00` une todos los MACs de 10 bytes en un solo array de bytes |
| Video / audio | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); tamaño de chunk **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Imagen progresiva | `firstScanSidecar` (**18**) con `firstScanLength` (**19**): un chunk de `ceil(len/16)*16` bytes; `scansSidecar` (**21**) con `scanLengths` (**22**): tamaños de chunk variables (`P1Y`) |
| Sticker | `firstFrameSidecar` (**12**) con `firstFrameLength` (**11**) |
| Ajustes | la prop de servidor `streaming_upload_chunk_size` es un token de diccionario; su efecto: unknown |
| Faltante | estado de descarga 30 `failed_no_sidecar` |
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
|------|-------|
| `surface` | `mms` (normal), `newsletter` (canales), `optimistic` (subida pre-envío); `AbstractC58025Pzy` |
| `type` | string de ruta de `MmsType` (sección 3), p. ej. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | base64 estándar de `fileEncSha256` con `+` a `-` y `/` a `_`; el padding `=` se conserva (`StringUtils.A0B`) |
| `direct_ip` | 1 cuando la autoridad es una IP (`ip4`, o `[ip6]` entre corchetes), de otro modo 0 |
| `auth` | el token de auth de `media_conn`; añadido como parámetro de query por `K19.A03` |
| `stream=1`, `streaming=riff` | ambos fijados cuando la solicitud es una subida en streaming (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | solo para `newsletter-image` / `-status` (flag **11191**) y `newsletter-video` / `-status` (flag **11192**) |
| `server_transcode=1` | `newsletter-video` con request id 10 y flag **9096** |
| `_nc_rmr=1` | subidas no-newsletter (flag de request `A0N`) |
| `_nc_cbep=1` | cuando la request lo permite y el flag **17404** está activado (significado desconocido) |
| `type`, `media_id`, `media_id_upload` | `media_id` = los 63 bits más significativos de un UUID de subida; `media_id_upload` = los 63 bits menos significativos, solo cuando la request tiene entradas adicionales; `type` es un string del llamante (significado: unknown) |

El significado de los nombres de query `_nc_cbep` y `_nc_rmr` es unknown (solo nombres).

### 8.2 Token (found, `C43489Iy4.A00`)

| Caso | Token |
|------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes de java.util.Random))`, fresco por request, no atado al archivo |
| Otro | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` son 32 bytes de `SecureRandom`, creados una vez y almacenados en preferencias como `upload_token_random_bytes` (base64 sin wrap, sin padding) |

Si `fileEncSha256` no se puede decodificar, el token es `SHA-256(installSecret)` solo. Propósito de la construcción: inferido como un chequeo del lado servidor de que el que sube conoce el hash sin exponerlo en la ruta.

### 8.3 Solicitud HTTP (found, `HttpsFormPost` `C43478Ixt`)

| Ítem | Valor |
|------|-------|
| Biblioteca | `HttpsURLConnection` con un `SSLSocketFactory` personalizado; marcador `http_stack = HttpUrlConnection` |
| Método | POST (`setDoOutput(true)` en `HttpURLConnection`; sin llamada de método explícita) |
| Timeouts | conexión 15000 ms, lectura 60000 ms |
| Encabezados | `Host: <hostname de ruta>` (la autoridad puede ser una IP), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, opcional `Companion_User_Secret` (argumento de constructor no-nulo; semántica de companion inferida) |
| Cuerpo (ruta presente) | stream de ciphertext crudo, solo un archivo (`MMS4 upload only supports a single file`); modo de streaming de longitud fija cuando la longitud se conoce, de otro modo chunked (`setChunkedStreamingMode(0)`); buffer de 16384 bytes |
| Cuerpo (sin ruta) | `multipart/form-data` legacy con partes `Content-Disposition: form-data` |
| Aborto | en interrupción de hilo o flag de cancelación el stream se rellena (`UploadRequest/Post streaming padding bytes=`) para que la longitud declarada se complete (propósito inferido) |
| Respuesta | hasta 1 MiB leído; HTTP >= 400 devuelve el código, el cuerpo va a `onError` |

### 8.4 Respuesta (found, `MediaUploadTransfer` `C59523QnV`)

Claves JSON leídas: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (aceptado solo si coincide con `[A-Za-z0-9-]{1,64}`), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (string JSON anidado con `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. Una respuesta sin `direct_path` no es tratada como error por este parser; etapas posteriores fallan con `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Subida reanudable (found)

| Paso | Detalle |
|------|--------|
| Sonda | misma URL de subida más `resume=1` (`HttpResumeCheck`); respuesta JSON `{"resume": "complete"}` con `url`, `direct_path` (ya subido) o `{"resume": <offset>}` |
| Continuar | POST con `Content-Range: bytes <offset>-*/*`, el stream se salta hasta `<offset>` primero |
| Fallbacks | `ResumeCheck/attempting fallback MMS upload form post`, también tras un error WATLS (TLS) |
| Error de parseo | estado `PBY.A03`, la subida se reinicia |

### 8.6 Suministrador de ruta y retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Regla | Detalle |
|------|--------|
| Bucle de intentos | `TransferRetries/run attempt = N; route = ...`; una transferencia por ruta; `no routes` termina el bucle |
| Elección de host | host `type=primary` cuyo conjunto de capacidades contiene el tipo de media; los primeros dos intentos lo usan; intentos posteriores usan la entrada `type=fallback` y sus campos `fallback_*` (orden inferido del flujo de control confuso) |
| Intentos | por defecto 4 (`4 - extra`); con los flags **12545** y **12446** el límite puede sobreescribirse después del intento 3; `max_auto_download_retry` / `max_manual_retry` (por defecto 3 cada uno) alimentan el conteo dependiente del modo (mapeo inferido) |
| Retraso | constante 1000 ms (`RouteSelector.A01`); con el flag **257** e intentos extra, exponencial: base 1000 ms, `2^n`, jitter, con tope en 3000 ms |
| Error de auth 401 / 403 | no se cuenta como fallo: espera un token más nuevo (presupuesto `A0J`, 20000 ms por defecto), intercambia, reintenta |
| Estado HTTP reintentable | `QKS.A08`: < 400 sí; 400-499 no, excepto 408 con el flag **13748**; >= 500 sí, excepto 505 y 507 |
| Proxy | con un proxy de usuario y el flag **4073** la autoridad de media se vuelve el host y puerto del proxy desde `proxy_media_port` (por defecto 587) |
| Chequeo de salud | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, conexión 15000 ms, lectura 30000 ms |

---

## 9. Descarga

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

El constructor requiere un hash de media, una ruta directa o una referencia cruzada (`media hash, direct path, or cross reference is required`). `mode` es `auto` o `manual`. `_nc_map=whatsapp-nofna` se añade para tipos en la lista del servidor `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (prop AB, flag **4836**). El query `auth` se añade en una ruta con flag (`PTU.A03`) y reemplaza un parámetro `auth` existente. Las fotos de perfil usan tipo `ppic`; los assets estáticos usan `/wa/static` con `_nc_cat`.

### 9.2 Elección de bucket y host (flujo de control decompilado, parcialmente confuso)

- Los hosts se filtran por capacidad `download` y por que `download_buckets` contenga el string de bucket.
- Bucket `1` cuando la ruta directa lleva `_nc_hot=<segundos>` más joven que la ventana en el flag **2136**; de otro modo, con el flag **2134** y `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); bucket de fallback `0`.
- Los tipos de newsletter y casos con flag omiten la lógica hot / hash.
- El bucket elegido se envía como `_nc_cat`.

### 9.3 Solicitud HTTP (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Ítem | Valor |
|------|-------|
| Método | GET (Tigon o `HttpURLConnection`) |
| Encabezados | `Host: <hostname de ruta>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (con flag), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (cuando se conoce un ETag) |
| Aceptado | HTTP 200 y 206 |
| Parcial | las vistas previas usan un prefijo de 262144 bytes (`Range: bytes=0-262143`) |
| 416 | tratado como completo cuando `Content-Range` es `*/<size>` e iguala el tamaño local; de otro modo reinicio (flag **29305**) o error |
| Lista de permitidos | con el símbolo de flag `PTU.A04`, el host debe estar en `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` (coincidencia de sufijo) a menos que la URL tenga `category=PSA`; de otro modo `invalid_url` (8) / log `host not in media CDN allow-list` |

### 9.4 Verificación (found)

El stream de descifrado verifica el MAC; las etapas de hash se mapean a estados 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; las entradas faltantes se mapean a 26-30 (sección 10.2).

---

## 10. Códigos de error

### 10.1 Manejo de estado HTTP

| Estado | Comportamiento |
|--------|-----------|
| 401, 403 | refrescar `media_conn`, intercambiar auth, reintentar (máx. 2 intercambios) |
| 408 | reintentar solo con el flag **13748** |
| 416 | ver 9.3 |
| 507 | estado de descarga 12 `throttle`, no se reintenta |
| 505 | no se reintenta |
| otros 4xx | no se reintenta |
| 5xx, < 400 | se reintenta dentro del presupuesto de intentos |

### 10.2 Estado de descarga (found, `QKK` `A03`)

| Código | Nombre | Código | Nombre |
|------|------|------|------|
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

Los códigos 10, 22, 33 y cualquier otro imprimen `invalid`. `QKK.A04` agrupa 1, 2, 3, 11, 15, 16, 18, 19, 20 y 25 (fallos de tipo red; la etiqueta es inferida).

### 10.3 Resultado de subida (found, nombres de métrica `media_upload_<NAME>`)

| Código | Nombre | Código | Nombre |
|------|------|------|------|
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

Mapeo de excepciones en `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, otra `IOException` 18 (red caída) o 3, `CancellationException` 1, `C7CL` 21, cualquier otra cosa 31. Tras un resultado no exitoso con 5, 21, 24, 34, 35 o 36 la clave y hash cacheados (`A0B`, `A0C`) se limpian.

---

## 11. Reintento de media (solicitud de re-subida)

Cuando una descarga falla porque el objeto ya no existe (típicamente estado 5 `too_old`, o una respuesta de clase 404), el receptor le pide al teléfono del remitente que suba de nuevo.

### 11.1 Solicitud: recibo `server-error` (found, `SendMediaErrorReceiptJob`)

| Variante | Writer | Cable |
|---------|--------|------|
| Multi-dispositivo (propio primario) | caso 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Legacy | caso 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (sin `rmr`) |

`enc_iv` son 12 bytes aleatorios; `enc_p` se produce nativamente (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) a partir de un mensaje que lleva el stanza id. La biblioteca nativa guarda la info HKDF `WhatsApp Media Retry Notification`; AES-GCM con el stanza id como AAD y una clave HKDF de 32 bytes se infiere del IV de 12 bytes y de la implementación de Baileys. Las props de servidor `mms4_media_retry_notification_encryption_enabled` y `mms4_server_error_receipt_encryption_enabled` son tokens de diccionario (efecto inferido: controla si se envía `<encrypt>`).

### 11.2 Respuesta: notificación `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Paso | Detalle |
|------|--------|
| Chequeo de cuenta | `rmr` de otra cuenta registra `cross-account-rmr` y se descarta a menos que el símbolo de flag `PTV.A0F` esté activado |
| Búsqueda | mensaje por `(chat, id, from_me)`; los mensajes no-media registran `message is null or not media` |
| Descifrado | nativo (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); el modelo de resultado da `directPath` (almacenado en el mensaje) y un int de resultado |
| Resultado | `<error code>` sobrescribe el resultado; el manejador compara el valor con 2 y 3 (con la numeración proto pública `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferido) |
| Continuar | el descargador recibe la nueva ruta directa (`resume reuploading download`); sin descargador activo el mensaje se encola para descarga automática |
| Reporte | con el flag **5718** el `reporting_token` se almacena para el mensaje |

---

## 12. Media view-once y de estado

| Tema | Hecho (found) |
|-------|--------------|
| Cripto / transporte | idéntico al media normal: mismo `MmsType`, misma HKDF, mismas URLs; no existe ningún tipo view-once en la tabla |
| Flag | `viewOnce` es un campo en `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); contenedor `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Reglas locales | el remitente no puede abrir su propio media view-once (`senders can not view their own media`); las miniaturas view-once se eliminan por `EphemeralUpdateRunnable/deleteViewOnceThumbnails`; un audio view-once sin clave de media no se envía (`unable to send encrypted media message due to missing mediaKey`) |
| Si el servidor elimina el objeto tras la visualización | unknown |
| Estado (`status@broadcast`) | usa las filas normales de `MmsType` (imagen, video, gif, audio) con sus propios ids numéricos; no existe ninguna info HKDF de `status`; los únicos tipos `*-status` son los de newsletter (sección 13) |
| Límites de estado | los tokens de diccionario `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` son props de servidor (valores: unknown) |
| Descarga de estado | `C59526QnY` guarda un `MediaDownload` y una variante `StatusMediaDownload`; ambos construyen la URL con el mismo generador |

---

## 13. Media de newsletter (canal)

| Aspecto | Newsletter | Regular |
|--------|-----------|---------|
| Superficie en la URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | nombres simples |
| Cifrado | ninguno: el descargador de artwork requiere `artworkEncSha256` solo para contenido no-newsletter (`required fields missing - artworkEncSha256 is null for encrypted content`); para otros tipos existe el stream de paso directo `C59535Qnh` (identidad). Las filas de `MmsType` todavía llevan bytes de info HKDF (no usados, inferido) |
| Token de subida | aleatorio, no atado al hash (sección 8.2) | secreto por instalación + hash |
| Filtro de ruta | sin lógica de bucket hot / hash para nombres que empiezan con `newsletter` | lógica de bucket (9.2) |
| Token ip de `media_conn` | `ip_token` se aplica para newsletter sin importar `set_ip_token` (flag **12149**) | solo cuando `set_ip_token` es true |
| Trabajo del servidor | `server_thumb_gen=1` (flags **11191**, **11192**), `server_transcode=1` para video (flag **9096**) | no fijado |
| Flag **27920** | leído en la ruta de newsletter de `C15490gQ`; efecto unknown | |

---

## 14. Ruta express y otras variantes de subida

| Variante | Evidencia |
|---------|----------|
| Ruta express | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) enviado como mensaje E2E (`FMessageMediaExpressPathNotify`, requiere url, hash y longitud); `ExpressPathDownload` registra `EP gain <ms> <bytes>`; log de subida `Use static route supplier for express path upload`; resultado de subida 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Comportamiento del lado servidor: unknown |
| Subida optimista | superficie `optimistic`; resultados de re-chequeo de hash 12; protocolo: unknown |
| Historial / app state | `md-msg-hist`, `md-app-state` usan el pipeline normal con sus strings de info |
| Historial de grupo | `group-history`, info `Group History`, mime `application/protobuf` verificado por el receptor (`C34677F2y`); la ruta sigue la sección 8.1 (`/mms/group-history/...`, inferido de la composición genérica) |

### 14.1 Envío de wallpaper de tema de chat (nuevo en 2.26.45.10, found)

Un flujo de tema por chat "enviar al chat" viaja sobre este pipeline genérico sin modificar. Punto de entrada: `ChatThemeViewModel.sendThemeToChat` (coroutine de Kotlin; locales `targetJid`, `sentBundle`, `sharedTheme` a partir de metadata de debug preservada) resuelve la fuente de wallpaper elegida (`DOWNLOADED`, `USER_PROVIDED`, `ANIMATED`, `GRADIENT`, `DEFAULT`, `NONE`) y llama a `ChatThemeSettingSenderImpl.A06` → `A01`.

| Paso | Detalle (found) |
|------|-----------------|
| Copia local | el `File` de wallpaper fuente se copia al almacenamiento de la app bajo `chat_theme_sent_wallpapers/<uuid>.jpg` |
| Subida | `ChatWallpaperUploader.A00` envuelve `MediaUploadCoordinatorImpl.A0G` (el mismo pipeline `media_conn` → HKDF → AES-CBC → HMAC → POST de las secciones 1-8 arriba), solicitando el modo de cifrado `LX/8cp;->A02`, cuyo campo `value` es el string literal `"E2EE"` |
| Copia del resultado | el resultado de la subida (`SGq`) se copia campo por campo a un descriptor genérico de adjunto de media (`LX/8cr`): string de resultado de subida → ruta directa, bytes de clave de media, una marca de tiempo, y tres arrays de bytes más de hash/HMAC |
| Superficie de setter | el descriptor se empuja a través de `LX/1iA` (extiende `LX/19i`), la **misma interfaz genérica de setter de adjunto de media** que usan los constructores ordinarios de mensaje de imagen; sus campos se alinean posicionalmente con `directPath` (**11**), `mediaKey` (**8**), y los campos de byte `fileSha256`/`fileEncSha256` (**9**/**12**, sección 6) de `imageMessage` |
| Mimetype | `image/jpeg` se fija explícitamente en la misma llamada |

Esto se envía a un interlocutor de chat real (`targetJid`), no es una sincronización local de solo preferencia de visualización: para temas respaldados por imagen, el propio bitmap del wallpaper se re-codifica y sube a través de la ruta de media E2EE estándar, así que el cliente receptor descarga y descifra una imagen real en lugar de aplicar un preset de tema conocido. No se encontró ningún tipo de media de subida o sobrescritura de ruta HTTP a medida (a diferencia de `/mms/group-history` del historial de grupo, sección 14) para este flujo — parece reutilizar un `MmsType` existente (probablemente `image`, no confirmado por separado).

**Unknown**: el campo exacto oneof de `Message` que termina llevando este adjunto — `LX/19i`/`LX/1iA` son clases base compartidas grandes usadas por muchos tipos de mensaje salientes, y el sitio concreto de asignación más allá de sus setters no se alcanzó en esta pasada. También unknown: si una elección de tema de color sólido/sin wallpaper (`DEFAULT`/`NONE`) se envía en absoluto, o se queda solo local. No se encontró ningún tipo de mensaje protobuf nuevo ni op de GraphQL/MEX para esta función (verificado contra los diffs de proto y query de 2.26.41.6→2.26.45.10); la lectura más defendible es que esto viaja sobre un campo de mensaje de media existente, probablemente `imageMessage` en sí — **inferred**, no confirmado.

---

## 15. Hardening nativo de los parsers de media (found, strings y exports de las bibliotecas desempacadas)

81 objetos compartidos se desempacan del archivo superpack. Los parsers inseguros en memoria de bytes controlados por el atacante están o sandboxeados o reemplazados por Rust.

| Entrada | Componente | Hardening |
|-------|-----------|-----------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp compilado a WebAssembly y rebajado a C por wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), wrapper `whatsapp::security::LibwebpSandbox` en un sandbox thread-local; flag Java `sWebPSandboxEnabled`; log de fallo `sandboxed WebP decode failed: status=%d`; guardas `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib en un sandbox wasm2c / WASI-minrt (`GiflibSandbox`, `wasi::minrt`); clases JNI `SandboxedGifImage`, `SandboxedGifFrame`; guarda `Called memcpy for memory larger than the sandbox` |
| Archivos Ogg / Opus | `libwhatsapp.so` | sandboxes RLBox wasm2c para `libogg.wasm` y `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; log de trap `wasm2c sandbox trap: %s (code=%d)` |
| Parseo de contenedor y stream | crates Rust de `libwhatsapp.so` | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, segmentador DASH, listas de edición), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (valores de digital-source-type IPTC como `trainedAlgorithmicMedia`, C2PA) |
| Decodificación AV1 | `libdav1d.so` | dav1d **1.5.1** (string de versión); exporta la API `dav1d_*` |
| Codificación AV1 | `libwzav1.so` | versión 2.3.1; exporta solo `wz_encoder_*` y `wz_codec_version*`; sin símbolos de decodificador, así que no parsea bitstreams remotos |
| Frames H.264 / H.265 | `MediaCodec` de la plataforma | fuera de la app |

Los parsers en Rust fallan con panics (`assertion failed: ...`, `While parsing field '...' in ...`) en lugar de corrupción de memoria: found como strings, efecto inferido. El sandbox `rlbox` cubre libogg y opusfile en `libwhatsapp.so`; otras bibliotecas usan wasm2c sin el wrapper RLBox (inferido de los símbolos). Si cada ruta de media entrante llega a estos parsers antes de la interacción del usuario: unknown. Comportamiento dinámico (fuzzing, crashes en runtime): no probado.

---

## 16. Feature flags (ids tal como se leen en los call sites; nombres no resueltos)

| Flag | Dónde | Controla |
|------|-------|----------|
| **149** | `RouteSelector`, `C43951qe` | persistir y recargar `media_conn` en preferencias |
| **257** | constructor de `Mms4RouteSupplier` | objeto de backoff exponencial |
| **258** | `Mms4RouteSupplier.A03` | int: intentos extra para modo 0 |
| **2134** | `A02` | bucket de descarga basado en hash |
| **2136** | `A02` | ventana de contenido hot (long) |
| **4073** | `A00` | enrutar media a través del proxy de usuario |
| **4836** | `Mms4DownloadUrlGenerator` | lista de tipos de baja tasa de aciertos (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | manejo del token de reporte |
| **9096** | `QBE` | `server_transcode=1` (video de newsletter) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` para imagen / video de newsletter |
| **12149** | `RouteSelector.A0L`, `A03` | usar `ip_token` |
| **12545** / **12446** | `A05` | sobrescribir el límite de intentos tras el intento 3 |
| **13748** | `QKS.A08` | reintentar HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | puntos de entrada de `RouteSelector` | booleano entregado a la selección de ruta como el flag de subida (semántica no resuelta) |
| **24661** | `MediaCryptoProvider` | validación del dominio de clave no-E2EE |
| **29305** | `PlainDownloadTransfer` | manejo de 416 |
| **37982**, **38437** | `C43481Ixw` | propiedad de Tigon, timeout de request |

---

## 17. Baileys (`baron-baileys-v2`, lectura de código, nada probado)

| Aspecto | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Solicitud de `media_conn` | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` tiene una variante opcional `last_id` | siempre `<media_conn>`, con `last_id` cuando existe un id previo |
| Campos parseados | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | no se lee `maxContentLengthBytes`; añade `auth_ttl`, `max_buckets`, `is_new`, `id`, campos de fallback, hijos de capacidad, conteos de retry, `ip_token` |
| Longitud HKDF | `hkdf(key, 112, {info})`, usa los bytes 0-79 | 80 bytes; los primeros 80 bytes de una salida HKDF no dependen de la longitud solicitada, así que IV, clave de cifrado y clave MAC son idénticos |
| Strings de info | `WhatsApp <X> Keys`; `gif` y `ptv` mapean a Video, `ptt` a Audio, `sticker` a Image | mismos strings y mapeos |
| Cifrado, MAC, hashes | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` añadido, `fileSha256`, `fileEncSha256` sobre `ct + mac` | igual |
| URL de subida | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Codificación de hash | base64 url-safe, padding `=` eliminado, luego `encodeURIComponent` | base64 url-safe, padding `=` conservado |
| Token | `fileEncSha256` url-safe | `SHA-256(installSecret || fileEncSha256)` (newsletter: aleatorio) |
| Tabla de rutas | `sticker` y `thumbnail-link` a `/mms/image`, `ptv` a `/mms/video`, `md-msg-hist` a `/mms/md-app-state`, sin `ptt` | el string `MmsType` es el segmento de ruta: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Encabezados | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | no se encontró `Origin`; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | intenta cada host una vez en orden | suministrador de ruta con intentos, intercambio de token en 401 / 403, sonda de reanudación |
| Reanudación | ninguna encontrada (`resume=1`, `Content-Range` ausente) | sonda `resume=1` y `Content-Range` |
| Sidecars | sin generación de `streamingSidecar`, `firstScanSidecar` o `scansSidecar` encontrada en `src` | generado para video, audio, imágenes progresivas |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | milisegundos internamente, segundos en el proto |
| Recibo de reintento | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = stanza id, IV 12 bytes, info HKDF `WhatsApp Media Retry Notification` | el caso writer 327 tiene la misma disposición de nodo; el IV de 12 bytes y el string de info son found; GCM / AAD inferido |
| Mapa de resultado de retry | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | no aplica (compara valores 2 y 3) |

Consecuencias prácticas (solo lectura de código): una subida de Baileys de un objeto `md-msg-hist` usa un string de ruta distinto al del cliente Android; el base64 con padding en la ruta es una diferencia visible; cualquier tolerancia del servidor para estas variantes es unknown.

---

## 18. Casos de error

| Síntoma | Causa | Arreglo |
|---------|-------|-----|
| Subida 401 / 403 | `auth` expirado o reemplazado | refrescar `media_conn`, reenviar con el nuevo `auth` |
| La subida no devuelve `direct_path` | subida rechazada o incompleta | verificar el estado; sonda de reanudación con `resume=1` |
| Descarga 404 / estado 5 `too_old` | objeto expirado en el CDN | enviar el recibo `server-error` (sección 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | bytes corruptos o `fileEncSha256` incorrecto | volver a obtener; verificar la fuente del hash |
| Falla el chequeo de MAC | clave de media incorrecta, info HKDF incorrecta (mezcla de tipos), o archivo truncado | usar el string de info del `MmsType` correcto; no reutilizar la info de Image para filas `sticker-pack` o `ptt` |
| `invalid_url` (8) | host fuera de la lista de permitidos del CDN | aceptar solo los sufijos listados |
| `throttle` (12), HTTP 507 | throttle del servidor | esperar `backoff` segundos (máx. 10800) |
| `no_route` (11) | ningún host usable de `media_conn` para el tipo | solicitar `media_conn`, verificar los tags de capacidad |
| `failed_no_media_key` (29), `no_sidecar` (30) | campo proto faltante | requerir `mediaKey`; sidecar solo para streaming |

---

## 19. Distinciones clave

| No confundir | Hecho |
|----------------|------|
| lista de hosts de `media_conn` vs URL de subida | el IQ da hosts y un `auth`; la ruta, token y query de la URL se construyen por transferencia |
| `auth` vs `token` | `auth` es el token de nivel cuenta de `media_conn`; `token` es por archivo |
| HKDF 80 vs 112 bytes | mismas claves; Android deriva 80 |
| `fileSha256` vs `fileEncSha256` | hash de texto plano vs hash de `ciphertext + mac10` |
| `fileEncSha256` en la ruta vs `directPath` | la ruta de subida usa el hash; la descarga usa el `directPath` devuelto por el servidor |
| `mediaKeyTimestamp` vs ventana de reutilización de clave | marca de tiempo en segundos en el cable; ventana de reutilización de 2-3 días en el remitente |
| Sidecar de streaming vs `fileEncSha256` | MACs de 10 bytes por chunk vs hash del archivo completo |
| Reintento de media vs reenvío | el remitente re-sube el mismo objeto y responde con un nuevo `directPath`; el mensaje no se reenvía |
| Media de newsletter vs media regular | sin cifrar, superficie `newsletter`, token aleatorio |
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

## 21. Incógnitas

| Ítem | Estado |
|------|--------|
| Comportamiento del servidor (validación de token, deduplicación, duración del objeto, eliminación view-once) | lado servidor |
| Nombres de query `_nc_cbep`, `_nc_rmr`, `type`; flag **21807** y los ids `PTU.*` | nombres o significado no resueltos |
| Ids numéricos en `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | significado no resuelto |
| Cifrado nativo de reintento de media (AES-GCM, AAD, longitud de clave) | string de info found; algoritmo inferido |
| Consumo de `ip_token`, valor de `X-FB-nc-oc`, fuente de `Companion_User_Secret` | no resuelto |
| Uso del dominio de clave de media NON_E2EE | no resuelto |
| Protocolos de ruta express y subida optimista | no resueltos |
| Orden exacto de hosts a través de los intentos y los conteos de intento dependientes del modo | flujo de control decompilado confuso |
| Qué media entrante llega a qué parser sandboxeado antes de la interacción del usuario | no mapeado |
| Tráfico | nada capturado; sin prueba dinámica |
