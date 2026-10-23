<!-- src-sha1: 8e15828bcc50ba6f6a9c5388872afeef15451af0 -->
# WhatsApp USync — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** USync IQ (`xmlns="usync"`): Modi, Kontexte und Sync-Typen, Aufbau von Request- und Response-Stanza, Query-Protokolle (contact, sidelist, status, text_status, picture, business, devices, disappearing_mode, lid, username), Kontakt-Lookup und Telefonnummern-Discovery, Device-List-Sync, Key-Index- und ADV-Prüfungen, LID-Mapping, Privacy-Token-Anreicherung, MEX `UsyncQuery` und Routing pro Protokoll, Rate Limits und Backoff, Client-Trigger, Feature-Flags, Vergleich mit Baileys

---

## 1. Was es ist (technisch)

USync ist die Bulk-Abfrage "wer ist dieser Nutzer". Ein IQ enthält eine Liste von Nutzern und eine Liste von Protokollen (Datentypen); der Server antwortet pro Nutzer und pro Protokoll. Dieselbe Stanza-Form bedient vier Aufgaben: Upload und Download des Adressbuchs, einzelne Telefonnummern-Lookups, Aktualisierung von Profildaten (Status, Bild, Business, Disappearing Mode) und Aktualisierung der Device-Liste für das Message-Fan-out. Alle Aussagen stammen aus statischer Analyse des dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = im Code gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst. Obfuskierte Namen gelten pro Build und wurden in 2.26.41.6 neu aufgelöst.

| Schicht | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| Stanza-Builder / Parser | `C18670m9` (Log-Tag `UniSyncProtocolHelper`): `A06` Build, `A07` Senden, `CFS` Ergebnis, `Brt` IQ-Fehler, `Bog` Zustellfehler | baut `<iq xmlns="usync">`, parst das `<usync>`-Ergebnis |
| Request-Modell | `A05` (Typ + Nutzer + Optionen), `A0A` (Builder pro Nutzer), `C222649hm` (Request pro Nutzer), `C222589hg` (ausstehender Request, einer pro IQ-ID) | was gefragt wird |
| Sync-Typ | `EnumC21760rz` (30 Werte), `EnumC21770s0` Kontext, `EnumC21780s1` Modus, `EnumC21790s3` Scope | Quelle der Attribute `mode` / `context` |
| Einzel-Lookups | `C23638AId` (`ContactQuerySync`) | Telefonnummer, JID, Username, LID zu Username |
| Batch-Sync | `C18580m0` (`ContactSyncHelper`), anonymer Callback `X.0m7` | Multi-Protokoll-Sync, Wahl MEX vs. klassisch, Backoff-Prefs |
| Öffentliche Einstiegspunkte | `C18230lP` (`ContactSyncMethods`), Builder `C21810s5`, Request `C21830s7`, Protokollmenge `C21820s6`, Reason `EnumC21800s4` (77 Werte) | alle Features rufen diese auf |
| Result-Applier | `N27` (`contactsyncresultupdater`), `C51909N4g` (`ContactSyncDevicesUpdater`) | schreibt DB, LID-Map, Devices |
| Device / ADV | `C23310uY` (`DeviceSyncManager`), `SyncDevicesJob`, `C24230w2` (`DeviceADVInfoHandler`) | Device-Refresh-Jobs, Key-Index-Verifikation |
| Privacy-Anreicherung | `C223659jg` (`ProfilePrivacyEnrichmentFetcher`), `C197138a8`, `C197148a9` | tctoken und gemeinsame Gruppe pro Nutzer |
| MEX-Variante | `C229259vZ` (`MexUsyncQueryHelper`), `M4I` (Route), `M5H` (Protokoll-Bit) | `UsyncQuery` und Routing |
| Backoff-Store | `C18800mM`, Prefs-Datei `contact_sync_prefs` | `*_sync_backoff`, `*_full_sync_wait` |

Entscheidende Punkte:

- Der Android-Builder erzeugt zehn Query-Children: `contact`, `sidelist`, `status`, `text_status`, `picture`, `business`, `devices`, `disappearing_mode`, `lid`, `username`. Er hat **kein** `bot`-Child und kein Feature-Child (found, alle String-Konstanten von `A06`). `reachability`, `linked_profiles`, `orgs` und `ddm` existieren nur in der MEX-Variante (Abschnitt 8).
- Android kennt vier Modi und zehn Kontexte (Abschnitt 2); jeder Request trägt in den gelesenen Einstiegspunkten `sid`, `index="0"`, `last="true"`.
- Nutzer stehen in `<list>` (normal) oder `<side_list>` (Kontakte außerhalb des Adressbuchs).
- Profil-Requests tragen einen Privacy-Nachweis pro Nutzer (gespeicherter tctoken oder eine gemeinsame Gruppen-JID), siehe Abschnitt 7 und WA_TCTOKEN_CSTOKEN.md.
- Username-Lookups sind in WA_USERNAME.md abgedeckt; dieser Report hält nur die gemeinsamen Stanza-Teile fest.

---

## 2. Stanza-Hülle

### 2.1 Request (found, `C18670m9.A06`)

```xml
<iq xmlns="usync" id="0AB1" type="get">                       <!-- `to` added by the sender, inferred -->
  <usync sid="sync_sid_query_<uuid>" index="0" last="true"
         mode="query" context="interactive" [allow_mutation="true"]>
    <query>                                                   <!-- protocol children, section 3 -->
      <contact [addressing_mode="lid"]/> <devices version="2"/> <picture type="preview" size="N"/> ...
    </query>
    <list>      <user jid="..." [common_gid="..."]> per-user children </user> ... </list>
    <side_list> <user jid="LID" pn_jid="PN"> ... </user> ... </side_list>
  </usync>
</iq>
```

| Teil | Regel (Code) |
|------|--------------|
| iq `id` | `C10140Tq.A0G()`: `"0"` + Hex eines Zählers, Überlauf bei 65536 (loggt "iqId too large") |
| `sid` | `AbstractC43461pq.A00(prefix)` = Präfix + `_` + zufällige UUID; Präfixe `sync_sid_query`, `ContactSyncHelper/sync_sid_<scope>`, `..._mex_profile` |
| `index` / `last` | aus dem Aufruf: `A07` übergibt immer `0` und `true` |
| `mode`, `context` | `EnumC21780s1.modeString`, `EnumC21770s0.contextString` des Sync-Typs |
| `allow_mutation="true"` | gesetzt, wenn `A05.A04` true ist: wird für Full-/Delta-Typen gebaut, wenn `C11980aQ.A0G()` gilt (Bedeutung nicht verfolgt) |
| contact-Child | vorhanden, wenn irgendein Request contact anfragt (`A05.A03`) oder wenn kein anderes Protokoll angefragt wird |
| Kontext REGISTRATION | wird über `C10140Tq.A0A(...)` statt `A06(...)` gesendet (found); Unterschied nicht verfolgt |
| Sendeoptionen | IQ-Timeout-Argument 32000 ms (`ContactQuerySync`) oder 128000 ms (`ContactSyncHelper`); numerischer Wert `102` an den Sender übergeben (Bedeutung unknown) |

### 2.2 Modi (found, `EnumC21780s1`)

| `mode` | Bedeutung |
|--------|-----------|
| `full` | vollständiger Resync des Scopes |
| `delta` | nur Änderungen seit dem letzten Sync |
| `query` | Lookup der gelisteten Nutzer, keine Zustandsänderung |
| `download` | serverseitige Kontaktmenge abrufen |

### 2.3 Kontexte (found, `EnumC21770s0`)

`metadata`, `registration`, `interactive`, `background`, `notification`, `message`, `add`, `voip`, `snapshot`, `wamo`.

### 2.4 Sync-Typen (found, `EnumC21760rz`)

Name, Wire-Code, Kontext / Modus / Scope. Codes 10-15 und 17-20 sind unbenutzt. Scope `PB` = Phonebook, `SL` = Side List, `MP` = Multi-Protokoll-Query. Der Code wird geloggt und in Metriken geführt; die Stanza trägt nur Kontext und Modus.

| Namen (Code) | Kontext / Modus | Scope |
|--------------|-----------------|-------|
| `REGISTRATION_FULL` (0) | registration / full | PB+SL |
| `INTERACTIVE_FULL` (1), `INTERACTIVE_DELTA` (2) | interactive / full, delta | PB+SL |
| `BACKGROUND_FULL` (3), `BACKGROUND_DELTA` (4) | background / full, delta | PB+SL |
| `NOTIFICATION_CONTACT` (5) | notification / delta | PB |
| `INTERACTIVE_QUERY` (6), `ADD_QUERY` (9) | interactive / query, add / query | PB |
| `NOTIFICATION_SIDELIST` (7) | notification / query | SL |
| `INTERACTIVE_DELTA_SIDELIST` (8) | interactive / delta | SL |
| `BACKGROUND_QUERY_PICTURES` (16), `BACKGROUND_MULTI_PROTOCOL_QUERY` (21), `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` (22) | background / query | MP |
| `REGISTRATION_COMPANION_MULTI_PROTOCOL_QUERY` (23) | registration / query | MP |
| `INTERACTIVE_MULTI_PROTOCOL_QUERY` (24), `MESSAGE_MULTI_PROTOCOL_QUERY` (25), `VOIP_MULTI_PROTOCOL_QUERY` (26) | interactive, message, voip / query | MP |
| `NOTIFICATION_MULTI_PROTOCOL_QUERY` (27), `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY` (28) | notification / query | MP |
| `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` (29), `WAMO_MULTI_PROTOCOL_QUERY` (38) | message, wamo / query | MP |
| `CONTACT_DONWLOAD` (30, sic) | background / download | PB |
| `CONTACT_FORCE_UPLOAD` (31) | metadata / delta | PB+SL |
| `CONTACT_UPLOAD` (32), `NATIVE_CONTACT_DELTA` (39) | background / delta | PB |
| `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` (33) | background / full | PB |
| `CONTACT_UPLOAD_SNAPSHOT` (34), `CONTACT_DOWNLOAD_SNAPSHOT` (35), `CONTACT_FULL_SYNC_SNAPSHOT` (36) | snapshot / delta, download, full | PB, PB, PB+SL |
| `CONTACT_RESTORE_FULL_SYNC` (37) | background / full | WA-Adressbuch |

Helfer: `A00()` = delta, `A01()` = full, `A02()` = full und registration. Nur `BACKGROUND_QUERY_PICTURES` setzt den Picture-Query-Typ auf `image`; jeder andere Typ fragt `preview` an.

---

## 3. Query-Protokolle

### 3.1 Überblick (found)

| Protokoll | `<query>`-Child | Request-Child pro Nutzer | Response-Child (pro Nutzer) | Hinweise |
|-----------|-----------------|--------------------------|-----------------------------|----------|
| contact | `<contact/>` | `<contact>+digits</contact>`, `<contact username=.. lid=.. pin=../>`, `<contact type="delete"/>`, leeres `<contact/>` | `<contact type="in\|out\|invalid">text</contact>` | nur in `<list>` |
| sidelist | `<sidelist [addressing_mode="lid"]/>` | `<sidelist type="delete"/>` | `<sidelist type=..>` in `<side_list>` | Nutzer außerhalb des Adressbuchs |
| status | `<status/>` | `<status t="secs"/>`, wenn eine gecachte Zeit existiert | `<status t code type>text</status>` | About-Text |
| text_status | `<text_status/>` | keins | `<text_status last_update_time ephemeral_duration_sec text><emoji content/></text_status>` | Flag **5839** |
| picture | `<picture type="image\|preview" [size="N"]/>` | `<picture id="N"/>` gecachte ID | `<picture id direct_path hash/>` | Privacy-angereichert |
| business | `<business><verified_name/><profile v="N"/></business>` | `<business><verified_name serial/><profile tag/></business>` | `<business pn_jid><verified_name verified_level host_storage actual_actors privacy_mode_ts>cert</verified_name>...</business>` | `v` = AB **471** & 0x3FFC (Default 1140) |
| devices | `<devices version="2"/>` | `<devices device_hash ts expected_ts/>` | `<devices><device-list><device id key-index is_hosted/></device-list><key-index-list ts expected_ts>bytes</key-index-list></devices>` | Abschnitt 5 |
| disappearing_mode | `<disappearing_mode/>` | keins | `<disappearing_mode duration t ephemerality_disabled/>` | `ephemerality_disabled` wird nur mit Flag **21235** gelesen |
| lid | `<lid/>` | `<lid jid="LID"/>`, wenn der PN-Nutzer eine bekannte LID hat | `<lid val="LID"/>` | Abschnitt 6 |
| username | `<username/>` | `<username username="@known"/>` | `<username>text</username>` oder `contact@username` | siehe WA_USERNAME.md |

Attribute pro `<user>`: `jid` (PN oder LID), `pn_jid` (Side-List-Einträge), `common_gid` (Abschnitt 7). Ein Nutzer kann außerdem ein `<tctoken>`-Child mit den gespeicherten Token-Bytes enthalten. In Responses hat `<user>` zusätzlich `pn_jid` und `new_jid`; der Parser nimmt `jid` und fällt auf `pn_jid` zurück, wenn `jid` fehlt.

### 3.2 Contact (found)

| Form | Bedingung | Hinweise |
|------|-----------|----------|
| `<contact>+15550001111</contact>` | Telefon-Lookup | der Nummern-String wird so durchgereicht, wie der Aufrufer ihn liefert; bei JID-basierten Lookups setzt `C23638AId.A05` ein `+` davor, wenn die JID eine Telefonnummern-JID ist und (`C11980aQ.A0M()` / AB **26739** an ist oder der Typ `ADD_QUERY` ist) |
| `<contact>15550001111</contact>` | PN-Nutzer mit LID-Addressing (`C11980aQ.A0L()`, AB **14565**) | Ziffern ohne `+` |
| `<contact username="u" [lid=".."] [pin=".."]/>` | Username-Lookup | `lid` / `pin` nur mit AB **12402**, sonst nur `username` |
| `<contact type="delete"/>` | Request als gelöscht markiert | Entfernung aus dem Adressbuch im Upload-Sync |
| `<contact/>` | LID-Nutzer ohne Username | Platzhalter |
| Query `<contact addressing_mode="lid"/>` | AB **14565** | LID-adressierter Contact-Sync |
| Query `metadata_version="3"` | Delta-Typ und ein internes Flag | das Flag wird im gelesenen Pfad nur aus einer konstanten false zugewiesen, wird also vermutlich nie gesendet (inferred) |

Response-`type`: `in` = registriert (interner Code 1), `out` = nicht registriert (2), `invalid` = Nummer nicht gültig (3); jeder andere Wert wirft einen Corrupt-Stream-Fehler. Der Textinhalt jedes `<contact>` wird an eine Liste pro Nutzer angehängt.

Ergebnisebene `<result><contact version refresh integrity snapshot_recovery>`: `version` wird im Ergebnis behalten, `refresh` (Sekunden) speist die Full-Sync-Wartezeit (Abschnitt 9), `integrity` ist `pass` (Default), `pending` oder `timelock` (intern 1 / 2 / 3), `snapshot_recovery` (`pending` / `pass`) wird nur mit Flag **22410** gelesen.

### 3.3 Status und Text-Status (found)

Verarbeitung des `<status>`-Ergebnisses: `type="fail"` mit `code` 401 / 403 / 404 = durch Privacy versteckt (interner Zustand 2); anderes `fail` = Fehler (0); nicht-leerer Text ohne Fehler = gesetzt (1, `t` * 1000 = Setzzeit); leer ohne Fehler und mit ausgeschaltetem Text-Status-Flag = keiner (3). Die Zustandsnamen sind inferred.

Bei eingeschaltetem Flag **5839** überschreibt ein `<text_status>`-Child den Zustand 1 / 3: Text = `text`, Emoji = `<emoji content>` (Default "", wenn nicht vorhanden), Setzzeit = `last_update_time` in Sekunden, Ablauf = Setzzeit + `ephemeral_duration_sec`, wenn dieser Wert über 0 liegt (Zustand 3). Ein versteckter Status (Zustand 2) ist ein Failure-Node mit 401 / 403 / 404, kein leerer String.

### 3.4 Picture, Business, Disappearing Mode (found)

| Protokoll | Request-Detail | Response-Parsing |
|-----------|----------------|------------------|
| picture | `type="preview"` plus `size` nur, wenn AB `AbstractC36291cD.A06` über 0 liegt (gedeckelt bei 300); `id` pro Nutzer nur, wenn eine gecachte ID existiert | `id` (int, -1 ohne `<picture>`), `direct_path`, `hash` |
| business | `profile v` = `C35756Fe7.A00()` = AB 471 & 16380; `serial` / `tag` pro Nutzer nur aus der lokalen Business-Zeile | `pn_jid` (füllt die PN eines LID-Nutzers und speichert das LID-PN-Paar), `verified_name`: `verified_level`, `host_storage`, `actual_actors`, `privacy_mode_ts`, Node-Bytes = Zertifikat |

---

## 4. Kontakt-Lookup und Telefonnummern-Discovery

### 4.1 Einzel-Lookups (found, `C23638AId`)

| Methode | Typ | Baut | Ergebnis |
|---------|-----|------|----------|
| `A0E(userJid, type, n)` | nur `INTERACTIVE_QUERY` oder `ADD_QUERY` | User-JID + contact, status, picture, business, disappearing_mode, lid, username; devices bei **5751**; text_status bei **5839** | `C43621q7` |
| `A0C` / `A0A(type, n, number)` | dieselben zwei Typen | Telefonnummer als `<contact>`; gleiche Menge (status nur, wenn der Aufrufer true übergibt) | `Pair(result, user)` |
| `A0B(type, n, number)` ("Lightweight") | beliebig | Telefon + contact, lid; devices bei **5751** | `Pair` |
| `A0D(type, numbers)` | beliebig | viele Nummern: contact, status, picture, business, disappearing_mode, lid; text_status bei **5839** | Array von Nutzern |
| `A0F(lid)` | `INTERACTIVE_QUERY` | `<user jid=LID/>` + `<contact/><username/>` | Username einer LID |
| `A0G(username, key)` | `INTERACTIVE_QUERY` | Username (+ Key) als `<contact>`; außerdem status, picture, business, disappearing_mode, lid, username nur, wenn **33609** false ist, text_status bei **5839** | WA_USERNAME.md |

Guards (found): Netzwerkprüfung (Ergebnis `network_unavailable`), In-Flight-Dedupe-Maps nach JID oder Nummer (zweiter Aufruf liefert "skip too frequent query", kein Zeitfenster), `sid` pro Aufruf, Wartezeit bis 32000 ms, danach Timeout-Ergebnis. Bei ausgeschaltetem AB **14565** wird eine LID-JID mit bekannter Telefonnummer vor dem Bau des Requests auf diese Nummer umgeschrieben (`AbstractC197018Zw.A0Y`; Richtung inferred aus dem folgenden `+`-Präfix-Schritt).

### 4.2 Ergebniscodes (`C43621q7`, Namen aus der Verwendung inferred)

0 `A04` Netzwerk nicht verfügbar; 1 `A08` übersprungen (nichts zu senden oder zu häufig); 2 `A07` Erfolg mit Änderungen (Kontakt-Entfernungspfad); 3 `A06` Erfolg; 4 `A03` Fehler (leeres Ergebnis, Timeout, Error); 5 `A05` Rate Limit (Ergebnisfehler 429); 6 `A02` Exception. `A01()` ist true für 1, 2, 3. Eine leere `<list>` mit Contact-Protokollfehler 429 ergibt 5, jede andere leere Liste ergibt 4.

### 4.3 Welche Features das Phonebook erreichen (found)

| Pfad | Einstieg | Typ | Protokolle (`C21820s6`) |
|------|----------|-----|-------------------------|
| Background-Full-Sync (nur Primary) | `C18230lP.A0F(reason)` | `BACKGROUND_FULL` | alles außer orgs |
| Erzwungener Full-Sync | `A01`-Helfer, periodischer Job `RunnableC23953AUi` case 23 | `BACKGROUND_FULL`; Companion: `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` | contact (`A0J`) oder Side List (`A0K`); Companion: alles außer contact / Side List (`A0D`) |
| Force Upload, Delta Upload, Download | `A07(reason)`, `A0G(reason)`, `A0C()` | `CONTACT_FORCE_UPLOAD`, `CONTACT_UPLOAD`, `CONTACT_DONWLOAD` | contact + lid (`A0G`) |
| Native Kontakte geändert | `A0J(reason, jids)` | `NATIVE_CONTACT_DELTA` | alles außer orgs |
| Verzögerter Sync nach Registrierung | `A0L` (Pref `registration_contact_sync_delayed`) | `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` | contact + lid |
| Side Contact bei erster Anzeige | `A0E(contact)` | Primary: `INTERACTIVE_DELTA_SIDELIST`; Companion: `INTERACTIVE_MULTI_PROTOCOL_QUERY` | alles außer orgs / alles außer contact, Side List, orgs |

Protokollmengen (`C21820s6`-Konstanten, found): `A0S` username; `A0G` contact + lid; `A0P` status; `A0Q` Text-Status; `A0O` picture; `A0F` business; `A0H` devices; `A0E` business + devices; `A0N` payment; `A0I` Disappearing Mode; `A0L` lid; `A0M` orgs; `A0D` alles außer contact, Side List, orgs; `A0R` wie `A0D` ohne lid; `A0J` contact + `A0D`-Menge; `A0K` Side List + `A0D`-Menge; `A0C` alles außer orgs. LID ist impliziert, wenn contact oder Side List synchronisiert wird.

`C21830s7` (SyncRequest) persistiert Optionen als JSON: `sync_is_urgent`, `sync_only_if_changed`, `sync_only_if_registered`, `sync_clear_whatsapp_sync_data`, `sync_should_retry` und ein `sync_<protocol>`-Boolean pro Protokoll (found); Builder-Default Retry-Int 5 (Bedeutung inferred).

### 4.4 Notification-getriebene Lookups (found)

Der Server pusht einen Hash statt einer Nummer; der Client löst ihn auf und führt eine Query aus.

| Notification-Handler | Payload | Sync | Protokolle |
|----------------------|---------|------|------------|
| `AnonymousClass145` (Contact-Update), `add` | bis zu 2 Hash-Children vom Typ `pn` (Default) oder `lid`; nur Primary | `NOTIFICATION_CONTACT` | alles außer orgs |
| dasselbe, update | Base64-Hash | `NOTIFICATION_SIDELIST` | status, picture, lid, username, text_status |
| `C1S0` Status-Notification | Attribut `hash` (Base64) | `NOTIFICATION_SIDELIST` (Reason `NOTIFICATION_STATUS`) | nur status |
| `C1S0` Picture-Notification | Attribut `hash` | `NOTIFICATION_SIDELIST` (Reason `NOTIFICATION_PICTURE`) | nur picture |
| `AnonymousClass142` Business-Notification (JID-lose Entfernung mit `hash`) | Base64-Hash | `NOTIFICATION_SIDELIST` (Reason `NOTIFICATION_BUSINESS`) | Business-Menge (Konstante nicht aufgelöst) |

Der Hash wird mit lokalen Nutzern über `digest(user + "WA_ADD_NOTIF")` abgeglichen, präfixweise bytewise verglichen (`AbstractC43461pq.A04`); der Digest-Algorithmus wird vom Aufrufer gewählt (nicht verfolgt). Ein servergetriggerter "Forced Sync" (`RunnableC23951AUg`, Reason `SERVER_FORACE_SYNC`) führt `BACKGROUND_FULL` oder den Companion-Typ aus.

### 4.5 Contact-Sync über MEX-Mutations (found, nicht USync)

Neu im Build: Der Kotlin-Contact-Sync (`com.whatsapp.contact.sync.kmp`, `.handler`) nutzt `w:mex`-Mutations statt des usync-IQ. Config `whatsapp-android-mex`, doc_ids aus dem Persist-ID-Asset.

| Operation | doc_id | Variablen (found) | Response |
|-----------|--------|-------------------|----------|
| `ContactsDeltaSyncMutation` | `28247314474869813` | `context` (`SEARCH`, `OSAB_IMPORT`, `EMAIL_IMPORT`, `QR_SCAN`), `primary_contacts_add[]`, `primary_contacts_remove[]` (`lid`, `modifier` = `BEST_EFFORT_DOWNGRADE_TO_WA_SIDE_CONTACT`, `normalized_phone`), `side_contacts_add[]` | `xwa2_contacts_delta_sync`: `results[]` {`client_cached_lid`, `failed`, `detail` (Union: raw_pn / primary_normalized_phone / lid / phone_status; side_status; username_status; email_status; normalized_phone)}, `retry_after_seconds` |
| `PrimaryContactsFullSyncMutation` | `36963099086669113` | nicht gelesen | nicht gelesen |
| `SideContactsFullSyncMutation` | `26880700761604398` | `context`, `cursor`, `side_contacts[]` (`client_cached_lid`, `normalized_phone`) paginiert | `results[]` wie oben, `retry_after_seconds` |

Was diesen Pfad gegenüber dem usync-Pfad steuert, wurde nicht gefunden (unknown). `retry_after_seconds` ist das MEX-Äquivalent des usync-`backoff`.

---

## 5. Device-List-Sync, Key-Index, ADV

### 5.1 Request und Response (found)

Request: Query-Child `<devices version="2"/>`; pro Nutzer `<devices device_hash="H" ts="T" expected_ts="E"/>`, nur gesendet, wenn ein Hash existiert (`ts`, `expected_ts` nur, wenn über 0 und `expected_ts` über `ts`). Die Werte stammen aus der lokalen Device-Zeile (`C15070fj.A07/A00/A04`).

Response pro Nutzer: `<devices>` enthält entweder ein `<error code text>` (Nutzer erhält Zustand -1, Log "parseUser/partial error") oder:

| Node | Attribute | Geparst zu |
|------|-----------|------------|
| `<device-list><device .../>` | `id` (int), `key-index`, `is_hosted` | `DeviceJid(user, id)` -> Key-Index; ein Widerspruch zwischen Hosted-Zustand der JID und `is_hosted` meldet `invalid-hosted-flag` |
| `<key-index-list ts expected_ts>` | `ts` (Sekunden), `expected_ts` (Default 0), Content-Bytes | signierte Key-Index-Liste, roh gespeichert |

Das Ergebnis-`<devices>` kann ein `<error>` mit Backoff tragen (Abschnitt 9). MEX-Route: `include_devices` plus `devices{hash, timestamp, expected_timestamp}`; Client-Log-Labels für verworfene Ergebnisse: `devices_dropped_status_error`, `devices_status_indeterminate`, `devices_hash_match_noop`, `devices_dropped_empty_without_hash`, `devices_dropped_no_jid`, `devices_dropped_stale_timestamp`, `devices_dropped_adv_proto_missing`, `devices_dropped_adv_verify_failed`, `devices_dropped_adv_data_update_failed`, `devices_outcome_unset`.

### 5.2 Update-Prüfungen (found, `C51909N4g`, `C24230w2`)

| Prüfung | Verhalten |
|---------|-----------|
| Key-Index-Liste leer | "update keyIndex is empty", kein Update |
| Response-`ts` älter als gespeichert | "timestamp is less than existing one", verworfen |
| Retry bei veraltetem expected-ts | Response-ts unter dem gespeicherten, `expected_ts` gleich dem gespeicherten ts und gespeicherter Wert älter als Pref `adv_last_device_job_ts`: loggt einen usync-Fetch-Fehler und sendet das WAM-Event `wam_adv_expected_ts_unavailable` (`C49716Ltt`), gibt true zurück (Wirkung beim Aufrufer nicht verfolgt) |
| neue Device-Info | `C51909N4g.A00` löscht das gespeicherte expected-ts, wenn das neue ts mindestens dem gespeicherten entspricht; Account-Typ aus der Device-Menge abgeleitet (`C9U.A01`) |

### 5.3 ADV-Verifikation des signierten Key-Index (found, `C24230w2.A07`, `A04`)

| Schritt | Detail |
|---------|--------|
| Parse | Key-Index-Bytes -> `ADVSignedKeyIndexList` (`C25786BAu`): `details` (**1**), `account_signature` (**2**), `account_signature_key` (**3**, optional) |
| Public Key | Identität des Primary Device aus dem lokalen Identity-Store; trägt der Proto `account_signature_key` und weicht er vom lokalen Key ab, wird dieser Key verwendet und mit `adv` getaggt; ohne beide Keys: Warnung "no primary identity" |
| Signatur | `account_signature` über `{0x06, 0x02} || details` mit dem gewählten Key verifizieren (`AbstractC30195DBc.A08`); Fehlschlag loggt "fail to verify account signature" und sendet ein WAM-Event (`C55912St`, 1 = lokaler Key, 2 = adv-Key) |
| Details | `details` -> `ADVKeyIndexList` (`BCB`): `raw_id` (**1**), `timestamp` (**2**), `current_index` (**3**), `valid_indexes` (**4**), `account_type` (**5**) |
| Timestamp-Abgleich | `details.timestamp` muss dem Attribut `ts` entsprechen, sonst "advTimestampMismatch" + WAM-Event `C2TD`, Ergebnis abgelehnt |
| Alter | ist `ts` älter als `min(35, AB 730)` Tage (Default 35) und hat `valid_indexes` mehr als 1 Eintrag: "advListTimestampInvalid", abgelehnt |
| Raw-ID | `raw_id` weicht von der gespeicherten ab: "incoming key-index not matching local state, resetting"; eigener Account auf einem Companion loggt `device_self_invalid_index_list`; andere Nutzer: `C15070fj.A0G(user, "adv_key_index_list_validation_failed")`, wenn keine neue Liste geparst wurde (Wirkung nicht verfolgt) |
| Filterung | `filterDeviceWithKeyIndexList` (`C24230w2.A08`) behält ein Device, wenn es das Primary ist oder sein `key-index` über 0 liegt und in `valid_indexes` gelistet ist; andernfalls wird es mit einem WAM-Event verworfen (`C55932Sv`, 1 wenn der Index 0 ist). Ein größerer gespeicherter Index erzeugt nur eine Warnung |

### 5.4 Device-Sync-Jobs (found)

`DeviceSyncManager.A03(jids, type)` reiht `SyncDevicesJob` ein (überspringt Nutzer, die bereits in Flight sind; ausstehende Nutzer überleben Neustarts in der Pref `pending_users_to_sync_device`). `syncType` wählt den Sync-Typ:

| `syncType` | Sync-Typ | Kontext | Aufgerufen von (found) |
|------------|----------|---------|------------------------|
| 0 / Default | `INTERACTIVE_MULTI_PROTOCOL_QUERY` | interactive | — |
| 1 | `MESSAGE_MULTI_PROTOCOL_QUERY` | message | `SyncDevicesAndSendInvisibleMessageJob` (Gruppen-Sendepfad `C22300su`, Gruppengröße zwischen AB 934 und AB 1946, ein Job pro Message-Key) |
| 2 | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | notification | Account-Sync der eigenen Devices (`C41431mS`) |
| 3 | `BACKGROUND_MULTI_PROTOCOL_QUERY` | background | eingehende Nachricht oder Status mit fehlgeschlagener ADV-Sender-Prüfung (`DecryptMessageRunnable` / `StatusProcessingRunnable`, Log `invalid adv sender`), ADV-Metadaten-Abweichungen (`C24230w2`), Replay ausstehender Nutzer |
| 4 | `VOIP_MULTI_PROTOCOL_QUERY` | voip | Aufbau der Call-Verschlüsselung für ein Nicht-Primary-Device (`C1A`, Log `voip/encryption/schedule usync`) |
| 5, 6 | `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY`, `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` | notification, message | nicht verfolgt |

Reine Device-Requests nutzen `C21820s6.A0H`. `handleADVMetadata` (`C24230w2.A0A`) löst außerdem einen Typ-3-Refresh aus, wenn die ADV-Metadaten einer eingehenden Nachricht einen Hosted-Account-Typ melden, der dem lokalen Zustand widerspricht (Devices vorher geleert), oder einen neueren Timestamp als gespeichert.

---

## 6. LID-Mapping

| Mechanismus | Detail (found) |
|-------------|----------------|
| `lid`-Protokoll | Query `<lid/>`; pro Nutzer `<lid jid=known LID/>` nur, wenn ein PN-Nutzer bereits eine gespeicherte LID hat; Response `<lid val="LID"/>` wird im Nutzerergebnis gespeichert |
| Mapping-Write | `N27.A03(users)`: LID = `new_jid` (wenn eine JID vom Typ LID) sonst das `lid`-Ergebnis sonst die Nutzer-`jid`, falls sie eine LID ist; PN = `pn_jid` sonst Nutzer-`jid`, falls sie eine PN ist; Paare gehen in einem Batch in den LID-PN-Mapping-Store |
| Business-`pn_jid` | ein LID-Nutzer ohne PN erhält die PN aus `<business pn_jid>`; das Paar wird gespeichert |
| Side List | Request-Nutzer tragen `jid` = LID und `pn_jid` = PN, wenn LID-Addressing an ist (`C11940aM.A05`, aufgelöst über `C11500Zc.A00`, Flag-ID nicht verfolgt); Fallbacks loggen `Sidelist: No LID provided`, `waContact_null`, `usernameLid_null` |
| Reparatur fehlender LIDs | `MissingLidHandler` (`C32M`): `requestSyncDevicesAndLidIfMissingLids` wartet 32000 ms auf eine `MESSAGE_MULTI_PROTOCOL_QUERY` mit dem lid-Protokoll, bevor ein externer Einstiegspunkt fortfährt |
| Mapping-Observer | `ContactJidMapObserver` (`C0ZA`): erscheint ein LID-PN-Paar und existiert ein veralteter Kontakt, wird der Ersatzkontakt hinzugefügt und ein `BACKGROUND_DELTA` mit Reason `LID_REQUEST` eingereiht |

Warum eine fehlende LID wichtig ist: Ein reiner PN-Kontakt ist beim LID-first-Senden nicht adressierbar; die Query füllt das Paar ohne Full-Sync (inferred aus den Aufrufstellen).

---

## 7. Privacy-Anreicherung (tctoken, gemeinsame Gruppe)

`ProfilePrivacyEnrichmentFetcher` (`C223659jg.A00`, Log-Label `ContactSyncHelper.privacyEnrichment`) läuft vor dem Senden über die Request-Liste. Für jeden Nutzer holt er (a) den gespeicherten Privacy-Token mit seinem Timestamp (`C14820fK.A0M`, verworfen, wenn älter als `C14820fK.A04.A02()`), (b) wenn kein gültiger Token existiert, eine mit dem Nutzer geteilte Gruppen-JID (`C197178aC.A04` / Bulk-Suche, braucht die eigene LID). Ergebnis `C197148a9{ token C9oI, commonGroup, flag }`.

| Ausgabe | Klassisches usync | MEX `UsyncQuery` |
|---------|-------------------|------------------|
| token | `<tctoken>token bytes</tctoken>` als Child von `<user>` | `privacy_token{tctoken, timestamp}` |
| gemeinsame Gruppe | Attribut `common_gid="..."` an `<user>` | `common_group` |

Gilt nur für Requests, die picture oder status anfragen (AB **9667**, Default true), Text-Status (**20798**, Default false), devices (**29769**), contact (**29770**), lid (**29771**) (Flags Default false, außer 9667). Ohne Token oder gemeinsame Gruppe kann der Server weiterhin antworten, lässt aber möglicherweise picture oder status weg (inferred; Serverregel unknown). Token-Ausgabe und `cstoken` stehen in WA_TCTOKEN_CSTOKEN.md.

Verwandt: `PRIVACY_TOKEN_REFRESH` (`C735439k`) löst `BACKGROUND_QUERY_PICTURES` mit der Nur-picture-Menge `A0O` in Batches von 10 Nutzern aus (found); dass der Zweck die Auffrischung der Token-Zuordnung ist, ist inferred aus dem Reason-Namen.

---

## 8. MEX `UsyncQuery` und Protokoll-Routing

### 8.1 Operation (found, `C229259vZ.A01`)

`w:mex`-Operation `UsyncQuery`, doc_id `38635300486116501` (Persist-ID-Asset), Response-Klasse `C2IQ`. Hülle wie in WA_USERNAME.md 2.2.

| Variable | Quelle |
|----------|--------|
| `query_input[]` | pro Nutzer: JID, `client_known_username`, `about_status{dhash}`, `picture{id}`, `business{serial, tag}`, `devices{hash, timestamp, expected_timestamp}`, `privacy_token{tctoken, timestamp}`, `common_group` |
| `telemetry.context` | Kontext-String in Kleinbuchstaben |
| `include_username`, `include_reachability`, `include_linked_profiles`, `include_lid`, `include_about_status`, `include_picture`, `include_biz`, `include_ddm`, `include_devices`, `include_orgs` | Booleans, gesetzt, wenn irgendein Nutzer das Protokoll anfragt |
| `picture_field_input` | `type` `IMAGE` oder `PREVIEW`, `preview_px` für Previews |
| `business_input` | `include_profile`, `include_vname`, `profile_version` |

Nicht über MEX transportiert: contact und text_status. Nur MEX: reachability, linked profiles, orgs, ddm (Disappearing Mode). Response-Details jenseits von username und lid (WA_USERNAME.md) wurden nicht gelesen (unknown).

### 8.2 Wann MEX genutzt wird (found, `C18580m0`)

1. AB **37780** (int, Default 0) ungleich null: Routing pro Protokoll. Obere 16 Bit = Bitmaske, die über klassisches usync (`SMAX`) läuft, untere 16 Bit = Maske, die über MEX läuft; sonst `DROP`. Bits (`M5H`): status 4, picture 8, business 16, devices 32, disappearing_mode 128, username 512, text_status 1024, orgs 2048. Request-Ebenen-Bits 1 (contact), 2 (`C70582ym.A07`, vermutlich Side List, inferred) und 256 reisen als "identity"-Maske. Ein Protokoll, das die gewählte Route nicht tragen kann, wird auf `DROP` gesetzt: text_status auf MEX, orgs auf SMAX. Die Logzeile lautet `ContactSyncHelper/read_route type=.. contacts=.. identity=..,.. failed=..`.
2. Sonst mit AB **33432** (Default false): klassische Query für den Haupt-Request, danach ein "mex profile follow-up" (`..._mex_profile`) für devices, mit einem Metrik-Marker, annotiert mit `requested_users`, `is_delta_sync`, Outcome `success`, `partial_success`, `no_result`, `timeout`, `exception`, `interrupted`.
3. Sonst entscheidet `A0F` pro Request: MEX wird abgelehnt, wenn der Request contact oder text_status enthält ("cantUseMex"), braucht AB **9732** für business und AB **8421** für username; der Rest darf über MEX laufen (`C229259vZ`), mit 128000 ms Wartezeit.

Default-Zustand dieses Builds: 37780 = 0, 33432 = false, 9732 = false, 8421 = false, USync läuft also über die klassische Stanza, sofern kein serverseitiger AB-Override etwas ändert.

---

## 9. Rate Limits, Fehler, Backoff

### 9.1 Fehlerformen (found)

| Wo | Form | Geparst von |
|----|------|-------------|
| IQ-Fehler | `<iq type="error"><error code backoff/></iq>` | `Brt`: `code`, `backoff` Sekunden * 1000, gedeckelt bei 3600000 ms (-1, wenn nicht vorhanden); ruft `BIz(type, sid, code, backoffMs)`, schließt das Future mit null ab |
| Zustellfehler | Transport-Callback | `Bog`: Future schlägt mit `C216419Uc` fehl; Sync-Zustand pro JID zurückgesetzt (`C502424l.A01`) |
| Protokollfehler | `<result><PROTO><error code text backoff/></PROTO></result>` | `C18670m9.A01`: `backoff` Sekunden * 1000, Default 7200 s, Deckel 3600000 ms (1 h); loggt `connection/unisynciq/parse/<proto>/error` |
| Protokollerfolg | `<PROTO refresh="n"/>` | `refresh` Sekunden * 1000 |
| Teilfehler auf Nutzerebene | `<devices><error code text/></devices>` | Zustand -1, Nutzer bleibt erhalten |
| MEX-Fehler | GraphQL-Error, Pfadfeld `<proto>_info`, optionaler Backoff-String | `C229259vZ.A00`: Backoff Default **7200**, Deckel 3600000, keine * 1000-Umrechnung in diesem Pfad (Einheiten unklar, unknown) |
| Username-Key | Codes `42901` (Requestor) und `42902` (Requestee) im Contact-Ergebnis | `C23638AId.A0G`, siehe WA_USERNAME.md |

Im Client-Code gesehene Codes: `429` (Rate Limit: Sync-Ergebnis 5), `503` (globaler Backoff), `42901`, `42902`.

### 9.2 Backoff-Store (found, Prefs-Datei `contact_sync_prefs`, `C18800mM`)

| Key | Geschrieben, wenn | Wert |
|-----|-------------------|------|
| `contact_sync_backoff` | jeder IQ- / Contact-Protokollfehler mit Backoff über 0 (`X.0m7.BIz`, `AO4.BIz`) | now + Backoff in ms |
| `delta_sync_backoff` | dasselbe, Modus delta und Code 429 | now + Backoff |
| `global_backoff_time` | dasselbe, Code 503 | now + Backoff |
| `sidelist_sync_backoff` | `ContactQuerySync`-Callback `AO2.BIz` bei **jedem** Fehler mit Backoff über 0 | now + Backoff; Code 503 setzt zusätzlich `global_backoff_time` (der Key-Name passt nicht zum Sync-Scope; found) |
| `contact_full_sync_wait`, `status_full_sync_wait`, `sidelist_full_sync_wait` | Attribut `refresh` des Protokollergebnisses | ms; ungesetzt = 86400000 (24 h) |
| `status_`, `picture_`, `business_`, `devices_`, `disappearing_mode_`, `lid_`, `username_`, `text_status_`, `reachability_` `sync_backoff` | Backoff des Protokollfehlers pro Protokoll in `BJ0` | now + Backoff |
| `last_contact_full_sync`, `last_status_full_sync`, `last_sidelist_full_sync` | Abschluss des Full-Sync | Timestamp |

`C18800mM.A02()` setzt die Keys contact, sidelist, status, picture, business, devices, delta, disappearing_mode, lid, reachability und global auf -1 zurück; `username_sync_backoff` und `text_status_sync_backoff` stehen nicht in dieser Liste (found).

Per String-Suche gefundene Reader: `reachability_sync_backoff` (`C18580m0`), `text_status_sync_backoff` (`C3MA`), die drei `*_full_sync_wait`-Keys und `last_*_full_sync` (periodischer Job: ein Full-Sync ist fällig, wenn `wait - now + last` höchstens 1800000 ms, 30 min, beträgt). Es wurde kein Reader von `contact_sync_backoff`, `delta_sync_backoff`, `global_backoff_time` oder den übrigen Keys pro Protokoll gefunden (unknown, ob die Prüfung den Key dynamisch baut).

### 9.3 Lokale Limits (found)

In-Flight-Dedupe: ein `querySyncJid` pro JID, eine Telefon-Query pro Nummer. Timeouts: 32000 ms Einzel-Lookup, 128000 ms Batch, 180 s für das Callback-Warten von `C18230lP.A00` (unbegrenzt bei `C11980aQ.A09`). Backoff-Deckel 3600000 ms. Batches der Privacy-Token-Auffrischung: 10 Nutzer. Serverseitige Query-Limits pro Account und pro Nummer sind unknown.

---

## 10. Was USync auslöst

Reason = `EnumC21800s4`-Wert (Client-Label, für Scheduling und Metriken). Typ = Sync-Typ.

| Client-Feature | Reason | Typ | Protokolle |
|----------------|--------|-----|------------|
| Registrierung abgeschlossen | `REGISTRATION_FULL` (`C25100xS`, `CJ8`) | `REGISTRATION_FULL` (Code 0) | Contact-Menge (Companion-Variante nicht verfolgt) |
| Contacts-Onboarding | `NC_ONBOARDING` | `A0G` Delta-Upload (`CONTACT_UPLOAD`) | contact + lid |
| Adressbuch des Geräts geändert (nur Primary) | `DEVICE_ADDRESS_BOOK_CHANGE` | dringendes On-Change-Delta (`C18230lP.A02`) | nicht verfolgt |
| Periodischer und erzwungener Full-Sync | `PERIODIC_FORCE_SYNC`, `FORCE_SYNC` | `BACKGROUND_FULL` | contact / Side List |
| Kontaktauswahl geöffnet | `CONTACT_PICKER_FULL_SYNC`, `CONTACT_PICKER_USYNC_RETRY` | `INTERACTIVE_FULL` | nicht verfolgt |
| Kontakt hinzufügen, neuer Chat per Nummer, Deep Link, kontaktloser Chat | `*_CONTACT_ADD`-Reasons existieren; nicht an den Query-Pfad gebunden | `ADD_QUERY` (`C9AA`) / `INTERACTIVE_QUERY` (`C9AQ`, `C9AY`, `AWR`, `A1P`) | siehe 4.1 |
| Chat mit unbekanntem Nutzer oder Business öffnen | `CONVERSATION_SIDE_CONTACT`, `SIDELIST_REQUEST` | Telefon-Query (`INTERACTIVE_QUERY`) bei AB **20988** (Default true), sonst `INTERACTIVE_DELTA_SIDELIST` | siehe 4.1 / 4.3 |
| Nachricht an Broadcast-Liste senden | `LID_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | lid |
| Gruppennachricht senden (Größe innerhalb AB 934..1946) | `DEVICE_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | devices |
| Eingehende Nachricht mit fehlgeschlagener ADV-Sender-Prüfung, ADV-Metadaten-Abweichung | `DEVICE_REQUEST` | `BACKGROUND_MULTI_PROTOCOL_QUERY` | devices |
| Aufbau der Call-Verschlüsselung | `DEVICE_REQUEST` | `VOIP_MULTI_PROTOCOL_QUERY` | devices |
| Sync des eigenen Accounts | `DEVICE_REQUEST` | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | devices |
| Server-Push: Änderung von contact, status, picture, business, username | `NOTIFICATION_*`, `USERNAME_UPDATE_NOTIFICATION` | `NOTIFICATION_CONTACT` / `NOTIFICATION_SIDELIST` | je nach Notification |
| Auffrischung von Disappearing Mode und Text-Status | `DM_FORCE_REFRESH`, `TEXT_STATUS_FORCE_REFRESH` | `BACKGROUND_MULTI_PROTOCOL_QUERY` (Text-Status auch `BACKGROUND_FULL`) | disappearing_mode / text_status |
| Account-Wechsel | `ACCOUNT_SWITCH_REFRESH` | `BACKGROUND_FULL` | nicht verfolgt |
| Privacy-Token-Auffrischung | `PRIVACY_TOKEN_REFRESH` | `BACKGROUND_QUERY_PICTURES` | picture |
| Änderung des LID-PN-Mappings | `LID_REQUEST` | `BACKGROUND_DELTA` | alles außer orgs |
| Business-Chat (Nachricht hinzugefügt, Anruf) | `BUSINESS_CONTACT_CHAT` (`C0LX`, `RunnableC23932ATn`) | `BACKGROUND_MULTI_PROTOCOL_QUERY` / `VOIP_MULTI_PROTOCOL_QUERY` | nicht verfolgt |

---

## 11. Feature-Flags

AB-Prop-IDs wie an den Aufrufstellen gelesen; Defaults aus den Config-Tabellen dieses Builds. Flag-IDs in Fett.

| Flag | Typ | Default | Steuert |
|------|-----|---------|---------|
| **5751** | bool | false | devices in Contact- und Telefonnummern-Queries anfragen |
| **5839** | bool | false | text_status-Protokoll (Request und Parsing) |
| **9667** | bool | true | Privacy-Anreicherung für picture- / status-Requests |
| **20798** | bool | false | Privacy-Anreicherung für text_status |
| **29769**, **29770**, **29771** | bool | false | Privacy-Anreicherung für devices-, contact-, lid-Requests |
| **9732** | bool | false | business über MEX |
| **8421** | bool | false | username über MEX |
| **37780** | int | 0 | Routing-Masken pro Protokoll (obere 16 SMAX, untere 16 MEX) |
| **33432** | bool | false | geteilte klassische Query + MEX-Profile-Follow-up |
| **12402** | bool | false | `lid` und `pin` am Username-`contact` |
| **14565** | bool | false | `addressing_mode="lid"` an contact, PN-Text nur mit Ziffern |
| **26739** | bool | false | `+`-Präfix an Telefonnummern |
| **471** | int | 1140 | business `profile v` (maskiert mit 0x3FFC) |
| **730** | int | 35 | maximales Alter des ADV-Key-Index in Tagen (gedeckelt bei 35) |
| **31261** | bool | false | fügt den bekannten `@username` pro Nutzer hinzu (`C223639je`) |
| **33609** | bool | true | bei true lässt der Key-Entry-Lookup `<username/>` weg |
| **20988** | bool | true | Telefon-Query statt Side-List-Sync bei einem unbekannten Business-Chat |

---

## 12. Baileys (`baron-baileys-v2`, verglichen mit `src/WAUSync` und `Socket/socket.js`)

| Thema | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| Hülle | `iq to=s.whatsapp.net type=get xmlns=usync` + `usync{context, mode, sid, last="true", index="0"}` | gleiche Attribute; `to` implizit |
| Modi | `query` (Default), `delta` | zusätzlich `full`, `download` |
| Kontexte | `interactive` (Default), `background`, `message`; `voip` taucht in seiner Backoff-Regel auf | zusätzlich `registration`, `notification`, `add`, `voip`, `metadata`, `snapshot`, `wamo` |
| Protokolle | ergänzt `bot`, `feature`, `sidelist` als Query-Child | kein `bot`- / `feature`-Child; Side-List-Nutzer stehen in `<side_list>` |
| contact | `<contact>phone</contact>`, Username mit `pin` / `lid`, `type` | Telefon mit `+`, `type="delete"`, Username |
| Status versteckt | `code="401"` an `<status>` ergibt `''` | `type="fail"` mit 401 / 403 / 404 |
| Privacy-Nachweis | `<tctoken>` nur unter dem status-Protokoll, wenn der Nutzer einen Token trägt | `<tctoken>` für picture / status / weitere und `common_gid` |
| Backoff | `error backoff` Sekunden * 1000, unbegrenzt | bei 1 h gedeckelt |

| Symptom (inferred) | Ursache | Fix |
|--------------------|---------|-----|
| picture / status fehlt bei Nicht-Kontakten | kein tctoken, keine `common_gid` | gespeicherten `<tctoken>` oder eine gemeinsame Gruppen-JID pro Nutzer anhängen |
| Device-Liste abgelehnt | Key-Index-Prüfungen von `ts` / `raw_id` aus Abschnitt 5.3 | verifizieren, dass `ts` dem signierten `details.timestamp` entspricht |
| Backoff ignoriert | Baileys nutzt den Serverwert ohne Deckel | bei 1 h deckeln, pro Protokoll warten |

---

## 13. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `ContactQuerySync/querySyncJid: rate-limit-error` | Contact-Ergebnisfehler 429, leere Liste | den gelieferten `backoff` abwarten, Query-Rate senken |
| `connection/unisynciq/parse/<proto>/error` | Fehler-Node pro Protokoll | `backoff` nur für dieses Protokoll speichern |
| `handleSyncContactError ... code=503` | Serverüberlastung | globaler Backoff, später erneut versuchen |
| `sidelist-jid-absent-from-response` | Server hat einen angefragten Side-List-Nutzer ausgelassen | Client markiert den Nutzer als synchronisiert, um eine Schleife zu vermeiden |
| `contactsyncDevicesupdater/update/verifyADVSignedKeyIndexList fail` | Signatur-, Proto- oder Timestamp-Prüfung fehlgeschlagen | Device-Zeile nicht aktualisiert, Refresh eingereiht |

---

## 14. Zentrale Unterscheidungen

| Nicht verwechseln | Detail |
|-------------------|--------|
| Sync-Typ vs. Reason | der Typ (`EnumC21760rz`) bestimmt Modus, Kontext, Scope; der Reason (`EnumC21800s4`) ist nur ein Label für Scheduling und Metriken |
| `list` vs. `side_list` | Adressbuch-Nutzer vs. Nutzer außerhalb des Adressbuchs (Side Contacts) |
| usync vs. MEX `UsyncQuery` vs. MEX-Contact-Mutations | drei Transporte für verwandte Daten; Routing-Flags in 8.2 und 4.5 |
| `<devices>`-Ergebnis vs. signierter Key-Index | der Device-Liste wird nicht vertraut, bis die signierte Liste verifiziert ist (5.3) |
| `refresh` vs. `backoff` | `refresh` = wie lange ein gutes Ergebnis wiederverwendet werden darf, `backoff` = wie lange nach einem Fehler Abstand zu halten ist |

---

## 15. Vollständiger Ablauf

```
[Feature]         [ContactSyncMethods]            [UniSync builder / MEX]                [Server]
  │ trigger (10)         │                                  │                               │
  ▼                      ▼                                  │                               │
 reason + type ──► SyncRequest (protocol set, users)        │                               │
                         │ enrich: tctoken / common_gid (7) │                               │
                         │ route per protocol (8)           ▼                               │
                         └──► classic: <iq xmlns=usync><usync sid index last mode context> ─►│
                         └──► MEX: w:mex UsyncQuery {query_input, include_*} ───────────────►│
                                                            │◄── <usync><result> per protocol│
                                                            │     <list> <side_list>         │
                                                            ▼                               │
                    parse: contact in/out, status, picture, business,                       │
                           devices + key-index-list, lid val, username                      │
                                  │                                                         │
        ┌─────────────────────────┼─────────────────────────┐                               │
        ▼                         ▼                         ▼                               │
 devices: verify ADV sig,   LID/PN pairs ──► mapping   result errors: 429 / 503 / backoff   │
 ts, raw_id, valid_indexes  store (N27.A03)            ──► prefs; refresh ──► full_sync_wait │
        │ ok                                                                                │
        ▼                                                                                   │
 device rows updated ──► message fan-out, call setup, side-list chats use the new data      │
```

---

## 16. Unbekanntes

| Thema | Grund |
|-------|-------|
| `to`-Attribut des IQ | vom Sender hinzugefügt; Sender nicht verfolgt |
| Unterschied von `C10140Tq.A0A` (registration) vs. `A06` | nicht verfolgt |
| Serverregeln für Query-Rate, Limits pro Nummer, welche Protokolle ein Requester lesen darf | Client sieht nur Fehlercodes |
| Reader von `contact_sync_backoff`, `global_backoff_time`, `delta_sync_backoff` | kein String-Reader gefunden |
| MEX-Backoff-Einheiten | kein `* 1000` in `C229259vZ.A00` |
| Welche Route in Produktion gewinnt | alle Routing-Flags sind in diesem Build standardmäßig aus; serverseitige AB-Werte unbekannt |
| Tatsächlicher Traffic | nur statische Analyse |
