<!-- src-sha1: c9f42e3645bee848584358bb7a4660a293218e2e -->
# WhatsApp Eventos — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-01
**Alcance:** Eventos tipo calendario (`eventMessage`, `eventInviteMessage`, `eventCoverImage`), RSVP cifrado (`encEventResponseMessage` / `EventResponseMessage`), subsistema de app "Events v2" (`com.whatsapp.eventsv2.*`: DB local, sincronización GraphQL, notificaciones push MEX, pipeline de imagen de portada, enlace de invitación/QR), ciclo de vida (crear/editar/cancelar/eliminar/salir), estados de RSVP, reglas de visibilidad de invitados/ubicación, contexto de grupo vs 1:1 vs comunidad, restricción de dispositivo vinculado, catálogo de operaciones GraphQL, recordatorios

---

## 1. Qué es

Un "Evento" es un objeto tipo calendario (nombre, descripción, ventana horaria, ubicación, enlace opcional de videollamada/llamada de voz) que puede publicarse en un chat 1:1, un grupo, o compartirse mediante un enlace/QR independiente, con invitados que pueden responder RSVP (Going / Maybe / Not going). La función se transporta por dos superficies de red a la vez: un mensaje de chat ordinario cifrado E2E (`Message.eventMessage` / `Message.eventInviteMessage`) que renderiza la tarjeta de invitación en la transcripción, y un plano de control paralelo GraphQL + push MEX (`com.whatsapp.eventsv2.*`, paquete nuevo en 2.26.41.6) que mantiene una base de datos local de eventos sincronizada de forma independiente al historial del chat. La criptografía del RSVP (caso de uso HKDF "Event Response", AES-GCM) se comparte con reacciones/encuestas/comentarios y está documentada en `WA_MESSAGE_SECRETS.md`; este informe cubre solo la capa de modelo de evento y ciclo de vida.

| Entidad | Campo de `Message` | Tipo (obf.) | Rol |
|--------|-----------------|-------------|------|
| `eventMessage` | **75** | `EventMessage` | evento base de calendario, publicado en un chat |
| `encEventResponseMessage` | **76** | `EncEventResponseMessage` (`DRN`) | seguimiento de RSVP cifrado |
| `eventCoverImage` | **85** | `FutureProofMessage` | wrapper genérico, transporta la foto de portada como un `imageMessage` anidado |
| `eventInviteMessage` | **122** | `EventInviteMessage` (`DTQ`) | tarjeta de invitación "Events v2", superconjunto de `eventMessage` |
| `eventResponses` (repetido) | **61**, en el equivalente a `WebMessageInfo` (`C30626DTu`) | `EventResponse` | resumen de RSVP por invitado transportado en la sincronización de historial |
| `eventAdditionalMetadata` | **64**, mismo host | `EventAdditionalMetadata` | un único bool `isStale` |

Todos los campos del proto y los campos de texto plano del RSVP a continuación se releyeron directamente de las clases de 2.26.41.6 (`DRP`, `DRN`, `DU9`, `E2D`, `C9T8` — **found**) y se verificaron contra el contenedor `Message` de nivel superior en `Tools/proto-extractor/research/2.26.41.6/whatsapp-deobfuscated.proto`. Niveles: **found** = leído en código/cadenas, **inferred** = deducido, **unknown** = no resuelto.

---

## 2. `EventMessage` (campo 75) — evento base

Sin cambios respecto al catálogo de la era 2.26.35.2; sigue teniendo 12 campos en 2.26.41.6.

| Campo | # | Tipo | Notas |
|-------|---|------|-------|
| `contextInfo` | 1 | `ContextInfo` | portador estándar de citas/menciones |
| `isCanceled` | 2 | bool | se establece con la acción de cancelar |
| `name` | 3 | string | título del evento |
| `description` | 4 | string | |
| `location` | 5 | `Message.LocationMessage` | pin de ubicación estática (lat/long/nombre/dirección), *no* en vivo |
| `joinLink` | 6 | string | URL de unión genérica (campo legado; superado por el enlace de invitación de Events v2 para eventos nuevos) |
| `startTime` | 7 | int64 | segundos unix |
| `endTime` | 8 | int64 | segundos unix |
| `extraGuestsAllowed` | 9 | bool | toggle "+1" |
| `isScheduleCall` | 10 | bool | mismo modelo usado para el punto de entrada "Schedule a call" |
| `hasReminder` | 11 | bool | |
| `reminderOffsetSec` | 12 | int64 | segundos antes de `startTime` |

`reminderOffsetSec` se completa desde un selector fijo (`EventReminderBottomSheet`, cadenas **found**): "Never", "Time of event", "15 minutes before", "30 minutes before", "1 hour before", "1 day before". El mapeo 0/900/1800/3600/86400 segundos es **inferred** (no leído como literal; la tabla opción-a-segundos del selector vive en una clase — `BXa`/`C27637BzN` — cuyo pool de constantes jadx no resolvió).

---

## 3. `EventInviteMessage` (campo 122, obf. `DTQ`) — invitación "Events v2"

Creció de 9 a 13 campos entre versiones; 2.26.41.6 trae los 13. **Corrección al material de partida**: el `Messages/eventInviteMessage/info.md` ya incorporado (capturado en 2.26.35.2) se detiene en el campo 9 (`callLink`) y le faltan los campos 10–13, confirmados presentes en este build mediante lectura directa de `DTQ`:

| Campo | # | Tipo | Añadido | Notas |
|-------|---|------|-------|-------|
| `contextInfo` | 1 | `ContextInfo` | base | |
| `eventId` | 2 | string | base | id de evento asignado por el servidor |
| `eventTitle` | 3 | string | base | |
| `jpegThumbnail` | 4 | bytes | base | miniatura de portada en línea |
| `startTime` | 5 | int64 | base | |
| `caption` | 6 | string | base | |
| `isCanceled` | 7 | bool | base | |
| `endTime` | 8 | int64 | base | |
| `callLink` | 9 | string | base | estilo `https://call.whatsapp.com/video/...` |
| `coverImageHandle` | 10 | string | 2.26.38.10 | referencia de media-handle, alternativa al `jpegThumbnail` en línea |
| `locationName` | 11 | string | 2.26.38.10 | etiqueta de ubicación legible |
| `lastUpdatedTsUsec` | 12 | int64 | 2.26.38.10 | microsegundos; avanza con cada `UpdateEvent` |
| `status` | 13 | int32 (enum abierto) | **2.26.41.6** | estado a nivel de evento; clase del enum no recuperable estáticamente |

`status` (13) es el único campo nuevo en el wire en esta versión. Los nombres de sus miembros de enum son **unknown** a nivel de proto — jadx no pudo recuperar la clase subyacente para este int32 de enum abierto. Sin embargo, el vocabulario de estado orientado a GraphQL usado para las variables relacionadas `rsvp_status`/`UpdateEvent.status` se recuperó de forma independiente (§6) y es un candidato plausible pero no confirmado para la misma semántica; no está probado que los dos compartan una representación en el wire.

---

## 4. `eventCoverImage` (campo 85) — wrapper de foto de portada

`FutureProofMessage { optional Message message = 1; }` — el mismo wrapper genérico usado para `lottieStickerMessage`, `statusMentionMessage`, etc. Sin campos específicos de evento; el `message` anidado transporta un `imageMessage` ordinario. El código consumidor (`EventCoverImageLoader`, `EventCoverImageThumbnailCreator`, `EventCoverImageUrlResolver`) lo trata como un adjunto de imagen normal — no se encontró validación adicional más allá del desempaquetado genérico del wrapper.

Events v2 también admite imágenes de portada **preestablecidas** (`EventPresetCoverImagesRepository`, catálogo obtenido por GraphQL, variables `cover_image_blob`/`is_preset_image` en `CreateEvent`/`UpdateEvent`) como alternativa a una foto subida por el usuario.

---

## 5. RSVP: `encEventResponseMessage` y `EventResponseMessage`

### 5.1 Forma en el wire (found, `DRN`/`DRP`/`E2D` leídos directamente)

| Portador | Campo | # | Tipo |
|---------|-------|---|------|
| `EncEventResponseMessage` (`DRN`, campo 76) | `eventCreationMessageKey` | 1 | `MessageKey` (`BD5`) |
| | `encPayload` | 2 | bytes |
| | `encIv` | 3 | bytes |
| `EventResponseMessage` (`DRP`, el texto plano AES-GCM) | `response` | 1 | enum `E2D` |
| | `timestampMs` | 2 | int64 |
| | `extraGuestCount` | 3 | int32 |

Valores de `E2D` (found, `E2D.java`): **0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE**.

Esto confirma directamente `WA_MESSAGE_SECRETS.md` §"encEventResponseMessage **76**" y resuelve un conflicto en el dump de proto auto-extraído (`Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`, que — debido a un bug de recuperación de nombre de campo señalado en su propio texto, "missing name slot at field #3" — lista `EventResponseMessage` como `timestampMs=1, extraGuestCount=2, field3=3`). La lectura directa de la clase (la cadena de orden de campos `BUILD_MESSAGE_INFO` de `DRP` y las constantes `RESPONSE_FIELD_NUMBER=1`/`TIMESTAMP_MS_FIELD_NUMBER=2`/`EXTRA_GUEST_COUNT_FIELD_NUMBER=3`) lo resuelve: **`response` es el campo 1, no el 3.**

### 5.2 Ruta de envío (found, `DU9.ADr`)

`DU9` (manejador del caso de uso de respuesta de evento, extiende `F2P`) construye un `DRP` a partir de un enum de nivel de app `C9T8` (`UNKNOWN=0, GOING=1, NOT_GOING=2, MAYBE=3` — numéricamente idéntico a `E2D`, confirmando que es un mirror 1:1 directo vía el conversor `EW0.A01`) más un timestamp y un int `extraGuestCount`, lo cifra con el caso de uso HKDF `"Event Response"` vía `MessageSecretCryptoHelper` (`C33285Eeb.A03`), y envuelve el ciphertext/IV/clave de mensaje original en un `DRN`. `AAl()` marca el stanza salvo con `<meta event_type="response">`. El detalle criptográfico (derivación HKDF, AES-GCM, AAD = `targetId‖0x00‖modifier`, reintento sender/LID) **no se repite aquí** — ver `WA_MESSAGE_SECRETS.md` §2–9, 16.

### 5.3 Tres enums adicionales con forma de RSVP (found) — una trampa

Además del enum en el wire `E2D` y su mirror `C9T8`, la app define al menos otras tres enumeraciones de estado RSVP con **ordenamientos de miembros distintos**, cada una usada en una capa distinta:

| Enum (obf.) | Miembros (ordinal) | Usado para |
|---|---|---|
| `E2D` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | texto plano en el wire `EventResponseMessage.response` |
| `C9T8` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | mirror a nivel de app de `E2D`, pasado a `DU9.ADr` |
| `C9T6` | 0 GOING, 1 NOT_GOING, 2 MAYBE, 3 NO_RESPONSE | ordenamiento `dbValue` local (`EventRsvpBottomSheet`, DB local), **sin slot UNKNOWN**, tiene `NO_RESPONSE` en su lugar |
| `C9U0` | strings de `serverValue`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `GOING`, `MAYBE`, `NOT_GOING`, `NO_RESPONSE` | variable GraphQL `rsvp_status` (`UpdateEventRsvp`, `JoinEventViaLink`) |

Esto resuelve en parte la brecha "enum RSVP unknown" señalada para la superficie GraphQL en `Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`: la variable **GraphQL** `rsvp_status` toma los strings literales `GOING` / `MAYBE` / `NOT_GOING` / `NO_RESPONSE` (found, `C9U0.serverValue`, consumidor `C207188s3.B2x()` que lee la clave `"rsvp_status"`). El enum en el wire-proto `EventInviteMessage.status` (campo 13, §3) permanece sin recuperar y **no está probado** que comparta este vocabulario.

Un quinto conjunto separado de valores enteros de "etiqueta de estado" (found, `C2115191e.A00`, usado para el chip de reenvío/vista previa en el chat) mapea `1 GOING, 2 GOING_WITH_GUEST, 3 NOT_GOING, 4 MAYBE, 5 NOT_RESPONDED, 6 CANCELED, default CREATOR` — un conjunto de etiquetas de UI de depuración/visualización, no un valor del wire.

---

## 6. Superficie GraphQL de Events v2 (esquema `www`, doc_ids found)

Existen 16 operaciones persistidas en el `whatsapp-android-www_client_persist_ids.json` distribuido; las variables se recuperaron de los puntos de llamada en la APK (documentadas en `Querys/www/guides/events.md`, que este informe verificó de forma cruzada en lugar de re-derivar).

| Op | doc_id | Op | doc_id |
|----|--------|----|--------|
| `CreateEvent` | `27122934507384369` | `UpdateEvent` | `27442441785378771` |
| `DeleteEvent` | `24671535952543811` | `UpdateEventRsvp` | `27592470423757790` |
| `GetEvent` | `27529572846713636` | `ListEvents` | `27633532006268526` |
| `GetEventCoverImage` | `28048111841543330` | `AddEventInvitations` | `28162575909992756` |
| `GetEventLinkPreview` | `27639296169058396` | `RemoveEventInvitations` | `27696932319970038` |
| `GetOrCreateEventInviteLink` | `26392982740362906` | `RemoveSelfEventInvitation` | `27063717026648637` |
| `JoinEventViaLink` | `27669318929396727` | `RotateEventInviteLink` | `27134834146102810` |
| `ValidateCachedEventIDs` | `27508030125525954` | mex `LogEventInviteCreate` | `27409709725288255` |

Variables clave recuperadas (found): `CreateEvent`/`UpdateEvent` toman `chat_jid`, `description`, `max_additional_guests`, `is_group_based_event`, `is_shareable`, `cover_image_handle`/`cover_image_blob`/`is_preset_image`, `location_address`/`location_web_url`, `call_link_media_type`, `call_link_waiting_room_enabled`; `UpdateEvent` toma además `clear_location`, `clear_location_coordinates`, `hide_invitee_list`, `link_id`, `status`. `UpdateEventRsvp`/`JoinEventViaLink` toman `event_id`/`link_token`, `rsvp_status`, `extra_guest_count`. El transporte es `inferred` (POST de `doc_id` persistido, mismo patrón que otras ops `www`); no se capturó tráfico.

### 6.1 Notificaciones push MEX (found, distintas del pull GraphQL anterior)

`DefaultEventsNotificationRepository` parsea dos esquemas de payload push **MEX** — `xwa2_notify_event_on_invite` y `xwa2_notify_event_on_update` (nombres de nodo literales en excepciones lanzadas, found) — que transportan `start_ts_sec`, `cover_image.handle`/`cover_image.uri`, ubicación, y campos de enlace de llamada, y los inserta directamente en la DB local de eventos (`DefaultLocalEventsDataSource.upsertEvents`). Esto significa que un evento puede aparecer en la lista local de Events de un dispositivo **sin** que el dispositivo haya recibido jamás el plano de mensaje de chat (`eventMessage`/`eventInviteMessage`) para él — el servidor empuja activamente notificaciones de invitación/actualización vía MEX de forma independiente a la entrega del chat. En la primera invitación, el estado RSVP local por defecto es `NO_RESPONSE` (`C9T6.A05.dbValue`).

---

## 7. Almacenamiento local y puente legado

`EventsDatabaseDataSource` (DB local estilo Room) es el almacén canónico para Events v2; `GraphqlEventsDataSource` lo llena desde las ops de §6; `FMessageEventsDataSource` hace de puente con el modelo **más antiguo**, solo-mensaje-de-chat (`eventMessage`/`eventInviteMessage` como filas `FMessage` planas, clase `C213509Ao` — también la clase que controla la generación de `messageSecret` para mensajes de evento según `WA_MESSAGE_SECRETS.md` §"prepare send") hacia el mismo stream `observeEventPreviews()` que consume la UI. En la práctica: un evento creado por un cliente más antiguo (o antes de que existiera Events v2) sigue renderizándose desde el mensaje de chat; un evento creado por Events v2 está respaldado por DB y sincronizado por GraphQL, con el mensaje de chat actuando como tarjeta de invitación compartible.

---

## 8. Acciones del ciclo de vida

| Acción | Quién | Mecanismo | Efecto |
|--------|-----|-----------|--------|
| **Create** | cualquier miembro del chat (grupo) / cualquiera de las partes (1:1) / cualquiera con un contexto elegible para QR | `CreateEvent` (GraphQL) luego se publica `eventInviteMessage` en el chat | el servidor asigna `eventId`; `EventComposerFragment` recopila nombre/descripción/hora/ubicación/portada/recordatorio/toggle de invitados/tipo de medio de enlace de llamada |
| **Update** | host | `UpdateEvent` (GraphQL); `lastUpdatedTsUsec` (campo 12) avanza | texto de notificación dirigido según qué campos cambiaron: "Event date has been updated.", "...date and location...", "...date and time...", "...date, time and location...", "...location has been updated.", "...time has been updated.", "...time and location..." (todos found, cadenas distintas por diff) |
| **Cancel** | host | establece `isCanceled`/`status`; diálogo de confirmación "Cancel event" / "Are you sure you want to cancel this event?" | "Event canceled"; texto push "%1$s canceled %2$s"; "Guests can no longer respond to the event." / "You can no longer respond to the event." — el RSVP se cierra |
| **Delete** | host | `DeleteEvent` (GraphQL) | se elimina de la lista local de eventos del host; el/los mensaje(s) de invitación en el chat permanecen visibles; "People on the guest list will see the event has been deleted." |
| **Leave** | invitado | acción local, sin cambio de RSVP implícito | el invitado deja de recibir futuras actualizaciones del evento: "You can only see event changes made before you left." |
| **Remove guest** | host | elimina al invitado; **restablece el enlace de invitación** (`RotateEventInviteLink`) | "Guest removed and event link reset" — medida explícita anti-reingreso para que la copia del enlace de ese invitado eliminado deje de funcionar; eliminar a un invitado que se unió vía enlace **no** invalida retroactivamente a otros que ya usaron ese enlace |
| **Report event** | invitado | envía reporte a WhatsApp | "No one in the event will know about this report."; también puede desencadenar la salida del evento |
| **Suspend** (moderación) | del lado del servidor (aplicación de políticas) | distinto de la cancelación | "Event suspended", "can't be changed right now"; un estado bloqueado del cual el host no puede editar para salir |

Eliminar invitados individualmente (`RemoveEventInvitations`) es distinto de eliminar a un invitado que ya se unió (`RemoveEventGuestUseCase`); `AddEventInvitations`/`RemoveSelfEventInvitation` completan la gestión de la lista de invitación.

---

## 9. UI y estados del RSVP

`EventRsvpBottomSheet` ofrece cuatro opciones de radio vinculadas a los ids de recurso `rsvp_going_btn`, `rsvp_going_with_guest_btn` (mostrado solo cuando `extraGuestsAllowed` está activo y el espectador elige una cantidad de invitados > 0), `rsvp_not_going_btn`, `rsvp_maybe_btn`; ningún botón está marcado para el estado de no respondido/`NO_RESPONSE`. Etiquetas (found, strings.xml): "Going", "Going with guest", "Maybe", "Not going". Un invitado puede además traer un conteo de acompañante adicional (`extraGuestCount`, campo 3 del wire de `EventResponseMessage`), condicionado por `EventMessage.extraGuestsAllowed` (campo 9) / `"You can't turn off 'Allow guests' for this event."` una vez que los invitados ya respondieron RSVP con un acompañante.

El RSVP de usuarios que no están en WhatsApp está explícitamente soportado mediante el enlace de unión: `"Guests can respond even if they're not on WhatsApp."` — `JoinEventViaLink` toma `rsvp_status` directamente sin una sesión WA autenticada, es decir, la ruta cifrada `encEventResponseMessage` no es el único canal de RSVP; los RSVP basados en enlace pasan por GraphQL en texto plano en su lugar.

---

## 10. Modelo de visibilidad y privacidad

Este es el hecho de "no confundir" más importante sobre Events: a diferencia del contenido de chat ordinario, **los metadatos del evento se divulgan explícitamente al servidor**, no son puramente opacos a nivel E2E.

| String (found) | Recurso | Significado |
|---|---|---|
| "Event details will be visible to guests and WhatsApp." | `str19d9` | nombre/descripción/hora/ubicación son legibles del lado del servidor (consistente con que sean variables GraphQL de `CreateEvent`/`UpdateEvent`, no solo bytes de proto cifrados) |
| "Event details are visible to guests and WhatsApp. Your personal messages and calls remain end-to-end encrypted." | `str1a3f` | alcance explícito: la garantía E2EE *no* se extiende a los detalles del evento |
| "Your name and response will be visible to other guests and WhatsApp." | `str1a08` | la identidad + respuesta del RSVP también es visible para el servidor (consistente con que `UpdateEventRsvp` sea una mutación GraphQL en texto plano, separada del eco cifrado `encEventResponseMessage` en el plano de chat) |
| "Respond to see the event location and more." / "Respond to see location" | `str19c7`/`str19c4` | la ubicación está **condicionada al RSVP** para invitados que aún no han respondido |
| "You can only see guests in your contacts or who you've messaged on WhatsApp." | `str1974` | la visibilidad de la lista de invitados está limitada al grafo de contactos/chats del propio espectador, no es un roster completo |
| "Anyone with the link can see the event and share it with others, even if they're not on WhatsApp." | `str198b` | el enlace/QR de invitación evita por completo la membresía — la posesión del enlace es el control de acceso |

Entonces: el cifrado E2E de `encEventResponseMessage` (HKDF + AES-GCM, §5, `WA_MESSAGE_SECRETS.md`) protege el payload del RSVP **en la transcripción del chat / contra el relay**, pero esa misma respuesta de RSVP y los propios metadatos del evento se envían de forma independiente al servidor en texto plano a través del plano de control GraphQL para sincronización, descubrimiento, e invitados basados en enlace (no-WA). Los dos planos no son mutuamente excluyentes — coexisten para el mismo evento.

---

## 11. Contexto de grupo vs 1:1 vs comunidad

- **Chat 1:1**: cualquiera de las partes puede crear un evento; la variable GraphQL `is_group_based_event` es false.
- **Chat de grupo**: `is_group_based_event: true`; el compositor muestra "Created for:" con el grupo identificado; las invitaciones pueden además obtenerse de la membresía del grupo (`EventInviteFromGroupsLoadController`, `EventInviteGroupFetcher`) permitiendo que un host invite personas de otros grupos compartidos.
- **Comunidad**: Events también aparece a nivel de comunidad — "Events in announcements", "Community events", "See all community events" (cadenas found) — una lista de eventos a nivel de comunidad distinta de los eventos de un solo grupo.
- **Independiente / basado en enlace**: un evento no necesita estar vinculado a ningún chat; `GetOrCreateEventInviteLink` + `EventInviteLinkQrActivity` producen un enlace/QR compartible independiente de la membresía del chat (§10, `str198b`).

La clasificación de soporte de dispositivo vinculado de `eventMessage` (`WA_MESSAGE_SECRETS.md` §15, `CompanionSupportVerifier`) permite el stanza `type="event"` en un dispositivo vinculado (companion) — es decir, la burbuja de invitación todavía puede *recibirse y almacenarse* allí — pero interactuar con ella está bloqueado: `EventsCompanionRedirectDialog` + el string `"To view or respond to this event, use WhatsApp on your primary device."` (found) redirige a los usuarios de dispositivo vinculado fuera de la UI de Events v2 por completo. Esta es una separación deliberada: la entrega a nivel de stanza es compatible con companion, la interacción a nivel de función es solo para el dispositivo primario.

---

## 12. Recordatorios y notificaciones

| Mecanismo | Disparador | Found/Inferred |
|---|---|---|
| `hasReminder`/`reminderOffsetSec` (campos 11/12 del wire de `EventMessage`) | configurado por el host, opciones del selector Never / Time of event / 15 min / 30 min / 1 hour / 1 day before start | found (strings de UI); mapeo de segundos inferred |
| Notificación de inicio siempre activa | "Guests also get notified at the time of the event." (`str1a47`) | found — independiente del recordatorio personalizado, cada invitado recibe una notificación cuando el evento comienza |
| "Allow precise event reminders" | prompt de permiso del SO para alarmas de hora exacta | found |
| Notificaciones de actualización | el texto varía según qué campos cambiaron (§8) | found |
| Notificación de cancelación | "%1$s canceled %2$s. See event" | found |
| Push MEX (`xwa2_notify_event_on_invite`/`_on_update`) | sincronización iniciada por el servidor, independiente de la entrega del chat | found (§6.1) |

---

## 13. Feature flags

No se recuperaron IDs numéricos de feature-flag que condicionen el comportamiento de Events v2 en este pase — a diferencia de los puntos de llamada aislados de gatekeeper booleano/int de `WA_MESSAGE_SECRETS.md`, los accesores de inyección de dependencias del paquete `eventsv2.*` (`C05T.A00(NNNNN)`, `C05Z.A00(NNNNN)`) son ids de búsqueda de componente/singleton, no lecturas de flag, y no se encontró ningún chequeo booleano estilo `AbstractC...Gatekeeper` ligado a un flag numérico que condicione la creación de eventos, el RSVP, o la redirección de companion. Los dos flags ya documentados para la ruta criptográfica RSVP compartida siguen siendo los relevantes: **15791** (conversión LID→PN del modificador event-response en chats 1:1) y la maquinaria de allowlist de companion/clasificador de tipo de mensaje en `WA_MESSAGE_SECRETS.md` §15–16. Se desconoce si un kill-switch separado condiciona la UI de Events v2 en sí misma.

---

## 14. Baileys

No se encontró manejo de envío o recepción de `eventMessage`/`eventInviteMessage`, ni cifrado RSVP de `encEventResponseMessage`, en `baron-baileys-v2` 1.5.17 más allá de lo que `WA_MESSAGE_SECRETS.md` §17 ya documenta para la ruta criptográfica add-on compartida (puede descifrar un `encEventResponseMessage` entrante usando la tabla genérica de caso de uso, pero no existe código específico de evento para remitente o modelo de evento). `eventMessage` y `eventInviteMessage` son por lo demás campos `Message` planos y enviables vía `snowi.sendjson` con los campos escalares de §2/§3 — componer uno no requiere el helper criptográfico en absoluto, solo `encEventResponseMessage` (el RSVP) lo requiere. No existe cliente GraphQL para las ops `www` de §6 en Baileys; esas requieren una ruta de POST GraphQL de `doc_id` persistido que no está implementada.

| Tema | Baileys | Android |
|---|---|---|
| Enviar `eventMessage`/`eventInviteMessage` | campo `Message` plano, alcanzable vía `snowi.sendjson` | igual |
| Cifrar `encEventResponseMessage` | no implementado (solo descifrado, ruta genérica de caso de uso) | `DU9.ADr` + `MessageSecretCryptoHelper` |
| Ops GraphQL de Events v2 (§6) | no implementado | `GraphqlEventsDataSource` |
| Sincronización push MEX (§6.1) | no implementado | `DefaultEventsNotificationRepository` |

---

## 15. Casos de error / trampas

| Síntoma | Causa | Nota |
|---|---|---|
| Falla el descifrado del RSVP / error 51 | clave de mensaje original equivocada, o desajuste de namespace sender/target (PN vs LID) | compartido con la ruta de voto de encuesta / comentario, ver `WA_MESSAGE_SECRETS.md` §18 |
| Evento visible en la lista de Events pero nunca apareció en el chat | el push MEX (`xwa2_notify_event_on_invite`) lo sincronizó de forma independiente a la entrega del chat | §6.1 |
| Falta la ubicación/lista de invitados para un invitado | aún no respondió RSVP (ubicación condicionada), o el invitado no está en los contactos/historial de chat del espectador (lista de invitados limitada) | §10 |
| Un invitado eliminado todavía puede hacer RSVP vía enlace antiguo | la eliminación del invitado restablece el enlace solo para el registro de *ese* invitado pero otros poseedores del enlace ya compartido no se ven afectados | §8, `str19ed` |
| "Can't change event" / evento bloqueado | el evento está suspendido por motivos de política, no simplemente cancelado | §8 |
| El dispositivo vinculado no puede abrir el evento | la interacción de Events v2 es solo para el dispositivo primario aunque el stanza en sí sea entregable a companion | §11 |
| `EventInviteMessage.status` (13) no se puede parsear/producir con precisión | clase de enum no recuperable estáticamente; **no probado** que sea idéntico al vocabulario GraphQL `rsvp_status`/`status` | §3, §5.3 |

---

## 16. Distinciones clave

| Esto | No esto |
|---|---|
| `eventMessage` (campo 75, base, 12 campos, sin cambios desde antes de 41.6) | `eventInviteMessage` (campo 122, `DTQ`, 13 campos, la tarjeta activa de "Events v2") |
| `encEventResponseMessage` (eco de RSVP cifrado E2E en el chat) | `UpdateEventRsvp`/`JoinEventViaLink` (RSVP GraphQL en texto plano, visible para el servidor) |
| Cancel (establece `isCanceled`, cierra el RSVP, el evento sigue visible) | Delete (se elimina de la lista del host; las invitaciones del chat permanecen, marcadas como eliminadas) |
| Delete (iniciado por el host, afecta la copia del host + marca como eliminado para otros) | Leave (iniciado por el invitado, el invitado deja de ver futuras actualizaciones) |
| Suspend (bloqueo de moderación del servidor) | Cancel (acción del host) |
| Remove guest + reset link (host, invalida la copia del enlace de *ese* invitado) | Remove invitation (host, antes de que el invitado se haya unido) |
| Enum RSVP mirror del wire `E2D`/`C9T8` (GOING=1, NOT_GOING=2, MAYBE=3, UNKNOWN=0) | Enum de DB local `C9T6` (GOING=0, NOT_GOING=1, MAYBE=2, NO_RESPONSE=3) — ordenamiento distinto, mismo concepto |
| Enum de string `rsvp_status` GraphQL `C9U0` (`GOING`/`MAYBE`/`NOT_GOING`/`NO_RESPONSE`) | Enum int32 abierto del wire `EventInviteMessage.status` (campo 13) — no recuperado, no probado que coincida |
| Visibilidad de la lista de invitados (limitada a los contactos del espectador) | Visibilidad del evento vía enlace/QR (abierta a cualquiera que posea el enlace) |

---

## 17. Flujo completo (evento de grupo, crear → RSVP → actualizar)

```
[Host]                                   [WhatsApp server / GraphQL+MEX]           [Guest]
   │ CreateEvent (GraphQL, www)                   │                                   │
   │  chat_jid, description, location, cover──────▶ stores event, assigns eventId     │
   │◀──────────────────────────────────────────── eventId                             │
   │ compose eventInviteMessage (eventId,          │                                   │
   │   coverImageHandle, locationName, ...)        │                                   │
   │ <message type="event"> (E2E, chat plane)──────┼──────────────────────────────────▶ renders invite card
   │                                                │  xwa2_notify_event_on_invite      │
   │                                                ├──────────────────────────────────▶ event appears in
   │                                                │  (MEX push, independent of chat)    Events list too
   │                                                │                                   │ opens EventRsvpBottomSheet
   │                                                │                                   │ picks Going/Maybe/Not going
   │                                                │◀───────── UpdateEventRsvp (GraphQL, plaintext rsvp_status)
   │                                                │◀───────── encEventResponseMessage (E2E, chat plane)
   │  guest list / "Going" badge updates            │  xwa2_notify_event_on_update?     │
   │  (location now visible to guest)               │  (on edits)                       │
   │                                                │                                   │
   │ UpdateEvent (change location/time)─────────────▶ lastUpdatedTsUsec advances         │
   │                                                ├──────────────────────────────────▶ "Event date and location
   │                                                │                                      have been updated."
```

---

## 18. Incógnitas

| Ítem | Estado |
|---|---|
| Nombres de miembros del enum `EventInviteMessage.status` (campo 13) | no recuperable estáticamente; los strings GraphQL `rsvp_status`/`status` (§5.3) son un análogo plausible pero no confirmado |
| Segundos exactos de `reminderOffsetSec` por opción del selector | inferred (0/900/1800/3600/86400), pool de constantes no resuelto |
| Formato de URL del enlace de unión / QR (`chat.whatsapp.com/event/...` o similar) | no encontrado en strings ni en los filtros de intent del manifiesto en este pase |
| IDs numéricos de feature-flag que condicionen la creación/RSVP/redirección de companion de Events v2 | no encontrado (ver §13) |
| Relación exacta entre `EventInviteMessage.status` y los enums de app locales `C9T6`/`C9T8` | no trazado |
| Comportamiento de "Require approval to join" (`str1a34`) | string encontrado; ruta de código no trazada |
| Si los campos de sincronización de historial `eventResponses`(61)/`eventAdditionalMetadata`(64) se completan en la sincronización de historial saliente, entrante, o ambas | no trazado |
