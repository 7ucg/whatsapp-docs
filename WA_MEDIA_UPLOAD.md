# WhatsApp Media Upload — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** Android media transfer: `media_conn` IQ (hosts, auth, ttl, buckets, fallback hosts), upload and download URL construction and HTTP parameters, media type table with HKDF info strings, media key generation and derivation, AES-CBC + HMAC encryption, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, thumbnails, streaming sidecars for video / audio / progressive images, resumable upload, route selection, retry and backoff, upload and download error codes, media retry receipt and `mediaretry` notification, view-once and status media, newsletter (channel) media, express path, client-side native hardening of media parsers, Baileys comparison

---

## 1. What it is (technically)

Media never travels inside the chatd stream (see [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). A message carries only a protobuf reference (key, hashes, `directPath`); the bytes go over separate HTTPS connections to media hosts. Chatd supplies one thing: the `media_conn` IQ that hands out host names and a short-lived upload auth token. All statements come from static analysis of the decompiled APK and the unpacked native libraries; nothing was captured on the wire. Tiers: **found** = read in code or strings, **inferred** = deduced, **unknown** = not resolved.

| Layer | 2.26.41.6 name | Role |
|-------|----------------|------|
| Route selector | `RouteSelector` (`C10950Wx`) | holds the current `media_conn` result, refresh timer, throttle, route factory |
| `media_conn` parser | `C43951qe` (IQ result handler), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | parses `<media_conn>` / `<host>` |
| Route supplier | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (static suppliers) | picks host per attempt, swaps auth token |
| Retry driver | `TransferRetries` (`C44566Jd2`) | attempt loop around one transfer |
| Media type table | `MmsType` (`C15530gU`) | per type: path string, HKDF info bytes, numeric id |
| Key provider | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF 80 bytes, non-E2EE domain key |
| Cipher streams | `M2I` (encrypt out), `M23` (encrypt in), `P9N` / `P1X` / `P1Y` (sidecar MACs), `C51101MlN` (ranged decrypt) | AES-CBC + HMAC |
| Upload driver | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (key reuse), `C57333Po0` (key generation + hashes) | hashes, sidecars, upload orchestration |
| Upload URL | `C43489Iy4` | `/surface/type/hash?...` |
| Download URL | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) upload; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) download | transport |
| Resume probe | `HttpResumeCheck` (`C59524QnW`) | asks server how many bytes it has |
| Retry receipt | `SendMediaErrorReceiptJob`, writer cases 77 and 327 in `HandlerThreadC21920sG` | request re-upload from the sender |
| Retry notification | `MediaRetryNotificationHandler` (`C1S0`, notification code 97) | consumes the answer |
| Native | `libwhatsapp.so` (Rust media crates, RLBox sandboxes), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | parsers and decoders |

Points that decide the rest of the report:

- Android derives **80** bytes from the media key (IV 16, cipher key 32, MAC key 32), not 112 (section 4).
- The HTTP path is `/{surface}/{type}/{urlSafeFileEncSha256}` where `type` is the `MmsType` string of the media (`image`, `ptt`, `md-msg-hist`, ...), not a coarse class (section 8.1).
- The Android upload `token` is not the file hash; it is a SHA-256 over a per-install secret and the file hash (section 8.2).
- Newsletter (channel) media shares the same code but uses surface `newsletter` and a random token; it is unencrypted (found for the artwork path, inferred for the rest, section 13).
- Download hosts are filtered by a bucket derived from the file hash (section 9.2).

---

## 2. `media_conn` IQ

### 2.1 Request (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout 32000 ms. Only one request is in flight (`inFlightMediaRoutingRequestTime`); a second call logs `not sending request` and returns. A global throttle (`ChatdMediaThrottleManager`) can suppress the call (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Response (found, `C43951qe.CFS`)

| Node / attribute | Type | Use |
|------------------|------|-----|
| `media_conn@auth` | string, required | upload auth token (`auth` query parameter) |
| `@ttl` | seconds | connection lifetime; expiry = send time + ttl * 1000 |
| `@auth_ttl` | seconds | auth token lifetime; expiry = send time + auth_ttl * 1000 |
| `@max_buckets` | long, default 0 | modulus for the download bucket (section 9.2) |
| `@is_new` | int, default 1 | 1 = replace the host list; otherwise keep the previous hosts and take only token and ttl (`previous hosts retained`) |
| `@id` | string | stored as `last_id`, sent back in the next request |
| `@max_auto_download_retry` | int, default 3 | retry budget for automatic downloads |
| `@max_manual_retry` | int, default 3 | retry budget for manual downloads |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | parsed and cached; `ip_token` is used only when flag **12149** is on and `set_ip_token` is true (consumption site: unknown) |
| `host` (repeated) | node | one route entry |

`host` attributes (found): `hostname` (required), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` or `fallback`; anything else becomes `primary`), `force_ip` (`"true"`). Children: `<upload>`, `<download>`, `<download_buckets>`; the child tag names are the capability entries. `upload` and `download` keep only tags that appear in a fixed set of 34 media type strings (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, the `newsletter-*` family, and the `thumbnail-*` family); `download_buckets` is kept unfiltered.

A route host is usable only if its hostname ends in `.whatsapp.net` (`Mms4RouteSupplier.A06`, also applied to `fallback_hostname`).

### 2.3 Caching and refresh (found)

| Rule | Value |
|------|-------|
| Persist | with flag **149** the result is stored as JSON (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) under `route_selector_prefs` / `media_conn`; loaded once, used only if the auth is not yet expired |
| Refresh check | before a transfer: if connection or auth expires within 120000 ms, send a new IQ and wait up to 20000 ms (`requestroutesandwaitforauth`) |
| Timer | `auth expiry - 60000 ms` after each result; foreground (`BgG`) re-arms it |
| Auth failure | HTTP 401 or 403 on a transfer triggers a refresh (`onmediatransfererrororresponsecode`), max 2 token swaps per transfer (`JW1.A00 < 2`), then the attempt is retried with the new `auth` |
| Auth before attempt | `refreshAuthBeforeAttempt` swaps in a newer token when the cached one is within 120000 ms of expiry (flag symbol `PTU.A0D`) |

### 2.4 IQ error (found, `C43951qe.Brt`)

`<error code backoff>` inside the IQ result:

| Code | Behaviour |
|------|-----------|
| 503 | reset the media throttle; schedule the next refresh after a Fibonacci backoff with jitter (`3/4 * t + rand(t/2)`) |
| 507 with backoff > 0 | throttle media requests until `now + min(backoff, 10800) s` |
| other / 0 | ignored |

---

## 3. Media types and HKDF info strings (found, `MmsType` `C15530gU` static init)

Each `MmsType` holds a path string (`A02`), a short file-type label (`A01`, e.g. `IMG`), the HKDF `info` bytes (`A03`) and a numeric id (`A00`). The `info` bytes are used raw as HKDF info (no further prefix).

| HKDF info | `MmsType` path strings |
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

Notes (found): `ptt` and `audio` share the Audio info but are different path strings; `sticker` uses Image info; `gif` and `ptv` use Video info; several `image` rows exist with different numeric ids (1, 23, 25, 37, 42, 44, 57; `sticker` is 20) for different call sites (id meaning unknown); `group-history` is the only entry whose info is not of the form `WhatsApp <X> Keys`. Profile pictures (`ppic`) appear only in the route capability set and in download generator calls, not as an `MmsType`.

---

## 4. Media key and derivation

### 4.1 Key generation (found)

| Item | Value |
|------|-------|
| Media key | 32 random bytes from `SecureRandom` (`C57333Po0`, `QIh.A0B` is `new SecureRandom()`) |
| Reuse | `MediaKeyGen/reuse key from message contents` when the key is younger than `172800000 ms + SecureRandom.nextInt(86400000)` (2 to 3 days, jittered), measured against the stored key timestamp; older keys are dropped (`key expired`) and regenerated |
| Domain | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `AbstractC38961i0.A00` called by `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01` rejects any other length (`Invalid length of derived secret`). Ciphertext length: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (PKCS#5 padded blocks plus 10 MAC bytes).

### 4.3 Non-E2EE media key (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (field **74**, message `DQT`) carries `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) and `e2eeMediaKey` (**2**). With flag **24661** the receiver checks that the key in the message matches the domain (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); on mismatch it falls back to the key as given. Which products use the NON_E2EE domain: unknown.

---

## 5. Encryption, MAC and hashes

### 5.1 Cipher (found, `M2I`, `M23`, `N6U`)

| Step | Detail |
|------|--------|
| Cipher | `AES/CBC/PKCS5Padding`, key = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, updated with the IV first, then every ciphertext byte; the first **10** bytes of the digest are appended to the ciphertext |
| `fileSha256` | SHA-256 over the plaintext (`P9M` digest stream over the file) |
| `fileEncSha256` | SHA-256 over ciphertext + 10 MAC bytes |
| Output | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Decrypt side (`P9N`, `M23`): MAC is verified over IV + ciphertext, then compared with the trailing 10 bytes. Ranged decrypt (`C51101MlN`): when the range start is not 0 the first 16 bytes read are used as IV (previous ciphertext block); inner chunks use `AES/CBC/NoPadding`, the final chunk uses PKCS#5 (inferred from the cipher selection).

### 5.2 Timestamps and paths

| Field | Value |
|-------|-------|
| `mediaKeyTimestamp` | local clock in milliseconds kept in the key object, written to the protobuf as seconds (`C20H.A06` = `/1000`) |
| `directPath` | server-returned path string, stored in the message and in the DB column `direct_path`; may carry query parameters (e.g. `_nc_hot` is read from it) |
| `url` | legacy full URL field; still present in proto classes and in the upload response, but the download generator is built from `directPath` or from the hash (section 9.1) |

### 5.3 Optimistic hash checks

`MediaUpload/optimistic-hash-fail` and `optimistic-plaintext-hash-fail` (upload result 12) are logged when the hash the server reports differs from the locally computed one. Optimistic upload (surface string `optimistic`) uploads before the send is committed; its protocol beyond the surface name: unknown.

---

## 6. Media message fields

Field numbers read from the generated protobuf classes. Class names are matched by field layout (inferred); numbers are found.

| Message (class) | Field numbers (name = number) |
|-----------------|-------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| History bundle (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

`Message` container (`C30628DTw`) numbers (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage` is field **21** of the container `BD3`.

### 6.1 Thumbnails

| Kind | Mechanism (found unless marked) |
|------|---------------------------------|
| Inline | `jpegThumbnail` (**16**) bytes in the message (image, video, document); `pngThumbnail` (**16**) in stickers |
| Uploaded | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (image **26-28**, video **21-23**, document **13-15**); `MmsType` `thumbnail-*` with the Thumbnail HKDF infos of section 3 |
| Key | the proto has no separate thumbnail key field, so a thumbnail is encrypted with the media key of its message (inferred) |
| Server-made | upload query `server_thumb_gen=1`; the upload response may return `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` |
| DB | table `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming and sidecars (found)

A sidecar is a list of 10-byte MACs, one per ciphertext chunk, that lets a player verify a range without reading the whole file.

| Item | Detail |
|------|--------|
| Algorithm | `P9N.read`: per chunk an `HmacSHA256(macKey)` is initialised with the **previous 16 ciphertext bytes** (the IV for the first chunk), fed the chunk, and the first 10 bytes of the digest are stored |
| Concatenation | `C57228PmG.A00` joins all 10-byte MACs into one byte array |
| Video / audio | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); chunk size **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Progressive image | `firstScanSidecar` (**18**) with `firstScanLength` (**19**): one chunk of `ceil(len/16)*16` bytes; `scansSidecar` (**21**) with `scanLengths` (**22**): variable chunk sizes (`P1Y`) |
| Sticker | `firstFrameSidecar` (**12**) with `firstFrameLength` (**11**) |
| Settings | server prop `streaming_upload_chunk_size` is a dictionary token; its effect: unknown |
| Missing | download status 30 `failed_no_sidecar` |
| Server streaming | upload query `stream=1` and `streaming=riff` together (section 8.1); DASH: `dashManifestUrl` (**33**), `metadataUrl` (**30**) in the response |

---

## 8. Upload

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Part | Value |
|------|-------|
| `surface` | `mms` (normal), `newsletter` (channels), `optimistic` (pre-send upload); `AbstractC58025Pzy` |
| `type` | `MmsType` path string (section 3), e.g. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | standard base64 of `fileEncSha256` with `+` to `-` and `/` to `_`; the `=` padding is kept (`StringUtils.A0B`) |
| `direct_ip` | 1 when the authority is an IP (`ip4`, or bracketed `[ip6]`), else 0 |
| `auth` | the `media_conn` auth token; added as a query parameter by `K19.A03` |
| `stream=1`, `streaming=riff` | both set when the request is a streamed upload (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | only for `newsletter-image` / `-status` (flag **11191**) and `newsletter-video` / `-status` (flag **11192**) |
| `server_transcode=1` | `newsletter-video` with request id 10 and flag **9096** |
| `_nc_rmr=1` | non-newsletter uploads (request flag `A0N`) |
| `_nc_cbep=1` | when the request allows it and flag **17404** is on (meaning unknown) |
| `type`, `media_id`, `media_id_upload` | `media_id` = most-significant 63 bits of an upload UUID; `media_id_upload` = least-significant 63 bits, only when the request has extra entries; `type` is a caller string (meaning: unknown) |

The meaning of the query names `_nc_cbep` and `_nc_rmr` is unknown (names only).

### 8.2 Token (found, `C43489Iy4.A00`)

| Case | Token |
|------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`, fresh per request, not bound to the file |
| Other | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` is 32 bytes from `SecureRandom`, created once and stored in preferences as `upload_token_random_bytes` (base64 no-wrap, no-padding) |

If `fileEncSha256` cannot be decoded the token is `SHA-256(installSecret)` alone. Purpose of the construction: inferred as a server-side check that the uploader knows the hash without exposing it in the path.

### 8.3 HTTP request (found, `HttpsFormPost` `C43478Ixt`)

| Item | Value |
|------|-------|
| Library | `HttpsURLConnection` with a custom `SSLSocketFactory`; marker `http_stack = HttpUrlConnection` |
| Method | POST (`setDoOutput(true)` on `HttpURLConnection`; no explicit method call) |
| Timeouts | connect 15000 ms, read 60000 ms |
| Headers | `Host: <route hostname>` (the authority may be an IP), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, optional `Companion_User_Secret` (non-null constructor argument; companion semantics inferred) |
| Body (route present) | raw ciphertext stream, single file only (`MMS4 upload only supports a single file`); fixed-length streaming mode when the length is known, else chunked (`setChunkedStreamingMode(0)`); buffer 16384 bytes |
| Body (no route) | legacy `multipart/form-data` with `Content-Disposition: form-data` parts |
| Abort | on thread interrupt or cancel flag the stream is padded (`UploadRequest/Post streaming padding bytes=`) so the declared length is completed (purpose inferred) |
| Response | up to 1 MiB read; HTTP >= 400 returns the code, body goes to `onError` |

### 8.4 Response (found, `MediaUploadTransfer` `C59523QnV`)

JSON keys read: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (accepted only if it matches `[A-Za-z0-9-]{1,64}`), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (nested JSON string with `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. A response without `direct_path` is not treated as an error by this parser; later stages fail with `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Resumable upload (found)

| Step | Detail |
|------|--------|
| Probe | same upload URL plus `resume=1` (`HttpResumeCheck`); JSON answer `{"resume": "complete"}` with `url`, `direct_path` (already uploaded) or `{"resume": <offset>}` |
| Continue | POST with `Content-Range: bytes <offset>-*/*`, the stream is skipped to `<offset>` first |
| Fallbacks | `ResumeCheck/attempting fallback MMS upload form post`, also after a WATLS (TLS) error |
| Parse error | status `PBY.A03`, upload restarts |

### 8.6 Route supplier and retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Rule | Detail |
|------|--------|
| Attempt loop | `TransferRetries/run attempt = N; route = ...`; one transfer per route; `no routes` ends the loop |
| Host pick | `type=primary` host whose capability set contains the media type; first two attempts use it; later attempts use the `type=fallback` entry and its `fallback_*` fields (order inferred from garbled control flow) |
| Attempts | default 4 (`4 - extra`); with flags **12545** and **12446** the limit can be overridden after attempt 3; `max_auto_download_retry` / `max_manual_retry` (default 3 each) feed the mode-dependent count (mapping inferred) |
| Delay | constant 1000 ms (`RouteSelector.A01`); with flag **257** and extra attempts, exponential: base 1000 ms, `2^n`, jitter, capped at 3000 ms |
| Auth error 401 / 403 | not counted as a failure: wait for a newer token (budget `A0J`, 20000 ms default), swap, retry |
| Retryable HTTP status | `QKS.A08`: < 400 yes; 400-499 no, except 408 with flag **13748**; >= 500 yes, except 505 and 507 |
| Proxy | with a user proxy and flag **4073** the media authority becomes the proxy host and port from `proxy_media_port` (default 587) |
| Health check | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, connect 15000 ms, read 30000 ms |

---

## 9. Download

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

The constructor requires a media hash, a direct path or a cross reference (`media hash, direct path, or cross reference is required`). `mode` is `auto` or `manual`. `_nc_map=whatsapp-nofna` is added for types in the server list `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (AB prop, flag **4836**). The `auth` query is added on a flagged path (`PTU.A03`) and replaces an existing `auth` parameter. Profile pictures use type `ppic`; static assets use `/wa/static` with `_nc_cat`.

### 9.2 Bucket and host choice (decompiled control flow, partly garbled)

- Hosts are filtered by `download` capability and by `download_buckets` containing the bucket string.
- Bucket `1` when the direct path carries `_nc_hot=<seconds>` younger than the window in flag **2136**; otherwise, with flag **2134** and `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); fallback bucket `0`.
- Newsletter types and flagged cases skip the hot / hash logic.
- The chosen bucket goes out as `_nc_cat`.

### 9.3 HTTP request (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Item | Value |
|------|-------|
| Method | GET (Tigon or `HttpURLConnection`) |
| Headers | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (flag-gated), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (when an ETag is known) |
| Accepted | HTTP 200 and 206 |
| Partial | previews use a prefix of 262144 bytes (`Range: bytes=0-262143`) |
| 416 | treated as complete when `Content-Range` is `*/<size>` and equals the local size; else restart (flag **29305**) or error |
| Allow-list | with flag symbol `PTU.A04`, the host must be in `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` (suffix match) unless the URL has `category=PSA`; else `invalid_url` (8) / log `host not in media CDN allow-list` |

### 9.4 Verification (found)

Decrypt stream checks the MAC; hash stages map to statuses 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; missing inputs map to 26-30 (section 10.2).

---

## 10. Error codes

### 10.1 HTTP status handling

| Status | Behaviour |
|--------|-----------|
| 401, 403 | refresh `media_conn`, swap auth, retry (max 2 swaps) |
| 408 | retry only with flag **13748** |
| 416 | see 9.3 |
| 507 | download status 12 `throttle`, not retried |
| 505 | not retried |
| other 4xx | not retried |
| 5xx, < 400 | retried within the attempt budget |

### 10.2 Download status (found, `QKK` `A03`)

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

Codes 10, 22, 33 and anything else print `invalid`. `QKK.A04` groups 1, 2, 3, 11, 15, 16, 18, 19, 20 and 25 (network-type failures; the label is inferred).

### 10.3 Upload result (found, metric names `media_upload_<NAME>`)

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

Exception mapping in `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, other `IOException` 18 (network down) or 3, `CancellationException` 1, `C7CL` 21, anything else 31. After a non-success result with 5, 21, 24, 34, 35 or 36 the cached key and hash (`A0B`, `A0C`) are cleared.

---

## 11. Media retry (re-upload request)

When a download fails because the object is gone (typically status 5 `too_old`, or a 404-class response), the receiver asks the sender's phone to upload again.

### 11.1 Request: receipt `server-error` (found, `SendMediaErrorReceiptJob`)

| Variant | Writer | Wire |
|---------|--------|------|
| Multi-device (own primary) | case 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Legacy | case 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (no `rmr`) |

`enc_iv` is 12 random bytes; `enc_p` is produced natively (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) from a message that carries the stanza id. The native library holds the HKDF info `WhatsApp Media Retry Notification`; AES-GCM with the stanza id as AAD and a 32-byte HKDF key is inferred from the 12-byte IV and from the Baileys implementation. Server props `mms4_media_retry_notification_encryption_enabled` and `mms4_server_error_receipt_encryption_enabled` are dictionary tokens (effect inferred: gate whether `<encrypt>` is sent).

### 11.2 Answer: notification `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Step | Detail |
|------|--------|
| Account check | `rmr` from another account logs `cross-account-rmr` and is dropped unless flag symbol `PTV.A0F` is on |
| Lookup | message by `(chat, id, from_me)`; non-media messages log `message is null or not media` |
| Decrypt | native (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); result model gives `directPath` (stored into the message) and a result int |
| Result | `<error code>` overrides the result; the handler compares the value with 2 and 3 (with the public proto numbering `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferred) |
| Continue | downloader gets the new direct path (`resume reuploading download`); with no active downloader the message is queued for auto download |
| Reporting | with flag **5718** the `reporting_token` is stored for the message |

---

## 12. View-once and status media

| Topic | Fact (found) |
|-------|--------------|
| Crypto / transport | identical to normal media: same `MmsType`, same HKDF, same URLs; there is no view-once type in the table |
| Flag | `viewOnce` is a field in `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); container `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Local rules | sender cannot open own view-once media (`senders can not view their own media`); view-once thumbnails are deleted by `EphemeralUpdateRunnable/deleteViewOnceThumbnails`; a view-once audio without media key is not sent (`unable to send encrypted media message due to missing mediaKey`) |
| Whether the server deletes the object after view | unknown |
| Status (`status@broadcast`) | uses the normal `MmsType` rows (image, video, gif, audio) with their own numeric ids; no `status` HKDF info exists; the only `*-status` types are the newsletter ones (section 13) |
| Status limits | dictionary tokens `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` are server props (values: unknown) |
| Status download | `C59526QnY` holds a `MediaDownload` and a `StatusMediaDownload` variant; both build the URL with the same generator |

---

## 13. Newsletter (channel) media

| Aspect | Newsletter | Regular |
|--------|-----------|---------|
| Surface in URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | plain names |
| Encryption | none: the artwork downloader requires `artworkEncSha256` only for non-newsletter content (`required fields missing - artworkEncSha256 is null for encrypted content`); for other types the passthrough stream `C59535Qnh` (identity) exists. The `MmsType` rows still carry HKDF info bytes (unused, inferred) |
| Upload token | random, not hash-bound (section 8.2) | per-install secret + hash |
| Route filter | no hot / hash bucket logic for names starting with `newsletter` | bucket logic (9.2) |
| `media_conn` ip token | `ip_token` is applied for newsletter regardless of `set_ip_token` (flag **12149**) | only when `set_ip_token` is true |
| Server work | `server_thumb_gen=1` (flags **11191**, **11192**), `server_transcode=1` for video (flag **9096**) | not set |
| Flag **27920** | read in the newsletter path of `C15490gQ`; effect unknown | |

---

## 14. Express path and other upload variants

| Variant | Evidence |
|---------|----------|
| Express path | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) sent as an E2E message (`FMessageMediaExpressPathNotify`, requires url, hash and length); `ExpressPathDownload` logs `EP gain <ms> <bytes>`; upload log `Use static route supplier for express path upload`; upload result 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Server-side behaviour: unknown |
| Optimistic upload | surface `optimistic`; hash re-check results 12; protocol: unknown |
| History / app state | `md-msg-hist`, `md-app-state` use the normal pipeline with their info strings |
| Group history | `group-history`, info `Group History`, mime `application/protobuf` checked by the receiver (`C34677F2y`); path follows section 8.1 (`/mms/group-history/...`, inferred from the generic composition) |

---

## 15. Native hardening of media parsers (found, strings and exports of the unpacked libraries)

81 shared objects are unpacked from the superpack archive. Memory-unsafe parsers of attacker-controlled bytes are either sandboxed or replaced by Rust.

| Input | Component | Hardening |
|-------|-----------|-----------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp compiled to WebAssembly and lowered to C by wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), wrapper `whatsapp::security::LibwebpSandbox` in a thread-local sandbox; Java flag `sWebPSandboxEnabled`; failure log `sandboxed WebP decode failed: status=%d`; guards `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib in a wasm2c / WASI-minrt sandbox (`GiflibSandbox`, `wasi::minrt`); JNI classes `SandboxedGifImage`, `SandboxedGifFrame`; guard `Called memcpy for memory larger than the sandbox` |
| Ogg / Opus files | `libwhatsapp.so` | RLBox wasm2c sandboxes for `libogg.wasm` and `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; trap log `wasm2c sandbox trap: %s (code=%d)` |
| Container and stream parsing | `libwhatsapp.so` Rust crates | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, DASH segmenter, edit lists), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (IPTC digital-source-type values such as `trainedAlgorithmicMedia`, C2PA) |
| AV1 decode | `libdav1d.so` | dav1d **1.5.1** (version string); exports the `dav1d_*` API |
| AV1 encode | `libwzav1.so` | version 2.3.1; exports only `wz_encoder_*` and `wz_codec_version*`; no decoder symbols, so it does not parse remote bitstreams |
| H.264 / H.265 frames | platform `MediaCodec` | outside the app |

Parsers in Rust fail with panics (`assertion failed: ...`, `While parsing field '...' in ...`) instead of memory corruption: found as strings, effect inferred. The `rlbox` sandbox covers libogg and opusfile in `libwhatsapp.so`; other libraries use wasm2c without the RLBox wrapper (inferred from symbols). Whether every inbound media path reaches these parsers before user interaction: unknown. Dynamic behaviour (fuzzing, runtime crashes): not tested.

---

## 16. Feature flags (ids as read at call sites; names unresolved)

| Flag | Where | Controls |
|------|-------|----------|
| **149** | `RouteSelector`, `C43951qe` | persist and reload `media_conn` in preferences |
| **257** | `Mms4RouteSupplier` ctor | exponential backoff object |
| **258** | `Mms4RouteSupplier.A03` | int: extra attempts for mode 0 |
| **2134** | `A02` | hash-based download bucket |
| **2136** | `A02` | hot-content window (long) |
| **4073** | `A00` | route media through the user proxy |
| **4836** | `Mms4DownloadUrlGenerator` | list of low-hit-rate types (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | reporting token handling |
| **9096** | `QBE` | `server_transcode=1` (newsletter video) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` for newsletter image / video |
| **12149** | `RouteSelector.A0L`, `A03` | use `ip_token` |
| **12545** / **12446** | `A05` | override the attempt limit after attempt 3 |
| **13748** | `QKS.A08` | retry HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | `RouteSelector` entry points | boolean handed to route selection as the upload flag (semantics unresolved) |
| **24661** | `MediaCryptoProvider` | non-E2EE key domain validation |
| **29305** | `PlainDownloadTransfer` | 416 handling |
| **37982**, **38437** | `C43481Ixw` | Tigon property, request timeout |

---

## 17. Baileys (`baron-baileys-v2`, source read, nothing tested)

| Aspect | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| `media_conn` request | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` has an optional `last_id` variant | always `<media_conn>`, with `last_id` when a previous id exists |
| Parsed fields | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | no `maxContentLengthBytes` read; adds `auth_ttl`, `max_buckets`, `is_new`, `id`, fallback fields, capability children, retry counts, `ip_token` |
| HKDF length | `hkdf(key, 112, {info})`, uses bytes 0-79 | 80 bytes; the first 80 bytes of an HKDF output do not depend on the requested length, so IV, cipher key and MAC key are identical |
| Info strings | `WhatsApp <X> Keys`; `gif` and `ptv` map to Video, `ptt` to Audio, `sticker` to Image | same strings and mappings |
| Cipher, MAC, hashes | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` appended, `fileSha256`, `fileEncSha256` over `ct + mac` | same |
| Upload URL | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Hash encoding | url-safe base64, `=` padding stripped, then `encodeURIComponent` | url-safe base64, `=` padding kept |
| Token | url-safe `fileEncSha256` | `SHA-256(installSecret || fileEncSha256)` (newsletter: random) |
| Path table | `sticker` and `thumbnail-link` to `/mms/image`, `ptv` to `/mms/video`, `md-msg-hist` to `/mms/md-app-state`, no `ptt` | the `MmsType` string is the path segment: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Headers | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | no `Origin` found; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | tries each host once in order | route supplier with attempts, 401 / 403 token swap, resume probe |
| Resume | none found (`resume=1`, `Content-Range` absent) | `resume=1` probe and `Content-Range` |
| Sidecars | no `streamingSidecar`, `firstScanSidecar` or `scansSidecar` generation found in `src` | generated for video, audio, progressive images |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | milliseconds internally, seconds in the proto |
| Retry receipt | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = stanza id, IV 12 bytes, HKDF info `WhatsApp Media Retry Notification` | writer case 327 has the same node layout; IV 12 bytes and the info string are found; GCM / AAD inferred |
| Retry result map | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | not applicable (compares values 2 and 3) |

Practical consequences (code read only): a Baileys upload of an `md-msg-hist` object uses a different path string than the Android client; padded base64 in the path is a visible difference; any server tolerance for these variants is unknown.

---

## 18. Error cases

| Symptom | Cause | Fix |
|---------|-------|-----|
| Upload 401 / 403 | `auth` expired or replaced | refresh `media_conn`, resend with the new `auth` |
| Upload returns no `direct_path` | upload rejected or incomplete | check status; resume probe with `resume=1` |
| Download 404 / status 5 `too_old` | object expired on the CDN | send the `server-error` receipt (section 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | corrupted bytes or wrong `fileEncSha256` | refetch; verify the hash source |
| MAC check fails | wrong media key, wrong HKDF info (type mix-up), or truncated file | use the info string of the right `MmsType`; do not reuse Image info for `sticker-pack` or `ptt` rows |
| `invalid_url` (8) | host outside the CDN allow-list | accept only the listed suffixes |
| `throttle` (12), HTTP 507 | server throttle | wait `backoff` seconds (max 10800) |
| `no_route` (11) | no usable `media_conn` host for the type | request `media_conn`, check the capability tags |
| `failed_no_media_key` (29), `no_sidecar` (30) | proto field missing | require `mediaKey`; sidecar only for streaming |

---

## 19. Key distinctions

| Do not confuse | Fact |
|----------------|------|
| `media_conn` host list vs upload URL | the IQ gives hosts and one `auth`; the URL path, token and query are built per transfer |
| `auth` vs `token` | `auth` is the account-level token from `media_conn`; `token` is per file |
| HKDF 80 vs 112 bytes | same keys; Android derives 80 |
| `fileSha256` vs `fileEncSha256` | plaintext hash vs hash of `ciphertext + mac10` |
| `fileEncSha256` in the path vs `directPath` | upload path uses the hash; download uses the server-returned `directPath` |
| `mediaKeyTimestamp` vs key reuse window | timestamp in seconds on the wire; reuse window 2-3 days on the sender |
| Streaming sidecar vs `fileEncSha256` | per-chunk 10-byte MACs vs whole-file hash |
| Media retry vs resend | the sender re-uploads the same object and answers with a new `directPath`; the message is not resent |
| Newsletter media vs regular media | unencrypted, surface `newsletter`, random token |
| `libwzav1` vs `libdav1d` | encoder vs decoder; only the decoder parses remote data |

---

## 20. Complete flow (send and receive one image)

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

| Item | Status |
|------|--------|
| Server behaviour (token validation, dedupe, object lifetime, view-once deletion) | server side |
| Query names `_nc_cbep`, `_nc_rmr`, `type`; flag **21807** and the `PTU.*` ids | names or meaning unresolved |
| Numeric ids in `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | meaning unresolved |
| Native media-retry cipher (AES-GCM, AAD, key length) | info string found; algorithm inferred |
| `ip_token` consumption, `X-FB-nc-oc` value, `Companion_User_Secret` source | unresolved |
| Use of the NON_E2EE media key domain | unresolved |
| Express path and optimistic upload protocols | unresolved |
| Exact host order across attempts and the mode-dependent attempt counts | decompiled control flow garbled |
| Which inbound media reaches which sandboxed parser before user interaction | not mapped |
| Traffic | nothing captured; no dynamic test |
