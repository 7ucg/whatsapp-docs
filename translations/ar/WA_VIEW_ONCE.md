<!-- src-sha1: b9a264b89fe2f15a6ff3587c9bc5a6b3a47e10c0 -->
# WhatsApp العرض لمرة واحدة — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-01
**النطاق:** الغلاف `viewOnceMessage` / `viewOnceMessageV2` / `viewOnceMessageV2Extension` مقابل الحقل المضمَّن `viewOnce` على `ImageMessage` / `VideoMessage` / `AudioMessage` / `ExtendedTextMessage`، آلية فك الغلاف العامة للرسائل المشتركة مع الرسائل المؤقتة (disappearing messages)، أنواع الرسائل وواجهة الوسم المشتركة، التطبيق من جهة العميل (حجب لقطة/تسجيل الشاشة، تقييد إعادة التوجيه/المشاركة/الحفظ، حجب العرض الذاتي للمرسل، تنظيف الوسائط المقتبسة)، التخزين المحلي وآلة الحالة (`message_view_once_media`، مهمة الحذف)، دورة حياة مفتاح الوسائط (مرتبط، غير مكرَّر)، حالة السلك `unavailable[type="view_once"]` ورموز القراءة/الكتابة بين الأجهزة، أعلام الميزات، مقارنة Baileys

---

## 1. ما هو

العرض لمرة واحدة (view-once) هو سمة لكل رسالة، لا نوع رسالة منفصل: يمكن وسم أي صورة أو فيديو أو رسالة صوتية، أو (في الإصدارات الأخيرة) نص، بحيث يحذف عميل المستلم النسخة المحلية بعد فتحها مرة واحدة، ويحجب العميل إضافة إلى ذلك لقطات الشاشة/تسجيل الشاشة ويُخفي إعادة التوجيه/المشاركة/الحفظ طالما كانت مفتوحة. كل العبارات هي تحليل ساكن للـ APK المفكَّك؛ لم يُلتقط شيء على الشبكة. المستويات: **found** = قُرئ في الشيفرة، **inferred** = مستنتج من الشيفرة، **unknown** = غير محلول. الأسماء حُلّت في 2.26.41.6 من سلاسل نصية ثابتة ووسوم سجلّ (`AppDataManager/contributeMetaAppData`، `ConversationRowViewOnceMedia/`، `EphemeralUpdateRunnable/`، `ViewOnceMessageStore/`، معرّفات سلاسل واجهة المستخدم).

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|-----------------|------|
| رسالة الغلاف (حقل واحد، `message` **1**) | `BD2` | متن `viewOnceMessage` **37**، `viewOnceMessageV2` **55**، `viewOnceMessageV2Extension` **59** على `Message` (`C30628DTw`) |
| علم مضمَّن لكل نوع وسائط | `ImageMessage.viewOnce` **25**، `VideoMessage.viewOnce` **20**، `AudioMessage.viewOnce` **21**، `ExtendedTextMessage.viewOnce` **30** | يُضبط مباشرة على رسالة الوسائط/النص، بلا غلاف |
| مفتاح التبديل بين المضمَّن والغلاف | العلم **8784** | عند التفعيل: الحقل المضمَّن فقط؛ عند التعطيل: الغلاف + الحقل المضمَّن معًا (6.3) |
| معالج صورة العرض لمرة واحدة | `C34670F2r` ("FMessageViewOnceImageProtobuf") | يبني/يقرأ `DdP`، نوع الرسالة **42** |
| معالج فيديو العرض لمرة واحدة | `C34671F2s` ("FMessageViewOnceVideoProtobuf") | يبني/يقرأ `C30972DdZ`، نوع الرسالة **43** |
| معالج نص العرض لمرة واحدة | `F33` ("FMessageViewOnceTextProtobuf") | يبني/يقرأ `C31208Dhd`، نوع الرسالة **78** |
| معالج صوت العرض لمرة واحدة | `C34669F2q` ("FMessageViewOnceAudioProtobuf") | يبني/يقرأ `C30963DdH`، نوع الرسالة **82** |
| واجهة الوسم | `InterfaceC24513Ahd` | تُنفَّذ من قبل جميع فئات FMessage الأربع أعلاه؛ تُستخدم لتوحيد سلوك واجهة المستخدم/القوائم عامةً |
| جدول الحالة المحلي | `message_view_once_media` | الأعمدة `message_row_id`، `state` |
| مُدخِل الحالة | `C199158dT` ("ViewOnceMessageStore") | جلب/إدراج/تحديث `state` |
| مهمة الحذف | `EphemeralUpdateRunnable` (فئة مجهولة داخل `C199218dZ`)، نوع المهمة **3** | "`ViewOnceMessageStore/getViewOnceMessagesToDelete`" |
| مساعد حجب التصوير الشاشة | `C66572s0` | `window.addFlags(8192)` = `FLAG_SECURE` |
| مفتاح العرض لمرة واحدة لعارض الوسائط | `C1ZB.A0O(i)` | `i == 42 \|\| i == 43` |
| عارض مخصص (نص/صوت) | `ViewOnceViewerActivity`، `ViewOnceTextFragment`، `ViewOnceAudioFragment` | Activity منفصل، دائمًا `FLAG_SECURE` |
| عارض مشترك (صورة/فيديو) | `MediaViewFragment` / `MediaViewMenu` | عارض الوسائط العادي، `FLAG_SECURE` فقط عندما يكون `C1ZB.A0O` صحيحًا |
| صفحات التوضيح التعليمية | `ViewOnceNuxBottomSheet`، `ViewOnceSecondaryNuxBottomSheet` | شرح يظهر مرة واحدة للمرسل/المستلم |
| منظّف الوسائط المقتبسة | `F43` ("QuotedMediaCleanupSerializationPostProcessor") | يحذف بايتات الوسائط من اقتباس رسالة عرض لمرة واحدة، العلم **25572** |

---

## 2. وسم Proto

### 2.1 الحقل المضمَّن (found)

```text
ImageMessage.viewOnce         = 25  (bool)
VideoMessage.viewOnce         = 20  (bool)
AudioMessage.viewOnce         = 21  (bool)
ExtendedTextMessage.viewOnce  = 30  (bool, VIEW_ONCE_FIELD_NUMBER)
```

كل منها قيمة منطقية بسيطة على رسالة الوسائط/النص العادية؛ لا حاجة لحاوية منفصلة لحملها. تأكيد ذلك من خلال قراءة جداول الحقول المُولَّدة لـ `C30612DTg` (صورة)، `C30614DTi` (فيديو)، `DTX` (صوت)، `C30613DTh` (نص ممتد).

### 2.2 رسالة الغلاف (found)

`viewOnceMessage` (**37**)، `viewOnceMessageV2` (**55**) و `viewOnceMessageV2Extension` (**59**) على `Message` كلها من النوع `BD2`، و `BD2` لها حقل واحد فقط، `message` **1**، وهو بذاته `Message`. أسماء الحقول الثلاثة تُفكَّك إلى الفئة نفسها بالضبط — إنها شكل الغلاف نفسه المستخدَم ثلاث مرات لثلاثة أجيال من البروتوكول:

```java
public final class BD2 extends GeneratedMessageLite {
    public static final int MESSAGE_FIELD_NUMBER = 1;
    public C30628DTw message_;   // a full nested Message
}
```

### 2.3 المضمَّن مقابل الغلاف: العلم 8784 (found)

كل معالج لكل نوع (`C34670F2r` الصورة، `C34671F2s` الفيديو، `F33` النص، `C34669F2q` الصوت) يبني الشيء نفسه مرتين ويختار أحدهما حسب علم:

```java
boolean zA15 = this.A00.A15(8784);
...
if (zA15) {
    dp5.A0R(c30612DTg);                 // inline viewOnce=true directly on the outer Message
    return;
}
dp5A0f.A0R(c30612DTg);                  // same media message, but inside the BD2 wrapper
BD2 bd2A0Q = ...;
c30628DTwA0j.viewOnceMessageV2_ = bd2A0Q;
```

مع تفعيل العلم، لا يُصدر 2.26.41.6 أبدًا غلافًا لرسالة عرض لمرة واحدة مُركَّبة محليًا؛ معالجات الاستقبال `CM7` في الفئات نفسها تنظر فقط إلى العلم المضمَّن (`c30612DTg.bitField0_ & ... && c30612DTg.viewOnce_`)، لا إلى حقول الغلاف — فك الغلاف إلى الشكل المضمَّن خطوة عامة منفصلة (2.4).

### 2.4 فك الغلاف العام (found)

جدول ثابت (`AbstractC33204EdH.A00`، 35 مُدخَلًا) يربط شرط "هل يوجد هذا الغلاف" بمستخرج "احصل على `Message` الداخلية" لكل غلاف توافق مستقبلي يعرفه العميل، بما في ذلك `ephemeralMessage` (غلاف الرسائل المؤقتة)، `viewOnceMessage`، `viewOnceMessageV2`، `viewOnceMessageV2Extension`، `editedMessage`، `documentWithCaptionMessage`، `botInvokeMessage`، `groupStatusMessage`، وغيرها. `C34748F5r` (التحقق من native-flow/`<biz>`، `AbstractC33204EdH.A00`) يتكرر عبر هذا الجدول حتى عمق 10 ليجد المحتوى القابل للتصنيف بصرف النظر عن عدد الأغلفة المحيطة به:

```java
for (EQR eqr : AbstractC33204EdH.A00) {
    if (hasWrapper(c30628DTw, eqr) &&
        A00(..., unwrap(c30628DTw, eqr), i + 1) != C02U.A00) {
        return result;
    }
}
```

`ephemeralMessage` وأغلفة العرض لمرة واحدة الثلاثة مُدخَلات نظيرة في هذا الجدول — نفس الآلية هيكليًا، لذا يمكن من حيث المبدأ تضمين رسالة عرض لمرة واحدة داخل غلاف رسائل مؤقتة، أو بجانبه. هذا يطابق قائمة Baileys الخاصة `getFutureProofMessage()` في `message-inspect.js`، التي تُعدِّد نفس مجموعة أسماء حقول الغلاف تمامًا.

---

## 3. أنواع الرسائل وواجهة الوسم

| النوع | فئة الوسائط | المعالج | Fragment/Activity |
|------|-------------|---------|--------------------|
| **42** | `DdP` (صورة) | `C34670F2r` | `MediaViewFragment` (عارض الصورة/الفيديو المشترك) |
| **43** | `C30972DdZ` (فيديو) | `C34671F2s` | `MediaViewFragment` |
| **78** | `C31208Dhd` (نص) | `F33` | `ViewOnceTextFragment` داخل `ViewOnceViewerActivity` |
| **82** | `C30963DdH` (صوت/ptt) | `C34669F2q` | `ViewOnceAudioFragment` داخل `ViewOnceViewerActivity` |

كل الفئات الأربع تُنفِّذ `InterfaceC24513Ahd`، الوسم الوحيد الذي يفحصه بقية العميل ("هل هذه رسالة عرض لمرة واحدة") بدل تكرار فحص الأنواع الأربعة في كل مكان. `C1ZB.A0O(i)` (`i==42 || i==43`) هو الفحص الأضيق الخاص بالصورة/الفيديو فقط المستخدَم حيث يحتاج `MediaViewFragment` المشترك إلى تمييز صورة/فيديو العرض لمرة واحدة عن كل ما يعرضه أيضًا.

مجموعة الأنواع `{42,43,78,82}` تتكرر حرفيًا في عدة مواقع استدعاء مستقلة وُجدت في هذا الإصدار: منتج `<meta view_once="true">` (القسم 6.1)، جدول البحث عن أسماء الأنواع (`AbstractC32316E9h`: `"viewOnceImage"`=42، `"viewOnceVideo"`=43، `"viewOnceAudio"`=82)، ودوال مساعدة `C1ZB` لضبط إمكانية الحفظ/العرض.

---

## 4. التطبيق من جهة العميل

### 4.1 حجب لقطة/تسجيل الشاشة (found)

`C66572s0.A00(Window)` دالة مساعدة من سطر واحد:

```java
public final void A00(Window window) {
    if (window != null) {
        window.addFlags(8192);   // WindowManager.LayoutParams.FLAG_SECURE
    }
}
```

`8192` (`0x2000`) هي القيمة الرقمية الخام لـ `FLAG_SECURE`؛ تستخدم الشيفرة المفكَّكة الثابت الرقمي لا الاسم الرمزي، فالبحث النصي عن `FLAG_SECURE` لا يجد شيئًا — يجب مطابقة الثابت بالقيمة. يحجب `FLAG_SECURE` النافذة في لقطات الشاشة، وفي صورة مصغرة التطبيقات الأخيرة، وخلال تسجيل/عرض الشاشة على مستوى نظام التشغيل؛ وهو ليس كشفًا خاصًا بـ WhatsApp، بل علم النافذة الآمنة القياسي في أندرويد.

موقعا استدعاء:

| موقع الاستدعاء | الشرط | النطاق |
|-----------|-------|-------|
| `MediaViewFragment` (عارض الوسائط العام) | `C1ZB.A0O(i)` أي `i==42 \|\| i==43` | يُطبَّق فقط عندما تكون الرسالة المعروضة صورة/فيديو عرض لمرة واحدة؛ وإلا لا يُؤمَّن عارض الوسائط العادي |
| `ViewOnceViewerActivity.onCreate` | غير مشروط | هذا الـ Activity لا يُشغَّل إلا لنص (78) أو صوت (82) عرض لمرة واحدة، فكل مثيل منه مؤمَّن |

التأثير الصافي: فتح أي من الأنواع الأربعة للعرض لمرة واحدة يضبط `FLAG_SECURE` على نافذة الاستضافة طوال مدة فتحها؛ إغلاق العارض (تفكيك الـ fragment/activity) يحذف النافذة، مما يسقط العلم معها. لم يُعثر على دليل على آلية *كشف* لقطة الشاشة (مثل `FileObserver` على `Pictures/Screenshots` أو مراقب محتوى `MediaStore`)؛ الحماية منع على مستوى نظام التشغيل، لا كشف بعد الحدث.

### 4.2 لا إعادة توجيه / مشاركة / حفظ (found)

يبني `ViewOnceViewerActivity.onCreateOptionsMenu` أربعة عناصر قائمة فقط بالضبط — معلومات، تفريغ نصي (للصوت فقط)، حذف، إبلاغ — ولا غيرها؛ لا يوجد عنصر إعادة توجيه أو مشاركة أو حفظ أو نسخ في تلك القائمة أصلًا. في `MediaViewMenu` المشترك (المستخدَم لصورة/فيديو العرض لمرة واحدة عبر عارض الوسائط العادي)، تُحسَب عدة متغيرات محلية منطقية لظهور عناصر القائمة باستثناء صريح `instanceof InterfaceC24513Ahd`، مثل:

```java
if (i6 == 2 && !c36911dGA1I21.element && ... && !(abstractC34931a2 instanceof InterfaceC24513Ahd)) {
    z14 = !C0DZ.A0X(c0df);     // forward-related menu flag, left false (hidden) for view-once
}
...
z16 = abstractC34931a2 instanceof InterfaceC24513Ahd;
if (!z16) {
    z17 = !AbstractC24760wu.A07(c0df);   // another gated flag, defaults false for view-once
}
```

بما أن كل علم تكون قيمته الافتراضية `false` ولا يُعيَّن قيمة قابلة للاستخدام إلا في الفرع غير الخاص بالعرض لمرة واحدة، تبقى عناصر القائمة المقابلة مخفية لرسائل `InterfaceC24513Ahd`. يُطبَّق التقييد في طبقة واجهة المستخدم (بناء القائمة)، لا بحذف الوسائط الأساسية من القرص المحلي قبل فتح العارض لها.

### 4.3 لا يمكن للمرسل إعادة فتح وسائطه الخاصة (found)

يفترض `DYM` (مكوّن صف المحادثة لوسائط العرض لمرة واحدة):

```java
C00K.A0C(false, "ConversationRowViewOnceMedia/senders can not view their own media");
```

على المسار الذي سيستخدمه صف العرض لمرة واحدة الخاص بالمرسل لإعادة فتح المحتوى — أي أن الثابتة "لا يحصل المرسل أبدًا على معالج فتح فعّال لرسالته الخاصة من نوع العرض لمرة واحدة" مُطبَّقة كتأكيد (assertion) صارم بدل إخفاء شرطي في واجهة المستخدم.

### 4.4 الاقتباس يُجرِّد الوسائط (found)

يعيد `F43` ("QuotedMediaCleanupSerializationPostProcessor"، محكوم بالعلم **25572**) كتابة `imageMessage` / `videoMessage` / `documentMessage` / `audioMessage` للرسالة المقتبسة قبل إرفاقها كـ `contextInfo.quotedMessage` لرسالة *جديدة* صادرة: ينسخ الحقول غير المتعلقة بالمحتوى (نوع mime، التعليق، الأبعاد، الصورة المصغرة، بت `viewOnce` نفسه) ولكنه يحذف `mediaKey`، و`fileSha256`/`fileEncSha256`، و`directPath`. لذا لا يمكن لاقتباس رسالة عرض لمرة واحدة تهريب مفتاح الوسائط الأصلي إلى رد؛ يُظهر الاقتباس البيانات الوصفية فقط.

### 4.5 صفحات التوضيح التعليمية (found)

تُعرَض `ViewOnceNuxBottomSheet` مرة واحدة لكل دور (مرسل/مستلم — متابَع بمفاتيح UXCam `ephemeral_view_once` / `ephemeral_view_once_receiver`) في أول مرة يرسل/يستقبل فيها كل طرف رسالة عرض لمرة واحدة، بنص مأخوذ مباشرة من `res/values/strings.xml`:

| معرّف السلسلة | النص |
|-----------|------|
| `str4e56` | "View once messages give you more privacy" |
| `str4e55` | "For added privacy, the recipient can't share, forward, copy, save, or take a screenshot of it." |
| `str4e68` / `str4e5d` / `str4e7b` | أشكال مختلفة لكل نوع: "This is a view once photo/message/video so it's more private" |
| `str4e69` / `str4e6a` / `str4e5c` | "Also, you can't share, forward, copy, save, or take a screenshot of it." |
| `str4e63` / `str4e64` | "View once photo, expired" / "View once photo, opened" (نفس النمط للفيديو/الصوت/النص) |

زوجا السلسلة "expired"/"opened" لكل نوع (صورة، فيديو، صوت، نص) هما الوجه الظاهر للمستخدم لعمود `state` المحلي (القسم 5).

---

## 5. التخزين المحلي وآلة الحالة

### 5.1 الجدول (found، `C199158dT`)

```sql
-- message_view_once_media(message_row_id, state)
SELECT state FROM message_view_once_media WHERE message_row_id = ?     -- GET_VIEW_ONCE_STATE_BY_MESSAGE_ROW_ID_SQL
UPDATE message_view_once_media SET state = ? WHERE message_row_id = ?  -- UPDATE_VIEW_ONCE_SQL
INSERT INTO message_view_once_media (message_row_id, state) VALUES (?, ?)  -- INSERT_VIEW_ONCE_SQL
```

صف واحد لكل رسالة عرض لمرة واحدة، مستقل عن جدولي `message` و `message_media` العامين (اللذين لا يزالان يحملان بيانات الصف/ملف الوسائط المشتركة مع الرسائل العادية).

### 5.2 الحالات (found لقيم الصف، تعيين الأسماء مستنتج جزئيًا)

| الانتقال | الشيفرة | المحفِّز |
|------------|------|---------|
| إنشاء الصف | `A02` (`BDk()` على FMessage، القيمة عند الإنشاء) | إرسال/استقبال الرسالة؛ القيمة الابتدائية هي ما يُرجعه FMessage — يتوافق مع "0 = غير مفتوحة" ولكن لم يُعثر على ثابت مسمّى |
| تمييزها كمفتوحة | `A03`: `state = 1` | تصل حالة الرسالة (`B6u()`) إلى **8** أو **9** أو **10** (رموز حالة متعلقة بالتنزيل/القراءة؛ الأسماء الدقيقة غير محلولة) |
| قراءة بلا صف | قيمة احتياطية `i = 2` في `A01` | لا يُرجع `GET_VIEW_ONCE_STATE...` أي صف؛ تعامل الشيفرة هذه الحالة كأن الرسالة قد انتهت صلاحيتها فعلًا |

فـ **1** = "مفتوحة" مؤكَّدة (موقع استدعاء مسمّى)؛ و **2** هي القيمة الاحتياطية لعدم وجود سجل/انتهاء الصلاحية؛ وتوجد قيمة ابتدائية/"غير مفتوحة" لكنها لم تُثبَّت على قيمة حرفية في هذا الإصدار.

### 5.3 الحذف (found)

نفس فئة `EphemeralUpdateRunnable` التي تُنهي صلاحية الرسائل المؤقتة (نوع المهمة 0، جدول `message_ephemeral`) وإضافات أسرار الرسائل (نوع المهمة 4، جدول `message_add_on`) تُشغِّل أيضًا نوع المهمة **3**، المسجَّل كـ `ViewOnceMessageStore/getViewOnceMessagesToDelete`:

```sql
SELECT message.* FROM message_view_once_media AS view_once
  JOIN message AS message ON view_once.message_row_id = message._id
  JOIN message_media AS message_media ON message_media.message_row_id = message._id
WHERE message_media.file_size IS NOT NULL
  AND message_media.file_size IS NOT 0
  AND message.from_me = 0
  AND view_once.state IN (1, 2)
LIMIT ?
```
<sub>(قائمة أعمدة مبسَّطة؛ `GET_EXPIRED_VIEW_ONCE_MESSAGES_SQL`)</sub>

بقراءة حرفية: المهمة لا تستهدف إلا وسائط العرض لمرة واحدة *المستقبَلة* (`from_me = 0`) التي لا يزال لها ملف على القرص (`file_size` موجود وغير صفري) وحالتها `1` (مفتوحة) أو `2` (القيمة الاحتياطية نفسها لـ "بلا صف"/منتهية الصلاحية). تُحرِّر المهمة ملف الوسائط المحلي للصفوف المطابقة لهذا الاستعلام؛ لا تحذف صف الرسالة نفسه (يبقى الصف، حاملًا تسمية "مفتوحة"/"منتهية" من واجهة المستخدم في 4.5). وسائط العرض لمرة واحدة **المُرسَلة** (`from_me = 1`) غير مشمولة في هذا الاستعلام — يتوافق هذا مع عدم السماح للمرسل أبدًا بإعادة فتحها (4.3)، لكن لم يُعثر على تنظيف مماثل لنسخة المرسل الخاصة؛ الاحتفاظ بها/حذفها **unknown**.

### 5.4 دورة حياة مفتاح الوسائط/التشفير (مرتبطة، غير مكرَّرة)

تستخدم وسائط العرض لمرة واحدة خط أنابيب الوسائط العادي من البداية إلى النهاية — نفس جدول `MmsType`، نفس اشتقاق المفتاح HKDF-80، نفس غلاف AES-CBC+HMAC، نفس عناوين الرفع/التنزيل؛ لا يوجد صف `MmsType` منفصل خاص بـ "العرض لمرة واحدة". انظر [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) الأقسام 3-5 للتشفير، والقسم 12 من ذلك التقرير للملاحظات الخاصة بالعرض لمرة واحدة (تأكيد عدم إمكانية رؤية المرسل، وسم سجلّ حذف الصورة المصغرة). ما إذا كان الخادم يحذف أو يعلِّم الكائن المرفوع بشكل مستقل بعد أول تنزيل فهذا **unknown** من هذا التحليل الساكن — ضمان جهة العميل هو حذف الملف المحلي في 5.3، لا عقد خادم يمكن للعميل مراقبته.

---

## 6. "العرض لمرة واحدة غير متاح" / الإشارة بين الأجهزة

### 6.1 حالة السلك `unavailable[type="view_once"]` (تصحيح لملاحظة بحثية سابقة)

ملاحظة بحثية سابقة (2.26.35.2) تتبّعت الزوج الحرفي الصادر `view_once`/`true` إلى دالة مسجَّلة كـ `AppDataManager/contributeMetaAppData` وتركت مفتوحًا ما إذا كانت تلك الدالة تبني عقدة كاملة أو تساهم فقط في البيانات الوصفية. في 2.26.41.6 نفس وسم السجلّ (`"AppDataManager/contributeMetaAppData type="`) **ليس** منتج `view_once`: إنه ينتمي إلى فرع مختلف غير متصل من `F6K` (بانِي عقدة `<meta>` العام) يطبع سمة `appdata` حرة الصيغة لرسائل البوت/الإضافات (`FZF.AVN()`). سمة `view_once` الفعلية في هذا الإصدار تُبنى قبل بضعة أسطر في *نفس* دالة `F6K`، بشكل مستقل عن ذلك السطر من السجلّ:

```java
if (c08j2.A15(11282) && (i == 42 || i == 43 || i == 82 || i == 78)) {
    EZV.A00(ezv, "view_once", "true");
}
```

هذا يُصدر `<meta view_once="true">` كطفل/سمة لعقدة `<meta>` التابعة لحالة `<message>` الصادرة (لا طفل `<unavailable type="view_once">` الذي تصفه الملاحظة البحثية و Baileys/whatsmeow). يمكن للأمرين أن يكونا صحيحين في آن واحد: `<meta view_once="true">` هو وسم المرسل الخاص بحالته الصادرة بأن هذه الرسالة عرض لمرة واحدة؛ `<unavailable type="view_once">` عقدة *مختلفة*، تُلاحَظ فقط في جانب الاستقبال/الويب عندما لم يُوزَّع نص مشفَّر إلى ذلك الجهاز. لا يمكن للتحليل الساكن لتطبيق أندرويد (الذي لا دور له هنا للويب/الأجهزة المرتبطة) أن يُظهر أي جانب يُجمِّع تلك العقدة الثانية؛ هذا التقرير لا يُغيّر الاستنتاج السابق متوسط-عالي الثقة بأنها مُنتَجة من الخادم أو مطبَّعة من جانب الخادم من حالة توزيع المرسل. تدعم Baileys جانب الاستقبال بحرفية *أكثر تحديدًا* من الحرفية العامة: يفحص `src/Socket/messages-recv.js` ما إذا كان `unavailableType === 'view_once_unavailable_fanout'` (إلى جانب `bot_unavailable_fanout`، `hosted_unavailable_fanout`) لتقرير تخطي طلب إعادة إرسال العنصر النائب عند الطلب، بينما يُطابق `src/Utils/decode-wa-message.js` بشكل منفصل الحرفية البسيطة `attrs.type === 'view_once'` على طفل `<unavailable>` لضبط `isViewOnce`/`StubType.VIEWED_ONCE`. هذان مساران شيفرة مختلفان لما عاملته الملاحظة البحثية السابقة كسلسلة واحدة.

### 6.2 رموز `view_once="read"`/`"write"` (رمز موجود، المستهلِك غير محلول)

الحرفيتان `view_once_read` و `view_once_write` موجودتان في جدول قاموس الحالة الثنائية لعميل أندرويد (`AbstractC40911lb`، قائمة المفردات السلكية الثابتة المستخدَمة لترميز الرموز المضغوط) — نفس نوع الجدول الذي يحمل `unavailable`، `enc`، `polltype`، إلخ. يقرأ `decode-wa-message.js` في Baileys قيمة `attrs.view_once` تكون `'read'` أو `'write'` على سمات مستوى `<enc>` ويخزّنها كـ `fullMessage.viewOnceType`. مجتمعةً، هذا يتوافق مع إشارة مزامنة "فُتحت فعلًا" لكل جهاز خاص بالمستخدم تنتقل مع غلاف الرسالة — من المحتمل أنها الطريقة التي تعرف بها أجهزة المستخدم المرتبطة الأخرى أن محتوى العرض لمرة واحدة فُتح فعلًا على جهاز واحد — لكن لم يُعثر في 2.26.41.6 على موقع استدعاء أندرويد *يضبط* أو *يستهلك* هذه السمة؛ سُجِّلت هنا كرمز سلكي موجود بمستهلك أندرويد غير محلول (**unknown**).

---

## 7. التفاعل مع الرسائل المؤقتة

العرض لمرة واحدة والرسائل المؤقتة (مدة صلاحية الرسالة لكل محادثة) علمان مستقلان متعامدان يمكن ضبطهما معًا على الرسالة نفسها:

- يستخدمان جدولين محليين منفصلين: `message_ephemeral` (المؤقتة، مفتاحها `expire_timestamp`) مقابل `message_view_once_media` (العرض لمرة واحدة، مفتاحها `state`).
- كلاهما تنتهي صلاحيته عبر مهام على نفس مُشغِّل `EphemeralUpdateRunnable` (نوع المهمة 0 للمؤقتة، نوع المهمة 3 للعرض لمرة واحدة، نوع المهمة 4 لإضافات أسرار الرسائل) — مسار جدولة/تنفيذ مشترك، وحالة وSQL مختلفان لكل ميزة.
- على مستوى proto، `ephemeralMessage` مُدخَل نظير في نفس جدول فك الغلاف العام الذي تحتويه أغلفة العرض لمرة واحدة الثلاثة (القسم 2.4): يمكن أن تُغلَّف رسالة كـ `ephemeralMessage{message: viewOnceMessage{message: imageMessage{...}}}` أو بالترتيب العكسي، ويسير فك الغلاف العودي في `C34748F5r` ودالة `getFutureProofMessage()` في Baileys عبر أي من الترتيبين.
- حذف الرسالة المؤقتة يزيل الرسالة كاملة بعد مدة صلاحية المحادثة بصرف النظر عن فتحها أم لا؛ حذف العرض لمرة واحدة يزيل *ملف الوسائط* فقط بعد فتح الرسالة (أو سقوطها في القيمة الاحتياطية 2)، ويترك صف الرسالة (المعروض الآن كـ "مفتوحة"/"منتهية") في مكانه. لذا فإن صورة عرض لمرة واحدة داخل محادثة مؤقتة تظل خاضعة لمدة صلاحية المحادثة فوق قاعدة الفتح-مرة-ثم-المحو الخاصة بوسائطها.

---

## 8. أعلام الميزات (المعرّفات كما قُرئت في مواقع الاستدعاء؛ الأسماء غير محلولة)

| المعرّف | النوع | يتحكم في |
|----|------|----------|
| **8784** | bool | إرسال وسائط العرض لمرة واحدة بالحقل المضمَّن فقط (مفعَّل) مقابل الحقل المضمَّن + الغلاف القديم (معطَّل) |
| **11282** | bool | إصدار `<meta view_once="true">` لأنواع الرسائل 42/43/78/82 |
| **25572** | bool | تجريد حقول الوسائط من رسالة عرض لمرة واحدة مقتبَسة (`F43`) |

(الأعلام التي تتحكم في خط أنابيب الوسائط المشترك — HKDF، الرفع/التنزيل، إعادة المحاولة — مُسردة في [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) القسم 16 ولا تُكرَّر هنا.)

---

## 9. Baileys (`baron-baileys-v2`، قراءة المصدر فقط، لم يُختبَر شيء)

| الموضوع | Baileys | Android 2.26.41.6 |
|-------|---------|---------------------|
| وسم جهة الإرسال | يُغلِّف دائمًا: `{ viewOnceMessage \| viewOnceMessageV2 \| viewOnceMessageV2Extension: { message } }` حسب خيار `viewOnceVersion` (`src/Utils/messages.js`) | يُغلِّف فقط عندما يكون العلم 8784 معطَّلًا؛ الافتراضي (8784 مفعَّل) يضبط حقل `viewOnce` المضمَّن على رسالة الوسائط/النص مباشرة، بلا غلاف |
| الغلاف يُستخدم أيضًا لغير الوسائط | يُستخدَم `viewOnceMessage` إضافة إلى ذلك لتحصين `buttonsMessage`/`templateMessage`/`listMessage`/`interactiveMessage` ضد التغييرات المستقبلية عند الإرسال (`src/Socket/messages-send.js`، `requiresViewOnce`) — لا علاقة له بخصوصية الحذف الذاتي | يُعاد استخدام نفس نوع الغلاف (`BD2`) في جدول فك الغلاف العام لـ `botInvokeMessage`، `editedMessage`، إلخ — نفس دور "الغلاف العام" مؤكَّد بشكل مستقل (2.4) |
| قائمة فك الغلاف العام | `getFutureProofMessage()` في `message-inspect.js`: `ephemeralMessage`، `viewOnceMessage`، `documentWithCaptionMessage`، `viewOnceMessageV2`، `viewOnceMessageV2Extension`، `editedMessage`، `groupMentionedMessage`، `botInvokeMessage`، ... | `AbstractC33204EdH.A00` (35 مُدخَلًا) — أسماء حقول الغلاف نفسها |
| معالجة الاستقبال لـ `unavailable` | فحصان حرفيان متمايزان: `attrs.type === 'view_once'` (يضبط `isViewOnce`) و `unavailableType === 'view_once_unavailable_fanout'` (يتخطى إعادة إرسال العنصر النائب) | منتج `<meta view_once>` من جهة العميل فقط (6.1)؛ عقدة `<unavailable>` نفسها مسار استقبال/جانب ويب، لم يُتابَع هنا |
| رمز القراءة/الكتابة `view_once` | يفكّ `attrs.view_once === 'read' \| 'write'` على سمات `<enc>` إلى `viewOnceType` | الرموز موجودة في قاموس السلك الخاص بالعميل؛ لم يُعثر على مستهلك أندرويد (6.2) |
| التحليلات | `WAM/constants.js`: `viewOnceMessagesSent` (16)، `viewOnceMessagesReceived` (17)، `viewOnceMessagesOpened` (18) | لم يُتابَع في هذا التقرير؛ انظر [WA_WAM_ANALYTICS.md](./WA_WAM_ANALYTICS.md) لآلية WAM عامةً |
| حجب لقطة الشاشة/إعادة التوجيه | غير مُطبَّق — Baileys مكتبة خلفية بلا واجهة مستخدم، بلا نافذة، بلا قائمة لتقييدها | `FLAG_SECURE` + حذف عناصر القائمة (4.1-4.2)؛ غير قابل للتكرار خارج واجهة أندرويد |
| الحذف المحلي بعد الفتح | غير منطبق — لا توجد لدى Baileys آلة حالة دائمة لعارض الوسائط؛ المستدعون مسؤولون عن تخزينهم الخاص | `message_view_once_media.state` + مهمة `EphemeralUpdateRunnable` نوع 3 (5.1-5.3) |

---

## 10. حالات الأخطاء / المزالق

| العارض | السبب | ملاحظة |
|---------|-------|------|
| وسائط العرض لمرة واحدة مفقودة عند إعادة فتح العارض | طبيعي: بلغت `state` القيمة 1 (مفتوحة) أو كان الصف غائبًا (القيمة الاحتياطية 2)، وحررت مهمة الحذف الملف فعلًا | ليس خللًا؛ هذا هو السلوك المقصود "فتح-مرة-ثم-محو" |
| وسائط العرض لمرة واحدة الخاصة بالمرسل لا تُفتح أبدًا من صف المحادثة | تأكيد `DYM` الصارم `senders can not view their own media` | بالتصميم، لا مسار خطأ |
| رد اقتباس لرسالة عرض لمرة واحدة لا يُظهر وسائط | يُجرِّد `F43` `mediaKey`/الـ hashes/`directPath` من الاقتباس، محافظًا فقط على التعليق/الأبعاد/الصورة المصغرة/بت `viewOnce` | متوقَّع؛ لا يمكن استخدام الاقتباس لاستخراج الوسائط الأصلية |
| عارض صورة/فيديو العرض لمرة واحدة يسمح بلقطات الشاشة في بعض الإصدارات ولا يسمح في أخرى | لا يُطبَّق `FLAG_SECURE` إلا عبر `C1ZB.A0O(i)` (الأنواع 42/43)؛ أي تراجع في ذلك المفتاح (مثل مسار شيفرة يفتح العارض المشترك لعنصر عرض لمرة واحدة من دون المرور عبر الاستدعاء المُحكَم) سيُسقط الحماية بصمت | موقع المفتاح موثَّق عند `MediaViewFragment` السطر ~3120 (هذا الإصدار) |
| جهاز مرتبط يُظهر رسالة عرض لمرة واحدة كمفتوحة فعلًا دون أن يفتحها المستخدم هناك | مزامنة محتملة بين الأجهزة عبر رموز السلك `view_once="read"/"write"` (6.2) | الآلية غير مؤكَّدة على جانب أندرويد؛ مسجَّلة كغير معروفة |

---

## 11. التمييزات الأساسية

| هذا | وليس هذا |
|------|----------|
| الحقل المنطقي `viewOnce` على `ImageMessage`/`VideoMessage`/`AudioMessage`/`ExtendedTextMessage` | الغلاف القديم `viewOnceMessage`/`viewOnceMessageV2`/`viewOnceMessageV2Extension` حول الرسالة نفسها |
| `viewOnceMessage` (`BD2`) مُستخدَم للخصوصية (الحذف الذاتي) | نوع الغلاف `BD2` نفسه يُعاد استخدامه كغلاف تحصين عام للإرسال بالأزرار/القالب/القائمة/التفاعلية (Baileys) ولـ `botInvokeMessage`/`editedMessage` على أندرويد |
| `message_view_once_media.state` (محلي، لكل رسالة، تتبع الفتح/الانتهاء) | `message_ephemeral.expire_timestamp` (محلي، لكل رسالة، مدة صلاحية المحادثة المؤقتة) — جدولان مستقلان، مهمتان مستقلتان، نفس المُشغِّل |
| `<meta view_once="true">` — مُصنِّف جهة المرسل على الحالة الصادرة | `<unavailable type="view_once">` — عقدة مختلفة تُلاحَظ في جانب الاستقبال/الويب عندما لم يصل أي نص مشفَّر إلى ذلك الجهاز |
| `FLAG_SECURE` على نافذة العارض (*منع* لقطة الشاشة/التسجيل) | استدعاء رجوع *كشف* لقطة شاشة — لم يُعثر على آلية كهذه |
| حذف *ملف* الوسائط المحلي بعد الفتح | حذف *صف* الرسالة — يبقى الصف، موسومًا بـ "مفتوحة"/"منتهية" |
| العرض لمرة واحدة (محو الوسائط بعد فتحة واحدة) | الرسائل المؤقتة (إزالة الرسالة كاملة بعد مدة صلاحية على مستوى المحادثة) — متعامدان، يمكن دمجهما |

---

## 12. التدفق الكامل (صورة عرض لمرة واحدة، محادثة فردية)

```
[Sender]
   │ pick photo, mark "view once" in composer
   │ ImageMessage.viewOnce = true          (flag 8784 on: inline only)
   │ upload via normal media pipeline (WA_MEDIA_UPLOAD.md)
   │ flag 11282 on, type==42 → <meta view_once="true">
   ▼
[Server]  relays the E2E-encrypted stanza; cannot read viewOnce (it's inside the ciphertext)
   │
   ▼
[Receiver]
   │ decrypt → ImageMessage.viewOnce == true, message type 42 (DdP)
   │ INSERT message_view_once_media(message_row_id, state=<initial>)
   │ thumbnail shown in the conversation row; sender-side row asserts "can not view own media"
   │
   ├── user taps to open ──► MediaViewFragment, C1ZB.A0O(42) == true
   │                          → window.addFlags(FLAG_SECURE)
   │                          → forward/share/save menu items hidden (InterfaceC24513Ahd)
   │                          → status reaches 8/9/10 → state = 1 ("opened")
   │                          → window closed, FLAG_SECURE drops with it
   │
   ▼
[EphemeralUpdateRunnable, job type 3]
   │ SELECT ... FROM message_view_once_media JOIN message_media
   │   WHERE from_me=0 AND file_size IS NOT NULL AND state IN (1,2)
   ▼
local media file deleted; row kept, UI shows "View once photo, opened"
```

---

## 13. مجاهيل

| العنصر | الحالة |
|------|-------|
| الثوابت المسمّاة لحالة `state` 0 (ابتدائية) والمعنى الدقيق المشترك بين 2 (القيمة الاحتياطية لعدم وجود صف) و "منتهية" | فقط 1 ("مفتوحة") له موقع استدعاء مسمّى؛ بقية الحالات مستنتجة من القيمة الاحتياطية وسلاسل واجهة المستخدم |
| رموز الحالة 8/9/10 التي يستهلكها `C199158dT.A03` لتفعيل "مفتوحة" | غير محلولة إلى ثوابت مسمّاة |
| الاحتفاظ بنسخة **المرسل** الخاصة من وسائط العرض لمرة واحدة المُرسَلة/حذفها | مهمة الحذف تستهدف فقط `from_me = 0`؛ لم يُعثر على تنظيف مماثل من جهة المرسل |
| حذف/وسم الخادم للكائن المرفوع بعد أول تنزيل | لا يمكن مراقبته من التحليل الساكن لجهة العميل |
| بناء عقدة `<unavailable type="view_once">` (عنصر نائب من العميل مقابل بناء من الخادم) | غير محلول؛ محمول من بحث سابق، لم يُحَل من جديد هنا |
| مستهلك أندرويد لرموز السلك `view_once="read"/"write"` | وجود الرمز مؤكَّد في جدول القاموس؛ لم يُعثر على موقع استدعاء |
| ما إذا كان `FLAG_SECURE` يُطبَّق على كل مسار شيفرة يمكنه عرض محتوى عرض لمرة واحدة (مثل معاينات الإشعارات، الـ widget، Wear) | لم يُفحَص إلا مساري `MediaViewFragment` و `ViewOnceViewerActivity` |
