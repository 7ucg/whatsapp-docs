<!-- src-sha1: c9f42e3645bee848584358bb7a4660a293218e2e -->
# WhatsApp Events — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** Kalenderartige Events (`eventMessage`, `eventInviteMessage`, `eventCoverImage`), verschlüsseltes RSVP (`encEventResponseMessage` / `EventResponseMessage`), "Events v2"-App-Subsystem (`com.whatsapp.eventsv2.*`: lokale DB, GraphQL-Sync, MEX-Push-Benachrichtigungen, Cover-Image-Pipeline, Invite-Link/QR), Lifecycle (Erstellen/Bearbeiten/Abbrechen/Löschen/Verlassen), RSVP-States, Gast-/Standort-Sichtbarkeitsregeln, Gruppen- vs. 1:1- vs. Community-Kontext, Companion-Device-Einschränkung, GraphQL-Op-Katalog, Erinnerungen

---

## 1. Was es ist

Ein "Event" ist ein kalenderartiges Objekt (Name, Beschreibung, Zeitfenster, Standort, optionaler Video-/Voice-Call-Link), das in einen 1:1-Chat, eine Gruppe oder per eigenständigem Link/QR geteilt werden kann, mit Gästen, die per RSVP antworten können (Going / Maybe / Not going). Das Feature läuft über zwei Wire-Oberflächen gleichzeitig: eine gewöhnliche E2E-verschlüsselte Chat-Nachricht (`Message.eventMessage` / `Message.eventInviteMessage`), die die Invite-Karte im Transcript rendert, und eine parallele GraphQL- + MEX-Push-Control-Plane (`com.whatsapp.eventsv2.*`, Package neu in 2.26.41.6), die eine lokale Events-Datenbank unabhängig vom Chat-Verlauf synchron hält. RSVP-Krypto (HKDF-Use-Case "Event Response", AES-GCM) wird mit Reactions/Polls/Comments geteilt und ist in `WA_MESSAGE_SECRETS.md` dokumentiert; dieser Report deckt nur die Event-Modell- und Lifecycle-Ebene ab.

| Entität | `Message`-Feld | Typ (obf.) | Rolle |
|--------|-----------------|-------------|------|
| `eventMessage` | **75** | `EventMessage` | Basis-Kalenderevent, in einen Chat gepostet |
| `encEventResponseMessage` | **76** | `EncEventResponseMessage` (`DRN`) | verschlüsselte RSVP-Folgenachricht |
| `eventCoverImage` | **85** | `FutureProofMessage` | generischer Wrapper, trägt das Cover-Foto als verschachtelte `imageMessage` |
| `eventInviteMessage` | **122** | `EventInviteMessage` (`DTQ`) | "Events v2"-Invite-Karte, Superset von `eventMessage` |
| `eventResponses` (wiederholt) | **61**, auf dem `WebMessageInfo`-Äquivalent (`C30626DTu`) | `EventResponse` | Per-Gast-RSVP-Rollup, in History-Sync mitgeführt |
| `eventAdditionalMetadata` | **64**, gleicher Host | `EventAdditionalMetadata` | einzelner `isStale`-Bool |

Alle Proto-Felder und die unten genannten RSVP-Klartextfelder wurden direkt aus den 2.26.41.6-Klassen gelesen (`DRP`, `DRN`, `DU9`, `E2D`, `C9T8` — **found**) und gegen den Top-Level-`Message`-Container in `Tools/proto-extractor/research/2.26.41.6/whatsapp-deobfuscated.proto` abgeglichen. Tiers: **found** = im Code/String gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst.

---

## 2. `EventMessage` (Feld 75) — Basis-Event

Unverändert seit der 2.26.35.2-Ära-Katalogisierung; weiterhin 12 Felder in 2.26.41.6.

| Feld | # | Typ | Notizen |
|-------|---|------|-------|
| `contextInfo` | 1 | `ContextInfo` | Standard-Quoting-/Mentions-Carrier |
| `isCanceled` | 2 | bool | von der Cancel-Action gesetzt |
| `name` | 3 | string | Event-Titel |
| `description` | 4 | string | |
| `location` | 5 | `Message.LocationMessage` | statischer Standort-Pin (lat/long/Name/Adresse), *nicht* live |
| `joinLink` | 6 | string | generische Join-URL (Legacy-Feld; abgelöst durch den Events-v2-Invite-Link für neue Events) |
| `startTime` | 7 | int64 | Unix-Sekunden |
| `endTime` | 8 | int64 | Unix-Sekunden |
| `extraGuestsAllowed` | 9 | bool | "+1"-Toggle |
| `isScheduleCall` | 10 | bool | gleiches Modell wie der "Schedule a call"-Einstiegspunkt |
| `hasReminder` | 11 | bool | |
| `reminderOffsetSec` | 12 | int64 | Sekunden vor `startTime` |

`reminderOffsetSec` wird aus einem festen Picker befüllt (`EventReminderBottomSheet`, Strings **found**): "Never", "Time of event", "15 minutes before", "30 minutes before", "1 hour before", "1 day before". Die 0/900/1800/3600/86400-Sekunden-Zuordnung ist **inferred** (nicht als Literal gelesen; die Option-zu-Sekunden-Tabelle des Pickers liegt in einer Klasse — `BXa`/`C27637BzN` — deren Konstanten-Pool jadx nicht aufgelöst hat).

---

## 3. `EventInviteMessage` (Feld 122, obf. `DTQ`) — "Events v2"-Invite

Wuchs über Releases von 9 auf 13 Felder; 2.26.41.6 trägt alle 13. **Korrektur zum Ausgangsmaterial**: Das committete `Messages/eventInviteMessage/info.md` (erfasst bei 2.26.35.2) stoppt bei Feld 9 (`callLink`) und fehlt die Felder 10–13, bestätigt vorhanden in diesem Build durch direktes Lesen von `DTQ`:

| Feld | # | Typ | Hinzugefügt | Notizen |
|-------|---|------|-------|-------|
| `contextInfo` | 1 | `ContextInfo` | Basis | |
| `eventId` | 2 | string | Basis | server-vergebene Event-ID |
| `eventTitle` | 3 | string | Basis | |
| `jpegThumbnail` | 4 | bytes | Basis | inline Cover-Thumbnail |
| `startTime` | 5 | int64 | Basis | |
| `caption` | 6 | string | Basis | |
| `isCanceled` | 7 | bool | Basis | |
| `endTime` | 8 | int64 | Basis | |
| `callLink` | 9 | string | Basis | im Stil von `https://call.whatsapp.com/video/...` |
| `coverImageHandle` | 10 | string | 2.26.38.10 | Media-Handle-Referenz, Alternative zum inline `jpegThumbnail` |
| `locationName` | 11 | string | 2.26.38.10 | menschenlesbares Standort-Label |
| `lastUpdatedTsUsec` | 12 | int64 | 2.26.38.10 | Mikrosekunden; schreitet bei jedem `UpdateEvent` fort |
| `status` | 13 | int32 (offenes Enum) | **2.26.41.6** | Event-Level-Status; Enum-Klasse statisch nicht wiederherstellbar |

`status` (13) ist das einzige neue Wire-Feld in diesem Release. Seine Enum-Member-Namen sind auf Proto-Ebene **unknown** — jadx konnte die Backing-Klasse für dieses offene Enum-int32 nicht wiederherstellen. Das GraphQL-seitige Status-Vokabular für die zugehörigen Variablen `rsvp_status`/`UpdateEvent.status` wurde jedoch unabhängig wiederhergestellt (§6) und ist ein plausibler, aber unbestätigter Kandidat für die gleiche Semantik; die beiden sind nicht nachweislich wire-identisch.

---

## 4. `eventCoverImage` (Feld 85) — Cover-Foto-Wrapper

`FutureProofMessage { optional Message message = 1; }` — der gleiche generische Wrapper, der für `lottieStickerMessage`, `statusMentionMessage` usw. verwendet wird. Keine eventspezifischen Felder; die verschachtelte `message` trägt eine gewöhnliche `imageMessage`. Consumer-Code (`EventCoverImageLoader`, `EventCoverImageThumbnailCreator`, `EventCoverImageUrlResolver`) behandelt sie wie einen normalen Bild-Anhang — keine zusätzliche Validierung über das generische Wrapper-Unwrapping hinaus wurde gefunden.

Events v2 unterstützt zusätzlich **voreingestellte** Cover-Images (`EventPresetCoverImagesRepository`, GraphQL-abgerufener Katalog, Variablen `cover_image_blob`/`is_preset_image` auf `CreateEvent`/`UpdateEvent`) als Alternative zu einem nutzerhochgeladenen Foto.

---

## 5. RSVP: `encEventResponseMessage` und `EventResponseMessage`

### 5.1 Wire-Form (found, `DRN`/`DRP`/`E2D` direkt gelesen)

| Carrier | Feld | # | Typ |
|---------|-------|---|------|
| `EncEventResponseMessage` (`DRN`, Feld 76) | `eventCreationMessageKey` | 1 | `MessageKey` (`BD5`) |
| | `encPayload` | 2 | bytes |
| | `encIv` | 3 | bytes |
| `EventResponseMessage` (`DRP`, der AES-GCM-Klartext) | `response` | 1 | enum `E2D` |
| | `timestampMs` | 2 | int64 |
| | `extraGuestCount` | 3 | int32 |

`E2D`-Werte (found, `E2D.java`): **0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE**.

Dies bestätigt direkt `WA_MESSAGE_SECRETS.md` §"encEventResponseMessage **76**" und löst einen Widerspruch im auto-extrahierten Proto-Dump auf (`Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`, das — wegen eines im eigenen Text vermerkten Field-Name-Recovery-Bugs, "missing name slot at field #3" — `EventResponseMessage` als `timestampMs=1, extraGuestCount=2, field3=3` listet). Der direkte Klassen-Read (der `BUILD_MESSAGE_INFO`-Feldreihenfolge-String von `DRP` und die Konstanten `RESPONSE_FIELD_NUMBER=1`/`TIMESTAMP_MS_FIELD_NUMBER=2`/`EXTRA_GUEST_COUNT_FIELD_NUMBER=3`) klärt es: **`response` ist Feld 1, nicht Feld 3.**

### 5.2 Sendepfad (found, `DU9.ADr`)

`DU9` (Event-Response-Use-Case-Handler, erweitert `F2P`) baut ein `DRP` aus einem App-Level-Enum `C9T8` (`UNKNOWN=0, GOING=1, NOT_GOING=2, MAYBE=3` — numerisch identisch zu `E2D`, was bestätigt, dass es ein direktes 1:1-Mirror über den Converter `EW0.A01` ist) plus einem Timestamp und einem `extraGuestCount`-Int, verschlüsselt es mit HKDF-Use-Case `"Event Response"` via `MessageSecretCryptoHelper` (`C33285Eeb.A03`), und verpackt Ciphertext/IV/ursprünglichen-Message-Key in ein `DRN`. `AAl()` stempelt `<meta event_type="response">` auf die ausgehende Stanza. Krypto-Detail (HKDF-Ableitung, AES-GCM, AAD = `targetId‖0x00‖modifier`, Sender-/LID-Retry) wird **hier nicht wiederholt** — siehe `WA_MESSAGE_SECRETS.md` §2–9, 16.

### 5.3 Drei weitere RSVP-förmige Enums (found) — ein Gotcha

Neben dem Wire-Enum `E2D` und seinem Mirror `C9T8` definiert die App mindestens drei *weitere* RSVP-Status-Enumerationen mit **unterschiedlichen Member-Reihenfolgen**, jede in einer anderen Schicht verwendet:

| Enum (obf.) | Member (ordinal) | Verwendet für |
|---|---|---|
| `E2D` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | Wire-Klartext `EventResponseMessage.response` |
| `C9T8` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | App-Level-Mirror von `E2D`, übergeben an `DU9.ADr` |
| `C9T6` | 0 GOING, 1 NOT_GOING, 2 MAYBE, 3 NO_RESPONSE | lokale `dbValue`-Reihenfolge (`EventRsvpBottomSheet`, lokale DB), **kein UNKNOWN-Slot**, hat stattdessen `NO_RESPONSE` |
| `C9U0` | `serverValue`-Strings: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `GOING`, `MAYBE`, `NOT_GOING`, `NO_RESPONSE` | GraphQL-Variable `rsvp_status` (`UpdateEventRsvp`, `JoinEventViaLink`) |

Dies löst einen Teil der für die GraphQL-Oberfläche in `Etc/whats-new-2.26.41.6/deep/social-and-messaging.md` vermerkten Lücke "RSVP enum unknown": Die **GraphQL**-Variable `rsvp_status` nimmt die Literal-Strings `GOING` / `MAYBE` / `NOT_GOING` / `NO_RESPONSE` (found, `C9U0.serverValue`, Consumer `C207188s3.B2x()` liest den Key `"rsvp_status"`). Das Wire-Proto-Enum `EventInviteMessage.status` (Feld 13, §3) bleibt unrecovered und ist **nicht nachgewiesen**, dieses Vokabular zu teilen.

Ein fünfter, separater Satz von Integer-"Status-Label"-Werten (found, `C2115191e.A00`, verwendet für den Chat-Forward-/Preview-Chip) mappt `1 GOING, 2 GOING_WITH_GUEST, 3 NOT_GOING, 4 MAYBE, 5 NOT_RESPONDED, 6 CANCELED, default CREATOR` — ein UI-Debug-/Anzeige-Label-Satz, kein Wire-Wert.

---

## 6. Events-v2-GraphQL-Oberfläche (`www`-Schema, found doc_ids)

16 persistierte Operationen existieren in der ausgelieferten `whatsapp-android-www_client_persist_ids.json`; Variablen wurden aus APK-Call-Sites wiederhergestellt (dokumentiert in `Querys/www/guides/events.md`, das dieser Report cross-checkte statt neu abzuleiten).

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

Wiederhergestellte Schlüsselvariablen (found): `CreateEvent`/`UpdateEvent` nehmen `chat_jid`, `description`, `max_additional_guests`, `is_group_based_event`, `is_shareable`, `cover_image_handle`/`cover_image_blob`/`is_preset_image`, `location_address`/`location_web_url`, `call_link_media_type`, `call_link_waiting_room_enabled`; `UpdateEvent` zusätzlich `clear_location`, `clear_location_coordinates`, `hide_invitee_list`, `link_id`, `status`. `UpdateEventRsvp`/`JoinEventViaLink` nehmen `event_id`/`link_token`, `rsvp_status`, `extra_guest_count`. Transport ist `inferred` (persisted-`doc_id`-POST, gleiches Muster wie andere `www`-Ops); kein Traffic wurde mitgeschnitten.

### 6.1 MEX-Push-Benachrichtigungen (found, verschieden vom GraphQL-Pull oben)

`DefaultEventsNotificationRepository` parst zwei **MEX**-Push-Payload-Schemas — `xwa2_notify_event_on_invite` und `xwa2_notify_event_on_update` (literale Node-Namen in geworfenen Exceptions, found) — die `start_ts_sec`, `cover_image.handle`/`cover_image.uri`, Standort- und Call-Link-Felder tragen, und schreibt sie direkt in die lokale Events-DB (`DefaultLocalEventsDataSource.upsertEvents`). Das bedeutet, ein Event kann in der lokalen Events-Liste eines Geräts auftauchen, **ohne** dass das Gerät jemals die Chat-Message-Ebene (`eventMessage`/`eventInviteMessage`) dafür erhalten hat — der Server pusht Invite-/Update-Benachrichtigungen aktiv per MEX unabhängig von der Chat-Zustellung. Bei der ersten Einladung ist der lokale RSVP-Status standardmäßig `NO_RESPONSE` (`C9T6.A05.dbValue`).

---

## 7. Lokaler Storage und Legacy-Brücke

`EventsDatabaseDataSource` (Room-artige lokale DB) ist der kanonische Store für Events v2; `GraphqlEventsDataSource` befüllt sie aus den Ops in §6; `FMessageEventsDataSource` überbrückt das **ältere** reine Chat-Message-Modell (`eventMessage`/`eventInviteMessage` als einfache `FMessage`-Zeilen, Klasse `C213509Ao` — auch die Klasse, die die `messageSecret`-Generierung für Event-Nachrichten gemäß `WA_MESSAGE_SECRETS.md` §"prepare send" gatet) in den gleichen `observeEventPreviews()`-Stream, den die UI konsumiert. Praktisch: Ein von einem älteren Client erstelltes Event (oder eines, das vor Events v2 existierte) rendert weiterhin aus der Chat-Nachricht; ein mit Events v2 erstelltes Event ist DB-backed und GraphQL-synchronisiert, wobei die Chat-Nachricht als teilbare Invite-Karte fungiert.

---

## 8. Lifecycle-Aktionen

| Aktion | Wer | Mechanismus | Effekt |
|--------|-----|-----------|--------|
| **Erstellen** | jedes Chat-Mitglied (Gruppe) / jede Partei (1:1) / jeder mit QR-fähigem Kontext | `CreateEvent` (GraphQL), dann `eventInviteMessage` in den Chat gepostet | Server vergibt `eventId`; `EventComposerFragment` sammelt Name/Beschreibung/Zeit/Standort/Cover/Erinnerung/Gast-Toggle/Call-Link-Medientyp |
| **Bearbeiten** | Host | `UpdateEvent` (GraphQL); `lastUpdatedTsUsec` (Feld 12) schreitet fort | zielgerichteter Benachrichtigungstext je nachdem, welche Felder sich geändert haben: "Event date has been updated.", "...date and location...", "...date and time...", "...date, time and location...", "...location has been updated.", "...time has been updated.", "...time and location..." (alle found, unterschiedliche Strings pro Diff) |
| **Abbrechen** | Host | setzt `isCanceled`/`status`; Bestätigungsdialog "Cancel event" / "Are you sure you want to cancel this event?" | "Event canceled"; Push-Text "%1$s canceled %2$s"; "Guests can no longer respond to the event." / "You can no longer respond to the event." — RSVP schließt |
| **Löschen** | Host | `DeleteEvent` (GraphQL) | aus der lokalen Events-Liste des Hosts entfernt; Chat-Einladungsnachricht(en) bleiben sichtbar; "People on the guest list will see the event has been deleted." |
| **Verlassen** | Gast | lokale Aktion, keine implizierte RSVP-Änderung | Gast erhält keine weiteren Event-Updates mehr: "You can only see event changes made before you left." |
| **Gast entfernen** | Host | entfernt Gast; **setzt den Invite-Link zurück** (`RotateEventInviteLink`) | "Guest removed and event link reset" — explizite Anti-Rejoin-Maßnahme, damit die Kopie des entfernten Gasts nicht mehr funktioniert; das Entfernen eines Gasts, der per Link beigetreten ist, invalidiert **nicht** rückwirkend andere, die den Link bereits genutzt haben |
| **Event melden** | Gast | sendet Meldung an WhatsApp | "No one in the event will know about this report."; kann zusätzlich das Verlassen des Events auslösen |
| **Sperren** (Moderation) | serverseitig (Policy-Enforcement) | unterscheidet sich vom Abbrechen | "Event suspended", "can't be changed right now"; ein gesperrter Zustand, aus dem der Host sich nicht herausbearbeiten kann |

Das individuelle Entfernen von Einladungen (`RemoveEventInvitations`) ist getrennt vom Entfernen eines beigetretenen Gasts (`RemoveEventGuestUseCase`); `AddEventInvitations`/`RemoveSelfEventInvitation` runden das Invite-List-Management ab.

---

## 9. RSVP-UI und States

`EventRsvpBottomSheet` bietet vier Radio-Optionen, gebunden an die Resource-IDs `rsvp_going_btn`, `rsvp_going_with_guest_btn` (nur gezeigt, wenn `extraGuestsAllowed` gesetzt ist und der Betrachter eine Gästezahl > 0 wählt), `rsvp_not_going_btn`, `rsvp_maybe_btn`; für den unbeantworteten/`NO_RESPONSE`-Zustand ist kein Button ausgewählt. Labels (found, strings.xml): "Going", "Going with guest", "Maybe", "Not going". Ein Gast kann zusätzlich eine Plus-Eins-Zahl mitbringen (`extraGuestCount`, Wire-Feld 3 von `EventResponseMessage`), gated durch `EventMessage.extraGuestsAllowed` (Feld 9) / `"You can't turn off 'Allow guests' for this event."`, sobald Gäste bereits mit einem Plus-Eins per RSVP geantwortet haben.

Non-WhatsApp-Nutzer-RSVP wird explizit über den Join-Link unterstützt: `"Guests can respond even if they're not on WhatsApp."` — `JoinEventViaLink` nimmt `rsvp_status` direkt, ohne authentifizierte WA-Session, d. h. der verschlüsselte `encEventResponseMessage`-Pfad ist nicht der einzige RSVP-Kanal; link-basierte RSVPs laufen stattdessen über plaintext GraphQL.

---

## 10. Sichtbarkeits- und Privacy-Modell

Dies ist die wichtigste "nicht verwechseln"-Tatsache über Events: Anders als gewöhnlicher Chat-Inhalt wird **Event-Metadaten explizit dem Server offengelegt**, nicht rein E2E-opak.

| String (found) | Resource | Bedeutung |
|---|---|---|
| "Event details will be visible to guests and WhatsApp." | `str19d9` | Name/Beschreibung/Zeit/Standort sind serverseitig lesbar (konsistent damit, dass sie GraphQL-`CreateEvent`/`UpdateEvent`-Variablen sind, nicht nur verschlüsselte Proto-Bytes) |
| "Event details are visible to guests and WhatsApp. Your personal messages and calls remain end-to-end encrypted." | `str1a3f` | explizite Abgrenzung: die E2EE-Garantie wird *nicht* auf Event-Details ausgedehnt |
| "Your name and response will be visible to other guests and WhatsApp." | `str1a08` | RSVP-Identität + Antwort ist ebenfalls serverseitig sichtbar (konsistent damit, dass `UpdateEventRsvp` eine plaintext GraphQL-Mutation ist, getrennt vom verschlüsselten `encEventResponseMessage`-Chat-Plane-Echo) |
| "Respond to see the event location and more." / "Respond to see location" | `str19c7`/`str19c4` | Standort ist für Gäste, die noch nicht geantwortet haben, **hinter RSVP gegatet** |
| "You can only see guests in your contacts or who you've messaged on WhatsApp." | `str1974` | Gast-Listen-Sichtbarkeit ist auf den eigenen Kontakt-/Chat-Graph des Betrachters begrenzt, kein vollständiges Roster |
| "Anyone with the link can see the event and share it with others, even if they're not on WhatsApp." | `str198b` | der Invite-Link/QR umgeht Mitgliedschaft vollständig — Link-Besitz ist die Zugangskontrolle |

Also: Die E2E-Verschlüsselung von `encEventResponseMessage` (HKDF + AES-GCM, §5, `WA_MESSAGE_SECRETS.md`) schützt den RSVP-Payload **im Chat-Transcript / gegen das Relay**, aber dieselbe RSVP-Antwort und die Event-eigenen Metadaten werden unabhängig davon im Klartext an den Server über die GraphQL-Control-Plane für Sync, Discovery und link-basierte (Non-WA-)Gäste gesendet. Die beiden Ebenen schließen sich nicht gegenseitig aus — sie koexistieren für dasselbe Event.

---

## 11. Gruppen- vs. 1:1- vs. Community-Kontext

- **1:1-Chat**: entweder Partei kann ein Event erstellen; GraphQL-Variable `is_group_based_event` ist false.
- **Gruppen-Chat**: `is_group_based_event: true`; der Composer zeigt "Created for:" mit der identifizierten Gruppe; Einladungen können zusätzlich aus der Gruppenmitgliedschaft bezogen werden (`EventInviteFromGroupsLoadController`, `EventInviteGroupFetcher`), was es einem Host erlaubt, Leute aus anderen gemeinsamen Gruppen einzuladen.
- **Community**: Events erscheinen auch auf Community-Ebene — "Events in announcements", "Community events", "See all community events" (found Strings) — eine community-weite Events-Liste, getrennt von den Events einer einzelnen Gruppe.
- **Eigenständig / linkbasiert**: Ein Event muss an keinen Chat gebunden sein; `GetOrCreateEventInviteLink` + `EventInviteLinkQrActivity` erzeugen einen teilbaren Link/QR unabhängig von Chat-Mitgliedschaft (§10, `str198b`).

Die Companion-Support-Klassifizierung von `eventMessage` (`WA_MESSAGE_SECRETS.md` §15, `CompanionSupportVerifier`) erlaubt die Stanza `type="event"` auf einem verlinkten (Companion-)Gerät — d. h. die Invite-Bubble kann dort weiterhin *empfangen und gespeichert* werden — aber die Interaktion damit ist blockiert: `EventsCompanionRedirectDialog` + String `"To view or respond to this event, use WhatsApp on your primary device."` (found) leitet Companion-Device-Nutzer vollständig von der Events-v2-UI weg. Dies ist eine bewusste Trennung: Zustellung auf Stanza-Ebene ist companion-sicher, Interaktion auf Feature-Ebene ist nur-primär-Gerät.

---

## 12. Erinnerungen und Benachrichtigungen

| Mechanismus | Trigger | Found/Inferred |
|---|---|---|
| `hasReminder`/`reminderOffsetSec` (Wire-Felder 11/12 von `EventMessage`) | host-konfiguriert, Picker-Optionen Never / Time of event / 15 min / 30 min / 1 hour / 1 day before start | found (UI-Strings); Sekunden-Zuordnung inferred |
| Immer-aktive Start-Benachrichtigung | "Guests also get notified at the time of the event." (`str1a47`) | found — unabhängig von der individuellen Erinnerung, jeder Gast erhält eine Benachrichtigung beim Start des Events |
| "Allow precise event reminders" | OS-Berechtigungsaufforderung für exakte Alarme | found |
| Update-Benachrichtigungen | Text variiert je geänderter Felder (§8) | found |
| Abbruch-Benachrichtigung | "%1$s canceled %2$s. See event" | found |
| MEX-Push (`xwa2_notify_event_on_invite`/`_on_update`) | serverseitig initiierte Synchronisation, unabhängig von Chat-Zustellung | found (§6.1) |

---

## 13. Feature-Flags

Keine numerischen Feature-Flag-IDs, die Events-v2-Verhalten gaten, wurden in diesem Pass wiedergefunden — anders als die isolierten Boolean-/Int-Gatekeeper-Call-Sites in `WA_MESSAGE_SECRETS.md` sind die Dependency-Injection-Accessoren des `eventsv2.*`-Packages (`C05T.A00(NNNNN)`, `C05Z.A00(NNNNN)`) Component-/Singleton-Lookup-IDs, keine Flag-Reads, und keine `AbstractC...Gatekeeper`-artige Boolean-Prüfung an ein numerisches Flag gebunden wurde gefunden, die Event-Erstellung, RSVP oder den Companion-Redirect gatet. Die beiden bereits für den geteilten RSVP-Krypto-Pfad dokumentierten Flags bleiben die relevanten: **15791** (Event-Response-Modifier-LID→PN-Konvertierung in 1:1-Chats) und die Companion-Allowlist-/Message-Type-Classifier-Mechanik in `WA_MESSAGE_SECRETS.md` §15–16. Unbekannt, ob ein separater Kill-Switch die Events-v2-UI selbst gatet.

---

## 14. Baileys

Kein Senden/Empfangen von `eventMessage`/`eventInviteMessage`, und keine `encEventResponseMessage`-RSVP-Verschlüsselung, wurde in `baron-baileys-v2` 1.5.17 gefunden, über das hinaus, was `WA_MESSAGE_SECRETS.md` §17 bereits für den geteilten Add-on-Krypto-Pfad dokumentiert (es kann ein eingehendes `encEventResponseMessage` mit der generischen Use-Case-Tabelle entschlüsseln, aber es existiert kein eventspezifischer Sender oder Event-Modell-Code). `eventMessage` und `eventInviteMessage` sind ansonsten einfache `Message`-Felder und sendbar via `snowi.sendjson` mit den Skalarfeldern aus §2/§3 — das Zusammenstellen eines solchen benötigt den Krypto-Helper überhaupt nicht, nur `encEventResponseMessage` (das RSVP) tut das. Kein GraphQL-Client für die `www`-Ops aus §6 existiert in Baileys; diese benötigen einen persisted-`doc_id`-GraphQL-POST-Pfad, der nicht implementiert ist.

| Thema | Baileys | Android |
|---|---|---|
| `eventMessage`/`eventInviteMessage` senden | einfaches `Message`-Feld, erreichbar via `snowi.sendjson` | gleich |
| `encEventResponseMessage` verschlüsseln | nicht implementiert (nur-decrypt, generischer Use-Case-Pfad) | `DU9.ADr` + `MessageSecretCryptoHelper` |
| Events-v2-GraphQL-Ops (§6) | nicht implementiert | `GraphqlEventsDataSource` |
| MEX-Push-Sync (§6.1) | nicht implementiert | `DefaultEventsNotificationRepository` |

---

## 15. Fehlerfälle / Gotchas

| Symptom | Ursache | Notiz |
|---|---|---|
| RSVP-Entschlüsselung schlägt fehl / Fehler 51 | falscher Original-Message-Key, oder Sender-/Target-Namespace-Mismatch (PN vs. LID) | geteilt mit Poll-Vote-/Comment-Pfad, siehe `WA_MESSAGE_SECRETS.md` §18 |
| Event in der Events-Liste sichtbar, aber nie im Chat erschienen | MEX-Push (`xwa2_notify_event_on_invite`) hat es unabhängig von der Chat-Zustellung synchronisiert | §6.1 |
| Standort/Gästeliste fehlt bei einem Eingeladenen | noch nicht per RSVP geantwortet (Standort gegatet), oder Gast nicht in den Kontakten/Chat-Verlauf des Betrachters (Gästeliste begrenzt) | §10 |
| Entfernter Gast kann weiterhin über alten Link per RSVP antworten | Gast-Entfernung setzt den Link nur für *diesen* Gast-Datensatz zurück, andere Besitzer des bereits geteilten Links sind nicht betroffen | §8, `str19ed` |
| "Can't change event" / Event gesperrt | Event ist aus Policy-Gründen gesperrt, nicht nur abgebrochen | §8 |
| Companion-Device kann das Event nicht öffnen | Events-v2-Interaktion ist nur-primär-Gerät, auch wenn die Stanza selbst companion-zustellbar ist | §11 |
| `EventInviteMessage.status` (13) kann nicht präzise geparst/erzeugt werden | Enum-Klasse statisch nicht wiederherstellbar; **nicht nachgewiesen** identisch mit dem GraphQL-`rsvp_status`/`status`-Vokabular | §3, §5.3 |

---

## 16. Wichtige Unterscheidungen

| Dies | Nicht dies |
|---|---|
| `eventMessage` (Feld 75, Basis, 12 Felder, unverändert seit vor-41.6) | `eventInviteMessage` (Feld 122, `DTQ`, 13 Felder, die aktive "Events v2"-Karte) |
| `encEventResponseMessage` (E2E-verschlüsseltes RSVP-Echo im Chat) | `UpdateEventRsvp`/`JoinEventViaLink` (plaintext GraphQL-RSVP, serverseitig sichtbar) |
| Abbrechen (setzt `isCanceled`, schließt RSVP, Event bleibt sichtbar) | Löschen (entfernt aus der Liste des Hosts; Chat-Einladungen bleiben, als gelöscht markiert) |
| Löschen (host-initiiert, betrifft die Kopie des Hosts + markiert für andere als gelöscht) | Verlassen (gast-initiiert, Gast sieht keine weiteren Updates mehr) |
| Sperren (serverseitiger Moderations-Lock) | Abbrechen (Host-Aktion) |
| Gast entfernen + Link zurücksetzen (Host, invalidiert *diese* Gast-Link-Kopie) | Einladung entfernen (Host, bevor der Gast beigetreten ist) |
| `E2D`/`C9T8`-wire-mirroring RSVP-Enum (GOING=1, NOT_GOING=2, MAYBE=3, UNKNOWN=0) | `C9T6`-lokales-DB-Enum (GOING=0, NOT_GOING=1, MAYBE=2, NO_RESPONSE=3) — andere Reihenfolge, gleiches Konzept |
| `C9U0`-GraphQL-`rsvp_status`-String-Enum (`GOING`/`MAYBE`/`NOT_GOING`/`NO_RESPONSE`) | `EventInviteMessage.status` (Feld 13) Wire-int32-offenes-Enum — unrecovered, nicht nachgewiesen übereinstimmend |
| Gästeliste-Sichtbarkeit (begrenzt auf die Kontakte des Betrachters) | Event-Sichtbarkeit via Link/QR (offen für jeden, der den Link besitzt) |

---

## 17. Vollständiger Ablauf (Gruppen-Event, Erstellen → RSVP → Update)

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

## 18. Unbekannte

| Punkt | Status |
|---|---|
| `EventInviteMessage.status` (Feld 13) Enum-Member-Namen | statisch nicht wiederherstellbar; GraphQL-`rsvp_status`/`status`-Strings (§5.3) sind ein plausibles, aber unbestätigtes Analogon |
| `reminderOffsetSec` exakte Sekunden pro Picker-Option | inferred (0/900/1800/3600/86400), Konstanten-Pool nicht aufgelöst |
| Join-Link-/QR-URL-Format (`chat.whatsapp.com/event/...` oder ähnlich) | in diesem Pass nicht in Strings oder Manifest-Intent-Filtern gefunden |
| Numerische Feature-Flag-IDs, die Events-v2-Erstellung/RSVP/Companion-Redirect gaten | nicht gefunden (siehe §13) |
| Exakte Beziehung zwischen `EventInviteMessage.status` und den lokalen `C9T6`/`C9T8`-App-Enums | nicht nachverfolgt |
| Verhalten von "Require approval to join" (`str1a34`) | String gefunden; Code-Pfad nicht nachverfolgt |
| Ob die History-Sync-Felder `eventResponses`(61)/`eventAdditionalMetadata`(64) bei ausgehendem History-Sync, eingehendem, oder beidem befüllt werden | nicht nachverfolgt |
