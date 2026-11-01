<!-- src-sha1: d4ba76d600d4bfecb03ea6dfec4064e9d1ae1733 -->
# WhatsApp Çıkartmalar — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** `Message.StickerMessage` proto'su (görsel/Lottie metadata, avatar/AI/premium bayrakları, `emojis`, `accessibilityLabel`), gömülü sesli çıkartmalar (`StickerMessage.audioMessage`), `lottieStickerMessage` / `audioStickerMessage` genel sarmalayıcıları, `stickerPackMessage` (paket paylaşımı), çıkartma paketi yerel depolama ve `.was`/Lottie ZIP formatı, `stickerSyncRmrMessage` (bulunmadığı doğrulandı), üçüncü taraf çıkartma paketi intent'leri ve content-provider sözleşmesi, yerleşik AI çıkartma üretim sağlayıcısı, yerel çıkartma araması, özellik bayrakları; medya kriptografisi tekrarlanmıyor (bkz. [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md))

---

## 1. Genel Bakış

Android'de bir "çıkartma", birkaç farklı hat (wire) mesaj tipinin yanı sıra büyük bir birinci taraf uygulama alt sistemi (mağaza, yerel son kullanılanlar, arama, AI üretimi) ve üçüncü taraflara açık bir entegrasyon yüzeyinden (intent'ler + content provider'lar) oluşur. Tüm medya baytları (çıkartma görseli, paket ZIP'i, küçük resimler) diğer tüm eklerle aynı şifreli medya hattından geçer — `MmsType` satırları (`sticker`, `sticker-pack`, `thumbnail-sticker-pack`, `newsletter-sticker`, `newsletter-sticker-pack`) için [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) bölüm 3'e bakın.

| Varlık | `Message` alanı | Hat tipi | Rolü |
|--------|------------------|-----------|------|
| Tekil çıkartma | `stickerMessage` | **26**, `StickerMessage` (`C30611DTf`) | sohbette gönderilen tek bir çıkartma görseli/animasyonu |
| Sesli çıkartma (gömülü) | `StickerMessage.audioMessage` | `StickerMessage`'ın **26**'sı, `oneof audio` → `AudioMessage` | bir çıkartma gönderimine eklenen kısa sesli klip |
| Lottie sarmalayıcı | `lottieStickerMessage` | **74**, `FutureProofMessage` (`BD2`) | genel zarf, ad Lottie'ye özel bir yük ima ediyor; iç içe içerik çözülemedi |
| Sesli-çıkartma sarmalayıcı | `audioStickerMessage` | **134**, `FutureProofMessage` (`BD2`) | aynı genel zarf deseni, bu derlemede yeni; iç içe içerik çözülemedi |
| Çıkartma paketi | `stickerPackMessage` | **86**, `StickerPackMessage` (`C30610DTe`) | bir paketi (çıkartmaların ZIP'i) paylaşır/kurar |
| Çıkartma-senkron isteği | `stickerSyncRmrMessage` | **47** (eski derlemeler) | 2.26.41.6'daki `Message` proto'sunda **yok** (bkz. bölüm 7) |
| Durum çıkartma tepkisi | `statusStickerInteractionMessage` | **110**, `StatusStickerInteractionMessage` (`C30560DRg`) | bir durum (status) gönderisine tepki çıkartması; bu belgede sadece referans olarak geçer, kapsam dışı |
| Üçüncü taraf paket ekleme | Android `Intent` | `com.whatsapp.intent.action.ENABLE_STICKER_PACK` | harici uygulama WhatsApp'tan kendi barındırdığı bir paketi içe aktarmasını ister |
| Üçüncü taraf gönderim | Android `Intent` | `com.whatsapp.intent.action.SEND_STICKER` | harici uygulama tek bir WebP çıkartmasını WhatsApp'ın seçicisine teslim eder |
| Paket içerik sözleşmesi | `ContentProvider` (harici uygulamanın kendi) | `content://<authority>/metadata`, `/stickers`, `/stickers_asset` | WhatsApp'ın üçüncü taraf bir paketi nasıl okuduğu |
| AI çıkartma üretimi | `ContentProvider` (WhatsApp'ın kendi) | `content://com.whatsapp.provider.sticker_command/generate` | uygulama içi GenAI çıkartma oluşturma, content-provider çağrılarıyla kullanılır, bir sohbet mesajı değildir |

Katmanlar `IMPORTANT.md`'yi takip eder: **found** = decompile edilmiş kod/string/manifest içinde doğrudan okundu, **inferred** = kod şeklinden çıkarıldı, **unknown** = çözülemedi. Buradaki tüm kanıtlar statiktir (decompile edilmiş APK + manifest); hat üzerinde hiçbir şey yakalanmadı.

---

## 2. `Message.StickerMessage` (alan 26)

### 2.1 Alanlar (found, `C30611DTf`)

| Alan | # | Tip | Kullanım |
|-------|---|------|-----|
| `url` | 1 | string | eski tip tam URL |
| `fileSha256` | 2 | bytes | düz metin hash'i |
| `fileEncSha256` | 3 | bytes | şifreli metin+MAC hash'i, aynı zamanda yükleme yolu hash'i |
| `mediaKey` | 4 | bytes | 32 baytlık anahtar, HKDF bilgisi `WhatsApp Image Keys` (medya hattı, burada tekrarlanmıyor) |
| `mimetype` | 5 | string | sıradan çıkartmalar için `image/webp` |
| `height` / `width` | 6 / 7 | uint32 | piksel boyutları |
| `directPath` | 8 | string | indirme yolu |
| `fileLength` | 9 | uint64 | şifreli metin uzunluğu |
| `mediaKeyTimestamp` | 10 | int64 | saniye |
| `firstFrameLength` / `firstFrameSidecar` | 11 / 12 | uint32 / bytes | ilk animasyon karesi için sidecar (bkz. [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) bölüm 7) |
| `isAnimated` | 13 | bool | animasyonlu WebP |
| `pngThumbnail` | 16 | bytes | satır içi küçük resim |
| `contextInfo` | 17 | `ContextInfo` | alıntı/yanıt/reklam metadata |
| `stickerSentTs` | 18 | int64 | gönderim zaman damgası |
| `isAvatar` | 19 | bool | avatar çıkartması |
| `isAiSticker` | 20 | bool | AI tarafından üretilmiş çıkartma |
| `isLottie` | 21 | bool | çıkartma yükü düz bir WebP değil, bir Lottie animasyonudur (bkz. bölüm 4) |
| `accessibilityLabel` | 22 | string | ekran okuyucu metni |
| `premium` | 24 | int32 | çözülemedi (tüketici bulunamadı) |
| `emojis` | 25 | string | **found kullanım**: yerel arama etiketi, bkz. bölüm 9 |
| `audioMessage` | 26 | `AudioMessage` (`oneof audio`) | gömülü sesli-çıkartma klibi, bkz. bölüm 3 |

Alan numarası boşlukları 14, 15, 23: tanımlı alan yok; önceki kullanım bilinmiyor. Bu, başlangıç materyali olan `Messages/stickerMessage` notunu düzeltir — o not `emojis` (25)'i son alan olarak listeler ve alan 26'yı (`audioMessage`) hiç içermez — 2.26.41.6'da `C30611DTf` içinde var olduğu doğrulandı (`AUDIO_MESSAGE_FIELD_NUMBER = 26`) ve bu, güncel `baron-baileys-v2` proto'sundaki `oneof audio` bloğuyla eşleşiyor.

### 2.2 Mesaj-tipi-string sınıflandırması (found)

Bir `StickerMessage`/`StickerPackMessage` gönderimine bağlı gözlenen tip string'leri, analitik dispatch'ten (`C21880sC`) ve çıkartma-tipi yardımcı fonksiyondan toplandı: `sticker`, `avatar_sticker`, `genai_sticker`, `1p_sticker`, `user_created_sticker`, `sticker_pack`. `avatar_sticker` ve `genai_sticker`, `isAvatar`/`isAiSticker`'dan gelir; `1p_sticker` ve `user_created_sticker`, `StickerPackOrigin` enum'uyla (bölüm 5) örtüşür ama `sticker`, `1p_sticker` ve `user_created_sticker` arasında seçim yapan kesin karar fonksiyonu bu geçişte izole edilemedi (öncelik bilinmiyor). Baileys (`messages-send.js`), bu string'i istemci tarafında türetirken `isLottie`'yi `isAvatar`'dan önce kontrol eder; Android'in de aynısını yapıp yapmadığı doğrulanmadı.

### 2.3 `emojis` ve `accessibilityLabel` (found, başlangıç materyalinden yükseltildi)

- `emojis` (25): `EmojiGroupMapper`/`StickerSearchManager` tarafından yerel arama etiketi string'i olarak tüketilir — amacının alan adının ötesine geçtiğini doğrular (bölüm 9). Sunucuya sorgulanmıyor.
- *Gönderilmiş bir çıkartma* üzerindeki `accessibilityLabel` ile *üçüncü taraf paket çıkartması* (`StickerContentProviderFetcher`, bölüm 8) üzerindeki `sticker_accessibility_text`, her ikisi de statik bir çıkartma için **125** karakter, animasyonlu bir çıkartma için **250** karakter sınırına sahiptir (`ThirdPartyStickerFetcher`, literal int'ler 125/250; JADX 125 dalını, 125 değerini de barındıran ilgisiz bir alan olan `C30628DTw.SPLIT_PAYMENT_MESSAGE_FIELD_NUMBER` olarak hatalı gösterir — bu bir decompiler adlandırma artefaktıdır, sayısal değerin kendisi doğrudan bytecode'dan okunur).

---

## 3. Sesli çıkartmalar: `StickerMessage.audioMessage` ve `audioStickerMessage` (134)

İki ayrı, found mekanizma, birbirine karıştırmayın:

| Mekanizma | Alan | Kanıt |
|-----------|-------|----------|
| Gömülü klip | `StickerMessage.audioMessage` (26, `oneof audio`) | `C30611DTf` içinde mevcut; `baron-baileys-v2`'nin `WAProto.proto`'suyla tam eşleşiyor (`oneof audio { Message.AudioMessage audioMessage = 26; }`) |
| Bağımsız sarmalayıcı | `Message.audioStickerMessage` (134, `FutureProofMessage`/`BD2`) | 2.26.41.6 için `C30628DTw`'de yeni alan, `Messages/` başlangıç materyalinde yok; `lottieStickerMessage` (bölüm 1) ile aynı genel-zarf deseni, iç içe içerik bilinmiyor |

İstemci destek paketi `com.whatsapp.stickers.sound`, bir "sesli çıkartma" yazım özelliğini doğrular: `StickerOpusEncoder` (`nativeEncode(short[] pcm, String outPath)`, kaydedilen bir klibin native Opus kodlaması) ve `SoundStickerAudioDownloader` (eklenmiş sesin oynatılmadan önce indirildiğinden emin olur, sıradan medya hattından geçirir). Bu, kısa bir sesli notanın yeni alan-134 sarmalayıcısı yerine (veya onunla birlikte) alan 26 üzerinden gömülmesiyle uyumludur.

---

## 4. Çıkartma dosya formatları

### 4.1 Düz ve animasyonlu WebP (found)

`mimetype = image/webp`; `isAnimated`, animasyonlu bir WebP'yi işaretler. Çözme işlemi `libstatic-webp.so`'nun sandbox'lanmış libwebp'inden geçer (bkz. [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) bölüm 15).

### 4.2 Lottie çıkartmaları — `.was` ZIP konteyneri (found, `LottieStickerZipEntrySaver` / `C161836tL`)

`isLottie` ayarlandığında, çıkartmanın medya dosyası bir WebP değildir: bir `LottieStickerZipEntrySaver` üzerinden kaydedilen ve okunan bir ZIP arşividir ve şunları içermelidir:

| Girdi | Rol |
|-------|-----|
| `animation/animation.json` | Lottie (bodymovin) JSON animasyonu, birincil |
| `animation/animation.json.trust_token` | JSON için eşlik eden güven/imza token'ı |
| `animation/animation_secondary.json` + `.trust_token` | isteğe bağlı ikincil animasyon varyantı |

Genel paket seviyesi çıkarıcı (`C161826tK`, log etiketi `StickerPackZipEntrySaver`, temel sınıf adı `SafeZipEntrySaver`), ayrıca çıkarılan dosya uzantılarını `png`, `webp` ve `was` ile sınırlar — yani kamuya açık `.was` ("WhatsApp Animated Sticker") dosya uzantısı, bu Lottie konteynerinin disk üzerindeki/ZIP-girdisi işaretidir ve kabul edilmeden önce bir içerik koklayıcı (sniffer) ile iddia edilen MIME (`application/was`) karşılaştırılarak kontrol edilir.

### 4.3 Paket ZIP çıkarma sınırları (found, `C161826tK` constructor)

| Sınır | Değer |
|-------|-------|
| Paket ZIP başına maksimum girdi | **65** (sabit kodlanmış) |
| Girdi başına maksimum bayt | sözlük token'ı (bayrak id **1900**, KB) × 1024 |
| Paket başına toplam maksimum bayt | aynı token × 1024 × 65 |
| Yol aşımı (path traversal) | her girdinin hedef yolu normalize edilir ve hiçbir bayt yazılmadan önce paketin kendi dizini içinde çözülmelidir ("Zip entry is attempting to save outside of current directory") — zip-slip koruması |
| Reddedilen girdi | başarısız bir içerik-tipi koklamasından sonra silinir, `StickerPackZipEntrySaver/file in zip is not valid` olarak loglanır |

Bu, `Messages/stickerPackMessage` başlangıç notunu (sadece 2.26.34.4'ten bir log referansı olarak "ZIP extraction and file validation" ve "validates sticker files reside within extracted ZIP boundaries"i andan, sınırlar olmadan) doğrular ve genişletir.

---

## 5. `Message.StickerPackMessage` (alan 86)

### 5.1 Alanlar (found, `C30610DTe`) — başlangıç materyali ve `baron-baileys-v2` ile tam eşleşir

| Alan | # | Tip |
|-------|---|------|
| `stickerPackId` | 1 | string |
| `name` | 2 | string |
| `publisher` | 3 | string |
| `stickers` | 4 | repeated `Sticker` |
| `fileLength` / `fileSha256` / `fileEncSha256` / `mediaKey` / `directPath` / `mediaKeyTimestamp` | 5, 6, 7, 8, 9, 13 | paket ZIP medya referansı (`MmsType` `sticker-pack`, HKDF bilgisi `WhatsApp Sticker Pack Keys`) |
| `caption` | 10 | string |
| `contextInfo` | 11 | `ContextInfo` |
| `packDescription` | 12 | string |
| `trayIconFileName` | 14 | string |
| `thumbnailDirectPath` / `thumbnailSha256` / `thumbnailEncSha256` / `thumbnailHeight` / `thumbnailWidth` | 15–19 | paket küçük resmi (`MmsType` `thumbnail-sticker-pack`) |
| `imageDataHash` | 20 | string |
| `stickerPackSize` | 21 | uint64 |
| `stickerPackOrigin` | 22 | enum `StickerPackOrigin` |

İç içe `Sticker`: `fileName` (1), `isAnimated` (2), `emojis` (3, repeated), `accessibilityLabel` (4), `isLottie` (5), `mimetype` (6), `premium` (7).

`StickerPackOrigin`: `FIRST_PARTY` = 0, `THIRD_PARTY` = 1, `USER_CREATED` = 2.

### 5.2 Yerel depolama (found, `AbstractC149676Ty.java`, `C1888782f.java`, `C0R5.java`)

| Tablo | Sütunlar |
|-------|-------|
| `message_sticker_pack` | `message_row_id`, `sticker_pack_id`, `pack_name`, `pack_description`, `publisher`, `tray_icon_file_name`, `image_data_hash`, `sticker_pack_size`, `sticker_pack_origin`; `pack_name` ve `publisher` üzerinde indekslenmiş |
| `message_sticker_pack_stickers` | `_id`, `message_row_id`, `file_name`, `is_animated`, `emojis`, `accessibility_label`, `is_lottie`, `mimetype` |

Bu, başlangıç materyalinin sürüm-2.26.34.4 işaretçisini (`StickerPackMessageMapper` / `message_sticker_pack`, sadece bir log string'i ile anılan) 2.26.41.6'nın somut sütun listesiyle değiştirir.

---

## 6. `stickerSyncRmrMessage` — 2.26.41.6'da bulunmadığı doğrulandı

Alan 47 (`StickerSyncRMRMessage`: `filehash` repeated string, `rmrSource` string, `requestTimestamp` int64), 2.26.41.6 için `C30628DTw` (`Message` konteyneri) içinde **görünmüyor**: hiçbir alan numarası 47 ona eşlenmiyor ve decompile edilmiş ağaçta `StickerSyncRMR`/`stickerSyncRmr` içeren hiçbir sınıf veya string yok. Bu, başlangıç materyalinin alanın 2.26.36.1'de de zaten yok olduğuna dair kendi gözlemiyle eşleşiyor ve genişletiyor — beş derleme sonra bile yok. Kanıt sözleşmesine göre bu **gözlenen bir yokluktur**, doğrulanmış bir kaldırma değil: yeniden adlandırılmış, farklı bir proto'ya taşınmış veya tamamen düşürülmüş mü olduğu bilinmiyor.

`filehash`-anahtarlı bir tablo hâlâ var, ama ilgisiz bir amaç için: `RecentStickerDBStorage` (`C6VB`, `C17460jr`, `C6V8`), son kullanılanlar tepsisi için yerel olarak gönderilmiş/alınmış çıkartmaları dosya hash'ine göre takip eder — bu yerel bir defter tutmadır, hat senkron mesajı değildir ve onunla karıştırılmamalıdır.

---

## 7. Üçüncü taraf çıkartma paketi API'si

Bu, kamuya açık, kural olarak belgelenmiş bir entegrasyon yüzeyidir (`com.whatsapp.sticker.READ` izin ailesi); aşağıdakilerin tümü `AndroidManifest.xml`'de ve bunu destekleyen sınıflarda bulundu (found).

### 7.1 Manifest yüzeyi

| Bileşen | Bildirim |
|-----------|-------------|
| İzin | `com.whatsapp.sticker.READ` — WhatsApp sorgu yapmadan önce üçüncü taraf uygulamanın kendi content provider'ında gereken `android:readPermission` |
| Paket ekleme aktivitesi | `com.whatsapp.stickers.ui.thirdpartystickers.AddThirdPartyStickerPackActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.ENABLE_STICKER_PACK` + `category DEFAULT` |
| Paket ekleme eski takma ad | `activity-alias` `com.whatsapp.stickers.thirdpartystickers.AddThirdPartyStickerPackActivity` → aynı hedef (eski paket adına göre derlenmiş uygulamalar için korunmuş) |
| Tekil çıkartma gönderme aktivitesi | `com.whatsapp.stickers.command.send.SendStickerCommandActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.SEND_STICKER` + `category DEFAULT` + `data mimeType="image/webp"` |
| Beyaz liste kontrolü sağlayıcısı | `com.whatsapp.provider.sticker_whitelist_check` → `WhitelistPackQueryContentProvider`, `exported="true"` |
| Derin bağlantı | `whatsapp://stickerpack` (`<data android:host="stickerpack" android:scheme="whatsapp"/>`); bu özel host için hedef aktivite/yönlendirme bu geçişte izole edilemedi (bilinmiyor) |

### 7.2 `ENABLE_STICKER_PACK` intent sözleşmesi (found, `AddThirdPartyStickerPackActivity`)

İstek ekstraları (`String`): `sticker_pack_id`, `sticker_pack_authority`, `sticker_pack_name`.

Herhangi bir şey getirilmeden önce doğrulama:
1. `getCallingActivity()` null olmamalı (intent, bir broadcast-tarzı başlatma değil, `startActivityForResult`'tan gelmelidir).
2. `PackageManager.resolveContentProvider(sticker_pack_authority, …)` bir sağlayıcıya çözülmelidir.
3. Çözülen sağlayıcının paketi, çağıran aktivitenin paketine eşit olmalıdır — **bir uygulama ancak kendisine ait authority'ler için kefil olabilir**.

Döndürülen `Intent` üzerindeki sonuç ekstraları (birisi): `add_successful=true`, `already_added=true`, `validation_error=<string>`, veya `CancelReason.USER_CANCELLED=true` (kullanıcı ekleme iletişim kutusunu kapattı).

### 7.3 Paket içerik-sağlayıcı sözleşmesi (found, `StickerContentProviderFetcher`/`C179697lN`, `C175327dG`)

WhatsApp, üçüncü taraf bir paketi *çağıran uygulamanın kendi* sağlayıcısını verilen authority'de sorgulayarak okur, bu sağlayıcı üzerinde `readPermission == "com.whatsapp.sticker.READ"` ile korunur:

| URI | Döndürülen sütunlar |
|-----|-------------------|
| `content://<authority>/metadata/<identifier>` | `sticker_pack_identifier`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_icon`, `android_play_store_link`, `ios_app_download_link`, `image_data_version`, `whatsapp_will_not_cache_stickers`, `animated_sticker_pack` |
| `content://<authority>/stickers/<identifier>` | `sticker_file_name`, `sticker_emoji`, `sticker_accessibility_text` |
| `content://<authority>/stickers_asset/<identifier>/<filename>` | açılabilir akış (tepsi simgesi veya tekil çıkartma dosyası) |

Fetcher'da bulunan doğrulama: `authority`/`identifier`, geçersiz karakterleri reddeder; `identifier` ≤ 128 karakter; döndürülen `sticker_pack_identifier`, istenen identifier'ı yansıtmalıdır; `sticker_pack_icon` dosya adı ≤ 128 karakter; `android_play_store_link`, `play.google.com` içermelidir, `ios_app_download_link`, `itunes.apple.com` veya `apps.apple.com` içermelidir; `publisher`/`name` boş olmamalı ve ≤ 128 karakter; `tray` id boş olmamalı; çıkartma sayısı `[flag 17124, flag 17327]` aralığında olmalıdır (sözlük-token sınırları, sayısal değerler bu geçişte çözülemedi); getirilen her çıkartma varlığı, statik bir paket için **~103424 bayt (101 KB)**, animasyonlu bir paket için **~512512 bayt (500.5 KB)** ile sınırlıdır (`Math.min(animated ? 500 : 100, 1024) + 1) * 1024`; aşırı büyük veya okunamayan akışlar, tüm paketi iptal etmek yerine dosya null olarak ayarlanıp düşürülür. Sağlayıcının paketinin getirme sırasında ortadan kaybolmasını işleyen eşleşen bir `app may have been deleted` / `third_party_sticker_app_deleted` yolu var.

Ayrı bir boolean bayrak (**13081**), zaten beyaz listeye alınmış bir paketin content provider'dan yeniden getirilip getirilmeyeceğini veya önbellekten sunulup sunulmayacağını kontrol eder ve bayrak **22198**, daha eski bir eşzamanlı iletişim-kutusu-odaklı ekleme akışı ile çıkartma-paketi önizleme ekranına doğrudan yönlendirme arasında geçiş yapar; bayrak **13711**, aktivite yerine content-provider kısayol yolu (bölüm 7.5) üzerinden kurulum yaparken iki dahili kurulum varyantı (`C175327dG.A00` vs `A01`) arasında seçim yapar.

### 7.4 `SEND_STICKER` intent sözleşmesi (found, `SendStickerCommandActivity`)

Veri: çağıran uygulamanın kendi sağlayıcısından, authority'si o çağıran pakete çözülmesi gereken bir `content://` URI'si. Referans verilen dosya tam olarak **512×512** WebP olarak çözülmeli ve ≤ **500000 bayt** olmalıdır; istemci bunu normal çıkartma hattı (hash, saklama, ekleme) üzerinden yeniden damgalar ve varsa şu `Intent` ekstralarını `Sticker` paket metadata'sı olarak ekler: `sticker_accessibility_text`, `sticker_pack_id`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_ios_store_link`, `sticker_pack_play_store_link` (iki mağaza bağlantısı, bölüm 7.3'tekiyle aynı alan adı kontrolleriyle doğrulanır).

### 7.5 Beyaz liste kontrolü sağlayıcısı (found, `WhitelistPackQueryContentProvider`)

`content://com.whatsapp.provider.sticker_whitelist_check/<match>?authority=<pkg-authority>&identifier=<pack-id>` — "bu paket zaten eklendi mi" sorusunu yanıtlayan, tek satırlı, tek sütunlu (`result`, `0`/`1`) bir cursor. Çağıran doğrulaması 7.2'yi yansıtır: çağıran paket, sorgulanan `authority`'ye sahip paketle eşleşmelidir. `getType()`'ın döndürdüğü MIME tipi: `vnd.android.cursor.item/vnd.com.whatsapp.provider.sticker_whitelist_check.is_whitelisted`.

### 7.6 Dahili çıkartma-komutu sağlayıcısı (found, `StickerCommandProvider`, `com.whatsapp.provider.sticker_command`, `exported="true"`)

Yukarıdaki üçüncü taraf sözleşmesinin bir parçası değil — bu, WhatsApp'ın kendi UI/asistan yüzeyleri tarafından sorgulanan, WhatsApp'ın kendi sağlayıcısıdır, URI son-yol-bölümü dispatch'iyle:

| Yol | Davranış |
|------|-----------|
| `installPack?authority=&identifier=` | bölüm 7.3'teki aynı `C175327dG` getirme/doğrulama yolu üzerinden bir paket kurar, aktivite UI'sını atlayarak |
| `removePack?authority=&identifier=` | önceden eklenmiş bir paketi kaldırır |
| `generate?prompt=` | AI çıkartma üretimi (bölüm 8); prompt uzunluğu, trim sonrası 3–200 karakter olmalıdır |
| `availability` | AI çıkartma üretimi için `{available, consent_required}` döndürür |
| `image/<token>` (`openFile` üzerinden) | üretilen bir çıkartma PNG/WebP'sini opak bir token ile geri akıtır, MIME `image/webp` |

---

## 8. AI tarafından üretilen çıkartmalar (found, `AiStickerCommands`, `StickerCommandProvider`)

`isAiSticker` (alan 20), bir `StickerMessage`'ı AI tarafından üretilmiş olarak işaretler; tip string'i `genai_sticker`'dır (bölüm 2.2). Üretimin kendisi, `generate` sağlayıcı yolu (7.6) üzerinden yerel-UI tarafından tetiklenir: herhangi bir üretim çağrısından önce uygunluk (`C174467bs.A00`) ve onay (`A02`) kapıları kontrol edilir; sonuçlar, daha sonra `image/<token>` üzerinden çözülen opak `token`'lar listesi olarak geri gelir. Gerçek üretim arka ucu (cihaz üzerinde mi yoksa sunucu tarafında mı) bu kod yolundan bilinmiyor — sadece istemci tarafı uygunluk/onay/token boru hattı çözüldü.

---

## 9. Çıkartma araması (found, `StickerSearchManager`, `EmojiGroupMapper`, bağlamsal-öneri paketi)

Tamamen yerel, bir sunucu sorgusu değil. `StickerSearchManager.A00`, serbest metin bir sorgu alır, bunu `EmojiGroupMapper` aracılığıyla bir emoji karakter kümesine çözer, bunları boşlukla ayrılmış bir string'e birleştirir ve bu string'i her `StickerMessage`/paket `Sticker`'ının **yerel olarak depolanmış** `emojis` alanına (bölüm 2.3) artı son kullanılan/öne çıkan adaylara karşı eşleştirir, sonuçları "tam emoji eşleşmesi" ile "diğer" kovalarına ayırır ve bir sözlük-token sonuç sınırına (bayrak **22573**) kırpar. Ayrı bir `includeAvatarResults` bayrağı, avatar çıkartmalarının katılıp katılmayacağını kontrol eder, kendi uygunluk kontrolünün arkasında korunur. Bu, proto'nun `emojis` string alanının istemci tarafı arama indeks anahtarı olduğunu — sadece görüntüleme amaçlı bir etiket değil — doğrular ve "olabilir… bilinmiyor" statüsünden found'a yükseltir.

---

## 10. Medya şifrelemesi (bağlantı, tekrarlanmıyor)

Her çıkartma taşıyan medya referansı (`stickerMessage`, `stickerPackMessage`, bunların küçük resimleri), [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md)'de belgelenen aynı medya hattından geçer: 32 baytlık rastgele medya anahtarı, HKDF-80 (`sticker` için `WhatsApp Image Keys`, `sticker-pack` için `WhatsApp Sticker Pack Keys`, paket küçük resmi için `WhatsApp Sticker Pack Thumbnail Keys`, `WhatsApp Image Thumbnail Keys`-tarzı işleme burada kullanılmıyor — çıkartma ve paket küçük resimlerinin kendi özel bilgi string'leri var), AES-CBC + 10 baytlık kesilmiş HMAC-SHA256, `fileSha256`/`fileEncSha256`, `media_conn` tarafından verilen host'lar ve `/mms/<type>/<hash>` yükleme URL şekli. Çıkartmaya özel hiçbir şey bunların hiçbirini değiştirmiyor; tam türetme, tekrar deneme ve hata-kodu tabloları için o raporun 2–9. bölümlerine bakın.

---

## 11. Özellik bayrakları (çağrı noktalarında okunduğu gibi id'ler; adlar çözülemedi)

| Bayrak | Yer | Kontrol ettiği |
|------|-------|----------|
| **1900** | `C161826tK` ctor | girdi başına ve toplam paket-ZIP çıkarma boyutu bütçesi (KB) |
| **13081** | `AddThirdPartyStickerPackActivity` | zaten beyaz listeye alınmış üçüncü taraf paket için yeniden getirme vs. önbellek |
| **13711** | `StickerCommandProvider`, `AddThirdPartyStickerPackActivity` | kurulum-yolu varyantını seçer (`C175327dG.A00` vs `A01`) |
| **17124** / **17327** | `StickerContentProviderFetcher` | üçüncü taraf paketten kabul edilen min / maks çıkartma sayısı |
| **22198** | `AddThirdPartyStickerPackActivity` | eşzamansız iletişim-kutusu-odaklı ekleme akışı vs. doğrudan önizleme-ekranı yönlendirmesi |
| **22573** | `StickerSearchManager` | yerel arama sonuç sınırı |

---

## 12. Baileys (`baron-baileys-v2`, kaynak okundu, hiçbir şey test edilmedi)

| Yön | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| `Message.StickerMessage` alanları | `audioMessage` (26, `oneof audio`) dahil aynı alan kümesi — proto kaynağı, decompile edilmiş 2.26.41.6 düzeniyle alan-alan eşleşiyor | aynı (bölüm 2.1) |
| `Message.StickerPackMessage` alanları | aynı alan kümesi (1–22) | aynı (bölüm 5.1) |
| Çıkartma gönderme | `prepareWAMessageMedia({ sticker })`, genel medya-hazırlama yolu (`MmsType` `sticker`, Image HKDF bilgisi) üzerinden `stickerMessage` oluşturur; `stickerAudio` seçeneği, hazırlanmış bir `audioMessage`'ı `m.stickerMessage.audioMessage` üzerine ekler | [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) bölüm 17'ye göre aynı medya hattı |
| Paket gönderme | `stickerPackMessage`/`stickerPack` girdisi, ek doğrulama olmadan `StickerPackMessage.fromObject` üzerinden geçirilir | istemci, kendi oluşturduğu bir paketi kabul etmeden önce ek olarak ZIP çıkarıcı ve DB kısıtlamaları (bölüm 5, 6) üzerinden doğrular |
| Çözümleme | `decode-wa-message.js`, `isAvatar`→`avatar_sticker`, `isAiSticker`/`isGenAI`→`genai_sticker` eşler; `messages-send.js`, giden tip string'ini türetirken `isLottie`→`1p_sticker`'ı `isAvatar`/düz `sticker`'dan önce eşler | aynı üç mesaj-tipi string'i Android analitik dispatch'inde bulundu (`avatar_sticker`, `genai_sticker`, artı `1p_sticker`/`user_created_sticker`); kesin Android öncelik sırası doğrulanmadı (bölüm 2.2) |
| Üçüncü taraf paket intent'leri/sağlayıcıları | uygulanmamış — Baileys'in Android `Intent`/`ContentProvider` yüzeyi yok | tam yüzey, bölüm 7 |
| `lottieStickerMessage` / `audioStickerMessage` sarmalayıcıları | sadece proto içinde çıplak bir `FutureProofMessage` alanı olarak mevcut; özel bir kodlayıcı/çözücü yolu bulunamadı | aynı çıplak zarf, alan-özel işleme de bulunamadı (bölüm 3) |

---

## 13. Hata durumları

| Semptom | Neden | Çözüm |
|---------|-------|-----|
| `ENABLE_STICKER_PACK`, "cannot find the provider for authority" `validation_error`'ı döndürür | üçüncü taraf uygulamanın `authority` string'i kurulu hiçbir sağlayıcıya çözülmüyor | çıkartma-paketi yayınlayan uygulama, o tam authority altında kendi sağlayıcısını bildirmeli ve dışa aktarmalıdır |
| `ENABLE_STICKER_PACK`, "does not own authority" döndürür | çağıran paket, çözülen sağlayıcının paketinden farklı | bir uygulama ancak kendi paketi içindeki authority'ler için kefil olabilir |
| Paket ekleme "sticker count should be between X and Y" ile sessizce başarısız olur | paketin `stickers` sorgusu `[flag 17124, flag 17327]` dışında bir satır sayısı döndürdü | üçüncü taraf `/stickers/<id>` cursor'ını sunucu tarafında yapılandırılmış sınırlar içinde tut |
| `SafeZipEntrySaver: File being unzipped is too big` / "Too many files to unzip" | paket ZIP'i girdi-başına/toplam bayt bütçesini veya 65-girdi sınırını aşıyor | paketi küçültün veya çıkartmaları paketlere bölün |
| `tray image name invalid` / ad uzunluğu hatası | üçüncü taraf `sticker_pack_icon`, geçersiz karakterler içeriyor veya 128 karakteri aşıyor | tepsi dosya adını temizleyin ve kısaltın |
| `StickerPackZipEntrySaver/file in zip is not valid` | çıkarılan bir girdinin koklanmış içerik tipi, iddia edilen uzantısı/MIME'ı ile eşleşmiyor | baytları `png`/`webp`/`was` ile gerçekten eşleşen girdiler gönderin |
| `the sticker is not a 512px WebP` (`SEND_STICKER`) | tekil-çıkartma intent'inin görseli tam olarak 512×512 değil | intent'i göndermeden önce yeniden boyutlandırın |

---

## 14. Temel ayrımlar

| Karıştırılmamalı | Gerçek |
|----------------|------|
| `StickerMessage.audioMessage` (alan 26) vs. `Message.audioStickerMessage` (alan 134) | öncesi, bir çıkartma gönderimi içinde gömülü, doğrulanmış bir `AudioMessage`'dır; sonrası, bu derlemeye yeni gelen, hâlâ opak, ayrı bir üst seviye sarmalayıcı alandır |
| `isLottie` (çıkartma başı bayrak) vs. `Message.lottieStickerMessage` (alan 74 sarmalayıcı) | bayrak, somut, found bir dosya formatına (`animation/animation.json` içeren `.was` ZIP) bağlıdır; sarmalayıcı alanın iç içe yükü hâlâ çözülmedi — aynı mekanizma oldukları gösterilmedi |
| `stickerSyncRmrMessage` (hat mesajı, yok) vs. `RecentStickerDBStorage` (`filehash`-anahtarlı yerel tablo) | öncesi bu derlemede hat üzerinde artık mevcut değil; sonrası, aynı zamanda dosya hash'ine göre anahtarlanan, ilgisiz bir yerel defter tutmadır |
| Üçüncü taraf paket sözleşmesi (bölüm 7.2–7.5, harici uygulamanın sağlayıcısı) vs. `StickerCommandProvider` (bölüm 7.6, WhatsApp'ın kendi sağlayıcısı) | her ikisi de "authority+identifier ile bir paket kurabilir", ama öncesi WhatsApp'ın *başka bir uygulamanın* sağlayıcısını okuması, sonrası WhatsApp'ın kendi aktivite UI'sı etrafındaki dahili kısayoludur |
| AI çıkartma üretimi (`isAiSticker`, yerel GenAI akışı) vs. üçüncü taraf AI/çıkartma uygulamaları | öncesi, `StickerCommandProvider`'ın arkasındaki WhatsApp'ın kendi uygulama içi özelliğidir; üçüncü taraf content-provider sözleşmesiyle hiçbir ilgisi yoktur |

---

## 15. Akış: üçüncü taraf bir çıkartma paketi ekleme

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

## 16. Bilinmeyenler

| Öğe | Durum |
|------|--------|
| `lottieStickerMessage` (74) ve `audioStickerMessage` (134)'ün iç içe yükü | alan mevcut, genel `FutureProofMessage` sarmalayıcı, içeriği çözülemedi |
| `sticker` vs. `1p_sticker` vs. `user_created_sticker` tip string'leri için kesin Android önceliği | sadece analitik bytecode eşlemesi bulundu, seçici fonksiyon bulunamadı |
| `StickerMessage`/`Sticker` üzerindeki `premium` alanı (24) | tüketici bulunamadı |
| Sözlük-token bayrakları 1900, 17124, 17327, 22573'ün ardındaki sayısal değerler | token id'leri bulundu, canlı değerler statik olarak çözülemedi |
| `whatsapp://stickerpack` derin bağlantısının hedef aktivitesi | host, manifest'in genel derin-bağlantı intent-filter'ında bildirilmiş; hangi dahili ekranın bunu tükettiği izole edilemedi |
| AI çıkartma üretim arka ucu (cihaz üzerinde vs. sunucu) | sadece istemci uygunluk/onay/token boru hattı çözüldü |
| Sunucunun kendi paket boyutu/sayısı sınırlarını istemcinin ötesinde uygulayıp uygulamadığı | sunucu tarafı, bilinmiyor |
| `stickerSyncRmrMessage`'ın kaderi (yeniden adlandırıldı, taşındı veya düşürüldü) | 2.26.36.1'den 2.26.41.6'ya kadar hat proto'sunda yok olduğu doğrulandı; kaldırma doğrulanmadı |
| Trafik | hiçbir şey yakalanmadı; dinamik test yok |
