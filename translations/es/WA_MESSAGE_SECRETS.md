<!-- src-sha1: 7a4b50013c0f196c95c57808469516becf9a34b7 -->
# WhatsApp Message Secrets — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** `messageSecret` por mensaje (generación, `MessageContextInfo`, almacén local, history sync), derivación de claves por caso de uso (HKDF), IV / AAD de AES-GCM, add-ons cifrados (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, ediciones `secretEncryptedMessage`), vinculación de identidad de remitente / destino y reintento LID / PN, huérfanos y fallbacks por secreto ausente, extensiones del stanza `<message>` (atributos, atributos de `<enc>`, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, verificación de soporte en companion), feature flags, comparación con Baileys

---

## 1. Qué es (técnicamente)

Todo mensaje que pueda recibir más adelante un seguimiento cifrado lleva un secreto aleatorio de 32 bytes dentro de su propio payload cifrado de extremo a extremo (`MessageContextInfo.messageSecret`). Un seguimiento (reacción, voto de encuesta, respuesta a evento, comentario, edición) se cifra con una clave derivada de ese secreto, del id del mensaje original, del remitente original y del modificador. El servidor retransmite el seguimiento como un mensaje E2E ordinario, pero no puede leerlo ni moverlo a otro destino, usuario o caso de uso sin romper la autenticación GCM. Todas las afirmaciones provienen del análisis estático del APK decompilado; no se capturó nada en la red. Niveles: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres ofuscados se resolvieron de nuevo en 2.26.41.6 a partir de strings estables (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, strings de casos de uso, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

La misma versión define también las extensiones del stanza `<message>` (sección 10 en adelante): atributos y nodos hijos que clasifican y enrutan un mensaje pero no transportan su contenido. Se agrupan aquí porque `<meta polltype>` / `<meta event_type>` deben coincidir con el payload cifrado con secreto (7.4).

| Entidad | Nombre en 2.26.41.6 | Función |
|---------|----------------|------|
| Helper criptográfico (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` cifrar, `A04` descifrar (reintento de identidad), `A02` resolver la clave de destino |
| Portadores de parámetros de cifrado / descifrado | `C32833ETl` / `C32854EUg` | datos, remitente, clave de destino, caso de uso / IV, payload, claves, remitente |
| Derivación de clave | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, salt cero |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | nativo, tag de 16 bytes |
| Proveedores de AAD | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (ninguno) | datos adicionales |
| Generador del secreto | `AbstractC33322EfC.A01` | `SecureRandom`, 32 bytes |
| Almacén de secretos (`MessageSecretStore`) / extra en memoria | `C35311ad` (tabla `message_secret`) / `C35171aP` en el mensaje `C13G` | persistir y transportar |
| Mapeador de clave original (`ReferentialKeyUtil`) | `C43661qB.A03` | clave del mensaje original sin editar |
| Handlers de reacciones | `DU8` (envío), rama `F2P` (recepción) | `reactionMessage` / `encReactionMessage` |
| Voto de encuesta / respuesta a evento / comentario | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Ediciones cifradas con secreto (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Creación de encuesta / evento (secreto tomado al recibir) | `F2N` / `F2M` | lee `messageSecret` hacia el FMessage |
| Proto: contexto / mensaje / clave | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Selector del `type` del stanza | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Contribuyentes del stanza saliente | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), flags `F68`, `F69` cap, `F6H` padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | construyen los hijos de `<message>` |
| Acumulador de `<meta>` | `EZV` (atributos `A01`, hijos `A00`) | un nodo `<meta>` |
| Constructor de atributos de `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Verificación de soporte en companion | `C34757F6a` + `AbstractC32927EXc` | lista permitida de tipos e hijos |
| Parsers de especificación entrante | `C33474Ehg` (status / regular), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | extracción de atributos e hijos |
| Evento WAM de error | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. El secreto por mensaje

### 2.1 Dónde reside (found)

`MessageContextInfo` (`C30624DTs`) es el campo **35** de `Message` (`C30628DTw`). Campos relevantes aquí:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | pista de lista de dispositivos (no relacionada con el secreto) |
| `messageSecret` | **3** | bytes (32) | secreto por mensaje |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | duración del add-on (pin: debe ser 0 para desfijar) |
| `botMessageSecret` | **6** | bytes (32) | variante bot del secreto |
| `botMetadata` | **7** | message | contexto del bot |
| `reportingTokenVersion` | **8** | uint32 | versión del reporting token de este mensaje |
| `messageAddOnExpiryType` | **9** | enum | expiración del add-on |
| `messageAssociation` | **10** | message | asociación |

El portador de history sync `WebMessageInfo` (`C30626DTu`) tiene su propio campo `messageSecret` **49** (found), usado cuando los mensajes se exportan a un nuevo companion (sección 2.4).

### 2.2 Generación (found, condiciones en parte inferred)

El secreto es `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). Se adjunta antes de serializar el mensaje:

| Lugar | Condición |
|-------|-----------|
| `C33166Ecf.A06` (preparar envío) | el mensaje no tiene secreto y se cumple al menos una de: clase de encuesta `C13J`; `EZN.A01(msg)` (clase bot / add-on, con flags de tipo de chat **2200**, **11104**, **19303**); compuertas por clase de chat: grupo con flag **3143**, lista de difusión con **3144**, status con **3145**, compuerta de clase **3146**; `C35201aS.A00` (flag **3142**, chat propio / bot); mensaje de evento `C213509Ao` |
| `AJ0` (procesador de envío) | la versión del reporting token `C35241aW.A05()` (AB int **8860**, limitada por `AbstractC35301ac.A00`) es distinta de cero y la clase del mensaje no está excluida por `C35241aW.A02` (status, newsletter, clases de add-on seleccionadas) |
| `C72h`, `C34455Exe`, `EPA` | los objetos de status (`AbstractC34478Ey1.A0R`) reciben un secreto nuevo al crearse |
| `C33437Eh4` | mensaje bot "request welcome", solo cuando su llamador lo pide |
| `C9mW` | mensaje de tipo 117, flag **24741**, cuando no hay ninguno |

Los predicados detrás de `EZN.A01`, `C35201aS.A00` y las compuertas `3142`..`3146` no se resolvieron por completo; la lista anterior indica qué comprueba el código, no qué mensajes visibles para el usuario califican. Los mensajes sin secreto no pueden recibir add-ons cifrados desde este cliente (sección 9).

### 2.3 Almacenamiento local (found)

`C35311ad` escribe `message_secret(message_row_id, message_secret)` con semántica de reemplazo (`MessageSecretStore/insertMessageSecret`) y lee la última fila para un `message_row_id`. El FMessage lo conserva como extra `C35171aP` (`A0L` set, `A0c` get, `A0Q` = no vacío). Dos procesadores en `AbstractC17240jU` (`C35161aO` y uno anónimo) lo escriben cuando el extra está sucio y el chat califica.

### 2.4 Validación en recepción y transferencia (found)

| Paso | Comportamiento |
|------|-----------|
| Validador de proto `C33475Ehh.A0V` | `message_secret` debe tener exactamente **32** bytes, código de error **67**; la variante bot (`bot_message_secret`, grupo `whatsapp_security`) se valida igual |
| Creación de encuesta `F2N` | copia `messageSecret_` al nuevo FMessage (`A0L`) |
| Respuestas a preguntas de status `C34838F9e` | misma copia para `statusQuestionAnswerMessage` |
| Exportación de history sync `C34388EwZ.A00` | escribe el secreto almacenado en `WebMessageInfo.messageSecret` (49) |
| Importación de history sync `C34388EwZ.C59` | lo copia de vuelta (`A0L`) |
| Comentarios `C34387EwY` | reconstruye un `MessageContextInfo` a partir de `WebMessageInfo.messageSecret` para el hilo de comentarios |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) registra `message_secret_error` **0** = ausente (se mapea al código de error 66) o **1** = longitud inválida (67) para mensajes que requieren un secreto (`AbstractC33322EfC.A00`: tiene el flag y no es de la clase `C35281aa`).

---

## 3. Derivación de claves por caso de uso

### 3.1 Fórmula (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract con un salt cero de 32 bytes (`AbstractC38971i1.A00(ikm, salt)`), seguido del bucle expand de RFC 5869. Fundamentos de HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) sección 5.1. La salida de 32 bytes se usa como clave AES-256 (inferred por la longitud; la llamada nativa recibe la clave como `byte[]`).

Entradas:

| Entrada | Fuente | Notas |
|-------|--------|-------|
| `originalMessageId` | id de clave del destino tras `ReferentialKeyUtil` (`C43661qB.A03`) al cifrar; id de clave del proto `targetMessageKey` al descifrar | para un destino editado es el id del mensaje **original** (log `getOriginalKey`) |
| `targetSender` | autor del mensaje original: remitente almacenado (`C12300aw.A01`) | `UserJid`, por tanto sin sufijo de dispositivo (a nivel de tipo; la forma en string `user@server` es inferred) |
| `modifier` | autor del add-on: JID de la cuenta propia (`C09A.A0G`, un LID, devuelto por `CUC()` / `Ash()`) al enviar, el JID del remitente del envelope al recibir | |
| `useCase` | string de 3.2 | sin separador entre los cuatro componentes |

El JID propio es un JID de cuenta LID (`C14080dr`, servidor `lid`, comprobación "Invalid LID"). Tanto `AnonymousClass091.Ash()` como `CUC()` devuelven el mismo campo.

### 3.2 Strings de caso de uso (found)

| Caso de uso | Portador | AAD | Literal Java en 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | ninguno | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | ninguno | `F3W` |
| `Event Edit` | `secretEncryptedMessage` tipo 1 | ninguno | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` tipo 2 | ninguno | `F3Y.A00`, solo con el flag **17811** |
| `Poll Edit` | `secretEncryptedMessage` tipo 4 | ninguno | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` tipo 5 | ninguno | `F3Y.A00` |
| `WASA` | ruta bot (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | dos etapas, 3.3 |
| `Report Token` | clave del reporting token | nativo | sin literal Java; presente en `libwhatsapp.so`, derivado de forma nativa (3.4) |

### 3.3 Variante bot / WASA (found, detalles inferred)

Para el caso de uso `WASA` la derivación tiene dos etapas y no hay string de caso de uso en la segunda:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` es el modificador y `jidB` el JID remoto (del chat), que debe ser un `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`); el id es la clave del mensaje actual cuando existe, si no la clave de destino (lambda de `C33285Eeb.A03`). Contraparte nativa: `WcmBotMessageSecretAPICreateWithMessageSecret`. Contexto de Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Clave del reporting token (found / inferred)

`C33364Efs.A06` y `C33421Ego` llaman a `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: el objeto nativo deriva la clave para el id de caso de uso **5**; el lado Java solo pasa los raw strings de los JID. El string `Report Token` existe en la librería nativa; el mapeo del id 5 a ese string es inferred. Token y subida: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. Estructura AEAD

| Elemento | Valor | Nivel |
|------|-------|------|
| Cifrado | AES-GCM, nativo (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; descifrado `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Clave | 32 bytes de la sección 3 | found |
| IV | **12** bytes aleatorios por cifrado (`SecureRandom`); el descifrado rechaza cualquier otro tamaño | found |
| Tag | 16 bytes; la constante 16 se pasa en ambas llamadas; la posición (añadido al ciphertext) se infiere del descifrado de Baileys | found / inferred |
| AAD | según el caso de uso (3.2); `null` cuando el proveedor es `C34631F1e` | found |
| Plaintext | el proto interno serializado (tabla 5) | found |
| Salida | tripleta `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| Resultado vacío | log `encryption values are invalid`, error `Encryption using iJniBridge failed` | found |

Reintento de voto de encuesta: si el voto ya contiene IV y payload (`C30957Dd6.A03` / `A04`), se reenvía el mismo ciphertext en lugar de volver a cifrar (found, rama legacy de `DUA`).

---

## 5. Portadores y plaintexts

| Portador (campo en `Message`) | Clase | Campos | Plaintext descifrado |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (borrado antes de cifrar), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (bytes repetidos, hashes de opciones) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown, 1 going, 2 not going, 3 maybe), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `Message` completo (el cuerpo del comentario); la forma en plaintext es `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | `Message` completo |
| `reactionMessage` **46** | `DSH` | forma en plaintext | reacción en claro |
| `conditionalRevealMessage` **120** | n/a | no es el esquema de message-secret (sección 14.1) | mensajes programados |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. El valor 3 no existe en este build (`forNumber(3)` devuelve null, se trata como unknown y se rechaza).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Lado emisor

### 6.1 Ruta común (found, `C33285Eeb.A03`)

1. Resolver el FMessage de destino por clave (`target message not found. Cannot proceed further` -> error 71).
2. Leer su secreto de `message_secret`; null o longitud != 32 -> `message secret missing or invalid` (66).
3. Clave original mediante `C43661qB.A03` (null -> error 0). Remitente de destino mediante `C12300aw.A01`.
4. En un chat 1:1 (`C0DZ.A0k(chat)`) el remitente de destino se convierte al namespace del modificador: modificador LID y destino PN -> destino mapeado de PN a LID; modificador PN y destino LID -> destino mapeado de LID a PN. En grupos no hay conversión.
5. Solo Event Response: flag **15791**, chat 1:1 y un modificador de tipo cuenta -> modificador convertido a PN.
6. IV aleatorio de 12 bytes, derivar la clave (3.1), AES-GCM con el AAD del caso de uso.
7. Construir el `MessageKey` externo a partir del remitente de destino y la clave original (`C32717EOy.A01`); el portador contiene `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 Por portador (found)

| Portador | Compuerta al enviar |
|---------|--------------|
| Reacción (`DU8.ADr`) | se cifra **solo** si el chat es un grupo (`C0DZ.A0l`) con `group_type == 3` (`C0GQ.A0A`; establecido en `CMP` a partir de `isDefaultSubgroup_`, es decir, un subgrupo predeterminado de comunidad, interpretación inferred) y el flag de contexto de serialización `A09` es false. En cualquier otro chat se envía el `reactionMessage` en claro. `ReactionMessage.key` se anula antes de cifrar (la clave pasa al `targetMessageKey` externo) |
| Voto de encuesta (`DUA.ADr`) | flag **6772** activado: helper compartido, siempre cifrado; desactivado: rama inline legacy con la misma derivación y AAD (remitente de destino = LID propio para encuestas propias, si no el JID derivado de la clave de destino del voto; modificador = LID propio). `metadata` (`pollNameHash`, `lastEditStanzaId` opcional) se estampa cuando el flag **31593** está activado |
| Respuesta a evento (`DU9.ADr`) | siempre cifrada; el `EventResponseMessage` en plaintext tiene `response`, `timestampMs`, `extraGuestCount` |
| Comentario (`F3W.ADr`) | siempre cifrado; el plaintext es el `Message` completo del comentario; el destino es la clave padre de `CommentMessageInfo` |
| Edición cifrada con secreto (`F3Y.C5S`) | solo cuando el mensaje tiene información de edición de tipo `E2Q` y el contexto de serialización no es forwarded / orphan; `MESSAGE_EDIT` además necesita el flag **17811** (si no, `getUseCase` lanza excepción). Para ediciones de mensajes propios, dos líneas de log (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) muestran casos que se envían como ediciones en claro; la condición completa (flags **37948**, **35457**) se perdió en la decompilación |

Los payloads anidados cifrados con secreto se rechazan en ambos lados (`nested_secret_encrypted_message`).

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

`senderUserJid` (modificador) por portador: LID propio cuando el envelope es mío; encuesta: JID del remitente (`c0df` o `B4g()`); respuesta a evento: usuario del chat en 1:1, si no usuario del envelope; comentario: solo LID (`C0DZ.A0Y`: tipos 18, 19, 25), un remitente PN falla con el error 0; reacción: remitente del envelope solo si es un LID, en otro caso null.

### 7.2 Reintento de identidad LID / PN (found la estructura, cola inferred)

El primer intento usa los JID tal como llegan. Si falla, el helper mapea ambos JID al otro namespace (`C0YH.A0I` LID->PN, `A0F` PN->LID) y reintenta una vez; si ambos ya eran LID o falta el mapeo, el resultado es el error **51** (descifrado fallido). La cola decompilada del reintento se perdió en parte, por lo que el conjunto exacto de pares intentados es inferred. La comprobación es la autenticación GCM: un par equivocado falla, el correcto descifra.

### 7.3 Padre ausente: huérfanos (found)

| Portador | Comportamiento cuando el padre no se encuentra o es un placeholder |
|---------|-----------------------------------------------------------|
| Reacción | se almacena un FMessage de tipo **56** con los bytes crudos de `Message` (`DdA(key, 56, ts).A02`); el descifrado se aplaza |
| Voto de encuesta | `C30957Dd6.A02 = Message.toByteArray()`; se almacena sin descifrar |
| Respuesta a evento | `Dd7(key, target, bytes, ts)` se almacena sin descifrar |
| Comentario | placeholder `C34671Zb` con la clave padre y la fila `-1` |
| Edición cifrada con secreto | `DeD(MessageOrphan)` con tipo de huérfano **5**, motivo **1** (padre ausente) o **2** (placeholder) |

Se espera una repetición (replay) cuando llegue el padre (los huérfanos se persisten con los bytes crudos), pero no se rastreó el disparador del replay (inferred).

### 7.4 Validación tras descifrar (found)

| Caso | Comprobación | Fallo |
|------|-------|---------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` debe ser `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | tipo `POLL_ADD_OPTION` y un segundo campo del stanza igual a `poll_add_option` (campo sin resolver) | `poll_add_option_stanza_invalid` (76) |
| Edición de evento | mensaje interno de tipo 92, la clave resultante coincide con la clave externa | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Edición de encuesta | tipo interno 66, ambos mensajes son encuestas, mismo fin y flags, ediciones de opciones consistentes con las opciones almacenadas, timestamp no posterior al fin | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Añadir opción a encuesta | tipo interno 137, el padre es una encuesta, la clave de destino coincide con la clave externa, no posterior al fin | `poll_add_option_past_end_time` |
| Recepción de edición de encuesta | el AB int **24886** debe ser distinto de cero | error 10016 ("futureproofing") |
| Recepción de añadir opción a encuesta | AB **25758** debe ser distinto de cero | error 10017 |
| Voto de encuesta | la selección debe ser válida para la encuesta (`AbstractC33199EdC.A02`); el timestamp del voto no posterior al fin de la encuesta | `poll_update_past_end_time`, `invalid poll vote selection` |
| Metadata del voto | `pollNameHash` + `lastEditStanzaId` comprobados contra la encuesta almacenada (`C32977EZa.A01`); "unstamped" cuando falta; una discrepancia descarta el voto | `poll_update_tc_drop` |
| Forma del voto | IV exactamente 12 (`poll_update_invalid_vote_enc_iv`), payload presente, timestamp del remitente presente | error 11 |
| Respuesta a evento | clave, IV (12), payload presentes; el padre debe ser un evento o un mensaje de revoke del remitente | `parent message is not event message nor sender revoke` |

---

## 8. Vinculación remitente / destino

| Vinculado por la clave | Efecto |
|------------------|--------|
| Id del mensaje original | un ciphertext no puede reutilizarse en otro mensaje |
| JID del remitente de destino | no puede atribuirse a un autor original distinto |
| JID del modificador | no puede reproducirse como add-on de otro usuario |
| String del caso de uso | un ciphertext de reacción no se descifra como voto, comentario o edición |
| AAD (voto de encuesta, respuesta a evento) | vincula además `targetId` y el modificador al tag |

No vinculados: JID del chat, timestamp, posición del ciphertext en el hilo, número de add-ons previos. El `participant` / `from` del envelope es lo que el receptor usa como modificador; está autenticado por la sesión E2E, no por el secreto. Cualquiera que posea el secreto original (todo participante que recibió el mensaje original, en un grupo) puede derivar claves para cualquier modificador; el esquema impide el reenvío a otro destino por parte del relay, no la suplantación por parte de miembros del grupo (inferred a partir de la construcción).

---

## 9. Fallbacks por secreto ausente (found salvo indicación)

| Situación | Emisor | Receptor |
|-----------|--------|----------|
| El original no tiene secreto | el cifrado falla (66); ruta legacy de encuesta: `invalid message_secret secretSize` | padre presente, secreto null: error **66**, registrado en el error reporter con `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` código 0 |
| El secreto no tiene 32 bytes | cifrado rechazado | error **67**, WAM código 1 |
| Padre no encontrado | error de cifrado 71 | almacenado como huérfano (7.3) |
| Reacción en un chat que no es subgrupo predeterminado | se envía en su lugar el `reactionMessage` en claro (no hace falta secreto) | gestionado por la rama en claro |
| Edición de mensaje sin el flag 17811 | `getUseCase` lanza excepción (`unknown message secret encrypted type`, código 0); si el emisor evita el tipo cuando el flag está desactivado no está resuelto | misma excepción |
| Falla el descifrado del add-on | n/a | el add-on queda oculto / no disponible; no se encontró texto de fallback visible (unknown) |
| Nuevo companion sin el original | n/a | history sync transporta el secreto en `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | se establece en mensajes con información de edición (12.3) | indica al receptor que no muestre un placeholder de fallo; consumidor del flag sin resolver |

---

## 10. Stanza `<message>`: lo que añade el cliente

Los hijos salientes los construyen contribuyentes independientes (`InterfaceC35538FaZ`) que se añaden al constructor del stanza `C33150EcP`.

### 10.1 Atributos (found)

| Atributo | Productor / consumidor | Valores / significado |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (a partir del proto): `secretEncryptedMessage` con `EVENT_EDIT` -> `event`, con `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` cae a `text` / `media`; campos de reacción (en claro o enc) -> `reaction`; actualización / creación de encuesta -> `poll`; `encEventResponseMessage` y evento -> `event` |
| `edit` | specs de recepción `C33474Ehg` (requiere el tag de nodo `status`; su relación con el stanza `<message>` simple no está resuelta), `C23206A1f` (newsletter); acks `AbstractC33465EhX.A05` | `1`, `7`, `8` en `C33474Ehg`; `3` y `8` en la spec de newsletter; los acks lo repiten salvo `0` / vacío; ver 10.2 |
| `category` | stanza, acks, retry receipts | `peer` selecciona la ruta de mensajes peer |
| `device_fanout` | `F6M` | `"false"` en reintentos dirigidos uno a uno |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | transporte | identidad / ciclo de vida, no contenido |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | parsers de identidad (`AbstractC33466EhY`, `C34763F6g`) | alias PN / LID / username |

### 10.2 Valores de `edit`

| Valor | Contexto | Nivel |
|-------|---------|------|
| `1` | edición de un mensaje enviado (parseado en `C33474Ehg.A0L`) | found |
| `2` | pin en el chat: la ruta de recepción exige la versión de edición interna 2 (`Invalid edited version`) | mapeo al atributo inferred |
| `3` | edición de mensaje de newsletter: parseado solo en la spec de newsletter (`C23206A1f.A0G`), y `EWW.A01` establece la versión de edición 3 cuando el chat es un newsletter (tipo de JID 21, servidor `newsletter`) | found (esto resuelve el "unknown 3" anterior) |
| `7` | revoke por el remitente (`C33474Ehg.A0M`) | found |
| `8` | borrado por admin (`C33474Ehg.A0S`, spec de newsletter `A0H`) | found |
| `0` / vacío | mensaje normal; se omite en los acks | found |

La versión de edición interna (`EWW.A01`) es `1` para chats normales y `3` para newsletters; las ediciones en chats normales también establecen el flag de ocultar `decrypt-fail` (12.3).

### 10.3 Hijos directos (found)

| Hijo | Productor | Significado |
|-------|----------|---------|
| `enc` | capa de cifrado | ciphertext, ver sección 11 |
| `participants` / `to` | `F6E` y fanout | ciphertexts por dispositivo |
| `device-identity` | `F6B` | identidad de dispositivo firmada |
| `registration` | parser `C33474Ehg.A04` | exactamente 4 bytes |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | como máximo AB int **20606** por stanza, habilitado por **20605** |
| `cstoken` | `F6G` | token de contacto frío |
| `padding` | `F6H` | bytes aleatorios, de longitud `retryCount × 1571`, flags **8311**, **9209** (`ta_pad` también presente) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (HMAC de 16 bytes), ver [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | sección 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | procesador de negocio `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | nodos flag vacíos a partir de un bitmask en el constructor: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | parser | categoría binaria opaca (status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` en envíos a JID de tipo 3 (lista de difusión, inferred), flags **16656** (emitir) y **13537** (valor) |
| `verified_name` | negocio | certificado de negocio verificado |
| `unavailable`, `bypassed` | parser | nodos marcadores; el literal `unavailable` no coincidió en 2.26.41.6 (basado en constantes), semántica no verificada aquí |

---

## 11. Nodo `<enc>`

### 11.1 Atributos (found, `AbstractC33466EhY.A09`)

| Atributo | Valor | Condición |
|-----------|-------|-----------|
| `v` | `2` o `3` | versión del ciphertext (el parser de recepción acepta `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | mensaje Signal, mensaje prekey, sender key, `frskmsg`, `msmsg` de bot, marcador de plaintext |
| `count` | contador de reintentos | se omite cuando es 0 |
| `mediatype` | ver 11.2 | clasificación de media / interactivo |
| `native_flow_name` | nombre del flow | mensajes native-flow |
| `duration` | int >= 0 | ubicación en vivo |
| `decrypt-fail` | `hide` | mensaje marcado como ocultable (12.3) |
| `state` | `false` | envíos `pkmsg` bajo un flag en el portador del ciphertext |
| `session_type` | `pq` | flag del portador de sesión post-cuántica |
| `bucket` | string | cuando se establece en el portador del ciphertext |

Comprobaciones en recepción (`C33013EaB`): dos nodos `<enc>` en un mismo mensaje deben coincidir en contador de reintentos y versión del ciphertext; un `enc` en un newsletter se rechaza (`Received enc message for newsletters`); `decrypt-fail=hide` solo se respeta cuando la categoría no es `peer` y el predicado de chat `C1ZB.A0L` es false.

### 11.2 Valores de `mediatype` aceptados por la spec (found, 37 entradas)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. Enum de `native_flow_name` (8 entradas): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. Nodo `<meta>`

Todos los atributos e hijos se acumulan en `EZV` mediante los handlers que llama `F6K` (por clase de mensaje `FXq.AAl`, por add-on `FZH.AAl`) y se emiten como un único `<meta>` (`C33150EcP.A00`). Un acumulador vacío no emite nada.

### 12.1 Clasificadores de operación (found)

| Atributo | Valores | Productor |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | handlers de encuesta |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | handlers de evento |
| `content_type` | `add_on` para la clase de add-on `AbstractC35181aQ` (incluye reacciones; votos / respuestas inferred) en chats donde `C0DZ.A0U` es false; `status_notify` / `add_on` para notificaciones de status | `F6K` |
| `type` | `scheduled_message` con `st` (segundos, omitido para la clase de mensaje de cancelar programación) e hijo `<key rkid="...">` (bytes de la clave omitidos para esa clase) | `F6K`, conditional reveal |
| `appdata` | string libre de `FZF.AVN()`; editar appdata se rechaza | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | mensaje de member-tag `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (y otros) | `AJR` |
| `message_association_type` | token de asociación, más `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` en subidas de status | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | id / JID del padre | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; hijo `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, más strings de puntos de entrada de Meta AI (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` para chats 1:1 bajo el flag **36091** (significado sin resolver) | `F6K` |
| `view_once` | `true` para tipos view-once bajo el flag **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (mensaje de tipo 108) | `F6K` |
| `share_pn` | `true` (mensaje de tipo 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | enrutamiento de bot / hilo | `F6K` |

### 12.2 Parseado en recepción (found)

Entradas de `<meta>` que lee el cliente: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (solo chats de grupo), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (segundos, almacenado en ms), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, y los hijos `mention_source/to`, `mentioned_users/to`. Los meta de newsletter añaden `admin_profile`, `paid_partnership`, `ai_content` (listados del catálogo anterior; no releídos aquí, unverified). `deprecated_lid_session` no se encontró en 2.26.41.6.

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

El receptor lee el nombre del flow (`native_flow_name` o el `name` anidado) y luego clasifica: `buttons` presente, `list` presente, o native flow; con un nombre y un hermano `hsm` pasa a ser una plantilla. Los fallos de validación se llaman `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: un clasificador `biz` que no coincide con el payload cifrado es un fallo de validación, no un tipo de mensaje distinto. Otros atributos de `biz` leídos en otros lugares: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, hijo `quality_control` con `decision_source`.

### 13.2 `<bot>` (found)

Saliente (`F6M`): atributos `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, hijo `tee_routing` (`tee_routing_token`, `tee_ik_id`). Entrante (`C34747F5q`): `<bot edit="full|...">` por defecto `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; sin `<meta target_id>` el mensaje no se trata como respuesta de bot. Detalles: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Esquemas relacionados que no son message-secret

### 14.1 Conditional reveal (mensajes programados)

`conditionalRevealMessage` (campo **120**) usa una clave de revelado aleatoria independiente (`<meta type="scheduled_message" st><key rkid>`); el servidor controla la revelación. Sin HKDF a partir de `messageSecret`. Los internos del protocolo de revelado no se rastrearon (unknown).

### 14.2 Reporting token

`reportingTokenVersion` (campo **8**) y el `<reporting_token>` de 16 bytes usan la clave nativa del id de caso de uso 5 (3.4), no el HKDF de Java. Contenido del token: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Verificador de soporte en companion (found)

`CompanionSupportVerifier` (`C34757F6a`, solo en un companion, tras un flag): los mensajes que no son `peer` se aceptan solo si el `type` está en `{text, media, reaction, poll, event}` (o `pay` con un hijo `transaction` / `pay` de remesa) y cada hijo directo está en `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. En caso contrario registra `unsupported child node=` / `unsupported message type=` y el mensaje se clasifica como no soportado en el companion. Un peer broadcast con `participants` en un companion se descarta (`received peer broadcast message on companion-mode, dropping`, nack 415 / 18). El nuevo hijo `cap` y `tctoken` / `cstoken` no están en la lista; dónde se gestionan antes de esta comprobación no está resuelto. `unavailable` y `participants` pasan por sus propias rutas.

---

## 16. Feature flags (ids tal como se leen en los call sites; nombres sin resolver)

| ID | Tipo | Controla |
|----|------|----------|
| **6772** | bool | voto de encuesta: helper compartido vs cifrado inline legacy |
| **31593** | bool | estampado de `metadata` del voto de encuesta |
| **17811** | bool | caso de uso `Message Edit` (envío y recepción) |
| **37948**, **35457** | bool | condiciones para envolver ediciones de mensajes propios |
| **24886** | int | recepción de edición de encuesta (0 = rechazada, 10016) |
| **25758** | int | recepción de añadir opción a encuesta (0 = rechazada, 10017) |
| **15791** | bool | modificador de respuesta a evento LID -> PN en chats 1:1 |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | generación del secreto por clase de chat |
| **8860** | int | versión máxima del reporting token (generación del secreto) |
| **24741** | bool | secreto para mensajes de tipo 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | hijo `cap` y su valor |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool / int | habilitación de `tctoken` / límite por stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, código fuente leído, nada probado)

Solo hechos leídos en `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`.

| Tema | Baileys | Android |
|-------|---------|---------|
| Clave | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | idéntico (3.1) |
| Casos de uso | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, más `Message Schedule` para el enum 3 | mismos strings; el valor 3 no está definido en 2.26.41.6 |
| AAD | `id\0modifier` para encuesta y evento, vacío para edición / comentario / reacción | igual |
| Identidad | prueba candidatos PN y LID de creator y modifier, GCM autentica el par correcto | misma idea (7.2) |
| Secreto ausente | registra, emite la actualización cruda `encReactionMessage` / `pollUpdateMessage`, sin descifrar | almacenado como huérfano |
| Generación del secreto | `randomBytes(32)` para encuesta, evento y cuando falta `messageContextInfo.messageSecret` | 2.2 |
| Clave de reporting | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; reporting omitido para reacciones, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | id nativo 5 (3.4) |
| Lado de envío | no se encontró emisor para `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` ni `encCommentMessage` en los archivos leídos | Android envía los cuatro |

Consecuencia leída del código: Baileys puede descifrar los seguimientos que recibe, pero los archivos leídos no contienen cifrado para ellos. No se buscó si existe un helper de envío en otra parte.

---

## 18. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| Error 11 | IV que no es de 12 bytes o payload vacío / campo ausente | revisar `encIv` (campo 3, o 2 para `PollEncValue`) |
| Error 51 | namespace de JID de remitente / destino incorrecto (PN vs LID), id original incorrecto | reintentar ambos namespaces, usar el id del mensaje original (sin editar) |
| Falla el voto de una encuesta editada | el id de clave debe ser el id de la encuesta original, no el de la última edición | resolver la clave original |
| Falla un comentario de un remitente PN | el descifrado de comentarios requiere un remitente LID | usar el LID |
| Edición de encuesta / añadir opción rechazada | flags **24886** / **25758** desactivados, o el `polltype` del stanza no coincide con `secretEncType` | enviar `<meta polltype>` y tipo coincidentes |
| Mensaje ignorado en un companion | nodo hijo o `type` desconocido | ceñirse a la lista permitida (sección 15) |
| Mensaje `<biz>` no soportado | el clasificador no coincide con el payload | derivar el clasificador del payload |

---

## 19. Distinciones clave

| Esto | No esto |
|------|----------|
| `messageSecret` (por mensaje, aleatorio, 32 bytes) | media key, sender key, app-state sync key, call key |
| Clave de caso de uso (HKDF, por destino / usuario / caso de uso) | el secreto en sí |
| `secretEncryptedMessage` (envuelve un `Message` completo) | `encReactionMessage` (envuelve un `ReactionMessage`) |
| AAD de `Poll Vote` / `Event Response` = id + NUL + modifier | edición / comentario / reacción con AAD vacío |
| `targetMessageKey` en el portador externo | `ReactionMessage.key` dentro del plaintext (borrado al enviar) |
| `meta polltype` / `event_type` (clasificador) | el payload cifrado (contenido) |
| atributo de stanza `edit` | `secretEncType` (caso de uso de cifrado) |
| `decrypt-fail="hide"` en `<enc>` | retry receipt / nodo `retry` |

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

| Elemento | Estado |
|------|-------|
| Predicados exactos de `EZN.A01`, `C35201aS.A00`, flags 3142-3146 | compuertas por clase de chat vistas, conjunto visible para el usuario sin resolver |
| Tabla de ids de casos de uso nativos (nombres a ids distintos de 5 = Report Token) | no leída |
| Posición del tag GCM y tamaño de la clave AES | inferred a partir de constantes y Baileys |
| Condición completa para enviar `MESSAGE_EDIT` propio envuelto vs en claro (flags 37948, 35457) | el decompilador perdió el control de flujo |
| Significado de `acp="2"`, del flag de serialización `A09`, del segundo campo de stanza de poll-add-option | sin resolver |
| Consumidor de `decrypt-fail="hide"` en el envelope parseado | el flag se transporta al envelope, efecto no rastreado |
| Resultado visible para el usuario de un add-on permanentemente indescifrable | no se encontró texto de fallback |
| `unavailable`, `bypassed`, `deprecated_lid_session` | no reverificados en 2.26.41.6 |
