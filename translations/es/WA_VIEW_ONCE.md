<!-- src-sha1: b9a264b89fe2f15a6ff3587c9bc5a6b3a47e10c0 -->
# WhatsApp Ver una vez — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** el wrapper `viewOnceMessage` / `viewOnceMessageV2` / `viewOnceMessageV2Extension` frente al campo inline `viewOnce` en `ImageMessage` / `VideoMessage` / `AudioMessage` / `ExtendedTextMessage`, el mecanismo genérico de desenvoltura de wrappers de mensaje compartido con los mensajes temporales, los tipos de mensaje y la interfaz marcadora común, la aplicación en el cliente (bloqueo de captura/grabación de pantalla, restricción de reenviar/compartir/guardar, bloqueo de autovisualización del remitente, eliminación de medios citados), el almacenamiento local y la máquina de estados (`message_view_once_media`, job de eliminación), el ciclo de vida de la media key (enlazada, no repetida), el caso de wire `unavailable[type="view_once"]` y los tokens de lectura/escritura entre dispositivos, feature flags, comparación con Baileys

---

## 1. Qué es

Ver una vez es un atributo por mensaje, no un tipo de mensaje separado: cualquier imagen, video, mensaje de voz o (en builds recientes) texto puede marcarse para que el cliente del destinatario elimine la copia local tras abrirlo una vez, y además el cliente bloquea las capturas/grabaciones de pantalla y oculta reenviar/compartir/guardar mientras está abierto. Todas las afirmaciones son análisis estático del APK decompilado; nada fue capturado en la red. Niveles: **found** = leído en código, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres se resolvieron en 2.26.41.6 a partir de strings estables y tags de log (`AppDataManager/contributeMetaAppData`, `ConversationRowViewOnceMedia/`, `EphemeralUpdateRunnable/`, `ViewOnceMessageStore/`, ids de strings de UI).

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|-----------------|------|
| Mensaje wrapper (un campo, `message` **1**) | `BD2` | cuerpo de `viewOnceMessage` **37**, `viewOnceMessageV2` **55**, `viewOnceMessageV2Extension` **59** en `Message` (`C30628DTw`) |
| Flag inline por tipo de medio | `ImageMessage.viewOnce` **25**, `VideoMessage.viewOnce` **20**, `AudioMessage.viewOnce` **21**, `ExtendedTextMessage.viewOnce` **30** | se fija directamente en el mensaje de medio/texto, sin wrapper |
| Switch inline vs. wrapper | flag **8784** | activado: solo campo inline; desactivado: wrapper + campo inline ambos fijados (6.3) |
| Handler de imagen ver una vez | `C34670F2r` ("FMessageViewOnceImageProtobuf") | construye/lee `DdP`, tipo de mensaje **42** |
| Handler de video ver una vez | `C34671F2s` ("FMessageViewOnceVideoProtobuf") | construye/lee `C30972DdZ`, tipo de mensaje **43** |
| Handler de texto ver una vez | `F33` ("FMessageViewOnceTextProtobuf") | construye/lee `C31208Dhd`, tipo de mensaje **78** |
| Handler de audio ver una vez | `C34669F2q` ("FMessageViewOnceAudioProtobuf") | construye/lee `C30963DdH`, tipo de mensaje **82** |
| Interfaz marcadora | `InterfaceC24513Ahd` | implementada por las cuatro clases FMessage anteriores; usada para condicionar el comportamiento genérico de UI/menú |
| Tabla de estado local | `message_view_once_media` | columnas `message_row_id`, `state` |
| Accesor de estado | `C199158dT` ("ViewOnceMessageStore") | get/insert/update de `state` |
| Job de eliminación | `EphemeralUpdateRunnable` (clase anónima en `C199218dZ`), tipo de job **3** | "`ViewOnceMessageStore/getViewOnceMessagesToDelete`" |
| Helper de bloqueo de captura de pantalla | `C66572s0` | `window.addFlags(8192)` = `FLAG_SECURE` |
| Gate de ver una vez para el visor de medios | `C1ZB.A0O(i)` | `i == 42 \|\| i == 43` |
| Visor dedicado (texto/audio) | `ViewOnceViewerActivity`, `ViewOnceTextFragment`, `ViewOnceAudioFragment` | Activity separada, siempre `FLAG_SECURE` |
| Visor compartido (imagen/video) | `MediaViewFragment` / `MediaViewMenu` | visor de medios normal, `FLAG_SECURE` solo cuando `C1ZB.A0O` es true |
| Hojas educativas | `ViewOnceNuxBottomSheet`, `ViewOnceSecondaryNuxBottomSheet` | explicación mostrada una vez al remitente/receptor |
| Eliminador de medios citados | `F43` ("QuotedMediaCleanupSerializationPostProcessor") | elimina los bytes de medio de una cita de un mensaje ver una vez, flag **25572** |

---

## 2. Marcado en el proto

### 2.1 Campo inline (found)

```text
ImageMessage.viewOnce         = 25  (bool)
VideoMessage.viewOnce         = 20  (bool)
AudioMessage.viewOnce         = 21  (bool)
ExtendedTextMessage.viewOnce  = 30  (bool, VIEW_ONCE_FIELD_NUMBER)
```

Cada uno es un booleano plano en el mensaje normal de medio/texto; no se requiere un contenedor separado para transportarlo. Confirmado al leer las tablas de campos generadas de `C30612DTg` (Image), `C30614DTi` (Video), `DTX` (Audio), `C30613DTh` (ExtendedText).

### 2.2 Mensaje wrapper (found)

`viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**) y `viewOnceMessageV2Extension` (**59**) en `Message` son todos del tipo `BD2`, y `BD2` tiene exactamente un campo, `message` **1**, que a su vez es un `Message`. Los tres nombres de campo decompilan a la clase idéntica — son la misma forma de wrapper usada tres veces para tres generaciones del protocolo:

```java
public final class BD2 extends GeneratedMessageLite {
    public static final int MESSAGE_FIELD_NUMBER = 1;
    public C30628DTw message_;   // a full nested Message
}
```

### 2.3 Inline vs. wrapper: flag 8784 (found)

Cada handler por tipo (`C34670F2r` imagen, `C34671F2s` video, `F33` texto, `C34669F2q` audio) construye lo mismo dos veces y elige uno según un flag:

```java
boolean zA15 = this.A00.A15(8784);
...
if (zA15) {
    dp5.A0R(c30612DTg);                 // inline viewOnce=true directly on the outer Message
    return;
}
dp5A0f.A0R(c30612DTg);                  // same media message, but inside the BD2 wrapper
BD2 bd2A0Q = ...;
c30628DTwA0j.viewOnceMessageV2_ = bd2A0Q;
```

Con el flag activado, 2.26.41.6 nunca emite un wrapper para un mensaje ver una vez compuesto localmente; los handlers de recepción `CM7` en las mismas clases solo miran el flag inline (`c30612DTg.bitField0_ & ... && c30612DTg.viewOnce_`), no los campos del wrapper — desenvolver un wrapper hasta la forma inline es un paso genérico separado (2.4).

### 2.4 Desenvoltura genérica de wrapper (found)

Una tabla estática (`AbstractC33204EdH.A00`, 35 entradas) empareja un predicado de "tiene este wrapper" con un extractor de "obtener el `Message` interno" para cada wrapper de compatibilidad futura que el cliente conoce, incluyendo `ephemeralMessage` (wrapper de mensajes temporales), `viewOnceMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `documentWithCaptionMessage`, `botInvokeMessage`, `groupStatusMessage`, y otros. `C34748F5r` (validación de native-flow/`<biz>`, `AbstractC33204EdH.A00`) recorre esta tabla recursivamente hasta profundidad 10 para encontrar el contenido clasificable sin importar cuántos wrappers lo rodeen:

```java
for (EQR eqr : AbstractC33204EdH.A00) {
    if (hasWrapper(c30628DTw, eqr) &&
        A00(..., unwrap(c30628DTw, eqr), i + 1) != C02U.A00) {
        return result;
    }
}
```

`ephemeralMessage` y los tres wrappers de ver una vez son entradas pares en esta tabla — estructuralmente el mismo mecanismo, de modo que un mensaje ver una vez puede en principio anidarse dentro de, o junto a, un wrapper de mensajes temporales (sección 7). Esto refleja la propia lista `getFutureProofMessage()` de Baileys en `message-inspect.js`, que enumera el mismo conjunto de nombres de campo de wrapper.

---

## 3. Tipos de mensaje y la interfaz marcadora

| Tipo | Clase de medio | Handler | Fragment/Activity |
|------|-------------|---------|--------------------|
| **42** | `DdP` (imagen) | `C34670F2r` | `MediaViewFragment` (visor compartido de imagen/video) |
| **43** | `C30972DdZ` (video) | `C34671F2s` | `MediaViewFragment` |
| **78** | `C31208Dhd` (texto) | `F33` | `ViewOnceTextFragment` dentro de `ViewOnceViewerActivity` |
| **82** | `C30963DdH` (audio/ptt) | `C34669F2q` | `ViewOnceAudioFragment` dentro de `ViewOnceViewerActivity` |

Las cuatro clases implementan `InterfaceC24513Ahd`, el único marcador que el resto del cliente comprueba ("esto es un mensaje ver una vez") en lugar de repetir la comprobación de cuatro tipos en todas partes. `C1ZB.A0O(i)` (`i==42 || i==43`) es la prueba más estrecha, solo imagen/video, usada donde el `MediaViewFragment` compartido necesita distinguir imagen/video ver una vez de todo lo demás que también renderiza.

El conjunto de tipos `{42,43,78,82}` se repite textualmente en varios sitios de llamada independientes encontrados en este build: el productor de `<meta view_once="true">` (sección 6.1), la tabla de búsqueda por nombre de tipo (`AbstractC32316E9h`: `"viewOnceImage"`=42, `"viewOnceVideo"`=43, `"viewOnceAudio"`=82), y los métodos helper de `C1ZB` para el control de guardado/visualización.

---

## 4. Aplicación en el cliente

### 4.1 Bloqueo de captura/grabación de pantalla (found)

`C66572s0.A00(Window)` es un helper de una línea:

```java
public final void A00(Window window) {
    if (window != null) {
        window.addFlags(8192);   // WindowManager.LayoutParams.FLAG_SECURE
    }
}
```

`8192` (`0x2000`) es el valor numérico crudo de `FLAG_SECURE`; las fuentes decompiladas usan la constante numérica, no el nombre simbólico, así que una búsqueda de texto de `FLAG_SECURE` no encuentra nada — la constante debe coincidirse por valor. `FLAG_SECURE` oscurece la ventana en capturas de pantalla, en la miniatura de apps recientes, y durante la grabación/transmisión de pantalla a nivel de SO; no es una detección específica de WhatsApp, es el flag estándar de ventana segura de Android.

Dos sitios de llamada:

| Sitio de llamada | Condición | Alcance |
|-----------|-----------|-------|
| `MediaViewFragment` (visor de medios genérico) | `C1ZB.A0O(i)` es decir `i==42 \|\| i==43` | se aplica solo cuando el mensaje mostrado es imagen/video ver una vez; en caso contrario, el visor de medios normal no se asegura |
| `ViewOnceViewerActivity.onCreate` | incondicional | esta Activity solo se lanza para texto (78) o audio (82) ver una vez, así que cada instancia está asegurada |

Efecto neto: abrir cualquiera de los cuatro tipos ver una vez fija `FLAG_SECURE` en la ventana anfitriona mientras está abierta; cerrar el visor (al destruirse el fragment/activity) elimina la ventana, lo que descarta el flag con ella. No se encontró evidencia de un mecanismo de *detección* de capturas de pantalla (por ejemplo, un `FileObserver` en `Pictures/Screenshots` o un content-observer de `MediaStore`); la protección es prevención a nivel de SO, no detección posterior al hecho.

### 4.2 Sin reenviar / compartir / guardar (found)

`ViewOnceViewerActivity.onCreateOptionsMenu` construye exactamente cuatro entradas de menú — info, transcribir (solo audio), eliminar, reportar — y ninguna más; no hay entrada de reenviar, compartir, guardar o copiar en ese menú en absoluto. En el `MediaViewMenu` compartido (usado para imagen/video ver una vez a través del visor de medios normal), varias variables locales booleanas de visibilidad de menú se calculan con una exclusión explícita `instanceof InterfaceC24513Ahd`, por ejemplo:

```java
if (i6 == 2 && !c36911dGA1I21.element && ... && !(abstractC34931a2 instanceof InterfaceC24513Ahd)) {
    z14 = !C0DZ.A0X(c0df);     // forward-related menu flag, left false (hidden) for view-once
}
...
z16 = abstractC34931a2 instanceof InterfaceC24513Ahd;
if (!z16) {
    z17 = !AbstractC24760wu.A07(c0df);   // another gated flag, defaults false for view-once
}
```

Como cada flag tiene por defecto `false` y solo se le asigna un valor utilizable en la rama que no es ver una vez, los elementos de menú correspondientes permanecen ocultos para mensajes `InterfaceC24513Ahd`. La restricción se aplica en la capa de UI (construcción del menú), no eliminando el medio subyacente del disco local antes de que el visor lo abra.

### 4.3 El remitente no puede reabrir su propio medio (found)

`DYM` (componente de fila de conversación para medio ver una vez) afirma:

```java
C00K.A0C(false, "ConversationRowViewOnceMedia/senders can not view their own media");
```

en el camino que usaría la propia fila de medio ver una vez enviada por el remitente para reabrir el contenido — es decir, la invariante "un remitente nunca obtiene un handler de apertura funcional para su propio mensaje ver una vez" se aplica como una aserción dura en lugar de una ocultación condicional de UI.

### 4.4 Citar elimina el medio (found)

`F43` ("QuotedMediaCleanupSerializationPostProcessor", condicionado por el flag **25572**) reescribe los campos `imageMessage` / `videoMessage` / `documentMessage` / `audioMessage` de un mensaje citado antes de que se adjunte como `contextInfo.quotedMessage` a un *nuevo* mensaje saliente: copia campos que no son de contenido (mimetype, caption, dimensiones, miniatura, el propio bit `viewOnce`) pero elimina `mediaKey`, `fileSha256`/`fileEncSha256` y `directPath`. Citar un mensaje ver una vez por lo tanto no puede filtrar la media key original en una respuesta; la cita muestra solo metadatos.

### 4.5 Hojas educativas (found)

`ViewOnceNuxBottomSheet` se muestra una vez por rol (remitente/receptor — rastreado por las claves de UXCam `ephemeral_view_once` / `ephemeral_view_once_receiver`) la primera vez que cada lado envía/recibe un mensaje ver una vez, con el texto extraído directamente de `res/values/strings.xml`:

| Id de string | Texto |
|-----------|------|
| `str4e56` | "View once messages give you more privacy" |
| `str4e55` | "For added privacy, the recipient can't share, forward, copy, save, or take a screenshot of it." |
| `str4e68` / `str4e5d` / `str4e7b` | variantes por tipo: "This is a view once photo/message/video so it's more private" |
| `str4e69` / `str4e6a` / `str4e5c` | "Also, you can't share, forward, copy, save, or take a screenshot of it." |
| `str4e63` / `str4e64` | "View once photo, expired" / "View once photo, opened" (mismo patrón para video/audio/texto) |

Los pares de string "expired"/"opened" por tipo (imagen, video, audio, texto) son la cara visible para el usuario de la columna local `state` (sección 5).

---

## 5. Almacenamiento local y máquina de estados

### 5.1 Tabla (found, `C199158dT`)

```sql
-- message_view_once_media(message_row_id, state)
SELECT state FROM message_view_once_media WHERE message_row_id = ?     -- GET_VIEW_ONCE_STATE_BY_MESSAGE_ROW_ID_SQL
UPDATE message_view_once_media SET state = ? WHERE message_row_id = ?  -- UPDATE_VIEW_ONCE_SQL
INSERT INTO message_view_once_media (message_row_id, state) VALUES (?, ?)  -- INSERT_VIEW_ONCE_SQL
```

Una fila por mensaje ver una vez, independiente de las tablas genéricas `message` y `message_media` (que siguen conteniendo la contabilidad de fila/archivo de medio compartida con los mensajes ordinarios).

### 5.2 Estados (found los valores de fila, el mapeo de nombres parcialmente inferido)

| Transición | Código | Disparador |
|------------|------|---------|
| Fila creada | `A02` (`BDk()` en el FMessage, valor al crearse) | mensaje enviado/recibido; el valor inicial es el que reporte el FMessage — consistente con "0 = no abierto" pero no se encontró una constante nombrada |
| Marcado como abierto | `A03`: `state = 1` | el estado del mensaje (`B6u()`) alcanza **8**, **9** o **10** (códigos de estado relacionados con descarga/lectura; nombres exactos no resueltos) |
| Lectura sin fila | fallback `i = 2` en `A01` | `GET_VIEW_ONCE_STATE...` no devuelve fila; el código lo trata como si el mensaje ya hubiera expirado |

Así que **1** = "abierto" confirmado (sitio de llamada nombrado); **2** es el fallback de sin-registro/expirado; existe un valor inicial/"no abierto" pero no se fijó a un literal en este build.

### 5.3 Eliminación (found)

La misma clase `EphemeralUpdateRunnable` que expira los mensajes temporales (tipo de job 0, tabla `message_ephemeral`) y los add-ons de secreto de mensaje (tipo de job 4, tabla `message_add_on`) también ejecuta el tipo de job **3**, registrado como `ViewOnceMessageStore/getViewOnceMessagesToDelete`:

```sql
SELECT message.* FROM message_view_once_media AS view_once
  JOIN message AS message ON view_once.message_row_id = message._id
  JOIN message_media AS message_media ON message_media.message_row_id = message._id
WHERE message_media.file_size IS NOT NULL
  AND message_media.file_size IS NOT 0
  AND message.from_me = 0
  AND view_once.state IN (1, 2)
LIMIT ?
```
<sub>(lista de columnas simplificada; `GET_EXPIRED_VIEW_ONCE_MESSAGES_SQL`)</sub>

Leído literalmente: el job solo apunta a medios ver una vez *recibidos* (`from_me = 0`) que todavía tienen un archivo en disco (`file_size` presente y distinto de cero) y cuyo estado es `1` (abierto) o `2` (el mismo valor de fallback usado para "sin fila"/expirado). El job libera el archivo de medio local para las filas que coinciden con esa consulta; no elimina la fila del mensaje en sí (la fila sobrevive, llevando la etiqueta de UI "opened"/"expired" de 4.5). El medio ver una vez **enviado** (`from_me = 1`) no está cubierto por esta consulta — consistente con que al remitente nunca se le permite reabrirlo (4.3), pero no se encontró una limpieza correspondiente para la propia copia del remitente; su retención/eliminación es **unknown**.

### 5.4 Ciclo de vida de la media key / criptografía (enlazada, no repetida)

El medio ver una vez usa el pipeline de medios ordinario de principio a fin — la misma tabla `MmsType`, la misma derivación de clave HKDF-80, el mismo envelope AES-CBC+HMAC, las mismas URLs de subida/descarga; no hay una fila `MmsType` separada para "ver una vez". Ver [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) secciones 3-5 para la criptografía, y la sección 12 de ese reporte para las notas específicas de ver una vez (aserción de no-visualización-propia del remitente, tag de log de eliminación de miniatura). Si el servidor elimina o marca independientemente el objeto subido tras la primera descarga es **unknown** a partir de este análisis estático — la garantía del lado del cliente es la eliminación del archivo local en 5.3, no un contrato del servidor que el cliente pueda observar.

---

## 6. "Ver una vez no disponible" / señalización entre dispositivos

### 6.1 Stanza `unavailable[type="view_once"]` (corrección a una nota de investigación anterior)

Una nota de investigación anterior (2.26.35.2) rastreó el par de literales de salida `view_once`/`true` hasta un método registrado como `AppDataManager/contributeMetaAppData` y dejó abierto si ese método construía un nodo completo o solo contribuía metadatos. En 2.26.41.6 el mismo tag de log (`"AppDataManager/contributeMetaAppData type="`) **no** es el productor de `view_once`: pertenece a una rama diferente y no relacionada de `F6K` (el constructor genérico de nodos `<meta>`) que estampa un atributo `appdata` de formato libre para mensajes de bot/add-on (`FZF.AVN()`). El atributo `view_once` real en este build se construye unas líneas antes en el *mismo* método `F6K`, independientemente de esa línea de log:

```java
if (c08j2.A15(11282) && (i == 42 || i == 43 || i == 82 || i == 78)) {
    EZV.A00(ezv, "view_once", "true");
}
```

Esto emite `<meta view_once="true">` como hijo/atributo del nodo `<meta>` de la stanza `<message>` saliente (no el hijo `<unavailable type="view_once">` que describen la nota de investigación y Baileys/whatsmeow). Ambos pueden ser ciertos a la vez: `<meta view_once="true">` es el marcador en la propia stanza del remitente de que este mensaje es ver una vez; `<unavailable type="view_once">` es un nodo *diferente*, observado solo en el lado de recepción/Web cuando no se distribuyó ciphertext a ese dispositivo. El análisis estático del APK de Android (que no tiene un rol Web/dispositivo enlazado aquí) no puede mostrar qué lado ensambla ese segundo nodo; este reporte no cambia la conclusión anterior de confianza media-alta de que es producido por el servidor o normalizado por el servidor a partir del estado de distribución del remitente. Baileys corrobora el lado de recepción con un literal *más específico* que el genérico: `src/Socket/messages-recv.js` comprueba `unavailableType === 'view_once_unavailable_fanout'` (junto a `bot_unavailable_fanout`, `hosted_unavailable_fanout`) para decidir si omitir una solicitud de reenvío de placeholder a demanda, mientras que `src/Utils/decode-wa-message.js` por separado coincide con el `attrs.type === 'view_once'` plano en un hijo `<unavailable>` para fijar `isViewOnce`/`StubType.VIEWED_ONCE`. Son dos rutas de código diferentes para lo que la nota de investigación anterior trataba como un solo string.

### 6.2 Tokens `view_once="read"`/`"write"` (token found, consumidor no resuelto)

Los literales `view_once_read` y `view_once_write` están presentes en la tabla de diccionario de stanza binaria del cliente de Android (`AbstractC40911lb`, la lista fija de vocabulario de wire usada para codificación compacta de tokens) — el mismo tipo de tabla que lleva `unavailable`, `enc`, `polltype`, etc. El `decode-wa-message.js` de Baileys lee un valor `attrs.view_once` de `'read'` o `'write'` en atributos a nivel de `<enc>` y lo almacena como `fullMessage.viewOnceType`. En conjunto, esto es consistente con una señal de sincronización "ya abierto" por dispositivo propio que viaja junto con el envelope del mensaje — plausiblemente cómo los otros dispositivos enlazados de un usuario se enteran de que el contenido ver una vez ya fue abierto en uno de ellos — pero no se localizó ningún sitio de llamada de Android que *fije* o *consuma* este atributo en 2.26.41.6; se registra aquí como un token de wire found con un consumidor de Android no resuelto (**unknown**).

---

## 7. Interacción con los mensajes temporales

Ver una vez y los mensajes temporales (TTL de mensaje por chat) son flags independientes y ortogonales que pueden fijarse ambos en el mismo mensaje:

- Usan tablas locales separadas: `message_ephemeral` (temporal, indexada por `expire_timestamp`) vs. `message_view_once_media` (ver una vez, indexada por `state`).
- Ambos son expirados por jobs en el *mismo* worker `EphemeralUpdateRunnable` (tipo de job 0 para temporal, tipo de job 3 para ver una vez, tipo de job 4 para add-ons de secreto de mensaje) — una ruta de programación/ejecución compartida, estado y SQL distintos por feature.
- A nivel de proto, `ephemeralMessage` es una entrada par en la misma tabla genérica de desenvoltura de wrapper que los tres wrappers de ver una vez (sección 2.4): un mensaje puede envolverse como `ephemeralMessage{message: viewOnceMessage{message: imageMessage{...}}}` o en el orden inverso, y tanto la desenvoltura recursiva en `C34748F5r` como el `getFutureProofMessage()` de Baileys recorren cualquiera de los dos órdenes.
- La eliminación de mensajes temporales remueve el mensaje completo tras el TTL del chat sin importar si fue abierto; la eliminación de ver una vez remueve solo el *archivo de medio* una vez que el mensaje fue abierto (o cae en el fallback de estado 2), y deja la fila del mensaje (ahora mostrada como "opened"/"expired") en su lugar. Una foto ver una vez dentro de un chat temporal está por lo tanto todavía sujeta al TTL del chat además de su propia regla de un-abrir-y-borrar de medio.

---

## 8. Feature flags (ids como se leyeron en los sitios de llamada; nombres no resueltos)

| ID | Tipo | Controla |
|----|------|----------|
| **8784** | bool | enviar medio ver una vez solo con el campo inline (activado) vs. campo inline + wrapper legacy (desactivado) |
| **11282** | bool | emitir `<meta view_once="true">` para los tipos de mensaje 42/43/78/82 |
| **25572** | bool | eliminar campos de medio de un mensaje ver una vez citado (`F43`) |

(Los flags que gobiernan el pipeline de medios compartido — HKDF, subida/descarga, reintentos — se listan en [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) sección 16 y no se repiten aquí.)

---

## 9. Baileys (`baron-baileys-v2`, código leído, nada probado)

| Tema | Baileys | Android 2.26.41.6 |
|-------|---------|---------------------|
| Marcado del lado de envío | siempre envuelve: `{ viewOnceMessage \| viewOnceMessageV2 \| viewOnceMessageV2Extension: { message } }` dependiendo de una opción `viewOnceVersion` (`src/Utils/messages.js`) | solo envuelve cuando el flag 8784 está desactivado; el valor por defecto (8784 activado) fija el campo inline `viewOnce` directamente en el mensaje de medio/texto, sin wrapper |
| Wrapper también usado para no-medios | `viewOnceMessage` se usa además para dar futureproofing a los envíos de `buttonsMessage`/`templateMessage`/`listMessage`/`interactiveMessage` (`src/Socket/messages-send.js`, `requiresViewOnce`) — no relacionado con la privacidad de autodestrucción | el mismo tipo de wrapper (`BD2`) es reutilizado por la tabla de desenvoltura genérica para `botInvokeMessage`, `editedMessage`, etc. — el mismo rol de "envelope genérico" confirmado independientemente (2.4) |
| Lista de desenvoltura genérica | `getFutureProofMessage()` en `message-inspect.js`: `ephemeralMessage`, `viewOnceMessage`, `documentWithCaptionMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `groupMentionedMessage`, `botInvokeMessage`, ... | `AbstractC33204EdH.A00` (35 entradas) — mismos nombres de campo de wrapper |
| Manejo de recepción de `unavailable` | dos comprobaciones de literal distintas: `attrs.type === 'view_once'` (fija `isViewOnce`) y `unavailableType === 'view_once_unavailable_fanout'` (omite el reenvío de placeholder) | solo el productor de `<meta view_once>` del lado del cliente (6.1); el nodo `<unavailable>` en sí es de la ruta de recepción/lado Web, no rastreado aquí |
| Token de lectura/escritura `view_once` | decodifica `attrs.view_once === 'read' \| 'write'` en atributos de `<enc>` como `viewOnceType` | tokens presentes en el diccionario de wire del cliente; no se localizó consumidor de Android (6.2) |
| Analítica | `WAM/constants.js`: `viewOnceMessagesSent` (16), `viewOnceMessagesReceived` (17), `viewOnceMessagesOpened` (18) | no rastreado en este reporte; ver [WA_WAM_ANALYTICS.md](./WA_WAM_ANALYTICS.md) para el mecanismo de WAM en general |
| Bloqueo de captura/reenvío | no implementado — Baileys es una biblioteca backend sin UI, sin ventana, sin menú que restringir | `FLAG_SECURE` + omisión de elemento de menú (4.1-4.2); no reproducible fuera de una UI de Android |
| Eliminación local tras abrir | no aplica — Baileys no tiene una máquina de estados persistente de visor de medios; los llamadores son responsables de su propio almacenamiento | `message_view_once_media.state` + job tipo 3 de `EphemeralUpdateRunnable` (5.1-5.3) |

---

## 10. Casos de error / gotchas

| Síntoma | Causa | Nota |
|---------|-------|------|
| El medio ver una vez desaparece al reabrir el visor | normal: `state` alcanzó 1 (abierto) o la fila estaba ausente (fallback 2), y el job de eliminación ya liberó el archivo | no es un bug; este es el comportamiento previsto de un-abrir-y-borrar |
| El propio medio ver una vez del remitente nunca se abre desde la fila de conversación | aserción dura de `DYM` `senders can not view their own media` | por diseño, no una ruta de error |
| La respuesta citando un mensaje ver una vez no muestra medio | `F43` elimina `mediaKey`/hashes/`directPath` de la cita, conservando solo caption/dimensiones/miniatura/el bit `viewOnce` | esperado; la cita no puede usarse para reextraer el medio |
| El visor de imagen/video ver una vez deja pasar capturas de pantalla en algunos builds pero no en otros | `FLAG_SECURE` solo se aplica vía `C1ZB.A0O(i)` (tipos 42/43); cualquier regresión en ese gate (por ejemplo, una ruta de código que abra el visor compartido para un elemento ver una vez sin pasar por la llamada con gate) descartaría silenciosamente la protección | ubicación del gate documentada en `MediaViewFragment` línea ~3120 (este build) |
| Un dispositivo enlazado muestra un mensaje ver una vez como ya abierto sin que el usuario lo abra ahí | sincronización plausible entre dispositivos vía tokens de wire `view_once="read"/"write"` (6.2) | mecanismo no confirmado del lado de Android; registrado como unknown |

---

## 11. Distinciones clave

| Esto | No esto |
|------|----------|
| Campo booleano `viewOnce` en `ImageMessage`/`VideoMessage`/`AudioMessage`/`ExtendedTextMessage` | el wrapper legacy `viewOnceMessage`/`viewOnceMessageV2`/`viewOnceMessageV2Extension` alrededor del mismo mensaje |
| `viewOnceMessage` (`BD2`) usado para privacidad (autodestrucción) | el mismo tipo de wrapper `BD2` reutilizado como envelope genérico de futureproofing para envíos de buttons/template/list/interactive (Baileys) y para `botInvokeMessage`/`editedMessage` en Android |
| `message_view_once_media.state` (local, por mensaje, rastreo de abierto/expirado) | `message_ephemeral.expire_timestamp` (local, por mensaje, TTL de chat temporal) — tablas independientes, jobs independientes, mismo runner |
| `<meta view_once="true">` — clasificador del lado del remitente en la stanza saliente | `<unavailable type="view_once">` — un nodo diferente visto en el lado de recepción/Web cuando no llegó ciphertext a ese dispositivo |
| `FLAG_SECURE` en la ventana del visor (*prevención* de captura/grabación de pantalla) | un callback de *detección* de captura de pantalla — no se encontró tal mecanismo |
| Eliminación del *archivo* de medio local tras abrir | eliminación de la *fila* del mensaje — la fila sobrevive, etiquetada "opened"/"expired" |
| Ver una vez (el medio se borra tras una apertura) | mensajes temporales (todo el mensaje se remueve tras un TTL a nivel de chat) — ortogonales, pueden combinarse |

---

## 12. Flujo completo (foto ver una vez, chat 1:1)

```
[Sender]
   │ pick photo, mark "view once" in composer
   │ ImageMessage.viewOnce = true          (flag 8784 on: inline only)
   │ upload via normal media pipeline (WA_MEDIA_UPLOAD.md)
   │ flag 11282 on, type==42 → <meta view_once="true">
   ▼
[Server]  relays the E2E-encrypted stanza; cannot read viewOnce (it's inside the ciphertext)
   │
   ▼
[Receiver]
   │ decrypt → ImageMessage.viewOnce == true, message type 42 (DdP)
   │ INSERT message_view_once_media(message_row_id, state=<initial>)
   │ thumbnail shown in the conversation row; sender-side row asserts "can not view own media"
   │
   ├── user taps to open ──► MediaViewFragment, C1ZB.A0O(42) == true
   │                          → window.addFlags(FLAG_SECURE)
   │                          → forward/share/save menu items hidden (InterfaceC24513Ahd)
   │                          → status reaches 8/9/10 → state = 1 ("opened")
   │                          → window closed, FLAG_SECURE drops with it
   │
   ▼
[EphemeralUpdateRunnable, job type 3]
   │ SELECT ... FROM message_view_once_media JOIN message_media
   │   WHERE from_me=0 AND file_size IS NOT NULL AND state IN (1,2)
   ▼
local media file deleted; row kept, UI shows "View once photo, opened"
```

---

## 13. Incógnitas

| Elemento | Estado |
|------|-------|
| Constantes nombradas para `state` 0 (inicial) y el significado exacto compartido entre 2 (fallback de sin-fila) y "expired" | solo 1 ("opened") tiene un sitio de llamada nombrado; el resto se infiere del valor de fallback y los strings de UI |
| Códigos de estado 8/9/10 consumidos por `C199158dT.A03` para disparar "opened" | no resueltos a constantes nombradas |
| Retención/limpieza de la **propia** copia del remitente del medio ver una vez enviado | el job de eliminación solo apunta a `from_me = 0`; no se encontró limpieza correspondiente del lado del remitente |
| Eliminación/marcado del lado del servidor del objeto subido tras la primera descarga | no se puede observar desde el análisis estático del cliente |
| Construcción del nodo `<unavailable type="view_once">` (placeholder del cliente vs. construido por el servidor) | no resuelto; arrastrado de investigación anterior, no resuelto de nuevo aquí |
| Consumidor de Android de los tokens de wire `view_once="read"/"write"` | presencia del token confirmada en la tabla de diccionario; no se localizó sitio de llamada |
| Si `FLAG_SECURE` se aplica en cada ruta de código que puede presentar contenido ver una vez (por ejemplo, previsualizaciones de notificación, widget, Wear) | solo se comprobaron las rutas de `MediaViewFragment` y `ViewOnceViewerActivity` |
