<!-- src-sha1: 4762669c756eee4725aaf5af56633f2b59edd479 -->
# WhatsApp خصائص AB — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** خصائص AB / أعلام الميزات (feature flags) على Android: معرّفات الأعلام الرقمية وجداول القيم الافتراضية المطبوعة، القارئات المطبوعة وخيارات القراءة، طبقة MobileConfig (Stable IDs، أنواع الوحدات، `params_map_v4_u*`، `MetaConfigFetchMutation`)، IQ مزامنة الخصائص (`xmlns="abt"`: hash، refresh، refresh_id، delta، مفاتيح expo، أوزان العينات)، خصائص مستوى المجموعة، خصائص ما قبل التسجيل، التجارب على الجهاز (دون اتصال)، التخزين على الجهاز، تسجيل التعرّض (exposure)، مسارات التجاوز (override) والتنقيح، العلاقة بمعرّفات الأعلام المذكورة في التقارير الأخرى، فهرس الأعلام حسب المجال، المقارنة مع Baileys

---

## 1. ما هو (تقنيًا)

خصائص AB هي أعلام الميزات التي يتحكم بها الخادم في العميل. يُعرَّف كل علم برقم **config code** فقط (مثل `20548`)؛ ولا يوجد أي اسم للعلم داخل APK. يشحن العميل جدول قيم افتراضية مطبوعًا لكل رمز، ويطلب من الخادم القيم المتجاوِزة عبر IQ، ويخزّن الجواب في SharedPreferences، ويقرأه عبر فئة قارئ مجردة واحدة. تعمل طبقة ثانية مشتقة من Meta (MobileConfig) بجانبها ويمكن أن تصبح مصدر الحقيقة. جميع العبارات مستمدة من التحليل الساكن لـ APK المفكَّك؛ لم يُلتقط شيء على الشبكة. المستويات: **found** = قُرئ في الشيفرة أو البيانات، **inferred** = مستنتج، **unknown** = غير محلول. الأسماء المشوَّشة تختلف من إصدار لآخر وأُعيد حلّها في 2.26.41.6.

| الطبقة | الاسم في 2.26.41.6 | الدور |
|-------|----------------|------|
| أساس القارئ | `C00D` (abstract) | accessors مطبوعة، caches، exposure، مفتاح تبديل MobileConfig |
| المخزن الرئيسي | `C08J` (`extends C00D`، prefs `ab-props`) | يحمل خرائط القيم الافتراضية الخمس، ويقرأ جميع الأعلام العادية |
| مخزن ما قبل chatd | `C0D9` (prefs `ab-prechatd-props`) | أعلام تُجلب عبر HTTP قبل اتصال الحساب |
| المخزن الخاص | `C0ER` (prefs `ab-private-abprop`) | قيم التجارب على الجهاز، بنفس قيم `C08J` الافتراضية |
| خيارات القراءة | `C00F` (`AbPropsOptions`) | وضع exposure + تثبيت أول وصول |
| الواصفات المطبوعة | `C054909t` ABPropBoolean، `C055109v` ABPropInt، `C1OT` ABPropFloat، `C055009u` ABPropString، `C055209w` ABPropJson | id + القيمة الافتراضية في موضع الاستدعاء |
| مدير المزامنة | `C0D2` (`ABPropsManager`) | التخزين، hash، refresh، النسخ الاحتياطي، تحديث ما قبل chatd |
| الطلب / الاستجابة | `C27646BzW` (الطلب)، `C28894Cgv` (الاستجابة + الخطأ) | `<iq xmlns="abt">` |
| المُشغِّل | الفرع الافتراضي في `RunnableC48591z1` (السجل `MessageHandler/maybeGetNewAbProps`)، `C1S0` معالج `<... abprops/>` | متى يُرسل الجلب |
| خصائص المجموعة | `C41861nA` (`GroupAbPropsManager`)، `C502324k` (المُشغِّل)، `C28900Ch1` (الاستجابة) | قيم لكل مجموعة |
| MobileConfig | `C053409d` (factory)، `C054709r` (`InterfaceC054609q`)، `C06510El` (جدول Stable-ID)، `C34081Wt` / `C34091Wu` (lambdas مطبوعة)، `C06460Eg`، `C053809h` (جدول التجاوزات)، `CQN` + `C29448CqB` (الجالب)، `C41251mA` (منسّق الجلب) | محرك مدعوم أصليًا، جلب عبر MEX |
| Exposure | `C42831om`، `BxP`، `C27952CBv`، حدث WAM `C44051qo` (5504) | مفاتيح exposure |
| AB دون اتصال | `C24976ApB`، `C27629BzE`، `C60839RQl`، `ON0` / `ON1` / `C53973OMy`، `ConfigVariable` | إسناد التجارب محليًا |
| المراقبون | `C0NE` (3 callbacks)، 46 منفِّذًا، مثل `CY8` | يتفاعلون مع القيم المتغيرة |

النقاط الحاسمة:

- فضاء معرّفات الأعلام فضاء رقمي واحد (أقصى معرّف **39140**، و21,424 معرّفًا له قيمة افتراضية). أما `C05Z.A00(n)` و`C1XG.A0I(n)` وأعداد IQ الصحيحة الخاصة بالنوع ومعرّفات WAM فهي فضاءات أرقام مختلفة (القسم 12).
- الأسماء لا تصل إلى العميل أبدًا. لا في جداول القيم الافتراضية، ولا في استجابة المزامنة (`config_code` فقط)، ولا في أي مورد.
- هناك ثلاثة مسارات مزامنة متوازية: `abt` IQ (مستوى المستخدم)، و`abt` IQ مع `group=` (مستوى المجموعة)، وجلب MobileConfig عبر MEX (القسم 4).

---

## 2. نموذج العلم

### 2.1 الأنواع وجداول القيم الافتراضية (found، `C08J`)

تُبنى خمس خرائط غير قابلة للتعديل في مُنشئ `C08J` (`buildKeepingLast`، لذا فإن تكرار puts في الشيفرة المفكَّكة غير ضار). الأعداد هي معرّفات فريدة لكل خريطة:

| النوع | الخريطة | Accessors على `C00D` | المعرّفات | مثال |
|------|-----|---------------------|-----|---------|
| bool | `A1A()` | `A15(id)`، `A18(ABPropBoolean)`، `A0E(...)` | 16,668 (1,237 قيمتها الافتراضية `true`) | `9667` true |
| int | `A1C()` | `A0b(id)`، `A0f(ABPropInt)`، `A02(...)` | 3,530 | `996` 604800 |
| float | `A1B()` | `A0Z(id)`، `A0a(ABPropFloat)`، `A00(...)` | 177 | `31535` 0.0 |
| string | `A1E()` | `A0j(id)`، `A0n(ABPropString)`، `A08(...)` | 867 | `34350` regex |
| JSON | `A1D()` | `A0p(id)`، `A0r(ABPropJson)`، `A09(...)` | 182 | `21995` `{}` |

لا يوجد معرّف في خريطتين. القراءات الحرفية الساكنة (`A15(n)` و`A0b(n)` و`A0j(n)` و`A0Z(n)` و`A0p(n)`): 16,355 موضع استدعاء في `p000X` و`com`؛ وتُضاف إليها قراءات الواصفات (مواضع الإنشاء: 492 ABPropBoolean، منها 482 متمايزة، و259 ABPropInt، و30 ABPropFloat، و66 ABPropString، و12 ABPropJson).

حلّ القيمة الافتراضية (found، `C00D.A0D`، `A01`):

| الخطوة | القاعدة |
|------|------|
| 1 | قيمة مخزنة مؤقتًا في الذاكرة لهذه العملية |
| 2 | قيمة الخادم المخزنة في prefs `ab-props` تحت المفتاح `String.valueOf(id)` |
| 3 | القيمة الافتراضية من خريطة نوع المعرّف |
| 4 | القيمة الافتراضية في موضع الاستدعاء لواصف ABPropX (فقط عندما لا يكون للخريطة إدخال) |
| 5 | لا شيء: `IllegalArgumentException("Unknown BooleanField: <id>")` (int: `Unknown IntField`) |

لجميع واصفات ABPropBoolean المتمايزة البالغ عددها 482 يوجد المعرّف في الخريطة وتساوي القيمة الافتراضية الإنتاجية للواصف القيمةَ الافتراضية للخريطة. يختلف `debugDefaultValue` في ABPropBoolean عن القيمة الإنتاجية في 182 منها، لكنه لا يُقرأ في أي مكان إلا في `equals` / `hashCode` / `toString` (smali: الحقل `A02` مُشار إليه فقط داخل `09t`؛ وتستخدم accessors المعرّف والقيمة الافتراضية الإنتاجية فقط). ليس له أي أثر وقت التشغيل في هذا البناء.

### 2.2 تحليل القيمة عند التخزين (found، `C0D2.A00`)

| خريطة المعرّف | يُخزَّن كـ | التحليل |
|---------------|-----------|-------|
| bool | `putBoolean` | `Integer.parseInt(config_value) != 0` (الصيغة على السلك `"1"` / `"0"`) |
| int | `putInt` | `Integer.parseInt` |
| float | `putFloat` | `Float.parseFloat` |
| string | `putString` | كما هو |
| JSON | `putString` | يُتحقق منه بـ `new JSONObject(...)`؛ الفشل يسجّل `ABPropsManager/invalid format for config; configCode=...` ولا تُخزَّن الخاصية |
| معرّف في أي خريطة لا يوجد | `putString` | يُخزَّن كسلسلة؛ والقراءة المطبوعة لمثل هذا المعرّف لا قيمة افتراضية لها وتُلقي استثناءً (2.1 الخطوة 5) |

على خلاف جدول WA Web (تُسقَط الرموز المجهولة)، يحتفظ Android بالرموز المجهولة كسلاسل (found).

### 2.3 خيارات القراءة (found، `C00F` = `AbPropsOptions`)

| الثابت | exposureOptions | firstAccessValue | الاستخدام |
|----------|-----------------|------------------|---------|
| `A03` | WITH_EXPOSURE_LOGGING (1) | false | الافتراضي لجميع القراءات العادية (`A15`، `A0b`، ...) |
| `A02` | WITH_EXPOSURE_LOGGING | true | `A19(...)`، `A16`، قراءات bootstrap الخاصة بـ MobileConfig |
| `A06` / `A05` | WITHOUT_EXPOSURE_LOGGING (0) | false / true | يشتقها `A00()` |
| `A04` | WITH_URGENT_EXPOSURE_LOGGING (2) | false | مخزن ما قبل chatd عندما يكون العلم **24317** مفعّلًا |

`firstAccessValue = true` يثبّت أول قيمة تُقرأ في العملية داخل `C00D.A07` (ConcurrentHashMap)؛ والقراءات اللاحقة لذلك المعرّف تعيد القيمة المثبّتة حتى بعد مزامنة (found، `C00D.A0D`، `A0i`). القراءات العادية تستخدم cache `A0P`، الذي يمسحه `A0s()` بعد كل مزامنة.

### 2.4 مسار القراءة ومصدر الحقيقة (found، `C00D.A07` smali؛ أسماء المفاتيح مستنتجة من الاستخدام)

```
read(id)
  ├─ A14() true  (A0E && A0b && !A0S)  and A08 set  and MobileConfig context present
  │      └─► MobileConfig value via C34081Wt/C34091Wu  (Stable ID lookup, C054709r.B6F)
  └─ else
         ├─ legacy value: cache A0P ► prefs "ab-props" ► default map
         └─ if A0E && A0G (shadow): also read MobileConfig and compare (A0C)
```

| الحقل | المصدر | المعنى (inferred) |
|-------|--------|--------------------|
| `A0F` | pref `23048` (bool)، `C08J` فقط | MobileConfig مُهيَّأ لهذا الحساب |
| `A0E` | `A0F` أو pref `27668` (int) > 0 | MobileConfig نشط (`C08J` فقط؛ false لـ `C0D9` و`C0ER`) |
| `A0b` | pref `24896` | MobileConfig هو مصدر الحقيقة |
| `A0S` | pref `25403`، يُعاد قراءته في `A0s()` | تجاوز يعيد إلى المسار القديم |
| `A0G` | pref `22646` | المقارنة الظلية (shadow) مفعّلة |
| `A0c` | pref `38895` == 1 | cache لكل قراءة `A0d` لقيم MobileConfig |
| `A08` | AtomicBoolean، يُضبط في `C054709r.BN4` (تهيئة MobileConfig) | MobileConfig جاهز؛ وعندها فقط يُسلك مسار MobileConfig (found)؛ يُعاد ضبطه في المُنشئ إلى false |

جميع الحقول الستة هي نفسها خصائص AB، وتُقرأ مباشرة من ملف prefs عند الإنشاء (found). يبني الوضع الظلي سجل مقارنة `N25` ويرسل حدث field-stats (`C56612Vl`، القيمة `mobile_config_inconsistent_value`) بعيّنة 1 من كل العلم **22647** (الافتراضي 10) (found). عندما يكون MobileConfig هو المصدر ولا يملك المعرّف Stable ID، تعيد lambda المطبوعة `false` / `0` / `""` مع مصدر القيمة `INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`، وليس قيمة خريطة القيم الافتراضية (found في `C34081Wt`؛ الأثر على المعرّفات الـ 70 ذات القيمة الافتراضية فقط inferred).

---

## 3. طبقة MobileConfig

### 3.1 Stable IDs (found، `C06510El.A0J`)

`long[39141]` مفهرس بـ config code، مع 21,380 إدخالًا غير صفري. `C054709r.B6F(id)` يعيد الإدخال (0 = لا شيء). يوجد 21,354 معرّفًا في كلٍّ من خرائط القيم الافتراضية وهذا الجدول؛ و70 معرّفًا في القيم الافتراضية فقط، و26 في Stable-ID فقط.

| البتات | الحقل | الدليل |
|------|-------|----------|
| 0-15 | slot index | `C053809h.A00`: `j & 65535`؛ المعنى inferred |
| 32-47 | config index، `0..20780`، واحد لكل إدخال بترتيب المعرّفات | `C06460Eg.A00`: `(j >>> 32) & 65535`، `C053409d.A08(int)` |
| 48-53 | نوع القيمة: 1 bool، 2 int، 3 string أو JSON، 4 float | جدول تقاطعي مع خرائط القيم الافتراضية، دون استثناء |
| 54-59 | نوع الوحدة: 1 SESSIONLESS (564 معرّفًا)، 2 SESSIONBASED (20,781)، 6 GROUP (35) | جدول تقاطعي؛ القسم 3.2 |
| 60-63 | القيمة `2` إذا وفقط إذا كانت القيمة الافتراضية لـ bool هي `true` | 1,231 من 1,231 معرّفًا؛ 6 معرّفات ذات قيمة افتراضية true ليس لها Stable ID |

### 3.2 أنواع الوحدات و`params_map_v4_u*` (found)

يُحمَّل `assets/params_map_v4_u<N>.txt` بواسطة `N3E` حيث `N` = نوع وحدة MobileConfig (`AbstractC24817AmY.A00`): 0 NULL_VALUE، 1 SESSIONLESS، 2 SESSIONBASED، 3 PAGEID، 4 ADMINID، 6 GROUP، 7 FAMILY_DEVICE_ID، 8 FRLID، 9 AD_ACCOUNT_ID، 10 WEARABLE_DEVICE_OWNER_ID. اللاحقة هي نوع الوحدة، وليست عرض قيمة. تحمل المكتبة الأصلية سلسلة التنسيق نفسها `params_map_v4_u%d.txt` (`libmobileconfig-jni.so`).

| الملف | الوحدة | الإدخالات | مفتاح الإصدار | المعرّفات ضمن نطاق رموز WA |
|------|------|---------|-------------|------------------------------|
| `u1` | SESSIONLESS (قابلة للاستخدام قبل تسجيل الدخول) | 575 | 565 | 564 |
| `u2` | SESSIONBASED | 20,844 | 20785 | 20,781 |
| `u4` | ADMINID | 72 | 2 | 0 (المعرّفات 112607..121623) |
| `u6` | GROUP | 35 | 35 | 35 |

الإدخال (8 بايت، قيمتان u32 little-endian، تخطيط الترويسة كما في الملف: magic `v4`، فحص `0x7fff`، مفتاح الإصدار، العدد، hash من 32 محرفًا):

| الحقل | الاستنتاج |
|-------|---------|
| `int2 >> 12` | config code الخاص بـ WA: في `u1`/`u2`/`u6` يطابق جدول Stable-ID (564 / 20,781 / 35 تطابقًا) وخرائط القيم الافتراضية؛ والبتات الـ 12 الدنيا تساوي 0 لجميع الإدخالات عدا قلة |
| `int1` البتات الـ 16 الدنيا | قناع نوع القيمة: `0x881` bool، `0x1001` int، `0x1801` string/JSON، `0x2001` float (`u2`)؛ البت 15 مضبوط تحديدًا لقيم bool الافتراضية `true` (25 + 1,206 = 1,231) |
| `int1 >> 16` | رقم slot متسلسل (inferred) |
| معرّفات `u4` | خارج نطاق رموز WA؛ الغرض unknown |

البتات التسع الدنيا من `int1` تساوي 1 أو 129 فقط؛ وليست معرّف معامل.

معرّفات GROUP الـ 35 (found): 18205, 23245, 23246, 23397, 23398, 24075, 26013, 26269, 26270, 26862, 27009, 27025, 27247, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 33673, 34075, 34277, 34333, 35211, 35227, 35639, 35772, 36156, 36504, 36505, 37523, 37524, 38082, 38083. العلم **18205** يُقرأ لكل مجموعة بواسطة `GroupAbPropsManager` (القسم 4.7).

### 3.3 جلب MobileConfig عبر MEX (found، `CQN`، `C29448CqB`)

طفرة MEX `MetaConfigFetchMutation`، المخطط `whatsapp-android-www`، doc_id **28207206725568030**، الحقل الجذر `xwa2_mobile_config_fetch`. حقول الإدخال المضبوطة في `CQN`: `api_version`، `fetch_type`، `unit_type`، `unit_id`، `device_id`، `query_hash`، `query_string`، `bln_queries`، `mc_debug_id`، `mobile_app_universe_type`؛ وتكون دائمًا null في المسارات المقروءة: `batch_size`، `bln_li_hashes`، `bool_opt_policy`، `contact_point`. السجل: `WAMobileConfigFetcher/fetchWwwConfigs/request unit_type=...`. الاستجابة: blob إعدادات يُسلَّم إلى المدير الأصلي (`onComplete(true, blob)`)، إضافة إلى `ep_refresh_id` و`ab_key`. يُخزَّن `ab_key` كـ `mc_expo:sys:ab_key`.

`C41251mA` (`MobileConfigFetchCoordinatorImpl`) يقرر متى يعمل هذا الجلب بعد جلب خصائص AB: ABPropInt **36185** (الافتراضي 0) يختار الخيار: القيمة 2 تنتظر استئناف وضع عدم الاتصال (`waiting for offline resume`)، وكل قيمة أخرى تجلب الآن؛ والقيمة 1 تفحص إصدار الجلب المخزَّن لكل وحدة مقابل إصدار `abprops` (`C054709r.A01`)، وطلب delta يقارن إصدار التطبيق لآخر handle مع `2.26.41.6`. يستدعي `C054709r.CpO` الدالة `updateConfigs`، وسجل callback هو `WAMobileConfigFetcher/updateConfigs() callback: succeeded=`؛ والنجاح يخزّن `last_full_fetch_ms:<unit>:<key>`.

يحمل stanza `<success>` الخاص بتسجيل الدخول أيضًا `mc_ep_version` (إصدار emergency-push الخاص بـ MobileConfig) بجانب `props` و`abprops` (found، `HandlerThreadC12340b0`)؛ المستهلك لم يُتتبَّع.

---

## 4. مزامنة الخصائص

### 4.1 الطلب (found، `C27646BzW.A00(boolean force, boolean delta, int refreshId)`)

```xml
<iq to="s.whatsapp.net" type="get" id="..." xmlns="abt">
  <props protocol="1" hash="<stored config_hash | empty>" [refresh_id="<last_version>"]/>
</iq>
```

| السمة | القاعدة |
|-----------|------|
| `protocol` | ثابت `1` |
| `hash` | القيمة المخزَّنة `ab_props:sys:config_hash`؛ سلسلة فارغة عند ضبط `force` أو `delta`، أو عند عدم وجود شيء مخزَّن |
| `refresh_id` | فقط عند ضبط `delta` و`refreshId > 0`؛ القيمة = `ab_props:sys:last_version` المخزَّنة |
| send | `MessageClient.A0W(callback, node, id, 220, 32000L)`: عدد IQ الصحيح لنوع الطلب 220، المهلة 32,000 ms |

### 4.2 الاستجابة (found، `C28894Cgv.CFS`)

```xml
<iq type="result"><props ab_key="..." hash="..." refresh="86400" refresh_id="N" [delta_update="true"]>
  <prop config_code="20548" config_value="1" config_expo_key="..."/>     <!-- one per changed flag -->
  <prop event_code="1094" sampling_weight="N"/>                         <!-- event sampling, no config_code -->
</props><erid>...</erid></iq>
```

| العنصر | المعالجة |
|------|----------|
| `config_code` + `config_value` | تخزين مطبوع وفق 2.2، بمفتاح `String.valueOf(code)` |
| `config_expo_key` | يُخزَّن كـ `<code>_expo_key` عندما يكون غير فارغ وقد خُزِّنت القيمة (مفتاح exposure للتجربة / المجموعة التي ينتمي إليها الحساب؛ صيغة المفتاح unknown) |
| `ab_key` | يُخزَّن `ab_props:sys:config_key`؛ ويُضبط كسمة WAM **4473** (كلتا القناتين) عندما لا يكون MobileConfig هو المصدر |
| `hash` | hash المحتوى للمجموعة كاملة؛ يُخزَّن `ab_props:sys:config_hash`؛ والاستجابة بلا hash وبلا `delta_update` لا تغيّر أي قيم |
| `refresh` | ثوانٍ، الافتراضي 86400؛ يُخزَّن × 1000 ms في `ab_props:sys:refresh`، بحد أدنى 600,000 ms؛ لا يُحدَّث بواسطة delta |
| `refresh_id` | إصدار المجموعة؛ يُخزَّن `ab_props:sys:last_version` (وبعد delta أيضًا) |
| `delta_update="true"` | دمج في prefs الموجودة؛ يُترك hash والمفتاح وrefresh و`last_refresh_time` دون تغيير |
| hash موجود | تُنسخ prefs السابقة إلى `ab-props-backup` (تُمسح أولًا) |
| تحديث كامل (hash موجود، وليس delta) | يُمسح المخزن (مع الإبقاء على `refresh` و`last_exposure_keys`)، وتُكتب جميع الخصائص |
| `event_code` + `sampling_weight` | صفوف بلا `config_code`؛ تُعاد كتابتها في prefs `field-stats-events-sampling` (المفتاح = رمز الحدث، القيمة = الوزن)؛ والرمز **1094** يضبط أيضًا `app_launch_event_sampling_weight` |
| `<erid>` | rid مشفّر: مع تفعيل العلم **3664** يُمسح، ومع تفعيل **6084** وتغيّر القيمة يُخزَّن كـ `encrypted_rid` |

بعد تحديث كامل ناجح: `last_refresh_time` = الآن (ms)، و`fetch_app_version` = `2.26.41.6`، وتُعاد ضبط عدّادات الأخطاء، ويُبلَّغ المراقبون (4.8).

### 4.3 المُشغِّلات (found ما لم يُذكر خلاف ذلك)

| المُشغِّل | الشرط |
|---------|-----------|
| تسجيل الدخول `<success abprops="N">` (و`props` و`mc_ep_version` أيضًا) | الإصدار `N` > `last_version` المخزَّن: طلب مع `force` + `delta` + `refresh_id`؛ الوضع DELTA (السجل `versionMismatch`) |
| المسار نفسه | `last_refresh_time + refresh < now`، أو `now < last_refresh_time` (تراجع الساعة؛ الفرع مقروء في smali، والشيفرة المفكَّكة تحذف else): طلب عادي مع hash المخزَّن؛ الوضع FULL (السجل `AB Props too old`) |
| عنصر ابن وارد `<... abprops/>` (يُوجَّه مع العنصرين الابنين `log` و`push-config`؛ العنصر الأب `ib` inferred) | `forceFetchABPropsAndMobileConfig`: `A00(true, false, 0)` (hash فارغ، كامل) عندما يكون إرسال الرسائل جاهزًا؛ ثم MobileConfig `BMu` + `CpO` |
| التسجيل | جلب ما قبل chatd (4.6)؛ إسناد دون اتصال (6) |

### 4.4 فترة التحديث والأخطاء (found)

| العنصر | القيمة |
|------|-------|
| الفترة الافتراضية | `ab_props:sys:refresh` الافتراضي 86,400,000 ms |
| `refresh` من الخادم | ثوانٍ، × 1000، بحد أدنى 600,000 ms |
| رموز الأخطاء المعدودة | 207، 304، 400-503 (`C28894Cgv.Brt`)؛ الرموز الأخرى تسجّل فقط `unknown error code` |
| احتساب إعادة المحاولة | `fetch_attemp_count` +1 لكل خطأ؛ عند 3 يصبح `last_refresh_time` = الآن ويُعاد ضبط العدّاد، فتنتظر المحاولة التالية فترة واحدة |
| آخر خطأ | `ab_props:sys:last_error_code`، يُمسح عند النجاح |
| فشل التسليم (`Bog`) | no-op |

### 4.5 القراءات أثناء نافذة الجلب

يمكن أن يصل `<props>` بعد أن تقرأ الشاشات الأولى الأعلام. القراءة الأولى لمعرّف قبل توفّر البيانات تستخدم القيمة الافتراضية؛ ومع تثبيت `firstAccessValue` (2.3) تبقى القيمة الافتراضية المثبّتة طوال العملية (found)؛ وتنتظر شاشات التسجيل مع مهلة وصول الخصائص عبر الاتصال (سلاسل السجل `RegisterPhoneViewModel/cancelOnlineAbPropsTimeout` و`OnlineAbpropsAsyncStatus`، found؛ مدة الانتظار الدقيقة unknown).

### 4.6 خصائص ما قبل chatd (found، `C44707Jfc`، `C43414Iwr`، `K49`، `C0D2.A08`)

قبل اتصال الحساب، يستدعي عميل HTTP الخاص بالتسجيل `checkPreChatdABProps` (`reg-onboard-abprop-request`) مع `ab_hash` (pref `pref_pre_chatd_ab_hash`). تحمل النتيجة hash جديدًا، ومصفوفة JSON باسم `expConfigs` من `{config_code, config_value, config_expo_key}`، و`ab_key`، وتأخيرًا للجلب التالي (`pref_pre_chatd_ab_next_fetch_time` = الآن + التأخير). يمسح `C0D2.A08` مخزن ما قبل chatd (`A04`) ويعيد كتابته بقواعد الطباعة نفسها (2.2) في prefs `ab-prechatd-props`. يُحفظ exposure في `pref_expo_keys` (مصفوفة JSON من `<expo_key>,<timestamp>`) ويُرسل عبر سجل قمع التسجيل (`abprop_exposure` / `ab_prechatd_exposure`، مع `ab_key` من `pref_pre_chatd_ab_key`)، وليس عبر WAM 5504. قراءات ما قبل chatd تستخدم الخيار `A04` (urgent) عندما يكون العلم **24317** مفعّلًا، وإلا `A03`.

### 4.7 خصائص مستوى المجموعة (found، `C41861nA`، `C502324k`، `C28900Ch1`)

```xml
<iq to="s.whatsapp.net" type="get" xmlns="abt"><props group="<group jid>" hash="<cached | empty>"/></iq>
```

النوع 220 والمهلة 32,000 ms نفسهما كما في 4.1. مصفوفة سمات الطلب فيها إدخالان: `group` و`hash` (smali). البوابة: العلم **16206** (الرئيسي) وفتح محادثة مجموعة (`COK` / `Bnc`)؛ يُتخطّى مع `reason=cacheValid` حتى `_nextRefreshTimeInSeconds`، أو `reason=disabled`. الاستجابة: `hash`، و`refresh` مقيَّد بين 600..604,800 ث (الافتراضي 86,400)، و`refresh_id`، و`<prop config_code config_value config_expo_key>`، مطبوعة بخرائط القيم الافتراضية نفسها (bool وint وfloat، وإلا string). المعرّفات في فضاء المعرّفات المشترك؛ ونوع الوحدة GROUP (3.2) يحدد المعرّفات الـ 35 المخصصة له، والعلم المقروء لمجموعة هو `A04(groupJid, id)`. تعيد القراءات `null` عندما لا تملك المجموعة قيمة مخزَّنة (يعود المستدعي حينها إلى بديل، لم يُتتبَّع). المفاتيح في prefs المجموعة (`groupAbProps`، الاسم inferred من `C00E`): `<jid>_<id>_value`، `<jid>_<id>_exposureKey`، `<jid>_exposureKeysSet`، `<jid>_nextRefreshTimeInSeconds`، `<jid>_lastRefreshHash`. لا يوجد نوع JSON لقيم المجموعة.

### 4.8 المراقبون (found)

لدى `C0NE` ثلاثة callbacks: `BhX` قبل كتابة القيم الجديدة (الحدث 34)، و`Bfk` و`C2K` بعدها (الحدثان 33 و32). مثال `CY8` (`PQKeysUploadABPropsObserver`): يتذكر العلم **21198** في `BhX`؛ وإن انتقل من `true` إلى `false` في `Bfk`، يسجّل `PQ_KEYS_UPLOAD_CODE changed from true to false, deleting all kyber prekeys` ويضع `DeleteKyberPreKeysJob` في الطابور. 46 فئة تنفّذ `C0NE` (عدد grep).

---

## 5. التخزين على الجهاز

| ملف / مفتاح Prefs | المحتوى |
|-----------------|---------|
| `ab-props` (`C08J`، `C0D2.A00`) | قيمة `<id>`، و`<id>_expo_key`، ومفاتيح `ab_props:sys:*` أدناه |
| `ab_props:sys:config_hash`، `config_key`، `last_version`، `refresh`، `last_refresh_time`، `fetch_app_version`، `fetch_attemp_count`، `last_error_code` | حالة المزامنة |
| `ab_props:sys:last_exposure_keys` (مجموعة سلاسل)، `last_daily_expo_key_update` | حالة exposure |
| `ab_props:sys:private_experimentation_id` | معرّف عشوائي للتجارب على الجهاز (6) |
| `ab_offline_props:offline_exposure_strings`، `ab_offline_props:offline_exposure_hash_strings` | exposure للتجارب دون اتصال (في `ab-props`) |
| `ab-props-backup` | نسخة من المخزن السابق، تُعاد كتابتها عند كل تحديث كامل |
| `ab-prechatd-props` | قيم ما قبل chatd إضافة إلى `pref_expo_keys` |
| `ab-private-abprop` | `last_read_time_ms` (يُحدَّث مرة كل ساعة كحد أقصى) والقيم الخاصة |
| `mc_expo:sys:ab_key`، `mc_expo:sys:last_exposure_keys`، `mc_expo:sys:last_exposure_keys_without_logging` | حالة exposure من جانب MobileConfig |
| `field-stats-events-sampling` | رمز الحدث إلى وزن العيّنة |
| `groupAbProps` | قيم المجموعات (4.7) |
| `<dataDir>/mobileconfig/mc_overrides.json`، `id_name_mapping.json` | جدول تجاوزات MobileConfig، وخريطة المعرّف-الاسم (أسماء الملفات found في `C053409d`؛ غير موجودة في APK) |
| `pref_pre_chatd_ab_hash`، `pref_pre_chatd_ab_key`، `pref_pre_chatd_ab_next_fetch_time`، `pref_is_blocking_prechatd_exposure` | حالة ما قبل chatd (prefs التسجيل) |

تُفتح جميع الملفات عبر `C00S.A05(name)` (مقبض `SharedPreferences` في دليل البيانات الخاص بالتطبيق)؛ ولم يُفحص ما إذا كان هذا المصنع يضيف تشفيرًا أو تعتيمًا (unknown).

---

## 6. Exposure والتجارب والمجموعات

### 6.1 تسجيل Exposure (found)

| الخطوة | التفصيل |
|------|--------|
| 1 | قراءة مع تسجيل exposure (2.3) تستدعي `A0B(options, this, "<id>_expo_key")` -> `A12` |
| 2 | مفتاح expo غير فارغ لم يكن بعدُ في `last_exposure_keys`: يُضاف ويُحفظ |
| 3 | المخزن الرئيسي: `C42831om.A01` ينشر حدث WAM **5504** `WamWefrClientExposure` (`wam_wefr_client_exposure`)، مع debounce لا يقل عن ثانية واحدة؛ و`BxP` يستدعي وقت تشغيل WAM (`C0D6.CYl(value, 5029, ...)`؛ "attribute" inferred من شكل الاستدعاء) مع المفاتيح المربوطة بفواصل (دمج لكل مصدر عندما يكون العلم **31830** مفعّلًا) |
| 4 | بعد مزامنة كاملة تبقى في المجموعة فقط المفاتيح التي لا تزال الاستجابة الجديدة تحملها |
| 5 | إعادة الإرسال اليومية: عند callback التحول إلى المقدمة `A0A0.BvR`، إذا مرّ أكثر من 24 ساعة منذ `last_daily_expo_key_update` (`sent_with_daily` = true) |
| 6 | ما قبل chatd: خيط النبض `C27952CBv` يرسل سجل القمع (4.6)؛ ووضع URGENT يُطلقه فورًا |

حقول WAM 5504 (أسماء Falco): `dedup_key`، `device_exp_id`، `exposure_key`، `from_metaconfig`، `sent_with_daily`. `device_exp_id` سلسلة مشتقة من كائن هوية الجهاز (`C09E.A0J().A03()`)؛ الاشتقاق لم يُتتبَّع (unknown).

### 6.2 معرّفات التجارب والمجموعات

| المعرّف | الموضع | المعنى |
|----|-------|---------|
| `config_expo_key` | لكل `<prop>` | مفتاح exposure لذراع التجربة؛ معتَّم بالنسبة للعميل، يُقارَن ويُسجَّل فقط |
| `ab_key` | سمة `<props>` | مفتاح المجموعة المسندة كاملة؛ سمة WAM 4473 |
| `refresh_id` | سمة `<props>` | إصدار المجموعة؛ يُقارَن مع `abprops` في `<success>` الخاص بتسجيل الدخول |
| `hash` | سمة `<props>` | hash المحتوى المستخدم لـ "لا تغيير" |
| `private_experimentation_id` | محلي | معرّف عشوائي يُستخدم كوحدة للتجارب على الجهاز |
| `device_id`، `unit_id` | جلب MEX | هوية وحدة MobileConfig |

الاستهداف من جانب الخادم (البلد، الشريحة، النسبة المئوية) غير مرئي؛ لا يرى العميل سوى القيم الناتجة (unknown).

### 6.3 أوزان العيّنات (found)

صفوف `<prop event_code sampling_weight>` تغذّي مسجِّل field-stats: وزن عيّنة 1 من N لكل حدث. الحدث **1094** (إطلاق التطبيق) يُعكَس إلى `app_launch_event_sampling_weight`. المفتاح هو رمز حدث WAM، وليس معرّف علم.

---

## 7. التقييم المحلي والتجاوزات ومسارات التنقيح

### 7.1 AB دون اتصال (found، `C24976ApB`، `C27629BzE`، `C60839RQl`)

التجارب المُجمَّعة داخل APK (`C60839RQl.A00`، قائمة `ON0` -> `ON1` -> `C53973OMy` -> `ConfigVariable{id, name, value, type}`) تُقيَّم مقابل خريطة معلومات مستخدم محلية وتُكتب في مخزن `ab-props` بقواعد الطباعة نفسها. يجوز للشروط (شجرة `RM2`) استخدام الخصائص `platform` و`app_version` و`app_build` و`release_channel` و`os_version` فقط (`C0ER.A0B`). مفاتيح معلومات المستخدم: `device_id`، `app_build`، `release_channel`، `app_version`، `os_version`، `platform`، `country` (بلد SIM)، `private_experimentation_id`. في هذا الإصدار التجريبي، `app_build` و`release_channel` هما الثابت `beta`. عند الإسناد تُزال مفاتيح المزامنة (`config_hash`، `last_refresh_time`، `fetch_app_version`، `last_version`) ليكون الجلب التالي عبر الاتصال كاملًا، ويُطلَق سجل حرج `abprops-offline-assigned-after-registration-verified` عندما يحدث الإسناد مع `registration_state == 3`. تعريفات التجارب غير مُعدَّدة هنا (unknown).

### 7.2 تجاوزات MobileConfig (found، الأثر inferred)

يحمّل `C053809h` الملف `mc_overrides.json` (`hasOverridesFile`، `boolOverrideForParam`، `intOverrideForParam`، `stringOverrideForParam`، `doubleOverrideForParam`، مفهرسة بـ Stable ID المعبّأ بـ 64 بت)، ويعيده `C053409d.getOrCreateOverridesTable` إلى المحرك. تنطبق التجاوزات على مسار MobileConfig فقط، وليس على مسار prefs القديم. ما إذا كان المحرك يستشير الجدول في بناء release unknown؛ ولا دليل على اختبار وقت التشغيل.

### 7.3 رابط `override-abprops` العميق (found)

مضيف manifest ‏`whatsapp-consumer://override-abprops` (اسم مستعار مُصدَّر لـ `DeepLinkActivity`). يربطه `IJB` بمعرّف الوجهة 154. تحلل `DeepLinkActivity.A0w` مقطع المسار `bugbash` ومعاملات الاستعلام `feature_name` و`feature_id` و`category` و`min_app_version` و`ready_to_test_time` و`variants` (مصفوفة JSON بصيغة base64 من `{label, abprops:[{abprop_key, abprop_value}]}`) إلى `BugBashSession` / `BugBashVariant`. يوجد سبب خطأ `abprop_override_not_allowed`. لم يُعثر على شيفرة تكتب `abprop_key` / `abprop_value` في أي مخزن خصائص: `BugBashVariant` مُشار إليه فقط من المحلل والمسلسِل الخاص به، و`bugbash_session` يُقرأ فقط (`C51723Mxj`). شرط البوابة ومسار التطبيق unknown.

### 7.4 أخرى

| المسار | التفصيل |
|------|--------|
| ABPropBoolean `debugDefaultValue` | مُعلَن (182 تختلف)، لا يُقرأ أبدًا (2.1) |
| واجهة التنقيح | `com.whatsapp.backup.debugscreen.BackupAbPropsUiState` (اسم الفئة فقط، شاشة تنقيح النسخ الاحتياطي) |
| محلل الأداء لكل قراءة | prefs `31165` (int) و`32010` (bool) تغذّيان `C00D.A0H/A0I/A0J` وفئة عدّاد (`Pr8`)؛ الغرض غير محلول |

---

## 8. معرّفات الأعلام المذكورة في التقارير الأخرى (تم التحقق في 2.26.41.6)

بُحث عن كل معرّف في خرائط القيم الافتراضية وجدول Stable-ID. الأنواع هي أنواع الخرائط.

| التقرير | النتيجة |
|--------|--------|
| `WA_BAN_SYSTEM_DEEP_EN.md` | 11061، 11064، 11065 (int 86400)، 12709، 16349، 19793، 19893، 26697، 27269، 14837، 25631 موجودة، bool قيمتها الافتراضية false؛ 12840 و20278 خريطتا **JSON** (القيم الافتراضية تتطابق)؛ 31535 / 31536 من نوع **float**، القيمة الافتراضية 0.0. **34166 ليس علمًا**: لا قيمة افتراضية، ولا Stable ID؛ `ContactInfoActivity.A0K = C1XG.A0I(34166)` هو معرّف حقن (الجيران 34165 و34168 و34169 من النوع نفسه). 2923 غائب (كما ورد) |
| `WA_TCTOKEN_CSTOKEN.md` | جميع المعرّفات الـ 16 موجودة؛ القيم الافتراضية: 996 / 865 / 26897 = 604800، 997 / 909 = 4، 3802 / 22012 = 26، 4063 = 0، 20606 = 2000، وجميع معرّفات bool قيمتها false. `299` هو عدد IQ الصحيح لنوع الطلب الخاص بـ IQ رمز الخصوصية، وليس علمًا |
| `WA_META_AI.md` | 25119، 26189، 27083، 37227، 37852، 37054 bool false؛ **26190 هو JSON**، القيمة الافتراضية `""` |
| `WA_USERNAME.md` | جميع المعرّفات الـ 18 موجودة بالقيم الافتراضية الموثّقة؛ **34350 إدخال خريطة string** (regex)، **21995 إدخال خريطة JSON** |
| `WA_USYNC.md` | جميع معرّفات الأعلام الـ 21 موجودة بالقيم الافتراضية الموثّقة (730 = 35، 471 = 1140، 9667 / 33609 / 20988 = true) |

يظهر فضاء الرموز نفسه على WA Web: بالنسبة لـ 11 اسم خاصية معروفًا من جدول خصائص WA Web العام، يملك إدخال Android الرمز والنوع والقيمة الافتراضية نفسها (مثل 22797 JSON `{}`، 32276 string `info_card, list_card`، 26270 int 1209600، 35639 int -1، 12539 bool true، 25071 / 1133 / 23245 / 28357 / 27009 / 6939 bool false) (found من جهة Android، inferred بالنسبة لـ "الخاصية نفسها"). المعرّفات الخاصة بـ Web فقط (3042، 30590، 24037، 25322) ليس لها قيمة افتراضية في Android. 12 من أصل 16 معرّف مستوى مجموعة في Web هي معرّفات وحدة GROUP في Android (3.2).

---

## 9. التسمية والفئات

| الموضوع | الاستنتاج |
|-------|---------|
| الأسماء | لم يُعثر على جدول أسماء مقروء في dex أو assets (بحث عن اسمي علمين قديمين معروفين طابق سلاسل السجل فقط)؛ و`id_name_mapping.json` مجرد اسم ملف وقت التشغيل في `C053409d` |
| الأسماء في السجلات | بعض سلاسل السجل تعيد استخدام أسماء: `PQ_KEYS_UPLOAD_CODE` (21198)، `abprop_override_not_allowed`؛ والأسماء من الإصدارات الأقدم أو من WA Web هي الطريق الوحيد إلى الدلالات |
| الفئات | لا حقل فئة. تأتي البنية من نوع الوحدة (SESSIONLESS 564، SESSIONBASED 20,781، GROUP 35) ونوع القيمة |
| الأكثر قراءة | المعرّفات الحرفية الأكثر قراءة: **20548** (bool true، 511 موضعًا)، **9970** (false، 312)، **1107** (false، 151)، **12267** (true، 147)، **1600** (string `{"allowed_product_type":"none"}`، 146)، **27008** (false، 104)، **13989** (int 7، 87). الدلالات غير محلولة |

---

## 10. فهرس الأعلام حسب المجال (القيم الافتراضية found في `C08J`؛ الاستخدام مقروء من التقارير الأخرى وأُعيد فحصه هنا)

### 10.1 المزامنة وبنية MobileConfig التحتية

| العلم | النوع | الافتراضي | ما يتحكم به |
|------|------|---------|----------|
| **23048** | bool | false | MobileConfig مُهيَّأ (`A0F`) |
| **27668** | int | 0 | `AbstractC06100Cm.A0E`؛ > 0 يفعّل MobileConfig (`A0E`) |
| **24896** | bool | false | MobileConfig هو مصدر الحقيقة (inferred) |
| **25403** | bool | false | العودة إلى المصدر القديم (inferred) |
| **22646** | bool | false | المقارنة الظلية |
| **22647** | int | 10 | معدل أخذ عيّنات سجل الظل |
| **38895** | int | 0 | `== 1`: cache MobileConfig لكل قراءة |
| **26524**، **28443**، **30441**، **30556** | bool | false | خيارات factory الخاصة بـ MobileConfig (`CbW`، `BMu`) |
| **26525** | int | 600 | خيار factory الخاص بـ MobileConfig (`CbW`)، الوحدة غير محلولة |
| **26640** | bool | false | معامل تهيئة MobileConfig (`BN4`) |
| **35778** / **36185** | int | 0 | مرحلة التهيئة / خيار توقيت الجلب (`C054709r.APn`، `C41251mA.A00`) |
| **24317** | bool (SESSIONLESS) | false | قراءات ما قبل chatd تستخدم urgent exposure |
| **31830** | bool | false | دمج لكل مصدر لسمة exposure رقم 5029 |
| **16206** | bool | false | البوابة الرئيسية لخصائص المجموعة |
| **18205** | bool (GROUP) | false | قراءة لكل مجموعة في `GroupAbPropsManager` |
| **3664** / **6084** | bool | false | مسح / ضبط `encrypted_rid` |
| **21198** | bool | false | `PQ_KEYS_UPLOAD`: رفع prekeys من نوع Kyber؛ الانتقال من `true` إلى `false` يحذفها |

### 10.2 الحظر والسلامة (`WA_BAN_SYSTEM_DEEP_EN.md`)

11061، 11064، 11065 (int 86400)، 12709، 16349، 19793، 19893، 26697، 27269، 14837، 25631 (bool false)؛ 12840 (JSON `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}`)؛ 20278 (JSON `{"max_messages": 10000, "farthest_time_days": 30}`)؛ 31535 / 31536 (float 0.0).

### 10.3 رمز الخصوصية وcstoken (`WA_TCTOKEN_CSTOKEN.md`)

| العلم | النوع | الافتراضي |
|------|------|---------|
| **996** / **997** | int | 604800 / 4 |
| **865** / **909** | int | 604800 / 4 |
| **4063** | int | 0 |
| **3802** / **22012** | int | 26 / 26 |
| **20605** / **14303** / **15491** | bool | false |
| **20606** | int | 2000 |
| **24915** / **24941** / **18639** / **25253** | bool | false |
| **26897** | int | 604800 |

### 10.4 Meta AI واسم المستخدم وUSync

| التقرير | الأعلام (القيمة الافتراضية) |
|--------|-----------------|
| `WA_META_AI.md` | **26189**، **27083**، **25119** (بلا قارئ)، **37227**، **37852**، **37054**: bool false؛ **26190** JSON `""` |
| `WA_USERNAME.md` | **4745**، **20189**، **23817**، **21199**، **16033**، **8421**، **12402**، **28678**: bool false؛ **21995** JSON `{}`؛ **20494** 3، **20459** 35، **34347** 4، **34348** 6، **28127** 30، **29327** 60؛ **34350** string `^([0-9]{4}\|[A-Z0-9]{6})$` |
| `WA_USYNC.md` | **5751**، **5839**، **20798**، **29769**-**29771**، **9732**، **33432**، **14565**، **26739**، **31261**: bool false؛ **9667**، **33609**، **20988**: true؛ **730** 35، **471** 1140، **37780** 0 |

### 10.5 مستوى المجموعة (وحدة GROUP، 35 معرّفًا)

Bool false: 18205، 23245، 23246، 26013، 26269، 26862، 27009، 27025، 28357، 28358، 29275، 30905، 30906، 31456، 32501، 34075، 35211، 35772، 36156، 36504، 36505، 38082، 38083. Int: 26270 (1209600 ث = 14 يومًا)، 27247 (0)، 23397 / 23398 / 24075 / 34277 / 34333 / 35227 / 35639 / 37523 / 37524 (-1). String: 33673 (`none`). أسماء 26270 و23245 و23246 و26269 و30905 و30906 و28357 و28358 و27009 و27025 و35639 و35772 تأتي من WA Web (سجل المجموعة وإعدادات الاستطلاع؛ inferred).

---

## 11. Baileys (`baron-baileys-v2`، `src/Socket/chats.js`)

| الموضوع | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| طلب المستخدم | `fetchABProps(protocol='1', hash, refreshId)`: `<props protocol hash? refresh_id?>` في `xmlns="abt"` | الشكل نفسه؛ `hash` موجود دائمًا (فارغ عند الإجبار)، و`refresh_id` فقط مع delta |
| طلب المجموعة | `{ group }` فقط | `group` + `hash` (مصفوفة من 2 في smali) |
| مفاتيح الاستجابة | `reduceBinaryNodeToDictionary(props, 'prop')`: قاموس `config_code` -> `config_value` | تخزين مطبوع؛ و`config_expo_key` وصفوف `event_code` و`hash` و`refresh` و`refresh_id` و`delta_update` كلها مستخدمة |
| البحث | باسم العلم (`abProps['stella_interop_enabled']`) | بالرمز الرقمي فقط |
| الخصائص القديمة | `fetchProps`: `xmlns="w"` ‏`<props protocol="2" hash>` خصائص مسمّاة | لم يُعثر على builder؛ تظهر الأسماء فقط في قاموس رموز stanza (`AbstractC40911lb`) |
| refresh | لا شيء (مرة لكل اتصال) | فترة + فحص إصدار + push |

| العَرَض | السبب | الحل |
|---------|-------|-----|
| `abProps['<name>']` قيمته `undefined` | استجابة `abt` تحمل `config_code` فقط | استخدم الرمز كمفتاح؛ فضاء الرموز هو المذكور في القسم 8 |
| يظهر مفتاح `undefined` في القاموس | صفوف `event_code` / `sampling_weight` لا تحمل `config_code` | تخطَّ الصفوف التي بلا `config_code` |
| قيم قديمة | لا معالجة لـ hash / refresh / `refresh_id`، ولا delta | خزّن `hash` و`refresh` و`refresh_id`؛ وأرسل `hash` و`refresh_id` في الطلب التالي |
| قراءة bool كسلسلة truthy | `config_value` هو `"1"` / `"0"` | حلّل حسب النوع (`!= 0`) |

---

## 12. حالات الخطأ

| العَرَض | السبب | الحل |
|---------|-------|-----|
| `ABPropsManager/onABPropError; unknown error code: N` | خطأ خارج 207 / 304 / 400-503 | لا شيء؛ العدّاد لا يتقدم |
| 3 عمليات جلب فاشلة، ولا إعادة محاولة ليوم | بلغ `fetch_attemp_count` القيمة 3، و`last_refresh_time` = الآن | انتظر فترة واحدة أو ارتفاع إصدار `abprops` في تسجيل الدخول |
| `AbPropProtocolHelper/onReceiveABProps failed to parse response` (`C49828Lvo`) | `<props>` مشوَّه | يُعاد إلقاء الاستثناء، والمخزن لا يُمس |
| `ABPropsManager/invalid format for config; configCode=N; value=V` | int/float غير رقمي أو JSON غير صالح | تُتخطّى تلك الخاصية |
| `IllegalArgumentException: Unknown BooleanField: N` | قراءة مطبوعة لمعرّف بلا قيمة افتراضية في الخريطة وبلا قيمة افتراضية في الواصف | أضف قيمة افتراضية؛ `N` هو config code |
| قراءة MobileConfig تعيد `false` / `0` / `""` | المعرّف بلا Stable ID (`INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`) | اقرأ عبر المسار القديم |
| `WAMCEvaluation/invalid json format; key=N` | قيمة علم JSON غير قابلة للتحليل على مسار MobileConfig | يُعاد `JSONObject` فارغ |
| `GroupAbPropsClient/malformedResponse ... noPropsChild` / `parseFailed` | استجابة مجموعة بلا `<props>` أو تحليل فاشل | لا تُخزَّن قيمة مجموعة |
| `GroupAbProps/fetchSkip reason=cacheValid` / `disabled` | قبل `_nextRefreshTimeInSeconds` / العلم 16206 مُعطَّل | لا شيء |
| `ABPreChatdProps/exception ... error add expo key` | JSON تالف في `pref_expo_keys` | لا يُضاف المفتاح |

---

## 13. فروق أساسية

| لا تخلط بين | التفصيل |
|----------------|--------|
| config code مقابل معرّف الحقن | `A15(20548)` علم؛ أما `C05Z.A00(66)` و`C1XG.A0I(34166)` و`C00C.A02(61)` فهي معرّفات تبعية |
| config code مقابل نوع طلب IQ | `A0W(..., 220, 32000L)` (220 هنا، و299 في IQ رمز الخصوصية) هو عدد صحيح لنوع الطلب |
| config code مقابل معرّفات WAM | 5504 حدث، و5029 و4473 سمتا WAM، و1094 رمز حدث في صفوف العيّنات |
| config code مقابل Stable ID | الرمز (<= 39140) يفهرس الجدول؛ أما Stable ID فهو محدِّد MobileConfig بـ 64 بت |
| `abt` IQ مقابل خصائص `w` مقابل جدول DB ‏`props` | `abt` = خصائص AB الرقمية؛ خصائص `w` القديمة = خصائص الخادم المسمّاة؛ جدول SQL ‏`props` = مخزن مفتاح-قيمة محلي |
| خصائص المستخدم مقابل خصائص المجموعة | فضاء المعرّفات نفسه، والخرائط نفسها؛ قيم المجموعة تعيش في `groupAbProps`، بمفتاح group jid، والوحدة GROUP |
| `ab_key` مقابل `config_expo_key` مقابل `hash` مقابل `refresh_id` | مفتاح المجموعة / مفتاح التجربة لكل خاصية / hash المحتوى / الإصدار |
| `abprops` في تسجيل الدخول مقابل `<props refresh_id>` | إصدار الخادم الحالي مقابل الإصدار المخزَّن من آخر جواب |
| MEX ‏`MetaConfigFetchMutation` مقابل `abt` | blob الخاص بـ MobileConfig مقابل الخصائص الرقمية القديمة؛ يعمل كلاهما عندما يكون MobileConfig نشطًا |
| القيمة الافتراضية الإنتاجية مقابل قيمة التنقيح الافتراضية | تُقرأ القيمة الافتراضية الإنتاجية فقط |
| تثبيت أول وصول مقابل cache العادي | القيم المثبّتة تنجو من المزامنات حتى نهاية العملية |
| الإسناد دون اتصال مقابل عبر الاتصال | التجارب دون اتصال تكتب المخزن نفسه، ثم تفرض جلبًا كاملًا عبر الاتصال |

---

## 14. التدفق الكامل

```
[Server]            [Login]                 [C0D2 / C27646BzW]               [C08J reads]         [WAM]
   │ <success abprops=N props mc_ep_version>   │                                   │                 │
   ├──────────────────►│ N > last_version? or  │                                   │                 │
   │                   │ last_refresh+refresh<now                                  │                 │
   │                   ├──────────────────────►│ <iq xmlns=abt>                    │                 │
   │◄───────────────────────────────────────── │  <props protocol=1 hash [refresh_id]>             │
   │ <props ab_key hash refresh refresh_id [delta_update]>                          │                 │
   │   <prop config_code config_value config_expo_key/> ... <prop event_code sampling_weight/>      │
   ├──────────────────────────────────────────►│ typed store per id (bool/int/float/string/JSON)   │
   │                                           │ backup, hash, refresh, last_version, ab_key       │
   │                                           ├─ observers BhX ► write ► Bfk / C2K ──────────────►│
   │                                           │ A0s(): clear read cache                           │
   │                                           │                                   │                 │
   │ <ib><abprops/>  (force, empty hash) ─────►│                                   │                 │
   │                                           │                                   │                 │
   │                                      A15(id) / A0b(id) / A0j(id)...           │                 │
   │                                           │          cache ► prefs ► default map ► (descriptor)│
   │                                           │          MobileConfig path if A0E && A0b && !A0S   │
   │                                           │                                   ├ first read ────►│ 5504 exposure
   │                                           │                                   │ + 24 h resend   │ 5029, 4473
   │                                           │                                   │                 │
   │ MEX MetaConfigFetchMutation ◄─────────────┼── C41251mA (option 36185) ────────┤                 │
   │ xwa2_mobile_config_fetch {blob, ep_refresh_id, ab_key} ───► native MobileConfig, Stable IDs    │
   │                                           │                                   │                 │
   │ <iq xmlns=abt><props group hash> (group opened, flag 16206) ► groupAbProps ► A04(groupJid,id)   │
```

---

## 15. المجهولات

| الموضوع | السبب |
|-------|--------|
| دلالات الأعلام | لا أسماء؛ الدلالات فقط حيث يحلّها موضع استدعاء أو تقرير آخر |
| الإسناد من جهة الخادم | الاستهداف ونسب الإطلاق وتعريفات التجارب ليست في العميل |
| الـ stanza الأب لعنصر push الابن `abprops` | المعالج مسجَّل تحت رمز الرسالة 235؛ `ib` inferred |
| الرابط بين `abprops` في تسجيل الدخول ووسيط الإصدار في المُشغِّل | يأخذ المُشغِّل `Integer`؛ وتحليل تسجيل الدخول يضبط `AtomicReference`؛ الاتصال inferred |
| `mc_overrides.json` الخاص بـ MobileConfig في بناءات release | شيفرة الجدول موجودة؛ لا دليل على أنه يُستشار أو أن مستخدم التطبيق يستطيع الكتابة فيه |
| بوابة `override-abprops` ومسار التطبيق | سبب `abprop_override_not_allowed` موجود؛ لم يُعثر على كاتب إلى أي مخزن خصائص |
| اشتقاق `device_exp_id`، وصيغة `config_expo_key` | لم يُتتبَّعا |
| بتات Stable-ID 0-15، وإدخالات وحدة `u4`، و`int1 >> 16` | المعنى غير محلول |
| prefs ‏`31165` و`32010`، والعلم `35778`، وقيم `36185` ‏1 / 2 | مقروءة جزئيًا (`Pr8`، المنسّق) |
| سلوك المعرّفات الـ 70 ذات القيم الافتراضية فقط تحت MobileConfig | تعيد lambda المطبوعة قيمًا صفرية (found)؛ الأثر على الميزات لم يُتتبَّع |
| دلالات delta من جهة الخادم | أي الخصائص يحملها delta |
| حركة المرور الفعلية والقيم الحية المقدَّمة | تحليل ساكن فقط |
