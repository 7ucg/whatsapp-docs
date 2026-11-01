<!-- src-sha1: 4123b5a528529c4f17625135c9cbbdbd63f1dc08 -->
# WhatsApp Encuestas — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** familia de mensajes de encuesta (`pollCreationMessage` hasta `pollCreationMessageV6`, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), historial de versiones y lógica de selección de envío/recepción, validación y límites de creación, vinculación de opciones de encuesta con imagen, selección de voto y modelo de privacidad, selección múltiple vs. única, edición de encuestas, instantánea de resultados al reenviar, feature flags

---

## 1. Qué es

Una encuesta es un sub-objeto de `Message` (`PollCreationMessage`, reutilizado sin cambios en seis campos de nivel superior versionados) que transporta una pregunta, una lista de opciones, un tope de selección y ajustes opcionales de quiz/hora de cierre/visibilidad. Los votos (`pollUpdateMessage`), las opciones añadidas (`pollAddOptionMessage`) y las ediciones (`secretEncryptedMessage`) son mensajes de seguimiento independientes, vinculados al id del mensaje de creación y derivados a partir del secreto por mensaje de este; ese cifrado (casos de uso de HKDF, AES-GCM, AAD, reintento de identidad) se cubre en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) y no se repite aquí. Este informe cubre la capa de tipo de mensaje: qué campo lleva qué, cómo elige el cliente entre ellos, validación y límites, y qué hacen los handlers específicos de encuesta con los payloads descifrados. Todos los hallazgos son análisis estático del APK 2.26.41.6 decompilado (fuentes Java bajo `java_src/`, más `res/values/strings.xml`); nada se capturó en tránsito. Niveles: **found** = leído en código/recursos, **inferred** = deducido del código, **unknown** = no resuelto.

| Entidad | Campo en `Message` | Tipo de proto | Rol |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | slot de creación original |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | creación en un chat de subgrupo por defecto de una comunidad |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | slot de creación de encuesta simple (por defecto actual para encuestas ordinarias) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | envoltorio de compatibilidad futura alrededor de un `Message.pollCreationMessage` interno (campo 49) |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | slot de creación de quiz |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | slot de encuesta extendida (hora de cierre / ocultar nombres de votantes / permitir añadir opción) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | una imagen de opción de encuesta con imagen, vinculada a la encuesta futura vía `messageAssociation` |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | añade una opción a una encuesta existente |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | voto (cifrado) o metadatos de voto |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | instantánea estática de resultados, encuesta reenviada a otro chat |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | igual, variante quiz (recuentos de votos puestos a cero) |

Los números de campo se verificaron directamente contra `C30628DTw` (la clase proto `Message`), que declara las once constantes `POLL_*_FIELD_NUMBER` que coinciden con la tabla anterior.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Campos (found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | presente en el wire pero sin uso por los handlers leídos en esta pasada (los votos usan el `messageSecret` por mensaje, no este campo; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | pregunta de la encuesta, máx. 5000 caracteres, requerido |
| `options` | **3** | repeated `Option` | opciones de respuesta |
| `selectableOptionsCount` | **4** | uint32 | tope de selección, requerido (§11) |
| `contextInfo` | **5** | `ContextInfo` | contexto estándar |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | opción de respuesta correcta del quiz, requerida cuando `pollType=QUIZ` |
| `endTime` | **9** | int64 | timestamp de cierre de la encuesta (ms) |
| `hideParticipantName` | **10** | bool | "Ocultar nombres de votantes" (§10) |
| `allowAddOption` | **11** | bool | "Permitir que otros añadan opciones" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, solo poblado para opciones de encuesta con imagen, §5).

### 2.2 Representación local

El cliente almacena una encuesta parseada como `C13J` (variante quiz con imagen `C13K`), con las opciones como objetos `C33283EeZ` que llevan el nombre crudo (`A04`), un digest SHA-256 calculado localmente a partir del nombre (`A02`, §9.1) y, para opciones con imagen, el `optionHash` del wire (`A08`).

---

## 3. Historial de versiones

### 3.1 Qué campo se usa para enviar (found, `F2N.A00`/`A02`)

```text
pollType == QUIZ (correct answer set)              -> pollCreationMessageV5
chat is a community default-subgroup (group_type 3) -> pollCreationMessageV2
else:
  hideParticipantName / endTime / allowAddOption set -> pollCreationMessageV6
  none of those set                                   -> pollCreationMessageV3
```

`pollCreationMessageV4` nunca es poblado por el camino de envío leído en esta pasada; solo aparece en recepción (§3.3). La comprobación de comunidad reutiliza el mismo predicado `group_type == 3` que el fallback de reacción en texto plano en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2 (`C0GQ.A0A(chat) == 3`, derivado de `isDefaultSubgroup_`); por qué una encuesta de subgrupo por defecto obtiene su propio slot versionado en lugar de V3/V6 no se explica en el código leído aquí (inferido: orden histórico del rollout, dado que el número de campo de V2 es el más bajo del conjunto extendido).

Así, en la práctica: **V3** es el slot actual para una encuesta ordinaria de selección múltiple/única sin extras, **V6** es el actual para una encuesta que usa hora de cierre, nombres de votantes ocultos o añadir opción, **V5** es el actual para quizzes, y **V2** es una variante específica de subgrupo de comunidad de la misma forma base. **V1** (el campo sin versionar 49) y **V4** no son elegidos por el emisor en este build.

### 3.2 `pollCreationMessageV4` = envoltorio de compatibilidad futura (found, `F2N.CM7`)

El tipo proto de V4 es `FutureProofMessage` (`BD2`, campo único `message` = un `Message` interno). En recepción, cuando el slot V4 está poblado, el cliente desenvuelve `BD2.message_` y lee el campo `pollCreationMessage` (49) de ese mensaje interno propio como el `PollCreationMessage` real. Esto es un envoltorio de fallback genuino, no un campo muerto: un emisor que necesita emitir una variante de encuesta más nueva/no definida puede envolver una encuesta básica (con la forma del campo 49) dentro de V4, de modo que los clientes más antiguos — que solo entienden el desenvolvimiento genérico de `FutureProofMessage`, no el slot más nuevo — sigan renderizando una encuesta simple. Ningún camino de código en esta pasada puebla V4 en el envío, así que esto existe por compatibilidad hacia adelante/atrás entre versiones de cliente, no por algo que el propio cliente 2.26.41.6 emita (inferido).

### 3.3 Selección en recepción y degradación (found, aproximado; el decompilador perdió parte de la estructura de ramas)

`F2N.CM7` comprueba los bitfields de `Message` en el orden V1 → V2 → V4 → V5 → V6 → fallback-V3 y parsea el que sea que esté poblado en el mismo validador (`F2N.A01`, §4). Tres flags condicionan la aceptación de los campos extra de V6 en recepción; cuando un flag está apagado, la encuesta se **degrada** (se parsea como el placeholder genérico de compatibilidad futura en lugar de una burbuja de encuesta) en vez de ser rechazada directamente:

| Campo extra | Gate | Efecto cuando el gate está apagado |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | se registra `poll downgraded to FMessageFuture (receiving disabled)`, no se renderiza como encuesta |
| `hideParticipantName` | AB int **24885** | degradación (polaridad exacta de la comprobación no resuelta del todo a partir del flujo de control decompilado) |
| `allowAddOption` | AB int **25758** | degradación |

El anidamiento exacto de estas tres condiciones no pudo reconstruirse completamente (JADX reporta bloques duplicados/inalcanzables en `F2N.CM7`); los flags de gating y el resultado de degradación son found, la combinación booleana precisa es inferred.

### 3.4 Gate de contenido de imagen

`pollContentType = IMAGE` solo se respeta en el camino de parseo V3/V5 cuando el bit de `pollContentType` está establecido; si está establecido pero el valor no es `IMAGE`, el mensaje se rechaza (`return null`, cae al parser genérico) en lugar de tratarse silenciosamente como texto.

---

## 4. Validación de creación (found, `F2N.A01`)

Validador único compartido por todos los campos de creación versionados. Lanza excepción, código de error **11** salvo que se indique lo contrario:

| Comprobación | Regla | Cadena de error |
|-------|-------|--------------|
| Nombre presente | el bit de `name` debe estar establecido | `poll_creation_missing_name` |
| Longitud del nombre | 1–5000 caracteres (salvo que un contexto de parseo laxo omita esto, §4.1) | `poll_creation_invalid_name` |
| Respuesta correcta del quiz | si `pollType=QUIZ`, el bit de `correctAnswer` debe estar establecido | `poll_creation_missing_correct_answer` |
| Opciones presentes | al menos una opción, salvo que aplique el bypass de cero opciones (§4.1) | `poll_creation_missing_options` |
| Número de opciones (inferior) | ≥ 2 opciones (0 bajo el bypass) | `poll_creation_invalid_options_count` |
| Número de opciones (superior) | ≤ `min(AB int 1408, 12)` — 12 es un techo duro del cliente sin importar el valor del servidor | `poll_creation_invalid_options_count` |
| Longitud del nombre de opción | 1–2500 caracteres por opción | `poll_creation_invalid_option` |
| Nombre de respuesta correcta | si es quiz, `correctAnswer.optionName` debe ser no vacío | `poll_creation_missing_correct_answer_name` |
| Opciones duplicadas | los nombres de opción deben ser únicos | `poll_creation_duplicate_options` |
| Opciones duplicadas recortadas | bajo el flag AB **25758**, los nombres recortados de espacios en blanco también deben ser únicos | `poll_creation_duplicate_trimmed_options` |
| La respuesta correcta coincide con una opción | el nombre de respuesta correcta del quiz debe igualar el nombre de una opción | `poll_creation_unmatched_correct_answer` |
| Recuento seleccionable presente | el bit de `selectableOptionsCount` debe estar establecido | `poll_creation_missing_selectable_options_count` |
| Rango del recuento seleccionable | `0 <= selectableOptionsCount <= options.size()` (o `<= min(1408,12)` bajo el bypass) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Bypass laxo / de cero opciones (found el camino de código, semántica inferred)

Un booleano local (`z`) calculado a partir de AB bool **37909**, consultado solo cuando un contador interno de contexto de parseo es igual a 1, relaja el mínimo de opciones a 0 y amplía el techo del recuento seleccionable al límite crudo `min(1408,12)` en lugar de `options.size()`. El valor de contexto de parseo al que esto corresponde (recepción normal vs. algún otro camino de ingesta, p. ej. sincronización de historial) no se resolvió; esto se registra como found-pero-no-explicado en lugar de una funcionalidad confirmada y visible al usuario de "encuesta sin opciones".

### 4.2 Bypass de nombre laxo / sincronización de historial

Un flag de contexto distinto (`c33371Eg0.A0W`) cortocircuita tanto la comprobación de longitud del nombre como (equivalentemente, en `F39`, §9) la comprobación de longitud del nombre en la instantánea de resultados, aceptando la cadena cruda sin verificar. Consistente con un camino de parseo de fuente confiable (p. ej. reimportación local de historial) más que una recepción de red normal; no confirmado de forma independiente.

---

## 5. Opciones de encuesta con imagen: `pollCreationOptionImageMessage`

### 5.1 Estructura y vinculación (found)

`pollCreationOptionImageMessage` (campo 90) envuelve un `ImageMessage` subido ordinario dentro de un `FutureProofMessage` — la imagen **no** está embebida en `PollCreationMessage.Option`. Cada imagen de opción se envía como su propio mensaje hijo, asociado a la encuesta (aún no enviada) vía `MessageContextInfo.messageAssociation`, tipo de asociación `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; este es el valor de enum de este build — un build anterior lo tenía en 7, el valor numérico no es estable entre versiones y debe releerse en cada release). El helper del lado de envío "MediaPollAssociationProvider" (en `C20M`) cuenta las filas de `message_association` para el id de fila de la encuesta padre y el tipo de asociación `6`; una vez que el recuento alcanza el número de opciones, se considera que todas las imágenes de opción están subidas y el cliente procede a enviar la encuesta misma con `pollContentType = IMAGE`.

### 5.2 Hash de opción para opciones con imagen (inferred, trasladado de un build anterior, no re-derivado línea por línea en 2.26.41.6)

Para opciones de texto plano el campo `optionHash` del wire se deja vacío; el único hash calculado para una opción de texto plano es el digest local de búsqueda `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(confirmado directamente en 2.26.41.6, §9.1 — este es el valor usado para hacer coincidir las selecciones de voto, no el campo proto `optionHash`). Para opciones **con imagen** se puebla el campo proto `optionHash`; un trace de una versión anterior de la secuencia de envío encontró que combina el hash del nombre de la opción con el `fileSha256` de la imagen subida:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Esta fórmula no se reverificó contra el código de 2.26.41.6 en esta pasada (la clase que la calcula no fue localizada); se mantiene como inferred y debería re-comprobarse antes de confiar en ella.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, campo 121)

### 6.1 Campos (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, misma forma que la del voto, §7).

### 6.2 Envío (found, `F2L.ADr`)

Construye una `Option` a partir del nombre nuevo (y, para encuestas con imagen, su hash), adjunta la clave de la encuesta de origen y — para chats 1:1, cuando no es un contexto de edición — resuelve la identidad del emisor a través del límite LID/PN de la misma forma que la capa de secretos de mensaje hace para otros add-ons (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 paso 4). La opción misma **no** está cifrada por secreto en esta capa como lo está un `pollUpdateMessage`: el payload de añadir opción viaja como un campo de mensaje normal; lo que se envuelve en `secretEncryptedMessage` (tipo `POLL_ADD_OPTION`) es el intento de añadir opción como un todo cuando debe viajar por el esquema de secreto de mensaje (§8).

### 6.3 Validación en recepción (found, `F2L.CM7`)

| Comprobación | Error |
|-------|-------|
| Gate de feature: AB int **25758** debe ser distinto de cero | error **10017** |
| `pollCreationMessageKey` presente | `poll_add_option_missing_poll_message_key` |
| `addOption` presente | `poll_add_option_missing_poll_option` |
| Nombre de opción no vacío, ≤ 2500 caracteres | `poll_add_option_invalid_option` |

El objeto local resultante se cifra por secreto para el transporte usando el caso de uso `Poll Add Option` (llamada confirmada al helper de secreto de mensaje con `AnonymousClass122.POLL_ADD_OPTION` como etiqueta de asociación). Las opciones añadidas se rastrean para hacer coincidir con opciones existentes de la misma forma que las opciones de encuesta con imagen (tipo de asociación `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (voto y metadatos de voto)

El cifrado completo (caso de uso HKDF `Poll Vote`, AAD, AES-GCM, reintento de identidad LID/PN) está en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7; esta sección cubre solo lo que el handler de voto de encuesta (`DUA`, extiende `F2P`) hace con el texto en claro.

### 7.1 Dos caminos de envío/recepción (found)

AB bool **6772** selecciona entre:
- **activado** (actual): un helper de cifrado compartido (`C33285Eeb`) construye el texto cifrado y la `MessageKey`; el voto se reintenta a partir de un par `(iv, payload)` almacenado previamente cuando existe, en lugar de volver a cifrar.
- **desactivado** (legacy): una rama en línea dentro de `DUA` hace la misma llamada HKDF/AES-GCM directamente, derivando ella misma la identidad del destinatario (el propio LID para votos sobre la encuesta propia del votante, si no, el JID resuelto del destinatario del voto).

### 7.2 Payload del voto: `PollVoteMessage` (`DPF`)

Campo único `selectedOptions` **1**, bytes repetidos — cada entrada es un digest SHA-256 de 32 bytes del nombre de la opción (§9.1), no un índice. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`) valida la selección descifrada:

| Comprobación | Regla | Etiqueta de log |
|-------|-------|-----------------|
| Tamaño de la selección | ≤ 12 **y** ≤ el `selectableOptionsCount` de la encuesta (cuando > 0) | `poll_vote_invalid_options_count` |
| Forma del hash | cada hash seleccionado decodifica exactamente a 32 bytes | `poll_vote_invalid_option_hashes` |
| Duplicados | ningún hash repetido en un mismo voto | `poll_vote_duplicate_option_hashes` |
| Resolución | cada hash seleccionado debe coincidir con uno de los hashes de opción conocidos (no eliminados) de la encuesta | devuelve un resultado de error, sin coincidencia -> voto rechazado |

### 7.3 Hora de cierre y metadatos (found, `DUA.A01`)

Un voto cuyo `senderTimestampMs` sea posterior al `endTime` de la encuesta es rechazado (`poll_update_past_end_time`); bajo AB bool **2321**, un evento de voto rechazado además alimenta un contador de telemetría (`N0e`). Los `metadata` del voto (`pollNameHash`, `lastEditStanzaId`) se estampan en el envío solo bajo AB bool **31593**; en recepción, un bloque de metadata ausente/vacío se registra como `"unstamped"` (no rechazado por sí solo) mientras que un estampado *no coincidente* (comprobado por `C32977EZa`) descarta el voto con `poll_update_tc_drop`. Esta metadata existe para que un cliente pueda detectar que está votando contra una encuesta cuyo historial de edición aún no ha alcanzado.

---

## 8. Edición de encuestas (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Transportada dentro del envoltorio genérico `secretEncryptedMessage` (campo 82), no un transportador específico de encuesta; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4 para el sobre, el AAD y la tabla de códigos de error (`poll_edit_message_stanza_invalid`, gate AB int **24886**, error **10016**). La validación específica de encuesta (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) requiere:

- el mensaje interno es de tipo FMessage 66 y es una encuesta tanto antes como después de la edición;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` y `pollType` **no cambian** entre la encuesta almacenada y la editada — solo el texto de la pregunta y/o los textos de opción pueden diferir;
- coincidencia de opciones: con un flag por chat (`EOI.A01()`, id no resuelto) activado, las opciones editadas se comparan contra un historial de renombrado almacenado mediante una coincidencia secuencial (que preserva el orden), permitiendo renombrar opciones in situ; el comportamiento exacto de la rama de comparación no-renombrado es inferred (JADX nuevamente pierde parte del flujo de control — la función cae en `poll_edit_invalid_edits` en esa rama en la forma decompilada, lo cual es poco probable que sea el comportamiento real del cliente para una edición sin cambios).

Existe una cadena de toast `"Couldn't edit poll"` en los recursos, lo que confirma que la edición de encuestas es visible al usuario en este build, no solo un camino de protocolo reservado.

---

## 9. Internos de coincidencia de voto

### 9.1 Hash de opción (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

SHA-256 plano del texto visible de la opción, sin material de clave. Este es el valor almacenado por opción local (`C33283EeZ.A02`) y el valor contra el que se comparan las entradas de `selectedOptions` de un voto. Cualquier aplicación que conozca el texto de la opción puede calcular el mismo hash — la privacidad de un voto proviene enteramente del cifrado de secreto de mensaje del payload del voto (§7, y [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), no de que el hash sea impredecible.

---

## 10. Modelo de privacidad / anonimato del voto

| Afirmación | Estado |
|-------|--------|
| Los votos están cifrados de extremo a extremo por votante, por encuesta (caso de uso HKDF `Poll Vote`) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| La opción seleccionada se identifica por un hash de contenido, no por un índice | found, §9.1 |
| `hideParticipantName` ("Ocultar nombres de votantes") suprime la visualización de quién votó, en la UI | found (cadena `str2137`, campo 10 de `PollCreationMessage`) |
| `hideParticipantName` oculta al votante del servidor o de otros clientes a nivel de protocolo | **no respaldado por el código leído aquí** — el `participant`/`from` del sobre (es decir, la identidad del votante) se entrega y autentica de la misma forma para cada add-on sin importar este flag (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName` es un ajuste solo de visualización en el objeto de la encuesta, no un cambio de enrutamiento o cifrado |
| El creador de la encuesta siempre puede determinar quién votó | inferred — nada en el camino de descifrado del voto (§7, §9) depende de `hideParticipantName`; el cliente del creador descifra cada voto con la identidad del votante como modificador |

En resumen: las encuestas de WhatsApp no son anónimas para el creador de la encuesta. "Ocultar nombres de votantes" solo controla si *otros participantes* (en la lista "Votos de la encuesta") ven quién votó; no cambia lo que está criptográficamente vinculado al voto, y el servidor nunca conoce el contenido del voto de todas formas (la garantía E2E habitual, no algo específico de este flag).

---

## 11. Selección múltiple vs. selección única

`selectableOptionsCount` (campo 4) es el único mecanismo: un voto con más selecciones que este valor es rechazado (§7.2). No hay un booleano separado de "es selección múltiple" en el wire — la selección única es simplemente `selectableOptionsCount = 1`. La UI de creación expone esto como un único interruptor, **"Permitir varias respuestas"** (cadena `str425f`); cuando está desactivado se infiere que el cliente envía `selectableOptionsCount = 1`, cuando está activado se infiere que envía `selectableOptionsCount = options.size()` (la UI no parece exponer un tope numérico arbitrario — inferido a partir de la cadena del único booleano, no confirmado de forma independiente en el código de la UI de creación). El protocolo en sí permite cualquier valor `0..options.size()` (§4), así que un valor del lado cliente distinto de 1 o "todas las opciones" es posible aunque la UI estándar no lo ofrezca. Los quizzes son implícitamente de selección única (una respuesta correcta; cadena visible al votante `"Quiz • Select one correct answer"`, `str57a5`).

Las etiquetas visibles al votante confirman los dos modos: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: instantánea al reenviar

### 12.1 Propósito (found, `F1A`)

Reenviar una encuesta activa a otro chat **no** reenvía la encuesta interactiva. `F1A` (uno de varios convertidores de "reenvío" que todos implementan la misma interfaz de conversión usada en distintos tipos de mensaje — el convertidor hermano para tipos no soportados lanza `"Cannot forward message of type: ..."`) convierte la encuesta activa (`C13J`) en un objeto `Dd2`: texto de la pregunta, el nombre de cada opción y su **recuento local de votos actual**, y el tipo de encuesta/quiz. Esto se serializa luego como `pollResultSnapshotMessage` (encuesta simple) o `pollResultSnapshotMessageV3` (quiz) y se renderiza con un view holder dedicado (`DWH`), distinto de la burbuja de encuesta interactiva.

### 12.2 Campos (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (repeated `PollVote` — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (mismo enum `PollType` que la creación).

### 12.3 Validación (found, `F39`)

Mismo tipo de comprobaciones que la creación: nombre 1–5000 caracteres, al menos 2 opciones, como máximo `min(AB 1408, 12)` opciones, cada nombre de opción 1–2500 caracteres. Para la variante **quiz** (`V3`), los recuentos de votos se fuerzan a 0 en el envío — una instantánea de quiz reenviada nunca revela los recuentos, solo la pregunta y la lista de opciones.

---

## 13. Resumen de límites

| Elemento | Límite | Fuente |
|------|-------|--------|
| Longitud del nombre de encuesta/pregunta | 1–5000 caracteres | `F2N.A01`, `F39.A00` |
| Longitud del nombre de opción | 1–2500 caracteres | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Número de opciones (creación, instantánea) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Opciones seleccionadas por voto | ≤ 12 y ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| Rango de `selectableOptionsCount` | 0–options.size() (0–12 bajo el bypass laxo, §4.1) | `F2N.A01` |
| Tamaño del hash de opción (entradas de voto) | exactamente 32 bytes | `AbstractC33199EdC` |

---

## 14. Feature flags (ids tal como se leen en los call sites; nombres no resueltos)

| ID | Tipo | Controla |
|----|------|----------|
| **1408** | int | número máximo de opciones de encuesta configurado por el servidor, techo duro del cliente de 12 sin importar el valor |
| **24884** | bool | respetar `endTime` en recepción de una encuesta extendida (V5/V6); apagado -> degradada a placeholder de compatibilidad futura |
| **24885** | int | condiciona la aceptación de `hideParticipantName` en recepción (polaridad exacta no resuelta) |
| **24886** | int | gate de recepción de edición de encuesta; 0 -> rechazado, error 10016 |
| **25758** | int (truthy) | gate de recepción de añadir opción a encuesta (error 10017); también condiciona el rechazo de opción duplicada recortada en la creación |
| **31593** | bool | estampar metadata `pollNameHash`/`lastEditStanzaId` en un voto saliente |
| **6772** | bool | voto de encuesta: helper de cifrado compartido (activado) vs. camino en línea legacy (desactivado) |
| **37909** | bool | permite una encuesta con cero opciones en un contexto de parseo específico (no resuelto) |
| **2321** | bool | detalle extra de telemetría registrado cuando un voto se rechaza por estar después de la hora de cierre de la encuesta |

Los flags de la capa de secreto de mensaje que también afectan a las encuestas (gate del caso de uso de edición **17811**, gates de generación, etc.) están documentados en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16 y no se repiten aquí.

---

## 15. Baileys (solo hechos confirmados)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17 ya cubre las partes de una implementación JavaScript (`baron-baileys-v2` 1.5.17) relevantes para encuestas, a partir de la lectura de `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`:

- La derivación HKDF y las cadenas de caso de uso `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` coinciden exactamente con los literales del cliente Android, incluyendo el AAD `id\0modifier` para `Poll Vote`.
- El AAD, el reintento de identidad (PN/LID) y el manejo de secreto faltante (recurrir a la actualización cruda, sin descifrar) coinciden con el comportamiento de Android descrito en este informe (§7) y en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3.
- No se encontró ningún camino de cifrado del lado del envío para `pollUpdateMessage` (ni `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) en los archivos leídos — es decir, esa implementación podía descifrar un voto entrante, pero los archivos revisados no contenían código para cifrar y enviar uno.

Nada específico de encuestas más allá de lo ya expuesto allí se reverificó de forma independiente en esta pasada (no se leyó código de creación de encuesta, hash de opción o edición de encuesta de Baileys); no se hacen más afirmaciones sobre Baileys aquí.

---

## 16. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | menos de 2 o más de `min(1408,12)` opciones | mantener las opciones dentro del rango |
| `poll_creation_unmatched_correct_answer` | `correctAnswer.optionName` del quiz no coincide con el nombre de ninguna opción | establecer la respuesta correcta con una coincidencia exacta |
| Encuesta no mostrada silenciosamente (degradada) | `endTime`/`hideParticipantName`/`allowAddOption` establecidos en una encuesta V6 pero el flag AB correspondiente está apagado en el receptor | del lado del emisor, no arreglable por contenido; brecha de capacidad del receptor |
| `poll_vote_invalid_options_count` | el voto selecciona más opciones que `selectableOptionsCount`, o más de 12 | respetar el tope de la encuesta |
| `poll_update_past_end_time` | timestamp de voto (o de añadir opción / edición) posterior a `endTime` | votar antes de que la encuesta se cierre |
| `poll_update_tc_drop` | `pollNameHash`/`lastEditStanzaId` del voto no coincide con la vista que el receptor tiene de la encuesta | resincronizar el historial de edición de la encuesta antes de votar |
| error **10017** al añadir opción | AB **25758** es cero en el receptor | brecha de capacidad del receptor |
| error **10016** al editar encuesta | AB **24886** es cero en el receptor | brecha de capacidad del receptor |
| `poll_add_option_past_end_time` | opción añadida después de `endTime` | añadir opciones antes de que la encuesta se cierre |

---

## 17. Distinciones clave

| Esto | No esto |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (tipo `PollCreationMessage`) | `pollCreationMessageV4` (`FutureProofMessage` que envuelve una encuesta básica interna) |
| `pollUpdateMessage` (voto, o metadatos de voto) | `secretEncryptedMessage` con `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` (edición de encuesta / añadir opción) |
| `pollAddOptionMessage` (el payload de la opción nueva) | el envoltorio `secretEncryptedMessage` que lo transporta por el wire cuando está vinculado al secreto de mensaje |
| `pollResultSnapshotMessage`/V3 (estático, reenviado) | la encuesta interactiva activa (`pollCreationMessage*`) |
| Selección de opción por hash SHA-256(nombre) | selección por índice — las encuestas de WhatsApp nunca seleccionan por posición |
| `hideParticipantName` (ajuste de visualización en la UI) | anonimato del emisor del voto (no existe; el creador siempre resuelve al votante) |
| `selectableOptionsCount` (la única señal de múltiple/único) | un booleano separado de "es selección múltiple" (ninguno existe) |

---

## 18. Flujo completo (creación, opción con imagen, voto, reenvío)

```
[Creator]                                          [Server]                     [Participant]
   │ build PollCreationMessage                        │                              │
   │  (quiz? -> V5; community subgroup? -> V2;         │                              │
   │   extras(endTime/hide/addOpt)? -> V6; else V3)    │                              │
   │ [image poll]                                      │                              │
   │  send N × pollCreationOptionImageMessage           │                              │
   │   (messageAssociation MEDIA_POLL=6, parent key)───▶───────────────────────────▶ received,
   │  wait for all fileSha256                           │                              associated
   │  compute optionHash per option                     │                              │
   │ send pollCreationMessage* ─────────────────────────▶──────────────────────────▶ store poll,
   │                                                    │                              secret
   │                                                    │        select option(s)     │
   │                                                    │        hash = SHA256(name)  │
   │                                                    │        key = HKDF(secret,   │
   │                                                    │          pollId‖creator‖    │
   │                                                    │          voter‖"Poll Vote") │
   │                                                    │        pollUpdateMessage    │
   │◀────────────────────────────────────────────────────◀ {key, vote{ct,iv}, ts} ────│
   │ validate: end time, selection count/hash shape     │                              │
   │ decrypt, resolve hash -> known option              │                              │
   │ apply vote                                         │                              │
   │                                                    │                              │
   │ [user forwards the poll elsewhere]                 │                              │
   │ convert live poll -> Dd2 (name, per-option count)  │                              │
   │ quiz? zero the counts                              │                              │
   │ send pollResultSnapshotMessage[/V3] ───────────────▶──────────────────────────▶ static bubble,
   │                                                    │                              not interactive
```

---

## 19. Incógnitas

| Elemento | Estado |
|------|-------|
| Polaridad exacta de AB **24885** (aceptación/degradación de hideParticipantName) | estructura de rama decompilada incompleta |
| Fórmula de hash de opción con imagen (`nameHash`+`imageHash`) para 2.26.41.6 | trasladada de un build anterior, no re-derivada en el código de este build |
| Id del flag AB detrás del interruptor por chat de "renombrado ordenado de opción" usado en la coincidencia de edición de encuesta (`EOI.A01()`) | id no resuelto |
| Rama no-renombrado de la comparación de opciones en edición de encuesta | el decompilador pierde parte del flujo de control; la forma decompilada literal siempre cae en `poll_edit_invalid_edits`, lo cual es poco probable que sea el comportamiento real para una edición sin cambios |
| Valor de contexto de parseo (`c33371Eg0.A00 == 1`) que habilita el bypass de cero opciones (AB **37909**) | no identificado (sincronización de historial vs. otro camino) |
| Si la UI de creación estándar puede enviar valores de `selectableOptionsCount` distintos de 1 o "todas las opciones" | inferido a partir de la cadena de un único interruptor booleano, no confirmado contra el código de la UI |
| Estabilidad del valor numérico de `MEDIA_POLL` entre versiones | encontrado como 6 en 2.26.41.6; un build anterior usó un valor distinto, así que no fijarlo entre versiones |
