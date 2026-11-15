<!-- src-sha1: 287eecdda43f9253685bac27a2f3bea697aa3989 -->
# WhatsApp Encuestas — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** familia de mensajes de encuesta (`pollCreationMessage` hasta `pollCreationMessageV6`, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), historial de versiones y lógica de selección al enviar/recibir, validación y límites de creación, vinculación de opciones de encuesta con imagen, modelo de selección de voto y privacidad, multi-selección vs. selección única, edición de encuesta, snapshot de resultado al reenviar, feature flags

---

## 1. Qué es

Una encuesta es un sub-objeto de `Message` (`PollCreationMessage`, reutilizado sin cambios a través de seis campos de nivel superior versionados) que lleva una pregunta, una lista de opciones, un tope de selección, y ajustes opcionales de quiz/hora de cierre/visibilidad. Los votos (`pollUpdateMessage`), las opciones añadidas (`pollAddOptionMessage`) y las ediciones (`secretEncryptedMessage`) son mensajes de seguimiento separados atados al id del mensaje de creación y con clave derivada de su secreto por mensaje; ese cifrado (casos de uso HKDF, AES-GCM, AAD, reintento de identidad) está cubierto en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) y no se repite aquí. Este informe cubre la capa de tipo de mensaje: qué campo lleva qué, cómo elige el cliente entre ellos, validación y límites, y qué hacen los manejadores específicos de encuesta con los payloads descifrados. Todos los hallazgos son análisis estático de la APK decompilada 2.26.41.6 (fuentes Java bajo `java_src/`, más `res/values/strings.xml`); nada se capturó en el cable. Niveles: **found** = leído en código/recursos, **inferred** = deducido del código, **unknown** = no resuelto.

| Entidad | Campo en `Message` | Tipo proto | Rol |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | slot de creación original |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | creación en un chat de sub-grupo por defecto de comunidad |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | slot de creación de encuesta plana (por defecto actual para encuestas ordinarias) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | envoltura de compatibilidad futura alrededor de un `Message.pollCreationMessage` interno (campo 49) |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | slot de creación de quiz |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | slot de encuesta extendida (hora de cierre / ocultar-nombres-de-votante / permitir-añadir-opción) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | una imagen de opción de encuesta con imagen, vinculada a la futura encuesta vía `messageAssociation` |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | añade una opción a una encuesta existente |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | voto (cifrado) o metadata de voto |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | snapshot estático de resultado, encuesta reenviada a otro chat |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | igual, variante de quiz (conteos de voto puestos a cero) |

Números de campo verificados directamente contra `C30628DTw` (la clase proto `Message`), que declara las once constantes `POLL_*_FIELD_NUMBER` que coinciden con la tabla arriba.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Campos (found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | presente en el cable pero no usado por los manejadores leídos en esta pasada (los votos usan el `messageSecret` por mensaje, no este campo; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | pregunta de la encuesta, máx. 5000 caracteres, requerido |
| `options` | **3** | `Option` repetido | opciones de respuesta |
| `selectableOptionsCount` | **4** | uint32 | tope de selección, requerido (§11) |
| `contextInfo` | **5** | `ContextInfo` | contexto estándar |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | opción de respuesta correcta del quiz, requerida cuando `pollType=QUIZ` |
| `endTime` | **9** | int64 | marca de tiempo de cierre de la encuesta (ms) |
| `hideParticipantName` | **10** | bool | "Ocultar nombres de votantes" (§10) |
| `allowAddOption` | **11** | bool | "Permitir que otros añadan opciones" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, solo poblado para opciones de encuesta con imagen, §5).

### 2.2 Representación local

El cliente almacena una encuesta parseada como `C13J` (variante de imagen de quiz `C13K`), con opciones como objetos `C33283EeZ` que llevan el nombre crudo (`A04`), un digest SHA-256 calculado localmente del nombre (`A02`, §9.1) y, para opciones de imagen, el `optionHash` de cable (`A08`).

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

`pollCreationMessageV4` nunca es poblado por la ruta de envío leída en esta pasada; solo aparece al recibir (§3.3). El chequeo de comunidad reutiliza el mismo predicado `group_type == 3` que el fallback de reacción en texto plano en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2 (`C0GQ.A0A(chat) == 3`, fijado desde `isDefaultSubgroup_`); por qué una encuesta de sub-grupo por defecto obtiene su propio slot versionado en lugar de V3/V6 no se explica en el código leído aquí (inferred: orden histórico de despliegue, ya que el número de campo de V2 es el más bajo del conjunto extendido).

Así que en la práctica: **V3** es el slot actual para una encuesta ordinaria de selección múltiple/única sin extras, **V6** es el actual para una encuesta que usa hora de cierre, nombres de votante ocultos o añadir-opción, **V5** es el actual para quizzes, y **V2** es una variante específica de sub-grupo de comunidad de la misma forma base. **V1** (el campo sin versión 49) y **V4** no son elegidos por el remitente en este build.

### 3.2 `pollCreationMessageV4` = envoltura de compatibilidad futura (found, `F2N.CM7`)

El tipo proto de V4 es `FutureProofMessage` (`BD2`, campo único `message` = un `Message` interno). Al recibir, cuando el slot V4 está poblado, el cliente desenvuelve `BD2.message_` y lee el propio campo `pollCreationMessage` (49) de *ese* mensaje interno como el `PollCreationMessage` real. Esta es una envoltura de fallback genuina, no un campo muerto: un remitente que necesite emitir una variante de encuesta más nueva/no definida puede envolver una encuesta básica (con forma de campo 49) dentro de V4 para que los clientes más antiguos — que solo entienden el desenvuelto genérico `FutureProofMessage`, no el slot más nuevo — todavía rendericen una encuesta plana. Ninguna ruta de código en esta pasada pobla V4 al enviar, así que esto existe para compatibilidad adelante/atrás entre versiones de cliente, no para algo que el propio cliente 2.26.41.6 emita (inferred).

### 3.3 Selección y degradación del lado recepción (found, aproximado; el decompilador perdió algo de estructura de rama)

`F2N.CM7` verifica los bitfields del `Message` en orden V1 → V2 → V4 → V5 → V6 → fallback V3 y parsea cualquiera que esté poblado en el mismo validador (`F2N.A01`, §4). Tres flags controlan la aceptación de los campos extra de V6 al recibir; cuando un flag está desactivado la encuesta se **degrada** (se parsea como el placeholder genérico de compatibilidad futura en lugar de una burbuja de encuesta) en lugar de ser rechazada de plano:

| Campo extra | Compuerta | Efecto cuando la compuerta está apagada |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | registra `poll downgraded to FMessageFuture (receiving disabled)`, no se renderiza como encuesta |
| `hideParticipantName` | AB int **24885** | degradación (polaridad exacta del chequeo no completamente resuelta del flujo de control decompilado) |
| `allowAddOption` | AB int **25758** | degradación |

El anidamiento exacto de estas tres condiciones no pudo reconstruirse completamente (JADX reporta bloques duplicados/inalcanzables en `F2N.CM7`); los flags de compuerta y el resultado de degradación son found, la combinación booleana precisa es inferred.

### 3.4 Compuerta de contenido de imagen

`pollContentType = IMAGE` solo se honra en la ruta de parseo V3/V5 cuando el bit de `pollContentType` está fijado; si está fijado pero el valor no es `IMAGE`, el mensaje se rechaza (`return null`, cae al parser genérico) en lugar de tratarse silenciosamente como texto.

---

## 4. Validación de creación (found, `F2N.A01`)

Validador único compartido por todos los campos de creación versionados. Lanza, código de error **11** salvo que se indique:

| Chequeo | Regla | String de error |
|-------|------|--------------|
| Nombre presente | el bit de `name` debe estar fijado | `poll_creation_missing_name` |
| Longitud de nombre | 1–5000 caracteres (salvo que un contexto de parseo laxo lo evite, §4.1) | `poll_creation_invalid_name` |
| Respuesta correcta de quiz | si `pollType=QUIZ`, el bit de `correctAnswer` debe estar fijado | `poll_creation_missing_correct_answer` |
| Opciones presentes | al menos una opción, salvo que aplique el bypass de cero-opciones (§4.1) | `poll_creation_missing_options` |
| Conteo de opciones (inferior) | ≥ 2 opciones (0 bajo el bypass) | `poll_creation_invalid_options_count` |
| Conteo de opciones (superior) | ≤ `min(AB int 1408, 12)` — 12 es un tope duro del cliente sin importar el valor del servidor | `poll_creation_invalid_options_count` |
| Longitud de nombre de opción | 1–2500 caracteres por opción | `poll_creation_invalid_option` |
| Nombre de respuesta correcta | si es quiz, `correctAnswer.optionName` debe ser no vacío | `poll_creation_missing_correct_answer_name` |
| Opciones duplicadas | los nombres de opción deben ser únicos | `poll_creation_duplicate_options` |
| Opciones duplicadas recortadas | bajo el flag AB **25758**, los nombres recortados de espacios también deben ser únicos | `poll_creation_duplicate_trimmed_options` |
| La respuesta correcta coincide con una opción | el nombre de respuesta correcta del quiz debe igualar el nombre de una opción | `poll_creation_unmatched_correct_answer` |
| Conteo seleccionable presente | el bit de `selectableOptionsCount` debe estar fijado | `poll_creation_missing_selectable_options_count` |
| Rango del conteo seleccionable | `0 <= selectableOptionsCount <= options.size()` (o `<= min(1408,12)` bajo el bypass) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Bypass de cero-opciones / laxo (ruta de código found, semántica inferred)

Un booleano local (`z`) calculado a partir del flag AB bool **37909**, solo consultado cuando un contador interno de contexto de parseo iguala 1, relaja el mínimo de opciones a 0 y amplía el tope de conteo seleccionable al límite crudo `min(1408,12)` en lugar de `options.size()`. El valor de contexto de parseo al que esto corresponde (recepción normal vs. alguna otra ruta de ingesta, p. ej. sincronización de historial) no fue resuelto; esto se registra como found-pero-sin-explicar en lugar de una función confirmada de "encuesta sin opciones" visible al usuario.

### 4.2 Bypass de sincronización de historial / nombre laxo

Un flag de contexto separado (`c33371Eg0.A0W`) cortocircuita tanto el chequeo de longitud de nombre como (equivalentemente, en `F39`, §9) el chequeo de longitud de nombre del snapshot de resultado, aceptando el string crudo sin verificar. Consistente con una ruta de parseo de fuente confiable (p. ej. re-importación de historial local) en lugar de una recepción de red normal; no confirmado independientemente.

---

## 5. Opciones de encuesta con imagen: `pollCreationOptionImageMessage`

### 5.1 Estructura y vinculación (found)

`pollCreationOptionImageMessage` (campo 90) envuelve un `ImageMessage` subido ordinario dentro de un `FutureProofMessage` — la imagen **no** está embebida en `PollCreationMessage.Option`. Cada imagen de opción se envía como su propio mensaje hijo, asociado con la encuesta (aún no enviada) vía `MessageContextInfo.messageAssociation`, tipo de asociación `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; este es el valor de enum de este build — un build anterior lo tenía en 7, el valor numérico no es estable entre versiones y debe re-leerse por release). El ayudante del lado envío "MediaPollAssociationProvider" (en `C20M`) cuenta las filas de `message_association` para el row id de la encuesta padre y tipo de asociación `6`; una vez que el conteo llega al conteo de opciones, todas las imágenes de opción se consideran subidas y el cliente procede a enviar la encuesta misma con `pollContentType = IMAGE`.

### 5.2 Hash de opción para opciones de imagen (inferred, trasladado de un build anterior, no re-derivado línea por línea en 2.26.41.6)

Para opciones de texto plano el campo de cable `optionHash` se deja vacío; el único hash calculado para una opción de texto plano es el digest de búsqueda local `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(confirmado directamente en 2.26.41.6, §9.1 — este es el hash usado para emparejar selecciones de voto, no el campo proto `optionHash`). Para opciones de **imagen** el campo proto `optionHash` está poblado; un rastreo de versión anterior de la secuencia de envío encontró que combina el hash del nombre de la opción con el `fileSha256` de la imagen subida:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Esta fórmula no fue re-verificada contra el código de 2.26.41.6 en esta pasada (la clase que la calcula no fue localizada); se traslada como inferred y debería re-verificarse antes de confiar en ella.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, campo 121)

### 6.1 Campos (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, misma forma que la del voto, §7).

### 6.2 Envío (found, `F2L.ADr`)

Construye un `Option` a partir del nombre nuevo (y, para encuestas de imagen, su hash), adjunta la clave de la encuesta de origen, y — para chats 1:1, cuando no es un contexto de edición — resuelve la identidad del remitente a través del límite LID/PN del mismo modo que la capa de secreto de mensaje lo hace para otros add-ons (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 paso 4). La opción *no* está cifrada en sí como secreto en esta capa del modo en que lo está un `pollUpdateMessage`: el payload de add-option viaja como un campo de mensaje normal; lo que se envuelve en `secretEncryptedMessage` (tipo `POLL_ADD_OPTION`) es el intento de añadir opción como un todo cuando debe viajar sobre el esquema de secreto de mensaje (§8).

### 6.3 Validación al recibir (found, `F2L.CM7`)

| Chequeo | Error |
|-------|-------|
| Compuerta de función: AB int **25758** debe ser no-cero | error **10017** |
| `pollCreationMessageKey` presente | `poll_add_option_missing_poll_message_key` |
| `addOption` presente | `poll_add_option_missing_poll_option` |
| Nombre de opción no vacío, ≤ 2500 caracteres | `poll_add_option_invalid_option` |

El objeto local resultante se cifra como secreto para transporte usando el caso de uso `Poll Add Option` (llamada confirmada al ayudante de secreto de mensaje con `AnonymousClass122.POLL_ADD_OPTION` como tag de asociación). Las opciones añadidas se rastrean para emparejamiento con opción existente del mismo modo que las opciones de encuesta con imagen (tipo de asociación `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (voto y metadata de voto)

El cripto completo (caso de uso HKDF `Poll Vote`, AAD, AES-GCM, reintento de identidad LID/PN) está en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7; esta sección cubre solo lo que el manejador de voto de encuesta (`DUA`, extiende `F2P`) hace con el texto plano.

### 7.1 Dos rutas de envío/recepción (found)

El flag AB bool **6772** selecciona entre:
- **activado** (actual): un ayudante de cifrado compartido (`C33285Eeb`) construye el ciphertext y la `MessageKey`; el voto se reintenta desde un par `(iv, payload)` almacenado previamente cuando está presente en lugar de re-cifrar.
- **desactivado** (legacy): una rama en línea en `DUA` hace la misma llamada HKDF/AES-GCM directamente, derivando la identidad del remitente objetivo ella misma (propio LID para votos en la propia encuesta del votante, de otro modo el JID resuelto del objetivo del voto).

### 7.2 Payload de voto: `PollVoteMessage` (`DPF`)

Campo único `selectedOptions` **1**, bytes repetidos — cada entrada es un digest SHA-256 de 32 bytes del nombre de opción (§9.1), no un índice. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`) valida la selección descifrada:

| Chequeo | Regla | Tag de log |
|-------|------|------|
| Tamaño de selección | ≤ 12 **y** ≤ el `selectableOptionsCount` de la encuesta (cuando > 0) | `poll_vote_invalid_options_count` |
| Forma de hash | cada hash seleccionado decodifica a exactamente 32 bytes | `poll_vote_invalid_option_hashes` |
| Duplicados | ningún hash repetido en un voto | `poll_vote_duplicate_option_hashes` |
| Resolución | cada hash seleccionado debe coincidir con uno de los hashes de opción conocidos (no eliminados) de la encuesta | devuelve un resultado de error, sin coincidencia -> voto rechazado |

### 7.3 Hora de cierre y metadata (found, `DUA.A01`)

Un voto cuyo `senderTimestampMs` sea posterior al `endTime` de la encuesta se rechaza (`poll_update_past_end_time`); bajo el flag AB bool **2321** un evento de voto rechazado además alimenta un contador de telemetría (`N0e`). La `metadata` del voto (`pollNameHash`, `lastEditStanzaId`) se estampa al enviar solo bajo el flag AB bool **31593**; al recibir, un bloque de metadata faltante/vacío se registra `"unstamped"` (no rechazado por sí solo) mientras que un estampado *no coincidente* (verificado por `C32977EZa`) descarta el voto con `poll_update_tc_drop`. Esta metadata existe para que un cliente pueda detectar que está votando contra una encuesta cuyo historial de ediciones todavía no ha alcanzado.

---

## 8. Edición de encuesta (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Llevada dentro de la envoltura genérica `secretEncryptedMessage` (campo 82), no un portador específico de encuesta; ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4 para el envelope, AAD, y la tabla de código de error (`poll_edit_message_stanza_invalid`, compuerta AB int **24886**, error **10016**). La validación específica de encuesta (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) requiere:

- el mensaje interno es FMessage tipo 66 y es una encuesta tanto antes como después de la edición;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` y `pollType` son **sin cambios** entre la encuesta almacenada y la editada — solo el texto de la pregunta y/o los textos de opción pueden diferir;
- emparejamiento de opciones: con un flag por chat (`EOI.A01()`, id no resuelto) activado, las opciones editadas se emparejan contra un historial de renombrado almacenado vía un emparejamiento secuencial (que preserva el orden), permitiendo renombrar opciones in situ; el comportamiento exacto de la rama de comparación sin renombrado es inferred (JADX de nuevo pierde parte del flujo de control — la función cae a `poll_edit_invalid_edits` en esa rama en la forma decompilada, lo cual es improbable que sea el comportamiento real del cliente para una edición sin cambios).

Existe un string de toast "Couldn't edit poll" en los recursos, confirmando que la edición de encuesta es visible al usuario en este build, no meramente una ruta de protocolo reservada.

### 8.1 UI de edición de encuesta (nueva en 2.26.45.10) — op de cable no resuelta

Un nuevo paquete `com.whatsapp.polls.ui.edit` envía `PollEditActivity` más
diálogos de apoyo (`PollEditDiscardChangesDialog`, `PollEditSendFailedDialog`,
`PollOptionRemoveConfirmationDialog`), permitiendo que un remitente renombre una encuesta
ya enviada o añada/elimine opciones de ella. Found y unknown, a partir de rastreo
estático de smali (sin decompile más allá de leer el smali existente):

- **Found:** `PollEditActivity` está respaldada por un estado de edición guardado en
  `SavedStateHandle` (view model `LX/8kp`, payload de edición `LX/A4G`: nombre/id, string
  de nombre de la encuesta, filas de opción actuales, un `Set<Long>` de ids de fila
  eliminados). Las filas de opción (`LX/JZ8`) no llevan ningún flag de eliminación — una
  opción simplemente está ausente de la lista final diferenciada contra el estado de
  encuesta en vivo (`LX/8kp;->A03(LX/A4G;LX/9ei;LX/8kp;)LX/9oc;`). La eliminación de opción
  está controlada por un chequeo de despliegue escalonado,
  `LX/Ihb;->getPollRemoveOptionRollout()LX/1yG;` — una compuerta de función del lado
  cliente, no evidencia de una nueva op de cable.
- **Found:** el diff de proto-schema entre 2.26.41.6 y 2.26.45.10 contiene **cero**
  cambios relacionados con encuestas — ningún campo nuevo o renombrado para renombrado u
  eliminación de opción aparece en ningún lugar del schema extraído para esta versión.
- **Inferred:** añadir una opción desde esta UI probablemente todavía viaja sobre el
  `pollAddOptionMessage` existente (§6, campo 121) — el affordance de "añadir fila" de la
  UI coincide con la forma de ese mensaje y no se introdujo ninguna primitiva de
  reemplazo de añadir-opción. No confirmado rastreando el manejador de guardado.
- **Unknown:** el renombrado y la eliminación de opción no tienen ninguna primitiva de
  cable confirmada. Dos candidatos no confirmados, ninguno más probable que el otro con
  la evidencia actual: (1) un reemplazo de encuesta completa vía `Message.editedMessage`
  (`FutureProofMessage` envolviendo un `pollCreationMessage` fresco), o (2) reutilización
  del campo cifrado opaco `vote` de `pollUpdateMessage` (`PollEncValue`, §7) para una
  actualización no-de-voto. La llamada de red real del botón de guardar está detrás de un
  despachador `View.OnClickListener` compartido, fusionado por R8 (`LX/A50`) cuya rama de
  `switch` relevante no pudo aislarse solo con smali — este es el bloqueador específico,
  no una elección de alcance.

Esto se deja abierto en lugar de resolverse como una mejor conjetura; re-verificar una
vez que un diff de proto contra una versión posterior muestre un campo nuevo, o una vez
que se rastree la rama de despacho de `LX/A50`.

---

## 9. Internals del emparejamiento de voto

### 9.1 Hash de opción (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

SHA-256 plano del texto visible de la opción, sin material de clave. Este es el valor almacenado por opción local (`C33283EeZ.A02`) y el valor contra el que se emparejan las entradas de `selectedOptions` de un voto. Cualquier aplicación que conozca el texto de la opción puede calcular el mismo hash — la privacidad de un voto viene enteramente del cifrado de secreto de mensaje del payload del voto (§7, y [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), no de que el hash sea impredecible.

---

## 10. Modelo de privacidad / anonimato del voto

| Afirmación | Estado |
|-------|-------|
| Los votos están cifrados de extremo a extremo por votante, por encuesta (caso de uso HKDF `Poll Vote`) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| La opción seleccionada se identifica por un hash de contenido, no un índice | found, §9.1 |
| `hideParticipantName` ("Ocultar nombres de votantes") suprime la visualización de quién votó, en la UI | found (string `str2137`, campo 10 de `PollCreationMessage`) |
| `hideParticipantName` oculta al votante del servidor o de otros clientes a nivel de protocolo | **no respaldado por el código leído aquí** — el envelope `participant`/`from` (es decir, la identidad del votante) se entrega y autentica del mismo modo para cada add-on sin importar este flag (ver [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName` es un ajuste solo de visualización en el objeto de encuesta, no un cambio de enrutamiento o cifrado |
| El creador de la encuesta siempre puede determinar quién votó | inferred — nada en la ruta de descifrado de voto (§7, §9) depende de `hideParticipantName`; el cliente del creador descifra cada voto con la identidad del votante como el modificador |

En resumen: las encuestas de WhatsApp no son anónimas para el creador de la encuesta. "Ocultar nombres de votantes" solo controla si *otros participantes* (en la lista "Votos de la encuesta") ven quién votó; no cambia lo que está criptográficamente vinculado al voto, y el servidor nunca conoce el contenido del voto de ningún modo (la garantía E2E habitual, no algo específico de este flag).

---

## 11. Multi-selección vs. selección única

`selectableOptionsCount` (campo 4) es el único mecanismo: un voto con más selecciones que este valor se rechaza (§7.2). No existe un booleano separado "es multi-selección" en el cable — la selección única es simplemente `selectableOptionsCount = 1`. La UI de creación expone esto como un solo toggle, **"Permitir varias respuestas"** (string `str425f`); cuando está apagado se infiere que el cliente envía `selectableOptionsCount = 1`, cuando está encendido se infiere que envía `selectableOptionsCount = options.size()` (la UI no parece exponer un tope numérico arbitrario — inferido del único string booleano, no confirmado independientemente en el código de la UI de creación). El protocolo en sí permite cualquier valor `0..options.size()` (§4), así que un valor del lado cliente distinto de 1 o "todas las opciones" es posible aunque la UI de fábrica no lo ofrezca. Los quizzes son implícitamente de selección única (una respuesta correcta; string visible al votante `"Quiz • Select one correct answer"`, `str57a5`).

Las etiquetas visibles al votante confirman los dos modos: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: snapshot al reenviar

### 12.1 Propósito (found, `F1A`)

Reenviar una encuesta en vivo a otro chat **no** reenvía la encuesta interactiva. `F1A` (uno de varios conversores de "forward" que todos implementan la misma interfaz de conversión usada en varios tipos de mensaje — el conversor hermano para tipos no soportados lanza `"Cannot forward message of type: ..."`) convierte la encuesta en vivo (`C13J`) en un objeto `Dd2`: texto de la pregunta, el nombre de cada opción y el **conteo de voto local actual**, y el tipo encuesta/quiz. Esto se serializa luego como `pollResultSnapshotMessage` (encuesta plana) o `pollResultSnapshotMessageV3` (quiz) y se renderiza con un view holder dedicado (`DWH`), distinto de la burbuja interactiva de encuesta.

### 12.2 Campos (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (`PollVote` repetido — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (mismo enum `PollType` que la creación).

### 12.3 Validación (found, `F39`)

Misma forma de chequeos que la creación: nombre 1–5000 caracteres, al menos 2 opciones, como máximo `min(AB 1408, 12)` opciones, cada nombre de opción 1–2500 caracteres. Para la variante de **quiz** (`V3`), los conteos de voto se fuerzan a 0 al enviar — un snapshot de quiz reenviado nunca revela los conteos, solo la pregunta y la lista de opciones.

---

## 13. Resumen de límites

| Ítem | Límite | Fuente |
|------|-------|--------|
| Longitud del nombre de encuesta/pregunta | 1–5000 caracteres | `F2N.A01`, `F39.A00` |
| Longitud del nombre de opción | 1–2500 caracteres | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Conteo de opciones (creación, snapshot) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Opciones seleccionadas por voto | ≤ 12 y ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| Rango de `selectableOptionsCount` | 0–options.size() (0–12 bajo el bypass de contexto laxo, §4.1) | `F2N.A01` |
| Tamaño de hash de opción (entradas de voto) | exactamente 32 bytes | `AbstractC33199EdC` |

---

## 14. Feature flags (ids tal como se leen en los call sites; nombres no resueltos)

| ID | Tipo | Controla |
|----|------|----------|
| **1408** | int | conteo máximo de opciones de encuesta configurado por servidor, tope duro del cliente de 12 sin importar el valor |
| **24884** | bool | honrar `endTime` al recibir una encuesta extendida (V5/V6); apagado -> degradada a un placeholder de compatibilidad futura |
| **24885** | int | controla la aceptación de `hideParticipantName` al recibir (polaridad exacta no resuelta) |
| **24886** | int | compuerta de recepción de edición de encuesta; 0 -> rechazada, error 10016 |
| **25758** | int (truthy) | compuerta de recepción de añadir-opción de encuesta (error 10017); también controla el rechazo de opción-recortada-duplicada en la creación |
| **31593** | bool | estampar metadata `pollNameHash`/`lastEditStanzaId` en un voto saliente |
| **6772** | bool | voto de encuesta: ayudante de cifrado compartido (activado) vs. ruta en línea legacy (desactivado) |
| **37909** | bool | permite una encuesta con cero opciones en un contexto de parseo específico (no resuelto) |
| **2321** | bool | detalle extra de telemetría registrado cuando un voto se rechaza por estar después de la hora de cierre de la encuesta |

Los flags de la capa de secreto de mensaje que también afectan a las encuestas (compuerta de caso de uso de edición **17811**, compuertas de generación, etc.) están documentados en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16 y no se repiten aquí.

---

## 15. Baileys (solo hechos confirmados)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17 ya cubre las partes de una implementación JavaScript (`baron-baileys-v2` 1.5.17) relevantes para encuestas, a partir de la lectura de `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`:

- La derivación HKDF y los strings de caso de uso `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` coinciden exactamente con los literales del cliente Android, incluyendo el AAD `id\0modifier` para `Poll Vote`.
- El AAD, el reintento de identidad (PN/LID), y el manejo de secreto faltante (recurrir a la actualización cruda, no descifrada) coinciden con el comportamiento de Android descrito en este informe (§7) y en [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3.
- No se encontró ninguna ruta de cifrado del lado envío para `pollUpdateMessage` (o `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) en los archivos leídos — es decir, esa implementación podía descifrar un voto entrante pero los archivos revisados no contenían código para cifrar y enviar uno.

Nada específico de encuesta más allá de lo ya afirmado ahí se re-verificó independientemente en esta pasada (no se leyó código de creación de encuesta, hash de opción, ni edición de encuesta de Baileys); no se hacen más afirmaciones de Baileys aquí.

---

## 16. Casos de error

| Síntoma | Causa | Arreglo |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | menos de 2 o más de `min(1408,12)` opciones | mantener las opciones dentro del rango |
| `poll_creation_unmatched_correct_answer` | `correctAnswer.optionName` del quiz no iguala el nombre de ninguna opción | fijar la respuesta correcta a una coincidencia exacta |
| Encuesta silenciosamente no mostrada (degradada) | `endTime`/`hideParticipantName`/`allowAddOption` fijados en una encuesta V6 pero el flag AB correspondiente está apagado en el receptor | lado remitente, no arreglable por contenido; vacío de capacidad del receptor |
| `poll_vote_invalid_options_count` | el voto selecciona más opciones que `selectableOptionsCount`, o más de 12 | respetar el tope de la encuesta |
| `poll_update_past_end_time` | marca de tiempo del voto (o añadir opción / edición) posterior a `endTime` | votar antes de que cierre la encuesta |
| `poll_update_tc_drop` | el `pollNameHash`/`lastEditStanzaId` del voto no coincide con la vista del receptor de la encuesta | resincronizar el historial de edición de la encuesta antes de votar |
| error **10017** en añadir-opción | AB **25758** es cero en el receptor | vacío de capacidad del receptor |
| error **10016** en edición de encuesta | AB **24886** es cero en el receptor | vacío de capacidad del receptor |
| `poll_add_option_past_end_time` | opción añadida después de `endTime` | añadir opciones antes de que cierre la encuesta |

---

## 17. Distinciones clave

| Esto | No esto |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (tipo `PollCreationMessage`) | `pollCreationMessageV4` (`FutureProofMessage` envolviendo una encuesta básica interna) |
| `pollUpdateMessage` (voto, o metadata de voto) | `secretEncryptedMessage` con `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` (edición de encuesta / añadir opción) |
| `pollAddOptionMessage` (el payload de la nueva opción) | la envoltura `secretEncryptedMessage` que lo lleva sobre el cable cuando está atado a secreto de mensaje |
| `pollResultSnapshotMessage`/V3 (estático, reenviado) | la encuesta interactiva en vivo (`pollCreationMessage*`) |
| Selección de opción por hash SHA-256(nombre) | selección por índice — las encuestas de WhatsApp nunca seleccionan por posición |
| `hideParticipantName` (ajuste de visualización de UI) | anonimato del remitente del voto (no existe; el creador siempre resuelve al votante) |
| `selectableOptionsCount` (la única señal multi/selección-única) | un booleano separado "es multi-selección" (no existe ninguno) |

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

| Ítem | Estado |
|------|--------|
| Polaridad exacta de AB **24885** (aceptar/degradar hideParticipantName) | estructura de rama decompilada incompleta |
| Fórmula de hash de opción con imagen (`nameHash`+`imageHash`) para 2.26.41.6 | trasladada de un build anterior, no re-derivada en el código de este build |
| Id de flag AB detrás del toggle por chat de "renombrado de opción ordenado" usado en el emparejamiento de edición de encuesta (`EOI.A01()`) | id no resuelto |
| Rama sin renombrado de la comparación de opción en edición de encuesta | el decompilador pierde parte del flujo de control; la forma decompilada literal siempre cae a `poll_edit_invalid_edits`, lo cual es improbable que sea el comportamiento real para una edición sin cambios |
| Valor de contexto de parseo (`c33371Eg0.A00 == 1`) que habilita el bypass de cero-opciones (AB **37909**) | no identificado (sincronización de historial vs. otra ruta) |
| Si la UI de creación de fábrica puede enviar valores de `selectableOptionsCount` distintos de 1 o "todas las opciones" | inferido de un único string de toggle booleano, no confirmado contra el código de la UI |
| Estabilidad del valor numérico de asociación `MEDIA_POLL` entre versiones | found como 6 en 2.26.41.6; un build anterior usaba un valor distinto, así que no hardcodearlo entre versiones |
