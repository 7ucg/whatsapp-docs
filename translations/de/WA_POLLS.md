<!-- src-sha1: 287eecdda43f9253685bac27a2f3bea697aa3989 -->
# WhatsApp Umfragen — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** Umfragen-Nachrichtenfamilie (`pollCreationMessage` bis `pollCreationMessageV6`, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), Versionsgeschichte und Sende-/Empfangsauswahllogik, Erstellungsvalidierung und Limits, Verknüpfung von Bild-Umfrage-Optionen, Stimmauswahl und Privacy-Modell, Mehrfach- vs. Einfachauswahl, Umfragebearbeitung, Forward-Zeit-Ergebnis-Snapshotting, Feature-Flags

---

## 1. Was es ist

Eine Umfrage ist ein `Message`-Sub-Objekt (`PollCreationMessage`, unverändert über sechs versionierte Top-Level-Felder wiederverwendet), das eine Frage, eine Liste von Optionen, eine Auswahlobergrenze und optionale Quiz-/Endzeit-/Sichtbarkeits-Einstellungen trägt. Stimmen (`pollUpdateMessage`), hinzugefügte Optionen (`pollAddOptionMessage`) und Bearbeitungen (`secretEncryptedMessage`) sind separate Folgenachrichten, die an die ID der Erstellungsnachricht gebunden und über deren Per-Message-Secret verschlüsselt sind; diese Verschlüsselung (HKDF-Anwendungsfälle, AES-GCM, AAD, Identity-Retry) ist in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) abgedeckt und wird hier nicht wiederholt. Dieser Report deckt die Nachrichtentyp-Ebene ab: welches Feld was trägt, wie der Client zwischen ihnen wählt, Validierung und Limits, und was die umfragespezifischen Handler mit den entschlüsselten Payloads tun. Alle Befunde sind statische Analyse der dekompilierten 2.26.41.6-APK (Java-Quellen unter `java_src/`, plus `res/values/strings.xml`); nichts wurde auf der Leitung mitgeschnitten. Stufen: **found** = im Code/in Ressourcen gelesen, **inferred** = aus Code abgeleitet, **unknown** = nicht aufgelöst.

| Entität | Feld in `Message` | Proto-Typ | Rolle |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | ursprünglicher Erstellungs-Slot |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | Erstellung in der Default-Subgroup-Chat einer Community |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | einfacher Umfrage-Erstellungs-Slot (aktueller Standard für gewöhnliche Umfragen) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | Forward-Compat-Wrapper um eine innere `Message.pollCreationMessage` (Feld 49) |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | Quiz-Erstellungs-Slot |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | erweiterter Umfrage-Slot (Endzeit / Voter-Namen verbergen / Option hinzufügen erlauben) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | ein Bild einer Bild-Umfrage-Option, über `messageAssociation` mit der (noch nicht gesendeten) Umfrage verknüpft |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | fügt einer bestehenden Umfrage eine Option hinzu |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | Stimme (verschlüsselt) oder Stimmen-Metadaten |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | statischer Ergebnis-Snapshot, Umfrage in einen anderen Chat weitergeleitet |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | dasselbe, Quiz-Variante (Stimmenzahlen auf null gesetzt) |

Feldnummern direkt gegen `C30628DTw` (die `Message`-Proto-Klasse) verifiziert, die alle elf `POLL_*_FIELD_NUMBER`-Konstanten passend zur obigen Tabelle deklariert.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Felder (found)

| Feld | Nummer | Typ | Verwendung |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | auf der Leitung vorhanden, aber von den in diesem Pass gelesenen Handlern ungenutzt (Stimmen verwenden das Per-Message `messageSecret`, nicht dieses Feld; siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | Umfragefrage, max. 5000 Zeichen, erforderlich |
| `options` | **3** | repeated `Option` | Antwortoptionen |
| `selectableOptionsCount` | **4** | uint32 | Auswahlobergrenze, erforderlich (§11) |
| `contextInfo` | **5** | `ContextInfo` | Standard-Kontext |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | korrekte Quiz-Antwortoption, erforderlich wenn `pollType=QUIZ` |
| `endTime` | **9** | int64 | Umfrage-Schlusszeitpunkt (ms) |
| `hideParticipantName` | **10** | bool | "Voter-Namen verbergen" (§10) |
| `allowAddOption` | **11** | bool | "Anderen erlauben, Optionen hinzuzufügen" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, nur für Bild-Umfrage-Optionen befüllt, §5).

### 2.2 Lokale Repräsentation

Der Client speichert eine geparste Umfrage als `C13J` (Quiz-Bild-Variante `C13K`), mit Optionen als `C33283EeZ`-Objekten, die den rohen Namen (`A04`), einen lokal berechneten SHA-256-Digest des Namens (`A02`, §9.1) und, für Bildoptionen, den Wire-`optionHash` (`A08`) tragen.

---

## 3. Versionsgeschichte

### 3.1 Welches Feld zum Senden verwendet wird (found, `F2N.A00`/`A02`)

```text
pollType == QUIZ (correct answer set)              -> pollCreationMessageV5
chat is a community default-subgroup (group_type 3) -> pollCreationMessageV2
else:
  hideParticipantName / endTime / allowAddOption set -> pollCreationMessageV6
  none of those set                                   -> pollCreationMessageV3
```

`pollCreationMessageV4` wird vom in diesem Pass gelesenen Sendepfad nie befüllt; es erscheint nur beim Empfang (§3.3). Der Community-Check verwendet dasselbe `group_type == 3`-Prädikat wie der Plaintext-Reaction-Fallback in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2 (`C0GQ.A0A(chat) == 3`, aus `isDefaultSubgroup_` gesetzt); warum eine Community-Subgroup-Umfrage einen eigenen versionierten Slot statt V3/V6 erhält, wird im hier gelesenen Code nicht erklärt (inferred: historische Rollout-Reihenfolge, da V2s Feldnummer die niedrigste des erweiterten Sets ist).

In der Praxis also: **V3** ist der aktuelle Slot für eine gewöhnliche Mehrfach-/Einfachauswahl-Umfrage ohne Extras, **V6** ist aktuell für eine Umfrage mit Endzeit, verborgenen Voter-Namen oder Option-hinzufügen, **V5** ist aktuell für Quizze, und **V2** ist eine Community-Subgroup-spezifische Variante derselben Grundform. **V1** (das unversionierte Feld 49) und **V4** werden vom Sender in diesem Build nicht gewählt.

### 3.2 `pollCreationMessageV4` = Forward-Compat-Wrapper (found, `F2N.CM7`)

V4s Proto-Typ ist `FutureProofMessage` (`BD2`, einziges Feld `message` = eine innere `Message`). Beim Empfang, wenn der V4-Slot befüllt ist, entpackt der Client `BD2.message_` und liest *deren* eigenes `pollCreationMessage`-Feld (49) als die eigentliche `PollCreationMessage`. Dies ist ein echtes Fallback-Envelope, kein totes Feld: ein Sender, der eine neuere/undefinierte Umfrage-Variante senden muss, kann eine einfache (feld-49-geformte) Umfrage in V4 einwickeln, damit ältere Clients — die nur das generische `FutureProofMessage`-Unwrap verstehen, nicht den neueren Slot — trotzdem eine einfache Umfrage rendern. Kein Codepfad in diesem Pass befüllt V4 beim Senden, daher existiert dies für Forward-/Backward-Kompatibilität zwischen Client-Versionen, nicht für etwas, das der 2.26.41.6-Client selbst sendet (inferred).

### 3.3 Empfangsseitige Auswahl und Downgrade (found, approximativ; Dekompiler hat Teile der Branch-Struktur verloren)

`F2N.CM7` prüft die `Message`-Bitfields in der Reihenfolge V1 → V2 → V4 → V5 → V6 → V3-Fallback und parst, welches versionierte Feld auch immer befüllt ist, in denselben Validator (`F2N.A01`, §4). Drei Flags gaten die Akzeptanz der V6-Extra-Felder beim Empfang; wenn ein Flag aus ist, wird die Umfrage **downgegraded** (als generischer Future-Proof-Platzhalter geparst statt als Umfrage-Bubble) statt gänzlich abgelehnt:

| Extra-Feld | Gate | Effekt wenn Gate aus ist |
|-------------|------|--------------------------|
| `endTime` | AB-Int **24884** (`receivingEnabled`) | protokolliert `poll downgraded to FMessageFuture (receiving disabled)`, nicht als Umfrage gerendert |
| `hideParticipantName` | AB-Int **24885** | Downgrade (genaue Polarität des Checks aus dem dekompilierten Kontrollfluss nicht vollständig aufgelöst) |
| `allowAddOption` | AB-Int **25758** | Downgrade |

Die genaue Verschachtelung dieser drei Bedingungen konnte nicht vollständig rekonstruiert werden (JADX meldet duplizierte/unerreichbare Blöcke in `F2N.CM7`); die Gating-Flags und das Downgrade-Ergebnis sind found, die präzise boolesche Kombination ist inferred.

### 3.4 Image-Content-Gate

`pollContentType = IMAGE` wird nur im V3/V5-Parse-Pfad respektiert, wenn das Bit für `pollContentType` gesetzt ist; ist es gesetzt, der Wert aber nicht `IMAGE`, wird die Nachricht abgelehnt (`return null`, fällt durch zum generischen Parser) statt stillschweigend als Text behandelt zu werden.

---

## 4. Erstellungsvalidierung (found, `F2N.A01`)

Einzelner Validator, geteilt von allen versionierten Erstellungsfeldern. Wirft, Fehlercode **11** sofern nicht anders angegeben:

| Check | Regel | Fehlerstring |
|-------|------|--------------|
| Name vorhanden | `name`-Bit muss gesetzt sein | `poll_creation_missing_name` |
| Namenslänge | 1–5000 Zeichen (sofern kein lenienter Parse-Kontext dies umgeht, §4.1) | `poll_creation_invalid_name` |
| Quiz-korrekte Antwort | falls `pollType=QUIZ`, `correctAnswer`-Bit muss gesetzt sein | `poll_creation_missing_correct_answer` |
| Optionen vorhanden | mindestens eine Option, sofern nicht der Zero-Options-Bypass (§4.1) greift | `poll_creation_missing_options` |
| Optionsanzahl (unten) | ≥ 2 Optionen (0 unter dem Bypass) | `poll_creation_invalid_options_count` |
| Optionsanzahl (oben) | ≤ `min(AB-Int 1408, 12)` — 12 ist eine harte Client-Obergrenze unabhängig vom Serverwert | `poll_creation_invalid_options_count` |
| Optionsnamenslänge | 1–2500 Zeichen pro Option | `poll_creation_invalid_option` |
| Name der korrekten Antwort | falls Quiz, `correctAnswer.optionName` muss nicht-leer sein | `poll_creation_missing_correct_answer_name` |
| Doppelte Optionen | Optionsnamen müssen eindeutig sein | `poll_creation_duplicate_options` |
| Doppelte getrimmte Optionen | unter AB-Flag **25758** müssen auch whitespace-getrimmte Namen eindeutig sein | `poll_creation_duplicate_trimmed_options` |
| Korrekte Antwort matcht eine Option | Name der Quiz-korrekten Antwort muss dem Namen einer Option entsprechen | `poll_creation_unmatched_correct_answer` |
| Auswahlanzahl vorhanden | `selectableOptionsCount`-Bit muss gesetzt sein | `poll_creation_missing_selectable_options_count` |
| Auswahlanzahl-Bereich | `0 <= selectableOptionsCount <= options.size()` (oder `<= min(1408,12)` unter dem Bypass) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Zero-Option-/lenienter Bypass (found Codepfad, Semantik inferred)

Ein lokaler Boolean (`z`), berechnet aus AB-Bool **37909**, nur konsultiert wenn ein interner Parse-Kontext-Zähler gleich 1 ist, lockert die Mindest-Optionsanzahl auf 0 und weitet die Auswahlanzahl-Obergrenze auf die rohe `min(1408,12)`-Grenze statt `options.size()`. Der Parse-Kontext-Wert, dem dies entspricht (normaler Empfang vs. ein anderer Ingestion-Pfad, z. B. History-Sync), wurde nicht aufgelöst; dies wird als found-aber-unerklärt festgehalten, nicht als bestätigtes nutzersichtbares "optionslose Umfrage"-Feature.

### 4.2 History-Sync-/lenienter-Name-Bypass

Ein separates Kontext-Flag (`c33371Eg0.A0W`) überbrückt sowohl den Namenslänge-Check als auch (äquivalent, in `F39`, §9) den Namenslänge-Check des Ergebnis-Snapshots und akzeptiert den rohen String ungeprüft. Konsistent mit einem Trusted-Source-Parse-Pfad (z. B. lokaler History-Re-Import) statt einem normalen Netzwerk-Empfang; nicht unabhängig bestätigt.

---

## 5. Bild-Umfrage-Optionen: `pollCreationOptionImageMessage`

### 5.1 Struktur und Verknüpfung (found)

`pollCreationOptionImageMessage` (Feld 90) wickelt eine gewöhnliche hochgeladene `ImageMessage` in einer `FutureProofMessage` ein — das Bild ist **nicht** in `PollCreationMessage.Option` eingebettet. Jedes Options-Bild wird als eigene Kindnachricht gesendet, verknüpft mit der (noch nicht gesendeten) Umfrage über `MessageContextInfo.messageAssociation`, Assoziationstyp `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; dieser Build-Enumwert — ein früherer Build hatte ihn auf 7, der numerische Wert ist über Versionen nicht stabil und muss pro Release neu gelesen werden). Der Sendeseitige Helfer "MediaPollAssociationProvider" (in `C20M`) zählt `message_association`-Zeilen für die Row-ID der Eltern-Umfrage und Assoziationstyp `6`; sobald die Anzahl die Optionsanzahl erreicht, gelten alle Options-Bilder als hochgeladen und der Client fährt fort, die Umfrage selbst mit `pollContentType = IMAGE` zu senden.

### 5.2 Options-Hash für Bild-Optionen (inferred, aus einem früheren Build übernommen, in 2.26.41.6 nicht Zeile für Zeile neu abgeleitet)

Für reine Text-Optionen bleibt das Wire-`optionHash`-Feld leer; der einzige für eine Text-Option berechnete Hash ist der lokale Lookup-Digest `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(direkt in 2.26.41.6 bestätigt, §9.1 — dies ist der Hash, gegen den Stimmauswahlen gematcht werden, nicht das Proto-`optionHash`-Feld). Für **Bild**-Optionen ist das Proto-`optionHash`-Feld befüllt; ein Trace der Sendesequenz einer früheren Version fand, dass es den Namens-Hash der Option mit dem `fileSha256` des hochgeladenen Bildes kombiniert:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Diese Formel wurde in diesem Pass nicht gegen den 2.26.41.6-Code neu verifiziert (die berechnende Klasse wurde nicht lokalisiert); sie wird als inferred übernommen und sollte vor Verwendung neu geprüft werden.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, Feld 121)

### 6.1 Felder (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, dieselbe Form wie die der Stimme, §7).

### 6.2 Senden (found, `F2L.ADr`)

Baut eine `Option` aus dem neuen Namen (und, für Bild-Umfragen, deren Hash), hängt den Schlüssel der ursprünglichen Umfrage an, und — für 1:1-Chats, wenn kein Edit-Kontext — löst die Sender-Identität über die LID/PN-Grenze auf dieselbe Weise auf, wie es die Message-Secret-Schicht für andere Add-ons tut (siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 Schritt 4). Die Option ist auf dieser Ebene selbst *nicht* secret-verschlüsselt wie es ein `pollUpdateMessage` ist: die Add-Option-Payload reist als normales Nachrichtenfeld; was in `secretEncryptedMessage` (Typ `POLL_ADD_OPTION`) eingewickelt wird, ist der Add-Option-Versuch als Ganzes, wenn er auf dem Message-Secret-Schema reiten muss (§8).

### 6.3 Empfangsvalidierung (found, `F2L.CM7`)

| Check | Fehler |
|-------|-------|
| Feature-Gate: AB-Int **25758** muss ungleich null sein | Fehler **10017** |
| `pollCreationMessageKey` vorhanden | `poll_add_option_missing_poll_message_key` |
| `addOption` vorhanden | `poll_add_option_missing_poll_option` |
| Optionsname nicht-leer, ≤ 2500 Zeichen | `poll_add_option_invalid_option` |

Das resultierende lokale Objekt wird für den Transport secret-verschlüsselt unter Verwendung des Anwendungsfalls `Poll Add Option` (bestätigter Aufruf des Message-Secret-Helfers mit `AnonymousClass122.POLL_ADD_OPTION` als Assoziations-Tag). Hinzugefügte Optionen werden für das Matching mit bestehenden Optionen auf dieselbe Weise verfolgt wie Bild-Umfrage-Optionen (Assoziationstyp `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (Stimme und Stimmen-Metadaten)

Vollständige Krypto (HKDF-Anwendungsfall `Poll Vote`, AAD, AES-GCM, LID/PN-Identity-Retry) ist in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7; dieser Abschnitt deckt nur ab, was der Poll-Vote-Handler (`DUA`, erweitert `F2P`) mit dem Plaintext tut.

### 7.1 Zwei Sende-/Empfangspfade (found)

AB-Bool **6772** wählt zwischen:
- **an** (aktuell): ein geteilter Verschlüsselungs-Helfer (`C33285Eeb`) baut Chiffretext und `MessageKey`; Stimme wird aus einem zuvor gespeicherten `(iv, payload)`-Paar wiederholt, falls vorhanden, statt neu zu verschlüsseln.
- **aus** (legacy): ein Inline-Branch in `DUA` macht denselben HKDF/AES-GCM-Aufruf direkt, leitet die Ziel-Sender-Identität selbst ab (eigene LID für Stimmen auf der eigenen Umfrage des Voters, sonst die aufgelöste JID des Stimm-Ziels).

### 7.2 Stimmen-Payload: `PollVoteMessage` (`DPF`)

Einziges Feld `selectedOptions` **1**, repeated bytes — jeder Eintrag ist ein 32-Byte-SHA-256-Namens-Digest der Option (§9.1), kein Index. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`) validiert die entschlüsselte Auswahl:

| Check | Regel | Log-Tag |
|-------|------|------|
| Auswahlgröße | ≤ 12 **und** ≤ `selectableOptionsCount` der Umfrage (wenn > 0) | `poll_vote_invalid_options_count` |
| Hash-Form | jeder ausgewählte Hash dekodiert zu genau 32 Bytes | `poll_vote_invalid_option_hashes` |
| Duplikate | kein wiederholter Hash in einer Stimme | `poll_vote_duplicate_option_hashes` |
| Auflösung | jeder ausgewählte Hash muss einem der bekannten (nicht entfernten) Options-Hashes der Umfrage entsprechen | gibt ein Fehlerergebnis zurück, kein Match -> Stimme abgelehnt |

### 7.3 Endzeit und Metadaten (found, `DUA.A01`)

Eine Stimme, deren `senderTimestampMs` nach der `endTime` der Umfrage liegt, wird abgelehnt (`poll_update_past_end_time`); unter AB-Bool **2321** füttert ein abgelehntes Stimm-Event zusätzlich einen Telemetrie-Zähler (`N0e`). Stimmen-`metadata` (`pollNameHash`, `lastEditStanzaId`) wird beim Senden nur unter AB-Bool **31593** gestempelt; beim Empfang wird ein fehlender/leerer Metadaten-Block als `"unstamped"` protokolliert (nicht allein dadurch abgelehnt), während ein *nicht übereinstimmender* Stempel (geprüft von `C32977EZa`) die Stimme mit `poll_update_tc_drop` fallen lässt. Diese Metadaten existieren, damit ein Client erkennen kann, dass er gegen eine Umfrage stimmt, deren Edit-Historie er noch nicht nachgeholt hat.

---

## 8. Umfragebearbeitung (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Transportiert innerhalb des generischen `secretEncryptedMessage`-Wrappers (Feld 82), kein umfragespezifischer Carrier; siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4 für das Envelope, die AAD und die Fehlercode-Tabelle (`poll_edit_message_stanza_invalid`, AB-Int **24886**-Gate, Fehler **10016**). Die umfragespezifische Validierung (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) verlangt:

- die innere Nachricht ist FMessage-Typ 66 und ist sowohl vor als auch nach der Bearbeitung eine Umfrage;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` und `pollType` sind zwischen der gespeicherten und der bearbeiteten Umfrage **unverändert** — nur der Fragetext und/oder die Optionstexte dürfen abweichen;
- Options-Matching: mit einem Per-Chat-Flag (`EOI.A01()`, ID nicht aufgelöst) aktiviert, werden bearbeitete Optionen gegen eine gespeicherte Rename-Historie via sequenziellem (reihenfolgeerhaltendem) Match abgeglichen, was eine In-Place-Umbenennung von Optionen erlaubt; das genaue Verhalten des Nicht-Umbenennungs-Vergleichszweigs ist inferred (JADX lässt wieder einen Teil des Kontrollflusses fallen — die Funktion fällt in diesem Zweig in der dekompilierten Form durch zu `poll_edit_invalid_edits`, was für das reale Clientverhalten bei einer No-op-Bearbeitung unwahrscheinlich ist).

Ein `"Couldn't edit poll"`-Toast-String existiert in den Ressourcen, was bestätigt, dass Umfragebearbeitung in diesem Build nutzersichtbar ist, nicht nur ein reservierter Protokollpfad.

### 8.1 Poll-Edit-UI (neu in 2.26.45.10) — Wire-Op ungelöst

Ein neues Package `com.whatsapp.polls.ui.edit` liefert `PollEditActivity` plus unterstützende
Dialoge (`PollEditDiscardChangesDialog`, `PollEditSendFailedDialog`,
`PollOptionRemoveConfirmationDialog`), die einem Sender erlauben, eine bereits gesendete Umfrage umzubenennen oder
Optionen hinzuzufügen/zu entfernen. Found und unknown, aus statischem Smali-Tracing (kein Dekompil
über das Lesen existierenden Smalis hinaus):

- **Found:** `PollEditActivity` wird von einem in einem `SavedStateHandle` gehaltenen Edit-State (`LX/8kp`
  View-Model, `LX/A4G` Edit-Payload: Name/ID, Umfragenamens-String, aktuelle Options-Reihen, ein
  `Set<Long>` entfernter Row-IDs) unterstützt. Options-Reihen (`LX/JZ8`) tragen kein Entfernungs-Flag — eine Option
  ist in der finalen Liste, die gegen den Live-Umfragen-State gediffed wird, schlicht abwesend
  (`LX/8kp;->A03(LX/A4G;LX/9ei;LX/8kp;)LX/9oc;`). Optionsentfernung ist durch einen gestuften
  Rollout-Check gegated, `LX/Ihb;->getPollRemoveOptionRollout()LX/1yG;` — ein clientseitiges Feature-Gate,
  kein Beleg für eine neue Wire-Op.
- **Found:** der Proto-Schema-Diff zwischen 2.26.41.6 und 2.26.45.10 enthält **null**
  umfragebezogene Änderungen — kein neues oder umbenanntes Feld für Umbenennung oder Optionsentfernung erscheint
  irgendwo im extrahierten Schema für diese Version.
- **Inferred:** das Hinzufügen einer Option aus dieser UI reitet höchstwahrscheinlich weiterhin auf der bestehenden
  `pollAddOptionMessage` (§6, Feld 121) — die "Reihe hinzufügen"-Affordanz der UI passt zur Form dieser
  Nachricht, und keine Ersatz-Add-Option-Primitive wurde eingeführt. Nicht bestätigt durch
  Tracing des Save-Handlers.
- **Unknown:** Umbenennung und Optionsentfernung haben keine bestätigte Wire-Primitive. Zwei
  unbestätigte Kandidaten, keiner wahrscheinlicher als der andere nach aktueller Evidenz: (1) ein
  vollständiger Umfragen-Ersatz via `Message.editedMessage` (`FutureProofMessage`, das eine frische
  `pollCreationMessage` einwickelt), oder (2) Wiederverwendung des opaken verschlüsselten `vote`-Feldes
  von `pollUpdateMessage` (`PollEncValue`, §7) für ein Nicht-Vote-Update. Der tatsächliche Netzwerkaufruf des Save-Buttons
  sitzt hinter einem geteilten, R8-gemergten `View.OnClickListener`-Dispatcher (`LX/A50`), dessen
  relevanter `switch`-Zweig aus Smali allein nicht isoliert werden konnte — das ist der konkrete
  Blocker, keine Scope-Entscheidung.

Dies wird offen gelassen statt auf eine Best-Guess aufgelöst; neu prüfen, sobald ein Proto-Diff gegen
eine spätere Version ein neues Feld zeigt, oder sobald der `LX/A50`-Dispatch-Zweig getraced ist.

---

## 9. Vote-Matching-Internas

### 9.1 Options-Hash (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

Reines SHA-256 des sichtbaren Textes der Option, kein Schlüsselmaterial. Dies ist der Wert, der pro lokaler Option gespeichert wird (`C33283EeZ.A02`), und der Wert, gegen den die `selectedOptions`-Einträge einer Stimme gematcht werden. Jede Anwendung, die den Text der Option kennt, kann denselben Hash berechnen — die Privacy einer Stimme kommt vollständig aus der Message-Secret-Verschlüsselung der Stimmen-Payload (§7, und [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), nicht daraus, dass der Hash unerratbar wäre.

---

## 10. Stimm-Privacy-/Anonymitäts-Modell

| Behauptung | Status |
|-------|--------|
| Stimmen sind end-to-end-verschlüsselt pro Voter, pro Umfrage (HKDF-Anwendungsfall `Poll Vote`) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| Die gewählte Option wird durch einen Content-Hash identifiziert, nicht durch einen Index | found, §9.1 |
| `hideParticipantName` ("Voter-Namen verbergen") unterdrückt die Anzeige, wer abgestimmt hat, in der UI | found (String `str2137`, Feld 10 von `PollCreationMessage`) |
| `hideParticipantName` verbirgt den Voter vor dem Server oder vor anderen Clients auf Protokollebene | **nicht durch hier gelesenen Code gestützt** — das Envelope `participant`/`from` (d. h. die Identität des Voters) wird für jedes Add-on unabhängig von diesem Flag gleich zugestellt und authentifiziert (siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName` ist eine reine Display-Einstellung am Umfragenobjekt, keine Routing- oder Verschlüsselungsänderung |
| Der Umfragen-Ersteller kann immer bestimmen, wer abgestimmt hat | inferred — nichts im Vote-Decrypt-Pfad (§7, §9) hängt von `hideParticipantName` ab; der Client des Erstellers entschlüsselt jede Stimme mit der Identität des Voters als Modifier |

Kurz gesagt: WhatsApp-Umfragen sind für den Umfragen-Ersteller nicht anonym. "Voter-Namen verbergen" kontrolliert nur, ob *andere Teilnehmer* (in der "Poll votes"-Liste) sehen, wer abgestimmt hat; es ändert nicht, was kryptografisch in die Stimme eingebunden ist, und der Server lernt den Stimm-Inhalt in beiden Fällen ohnehin nicht (die übliche E2E-Garantie, nichts Spezifisches für dieses Flag).

---

## 11. Mehrfach- vs. Einfachauswahl

`selectableOptionsCount` (Feld 4) ist der einzige Mechanismus: eine Stimme mit mehr Auswahlen als diesem Wert wird abgelehnt (§7.2). Es gibt kein separates "ist Mehrfachauswahl"-Boolean auf der Leitung — Einfachauswahl ist schlicht `selectableOptionsCount = 1`. Die Erstellungs-UI exponiert dies als einzelnen Toggle, **"Mehrere Antworten erlauben"** (String `str425f`); wenn aus, wird inferred, dass der Client `selectableOptionsCount = 1` sendet, wenn an, wird inferred, dass er `selectableOptionsCount = options.size()` sendet (die UI scheint keine beliebige numerische Obergrenze zu exponieren — inferred aus dem einzelnen Boolean-String, nicht unabhängig im Erstellungs-UI-Code bestätigt). Das Protokoll selbst erlaubt jeden Wert `0..options.size()` (§4), sodass ein clientseitiger Wert außer 1 oder "alle Optionen" möglich ist, auch wenn die Standard-UI ihn nicht anbietet. Quizze sind implizit Einfachauswahl (eine korrekte Antwort; voter-sichtbarer String `"Quiz • Select one correct answer"`, `str57a5`).

Voter-sichtbare Labels bestätigen die zwei Modi: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: Forward-Zeit-Snapshot

### 12.1 Zweck (found, `F1A`)

Das Weiterleiten einer Live-Umfrage in einen anderen Chat leitet die interaktive Umfrage **nicht** weiter. `F1A` (einer von mehreren "Forward"-Konvertern, die alle dasselbe Konvertierungs-Interface implementieren, das über Nachrichtentypen hinweg genutzt wird — der Sibling-Konverter für nicht unterstützte Typen wirft `"Cannot forward message of type: ..."`) konvertiert die Live-Umfrage (`C13J`) in ein `Dd2`-Objekt: Fragetext, Name jeder Option und **aktuelle lokale Stimmenanzahl**, und der Umfrage-/Quiz-Typ. Dies wird dann als `pollResultSnapshotMessage` (einfache Umfrage) oder `pollResultSnapshotMessageV3` (Quiz) serialisiert und mit einem dedizierten View-Holder (`DWH`) gerendert, verschieden von der interaktiven Umfragen-Bubble.

### 12.2 Felder (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (repeated `PollVote` — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (derselbe `PollType`-Enum wie bei der Erstellung).

### 12.3 Validierung (found, `F39`)

Dieselbe Art von Checks wie bei der Erstellung: Name 1–5000 Zeichen, mindestens 2 Optionen, höchstens `min(AB 1408, 12)` Optionen, jeder Optionsname 1–2500 Zeichen. Für die **Quiz**-Variante (`V3`) werden Stimmenzahlen beim Senden auf 0 gezwungen — ein weitergeleiteter Quiz-Snapshot gibt nie Zählungen preis, nur die Frage und die Optionsliste.

---

## 13. Limits-Zusammenfassung

| Item | Limit | Quelle |
|------|-------|--------|
| Länge des Umfragen-/Fragennamens | 1–5000 Zeichen | `F2N.A01`, `F39.A00` |
| Optionsnamenslänge | 1–2500 Zeichen | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Optionsanzahl (Erstellung, Snapshot) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Ausgewählte Optionen pro Stimme | ≤ 12 und ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| `selectableOptionsCount`-Bereich | 0–options.size() (0–12 unter dem lenienten-Kontext-Bypass, §4.1) | `F2N.A01` |
| Options-Hash-Größe (Vote-Einträge) | exakt 32 Bytes | `AbstractC33199EdC` |

---

## 14. Feature-Flags (IDs wie an den Call-Sites gelesen; Namen ungelöst)

| ID | Typ | Kontrolliert |
|----|------|------|
| **1408** | int | server-konfigurierte maximale Umfrage-Optionsanzahl, harte Client-Obergrenze 12 unabhängig vom Wert |
| **24884** | bool | `endTime` beim Empfang einer erweiterten Umfrage (V5/V6) respektieren; aus -> auf einen Future-Proof-Platzhalter downgegraded |
| **24885** | int | gated die Akzeptanz von `hideParticipantName` beim Empfang (genaue Polarität ungelöst) |
| **24886** | int | Poll-Edit-Empfangs-Gate; 0 -> abgelehnt, Fehler 10016 |
| **25758** | int (truthy) | Poll-Add-Option-Empfangs-Gate (Fehler 10017); gated auch die Ablehnung doppelter getrimmter Optionen bei der Erstellung |
| **31593** | bool | stempelt `pollNameHash`/`lastEditStanzaId`-Metadaten auf eine ausgehende Stimme |
| **6772** | bool | Poll-Vote: geteilter Verschlüsselungs-Helfer (an) vs. Legacy-Inline-Pfad (aus) |
| **37909** | bool | erlaubt eine Umfrage mit null Optionen in einem spezifischen (ungelösten) Parse-Kontext |
| **2321** | bool | zusätzliches Telemetrie-Detail protokolliert, wenn eine Stimme als nach der Umfragen-Endzeit abgelehnt wird |

Flags der Message-Secret-Schicht, die ebenfalls Umfragen betreffen (Edit-Anwendungsfall-Gate **17811**, Generation-Gates usw.), sind in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16 dokumentiert und werden hier nicht wiederholt.

---

## 15. Baileys (nur bestätigte Fakten)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17 deckt bereits die für Umfragen relevanten Teile einer JavaScript-Implementierung (`baron-baileys-v2` 1.5.17) ab, aus dem Lesen von `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`:

- Die HKDF-Ableitung und die Anwendungsfall-Strings `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` entsprechen exakt den Literalen des Android-Clients, einschließlich der `id\0modifier`-AAD für `Poll Vote`.
- Die AAD, der Identity-Retry (PN/LID) und das Handling fehlender Secrets (Fallback auf das rohe, unentschlüsselte Update) entsprechen dem in diesem Report (§7) und in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3 beschriebenen Android-Verhalten.
- Kein Sendepfad zur Verschlüsselung von `pollUpdateMessage` (oder `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) wurde in den gelesenen Dateien gefunden — d. h. diese Implementierung konnte eine eingehende Stimme entschlüsseln, aber die durchgesehenen Dateien enthielten keinen Code, um eine zu verschlüsseln und zu senden.

Nichts umfragespezifisches über das dort bereits Gesagte hinaus wurde in diesem Pass unabhängig neu verifiziert (kein Baileys-Code zu Poll-Creation, Options-Hash oder Poll-Edit wurde gelesen); keine weiteren Baileys-Behauptungen werden hier gemacht.

---

## 16. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | weniger als 2 oder mehr als `min(1408,12)` Optionen | Optionen im Bereich halten |
| `poll_creation_unmatched_correct_answer` | Quiz-`correctAnswer.optionName` entspricht keinem Optionsnamen | die korrekte Antwort auf eine exakte Übereinstimmung setzen |
| Umfrage wird still nicht angezeigt (downgegraded) | `endTime`/`hideParticipantName`/`allowAddOption` auf einer V6-Umfrage gesetzt, aber das passende AB-Flag ist beim Empfänger aus | senderseitig, inhaltlich nicht behebbar; Empfänger-Capability-Lücke |
| `poll_vote_invalid_options_count` | Stimme wählt mehr Optionen als `selectableOptionsCount`, oder mehr als 12 | die Obergrenze der Umfrage respektieren |
| `poll_update_past_end_time` | Stimme (oder Option hinzufügen / Bearbeitung) mit Zeitstempel nach `endTime` | vor Schließung der Umfrage abstimmen |
| `poll_update_tc_drop` | `pollNameHash`/`lastEditStanzaId` der Stimme entspricht nicht der Sicht des Empfängers auf die Umfrage | Poll-Edit-Historie vor dem Abstimmen resynchronisieren |
| Fehler **10017** bei Add-Option | AB **25758** ist beim Empfänger null | Empfänger-Capability-Lücke |
| Fehler **10016** bei Poll-Edit | AB **24886** ist beim Empfänger null | Empfänger-Capability-Lücke |
| `poll_add_option_past_end_time` | Option nach `endTime` hinzugefügt | Optionen vor Schließung der Umfrage hinzufügen |

---

## 17. Wichtige Unterscheidungen

| Dies | Nicht dies |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (`PollCreationMessage`-Typ) | `pollCreationMessageV4` (`FutureProofMessage`, das eine innere einfache Umfrage einwickelt) |
| `pollUpdateMessage` (Stimme, oder Stimmen-Metadaten) | `secretEncryptedMessage` mit `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` (Poll-Edit / Option hinzufügen) |
| `pollAddOptionMessage` (die neue Options-Payload) | `secretEncryptedMessage`-Wrapper, der sie über die Leitung trägt, wenn message-secret-gebunden |
| `pollResultSnapshotMessage`/V3 (statisch, weitergeleitet) | die Live-interaktive Umfrage (`pollCreationMessage*`) |
| Optionsauswahl per SHA-256(name)-Hash | Auswahl per Index — WhatsApp-Umfragen wählen nie nach Position |
| `hideParticipantName` (UI-Display-Einstellung) | Anonymität des Stimmsenders (existiert nicht; Ersteller löst den Voter immer auf) |
| `selectableOptionsCount` (das einzige Mehrfach-/Einfachauswahl-Signal) | ein separates "ist Mehrfachauswahl"-Boolean (keines existiert) |

---

## 18. Vollständiger Ablauf (Erstellung, Bildoption, Stimme, Weiterleitung)

```
[Creator]                                          [Server]                     [Participant]
   │ build PollCreationMessage                        │                              │
   │  (quiz? -> V5; community subgroup? -> V2;         │                              │
   │   extras(endTime/hide/addOpt)? -> V6; else V3)    │                              │
   │ [image poll]                                      │                              │
   │  send N × pollCreationOptionImageMessage           │                              │
   │   (messageAssociation MEDIA_POLL=6, parent key)───▶───────────────────────────▶ received,
   │  wait for all fileSha256                           │                              associated
   │  compute optionHash per option                     │                              │
   │ send pollCreationMessage* ─────────────────────────▶──────────────────────────▶ store poll,
   │                                                    │                              secret
   │                                                    │        select option(s)     │
   │                                                    │        hash = SHA256(name)  │
   │                                                    │        key = HKDF(secret,   │
   │                                                    │          pollId‖creator‖    │
   │                                                    │          voter‖"Poll Vote") │
   │                                                    │        pollUpdateMessage    │
   │◀────────────────────────────────────────────────────◀ {key, vote{ct,iv}, ts} ────│
   │ validate: end time, selection count/hash shape     │                              │
   │ decrypt, resolve hash -> known option              │                              │
   │ apply vote                                         │                              │
   │                                                    │                              │
   │ [user forwards the poll elsewhere]                 │                              │
   │ convert live poll -> Dd2 (name, per-option count)  │                              │
   │ quiz? zero the counts                              │                              │
   │ send pollResultSnapshotMessage[/V3] ───────────────▶──────────────────────────▶ static bubble,
   │                                                    │                              not interactive
```

---

## 19. Unbekannte

| Item | Status |
|------|-------|
| Genaue Polarität von AB **24885** (hideParticipantName akzeptieren/downgraden) | dekompilierte Branch-Struktur unvollständig |
| Formel des Bild-Options-Hashs (`nameHash`+`imageHash`) für 2.26.41.6 | aus einem früheren Build übernommen, in diesem Build-Code nicht neu abgeleitet |
| AB-Flag-ID hinter dem Per-Chat-"geordnetes Options-Umbenennungs"-Toggle, das beim Poll-Edit-Matching verwendet wird (`EOI.A01()`) | ID nicht aufgelöst |
| Nicht-Umbenennungs-Zweig des Poll-Edit-Options-Vergleichs | Dekompiler lässt einen Teil des Kontrollflusses fallen; die wörtliche dekompilierte Form fällt immer durch zu `poll_edit_invalid_edits`, was für das reale Verhalten bei einer No-op-Bearbeitung unwahrscheinlich ist |
| Parse-Kontext-Wert (`c33371Eg0.A00 == 1`), der den Zero-Option-Bypass aktiviert (AB **37909**) | nicht identifiziert (History-Sync vs. ein anderer Pfad) |
| Ob die Standard-Erstellungs-UI `selectableOptionsCount`-Werte außer 1 oder "alle Optionen" senden kann | inferred aus einem einzelnen Boolean-Toggle-String, nicht gegen UI-Code bestätigt |
| Stabilität des numerischen `MEDIA_POLL`-Assoziationswertes über Versionen | found als 6 in 2.26.41.6; ein früherer Build verwendete einen anderen Wert, also nicht über Versionen hinweg hartkodieren |
</content>
