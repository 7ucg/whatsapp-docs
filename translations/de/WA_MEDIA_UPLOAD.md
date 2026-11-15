<!-- src-sha1: a12736ca9c475f1c7c0195dbae0d18d5725a4440 -->
# WhatsApp Medien-Upload — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Android Medienübertragung: `media_conn` IQ (Hosts, Auth, ttl, Buckets, Fallback-Hosts), Konstruktion von Upload- und Download-URLs und HTTP-Parametern, Medientyp-Tabelle mit HKDF-info-Strings, Medienschlüssel-Erzeugung und -Ableitung, AES-CBC + HMAC Verschlüsselung, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, Thumbnails, Streaming-Sidecars für Video / Audio / progressive Bilder, resumable Upload, Routenauswahl, Retry und Backoff, Upload- und Download-Fehlercodes, Media-Retry-Receipt und `mediaretry`-Benachrichtigung, View-Once- und Status-Medien, Newsletter-(Channel-)Medien, Express-Pfad, clientseitige native Hardening der Medienparser, Baileys-Vergleich

---

## 1. Was es technisch ist

Medien laufen nie innerhalb des chatd-Streams (siehe [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Eine Nachricht trägt nur eine Protobuf-Referenz (Key, Hashes, `directPath`); die Bytes gehen über separate HTTPS-Verbindungen zu Medien-Hosts. Chatd liefert nur eine Sache: die `media_conn`-IQ, die Hostnamen und ein kurzlebiges Upload-Auth-Token ausgibt. Alle Aussagen stammen aus statischer Analyse der dekompilierten APK und der entpackten nativen Bibliotheken; nichts wurde auf der Leitung mitgeschnitten. Tiers: **found** = im Code oder in Strings gelesen, **inferred** = hergeleitet, **unknown** = nicht aufgelöst.

| Schicht | 2.26.41.6-Name | Rolle |
|-------|----------------|------|
| Routen-Selektor | `RouteSelector` (`C10950Wx`) | hält das aktuelle `media_conn`-Ergebnis, Refresh-Timer, Throttle, Routen-Fabrik |
| `media_conn`-Parser | `C43951qe` (IQ-Result-Handler), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | parst `<media_conn>` / `<host>` |
| Routen-Lieferant | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (statische Supplier) | wählt Host pro Versuch, tauscht Auth-Token |
| Retry-Treiber | `TransferRetries` (`C44566Jd2`) | Versuchsschleife um einen Transfer |
| Medientyp-Tabelle | `MmsType` (`C15530gU`) | pro Typ: Pfad-String, HKDF-info-Bytes, numerische id |
| Key-Provider | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF 80 Bytes, Nicht-E2EE-Domain-Key |
| Cipher-Streams | `M2I` (Verschlüsselung ausgehend), `M23` (Verschlüsselung eingehend), `P9N` / `P1X` / `P1Y` (Sidecar-MACs), `C51101MlN` (Ranged-Decrypt) | AES-CBC + HMAC |
| Upload-Treiber | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (Key-Wiederverwendung), `C57333Po0` (Key-Erzeugung + Hashes) | Hashes, Sidecars, Upload-Orchestrierung |
| Upload-URL | `C43489Iy4` | `/surface/type/hash?...` |
| Download-URL | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) Upload; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) Download | Transport |
| Resume-Probe | `HttpResumeCheck` (`C59524QnW`) | fragt den Server, wie viele Bytes er bereits hat |
| Retry-Receipt | `SendMediaErrorReceiptJob`, Writer-Fälle 77 und 327 in `HandlerThreadC21920sG` | fordert vom Sender erneuten Upload an |
| Retry-Benachrichtigung | `MediaRetryNotificationHandler` (`C1S0`, Notification-Code 97) | verarbeitet die Antwort |
| Native | `libwhatsapp.so` (Rust-Media-Crates, RLBox-Sandboxes), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | Parser und Decoder |

Punkte, die den Rest des Reports bestimmen:

- Android leitet **80** Bytes aus dem Medienschlüssel ab (IV 16, Cipher-Key 32, MAC-Key 32), nicht 112 (Abschnitt 4).
- Der HTTP-Pfad ist `/{surface}/{type}/{urlSafeFileEncSha256}`, wobei `type` der `MmsType`-String des Mediums ist (`image`, `ptt`, `md-msg-hist`, ...), keine grobe Klasse (Abschnitt 8.1).
- Das Android-Upload-`token` ist nicht der Dateihash; es ist ein SHA-256 über ein installationsspezifisches Geheimnis und den Dateihash (Abschnitt 8.2).
- Newsletter-(Channel-)Medien nutzen denselben Code, aber Surface `newsletter` und ein zufälliges Token; sie sind unverschlüsselt (found für den Artwork-Pfad, inferred für den Rest, Abschnitt 13).
- Download-Hosts werden nach einem aus dem Dateihash abgeleiteten Bucket gefiltert (Abschnitt 9.2).

---

## 2. `media_conn`-IQ

### 2.1 Anfrage (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout 32000 ms. Nur eine Anfrage ist gleichzeitig unterwegs (`inFlightMediaRoutingRequestTime`); ein zweiter Aufruf loggt `not sending request` und kehrt zurück. Ein globaler Throttle (`ChatdMediaThrottleManager`) kann den Aufruf unterdrücken (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Antwort (found, `C43951qe.CFS`)

| Node / Attribut | Typ | Verwendung |
|------------------|------|-----|
| `media_conn@auth` | String, erforderlich | Upload-Auth-Token (`auth`-Query-Parameter) |
| `@ttl` | Sekunden | Lebensdauer der Verbindung; Ablauf = Sendezeit + ttl * 1000 |
| `@auth_ttl` | Sekunden | Lebensdauer des Auth-Tokens; Ablauf = Sendezeit + auth_ttl * 1000 |
| `@max_buckets` | long, Default 0 | Modulus für den Download-Bucket (Abschnitt 9.2) |
| `@is_new` | int, Default 1 | 1 = Host-Liste ersetzen; sonst vorherige Hosts behalten und nur Token und ttl übernehmen (`previous hosts retained`) |
| `@id` | String | als `last_id` gespeichert, in der nächsten Anfrage zurückgesendet |
| `@max_auto_download_retry` | int, Default 3 | Retry-Budget für automatische Downloads |
| `@max_manual_retry` | int, Default 3 | Retry-Budget für manuelle Downloads |
| `@ip_token`, `@set_ip_token` | String, "0"/"1" | geparst und gecacht; `ip_token` wird nur verwendet, wenn Flag **12149** aktiv ist und `set_ip_token` true ist (Verwendungsstelle: unknown) |
| `host` (wiederholt) | Node | ein Routeneintrag |

`host`-Attribute (found): `hostname` (erforderlich), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` oder `fallback`; alles andere wird zu `primary`), `force_ip` (`"true"`). Kinder: `<upload>`, `<download>`, `<download_buckets>`; die Kind-Tag-Namen sind die Capability-Einträge. `upload` und `download` behalten nur Tags, die in einer festen Menge von 34 Medientyp-Strings vorkommen (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, die `newsletter-*`-Familie und die `thumbnail-*`-Familie); `download_buckets` wird ungefiltert behalten.

Ein Routen-Host ist nur nutzbar, wenn sein Hostname auf `.whatsapp.net` endet (`Mms4RouteSupplier.A06`, gilt auch für `fallback_hostname`).

### 2.3 Caching und Refresh (found)

| Regel | Wert |
|------|-------|
| Persistieren | mit Flag **149** wird das Ergebnis als JSON (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) unter `route_selector_prefs` / `media_conn` gespeichert; einmal geladen, nur genutzt, wenn der Auth noch nicht abgelaufen ist |
| Refresh-Check | vor einem Transfer: wenn Verbindung oder Auth innerhalb von 120000 ms abläuft, neue IQ senden und bis zu 20000 ms warten (`requestroutesandwaitforauth`) |
| Timer | `auth expiry - 60000 ms` nach jedem Ergebnis; Vordergrund (`BgG`) stellt ihn neu |
| Auth-Fehler | HTTP 401 oder 403 bei einem Transfer triggert einen Refresh (`onmediatransfererrororresponsecode`), max. 2 Token-Wechsel pro Transfer (`JW1.A00 < 2`), danach wird der Versuch mit dem neuen `auth` wiederholt |
| Auth vor Versuch | `refreshAuthBeforeAttempt` tauscht ein neueres Token ein, wenn das gecachte innerhalb von 120000 ms vor Ablauf liegt (Flag-Symbol `PTU.A0D`) |

### 2.4 IQ-Fehler (found, `C43951qe.Brt`)

`<error code backoff>` im IQ-Ergebnis:

| Code | Verhalten |
|------|-----------|
| 503 | setzt den Medien-Throttle zurück; plant den nächsten Refresh nach einem Fibonacci-Backoff mit Jitter (`3/4 * t + rand(t/2)`) |
| 507 mit backoff > 0 | throttelt Medienanfragen bis `now + min(backoff, 10800) s` |
| andere / 0 | ignoriert |

---

## 3. Medientypen und HKDF-info-Strings (found, `MmsType` `C15530gU` statische Initialisierung)

Jeder `MmsType` hält einen Pfad-String (`A02`), ein kurzes Dateityp-Label (`A01`, z. B. `IMG`), die HKDF-`info`-Bytes (`A03`) und eine numerische id (`A00`). Die `info`-Bytes werden roh als HKDF-info verwendet (ohne weiteres Präfix).

| HKDF-info | `MmsType`-Pfad-Strings |
|-----------|------------------------|
| `WhatsApp Image Keys` | `image`, `sticker`, `kyc-id`, `biz-cover-photo`, `biz-flows`, `wamo-image`, `newsletter-image`, `newsletter-image-status`, `newsletter-sticker`, `newsletter-music-artwork` |
| `WhatsApp Video Keys` | `video`, `ptv`, `gif`, `wamo-video`, `newsletter-video`, `newsletter-video-status`, `newsletter-ptv`, `newsletter-gif`, `newsletter-gif-status` |
| `WhatsApp Audio Keys` | `audio`, `ptt`, `newsletter-audio`, `newsletter-audio-status`, `newsletter-ptt` |
| `WhatsApp Document Keys` | `document`, `biz-flows`, `maiba-file`, `db`, `newsletter-document` |
| `WhatsApp Image Thumbnail Keys` | `thumbnail-image`, `newsletter-thumbnail-image`, `newsletter-thumbnail-status` |
| `WhatsApp Video Thumbnail Keys` | `thumbnail-video`, `thumbnail-gif`, `newsletter-thumbnail-video` |
| `WhatsApp Document Thumbnail Keys` | `thumbnail-document` |
| `WhatsApp Link Thumbnail Keys` | `thumbnail-link`, `newsletter-thumbnail-link` |
| `WhatsApp Chat Wallpaper Keys` | `chat-wallpaper-image` |
| `WhatsApp App State Keys` | `md-app-state` |
| `WhatsApp History Keys` | `md-msg-hist` |
| `Group History` | `group-history` |
| `WhatsApp Sticker Pack Keys` | `sticker-pack`, `newsletter-sticker-pack` |
| `WhatsApp Sticker Pack Thumbnail Keys` | `thumbnail-sticker-pack`, `newsletter-thumbnail-sticker-pack` |
| `WhatsApp Payment Background Keys` | `payment-bg-image` |
| `WhatsApp Music Artwork Keys` | `music-artwork` |
| `waffle_hkdf_info` | `waffle-image`, `waffle-video`, `waffle-gif` |
| `PAYMENT_DOC_UPLOAD` | `payment-br-document` |
| `ads-image` / `ads-video` | `ads-image` / `ads-video` |

Anmerkungen (found): `ptt` und `audio` teilen sich die Audio-info, sind aber unterschiedliche Pfad-Strings; `sticker` nutzt die Image-info; `gif` und `ptv` nutzen die Video-info; mehrere `image`-Zeilen existieren mit unterschiedlichen numerischen ids (1, 23, 25, 37, 42, 44, 57; `sticker` ist 20) für unterschiedliche Call-Sites (Bedeutung der id unbekannt); `group-history` ist der einzige Eintrag, dessen info nicht die Form `WhatsApp <X> Keys` hat. Profilbilder (`ppic`) erscheinen nur im Route-Capability-Set und in Download-Generator-Aufrufen, nicht als `MmsType`.

---

## 4. Medienschlüssel und Ableitung

### 4.1 Schlüsselerzeugung (found)

| Punkt | Wert |
|------|-------|
| Medienschlüssel | 32 Zufallsbytes aus `SecureRandom` (`C57333Po0`, `QIh.A0B` ist `new SecureRandom()`) |
| Wiederverwendung | `MediaKeyGen/reuse key from message contents` wenn der Schlüssel jünger ist als `172800000 ms + SecureRandom.nextInt(86400000)` (2 bis 3 Tage, gejittert), gemessen gegen den gespeicherten Key-Timestamp; ältere Schlüssel werden verworfen (`key expired`) und neu erzeugt |
| Domain | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `AbstractC38961i0.A00` aufgerufen von `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01` weist jede andere Länge zurück (`Invalid length of derived secret`). Ciphertext-Länge: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (PKCS#5-gepaddete Blöcke plus 10 MAC-Bytes).

### 4.3 Nicht-E2EE-Medienschlüssel (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (Feld **74**, Nachricht `DQT`) trägt `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) und `e2eeMediaKey` (**2**). Mit Flag **24661** prüft der Empfänger, ob der Schlüssel in der Nachricht zur Domain passt (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); bei Mismatch fällt er auf den gegebenen Schlüssel zurück. Welche Produkte die NON_E2EE-Domain nutzen: unknown.

---

## 5. Verschlüsselung, MAC und Hashes

### 5.1 Cipher (found, `M2I`, `M23`, `N6U`)

| Schritt | Detail |
|------|--------|
| Cipher | `AES/CBC/PKCS5Padding`, Key = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, zuerst mit dem IV aktualisiert, dann mit jedem Ciphertext-Byte; die ersten **10** Bytes des Digests werden an den Ciphertext angehängt |
| `fileSha256` | SHA-256 über den Klartext (`P9M`-Digest-Stream über die Datei) |
| `fileEncSha256` | SHA-256 über Ciphertext + 10 MAC-Bytes |
| Ausgabe | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Entschlüsselungsseite (`P9N`, `M23`): MAC wird über IV + Ciphertext verifiziert, dann mit den letzten 10 Bytes verglichen. Ranged-Decrypt (`C51101MlN`): wenn der Range-Start nicht 0 ist, werden die ersten 16 gelesenen Bytes als IV genutzt (vorheriger Ciphertext-Block); innere Chunks nutzen `AES/CBC/NoPadding`, der letzte Chunk nutzt PKCS#5 (inferred aus der Cipher-Auswahl).

### 5.2 Timestamps und Pfade

| Feld | Wert |
|-------|-------|
| `mediaKeyTimestamp` | lokale Uhr in Millisekunden, im Key-Objekt gehalten, ins Protobuf als Sekunden geschrieben (`C20H.A06` = `/1000`) |
| `directPath` | server-zurückgegebener Pfad-String, in der Nachricht und in der DB-Spalte `direct_path` gespeichert; kann Query-Parameter tragen (z. B. wird `_nc_hot` daraus gelesen) |
| `url` | legacy vollständiges URL-Feld; existiert noch in Proto-Klassen und in der Upload-Antwort, aber der Download-Generator wird aus `directPath` oder aus dem Hash gebaut (Abschnitt 9.1) |

### 5.3 Optimistische Hash-Checks

`MediaUpload/optimistic-hash-fail` und `optimistic-plaintext-hash-fail` (Upload-Result 12) werden geloggt, wenn der vom Server gemeldete Hash vom lokal berechneten abweicht. Optimistischer Upload (Surface-String `optimistic`) lädt hoch, bevor der Send committed ist; sein Protokoll über den Surface-Namen hinaus: unknown.

---

## 6. Medien-Nachrichtenfelder

Feldnummern aus den generierten Protobuf-Klassen gelesen. Klassennamen werden anhand des Feld-Layouts zugeordnet (inferred); Nummern sind found.

| Nachricht (Klasse) | Feldnummern (Name = Nummer) |
|-----------------|-------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| History-Bundle (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

`Message`-Container (`C30628DTw`) Nummern (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage` ist Feld **21** des Containers `BD3`.

### 6.1 Thumbnails

| Art | Mechanismus (found, sofern nicht markiert) |
|------|---------------------------------|
| Inline | `jpegThumbnail`-Bytes (**16**) in der Nachricht (Image, Video, Document); `pngThumbnail` (**16**) in Stickers |
| Hochgeladen | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (Image **26-28**, Video **21-23**, Document **13-15**); `MmsType` `thumbnail-*` mit den Thumbnail-HKDF-infos aus Abschnitt 3 |
| Key | das Proto hat kein separates Thumbnail-Key-Feld, also wird ein Thumbnail mit dem Medienschlüssel seiner Nachricht verschlüsselt (inferred) |
| Server-erzeugt | Upload-Query `server_thumb_gen=1`; die Upload-Antwort kann `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` zurückgeben |
| DB | Tabelle `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming und Sidecars (found)

Ein Sidecar ist eine Liste von 10-Byte-MACs, einer pro Ciphertext-Chunk, die einem Player erlaubt, einen Bereich ohne Lesen der ganzen Datei zu verifizieren.

| Punkt | Detail |
|------|--------|
| Algorithmus | `P9N.read`: pro Chunk wird ein `HmacSHA256(macKey)` mit den **vorherigen 16 Ciphertext-Bytes** initialisiert (dem IV für den ersten Chunk), dem Chunk gefüttert, und die ersten 10 Bytes des Digests werden gespeichert |
| Konkatenation | `C57228PmG.A00` fügt alle 10-Byte-MACs in ein Byte-Array zusammen |
| Video / Audio | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); Chunk-Größe **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Progressives Bild | `firstScanSidecar` (**18**) mit `firstScanLength` (**19**): ein Chunk von `ceil(len/16)*16` Bytes; `scansSidecar` (**21**) mit `scanLengths` (**22**): variable Chunk-Größen (`P1Y`) |
| Sticker | `firstFrameSidecar` (**12**) mit `firstFrameLength` (**11**) |
| Einstellungen | Server-Prop `streaming_upload_chunk_size` ist ein Dictionary-Token; seine Wirkung: unknown |
| Fehlend | Download-Status 30 `failed_no_sidecar` |
| Server-Streaming | Upload-Query `stream=1` und `streaming=riff` gemeinsam (Abschnitt 8.1); DASH: `dashManifestUrl` (**33**), `metadataUrl` (**30**) in der Antwort |

---

## 8. Upload

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Teil | Wert |
|------|------|
| `surface` | `mms` (normal), `newsletter` (Channels), `optimistic` (Pre-Send-Upload); `AbstractC58025Pzy` |
| `type` | `MmsType`-Pfad-String (Abschnitt 3), z. B. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | Standard-Base64 von `fileEncSha256` mit `+` zu `-` und `/` zu `_`; das `=`-Padding wird beibehalten (`StringUtils.A0B`) |
| `direct_ip` | 1 wenn die Authority eine IP ist (`ip4`, oder geklammertes `[ip6]`), sonst 0 |
| `auth` | das `media_conn`-Auth-Token; als Query-Parameter von `K19.A03` hinzugefügt |
| `stream=1`, `streaming=riff` | beide gesetzt, wenn die Anfrage ein gestreamter Upload ist (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | nur für `newsletter-image` / `-status` (Flag **11191**) und `newsletter-video` / `-status` (Flag **11192**) |
| `server_transcode=1` | `newsletter-video` mit Request-id 10 und Flag **9096** |
| `_nc_rmr=1` | Nicht-Newsletter-Uploads (Request-Flag `A0N`) |
| `_nc_cbep=1` | wenn die Anfrage es erlaubt und Flag **17404** aktiv ist (Bedeutung unbekannt) |
| `type`, `media_id`, `media_id_upload` | `media_id` = die höchstwertigen 63 Bits einer Upload-UUID; `media_id_upload` = die niedrigstwertigen 63 Bits, nur wenn die Anfrage zusätzliche Einträge hat; `type` ist ein Caller-String (Bedeutung: unknown) |

Die Bedeutung der Query-Namen `_nc_cbep` und `_nc_rmr` ist unknown (nur Namen).

### 8.2 Token (found, `C43489Iy4.A00`)

| Fall | Token |
|------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`, frisch pro Anfrage, nicht an die Datei gebunden |
| Andere | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` sind 32 Bytes aus `SecureRandom`, einmalig erzeugt und in den Preferences gespeichert als `upload_token_random_bytes` (Base64 no-wrap, no-padding) |

Wenn `fileEncSha256` nicht dekodiert werden kann, ist das Token `SHA-256(installSecret)` allein. Zweck der Konstruktion: inferred als serverseitiger Check, dass der Uploader den Hash kennt, ohne ihn im Pfad offenzulegen.

### 8.3 HTTP-Anfrage (found, `HttpsFormPost` `C43478Ixt`)

| Punkt | Wert |
|------|------|
| Bibliothek | `HttpsURLConnection` mit einer benutzerdefinierten `SSLSocketFactory`; Marker `http_stack = HttpUrlConnection` |
| Methode | POST (`setDoOutput(true)` auf `HttpURLConnection`; kein expliziter Methoden-Aufruf) |
| Timeouts | Connect 15000 ms, Read 60000 ms |
| Header | `Host: <route hostname>` (die Authority kann eine IP sein), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, optional `Companion_User_Secret` (nicht-null Konstruktor-Argument; Companion-Semantik inferred) |
| Body (Route vorhanden) | roher Ciphertext-Stream, nur eine einzelne Datei (`MMS4 upload only supports a single file`); fixed-length Streaming-Modus, wenn die Länge bekannt ist, sonst chunked (`setChunkedStreamingMode(0)`); Puffer 16384 Bytes |
| Body (keine Route) | legacy `multipart/form-data` mit `Content-Disposition: form-data`-Teilen |
| Abbruch | bei Thread-Interrupt oder Cancel-Flag wird der Stream gepolstert (`UploadRequest/Post streaming padding bytes=`), sodass die deklarierte Länge erreicht wird (Zweck inferred) |
| Antwort | bis zu 1 MiB gelesen; HTTP >= 400 gibt den Code zurück, Body geht an `onError` |

### 8.4 Antwort (found, `MediaUploadTransfer` `C59523QnV`)

Gelesene JSON-Keys: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (nur akzeptiert, wenn er `[A-Za-z0-9-]{1,64}` entspricht), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (verschachtelter JSON-String mit `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. Eine Antwort ohne `direct_path` wird von diesem Parser nicht als Fehler behandelt; spätere Stufen scheitern mit `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Resumable Upload (found)

| Schritt | Detail |
|------|--------|
| Probe | dieselbe Upload-URL plus `resume=1` (`HttpResumeCheck`); JSON-Antwort `{"resume": "complete"}` mit `url`, `direct_path` (bereits hochgeladen) oder `{"resume": <offset>}` |
| Fortsetzen | POST mit `Content-Range: bytes <offset>-*/*`, der Stream wird zuerst zu `<offset>` gesprungen |
| Fallbacks | `ResumeCheck/attempting fallback MMS upload form post`, auch nach einem WATLS-(TLS-)Fehler |
| Parse-Fehler | Status `PBY.A03`, Upload startet neu |

### 8.6 Routen-Lieferant und Retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Regel | Detail |
|------|--------|
| Versuchsschleife | `TransferRetries/run attempt = N; route = ...`; ein Transfer pro Route; `no routes` beendet die Schleife |
| Host-Auswahl | `type=primary`-Host, dessen Capability-Set den Medientyp enthält; die ersten zwei Versuche nutzen ihn; spätere Versuche nutzen den `type=fallback`-Eintrag und dessen `fallback_*`-Felder (Reihenfolge inferred aus verwirrtem Kontrollfluss) |
| Versuche | Default 4 (`4 - extra`); mit Flags **12545** und **12446** kann das Limit nach Versuch 3 überschrieben werden; `max_auto_download_retry` / `max_manual_retry` (Default je 3) speist die modusabhängige Anzahl (Mapping inferred) |
| Verzögerung | konstant 1000 ms (`RouteSelector.A01`); mit Flag **257** und Extra-Versuchen exponentiell: Basis 1000 ms, `2^n`, Jitter, gekappt bei 3000 ms |
| Auth-Fehler 401 / 403 | gilt nicht als Fehlschlag: wartet auf ein neueres Token (Budget `A0J`, Default 20000 ms), tauscht, versucht erneut |
| Wiederholbarer HTTP-Status | `QKS.A08`: < 400 ja; 400-499 nein, außer 408 mit Flag **13748**; >= 500 ja, außer 505 und 507 |
| Proxy | mit einem Benutzer-Proxy und Flag **4073** wird die Medien-Authority zu Proxy-Host und -Port aus `proxy_media_port` (Default 587) |
| Health-Check | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, Connect 15000 ms, Read 30000 ms |

---

## 9. Download

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

Der Konstruktor erfordert einen Medienhash, einen direct path oder eine Cross-Referenz (`media hash, direct path, or cross reference is required`). `mode` ist `auto` oder `manual`. `_nc_map=whatsapp-nofna` wird für Typen in der Server-Liste `LOW_CACHE_HIT_RATE_MEDIA_TYPES` hinzugefügt (AB-Prop, Flag **4836**). Die `auth`-Query wird auf einem geflaggten Pfad hinzugefügt (`PTU.A03`) und ersetzt einen vorhandenen `auth`-Parameter. Profilbilder nutzen Typ `ppic`; statische Assets nutzen `/wa/static` mit `_nc_cat`.

### 9.2 Bucket- und Host-Auswahl (dekompilierter Kontrollfluss, teils verwirrt)

- Hosts werden nach `download`-Capability und nach `download_buckets`, die den Bucket-String enthalten, gefiltert.
- Bucket `1`, wenn der direct path `_nc_hot=<seconds>` trägt, jünger als das Fenster in Flag **2136**; sonst, mit Flag **2134** und `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); Fallback-Bucket `0`.
- Newsletter-Typen und geflaggte Fälle überspringen die Hot- / Hash-Logik.
- Der gewählte Bucket geht als `_nc_cat` heraus.

### 9.3 HTTP-Anfrage (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Punkt | Wert |
|------|------|
| Methode | GET (Tigon oder `HttpURLConnection`) |
| Header | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (flag-gesteuert), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (wenn ein ETag bekannt ist) |
| Akzeptiert | HTTP 200 und 206 |
| Teilweise | Previews nutzen ein Präfix von 262144 Bytes (`Range: bytes=0-262143`) |
| 416 | als vollständig behandelt, wenn `Content-Range` `*/<size>` ist und der lokalen Größe entspricht; sonst Neustart (Flag **29305**) oder Fehler |
| Allow-List | mit Flag-Symbol `PTU.A04` muss der Host in `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` liegen (Suffix-Match), außer die URL hat `category=PSA`; sonst `invalid_url` (8) / Log `host not in media CDN allow-list` |

### 9.4 Verifikation (found)

Der Decrypt-Stream prüft den MAC; Hash-Stufen mappen auf die Status 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; fehlende Eingaben mappen auf 26-30 (Abschnitt 10.2).

---

## 10. Fehlercodes

### 10.1 HTTP-Status-Behandlung

| Status | Verhalten |
|--------|-----------|
| 401, 403 | `media_conn` refreshen, Auth tauschen, erneut versuchen (max. 2 Tausche) |
| 408 | nur mit Flag **13748** erneut versuchen |
| 416 | siehe 9.3 |
| 507 | Download-Status 12 `throttle`, nicht erneut versucht |
| 505 | nicht erneut versucht |
| andere 4xx | nicht erneut versucht |
| 5xx, < 400 | innerhalb des Versuchs-Budgets erneut versucht |

### 10.2 Download-Status (found, `QKK` `A03`)

| Code | Name | Code | Name |
|------|------|------|------|
| 0 | success | 17 | wamsys_failed |
| 1 | failed_generic | 18 | failed_network |
| 2 | dns_failure | 19 | failed_connect |
| 3 | timeout | 20 | host_switch_required |
| 4 | disk_full | 21 | suspicious_content |
| 5 | too_old | 23 | partial_image_downloaded |
| 6 | resume_failed | 24 | programmatic_cancel |
| 7 | hash_mismatch | 25 | failed_no_client_network |
| 8 | invalid_url | 26 | failed_no_encryption_algorithm |
| 9 | output_stream_fail | 27 | failed_no_encrypted_hash |
| 11 | no_route | 28 | failed_no_media_hash |
| 12 | throttle | 29 | failed_no_media_key |
| 13 | user_cancel | 30 | failed_no_sidecar |
| 14 | prefetch_end | 31 | failed_hash_verification |
| 15 | watls_error | 32 | enc_hash_mismatch |
| 16 | server_error | 34 | deduped |

Codes 10, 22, 33 und alles andere drucken `invalid`. `QKK.A04` gruppiert 1, 2, 3, 11, 15, 16, 18, 19, 20 und 25 (netzwerkartige Fehlschläge; das Label ist inferred).

### 10.3 Upload-Ergebnis (found, Metriknamen `media_upload_<NAME>`)

| Code | Name | Code | Name |
|------|------|------|------|
| 1 | CANCEL | 22 | FAILED_DNS_LOOKUP |
| 2 | FAILED_INSUFFICIENT_SPACE | 23 | FAILED_WAMSYS |
| 3 | FAILED_IO | 24 | FAILED_TOO_LARGE |
| 4 | FAILED_OOM | 25 | ERROR_NO_CLIENT_NETWORK |
| 5 | FAILED_BAD_MEDIA | 26 | HOST_SWITCH_REQUIRED |
| 6 | FAILED_NO_PERMISSIONS | 27 | SKIPPED_EP_NO_PRIMARY_HOST |
| 7 | FAILED_FNF | 28 | FAILED_CRONET |
| 8 | FAILED_SERVER | 29 | FAILED_NO_DIRECT_PATH |
| 9 | FAILED_REQUEST | 30 | FAILED_NO_MEDIA_KEY |
| 10 | FAILED_REQUEST_TIMEOUT | 31 | FAILED_UNKNOWN |
| 11 | FAILED_NOT_FINALIZED | 32 | CANCEL_PROGRAMMATIC |
| 12 | FAILED_OPTIMISTIC_HASH | 33 | FAILED_NO_ROUTE |
| 13 | FAILED_MEDIA_CONN | 34 | FAILED_CANNOT_TRANSCODE |
| 14 | FAILED_OPTIMISTIC_NETWORK_UNSAFE | 35 | FAILED_UNKNOWN_MIMETYPE |
| 15 | FAILED_THROTTLE | 36 | FAILED_SERVER_REJECTED_MEDIA |
| 16 | FAILED_NO_SUCH_ALGORITHM | 37 | FAILED_IO_ENCRYPTION |
| 17 | FAILED_NETWORK | 38 | FAILED_STREAMING_METADATA_TOO_LARGE |
| 18 | FAILED_WATLS | 39 | FAILED_MUSIC_REPORTING |
| 19 | FAILED_URL | 20 / 21 | FAILED_TRANSCODING_UNKNOWN / FAILED_FILE_FORMAT_UNSUPPORTED |

Exception-Mapping in `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, andere `IOException` 18 (Netzwerk down) oder 3, `CancellationException` 1, `C7CL` 21, alles andere 31. Nach einem nicht erfolgreichen Ergebnis mit 5, 21, 24, 34, 35 oder 36 werden der gecachte Key und Hash (`A0B`, `A0C`) gelöscht.

---

## 11. Media-Retry (Re-Upload-Anfrage)

Wenn ein Download fehlschlägt, weil das Objekt verschwunden ist (typischerweise Status 5 `too_old`, oder eine 404-artige Antwort), fragt der Empfänger das Telefon des Senders, erneut hochzuladen.

### 11.1 Anfrage: Receipt `server-error` (found, `SendMediaErrorReceiptJob`)

| Variante | Writer | Wire |
|---------|--------|------|
| Multi-Device (eigener Primary) | Fall 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Legacy | Fall 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (ohne `rmr`) |

`enc_iv` sind 12 Zufallsbytes; `enc_p` wird native erzeugt (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) aus einer Nachricht, die die Stanza-id trägt. Die native Bibliothek hält die HKDF-info `WhatsApp Media Retry Notification`; AES-GCM mit der Stanza-id als AAD und einem 32-Byte-HKDF-Key ist inferred aus der 12-Byte-IV und aus der Baileys-Implementierung. Server-Props `mms4_media_retry_notification_encryption_enabled` und `mms4_server_error_receipt_encryption_enabled` sind Dictionary-Tokens (Wirkung inferred: steuern, ob `<encrypt>` gesendet wird).

### 11.2 Antwort: Notification `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Schritt | Detail |
|------|--------|
| Account-Check | `rmr` von einem anderen Account loggt `cross-account-rmr` und wird verworfen, außer Flag-Symbol `PTV.A0F` ist aktiv |
| Lookup | Nachricht über `(chat, id, from_me)`; Nicht-Medien-Nachrichten loggen `message is null or not media` |
| Entschlüsseln | native (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); das Ergebnis-Modell liefert `directPath` (in der Nachricht gespeichert) und ein Ergebnis-int |
| Ergebnis | `<error code>` überschreibt das Ergebnis; der Handler vergleicht den Wert mit 2 und 3 (mit der öffentlichen Proto-Nummerierung `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferred) |
| Fortsetzen | der Downloader bekommt den neuen direct path (`resume reuploading download`); ohne aktiven Downloader wird die Nachricht für Auto-Download eingereiht |
| Reporting | mit Flag **5718** wird der `reporting_token` für die Nachricht gespeichert |

---

## 12. View-Once- und Status-Medien

| Thema | Fakt (found) |
|-------|--------------|
| Krypto / Transport | identisch zu normalen Medien: derselbe `MmsType`, dieselbe HKDF, dieselben URLs; es gibt keinen View-Once-Typ in der Tabelle |
| Flag | `viewOnce` ist ein Feld in `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); Container `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Lokale Regeln | der Sender kann seine eigenen View-Once-Medien nicht öffnen (`senders can not view their own media`); View-Once-Thumbnails werden von `EphemeralUpdateRunnable/deleteViewOnceThumbnails` gelöscht; ein View-Once-Audio ohne Medienschlüssel wird nicht gesendet (`unable to send encrypted media message due to missing mediaKey`) |
| Ob der Server das Objekt nach dem Ansehen löscht | unknown |
| Status (`status@broadcast`) | nutzt die normalen `MmsType`-Zeilen (Image, Video, Gif, Audio) mit ihren eigenen numerischen ids; es existiert keine `status`-HKDF-info; die einzigen `*-status`-Typen sind die Newsletter-Typen (Abschnitt 13) |
| Status-Limits | Dictionary-Tokens `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` sind Server-Props (Werte: unknown) |
| Status-Download | `C59526QnY` hält einen `MediaDownload` und eine `StatusMediaDownload`-Variante; beide bauen die URL mit demselben Generator |

---

## 13. Newsletter-(Channel-)Medien

| Aspekt | Newsletter | Regulär |
|--------|-----------|---------|
| Surface in der URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | normale Namen |
| Verschlüsselung | keine: der Artwork-Downloader erfordert `artworkEncSha256` nur für nicht-Newsletter-Inhalte (`required fields missing - artworkEncSha256 is null for encrypted content`); für andere Typen existiert der Passthrough-Stream `C59535Qnh` (Identität). Die `MmsType`-Zeilen tragen weiterhin HKDF-info-Bytes (unbenutzt, inferred) |
| Upload-Token | zufällig, nicht hash-gebunden (Abschnitt 8.2) | pro-Installation-Secret + Hash |
| Routen-Filter | keine Hot- / Hash-Bucket-Logik für Namen, die mit `newsletter` beginnen | Bucket-Logik (9.2) |
| `media_conn` ip-Token | `ip_token` wird für Newsletter unabhängig von `set_ip_token` angewendet (Flag **12149**) | nur wenn `set_ip_token` true ist |
| Server-Arbeit | `server_thumb_gen=1` (Flags **11191**, **11192**), `server_transcode=1` für Video (Flag **9096**) | nicht gesetzt |
| Flag **27920** | im Newsletter-Pfad von `C15490gQ` gelesen; Wirkung unbekannt | |

---

## 14. Express-Pfad und andere Upload-Varianten

| Variante | Beleg |
|---------|----------|
| Express-Pfad | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) als E2E-Nachricht gesendet (`FMessageMediaExpressPathNotify`, erfordert url, hash und length); `ExpressPathDownload` loggt `EP gain <ms> <bytes>`; Upload-Log `Use static route supplier for express path upload`; Upload-Ergebnis 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Serverseitiges Verhalten: unknown |
| Optimistischer Upload | Surface `optimistic`; Hash-Re-Check-Ergebnis 12; Protokoll: unknown |
| History / App-State | `md-msg-hist`, `md-app-state` nutzen die normale Pipeline mit ihren info-Strings |
| Group History | `group-history`, info `Group History`, mime `application/protobuf`, vom Empfänger geprüft (`C34677F2y`); Pfad folgt Abschnitt 8.1 (`/mms/group-history/...`, inferred aus der generischen Komposition) |

### 14.1 Chat-Theme-Wallpaper-Versand (neu in 2.26.45.10, found)

Ein Pro-Chat-Theme-"an Chat senden"-Flow fährt diese generische Pipeline unverändert. Einstiegspunkt: `ChatThemeViewModel.sendThemeToChat` (Kotlin-Coroutine; lokale Variablen `targetJid`, `sentBundle`, `sharedTheme` aus erhaltener Debug-Metadaten) löst die gewählte Wallpaper-Quelle auf (`DOWNLOADED`, `USER_PROVIDED`, `ANIMATED`, `GRADIENT`, `DEFAULT`, `NONE`) und ruft `ChatThemeSettingSenderImpl.A06` → `A01`.

| Schritt | Detail (found) |
|------|-----------------|
| Lokale Kopie | die Quell-Wallpaper-`File` wird in den App-Speicher unter `chat_theme_sent_wallpapers/<uuid>.jpg` kopiert |
| Upload | `ChatWallpaperUploader.A00` umschließt `MediaUploadCoordinatorImpl.A0G` (dieselbe `media_conn` → HKDF → AES-CBC → HMAC → POST-Pipeline wie Abschnitt 1-8 oben), fordert Verschlüsselungsmodus `LX/8cp;->A02`, dessen `value`-Feld der literale String `"E2EE"` ist |
| Ergebnis-Kopie | das Upload-Ergebnis (`SGq`) wird Feld für Feld in einen generischen Medien-Anhang-Deskriptor (`LX/8cr`) kopiert: Upload-Ergebnis-String → direct path, Medienschlüssel-Bytes, ein Timestamp, und drei weitere Hash/HMAC-Byte-Arrays |
| Setter-Oberfläche | der Deskriptor wird durch `LX/1iA` (erweitert `LX/19i`) geschickt, die **gleiche generische Medien-Anhang-Setter-Schnittstelle**, die normale Image-Message-Builder nutzen; ihre Felder liegen positionell mit `imageMessage`'s `directPath` (**11**), `mediaKey` (**8**) und den `fileSha256`/`fileEncSha256`-Byte-Feldern (**9**/**12**, Abschnitt 6) deckungsgleich |
| Mimetype | `image/jpeg` wird explizit beim gleichen Aufruf gesetzt |

Dies wird an einen echten Chat-Partner (`targetJid`) gesendet, nicht als rein lokale Anzeige-Präferenz-Synchronisierung: bei bildbasierten Themes wird das Wallpaper-Bitmap selbst neu enkodiert und über den Standard-E2EE-Medienpfad hochgeladen, sodass der empfangende Client ein echtes Bild herunterlädt und entschlüsselt statt ein bekanntes Theme-Preset anzuwenden. Kein eigenständiger Upload-Medientyp oder HTTP-Pfad-Override (anders als bei Group-History's `/mms/group-history`, Abschnitt 14) wurde für diesen Flow gefunden — er scheint einen existierenden `MmsType` wiederzuverwenden (vermutlich `image`, nicht separat bestätigt).

**Unknown**: das exakte `Message`-oneof-Feld, in dem dieser Anhang letztlich landet — `LX/19i`/`LX/1iA` sind große gemeinsam genutzte Basisklassen, die von vielen ausgehenden Nachrichtentypen verwendet werden, und die konkrete Allokationsstelle hinter ihren Settern wurde in diesem Pass nicht erreicht. Ebenfalls unknown: ob eine Solid-Color-/Kein-Wallpaper-Theme-Auswahl (`DEFAULT`/`NONE`) überhaupt gesendet wird, oder lokal bleibt. Kein neuer Protobuf-Nachrichtentyp oder GraphQL/MEX-op wurde für dieses Feature gefunden (geprüft gegen die 2.26.41.6→2.26.45.10-Proto- und Query-Diffs); die vertretbarste Lesart ist, dass dies ein existierendes Medien-Nachrichtenfeld nutzt, höchstwahrscheinlich `imageMessage` selbst — **inferred**, nicht bestätigt.

---

## 15. Native Hardening der Medienparser (found, Strings und Exports der entpackten Bibliotheken)

81 Shared Objects werden aus dem Superpack-Archiv entpackt. Speicherunsichere Parser für angreifer-kontrollierte Bytes sind entweder sandboxed oder durch Rust ersetzt.

| Eingabe | Komponente | Hardening |
|-------|-----------|-----------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp zu WebAssembly kompiliert und von wasm2c zu C heruntergebrochen (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), Wrapper `whatsapp::security::LibwebpSandbox` in einer Thread-lokalen Sandbox; Java-Flag `sWebPSandboxEnabled`; Fehler-Log `sandboxed WebP decode failed: status=%d`; Guards `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib in einer wasm2c-/WASI-minrt-Sandbox (`GiflibSandbox`, `wasi::minrt`); JNI-Klassen `SandboxedGifImage`, `SandboxedGifFrame`; Guard `Called memcpy for memory larger than the sandbox` |
| Ogg / Opus-Dateien | `libwhatsapp.so` | RLBox-wasm2c-Sandboxes für `libogg.wasm` und `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; Trap-Log `wasm2c sandbox trap: %s (code=%d)` |
| Container- und Stream-Parsing | `libwhatsapp.so` Rust-Crates | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, DASH-Segmenter, Edit-Listen), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (IPTC digital-source-type-Werte wie `trainedAlgorithmicMedia`, C2PA) |
| AV1-Decode | `libdav1d.so` | dav1d **1.5.1** (Versions-String); exportiert die `dav1d_*`-API |
| AV1-Encode | `libwzav1.so` | Version 2.3.1; exportiert nur `wz_encoder_*` und `wz_codec_version*`; keine Decoder-Symbole, parst also keine Remote-Bitstreams |
| H.264 / H.265-Frames | Plattform-`MediaCodec` | außerhalb der App |

Parser in Rust scheitern mit Panics (`assertion failed: ...`, `While parsing field '...' in ...`) statt Speicherkorruption: found als Strings, Wirkung inferred. Die `rlbox`-Sandbox deckt libogg und opusfile in `libwhatsapp.so` ab; andere Bibliotheken nutzen wasm2c ohne den RLBox-Wrapper (inferred aus den Symbolen). Ob jeder eingehende Medienpfad diese Parser vor der Nutzerinteraktion erreicht: unknown. Dynamisches Verhalten (Fuzzing, Laufzeit-Abstürze): nicht getestet.

---

## 16. Feature-Flags (ids wie an den Call-Sites gelesen; Namen unaufgelöst)

| Flag | Wo | Steuert |
|------|-------|----------|
| **149** | `RouteSelector`, `C43951qe` | persistiert und lädt `media_conn` in den Preferences |
| **257** | `Mms4RouteSupplier`-Konstruktor | Exponential-Backoff-Objekt |
| **258** | `Mms4RouteSupplier.A03` | int: Extra-Versuche für Modus 0 |
| **2134** | `A02` | hash-basierter Download-Bucket |
| **2136** | `A02` | Hot-Content-Fenster (long) |
| **4073** | `A00` | leitet Medien über den Benutzer-Proxy |
| **4836** | `Mms4DownloadUrlGenerator` | Liste der Low-Hit-Rate-Typen (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | Reporting-Token-Behandlung |
| **9096** | `QBE` | `server_transcode=1` (Newsletter-Video) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` für Newsletter-Image / -Video |
| **12149** | `RouteSelector.A0L`, `A03` | nutzt `ip_token` |
| **12545** / **12446** | `A05` | überschreibt das Versuchslimit nach Versuch 3 |
| **13748** | `QKS.A08` | wiederholt HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | `RouteSelector`-Einstiegspunkte | Boolean, der der Routenauswahl als Upload-Flag übergeben wird (Semantik unaufgelöst) |
| **24661** | `MediaCryptoProvider` | Nicht-E2EE-Key-Domain-Validierung |
| **29305** | `PlainDownloadTransfer` | 416-Behandlung |
| **37982**, **38437** | `C43481Ixw` | Tigon-Property, Request-Timeout |

---

## 17. Baileys (`baron-baileys-v2`, Quelle gelesen, nichts getestet)

| Aspekt | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| `media_conn`-Anfrage | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` hat eine optionale `last_id`-Variante | immer `<media_conn>`, mit `last_id`, wenn eine vorherige id existiert |
| Geparste Felder | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | kein `maxContentLengthBytes` gelesen; fügt `auth_ttl`, `max_buckets`, `is_new`, `id`, Fallback-Felder, Capability-Kinder, Retry-Zähler, `ip_token` hinzu |
| HKDF-Länge | `hkdf(key, 112, {info})`, nutzt Bytes 0-79 | 80 Bytes; die ersten 80 Bytes einer HKDF-Ausgabe hängen nicht von der angeforderten Länge ab, also sind IV, Cipher-Key und MAC-Key identisch |
| info-Strings | `WhatsApp <X> Keys`; `gif` und `ptv` mappen auf Video, `ptt` auf Audio, `sticker` auf Image | gleiche Strings und Mappings |
| Cipher, MAC, Hashes | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` angehängt, `fileSha256`, `fileEncSha256` über `ct + mac` | gleich |
| Upload-URL | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Hash-Encoding | url-safe Base64, `=`-Padding entfernt, dann `encodeURIComponent` | url-safe Base64, `=`-Padding beibehalten |
| Token | url-safe `fileEncSha256` | `SHA-256(installSecret || fileEncSha256)` (Newsletter: zufällig) |
| Pfad-Tabelle | `sticker` und `thumbnail-link` zu `/mms/image`, `ptv` zu `/mms/video`, `md-msg-hist` zu `/mms/md-app-state`, kein `ptt` | der `MmsType`-String ist das Pfadsegment: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Header | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | kein `Origin` gefunden; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | versucht jeden Host einmal in Reihenfolge | Routen-Lieferant mit Versuchen, 401 / 403-Token-Tausch, Resume-Probe |
| Resume | nichts gefunden (`resume=1`, `Content-Range` fehlend) | `resume=1`-Probe und `Content-Range` |
| Sidecars | keine `streamingSidecar`-, `firstScanSidecar`- oder `scansSidecar`-Erzeugung in `src` gefunden | erzeugt für Video, Audio, progressive Bilder |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | intern Millisekunden, im Proto Sekunden |
| Retry-Receipt | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = Stanza-id, IV 12 Bytes, HKDF-info `WhatsApp Media Retry Notification` | Writer-Fall 327 hat das gleiche Node-Layout; IV 12 Bytes und der info-String sind found; GCM / AAD inferred |
| Retry-Ergebnis-Mapping | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | nicht anwendbar (vergleicht Werte 2 und 3) |

Praktische Konsequenzen (nur Quelle gelesen): ein Baileys-Upload eines `md-msg-hist`-Objekts nutzt einen anderen Pfad-String als der Android-Client; gepolstertes Base64 im Pfad ist ein sichtbarer Unterschied; jegliche Server-Toleranz für diese Varianten ist unknown.

---

## 18. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|-------|-----|
| Upload 401 / 403 | `auth` abgelaufen oder ersetzt | `media_conn` refreshen, mit neuem `auth` erneut senden |
| Upload liefert keinen `direct_path` | Upload abgelehnt oder unvollständig | Status prüfen; Resume-Probe mit `resume=1` |
| Download 404 / Status 5 `too_old` | Objekt auf dem CDN abgelaufen | `server-error`-Receipt senden (Abschnitt 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | korrumpierte Bytes oder falscher `fileEncSha256` | neu abrufen; Hash-Quelle verifizieren |
| MAC-Check schlägt fehl | falscher Medienschlüssel, falsche HKDF-info (Typ-Verwechslung), oder abgeschnittene Datei | den info-String des richtigen `MmsType` nutzen; Image-info nicht für `sticker-pack`- oder `ptt`-Zeilen wiederverwenden |
| `invalid_url` (8) | Host außerhalb der CDN-Allow-List | nur die gelisteten Suffixe akzeptieren |
| `throttle` (12), HTTP 507 | Server-Throttle | `backoff`-Sekunden abwarten (max. 10800) |
| `no_route` (11) | kein nutzbarer `media_conn`-Host für den Typ | `media_conn` anfragen, Capability-Tags prüfen |
| `failed_no_media_key` (29), `no_sidecar` (30) | Proto-Feld fehlt | `mediaKey` erfordern; Sidecar nur für Streaming |

---

## 19. Abgrenzungen

| Nicht verwechseln | Fakt |
|----------------|------|
| `media_conn`-Hostliste vs. Upload-URL | die IQ liefert Hosts und einen `auth`; der URL-Pfad, Token und Query werden pro Transfer gebaut |
| `auth` vs. `token` | `auth` ist das Account-Level-Token aus `media_conn`; `token` ist pro Datei |
| HKDF 80 vs. 112 Bytes | gleiche Keys; Android leitet 80 ab |
| `fileSha256` vs. `fileEncSha256` | Klartext-Hash vs. Hash von `ciphertext + mac10` |
| `fileEncSha256` im Pfad vs. `directPath` | der Upload-Pfad nutzt den Hash; der Download nutzt den server-zurückgegebenen `directPath` |
| `mediaKeyTimestamp` vs. Wiederverwendungsfenster des Keys | Timestamp in Sekunden auf der Leitung; Wiederverwendungsfenster 2-3 Tage auf dem Sender |
| Streaming-Sidecar vs. `fileEncSha256` | Per-Chunk-10-Byte-MACs vs. Gesamtdatei-Hash |
| Media-Retry vs. Resend | der Sender lädt dasselbe Objekt erneut hoch und antwortet mit einem neuen `directPath`; die Nachricht wird nicht erneut gesendet |
| Newsletter-Medien vs. reguläre Medien | unverschlüsselt, Surface `newsletter`, zufälliges Token |
| `libwzav1` vs. `libdav1d` | Encoder vs. Decoder; nur der Decoder parst Remote-Daten |

---

## 20. Vollständiger Flow (Senden und Empfangen eines Bildes)

```
[Sender app]  pick file → process (resize, strip) → MmsType "image"
     │
     ▼
[RouteSelector]  media_conn fresh? (conn/auth > 120 s left) ── no ──► <iq xmlns="w:m" type="set"><media_conn last_id/></iq>
     │                                                                   │ ◄── auth, ttl, auth_ttl, max_buckets, hosts
     ▼
[Uploader]  mediaKey = 32 B SecureRandom ; okm = HKDF(mediaKey, "WhatsApp Image Keys", 80)
     │  iv | cipherKey | macKey ; AES-CBC encrypt ; mac10 = HMAC(macKey, iv||ct)[0:10]
     │  fileSha256 (plain), fileEncSha256 (ct||mac10) ; optional sidecar / thumbnails
     ▼
[Mms4RouteSupplier]  host: type=primary, upload set has "image"
     │  POST https://host/mms/image/<hash>?direct_ip=0&token=<sha256(secret||hash)>&auth=<auth>
     │      Host, Accept-Encoding: identity, body = ct||mac10   (resume: ?resume=1, Content-Range)
     ▼
[Media server]  (not observed) ──► {"url","direct_path","handle","ts",...}
     │
     ▼
[Sender]  ImageMessage{mediaKey, fileSha256, fileEncSha256, directPath, mediaKeyTimestamp(s), jpegThumbnail, ...}
     │  Signal-encrypted message over chatd
     ▼
[Receiver]  host from media_conn (download set + bucket _nc_cat)
     │  GET https://host<directPath>?direct_ip=0&_nc_cat=<b>&mode=auto
     │      Range: bytes=0-   (200 or 206)
     ▼
[Receiver]  check enc hash → MAC → AES-CBC decrypt → check fileSha256 → store
     │
     ├── object gone (404 / too_old) ──► <receipt type="server-error"><encrypt enc_p enc_iv/><rmr/></receipt>
     │                                         │
     │                                [Sender phone] re-uploads, answers
     │                                         ▼
     └──────────────────────────────── <notification type="mediaretry"><encrypt enc_p enc_iv/></notification>
                                         → new directPath → resume download
```

---

## 21. Unknowns

| Punkt | Status |
|------|--------|
| Serververhalten (Token-Validierung, Deduplizierung, Objekt-Lebensdauer, View-Once-Löschung) | serverseitig |
| Query-Namen `_nc_cbep`, `_nc_rmr`, `type`; Flag **21807** und die `PTU.*`-ids | Namen oder Bedeutung unaufgelöst |
| Numerische ids in `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | Bedeutung unaufgelöst |
| Native Media-Retry-Chiffre (AES-GCM, AAD, Schlüssellänge) | info-String found; Algorithmus inferred |
| `ip_token`-Verwendung, `X-FB-nc-oc`-Wert, `Companion_User_Secret`-Quelle | unaufgelöst |
| Verwendung der NON_E2EE-Medienschlüssel-Domain | unaufgelöst |
| Express-Pfad- und optimistische Upload-Protokolle | unaufgelöst |
| Exakte Host-Reihenfolge über Versuche und die modusabhängigen Versuchszähler | dekompilierter Kontrollfluss verwirrt |
| Welche eingehenden Medien welchen sandboxed Parser vor der Nutzerinteraktion erreichen | nicht abgebildet |
| Traffic | nichts mitgeschnitten; kein dynamischer Test |
