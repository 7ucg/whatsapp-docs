# WhatsApp Events — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-11-01
**Scope:** calendar-style Events (`eventMessage`, `eventInviteMessage`, `eventCoverImage`), encrypted RSVP (`encEventResponseMessage` / `EventResponseMessage`), "Events v2" app subsystem (`com.whatsapp.eventsv2.*`: local DB, GraphQL sync, MEX push notifications, cover-image pipeline, invite-link/QR), lifecycle (create/edit/cancel/delete/leave), RSVP states, guest/location visibility rules, group vs 1:1 vs community context, companion-device restriction, GraphQL op catalogue, reminders

---

## 1. What it is

An "Event" is a calendar-style object (name, description, time window, location, optional video/voice call link) that can be posted into a 1:1 chat, a group, or shared via a standalone link/QR, with guests able to RSVP (Going / Maybe / Not going). The feature ships over two wire surfaces at once: an ordinary E2E-encrypted chat message (`Message.eventMessage` / `Message.eventInviteMessage`) that renders the invite card in the transcript, and a parallel GraphQL + MEX-push control plane (`com.whatsapp.eventsv2.*`, package new in 2.26.41.6) that keeps a local events database in sync independently of chat history. RSVP crypto (HKDF use case "Event Response", AES-GCM) is shared with reactions/polls/comments and is documented in `WA_MESSAGE_SECRETS.md`; this report covers the event-model and lifecycle layer only.

| Entity | `Message` field | Type (obf.) | Role |
|--------|-----------------|-------------|------|
| `eventMessage` | **75** | `EventMessage` | base calendar event, posted into a chat |
| `encEventResponseMessage` | **76** | `EncEventResponseMessage` (`DRN`) | encrypted RSVP follow-up |
| `eventCoverImage` | **85** | `FutureProofMessage` | generic wrapper, carries the cover photo as a nested `imageMessage` |
| `eventInviteMessage` | **122** | `EventInviteMessage` (`DTQ`) | "Events v2" invite card, superset of `eventMessage` |
| `eventResponses` (repeated) | **61**, on the `WebMessageInfo`-equivalent (`C30626DTu`) | `EventResponse` | per-guest RSVP roll-up carried in history sync |
| `eventAdditionalMetadata` | **64**, same host | `EventAdditionalMetadata` | single `isStale` bool |

All proto fields and the RSVP plaintext fields below were re-read directly from the 2.26.41.6 classes (`DRP`, `DRN`, `DU9`, `E2D`, `C9T8` — **found**) and cross-checked against the top-level `Message` container in `Tools/proto-extractor/research/2.26.41.6/whatsapp-deobfuscated.proto`. Tiers: **found** = read in code/strings, **inferred** = deduced, **unknown** = not resolved.

---

## 2. `EventMessage` (field 75) — base event

Unchanged from the 2.26.35.2-era catalogue; still 12 fields in 2.26.41.6.

| Field | # | Type | Notes |
|-------|---|------|-------|
| `contextInfo` | 1 | `ContextInfo` | standard quoting/mentions carrier |
| `isCanceled` | 2 | bool | set by the cancel action |
| `name` | 3 | string | event title |
| `description` | 4 | string | |
| `location` | 5 | `Message.LocationMessage` | static location pin (lat/long/name/address), *not* live |
| `joinLink` | 6 | string | generic join URL (legacy field; superseded by the Events v2 invite link for new events) |
| `startTime` | 7 | int64 | unix seconds |
| `endTime` | 8 | int64 | unix seconds |
| `extraGuestsAllowed` | 9 | bool | "+1" toggle |
| `isScheduleCall` | 10 | bool | same model used for the "Schedule a call" entry point |
| `hasReminder` | 11 | bool | |
| `reminderOffsetSec` | 12 | int64 | seconds before `startTime` |

`reminderOffsetSec` is populated from a fixed picker (`EventReminderBottomSheet`, strings **found**): "Never", "Time of event", "15 minutes before", "30 minutes before", "1 hour before", "1 day before". The 0/900/1800/3600/86400-second mapping is **inferred** (not read as literals; the picker's option-to-seconds table lives in a class — `BXa`/`C27637BzN` — whose constant pool jadx did not resolve).

---

## 3. `EventInviteMessage` (field 122, obf. `DTQ`) — "Events v2" invite

Grew from 9 to 13 fields across releases; 2.26.41.6 carries all 13. **Correction to the starting material**: the committed `Messages/eventInviteMessage/info.md` (captured at 2.26.35.2) stops at field 9 (`callLink`) and is missing fields 10–13, confirmed present in this build by direct read of `DTQ`:

| Field | # | Type | Added | Notes |
|-------|---|------|-------|-------|
| `contextInfo` | 1 | `ContextInfo` | base | |
| `eventId` | 2 | string | base | server-assigned event id |
| `eventTitle` | 3 | string | base | |
| `jpegThumbnail` | 4 | bytes | base | inline cover thumbnail |
| `startTime` | 5 | int64 | base | |
| `caption` | 6 | string | base | |
| `isCanceled` | 7 | bool | base | |
| `endTime` | 8 | int64 | base | |
| `callLink` | 9 | string | base | `https://call.whatsapp.com/video/...` style |
| `coverImageHandle` | 10 | string | 2.26.38.10 | media-handle reference, alternative to inline `jpegThumbnail` |
| `locationName` | 11 | string | 2.26.38.10 | human-readable location label |
| `lastUpdatedTsUsec` | 12 | int64 | 2.26.38.10 | microseconds; advances on every `UpdateEvent` |
| `status` | 13 | int32 (open enum) | **2.26.41.6** | event-level status; enum class not recoverable statically |

`status` (13) is the only new wire field in this release. Its enum member names are **unknown** at the proto level — jadx could not recover the backing class for this open-enum int32. However, the GraphQL-facing status vocabulary used for the related `rsvp_status`/`UpdateEvent.status` variables was recovered independently (§6) and is a plausible but unconfirmed candidate for the same semantics; the two are not proven to share a wire representation.

---

## 4. `eventCoverImage` (field 85) — cover photo wrapper

`FutureProofMessage { optional Message message = 1; }` — the same generic wrapper used for `lottieStickerMessage`, `statusMentionMessage`, etc. No event-specific fields; the nested `message` carries an ordinary `imageMessage`. Consumer code (`EventCoverImageLoader`, `EventCoverImageThumbnailCreator`, `EventCoverImageUrlResolver`) treats it as a normal image attachment — no additional validation beyond generic wrapper unwrapping was found.

Events v2 also supports **preset** cover images (`EventPresetCoverImagesRepository`, GraphQL-fetched catalogue, `cover_image_blob`/`is_preset_image` variables on `CreateEvent`/`UpdateEvent`) as an alternative to a user-uploaded photo.

---

## 5. RSVP: `encEventResponseMessage` and `EventResponseMessage`

### 5.1 Wire shape (found, `DRN`/`DRP`/`E2D` read directly)

| Carrier | Field | # | Type |
|---------|-------|---|------|
| `EncEventResponseMessage` (`DRN`, field 76) | `eventCreationMessageKey` | 1 | `MessageKey` (`BD5`) |
| | `encPayload` | 2 | bytes |
| | `encIv` | 3 | bytes |
| `EventResponseMessage` (`DRP`, the AES-GCM plaintext) | `response` | 1 | enum `E2D` |
| | `timestampMs` | 2 | int64 |
| | `extraGuestCount` | 3 | int32 |

`E2D` values (found, `E2D.java`): **0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE**.

This directly confirms `WA_MESSAGE_SECRETS.md` §"encEventResponseMessage **76**" and resolves a conflict in the auto-extracted proto dump (`Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`, which — due to a field-name-recovery bug noted in its own text, "missing name slot at field #3" — lists `EventResponseMessage` as `timestampMs=1, extraGuestCount=2, field3=3`). The direct class read (`DRP`'s `BUILD_MESSAGE_INFO` field-order string and `RESPONSE_FIELD_NUMBER=1`/`TIMESTAMP_MS_FIELD_NUMBER=2`/`EXTRA_GUEST_COUNT_FIELD_NUMBER=3` constants) settles it: **`response` is field 1, not field 3.**

### 5.2 Send path (found, `DU9.ADr`)

`DU9` (event-response use-case handler, extends `F2P`) builds a `DRP` from an app-level `C9T8` enum (`UNKNOWN=0, GOING=1, NOT_GOING=2, MAYBE=3` — numerically identical to `E2D`, confirming it is a straight 1:1 mirror via converter `EW0.A01`) plus a timestamp and `extraGuestCount` int, encrypts it with HKDF use case `"Event Response"` via `MessageSecretCryptoHelper` (`C33285Eeb.A03`), and wraps the ciphertext/IV/original-message-key into a `DRN`. `AAl()` stamps the outgoing stanza's `<meta event_type="response">`. Crypto detail (HKDF derivation, AES-GCM, AAD = `targetId‖0x00‖modifier`, sender/LID retry) is **not repeated here** — see `WA_MESSAGE_SECRETS.md` §2–9, 16.

### 5.3 Three more RSVP-shaped enums (found) — a gotcha

Besides the wire enum `E2D` and its mirror `C9T8`, the app defines at least three *other* RSVP-status enumerations with **different member orderings**, each used in a different layer:

| Enum (obf.) | Members (ordinal) | Used for |
|---|---|---|
| `E2D` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | wire plaintext `EventResponseMessage.response` |
| `C9T8` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | app-level mirror of `E2D`, passed into `DU9.ADr` |
| `C9T6` | 0 GOING, 1 NOT_GOING, 2 MAYBE, 3 NO_RESPONSE | local `dbValue` ordering (`EventRsvpBottomSheet`, local DB), **no UNKNOWN slot**, has `NO_RESPONSE` instead |
| `C9U0` | `serverValue` strings: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `GOING`, `MAYBE`, `NOT_GOING`, `NO_RESPONSE` | GraphQL `rsvp_status` variable (`UpdateEventRsvp`, `JoinEventViaLink`) |

This resolves part of the "RSVP enum unknown" gap noted for the GraphQL surface in `Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`: the `rsvp_status` **GraphQL** variable takes the literal strings `GOING` / `MAYBE` / `NOT_GOING` / `NO_RESPONSE` (found, `C9U0.serverValue`, consumer `C207188s3.B2x()` reading key `"rsvp_status"`). The wire-proto `EventInviteMessage.status` (field 13, §3) enum class remains unrecovered and is **not proven** to share this vocabulary.

A fifth, separate set of integer "status label" values (found, `C2115191e.A00`, used for the chat-forward/preview chip) maps `1 GOING, 2 GOING_WITH_GUEST, 3 NOT_GOING, 4 MAYBE, 5 NOT_RESPONDED, 6 CANCELED, default CREATOR` — a UI debug/display label set, not a wire value.

---

## 6. Events v2 GraphQL surface (`www` schema, found doc_ids)

16 persisted operations exist in the shipped `whatsapp-android-www_client_persist_ids.json`; variables recovered from APK call sites (documented in `Querys/www/guides/events.md`, which this report cross-checked rather than re-deriving).

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

Key recovered variables (found): `CreateEvent`/`UpdateEvent` take `chat_jid`, `description`, `max_additional_guests`, `is_group_based_event`, `is_shareable`, `cover_image_handle`/`cover_image_blob`/`is_preset_image`, `location_address`/`location_web_url`, `call_link_media_type`, `call_link_waiting_room_enabled`; `UpdateEvent` additionally takes `clear_location`, `clear_location_coordinates`, `hide_invitee_list`, `link_id`, `status`. `UpdateEventRsvp`/`JoinEventViaLink` take `event_id`/`link_token`, `rsvp_status`, `extra_guest_count`. Transport is `inferred` (persisted-`doc_id` POST, same pattern as other `www` ops); no traffic was captured.

### 6.1 MEX push notifications (found, distinct from the GraphQL pull above)

`DefaultEventsNotificationRepository` parses two **MEX** push payload schemas — `xwa2_notify_event_on_invite` and `xwa2_notify_event_on_update` (literal node names in thrown exceptions, found) — carrying `start_ts_sec`, `cover_image.handle`/`cover_image.uri`, location, and call-link fields, and upserts them straight into the local events DB (`DefaultLocalEventsDataSource.upsertEvents`). This means an event can appear in a device's local Events list **without** the device ever having received the chat-message plane (`eventMessage`/`eventInviteMessage`) for it — the server actively pushes invite/update notifications through MEX independent of chat delivery. On first invite, the local RSVP status defaults to `NO_RESPONSE` (`C9T6.A05.dbValue`).

---

## 7. Local storage and legacy bridge

`EventsDatabaseDataSource` (Room-style local DB) is the canonical store for Events v2; `GraphqlEventsDataSource` fills it from the ops in §6; `FMessageEventsDataSource` bridges the **older** chat-message-only model (`eventMessage`/`eventInviteMessage` as plain `FMessage` rows, class `C213509Ao` — also the class gating `messageSecret` generation for event messages per `WA_MESSAGE_SECRETS.md` §"prepare send") into the same `observeEventPreviews()` stream the UI consumes. Practically: an event created by an older client (or before Events v2 existed) still renders from the chat message; an Events-v2-created event is DB-backed and GraphQL-synced, with the chat message acting as the shareable invite card.

---

## 8. Lifecycle actions

| Action | Who | Mechanism | Effect |
|--------|-----|-----------|--------|
| **Create** | any chat member (group) / either party (1:1) / anyone with a QR-eligible context | `CreateEvent` (GraphQL) then `eventInviteMessage` posted to chat | server assigns `eventId`; `EventComposerFragment` collects name/description/time/location/cover/reminder/guest toggle/call-link media type |
| **Update** | host | `UpdateEvent` (GraphQL); `lastUpdatedTsUsec` (field 12) advances | targeted notification text depending on which fields changed: "Event date has been updated.", "...date and location...", "...date and time...", "...date, time and location...", "...location has been updated.", "...time has been updated.", "...time and location..." (all found, distinct strings per diff) |
| **Cancel** | host | sets `isCanceled`/`status`; confirmation dialog "Cancel event" / "Are you sure you want to cancel this event?" | "Event canceled"; push text "%1$s canceled %2$s"; "Guests can no longer respond to the event." / "You can no longer respond to the event." — RSVP closes |
| **Delete** | host | `DeleteEvent` (GraphQL) | removed from the host's local events list; chat invitation message(s) remain visible; "People on the guest list will see the event has been deleted." |
| **Leave** | guest | local action, no RSVP change implied | guest stops receiving further event updates: "You can only see event changes made before you left." |
| **Remove guest** | host | removes guest; **resets the invite link** (`RotateEventInviteLink`) | "Guest removed and event link reset" — explicit anti-rejoin measure so a removed guest's copy of the link stops working; removing a guest who joined via link does **not** retroactively invalidate others who already used that link |
| **Report event** | guest | sends report to WhatsApp | "No one in the event will know about this report."; may also trigger leaving the event |
| **Suspend** (moderation) | server-side (policy enforcement) | distinct from cancellation | "Event suspended", "can't be changed right now"; a locked state the host cannot edit out of |

Removing invitees individually (`RemoveEventInvitations`) is separate from removing a joined guest (`RemoveEventGuestUseCase`); `AddEventInvitations`/`RemoveSelfEventInvitation` round out invite-list management.

---

## 9. RSVP UI and states

`EventRsvpBottomSheet` offers four radio options bound to resource ids `rsvp_going_btn`, `rsvp_going_with_guest_btn` (shown only when `extraGuestsAllowed` is set and the viewer picks a guest count > 0), `rsvp_not_going_btn`, `rsvp_maybe_btn`; no button is checked for the unanswered/`NO_RESPONSE` state. Labels (found, strings.xml): "Going", "Going with guest", "Maybe", "Not going". A guest can additionally bring a plus-one count (`extraGuestCount`, wire field 3 of `EventResponseMessage`), gated by `EventMessage.extraGuestsAllowed` (field 9) / `"You can't turn off 'Allow guests' for this event."` once guests have already RSVP'd with a plus-one.

Non-WhatsApp-user RSVP is explicitly supported through the join link: `"Guests can respond even if they're not on WhatsApp."` — `JoinEventViaLink` takes `rsvp_status` directly without an authenticated WA session, i.e. the encrypted `encEventResponseMessage` path is not the only RSVP channel; link-based RSVPs go through plaintext GraphQL instead.

---

## 10. Visibility and privacy model

This is the most important "do not confuse" fact about Events: unlike ordinary chat content, **event metadata is explicitly disclosed to the server**, not purely E2E-opaque.

| String (found) | Resource | Meaning |
|---|---|---|
| "Event details will be visible to guests and WhatsApp." | `str19d9` | name/description/time/location are readable server-side (consistent with them being GraphQL `CreateEvent`/`UpdateEvent` variables, not only encrypted proto bytes) |
| "Event details are visible to guests and WhatsApp. Your personal messages and calls remain end-to-end encrypted." | `str1a3f` | explicit scoping: the E2EE guarantee is *not* extended to event details |
| "Your name and response will be visible to other guests and WhatsApp." | `str1a08` | RSVP identity + answer is also server-visible (consistent with `UpdateEventRsvp` being a plaintext GraphQL mutation, separate from the encrypted `encEventResponseMessage` chat-plane echo) |
| "Respond to see the event location and more." / "Respond to see location" | `str19c7`/`str19c4` | location is **gated behind RSVP** for guests who haven't answered yet |
| "You can only see guests in your contacts or who you've messaged on WhatsApp." | `str1974` | guest-list visibility is capped to the viewer's own contact/chat graph, not a full roster |
| "Anyone with the link can see the event and share it with others, even if they're not on WhatsApp." | `str198b` | the invite link/QR bypasses membership entirely — link possession is the access control |

So: the `encEventResponseMessage` E2E encryption (HKDF + AES-GCM, §5, `WA_MESSAGE_SECRETS.md`) protects the RSVP payload **in the chat transcript / against the relay**, but the same RSVP answer and the event's own metadata are independently sent to the server in plaintext over the GraphQL control plane for sync, discovery, and link-based (non-WA) guests. The two planes are not mutually exclusive — they coexist for the same event.

---

## 11. Group vs 1:1 vs community context

- **1:1 chat**: either party can create an event; `is_group_based_event` GraphQL variable is false.
- **Group chat**: `is_group_based_event: true`; the composer shows "Created for:" with the group identified; invites can additionally be sourced from group membership (`EventInviteFromGroupsLoadController`, `EventInviteGroupFetcher`) letting a host invite people from other shared groups.
- **Community**: Events surface at the community level too — "Events in announcements", "Community events", "See all community events" (found strings) — a community-wide events list distinct from a single group's events.
- **Standalone / link-based**: an event need not be tied to any chat; `GetOrCreateEventInviteLink` + `EventInviteLinkQrActivity` produce a shareable link/QR independent of chat membership (§10, `str198b`).

`eventMessage`'s companion-support classification (`WA_MESSAGE_SECRETS.md` §15, `CompanionSupportVerifier`) allows the stanza `type="event"` on a linked (companion) device — i.e. the invite bubble can still be *received and stored* there — but interacting with it is blocked: `EventsCompanionRedirectDialog` + string `"To view or respond to this event, use WhatsApp on your primary device."` (found) redirects companion-device users away from the Events v2 UI entirely. This is a deliberate split: stanza-level delivery is companion-safe, feature-level interaction is primary-device-only.

---

## 12. Reminders and notifications

| Mechanism | Trigger | Found/Inferred |
|---|---|---|
| `hasReminder`/`reminderOffsetSec` (wire fields 11/12 of `EventMessage`) | host-configured, picker options Never / Time of event / 15 min / 30 min / 1 hour / 1 day before start | found (UI strings); seconds mapping inferred |
| Always-on start notification | "Guests also get notified at the time of the event." (`str1a47`) | found — independent of the custom reminder, every guest gets a notification when the event starts |
| "Allow precise event reminders" | OS permission prompt for exact-time alarms | found |
| Update notifications | text varies by which fields changed (§8) | found |
| Cancellation notification | "%1$s canceled %2$s. See event" | found |
| MEX push (`xwa2_notify_event_on_invite`/`_on_update`) | server-initiated sync, independent of chat delivery | found (§6.1) |

---

## 13. Feature flags

No numeric feature-flag IDs gating Events v2 behavior were recovered in this pass — unlike `WA_MESSAGE_SECRETS.md`'s isolated boolean/int gatekeeper call sites, the `eventsv2.*` package's dependency-injection accessors (`C05T.A00(NNNNN)`, `C05Z.A00(NNNNN)`) are component/singleton lookup ids, not flag reads, and no `AbstractC...Gatekeeper`-style boolean check tied to a numeric flag was found guarding event creation, RSVP, or the companion redirect. The two flags already documented for the shared RSVP crypto path remain the relevant ones: **15791** (event-response modifier LID→PN conversion in 1:1 chats) and the companion-allowlist/message-type-classifier machinery in `WA_MESSAGE_SECRETS.md` §15–16. Unknown whether a separate kill-switch gates the Events v2 UI itself.

---

## 14. Baileys

No `eventMessage`/`eventInviteMessage` send or receive handling, and no `encEventResponseMessage` RSVP encryption, was found in `baron-baileys-v2` 1.5.17 beyond what `WA_MESSAGE_SECRETS.md` §17 already documents for the shared add-on crypto path (it can decrypt an incoming `encEventResponseMessage` using the generic use-case table, but no event-specific sender or event-model code exists). `eventMessage` and `eventInviteMessage` are otherwise plain `Message` fields and sendable via `snowi.sendjson` with the scalar fields in §2/§3 — composing one does not require the crypto helper at all, only `encEventResponseMessage` (the RSVP) does. No GraphQL client for the `www` ops in §6 exists in Baileys; those require a persisted-`doc_id` GraphQL POST path that is not implemented.

| Topic | Baileys | Android |
|---|---|---|
| Send `eventMessage`/`eventInviteMessage` | plain `Message` field, reachable via `snowi.sendjson` | same |
| Encrypt `encEventResponseMessage` | not implemented (decrypt-only, generic use-case path) | `DU9.ADr` + `MessageSecretCryptoHelper` |
| Events v2 GraphQL ops (§6) | not implemented | `GraphqlEventsDataSource` |
| MEX push sync (§6.1) | not implemented | `DefaultEventsNotificationRepository` |

---

## 15. Error cases / gotchas

| Symptom | Cause | Note |
|---|---|---|
| RSVP decrypt fails / error 51 | wrong original-message key, or sender/target namespace (PN vs LID) mismatch | shared with poll vote / comment path, see `WA_MESSAGE_SECRETS.md` §18 |
| Event visible in Events list but never appeared in chat | MEX push (`xwa2_notify_event_on_invite`) synced it independently of chat delivery | §6.1 |
| Location/guest-list missing for an invitee | not yet RSVP'd (location gated), or guest not in viewer's contacts/chat history (guest-list capped) | §10 |
| Removed guest can still RSVP via old link | guest removal resets the link for *that* guest's record but other holders of the already-shared link are unaffected | §8, `str19ed` |
| "Can't change event" / event locked | event is suspended for policy reasons, not merely canceled | §8 |
| Companion device can't open the event | Events v2 interaction is primary-device-only even though the stanza itself is companion-deliverable | §11 |
| `EventInviteMessage.status` (13) can't be parsed/produced precisely | enum class not recoverable statically; **not proven** identical to the GraphQL `rsvp_status`/`status` vocabulary | §3, §5.3 |

---

## 16. Key distinctions

| This | Not this |
|---|---|
| `eventMessage` (field 75, base, 12 fields, unchanged since pre-41.6) | `eventInviteMessage` (field 122, `DTQ`, 13 fields, the active "Events v2" card) |
| `encEventResponseMessage` (E2E-encrypted RSVP echo in the chat) | `UpdateEventRsvp`/`JoinEventViaLink` (plaintext GraphQL RSVP, server-visible) |
| Cancel (sets `isCanceled`, closes RSVP, event stays visible) | Delete (removes from host's list; chat invites remain, marked deleted) |
| Delete (host-initiated, affects host's copy + marks deleted for others) | Leave (guest-initiated, guest stops seeing further updates) |
| Suspend (server moderation lock) | Cancel (host action) |
| Remove guest + reset link (host, invalidates *that* guest's link copy) | Remove invitation (host, before guest has joined) |
| `E2D`/`C9T8` wire-mirroring RSVP enum (GOING=1, NOT_GOING=2, MAYBE=3, UNKNOWN=0) | `C9T6` local-DB enum (GOING=0, NOT_GOING=1, MAYBE=2, NO_RESPONSE=3) — different ordering, same concept |
| `C9U0` GraphQL `rsvp_status` string enum (`GOING`/`MAYBE`/`NOT_GOING`/`NO_RESPONSE`) | `EventInviteMessage.status` (field 13) wire int32 open enum — unrecovered, not proven to match |
| Guest-list visibility (capped to viewer's contacts) | Event visibility via link/QR (open to anyone holding the link) |

---

## 17. Complete flow (group event, create → RSVP → update)

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

## 18. Unknowns

| Item | State |
|---|---|
| `EventInviteMessage.status` (field 13) enum member names | not recoverable statically; GraphQL `rsvp_status`/`status` strings (§5.3) are a plausible but unconfirmed analogue |
| `reminderOffsetSec` exact seconds per picker option | inferred (0/900/1800/3600/86400), constant pool not resolved |
| Join-link / QR URL format (`chat.whatsapp.com/event/...` or similar) | not found in strings or manifest intent filters in this pass |
| Numeric feature-flag IDs gating Events v2 creation/RSVP/companion-redirect | not found (see §13) |
| Exact relationship between `EventInviteMessage.status` and the local `C9T6`/`C9T8` app enums | not traced |
| "Require approval to join" (`str1a34`) behavior | string found; code path not traced |
| Whether `eventResponses`(61)/`eventAdditionalMetadata`(64) history-sync fields are populated on outgoing history sync, incoming, or both | not traced |
