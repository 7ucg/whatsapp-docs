<!-- src-sha1: d4ba76d600d4bfecb03ea6dfec4064e9d1ae1733 -->
# WhatsApp Sticker — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-11-01
**Umfang:** `Message.StickerMessage`-Proto (Bild/Lottie-Metadaten, Avatar/AI/Premium-Flags, `emojis`, `accessibilityLabel`), eingebettete Sound-Sticker (`StickerMessage.audioMessage`), generische `lottieStickerMessage`-/`audioStickerMessage`-Wrapper, `stickerPackMessage` (Pack-Sharing), lokale Speicherung von Sticker-Packs und das `.was`/Lottie-ZIP-Format, `stickerSyncRmrMessage` (bestätigt entfernt), Sticker-Pack-Intents und Content-Provider-Vertrag von Drittanbietern, eingebauter AI-Sticker-Generierungs-Provider, lokale Sticker-Suche, Feature-Flags; Medien-Kryptografie wird nicht wiederholt (siehe [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md))

---

## 1. Übersicht

Ein "Sticker" auf Android ist einer von mehreren Wire-Message-Typen plus ein großes First-Party-App-Subsystem (Store, lokale Recents, Suche, AI-Generierung) und eine öffentliche Drittanbieter-Integrationsfläche (Intents + Content-Provider). Alle Medien-Bytes (Sticker-Bild, Pack-ZIP, Thumbnails) laufen durch dieselbe verschlüsselte Medien-Pipeline wie jeder andere Anhang — siehe [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) Abschnitt 3 für die `MmsType`-Zeilen (`sticker`, `sticker-pack`, `thumbnail-sticker-pack`, `newsletter-sticker`, `newsletter-sticker-pack`).

| Entität | `Message`-Feld | Wire-Typ | Rolle |
|--------|------------------|-----------|------|
| Einzelner Sticker | `stickerMessage` | **26**, `StickerMessage` (`C30611DTf`) | ein Sticker-Bild/Animation, in einem Chat gesendet |
| Sound-Sticker (eingebettet) | `StickerMessage.audioMessage` | **26** von `StickerMessage`, `oneof audio` → `AudioMessage` | ein kurzer Sprachclip, an einen Sticker-Versand angehängt |
| Lottie-Wrapper | `lottieStickerMessage` | **74**, `FutureProofMessage` (`BD2`) | generischer Umschlag, Name impliziert Lottie-spezifischen Payload; verschachtelter Inhalt ungeklärt |
| Audio-Sticker-Wrapper | `audioStickerMessage` | **134**, `FutureProofMessage` (`BD2`) | gleiches generisches Umschlag-Muster, neu in diesem Build; verschachtelter Inhalt ungeklärt |
| Sticker-Pack | `stickerPackMessage` | **86**, `StickerPackMessage` (`C30610DTe`) | teilt/installiert ein Pack (ZIP von Stickern) |
| Sticker-Sync-Anfrage | `stickerSyncRmrMessage` | **47** (ältere Builds) | **fehlt** im `Message`-Proto in 2.26.41.6 (siehe Abschnitt 7) |
| Status-Sticker-Reaktion | `statusStickerInteractionMessage` | **110**, `StatusStickerInteractionMessage` (`C30560DRg`) | Reaktions-Sticker auf einen Status-Post; hier über diesen Verweis hinaus außerhalb des Umfangs |
| Drittanbieter-Pack-Hinzufügen | Android-`Intent` | `com.whatsapp.intent.action.ENABLE_STICKER_PACK` | externe App bittet WhatsApp, ein von ihr gehostetes Pack zu importieren |
| Drittanbieter-Versand | Android-`Intent` | `com.whatsapp.intent.action.SEND_STICKER` | externe App übergibt einen einzelnen WebP-Sticker an WhatsApps Picker |
| Pack-Inhalts-Vertrag | `ContentProvider` (der externen App eigener) | `content://<authority>/metadata`, `/stickers`, `/stickers_asset` | wie WhatsApp ein Drittanbieter-Pack liest |
| AI-Sticker-Generierung | `ContentProvider` (WhatsApps eigener) | `content://com.whatsapp.provider.sticker_command/generate` | In-App-GenAI-Sticker-Erstellung, über Content-Provider-Aufrufe konsumiert, keine Chat-Message |

Tiers folgen `IMPORTANT.md`: **found** = direkt in dekompiliertem Code/Strings/Manifest gelesen, **inferred** = aus der Code-Form abgeleitet, **unknown** = nicht geklärt. Alle Belege hier sind statisch (dekompilierte APK + Manifest); nichts wurde auf der Leitung mitgeschnitten.

---

## 2. `Message.StickerMessage` (Feld 26)

### 2.1 Felder (found, `C30611DTf`)

| Feld | # | Typ | Verwendung |
|-------|---|------|-----|
| `url` | 1 | string | Legacy-Volltext-URL |
| `fileSha256` | 2 | bytes | Hash des Klartexts |
| `fileEncSha256` | 3 | bytes | Hash von Ciphertext+MAC, auch der Upload-Pfad-Hash |
| `mediaKey` | 4 | bytes | 32-Byte-Schlüssel, HKDF-Info `WhatsApp Image Keys` (Medien-Pipeline, hier nicht wiederholt) |
| `mimetype` | 5 | string | `image/webp` für gewöhnliche Sticker |
| `height` / `width` | 6 / 7 | uint32 | Pixelabmessungen |
| `directPath` | 8 | string | Download-Pfad |
| `fileLength` | 9 | uint64 | Ciphertext-Länge |
| `mediaKeyTimestamp` | 10 | int64 | Sekunden |
| `firstFrameLength` / `firstFrameSidecar` | 11 / 12 | uint32 / bytes | Sidecar für das erste Animations-Frame (siehe [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) Abschnitt 7) |
| `isAnimated` | 13 | bool | animiertes WebP |
| `pngThumbnail` | 16 | bytes | inline-Thumbnail |
| `contextInfo` | 17 | `ContextInfo` | Zitat/Antwort/Anzeigen-Metadaten |
| `stickerSentTs` | 18 | int64 | Sendezeitstempel |
| `isAvatar` | 19 | bool | Avatar-Sticker |
| `isAiSticker` | 20 | bool | AI-generierter Sticker |
| `isLottie` | 21 | bool | der Sticker-Payload ist eine Lottie-Animation, kein einfaches WebP (siehe Abschnitt 4) |
| `accessibilityLabel` | 22 | string | Screenreader-Text |
| `premium` | 24 | int32 | ungeklärt (kein Konsument gefunden) |
| `emojis` | 25 | string | **gefundene Verwendung**: lokales Such-Tag, siehe Abschnitt 9 |
| `audioMessage` | 26 | `AudioMessage` (`oneof audio`) | eingebetteter Sound-Sticker-Clip, siehe Abschnitt 3 |

Feldnummer-Lücken 14, 15, 23: kein definiertes Feld; frühere Nutzung unbekannt. Dies korrigiert die ursprüngliche `Messages/stickerMessage`-Notiz, die `emojis` (25) als letztes Feld auflistet und Feld 26 (`audioMessage`) überhaupt nicht führt — bestätigt vorhanden in `C30611DTf` in 2.26.41.6 (`AUDIO_MESSAGE_FIELD_NUMBER = 26`) und passend zum `oneof audio`-Block im aktuellen `baron-baileys-v2`-Proto.

### 2.2 Message-Type-String-Klassifizierung (found)

Beobachtete Typ-Strings, die an einen `StickerMessage`/`StickerPackMessage`-Versand gebunden sind, gesammelt aus dem Analytics-Dispatch (`C21880sC`) und dem Sticker-Typ-Helper: `sticker`, `avatar_sticker`, `genai_sticker`, `1p_sticker`, `user_created_sticker`, `sticker_pack`. `avatar_sticker` und `genai_sticker` stammen aus `isAvatar`/`isAiSticker`; `1p_sticker` und `user_created_sticker` fügen sich zum `StickerPackOrigin`-Enum (Abschnitt 5), aber die genaue Entscheidungsfunktion, die zwischen `sticker`, `1p_sticker` und `user_created_sticker` wählt, wurde in diesem Durchgang nicht isoliert (unbekannte Präzedenz). Baileys (`messages-send.js`) prüft `isLottie` vor `isAvatar` bei der clientseitigen Ableitung dieses Strings; ob Android dasselbe tut, wurde nicht bestätigt.

### 2.3 `emojis` und `accessibilityLabel` (found, aus dem Ausgangsmaterial aufgewertet)

- `emojis` (25): wird von `EmojiGroupMapper`/`StickerSearchManager` als lokaler Such-Tag-String konsumiert — bestätigt seinen Zweck jenseits des Feldnamens (Abschnitt 9). Nicht server-abgefragt.
- `accessibilityLabel` auf einem *gesendeten Sticker* und `sticker_accessibility_text` auf einem *Drittanbieter-Pack-Sticker* (`StickerContentProviderFetcher`, Abschnitt 8) sind beide auf **125** Zeichen für einen statischen Sticker und **250** für einen animierten begrenzt (`ThirdPartyStickerFetcher`, literale Ints 125/250; JADX zeigt den 125-Zweig fälschlich als ein unzusammenhängendes Feld `C30628DTw.SPLIT_PAYMENT_MESSAGE_FIELD_NUMBER` an, weil dieses Feld zufällig ebenfalls den Wert 125 trägt — ein Dekompiler-Benennungsartefakt, der Zahlenwert selbst wird direkt aus dem Bytecode gelesen).

---

## 3. Sound-Sticker: `StickerMessage.audioMessage` und `audioStickerMessage` (134)

Zwei unterschiedliche, gefundene Mechanismen, nicht vermischen:

| Mechanismus | Feld | Beleg |
|-----------|-------|----------|
| Eingebetteter Clip | `StickerMessage.audioMessage` (26, `oneof audio`) | vorhanden in `C30611DTf`; passt exakt zu `baron-baileys-v2`s `WAProto.proto` (`oneof audio { Message.AudioMessage audioMessage = 26; }`) |
| Eigenständiger Wrapper | `Message.audioStickerMessage` (134, `FutureProofMessage`/`BD2`) | neues Feld in `C30628DTw` für 2.26.41.6, nicht im `Messages/`-Ausgangsmaterial vorhanden; gleiches generisches Umschlag-Muster wie `lottieStickerMessage` (Abschnitt 1), verschachtelter Inhalt unbekannt |

Das Client-Support-Paket `com.whatsapp.stickers.sound` bestätigt ein "Sound-Sticker"-Authoring-Feature: `StickerOpusEncoder` (`nativeEncode(short[] pcm, String outPath)`, native Opus-Kodierung eines aufgenommenen Clips) und `SoundStickerAudioDownloader` (stellt sicher, dass das angehängte Audio vor der Wiedergabe geholt wird, leitet über die gewöhnliche Medien-Pipeline). Dies ist konsistent mit dem Einbetten einer kurzen Sprachnotiz über Feld 26 anstatt (oder zusätzlich zu) des neueren Feld-134-Wrappers.

---

## 4. Sticker-Dateiformate

### 4.1 Einfaches und animiertes WebP (found)

`mimetype = image/webp`; `isAnimated` kennzeichnet ein animiertes WebP. Die Dekodierung läuft über `libstatic-webp.so`s sandboxed libwebp (siehe [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) Abschnitt 15).

### 4.2 Lottie-Sticker — `.was`-ZIP-Container (found, `LottieStickerZipEntrySaver` / `C161836tL`)

Wenn `isLottie` gesetzt ist, ist die Mediendatei des Stickers kein WebP: es ist ein ZIP-Archiv, gespeichert und gelesen über einen `LottieStickerZipEntrySaver`, das enthalten muss:

| Eintrag | Rolle |
|-------|------|
| `animation/animation.json` | die Lottie-(Bodymovin-)JSON-Animation, primär |
| `animation/animation.json.trust_token` | begleitendes Trust/Signatur-Token für das JSON |
| `animation/animation_secondary.json` + `.trust_token` | optionale sekundäre Animations-Variante |

Ein generischer Pack-Level-Extraktor (`C161826tK`, Log-Tag `StickerPackZipEntrySaver`, Basisklassenname `SafeZipEntrySaver`) erlaubt zusätzlich nur die Dateierweiterungen `png`, `webp` und `was` — d. h. die öffentliche `.was`-("WhatsApp Animated Sticker")-Dateierweiterung ist der On-Disk-/ZIP-Eintrags-Marker für diesen Lottie-Container, geprüft gegen den behaupteten MIME-Typ (`application/was`) über einen Content-Sniffer vor der Akzeptanz.

### 4.3 Pack-ZIP-Extraktionslimits (found, `C161826tK`-Konstruktor)

| Limit | Wert |
|-------|-------|
| Max. Einträge pro Pack-ZIP | **65** (hart kodiert) |
| Max. Bytes pro Eintrag | Dictionary-Token (Flag-ID **1900**, KB) × 1024 |
| Max. Gesamtbytes pro Pack | derselbe Token × 1024 × 65 |
| Pfad-Traversal | der Zielpfad jedes Eintrags wird kanonisiert und muss innerhalb des eigenen Verzeichnisses des Packs aufgelöst werden ("Zip entry is attempting to save outside of current directory"), bevor irgendein Byte geschrieben wird — Zip-Slip-Schutz |
| Abgelehnter Eintrag | gelöscht nach einem fehlgeschlagenen Content-Type-Sniff, protokolliert als `StickerPackZipEntrySaver/file in zip is not valid` |

Dies erhärtet und erweitert die `Messages/stickerPackMessage`-Ausgangsnotiz (die "ZIP extraction and file validation" und "validates sticker files reside within extracted ZIP boundaries" aus nur 2.26.34.4 als Log-Referenz zitierte, ohne die Limits).

---

## 5. `Message.StickerPackMessage` (Feld 86)

### 5.1 Felder (found, `C30610DTe`) — entspricht dem Ausgangsmaterial und `baron-baileys-v2` exakt

| Feld | # | Typ |
|-------|---|------|
| `stickerPackId` | 1 | string |
| `name` | 2 | string |
| `publisher` | 3 | string |
| `stickers` | 4 | repeated `Sticker` |
| `fileLength` / `fileSha256` / `fileEncSha256` / `mediaKey` / `directPath` / `mediaKeyTimestamp` | 5, 6, 7, 8, 9, 13 | Pack-ZIP-Medienreferenz (`MmsType` `sticker-pack`, HKDF-Info `WhatsApp Sticker Pack Keys`) |
| `caption` | 10 | string |
| `contextInfo` | 11 | `ContextInfo` |
| `packDescription` | 12 | string |
| `trayIconFileName` | 14 | string |
| `thumbnailDirectPath` / `thumbnailSha256` / `thumbnailEncSha256` / `thumbnailHeight` / `thumbnailWidth` | 15–19 | Pack-Thumbnail (`MmsType` `thumbnail-sticker-pack`) |
| `imageDataHash` | 20 | string |
| `stickerPackSize` | 21 | uint64 |
| `stickerPackOrigin` | 22 | enum `StickerPackOrigin` |

Verschachteltes `Sticker`: `fileName` (1), `isAnimated` (2), `emojis` (3, repeated), `accessibilityLabel` (4), `isLottie` (5), `mimetype` (6), `premium` (7).

`StickerPackOrigin`: `FIRST_PARTY` = 0, `THIRD_PARTY` = 1, `USER_CREATED` = 2.

### 5.2 Lokale Speicherung (found, `AbstractC149676Ty.java`, `C1888782f.java`, `C0R5.java`)

| Tabelle | Spalten |
|-------|---------|
| `message_sticker_pack` | `message_row_id`, `sticker_pack_id`, `pack_name`, `pack_description`, `publisher`, `tray_icon_file_name`, `image_data_hash`, `sticker_pack_size`, `sticker_pack_origin`; indiziert auf `pack_name` und `publisher` |
| `message_sticker_pack_stickers` | `_id`, `message_row_id`, `file_name`, `is_animated`, `emojis`, `accessibility_label`, `is_lottie`, `mimetype` |

Dies ersetzt den Verweis des Ausgangsmaterials auf Version 2.26.34.4 (`StickerPackMessageMapper` / `message_sticker_pack`, nur durch einen Log-String zitiert) durch die konkrete Spaltenliste für 2.26.41.6.

---

## 6. `stickerSyncRmrMessage` — in 2.26.41.6 bestätigt entfernt

Feld 47 (`StickerSyncRMRMessage`: `filehash` repeated string, `rmrSource` string, `requestTimestamp` int64) erscheint in `C30628DTw` (dem `Message`-Container) für 2.26.41.6 **nicht**: keine Feldnummer 47 bildet darauf ab, und es existiert keine Klasse oder String mit `StickerSyncRMR`/`stickerSyncRmr` irgendwo im dekompilierten Baum. Dies entspricht und erweitert die eigene Beobachtung des Ausgangsmaterials, dass das Feld bereits in 2.26.36.1 fehlte — es bleibt fünf Builds später weiterhin abwesend. Gemäß dem Evidenz-Vertrag ist dies eine **beobachtete Abwesenheit**, keine bestätigte Entfernung: ob es umbenannt, in ein anderes Proto verschoben oder ganz gestrichen wurde, ist unbekannt.

Eine nach `filehash` indizierte Tabelle existiert weiterhin, aber zu einem unverwandten Zweck: `RecentStickerDBStorage` (`C6VB`, `C17460jr`, `C6V8`) verfolgt lokal gesendete/empfangene Sticker nach Datei-Hash für die Recents-Leiste — dies ist lokale Buchhaltung, nicht die Wire-Sync-Message, und darf nicht damit verwechselt werden.

---

## 7. Drittanbieter-Sticker-Pack-API

Dies ist eine öffentliche, per Konvention dokumentierte Integrationsfläche (`com.whatsapp.sticker.READ`-Berechtigungsfamilie); alles Folgende findet sich im `AndroidManifest.xml` und den zugehörigen Klassen.

### 7.1 Manifest-Fläche

| Komponente | Deklaration |
|-----------|-------------|
| Berechtigung | `com.whatsapp.sticker.READ` — erforderliches `android:readPermission` auf dem eigenen Content-Provider einer Drittanbieter-App, bevor WhatsApp ihn abfragt |
| Pack-Hinzufügen-Activity | `com.whatsapp.stickers.ui.thirdpartystickers.AddThirdPartyStickerPackActivity`, `exported="true"`, Intent-Filter `action com.whatsapp.intent.action.ENABLE_STICKER_PACK` + `category DEFAULT` |
| Pack-Hinzufügen-Legacy-Alias | `activity-alias` `com.whatsapp.stickers.thirdpartystickers.AddThirdPartyStickerPackActivity` → gleiches Ziel (erhalten für Apps, die gegen den Pre-Refactor-Paketnamen gebaut sind) |
| Einzel-Sticker-Senden-Activity | `com.whatsapp.stickers.command.send.SendStickerCommandActivity`, `exported="true"`, Intent-Filter `action com.whatsapp.intent.action.SEND_STICKER` + `category DEFAULT` + `data mimeType="image/webp"` |
| Whitelist-Prüf-Provider | `com.whatsapp.provider.sticker_whitelist_check` → `WhitelistPackQueryContentProvider`, `exported="true"` |
| Deep-Link | `whatsapp://stickerpack` (`<data android:host="stickerpack" android:scheme="whatsapp"/>`); Zielaktivität/Routing für diesen spezifischen Host in diesem Durchgang nicht isoliert (unknown) |

### 7.2 `ENABLE_STICKER_PACK`-Intent-Vertrag (found, `AddThirdPartyStickerPackActivity`)

Request-Extras (`String`): `sticker_pack_id`, `sticker_pack_authority`, `sticker_pack_name`.

Validierung, bevor irgendetwas geholt wird:
1. `getCallingActivity()` muss ungleich null sein (der Intent muss von `startActivityForResult` kommen, nicht von einem bloßen Broadcast-artigen Start).
2. `PackageManager.resolveContentProvider(sticker_pack_authority, …)` muss zu einem Provider aufgelöst werden.
3. Das Paket des aufgelösten Providers muss dem Paket der aufrufenden Activity entsprechen — **eine App kann nur für Authorities bürgen, die sie selbst besitzt**.

Result-Extras auf dem zurückgegebenen `Intent` (eines von): `add_successful=true`, `already_added=true`, `validation_error=<string>`, oder `CancelReason.USER_CANCELLED=true` (Nutzer hat den Hinzufügen-Dialog abgebrochen).

### 7.3 Pack-Content-Provider-Vertrag (found, `StickerContentProviderFetcher`/`C179697lN`, `C175327dG`)

WhatsApp liest ein Drittanbieter-Pack, indem es den *eigenen Provider der aufrufenden App* an der angegebenen Authority abfragt, abgesichert über `readPermission == "com.whatsapp.sticker.READ"` auf diesem Provider:

| URI | Zurückgegebene Spalten |
|-----|-------------------|
| `content://<authority>/metadata/<identifier>` | `sticker_pack_identifier`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_icon`, `android_play_store_link`, `ios_app_download_link`, `image_data_version`, `whatsapp_will_not_cache_stickers`, `animated_sticker_pack` |
| `content://<authority>/stickers/<identifier>` | `sticker_file_name`, `sticker_emoji`, `sticker_accessibility_text` |
| `content://<authority>/stickers_asset/<identifier>/<filename>` | öffenbarer Stream (Tray-Icon oder einzelne Sticker-Datei) |

Im Fetcher gefundene Validierung: `authority`/`identifier` weisen ungültige Zeichen zurück; `identifier` ≤ 128 Zeichen; zurückgegebenes `sticker_pack_identifier` muss den angeforderten Identifier spiegeln; `sticker_pack_icon`-Dateiname ≤ 128 Zeichen; `android_play_store_link` muss `play.google.com` enthalten, `ios_app_download_link` muss `itunes.apple.com` oder `apps.apple.com` enthalten; `publisher`/`name` nicht leer und ≤ 128 Zeichen; `tray`-ID nicht leer; die Sticker-Anzahl muss innerhalb von `[Flag 17124, Flag 17327]` inklusive liegen (Dictionary-Token-Grenzen, numerische Werte in diesem Durchgang nicht geklärt); jedes geholte Sticker-Asset ist begrenzt auf **~103424 Bytes (101 KB)** für ein statisches Pack oder **~512512 Bytes (500,5 KB)** für ein animiertes Pack (`Math.min(animated ? 500 : 100, 1024) + 1) * 1024`; übergroße oder unlesbare Streams werden verworfen, wobei die Datei auf null gesetzt wird, statt das gesamte Pack abzubrechen. Ein passender `app may have been deleted` / `third_party_sticker_app_deleted`-Pfad behandelt das Verschwinden des Pakets des Providers mitten im Abruf.

Ein separates boolesches Flag (**13081**) steuert, ob ein bereits auf der Whitelist stehendes Pack weiterhin vom Content-Provider neu geholt oder aus dem Cache bedient wird, und Flag **22198** schaltet zwischen einem älteren synchronen Dialog-gesteuerten Hinzufügen-Flow und direktem Routing zum Sticker-Pack-Vorschau-Bildschirm um; Flag **13711** wählt zwischen zwei internen Installationsvarianten (`C175327dG.A00` vs. `A01`) beim Installieren über den Content-Provider-Shortcut-Pfad (Abschnitt 7.5) statt über die Activity.

### 7.4 `SEND_STICKER`-Intent-Vertrag (found, `SendStickerCommandActivity`)

Daten: eine `content://`-URI, vom eigenen Provider der aufrufenden App, deren Authority sich auf genau dasselbe aufrufende Paket auflösen muss. Die referenzierte Datei muss als exakt **512×512** WebP dekodieren und ≤ **500000 Bytes** sein; der Client stempelt sie neu durch die normale Sticker-Pipeline (Hash, Speicherung, Anhängen) und hängt diese `Intent`-Extras als `Sticker`-Pack-Metadaten an, falls vorhanden: `sticker_accessibility_text`, `sticker_pack_id`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_ios_store_link`, `sticker_pack_play_store_link` (die beiden Store-Links werden mit denselben Domain-Prüfungen wie in Abschnitt 7.3 validiert).

### 7.5 Whitelist-Prüf-Provider (found, `WhitelistPackQueryContentProvider`)

`content://com.whatsapp.provider.sticker_whitelist_check/<match>?authority=<pkg-authority>&identifier=<pack-id>` — Single-Row-, Single-Column-(`result`, `0`/`1`)-Cursor, der beantwortet "ist dieses Pack bereits hinzugefügt". Die Aufrufer-Validierung spiegelt 7.2: das aufrufende Paket muss dem Paket entsprechen, das die abgefragte `authority` besitzt. Von `getType()` zurückgegebener MIME-Typ: `vnd.android.cursor.item/vnd.com.whatsapp.provider.sticker_whitelist_check.is_whitelisted`.

### 7.6 Interner Sticker-Command-Provider (found, `StickerCommandProvider`, `com.whatsapp.provider.sticker_command`, `exported="true"`)

Nicht Teil des oben genannten Drittanbieter-Vertrags — dies ist WhatsApps eigener Provider, abgefragt von WhatsApps eigenen UI-/Assistenten-Flächen, mit URI-Last-Path-Segment-Dispatch:

| Pfad | Verhalten |
|------|-----------|
| `installPack?authority=&identifier=` | installiert ein Pack über denselben `C175327dG`-Fetch-/Validierungspfad wie Abschnitt 7.3, unter Umgehung der Activity-UI |
| `removePack?authority=&identifier=` | deinstalliert ein zuvor hinzugefügtes Pack |
| `generate?prompt=` | AI-Sticker-Generierung (Abschnitt 8); Prompt-Länge muss nach dem Trimmen 3–200 Zeichen sein |
| `availability` | gibt `{available, consent_required}` für die AI-Sticker-Generierung zurück |
| `image/<token>` (via `openFile`) | streamt einen generierten Sticker PNG/WebP anhand eines opaken Tokens zurück, MIME `image/webp` |

---

## 8. AI-generierte Sticker (found, `AiStickerCommands`, `StickerCommandProvider`)

`isAiSticker` (Feld 20) kennzeichnet eine `StickerMessage` als AI-generiert; der Typ-String ist `genai_sticker` (Abschnitt 2.2). Die Generierung selbst wird lokal-UI-ausgelöst über den `generate`-Provider-Pfad (7.6): Eignungs- (`C174467bs.A00`) und Einwilligungs-Gates (`A02`) werden vor jedem Generierungsaufruf geprüft; Ergebnisse kommen als Liste opaker `token`s zurück, die später über `image/<token>` aufgelöst werden. Das tatsächliche Generierungs-Backend (on-device vs. serverseitiges Modell) ist aus diesem Code-Pfad unbekannt — nur die clientseitige Eignungs-/Einwilligungs-/Token-Verkabelung wurde geklärt.

---

## 9. Sticker-Suche (found, `StickerSearchManager`, `EmojiGroupMapper`, Kontext-Vorschlagspaket)

Vollständig lokal, keine Server-Abfrage. `StickerSearchManager.A00` nimmt eine Freitext-Abfrage, löst sie über `EmojiGroupMapper` in eine Menge von Emoji-Zeichen auf, fügt sie zu einem durch Leerzeichen getrennten String zusammen und matcht diesen String gegen das **lokal gespeicherte** `emojis`-Feld jeder `StickerMessage`/Pack-`Sticker` (Abschnitt 2.3) plus zuletzt verwendete/featured Kandidaten, wobei die Ergebnisse in "exakte Emoji-Übereinstimmung" vs. "sonstige"-Buckets aufgeteilt und auf ein Dictionary-Token-Ergebnislimit (Flag **22573**) gekürzt werden. Ein `includeAvatarResults`-Flag steuert separat, ob Avatar-Sticker teilnehmen, abgesichert durch eine eigene Eignungsprüfung. Dies bestätigt — und wertet von "kann… unbekannt enthalten" auf found auf —, dass das `emojis`-String-Feld des Protos der clientseitige Such-Indexschlüssel ist, kein reines Anzeige-Tag.

---

## 10. Medien-Verschlüsselung (Verweis, nicht wiederholt)

Jede sticker-tragende Medienreferenz (`stickerMessage`, `stickerPackMessage`, deren Thumbnails) läuft durch dieselbe in [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) dokumentierte Medien-Pipeline: 32-Byte-Zufalls-Medienschlüssel, HKDF-80 (`WhatsApp Image Keys` für `sticker`, `WhatsApp Sticker Pack Keys` für `sticker-pack`, `WhatsApp Sticker Pack Thumbnail Keys` für das Pack-Thumbnail, eine `WhatsApp Image Thumbnail Keys`-artige Handhabung wird hier nicht verwendet — Sticker- und Pack-Thumbnails haben ihre eigenen dedizierten Info-Strings), AES-CBC + 10-Byte trunkiertes HMAC-SHA256, `fileSha256`/`fileEncSha256`, von `media_conn` ausgegebene Hosts, und die `/mms/<type>/<hash>`-Upload-URL-Form. Nichts Sticker-Spezifisches ändert etwas davon; siehe Abschnitte 2–9 jenes Reports für die vollständigen Ableitungs-, Retry- und Fehlercode-Tabellen.

---

## 11. Feature-Flags (IDs wie an den Call-Sites gelesen; Namen ungeklärt)

| Flag | Wo | Steuert |
|------|-------|----------|
| **1900** | `C161826tK`-Konstruktor | Pro-Eintrag- und Gesamt-Budget (KB) für die Pack-ZIP-Extraktion |
| **13081** | `AddThirdPartyStickerPackActivity` | erneutes Holen vs. Cache für ein bereits auf der Whitelist stehendes Drittanbieter-Pack |
| **13711** | `StickerCommandProvider`, `AddThirdPartyStickerPackActivity` | wählt Installationspfad-Variante (`C175327dG.A00` vs. `A01`) |
| **17124** / **17327** | `StickerContentProviderFetcher` | Min./Max.-Sticker-Anzahl, die von einem Drittanbieter-Pack akzeptiert wird |
| **22198** | `AddThirdPartyStickerPackActivity` | asynchroner Dialog-gesteuerter Hinzufügen-Flow vs. direktes Vorschau-Bildschirm-Routing |
| **22573** | `StickerSearchManager` | lokales Such-Ergebnislimit |

---

## 12. Baileys (`baron-baileys-v2`, Quelle gelesen, nichts getestet)

| Aspekt | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| `Message.StickerMessage`-Felder | identischer Feldsatz inklusive `audioMessage` (26, `oneof audio`) — die Proto-Quelle passt feldweise exakt zum dekompilierten 2.26.41.6-Layout | gleich (Abschnitt 2.1) |
| `Message.StickerPackMessage`-Felder | identischer Feldsatz (1–22) | gleich (Abschnitt 5.1) |
| Sticker senden | `prepareWAMessageMedia({ sticker })` baut `stickerMessage` über den generischen Medien-Vorbereitungspfad (`MmsType` `sticker`, Image-HKDF-Info); die `stickerAudio`-Option hängt eine vorbereitete `audioMessage` an `m.stickerMessage.audioMessage` an | gleiche Medien-Pipeline gemäß [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) Abschnitt 17 |
| Pack senden | `stickerPackMessage`/`stickerPack`-Eingabe wird ohne zusätzliche Validierung durch `StickerPackMessage.fromObject` geleitet | Client validiert zusätzlich über den ZIP-Extraktor und DB-Constraints (Abschnitt 5, 6), bevor ein selbst gebautes Pack akzeptiert wird |
| Dekodierung | `decode-wa-message.js` mappt `isAvatar`→`avatar_sticker`, `isAiSticker`/`isGenAI`→`genai_sticker`; `messages-send.js` mappt `isLottie`→`1p_sticker` vor `isAvatar`/plain `sticker` bei der Ableitung des ausgehenden Typ-Strings | dieselben drei Message-Typ-Strings im Android-Analytics-Dispatch gefunden (`avatar_sticker`, `genai_sticker`, plus `1p_sticker`/`user_created_sticker`); exakte Android-Präzedenz-Reihenfolge unbestätigt (Abschnitt 2.2) |
| Drittanbieter-Pack-Intents/-Provider | nicht implementiert — Baileys hat keine Android-`Intent`/`ContentProvider`-Fläche | vollständige Fläche, Abschnitt 7 |
| `lottieStickerMessage`-/`audioStickerMessage`-Wrapper | vorhanden als bloßes `FutureProofMessage`-Feld nur im Proto; kein dedizierter Encoder-/Decoder-Pfad gefunden | gleicher bloßer Umschlag, ebenfalls keine feldspezifische Behandlung gefunden (Abschnitt 3) |

---

## 13. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| `ENABLE_STICKER_PACK` gibt `validation_error` "cannot find the provider for authority" zurück | der `authority`-String der Drittanbieter-App löst sich zu keinem installierten Provider auf | die Sticker-Pack-veröffentlichende App muss ihren Provider unter genau dieser Authority deklarieren und exportieren |
| `ENABLE_STICKER_PACK` gibt "does not own authority" zurück | aufrufendes Paket unterscheidet sich vom Paket des aufgelösten Providers | eine App darf nur für Authorities innerhalb ihres eigenen Pakets bürgen |
| Pack-Hinzufügen schlägt stillschweigend fehl mit "sticker count should be between X and Y" | die `stickers`-Abfrage des Packs lieferte eine Zeilenanzahl außerhalb von `[Flag 17124, Flag 17327]` | den Drittanbieter-`/stickers/<id>`-Cursor innerhalb der serverseitig konfigurierten Grenzen halten |
| `SafeZipEntrySaver: File being unzipped is too big` / "Too many files to unzip" | Pack-ZIP überschreitet das Pro-Eintrag-/Gesamt-Byte-Budget oder die 65-Einträge-Obergrenze | das Pack verkleinern oder Sticker über mehrere Packs verteilen |
| `tray image name invalid` / Namenslängenfehler | `sticker_pack_icon` des Drittanbieters enthält ungültige Zeichen oder überschreitet 128 Zeichen | den Tray-Dateinamen bereinigen und verkürzen |
| `StickerPackZipEntrySaver/file in zip is not valid` | der gesniffte Content-Typ eines extrahierten Eintrags passt nicht zu seiner behaupteten Erweiterung/MIME | Einträge versenden, deren Bytes tatsächlich zu `png`/`webp`/`was` passen |
| `the sticker is not a 512px WebP` (`SEND_STICKER`) | Bild des Einzel-Sticker-Intents ist nicht exakt 512×512 | vor dem Senden des Intents skalieren |

---

## 14. Zu unterscheidende Begriffe

| Nicht verwechseln | Fakt |
|----------------|------|
| `StickerMessage.audioMessage` (Feld 26) vs. `Message.audioStickerMessage` (Feld 134) | ersteres ist eine bestätigte eingebettete `AudioMessage` innerhalb eines Sticker-Versands; letzteres ist ein separates, weiterhin opakes Top-Level-Wrapper-Feld, neu in diesem Build |
| `isLottie` (Pro-Sticker-Flag) vs. `Message.lottieStickerMessage` (Feld-74-Wrapper) | das Flag ist an ein konkretes, gefundenes Dateiformat gebunden (`.was`-ZIP mit `animation/animation.json`); der verschachtelte Payload des Wrapper-Feldes ist weiterhin ungeklärt — es ist nicht gezeigt, dass es sich um denselben Mechanismus handelt |
| `stickerSyncRmrMessage` (Wire-Message, abwesend) vs. `RecentStickerDBStorage` (nach `filehash` indizierte lokale Tabelle) | ersteres existiert in diesem Build auf der Leitung nicht mehr; letzteres ist unverwandte lokale Buchhaltung, die zufällig ebenfalls nach Datei-Hash indiziert |
| Drittanbieter-Pack-Vertrag (Abschnitte 7.2–7.5, Provider der externen App) vs. `StickerCommandProvider` (Abschnitt 7.6, WhatsApps eigener Provider) | beide können "ein Pack per Authority+Identifier installieren", aber der erste ist WhatsApp, das *den Provider einer anderen App liest*, der zweite ist WhatsApps interner Shortcut um seine eigene Activity-UI herum |
| AI-Sticker-Generierung (`isAiSticker`, lokaler GenAI-Flow) vs. Drittanbieter-AI-/Sticker-Apps | ersteres ist WhatsApps eigenes In-App-Feature hinter `StickerCommandProvider`; es hat nichts mit dem Drittanbieter-Content-Provider-Vertrag zu tun |

---

## 15. Ablauf: Hinzufügen eines Drittanbieter-Sticker-Packs

```
[Third-party app]  exports ContentProvider at authority X, readPermission=com.whatsapp.sticker.READ
     │  startActivityForResult(ACTION_ENABLE_STICKER_PACK, extras: sticker_pack_id, sticker_pack_authority=X, sticker_pack_name)
     ▼
[AddThirdPartyStickerPackActivity]  getCallingActivity() != null?
     │  resolveContentProvider(X) exists?  calling package == provider's package?
     ▼  (all pass)
[StickerContentProviderFetcher]  query content://X/metadata/<id>
     │  validate identifier echo, name/publisher length, tray icon name, store links
     ▼
[StickerContentProviderFetcher]  query content://X/stickers/<id>  (sticker_file_name, sticker_emoji, sticker_accessibility_text)
     │  validate count in [flag 17124, flag 17327], accessibility text ≤ 125/250 chars
     ▼
[StickerContentProviderFetcher]  openInputStream content://X/stickers_asset/<id>/<file>  per sticker + tray icon
     │  cap ~101 KB (static) / ~500.5 KB (animated) per asset
     ▼
[Client]  store pack + stickers, mark whitelisted (ThirdPartyWhitelistedPacksStore)
     │
     ▼
[AddThirdPartyStickerPackActivity]  result Intent: add_successful=true | already_added=true | validation_error=<reason>
     │
     ▼
[Third-party app]  onActivityResult()
```

---

## 16. Unbekannte Punkte

| Punkt | Status |
|------|--------|
| Verschachtelter Payload von `lottieStickerMessage` (74) und `audioStickerMessage` (134) | Feld existiert, generischer `FutureProofMessage`-Wrapper, Inhalt ungeklärt |
| Exakte Android-Präzedenz für `sticker` vs. `1p_sticker` vs. `user_created_sticker`-Typ-Strings | nur die Analytics-Bytecode-Zuordnung wurde gefunden, nicht die auswählende Funktion |
| `premium`-Feld (24) auf `StickerMessage`/`Sticker` | kein Konsument gefunden |
| Numerische Werte hinter den Dictionary-Token-Flags 1900, 17124, 17327, 22573 | Token-IDs gefunden, Live-Werte statisch nicht geklärt |
| `whatsapp://stickerpack`-Deep-Link-Zielaktivität | Host im generischen Deep-Link-Intent-Filter des Manifests deklariert; welcher interne Bildschirm ihn konsumiert, wurde nicht isoliert |
| AI-Sticker-Generierungs-Backend (on-device vs. Server) | nur clientseitige Eignungs-/Einwilligungs-/Token-Verkabelung geklärt |
| Ob der Server seine eigenen Pack-Größen-/Anzahl-Limits über die des Clients hinaus durchsetzt | serverseitig, unbekannt |
| Schicksal von `stickerSyncRmrMessage` (umbenannt, verschoben oder entfernt) | bestätigt abwesend vom Wire-Proto in 2.26.36.1 bis 2.26.41.6; Entfernung nicht bestätigt |
| Traffic | nichts mitgeschnitten; kein dynamischer Test |
