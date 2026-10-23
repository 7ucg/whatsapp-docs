<!-- src-sha1: e4fe5d62fca781d0449295a5d549413929d95191 -->
# WhatsApp Broadcast Lists — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** klassische Broadcast-Listen und Status-Broadcasts auf Android: `@broadcast`-JID-Modell (list / status / location), Listenerstellung, Mitgliedschaftslimits und Empfängerregeln, `w:b`-IQs (Listen abrufen, Liste löschen, Quota), App-State `business_broadcast_list`, LID-Migration, lokale Speicherung, Clone-on-insert pro Empfänger, Send-Stanza (Sender-Key-Fan-out, `phash`, `bucketing`, `<cap>`, ephemere Einstellungen pro Empfänger), Ack- und Receipt-Aggregation, monatliche Broadcast-Quota, Spam-Warnungs-Bans, GAP, `status@broadcast`-Posting (`SendE2eStatusJob`, Parts, manuelle Buckets), Status-Datenschutzmodi, Close Friends und Custom Audiences, Status-Reply / Reaction / Mention / Notify, Status-Tabellen, Feature-Flags, Baileys-Vergleich

---

## 1. Was es ist (technisch)

Es existieren drei serverseitige `broadcast`-JIDs. Alle sind "Multi-Participant"-JIDs (`AbstractC20660pZ`, gleiche Basis wie Gruppen) und teilen sich eine Send-Pipeline: Der Sender verschlüsselt einmal mit einem Sender Key und übergibt den Key paarweise an jedes Empfängergerät. Alle Aussagen beruhen auf statischer Analyse der dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tier: **found** = im Code gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst. Nichts hier ist **tested**. Obfuskierte Namen wurden in 2.26.41.6 anhand stabiler Strings neu aufgelöst (`BroadcastListManager/…`, `BroadcastXmppMethods/…`, `StatusParticipantUserManager/…`, `SendE2eStatusJob/…`, Tabellen- und Pref-Namen).

| Entität | JID-Form | `Jid.getType()` | Klasse | Rolle |
|---------|----------|-----------------|--------|-------|
| Klassische Broadcast-Liste | `<id>@broadcast` | 3 | `C99P` | Liste des Primärgeräts, Empfänger erhalten 1:1-Kopien |
| Status-Broadcast | `status@broadcast` | 5 | `C199018dF` | Status-Posts, Zielgruppe pro Post gewählt |
| Location-Broadcast | `location@broadcast` | 6 | `BOC` | existiert im JID-Modell; Nutzung nicht verfolgt (Live-Standort aus dem Namen inferred) |
| Eigener Status-Pseudo-User | `status_me` (lokal) | 11 | `C0Dh` | rein lokaler Alias, keine Wire-JID (Rolle inferred) |

Außerhalb des Umfangs: Newsletter (`SendNewsletterStatusJob` ist ein separater Job), Business-Kampagnen und Insights, Android-OS-Broadcasts.

| Komponente | Name in 2.26.41.6 | Rolle |
|-----------|----------------|-------|
| JID-Parser / Helfer | `C0DJ.A00` / `C0DZ.A0P`, `A0Q`, `A0h` | `broadcast`-Server: User `location` → `BOC`, `status` → `C199018dF`, sonst `C99P`; Helfer liefern true für jeden Broadcast (3, 5, 6) / Liste (3) / Status (5) |
| Listen-Allocator / -Manager | `C0YJ.A0E` / `A0K` (`BroadcastListManager`) | neue Listen-ID / Teilnehmer hinzufügen und entfernen |
| LID-Filter und Migration | `C70552yj` (`BroadcastListLidMigrationHelper`), `C0UV` (Migrations-Task) | PN → LID |
| Participant Manager / Store | `C22300su` (`A0j` add, `A0k` remove), `C14850fN` (`ParticipantUserStore`) | mit Gruppen geteilt |
| Listen-IQs | `C18240lQ` (`BroadcastXmppMethods`), `AKU` (Result-Handler), `BroadcastListQuotaProtocol` + `C9EN` | Listen abrufen, Liste löschen, Quota |
| Quota-Client | `C720733k` (Repository), `C2EX` (ViewModel), `C74823Ej` (Message-Listener) | monatliches Limit |
| App-State-Mutation | `C224469lG` (Dispatch), `C26057BNq` (`BusinessBroadcastListMutation`) | `business_broadcast_list` |
| Clone-on-insert | `C231399zG` (`BroadcastCloneOnInsertProcessor`), `AJO` | lokale Kopien pro Empfänger |
| Ack / Receipts | `C22500tF`, `C22790ti` (`MainMessageStore`), `C269411e` (`MessageStatusStore`) | Server-Ack, Receipt-Aufteilung |
| Encryptor / Jobs | `F6P` (`E2eMessageEncryptor`), `SendE2EMessageJob`, `SendE2eStatusJob` | Sender Key, SKDM, Stanza-Aufbau |
| Eingehender Verifier | `C34757F6a` (`CompanionSupportVerifier`) | verwirft Listenkopien auf Companions |
| Status-Zielgruppe | `C11550Zh` (`StatusInfoStore`), `C182877r0` (Distribution-Info), `C23140uH` (`StatusParticipantUserManager`), `C1889082i` (`StatusCustomListStore`), `C23340ub` (Bucketing-Config) | Datenschutzmodi, Listen, Buckets |
| Status-Privacy-Sync | `C48386LBh` (`StatusPrivacySyncMutation`), `C49626LsR` (Wire `StatusPrivacyAction`), `M7H` (Mode-Enum) | App-State-Action 44 |

---

## 2. JID-Modell

### 2.1 Parsing (found)

| Regel | Wert |
|-------|------|
| Server | `broadcast` |
| User `status` / `location` | Singletons `C199018dF` / `BOC` |
| Jeder andere User | `C99P`: Länge 1..20, erstes Zeichen `1`..`9`, übrige Zeichen `0`..`9`, sonst wird `C09B` geworfen |

Die Regel "keine führende Null" ist aus dem `C99P`-Konstruktor gelesen (Smali vergleicht gegen `0x31`/`0x39`, Rest `0x30`..`0x39`). Eine Liste ist nicht `g.us`, nutzt aber die Gruppen-Participant-Maschinerie wieder (3.5).

### 2.2 Allokation (found, `C0YJ.A0E`)

Die ID ist `System.currentTimeMillis() / 1000` gefolgt von `@broadcast`, um eine Sekunde erhöht, solange lokal eine Liste mit dieser ID existiert. Die Eindeutigkeit wird nur gegen die lokale Chatliste geprüft; vor der Allokation erfolgt kein Server-Call (es gibt kein Create-IQ, 3.3). Ob der Server eine beliebige ID akzeptiert, ist statisch nicht feststellbar.

---

## 3. Lebenszyklus einer Liste

### 3.1 Erstellung (found, teilweise inferred)

```
[Picker]  "New broadcast" (menu item hidden when BRD() = companion mode), max 256 selected
     ▼
createBroadcastList callback (C222519hZ):
     │   C0YJ.A0E()                                allocate <seconds>@broadcast
     │   A0K.A04(jid, users): C70552yj.A00 → LID filter ; C22300su.A0h → local participants ; contact entry (name "")
     ▼
compose flow opens; system message "You created broadcast list "X" with N recipients"
```

`A0K.A04` sendet weder ein IQ noch eine App-State-Mutation (found). Das erste serverseitig sichtbare Ereignis ist das erste Senden an die Listen-JID (4.2); dass der Server den Listenzustand daraus ableitet, ist inferred. Dieselbe Allokation wird für Newsletter-Follower-Einladungen wiederverwendet (`userActionSendNewsletterFollowerInviteMessages`, found).

### 3.2 Mitgliedschaftslimits und Empfängerregeln

| Regel | Wert | Tier |
|-------|------|------|
| Max. Empfänger | 256: `ContactPickerFragmentKt.A39` lehnt `selected.size() > 256` ab (`Broadcast to a maximum of %d people at a time`); Picker-Grenze `min(256, groupLimit - 1)` | found |
| Empfängerquelle | Contact Picker; Berechtigungstext `To create a broadcast … allow WhatsApp access to your contacts`; blockierte Kontakte: `To add to broadcast list, unblock %s` | found |
| Empfänger muss den Sender gespeichert haben | nur UI-Text (`Only contacts who have you in their address book will receive your broadcast messages.`); Durchsetzung serverseitig | found (Text), unknown (Durchsetzung) |
| LID-Adressierung | `A0K.A01` liefert immer `lid`; PN-Teilnehmer ohne LID-Mapping werden verworfen (`lid-broadcast-filtered-participants`) | found |
| Fehlendes Mapping beim Senden | `missing_pn_lid_mapping_for_broadcast`: Clone übersprungen, Encryptor wirft `E39(device, 4)` | found |
| Leere Teilnehmermenge | `saveGroupParticipants/broadcast_would_be_cleared`; mit Flag **30111** (Default true) bleiben gespeicherte Teilnehmer erhalten | found |

### 3.3 Server-IQs (found)

Nur drei IQs betreffen Listen. Es gibt kein Create- oder Edit-IQ.

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

Alle drei verwenden ein Timeout von 32 s. `AKU` (Get-Result) legt für jede `<list>` ohne lokalen Chat- oder Kontakteintrag den Chat (`A0K.A00`, Systemnachricht Typ 9) und einen Kontakteintrag an und speichert die Maps `pn_jid` und `username`. Delete wird von `C18240lQ.A01` gesendet und von einem App-State-REMOVE gefolgt (3.4).

Restore-Trigger (found): `RegistrationInitializer/shouldrefreshlists` setzt die Pref `refresh_broadcast_lists=true` und sendet nach der Registrierung Get-Lists (zusammen mit Get-Privacy-Settings); `MessageHandlerCallback/ready` wiederholt dies, solange die Pref true ist; `AKU` löscht sie. Der Server persistiert Listen daher pro Account (found durch Implikation). Wie er eine Liste erfährt, ist clientseitig nicht sichtbar (unknown, siehe 3.1).

### 3.4 App-State-Mutation (found)

| Element | Wert |
|---------|------|
| Action | `BusinessBroadcastListAction`, Wire-Name `business_broadcast_list` (`EnumC24865AnN.A0H`, Ordinal 62), `SyncActionValue`-Feld **69**, Collection `regular`, API-Version 7 |
| Index | `["business_broadcast_list", "<list jid>"]` |
| Operation | SET bei Add, Remove, Rename; REMOVE mit `deleted=true`, leeren Participants, Name `""` beim Löschen einer Liste (`A0T`, `syncBusinessBroadcastListRemoval`) |
| Gate | `C12440bB.A0b()` (syncd nicht blockiert oder Companion-dirty); Business-Hooks (`storeForBroadcast`, `onAudienceChanged`, `getCustomAudienceFbidForBroadcast`) fehlen in dieser APK |
| Aufrufer | `A0K.A03` / `A05` (add / remove), Rename in `BroadcastListChatInfoActivity`, `C24085AaS` (Participant-Set) |
| Apply-Seite | kein Handler referenziert `EnumC24865AnN.A0H`; es existieren nur der Writer (`C26057BNq`) und der Feld-Accessor in `BD4`, daher ist das Apply-Verhalten beim Consumer unknown |

| Feld | Nummer | Typ | Wert / Verwendung |
|------|--------|-----|-------------------|
| `deleted` | **1** | bool | Liste entfernt |
| `participants` | **2** | repeated `BroadcastListParticipant` | Zielgruppe (`lid_jid` **1** erforderlich, `pn_jid` **2**) |
| `list_name` | **3** | string | Betreff |
| `label_ids` | **4** | repeated string | Label-Zielgruppe (Alternative zu Participants, nie beides) |
| `audience_expression` | **5** | string | dynamische Zielgruppe (Business) |
| `custom_audience_fbid` | **6** | string | nur Business |

Gleiche Collection: `BusinessBroadcastCampaignAction` (81), `BusinessBroadcastInsightsAction` (82), `MarketingMessageBroadcastAction` (39); nur im Enum vorhanden `BusinessBroadcastAssociationAction` (59) und `BusinessBroadcastAction` (94). Grundlagen: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md).

### 3.5 LID-Migration, Speicherung, Companions

`BroadcastListLidMigrationTask` (`C0UV`) konvertiert jede Liste von PN- zu LID-Teilnehmern: ein Usync für fehlende LIDs (Fehler wird als `usync_failed` geloggt, der Task läuft weiter), dann entfernt `C70552yj.A03` die PN-Teilnehmer und fügt das LID-Set in einer Transaktion hinzu.

| Store | Inhalt | Tier |
|-------|--------|------|
| `chat` / `chat_view`, `jid.type = 3`, `subject`, `created_timestamp`, `hidden` | der Listen-Chat (`C222989iV`) | found |
| `group_participant_user` (`group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `label`, `add_timestamp`), `group_participant_device` | Empfänger, mit Gruppen geteilt | found |
| `wa_group_admin_settings` (`jid`, `addressing_mode`, `group_state`) | Adressierungsmodus pro Liste (Telemetrie zählt `@broadcast`-Zeilen) | found |
| `message`-Spalten `broadcast`, `recipient_count`, `participant_hash`, `key_id`, `chat_row_id`, `from_me` | Listennachricht und Ack-Daten | found |
| `message_broadcast_ephemeral` (`message_row_id`, `shared_secret`) | Secret pro Nachricht für selbstlöschende Nachrichten in Listen | found |

Companions (found): Die Menüeinträge `New broadcast` / `Broadcast lists` werden nur hinzugefügt, wenn `BRD()` false ist; `C34757F6a` wirft `E3A(415, "received peer broadcast message on companion-mode, dropping", 18)` für eine Listenkopie des eigenen Accounts, die `<participants>` trägt; Action 69 hat keinen Apply-Handler.

---

## 4. Senden an eine Liste

### 4.1 Lokaler Fan-out (found, `C231399zG`)

```java
// A02(msg): msg.fromMe, not one of two excluded message classes, status 0 or 2 (or 4 with flag 26867)
msg.A0Z = true;                                   // message.broadcast = 1
for (recipient : msg.A0A())                       // recipient list stored on the FMessage
    normalized = lidMapper.A0C(recipient);        // null → missing_pn_lid_mapping_for_broadcast, skip
    store.add(cloneFactory.A00(msg, new C1ZA(normalized, msg.key.id, true)));   // own row in the recipient's 1:1 chat
```

| Eigenschaft | Wert |
|-------------|------|
| Message-ID | identisch für die Listennachricht und jeden Clone (`key_id` kopiert, nur der Chat unterscheidet sich) |
| Zähler | `recipient_count` (`FMessage.A06`) in der Listenzeile; Referenzzähler der Mediendatei um die Clone-Anzahl erhöht |
| Duplikate | `SQLiteConstraintException` bei vorhandenem Clone-Key wird geloggt und übersprungen |
| Selbstlöschende Nachrichten | Clone übernimmt die Einstellung pro Empfänger aus der Ephemeral-Map (Schlüssel: Primärgerät des Empfängers); Ablaufzeilen in `message_ephemeral` |

### 4.2 Wire-Format (found, teilweise inferred)

Eine Stanza, adressiert an die Listen-JID (Beispiel, Attributwerte illustrativ). Die Verschlüsselung nutzt den Gruppenpfad wieder (`F6P` ist auf `AbstractC20660pZ` typisiert): ein Sender-Key-Ciphertext plus Sender-Key-Distribution-Messages pro Gerät. Grundlagen zu Sender Key und Session werden hier nicht wiederholt.

```xml
<message to="1760000000@broadcast" type="text" id="3EB0…" t="…" phash="2:AbCdEf==" addressing_mode="lid">
  <participants>
    <to jid="<recipient device jid>"><enc v="2" type="pkmsg|msg" …/></to>   <!-- SKDM wrapped pairwise -->
  </participants>
  <enc v="2" type="skmsg" …/>                                                <!-- message under the sender key -->
  <cap client_capping_ready="true|false"/>                                   <!-- flag 16656 only -->
</message>
```

| Attribut | Quelle | Hinweise |
|----------|--------|----------|
| `to`, `type`, `id`, `t` | Chat-JID (`C33150EcP.A07`), `AbstractC30999De0.A02`, `C1ZA.A01`, `originalTimestamp` | `to` ist die Listen-JID (aus dem gemeinsamen Builder inferred); `t` nur wenn ungleich null |
| `phash` | `groupParticipantHash` | 4.3 |
| `bucketing` | `eva.A05` | `primcomp`, wenn Flag **28183** und Teilnehmerzahl ≥ **28185** (512); Listen (≤ 256) bleiben in der Praxis ungesetzt (inferred) |
| `addressing_mode` | `lid` | bei JIDs vom Typ 28 weggelassen |
| `participant`, `recipient`, `recipient_pn`, `peer_recipient_pn`, `peer_recipient_username` | Job-Felder | Peer- / Retry- / DSM-Sends |
| `edit`, `expiration`, `device_fanout="false"`, `privacy_sensitive="1"` | Job-Felder | optional |

Die Children stammen von Contributors (`InterfaceC35538FaZ.ASY`, `processStanzaNodeParamsUsingNewFramework`). `F69` fügt für Listen-Chats `<cap client_capping_ready="…"/>` hinzu, wenn Flag **16656** an ist; der Wert ist Flag **13537**.

| Schritt | Detail | Tier |
|---------|--------|------|
| Empfängergeräte | Participant-Manager-Set abzüglich Gerätetypen 26 / 27 (`F6P.A07`, gehostete Geräte inferred); für Listen-Chats fügt `AxolotlMultiDeviceSessionRequirement` die eigenen Companion-Geräte (`BPE`: eigener User, nicht primär) zur SKDM-Zielmenge hinzu | found / inferred |
| Sender-Key-Name | (eigene Geräteadresse, `groupId`-String `A0J`); `A0J` wird in `SenderKeyDistributionMessage.groupId` geschrieben; Status `-1002` von `encryptForGroup` = ungültiger Sender Key, rotiert | found |
| Ephemeral-Blobs pro Empfänger | `F6P.A0A` (`buildBroadcastListEphemeralSettings`): baut für jedes Empfängergerät, das in der paarweisen Map fehlt (eigene Companions übersprungen), `EphemeralSetting(expiration or afterReadDuration, timestamp)` und verschlüsselt es nativ mit dem `shared_secret` der Nachricht (`JniBridge.jvidispatchOOOOOOO`); fehlende Einstellung wirft `E39(device, 4)`. Zweck (Timer pro Empfänger innerhalb einer Stanza) inferred | found / inferred |
| Eigene Geräte | Nachricht in `DeviceSentMessage` verpackt mit `destinationJid = list` und `phash` der Empfängergeräte (`C33284Eea.A01`) | found |
| Größe | `BoundedStanzaSizeException` → `stanza-too-large` / `large payload` | found |

### 4.3 `phash` (found, `AbstractC44221r5`)

`<version>:` + Base64 (`NO_WRAP`, Padding beibehalten) der ersten 6 Bytes von SHA-256 über die sortierten Empfängergeräte. Version `2:` hasht `user.0:device@server`-Strings (Flag **16731** false, Default); Version `3:` hasht die rohen Geräte-Strings (Flag **16731** true). Verwendet für Gruppen-, Listen- und Status-Stanzas.

### 4.4 Ack und Receipts (found)

| Ereignis | Behandlung |
|----------|------------|
| Server-Ack | `C22500tF` → `C22790ti.A04`: aktualisiert für Listen-Chats (nicht Status) `message` mit `chat_row_id IN (list chat, every clone chat) AND from_me = 1 AND key_id = ?` und setzt `status`, `receipt_server_timestamp`, `recipient_count`; fällt auf einen Scan über `timestamp/from_me/key_id` zurück (`UPDATE_RCV_BROADCAST_SERVER_SQL`, Log `message-table-scan`), wenn die Empfängerliste kürzer als `recipient_count` ist |
| Empfänger-Receipt | `MessageStatusStore.splitStatusUpdateReceipts`: ein Receipt für den Listen-Key wird auf den Clone `(normalized recipient, same id, fromMe)` abgebildet und auf den Clone (`broadcast-individual`) sowie die Multi-Nachricht angewendet; Status-Downgrades werden verworfen (`broadcast-statusdowngrade`); ein unbekannter Clone loggt `nosuchmessage for broadcast` |

Die Regel für den Summenstatus der Listenzeile und was das Telefon eines Empfängers anzeigt, sind ungelöst (unknown).

---

## 5. Limits und Missbrauchskontrollen

### 5.1 Monatliche Broadcast-Quota (found, Consumer-Pfad)

```
iq get xmlns=w:b smax_id=143
  → <limits is_heavy_sender="true|false" messages_left="N" total_limit="M"/>
    <timeframe start_ts_s="…" reset_ts_s="…" end_ts_s="…"/>
```

Client-Bereichsprüfungen: `messages_left` 0..300, `total_limit` 1..300, Timestamps 2020-01-01..2100-01-01. Fehler-IQ-Codes werden auf Client-Ergebnisse abgebildet: `400` → 3, `401` → 4, `403` → 5, `500` → 1, sonst → 0, keine Verbindung oder Zustellfehler → 2 (`consumer_broadcast_capping_iq_error_response`).

| Mechanismus | Detail |
|-------------|--------|
| Cache | Prefs `broadcast_quota_messages_left`, `_message_limit`, `_last_timestamp_fetched_ms`, `_heavy_sender`, `_start_timestamp`, `_end_timestamp`, `_reset_timestamp` |
| Refresh | wenn die Zeit seit dem letzten Fetch Flag **13818** Minuten überschreitet (Default 1440) oder now ≥ `reset_ts_s` (Kombination im Decompilat verstümmelt, OR inferred) |
| Decrement / Increment | `C74823Ej`: pro hinzugefügter Listennachricht, die als `broadcast` markiert ist und nicht in einem Set ausgenommener Nachrichtentypen liegt (`C2EX.A00`), pro Nachricht, nicht pro Empfänger; beim Löschen ungesendeter Listennachrichten wieder erhöht, begrenzt auf `total_limit` |
| Pre-Send-Block | Prädikat in `C20M`: Listen-Chat und Flags **16585** und **13537** und `messages_left == 0` → Senden verweigert, Bottom Sheet `You've reached the broadcast limit for this month` |
| UI / Telemetrie | `Send up to %d broadcasts per month`, Onboarding-Sheet für Heavy Sender (`CappingBroadcastManager`); `wam_broadcast_list` (`blLimit`, `currentBlSends`, `numBlLists`, `broadcastListSize`) |

Der Limit-Wert kommt vom Server; im Client existiert nur die Bereichsprüfung. Business-seitige Hooks (`isSmbPremiumBroadcastCappingEnabled`) sind in dieser APK Stubs.

### 5.2 Spam-Warnungs-Bans (found)

`SpamWarningActivity` nimmt einen Server-Code (`spam_warning_reason_key`), `expiry_in_seconds`, optionalen Server-Text und FAQ-URL entgegen. Codes: **101** Nachrichten an Personen, die den Sender nicht im Adressbuch haben, **102** zu viele Blockierungen, **103** Gruppen mit Personen, die den Sender nicht gespeichert haben, **104** gleiche Nachricht an zu viele Personen, **106** zu viele Nachrichten an eine Broadcast-Liste; andere zeigen den generischen Ban wegen Nutzungsbedingungen. Zustellpfad und übrige Ban-Oberfläche: [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md). Schwellenwerte sind serverseitig (unknown).

### 5.3 Config 20278 und GAP

- Config **20278** existiert nur als Default-String `{"max_messages": 10000, "farthest_time_days": 30}` in zwei Default-Tabellen. Im Consumer-Code gibt es keine weitere Referenz auf `max_messages` / `farthest_time_days`, also wurde kein Reader gefunden. Es ist nicht das Consumer-Listenlimit (5.1); die Verwendung ist unknown (Business-seitiger Default).
- GAP (`com.whatsapp.gapenforcement`, Flag **14837**, Default false) arbeitet empfangsseitig: `GapEnforcementTrigger.onMarketingMessageReceived` und `RulesManager` werten Inbox-Regeln für Marketing-Message-Threads aus (`parseMaxMmThreadsInTopInboxSize`, `parseNoConsecutiveInTopInboxSize`, `parseMinNUpdatedP`) und loggen Genauigkeitsergebnisse; es läuft nicht auf Companions und begrenzt keine Sends aus Listen. Die Auflösung des Akronyms steht nicht in der APK (unknown).

---

## 6. status@broadcast

### 6.1 Send-Pipeline (found)

`SendE2eStatusJob` hat einen Typ (`EnumC32060Dzj`): `STATUS` 0 (der Post, Tabelle `status`), `STATUS_ADD_ON` 1 (Reactions und andere Add-ons, `status_add_on`), `STATUS_NOTIFY` 2 (Reply- / Reshare- / Mention-Benachrichtigungen, `status_notify`). Die Stanza nutzt den Attribut-Builder aus 4.2 plus `<meta>`-Contributors (Beispiel, Attributwerte illustrativ):

```xml
<message to="status@broadcast" type="media" id="3EB0…" phash="2:…" bucketing="manual" addressing_mode="lid">
  <participants><to jid="<device>"><enc v="2" type="pkmsg|msg"/></to>…</participants>
  <enc v="2" type="skmsg" bucket="f1"/>                      <!-- one per bucket when bucketed -->
  <meta status_setting="contacts" session_scope="status"/>
</message>
```

| Attribut | Akzeptierte Werte (Stanza-Wertemengen, `C9E2`) |
|----------|-----------------------------------------------|
| `status_setting` | `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist` |
| `content_type` | `add_on`, `status_notify` |
| `message_association_type` | `av1_video_dual_upload`, `hd_image_dual_upload`, `hd_video_dual_upload`, `hevc_video_dual_upload` |
| `interaction_type` | `question`, `question_reshare` (mit `parent_server_id`, `response_server_id`) |
| `bucketing` | `manual`, `primcomp`, `threebuckets` (`threebuckets` nur in der Wertemenge) |

| Element | Detail |
|---------|--------|
| Ack-Timeout | 300000 ms (`no ack within 300000ms`) |
| Parts | große Zielgruppen werden aufgeteilt: `status_send_part` (`status_row_id`, `part_code`, `is_first_part`, `device_count`, `state`, `sent_timestamp`, `ack_timestamp`, `error_code`, `stanza_devices_hash`); Geräte-Tracking in `status_receipt_device` (`uuid`, `receipt_device_jid`, `receipt_device_timestamp`, `primary_device_version`, `part_code`) |
| Gruppenstatus | `buildGroupStatus called with non-PermanentGroupJid`; `is_group_status`; Message-Felder 92 / 96 / 103 |
| Build-Fehler | `StatusStanzaBuildFailureReason`: `MISSING_RETRY_CIPHERTEXT`, `TARGETS_UNRESOLVABLE`, `PART_ATTEMPT_PERSISTENCE_FAILED`, `CANONICAL_ACK_PENDING`, `EMPTY_FANOUT`, `NON_CURRENT_BATCH`, `MISSING_SENDER_KEY_CIPHERTEXT`, `UNKNOWN` |
| Job-Fehler | `encryption_limit`, `out_of_memory`, `payload_too_large`, `stanza_error`, `stanza_too_large` (behandelt, wenn Flag **29113** an ist), `unrecoverable_error` |

### 6.2 Zielgruppe: Datenschutzmodi (found)

Die Zielgruppe wird auf dem Sender aufgelöst und zu expliziten Empfängergeräten expandiert; das Attribut `status_setting` kennzeichnet nur den Modus. Lokaler Zustand: `C11550Zh` (Prefs `status_distribution`, `status_distribution_modes`, `status_white_list`, `status_black_list`).

| Lokaler Modus | Name | `status_setting` | Wire `M7H` (App-State) |
|---------------|------|------------------|------------------------|
| 0 | My contacts | `contacts` | `CONTACTS` 2 |
| 1 | Only share with | `allowlist` | `ALLOW_LIST` 0 |
| 2 | My contacts except | `denylist` | `DENY_LIST` 1 |
| 3 | Unset-Fallback von `C182877r0.A01()`; von der Sync-Mutation abgelehnt (`StatusPrivacySyncMutation invalid status setting`) | | |
| 4 | Custom Audience / Close Friends | `customlist` / `closefriends` (inferred) | `CUSTOM_LIST` 4 (`CLOSE_FRIENDS` 3 existiert im Enum, wird nicht erzeugt) |

Mapping lokal zu Wire (found, `C48386LBh.A04`): 1 → 0, 2 → 1, 4 → 4, sonst 2. Die Modusnamen für 0..2 werden vom Send-Job auch als `contacts` / `allowlist` / `denylist` geloggt.

Server-Privacy-Listen nutzen das `privacy`-IQ, Kategorie `status` (Kategoriename aus `AboutStatusPrivacyActivity`):

```xml
<iq to="s.whatsapp.net" xmlns="privacy" type="get" id="…">
  <privacy addressing_mode="lid"><list name="status" value="contact_allowlist|contact_blacklist" dhash="…"/></privacy>
</iq>
<iq xmlns="privacy" type="set"><privacy><category name="status" value="contacts|contact_blacklist|contact_allowlist"/></privacy></iq>
```

(`AbstractC230749y7.A02`, `C228009tS`, `C18260lS.A0P`; Get läuft je nach Flag **23463** über MEX / SMAX / Shadow, Set über MEX bei **23639**, sonst SMAX.)

### 6.3 Custom Audiences und Close Friends (found)

UI-Strings: `New: Close friends`, `People you include see a purple ring on your status`, `Create audience`, `Choose name & emoji`.

| Element | Wert |
|---------|------|
| Tabelle `status_privacy_custom_list` | `row_id` (PK), `list_id` (unique), `name`, `emoji`, `is_selected` (Default 0), `member_jids`, `source_group_jids`, `allow_list_selected`; sowohl im Message-Store als auch im Status-Store geführt (`*_MSGSTORE_DB`, `*_STATUS_DB`) |
| App-State | `status_privacy` (Ordinal 38, `regular_high`, Feld **44**); `StatusPrivacyAction`: `mode` **1**, `user_jid` **2**, `shareToFB` **3**, `shareToIG` **4**, `custom_lists` **5**, `modes` **6**; `StatusCustomList`: `list_id` **1**, `name` **2**, `emoji` **3**, `is_selected` **4**, `user_jid` **5** |
| Datensatz pro Post | `status_message_info`: `status_distribution_mode`, `selected_audience_list`, `audience_type`, `status_audience_custom_list_name`, `_emoji` |
| Validierung | `StatusParticipantUserManager/validateAudience` (enthält eine `HAS_STATUS_AUDIENCE`-Prüfung über `wa_contacts`), `StatusEmptyAudienceGuard` in den Composern |

Verwandt: `userStatusMute` (Ordinal 23, Feld 29, `muted`). Mehrere gleichzeitige Modi benötigen Flag **28731**, der Custom-List-Store **27031** (beide Default false; die Status-Config-Helfer `A0F` / `A0I` steuern dies ebenfalls, ungelöst).

### 6.4 Manuelle Sender-Key-Buckets (found)

| Element | Detail |
|---------|--------|
| Tabelle `manual_user_group_bucket` | `row_id`, `user_jid_row_id`, `multi_participant_jid_row_id`, `status_audience`, `bucket`; Unique-Index auf User + Gruppe |
| Zielgruppennamen / Bucket-Präfixe | `contacts` → `c`, `close_friends` → `f`, `allow_list` → `a`, `close_friends:<id>` → abgeleitetes Präfix; andere Namen werfen `Unknown manual SKB audience name` |
| Store / Planung | `ManualBucketStore/assignUsersToBuckets`, `deleteRowsForBuckets`, `getHoldersByBucketForGroup`; `ManualBucketingUtils/planSend`, `trimToEncBudget`; `SenderKeyBucketingRollback/cleanupBucketedState` |
| Flags | **28184** + Rollout-Cap **34545** (0 = alle) aktivieren manuelles Bucketing für Status (`C23340ub.A01`) |

### 6.5 Reply, Reaction, Mention, Notify (found)

| Interaktion | Mechanismus |
|-------------|-------------|
| Reply | normale 1:1-Nachricht, die den Status zitiert (`status_reply`: `status_row_id`, `ref_id`, `reply_timestamp`); `Message.statusQuotedMessage` (Feld **109**) für Question-Replies |
| Reaction / Add-on | Job-Typ `STATUS_ADD_ON`; `status_add_on` (`status_row_id`, `type`, `uuid`, `sender_user_jid`, `state`, `sender_timestamp`, `is_revoked`, `content_proto`, `secret`); Gates pro Post `cannot_receive_reactions`, `can_receive_multi_reactions` |
| Mention | `status_message_info.is_mentioned`, `status_mentions`, `status_mention_source`; `Message.statusMentionMessage` (Feld **87**) ist ein Single-Field-Wrapper (`message` **1**), der wie `viewOnceMessage` entpackt wird (`C35228FOg`); weitere Semantik inferred |
| Notify | `Message.statusNotificationMessage` (Feld **98**): `responseMessageKey` **1**, `originalMessageKey` **2**, `type` **3** (1 add yours, 2 reshare, 3 question-answer reshare, 4 group status reply); gespeichert in `status_notify` |
| Verwandte Felder | `groupStatusMentionMessage` **92**, `groupStatusMessage` **96**, `groupStatusMessageV2` **103**, `statusQuestionAnswerMessage` **105**, `statusStickerInteractionMessage` **110** |

### 6.6 Status-Speicherung (found)

| Tabelle | Schlüsselspalten |
|---------|------------------|
| `status` (Status-Store) | `uuid`, `sender_user_jid`, `status_info_row_id`, `type`, `timestamp`, `server_receipt_timestamp`, `state`, `secret`, `content_proto`, `origin`, `flags`, `audience_type`, `stanza_xml`, `batch_state` |
| `status` (Message-Store, Legacy-Zusammenfassung), `status_info` | `jid_row_id` / `chat_jid`, `unseen_count` / `unread_count`, `total_count`, `unread_count_close_friends` |
| `status_message_info` | `message_row_id`, `status_distribution_mode` (3 wenn nicht gesetzt), Gates für Mention / Reaction / Reshare, `is_group_status`, `ranking_version`, Zielgruppenspalten (6.3) |
| `status_send_part`, `status_receipt_device`, `manual_user_group_bucket` | Sendezustand (6.1, 6.4) |

Die beiden Tabellen namens `status` haben disjunkte Spalten und liegen in verschiedenen Datenbanken (aus den Labels `MSGSTORE_DB` / `STATUS_DB` inferred). Weitere Tabellen (`status_media_link`, `status_seen_receipt`, `status_ranking*`, `status_interactions*`) sind nur namentlich aufgeführt.

---

## 7. Feature-Flags

IDs wie an den Aufrufstellen gelesen; Defaults aus den kompilierten Default-Tabellen.

| ID | Default | Steuert |
|----|---------|---------|
| **13537** | false | Consumer-Broadcast-Capping: Listen-Home, Quota-Fetch / -Decrement, Wert von `client_capping_ready` |
| **16585** | true | Listen-Sends blockieren, wenn `messages_left == 0` |
| **16656** | false | fügt `<cap client_capping_ready/>` zu Listen-Stanzas hinzu |
| **13818** | 1440 | Quota-Refresh-Intervall (Minuten) |
| **15515** | true | Capping-UI-Helfer (`C33z.A08`, mit 13537) |
| **19790** | false | wenn true, überspringt Clone-on-insert das Mapping zitierter Nachrichten |
| **26867** | true | Clone-on-insert-Zweig für gesendete Nachrichten mit Status 4 (Bedeutung ungelöst) |
| **30111** | true | gespeicherte Listen-Teilnehmer behalten, wenn ein Save sie leeren würde |
| **16731** | false | `phash`-Variante `3:` statt `2:` |
| **28183** / **28184** | false / false | `primcomp`-Bucketing Master / manuelles Status-Bucketing |
| **28185** / **28199** / **34545** | 512 / 2 / 0 | Bucketing-Teilnehmerschwelle / zweiter Int (ungelöst) / Rollout-Cap |
| **28731** / **27031** | false / false | mehrere Status-Modi / Custom-List-Store |
| **29113** | false | Stanza-too-large-Behandlung für Status |
| **23463** / **23639** / **23874** | 0 / false / false | Privacy-Get-Protokoll (1 MEX, 2 Shadow, sonst SMAX) / Privacy-Set über MEX / Pfad für Privacy-Listen-Fetch |
| **14837** | false | GAP-Enforcement |
| **20278** (string) | `{"max_messages": 10000, "farthest_time_days": 30}` | Business-Broadcast-Limit-Default, kein Consumer-Reader |

---

## 8. Baileys (`baron-baileys-v2`, gegen den Quellcode geprüft)

| Bereich | Implementierung | Urteil gegenüber 2.26.41.6 |
|---------|-----------------|----------------------------|
| Status-Send | `messages-send.js`: `isStatus`, `statusJidList` an die Teilnehmerliste angehängt, `<meta status_setting session_scope="status">` | entspricht 6.1 / 6.2; `statusPrivacy` wird nicht validiert (gültig: `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist`) |
| Zielgruppen-Skalierung | explizite `statusJidList`, keine Buckets, kein `bucketing`-Attribut | große Zielgruppen laufen in Stanza-Limits (6.1) |
| Liste löschen | `deleteBroadcastList`: `w:b` set, `<delete><list id/></delete>` | entspricht 3.3 |
| Quota | `fetchBroadcastListQuota`: `xmlns="w:biz"` mit Child `<broadcast_list_quota/>` | Request stimmt nicht überein (`w:b`, `smax_id=143`, kein Child); Response-Parsing stimmt überein |
| Listen abrufen / App-State / Listen-Send | nicht implementiert / `businessBroadcastListAction` als `settings.update` ausgegeben / `isJidBroadcast` nur fürs Dekodieren | siehe unten |

| Symptom | Ursache | Fix |
|---------|---------|-----|
| Senden an klassische Liste verworfen oder abgelehnt | Listen sind Zustand des Primärgeräts: Companions blenden das Feature aus, verwerfen Listenkopien des eigenen Accounts mit `participants` (415), es gibt kein Create-IQ | keine Listen-JIDs von einem Companion ansprechen; 1:1-Nachrichten pro Empfänger senden oder `status@broadcast` mit `statusJidList` nutzen |
| Empfänger nicht auflösbar | keine Mitgliederabfrage für Listen auf Companions; Teilnehmer sind LID-adressiert und nach Mapping gefiltert | LIDs zuerst per Usync auflösen |
| Quota-Request-Fehler | falscher Namespace | `xmlns="w:b"`, `smax_id` 143, `type="get"`, `to="s.whatsapp.net"` |

Separate 1:1-Sends sind transportkompatibel, aber keine klassische Liste (kein Listen-Chat, keine gemeinsame ID, keine Quota).

---

## 9. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `missing_pn_lid_mapping_for_broadcast`, `lid-broadcast-filtered-participants` | PN des Empfängers hat kein LID-Mapping | LIDs (Usync) vor dem Hinzufügen oder Senden holen |
| 415 `received peer broadcast message on companion-mode` | Listenkopie mit `participants` auf einem Companion | erwartet, Companions verarbeiten keine Listen-Sends |
| Senden blockiert, Limit-Sheet | `messages_left == 0` mit 13537 und 16585 | auf `reset_ts_s` warten, ungesendete Listennachrichten löschen |
| Ban-Code 106 | zu viele Nachrichten an eine Broadcast-Liste | auf `expiry_in_seconds` warten |
| `broadcast_would_be_cleared` | Teilnehmer-Save mit leerer Menge | Flag 30111 behält Teilnehmer |
| `EMPTY_FANOUT` | Zielgruppe wurde zu null Geräten aufgelöst | Zielgruppe korrigieren, `StatusEmptyAudienceGuard` sollte früher blocken |
| `stanza_too_large`, `payload_too_large` | zu viele Geräte oder zu großer Payload | Parts / Buckets (6.1, 6.4), Flag 29113 |

---

## 10. Wichtige Unterscheidungen

| Nicht verwechseln | Unterschied |
|-------------------|-------------|
| Liste (Typ 3) vs `status@broadcast` (Typ 5) | Liste: gespeicherte Empfänger, Clones pro Empfänger, monatliche Quota; Status: Zielgruppe pro Post, keine Clones, eigene Tabellen |
| Liste vs Gruppe | gleicher Participant-Store und Sender-Key-Pfad; Liste ist nur auf dem Primärgerät, Empfänger sind keine Mitglieder und sehen 1:1-Chats |
| Server-`w:b`-Listen vs App-State-Action 69 | `w:b` stellt Listen nach der Registrierung wieder her; Action 69 wird für den Sync geschrieben und hat keinen Consumer-Apply-Handler |
| Quota (`w:b` smax 143, ≤ 300) vs Config 20278 (10,000 / 30 Tage) | Quota kommt vom Server und wird in der UI durchgesetzt; 20278 hat keinen Consumer-Reader |
| Quota vs Ban-Code 106 vs GAP | weiches Limit mit UI / vom Server verhängter temporärer Ban / empfangsseitige Inbox-Regeln |
| `privacy`-IQ vs Custom Audiences | das IQ hält drei Server-Modi; Custom Lists und Close Friends sind lokal plus App-State-Action 44 |

---

## 11. Kompletter Ablauf

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

## 12. Unbekanntes

| Element | Status |
|---------|--------|
| Wie der Server eine Liste registriert (es existieren nur Get- / Delete- / Quota-IQs) | Registrierung beim Senden inferred |
| Serverregel, dass Empfänger den Sender gespeichert haben müssen; Listengröße und Quota-Werte | serverseitig (nur UI-Text und Bereichsprüfungen) |
| Apply-Verhalten von App-State-Action 69 beim Consumer | kein Handler gefunden |
| Was Empfänger für eine Listennachricht erhalten; Summen-Receipt-Regel der Listenzeile | vom Sender aus nicht sichtbar |
| Quota-Refresh-Kombination, Set ausgenommener Nachrichtentypen | Decompilat verstümmelt / nicht verfolgt |
| Lokaler Status-Modus 3, `threebuckets`, Flags 28199, 26867, 15515, Status-Config `A0F` / `A0I` | ungelöst |
| Nutzung von `location@broadcast`; Auflösung von "GAP" | nicht verfolgt / nicht in der APK |
| Traffic | nichts mitgeschnitten |
