<!-- src-sha1: 0c8270cd51a33a8c9e23ceb0a6129e273e5cb070 -->
# WhatsApp Group History — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Group-History-Sharing auf Android (aktuelle Gruppennachrichten an neue Mitglieder senden): Admin-Einstellung `member_share_group_history_mode`, Berechtigung von Sender und Empfänger, Add-/Approval-Join-Flow und Pending-Job, Nachrichtenauswahl und Limits, `MessageHistoryBundle` (Feld 70) und `MessageHistoryNotice` (Feld 102), inneres `GroupHistory`-Proto, Verschlüsselung und Upload der Bundle-Medien, Validierung und Import beim Empfänger, Gruppen-Metadaten (Teilnehmer, LID- vs. PN-Adressierung, Community-Beziehungen), Sender-Key-Nutzung, Reporting-Tokens, Companion-HistorySync (`HistorySyncConfig`, Sync-Typen, On-Demand-Peer-Operationen), Feature-Flags, Baileys

---

## 1. Was es ist (technisch)

Group-History-Sharing erlaubt einem Gruppenmitglied (Admin, oder jedes Mitglied, wenn der Admin es erlaubt), ein Bundle aktueller Gruppennachrichten an gerade hinzugefügte Personen zu senden, damit der Neuling Kontext sieht. Es ist eine normale Ende-zu-Ende-verschlüsselte Gruppennachricht, deren Payload eine Mediendatei ist (ein Protobuf aus `WebMessageInfo`-Einträgen). Es ist **nicht** der HistorySync der Companion-Geräte (Abschnitt 11), obwohl beide das Wort „history“ und einige Capability-Flags teilen.

Alle Aussagen stammen aus der statischen Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = in Code oder Ressourcen gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst. Obfuszierte Namen wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst (`FMessageGroupHistoryBundleProtobuf`, `GroupHistorySendPermissionChecker`, `PendingSendGroupHistoryJob`, `member_share_group_history_mode`, `Group History`).

| Entität | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| Bundle-Nachricht | `C213539Ar` (`FMessageGroupHistoryBundle`), FMessage-Typ **117** | äußere Medien-Nachricht, `Message.messageHistoryBundle` Feld **70** |
| Notice-Nachricht | `C213519Ap` (`FMessageGroupHistoryNotice`), FMessage-Typ **118** | Zeile „History wurde gesendet“, `Message.messageHistoryNotice` Feld **102** |
| Bundle-Serializer / -Parser | `C34677F2y` (`FMessageGroupHistoryBundleProtobuf`) | äußere Nachricht bauen und validieren |
| Notice-Serializer / -Parser | `C34678F2z` (`FMessageGroupHistoryNoticeProtobuf`) | Notice bauen und validieren |
| Bundle-Builder | `C9mW.A00` (+ `C231239yy`, `FMessageGroupHistoryBundleFactory`) | auswählen, packen, Datei schreiben, Medien-Nachricht erzeugen |
| Nachrichtenauswahl | `A0G` (`GroupHistoryMessageManager`) | SQL für Anzahl und Zeilen |
| Berechtigung | `A1W` (`GroupHistorySendPermissionChecker`), `C230099x1` (Gates) | Prüfungen für Sender / Empfänger / Entry-Point |
| Pending-Job | `PendingSendGroupHistoryJob`, `SendGroupHistoryJobRequirement` | dauerhafter Job nach dem Hinzufügen |
| Requirement-Provider | `C197318aR` (`SendGroupHistoryRequirementProvider`) | Add-/Approval-Events geben den Job frei |
| Empfänger | `GroupHistoryBundleProcessor`, `GroupHistoryBundleFileProcessor` | herunterladen, parsen, einfügen |
| Validatoren / Inserter | `C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg` (`GroupHistoryMessageValidator` / `GroupHistoryMessageInserter`) | Prüfungen pro Nachricht und DB-Insert |
| Media-Type-Zeile | `C15530gU.A0F` | `group-history`, `GROUP_HISTORY`, HKDF-Info `Group History`, id **117** |
| Einstellungs-UI | `com.whatsapp.grouphistory.setting.ui.*`, `GroupPermissionsActivity` (`C201678ic`) | Mengen-Dialog, Footer-Toggle, Berechtigungs-Schalter |

Pro Share existieren zwei getrennte Nachrichten: das **Bundle** (trägt die Daten, geht an die Gruppe) und die **Notice** (trägt nur Anzahlen und Empfänger, wird gesendet, nachdem das Bundle das Gerät verlassen hat, Abschnitt 5.4).

---

## 2. Gruppen-Metadaten und Einstellungen

### 2.1 Gruppen-Info-Node (`<group>`, Legacy-XMPP-Pfad `C23201A1a.A0C`)

Wird vom selben Helper für `w:g2`-Abfragen und Gruppen-Notifications geparst; ein MEX/SMAX-Gegenstück existiert (`AbstractC23204A1d`, `AN6`, `C23690AKd`). Nur Felder, die hier und für die Adressierung relevant sind:

| Attribut / Kind | Typ | Verwendung |
|-----------------|-----|------------|
| `id`, `creation`, `subject`, `s_t`, `s_o`, `s_o_pn`, `creator`, `creator_pn` | Attribute | Identität; die `_pn`-Gegenstücke tragen die Telefon-JID neben einer LID |
| `addressing_mode` | `lid` oder `pn` | gespeichert in `wa_group_admin_settings.addressing_mode`; alles außer `pn` wird als `lid` gelesen (`AbstractC268510t`) |
| `<group_history/>` | leeres Kind | boolesche Präsenz; gespeichert als `history_enabled`; Bedeutung inferred (Feature-Flag der Gruppe) |
| `<member_share_group_history_mode>` | Text | Admin-Einstellung, 2.4 |
| `<member_add_mode>` | `all_member_add` / andere | `member_add_mode` 1 / 0 |
| `parent`, `default_sub_group`, `linked_parent jid`, `general_chat` | Kinder | Gruppentyp, 2.3 |

### 2.2 Teilnehmer und Adressierung (found)

`<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`):

| Attribut | Verwendung für Group History |
|----------|------------------------------|
| `jid` | Teilnehmer, LID oder PN je nach `addressing_mode`; eine PN-JID mit `phone_number`-Attribut wird auf Mismatch geprüft |
| `lid`, `phone_number` | die jeweils andere Adressform; gespeichert über das JID-Mapping-Repository |
| `join_time` | positiver Long (Sekunden, inferred); pro Teilnehmer gespeichert; Grundlage für „joined too long ago“ |
| `group_history_sent` | `"true"` / `"false"`, Boolean; speist `group_participant_user.group_history_send_state` (Mapping inferred, 3.2) |

Empfänger- und Senderlisten in den Bundle-Metadaten (Abschnitt 6.2) sind JID-Strings. Der Job normalisiert sie vor der Verwendung auf den Adressierungsmodus der Gruppe: `PendingSendGroupHistoryJob.A01` bildet jeden Empfänger auf seine **LID** ab, wenn die Gruppe LID-adressiert ist (`C30194DBb.A05`), sonst LID auf PN (`C0YH.A0G` / `AbstractC197018Zw.A0Y`). Wird ein Teilnehmer hinzugefügt, akzeptiert der Job beide Formen (`C0YH.A0J` liefert das Gegenstück), um die Requirement-Sets zu treffen. Welche Form auf der Leitung landet, hängt vom Gruppenmodus ab (inferred aus dem Mapping-Code).

### 2.3 Community- und Parent-Gruppen-Beziehungen

`C23201A1a.A01` klassifiziert einen Gruppen-Node: **0** normal, **1** Community-Parent (`parent`), **2** verknüpfte Sub-Gruppe (`linked_parent`), **3** Default-Sub-Gruppe (`default_sub_group`), **6** General Chat. `A03` liest die Parent-JID aus `linked_parent jid`. Der Default für `membership_approval_mode` bei Sub-Gruppen stammt aus `parent/default_membership_approval_mode="request_required"`.

Found: `A1W` prüft nur den **JID-Typ** (Typen 1 und 2 passieren `C0DZ.A0l`: `@g.us`-Gruppe und die `@temp`-Gruppe `C99Q`), nicht die Community-Rolle. Der Empfänger akzeptiert nur Typ 1 (`C0DZ.A0b`). Ob eine Parent- / Announcement-Gruppe durch serverseitige oder per-Gruppe-Experiment-Gates ausgeschlossen wird (23245 / 30905 sind per Gruppe), ist unknown. Comment-Nachrichten (Kommentare in Community-Announcements) und Association-Kinder reisen in separaten Listen (6.1); der Empfänger verwirft einen Kommentar oder ein Kind, dessen Parent nicht im Bundle ist (`orphan_parent_not_in_bundle`, `invalid_comment`).

### 2.4 Admin-Einstellung `member_share_group_history_mode`

| Wire-Wert | Enum (`EnumC216299Tq`) | Lokaler Int | Bedeutung |
|-----------|------------------------|-------------|-----------|
| fehlt / unbekannt | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` 0 | 0 | nicht gesetzt |
| `admin_share` | `ADMIN_SHARE` 1 | 1 | nur Admins senden History |
| `all_member_share` | `ALL_MEMBER_SHARE` 2 | 2 | jedes Mitglied darf senden |
| `all_member_share_toggle_on` | `ALL_MEMBER_SHARE_TOGGLE_ON` 3 | 2 | wie 2; in Notifications gesehene Variante (Unterscheidung inferred) |

Mapping: `AbstractC227759t3.A01(String)` (String zu Int), `A00(enum)` (Enum zu Int, 2 und 3 zu 2).

| Punkt | Detail (found) |
|-------|----------------|
| Setzen | `GroupPermissionsActivity`-Schalter (`C201678ic.A04`): MEX-Operation `SetGroupProperty` (Client `whatsapp-android-mex`, Input-Klasse `C204518nF`) mit `member_share_group_history_mode` = `ALL_MEMBER_SHARE` oder `ADMIN_SHARE`. Derselbe Input trägt außerdem `allow_admin_reports`, `allow_non_admin_sub_group_creation`, `announcement`, `hidden_group`, `locked`, `member_add_mode`, `member_link_mode`, `membership_approval_mode_enabled`, `participant_label_enabled`, `subject` |
| Notification | Gruppen-Notification (`w:gp2`, inferred) Kind `member_share_group_history_mode` (`C22270sr`) ruft `A0g(actor, group, mode int, ts)` auf: aktualisiert den gespeicherten Modus und fügt eine Systemnachricht ein |
| Systemnachricht | „turned on / off recent history sharing for new members“ in sechs Varianten (Akteur `%s`, „Recent history sharing was ...“, „You ...“), jeweils mit „Tap to change“ oder „Tap to learn more“ |
| History-Sync | `GroupShareGroupHistoryModeHistorySync` erzeugt die Systemnachricht für Companions neu; `GroupChangeHistoryEnabledHistorySync` tut dasselbe für `history_enabled` |
| DB | `wa_group_admin_settings`: `share_group_history_setting_mode`, `group_history_toggle_mode`, `history_enabled`, `earliest_group_history_message_timestamp_ms` |

Die Bedeutung von `group_history_toggle_mode` (Int, getrennt vom Share-Modus) ist nicht aufgelöst; die Spalte wird für Gruppen gelesen, in denen sie ungleich null ist und `group_state = 0` gilt. UI-Texte: „Admins can choose if members are allowed to send message history“, „Admins control if history is sent“, „When adding someone to the group, members have the choice to send up to 100 recent messages“.

---

## 3. Berechtigung

### 3.1 Sender (`A1W.A03`, found)

| # | Bedingung | Sonst |
|---|-----------|-------|
| 1 | Kill-Switch **35987** an (Sender-Voraussetzungen) | `PREREQUISITES_DISABLED` |
| 2 | Gruppen-JID-Typ 1 oder 2 | `GROUP_TYPE_NOT_ELIGIBLE` |
| 3 | Gruppen-Kontaktzeile existiert | `GROUP_NOT_FOUND` |
| 4 | Ich bin in der Gruppe, und entweder bin ich Admin / Superadmin, oder (`require_membership_approval` = false und `member_add_mode` = 1 und Share-Modus = 2) | `SENDER_NOT_ELIGIBLE` (Log listet die drei Werte) |
| 5 | mindestens eine teilbare Nachricht existiert (`A0G.A00` Anzahl > 0) | `NO_SHAREABLE_MESSAGES` (korrigiert auch den gespeicherten Earliest-Timestamp, `A0A`) |
| 6 | Gate pro Entry-Point `A1W.A02` (3.3) | `EXPERIMENT_DISABLED` |

Ein einfaches Mitglied kann also nur in Gruppen senden, in denen jeder Mitglieder hinzufügen darf, keine Genehmigung nötig ist und der Admin `all_member_share` aktiviert hat.

### 3.2 Empfänger (pro hinzugefügtem Nutzer, found)

| Prüfung | Ergebniscode |
|---------|--------------|
| Empfänger ist kein Bot (`AbstractC24760wu.A03`) | `RECEIVER_NOT_ELIGIBLE` |
| Empfänger-Kontakt ist nicht „no longer active“ (`externalUserState`, `A07`) | `RECEIVER_INACTIVE` |
| Teilnehmerzeile für (Gruppe, Nutzer) existiert | `NOT_IN_GROUP` |
| `now - join_time` unter Flag **30333** (Einheit nicht aufgelöst) und `group_history_send_state` ist null oder 1 | `NOT_NEW_OR_ALREADY_SENT` |

`group_history_send_state` (Spalte von `group_participant_user`, geschrieben von `C14850fN.A0R`): 1 = noch berechtigt, 2 = bereits gesendet (found aus dem „already sent“-Zweig und dem Cancel-Pfad, der 2 auf 1 zurücksetzt). Das Mapping des Wire-Attributs `group_history_sent` auf den State ist inferred.

### 3.3 Gates (`C230099x1`, `A1W.A02`)

Jedes Gate ist `globales Flag OR per-Gruppe-Exposure` (`C41861nA.A04(group, id)`):

| Helper | Global | Per-Gruppe-id | Verwendung |
|--------|--------|---------------|------------|
| `A01` | **26451** | 30905 | Entry-Point `AFTER_JOIN` |
| `A02` | **15313** | 23245 | History beim Hinzufügen senden (`A1W.A0B`), steuert auch `onGroupParticipantsAdded` |
| `A03` | **29973** | 30906 | Aufrufer nicht verfolgt |

Entry-Points (`C9SA`): `AFTER_JOIN`, `FROM_MENTION`, `FROM_CONTACT_MESSAGE`. `FROM_MENTION` und `FROM_CONTACT_MESSAGE` sind zusätzlich an die Kill-Switches **35554** / **35555** und an das Gate `A02` gebunden. Die Polarität der kombinierten Prüfung ist nicht aufgelöst (Dekompilat-Flow ist um `A1W.A09` verworren).

---

## 4. Join-Flow (Sender-Seite)

### 4.1 UI-Entry-Points (found)

| Entry | Klasse | Was passiert |
|-------|--------|--------------|
| Add-Members-Picker | `VoipParticipantPickerFragment` + `GroupHistoryAddMembersSettingFooterView` | Footer „Send message history to approved members“ mit Toggle und Link „recent messages“; Antippen öffnet den Mengen-Dialog; Toggle-Zustand wird gemerkt (`is_group_history_toggled`) |
| Membership-Approval-Screen | `GroupMembershipApprovalRequestsFragment` (`C24002AWf`) | derselbe Mengen-Dialog vor dem Genehmigen |
| Post-Join-Sheet | `GroupHistoryAfterJoinSendBottomSheetFragment` | „Send message history to %1$s?“ (ein oder zwei Namen) |
| Mention / geteilter Kontakt | Entry-Points `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | nur Namen; Verhalten nicht verfolgt |

Bestätigungstext bei der ersten Nutzung: „Group history messages are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.“ (Zähler `group_history_confirmation_dialog_confirmed_times`).

### 4.2 Mengenoptionen (`C229129vL.A00(n)`, found)

`n` = Anzahl aus `A0G.A00` (Nachrichten, die in die Limits aus 5.1 passen).

| n | Optionen |
|---|----------|
| 0 | keine („No message history to view“) |
| 1..25 | eine Option, `n`, markiert „all“ („Last %d (all)“) |
| > 25 | `k = min(4, ceil(n/25))`, `step = max(25, n/k)`; Optionen `step`, `2*step`, ... bis `k-1` Schritte, dann `n` (markiert „all“ unter einer Größenbedingung am letzten Schritt; genauer Vergleich nicht aufgelöst) |

Die Liste wird dann von `C0CG.A0Z` umgekehrt (inferred: größte zuerst); der erste Eintrag ist vorausgewählt. Ein Hinweis zu angehefteten Nachrichten („All available pinned messages will be included“) wird immer angezeigt.

### 4.3 Add-IQ und Event-Verdrahtung (found)

```xml
<iq xmlns="w:g2" type="set" to="GROUP@g.us" id="…">
  <add>                                       <!-- optional transparency_acknowledged="true" -->
    <participant jid="USER"><privacy>bytes</privacy></participant>   <!-- privacy child optional -->
  </add>
</iq>
```

Beim Lesen des Builders (`C11410Yt`) gefunden: Der Add-Request erhält kein history-spezifisches Attribut; die History-Entscheidung ist rein lokal. Events, die den Pending-Job freigeben (`C197318aR`, Timeout 32 s für die IQ selbst):

| Event | Handler | Wirkung |
|-------|---------|---------|
| History angefordert | `CCP(params, group, requestId, receivers, nonReceivers, approvedByMe)` | `PendingSendGroupHistoryJob` persistieren; gewählte Anzahl in `A08[requestId]` merken; `group_history_usage_activated` setzen |
| Add-IQ beantwortet | `BfO(C222169gu)` | Ergebnis-Map pro Request speichern |
| Teilnehmer hinzugefügt (Notification) | `BvD` (nur wenn Gate `A02`) | zu den Sets „added by me“ / „added by others“ hinzufügen |
| Membership-Approval beantwortet | `C05(group, user, requestId, approved)` | genehmigten Nutzer (oder leer) speichern |

### 4.4 Pending-Job (`PendingSendGroupHistoryJob`, found)

Felder: `permanentGroupRawJid`, `requestId`, `messageCount`, `lastMessageSortId`, `groupHistoryReceiverRawJids`, `groupHistoryNonReceiverRawJids`, `approvedByMeRawJids`, `jobScheduledServerTimeInMillis`, `expirationTimeInMins`. Persistente Job-id `group-pending-send-group-history`, Requirement `SendGroupHistoryJobRequirement` (alle Empfänger-JIDs müssen parsebar sein, sonst `invalid group history receiver jid`).

| Schritt | Detail |
|---------|--------|
| Requirement erfüllt, wenn | Job abgelaufen; oder das Add-/Approval-Ergebnis für `requestId` eingetroffen ist; oder ein Empfänger im Set „added by others“ ist und nicht von mir genehmigt; oder ein Empfänger inzwischen Teilnehmer ist (`A0r`) |
| Ablauf | `scheduled + flag 19034` Minuten; abgelaufener Job: abbrechen, Teilnehmer-State 2 auf 1 zurücksetzen |
| Run | Empfänger in bereits beigetretene und übrige aufteilen; die übrigen gehen in einen **neuen** Pending-Job (gleiche Request-id, Non-Receivers gefiltert); beigetretene Empfänger erhalten das Bundle (`C9mW.A00`) |
| Bot-Empfänger | ein TEE-Bot-Empfänger (`AbstractC197238aI.A00`) wird über einen separaten History-Share-Stamp behandelt (`A04`, 5.5) |
| Duplikat-Schutz | `C197318aR.A09` Map (Gruppe, Nutzer) auf Sendezeit; Einträge älter als `19034` Minuten (min 5) werden entfernt |

---

## 5. Auswahl, Limits und Packen

### 5.1 Zeilenauswahl (`A0G`, `AbstractC494421h.A00`, found)

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

| Parameter | Quelle |
|-----------|--------|
| `n` | die Count-Query nutzt Flag **18405** als LIMIT; die Send-Query nutzt die vom Nutzer gewählte Anzahl |
| Fenster | Flag **18406** (Sekunden) vor der Scheduling-Zeit; UI-Text verspricht „up to 100“ Nachrichten |
| teilbare Typen | Registry pro FMessage-Typ (`C222979iT.A00`, `C1ZP.BUv()` true), mit Override pro Nachricht (`C30039D5b`); hier nicht aufgezählt |
| eigene Nachrichten | nur solche, die das Gerät verlassen haben (`status` nicht in der Pending-/Failed-Menge `AbstractC494421h.A00`) |
| ephemeral | abgelaufene und nicht behaltene Nachrichten werden übersprungen |

Ist eine Post-Join-Sort-id bekannt (`C14650f0.A05`), verankert sich die Zählung daran („post-join query“); sonst an der neuesten Nachricht („pre-join query“).

### 5.2 Listen im Bundle (found, `C9mW.A00`)

| Liste | Inhalt | Limit |
|-------|--------|-------|
| `messages` | die ausgewählten Zeilen (nur teilbare) | `n` |
| `uncountedAssociatedMessageLists` | an eine ausgewählte Parent-Nachricht gehängte Kinder (Album-Items, Polls, ...), gruppiert nach `(parent key, association type)`; nur bei **24033** | nicht in `messageCount` gezählt |
| `commentMessages` | Kommentare zu ausgewählten Nachrichten (`C14780fG.A02(list, flag 6050, …)`) | Flag **6050** (inferred als Obergrenze) |
| `outOfWindowPinnedMessages` | angeheftete Nachrichten, älter als die älteste ausgewählte; nur Nicht-Medien; gefiltert über die teilbare Menge | alle verfügbaren (Disclaimer-String); Empfänger-Obergrenze Flag **19811** (inferred) |

Association-Typen (`C13O`, 21 Werte): `FUTURE` 0 (auch Fallback), `MEDIA_ALBUM` 1, `BOT_PLUGIN` 2, `EVENT_COVER_IMAGE` 3, `HD_VIDEO_DUAL_UPLOAD` 5, `STATUS_EXTERNAL_RESHARE` 6, `MEDIA_POLL` 7, `POLL_ADD_OPTION` 20, `STREAMED_HD_VIDEO_DUAL_UPLOAD` 22 und weitere Status- / Sticker- / Dual-Upload-Arten.

### 5.3 Packen (found)

1. Das `GroupHistory`-Proto (6.1) wird in eine Datei mit der Endung `proto` serialisiert (`File … A0Z(C15530gU.A0F, "proto")`); ein Kompressionsschritt wurde nicht gefunden.
2. Eine neue FMessage vom Typ 117 wird im Gruppenchat mit der Datei als Medium erzeugt (`mimetype application/protobuf`) und an die normale Media-Message-Send-Pipeline übergeben (Upload und Verschlüsselung, Abschnitt 7).
3. Lokale Felder der FMessage: Nachrichtenanzahl, ältester Timestamp im Fenster (Sekunden), ältester Timestamp gesamt (min mit angehefteten Nachrichten), Empfänger, Non-Receivers, Größen der gepackten Nachrichtenlisten, Dateigröße, Build-Zeit (Telemetrie).
4. Ist **24741** an und die Nachricht hat kein Secret, wird ein frisches Message-Secret erzeugt, danach werden Reporting-Tokens pro Originalnachricht berechnet (Abschnitt 9).

### 5.4 Notice nach dem Senden (found, `ANQ.C0M`)

Erreicht das Bundle Status **1** (oder **24**, wenn Flag **28787** an ist) und die Notice wurde noch nicht gesendet (`A00 != 1`), erzeugt das Gerät eine Typ-118-Notice in derselben Gruppe mit den Anzahlen, Timestamps und Empfängern des Bundles und sendet sie (`C33166Ecf.A06`). Jedes Gruppenmitglied erhält sie; in `historyReceivers` genannte Empfänger markieren sie zusätzlich (`AbstractC30028D4q.A1B`).

### 5.5 TEE-Bot-History-Share (found, kurz)

Für einen Bot-Empfänger versieht `C9mW.A01` ausgewählte Nachrichten mit einem Message-Secret mit einem Proof (`AbstractC33322EfC.A02(sender, botJid, "TEE History Share", stanzaId, secret)`) und sendet eine Notice, deren `botHistoryShareSyncMetadata` `(stanzaId, messageSecretProof)` listet. Zum Bot-Kontext siehe den Meta-AI-Report: [WA_META_AI.md](./WA_META_AI.md). Der Bot-Pfad lädt kein Bundle hoch.

---

## 6. Wire-Format

### 6.1 Innere Datei: `GroupHistory` (`DSN`)

| Feld | Nummer | Typ | Inhalt |
|------|--------|-----|--------|
| `messages` | **1** | repeated `WebMessageInfo` (`C30626DTu`) | gezählte Nachrichten |
| `uncountedAssociatedMessageLists` | **2** | repeated `UncountedAssociatedMessageList` (`C30578DRy`) | `messages` **1** (repeated WebMessageInfo), `parentMessage` **2** (`MessageKey`, `BD5`), `associationType` **3** (Enum `C13O`) |
| `commentMessages` | **3** | repeated `WebMessageInfo` | Kommentare |
| `outOfWindowPinnedMessages` | **4** | repeated `WebMessageInfo` | Pins |

Der Empfänger parst dieselben Bytes ein zweites Mal als `GroupHistoryWithMessageBytes` (`C30576DRw`: dieselben vier Feldnummern; Einträge `C30543DQp` mit `key` **1** (`MessageKey`) und `message` **2** (bytes); Association-Listen `DPH` lesen nur `messages` **1**). Diese Variante behält die ursprünglich serialisierten Bytes pro Nachricht (genutzt für die Validierung von Reporting-Tokens und die Secret-Behandlung, inferred).

### 6.2 Äußere Nachricht: `Message.messageHistoryBundle` (`DT6`, Feld **70**)

| Feld | Nummer | Typ | Wert / Verwendung |
|------|--------|-----|-------------------|
| `mimetype` | **1** | string | muss `application/protobuf` entsprechen |
| `fileSha256` | **2** | bytes | 32 Bytes, Klartext-Hash |
| `mediaKey` | **3** | bytes | Media-Key |
| `fileEncSha256` | **4** | bytes | 32 Bytes, Ciphertext-Hash |
| `directPath` | **5** | string | Upload-Pfad; leer wird geloggt, beim Parsen nicht fatal |
| `mediaKeyTimestamp` | **6** | int64 | Sekunden |
| `contextInfo` | **7** | `ContextInfo` | Standard |
| `messageHistoryMetadata` | **8** | `MessageHistoryMetadata` (`C30583DSd`) | siehe unten |

`MessageHistoryMetadata`:

| Feld | Nummer | Typ | Regel beim Empfang |
|------|--------|-----|--------------------|
| `historyReceivers` | **1** | repeated string | mindestens einer; der aktuelle Nutzer muss gelistet sein |
| `oldestMessageTimestampInWindow` | **2** | int64 | vorhanden und > 0 |
| `messageCount` | **3** | int64 | vorhanden und > 0 |
| `nonHistoryReceivers` | **4** | repeated string | optional |
| `oldestMessageTimestampInBundle` | **5** | int64 | optional (enthält Pins) |

### 6.3 Notice: `Message.messageHistoryNotice` (`DRY`, Feld **102**)

`contextInfo` **1**, `messageHistoryMetadata` **2** (gleicher Typ, erforderlich mit Regeln für Empfänger, Timestamp und Anzahl), `botHistoryShareSyncMetadata` **3** (`C25765B9z`: `botJid` **1**, `historyShareMessages` **3** repeated `BA2` = `stanzaId` **1**, `messageSecretProof` **2**). Das Lite-Layout hat kein Feld **2** in `C25765B9z`; ein Cutoff existiert nur als lokaler State (`C213519Ap.A03`).

### 6.4 Stanza-Ebene (found)

| Punkt | Bundle (117) | Notice (118) |
|-------|--------------|--------------|
| Stanza-`type` | `media` | nicht medienspezifisch |
| `<enc>`-Media-Type | `group_history` (`C30106D7q`; in der erlaubten Enc-Media-Type-Menge `C9E2` / `C33474Ehg`) | keiner |
| `<meta appdata="…">` | **nicht gesetzt** (`C213539Ar` implementiert `FZF` nicht) | `group_history` (`C213519Ap.AVN`; `F6K` schreibt es) |
| Empfänger-Prüfung | `A0O == "media"` und `A0J == "group_history"`, sonst Fehler 11 | `appdata == group_history`, sonst Fehler 76 |
| `<reporting>` | optional, Abschnitt 9 | keines |

Beide Prüfungen werden übersprungen, wenn die Envelope-Flags `A0V` / `A0U` gesetzt sind (Bedeutung ungeklärt). Ein Bundle, das mit Media-Type `group_history` aber ohne passende Nachricht ankommt, sowie ein Notice-Appdata auf einem fremden Typ werden von `GroupHistoryBundleDeserializationValidator` / `GroupHistoryNoticeDeserializationValidator` (`F3b` / `F3c`) abgelehnt.

### 6.5 `WebMessageInfo`-Marker (`C30626DTu`, found)

| Feld | Nummer | Typ | Verwendung |
|------|--------|-----|------------|
| `isGroupHistoryMessage` | **57** | bool | Nachricht wurde aus einem Bundle importiert |
| `reportingTokenInfo` | **62** | message | Reporting-Tag (siehe Reporting-Report) |
| `groupHistoryIndividualMessageInfo` | **74** | `C30549DQv` | `bundleMessageKey` **1** (`MessageKey`), `editedAfterReceivedAsHistory` **2** (bool) |
| `groupHistoryBundleInfo` | **75** | `C30548DQu` | `deprecatedMessageHistoryBundle` **1**, `processState` **2** (Enum `EnumC32128E2a`) |

`processState`: `NOT_INJECTED` 0, `INJECTED` 1, `INJECTED_PARTIAL` 2, `INJECTION_FAILED` 3, `INJECTION_FAILED_NO_RETRY` 4, `DEDUPED` 5.

---

## 7. Verschlüsselung und Medien

| Schicht | Found |
|---------|-------|
| Nachrichtentransport | normales Gruppen-Fan-out: die 117-Nachricht wird wie jede Gruppennachricht verschlüsselt (Sender-Key-`skmsg` pro Gruppe plus die übliche Sender-Key-Distribution an Geräte). Grundlagen werden hier nicht wiederholt; die `<enc>`-Stanza-Form steht in [WA_CALL_SIGNALING.md](./WA_CALL_SIGNALING.md) im Abschnitt zu `<enc>`. Der Sender-Key-State pro Gerät liegt in `group_participant_device` (`sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket`) |
| Media-Zeile | `C15530gU.A0F`: Upload-Typ `group-history`, Dateityp `GROUP_HISTORY`, HKDF-Info `Group History`, id 117 |
| Key / Cipher | zufälliger Media-Key, HKDF-SHA256 mit Info `Group History`, AES-256-CBC, HMAC-SHA256 auf 10 Bytes gekürzt angehängt, `fileSha256` / `fileEncSha256` im Proto: das generische Schema in [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) Abschnitt 6 (80-Byte-Expansion auf Android); über die gemeinsame Send-Pipeline auf diesen Typ angewendet (inferred, nur die Typ-Zeile wurde gelesen) |
| Upload-URL | `https://<host>/mms/group-history/<hash>?…`; die Komposition `mms/<upload type>` ist für die Tabelle found (Abschnitt 4 des Media-Reports); der literale Pfad für diesen Typ wurde nicht erfasst (inferred) |
| Download | Standard-Media-Download mit `mediaKey`, `directPath`, Hashes; Fehlertext `GroupHistoryBundleProcessor/download failed for … with reason …` |
| Key-Wiederverwendung | der Bundle-Media-Key ist unabhängig von den Message-Keys der enthaltenen Nachrichten |

Der Empfänger arbeitet immer mit dem `mediaKey` des Protos; ein Bundle, dessen Hashes nicht 32 Bytes lang sind, wird abgelehnt (`bogus sha-256 hash received`, Fehler 14).

---

## 8. Empfänger: Validierung und Import

### 8.1 Prüfungen beim Parsen (`C34677F2y.CM7`, found)

| Prüfung | Fehler |
|---------|--------|
| Chat-JID ist eine Gruppe (`A0l`) | 11 `chatJid is not a group` |
| Envelope `media` + Enc-Media-Type `group_history` | 11 |
| `mimetype == application/protobuf` | 11 |
| `fileSha256`, `mediaKey`, `fileEncSha256`, `mediaKeyTimestamp`, Metadaten vorhanden | 11 |
| `historyReceivers` nicht leer, Fenster-Timestamp > 0, Anzahl > 0 | 11 |
| aktueller Nutzer in `historyReceivers` (nicht bei eigenen Nachrichten) | 11 `current user is not in history receivers list` |
| Gate **15311** aus | Platzhalter-FMessage `C35281aa` mit Code **82** („Update to the latest version of WhatsApp to see it“) |
| Hash-Längen 32 | 14 |

Notice (`C34678F2z`): Gruppenchat, Appdata, Metadaten mit Empfängern / Timestamp / Anzahl; Gate **15722** aus ergibt Platzhalter-Code **10008**.

### 8.2 Verarbeitung (`GroupHistoryBundleProcessor`, found, sofern nicht anders markiert)

1. Trigger: Nachricht hinzugefügt (`C0G`) und erneut bei Media-State 3 (`C0M`). Ein Kandidat ist ein Gruppenchat (Typ 1), nicht von mir, State 0 oder 5, mit mir in der Empfängerliste und jünger als Flag **25910** (Einheit nicht aufgelöst; sonst „Message history expired“).
2. Dedupe (Flag **30462**): wurde für dieselbe Join-Session bereits ein Bundle verarbeitet, wird das neue als deduped markiert (`deduped_bundle_for_join_session`), UI: „%1$s also sent you message history, which you already got from someone else“.
3. Medien herunterladen; bei Fehler erscheint „Couldn't download message history from %1$s“.
4. Datei zweimal parsen (`DSN`, `DRw`); Parse-Fehler: `protobuf_parse_failed`.
5. Anker finden: die letzte Gruppen-Join-Nachricht („failed to find latest group join message, adding messages before the first message in chat“, wenn keine vorhanden); ein zu alter Anker: `anchor_message_too_old`.
6. Jede Nachricht validieren und einfügen (8.3); jede eingefügte Zeile mit dem Bundle verknüpfen (`group_history_bundle_association`: `bundle_message_key_id`, `message_row_id`, `message_sort_id`); `isGroupHistoryMessage` markieren.
7. Out-of-Window-Pins: Obergrenze (Flag **19811**, inferred), geteilten Pin-State anwenden (`applySharedPin`).
8. Ausstehende Bot-History-Share-Stamps anwenden (`BotHistoryShareHelper`), dann Telemetrie (`group_history_receiver_user_journey`).

Importierte Zeilen werden vor dem Join-Anker platziert und erscheinen daher über der Zeile „you were added“ (inferred aus der Anker-Logik).

### 8.3 Validierung pro Nachricht (`C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg`, found)

| Skip-Grund | Ursache |
|------------|---------|
| `invalid_jid` | `key.remoteJid` weicht vom Bundle-Chat ab |
| `non_hex_id` | `key.id` ist nicht rein hexadezimal |
| `timestamp_too_old` | `messageTimestamp` nicht neuer als die erlaubte Untergrenze (Logfelder `msgTs`, `allowedTs`, `diff`; Grenze aus lokalem State abgeleitet, Formel nicht aufgelöst) |
| `parse_failed`, `pin_not_parsed` | Proto des Eintrags wurde nicht geparst |
| `not_shareable` | Nachrichtentyp für den Import nicht erlaubt |
| `no_local_copy` | geteilter Pin, dessen Nachricht übersprungen wurde und nicht lokal vorhanden ist |
| `max_limit_reached` | Obergrenze erreicht |
| `timestamp_after_anchor` | Nachricht neuer als der Join-Anker |
| `already_exists`, `duplicate`, `expired` | lokal bereits vorhanden, Duplikat in der Datei, ephemeral abgelaufen und nicht behalten |
| `orphan_parent_not_in_bundle`, `invalid_comment` | Kommentar / Association-Kind ohne seinen Parent in der Datei |
| `insert_exception`, `anchor_messages_failed`, `insert_messages_exception` | lokale DB-Fehler |

Weiter: Eine Nachricht braucht ihr erhaltenes `messageSecret` (Logs `messageSecretLost`, `noMessageSecret`); die lokale Kopie gewinnt, wenn eine Nachricht mit abweichendem Inhalt existiert (`keeping local …`).

Berührte Tabellen (found): `group_history_bundle_association` (`bundle_message_key_id`, `message_row_id`, `message_sort_id`), `group_history_share_reporting_info` (`stanza_id`, `reporting_tag`, `send_timestamp`, `added_timestamp`, `reporting_token`, `reporting_token_version`, `is_send`, `validation_policy`), `group_participant_user.group_history_send_state`, `wa_group_admin_settings` (2.4).

---

## 9. Reporting-Tokens (kurz)

Stanza-Abschnitt für ein Bundle, wenn **24741** an ist (`F6C`, `GhsReportingTokenMessageSendStanzaContributor`):

```xml
<reporting>
  <message id="ORIGINAL_STANZA_ID"><reporting_token v="N">16 bytes</reporting_token></message>
  …
</reporting>
```

Token-Ableitung und Speicherung stehen in [WA_REPORTING.md](./WA_REPORTING.md) (Abschnitt 6.2); ein Teil der Key-Ableitung läuft in nativem Code, daher sind die exakten Bytes allein aus Java nicht reproduzierbar. Beim Empfang erzeugt ein fehlendes Token für eine importierte Nachricht, wenn **5718** und **24742** an sind, die Telemetrie `GROUP_HISTORY_MESSAGE_MISSING_FROM_PUBLIC_STANZA` (und, mit **13063**, eine interne Diagnosezeile); die Nachricht wird in diesem Pfad trotzdem eingefügt (inferred aus dem Kontrollfluss). Ob der Server Tokens verlangt: unknown.

---

## 10. HistorySync der Companion-Geräte (verwandt, keine Group History)

Grundlagen zu Pairing und App-State stehen in [WA_LINKED_DEVICE_PAIRING.md](./WA_LINKED_DEVICE_PAIRING.md) und [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md). Nur, was Gruppendaten betrifft:

### 10.1 `HistorySyncConfig` (`C44601rs`, Companion meldet an; Feldnummern aus dem Lite-Layout)

| Feld | # | Companion-Wert (found) |
|------|---|------------------------|
| `fullSyncDaysLimit`, `fullSyncSizeMbLimit` | 1, 2 | Flags **15284**, **15283** |
| `storageQuotaMb`, `initialSyncMaxMessagesPerChat` | 3, 20 | im verfolgten Zweig nicht gesetzt |
| `recentSyncDaysLimit` | 5 | 0 |
| `supportMessageAssociation`, `supportHostedGroupMsg`, `supportAddOnHistorySyncMigration` | 14, 11, 13 | true |
| `supportGroupHistory` | 15 | Flag **20658** |
| `onDemandReady` / `completeOnDemandReady` | 16 / 18 | `!` Flag **18953** / false |
| `thumbnailSyncDaysLimit` | 19 | Flag **21217** |
| `supportHatchHistory` / Bot-Channel-Liste | 22 / 23 | Flag **26445** / Verzweigung auf **26614** |
| Call-Log, Bot- und CAG-History, `supportNewsletter`, `supportInlineContacts`, ... | 4, 6-8, 12, 24-27 | true (andere false) |

Die übrigen Felder (`supportBizHostedMsg` 9, `supportRecentSyncChunkMessageCountTuning` 10, `supportGuestChat` 17, `supportManusHistory` 21, `supportUniversalReachChat` 26, `supportOmittedConversationIndex` 27) werden hier nicht im Detail behandelt.

### 10.2 Sync-Typen und Nachrichten

| Nachricht | Feld | Inhalt |
|-----------|------|--------|
| `HistorySync` (`C25838BCy`) | `syncType` **1**, `conversations` **2**, `statusV3Messages` **3**, `chunkOrder` **5**, `progress` **6**, `pushnames` **7**, `globalSettings` **8**, `threadIdUserSecret` **9**, `threadDsTimeframeOffset` **10**, `recentStickers` **11**, `pastParticipants` **12**, `callLogRecords` **13**, `aiWaitListState` **14**, `phoneNumberToLidMappings` **15**, `companionMetaNonce` **16**, `shareableChatIdentifierEncryptionKey` **17**, `accounts` **18**, `nctSalt` **19**, `inlineContacts` **20/21**, `omittedConversations` **23/24** | Gruppenkonversationen reisen in `conversations`; `pastParticipants` (**12**) listet ehemalige Gruppenmitglieder |
| `HistorySyncNotification` (`C25834BCt`) | `fileSha256` **1**, `fileLength` **2**, `mediaKey` **3**, `fileEncSha256` **4**, `directPath` **5**, `syncType` **6**, `chunkOrder` **7**, `originalMessageId` **8**, `progress` **9**, `oldestMsgInChunkTimestampSec` **10**, `initialHistBootstrapInlinePayload` **11**, `peerDataRequestSessionId` **12**, `fullHistorySyncOnDemandRequestMetadata` **13**, `encHandle` **14**, `messageAccessStatus` **15** | per Media referenzierter Chunk; der Payload ist `HistorySync` |

Sync-Typen: `INITIAL_BOOTSTRAP` 0, `INITIAL_STATUS_V3` 1, `FULL` 2, `RECENT` 3, `PUSH_NAME` 4, `NON_BLOCKING_DATA` 5, `ON_DEMAND` 6, und im Enum mit 9 Werten (`EnumC26456Bdr`) außerdem `NO_HISTORY` 7 und `MESSAGE_ACCESS_STATUS` 8 (`EnumC26449Bdk` ist die Variante mit 7 Werten).

### 10.3 On-Demand-Peer-Data-Operationen (`EnumC26460Bdv`, found)

| Operation | Id | Request-Feld (`C25823BCh`) | Response-Feld (`C25828BCm`) |
|-----------|----|----------------------------|------------------------------|
| `HISTORY_SYNC_ON_DEMAND` | 3 | `historySyncOnDemandRequest` **4** (`BCR`: `chatJid` **1**, `oldestMsgId` **2**, `oldestMsgFromMe` **3**, `onDemandMsgCount` **4**, `oldestMsgTimestampMs` **5**, `accountLid` **6**, `supportInlineResponse` **7**) | keines definiert; History kommt als `HistorySyncNotification` (inferred) |
| `FULL_HISTORY_SYNC_ON_DEMAND` | 6 | `fullHistorySyncOnDemandRequest` **6** (`BBB`: `requestMetadata` **1** `BBA`, `historySyncConfig` **2**, `fullHistorySyncOnDemandConfig` **3** `C156516k5`: `historyFromTimestamp` **1**, `historyDurationDays` **2**) | `fullHistorySyncOnDemandRequestResponse` **6** |
| `PLACEHOLDER_MESSAGE_RESEND` | 4 | **5** | **4** |
| `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` | 8 | **7** | **8** |

Das Primärgerät hält pro Sync eine Zeile in `msg_history_sync` (`device_id`, `sync_type`, `last_processed_msg_row_id`, `oldest_msg_row_id`, `sent_msgs_count`, `chunk_order`, `sent_bytes`, `last_chunk_timestamp`, `status`, `peer_msg_row_id`, `oldest_message_to_sync_row_id`, `session_id`, `size_limit_bytes`, `full_history_on_demand_request_id`, …). Serverseitige Obergrenzen für Chunk-Größe und Nachrichtenanzahl sind im hier gelesenen Client-Code nicht sichtbar (unknown). Es existiert keine On-Demand-Operation speziell für die geteilte History einer Gruppe.

### 10.4 Group History auf Companions

| Punkt | Found |
|-------|-------|
| Capability | `supportGroupHistory` (Flag **20658**) in `companion-props`; auf dem Primärgerät als `support_group_history` gespeichert (Pairing-Report, Abschnitt 6.2); Consumer nicht verfolgt |
| Bundle-Zustellung | das Bundle ist eine normale Gruppennachricht, daher erhält jedes Gerät eines Empfängers es; Strings für verknüpfte Geräte („Open WhatsApp on your phone and visit this group to see it“) deuten dort auf einen Platzhalter hin (inferred) |
| Primary-Sync-Build | `BuildHistorySyncParams` (`C33151EcQ`) trägt `supportGroupHistory`, `pullGroupHistoryUncountedChildren`, `maxCommentsToAdd`, `supportMessageAssociation`; Consumer nicht verfolgt |
| Systemnachrichten | Änderungen von Share-Modus, history-enabled sowie Member-Add- / Link- / Approval-Modus werden für Companions von den `Group*HistorySync`-Klassen neu aufgebaut |

---

## 11. Feature-Flags und Limits

Flag-ids sind fett; Werte werden vom Server geliefert, kompilierte Defaults wurden nicht aufgelöst (UI-Text sagt „up to 100“ Nachrichten).

| Flag | Typ | Steuert | Tier |
|------|-----|---------|------|
| **35987** | bool | Kill-Switch für Sender-Voraussetzungen | found |
| **15313** / 23245 | bool / Gruppe | Gate `A02`, History beim Hinzufügen senden | found |
| **26451** / 30905 | bool / Gruppe | Gate `A01`, Entry-Point `AFTER_JOIN` | found |
| **29973** / 30906 | bool / Gruppe | Gate `A03` | found (Verwendung unknown) |
| **35554**, **35555** | bool | `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | Polarität inferred |
| **18405** | int | LIMIT der Count-Query (Obergrenze der Angebotsgröße) | found |
| **18406** | int, s | Rückschau-Fenster vor der Scheduling-Zeit | found |
| **19034** | int, min | Ablauf des Pending-Jobs, Dedupe-Prune (min 5) | found |
| **30333** | long | maximale Zeit seit Join für einen Empfänger | found (Einheit ungeklärt) |
| **24033** | bool | Association-Listen und Association-Filter | found |
| **6050** | int | Obergrenze der Kommentarsammlung | inferred |
| **24741** | bool | Reporting-Tokens beim Senden bauen | found |
| **28787** | bool | Notice-Trigger Status 24 statt 1 | found |
| **20658** | bool | Companion meldet `supportGroupHistory` an | found |
| **15311** | bool | Empfang: Bundle akzeptiert (aus: Platzhalter 82) | found |
| **15722** | bool | Empfang: Notice akzeptiert (aus: Platzhalter 10008) | found |
| **30462** | bool | Empfang: Dedupe pro Join-Session | found |
| **25910** | long | Empfang: Frische-Fenster eines Bundles | found (Einheit ungeklärt) |
| **19811** | int | Empfang: Obergrenze für Out-of-Window-Pins | inferred |
| **24034** / **25037** | bool / int | Empfang: Verarbeitung von Association-Kindern und ihr Int-Parameter | inferred |
| **26039** | bool | Inserter-Gate (drei Stellen) | found (Verwendung unknown) |
| **5718** + **24742** | bool | Empfang: Validierung von Reporting-Tokens | found |
| **13063** | bool | interne Diagnosezeile bei fehlendem Token | found |

---

## 12. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| Keine Option „send history“ | Sender nicht berechtigt (3.1), Gruppe nicht LID / PN-konsistent, oder keine teilbaren Nachrichten | Admin aktiviert `all_member_share`, Member-Add-Modus `all_member_add`, keine Genehmigung; oder als Admin senden |
| Empfänger zeigt „Update to the latest version“ | Gate 15311 / 15722 aus oder unbekannter Typ | auf dem Client nichts |
| Bundle abgelehnt, Fehler 11 | falscher MIME, Envelope-Typ, Media-Type, fehlendes Feld, ich nicht in `historyReceivers` | nach Abschnitt 6 bauen |
| Bundle abgelehnt, Fehler 14 | Hash nicht 32 Bytes | Hashes korrigieren |
| Notice abgelehnt, Fehler 11 / 76 | Appdata nicht `group_history` (Parse, 11); Notice-Appdata auf anderem Typ (Validator, 76) | `appdata=group_history` nur auf Typ 118 setzen |
| Nachrichten nach dem Import fehlen | Skip-Gründe in 8.3 (`timestamp_too_old`, `not_shareable`, `invalid_jid`) | Keys müssen Hex-ids derselben Gruppe sein |
| „Couldn't download message history“ | Media-Download fehlgeschlagen (abgelaufener `directPath`, Key-Mismatch) | erneut versuchen; neu senden |
| Job läuft nie | Add- oder Approval-Event nicht gesehen, Empfänger wurden nie Teilnehmer, Job abgelaufen (19034) | erneut hinzufügen und neu senden |

---

## 13. Wichtige Unterscheidungen

| Nicht verwechseln | Mit |
|-------------------|-----|
| Group-History-Bundle (Typ 117, `application/protobuf`, `group-history`) | Companion-HistorySync-Notification (`HistorySyncNotification`, `md-msg-hist`) |
| Bundle (Daten, kein Appdata) | Notice (Anzahlen und Empfänger, `appdata=group_history`) |
| `member_share_group_history_mode` (wer senden darf) | `group_history_toggle_mode` / `history_enabled` (Bedeutung ungeklärt) |
| `historyReceivers` (erhalten die Daten) | `nonHistoryReceivers` (hinzugefügt, erhalten nichts) |
| `oldestMessageTimestampInWindow` (**2**) | `oldestMessageTimestampInBundle` (**5**, enthält Out-of-Window-Pins) |
| `messages`-Anzahl (`messageCount`) | ungezählte Association-Kinder und Kommentare |
| `supportGroupHistory` in `HistorySyncConfig` (Geräte-Capability) | die Admin-Einstellung |

---

## 14. Baileys (`baron-baileys-v2` 1.5.17)

Nur Fakten, die in `src/Utils/group-history.js`, `src/Socket/groups.js`, `src/Socket/messages-recv.js`, `src/Socket/aigroups.js`, `src/Utils/validate-connection.js`, `WAProto/index.js` gelesen wurden. Nichts wurde gegen einen Server getestet; es wird kein Fehler behauptet.

| Thema | Baileys | Android |
|-------|---------|---------|
| Proto | `GroupHistory`, `GroupHistoryWithMessageBytes`, `GroupHistoryBundleInfo`, `GroupHistoryIndividualMessageInfo`, `Message.messageHistoryBundle`, `messageHistoryNotice`, `HistorySyncConfig.supportGroupHistory` in `WAProto` vorhanden | 6 |
| Decoder | `decodeGroupHistory` versucht `zlib.inflateSync`, fällt auf rohe Bytes zurück; optionaler Modus `GroupHistoryWithMessageBytes`; `processGroupHistory` normalisiert die vier Listen | auf Android keine Kompression gefunden; rohes Protobuf gelesen |
| Empfang des Bundles | kein Code behandelt `messageHistoryBundle` (Media-Download, Validierung, Einfügen) | Abschnitt 8 |
| Senden des Bundles | keines | Abschnitt 5 |
| Companion-Capability | `supportGroupHistory: true` in der angemeldeten `HistorySyncConfig` | Flag 20658 |
| Gruppeneinstellung | `member_share_group_history_mode` wird aus den Gruppen-Metadaten gelesen; `groupSetProperty(jid, property, value)` über MEX; Mex-Notification `NotificationGroupMemberShareGroupHistoryModePropertyUpdate` emittiert `groups.update { memberShareHistoryMode }` | 2.4 |
| `aiGroupCreate` | akzeptiert `memberShareGroupHistoryMode` (Default `all_member_share`), legt es im gelesenen Code aber nicht in die Create-Stanza | nicht zutreffend |
| Teilnehmer-Attribute | `group_history_sent`, `join_time` werden nicht geparst | 2.2 |
| Adressierung | `addressing_mode` wird aus dem Gruppen-Node gelesen, beim Senden Default `lid` | 2.2 |

Auf das Gelesene begrenzte Konsequenz: Ein Baileys-Client, der `supportGroupHistory` anmeldet, kann ein empfangenes Bundle nicht importieren, weil im Quellcode kein Consumer existiert. Ein Sender muss den Abschnitten 5 bis 7 folgen (Senden nach dem Hinzufügen, `media`-Typ mit Enc-Media-Type `group_history`, Media-Type `group-history` mit HKDF-Info `Group History`, Notice mit Appdata); ob der Server ein Bundle ohne `<reporting>`-Tokens akzeptiert, ist unknown.

---

## 15. Kompletter Flow

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

## 16. Unknowns

| Punkt | Status |
|-------|--------|
| Serverseitige Akzeptanzregeln, Retention, Größenlimits, Pflicht für Reporting-Tokens | serverseitig, nicht beobachtet |
| Default-Werte von 18405, 18406, 19034, 25910, 30333 | vom Server geliefert, Defaults nicht aufgelöst |
| Exakte Untergrenze von `timestamp_too_old` und Einheit von 25910 / 30333 | nicht aufgelöst |
| Polarität von `A1W.A02` pro Entry-Point; Verwendung von Gate `A03` und Flag 26039 | verworrenes Dekompilat / nicht verfolgt |
| Bedeutung der Spalte `group_history_toggle_mode` und des Kinds `<group_history/>` | Namen gefunden, Semantik nur inferred |
| Liste der teilbaren Nachrichtentypen (`BUv()`-Registry) | nicht aufgezählt |
| Companion-Darstellung eines Bundles; Consumer von `support_group_history` auf dem Primärgerät | nicht verfolgt |
| Nativer Teil der Reporting-Token-Key-Ableitung | nativ, nicht gelesen |
| Traffic | nichts mitgeschnitten; alle Flows aus Code |
