<!-- src-sha1: 0c8270cd51a33a8c9e23ceb0a6129e273e5cb070 -->
# WhatsApp Historial de grupo — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** compartir el historial de grupo en Android (mensajes recientes del grupo enviados a los miembros nuevos): ajuste de admin `member_share_group_history_mode`, elegibilidad de emisor y receptor, flujo de unión por adición / aprobación y job pendiente, selección de mensajes y límites, `MessageHistoryBundle` (campo 70) y `MessageHistoryNotice` (campo 102), proto interno `GroupHistory`, cifrado y subida de los medios del bundle, validación e importación en el receptor, metadatos del grupo (participantes, direccionamiento LID vs PN, relaciones de comunidad), uso de sender-key, tokens de reporte, HistorySync de dispositivos complementarios (`HistorySyncConfig`, tipos de sync, operaciones peer bajo demanda), feature flags, Baileys

---

## 1. Qué es (técnicamente)

El historial de grupo permite que un miembro del grupo (admin, o cualquier miembro si el admin lo permite) envíe un bundle de mensajes recientes del grupo a las personas recién añadidas, para que la persona nueva vea el contexto. Es un mensaje de grupo normal cifrado de extremo a extremo cuyo payload es un archivo de medios (un protobuf de entradas `WebMessageInfo`). **No** es el HistorySync de dispositivos complementarios (sección 11), aunque ambos comparten la palabra "history" y algunos flags de capacidad.

Todas las afirmaciones provienen del análisis estático del APK decompilado; no se capturó nada en la red. Niveles: **found** = leído en código o recursos, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres ofuscados se re-resolvieron en 2.26.41.6 a partir de strings estables (`FMessageGroupHistoryBundleProtobuf`, `GroupHistorySendPermissionChecker`, `PendingSendGroupHistoryJob`, `member_share_group_history_mode`, `Group History`).

| Entidad | Nombre en 2.26.41.6 | Función |
|--------|----------------|------|
| Mensaje bundle | `C213539Ar` (`FMessageGroupHistoryBundle`), FMessage tipo **117** | mensaje de medios externo, `Message.messageHistoryBundle` campo **70** |
| Mensaje notice | `C213519Ap` (`FMessageGroupHistoryNotice`), FMessage tipo **118** | fila "se envió el historial", `Message.messageHistoryNotice` campo **102** |
| Serializador / parser del bundle | `C34677F2y` (`FMessageGroupHistoryBundleProtobuf`) | construir y validar el mensaje externo |
| Serializador / parser del notice | `C34678F2z` (`FMessageGroupHistoryNoticeProtobuf`) | construir y validar el notice |
| Constructor del bundle | `C9mW.A00` (+ `C231239yy`, `FMessageGroupHistoryBundleFactory`) | seleccionar, empaquetar, escribir el archivo, crear el mensaje de medios |
| Selección de mensajes | `A0G` (`GroupHistoryMessageManager`) | SQL para conteo y filas |
| Elegibilidad | `A1W` (`GroupHistorySendPermissionChecker`), `C230099x1` (gates) | comprobaciones de emisor / receptor / punto de entrada |
| Job pendiente | `PendingSendGroupHistoryJob`, `SendGroupHistoryJobRequirement` | job duradero tras la adición |
| Proveedor de requisitos | `C197318aR` (`SendGroupHistoryRequirementProvider`) | los eventos de adición / aprobación liberan el job |
| Receptor | `GroupHistoryBundleProcessor`, `GroupHistoryBundleFileProcessor` | descargar, parsear, insertar |
| Validadores / inserter | `C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg` (`GroupHistoryMessageValidator` / `GroupHistoryMessageInserter`) | comprobaciones por mensaje e inserción en la DB |
| Fila de tipo de medio | `C15530gU.A0F` | `group-history`, `GROUP_HISTORY`, HKDF info `Group History`, id **117** |
| UI de ajustes | `com.whatsapp.grouphistory.setting.ui.*`, `GroupPermissionsActivity` (`C201678ic`) | diálogo de cantidad, toggle del pie, interruptor de permiso |

Por cada compartición existen dos mensajes distintos: el **bundle** (lleva los datos, enviado al grupo) y el **notice** (lleva solo conteos y receptores, enviado después de que el bundle salió del dispositivo, sección 5.4).

---

## 2. Metadatos y ajustes del grupo

### 2.1 Nodo de info del grupo (`<group>`, ruta XMPP heredada `C23201A1a.A0C`)

Parseado por el mismo helper para consultas `w:g2` y notificaciones de grupo; existe un gemelo MEX/SMAX (`AbstractC23204A1d`, `AN6`, `C23690AKd`). Solo los campos relevantes aquí y para el direccionamiento:

| Atributo / hijo | Tipo | Uso |
|-------------------|------|-----|
| `id`, `creation`, `subject`, `s_t`, `s_o`, `s_o_pn`, `creator`, `creator_pn` | attrs | identidad; los gemelos `_pn` llevan el JID de teléfono junto a un LID |
| `addressing_mode` | `lid` o `pn` | almacenado en `wa_group_admin_settings.addressing_mode`; cualquier valor distinto de `pn` se lee como `lid` (`AbstractC268510t`) |
| `<group_history/>` | hijo vacío | presencia booleana; almacenado como `history_enabled`; significado inferido (feature flag del grupo) |
| `<member_share_group_history_mode>` | texto | ajuste de admin, 2.4 |
| `<member_add_mode>` | `all_member_add` / otro | `member_add_mode` 1 / 0 |
| `parent`, `default_sub_group`, `linked_parent jid`, `general_chat` | hijos | tipo de grupo, 2.3 |

### 2.2 Participantes y direccionamiento (found)

`<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`):

| Atributo | Uso para el historial de grupo |
|-----------|-----------------------|
| `jid` | participante, LID o PN según `addressing_mode`; un JID PN con atributo `phone_number` se comprueba por discrepancia |
| `lid`, `phone_number` | la otra forma de dirección; almacenada mediante el repositorio de mapeo de JID |
| `join_time` | long positivo (segundos, inferred); almacenado por participante; base para "se unió hace demasiado tiempo" |
| `group_history_sent` | `"true"` / `"false"`, Boolean; alimenta `group_participant_user.group_history_send_state` (mapeo inferido, 3.2) |

Las listas de receptores y emisores en los metadatos del bundle (sección 6.2) son strings JID. El job las normaliza al modo de direccionamiento del grupo antes de usarlas: `PendingSendGroupHistoryJob.A01` mapea cada receptor a su **LID** cuando el grupo usa direccionamiento LID (`C30194DBb.A05`), y si no mapea LID a PN (`C0YH.A0G` / `AbstractC197018Zw.A0Y`). Cuando se añade un participante, el job acepta ambas formas (`C0YH.A0J` devuelve la contraparte) para coincidir con los conjuntos de requisitos. Qué forma acaba en la red depende del modo del grupo (inferido del código de mapeo).

### 2.3 Relaciones de comunidad y grupo padre

`C23201A1a.A01` clasifica un nodo de grupo: **0** normal, **1** padre de comunidad (`parent`), **2** subgrupo vinculado (`linked_parent`), **3** subgrupo por defecto (`default_sub_group`), **6** chat general. `A03` lee el JID del padre de `linked_parent jid`. El valor por defecto de `membership_approval_mode` para subgrupos proviene de `parent/default_membership_approval_mode="request_required"`.

Found: `A1W` comprueba solo el **tipo de JID** (los tipos 1 y 2 pasan `C0DZ.A0l`: grupo `@g.us` y el grupo `@temp` `C99Q`), no el rol en la comunidad. El receptor acepta solo el tipo 1 (`C0DZ.A0b`). Si un grupo padre / de anuncios queda excluido por gates del servidor o experimentos por grupo (23245 / 30905 son por grupo) es unknown. Los mensajes de comentario (comentarios de anuncios de comunidad) y los hijos de asociación viajan en listas separadas (6.1); el receptor descarta un comentario o hijo cuyo padre no está en el bundle (`orphan_parent_not_in_bundle`, `invalid_comment`).

### 2.4 Ajuste de admin `member_share_group_history_mode`

| Valor en la red | Enum (`EnumC216299Tq`) | Int local | Significado |
|------------|------------------------|-----------|---------|
| ausente / desconocido | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` 0 | 0 | sin definir |
| `admin_share` | `ADMIN_SHARE` 1 | 1 | solo los admins envían historial |
| `all_member_share` | `ALL_MEMBER_SHARE` 2 | 2 | cualquier miembro puede enviar |
| `all_member_share_toggle_on` | `ALL_MEMBER_SHARE_TOGGLE_ON` 3 | 2 | igual que 2; variante vista en notificaciones (distinción inferida) |

Mapeo: `AbstractC227759t3.A01(String)` (string a int), `A00(enum)` (enum a int, 2 y 3 a 2).

| Elemento | Detalle (found) |
|------|----------------|
| Establecer | interruptor de `GroupPermissionsActivity` (`C201678ic.A04`): operación MEX `SetGroupProperty` (cliente `whatsapp-android-mex`, clase de entrada `C204518nF`) con `member_share_group_history_mode` = `ALL_MEMBER_SHARE` o `ADMIN_SHARE`. La misma entrada lleva además `allow_admin_reports`, `allow_non_admin_sub_group_creation`, `announcement`, `hidden_group`, `locked`, `member_add_mode`, `member_link_mode`, `membership_approval_mode_enabled`, `participant_label_enabled`, `subject` |
| Notificación | la notificación de grupo (`w:gp2`, inferido) hijo `member_share_group_history_mode` (`C22270sr`) llama a `A0g(actor, group, mode int, ts)`: actualiza el modo almacenado e inserta un mensaje de sistema |
| Mensaje de sistema | "activó / desactivó el uso compartido del historial reciente para miembros nuevos" en seis variantes (actor `%s`, "Recent history sharing was ...", "You ..."), cada una con "Tap to change" o "Tap to learn more" |
| History sync | `GroupShareGroupHistoryModeHistorySync` recrea el mensaje de sistema para los dispositivos complementarios; `GroupChangeHistoryEnabledHistorySync` hace lo mismo para `history_enabled` |
| DB | `wa_group_admin_settings`: `share_group_history_setting_mode`, `group_history_toggle_mode`, `history_enabled`, `earliest_group_history_message_timestamp_ms` |

El significado de `group_history_toggle_mode` (int, separado del modo de compartición) no está resuelto; la columna se lee para grupos donde es distinta de cero y `group_state = 0`. Textos de la UI: "Admins can choose if members are allowed to send message history", "Admins control if history is sent", "When adding someone to the group, members have the choice to send up to 100 recent messages".

---

## 3. Elegibilidad

### 3.1 Emisor (`A1W.A03`, found)

| # | Condición | Si no |
|---|-----------|------|
| 1 | kill switch **35987** activado (prerrequisitos del emisor) | `PREREQUISITES_DISABLED` |
| 2 | tipo de JID de grupo 1 o 2 | `GROUP_TYPE_NOT_ELIGIBLE` |
| 3 | existe la fila de contacto del grupo | `GROUP_NOT_FOUND` |
| 4 | estoy en el grupo, y o soy admin / superadmin, o (`require_membership_approval` = false y `member_add_mode` = 1 y modo de compartición = 2) | `SENDER_NOT_ELIGIBLE` (el log lista los tres valores) |
| 5 | existe al menos un mensaje compartible (conteo `A0G.A00` > 0) | `NO_SHAREABLE_MESSAGES` (también corrige el timestamp más antiguo almacenado, `A0A`) |
| 6 | gate por punto de entrada `A1W.A02` (3.3) | `EXPERIMENT_DISABLED` |

Es decir, un miembro normal solo puede enviar en grupos donde cualquiera puede añadir miembros, no se necesita aprobación y el admin habilitó `all_member_share`.

### 3.2 Receptor (por usuario añadido, found)

| Comprobación | Código de resultado |
|-------|-------------|
| el receptor no es un bot (`AbstractC24760wu.A03`) | `RECEIVER_NOT_ELIGIBLE` |
| el contacto receptor no está "no longer active" (`externalUserState`, `A07`) | `RECEIVER_INACTIVE` |
| existe la fila de participante para (grupo, usuario) | `NOT_IN_GROUP` |
| `now - join_time` por debajo del flag **30333** (unidad no resuelta) y `group_history_send_state` es null o 1 | `NOT_NEW_OR_ALREADY_SENT` |

`group_history_send_state` (columna de `group_participant_user`, escrita por `C14850fN.A0R`): 1 = aún elegible, 2 = ya enviado (found a partir de la rama "ya enviado" y de la ruta de cancelación que restablece 2 a 1). El mapeo del atributo de red `group_history_sent` al estado es inferido.

### 3.3 Gates (`C230099x1`, `A1W.A02`)

Cada gate es `flag global OR exposición por grupo` (`C41861nA.A04(group, id)`):

| Helper | Global | Id por grupo | Uso |
|--------|--------|--------------|-----|
| `A01` | **26451** | 30905 | punto de entrada `AFTER_JOIN` |
| `A02` | **15313** | 23245 | enviar historial durante la adición (`A1W.A0B`), también controla `onGroupParticipantsAdded` |
| `A03` | **29973** | 30906 | llamadores no trazados |

Puntos de entrada (`C9SA`): `AFTER_JOIN`, `FROM_MENTION`, `FROM_CONTACT_MESSAGE`. `FROM_MENTION` y `FROM_CONTACT_MESSAGE` están además ligados a los kill switches **35554** / **35555** y al gate `A02`. La polaridad de la comprobación combinada no está resuelta (el flujo decompilado está distorsionado alrededor de `A1W.A09`).

---

## 4. Flujo de unión (lado emisor)

### 4.1 Puntos de entrada de la UI (found)

| Entrada | Clase | Qué ocurre |
|-------|-------|--------------|
| Selector de añadir miembros | `VoipParticipantPickerFragment` + `GroupHistoryAddMembersSettingFooterView` | pie "Send message history to approved members" con un toggle y un enlace "recent messages"; al pulsar se abre el diálogo de cantidad; el estado del toggle se recuerda (`is_group_history_toggled`) |
| Pantalla de aprobación de membresía | `GroupMembershipApprovalRequestsFragment` (`C24002AWf`) | el mismo diálogo de cantidad antes de aprobar |
| Hoja posterior a la unión | `GroupHistoryAfterJoinSendBottomSheetFragment` | "Send message history to %1$s?" (uno o dos nombres) |
| Mención / contacto compartido | puntos de entrada `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | solo nombres; comportamiento no trazado |

Texto de confirmación en el primer uso: "Group history messages are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them." (contador `group_history_confirmation_dialog_confirmed_times`).

### 4.2 Opciones de cantidad (`C229129vL.A00(n)`, found)

`n` = conteo de `A0G.A00` (mensajes que caben en los límites de 5.1).

| n | Opciones |
|---|---------|
| 0 | ninguna ("No message history to view") |
| 1..25 | una opción, `n`, marcada "all" ("Last %d (all)") |
| > 25 | `k = min(4, ceil(n/25))`, `step = max(25, n/k)`; opciones `step`, `2*step`, ... hasta `k-1` pasos, luego `n` (marcada "all" bajo una condición de tamaño en el último paso; la comparación exacta no está resuelta) |

La lista se invierte luego mediante `C0CG.A0Z` (inferido: la mayor primero); la primera entrada viene preseleccionada. Siempre se muestra un aviso de mensajes fijados ("All available pinned messages will be included").

### 4.3 IQ de adición y cableado de eventos (found)

```xml
<iq xmlns="w:g2" type="set" to="GROUP@g.us" id="…">
  <add>                                       <!-- optional transparency_acknowledged="true" -->
    <participant jid="USER"><privacy>bytes</privacy></participant>   <!-- privacy child optional -->
  </add>
</iq>
```

Found leyendo el builder (`C11410Yt`): no se añade ningún atributo específico del historial a la solicitud de adición; la decisión sobre el historial es puramente local. Eventos que liberan el job pendiente (`C197318aR`, timeout de 32 s para el IQ en sí):

| Evento | Handler | Efecto |
|-------|---------|--------|
| Historial solicitado | `CCP(params, group, requestId, receivers, nonReceivers, approvedByMe)` | persistir `PendingSendGroupHistoryJob`; recordar la cantidad elegida en `A08[requestId]`; establecer `group_history_usage_activated` |
| IQ de adición respondido | `BfO(C222169gu)` | almacenar el mapa de resultados por solicitud |
| Participantes añadidos (notificación) | `BvD` (solo con el gate `A02`) | añadir a los conjuntos "añadidos por mí" / "añadidos por otros" |
| Aprobación de membresía respondida | `C05(group, user, requestId, approved)` | almacenar el usuario aprobado (o vacío) |

### 4.4 Job pendiente (`PendingSendGroupHistoryJob`, found)

Campos: `permanentGroupRawJid`, `requestId`, `messageCount`, `lastMessageSortId`, `groupHistoryReceiverRawJids`, `groupHistoryNonReceiverRawJids`, `approvedByMeRawJids`, `jobScheduledServerTimeInMillis`, `expirationTimeInMins`. Id de job persistente `group-pending-send-group-history`, requisito `SendGroupHistoryJobRequirement` (todos los JID de receptores deben parsearse, si no `invalid group history receiver jid`).

| Paso | Detalle |
|------|--------|
| Requisito cumplido cuando | el job expiró; o llegó el resultado de la adición / aprobación para `requestId`; o un receptor está en el conjunto "añadidos por otros" y no aprobado por mí; o un receptor ya es participante (`A0r`) |
| Expiración | `scheduled + flag 19034` minutos; job expirado: cancelar, restablecer el estado de participante 2 a 1 |
| Ejecución | dividir los receptores en ya unidos y restantes; los restantes pasan a un **nuevo** job pendiente (mismo request id, no-receptores filtrados); los receptores ya unidos reciben el bundle (`C9mW.A00`) |
| Receptores bot | un receptor bot TEE (`AbstractC197238aI.A00`) se gestiona con un sello de historial compartido aparte (`A04`, 5.5) |
| Protección contra duplicados | mapa `C197318aR.A09` (grupo, usuario) a hora de envío; las entradas con más de `19034` minutos (mín. 5) se podan |

---

## 5. Selección, límites y empaquetado

### 5.1 Selección de filas (`A0G`, `AbstractC494421h.A00`, found)

```sql
SELECT … FROM available_message_view [ / with association join when 24033 ]
WHERE timestamp >= (scheduledTimeMs - flag18406 s)
  AND chat_row_id = ? AND sort_id <= ?                 -- anchor = last message at scheduling time
  AND view_mode IS NOT 1 AND view_mode IS NOT 3
  AND message_type IN (shareable types)                -- from the type registry, BUv()
  AND (association_type IS NULL OR association_type IN (supported))   -- only when 24033
  AND (from_me = 0 OR status NOT IN (-1,0,1,2,7,20,21,22))
  AND (expire_timestamp IS NULL OR expire_timestamp >= now OR keep_in_chat = 1)
ORDER BY sort_id DESC LIMIT n
```

| Parámetro | Fuente |
|-----------|--------|
| `n` | la consulta de conteo usa el flag **18405** como LIMIT; la consulta de envío usa el conteo elegido por el usuario |
| ventana | flag **18406** (segundos) antes de la hora de programación; el texto de la UI promete "up to 100" mensajes |
| tipos compartibles | registro por tipo de FMessage (`C222979iT.A00`, `C1ZP.BUv()` true), con una anulación por mensaje (`C30039D5b`); no enumerado aquí |
| mensajes propios | solo los que salieron del dispositivo (`status` fuera del conjunto pendiente / fallido `AbstractC494421h.A00`) |
| efímeros | los mensajes expirados y no conservados se omiten |

Si se conoce un sort id posterior a la unión (`C14650f0.A05`), el conteo se ancla en él ("post-join query"); si no, en el mensaje más reciente ("pre-join query").

### 5.2 Listas en el bundle (found, `C9mW.A00`)

| Lista | Contenido | Límite |
|------|---------|-------|
| `messages` | las filas seleccionadas (solo compartibles) | `n` |
| `uncountedAssociatedMessageLists` | hijos adjuntos a un padre seleccionado (elementos de álbum, encuestas, ...), agrupados por `(parent key, association type)`; solo con **24033** | no cuentan en `messageCount` |
| `commentMessages` | comentarios de los mensajes seleccionados (`C14780fG.A02(list, flag 6050, …)`) | flag **6050** (inferido como el tope) |
| `outOfWindowPinnedMessages` | mensajes fijados más antiguos que el seleccionado más antiguo; solo sin medios; filtrados por el conjunto compartible | todos los disponibles (string de aviso); tope del receptor flag **19811** (inferido) |

Tipos de asociación (`C13O`, 21 valores): `FUTURE` 0 (también el fallback), `MEDIA_ALBUM` 1, `BOT_PLUGIN` 2, `EVENT_COVER_IMAGE` 3, `HD_VIDEO_DUAL_UPLOAD` 5, `STATUS_EXTERNAL_RESHARE` 6, `MEDIA_POLL` 7, `POLL_ADD_OPTION` 20, `STREAMED_HD_VIDEO_DUAL_UPLOAD` 22 y otros tipos de estado / sticker / dual-upload.

### 5.3 Empaquetado (found)

1. El proto `GroupHistory` (6.1) se serializa a un archivo con extensión `proto` (`File … A0Z(C15530gU.A0F, "proto")`); no se encontró ningún paso de compresión.
2. Se crea un nuevo FMessage de tipo 117 en el chat del grupo con el archivo como medio (`mimetype application/protobuf`) y se entrega al pipeline normal de envío de mensajes de medios (subida y cifrado, sección 7).
3. Campos locales en el FMessage: conteo de mensajes, timestamp más antiguo en la ventana (segundos), timestamp más antiguo global (mín. con los mensajes fijados), receptores, no-receptores, tamaños de las listas de mensajes empaquetadas, tamaño del archivo, tiempo de construcción (telemetría).
4. Si **24741** está activado y el mensaje no tiene secreto, se genera un message secret nuevo para él y luego se calculan tokens de reporte por cada mensaje original (sección 9).

### 5.4 Notice tras el envío (found, `ANQ.C0M`)

Cuando el bundle alcanza el estado **1** (o **24** si el flag **28787** está activado) y el notice aún no se había enviado (`A00 != 1`), el dispositivo crea un notice de tipo 118 en el mismo grupo con los conteos, timestamps y receptores del bundle y lo envía (`C33166Ecf.A06`). Todos los miembros del grupo lo reciben; los destinatarios nombrados en `historyReceivers` además lo marcan (`AbstractC30028D4q.A1B`).

### 5.5 Historial compartido con bot TEE (found, breve)

Para un receptor bot, `C9mW.A01` sella los mensajes seleccionados que llevan un message secret con una prueba (`AbstractC33322EfC.A02(sender, botJid, "TEE History Share", stanzaId, secret)`) y envía un notice cuyo `botHistoryShareSyncMetadata` lista `(stanzaId, messageSecretProof)`. Ver el informe de Meta AI para el contexto de bots: [WA_META_AI.md](./WA_META_AI.md). La ruta de bot no sube un bundle.

---

## 6. Formato en la red

### 6.1 Archivo interno: `GroupHistory` (`DSN`)

| Campo | Número | Tipo | Contenido |
|-------|--------|------|---------|
| `messages` | **1** | repeated `WebMessageInfo` (`C30626DTu`) | mensajes contados |
| `uncountedAssociatedMessageLists` | **2** | repeated `UncountedAssociatedMessageList` (`C30578DRy`) | `messages` **1** (repeated WebMessageInfo), `parentMessage` **2** (`MessageKey`, `BD5`), `associationType` **3** (enum `C13O`) |
| `commentMessages` | **3** | repeated `WebMessageInfo` | comentarios |
| `outOfWindowPinnedMessages` | **4** | repeated `WebMessageInfo` | fijados |

El receptor parsea los mismos bytes una segunda vez como `GroupHistoryWithMessageBytes` (`C30576DRw`: los mismos cuatro números de campo; entradas `C30543DQp` con `key` **1** (`MessageKey`) y `message` **2** (bytes); las listas de asociación `DPH` leen solo `messages` **1**). Esa variante conserva los bytes serializados originales por mensaje (usada para la validación de tokens de reporte y el manejo de secretos, inferido).

### 6.2 Mensaje externo: `Message.messageHistoryBundle` (`DT6`, campo **70**)

| Campo | Número | Tipo | Valor / uso |
|-------|--------|------|-------------|
| `mimetype` | **1** | string | debe ser igual a `application/protobuf` |
| `fileSha256` | **2** | bytes | 32 bytes, hash del texto plano |
| `mediaKey` | **3** | bytes | media key |
| `fileEncSha256` | **4** | bytes | 32 bytes, hash del texto cifrado |
| `directPath` | **5** | string | ruta de subida; vacío se registra en el log, no es fatal al parsear |
| `mediaKeyTimestamp` | **6** | int64 | segundos |
| `contextInfo` | **7** | `ContextInfo` | estándar |
| `messageHistoryMetadata` | **8** | `MessageHistoryMetadata` (`C30583DSd`) | ver abajo |

`MessageHistoryMetadata`:

| Campo | Número | Tipo | Regla al recibir |
|-------|--------|------|-----------------|
| `historyReceivers` | **1** | repeated string | al menos uno; el usuario actual debe figurar |
| `oldestMessageTimestampInWindow` | **2** | int64 | presente y > 0 |
| `messageCount` | **3** | int64 | presente y > 0 |
| `nonHistoryReceivers` | **4** | repeated string | opcional |
| `oldestMessageTimestampInBundle` | **5** | int64 | opcional (incluye fijados) |

### 6.3 Notice: `Message.messageHistoryNotice` (`DRY`, campo **102**)

`contextInfo` **1**, `messageHistoryMetadata` **2** (mismo tipo, obligatorio con las reglas de receptores, timestamp y conteo), `botHistoryShareSyncMetadata` **3** (`C25765B9z`: `botJid` **1**, `historyShareMessages` **3** repeated `BA2` = `stanzaId` **1**, `messageSecretProof` **2**). El layout lite no tiene el campo **2** en `C25765B9z`; un cutoff existe solo como estado local (`C213519Ap.A03`).

### 6.4 Nivel de stanza (found)

| Elemento | Bundle (117) | Notice (118) |
|------|--------------|--------------|
| `type` de la stanza | `media` | no específico de medios |
| `<enc>` media type | `group_history` (`C30106D7q`; en el conjunto permitido de enc media types `C9E2` / `C33474Ehg`) | ninguno |
| `<meta appdata="…">` | **no establecido** (`C213539Ar` no implementa `FZF`) | `group_history` (`C213519Ap.AVN`; lo escribe `F6K`) |
| comprobación del receptor | `A0O == "media"` y `A0J == "group_history"`, si no error 11 | `appdata == group_history`, si no error 76 |
| `<reporting>` | opcional, sección 9 | ninguno |

Ambas comprobaciones se omiten cuando los flags del envelope `A0V` / `A0U` están activos (significado sin resolver). Un bundle que llega con media type `group_history` pero sin un mensaje coincidente, y un appdata de notice en un tipo ajeno, son rechazados por `GroupHistoryBundleDeserializationValidator` / `GroupHistoryNoticeDeserializationValidator` (`F3b` / `F3c`).

### 6.5 Marcadores de `WebMessageInfo` (`C30626DTu`, found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `isGroupHistoryMessage` | **57** | bool | el mensaje se importó desde un bundle |
| `reportingTokenInfo` | **62** | message | tag de reporte (ver el informe de Reporting) |
| `groupHistoryIndividualMessageInfo` | **74** | `C30549DQv` | `bundleMessageKey` **1** (`MessageKey`), `editedAfterReceivedAsHistory` **2** (bool) |
| `groupHistoryBundleInfo` | **75** | `C30548DQu` | `deprecatedMessageHistoryBundle` **1**, `processState` **2** (enum `EnumC32128E2a`) |

`processState`: `NOT_INJECTED` 0, `INJECTED` 1, `INJECTED_PARTIAL` 2, `INJECTION_FAILED` 3, `INJECTION_FAILED_NO_RETRY` 4, `DEDUPED` 5.

---

## 7. Cifrado y medios

| Capa | Found |
|-------|-------|
| Transporte del mensaje | fan-out de grupo normal: el mensaje 117 se cifra como cualquier mensaje de grupo (`skmsg` de sender-key por grupo más la distribución habitual de sender-key a los dispositivos). Lo básico no se repite aquí; la forma de la stanza `<enc>` está en [WA_CALL_SIGNALING.md](./WA_CALL_SIGNALING.md) sección sobre `<enc>`. El estado de sender-key por dispositivo vive en `group_participant_device` (`sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket`) |
| Fila de medios | `C15530gU.A0F`: tipo de subida `group-history`, tipo de archivo `GROUP_HISTORY`, HKDF info `Group History`, id 117 |
| Clave / cifrado | media key aleatoria, HKDF-SHA256 con info `Group History`, AES-256-CBC, HMAC-SHA256 truncado a 10 bytes anexado, `fileSha256` / `fileEncSha256` en el proto: el esquema genérico de [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) sección 6 (expansión de 80 bytes en Android); aplicado a este tipo mediante el pipeline de envío común (inferido, solo se leyó la fila del tipo) |
| URL de subida | `https://<host>/mms/group-history/<hash>?…`; la composición `mms/<upload type>` es found para la tabla (sección 4 del informe de medios); la ruta literal para este tipo no se capturó (inferido) |
| Descarga | descarga de medios estándar usando `mediaKey`, `directPath`, hashes; texto de fallo `GroupHistoryBundleProcessor/download failed for … with reason …` |
| Reutilización de claves | la media key del bundle es independiente de las claves de mensaje de los mensajes contenidos |

El receptor siempre trabaja con la `mediaKey` del proto; un bundle cuyos hashes no miden 32 bytes se rechaza (`bogus sha-256 hash received`, error 14).

---

## 8. Receptor: validación e importación

### 8.1 Comprobaciones al parsear (`C34677F2y.CM7`, found)

| Comprobación | Error |
|-------|-------|
| el JID del chat es un grupo (`A0l`) | 11 `chatJid is not a group` |
| envelope `media` + enc media type `group_history` | 11 |
| `mimetype == application/protobuf` | 11 |
| `fileSha256`, `mediaKey`, `fileEncSha256`, `mediaKeyTimestamp`, metadatos presentes | 11 |
| `historyReceivers` no vacío, timestamp de ventana > 0, conteo > 0 | 11 |
| usuario actual en `historyReceivers` (no para mensajes propios) | 11 `current user is not in history receivers list` |
| gate **15311** desactivado | FMessage placeholder `C35281aa` con código **82** ("Update to the latest version of WhatsApp to see it") |
| longitud de hashes 32 | 14 |

Notice (`C34678F2z`): chat de grupo, appdata, metadatos con receptores / timestamp / conteo; el gate **15722** desactivado da el placeholder con código **10008**.

### 8.2 Procesamiento (`GroupHistoryBundleProcessor`, found salvo indicación)

1. Disparador: mensaje añadido (`C0G`) y de nuevo en el estado de medios 3 (`C0M`). Un candidato es un chat de grupo (tipo 1), no mío, estado 0 o 5, conmigo en la lista de receptores, y más reciente que el flag **25910** (unidad no resuelta; en caso contrario "Message history expired").
2. Deduplicación (flag **30462**): si ya se procesó un bundle para la misma sesión de unión, el nuevo se marca como deduplicado (`deduped_bundle_for_join_session`), UI: "%1$s also sent you message history, which you already got from someone else".
3. Descargar el medio; el fallo muestra "Couldn't download message history from %1$s".
4. Parsear el archivo dos veces (`DSN`, `DRw`); fallo de parseo: `protobuf_parse_failed`.
5. Buscar el ancla: el último mensaje de unión al grupo ("failed to find latest group join message, adding messages before the first message in chat" cuando no hay ninguno); un ancla demasiado antigua: `anchor_message_too_old`.
6. Validar e insertar cada mensaje (8.3); asociar cada fila insertada con el bundle (`group_history_bundle_association`: `bundle_message_key_id`, `message_row_id`, `message_sort_id`); marcar `isGroupHistoryMessage`.
7. Fijados fuera de ventana: tope (flag **19811**, inferido), aplicar el estado de fijado compartido (`applySharedPin`).
8. Aplicar los sellos pendientes de historial compartido con bots (`BotHistoryShareHelper`), luego telemetría (`group_history_receiver_user_journey`).

Las filas importadas se colocan antes del ancla de unión, por lo que aparecen sobre la línea "te añadieron" (inferido de la lógica del ancla).

### 8.3 Validación por mensaje (`C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg`, found)

| Motivo de omisión | Causa |
|-------------|-------|
| `invalid_jid` | `key.remoteJid` difiere del chat del bundle |
| `non_hex_id` | `key.id` no es solo hexadecimal |
| `timestamp_too_old` | `messageTimestamp` no es más reciente que el límite inferior permitido (campos de log `msgTs`, `allowedTs`, `diff`; límite derivado del estado local, fórmula no resuelta) |
| `parse_failed`, `pin_not_parsed` | el proto de la entrada no se parseó |
| `not_shareable` | tipo de mensaje no permitido para importar |
| `no_local_copy` | fijado compartido cuyo mensaje se omitió y no es local |
| `max_limit_reached` | tope alcanzado |
| `timestamp_after_anchor` | mensaje más reciente que el ancla de unión |
| `already_exists`, `duplicate`, `expired` | ya presente localmente, duplicado en el archivo, efímero expirado y no conservado |
| `orphan_parent_not_in_bundle`, `invalid_comment` | comentario / hijo de asociación sin su padre en el archivo |
| `insert_exception`, `anchor_messages_failed`, `insert_messages_exception` | errores de la DB local |

Además: un mensaje necesita conservar su `messageSecret` (logs `messageSecretLost`, `noMessageSecret`); la copia local prevalece cuando existe un mensaje con contenido distinto (`keeping local …`).

Tablas tocadas (found): `group_history_bundle_association` (`bundle_message_key_id`, `message_row_id`, `message_sort_id`), `group_history_share_reporting_info` (`stanza_id`, `reporting_tag`, `send_timestamp`, `added_timestamp`, `reporting_token`, `reporting_token_version`, `is_send`, `validation_policy`), `group_participant_user.group_history_send_state`, `wa_group_admin_settings` (2.4).

---

## 9. Tokens de reporte (breve)

Sección de stanza para un bundle cuando **24741** está activado (`F6C`, `GhsReportingTokenMessageSendStanzaContributor`):

```xml
<reporting>
  <message id="ORIGINAL_STANZA_ID"><reporting_token v="N">16 bytes</reporting_token></message>
  …
</reporting>
```

La derivación y el almacenamiento del token están en [WA_REPORTING.md](./WA_REPORTING.md) (sección 6.2); parte de la derivación de la clave se ejecuta en código nativo, por lo que los bytes exactos no son reproducibles solo con Java. Al recibir, cuando **5718** y **24742** están activados, un token ausente para un mensaje importado produce la telemetría `GROUP_HISTORY_MESSAGE_MISSING_FROM_PUBLIC_STANZA` (y, con **13063**, una fila de diagnóstico interna); en esa ruta el mensaje se inserta igualmente (inferido del flujo de control). Si el servidor exige tokens: unknown.

---

## 10. HistorySync de dispositivos complementarios (relacionado, no es historial de grupo)

Lo básico del emparejamiento y del app-state está en [WA_LINKED_DEVICE_PAIRING.md](./WA_LINKED_DEVICE_PAIRING.md) y [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md). Solo lo que afecta a los datos de grupo:

### 10.1 `HistorySyncConfig` (`C44601rs`, lo anuncia el complementario; números de campo del layout lite)

| Campo | # | Valor del complementario (found) |
|-------|---|-------------------------|
| `fullSyncDaysLimit`, `fullSyncSizeMbLimit` | 1, 2 | flags **15284**, **15283** |
| `storageQuotaMb`, `initialSyncMaxMessagesPerChat` | 3, 20 | no establecidos en la rama trazada |
| `recentSyncDaysLimit` | 5 | 0 |
| `supportMessageAssociation`, `supportHostedGroupMsg`, `supportAddOnHistorySyncMigration` | 14, 11, 13 | true |
| `supportGroupHistory` | 15 | flag **20658** |
| `onDemandReady` / `completeOnDemandReady` | 16 / 18 | `!` flag **18953** / false |
| `thumbnailSyncDaysLimit` | 19 | flag **21217** |
| `supportHatchHistory` / lista de canales de bots | 22 / 23 | flag **26445** / rama en **26614** |
| historial de llamadas, de bots y de CAG, `supportNewsletter`, `supportInlineContacts`, ... | 4, 6-8, 12, 24-27 | true (los demás false) |

Los campos restantes (`supportBizHostedMsg` 9, `supportRecentSyncChunkMessageCountTuning` 10, `supportGuestChat` 17, `supportManusHistory` 21, `supportUniversalReachChat` 26, `supportOmittedConversationIndex` 27) no se detallan aquí.

### 10.2 Tipos de sync y mensajes

| Mensaje | Campo | Contenido |
|---------|-------|---------|
| `HistorySync` (`C25838BCy`) | `syncType` **1**, `conversations` **2**, `statusV3Messages` **3**, `chunkOrder` **5**, `progress` **6**, `pushnames` **7**, `globalSettings` **8**, `threadIdUserSecret` **9**, `threadDsTimeframeOffset` **10**, `recentStickers` **11**, `pastParticipants` **12**, `callLogRecords` **13**, `aiWaitListState` **14**, `phoneNumberToLidMappings` **15**, `companionMetaNonce` **16**, `shareableChatIdentifierEncryptionKey` **17**, `accounts` **18**, `nctSalt` **19**, `inlineContacts` **20/21**, `omittedConversations` **23/24** | las conversaciones de grupo viajan en `conversations`; `pastParticipants` (**12**) lista a antiguos miembros del grupo |
| `HistorySyncNotification` (`C25834BCt`) | `fileSha256` **1**, `fileLength` **2**, `mediaKey` **3**, `fileEncSha256` **4**, `directPath` **5**, `syncType` **6**, `chunkOrder` **7**, `originalMessageId` **8**, `progress` **9**, `oldestMsgInChunkTimestampSec` **10**, `initialHistBootstrapInlinePayload` **11**, `peerDataRequestSessionId` **12**, `fullHistorySyncOnDemandRequestMetadata` **13**, `encHandle` **14**, `messageAccessStatus` **15** | chunk referenciado por medios; el payload es `HistorySync` |

Tipos de sync: `INITIAL_BOOTSTRAP` 0, `INITIAL_STATUS_V3` 1, `FULL` 2, `RECENT` 3, `PUSH_NAME` 4, `NON_BLOCKING_DATA` 5, `ON_DEMAND` 6, y en el enum de 9 valores (`EnumC26456Bdr`) también `NO_HISTORY` 7 y `MESSAGE_ACCESS_STATUS` 8 (`EnumC26449Bdk` es la variante de 7 valores).

### 10.3 Operaciones peer data bajo demanda (`EnumC26460Bdv`, found)

| Operación | Id | Campo de solicitud (`C25823BCh`) | Campo de respuesta (`C25828BCm`) |
|-----------|----|-----------------------------|------------------------------|
| `HISTORY_SYNC_ON_DEMAND` | 3 | `historySyncOnDemandRequest` **4** (`BCR`: `chatJid` **1**, `oldestMsgId` **2**, `oldestMsgFromMe` **3**, `onDemandMsgCount` **4**, `oldestMsgTimestampMs` **5**, `accountLid` **6**, `supportInlineResponse` **7**) | ninguno definido; el historial llega como un `HistorySyncNotification` (inferido) |
| `FULL_HISTORY_SYNC_ON_DEMAND` | 6 | `fullHistorySyncOnDemandRequest` **6** (`BBB`: `requestMetadata` **1** `BBA`, `historySyncConfig` **2**, `fullHistorySyncOnDemandConfig` **3** `C156516k5`: `historyFromTimestamp` **1**, `historyDurationDays` **2**) | `fullHistorySyncOnDemandRequestResponse` **6** |
| `PLACEHOLDER_MESSAGE_RESEND` | 4 | **5** | **4** |
| `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` | 8 | **7** | **8** |

El primario mantiene una fila por sync en `msg_history_sync` (`device_id`, `sync_type`, `last_processed_msg_row_id`, `oldest_msg_row_id`, `sent_msgs_count`, `chunk_order`, `sent_bytes`, `last_chunk_timestamp`, `status`, `peer_msg_row_id`, `oldest_message_to_sync_row_id`, `session_id`, `size_limit_bytes`, `full_history_on_demand_request_id`, …). Los topes del servidor sobre el tamaño de chunk y el número de mensajes no son visibles en el código del cliente leído (unknown). No existe ninguna operación bajo demanda específica para el historial compartido de un grupo.

### 10.4 Historial de grupo en dispositivos complementarios

| Elemento | Found |
|------|-------|
| Capacidad | `supportGroupHistory` (flag **20658**) en `companion-props`; almacenado en el primario como `support_group_history` (informe de emparejamiento, sección 6.2); consumidor no trazado |
| Entrega del bundle | el bundle es un mensaje de grupo normal, por lo que todos los dispositivos de un receptor lo reciben; los strings para dispositivos vinculados ("Open WhatsApp on your phone and visit this group to see it") sugieren un placeholder allí (inferido) |
| Construcción del sync en el primario | `BuildHistorySyncParams` (`C33151EcQ`) lleva `supportGroupHistory`, `pullGroupHistoryUncountedChildren`, `maxCommentsToAdd`, `supportMessageAssociation`; consumidores no trazados |
| Mensajes de sistema | los cambios de modo de compartición, history-enabled, modo de añadir miembros / enlace / aprobación se reconstruyen para los complementarios mediante las clases `Group*HistorySync` |

---

## 11. Feature flags y límites

Los ids de flag van en negrita; los valores los entrega el servidor, los valores por defecto compilados no se resolvieron (el texto de la UI dice "up to 100" mensajes).

| Flag | Tipo | Controla | Nivel |
|------|------|----------|------|
| **35987** | bool | kill switch de prerrequisitos del emisor | found |
| **15313** / 23245 | bool / group | gate `A02`, enviar historial durante la adición | found |
| **26451** / 30905 | bool / group | gate `A01`, punto de entrada `AFTER_JOIN` | found |
| **29973** / 30906 | bool / group | gate `A03` | found (uso unknown) |
| **35554**, **35555** | bool | `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | polaridad inferred |
| **18405** | int | LIMIT de la consulta de conteo (tope del tamaño ofrecido) | found |
| **18406** | int, s | ventana retrospectiva antes de la hora de programación | found |
| **19034** | int, min | expiración del job pendiente, poda de duplicados (mín. 5) | found |
| **30333** | long | tiempo máximo desde la unión para un receptor | found (unidad sin resolver) |
| **24033** | bool | listas de asociación y filtro de asociación | found |
| **6050** | int | tope de recolección de comentarios | inferred |
| **24741** | bool | construir tokens de reporte al enviar | found |
| **28787** | bool | el notice se dispara con el estado 24 en lugar de 1 | found |
| **20658** | bool | el complementario anuncia `supportGroupHistory` | found |
| **15311** | bool | recepción: bundle aceptado (desactivado: placeholder 82) | found |
| **15722** | bool | recepción: notice aceptado (desactivado: placeholder 10008) | found |
| **30462** | bool | recepción: deduplicación por sesión de unión | found |
| **25910** | long | recepción: ventana de frescura de un bundle | found (unidad sin resolver) |
| **19811** | int | recepción: tope de fijados fuera de ventana | inferred |
| **24034** / **25037** | bool / int | recepción: procesamiento de hijos de asociación y su parámetro int | inferred |
| **26039** | bool | gate del inserter (tres sitios) | found (uso unknown) |
| **5718** + **24742** | bool | recepción: validación de tokens de reporte | found |
| **13063** | bool | fila de diagnóstico interna ante token ausente | found |

---

## 12. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| No hay opción "send history" | emisor no elegible (3.1), grupo sin consistencia LID / PN, o sin mensajes compartibles | el admin habilita `all_member_share`, modo de añadir miembros `all_member_add`, sin aprobación; o enviar como admin |
| El receptor muestra "Update to the latest version" | gate 15311 / 15722 desactivado o tipo desconocido | ninguna en el cliente |
| Bundle rechazado, error 11 | MIME incorrecto, tipo de envelope, media type, campo ausente, yo no estoy en `historyReceivers` | construir según la sección 6 |
| Bundle rechazado, error 14 | hash que no mide 32 bytes | corregir los hashes |
| Notice rechazado, error 11 / 76 | appdata que no es `group_history` (parseo, 11); appdata de notice en otro tipo (validador, 76) | establecer `appdata=group_history` solo en el tipo 118 |
| Faltan mensajes tras la importación | motivos de omisión en 8.3 (`timestamp_too_old`, `not_shareable`, `invalid_jid`) | las claves deben ser ids hexadecimales del mismo grupo |
| "Couldn't download message history" | falló la descarga de medios (`directPath` expirado, clave que no coincide) | reintentar; reenviar |
| El job nunca se ejecuta | no se vio el evento de adición o aprobación, los receptores nunca llegaron a ser participantes, el job expiró (19034) | volver a añadir y reenviar |

---

## 13. Distinciones clave

| No confundir | Con |
|----------------|------|
| Bundle de historial de grupo (tipo 117, `application/protobuf`, `group-history`) | notificación HistorySync de dispositivo complementario (`HistorySyncNotification`, `md-msg-hist`) |
| Bundle (datos, sin appdata) | notice (conteos y receptores, `appdata=group_history`) |
| `member_share_group_history_mode` (quién puede enviar) | `group_history_toggle_mode` / `history_enabled` (significado sin resolver) |
| `historyReceivers` (reciben los datos) | `nonHistoryReceivers` (añadidos, no reciben) |
| `oldestMessageTimestampInWindow` (**2**) | `oldestMessageTimestampInBundle` (**5**, incluye fijados fuera de ventana) |
| conteo de `messages` (`messageCount`) | hijos de asociación no contados y comentarios |
| `supportGroupHistory` en `HistorySyncConfig` (capacidad del dispositivo) | el ajuste de admin |

---

## 14. Baileys (`baron-baileys-v2` 1.5.17)

Solo hechos leídos en `src/Utils/group-history.js`, `src/Socket/groups.js`, `src/Socket/messages-recv.js`, `src/Socket/aigroups.js`, `src/Utils/validate-connection.js`, `WAProto/index.js`. No se probó nada contra un servidor; no se afirma ningún fallo.

| Tema | Baileys | Android |
|-------|---------|---------|
| Proto | `GroupHistory`, `GroupHistoryWithMessageBytes`, `GroupHistoryBundleInfo`, `GroupHistoryIndividualMessageInfo`, `Message.messageHistoryBundle`, `messageHistoryNotice`, `HistorySyncConfig.supportGroupHistory` presentes en `WAProto` | 6 |
| Decoder | `decodeGroupHistory` intenta `zlib.inflateSync`, recurre a los bytes sin procesar; modo opcional `GroupHistoryWithMessageBytes`; `processGroupHistory` normaliza las cuatro listas | no se encontró compresión en Android; lectura del protobuf sin procesar |
| Recepción del bundle | ningún código maneja `messageHistoryBundle` (descarga de medios, validación, inserción) | sección 8 |
| Envío del bundle | ninguno | sección 5 |
| Capacidad del complementario | `supportGroupHistory: true` en el `HistorySyncConfig` anunciado | flag 20658 |
| Ajuste de grupo | `member_share_group_history_mode` leído de los metadatos del grupo; `groupSetProperty(jid, property, value)` sobre MEX; la notificación mex `NotificationGroupMemberShareGroupHistoryModePropertyUpdate` emite `groups.update { memberShareHistoryMode }` | 2.4 |
| `aiGroupCreate` | acepta `memberShareGroupHistoryMode` (por defecto `all_member_share`) pero no lo coloca en la stanza de creación en el código leído | no aplica |
| Atributos de participante | `group_history_sent`, `join_time` no se parsean | 2.2 |
| Direccionamiento | `addressing_mode` leído del nodo del grupo, por defecto `lid` al enviar | 2.2 |

Consecuencia limitada a lo leído: un cliente Baileys que anuncia `supportGroupHistory` no puede importar un bundle recibido, porque no existe ningún consumidor en el código fuente. Un emisor debe seguir las secciones 5 a 7 (envío posterior a la adición, tipo `media` con enc media type `group_history`, media type `group-history` con HKDF info `Group History`, notice con appdata); si el servidor acepta un bundle sin tokens `<reporting>` es unknown.

---

## 15. Flujo completo

```
[Admin]  switch "Send message history" ─► MEX SetGroupProperty member_share_group_history_mode=ALL_MEMBER_SHARE|ADMIN_SHARE
     │
     ▼
[WA Server]  w:gp2 notification member_share_group_history_mode ─► all members: store mode, system message

[Sender]  add members (picker / approval screen / post-join sheet)
     │   A1W.A09: gate 35987, group type, sender (admin or all_member_share + all_member_add + no approval),
     │            receiver (join age, send_state), shareable messages
     │   A0G.A00 count ─► amount options (<=25 one option, else up to 4)
     ▼
iq set w:g2 <add><participant jid/></add>          (no history attribute)
     │
     ▼
[WA Server]  result ─► BfO / C05 / BvD events ─► PendingSendGroupHistoryJob requirement met
     │
     ▼
[Sender]  A0M: split joined / remaining (remaining re-queued) ─► C9mW.A00
     │   rows: timestamp >= scheduled - 18406 s, sort_id <= anchor, LIMIT n
     │   + association lists (24033) + comments (6050) + out-of-window pins
     │   GroupHistory proto ─► file ─► FMessage 117, mimetype application/protobuf
     ▼
upload  /mms/group-history  (HKDF info "Group History", AES-CBC + HMAC-10)       [WA_MEDIA_UPLOAD]
     │
     ▼
group message  type=media, enc mediatype=group_history, Message.messageHistoryBundle(70)
     │          metadata: receivers, nonReceivers, oldest ts (window / bundle), count
     │          optional <reporting><message id><reporting_token v/></message></reporting> (24741)
     ▼
[Receivers' devices]  C34677F2y checks (group, media, MIME, hashes, me in historyReceivers, gate 15311)
     │   download + decrypt ─► parse DSN / DRw ─► dedupe (30462) ─► anchor = join message
     │   validate each WebMessageInfo (jid, hex id, timestamp, type) ─► insert before anchor
     │   group_history_bundle_association, isGroupHistoryMessage=57
     ▼
[Sender]  bundle status 1 (24 with 28787) ─► notice type 118, appdata group_history, same metadata
     │
     ▼
[All members]  system row "<name> sent message history that starts on <date>"
```

---

## 16. Incógnitas

| Elemento | Estado |
|------|--------|
| Reglas de aceptación del servidor, retención, topes de tamaño, exigencia de tokens de reporte | lado servidor, no observado |
| Valores por defecto de 18405, 18406, 19034, 25910, 30333 | entregados por el servidor, valores por defecto sin resolver |
| Límite inferior exacto de `timestamp_too_old` y unidad de 25910 / 30333 | no resuelto |
| Polaridad de `A1W.A02` por punto de entrada; uso del gate `A03` y del flag 26039 | decompilación distorsionada / no trazado |
| Significado de la columna `group_history_toggle_mode` y del hijo `<group_history/>` | nombres encontrados, semántica solo inferida |
| Lista de tipos de mensaje compartibles (registro `BUv()`) | no enumerada |
| Renderizado en el complementario de un bundle; consumidor de `support_group_history` en el primario | no trazado |
| Parte nativa de la derivación de la clave del token de reporte | nativo, no leído |
| Tráfico | no se capturó nada; todos los flujos provienen del código |
