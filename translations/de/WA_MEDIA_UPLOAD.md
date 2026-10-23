<!-- src-sha1: a94958787eccb3db407fbb92cf700d9a4d424f4a -->
# WhatsApp Medien-Upload — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** Android-Medientransfer: `media_conn`-IQ (Hosts, Auth, ttl, Buckets, Fallback-Hosts), Aufbau der Upload- und Download-URL sowie HTTP-Parameter, Medientyp-Tabelle mit HKDF-Info-Strings, Erzeugung und Ableitung des Media-Keys, AES-CBC- + HMAC-Verschlüsselung, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, Thumbnails, Streaming-Sidecars für Video / Audio / progressive Bilder, fortsetzbarer Upload, Routenauswahl, Retry und Backoff, Upload- und Download-Fehlercodes, Media-Retry-Receipt und `mediaretry`-Notification, View-once- und Status-Medien, Newsletter-Medien (Channels), Express Path, clientseitige native Härtung der Medien-Parser, Baileys-Vergleich

---

## 1. Was es ist (technisch)

Medien laufen nie durch den chatd-Stream (siehe [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Eine Nachricht enthält nur eine Protobuf-Referenz (Key, Hashes, `directPath`); die Bytes gehen über separate HTTPS-Verbindungen zu Medien-Hosts. Chatd liefert genau eines: die `media_conn`-IQ, die Hostnamen und ein kurzlebiges Upload-Auth-Token ausgibt. Alle Aussagen stammen aus statischer Analyse des dekompilierten APK und der entpackten nativen Bibliotheken; auf der Leitung wurde nichts mitgeschnitten. Tiers: **found** = in Code oder Strings gelesen, **inferred** = abgeleitet, **unknown** = nicht aufgelöst.

| Schicht | Name in 2.26.41.6 | Rolle |
|---------|-------------------|-------|
| Route selector | `RouteSelector` (`C10950Wx`) | hält das aktuelle `media_conn`-Ergebnis, Refresh-Timer, Throttle, Route-Factory |
| `media_conn`-Parser | `C43951qe` (IQ-Result-Handler), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | parst `<media_conn>` / `<host>` |
| Route supplier | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (statische Supplier) | wählt pro Versuch einen Host, tauscht das Auth-Token |
| Retry-Treiber | `TransferRetries` (`C44566Jd2`) | Versuchsschleife um einen Transfer |
| Medientyp-Tabelle | `MmsType` (`C15530gU`) | pro Typ: Pfad-String, HKDF-Info-Bytes, numerische ID |
| Key-Provider | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF 80 Bytes, Non-E2EE-Domain-Key |
| Cipher-Streams | `M2I` (Verschlüsselung ausgehend), `M23` (Verschlüsselung eingehend), `P9N` / `P1X` / `P1Y` (Sidecar-MACs), `C51101MlN` (Ranged-Entschlüsselung) | AES-CBC + HMAC |
| Upload-Treiber | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (Key-Wiederverwendung), `C57333Po0` (Key-Erzeugung + Hashes) | Hashes, Sidecars, Upload-Orchestrierung |
| Upload-URL | `C43489Iy4` | `/surface/type/hash?...` |
| Download-URL | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) Upload; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) Download | Transport |
| Resume-Probe | `HttpResumeCheck` (`C59524QnW`) | fragt den Server, wie viele Bytes er hat |
| Retry-Receipt | `SendMediaErrorReceiptJob`, Writer-Cases 77 und 327 in `HandlerThreadC21920sG` | fordert vom Sender einen erneuten Upload an |
| Retry-Notification | `MediaRetryNotificationHandler` (`C1S0`, Notification-Code 97) | verarbeitet die Antwort |
| Nativ | `libwhatsapp.so` (Rust-Media-Crates, RLBox-Sandboxes), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | Parser und Decoder |

Punkte, die den Rest des Reports bestimmen:

- Android leitet **80** Bytes aus dem Media-Key ab (IV 16, Cipher-Key 32, MAC-Key 32), nicht 112 (Abschnitt 4).
- Der HTTP-Pfad ist `/{surface}/{type}/{urlSafeFileEncSha256}`, wobei `type` der `MmsType`-String des Mediums ist (`image`, `ptt`, `md-msg-hist`, ...), keine grobe Klasse (Abschnitt 8.1).
- Das Android-Upload-`token` ist nicht der Datei-Hash, sondern ein SHA-256 über ein Geheimnis pro Installation und den Datei-Hash (Abschnitt 8.2).
- Newsletter-Medien (Channels) teilen sich denselben Code, nutzen aber die Surface `newsletter` und ein zufälliges Token; sie sind unverschlüsselt (found für den Artwork-Pfad, inferred für den Rest, Abschnitt 13).
- Download-Hosts werden nach einem aus dem Datei-Hash abgeleiteten Bucket gefiltert (Abschnitt 9.2).

---

## 2. `media_conn`-IQ

### 2.1 Request (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout 32000 ms. Es ist immer nur ein Request in Flight (`inFlightMediaRoutingRequestTime`); ein zweiter Aufruf loggt `not sending request` und kehrt zurück. Ein globaler Throttle (`ChatdMediaThrottleManager`) kann den Aufruf unterdrücken (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Response (found, `C43951qe.CFS`)

| Node / Attribut | Typ | Verwendung |
|-----------------|-----|------------|
| `media_conn@auth` | string, erforderlich | Upload-Auth-Token (`auth`-Query-Parameter) |
| `@ttl` | Sekunden | Lebensdauer der Verbindung; Ablauf = Sendezeit + ttl * 1000 |
| `@auth_ttl` | Sekunden | Lebensdauer des Auth-Tokens; Ablauf = Sendezeit + auth_ttl * 1000 |
| `@max_buckets` | long, Default 0 | Modulus für den Download-Bucket (Abschnitt 9.2) |
| `@is_new` | int, Default 1 | 1 = Host-Liste ersetzen; sonst vorherige Hosts behalten und nur Token und ttl übernehmen (`previous hosts retained`) |
| `@id` | string | als `last_id` gespeichert, im nächsten Request zurückgesendet |
| `@max_auto_download_retry` | int, Default 3 | Retry-Budget für automatische Downloads |
| `@max_manual_retry` | int, Default 3 | Retry-Budget für manuelle Downloads |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | geparst und gecacht; `ip_token` wird nur verwendet, wenn Flag **12149** an ist und `set_ip_token` true ist (Verbrauchsstelle: unknown) |
| `host` (wiederholt) | node | ein Routeneintrag |

`host`-Attribute (found): `hostname` (erforderlich), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` oder `fallback`; alles andere wird zu `primary`), `force_ip` (`"true"`). Kinder: `<upload>`, `<download>`, `<download_buckets>`; die Tag-Namen der Kinder sind die Capability-Einträge. `upload` und `download` behalten nur Tags, die in einer festen Menge von 34 Medientyp-Strings vorkommen (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, die `newsletter-*`-Familie und die `thumbnail-*`-Familie); `download_buckets` bleibt ungefiltert.

Ein Routen-Host ist nur nutzbar, wenn sein Hostname auf `.whatsapp.net` endet (`Mms4RouteSupplier.A06`, wird auch auf `fallback_hostname` angewendet).

### 2.3 Caching und Refresh (found)

| Regel | Wert |
|-------|------|
| Persistenz | mit Flag **149** wird das Ergebnis als JSON gespeichert (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) unter `route_selector_prefs` / `media_conn`; einmal geladen, nur verwendet, wenn das Auth noch nicht abgelaufen ist |
| Refresh-Check | vor einem Transfer: läuft Verbindung oder Auth innerhalb von 120000 ms ab, wird eine neue IQ gesendet und bis zu 20000 ms gewartet (`requestroutesandwaitforauth`) |
| Timer | `auth expiry - 60000 ms` nach jedem Ergebnis; Foreground (`BgG`) setzt ihn neu |
| Auth-Fehler | HTTP 401 oder 403 bei einem Transfer löst einen Refresh aus (`onmediatransfererrororresponsecode`), maximal 2 Token-Wechsel pro Transfer (`JW1.A00 < 2`), danach wird der Versuch mit dem neuen `auth` wiederholt |
| Auth vor dem Versuch | `refreshAuthBeforeAttempt` tauscht ein neueres Token ein, wenn das gecachte innerhalb von 120000 ms vor Ablauf liegt (Flag-Symbol `PTU.A0D`) |

### 2.4 IQ-Fehler (found, `C43951qe.Brt`)

`<error code backoff>` innerhalb des IQ-Results:

| Code | Verhalten |
|------|-----------|
| 503 | Media-Throttle zurücksetzen; nächsten Refresh nach einem Fibonacci-Backoff mit Jitter planen (`3/4 * t + rand(t/2)`) |
| 507 mit backoff > 0 | Media-Requests drosseln bis `now + min(backoff, 10800) s` |
| andere / 0 | ignoriert |

---

## 3. Medientypen und HKDF-Info-Strings (found, `MmsType` `C15530gU` static init)

Jeder `MmsType` hält einen Pfad-String (`A02`), ein kurzes Dateityp-Label (`A01`, z. B. `IMG`), die HKDF-`info`-Bytes (`A03`) und eine numerische ID (`A00`). Die `info`-Bytes werden roh als HKDF-Info verwendet (kein weiteres Präfix).

| HKDF info | `MmsType`-Pfad-Strings |
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

Hinweise (found): `ptt` und `audio` teilen sich die Audio-Info, sind aber unterschiedliche Pfad-Strings; `sticker` nutzt die Image-Info; `gif` und `ptv` nutzen die Video-Info; es gibt mehrere `image`-Zeilen mit unterschiedlichen numerischen IDs (1, 23, 25, 37, 42, 44, 57; `sticker` ist 20) für verschiedene Aufrufstellen (Bedeutung der ID unknown); `group-history` ist der einzige Eintrag, dessen Info nicht die Form `WhatsApp <X> Keys` hat. Profilbilder (`ppic`) erscheinen nur in der Route-Capability-Menge und in Download-Generator-Aufrufen, nicht als `MmsType`.

---

## 4. Media-Key und Ableitung

### 4.1 Key-Erzeugung (found)

| Element | Wert |
|---------|------|
| Media-Key | 32 Zufallsbytes aus `SecureRandom` (`C57333Po0`, `QIh.A0B` ist `new SecureRandom()`) |
| Wiederverwendung | `MediaKeyGen/reuse key from message contents`, wenn der Key jünger ist als `172800000 ms + SecureRandom.nextInt(86400000)` (2 bis 3 Tage, mit Jitter), gemessen am gespeicherten Key-Timestamp; ältere Keys werden verworfen (`key expired`) und neu erzeugt |
| Domain | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `AbstractC38961i0.A00`, aufgerufen von `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01` lehnt jede andere Länge ab (`Invalid length of derived secret`). Ciphertext-Länge: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (PKCS#5-gepolsterte Blöcke plus 10 MAC-Bytes).

### 4.3 Non-E2EE-Media-Key (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (Feld **74**, Message `DQT`) trägt `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) und `e2eeMediaKey` (**2**). Mit Flag **24661** prüft der Empfänger, ob der Key in der Nachricht zur Domain passt (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); bei Abweichung fällt er auf den Key wie angegeben zurück. Welche Produkte die NON_E2EE-Domain nutzen: unknown.

---

## 5. Verschlüsselung, MAC und Hashes

### 5.1 Cipher (found, `M2I`, `M23`, `N6U`)

| Schritt | Detail |
|---------|--------|
| Cipher | `AES/CBC/PKCS5Padding`, Key = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, zuerst mit dem IV aktualisiert, dann mit jedem Ciphertext-Byte; die ersten **10** Bytes des Digest werden an den Ciphertext angehängt |
| `fileSha256` | SHA-256 über den Klartext (`P9M`-Digest-Stream über die Datei) |
| `fileEncSha256` | SHA-256 über Ciphertext + 10 MAC-Bytes |
| Ausgabe | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Entschlüsselungsseite (`P9N`, `M23`): Der MAC wird über IV + Ciphertext geprüft und dann mit den abschließenden 10 Bytes verglichen. Ranged-Entschlüsselung (`C51101MlN`): Ist der Range-Start nicht 0, werden die ersten 16 gelesenen Bytes als IV verwendet (vorheriger Ciphertext-Block); innere Chunks nutzen `AES/CBC/NoPadding`, der letzte Chunk PKCS#5 (inferred aus der Cipher-Auswahl).

### 5.2 Timestamps und Pfade

| Feld | Wert |
|------|------|
| `mediaKeyTimestamp` | lokale Uhr in Millisekunden, im Key-Objekt gehalten, als Sekunden ins Protobuf geschrieben (`C20H.A06` = `/1000`) |
| `directPath` | vom Server zurückgegebener Pfad-String, in der Nachricht und in der DB-Spalte `direct_path` gespeichert; kann Query-Parameter tragen (z. B. wird `_nc_hot` daraus gelesen) |
| `url` | Legacy-Feld mit vollständiger URL; noch in Proto-Klassen und in der Upload-Response vorhanden, aber der Download-Generator wird aus `directPath` oder aus dem Hash gebaut (Abschnitt 9.1) |

### 5.3 Optimistische Hash-Prüfungen

`MediaUpload/optimistic-hash-fail` und `optimistic-plaintext-hash-fail` (Upload-Result 12) werden geloggt, wenn der vom Server gemeldete Hash vom lokal berechneten abweicht. Optimistic Upload (Surface-String `optimistic`) lädt hoch, bevor der Versand committet ist; sein Protokoll jenseits des Surface-Namens: unknown.

---

## 6. Media-Message-Felder

Feldnummern aus den generierten Protobuf-Klassen gelesen. Klassennamen sind anhand des Feld-Layouts zugeordnet (inferred); die Nummern sind found.

| Message (Klasse) | Feldnummern (Name = Nummer) |
|------------------|------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| History-Bundle (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

Nummern des `Message`-Containers (`C30628DTw`) (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage` ist Feld **21** des Containers `BD3`.

### 6.1 Thumbnails

| Art | Mechanismus (found, sofern nicht anders markiert) |
|-----|---------------------------------------------------|
| Inline | `jpegThumbnail`-Bytes (**16**) in der Nachricht (Bild, Video, Dokument); `pngThumbnail` (**16**) bei Stickern |
| Hochgeladen | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (Bild **26-28**, Video **21-23**, Dokument **13-15**); `MmsType` `thumbnail-*` mit den Thumbnail-HKDF-Infos aus Abschnitt 3 |
| Key | das Proto hat kein separates Thumbnail-Key-Feld, daher wird ein Thumbnail mit dem Media-Key seiner Nachricht verschlüsselt (inferred) |
| Serverseitig erzeugt | Upload-Query `server_thumb_gen=1`; die Upload-Response kann `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` zurückgeben |
| DB | Tabelle `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming und Sidecars (found)

Ein Sidecar ist eine Liste von 10-Byte-MACs, einer pro Ciphertext-Chunk, mit der ein Player einen Bereich verifizieren kann, ohne die ganze Datei zu lesen.

| Element | Detail |
|---------|--------|
| Algorithmus | `P9N.read`: pro Chunk wird ein `HmacSHA256(macKey)` mit den **vorherigen 16 Ciphertext-Bytes** initialisiert (beim ersten Chunk der IV), mit dem Chunk gefüttert, und die ersten 10 Bytes des Digest werden gespeichert |
| Verkettung | `C57228PmG.A00` fügt alle 10-Byte-MACs zu einem Byte-Array zusammen |
| Video / Audio | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); Chunk-Größe **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Progressives Bild | `firstScanSidecar` (**18**) mit `firstScanLength` (**19**): ein Chunk von `ceil(len/16)*16` Bytes; `scansSidecar` (**21**) mit `scanLengths` (**22**): Chunks variabler Größe (`P1Y`) |
| Sticker | `firstFrameSidecar` (**12**) mit `firstFrameLength` (**11**) |
| Einstellungen | Server-Prop `streaming_upload_chunk_size` ist ein Dictionary-Token; Wirkung: unknown |
| Fehlt | Download-Status 30 `failed_no_sidecar` |
| Server-Streaming | Upload-Query `stream=1` und `streaming=riff` zusammen (Abschnitt 8.1); DASH: `dashManifestUrl` (**33**), `metadataUrl` (**30**) in der Response |

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
| `surface` | `mms` (normal), `newsletter` (Channels), `optimistic` (Upload vor dem Senden); `AbstractC58025Pzy` |
| `type` | `MmsType`-Pfad-String (Abschnitt 3), z. B. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | Standard-Base64 von `fileEncSha256` mit `+` zu `-` und `/` zu `_`; das `=`-Padding bleibt erhalten (`StringUtils.A0B`) |
| `direct_ip` | 1, wenn die Authority eine IP ist (`ip4` oder `[ip6]` in Klammern), sonst 0 |
| `auth` | das `media_conn`-Auth-Token; wird von `K19.A03` als Query-Parameter hinzugefügt |
| `stream=1`, `streaming=riff` | beide gesetzt, wenn der Request ein gestreamter Upload ist (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | nur für `newsletter-image` / `-status` (Flag **11191**) und `newsletter-video` / `-status` (Flag **11192**) |
| `server_transcode=1` | `newsletter-video` mit Request-ID 10 und Flag **9096** |
| `_nc_rmr=1` | Uploads außerhalb von Newslettern (Request-Flag `A0N`) |
| `_nc_cbep=1` | wenn der Request es erlaubt und Flag **17404** an ist (Bedeutung unknown) |
| `type`, `media_id`, `media_id_upload` | `media_id` = höchstwertige 63 Bit einer Upload-UUID; `media_id_upload` = niedrigstwertige 63 Bit, nur wenn der Request zusätzliche Einträge hat; `type` ist ein Caller-String (Bedeutung: unknown) |

Die Bedeutung der Query-Namen `_nc_cbep` und `_nc_rmr` ist unknown (nur Namen).

### 8.2 Token (found, `C43489Iy4.A00`)

| Fall | Token |
|------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`, pro Request neu, nicht an die Datei gebunden |
| Sonst | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` sind 32 Bytes aus `SecureRandom`, einmal erzeugt und in den Preferences als `upload_token_random_bytes` gespeichert (Base64 no-wrap, no-padding) |

Kann `fileEncSha256` nicht dekodiert werden, ist das Token allein `SHA-256(installSecret)`. Zweck der Konstruktion: inferred als serverseitige Prüfung, dass der Uploader den Hash kennt, ohne ihn im Pfad offenzulegen.

### 8.3 HTTP-Request (found, `HttpsFormPost` `C43478Ixt`)

| Element | Wert |
|---------|------|
| Bibliothek | `HttpsURLConnection` mit eigener `SSLSocketFactory`; Marker `http_stack = HttpUrlConnection` |
| Methode | POST (`setDoOutput(true)` auf `HttpURLConnection`; kein expliziter Methodenaufruf) |
| Timeouts | Connect 15000 ms, Read 60000 ms |
| Header | `Host: <route hostname>` (die Authority kann eine IP sein), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, optional `Companion_User_Secret` (Konstruktorargument ungleich null; Companion-Semantik inferred) |
| Body (Route vorhanden) | rohe Ciphertext-Stream, nur eine einzelne Datei (`MMS4 upload only supports a single file`); Streaming-Modus mit fester Länge, wenn die Länge bekannt ist, sonst chunked (`setChunkedStreamingMode(0)`); Puffer 16384 Bytes |
| Body (keine Route) | Legacy-`multipart/form-data` mit `Content-Disposition: form-data`-Parts |
| Abbruch | bei Thread-Interrupt oder Cancel-Flag wird der Stream aufgefüllt (`UploadRequest/Post streaming padding bytes=`), damit die deklarierte Länge erreicht wird (Zweck inferred) |
| Response | bis zu 1 MiB gelesen; HTTP >= 400 gibt den Code zurück, der Body geht an `onError` |

### 8.4 Response (found, `MediaUploadTransfer` `C59523QnV`)

Gelesene JSON-Keys: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (nur akzeptiert, wenn es `[A-Za-z0-9-]{1,64}` entspricht), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (verschachtelter JSON-String mit `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. Eine Response ohne `direct_path` wird von diesem Parser nicht als Fehler behandelt; spätere Stufen scheitern mit `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Fortsetzbarer Upload (found)

| Schritt | Detail |
|---------|--------|
| Probe | gleiche Upload-URL plus `resume=1` (`HttpResumeCheck`); JSON-Antwort `{"resume": "complete"}` mit `url`, `direct_path` (bereits hochgeladen) oder `{"resume": <offset>}` |
| Fortsetzen | POST mit `Content-Range: bytes <offset>-*/*`, der Stream wird zuvor bis `<offset>` übersprungen |
| Fallbacks | `ResumeCheck/attempting fallback MMS upload form post`, auch nach einem WATLS-(TLS-)Fehler |
| Parse-Fehler | Status `PBY.A03`, Upload startet neu |

### 8.6 Route supplier und Retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Regel | Detail |
|-------|--------|
| Versuchsschleife | `TransferRetries/run attempt = N; route = ...`; ein Transfer pro Route; `no routes` beendet die Schleife |
| Host-Wahl | `type=primary`-Host, dessen Capability-Menge den Medientyp enthält; die ersten zwei Versuche nutzen ihn; spätere Versuche nutzen den `type=fallback`-Eintrag und dessen `fallback_*`-Felder (Reihenfolge inferred aus verwirrtem Kontrollfluss) |
| Versuche | Default 4 (`4 - extra`); mit den Flags **12545** und **12446** kann das Limit nach Versuch 3 überschrieben werden; `max_auto_download_retry` / `max_manual_retry` (je Default 3) speisen die modusabhängige Anzahl (Zuordnung inferred) |
| Delay | konstant 1000 ms (`RouteSelector.A01`); mit Flag **257** und zusätzlichen Versuchen exponentiell: Basis 1000 ms, `2^n`, Jitter, gedeckelt bei 3000 ms |
| Auth-Fehler 401 / 403 | wird nicht als Fehlschlag gezählt: auf ein neueres Token warten (Budget `A0J`, Default 20000 ms), tauschen, wiederholen |
| Wiederholbarer HTTP-Status | `QKS.A08`: < 400 ja; 400-499 nein, außer 408 mit Flag **13748**; >= 500 ja, außer 505 und 507 |
| Proxy | mit User-Proxy und Flag **4073** wird die Media-Authority zu Proxy-Host und Port aus `proxy_media_port` (Default 587) |
| Health-Check | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, Connect 15000 ms, Read 30000 ms |

---

## 9. Download

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

Der Konstruktor verlangt einen Media-Hash, einen Direct Path oder eine Cross-Reference (`media hash, direct path, or cross reference is required`). `mode` ist `auto` oder `manual`. `_nc_map=whatsapp-nofna` wird für Typen aus der Server-Liste `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (AB-Prop, Flag **4836**) hinzugefügt. Die `auth`-Query wird auf einem geflaggten Pfad (`PTU.A03`) hinzugefügt und ersetzt einen vorhandenen `auth`-Parameter. Profilbilder nutzen den Typ `ppic`; statische Assets nutzen `/wa/static` mit `_nc_cat`.

### 9.2 Bucket- und Host-Wahl (dekompilierter Kontrollfluss, teilweise verwirrt)

- Hosts werden nach der `download`-Capability gefiltert und danach, ob `download_buckets` den Bucket-String enthält.
- Bucket `1`, wenn der Direct Path `_nc_hot=<seconds>` trägt, das jünger ist als das Fenster in Flag **2136**; sonst, mit Flag **2134** und `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); Fallback-Bucket `0`.
- Newsletter-Typen und geflaggte Fälle überspringen die Hot-/Hash-Logik.
- Der gewählte Bucket geht als `_nc_cat` raus.

### 9.3 HTTP-Request (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Element | Wert |
|---------|------|
| Methode | GET (Tigon oder `HttpURLConnection`) |
| Header | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (Flag-gesteuert), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (wenn ein ETag bekannt ist) |
| Akzeptiert | HTTP 200 und 206 |
| Partiell | Previews nutzen ein Präfix von 262144 Bytes (`Range: bytes=0-262143`) |
| 416 | gilt als vollständig, wenn `Content-Range` `*/<size>` ist und der lokalen Größe entspricht; sonst Neustart (Flag **29305**) oder Fehler |
| Allow-List | mit Flag-Symbol `PTU.A04` muss der Host in `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` liegen (Suffix-Match), außer die URL hat `category=PSA`; sonst `invalid_url` (8) / Log `host not in media CDN allow-list` |

### 9.4 Verifikation (found)

Der Decrypt-Stream prüft den MAC; Hash-Stufen werden auf die Status 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch` abgebildet; fehlende Eingaben auf 26-30 (Abschnitt 10.2).

---

## 10. Fehlercodes

### 10.1 Behandlung von HTTP-Status

| Status | Verhalten |
|--------|-----------|
| 401, 403 | `media_conn` aktualisieren, Auth tauschen, wiederholen (max. 2 Wechsel) |
| 408 | Retry nur mit Flag **13748** |
| 416 | siehe 9.3 |
| 507 | Download-Status 12 `throttle`, kein Retry |
| 505 | kein Retry |
| andere 4xx | kein Retry |
| 5xx, < 400 | Retry im Rahmen des Versuchsbudgets |

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

Die Codes 10, 22, 33 und alles andere geben `invalid` aus. `QKK.A04` gruppiert 1, 2, 3, 11, 15, 16, 18, 19, 20 und 25 (Netzwerk-Fehler; die Bezeichnung ist inferred).

### 10.3 Upload-Result (found, Metrik-Namen `media_upload_<NAME>`)

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

Exception-Mapping in `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, sonstige `IOException` 18 (Netzwerk down) oder 3, `CancellationException` 1, `C7CL` 21, alles andere 31. Nach einem Nicht-Erfolgs-Result mit 5, 21, 24, 34, 35 oder 36 werden der gecachte Key und Hash (`A0B`, `A0C`) gelöscht.

---

## 11. Media Retry (Re-Upload-Anforderung)

Schlägt ein Download fehl, weil das Objekt weg ist (typischerweise Status 5 `too_old` oder eine Response der 404-Klasse), bittet der Empfänger das Telefon des Senders um einen erneuten Upload.

### 11.1 Request: Receipt `server-error` (found, `SendMediaErrorReceiptJob`)

| Variante | Writer | Wire |
|----------|--------|------|
| Multi-Device (eigenes Primary) | case 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Legacy | case 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (kein `rmr`) |

`enc_iv` sind 12 Zufallsbytes; `enc_p` wird nativ erzeugt (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) aus einer Nachricht, die die Stanza-ID trägt. Die native Bibliothek hält die HKDF-Info `WhatsApp Media Retry Notification`; AES-GCM mit der Stanza-ID als AAD und einem 32-Byte-HKDF-Key ist inferred aus dem 12-Byte-IV und der Baileys-Implementierung. Die Server-Props `mms4_media_retry_notification_encryption_enabled` und `mms4_server_error_receipt_encryption_enabled` sind Dictionary-Tokens (Wirkung inferred: steuern, ob `<encrypt>` gesendet wird).

### 11.2 Antwort: Notification `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Schritt | Detail |
|---------|--------|
| Account-Check | ein `rmr` von einem anderen Account loggt `cross-account-rmr` und wird verworfen, außer das Flag-Symbol `PTV.A0F` ist an |
| Lookup | Nachricht nach `(chat, id, from_me)`; Nicht-Medien-Nachrichten loggen `message is null or not media` |
| Entschlüsselung | nativ (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); das Ergebnismodell liefert `directPath` (in der Nachricht gespeichert) und einen Result-Int |
| Result | `<error code>` überschreibt das Result; der Handler vergleicht den Wert mit 2 und 3 (mit der öffentlichen Proto-Nummerierung `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferred) |
| Fortsetzen | der Downloader erhält den neuen Direct Path (`resume reuploading download`); ohne aktiven Downloader wird die Nachricht für den Auto-Download eingereiht |
| Reporting | mit Flag **5718** wird das `reporting_token` für die Nachricht gespeichert |

---

## 12. View-once- und Status-Medien

| Thema | Fakt (found) |
|-------|--------------|
| Crypto / Transport | identisch mit normalen Medien: gleicher `MmsType`, gleiches HKDF, gleiche URLs; in der Tabelle gibt es keinen View-once-Typ |
| Flag | `viewOnce` ist ein Feld in `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); Container `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Lokale Regeln | der Sender kann eigene View-once-Medien nicht öffnen (`senders can not view their own media`); View-once-Thumbnails werden von `EphemeralUpdateRunnable/deleteViewOnceThumbnails` gelöscht; ein View-once-Audio ohne Media-Key wird nicht gesendet (`unable to send encrypted media message due to missing mediaKey`) |
| Ob der Server das Objekt nach dem Ansehen löscht | unknown |
| Status (`status@broadcast`) | nutzt die normalen `MmsType`-Zeilen (image, video, gif, audio) mit eigenen numerischen IDs; es gibt keine `status`-HKDF-Info; die einzigen `*-status`-Typen sind die der Newsletter (Abschnitt 13) |
| Status-Limits | die Dictionary-Tokens `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` sind Server-Props (Werte: unknown) |
| Status-Download | `C59526QnY` hält eine `MediaDownload`- und eine `StatusMediaDownload`-Variante; beide bauen die URL mit demselben Generator |

---

## 13. Newsletter-Medien (Channels)

| Aspekt | Newsletter | Regulär |
|--------|-----------|---------|
| Surface in der URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | einfache Namen |
| Verschlüsselung | keine: der Artwork-Downloader verlangt `artworkEncSha256` nur für nicht-Newsletter-Inhalte (`required fields missing - artworkEncSha256 is null for encrypted content`); für andere Typen existiert der Passthrough-Stream `C59535Qnh` (Identität). Die `MmsType`-Zeilen tragen weiterhin HKDF-Info-Bytes (ungenutzt, inferred) |
| Upload-Token | zufällig, nicht hash-gebunden (Abschnitt 8.2) | Geheimnis pro Installation + Hash |
| Route-Filter | keine Hot-/Hash-Bucket-Logik für Namen, die mit `newsletter` beginnen | Bucket-Logik (9.2) |
| `media_conn` ip token | `ip_token` wird für Newsletter unabhängig von `set_ip_token` angewendet (Flag **12149**) | nur wenn `set_ip_token` true ist |
| Server-Arbeit | `server_thumb_gen=1` (Flags **11191**, **11192**), `server_transcode=1` für Video (Flag **9096**) | nicht gesetzt |
| Flag **27920** | im Newsletter-Pfad von `C15490gQ` gelesen; Wirkung unknown | |

---

## 14. Express Path und andere Upload-Varianten

| Variante | Evidenz |
|----------|---------|
| Express Path | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) als E2E-Nachricht gesendet (`FMessageMediaExpressPathNotify`, verlangt URL, Hash und Länge); `ExpressPathDownload` loggt `EP gain <ms> <bytes>`; Upload-Log `Use static route supplier for express path upload`; Upload-Result 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Serverseitiges Verhalten: unknown |
| Optimistic Upload | Surface `optimistic`; Hash-Recheck-Results 12; Protokoll: unknown |
| History / App State | `md-msg-hist`, `md-app-state` nutzen die normale Pipeline mit ihren Info-Strings |
| Group History | `group-history`, Info `Group History`, Mime `application/protobuf` vom Empfänger geprüft (`C34677F2y`); Pfad folgt Abschnitt 8.1 (`/mms/group-history/...`, inferred aus der generischen Zusammensetzung) |

---

## 15. Native Härtung der Medien-Parser (found, Strings und Exports der entpackten Bibliotheken)

81 Shared Objects werden aus dem Superpack-Archiv entpackt. Speicherunsichere Parser für angreiferkontrollierte Bytes sind entweder in einer Sandbox oder durch Rust ersetzt.

| Eingabe | Komponente | Härtung |
|---------|------------|---------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp nach WebAssembly kompiliert und per wasm2c nach C abgesenkt (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), Wrapper `whatsapp::security::LibwebpSandbox` in einer Thread-Local-Sandbox; Java-Flag `sWebPSandboxEnabled`; Fehler-Log `sandboxed WebP decode failed: status=%d`; Guards `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib in einer wasm2c- / WASI-minrt-Sandbox (`GiflibSandbox`, `wasi::minrt`); JNI-Klassen `SandboxedGifImage`, `SandboxedGifFrame`; Guard `Called memcpy for memory larger than the sandbox` |
| Ogg- / Opus-Dateien | `libwhatsapp.so` | RLBox-wasm2c-Sandboxes für `libogg.wasm` und `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; Trap-Log `wasm2c sandbox trap: %s (code=%d)` |
| Container- und Stream-Parsing | `libwhatsapp.so`-Rust-Crates | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, DASH-Segmenter, Edit Lists), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (IPTC-Digital-Source-Type-Werte wie `trainedAlgorithmicMedia`, C2PA) |
| AV1-Decode | `libdav1d.so` | dav1d **1.5.1** (Versions-String); exportiert die `dav1d_*`-API |
| AV1-Encode | `libwzav1.so` | Version 2.3.1; exportiert nur `wz_encoder_*` und `wz_codec_version*`; keine Decoder-Symbole, parst also keine entfernten Bitstreams |
| H.264- / H.265-Frames | Plattform-`MediaCodec` | außerhalb der App |

Parser in Rust scheitern mit Panics (`assertion failed: ...`, `While parsing field '...' in ...`) statt mit Speicherkorruption: als Strings found, Wirkung inferred. Die `rlbox`-Sandbox deckt libogg und opusfile in `libwhatsapp.so` ab; andere Bibliotheken nutzen wasm2c ohne den RLBox-Wrapper (inferred aus Symbolen). Ob jeder eingehende Medienpfad diese Parser vor einer Nutzerinteraktion erreicht: unknown. Dynamisches Verhalten (Fuzzing, Laufzeit-Crashes): nicht getestet.

---

## 16. Feature Flags (IDs wie an den Aufrufstellen gelesen; Namen nicht aufgelöst)

| Flag | Wo | Steuert |
|------|----|---------|
| **149** | `RouteSelector`, `C43951qe` | `media_conn` in den Preferences persistieren und neu laden |
| **257** | `Mms4RouteSupplier` ctor | exponentielles Backoff-Objekt |
| **258** | `Mms4RouteSupplier.A03` | int: zusätzliche Versuche für Modus 0 |
| **2134** | `A02` | hashbasierter Download-Bucket |
| **2136** | `A02` | Hot-Content-Fenster (long) |
| **4073** | `A00` | Medien über den User-Proxy routen |
| **4836** | `Mms4DownloadUrlGenerator` | Liste von Typen mit niedriger Hit-Rate (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | Behandlung des Reporting-Tokens |
| **9096** | `QBE` | `server_transcode=1` (Newsletter-Video) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` für Newsletter-Bild / -Video |
| **12149** | `RouteSelector.A0L`, `A03` | `ip_token` verwenden |
| **12545** / **12446** | `A05` | Versuchslimit nach Versuch 3 überschreiben |
| **13748** | `QKS.A08` | HTTP 408 wiederholen |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | `RouteSelector`-Einstiegspunkte | Boolean, der als Upload-Flag an die Routenauswahl übergeben wird (Semantik nicht aufgelöst) |
| **24661** | `MediaCryptoProvider` | Validierung der Non-E2EE-Key-Domain |
| **29305** | `PlainDownloadTransfer` | 416-Behandlung |
| **37982**, **38437** | `C43481Ixw` | Tigon-Property, Request-Timeout |

---

## 17. Baileys (`baron-baileys-v2`, Quellcode gelesen, nichts getestet)

| Aspekt | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| `media_conn`-Request | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` hat eine optionale `last_id`-Variante | immer `<media_conn>`, mit `last_id`, wenn eine vorherige ID existiert |
| Geparste Felder | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | kein `maxContentLengthBytes` gelesen; ergänzt `auth_ttl`, `max_buckets`, `is_new`, `id`, Fallback-Felder, Capability-Kinder, Retry-Zähler, `ip_token` |
| HKDF-Länge | `hkdf(key, 112, {info})`, nutzt Bytes 0-79 | 80 Bytes; die ersten 80 Bytes einer HKDF-Ausgabe hängen nicht von der angeforderten Länge ab, daher sind IV, Cipher-Key und MAC-Key identisch |
| Info-Strings | `WhatsApp <X> Keys`; `gif` und `ptv` werden auf Video abgebildet, `ptt` auf Audio, `sticker` auf Image | gleiche Strings und Zuordnungen |
| Cipher, MAC, Hashes | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` angehängt, `fileSha256`, `fileEncSha256` über `ct + mac` | gleich |
| Upload-URL | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Hash-Kodierung | url-safe Base64, `=`-Padding entfernt, dann `encodeURIComponent` | url-safe Base64, `=`-Padding behalten |
| Token | url-safe `fileEncSha256` | `SHA-256(installSecret || fileEncSha256)` (Newsletter: zufällig) |
| Pfad-Tabelle | `sticker` und `thumbnail-link` auf `/mms/image`, `ptv` auf `/mms/video`, `md-msg-hist` auf `/mms/md-app-state`, kein `ptt` | der `MmsType`-String ist das Pfadsegment: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Header | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | kein `Origin` gefunden; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | probiert jeden Host einmal der Reihe nach | Route supplier mit Versuchen, 401- / 403-Token-Wechsel, Resume-Probe |
| Resume | keiner gefunden (`resume=1`, `Content-Range` fehlen) | `resume=1`-Probe und `Content-Range` |
| Sidecars | keine Erzeugung von `streamingSidecar`, `firstScanSidecar` oder `scansSidecar` in `src` gefunden | erzeugt für Video, Audio, progressive Bilder |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | intern Millisekunden, im Proto Sekunden |
| Retry-Receipt | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = Stanza-ID, IV 12 Bytes, HKDF-Info `WhatsApp Media Retry Notification` | Writer case 327 hat dasselbe Node-Layout; 12-Byte-IV und Info-String sind found; GCM / AAD inferred |
| Retry-Result-Map | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | nicht anwendbar (vergleicht die Werte 2 und 3) |

Praktische Folgen (nur Code gelesen): Ein Baileys-Upload eines `md-msg-hist`-Objekts nutzt einen anderen Pfad-String als der Android-Client; gepaddetes Base64 im Pfad ist ein sichtbarer Unterschied; eine serverseitige Toleranz für diese Varianten ist unknown.

---

## 18. Fehlerfälle

| Symptom | Ursache | Fix |
|---------|---------|-----|
| Upload 401 / 403 | `auth` abgelaufen oder ersetzt | `media_conn` aktualisieren, mit dem neuen `auth` erneut senden |
| Upload liefert kein `direct_path` | Upload abgelehnt oder unvollständig | Status prüfen; Resume-Probe mit `resume=1` |
| Download 404 / Status 5 `too_old` | Objekt auf dem CDN abgelaufen | `server-error`-Receipt senden (Abschnitt 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | korrupte Bytes oder falsches `fileEncSha256` | erneut laden; Hash-Quelle prüfen |
| MAC-Prüfung schlägt fehl | falscher Media-Key, falsche HKDF-Info (Typ verwechselt) oder abgeschnittene Datei | die Info-String des richtigen `MmsType` nutzen; Image-Info nicht für `sticker-pack`- oder `ptt`-Zeilen wiederverwenden |
| `invalid_url` (8) | Host außerhalb der CDN-Allow-List | nur die aufgeführten Suffixe akzeptieren |
| `throttle` (12), HTTP 507 | Server-Throttle | `backoff` Sekunden warten (max. 10800) |
| `no_route` (11) | kein nutzbarer `media_conn`-Host für den Typ | `media_conn` anfordern, Capability-Tags prüfen |
| `failed_no_media_key` (29), `no_sidecar` (30) | Proto-Feld fehlt | `mediaKey` verlangen; Sidecar nur für Streaming |

---

## 19. Wichtige Abgrenzungen

| Nicht verwechseln | Fakt |
|-------------------|------|
| `media_conn`-Host-Liste vs. Upload-URL | die IQ liefert Hosts und ein `auth`; URL-Pfad, Token und Query werden pro Transfer gebaut |
| `auth` vs. `token` | `auth` ist das Account-weite Token aus `media_conn`; `token` gilt pro Datei |
| HKDF 80 vs. 112 Bytes | gleiche Keys; Android leitet 80 ab |
| `fileSha256` vs. `fileEncSha256` | Klartext-Hash vs. Hash von `ciphertext + mac10` |
| `fileEncSha256` im Pfad vs. `directPath` | der Upload-Pfad nutzt den Hash; der Download nutzt den vom Server zurückgegebenen `directPath` |
| `mediaKeyTimestamp` vs. Key-Wiederverwendungsfenster | Timestamp in Sekunden auf der Leitung; Wiederverwendungsfenster 2-3 Tage beim Sender |
| Streaming-Sidecar vs. `fileEncSha256` | 10-Byte-MACs pro Chunk vs. Hash der ganzen Datei |
| Media Retry vs. erneutes Senden | der Sender lädt dasselbe Objekt neu hoch und antwortet mit einem neuen `directPath`; die Nachricht wird nicht neu gesendet |
| Newsletter-Medien vs. reguläre Medien | unverschlüsselt, Surface `newsletter`, zufälliges Token |
| `libwzav1` vs. `libdav1d` | Encoder vs. Decoder; nur der Decoder parst entfernte Daten |

---

## 20. Kompletter Ablauf (ein Bild senden und empfangen)

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

## 21. Unbekanntes

| Punkt | Status |
|-------|--------|
| Serververhalten (Token-Validierung, Dedupe, Objektlebensdauer, View-once-Löschung) | serverseitig |
| Query-Namen `_nc_cbep`, `_nc_rmr`, `type`; Flag **21807** und die `PTU.*`-IDs | Namen oder Bedeutung nicht aufgelöst |
| Numerische IDs in `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | Bedeutung nicht aufgelöst |
| Nativer Media-Retry-Cipher (AES-GCM, AAD, Key-Länge) | Info-String found; Algorithmus inferred |
| Verwendung von `ip_token`, Wert von `X-FB-nc-oc`, Quelle von `Companion_User_Secret` | nicht aufgelöst |
| Verwendung der NON_E2EE-Media-Key-Domain | nicht aufgelöst |
| Protokolle von Express Path und Optimistic Upload | nicht aufgelöst |
| Genaue Host-Reihenfolge über die Versuche und die modusabhängigen Versuchszahlen | dekompilierter Kontrollfluss verwirrt |
| Welche eingehenden Medien welchen sandboxed Parser vor einer Nutzerinteraktion erreichen | nicht kartiert |
| Traffic | nichts mitgeschnitten; kein dynamischer Test |
