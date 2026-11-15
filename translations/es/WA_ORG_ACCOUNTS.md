<!-- src-sha1: 5fa1223d0cb214989ef32453299c247d3ee92ecf -->
# WhatsApp Cuentas de Organización — Full RE Report
**Versión:** 2.26.45.10 | **Fecha:** 2026-11-15
**Alcance:** modelo de entidad de cuenta-org (org_id, directorio de miembros, taxonomía de member-tag/team), flujo de unión por enlace de invitación, verificación de disponibilidad de nombre visible, onboarding con compuerta de email (OTP), catálogo de operaciones `GraphQlOrgApi`/`OrgEmailCodeClient` (9 ops, `www` + `mex`), distinción respecto a Managed Account y a la delegación de WhatsApp Business API, notas de implementación Baileys/velowa

---

## 1. Qué es una cuenta de organización

Todas las afirmaciones son análisis estático de la APK decompilada. Nivel: **found** = literal de string/campo leído en un call site, **inferred** = deducido de la forma del código sin una llamada end-to-end rastreada, **unknown** = no resuelto.

Un "org" (nomenclatura interna en todo el código, nunca expandido a "organization" en ningún string leído) es una entidad de membresía con identidad propia, un directorio de miembros al que se puede unir, y una ruta de onboarding por enlace de invitación más OTP por email, completamente separada del propio registro por número de teléfono de la cuenta y de los otros dos sistemas con sonido "managed" ya presentes en este repositorio (sección 7).

| Entidad | Nombre interno | Campos (found) | Rol |
|---|---|---|---|
| Identidad de org | `org_id` | `org_id`, `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` | la propia org, resuelta desde un enlace de invitación |
| Enlace de invitación | `link_token` | transportado de extremo a extremo desde el referrer/deep-link hasta la mutación final de unión | credencial de unión ¿de un solo uso?; duración exacta `unknown` |
| Identidad de miembro dentro de la org | `display_name` (+ opcional `display_last_name`), `member_tag` | nombre visible por miembro sujeto a su propia verificación de disponibilidad/política, independiente del nombre de perfil principal de la cuenta | cómo se muestra un miembro dentro del directorio de la org |
| Taxonomía de equipo/rol | `team`, `team_options`, `selected_team` | encontrados como campos de estado; la semántica de los valores individuales de team no está resuelta | agrupación de miembros dentro de una org |
| Relación de directorio | `relationship` (`OrgDirectory`), único valor observado `"CONTACT"` | — | el único valor de filtro de relación visto; otros mapeos ordinal→string son `unknown` |

Todos estos nombres de campo se leen textualmente como literales `const-string` inmediatamente antes de una llamada setter `GraphQlCallInput`/`LX/0jN` en `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali` y `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali` (2.26.45.10), más la lista de campos del objeto de estado `OrgJoinViewModel` — todo **found**. El orden de pasos que enlaza estas ops en un flujo (sección 3) es **inferred** a partir de cómo se alinean los campos de estado, no de una única secuencia de llamadas rastreada.

---

## 2. Catálogo de operaciones

9 operaciones en dos transportes, todas en `com.whatsapp.orgs`. 7 en `www` (`GraphQlOrgApi`, GraphQL de persisted-doc_id vía `Lcom/facebook/pando/TreeWithGraphQL`), 2 en `mex` (`OrgEmailCodeClient`). Las variables son **found** desde el call site en cada fila abajo.

| Op | Transporte | doc_id (2.26.45.10) | Tipo | Variables | Propósito |
|---|---|---|---|---|---|
| `OrgInvitePreview` | www | `29166886682947630` | Query | `link_token` | vista previa de la org (nombre/ícono/conteo de miembros) antes de comprometerse a unirse |
| `OrgCheckDisplayName` | www | `28738875225734024` | Query | `display_name` | verificación de disponibilidad/política para el nombre visible del miembro dentro de la org |
| `OrgCheckEmailEligibility` | www | `28705126895811065` | Query | `link_token`, `email` | si este email es usable para esta invitación de org específica |
| `OrgSendEmailCode` | mex | `28659396457057459` | Mutation | `email` | enviar OTP por email |
| `OrgVerifyEmailCode` | mex | `29096159596657036` | Mutation | `email`, `code` | verificar OTP de email |
| `OrgJoin` | www | `29366364109633604` | Mutation | `link_token`, `email`, `org_display_name`, `member_tag`, `org_display_last_name` | envío final de unión |
| `OrgDirectory` | www | `28698253656512395` (rotado desde `28049955604655823` en 2.26.41.6) | Query | `org_id`, `relationship` (solo se observó `"CONTACT"`), `first`, `after` | directorio de miembros paginado, post-unión |
| `OrgMemberSearch` | www | `39884553687825642` (rotado desde `28199835469697557`) | Query | `query`, `org_id`, `first`, `after` | búsqueda dentro del directorio de miembros |
| `OrgLeaveMutation` | www | `28491454287217875` | Mutation | `org_id` | salir de la org, en cualquier momento tras unirse |
| `OrgList` | www | `28999557569709709` (rotado desde `27920891847589435`) | Query | `unknown` (no se encontró call site estático más allá del doc_id/rotación) | listar las orgs a las que pertenece la cuenta |

Las 7 ops `www` viven en una sola clase, `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`; las dos ops `mex` en `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`. El namespace/schema para las ops `www` es `whatsapp-android-www`; para las ops `mex`, `whatsapp-android-mex`. `OrgDirectory`/`OrgList`/`OrgMemberSearch` ya existían antes de 2.26.45.10 (capturadas por primera vez contra 2.26.41.6); sus doc_ids rotaron entre ambos builds (misma clase, mismos nombres de campo) — las otras 7 son nuevas en 2.26.45.10.

Existen ops de búsqueda auxiliares un paquete más allá, `com/whatsapp/work/publicidentity/` — no son parte del flujo de unión en sí, sino la forma en que el cliente de un contacto se entera de que alguien pertenece a una org, incluso antes de que haya una invitación involucrada:

| Op | Transporte | doc_id | Variables | Propósito |
|---|---|---|---|---|
| `WorkPublicContactInfoQuery` | www | `29154186964216430` | `lids` (lista) | estado de work/business-account por contacto, en lote (`CoalescingBatcher`, con debounce, máx. 100 claves por ronda) |
| `WorkPublicOrgInfoQuery` | www | `28899689926378846` | `ids` (lista, ids de org) | información pública de org (`id`, `name`, 2 campos string opacos adicionales — `inferred`: logo/dominio) para las orgs a las que pertenece un contacto |

---

## 3. Flujo de unión de extremo a extremo

Orden **inferred**, ensamblado a partir de los nombres de campos del objeto de estado de `OrgJoinViewModel` (ninguna secuencia de llamadas rastreada única cubre esto de extremo a extremo):

### 3.1 Entrada

La invitación llega como un link token, bien a través de un referrer/deep-link (`OrgInviteReferrerOpener`, literal `org_invite_token_from_referrer` → se convierte en `link_token`) o abierta directamente (`OrgInviteLandingActivity`, con estados de fallo `org_invite_landing_failure` / `org_invite_landing_already_in_org`).

### 3.2 Vista previa

`OrgInvitePreview(link_token)` devuelve lo suficiente para poblar `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` antes de que el usuario se comprometa a nada.

### 3.3 Verificación de nombre visible

`OrgJoinActivity`/`OrgJoinViewModel` recoge `display_name` (+ opcional `display_last_name`) y una selección de team (`team`/`team_options`/`selected_team`). `OrgCheckDisplayName(display_name)` es la compuerta de política/disponibilidad; ante un rechazo, la continuación anidada `OrgJoinViewModel$checkName$2` fija `name_refusal` y/o `last_name_refused` de forma independiente — el nombre y el apellido pueden ser rechazados cada uno por separado.

### 3.4 Elegibilidad de email y OTP

`OrgCheckEmailEligibility(link_token, email)` verifica si un email dado puede usarse para esta invitación específica. `OrgSendEmailCode(email)` (mex) envía entonces el OTP; tras que el usuario lo ingresa, `OrgVerifyEmailCode(email, code)` (mex) lo verifica. La verificación puede exponer `username_pending_email` / `rejoin_after_username` / `username_screen_open` — la unión puede quedar supeditada a la configuración de username de la cuenta principal, una dependencia del sistema de `WA_USERNAME.md` que por lo demás no está relacionada con las orgs.

### 3.5 Unión

`OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)` es el envío final. El éxito fija `joined=true` y pobla los campos de la org (`org_id`, `org_name`, `org_member_count`, `org_icon_*`, `org_description`) en el estado local.

### 3.6 Post-unión

`OrgDirectory(org_id, relationship="CONTACT", first, after)` obtiene el directorio de miembros; `OrgMemberSearch(query, org_id, first, after)` lo busca. `OrgLeaveMutation(org_id)` permite salir, en cualquier momento después de unirse.

```
[Invite link / referrer]
  │ OrgInviteReferrerOpener: org_invite_token_from_referrer -> link_token
  │ (or OrgInviteLandingActivity: org_invite_landing_failure / _already_in_org)
  ▼
[OrgInvitePreview(link_token)]
  │  org_name, org_member_count, org_icon_*, org_description
  ▼
[OrgJoinActivity / OrgJoinViewModel]
  │  org_join_offline, step, team/team_options/selected_team, display_name, display_last_name
  ▼
[OrgCheckDisplayName(display_name)]
  │  -> name_refusal / last_name_refused on rejection
  ▼
[OrgCheckEmailEligibility(link_token, email)]
  ▼
[OrgSendEmailCode(email)]           -- mex, OTP send
  ▼
[user enters code]
  ▼
[OrgVerifyEmailCode(email, code)]   -- mex, OTP verify
  │  -> username_pending_email / rejoin_after_username / username_screen_open
  ▼
[OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)]
  │  -> joined=true, org_id/org_name/org_member_count/org_icon_*/org_description populated
  ▼
[OrgDirectory(org_id, relationship="CONTACT", first, after)]
[OrgMemberSearch(query, org_id, first, after)]
[OrgLeaveMutation(org_id)]
```

---

## 4. Distinciones clave — no confundir

Existen tres conceptos de "estructura de cuenta" no relacionados en/alrededor de este cliente. No comparten código, ni proto, ni espacio de doc_id.

| | Cuentas de Organización (este informe) | Managed Account (`WA_MANAGED_ACCOUNT.md`) | Delegación Business API (BSP/Cloud API) |
|---|---|---|---|
| Identidad de entidad | `org_id`, directorio propio | `ManagedAccountConnection`, indexado por `connectionLid`/`connectionPnJid` | campos del certificado de nombre verificado (`host_storage`/`actual_actors`), sin nuevo id de entidad |
| Relación | unión voluntaria vía enlace de invitación, N miembros por org | un sponsor ↔ un dependiente, un vínculo de supervisión | un número de negocio operado por Meta/un proveedor sobre Cloud API |
| Onboarding | enlace de invitación + OTP de email + verificación de disponibilidad de nombre visible | deep link + vinculación iniciada por el sponsor (`ManagedAccountInitiateLinkingQuery` etc.) | aprovisionamiento del lado servidor en la plataforma de negocio de Meta; invisible para este cliente más allá de los marcadores resultantes |
| Ubicación de código | `com.whatsapp.orgs.*` | `com.whatsapp.managedaccount.*` / `pma.*` / `pmta.*` | sin paquete dedicado; señalizado vía campos de certificado `w:biz` y tipo de cuenta `HOSTED` multi-dispositivo |
| Transporte | GraphQL `whatsapp-android-www` + `whatsapp-android-mex` (OTP) | solo `whatsapp-android-mex` | campos de stanza `w:biz`, no es un protocolo de unión/invitación en absoluto |
| Salir/desvincular | `OrgLeaveMutation(org_id)` | `ManagedAccountRevokeLinkingMutation` | no aplica — sin unión/salida por cuenta; el número en sí se aprovisiona/desaprovisiona del lado servidor |
| Concepto de directorio | sí — `OrgDirectory`/`OrgMemberSearch`, acotado por relación | no | no |

Ninguno de los tres es un cambio de nombre o evolución de otro: una cuenta de organización no tiene semántica de supervisión (sin estado de edad/graduación, sin PIN de sponsor) ni semántica de certificado de negocio (sin `host_storage`/`actual_actors`, sin verificación de prefijo de emisor); es un modelo simple y voluntario de membresía-con-directorio superpuesto a una cuenta de WhatsApp ya registrada. La conclusión de nomenclatura de producto ("la función propia de WhatsApp de organizaciones para empresas/instituciones") es **inferred** solo a partir de la forma de los campos (`org_id` + directorio de miembros + verificación de disponibilidad de nombre visible + verificación de dominio de email) — no se leyó ningún texto de marketing ni copy en el cliente que nombrara la función.

---

## 5. Casos de error

No se pudo construir ninguna tabla de códigos de error a partir de los call sites de este build — no se encontraron literales de forma de respuesta (nombres de campo de éxito/fallo, códigos de error numéricos) para ninguna de las 9 ops en esta pasada. Las únicas señales de rechazo leídas son los dos campos de estado booleanos en `OrgJoinViewModel$checkName$2`:

| Síntoma | Causa | Evidencia |
|---|---|---|
| Nombre visible rechazado | fallo de política/disponibilidad de `OrgCheckDisplayName` | `name_refusal` fijado (found, campo de estado) |
| Apellido rechazado independientemente del nombre | mismo chequeo, rama específica de apellido | `last_name_refused` fijado (found, campo de estado) |
| Unión bloqueada pendiente de configuración de username | el éxito de `OrgVerifyEmailCode` depende del estado de username propio de la cuenta | `username_pending_email`/`rejoin_after_username`/`username_screen_open` (found, campos de estado; condición exacta del servidor `unknown`) |
| Invitación abierta ya siendo miembro | corte en seco de la landing page | `org_invite_landing_already_in_org` (found, literal de string) |
| Enlace de invitación inválido/expirado | fallo genérico de landing | `org_invite_landing_failure` (found, literal de string; no se encontró sub-razón distinta) |

---

## 6. Notas de implementación Baileys / velowa

Las 9 ops son llamadas GraphQL/MEX estándar de persisted-doc_id sobre los mismos namespaces `whatsapp-android-www`/`whatsapp-android-mex` que velowa ya implementa para otras funciones (username, groups) — no se encontró ningún transporte novedoso ni ninguna capa de cripto nativa específica de orgs.

| Listo para cable | No listo para cable |
|---|---|
| Los 9 nombres de op + doc_ids + claves de variable (sección 2) — suficiente para dar forma a una solicitud | Los nombres de campo de respuesta son unknown para todas las ops excepto las cuatro leídas explícitamente al estado de `OrgJoinViewModel` (sección 1); un cliente debe tratar todas las respuestas como JSON opaco hasta que una captura en vivo confirme las formas |
| Ruta de propagación de `link_token` (referrer → preview → join) | La compuerta exacta de pasos — si el servidor exige el orden de la sección 3, o si p. ej. `OrgCheckDisplayName`/`OrgCheckEmailEligibility` se pueden omitir — es `inferred`, no confirmado |
| Forma de paginación de `OrgDirectory`/`OrgMemberSearch` (`first`/`after`, patrón de cursor estándar) | Enum `relationship`: solo se confirma `"CONTACT"`; otros valores posibles son `unknown`, así que un cliente no debe asumir que es el único filtro válido |
| `OrgLeaveMutation(org_id)` — mutación de un solo campo, trivial de implementar | Las variables de `OrgList` en su totalidad (no se encontró call site — probablemente envía `{}`, no confirmado) |
| `WorkPublicContactInfoQuery`/`WorkPublicOrgInfoQuery` para búsquedas de solo lectura "¿este contacto está en una org?", independientes del flujo de unión | El formato de URL de invitación/deep-link en sí (host, ruta, codificación del token) — no capturado en esta pasada |

Una implementación de velowa que intente este flujo debe esperar descubrir las formas de respuesta empíricamente contra una cuenta en vivo, la misma advertencia que ya llevan los otros informes de transporte `inferred` de este repositorio (p. ej. `WA_USERNAME.md`).

---

## 7. Incógnitas

| Tema | Razón |
|---|---|
| Variables de `OrgList` | no se encontró call site estático más allá del doc_id + rotación; probablemente `{}` pero no confirmado |
| Valores del enum `relationship` distintos de `"CONTACT"` | solo se observó un mapeo ordinal→string (ordinal 0 → `"CONTACT"`); otras ramas no cubiertas en esta pasada |
| Formas de campo de respuesta para las 9 ops | no se encontraron literales/nombres de campo del lado respuesta en ningún call site; todo más allá de los campos de estado de `OrgJoinViewModel` es opaco |
| Duración/semántica de un solo uso de `link_token` | no rastreado; se asume de un solo uso solo por convención de nombres |
| Cumplimiento del lado servidor del orden de pasos de la sección 3 | ensamblado a partir de la forma de los campos de estado, no de una cadena de llamadas secuencial rastreada — un cliente podría poder reordenar u omitir pasos; no probado |
| Conjuntos de valores de `member_tag`/`team` | los campos existen (`team_options`, `member_tag`) pero no se encontraron valores enumerados |
| Formato de URL del enlace de invitación | no capturado en esta pasada |

---

## 8. Evidencia

Análisis estático del smali de WhatsApp Android 2.26.45.10, todos los literales y claves de variable leídos como `const-string` inmediatamente antes de su llamada setter `GraphQlCallInput`/`LX/0jN`. No se interceptó ningún tráfico; todas las afirmaciones de transporte/forma de respuesta son `inferred`. Fuente: `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`, `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`, `com/whatsapp/orgs/ui/join/OrgJoinActivity.smali`, `OrgJoinViewModel.smali`, `OrgJoinViewModel$checkName$2.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteReferrerOpener.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteLandingActivity.smali`, `com/whatsapp/work/publicidentity/graphql/MexWorkIdentityTransport.smali`.
