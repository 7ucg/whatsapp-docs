<!-- src-sha1: 27b3b625c1ca67d873007881de02f13ba8cbf277 -->
# WhatsApp Reportes — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** Reportes de usuario/contacto, grupo, canal, estado, llamada y mensaje — stanzas SMAX `spam`, `spam_list`, tipos de reporte, puntos de entrada `spam_flow`, reporting tokens, subida de contenido, UI de reportar/bloquear, report-to-admin, stanza de bloqueo y listas de motivos, errores del servidor, señales de abuso del lado del cliente, Baileys

---

## 1. Qué es un reporte (técnicamente)

Un reporte es un IQ `set` a `s.whatsapp.net` en el namespace `spam`. Lleva un nodo `spam_list` (entidad reportada, mensajes reportados, punto de entrada, contexto de business discovery). El cliente vuelve a serializar los mensajes reportados como protobuf en texto plano y los sube junto con un reporting token y la clave que lo verifica. El bloqueo es un stanza aparte (`blocklist`). Report-to-admin es un tercer stanza, sin relación (`w:g2`).

Todas las afirmaciones son análisis estático del APK decompilado. Nivel: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto. Nada de esto se capturó en la red.

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Constructor de IQ (multipropósito, `$t` selecciona la forma) | `C9EN` | construye todos los IQ de reporte (tipos 0, 18-23) y muchos IQ no relacionados |
| Nodo de motivo/punto de entrada | `C9E2` | `spam_list` con `spam_flow`, `wi_trace_id`, `is_known_chat`, ... (`xmlns="spam"`) |
| Hijo de configuración de grupo | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| Envoltorio de contenido | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Nodos varios | `C31084Dfc`, `C31085Dfd` | flags (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Serializador ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, ensamblado del token |
| SMAX manager | `SpamRPCManager` | `A01`-`A06`, uno por tipo de reporte (nombre de paquete sin ofuscar) |
| Repo | `SpamReportRepo` | enruta por clase de JID, efectos secundarios locales |
| Wrappers RPC | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | paquete `com.whatsapp.reportinfra.rpc` |
| Lista blanca de origen | `C9ZJ` | valida el punto de entrada (78 valores) |
| UI | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | diálogo de reporte, bloqueo/salida opcional |
| Ejecutor de bloqueo | `C227489sZ` → `C34631Yx` | IQ `blocklist` |
| Report-to-admin | `RtaXmppClient` | cola de reportes `w:g2` |
| Token store | `C23070uA` | tablas `reporting_info`, `reporting_info_content` |

Los nombres difieren por build; cada nombre ofuscado anterior se resolvió en 2.26.41.6 a partir de strings estables (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`).

---

## 2. Tipos de reporte

### 2.1 Enrutamiento (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` se ramifica según la clase del JID:

| JID reportado | Clase RPC | `SpamRPCManager` | Builder `$t` | Clase de respuesta | Etiqueta de log |
|--------------|-----------|------------------|--------------|----------------|-----------|
| objeto de estado seleccionado (`AbstractC31014DeU` no nulo) en un JID de newsletter | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| usuario (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| grupo | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| objeto de estado seleccionado en cualquier otro JID, o JID de estado con una lista de mensajes | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| newsletter/canal | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| id de evento (string) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| cualquier otro | ninguna | ninguno | ninguno | ninguna | `SpamReportRepo: unrecognized jid` lanzado, devuelto como falla |
| chat de bot | ninguna (ver 3.3) | ninguno | ninguno | ninguna | `C214999If` |

Otras formas de `C9EN` que no son reportes de spam: `$t=0` reporte a admins y `$t=1` alternar configuración de grupo (sección 9), `$t=2` sugerencias de subgrupos, `$t=24/25/26` nodos `status`. El RPC de evento se llama desde lambdas de corrutina (`AYs`, `Aaa`); la UI de origen es unknown (existen los puntos de entrada de evento `event_home_report` / `event_info_report`, por lo que los reportes de evento son inferred).

### 2.2 Los reportes de llamada son reportes de usuario (found)

`SpamReportRepo.triggerReportCallNonSuspend` (origen `call_spam_dialog_report`) llama a `IndividualSpamReportRpc.A00` sin `jid` reportado, sin mensajes y con un ítem de llamada. El ítem de llamada (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` incluye `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` y errores fatales de códec. El flag **36386** elige la forma del JID propio en `to` (`CUC()` vs `Ask()`, inferred LID vs PN). Un reporte de usuario desde la UI con `shouldIncludeCallLogsInReport` agrega hasta 5 ítems de registro de llamadas (`C16430i1.A0B(jid, 5)`).

---

## 3. Flujo del cliente

### 3.1 Diálogo

`ReportSpamDialogFragment` (diálogo inferior). Argumentos del fragment (found): `flow` (la cadena del punto de entrada, se convierte en `spam_flow`), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` carga el estado del diálogo.

Al confirmar, se ejecuta `reportAsSpam$1`:

1. Chat de bot: se omite el RPC (3.3). En otro caso, `SpamReportRepo.A02(...)` con el mensaje seleccionado en una lista de un elemento (o ninguno).
2. El éxito trae un id de reporte opcional; el error muestra el toast `str3bf8` (o `C227489sZ.A00`, log `spamreportmanager/spam/report/no-network-cannot-report`). Se llena WAM `wam_spam_report_perf` (11.3).
3. Acción extra opcional `triggerExtraAction$2` (3.2), diálogo de finalización desde `H2U` (10.2), escrituras locales (3.3).

### 3.2 Solo reportar vs reportar + acción extra (found)

La casilla se mapea a la cadena `report` (sin marcar) o `report_block` (marcada), usada para analítica (`asd.BaC` vs `BaD`) y para el toast posterior al reporte. La acción extra difiere según el destino:

| Destino | Acción extra al estar marcada |
|--------|--------------------------|
| usuario | bloqueo mediante `C227489sZ.A01` → IQ `blocklist` de `C34631Yx` (sección 8), motivo de bloqueo `null`, punto de entrada = `flow`, `deleteChat` = arg `shouldDeleteChatOnBlock` |
| grupo | tarea de salir del grupo (`C98C` / `C9CI`, ejecutada con el JID del grupo; semántica de salida inferred) |
| canal | oculta localmente el canal reportado (`NewsletterReportCompletionListener`, flag **25218**), luego el flujo de salir/dejar de seguir el newsletter |

El IQ de reporte se envía primero; el bloqueo/salida se ejecuta después de que el RPC retorna, sin importar su resultado (inferred a partir del flujo de control, no hay verificación de éxito antes de `triggerExtraAction$2`).

### 3.3 Chats de bot y efectos locales (found)

Los chats de bot omiten `SpamReportRepo`: el cliente llama a `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) y lo trata como éxito (`C214999If`); la forma en la red es unknown. Para otros chats, `C24120Ab1` case 4 hace:

| Paso | Efecto |
|------|--------|
| ningún mensaje seleccionado | recopila los últimos **5** mensajes del chat (`C14680f4.A01(..., 5, true)`; filas de tipo sistema excluidas, sin filtro `from_me` en esta variante) como contenido reportado |
| chat de usuario | log local `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; el flag **20085** condiciona `H0J.A00(jid, ...)` (propósito unknown) |
| después del RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, sin verificación del resultado del RPC en el flujo visible |

---

## 4. Envoltorio del stanza y namespace

### 4.1 El nodo de motivo se fusiona en el IQ (found)

Los RPC no emiten dos nodos `spam_list` hermanos. El `spam_list` principal (jid, mensajes) y el nodo de motivo `C9E2` (un fragmento `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>`) se combinan con `C10340Uk.A04`, que fusiona atributos e hijos del mismo nombre (valores de atributo en conflicto o conteos de hijos distintos abortan la fusión). Resultado:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Evidencia: los ctors de `C9EN` para 18-23 llaman a `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`; `C9E2` case 5 construye `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. El `id` del IQ viene de `MessageClientSmaxWrapper.A01()` (`n<hex counter>`, `C10140Tq.A0H`). Timeout de envío de 32000 ms (`A0F(node, id, cont, type, 32000, ...)`); una respuesta nula (timeout/falla de entrega) se convierte en `C216549Uq`.

Los tipos 0 y 1 fijan `xmlns="w:g2"` y `to=<group>` literalmente; los tipos 18-23 construyen `<iq type="set">` y dependen de la fusión para `to` y `xmlns`. El id de tipo pasado al emisor es **98** (grupo, newsletter, evento) y **385** (report-to-admin).

### 4.2 Hermanos opcionales fusionados en `spam_list`

| Nodo/attr | Fuente | Condición | Nivel |
|-----------|--------|------|------|
| `spam_flow` | arg `flow` normalizado por `C9ZJ` | siempre | found |
| `wi_trace_id` (exactamente 24 caracteres) | `$wiTraceId` de `reportAsSpam$1` | opcional | found; origen del valor unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | flag **22256**; usuario: verificación de libreta de direcciones, grupo: verificación de pertenencia al grupo | found |
| hijo `biz_opt_out` | `C33446EhE.A07` | existe un registro de business discovery | found (ver 8.3) |

---

## 5. Stanzas por tipo

`from`/`to` de un ítem `<message>`: para la ruta de usuario, el nodo anónimo `C9E4` fija `to=<jid>` cuando el mensaje es saliente (`key.fromMe`) y `from=<jid>` en caso contrario. Los conteos son límites del builder (`AbstractC10350Ul.A07`).

### 5.1 Usuario (tipo 20)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<userJid>" spam_flow="chat" wi_trace_id="...">   <!-- jid: UserJid or interop jid (C99O) -->
    <message from|to="<userJid>" t id deleted_reason>              <!-- 0..210 items -->
      <raw v="2" local_message_type="<int>" mediatype="<enum>"><proto bytes></raw>
      <content_validation type="e2e_proto_message|mms_retry|plaintext_v3">
        <reporting_token v="<n>"><tag, min 6 bytes></reporting_token>
        <reporting_token_key><key, 16-32 bytes></reporting_token_key>
      </content_validation>
    </message>
    <call .../>                                                    <!-- 0..5 items, section 2.2 -->
    <extension_screen extension_id session_id t name entry_point>  <!-- 0..5, business Flows context (A0B), data child -->
    <biz_opt_out business_discovery_timestamp business_discovery_id business_discovery_entry_point/>
  </spam_list>
</iq>
```

El builder toma tres listas de ítems con topes de 210 (mensajes), 5 (ítems de llamada), 5 (ítems de business-flow sin mensaje, `C33446EhE.A0B`: las últimas 5 entradas del almacén por negocio `messageless_flow_ids_per_business_<jid>`, nodo `extension_screen`). `jid` se valida solo contra `UserJid` y `C99O`; no hay `subject` en esta ruta.

### 5.2 Grupo (tipo 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` es **el usuario que agregó al reportante al grupo**, no el reportante. Se lee del mensaje de sistema local ("me joined") mediante el SQL `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`). Opcional. (found)
- `subject` es el nombre para mostrar del grupo tomado del registro de contacto (`C06290Dn.A07().A00.A0b`; significado del campo inferred), cadena vacía `""` para grupos padre de comunidad o cuando no existe registro (`Voip.REJECT_REASON_DECLINED` es `""`). No es un motivo. Límite de longitud 0..65536. (found)
- Una cuarta lista en el ctor lanza excepción (`getNode`) si no está vacía; el RPC pasa una lista vacía.

### 5.3 Newsletter (tipo 21) y publicación de estado (tipo 22)

```xml
<spam_list jid="<newsletterJid>" subject="<channel name or ''>" spam_flow="newsletter_info_report">
  <message from="<newsletterJid>">...</message>        <!-- 0..65 -->
</spam_list>
<spam_list jid="<statusPosterJid>" spam_flow="status_post_report">
  <message from="<posterJid>">...</message>           <!-- 1..2 items, only the first selected status is passed -->
  <biz_opt_out .../>                                   <!-- optional -->
</spam_list>
```

El `subject` del newsletter = nombre del canal (`C2130898y.A0j`), `""` si se desconoce (found). Los reportes de estado usan sus propias tablas de tokens `status_reporting_info` / `status_reporting_content`.

### 5.4 Estado de canal V2 (tipo 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

El estado se identifica por `server_id` + marca de tiempo, sin contenido subido. El contenido del hijo `status` (`InterfaceC35700FdB`) no está resuelto.

### 5.5 Evento (tipo 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`, sin `wi_trace_id` (ruta `C9E2(String)` de un argumento). Mensaje a admins (tipo 0): sección 9.1.

---

## 6. Contenido reportado y tokens

### 6.1 Qué se sube (found)

`C33446EhE.A0A(fmsg, entryPoint)` construye un ítem de mensaje por cada mensaje reportado:

| Parte | Detalle |
|------|--------|
| attrs de `<message>` | `t` (marca de tiempo del mensaje, 0..2^53), `id` (id del stanza), jid `from`/`to`, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | protobuf `Message` re-serializado (`C30628DTw` con `MessageContextInfo` `C30624DTs`); `local_message_type` = entero del tipo de mensaje interno |
| `<content_validation>` | token + clave (6.2) |
| meta flags | `<edit v="1">` (editado), `<multicast/>` (flag de broadcast 64), `<url_number/>` (flag 4), `<url_text/>` (flag 2), id de plantilla, `hsm` tid, `iab reported_link`, `original_sender` / `group_history_sender`, variantes de pago `futureproof`/`request`/`send` (`pay`), `reported_push_name` |
| hijo `<reporting>` | flag **5718**: construido a partir de las filas `reporting_info` del mensaje (`C23070uA.A03`), hasta 1000 entradas (`C31085Dfd` case 28); esquema por entrada no leído por completo |
| portadores alternativos | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 valores, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

Mensajes de plantilla OTP: el placeholder `<code>` en los títulos de botones se reemplaza por el código real antes de la serialización (`AbstractC32303E8u.A00`). View-once: cuando el mensaje es view-once y ya fue abierto/expiró y el origen no es `media_viewer` / `view_once_viewer`, `A06` es true y se omite el bloque de serialización. Si el ítem entonces lleva un `raw` vacío o ausente es inferred (declaración no inicializada en la decompilación).

Este stanza no vuelve a subir los archivos multimedia; el mensaje serializado lleva las referencias al medio (inferred; no se encontró ninguna llamada de subida). El stanza contiene el proto en texto plano y la clave juntos, así que el servidor puede leer el contenido: nodos **found**, legibilidad **inferred**.

### 6.2 Reporting token y clave (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

Ensamblado en `C33446EhE.A03` a partir de la fila almacenada (`C34539Ez0`): bytes del token (`A05`), versión (`A02`), id del stanza (`A03`), clave (`A07`). Si falta la clave se vuelve a derivar: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → nativo `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (id de caso de uso **5**; los chats que no son de usuario pasan por variantes de `JniBridge`). Si tanto la clave como un token de 6 bytes están ausentes/en cero, el cliente registra `ReportingToken/MissingFkAtReport` y usa una clave de 32 bytes toda en ceros. Un token ausente devuelve `null` (`ReportingToken is null`, el ítem no tiene `content_validation`).

### 6.3 Ciclo de vida del token (found salvo que se indique)

| Etapa | Detalle |
|-------|--------|
| Mensaje saliente | builder `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Token = primeros 16 bytes de `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = proto del mensaje con filtrado de campos dependiente de la versión (`A07`, elimina subcampos seleccionados del campo 35; lectura inferred). Llamadores del builder no rastreados |
| Compartir historial de grupo | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): para mensajes de tipo 117, `<reporting>` con un hijo por entrada (attr `id`, hijo `<reporting_token v>`) |
| Mensaje entrante | hijo del stanza `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>` parseado por `C34764F6h` / `C1S0`, flag **5718**; tag y token son ambos opcionales, el tag es obligatorio |
| Almacenamiento | tablas `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) y `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`); `message_conditional_reveal.reporting_token_info` (blob); `group_history_share_reporting_info`; `status_reporting_info` |
| Historial | `WebMessageInfo.reportingTokenInfo` campo **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; flag **6578** |
| Limpieza | filas `reporting_info*` eliminadas cuando `receive_timestamp` es anterior a un corte (`FP7` case 6); valor del corte no resuelto |
| Nodo de validación alternativo | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

Quién emite `reporting_tag` y cómo el servidor verifica el token: del lado del servidor, unknown. El emparejamiento (tag en el stanza, token+clave en el reporte) es inferred.

---

## 7. Puntos de entrada `spam_flow`

97 valores (found, `C9E2` case 5, orden = orden del array). El arg `flow` se pasa por `C9ZJ.A00`, que acepta **78** de ellos y lanza `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` en caso contrario. Los seis wrappers RPC lo llaman, y `SpamReportRepo.A02` captura la excepción y devuelve una falla (error del lado del cliente, no se envía stanza). Los 78 son un subconjunto estricto de los 97. Los 19 valores rechazados: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. Probablemente son orígenes solo de bloqueo o de otros RPC (inferred). `channel_status_report` está en el enum pero es rechazado por `C9ZJ`; qué flujo pasa el llamador del estado de canal es unknown.

| Superficie | Valores |
|---------|--------|
| Chat / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Banners de spam | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| Tarjetas de seguridad FMX | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| Alertas de estafa en el dispositivo | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Grupo | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Llamadas | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Canales / estado / eventos | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Business | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

La elección entre `*_suspicious` y la variante simple para las tarjetas FMX se hace en `C230769yA.A05` a partir de `A0D(userJid)` (contacto conocido o no); se infiere que ese predicado es una verificación de libreta de direcciones. Las variantes `server_flagged` se eligen según el tipo de tarjeta; de dónde viene el flag del servidor es unknown.

`wi_trace_id`: atributo opcional de 24 caracteres, pasado tal cual desde el llamador; su generador no se encontró (unknown). También es un campo de WAM `wam_spam_report_perf` (11.3).

---

## 8. Bloqueo, motivos y contexto de business

### 8.1 IQ de bloqueo (found, zona de `C34631Yx.A0M`)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` y `entry_point` solo se emiten para `action="block"`. `jid` se elige entre las formas PN y LID mediante una verificación de configuración (rama `zA02`; regla exacta no leída por completo); en un bloqueo, el identificador extra es uno de `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. Timeout 20000 ms. Los puntos de entrada que empiezan con `odml_scam_alert_*` se reescriben a `1_1_spam_banner_block` (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). Los chats PSA usan un IQ distinto (`xmlns="w:comms:chat"`, `<blocking action>`). Obtención: `type="get"`, `<item dhash>` opcional.

### 8.2 Motivos de bloqueo (found)

String hardcodeado → int local en `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, otro = 0. `RunnableC40792Hpk` mapea los mismos strings a un segundo conjunto de códigos. Estos ints alimentan llamadas de log locales; si llegan a un servidor es unknown.

Hoja de bloqueo de business (`C24126Ab7`): mapa de motivos del servidor si no está vacío; si no, `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; chats de plantilla OTP: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Contexto de business discovery (found)

`C33446EhE.A07` lee el registro de business discovery del JID reportado (almacén `LA8`): marca de tiempo, id, punto de entrada. Enum de puntos de entrada (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. Se adjunta tanto a los reportes (`biz_opt_out` bajo `spam_list`) como a los bloqueos. Estas son las únicas señales de cómo-empezó-este-chat encontradas en el cliente.

### 8.4 Listas de motivos de reporte (found)

Solo los anuncios de business tienen una lista seleccionable. `ReportReasonListFragment` empieza vacío y se llena desde `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (respuesta `mobile_config` > `list` con `name`, `v`, `country`). Enum de respaldo hardcodeado (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. Cuándo se usa el respaldo: inferred como lista del servidor no disponible. No hay selector de motivo para reportes ordinarios de usuario/grupo/mensaje; el único "motivo" en la red es `spam_flow`.

---

## 9. Reportar a los admins del grupo

### 9.1 Envío y obtención (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

No se envía contenido, token ni `spam_flow`; solo el id del mensaje. Los errores solo registran `Rta::<op>/onError: <code>` o `/onDeliveryFailure: Network Failure`.

### 9.2 Alternancia de reporte de miembros (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (activar) o `<not_allow_admin_reports/>` (desactivar), smax 384. Los nodos son hijos directos del IQ, no envueltos en un nodo `group`. El builder acepta hasta cuatro nodos de configuración hermanos en un IQ.

---

## 10. Respuesta del servidor y diálogos de finalización

### 10.1 Respuesta (found)

Éxito (`type=result`): hijo `report` con atributo `id` (máx. 20 caracteres) → `C213959Ch.A01` → devuelto a la UI como el id del reporte. Errores (`<error code text>`), por clase de respuesta:

| Código | Nombre | Individual | Grupo | Newsletter | Estado | Estado V2 | Evento |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 Diálogos de finalización

`H2U` decide a partir del id del reporte y las condiciones, luego `C5BD` construye el fragment (`arg_report_id`, `arg_is_ad_report`):

| Condición | Diálogo |
|------|--------|
| flag **25818**, chat de usuario, mensaje presente | `NciiCompletionDialogFragment` |
| flag **6145** | `DsaCompletionDialogFragment` (UE) |
| flag **14249** | `UkOsaCompletionDialogFragment` |
| flags **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

Todos excepto NCII necesitan un id de reporte no nulo; sin id no hay diálogo.

---

## 11. Señales de abuso en el cliente

### 11.1 Qué envía el cliente además del contenido (found)

Los puntos de entrada con `*_server_flagged_suspicious` significan que la tarjeta se mostró para un chat marcado por una señal distinta de la verificación local de contactos; cómo el cliente se entera de ese flag es unknown. Enviado en los reportes: `is_known_chat`, `biz_opt_out` (cómo empezó el chat de business), ítems de llamada (duración, quién terminó, motivo de terminación), contexto `extension_screen` de business Flows, `source` (quién me agregó al grupo), `reported_push_name`, flags de reenvío/broadcast/URL en cada mensaje, flag de editado, estado view-once, punto de entrada, `wi_trace_id` opcional.

### 11.2 Detección de estafas en el dispositivo (found, acotado)

`com.whatsapp.integrityai` ejecuta en el dispositivo un conjunto de modelos descargado (`scam_detection`) mediante ExecuTorch (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; features `mostRecentSenderScore`, `isCountryMismatch`). Los resultados activan banners/hojas de advertencia y los puntos de entrada `odml_scam_alert_*` anteriores. Un registro JSON local del escaneo (`outcome`, `inputs`, `model_info`, `verification`) se escribe en un `FileStash` cuando `integrity_warning_report_enabled` (`C57375Pog`). No se encontró ninguna subida de ese registro (unknown). Es independiente del stanza de reporte `spam`.

### 11.3 Telemetría (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. Mapeo de códigos de error en `reportAsSpam$1`: cancelación -4, timeout/sin respuesta -1, otra excepción -3, error de protocolo = código de error del IQ.

---

## 12. Baileys

El paquete `baron-baileys-v2` no tiene API de reportes. Las formas siguientes provienen de los nodos found y están untested.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

Las formas de reporte de usuario/grupo/canal siguen la sección 5 (un solo `spam_list` fusionado, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Por qué falla (todo inferred) | Causa | Solución |
|--------------|-------|-----|
| error 548 o no-op silencioso | no hay reporting token/clave válidos: Baileys descarta el hijo `<reporting>` de los mensajes entrantes y nunca deriva la clave | parsear `reporting_tag`/`reporting_token` al recibir, almacenar por mensaje, derivar la clave desde `messageSecret` (caso de uso 5) al momento del reporte |
| 400 | `jid` de clase incorrecta (debe ser usuario/interop para el tipo 20), conteos de ítems por encima de los topes, `spam_flow` de tipo incorrecto | usar los strings de `spam_flow` de la sección 7; mantenerse bajo 210 / 5 ítems |
| IQ rechazado | dos `spam_list` hermanos (motivo enviado como segundo nodo) en lugar de un nodo fusionado | enviar un solo `spam_list` con todos los atributos |

Tanto `wi_trace_id` como `is_known_chat` son opcionales en el builder; si el servidor acepta reportes con tokens fabricados es unknown.

---

## 13. Casos de error

| Síntoma | Causa | Nivel |
|---------|-------|------|
| toast `str3bf8`, no se envía nada | `C9ZJ` rechazó el valor de `flow` (`Invalid BlockSpamReportOrigin value`) | found |
| falla `unrecognized jid` | el JID del chat no es usuario/grupo/estado/newsletter | found |
| el reporte "falla" sin toast | error del servidor 548: `C9ZI.A00` devuelve el mismo objeto de resultado sin error que la ruta de bot | found |
| toast de falla genérica | 400/403/429/500/501, o timeout (32 s) → `C216549Uq` | found |
| falta el contenido del reporte | view-once abierto/expirado y origen que no es un visor; el mensaje no tiene token almacenado | found / inferred |
| el estado local dice reportado, el servidor lo rechazó | `is_spam_reported` se escribe después del RPC sin verificación visible del resultado | found (flujo), inferred (consecuencia) |

---

## 14. Distinciones clave

| No confundir | Con |
|----------------|------------|
| `spam_list@source` | el reportante. Es el usuario que agregó al reportante al grupo |
| `spam_list@subject` (grupo, canal) | un motivo. Es el nombre del grupo/canal |
| `spam_flow` | un motivo de reporte. Es la superficie de la UI que disparó el reporte (97 valores) |
| reporte (xmlns `spam`) | bloqueo (xmlns `blocklist`), report-to-admin (xmlns `w:g2`), baja de marketing (xmlns `optoutlist`, `C31105Dfx`, no analizado más) |
| dos nodos `spam_list` | un `spam_list` fusionado (atributos e hijos combinados) |
| spam de llamada | spam de evento. Los reportes de llamada son tipo 20 con un ítem `call`; el tipo 18 es `event_id` |
| `reporting_tag` (emitido por el servidor, almacenado al recibir) | `reporting_token` (HMAC de 16 bytes, enviado con los mensajes salientes y subido en los reportes) y `reporting_token_key` (derivada, subida) |
| report-to-admin | reporte a WhatsApp. El reporte a admin envía solo `message_id`; sin contenido, sin token |
| `wi_trace_id` (id de traza enviado por el cliente) | el id del reporte, que el servidor devuelve en `<report id>` |
| `report_block` | un valor de la red. Es un string de analítica/toast del cliente; el bloqueo es su propio IQ |
| alternancia `allow_admin_reports` (`$t=1`) | mensaje report-to-admin (`$t=0`) |

---

## 15. Flujo de extremo a extremo

```
[User]                  [Client]                                        [WhatsApp server]
  │ Report / Block+Report    │                                               │
  ├────────────────────────▶│ ReportSpamDialogFragment(flow = spam_flow)     │
  │ confirm (+block/leave)   │ reportAsSpam$1                                │
  │                          │  bot chat ──▶ BotMessageHelper/reportUgc      │
  │                          │ SpamReportRepo.A02: route by JID class        │
  │                          │  C9ZJ(flow) ──✗ IllegalArgumentException      │
  │                          │  no message ──▶ last 5 messages from DB       │
  │                          │ serialize msgs (EhE) + token + key,           │
  │                          │ is_known_chat, biz_opt_out, call items        │
  │                          │ C9EN + C9E2 merged into ONE spam_list         │
  │                          │ ── iq set xmlns=spam to=s.whatsapp.net ─────▶│
  │                          │                                   verify token│
  │                          │◀── result <report id> | error 400/403/429/    │
  │                          │    500/501/548 (548 treated as success)       │
  │                          │ WAM wam_spam_report_perf                      │
  │                          │ contacts.is_spam_reported = 1                 │
  │                          │ extra action:                                 │
  │                          │  user ── iq set xmlns=blocklist (block) ────▶│
  │                          │  group ─ leave   channel ─ hide + exit        │
  │◀─ completion dialog (DSA / UK OSA / AU OSA / NCII; needs report id)      │
  │                                                                          │
  │ member: iq set xmlns=w:g2 to=group reports>report{message_id} ──────────▶│
  │ admin : iq get xmlns=w:g2 to=group <reports/> ◀── report > reporter      │
```

---

## 16. Unknown

| Elemento | Motivo |
|------|--------|
| Verificación del token en el servidor, emisión de `reporting_tag`, cómo se decide `server_flagged` | lógica del servidor, no está en el APK |
| Origen de `wi_trace_id` | generador no localizado en la decompilación |
| Disparador de UI del reporte de evento, forma en la red del reporte de chat de bot | solo llamadores lambda (`AYs`, `Aaa`) / `reportUgc` no rastreado más allá de `C33437Eh4` |
| String de flujo que pasa el llamador del reporte de estado de canal | `channel_status_report` es rechazado por `C9ZJ` |
| Corte de la limpieza de `reporting_info*` | llamador de `FP7` case 6 no rastreado |
| Subida del registro local de escaneo de estafas | no se encontró ningún consumidor |
| Esquema por entrada del hijo `reporting` por mensaje y propósito de la llamada del flag 20085 | construido a partir de filas de DB, lógica del consumidor no leída |
| Aceptación en vivo de cualquier stanza de la sección 12 | no se capturó tráfico |
