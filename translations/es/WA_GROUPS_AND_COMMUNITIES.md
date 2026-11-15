<!-- src-sha1: 900bf74a45a7fabc6e7b8c42ef4df8074e676084 -->
# WhatsApp Grupos y Comunidades — Full RE Report
**Versión:** 2.26.41.6 (superficie de cable de aprobación de membresía/aprobación de unión verificada adicionalmente en 2.26.45.10, indicado en línea) | **Fecha:** 2026-11-15
**Alcance:** Modelo estructural de grupo vs. comunidad (grupo padre, sub-grupos vinculados, sub-grupo por defecto, chat general), direccionamiento JID, superficie de cable legacy `w:g2`/`w:gp2`, el catálogo de operaciones GraphQL de grupo/comunidad de `whatsapp-android-mex`, flujos de creación/invitación/acción-admin, enlaces de invitación, y la aprobación de unión a comunidad (`QueryMembershipApprovalRequests`, `GroupMembershipRequestUpdate`, el fallback legacy de `w:g2`, y la op de envío inferida `JoinMembershipForm`).

---

## 1. Qué es

Una **comunidad** de WhatsApp no es una entidad direccionable distinta. Es un **grupo** — el mismo espacio de JID, el mismo parser de nodo `<group>`, la misma tabla `wa_group_admin_settings` — que cumple el rol de **grupo padre** para un conjunto de **sub-grupos vinculados**. Este informe reúne el modelo de grupo/comunidad que de otro modo está disperso entre [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2 (clasificación, direccionamiento), [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) (tablas de BD), [WA_REPORTING.md](WA_REPORTING.md) (la superficie `w:g2` de reporte-a-admin) y [WA_POLLS.md](WA_POLLS.md) (variante de encuesta de sub-grupo por defecto), y añade el catálogo de operaciones MEX de grupo/comunidad y el hallazgo de aprobación de unión a comunidad de 2.26.45.10.

### 1.1 Entidades

| Entidad | Direccionamiento | Relación | Nivel |
|--------|-----------|----------|------|
| Grupo | JID propio `@g.us` | — | found |
| Comunidad | **mismo** espacio de JID `@g.us` que un grupo; clasificada, no tipada por separado | es un grupo que actúa como padre | found |
| Grupo padre | tipo de nodo `<group>` **1** (hijo `parent` presente) | cima de una comunidad | found |
| Sub-grupo vinculado | tipo de nodo `<group>` **2** (hijo `linked_parent jid`) | `linked_parent jid` apunta al JID del padre | found |
| Sub-grupo por defecto | tipo de nodo `<group>` **3** (hijo `default_sub_group`) | sub-grupo auto-creado de una comunidad; `group_type` **3** localmente, también el disparador de `pollCreationMessageV2` (WA_POLLS §1) | found |
| Chat general | tipo de nodo `<group>` **6** (hijo `general_chat`) | chat estilo anuncio de toda la comunidad | found |
| Grupo normal | tipo de nodo `<group>` **0** | sin relación de comunidad | found |

Clasificación y extracción de JID del padre: `C23201A1a.A01` (tipos 0/1/2/3/6 arriba), `C23201A1a.A03` (lee el JID del padre desde `linked_parent jid`) — ambos `found` en [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.3, re-citados aquí en lugar de re-derivados. `membership_approval_mode` para un sub-grupo toma por defecto el valor de `parent/default_membership_approval_mode="request_required"`.

---

## 2. Modelo de direccionamiento y participantes

Condensado de [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1–2.2 (detalle completo ahí; campos específicos de group-history omitidos aquí):

- Nodo `<group>`, ruta legacy `C23201A1a.A0C` (compartida con notificaciones de grupo); existe un gemelo MEX/SMAX (`AbstractC23204A1d`, `AN6`, `C23690AKd`).
- Atributos core: `id`, `creation`, `subject`, `s_t`/`s_o`/`s_o_pn`, `creator`/`creator_pn` (los gemelos `_pn` llevan el JID de teléfono junto a un LID).
- `addressing_mode` (`lid` / `pn`) — almacenado en `wa_group_admin_settings.addressing_mode`; cualquier valor distinto de `pn` se lee como `lid`.
- `<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`). `type` es el atributo de rol por grupo que respalda el estado de admin; `jid`/`lid`/`phone_number` llevan las dos formas de dirección según `addressing_mode`.

No existe una clave separada tipo `community_jid` o `newsletter_jid` en ningún lugar del cliente — confirmado con evidencia de código fresca en §11.3 más abajo, consistente con el modelo "la comunidad es un grupo" de §1.

---

## 3. Protocolo de cable legacy (`w:g2` / `w:gp2`)

Las operaciones de grupo pre-MEX siguen corriendo como IQs XMPP binarios bajo el namespace `w:g2`; `w:gp2` figura como una de las variantes de stanza push `notification` (inventarios de namespaces `Protocols/xml-stanzas`, `Protocols/xmpp-namespaces-android`, `found`). Ejemplo concreto, recuperado estructuralmente (`found`, `WASmaxGroupsGetGroupInfoRPC`):

```
iq[id=<stanzaId>, to=<groupJid>, type="get", xmlns="w:g2"]
  query[request=<string>, phash=<string?>]
    add_request[admin=<userJid>, code=<string>, expiration=<int>]   (optional, min=0 max=1)
```

Variantes de respuesta: `ClientError` / `ServerError` / `Success` (metadata completa del grupo: participantes, asunto, creación, descripción, ajustes efímeros). El mismo namespace lleva operaciones de grupo no relacionadas documentadas en otro lugar de este repositorio y no repetidas aquí:

- Reporte-a-admin (`<iq to=groupJid type=set xmlns=w:g2><reports><report message_id=.../></reports></iq>`) y el toggle de reporte-admin (`allow_admin_reports`/`not_allow_admin_reports`) — [WA_REPORTING.md](WA_REPORTING.md) §9.
- El fallback legacy de solicitudes de aprobación de membresía — §11.2 más abajo.

---

## 4. Superficie GraphQL MEX

Catálogo de persisted-queries de `whatsapp-android-mex`, `found in` el asset embebido `whatsapp-android-mex_client_persist_ids.json`. Los valores de `doc_id` rotan en cada build de la APK (95 rotaciones registradas entre 2.26.41.6 y 2.26.45.10, `Querys/graphql-diff-2.26.41.6-to-2.26.45.10.md` en el brain) — las tablas abajo son el snapshot de 2.26.41.6.

### 4.1 Operaciones de grupo (21)

| Operación | doc_id (2.26.41.6) | Tipo |
|---|---|---|
| `AddParticipantsToGroupV2` | `28425601030437902` | Mutation |
| `AddParticipantsToGroupsV3` | `26857242513977310` | Mutation |
| `AddParticipantsToInteropGroup` | `25732168276369451` | Mutation |
| `AllowNonAdminGroupCreation` | `32024438593867697` | Query |
| `CreateGroup` | `38588807217433890` | Mutation |
| `GetPreRegGroupAddRequestsQuery` | `25018599251091282` | Query |
| `GroupMembershipRequestUpdate` | `29469157542702726` | Mutation |
| `GroupsCreateInteropGroup` | `25726817620301611` | Mutation |
| `GroupsStoreAndSendInvitesSMSMutation` | `27018112604523582` | Mutation |
| `GroupsStoreInvitesSMSMutation` | `25508574885415377` | Mutation |
| `JoinMembershipForm` | `28997137096573014` (nuevo solo en el catálogo de 2.26.45.10) | unknown |
| `LeaveInteropGroup` | `25346167795013271` | Query |
| `QueryBatchGetGroups` | `28340966318889583` | Query |
| `QueryGroupInfo` | `38342717635376065` | Query |
| `QueryGroupInfoByCode` | `27616410928049563` | Query |
| `QueryInteropGroupInfo` | `32734144032867938` | Query |
| `QueryLinkedGroupInfo` | `28221051120830416` | Query |
| `QueryMembershipApprovalRequests` | `28845604101745223` | Query |
| `QueryParticipatingGroups` | `28394594513526802` | Query |
| `QuerySuggestedGroups` | `26012055225051917` | Query |
| `SetGroupProperty` | `24688994337458819` | Mutation |
| `SetGroupResetInviteLink` | `24812851838367451` | Mutation |

### 4.2 Operaciones de comunidad (4)

| Operación | doc_id (2.26.41.6) | Tipo |
|---|---|---|
| `QueryCommunityParticipantCount` | `31981537024824321` | Query |
| `QuerySubgroupParticipantCount` | `24784259781196779` | Query |
| `QuerySubgroups` | `25554052094203120` | Query |
| `UpdateCommunityOwner` | `24781435194845316` | Mutation |

No existe en este catálogo ninguna operación con nombre `CreateCommunity` — `unknown` si la creación de comunidad es un wizard local del cliente que encadena `CreateGroup` + llamadas de vinculación, o una promoción implícita de servidor de un grupo a padre; no resuelto en esta pasada.

### 4.3 Variables recuperadas de los call sites de la APK (`found`)

| Operación | Variables | Call site |
|---|---|---|
| `CreateGroup` | `participants`, `subject`, `expiration_time_in_sec`, `trigger`, `member_add_mode`, `member_link_mode`, `member_share_group_history_mode`, `username`, `user_lid` | `X/C36500G6k.java` |
| `AddParticipantsToGroupV2` | `mode`, `user_lid`, `username`, `group_id`, `participants`, `add_participants_metadata`, `input` | `X/C08600aH.java` |
| `AddParticipantsToGroupsV3` | `mode`, `group_ids`, `participants`, `tctoken`, `privacy_token`, `add_participants_metadata` | `X/RunnableC24380AnV.java` |
| `QueryGroupInfo` | `group_jid`, `query_context`, `input` | `X/C08630aK.java` |
| `QueryGroupInfoByCode` | `invite_code`, `query_context`, `get`, `input` | `X/C08600aH.java` |
| `QueryLinkedGroupInfo` | `group_jid`, `sub_group_jid_hint`, `query_context`, `input` | `X/JOF.java` |
| `QueryBatchGetGroups` | `group_jid`, `query_context`, `groups`, `request_context` | `X/FGG.java` |
| `QueryParticipatingGroups` | `input` | `X/C16710ou.java` |
| `SetGroupProperty` | ver §9 | `X/A18.java`, `X/A19.java` |
| `SetGroupResetInviteLink` | `group_id`, `query_context`, `group_input`, `group_jid`, `max_use`, `seconds_for_expiry` | `X/C54392a5.java` |
| `AllowNonAdminGroupCreation` | `allow_non_admin_sub_group_creation` (bool) | `com/whatsapp/community/mex/AllowNonAdminSubGroupCreationGraphQlHandler.java` |
| `QuerySuggestedGroups` | `group_input` | `com/whatsapp/community/mex/GetSuggestedGroupsGraphQlHandler.java` |
| `QuerySubgroups` | `group_input` | `com/whatsapp/community/mex/GetSubgroupsGraphQlHandler.java` |
| `UpdateCommunityOwner` | `new_role`, `group_id`, `role_updates`, `user_jid` | `com/whatsapp/community/mex/TransferCommunityOwnershipGraphQlHandler.java` |
| `GroupsStoreAndSendInvitesSMSMutation` | `server_sent_sms`, `participants`, `entry_point`, `is_bundle_invite`, `participant`, `group_jid` | `com/whatsapp/invite/api/ServerSentGroupInviteMutationHelper.java`, `com/whatsapp/invite/ui/SMSPreviewGroupInviteBottomSheetFragment.java` |
| `GroupsStoreInvitesSMSMutation` | `partcipants` (sic), `group_jid` | `X/C67052zD.java` |
| `AddParticipantsToInteropGroup` | `gid`, `participants`, `jid`, `input` | `X/C3ZT.java` |
| `QueryInteropGroupInfo` | `gid`, `group_input` | `X/C3ZT.java` |

El resto (`GetPreRegGroupAddRequestsQuery`, `GroupsCreateInteropGroup`, `LeaveInteropGroup`, `QueryCommunityParticipantCount`, `QuerySubgroupParticipantCount`) no tiene call site estático recuperado: `unknown`, probablemente envían `{}`.

---

## 5. Creación de un grupo

`CreateGroup` (§4.3) fija `member_add_mode`, `member_link_mode`, `member_share_group_history_mode` en el momento de creación — las mismas tres propiedades de admin que `SetGroupProperty` edita después (§9). `trigger` es una etiqueta de punto de entrada tipo string (`found`, el conjunto exacto de valores no se enumeró en esta pasada).

---

## 6. Enlaces de invitación e invitaciones

| Elemento | Detalle | Nivel |
|------|--------|------|
| Reiniciar/crear enlace de invitación | `SetGroupResetInviteLink`: `group_id`, `group_jid`, `max_use`, `seconds_for_expiry` | found |
| Resolver un código de invitación | `QueryGroupInfoByCode`: `invite_code` -> info del grupo | found |
| Invitación SMS (bundle) | `GroupsStoreAndSendInvitesSMSMutation`: `participants`, `entry_point`, `is_bundle_invite`, `server_sent_sms` | found |
| Invitación SMS (solo almacenamiento) | `GroupsStoreInvitesSMSMutation`: `group_jid`, participants | found |
| Lista de permitidos/bloqueados | BD `wa_group_add_allow_list`, `wa_group_add_black_list` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |
| Invitaciones a no-WhatsApp | BD `group_non_wa_invites` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |

### 6.1 Forma de cable `groupInviteMessage`

`Message.groupInviteMessage`, campo **28**, tipo anidado `Message.GroupInviteMessage` (encontrado en WAProto.proto):

| Campo | # | Tipo |
|-------|---|------|
| `groupJid` | 1 | string |
| `inviteCode` | 2 | string |
| `inviteExpiration` | 3 | int64 |
| `groupName` | 4 | string |
| `jpegThumbnail` | 5 | bytes |
| `caption` | 6 | string |
| `contextInfo` | 7 | ContextInfo |
| `groupType` | 8 | enum `GroupType` |

`GroupType`: `DEFAULT` = 0, `PARENT` = 1 — el propio mensaje de invitación distingue una invitación de grupo plano de una invitación de comunidad (grupo padre), consistente con el modelo "la comunidad es un grupo clasificado" de §1. Existe un segundo tipo `GroupInviteMessage` de nivel superior no relacionado en el mismo archivo proto; esta tabla cubre solo el `Message.GroupInviteMessage` anidado usado por el campo 28.

---

## 7. Participantes: agregar, sugerir, enumerar

| Operación | Propósito (inferido del nombre + variables) |
|---|---|
| `AddParticipantsToGroupV2` / `V3` | agregar uno o más usuarios a uno o más grupos |
| `QueryParticipatingGroups` | listar grupos en los que está el llamante |
| `QueryBatchGetGroups` | fetch de metadata en lote para un conjunto de JIDs de grupo |
| `QuerySuggestedGroups` | superficie de sugerencias de comunidad/grupo; BD `member_suggested_groups_v2` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) |
| `QuerySubgroups` / `QuerySubgroupParticipantCount` / `QueryCommunityParticipantCount` | conteos a nivel de comunidad sobre los sub-grupos vinculados |

El atributo `<participant type=...>` (§2) lleva el flag de admin/rol por grupo, y `group_participant_user.rank` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §3.6) lo persiste localmente — así que el rango de admin existe como concepto, pero no se encontró ninguna operación MEX explícita de promover/degradar o eliminar-participante en este catálogo (las 21/4 ops de grupo/comunidad arriba son exhaustivas para 2.26.41.6). **Unknown**: si esa ruta todavía corre puramente como un IQ legacy `w:g2` de lista de participantes (consistente con el propio nombre de `AddParticipantsToGroupV2`, que implica que existió un predecesor V1) o bajo algún nombre de operación fuera de los buckets de subcadena `group`/`community`; no resuelto en esta pasada.

---

## 8. Grupos interop (breve)

`AddParticipantsToInteropGroup`, `GroupsCreateInteropGroup`, `QueryInteropGroupInfo`, `LeaveInteropGroup` — un conjunto pequeño paralelo de operaciones de grupo para grupos puenteados ("interop") con terceros. Fuera de alcance aquí más allá de listarlos; ver [WA_INTEROP.md](WA_INTEROP.md) para el modelo de consentimiento/puente interop en el que se insertan.

---

## 9. Ajustes de admin — `SetGroupProperty`

**Variables** (`found`, `X/A18.java`, `X/A19.java`):

| Campo | Tipo | Significado | Nivel |
|-------|------|---------|------|
| `group_id` | str | grupo objetivo | found |
| `subject` | str | nombre del grupo | found |
| `description` | str | descripción del grupo | found |
| `previous_id` | str | marcador de concurrencia optimista / valor previo (inferido) | inferred |
| `member_add_mode` | str | quién puede agregar miembros (`all_member_add` / otro, refleja el hijo legacy `<member_add_mode>`, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1) | found |
| `member_link_mode` | str | modo de permiso de enlace de invitación (inferido del nombre) | inferred |
| `member_share_group_history_mode` | str | `ADMIN_SHARE` / `ALL_MEMBER_SHARE`, enum completo y mapeo de mensaje de sistema en [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4 — no repetido aquí | found |
| `membership_approval_mode_enabled` | bool | activa/desactiva la restricción de solicitud de unión para este grupo — ver §11 | found |
| `limit_sharing`, `limit_sharing_enabled`, `limit_sharing_trigger` | str/bool/str | toggle de límite de reenvío para este grupo (inferido: restricción de reenvío "limit sharing") | inferred |
| `input` | str | objeto wrapper/contexto (forma no resuelta) | unknown |

La contraparte de notificación del lado servidor y la lista completa de columnas de `wa_group_admin_settings` (`restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `require_membership_approval`, `addressing_mode`, `allow_member_labels`, …) están en [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4 — referenciadas en cruz, no duplicadas.

---

## 10. Estructura específica de comunidad

| Elemento | Detalle | Nivel |
|------|--------|------|
| Enumeración de sub-grupos | `QuerySubgroups` (`group_input`) | found |
| Conteos de sub-grupo/comunidad | `QuerySubgroupParticipantCount`, `QueryCommunityParticipantCount` | found (ops existen), unknown (variables) |
| Búsqueda de grupo vinculado | `QueryLinkedGroupInfo` (`group_jid`, `sub_group_jid_hint`) — resuelve un sub-grupo dado su padre | found |
| Transferencia de propiedad | `UpdateCommunityOwner` (`new_role`, `group_id`, `role_updates`, `user_jid`) | found |
| Toggle de creación de sub-grupo no-admin | `AllowNonAdminGroupCreation` (`allow_non_admin_sub_group_creation` bool) | found |
| Variante de encuesta de sub-grupo por defecto | `pollCreationMessageV2` es el slot de encuesta usado cuando el chat es un sub-grupo por defecto (`group_type == 3`) — [WA_POLLS.md](WA_POLLS.md) §1, §3.3 | found |
| Tablas de BD | `subgroup_info`, `community_settings`, `group_relationship` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4) | found |

---

## 11. Aprobación de membresía y aprobación de unión a comunidad

### 11.1 Grupos: restricción de solicitud-de-unión

`membership_approval_mode_enabled` (`SetGroupProperty`, §9) activa la unión con restricción de admin para un grupo; `wa_group_admin_settings.require_membership_approval` es el flag persistido ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). Para un **sub-grupo** de una comunidad, el valor por defecto viene del padre en su lugar: `parent/default_membership_approval_mode="request_required"` (§1.1, `C23201A1a`). El almacenamiento de solicitudes pendientes se divide según quién puede aprobar: `group_membership_approval_requests` (visible para admin) y `non_admin_group_membership_approval_requests`; `group_membership_form_questions` contiene preguntas configuradas por el admin que un solicitante debe responder, y `group_membership_count` lleva los conteos agregados (todos `found`, [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). `group_membership_form_questions` es la evidencia concreta del lado cliente de que existe un flujo de formulario de membresía — directamente relevante para `JoinMembershipForm` más abajo.

### 11.2 Superficie de cable: ruta principal MEX + fallback legacy

`com/whatsapp/group/data/GroupFetchAllMembershipApprovalRequestsJob` (`found`, smali de 2.26.45.10) implementa "obtener solicitudes de unión pendientes de aprobación de admin" para un `groupJidRawString`, controlado en runtime por `LX/00E;->A0G(LX/00E;LX/00g;)Z` contra el flag id `LX/4WC;->A04` (leído vía `LX/00U;->A03(0x10d4)`):

| Ruta | Condición | Mecanismo |
|------|-----------|-----------|
| MEX | flag activado | `GraphQlCallInput` con `query_context="INTERACTIVE"` y el `GroupJid` objetivo, operación **`QueryMembershipApprovalRequests`** en el namespace `whatsapp-android-mex` |
| IQ binario legacy | flag desactivado (fallback `LX/0RD`) | `<iq type="get" xmlns="w:g2" to="<group_jid>" id="..."><membership_approval_requests/></iq>` |

El `doc_id` de `QueryMembershipApprovalRequests` rota normalmente entre builds: `28845604101745223` (2.26.41.6) → `28584744077887639` (2.26.45.10). La mutación de aprobar/denegar del admin, `GroupMembershipRequestUpdate`, es la contraparte (`29469157542702726` → `28746221238391491`, mismo patrón de rotación normal); su call site no fue rastreado en esta pasada, pero es la única mutación de membresía de grupo del lado admin en el catálogo (§4.1).

`JoinMembershipForm` (doc_id `28997137096573014`) es genuinamente nueva en el catálogo de 2.26.45.10 — ausente en 2.26.41.6, no una rotación de una op existente. Su nombre, combinado con la tabla `group_membership_form_questions` (§11.1), la convierte en la mejor candidata para la mutación del lado envío "responder las preguntas del formulario de membresía del admin y solicitar unirse" — pero su call site no fue rastreado en esta pasada. **Inferred**, no found, para su rol y esquema exactos.

### 11.3 Aprobación de unión a comunidad específicamente (2.26.45.10, found)

Paquete nuevo `com/whatsapp/community/product/joinapproval/`, una clase: `CommunityJoinApprovalNuxBottomSheet` — una hoja explicativa de UI local ("necesitarás aprobación del admin para unirte a esta comunidad"), no un call site de red en sí mismo.

- Construida por `LX/3IN;->C3f` con argumentos de bundle `"group_jid"` (el JID propio de la comunidad, leído como string de JID de grupo plano) y `"community_name"`.
- Manejador del botón primario `LX/3Ge;->C3f`, `pswitch_28`: lee el `GroupJid` almacenado, llama a `LX/122;->A01(Context, GroupJid, Integer)Intent`, lo inicia vía `LX/0KC;->A02`, descarta la hoja.

**Hallazgo clave:** la comunidad se direcciona por `group_jid`, no por una clave distinta tipo `community_jid`/`newsletter_jid` — confirmación directa de código, no solo convención de nombres, del modelo "la comunidad es un grupo" de §1/§2. No existe ninguna operación tipo `Community*ApprovalRequests` en todo el catálogo; las solicitudes de unión pendientes de una comunidad viajan exactamente por el mismo par MEX `QueryMembershipApprovalRequests` / `GroupMembershipRequestUpdate` (y el mismo fallback legacy `w:g2`) que usa un grupo plano, porque el job de aprobación de membresía solo ve un `groupJidRawString`.

### 11.4 Veredicto

| Afirmación | Nivel |
|-------|------|
| Comunidad direccionada por `group_jid`, misma ruta de código que los grupos | found |
| Listar solicitudes pendientes: MEX `QueryMembershipApprovalRequests` | found |
| Aprobar/denegar: MEX `GroupMembershipRequestUpdate` | found (op existe, catalogada); call site no rastreado |
| Fallback legacy: `<iq xmlns="w:g2"><membership_approval_requests/></iq>` | found |
| Flag de característica que selecciona MEX vs. legacy | found (flag id, no su estado de rollout actual) |
| El lado de envío es `JoinMembershipForm` | inferred |
| Esquema/variables exactas de `JoinMembershipForm` | unknown |
| Lógica de aceptación/validación del lado servidor | unknown (solo análisis estático, sin captura de tráfico) |

---

## 12. Referencia cruzada de almacenamiento local

Las listas completas de columnas están en [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md); esta es una tabla de referencia, no una duplicación:

| Tabla | Rol |
|-------|-----|
| `wa_group_admin_settings` | ajustes de admin por grupo (modo de direccionamiento, historial, aprobación, límite de reenvío, ...) |
| `group_participant_user`, `group_past_participant_user`, `group_participant_device` | participantes actuales/pasados, rango, estado de sender-key por dispositivo |
| `group_membership_approval_requests`, `non_admin_group_membership_approval_requests` | solicitudes de unión pendientes, divididas por visibilidad de aprobador |
| `group_membership_form_questions` | preguntas de formulario de membresía configuradas por el admin (§11.1, §11.2) |
| `group_membership_count` | conteos agregados |
| `subgroup_info`, `community_settings`, `group_relationship` | estructura de comunidad/sub-grupo |
| `member_suggested_groups_v2` | superficie de grupos sugeridos |
| `group_suspension_appeal` | estado de apelación de suspensión a nivel de grupo |
| `group_non_wa_invites` | invitaciones a contactos no-WhatsApp |
| `group_root_key_mapping` | mapeo de raíz de sender-key |

---

## 13. Notas de implementación Baileys / velowa

Todas las ops MEX de grupo/comunidad usan el mismo sobre IQ `w:mex` que cualquier otra persisted-query en este repositorio (`Protocols/mex-graphql`, `graphql-invocation-guide.md`):

```js
const res = await sock.query({
  tag: 'iq', attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '<doc_id>' },
    content: Buffer.from(JSON.stringify({ queryId: '<doc_id>', variables })) }],
})
```

El fetch legacy de metadata/participantes de grupo se mantiene en `w:g2` y ya está implementado por la mayoría de las librerías de WA Web (`groupMetadata`, llamadas estilo `groupQuery`); la aprobación de membresía necesita el IQ de §11.2 añadido explícitamente — la mayoría de las librerías no lo consultan.

| Por qué falla | Arreglo |
|---------------|-----|
| `doc_id` hardcodeado para cualquier op de grupo/comunidad | el `doc_id` rota en cada build de la APK (confirmado: 4 ops de grupo rotaron entre 2.26.38.10 y 2.26.41.6 solamente); refrescar desde una extracción de catálogo actual, no fijarlo |
| Asumir que la aprobación de membresía es siempre `w:g2` legacy | Está controlada por feature flag; una vez que el flag está activado del lado servidor para una cuenta, las solicitudes pendientes solo surgen vía MEX `QueryMembershipApprovalRequests` — implementar ambas rutas o solo MEX de ahora en adelante |
| Asumir que una comunidad tiene su propio tipo de JID | No lo tiene — direccionarla con el propio JID `@g.us` del grupo padre, igual que cualquier op de grupo |
| Intentar enviar programáticamente una solicitud de unión restringida | El esquema de `JoinMembershipForm` no está resuelto (solo rol inferido); no es implementable con confianza todavía |

---

## 14. Distinciones clave

- **La comunidad es un grupo clasificado, no una entidad separada.** No hay `community_jid`; el propio JID de la comunidad es un JID de grupo con tipo de nodo 1 (`parent`).
- **`member_share_group_history_mode`** (quién puede compartir historial reciente con nuevos miembros, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4) no está relacionado con **`membership_approval_mode_enabled`** (restricción de solicitud de unión, §9/§11) — ambos son campos de `SetGroupProperty` pero controlan características distintas.
- **`w:g2` reporte-a-admin** ([WA_REPORTING.md](WA_REPORTING.md) §9) y **fallback de `w:g2` de solicitudes de aprobación de membresía** (§11.2) comparten un namespace pero son nodos hijo no relacionados (`reports`/`allow_admin_reports` vs. `membership_approval_requests`).
- **`JoinMembershipForm`** es una op de envío inferida, no confirmada — no tratarla como found.
- **Promover/degradar/eliminar-participante** no tiene ninguna operación MEX identificada en este catálogo; tratar como no resuelto, no como "corre solo sobre `w:g2` legacy" (suposición, no evidencia).

---

## 15. Flujo de aprobación de unión a comunidad (según lo evidenciado hasta ahora)

```
[Member]                         [Client]                              [Server / whatsapp-android-mex]
   │ taps "Request to join"         │                                        │
   ├────────────────────────────────▶ CommunityJoinApprovalNuxBottomSheet    │
   │                                 │  (local explainer, group_jid+name)    │
   │ taps primary button             │                                        │
   ├────────────────────────────────▶ LX/3Ge;->C3f pswitch_28                │
   │                                 │  -> LX/122;->A01(ctx, GroupJid, int)  │
   │                                 │     Intent into group/community flow  │
   │                                 │  (submit side, inferred)              │
   │                                 ├───────────────────────────────────────▶ JoinMembershipForm (inferred)
   │                                 │                                        │
[Admin]                           [Client]                                 │
   │ opens pending-requests screen   │                                        │
   ├────────────────────────────────▶ GroupFetchAllMembershipApprovalRequestsJob
   │                                 │  flag on  ─▶ QueryMembershipApprovalRequests (MEX)
   │                                 │  flag off ─▶ <iq xmlns="w:g2"><membership_approval_requests/></iq>
   │                                 │                                        │
   │ approves / denies               │                                        │
   ├────────────────────────────────▶ GroupMembershipRequestUpdate (MEX) ────▶ server
```

---

## 16. Ítems abiertos / gotchas

- Variables/forma de respuesta de `JoinMembershipForm`: unknown, no rastreado a nivel de call site.
- Variables propias de `GroupMembershipRequestUpdate`: no recuperadas de un call site en esta pasada (solo se confirmó la existencia de la op).
- Promover/degradar/eliminar-participante: no se identificó ninguna op MEX; si es solo-legacy o si falta en el catálogo queda sin resolver.
- `CreateCommunity`: no existe tal op MEX; la ruta de creación de comunidad queda sin resolver (el wizard del cliente que encadena `CreateGroup` + vinculación es la hipótesis de trabajo, no confirmada).
- Todas las afirmaciones en §11 más allá de la existencia de la tabla de BD son análisis estático; nada aquí fue probado con tráfico (según el contrato de evidencia — no se realizó interacción en vivo con el servidor para este informe).
