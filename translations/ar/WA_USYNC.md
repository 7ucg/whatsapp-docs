<!-- src-sha1: 8e15828bcc50ba6f6a9c5388872afeef15451af0 -->
# WhatsApp USync — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** USync IQ (`xmlns="usync"`): الأوضاع (modes) والسياقات (contexts) وأنواع المزامنة، بنية stanza الطلب والاستجابة، بروتوكولات الاستعلام (contact, sidelist, status, text_status, picture, business, devices, disappearing_mode, lid, username)، البحث عن جهات الاتصال واكتشاف أرقام الهواتف، مزامنة قائمة الأجهزة، فحوصات key-index وADV، ربط LID، إثراء رموز الخصوصية (privacy-token)، MEX `UsyncQuery` والتوجيه لكل بروتوكول، حدود المعدل وbackoff، محفزات العميل، feature flags، مقارنة مع Baileys

---

## 1. ما هو (تقنيًا)

USync هو استعلام "من هو هذا المستخدم" المجمّع. يحمل IQ واحد قائمة مستخدمين وقائمة بروتوكولات (أنواع بيانات)؛ ويجيب الخادم لكل مستخدم ولكل بروتوكول. يخدم شكل stanza نفسه أربع مهام: رفع دفتر العناوين وتنزيله، وعمليات البحث المفردة عن رقم هاتف، وتحديث بيانات الملف الشخصي (الحالة، الصورة، النشاط التجاري، الوضع المؤقت)، وتحديث قائمة الأجهزة لتوزيع الرسائل (fan-out). جميع العبارات مأخوذة من التحليل الساكن لـ APK المفكَّك؛ ولم يُلتقط أي شيء على الشبكة. المستويات: **found** = مقروء في الكود، **inferred** = مستنتج، **unknown** = غير محسوم. الأسماء المشوَّشة (obfuscated) خاصة بكل بناء، وقد أُعيد حلّها في 2.26.41.6.

| الطبقة | الاسم في 2.26.41.6 | الدور |
|-------|----------------|------|
| باني / محلل stanza | `C18670m9` (وسم السجل `UniSyncProtocolHelper`): `A06` بناء، `A07` إرسال، `CFS` النتيجة، `Brt` خطأ iq، `Bog` فشل التسليم | يبني `<iq xmlns="usync">` ويحلل نتيجة `<usync>` |
| نموذج الطلب | `A05` (النوع + المستخدمون + الخيارات)، `A0A` (باني لكل مستخدم)، `C222649hm` (طلب لكل مستخدم)، `C222589hg` (طلب معلّق، واحد لكل iq id) | ما يُسأل عنه |
| نوع المزامنة | `EnumC21760rz` (30 قيمة)، `EnumC21770s0` السياق، `EnumC21780s1` الوضع، `EnumC21790s3` النطاق | مصدر السمتين `mode` / `context` |
| عمليات البحث المفردة | `C23638AId` (`ContactQuerySync`) | رقم الهاتف، JID، اسم المستخدم، LID إلى اسم مستخدم |
| المزامنة الدفعية | `C18580m0` (`ContactSyncHelper`)، رد نداء مجهول `X.0m7` | مزامنة متعددة البروتوكولات، اختيار MEX أو الكلاسيكي، تفضيلات backoff |
| نقاط الدخول العامة | `C18230lP` (`ContactSyncMethods`)، الباني `C21810s5`، الطلب `C21830s7`، مجموعة البروتوكولات `C21820s6`، السبب `EnumC21800s4` (77 قيمة) | تستدعيها جميع الميزات |
| مطبّق النتيجة | `N27` (`contactsyncresultupdater`)، `C51909N4g` (`ContactSyncDevicesUpdater`) | يكتب قاعدة البيانات وخريطة LID والأجهزة |
| الأجهزة / ADV | `C23310uY` (`DeviceSyncManager`)، `SyncDevicesJob`، `C24230w2` (`DeviceADVInfoHandler`) | مهام تحديث الأجهزة، التحقق من key-index |
| إثراء الخصوصية | `C223659jg` (`ProfilePrivacyEnrichmentFetcher`)، `C197138a8`، `C197148a9` | tctoken ومجموعة مشتركة لكل مستخدم |
| متغير MEX | `C229259vZ` (`MexUsyncQueryHelper`)، `M4I` (المسار)، `M5H` (بت البروتوكول) | `UsyncQuery` والتوجيه |
| مخزن backoff | `C18800mM`، ملف التفضيلات `contact_sync_prefs` | `*_sync_backoff`، `*_full_sync_wait` |

نقاط حاسمة:

- يُخرج الباني على Android عشرة عناصر استعلام فرعية: `contact`، `sidelist`، `status`، `text_status`، `picture`، `business`، `devices`، `disappearing_mode`، `lid`، `username`. **لا** يوجد عنصر فرعي `bot` ولا عنصر فرعي للميزات (found، كلها ثوابت نصية في `A06`). العناصر `reachability` و`linked_profiles` و`orgs` و`ddm` موجودة في متغير MEX فقط (القسم 8).
- لدى Android أربعة أوضاع وعشرة سياقات (القسم 2)؛ كل طلب يحمل `sid` و`index="0"` و`last="true"` في نقاط الدخول المقروءة.
- يوضع المستخدمون في `<list>` (عادي) أو `<side_list>` (جهات اتصال خارج دفتر العناوين).
- تحمل طلبات الملف الشخصي دليل خصوصية لكل مستخدم (tctoken مخزَّن، أو JID لمجموعة مشتركة)، انظر القسم 7 وWA_TCTOKEN_CSTOKEN.md.
- عمليات البحث عن اسم المستخدم مغطاة في WA_USERNAME.md؛ يسجل هذا التقرير أجزاء stanza المشتركة فقط.

---

## 2. غلاف stanza

### 2.1 الطلب (found، `C18670m9.A06`)

```xml
<iq xmlns="usync" id="0AB1" type="get">                       <!-- `to` added by the sender, inferred -->
  <usync sid="sync_sid_query_<uuid>" index="0" last="true"
         mode="query" context="interactive" [allow_mutation="true"]>
    <query>                                                   <!-- protocol children, section 3 -->
      <contact [addressing_mode="lid"]/> <devices version="2"/> <picture type="preview" size="N"/> ...
    </query>
    <list>      <user jid="..." [common_gid="..."]> per-user children </user> ... </list>
    <side_list> <user jid="LID" pn_jid="PN"> ... </user> ... </side_list>
  </usync>
</iq>
```

| الجزء | القاعدة (الكود) |
|------|-------------|
| iq `id` | `C10140Tq.A0G()`: `"0"` + hex لعدّاد، يلتف عند 65536 (يسجل "iqId too large") |
| `sid` | `AbstractC43461pq.A00(prefix)` = prefix + `_` + UUID عشوائي؛ البادئات `sync_sid_query` و`ContactSyncHelper/sync_sid_<scope>` و`..._mex_profile` |
| `index` / `last` | من الاستدعاء: `A07` يمرر دائمًا `0` و`true` |
| `mode`، `context` | `EnumC21780s1.modeString`، `EnumC21770s0.contextString` لنوع المزامنة |
| `allow_mutation="true"` | يُضبط عندما تكون `A05.A04` صحيحة: يُبنى لأنواع full / delta عندما تتحقق `C11980aQ.A0G()` (المعنى لم يُتتبع) |
| العنصر الفرعي contact | موجود عندما يطلب أي طلب contact (`A05.A03`) أو عندما لا يُطلب أي بروتوكول آخر |
| سياق REGISTRATION | يُرسل عبر `C10140Tq.A0A(...)` بدلًا من `A06(...)` (found)؛ الفرق لم يُتتبع |
| خيارات الإرسال | وسيط مهلة iq بقيمة 32000 ms (`ContactQuerySync`) أو 128000 ms (`ContactSyncHelper`)؛ الرقم `102` يُمرر إلى المرسل (المعنى unknown) |

### 2.2 الأوضاع (found، `EnumC21780s1`)

| `mode` | المعنى |
|--------|---------|
| `full` | إعادة مزامنة كاملة للنطاق |
| `delta` | التغييرات فقط منذ آخر مزامنة |
| `query` | البحث عن المستخدمين المدرجين، دون تغيير الحالة |
| `download` | سحب مجموعة جهات الاتصال من جهة الخادم |

### 2.3 السياقات (found، `EnumC21770s0`)

`metadata`، `registration`، `interactive`، `background`، `notification`، `message`، `add`، `voip`، `snapshot`، `wamo`.

### 2.4 أنواع المزامنة (found، `EnumC21760rz`)

الاسم، رمز السلك (wire code)، السياق / الوضع / النطاق. الرموز 10-15 و17-20 غير مستخدمة. النطاق `PB` = دفتر الهاتف، `SL` = side list، `MP` = استعلام متعدد البروتوكولات. يُسجَّل الرمز ويُحفظ في المقاييس؛ أما stanza فتحمل السياق والوضع فقط.

| الأسماء (الرمز) | السياق / الوضع | النطاق |
|--------------|----------------|-------|
| `REGISTRATION_FULL` (0) | registration / full | PB+SL |
| `INTERACTIVE_FULL` (1)، `INTERACTIVE_DELTA` (2) | interactive / full، delta | PB+SL |
| `BACKGROUND_FULL` (3)، `BACKGROUND_DELTA` (4) | background / full، delta | PB+SL |
| `NOTIFICATION_CONTACT` (5) | notification / delta | PB |
| `INTERACTIVE_QUERY` (6)، `ADD_QUERY` (9) | interactive / query، add / query | PB |
| `NOTIFICATION_SIDELIST` (7) | notification / query | SL |
| `INTERACTIVE_DELTA_SIDELIST` (8) | interactive / delta | SL |
| `BACKGROUND_QUERY_PICTURES` (16)، `BACKGROUND_MULTI_PROTOCOL_QUERY` (21)، `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` (22) | background / query | MP |
| `REGISTRATION_COMPANION_MULTI_PROTOCOL_QUERY` (23) | registration / query | MP |
| `INTERACTIVE_MULTI_PROTOCOL_QUERY` (24)، `MESSAGE_MULTI_PROTOCOL_QUERY` (25)، `VOIP_MULTI_PROTOCOL_QUERY` (26) | interactive، message، voip / query | MP |
| `NOTIFICATION_MULTI_PROTOCOL_QUERY` (27)، `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY` (28) | notification / query | MP |
| `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` (29)، `WAMO_MULTI_PROTOCOL_QUERY` (38) | message، wamo / query | MP |
| `CONTACT_DONWLOAD` (30، sic) | background / download | PB |
| `CONTACT_FORCE_UPLOAD` (31) | metadata / delta | PB+SL |
| `CONTACT_UPLOAD` (32)، `NATIVE_CONTACT_DELTA` (39) | background / delta | PB |
| `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` (33) | background / full | PB |
| `CONTACT_UPLOAD_SNAPSHOT` (34)، `CONTACT_DOWNLOAD_SNAPSHOT` (35)، `CONTACT_FULL_SYNC_SNAPSHOT` (36) | snapshot / delta، download، full | PB، PB، PB+SL |
| `CONTACT_RESTORE_FULL_SYNC` (37) | background / full | دفتر عناوين WA |

دوال مساعدة: `A00()` = delta، `A01()` = full، `A02()` = full وregistration. النوع `BACKGROUND_QUERY_PICTURES` وحده يجعل نوع استعلام الصورة `image`؛ وكل نوع آخر يطلب `preview`.

---

## 3. بروتوكولات الاستعلام

### 3.1 نظرة عامة (found)

| البروتوكول | العنصر الفرعي في `<query>` | العنصر الفرعي لكل مستخدم في الطلب | العنصر الفرعي في الاستجابة (لكل مستخدم) | ملاحظات |
|----------|-----------------|------------------------|---------------------------|-------|
| contact | `<contact/>` | `<contact>+digits</contact>`، `<contact username=.. lid=.. pin=../>`، `<contact type="delete"/>`، `<contact/>` فارغ | `<contact type="in\|out\|invalid">text</contact>` | في `<list>` فقط |
| sidelist | `<sidelist [addressing_mode="lid"]/>` | `<sidelist type="delete"/>` | `<sidelist type=..>` في `<side_list>` | مستخدمون خارج دفتر العناوين |
| status | `<status/>` | `<status t="secs"/>` عند وجود وقت مخزَّن مؤقتًا | `<status t code type>text</status>` | نص "الحالة" (About) |
| text_status | `<text_status/>` | لا شيء | `<text_status last_update_time ephemeral_duration_sec text><emoji content/></text_status>` | flag **5839** |
| picture | `<picture type="image\|preview" [size="N"]/>` | `<picture id="N"/>` معرّف مخزَّن مؤقتًا | `<picture id direct_path hash/>` | مُثرى بالخصوصية |
| business | `<business><verified_name/><profile v="N"/></business>` | `<business><verified_name serial/><profile tag/></business>` | `<business pn_jid><verified_name verified_level host_storage actual_actors privacy_mode_ts>cert</verified_name>...</business>` | `v` = AB **471** & 0x3FFC (الافتراضي 1140) |
| devices | `<devices version="2"/>` | `<devices device_hash ts expected_ts/>` | `<devices><device-list><device id key-index is_hosted/></device-list><key-index-list ts expected_ts>bytes</key-index-list></devices>` | القسم 5 |
| disappearing_mode | `<disappearing_mode/>` | لا شيء | `<disappearing_mode duration t ephemerality_disabled/>` | `ephemerality_disabled` يُقرأ فقط مع flag **21235** |
| lid | `<lid/>` | `<lid jid="LID"/>` عندما يكون لمستخدم PN معروف LID | `<lid val="LID"/>` | القسم 6 |
| username | `<username/>` | `<username username="@known"/>` | `<username>text</username>` أو `contact@username` | انظر WA_USERNAME.md |

السمات لكل مستخدم على `<user>`: `jid` (PN أو LID)، `pn_jid` (مدخلات side-list)، `common_gid` (القسم 7). وقد يحتوي المستخدم أيضًا على عنصر فرعي `<tctoken>` يحمل بايتات الرمز المخزَّن. في الاستجابات يحمل `<user>` أيضًا `pn_jid` و`new_jid`؛ ويأخذ المحلل `jid`، ويرجع إلى `pn_jid` عند غياب `jid`.

### 3.2 Contact (found)

| الشكل | الشرط | ملاحظات |
|------|-----------|-------|
| `<contact>+15550001111</contact>` | بحث بالهاتف | سلسلة الرقم تُمرر كما أعطاها المستدعي؛ وفي عمليات البحث المبنية على JID تضيف `C23638AId.A05` البادئة `+` عندما يكون JID هو JID رقم هاتف و(`C11980aQ.A0M()` / AB **26739** مفعّل، أو النوع `ADD_QUERY`) |
| `<contact>15550001111</contact>` | مستخدم PN مع عنونة LID (`C11980aQ.A0L()`، AB **14565**) | أرقام بدون `+` |
| `<contact username="u" [lid=".."] [pin=".."]/>` | بحث باسم المستخدم | `lid` / `pin` فقط مع AB **12402**، وإلا `username` فقط |
| `<contact type="delete"/>` | طلب موسوم كمحذوف | إزالة من دفتر العناوين في مزامنة الرفع |
| `<contact/>` | مستخدم LID بلا اسم مستخدم | عنصر نائب |
| الاستعلام `<contact addressing_mode="lid"/>` | AB **14565** | مزامنة جهات اتصال بعنونة LID |
| الاستعلام `metadata_version="3"` | نوع delta وflag داخلي | الـ flag لا يُسند إلا من ثابت false في المسار المقروء، لذا على الأرجح لا يُرسل أبدًا (inferred) |

`type` في الاستجابة: `in` = مسجَّل (الرمز الداخلي 1)، `out` = غير مسجَّل (2)، `invalid` = رقم غير صالح (3)؛ وأي قيمة أخرى ترمي خطأ تيار تالف. يُلحق محتوى النص لكل `<contact>` بقائمة لكل مستخدم.

على مستوى النتيجة `<result><contact version refresh integrity snapshot_recovery>`: يُحتفظ بـ `version` في النتيجة، وثواني `refresh` تغذي انتظار المزامنة الكاملة (القسم 9)، و`integrity` هو `pass` (الافتراضي) أو `pending` أو `timelock` (داخليًا 1 / 2 / 3)، و`snapshot_recovery` (`pending` / `pass`) يُقرأ فقط مع flag **22410**.

### 3.3 الحالة والحالة النصية (found)

معالجة نتيجة `<status>`: `type="fail"` مع `code` بقيمة 401 / 403 / 404 = مخفية بسبب الخصوصية (الحالة الداخلية 2)؛ أي `fail` آخر = فشل (0)؛ نص غير فارغ بلا خطأ = مضبوط (1، و`t` * 1000 = وقت الضبط)؛ فارغ بلا خطأ مع إيقاف flag الحالة النصية = لا شيء (3). أسماء الحالات inferred.

مع تفعيل flag **5839**، يتجاوز العنصر الفرعي `<text_status>` الحالة 1 / 3: النص = `text`، الإيموجي = `<emoji content>` (الافتراضي "" عند الغياب)، وقت الضبط = ثواني `last_update_time`، الانتهاء = وقت الضبط + `ephemeral_duration_sec` عندما يكون أكبر من 0 (الحالة 3). الحالة المخفية (2) هي عقدة فشل بالرمز 401 / 403 / 404، وليست سلسلة فارغة.

### 3.4 الصورة والنشاط التجاري والوضع المؤقت (found)

| البروتوكول | تفصيل الطلب | تحليل الاستجابة |
|----------|----------------|------------------|
| picture | `type="preview"` مع `size` فقط عندما يكون AB `AbstractC36291cD.A06` أكبر من 0 (بحد أقصى 300)؛ و`id` لكل مستخدم فقط عند وجود معرّف مخزَّن مؤقتًا | `id` (int، -1 عند غياب `<picture>`)، `direct_path`، `hash` |
| business | `profile v` = `C35756Fe7.A00()` = AB 471 & 16380؛ و`serial` / `tag` لكل مستخدم فقط من صف النشاط التجاري المحلي | `pn_jid` (يملأ PN لمستخدم LID ويخزن زوج LID-PN)، `verified_name`: `verified_level`، `host_storage`، `actual_actors`، `privacy_mode_ts`، بايتات العقدة = الشهادة |

---

## 4. البحث عن جهات الاتصال واكتشاف أرقام الهواتف

### 4.1 عمليات البحث المفردة (found، `C23638AId`)

| الدالة | النوع | تبني | النتيجة |
|--------|------|--------|--------|
| `A0E(userJid, type, n)` | `INTERACTIVE_QUERY` أو `ADD_QUERY` فقط | JID المستخدم + contact، status، picture، business، disappearing_mode، lid، username؛ وdevices إن كان **5751**؛ وtext_status إن كان **5839** | `C43621q7` |
| `A0C` / `A0A(type, n, number)` | النوعان نفسهما | رقم الهاتف كـ `<contact>`؛ المجموعة نفسها (status فقط عندما يمرر المستدعي true) | `Pair(result, user)` |
| `A0B(type, n, number)` ("Lightweight") | أي نوع | الهاتف + contact، lid؛ وdevices إن كان **5751** | `Pair` |
| `A0D(type, numbers)` | أي نوع | أرقام متعددة: contact، status، picture، business، disappearing_mode، lid؛ وtext_status إن كان **5839** | مصفوفة مستخدمين |
| `A0F(lid)` | `INTERACTIVE_QUERY` | `<user jid=LID/>` + `<contact/><username/>` | اسم المستخدم لـ LID |
| `A0G(username, key)` | `INTERACTIVE_QUERY` | اسم المستخدم (+ المفتاح) كـ `<contact>`؛ وكذلك status، picture، business، disappearing_mode، lid، username فقط إذا كان **33609** false، وtext_status إن كان **5839** | WA_USERNAME.md |

الحمايات (found): فحص الشبكة (نتيجة `network_unavailable`)، منع التكرار أثناء التنفيذ بخرائط مفتاحها JID أو الرقم (الاستدعاء الثاني يعيد "skip too frequent query"، بلا نافذة زمنية)، `sid` لكل استدعاء، انتظار حتى 32000 ms ثم نتيجة المهلة. مع إيقاف AB **14565**، يُعاد كتابة LID JID ذي رقم هاتف معروف إلى ذلك الرقم قبل بناء الطلب (`AbstractC197018Zw.A0Y`؛ الاتجاه inferred من خطوة البادئة `+` التي تليه).

### 4.2 رموز النتيجة (`C43621q7`، الأسماء inferred من الاستخدام)

0 `A04` الشبكة غير متاحة؛ 1 `A08` تخطّي (لا شيء للإرسال أو تكرار مفرط)؛ 2 `A07` نجاح مع تغييرات (مسار إزالة جهة اتصال)؛ 3 `A06` نجاح؛ 4 `A03` فشل (نتيجة فارغة، مهلة، خطأ)؛ 5 `A05` تجاوز حد المعدل (خطأ النتيجة 429)؛ 6 `A02` استثناء. `A01()` صحيحة للقيم 1 و2 و3. قائمة `<list>` فارغة مع خطأ 429 في بروتوكول contact تعطي 5، وأي قائمة فارغة أخرى تعطي 4.

### 4.3 أي الميزات تصل إلى دفتر الهاتف (found)

| المسار | نقطة الدخول | النوع | البروتوكولات (`C21820s6`) |
|------|-------|------|------------------------|
| مزامنة كاملة في الخلفية (الجهاز الأساسي فقط) | `C18230lP.A0F(reason)` | `BACKGROUND_FULL` | كل شيء عدا orgs |
| مزامنة كاملة قسرية | الدالة المساعدة `A01`، المهمة الدورية `RunnableC23953AUi` الحالة 23 | `BACKGROUND_FULL`؛ الجهاز المرافق: `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` | contact (`A0J`) أو side list (`A0K`)؛ المرافق: الكل عدا contact / side list (`A0D`) |
| رفع قسري، رفع delta، تنزيل | `A07(reason)`، `A0G(reason)`، `A0C()` | `CONTACT_FORCE_UPLOAD`، `CONTACT_UPLOAD`، `CONTACT_DONWLOAD` | contact + lid (`A0G`) |
| تغيّر جهات الاتصال الأصلية | `A0J(reason, jids)` | `NATIVE_CONTACT_DELTA` | الكل عدا orgs |
| مزامنة مؤجلة بعد التسجيل | `A0L` (التفضيل `registration_contact_sync_delayed`) | `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` | contact + lid |
| جهة اتصال جانبية عند أول عرض | `A0E(contact)` | الأساسي: `INTERACTIVE_DELTA_SIDELIST`؛ المرافق: `INTERACTIVE_MULTI_PROTOCOL_QUERY` | الكل عدا orgs / الكل عدا contact وside list وorgs |

مجموعات البروتوكولات (ثوابت `C21820s6`، found): `A0S` username؛ `A0G` contact + lid؛ `A0P` status؛ `A0Q` text status؛ `A0O` picture؛ `A0F` business؛ `A0H` devices؛ `A0E` business + devices؛ `A0N` payment؛ `A0I` disappearing mode؛ `A0L` lid؛ `A0M` orgs؛ `A0D` الكل عدا contact وside list وorgs؛ `A0R` مثل `A0D` بدون lid؛ `A0J` contact + مجموعة `A0D`؛ `A0K` side list + مجموعة `A0D`؛ `A0C` الكل عدا orgs. يكون LID ضمنيًا عند مزامنة contact أو side list.

يحفظ `C21830s7` (SyncRequest) الخيارات بصيغة JSON: `sync_is_urgent`، `sync_only_if_changed`، `sync_only_if_registered`، `sync_clear_whatsapp_sync_data`، `sync_should_retry` وقيمة منطقية `sync_<protocol>` واحدة لكل بروتوكول (found)؛ القيمة الافتراضية للباني لإعادة المحاولة عدد صحيح 5 (المعنى inferred).

### 4.4 عمليات البحث المدفوعة بالإشعارات (found)

يدفع الخادم hash بدلًا من الرقم؛ فيحلّه العميل وينفذ استعلامًا.

| معالج الإشعار | الحمولة | المزامنة | البروتوكولات |
|----------------------|---------|------|-----------|
| `AnonymousClass145` (تحديث جهة اتصال)، `add` | حتى عنصرين فرعيين hash من النوع `pn` (الافتراضي) أو `lid`؛ الجهاز الأساسي فقط | `NOTIFICATION_CONTACT` | الكل عدا orgs |
| المعالج نفسه، update | hash بترميز base64 | `NOTIFICATION_SIDELIST` | status، picture، lid، username، text_status |
| إشعار الحالة `C1S0` | السمة `hash` (base64) | `NOTIFICATION_SIDELIST` (السبب `NOTIFICATION_STATUS`) | status فقط |
| إشعار الصورة `C1S0` | السمة `hash` | `NOTIFICATION_SIDELIST` (السبب `NOTIFICATION_PICTURE`) | picture فقط |
| إشعار النشاط التجاري `AnonymousClass142` (إزالة بلا jid مع `hash`) | hash بترميز base64 | `NOTIFICATION_SIDELIST` (السبب `NOTIFICATION_BUSINESS`) | مجموعة business (الثابت لم يُحل) |

يطابق الـ hash المستخدمين المحليين عبر `digest(user + "WA_ADD_NOTIF")` مقارنةً ببادئة البايتات (`AbstractC43461pq.A04`)؛ وخوارزمية الـ digest يختارها المستدعي (لم تُتتبع). "المزامنة القسرية" المُطلقة من الخادم (`RunnableC23951AUg`، السبب `SERVER_FORACE_SYNC`) تنفذ `BACKGROUND_FULL` أو النوع المرافق.

### 4.5 مزامنة جهات الاتصال عبر طفرات MEX (found، ليست USync)

جديد في هذا البناء: مزامنة جهات الاتصال بلغة Kotlin (`com.whatsapp.contact.sync.kmp`، `.handler`) تستخدم طفرات `w:mex` بدلًا من usync IQ. الإعداد `whatsapp-android-mex`، وقيم doc_id من أصل persist-id.

| العملية | doc_id | المتغيرات (found) | الاستجابة |
|-----------|--------|-------------------|----------|
| `ContactsDeltaSyncMutation` | `28247314474869813` | `context` (`SEARCH`, `OSAB_IMPORT`, `EMAIL_IMPORT`, `QR_SCAN`)، `primary_contacts_add[]`، `primary_contacts_remove[]` (`lid`، `modifier` = `BEST_EFFORT_DOWNGRADE_TO_WA_SIDE_CONTACT`، `normalized_phone`)، `side_contacts_add[]` | `xwa2_contacts_delta_sync`: `results[]` {`client_cached_lid`، `failed`، `detail` (union: raw_pn / primary_normalized_phone / lid / phone_status; side_status; username_status; email_status; normalized_phone)}، `retry_after_seconds` |
| `PrimaryContactsFullSyncMutation` | `36963099086669113` | لم يُقرأ | لم يُقرأ |
| `SideContactsFullSyncMutation` | `26880700761604398` | `context`، `cursor`، `side_contacts[]` (`client_cached_lid`، `normalized_phone`) مقسّمة إلى صفحات | `results[]` كما سبق، `retry_after_seconds` |

لم يُعثر على ما يتحكم باختيار هذا المسار مقابل مسار usync (unknown). `retry_after_seconds` هو المكافئ في MEX لـ `backoff` في usync.

---

## 5. مزامنة قائمة الأجهزة، key index، ADV

### 5.1 الطلب والاستجابة (found)

الطلب: العنصر الفرعي للاستعلام `<devices version="2"/>`؛ ولكل مستخدم `<devices device_hash="H" ts="T" expected_ts="E"/>`، ويُرسل فقط عند وجود hash (و`ts`، `expected_ts` فقط عندما تكونان أكبر من 0 وتكون `expected_ts` أكبر من `ts`). تأتي القيم من صف الجهاز المحلي (`C15070fj.A07/A00/A04`).

الاستجابة لكل مستخدم: إما أن يحتوي `<devices>` على `<error code text>` (تصبح حالة المستخدم -1، ويُسجل "parseUser/partial error") أو:

| العقدة | السمات | تُحلَّل إلى |
|------|------------|------------------|
| `<device-list><device .../>` | `id` (int)، `key-index`، `is_hosted` | `DeviceJid(user, id)` -> key index؛ عدم تطابق حالة hosted في JID مع `is_hosted` يبلّغ عن `invalid-hosted-flag` |
| `<key-index-list ts expected_ts>` | `ts` (ثوانٍ)، `expected_ts` (الافتراضي 0)، بايتات المحتوى | قائمة key-index موقَّعة، تُخزَّن خامًا |

قد يحمل `<devices>` على مستوى النتيجة `<error>` مع backoff (القسم 9). مسار MEX: `include_devices` مع `devices{hash, timestamp, expected_timestamp}`؛ تسميات سجل العميل للنتائج المُسقَطة: `devices_dropped_status_error`، `devices_status_indeterminate`، `devices_hash_match_noop`، `devices_dropped_empty_without_hash`، `devices_dropped_no_jid`، `devices_dropped_stale_timestamp`، `devices_dropped_adv_proto_missing`، `devices_dropped_adv_verify_failed`، `devices_dropped_adv_data_update_failed`، `devices_outcome_unset`.

### 5.2 فحوصات التحديث (found، `C51909N4g`، `C24230w2`)

| الفحص | السلوك |
|-------|-----------|
| قائمة key-index فارغة | "update keyIndex is empty"، لا تحديث |
| `ts` الاستجابة أقدم من المخزَّن | "timestamp is less than existing one"، يُسقَط |
| إعادة محاولة expected-ts القديم | ts الاستجابة أقل من المخزَّن، و`expected_ts` يساوي ts المخزَّن والقيمة المخزَّنة أقدم من التفضيل `adv_last_device_job_ts`: يسجل خطأ جلب usync ويُصدر حدث WAM `wam_adv_expected_ts_unavailable` (`C49716Ltt`)، ويعيد true (أثر المستدعي لم يُتتبع) |
| معلومات جهاز جديد | `C51909N4g.A00` يمسح expected ts المخزَّن عندما يكون ts الجديد مساويًا للمخزَّن أو أحدث منه؛ نوع الحساب يُشتق من مجموعة الأجهزة (`C9U.A01`) |

### 5.3 التحقق من key-index الموقَّع في ADV (found، `C24230w2.A07`، `A04`)

| الخطوة | التفصيل |
|------|--------|
| التحليل | بايتات key-index -> `ADVSignedKeyIndexList` (`C25786BAu`): `details` (**1**)، `account_signature` (**2**)، `account_signature_key` (**3**، اختياري) |
| المفتاح العام | هوية الجهاز الأساسي من مخزن الهوية المحلي؛ إذا حمل proto المفتاح `account_signature_key` وكان يختلف عن المفتاح المحلي، يُستخدم ذلك المفتاح ويُوسم `adv`؛ وعند غياب المفتاحين: تحذير "no primary identity" |
| التوقيع | التحقق من `account_signature` على `{0x06, 0x02} || details` بالمفتاح المختار (`AbstractC30195DBc.A08`)؛ يسجل الفشل "fail to verify account signature" ويُصدر حدث WAM (`C55912St`، 1 = المفتاح المحلي، 2 = مفتاح adv) |
| التفاصيل | `details` -> `ADVKeyIndexList` (`BCB`): `raw_id` (**1**)، `timestamp` (**2**)، `current_index` (**3**)، `valid_indexes` (**4**)، `account_type` (**5**) |
| تطابق الطابع الزمني | يجب أن يساوي `details.timestamp` السمة `ts`، وإلا "advTimestampMismatch" + حدث WAM `C2TD`، وتُرفض النتيجة |
| العمر | إذا كان `ts` أقدم من `min(35, AB 730)` يومًا (الافتراضي 35) وكان في `valid_indexes` أكثر من مدخل واحد: "advListTimestampInvalid"، تُرفض |
| Raw id | `raw_id` مختلف عن المخزَّن: "incoming key-index not matching local state, resetting"؛ الحساب الخاص على جهاز مرافق يسجل `device_self_invalid_index_list`؛ المستخدمون الآخرون: `C15070fj.A0G(user, "adv_key_index_list_validation_failed")` عندما لم تُحلَّل قائمة جديدة (الأثر لم يُتتبع) |
| التصفية | `filterDeviceWithKeyIndexList` (`C24230w2.A08`) تُبقي الجهاز عندما يكون هو الأساسي، أو يكون `key-index` الخاص به أكبر من 0 ومدرجًا في `valid_indexes`؛ وإلا يُسقَط مع حدث WAM (`C55932Sv`، القيمة 1 عندما يكون الفهرس 0). فهرس مخزَّن أكبر ينتج تحذيرًا فقط |

### 5.4 مهام مزامنة الأجهزة (found)

`DeviceSyncManager.A03(jids, type)` تضع `SyncDevicesJob` في الطابور (تتخطى المستخدمين الجاري تنفيذهم؛ والمستخدمون المعلّقون ينجون من إعادة التشغيل في التفضيل `pending_users_to_sync_device`). يختار `syncType` نوع المزامنة:

| `syncType` | نوع المزامنة | السياق | يُستدعى من (found) |
|------------|-----------|---------|---------------------|
| 0 / الافتراضي | `INTERACTIVE_MULTI_PROTOCOL_QUERY` | interactive | — |
| 1 | `MESSAGE_MULTI_PROTOCOL_QUERY` | message | `SyncDevicesAndSendInvisibleMessageJob` (مسار إرسال المجموعة `C22300su`، حجم المجموعة بين AB 934 وAB 1946، مهمة واحدة لكل مفتاح رسالة) |
| 2 | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | notification | مزامنة الحساب لأجهزته الخاصة (`C41431mS`) |
| 3 | `BACKGROUND_MULTI_PROTOCOL_QUERY` | background | رسالة واردة أو حالة فشل فيها فحص مرسل ADV (`DecryptMessageRunnable` / `StatusProcessingRunnable`، السجل `invalid adv sender`)، عدم تطابق بيانات ADV الوصفية (`C24230w2`)، إعادة تشغيل المستخدمين المعلّقين |
| 4 | `VOIP_MULTI_PROTOCOL_QUERY` | voip | إعداد تشفير المكالمة لجهاز غير أساسي (`C1A`، السجل `voip/encryption/schedule usync`) |
| 5، 6 | `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY`، `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` | notification، message | لم تُتتبع |

تستخدم الطلبات الخاصة بالأجهزة فقط `C21820s6.A0H`. تطلق `handleADVMetadata` (`C24230w2.A0A`) أيضًا تحديثًا من النوع 3 عندما تبلغ بيانات ADV الوصفية لرسالة واردة عن نوع حساب hosted يخالف الحالة المحلية (تُمسح الأجهزة أولًا)، أو عن طابع زمني أحدث من المخزَّن.

---

## 6. ربط LID

| الآلية | التفصيل (found) |
|-----------|----------------|
| بروتوكول `lid` | الاستعلام `<lid/>`؛ و`<lid jid=known LID/>` لكل مستخدم فقط عندما يكون لمستخدم PN بالفعل LID مخزَّن؛ الاستجابة `<lid val="LID"/>` تُخزَّن في نتيجة المستخدم |
| كتابة الربط | `N27.A03(users)`: LID = `new_jid` (إن كان JID من نوع LID) وإلا نتيجة `lid` وإلا `jid` المستخدم إن كان LID؛ PN = `pn_jid` وإلا `jid` المستخدم إن كان PN؛ تذهب الأزواج إلى مخزن ربط LID-PN في دفعة واحدة |
| `pn_jid` في business | مستخدم LID بلا PN يحصل على PN من `<business pn_jid>`؛ ويُخزَّن الزوج |
| Side list | مستخدمو الطلب يحملون `jid` = LID و`pn_jid` = PN عندما تكون عنونة LID مفعّلة (`C11940aM.A05`، تُحل عبر `C11500Zc.A00`، معرّف flag لم يُتتبع)؛ المسارات الاحتياطية تسجل `Sidelist: No LID provided` و`waContact_null` و`usernameLid_null` |
| إصلاح LID المفقود | `MissingLidHandler` (`C32M`): `requestSyncDevicesAndLidIfMissingLids` تنتظر 32000 ms لاستعلام `MESSAGE_MULTI_PROTOCOL_QUERY` مع بروتوكول lid قبل أن تتابع نقطة دخول خارجية |
| مراقب الربط | `ContactJidMapObserver` (`C0ZA`): عندما يظهر زوج LID-PN وتوجد جهة اتصال مهجورة (deprecated)، يضيف جهة الاتصال البديلة ويضع `BACKGROUND_DELTA` في الطابور بالسبب `LID_REQUEST` |

لماذا يهم غياب LID: لا يمكن عنونة جهة اتصال PN فقط في الإرسال الذي يفضّل LID؛ يملأ الاستعلام الزوج دون مزامنة كاملة (inferred من مواضع الاستدعاء).

---

## 7. إثراء الخصوصية (tctoken، مجموعة مشتركة)

يعمل `ProfilePrivacyEnrichmentFetcher` (`C223659jg.A00`، تسمية السجل `ContactSyncHelper.privacyEnrichment`) على قائمة الطلبات قبل الإرسال. لكل مستخدم يجلب (أ) رمز الخصوصية المخزَّن مع طابعه الزمني (`C14820fK.A0M`، يُسقَط عندما يكون أقدم من `C14820fK.A04.A02()`)، (ب) عند عدم وجود رمز صالح، JID لمجموعة مشتركة مع المستخدم (`C197178aC.A04` / بحث جماعي، يتطلب LID الخاص). النتيجة `C197148a9{ token C9oI, commonGroup, flag }`.

| المخرج | usync الكلاسيكي | MEX `UsyncQuery` |
|--------|---------------|------------------|
| token | عنصر فرعي `<tctoken>token bytes</tctoken>` لـ `<user>` | `privacy_token{tctoken, timestamp}` |
| المجموعة المشتركة | السمة `common_gid="..."` على `<user>` | `common_group` |

ينطبق فقط على الطلبات التي تسأل عن الصورة أو الحالة (AB **9667**، الافتراضي true)، والحالة النصية (**20798**، الافتراضي false)، والأجهزة (**29769**)، وcontact (**29770**)، وlid (**29771**) (الـ flags افتراضيًا false عدا 9667). بدون رمز أو مجموعة مشتركة قد يظل الخادم يجيب لكنه قد يُغفل الصورة أو الحالة (inferred؛ قاعدة الخادم unknown). إصدار الرموز و`cstoken` في WA_TCTOKEN_CSTOKEN.md.

ذو صلة: `PRIVACY_TOKEN_REFRESH` (`C735439k`) يصدر `BACKGROUND_QUERY_PICTURES` بمجموعة الصورة فقط `A0O` على دفعات من 10 مستخدمين (found)؛ أما أن الغرض هو تحديث ارتباط الرمز فهو inferred من اسم السبب.

---

## 8. MEX `UsyncQuery` وتوجيه البروتوكولات

### 8.1 العملية (found، `C229259vZ.A01`)

عملية `w:mex` ‏`UsyncQuery`، doc_id ‏`38635300486116501` (أصل persist-id)، فئة الاستجابة `C2IQ`. الغلاف كما في WA_USERNAME.md 2.2.

| المتغير | المصدر |
|----------|--------|
| `query_input[]` | لكل مستخدم: JID، `client_known_username`، `about_status{dhash}`، `picture{id}`، `business{serial, tag}`، `devices{hash, timestamp, expected_timestamp}`، `privacy_token{tctoken, timestamp}`، `common_group` |
| `telemetry.context` | سلسلة السياق بأحرف صغيرة |
| `include_username`، `include_reachability`، `include_linked_profiles`، `include_lid`، `include_about_status`، `include_picture`، `include_biz`، `include_ddm`، `include_devices`، `include_orgs` | قيم منطقية تُضبط عندما يطلب أي مستخدم البروتوكول |
| `picture_field_input` | `type` ‏`IMAGE` أو `PREVIEW`، و`preview_px` للمعاينات |
| `business_input` | `include_profile`، `include_vname`، `profile_version` |

لا يُحمل عبر MEX: contact وtext_status. حصرًا في MEX: reachability، linked profiles، orgs، ddm (الوضع المؤقت). تفاصيل الاستجابة عدا username وlid (WA_USERNAME.md) لم تُقرأ (unknown).

### 8.2 متى يُستخدم MEX (found، `C18580m0`)

1. AB **37780** (int، الافتراضي 0) غير صفري: توجيه لكل بروتوكول. أعلى 16 بت = قناع بتات يُوجَّه عبر usync الكلاسيكي (`SMAX`)، أدنى 16 بت = قناع يُوجَّه عبر MEX؛ و`DROP` خلاف ذلك. البتات (`M5H`): status 4، picture 8، business 16، devices 32، disappearing_mode 128، username 512، text_status 1024، orgs 2048. بتات مستوى الطلب 1 (contact) و2 (`C70582ym.A07`، على الأرجح side list، inferred) و256 تسافر كقناع "identity". البروتوكول الذي لا يستطيع المسار المختار حمله يُضبط على `DROP`: ‏text_status على MEX، وorgs على SMAX. سطر السجل هو `ContactSyncHelper/read_route type=.. contacts=.. identity=..,.. failed=..`.
2. وإلا مع AB **33432** (الافتراضي false): استعلام كلاسيكي للطلب الرئيسي، ثم "متابعة mex profile" (`..._mex_profile`) للأجهزة، مع علامة مقاييس موسومة بـ `requested_users` و`is_delta_sync` والنتيجة `success` و`partial_success` و`no_result` و`timeout` و`exception` و`interrupted`.
3. وإلا تقرر `A0F` لكل طلب: يُرفض MEX عندما يحتوي الطلب على contact أو text_status ("cantUseMex")، ويحتاج AB **9732** للنشاط التجاري وAB **8421** لاسم المستخدم؛ والباقي قد يمر عبر MEX (`C229259vZ`)، بانتظار 128000 ms.

الحالة الافتراضية لهذا البناء: 37780 = 0، 33432 = false، 9732 = false، 8421 = false، لذا يعمل USync عبر stanza الكلاسيكية ما لم يغيّر تجاوز AB من الخادم ذلك.

---

## 9. حدود المعدل، الأخطاء، backoff

### 9.1 أشكال الأخطاء (found)

| الموضع | الشكل | يحلله |
|-------|-------|-----------|
| خطأ iq | `<iq type="error"><error code backoff/></iq>` | `Brt`: ‏`code`، ثواني `backoff` * 1000 بحد أقصى 3600000 ms (-1 عند الغياب)؛ يستدعي `BIz(type, sid, code, backoffMs)`، ويُكمل الـ future بقيمة null |
| فشل التسليم | رد نداء النقل | `Bog`: يفشل الـ future بـ `C216419Uc`؛ وتُعاد حالة المزامنة لكل JID إلى الصفر (`C502424l.A01`) |
| خطأ بروتوكول | `<result><PROTO><error code text backoff/></PROTO></result>` | `C18670m9.A01`: ثواني `backoff` * 1000، الافتراضي 7200 s، الحد الأقصى 3600000 ms (ساعة واحدة)؛ يسجل `connection/unisynciq/parse/<proto>/error` |
| نجاح بروتوكول | `<PROTO refresh="n"/>` | ثواني `refresh` * 1000 |
| فشل جزئي على مستوى المستخدم | `<devices><error code text/></devices>` | الحالة -1، يبقى المستخدم |
| خطأ MEX | خطأ GraphQL، حقل المسار `<proto>_info`، سلسلة backoff اختيارية | `C229259vZ.A00`: القيمة الافتراضية لـ backoff **7200**، الحد الأقصى 3600000، بلا تحويل * 1000 في هذا المسار (الوحدات غير واضحة، unknown) |
| مفتاح username | الرمزان `42901` (الطالِب) و`42902` (المطلوب) في نتيجة contact | `C23638AId.A0G`، انظر WA_USERNAME.md |

رموز شوهدت في منطق العميل: `429` (حد المعدل: نتيجة المزامنة 5)، `503` (backoff عام)، `42901`، `42902`.

### 9.2 مخزن backoff (found، ملف التفضيلات `contact_sync_prefs`، `C18800mM`)

| المفتاح | يُكتب عندما | القيمة |
|-----|--------------|-------|
| `contact_sync_backoff` | أي خطأ iq / بروتوكول contact مع backoff أكبر من 0 (`X.0m7.BIz`، `AO4.BIz`) | الآن + backoff ms |
| `delta_sync_backoff` | الشرط نفسه، الوضع delta والرمز 429 | الآن + backoff |
| `global_backoff_time` | الشرط نفسه، الرمز 503 | الآن + backoff |
| `sidelist_sync_backoff` | رد نداء `ContactQuerySync` ‏`AO2.BIz` عند **أي** خطأ مع backoff أكبر من 0 | الآن + backoff؛ الرمز 503 يضبط أيضًا `global_backoff_time` (اسم المفتاح لا يطابق نطاق المزامنة؛ found) |
| `contact_full_sync_wait`، `status_full_sync_wait`، `sidelist_full_sync_wait` | السمة `refresh` لنتيجة البروتوكول | ms؛ غير مضبوط = 86400000 (24 ساعة) |
| `status_`، `picture_`، `business_`، `devices_`، `disappearing_mode_`، `lid_`، `username_`، `text_status_`، `reachability_` ‏`sync_backoff` | backoff خطأ نتيجة البروتوكول في `BJ0` | الآن + backoff |
| `last_contact_full_sync`، `last_status_full_sync`، `last_sidelist_full_sync` | اكتمال المزامنة الكاملة | طابع زمني |

تعيد `C18800mM.A02()` مفاتيح contact وsidelist وstatus وpicture وbusiness وdevices وdelta وdisappearing_mode وlid وreachability وglobal إلى -1؛ أما `username_sync_backoff` و`text_status_sync_backoff` فليسا في تلك القائمة (found).

القارئات التي عُثر عليها بالبحث النصي: `reachability_sync_backoff` (`C18580m0`)، `text_status_sync_backoff` (`C3MA`)، مفاتيح `*_full_sync_wait` الثلاثة و`last_*_full_sync` (المهمة الدورية: تستحق مزامنة كاملة عندما تكون `wait - now + last` أقل من أو تساوي 1800000 ms، أي 30 دقيقة). لم يُعثر على قارئ لـ `contact_sync_backoff` أو `delta_sync_backoff` أو `global_backoff_time` أو مفاتيح البروتوكولات الأخرى (unknown ما إذا كان الفحص يبني المفتاح ديناميكيًا).

### 9.3 الحدود المحلية (found)

منع التكرار أثناء التنفيذ: `querySyncJid` واحد لكل JID، واستعلام هاتف واحد لكل رقم. المهل: 32000 ms للبحث المفرد، 128000 ms للدفعة، 180 s لانتظار رد نداء `C18230lP.A00` (غير محدودة عندما تتحقق `C11980aQ.A09`). الحد الأقصى لـ backoff هو 3600000 ms. دفعات تحديث privacy-token من 10 مستخدمين. حدود الاستعلام من جهة الخادم لكل حساب ولكل رقم unknown.

---

## 10. ما الذي يطلق USync

السبب = قيمة `EnumC21800s4` (تسمية من العميل، تُستخدم للجدولة والمقاييس). النوع = نوع المزامنة.

| ميزة العميل | السبب | النوع | البروتوكولات |
|----------------|--------|------|-----------|
| انتهاء التسجيل | `REGISTRATION_FULL` (`C25100xS`، `CJ8`) | `REGISTRATION_FULL` (الرمز 0) | مجموعة contact (المتغير المرافق لم يُتتبع) |
| التهيئة الأولية لجهات الاتصال | `NC_ONBOARDING` | رفع delta بـ `A0G` (`CONTACT_UPLOAD`) | contact + lid |
| تغيّر دفتر عناوين الجهاز (الأساسي فقط) | `DEVICE_ADDRESS_BOOK_CHANGE` | delta عاجل عند التغيّر (`C18230lP.A02`) | لم تُتتبع |
| مزامنة كاملة دورية وقسرية | `PERIODIC_FORCE_SYNC`، `FORCE_SYNC` | `BACKGROUND_FULL` | contact / side list |
| فتح منتقي جهات الاتصال | `CONTACT_PICKER_FULL_SYNC`، `CONTACT_PICKER_USYNC_RETRY` | `INTERACTIVE_FULL` | لم تُتتبع |
| إضافة جهة اتصال، محادثة جديدة برقم، رابط عميق، محادثة بلا جهة اتصال | أسباب `*_CONTACT_ADD` موجودة؛ غير مربوطة بمسار الاستعلام | `ADD_QUERY` (`C9AA`) / `INTERACTIVE_QUERY` (`C9AQ`، `C9AY`، `AWR`، `A1P`) | انظر 4.1 |
| فتح محادثة مع مستخدم أو نشاط تجاري غير محفوظ | `CONVERSATION_SIDE_CONTACT`، `SIDELIST_REQUEST` | استعلام هاتف (`INTERACTIVE_QUERY`) عندما يكون AB **20988** (الافتراضي true)، وإلا `INTERACTIVE_DELTA_SIDELIST` | انظر 4.1 / 4.3 |
| إرسال رسالة إلى قائمة بث | `LID_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | lid |
| إرسال رسالة مجموعة (الحجم ضمن AB 934..1946) | `DEVICE_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | devices |
| رسالة واردة فشل فيها فحص مرسل ADV، عدم تطابق بيانات ADV الوصفية | `DEVICE_REQUEST` | `BACKGROUND_MULTI_PROTOCOL_QUERY` | devices |
| إعداد تشفير المكالمة | `DEVICE_REQUEST` | `VOIP_MULTI_PROTOCOL_QUERY` | devices |
| مزامنة الحساب الخاص | `DEVICE_REQUEST` | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | devices |
| دفع من الخادم: تغيّر contact أو status أو picture أو business أو username | `NOTIFICATION_*`، `USERNAME_UPDATE_NOTIFICATION` | `NOTIFICATION_CONTACT` / `NOTIFICATION_SIDELIST` | حسب الإشعار |
| تحديث الوضع المؤقت والحالة النصية | `DM_FORCE_REFRESH`، `TEXT_STATUS_FORCE_REFRESH` | `BACKGROUND_MULTI_PROTOCOL_QUERY` (والحالة النصية أيضًا `BACKGROUND_FULL`) | disappearing_mode / text_status |
| تبديل الحساب | `ACCOUNT_SWITCH_REFRESH` | `BACKGROUND_FULL` | لم تُتتبع |
| تحديث privacy token | `PRIVACY_TOKEN_REFRESH` | `BACKGROUND_QUERY_PICTURES` | picture |
| تغيّر ربط LID-PN | `LID_REQUEST` | `BACKGROUND_DELTA` | الكل عدا orgs |
| محادثة نشاط تجاري (إضافة رسالة، مكالمة) | `BUSINESS_CONTACT_CHAT` (`C0LX`، `RunnableC23932ATn`) | `BACKGROUND_MULTI_PROTOCOL_QUERY` / `VOIP_MULTI_PROTOCOL_QUERY` | لم تُتتبع |

---

## 11. Feature flags

معرّفات AB-prop كما قُرئت في مواضع الاستدعاء؛ والقيم الافتراضية من جداول الإعداد في هذا البناء. معرّفات الـ flags بخط عريض.

| Flag | النوع | الافتراضي | ما يتحكم به |
|------|------|---------|----------|
| **5751** | bool | false | طلب devices في استعلامات contact ورقم الهاتف |
| **5839** | bool | false | بروتوكول text_status (الطلب والتحليل) |
| **9667** | bool | true | إثراء الخصوصية لطلبات picture / status |
| **20798** | bool | false | إثراء الخصوصية لـ text_status |
| **29769**، **29770**، **29771** | bool | false | إثراء الخصوصية لطلبات devices وcontact وlid |
| **9732** | bool | false | business عبر MEX |
| **8421** | bool | false | username عبر MEX |
| **37780** | int | 0 | أقنعة توجيه البروتوكولات (أعلى 16 SMAX، أدنى 16 MEX) |
| **33432** | bool | false | فصل الاستعلام الكلاسيكي + متابعة MEX profile |
| **12402** | bool | false | `lid` و`pin` على `contact` الخاص بـ username |
| **14565** | bool | false | `addressing_mode="lid"` على contact، نص PN بالأرقام فقط |
| **26739** | bool | false | البادئة `+` على أرقام الهواتف |
| **471** | int | 1140 | `profile v` للنشاط التجاري (مقنَّع بـ 0x3FFC) |
| **730** | int | 35 | أقصى عمر لـ key-index في ADV بالأيام (بحد أقصى 35) |
| **31261** | bool | false | يضيف `@username` المعروف لكل مستخدم (`C223639je`) |
| **33609** | bool | true | عندما يكون true، يُسقط البحث بإدخال المفتاح العنصر `<username/>` |
| **20988** | bool | true | استعلام هاتف بدلًا من مزامنة side-list في محادثة نشاط تجاري غير محفوظ |

---

## 12. Baileys (`baron-baileys-v2`، مقارنةً بـ `src/WAUSync` و`Socket/socket.js` فيه)

| الموضوع | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| الغلاف | `iq to=s.whatsapp.net type=get xmlns=usync` + `usync{context, mode, sid, last="true", index="0"}` | السمات نفسها؛ `to` ضمني |
| الأوضاع | `query` (الافتراضي)، `delta` | وكذلك `full`، `download` |
| السياقات | `interactive` (الافتراضي)، `background`، `message`؛ ويظهر `voip` في قاعدة backoff الخاصة به | إضافة إلى `registration`، `notification`، `add`، `voip`، `metadata`، `snapshot`، `wamo` |
| البروتوكولات | يضيف `bot`، `feature`، `sidelist` كعنصر فرعي للاستعلام | لا عنصر فرعي `bot` / `feature`؛ مستخدمو sidelist يوضعون في `<side_list>` |
| contact | `<contact>phone</contact>`، اسم المستخدم مع `pin` / `lid`، `type` | الهاتف مع `+`، `type="delete"`، اسم المستخدم |
| الحالة المخفية | `code="401"` على `<status>` يعطي `''` | `type="fail"` مع 401 / 403 / 404 |
| دليل الخصوصية | `<tctoken>` تحت بروتوكول status فقط، عندما يحمل المستخدم رمزًا | `<tctoken>` لـ picture / status / غيرها و`common_gid` |
| backoff | ثواني `error backoff` * 1000، بلا حد أقصى | بحد أقصى ساعة واحدة |

| العرض (inferred) | السبب | الحل |
|--------------------|-------|-----|
| picture / status مفقودان لغير جهات الاتصال | لا tctoken ولا `common_gid` | إرفاق `<tctoken>` المخزَّن أو JID لمجموعة مشتركة لكل مستخدم |
| رفض قائمة الأجهزة | فحوصات `ts` / `raw_id` لـ key-index في القسم 5.3 | التحقق من أن `ts` يساوي `details.timestamp` الموقَّع |
| تجاهل backoff | يستخدم Baileys قيمة الخادم بلا حد أقصى | وضع حد أقصى ساعة واحدة، والانتظار لكل بروتوكول |

---

## 13. حالات الخطأ

| العرض | السبب | الحل |
|---------|-------|-----|
| `ContactQuerySync/querySyncJid: rate-limit-error` | خطأ نتيجة contact بالرمز 429، قائمة فارغة | انتظار `backoff` المُعاد، وتقليل معدل الاستعلام |
| `connection/unisynciq/parse/<proto>/error` | عقدة خطأ لكل بروتوكول | تخزين `backoff` لذلك البروتوكول فقط |
| `handleSyncContactError ... code=503` | حمل زائد على الخادم | backoff عام، وإعادة المحاولة لاحقًا |
| `sidelist-jid-absent-from-response` | أغفل الخادم مستخدم side-list مطلوبًا | يعلّم العميل المستخدم كمُزامَن لتجنب حلقة |
| `contactsyncDevicesupdater/update/verifyADVSignedKeyIndexList fail` | فشل فحص التوقيع أو proto أو الطابع الزمني | لا يُحدَّث صف الجهاز، ويوضع تحديث في الطابور |

---

## 14. فروق أساسية

| لا تخلط بين | التفصيل |
|----------------|--------|
| نوع المزامنة مقابل السبب | النوع (`EnumC21760rz`) يختار الوضع والسياق والنطاق؛ أما السبب (`EnumC21800s4`) فمجرد تسمية للجدولة والمقاييس |
| `list` مقابل `side_list` | مستخدمو دفتر العناوين مقابل مستخدمين خارج دفتر العناوين (جهات اتصال جانبية) |
| usync مقابل MEX `UsyncQuery` مقابل طفرات جهات الاتصال في MEX | ثلاث وسائل نقل لبيانات متقاربة؛ flags التوجيه في 8.2 و4.5 |
| نتيجة `<devices>` مقابل key index الموقَّع | قائمة الأجهزة غير موثوقة حتى تتحقق القائمة الموقَّعة (5.3) |
| `refresh` مقابل `backoff` | `refresh` = المدة التي يجوز فيها إعادة استخدام نتيجة جيدة، و`backoff` = المدة التي يجب الابتعاد فيها بعد خطأ |

---

## 15. التدفق الكامل

```
[Feature]         [ContactSyncMethods]            [UniSync builder / MEX]                [Server]
  │ trigger (10)         │                                  │                               │
  ▼                      ▼                                  │                               │
 reason + type ──► SyncRequest (protocol set, users)        │                               │
                         │ enrich: tctoken / common_gid (7) │                               │
                         │ route per protocol (8)           ▼                               │
                         └──► classic: <iq xmlns=usync><usync sid index last mode context> ─►│
                         └──► MEX: w:mex UsyncQuery {query_input, include_*} ───────────────►│
                                                            │◄── <usync><result> per protocol│
                                                            │     <list> <side_list>         │
                                                            ▼                               │
                    parse: contact in/out, status, picture, business,                       │
                           devices + key-index-list, lid val, username                      │
                                  │                                                         │
        ┌─────────────────────────┼─────────────────────────┐                               │
        ▼                         ▼                         ▼                               │
 devices: verify ADV sig,   LID/PN pairs ──► mapping   result errors: 429 / 503 / backoff   │
 ts, raw_id, valid_indexes  store (N27.A03)            ──► prefs; refresh ──► full_sync_wait │
        │ ok                                                                                │
        ▼                                                                                   │
 device rows updated ──► message fan-out, call setup, side-list chats use the new data      │
```

---

## 16. غير المعروف

| الموضوع | السبب |
|-------|--------|
| السمة `to` في iq | يضيفها المرسل؛ المرسل لم يُتتبع |
| الفرق بين `C10140Tq.A0A` (التسجيل) و`A06` | لم يُتتبع |
| قواعد الخادم لمعدل الاستعلام وحدود كل رقم وأي البروتوكولات يجوز للطالب قراءتها | العميل لا يرى سوى رموز الأخطاء |
| قارئات `contact_sync_backoff` و`global_backoff_time` و`delta_sync_backoff` | لم يُعثر على قارئ نصي |
| وحدات backoff في MEX | لا يوجد `* 1000` في `C229259vZ.A00` |
| أي مسار يفوز في الإنتاج | جميع flags التوجيه افتراضيًا معطلة في هذا البناء؛ قيم AB من الخادم unknown |
| حركة الشبكة الفعلية | تحليل ساكن فقط |
