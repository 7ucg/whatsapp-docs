<!-- src-sha1: a12736ca9c475f1c7c0195dbae0d18d5725a4440 -->
# WhatsApp Medya Yükleme — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android medya transferi: `media_conn` IQ'su (host'lar, auth, ttl, bucket'lar, fallback host'ları), yükleme ve indirme URL inşası ve HTTP parametreleri, HKDF info string'leriyle medya tipi tablosu, medya key üretimi ve türetimi, AES-CBC + HMAC şifreleme, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, küçük resimler, video / ses / progressive görüntü için streaming sidecar'ları, resumable upload, route seçimi, retry ve backoff, yükleme ve indirme hata kodları, medya retry receipt'i ve `mediaretry` bildirimi, view-once ve status medyası, newsletter (kanal) medyası, express path, medya parser'larının istemci-tarafı native sağlamlaştırması, Baileys karşılaştırması

---

## 1. Teknik olarak ne

Medya, hiçbir zaman chatd stream'i içinde seyahat etmez (bkz [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Bir mesaj sadece bir protobuf referansı taşır (key, hash'ler, `directPath`); byte'lar medya host'larına ayrı HTTPS bağlantıları üzerinden gider. Chatd tek bir şey sağlar: host adlarını ve kısa-ömürlü bir yükleme auth token'ını veren `media_conn` IQ'su. Tüm ifadeler decompile edilmiş APK'nın ve açılmış native kütüphanelerin statik analizinden gelir; hiçbir şey wire üzerinde yakalanmamıştır. Kademeler: **found** = kod veya string'lerde okundu, **inferred** = çıkarıldı, **unknown** = çözülmedi.

| Katman | 2.26.41.6 adı | Rol |
|-------|----------------|------|
| Route selector | `RouteSelector` (`C10950Wx`) | mevcut `media_conn` sonucunu, yenileme zamanlayıcısını, throttle'ı, route factory'sini tutar |
| `media_conn` parser'ı | `C43951qe` (IQ sonuç handler'ı), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | `<media_conn>` / `<host>`'u çözümler |
| Route sağlayıcısı | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (statik sağlayıcılar) | deneme-başına host seçer, auth token'ını değiştirir |
| Retry sürücüsü | `TransferRetries` (`C44566Jd2`) | bir transfer etrafındaki deneme döngüsü |
| Medya tipi tablosu | `MmsType` (`C15530gU`) | tip-başına: path string'i, HKDF info byte'ları, sayısal id |
| Key sağlayıcısı | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF 80 byte, non-E2EE domain key'i |
| Cipher stream'leri | `M2I` (şifreleme çıkışı), `M23` (şifreleme girişi), `P9N` / `P1X` / `P1Y` (sidecar MAC'leri), `C51101MlN` (ranged decrypt) | AES-CBC + HMAC |
| Yükleme sürücüsü | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (key yeniden kullanımı), `C57333Po0` (key üretimi + hash'ler) | hash'ler, sidecar'lar, yükleme orkestrasyonu |
| Yükleme URL'i | `C43489Iy4` | `/surface/type/hash?...` |
| İndirme URL'i | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) yükleme; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) indirme | transport |
| Resume probe'u | `HttpResumeCheck` (`C59524QnW`) | sunucuya kaç byte'a sahip olduğunu sorar |
| Retry receipt'i | `SendMediaErrorReceiptJob`, `HandlerThreadC21920sG`'de writer durumları 77 ve 327 | gönderenden yeniden-yükleme talep eder |
| Retry bildirimi | `MediaRetryNotificationHandler` (`C1S0`, bildirim kodu 97) | cevabı tüketir |
| Native | `libwhatsapp.so` (Rust medya crate'leri, RLBox sandbox'ları), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | parser'lar ve decoder'lar |

Raporun kalanını belirleyen noktalar:

- Android, medya key'inden **80** byte türetir (IV 16, cipher key 32, MAC key 32), 112 değil (bölüm 4).
- HTTP path'i `/{surface}/{type}/{urlSafeFileEncSha256}`'dir, `type` medyanın `MmsType` string'idir (`image`, `ptt`, `md-msg-hist`, ...), kaba bir sınıf değil (bölüm 8.1).
- Android yükleme `token`'ı dosya hash'i değildir; kurulum-başına bir sır ile dosya hash'i üzerinden bir SHA-256'dır (bölüm 8.2).
- Newsletter (kanal) medyası aynı kodu paylaşır ama `newsletter` surface'ini ve rastgele bir token kullanır; şifrelenmemiştir (artwork path'i için found, kalan için inferred, bölüm 13).
- İndirme host'ları, dosya hash'inden türetilen bir bucket'a göre filtrelenir (bölüm 9.2).

---

## 2. `media_conn` IQ'su

### 2.1 İstek (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout 32000 ms. Sadece bir istek uçuşta (`inFlightMediaRoutingRequestTime`); ikinci bir çağrı `not sending request` loglar ve döner. Küresel bir throttle (`ChatdMediaThrottleManager`) çağrıyı bastırabilir (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Yanıt (found, `C43951qe.CFS`)

| Node / attribute | Tip | Kullanım |
|------------------|------|-----|
| `media_conn@auth` | string, gerekli | yükleme auth token'ı (`auth` query parametresi) |
| `@ttl` | saniye | bağlantı ömrü; süre dolumu = gönderme zamanı + ttl * 1000 |
| `@auth_ttl` | saniye | auth token ömrü; süre dolumu = gönderme zamanı + auth_ttl * 1000 |
| `@max_buckets` | long, varsayılan 0 | indirme bucket'ı için modulus (bölüm 9.2) |
| `@is_new` | int, varsayılan 1 | 1 = host listesini değiştir; aksi halde önceki host'ları tut ve sadece token ile ttl'i al (`previous hosts retained`) |
| `@id` | string | `last_id` olarak saklanır, bir sonraki istekte geri gönderilir |
| `@max_auto_download_retry` | int, varsayılan 3 | otomatik indirmeler için retry bütçesi |
| `@max_manual_retry` | int, varsayılan 3 | manuel indirmeler için retry bütçesi |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | ayrıştırılır ve cache'lenir; `ip_token` sadece flag **12149** açıksa ve `set_ip_token` doğruysa kullanılır (tüketim noktası: unknown) |
| `host` (tekrarlı) | node | bir route girişi |

`host` attribute'ları (found): `hostname` (gerekli), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` veya `fallback`; başka herhangi bir şey `primary` olur), `force_ip` (`"true"`). Çocuklar: `<upload>`, `<download>`, `<download_buckets>`; çocuk tag isimleri yetenek girdileridir. `upload` ve `download`, sabit 34 medya-tipi-string kümesinde (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, `newsletter-*` ailesi ve `thumbnail-*` ailesi) görünen tag'leri sadece tutar; `download_buckets` filtrelenmeden tutulur.

Bir route host'u sadece hostname'i `.whatsapp.net` ile bitiyorsa kullanılabilirdir (`Mms4RouteSupplier.A06`, `fallback_hostname`'e de uygulanır).

### 2.3 Cache'leme ve yenileme (found)

| Kural | Değer |
|------|-------|
| Kalıcılık | flag **149** ile sonuç JSON olarak saklanır (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) `route_selector_prefs` / `media_conn` altında; bir kez yüklenir, sadece auth henüz süresi dolmamışsa kullanılır |
| Yenileme kontrolü | bir transferden önce: eğer bağlantı veya auth 120000 ms içinde süresi dolacaksa, yeni bir IQ gönder ve en fazla 20000 ms bekle (`requestroutesandwaitforauth`) |
| Zamanlayıcı | her sonuçtan sonra `auth expiry - 60000 ms`; ön plan (`BgG`) bunu yeniden kurar |
| Auth başarısızlığı | bir transferde HTTP 401 veya 403 bir yenilemeyi tetikler (`onmediatransfererrororresponsecode`), transfer-başına maks 2 token değişimi (`JW1.A00 < 2`), sonra deneme yeni `auth` ile yeniden yapılır |
| Deneme öncesi auth | `refreshAuthBeforeAttempt`, cache'lenmiş token süresi dolumuna 120000 ms içindeyken daha yeni bir token değiştirir (flag sembolü `PTU.A0D`) |

### 2.4 IQ hatası (found, `C43951qe.Brt`)

IQ sonucu içinde `<error code backoff>`:

| Kod | Davranış |
|------|-----------|
| 503 | medya throttle'ını sıfırla; jitter'lı bir Fibonacci backoff'u (`3/4 * t + rand(t/2)`) sonrası bir sonraki yenilemeyi planla |
| 507, backoff > 0 ile | medya isteklerini `now + min(backoff, 10800) s`'ye kadar throttle et |
| diğer / 0 | göz ardı edilir |

---

## 3. Medya tipleri ve HKDF info string'leri (found, `MmsType` `C15530gU` statik init)

Her `MmsType`, bir path string'i (`A02`), kısa bir dosya-tipi etiketi (`A01`, örn. `IMG`), HKDF `info` byte'ları (`A03`) ve sayısal bir id (`A00`) tutar. `info` byte'ları HKDF info olarak ham şekilde kullanılır (ek bir önek yok).

| HKDF info | `MmsType` path string'leri |
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

Notlar (found): `ptt` ve `audio`, Audio info'yu paylaşır ama farklı path string'leridir; `sticker` Image info'yu kullanır; `gif` ve `ptv` Video info'yu kullanır; farklı çağrı noktaları için farklı sayısal id'lere (1, 23, 25, 37, 42, 44, 57; `sticker` 20'dir) sahip birkaç `image` satırı vardır (id anlamı unknown); `group-history`, info'su `WhatsApp <X> Keys` biçiminde olmayan tek girdidir. Profil resimleri (`ppic`), sadece route yetenek kümesinde ve indirme generator çağrılarında görünür, bir `MmsType` olarak değil.

---

## 4. Medya key'i ve türetimi

### 4.1 Key üretimi (found)

| Öğe | Değer |
|------|-------|
| Medya key'i | `SecureRandom`'dan 32 rastgele byte (`C57333Po0`, `QIh.A0B`, `new SecureRandom()`'dur) |
| Yeniden kullanım | `MediaKeyGen/reuse key from message contents`, key saklanmış key zaman damgasına karşı ölçülen `172800000 ms + SecureRandom.nextInt(86400000)` (2 ile 3 gün arası, jitter'lı) yaşından küçükse; daha eski key'ler düşürülür (`key expired`) ve yeniden üretilir |
| Domain | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `C59530Qnc.AM1` tarafından çağrılan `AbstractC38961i0.A00`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01`, başka herhangi bir uzunluğu reddeder (`Invalid length of derived secret`). Ciphertext uzunluğu: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (PKCS#5 padded bloklar artı 10 MAC byte'ı).

### 4.3 Non-E2EE medya key'i (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (alan **74**, mesaj `DQT`), `mediaKeyDomain`'i (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) ve `e2eeMediaKey`'i (**2**) taşır. Flag **24661** ile alıcı, mesajdaki key'in domain'le eşleştiğini kontrol eder (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); uyuşmazlıkta verildiği gibi key'e geri döner. Hangi ürünlerin NON_E2EE domain'ini kullandığı: unknown.

---

## 5. Şifreleme, MAC ve hash'ler

### 5.1 Cipher (found, `M2I`, `M23`, `N6U`)

| Adım | Detay |
|------|------|
| Cipher | `AES/CBC/PKCS5Padding`, key = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, önce IV ile güncellenir, sonra her ciphertext byte'ı ile; digest'in ilk **10** byte'ı ciphertext'e eklenir |
| `fileSha256` | plaintext üzerinde SHA-256 (`P9M` digest stream'i dosya üzerinde) |
| `fileEncSha256` | ciphertext + 10 MAC byte'ı üzerinde SHA-256 |
| Çıktı | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Çözme tarafı (`P9N`, `M23`): MAC, IV + ciphertext üzerinde doğrulanır, sonra son 10 byte ile karşılaştırılır. Ranged decrypt (`C51101MlN`): range başlangıcı 0 değilken okunan ilk 16 byte IV olarak kullanılır (önceki ciphertext bloğu); iç parçalar `AES/CBC/NoPadding` kullanır, son parça PKCS#5 kullanır (cipher seçiminden inferred).

### 5.2 Zaman damgaları ve path'ler

| Alan | Değer |
|-------|-------|
| `mediaKeyTimestamp` | key nesnesinde tutulan milisaniye cinsinden yerel saat, protobuf'a saniye olarak yazılır (`C20H.A06` = `/1000`) |
| `directPath` | sunucunun döndürdüğü path string'i, mesajda ve DB kolonunda `direct_path`'te saklanır; query parametreleri taşıyabilir (örn. `_nc_hot` ondan okunur) |
| `url` | eski tam URL alanı; hâlâ proto sınıflarında ve yükleme yanıtında mevcut, ama indirme generator'u `directPath`'ten veya hash'ten inşa edilir (bölüm 9.1) |

### 5.3 Optimistic hash kontrolleri

`MediaUpload/optimistic-hash-fail` ve `optimistic-plaintext-hash-fail` (yükleme sonucu 12), sunucunun raporladığı hash yerel olarak hesaplanandan farklı olduğunda loglanır. Optimistic upload (surface string'i `optimistic`), gönderi commit edilmeden önce yükler; surface adının ötesindeki protokolü: unknown.

---

## 6. Medya mesajı alanları

Alan numaraları, üretilmiş protobuf sınıflarından okunur. Sınıf adları alan düzenine göre eşleştirilmiştir (inferred); numaralar found'dur.

| Mesaj (sınıf) | Alan numaraları (ad = numara) |
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

`Message` konteyner'ı (`C30628DTw`) numaraları (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage`, konteyner `BD3`'ün alanı **21**'dir.

### 6.1 Küçük resimler

| Tür | Mekanizma (işaretlenmediyse found) |
|------|---------------------------------|
| Inline | mesaj içindeki `jpegThumbnail` (**16**) byte'ları (görüntü, video, belge); sticker'larda `pngThumbnail` (**16**) |
| Yüklenmiş | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (görüntü **26-28**, video **21-23**, belge **13-15**); bölüm 3'ün Thumbnail HKDF info'larıyla `MmsType` `thumbnail-*` |
| Key | proto'nun ayrı bir küçük-resim key alanı yok, bu yüzden bir küçük resim kendi mesajının medya key'iyle şifrelenir (inferred) |
| Sunucu-yapımı | yükleme query'si `server_thumb_gen=1`; yükleme yanıtı `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` döndürebilir |
| DB | tablo `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming ve sidecar'lar (found)

Bir sidecar, bir player'ın tüm dosyayı okumadan bir range'i doğrulamasına izin veren, ciphertext parçası başına bir, 10-byte'lık MAC'lerin bir listesidir.

| Öğe | Detay |
|------|------|
| Algoritma | `P9N.read`: parça başına bir `HmacSHA256(macKey)`, **önceki 16 ciphertext byte'ıyla** (ilk parça için IV) başlatılır, parça beslenir, ve digest'in ilk 10 byte'ı saklanır |
| Birleştirme | `C57228PmG.A00`, tüm 10-byte'lık MAC'leri bir byte dizisine birleştirir |
| Video / ses | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); parça boyutu **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Progressive görüntü | `firstScanLength` (**19**) ile `firstScanSidecar` (**18**): `ceil(len/16)*16` byte'lık bir parça; `scanLengths` (**22**) ile `scansSidecar` (**21**): değişken parça boyutları (`P1Y`) |
| Sticker | `firstFrameLength` (**11**) ile `firstFrameSidecar` (**12**) |
| Ayarlar | sunucu prop'u `streaming_upload_chunk_size` bir dictionary token'ıdır; etkisi: unknown |
| Eksik | indirme durumu 30 `failed_no_sidecar` |
| Sunucu streaming'i | yükleme query'si `stream=1` ve `streaming=riff` birlikte (bölüm 8.1); DASH: yanıtta `dashManifestUrl` (**33**), `metadataUrl` (**30**) |

---

## 8. Yükleme

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Parça | Değer |
|------|------|
| `surface` | `mms` (normal), `newsletter` (kanallar), `optimistic` (gönderi-öncesi yükleme); `AbstractC58025Pzy` |
| `type` | `MmsType` path string'i (bölüm 3), örn. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | `fileEncSha256`'nın `+`'nin `-`'ye ve `/`'nin `_`'ye dönüştürüldüğü standart base64'ü; `=` padding korunur (`StringUtils.A0B`) |
| `direct_ip` | authority bir IP olduğunda (`ip4` veya köşeli parantezli `[ip6]`) 1, aksi halde 0 |
| `auth` | `media_conn` auth token'ı; `K19.A03` tarafından bir query parametresi olarak eklenir |
| `stream=1`, `streaming=riff` | istek stream'lenmiş bir yükleme olduğunda ikisi de ayarlanır (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | sadece `newsletter-image` / `-status` (flag **11191**) ve `newsletter-video` / `-status` (flag **11192**) için |
| `server_transcode=1` | istek id'si 10 ve flag **9096** ile `newsletter-video` |
| `_nc_rmr=1` | newsletter-olmayan yüklemeler (istek flag'i `A0N`) |
| `_nc_cbep=1` | istek buna izin verdiğinde ve flag **17404** açıkken (anlamı unknown) |
| `type`, `media_id`, `media_id_upload` | `media_id` = bir yükleme UUID'sinin en-önemli 63 biti; `media_id_upload` = en-önemsiz 63 bit, sadece istekte ekstra girdiler varsa; `type` bir çağıran string'idir (anlam: unknown) |

`_nc_cbep` ve `_nc_rmr` query adlarının anlamı unknown'dır (sadece isimler).

### 8.2 Token (found, `C43489Iy4.A00`)

| Durum | Token |
|------|------|
| Newsletter | `urlsafeBase64(SHA-256(java.util.Random'dan 32 byte))`, istek-başına taze, dosyaya bağlı değil |
| Diğer | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret`, `SecureRandom`'dan 32 byte'tır, bir kez oluşturulur ve tercihlerde `upload_token_random_bytes` olarak saklanır (base64 no-wrap, no-padding) |

Eğer `fileEncSha256` çözülemezse token sadece `SHA-256(installSecret)`'tir. İnşasının amacı: yükleyicinin hash'i yolda açığa çıkarmadan bildiğini sunucu-tarafı bir kontrolü olarak inferred.

### 8.3 HTTP isteği (found, `HttpsFormPost` `C43478Ixt`)

| Öğe | Değer |
|------|------|
| Kütüphane | özel bir `SSLSocketFactory` ile `HttpsURLConnection`; işaretçi `http_stack = HttpUrlConnection` |
| Metod | POST (`HttpURLConnection` üzerinde `setDoOutput(true)`; açık bir metod çağrısı yok) |
| Timeout'lar | bağlantı 15000 ms, okuma 60000 ms |
| Header'lar | `Host: <route hostname>` (authority bir IP olabilir), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, opsiyonel `Companion_User_Secret` (non-null constructor argümanı; companion semantiği inferred) |
| Gövde (route mevcut) | ham ciphertext stream'i, sadece tek dosya (`MMS4 upload only supports a single file`); uzunluk bilindiğinde sabit-uzunluklu streaming modu, aksi halde chunked (`setChunkedStreamingMode(0)`); buffer 16384 byte |
| Gövde (route yok) | eski `multipart/form-data`, `Content-Disposition: form-data` parçalarıyla |
| İptal | thread kesintisinde veya iptal flag'inde stream padded edilir (`UploadRequest/Post streaming padding bytes=`) böylece deklare edilen uzunluk tamamlanır (amaç inferred) |
| Yanıt | 1 MiB'ye kadar okunur; HTTP >= 400 kodu döndürür, gövde `onError`'a gider |

### 8.4 Yanıt (found, `MediaUploadTransfer` `C59523QnV`)

Okunan JSON key'leri: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (sadece `[A-Za-z0-9-]{1,64}` ile eşleşirse kabul edilir), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (`thumbnail_direct_path`, `thumbnail_sha256` ile nested JSON string'i), `metadata_url`, `dash_manifest_url`. `direct_path` olmayan bir yanıt bu parser tarafından bir hata olarak ele alınmaz; sonraki aşamalar `FAILED_NO_DIRECT_PATH` (29) ile başarısız olur.

### 8.5 Resumable upload (found)

| Adım | Detay |
|------|------|
| Probe | aynı yükleme URL'i artı `resume=1` (`HttpResumeCheck`); JSON cevabı `{"resume": "complete"}`, `url`, `direct_path` ile (zaten yüklenmiş) veya `{"resume": <offset>}` |
| Devam | `Content-Range: bytes <offset>-*/*` ile POST, stream önce `<offset>`'e atlanır |
| Fallback'ler | `ResumeCheck/attempting fallback MMS upload form post`, ayrıca bir WATLS (TLS) hatasından sonra |
| Ayrıştırma hatası | durum `PBY.A03`, yükleme yeniden başlar |

### 8.6 Route sağlayıcısı ve retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Kural | Detay |
|------|------|
| Deneme döngüsü | `TransferRetries/run attempt = N; route = ...`; route-başına bir transfer; `no routes` döngüyü sonlandırır |
| Host seçimi | yetenek kümesi medya tipini içeren `type=primary` host; ilk iki deneme onu kullanır; sonraki denemeler `type=fallback` girdisini ve onun `fallback_*` alanlarını kullanır (sıra, karmaşık kontrol akışından inferred) |
| Denemeler | varsayılan 4 (`4 - extra`); flag **12545** ve **12446** ile limit deneme 3'ten sonra override edilebilir; `max_auto_download_retry` / `max_manual_retry` (her biri varsayılan 3) moda-bağlı sayıyı besler (eşleme inferred) |
| Gecikme | sabit 1000 ms (`RouteSelector.A01`); flag **257** ve ek denemelerle, üstel: taban 1000 ms, `2^n`, jitter, 3000 ms'de sınırlı |
| Auth hatası 401 / 403 | bir başarısızlık olarak sayılmaz: daha yeni bir token beklenir (bütçe `A0J`, varsayılan 20000 ms), değiştirilir, yeniden denenir |
| Retry'lenebilir HTTP durumu | `QKS.A08`: < 400 evet; 400-499 hayır, flag **13748** ile 408 hariç; >= 500 evet, 505 ve 507 hariç |
| Proxy | bir kullanıcı proxy'si ve flag **4073** ile medya authority'si `proxy_media_port`'tan (varsayılan 587) proxy host ve port'u olur |
| Sağlık kontrolü | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, bağlantı 15000 ms, okuma 30000 ms |

---

## 9. İndirme

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

Constructor bir medya hash'i, bir direct path veya bir çapraz referans gerektirir (`media hash, direct path, or cross reference is required`). `mode`, `auto` veya `manual`'dır. `_nc_map=whatsapp-nofna`, sunucu listesindeki `LOW_CACHE_HIT_RATE_MEDIA_TYPES`'taki (AB prop, flag **4836**) tipler için eklenir. `auth` query'si, flaglenmiş bir path'te (`PTU.A03`) eklenir ve mevcut bir `auth` parametresinin yerini alır. Profil resimleri `ppic` tipini kullanır; statik asset'ler `_nc_cat` ile `/wa/static`'i kullanır.

### 9.2 Bucket ve host seçimi (decompile edilmiş kontrol akışı, kısmen bozuk)

- Host'lar `download` yeteneğine ve bucket string'ini içeren `download_buckets`'a göre filtrelenir.
- Direct path, flag **2136**'daki pencereden daha genç bir `_nc_hot=<seconds>` taşıdığında bucket `1`; aksi halde, flag **2134** ve `max_buckets > 0` ile: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); fallback bucket `0`.
- Newsletter tipleri ve flaglenmiş durumlar hot / hash mantığını atlar.
- Seçilen bucket `_nc_cat` olarak gider.

### 9.3 HTTP isteği (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Öğe | Değer |
|------|------|
| Metod | GET (Tigon veya `HttpURLConnection`) |
| Header'lar | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (flag-gated), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (bir ETag bilindiğinde) |
| Kabul edilen | HTTP 200 ve 206 |
| Kısmi | önizlemeler 262144 byte'lık bir önek kullanır (`Range: bytes=0-262143`) |
| 416 | `Content-Range` `*/<size>` olduğunda ve yerel boyuta eşit olduğunda tamamlanmış olarak ele alınır; aksi halde yeniden başlat (flag **29305**) veya hata |
| Allow-list | flag sembolü `PTU.A04` ile, URL'de `category=PSA` yoksa host `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` içinde olmalıdır (suffix eşleşmesi); aksi halde `invalid_url` (8) / log `host not in media CDN allow-list` |

### 9.4 Doğrulama (found)

Decrypt stream'i MAC'i kontrol eder; hash aşamaları durumlara eşlenir 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; eksik girdiler 26-30'a eşlenir (bölüm 10.2).

---

## 10. Hata kodları

### 10.1 HTTP durum işleme

| Durum | Davranış |
|--------|-----------|
| 401, 403 | `media_conn`'u yenile, auth'u değiştir, yeniden dene (maks 2 değişim) |
| 408 | sadece flag **13748** ile yeniden dene |
| 416 | bkz 9.3 |
| 507 | indirme durumu 12 `throttle`, yeniden denenmez |
| 505 | yeniden denenmez |
| diğer 4xx | yeniden denenmez |
| 5xx, < 400 | deneme bütçesi içinde yeniden denenir |

### 10.2 İndirme durumu (found, `QKK` `A03`)

| Kod | Ad | Kod | Ad |
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

Kodlar 10, 22, 33 ve başka herhangi bir şey `invalid` yazdırır. `QKK.A04`, 1, 2, 3, 11, 15, 16, 18, 19, 20 ve 25'i (ağ-tipi başarısızlıklar; etiket inferred) gruplar.

### 10.3 Yükleme sonucu (found, metrik adları `media_upload_<NAME>`)

| Kod | Ad | Kod | Ad |
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

`QBE.A00`'da exception eşlemesi (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, diğer `IOException` 18 (ağ kapalı) veya 3, `CancellationException` 1, `C7CL` 21, başka herhangi bir şey 31. 5, 21, 24, 34, 35 veya 36 ile bir başarısız-olmayan sonuçtan sonra cache'lenmiş key ve hash (`A0B`, `A0C`) temizlenir.

---

## 11. Medya retry'i (yeniden-yükleme isteği)

Bir indirme nesne gittiği için başarısız olduğunda (tipik olarak durum 5 `too_old`, veya bir 404-sınıfı yanıt), alıcı gönderenin telefonundan yeniden yüklemesini ister.

### 11.1 İstek: receipt `server-error` (found, `SendMediaErrorReceiptJob`)

| Varyant | Writer | Wire |
|---------|--------|------|
| Multi-device (kendi primary'si) | durum 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Legacy | durum 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (`rmr` yok) |

`enc_iv`, 12 rastgele byte'tır; `enc_p`, stanza id'sini taşıyan bir mesajdan native olarak üretilir (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`). Native kütüphane, HKDF info `WhatsApp Media Retry Notification`'ı tutar; stanza id AAD olarak ve 32-byte'lık bir HKDF key ile AES-GCM, 12-byte'lık IV'den ve Baileys uygulamasından inferred'dir. Sunucu prop'ları `mms4_media_retry_notification_encryption_enabled` ve `mms4_server_error_receipt_encryption_enabled` dictionary token'larıdır (etki inferred: `<encrypt>`'in gönderilip gönderilmediğini gater).

### 11.2 Cevap: bildirim `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Adım | Detay |
|------|------|
| Hesap kontrolü | başka bir hesaptan `rmr`, `cross-account-rmr` loglar ve flag sembolü `PTV.A0F` açık olmadıkça düşürülür |
| Arama | `(chat, id, from_me)` ile mesaj; medya-olmayan mesajlar `message is null or not media` loglar |
| Çözme | native (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); sonuç modeli `directPath`'i (mesaja saklanır) ve bir sonuç int'i verir |
| Sonuç | `<error code>`, sonucu override eder; handler değeri 2 ve 3 ile karşılaştırır (kamuya açık proto numaralandırmasıyla `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferred) |
| Devam | indirici yeni direct path'i alır (`resume reuploading download`); aktif bir indirici yoksa mesaj otomatik indirme için kuyruklanır |
| Raporlama | flag **5718** ile `reporting_token` mesaj için saklanır |

---

## 12. View-once ve status medyası

| Konu | Gerçek (found) |
|-------|--------------|
| Kripto / transport | normal medya ile özdeş: aynı `MmsType`, aynı HKDF, aynı URL'ler; tabloda bir view-once tipi yok |
| Flag | `viewOnce`, `ImageMessage`'da (**25**), `VideoMessage`'da (**20**), `AudioMessage`'da (**21**) bir alandır; konteyner `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Yerel kurallar | gönderen kendi view-once medyasını açamaz (`senders can not view their own media`); view-once küçük resimleri `EphemeralUpdateRunnable/deleteViewOnceThumbnails` tarafından silinir; medya key'i olmayan bir view-once ses gönderilmez (`unable to send encrypted media message due to missing mediaKey`) |
| Sunucunun görüntülemeden sonra nesneyi silip silmediği | unknown |
| Status (`status@broadcast`) | kendi sayısal id'leriyle normal `MmsType` satırlarını kullanır (görüntü, video, gif, ses); hiçbir `status` HKDF info'su yok; sadece `*-status` tipleri newsletter olanlardır (bölüm 13) |
| Status limitleri | dictionary token'ları `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` sunucu prop'larıdır (değerler: unknown) |
| Status indirme | `C59526QnY`, bir `MediaDownload` ve bir `StatusMediaDownload` varyantı tutar; her ikisi de URL'i aynı generator ile inşa eder |

---

## 13. Newsletter (kanal) medyası

| Açı | Newsletter | Normal |
|--------|-----------|---------|
| URL'deki surface | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | düz isimler |
| Şifreleme | yok: artwork indirici, `artworkEncSha256`'yı sadece newsletter-olmayan içerik için gerektirir (`required fields missing - artworkEncSha256 is null for encrypted content`); diğer tipler için passthrough stream'i `C59535Qnh` (identity) mevcut. `MmsType` satırları hâlâ HKDF info byte'larını taşır (kullanılmıyor, inferred) |
| Yükleme token'ı | rastgele, hash-bağlı değil (bölüm 8.2) | kurulum-başına sır + hash |
| Route filtresi | `newsletter` ile başlayan isimler için hot / hash bucket mantığı yok | bucket mantığı (9.2) |
| `media_conn` ip token'ı | `ip_token`, `set_ip_token`'dan bağımsız olarak newsletter için uygulanır (flag **12149**) | sadece `set_ip_token` doğruyken |
| Sunucu işi | video için `server_thumb_gen=1` (flag'ler **11191**, **11192**), `server_transcode=1` | ayarlanmaz |
| Flag **27920** | `C15490gQ`'nin newsletter path'inde okunur; etkisi unknown | |

---

## 14. Express path ve diğer yükleme varyantları

| Varyant | Kanıt |
|---------|---------|
| Express path | bir E2E mesajı olarak gönderilen `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) (`FMessageMediaExpressPathNotify`, url, hash ve length gerektirir); `ExpressPathDownload`, `EP gain <ms> <bytes>` loglar; yükleme logu `Use static route supplier for express path upload`; yükleme sonucu 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Sunucu-tarafı davranış: unknown |
| Optimistic upload | surface `optimistic`; hash yeniden-kontrolü sonuçları 12; protokol: unknown |
| History / app state | `md-msg-hist`, `md-app-state`, kendi info string'leriyle normal pipeline'ı kullanır |
| Group history | `group-history`, info `Group History`, alıcı tarafından kontrol edilen mime `application/protobuf` (`C34677F2y`); path, bölüm 8.1'i izler (`/mms/group-history/...`, genel bileşimden inferred) |

### 14.1 Sohbet-teması wallpaper gönderimi (2.26.45.10'da yeni, found)

Sohbet-başına bir tema "sohbete gönder" akışı, değiştirilmeden bu genel pipeline'a biner. Giriş noktası: `ChatThemeViewModel.sendThemeToChat` (Kotlin coroutine; korunan debug metadata'sından `targetJid`, `sentBundle`, `sharedTheme` local'leri), seçilen wallpaper kaynağını (`DOWNLOADED`, `USER_PROVIDED`, `ANIMATED`, `GRADIENT`, `DEFAULT`, `NONE`) çözümler ve `ChatThemeSettingSenderImpl.A06` → `A01`'i çağırır.

| Adım | Detay (found) |
|------|-----------------|
| Yerel kopya | kaynak wallpaper `File`'ı, uygulama depolamasına `chat_theme_sent_wallpapers/<uuid>.jpg` altına kopyalanır |
| Yükleme | `ChatWallpaperUploader.A00`, `MediaUploadCoordinatorImpl.A0G`'i sarar (yukarıdaki bölüm 1-8'deki aynı `media_conn` → HKDF → AES-CBC → HMAC → POST pipeline'ı), `value` alanı literal string `"E2EE"` olan şifreleme modu `LX/8cp;->A02`'yi talep ederek |
| Sonuç kopyası | yükleme sonucu (`SGq`), alan-alan genel bir medya-eki tanımlayıcısına (`LX/8cr`) kopyalanır: yükleme-sonucu string'i → direct path, medya-key byte'ları, bir zaman damgası ve üç ek hash/HMAC byte dizisi |
| Setter yüzeyi | tanımlayıcı, sıradan görüntü-mesajı builder'larının kullandığı **aynı genel medya-eki setter arayüzü** olan `LX/1iA` (`LX/19i`'yi extend eder) üzerinden push edilir; alanları `imageMessage`'ın `directPath` (**11**), `mediaKey` (**8**) ve `fileSha256`/`fileEncSha256` byte alanlarıyla (**9**/**12**, bölüm 6) pozisyonel olarak hizalanır |
| Mimetype | aynı çağrıda `image/jpeg` açıkça ayarlanır |

Bu, yerel-sadece bir görüntü-tercih senkronizasyonu değil, gerçek bir sohbet eşine (`targetJid`) gönderilir: görüntü-destekli temalar için wallpaper bitmap'inin kendisi yeniden kodlanır ve standart E2EE medya yolu üzerinden yüklenir, böylece alıcı istemci bilinen bir tema preset'i uygulamak yerine gerçek bir görüntüyü indirir ve çözer. Bu akış için (group-history'nin `/mms/group-history`'sinin aksine, bölüm 14) özel bir yükleme medya-tipi veya HTTP-path override'ı bulunmadı — mevcut bir `MmsType`'ı yeniden kullandığı görünüyor (muhtemelen `image`, ayrı olarak doğrulanmamış).

**Unknown**: bu eki sonunda taşıyan tam `Message` oneof alanı — `LX/19i`/`LX/1iA`, birçok çıkış mesajı tipi tarafından kullanılan büyük paylaşımlı temel sınıflardır, ve setter'larının ötesindeki somut tahsis noktasına bu geçişte ulaşılmadı. Ayrıca unknown: düz-renk/wallpaper-yok bir tema seçiminin (`DEFAULT`/`NONE`) hiç gönderilip gönderilmediği, yoksa yerel-sadece kalıp kalmadığı. Bu özellik için yeni bir protobuf mesaj tipi veya GraphQL/MEX operasyonu bulunamadı (2.26.41.6→2.26.45.10 proto ve query diff'lerine karşı kontrol edildi); en savunulabilir okuma, bunun mevcut bir medya-mesajı alanına bindiğidir, en olası olarak `imageMessage`'ın kendisine — **inferred**, doğrulanmamış.

---

## 15. Medya parser'larının native sağlamlaştırılması (found, açılmış kütüphanelerin string'leri ve export'ları)

Superpack arşivinden 81 paylaşımlı nesne açılır. Saldırgan-kontrollü byte'ların bellek-güvensiz parser'ları sandbox'lanmış veya Rust ile değiştirilmiştir.

| Girdi | Bileşen | Sağlamlaştırma |
|-------|-----------|-----------|
| WebP | `libstatic-webp.so` (43 KB) | WebAssembly'ye derlenmiş ve wasm2c tarafından C'ye düşürülmüş libwebp (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), thread-local bir sandbox'ta wrapper `whatsapp::security::LibwebpSandbox`; Java flag'i `sWebPSandboxEnabled`; başarısızlık logu `sandboxed WebP decode failed: status=%d`; korumalar `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | bir wasm2c / WASI-minrt sandbox'ında giflib (`GiflibSandbox`, `wasi::minrt`); JNI sınıfları `SandboxedGifImage`, `SandboxedGifFrame`; koruma `Called memcpy for memory larger than the sandbox` |
| Ogg / Opus dosyaları | `libwhatsapp.so` | `libogg.wasm` ve `opusfile.wasm` için RLBox wasm2c sandbox'ları (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; trap logu `wasm2c sandbox trap: %s (code=%d)` |
| Konteyner ve stream ayrıştırma | `libwhatsapp.so` Rust crate'leri | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, DASH segmenter, edit list'ler), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (IPTC digital-source-type değerleri, `trainedAlgorithmicMedia` gibi, C2PA) |
| AV1 çözme | `libdav1d.so` | dav1d **1.5.1** (versiyon string'i); `dav1d_*` API'sini export eder |
| AV1 kodlama | `libwzav1.so` | versiyon 2.3.1; sadece `wz_encoder_*` ve `wz_codec_version*` export eder; decoder sembolü yok, bu yüzden uzak bitstream'leri ayrıştırmaz |
| H.264 / H.265 frame'leri | platform `MediaCodec` | uygulamanın dışında |

Rust'taki parser'lar bellek bozulması yerine panic'lerle başarısız olur (`assertion failed: ...`, `While parsing field '...' in ...`): string olarak found, etki inferred. `rlbox` sandbox'ı `libwhatsapp.so`'daki libogg ve opusfile'ı kapsar; diğer kütüphaneler RLBox wrapper'ı olmadan wasm2c kullanır (sembollerden inferred). Her gelen medya yolunun kullanıcı etkileşiminden önce bu parser'lara ulaşıp ulaşmadığı: unknown. Dinamik davranış (fuzzing, çalışma-zamanı çökmeleri): test edilmedi.

---

## 16. Feature flag'leri (çağrı noktalarında okunan id'ler; isimler çözülmemiş)

| Flag | Nerede | Kontrol ettiği |
|------|-------|----------|
| **149** | `RouteSelector`, `C43951qe` | `media_conn`'u tercihlerde kalıcı hale getir ve yeniden yükle |
| **257** | `Mms4RouteSupplier` ctor | üstel backoff nesnesi |
| **258** | `Mms4RouteSupplier.A03` | int: mod 0 için ek denemeler |
| **2134** | `A02` | hash-tabanlı indirme bucket'ı |
| **2136** | `A02` | hot-içerik penceresi (long) |
| **4073** | `A00` | medyayı kullanıcı proxy'si üzerinden yönlendir |
| **4836** | `Mms4DownloadUrlGenerator` | düşük-hit-oranlı tipler listesi (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | reporting token işleme |
| **9096** | `QBE` | `server_transcode=1` (newsletter video) |
| **11191** / **11192** | `C14210e6.A08` | newsletter görüntü / video için `server_thumb_gen=1` |
| **12149** | `RouteSelector.A0L`, `A03` | `ip_token` kullan |
| **12545** / **12446** | `A05` | deneme limitini deneme 3'ten sonra override et |
| **13748** | `QKS.A08` | HTTP 408'i yeniden dene |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | `RouteSelector` giriş noktaları | route seçimine yükleme flag'i olarak verilen boolean (semantik çözülmemiş) |
| **24661** | `MediaCryptoProvider` | non-E2EE key domain doğrulaması |
| **29305** | `PlainDownloadTransfer` | 416 işleme |
| **37982**, **38437** | `C43481Ixw` | Tigon prop'u, istek timeout'u |

---

## 17. Baileys (`baron-baileys-v2`, kaynak okundu, hiçbir şey test edilmedi)

| Açı | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| `media_conn` isteği | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js`'de opsiyonel bir `last_id` varyantı var | her zaman `<media_conn>`, önceki bir id varsa `last_id` ile |
| Ayrıştırılan alanlar | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | `maxContentLengthBytes` okunmaz; `auth_ttl`, `max_buckets`, `is_new`, `id`, fallback alanları, yetenek çocukları, retry sayıları, `ip_token` ekler |
| HKDF uzunluğu | `hkdf(key, 112, {info})`, 0-79 byte'ları kullanır | 80 byte; bir HKDF çıktısının ilk 80 byte'ı istenen uzunluğa bağlı değildir, bu yüzden IV, cipher key ve MAC key özdeştir |
| Info string'leri | `WhatsApp <X> Keys`; `gif` ve `ptv` Video'ya, `ptt` Audio'ya, `sticker` Image'a eşlenir | aynı string'ler ve eşlemeler |
| Cipher, MAC, hash'ler | AES-256-CBC, eklenen `HMAC-SHA256(macKey, iv + ct)[0:10]`, `ct + mac` üzerinde `fileSha256`, `fileEncSha256` | aynı |
| Yükleme URL'i | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Hash kodlaması | url-safe base64, `=` padding çıkarılmış, sonra `encodeURIComponent` | url-safe base64, `=` padding korunmuş |
| Token | url-safe `fileEncSha256` | `SHA-256(installSecret || fileEncSha256)` (newsletter: rastgele) |
| Path tablosu | `sticker` ve `thumbnail-link`, `/mms/image`'a, `ptv`, `/mms/video`'ya, `md-msg-hist`, `/mms/md-app-state`'e, `ptt` yok | `MmsType` string'i path segmentidir: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Header'lar | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | `Origin` bulunamadı; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | her host'u sırayla bir kez dener | denemeleriyle route sağlayıcısı, 401 / 403 token değişimi, resume probe'u |
| Resume | bulunamadı (`resume=1`, `Content-Range` yok) | `resume=1` probe'u ve `Content-Range` |
| Sidecar'lar | `src`'de `streamingSidecar`, `firstScanSidecar` veya `scansSidecar` üretimi bulunamadı | video, ses, progressive görüntüler için üretilir |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | dahili olarak milisaniye, proto'da saniye |
| Retry receipt'i | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = stanza id, IV 12 byte, HKDF info `WhatsApp Media Retry Notification` | writer durumu 327 aynı node düzenine sahip; IV 12 byte ve info string'i found'dur; GCM / AAD inferred'dir |
| Retry sonuç eşlemesi | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | uygulanamaz (2 ve 3 değerlerini karşılaştırır) |

Pratik sonuçlar (sadece kod okundu): bir `md-msg-hist` nesnesinin Baileys yüklemesi, Android istemcisinden farklı bir path string'i kullanır; path'teki padded base64 görünür bir farktır; bu varyantlar için herhangi bir sunucu toleransı unknown'dır.

---

## 18. Hata durumları

| Belirti | Neden | Düzeltme |
|---------|-------|-----|
| Yükleme 401 / 403 | `auth` süresi dolmuş veya değiştirilmiş | `media_conn`'u yenile, yeni `auth` ile yeniden gönder |
| Yükleme `direct_path` döndürmüyor | yükleme reddedildi veya tamamlanmadı | durumu kontrol et; `resume=1` ile resume probe'u |
| İndirme 404 / durum 5 `too_old` | nesne CDN'de süresi dolmuş | `server-error` receipt'ini gönder (bölüm 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | bozuk byte'lar veya yanlış `fileEncSha256` | yeniden getir; hash kaynağını doğrula |
| MAC kontrolü başarısız | yanlış medya key'i, yanlış HKDF info'su (tip karışıklığı) veya kesilmiş dosya | doğru `MmsType`'ın info string'ini kullan; Image info'yu `sticker-pack` veya `ptt` satırları için yeniden kullanma |
| `invalid_url` (8) | host CDN allow-list'inin dışında | sadece listelenen suffix'leri kabul et |
| `throttle` (12), HTTP 507 | sunucu throttle'ı | `backoff` saniye kadar bekle (maks 10800) |
| `no_route` (11) | tip için kullanılabilir `media_conn` host'u yok | `media_conn` iste, yetenek tag'lerini kontrol et |
| `failed_no_media_key` (29), `no_sidecar` (30) | proto alanı eksik | `mediaKey`'i gerektir; sidecar sadece streaming için |

---

## 19. Ayırt edilmesi gereken noktalar

| Karıştırılmaması gereken | Gerçek |
|----------------|------|
| `media_conn` host listesi vs yükleme URL'i | IQ host'ları ve bir `auth` verir; URL path'i, token'ı ve query'si transfer-başına inşa edilir |
| `auth` vs `token` | `auth`, `media_conn`'dan hesap-seviyesi token'dır; `token` dosya-başınadır |
| HKDF 80 vs 112 byte | aynı key'ler; Android 80 türetir |
| `fileSha256` vs `fileEncSha256` | plaintext hash'i vs `ciphertext + mac10`'un hash'i |
| Path'teki `fileEncSha256` vs `directPath` | yükleme path'i hash'i kullanır; indirme sunucunun döndürdüğü `directPath`'i kullanır |
| `mediaKeyTimestamp` vs key yeniden-kullanım penceresi | wire'da saniye cinsinden zaman damgası; gönderende 2-3 günlük yeniden-kullanım penceresi |
| Streaming sidecar'ı vs `fileEncSha256` | parça-başına 10-byte'lık MAC'ler vs tüm-dosya hash'i |
| Medya retry'i vs yeniden gönderme | gönderen aynı nesneyi yeniden yükler ve yeni bir `directPath` ile cevaplar; mesaj yeniden gönderilmez |
| Newsletter medyası vs normal medya | şifrelenmemiş, surface `newsletter`, rastgele token |
| `libwzav1` vs `libdav1d` | encoder vs decoder; sadece decoder uzak veriyi ayrıştırır |

---

## 20. Tam akış (bir görüntüyü gönderme ve alma)

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

## 21. Bilinmeyenler

| Öğe | Durum |
|------|--------|
| Sunucu davranışı (token doğrulama, dedupe, nesne ömrü, view-once silme) | sunucu tarafı |
| Query adları `_nc_cbep`, `_nc_rmr`, `type`; flag **21807** ve `PTU.*` id'leri | isimler veya anlam çözülmemiş |
| `MmsType`'taki sayısal id'ler (1, 20, 23, 25, 37, 42, 44, 57, ...) | anlam çözülmemiş |
| Native medya-retry cipher'ı (AES-GCM, AAD, key uzunluğu) | info string'i found; algoritma inferred |
| `ip_token` tüketimi, `X-FB-nc-oc` değeri, `Companion_User_Secret` kaynağı | çözülmemiş |
| NON_E2EE medya key domain'inin kullanımı | çözülmemiş |
| Express path ve optimistic upload protokolleri | çözülmemiş |
| Denemeler arasındaki tam host sırası ve moda-bağlı deneme sayıları | decompile edilmiş kontrol akışı bozuk |
| Hangi gelen medyanın kullanıcı etkileşiminden önce hangi sandbox'lanmış parser'a ulaştığı | eşlenmemiş |
| Trafik | hiçbir şey yakalanmadı; dinamik test yok |
