<!-- src-sha1: 4123b5a528529c4f17625135c9cbbdbd63f1dc08 -->
# WhatsApp Polls — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** Poll-Message-Familie (`pollCreationMessage` bis `pollCreationMessageV6`, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), Versionshistorie und Send-/Receive-Auswahllogik, Erstellungsvalidierung und Limits, Image-Poll-Options-Linking, Vote-Selection und Privacy-Modell, Multi-Select vs. Single-Select, Poll-Editing, Forward-Time-Result-Snapshotting, Feature-Flags

---

## 1. Was es ist

Ein Poll ist ein `Message`-Sub-Objekt (`PollCreationMessage`, unverändert über sechs versionierte Top-Level-Felder wiederverwendet), das eine Frage, eine Liste von Optionen, eine Selection-Cap und optionale Quiz-/End-Time-/Visibility-Einstellungen trägt. Votes (`pollUpdateMessage`), hinzugefügte Optionen (`pollAddOptionMessage`) und Edits (`secretEncryptedMessage`) sind separate Folgenachrichten, die an die ID der Creation-Message und ihr per-message Secret gebunden sind; diese Verschlüsselung (HKDF-Use-Cases, AES-GCM, AAD, Identity-Retry) ist in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) behandelt und wird hier nicht wiederholt. Dieser Report deckt die Message-Type-Ebene ab: welches Feld was trägt, wie der Client zwischen ihnen wählt, Validierung und Limits, und was die poll-spezifischen Handler mit den entschlüsselten Payloads tun. Alle Befunde sind statische Analyse der dekompilierten 2.26.41.6-APK (Java-Sources unter `java_src/`, plus `res/values/strings.xml`); nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = im Code/in Resources gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst.

| Entität | Feld in `Message` | Proto-Typ | Rolle |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | ursprünglicher Creation-Slot |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | Creation in einem Community-Default-Subgroup-Chat |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | Plain-Poll-Creation-Slot (aktueller Default für gewöhnliche Polls) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | Forward-Compat-Wrapper um eine innere `Message.pollCreationMessage` (Feld 49) |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | Quiz-Creation-Slot |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | Extended-Poll-Slot (End Time / Hide-Voter-Names / Allow-Add-Option) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | ein Image-Poll-Options-Bild, über `messageAssociation` an den zukünftigen Poll verlinkt |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | fügt einem bestehenden Poll eine Option hinzu |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | Vote (verschlüsselt) oder Vote-Metadaten |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | statischer Result-Snapshot, Poll in anderen Chat weitergeleitet |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | dieselbe, Quiz-Variante (Vote Counts auf null gesetzt) |

Feldnummern direkt gegen `C30628DTw` (die `Message`-Proto-Klasse) verifiziert, die alle elf `POLL_*_FIELD_NUMBER`-Konstanten passend zur obigen Tabelle deklariert.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Felder (found)

| Feld | Nummer | Typ | Verwendung |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | auf der Leitung vorhanden, aber von den in diesem Pass gelesenen Handlern unbenutzt (Votes nutzen das per-message `messageSecret`, nicht dieses Feld; siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | Poll-Frage, max. 5000 Zeichen, erforderlich |
| `options` | **3** | repeated `Option` | Antwortoptionen |
| `selectableOptionsCount` | **4** | uint32 | Selection-Cap, erforderlich (§11) |
| `contextInfo` | **5** | `ContextInfo` | Standard-Context |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | Quiz-Correct-Answer-Option, erforderlich wenn `pollType=QUIZ` |
| `endTime` | **9** | int64 | Poll-Close-Timestamp (ms) |
| `hideParticipantName` | **10** | bool | "Hide voter names" (§10) |
| `allowAddOption` | **11** | bool | "Allow others to add options" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, nur für Image-Poll-Optionen befüllt, §5).

### 2.2 Lokale Repräsentation

Der Client speichert einen geparsten Poll als `C13J` (Quiz-Image-Variante `C13K`), mit Optionen als `C33283EeZ`-Objekte, die den rohen Namen (`A04`), einen lokal berechneten SHA-256-Digest des Namens (`A02`, §9.1) und, für Image-Optionen, den Wire-`optionHash` (`A08`) tragen.

---

## 3. Versionshistorie

### 3.1 Welches Feld zum Senden genutzt wird (found, `F2N.A00`/`A02`)

```text
pollType == QUIZ (correct answer set)              -> pollCreationMessageV5
chat is a community default-subgroup (group_type 3) -> pollCreationMessageV2
else:
  hideParticipantName / endTime / allowAddOption set -> pollCreationMessageV6
  none of those set                                   -> pollCreationMessageV3
```

`pollCreationMessageV4` wird vom in diesem Pass gelesenen Send-Path nie befüllt; es erscheint nur beim Receive (§3.3). Der Community-Check nutzt dasselbe `group_type == 3`-Prädikat wie der Plaintext-Reaction-Fallback in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2 (`C0GQ.A0A(chat) == 3`, gesetzt aus `isDefaultSubgroup_`); warum ein Default-Subgroup-Poll einen eigenen versionierten Slot statt V3/V6 bekommt, wird im hier gelesenen Code nicht erklärt (inferred: historische Rollout-Reihenfolge, da V2's Feldnummer die niedrigste des erweiterten Sets ist).

Also in der Praxis: **V3** ist der aktuelle Slot für einen gewöhnlichen Multi-/Single-Choice-Poll ohne Extras, **V6** ist aktuell für einen Poll mit End Time, Hidden Voter Names oder Add-Option, **V5** ist aktuell für Quizze, und **V2** ist eine Community-Subgroup-spezifische Variante derselben Basis-Shape. **V1** (das unversionierte Feld 49) und **V4** werden vom Sender in diesem Build nicht gewählt.

### 3.2 `pollCreationMessageV4` = Forward-Compat-Wrapper (found, `F2N.CM7`)

V4's Proto-Typ ist `FutureProofMessage` (`BD2`, ein einziges Feld `message` = eine innere `Message`). Beim Receive, wenn der V4-Slot befüllt ist, unwrapped der Client `BD2.message_` und liest das Feld `pollCreationMessage` (49) dieser inneren Message selbst als die eigentliche `PollCreationMessage`. Das ist ein echter Fallback-Envelope, kein totes Feld: ein Sender, der eine neuere/undefinierte Poll-Variante emittieren muss, kann einen Basic-Poll (in Field-49-Shape) in V4 wrappen, sodass ältere Clients — die nur den generischen `FutureProofMessage`-Unwrap verstehen, nicht den neueren Slot — trotzdem einen Plain Poll rendern. Kein Code-Pfad in diesem Pass befüllt V4 beim Senden, also existiert das für Forward-/Backward-Compatibility zwischen Client-Versionen, nicht für etwas, das der 2.26.41.6-Client selbst emittiert (inferred).

### 3.3 Receive-seitige Auswahl und Downgrade (found, approximativ; der Decompiler hat Teile der Branch-Struktur verloren)

`F2N.CM7` prüft die `Message`-Bitfields in der Reihenfolge V1 → V2 → V4 → V5 → V6 → V3-Fallback und parst, welches versionierte Feld befüllt ist, in denselben Validator (`F2N.A01`, §4). Drei Flags gaten die Akzeptanz der V6-Extra-Felder beim Receive; wenn ein Flag aus ist, wird der Poll **downgraded** (als generischer Future-Proof-Placeholder geparst statt als Poll-Bubble), statt rundweg abgelehnt zu werden:

| Extra-Feld | Gate | Effekt wenn Gate aus ist |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | geloggt `poll downgraded to FMessageFuture (receiving disabled)`, nicht als Poll gerendert |
| `hideParticipantName` | AB int **24885** | Downgrade (exakte Polarität des Checks nicht vollständig aus dem Control Flow aufgelöst) |
| `allowAddOption` | AB int **25758** | Downgrade |

Die exakte Verschachtelung dieser drei Conditions konnte nicht vollständig rekonstruiert werden (JADX meldet duplizierte/unreachable Blöcke in `F2N.CM7`); die Gating-Flags und das Downgrade-Outcome sind found, die präzise Boolean-Kombination ist inferred.

### 3.4 Image-Content-Gate

`pollContentType = IMAGE` wird auf dem V3/V5-Parse-Path nur honoriert, wenn das Bit für `pollContentType` gesetzt ist; ist es gesetzt, der Wert aber nicht `IMAGE`, wird die Message abgelehnt (`return null`, fällt durch zum generischen Parser), statt stillschweigend als Text behandelt zu werden.

---

## 4. Erstellungsvalidierung (found, `F2N.A01`)

Einziger Validator, geteilt von allen versionierten Creation-Feldern. Wirft, Error-Code **11** sofern nicht anders angegeben:

| Check | Regel | Error-String |
|-------|------|--------------|
| Name vorhanden | `name`-Bit muss gesetzt sein | `poll_creation_missing_name` |
| Name-Länge | 1–5000 Zeichen (außer ein Lenient-Parse-Context umgeht das, §4.1) | `poll_creation_invalid_name` |
| Quiz Correct Answer | wenn `pollType=QUIZ`, muss `correctAnswer`-Bit gesetzt sein | `poll_creation_missing_correct_answer` |
| Optionen vorhanden | mindestens eine Option, außer der Zero-Options-Bypass (§4.1) greift | `poll_creation_missing_options` |
| Option Count (unten) | ≥ 2 Optionen (0 unter dem Bypass) | `poll_creation_invalid_options_count` |
| Option Count (oben) | ≤ `min(AB int 1408, 12)` — 12 ist eine harte Client-Obergrenze unabhängig vom Server-Wert | `poll_creation_invalid_options_count` |
| Option-Name-Länge | 1–2500 Zeichen pro Option | `poll_creation_invalid_option` |
| Correct-Answer-Name | wenn Quiz, muss `correctAnswer.optionName` nicht-leer sein | `poll_creation_missing_correct_answer_name` |
| Duplicate Options | Options-Namen müssen eindeutig sein | `poll_creation_duplicate_options` |
| Duplicate Trimmed Options | unter AB-Flag **25758** müssen auch whitespace-getrimmte Namen eindeutig sein | `poll_creation_duplicate_trimmed_options` |
| Correct Answer matched eine Option | Quiz-Correct-Answer-Name muss dem Namen einer Option entsprechen | `poll_creation_unmatched_correct_answer` |
| Selectable Count vorhanden | `selectableOptionsCount`-Bit muss gesetzt sein | `poll_creation_missing_selectable_options_count` |
| Selectable Count Range | `0 <= selectableOptionsCount <= options.size()` (bzw. `<= min(1408,12)` unter dem Bypass) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Zero-Option-/Lenient-Bypass (found Code-Pfad, Semantik inferred)

Ein lokaler Boolean (`z`), berechnet aus AB bool **37909**, nur konsultiert wenn ein interner Parse-Context-Counter gleich 1 ist, lockert die Mindest-Option-Count auf 0 und weitet die Selectable-Count-Obergrenze auf die rohe `min(1408,12)`-Grenze statt `options.size()`. Welchem Parse-Context-Wert das entspricht (normaler Receive vs. ein anderer Ingestion-Path, z. B. History Sync) wurde nicht aufgelöst; dies wird als found-but-unexplained verzeichnet, nicht als bestätigtes nutzersichtbares "optionsloser Poll"-Feature.

### 4.2 History-Sync-/Lenient-Name-Bypass

Ein separates Context-Flag (`c33371Eg0.A0W`) umgeht sowohl den Name-Length-Check als auch (äquivalent, in `F39`, §9) den Result-Snapshot-Name-Length-Check und akzeptiert den rohen String ungeprüft. Konsistent mit einem Trusted-Source-Parse-Path (z. B. lokaler History-Re-Import) statt einem normalen Network-Receive; nicht unabhängig bestätigt.

---

## 5. Image-Poll-Optionen: `pollCreationOptionImageMessage`

### 5.1 Struktur und Linking (found)

`pollCreationOptionImageMessage` (Feld 90) wrapped eine gewöhnliche hochgeladene `ImageMessage` in einer `FutureProofMessage` — das Bild ist **nicht** in `PollCreationMessage.Option` eingebettet. Jedes Options-Bild wird als eigene Child-Message gesendet, über `MessageContextInfo.messageAssociation` mit dem (noch nicht gesendeten) Poll assoziiert, Association-Type `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; dieser Enum-Wert gilt für diesen Build — ein früherer Build hatte ihn bei 7, der numerische Wert ist über Versionen hinweg nicht stabil und muss pro Release neu gelesen werden). Der sendeseitige "MediaPollAssociationProvider"-Helper (in `C20M`) zählt `message_association`-Rows für die Row-ID des Parent-Polls und Association-Type `6`; sobald die Count die Option-Count erreicht, gelten alle Options-Bilder als hochgeladen und der Client fährt fort, den Poll selbst mit `pollContentType = IMAGE` zu senden.

### 5.2 Option-Hash für Image-Optionen (inferred, aus einem früheren Build übernommen, in 2.26.41.6 nicht Zeile für Zeile neu abgeleitet)

Für reine Text-Optionen bleibt das Wire-Feld `optionHash` leer; der einzige für eine Plain-Text-Option berechnete Hash ist der lokale Lookup-Digest `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(direkt in 2.26.41.6 bestätigt, §9.1 — dies ist der Wert, gegen den Vote-Selections gematcht werden, nicht das Proto-Feld `optionHash`). Für **Image**-Optionen ist das Proto-Feld `optionHash` befüllt; ein Trace der Send-Sequenz einer früheren Version fand, dass es den Options-Namens-Hash mit dem `fileSha256` des hochgeladenen Bildes kombiniert:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Diese Formel wurde in diesem Pass nicht gegen den 2.26.41.6-Code re-verifiziert (die berechnende Klasse wurde nicht lokalisiert); sie wird als inferred übernommen und sollte vor jeglicher Verlässlichkeit nachgeprüft werden.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, Feld 121)

### 6.1 Felder (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, dieselbe Shape wie die des Votes, §7).

### 6.2 Senden (found, `F2L.ADr`)

Baut eine `Option` aus dem neuen Namen (und, für Image-Polls, deren Hash), hängt den Key des ursprünglichen Polls an und — für 1:1-Chats, wenn kein Edit-Context — resolved die Sender-Identität über die LID-/PN-Grenze auf dieselbe Weise wie die Message-Secret-Schicht für andere Add-Ons (siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 Schritt 4). Die Option wird auf dieser Ebene selbst *nicht* secret-verschlüsselt wie ein `pollUpdateMessage`: die Add-Option-Payload reist als normales Message-Feld; was in `secretEncryptedMessage` (Type `POLL_ADD_OPTION`) gewrapped wird, ist der Add-Option-Versuch als Ganzes, wenn er auf dem Message-Secret-Scheme reiten muss (§8).

### 6.3 Receive-Validierung (found, `F2L.CM7`)

| Check | Error |
|-------|-------|
| Feature-Gate: AB int **25758** muss ungleich 0 sein | Error **10017** |
| `pollCreationMessageKey` vorhanden | `poll_add_option_missing_poll_message_key` |
| `addOption` vorhanden | `poll_add_option_missing_poll_option` |
| Option-Name nicht-leer, ≤ 2500 Zeichen | `poll_add_option_invalid_option` |

Das resultierende lokale Objekt wird für den Transport secret-verschlüsselt, unter Verwendung des Use Case `Poll Add Option` (bestätigter Call in den Message-Secret-Helper mit `AnonymousClass122.POLL_ADD_OPTION` als Association-Tag). Hinzugefügte Optionen werden für das Matching mit bestehenden Optionen genauso getrackt wie Image-Poll-Optionen (Association-Type `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (Vote und Vote-Metadaten)

Volle Krypto (HKDF-Use-Case `Poll Vote`, AAD, AES-GCM, LID-/PN-Identity-Retry) ist in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7; dieser Abschnitt deckt nur ab, was der Poll-Vote-Handler (`DUA`, erweitert `F2P`) mit dem Plaintext tut.

### 7.1 Zwei Send-/Receive-Pfade (found)

AB bool **6772** wählt zwischen:
- **an** (aktuell): ein gemeinsamer Encryption-Helper (`C33285Eeb`) baut Ciphertext und `MessageKey`; der Vote wird aus einem zuvor gespeicherten `(iv, payload)`-Paar wiederholt, falls vorhanden, statt neu verschlüsselt.
- **aus** (legacy): ein Inline-Branch in `DUA` führt denselben HKDF-/AES-GCM-Call direkt aus und leitet die Ziel-Sender-Identität selbst ab (eigene LID für Votes auf den eigenen Poll des Voters, sonst die resolvte JID des Vote-Targets).

### 7.2 Vote-Payload: `PollVoteMessage` (`DPF`)

Einziges Feld `selectedOptions` **1**, repeated bytes — jeder Eintrag ist ein 32-Byte-SHA-256-Options-Namens-Digest (§9.1), kein Index. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`) validiert die entschlüsselte Selection:

| Check | Regel | Log-Tag |
|-------|------|---------|
| Selection-Größe | ≤ 12 **und** ≤ `selectableOptionsCount` des Polls (wenn > 0) | `poll_vote_invalid_options_count` |
| Hash-Shape | jeder ausgewählte Hash decodiert zu exakt 32 Bytes | `poll_vote_invalid_option_hashes` |
| Duplikate | kein wiederholter Hash in einem Vote | `poll_vote_duplicate_option_hashes` |
| Resolution | jeder ausgewählte Hash muss einem der bekannten (nicht entfernten) Options-Hashes des Polls entsprechen | liefert ein Error-Result, keine Übereinstimmung -> Vote abgelehnt |

### 7.3 End Time und Metadaten (found, `DUA.A01`)

Ein Vote, dessen `senderTimestampMs` nach dem `endTime` des Polls liegt, wird abgelehnt (`poll_update_past_end_time`); unter AB bool **2321** speist ein abgelehntes-Vote-Event zusätzlich einen Telemetrie-Counter (`N0e`). Die Vote-`metadata` (`pollNameHash`, `lastEditStanzaId`) wird beim Senden nur unter AB bool **31593** gestempelt; beim Receive wird ein fehlender/leerer Metadata-Block geloggt als `"unstamped"` (dadurch allein nicht abgelehnt), während ein *nicht übereinstimmender* Stamp (geprüft von `C32977EZa`) den Vote mit `poll_update_tc_drop` verwirft. Diese Metadaten existieren, damit ein Client erkennen kann, dass er gegen einen Poll votet, dessen Edit-Historie er noch nicht nachgezogen hat.

---

## 8. Poll-Editing (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Getragen im generischen `secretEncryptedMessage`-Wrapper (Feld 82), kein poll-spezifischer Carrier; siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4 für den Envelope, die AAD, und die Error-Code-Tabelle (`poll_edit_message_stanza_invalid`, AB int **24886**-Gate, Error **10016**). Die poll-spezifische Validierung (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) erfordert:

- die innere Message ist FMessage-Type 66 und ist sowohl vor als auch nach dem Edit ein Poll;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` und `pollType` sind zwischen dem gespeicherten Poll und dem bearbeiteten **unverändert** — nur der Frage-Text und/oder Options-Texte dürfen abweichen;
- Options-Matching: mit einem per-Chat-Flag (`EOI.A01()`, ID nicht aufgelöst) aktiviert, werden bearbeitete Optionen gegen eine gespeicherte Rename-Historie via sequenziellem (reihenfolgeerhaltendem) Match gematcht, was Umbenennungen von Optionen in place erlaubt; das exakte Verhalten des Non-Renaming-Vergleichs-Branch ist inferred (JADX lässt wieder einen Teil des Control Flow fallen — die Funktion fällt in diesem Branch in der dekompilierten Form zu `poll_edit_invalid_edits` durch, was unwahrscheinlich das echte Client-Verhalten für einen No-op-Edit ist).

Ein `"Couldn't edit poll"`-Toast-String existiert in den Resources, was bestätigt, dass Poll-Editing in diesem Build nutzersichtbar ist, nicht nur ein reservierter Protokoll-Pfad.

---

## 9. Vote-Matching-Internals

### 9.1 Option-Hash (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

Reines SHA-256 des sichtbaren Textes der Option, kein Key-Material. Dies ist der Wert, der pro lokaler Option gespeichert wird (`C33283EeZ.A02`) und der Wert, gegen den die `selectedOptions`-Einträge eines Votes gematcht werden. Jede Anwendung, die den Text der Option kennt, kann denselben Hash berechnen — die Privacy eines Votes kommt vollständig aus der Message-Secret-Verschlüsselung der Vote-Payload (§7, und [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), nicht daraus, dass der Hash unguessable wäre.

---

## 10. Vote-Privacy-/Anonymitäts-Modell

| Claim | Status |
|-------|--------|
| Votes sind end-to-end-verschlüsselt pro Voter, pro Poll (HKDF-Use-Case `Poll Vote`) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| Die ausgewählte Option wird durch einen Content-Hash identifiziert, nicht einen Index | found, §9.1 |
| `hideParticipantName` ("Hide voter names") unterdrückt die Anzeige, wer gevotet hat, in der UI | found (String `str2137`, Feld 10 von `PollCreationMessage`) |
| `hideParticipantName` versteckt den Voter vom Server oder von anderen Clients auf Protokoll-Ebene | **nicht durch hier gelesenen Code unterstützt** — der Envelope `participant`/`from` (d. h. die Identität des Voters) wird für jedes Add-On gleich ausgeliefert und authentifiziert, unabhängig von diesem Flag (siehe [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName` ist eine reine Display-Einstellung am Poll-Objekt, keine Routing- oder Encryption-Änderung |
| Der Poll-Creator kann immer bestimmen, wer gevotet hat | inferred — nichts im Vote-Decrypt-Path (§7, §9) hängt von `hideParticipantName` ab; der Client des Creators entschlüsselt jeden Vote mit der Identität des Voters als Modifier |

Kurz gesagt: WhatsApp-Polls sind für den Poll-Creator nicht anonym. "Hide voter names" kontrolliert nur, ob *andere Teilnehmer* (in der "Poll votes"-Liste) sehen, wer gevotet hat; es ändert nicht, was kryptografisch in den Vote eingebunden ist, und der Server erfährt den Vote-Inhalt in keinem Fall (die übliche E2E-Garantie, nichts spezifisches für dieses Flag).

---

## 11. Multi-Select vs. Single-Select

`selectableOptionsCount` (Feld 4) ist der einzige Mechanismus: ein Vote mit mehr Selections als diesem Wert wird abgelehnt (§7.2). Es gibt kein separates "is multi-select"-Boolean auf der Leitung — Single-Select ist einfach `selectableOptionsCount = 1`. Die Creation-UI exponiert dies als einzigen Toggle, **"Allow multiple answers"** (String `str425f`); wenn aus, wird inferred, dass der Client `selectableOptionsCount = 1` sendet, wenn an, wird inferred, dass er `selectableOptionsCount = options.size()` sendet (die UI scheint keine beliebige numerische Cap zu exponieren — inferred aus dem einzelnen Boolean-String, nicht unabhängig im Creation-UI-Code bestätigt). Das Protokoll selbst erlaubt jeden Wert `0..options.size()` (§4), also ist ein clientseitiger Wert außer 1 oder "alle Optionen" möglich, selbst wenn die Stock-UI das nicht anbietet. Quizze sind implizit Single-Select (eine Correct Answer; voter-seitiger String `"Quiz • Select one correct answer"`, `str57a5`).

Voter-seitige Labels bestätigen die zwei Modi: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: Forward-Time-Snapshot

### 12.1 Zweck (found, `F1A`)

Das Weiterleiten eines Live-Polls in einen anderen Chat leitet **nicht** den interaktiven Poll weiter. `F1A` (einer von mehreren "Forward"-Convertern, die alle dasselbe Conversion-Interface implementieren, das über Message-Types hinweg genutzt wird — der Sibling-Converter für nicht unterstützte Types wirft `"Cannot forward message of type: ..."`) konvertiert den Live-Poll (`C13J`) in ein `Dd2`-Objekt: Frage-Text, jeder Options-Name und **aktueller lokaler Vote Count**, und der Poll-/Quiz-Type. Dies wird dann als `pollResultSnapshotMessage` (Plain Poll) oder `pollResultSnapshotMessageV3` (Quiz) serialisiert und mit einem dedizierten View Holder (`DWH`) gerendert, getrennt von der interaktiven Poll-Bubble.

### 12.2 Felder (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (repeated `PollVote` — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (derselbe `PollType`-Enum wie bei Creation).

### 12.3 Validierung (found, `F39`)

Dieselbe Shape von Checks wie bei Creation: Name 1–5000 Zeichen, mindestens 2 Optionen, höchstens `min(AB 1408, 12)` Optionen, jeder Options-Name 1–2500 Zeichen. Für die **Quiz**-Variante (`V3`) werden Vote Counts beim Senden auf 0 gezwungen — ein weitergeleiteter Quiz-Snapshot gibt nie Tallies preis, nur die Frage und die Options-Liste.

---

## 13. Limits-Übersicht

| Item | Limit | Quelle |
|------|-------|--------|
| Poll-/Frage-Namenslänge | 1–5000 Zeichen | `F2N.A01`, `F39.A00` |
| Options-Namenslänge | 1–2500 Zeichen | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Option Count (Creation, Snapshot) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Selected Options pro Vote | ≤ 12 und ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| `selectableOptionsCount`-Range | 0–options.size() (0–12 unter dem Lenient-Context-Bypass, §4.1) | `F2N.A01` |
| Option-Hash-Größe (Vote-Einträge) | exakt 32 Bytes | `AbstractC33199EdC` |

---

## 14. Feature-Flags (IDs wie an Call-Sites gelesen; Namen nicht aufgelöst)

| ID | Typ | Steuert |
|----|------|---------|
| **1408** | int | server-konfigurierte maximale Poll-Options-Count, harte Client-Obergrenze 12 unabhängig vom Wert |
| **24884** | bool | honoriert `endTime` beim Receive eines Extended Polls (V5/V6); aus -> downgraded zu einem Future-Proof-Placeholder |
| **24885** | int | gated die Akzeptanz von `hideParticipantName` beim Receive (exakte Polarität nicht aufgelöst) |
| **24886** | int | Poll-Edit-Receive-Gate; 0 -> abgelehnt, Error 10016 |
| **25758** | int (truthy) | Poll-Add-Option-Receive-Gate (Error 10017); gated auch die Duplicate-Trimmed-Option-Ablehnung bei der Creation |
| **31593** | bool | stempelt `pollNameHash`/`lastEditStanzaId`-Metadaten auf einen ausgehenden Vote |
| **6772** | bool | Poll Vote: gemeinsamer Encryption-Helper (an) vs. Legacy-Inline-Path (aus) |
| **37909** | bool | erlaubt einen Poll mit null Optionen in einem bestimmten (nicht aufgelösten) Parse-Context |
| **2321** | bool | zusätzliches Telemetrie-Detail geloggt, wenn ein Vote als nach der Poll-End-Time abgelehnt wird |

Message-Secret-Layer-Flags, die ebenfalls Polls betreffen (Edit-Use-Case-Gate **17811**, Generation-Gates, etc.) sind in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16 dokumentiert und hier nicht wiederholt.

---

## 15. Baileys (nur bestätigte Fakten)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17 deckt bereits die Teile einer JavaScript-Implementierung (`baron-baileys-v2` 1.5.17) ab, die für Polls relevant sind, basierend auf `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`:

- Die HKDF-Ableitung und die Use-Case-Strings `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` stimmen exakt mit den Literalen des Android-Clients überein, einschließlich der `id\0modifier`-AAD für `Poll Vote`.
- Die AAD, der Identity-Retry (PN/LID) und das Missing-Secret-Handling (Fallback auf das rohe, unentschlüsselte Update) stimmen mit dem in diesem Report (§7) und in [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3 beschriebenen Android-Verhalten überein.
- Kein Send-seitiger Encryption-Path für `pollUpdateMessage` (oder `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) wurde in den gelesenen Dateien gefunden — d. h. diese Implementierung konnte einen eingehenden Vote entschlüsseln, aber die durchgesehenen Dateien enthielten keinen Code, um einen zu verschlüsseln und zu senden.

Nichts poll-spezifisches über das dort bereits Festgehaltene hinaus wurde in diesem Pass unabhängig re-verifiziert (kein Baileys-Code zu Poll-Creation, Option-Hash oder Poll-Edit wurde gelesen); keine weiteren Baileys-Claims werden hier gemacht.

---

## 16. Error-Fälle

| Symptom | Ursache | Fix |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | weniger als 2 oder mehr als `min(1408,12)` Optionen | Optionen im Rahmen halten |
| `poll_creation_unmatched_correct_answer` | `correctAnswer.optionName` des Quiz entspricht keinem Options-Namen | Correct Answer auf exakte Übereinstimmung setzen |
| Poll wird stillschweigend nicht angezeigt (downgraded) | `endTime`/`hideParticipantName`/`allowAddOption` auf einem V6-Poll gesetzt, aber das passende AB-Flag ist beim Empfänger aus | senderseitig, nicht per Inhalt fixbar; Receiver-Capability-Gap |
| `poll_vote_invalid_options_count` | Vote wählt mehr Optionen als `selectableOptionsCount`, oder mehr als 12 | die Cap des Polls respektieren |
| `poll_update_past_end_time` | Vote- (oder Add-Option-/Edit-)Timestamp nach `endTime` | voten, bevor der Poll schließt |
| `poll_update_tc_drop` | `pollNameHash`/`lastEditStanzaId` des Votes entspricht nicht der Sicht des Empfängers auf den Poll | Poll-Edit-Historie synchronisieren, bevor gevotet wird |
| Error **10017** bei Add-Option | AB **25758** ist beim Empfänger 0 | Receiver-Capability-Gap |
| Error **10016** bei Poll-Edit | AB **24886** ist beim Empfänger 0 | Receiver-Capability-Gap |
| `poll_add_option_past_end_time` | Option nach `endTime` hinzugefügt | Optionen hinzufügen, bevor der Poll schließt |

---

## 17. Wichtige Unterscheidungen

| Dies | Nicht das |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (`PollCreationMessage`-Typ) | `pollCreationMessageV4` (`FutureProofMessage`, wrapped eine innere Basic Poll) |
| `pollUpdateMessage` (Vote, oder Vote-Metadaten) | `secretEncryptedMessage` mit `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` (Poll-Edit / Add-Option) |
| `pollAddOptionMessage` (die neue Options-Payload) | `secretEncryptedMessage`-Wrapper, der sie über die Leitung trägt, wenn Message-Secret-gebunden |
| `pollResultSnapshotMessage`/V3 (statisch, weitergeleitet) | der Live-interaktive Poll (`pollCreationMessage*`) |
| Options-Selection via SHA-256(Name)-Hash | Selection via Index — WhatsApp-Polls selektieren nie über Position |
| `hideParticipantName` (UI-Display-Einstellung) | Vote-Sender-Anonymität (existiert nicht; der Creator resolved den Voter immer) |
| `selectableOptionsCount` (das einzige Multi-/Single-Select-Signal) | ein separates "is multi-select"-Boolean (existiert nicht) |

---

## 18. Vollständiger Flow (Creation, Image-Option, Vote, Forward)

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

## 19. Unbekannte Punkte

| Item | Status |
|------|-------|
| Exakte Polarität von AB **24885** (hideParticipantName Accept/Downgrade) | dekompilierte Branch-Struktur unvollständig |
| Image-Option-Hash-Formel (`nameHash`+`imageHash`) für 2.26.41.6 | aus einem früheren Build übernommen, in diesem Build-Code nicht neu abgeleitet |
| AB-Flag-ID hinter dem per-Chat-"Ordered Option Rename"-Toggle, genutzt im Poll-Edit-Matching (`EOI.A01()`) | ID nicht aufgelöst |
| Non-Renaming-Branch des Poll-Edit-Options-Vergleichs | Decompiler lässt einen Teil des Control Flow fallen; die wörtliche dekompilierte Form fällt immer zu `poll_edit_invalid_edits` durch, was unwahrscheinlich das echte Verhalten für einen No-op-Edit ist |
| Parse-Context-Wert (`c33371Eg0.A00 == 1`), der den Zero-Option-Bypass aktiviert (AB **37909**) | nicht identifiziert (History Sync vs. ein anderer Path) |
| Ob die Stock-Creation-UI `selectableOptionsCount`-Werte außer 1 oder "alle Optionen" senden kann | inferred aus einem einzelnen Boolean-Toggle-String, nicht gegen UI-Code bestätigt |
| Stabilität des numerischen Werts von `MEDIA_POLL` über Versionen hinweg | gefunden als 6 in 2.26.41.6; ein früherer Build nutzte einen anderen Wert, also nicht über Versionen hinweg hardcoden |
