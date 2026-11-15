<!-- src-sha1: 09dd00f496c4831ec33afbfd78f4db63a78bf014 -->
# WhatsApp Reportes — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** reporte de usuario/contacto, grupo, canal, estado, llamada y mensaje — stanzas SMAX `spam`, `spam_list`, tipos de reporte, puntos de entrada de `spam_flow`, tokens de reporte, subida de contenido, UI de reporte/bloqueo, reporte a admin, stanza de bloqueo y listas de razón, errores de servidor, señales de abuso del lado cliente, Baileys

---

## 1. Qué es un reporte (técnicamente)

Un reporte es un IQ `set` a `s.whatsapp.net` en el namespace `spam`. Lleva un nodo `spam_list` (entidad reportada, mensajes reportados, punto de entrada, contexto de descubrimiento de negocio). El cliente re-serializa los mensajes reportados como protobuf en texto plano y los sube junto con un token de reporte y la clave que lo verifica. Bloquear es un stanza separado (`blocklist`). Reportar a un admin es un tercer stanza, no relacionado (`w:g2`).

Todas las afirmaciones son análisis estático de la APK decompilada. Nivel: **found** = leído en código, **inferred** = deducido del código, **unknown** = no resuelto. Nada aquí fue capturado en el cable.

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Constructor de IQ (multi-propósito, `$t` selecciona la forma) | `C9EN` | construye cada IQ de reporte (tipos 0, 18-23) y muchos otros IQs no relacionados |
| Nodo de razón/punto de entrada | `C9E2` | `spam_list` con `spam_flow`, `wi_trace_id`, `is_known_chat`, ... (`xmlns="spam"`) |
| Hijo de ajuste de grupo | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| Envoltura de contenido | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Nodos varios | `C31084Dfc`, `C31085Dfd` | flags (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Serializador ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, ensamblaje de token |
| Gestor SMAX | `SpamRPCManager` | `A01`-`A06`, uno por tipo de reporte |
| Repo | `SpamReportRepo` | enruta por clase de JID, efectos secundarios locales |
| Wrappers de RPC | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | paquete `com.whatsapp.reportinfra.rpc` |
| Lista blanca de origen | `C9ZJ` | valida el punto de entrada (78 valores) |
| UI | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | diálogo de reporte, bloqueo/salida opcional |
| Ejecutor de bloqueo | `C227489sZ` → `C34631Yx` | IQ `blocklist` |
| Reporte a admin | `RtaXmppClient` | cola de reportes `w:g2` |
| Almacén de token | `C23070uA` | tablas `reporting_info`, `reporting_info_content` |

Los nombres difieren por build; cada nombre obfuscado arriba se resolvió en 2.26.41.6 a partir de strings estables (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`).

**Re-verificado en 2.26.45.10** (found): `com.whatsapp.reportinfra.rpc.*` (los seis wrappers de RPC) y
`com.whatsapp.reportinfra.repo.SpamReportRepo` no cambian — mismas seis clases, mismo enrutamiento por clase de
JID, mismas llamadas `SpamRPCManager.A01`-`A06`, mismos strings de error/log (chequeo solo-smali, sin jadx en
esta pasada). Esto no es una nueva superficie de reporte; es el mismo paquete documentado arriba, solo
re-confirmado. El hook de métrica de rendimiento WAM (`wam_spam_report_perf`, sección 11.3) ahora viaja
visiblemente a través de un ayudante nombrado `ReportSpamPerfMetric$Companion` una capa más cerca de
`SpamReportRepo` — misma telemetría, sin campos nuevos.

---

## 2. Tipos de reporte

### 2.1 Enrutamiento (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` se bifurca según la clase de JID:

| JID reportado | Clase RPC | `SpamRPCManager` | Constructor `$t` | Clase de respuesta | Etiqueta de log |
|--------------|-----------|------------------|--------------|----------------|-----------|
| objeto de estado seleccionado (`AbstractC31014DeU` no null) en un JID de newsletter | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| usuario (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| grupo | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| objeto de estado seleccionado en cualquier otro JID, o JID de estado con una lista de mensajes | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| newsletter/canal | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| id de evento (string) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| cualquier otra cosa | ninguna | ninguna | ninguna | ninguna | se lanza `SpamReportRepo: unrecognized jid`, devuelto como fallo |
| chat de bot | ninguna (ver 3.3) | ninguna | ninguna | ninguna | `C214999If` |

Otras formas de `C9EN` que no son reportes de spam: `$t=0` reporte a admins y `$t=1` toggle de ajuste de grupo (sección 9), `$t=2` sugerencias de sub-grupo, `$t=24/25/26` nodos `status`. El RPC de evento se llama desde lambdas de corrutina (`AYs`, `Aaa`); la UI de origen es unknown (existen puntos de entrada de evento `event_home_report` / `event_info_report`, así que los reportes de evento son inferred).

### 2.2 Los reportes de llamada son reportes de usuario (found)

`SpamReportRepo.triggerReportCallNonSuspend` (origen `call_spam_dialog_report`) llama a `IndividualSpamReportRpc.A00` sin `jid` reportado, sin mensajes, y un ítem de llamada. El ítem de llamada (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` incluye `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` y errores fatales de codec. El flag **36386** elige la forma del propio JID en `to` (`CUC()` vs `Ask()`, inferred LID vs PN). Un reporte de usuario de UI con `shouldIncludeCallLogsInReport` añade hasta 5 ítems de log de llamada (`C16430i1.A0B(jid, 5)`).

---

## 3. Flujo del cliente

### 3.1 Diálogo

`ReportSpamDialogFragment` (diálogo inferior). Argumentos del fragment (found): `flow` (el string de punto de entrada, se convierte en `spam_flow`), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` carga el estado del diálogo.

Al confirmar, corre `reportAsSpam$1`:

1. Chat de bot: omite el RPC (3.3). De otro modo `SpamReportRepo.A02(...)` con el mensaje seleccionado en una lista de un elemento (o ninguno).
2. El éxito lleva un id de reporte opcional; el error muestra el toast `str3bf8` (o `C227489sZ.A00`, log `spamreportmanager/spam/report/no-network-cannot-report`). El WAM `wam_spam_report_perf` se llena (11.3).
3. Acción extra opcional `triggerExtraAction$2` (3.2), diálogo de finalización de `H2U` (10.2), escrituras locales (3.3).

### 3.2 Solo reportar vs reportar + acción extra (found)

El checkbox mapea al string `report` (sin marcar) o `report_block` (marcado), usado para analítica (`asd.BaC` vs `BaD`) y el toast posterior al reporte. La acción extra difiere según el objetivo:

| Objetivo | Acción extra cuando está marcado |
|--------|--------------------------|
| usuario | bloquear vía `C227489sZ.A01` → IQ `blocklist` de `C34631Yx` (sección 8), razón de bloqueo `null`, punto de entrada = `flow`, `deleteChat` = argumento `shouldDeleteChatOnBlock` |
| grupo | tarea de salir del grupo (`C98C` / `C9CI`, corrida con el JID del grupo; semántica de salida inferred) |
| canal | ocultar el canal reportado localmente (`NewsletterReportCompletionListener`, flag **25218**), luego flujo de salida/dejar-de-seguir de newsletter |

El IQ de reporte se envía primero; el bloqueo/salida corre después de que el RPC retorna, sin importar su resultado (inferido del flujo de control, sin chequeo de éxito antes de `triggerExtraAction$2`).

### 3.3 Chats de bot y efectos locales (found)

Los chats de bot omiten `SpamReportRepo`: el cliente llama a `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) y lo trata como éxito (`C214999If`); forma de cable unknown. Para otros chats `C24120Ab1` caso 4 hace:

| Paso | Efecto |
|------|------|
| sin mensaje seleccionado | recoge los últimos **5** mensajes del chat (`C14680f4.A01(..., 5, true)`; filas de tipo sistema excluidas, sin filtro `from_me` en esta variante) como el contenido reportado |
| chat de usuario | log local `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; el flag **20085** controla `H0J.A00(jid, ...)` (propósito unknown) |
| tras el RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, sin chequeo del resultado del RPC en el flujo visible |

---

## 4. Envelope de stanza y namespace

### 4.1 El nodo de razón se fusiona en el IQ (found)

Los RPCs no emiten dos hermanos `spam_list`. El `spam_list` principal (jid, mensajes) y el nodo de razón `C9E2` (un fragmento `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>`) se combinan con `C10340Uk.A04`, que fusiona atributos e hijos del mismo nombre (valores de atributo o conteos de hijo en conflicto abortan la fusión). Resultado:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Evidencia: los constructores de `C9EN` para 18-23 llaman a `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`; `C9E2` caso 5 construye `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. El `id` del IQ viene de `MessageClientSmaxWrapper.A01()` (`n<hex counter>`, `C10140Tq.A0H`). Timeout de envío 32000 ms (`A0F(node, id, cont, type, 32000, ...)`); una respuesta null (timeout/fallo de entrega) se convierte en `C216549Uq`.

Los tipos 0 y 1 fijan `xmlns="w:g2"` y `to=<group>` literalmente; los tipos 18-23 construyen `<iq type="set">` y dependen de la fusión para `to` y `xmlns`. El tipo id pasado al remitente es **98** (grupo, newsletter, evento) y **385** (reporte a admin).

### 4.2 Hermanos opcionales fusionados en `spam_list`

| Nodo/atributo | Fuente | Compuerta | Nivel |
|-----------|--------|------|------|
| `spam_flow` | argumento `flow` normalizado por `C9ZJ` | siempre | found |
| `wi_trace_id` (exactamente 24 caracteres) | `$wiTraceId` de `reportAsSpam$1` | opcional | found; origen del valor unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | flag **22256**; usuario: chequeo de agenda, grupo: chequeo de membresía de grupo | found |
| hijo `biz_opt_out` | `C33446EhE.A07` | existe registro de descubrimiento de negocio | found (ver 8.3) |

---

## 5. Stanzas por tipo

`from`/`to` de un ítem `<message>`: para la ruta de usuario el nodo anónimo `C9E4` fija `to=<jid>` cuando el mensaje es saliente (`key.fromMe`) y `from=<jid>` de otro modo. Los conteos son compuertas del constructor (`AbstractC10350Ul.A07`).

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

El constructor toma tres listas de ítems con topes de 210 (mensajes), 5 (ítems de llamada), 5 (ítems de business-flow sin mensaje, `C33446EhE.A0B`: últimas 5 entradas del almacén por negocio `messageless_flow_ids_per_business_<jid>`, nodo `extension_screen`). `jid` se valida solo contra `UserJid` y `C99O`; sin `subject` en esta ruta.

### 5.2 Grupo (tipo 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` es **el usuario que añadió al reportante al grupo**, no el reportante. Se lee del mensaje de sistema local ("yo me uní") por SQL `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`). Opcional. (found)
- `subject` es el nombre visible del grupo del registro de contacto (`C06290Dn.A07().A00.A0b`; significado del campo inferred), string vacío `""` para grupos padre de comunidad o cuando no existe registro (`Voip.REJECT_REASON_DECLINED` es `""`). No es una razón. Compuerta de longitud 0..65536. (found)
- Una cuarta lista en el constructor lanza (`getNode`) si no está vacía; el RPC pasa una lista vacía.

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

`subject` de newsletter = nombre del canal (`C2130898y.A0j`), `""` si desconocido (found). Los reportes de estado usan sus propias tablas de token `status_reporting_info` / `status_reporting_content`.

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

`C33446EhE.A0A(fmsg, entryPoint)` construye un ítem de mensaje por mensaje reportado:

| Parte | Detalle |
|------|--------|
| atributos de `<message>` | `t` (marca de tiempo del mensaje, 0..2^53), `id` (stanza id), jid `from`/`to`, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | protobuf `Message` re-serializado (`C30628DTw` con `MessageContextInfo` `C30624DTs`); `local_message_type` = int de tipo de mensaje interno |
| `<content_validation>` | token + clave (6.2) |
| flags de meta | `<edit v="1">` (editado), `<multicast/>` (flag de difusión 64), `<url_number/>` (flag 4), `<url_text/>` (flag 2), id de plantilla, tid de `hsm`, `iab reported_link`, `original_sender` / `group_history_sender`, variantes de pago `futureproof`/`request`/`send` (`pay`), `reported_push_name` |
| hijo `<reporting>` | flag **5718**: construido a partir de las filas `reporting_info` del mensaje (`C23070uA.A03`), hasta 1000 entradas (`C31085Dfd` caso 28); schema por entrada no completamente leído |
| portadores alternativos | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 valores, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

Mensajes de plantilla OTP: el placeholder `<code>` en los títulos de botón se reemplaza con el código real antes de la serialización (`AbstractC32303E8u.A00`). View-once: cuando el mensaje es view-once y ya está abierto/expirado y el origen no es `media_viewer` / `view_once_viewer`, `A06` es true y el bloque de serialización se omite. Si el ítem entonces lleva un `raw` vacío o ausente es inferred (declaración no inicializada en el decompile).

Los archivos de media no se re-suben por este stanza; el mensaje serializado lleva las referencias de media (inferred; no se encontró ninguna llamada de subida). El stanza guarda el proto en texto plano y la clave juntos, así que el servidor puede leer el contenido: nodos **found**, legibilidad **inferred**.

### 6.2 Token y clave de reporte (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

Ensamblado en `C33446EhE.A03` a partir de la fila almacenada (`C34539Ez0`): bytes del token (`A05`), versión (`A02`), id del stanza (`A03`), clave (`A07`). Si falta la clave se re-deriva: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → nativo `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (id de caso de uso **5**; los chats no-usuario pasan por variantes de `JniBridge`). Si tanto la clave como un token de 6 bytes están ausentes/en cero, el cliente registra `ReportingToken/MissingFkAtReport` y usa una clave de 32 bytes toda en cero. Un token faltante devuelve `null` (`ReportingToken is null`, el ítem no tiene `content_validation`).

### 6.3 Ciclo de vida del token (found salvo que se indique)

| Etapa | Detalle |
|-------|--------|
| Mensaje saliente | constructor `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Token = primeros 16 bytes de `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = proto de mensaje con filtrado de campo dependiente de versión (`A07`, elimina sub-campos seleccionados del campo 35; lectura inferred). Los llamantes del constructor no fueron rastreados |
| Compartir historial de grupo | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): para mensajes tipo 117 `<reporting>` con un hijo por entrada (atributo `id`, hijo `<reporting_token v>`) |
| Mensaje entrante | hijo de stanza `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>` parseado por `C34764F6h` / `C1S0`, flag **5718**; tanto tag como token opcionales, tag requerido |
| Almacenamiento | tablas `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) y `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`); `message_conditional_reveal.reporting_token_info` (blob); `group_history_share_reporting_info`; `status_reporting_info` |
| Historial | `WebMessageInfo.reportingTokenInfo` campo **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; flag **6578** |
| Limpieza | las filas de `reporting_info*` se eliminan cuando `receive_timestamp` es más antiguo que un corte (`FP7` caso 6); valor del corte no resuelto |
| Nodo de validación alternativo | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

Quién emite `reporting_tag` y cómo el servidor verifica el token: lado servidor, unknown. El emparejamiento (tag en el stanza, token+clave en el reporte) es inferred.

---

## 7. Puntos de entrada de `spam_flow`

97 valores (found, `C9E2` caso 5, orden = orden del array). El argumento `flow` pasa por `C9ZJ.A00`, que acepta **78** de ellos y lanza `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` de otro modo. Los seis wrappers de RPC lo llaman todos, y `SpamReportRepo.A02` captura la excepción y devuelve un fallo (error del lado cliente, no se envía ningún stanza). Los 78 son un subconjunto estricto de los 97. Los 19 valores rechazados: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. Probablemente estos son orígenes solo-de-bloqueo u otros orígenes de otro RPC (inferred). `channel_status_report` está en el enum pero rechazado por `C9ZJ`; qué flow pasa el llamante de channel-status es unknown.

| Superficie | Valores |
|---------|--------|
| Chat / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Banners de spam | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| Tarjetas de seguridad FMX | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| Alertas de estafa en el dispositivo | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Grupo | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Llamadas | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Canales / estado / eventos | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Negocio | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

La elección entre `*_suspicious` y plano para las tarjetas FMX se hace en `C230769yA.A05` a partir de `A0D(userJid)` (contacto conocido o no); ese predicado se infiere que es un chequeo de agenda. Las variantes `server_flagged` se eligen por tipo de tarjeta; de dónde viene el flag del servidor es unknown.

`wi_trace_id`: atributo opcional de 24 caracteres, pasado desde el llamante; su generador no fue encontrado (unknown). También es un campo del WAM `wam_spam_report_perf` (11.3).

---

## 8. Bloqueo, razones y contexto de negocio

### 8.1 IQ de bloqueo (found, área de `C34631Yx.A0M`)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` y `entry_point` solo se emiten para `action="block"`. `jid` se elige entre las formas PN y LID por un chequeo de ajuste (rama `zA02`; regla exacta no completamente leída); al bloquear el identificador extra es uno de `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. Timeout 20000 ms. Los puntos de entrada que empiezan con `odml_scam_alert_*` se reescriben a `1_1_spam_banner_block` (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). Los chats PSA usan un IQ distinto (`xmlns="w:comms:chat"`, `<blocking action>`). Obtención: `type="get"`, opcional `<item dhash>`.

### 8.2 Razones de bloqueo (found)

String hardcodeado → int local en `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, otro = 0. `RunnableC40792Hpk` mapea los mismos strings a un segundo conjunto de códigos. Estos ints alimentan llamadas de log locales; si llegan a un servidor es unknown.

Hoja de bloqueo de negocio (`C24126Ab7`): mapa de razón del servidor si no está vacío, de otro modo `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; chats de plantilla OTP: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Contexto de descubrimiento de negocio (found)

`C33446EhE.A07` lee el registro de descubrimiento de negocio para el JID reportado (almacén `LA8`): marca de tiempo, id, punto de entrada. Enum de punto de entrada (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. Se adjunta tanto a reportes (`biz_opt_out` bajo `spam_list`) como a bloqueos. Estas son las únicas señales de "cómo empezó este chat" encontradas en el cliente.

### 8.4 Listas de razón de reporte (found)

Solo los anuncios de negocio tienen una lista seleccionable. `ReportReasonListFragment` empieza vacío y se llena desde `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (respuesta `mobile_config` > `list` con `name`, `v`, `country`). Enum de fallback hardcodeado (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. Cuándo se usa el fallback: inferido como lista de servidor no disponible. No hay ningún selector de razón para reportes ordinarios de usuario/grupo/mensaje; la única "razón" en el cable es `spam_flow`.

---

## 9. Reporte a los admins del grupo

### 9.1 Envío y obtención (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

No se envía contenido, token ni `spam_flow`; solo el id del mensaje. Los errores solo registran `Rta::<op>/onError: <code>` o `/onDeliveryFailure: Network Failure`.

### 9.2 Toggle de reporte de miembro (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (activar) o `<not_allow_admin_reports/>` (desactivar), smax 384. Los nodos son hijos directos del IQ, no envueltos en un nodo `group`. El constructor acepta hasta cuatro nodos de ajuste hermanos en un IQ.

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

`H2U` decide a partir del id de reporte y de compuertas, luego `C5BD` construye el fragment (`arg_report_id`, `arg_is_ad_report`):

| Compuerta | Diálogo |
|------|------|
| flag **25818**, chat de usuario, mensaje presente | `NciiCompletionDialogFragment` |
| flag **6145** | `DsaCompletionDialogFragment` (EU) |
| flag **14249** | `UkOsaCompletionDialogFragment` |
| flags **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

Todos excepto NCII necesitan un id de reporte no-null; sin id no hay diálogo.

---

## 11. Señales de abuso en el cliente

### 11.1 Qué envía el cliente más allá del contenido (found)

Los puntos de entrada con `*_server_flagged_suspicious` significan que la tarjeta se mostró para un chat marcado por una señal distinta del chequeo de agenda local; cómo el cliente se entera de ese flag es unknown. Enviado en reportes: `is_known_chat`, `biz_opt_out` (cómo empezó el chat de negocio), ítems de llamada (duración, quién terminó, razón de terminación), contexto de Flows de negocio `extension_screen`, `source` (quién me añadió al grupo), `reported_push_name`, flags de forward/difusión/URL en cada mensaje, flag de editado, estado view-once, punto de entrada, `wi_trace_id` opcional.

### 11.2 Detección de estafa en el dispositivo (found, acotado)

`com.whatsapp.integrityai` corre un conjunto de modelos descargado (`scam_detection`) en el dispositivo vía ExecuTorch (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; características `mostRecentSenderScore`, `isCountryMismatch`). Los resultados conducen banners/hojas de advertencia y los puntos de entrada `odml_scam_alert_*` de arriba. Se escribe un registro de escaneo JSON local (`outcome`, `inputs`, `model_info`, `verification`) en un `FileStash` cuando `integrity_warning_report_enabled` (`C57375Pog`). No se encontró ninguna subida de ese registro (unknown). Es independiente del stanza de reporte `spam`.

### 11.3 Telemetría (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. Mapeo de código de error en `reportAsSpam$1`: cancelación -4, timeout/sin respuesta -1, otra excepción -3, error de protocolo = código de error del IQ.

---

## 12. Baileys

El paquete `baron-baileys-v2` no tiene ninguna API de reporte. Las formas abajo vienen de los nodos found y no están probadas.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

Las formas de reporte de usuario/grupo/canal siguen la sección 5 (un `spam_list` fusionado, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Por qué falla (todo inferred) | Causa | Arreglo |
|--------------|-------|-----|
| error 548 o no-op silencioso | sin token/clave de reporte válidos: Baileys descarta el hijo `<reporting>` de los mensajes entrantes y nunca deriva la clave | parsear `reporting_tag`/`reporting_token` al recibir, almacenar por mensaje, derivar la clave de `messageSecret` (caso de uso 5) al reportar |
| 400 | `jid` de clase incorrecta (debe ser usuario/interop para el tipo 20), conteos de ítem por encima de los topes, `spam_flow` de tipo incorrecto | usar los strings de `spam_flow` de la sección 7; mantenerse bajo 210 / 5 ítems |
| IQ rechazado | dos hermanos `spam_list` (razón enviada como un segundo nodo) en lugar de uno fusionado | enviar un `spam_list` con todos los atributos |

Tanto `wi_trace_id` como `is_known_chat` son opcionales en el constructor; si el servidor acepta reportes con tokens fabricados es unknown.

---

## 13. Casos de error

| Síntoma | Causa | Nivel |
|---------|-------|------|
| toast `str3bf8`, nada enviado | `C9ZJ` rechazó el valor `flow` (`Invalid BlockSpamReportOrigin value`) | found |
| fallo `unrecognized jid` | el JID del chat no es ninguno de usuario/grupo/estado/newsletter | found |
| el reporte "falla" sin toast | error de servidor 548: `C9ZI.A00` devuelve el mismo objeto de resultado sin-error que la ruta de bot | found |
| toast de fallo genérico | 400/403/429/500/501, o timeout (32 s) → `C216549Uq` | found |
| contenido del reporte faltante | view-once abierto/expirado y origen no es un visor; el mensaje no tiene token almacenado | found / inferred |
| estado local dice reportado, servidor rechazó | `is_spam_reported` escrito tras el RPC sin un chequeo de resultado visible | found (flujo), inferred (consecuencia) |

---

## 14. Distinciones clave

| No confundir | Con |
|----------------|------|
| `spam_list@source` | el reportante. Es el usuario que añadió al reportante al grupo |
| `spam_list@subject` (grupo, canal) | una razón. Es el nombre del grupo/canal |
| `spam_flow` | una razón de reporte. Es la superficie de UI que disparó el reporte (97 valores) |
| reporte (xmlns `spam`) | bloqueo (xmlns `blocklist`), reporte a admin (xmlns `w:g2`), opt-out de marketing (xmlns `optoutlist`, `C31105Dfx`, no analizado más a fondo) |
| dos nodos `spam_list` | un `spam_list` fusionado (atributos e hijos combinados) |
| spam de llamada | spam de evento. Los reportes de llamada son tipo 20 con un ítem `call`; el tipo 18 es `event_id` |
| `reporting_tag` (emitido por el servidor, almacenado al recibir) | `reporting_token` (HMAC de 16 bytes, enviado con mensajes salientes y subido en reportes) y `reporting_token_key` (derivado, subido) |
| reporte a admin | reporte a WhatsApp. El reporte de admin envía solo `message_id`; sin contenido, sin token |
| `wi_trace_id` (id de trazo enviado por el cliente) | el id de reporte, que el servidor devuelve en `<report id>` |
| `report_block` | un valor de cable. Es un string de analítica/toast del cliente; bloquear es su propio IQ |
| toggle `allow_admin_reports` (`$t=1`) | mensaje de reporte a admin (`$t=0`) |

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

| Ítem | Razón |
|------|--------|
| Verificación del token del lado servidor, emisión de `reporting_tag`, cómo se decide `server_flagged` | lógica del servidor, no está en la APK |
| Origen de `wi_trace_id` | generador no localizado en el decompile |
| Disparador de UI del reporte de evento, forma de cable del reporte de chat de bot | solo llamantes lambda (`AYs`, `Aaa`) / `reportUgc` no rastreado más allá de `C33437Eh4` |
| String de flow que pasa el llamante del reporte de channel-status | `channel_status_report` es rechazado por `C9ZJ` |
| Corte de la limpieza de `reporting_info*` | llamante de `FP7` caso 6 no rastreado |
| Subida del registro local de escaneo de estafa | no se encontró ningún consumidor |
| Schema por entrada del hijo `reporting` por mensaje y propósito de la llamada al flag 20085 | construido a partir de filas de BD, lógica consumidora no leída |
| Aceptación en vivo de cualquier stanza de la sección 12 | no se capturó ningún tráfico |
