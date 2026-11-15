<!-- src-sha1: 73855f4f8148d9b0ef853f43cef4adbe0cb996a5 -->
# WhatsApp اسم المستخدم — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** فحص/ضبط/حجز/حذف اسم المستخدم، مفتاح اسم المستخدم (PIN)، العلاقة بـLID، الخصوصية والظهور، عمليات w:mex GraphQL (doc_ids، المتغيرات، الاستجابات)، الإشعارات، بحث USync، قواعد التحقق، أعلام الميزات، ملاحظات Baileys

---

## 1. ما هو اسم المستخدم (تقنياً)

اسم المستخدم مُعرِّف من جهة الخادم مرتبط بحساب، يُستخدَم لإمكانية الوصول إلى جهة اتصال دون كشف رقم الهاتف. كل العبارات تحليل ساكن للـAPK المفكَّك. المستوى: **found** = مقروء في الكود أو الموارد، **inferred** = مُستنتَج من الكود، **unknown** = غير محسوم.

تُبنى الميزة على ثلاث طبقات:

| الطبقة | النقل | تُستخدَم لـ |
|-------|-----------|----------|
| إدارة الذات | IQ من نوع `w:mex`، GraphQL دائم (إعداد `whatsapp-android-mex`) | الفحص، الضبط/الحجز/الحذف، الجلب، ضبط/حذف المفتاح (PIN)، الفحص المتعدد |
| البحث عن الآخرين | USync (`xmlns="usync"`) ونسخة MEX `UsyncQuery` | حل `@username` (+ المفتاح) إلى LID، جلب اسم مستخدم JID معروف |
| الدفع | إشعارات MEX | `UsernameSetNotification`، `UsernameUpdateNotification`، `UsernameDeleteNotification` |
| عبر الأجهزة | مزامنة حالة التطبيق (`SyncActionValue`) | `username_chat_start_mode`، `lid_contact_action` (يحمل `username`) |

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| مدير اسم المستخدم | `C122815Lj` | استدعاءات `UsernameGet`، `UsernameSet`، تحديث الحالة المحلية، خطّاف تحديد المعدَّل |
| فحص التوافر | `C67402tT` | استدعاء `UsernameCheck` + تعيين الاستجابة |
| الفحص المتعدد | `C76333Kg` | `UsernameCheckMulti`، أجزاء من 10 |
| واجهة المفتاح | `MexUsernamePinProtocolApi` | `UsernamePinSet` (ضبط/حذف المفتاح) |
| الحالة/التفضيلات المحلية | `C5Q8` | `username_reservation_state`، `username_pin`، `is_username_revoked` |
| تعداد الحالة | `C4DU` | `UNSET`، `RESERVED`، `ACTIVATED`، `CREATED` |
| وضع الأهلية | `C224069kP.A00()` ← `C9SR` | `CREATION`، `RESERVATION`، `COMPANION_READ_ONLY`، `DISABLED` |
| مخزن تحديد المعدَّل | `C67942uO` | تأخير تصاعدي بعد 429 / 503 / 529 |
| المُحقِّق المحلي | `C82003fB.A04`، `C1187754z` | الطول، مجموعة الأحرف، قواعد النقطة، التعبير النمطي |
| مُحقِّق المفتاح | `C1176550d` (+ `AbstractC111284pZ`) | شكل المفتاح |
| نموذج عرض إدخال المفتاح | `UsernamePinEntryViewModel` | إرسال مفتاح لاسم مستخدم خارجي |
| عميل USync | `C23638AId` (`querySyncUsernameWithErrorInfo`)، `C18670m9` | باني/مُحلِّل stanza usync الكلاسيكي |
| MEX USync | `C229259vZ`، `O0F` | `UsyncQuery` بـ`include_username` |
| معالِجات الإشعارات | `C49822Lvi`، `C49821Lvh`، مجهول `X.2YG` في `AbstractC20380p4` | الضبط/الحذف/التحديث |

التسمية: الاسم الظاهر للمستخدم لـPIN هو **مفتاح اسم المستخدم** (سلاسل "Username key"، "Add a username key to control who can contact you"). السلك والكود يقولان `pin`.

---

## 2. عمليات MEX (doc_ids)

### 2.1 أين تعيش قيم doc_id

قيم doc_id ليست سلاسل حرفية في `java_src`. يرسل العميل اسم العملية (`"UsernameSet"`، ...) باسم الإعداد `"whatsapp-android-mex"` (found، `C16880is`). يُقرأ المعرّف العددي من `assets/whatsapp-android-mex_client_persist_ids.json`: يُخطِّط `EnumC17010j7.WHATSAPP_ANDROID_MEX` إلى ذلك الملف، يُعيد `C17040jA.CMg(op)` حقل `doc_id`، و`AGb(op)` حقل `client_doc_id` (found). أي من الوصولين يُغذِّي سمة `query_id` لم يُتعقَّب حتى النهاية (unknown)؛ التقاطات سابقة على 2.26.26.4 تُظهر `query_id` يساوي `doc_id`.

قيم doc_id أدناه **found** في موارد 2.26.41.6:

| العملية | doc_id | النوع | موقع الاستدعاء | صنف الاستجابة |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | لا شيء مُعثور عليه | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

ملاحظات:
- `UsernameGetRecommendationsQuery`: الاسم يظهر فقط في JSON الموارد. لا صنف في `java_src` يشير إليه بسلسلة (found). المتغيرات والاستجابة غير معروفة.
- أسماء الإشعارات الثلاثة (`UsernameSetNotification`، `UsernameUpdateNotification`، `UsernameDeleteNotification`) لا إدخال لها في موارد معرّفات الديمومة. إنها أنواع إشعارات، لا طلبات (انظر 7).
- يحمل مورد الموارد `operation_name_hash`، `operation_text_hash` و`client_doc_id` لكل عملية. مثال `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 الغلاف

مبني في `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| الحقل | القاعدة (الكود) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | `get` لكل عملية، بما فيها الطفرات |
| سمة `query_id` | تُضبَط فقط إذا كانت من 1 إلى 20 حرفاً |
| الجسم | JSON `{"queryId": ..., "variables": {...}}`، من 1 إلى 8448000 بايت |
| متغيرات فارغة | `C16770ig.A03(k, null)` و`A02(k, null)` تتجاوز المفتاح، فقيمة غائبة تعني أن المفتاح غير مُرسَل |

لا تُستنسَخ stanzas السلك لجلسات حية هنا؛ هذا البناء حُلِّل ساكناً فقط.

---

## 3. العمليات بالتفصيل

### 3.1 UsernameCheck

المتغيرات (found، `C67402tT.A00`):

| المتغير | النوع | الشرط |
|----------|------|-----------|
| `username` | string | دائماً |
| `include_suggestions` | bool | دائماً (تُمرِّر الواجهة `false` في مسار الفحص المُحدَّد النوع `C64H` الحالة 21) |
| `source` | string | فقط إذا غير فارغ |
| `session_id` | string | فقط إذا غير فارغ |

تعيين `source` (`AbstractC78993Wd.A0U`): int 1 ← `FB`، 2 ← `IG`، 3 ← `USER_INPUT`، 4 ← `SUGGESTION`، غيرها ← null (لا تُرسَل).

مسار الاستجابة (found، فرع `C77183Np` الافتراضي): `data.xwa2_username_check`

| الحقل | النوع | الاستخدام |
|-------|------|-----|
| `result` | تعداد `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `INVALID`، `SUCCESS` |
| `suggestions` | list<string> | تُقرأ فقط عند `INVALID` |
| `rejection_reasons` | قائمة `C4G8` | تُقرأ فقط عند `INVALID` |
| `suggestions_eligible` | bool | تبقى `true` افتراضياً عندما يكون الحقل فارغاً |

قيم `C4G8` (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `ALREADY_TAKEN`، `REQUIRE_FB_ACCOUNT_LINKING`، `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`، `REQUIRE_IG_ACCOUNT_LINKING`، `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

التعيين: `SUCCESS` ← `C76283Kb` (متاح)؛ `INVALID` ← `C76303Kd` (غير متاح، يحمل الاقتراحات + الأسباب)؛ `UNSET` ← لا فرع يُعيِّن نتيجة (يحصل رد النداء على المتغير السابق/الفارغ؛ السلوك غير معروف). تأخير تصاعدي محلي نشط ← `C76293Kc` (خطأ برمز تحديد معدَّل من التفضيلات، انظر 5.3)؛ رد نداء فشل الطلب نفسه لم يُقرأ.

تُحرِّك أسباب الرفض نص ربط الحساب ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center"، `C82003fB`). في `C82003fB` أي سبب غير `UNSET` يُحفِّز مسار خطأ محلي برمز 40601 (`A08(40601L)`)؛ قائمة فارغة أو تحتوي `UNSET` فقط تُظهر "Username isn't allowed." مسار التحكم الدقيق حول الحلقة مُفكَّك جزئياً فقط (مستنتج).

### 3.2 UsernameCheckMulti

| المتغير | النوع | ملاحظات |
|----------|------|-------|
| `usernames` | **list<string>** | مصفوفة عبر `A00.A0B("usernames", list)`؛ يُصنِّفه فهرس doc_id كـ`str`، لكن الكود يرسل قائمة |

التجزيء (`C76333Kg.AG5`): تُقسَّم القائمة إلى أول 10 والباقي؛ تُعالَج البقية بعد تأخير علم **29327** (الافتراضي 60، الوحدة غير محسومة). قائمة فارغة تُعيد خريطة فارغة دون طلب.

مسار الاستجابة `data.xwa2_username_check_multi.results[]` (found): كل إدخال يحمل `username` و`response.result` (نفس `EnumC59782gh`). التعيين: `SUCCESS` ← متاح، `INVALID` ← غير متاح (لا اقتراحات، `suggestions_eligible=false`)، أي شيء آخر ← خطأ. الأسماء الغائبة عن النتيجة تُوسَم كخطأ.

المستهلك: `UsernameAvailabilityCache` يخزِّن `EnumC59192fk` (`UNKNOWN`، `AVAILABLE`، `UNAVAILABLE`) لكل اسم. الغرض (جلب مسبق لاقتراحات اسم مستخدم Facebook/Instagram، سلسلة `foa_username_prefetch_cache`) مستنتج.

### 3.3 UsernameSet (الإنشاء/التغيير/الحجز/الحذف)

المتغيرات (found، `C122815Lj.A00`):

| المتغير | النوع | الشرط |
|----------|------|-----------|
| `username` | string | يُحذَف عندما يكون فارغاً (**الحذف**) |
| `reserved` | bool | يُرسَل دائماً |
| `session_id` | string | فقط إذا غير فارغ (`C1YW.A08`) |
| `source` | string | فقط إذا كان عدد المصدر غير فارغ (انظر 3.1) |
| `pin` | string | فقط إذا غير فارغ |

`reserved` محسوبة، لا ثابتة (found). المعطى `z` (القسر) = true يُعطي `false`. وإلا: الحالة الحالية `ACTIVATED` أو `CREATED` تُعطي `false`؛ الحالة الحالية `RESERVED` أو وضع الأهلية `RESERVATION` تُعطي `true`؛ كل الحالات الأخرى تُعطي `false`. فتُرسَل `reserved:true` فقط للحسابات في وضع الحجز أو التي تحمل حجزاً أصلاً.

الحذف نمط من نفس العملية: `username == null` ← وسم سجل `delete`، وإلا `set` (أيضاً في `MexUsernamePinProtocolApi` للمفتاح). باسم مستخدم فارغ لا يكون المفتاح `username` في المتغيرات (found).

حارس من جانب العميل: قبل الإرسال، إذا أفاد مخزن تحديد المعدَّل بتأخير تصاعدي نشط، يفشل الاستدعاء محلياً برمز `username_creation_rate_limit_error_code` ونص "rate limit expiration time not reached" (found، `C122815Lj.A03`).

معالجة النجاح (`C122815Lj.A01`، found):

| الشرط | الحالة المحلية المكتوبة (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| اسم مستخدم فارغ أو خالٍ | `UNSET`، تُمحى تفضيلة المفتاح |
| كانت `reserved` صحيحة | `RESERVED` |
| علم التفعيل | `ACTIVATED` |
| غير ذلك | `ACTIVATED` إذا كانت الحالة `ACTIVATED` والاسم يساوي الاسم المخزَّن، وإلا `CREATED` |
| عدد `source` هو 1 أو 2 | تفضيلة `username_set_via_account_linking` = (عدد == 2) |
| `pin` مُرسَل | تُحدَّث تفضيلة `username_pin` |
| علم القاصر | تفضيلة `is_teen_account` = true |

كتابة التفضيلة هي `Voip.REJECT_REASON_DECLINED`، وهي السلسلة الفارغة `""` في هذا البناء (found).

معالجة الخطأ (`C138725uA` الحالة 2):

| رمز شبيه بـHTTP | إجراء العميل |
|----------------|---------------|
| 429، 503، 529 | يُخزَّن التأخير التصاعدي (5.3) |
| 304 | يُعامَل كنجاح ("not modified")، تُحدَّث الحالة المحلية مع ذلك |
| لا اتصال (`C213639Bb`) | نتيجة `C4BO` "no network" |
| غيره | `C4BN(code, message)` |

### 3.4 UsernameGet

المتغيرات: لا شيء (يبني الاستدعاء مجموعة متغيرات فارغة، found، `C122815Lj.A02`). مُوسَم `@Deprecated`، استُبدِل بنسخة مُعلَّقة (suspend).

الاستجابة (found، `C138815uJ` الحالة 34): `data.xwa2_username_get.username_info`

| الحقل | الاستخدام |
|-------|------|
| `username` | يُخزَّن؛ سلسلة فارغة إذا غائب |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `ACTIVE`، `RESERVED` |
| `pin` | **المفتاح يُعاد صِرفاً ويُخزَّن في تفضيلة `username_pin`**؛ سلسلة فارغة إذا غائب |

تعيين الحالة: `RESERVED` ← `C4DU.RESERVED`؛ `ACTIVE` ← `ACTIVATED` إذا كان اسم المستخدم المخزَّن يساوي المُعاد والحالة المحلية كانت `RESERVED` أو `ACTIVATED`، وإلا `CREATED`؛ حالة فارغة أو `username_info` فارغ ← `UNSET`.

حالة خطأ 404 من الخادم تمحو اسم المستخدم المحلي، المفتاح والحالة (سجل `clearSelfUsernameData NOT_FOUND`).

ما إذا كان الاستدعاء يُستخدَم كنبضة قلب غير معروف؛ الملاحظة القديمة "polling heartbeat" لا يدعمها كود هذا البناء.

### 3.5 UsernamePinSet (مفتاح اسم المستخدم)

المتغيرات (found): `pin` (string)، يُحذَف عندما يكون فارغاً.

| الإجراء | المتغيرات |
|--------|-----------|
| ضبط المفتاح | `{"pin": "<key>"}` |
| حذف المفتاح | `{}` (`A02` يستدعي `A00(null)`) |

اسم العملية لكليهما هو `UsernamePinSet`؛ لا توجد عملية تحقق منفصلة. التحقق من مفتاح خارجي يتم في USync (4). غير مُتَّصل: يُعيد `C213639Bb("UsernamePinSet")` دون طلب.

يمكن للمفتاح أيضاً الانتقال في `UsernameSet` (المتغير `pin`). يستخدم `C81793ej.A0x` `UsernameSet` باسم المستخدم الموجود والـ`pin` الجديد عندما يكون اسم مستخدم مخزَّناً محلياً أصلاً (`A00 != null`)، و`UsernamePinSet` وإلا (found).

لا يوجد وصول حقل لصنف الاستجابة `C48557LJz` في الملفات المقروءة؛ شكل الاستجابة غير معروف.

---

## 4. البحث عن مستخدمين آخرين

### 4.1 USync الكلاسيكي باسم المستخدم (تدفق المفتاح)

مبني في `C18670m9.A06` (فشل jadx على هذه الدالة، قُرئت من smali `X/0m9.smali`). لكل إدخال طلب `C222649hm`: الحقل `A0C` = اسم المستخدم، `A0D` = المفتاح، `A05` = LID.

سمات عنصر جهة الاتصال الفرعي (مُعثور عليه في smali): `username` دائماً؛ `lid` عندما يكون LID معروفاً محلياً؛ `pin` عند ضبط مفتاح. السمات الإضافية مضبوطة بالعلم **12402** (الافتراضي `false`): عندما يكون العلم مُعطَّلاً، يُكتَب فقط `username` (found). اسم العقدة `contact` مستنتج من مُحلِّل الاستجابة، الذي يقرأ العنصر الفرعي `contact` وسمته `username` (`C18670m9` السطور ~969-975).

```xml
<iq xmlns="usync" to="[server]" type="get">
  <usync mode="query" context="interactive" sid="..." index="0" last="true">
    <list>
      <user><contact username="name" lid="LID" pin="KEY"/></user>
    </list>
    <query><contact/> ... </query>
  </usync>
</iq>
```

نقطة الدخول: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`)، تُستدعى من `submitPinForUsername`. نوع المزامنة `EnumC21760rz.A0J`، مهلة 32000 ms. مجموعة السمات `contact`، `pin`، `username` موجودة في مجموعات تنقية السجل الخاصة بـ`AbstractC40921lc` (found).

حل محلي مسبق: يبحث `A0M.Aol(username)` عن `lid_row_id` في جدول `lid_display_name` حيث `UPPER(username) = UPPER(?)`، الصف الأحدث أولاً (found، `C1S0`). يدخل LID، إن عُرف، في سمة `lid`.

### 4.2 تقييم النتيجة (إدخال المفتاح)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| النتيجة | الشرط |
|---------|---------|
| مفتاح صحيح | النتيجة `UserJid` هي LID (`C14080dr`) |
| مفتاح خاطئ | النتيجة لا تحمل LID: سجل `[un-pin] incorrect PIN`، نص خطأ "Wrong key entered" |
| لا شبكة | `C9qA` الرمز 1 |
| خطأ بنية تحتية عام | `C9qA` الرمز 2 |
| تحديد معدَّل طالب الطلب | `C225769os.A01` صحيح: "Too many attempts made. Try later." |
| تحديد معدَّل المطلوب | `C225769os.A00` صحيح: "This account can't be reached with their key right now..." |

يُشغَّل فحص تحديد معدَّل مخزَّن مؤقتاً من جانب العميل أولاً عندما يكون العلم **16033** مُفعَّلاً وإعداد JSON **21995** يحمل `enable_key_rate_limit` صحيحاً (الافتراضي صحيح): `C30P.A00` مقابل LID الخاص ومقابل اسم المستخدم الهدف. يُزال `@` من اسم المستخدم (`C0CX.A0i(username, '@')`).

عند النجاح النتيجة **LID**، وتُعالَج الدردشة بعد ذلك إلى LID (مستنتج من فحص `C14080dr`؛ خطوة فتح الدردشة لم تُتعقَّب).

### 4.3 جلب اسم مستخدم لـLID معروف

يبني `C23638AId` (السطر ~600-650) usync بـ`<list><user jid="LID"/></list><query><contact/><username/></query>`، نمط/سياق من `EnumC21760rz.A0J` (found). يقرأ المُحلِّل `username` كعنصر فرعي من نتيجة `<usync>` (`C18670m9` السطر 586، فقط عندما طلبها الطلب).

### 4.4 MEX USync (`UsyncQuery`)

يبني `C229259vZ.A01` `UsyncQuery` (doc_id أعلاه). الأجزاء ذات الصلة (found):

| المتغير | الاستخدام |
|----------|-----|
| `query_input[]` | إدخال واحد لكل مستخدم: JID (`C493020r.A0C`)، `client_known_username` اختياري (فقط عندما يُطلَب اسم المستخدم وغير فارغ) |
| `include_username` | bool، يُضبَط عندما يطلب أي إدخال اسم المستخدم |
| `include_lid` | bool، يطلب `lid_info` |
| `telemetry.context` | سياق USync بحروف صغيرة |

الاستجابة لكل مستخدم: `jid`، `username_info`، `lid_info` (`O0F`). `username_info` متعدد الأشكال بتجزئة النوع: نوع قيمة يحمل `username`، أو نوع حالة بـ`status` من `EnumC216389Tz`: `EMPTY`، `NOT_ALLOWED`، `NO_CHANGE` (+ غير مضبوط). تُسجَّل `NOT_ALLOWED` كـ"username not allowed to be queried" وتمحو اسم المستخدم المخزَّن؛ `NO_CHANGE` تحتفظ به. يحمل `lid_info.lid_jid` الـLID.

البوّابة: يرفض `ContactSyncHelper` مسار MEX بالسجل "cantUseMex as username ab prop is off" إلا إذا كان العلم **8421** مُفعَّلاً عند طلب اسم مستخدم (found؛ الافتراضي `false`).

---

## 5. التحقق والحدود والأخطاء

### 5.1 شكل اسم المستخدم (محلي)

مُحقِّق `C82003fB.A04` (found)، فحوصات بهذا الترتيب:

| الترتيب | الفحص | معرّف الخطأ (`C02U`) | سلسلة الرسالة |
|-------|-------|-------------------|----------------|
| 1 | كل حرف في `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | الطول >= الأدنى (العلم **20494**، الافتراضي 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | الطول <= الأعلى (العلم **20459**، الافتراضي 35) | 1 | نفس السلسلة |
| 4 | لا `.` بادئة، لا `.` خاتمة، لا `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | حرف ASCII واحد على الأقل | 4 | "Choose a username with at least one letter" |
| 6 | تعبير نمطي (أدناه) | ينجح أو يفشل برمز 2 | لا ينطبق |

التعبير النمطي المبني بواسطة `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

لا تُطبِّع حالة الأحرف بواسطة المُحقِّق؛ البحث المحلي `Aol` يُقارِن بـ`UPPER()`، فالمطابقة غير حسّاسة لحالة الأحرف محلياً (found). ما إذا كان الخادم يعامل الأسماء دون حساسية لحالة الأحرف غير معروف. الشرطة السفلية البادئة مسموحة بالتعبير النمطي؛ نص الواجهة يقول "يبدأ بحرف"، وهذا أشد من التعبير النمطي (found، عدم تطابق).

ترفض الواجهة أيضاً روابط الويب: "Enter only your username, not a web link" (السلسلة موجودة، الفحص لم يُتعقَّب).

### 5.2 شكل مفتاح اسم المستخدم

`C1176550d.A00` (found): العلم **34350** سلسلة تعبير نمطي، الافتراضي `^([0-9]{4}|[A-Z0-9]{6})$`. إذا كانت سلسلة العلم فارغة، يكون الحل البديل أربعة أرقام بالضبط. تعبير نمطي غير صالح يُسجِّل `[un-pin] invalid username_key_regex` ويقبل أي شيء. أعلام حدود الطول **34347** (الأدنى، 4) و**34348** (الأعلى، 6) تُغذِّي فقط مسار رسالة الخطأ في `UsernamePinEntryViewModel.A0w`. قواعد الخادم غير معروفة.

فالملاحظة القديمة "PIN من 4 أرقام" ناقصة: الافتراضي المشحون يقبل أربعة أرقام أو ستة أحرف/أرقام كبيرة.

### 5.3 تحديد المعدَّل والتأخير التصاعدي

`C67942uO` (found)، نشط فقط بالعلم **28678** (الافتراضي `false`):

| العنصر | القيمة |
|------|-------|
| المُحفِّز | خطأ `UsernameSet` 429، 503 أو 529 |
| المدة | سلسلة شبيهة بـ`Retry-After` تُحلَّل كثوانٍ عدد صحيح (`C23680AJt.A00`)، وإلا العلم **28127** (الافتراضي 30) ثانية |
| التخزين | تفضيلتا `username_creation_rate_limit_backoff_expiry` (ms)، `username_creation_rate_limit_error_code` |
| الأثر | يفشل `UsernameCheck`، `UsernameCheckMulti`، `UsernameSet` محلياً حتى الانتهاء |

### 5.4 تعيين رمز الخطأ إلى رسالة (`C82003fB.A02`، found)

| الرمز | الرسالة |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403، 404، 429 | "Couldn't complete your request. Try again." |
| 500، 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406، 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| غيره | "We couldn't complete your request. Try again." |

40601 إلى 40603 موجودة في المجموعة المسموحة `AbstractC111104pH.A01` (فقط 40603 مُعثور عليها في الكود المقروء). دلالاتها من جهة الخادم غير معروفة بما يتجاوز نص العميل.

---

## 6. العلاقة بـLID

الكل found إلا إذا أُشير إلى غيره.

| الحقيقة | الدليل |
|------|------|
| تحل بحوث اسم المستخدم إلى **LID**، لا إلى JID هاتف | فحص نجاح المفتاح `userJid instanceof C14080dr` (صنف LID)؛ `lid_info.lid_jid` في usync MEX |
| خريطة محلية اسم المستخدم ← LID | جدول `lid_display_name` (أعمدة `username`، `lid_row_id`)، استعلام في `C1S0` |
| تُعرِّف الإشعارات المستخدم بـLID | معالِجا الضبط/الحذف يُحلِّلان `LidUserJid` (نص خطأ "Failed to parse LidUserJid") |
| قد يحمل إشعار الحذف JID هاتف | يفحص المعالِج `isPnPresent`؛ مع وجود PN يحوِّل JID لهاتف ويتصرف، دون PN يُعيد |
| إجراء مزامنة جهة الاتصال | يحمل `ContactAction` `username` (6) إلى جوار `lid_jid` (3)، `pn_jid` (5)؛ أيضاً `LidContactAction` (`lid_contact`، حقل SyncActionValue 61) |
| نمط بدء الدردشة | حقل SyncActionValue **59** `username_chat_start_mode`، تعداد `EnumC50053M6w`: `LID` = 1، `PN` = 2. فقط المُرمِّز المُزامِن مُعثور عليه؛ لا مستهلك في كود الواجهة (غير معروف) |
| سلسلة ميزة الرفيق | عند ربط رفيق يُضيف الحساب الأساسي `username_supported` (العلم 4745 أو 20189)، `username_reservation_only_mode` (العلم 20189 فقط)، `username_account_linking_enabled` (العلم 21199) إلى قائمة ميزاته (`C25056AqU`) |

مستنتج: مستخدم موجود فقط كاسم مستخدم قابل للوصول إلا عبر LID حتى يشارك المالك رقم الهاتف؛ تدعم ذلك السلاسل "If you continue, your phone number will show in existing username chats and calls" (حوار الحذف) لكن مسار كشف PN لم يُتعقَّب.

---

## 7. الإشعارات

تمتد المعالِجات من `AbstractC23194A0r` وتُسجَّل في `AbstractC20380p4` (found):

| الإشعار | المعالِج | السلوك |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | الحمولة `xwa2_notify_username_on_change`: تقرأ LID (تجزئة الحقل 107143) واسم المستخدم؛ تُخزَّن عبر `InterfaceC11470Yz.BNU(lid, username)`؛ إذا كانت جهة الاتصال موجودة ومن النوع المطابق، تُحدِّث جهة الاتصال (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | الحمولة `xwa2_notify_username_delete`: تقرأ LID وPN (تجزئة -983979708)؛ مع وجود PN تُشغِّل تحديث الحذف (`C53594Nzh`) |
| `UsernameUpdateNotification` | مجهول `X.2YG` | تقرأ تجزئة base64 من الحمولة، تبني طلب USync بسبب `USERNAME_UPDATE_NOTIFICATION` و`EnumC21760rz.A0Q` (سياق `NOTIFICATION_SIDELIST`، نمط `query`؛ انظر WA_USYNC.md)، سجل `usync triggered for hash` |

النص الظاهر للمستخدم: "Your username has changed"، "WhatsApp has assigned you a new username (%1$s)"، أي أن الخادم يستطيع إعادة تعيين اسم مستخدم (إبطال، تفضيلة `is_username_revoked`، `revocation_banner_dismissed_<username>`).

---

## 8. أعلام الميزات

معرّفات الأعلام هي معرّفات خاصية AB تُقرأ عبر `C08J` (الافتراضيات من جداول `C08J`). كل الافتراضيات أدناه قُرئت من هذا البناء.

| العلم | النوع | الافتراضي | يتحكم في |
|------|------|---------|----------|
| **4745** | bool | false | الأساسي: إنشاء اسم مستخدم (وضع `CREATION`)؛ يُعلَن أيضاً كـ`username_supported` |
| **20189** | bool | false | الأساسي: وضع الحجز فقط (`RESERVATION`)؛ `username_supported` |
| **23817** | bool | false | الرفيق: ميزات اسم المستخدم كلياً (وإلا `DISABLED`) |
| **21199** | bool | false | ربط الحساب (FB / IG) مُفعَّل، يُعلَن كـ`username_account_linking_enabled` |
| **16033** | bool | false | البوّابة الرئيسية لميزات المفتاح (`C79343Xx.A00`): تحديد معدَّل المفتاح، ترقية المفتاح، عرض اسم مستخدم WABI |
| **21995** | JSON | `{}` | `enable_key_rate_limit`، `enable_key_upsell_flows`، `enable_wabi_username_view` (كلها افتراضياً صحيحة عندما يكون مفتاح JSON غائباً) |
| **8421** | bool | false | يسمح بـ`UsyncQuery` من MEX لطلبات اسم المستخدم |
| **12402** | bool | false | يضيف سمتي `lid` و`pin` إلى عقدة `contact` الخاصة بـusync |
| **20494** / **20459** | int | 3 / 35 | أدنى/أعلى طول اسم مستخدم |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | تعبير نمطي للمفتاح |
| **34347** / **34348** | int | 4 / 6 | حدود طول المفتاح (رسالة الخطأ) |
| **28678** | bool | false | يُفعِّل مخزن التأخير التصاعدي لتحديد المعدَّل |
| **28127** | int | 30 | ثواني التأخير التصاعدي الافتراضية |
| **29327** | int | 60 | التأخير قبل الدفعة الثانية من `UsernameCheckMulti` |

أهلية الرفيق (`C224069kP.A00`، قراءة على مستوى البايت كود):

```
companion (identity of the A02 check inferred from the "open WhatsApp on your primary device" strings):
  23817 off, or pref username_reservation_creation_supported_on_primary false  -> DISABLED
  pref username_account_linking_enabled_on_primary true                         -> COMPANION_READ_ONLY
  state RESERVED                                                                -> COMPANION_READ_ONLY
  state not UNSET                                                               -> CREATION
  state UNSET and pref username_reservation_only_mode_on_primary true           -> COMPANION_READ_ONLY
  state UNSET otherwise                                                         -> CREATION
primary:
  4745 on -> CREATION;  else 20189 on -> RESERVATION;  else DISABLED
```

التفضيلات الثلاث `*_on_primary` مقروءة فقط هنا؛ أين تُكتَب لم يُعثر عليه (غير معروف).

---

## 9. الخصوصية والظهور

| الجانب | النتيجة | المستوى |
|--------|---------|------|
| الغرض | "Keep your phone number private with a username"؛ من لا يحمل الرقم محفوظاً يرى اسم المستخدم بدلاً منه | found (سلاسل) |
| أول تواصل | بمفتاح مضبوط، من "لم تتفاعل معهم" يجب أن يُدخلوا المفتاح قبل التواصل مع اسم المستخدم | found (سلاسل) |
| مشاركة المفتاح | إجراء مشاركة اسم المستخدم يمكن أن يشمل المفتاح (تفضيلة `username_share_include_pin`، رُحِّلت بعيداً في `C138535tr`)؛ سلاسل "Share your username and key" | found |
| أين يُخفى الرقم | يرى مشرفو المجتمع ومشرفو القناة الرقم إلا إذا ضُبط اسم مستخدم؛ لا يرى متابعو القناة أياً منهما | found (سلاسل) |
| قياس عن بُعد للمجموعة/الخيط | حقول `has_username`، `has_username_pin`، `is_username_thread` في قياس إرسال الرسائل عن بُعد (`DZ1`، `RQG`) | found |
| المفتاح في حالة السكون | يُعيد `UsernameGet` المفتاح الخاص ويُخزَّن في تفضيلات صِرفة `username_pin` | found |
| دردشات طرف ثالث | "Usernames and contacts added to third-party chats will not save to your phone" | found (سلسلة) |
| الأعمال | "This username is only available on WhatsApp Business" يظهر كنص رفض | found (سلسلة) |
| من يمكنه الاستعلام | حالة usync MEX `NOT_ALLOWED` تُظهر أن الخادم يستطيع رفض كشف اسم المستخدم حسب الطالب | found (تعداد)، القاعدة غير معروفة |
| القاصرون | تفضيلة `is_teen_account`؛ نصوص الوالد "Your child created the username ..." | found |

قواعد الظهور التي يفرضها الخادم (من يستطيع حل اسم مستخدم، حدود معدَّل المفتاح، إعادة التعيين) غير معروفة من العميل.

### 9أ. ضوابط جمهور مشاركة رقم الهاتف (جديدة في 2.26.45.10، found)

تتحكم حزمة منفصلة `com.whatsapp.pnsharing` فيمن يمكنه رؤية رقم هاتف الحساب، مستقلة عن قواعد ظهور اسم المستخدم نفسه في 9. عمليتا `whatsapp-android-mex` جديدتان، كلاهما `found` من سلاسل `const-string` صِرفة في smali (لا حاجة إلى فك تجميع، `PnSharingAudienceUpdater.smali` / `PnSharingListFetcher.smali` / `PnSharingListUpdater.smali`):

| العملية | doc_id | النوع |
|-----------|--------|------|
| `UsernamePhoneNumberPrivacyUpdateMutation` | `28835748819379698` | mutation |
| `UsernamePhoneNumberPrivacyGetQuery` | `29264643203229836` | query |

إعداد الجمهور واحد من 4 قيم للتعداد المشترَك غير الخاص بـpnsharing `LX/BWW` (13 عضواً إجمالاً، فقط هذه الأربعة قابلة للوصول من مسار هذا الاستدعاء):

| الترتيب (ordinal) | عضو `LX/BWW` | قيمة `setting` |
|---|---|---|
| 0 | `A02` | `ALL` |
| 1 | `A07` | `MYCONTACTS` |
| 2 | `A08` | `MYCONTACTSEXCEPT` |
| 3 | `A09` | `NONE` |

**`UsernamePhoneNumberPrivacyUpdateMutation` تدريجية، لا استبدال كامل.** موقعا استدعاء يُغذِّيانها:

- `PnSharingAudienceUpdater.A00` — تغيير الإعداد على المستوى الأعلى فقط، دون إدخالات قائمة.
- `PnSharingListUpdater.A01` — إضافة/إزالة لكل إدخال مقابل واحدة من ثلاث قوائم جمهور.

الحقول على المستوى الأعلى (found):

| الحقل | النوع | المعنى |
|-------|------|------|
| `setting` | string | `ALL` / `MYCONTACTS` / `MYCONTACTSEXCEPT` / `NONE`، انظر الجدول أعلاه |
| `input` | object | حمولة متداخلة، انظر أدناه |

حقول `input` (found، متداخلة تحت `allow_list` / `contact_exclude_list` / `deny_list` تبعاً لأي من الإعدادات الثلاثة غير `MYCONTACTS` نشط — `MYCONTACTS` لا تُرسِل مفتاح قائمة):

| الحقل | النوع | المعنى |
|-------|------|------|
| `dhash` | string | تجزئة محتوى قائمة الجمهور، تُستخدَم لإبطال التخزين المؤقت/اكتشاف التعارض (سلسلة سجل "...changed since it was read" مجاورة لها) |
| `entries` | قائمة أجسام | إدخالات ADD/DEL تدريجية، لا استبدال قائمة كامل |

حقول عنصر `entries[]` (found، مبنية بواسطة `PnSharingListUpdater.A00(Integer, Integer)`):

| الحقل | النوع | المعنى |
|-------|------|------|
| `entry_type` | string | `USER` أو `GROUP` |
| `operation` | string | `ADD` أو `DEL` |
| `group_jid` | string، قابل للفراغ | يُضبَط فقط عندما `entry_type=GROUP` |
| `pn_jid` | string، قابل للفراغ | يُضبَط عندما يكون الإدخال رقم هاتف خام (`PhoneUserJid`) |
| `user_jid` | string، قابل للفراغ | يُضبَط عندما يكون الإدخال `Jid` جهة اتصال مُحلَّلة |
| `username` | string، قابل للفراغ | الحقل موجود في المخطط لكن لا موقع استدعاء مرصود يملؤه؛ الغرض `inferred`: إقران رقم هاتف ليس جهة اتصال بعد باسم عرض، بما يتسق مع استثناءات بنمط `UsernameSet` — `unknown` ما إذا كان أي مُستدعٍ يضبطه فعلياً |

تُملأ واحدة فقط من `group_jid` / `pn_jid` / `user_jid` لكل إدخال (found)؛ تبقى الأخريان فارغتين.

`UsernamePhoneNumberPrivacyGetQuery` هي نظيرة القراءة (found، `PnSharingListFetcher.smali`): رحلة ذهاب وعودة مُجمَّعة واحدة تجلب كل القوائم الثلاث دفعة واحدة، كل منها مُفهرَسة بـ`dhash` خاصة بها (تجزئة مخزَّنة محلياً مؤقتاً، أو السلسلة الحرفية `"none"` إذا غائبة) للتحقق من التخزين المؤقت.

**doc_id غير محسوم:** يُدرِج فهرس الاستعلام الدائم أيضاً `PnSharingPhoneNumberFetch` (doc_id `29229648029980096`، النوع query). بحث grep في شجرة smali الكاملة المُفكَّكة لـ2.26.45.10 (كل الأجزاء، لا فقط `com/whatsapp/pnsharing/`) عن هذه السلسلة الحرفية لا يُظهر موقع استدعاء — فقط مورد `whatsapp-android-mex_client_persist_ids.json` المشحون يُشير إليها. من يستدعيها وماذا ترسل **غير معروف**. المرشَّح الأرجح بالاسم فقط (**مستنتج**، لا أكثر): جلب ظهور رقم هاتف لكل جهة اتصال/مجموعة، أي نظيرة العنصر الواحد لاستعلام القوائم الثلاث المُجمَّع أعلاه — غير مؤكَّد.

---

## 10. ملاحظات Baileys

الغلاف في 2.2 عام؛ يستطيع عميل Baileys بناءه. هذا **مستنتج**، لم يُختبَر هنا.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| الخطر | السبب |
|------|--------|
| انحراف doc_id | المعرّفات خاصة بموارد هذا البناء؛ قد تختلف البناءات الأخرى (غير معروف) |
| `session_id` | يرسله الكود عند وجوده؛ ما إذا كان الخادم يتطلب نفس القيمة للفحص والضبط غير معروف |
| سمات المفتاح | `lid` / `pin` على `contact` محجوبة بالعلم 12402؛ قد يتجاهلها الخادم لعملاء دون العلم (غير معروف) |
| القواعد المحلية | الطول، مجموعة الأحرف وقواعد النقطة من جانب العميل؛ قواعد الخادم غير معروفة |

---

## 11. فروق أساسية

| لا تخلط بين | الفرق |
|----------------|------------|
| مفتاح اسم المستخدم مقابل PIN الحساب / 2FA | مفتاح اسم المستخدم (`pin` في `UsernamePinSet`، تفضيلة `username_pin`) يحجب أول تواصل عبر اسم المستخدم. غير مرتبط بـ2FA التسجيل |
| متغير `reserved` مقابل `UsernamePinSet` | `reserved` ينتمي لـ`UsernameSet` ويُعلِّم حجزاً؛ المفتاح له عمليته الخاصة |
| حالة `RESERVED` | `C4DU.RESERVED` المحلية / `state=RESERVED` من الخادم اسم محجوز غير قابل للاستخدام بعد؛ `ACTIVATED` و`CREATED` قابلتان للاستخدام |
| الحذف | لا توجد عملية حذف؛ `UsernameSet` دون `username` تحذف؛ حذف المفتاح هو `UsernamePinSet` بـ`{}` |
| نتيجة الفحص `INVALID` | تغطي الأخذ، الحاجة للربط ومشكلات الشكل؛ التفصيل في `rejection_reasons` |
| اسم المستخدم مقابل LID | اسم المستخدم معرِّف؛ هوية العنونة هي LID |
| أعداد `source` | 1 `FB`، 2 `IG`، 3 `USER_INPUT`، 4 `SUGGESTION`؛ ليست نفس أعداد معرّفات خطأ `C02U` |
| doc_id مقابل `client_doc_id` | كلاهما في الموارد؛ المعرّفات المُلتقَطة تساوي `doc_id` |
| الإشعارات مقابل العمليات | أنواع `Username*Notification` الثلاثة معالِجات دفع، لا طلبات |
| تسميات عابرة للمستودعات | `25975613018777537` غائب عن موارد معرّفات الديمومة في هذا البناء؛ `25741205615468935` هو `GetTextStatusList` في هذا البناء. لا أحدهما عملية اسم مستخدم هنا |

---

## 12. التدفق من البداية إلى النهاية

```
[User]                [Client]                              [Server]
  │ type name           │                                      │
  ▼                     │                                      │
 local validate ────────┤ charset, 3..35, dots, regex (5.1)    │
  │ ok                  ▼                                      │
  │              UsernameCheck {username, include_suggestions,  │
  │                             source, session_id}  ─────────►│
  │                     │◄──── xwa2_username_check {result,    │
  │                     │       suggestions, rejection_reasons}│
  │ SUCCESS             │                                      │
  ▼                     ▼                                      │
 confirm ─────────► UsernameSet {username, reserved,           │
                      session_id, source, [pin]} ─────────────►│
                        │◄──── ok | 304 | 40601..40603 | 429/503/529
                        ▼                                      │
                  write prefs: state, username_pin             │
                  429/503/529 -> backoff (flag 28678)          │
                                                               │
 [Owner sets key] ► UsernamePinSet {pin} | {} (delete) ───────►│

 [Other user, first contact]
  │ enter @name + key
  ▼
 validate key (flag 34350) ► usync contact{username,[lid],[pin]} ──►[Server]
                        │◄──── user jid (LID) | no LID | rate-limit flags
                        ▼
              LID  = open chat addressed to the LID
              none = "Wrong key entered"
              limit = "Too many attempts" / "can't be reached"

 [Server push]
   UsernameSetNotification (lid, username)  -> update local map
   UsernameDeleteNotification (lid, pn)     -> update contact
   UsernameUpdateNotification (hash)        -> usync delta
```

---

## 13. المجاهيل

| الموضوع | السبب |
|-------|--------|
| الوصول الدقيق الذي يُغذِّي `query_id` | مستهلك `doc_id` مقابل `client_doc_id` لم يُتعقَّب إلى باني IQ |
| شكل استجابة `UsernamePinSet`، `UsernameSet` | أصناف الاستجابة لا وصول حقل لها في الكود المقروء |
| `UsernameGetRecommendationsQuery` | لا موقع استدعاء، لا متغيرات |
| قواعد اسم المستخدم والمفتاح من جهة الخادم | العميل يُحقِّق محلياً فقط |
| معنى 40601-40603 على الخادم | فقط سلاسل العميل مُعثور عليها |
| أصل تفضيلات `*_on_primary` | لا كاتب مُعثور عليه |
| أثر `username_chat_start_mode` | لا مستهلك مُعثور عليه |
| نمط استخدام `UsernameGet` (نبضة قلب) | لا يدعمه الكود المقروء |
| خطوة فتح الدردشة بعد مفتاح صحيح | لم تُتعقَّب بعد فحص LID |
| الحركة الفعلية | تحليل ساكن فقط |
