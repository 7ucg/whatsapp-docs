<!-- src-sha1: b8f7c5d44373d4a7bc19be29e7bd26af81a86f85 -->
# WhatsApp Message Secrets — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** `messageSecret` por mensaje (generación, `MessageContextInfo`, almacén local, sincronización de historial), derivación de clave por caso de uso (HKDF), IV / AAD de AES-GCM, add-ons cifrados (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, ediciones de `secretEncryptedMessage`), vinculación de identidad remitente/objetivo y reintento LID/PN, huérfanos y fallbacks de secreto faltante, extensiones del stanza `<message>` (atributos, atributos de `<enc>`, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, chequeo de soporte de companion), feature flags, comparación con Baileys

---

## 1. Qué es (técnicamente)

Cada mensaje que puede más tarde recibir un seguimiento cifrado lleva un secreto aleatorio de 32 bytes en su propio payload cifrado de extremo a extremo (`MessageContextInfo.messageSecret`). Un seguimiento (reacción, voto de encuesta, respuesta de evento, comentario, edición) se cifra con una clave derivada de ese secreto, el id del mensaje original, el remitente original y el modificador. El servidor retransmite el seguimiento como un mensaje E2E ordinario pero no puede leerlo ni moverlo a otro objetivo, usuario o caso de uso sin romper la autenticación GCM. Todas las afirmaciones son análisis estático de la APK decompilada; nada se capturó en el cable. Niveles: **found** = leído en código, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres obfuscados se re-resolvieron en 2.26.41.6 a partir de strings estables (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, strings de caso de uso, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

El mismo release también define las extensiones del stanza `<message>` (sección 10 en adelante): atributos y nodos hijos que clasifican y enrutan un mensaje pero no llevan su contenido. Se agrupan aquí porque `<meta polltype>` / `<meta event_type>` deben coincidir con el payload cifrado como secreto (7.4).

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Ayudante cripto (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` cifrar, `A04` descifrar (reintento de identidad), `A02` resolución de clave objetivo |
| Portadores de parámetros de cifrado/descifrado | `C32833ETl` / `C32854EUg` | datos, remitente, clave objetivo, caso de uso / IV, payload, claves, remitente |
| Derivación de clave | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, salt cero |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | nativo, tag de 16 bytes |
| Proveedores de AAD | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (ninguno) | datos adicionales |
| Generador de secreto | `AbstractC33322EfC.A01` | `SecureRandom`, 32 bytes |
| Almacén de secreto (`MessageSecretStore`) / extra en memoria | `C35311ad` (tabla `message_secret`) / `C35171aP` en el mensaje `C13G` | persistir y llevar |
| Mapeador de clave original (`ReferentialKeyUtil`) | `C43661qB.A03` | clave del mensaje original sin editar |
| Manejadores de reacción | `DU8` (enviar), rama `F2P` (recibir) | `reactionMessage` / `encReactionMessage` |
| Voto de encuesta / respuesta de evento / comentario | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Ediciones cifradas como secreto (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Creación de encuesta / evento (secreto tomado al recibir) | `F2N` / `F2M` | lee `messageSecret` en el FMessage |
| Proto: contexto / mensaje / clave | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Selector de `type` del stanza | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Contribuidores de stanza saliente | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` flags, `F69` cap, `F6H` padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | construyen hijos de `<message>` |
| Acumulador `<meta>` | `EZV` (atributos `A01`, hijos `A00`) | un nodo `<meta>` |
| Constructor de atributos `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Chequeo de soporte de companion | `C34757F6a` + `AbstractC32927EXc` | lista de permitidos de tipo e hijo |
| Parsers de spec entrante | `C33474Ehg` (status / regular), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | extracción de atributo e hijo |
| Evento de error WAM | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. El secreto por mensaje

### 2.1 Dónde vive (found)

`MessageContextInfo` (`C30624DTs`) es el campo **35** de `Message` (`C30628DTw`). Campos relevantes aquí:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | mensaje / int | pista de lista de dispositivos (no relacionado con secretos) |
| `messageSecret` | **3** | bytes (32) | secreto por mensaje |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | duración del add-on (pin: debe ser 0 para unpin) |
| `botMessageSecret` | **6** | bytes (32) | variante de bot del secreto |
| `botMetadata` | **7** | mensaje | contexto de bot |
| `reportingTokenVersion` | **8** | uint32 | versión de token de reporte de este mensaje |
| `messageAddOnExpiryType` | **9** | enum | expiración del add-on |
| `messageAssociation` | **10** | mensaje | asociación |

El portador de sincronización de historial `WebMessageInfo` (`C30626DTu`) tiene su propio campo `messageSecret` **49** (found), usado cuando los mensajes se exportan a un nuevo companion (sección 2.4).

### 2.2 Generación (found, condiciones parcialmente inferred)

El secreto es `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). Se adjunta antes de que el mensaje sea serializado:

| Lugar | Condición |
|-------|-----------|
| `C33166Ecf.A06` (preparar envío) | el mensaje no tiene secreto y al menos uno de: clase de encuesta `C13J`; `EZN.A01(msg)` (clase bot/add-on, con flags de tipo de chat **2200**, **11104**, **19303**); compuertas de clase de chat: grupo con flag **3143**, lista de difusión con **3144**, estado con **3145**, compuerta de clase **3146**; `C35201aS.A00` (flag **3142**, chat propio/bot); mensaje de evento `C213509Ao` |
| `AJ0` (procesador de envío) | la versión de token de reporte `C35241aW.A05()` (AB int **8860**, limitado por `AbstractC35301ac.A00`) es no-cero y la clase de mensaje no está excluida por `C35241aW.A02` (status, newsletter, clases de add-on seleccionadas) |
| `C72h`, `C34455Exe`, `EPA` | los objetos de estado (`AbstractC34478Ey1.A0R`) obtienen un secreto fresco en la creación |
| `C33437Eh4` | mensaje de bot "request welcome", solo cuando su llamante lo pide |
| `C9mW` | tipo de mensaje 117, flag **24741**, cuando no hay ninguno presente |

Los predicados detrás de `EZN.A01`, `C35201aS.A00` y las compuertas `3142`..`3146` no se resolvieron completamente; la lista arriba dice qué verifica el código, no qué mensajes visibles al usuario califican. Los mensajes sin secreto no pueden recibir add-ons cifrados de este cliente (sección 9).

### 2.3 Almacenamiento local (found)

`C35311ad` escribe `message_secret(message_row_id, message_secret)` con semántica de reemplazo (`MessageSecretStore/insertMessageSecret`) y lee la última fila para un `message_row_id`. El FMessage lo guarda como extra `C35171aP` (`A0L` fija, `A0c` obtiene, `A0Q` = no vacío). Dos procesadores en `AbstractC17240jU` (`C35161aO` y uno anónimo) lo escriben cuando el extra está sucio y el chat califica.

### 2.4 Validación y transferencia del lado recepción (found)

| Paso | Comportamiento |
|------|------|
| Validador proto `C33475Ehh.A0V` | `message_secret` debe tener exactamente **32** bytes, código de error **67**; la variante de bot (`bot_message_secret`, grupo `whatsapp_security`) se valida del mismo modo |
| Creación de encuesta `F2N` | copia `messageSecret_` al nuevo FMessage (`A0L`) |
| Respuestas de pregunta de estado `C34838F9e` | misma copia para `statusQuestionAnswerMessage` |
| Exportación de sincronización de historial `C34388EwZ.A00` | escribe el secreto almacenado en `WebMessageInfo.messageSecret` (49) |
| Importación de sincronización de historial `C34388EwZ.C59` | lo copia de vuelta (`A0L`) |
| Comentarios `C34387EwY` | reconstruye un `MessageContextInfo` a partir de `WebMessageInfo.messageSecret` para el hilo de comentario |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) registra `message_secret_error` **0** = faltante (mapea al código de error 66) o **1** = longitud inválida (67) para mensajes que requieren un secreto (`AbstractC33322EfC.A00`: tiene el flag y no es de la clase `C35281aa`).

---

## 3. Derivación de clave por caso de uso

### 3.1 Fórmula (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract con un salt cero de 32 bytes (`AbstractC38971i1.A00(ikm, salt)`), luego el bucle expand de RFC 5869. Fundamentos de HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) sección 5.1. La salida de 32 bytes se usa como clave AES-256 (inferido de la longitud; la llamada nativa toma la clave como `byte[]`).

Entradas:

| Entrada | Fuente | Notas |
|-------|--------|-------|
| `originalMessageId` | id de clave del objetivo tras `ReferentialKeyUtil` (`C43661qB.A03`) al cifrar; id de clave del `targetMessageKey` del proto al descifrar | para un objetivo editado este es el id del mensaje **original** (log `getOriginalKey`) |
| `targetSender` | autor del mensaje original: remitente almacenado (`C12300aw.A01`) | `UserJid`, así que sin sufijo de dispositivo (a nivel de tipo; la forma de string `user@server` es inferred) |
| `modifier` | autor del add-on: JID de cuenta propia (`C09A.A0G`, un LID, devuelto por `CUC()` / `Ash()`) al enviar, el JID remitente del envelope al recibir | |
| `useCase` | string de 3.2 | sin separador entre los cuatro componentes |

El JID propio es un JID de cuenta LID (`C14080dr`, servidor `lid`, chequeo "Invalid LID"). Tanto `AnonymousClass091.Ash()` como `CUC()` devuelven el mismo campo.

### 3.2 Strings de caso de uso (found)

| Caso de uso | Portador | AAD | Literal Java en 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | ninguno | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | ninguno | `F3W` |
| `Event Edit` | `secretEncryptedMessage` tipo 1 | ninguno | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` tipo 2 | ninguno | `F3Y.A00`, solo con flag **17811** |
| `Poll Edit` | `secretEncryptedMessage` tipo 4 | ninguno | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` tipo 5 | ninguno | `F3Y.A00` |
| `WASA` | ruta de bot (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | dos etapas, 3.3 |
| `Report Token` | clave de token de reporte | nativo | sin literal Java; presente en `libwhatsapp.so`, derivado nativamente (3.4) |

### 3.3 Variante de bot / WASA (found, detalles inferred)

Para el caso de uso `WASA` la derivación tiene dos etapas y ningún string de caso de uso en la segunda:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` es el modificador y `jidB` el JID remoto (chat), que debe ser un `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`); el id es la clave del mensaje actual cuando está presente, de otro modo la clave objetivo (lambda `C33285Eeb.A03`). Contraparte nativa: `WcmBotMessageSecretAPICreateWithMessageSecret`. Contexto de Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Clave de token de reporte (found / inferred)

`C33364Efs.A06` y `C33421Ego` llaman a `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: el objeto nativo deriva la clave para el id de caso de uso **5**; el lado Java solo pasa strings crudos de JID. El string `Report Token` existe en la biblioteca nativa; el mapeo del id 5 a ese string es inferred. Token y subida: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. Disposición AEAD

| Ítem | Valor | Nivel |
|------|-------|------|
| Cifrado | AES-GCM, nativo (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; descifrar `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Clave | 32 bytes de la sección 3 | found |
| IV | **12** bytes aleatorios por cifrado (`SecureRandom`); el descifrado rechaza cualquier otro tamaño | found |
| Tag | 16 bytes; la constante 16 se pasa en ambas llamadas; la posición (añadida al ciphertext) es inferred de la implementación de descifrado de Baileys | found / inferred |
| AAD | por caso de uso (3.2); `null` cuando el proveedor es `C34631F1e` | found |
| Texto plano | el proto interno serializado (tabla 5) | found |
| Salida | triple `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| Resultado vacío | log `encryption values are invalid`, error `Encryption using iJniBridge failed` | found |

Reintento de voto de encuesta: si el voto ya tiene IV y payload (`C30957Dd6.A03` / `A04`) se reenvía el mismo ciphertext en lugar de re-cifrar (found, rama legacy de `DUA`).

---

## 5. Portadores y textos planos

| Portador (campo en `Message`) | Clase | Campos | Texto plano descifrado |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (limpiado antes del cifrado), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (bytes repetidos, hashes de opción) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 desconocido, 1 va, 2 no va, 3 tal vez), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `Message` completo (el cuerpo del comentario); la forma en texto plano es `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | `Message` completo |
| `reactionMessage` **46** | `DSH` | forma en texto plano | reacción plana |
| `conditionalRevealMessage` **120** | n/a | no es el esquema de message-secret (sección 14.1) | mensajes programados |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. El valor 3 no existe en este build (`forNumber(3)` devuelve null, tratado como unknown y rechazado).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Lado remitente

### 6.1 Ruta común (found, `C33285Eeb.A03`)

1. Resolver el FMessage objetivo por clave (`target message not found. Cannot proceed further` -> error 71).
2. Leer su secreto de `message_secret`; null o longitud != 32 -> `message secret missing or invalid` (66).
3. Clave original vía `C43661qB.A03` (null -> error 0). Remitente objetivo vía `C12300aw.A01`.
4. En un chat 1:1 (`C0DZ.A0k(chat)`) el remitente objetivo se convierte al namespace del modificador: modificador LID y objetivo PN -> objetivo mapeado de PN a LID; modificador PN y objetivo LID -> objetivo mapeado de LID a PN. En grupos, sin conversión.
5. Solo Event Response: flag **15791**, chat 1:1 y un modificador de tipo cuenta -> modificador convertido a PN.
6. IV aleatorio de 12 bytes, derivar clave (3.1), AES-GCM con el AAD de caso de uso.
7. Construir el `MessageKey` externo a partir del remitente objetivo y la clave original (`C32717EOy.A01`); el portador lleva `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 Por portador (found)

| Portador | Compuerta al enviar |
|---------|--------------|
| Reacción (`DU8.ADr`) | cifrada **solo** si el chat es un grupo (`C0DZ.A0l`) con `group_type == 3` (`C0GQ.A0A`; fijado en `CMP` desde `isDefaultSubgroup_`, es decir, un sub-grupo por defecto de comunidad, interpretación inferred) y el flag de contexto de serialización `A09` es false. En cualquier otro chat se envía el `reactionMessage` plano. `ReactionMessage.key` se pone a null antes del cifrado (la clave se mueve al `targetMessageKey` externo) |
| Voto de encuesta (`DUA.ADr`) | flag **6772** activado: ayudante compartido, siempre cifrado; desactivado: rama en línea legacy con la misma derivación y AAD (remitente objetivo = propio LID para encuestas propias, de otro modo el JID derivado de la clave objetivo del voto; modificador = propio LID). `metadata` (`pollNameHash`, `lastEditStanzaId` opcional) se estampa cuando el flag **31593** está activado |
| Respuesta de evento (`DU9.ADr`) | siempre cifrada; el `EventResponseMessage` en texto plano tiene `response`, `timestampMs`, `extraGuestCount` |
| Comentario (`F3W.ADr`) | siempre cifrado; el texto plano es el `Message` completo del comentario; el objetivo es la clave padre de `CommentMessageInfo` |
| Edición cifrada como secreto (`F3Y.C5S`) | solo cuando el mensaje tiene info de edición de tipo `E2Q` y el contexto de serialización no es reenviado/huérfano; `MESSAGE_EDIT` necesita además el flag **17811** (de otro modo `getUseCase` lanza). Para ediciones de mensaje propio dos líneas de log (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) muestran casos que se envían como ediciones planas; la condición completa (flags **37948**, **35457**) se perdió en la decompilación |

Los payloads cifrados-como-secreto anidados se rechazan en ambos lados (`nested_secret_encrypted_message`).

---

## 7. Lado receptor

### 7.1 Descifrado (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (modificador) por portador: propio LID cuando el envelope es propio; encuesta: JID del remitente (`c0df` o `B4g()`); respuesta de evento: usuario del chat en 1:1, de otro modo usuario del envelope; comentario: solo LID (`C0DZ.A0Y`: tipos 18, 19, 25), un remitente PN falla con error 0; reacción: solo el remitente del envelope si es un LID, de otro modo null.

### 7.2 Reintento de identidad LID / PN (estructura found, cola inferred)

El primer intento usa los JIDs tal como se dan. En caso de fallo el ayudante mapea ambos JIDs al otro namespace (`C0YH.A0I` LID->PN, `A0F` PN->LID) y reintenta una vez; si ambos ya eran LID o el mapeo falta, el resultado es error **51** (descifrado fallido). La cola decompilada del reintento se perdió parcialmente, así que el conjunto exacto de pares intentados es inferred. El chequeo es la autenticación GCM: un par incorrecto falla, el correcto descifra.

### 7.3 Padre faltante: huérfanos (found)

| Portador | Comportamiento cuando el padre no se encuentra o es un placeholder |
|---------|-----------------------------------------------------------|
| Reacción | el FMessage tipo **56** se almacena con los bytes crudos de `Message` (`DdA(key, 56, ts).A02`); el descifrado se posterga |
| Voto de encuesta | `C30957Dd6.A02 = Message.toByteArray()`; almacenado sin descifrar |
| Respuesta de evento | `Dd7(key, target, bytes, ts)` almacenado sin descifrar |
| Comentario | placeholder `C34671Zb` con la clave padre y fila `-1` |
| Edición cifrada como secreto | `DeD(MessageOrphan)` con tipo de huérfano **5**, razón **1** (padre ausente) o **2** (placeholder) |

Se espera un replay cuando llega el padre (los huérfanos se persisten con los bytes crudos) pero el disparador del replay no fue rastreado (inferred).

### 7.4 Validación tras el descifrado (found)

| Caso | Chequeo | Fallo |
|------|-------|---------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` debe ser `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | tipo `POLL_ADD_OPTION` y un segundo campo de stanza igual a `poll_add_option` (campo no resuelto) | `poll_add_option_stanza_invalid` (76) |
| Edición de evento | mensaje interno tipo 92, la clave resultante iguala la clave externa | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Edición de encuesta | tipo interno 66, ambos mensajes son encuestas, misma hora de cierre y flags, ediciones de opción consistentes con las opciones almacenadas, marca de tiempo no posterior a la hora de cierre | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Añadir opción de encuesta | tipo interno 137, el padre es una encuesta, la clave objetivo iguala la clave externa, no posterior a la hora de cierre | `poll_add_option_past_end_time` |
| Recepción de edición de encuesta | el AB int **24886** debe ser no-cero | error 10016 ("futureproofing") |
| Recepción de añadir opción de encuesta | el AB **25758** debe ser no-cero | error 10017 |
| Voto de encuesta | la selección debe ser válida para la encuesta (`AbstractC33199EdC.A02`); la marca de tiempo del voto no posterior a la hora de cierre de la encuesta | `poll_update_past_end_time`, `invalid poll vote selection` |
| Metadata de voto de encuesta | `pollNameHash` + `lastEditStanzaId` verificados contra la encuesta almacenada (`C32977EZa.A01`); "unstamped" cuando está ausente; el desajuste descarta el voto | `poll_update_tc_drop` |
| Forma del voto de encuesta | IV exactamente 12 (`poll_update_invalid_vote_enc_iv`), payload presente, marca de tiempo del remitente presente | error 11 |
| Respuesta de evento | clave, IV (12), payload presente; el padre debe ser un evento o un mensaje de revocación del remitente | `parent message is not event message nor sender revoke` |

---

## 8. Vinculación remitente / objetivo

| Vinculado por la clave | Efecto |
|------------------|--------|
| Id del mensaje original | un ciphertext no se puede reutilizar en otro mensaje |
| JID del remitente objetivo | no se puede atribuir a un autor original distinto |
| JID del modificador | no se puede repetir como el add-on de otro usuario |
| String de caso de uso | un ciphertext de reacción no descifra como voto, comentario o edición |
| AAD (voto de encuesta, respuesta de evento) | vincula adicionalmente `targetId` y el modificador al tag |

No vinculado: JID del chat, marca de tiempo, posición del ciphertext en el hilo, el número de add-ons previos. El `participant`/`from` del envelope es lo que el receptor usa como el modificador; está autenticado por la sesión E2E, no por el secreto. Cualquiera que tenga el secreto original (cada participante que recibió el mensaje original, en un grupo) puede derivar claves para cualquier modificador; el esquema previene el re-direccionamiento del lado relay, no la impersonación por miembros del grupo (inferido de la construcción).

---

## 9. Fallbacks de secreto faltante (found salvo que se indique)

| Situación | Remitente | Receptor |
|-----------|--------|----------|
| El original no tiene secreto | el cifrado falla (66); ruta legacy de encuesta: `invalid message_secret secretSize` | padre presente, secreto null: error **66**, registrado al reportador de errores con `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` código 0 |
| Secreto no de 32 bytes | cifrado rechazado | error **67**, código WAM 1 |
| Padre no encontrado | error de cifrado 71 | almacenado como huérfano (7.3) |
| Reacción en un chat que no es sub-grupo-por-defecto | se envía en su lugar el `reactionMessage` en texto plano (no se necesita secreto) | manejado por la rama plana |
| Edición de mensaje sin el flag 17811 | `getUseCase` lanza (`unknown message secret encrypted type`, código 0); si el remitente evita el tipo cuando el flag está apagado no está resuelto | mismo lanzamiento |
| El descifrado del add-on falla | n/a | el add-on permanece oculto/no disponible; no se encontró ningún texto de fallback visible (unknown) |
| Nuevo companion sin el original | n/a | la sincronización de historial lleva el secreto en `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | fijado en mensajes con info de edición (12.3) | le dice al receptor que no muestre un placeholder de fallo; el consumidor del flag no está resuelto |

---

## 10. Stanza `<message>`: qué añade el cliente

Los hijos salientes se construyen por contribuidores independientes (`InterfaceC35538FaZ`) que añaden al constructor de stanza `C33150EcP`.

### 10.1 Atributos (found)

| Atributo | Productor / consumidor | Valores / significado |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (del proto): `secretEncryptedMessage` con `EVENT_EDIT` -> `event`, con `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` cae a `text` / `media`; campos de reacción (plana o enc) -> `reaction`; actualización/creación de encuesta -> `poll`; `encEventResponseMessage` y evento -> `event` |
| `edit` | specs de recepción `C33474Ehg` (requiere tag de nodo `status`; su relación con el stanza `<message>` plano no está resuelta), `C23206A1f` (newsletter); acks `AbstractC33465EhX.A05` | `1`, `7`, `8` en `C33474Ehg`; `3` y `8` en la spec de newsletter; los acks lo repiten salvo que sea `0`/vacío; ver 10.2 |
| `category` | stanza, acks, recibos de reintento | `peer` selecciona la ruta de mensaje entre pares |
| `device_fanout` | `F6M` | `"false"` en reintentos uno-a-uno dirigidos |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | transporte | identidad / ciclo de vida, no contenido |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | parsers de identidad (`AbstractC33466EhY`, `C34763F6g`) | alias de PN / LID / username |

### 10.2 Valores de `edit`

| Valor | Contexto | Nivel |
|-------|---------|------|
| `1` | edición de un mensaje enviado (parseado en `C33474Ehg.A0L`) | found |
| `2` | fijar en el chat: la ruta de recepción requiere la versión de edición interna 2 (`Invalid edited version`) | mapeo al atributo inferred |
| `3` | edición de mensaje de newsletter: parseado solo en la spec de newsletter (`C23206A1f.A0G`), y `EWW.A01` fija la versión de edición 3 cuando el chat es una newsletter (tipo de JID 21, servidor `newsletter`) | found (esto resuelve el anterior "3 unknown") |
| `7` | revocación por el remitente (`C33474Ehg.A0M`) | found |
| `8` | eliminación de admin (`C33474Ehg.A0S`, spec de newsletter `A0H`) | found |
| `0` / vacío | mensaje normal; omitido de los acks | found |

La versión de edición interna (`EWW.A01`) es `1` para chats normales y `3` para newsletters; las ediciones de chat normal también fijan el flag hide de `decrypt-fail` (12.3).

### 10.3 Hijos directos (found)

| Hijo | Productor | Significado |
|-------|----------|---------|
| `enc` | capa de cifrado | ciphertext, ver sección 11 |
| `participants` / `to` | `F6E` y fanout | ciphertexts por dispositivo |
| `device-identity` | `F6B` | identidad de dispositivo firmada |
| `registration` | parser `C33474Ehg.A04` | exactamente 4 bytes |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | como máximo el AB int **20606** por stanza, habilitado por **20605** |
| `cstoken` | `F6G` | token de contacto en frío |
| `padding` | `F6H` | bytes aleatorios, longitud `retryCount × 1571`, flags **8311**, **9209** (`ta_pad` también presente) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (HMAC de 16 bytes), ver [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | sección 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | procesador de negocio `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | nodos de flag vacíos de una bitmask en el constructor: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | parser | categoría binaria opaca (status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` en envíos a JID tipo 3 (lista de difusión, inferred), flags **16656** (emitir) y **13537** (valor) |
| `verified_name` | negocio | certificado de negocio verificado |
| `unavailable`, `bypassed` | parser | nodos marcadores; el literal `unavailable` no coincide en 2.26.41.6 (basado en constante), semántica no verificada aquí |

---

## 11. Nodo `<enc>`

### 11.1 Atributos (found, `AbstractC33466EhY.A09`)

| Atributo | Valor | Condición |
|-----------|-------|-----------|
| `v` | `2` o `3` | versión del ciphertext (el parser de recepción acepta `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | mensaje Signal, mensaje prekey, sender key, `frskmsg`, bot `msmsg`, marcador en texto plano |
| `count` | conteo de reintento | omitido cuando es 0 |
| `mediatype` | ver 11.2 | clasificación de media / interactivo |
| `native_flow_name` | nombre de flow | mensajes de native-flow |
| `duration` | int >= 0 | ubicación en vivo |
| `decrypt-fail` | `hide` | mensaje marcado como ocultable (12.3) |
| `state` | `false` | envíos de `pkmsg` bajo un flag en el portador de ciphertext |
| `session_type` | `pq` | flag de portador de sesión post-cuántica |
| `bucket` | string | cuando se fija en el portador de ciphertext |

Chequeos de recepción (`C33013EaB`): dos nodos `<enc>` en un mensaje deben coincidir en conteo de reintento y versión de ciphertext; un `enc` en una newsletter se rechaza (`Received enc message for newsletters`); `decrypt-fail=hide` se honra solo cuando la categoría no es `peer` y el predicado de chat `C1ZB.A0L` es false.

### 11.2 Valores de `mediatype` aceptados por la spec (found, 37 entradas)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. Enum `native_flow_name` (8 entradas): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. Nodo `<meta>`

Todos los atributos e hijos se acumulan en `EZV` por los manejadores que `F6K` llama (por clase de mensaje `FXq.AAl`, por add-on `FZH.AAl`) y se emiten como un solo `<meta>` (`C33150EcP.A00`). Un acumulador vacío no emite nada.

### 12.1 Clasificadores de operación (found)

| Atributo | Valores | Productor |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | manejadores de encuesta |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | manejadores de evento |
| `content_type` | `add_on` para la clase de add-on `AbstractC35181aQ` (incluye reacciones; votos/respuestas inferred) en chats donde `C0DZ.A0U` es false; `status_notify` / `add_on` para notificaciones de estado | `F6K` |
| `type` | `scheduled_message` con `st` (segundos, omitido para la clase de mensaje de desprogramación) e hijo `<key rkid="...">` (bytes de clave omitidos para esa clase) | `F6K`, revelación condicional |
| `appdata` | string libre de `FZF.AVN()`; editar appdata se rechaza | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | mensaje de member-tag `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (y otros) | `AJR` |
| `message_association_type` | token de asociación, más `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` en subidas de estado | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | id/JID del padre | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; hijo `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, más strings de punto de entrada de Meta AI (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` para chats 1:1 bajo el flag **36091** (significado no resuelto) | `F6K` |
| `view_once` | `true` para tipos view-once bajo el flag **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (tipo de mensaje 108) | `F6K` |
| `share_pn` | `true` (tipo de mensaje 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | enrutamiento de bot / hilo | `F6K` |

### 12.2 Parseado al recibir (found)

Entradas de `<meta>` que el cliente lee: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (solo chats de grupo), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (segundos, almacenado en ms), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, e hijos `mention_source/to`, `mentioned_users/to`. Los metas de newsletter añaden `admin_profile`, `paid_partnership`, `ai_content` (listados del catálogo anterior; no re-leídos aquí, no verificados). `deprecated_lid_session` se confirma ausente a partir de 2.26.45.10: un grep insensible a mayúsculas/minúsculas exhaustivo en todo el árbol decodificado de 2.26.45.10 y WA Business 2.26.45.7 no encontró ninguna coincidencia exacta o cercana (`found`); se infiere que es una eliminación intencional del flag transicional de migración PN→LID, no un renombrado (`inferred`).

---

## 13. `<biz>`, `<bot>`

### 13.1 `<biz>` (found, `C34748F5r.CM3`)

```xml
<biz native_flow_name="...">                       <!-- or -->
<biz>
  <interactive type="native_flow">
    <native_flow name="..."/>
  </interactive>
  <buttons/> | <list/>
</biz>
<hsm category="..." tag="..."/>                    <!-- sibling, template classification -->
```

El receptor lee el nombre del flow (`native_flow_name` o el `name` anidado), luego clasifica: `buttons` presente, `list` presente, o native flow; con un nombre y un hermano `hsm` se convierte en una plantilla. Los fallos de validación se llaman `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: un clasificador `biz` que no coincide con el payload cifrado es un fallo de validación, no un tipo de mensaje distinto. Otros atributos de `biz` leídos en otro lugar: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, hijo `quality_control` con `decision_source`.

### 13.2 `<bot>` (found)

Saliente (`F6M`): atributos `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, hijo `tee_routing` (`tee_routing_token`, `tee_ik_id`). Entrante (`C34747F5q`): `<bot edit="full|...">` por defecto `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; sin `<meta target_id>` el mensaje no se maneja como una respuesta de bot. Detalles: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Esquemas relacionados que no son message-secret

### 14.1 Revelación condicional (mensajes programados)

`conditionalRevealMessage` (campo **120**) usa una clave de revelación aleatoria separada (`<meta type="scheduled_message" st><key rkid>`); el servidor controla la revelación. Sin HKDF a partir de `messageSecret`. Los internals del protocolo de revelación no fueron rastreados (unknown).

### 14.2 Token de reporte

`reportingTokenVersion` (campo **8**) y el `<reporting_token>` de 16 bytes usan la clave nativa del caso de uso id 5 (3.4), no HKDF de Java. Contenido del token: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Verificador de soporte de companion (found)

`CompanionSupportVerifier` (`C34757F6a`, solo en un companion, detrás de un flag): los mensajes no-`peer` se aceptan solo si el `type` está en `{text, media, reaction, poll, event}` (o `pay` con un hijo `transaction`/`pay` de remesa) y cada hijo directo está en `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. De otro modo registra `unsupported child node=` / `unsupported message type=` y el mensaje se clasifica como no soportado en el companion. Una difusión entre pares con `participants` en un companion se descarta (`received peer broadcast message on companion-mode, dropping`, nack 415/18). El nuevo hijo `cap` y `tctoken`/`cstoken` no están en la lista; dónde se manejan antes de este chequeo no está resuelto. `unavailable` y `participants` pasan por sus propias rutas.

---

## 16. Feature flags (ids tal como se leen en los call sites; nombres no resueltos)

| ID | Tipo | Controla |
|----|------|----------|
| **6772** | bool | voto de encuesta: ayudante compartido vs. cifrado en línea legacy |
| **31593** | bool | estampado de `metadata` del voto de encuesta |
| **17811** | bool | caso de uso `Message Edit` (envío y recepción) |
| **37948**, **35457** | bool | condiciones para envolver ediciones de mensaje propio |
| **24886** | int | recepción de edición de encuesta (0 = rechazada, 10016) |
| **25758** | int | recepción de añadir opción de encuesta (0 = rechazada, 10017) |
| **15791** | bool | modificador de respuesta de evento LID -> PN en chats 1:1 |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | generación de secreto por clase de chat |
| **8860** | int | versión máxima de token de reporte (generación de secreto) |
| **24741** | bool | secreto para tipo de mensaje 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | hijo `cap` y su valor |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool / int | activar `tctoken` / tope por stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, lectura de código, nada probado)

Solo hechos leídos en `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`.

| Tema | Baileys | Android |
|-------|---------|---------|
| Clave | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | idéntico (3.1) |
| Casos de uso | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, más `Message Schedule` para el enum 3 | mismos strings; el valor 3 no está definido en 2.26.41.6 |
| AAD | `id\0modifier` para encuesta y evento, vacío para edición/comentario/reacción | igual |
| Identidad | intenta candidatos PN y LID del creador y modificador, GCM autentica el par correcto | misma idea (7.2) |
| Secreto faltante | registra, emite la actualización cruda `encReactionMessage` / `pollUpdateMessage`, sin descifrar | almacenado como huérfano |
| Generación de secreto | `randomBytes(32)` para encuesta, evento y cuando falta `messageContextInfo.messageSecret` | 2.2 |
| Clave de reporte | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; el reporte se omite para reacciones, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | id nativo 5 (3.4) |
| Lado envío | no se encontró ningún remitente para `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` o `encCommentMessage` en los archivos leídos | Android envía los cuatro |

Consecuencia leída del código: Baileys puede descifrar seguimientos que recibe pero los archivos leídos no contienen cifrado para ellos. Si existe un ayudante de envío en otro lugar no fue buscado.

---

## 18. Casos de error

| Síntoma | Causa | Arreglo |
|---------|-------|-----|
| Error 11 | IV no de 12 bytes o payload vacío / campo faltante | verificar `encIv` (campo 3, o 2 para `PollEncValue`) |
| Error 51 | namespace de JID remitente/objetivo incorrecto (PN vs LID), id original incorrecto | reintentar ambos namespaces, usar el id de mensaje original (sin editar) |
| El voto para una encuesta editada falla | el id de clave debe ser el id de encuesta original, no el último id de edición | resolver la clave original |
| El comentario de un remitente PN falla | el descifrado de comentario requiere un remitente LID | usar el LID |
| Edición/añadir-opción de encuesta rechazada | flags **24886** / **25758** apagados, o el `polltype` del stanza no coincide con `secretEncType` | enviar `<meta polltype>` y tipo coincidentes |
| Mensaje ignorado en un companion | nodo hijo o `type` desconocido | mantenerse en la lista de permitidos (sección 15) |
| Mensaje `<biz>` no soportado | el clasificador no coincide con el payload | derivar el clasificador del payload |

---

## 19. Distinciones clave

| Esto | No esto |
|------|----------|
| `messageSecret` (por mensaje, aleatorio, 32 bytes) | clave de media, sender key, clave de sincronización de app-state, clave de llamada |
| Clave de caso de uso (HKDF, por objetivo/usuario/caso de uso) | el secreto mismo |
| `secretEncryptedMessage` (envuelve un `Message` completo) | `encReactionMessage` (envuelve un `ReactionMessage`) |
| AAD de `Poll Vote` / `Event Response` = id + NUL + modificador | edición/comentario/reacción con AAD vacío |
| `targetMessageKey` en el portador externo | `ReactionMessage.key` dentro del texto plano (limpiado al enviar) |
| `meta polltype` / `event_type` (clasificador) | el payload cifrado (contenido) |
| atributo `edit` del stanza | `secretEncType` (caso de uso de cifrado) |
| `decrypt-fail="hide"` en `<enc>` | recibo de reintento / nodo `retry` |

---

## 20. Flujo completo (voto de encuesta, 1:1 o grupo)

```
[Creator]                                            [Server]                      [Voter]
   │ poll creation Message                              │                             │
   │ messageContextInfo.messageSecret = random 32       │                             │
   │ store message_secret[row]                          │                             │
   │ <message type="poll"><meta polltype="creation">────▶────────────────────────────▶ stores secret
   │                                                    │                             │
   │                                                    │      select options (hashes)│
   │                                                    │      secret = store[poll]   │
   │                                                    │      key = HKDF(secret,     │
   │                                                    │        pollId‖creator‖voter │
   │                                                    │        ‖"Poll Vote")        │
   │                                                    │      iv = random 12         │
   │                                                    │      ct = GCM(key, iv,      │
   │                                                    │        PollVoteMessage,     │
   │                                                    │        aad = pollId\0voter) │
   │              <message type="poll"><meta polltype="vote">                         │
   │◀────────────────────────────────────────────────────◀ pollUpdateMessage{key,vote{ct,iv},metadata,ts}
   │ parent found? no -> orphan, keep raw bytes         │                             │
   │ validate end time, enc iv = 12                     │                             │
   │ key = HKDF(secret, pollId‖creator‖voter‖"Poll Vote")                              │
   │ GCM-decrypt, fail -> retry PN/LID pair, else 51    │                             │
   │ check option hashes ⊂ poll options, stamp match    │                             │
   │ apply vote                                         │                             │
```

---

## 21. Incógnitas

| Ítem | Estado |
|------|-------|
| Predicados exactos para `EZN.A01`, `C35201aS.A00`, flags 3142-3146 | compuerta por clase de chat vista, el conjunto visible al usuario no resuelto |
| Tabla nativa de id de caso de uso (nombres a ids distintos de 5 = Report Token) | no leído |
| Posición del tag GCM y tamaño de clave AES | inferido de constantes y de Baileys |
| Condición completa para enviar ediciones propias de `MESSAGE_EDIT` envueltas vs. planas (flags 37948, 35457) | el decompilador perdió el flujo de control |
| Significado de `acp="2"`, flag de serialización `A09`, segundo campo de stanza de añadir-opción-de-encuesta | no resuelto |
| Consumidor de `decrypt-fail="hide"` en el envelope parseado | flag llevado al envelope, efecto no rastreado |
| Resultado visible al usuario de un add-on permanentemente no descifrable | no se encontró ningún texto de fallback |
| `unavailable`, `bypassed` | no re-verificado en 2.26.41.6 |
| `deprecated_lid_session` | confirmado ausente a partir de 2.26.45.10 (grep exhaustivo, tanto en los árboles de WhatsApp como de WA Business); eliminación vs. renombrado es `inferred`, no probado |
