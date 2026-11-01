<!-- src-sha1: b9a264b89fe2f15a6ff3587c9bc5a6b3a47e10c0 -->
# WhatsApp View-Once — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** `viewOnceMessage` / `viewOnceMessageV2` / `viewOnceMessageV2Extension`-Wrapper vs. das inline `viewOnce`-Feld auf `ImageMessage` / `VideoMessage` / `AudioMessage` / `ExtendedTextMessage`, der generische Message-Wrapper-Unwrap-Mechanismus, geteilt mit Disappearing Messages, Nachrichtentypen und das gemeinsame Marker-Interface, clientseitige Durchsetzung (Screenshot-/Screen-Recording-Blockade, Forward-/Share-/Save-Einschränkung, Sender-Self-View-Blockade, Quoted-Media-Stripping), lokaler Storage und State Machine (`message_view_once_media`, Deletion Job), Media-Key-Lifecycle (verlinkt, nicht wiederholt), der `unavailable[type="view_once"]`-Wire-Case und Cross-Device Read/Write Tokens, Feature-Flags, Baileys-Vergleich

---

## 1. Was es ist

View-Once ist ein Attribut pro Nachricht, kein eigener Nachrichtentyp: jedes Bild, Video, jede Sprachnachricht oder (in aktuellen Builds) Text kann so markiert werden, dass der Client des Empfängers die lokale Kopie nach einmaligem Öffnen löscht; zusätzlich blockiert der Client Screenshots/Screen-Recording und blendet Forward/Share/Save aus, solange der Inhalt offen ist. Alle Aussagen stammen aus statischer Analyse des dekompilierten APK; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = im Code gelesen, **inferred** = aus dem Code abgeleitet, **unknown** = nicht aufgelöst. Namen wurden in 2.26.41.6 anhand stabiler Strings und Log-Tags neu aufgelöst (`AppDataManager/contributeMetaAppData`, `ConversationRowViewOnceMedia/`, `EphemeralUpdateRunnable/`, `ViewOnceMessageStore/`, UI-String-IDs).

| Entität | Name in 2.26.41.6 | Rolle |
|--------|-----------------|------|
| Wrapper-Nachricht (ein Feld, `message` **1**) | `BD2` | Body von `viewOnceMessage` **37**, `viewOnceMessageV2` **55**, `viewOnceMessageV2Extension` **59** auf `Message` (`C30628DTw`) |
| Inline-Flag pro Medientyp | `ImageMessage.viewOnce` **25**, `VideoMessage.viewOnce` **20**, `AudioMessage.viewOnce` **21**, `ExtendedTextMessage.viewOnce` **30** | direkt auf der Medien-/Textnachricht gesetzt, kein Wrapper |
| Wrapper-vs-Inline-Switch | Flag **8784** | an: nur Inline-Feld; aus: Wrapper + Inline-Feld beide gesetzt (6.3) |
| View-Once-Bild-Handler | `C34670F2r` ("FMessageViewOnceImageProtobuf") | baut/liest `DdP`, Nachrichtentyp **42** |
| View-Once-Video-Handler | `C34671F2s` ("FMessageViewOnceVideoProtobuf") | baut/liest `C30972DdZ`, Nachrichtentyp **43** |
| View-Once-Text-Handler | `F33` ("FMessageViewOnceTextProtobuf") | baut/liest `C31208Dhd`, Nachrichtentyp **78** |
| View-Once-Audio-Handler | `C34669F2q` ("FMessageViewOnceAudioProtobuf") | baut/liest `C30963DdH`, Nachrichtentyp **82** |
| Marker-Interface | `InterfaceC24513Ahd` | implementiert von allen vier FMessage-Klassen oben; genutzt, um UI-/Menü-Verhalten generisch zu steuern |
| Lokale State-Tabelle | `message_view_once_media` | Spalten `message_row_id`, `state` |
| State-Accessor | `C199158dT` ("ViewOnceMessageStore") | get/insert/update auf `state` |
| Deletion Job | `EphemeralUpdateRunnable` (anonyme Klasse in `C199218dZ`), Job-Typ **3** | "`ViewOnceMessageStore/getViewOnceMessagesToDelete`" |
| Screen-Capture-Block-Helper | `C66572s0` | `window.addFlags(8192)` = `FLAG_SECURE` |
| View-Once-Gate für den Media-Viewer | `C1ZB.A0O(i)` | `i == 42 \|\| i == 43` |
| Dedizierter Viewer (Text/Audio) | `ViewOnceViewerActivity`, `ViewOnceTextFragment`, `ViewOnceAudioFragment` | eigene Activity, immer `FLAG_SECURE` |
| Geteilter Viewer (Bild/Video) | `MediaViewFragment` / `MediaViewMenu` | normaler Media-Viewer, `FLAG_SECURE` nur wenn `C1ZB.A0O` true ist |
| Education Sheets | `ViewOnceNuxBottomSheet`, `ViewOnceSecondaryNuxBottomSheet` | einmaliger Erklärtext für Sender/Empfänger |
| Quoted-Media-Stripper | `F43` ("QuotedMediaCleanupSerializationPostProcessor") | entfernt Media-Bytes aus dem Zitat einer View-Once-Nachricht, Flag **25572** |

---

## 2. Proto-Markierung

### 2.1 Inline-Feld (found)

```text
ImageMessage.viewOnce         = 25  (bool)
VideoMessage.viewOnce         = 20  (bool)
AudioMessage.viewOnce         = 21  (bool)
ExtendedTextMessage.viewOnce  = 30  (bool, VIEW_ONCE_FIELD_NUMBER)
```

Jedes ist ein einfaches Boolean auf der normalen Medien-/Textnachricht; kein separater Container ist nötig, um es zu tragen. Bestätigt durch Lesen der generierten Feldtabellen von `C30612DTg` (Image), `C30614DTi` (Video), `DTX` (Audio), `C30613DTh` (ExtendedText).

### 2.2 Wrapper-Nachricht (found)

`viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**) und `viewOnceMessageV2Extension` (**59**) auf `Message` sind alle vom Typ `BD2`, und `BD2` hat genau ein Feld, `message` **1**, selbst eine `Message`. Alle drei Feldnamen dekompilieren zur identischen Klasse — es ist dieselbe Wrapper-Form, dreimal für drei Protokollgenerationen verwendet:

```java
public final class BD2 extends GeneratedMessageLite {
    public static final int MESSAGE_FIELD_NUMBER = 1;
    public C30628DTw message_;   // a full nested Message
}
```

### 2.3 Inline vs. Wrapper: Flag 8784 (found)

Jeder Per-Type-Handler (`C34670F2r` Bild, `C34671F2s` Video, `F33` Text, `C34669F2q` Audio) baut dasselbe zweimal und wählt eins über ein Flag:

```java
boolean zA15 = this.A00.A15(8784);
...
if (zA15) {
    dp5.A0R(c30612DTg);                 // inline viewOnce=true directly on the outer Message
    return;
}
dp5A0f.A0R(c30612DTg);                  // same media message, but inside the BD2 wrapper
BD2 bd2A0Q = ...;
c30628DTwA0j.viewOnceMessageV2_ = bd2A0Q;
```

Mit dem Flag an sendet 2.26.41.6 nie einen Wrapper für eine lokal verfasste View-Once-Nachricht; die empfangsseitigen `CM7`-Handler (Receive) in denselben Klassen schauen nur auf das Inline-Flag (`c30612DTg.bitField0_ & ... && c30612DTg.viewOnce_`), nicht auf die Wrapper-Felder — das Auspacken eines Wrappers bis zur Inline-Form ist ein separater, generischer Schritt (2.4).

### 2.4 Generisches Wrapper-Unwrap (found)

Eine statische Tabelle (`AbstractC33204EdH.A00`, 35 Einträge) paart ein "hat diesen Wrapper"-Prädikat mit einem "hol die innere `Message`"-Extractor für jeden Forward-Compatibility-Wrapper, den der Client kennt, einschließlich `ephemeralMessage` (Disappearing-Messages-Wrapper), `viewOnceMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `documentWithCaptionMessage`, `botInvokeMessage`, `groupStatusMessage` und weitere. `C34748F5r` (Native-Flow-/`<biz>`-Validierung, `AbstractC33204EdH.A00`) rekursiert durch diese Tabelle bis Tiefe 10, um den klassifizierbaren Inhalt zu finden, unabhängig davon, wie viele Wrapper ihn umgeben:

```java
for (EQR eqr : AbstractC33204EdH.A00) {
    if (hasWrapper(c30628DTw, eqr) &&
        A00(..., unwrap(c30628DTw, eqr), i + 1) != C02U.A00) {
        return result;
    }
}
```

`ephemeralMessage` und die drei View-Once-Wrapper sind Peer-Einträge in dieser Tabelle — strukturell derselbe Mechanismus, sodass eine View-Once-Nachricht im Prinzip in einem Disappearing-Messages-Wrapper verschachtelt sein kann, oder daneben (Abschnitt 7). Das spiegelt Baileys' eigene `getFutureProofMessage()`-Liste in `message-inspect.js`, die dieselbe Menge an Wrapper-Feldnamen aufzählt.

---

## 3. Nachrichtentypen und das Marker-Interface

| Typ | Media-Klasse | Handler | Fragment/Activity |
|------|-------------|---------|--------------------|
| **42** | `DdP` (Bild) | `C34670F2r` | `MediaViewFragment` (geteilter Bild/Video-Viewer) |
| **43** | `C30972DdZ` (Video) | `C34671F2s` | `MediaViewFragment` |
| **78** | `C31208Dhd` (Text) | `F33` | `ViewOnceTextFragment` innerhalb `ViewOnceViewerActivity` |
| **82** | `C30963DdH` (Audio/PTT) | `C34669F2q` | `ViewOnceAudioFragment` innerhalb `ViewOnceViewerActivity` |

Alle vier Klassen implementieren `InterfaceC24513Ahd`, den einen Marker, auf den der Rest des Clients testet ("ist dies eine View-Once-Nachricht") statt die Vier-Typen-Prüfung überall zu wiederholen. `C1ZB.A0O(i)` (`i==42 || i==43`) ist der engere Bild/Video-only-Test, der dort verwendet wird, wo das geteilte `MediaViewFragment` View-Once-Bild/Video von allem anderen unterscheiden muss, das es auch rendert.

Die Typmenge `{42,43,78,82}` taucht wörtlich an mehreren unabhängigen Call-Sites in diesem Build auf: dem `<meta view_once="true">`-Producer (Abschnitt 6.1), der Typnamen-Lookup-Tabelle (`AbstractC32316E9h`: `"viewOnceImage"`=42, `"viewOnceVideo"`=43, `"viewOnceAudio"`=82) und `C1ZB`-Helper-Methoden für Save-/Display-Gating.

---

## 4. Clientseitige Durchsetzung

### 4.1 Screenshot-/Screen-Recording-Blockade (found)

`C66572s0.A00(Window)` ist ein einzeiliger Helper:

```java
public final void A00(Window window) {
    if (window != null) {
        window.addFlags(8192);   // WindowManager.LayoutParams.FLAG_SECURE
    }
}
```

`8192` (`0x2000`) ist der rohe Wert von `FLAG_SECURE`; die dekompilierten Sources nutzen die numerische Konstante, nicht den symbolischen Namen, also findet eine Textsuche nach `FLAG_SECURE` nichts — die Konstante muss per Wert abgeglichen werden. `FLAG_SECURE` schwärzt das Fenster in Screenshots, im Recent-Apps-Thumbnail und während Screen-Recording/Casting auf OS-Ebene; das ist keine WhatsApp-spezifische Erkennung, sondern das Standard-Android-Secure-Window-Flag.

Zwei Call-Sites:

| Call-Site | Bedingung | Scope |
|-----------|-----------|-------|
| `MediaViewFragment` (generischer Media-Viewer) | `C1ZB.A0O(i)` d. h. `i==42 \|\| i==43` | nur angewendet, wenn die angezeigte Nachricht View-Once-Bild/Video ist; sonst wird der normale Media-Viewer nicht gesichert |
| `ViewOnceViewerActivity.onCreate` | unbedingt | diese Activity wird nur für View-Once-Text (78) oder -Audio (82) gestartet, also ist jede ihrer Instanzen gesichert |

Netto-Effekt: Das Öffnen eines der vier View-Once-Typen setzt `FLAG_SECURE` auf dem Host-Fenster, solange es offen ist; das Schließen des Viewers (Fragment/Activity wird zerstört) entfernt das Fenster und damit das Flag. Kein Hinweis auf einen Screenshot-*Erkennungs*-Mechanismus (z. B. ein `FileObserver` auf `Pictures/Screenshots` oder ein `MediaStore`-Content-Observer) wurde gefunden; der Schutz ist OS-seitige Prävention, keine nachträgliche Erkennung.

### 4.2 Kein Forward / Share / Save (found)

`ViewOnceViewerActivity.onCreateOptionsMenu` baut genau vier Menüeinträge — Info, Transcribe (nur Audio), Delete, Report — und keine weiteren; es gibt in diesem Menü überhaupt keinen Forward-, Share-, Save- oder Copy-Eintrag. Im geteilten `MediaViewMenu` (für View-Once-Bild/Video über den normalen Media-Viewer) werden mehrere boolesche Menü-Sichtbarkeits-Locals mit einem expliziten `instanceof InterfaceC24513Ahd`-Ausschluss berechnet, z. B.:

```java
if (i6 == 2 && !c36911dGA1I21.element && ... && !(abstractC34931a2 instanceof InterfaceC24513Ahd)) {
    z14 = !C0DZ.A0X(c0df);     // forward-related menu flag, left false (hidden) for view-once
}
...
z16 = abstractC34931a2 instanceof InterfaceC24513Ahd;
if (!z16) {
    z17 = !AbstractC24760wu.A07(c0df);   // another gated flag, defaults false for view-once
}
```

Da jedes Flag standardmäßig `false` ist und nur im Nicht-View-Once-Zweig einen nutzbaren Wert zugewiesen bekommt, bleiben die entsprechenden Menüeinträge für `InterfaceC24513Ahd`-Nachrichten versteckt. Die Einschränkung wird in der UI-Schicht durchgesetzt (Menü-Konstruktion), nicht durch Entfernen der zugrunde liegenden Media vom lokalen Speicher, bevor der Viewer sie öffnet.

### 4.3 Sender kann eigene Media nicht erneut öffnen (found)

`DYM` (Conversation-Row-Komponente für View-Once-Media) behauptet:

```java
C00K.A0C(false, "ConversationRowViewOnceMedia/senders can not view their own media");
```

auf dem Pfad, den die eigene View-Once-Row eines Senders zum erneuten Öffnen des Inhalts nutzen würde — d. h. die Invariante "ein Sender bekommt nie einen funktionierenden Open-Handler für seine eigene View-Once-Nachricht" wird als harte Assertion durchgesetzt, nicht als bedingtes UI-Hide.

### 4.4 Zitieren entfernt die Media (found)

`F43` ("QuotedMediaCleanupSerializationPostProcessor", gesteuert über Flag **25572**) schreibt die `imageMessage` / `videoMessage` / `documentMessage` / `audioMessage` einer zitierten Nachricht um, bevor sie als `contextInfo.quotedMessage` an eine *neue* ausgehende Nachricht angehängt wird: Es kopiert Nicht-Inhalts-Felder (Mimetype, Caption, Dimensionen, Thumbnail, das `viewOnce`-Bit selbst), entfernt aber `mediaKey`, `fileSha256`/`fileEncSha256` und `directPath`. Das Zitieren einer View-Once-Nachricht kann den originalen Media-Key daher nicht in eine Antwort einschmuggeln; das Zitat zeigt nur Metadaten.

### 4.5 Education Sheets (found)

`ViewOnceNuxBottomSheet` wird einmal pro Rolle (Sender/Empfänger — getrackt über UXCam-Keys `ephemeral_view_once` / `ephemeral_view_once_receiver`) beim ersten Senden/Empfangen einer View-Once-Nachricht jeder Seite gezeigt, mit Text direkt aus `res/values/strings.xml`:

| String-ID | Text |
|-----------|------|
| `str4e56` | "View once messages give you more privacy" |
| `str4e55` | "For added privacy, the recipient can't share, forward, copy, save, or take a screenshot of it." |
| `str4e68` / `str4e5d` / `str4e7b` | Per-Type-Varianten: "This is a view once photo/message/video so it's more private" |
| `str4e69` / `str4e6a` / `str4e5c` | "Also, you can't share, forward, copy, save, or take a screenshot of it." |
| `str4e63` / `str4e64` | "View once photo, expired" / "View once photo, opened" (gleiches Muster für Video/Audio/Text) |

Die "expired"/"opened"-String-Paare pro Typ (Bild, Video, Audio, Text) sind die nutzersichtbare Seite der lokalen `state`-Spalte (Abschnitt 5).

---

## 5. Lokaler Storage und State Machine

### 5.1 Tabelle (found, `C199158dT`)

```sql
-- message_view_once_media(message_row_id, state)
SELECT state FROM message_view_once_media WHERE message_row_id = ?     -- GET_VIEW_ONCE_STATE_BY_MESSAGE_ROW_ID_SQL
UPDATE message_view_once_media SET state = ? WHERE message_row_id = ?  -- UPDATE_VIEW_ONCE_SQL
INSERT INTO message_view_once_media (message_row_id, state) VALUES (?, ?)  -- INSERT_VIEW_ONCE_SQL
```

Eine Row pro View-Once-Nachricht, unabhängig von den generischen Tabellen `message` und `message_media` (die weiterhin die Row-/Media-File-Buchhaltung halten, geteilt mit gewöhnlichen Nachrichten).

### 5.2 States (found Row-Werte, Namenszuordnung teilweise inferred)

| Übergang | Code | Trigger |
|------------|------|---------|
| Row erstellt | `A02` (`BDk()` auf der FMessage, Wert bei Erstellung) | Nachricht gesendet/empfangen; Initialwert ist, was die FMessage meldet — konsistent mit "0 = ungeöffnet", aber keine benannte Konstante gefunden |
| Als geöffnet markiert | `A03`: `state = 1` | Nachrichtenstatus (`B6u()`) erreicht **8**, **9** oder **10** (Download-/Read-bezogene Statuscodes; exakte Namen nicht aufgelöst) |
| Gelesen ohne Row | Fallback `i = 2` in `A01` | `GET_VIEW_ONCE_STATE...` liefert keine Row; der Code behandelt dies, als sei die Nachricht bereits abgelaufen |

Also: **1** = bestätigt "opened" (benannte Call-Site); **2** ist der No-Record-/Expired-Fallback; ein Initial-/"unopened"-Wert existiert, wurde aber in diesem Build nicht auf ein Literal festgenagelt.

### 5.3 Löschung (found)

Dieselbe `EphemeralUpdateRunnable`-Klasse, die Disappearing Messages (Job-Typ 0, Tabelle `message_ephemeral`) und Message-Secret-Add-ons (Job-Typ 4, Tabelle `message_add_on`) ablaufen lässt, führt auch Job-Typ **3** aus, geloggt als `ViewOnceMessageStore/getViewOnceMessagesToDelete`:

```sql
SELECT message.* FROM message_view_once_media AS view_once
  JOIN message AS message ON view_once.message_row_id = message._id
  JOIN message_media AS message_media ON message_media.message_row_id = message._id
WHERE message_media.file_size IS NOT NULL
  AND message_media.file_size IS NOT 0
  AND message.from_me = 0
  AND view_once.state IN (1, 2)
LIMIT ?
```
<sub>(vereinfachte Spaltenliste; `GET_EXPIRED_VIEW_ONCE_MESSAGES_SQL`)</sub>

Wörtlich gelesen: Der Job zielt nur auf *empfangene* View-Once-Media (`from_me = 0`), die noch eine Datei auf der Platte hat (`file_size` vorhanden und ungleich null) und deren State `1` (opened) oder `2` (derselbe Fallback-Wert wie "no row"/expired) ist. Der Job gibt die lokale Mediendatei für passende Rows frei; er löscht nicht die Nachrichten-Row selbst (die Row bleibt bestehen und trägt das "opened"/"expired"-UI-Label aus 4.5). **Gesendete** View-Once-Media (`from_me = 1`) wird von dieser Query nicht erfasst — konsistent damit, dass der Sender sie nie erneut öffnen darf (4.3), aber eine entsprechende Cleanup-Logik für die eigene Kopie des Senders wurde nicht gefunden; deren Retention/Löschung ist **unknown**.

### 5.4 Media-Key/Crypto-Lifecycle (verlinkt, nicht wiederholt)

View-Once-Media nutzt durchgängig die normale Media-Pipeline — dieselbe `MmsType`-Tabelle, dieselbe HKDF-80-Schlüsselableitung, derselbe AES-CBC+HMAC-Envelope, dieselben Upload-/Download-URLs; es gibt keine separate "View-Once"-`MmsType`-Row. Siehe [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) Abschnitte 3-5 für die Crypto und Abschnitt 12 dieses Reports für die View-Once-spezifischen Notizen (Sender-cannot-view-Assertion, Thumbnail-Löschungs-Log-Tag). Ob der Server das hochgeladene Objekt nach dem ersten Download unabhängig löscht oder markiert, ist aus dieser statischen Analyse **unknown** — die clientseitige Garantie ist die lokale File-Löschung in 5.3, kein Server-Vertrag, den der Client beobachten kann.

---

## 6. "View once unavailable" / Cross-Device-Signalisierung

### 6.1 `unavailable[type="view_once"]`-Stanza (Korrektur zu einer früheren Research-Notiz)

Eine frühere Research-Notiz (2.26.35.2) verfolgte das ausgehende Literal-Paar `view_once`/`true` zu einer Methode, geloggt als `AppDataManager/contributeMetaAppData`, und ließ offen, ob diese Methode einen kompletten Node baute oder nur Metadaten beisteuerte. In 2.26.41.6 ist derselbe Log-Tag (`"AppDataManager/contributeMetaAppData type="`) **nicht** der `view_once`-Producer: er gehört zu einem anderen, unverbundenen Zweig von `F6K` (dem generischen `<meta>`-Node-Builder), der ein freies `appdata`-Attribut für Bot-/Add-on-Nachrichten einstempelt (`FZF.AVN()`). Das tatsächliche `view_once`-Attribut in diesem Build wird einige Zeilen vorher in derselben `F6K`-Methode gebaut, unabhängig von dieser Log-Zeile:

```java
if (c08j2.A15(11282) && (i == 42 || i == 43 || i == 82 || i == 78)) {
    EZV.A00(ezv, "view_once", "true");
}
```

Das erzeugt `<meta view_once="true">` als Child/Attribut des `<meta>`-Node der ausgehenden `<message>`-Stanza (nicht das `<unavailable type="view_once">`-Child, das die Research-Notiz und Baileys/whatsmeow beschreiben). Beides kann zugleich wahr sein: `<meta view_once="true">` ist der sendereigene Stanza-Marker, dass diese Nachricht View-Once ist; `<unavailable type="view_once">` ist ein *anderer* Node, nur auf der Empfangs-/Web-Seite beobachtet, wenn keine Chiffretext an dieses Device gefanout wurde. Statische Analyse der Android-APK (die hier keine Web-/Linked-Device-Rolle hat) kann nicht zeigen, welche Seite diesen zweiten Node baut; dieser Report ändert nicht die frühere mittel-hoch-konfidente Schlussfolgerung, dass er serverseitig produziert oder aus dem Fanout-State des Senders server-normalisiert wird. Baileys bestätigt die Empfangsseite mit einem *spezifischeren* Literal als dem generischen: `src/Socket/messages-recv.js` prüft `unavailableType === 'view_once_unavailable_fanout'` (neben `bot_unavailable_fanout`, `hosted_unavailable_fanout`), um zu entscheiden, ob eine On-Demand-Placeholder-Resend-Anfrage übersprungen wird, während `src/Utils/decode-wa-message.js` separat das einfache `attrs.type === 'view_once'` auf einem `<unavailable>`-Child matcht, um `isViewOnce`/`StubType.VIEWED_ONCE` zu setzen. Das sind zwei verschiedene Codepfade für das, was die frühere Research-Notiz als einen String behandelte.

### 6.2 `view_once="read"`/`"write"`-Tokens (found Token, Consumer unresolved)

Die Literale `view_once_read` und `view_once_write` sind in der Binary-Stanza-Dictionary-Tabelle des Android-Clients präsent (`AbstractC40911lb`, die feste Wire-Vokabular-Liste für Compact-Token-Encoding) — dieselbe Art Tabelle, die `unavailable`, `enc`, `polltype` usw. trägt. Baileys' `decode-wa-message.js` liest einen `attrs.view_once`-Wert von `'read'` oder `'write'` auf `<enc>`-Level-Attributen und speichert ihn als `fullMessage.viewOnceType`. Zusammengenommen ist das konsistent mit einem Per-eigenes-Device-"bereits geöffnet"-Sync-Signal, das mit dem Nachrichten-Envelope mitreist — vermutlich wie andere Linked Devices eines Nutzers erfahren, dass der View-Once-Inhalt auf einem Device bereits geöffnet wurde — aber keine Android-Call-Site, die dieses Attribut *setzt* oder *konsumiert*, wurde in 2.26.41.6 gefunden; hier festgehalten als gefundenes Wire-Token mit ungelöstem Android-Consumer (**unknown**).

---

## 7. Zusammenspiel mit Disappearing Messages

View-Once und Disappearing Messages (Per-Chat-Nachrichten-TTL) sind unabhängige, orthogonale Flags, die beide auf derselben Nachricht gesetzt sein können:

- Sie nutzen separate lokale Tabellen: `message_ephemeral` (Disappearing, nach `expire_timestamp` indiziert) vs. `message_view_once_media` (View-Once, nach `state` indiziert).
- Beide werden von Jobs auf demselben `EphemeralUpdateRunnable`-Worker abgelaufen (Job-Typ 0 für Disappearing, Job-Typ 3 für View-Once, Job-Typ 4 für Message-Secret-Add-ons) — ein gemeinsamer Scheduling-/Ausführungspfad, aber getrennte State- und SQL-Logik pro Feature.
- Auf Proto-Ebene ist `ephemeralMessage` ein Peer-Eintrag in genau derselben generischen Wrapper-Unwrap-Tabelle wie die drei View-Once-Wrapper (Abschnitt 2.4): eine Nachricht kann als `ephemeralMessage{message: viewOnceMessage{message: imageMessage{...}}}` oder in umgekehrter Verschachtelung gewrappt sein, und das rekursive Unwrap in `C34748F5r` sowie Baileys' `getFutureProofMessage()` laufen beide Reihenfolgen durch.
- Disappearing-Message-Löschung entfernt die gesamte Nachricht nach der Chat-TTL, unabhängig davon, ob sie geöffnet wurde; View-Once-Löschung entfernt nur die *Mediendatei*, sobald die Nachricht geöffnet wurde (oder in den State-2-Fallback fällt), und lässt die Nachrichten-Row (jetzt als "opened"/"expired" angezeigt) bestehen. Ein View-Once-Foto in einem Disappearing-Chat unterliegt daher zusätzlich zu seiner eigenen One-Open-then-Wipe-Media-Regel der TTL des Chats.

---

## 8. Feature-Flags (IDs wie an Call-Sites gelesen; Namen unresolved)

| ID | Typ | Steuert |
|----|------|------|
| **8784** | bool | View-Once-Media mit nur dem Inline-Feld senden (an) vs. Inline-Feld + Legacy-Wrapper (aus) |
| **11282** | bool | `<meta view_once="true">` für Nachrichtentypen 42/43/78/82 emittieren |
| **25572** | bool | Media-Felder aus einer zitierten View-Once-Nachricht entfernen (`F43`) |

(Flags, die die geteilte Media-Pipeline steuern — HKDF, Upload/Download, Retry — sind in [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) Abschnitt 16 gelistet und hier nicht wiederholt.)

---

## 9. Baileys (`baron-baileys-v2`, Source gelesen, nichts getestet)

| Thema | Baileys | Android 2.26.41.6 |
|-------|---------|---------------------|
| Send-seitige Markierung | wrappt immer: `{ viewOnceMessage \| viewOnceMessageV2 \| viewOnceMessageV2Extension: { message } }` je nach `viewOnceVersion`-Option (`src/Utils/messages.js`) | wrappt nur, wenn Flag 8784 aus ist; der Default (8784 an) setzt das Inline-`viewOnce`-Feld direkt auf der Medien-/Textnachricht, kein Wrapper |
| Wrapper auch für Nicht-Media genutzt | `viewOnceMessage` wird zusätzlich genutzt, um `buttonsMessage`/`templateMessage`/`listMessage`/`interactiveMessage`-Sends futureproof zu machen (`src/Socket/messages-send.js`, `requiresViewOnce`) — unabhängig von der Self-Destruct-Privacy-Funktion | derselbe Wrapper-Typ (`BD2`) wird von der generischen Unwrap-Tabelle für `botInvokeMessage`, `editedMessage` usw. wiederverwendet — dieselbe "generische Envelope"-Rolle unabhängig bestätigt (2.4) |
| Generische Unwrap-Liste | `getFutureProofMessage()` in `message-inspect.js`: `ephemeralMessage`, `viewOnceMessage`, `documentWithCaptionMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `groupMentionedMessage`, `botInvokeMessage`, ... | `AbstractC33204EdH.A00` (35 Einträge) — dieselben Wrapper-Feldnamen |
| `unavailable`-Receive-Handling | zwei verschiedene Literal-Checks: `attrs.type === 'view_once'` (setzt `isViewOnce`) und `unavailableType === 'view_once_unavailable_fanout'` (überspringt Placeholder-Resend) | nur clientseitiger `<meta view_once>`-Producer (6.1); der `<unavailable>`-Node selbst ist Receive-Pfad/Web-seitig, hier nicht verfolgt |
| `view_once` Read/Write-Token | dekodiert `attrs.view_once === 'read' \| 'write'` auf `<enc>`-Attributen in `viewOnceType` | Tokens im Wire-Dictionary des Clients präsent; kein Android-Consumer gefunden (6.2) |
| Analytics | `WAM/constants.js`: `viewOnceMessagesSent` (16), `viewOnceMessagesReceived` (17), `viewOnceMessagesOpened` (18) | in diesem Report nicht verfolgt; siehe [WA_WAM_ANALYTICS.md](./WA_WAM_ANALYTICS.md) für den WAM-Mechanismus im Allgemeinen |
| Screenshot-/Forward-Blockade | nicht implementiert — Baileys ist eine Backend-Library ohne UI, kein Window, kein Menü zum Einschränken | `FLAG_SECURE` + Menüeintrag-Omission (4.1-4.2); außerhalb einer Android-UI nicht reproduzierbar |
| Lokale Löschung nach Öffnen | nicht anwendbar — Baileys hat keine persistente Media-Viewer-State-Machine; Caller sind selbst für ihren Storage verantwortlich | `message_view_once_media.state` + `EphemeralUpdateRunnable`-Job-Typ 3 (5.1-5.3) |

---

## 10. Fehlerfälle / Gotchas

| Symptom | Ursache | Hinweis |
|---------|---------|------|
| View-Once-Media ist verschwunden, wenn der Viewer erneut geöffnet wird | normal: `state` hat 1 (opened) erreicht oder die Row fehlte (Fallback 2), und der Deletion Job hat die Datei bereits freigegeben | kein Bug; dies ist das beabsichtigte One-Open-then-Wipe-Verhalten |
| Eigene View-Once-Media des Senders öffnet sich nie aus der Conversation Row | `DYM`-Hard-Assertion `senders can not view their own media` | per Design, kein Fehlerpfad |
| Zitierte View-Once-Antwort zeigt keine Media | `F43` entfernt `mediaKey`/Hashes/`directPath` aus dem Zitat, behält nur Caption/Dimensionen/Thumbnail/das `viewOnce`-Bit | erwartet; Zitieren kann nicht genutzt werden, um die Media zu re-extrahieren |
| View-Once-Bild/Video-Viewer lässt auf manchen Builds Screenshots durch, auf anderen nicht | `FLAG_SECURE` wird nur über `C1ZB.A0O(i)` (Typen 42/43) angewendet; jede Regression in diesem Gate (z. B. ein Codepfad, der den geteilten Viewer für ein View-Once-Item öffnet, ohne durch das gegatete Call geht) würde den Schutz stillschweigend entfernen | Gate-Position dokumentiert bei `MediaViewFragment` Zeile ~3120 (dieser Build) |
| Ein Linked Device zeigt eine View-Once-Nachricht als bereits geöffnet an, ohne dass der Nutzer sie dort geöffnet hat | plausibler Cross-Device-Sync über `view_once="read"/"write"`-Wire-Tokens (6.2) | Mechanismus auf der Android-Seite nicht bestätigt; als unknown festgehalten |

---

## 11. Wichtige Unterscheidungen

| Dies | Nicht dies |
|------|------|
| `viewOnce`-Boolean-Feld auf `ImageMessage`/`VideoMessage`/`AudioMessage`/`ExtendedTextMessage` | der Legacy-`viewOnceMessage`/`viewOnceMessageV2`/`viewOnceMessageV2Extension`-Wrapper um dieselbe Nachricht |
| `viewOnceMessage` (`BD2`) für Privacy (Self-Destruct) genutzt | derselbe `BD2`-Wrapper-Typ, wiederverwendet als generische Futureproofing-Envelope für Buttons-/Template-/List-/Interactive-Sends (Baileys) und für `botInvokeMessage`/`editedMessage` auf Android |
| `message_view_once_media.state` (lokal, pro Nachricht, Open-/Expire-Tracking) | `message_ephemeral.expire_timestamp` (lokal, pro Nachricht, Disappearing-Chat-TTL) — unabhängige Tabellen, unabhängige Jobs, derselbe Runner |
| `<meta view_once="true">` — senderseitiger Classifier auf der ausgehenden Stanza | `<unavailable type="view_once">` — ein anderer Node, gesehen auf der Empfangs-/Web-Seite, wenn keine Chiffretext dieses Device erreichte |
| `FLAG_SECURE` auf dem Viewer-Window (Screenshot-/Recording-*Prävention*) | ein Screenshot-*Erkennungs*-Callback — kein solcher Mechanismus gefunden |
| Löschung der lokalen Media-*Datei* nach dem Öffnen | Löschung der Nachrichten-*Row* — die Row bleibt bestehen, gelabelt "opened"/"expired" |
| View-Once (Media wird nach einmaligem Öffnen gewiped) | Disappearing Messages (gesamte Nachricht wird nach einer Chat-Level-TTL entfernt) — orthogonal, kombinierbar |

---

## 12. Vollständiger Flow (View-Once-Foto, 1:1-Chat)

```
[Sender]
   │ pick photo, mark "view once" in composer
   │ ImageMessage.viewOnce = true          (flag 8784 on: inline only)
   │ upload via normal media pipeline (WA_MEDIA_UPLOAD.md)
   │ flag 11282 on, type==42 → <meta view_once="true">
   ▼
[Server]  relays the E2E-encrypted stanza; cannot read viewOnce (it's inside the ciphertext)
   │
   ▼
[Receiver]
   │ decrypt → ImageMessage.viewOnce == true, message type 42 (DdP)
   │ INSERT message_view_once_media(message_row_id, state=<initial>)
   │ thumbnail shown in the conversation row; sender-side row asserts "can not view own media"
   │
   ├── user taps to open ──► MediaViewFragment, C1ZB.A0O(42) == true
   │                          → window.addFlags(FLAG_SECURE)
   │                          → forward/share/save menu items hidden (InterfaceC24513Ahd)
   │                          → status reaches 8/9/10 → state = 1 ("opened")
   │                          → window closed, FLAG_SECURE drops with it
   │
   ▼
[EphemeralUpdateRunnable, job type 3]
   │ SELECT ... FROM message_view_once_media JOIN message_media
   │   WHERE from_me=0 AND file_size IS NOT NULL AND state IN (1,2)
   ▼
local media file deleted; row kept, UI shows "View once photo, opened"
```

---

## 13. Unknowns

| Item | Status |
|------|------|
| Benannte Konstanten für `state` 0 (initial) und die exakte Bedeutung, geteilt zwischen 2 (No-Row-Fallback) und "expired" | nur 1 ("opened") hat eine benannte Call-Site; der Rest ist aus dem Fallback-Wert und UI-Strings inferred |
| Statuscodes 8/9/10, konsumiert von `C199158dT.A03`, um "opened" auszulösen | nicht auf benannte Konstanten aufgelöst |
| Retention/Cleanup der **eigenen** Kopie des Senders von gesendeter View-Once-Media | Deletion Job zielt nur auf `from_me = 0`; keine entsprechende senderseitige Cleanup-Logik gefunden |
| Serverseitige Löschung/Markierung des hochgeladenen Objekts nach erstem Download | aus statischer Client-Analyse nicht beobachtbar |
| Konstruktion des `<unavailable type="view_once">`-Nodes (Client-Placeholder vs. server-gebaut) | unresolved; aus früherer Research übernommen, hier nicht neu aufgelöst |
| Android-Consumer der `view_once="read"/"write"`-Wire-Tokens | Token-Präsenz in der Dictionary-Tabelle bestätigt; keine Call-Site gefunden |
| Ob `FLAG_SECURE` auf jedem Codepfad angewendet wird, der View-Once-Inhalt darstellen kann (z. B. Notification-Previews, Widget, Wear) | nur die Pfade `MediaViewFragment` und `ViewOnceViewerActivity` wurden geprüft |
