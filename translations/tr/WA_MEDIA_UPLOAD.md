<!-- src-sha1: a94958787eccb3db407fbb92cf700d9a4d424f4a -->
# WhatsApp Media Upload — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android medya aktarımı: `media_conn` IQ (host'lar, auth, ttl, bucket'lar, fallback host'lar), yükleme ve indirme URL'sinin oluşturulması ve HTTP parametreleri, HKDF info string'leriyle medya türü tablosu, medya anahtarının üretimi ve türetilmesi, AES-CBC + HMAC şifreleme, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, küçük resimler (thumbnail), video / ses / aşamalı (progressive) görüntüler için streaming sidecar'lar, devam ettirilebilir (resumable) yükleme, route seçimi, yeniden deneme ve backoff, yükleme ve indirme hata kodları, medya retry receipt'i ve `mediaretry` bildirimi, tek seferlik görüntülenen (view-once) ve durum (status) medyası, newsletter (kanal) medyası, express path, medya parser'larının istemci tarafı native sertleştirmesi, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

Medya hiçbir zaman chatd akışı içinde taşınmaz (bkz. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Mesaj yalnızca bir protobuf referansı (anahtar, hash'ler, `directPath`) taşır; baytlar medya host'larına açılan ayrı HTTPS bağlantılarıyla gider. chatd tek bir şey sağlar: host adlarını ve kısa ömürlü bir yükleme auth token'ını dağıtan `media_conn` IQ'su. Tüm ifadeler çözülmüş (decompile edilmiş) APK'nın ve açılmış native kütüphanelerin statik analizinden gelir; ağ üzerinde hiçbir şey yakalanmadı. Kademeler: **found** = kodda veya string'lerde okundu, **inferred** = çıkarım, **unknown** = çözülemedi.

| Katman | 2.26.41.6 adı | Rol |
|--------|----------------|-----|
| Route seçici | `RouteSelector` (`C10950Wx`) | mevcut `media_conn` sonucunu, yenileme zamanlayıcısını, throttle'ı ve route factory'sini tutar |
| `media_conn` parser'ı | `C43951qe` (IQ sonuç handler'ı), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | `<media_conn>` / `<host>` öğelerini ayrıştırır |
| Route supplier | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (statik supplier'lar) | her denemede host seçer, auth token'ını değiştirir |
| Retry sürücüsü | `TransferRetries` (`C44566Jd2`) | tek bir aktarımın etrafındaki deneme döngüsü |
| Medya türü tablosu | `MmsType` (`C15530gU`) | tür başına: path string'i, HKDF info baytları, sayısal id |
| Anahtar sağlayıcı | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF 80 bayt, non-E2EE domain anahtarı |
| Cipher stream'leri | `M2I` (şifreleyerek yaz), `M23` (şifreleyerek oku), `P9N` / `P1X` / `P1Y` (sidecar MAC'leri), `C51101MlN` (aralıklı (ranged) çözme) | AES-CBC + HMAC |
| Yükleme sürücüsü | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (anahtar yeniden kullanımı), `C57333Po0` (anahtar üretimi + hash'ler) | hash'ler, sidecar'lar, yükleme orkestrasyonu |
| Yükleme URL'si | `C43489Iy4` | `/surface/type/hash?...` |
| İndirme URL'si | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | yükleme: `HttpsFormPost` (`C43478Ixt`, `K19`); indirme: `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) | taşıma |
| Resume probe | `HttpResumeCheck` (`C59524QnW`) | sunucuya kaç baytı olduğunu sorar |
| Retry receipt | `SendMediaErrorReceiptJob`, `HandlerThreadC21920sG` içindeki writer case 77 ve 327 | gönderenden yeniden yükleme ister |
| Retry bildirimi | `MediaRetryNotificationHandler` (`C1S0`, bildirim kodu 97) | yanıtı işler |
| Native | `libwhatsapp.so` (Rust medya crate'leri, RLBox sandbox'ları), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | parser'lar ve decoder'lar |

Raporun geri kalanını belirleyen noktalar:

- Android, medya anahtarından 112 değil **80** bayt türetir (IV 16, cipher key 32, MAC key 32) (bölüm 4).
- HTTP path'i `/{surface}/{type}/{urlSafeFileEncSha256}` biçimindedir; burada `type`, medyanın `MmsType` string'idir (`image`, `ptt`, `md-msg-hist`, ...), kaba bir sınıf değildir (bölüm 8.1).
- Android yükleme `token`'ı dosya hash'i değildir; kurulum başına bir sır ile dosya hash'i üzerinden alınan SHA-256'dır (bölüm 8.2).
- Newsletter (kanal) medyası aynı kodu paylaşır ancak `newsletter` surface'ini ve rastgele bir token kullanır; şifrelenmemiştir (artwork yolu için found, geri kalanı için inferred, bölüm 13).
- İndirme host'ları, dosya hash'inden türetilen bir bucket ile filtrelenir (bölüm 9.2).

---

## 2. `media_conn` IQ

### 2.1 İstek (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Timeout 32000 ms. Aynı anda yalnızca bir istek uçuştadır (`inFlightMediaRoutingRequestTime`); ikinci çağrı `not sending request` loglar ve geri döner. Genel bir throttle (`ChatdMediaThrottleManager`) çağrıyı bastırabilir (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Yanıt (found, `C43951qe.CFS`)

| Node / öznitelik | Tür | Kullanım |
|------------------|-----|----------|
| `media_conn@auth` | string, zorunlu | yükleme auth token'ı (`auth` query parametresi) |
| `@ttl` | saniye | bağlantı ömrü; sona erme = gönderim zamanı + ttl * 1000 |
| `@auth_ttl` | saniye | auth token ömrü; sona erme = gönderim zamanı + auth_ttl * 1000 |
| `@max_buckets` | long, varsayılan 0 | indirme bucket'ı için modül (bölüm 9.2) |
| `@is_new` | int, varsayılan 1 | 1 = host listesini değiştir; aksi halde önceki host'ları koru ve yalnızca token ile ttl'i al (`previous hosts retained`) |
| `@id` | string | `last_id` olarak saklanır, sonraki istekte geri gönderilir |
| `@max_auto_download_retry` | int, varsayılan 3 | otomatik indirmeler için yeniden deneme bütçesi |
| `@max_manual_retry` | int, varsayılan 3 | manuel indirmeler için yeniden deneme bütçesi |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | ayrıştırılır ve önbelleğe alınır; `ip_token` yalnızca flag **12149** açıksa ve `set_ip_token` true ise kullanılır (tüketim noktası: unknown) |
| `host` (tekrarlı) | node | bir route girdisi |

`host` öznitelikleri (found): `hostname` (zorunlu), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` veya `fallback`; başka her değer `primary` olur), `force_ip` (`"true"`). Alt öğeler: `<upload>`, `<download>`, `<download_buckets>`; alt etiket adları yetenek (capability) girdileridir. `upload` ve `download`, yalnızca sabit bir 34 medya türü string'i kümesinde görünen etiketleri tutar (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, `newsletter-*` ailesi ve `thumbnail-*` ailesi); `download_buckets` filtrelenmeden tutulur.

Bir route host'u yalnızca hostname'i `.whatsapp.net` ile bitiyorsa kullanılabilir (`Mms4RouteSupplier.A06`, `fallback_hostname` için de uygulanır).

### 2.3 Önbellekleme ve yenileme (found)

| Kural | Değer |
|-------|-------|
| Kalıcılık | flag **149** ile sonuç JSON olarak saklanır (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`), `route_selector_prefs` / `media_conn` altında; bir kez yüklenir, yalnızca auth henüz süresi dolmamışsa kullanılır |
| Yenileme kontrolü | aktarımdan önce: bağlantı veya auth 120000 ms içinde sona eriyorsa yeni IQ gönderilir ve 20000 ms'ye kadar beklenir (`requestroutesandwaitforauth`) |
| Zamanlayıcı | her sonuçtan sonra `auth expiry - 60000 ms`; foreground (`BgG`) yeniden kurar |
| Auth hatası | bir aktarımda HTTP 401 veya 403 yenilemeyi tetikler (`onmediatransfererrororresponsecode`), aktarım başına en fazla 2 token değişimi (`JW1.A00 < 2`), ardından deneme yeni `auth` ile tekrarlanır |
| Denemeden önce auth | `refreshAuthBeforeAttempt`, önbellekteki token'ın sona ermesine 120000 ms kala daha yeni bir token ile değiştirir (flag sembolü `PTU.A0D`) |

### 2.4 IQ hatası (found, `C43951qe.Brt`)

IQ sonucu içinde `<error code backoff>`:

| Kod | Davranış |
|-----|----------|
| 503 | medya throttle'ını sıfırla; sonraki yenilemeyi jitter'lı bir Fibonacci backoff'undan sonra planla (`3/4 * t + rand(t/2)`) |
| 507, backoff > 0 ile | medya isteklerini `now + min(backoff, 10800) s` zamanına kadar throttle et |
| diğer / 0 | yok sayılır |

---

## 3. Medya türleri ve HKDF info string'leri (found, `MmsType` `C15530gU` statik init)

Her `MmsType` bir path string'i (`A02`), kısa bir dosya türü etiketi (`A01`, örn. `IMG`), HKDF `info` baytlarını (`A03`) ve bir sayısal id'yi (`A00`) tutar. `info` baytları ham haliyle HKDF info olarak kullanılır (ek önek yok).

| HKDF info | `MmsType` path string'leri |
|-----------|----------------------------|
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

Notlar (found): `ptt` ve `audio` aynı Audio info'sunu paylaşır ancak path string'leri farklıdır; `sticker` Image info'sunu kullanır; `gif` ve `ptv` Video info'sunu kullanır; farklı çağrı noktaları için farklı sayısal id'lere sahip birkaç `image` satırı vardır (1, 23, 25, 37, 42, 44, 57; `sticker` 20'dir) (id anlamı unknown); `group-history`, info'su `WhatsApp <X> Keys` biçiminde olmayan tek girdidir. Profil resimleri (`ppic`) yalnızca route capability kümesinde ve indirme generator çağrılarında görünür, `MmsType` olarak yer almaz.

---

## 4. Medya anahtarı ve türetme

### 4.1 Anahtar üretimi (found)

| Öğe | Değer |
|-----|-------|
| Medya anahtarı | `SecureRandom`'dan 32 rastgele bayt (`C57333Po0`, `QIh.A0B` `new SecureRandom()`'dır) |
| Yeniden kullanım | anahtar, saklanan anahtar zaman damgasına göre `172800000 ms + SecureRandom.nextInt(86400000)`'dan (2 ila 3 gün, jitter'lı) gençse `MediaKeyGen/reuse key from message contents`; daha eski anahtarlar atılır (`key expired`) ve yeniden üretilir |
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

`N6U.A01` başka her uzunluğu reddeder (`Invalid length of derived secret`). Ciphertext uzunluğu: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (PKCS#5 dolgulu bloklar artı 10 MAC baytı).

### 4.3 Non-E2EE medya anahtarı (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (alan **74**, mesaj `DQT`) `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) ve `e2eeMediaKey` (**2**) taşır. Flag **24661** ile alıcı, mesajdaki anahtarın domain ile eşleştiğini kontrol eder (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); uyuşmazlıkta anahtarı olduğu gibi kullanmaya döner. Hangi ürünlerin NON_E2EE domain'ini kullandığı: unknown.

---

## 5. Şifreleme, MAC ve hash'ler

### 5.1 Cipher (found, `M2I`, `M23`, `N6U`)

| Adım | Ayrıntı |
|------|---------|
| Cipher | `AES/CBC/PKCS5Padding`, key = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, önce IV ile, sonra her ciphertext baytı ile güncellenir; digest'in ilk **10** baytı ciphertext'in sonuna eklenir |
| `fileSha256` | düz metin (plaintext) üzerinde SHA-256 (dosya üzerinde `P9M` digest stream'i) |
| `fileEncSha256` | ciphertext + 10 MAC baytı üzerinde SHA-256 |
| Çıktı | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Çözme tarafı (`P9N`, `M23`): MAC, IV + ciphertext üzerinden doğrulanır, ardından sondaki 10 baytla karşılaştırılır. Aralıklı (ranged) çözme (`C51101MlN`): aralık başlangıcı 0 değilse okunan ilk 16 bayt IV olarak kullanılır (önceki ciphertext bloğu); iç chunk'lar `AES/CBC/NoPadding` kullanır, son chunk PKCS#5 kullanır (cipher seçiminden inferred).

### 5.2 Zaman damgaları ve path'ler

| Alan | Değer |
|------|-------|
| `mediaKeyTimestamp` | anahtar nesnesinde tutulan milisaniye cinsinden yerel saat, protobuf'a saniye olarak yazılır (`C20H.A06` = `/1000`) |
| `directPath` | sunucunun döndürdüğü path string'i, mesajda ve DB sütunu `direct_path` içinde saklanır; query parametreleri taşıyabilir (örn. `_nc_hot` buradan okunur) |
| `url` | eski tam URL alanı; proto sınıflarında ve yükleme yanıtında hâlâ bulunur, ancak indirme generator'ı `directPath`'ten veya hash'ten kurulur (bölüm 9.1) |

### 5.3 İyimser (optimistic) hash kontrolleri

Sunucunun bildirdiği hash yerel olarak hesaplananla farklı olduğunda `MediaUpload/optimistic-hash-fail` ve `optimistic-plaintext-hash-fail` (yükleme sonucu 12) loglanır. İyimser yükleme (surface string'i `optimistic`) gönderim kesinleşmeden önce yükler; surface adının ötesindeki protokolü: unknown.

---

## 6. Medya mesajı alanları

Alan numaraları üretilmiş protobuf sınıflarından okundu. Sınıf adları alan düzenine göre eşleştirildi (inferred); numaralar found.

| Mesaj (sınıf) | Alan numaraları (ad = numara) |
|---------------|-------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| History bundle (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

`Message` container'ının (`C30628DTw`) numaraları (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage`, `BD3` container'ının alan **21**'idir.

### 6.1 Küçük resimler (thumbnail)

| Tür | Mekanizma (aksi belirtilmedikçe found) |
|-----|----------------------------------------|
| Inline | mesajdaki `jpegThumbnail` (**16**) baytları (image, video, document); sticker'larda `pngThumbnail` (**16**) |
| Yüklenen | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (image **26-28**, video **21-23**, document **13-15**); bölüm 3'teki Thumbnail HKDF info'larıyla `MmsType` `thumbnail-*` |
| Anahtar | proto'da ayrı bir thumbnail anahtar alanı yoktur, dolayısıyla thumbnail kendi mesajının medya anahtarıyla şifrelenir (inferred) |
| Sunucuda üretilen | yükleme query'si `server_thumb_gen=1`; yükleme yanıtı `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` döndürebilir |
| DB | tablo `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming ve sidecar'lar (found)

Sidecar, ciphertext chunk'ı başına bir tane olmak üzere 10 baytlık MAC'lerin listesidir; bir oynatıcının tüm dosyayı okumadan bir aralığı doğrulamasını sağlar.

| Öğe | Ayrıntı |
|-----|---------|
| Algoritma | `P9N.read`: her chunk için bir `HmacSHA256(macKey)` **önceki 16 ciphertext baytı** ile (ilk chunk için IV) başlatılır, chunk beslenir ve digest'in ilk 10 baytı saklanır |
| Birleştirme | `C57228PmG.A00` tüm 10 baytlık MAC'leri tek bir bayt dizisinde birleştirir |
| Video / ses | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); chunk boyutu **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Aşamalı (progressive) görüntü | `firstScanSidecar` (**18**) ve `firstScanLength` (**19**): `ceil(len/16)*16` baytlık tek chunk; `scansSidecar` (**21**) ve `scanLengths` (**22**): değişken chunk boyutları (`P1Y`) |
| Sticker | `firstFrameSidecar` (**12**) ve `firstFrameLength` (**11**) |
| Ayarlar | sunucu prop'u `streaming_upload_chunk_size` bir dictionary token'ıdır; etkisi: unknown |
| Eksik | indirme durumu 30 `failed_no_sidecar` |
| Sunucu streaming'i | yükleme query'si `stream=1` ve `streaming=riff` birlikte (bölüm 8.1); DASH: yanıttaki `dashManifestUrl` (**33**), `metadataUrl` (**30**) |

---

## 8. Yükleme

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Parça | Değer |
|-------|-------|
| `surface` | `mms` (normal), `newsletter` (kanallar), `optimistic` (gönderim öncesi yükleme); `AbstractC58025Pzy` |
| `type` | `MmsType` path string'i (bölüm 3), örn. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | `fileEncSha256`'nın standart base64'ü, `+` yerine `-` ve `/` yerine `_` ile; `=` dolgusu korunur (`StringUtils.A0B`) |
| `direct_ip` | authority bir IP ise 1 (`ip4` veya köşeli parantezli `[ip6]`), aksi halde 0 |
| `auth` | `media_conn` auth token'ı; `K19.A03` tarafından query parametresi olarak eklenir |
| `stream=1`, `streaming=riff` | istek streaming yüklemesiyse ikisi birlikte ayarlanır (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | yalnızca `newsletter-image` / `-status` (flag **11191**) ve `newsletter-video` / `-status` (flag **11192**) için |
| `server_transcode=1` | istek id'si 10 olan `newsletter-video` ve flag **9096** |
| `_nc_rmr=1` | newsletter olmayan yüklemeler (istek flag'i `A0N`) |
| `_nc_cbep=1` | istek izin verdiğinde ve flag **17404** açıkken (anlamı unknown) |
| `type`, `media_id`, `media_id_upload` | `media_id` = bir yükleme UUID'sinin en anlamlı 63 biti; `media_id_upload` = en az anlamlı 63 bit, yalnızca isteğin ek girdileri varsa; `type` çağıranın verdiği bir string'dir (anlamı: unknown) |

`_nc_cbep` ve `_nc_rmr` query adlarının anlamı unknown (yalnızca adlar).

### 8.2 Token (found, `C43489Iy4.A00`)

| Durum | Token |
|-------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`, istek başına yeni, dosyaya bağlı değil |
| Diğer | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret`, `SecureRandom`'dan 32 bayttır, bir kez oluşturulur ve preferences içinde `upload_token_random_bytes` olarak saklanır (base64 no-wrap, no-padding) |

`fileEncSha256` çözülemezse token yalnızca `SHA-256(installSecret)` olur. Yapının amacı: yükleyenin hash'i path'te açığa çıkarmadan bildiğini sunucu tarafında kontrol etmek (inferred).

### 8.3 HTTP isteği (found, `HttpsFormPost` `C43478Ixt`)

| Öğe | Değer |
|-----|-------|
| Kütüphane | özel bir `SSLSocketFactory` ile `HttpsURLConnection`; işaretçi `http_stack = HttpUrlConnection` |
| Method | POST (`HttpURLConnection` üzerinde `setDoOutput(true)`; açık method çağrısı yok) |
| Timeout'lar | connect 15000 ms, read 60000 ms |
| Header'lar | `Host: <route hostname>` (authority bir IP olabilir), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, isteğe bağlı `Companion_User_Secret` (null olmayan constructor argümanı; companion semantiği inferred) |
| Gövde (route var) | ham ciphertext stream'i, yalnızca tek dosya (`MMS4 upload only supports a single file`); uzunluk biliniyorsa sabit uzunluklu streaming modu, değilse chunked (`setChunkedStreamingMode(0)`); buffer 16384 bayt |
| Gövde (route yok) | `Content-Disposition: form-data` parçalarıyla eski `multipart/form-data` |
| Abort | thread interrupt veya cancel flag'inde stream dolgulanır (`UploadRequest/Post streaming padding bytes=`) ve bildirilen uzunluk tamamlanır (amaç inferred) |
| Yanıt | en fazla 1 MiB okunur; HTTP >= 400 kodu döndürür, gövde `onError`'a gider |

### 8.4 Yanıt (found, `MediaUploadTransfer` `C59523QnV`)

Okunan JSON anahtarları: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (yalnızca `[A-Za-z0-9-]{1,64}` ile eşleşirse kabul edilir), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (`thumbnail_direct_path`, `thumbnail_sha256` içeren iç içe JSON string'i), `metadata_url`, `dash_manifest_url`. `direct_path` içermeyen bir yanıt bu parser tarafından hata sayılmaz; sonraki aşamalar `FAILED_NO_DIRECT_PATH` (29) ile başarısız olur.

### 8.5 Devam ettirilebilir (resumable) yükleme (found)

| Adım | Ayrıntı |
|------|---------|
| Probe | aynı yükleme URL'si artı `resume=1` (`HttpResumeCheck`); JSON yanıtı `url`, `direct_path` ile `{"resume": "complete"}` (zaten yüklenmiş) veya `{"resume": <offset>}` |
| Devam | `Content-Range: bytes <offset>-*/*` ile POST, stream önce `<offset>` konumuna atlanır |
| Fallback'ler | `ResumeCheck/attempting fallback MMS upload form post`, bir WATLS (TLS) hatasından sonra da |
| Ayrıştırma hatası | durum `PBY.A03`, yükleme yeniden başlar |

### 8.6 Route supplier ve retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Kural | Ayrıntı |
|-------|---------|
| Deneme döngüsü | `TransferRetries/run attempt = N; route = ...`; route başına bir aktarım; `no routes` döngüyü bitirir |
| Host seçimi | capability kümesi medya türünü içeren `type=primary` host; ilk iki deneme onu kullanır; sonraki denemeler `type=fallback` girdisini ve onun `fallback_*` alanlarını kullanır (sıra, karışık control flow'dan inferred) |
| Deneme sayısı | varsayılan 4 (`4 - extra`); flag **12545** ve **12446** ile limit 3. denemeden sonra geçersiz kılınabilir; `max_auto_download_retry` / `max_manual_retry` (her biri varsayılan 3) moda bağlı sayıyı besler (eşleme inferred) |
| Gecikme | sabit 1000 ms (`RouteSelector.A01`); flag **257** ve ek denemelerle üstel: taban 1000 ms, `2^n`, jitter, üst sınır 3000 ms |
| Auth hatası 401 / 403 | başarısızlık olarak sayılmaz: daha yeni token beklenir (bütçe `A0J`, varsayılan 20000 ms), değiştirilir, yeniden denenir |
| Yeniden denenebilir HTTP durumu | `QKS.A08`: < 400 evet; 400-499 hayır, flag **13748** ile 408 hariç; >= 500 evet, 505 ve 507 hariç |
| Proxy | kullanıcı proxy'si ve flag **4073** ile medya authority'si proxy host'u olur ve port `proxy_media_port`'tan gelir (varsayılan 587) |
| Sağlık kontrolü | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, connect 15000 ms, read 30000 ms |

---

## 9. İndirme

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

Constructor bir medya hash'i, bir direct path veya bir cross reference ister (`media hash, direct path, or cross reference is required`). `mode`, `auto` veya `manual`dır. `_nc_map=whatsapp-nofna`, sunucu listesi `LOW_CACHE_HIT_RATE_MEDIA_TYPES` içindeki türler için eklenir (AB prop, flag **4836**). `auth` query'si bir flag'li yolda eklenir (`PTU.A03`) ve mevcut bir `auth` parametresinin yerine geçer. Profil resimleri `ppic` türünü kullanır; statik varlıklar `_nc_cat` ile `/wa/static` kullanır.

### 9.2 Bucket ve host seçimi (decompile edilmiş control flow, kısmen karışık)

- Host'lar `download` capability'sine ve bucket string'ini içeren `download_buckets`'a göre filtrelenir.
- Direct path, flag **2136**'daki pencereden daha genç bir `_nc_hot=<seconds>` taşıyorsa bucket `1`; aksi halde flag **2134** ve `max_buckets > 0` ile: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); fallback bucket `0`.
- Newsletter türleri ve flag'li durumlar hot / hash mantığını atlar.
- Seçilen bucket `_nc_cat` olarak gider.

### 9.3 HTTP isteği (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Öğe | Değer |
|-----|-------|
| Method | GET (Tigon veya `HttpURLConnection`) |
| Header'lar | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (flag'e bağlı), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (ETag biliniyorsa) |
| Kabul edilen | HTTP 200 ve 206 |
| Kısmi | önizlemeler 262144 baytlık bir önek kullanır (`Range: bytes=0-262143`) |
| 416 | `Content-Range` `*/<size>` ise ve yerel boyuta eşitse tamamlanmış sayılır; aksi halde yeniden başlat (flag **29305**) veya hata |
| İzin listesi | flag sembolü `PTU.A04` ile host, URL `category=PSA` içermedikçe `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` içinde olmalıdır (sonek eşleşmesi); aksi halde `invalid_url` (8) / log `host not in media CDN allow-list` |

### 9.4 Doğrulama (found)

Çözme stream'i MAC'i kontrol eder; hash aşamaları 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch` durumlarına eşlenir; eksik girdiler 26-30'a eşlenir (bölüm 10.2).

---

## 10. Hata kodları

### 10.1 HTTP durumu işleme

| Durum | Davranış |
|-------|----------|
| 401, 403 | `media_conn`'u yenile, auth'u değiştir, yeniden dene (en fazla 2 değişim) |
| 408 | yalnızca flag **13748** ile yeniden dene |
| 416 | bkz. 9.3 |
| 507 | indirme durumu 12 `throttle`, yeniden denenmez |
| 505 | yeniden denenmez |
| diğer 4xx | yeniden denenmez |
| 5xx, < 400 | deneme bütçesi içinde yeniden denenir |

### 10.2 İndirme durumu (found, `QKK` `A03`)

| Kod | Ad | Kod | Ad |
|-----|----|-----|----|
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

10, 22, 33 kodları ve diğer her şey `invalid` yazdırır. `QKK.A04`; 1, 2, 3, 11, 15, 16, 18, 19, 20 ve 25'i gruplar (ağ türü hatalar; etiket inferred).

### 10.3 Yükleme sonucu (found, metrik adları `media_upload_<NAME>`)

| Kod | Ad | Kod | Ad |
|-----|----|-----|----|
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

`QBE.A00` içindeki exception eşlemesi (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, diğer `IOException` 18 (ağ kapalı) veya 3, `CancellationException` 1, `C7CL` 21, geri kalan her şey 31. 5, 21, 24, 34, 35 veya 36 ile başarısız bir sonuçtan sonra önbellekteki anahtar ve hash (`A0B`, `A0C`) temizlenir.

---

## 11. Medya retry (yeniden yükleme isteği)

Bir indirme, nesne artık mevcut olmadığı için başarısız olduğunda (tipik olarak durum 5 `too_old` veya 404 sınıfı bir yanıt), alıcı göndericinin telefonundan yeniden yükleme yapmasını ister.

### 11.1 İstek: receipt `server-error` (found, `SendMediaErrorReceiptJob`)

| Varyant | Writer | Wire |
|---------|--------|------|
| Multi-device (kendi primary'si) | case 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Eski (legacy) | case 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (`rmr` yok) |

`enc_iv` 12 rastgele bayttır; `enc_p`, stanza id'sini taşıyan bir mesajdan native olarak üretilir (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`). Native kütüphane HKDF info'su `WhatsApp Media Retry Notification`'ı tutar; stanza id'si AAD olarak AES-GCM ve 32 baytlık HKDF anahtarı, 12 baytlık IV'den ve Baileys implementasyonundan inferred. Sunucu prop'ları `mms4_media_retry_notification_encryption_enabled` ve `mms4_server_error_receipt_encryption_enabled` dictionary token'larıdır (etki inferred: `<encrypt>` gönderilip gönderilmeyeceğini belirler).

### 11.2 Yanıt: bildirim `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Adım | Ayrıntı |
|------|---------|
| Hesap kontrolü | başka bir hesaptan gelen `rmr`, `cross-account-rmr` loglar ve flag sembolü `PTV.A0F` açık değilse atılır |
| Arama | `(chat, id, from_me)` ile mesaj; medya olmayan mesajlar `message is null or not media` loglar |
| Çözme | native (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); sonuç modeli `directPath` verir (mesaja kaydedilir) ve bir sonuç int'i |
| Sonuç | `<error code>` sonucu geçersiz kılar; handler değeri 2 ve 3 ile karşılaştırır (genel proto numaralandırmasıyla `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferred) |
| Devam | indirici yeni direct path'i alır (`resume reuploading download`); aktif indirici yoksa mesaj otomatik indirme için kuyruğa alınır |
| Raporlama | flag **5718** ile `reporting_token` mesaj için saklanır |

---

## 12. View-once ve status medyası

| Konu | Olgu (found) |
|------|--------------|
| Crypto / taşıma | normal medya ile aynı: aynı `MmsType`, aynı HKDF, aynı URL'ler; tabloda view-once türü yoktur |
| Flag | `viewOnce`, `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**) içinde bir alandır; container `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Yerel kurallar | gönderen kendi view-once medyasını açamaz (`senders can not view their own media`); view-once thumbnail'leri `EphemeralUpdateRunnable/deleteViewOnceThumbnails` tarafından silinir; medya anahtarı olmayan view-once ses gönderilmez (`unable to send encrypted media message due to missing mediaKey`) |
| Sunucunun nesneyi görüntülemeden sonra silip silmediği | unknown |
| Status (`status@broadcast`) | kendi sayısal id'leriyle normal `MmsType` satırlarını kullanır (image, video, gif, audio); `status` HKDF info'su yoktur; tek `*-status` türleri newsletter olanlardır (bölüm 13) |
| Status limitleri | dictionary token'ları `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` sunucu prop'larıdır (değerler: unknown) |
| Status indirme | `C59526QnY` bir `MediaDownload` ve bir `StatusMediaDownload` varyantı tutar; ikisi de URL'yi aynı generator ile kurar |

---

## 13. Newsletter (kanal) medyası

| Yön | Newsletter | Normal |
|-----|-----------|--------|
| URL'deki surface | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | düz adlar |
| Şifreleme | yok: artwork indirici `artworkEncSha256`'yı yalnızca newsletter olmayan içerik için ister (`required fields missing - artworkEncSha256 is null for encrypted content`); diğer türler için passthrough stream'i `C59535Qnh` (identity) vardır. `MmsType` satırları yine de HKDF info baytlarını taşır (kullanılmaz, inferred) |
| Yükleme token'ı | rastgele, hash'e bağlı değil (bölüm 8.2) | kurulum başına sır + hash |
| Route filtresi | `newsletter` ile başlayan adlar için hot / hash bucket mantığı yok | bucket mantığı (9.2) |
| `media_conn` ip token | `ip_token`, `set_ip_token`'dan bağımsız olarak newsletter için uygulanır (flag **12149**) | yalnızca `set_ip_token` true ise |
| Sunucu işi | `server_thumb_gen=1` (flag'ler **11191**, **11192**), video için `server_transcode=1` (flag **9096**) | ayarlanmaz |
| Flag **27920** | `C15490gQ`'nun newsletter yolunda okunur; etkisi unknown | |

---

## 14. Express path ve diğer yükleme varyantları

| Varyant | Kanıt |
|---------|-------|
| Express path | E2E mesaj olarak gönderilen `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) (`FMessageMediaExpressPathNotify`, url, hash ve uzunluk ister); `ExpressPathDownload` `EP gain <ms> <bytes>` loglar; yükleme logu `Use static route supplier for express path upload`; yükleme sonucu 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Sunucu tarafı davranış: unknown |
| İyimser (optimistic) yükleme | surface `optimistic`; hash yeniden kontrolü sonuç 12; protokol: unknown |
| History / app state | `md-msg-hist`, `md-app-state` kendi info string'leriyle normal pipeline'ı kullanır |
| Group history | `group-history`, info `Group History`, alıcı tarafından kontrol edilen mime `application/protobuf` (`C34677F2y`); path bölüm 8.1'i izler (`/mms/group-history/...`, genel kompozisyondan inferred) |

---

## 15. Medya parser'larının native sertleştirmesi (found, açılmış kütüphanelerin string'leri ve export'ları)

81 shared object superpack arşivinden açılır. Saldırgan kontrollü baytları ayrıştıran bellek-güvensiz parser'lar ya sandbox'a alınır ya da Rust ile değiştirilir.

| Girdi | Bileşen | Sertleştirme |
|-------|---------|--------------|
| WebP | `libstatic-webp.so` (43 KB) | WebAssembly'ye derlenmiş ve wasm2c ile C'ye indirgenmiş libwebp (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), thread-local sandbox içinde `whatsapp::security::LibwebpSandbox` wrapper'ı; Java flag'i `sWebPSandboxEnabled`; hata logu `sandboxed WebP decode failed: status=%d`; koruma `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | wasm2c / WASI-minrt sandbox'ında giflib (`GiflibSandbox`, `wasi::minrt`); JNI sınıfları `SandboxedGifImage`, `SandboxedGifFrame`; koruma `Called memcpy for memory larger than the sandbox` |
| Ogg / Opus dosyaları | `libwhatsapp.so` | `libogg.wasm` ve `opusfile.wasm` için RLBox wasm2c sandbox'ları (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; trap logu `wasm2c sandbox trap: %s (code=%d)` |
| Container ve stream ayrıştırma | `libwhatsapp.so` Rust crate'leri | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, DASH segmenter, edit list'ler), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (`trainedAlgorithmicMedia` gibi IPTC digital-source-type değerleri, C2PA) |
| AV1 decode | `libdav1d.so` | dav1d **1.5.1** (sürüm string'i); `dav1d_*` API'sini export eder |
| AV1 encode | `libwzav1.so` | sürüm 2.3.1; yalnızca `wz_encoder_*` ve `wz_codec_version*` export eder; decoder sembolü yok, dolayısıyla uzak bitstream'leri ayrıştırmaz |
| H.264 / H.265 kareleri | platform `MediaCodec` | uygulamanın dışında |

Rust'taki parser'lar bellek bozulması yerine panic ile başarısız olur (`assertion failed: ...`, `While parsing field '...' in ...`): string olarak found, etki inferred. `rlbox` sandbox'ı `libwhatsapp.so` içindeki libogg ve opusfile'ı kapsar; diğer kütüphaneler RLBox wrapper'ı olmadan wasm2c kullanır (semboller üzerinden inferred). Her gelen medya yolunun kullanıcı etkileşiminden önce bu parser'lara ulaşıp ulaşmadığı: unknown. Dinamik davranış (fuzzing, çalışma zamanı çökmeleri): tested değil.

---

## 16. Feature flag'leri (id'ler çağrı noktalarında okunduğu gibi; adlar çözülmedi)

| Flag | Nerede | Neyi kontrol eder |
|------|--------|-------------------|
| **149** | `RouteSelector`, `C43951qe` | `media_conn`'u preferences içinde kalıcı yap ve yeniden yükle |
| **257** | `Mms4RouteSupplier` ctor | üstel backoff nesnesi |
| **258** | `Mms4RouteSupplier.A03` | int: mod 0 için ek denemeler |
| **2134** | `A02` | hash tabanlı indirme bucket'ı |
| **2136** | `A02` | hot-content penceresi (long) |
| **4073** | `A00` | medyayı kullanıcı proxy'si üzerinden yönlendir |
| **4836** | `Mms4DownloadUrlGenerator` | düşük isabet oranlı türlerin listesi (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | reporting token işleme |
| **9096** | `QBE` | `server_transcode=1` (newsletter video) |
| **11191** / **11192** | `C14210e6.A08` | newsletter image / video için `server_thumb_gen=1` |
| **12149** | `RouteSelector.A0L`, `A03` | `ip_token` kullan |
| **12545** / **12446** | `A05` | 3. denemeden sonra deneme limitini geçersiz kıl |
| **13748** | `QKS.A08` | HTTP 408'i yeniden dene |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | `RouteSelector` giriş noktaları | route seçimine yükleme flag'i olarak verilen boolean (semantik çözülmedi) |
| **24661** | `MediaCryptoProvider` | non-E2EE anahtar domain doğrulaması |
| **29305** | `PlainDownloadTransfer` | 416 işleme |
| **37982**, **38437** | `C43481Ixw` | Tigon özelliği, istek timeout'u |

---

## 17. Baileys (`baron-baileys-v2`, kaynak okundu, hiçbir şey test edilmedi)

| Yön | Baileys | Android 2.26.41.6 |
|-----|---------|-------------------|
| `media_conn` isteği | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` isteğe bağlı bir `last_id` varyantına sahiptir | her zaman `<media_conn>`, önceki bir id varsa `last_id` ile |
| Ayrıştırılan alanlar | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | `maxContentLengthBytes` okunmaz; `auth_ttl`, `max_buckets`, `is_new`, `id`, fallback alanları, capability alt öğeleri, retry sayıları, `ip_token` eklenir |
| HKDF uzunluğu | `hkdf(key, 112, {info})`, bayt 0-79'u kullanır | 80 bayt; bir HKDF çıktısının ilk 80 baytı istenen uzunluğa bağlı değildir, dolayısıyla IV, cipher key ve MAC key aynıdır |
| Info string'leri | `WhatsApp <X> Keys`; `gif` ve `ptv` Video'ya, `ptt` Audio'ya, `sticker` Image'a eşlenir | aynı string'ler ve eşlemeler |
| Cipher, MAC, hash'ler | AES-256-CBC, eklenen `HMAC-SHA256(macKey, iv + ct)[0:10]`, `fileSha256`, `ct + mac` üzerinde `fileEncSha256` | aynı |
| Yükleme URL'si | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Hash kodlaması | url-safe base64, `=` dolgusu çıkarılmış, ardından `encodeURIComponent` | url-safe base64, `=` dolgusu korunmuş |
| Token | url-safe `fileEncSha256` | `SHA-256(installSecret || fileEncSha256)` (newsletter: rastgele) |
| Path tablosu | `sticker` ve `thumbnail-link` `/mms/image`'e, `ptv` `/mms/video`'ya, `md-msg-hist` `/mms/md-app-state`'e, `ptt` yok | `MmsType` string'i path segmentidir: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Header'lar | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | `Origin` bulunmadı; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | her host'u sırayla bir kez dener | denemeli route supplier, 401 / 403 token değişimi, resume probe |
| Resume | bulunmadı (`resume=1`, `Content-Range` yok) | `resume=1` probe'u ve `Content-Range` |
| Sidecar'lar | `src` içinde `streamingSidecar`, `firstScanSidecar` veya `scansSidecar` üretimi bulunmadı | video, ses, aşamalı görüntüler için üretilir |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | dahili olarak milisaniye, proto'da saniye |
| Retry receipt | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = stanza id, IV 12 bayt, HKDF info `WhatsApp Media Retry Notification` | writer case 327 aynı node düzenine sahiptir; IV 12 bayt ve info string'i found; GCM / AAD inferred |
| Retry sonuç haritası | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | uygulanamaz (2 ve 3 değerlerini karşılaştırır) |

Pratik sonuçlar (yalnızca kod okuma): bir `md-msg-hist` nesnesinin Baileys ile yüklenmesi Android istemcisinden farklı bir path string'i kullanır; path'te dolgulu base64 görünür bir farktır; bu varyantlara karşı herhangi bir sunucu toleransı unknown.

---

## 18. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| Yükleme 401 / 403 | `auth` süresi doldu veya değiştirildi | `media_conn`'u yenile, yeni `auth` ile tekrar gönder |
| Yükleme `direct_path` döndürmüyor | yükleme reddedildi veya eksik | durumu kontrol et; `resume=1` ile resume probe |
| İndirme 404 / durum 5 `too_old` | nesnenin CDN'deki süresi doldu | `server-error` receipt'ini gönder (bölüm 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | bozuk baytlar veya yanlış `fileEncSha256` | yeniden çek; hash kaynağını doğrula |
| MAC kontrolü başarısız | yanlış medya anahtarı, yanlış HKDF info (tür karışıklığı) veya kesilmiş dosya | doğru `MmsType`'ın info string'ini kullan; `sticker-pack` veya `ptt` satırları için Image info'sunu yeniden kullanma |
| `invalid_url` (8) | host CDN izin listesinin dışında | yalnızca listelenen sonekleri kabul et |
| `throttle` (12), HTTP 507 | sunucu throttle'ı | `backoff` saniye bekle (en fazla 10800) |
| `no_route` (11) | tür için kullanılabilir `media_conn` host'u yok | `media_conn` iste, capability etiketlerini kontrol et |
| `failed_no_media_key` (29), `no_sidecar` (30) | proto alanı eksik | `mediaKey` zorunlu kıl; sidecar yalnızca streaming için |

---

## 19. Temel ayrımlar

| Karıştırma | Olgu |
|------------|------|
| `media_conn` host listesi ve yükleme URL'si | IQ host'ları ve tek bir `auth` verir; URL path'i, token ve query aktarım başına kurulur |
| `auth` ve `token` | `auth`, `media_conn`'dan gelen hesap düzeyi token'dır; `token` dosya başınadır |
| HKDF 80 ve 112 bayt | aynı anahtarlar; Android 80 türetir |
| `fileSha256` ve `fileEncSha256` | düz metin hash'i ve `ciphertext + mac10` hash'i |
| path'teki `fileEncSha256` ve `directPath` | yükleme path'i hash'i kullanır; indirme sunucunun döndürdüğü `directPath`'i kullanır |
| `mediaKeyTimestamp` ve anahtar yeniden kullanım penceresi | wire'da saniye cinsinden zaman damgası; gönderende 2-3 günlük yeniden kullanım penceresi |
| Streaming sidecar ve `fileEncSha256` | chunk başına 10 baytlık MAC'ler ve tüm dosya hash'i |
| Medya retry ve yeniden gönderim | gönderen aynı nesneyi yeniden yükler ve yeni bir `directPath` ile yanıtlar; mesaj yeniden gönderilmez |
| Newsletter medyası ve normal medya | şifrelenmemiş, surface `newsletter`, rastgele token |
| `libwzav1` ve `libdav1d` | encoder ve decoder; yalnızca decoder uzak veriyi ayrıştırır |

---

## 20. Tam akış (bir resmi gönder ve al)

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
|-----|-------|
| Sunucu davranışı (token doğrulama, dedupe, nesne ömrü, view-once silme) | sunucu tarafı |
| Query adları `_nc_cbep`, `_nc_rmr`, `type`; flag **21807** ve `PTU.*` id'leri | adlar veya anlam çözülmedi |
| `MmsType` içindeki sayısal id'ler (1, 20, 23, 25, 37, 42, 44, 57, ...) | anlam çözülmedi |
| Native media-retry cipher'ı (AES-GCM, AAD, anahtar uzunluğu) | info string'i found; algoritma inferred |
| `ip_token` tüketimi, `X-FB-nc-oc` değeri, `Companion_User_Secret` kaynağı | çözülmedi |
| NON_E2EE medya anahtarı domain'inin kullanımı | çözülmedi |
| Express path ve optimistic yükleme protokolleri | çözülmedi |
| Denemeler arasındaki kesin host sırası ve moda bağlı deneme sayıları | decompile edilmiş control flow karışık |
| Hangi gelen medyanın kullanıcı etkileşiminden önce hangi sandbox'lı parser'a ulaştığı | haritalanmadı |
| Trafik | hiçbir şey yakalanmadı; dinamik test yok |
