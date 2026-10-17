<!-- src-sha1: 9e1058e3eb76214c55e35cbbb05dda93127364b1 -->
# WhatsApp اسم المستخدم — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** فحص اسم المستخدم / تعيينه / حجزه / حذفه، ومفتاح اسم المستخدم (PIN)، والعلاقة مع LID، والخصوصية والظهور، وعمليات GraphQL ‏w:mex (doc_ids، والمتغيرات، والاستجابات)، والإشعارات، والبحث عبر USync، وقواعد التحقق، وأعلام الميزات، وملاحظات Baileys

---

## 1. ما هو اسم المستخدم (من الناحية التقنية)

اسم المستخدم هو معرّف على جهة الخادم مرتبط بحساب، يُستخدم ليتمكن أحد من الوصول إلى جهة اتصال دون كشف رقم الهاتف. جميع العبارات هي نتيجة تحليل ساكن لـ APK المفكوك. المستوى: **found** = قُرئ في الشيفرة أو الأصول، **inferred** = مستنتَج من الشيفرة، **unknown** = لم يُحسم.

تقوم الميزة على ثلاث طبقات:

| الطبقة | النقل | الاستخدام |
|-------|-----------|----------|
| الإدارة الذاتية | ‏`w:mex` IQ، وGraphQL مخزَّن (الإعداد `whatsapp-android-mex`) | الفحص، والتعيين / الحجز / الحذف، والجلب، وتعيين / حذف المفتاح (PIN)، والفحص المتعدد |
| البحث عن الآخرين | ‏USync (`xmlns="usync"`) ونسخة MEX ‏`UsyncQuery` | تحويل `@username` (+ المفتاح) إلى LID، وجلب اسم المستخدم لـ JID معروف |
| الدفع | إشعارات MEX | `UsernameSetNotification` و`UsernameUpdateNotification` و`UsernameDeleteNotification` |
| عبر الأجهزة | مزامنة حالة التطبيق (`SyncActionValue`) | ‏`username_chat_start_mode` و`lid_contact_action` (يحمل `username`) |

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| مدير اسم المستخدم | `C122815Lj` | استدعاءات `UsernameGet` و`UsernameSet`، وتحديث الحالة المحلية، وخطّاف تحديد المعدل |
| فحص التوفر | `C67402tT` | استدعاء `UsernameCheck` + ربط الاستجابة |
| الفحص المتعدد | `C76333Kg` | ‏`UsernameCheckMulti`، بدفعات من 10 |
| واجهة المفتاح | `MexUsernamePinProtocolApi` | ‏`UsernamePinSet` (تعيين / حذف المفتاح) |
| الحالة المحلية / التفضيلات | `C5Q8` | ‏`username_reservation_state` و`username_pin` و`is_username_revoked` |
| تعداد الحالة | `C4DU` | ‏`UNSET` و`RESERVED` و`ACTIVATED` و`CREATED` |
| وضع الأهلية | `C224069kP.A00()` -> `C9SR` | ‏`CREATION` و`RESERVATION` و`COMPANION_READ_ONLY` و`DISABLED` |
| مخزن تحديد المعدل | `C67942uO` | التراجع بعد 429 / 503 / 529 |
| المدقّق المحلي | `C82003fB.A04`، `C1187754z` | الطول، ومجموعة المحارف، وقواعد النقطة، وregex |
| مدقّق المفتاح | `C1176550d` (+ `AbstractC111284pZ`) | صيغة المفتاح |
| VM إدخال المفتاح | `UsernamePinEntryViewModel` | إرسال مفتاح لاسم مستخدم أجنبي |
| عميل USync | `C23638AId` (`querySyncUsernameWithErrorInfo`)، `C18670m9` | باني / محلل stanza ‏usync الكلاسيكي |
| MEX USync | `C229259vZ`، `O0F` | ‏`UsyncQuery` مع `include_username` |
| معالجات الإشعارات | `C49822Lvi`، `C49821Lvh`، صنف مجهول `X.2YG` في `AbstractC20380p4` | تعيين / حذف / تحديث |

التسمية: الاسم الذي يراه المستخدم للـ PIN هو **username key** (السلاسل "Username key" و"Add a username key to control who can contact you"). أما في الشبكة والشيفرة فيُسمّى `pin`.

---

## 2. عمليات MEX (doc_ids)

### 2.1 أين توجد doc_ids

doc_ids ليست قيمًا حرفية في `java_src`. يرسل العميل اسم العملية (`"UsernameSet"`، ...) مع اسم الإعداد `"whatsapp-android-mex"` (found، `C16880is`). يُقرأ المعرّف الرقمي من `assets/whatsapp-android-mex_client_persist_ids.json`: يربط `EnumC17010j7.WHATSAPP_ANDROID_MEX` بذلك الملف، ويعيد `C17040jA.CMg(op)` الحقل `doc_id`، ويعيد `AGb(op)` الحقل `client_doc_id` (found). أي من الدالتين تملأ السمة `query_id` لم يُتتبَّع حتى النهاية (unknown)؛ وتُظهر التقاطات سابقة على 2.26.26.4 أن `query_id` يساوي `doc_id`.

doc_ids أدناه **found** في أصل 2.26.41.6:

| العملية | doc_id | النوع | موضع الاستدعاء | صنف الاستجابة |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | لم يُعثر على شيء | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

ملاحظات:
- ‏`UsernameGetRecommendationsQuery`: يرد الاسم فقط في JSON الأصل. لا يشير إليه أي صنف في `java_src` بسلسلة (found). المتغيرات والاستجابة unknown.
- أسماء الإشعارات الثلاثة (`UsernameSetNotification` و`UsernameUpdateNotification` و`UsernameDeleteNotification`) ليس لها مدخل في أصل persist-id. هي أنواع إشعارات لا طلبات (انظر 7).
- يحتوي الأصل على `operation_name_hash` و`operation_text_hash` و`client_doc_id` لكل عملية. مثال `UsernameSet`: ‏`client_doc_id` هو `427995565715419341100134328918` (found).

### 2.2 الغلاف

يُبنى في `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| الحقل | القاعدة (الشيفرة) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | ‏`get` لكل عملية، بما فيها mutations |
| السمة `query_id` | تُضبط فقط إذا كانت من 1 إلى 20 محرفًا |
| الجسم | ‏JSON ‏`{"queryId": ..., "variables": {...}}`، من 1 إلى 8448000 بايت |
| متغيرات null | ‏`C16770ig.A03(k, null)` و`A02(k, null)` يتخطيان المفتاح، فغياب القيمة يعني أن المفتاح لا يُرسَل |

لا تُعاد هنا stanzas الشبكة لجلسات حيّة؛ حُلّل هذا البناء بشكل ساكن فقط.

---

## 3. العمليات بالتفصيل

### 3.1 UsernameCheck

المتغيرات (found، `C67402tT.A00`):

| المتغير | النوع | الشرط |
|----------|------|-----------|
| `username` | string | دائمًا |
| `include_suggestions` | bool | دائمًا (تمرر واجهة المستخدم `false` في مسار الفحص المكتوب `C64H` الحالة 21) |
| `source` | string | فقط إذا لم يكن null |
| `session_id` | string | فقط إذا لم يكن null |

ربط `source` (`AbstractC78993Wd.A0U`): العدد 1 -> `FB`، 2 -> `IG`، 3 -> `USER_INPUT`، 4 -> `SUGGESTION`، غير ذلك -> null (لا يُرسَل).

مسار الاستجابة (found، الفرع الافتراضي في `C77183Np`): ‏`data.xwa2_username_check`

| الحقل | النوع | الاستخدام |
|-------|------|-----|
| `result` | تعداد `EnumC59782gh` | ‏`UNSET_OR_UNRECOGNIZED_ENUM_VALUE` و`INVALID` و`SUCCESS` |
| `suggestions` | list<string> | يُقرأ فقط عند `INVALID` |
| `rejection_reasons` | قائمة من `C4G8` | تُقرأ فقط عند `INVALID` |
| `suggestions_eligible` | bool | القيمة الافتراضية `true` حين يكون الحقل null |

قيم `C4G8` (found): ‏`UNSET_OR_UNRECOGNIZED_ENUM_VALUE` و`ALREADY_TAKEN` و`REQUIRE_FB_ACCOUNT_LINKING` و`REQUIRE_FB_CONSUMER_ACCOUNT_LINKING` و`REQUIRE_IG_ACCOUNT_LINKING` و`REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

الربط: ‏`SUCCESS` -> `C76283Kb` (متاح)؛ ‏`INVALID` -> `C76303Kd` (غير متاح، يحمل الاقتراحات + الأسباب)؛ ‏`UNSET` -> لا يعيّن أي فرع نتيجة (يحصل الاستدعاء على المتغير السابق/null؛ السلوك unknown). التراجع المحلي النشط -> `C76293Kc` (خطأ برمز تحديد المعدل من التفضيلات، انظر 5.3)؛ لم يُقرأ استدعاء الفشل للطلب نفسه.

تقود أسباب الرفض نص ربط الحسابات ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center"، `C82003fB`). في `C82003fB` أي سبب غير `UNSET` يطلق مسار الخطأ المحلي بالرمز 40601 (`A08(40601L)`)؛ أما القائمة الفارغة أو التي تحوي `UNSET` فقط فتعرض "Username isn't allowed." تدفّق التحكم حول الحلقة مفكوك جزئيًا فقط (inferred).

### 3.2 UsernameCheckMulti

| المتغير | النوع | ملاحظات |
|----------|------|-------|
| `usernames` | **list<string>** | مصفوفة عبر `A00.A0B("usernames", list)`؛ كتالوج doc_id يصنّفه `str`، بينما الشيفرة ترسل قائمة |

التجزئة (`C76333Kg.AG5`): تُقسَّم القائمة إلى أول 10 والباقي؛ ويُعالَج الباقي بعد تأخير قدره العلم **29327** (الافتراضي 60، الوحدة لم تُحسم). القائمة الفارغة تعيد خريطة فارغة دون طلب.

مسار الاستجابة `data.xwa2_username_check_multi.results[]` (found): لكل عنصر `username` و`response.result` (نفس `EnumC59782gh`). الربط: ‏`SUCCESS` -> متاح، `INVALID` -> غير متاح (دون اقتراحات، `suggestions_eligible=false`)، وأي شيء آخر -> خطأ. الأسماء الغائبة عن النتيجة تُوسم كخطأ.

المستهلك: يخزّن `UsernameAvailabilityCache` القيمة `EnumC59192fk` (`UNKNOWN` و`AVAILABLE` و`UNAVAILABLE`) لكل اسم. الغرض (جلب مسبق لاقتراحات أسماء المستخدمين من Facebook / Instagram، السلسلة `foa_username_prefetch_cache`) هو inferred.

### 3.3 UsernameSet (إنشاء / تغيير / حجز / حذف)

المتغيرات (found، `C122815Lj.A00`):

| المتغير | النوع | الشرط |
|----------|------|-----------|
| `username` | string | يُحذف عند null (**delete**) |
| `reserved` | bool | يُرسَل دائمًا |
| `session_id` | string | فقط إذا لم يكن فارغًا (`C1YW.A08`) |
| `source` | string | فقط إذا كان عدد المصدر غير null (انظر 3.1) |
| `pin` | string | فقط إذا لم يكن null |

‏`reserved` محسوب وليس ثابتًا (found). الوسيط `z` (force) = true يعطي `false`. وإلا: الحالة الحالية `ACTIVATED` أو `CREATED` تعطي `false`؛ والحالة الحالية `RESERVED` أو وضع الأهلية `RESERVATION` تعطي `true`؛ وكل الحالات الأخرى تعطي `false`. فلا يُرسَل `reserved:true` إلا للحسابات في وضع الحجز أو التي تحتفظ بحجز مسبقًا.

الحذف وضع من العملية نفسها: ‏`username == null` -> وسم السجل `delete`، وإلا `set` (وكذلك في `MexUsernamePinProtocolApi` للمفتاح). مع username يساوي null لا يوجد المفتاح `username` في المتغيرات (found).

حارس من جهة العميل: قبل الإرسال، إذا أبلغ مخزن تحديد المعدل عن تراجع نشط، يفشل الاستدعاء محليًا بالرمز `username_creation_rate_limit_error_code` والنص "rate limit expiration time not reached" (found، `C122815Lj.A03`).

معالجة النجاح (`C122815Lj.A01`، found):

| الشرط | الحالة المحلية المكتوبة (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username يساوي null أو فارغ | ‏`UNSET`، ويُمسح تفضيل المفتاح |
| كان `reserved` صحيحًا | `RESERVED` |
| علم التفعيل | `ACTIVATED` |
| غير ذلك | ‏`ACTIVATED` إذا كانت الحالة `ACTIVATED` وساوى الاسم الاسم المخزَّن، وإلا `CREATED` |
| العدد `source` هو 1 أو 2 | التفضيل `username_set_via_account_linking` = (int == 2) |
| أُرسل `pin` | يُحدَّث التفضيل `username_pin` |
| علم المراهق | التفضيل `is_teen_account` = true |

كتابة التفضيل هي `Voip.REJECT_REASON_DECLINED`، وهي السلسلة الفارغة `""` في هذا البناء (found).

معالجة الأخطاء (`C138725uA` الحالة 2):

| الرمز الشبيه بـ HTTP | إجراء العميل |
|----------------|---------------|
| 429، 503، 529 | يُخزَّن التراجع (5.3) |
| 304 | يُعامَل كنجاح ("not modified")، وتُحدَّث الحالة المحلية مع ذلك |
| لا اتصال (`C213639Bb`) | نتيجة `C4BO` ‏"no network" |
| غير ذلك | ‏`C4BN(code, message)` |

### 3.4 UsernameGet

المتغيرات: لا شيء (يبني الاستدعاء مجموعة متغيرات فارغة، found، `C122815Lj.A02`). موسوم `@Deprecated`، ومستبدل بنسخة suspend.

الاستجابة (found، `C138815uJ` الحالة 34): ‏`data.xwa2_username_get.username_info`

| الحقل | الاستخدام |
|-------|-----|
| `username` | يُخزَّن؛ سلسلة فارغة إن غاب |
| `state` | ‏`C4FC`: ‏`UNSET_OR_UNRECOGNIZED_ENUM_VALUE` و`ACTIVE` و`RESERVED` |
| `pin` | **يُعاد المفتاح بنص صريح ويُخزَّن في التفضيل `username_pin`**؛ سلسلة فارغة إن غاب |

ربط الحالة: ‏`RESERVED` -> `C4DU.RESERVED`؛ ‏`ACTIVE` -> `ACTIVATED` إذا ساوى اسم المستخدم المخزَّن المُعاد وكانت الحالة المحلية `RESERVED` أو `ACTIVATED`، وإلا `CREATED`؛ الحالة null أو `username_info` يساوي null -> `UNSET`.

الخطأ 404 من الخادم يمسح اسم المستخدم المحلي والمفتاح والحالة (السجل `clearSelfUsernameData NOT_FOUND`).

هل يُستخدم الاستدعاء كنبضة حياة (heartbeat): unknown؛ والملاحظة القديمة "polling heartbeat" غير مدعومة بشيفرة هذا البناء.

### 3.5 UsernamePinSet (مفتاح اسم المستخدم)

المتغيرات (found): ‏`pin` (string)، يُحذف عند null.

| الإجراء | المتغيرات |
|--------|-----------|
| تعيين المفتاح | `{"pin": "<key>"}` |
| حذف المفتاح | `{}` (يستدعي `A02` الدالة `A00(null)`) |

اسم العملية في الحالتين `UsernamePinSet`؛ ولا توجد عملية تحقق منفصلة. التحقق من مفتاح أجنبي يتم في USync (4). غير متصل: يعيد `C213639Bb("UsernamePinSet")` دون طلب.

يمكن أيضًا أن يسافر المفتاح داخل `UsernameSet` (المتغير `pin`). يستخدم `C81793ej.A0x` العملية `UsernameSet` مع اسم المستخدم الموجود و`pin` الجديد حين يكون اسم المستخدم مخزَّنًا محليًا (`A00 != null`)، و`UsernamePinSet` خلاف ذلك (found).

لا يملك صنف الاستجابة `C48557LJz` أي وصول إلى حقول في الملفات المقروءة؛ شكل الاستجابة unknown.

---

## 4. البحث عن مستخدمين آخرين

### 4.1 USync الكلاسيكي حسب اسم المستخدم (مسار المفتاح)

يُبنى في `C18670m9.A06` (فشل jadx في هذه الدالة، قُرئت من smali ‏`X/0m9.smali`). لكل مدخل طلب `C222649hm`: الحقل `A0C` = اسم المستخدم، و`A0D` = المفتاح، و`A05` = LID.

سمات العنصر الابن contact (found في smali): ‏`username` دائمًا؛ و`lid` حين يكون LID معروفًا محليًا؛ و`pin` حين يكون المفتاح مضبوطًا. السمات الإضافية يتحكم بها العلم **12402** (الافتراضي `false`): حين يكون العلم مغلقًا يُكتب `username` فقط (found). اسم العقدة `contact` هو inferred من محلل الاستجابة الذي يقرأ العنصر الابن `contact` وسمته `username` (`C18670m9` الأسطر ~969-975).

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

نقطة الدخول: ‏`C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`)، يستدعيها `submitPinForUsername`. نوع المزامنة `EnumC21760rz.A0J`، المهلة 32000 ms. مجموعة السمات `contact` و`pin` و`username` موجودة في مجموعات حجب السجلات لـ `AbstractC40921lc` (found).

الحل المحلي المسبق: يبحث `A0M.Aol(username)` عن `lid_row_id` في الجدول `lid_display_name` حيث `UPPER(username) = UPPER(?)`، الأحدث صفًا أولًا (found، `C1S0`). يدخل LID، إن عُرف، في السمة `lid`.

### 4.2 تقييم النتيجة (إدخال المفتاح)

‏`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| النتيجة | الشرط |
|---------|-----------|
| مفتاح صحيح | ‏`UserJid` في النتيجة هو LID (`C14080dr`) |
| مفتاح خاطئ | لا LID في النتيجة: السجل `[un-pin] incorrect PIN`، ونص الخطأ "Wrong key entered" |
| لا شبكة | ‏`C9qA` الرمز 1 |
| خطأ بنية تحتية عام | ‏`C9qA` الرمز 2 |
| تحديد معدل الطالب | ‏`C225769os.A01` صحيح: "Too many attempts made. Try later." |
| تحديد معدل المطلوب | ‏`C225769os.A00` صحيح: "This account can't be reached with their key right now..." |

يعمل فحص تحديد المعدل المخزَّن مؤقتًا في العميل أولًا حين يكون العلم **16033** مفعّلًا ويكون إعداد JSON ‏**21995** فيه `enable_key_rate_limit` صحيحًا (الافتراضي صحيح): ‏`C30P.A00` على LID الخاص وعلى اسم المستخدم المستهدف. يُجرَّد اسم المستخدم من `@` (`C0CX.A0i(username, '@')`).

عند النجاح تكون النتيجة **LID**، ثم تُوجَّه المحادثة إلى LID (inferred من فحص `C14080dr`؛ خطوة فتح المحادثة لم تُتتبَّع).

### 4.3 جلب اسم مستخدم LID معروف

يبني `C23638AId` (الأسطر ~600-650) usync بالشكل `<list><user jid="LID"/></list><query><contact/><username/></query>`، والوضع/السياق من `EnumC21760rz.A0J` (found). يقرأ المحلل `username` كعنصر ابن لنتيجة `<usync>` (`C18670m9` السطر 586، فقط حين طلب الطلب ذلك).

### 4.4 MEX USync (`UsyncQuery`)

يبني `C229259vZ.A01` العملية `UsyncQuery` (doc_id أعلاه). الأجزاء ذات الصلة (found):

| المتغير | الاستخدام |
|----------|-----|
| `query_input[]` | مدخل لكل مستخدم: JID (`C493020r.A0C`)، و`client_known_username` اختياري (فقط حين يُطلب اسم المستخدم ولا يكون فارغًا) |
| `include_username` | bool، يُضبط حين يطلب أي مدخل اسم المستخدم |
| `include_lid` | bool، يطلب `lid_info` |
| `telemetry.context` | سياق USync بأحرف صغيرة |

الاستجابة لكل مستخدم: ‏`jid` و`username_info` و`lid_info` (`O0F`). ‏`username_info` متعدد الأشكال حسب تجزئة النوع: نوع قيمة يحمل `username`، أو نوع حالة فيه `status` من `EnumC216389Tz`: ‏`EMPTY` و`NOT_ALLOWED` و`NO_CHANGE` (+ unset). يُسجَّل `NOT_ALLOWED` كـ "username not allowed to be queried" ويمسح اسم المستخدم المخزَّن؛ ويُبقيه `NO_CHANGE`. يحمل `lid_info.lid_jid` الـ LID.

البوابة: يرفض `ContactSyncHelper` مسار MEX بالسجل "cantUseMex as username ab prop is off" ما لم يكن العلم **8421** مفعّلًا حين يُطلب اسم المستخدم (found؛ الافتراضي `false`).

---

## 5. التحقق والحدود والأخطاء

### 5.1 صيغة اسم المستخدم (محلي)

المدقّق `C82003fB.A04` (found)، فحوصه بهذا الترتيب:

| الترتيب | الفحص | معرّف الخطأ (`C02U`) | سلسلة الرسالة |
|-------|-------|-------------------|----------------|
| 1 | كل محرف في `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | الطول >= الأدنى (العلم **20494**، الافتراضي 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | الطول <= الأقصى (العلم **20459**، الافتراضي 35) | 1 | السلسلة نفسها |
| 4 | لا `.` في البداية ولا في النهاية ولا `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | حرف ASCII واحد على الأقل | 4 | "Choose a username with at least one letter" |
| 6 | ‏regex (أدناه) | ينجح أو يفشل بالرمز 2 | غير متاح |

الـ regex الذي يبنيه `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

لا يوحّد المدقّق حالة الأحرف؛ والبحث المحلي `Aol` يقارن بـ `UPPER()`، فالمطابقة غير حساسة لحالة الأحرف محليًا (found). هل يعامل الخادم الأسماء دون حساسية لحالة الأحرف: unknown. تسمح regex بشرطة سفلية في البداية؛ بينما يقول نص الواجهة "start with a letter"، وهو أشد من regex (found، عدم اتساق).

ترفض الواجهة أيضًا الروابط: "Enter only your username, not a web link" (السلسلة موجودة، الفحص لم يُتتبَّع).

### 5.2 صيغة مفتاح اسم المستخدم

‏`C1176550d.A00` (found): العلم **34350** سلسلة regex، افتراضيها `^([0-9]{4}|[A-Z0-9]{6})$`. إذا كانت سلسلة العلم فارغة فالاحتياطي هو أربعة أرقام بالضبط. regex غير صالح يسجّل `[un-pin] invalid username_key_regex` ويقبل أي شيء. حدا الطول، العلمان **34347** (الأدنى، 4) و**34348** (الأقصى، 6)، يغذيان فقط مسار رسالة الخطأ في `UsernamePinEntryViewModel.A0w`. قواعد جهة الخادم unknown.

لذا فالملاحظة القديمة "4-digit PIN" غير كاملة: الافتراضي المشحون يقبل أربعة أرقام أو ستة أحرف وأرقام كبيرة.

### 5.3 تحديد المعدل والتراجع

‏`C67942uO` (found)، نشط فقط مع العلم **28678** (الافتراضي `false`):

| البند | القيمة |
|------|-------|
| المحفِّز | خطأ `UsernameSet` ‏429 أو 503 أو 529 |
| المدة | سلسلة شبيهة بـ `Retry-After` تُحلَّل كعدد صحيح من الثواني (`C23680AJt.A00`)، وإلا العلم **28127** (الافتراضي 30) ثانية |
| التخزين | التفضيلات `username_creation_rate_limit_backoff_expiry` (ms) و`username_creation_rate_limit_error_code` |
| الأثر | تفشل `UsernameCheck` و`UsernameCheckMulti` و`UsernameSet` محليًا حتى الانتهاء |

### 5.4 من رمز الخطأ إلى الرسالة (`C82003fB.A02`, found)

| الرمز | الرسالة |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403، 404، 429 | "Couldn't complete your request. Try again." |
| 500، 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406، 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| غير ذلك | "We couldn't complete your request. Try again." |

الرموز 40601 إلى 40603 ضمن المجموعة المسموح بها `AbstractC111104pH.A01` (يظهر 40603 فقط في الشيفرة المقروءة). دلالاتها على الخادم unknown فيما وراء نص العميل.

---

## 6. العلاقة مع LID

الكل found ما لم يُوسم خلاف ذلك.

| الواقعة | الدليل |
|------|----------|
| تُحل عمليات البحث عن اسم المستخدم إلى **LID** لا إلى JID الهاتف | اختبار نجاح المفتاح `userJid instanceof C14080dr` (صنف LID)؛ و`lid_info.lid_jid` في MEX usync |
| الخريطة المحلية من اسم المستخدم إلى LID | الجدول `lid_display_name` (الأعمدة `username` و`lid_row_id`)، والاستعلام في `C1S0` |
| تعرّف الإشعارات المستخدم بالـ LID | تحلل معالجات التعيين / الحذف `LidUserJid` (نص الخطأ "Failed to parse LidUserJid") |
| قد يحمل إشعار الحذف JID هاتف | يفحص المعالج `isPnPresent`؛ مع وجود PN يحوّل إلى PN JID ويتصرف، وبدونه يعود |
| إجراء مزامنة جهات الاتصال | ‏`ContactAction` فيه `username` (6) بجانب `lid_jid` (3) و`pn_jid` (5)؛ وكذلك `LidContactAction` (‏`lid_contact`، الحقل 61 في SyncActionValue) |
| وضع بدء المحادثة | حقل SyncActionValue رقم **59** ‏`username_chat_start_mode`، التعداد `EnumC50053M6w`: ‏`LID` = 1، `PN` = 2. وُجد فقط مرمّز المزامنة؛ لا مستهلك في شيفرة الواجهة (unknown) |
| سلسلة ميزة المرافق | عند ربط جهاز مرافق يضيف الأساسي `username_supported` (العلم 4745 أو 20189)، و`username_reservation_only_mode` (20189 فقط)، و`username_account_linking_enabled` (العلم 21199) إلى قائمة ميزاته (`C25056AqU`) |

Inferred: المستخدم الموجود فقط كاسم مستخدم لا يمكن الوصول إليه إلا عبر LID حتى يشارك المالك رقم الهاتف؛ والسلسلة "If you continue, your phone number will show in existing username chats and calls" (حوار الحذف) تدعم ذلك، لكن مسار كشف PN لم يُتتبَّع.

---

## 7. الإشعارات

تمدّد المعالجات `AbstractC23194A0r` وتُسجَّل في `AbstractC20380p4` (found):

| الإشعار | المعالج | السلوك |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | الحمولة `xwa2_notify_username_on_change`: يقرأ LID (تجزئة الحقل 107143) واسم المستخدم؛ ويخزّن عبر `InterfaceC11470Yz.BNU(lid, username)`؛ وإذا كانت جهة الاتصال موجودة ومن النوع المطابق يحدّثها (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | الحمولة `xwa2_notify_username_delete`: يقرأ LID وPN (التجزئة -983979708)؛ ومع وجود PN يشغّل تحديث الحذف (`C53594Nzh`) |
| `UsernameUpdateNotification` | صنف مجهول `X.2YG` | يقرأ تجزئة base64 من الحمولة، ويبني طلب USync بالسبب `USERNAME_UPDATE_NOTIFICATION` و`EnumC21760rz.A0Q` (مزامنة على نمط delta، inferred)، والسجل `usync triggered for hash` |

النص المعروض للمستخدم: "Your username has changed"، "WhatsApp has assigned you a new username (%1$s)"، أي أن الخادم يمكنه إعادة تعيين اسم مستخدم (الإلغاء، والتفضيل `is_username_revoked`، و`revocation_banner_dismissed_<username>`).

---

## 8. أعلام الميزات

معرّفات الأعلام هي معرّفات AB-prop تُقرأ عبر `C08J` (القيم الافتراضية من جداول `C08J`). جميع القيم الافتراضية أدناه قُرئت من هذا البناء.

| العلم | النوع | الافتراضي | يتحكم في |
|------|------|---------|----------|
| **4745** | bool | false | الأساسي: إنشاء اسم المستخدم (وضع `CREATION`)؛ ويُعلَن أيضًا كـ `username_supported` |
| **20189** | bool | false | الأساسي: وضع الحجز فقط (`RESERVATION`)؛ و`username_supported` |
| **23817** | bool | false | المرافق: ميزات اسم المستخدم أصلًا (وإلا `DISABLED`) |
| **21199** | bool | false | تفعيل ربط الحسابات (FB / IG)، ويُعلَن كـ `username_account_linking_enabled` |
| **16033** | bool | false | البوابة الرئيسية لميزات المفتاح (`C79343Xx.A00`): تحديد معدل المفتاح، وترويج المفتاح، وعرض WABI لاسم المستخدم |
| **21995** | JSON | `{}` | ‏`enable_key_rate_limit` و`enable_key_upsell_flows` و`enable_wabi_username_view` (كلها صحيحة افتراضيًا حين يغيب مفتاح JSON) |
| **8421** | bool | false | يسمح بـ MEX ‏`UsyncQuery` لطلبات اسم المستخدم |
| **12402** | bool | false | يضيف السمتين `lid` و`pin` إلى عقدة usync ‏`contact` |
| **20494** / **20459** | int | 3 / 35 | الحد الأدنى / الأقصى لطول اسم المستخدم |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | regex المفتاح |
| **34347** / **34348** | int | 4 / 6 | حدا طول المفتاح (رسالة الخطأ) |
| **28678** | bool | false | يفعّل مخزن تراجع تحديد المعدل |
| **28127** | int | 30 | ثواني التراجع الافتراضية |
| **29327** | int | 60 | التأخير قبل الدفعة الثانية من `UsernameCheckMulti` |

أهلية المرافق (`C224069kP.A00`، قراءة على مستوى bytecode):

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

التفضيلات الثلاثة `*_on_primary` تُقرأ هنا فقط؛ ولم يُعثر على موضع كتابتها (unknown).

---

## 9. الخصوصية والظهور

| الجانب | النتيجة | المستوى |
|--------|---------|------|
| الغرض | "Keep your phone number private with a username"؛ من لا يحفظون الرقم يرون اسم المستخدم بدلًا منه | found (سلاسل) |
| أول تواصل | مع ضبط مفتاح، على الأشخاص الذين "you haven't interacted with" إدخال المفتاح قبل التواصل مع اسم المستخدم | found (سلاسل) |
| مشاركة المفتاح | قد يتضمن إجراء مشاركة اسم المستخدم المفتاح (التفضيل `username_share_include_pin`، رُحّل بعيدًا في `C138535tr`)؛ السلاسل "Share your username and key" | found |
| أين يُخفى الرقم | يرى مديرو المجتمعات ومديرو القنوات الرقم ما لم يُضبط اسم مستخدم؛ ولا يرى متابعو القنوات أيًّا منهما | found (سلاسل) |
| قياس المجموعات / الخيوط عن بُعد | الحقول `has_username` و`has_username_pin` و`is_username_thread` في قياس إرسال الرسائل (`DZ1`، `RQG`) | found |
| المفتاح في حالة السكون | يُعاد المفتاح الخاص من `UsernameGet` ويُخزَّن في التفضيلات النصية الصريحة `username_pin` | found |
| محادثات الأطراف الثالثة | "Usernames and contacts added to third-party chats will not save to your phone" | found (سلسلة) |
| الأعمال | يظهر "This username is only available on WhatsApp Business" كنص رفض | found (سلسلة) |
| من يمكنه الاستعلام | حالة MEX usync ‏`NOT_ALLOWED` تُظهر أن الخادم يمكنه رفض كشف اسم المستخدم لكل طالب | found (تعداد)، القاعدة unknown |
| القاصرون | التفضيل `is_teen_account`؛ ونصوص الوالدين "Your child created the username ..." | found |

قواعد الظهور التي يفرضها الخادم (من يحق له حل اسم مستخدم، وتحديد معدل المفتاح، وإعادة التعيين) unknown من جهة العميل.

---

## 10. ملاحظات Baileys

الغلاف في 2.2 عام؛ ويمكن لعميل Baileys بناؤه. هذا **inferred** وليس مُختبَرًا هنا.

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
| انجراف doc_id | المعرّفات تخص أصل هذا البناء؛ وقد تختلف في بناءات أخرى (unknown) |
| `session_id` | ترسله الشيفرة حين يوجد؛ هل يشترط الخادم القيمة نفسها للفحص والتعيين unknown |
| سمات المفتاح | ‏`lid` / `pin` على `contact` خلف العلم 12402؛ وقد يتجاهلها الخادم للعملاء دون العلم (unknown) |
| القواعد المحلية | قواعد الطول ومجموعة المحارف والنقطة جهة العميل؛ وقواعد الخادم unknown |

---

## 11. فروق أساسية

| لا تخلط بين | الفرق |
|----------------|------------|
| مفتاح اسم المستخدم وPIN الحساب / 2FA | مفتاح اسم المستخدم (`pin` في `UsernamePinSet`، والتفضيل `username_pin`) يضبط أول تواصل عبر اسم المستخدم. ولا علاقة له بـ 2FA التسجيل |
| المتغير `reserved` و`UsernamePinSet` | ‏`reserved` ينتمي إلى `UsernameSet` ويعلّم حجزًا؛ وللمفتاح عمليته الخاصة |
| الحالة `RESERVED` | ‏`C4DU.RESERVED` المحلية / `state=RESERVED` على الخادم هو اسم محجوز لم يصبح قابلًا للاستخدام بعد؛ أما `ACTIVATED` و`CREATED` فقابلان للاستخدام |
| الحذف | لا توجد عملية حذف؛ ‏`UsernameSet` بلا `username` يحذف؛ وحذف المفتاح هو `UsernamePinSet` مع `{}` |
| نتيجة الفحص `INVALID` | تشمل المأخوذ، وما يتطلب الربط، ومشكلات الصيغة؛ والتفصيل في `rejection_reasons` |
| اسم المستخدم مقابل LID | اسم المستخدم معرّف عرض؛ وهوية العنونة هي LID |
| أعداد `source` | ‏1 `FB`، 2 `IG`، 3 `USER_INPUT`، 4 `SUGGESTION`؛ وليست نفس أعداد معرّفات خطأ `C02U` |
| doc_id مقابل `client_doc_id` | كلاهما في الأصل؛ والمعرّفات الملتقطة تساوي `doc_id` |
| الإشعارات مقابل العمليات | أنواع `Username*Notification` الثلاثة معالجات دفع لا طلبات |
| تسميات عبر المستودعات | ‏`25975613018777537` غائب عن أصل persist-id في هذا البناء؛ و`25741205615468935` هو `GetTextStatusList` في هذا البناء. وليس أيٌّ منهما عملية اسم مستخدم هنا |

---

## 12. المسار الكامل

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

## 13. المجهولات

| الموضوع | السبب |
|-------|--------|
| الدالة الفعلية التي تغذي `query_id` | لم يُتتبَّع مستهلك `doc_id` مقابل `client_doc_id` حتى باني IQ |
| شكل استجابة `UsernamePinSet` و`UsernameSet` | لا وصول إلى حقول في أصناف الاستجابة في الشيفرة المقروءة |
| `UsernameGetRecommendationsQuery` | لا موضع استدعاء ولا متغيرات |
| قواعد اسم المستخدم والمفتاح على الخادم | يتحقق العميل محليًا فقط |
| معنى 40601-40603 على الخادم | لم تُوجد سوى نصوص العميل |
| مصدر تفضيلات `*_on_primary` | لم يُعثر على كاتب |
| أثر `username_chat_start_mode` | لم يُعثر على مستهلك |
| نمط استخدام `UsernameGet` (heartbeat) | غير مدعوم بالشيفرة المقروءة |
| خطوة فتح المحادثة بعد مفتاح صحيح | لم تُتتبَّع بعد فحص LID |
| حركة الشبكة الفعلية | تحليل ساكن فقط |
