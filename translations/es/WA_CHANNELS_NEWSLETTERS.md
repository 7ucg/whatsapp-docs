<!-- src-sha1: 42c77add3dafd5b90522b32d91692dff968b2f54 -->
# WhatsApp Canales y Newsletters — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** dominio de JID `@newsletter` y la denominación interna "newsletter", seguir/dejar de seguir, creación de canales, roles de administrador y traspaso, los seis campos proto `newsletterAdmin*`/`newsletterFollower*`/`newsletterScheduledMessage`, metadatos del canal (nombre, descripción, foto, verificación, estado), reacciones en publicaciones, recuentos de vistas/seguidores, flujo de invitación/revocación/aceptación de administrador, operaciones GraphQL/MEX de newsletter (doc_ids), almacenamiento local, feature flags, casos de error

---

## 1. Qué es (técnicamente)

Un "canal" es el nombre orientado al consumidor para lo que el cliente llama internamente **newsletter**: un JID de difusión uno-a-muchos con almacenamiento en servidor (no E2E), un pequeño conjunto de roles (owner/admin/subscriber/guest), y la mayoría de las operaciones del plano de control se transportan sobre `w:mex` GraphQL en lugar de IQs XMPP clásicos. La entrega de contenido (obtención de publicaciones, obtención de estados, mensajes programados, suscripción a actualizaciones en vivo) sigue usando un namespace IQ XMPP dedicado, `xmlns="newsletter"`. Todas las afirmaciones son análisis estático del APK decompilado; no se capturó nada en la red. Tiers: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto. A diferencia de la mayoría de los reportes de este repositorio con nombres ofuscados, el paquete de newsletter visible para el cliente (`com.whatsapp.newsletter.*`, 122 archivos) se distribuye con **nombres de clase y método legibles** en 2.26.41.6; solo la infraestructura compartida (JID, proto de mensaje, constructores de IQ) está ofuscada y se resuelve aquí de nuevo a partir de strings estables.

Fuera de alcance: listas de difusión clásicas y `status@broadcast` — ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md). Mecánica de búsqueda de contactos/dispositivos reutilizada por los newsletters (no específica de newsletter) — ver [WA_USYNC.md](WA_USYNC.md).

| Entidad | Valor | Tier |
|--------|-------|------|
| Servidor del JID | `newsletter` (p. ej. `120363000000000000@newsletter`) | found |
| `Jid.getType()` | **21** | found |
| Cifrado | `EnumC14260eC.NON_E2EE` — el contenido del canal **no está cifrado de extremo a extremo** | found |
| Clase del modelo local | `C2130898y` ("NewsletterInfo"), extiende la fila de chat genérica `C14220e7` | found |
| Clase del JID | `C1Y7` (`NewsletterJid`) | found |
| Enlace de invitación | `https://whatsapp.com/channel/<invite_code>` | found |
| Tabla local de BD | `newsletter` (columnas incluyen `membership`, `invite_code`, indexadas) | found |

| Componente | Nombre en 2.26.41.6 | Rol |
|-----------|----------------|------|
| Parser de JID | `C0DL.A03` (switch de strings del servidor), `C1Y7` (JID), `C1Y8` (companion/cache del JID) | valida el id numérico, sin cero inicial, construye/cachea `C1Y7` |
| Predicados de JID | `C0DZ.A0a(jid)` = `getType()==21`; `C0DZ.A0M` incluye el tipo 21 en el conjunto que también contiene grupos (18), lista de difusión (3), estado (5) etc. | isNewsletter / conjunto con capacidad multi-destinatario |
| Modelo local | `C2130898y` | rol, verificación, silencio, configuración de reacción, estado, recuentos |
| Roles | `C9U5` (enum local), `C9U4` (enum de string en wire) | sección 4 |
| Job de metadatos | `BaseMetadataNewsletterGraphqlJob`, `GetNewsletterAdminMetadataJob` | `NewsletterMetadata` / `NewsletterAdminMetadataQuery` |
| Job de actualización | `UpdateNewsletterGraphqlJob` | `NewsletterMetadataUpdate` |
| Job de creación/borrado | bajo `com.whatsapp.newsletter.editcreate`, `com.whatsapp.newsletter.delete` | `NewsletterCreate(Verified)` / `NewsletterDelete` |
| Obtención de mensajes | `GetNewsletterMessagesJob`, `GetNewsletterMessagesUpdatesJob`, `GetNewsletterMyAddOnMessagesJob`, `SendNewsletterMessageJob`, `SendViewReceiptJob` | `com.whatsapp.newsletter.messages.job` |
| Obtención de estados (actualizaciones del canal) | `GetNewsletterStatusesJob`, `GetNewsletterStatusUpdatesJob`, `GetStatusMyAddOnsJob` | `com.whatsapp.newsletter.status.job` |
| Constructor de IQ | `C9EN` (constructores con `xmlns="newsletter"`), `C9E2` (conjuntos de valores de view-role / child-node) | sección 6 |
| Envío de invitación de admin | `C9m6` (`UserActionsNewsletterMessaging`), `C213489Am` | sección 5.4 |
| Almacén de reacciones | `C12H`, `C23768ANd` → tabla `newsletter_message_reaction` | sección 7 |

---

## 2. JID y dominio

### 2.1 Parseo (found, `C0DL.A03`)

```java
// X.0DL (C0DL)
public C1Y7 A03(String str, String str2) throws C09B {
    String strTrim = str.trim();
    if (strTrim.isEmpty() || "0".equals(strTrim) || strTrim.indexOf("0") == 0)
        throw new C09B("Identifier must be a valid number starting with non-zero");
    if (!"newsletter".equals(str2)) throw new C09B(...);
    // cache lookup/insert, returns C1Y7(str)
}
```

`C1Y7.getServer()` devuelve el string literal `"newsletter"`; `getType()` devuelve `21`. La misma regla de id numérico sin cero inicial que otros tipos de JID multiparte (grupos, listas de difusión — ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §2.1). El router genérico de JID `C0DZ.A01` cae en `C1Y7.A03.A02(str)` como su caso por defecto cuando el string no es un singleton conocido, ni un `UserJid`, ni un `GroupJid` — es decir, `@newsletter` es el dominio de respaldo en ese parser (found).

### 2.2 Pertenencia al conjunto de tipos (found, `C0DZ.java`)

```java
public static boolean A0a(Jid jid) { return jid != null && jid.getType() == 21; }   // isNewsletter
public static boolean A0M(Jid jid) {
    int type = jid.getType();
    return type==0||type==1||type==18||type==22||type==3||type==7||type==21||type==26||type==28;
}
```
`A0a` es el predicado dedicado de newsletter. `A0M` agrupa el tipo 21 junto con grupos (18/22), lista de difusión (3), comunidad (7) y otros en un conjunto más amplio de "capacidad multi-participante" (el propósito de la agrupación exacta no se rastreó por completo; se infiere que habilita maquinaria compartida de participantes/sesión).

---

## 3. Seguir / dejar de seguir

Seguir **no** es una suscripción de stanza; es una mutación `w:mex`, y el rol local (`C9U5`) cambia entre `GUEST` y `SUBSCRIBED`.

| Operación | doc_id | Variables (found) |
|-----------|--------|--------------------|
| `NewsletterJoin` | `24658527423838739` | `entry_point`, `record`, `recipient_account_id`, `sessions`, `jid`, `fetch_and_validate_vname`, `call_offer`, `request_bottom_sheet_fragment` |
| `NewsletterLeave` | `25758579043742316` | forma idéntica a `NewsletterJoin` |

Ambas se construyen con la misma clase, `X/RunnableC24381AnW.java` (found). El conjunto de variables compartido (`entry_point`, `call_offer`, `request_bottom_sheet_fragment`) sugiere que join/leave reutilizan un wrapper de mutación genérico de "acción de chat" usado también para llamadas y acciones disparadas desde bottom-sheet en otras partes de la app (inferred).

Transiciones de rol local en el objeto `C2130898y` ("NewsletterInfo"):

| Helper | Condición | Significado |
|--------|-----------|-------------|
| `A0p()` | `!muted && role==ADMIN` | es admin |
| `A0q()` | `!muted && (role==ADMIN \|\| role==OWNER)` | es admin u owner |
| `A0r()` | `role==SUBSCRIBED` | está siguiendo |
| `A0s()` | `role==GUEST` | no sigue (se usa para forzar `fetch_viewer_metadata=true` en una actualización de metadatos — found en `BaseMetadataNewsletterGraphqlJob`) |
| `A0u()` | `!muted && role==OWNER` | es owner |

String de error en la UI al fallar el follow: `str1c0d` "Couldn't follow channel", `str1c0e` "Couldn't follow channel. Check your device's internet connection and try again." (found, `res/values/strings.xml`).

---

## 4. Roles

Existen dos enums de rol paralelos: un enum local persistido y un enum de string en wire usado en variables/respuestas de GraphQL.

### 4.1 Rol local (found, `C9U5`)

```java
GUEST=0 (A03), SUBSCRIBED=1 (A05), ADMIN=2 (A02), OWNER=3 (A04)
```
`C9U5.A00()` mapea ordinal → un rango de prioridad: GUEST→4, SUBSCRIBED→3, ADMIN→2, OWNER→1 (menor = más privilegiado; propósito — orden de clasificación para listas de admin — inferred).

### 4.2 Rol en wire (found, `C9U4`, `serverValue` = nombre del enum)

```
UNSET_OR_UNRECOGNIZED_ENUM_VALUE, ADMIN, GUEST, OWNER, SUBSCRIBER
```
Se usa como el valor del atributo `view_role` en el child `smax:any` de los IQs XMPP de newsletter (sección 6) y como el valor `viewer_metadata.role` de GraphQL (sección 8).

### 4.3 Capacidades y traspaso

| Acción | Operación GraphQL | doc_id |
|--------|-----------|--------|
| Invitar a un usuario como admin | `NewsletterAdminInvite` | `26278681041745438` |
| Revocar una invitación de admin pendiente | `NewsletterAdminInviteRevoke` | `24369392486051948` |
| Aceptar una invitación de admin | `NewsletterAcceptAdminInvite` | `24934958956134858` |
| Degradar a un admin | `NewsletterAdminDemote` | `25054538847517281` |
| Transferir la propiedad | `NewsletterChangeOwner` | `24737692515842078` |
| Obtención masiva de perfiles de admin | `NewsletterAdminProfilesQuery` | `28089989690595314` |
| Actualización de perfil de admin (nombre/foto) | `NewsletterAdminProfileUpdate` | `25959584293627630` |
| Metadatos de admin (completos, campos solo-admin) | `NewsletterAdminMetadataQuery` | `26882701001369256` |
| Gate de capacidades | `NewslettersAdminCapabilitiesQuery` | `27579307995002556` |

Enum de acción del flujo de invitación de admin (found, `EnumC215899Sc`, usado por `AdminInviteErrorDialog`): `NOT_SUPPORTED=0`, `INVITE=1`, `ACCEPT_INVITE=2`, `REVOKE=3`, `DISMISS=4`.

Strings de error en la UI (found): `str0095` "Couldn't accept the admin invite. Please try again.", `str106c`/`str2bed` "Couldn't transfer ownership. Please try again(.)/ later.", `str2300`/`str2abd` "Channel admin invite", `str22fb` "Invite %s as admin?", `str2bd8` "Invite as channel admin".

---

## 5. Invitación de admin — mensaje cliente a cliente, no solo GraphQL

El flujo de invitación de admin tiene **dos** mecanismos separados que se ejecutan ambos: una mutación MEX (`NewsletterAdminInvite`, concesión del lado servidor) y un **mensaje 1:1 de extremo a extremo** normal que lleva el payload de la invitación al invitado, construido independientemente de MEX.

### 5.1 Proto (found, confirma y amplía el material de partida de `Messages/newsletterAdminInviteMessage`)

`Message.newsletterAdminInviteMessage` — campo **78** de `Message` (`C30628DTw`), tipo `NewsletterAdminInviteMessage` (ofuscado `C30596DSq` en 2.26.41.6; las constantes de JADX están en la propia clase, no en el número de campo de `Message`, ya que la constante del campo admin-invite no estaba en el conjunto grepeado; el campo 78 coincide con una referencia anterior de WAProto.proto y queda corroborado de forma independiente porque todos los demás campos abajo resuelven exactamente como se documenta):

| Campo | Número | Tipo |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `inviteExpiration` | **5** | int64 |
| `contextInfo` | **6** | `ContextInfo` |

Constantes de número de campo confirmadas `CAPTION_FIELD_NUMBER=4`, `CONTEXT_INFO_FIELD_NUMBER=6`, `INVITE_EXPIRATION_FIELD_NUMBER=5`, `JPEG_THUMBNAIL_FIELD_NUMBER=3`, `NEWSLETTER_JID_FIELD_NUMBER=1`, `NEWSLETTER_NAME_FIELD_NUMBER=2` leídas directamente de `C30596DSq` (found) — coincide exactamente con un mapa de campos anterior para esta versión.

### 5.2 Ruta de envío (found, `C9m6` = `UserActionsNewsletterMessaging`)

```java
public final void A00(Context context, C1Y7 c1y7, String name, String caption, HashMap userJidToExpiration) {
    byte[] thumbnail = A01(context, c1y7);           // JPEG of the channel picture, quality 80
    for (entry in userJidToExpiration) {
        C213489Am item = new C213489Am(..., 94, ...); // message-type tag 94
        item.A01 = c1y7;          // newsletterJid
        item.A03 = name;          // newsletterName
        item.A00 = entry.value;   // inviteExpiration
        item.A02 = caption;
        item.A0O(thumbnail, false);
        // enqueued as a normal E2E message to the invitee's UserJid
    }
}
```
Línea de log: `"UserActionsNewsletterMessaging/userActionSendNewsletterAdminInviteMessages"`. Se envía un mensaje por cada invitado, cada uno con su propio timestamp de expiración — es decir, la invitación es un **mensaje E2E por destinatario**, mientras que la operación MEX `NewsletterAdminInvite` (lado servidor) es el registro de concesión autoritativo (relación inferida entre las dos rutas; ambas están presentes en el código, el orden/dependencia no se rastreó).

### 5.3 Aceptación

El cliente del invitado llama a `NewsletterAcceptAdminInvite` (MEX). Su solicitud ya lleva el conjunto completo de variables de obtención de metadatos (`fetch_followers_count`, `fetch_state`, `fetch_verification`, `fetch_viewer_metadata`, …) — aceptar una invitación y volver a obtener los metadatos del canal son un único round trip (found, variables de `X/AbstractC23610Aaw.java`).

---

## 6. Otros mensajes de newsletter: invitación de seguidor, perfil de admin, programado

### 6.1 `newsletterFollowerInviteMessage` / `newsletterFollowerInviteMessageV2`

Confirmado en 2.26.41.6 exactamente como indica el material de partida, y re-verificado aquí de forma independiente: ambos campos de `Message` existen (`NEWSLETTER_FOLLOWER_INVITE_MESSAGE_FIELD_NUMBER` = **108**, `NEWSLETTER_FOLLOWER_INVITE_MESSAGE_V2_FIELD_NUMBER` = **113**, ambos encontrados como constantes con nombre en `C30628DTw`), y **ambos se mapean al mismo tipo de submensaje**, `C30585DSf`:

| Campo | Número | Tipo |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `contextInfo` | **5** | `ContextInfo` |

Por qué existen ambos números de campo para un solo tipo sigue siendo **unknown** — tampoco se encontró una separación de comportamiento en la capa Java en esta pasada (consistente con un hallazgo anterior).

### 6.2 `newsletterAdminProfileMessage` / `newsletterAdminProfileStatusMessage` / `newsletterScheduledMessage`

Los tres confirmados presentes como constantes con nombre en `C30628DTw` (`NEWSLETTER_ADMIN_PROFILE_MESSAGE_FIELD_NUMBER` = **116**, `NEWSLETTER_ADMIN_PROFILE_STATUS_MESSAGE_FIELD_NUMBER` = **126**, `NEWSLETTER_SCHEDULED_MESSAGE_FIELD_NUMBER` = **132**), y los tres resuelven al mismo tipo de wrapper genérico de un solo campo, `BD2` (= `FutureProofMessage`):

```java
public final class BD2 { public C30628DTw message_; }   // field "message", number 1, type Message (recursive)
```

No existe ninguna clase de renderizado/validación específica de campo para ninguno de los tres (found, coincide con una nota anterior para `newsletterAdminProfileMessage` y `newsletterScheduledMessage`). `newsletterScheduledMessage` sí tiene una superficie dedicada no-mensaje: la tabla local `newsletter_scheduled_message` (`chat_row_id`, `scheduled_server_id`, indexada única) y el child de IQ en wire `<scheduled_messages/>` (sección 6.3) — la *funcionalidad* de programación es real y está rastreada; solo el campo proto `Message.newsletterScheduledMessage` en sí permanece como un wrapper sin expandir.

### 6.3 Tablas locales relacionadas

`newsletter_scheduled_message`, `newsletter_admin_profile` (`chat_row_id`, `admin_profile_id`, `timestamp`) respaldan `NewsletterAdminProfilesQuery`/`NewsletterAdminProfileUpdate` y la UI de programación respectivamente (found, `C0SG.java`, `C0S3.java`).

---

## 7. Publicaciones del canal: obtención, envío, reacciones, recuentos de vistas

### 7.1 Namespace IQ XMPP `newsletter` (found, `C9EN`)

La obtención de contenido y algunas acciones de escritura usan un namespace IQ dedicado, separado de MEX:

```xml
<iq xmlns="newsletter" type="get" to="<jid>@newsletter" id="…">
  <messages count="N">
    <smax:any type="jid" jid="<jid>@newsletter" view_role="admin|guest|owner|subscriber"/>
    <before count="N"/> <!-- or <after count="N"/> -->
  </messages>
</iq>
```

| Child element | Constructor | Propósito |
|---------------|-------------|-----------|
| `<messages count/>` + `<before>`/`<after>` | `C9EN(C9EB, C9E2, id, count)` | paginar publicaciones del canal |
| `<message_updates count since/>` | `C9EN(C1Y7, C9E8, Long, id, count)` | sincronización delta de publicaciones editadas/eliminadas |
| `<statuses count/>` | `C9EN(C9E9, C9E2, id, count)` | obtención de estados/actualizaciones del canal |
| `<status_updates count since/>` | `C9EN(C1Y7, C9EA, Long, id, count)` | sincronización delta de publicaciones de estado |
| `<scheduled_messages count/>` | `C9EN(C1Y7, C31085Dfd, id, count)` | publicaciones programadas pendientes |
| `<question_responses server_id count/>` (plain and `type="status"`) | `C9EN(...)` | respuestas de encuesta/pregunta en una publicación |
| `<my_question_responses server_id/>` | `C9EN(C1Y7, String, long)` | respuestas propias del llamador |
| `<my_addons type="status" limit jid/>` | `C9EN(C1Y7, String, int, long)` | reacciones/add-ons propios del llamador |
| `<live_updates/>` (`type="set"`) | `C9EN(C1Y7, String)` | suscribirse a push en vivo para un canal |

El atributo `view_role` en `smax:any` lleva el string de rol `C9U4` propio del llamador (admin/guest/owner/subscriber) en cada IQ de obtención de contenido — el servidor parece filtrar el contenido de la respuesta (p. ej. campos solo-admin) por solicitud en lugar de solo por estado de sesión (inferred).

### 7.2 Envío (found, `SendNewsletterMessageJob`) y recibos de vista

Publicar en un canal reutiliza el pipeline de envío estándar (no se detalla más aquí; el job envuelve la maquinaria normal de la stanza `<message>`). Ver una publicación es explícito y separado de la entrega/recibos de lectura:

```java
// com.whatsapp.newsletter.messages.job.SendViewReceiptJob
<receipt to="<jid>@newsletter" id="…" type="view">
  <list><item server_id="…"/> …</list>
</receipt>
```
Un recibo `view` agrupa varios ids de mensaje del servidor. Este es el mecanismo que alimenta el **recuento de vistas** por publicación mostrado en la UI del canal (found; el contador mismo se agrega en el servidor — el cliente solo lo reporta, nunca lee de vuelta un recuento mediante este IQ).

### 7.3 Reacciones (found)

Las reacciones en las publicaciones del canal están **agregadas, no atribuidas** en el almacenamiento local:

```sql
CREATE UNIQUE INDEX newsletter_message_reaction_index
  ON newsletter_message_reaction (message_row_id, reaction);
-- columns include: reaction, reaction_count
```
es decir, una fila por par `(mensaje, emoji)` con un contador acumulado, no una fila por usuario que reacciona — lo que coincide con la UI del canal mostrando un recuento agregado por emoji en lugar de una lista de quienes reaccionaron, como ocurre con los usuarios normales. `newsletter_my_reaction_orphan_message` (`chat_row_id`, `server_message_id`, indexada única) guarda la reacción **propia** del llamador cuando llega antes de la publicación a la que apunta, para reconciliarse una vez que la publicación aterriza.

Quién reaccionó solo es visible para los admins, mediante una consulta MEX dedicada:

| Operación | doc_id | Variables |
|-----------|--------|-----------|
| `NewsletterReactionSendersList` | `25219734117717032` | `server_id` |

La política de reacciones es configurable por canal (sección 8.2, `reaction_codes`): `ALL`, `BASIC`, `BLOCKLIST`, `NONE` (strings en wire, ver `C9U3`/`C9TA` abajo).

### 7.4 Recuentos de seguidores / vistas en los metadatos

`thread_metadata.followers_count` se devuelve como parte de `NewsletterMetadata` (sección 8.1). También existe una operación paginada dedicada:

| Operación | doc_id | Variables |
|-----------|--------|-----------|
| `NewsletterFollowers` | `25646542368289354` | `newsletter_id`, `count` |

Los recuentos de vistas por publicación no se devuelven mediante una operación independiente documentada en esta pasada; se infiere que viven dentro de los metadatos por mensaje devueltos por el IQ `messages`/`message_updates` (sección 7.1), que no se expandió más aquí (nombre de campo exacto unknown).

---

## 8. Metadatos del canal (forma de la respuesta GraphQL)

### 8.1 Respuesta `NewsletterMetadata` (found, cadena `C208048tR → C208038tQ → C208028tP`, nodo GraphQL `xwa2_newsletter`)

```
xwa2_newsletter {
  id
  refresh_after_interval_sec
  state { type }                                    // C9UA
  status_metadata { last_status_sent_time, last_status_server_id }
  thread_metadata {
    creation_time
    description { text, id }
    followers_count
    handle
    invite                                           // invite code / link token
    name { text, id }
    picture { direct_path, type, url, id }
    pinned_messages[]
    preview
    settings { reaction_codes { value } }            // C9U3
    verification                                     // EnumC216369Tx
    verification_source                              // EnumC216219Ti
    wamo_sub { plan_id }
  }
  viewer_metadata {
    role                                             // C9U4
    settings[]                                       // { type, value } = EnumC216349Tv / EnumC216359Tw
    wamo_sub_status                                  // EnumC216229Tj
  }
}
```

### 8.2 Enums (found)

| Enum | Valores (strings de valor-servidor donde aplica) |
|------|---|
| `state.type` (`C9UA`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `DELETED`, `GEOSUSPENDED`, `NON_EXISTING`, `SUSPENDED` |
| `verification` (`EnumC216369Tx`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `UNVERIFIED`, `VERIFIED` |
| `verification_source` (`EnumC216219Ti`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `LEGACY_MANUAL_REVIEW`, `META_VERIFIED_SUBSCRIPTION` |
| `viewer_metadata.role` (`C9U4`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ADMIN`, `GUEST`, `OWNER`, `SUBSCRIBER` |
| `wamo_sub_status` (`EnumC216229Tj`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `INACTIVE` |
| `settings[].type` (`EnumC216349Tv`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `MUTE_ADMIN_ACTIVITY`, `MUTE_FOLLOWER_ACTIVITY` |
| `settings[].value` (`EnumC216359Tw`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `OFF`, `ON` |
| `reaction_codes.value` (`C9U3`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `BASIC`, `BLOCKLIST`, `NONE` |

Espejos locales en `C2130898y` ("NewsletterInfo"): estado de verificación `EnumC216079Su` (`NOT_VERIFIED=0`, `VERIFIED=1`), fuente de verificación `C9T1` (`UNKNOWN_VERIFICATION_SOURCE=0`, `META_VERIFIED_SUBSCRIPTION=1`, `LEGACY_MANUAL_REVIEW=2`), estado de enforcement `C9T2` (`NOT_ENFORCED`, `SUSPENDED`, `GEOSUSPENDED` — su lectura se filtra detrás del flag **3877** en `A0w`/`A0x`), estado local "activo" `C9T3` (`NOT_SET`, `INACTIVE`, `ACTIVE`), progreso de migración/creación `C9T9` (`NOT_STARTED`, `IN_PROGRESS`, `FAILED`, `COMPLETED`), visibilidad en el directorio `EnumC216039Sq` (`PUBLIC`, `PRIVATE`) y configuración local de reacción `C9TA` (`DEFAULT=0`→wire `"BASIC"`, `ALL=1`→`"ALL"`, `NONE=2`→`"NONE"`, `BLOCKLIST=3`→`"BLOCKLIST"` — mapeo leído de `UpdateNewsletterGraphqlJob.A0M`).

### 8.3 Actualización (found, `UpdateNewsletterGraphqlJob` → `NewsletterMetadataUpdate`)

```js
// GraphQl input built for doc_id 27150690864552229
updates: {
  description?: string,   // "" clears
  name?: string,
  picture?: base64,        // "" clears
  admin_profiles_enabled?: { settings: { admin_profiles_enabled, reaction_codes: { value: "ALL"|"BASIC"|"NONE"|"BLOCKLIST" } } }
}
newsletter_id: <jid>
fetch_image: true, fetch_preview: true, fetch_name: true,
fetch_viewer_metadata / fetch_state / fetch_verification / fetch_followers_count: <bool, usually mirrors viewer role>
```

### 8.4 Strings de verificación en la UI (found)

`str136f` "New verified channel", `str2be2`/`str2be3` "Create verified channel"/icon, `str2c51` "Verified channels", `str2c78` "Your verified badge will be removed from this channel. Your Meta Verified subscription will remain active.", `str2ca9` "Sorry, you cannot change the name of a verified channel from the app. Please contact customer support for assistance." — es decir, los canales verificados tienen un nombre inmutable aplicado por el servidor (solo UX del lado cliente; la aplicación del lado servidor es unknown).

---

## 9. Operaciones GraphQL / MEX de newsletter (doc_ids)

Todos los doc_ids siguientes se re-verificaron de forma independiente para este build contra `assets/whatsapp-android-mex_client_persist_ids.json` dentro de `WhatsApp_2.26.41.6.apk` (found — los doc_ids son entradas de asset estáticas, no ofuscadas, y son estables a través de la comparación de versiones intentada aquí). Existen 46 operaciones `Newsletter*` en ese asset en total; las que no se detallan en otra parte de este reporte:

| Operación | doc_id | Propósito (inferido del nombre/variables) |
|-----------|--------|------------------------------------------|
| `NewsletterCreate` | `27009199332109318` | crear un canal |
| `NewsletterCreateVerified` | `27777918425146464` | crear un canal pre-verificado (cuentas privilegiadas) |
| `NewsletterDelete` | `31838460859131915` | eliminar un canal |
| `NewsletterUpdateVerification` | `27133493439664458` | solicitar/actualizar el estado de verificación |
| `NewsletterHide` / `NewsletterUnhide` | `25033614912931367` / `24551592861177484` | alternar la visibilidad en el directorio (local `EnumC216039Sq`) |
| `NewsletterFollowing` | `26856957210673444` | lista de canales que sigue la cuenta |
| `NewsletterDirectoryList` / `Search` / `CategoryPreview` | `27480627564903390` / `27887355094203575` / `27432651036395658` | navegación pública del directorio |
| `NewsletterSimilar` / `NewsletterRecommended` | `36410329795280256` / `26638880912457992` | descubrimiento |
| `NewsletterInsights` | `24672564052397921` | analítica del owner/admin |
| `NewsletterPinMessages` / `NewsletterUnpinMessages` | `28521965914059511` / `37386851567568720` | gestión de publicaciones fijadas (`message_ids`) |
| `NewsletterBlockUser` | `25106066249006236` | bloquear a un seguidor |
| `NewsletterLogExposures` | `24606408825709914` | telemetría de impresiones del directorio |
| `NewsletterLinkPreviewCheck` | `24188786150796507` | validar dominios de vista previa de enlaces en publicaciones |
| `NewsletterPollVoterList` | `24803802869271956` | votantes de encuesta en una publicación (`jid`, `vote_hash`) |
| `NewsletterQuestionResponseStateUpdate` | `24896618076668076` | estado de moderación de preguntas y respuestas |
| `NewsletterLabelAiContent` / `NewsletterLabelPaidPartnership` | `27470054215955630` / `26221505494211174` | etiqueta por publicación de contenido generado por IA / asociación pagada |
| `NewsletterChangeWamoSub` / `Enable`/`DisableWamoSub` | `25201342542835866` / `25122474967344830` / `31916794074578680` | estado de suscripción de monetización de WhatsApp |
| `NewsletterUserReports` / `NewsletterCreateReportAppeal` | `27149305681394065` / `27792557363683798` | reporte de abuso / apelación |
| `NewsletterEnforcements` / `NewsletterEnforcementAlertStates` | `27089116857425014` / `27640745535604048` | estado de enforcement/suspensión (paquete propio `com.whatsapp.newsletterenforcements`) |
| `NewsletterUpdateUserSetting` | `24935528202764688` | preferencia de UI por usuario (p. ej. contador de tooltip del selector de contactos) |
| `FetchNewsletterRankingFeatures` | `24742757908756088` | obtención de señales de ranking (directorio/recomendación) |

Todas son IQs `w:mex` (`type="get"`), schema `whatsapp_mex`, transporte confirmado por el patrón de llamada compartido `C16880is`/`TreeWithGraphQL` visto en §5–8 (found). Las formas de respuesta más allá de `NewsletterMetadata` de §8 no se expandieron en esta pasada (unknown).

---

## 10. Almacenamiento

| Tabla | Columnas clave (found) |
|-------|----------------------|
| `newsletter` | `membership` (indexada), `invite_code` (indexada) |
| `newsletter_message` | única en `(chat_row_id, server_message_id)`; `is_autodelete_eligible` (indexada) |
| `newsletter_message_reaction` | única en `(message_row_id, reaction)`; `reaction`, `reaction_count` |
| `newsletter_my_reaction_orphan_message` | única en `(chat_row_id, server_message_id)` — reacción propia del llamador que llega antes de su publicación objetivo |
| `newsletter_admin_profile` | única en `(chat_row_id, admin_profile_id)`; `timestamp` (indexada) |
| `newsletter_subscribers` | indexada en `(chat_row_id, type_of_fetch)` |
| `newsletter_scheduled_message` | única en `(chat_row_id, scheduled_server_id)` |
| `newsletter_interaction` | indexada en `timestamp_ms` y `(newsletter_jid_row_id, timestamp_ms)` |
| `newsletter_linked_account` | indexada en `chat_row_id` |
| `newsletter_pinned_message` | indexada en `(chat_row_id, pin_timestamp_ms)` |
| `newsletter_media_clear` | única en `(chat_row_id, media_type)` |

La infraestructura de chat compartida (`chat`/`chat_view`, columnas core de `message`) se reutiliza como para cualquier chat tipado como `Jid`, igual que grupos/listas de difusión (ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §3.5) — no se detalla de nuevo aquí.

---

## 11. Feature flags

IDs leídos en los puntos de llamada en `com.whatsapp.newsletter.*`; no todos los valores por defecto se resolvieron en esta pasada (marcados donde se conocen).

| ID | Controla |
|----|----------|
| **3877** | filtra la lectura de los helpers locales de estado de enforcement `A0w`/`A0x` (comprobaciones `SUSPENDED`/`GEOSUSPENDED`) en `C2130898y` |
| **1777** | selector de país en los filtros del directorio |
| **5276** | vista de identidad del canal durante la UI de migración newsletter→algo |
| **6445** | `ShareNewsletterInviteLinkActivity` |
| **6618** | `ViewNewsletterProfilePhoto` |
| **7237** | `NewsletterStatusView` |
| **9096** | `SendNewsletterMessageJob` |
| **12989** | `NewsletterDirectoryCategoriesActivity` |
| **15754** | marcador del perf-tracker "messages_fetch_end" en `GetNewsletterMessagesJob` |
| **17985** | `ForwardCounterAcsRepository` (contador de publicaciones reenviadas) |
| **19889** | `ForwardCounterApi` |
| **23797** | `NewsletterDescriptionView` |

Los valores por defecto exactos y el alcance completo del comportamiento filtrado no se rastrearon más allá de "la clase es alcanzable solo cuando el flag está activo" (inferido de la forma del punto de llamada); tratar esta tabla como un mapa de dónde mirar, no como valores por defecto on/off confirmados (unknown para la mayoría de las filas).

---

## 12. Casos de error

| Síntoma | Causa | Arreglo / comportamiento esperado |
|---------|-------|--------------------------|
| "Couldn't follow channel" (`str1c0d`/`str1c0e`) | `NewsletterJoin` falló o no hay conectividad | reintentar; comprobar la conexión |
| "Couldn't accept the admin invite. Please try again." (`str0095`) | `NewsletterAcceptAdminInvite` falló | reintentar |
| "Couldn't transfer ownership…" (`str106c`/`str2bed`) | `NewsletterChangeOwner` falló | reintentar más tarde |
| "Sorry, you cannot change the name of a verified channel from the app." (`str2ca9`) | el canal está `VERIFIED`; nombre inmutable del lado cliente | contactar con soporte (lado servidor; enforcement exacto unknown) |
| La reacción propia no tiene publicación coincidente aún | la stanza/evento de reacción llegó antes que la propia entrega de la publicación | se retiene en `newsletter_my_reaction_orphan_message` hasta que la publicación aterriza, luego se reconcilia |
| `state.type` = `SUSPENDED`/`GEOSUSPENDED` | acción de enforcement contra el canal | la obtención de contenido sigue devolviendo `state`; publicar/acciones de admin presumiblemente bloqueadas del lado servidor (gate exacto unknown) |
| `state.type` = `DELETED`/`NON_EXISTING` | canal eliminado o nunca existió | el cliente debería descartar la fila local de `newsletter` (ruta de aplicación no rastreada) |
| Acción de invitación de admin = `NOT_SUPPORTED` (`EnumC215899Sc`) | invitar/aceptar/revocar intentado en un contexto no soportado (p. ej. rol, build) | diálogo de error genérico, sin botón de reintentar (`str5735`) |

---

## 13. Distinciones clave

| No confundir | Diferencia |
|----------------|------------|
| Newsletter (`@newsletter`, tipo 21) vs lista de difusión (`@broadcast`, tipo 3) | newsletter: almacenada en servidor, no E2E, modelo público de seguir, roles; lista de difusión: fan-out E2E con sender-key solo a contactos guardados — ver [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) |
| IQ `xmlns="newsletter"` vs operaciones GraphQL `Newsletter*` de `w:mex` | IQ = obtención/paginación/suscripción de contenido (mensajes, estados, programados, live-updates); MEX = metadatos, roles, directorio, moderación, monetización |
| `newsletterAdminInviteMessage` (mensaje E2E 1:1, campo 78) vs `NewsletterAdminInvite` (mutación MEX) | el mensaje es la notificación por destinatario con su propia expiración; la operación MEX es la concesión del lado servidor — ambas existen, relación inferida |
| `newsletterFollowerInviteMessage` (campo 108) vs `newsletterFollowerInviteMessageV2` (campo 113) | tipo de payload idéntico (`C30585DSf`); razón de la duplicación unknown |
| Rol local `C9U5` (GUEST/SUBSCRIBED/ADMIN/OWNER) vs rol en wire `C9U4` (…GUEST/ADMIN/OWNER/SUBSCRIBER) | los mismos cuatro roles, distinto orden ordinal y distinto orden/mayúsculas de string — no asumir compatibilidad ordinal |
| Valor en wire de `reaction_codes` (`ALL`/`BASIC`/`BLOCKLIST`/`NONE`, de `C9U3`) vs el mapa local ordinal-a-string de `C9TA` | el ordinal local 0 (`DEFAULT`) serializa al string en wire `"BASIC"`, no `"DEFAULT"` |
| Almacenamiento de reacciones por publicación (`newsletter_message_reaction`, recuento agregado) vs reacciones de mensaje normales | los canales almacenan una fila por par `(mensaje, emoji)` con un contador, no una fila por usuario que reacciona |

---

## 14. Flujo completo

```
[Admin]  create channel
    │   NewsletterCreate / NewsletterCreateVerified (MEX) ──► [WA Server] allocates <id>@newsletter
    ▼
[Admin]  set name/description/picture, reaction policy
    │   UpdateNewsletterGraphqlJob ──► NewsletterMetadataUpdate (MEX)
    ▼
[Admin]  invite co-admin
    │   C9m6: per-recipient E2E message (newsletterAdminInviteMessage, field 78, own expiration)
    │   + NewsletterAdminInvite (MEX, server-side grant)
    ▼
[Invitee]  NewsletterAcceptAdminInvite (MEX) ──► role GUEST/SUBSCRIBED → ADMIN (C9U5)

[User]  discover channel (directory / shared link https://whatsapp.com/channel/<code>)
    ▼
[Client]  NewsletterJoin (MEX) ──► role → SUBSCRIBED
    ▼
[Client]  <iq xmlns="newsletter" type="get"><messages count view_role=subscriber/></iq>
    │◄── posts, paginated by before/after server_id
    ▼
[User]  views post ──► <receipt type="view"><list><item server_id/></list></receipt> (view count)
[User]  reacts ──► newsletter_message_reaction (aggregate count, own reaction may be orphaned until post lands)

[Admin]  moderates: NewsletterReactionSendersList (who reacted), NewsletterBlockUser,
         NewsletterPinMessages/Unpin, NewsletterUpdateVerification, NewsletterChangeOwner
    ▼
[Owner]  delete channel ──► NewsletterDelete (MEX)
```

---

## 15. Incógnitas

| Elemento | Razón |
|------|--------|
| Relación/orden exacto entre el mensaje E2E de invitación de admin y la concesión MEX `NewsletterAdminInvite` | ambos existen en el código; cuál es autoritativo, o si uno dispara al otro, no se rastreó |
| Por qué `newsletterFollowerInviteMessage` (108) y `…V2` (113) comparten un tipo proto | no se encontró separación de comportamiento en la capa Java |
| Nombre/ubicación exacta del campo de recuento de vistas por publicación en la respuesta de obtención de mensajes | se infiere que existe dentro del payload del IQ `messages`/`message_updates`; no se expandió |
| Aplicación del lado servidor del nombre inmutable en canales verificados | el cliente solo muestra un string de error estático |
| Forma completa de la respuesta de la mayoría de las operaciones MEX más allá de `NewsletterMetadata` | no se leyó en esta pasada |
| Valores por defecto para la mayoría de los feature flags en §11 | solo alcanzabilidad de clase, estado por defecto no confirmado |
| Tráfico / comportamiento del servidor en vivo | nada capturado; solo análisis estático |

---

## 16. Baileys

No cubierto: `baron-baileys-v2` (el fork de Baileys usado como línea base de comparación en los otros reportes de este repositorio) no tiene una implementación confirmada y verificada contra este APK de newsletter/canal con la que comparar al momento de escribir esto. No se inspeccionó código del lado de Baileys para este reporte. Añadir una sección de Baileys sin hechos verificados violaría las reglas de evidencia de este repositorio. Si/cuando `baron-baileys-v2` incorpore soporte de newsletter, esta sección debería completarse contra el JID (tipo 21, servidor `newsletter`), los IQs `xmlns="newsletter"` de §7.1, y los doc_ids MEX de §9.
