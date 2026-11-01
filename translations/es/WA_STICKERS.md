<!-- src-sha1: d4ba76d600d4bfecb03ea6dfec4064e9d1ae1733 -->
# WhatsApp Stickers — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** proto `Message.StickerMessage` (metadatos de imagen/Lottie, flags de avatar/AI/premium, `emojis`, `accessibilityLabel`), sound stickers embebidos (`StickerMessage.audioMessage`), wrappers genéricos `lottieStickerMessage` / `audioStickerMessage`, `stickerPackMessage` (compartir pack), almacenamiento local de sticker packs y el formato ZIP `.was`/Lottie, `stickerSyncRmrMessage` (confirmado ausente), intents de terceros para sticker packs y el contrato de content-provider, proveedor nativo de generación de stickers con AI, búsqueda local de stickers, feature flags; la criptografía de media no se repite (ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md))

---

## 1. Visión general

Un "sticker" en Android es uno de varios tipos de mensaje de wire más un subsistema de app propio y grande (store, recientes locales, búsqueda, generación con AI) y una superficie de integración pública de terceros (intents + content providers). Todos los bytes de media (imagen del sticker, ZIP del pack, thumbnails) viajan por el mismo pipeline de media cifrada que cualquier otro adjunto — ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) sección 3 para las filas de `MmsType` (`sticker`, `sticker-pack`, `thumbnail-sticker-pack`, `newsletter-sticker`, `newsletter-sticker-pack`).

| Entidad | Campo de `Message` | Tipo de wire | Rol |
|--------|------------------|-----------|------|
| Sticker individual | `stickerMessage` | **26**, `StickerMessage` (`C30611DTf`) | una imagen/animación de sticker enviada en un chat |
| Sound sticker (embebido) | `StickerMessage.audioMessage` | **26** de `StickerMessage`, `oneof audio` → `AudioMessage` | un clip de voz corto adjunto a un envío de sticker |
| Wrapper Lottie | `lottieStickerMessage` | **74**, `FutureProofMessage` (`BD2`) | envoltorio genérico, el nombre sugiere un payload específico de Lottie; contenido anidado sin resolver |
| Wrapper audio-sticker | `audioStickerMessage` | **134**, `FutureProofMessage` (`BD2`) | mismo patrón de envoltorio genérico, nuevo en este build; contenido anidado sin resolver |
| Sticker pack | `stickerPackMessage` | **86**, `StickerPackMessage` (`C30610DTe`) | comparte/instala un pack (ZIP de stickers) |
| Solicitud de sync de sticker | `stickerSyncRmrMessage` | **47** (builds antiguos) | **ausente** del proto `Message` en 2.26.41.6 (ver sección 7) |
| Reacción de sticker en status | `statusStickerInteractionMessage` | **110**, `StatusStickerInteractionMessage` (`C30560DRg`) | sticker de reacción en una publicación de status; fuera de alcance aquí más allá de esta referencia |
| Añadir pack de terceros | `Intent` de Android | `com.whatsapp.intent.action.ENABLE_STICKER_PACK` | una app externa pide a WhatsApp que importe un pack que ella misma hospeda |
| Envío de terceros | `Intent` de Android | `com.whatsapp.intent.action.SEND_STICKER` | una app externa entrega un único sticker WebP al selector de WhatsApp |
| Contrato de contenido de pack | `ContentProvider` (propio de la app externa) | `content://<authority>/metadata`, `/stickers`, `/stickers_asset` | cómo WhatsApp lee un pack de terceros |
| Generación de stickers con AI | `ContentProvider` (propio de WhatsApp) | `content://com.whatsapp.provider.sticker_command/generate` | creación de stickers con GenAI dentro de la app, consumida vía llamadas a content-provider, no un mensaje de chat |

Los niveles siguen `IMPORTANT.md`: **found** = leído directamente en código/strings/manifest decompilados, **inferred** = deducido de la forma del código, **unknown** = sin resolver. Toda la evidencia aquí es estática (APK decompilado + manifest); nada se capturó en el wire.

---

## 2. `Message.StickerMessage` (campo 26)

### 2.1 Campos (found, `C30611DTf`)

| Campo | # | Tipo | Uso |
|-------|---|------|-----|
| `url` | 1 | string | URL completa legacy |
| `fileSha256` | 2 | bytes | hash en claro |
| `fileEncSha256` | 3 | bytes | hash de ciphertext+MAC, también el hash de la ruta de subida |
| `mediaKey` | 4 | bytes | clave de 32 bytes, HKDF info `WhatsApp Image Keys` (pipeline de media, no repetido aquí) |
| `mimetype` | 5 | string | `image/webp` para stickers ordinarios |
| `height` / `width` | 6 / 7 | uint32 | dimensiones en píxeles |
| `directPath` | 8 | string | ruta de descarga |
| `fileLength` | 9 | uint64 | longitud del ciphertext |
| `mediaKeyTimestamp` | 10 | int64 | segundos |
| `firstFrameLength` / `firstFrameSidecar` | 11 / 12 | uint32 / bytes | sidecar para el primer frame de la animación (ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) sección 7) |
| `isAnimated` | 13 | bool | WebP animado |
| `pngThumbnail` | 16 | bytes | thumbnail inline |
| `contextInfo` | 17 | `ContextInfo` | metadatos de cita/respuesta/ad |
| `stickerSentTs` | 18 | int64 | timestamp de envío |
| `isAvatar` | 19 | bool | sticker de avatar |
| `isAiSticker` | 20 | bool | sticker generado con AI |
| `isLottie` | 21 | bool | el payload del sticker es una animación Lottie, no un WebP plano (ver sección 4) |
| `accessibilityLabel` | 22 | string | texto para lector de pantalla |
| `premium` | 24 | int32 | sin resolver (no se encontró consumidor) |
| `emojis` | 25 | string | **uso found**: tag de búsqueda local, ver sección 9 |
| `audioMessage` | 26 | `AudioMessage` (`oneof audio`) | clip embebido de sound-sticker, ver sección 3 |

Huecos de número de campo 14, 15, 23: sin campo definido; uso previo desconocido. Esto corrige la nota inicial de `Messages/stickerMessage`, que lista `emojis` (25) como el último campo y no incluye el campo 26 (`audioMessage`) en absoluto — confirmado presente en `C30611DTf` en 2.26.41.6 (`AUDIO_MESSAGE_FIELD_NUMBER = 26`) y coincide con el bloque `oneof audio` del proto actual de `baron-baileys-v2`.

### 2.2 Clasificación por string de tipo de mensaje (found)

Strings de tipo observados vinculados a un envío de `StickerMessage`/`StickerPackMessage`, recolectados del dispatch de analytics (`C21880sC`) y del helper de tipo de sticker: `sticker`, `avatar_sticker`, `genai_sticker`, `1p_sticker`, `user_created_sticker`, `sticker_pack`. `avatar_sticker` y `genai_sticker` provienen de `isAvatar`/`isAiSticker`; `1p_sticker` y `user_created_sticker` se corresponden con el enum `StickerPackOrigin` (sección 5) pero la función de decisión exacta que elige entre `sticker`, `1p_sticker` y `user_created_sticker` no se aisló en este pase (precedencia desconocida). Baileys (`messages-send.js`) comprueba `isLottie` antes de `isAvatar` al derivar este string en el cliente; no se confirmó si Android hace lo mismo.

### 2.3 `emojis` y `accessibilityLabel` (found, mejorado respecto al material inicial)

- `emojis` (25): consumido por `EmojiGroupMapper`/`StickerSearchManager` como el string de tag de búsqueda local — confirma su propósito más allá del nombre del campo (sección 9). No se consulta al servidor.
- `accessibilityLabel` en un *sticker enviado* y `sticker_accessibility_text` en un *sticker de pack de terceros* (`StickerContentProviderFetcher`, sección 8) ambos tienen un tope de **125** caracteres para un sticker estático y **250** para uno animado (`ThirdPartyStickerFetcher`, literales enteros 125/250; JADX muestra mal la rama de 125 como un campo no relacionado `C30628DTw.SPLIT_PAYMENT_MESSAGE_FIELD_NUMBER` porque ese campo también tiene por casualidad el valor 125 — un artefacto de nombrado del decompilador, el valor numérico en sí se lee directamente del bytecode).

---

## 3. Sound stickers: `StickerMessage.audioMessage` y `audioStickerMessage` (134)

Dos mecanismos distintos, ambos found, no deben confundirse:

| Mecanismo | Campo | Evidencia |
|-----------|-------|----------|
| Clip embebido | `StickerMessage.audioMessage` (26, `oneof audio`) | presente en `C30611DTf`; coincide exactamente con el `WAProto.proto` de `baron-baileys-v2` (`oneof audio { Message.AudioMessage audioMessage = 26; }`) |
| Wrapper independiente | `Message.audioStickerMessage` (134, `FutureProofMessage`/`BD2`) | campo nuevo en `C30628DTw` para 2.26.41.6, no presente en el material inicial de `Messages/`; mismo patrón de envoltorio genérico que `lottieStickerMessage` (sección 1), contenido anidado desconocido |

El paquete de soporte del cliente `com.whatsapp.stickers.sound` confirma una funcionalidad de autoría de "sound sticker": `StickerOpusEncoder` (`nativeEncode(short[] pcm, String outPath)`, codificación Opus nativa de un clip grabado) y `SoundStickerAudioDownloader` (asegura que el audio adjunto se descargue antes de la reproducción, enrutando por el pipeline de media habitual). Esto es consistente con embeber una nota de voz corta vía el campo 26 en lugar de (o junto con) el wrapper más nuevo del campo 134.

---

## 4. Formatos de archivo de sticker

### 4.1 WebP plano y animado (found)

`mimetype = image/webp`; `isAnimated` marca un WebP animado. La decodificación pasa por el libwebp en sandbox de `libstatic-webp.so` (ver [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) sección 15).

### 4.2 Stickers Lottie — contenedor ZIP `.was` (found, `LottieStickerZipEntrySaver` / `C161836tL`)

Cuando `isLottie` está activo, el archivo de media del sticker no es un WebP: es un archivo ZIP, guardado y leído mediante un `LottieStickerZipEntrySaver`, que debe contener:

| Entrada | Rol |
|-------|------|
| `animation/animation.json` | la animación Lottie (bodymovin) JSON, primaria |
| `animation/animation.json.trust_token` | token de confianza/firma acompañante para el JSON |
| `animation/animation_secondary.json` + `.trust_token` | variante de animación secundaria opcional |

Un extractor genérico a nivel de pack (`C161826tK`, log tag `StickerPackZipEntrySaver`, clase base `SafeZipEntrySaver`) además restringe las extensiones de archivo extraídas mediante allow-list a `png`, `webp` y `was` — es decir, la extensión pública de archivo `.was` ("WhatsApp Animated Sticker") es el marcador en disco/entrada de ZIP de este contenedor Lottie, verificado contra el MIME declarado (`application/was`) mediante un sniffer de contenido antes de aceptarse.

### 4.3 Límites de extracción del ZIP del pack (found, constructor de `C161826tK`)

| Límite | Valor |
|-------|-------|
| Máximo de entradas por ZIP de pack | **65** (hard-coded) |
| Máximo de bytes por entrada | token de diccionario (flag id **1900**, KB) × 1024 |
| Máximo de bytes totales por pack | mismo token × 1024 × 65 |
| Path traversal | la ruta destino de cada entrada se canonicaliza y debe resolver dentro del directorio propio del pack ("Zip entry is attempting to save outside of current directory") antes de escribir ningún byte — guard zip-slip |
| Entrada rechazada | eliminada tras fallar el sniff de tipo de contenido, se registra `StickerPackZipEntrySaver/file in zip is not valid` |

Esto corrobora y amplía la nota inicial de `Messages/stickerPackMessage` (que citaba "ZIP extraction and file validation" y "validates sticker files reside within extracted ZIP boundaries" de 2.26.34.4 solo como una referencia de log, sin los límites).

---

## 5. `Message.StickerPackMessage` (campo 86)

### 5.1 Campos (found, `C30610DTe`) — coincide exactamente con el material inicial y con `baron-baileys-v2`

| Campo | # | Tipo |
|-------|---|------|
| `stickerPackId` | 1 | string |
| `name` | 2 | string |
| `publisher` | 3 | string |
| `stickers` | 4 | repeated `Sticker` |
| `fileLength` / `fileSha256` / `fileEncSha256` / `mediaKey` / `directPath` / `mediaKeyTimestamp` | 5, 6, 7, 8, 9, 13 | referencia de media del ZIP del pack (`MmsType` `sticker-pack`, HKDF info `WhatsApp Sticker Pack Keys`) |
| `caption` | 10 | string |
| `contextInfo` | 11 | `ContextInfo` |
| `packDescription` | 12 | string |
| `trayIconFileName` | 14 | string |
| `thumbnailDirectPath` / `thumbnailSha256` / `thumbnailEncSha256` / `thumbnailHeight` / `thumbnailWidth` | 15–19 | thumbnail del pack (`MmsType` `thumbnail-sticker-pack`) |
| `imageDataHash` | 20 | string |
| `stickerPackSize` | 21 | uint64 |
| `stickerPackOrigin` | 22 | enum `StickerPackOrigin` |

`Sticker` anidado: `fileName` (1), `isAnimated` (2), `emojis` (3, repeated), `accessibilityLabel` (4), `isLottie` (5), `mimetype` (6), `premium` (7).

`StickerPackOrigin`: `FIRST_PARTY` = 0, `THIRD_PARTY` = 1, `USER_CREATED` = 2.

### 5.2 Almacenamiento local (found, `AbstractC149676Ty.java`, `C1888782f.java`, `C0R5.java`)

| Tabla | Columnas |
|-------|---------|
| `message_sticker_pack` | `message_row_id`, `sticker_pack_id`, `pack_name`, `pack_description`, `publisher`, `tray_icon_file_name`, `image_data_hash`, `sticker_pack_size`, `sticker_pack_origin`; indexada por `pack_name` y `publisher` |
| `message_sticker_pack_stickers` | `_id`, `message_row_id`, `file_name`, `is_animated`, `emojis`, `accessibility_label`, `is_lottie`, `mimetype` |

Esto sustituye el puntero del material inicial a la versión 2.26.34.4 (`StickerPackMessageMapper` / `message_sticker_pack`, citado solo por string de log) con la lista concreta de columnas de 2.26.41.6.

---

## 6. `stickerSyncRmrMessage` — confirmado ausente en 2.26.41.6

El campo 47 (`StickerSyncRMRMessage`: `filehash` repeated string, `rmrSource` string, `requestTimestamp` int64) **no** aparece en `C30628DTw` (el contenedor `Message`) para 2.26.41.6: ningún número de campo 47 lo mapea, y no existe ninguna clase o string que contenga `StickerSyncRMR`/`stickerSyncRmr` en ningún lugar del árbol decompilado. Esto coincide y amplía la propia observación del material inicial de que el campo ya estaba ausente en 2.26.36.1 — sigue ausente cinco builds después. Según el contrato de evidencia, esto es una **ausencia observada**, no una eliminación confirmada: si fue renombrado, movido a otro proto, o eliminado del todo es desconocido.

Todavía existe una tabla con clave por `filehash`, pero con un propósito no relacionado: `RecentStickerDBStorage` (`C6VB`, `C17460jr`, `C6V8`) rastrea stickers enviados/recibidos localmente por hash de archivo para la bandeja de recientes — esto es contabilidad local, no el mensaje de sync del wire, y no debe confundirse con él.

---

## 7. API de sticker packs de terceros

Esta es una superficie de integración pública, documentada por convención (familia de permisos `com.whatsapp.sticker.READ`); todo lo siguiente es found en `AndroidManifest.xml` y las clases que lo respaldan.

### 7.1 Superficie del manifest

| Componente | Declaración |
|-----------|-------------|
| Permiso | `com.whatsapp.sticker.READ` — requerido como `android:readPermission` en el content provider propio de una app de terceros antes de que WhatsApp lo consulte |
| Activity de añadir pack | `com.whatsapp.stickers.ui.thirdpartystickers.AddThirdPartyStickerPackActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.ENABLE_STICKER_PACK` + `category DEFAULT` |
| Alias legacy de añadir pack | `activity-alias` `com.whatsapp.stickers.thirdpartystickers.AddThirdPartyStickerPackActivity` → mismo destino (mantenido para apps compiladas contra el nombre de paquete pre-refactor) |
| Activity de enviar un único sticker | `com.whatsapp.stickers.command.send.SendStickerCommandActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.SEND_STICKER` + `category DEFAULT` + `data mimeType="image/webp"` |
| Provider de verificación de whitelist | `com.whatsapp.provider.sticker_whitelist_check` → `WhitelistPackQueryContentProvider`, `exported="true"` |
| Deep link | `whatsapp://stickerpack` (`<data android:host="stickerpack" android:scheme="whatsapp"/>`); la activity/ruteo de destino para este host específico no se aisló en este pase (unknown) |

### 7.2 Contrato del intent `ENABLE_STICKER_PACK` (found, `AddThirdPartyStickerPackActivity`)

Extras de la solicitud (`String`): `sticker_pack_id`, `sticker_pack_authority`, `sticker_pack_name`.

Validación antes de buscar nada:
1. `getCallingActivity()` debe ser no nulo (el intent debe venir de `startActivityForResult`, no de un lanzamiento tipo broadcast).
2. `PackageManager.resolveContentProvider(sticker_pack_authority, …)` debe resolver a un provider.
3. El paquete del provider resuelto debe ser igual al paquete de la activity que llama — **una app solo puede responder por authorities que ella misma posee**.

Extras del resultado en el `Intent` devuelto (uno de): `add_successful=true`, `already_added=true`, `validation_error=<string>`, o `CancelReason.USER_CANCELLED=true` (el usuario cerró el diálogo de añadir).

### 7.3 Contrato del content-provider de contenido de pack (found, `StickerContentProviderFetcher`/`C179697lN`, `C175327dG`)

WhatsApp lee un pack de terceros consultando el provider *propio de la app que llama* en la authority dada, condicionado a `readPermission == "com.whatsapp.sticker.READ"` en ese provider:

| URI | Columnas devueltas |
|-----|-------------------|
| `content://<authority>/metadata/<identifier>` | `sticker_pack_identifier`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_icon`, `android_play_store_link`, `ios_app_download_link`, `image_data_version`, `whatsapp_will_not_cache_stickers`, `animated_sticker_pack` |
| `content://<authority>/stickers/<identifier>` | `sticker_file_name`, `sticker_emoji`, `sticker_accessibility_text` |
| `content://<authority>/stickers_asset/<identifier>/<filename>` | stream abrible (icono de bandeja o archivo de sticker individual) |

Validación encontrada en el fetcher: `authority`/`identifier` rechazan caracteres inválidos; `identifier` ≤ 128 caracteres; el `sticker_pack_identifier` devuelto debe reflejar el identifier solicitado; el nombre de archivo de `sticker_pack_icon` ≤ 128 caracteres; `android_play_store_link` debe contener `play.google.com`, `ios_app_download_link` debe contener `itunes.apple.com` o `apps.apple.com`; `publisher`/`name` no vacíos y ≤ 128 caracteres; el id de `tray` no vacío; el conteo de stickers debe estar dentro de `[flag 17124, flag 17327]` inclusive (límites de token de diccionario, valores numéricos no resueltos en este pase); cada asset de sticker obtenido tiene un tope de **~103424 bytes (101 KB)** para un pack estático o **~512512 bytes (500,5 KB)** para uno animado (`Math.min(animated ? 500 : 100, 1024) + 1) * 1024`; los streams sobredimensionados o no legibles se descartan con el archivo puesto a null en lugar de abortar todo el pack. Una ruta relacionada `app may have been deleted` / `third_party_sticker_app_deleted` maneja la desaparición del paquete del provider a mitad del fetch.

Un flag booleano separado (**13081**) controla si un pack ya en whitelist se vuelve a buscar en el content provider o se sirve desde cache, y el flag **22198** alterna entre un flujo de añadir antiguo con diálogo síncrono y el ruteo directo a la pantalla de previsualización del sticker pack; el flag **13711** selecciona entre dos variantes internas de instalación (`C175327dG.A00` vs `A01`) al instalar vía la ruta de shortcut del content-provider (sección 7.5) en lugar de la activity.

### 7.4 Contrato del intent `SEND_STICKER` (found, `SendStickerCommandActivity`)

Datos: una URI `content://`, del provider propio de la app que llama, cuya authority debe resolver a ese mismo paquete que llama. El archivo referenciado debe decodificar como exactamente **512×512** WebP y pesar ≤ **500000 bytes**; el cliente lo re-estampa a través del pipeline normal de sticker (hash, almacenar, adjuntar) y adjunta estos extras de `Intent` como metadatos de pack `Sticker` si están presentes: `sticker_accessibility_text`, `sticker_pack_id`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_ios_store_link`, `sticker_pack_play_store_link` (los dos enlaces de tienda se validan con las mismas comprobaciones de dominio de la sección 7.3).

### 7.5 Provider de verificación de whitelist (found, `WhitelistPackQueryContentProvider`)

`content://com.whatsapp.provider.sticker_whitelist_check/<match>?authority=<pkg-authority>&identifier=<pack-id>` — cursor de una sola fila, una sola columna (`result`, `0`/`1`) que responde "¿este pack ya está añadido?". La validación de quien llama refleja la 7.2: el paquete que llama debe ser igual al paquete que posee la `authority` consultada. Tipo MIME devuelto por `getType()`: `vnd.android.cursor.item/vnd.com.whatsapp.provider.sticker_whitelist_check.is_whitelisted`.

### 7.6 Provider interno de comandos de sticker (found, `StickerCommandProvider`, `com.whatsapp.provider.sticker_command`, `exported="true"`)

No forma parte del contrato de terceros anterior — este es el provider propio de WhatsApp, consultado por las propias superficies de UI/asistente de WhatsApp, con dispatch por último segmento de ruta de la URI:

| Ruta | Comportamiento |
|------|-----------|
| `installPack?authority=&identifier=` | instala un pack vía la misma ruta de fetch/validación `C175327dG` de la sección 7.3, saltándose la UI de la activity |
| `removePack?authority=&identifier=` | desinstala un pack previamente añadido |
| `generate?prompt=` | generación de sticker con AI (sección 8); la longitud del prompt debe ser de 3–200 caracteres tras el trim |
| `availability` | devuelve `{available, consent_required}` para la generación de stickers con AI |
| `image/<token>` (vía `openFile`) | transmite de vuelta un sticker generado en PNG/WebP por token opaco, MIME `image/webp` |

---

## 8. Stickers generados con AI (found, `AiStickerCommands`, `StickerCommandProvider`)

`isAiSticker` (campo 20) marca un `StickerMessage` como generado con AI; el string de tipo es `genai_sticker` (sección 2.2). La generación en sí se dispara desde la UI local a través de la ruta del provider `generate` (7.6): las compuertas de elegibilidad (`C174467bs.A00`) y consentimiento (`A02`) se comprueban antes de cualquier llamada de generación; los resultados vuelven como una lista de `token`s opacos resueltos más tarde mediante `image/<token>`. El backend de generación real (en el dispositivo vs. del lado del servidor) es desconocido desde esta ruta de código — solo se resolvió la lógica del lado del cliente de elegibilidad/consentimiento/token.

---

## 9. Búsqueda de stickers (found, `StickerSearchManager`, `EmojiGroupMapper`, paquete de sugerencias contextuales)

Completamente local, no es una consulta al servidor. `StickerSearchManager.A00` toma una consulta en texto libre, la resuelve a un conjunto de caracteres emoji vía `EmojiGroupMapper`, los une en un string separado por espacios, y hace coincidir ese string contra el campo `emojis` **almacenado localmente** de cada `StickerMessage`/`Sticker` de pack (sección 2.3) más candidatos usados recientemente/destacados, dividiendo los resultados en los grupos "coincidencia exacta de emoji" vs. "otros" y truncando a un límite de token de diccionario (flag **22573**). Un flag `includeAvatarResults` separado condiciona si los stickers de avatar participan, protegido detrás de su propia comprobación de elegibilidad. Esto confirma — y eleva de "puede contener… desconocido" a found — que el campo string `emojis` del proto es la clave de índice de búsqueda del lado del cliente, no solo una etiqueta de visualización.

---

## 10. Cifrado de media (enlace, no repetido)

Toda referencia de media que lleva un sticker (`stickerMessage`, `stickerPackMessage`, sus thumbnails) pasa por el pipeline de media idéntico documentado en [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md): clave de media aleatoria de 32 bytes, HKDF-80 (`WhatsApp Image Keys` para `sticker`, `WhatsApp Sticker Pack Keys` para `sticker-pack`, `WhatsApp Sticker Pack Thumbnail Keys` para el thumbnail del pack, el manejo tipo `WhatsApp Image Thumbnail Keys` no se usa aquí — los thumbnails de sticker y de pack tienen sus propios strings info dedicados), AES-CBC + HMAC-SHA256 truncado a 10 bytes, `fileSha256`/`fileEncSha256`, hosts emitidos por `media_conn`, y la forma de URL de subida `/mms/<type>/<hash>`. Nada específico de stickers cambia nada de eso; ver las secciones 2–9 de ese informe para las tablas completas de derivación, reintento y códigos de error.

---

## 11. Feature flags (ids como se leen en los sitios de llamada; nombres sin resolver)

| Flag | Dónde | Controla |
|------|-------|----------|
| **1900** | constructor de `C161826tK` | presupuesto de tamaño (KB) de extracción del ZIP de pack, por entrada y agregado |
| **13081** | `AddThirdPartyStickerPackActivity` | re-fetch vs. cache para un pack de terceros ya en whitelist |
| **13711** | `StickerCommandProvider`, `AddThirdPartyStickerPackActivity` | selecciona la variante de ruta de instalación (`C175327dG.A00` vs `A01`) |
| **17124** / **17327** | `StickerContentProviderFetcher` | conteo mínimo / máximo de stickers aceptado de un pack de terceros |
| **22198** | `AddThirdPartyStickerPackActivity` | flujo de añadir con diálogo asíncrono vs. ruteo directo a pantalla de previsualización |
| **22573** | `StickerSearchManager` | límite de resultados de búsqueda local |

---

## 12. Baileys (`baron-baileys-v2`, lectura de código fuente, nada probado)

| Aspecto | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Campos de `Message.StickerMessage` | conjunto de campos idéntico incluyendo `audioMessage` (26, `oneof audio`) — el código fuente del proto coincide campo a campo con el layout decompilado de 2.26.41.6 | igual (sección 2.1) |
| Campos de `Message.StickerPackMessage` | conjunto de campos idéntico (1–22) | igual (sección 5.1) |
| Enviar un sticker | `prepareWAMessageMedia({ sticker })` construye `stickerMessage` a través de la ruta genérica de preparación de media (`MmsType` `sticker`, Image HKDF info); la opción `stickerAudio` adjunta un `audioMessage` preparado sobre `m.stickerMessage.audioMessage` | mismo pipeline de media según [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) sección 17 |
| Enviar un pack | la entrada `stickerPackMessage`/`stickerPack` se pasa a través de `StickerPackMessage.fromObject` sin validación adicional | el cliente además valida vía el extractor de ZIP y las restricciones de la DB (secciones 5, 6) antes de aceptar un pack que él mismo construye |
| Decodificación | `decode-wa-message.js` mapea `isAvatar`→`avatar_sticker`, `isAiSticker`/`isGenAI`→`genai_sticker`; `messages-send.js` mapea `isLottie`→`1p_sticker` antes de `isAvatar`/`sticker` plano al derivar el string de tipo saliente | mismos tres strings de tipo de mensaje encontrados en el dispatch de analytics de Android (`avatar_sticker`, `genai_sticker`, más `1p_sticker`/`user_created_sticker`); orden de precedencia exacto de Android sin confirmar (sección 2.2) |
| Intents/providers de pack de terceros | no implementado — Baileys no tiene superficie de `Intent`/`ContentProvider` de Android | superficie completa, sección 7 |
| Wrappers `lottieStickerMessage` / `audioStickerMessage` | presentes como un campo `FutureProofMessage` desnudo solo en el proto; no se encontró encoder/decoder dedicado | mismo envoltorio desnudo, tampoco se encontró manejo específico del campo (sección 3) |

---

## 13. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `ENABLE_STICKER_PACK` devuelve `validation_error` "cannot find the provider for authority" | el string `authority` de la app de terceros no resuelve a ningún provider instalado | la app que publica el sticker pack debe declarar y exportar su provider bajo esa authority exacta |
| `ENABLE_STICKER_PACK` devuelve "does not own authority" | el paquete que llama difiere del paquete del provider resuelto | una app solo puede responder por authorities dentro de su propio paquete |
| Añadir pack falla silenciosamente con "sticker count should be between X and Y" | la consulta `stickers` del pack devolvió un conteo de filas fuera de `[flag 17124, flag 17327]` | mantener el cursor de terceros `/stickers/<id>` dentro de los límites configurados por el servidor |
| `SafeZipEntrySaver: File being unzipped is too big` / "Too many files to unzip" | el ZIP del pack excede el presupuesto de bytes por entrada/agregado o el tope de 65 entradas | reducir el pack o dividir los stickers entre varios packs |
| `tray image name invalid` / error de longitud de nombre | el `sticker_pack_icon` de terceros contiene caracteres inválidos o excede 128 caracteres | sanear y acortar el nombre de archivo de la bandeja |
| `StickerPackZipEntrySaver/file in zip is not valid` | el tipo de contenido detectado de una entrada extraída no coincide con su extensión/MIME declarado | enviar entradas cuyos bytes realmente coincidan con `png`/`webp`/`was` |
| `the sticker is not a 512px WebP` (`SEND_STICKER`) | la imagen del intent de sticker individual no es exactamente 512×512 | redimensionar antes de enviar el intent |

---

## 14. Distinciones clave

| No confundir | Hecho |
|----------------|------|
| `StickerMessage.audioMessage` (campo 26) vs. `Message.audioStickerMessage` (campo 134) | el primero es un `AudioMessage` embebido confirmado dentro de un envío de sticker; el segundo es un campo wrapper de nivel superior separado, aún opaco, nuevo en este build |
| `isLottie` (flag por sticker) vs. `Message.lottieStickerMessage` (wrapper del campo 74) | el flag está vinculado a un formato de archivo concreto y found (ZIP `.was` con `animation/animation.json`); el payload anidado del campo wrapper aún está sin resolver — no se ha demostrado que sean el mismo mecanismo |
| `stickerSyncRmrMessage` (mensaje de wire, ausente) vs. `RecentStickerDBStorage` (tabla local con clave `filehash`) | el primero ya no existe en el wire en este build; el segundo es contabilidad local no relacionada que da la casualidad de que también tiene clave por hash de archivo |
| Contrato de pack de terceros (secciones 7.2–7.5, provider de la app externa) vs. `StickerCommandProvider` (sección 7.6, provider propio de WhatsApp) | ambos pueden "instalar un pack por authority+identifier", pero el primero es WhatsApp *leyendo el provider de otra app*, el segundo es el shortcut interno de WhatsApp alrededor de su propia UI de activity |
| Generación de stickers con AI (`isAiSticker`, flujo GenAI local) vs. apps de terceros de AI/sticker | el primero es la propia funcionalidad in-app de WhatsApp detrás de `StickerCommandProvider`; no tiene nada que ver con el contrato de content-provider de terceros |

---

## 15. Flujo: añadir un sticker pack de terceros

```
[Third-party app]  exports ContentProvider at authority X, readPermission=com.whatsapp.sticker.READ
     │  startActivityForResult(ACTION_ENABLE_STICKER_PACK, extras: sticker_pack_id, sticker_pack_authority=X, sticker_pack_name)
     ▼
[AddThirdPartyStickerPackActivity]  getCallingActivity() != null?
     │  resolveContentProvider(X) exists?  calling package == provider's package?
     ▼  (all pass)
[StickerContentProviderFetcher]  query content://X/metadata/<id>
     │  validate identifier echo, name/publisher length, tray icon name, store links
     ▼
[StickerContentProviderFetcher]  query content://X/stickers/<id>  (sticker_file_name, sticker_emoji, sticker_accessibility_text)
     │  validate count in [flag 17124, flag 17327], accessibility text ≤ 125/250 chars
     ▼
[StickerContentProviderFetcher]  openInputStream content://X/stickers_asset/<id>/<file>  per sticker + tray icon
     │  cap ~101 KB (static) / ~500.5 KB (animated) per asset
     ▼
[Client]  store pack + stickers, mark whitelisted (ThirdPartyWhitelistedPacksStore)
     │
     ▼
[AddThirdPartyStickerPackActivity]  result Intent: add_successful=true | already_added=true | validation_error=<reason>
     │
     ▼
[Third-party app]  onActivityResult()
```

---

## 16. Incógnitas

| Ítem | Estado |
|------|--------|
| Payload anidado de `lottieStickerMessage` (74) y `audioStickerMessage` (134) | el campo existe, wrapper genérico `FutureProofMessage`, contenido sin resolver |
| Precedencia exacta en Android para los strings de tipo `sticker` vs. `1p_sticker` vs. `user_created_sticker` | solo se encontró el mapeo en el bytecode de analytics, no la función que selecciona |
| Campo `premium` (24) en `StickerMessage`/`Sticker` | no se localizó consumidor |
| Valores numéricos detrás de los flags de token de diccionario 1900, 17124, 17327, 22573 | ids de token encontrados, valores en vivo no resueltos estáticamente |
| Activity de destino del deep link `whatsapp://stickerpack` | el host está declarado en el intent-filter de deep-link genérico del manifest; qué pantalla interna lo consume no se aisló |
| Backend de generación de stickers con AI (en el dispositivo vs. servidor) | solo se resolvió la lógica de elegibilidad/consentimiento/token del lado del cliente |
| Si el servidor aplica sus propios límites de tamaño/conteo de pack más allá de los del cliente | del lado del servidor, desconocido |
| El destino de `stickerSyncRmrMessage` (renombrado, movido o eliminado) | confirmado ausente del proto de wire desde 2.26.36.1 hasta 2.26.41.6; eliminación no confirmada |
| Tráfico | nada capturado; sin prueba dinámica |
