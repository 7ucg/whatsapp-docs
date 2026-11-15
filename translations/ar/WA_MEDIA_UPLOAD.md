<!-- src-sha1: a12736ca9c475f1c7c0195dbae0d18d5725a4440 -->
# WhatsApp رفع الوسائط — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** نقل الوسائط على أندرويد: IQ من نوع `media_conn` (المضيفون، المصادقة، ttl، الدلاء، المضيفون البديلون)، بناء عناوين URL للرفع والتنزيل ومعطيات HTTP، جدول نوع الوسائط بسلاسل معلومات HKDF، توليد واستخلاص مفتاح الوسائط، تشفير AES-CBC + HMAC، `fileSha256` / `fileEncSha256`، `mediaKeyTimestamp`، المسار المباشر، الصور المصغَّرة، سلاسل تدفق جانبية (sidecar) للفيديو/الصوت/الصور التقدمية، الرفع القابل للاستئناف، اختيار المسار، إعادة المحاولة والتأخير التصاعدي، رموز خطأ الرفع والتنزيل، إيصال إعادة محاولة الوسائط وإشعار `mediaretry`، وسائط المرة الواحدة والحالة، وسائط النشرة (القناة)، المسار السريع (express)، التحصين الأصلي من جانب العميل لمحلِّلات الوسائط، مقارنة Baileys

---

## 1. ما هو (تقنياً)

لا تنتقل الوسائط أبداً داخل تيار chatd (انظر [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). تحمل الرسالة فقط مرجع protobuf (مفتاح، تجزئات، `directPath`)؛ تنتقل البايتات عبر اتصالات HTTPS منفصلة إلى مضيفي الوسائط. يوفّر chatd شيئاً واحداً: IQ من نوع `media_conn` التي تسلّم أسماء المضيفين ورمز مصادقة رفع قصير الأمد. كل العبارات تأتي من تحليل ساكن للـAPK المفكَّك والمكتبات الأصلية المفكوكة التعبئة؛ لم يُلتقط شيء على السلك. المستويات: **found** = مقروء في الكود أو السلاسل، **inferred** = مُستنتَج، **unknown** = غير محسوم.

| الطبقة | الاسم في 2.26.41.6 | الدور |
|-------|----------------|------|
| مُحدِّد المسار | `RouteSelector` (`C10950Wx`) | يحمل نتيجة `media_conn` الحالية، مؤقت التحديث، الكبت، مُصنِّع المسار |
| مُحلِّل `media_conn` | `C43951qe` (معالج نتيجة IQ)، `C41561mf` (RoutingResponse)، `C41441mT` (RouteHost) | يُحلِّل `<media_conn>` / `<host>` |
| مُزوِّد المسار | `Mms4RouteSupplier` (`C46433KQw`)، `C46435KQy` / `C46436KQz` (مُزوِّدون ساكنون) | يختار مضيفاً لكل محاولة، يُبدِّل رمز المصادقة |
| مُشغِّل إعادة المحاولة | `TransferRetries` (`C44566Jd2`) | حلقة محاولات حول نقل واحد |
| جدول نوع الوسائط | `MmsType` (`C15530gU`) | لكل نوع: سلسلة المسار، بايتات معلومات HKDF، معرّف عددي |
| مُزوِّد المفتاح | `MmsImageCipherKeyProvider` (`C59530Qnc`)، `MediaCryptoProvider` (`C58155Q5r`) | HKDF بـ80 بايت، مفتاح نطاق غير E2EE |
| تيارات التشفير | `M2I` (تشفير خارج)، `M23` (تشفير داخل)، `P9N` / `P1X` / `P1Y` (MACs تدفق جانبي)، `C51101MlN` (فك تشفير مُقيَّد بنطاق) | AES-CBC + HMAC |
| مُشغِّل الرفع | `MediaUploadUtils` (`QIh`)، `QBE`، `Q52` (إعادة استخدام المفتاح)، `C57333Po0` (توليد المفتاح + التجزئات) | التجزئات، التدفقات الجانبية، تنسيق الرفع |
| عنوان URL للرفع | `C43489Iy4` | `/surface/type/hash?...` |
| عنوان URL للتنزيل | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`، `K19`) للرفع؛ `PlainDownloadTransfer` (`CallableC60106QxW`)، `C17660kC`، `C43481Ixw` (Tigon) للتنزيل | النقل |
| فحص الاستئناف | `HttpResumeCheck` (`C59524QnW`) | يسأل الخادم عن عدد البايتات التي يملكها |
| إيصال إعادة المحاولة | `SendMediaErrorReceiptJob`، حالتا الكاتب 77 و327 في `HandlerThreadC21920sG` | يطلب إعادة رفع من المُرسِل |
| إشعار إعادة المحاولة | `MediaRetryNotificationHandler` (`C1S0`، رمز إشعار 97) | يستهلك الإجابة |
| أصلي | `libwhatsapp.so` (صناديق Rust للوسائط، حاويات RLBox)، `libstatic-webp.so`، `libwa_sandboxed_gifimage.so`، `libdav1d.so` | المحلِّلات ومفكِّكات الترميز |

نقاط تحدِّد بقية التقرير:

- يستخلص أندرويد **80** بايت من مفتاح الوسائط (IV 16، مفتاح تشفير 32، مفتاح MAC 32)، لا 112 (القسم 4).
- مسار HTTP هو `/{surface}/{type}/{urlSafeFileEncSha256}` حيث `type` هو سلسلة `MmsType` الخاصة بالوسائط (`image`، `ptt`، `md-msg-hist`، ...)، لا فئة عريضة (القسم 8.1).
- `token` الخاص بالرفع على أندرويد ليس تجزئة الملف؛ إنه SHA-256 على سرّ خاص بالتثبيت مع تجزئة الملف (القسم 8.2).
- وسائط النشرة (القناة) تتشارك نفس الكود لكنها تستخدم سطح `newsletter` ورمزاً عشوائياً؛ وهي غير مشفَّرة (found لمسار الأعمال الفنية (artwork)، inferred للباقي، القسم 13).
- تُصفَّى مضيفو التنزيل بدلاء مُستخلَصة من تجزئة الملف (القسم 9.2).

---

## 2. IQ من نوع `media_conn`

### 2.1 الطلب (found، `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

مهلة 32000 ms. طلب واحد فقط قيد التنفيذ (`inFlightMediaRoutingRequestTime`)؛ استدعاء ثانٍ يسجِّل `not sending request` ويُعاد. كبت عام (`ChatdMediaThrottleManager`) يمكن أن يُكبِت الاستدعاء (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 الاستجابة (found، `C43951qe.CFS`)

| العقدة / السمة | النوع | الاستخدام |
|------------------|------|-----|
| `media_conn@auth` | سلسلة، مطلوبة | رمز مصادقة الرفع (معطى استعلام `auth`) |
| `@ttl` | ثوانٍ | مدة صلاحية الاتصال؛ الانتهاء = وقت الإرسال + ttl × 1000 |
| `@auth_ttl` | ثوانٍ | مدة صلاحية رمز المصادقة؛ الانتهاء = وقت الإرسال + auth_ttl × 1000 |
| `@max_buckets` | long، الافتراضي 0 | المقياس (modulus) لدلو التنزيل (القسم 9.2) |
| `@is_new` | int، الافتراضي 1 | 1 = استبدال قائمة المضيفين؛ وإلا يُحتفَظ بالمضيفين السابقين ويؤخذ فقط الرمز وttl (`previous hosts retained`) |
| `@id` | سلسلة | تُخزَّن كـ`last_id`، تُرسَل في الطلب التالي |
| `@max_auto_download_retry` | int، الافتراضي 3 | ميزانية إعادة محاولة التنزيلات الآلية |
| `@max_manual_retry` | int، الافتراضي 3 | ميزانية إعادة محاولة التنزيلات اليدوية |
| `@ip_token`، `@set_ip_token` | سلسلة، "0"/"1" | تُحلَّل وتُخزَّن؛ `ip_token` يُستخدم فقط عندما يكون العلم **12149** مُفعَّلاً و`set_ip_token` صحيحاً (موقع الاستهلاك: غير معروف) |
| `host` (مُكرَّرة) | عقدة | إدخال مسار واحد |

سمات `host` (found): `hostname` (مطلوبة)، `ip4`، `ip6`، `class`، `fallback_hostname`، `fallback_ip4`، `fallback_ip6`، `fallback_class`، `type` (`primary` أو `fallback`؛ أي شيء آخر يصبح `primary`)، `force_ip` (`"true"`). العناصر الفرعية: `<upload>`، `<download>`، `<download_buckets>`؛ أسماء العناصر الفرعية هي إدخالات القدرة. يحتفظ `upload` و`download` فقط بالوسوم التي تظهر في مجموعة ثابتة من 34 سلسلة نوع وسائط (`audio`، `image`، `chat-wallpaper-image`، `video`، `ptv`، `kyc-id`، `sticker`، `document`، `ptt`، `gif`، `md-app-state`، `md-msg-hist`، `ppic`، عائلة `newsletter-*`، وعائلة `thumbnail-*`)؛ يُحتفَظ بـ`download_buckets` دون تصفية.

لا يكون مضيف المسار قابلاً للاستخدام إلا إذا انتهى اسم مضيفه بـ`.whatsapp.net` (`Mms4RouteSupplier.A06`، يُطبَّق أيضاً على `fallback_hostname`).

### 2.3 التخزين المؤقت والتحديث (found)

| القاعدة | القيمة |
|------|-------|
| الحفظ | بالعلم **149** تُخزَّن النتيجة كـJSON (`auth_token`، `conn_ttl`، `auth_ttl`، `max_buckets`، `hosts`، `last_id`، `is_new`، `max_autodownload_retry`، `max_manual_retry`، `ip_token`، `set_ip_token`، `send_time_abs_ms`) تحت `route_selector_prefs` / `media_conn`؛ تُحمَّل مرة واحدة، تُستخدم فقط إذا لم تنته صلاحية المصادقة بعد |
| فحص التحديث | قبل أي نقل: إذا كانت صلاحية الاتصال أو المصادقة تنتهي في غضون 120000 ms، يُرسَل IQ جديدة وتُنتظَر الاستجابة حتى 20000 ms (`requestroutesandwaitforauth`) |
| المؤقت | `انتهاء صلاحية المصادقة - 60000 ms` بعد كل نتيجة؛ المقدمة (`BgG`) تُعيد ضبطه |
| فشل المصادقة | HTTP 401 أو 403 على نقل يُحفِّز تحديثاً (`onmediatransfererrororresponsecode`)، بحد أقصى تبديلي رمز لكل نقل (`JW1.A00 < 2`)، ثم تُعاد المحاولة بـ`auth` الجديد |
| المصادقة قبل المحاولة | `refreshAuthBeforeAttempt` يُبدِّل برمز أحدث عندما يكون المخزَّن مؤقتاً على بُعد 120000 ms من الانتهاء (رمز علم `PTU.A0D`) |

### 2.4 خطأ IQ (found، `C43951qe.Brt`)

`<error code backoff>` داخل نتيجة IQ:

| الرمز | السلوك |
|------|-----------|
| 503 | إعادة ضبط كبت الوسائط؛ جدولة التحديث التالي بعد تأخير فيبوناتشي مع اضطراب عشوائي (`3/4 * t + rand(t/2)`) |
| 507 مع backoff > 0 | كبت طلبات الوسائط حتى `now + min(backoff, 10800) s` |
| غيره / 0 | يُتجاهَل |

---

## 3. أنواع الوسائط وسلاسل معلومات HKDF (found، التهيئة الساكنة لـ`MmsType` `C15530gU`)

يحمل كل `MmsType` سلسلة مسار (`A02`)، تسمية نوع ملف قصيرة (`A01`، مثل `IMG`)، بايتات `info` الخاصة بـHKDF (`A03`) ومعرّف عددي (`A00`). تُستخدم بايتات `info` خاماً كمعلومات HKDF (دون أي بادئة إضافية).

| معلومات HKDF | سلاسل مسار `MmsType` |
|-----------|------------------------|
| `WhatsApp Image Keys` | `image`، `sticker`، `kyc-id`، `biz-cover-photo`، `biz-flows`، `wamo-image`، `newsletter-image`، `newsletter-image-status`، `newsletter-sticker`، `newsletter-music-artwork` |
| `WhatsApp Video Keys` | `video`، `ptv`، `gif`، `wamo-video`، `newsletter-video`، `newsletter-video-status`، `newsletter-ptv`، `newsletter-gif`، `newsletter-gif-status` |
| `WhatsApp Audio Keys` | `audio`، `ptt`، `newsletter-audio`، `newsletter-audio-status`، `newsletter-ptt` |
| `WhatsApp Document Keys` | `document`، `biz-flows`، `maiba-file`، `db`، `newsletter-document` |
| `WhatsApp Image Thumbnail Keys` | `thumbnail-image`، `newsletter-thumbnail-image`، `newsletter-thumbnail-status` |
| `WhatsApp Video Thumbnail Keys` | `thumbnail-video`، `thumbnail-gif`، `newsletter-thumbnail-video` |
| `WhatsApp Document Thumbnail Keys` | `thumbnail-document` |
| `WhatsApp Link Thumbnail Keys` | `thumbnail-link`، `newsletter-thumbnail-link` |
| `WhatsApp Chat Wallpaper Keys` | `chat-wallpaper-image` |
| `WhatsApp App State Keys` | `md-app-state` |
| `WhatsApp History Keys` | `md-msg-hist` |
| `Group History` | `group-history` |
| `WhatsApp Sticker Pack Keys` | `sticker-pack`، `newsletter-sticker-pack` |
| `WhatsApp Sticker Pack Thumbnail Keys` | `thumbnail-sticker-pack`، `newsletter-thumbnail-sticker-pack` |
| `WhatsApp Payment Background Keys` | `payment-bg-image` |
| `WhatsApp Music Artwork Keys` | `music-artwork` |
| `waffle_hkdf_info` | `waffle-image`، `waffle-video`، `waffle-gif` |
| `PAYMENT_DOC_UPLOAD` | `payment-br-document` |
| `ads-image` / `ads-video` | `ads-image` / `ads-video` |

ملاحظات (found): يتشارك `ptt` و`audio` معلومات Audio لكنهما سلسلتا مسار مختلفتان؛ `sticker` يستخدم معلومات Image؛ `gif` و`ptv` يستخدمان معلومات Video؛ توجد عدة صفوف `image` بمعرّفات عددية مختلفة (1، 23، 25، 37، 42، 44، 57؛ `sticker` هو 20) لمواقع استدعاء مختلفة (معنى المعرّف غير معروف)؛ `group-history` هو الإدخال الوحيد الذي لا تكون معلوماته على شكل `WhatsApp <X> Keys`. صور الملف الشخصي (`ppic`) تظهر فقط في مجموعة قدرة المسار وفي استدعاءات مُولِّد التنزيل، لا كـ`MmsType`.

---

## 4. مفتاح الوسائط والاستخلاص

### 4.1 توليد المفتاح (found)

| العنصر | القيمة |
|------|-------|
| مفتاح الوسائط | 32 بايت عشوائية من `SecureRandom` (`C57333Po0`، `QIh.A0B` هو `new SecureRandom()`) |
| إعادة الاستخدام | `MediaKeyGen/reuse key from message contents` عندما يكون المفتاح أصغر سناً من `172800000 ms + SecureRandom.nextInt(86400000)` (2 إلى 3 أيام، باضطراب عشوائي)، مقارنة بالطابع الزمني المخزَّن للمفتاح؛ المفاتيح الأقدم تُستبعَد (`key expired`) وتُعاد توليدها |
| النطاق | `D5C`: `E2EE` (0)، `NON_E2EE` (1)، `UNKNOWN` (-1) |

### 4.2 HKDF (found، `AbstractC38961i0.A00` المُستدعاة من `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

يرفض `N6U.A01` أي طول آخر (`Invalid length of derived secret`). طول نص التشفير: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (كُتَل PKCS#5 مُحشوّة إضافة إلى 10 بايتات MAC).

### 4.3 مفتاح الوسائط غير E2EE (found، `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

يحمل `ContextInfo.mediaDomainInfo` (الحقل **74**، الرسالة `DQT`) `mediaKeyDomain` (**1**: 0 UNKNOWN، 1 E2EE، 2 NON_E2EE) و`e2eeMediaKey` (**2**). بالعلم **24661** يفحص المستقبل أن المفتاح في الرسالة يطابق النطاق (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`)؛ عند عدم التطابق يعود إلى المفتاح كما ورد. أي المنتجات تستخدم نطاق NON_E2EE: غير معروف.

---

## 5. التشفير وMAC والتجزئات

### 5.1 التشفير (found، `M2I`، `M23`، `N6U`)

| الخطوة | التفصيل |
|------|--------|
| التشفير | `AES/CBC/PKCS5Padding`، المفتاح = cipherKey، IV = iv |
| MAC | `HmacSHA256(macKey)`، يُحدَّث بـIV أولاً، ثم كل بايت من نص التشفير؛ تُلحَق أول **10** بايتات من الملخَّص بنص التشفير |
| `fileSha256` | SHA-256 على النص الصِّرف (تيار ملخَّص `P9M` على الملف) |
| `fileEncSha256` | SHA-256 على نص التشفير + 10 بايتات MAC |
| الناتج | `ciphertext || mac10`؛ `Content-Length` = `N6U.A00(plaintextLength)` |

جانب فك التشفير (`P9N`، `M23`): يُحقَّق MAC على IV + نص التشفير، ثم يُقارَن بالبايتات العشرة الأخيرة. فك التشفير المُقيَّد بنطاق (`C51101MlN`): عندما لا تكون بداية النطاق 0 تُستخدم أول 16 بايت مقروءة كـIV (كتلة نص التشفير السابقة)؛ الأجزاء الداخلية تستخدم `AES/CBC/NoPadding`، الجزء الأخير يستخدم PKCS#5 (مستنتج من اختيار التشفير).

### 5.2 الطوابع الزمنية والمسارات

| الحقل | القيمة |
|-------|-------|
| `mediaKeyTimestamp` | الساعة المحلية بالمللي ثانية محفوظة في كائن المفتاح، تُكتب في الـprotobuf كثوانٍ (`C20H.A06` = `/1000`) |
| `directPath` | سلسلة مسار يُعيدها الخادم، تُخزَّن في الرسالة وفي عمود قاعدة البيانات `direct_path`؛ قد تحمل معطيات استعلام (مثلاً تُقرأ منه `_nc_hot`) |
| `url` | حقل عنوان URL كامل قديم؛ لا يزال موجوداً في أصناف proto وفي استجابة الرفع، لكن مُولِّد التنزيل يُبنى من `directPath` أو من التجزئة (القسم 9.1) |

### 5.3 فحوصات التجزئة التفاؤلية

تُسجَّل `MediaUpload/optimistic-hash-fail` و`optimistic-plaintext-hash-fail` (نتيجة رفع 12) عندما تختلف التجزئة التي يُعيدها الخادم عن تلك المحسوبة محلياً. الرفع التفاؤلي (سلسلة سطح `optimistic`) يرفع قبل الالتزام بالإرسال؛ بروتوكوله بما يتجاوز اسم السطح: غير معروف.

---

## 6. حقول رسالة الوسائط

أرقام الحقول مقروءة من أصناف protobuf المُولَّدة. أسماء الأصناف مُطابَقة بتخطيط الحقل (مستنتج)؛ الأرقام found.

| الرسالة (الصنف) | أرقام الحقول (الاسم = الرقم) |
|-----------------|-------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**، mimetype **2**، caption **3**، fileSha256 **4**، fileLength **5**، height **6**، width **7**، mediaKey **8**، fileEncSha256 **9**، directPath **11**، mediaKeyTimestamp **12**، jpegThumbnail **16**، contextInfo **17**، firstScanSidecar **18**، firstScanLength **19**، experimentGroupId **20**، scansSidecar **21**، scanLengths **22**، midQualityFileSha256 **23**، midQualityFileEncSha256 **24**، viewOnce **25**، thumbnailDirectPath **26**، thumbnailSha256 **27**، thumbnailEncSha256 **28**، staticUrl **29**، imageSourceType **31**، accessibilityLabel **32**، qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**، mimetype **2**، fileSha256 **3**، fileLength **4**، seconds **5**، mediaKey **6**، caption **7**، gifPlayback **8**، height **9**، width **10**، fileEncSha256 **11**، directPath **13**، mediaKeyTimestamp **14**، jpegThumbnail **16**، contextInfo **17**، streamingSidecar **18**، gifAttribution **19**، viewOnce **20**، thumbnailDirectPath **21**، thumbnailSha256 **22**، thumbnailEncSha256 **23**، staticUrl **24**، processedVideos **27**، metadataUrl **30**، videoSourceType **31**، dashManifestUrl **33**، smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**، mimetype **2**، fileSha256 **3**، fileLength **4**، seconds **5**، ptt **6**، mediaKey **7**، fileEncSha256 **8**، directPath **9**، mediaKeyTimestamp **10**، contextInfo **17**، streamingSidecar **18**، waveform **19**، backgroundArgb **20**، viewOnce **21**، accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**، mimetype **2**، title **3**، fileSha256 **4**، fileLength **5**، pageCount **6**، mediaKey **7**، fileName **8**، fileEncSha256 **9**، directPath **10**، mediaKeyTimestamp **11**، thumbnailDirectPath **13**، thumbnailSha256 **14**، thumbnailEncSha256 **15**، jpegThumbnail **16**، contextInfo **17**، thumbnailHeight **18**، thumbnailWidth **19**، caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**، fileSha256 **2**، fileEncSha256 **3**، mediaKey **4**، mimetype **5**، height **6**، width **7**، directPath **8**، fileLength **9**، mediaKeyTimestamp **10**، firstFrameLength **11**، firstFrameSidecar **12**، isAnimated **13**، pngThumbnail **16**، contextInfo **17**، stickerSentTs **18**، isAvatar **19**، isAiSticker **20**، isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**، fileLength **2**، mediaKey **3**، fileEncSha256 **4**، directPath **5**، syncType **6**، chunkOrder **7**، encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**، directPath **2**، handle **3**، fileSizeBytes **4**، fileSha256 **5**، fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**، fileEncSha256 **2**، fileLength **3** |
| حزمة History (`DT6`) | mimetype **1**، fileSha256 **2**، mediaKey **3**، fileEncSha256 **4**، directPath **5**، mediaKeyTimestamp **6**، contextInfo **7**، messageHistoryMetadata **8** |

أرقام حاوية `Message` (`C30628DTw`) (found): imageMessage **3**، documentMessage **7**، audioMessage **8**، videoMessage **9**، stickerMessage **26**، viewOnceMessage **37**، viewOnceMessageV2 **55**، viewOnceMessageV2Extension **59**، ptvMessage **66**، stickerPackMessage **86**، musicMessage **129**؛ `mediaNotifyMessage` هو الحقل **21** من الحاوية `BD3`.

### 6.1 الصور المصغَّرة

| النوع | الآلية (found إلا إذا أُشير إلى غيره) |
|------|---------------------------------|
| مضمَّنة | بايتات `jpegThumbnail` (**16**) في الرسالة (صورة، فيديو، وثيقة)؛ `pngThumbnail` (**16**) في الملصقات |
| مرفوعة | `thumbnailDirectPath`، `thumbnailSha256`، `thumbnailEncSha256` (صورة **26-28**، فيديو **21-23**، وثيقة **13-15**)؛ `MmsType` من نوع `thumbnail-*` بمعلومات HKDF الخاصة بالصور المصغَّرة من القسم 3 |
| المفتاح | لا يحمل البروتو حقل مفتاح مصغَّر منفصل، فتُشفَّر الصورة المصغَّرة بمفتاح وسائط رسالتها (مستنتج) |
| من صنع الخادم | معطى استعلام الرفع `server_thumb_gen=1`؛ قد تُعيد استجابة الرفع `thumbnail_info` = نص JSON متداخل `{thumbnail_direct_path, thumbnail_sha256}` |
| قاعدة البيانات | جدول `mms_thumbnail_metadata` (directPath، mediaKey، mediaKeyTimestampMs، encThumbHash، thumbHash، width، height) |

---

## 7. البث والتدفقات الجانبية (found)

التدفق الجانبي (sidecar) قائمة من MACs بطول 10 بايت، واحدة لكل جزء من نص التشفير، تسمح لمُشغِّل بالتحقق من نطاق دون قراءة الملف كاملاً.

| العنصر | التفصيل |
|------|--------|
| الخوارزمية | `P9N.read`: لكل جزء تُهيَّأ `HmacSHA256(macKey)` بـ**آخر 16 بايت من نص التشفير السابق** (IV للجزء الأول)، تُغذَّى بالجزء، وتُخزَّن أول 10 بايتات من الملخَّص |
| التسلسل | `C57228PmG.A00` يُدمِج كل MACs بطول 10 بايت في مصفوفة بايتات واحدة |
| الفيديو/الصوت | `VideoMessage.streamingSidecar` (**18**)، `AudioMessage.streamingSidecar` (**18**)؛ حجم الجزء **65536** (`QBE`، `QIh.A00(..., 65536)`) |
| الصورة التقدمية | `firstScanSidecar` (**18**) مع `firstScanLength` (**19**): جزء واحد بحجم `ceil(len/16)*16` بايت؛ `scansSidecar` (**21**) مع `scanLengths` (**22**): أحجام أجزاء متغيِّرة (`P1Y`) |
| الملصق | `firstFrameSidecar` (**12**) مع `firstFrameLength` (**11**) |
| الإعدادات | خاصية الخادم `streaming_upload_chunk_size` رمز قاموس؛ أثرها: غير معروف |
| غائب | رمز حالة تنزيل 30 `failed_no_sidecar` |
| البث من الخادم | معطى استعلام الرفع `stream=1` و`streaming=riff` معاً (القسم 8.1)؛ DASH: `dashManifestUrl` (**33**)، `metadataUrl` (**30**) في الاستجابة |

---

## 8. الرفع

### 8.1 عنوان URL (found، `C43489Iy4`، `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| الجزء | القيمة |
|------|------|
| `surface` | `mms` (عادي)، `newsletter` (القنوات)، `optimistic` (رفع قبل الإرسال)؛ `AbstractC58025Pzy` |
| `type` | سلسلة مسار `MmsType` (القسم 3)، مثل `image`، `ptt`، `md-msg-hist` |
| `urlSafeFileEncSha256` | base64 قياسي لـ`fileEncSha256` مع تحويل `+` إلى `-` و`/` إلى `_`؛ يُحتفَظ بحشو `=` (`StringUtils.A0B`) |
| `direct_ip` | 1 عندما تكون السلطة (authority) IP (`ip4`، أو `[ip6]` بين أقواس)، وإلا 0 |
| `auth` | رمز مصادقة `media_conn`؛ يُضاف كمعطى استعلام بواسطة `K19.A03` |
| `stream=1`، `streaming=riff` | يُضبطان كلاهما عندما يكون الطلب رفعاً مُبثّاً (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | فقط لـ`newsletter-image` / `-status` (العلم **11191**) و`newsletter-video` / `-status` (العلم **11192**) |
| `server_transcode=1` | `newsletter-video` مع معرّف طلب 10 والعلم **9096** |
| `_nc_rmr=1` | رفعات غير النشرة (علم الطلب `A0N`) |
| `_nc_cbep=1` | عندما يسمح الطلب بذلك والعلم **17404** مُفعَّل (المعنى غير معروف) |
| `type`، `media_id`، `media_id_upload` | `media_id` = أكثر 63 بتاً دلالة من UUID الرفع؛ `media_id_upload` = أقل 63 بتاً دلالة، فقط عندما يحمل الطلب إدخالات إضافية؛ `type` سلسلة من المُستدعي (المعنى: غير معروف) |

معنى أسماء الاستعلام `_nc_cbep` و`_nc_rmr` غير معروف (أسماء فقط).

### 8.2 الرمز (found، `C43489Iy4.A00`)

| الحالة | الرمز |
|------|------|
| النشرة | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`، جديد لكل طلب، غير مرتبط بالملف |
| غيرها | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`؛ `installSecret` 32 بايت من `SecureRandom`، تُنشأ مرة واحدة وتُخزَّن في التفضيلات كـ`upload_token_random_bytes` (base64 دون تغليف، دون حشو) |

إذا تعذَّر فك ترميز `fileEncSha256` يكون الرمز `SHA-256(installSecret)` وحده. الغرض من البناء: مستنتج أنه فحص من جهة الخادم يتحقق من أن الرافع يعرف التجزئة دون كشفها في المسار.

### 8.3 طلب HTTP (found، `HttpsFormPost` `C43478Ixt`)

| العنصر | القيمة |
|------|------|
| المكتبة | `HttpsURLConnection` بـ`SSLSocketFactory` مخصَّص؛ علامة `http_stack = HttpUrlConnection` |
| الطريقة | POST (`setDoOutput(true)` على `HttpURLConnection`؛ لا استدعاء طريقة صريح) |
| المهلات | الاتصال 15000 ms، القراءة 60000 ms |
| الرؤوس | `Host: <route hostname>` (قد تكون السلطة IP)، `User-Agent`، `Accept-Encoding: identity`، `X-FB-Request-Analytics-Tags`، `Companion_User_Secret` اختياري (معطى باني غير فارغ؛ دلالات الرفيق مستنتجة) |
| الجسم (المسار موجود) | تيار نص تشفير خام، ملف واحد فقط (`MMS4 upload only supports a single file`)؛ نمط بث بطول ثابت عند معرفة الطول، وإلا مُجزَّأ (`setChunkedStreamingMode(0)`)؛ مِخزَن 16384 بايت |
| الجسم (لا مسار) | `multipart/form-data` قديم بأجزاء `Content-Disposition: form-data` |
| الإلغاء | عند مقاطعة الخيط أو علم الإلغاء يُحشى التيار (`UploadRequest/Post streaming padding bytes=`) ليُكتمَل الطول المُعلَن (الغرض مستنتج) |
| الاستجابة | قراءة حتى 1 ميبيبايت؛ HTTP >= 400 يُعيد الرمز، يذهب الجسم إلى `onError` |

### 8.4 الاستجابة (found، `MediaUploadTransfer` `C59523QnV`)

مفاتيح JSON المقروءة: `url`، `direct_path`، `handle`، `enc_handle`، `mcs_request_id` (يُقبَل فقط إذا طابق `[A-Za-z0-9-]{1,64}`)، `meta_hmac`، `fbid`، `ts`، `thumbnail_info` (سلسلة JSON متداخلة بـ`thumbnail_direct_path`، `thumbnail_sha256`)، `metadata_url`، `dash_manifest_url`. استجابة بلا `direct_path` لا تُعامَل كخطأ بواسطة هذا المُحلِّل؛ تفشل المراحل اللاحقة بـ`FAILED_NO_DIRECT_PATH` (29).

### 8.5 الرفع القابل للاستئناف (found)

| الخطوة | التفصيل |
|------|--------|
| الفحص | عنوان URL الرفع نفسه إضافة إلى `resume=1` (`HttpResumeCheck`)؛ إجابة JSON `{"resume": "complete"}` بـ`url`، `direct_path` (مرفوع أصلاً) أو `{"resume": <offset>}` |
| الاستمرار | POST بـ`Content-Range: bytes <offset>-*/*`، يُتجاوَز التيار إلى `<offset>` أولاً |
| الحلول البديلة | `ResumeCheck/attempting fallback MMS upload form post`، أيضاً بعد خطأ WATLS (TLS) |
| خطأ تحليل | حالة `PBY.A03`، يُعاد تشغيل الرفع |

### 8.6 مُزوِّد المسار وإعادة المحاولة (found، `Mms4RouteSupplier`، `TransferRetries`)

| القاعدة | التفصيل |
|------|--------|
| حلقة المحاولات | `TransferRetries/run attempt = N; route = ...`؛ نقل واحد لكل مسار؛ `no routes` تُنهي الحلقة |
| اختيار المضيف | مضيف `type=primary` تحتوي مجموعة قدرته نوع الوسائط؛ أول محاولتين تستخدمانه؛ المحاولات اللاحقة تستخدم إدخال `type=fallback` وحقوله `fallback_*` (الترتيب مستنتج من مسار تحكم مُشوَّش) |
| المحاولات | الافتراضي 4 (`4 - extra`)؛ بالعلمين **12545** و**12446** يمكن تجاوز الحد بعد المحاولة 3؛ `max_auto_download_retry` / `max_manual_retry` (الافتراضي 3 لكل منهما) تُغذِّي العدد المعتمد على الوضع (التعيين مستنتج) |
| التأخير | ثابت 1000 ms (`RouteSelector.A01`)؛ بالعلم **257** ومحاولات إضافية، تصاعدي: أساس 1000 ms، `2^n`، اضطراب عشوائي، بحد أقصى 3000 ms |
| خطأ مصادقة 401 / 403 | لا يُحسَب كفشل: انتظار رمز أحدث (ميزانية `A0J`، 20000 ms افتراضياً)، تبديل، إعادة محاولة |
| رمز HTTP قابل لإعادة المحاولة | `QKS.A08`: < 400 نعم؛ 400-499 لا، إلا 408 بالعلم **13748**؛ >= 500 نعم، إلا 505 و507 |
| الوكيل | بوكيل مستخدِم والعلم **4073** تصبح سلطة الوسائط هي مضيف الوكيل ومنفذه من `proxy_media_port` (الافتراضي 587) |
| فحص الصحة | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`، `Host: mmg.whatsapp.net`، الاتصال 15000 ms، القراءة 30000 ms |

---

## 9. التنزيل

### 9.1 عنوان URL (found، `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

يتطلب الباني تجزئة وسائط، مساراً مباشراً، أو مرجعاً متقاطعاً (`media hash, direct path, or cross reference is required`). `mode` يكون `auto` أو `manual`. يُضاف `_nc_map=whatsapp-nofna` للأنواع في قائمة الخادم `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (خاصية AB، العلم **4836**). يُضاف معطى `auth` على مسار مُعلَّم (`PTU.A03`) ويستبدل معطى `auth` موجوداً. تستخدم صور الملف الشخصي النوع `ppic`؛ تستخدم الموارد الثابتة `/wa/static` مع `_nc_cat`.

### 9.2 اختيار الدلو والمضيف (مسار تحكم مُفكَّك، مُشوَّش جزئياً)

- تُصفَّى المضيفات بقدرة `download` وبكون `download_buckets` يحتوي سلسلة الدلو.
- الدلو `1` عندما يحمل المسار المباشر `_nc_hot=<seconds>` أصغر سناً من النافذة في العلم **2136**؛ وإلا، بالعلم **2134** و`max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`)؛ دلو بديل `0`.
- أنواع النشرة والحالات المُعلَّمة تتجاوز منطق الحرارة/التجزئة.
- الدلو المختار يُرسَل كـ`_nc_cat`.

### 9.3 طلب HTTP (found، `C17660kC`، `C43481Ixw`، `PlainDownloadTransfer`)

| العنصر | القيمة |
|------|------|
| الطريقة | GET (Tigon أو `HttpURLConnection`) |
| الرؤوس | `Host: <route hostname>`، `Accept-Encoding: identity`، `Range: bytes=<start>-<end>`، `User-Agent`، `X-FB-Socket-Option: TCP_CONGESTION=bbr` (مُحدَّد بعلم)، `X-FB-nc-oc`، `X-FB-Pad`، `If-None-Match` (عند معرفة ETag) |
| المقبول | HTTP 200 و206 |
| جزئي | المعاينات تستخدم بادئة 262144 بايت (`Range: bytes=0-262143`) |
| 416 | يُعامَل كمُكتمَل عندما يكون `Content-Range` هو `*/<size>` ويُطابق الحجم المحلي؛ وإلا إعادة التشغيل (العلم **29305**) أو خطأ |
| قائمة سماح | بالعلم `PTU.A04`، يجب أن يكون المضيف في `whatsapp.net`، `whatsapp.com`، `facebook.net`، `facebook.com`، `instagram.net`، `instagram.com`، `fbcdn.net`، `fbcdn.com`، `cdninstagram.net`، `cdninstagram.com` (مطابقة لاحقة) إلا إذا كان عنوان URL يحمل `category=PSA`؛ وإلا `invalid_url` (8) / سجل `host not in media CDN allow-list` |

### 9.4 التحقق (found)

يفحص تيار فك التشفير MAC؛ تُطابِق مراحل التجزئة الحالات 7 `hash_mismatch`، 31 `failed_hash_verification`، 32 `enc_hash_mismatch`؛ المُدخلات الغائبة تُطابِق 26-30 (القسم 10.2).

---

## 10. رموز الخطأ

### 10.1 معالجة حالة HTTP

| الحالة | السلوك |
|--------|-----------|
| 401، 403 | تحديث `media_conn`، تبديل المصادقة، إعادة محاولة (بحد أقصى تبديلين) |
| 408 | إعادة محاولة فقط بالعلم **13748** |
| 416 | انظر 9.3 |
| 507 | حالة تنزيل 12 `throttle`، لا تُعاد المحاولة |
| 505 | لا تُعاد المحاولة |
| 4xx أخرى | لا تُعاد المحاولة |
| 5xx، < 400 | تُعاد المحاولة ضمن ميزانية المحاولات |

### 10.2 حالة التنزيل (found، `QKK` `A03`)

| الرمز | الاسم | الرمز | الاسم |
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

الرموز 10، 22، 33 وأي شيء آخر تطبع `invalid`. `QKK.A04` يُجمِّع 1، 2، 3، 11، 15، 16، 18، 19، 20 و25 (فشل من نوع الشبكة؛ التسمية مستنتجة).

### 10.3 نتيجة الرفع (found، أسماء مقياس `media_upload_<NAME>`)

| الرمز | الاسم | الرمز | الاسم |
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

تعيين الاستثناءات في `QBE.A00` (found): `FileNotFoundException` 7، `NoSuchAlgorithmException` 16، `SocketTimeoutException` 10، `UnknownHostException` 22، `IOException` أخرى 18 (الشبكة معطَّلة) أو 3، `CancellationException` 1، `C7CL` 21، أي شيء آخر 31. بعد نتيجة غير ناجحة بـ5، 21، 24، 34، 35 أو 36 يُمحَى المفتاح والتجزئة المخزَّنان مؤقتاً (`A0B`، `A0C`).

---

## 11. إعادة محاولة الوسائط (طلب إعادة رفع)

عندما يفشل تنزيل لأن الكائن قد اختفى (عادةً حالة 5 `too_old`، أو استجابة من فئة 404)، يطلب المستقبل من هاتف المُرسِل إعادة الرفع.

### 11.1 الطلب: إيصال `server-error` (found، `SendMediaErrorReceiptJob`)

| النسخة | الكاتب | السلك |
|---------|--------|------|
| أجهزة متعددة (أساسي خاص) | الحالة 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| قديم | الحالة 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (دون `rmr`) |

`enc_iv` هو 12 بايت عشوائية؛ يُنتَج `enc_p` أصلياً (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) من رسالة تحمل معرّف stanza. تحمل المكتبة الأصلية معلومات HKDF `WhatsApp Media Retry Notification`؛ AES-GCM بمعرّف stanza كـAAD ومفتاح HKDF بطول 32 بايت مستنتج من IV بطول 12 بايت ومن تنفيذ Baileys. خاصيتا الخادم `mms4_media_retry_notification_encryption_enabled` و`mms4_server_error_receipt_encryption_enabled` رمزا قاموس (الأثر مستنتج: يحدِّدان ما إذا كان `<encrypt>` يُرسَل).

### 11.2 الإجابة: إشعار `mediaretry` (found، `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| الخطوة | التفصيل |
|------|--------|
| فحص الحساب | `rmr` من حساب آخر يسجِّل `cross-account-rmr` ويُستبعَد إلا إذا كان رمز العلم `PTV.A0F` مُفعَّلاً |
| البحث | رسالة بـ`(chat, id, from_me)`؛ الرسائل غير الوسائطية تسجِّل `message is null or not media` |
| فك التشفير | أصلي (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`)؛ نموذج النتيجة يُعطي `directPath` (يُخزَّن في الرسالة) وعدداً صحيحاً للنتيجة |
| النتيجة | `<error code>` يتجاوز النتيجة؛ يُقارِن المعالج القيمة بـ2 و3 (بترقيم البروتو العام `NOT_FOUND` = 2، `DECRYPTION_ERROR` = 3، مستنتج) |
| الاستمرار | يحصل المُنزِّل على المسار المباشر الجديد (`resume reuploading download`)؛ دون مُنزِّل نشط تُضاف الرسالة لقائمة التنزيل الآلي |
| التقرير | بالعلم **5718** يُخزَّن `reporting_token` للرسالة |

---

## 12. وسائط المرة الواحدة والحالة

| الموضوع | الحقيقة (found) |
|-------|--------------|
| التشفير/النقل | مطابق تماماً للوسائط العادية: نفس `MmsType`، نفس HKDF، نفس العناوين؛ لا يوجد نوع "مرة واحدة" في الجدول |
| العلم | `viewOnce` حقل في `ImageMessage` (**25**)، `VideoMessage` (**20**)، `AudioMessage` (**21**)؛ الحاوية `viewOnceMessage` (**37**)، `viewOnceMessageV2` (**55**)، `viewOnceMessageV2Extension` (**59**) |
| قواعد محلية | لا يستطيع المُرسِل فتح وسائط مرة واحدة خاصة به (`senders can not view their own media`)؛ تُحذَف الصور المصغَّرة لوسائط المرة الواحدة بواسطة `EphemeralUpdateRunnable/deleteViewOnceThumbnails`؛ لا يُرسَل صوت مرة واحدة دون مفتاح وسائط (`unable to send encrypted media message due to missing mediaKey`) |
| ما إذا كان الخادم يحذف الكائن بعد العرض | غير معروف |
| الحالة (`status@broadcast`) | تستخدم صفوف `MmsType` العادية (صورة، فيديو، gif، صوت) بمعرّفاتها العددية الخاصة؛ لا توجد معلومات HKDF خاصة بـ"status"؛ الأنواع الوحيدة من نوع `*-status` هي تلك الخاصة بالنشرة (القسم 13) |
| حدود الحالة | رموز قاموس `status_video_max_duration`، `status_video_max_bitrate`، `status_image_max_edge`، `status_image_quality` خصائص خادم (القيم: غير معروفة) |
| تنزيل الحالة | `C59526QnY` يحمل `MediaDownload` ونسخة `StatusMediaDownload`؛ كلاهما يبني عنوان URL بنفس المُولِّد |

---

## 13. وسائط النشرة (القناة)

| الجانب | النشرة | العادية |
|--------|-----------|---------|
| السطح في عنوان URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`، `-video`، `-ptt`، `-ptv`، `-audio`، `-document`، `-gif`، `-sticker`، `-sticker-pack`، `-music-artwork`، `-image-status`، `-video-status`، `-gif-status`، `-audio-status`، `-thumbnail-*` | أسماء عادية |
| التشفير | لا شيء: مُنزِّل العمل الفني يتطلب `artworkEncSha256` فقط للمحتوى غير الخاص بالنشرة (`required fields missing - artworkEncSha256 is null for encrypted content`)؛ للأنواع الأخرى يوجد تيار تمرير `C59535Qnh` (هوية). لا تزال صفوف `MmsType` تحمل بايتات معلومات HKDF (غير مُستخدَمة، مستنتج) |
| رمز الرفع | عشوائي، غير مرتبط بالتجزئة (القسم 8.2) | سرّ خاص بالتثبيت + التجزئة |
| تصفية المسار | لا منطق دلو حرارة/تجزئة للأسماء التي تبدأ بـ`newsletter` | منطق الدلو (9.2) |
| رمز IP في `media_conn` | يُطبَّق `ip_token` للنشرة بصرف النظر عن `set_ip_token` (العلم **12149**) | فقط عندما يكون `set_ip_token` صحيحاً |
| عمل الخادم | `server_thumb_gen=1` (العلمان **11191**، **11192**)، `server_transcode=1` للفيديو (العلم **9096**) | غير مُضبوط |
| العلم **27920** | مقروء في مسار النشرة لـ`C15490gQ`؛ الأثر غير معروف | |

---

## 14. المسار السريع وبقية نسخ الرفع

| النسخة | الدليل |
|---------|---------|
| المسار السريع | `MediaNotifyMessage` (`expressPathUrl`، `fileEncSha256`، `fileLength`) تُرسَل كرسالة E2E (`FMessageMediaExpressPathNotify`، تتطلب url، تجزئة، وطول)؛ `ExpressPathDownload` يسجِّل `EP gain <ms> <bytes>`؛ سجل الرفع `Use static route supplier for express path upload`؛ نتيجة رفع 27 `SKIPPED_EP_NO_PRIMARY_HOST`. سلوك جهة الخادم: غير معروف |
| الرفع التفاؤلي | سطح `optimistic`؛ نتائج إعادة فحص التجزئة 12؛ البروتوكول: غير معروف |
| التاريخ/حالة التطبيق | `md-msg-hist`، `md-app-state` تستخدمان خط الأنابيب العادي بسلاسل معلوماتهما |
| تاريخ المجموعة | `group-history`، معلومات `Group History`، نوع mime `application/protobuf` يفحصه المستقبل (`C34677F2y`)؛ المسار يتبع القسم 8.1 (`/mms/group-history/...`، مستنتج من التركيب العام) |

### 14.1 إرسال خلفية سمة الدردشة (جديد في 2.26.45.10، found)

تدفق "إرسال إلى الدردشة" لسمة دردشة خاصة ينتقل عبر خط الأنابيب العام هذا دون تعديل. نقطة الدخول: `ChatThemeViewModel.sendThemeToChat` (coroutine كوتلن؛ المتغيرات المحلية `targetJid`، `sentBundle`، `sharedTheme` من بيانات تنقيح محفوظة) يحل مصدر الخلفية المختار (`DOWNLOADED`، `USER_PROVIDED`، `ANIMATED`، `GRADIENT`، `DEFAULT`، `NONE`) ويستدعي `ChatThemeSettingSenderImpl.A06` ← `A01`.

| الخطوة | التفصيل (found) |
|------|-----------------|
| نسخة محلية | يُنسَخ ملف الخلفية المصدر إلى تخزين التطبيق تحت `chat_theme_sent_wallpapers/<uuid>.jpg` |
| الرفع | يُغلِّف `ChatWallpaperUploader.A00` دالة `MediaUploadCoordinatorImpl.A0G` (نفس خط أنابيب `media_conn` ← HKDF ← AES-CBC ← HMAC ← POST للأقسام 1-8 أعلاه)، طالباً وضع تشفير `LX/8cp;->A02`، الذي يحمل حقل `value` السلسلة الحرفية `"E2EE"` |
| نسخ النتيجة | تُنسَخ نتيجة الرفع (`SGq`) حقلاً بحقل إلى وصف مرفق وسائط عام (`LX/8cr`): سلسلة نتيجة الرفع ← مسار مباشر، بايتات مفتاح الوسائط، طابع زمني، وثلاث مصفوفات بايتات تجزئة/HMAC إضافية |
| سطح الضابط | يُمرَّر الوصف عبر `LX/1iA` (يرث `LX/19i`)، **واجهة ضابط مرفق الوسائط العامة نفسها** التي تستخدمها بُناة رسائل الصور العادية؛ تتوافق حقوله موضعياً مع `directPath` (**11**)، `mediaKey` (**8**)، وحقول بايتات `fileSha256`/`fileEncSha256` (**9**/**12**، القسم 6) الخاصة بـ`imageMessage` |
| نوع mime | يُضبَط `image/jpeg` صريحاً في الاستدعاء نفسه |

تُرسَل هذه إلى طرف دردشة حقيقي (`targetJid`)، لا إلى مزامنة تفضيل عرض محلية فقط: للسمات القائمة على الصور، تُعاد ترميز بتمابة الخلفية نفسها ورفعها عبر مسار الوسائط القياسي المشفَّر من طرف إلى طرف، فيُنزِّل العميل المستقبل ويفكّ تشفير صورة حقيقية بدلاً من تطبيق قالب سمة معروف. لم يُعثر على أي نوع وسائط رفع مخصَّص أو تجاوز مسار HTTP (بخلاف `/mms/group-history` الخاص بتاريخ المجموعة، القسم 14) لهذا التدفق — يبدو أنه يعيد استخدام `MmsType` موجود (على الأرجح `image`، غير مؤكَّد بشكل منفصل).

**غير معروف**: حقل `oneof` الدقيق لـ`Message` الذي ينتهي حاملاً هذا المرفق — `LX/19i`/`LX/1iA` أصناف أساس مشترَكة كبيرة تستخدمها أنواع رسائل خارجة كثيرة، ولم يُبلَغ موقع التخصيص الملموس بعد ضوابطها في هذا التمرير. أيضاً غير معروف: ما إذا كان اختيار سمة لون صِرف/بلا خلفية (`DEFAULT`/`NONE`) يُرسَل على الإطلاق، أو يبقى محلياً فقط. لم يُعثر على نوع رسالة protobuf جديد أو عملية GraphQL/MEX لهذه الميزة (فُحص مقابل فروق proto والاستعلامات بين 2.26.41.6←2.26.45.10)؛ القراءة الأكثر دفاعية هي أن هذا ينتقل عبر حقل رسالة وسائط موجود، على الأرجح `imageMessage` نفسه — **مستنتج**، غير مؤكَّد.

---

## 15. التحصين الأصلي لمحلِّلات الوسائط (found، سلاسل وتصديرات المكتبات المفكوكة التعبئة)

تُفكَّك تعبئة 81 ملف كائن مشترَك من أرشيف superpack. محلِّلات بايتات غير آمنة من الذاكرة لبايتات يتحكم فيها المهاجم محجوزة في حاويات أو مُستبدَلة بـRust.

| المُدخل | المكوِّن | التحصين |
|-------|-----------|---------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp مُترجَمة إلى WebAssembly ومُخفَّضة إلى C بواسطة wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`، `wasm2c_$webp.wasm_instantiate`)، غلاف `whatsapp::security::LibwebpSandbox` في حاوية خيطية محلية؛ علم Java `sWebPSandboxEnabled`؛ سجل الفشل `sandboxed WebP decode failed: status=%d`؛ حُرّاس `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib في حاوية wasm2c / WASI-minrt (`GiflibSandbox`، `wasi::minrt`)؛ أصناف JNI `SandboxedGifImage`، `SandboxedGifFrame`؛ حارس `Called memcpy for memory larger than the sandbox` |
| ملفات Ogg / Opus | `libwhatsapp.so` | حاويات RLBox wasm2c لـ`libogg.wasm` و`opusfile.wasm` (`rlbox_wasm2c_sandbox`)، `SandboxedOpusMultistreamDecoder`، `wa_ogg_opus::SandboxedOggFile`؛ JNI `opusSetSandboxingEnabled`؛ سجل الفخ `wasm2c sandbox trap: %s (code=%d)` |
| تحليل الحاوية والتيار | صناديق Rust في `libwhatsapp.so` | `libmp4operations-rs` (tkhd، mvhd، mdhd، stsc، stts، stz2، ctts، hvcc، clap، sidx، emsg، mfhd، hdlr، مُقسِّم DASH، قوائم التحرير)، `libwamediastreams-rs` (amr، av1 OBU، flac، h264، h265، mp3 / ID3، ogg، opus، qcelp، speex، theora، vorbis، vp8، xmp، avc SPS)، `libwaimageoperations-rs` (exif، gif، jpeg، png، webp)، `libwamediacommon-rs` (`jpegrepair.rs`، `errorcodes.rs`)، `libwamediaprovenance-rs` (قيم IPTC لنوع المصدر الرقمي مثل `trainedAlgorithmicMedia`، C2PA) |
| فك ترميز AV1 | `libdav1d.so` | dav1d **1.5.1** (سلسلة الإصدار)؛ يُصدِّر واجهة `dav1d_*` |
| ترميز AV1 | `libwzav1.so` | الإصدار 2.3.1؛ يُصدِّر فقط `wz_encoder_*` و`wz_codec_version*`؛ لا رموز فك ترميز، فلا يُحلِّل تدفقات بتات عن بُعد |
| إطارات H.264 / H.265 | `MediaCodec` الخاص بالمنصة | خارج التطبيق |

تفشل المحلِّلات بـRust بـpanics (`assertion failed: ...`، `While parsing field '...' in ...`) بدلاً من تلف الذاكرة: found كسلاسل، الأثر مستنتج. تغطي حاوية `rlbox` libogg وopusfile في `libwhatsapp.so`؛ تستخدم مكتبات أخرى wasm2c دون غلاف RLBox (مستنتج من الرموز). ما إذا كان كل مسار وسائط وارد يصل إلى هذه المحلِّلات قبل تفاعل المستخدم: غير معروف. السلوك الديناميكي (fuzzing، انهيارات وقت التشغيل): غير مُختبَر.

---

## 16. أعلام الميزات (المعرّفات كما تُقرأ في مواقع الاستدعاء؛ الأسماء غير محسومة)

| العلم | أين | يتحكم في |
|------|-------|----------|
| **149** | `RouteSelector`، `C43951qe` | حفظ وإعادة تحميل `media_conn` في التفضيلات |
| **257** | باني `Mms4RouteSupplier` | كائن التأخير التصاعدي |
| **258** | `Mms4RouteSupplier.A03` | int: محاولات إضافية للوضع 0 |
| **2134** | `A02` | دلو تنزيل مبنيّ على التجزئة |
| **2136** | `A02` | نافذة المحتوى الحار (long) |
| **4073** | `A00` | توجيه الوسائط عبر وكيل المستخدم |
| **4836** | `Mms4DownloadUrlGenerator` | قائمة الأنواع منخفضة معدل الإصابة (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | معالجة رمز التقرير |
| **9096** | `QBE` | `server_transcode=1` (فيديو النشرة) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` لصورة/فيديو النشرة |
| **12149** | `RouteSelector.A0L`، `A03` | استخدام `ip_token` |
| **12545** / **12446** | `A05` | تجاوز حد المحاولات بعد المحاولة 3 |
| **13748** | `QKS.A08` | إعادة محاولة HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | نقاط دخول `RouteSelector` | قيمة منطقية تُمرَّر لاختيار المسار كعلم الرفع (الدلالات غير محسومة) |
| **24661** | `MediaCryptoProvider` | التحقق من نطاق مفتاح غير E2EE |
| **29305** | `PlainDownloadTransfer` | معالجة 416 |
| **37982**، **38437** | `C43481Ixw` | خاصية Tigon، مهلة الطلب |

---

## 17. Baileys (`baron-baileys-v2`، قراءة المصدر، لا شيء مُختبَر)

| الجانب | Baileys | أندرويد 2.26.41.6 |
|--------|---------|-------------------|
| طلب `media_conn` | `<media_conn/>`، `w:m`، `set`، `s.whatsapp.net`؛ `Socket/chats.js` يحمل نسخة اختيارية بـ`last_id` | دائماً `<media_conn>`، مع `last_id` عندما يوجد معرّف سابق |
| الحقول المُحلَّلة | `hostname`، `maxContentLengthBytes`، `auth`، `ttl` | لا قراءة لـ`maxContentLengthBytes`؛ يضيف `auth_ttl`، `max_buckets`، `is_new`، `id`، الحقول البديلة، عناصر القدرة الفرعية، عدادات إعادة المحاولة، `ip_token` |
| طول HKDF | `hkdf(key, 112, {info})`، يستخدم البايتات 0-79 | 80 بايت؛ أول 80 بايت من ناتج HKDF لا تعتمد على الطول المطلوب، فIV ومفتاح التشفير ومفتاح MAC متطابقة |
| سلاسل المعلومات | `WhatsApp <X> Keys`؛ `gif` و`ptv` تُخطَّطان لـVideo، `ptt` لـAudio، `sticker` لـImage | نفس السلاسل والتعيينات |
| التشفير، MAC، التجزئات | AES-256-CBC، `HMAC-SHA256(macKey, iv + ct)[0:10]` تُلحَق، `fileSha256`، `fileEncSha256` على `ct + mac` | مطابق |
| عنوان URL الرفع | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| ترميز التجزئة | base64 آمن للرابط، حشو `=` مُزال، ثم `encodeURIComponent` | base64 آمن للرابط، حشو `=` محفوظ |
| الرمز | `fileEncSha256` آمن للرابط | `SHA-256(installSecret || fileEncSha256)` (النشرة: عشوائي) |
| جدول المسار | `sticker` و`thumbnail-link` إلى `/mms/image`، `ptv` إلى `/mms/video`، `md-msg-hist` إلى `/mms/md-app-state`، لا `ptt` | سلسلة `MmsType` هي جزء المسار: `sticker`، `thumbnail-link`، `ptv`، `md-msg-hist`، `ptt` |
| الرؤوس | `Content-Type: application/octet-stream`، `Origin: https://web.whatsapp.com` | لا `Origin` مُعثور عليه؛ `Host`، `Accept-Encoding: identity`، `User-Agent`، `X-FB-*` |
| إعادة المحاولة | تجربة كل مضيف مرة واحدة بالترتيب | مُزوِّد مسار بمحاولات، تبديل رمز 401/403، فحص استئناف |
| الاستئناف | لا شيء مُعثور عليه (`resume=1`، `Content-Range` غائبان) | فحص `resume=1` و`Content-Range` |
| التدفقات الجانبية | لا توليد `streamingSidecar`، `firstScanSidecar` أو `scansSidecar` مُعثور عليه في `src` | يُولَّد للفيديو، الصوت، الصور التقدمية |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | مللي ثانية داخلياً، ثوانٍ في البروتو |
| إيصال إعادة المحاولة | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`، GCM، AAD = معرّف stanza، IV 12 بايت، معلومات HKDF `WhatsApp Media Retry Notification` | حالة الكاتب 327 لها نفس تخطيط العقدة؛ IV بـ12 بايت وسلسلة المعلومات found؛ GCM/AAD مستنتجان |
| خريطة نتيجة إعادة المحاولة | `SUCCESS` 200، `DECRYPTION_ERROR` 412، `NOT_FOUND` 404، `GENERAL_ERROR` 418 | لا ينطبق (يُقارِن القيمتين 2 و3) |

نتائج عملية (قراءة الكود فقط): رفع Baileys لكائن `md-msg-hist` يستخدم سلسلة مسار مختلفة عن عميل أندرويد؛ base64 المُحشوّ في المسار فارق مرئي؛ أي تسامح من الخادم مع هذه النسخ غير معروف.

---

## 18. حالات الخطأ

| العرض | السبب | الحل |
|---------|-------|-----|
| رفع 401/403 | `auth` منتهٍ أو مُستبدَل | تحديث `media_conn`، إعادة الإرسال بـ`auth` الجديد |
| الرفع يُعيد بلا `direct_path` | الرفع مرفوض أو غير مكتمل | فحص الحالة؛ فحص استئناف بـ`resume=1` |
| تنزيل 404 / حالة 5 `too_old` | الكائن منتهي الصلاحية على CDN | إرسال إيصال `server-error` (القسم 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | بايتات تالفة أو `fileEncSha256` خاطئ | إعادة الجلب؛ التحقق من مصدر التجزئة |
| فشل فحص MAC | مفتاح وسائط خاطئ، معلومات HKDF خاطئة (خلط نوع)، أو ملف مُقتطَع | استخدام سلسلة معلومات `MmsType` الصحيح؛ لا إعادة استخدام معلومات Image لصفوف `sticker-pack` أو `ptt` |
| `invalid_url` (8) | مضيف خارج قائمة سماح CDN | قبول فقط اللواحق المُدرَجة |
| `throttle` (12)، HTTP 507 | كبت الخادم | الانتظار `backoff` ثانية (بحد أقصى 10800) |
| `no_route` (11) | لا مضيف `media_conn` صالح لهذا النوع | طلب `media_conn`، فحص وسوم القدرة |
| `failed_no_media_key` (29)، `no_sidecar` (30) | حقل proto غائب | يتطلب `mediaKey`؛ التدفق الجانبي فقط للبث |

---

## 19. فروق أساسية

| لا تخلط بين | الحقيقة |
|----------------|------|
| قائمة مضيفي `media_conn` مقابل عنوان URL الرفع | تُعطي IQ المضيفين و`auth` واحداً؛ يُبنى مسار عنوان URL والرمز والاستعلام لكل نقل |
| `auth` مقابل `token` | `auth` رمز على مستوى الحساب من `media_conn`؛ `token` لكل ملف |
| HKDF بـ80 مقابل 112 بايت | نفس المفاتيح؛ أندرويد يستخلص 80 |
| `fileSha256` مقابل `fileEncSha256` | تجزئة النص الصِّرف مقابل تجزئة `ciphertext + mac10` |
| `fileEncSha256` في المسار مقابل `directPath` | مسار الرفع يستخدم التجزئة؛ التنزيل يستخدم `directPath` الذي يُعيده الخادم |
| `mediaKeyTimestamp` مقابل نافذة إعادة استخدام المفتاح | الطابع الزمني بالثواني على السلك؛ نافذة إعادة الاستخدام 2-3 أيام على المُرسِل |
| التدفق الجانبي المُبثّ مقابل `fileEncSha256` | MACs بطول 10 بايت لكل جزء مقابل تجزئة الملف كاملاً |
| إعادة محاولة الوسائط مقابل إعادة الإرسال | يُعيد المُرسِل رفع الكائن نفسه ويُجيب بـ`directPath` جديد؛ لا تُعاد الرسالة |
| وسائط النشرة مقابل الوسائط العادية | غير مشفَّرة، سطح `newsletter`، رمز عشوائي |
| `libwzav1` مقابل `libdav1d` | مُرمِّز مقابل مُفكِّك؛ فقط المُفكِّك يُحلِّل بيانات عن بُعد |

---

## 20. التدفق الكامل (إرسال واستلام صورة واحدة)

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

## 21. المجاهيل

| العنصر | الحالة |
|------|--------|
| سلوك الخادم (التحقق من الرمز، منع التكرار، عمر الكائن، حذف المرة الواحدة) | جانب الخادم |
| أسماء الاستعلام `_nc_cbep`، `_nc_rmr`، `type`؛ العلم **21807** ومعرّفات `PTU.*` | الأسماء أو المعنى غير محسومين |
| المعرّفات العددية في `MmsType` (1، 20، 23، 25، 37، 42، 44، 57، ...) | المعنى غير محسوم |
| تشفير إعادة محاولة الوسائط الأصلي (AES-GCM، AAD، طول المفتاح) | سلسلة المعلومات مُعثور عليها؛ الخوارزمية مستنتجة |
| استهلاك `ip_token`، قيمة `X-FB-nc-oc`، مصدر `Companion_User_Secret` | غير محسوم |
| استخدام نطاق مفتاح الوسائط NON_E2EE | غير محسوم |
| بروتوكولا المسار السريع والرفع التفاؤلي | غير محسومين |
| الترتيب الدقيق للمضيفين عبر المحاولات وأعداد المحاولات المعتمدة على الوضع | مسار تحكم مُفكَّك مُشوَّش |
| أي وسائط واردة تصل أي محلِّل محجوز قبل تفاعل المستخدم | غير مُخطَّط |
| الحركة | لا شيء مُلتقَط؛ لا اختبار ديناميكي |
