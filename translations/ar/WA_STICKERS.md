<!-- src-sha1: d4ba76d600d4bfecb03ea6dfec4064e9d1ae1733 -->
# WhatsApp ملصقات (Stickers) — تقرير RE كامل
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-01
**النطاق:** بروتوكول `Message.StickerMessage` (بيانات تعريفية للصورة/Lottie، أعلام الصورة الرمزية/الذكاء الاصطناعي/المميّز، `emojis`، `accessibilityLabel`)، ملصقات صوتية مضمَّنة (`StickerMessage.audioMessage`)، أغلفة عامة `lottieStickerMessage` / `audioStickerMessage`، `stickerPackMessage` (مشاركة حِزم الملصقات)، التخزين المحلي لحِزم الملصقات وصيغة `.was`/Lottie ZIP، `stickerSyncRmrMessage` (مؤكَّد غيابه)، نوايا (intents) حِزم الملصقات من جهات خارجية وعقد موفِّر المحتوى، موفِّر توليد ملصقات بالذكاء الاصطناعي المدمج، بحث الملصقات المحلي، أعلام الميزات؛ تشفير الوسائط لا يُكرَّر هنا (انظر [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md))

---

## 1. نظرة عامة

"الملصق" (sticker) على أندرويد هو أحد عدة أنواع رسائل سلكية (wire message) إضافةً إلى نظام فرعي كبير في التطبيق من الطرف الأول (متجر، عناصر مستخدَمة مؤخرًا محليًا، بحث، توليد بالذكاء الاصطناعي) وسطح تكامل عام لأطراف ثالثة (نوايا + موفِّرو محتوى). كل بايتات الوسائط (صورة الملصق، أرشيف ZIP للحزمة، الصور المصغّرة) تمر عبر خط أنابيب الوسائط المشفَّر نفسه كأي مرفق آخر — انظر [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) القسم 3 لصفوف `MmsType` (`sticker`، `sticker-pack`، `thumbnail-sticker-pack`، `newsletter-sticker`، `newsletter-sticker-pack`).

| الكيان | حقل `Message` | نوع الحقل السلكي | الدور |
|--------|------------------|-----------|------|
| ملصق مفرد | `stickerMessage` | **26**، `StickerMessage` (`C30611DTf`) | صورة/رسم متحرك مُرسَل ضمن محادثة |
| ملصق صوتي (مضمَّن) | `StickerMessage.audioMessage` | **26** ضمن `StickerMessage`، `oneof audio` → `AudioMessage` | مقطع صوتي قصير مرفق بإرسال ملصق |
| غلاف Lottie | `lottieStickerMessage` | **74**، `FutureProofMessage` (`BD2`) | غلاف عام، يُفهم من الاسم أنه مخصّص لحمولة Lottie؛ المحتوى المتداخل غير محلول |
| غلاف الملصق الصوتي | `audioStickerMessage` | **134**، `FutureProofMessage` (`BD2`) | نفس نمط الغلاف العام، جديد في هذا الإصدار؛ المحتوى المتداخل غير محلول |
| حزمة ملصقات | `stickerPackMessage` | **86**، `StickerPackMessage` (`C30610DTe`) | مشاركة/تثبيت حزمة (أرشيف ZIP من الملصقات) |
| طلب مزامنة الملصقات | `stickerSyncRmrMessage` | **47** (إصدارات أقدم) | **غائب** من بروتوكول `Message` في 2.26.41.6 (انظر القسم 7) |
| تفاعل ملصق على الحالة | `statusStickerInteractionMessage` | **110**، `StatusStickerInteractionMessage` (`C30560DRg`) | ملصق تفاعل على منشور حالة؛ خارج النطاق هنا باستثناء هذه الإشارة |
| إضافة حزمة من طرف ثالث | نية (`Intent`) أندرويد | `com.whatsapp.intent.action.ENABLE_STICKER_PACK` | تطلب تطبيق خارجي من واتساب استيراد حزمة يستضيفها هو |
| إرسال من طرف ثالث | نية (`Intent`) أندرويد | `com.whatsapp.intent.action.SEND_STICKER` | يسلِّم تطبيق خارجي ملصق WebP مفرد إلى منتقي واتساب |
| عقد محتوى الحزمة | `ContentProvider` (موفِّر التطبيق الخارجي نفسه) | `content://<authority>/metadata`، `/stickers`، `/stickers_asset` | كيفية قراءة واتساب لحزمة من طرف ثالث |
| توليد ملصقات بالذكاء الاصطناعي | `ContentProvider` (موفِّر واتساب نفسه) | `content://com.whatsapp.provider.sticker_command/generate` | إنشاء ملصقات بالذكاء الاصطناعي ضمن التطبيق، يُستهلَك عبر استدعاءات موفِّر المحتوى، وليس رسالة محادثة |

تتبع المستويات `IMPORTANT.md`: **found** = مقروء مباشرة في الشيفرة المفكوكة/السلاسل النصية/البيان (manifest)، **inferred** = مُستنتَج من بنية الشيفرة، **unknown** = غير محلول. كل الأدلة هنا ثابتة (استاتيكية، تحليل ملف APK المفكوك + البيان)؛ لم يُسجَّل شيء عبر الشبكة.

---

## 2. `Message.StickerMessage` (الحقل 26)

### 2.1 الحقول (found، `C30611DTf`)

| الحقل | # | النوع | الاستخدام |
|-------|---|------|----------|
| `url` | 1 | string | رابط كامل قديم (legacy) |
| `fileSha256` | 2 | bytes | بصمة النص الصِّرف |
| `fileEncSha256` | 3 | bytes | بصمة النص المشفَّر+MAC، وهي أيضًا بصمة مسار الرفع |
| `mediaKey` | 4 | bytes | مفتاح 32 بايت، معلومة HKDF هي `WhatsApp Image Keys` (خط أنابيب الوسائط، لا يُكرَّر هنا) |
| `mimetype` | 5 | string | `image/webp` للملصقات العادية |
| `height` / `width` | 6 / 7 | uint32 | أبعاد البكسل |
| `directPath` | 8 | string | مسار التنزيل |
| `fileLength` | 9 | uint64 | طول النص المشفَّر |
| `mediaKeyTimestamp` | 10 | int64 | بالثواني |
| `firstFrameLength` / `firstFrameSidecar` | 11 / 12 | uint32 / bytes | بيانات جانبية (sidecar) للإطار الأول من الرسم المتحرك (انظر [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) القسم 7) |
| `isAnimated` | 13 | bool | WebP متحرك |
| `pngThumbnail` | 16 | bytes | صورة مصغّرة مضمَّنة |
| `contextInfo` | 17 | `ContextInfo` | بيانات الاقتباس/الرد/الإعلان |
| `stickerSentTs` | 18 | int64 | وقت الإرسال |
| `isAvatar` | 19 | bool | ملصق صورة رمزية (avatar) |
| `isAiSticker` | 20 | bool | ملصق مولَّد بالذكاء الاصطناعي |
| `isLottie` | 21 | bool | حمولة الملصق هي رسم متحرك Lottie، لا WebP عادي (انظر القسم 4) |
| `accessibilityLabel` | 22 | string | نص قارئ الشاشة |
| `premium` | 24 | int32 | غير محلول (لم يُعثر على مستهلِك للحقل) |
| `emojis` | 25 | string | **استخدام found**: علامة بحث محلية، انظر القسم 9 |
| `audioMessage` | 26 | `AudioMessage` (`oneof audio`) | مقطع ملصق صوتي مضمَّن، انظر القسم 3 |

ثغرات في ترقيم الحقول 14، 15، 23: لا يوجد حقل معرَّف؛ استخدامها السابق غير معروف. هذا يصحِّح ملاحظة المادة المصدرية `Messages/stickerMessage`، التي تسرد `emojis` (25) كآخر حقل ولا تتضمن الحقل 26 (`audioMessage`) على الإطلاق — تأكَّد وجوده في `C30611DTf` في 2.26.41.6 (`AUDIO_MESSAGE_FIELD_NUMBER = 26`) ويطابق كتلة `oneof audio` في بروتوكول `baron-baileys-v2` الحالي.

### 2.2 تصنيف سلسلة نوع الرسالة (found)

سلاسل الأنواع المرصودة المرتبطة بإرسال `StickerMessage`/`StickerPackMessage`، مُجمَّعة من إرسال التحليلات (`C21880sC`) ومُساعد نوع الملصق: `sticker`، `avatar_sticker`، `genai_sticker`، `1p_sticker`، `user_created_sticker`، `sticker_pack`. تأتي `avatar_sticker` و`genai_sticker` من `isAvatar`/`isAiSticker`؛ وتتوافق `1p_sticker` و`user_created_sticker` مع تعداد `StickerPackOrigin` (القسم 5) لكن الدالة الدقيقة التي تحدد الاختيار بين `sticker` و`1p_sticker` و`user_created_sticker` لم تُحدَّد في هذا التمرير (أسبقية غير معروفة). تتحقق Baileys (`messages-send.js`) من `isLottie` قبل `isAvatar` عند استنتاج هذه السلسلة من جانب العميل؛ لم يُؤكَّد إن كان أندرويد يفعل الأمر نفسه.

### 2.3 `emojis` و`accessibilityLabel` (found، تمت ترقيتها من المادة المصدرية الأولية)

- `emojis` (25): يستهلكها `EmojiGroupMapper`/`StickerSearchManager` كسلسلة علامة بحث محلية — يؤكد غرضها بما يتجاوز اسم الحقل (القسم 9). لا يُستعلَم عنها من الخادم.
- يبلغ الحد الأقصى لكل من `accessibilityLabel` على *ملصق مُرسَل* و`sticker_accessibility_text` على *ملصق حزمة من طرف ثالث* (`StickerContentProviderFetcher`، القسم 8) **125** حرفًا للملصق الثابت و**250** حرفًا للمتحرك (`ThirdPartyStickerFetcher`، الأعداد الحرفية 125/250؛ يعرض JADX فرع 125 خطأً كحقل غير ذي صلة `C30628DTw.SPLIT_PAYMENT_MESSAGE_FIELD_NUMBER` لأن ذلك الحقل يحمل أيضًا القيمة 125 — وهو أثر ناتج عن فاكّ التفكيك (decompiler)، والقيمة العددية نفسها مقروءة مباشرة من الشيفرة الثنائية (bytecode)).

---

## 3. الملصقات الصوتية: `StickerMessage.audioMessage` و`audioStickerMessage` (134)

آليتان منفصلتان، كلاهما found، لا يجب الخلط بينهما:

| الآلية | الحقل | الدليل |
|-----------|-------|----------|
| مقطع مضمَّن | `StickerMessage.audioMessage` (26، `oneof audio`) | موجود في `C30611DTf`؛ يطابق `WAProto.proto` في `baron-baileys-v2` تمامًا (`oneof audio { Message.AudioMessage audioMessage = 26; }`) |
| غلاف مستقل | `Message.audioStickerMessage` (134، `FutureProofMessage`/`BD2`) | حقل جديد في `C30628DTw` لإصدار 2.26.41.6، غير موجود في مادة `Messages/` المصدرية الأولية؛ نفس نمط الغلاف العام لـ `lottieStickerMessage` (القسم 1)، المحتوى المتداخل غير معروف |

تؤكد حزمة الدعم من جانب العميل `com.whatsapp.stickers.sound` وجود ميزة تأليف "ملصق صوتي": `StickerOpusEncoder` (‏`nativeEncode(short[] pcm, String outPath)‏`، ترميز Opus أصلي (native) لمقطع مسجَّل) و`SoundStickerAudioDownloader` (يضمن جلب الصوت المرفق قبل التشغيل، ويوجِّهه عبر خط أنابيب الوسائط العادي). هذا يتوافق مع تضمين مذكرة صوتية قصيرة عبر الحقل 26 بدلًا من (أو إلى جانب) الغلاف الأحدث في الحقل 134.

---

## 4. صيغ ملفات الملصقات

### 4.1 WebP الثابت والمتحرك (found)

`mimetype = image/webp`؛ يُشير `isAnimated` إلى WebP متحرك. يمر فك الترميز عبر libwebp المعزولة (sandboxed) في `libstatic-webp.so` (انظر [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) القسم 15).

### 4.2 ملصقات Lottie — وعاء ZIP بصيغة `.was` (found، `LottieStickerZipEntrySaver` / `C161836tL`)

عند ضبط `isLottie`، لا يكون ملف الوسائط للملصق WebP: بل هو أرشيف ZIP، يُحفَظ ويُقرَأ عبر `LottieStickerZipEntrySaver`، ويجب أن يحتوي على:

| المُدخَل | الدور |
|-------|------|
| `animation/animation.json` | ملف JSON لرسم Lottie المتحرك (bodymovin)، الأساسي |
| `animation/animation.json.trust_token` | رمز ثقة/توقيع مرافق لملف JSON |
| `animation/animation_secondary.json` + `.trust_token` | متغيّر رسم متحرك ثانوي اختياري |

يضيف مُستخرِج (extractor) عام على مستوى الحزمة (`C161826tK`، علامة السجل (log tag) `StickerPackZipEntrySaver`، اسم الصنف الأساسي `SafeZipEntrySaver`) قائمة سماح لامتدادات الملفات المُستخرَجة تشمل `png`، `webp`، و`was` — أي أن امتداد الملف العام `.was` (اختصار "WhatsApp Animated Sticker") هو العلامة على القرص/في مُدخَل ZIP لهذا الوعاء الخاص بـ Lottie، ويُفحَص مقابل نوع MIME المُعلَن (`application/was`) عبر مُستكشِف محتوى (content sniffer) قبل القبول.

### 4.3 حدود استخراج أرشيف ZIP للحزمة (found، باني `C161826tK`)

| الحد | القيمة |
|-------|-------|
| الحد الأقصى للمُدخَلات لكل حزمة ZIP | **65** (مُبرمَج ثابتًا) |
| الحد الأقصى للبايتات لكل مُدخَل | رمز قاموس (معرِّف العلم **1900**، بالكيلوبايت) × 1024 |
| الحد الأقصى الإجمالي للبايتات لكل حزمة | نفس الرمز × 1024 × 65 |
| عبور المسار (Path traversal) | يُحوَّل كل مسار هدف لمُدخَل إلى صيغته القانونية (canonicalize) ويجب أن يُحلَّ ضمن مجلد الحزمة الخاص بها ("Zip entry is attempting to save outside of current directory") قبل كتابة أي بايت — حماية من نوع zip-slip |
| مُدخَل مرفوض | يُحذَف بعد فشل استكشاف نوع المحتوى، مُسجَّل كـ `StickerPackZipEntrySaver/file in zip is not valid` |

هذا يُثبِّت ويوسِّع ملاحظة مادة `Messages/stickerPackMessage` المصدرية الأولية (التي استشهدت ب‍ "استخراج ZIP وتحقق من الملفات" و"تحقق أن ملفات الملصقات تقع داخل حدود أرشيف ZIP المستخرَج" من 2.26.34.4 فقط عبر إشارة سجل، دون الحدود الفعلية).

---

## 5. `Message.StickerPackMessage` (الحقل 86)

### 5.1 الحقول (found، `C30610DTe`) — تطابق المادة المصدرية الأولية و`baron-baileys-v2` تمامًا

| الحقل | # | النوع |
|-------|---|------|
| `stickerPackId` | 1 | string |
| `name` | 2 | string |
| `publisher` | 3 | string |
| `stickers` | 4 | repeated `Sticker` |
| `fileLength` / `fileSha256` / `fileEncSha256` / `mediaKey` / `directPath` / `mediaKeyTimestamp` | 5، 6، 7، 8، 9، 13 | إشارة وسائط أرشيف ZIP للحزمة (`MmsType` `sticker-pack`، معلومة HKDF هي `WhatsApp Sticker Pack Keys`) |
| `caption` | 10 | string |
| `contextInfo` | 11 | `ContextInfo` |
| `packDescription` | 12 | string |
| `trayIconFileName` | 14 | string |
| `thumbnailDirectPath` / `thumbnailSha256` / `thumbnailEncSha256` / `thumbnailHeight` / `thumbnailWidth` | 15–19 | الصورة المصغّرة للحزمة (`MmsType` `thumbnail-sticker-pack`) |
| `imageDataHash` | 20 | string |
| `stickerPackSize` | 21 | uint64 |
| `stickerPackOrigin` | 22 | تعداد (enum) `StickerPackOrigin` |

`Sticker` المتداخل: `fileName` (1)، `isAnimated` (2)، `emojis` (3، مكرَّر)، `accessibilityLabel` (4)، `isLottie` (5)، `mimetype` (6)، `premium` (7).

`StickerPackOrigin`: `FIRST_PARTY` = 0، `THIRD_PARTY` = 1، `USER_CREATED` = 2.

### 5.2 التخزين المحلي (found، `AbstractC149676Ty.java`، `C1888782f.java`، `C0R5.java`)

| الجدول | الأعمدة |
|-------|---------|
| `message_sticker_pack` | `message_row_id`، `sticker_pack_id`، `pack_name`، `pack_description`، `publisher`، `tray_icon_file_name`، `image_data_hash`، `sticker_pack_size`، `sticker_pack_origin`؛ مُفهرَس على `pack_name` و`publisher` |
| `message_sticker_pack_stickers` | `_id`، `message_row_id`، `file_name`، `is_animated`، `emojis`، `accessibility_label`، `is_lottie`، `mimetype` |

هذا يحل محل إشارة المادة المصدرية الأولية لإصدار 2.26.34.4 (`StickerPackMessageMapper` / `message_sticker_pack`، المُستشهَد بها فقط عبر سلسلة سجل) بقائمة أعمدة إصدار 2.26.41.6 الملموسة.

---

## 6. `stickerSyncRmrMessage` — مؤكَّد غيابه في 2.26.41.6

الحقل 47 (`StickerSyncRMRMessage`: `filehash` سلسلة مكرَّرة، `rmrSource` سلسلة، `requestTimestamp` int64) **لا** يظهر في `C30628DTw` (حاوية `Message`) لإصدار 2.26.41.6: لا يوجد رقم حقل 47 يرتبط به، ولا يوجد أي صنف أو سلسلة نصية تحتوي `StickerSyncRMR`/`stickerSyncRmr` في أي مكان في الشجرة المفكوكة. هذا يطابق ويوسِّع ملاحظة المادة المصدرية الأولية نفسها التي أشارت إلى أن الحقل كان غائبًا فعليًا منذ 2.26.36.1 — إنه لا يزال غائبًا بعد خمسة إصدارات. وفقًا لعقد الأدلة فهذا **غياب مرصود**، لا إزالة مؤكَّدة: ما إذا كان قد أُعيدت تسميته أو نُقل إلى بروتوكول مختلف أو أُسقط كليًا أمر غير معروف.

لا يزال يوجد جدول مُفتَرَس بـ `filehash`، لكن لغرض غير ذي صلة: يتابع `RecentStickerDBStorage` (`C6VB`، `C17460jr`، `C6V8`) الملصقات المُرسَلة/المُستقبَلة محليًا بحسب بصمة الملف من أجل درج "المستخدَم مؤخرًا" — هذا تدوين محلي، وليس رسالة المزامنة السلكية، ويجب ألا يُخلَط به.

---

## 7. واجهة برمجية لحزم ملصقات من طرف ثالث

هذا سطح تكامل عام، موثَّق بالعُرف (أسرة الصلاحية `com.whatsapp.sticker.READ`)؛ كل ما يلي found في `AndroidManifest.xml` والأصناف الداعمة.

### 7.1 سطح البيان (Manifest)

| المكوِّن | الإعلان |
|-----------|-------------|
| الصلاحية | `com.whatsapp.sticker.READ` — مطلوبة كـ `android:readPermission` على موفِّر المحتوى الخاص بتطبيق الطرف الثالث نفسه قبل أن يستعلم واتساب عنه |
| نشاط إضافة حزمة | `com.whatsapp.stickers.ui.thirdpartystickers.AddThirdPartyStickerPackActivity`، `exported="true"`، مُرشِّح نية (intent-filter) `action com.whatsapp.intent.action.ENABLE_STICKER_PACK` + `category DEFAULT` |
| اسم مُستعار قديم لإضافة حزمة | `activity-alias` بـ `com.whatsapp.stickers.thirdpartystickers.AddThirdPartyStickerPackActivity` → يشير إلى الهدف نفسه (مُحتفَظ به للتطبيقات المبنيَّة ضد اسم الحزمة قبل إعادة الهيكلة) |
| نشاط إرسال ملصق مفرد | `com.whatsapp.stickers.command.send.SendStickerCommandActivity`، `exported="true"`، مُرشِّح نية `action com.whatsapp.intent.action.SEND_STICKER` + `category DEFAULT` + `data mimeType="image/webp"` |
| موفِّر فحص القائمة البيضاء | `com.whatsapp.provider.sticker_whitelist_check` → `WhitelistPackQueryContentProvider`، `exported="true"` |
| رابط عميق (deep link) | `whatsapp://stickerpack` (`<data android:host="stickerpack" android:scheme="whatsapp"/>`)؛ النشاط الهدف/التوجيه لهذا المضيف المحدَّد لم يُحدَّد في هذا التمرير (unknown) |

### 7.2 عقد نية `ENABLE_STICKER_PACK` (found، `AddThirdPartyStickerPackActivity`)

بيانات الطلب (`String`): `sticker_pack_id`، `sticker_pack_authority`، `sticker_pack_name`.

التحقق قبل جلب أي شيء:
1. يجب أن تكون `getCallingActivity()` غير فارغة (يجب أن تأتي النية من `startActivityForResult`، لا من بث شبيه بالإعلان المفرد).
2. يجب أن تُحلَّ `PackageManager.resolveContentProvider(sticker_pack_authority, …)` إلى موفِّر.
3. يجب أن تطابق حزمة الموفِّر المُحلَّل حزمة النشاط المُستدعي — **لا يمكن لتطبيق أن يضمن سلطات (authorities) لا يملكها هو نفسه**.

بيانات النتيجة في النية (`Intent`) المُعادة (أحدها): `add_successful=true`، `already_added=true`، `validation_error=<string>`، أو `CancelReason.USER_CANCELLED=true` (رفض المستخدِم مربع حوار الإضافة).

### 7.3 عقد موفِّر محتوى الحزمة (found، `StickerContentProviderFetcher`/`C179697lN`، `C175327dG`)

يقرأ واتساب حزمة من طرف ثالث باستعلام موفِّر *التطبيق المُستدعي نفسه* عند السلطة (authority) المُعطاة، محميًا بشرط `readPermission == "com.whatsapp.sticker.READ"` على ذلك الموفِّر:

| الرابط (URI) | الأعمدة المُعادة |
|-----|-------------------|
| `content://<authority>/metadata/<identifier>` | `sticker_pack_identifier`، `sticker_pack_name`، `sticker_pack_publisher`، `sticker_pack_icon`، `android_play_store_link`، `ios_app_download_link`، `image_data_version`، `whatsapp_will_not_cache_stickers`، `animated_sticker_pack` |
| `content://<authority>/stickers/<identifier>` | `sticker_file_name`، `sticker_emoji`، `sticker_accessibility_text` |
| `content://<authority>/stickers_asset/<identifier>/<filename>` | تيار (stream) قابل للفتح (أيقونة الدرج أو ملف ملصق مفرد) |

التحقق الموجود في الجالب (fetcher): يُرفَض `authority`/`identifier` عند احتوائهما أحرفًا غير صالحة؛ `identifier` ≤ 128 حرفًا؛ يجب أن يُكرِّر `sticker_pack_identifier` المُعاد المعرِّف المطلوب؛ اسم ملف `sticker_pack_icon` ≤ 128 حرفًا؛ يجب أن يحتوي `android_play_store_link` على `play.google.com`، ويجب أن يحتوي `ios_app_download_link` على `itunes.apple.com` أو `apps.apple.com`؛ `publisher`/`name` غير فارغين و≤ 128 حرفًا؛ معرِّف `tray` غير فارغ؛ يجب أن يقع عدد الملصقات ضمن `[flag 17124, flag 17327]` شاملةً (حدود رمز قاموس، القيم العددية غير مُحلولة في هذا التمرير)؛ يُحدَّد كل أصل ملصق مُجلَب بحد أقصى **~103424 بايت (101 كيلوبايت)** للحزمة الثابتة أو **~512512 بايت (500.5 كيلوبايت)** للحزمة المتحرِّكة (‏`(Math.min(animated ? 500 : 100, 1024) + 1) * 1024`‏)؛ تُسقَط التيارات الزائدة الحجم أو غير القابلة للقراءة بضبط الملف إلى null بدلًا من إلغاء الحزمة كاملةً. مسار مطابق `app may have been deleted` / `third_party_sticker_app_deleted` يُعالِج حالة اختفاء حزمة الموفِّر في منتصف الجلب.

يتحكم علم بوليني مستقل (**13081**) في ما إذا كانت حزمة مُدرَجة بالفعل في القائمة البيضاء تُعاد جلبها من موفِّر المحتوى أو تُقدَّم من ذاكرة التخزين المؤقت، ويبدِّل العلم **22198** بين تدفق إضافة أقدم تفاعلي عبر مربع حوار متزامن والتوجيه مباشرة إلى شاشة معاينة حزمة الملصقات؛ ويختار العلم **13711** بين متغيِّرين داخليين للتثبيت (`C175327dG.A00` مقابل `A01`) عند التثبيت عبر مسار اختصار موفِّر المحتوى (القسم 7.5) بدلًا من النشاط.

### 7.4 عقد نية `SEND_STICKER` (found، `SendStickerCommandActivity`)

البيانات: رابط `content://`، من موفِّر التطبيق المُستدعي نفسه، يجب أن تُحلَّ سلطته إلى الحزمة المُستدعية ذاتها. يجب أن يُفكَّك ترميز الملف المُشار إليه كصورة WebP بأبعاد **512×512** تمامًا وبحجم ≤ **500000** بايت؛ يُعيد العميل ختم (restamp) الملف عبر خط أنابيب الملصقات العادي (البصمة، التخزين، الإرفاق) ويُرفِق بيانات النية (`Intent`) التالية كبيانات تعريفية لحزمة `Sticker` إن وُجدت: `sticker_accessibility_text`، `sticker_pack_id`، `sticker_pack_name`، `sticker_pack_publisher`، `sticker_pack_ios_store_link`، `sticker_pack_play_store_link` (يُتحقَّق من رابطَي المتجرين بنفس فحوص المجال في القسم 7.3).

### 7.5 موفِّر فحص القائمة البيضاء (found، `WhitelistPackQueryContentProvider`)

`content://com.whatsapp.provider.sticker_whitelist_check/<match>?authority=<pkg-authority>&identifier=<pack-id>` — مؤشِّر (cursor) من صف واحد وعمود واحد (`result`، `0`/`1`) يجيب عن سؤال "هل هذه الحزمة مُضافة بالفعل". التحقق من المُستدعي يُطابق 7.2: يجب أن تساوي الحزمة المُستدعية الحزمة التي تملك `authority` المُستعلَم عنها. نوع MIME المُعاد عبر `getType()`: `vnd.android.cursor.item/vnd.com.whatsapp.provider.sticker_whitelist_check.is_whitelisted`.

### 7.6 موفِّر أمر الملصقات الداخلي (found، `StickerCommandProvider`، `com.whatsapp.provider.sticker_command`، `exported="true"`)

ليس جزءًا من عقد الطرف الثالث أعلاه — هذا موفِّر واتساب نفسه، تستعلم عنه أسطح واجهة المستخدم/المساعِد الخاصة بواتساب، بتوجيه حسب آخر جزء من مسار الرابط (URI):

| المسار | السلوك |
|------|--------|
| `installPack?authority=&identifier=` | يثبِّت حزمة عبر مسار الجلب/التحقق نفسه `C175327dG` من القسم 7.3، متجاوزًا واجهة النشاط |
| `removePack?authority=&identifier=` | يلغي تثبيت حزمة مُضافة سابقًا |
| `generate?prompt=` | توليد ملصق بالذكاء الاصطناعي (القسم 8)؛ يجب أن يكون طول `prompt` بين 3 و200 حرفًا بعد الاقتصاص (trim) |
| `availability` | يُعيد `{available, consent_required}` لتوليد الملصقات بالذكاء الاصطناعي |
| `image/<token>` (عبر `openFile`) | يُبث ملصقًا مولَّدًا بصيغة PNG/WebP مُستعاد برمز (token) معتم، نوع MIME هو `image/webp` |

---

## 8. الملصقات المولَّدة بالذكاء الاصطناعي (found، `AiStickerCommands`، `StickerCommandProvider`)

يُشير `isAiSticker` (الحقل 20) إلى أن `StickerMessage` مولَّد بالذكاء الاصطناعي؛ سلسلة النوع هي `genai_sticker` (القسم 2.2). يتم التوليد نفسه بإشعال محلي من واجهة المستخدم عبر مسار الموفِّر `generate` (7.6): يُفحَص مانِحَا الأهلية (`C174467bs.A00`) والموافقة (`A02`) قبل أي استدعاء توليد؛ تعود النتائج كقائمة من `token`s معتمة تُحَلّ لاحقًا عبر `image/<token>`. محرِّك التوليد الفعلي (على الجهاز أم من جانب الخادم) غير معروف من هذا المسار الشيفري — فقط سلسلة عمل الأهلية/الموافقة/الرمز من جانب العميل مُحلولة.

---

## 9. بحث الملصقات (found، `StickerSearchManager`، `EmojiGroupMapper`، حزمة الاقتراحات السياقية)

محلي بالكامل، وليس استعلامًا من الخادم. تأخذ `StickerSearchManager.A00` استعلامًا نصيًا حرًا، وتحلِّله إلى مجموعة من رموز الإيموجي عبر `EmojiGroupMapper`، وتضمها في سلسلة مفصولة بفراغات، وتطابق تلك السلسلة مقابل حقل `emojis` **المخزَّن محليًا** لكل `StickerMessage`/`Sticker` من حزمة (القسم 2.3) إضافة إلى المرشَّحين المستخدَمين مؤخرًا/المميَّزين، وتقسِّم النتائج إلى حاويتين: "تطابق إيموجي دقيق" و"أخرى"، وتقتصر على حد نتائج برمز قاموس (العلم **22573**). علم `includeAvatarResults` مستقل يتحكم في مشاركة ملصقات الصور الرمزية (avatar)، محمي بفحص أهلية خاص به. هذا يؤكد — ويرقي من "قد يحتوي… غير معروف" إلى found — أن حقل `emojis` في البروتوكول هو مفتاح فهرس البحث من جانب العميل، لا مجرد علامة عرض.

---

## 10. تشفير الوسائط (ربط، لا تكرار)

تمر كل إشارة وسائط تحمل ملصقًا (`stickerMessage`، `stickerPackMessage`، وصورهما المصغّرة) عبر خط أنابيب الوسائط ذاته المُوثَّق في [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md): مفتاح وسائط عشوائي بطول 32 بايت، HKDF-80 (‏`WhatsApp Image Keys` لـ `sticker`، `WhatsApp Sticker Pack Keys` لـ `sticker-pack`، `WhatsApp Sticker Pack Thumbnail Keys` للصورة المصغّرة للحزمة، ومعالجة بنمط `WhatsApp Image Thumbnail Keys` غير مستخدَمة هنا — لكل من الملصق والصورة المصغّرة للحزمة سلسلة معلومات (info) مخصَّصة له)، AES-CBC + HMAC-SHA256 مُقتصَر إلى 10 بايت، `fileSha256`/`fileEncSha256`، مضيفون صادرون عن `media_conn`، وشكل رابط الرفع `/mms/<type>/<hash>`. لا شيء خاص بالملصقات يُغيِّر أي من ذلك؛ انظر أقسام 2–9 من ذلك التقرير لجدول الاستخلاص والمحاولة والرموز الخطأ الكامل.

---

## 11. أعلام الميزات (المعرِّفات كما تُقرَأ عند نقاط الاستدعاء؛ الأسماء غير محلولة)

| العلم | المكان | ما يتحكم به |
|------|-------|----------|
| **1900** | باني `C161826tK` | موازنة حجم استخراج أرشيف ZIP للحزمة لكل مُدخَل وإجماليًا (بالكيلوبايت) |
| **13081** | `AddThirdPartyStickerPackActivity` | إعادة الجلب مقابل التخزين المؤقت لحزمة طرف ثالث مُدرَجة في القائمة البيضاء بالفعل |
| **13711** | `StickerCommandProvider`، `AddThirdPartyStickerPackActivity` | يختار متغيِّر مسار التثبيت (`C175327dG.A00` مقابل `A01`) |
| **17124** / **17327** | `StickerContentProviderFetcher` | الحد الأدنى / الأقصى لعدد الملصقات المقبول من حزمة طرف ثالث |
| **22198** | `AddThirdPartyStickerPackActivity` | تدفق إضافة تفاعلي عبر مربع حوار مقابل التوجيه المباشر إلى شاشة المعاينة |
| **22573** | `StickerSearchManager` | حد نتائج البحث المحلي |

---

## 12. Baileys (`baron-baileys-v2`، شيفرة مصدرية مقروءة، لم يُختبَر شيء)

| الجانب | Baileys | أندرويد 2.26.41.6 |
|--------|---------|-------------------|
| حقول `Message.StickerMessage` | نفس مجموعة الحقول بما فيها `audioMessage` (26، `oneof audio`) — مصدر البروتوكول يطابق بنية 2.26.41.6 المفكوكة حقلًا بحقل | نفسه (القسم 2.1) |
| حقول `Message.StickerPackMessage` | نفس مجموعة الحقول (1–22) | نفسه (القسم 5.1) |
| إرسال ملصق | تبني `prepareWAMessageMedia({ sticker })` حقل `stickerMessage` عبر مسار تحضير الوسائط العام (‏`MmsType` `sticker`، معلومة HKDF للصورة)؛ خيار `stickerAudio` يُرفِق `audioMessage` مُحضَّرًا إلى `m.stickerMessage.audioMessage` | نفس خط أنابيب الوسائط حسب [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) القسم 17 |
| إرسال حزمة | تُمرَّر مُدخَلات `stickerPackMessage`/`stickerPack` عبر `StickerPackMessage.fromObject` دون تحقق إضافي | يتحقق العميل إضافةً عبر مُستخرِج ZIP وقيود قاعدة البيانات (القسمان 5، 6) قبل قبول حزمة يبنيها هو نفسه |
| فك الترميز | يربط `decode-wa-message.js` بين `isAvatar`→`avatar_sticker`، `isAiSticker`/`isGenAI`→`genai_sticker`؛ يربط `messages-send.js` بين `isLottie`→`1p_sticker` قبل `isAvatar`/`sticker` العادي عند استنتاج سلسلة النوع الصادرة | نفس ثلاث سلاسل أنواع رسائل موجودة في إرسال تحليلات أندرويد (`avatar_sticker`، `genai_sticker`، إضافة إلى `1p_sticker`/`user_created_sticker`)؛ ترتيب الأسبقية الدقيق لأندرويد غير مؤكَّد (القسم 2.2) |
| نوايا/موفِّرو حزم الطرف الثالث | غير مُنفَّذة — لا يملك Baileys أي سطح `Intent`/`ContentProvider` لأندرويد | سطح كامل، القسم 7 |
| أغلفة `lottieStickerMessage` / `audioStickerMessage` | موجودة كحقل `FutureProofMessage` بسيط في البروتوكول فقط؛ لا يوجد مسار تشفير/فك تشفير مخصَّص | نفس الغلاف البسيط، لا توجد معالجة خاصة بالحقل هنا أيضًا (القسم 3) |

---

## 13. حالات الخطأ

| العرض | السبب | الإصلاح |
|---------|-------|-----|
| تُعيد `ENABLE_STICKER_PACK` خطأ `validation_error` "cannot find the provider for authority" | سلسلة `authority` لتطبيق الطرف الثالث لا تُحلَّ إلى أي موفِّر مُثبَّت | يجب أن يعلن تطبيق نشر حزمة الملصقات موفِّره ويصدِّره تحت سلطة (authority) تلك بالضبط |
| تُعيد `ENABLE_STICKER_PACK` رسالة "does not own authority" | حزمة المُستدعي تختلف عن حزمة الموفِّر المُحلَّل | لا يمكن لتطبيق أن يضمن إلا السلطات داخل حزمته هو نفسه |
| تفشل إضافة الحزمة بصمتًا برسالة "sticker count should be between X and Y" | أعاد استعلام `stickers` للحزمة عدد صفوف خارج `[flag 17124, flag 17327]` | حافظ على مؤشِّر `/stickers/<id>` للطرف الثالث ضمن الحدود المُهيَّأة من الخادم |
| `SafeZipEntrySaver: File being unzipped is too big` / "Too many files to unzip" | تتجاوز حزمة ZIP موازنة البايتات لكل مُدخَل/إجماليًا أو سقف 65 مُدخَلًا | قلِّص الحزمة أو قسِّم الملصقات على حزم |
| خطأ `tray image name invalid` / طول الاسم | يحتوي `sticker_pack_icon` للطرف الثالث على أحرف غير صالحة أو يتجاوز 128 حرفًا | طهِّر وقصِّر اسم ملف الدرج |
| `StickerPackZipEntrySaver/file in zip is not valid` | نوع المحتوى المُستكشَف لمُدخَل مُستخرَج لا يطابق امتداده/نوع MIME المُعلَن | أرسل مُدخَلات تطابق بايتاتها فعليًا `png`/`webp`/`was` |
| `the sticker is not a 512px WebP` (`SEND_STICKER`) | صورة نية الملصق المفرد ليست بأبعاد 512×512 تمامًا | غيِّر الحجم قبل إرسال النية |

---

## 14. تمييزات أساسية

| لا تخلط بين | الحقيقة |
|----------------|------|
| `StickerMessage.audioMessage` (الحقل 26) و`Message.audioStickerMessage` (الحقل 134) | الأول `AudioMessage` مضمَّن مؤكَّد داخل إرسال ملصق؛ الثاني حقل غلاف مستقل على مستوى الأعلى لا يزال معتمًا، جديد في هذا الإصدار |
| `isLottie` (علم خاص بالملصق) و`Message.lottieStickerMessage` (الحقل 74، غلاف) | العلم مرتبط بصيغة ملف ملموسة found (أرشيف ZIP بصيغة `.was` يحتوي `animation/animation.json`)؛ حمولة الحقل الغلاف المتداخلة لا تزال غير محلولة — لم يظهر أنهما الآلية نفسها |
| `stickerSyncRmrMessage` (رسالة سلكية، غائبة) و`RecentStickerDBStorage` (جدول محلي مُفتَرَس بـ `filehash`) | الأولى لم تعد موجودة على السلك في هذا الإصدار؛ الثانية تدوين محلي غير ذي صلة يُفترَس أيضًا بصمة الملف بالمصادفة |
| عقد حزمة الطرف الثالث (الأقسام 7.2–7.5، موفِّر التطبيق الخارجي) و`StickerCommandProvider` (القسم 7.6، موفِّر واتساب نفسه) | يستطيع كلاهما "تثبيت حزمة بسلطة+معرِّف"، لكن الأول هو واتساب *يقرأ موفِّر تطبيق آخر*، والثاني اختصار واتساب الداخلي حول واجهة نشاطه الخاص |
| توليد ملصقات بالذكاء الاصطناعي (`isAiSticker`، تدفق GenAI محلي) وتطبيقات الذكاء الاصطناعي/الملصقات من أطراف ثالثة | الأول ميزة واتساب الخاصة ضمن التطبيق خلف `StickerCommandProvider`؛ لا علاقة له بعقد موفِّر المحتوى للطرف الثالث |

---

## 15. التدفق: إضافة حزمة ملصقات من طرف ثالث

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

## 16. مجاهيل

| العنصر | الحالة |
|------|--------|
| حمولة `lottieStickerMessage` (74) و`audioStickerMessage` (134) المتداخلة | الحقل موجود، غلاف `FutureProofMessage` عام، المحتويات غير محلولة |
| أسبقية أندرويد الدقيقة لسلاسل الأنواع `sticker` مقابل `1p_sticker` مقابل `user_created_sticker` | تم العثور فقط على ربط شيفرة التحليلات الثنائية، وليس دالة الاختيار |
| حقل `premium` (24) على `StickerMessage`/`Sticker` | لم يُعثَر على مستهلِك له |
| القيم العددية خلف أعلام رمز القاموس 1900، 17124، 17327، 22573 | معرِّفات الرموز موجودة، القيم الفعلية غير محلولة استاتيكيًا |
| هدف الرابط العميق `whatsapp://stickerpack` | المضيف مُعلَن في مُرشِّح النية العام للروابط العميقة في البيان؛ الشاشة الداخلية التي تستهلكه لم تُحدَّد |
| محرِّك توليد الملصقات بالذكاء الاصطناعي (على الجهاز أم من جانب الخادم) | فقط سلسلة عمل الأهلية/الموافقة/الرمز من جانب العميل مُحلولة |
| هل يفرض الخادم حدوده الخاصة لحجم/عدد الحزمة بما يتجاوز حدود العميل | من جانب الخادم، غير معروف |
| مصير `stickerSyncRmrMessage` (أُعيدت تسميته، نُقلت، أو أُسقطت) | مؤكَّد غيابه من بروتوكول السلك من 2.26.36.1 حتى 2.26.41.6؛ الإزالة غير مؤكَّدة |
| حركة الشبكة (Traffic) | لم يُسجَّل شيء؛ لا اختبار ديناميكي |
