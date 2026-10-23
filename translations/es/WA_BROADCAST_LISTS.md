<!-- src-sha1: e4fe5d62fca781d0449295a5d549413929d95191 -->
# WhatsApp Listas de difusión — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** listas de difusión clásicas y difusiones de estados en Android: modelo de JID `@broadcast` (lista / estado / ubicación), creación de listas, límites de membresía y reglas de destinatarios, IQs `w:b` (obtener listas, eliminar lista, cuota), app-state `business_broadcast_list`, migración a LID, almacenamiento local, clonación por destinatario al insertar, stanza de envío (fan-out con sender key, `phash`, `bucketing`, `<cap>`, ajustes efímeros por destinatario), agregación de ack y recibos, cuota mensual de difusión, bloqueos por advertencia de spam, GAP, publicación en `status@broadcast` (`SendE2eStatusJob`, partes, buckets manuales), modos de privacidad de estados, amigos cercanos y audiencias personalizadas, respuesta / reacción / mención / notificación de estados, tablas de estados, feature flags, comparación con Baileys

---

## 1. Qué es (técnicamente)

Existen tres JIDs de servidor `broadcast`. Todos son JIDs "multiparticipante" (`AbstractC20660pZ`, misma base que los grupos) y comparten un único pipeline de envío: el remitente cifra una vez con una sender key y entrega la clave a cada dispositivo destinatario de forma pairwise. Todas las afirmaciones provienen de análisis estático del APK decompilado; no se capturó nada en la red. Tier: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto. Nada aquí es **tested**. Los nombres ofuscados se resolvieron de nuevo en 2.26.41.6 a partir de strings estables (`BroadcastListManager/…`, `BroadcastXmppMethods/…`, `StatusParticipantUserManager/…`, `SendE2eStatusJob/…`, nombres de tablas y prefs).

| Entidad | Forma del JID | `Jid.getType()` | Clase | Rol |
|---------|---------------|-----------------|-------|-----|
| Lista de difusión clásica | `<id>@broadcast` | 3 | `C99P` | lista del dispositivo primario, los destinatarios reciben copias 1:1 |
| Difusión de estados | `status@broadcast` | 5 | `C199018dF` | publicaciones de estado, audiencia elegida por publicación |
| Difusión de ubicación | `location@broadcast` | 6 | `BOC` | existe en el modelo de JID; uso no rastreado (ubicación en vivo inferida por el nombre) |
| Pseudo usuario de estado propio | `status_me` (local) | 11 | `C0Dh` | alias solo local, no es un JID de red (rol inferido) |

Fuera de alcance: newsletters (`SendNewsletterStatusJob` es un job aparte), campañas e insights de Business, broadcasts del SO Android.

| Componente | Nombre en 2.26.41.6 | Rol |
|------------|---------------------|-----|
| Parser / helpers de JID | `C0DJ.A00` / `C0DZ.A0P`, `A0Q`, `A0h` | servidor `broadcast`: usuario `location` → `BOC`, `status` → `C199018dF`, otro → `C99P`; los helpers devuelven true para cualquier broadcast (3, 5, 6) / lista (3) / estado (5) |
| Asignador / gestor de listas | `C0YJ.A0E` / `A0K` (`BroadcastListManager`) | nuevo id de lista / agregar y quitar participantes |
| Filtro y migración a LID | `C70552yj` (`BroadcastListLidMigrationHelper`), `C0UV` (tarea de migración) | PN → LID |
| Gestor / store de participantes | `C22300su` (`A0j` agregar, `A0k` quitar), `C14850fN` (`ParticipantUserStore`) | compartido con los grupos |
| IQs de listas | `C18240lQ` (`BroadcastXmppMethods`), `AKU` (handler de resultado), `BroadcastListQuotaProtocol` + `C9EN` | obtener listas, eliminar lista, cuota |
| Cliente de cuota | `C720733k` (repositorio), `C2EX` (view model), `C74823Ej` (listener de mensajes) | límite mensual |
| Mutación app-state | `C224469lG` (dispatch), `C26057BNq` (`BusinessBroadcastListMutation`) | `business_broadcast_list` |
| Clonación al insertar | `C231399zG` (`BroadcastCloneOnInsertProcessor`), `AJO` | copias locales por destinatario |
| Ack / recibos | `C22500tF`, `C22790ti` (`MainMessageStore`), `C269411e` (`MessageStatusStore`) | ack del servidor, división de recibos |
| Cifrador / jobs | `F6P` (`E2eMessageEncryptor`), `SendE2EMessageJob`, `SendE2eStatusJob` | sender key, SKDM, construcción de la stanza |
| Verificador de entrada | `C34757F6a` (`CompanionSupportVerifier`) | descarta copias de listas en companions |
| Audiencia de estados | `C11550Zh` (`StatusInfoStore`), `C182877r0` (distribution info), `C23140uH` (`StatusParticipantUserManager`), `C1889082i` (`StatusCustomListStore`), `C23340ub` (configuración de bucketing) | modos de privacidad, listas, buckets |
| Sincronización de privacidad de estados | `C48386LBh` (`StatusPrivacySyncMutation`), `C49626LsR` (Wire `StatusPrivacyAction`), `M7H` (enum de modos) | acción app-state 44 |

---

## 2. Modelo de JID

### 2.1 Parseo (found)

| Regla | Valor |
|-------|-------|
| Servidor | `broadcast` |
| Usuario `status` / `location` | singletons `C199018dF` / `BOC` |
| Cualquier otro usuario | `C99P`: longitud 1..20, primer carácter `1`..`9`, resto `0`..`9`, de lo contrario se lanza `C09B` |

La regla de no empezar con cero se lee del constructor de `C99P` (smali compara con `0x31`/`0x39`, resto `0x30`..`0x39`). Una lista no es `g.us`, pero reutiliza la maquinaria de participantes de grupo (3.5).

### 2.2 Asignación (found, `C0YJ.A0E`)

El id es `System.currentTimeMillis() / 1000` seguido de `@broadcast`, incrementado en un segundo mientras exista localmente una lista con ese id. La unicidad se comprueba solo contra la lista de chats local; ninguna llamada al servidor precede a la asignación (no existe IQ de creación, 3.3). No se puede determinar estáticamente si el servidor acepta un id arbitrario.

---

## 3. Ciclo de vida de la lista

### 3.1 Creación (found, parcialmente inferred)

```
[Picker]  "New broadcast" (menu item hidden when BRD() = companion mode), max 256 selected
     ▼
createBroadcastList callback (C222519hZ):
     │   C0YJ.A0E()                                allocate <seconds>@broadcast
     │   A0K.A04(jid, users): C70552yj.A00 → LID filter ; C22300su.A0h → local participants ; contact entry (name "")
     ▼
compose flow opens; system message "You created broadcast list "X" with N recipients"
```

`A0K.A04` no emite ningún IQ ni mutación app-state (found). El primer evento visible para el servidor es el primer envío al JID de la lista (4.2); que el servidor derive el estado de la lista a partir de él es inferred. La misma asignación se reutiliza para las invitaciones a seguidores de newsletters (`userActionSendNewsletterFollowerInviteMessages`, found).

### 3.2 Límites de membresía y reglas de destinatarios

| Regla | Valor | Tier |
|-------|-------|------|
| Máx. de destinatarios | 256: `ContactPickerFragmentKt.A39` rechaza `selected.size() > 256` (`Broadcast to a maximum of %d people at a time`); límite del picker `min(256, groupLimit - 1)` | found |
| Origen de destinatarios | selector de contactos; texto de permiso `To create a broadcast … allow WhatsApp access to your contacts`; contactos bloqueados: `To add to broadcast list, unblock %s` | found |
| El receptor debe tener guardado al remitente | solo texto de UI (`Only contacts who have you in their address book will receive your broadcast messages.`); la aplicación de la regla es del lado del servidor | found (texto), unknown (aplicación) |
| Direccionamiento LID | `A0K.A01` siempre devuelve `lid`; los participantes PN sin mapeo a LID se descartan (`lid-broadcast-filtered-participants`) | found |
| Mapeo ausente al enviar | `missing_pn_lid_mapping_for_broadcast`: clon omitido, el cifrador lanza `E39(device, 4)` | found |
| Conjunto de participantes vacío | `saveGroupParticipants/broadcast_would_be_cleared`; con el flag **30111** (por defecto true) se conservan los participantes almacenados | found |

### 3.3 IQs del servidor (found)

Solo tres IQs tocan las listas. No existe IQ de creación ni de edición.

```xml
<!-- restore: BroadcastXmppMethods/sendGetBroadcastLists -->
<iq to="s.whatsapp.net" xmlns="w:b" type="get" id="…"><lists/></iq>
<iq type="result"><lists>
  <list id="1760000000@broadcast" name="Family">
    <recipient jid="<lid>@lid" pn_jid="<pn>@s.whatsapp.net" username="…"/>   <!-- pn_jid, username read for LID recipients -->
  </list>
</lists></iq>

<!-- delete: sendDeleteBroadcastList -->
<iq to="s.whatsapp.net" xmlns="w:b" type="set" id="…"><delete><list id="1760000000@broadcast"/></delete></iq>

<!-- quota (5.1) -->
<iq to="s.whatsapp.net" xmlns="w:b" smax_id="143" type="get" id="…"/>
```

Los tres usan un timeout de 32 s. `AKU` (resultado de get) crea, por cada `<list>` sin chat ni entrada de contacto local, el chat (`A0K.A00`, mensaje de sistema tipo 9) y una entrada de contacto, y almacena los mapas `pn_jid` y `username`. Delete lo envía `C18240lQ.A01` y le sigue un REMOVE de app-state (3.4).

Disparador de restauración (found): `RegistrationInitializer/shouldrefreshlists` fija el pref `refresh_broadcast_lists=true` y envía get-lists (junto con get-privacy-settings) tras el registro; `MessageHandlerCallback/ready` lo repite mientras el pref sea true; `AKU` lo limpia. Por tanto, el servidor persiste las listas por cuenta (found por implicación). Cómo se entera de una lista no es visible del lado del cliente (unknown, véase 3.1).

### 3.4 Mutación app-state (found)

| Elemento | Valor |
|----------|-------|
| Acción | `BusinessBroadcastListAction`, nombre de red `business_broadcast_list` (`EnumC24865AnN.A0H`, ordinal 62), campo **69** de `SyncActionValue`, colección `regular`, versión de API 7 |
| Índice | `["business_broadcast_list", "<list jid>"]` |
| Operación | SET al agregar, quitar, renombrar; REMOVE con `deleted=true`, participantes vacíos, nombre `""` al eliminar la lista (`A0T`, `syncBusinessBroadcastListRemoval`) |
| Gate | `C12440bB.A0b()` (syncd no bloqueado o companion-dirty); los hooks de Business (`storeForBroadcast`, `onAudienceChanged`, `getCustomAudienceFbidForBroadcast`) están ausentes en este APK |
| Llamadores | `A0K.A03` / `A05` (agregar / quitar), renombrado en `BroadcastListChatInfoActivity`, `C24085AaS` (conjunto de participantes) |
| Lado de aplicación | ningún handler referencia `EnumC24865AnN.A0H`; solo existen el escritor (`C26057BNq`) y el accesor de campo en `BD4`, por lo que el comportamiento de aplicación del consumidor es unknown |

| Campo | Número | Tipo | Valor / uso |
|-------|--------|------|-------------|
| `deleted` | **1** | bool | lista eliminada |
| `participants` | **2** | repeated `BroadcastListParticipant` | audiencia (`lid_jid` **1** obligatorio, `pn_jid` **2**) |
| `list_name` | **3** | string | asunto |
| `label_ids` | **4** | repeated string | audiencia por etiquetas (alternativa a participants, nunca ambos) |
| `audience_expression` | **5** | string | audiencia dinámica (Business) |
| `custom_audience_fbid` | **6** | string | solo Business |

Misma colección: `BusinessBroadcastCampaignAction` (81), `BusinessBroadcastInsightsAction` (82), `MarketingMessageBroadcastAction` (39); solo en enum `BusinessBroadcastAssociationAction` (59) y `BusinessBroadcastAction` (94). Conceptos básicos: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md).

### 3.5 Migración a LID, almacenamiento, companions

`BroadcastListLidMigrationTask` (`C0UV`) convierte cada lista de participantes PN a LID: un usync para los LID faltantes (el fallo se registra como `usync_failed`, la tarea continúa), luego `C70552yj.A03` elimina los participantes PN y agrega el conjunto LID en una sola transacción.

| Store | Contenido | Tier |
|-------|-----------|------|
| `chat` / `chat_view`, `jid.type = 3`, `subject`, `created_timestamp`, `hidden` | el chat de la lista (`C222989iV`) | found |
| `group_participant_user` (`group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `label`, `add_timestamp`), `group_participant_device` | destinatarios, compartido con los grupos | found |
| `wa_group_admin_settings` (`jid`, `addressing_mode`, `group_state`) | modo de direccionamiento por lista (la telemetría cuenta filas `@broadcast`) | found |
| columnas de `message` `broadcast`, `recipient_count`, `participant_hash`, `key_id`, `chat_row_id`, `from_me` | mensaje de lista y datos de ack | found |
| `message_broadcast_ephemeral` (`message_row_id`, `shared_secret`) | secreto por mensaje para mensajes temporales de listas | found |

Companions (found): los ítems de menú `New broadcast` / `Broadcast lists` solo se agregan cuando `BRD()` es false; `C34757F6a` lanza `E3A(415, "received peer broadcast message on companion-mode, dropping", 18)` ante una copia de lista de la propia cuenta que lleva `<participants>`; la acción 69 no tiene handler de aplicación.

---

## 4. Envío a una lista

### 4.1 Fan-out local (found, `C231399zG`)

```java
// A02(msg): msg.fromMe, not one of two excluded message classes, status 0 or 2 (or 4 with flag 26867)
msg.A0Z = true;                                   // message.broadcast = 1
for (recipient : msg.A0A())                       // recipient list stored on the FMessage
    normalized = lidMapper.A0C(recipient);        // null → missing_pn_lid_mapping_for_broadcast, skip
    store.add(cloneFactory.A00(msg, new C1ZA(normalized, msg.key.id, true)));   // own row in the recipient's 1:1 chat
```

| Propiedad | Valor |
|-----------|-------|
| Id de mensaje | idéntico para el mensaje de lista y cada clon (`key_id` copiado, solo cambia el chat) |
| Conteos | `recipient_count` (`FMessage.A06`) en la fila de la lista; el conteo de referencias del archivo multimedia aumenta según el número de clones |
| Duplicados | una `SQLiteConstraintException` sobre una clave de clon existente se registra y se omite |
| Mensajes temporales | el clon toma el ajuste por destinatario del mapa efímero (indexado por dispositivo primario del destinatario); filas de expiración en `message_ephemeral` |

### 4.2 Formato de red (found, parcialmente inferred)

Una stanza dirigida al JID de la lista (ejemplo, valores de atributos ilustrativos). El cifrado reutiliza la ruta de grupos (`F6P` está tipado sobre `AbstractC20660pZ`): un ciphertext con sender key más mensajes de distribución de sender key por dispositivo. Los conceptos básicos de sender key y sesión no se repiten aquí.

```xml
<message to="1760000000@broadcast" type="text" id="3EB0…" t="…" phash="2:AbCdEf==" addressing_mode="lid">
  <participants>
    <to jid="<recipient device jid>"><enc v="2" type="pkmsg|msg" …/></to>   <!-- SKDM wrapped pairwise -->
  </participants>
  <enc v="2" type="skmsg" …/>                                                <!-- message under the sender key -->
  <cap client_capping_ready="true|false"/>                                   <!-- flag 16656 only -->
</message>
```

| Atributo | Origen | Notas |
|----------|--------|-------|
| `to`, `type`, `id`, `t` | JID del chat (`C33150EcP.A07`), `AbstractC30999De0.A02`, `C1ZA.A01`, `originalTimestamp` | `to` es el JID de la lista (inferred del builder compartido); `t` solo cuando es distinto de cero |
| `phash` | `groupParticipantHash` | 4.3 |
| `bucketing` | `eva.A05` | `primcomp` cuando el flag **28183** y el número de participantes ≥ **28185** (512); las listas (≤ 256) quedan sin establecer en la práctica (inferred) |
| `addressing_mode` | `lid` | omitido para JIDs de tipo 28 |
| `participant`, `recipient`, `recipient_pn`, `peer_recipient_pn`, `peer_recipient_username` | campos del job | envíos peer / retry / DSM |
| `edit`, `expiration`, `device_fanout="false"`, `privacy_sensitive="1"` | campos del job | opcionales |

Los hijos provienen de contributors (`InterfaceC35538FaZ.ASY`, `processStanzaNodeParamsUsingNewFramework`). `F69` agrega `<cap client_capping_ready="…"/>` para chats de lista cuando el flag **16656** está activo; el valor es el flag **13537**.

| Paso | Detalle | Tier |
|------|---------|------|
| Dispositivos destinatarios | conjunto del gestor de participantes menos los tipos de dispositivo 26 / 27 (`F6P.A07`, dispositivos hosted inferidos); para chats de lista `AxolotlMultiDeviceSessionRequirement` agrega los dispositivos companion propios (`BPE`: usuario propio, no primario) al conjunto objetivo de SKDM | found / inferred |
| Nombre de sender key | (dirección del dispositivo propio, string `groupId` `A0J`); `A0J` se escribe en `SenderKeyDistributionMessage.groupId`; el estado `-1002` de `encryptForGroup` = sender key inválida, rotada | found |
| Blobs efímeros por destinatario | `F6P.A0A` (`buildBroadcastListEphemeralSettings`): para cada dispositivo destinatario ausente del mapa pairwise (companions propios omitidos) construye `EphemeralSetting(expiration or afterReadDuration, timestamp)` y lo cifra de forma nativa con el `shared_secret` del mensaje (`JniBridge.jvidispatchOOOOOOO`); un ajuste ausente lanza `E39(device, 4)`. El propósito (temporizadores por destinatario dentro de una sola stanza) es inferred | found / inferred |
| Dispositivos propios | mensaje envuelto en `DeviceSentMessage` con `destinationJid = list` y `phash` de los dispositivos destinatarios (`C33284Eea.A01`) | found |
| Tamaño | `BoundedStanzaSizeException` → `stanza-too-large` / `large payload` | found |

### 4.3 `phash` (found, `AbstractC44221r5`)

`<version>:` + base64 (`NO_WRAP`, padding conservado) de los primeros 6 bytes de SHA-256 sobre los dispositivos destinatarios ordenados. La versión `2:` hashea strings `user.0:device@server` (flag **16731** false, por defecto); la versión `3:` hashea los strings crudos del dispositivo (flag **16731** true). Se usa en stanzas de grupo, lista y estado.

### 4.4 Ack y recibos (found)

| Evento | Manejo |
|--------|--------|
| Ack del servidor | `C22500tF` → `C22790ti.A04`: para chats de lista (no estado) actualiza `message` donde `chat_row_id IN (list chat, every clone chat) AND from_me = 1 AND key_id = ?` con `status`, `receipt_server_timestamp`, `recipient_count`; recurre a un escaneo por `timestamp/from_me/key_id` (`UPDATE_RCV_BROADCAST_SERVER_SQL`, log `message-table-scan`) cuando la lista de destinatarios es más corta que `recipient_count` |
| Recibo del destinatario | `MessageStatusStore.splitStatusUpdateReceipts`: un recibo para la clave de la lista se mapea al clon `(normalized recipient, same id, fromMe)` y se aplica al clon (`broadcast-individual`) y al mensaje múltiple; se descartan los retrocesos de estado (`broadcast-statusdowngrade`); un clon desconocido registra `nosuchmessage for broadcast` |

La regla del estado resumen de la fila de la lista y lo que muestra el teléfono de un destinatario no están resueltos (unknown).

---

## 5. Límites y controles de abuso

### 5.1 Cuota mensual de difusión (found, ruta del consumidor)

```
iq get xmlns=w:b smax_id=143
  → <limits is_heavy_sender="true|false" messages_left="N" total_limit="M"/>
    <timeframe start_ts_s="…" reset_ts_s="…" end_ts_s="…"/>
```

Comprobaciones de rango del cliente: `messages_left` 0..300, `total_limit` 1..300, timestamps 2020-01-01..2100-01-01. Los códigos de error del IQ se mapean a resultados del cliente `400` → 3, `401` → 4, `403` → 5, `500` → 1, otro → 0, sin conexión o fallo de entrega → 2 (`consumer_broadcast_capping_iq_error_response`).

| Mecanismo | Detalle |
|-----------|---------|
| Caché | prefs `broadcast_quota_messages_left`, `_message_limit`, `_last_timestamp_fetched_ms`, `_heavy_sender`, `_start_timestamp`, `_end_timestamp`, `_reset_timestamp` |
| Refresco | cuando el tiempo desde la última obtención supera el flag **13818** minutos (por defecto 1440) o ahora ≥ `reset_ts_s` (la combinación está corrupta en la decompilación, OR inferred) |
| Decremento / incremento | `C74823Ej`: por cada mensaje de lista agregado marcado `broadcast` y que no esté en un conjunto exento de tipos de mensaje (`C2EX.A00`), por mensaje y no por destinatario; se incrementa de vuelta al eliminar mensajes de lista no enviados, con tope en `total_limit` |
| Bloqueo previo al envío | predicado en `C20M`: chat de lista y flags **16585** y **13537** y `messages_left == 0` → envío rechazado, bottom sheet `You've reached the broadcast limit for this month` |
| UI / telemetría | `Send up to %d broadcasts per month`, sheet de onboarding para heavy senders (`CappingBroadcastManager`); `wam_broadcast_list` (`blLimit`, `currentBlSends`, `numBlLists`, `broadcastListSize`) |

El valor del tope lo provee el servidor; en el cliente solo está la comprobación de rango. Los hooks del lado Business (`isSmbPremiumBroadcastCappingEnabled`) son stubs en este APK.

### 5.2 Bloqueos por advertencia de spam (found)

`SpamWarningActivity` recibe un código del servidor (`spam_warning_reason_key`), `expiry_in_seconds`, texto opcional del servidor y URL de FAQ. Códigos: **101** mensajes a personas que no tienen al remitente en su libreta de direcciones, **102** demasiados bloqueos, **103** grupos con personas que no tienen guardado al remitente, **104** el mismo mensaje a demasiadas personas, **106** demasiados mensajes a una lista de difusión; los demás muestran el bloqueo genérico por términos de servicio. Ruta de entrega y el resto de la superficie de bloqueos: [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md). Los umbrales son del lado del servidor (unknown).

### 5.3 Config 20278 y GAP

- La config **20278** existe solo como un string por defecto `{"max_messages": 10000, "farthest_time_days": 30}` en dos tablas de defaults. No existe ninguna otra referencia a `max_messages` / `farthest_time_days` en el código del consumidor, por lo que no se encontró ningún lector. No es el tope de listas del consumidor (5.1); su uso es unknown (default del lado Business).
- GAP (`com.whatsapp.gapenforcement`, flag **14837**, por defecto false) es del lado de recepción: `GapEnforcementTrigger.onMarketingMessageReceived` y `RulesManager` evalúan reglas de bandeja para hilos de mensajes de marketing (`parseMaxMmThreadsInTopInboxSize`, `parseNoConsecutiveInTopInboxSize`, `parseMinNUpdatedP`) y registran resultados de precisión; no se ejecuta en companions y no limita los envíos desde listas. La expansión del acrónimo no está en el APK (unknown).

---

## 6. status@broadcast

### 6.1 Pipeline de envío (found)

`SendE2eStatusJob` tiene un tipo (`EnumC32060Dzj`): `STATUS` 0 (la publicación, tabla `status`), `STATUS_ADD_ON` 1 (reacciones y otros add-ons, `status_add_on`), `STATUS_NOTIFY` 2 (notificaciones de respuesta / reenvío / mención, `status_notify`). La stanza usa el builder de atributos de 4.2 más contributors de `<meta>` (ejemplo, valores de atributos ilustrativos):

```xml
<message to="status@broadcast" type="media" id="3EB0…" phash="2:…" bucketing="manual" addressing_mode="lid">
  <participants><to jid="<device>"><enc v="2" type="pkmsg|msg"/></to>…</participants>
  <enc v="2" type="skmsg" bucket="f1"/>                      <!-- one per bucket when bucketed -->
  <meta status_setting="contacts" session_scope="status"/>
</message>
```

| Atributo | Valores aceptados (conjuntos de valores de stanza, `C9E2`) |
|----------|------------------------------------------------------------|
| `status_setting` | `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist` |
| `content_type` | `add_on`, `status_notify` |
| `message_association_type` | `av1_video_dual_upload`, `hd_image_dual_upload`, `hd_video_dual_upload`, `hevc_video_dual_upload` |
| `interaction_type` | `question`, `question_reshare` (con `parent_server_id`, `response_server_id`) |
| `bucketing` | `manual`, `primcomp`, `threebuckets` (`threebuckets` solo en el conjunto de valores) |

| Elemento | Detalle |
|----------|---------|
| Timeout de ack | 300000 ms (`no ack within 300000ms`) |
| Partes | las audiencias grandes se dividen: `status_send_part` (`status_row_id`, `part_code`, `is_first_part`, `device_count`, `state`, `sent_timestamp`, `ack_timestamp`, `error_code`, `stanza_devices_hash`); seguimiento de dispositivos en `status_receipt_device` (`uuid`, `receipt_device_jid`, `receipt_device_timestamp`, `primary_device_version`, `part_code`) |
| Estado de grupo | `buildGroupStatus called with non-PermanentGroupJid`; `is_group_status`; campos de Message 92 / 96 / 103 |
| Fallos de construcción | `StatusStanzaBuildFailureReason`: `MISSING_RETRY_CIPHERTEXT`, `TARGETS_UNRESOLVABLE`, `PART_ATTEMPT_PERSISTENCE_FAILED`, `CANONICAL_ACK_PENDING`, `EMPTY_FANOUT`, `NON_CURRENT_BATCH`, `MISSING_SENDER_KEY_CIPHERTEXT`, `UNKNOWN` |
| Fallos del job | `encryption_limit`, `out_of_memory`, `payload_too_large`, `stanza_error`, `stanza_too_large` (manejado cuando el flag **29113** está activo), `unrecoverable_error` |

### 6.2 Audiencia: modos de privacidad (found)

La audiencia se resuelve en el remitente y se expande a dispositivos destinatarios explícitos; el atributo `status_setting` solo etiqueta el modo. Estado local: `C11550Zh` (prefs `status_distribution`, `status_distribution_modes`, `status_white_list`, `status_black_list`).

| Modo local | Nombre | `status_setting` | `M7H` en red (app-state) |
|------------|--------|------------------|--------------------------|
| 0 | My contacts | `contacts` | `CONTACTS` 2 |
| 1 | Only share with | `allowlist` | `ALLOW_LIST` 0 |
| 2 | My contacts except | `denylist` | `DENY_LIST` 1 |
| 3 | fallback sin establecer de `C182877r0.A01()`; rechazado por la mutación de sync (`StatusPrivacySyncMutation invalid status setting`) | | |
| 4 | audiencia personalizada / amigos cercanos | `customlist` / `closefriends` (inferred) | `CUSTOM_LIST` 4 (`CLOSE_FRIENDS` 3 existe en el enum, no se produce) |

Mapeo local a red (found, `C48386LBh.A04`): 1 → 0, 2 → 1, 4 → 4, otro → 2. El job de envío también registra los nombres de modo 0..2 como `contacts` / `allowlist` / `denylist`.

Las listas de privacidad del servidor usan el IQ `privacy`, categoría `status` (nombre de categoría de `AboutStatusPrivacyActivity`):

```xml
<iq to="s.whatsapp.net" xmlns="privacy" type="get" id="…">
  <privacy addressing_mode="lid"><list name="status" value="contact_allowlist|contact_blacklist" dhash="…"/></privacy>
</iq>
<iq xmlns="privacy" type="set"><privacy><category name="status" value="contacts|contact_blacklist|contact_allowlist"/></privacy></iq>
```

(`AbstractC230749y7.A02`, `C228009tS`, `C18260lS.A0P`; get es MEX / SMAX / shadow según el flag **23463**, set vía MEX cuando **23639**, de lo contrario SMAX.)

### 6.3 Audiencias personalizadas y amigos cercanos (found)

Strings de UI: `New: Close friends`, `People you include see a purple ring on your status`, `Create audience`, `Choose name & emoji`.

| Elemento | Valor |
|----------|-------|
| Tabla `status_privacy_custom_list` | `row_id` (PK), `list_id` (único), `name`, `emoji`, `is_selected` (por defecto 0), `member_jids`, `source_group_jids`, `allow_list_selected`; conservada tanto en el message store como en el status store (`*_MSGSTORE_DB`, `*_STATUS_DB`) |
| App-state | `status_privacy` (ordinal 38, `regular_high`, campo **44**); `StatusPrivacyAction`: `mode` **1**, `user_jid` **2**, `shareToFB` **3**, `shareToIG` **4**, `custom_lists` **5**, `modes` **6**; `StatusCustomList`: `list_id` **1**, `name` **2**, `emoji` **3**, `is_selected` **4**, `user_jid` **5** |
| Registro por publicación | `status_message_info`: `status_distribution_mode`, `selected_audience_list`, `audience_type`, `status_audience_custom_list_name`, `_emoji` |
| Validación | `StatusParticipantUserManager/validateAudience` (incluye una comprobación `HAS_STATUS_AUDIENCE` sobre `wa_contacts`), `StatusEmptyAudienceGuard` en los composers |

Relacionado: `userStatusMute` (ordinal 23, campo 29, `muted`). Los múltiples modos simultáneos requieren el flag **28731**, el store de listas personalizadas **27031** (ambos false por defecto; los helpers de status-config `A0F` / `A0I` también condicionan esto, sin resolver).

### 6.4 Buckets manuales de sender key (found)

| Elemento | Detalle |
|----------|---------|
| Tabla `manual_user_group_bucket` | `row_id`, `user_jid_row_id`, `multi_participant_jid_row_id`, `status_audience`, `bucket`; índice único sobre usuario + grupo |
| Nombres de audiencia / prefijos de bucket | `contacts` → `c`, `close_friends` → `f`, `allow_list` → `a`, `close_friends:<id>` → prefijo derivado; otros nombres lanzan `Unknown manual SKB audience name` |
| Store / planificación | `ManualBucketStore/assignUsersToBuckets`, `deleteRowsForBuckets`, `getHoldersByBucketForGroup`; `ManualBucketingUtils/planSend`, `trimToEncBudget`; `SenderKeyBucketingRollback/cleanupBucketedState` |
| Flags | **28184** + tope de rollout **34545** (0 = todos) habilitan el bucketing manual para estados (`C23340ub.A01`) |

### 6.5 Respuesta, reacción, mención, notificación (found)

| Interacción | Mecanismo |
|-------------|-----------|
| Respuesta | mensaje 1:1 normal que cita el estado (`status_reply`: `status_row_id`, `ref_id`, `reply_timestamp`); `Message.statusQuotedMessage` (campo **109**) para respuestas a preguntas |
| Reacción / add-on | tipo de job `STATUS_ADD_ON`; `status_add_on` (`status_row_id`, `type`, `uuid`, `sender_user_jid`, `state`, `sender_timestamp`, `is_revoked`, `content_proto`, `secret`); gates por publicación `cannot_receive_reactions`, `can_receive_multi_reactions` |
| Mención | `status_message_info.is_mentioned`, `status_mentions`, `status_mention_source`; `Message.statusMentionMessage` (campo **87**) es un wrapper de un solo campo (`message` **1**) que se desenvuelve como `viewOnceMessage` (`C35228FOg`); semántica adicional inferred |
| Notificación | `Message.statusNotificationMessage` (campo **98**): `responseMessageKey` **1**, `originalMessageKey` **2**, `type` **3** (1 agrega el tuyo, 2 reenvío, 3 reenvío de respuesta a pregunta, 4 respuesta a estado de grupo); almacenado en `status_notify` |
| Campos relacionados | `groupStatusMentionMessage` **92**, `groupStatusMessage` **96**, `groupStatusMessageV2` **103**, `statusQuestionAnswerMessage` **105**, `statusStickerInteractionMessage` **110** |

### 6.6 Almacenamiento de estados (found)

| Tabla | Columnas clave |
|-------|----------------|
| `status` (status store) | `uuid`, `sender_user_jid`, `status_info_row_id`, `type`, `timestamp`, `server_receipt_timestamp`, `state`, `secret`, `content_proto`, `origin`, `flags`, `audience_type`, `stanza_xml`, `batch_state` |
| `status` (message store, resumen legacy), `status_info` | `jid_row_id` / `chat_jid`, `unseen_count` / `unread_count`, `total_count`, `unread_count_close_friends` |
| `status_message_info` | `message_row_id`, `status_distribution_mode` (3 cuando no está establecido), gates de mención / reacción / reenvío, `is_group_status`, `ranking_version`, columnas de audiencia (6.3) |
| `status_send_part`, `status_receipt_device`, `manual_user_group_bucket` | estado de envío (6.1, 6.4) |

Las dos tablas llamadas `status` tienen columnas disjuntas y viven en bases de datos distintas (inferred a partir de las etiquetas `MSGSTORE_DB` / `STATUS_DB`). Otras tablas (`status_media_link`, `status_seen_receipt`, `status_ranking*`, `status_interactions*`) se listan solo por nombre.

---

## 7. Feature flags

Ids tal como se leen en los puntos de llamada; valores por defecto de las tablas de defaults compiladas.

| ID | Por defecto | Controla |
|----|-------------|----------|
| **13537** | false | capping de difusión del consumidor: inicio de listas, obtención / decremento de cuota, valor de `client_capping_ready` |
| **16585** | true | bloquear envíos a listas cuando `messages_left == 0` |
| **16656** | false | agrega `<cap client_capping_ready/>` a las stanzas de listas |
| **13818** | 1440 | intervalo de refresco de cuota (minutos) |
| **15515** | true | helper de UI de capping (`C33z.A08`, con 13537) |
| **19790** | false | cuando es true, la clonación al insertar omite el mapeo de mensajes citados |
| **26867** | true | rama de clonación al insertar para mensajes enviados con status 4 (significado sin resolver) |
| **30111** | true | conservar los participantes almacenados de la lista cuando un guardado los vaciaría |
| **16731** | false | variante de `phash` `3:` en lugar de `2:` |
| **28183** / **28184** | false / false | bucketing `primcomp` maestro / bucketing manual de estados |
| **28185** / **28199** / **34545** | 512 / 2 / 0 | umbral de participantes del bucketing / segundo entero (sin resolver) / tope de rollout |
| **28731** / **27031** | false / false | múltiples modos de estado / store de listas personalizadas |
| **29113** | false | manejo de stanza-too-large para estados |
| **23463** / **23639** / **23874** | 0 / false / false | protocolo de get de privacidad (1 MEX, 2 shadow, otro SMAX) / set de privacidad vía MEX / ruta de obtención de listas de privacidad |
| **14837** | false | aplicación de GAP |
| **20278** (string) | `{"max_messages": 10000, "farthest_time_days": 30}` | default del límite de difusión de Business, sin lector en el consumidor |

---

## 8. Baileys (`baron-baileys-v2`, verificado contra su código fuente)

| Área | Implementación | Veredicto frente a 2.26.41.6 |
|------|----------------|------------------------------|
| Envío de estados | `messages-send.js`: `isStatus`, `statusJidList` agregado a la lista de participantes, `<meta status_setting session_scope="status">` | coincide con 6.1 / 6.2; `statusPrivacy` no se valida (válidos: `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist`) |
| Escala de audiencia | `statusJidList` explícito, sin buckets, sin atributo `bucketing` | las audiencias grandes chocan con los límites de la stanza (6.1) |
| Eliminar lista | `deleteBroadcastList`: `w:b` set, `<delete><list id/></delete>` | coincide con 3.3 |
| Cuota | `fetchBroadcastListQuota`: `xmlns="w:biz"` con hijo `<broadcast_list_quota/>` | la solicitud no coincide (`w:b`, `smax_id=143`, sin hijo); el parseo de la respuesta coincide |
| Obtener listas / app-state / envío a lista | no implementado / `businessBroadcastListAction` emitido como `settings.update` / `isJidBroadcast` solo para decodificación | ver abajo |

| Síntoma | Causa | Solución |
|---------|-------|----------|
| envío a lista clásica descartado o rechazado | las listas son estado del dispositivo primario: los companions ocultan la función, descartan copias de listas de la propia cuenta con `participants` (415), no existe IQ de creación | no apuntar a JIDs de lista desde un companion; enviar mensajes 1:1 por destinatario o usar `status@broadcast` con `statusJidList` |
| destinatarios no resolubles | no hay consulta de miembros de listas en companions; los participantes están direccionados por LID y filtrados por mapeo | resolver los LID primero mediante usync |
| errores en la solicitud de cuota | namespace incorrecto | `xmlns="w:b"`, `smax_id` 143, `type="get"`, `to="s.whatsapp.net"` |

Los envíos 1:1 separados son compatibles a nivel de transporte, pero no son una lista clásica (sin chat de lista, id compartido ni cuota).

---

## 9. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `missing_pn_lid_mapping_for_broadcast`, `lid-broadcast-filtered-participants` | el PN del destinatario no tiene mapeo a LID | obtener los LID (usync) antes de agregar o enviar |
| 415 `received peer broadcast message on companion-mode` | copia de lista con `participants` en un companion | esperado, los companions no procesan envíos de listas |
| envío bloqueado, sheet de límite | `messages_left == 0` con 13537 y 16585 | esperar a `reset_ts_s`, eliminar mensajes de lista no enviados |
| código de bloqueo 106 | demasiados mensajes a una lista de difusión | esperar `expiry_in_seconds` |
| `broadcast_would_be_cleared` | guardado de participantes con un conjunto vacío | el flag 30111 conserva los participantes |
| `EMPTY_FANOUT` | la audiencia se resolvió a cero dispositivos | corregir la audiencia, `StatusEmptyAudienceGuard` debería bloquear antes |
| `stanza_too_large`, `payload_too_large` | demasiados dispositivos o payload | partes / buckets (6.1, 6.4), flag 29113 |

---

## 10. Distinciones clave

| No confundir | Diferencia |
|--------------|------------|
| Lista (tipo 3) vs `status@broadcast` (tipo 5) | lista: destinatarios almacenados, clones por destinatario, cuota mensual; estado: audiencia por publicación, sin clones, tablas propias |
| Lista vs grupo | mismo store de participantes y ruta de sender key; la lista es solo del primario, los destinatarios no son miembros y ven chats 1:1 |
| Listas `w:b` del servidor vs acción app-state 69 | `w:b` restaura las listas tras el registro; la acción 69 se escribe para sync y no tiene handler de aplicación en el consumidor |
| Cuota (`w:b` smax 143, ≤ 300) vs config 20278 (10,000 / 30 días) | la cuota la provee el servidor y se aplica en la UI; 20278 no tiene lector en el consumidor |
| Cuota vs código de bloqueo 106 vs GAP | tope blando con UI / bloqueo temporal emitido por el servidor / reglas de bandeja del lado de recepción |
| IQ `privacy` vs audiencias personalizadas | el IQ contiene tres modos del servidor; las listas personalizadas y los amigos cercanos son locales más la acción app-state 44 |

---

## 11. Flujo completo

```
[User]  New broadcast → select ≤ 256 contacts
     ▼
[Client]  C0YJ.A0E → <seconds>@broadcast ; A0K.A04 → LID filter, group_participant_user rows
     │     send → message.broadcast = 1 ; C231399zG clones into each recipient chat (same key id)
     │     quota gate: 13537 + 16585, messages_left > 0
     ▼
[SendE2EMessageJob]  F6P: skmsg + SKDM per device (pkmsg/msg) + ephemeral blobs ; DSM to own devices (phash)
     ▼
<message to="<id>@broadcast" phash id><participants>…</participants><enc type="skmsg"/><cap/></message>
     ▼
[WA Server]  (not observed) fan-out, ack
     ▼
ack → C22500tF updates list row + all clones ; receipts → splitStatusUpdateReceipts ; quota decremented on add

[User]  status: choose audience (contacts / allow / deny / close friends / custom)
     ▼
[Client]  validateAudience → StatusEmptyAudienceGuard ; users → LID → devices ; buckets c / f / a when 28184 on
     ▼
[SendE2eStatusJob]  type STATUS ; status_send_part rows ; sender key per bucket
     ▼
<message to="status@broadcast" phash bucketing><participants>…</participants><enc type="skmsg" bucket/><meta status_setting session_scope/></message>
     ▼
[WA Server]  (not observed) ack within 300 s ; viewers reply / react
     ▼
status_add_on / status_notify / status_reply rows ; status_receipt_device bookkeeping
```

---

## 12. Incógnitas

| Elemento | Estado |
|----------|--------|
| Cómo registra el servidor una lista (solo existen los IQs get / delete / quota) | registro en el momento del envío inferred |
| Regla del servidor de que los destinatarios deben tener guardado al remitente; valores de tamaño de lista y cuota | del lado del servidor (solo texto de UI y comprobaciones de rango) |
| Comportamiento de aplicación en el consumidor de la acción app-state 69 | no se encontró handler |
| Qué reciben los destinatarios de un mensaje de lista; regla de recibo resumen de la fila de la lista | no visible desde el remitente |
| Combinación de refresco de cuota, conjunto exento de tipos de mensaje | decompilación corrupta / no rastreado |
| Modo de estado local 3, `threebuckets`, flags 28199, 26867, 15515, status-config `A0F` / `A0I` | sin resolver |
| Uso de `location@broadcast`; expansión de "GAP" | no rastreado / no está en el APK |
| Tráfico | nada capturado |
