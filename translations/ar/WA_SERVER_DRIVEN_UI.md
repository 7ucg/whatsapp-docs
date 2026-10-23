<!-- src-sha1: 193c35598b4e82f9c32a0c5d2cee4dbf2d708588 -->
# WhatsApp واجهة المستخدم الموجَّهة من الخادم — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** الشاشات والإجراءات الموجَّهة من الخادم على Android: آلة حالات إجراءات Phoenix/FCS (IQ `xmlns="phoenix"`، أنواع الحالات، مشغّلات choice، سجل الموارد)، شاشات Bloks (جلب GraphQL، معرّفات doc والتوجيه بحسب app-id، حمولة JSON، معرّفات دوال Lispy، فضاءات أسماء الإجراءات، استعلامات المكوّنات، الذاكرات المؤقتة)، رسائل native flow (سجل أزرار NFM)، WhatsApp Flows (جسر WebView، سياسة مضيف SecureWebView، JSON الخاص بالتدفق)، الاستجابة الغنية للذكاء الاصطناعي وبطاقة FMX (ما ليس موجَّهًا من الخادم)، سكربتات المتصفح داخل التطبيق (جسر iabjs وnonce)، العزل (sandboxing) وأعلام الميزات، الصلة بـ Baileys

---

## 1. ما هو (تقنيًا)

لا يملك WhatsApp Android محرّك واجهة موجَّهة من الخادم واحدًا. توجد أربع آليات مستقلة؛ تجلب كل منها وصفًا من خادم (أو تقرؤه من رسالة) وتقود شيفرة أصلية (native). جميع العبارات مأخوذة من التحليل الساكن لـ APK المفكَّك؛ لم يُلتقط شيء على السلك. المستويات: **found** = مقروء في الشيفرة أو البيانات، **inferred** = مستنتج، **unknown** = غير محسوم. الأسماء المشوَّشة خاصة بكل بناء وأُعيد حلّها في 2.26.41.6.

| الآلية | ما تصفه | الناقل | المُصيِّر / المنفِّذ | أين تُستخدم |
|--------|---------|--------|----------------------|-------------|
| Phoenix (أسماء الأصناف تقول FCS "flow configuration service"، وسم السجل FDS) | تحكم التدفق: حالات `resource` / `choice` / `pass` / `succeed` / `subflow` | IQ `<iq xmlns="phoenix">` مع العنصر الابن `<fds>` | آلة الحالات `QKb`، معالجات الموارد (`AbstractC57917Pxu`) | تهيئة المدفوعات، رسالة العنوان، استبيان الأعمال، تدفقات بطاقات البرازيل |
| Bloks | الشاشات: شجرة مكوّنات + سكربتات Lispy + استعلامات مكوّنات غير متزامنة | طلب HTTPS GraphQL POST إلى `graph.<domain>/graphql` | أنشطة وfragments مضيفة بنظام Litho/RenderCore | المدفوعات، الدعم، الاشتراكات، الموافقة، ربط Accounts Center، minishops، الاستبيانات، موافقة أعمال Meta AI |
| رسائل Native flow (NFM) | أزرار على الرسائل التفاعلية (`nativeFlowInfo` الاسم + JSON للمعاملات) | رسالة (protobuf) | `C33370Efz` يوزّع على نحو 40 صنف إجراء | أزرار CTA، `address_message`، `galaxy_message` (Flows) |
| تطبيق ويب WhatsApp Flows | JSON للتدفق يُعرض بتطبيق ويب مستضاف | HTTPS (`flows.whatsapp.net`) داخل `SecureWebView` + قناة رسائل `WhatsAppBridge` | `WaFlowsWebViewBottomsheetModalActivity` / `FlowsWebBottomSheetContainer` | نماذج الأعمال (`galaxy_message`، الدفع المرن) |

نقاط حاسمة:

- Phoenix هو طبقة التحكم، وBloks هو طبقة العرض. حالة Phoenix من نوع `resource` بمعرّف `open_bloks_screen_graphql` تفتح شاشة Bloks؛ وإجراءات Bloks `wa.action.phoenix.*` تعود إلى آلة الحالات (القسم 3.5؛ الربط مستنتج من الأسماء).
- Bloks ليس MEX وليس IQ. هو طلب GraphQL POST بأسلوب Meta (`doc_id` + `variables`) عبر HTTPS (found، `AbstractC40195HfH`). أما Phoenix فهو IQ. صنف نتيجة استعلام نقطة نهاية Flows (`AnonymousClass456`) يتشارك القاعدة نفسها لمحلل استجابة Bloks؛ ولم يُحسم نقله (القسم 4.5).
- لا يستطيع محتوى الخادم تسمية شيفرة أصلية عشوائية. كل مسار يمر عبر سجل ثابت: معرّفات موارد Phoenix (15 في الشيفرة)، معرّفات دوال Bloks (681 مسمّاة)، أسماء أزرار NFM (39)، دوال جسر Flows (30)، قائمة السماح لـ xmlns في Bloks IQ (مدخلان).
- لم يُعثر على أي تحقق من توقيع الحمولة لحمولات Bloks أو Phoenix. `BloksTrustedPayload` (`verifiedRoot`) موجود وبلا أي مراجع (found، smali وJava).
- ليست موجَّهة من الخادم: بطاقة الثقة FMX (رسالة نظام ينشئها العميل)، الاستجابة الغنية للذكاء الاصطناعي (مجموعة مكوّنات protobuf ثابتة)، وملفات `assets/json/bloks_*_template.json` الثلاثة (هياكل تحميل/خطأ، وليست شاشات منتج).

تقارير ذات صلة: خصائص AB (IQ `abt`، معرّفات الأعلام) في `WA_AB_PROPS.md`؛ الاستجابة الغنية للذكاء الاصطناعي في `WA_META_AI.md` القسم 6.3. لم يُحدَّد موقع أي إطار يحمل اسم Genie (بحث نصي؛ غياب الإطار غير مثبت).

---

## 2. آلة حالات إجراءات Phoenix

### 2.1 المكوّنات (found، أسماء 2.26.41.6)

| الدور | الصنف | ملاحظات |
|-------|-------|---------|
| وقت التشغيل | `QKb` | وسم السجل `FcsStateMachine`؛ `A03` ينفّذ حالة واحدة، `A04` يتبع `next` أو يسحب من المكدس، `A05` ينهي |
| مدير FDS | `C58392QJx` | يبدأ إعدادًا (`A08`)، يرسل IQ (`A07`)، يبني خريطة الحالات من الاستجابة (`A01`) |
| باني IQ | `C31107Dfz` (المُنشئ مع `C9E1`)، `C9E1`، `C31085Dfd` | `xmlns="phoenix"` |
| محللات الاستجابة | `F7J` (`<iq><fds>`)، `F8I` (الحالات 17 إلى 20، 27، 28)، `F7Y` resource، `F7Z` choice، `C34784F7b` pass، `C34783F7a` succeed، `C34785F7c` subflow، `C34786F7d` version_check | محلل عام لمخطط السمات (`C197428ac`) |
| الحالات المحلَّلة | `P2W` resource، `P2U` choice، `P2T` pass، `P2S` succeed، `P2V` subflow، `C31057DfB` version_check | الجزء المشترك `P2Q`: `name`، `input_path`، `input_selector`، `next`، `result_selector`، `result_path` (`C33411Ege.A03`) |
| حالات وقت التشغيل | `C55819P7c` resource، `C55817P7a` choice، `C55818P7b` pass، `P7Z` succeed، `C55820P7d` subflow | التعيين في `C58392QJx.A01` |
| قاعدة الموارد | `AbstractC57917Pxu` | `A02()` = معرّف المورد، `A04(...)` = تنفيذ مع خريطة معاملات، المعرّف الافتراضي `throw_error` |
| الربط / السجل | `C51E` (المعرّف + معالج كسول)، `InterfaceC148426Oz.CP3()`، الاتحاد `C138515tp` | السجلات: `C135435oi`، `C135425oh`، `C135415og`، `C53207NpW`..`C53211Npa` |
| المشغّلات / الأخطاء / رد النداء | `RsJ` (28 مشغّلًا)، `AbstractC56245PPq`؛ `Q6G` (`catch`)؛ `C57560Pry` (`A00(error, result)`، `A01(result)`) | |

### 2.2 الجلب: IQ (found، `C31107Dfz`، `C58392QJx.A07`)

```
<iq xmlns="phoenix" type="get|set" id="...">
  <fds config="<config name>" state="<start state>" parameters="<json>">
    <context ... parameters='{"session-id":"...","bloks-versioning-id":"13c6e3b8...(64 hex)"}'/>
  </fds>
</iq>
```

| البند | القيمة | Tier |
|-------|--------|------|
| `type` | `get` عند البدء (`A08`)، `get` أو `set` للمورد `send_fds_iq` | found |
| أعداد IQ الصحيحة للنوع / المهلة | 302 (get)، 303 (set)، 32000 ms | found |
| `state`، `parameters` | تُكتبان فقط عند عدم الفراغ؛ `parameters` = JSON للمدخلات غير الفارغة | found |
| `bloks-versioning-id` | سلسلة ثابتة من 64 خانة hex، بالقيمة نفسها في كل بانٍ لطلبات Bloks (القسم 3.2) | found |
| تداخل عقدة السياق | `<context>` يحمل JSON؛ لم يُحسم التداخل الدقيق للعقدة الداخلية | unknown |

الاستجابة (found، `F7J`، `F8I`):

| العنصر | المحتوى | الاستخدام |
|--------|---------|-----------|
| سمات `<fds>` `state`، `parameters` | تلميح البدء | تُحلَّل، ولم تُتتبَّع أبعد |
| `<states start_at="...">` + `<state ...>`+ | البرنامج (القسم 2.3) | تهيئة `QKb`، السجل `initializeStateMachine num_states` |
| `<next_screens>` + `<screen is_entry_screen app_id bloks_server_params sources>` | شاشات Bloks للتحميل المسبق | `C58392QJx.A06` (تحميل مسبق) |
| `<screen_data parameters>` | كتلة بيانات الشاشة | تُحلَّل |
| `<persist_data>` + `<data ...>` | قيم يحتفظ بها المضيف | `C58392QJx.A02` (رد نداء لكل مفتاح) |

يُعاد خطأ IQ إلى المستدعي بصيغة `error` (`BtN`) ويُزال مدخل المدير المعلّق.

### 2.3 أنواع الحالات (found)

يقبل المحلل قائمة المميِّزات `FDSResourceState|FDSChoiceState|FDSSucceedState|FDSPassState|FDSSubflowState|FDSVersionCheckState` (`F8I` الحالة 27). السمة `type` هي السلسلة الثابتة في العمود الثاني.

| النوع | `type` | السمات الخاصة | سلوك وقت التشغيل |
|-------|--------|---------------|-------------------|
| Resource | `resource` | `id` (معرّف المورد)، `parameters`، `merge`، `merge_param`، `catch` | يبحث عن `id` في السجل؛ المعرّف المفقود يعطي الخطأ `ResourceNotFound`؛ يشغّل المعالج؛ تُدمج النتيجة وفق `merge`؛ ينتقل إلى `next` |
| Choice | `choice` | `default` (الحالة التالية الاحتياطية)، `catch`، أبناء `<choice choice="{json}"/>`+ (مفتاح مشغّل واحد + `next`) | يقيّم المشغّلات على JSON المدخل؛ أول تطابق يفوز، وإلا `default`؛ يلزم خيار واحد على الأقل |
| Pass | `pass` | `parameters` | يعيد كتابة البيانات وينتقل إلى `next`، بلا معالج |
| Succeed | `succeed` | لا شيء | نجاح نهائي (`A05` بلا خطأ) |
| Subflow | `subflow` | `launch_mode` (`child` أو `embedded`)، `config`، `parameters`، `catch` | `child`: مدير وآلة حالات جديدان؛ `embedded`: يجلب إعدادًا آخر داخل الجلسة نفسها (inferred من `C55820P7d`) |
| Version check | `version_check` | `default`، الابن `<choice>` | يُحلَّل (`C31057DfB`) لكن لا فرع له في `C58392QJx.A01`؛ تُسقَط الحالة (found)؛ والانتقال إليها سيفشل بالرسالة `state not found for name` (inferred) |

لا يملك المحلل حالة `fail`؛ ومع ذلك يسردها manifest (2.7).

المحدِّدات والبيانات (found):

- `input_selector` الافتراضي `"$"`؛ السلسلة `"null"` تعطّله (`C58392QJx.A01`). `result_selector` ودمج المعاملات يمران عبر `AbstractC58328QFo`. يُستخدم محرّك بأسلوب JSONPath لـ `catch` (`Q2G`، تعابير مثل `$.[i].error_equals`) (found)؛ أن المحدِّدات تستخدم المحرّك نفسه هو inferred.
- أنماط `merge` في `QKb.A03`: `replace` (الافتراضي)، `merge`، `incremental_merge`، `wae_commerce_merge` (found).
- `catch` = مصفوفة JSON من `{error_equals:[names], next:<state>}`؛ و`error_equals` الفارغ يطابق كل شيء (found، `Q6G.A00`). الأخطاء غير المطابَقة تنهي الآلة مع الخطأ (`A05`).
- أخطاء يرفعها المفسِّر نفسه: `ResourceNotFound`، `FailToResume`، `unsupportedComparisonTypes`، `comparingValuesWithDifferentTypes`، `genericChoiceStateError`؛ الخطأ الافتراضي للمعالج `NOT_CATCHABLE_ERROR` (`C5I7.A03`) (found).

### 2.4 مشغّلات choice (found، `RsJ.A00`)

28 صنفًا. يسرد manifest منها 21؛ وسبعة أسماء قديمة موجودة في الشيفرة فقط.

| المجموعة | الأسماء |
|----------|---------|
| Boolean | `and`، `or`، `not`، `booleanEquals` |
| Equality | `eq`، `neq`، `eq_any`، `neq_any`، `eq_path`، `neq_path`، `eq_any_path`، `neq_any_path`، `stringEquals` |
| Ordering | `gt`، `gte`، `lt`، `lte`، `gt_path`، `gte_path`، `lt_path`، `lte_path`، `numericalEquals`، `numericalGreaterThan`، `numericalGreaterThanEqual`، `numericalLessThan`، `numericalLessThanEqual` |
| Other | `isPresent`، `regex_match` (`variable` + `regex_match`) |

يُختار كل مشغّل بحضور مفتاحه في JSON الخاص بـ choice (`AbstractC56245PPq.A00`)؛ و`JSONException` يتخطى إلى المشغّل التالي. متغيرات `_path` تقارن بقيمة تُحلّ من مسار (inferred من الاسم)؛ ولم يُقرأ الحل الدقيق.

### 2.5 سجل الموارد (found)

يُسجَّل عبر `InterfaceC148426Oz.CP3()`؛ والمعرّفات تحملها موفّرات `C05T.A00(n)`. السجلات `C53207NpW`..`C53211Npa` تعيد مجموعة فقط عندما تكون `L8E.A1T()` صحيحة (`C18780mK.A03()` تساوي `C21610rj.A0E`)؛ ومعنى هذا المسند غير معروف.

| معرّف المورد | المعالج | في `phoenix-features.json` | السلوك |
|--------------|---------|----------------------------|--------|
| `open_bloks_screen_graphql` | `C954246c` | yes | يفتح شاشة Bloks؛ المعامل `app_id` مطلوب (يفشل التحويل وإلا) |
| `open_bloks_screen` | `C954346d` | no | مثله، مع `fetch_channel` = `GRAPHQL` (يستخدم `bloks_server_params`) أو `STATIC` (يستخدم `fetch_channel_params.static_url`، ويضبط `should_load_bloks_through_cdn: true`)؛ القيم الأخرى ترمي استثناءً |
| `send_fds_iq` | مجهول في `AbstractC79003We` | yes | المعاملات `config`، `type` (`GET`/`SET`)، `state`، `parameters`؛ يحتاج مدير FDS حيًّا بحسب معرّف المهمة؛ غياب المدير أو الإعداد يسجّل خطأ ويفشل بـ `NOT_CATCHABLE_ERROR` |
| `abprop_fetch` | مجهول في `AbstractC79003We` | no | المعاملات `code` (int)، `abprop_type` (`string`/`json`/`boolean`/`float`/`integer`)، `default_value`؛ يعيد `abprop_value` مقروءًا من مخزن AB؛ لم تُرَ قائمة سماح على `code` |
| `client_dasl_query` | `C954746h` | yes | يحتاج المعامل `query`، وإلا يسجّل `No parameters` ويفشل؛ ينفَّذ الاستعلام على منفِّذ خلفي |
| `dismiss_bottom_sheet` | `C955346n` | yes | يغلق الورقة الحالية |
| `native_flow_call_manager` | `C954946j` | yes | يحتاج `phone_number`؛ يختزله إلى أرقام و`+`؛ يبدأ `ACTION_DIAL` (`tel:`) مع `FLAG_ACTIVITY_NEW_TASK` (المتصل فقط، دون اتصال تلقائي) |
| `request_permission` | `C955046k` | no | طلب إذن Android (الصلة بـ `FcsRequestPermissionActivity` inferred) |
| `throw_error` | `C954446e` | no | يرفع خريطة `error`؛ يبحث عن الرسالة بـ `error_map_type` + `code` |
| `payment_encrypt_with_public_key` | `C31703Dr4` | yes | المعاملات `data_value`، `data_type`، `key_scope`، `provider_name`، `network` (مشروط) |
| `br_verify_card_deeplink` | `C955446o` | yes | يرسل بثًّا مقيَّدًا بالحزمة `com.whatsapp.payments.phoenix.action.launch_activity_for_phoenix_result` مع `app_to_app_partner_app_package`، `app_to_app_partner_intent_action`، `app_to_app_request_payload` (مشروط) |
| `br_verify_card_check_if_app_exists` | `C31702Dr3` | no | مشروط |
| `native_br_compliance`، `native_br_p2m_checkout_address`، `native_card_encryption_resource` | `C955146l`، `C955246m`، مجهول | no | مدفوعات البرازيل، مشروطة عدا مورد البطاقة |

أسماء في manifest فقط (بلا مدخل في السجل في هذا البناء): `error_response`، `native_flow_npci_common_library` (الشجرة الفرعية `mode.collect`)، `native_p2m_lite_compliance`، `native_p2m_lite_hpp_checkout`، `open_bloks_screen_static`. لا معالج لـ `open_bloks_screen_static`؛ مسار STATIC يعيش داخل `open_bloks_screen` بصيغة `fetch_channel`.

### 2.6 نقاط الإطلاق (found)

يُبنى `new C57778Pva(config, params, startState)` في: `address_message` (`C31337Djk`، NFM)، `biz_survey` (`C57417PpS`)، `br_merchant_onboarding` (`C33140EcF`)، `br_p2m_checkout_add_card`، `br_p2p_verify_card` (`C32703EOj`)، ومدخل رابط عميق يمرر إعدادًا باسم من الخادم مع حالة البدء `DeepLink` (`RunnableC46615KYo` الحالة 18، الإحالة `deeplink`). السلسلتان `add_card_phoenix` و`verify_card_phoenix` موجودتان؛ ودورهما كأسماء إعدادات inferred. برنامج الإعداد نفسه يأتي من الخادم؛ ولا يُشحن أي منه عدا manifest القدرات.

### 2.7 manifest القدرات

`assets/versioning/phoenix-features.json` (1,218 B، مطابق لنسخة 2.26.34.4): على المستوى الأعلى `pass`، `choice` (21 مشغّلًا)، `resource` (12 معرّفًا إضافة إلى `input_selector`، `parameters`، `result_selector`، `result_path`)، `succeed`، `fail`. لم يُحدَّد موضع استخدامه وقت التشغيل (لا مرجع نصي)؛ يُعامل كقائمة أسماء. الشيفرة هي المرجع (2.4، 2.5).

---

## 3. Bloks

### 3.1 أسطح الاستضافة (found)

| المضيف | الدور |
|--------|-------|
| `WaBloksActivity`، `WaBloksBottomSheetActivity`، `BloksCDSBottomSheetActivity`، `BloksCDSPreloadCDSBottomSheetActivity` | شاشة كاملة، ورقة سفلية، أوراق CDS (نظام التصميم) |
| `WaSqBloksActivity`، `WaBloksScreenQueryFragment` | مضيفات screen-query (أنواع `screen_query` مقابل `legacy_screen`) |
| `WaFcsModalActivity`، `WaFcsBottomSheetModalActivity`، `WaFcsPreloadedBloksActivity`؛ `SurveyCanonicalBloksActivity` (+ الورقة) | شاشات تستضيفها Phoenix؛ الاستبيانات |
| مضيفات المنتجات | `CommonBloksActivity`، `SupportBloksActivity`، `BrazilPayBloksActivity`، `ConsumerSubscriptionBloksActivity`، `DigitalCommerceDcpBloksActivity`، `CsatSurveyBloksActivity`، `AppointmentBloksHostActivity` (exported false)، `WaBackupStorageBloksActivity` (exported false) |

لا يعلن أي نشاط Bloks أو Flows أو Phoenix عن intent filter؛ و`targetSdkVersion` هو 36، لذا الأنشطة التي بلا `android:exported` غير مصدَّرة (found، manifest). يمكن لـ Bloks أيضًا تضمين مكوّن `WebView` (`AndroidBridge.updateSize`، الإجراء `bk.action.WebViewWithOnChange`) (found).

### 3.2 الجلب: GraphQL عبر HTTPS (found، `AbstractC40195HfH`، `C45J`)

| البند | القيمة |
|-------|--------|
| URL | `https://graph.<domain>/graphql<path>`؛ `<domain>` = التفضيل `pref_graphql_domain`، الافتراضي `whatsapp.com`؛ عدة أصناف طلبات تفرض `facebook.com`؛ `<path>` فارغ، أو `/extensions` لمتغير Flows |
| سلسلة الاستعلام | يُلحَق `?_emp=1` عندما تكون خاصية AB **549** مفعّلة (الافتراضي false) |
| الجسم | JSON `{"variables": "<json string>", "access_token": ..., "doc_id": <long>, "lang": ..., "Content-Type": "application/json"}` |
| الرمز | رمز لكل طلب إن وُجد، وإلا سلسلة رمز ثابتة مرتبطة بالتطبيق ومضمَّنة في العميل (القيمة غير مستنسخة) |
| الترويسات | `X-FB-Friendly-Name: WABloksAppRootQuery-<app_id>`، `X-FB-Request-Analytics-Tags` |
| `variables` | `app_id`، مفتاح الإصدار، `params` (سلسلة JSON)، `bloks_theme_params` |
| اسم مفتاح الإصدار | `version` أو `versioning_id` أو `bloks_version` بحسب صنف الطلب؛ والقيمة هي ثابت الـ 64 hex نفسه كما في Phoenix |
| متغير ما قبل الموافقة (`C136975rF`) | يضيف `app_version`، `locale`، `df_token`، `enc_token`، `disclosure_id`، `is_paused`، `country_code`، `encrypted_rid` |
| متغير الامتدادات (`C132735kG` الحالة 2) | `extension_id` (= `flow_id` لإصدارات رسالة التدفق 2 و3 و4)، `business_jid`، `screen_id`، `bloks_version` |
| الأخطاء | `errors[].extensions.error_code` (الافتراضي 417)، `is_retryable`؛ `error.code` 3489039 يطلق فحص سلامة وإعادة محاولة، و1675012 يعطي `Bad Request` (مسار ما قبل الموافقة) |

حقول جذر الاستجابة (`AnonymousClass451.A05`): الحمولة هي `data.<root>.payload` (سلسلة JSON).

| Doc id | حقل الجذر | يستخدمه (found) |
|--------|-----------|-----------------|
| 3651100555017197 | `whatsapp_bloks_getlayout` | المسار الافتراضي؛ minishops link/pdp/storefront |
| 3958953970834604 | `whatsapp_bloks_getprivatelayout` | الافتراضي لـ `C5LX.A00()`؛ إشعار خصوصية minishops، معاينة المنتجات |
| 9404809712971896 | `whatsapp_bloks_getlayout` | العائلات الموجَّهة بـ regex (3.3) |
| 9943385105682204 | `whatsapp_bloks_getprivatelayout` | `logged_out.cxthelp.whatsapp` |
| 6019334944816363 | تخطيط Flows (الجذر `whatsapp_galaxy_bloks_getflowlayout` موجود في `AnonymousClass424`؛ الصلة بين الاثنين inferred) | `com.bloks.www.whatsapp.galaxy.flow.v2`، `...commerce.galaxy_message`، `...commerce.extensions_message_v2` |
| 36103976949247233 | `wamo_bloks_get_layout` | أسطح WAMO |
| 9676557989071413 | غير معيَّن إلى حقل جذر | عيّنة/رعاية المدفوعات، `novi.care.*`، موافقة `whatsapp.ai.biz.*` |

معرّفا doc‏ 26891716230495873 (pix playground) و25865201793138751 يظهران في جداول التوجيه بلا حقل جذر محسوم.

### 3.3 التوجيه بحسب app-id (found)

تُعنوَن الشاشة بـ `app_id` (اسم منقّط، `com.bloks.www.*`). تعيّن جداول التوجيه كل `app_id` إلى واصف استعلام `C5LX(doc id, request-factory variant)`: عشرة جداول بمجموعات ثابتة (`InterfaceC148576Pp`: `C132235jS`..`C132335jc`) وجداول regex (`InterfaceC148726Qe`: `C132345jd`..`C132465jp`).

| العائلة | النمط أو المثال | Doc id |
|---------|-----------------|--------|
| مركز الطلبات / المدفوعات | `orders_hub(\..+)*`، `fbpay_hub`، `payment.mft.wallet.fbpay_hub`، `(payment.)?mft.wallet.*`، `payment.(bloks.(commerce|ecp).checkout|fbpay.ecp).*` | 9404809712971896 |
| `gai` / `sna` / ملصقات الذكاء الاصطناعي (معنى العائلة inferred من الأسماء) | `bloks.nme.gai`، `wa.nme.gai`، `wa.sna`، `whatsapp.ai.stickers.*` | 9404809712971896 |
| الاشتراكات | `dcp.subscriptions?(\..+)*` | 9404809712971896 |
| الدعم | `(csf|cxthelp)(\..+)+` | 9404809712971896 |
| Minishops | `minishops.link.app`، `.whatsapp.pdp`، `.storefront.wa` | 3651100555017197 |
| موافقة الذكاء الاصطناعي للأعمال | `whatsapp.ai.biz.{learn_more,consent,assistant_consent,third_party_consent,meta_ai_consent}` | 9676557989071413 |
| Playground / تنقيح | `wa.playground.payments.br.pix.*` (المتغير 9) ؛ `whatsapp.payments.phoenix.{debug,demo_*,multi_*}`، `payments.whatsapp.f2care`، `novi.care.*` (المتغير 10) | 26891716230495873 ؛ 9676557989071413 |

توجد 87 معرّفًا حرفيًا مختلفًا من `com.bloks.www.*` في الشيفرة؛ والباقي يصل من الخادم ويُوجَّه بعائلات regex. يوجد حارسا نمط في `AnonymousClass514`: معرّفات `consent(...)` قد تحمل `extra_params_json.whatsapp_bloks_networking_feature_override`؛ و`payment.mft.security.*` مع `ptt_use_case = WALLET` يختار مساعد الطلب `wallet_canonical` (found).

### 3.4 صيغة الحمولة (found)

محلل JSON متدفق `AbstractC122255Jb`؛ الكائن الأعلى يحوي `payload` (سلسلة) و`layout.bloks_payload`.

| مفتاح `bloks_payload` | المعنى |
|-----------------------|--------|
| `tree` | المكوّن الجذر (القسم أدناه)؛ `action` بدل `tree` للحمولات التي فيها إجراء فقط |
| `ft` | جدول الدوال: المعرّف إلى سلسلة تعبير |
| `data`، `values`، `templates`، `props` | سجلات بيانات (`id`، `type`، `data`، `scoped`)، تعابير قيم، قوالب، جدول أسماء الخصائص |
| `embedded_payloads`، `hoisted_async_components` | حمولات متداخلة بحسب المعرّف |
| `referenced`، `referenced_external`، `referenced_embedded_payloads`، `referenced_templates`، `referenced_ft_entries`، `referenced_values`، `referenced_ct`، `ct` | قوائم اعتماديات للحمولات الجزئية/المتدفقة |
| `component_queries` | استعلامات مكوّنات غير متزامنة (`id`، `app_id_expr`، `params`، `client_params`، `targets`، `cache_ttl_expr`، `disk_cache_enabled`، `is_scoped`) |
| `error_attribution` | `logging_id`، `source_map_id` |
| `depth`، `step_debugger_metadata.breakpoints` | عمق التدفق، المنقّح |

ترميز الشجرة (`C5AN`): العقدة كائن مفتاحه الوحيد نقطة رمزية (code point) واحدة؛ وهذه النقطة هي معرّف المكوّن (`AbstractC105654gT.A00` = `codePointAt(0)`)؛ ومفاتيح السمات أيضًا نقاط رمزية مفردة (`!`=33 id، `#`=35 child، `&`=38، `+`=43 للمكوّن الظلي 13347). خريطة معرّف المكوّن إلى الاسم ليست في الأصول (unknown).

معرّفات الدوال ("Lispy"، `C122545Ki`): عقدة السكربت مصفوفة JSON عنصرها الأول هو الدالة: `"#<name>"` مسمّاة، أو اسم منقّط يُحل عبر جدول الأسماء `AbstractC111054pC.A01`، أو سلسلة بالأساس 36 تُحلَّل بـ `Integer.parseInt(s, 36)`. للثوابت المنمّطة معرّفات ثابتة: 17809 `bool.Const`، 18327 `f32.Const`، 18338 `f64.Const`، 19222 `i32.Const`، 19237 `i64.Const`. يحوي جدول الأسماء 681 مدخلًا، المعرّفات من 17293 إلى 26071.

مفكوك من القوالب المشحونة (رمز بالأساس 36، المعرّف، اسم الجدول؛ found): `e2a` 18226 `core.If`؛ `e25` 18221 `core.GetArg`؛ `e2f` 18231 `core.TakeLast`؛ `e1w` 18212 `core.Apply`؛ `dng` 17692 `bloks.GetParameter`؛ `dnt` 17705 `bloks.GetVariable2`؛ `f4g` 19600 `map.Get`؛ `f6m` 19678 `mins.CallRuntime`؛ `igq` 23930 `core.AsNonnull`؛ `fjm` 20146 `screen.callback.DidFetchSucceed`؛ `foz` 20339 `ttrc.MarkerStart` (جميعها تحت `bk.action.`)؛ `h9h` 22373 مسرود بالاسم الحرفي `null`.

الصيغة النصية `\t(...)` في `ft` وسلاسل التعابير تسلسل مختلف؛ وأنها تستخدم معرّفات الأساس 36 نفسها يلزم من اتساق عمليات الفك أعلاه (inferred). لم يُقرأ المحلل النصي.

التفاوض على القدرات (inferred): يُرسل `bloks-versioning-id` ذو الـ 64 hex مع كل طلب؛ ويحوي الجدول 50 اسم قدرة `bk.versioning.*` (مثل `SupportsFunctionTables`، `TemplatePayloads`، `AsyncComponentBatchedWireProtocol`، `SupportsLispySignatureMinification`). أن الـ hash يعرّف مجموعة القدرات هذه هو inferred.

الأصول المشحونة (`assets/json/bloks_screen_template.json`، `bloks_bottomsheet_template.json`، `bloks_cds_base_screen_template.json`، بأحجام 9,028 / 9,124 / 11,443 B، مطابقة لـ 2.26.34.4): قالب جذر فيه `tree` لمؤشر دوران، ومدخل `component_queries` واحد هدفه `genScreenContent`، وبديل خطأ في `embedded_payloads` (`Something went wrong` / `Please try again later` في اثنين من الثلاثة). هي هياكل؛ وشاشات المنتج تأتي من نتيجة الاستعلام.

### 3.5 فضاءات أسماء الإجراءات (found، `AbstractC111054pC`)

| البادئة | العدد في جدول المعرّفات | أمثلة |
|---------|--------------------------|-------|
| `bk.action.core/bool/num/i32/i64/f32/string/array/map/math` | 113 | `core.If`، `core.Let`، `core.While`، `array.Map`، `string.*` |
| `bk.action.mins.*` | 36 | `CallRuntime`، `PutByVal`، `Raise` (آلة minscript الافتراضية) |
| `bk.action.bloks.*` | 61 | `OpenScreen`، `OpenBottomSheet`، `Inflate`، `FetchAsyncComponents`، `WriteLocalState`، `ReplaceChildren`، `WriteGlobalConsistencyStore` |
| `bk.action.cds.*`، `bk.callbacks.cds.*` | 13 + | `OpenCdsBottomSheet`، `PushCdsBottomSheet`، `UnwindToScreen` |
| `bk.action.animated/animation/timer/collection/textinput/text_input/video` | 58 | سلوك الواجهة |
| `bk.action.qpl/ttrc/trace` | 14 / 11 / 2 | علامات زمن الاستجابة (`ttrc.MarkerStart`) |
| `bk.action.privacy.consent.*` | 10 | `OpenFlow`، `LaunchConsent`، `ShutdownExperience` |
| `bk.action.waffle.*`، `bk.fx.*`، `bk.waffle.*` | 37 / 11 / 2 | ربط Accounts Center: `EncryptPassword`، `DeleteLocalUserCredentials`، `GetProfilePictureUrl`، `UnpauseWithNativeAuthBlob`، `PregenerateAndCacheRSAKeyPairs` |
| `bk.action.mft.*`، `bk.action.frontier.*`، `bk.action.apt.PleEncrypt`، `bk.action.commerce.GetPaymentToken`، `bk.action.payments.GetCreditCardMetaData` | 5 / 5 / 1 / 1 / 1 | المدفوعات: `ModularGeneratePTT`، `LaunchGooglePaySheet`، `IsLuhnCompliant` |
| `bk.action.navigation.OpenUrl`، `bk.fx.action.OpenURLInIAB`، `bk.action.acp.OpenUrlExternally`، `bk.action.OpenUniversalLink`، `bk.action.DeeplinkToOtherAppOrDirectToAppStore`، `bk.action.bloks.IsAppInstalled` | 6 | التنقل خارج Bloks |
| `bk.action.io.clipboard.SetString`، `bk.action.RequestPermission`، `bk.action.media.LoadAlbums`، `bk.fx.action.media.OpenMediaPicker`، `bk.action.foa.media.OpenCamera` | 5 | الوصول إلى الجهاز |
| `wa.action.*` | 75 | إجراءات مضيف WhatsApp (الجدول أدناه) |
| `wa.callbacks.*` | 10 | `FormInputOnTextChange`، `CodeInputOnTextChange`، `DatePickerOnDateSet`، `CameraViewOnMediaCaptured`، `ListViewItemSelected` |
| `bk.versioning.*`، `wa.versioning.image.base64` | 50 / 1 | أسماء القدرات |

أبرز `wa.action.*` (المعرّفات 22391 إلى 26071):

| المجموعة | الأسماء |
|----------|---------|
| Network | `IQRequest`، `AsyncRequest`، `UploadMedia`، `UploadProfilePicture` |
| جسر Phoenix | `phoenix.FdsIq`، `FdsIqV2`، `FcsReturnResult`، `FcsReturnResultV2`، `FcsReturnResumableData`، `statemachine.GoBack`، `GoBackV2` |
| حالة التطبيق | `GetAbPropValue`، `GetAppType`، `GetIntentParameter`، `LoadScreenParam`، `SaveScreenParam`، `IsDarkModeEnabled` |
| التنقل | `OpenUrl`، `RouteToNativeScreen`، `RouteToNativeBenefitDetail(V2)`، `navigation.OpenChat`، `OpenContactInfo`، `OpenNativeActionSheet`، `FinishActivity(WithResult)`، `PopScreen` |
| المراسلة / التجارة | `commerce.SendNFMReplyMessage`، `commerce.ActionWithCallback`، `share.Text`، `bonsai.SubmitFeedback`، `care.OpenContactSupport`، `care.OpenReportThisPayment` |
| القياس عن بعد | `SendFieldStat(V2)`، `StartFieldStatTimer`، `GetFieldStatEventId`، `perf.TrackPerformance`، `novi.EncryptLogEvent(V2)` |
| Deeplink | `RegDeeplinkListener`، `DeregDeeplinkListener` |

الحارس الموجود على إجراء IQ في Bloks (`C129575f5.A0Y`، السجل `IQRequestHelper/sendIQRequest: Invalid XMLNS`): لا يمرّ إلا xmlns `w:pay` و`urn:xmpp:whatsapp:account` (`C33327EfH.A02`)؛ وأي شيء آخر يستدعي رد النداء `on_failure`. وعليه لا تستطيع سكربتات Bloks إرسال IQ إلا في هذين الفضاءين (found). لم تُتتبَّع تنفيذات معالجات معظم معرّفات `wa.action.*` الأخرى (شيفرتها تُبلَغ بالمعرّف العددي).

### 3.6 استعلامات المكوّنات والتخزين المؤقت (found)

- يجلب `component_query` مكوّنًا غير متزامن بـ `app_id` عبر مسار GraphQL نفسه (المدير `C5L9`، وسم السجل `BloksComponentQueryManager`)؛ و`app_id_expr` و`params` و`client_params` و`cache_ttl_expr` تعابير Lispy تُقيَّم على العميل.
- مستويان للتخزين المؤقت: ذاكرة (`cache_src: memory`، `cache_age`) وقرص مفتاحه لكل استعلام (`BloksComponentQueryDiskCache`؛ الأصناف `C5NA`، `C5NN`، `C136885r6`). سجلات القرص مسلسَلة بـ Java (`ComponentQueryDiskCacheRecord`: `DiskCacheData{initialResponse, extensions}`، `responseTimestampMs`، `BloksComponentQueryResources`)؛ والبيانات الوصفية تحت `__disk_metadata`؛ ويتولى `Bloks_ACQ_ReadWriteThread` عمليات الإدخال/الإخراج. `disk_cache_enabled` مفتاح لكل استعلام.
- الإجراءات `bk.action.AsyncComponentCacheWrite` و`bloks.ClearCachedAsyncComponents` و`bloks.InvalidateCachedAsyncComponents` تتيح للحمولة إدارة الذاكرة المؤقتة.
- مجلد الذاكرة المؤقتة على القرص وحدّ حجمها وإخلاؤها: unknown. إزالة تسلسل Java لسجلات ذاكرة مؤقتة متأثرة بالخادم تحدث فقط من الذاكرة المؤقتة الخاصة بالتطبيق نفسه (inferred من مسار الشيفرة).

---

## 4. رسائل Native flow وWhatsApp Flows

### 4.1 سجل أزرار NFM (found، `AbstractC30032D4u` الحالة 442، الصنف `EYT`)

تحمل الرسالة التفاعلية أزرارًا بـ `nativeFlowInfo.name` وJSON للمعاملات. التوزيع: يبحث `C33370Efz.A05` عن الاسم في خريطة (`C0VA`) تضم نحو 40 صنفًا فرعيًا من `AbstractC33168Ech`؛ الأسماء غير المعروفة تسجّل `can not recognize NFM action` وتُسقَط؛ ويمكن تعطيل إجراء بالبوابة (عدّادان `wa:nfm_dispatch_gate_blocked` / `_observed`).

| المجموعة | الأسماء |
|----------|---------|
| أسماء الأزرار المدعومة (39) | `cta_catalog`، `review_and_pay`، `review_and_pay_v2`، `cta_call`، `cta_url`، `cta_copy`، `cta_pix_code_copy`، `offer_payment_account`، `form_message`، `open_webview`، `catalog_message`، `voice_call`، `video_call`، `landline_call`، `quick_reply`، `single_select`، `view_product`، `call_permission_request`، `cta_app_link`، `appointment`، `automated_greeting_message_view_catalog`، `send_location`، `order_status`، `booking_confirmation`، `booking_status`، `psi_nux_opt_in`، `psi_tos_opt_in`، `psi_opt_outs`، `account_authentication_request`، `request_contact_info`، `agent_api_key`، `otp`، `payment_reminder`، `cta_reminder`، `payment_request`، `api_signup`، `inapp_signup`، `split_payment`، `send_payment` |
| المجموعة الثانية | `address_message`، `galaxy_message` (تطلق التدفقات؛ الدور inferred من الاستخدام) |
| قائمة سماح مختلطة/ردود سريعة | `C33370Efz.A08`: `cta_url`، `cta_call`، `voice_call`، `video_call`، `cta_copy`، `menu_options`، `cta_reminder`، `view_product`، `cta_app_link`، `galaxy_message`، `otp`، `booking_*`، ... |

- يبدأ `address_message` إعداد Phoenix المسمّى `address_message` (`C31337Djk`، found).
- يفتح `galaxy_message` تطبيق WhatsApp Flows (4.2).
- تُخزَّن ردود التدفقات في `message_ui_elements_reply` (`flow_id`، `element_type` 8) و`interactive_message_bloks_widget` (found، SQL).

### 4.2 معاملات `galaxy_message` والإطلاق (found، `C31338Djl`، `C31337Djk`)

| المفتاح في JSON المعاملات | الاستخدام |
|---------------------------|-----------|
| `flow_id` | يجب أن يطابق `\d+` لإجراء Flows v2 |
| `flow_token`، `flow_cta` | مطلوبان مع `flow_id` (مسار Flows v2) |
| `flow_message_version` | `2` و`3` و`4` تختار متغيرات الامتداد لاستعلام Bloks |
| `flow_action` (`navigate` الافتراضي، `data_exchange`)، `flow_action_payload` (كائن) | الشاشة الأولى / قناة البيانات |
| `mode` | `draft` يعلّم تدفقًا مسودة (`is_draft`) |
| `form_type` | يوجّه إلى `FlexCheckoutNativeFormActivity` (الدفع المرن) |
| `flow_token_signature`، `www_proxy_secret` | تُمرَّر إلى الصفحة فقط عند تفعيل خاصية AB **14825** |

يأتي JID الأعمال المرسِل من المحادثة (`FlowsV2Action`)؛ وبدونه يُجهَض الإطلاق (`cannot launch flow without business jid`). يوجد مُصيِّران: تطبيق الويب (4.3) ومسار Bloks (`com.bloks.www.whatsapp.galaxy.flow.v2`، القسم 3.2). أيهما تسلكه رسالة معيّنة لم يُحسم؛ وخاصيتا AB **22787** (نشاط منفصل مقابل ورقة سفلية) و**14222** تُقرآن على مسار الويب.

### 4.3 تطبيق ويب Flows (found)

| البند | القيمة |
|-------|--------|
| عناوين URL الأساسية (خصائص AB نصية) | **7153** `https://flows.whatsapp.net/flows` (تحميل مسبق، `C35814Ff9`)، **6060** القيمة الافتراضية نفسها (جلب JSON التدفق `EP6`: الأساس + `/json/` + معرّف التدفق، inferred من ترتيب الباني)، **7125** `.../flows/cache_management/` (منظّف الذاكرة المؤقتة `C39066GzF`، الفاصل **7126** = 1382400)، **16723** `.../flows-app/catalog` (الكتالوج) |
| المضيف | `SecureWebView` (`com.facebook.secure.securewebview`): الوصول إلى الملفات والمحتوى معطّل؛ يُسمح بالتحميل فقط إذا كان المخطط `https` وكان المضيف يساوي مضيف URL الإطلاق أو نطاقًا فرعيًا منه (`GAP.A00`، `H26`، مدمجان بـ AND في `GAL`)؛ وإلا يُسجَّل `Uri is blocked` |
| URL الإطلاق | من الحزمة (`url`، الافتراضي `about:blank`)؛ والأساس خاصية AB، فيستطيع الخادم نقله؛ وسياسة المضيف تتبع URL الإطلاق (نتيجة inferred) |
| التحميل المسبق | `FlowsWebPreloader` يحمّل AB **7153** في WebView مخفي (`setCacheMode(2)`)؛ ويُتتبَّع إصدار ذاكرة service-worker المؤقتة عبر `flows_service_workers_cache_version` |
| الحقن في الصفحة | وسم `meta` مع viewport، `layoutDirection`، `locale`، `timeZone`، `supportedStyles` |
| الجسر | `window.WhatsAppBridge.invoke(method, data, cb)`؛ ينشئ الجانب الأصلي `MessageChannel` ويرسل `init-port` مع المنفذ 1 (`HQD`)؛ الرسائل JSON `{method, data, callbackID}`؛ والردود `{callbackID, responseData}` |
| ربط الأصل (origin) | يُحقن سكربت الجسر بـ `evaluateJavascript` في أي شيء يعرضه WebView؛ ويُرسَل المنفذ إلى الهدف `Uri.EMPTY`؛ والتقييد يعتمد على سياسة URL في SecureWebView (inferred) |
| JSON التدفق | يُجلب `flow_json` بـ `EP6.A01` (HTTP GET، يُخزَّن على القرص كسلسلة مسلسلة، المفتاح `<id>_<id2>`)، فقط عند تفعيل AB **8552**؛ ويبني `FlowsWebViewDataRepository` الحزمة (`flow_json`، `flow_action_payload`، `creation_source`، معرّفات الجلسة) |
| المفتاح العام | `WAExtensionsGetPublicKey` يعيد المفتاح العام لنقطة النهاية المحصَّل عبر نداء بيانات وصفية GraphQL (أخطاء `extensions-metadata-graphql-*`، النمط `required` أو `optional`)؛ والاستخدام لتشفير البيانات يتم في جانب الصفحة (inferred) |

دوال الجسر التي تعالجها الشيفرة الأصلية (30؛ `C41342Hyk`، `FlowsWebBottomSheetContainer.CKc`):

| المجموعة | الدوال |
|----------|--------|
| الجلسة | `WAExtensionsGetFlowData`، `WAExtensionsDataChannelExchange`، `WAExtensionsNavigate`، `WAExtensionsComplete`، `WAExtensionsClose`، `WAExtensionsGetPublicKey`، `WAExtensionsGetClientAbProps` |
| الواجهة | `WAFlowsShowNativeInputDialogComponent`، `WAExtensionsConfigureNavBar`، `WAFlowsMediaSelect`، `WAFlowsMediaRetry`، `WAFlowsMediaDelete`، `WAFlowsCopyText`، `WAFlowsOpenURL`، `WAExtensionsLearnMore`، `WAExtensionsContextualHelp` |
| الأعمال | `WAExtensionsSpamReport`، `WAExtensionsReportItem`، `WAFlowsDownloadResponse`، `WAFlowsMarketingDisclosureState`، `WAFlowsMarketingDisclosureUserAction` |
| السلة | `WAFlowsStoreShoppingFlowContext`، `WAFlowsGetCart`، `WAFlowsSetCartItem`، `WAFlowsClearCart` |
| القياس عن بعد | `WAMLogger`، `WAQPLLogger.start`، `.end`، `.annotate`، `.point` |

ملاحظات المعالجة: `WAFlowsOpenURL` يبدأ `ACTION_VIEW` فقط لعناوين `https`، وإلا يعرض snackbar؛ و`WAExtensionsGetClientAbProps` يعيد أي خاصية AB بالرمز والنوع (`bool`، `int`، `float`، `string`، `json`) دون قائمة سماح مرئية (`C37367GJs`)؛ والدوال غير المعروفة تذهب إلى معالج افتراضي (`GJW`)؛ والمدخل الذي يفشل تحليله يعطي `extensions-bridge-api-input-parse-error`.

### 4.4 إكمال التدفق

يُنهي `WAExtensionsComplete` الجلسة ويرسل العميل رسالة استجابة native-flow (أعمدة `native_flow_response_*`؛ المعاملات تحمل `wa_flow_response_params`، `flow_creation_source`، `response_message`) (found من الأسماء؛ لم يُتتبَّع مسار الإرسال).

### 4.5 استعلام نقطة نهاية Flows

يقرأ صنف النتيجة `AnonymousClass456` الجذر `whatsapp_galaxy_forward_flow_data_response` أو `xwa_flows_make_flow_endpoint_request` و`status_code`: 200 نجاح، و421 و504 يُعيَّنان إلى نتيجتين متمايزتين، والباقي فشل عام (found). هل يجري هذا عبر MEX أم عبر مكدس GraphQL على HTTPS: unknown (قاعدة المحلل مشتركة مع Bloks).

---

## 5. أسطح ليست واجهة موصوفة من الخادم

### 5.1 الاستجابة الغنية للذكاء الاصطناعي (تحملها الرسالة، مكوّنات ثابتة)

رسالة protobuf `richResponseMessage` (انظر `WA_META_AI.md` القسم 6.3). تعداد نوع الرسالة الفرعية `EnumC32139E2l` (found): `AI_RICH_RESPONSE_UNKNOWN` 0، `GRID_IMAGE` 1، `TEXT` 2، `INLINE_IMAGE` 3، `TABLE` 4، `CODE` 5، `DYNAMIC` 6، `MAP` 7، `LATEX` 8، `CONTENT_ITEMS` 9؛ أصناف تلوين الشيفرة (`KEYWORD`، `STRING`، `NUMBER`، `METHOD`، `COMMENT`، `DEFAULT`)؛ والبيانات الوصفية الديناميكية `IMAGE`، `GIF`. يعرض العميل مجموعة ثابتة؛ والإجراءات هي تنزيل الملف / إعادة التوجيه (`UnifiedResponseActionHandlerFactory`). لا لغة سكربت ولا DSL للإجراءات.

### 5.2 بطاقة FMX

تنشئ بطاقة FMX (`LE7`، مصنع نموذج العرض `fmxViewModelFactory`، وسم الصورة الرمزية `fmx-card-v2`) من العميل كرسالة نظام (`C198788cr`: `Creating FMX card system message for chat`)؛ وعدّادات مثل `fmxBizEnterpriseSenders` و`fmxMissingLidMapping` و`fmxSuspiciousBottomSheetCacheMiss` تدل على أنها مدفوعة بإشارات محلية. هل يوفّر الخادم أي نص للبطاقة: unknown. تُعامل كواجهة أصلية.

### 5.3 سكربتات المتصفح داخل التطبيق (iabjs)

في `res/raw/iabjs_*` خمسة عشر سكربتًا في 2.26.41.6 (أربعة أكثر من مجموعة 2.26.34.4): `autofill_execute_callback` و`autofill_language_detect` و`autofill_payment_detection` و`otp_autofill` جديدة. المضيف `WaInAppBrowsingActivity` (exported false).

| البند | القيمة (found) |
|-------|-----------------|
| كائن الجسر | `iabjs_unified_bridge`: `addWebMessageListener(name, allowedOrigins, listener, jsWorld)` في عالم JS المعزول `iab_js` عند الدعم (`HJY.A05`)؛ والبديل `addJavascriptInterface("iabjs_unified_bridge")` (`RunnableC40709HoJ`) |
| جانب الصفحة | `window.__call_iabjs_unified_bridge(method, nonce, payload)` يرسل `{method, payload, nonce}`؛ ويُستبدل nonce في `window.__iabjs_unified_bridge_nonce="%s"` عند الحقن |
| الفحص الأصلي | `C39590HNn`: يجب أن يساوي `nonce` في JSON الـ nonce المخزّن لدى المعالج (يُولَّد مرة لكل معالج بـ `AbstractC48382LBd.A00().toString()`، شبيه بـ UUID، inferred)؛ والاختلاف يسجّل `invalid_nonce` ويُسقِط النداء؛ والدالة `iabjs_register_proxy` تسجّل العالم؛ والدوال الأخرى تذهب إلى مستمعين مفتاحهم (العالم، الدالة) |
| الجديد في هذا البناء | `iabjs_autofill_payment_detection` يصنّف الحقول إلى `cc-number`، `cc-exp`، `cc-exp-month`، `cc-exp-year`، `cc-csc`، `cc-name` بحسب `autocomplete` أو regex على name/id/placeholder؛ و`iabjs_otp_autofill` يملأ `input[autocomplete="one-time-code"]`؛ و`iabjs_autofill_language_detect` يرسل `languageDetermined` |
| مجموعة الأصول المسموحة | `Set` يوفّره المستدعي؛ المحتوى لم يُتتبَّع (unknown) |
| البديل القديم | `addJavascriptInterface` بلا مرشّح لكل أصل (سلوك المنصة، inferred) |

ثمانية من السكربتات القديمة الأحد عشر مطابقة بايتًا ببايت لنسخ 2.26.34.4؛ وتغيّرت `detect_login_forms` و`navigation_performance_logger_android` و`iabjs_bridge_init` (453 B مقابل 433 B لتهيئة الجسر).

---

## 6. ملخص العزل والأمان

| التحكم | أين | Tier |
|--------|-----|------|
| معرّفات موارد Phoenix ثابتة في الشيفرة؛ المعرّف المجهول يعطي `ResourceNotFound` | `QKb.A03` | found |
| مشغّلات Phoenix ثابتة (28)؛ المشغّل غير المطابق يُتخطى | `RsJ`، `AbstractC56245PPq` | found |
| إجراء IQ في Bloks مقيَّد بـ xmlns `w:pay`، `urn:xmpp:whatsapp:account` | `C33327EfH.A02` | found |
| معرّفات دوال Bloks ثابتة (681 مسمّاة) | `AbstractC111054pC`، `C122545Ki` | found |
| أسماء NFM ثابتة (39 + 2)؛ المجهول يُسقَط | `AbstractC30032D4u`، `C33370Efz` | found |
| مضيف Flows: https + مضيف الإطلاق (أو نطاق فرعي) فقط، بلا وصول إلى الملفات/المحتوى | `SecureWebView`، `GAP`، `H26` | found |
| جسر Flows: قائمة دوال ثابتة؛ `WAFlowsOpenURL` https فقط | `FlowsWebBottomSheetContainer` | found |
| iabjs: فحص nonce، عالم معزول، مجموعة أصول | `C39590HNn`، `HJY` | found |
| بث Phoenix `br_verify_card_deeplink` مقيَّد بحزمة التطبيق نفسه | `C955446o` | found |
| جميع أنشطة Bloks وFlows وPhoenix بلا intent filters؛ targetSdk 36 | manifest | found |
| التحقق من توقيع أو hash لمحتوى Bloks/Phoenix | لم يُعثر على شيء؛ `BloksTrustedPayload` بلا مراجع | found (absence in searched paths) |
| يستطيع الخادم قراءة خصائص AB بالرمز (`abprop_fetch`، `WAExtensionsGetClientAbProps`) | لا قائمة سماح مرئية | found |
| ثقة النقل (TLS pinning، معالجة الرمز لطلبات graph) | لم يُحلَّل | unknown |

النتيجة (inferred): تقوم الثقة على النقل وعلى السجلات أعلاه؛ والبرنامج الخبيث أو المخترَق من جهة الخادم محدود بتلك السجلات، لكنها تشمل مساعدات تشفير المدفوعات، ومعالجة بيانات اعتماد Accounts Center، و`ACTION_DIAL`، وفتح URL، وقراءات AB.

---

## 7. التخزين المؤقت والتحميل المسبق

استعلامات مكوّنات Bloks: ذاكرة + قرص، وTTL بحسب `cache_ttl_expr` (3.6). Phoenix: قوائم `next_screens` التي يسردها الخادم تُحمَّل مسبقًا في `WaFcsPreloadedBloksActivity`؛ ومدخلات `persist_data` تذهب إلى مستمعين لكل مفتاح (found). Flows web: WebView للتحميل المسبق، وإصدار ذاكرة service-worker المؤقتة، ومنظّف مجدول (AB 7125/7126)، وذاكرة قرص مؤقتة لـ JSON التدفق، وعلامة حظر البيانات الوصفية `extensions_metadata_banned_<id>_<id>` في prefs (found).

---

## 8. أعلام الميزات (الافتراضيات من `C08J`؛ المعاني من موضع القراءة)

| ID | النوع | الافتراضي | يُقرأ في | التأثير |
|----|-------|-----------|----------|---------|
| **549** | bool | false | `AbstractC40195HfH.A03` | يُلحق `?_emp=1` بـ URL الخاص بـ GraphQL (ما لم تكن `C0GD.A02()`) |
| **7153** | string | `https://flows.whatsapp.net/flows` | `C35814Ff9` | URL التحميل المسبق لـ Flows |
| **6060** | string | نفسه | `EP6`، `C33350Efe` | أساس Flows لـ `/json/<id>` |
| **7125** | string | `.../flows/cache_management/` | `C39066GzF` | URL منظّف ذاكرة Flows المؤقتة |
| **7126** | int | 1382400 | `C39066GzF` | فاصل/تمكين المنظّف (الوحدة غير معروفة؛ > 0 يفعّل) |
| **8552** | bool | false | `FlowsWebViewDataRepository.A07` | جلب JSON التدفق أصليًا وتمريره إلى الصفحة |
| **14825** | bool | false | `FlowsWebViewDataRepository.A06` | تمرير `www_proxy_secret` و`flow_token_signature` |
| **22787** | bool | false | `C31338Djl` | Flows في نشاط منفصل مقابل ورقة سفلية |
| **24781** | bool | false | `FlowsWebBottomSheetContainer` | بدونه، تغلق الورقة المستعادة نفسها |
| **14222** | bool | false | `C31338Djl` | بوابة في مسار إطلاق Flows (التأثير الدقيق unknown) |
| **5333**، **1319** | bool | false / false | متغير Flows في `C45J` | كلاهما مفعّل: تُبلَّغ أخطاء تخطيط Flows بصيغة `extensions-layout-unexpected-error` |

تستخدم معرّفات الأعلام فضاء الأرقام نفسه في `WA_AB_PROPS.md`.

---

## 9. Baileys (`baron-baileys-v2`)

لا يملك عميل Baileys مُصيِّرًا، لذا Bloks وFlows web خارج المتناول. ما يمكنه لمسه هو الجزء الذي تحمله الرسالة، ومن حيث المبدأ IQ.

| الهدف | ما يعمل | لماذا قد يفشل | الإصلاح |
|-------|---------|----------------|---------|
| إرسال زر Flow | `interactiveMessage.nativeFlowMessage.buttons[]` مع `name: 'galaxy_message'` و`buttonParamsJson` يحمل المفاتيح في 4.2 (`flow_message_version`، `flow_id`، `flow_token`، `flow_cta`، `flow_action`، `flow_action_payload`) | يحتاج المستقبِل سياق JID أعمال، و`flow_id` عدديًا، و`flow_token`، و`flow_cta`؛ ومن غير المرجّح أن تُحترم رسائل المرسلين المستخدمين (غير الأعمال) (inferred) | الإرسال من حساب أعمال مسجَّل؛ إبقاء `flow_id` عدديًا |
| استخدام اسم زر غير معروف | لا شيء | `C33370Efz` يُسقِط الأسماء خارج الـ 39 + 2 | استخدام اسم من 4.1 |
| جلب برنامج Phoenix | `<iq xmlns="phoenix" type="get"><fds config=... /></iq>` | يقرر الخادم بحسب حالة الحساب/التطبيق؛ ولم يُلتقط محتوى الاستجابة قط | لم يُجرَّب؛ يُعامل كـ unknown |
| قراءة شاشة Bloks | لا ينطبق | يحتاج رمز graph وdoc id و`bloks-versioning-id`؛ لا مسار في Baileys | خارج النطاق |

---

## 10. حالات الخطأ

| العَرَض | السبب | الإصلاح |
|---------|-------|---------|
| `ResourceNotFound` وينتهي التدفق | حالة `resource` تسمّي معرّفًا غير موجود في السجل (أو معرّف برازيلي مشروطًا في بناء غير مطابق) | استخدام معرّفات من 2.5 |
| `state not found for name: <x>` | `next` يشير إلى حالة مفقودة، أو إلى حالة `version_check` (أسقطها `C58392QJx.A01`) | تعريف الهدف بنوع مدعوم |
| `unsupportedComparisonTypes` / `comparingValuesWithDifferentTypes` | مشغّل مطبَّق على أنواع خاطئة | مطابقة الأنواع؛ استخدام `catch`؛ و`NOT_CATCHABLE_ERROR` لا يمكن التقاطه |
| `FdsIqResource/execute: can't find FdsManager from the job_id` | `send_fds_iq` خارج جلسة حية | التشغيل داخل الجلسة التي بدأته |
| Bloks `Invalid XMLNS` | `wa.action.IQRequest` مع xmlns خارج قائمة السماح | فقط `w:pay`، `urn:xmpp:whatsapp:account` |
| `FcsScreenOpenerBloksDelegate: app_id is not present` | `open_bloks_screen*` بدون `app_id` | تمرير `app_id` |
| `error.code` 3489039 | طُلب فحص سلامة (جلب ما قبل الموافقة) | يعيد العميل المحاولة بعد الفحص |
| صفحة Flows فارغة، السجل `Uri is blocked` | غادر التنقل مضيف الإطلاق أو استخدم مخططًا غير https | إبقاء المحتوى على مضيف الإطلاق |
| `extensions-bridge-api-input-parse-error` | رسالة الجسر ليست JSON صالحًا بالشكل المتوقع | إرسال `{method, data, callbackID}` |
| iabjs `invalid_nonce` | nonce خاطئ أو مفقود | استخدام `__iabjs_unified_bridge_nonce` المحقون |

---

## 11. فروق أساسية

| لا تخلط بين | الفرق |
|-------------|-------|
| Phoenix مقابل Bloks | Phoenix = تدفق تحكم عبر IQ؛ Bloks = شاشات عبر GraphQL؛ يلتقيان عند `open_bloks_screen*` و`wa.action.phoenix.*` |
| FCS مقابل FDS | كلاهما يظهر: `flowconfigurationservice` (الحزمة، `FcsStateMachine`) و`FDS` (مدير IQ، `<fds>`، السجل `FDSManage`)؛ وتوسيع "FDS" ليس في الشيفرة |
| Manifest مقابل الشيفرة | يسرد `phoenix-features.json` ‏12 معرّف مورد و21 مشغّلًا؛ والشيفرة فيها 15 معرّف مورد و28 مشغّلًا؛ الشيفرة هي الحَكَم |
| `open_bloks_screen_static` مقابل `open_bloks_screen` + `fetch_channel=STATIC` | الأخير فقط له معالج |
| مفاتيح شجرة Bloks مقابل رموز العمليات | مفاتيح الشجرة نقاط رمزية للمكوّنات؛ ورؤوس السكربتات معرّفات دوال (أساس 36) |
| Flows web مقابل Flows Bloks | مُصيِّران لـ `galaxy_message`: WebView (`flows.whatsapp.net`) و`com.bloks.www.whatsapp.galaxy.flow.v2` |
| Bloks GraphQL مقابل MEX | يرسل Bloks POST إلى `graph.<domain>/graphql` مع `doc_id`؛ أما MEX فهو طبقة الاستعلام المحمولة عبر XMPP المستخدمة في مواضع أخرى |
| nonce في iabjs مقابل جسر Flows | يستخدم iabjs nonce لكل معالج داخل المغلَّف؛ وجسر Flows بلا nonce، ويعتمد على مصافحة المنفذ وسياسة URL |
| الاستجابة الغنية مقابل Bloks | الاستجابة الغنية مجموعة protobuf ثابتة؛ أما Bloks فشجرة قابلة للبرمجة |

---

## 12. التدفق الكامل

```
[Server]                                          [WhatsApp client]
   │  message: interactive nativeFlowInfo name        │
   ├─────────────────────────────────────────────────►│ C33370Efz: name in registry? gated?
   │        address_message              galaxy_message│
   │             ▼                              ▼      │
   │  Phoenix start C58392QJx.A08       Flows launch C31338Djl: SecureWebView (https, launch host)
   │  IQ <iq xmlns="phoenix"><fds config>      + MessageChannel init-port, or Bloks galaxy.flow.v2
   │◄────────────────────────────────────────────────┤
   │  <fds><states start_at><state type=..>           │
   ├─────────────────────────────────────────────────►│ QKb.A03 loop: resource | choice(28 ops) | pass | subflow | succeed
   │                                                  │ resource -> registry: open_bloks_screen_graphql, send_fds_iq, abprop_fetch, ...
   │  POST graph.<domain>/graphql {doc_id, variables{app_id, versioning id, params}}  (route by app_id: C5LX)
   │◄────────────────────────────────────────────────┤
   │  layout.bloks_payload {tree, ft, component_queries, ...}
   ├─────────────────────────────────────────────────►│ AbstractC122255Jb: tree (code-point keys) + Lispy (base-36 ids)
   │                                                  │ user action -> bk.* / wa.* function id
   │◄── IQ (w:pay | urn:xmpp:whatsapp:account only) ──┤ wa.action.IQRequest
   │                                                  │ wa.action.phoenix.FdsIq / FcsReturnResult -> back into QKb (next / catch / end)
   │◄── WAExtensionsComplete -> native-flow response ─┤
```

---

## 13. المجهولات

| البند | الحالة |
|-------|--------|
| توسيع "FDS"؛ معنى بوابة `L8E.A1T()` | unknown |
| خريطة النقطة الرمزية للمكوّن إلى الاسم؛ أسماء Lispy خارج الـ 681 المسرودة؛ المحلل النصي | unknown |
| شيفرة معالجات معظم معرّفات `wa.action.*` / `bk.action.*` (تُبلَغ بالمعرّف العددي) | unknown |
| محتوى الخادم الحقيقي: لم يُلتقط أي برنامج Phoenix أو شاشة Bloks | unknown (static only) |
| نقل `xwa_flows_make_flow_endpoint_request`؛ المُصيِّر الذي تسلكه `galaxy_message`؛ تأثير AB **14222** | unknown |
| موقع الذاكرة المؤقتة على القرص وحجمها وإخلاؤها؛ مجموعة أصول iabjs المسموحة؛ السلامة من جهة الخادم ما وراء TLS | unknown |
| هل يوجد إطار بأسلوب Genie في بناء آخر | unknown |
