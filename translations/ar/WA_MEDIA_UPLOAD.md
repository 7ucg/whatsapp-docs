<!-- src-sha1: a94958787eccb3db407fbb92cf700d9a4d424f4a -->
# WhatsApp رفع الوسائط — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** نقل الوسائط في Android: استعلام `media_conn` IQ (المضيفات، المصادقة، ttl، الـ buckets، المضيفات الاحتياطية)، بناء عناوين الرفع والتنزيل ومعاملات HTTP، جدول أنواع الوسائط مع سلاسل HKDF info، توليد مفتاح الوسائط واشتقاقه، التشفير بـ AES-CBC + HMAC، fileSha256 / fileEncSha256، mediaKeyTimestamp، direct path، الصور المصغرة، ملفات sidecar للبث (فيديو / صوت / صور تدريجية)، الرفع القابل للاستئناف، اختيار المسار، إعادة المحاولة والتراجع، رموز أخطاء الرفع والتنزيل، إيصال إعادة محاولة الوسائط وإشعار `mediaretry`، وسائط العرض لمرة واحدة والحالة، وسائط newsletter (القنوات)، express path، تقوية المحللات الأصلية للوسائط من جهة العميل، المقارنة مع Baileys

---

## 1. ما هو (تقنيًا)

لا تمر الوسائط أبدًا داخل تدفق chatd (انظر [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). تحمل الرسالة مرجعًا بصيغة protobuf فقط (المفتاح، الـ hashes، `directPath`)؛ أما البايتات فتنتقل عبر اتصالات HTTPS منفصلة إلى مضيفات الوسائط. يقدّم chatd شيئًا واحدًا: استعلام `media_conn` IQ الذي يمنح أسماء المضيفات ورمز مصادقة رفع قصير العمر. جميع العبارات مستمدة من التحليل الساكن لـ APK المفكَّك ومن المكتبات الأصلية المستخرجة؛ لم يُلتقط شيء على الشبكة. المستويات: **found** = قُرئ في الشيفرة أو السلاسل النصية، **inferred** = مستنتج، **unknown** = غير محلول.

| الطبقة | الاسم في 2.26.41.6 | الدور |
|-------|----------------|------|
| محدد المسار | `RouteSelector` (`C10950Wx`) | يحتفظ بنتيجة `media_conn` الحالية، ومؤقت التحديث، والـ throttle، ومصنع المسارات |
| محلل `media_conn` | `C43951qe` (معالج نتيجة IQ)، `C41561mf` (RoutingResponse)، `C41441mT` (RouteHost) | يحلل `<media_conn>` / `<host>` |
| مزود المسار | `Mms4RouteSupplier` (`C46433KQw`)، `C46435KQy` / `C46436KQz` (مزودات ثابتة) | يختار المضيف لكل محاولة، ويبدّل رمز المصادقة |
| مشغّل إعادة المحاولة | `TransferRetries` (`C44566Jd2`) | حلقة محاولات حول عملية نقل واحدة |
| جدول أنواع الوسائط | `MmsType` (`C15530gU`) | لكل نوع: سلسلة المسار، بايتات HKDF info، المعرّف الرقمي |
| مزود المفاتيح | `MmsImageCipherKeyProvider` (`C59530Qnc`)، `MediaCryptoProvider` (`C58155Q5r`) | HKDF بطول 80 بايت، مفتاح نطاق non-E2EE |
| تدفقات التشفير | `M2I` (تشفير الإخراج)، `M23` (تشفير الإدخال)، `P9N` / `P1X` / `P1Y` (MACs الخاصة بـ sidecar)، `C51101MlN` (فك تشفير بنطاق) | AES-CBC + HMAC |
| مشغّل الرفع | `MediaUploadUtils` (`QIh`)، `QBE`، `Q52` (إعادة استخدام المفتاح)، `C57333Po0` (توليد المفتاح + الـ hashes) | الـ hashes، ملفات sidecar، تنسيق الرفع |
| عنوان الرفع | `C43489Iy4` | `/surface/type/hash?...` |
| عنوان التنزيل | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`، `K19`) للرفع؛ `PlainDownloadTransfer` (`CallableC60106QxW`)، `C17660kC`، `C43481Ixw` (Tigon) للتنزيل | النقل |
| فحص الاستئناف | `HttpResumeCheck` (`C59524QnW`) | يسأل الخادم عن عدد البايتات التي يملكها |
| إيصال إعادة المحاولة | `SendMediaErrorReceiptJob`، حالتا الكاتب 77 و327 في `HandlerThreadC21920sG` | يطلب إعادة الرفع من المرسل |
| إشعار إعادة المحاولة | `MediaRetryNotificationHandler` (`C1S0`، رمز الإشعار 97) | يستهلك الإجابة |
| أصلي | `libwhatsapp.so` (حزم Rust للوسائط، صناديق RLBox الرملية)، `libstatic-webp.so`، `libwa_sandboxed_gifimage.so`، `libdav1d.so` | المحللات وفاكّات الترميز |

نقاط تحدد بقية التقرير:

- يشتق Android **80** بايت من مفتاح الوسائط (IV بطول 16، مفتاح التشفير 32، مفتاح MAC 32)، وليس 112 (القسم 4).
- مسار HTTP هو `/{surface}/{type}/{urlSafeFileEncSha256}` حيث `type` هو سلسلة `MmsType` الخاصة بالوسائط (`image`، `ptt`، `md-msg-hist`، ...)، وليس فئة عامة (القسم 8.1).
- الـ `token` الخاص بالرفع في Android ليس hash الملف؛ إنه SHA-256 على سر خاص بكل تثبيت وhash الملف (القسم 8.2).
- وسائط newsletter (القنوات) تشترك في الشيفرة نفسها لكنها تستخدم surface بقيمة `newsletter` وtoken عشوائيًا؛ وهي غير مشفرة (found لمسار الصورة الفنية artwork، inferred لباقي الأنواع، القسم 13).
- تُرشَّح مضيفات التنزيل بحسب bucket مشتق من hash الملف (القسم 9.2).

---

## 2. استعلام `media_conn` IQ

### 2.1 الطلب (found، `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

المهلة 32000 ms. يوجد طلب واحد فقط قيد التنفيذ (`inFlightMediaRoutingRequestTime`)؛ الاستدعاء الثاني يسجل `not sending request` ويعود. يمكن لـ throttle عام (`ChatdMediaThrottleManager`) أن يمنع الاستدعاء (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 الاستجابة (found، `C43951qe.CFS`)

| العقدة / السمة | النوع | الاستخدام |
|------------------|------|-----|
| `media_conn@auth` | string، مطلوب | رمز مصادقة الرفع (معامل الاستعلام `auth`) |
| `@ttl` | ثوانٍ | عمر الاتصال؛ الانتهاء = وقت الإرسال + ttl * 1000 |
| `@auth_ttl` | ثوانٍ | عمر رمز المصادقة؛ الانتهاء = وقت الإرسال + auth_ttl * 1000 |
| `@max_buckets` | long، الافتراضي 0 | المقياس (modulus) لـ bucket التنزيل (القسم 9.2) |
| `@is_new` | int، الافتراضي 1 | 1 = استبدال قائمة المضيفات؛ وإلا يُحتفظ بالمضيفات السابقة ويؤخذ الرمز وttl فقط (`previous hosts retained`) |
| `@id` | string | يُخزَّن كـ `last_id` ويُرسل في الطلب التالي |
| `@max_auto_download_retry` | int، الافتراضي 3 | ميزانية إعادة المحاولة للتنزيلات التلقائية |
| `@max_manual_retry` | int، الافتراضي 3 | ميزانية إعادة المحاولة للتنزيلات اليدوية |
| `@ip_token`، `@set_ip_token` | string، "0"/"1" | يُحللان ويُخزَّنان مؤقتًا؛ يُستخدم `ip_token` فقط عند تفعيل flag **12149** وكون `set_ip_token` صحيحًا (موضع الاستهلاك: unknown) |
| `host` (متكرر) | node | مدخل مسار واحد |

سمات `host` (found): `hostname` (مطلوب)، `ip4`، `ip6`، `class`، `fallback_hostname`، `fallback_ip4`، `fallback_ip6`، `fallback_class`، `type` (`primary` أو `fallback`؛ أي قيمة أخرى تصبح `primary`)، `force_ip` (`"true"`). العناصر الفرعية: `<upload>`، `<download>`، `<download_buckets>`؛ أسماء وسوم العناصر الفرعية هي مدخلات القدرات. يحتفظ `upload` و`download` فقط بالوسوم التي تظهر في مجموعة ثابتة من 34 سلسلة نوع وسائط (`audio`، `image`، `chat-wallpaper-image`، `video`، `ptv`، `kyc-id`، `sticker`، `document`، `ptt`، `gif`، `md-app-state`، `md-msg-hist`، `ppic`، عائلة `newsletter-*`، وعائلة `thumbnail-*`)؛ أما `download_buckets` فيُحتفظ به دون ترشيح.

لا يصلح مضيف المسار للاستخدام إلا إذا انتهى hostname بـ `.whatsapp.net` (`Mms4RouteSupplier.A06`، ويُطبَّق أيضًا على `fallback_hostname`).

### 2.3 التخزين المؤقت والتحديث (found)

| القاعدة | القيمة |
|------|-------|
| الحفظ | مع flag **149** تُخزَّن النتيجة كـ JSON (`auth_token`، `conn_ttl`، `auth_ttl`، `max_buckets`، `hosts`، `last_id`، `is_new`، `max_autodownload_retry`، `max_manual_retry`، `ip_token`، `set_ip_token`، `send_time_abs_ms`) تحت `route_selector_prefs` / `media_conn`؛ تُحمَّل مرة واحدة وتُستخدم فقط إذا لم تنتهِ صلاحية المصادقة بعد |
| فحص التحديث | قبل النقل: إذا انتهى الاتصال أو المصادقة خلال 120000 ms، يُرسل IQ جديد ويُنتظر حتى 20000 ms (`requestroutesandwaitforauth`) |
| المؤقت | `auth expiry - 60000 ms` بعد كل نتيجة؛ وضع foreground (`BgG`) يعيد ضبطه |
| فشل المصادقة | HTTP 401 أو 403 أثناء النقل يؤدي إلى تحديث (`onmediatransfererrororresponsecode`)، بحد أقصى تبديلين للرمز لكل عملية نقل (`JW1.A00 < 2`)، ثم تُعاد المحاولة بـ `auth` الجديد |
| المصادقة قبل المحاولة | يبدّل `refreshAuthBeforeAttempt` رمزًا أحدث عندما يكون المخزَّن ضمن 120000 ms من الانتهاء (رمز flag `PTU.A0D`) |

### 2.4 خطأ IQ (found، `C43951qe.Brt`)

`<error code backoff>` داخل نتيجة IQ:

| الرمز | السلوك |
|------|-----------|
| 503 | إعادة ضبط media throttle؛ جدولة التحديث التالي بعد تراجع Fibonacci مع jitter (`3/4 * t + rand(t/2)`) |
| 507 مع backoff > 0 | إخضاع طلبات الوسائط لـ throttle حتى `now + min(backoff, 10800) s` |
| أخرى / 0 | تُتجاهل |

---

## 3. أنواع الوسائط وسلاسل HKDF info (found، المهيّئ الساكن لـ `MmsType` `C15530gU`)

يحمل كل `MmsType` سلسلة مسار (`A02`)، وتسمية قصيرة لنوع الملف (`A01`، مثل `IMG`)، وبايتات HKDF `info` (`A03`)، ومعرّفًا رقميًا (`A00`). تُستخدم بايتات `info` كما هي كـ HKDF info (دون بادئة إضافية).

| HKDF info | سلاسل مسار `MmsType` |
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

ملاحظات (found): يتشارك `ptt` و`audio` معلومات Audio لكنهما سلسلتا مسار مختلفتان؛ يستخدم `sticker` معلومات Image؛ يستخدم `gif` و`ptv` معلومات Video؛ توجد عدة صفوف `image` بمعرّفات رقمية مختلفة (1، 23، 25، 37، 42، 44، 57؛ و`sticker` هو 20) لمواضع استدعاء مختلفة (معنى المعرّف unknown)؛ `group-history` هو المدخل الوحيد الذي لا تكون info الخاصة به بالصيغة `WhatsApp <X> Keys`. تظهر صور الملف الشخصي (`ppic`) فقط في مجموعة قدرات المسار وفي استدعاءات مولّد التنزيل، وليست `MmsType`.

---

## 4. مفتاح الوسائط والاشتقاق

### 4.1 توليد المفتاح (found)

| العنصر | القيمة |
|------|-------|
| مفتاح الوسائط | 32 بايت عشوائية من `SecureRandom` (`C57333Po0`، و`QIh.A0B` هو `new SecureRandom()`) |
| إعادة الاستخدام | `MediaKeyGen/reuse key from message contents` عندما يكون المفتاح أحدث من `172800000 ms + SecureRandom.nextInt(86400000)` (من يومين إلى ثلاثة أيام، مع jitter)، مقيسًا بالنسبة إلى الطابع الزمني المخزَّن للمفتاح؛ تُسقَط المفاتيح الأقدم (`key expired`) وتُولَّد من جديد |
| النطاق | `D5C`: ‏`E2EE` (0)، ‏`NON_E2EE` (1)، ‏`UNKNOWN` (-1) |

### 4.2 HKDF (found، `AbstractC38961i0.A00` يُستدعى من `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

يرفض `N6U.A01` أي طول آخر (`Invalid length of derived secret`). طول النص المشفر: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (كتل مبطنة بـ PKCS#5 زائد 10 بايت MAC).

### 4.3 مفتاح الوسائط non-E2EE (found، `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

يحمل `ContextInfo.mediaDomainInfo` (الحقل **74**، الرسالة `DQT`) الحقلين `mediaKeyDomain` (**1**: ‏0 UNKNOWN، 1 E2EE، 2 NON_E2EE) و`e2eeMediaKey` (**2**). مع flag **24661** يتحقق المستقبِل من أن المفتاح في الرسالة يطابق النطاق (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`)؛ وعند عدم التطابق يرجع إلى المفتاح كما هو. أي المنتجات تستخدم نطاق NON_E2EE: unknown.

---

## 5. التشفير وMAC والـ hashes

### 5.1 التشفير (found، `M2I`، `M23`، `N6U`)

| الخطوة | التفصيل |
|------|--------|
| التشفير | `AES/CBC/PKCS5Padding`، المفتاح = cipherKey، IV = iv |
| MAC | `HmacSHA256(macKey)`، يُحدَّث بـ IV أولًا ثم بكل بايت من النص المشفر؛ تُلحق أول **10** بايتات من الـ digest بالنص المشفر |
| `fileSha256` | SHA-256 على النص الأصلي (تدفق digest ‏`P9M` على الملف) |
| `fileEncSha256` | SHA-256 على النص المشفر + 10 بايتات MAC |
| الإخراج | `ciphertext || mac10`؛ ‏`Content-Length` = `N6U.A00(plaintextLength)` |

جهة فك التشفير (`P9N`، `M23`): يُتحقق من MAC على IV + النص المشفر، ثم يُقارن مع آخر 10 بايتات. فك التشفير بنطاق (`C51101MlN`): عندما لا يكون بداية النطاق 0 تُستخدم أول 16 بايت مقروءة كـ IV (كتلة النص المشفر السابقة)؛ تستخدم الأجزاء الداخلية `AES/CBC/NoPadding`، ويستخدم الجزء الأخير PKCS#5 (inferred من اختيار الـ cipher).

### 5.2 الطوابع الزمنية والمسارات

| الحقل | القيمة |
|-------|-------|
| `mediaKeyTimestamp` | ساعة محلية بالميلي ثانية محفوظة في كائن المفتاح، وتُكتب في protobuf بالثواني (`C20H.A06` = `/1000`) |
| `directPath` | سلسلة مسار يعيدها الخادم، تُخزَّن في الرسالة وفي عمود قاعدة البيانات `direct_path`؛ قد تحمل معاملات استعلام (مثلًا يُقرأ `_nc_hot` منها) |
| `url` | حقل URL كامل قديم؛ ما زال موجودًا في أصناف proto وفي استجابة الرفع، لكن مولّد التنزيل يُبنى من `directPath` أو من الـ hash (القسم 9.1) |

### 5.3 فحوص hash المتفائلة

يُسجَّل `MediaUpload/optimistic-hash-fail` و`optimistic-plaintext-hash-fail` (نتيجة الرفع 12) عندما يختلف الـ hash الذي يبلّغ عنه الخادم عن المحسوب محليًا. الرفع المتفائل (سلسلة surface ‏`optimistic`) يرفع قبل اعتماد الإرسال؛ بروتوكوله خارج اسم الـ surface: unknown.

---

## 6. حقول رسائل الوسائط

أرقام الحقول مقروءة من أصناف protobuf المولَّدة. أسماء الأصناف مطابَقة بحسب تخطيط الحقول (inferred)؛ والأرقام found.

| الرسالة (الصنف) | أرقام الحقول (الاسم = الرقم) |
|-----------------|-------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| حزمة السجل (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

أرقام الحاوية `Message` (`C30628DTw`) (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**؛ و`mediaNotifyMessage` هو الحقل **21** في الحاوية `BD3`.

### 6.1 الصور المصغرة

| النوع | الآلية (found ما لم يُذكر خلاف ذلك) |
|------|---------------------------------|
| مضمّنة | بايتات `jpegThumbnail` (**16**) في الرسالة (صورة، فيديو، مستند)؛ و`pngThumbnail` (**16**) في الملصقات |
| مرفوعة | `thumbnailDirectPath`، `thumbnailSha256`، `thumbnailEncSha256` (صورة **26-28**، فيديو **21-23**، مستند **13-15**)؛ ‏`MmsType` من نوع `thumbnail-*` مع HKDF infos الخاصة بالصور المصغرة من القسم 3 |
| المفتاح | لا يحتوي proto على حقل مفتاح منفصل للصورة المصغرة، لذا تُشفَّر الصورة المصغرة بمفتاح الوسائط الخاص برسالتها (inferred) |
| من صنع الخادم | معامل استعلام الرفع `server_thumb_gen=1`؛ قد تعيد استجابة الرفع `thumbnail_info` = JSON ‏`{thumbnail_direct_path, thumbnail_sha256}` |
| قاعدة البيانات | الجدول `mms_thumbnail_metadata` (directPath، mediaKey، mediaKeyTimestampMs، encThumbHash، thumbHash، width، height) |

---

## 7. البث وملفات sidecar (found)

الـ sidecar هو قائمة من MACs بطول 10 بايتات، واحد لكل جزء (chunk) من النص المشفر، تتيح للمشغّل التحقق من نطاق دون قراءة الملف بأكمله.

| العنصر | التفصيل |
|------|--------|
| الخوارزمية | `P9N.read`: لكل chunk تُهيَّأ `HmacSHA256(macKey)` بـ **16 بايت النص المشفر السابقة** (الـ IV للـ chunk الأول)، وتُغذّى بالـ chunk، وتُخزَّن أول 10 بايتات من الـ digest |
| الضم | يضم `C57228PmG.A00` كل MACs ذات 10 بايتات في مصفوفة بايتات واحدة |
| فيديو / صوت | `VideoMessage.streamingSidecar` (**18**)، `AudioMessage.streamingSidecar` (**18**)؛ حجم الـ chunk **65536** (`QBE`، `QIh.A00(..., 65536)`) |
| صورة تدريجية | `firstScanSidecar` (**18**) مع `firstScanLength` (**19**): chunk واحد بحجم `ceil(len/16)*16` بايت؛ و`scansSidecar` (**21**) مع `scanLengths` (**22**): أحجام chunk متغيرة (`P1Y`) |
| ملصق | `firstFrameSidecar` (**12**) مع `firstFrameLength` (**11**) |
| الإعدادات | خاصية الخادم `streaming_upload_chunk_size` هي dictionary token؛ أثرها: unknown |
| مفقود | حالة التنزيل 30 `failed_no_sidecar` |
| البث من الخادم | معاملا استعلام الرفع `stream=1` و`streaming=riff` معًا (القسم 8.1)؛ DASH: ‏`dashManifestUrl` (**33**)، `metadataUrl` (**30**) في الاستجابة |

---

## 8. الرفع

### 8.1 عنوان URL (found، `C43489Iy4`، `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| الجزء | القيمة |
|------|-------|
| `surface` | ‏`mms` (عادي)، `newsletter` (القنوات)، `optimistic` (رفع قبل الإرسال)؛ ‏`AbstractC58025Pzy` |
| `type` | سلسلة مسار `MmsType` (القسم 3)، مثل `image`، `ptt`، `md-msg-hist` |
| `urlSafeFileEncSha256` | base64 قياسي لـ `fileEncSha256` مع استبدال `+` بـ `-` و`/` بـ `_`؛ يُحتفظ بحشو `=` (`StringUtils.A0B`) |
| `direct_ip` | 1 عندما يكون authority عنوان IP (`ip4`، أو `[ip6]` بين أقواس)، وإلا 0 |
| `auth` | رمز المصادقة من `media_conn`؛ يُضاف كمعامل استعلام بواسطة `K19.A03` |
| `stream=1`، `streaming=riff` | يُضبطان معًا عندما يكون الطلب رفعًا متدفقًا (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | فقط لـ `newsletter-image` / `-status` (flag **11191**) و`newsletter-video` / `-status` (flag **11192**) |
| `server_transcode=1` | ‏`newsletter-video` مع معرّف الطلب 10 وflag **9096** |
| `_nc_rmr=1` | عمليات رفع غير newsletter (flag الطلب `A0N`) |
| `_nc_cbep=1` | عندما يسمح الطلب بذلك وflag **17404** مفعّل (المعنى unknown) |
| `type`، `media_id`، `media_id_upload` | ‏`media_id` = أعلى 63 بتًا دلالةً من UUID الرفع؛ ‏`media_id_upload` = أدنى 63 بتًا، فقط عندما يحتوي الطلب على مدخلات إضافية؛ و`type` سلسلة من المستدعي (المعنى: unknown) |

معنى أسماء الاستعلام `_nc_cbep` و`_nc_rmr` unknown (الأسماء فقط).

### 8.2 الرمز token (found، `C43489Iy4.A00`)

| الحالة | الرمز |
|------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`، جديد لكل طلب، غير مرتبط بالملف |
| غير ذلك | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`؛ ‏`installSecret` هو 32 بايت من `SecureRandom`، يُنشأ مرة واحدة ويُخزَّن في preferences باسم `upload_token_random_bytes` (base64 بلا wrap وبلا حشو) |

إذا تعذر فك ترميز `fileEncSha256` فإن الرمز هو `SHA-256(installSecret)` وحده. الغرض من هذا البناء: inferred كتحقق من جهة الخادم بأن الرافع يعرف الـ hash دون كشفه في المسار.

### 8.3 طلب HTTP (found، `HttpsFormPost` `C43478Ixt`)

| العنصر | القيمة |
|------|-------|
| المكتبة | `HttpsURLConnection` مع `SSLSocketFactory` مخصص؛ العلامة `http_stack = HttpUrlConnection` |
| الطريقة | POST (‏`setDoOutput(true)` على `HttpURLConnection`؛ دون استدعاء صريح للطريقة) |
| المهلات | الاتصال 15000 ms، القراءة 60000 ms |
| الرؤوس | ‏`Host: <route hostname>` (قد يكون authority عنوان IP)، `User-Agent`، `Accept-Encoding: identity`، `X-FB-Request-Analytics-Tags`، و`Companion_User_Secret` اختياري (وسيط مُنشئ غير null؛ دلالات companion inferred) |
| الجسم (المسار موجود) | تدفق النص المشفر الخام، ملف واحد فقط (`MMS4 upload only supports a single file`)؛ وضع بث بطول ثابت عندما يكون الطول معروفًا، وإلا chunked (`setChunkedStreamingMode(0)`)؛ المخزن المؤقت 16384 بايت |
| الجسم (لا مسار) | `multipart/form-data` قديم مع أجزاء `Content-Disposition: form-data` |
| الإلغاء | عند مقاطعة الخيط أو علم الإلغاء يُحشى التدفق (`UploadRequest/Post streaming padding bytes=`) ليكتمل الطول المعلن (الغرض inferred) |
| الاستجابة | تُقرأ حتى 1 MiB؛ ‏HTTP >= 400 يعيد الرمز، ويذهب الجسم إلى `onError` |

### 8.4 الاستجابة (found، `MediaUploadTransfer` `C59523QnV`)

مفاتيح JSON المقروءة: `url`، `direct_path`، `handle`، `enc_handle`، `mcs_request_id` (يُقبل فقط إذا طابق `[A-Za-z0-9-]{1,64}`)، `meta_hmac`، `fbid`، `ts`، `thumbnail_info` (سلسلة JSON متداخلة تحتوي `thumbnail_direct_path`، `thumbnail_sha256`)، `metadata_url`، `dash_manifest_url`. الاستجابة دون `direct_path` لا يعدّها هذا المحلل خطأ؛ وتفشل المراحل اللاحقة بـ `FAILED_NO_DIRECT_PATH` (29).

### 8.5 الرفع القابل للاستئناف (found)

| الخطوة | التفصيل |
|------|--------|
| الفحص | عنوان الرفع نفسه مع `resume=1` (`HttpResumeCheck`)؛ الإجابة JSON ‏`{"resume": "complete"}` مع `url`، `direct_path` (مرفوع مسبقًا) أو `{"resume": <offset>}` |
| المتابعة | POST مع `Content-Range: bytes <offset>-*/*`، ويُتخطى التدفق إلى `<offset>` أولًا |
| البدائل | ‏`ResumeCheck/attempting fallback MMS upload form post`، وأيضًا بعد خطأ WATLS (TLS) |
| خطأ التحليل | الحالة `PBY.A03`، ويُعاد بدء الرفع |

### 8.6 مزود المسار وإعادة المحاولة (found، `Mms4RouteSupplier`، `TransferRetries`)

| القاعدة | التفصيل |
|------|--------|
| حلقة المحاولات | `TransferRetries/run attempt = N; route = ...`؛ عملية نقل واحدة لكل مسار؛ ‏`no routes` ينهي الحلقة |
| اختيار المضيف | مضيف `type=primary` تحتوي مجموعة قدراته نوع الوسائط؛ تستخدمه أول محاولتين؛ تستخدم المحاولات اللاحقة مدخل `type=fallback` وحقوله `fallback_*` (الترتيب inferred من تدفق تحكم مشوَّش) |
| المحاولات | الافتراضي 4 (`4 - extra`)؛ مع flags **12545** و**12446** يمكن تجاوز الحد بعد المحاولة 3؛ ‏`max_auto_download_retry` / `max_manual_retry` (الافتراضي 3 لكل منهما) تغذي العدد المعتمد على الوضع (التعيين inferred) |
| التأخير | ثابت 1000 ms (`RouteSelector.A01`)؛ مع flag **257** ومحاولات إضافية، أسّي: الأساس 1000 ms، ‏`2^n`، مع jitter، بسقف 3000 ms |
| خطأ مصادقة 401 / 403 | لا يُحتسب فشلًا: انتظار رمز أحدث (الميزانية `A0J`، الافتراضي 20000 ms)، تبديل، إعادة محاولة |
| حالة HTTP القابلة لإعادة المحاولة | `QKS.A08`: أقل من 400 نعم؛ 400-499 لا، باستثناء 408 مع flag **13748**؛ ‏>= 500 نعم، باستثناء 505 و507 |
| Proxy | مع وكيل مستخدم وflag **4073** يصبح authority الوسائط هو مضيف الوكيل ومنفذه من `proxy_media_port` (الافتراضي 587) |
| فحص السلامة | `MediaHealthChecker`: ‏`POST https://<proxy>:<port>/mms/HEALTHCHECK`، ‏`Host: mmg.whatsapp.net`، الاتصال 15000 ms، القراءة 30000 ms |

---

## 9. التنزيل

### 9.1 عنوان URL (found، `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

يتطلب المُنشئ hash للوسائط أو direct path أو مرجعًا متقاطعًا (`media hash, direct path, or cross reference is required`). قيمة `mode` هي `auto` أو `manual`. تُضاف `_nc_map=whatsapp-nofna` للأنواع الموجودة في قائمة الخادم `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (خاصية AB، flag **4836**). يُضاف استعلام `auth` على مسار محكوم بـ flag (`PTU.A03`) ويستبدل معامل `auth` الموجود. تستخدم صور الملف الشخصي النوع `ppic`؛ وتستخدم الأصول الثابتة `/wa/static` مع `_nc_cat`.

### 9.2 اختيار الـ bucket والمضيف (تدفق تحكم مفكَّك، مشوَّش جزئيًا)

- تُرشَّح المضيفات بحسب قدرة `download` وبحسب احتواء `download_buckets` على سلسلة الـ bucket.
- الـ bucket هو `1` عندما يحمل direct path القيمة `_nc_hot=<seconds>` أحدث من النافذة في flag **2136**؛ وإلا، مع flag **2134** و`max_buckets > 0`: ‏`100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`)؛ والـ bucket الاحتياطي `0`.
- أنواع newsletter والحالات المحكومة بـ flag تتخطى منطق hot / hash.
- يُرسل الـ bucket المختار كـ `_nc_cat`.

### 9.3 طلب HTTP (found، `C17660kC`، `C43481Ixw`، `PlainDownloadTransfer`)

| العنصر | القيمة |
|------|-------|
| الطريقة | GET (Tigon أو `HttpURLConnection`) |
| الرؤوس | ‏`Host: <route hostname>`، `Accept-Encoding: identity`، `Range: bytes=<start>-<end>`، `User-Agent`، `X-FB-Socket-Option: TCP_CONGESTION=bbr` (محكوم بـ flag)، `X-FB-nc-oc`، `X-FB-Pad`، `If-None-Match` (عندما يكون ETag معروفًا) |
| المقبول | HTTP 200 و206 |
| جزئي | تستخدم المعاينات بادئة بحجم 262144 بايت (`Range: bytes=0-262143`) |
| 416 | يُعدّ اكتمالًا عندما يكون `Content-Range` هو `*/<size>` ويساوي الحجم المحلي؛ وإلا إعادة بدء (flag **29305**) أو خطأ |
| قائمة السماح | مع رمز flag ‏`PTU.A04`، يجب أن يكون المضيف في `whatsapp.net`، `whatsapp.com`، `facebook.net`، `facebook.com`، `instagram.net`، `instagram.com`، `fbcdn.net`، `fbcdn.com`، `cdninstagram.net`، `cdninstagram.com` (مطابقة لاحقة) ما لم يحمل URL القيمة `category=PSA`؛ وإلا `invalid_url` (8) / السجل `host not in media CDN allow-list` |

### 9.4 التحقق (found)

يتحقق تدفق فك التشفير من MAC؛ وتُعيَّن مراحل hash إلى الحالات 7 `hash_mismatch`، 31 `failed_hash_verification`، 32 `enc_hash_mismatch`؛ والمدخلات المفقودة تُعيَّن إلى 26-30 (القسم 10.2).

---

## 10. رموز الأخطاء

### 10.1 معالجة حالة HTTP

| الحالة | السلوك |
|--------|-----------|
| 401، 403 | تحديث `media_conn`، تبديل auth، إعادة محاولة (بحد أقصى تبديلين) |
| 408 | إعادة محاولة فقط مع flag **13748** |
| 416 | انظر 9.3 |
| 507 | حالة التنزيل 12 `throttle`، دون إعادة محاولة |
| 505 | دون إعادة محاولة |
| 4xx أخرى | دون إعادة محاولة |
| 5xx، أقل من 400 | تُعاد المحاولة ضمن ميزانية المحاولات |

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

الرموز 10 و22 و33 وأي رمز آخر تطبع `invalid`. يجمّع `QKK.A04` الرموز 1 و2 و3 و11 و15 و16 و18 و19 و20 و25 (إخفاقات من نوع الشبكة؛ التسمية inferred).

### 10.3 نتيجة الرفع (found، أسماء المقاييس `media_upload_<NAME>`)

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

ربط الاستثناءات في `QBE.A00` (found): ‏`FileNotFoundException` ← 7، `NoSuchAlgorithmException` ← 16، `SocketTimeoutException` ← 10، `UnknownHostException` ← 22، أي `IOException` أخرى ← 18 (الشبكة متوقفة) أو 3، `CancellationException` ← 1، ‏`C7CL` ← 21، وأي شيء آخر ← 31. بعد نتيجة غير ناجحة بالرموز 5 أو 21 أو 24 أو 34 أو 35 أو 36 يُمسح المفتاح والـ hash المخزَّنان مؤقتًا (`A0B`، `A0C`).

---

## 11. إعادة محاولة الوسائط (طلب إعادة الرفع)

عندما يفشل التنزيل لأن الكائن لم يعد موجودًا (عادةً الحالة 5 `too_old`، أو استجابة من فئة 404)، يطلب المستقبِل من هاتف المرسل أن يرفع مجددًا.

### 11.1 الطلب: إيصال `server-error` (found، `SendMediaErrorReceiptJob`)

| المتغير | الكاتب | الصيغة على السلك |
|---------|--------|------|
| متعدد الأجهزة (الهاتف الأساسي الخاص) | الحالة 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| قديم | الحالة 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (بدون `rmr`) |

`enc_iv` هو 12 بايت عشوائية؛ و`enc_p` يُنتَج أصليًا (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) من رسالة تحمل stanza id. تحتوي المكتبة الأصلية على HKDF info ‏`WhatsApp Media Retry Notification`؛ والتشفير AES-GCM مع stanza id كـ AAD ومفتاح HKDF بطول 32 بايت inferred من IV بطول 12 بايت ومن تنفيذ Baileys. خاصيتا الخادم `mms4_media_retry_notification_encryption_enabled` و`mms4_server_error_receipt_encryption_enabled` هما dictionary tokens (الأثر inferred: التحكم في إرسال `<encrypt>` من عدمه).

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
| فحص الحساب | `rmr` من حساب آخر يسجل `cross-account-rmr` ويُسقَط ما لم يكن رمز flag ‏`PTV.A0F` مفعّلًا |
| البحث | الرسالة بحسب `(chat, id, from_me)`؛ الرسائل غير الوسائط تسجل `message is null or not media` |
| فك التشفير | أصلي (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`)؛ النموذج الناتج يعطي `directPath` (يُخزَّن في الرسالة) وعددًا صحيحًا للنتيجة |
| النتيجة | `<error code>` يتجاوز النتيجة؛ يقارن المعالج القيمة مع 2 و3 (مع ترقيم proto العام `NOT_FOUND` = 2، `DECRYPTION_ERROR` = 3، inferred) |
| المتابعة | يحصل المنزِّل على direct path الجديد (`resume reuploading download`)؛ وفي غياب منزِّل نشط تُوضع الرسالة في طابور التنزيل التلقائي |
| الإبلاغ | مع flag **5718** يُخزَّن `reporting_token` للرسالة |

---

## 12. وسائط العرض لمرة واحدة والحالة

| الموضوع | الحقيقة (found) |
|-------|--------------|
| التشفير / النقل | مطابق للوسائط العادية: نفس `MmsType`، نفس HKDF، نفس عناوين URL؛ لا يوجد نوع عرض لمرة واحدة في الجدول |
| Flag | `viewOnce` حقل في `ImageMessage` (**25**)، `VideoMessage` (**20**)، `AudioMessage` (**21**)؛ والحاويات `viewOnceMessage` (**37**)، `viewOnceMessageV2` (**55**)، `viewOnceMessageV2Extension` (**59**) |
| قواعد محلية | لا يستطيع المرسل فتح وسائطه ذات العرض لمرة واحدة (`senders can not view their own media`)؛ تُحذف الصور المصغرة للعرض لمرة واحدة بواسطة `EphemeralUpdateRunnable/deleteViewOnceThumbnails`؛ والصوت ذو العرض لمرة واحدة دون مفتاح وسائط لا يُرسل (`unable to send encrypted media message due to missing mediaKey`) |
| هل يحذف الخادم الكائن بعد العرض | unknown |
| الحالة (`status@broadcast`) | تستخدم صفوف `MmsType` العادية (image، video، gif، audio) بمعرّفاتها الرقمية الخاصة؛ لا توجد HKDF info باسم `status`؛ أنواع `*-status` الوحيدة هي أنواع newsletter (القسم 13) |
| حدود الحالة | الرموز القاموسية `status_video_max_duration`، `status_video_max_bitrate`، `status_image_max_edge`، `status_image_quality` هي خصائص خادم (القيم: unknown) |
| تنزيل الحالة | يحتوي `C59526QnY` على متغيري `MediaDownload` و`StatusMediaDownload`؛ وكلاهما يبني URL بالمولّد نفسه |

---

## 13. وسائط newsletter (القنوات)

| الجانب | Newsletter | عادي |
|--------|-----------|---------|
| Surface في URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`، `-video`، `-ptt`، `-ptv`، `-audio`، `-document`، `-gif`، `-sticker`، `-sticker-pack`، `-music-artwork`، `-image-status`، `-video-status`، `-gif-status`، `-audio-status`، `-thumbnail-*` | الأسماء العادية |
| التشفير | لا يوجد: ينص منزِّل artwork على وجوب `artworkEncSha256` فقط للمحتوى غير newsletter (`required fields missing - artworkEncSha256 is null for encrypted content`)؛ وللأنواع الأخرى يوجد تدفق passthrough ‏`C59535Qnh` (identity). ما زالت صفوف `MmsType` تحمل بايتات HKDF info (غير مستخدمة، inferred) |
| رمز الرفع | عشوائي، غير مرتبط بـ hash (القسم 8.2) | سر لكل تثبيت + hash |
| ترشيح المسار | لا منطق hot / hash bucket للأسماء التي تبدأ بـ `newsletter` | منطق bucket (9.2) |
| `media_conn` ip token | يُطبَّق `ip_token` لـ newsletter بغض النظر عن `set_ip_token` (flag **12149**) | فقط عندما يكون `set_ip_token` صحيحًا |
| عمل الخادم | ‏`server_thumb_gen=1` (flags **11191**، **11192**)، ‏`server_transcode=1` للفيديو (flag **9096**) | غير مضبوط |
| Flag **27920** | يُقرأ في مسار newsletter في `C15490gQ`؛ الأثر unknown | |

---

## 14. Express path ومتغيرات رفع أخرى

| المتغير | الدليل |
|---------|----------|
| Express path | ‏`MediaNotifyMessage` (`expressPathUrl`، `fileEncSha256`، `fileLength`) يُرسل كرسالة E2E (`FMessageMediaExpressPathNotify`، يتطلب url وhash وطولًا)؛ يسجل `ExpressPathDownload` ‏`EP gain <ms> <bytes>`؛ سجل الرفع `Use static route supplier for express path upload`؛ نتيجة الرفع 27 `SKIPPED_EP_NO_PRIMARY_HOST`. السلوك من جهة الخادم: unknown |
| الرفع المتفائل | surface ‏`optimistic`؛ نتيجة إعادة فحص hash ‏12؛ البروتوكول: unknown |
| السجل / حالة التطبيق | يستخدم `md-msg-hist` و`md-app-state` المسار العادي مع سلاسل info الخاصة بهما |
| سجل المجموعة | ‏`group-history`، info ‏`Group History`، نوع mime ‏`application/protobuf` يفحصه المستقبِل (`C34677F2y`)؛ يتبع المسار القسم 8.1 (`/mms/group-history/...`، inferred من التركيب العام) |

---

## 15. تقوية المحللات الأصلية للوسائط (found، سلاسل وصادرات المكتبات المستخرجة)

استُخرج 81 كائنًا مشتركًا من أرشيف superpack. المحللات غير الآمنة للذاكرة التي تعالج بايتات يتحكم فيها المهاجم إما معزولة في sandbox أو مستبدلة بـ Rust.

| المدخل | المكوّن | التقوية |
|-------|-----------|-----------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp مُترجَمة إلى WebAssembly ومخفَّضة إلى C بواسطة wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`، `wasm2c_$webp.wasm_instantiate`)، والغلاف `whatsapp::security::LibwebpSandbox` في sandbox محلي للخيط؛ علم Java ‏`sWebPSandboxEnabled`؛ سجل الفشل `sandboxed WebP decode failed: status=%d`؛ حواجز `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib في sandbox من نوع wasm2c / WASI-minrt (`GiflibSandbox`، `wasi::minrt`)؛ أصناف JNI ‏`SandboxedGifImage`، `SandboxedGifFrame`؛ حاجز `Called memcpy for memory larger than the sandbox` |
| ملفات Ogg / Opus | `libwhatsapp.so` | صناديق RLBox wasm2c لـ `libogg.wasm` و`opusfile.wasm` (`rlbox_wasm2c_sandbox`)، ‏`SandboxedOpusMultistreamDecoder`، ‏`wa_ogg_opus::SandboxedOggFile`؛ JNI ‏`opusSetSandboxingEnabled`؛ سجل trap ‏`wasm2c sandbox trap: %s (code=%d)` |
| تحليل الحاويات والتدفقات | حزم Rust في `libwhatsapp.so` | `libmp4operations-rs` (tkhd، mvhd، mdhd، stsc، stts، stz2، ctts، hvcc، clap، sidx، emsg، mfhd، hdlr، مجزّئ DASH، edit lists)، `libwamediastreams-rs` (amr، av1 OBU، flac، h264، h265، mp3 / ID3، ogg، opus، qcelp، speex، theora، vorbis، vp8، xmp، avc SPS)، `libwaimageoperations-rs` (exif، gif، jpeg، png، webp)، `libwamediacommon-rs` (`jpegrepair.rs`، `errorcodes.rs`)، `libwamediaprovenance-rs` (قيم IPTC digital-source-type مثل `trainedAlgorithmicMedia`، C2PA) |
| فك ترميز AV1 | `libdav1d.so` | dav1d **1.5.1** (سلسلة الإصدار)؛ تصدّر واجهة `dav1d_*` |
| ترميز AV1 | `libwzav1.so` | الإصدار 2.3.1؛ تصدّر فقط `wz_encoder_*` و`wz_codec_version*`؛ لا رموز فك ترميز، لذا لا تحلل تدفقات بتات واردة من بعيد |
| إطارات H.264 / H.265 | `MediaCodec` الخاص بالمنصة | خارج التطبيق |

تفشل محللات Rust بـ panics (`assertion failed: ...`، `While parsing field '...' in ...`) بدل تلف الذاكرة: found كسلاسل نصية، والأثر inferred. يغطي sandbox ‏`rlbox` مكتبتي libogg وopusfile في `libwhatsapp.so`؛ وتستخدم المكتبات الأخرى wasm2c دون غلاف RLBox (inferred من الرموز). هل يصل كل مسار وسائط وارد إلى هذه المحللات قبل تفاعل المستخدم: unknown. السلوك الديناميكي (fuzzing، أعطال وقت التشغيل): لم يُختبر.

---

## 16. Feature flags (المعرّفات كما قُرئت في مواضع الاستدعاء؛ الأسماء غير محلولة)

| Flag | الموضع | ما يتحكم به |
|------|-------|----------|
| **149** | `RouteSelector`، `C43951qe` | حفظ `media_conn` وإعادة تحميله في preferences |
| **257** | مُنشئ `Mms4RouteSupplier` | كائن التراجع الأسّي |
| **258** | `Mms4RouteSupplier.A03` | int: محاولات إضافية للوضع 0 |
| **2134** | `A02` | bucket التنزيل المبني على hash |
| **2136** | `A02` | نافذة المحتوى الساخن (long) |
| **4073** | `A00` | تمرير الوسائط عبر وكيل المستخدم |
| **4836** | `Mms4DownloadUrlGenerator` | قائمة الأنواع منخفضة معدل الإصابة (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | معالجة رمز الإبلاغ |
| **9096** | `QBE` | `server_transcode=1` (فيديو newsletter) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` لصورة / فيديو newsletter |
| **12149** | `RouteSelector.A0L`، `A03` | استخدام `ip_token` |
| **12545** / **12446** | `A05` | تجاوز حد المحاولات بعد المحاولة 3 |
| **13748** | `QKS.A08` | إعادة محاولة HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | نقاط دخول `RouteSelector` | قيمة منطقية تُمرَّر إلى اختيار المسار كعلم الرفع (الدلالات غير محلولة) |
| **24661** | `MediaCryptoProvider` | التحقق من نطاق مفتاح non-E2EE |
| **29305** | `PlainDownloadTransfer` | معالجة 416 |
| **37982**، **38437** | `C43481Ixw` | خاصية Tigon، مهلة الطلب |

---

## 17. Baileys (`baron-baileys-v2`، المصدر مقروء، لم يُختبر شيء)

| الجانب | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| طلب `media_conn` | `<media_conn/>`، ‏`w:m`، ‏`set`، ‏`s.whatsapp.net`؛ ولدى `Socket/chats.js` متغير `last_id` اختياري | دائمًا `<media_conn>`، مع `last_id` عند وجود معرّف سابق |
| الحقول المحللة | `hostname`، `maxContentLengthBytes`، `auth`، `ttl` | لا يُقرأ `maxContentLengthBytes`؛ ويضيف `auth_ttl`، `max_buckets`، `is_new`، `id`، الحقول الاحتياطية، عناصر القدرات الفرعية، أعداد إعادة المحاولة، `ip_token` |
| طول HKDF | `hkdf(key, 112, {info})`، يستخدم البايتات 0-79 | 80 بايت؛ أول 80 بايت من ناتج HKDF لا تعتمد على الطول المطلوب، لذا IV ومفتاح التشفير ومفتاح MAC متطابقة |
| سلاسل info | `WhatsApp <X> Keys`؛ ‏`gif` و`ptv` يُربطان بـ Video، و`ptt` بـ Audio، و`sticker` بـ Image | نفس السلاسل ونفس الربط |
| التشفير، MAC، الـ hashes | AES-256-CBC، ‏`HMAC-SHA256(macKey, iv + ct)[0:10]` مُلحَق، ‏`fileSha256`، ‏`fileEncSha256` على `ct + mac` | نفسه |
| عنوان الرفع | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| ترميز الـ hash | base64 آمن للـ URL، حشو `=` محذوف، ثم `encodeURIComponent` | base64 آمن للـ URL، حشو `=` محفوظ |
| Token | `fileEncSha256` بصيغة آمنة للـ URL | `SHA-256(installSecret || fileEncSha256)` (newsletter: عشوائي) |
| جدول المسارات | `sticker` و`thumbnail-link` إلى `/mms/image`، ‏`ptv` إلى `/mms/video`، ‏`md-msg-hist` إلى `/mms/md-app-state`، دون `ptt` | سلسلة `MmsType` هي مقطع المسار: `sticker`، `thumbnail-link`، `ptv`، `md-msg-hist`، `ptt` |
| الرؤوس | `Content-Type: application/octet-stream`، ‏`Origin: https://web.whatsapp.com` | لا `Origin` وُجد؛ ‏`Host`، `Accept-Encoding: identity`، `User-Agent`، `X-FB-*` |
| إعادة المحاولة | يجرب كل مضيف مرة واحدة بالترتيب | مزود مسار مع محاولات، تبديل رمز 401 / 403، فحص استئناف |
| الاستئناف | لا شيء وُجد (`resume=1` و`Content-Range` غائبان) | فحص `resume=1` و`Content-Range` |
| ملفات sidecar | لا يوجد توليد لـ `streamingSidecar` أو `firstScanSidecar` أو `scansSidecar` في `src` | مولَّدة للفيديو والصوت والصور التدريجية |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | ميلي ثانية داخليًا، ثوانٍ في proto |
| إيصال إعادة المحاولة | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`، ‏GCM، ‏AAD = stanza id، ‏IV بطول 12 بايت، ‏HKDF info ‏`WhatsApp Media Retry Notification` | للكاتب الحالة 327 نفس تخطيط العقدة؛ ‏IV بطول 12 بايت وسلسلة info وُجدا؛ ‏GCM / AAD inferred |
| خريطة نتيجة إعادة المحاولة | `SUCCESS` 200، `DECRYPTION_ERROR` 412، `NOT_FOUND` 404، `GENERAL_ERROR` 418 | لا ينطبق (يقارن القيمتين 2 و3) |

نتائج عملية (قراءة الشيفرة فقط): رفع Baileys لكائن `md-msg-hist` يستخدم سلسلة مسار مختلفة عن عميل Android؛ وbase64 المحشو في المسار فرق ظاهر؛ وأي تسامح من الخادم تجاه هذه المتغيرات: unknown.

---

## 18. حالات الخطأ

| العَرَض | السبب | الحل |
|---------|-------|-----|
| الرفع 401 / 403 | انتهت صلاحية `auth` أو استُبدل | حدّث `media_conn` وأعد الإرسال بـ `auth` الجديد |
| الرفع لا يعيد `direct_path` | الرفع مرفوض أو غير مكتمل | افحص الحالة؛ فحص الاستئناف بـ `resume=1` |
| التنزيل 404 / الحالة 5 `too_old` | انتهت صلاحية الكائن على CDN | أرسل إيصال `server-error` (القسم 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | بايتات تالفة أو `fileEncSha256` خاطئ | أعد الجلب؛ تحقق من مصدر الـ hash |
| فشل فحص MAC | مفتاح وسائط خاطئ، أو HKDF info خاطئة (خلط الأنواع)، أو ملف مبتور | استخدم سلسلة info الخاصة بـ `MmsType` الصحيح؛ لا تعد استخدام info الخاصة بـ Image لصفوف `sticker-pack` أو `ptt` |
| `invalid_url` (8) | المضيف خارج قائمة CDN المسموحة | اقبل فقط اللواحق المدرجة |
| `throttle` (12)، HTTP 507 | throttle من الخادم | انتظر `backoff` ثانية (بحد أقصى 10800) |
| `no_route` (11) | لا يوجد مضيف `media_conn` صالح للنوع | اطلب `media_conn`، وافحص وسوم القدرات |
| `failed_no_media_key` (29)، `no_sidecar` (30) | حقل proto مفقود | اشترط `mediaKey`؛ ‏sidecar للبث فقط |

---

## 19. فروق أساسية

| لا تخلط بين | الحقيقة |
|----------------|------|
| قائمة مضيفات `media_conn` وعنوان الرفع | يعطي IQ المضيفات و`auth` واحدًا؛ أما مسار URL والـ token والاستعلام فتُبنى لكل عملية نقل |
| `auth` و`token` | ‏`auth` هو رمز مستوى الحساب من `media_conn`؛ و`token` لكل ملف |
| HKDF بطول 80 مقابل 112 بايت | نفس المفاتيح؛ يشتق Android ‏80 |
| `fileSha256` و`fileEncSha256` | hash النص الأصلي مقابل hash لـ `ciphertext + mac10` |
| `fileEncSha256` في المسار و`directPath` | مسار الرفع يستخدم الـ hash؛ والتنزيل يستخدم `directPath` الذي يعيده الخادم |
| `mediaKeyTimestamp` ونافذة إعادة استخدام المفتاح | الطابع الزمني بالثواني على السلك؛ ونافذة إعادة الاستخدام 2-3 أيام عند المرسل |
| sidecar البث و`fileEncSha256` | MACs بطول 10 بايتات لكل chunk مقابل hash للملف كاملًا |
| إعادة محاولة الوسائط وإعادة الإرسال | يعيد المرسل رفع الكائن نفسه ويجيب بـ `directPath` جديد؛ ولا تُعاد الرسالة |
| وسائط newsletter والوسائط العادية | غير مشفرة، surface ‏`newsletter`، token عشوائي |
| `libwzav1` و`libdav1d` | مرمِّز مقابل فاك ترميز؛ فاك الترميز وحده يحلل بيانات واردة من بعيد |

---

## 20. التدفق الكامل (إرسال واستقبال صورة واحدة)

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

## 21. المجهولات

| العنصر | الحالة |
|------|--------|
| سلوك الخادم (التحقق من token، إزالة التكرار، عمر الكائن، حذف العرض لمرة واحدة) | من جهة الخادم |
| أسماء الاستعلام `_nc_cbep`، `_nc_rmr`، `type`؛ وflag **21807** ومعرّفات `PTU.*` | الأسماء أو المعنى غير محلولة |
| المعرّفات الرقمية في `MmsType` (1، 20، 23، 25، 37، 42، 44، 57، ...) | المعنى غير محلول |
| تشفير إعادة محاولة الوسائط الأصلي (AES-GCM، AAD، طول المفتاح) | سلسلة info وُجدت؛ والخوارزمية inferred |
| استهلاك `ip_token`، قيمة `X-FB-nc-oc`، مصدر `Companion_User_Secret` | غير محلولة |
| استخدام نطاق مفتاح الوسائط NON_E2EE | غير محلول |
| بروتوكولا express path والرفع المتفائل | غير محلولين |
| ترتيب المضيفات الدقيق عبر المحاولات وأعداد المحاولات المعتمدة على الوضع | تدفق التحكم المفكَّك مشوَّش |
| أي وسائط واردة تصل إلى أي محلل معزول قبل تفاعل المستخدم | غير مرسوم |
| حركة الشبكة | لم يُلتقط شيء؛ لا اختبار ديناميكي |
