<!-- src-sha1: 8d1c772149420abe245fd6a70c2b6615d2ab4fc5 -->
# WhatsApp Interop — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** قابلية التشغيل البيني للمحادثات مع تطبيقات الطرف الثالث على Android (بأسلوب DMA): تقييد الميزة (feature gating) وأعلام AB، إشعار الموافقة والاشتراك (opt-in)، قائمة الـ integrators، نطاقات JID الخاصة بـ interop ووسم JID الثنائي، اكتشاف المستخدمين (`w:interop` FetchUsers)، `w:interop` IQ set، النص الصريح المقيّد `InteropMessage` وأنواع الرسائل المدعومة، فروقات التشفير وstanza، مجموعات interop (عمليات MEX، الإشعارات، خصوصية الإضافة)، ping قابلية الوصول، الحظر والإبلاغ، التخزين، حالات الخطأ، الفروق عن المحادثات الأصلية، مقارنة مع Baileys

---

## 1. ما هو (تقنياً)

يتيح Interop لحساب WhatsApp تبادل رسائل 1:1 ورسائل المجموعات مع حسابات تطبيقات مراسلة أخرى ("integrators"). لا يتحدث العميل مع تلك التطبيقات أبداً. بل يتحدث مع خوادم WhatsApp، التي تعرض كل حساب طرف ثالث بوصفه JID اصطناعياً في النطاق `interop` (المجموعات: `interop.g.us`). جميع العبارات مأخوذة من التحليل الساكن لملف APK المفكَّك؛ لم يُلتقط شيء على الشبكة ولم يُشغَّل شيء مقابل خادم. المستويات: **found** = مقروء في الكود أو الموارد، **inferred** = مستنتج من الكود، **unknown** = غير محسوم. الأسماء المشوَّشة (obfuscated) خاصة بكل بناء، وأُعيد حلّها في 2.26.41.6 انطلاقاً من سلاسل ثابتة (`InteropOptInManager/`، `InteropChatMessageHandler/`، `IntegratorManager/`، `w:interop`، `integrator_display_name`، `xwa2_interop_*`).

الحالة في هذا البناء:

| الجزء | الحالة في 2.26.41.6 |
|------|--------------------|
| الكود | **موجود وكامل**: الواجهة (10 activities إضافة إلى fragments وdialogs)، عميل IQ، عمليات MEX للمجموعات والخصوصية، مسار استقبال صارم، التخزين، معالج الإشعارات |
| مفتاح الخادم | **معطَّل افتراضياً**: علم AB الجذري **7495** افتراضه `false`؛ كل علم interop يُقرأ في الكود افتراضه `false` (القسم 2) |
| المنطقة | نص المنتج يقصرها على المستخدمين الذين لديهم رقم هاتف من المنطقة الأوروبية؛ **لم يُعثر على أي فحص للبلد من جهة العميل** (الإنفاذ مستنتج على الخادم، عبر العلم 7495 وقائمة integrators) |
| Integrators | **لا شيء مضمَّن في الكود**: لا اسم integrator ولا معرّف integrator ثابت في الكود أو الموارد أو assets؛ القائمة تأتي من الخادم (القسم 4) |

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| البوابة (`InteropRolloutManager`، الاسم مستنتج من getter) | `C32001Oa` | `A01` مؤهَّل، `A02` مؤهَّل وأساسي، `A00` المجموعات، `A03` صندوق وارد موحَّد |
| عميل IQ / البُناة / المحلِّلات | `DmaInteropRPCManager` (`com.whatsapp.infra.smax.generated.dmainterop.outgoing`)؛ `C31107Dfz` (الحالات 20-23)، `C31106Dfy`؛ `C214369Ee`، `C9EQ`، `C9EP`، `C214389Eg`، `A1J` | خمس RPCs من `w:interop`، تحليل صارم للمخطط |
| Integrators | `C227409sQ` المدير، `C23765ANa` المخزن، `A3X` (`IntegratorInfo`)، `InteropUiCache` = `SharedPreferencesOnSharedPreferenceChangeListenerC20390p5` (prefs `interop_ui`) | القائمة، حالة opt-in، ذاكرة الواجهة المؤقتة |
| JIDs | `C99O` المستخدم، `C41021lm` الجهاز، `C55529Oy6` المجموعة، `C9YC` المحلِّل؛ الكاتب `C40411kn.A00`، القارئ `C24610wf` (الوسم 244) | القسم 3 |
| الاستقبال | `ENP` -> `C34471Exu` (`DecryptionCallbackInterop`) -> `C34720F4p` (`InteropChatMessageHandler`)؛ `DTF` (نص صريح من 9 حقول)، `EUQ` (`ParseInteropMessageParams`) | مسار صارم |
| سجل الأنواع | `C32718EOz`؛ `FBN` نص، `FBK` صورة، `FBL` فيديو، `FBJ` GIF، `FBH` صوت، `FBI` مستند، `FBM` تفاعل، `FBG` غير مدعوم | protobuf <-> FMessage |
| الإرسال | `C33446EhE` (فرع)، `F6P` (`E2eMessageEncryptor`)، `F6K` (`<meta>`) | الصادر |
| المجموعات / الخصوصية | `InteropGroupsManager`، `C3R2`، `C3Rb` / `C3Qh` (smali فقط)؛ `C0WQ` (الإشعارات)؛ `InteropPrivacySettingsManager`، `C3Q4` / `C3Q1` / `C29664Cuh` | MEX |
| Opt-in | `C229349vm` (`InteropOptInManager`)، `ARH`، `A4N`، `C224669lg` / `C24380wI` (الإشعار)، `PaaInteropMigrator` | المعالج، الموافقة |
| Ping | `X.0xL` مجهول في `C1S0` (`InteropNotificationHandler`)، المعرّف 270 في `AbstractC32331E9w` | إشعار |
| التحليلات | `AnonymousClass590` | WAM 6684، 7044، 7168، 6680 |

---

## 2. تقييد الميزة (Feature gating)

### 2.1 سلسلة البوابة (found، `C32001Oa`)

| الدالة | الشرط | الاستخدام |
|--------|-----------|----------|
| `A01()` | الحساب ليس حساب تابع (dependent) وفق قواعد تجربة العمر (`C14980fa.A00` -> `C08520Ne.A03()` -> `C08530Nf.A03()` false؛ النوع التابع `EnumC08540Ng.DEPENDENT`) **و** AB **7495** | كل شيء؛ مجلد قائمة المحادثات، الشارة، الإنشاء |
| `A02()` | `A01()` وليس جهازاً مرافقاً (companion) (`AnonymousClass091.BRD()` false، أي أن `registration_device_id` يساوي 0) | مدير opt-in، الإعدادات، اختيار integrator، معالج الإشعارات |
| `A00()` | `A01()` وAB **15732** | إدخال "New group"، خطوة خصوصية المجموعة |
| `A03()` | `A01()` وAB **11479** | خطوة الصندوق الموحَّد والصندوق المدمج |

`InteropSettingsActivity.onResume` (يستدعي `finish()`)، و`InteropOptInSelectIntegratorsActivity.onCreate`، و`InteropOptInManager` ومعالج إشعارات `w:interop` تعيد فحص `A02()`.

### 2.2 أعلام AB (found: المعرّف والافتراضي ومواضع الاستدعاء؛ الأسماء من جدول أسماء بناء أقدم، مطابَقة بالمعرّف، **inferred**)

| العلم | الاسم القديم (inferred) | الافتراضي | يُقرأ في | يتحكم في |
|------|------------------------|---------|---------|----------|
| **7495** | `IS_USER_INTEROP_ELIGIBLE` | false | `C32001Oa.A01`، `C224669lg.A01`، `C230679y0` (الشارة)، `RunnableC23952AUh` (Home)، `C0Y5` | البوابة الجذرية؛ حالة شارة Home |
| **15732** | `INTEROP_GROUP_MESSAGING_ENABLED` | false | `C32001Oa.A00` | إنشاء المجموعات، خطوة خصوصية المجموعة |
| **11479** | `WA_INTEROP_UNIFIED_INBOX_ENABLED` | false | `C32001Oa.A03`؛ المعرّف مسجَّل أيضاً في `C33251Ee2` | خطوة نوع الصندوق، الصندوق المدمج |
| **25512** | `INTEROP_CONTACT_MASTER_ENABLED` | false | `C0ZT`، `C51044MkK`، `C201508iH`، `C93z`، `InteropSelectChatTypeActivity` | إدخال "New contact"، جهات اتصال interop المحفوظة، حل الأسماء |
| **5760** | `INTEROP_PROTOBUF_VALIDATION_ENABLED` | false | `ENP.A00` | يوجّه JIDs الخاصة بـ interop إلى مسار `InteropMessage` الصارم (8.1) |
| **38723** | بلا اسم | false | `EA0.A00` (descriptor) | توزيع sender key داخل مجموعات interop (سلسلة السجل `interop_group_skdm_processing_enabled`) |
| **23701** | `DMA_INFLATE_VIEW_ONDEMAND_ANDROID` | true | `C1R9` | تضخيم (inflation) عند الطلب لرأس interop في قائمة المحادثات |

معرَّفة بقيم افتراضية دون قارئ حرفي (الاستخدام unknown): **3953** `INTEROP_CLIENT_UX_ENABLED`، **5759** `INTEROP_BOOTSTRAP_ENABLED`، **6613** `INTEROP_WS8_ENABLED`، **18670** `INTEROP_ADD_GROUP_PARTICIPANT_CLIENT_ENABLED`، **20999**، **11518**، **13532**، **14070** (كلها false)؛ **22752**، **24016**، **24256**، **23652**، **24275**، **24098** (ضبط واجهة `DMA_*`، كلها true). العلم **11619** (`ENABLE_DMA_GROUP_JID`) ليس له إدخال في جداول الافتراضيات. الآلية: WA_AB_PROPS.md.

### 2.3 بوابات غير AB (found)

- إشعار الموافقة **20240306** عند المرحلة **160** (`C24380wI.A0D`): تعرض الإعدادات شاشة الضبط فقط عند القبول، وإلا شاشة الاستقبال الخاصة بـ opt-in (5.1).
- حساب تابع (`C14980fa`): غير مؤهَّل؛ يغادر `PaaInteropMigrator` مجموعات interop ويعيد ضبط الإشعار (5.5).
- الجهاز الأساسي (`A02()`): لا تستطيع الأجهزة المرافقة الاشتراك أو الضبط.

---

## 3. الهوية: JIDs والنطاقات

### 3.1 النطاقات (found)

| النوع | الصنف | نوع JID | الصيغة | التحقق |
|------|-------|----------|--------|------------|
| مستخدم interop | `C99O` (`InteropUserJid`) | **22** | `{integrator}-{account}@interop` | شرطة (آخر واحدة تفصل)؛ integrator من 1-3 أرقام بلا `0` بادئ ويُحلَّل كـ int؛ account من 1-15 رقماً بلا `0` بادئ |
| جهاز interop | `C41021lm` | **23** | `{integrator}-{account}:{device}@interop` | يجب أن يكون فهرس الجهاز **0**، وإلا `C09B` ("Interop device JIDs must have device index 0") |
| مجموعة interop | `C55529Oy6` (`GroupJid`) | **28** | `{gid}@interop.g.us` | gid من 1-20 رقماً، أول رقم 1-9، بلا `-` |

- `C0DZ.A0W` = النوع 22، `A0X` = 22 أو 23 (1:1)، `A0V` = 28، `A0U` = `A0X` أو `A0V` (أي محادثة interop)؛ مستخدم في 128 صنفاً. `C41021lm.getRawString()` يطبع دائماً `:0`. المصنع (`UserJid.JID_FACTORY.A04(str, "interop")`، `C9YC.A00`) يرمي `C09B` ("Invalid interop JID: ...") عند أي مخالفة للقواعد.
- معرّفات integrator في ردود IQ محصورة بين 1-999 (مثل قاعدة الأرقام الثلاثة). معرّفات المجموعات ليست بصيغة `creator-timestamp` القديمة؛ تأخذ عمليات MEX للمجموعات gid دون النطاق (`InteropGroupsManager.A00` يحذف `@...`).

### 3.2 الرمز الثنائي (found)

الوسم **244** `JID_INTEROP` (الكاتب `C40411kn.A00`، قارئ السمات `C24610wf`): السلسلة `user` (معرّف الحساب، أو gid للمجموعات) -> u16 **device** -> u16 **integrator** -> بايت **domain**.

بايت النطاق: **0** = `interop`، **2** = `interop.g.us`؛ أي قيمة أخرى ترمي خطأ ("invalid domain received for JID_INTEROP tuple"). يجب أن تحمل tuple المجموعة device 0 وintegrator 0 (وإلا "invalid interop group jid"). يعرض القارئ النطاق 0 بالشكل `{integrator}-{user}[:{device}]@interop` (يُحذف device عندما يكون 0). الوسم **245** (صيغة JID interop منفصلة في عملاء آخرين) ليس له معالج في هذا البناء (grep على `C24610wf` / `C40411kn`).

### 3.3 الربط والعرض (found)

| الموضوع | الحقيقة |
|-------|------|
| LID / PN | `WaJidMapRepository/setJidMapping refused mapping for interop JID`؛ JID الخاص بـ interop هو عنوان Signal الخاص به ومعرّف المحادثة |
| الاسم | مصدر الاسم `INTEROP_NAME` (`C0Y7`)، والقيمة من الحقل `display_name` لجهة الاتصال (`c06290Dn.A07().A00.A0b`)؛ محلِّل stanza الرسالة يقرأ `notify` و`display_name` لكل رسالة (`AbstractC33377Eg6.A02`)؛ استخدام `display_name` كاسم push لـ interop مستنتج |
| أعضاء المجموعة | تحليل مشاركي `w:g2` يُبقي JID الخاص بـ interop في سجل المشارك (`C23201A1a` -> `C228499uF.A00(c99o, ...)`)، إضافة إلى `display_name` و`lid` و`phone_number` و`join_time` |
| بيانات الملف الشخصي | لا صورة ملف شخصي ولا اسم: "Profile name and photo are not available in third-party chats" (سلسلة)؛ أيقونة integrator فقط (ذاكرة مؤقتة 8 MiB في `cache/interop_image_cache`، المحمِّل `interop_image_loader`) |

---

## 4. Integrators

### 4.1 النموذج (found)

لا يوجد اسم integrator ولا معرّف ثابت ولا جدول لأنواع المعرّفات في الكود أو `res/` أو `assets/`؛ الخادم يحدد أي integrators موجودة ومعرّفاتها وأسماءها وقدرتها على المجموعات. `A3X`: `A00` المعرّف، `A03` الاسم، `A02` الحالة (`ONBOARDING`، `ACTIVE`، `REMOVED`)، `A04` عنوان URL للأيقونة، `A05` optedIn، `A01` نوع المعرّف (`USERNAME`، `PHONE`، `EMAIL`)، `A06` supportsGroupMessaging. integrator الخاص بـ JID: `C99O.A00` -> `C227409sQ.A00` -> `A3X`.

### 4.2 الجلب (found، `C31107Dfz` الحالة 20، المحلِّل `C214369Ee`)

الطلب `<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><integrator fetch="all"/></iq>` (`to` = JID الخادم، الصنف `C19380nJ.A00`). النتيجة: `<integrator_list opted_in="true"><integrator id status identifier_type name icon opted_in><features group_messaging/></integrator>...</integrator_list>` (أسماء السمات found؛ شكل العقدة `features` مستنتج من المسار `features/group_messaging`).

خريطة السمات: `status` = `onboarding` / `active` / `removed`؛ `identifier_type` = `username` / `pn` / `email`؛ `features` -> `group_messaging` = `true` / `false`؛ `opted_in` افتراضه `true`. حدود المحلِّل: 0-999 integrator، المعرّف 1-999؛ يُسقَط الإدخال الذي بلا `name` أو `icon`؛ حالة أو نوع معرّف غير معروف يرمي خطأ. أخطاء IQ: `bad-request` (400)، `internal-server-error` (500) (`A1J.A02` / `A04`).

coroutine التحديث (`C24110Aar` الحالة 34، السجل `IntegratorManager/refreshIntegrators`) تكتب الجدول (5.6) والتفضيل `group_capable_integrators`. المحفزات التي عُثر عليها: فتح شاشة opt-in؛ معالج `<ack error>` العام (`C13X`) يحذف كل صفوف `integrator_display_name` عند رفض رسالة interop 1:1 (`C24110Aar` الحالة 35). لم تُحسم محفزات أخرى.

---

## 5. الموافقة، opt-in، الإعدادات

### 5.1 إشعار الموافقة (found)

معرّف الإشعار **20240306** هو إفصاح خصوصية (`C24380wI`، الصنف `PrivacyDisclosureDataManager`). المرحلة **160** = مقبول (`A0D`)؛ المراحل 105-399 تُعدّ "مؤهَّل/معروض" (`A02`). `InteropOptInManager.A01` (`C229349vm`):

```
A02() false -> log "interop is not enabled, stop"
notice 20240306 != 160 -> render notice (C32411Pr.A05); ARH.onUserOptedIn sets has_previously_onboarded and continues; dismiss / deny / error stop
else -> InteropOptInSelectIntegratorsActivity(entryPoint)
```

تُكتب المرحلة **162** بواسطة `PaaInteropMigrator` (`C24380wI.A09(null, 20240306, 162, false)`)؛ المعنى unknown (ليست 160، لذا يُعدّ الإشعار غير مقبول بعدها).

### 5.2 المعالج (Wizard) (found، `A4N`، `InteropOptInSelectIntegratorsActivity`)

```
Select integrators (list from table, header "Select the third-party apps you want people to message you from.")
   ▼
[AB 11479] Unified inbox option (COMBINED | SEPARATED) ──► else skip
   ▼
[AB 15732] Group privacy setting ("Who can add me to third-party groups") ──► else skip
   ▼
InteropOptInManager.A01: notice not accepted -> consent notice (5.1); accepted -> straight on
   ▼  onUserOptedIn
SetOptInIntegrators IQ (full list)
```

إذا كان الإشعار مقبولاً مسبقاً (التعديل من الإعدادات)، تخفي شاشة الاختيار زرَّي الإلغاء والمتابعة ويحفظ `C201718ig.A00` مباشرة (الحفظ عند التغيير مستنتج)؛ نوع الصندوق وخصوصية المجموعة صفّان منفصلان في fragment الضبط. يُستنتج أن خطوة خصوصية المجموعة تنتهي في `A01` (السجل `BaseInteropOptInViewModel onOptInContinue`). نقاط الدخول عدد صحيح (`entryPoint`) يُسجَّل في WAM (5.6).

### 5.3 SetOptInIntegrators (found، `C31107Dfz` الحالة 23، المحلِّل `C9EP`)

```xml
<iq type="set" xmlns="w:interop" to="s.whatsapp.net" id=".."><opt_in_integrators><integrator_list>
  <integrator id="12"/> ...      <!-- 0..999 entries, the full desired state -->
</integrator_list></opt_in_integrators></iq>   <!-- result: integrator_list/integrator[@id], each with an optional error child -->
```

معالجة العميل (`C24113Aau` الحالة 40): تُجمع الأخطاء لكل integrator؛ يُعاد كتابة الجدول في معاملة واحدة (يُمسح `opt_in_status` للجميع، ثم يُضبط للمطلوب مطروحاً منه المعرّفات الفاشلة). لا يوجد stanza منفصل لإلغاء الاشتراك: تستخدم حوارات إلغاء الاشتراك ومسار "turn off" نفس عملية set بقائمة أقصر (مستنتج من غياب أي stanza آخر لإلغاء الاشتراك؛ لم يُتتبَّع مسار القائمة الفارغة).

ربط أخطاء الواجهة (`InteropOptInSelectIntegratorsActivity.A0X`): الأكواد **500** و**810** و**800** -> "Apps can't be saved right now. Please try again later."؛ أي كود آخر أو null -> "Apps can't be saved right now."

### 5.4 شاشات الإعدادات (found، `AndroidManifest.xml`)

الشاشات (كلها في `AndroidManifest.xml`): `InteropSettingsActivity` مع fragments الرئيسي / Optin / Config (صفحة الاستقبال عندما لا يكون الإشعار مقبولاً، وإلا الضبط؛ الأسئلة الشائعة للمساعدة `317021344671277`)؛ `InteropOptInSelectIntegratorsActivity` (التطبيقات)؛ `InteropUnifiedInboxOptionActivity` ("Manage inbox"، COMBINED مقابل SEPARATED)؛ `InteropGroupPrivacySettingUpdateActivity` و`...AddBlocklistPickerActivity` (9.4)؛ `InteropReachNotificationSettingsActivity` ("Third-party chat requests"، 6.3)؛ `InteropOptOutDialogFragment` / `...IntegratorDialogFragment` ("Turn off third-party chats?")؛ `InteropConversationsActivity` (قائمة المجلد)؛ `InteropComposeSelectIntegratorActivity` و`...EnterInfoActivity` و`InteropSelectChatTypeActivity` (محادثة جديدة / مجموعة / جهة اتصال).

### 5.5 إلغاء الاشتراك والمرحِّل (migrator) (found)

عند إلغاء الاشتراك: تصبح المحادثات القائمة للقراءة فقط (لافتة في حقل الكتابة "Third-party chats are turned off. You can't send messages in this chat, and you won't receive messages."). `PaaInteropMigrator` (`C0q`): يعمل عندما يكون الحساب حساباً تابعاً (`C20K.A1W` = restricted) **و**الإشعار مقبولاً؛ يستدعي `LeaveInteropGroup` (`groups_to_leave`، أكواد الاستجابة ضمن {200, 400, 401, 403, 404, 405} تُعدّ منتهية)، ثم يكتب مرحلة الإشعار 162. توسعة "PAA" مستنتجة (تجربة العمر)؛ الارتباط بالحساب التابع found.

### 5.6 الحالة المخزنة والتحليلات (found)

| المخزن | المفاتيح / المخطط |
|-------|---------------|
| prefs `interop_ui` | `unified_inbox_option` (UNKNOWN / COMBINED / SEPARATED)، `who_can_add_me_to_interop_groups` (int)، `who_can_add_me_to_interop_groups_hash`، `who_can_add_me_to_interop_groups_deny_list` (مجموعة)، `optedInIntegratorNames` (مجموعة) + مفاتيح أسماء لكل معرّف، `interop_reach_enabled` (الافتراضي true)، `interop_reach_integrators` (مصفوفة int)، `interop_reach_notifs` (مجموعة من `id:name:display_name:t`)، `suspended_interop_groups` (مجموعة من gids)، `has_previously_onboarded`، `group_capable_integrators`؛ prefs `interop_badge_prefs`: `pref_interop_badge_disabled`، `pref_interop_badge_account_state`، `pref_interop_badge_third_party_chats_state` |
| الجدول `integrator_display_name` | `integrator_id` INTEGER PK، `display_name` TEXT، `status` INTEGER، `icon_path` TEXT الافتراضي `''`، `opt_in_status` INTEGER الافتراضي 0، `identifier_type` INTEGER الافتراضي 0، `group_messaging_supported` INTEGER؛ الفهرس `integrator_opt_in_index` على `opt_in_status` |
| جداول أخرى | `wa_block_list_interop` (فهرس فريد على `jid`)؛ صفوف `wa_address_book` مع `raw_contact_id = -5` و`jid LIKE '{id}-%@interop'` (`SAVED_INTEROP_CONTACTS`)، لا تُكتب في جهات اتصال الهاتف |
| WAM | 6684 (تسليم اللافتة)، 7044 (تدفق onboarding، معرّف الجلسة `InteropOnboardingSessionIdManager`)، 7168 (إجراء المستخدم)، 6680 (صندوق الطرف الثالث)؛ الحدث 1158 يحمل `interopContactsSize` و`interopContactsSizePerIntegrator` |

---

## 6. `w:interop` IQ set

تمر RPCs الخمس الخاصة بـ `DmaInteropRPCManager` عبر `MessageClientSmaxWrapper`؛ كل IQ يحمل `type` و`xmlns="w:interop"` و`to` = JID الخادم و`id`.

| العملية | النوع | الجسم | الحد | النتيجة |
|-----------|------|------|-------|--------|
| FetchIntegrators | get | `<integrator fetch="all"/>` | - | 4.2 |
| FetchUsers | get | `<users><user external_id integrator_id/></users>` | **1-20 مستخدماً** | 7.2 |
| SetOptInIntegrators | set | `<opt_in_integrators><integrator_list><integrator id/>` | 0-999 | 5.3 |
| GetReachabilitySettings | get | `<reachability_settings/>` | - | 6.3 |
| SetReachabilitySettings | set | `<reachability_settings enabled="true\|false"><integrator id/>...` | 0-999 | نتيجة / خطأ |
| Block / unblock | set | `<blocklist><item action="block\|unblock" jid="{interop JID}"/></blocklist>` | - | نتيجة؛ الأخطاء `IQErrorBadRequest`، `IQErrorInternalServerError` |

### 6.1 الحظر والإبلاغ (found)

يستخدم حظر interop `xmlns="w:interop"` (`C31106Dfy`، المساعد `C9EF`، السجل `InteropBlocklistHelper/getInteropBlocklist/error code:`) والجدول `wa_block_list_interop`. الواجهة: "Blocked in third-party chats"؛ يذكر حوار الحظر أن الأشخاص المحظورين على WhatsApp قد يظلون قادرين على الوصول إلى المستخدم في تطبيق الطرف الثالث. يستخدم الإبلاغ عن spam تدفق spam العام (`spam_flow`، `C9E2`) مع نص حوار خاص بكل integrator. توجيه الإشعارات: `AbstractC32331E9w` يربط xmlns `w:interop` بمعالج المعرّف **270**؛ `EnumC32096E0u.NOTIFICATION_W_INTEROP` = `"w:interop"`.

### 6.2 إشعار Ping (found، `X.0xL` المجهول في `C1S0`)

`<notification xmlns="w:interop" t=".."><ping display_name=".."><X id=".." name=".."/></ping></notification>` (الوسم `X` للابن الأول لـ `ping` لا يفحصه الكود).

يُقبل فقط ابن أول باسم `ping` (وإلا السجل `unknown tag=`). عندما يكون `A02()` true يُلحق `id:name:display_name:t` بالتفضيل `interop_reach_notifs`، ويعرض إشعاراً محلياً على القناة `critical_app_alerts@1` (النص "Chatting with people on third-party apps is an optional WhatsApp feature in the European Region."، الإجراء "Manage requests"، مستقبِل الإغلاق `InteropNotificationDismissReceiver`) ويسجّل WAM 6684. محفز الخادم (حاول شخص من integrator الوصول إلى المستخدم) مستنتج من نص الإعدادات "Get notified when someone wants to message you from a third-party app."

### 6.3 قابلية الوصول (Reachability) (found)

الإعدادات لكل **integrator** (الأبناء `<integrator id>`، الحد 0-999)، وليست لكل مستخدم. القيمة الافتراضية لـ `enabled` هي `true` في `interop_reach_enabled`. لم يُعثر على كود اشتراك presence لـ JIDs الخاصة بـ interop (مستنتج: قابلية الوصول تحل محلّه).

---

## 7. اكتشاف المستخدمين

### 7.1 FetchUsers (found، `C31107Dfz` الحالة 21، المحلِّل `C9EQ`)

تأتي JIDs الخاصة بـ interop من هذا IQ فقط؛ ليس لـ USync بروتوكول interop (WA_USYNC.md).

```xml
<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><users>
  <user external_id="alice@example.org" integrator_id="12"/>          <!-- 1..20 -->
</users></iq>
<!-- result -->
<users>
  <user jid="12-105012705411308@interop" external_id=".." normalized_external_id=".." integrator_id="12"/>
  <user external_id=".." normalized_external_id=".." integrator_id="12"><error code="404" text="item-not-found"/></user>
</users>
```

النتائج لكل مستخدم: النجاح `user[@jid]` (`C9DG`، يُحلَّل jid كـ `C99O`)؛ `item-not-found` الكود الافتراضي **404** (`C9DH`)؛ `forbidden` الافتراضي **403** (`C9DF`)؛ `internal-server-error` (`C9DE`).

أخطاء IQ بأكمله: `bad-request`، `internal-server-error`. قوائم النتائج في `C9FA`: غير موجود، ممنوع، خطأ خادم، خريطة محلولة `{(external_id, integrator) -> UserJid}`. يرفض الطلب والاستجابة كلاهما 0 أو أكثر من **20** مستخدماً.

### 7.2 إدخال المعرّف وجهات الاتصال المحفوظة (found، `InteropComposeEnterInfoActivity`)

| نوع المعرّف | الواجهة | القيمة المرسلة كـ `external_id` |
|-----------------|----|------------------------------|
| `USERNAME` | حقل واحد ("Enter Username") | نص |
| `PHONE` | منتقي البلد + الرقم | رمز البلد والرقم متصلان (مرشح لكل حرف، القاعدة لم تُتتبَّع) |
| `EMAIL` | حقل واحد | نص |

التدفق: اختيار التطبيق (`InteropComposeSelectIntegratorActivity`، integrators المشترَك فيها من الجدول) -> نوع المحادثة (`InteropSelectChatTypeActivity`: "New chat"، "New group" إذا كان AB 15732 وintegrator يدعم المجموعات، "New contact" إذا كان AB 25512) -> إدخال المعرّف -> FetchUsers -> فتح المحادثة على JID المُعاد. السلاسل: "This user can't be found" (غير موجود)، "This user is already a group member" (إضافة إلى مجموعة)، "Couldn't create the chat. Please try again.".

مع AB 25512، يحل `ContactFormActivity.verifyInteropIdentifierAndSave` المعرّف عبر FetchUsers (`C24113Aau` الحالة 41) ويحفظ صف `wa_address_book` (raw_contact_id -5)؛ "Usernames and contacts added to third-party chats will not save to your phone."

---

## 8. المراسلة

### 8.1 اختيار المسار (found)

فك التشفير (`ENP.A00`): عندما يكون AB **5760** مفعَّلاً وJID المحادثة يحقق `A0U` (interop 1:1 أو مجموعة interop)، يعالج النص المشفَّر `C34471Exu` (`DecryptionCallbackInterop`)؛ وإلا تعمل callbacks العادية. أنواع النص المشفَّر التي يعالجها `ENP` هي الشائعة: **0** (`msg`)، **1** (`pkmsg`)، **2** (`skmsg`، sender key)، **4** (مسار bot، ليس interop). إذن يستخدم interop نفس جلسات Signal وsender keys كالمحادثات الأصلية.

```
<message from="12-123[:0]@interop" ..><enc type=pkmsg|msg|skmsg v=2>...</enc></message>
   │  ENP.decryptMessage (Signal / sender key)
   ▼
C34471Exu.handlePlaintext
   │  remove padding (last byte = pad length; empty / zero / >= length fails, log DecryptUtil/removePadding)
   │  C33369Efy.A03(E0T.INTEROP_MESSAGE, ...)          ── message pipeline type "interop_message"
   ▼
C34720F4p (InteropChatMessageHandler)
   │  parse bytes as DTF (InteropMessage subset)
   │  unknown-field check -> failure 70
   │  C32718EOz.A00(EUQ) -> FMessage via type handlers; SKDM (group) processed if AB 38723
   ▼
store, receipt, notification
```

الإبلاغ عن الفشل: `C34720F4p.A00` يعيد `C33063Eaz(reason)` ويستدعي `A0Y(null, key, reason, 491)` في مسار الإيصال؛ `C34471Exu` يستدعي `C33369Efy.A07(.., 491, reason, ..)` للنص الصريح غير الصالح. القيمة الحرفية **491** مشتركة بينهما (المعنى غير محسوم).

### 8.2 مجموعة `InteropMessage` الجزئية للنص الصريح (found، `DTF`)

النص الصريح **ليس** `Message` الكامل. يعلن `DTF` هذه الحقول بالضبط، مرقَّمة كما في `Message` الكامل:

| الحقل | الرقم | النوع | المعالج | ملاحظات |
|-------|--------|------|---------|-------|
| `conversation` | **1** | string | `FBN` | نص عادي |
| `senderKeyDistributionMessage` | **2** | message | `C34720F4p` | معرّف المجموعة + axolotl SKDM؛ يجب أن يساوي معرّف المجموعة المحادثة عندما تكون المحادثة مجموعة |
| `imageMessage` | **3** | message | `FBK` | |
| `extendedTextMessage` | **6** | message | `FBN` | حقول معاينة الرابط |
| `documentMessage` | **7** | message | `FBI` | ليس عندما يكون `type` في stanza هو `medianotify` |
| `audioMessage` | **8** | message | `FBH` | الملاحظات الصوتية عبر `ptt` |
| `videoMessage` | **9** | message | `FBL` (بلا `gifPlayback`) / `FBJ` (`gifPlayback`) | |
| `reactionMessage` | **46** | message | `FBM` | |
| `ptvMessage` | **66** | message | لم يُعثر على معالج | مقبول من المخطط ويُفحص للحقول غير المعروفة؛ لا يوجد محلِّل FMessage في السجل (استقبال video-note غير محسوم) |

يقرأ فحص الحقول غير المعروفة عدد الحقول غير المعروفة بالانعكاس (reflection) من `DTF` ومن الرسائل الفرعية للصورة والفيديو وPTV والصوت والمستند والنص الموسَّع والتفاعل؛ عدد 1 أو أكثر يعيد الفشل **70**. لذلك تُفشل الحقول خارج `DTF` الرسالة: مثلاً `messageContextInfo` (35)، `protocolMessage` (12)، الملصق، جهة الاتصال، الموقع، الاستطلاع (مستنتج من المخطط؛ لم يُختبر أثر حقل بعينه).

### 8.3 أنواع الرسائل المدعومة والحدود (found)

| النوع | القواعد المفروضة عند الاستقبال (سبب الفشل) |
|------|--------------------------------------------|
| نص، فيديو | `conversation` أو `extendedTextMessage.text`، يُقتطع إلى **65536** حرفاً؛ معاينة الرابط فقط إذا كان `matchedText` عنوان URL صالحاً وموجوداً في النص؛ يُقتطع العنوان والوصف إلى 65536؛ نوع المعاينة يُربط بـ 0 و1 و4 و5 و6 و7؛ يتشارك الفيديو وGIF محلِّل الوسائط `C33395EgO.A05` (`gifPlayback` يختار `FBJ`) |
| صورة | `mediaKey` مطلوب (16)؛ `fileLength` >= 0 (13)؛ `fileSha256` 32 بايت (14)؛ `fileEncSha256` 32 بايت إذا وُجد (14)؛ mime **فقط `image/jpeg` أو `image/png`** (17)؛ يُنسخ `directPath` والعرض والارتفاع؛ ثلاثية الصورة المصغرة (direct path، sha، enc sha) اختيارية؛ تُقبل المسح التدريجي (progressive scans) عندما تكون أطوال المسح 2-20 وطول `scansSidecar` / 10 يساوي العدد والمجموع يتسع في int |
| صوت | `mediaKey` مطلوب (16)؛ `fileLength` > 0 (13)؛ التجزئات 32 بايت (14)؛ يجب أن يكون mime نوع صوت معروفاً (17)؛ العلم `ptt`؛ `waveform` يُحتفظ به فقط إذا كان 1-192 بايت؛ `backgroundArgb`؛ `seconds` |
| مستند | `mediaKey` مطلوب (16)؛ `fileLength` >= 0 (13)؛ التجزئات 32 بايت (14)؛ `title` يُقتطع إلى 65536؛ تُحفظ الصورة المصغرة JPEG إذا اجتازت فحص الحجم |
| تفاعل | `key.id` و`key.remoteJid` غير فارغين؛ `text` مع إصدار تعديل غير صفري يُرفض (تحذير `edit version and text message are both set`)؛ يُحتفظ بـ `senderTimestampMs`؛ يجب أن ينتج stanza بـ `type="reaction"` رسالة تفاعل (وإلا الفشل **76**) |
| رد / اقتباس | `ContextInfo` مع `stanzaId` و`participant` والرسالة المقتبسة (تُحلَّل كـ `DTF` مجدداً، `ContextInfoProtobufInterop`)، `quotedType`؛ في جهة الإرسال `InteropContextInfoBuilder` يسلسل الرسالة المقتبسة تكرارياً |

غير مقبول (خارج الحقول التسعة): الملصقات، جهات الاتصال، المواقع، الاستطلاعات، الأحداث، القوالب، العرض لمرة واحدة (view-once). تخفي أداة اختيار المرفقات إدخالات جهة الاتصال والموقع والاستطلاع والحدث وحالة المجموعة وimagine والدفع وpix والتحويل في محادثات interop (فحوصات `A0L` و`A0M` و`A0P` و`A0Q` و`A0R` و`A0T` و`A0U` و`A0X` في `ConversationAttachmentContentView`)؛ المستند والكاميرا والمعرض والصوت لا تقيدها فحوصات interop (يُستنتج بقاؤها). الرسائل المؤقتة (disappearing) غير مدعومة ("disappearing messages are not supported in third-party chats"، وتُستثنى أيضاً من إعداد المؤقت الافتراضي). تنتقل بايتات الوسائط عبر مسار وسائط WhatsApp العادي (المفتاح والتجزئات و`directPath` في الرسالة؛ قيمة تحليلات مصدر التنزيل 15 = `interop`).

### 8.4 جهة الإرسال (found)

| الخطوة | السلوك |
|------|-----------|
| المسلسِل (Serializer) | `C33446EhE`: نوع JID المحادثة 22/23 (`A0X`) يستخدم مسلسل interop (`C32718EOz.A01` مع `ADs` لكل نوع، السجلات `buildE2eInteropMessage`)؛ المحادثات الأخرى تستخدم البنّاء العادي، لذا **مجموعات** interop (النوع 28) تأخذ البنّاء العادي |
| صنف FMessage غير مدعوم | المعالج `FBG` -> يرمي `E3G` 70 قبل الإرسال؛ صنف خاطئ لمعالج -> `E3G` 0 |
| فحوصات الصورة | mime `image/jpeg` أو `image/png` وإلا `E3G` 17 (`null` يصبح `image/jpeg`)؛ تجزئة ليست 32 بايت `E3G` 14؛ مفتاح وسائط مفقود `E3G` 16؛ مساهمو stanza `F6B` و`F6G` و`F6I` و`F68` و`F69` و`F6H` و`F6M` و`F6X` ليس لهم فرع interop (الإرفاق غير محسوم) |
| المشفِّر (`F6P`) | في محادثات interop (`A0U`) يتخطى المشفِّر `C33284Eea.A02` (يضيف بيانات وصفية لقائمة الأجهزة عبر `AbstractC30999De0.A03`، مستنتج) ويتخطى `paddingBytes` (الحجم من AB 1723) |
| `<meta>` (`F6K`) | يُتخطى `content_type="add_on"` في محادثات interop |
| رمز الإبلاغ (`F6L`) | يُتخطى عندما يكون الهدف JID جهاز interop |
| قائمة الأجهزة / ADV | فهرس جهاز interop دائماً 0؛ لـ `DeviceADVInfoHandler` فحص interop عند مدخله (`C24230w2`، الخروج المبكر مستنتج)؛ لا يمكن توزيع متعدد الأجهزة (fan-out) (مستنتج: جهاز واحد لكل جهة اتصال) |

فروق أخرى عن الرسائل الأصلية: تستخدم محادثات interop نوع المسار `interop_message` (`E0T`) بدلاً من أنواع النص / الوسائط / التفاعل؛ قيمة نوع المحادثة في WAM هي 5 في حدث فك التشفير (`AbstractC33424Egr`) و6 في حدث `FNR` (الأصلي 3 / 1)؛ إضافات message-secret (أصوات الاستطلاع، التفاعلات المشفرة، انظر WA_MESSAGE_SECRETS.md) ليست ضمن الحقول التسعة، لذا لا يمكنها الوصول إلى محادثات interop (مستنتج).

---

## 9. مجموعات Interop

### 9.1 النموذج (found)

المجموعة هي `{gid}@interop.g.us` (النوع 28). الأعضاء حسابات WhatsApp (تُضاف كـ JIDs مستخدمين من نوع **LID**؛ found في مسار الإضافة، ومسار الإنشاء مستنتج بالمثل) وJIDs الخاصة بـ interop. تأتي بيانات المجموعة الوصفية من MEX بدلاً من `w:g2`: `C11410Yt.A0F` يستدعي `GroupXmppMethods/sendGetInteropGroupInfo` للنوع 28. الحالة `UNSET` و`ACTIVE` و`SUSPENDED`؛ تُحفظ gids المعلَّقة في التفضيل `suspended_interop_groups`. لافتات حقل الكتابة: مجموعة معلَّقة "You can't send messages to this group because all third-party members have left."؛ ألغيت العضوية أو أُزيلت "... because you're no longer a member."

### 9.2 عمليات MEX (found؛ معرّفات doc من `assets/whatsapp-android-mex_client_persist_ids.json`)

| العملية | doc_id | الحقل الجذري | الإدخال | المخرجات / ملاحظات |
|-----------|--------|-----------|-------|----------------|
| `GroupsCreateInteropGroup` | `25726817620301611` | `xwa2_interop_group_create` | `input.participants[{jid}]` | `group`: `gid` و`creation_time` و`creator_v2` و`display_name` و`participants_v2`؛ لا يُرسل موضوع |
| `LeaveInteropGroup` | `25346167795013271` | `xwa2_interop_group_leave` | `input.groups_to_leave[{gid}]` | `response_code` لكل مجموعة؛ {200, 400, 401, 403, 404, 405} تُعامل كنهائية |
| `AddParticipantsToInteropGroup` | `25732168276369451` | `xwa2_interop_add_participants_to_group` | `input.gid`، `input.participants[{jid}]` | أعضاء WhatsApp يُربطون PN إلى LID أولاً؛ LID قيمته `null` يُجهض الاستدعاء |
| `QueryInteropGroupInfo` | `32734144032867938` | `xwa2_interop_group_query_by_id` | `group_input.gid` | `state` و`gid` و`creation_time` و`creator_v2` و`participants_v2` |
| `InteropPrivacySettingsQuery` | `24849123668112654` | `xwa2_fetch_wa_users` -> `interop_privacy_settings` | `interop_privacy_settings_query_input{feature, dhash}` لـ LID الخاص | `settings_data` و`dhash` و`denied_contacts[{jid}]` |
| `InteropPrivacySettingsUpdate` | `25421856497452763` | `xwa2_interop_privacy_setting_update` | `feature`، `setting` | `success` |
| `InteropPrivacySettingWithContactListUpdate` | `24913399124998598` | `xwa2_interop_privacy_setting_with_contact_list_update` | `contact_list_type` و`contacts` و`dhash` (`none` إن غاب) و`feature` و`setting` | `success` |

تظهر أخطاء الإنشاء والإضافة كـ "This group couldn't be created" / "Make sure everyone you add to this group has third-party chats turned on." / "A group with these members already exists." (سلاسل found). يتطلب إنشاء المجموعة مستخدماً واحداً على الأقل من integrator المختار ("To create this third-party group, you need to select at least one %1$s user.").

### 9.3 إشعارات MEX (found، `C0WQ`)

| الإشعار | المعالج | الأثر |
|--------------|---------|--------|
| `NotificationInteropGroupCreateUpdate` | فرع `AbstractC23194A0r` (السجل `CreateInteropGroupNotificationHandler/`) | ينشئ المجموعة محلياً من `gid` والمنشئ والمشاركين |
| `NotificationInteropGroupParticipantsUpdate` (`Xwa2NotifyInteropGroupOnParticipantChange`) | `A0B` | يضيف مشاركين بالمصدر `general_chat_auto_add`، ويزيل المشاركين الذين غادروا؛ يعود مبكراً (`no updates needed to gid=`) عندما يكون `C22300su.A15()` false |
| `NotificationInteropGroupPropertyUpdate` | `A0C` | `state` ACTIVE أو SUSPENDED -> `suspended_interop_groups` |

### 9.4 من يستطيع إضافتي (found، الميزة `GROUPADD`)

تعداد الإعداد `C9U8`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` و`ALL` و`MYCONTACTS` و`MYCONTACTSEXCEPT` و`MYCONTACTS_AND_ENABLED_INTEROP_INTEGRATORS` و`NONE`. يحمل متغير قائمة جهات الاتصال قائمة المنع (`contact_list_type`، `contacts`). النص: "You can only be added to third-party chats by people who either use or have selected the same messaging app." يُخزَّن الإعداد لكل LID خاص ويُخبَّأ مع `dhash`؛ الإنفاذ على الخادم (مستنتج)، والعميل يعرض الإعداد فقط.

---

## 10. قائمة المحادثات، نموذج الخيط (thread)، الواجهة

| العنصر | الحقيقة (found) |
|------|--------------|
| الخيط | محادثة واحدة لكل JID خاص بـ interop (1:1) أو لكل gid؛ تُخزَّن في جداول المحادثات العادية؛ لا جدول خيوط منفصل |
| المجلد | `InteropConversationsActivity` / `Fragment`؛ عرض الرأس `InteropView` في قائمة المحادثات (`C31071Ju`، السجل `ChatListInteropChatsDelegate/`)؛ يظهر عندما يكون المستخدم مؤهَّلاً والإشعار مقبولاً، أو عند وجود محادثات interop مسبقاً؛ يُخفى عندما يكون الصندوق COMBINED |
| وضع الصندوق | SEPARATED: مجلد داخل الصندوق الرئيسي أو قائمة "More"؛ COMBINED: محادثات interop مدرجة في تبويب Chats (شريحة التصفية `interop` في مرشحات المحادثات، `THIRD_PARTY_FILTER`) |
| الصف / البحث | وسم اسم integrator وشارة الأيقونة على الصورة الرمزية؛ محادثات الطرف الثالث غير مشمولة في نتائج البحث |
| اللافتة / الشارة | "You're messaging someone outside of WhatsApp. Third-party apps may have different security."؛ شارة Home من `pref_interop_badge_*`، مقيدة بـ AB 7495 (`C230679y0`) |

---

## 11. Baileys (`baron-baileys-v2` 1.5.17، `src/Socket/interop.js`، `WABinary/decode.js`، المصدر مقروء، لم يُختبر شيء)

| الموضوع | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| Integrators | `12` (BirdyChat، email) و`13` (Haiket، pn) مضمَّنان في الكود | لا شيء في العميل؛ قائمة من الخادم |
| بحث دفعي | `INTEROP_BATCH_MAX = 256` | **20** (باني الطلب ومحلِّل الاستجابة) |
| إلغاء الاشتراك | `<opt_out_integrators><integrator_list>` | لا توجد عقدة كهذه؛ IQ opt-in بقائمة أقصر |
| ضبط قابلية الوصول | `<reachability_settings enabled><user external_id integrator_id/>` | أبناء `<integrator id/>` |
| الموافقة | `tos` IQ `trackable id=20240306 result=105`، ثم `160` | الإشعار 20240306 المرحلة 160 = مقبول (found)؛ صيغة السلك لـ IQ الإشعار لم تُتتبَّع |
| JID الثنائي | قارئ tuple 244 يرمي ما لم يكن النطاق = 0؛ الوسم 245 معالَج | الوسم 244 مع النطاق 0 **و**2 (المجموعات)؛ لا وسم 245 |
| الإشعارات | `type="interop"` مع `stella_interop_enabled` و`peer_device_presence` و`ig_profile` وfbid | معالج `w:interop` المعرّف 270 يعالج `ping` فقط |
| إرسال / استقبال | نص عادي كـ `conversation`، رمز الإبلاغ يُتخطى؛ تعليق في `Defaults/index.js`: استقبال interop غير منفَّذ | المسلسِل مقيَّد بالحقول التسعة؛ محلِّل `InteropMessage` صارم؛ معرّفات MEX للمجموعات والإشعارات متطابقة في النطاق |

لماذا يفشل (مستنتج من الكود المقارَن أعلاه):

| العَرَض | السبب | الإصلاح |
|---------|-------|-----|
| خطأ فك ترميز على JID مجموعة interop | قارئ tuple يرفض بايت النطاق 2 | قبول النطاق 2 -> `{gid}@interop.g.us`، مع اشتراط device وintegrator يساويان 0 |
| يُسقط النظير الرسالة بفشل حقل غير معروف | أي حقل خارج التسعة (مثل `messageContextInfo` مع `messageSecret`، `protocolMessage`) يفشل إذا كان النظير يشغّل نفس التحليل الصارم (مستنتج؛ لم تُتتبَّع إرسالات interop في Baileys لهذه الحقول) | بناء `Message` بالحقول 1 و2 و3 و6 و7 و8 و9 و46 فقط (و66) |
| إلغاء الاشتراك بلا أثر | `opt_out_integrators` غير موجود في العميل | إرسال SetOptInIntegrators بالمعرّفات المتبقية |
| لا شيء يصل إلى الجلسات المرافقة | جهات اتصال interop لها device 0 فقط | إبقاء interop على الجلسة الأساسية |

---

## 12. حالات الخطأ

| العَرَض | السبب | الموضع |
|---------|-------|-------|
| شاشات interop تُغلق فوراً أو لا تظهر أبداً | `C32001Oa.A02()` false: العلم 7495 معطَّل، أو حساب تابع، أو جهاز مرافق | 2.1 |
| "Apps can't be saved right now" | فشل SetOptInIntegrators؛ الأكواد 500 / 810 / 800 تحصل على نص "try again later" | 5.3 |
| "This user can't be found" | FetchUsers `item-not-found` (404) | 7.1 |
| استثناء JID interop غير صالح | integrator ليس 1-3 أرقام / صفر بادئ، account ليس 1-15 رقماً، فهرس الجهاز ليس 0 | 3.1 |
| المجموعة لم تُنشأ / حقل الكتابة معطَّل | خطأ إنشاء MEX أو مجموعة أعضاء مكررة / إلغاء الاشتراك، مجموعة معلَّقة، لم يعد عضواً | 9.1، 9.2 |
| رسالة واردة مُسقَطة، السبب 70 / 13 / 14 / 16 / 17 / 76 / 26 | حقل أو نوع غير معروف بلا معالج / حجم سيئ / طول تجزئة سيئ / مفتاح وسائط مفقود / mime غير صالح / عدم تطابق نوع التفاعل / استثناء تحليل | 8.2، 8.3 |
| تجاهل SKDM للمجموعة | AB 38723 معطَّل (السجل `sender key distribution message skipped`) | 8.1 |
| أسماء integrators مفقودة بعد خطأ إرسال | ack error مسح `integrator_display_name` | 4.2 |

---

## 13. فروقات رئيسية

| لا تخلط بين | الحقيقة |
|----------------|------|
| `w:interop` مقابل USync | اكتشاف جهات الاتصال هو FetchUsers على `w:interop` (حد أقصى 20)، وليس بروتوكول USync |
| `@interop` / `@interop.g.us` / `@g.us` | مستخدم وجهاز، مجموعة، مجموعة أصلية؛ JID الخاص بـ interop لا يُربط أبداً بـ LID أو PN |
| `InteropMessage` مقابل `Message` | الاستقبال يقبل 9 حقول؛ الإرسال يحذف السياق والحشو (padding) لـ interop |
| رمز الخصوصية `trusted_contact` | مهمة privacy-token عامة (WA_TCTOKEN_CSTOKEN.md)؛ لم يُعثر على كود خاص بـ interop في هذا البناء |
| "interop" في UPI | `IndiaUpiInterOpHybridActivity` و`IndiaUpiInteropSendToUpiActivity` وأعلام ملاحظة الدفع `isInterop` ميزات مدفوعات، لا علاقة لها |
| "interop" في Compose / EXIF | `androidx.compose.ui.viewinterop` و`InteroperabilityIFDPointer` مكتبات |
| مؤهَّل مقابل مشترك مقابل موافقة | العلم 7495 = مؤهَّل؛ `opted_in` لكل integrator يأتي من الخادم؛ الموافقة = الإشعار 20240306 المرحلة 160 |

---

## 14. التدفق الكامل

```
[User]              [Client]                                   [WA server]              [Integrator app]
  │ Settings > Third-party chats
  ├──────────────────► A02(): flag 7495, primary, not dependent
  │                    notice 20240306 != 160 ──► show ──► accept ──► stage 160
  │ apps (+ inbox type, + group privacy)
  ├──────────────────► SetOptInIntegrators ─────────────────► opted_in list; table rewritten
  │ New chat > app > id
  ├──────────────────► FetchUsers (1..20) ──────────────────► jid 12-<account>@interop / 404 / 403 / 500
  │ send text / image / video / audio / doc / reaction
  ├──────────────────► restricted Message (no context, no padding), Signal encrypt, device 0
  │                    <message to=..@interop> ─────────────► bridge (inferred) ───► [Integrator app]
  │                    <message from=..@interop><enc/> ◄──────────────────────────── reply
  │                    ENP -> DecryptionCallbackInterop -> DTF parse (unknown field -> 70) -> FBx -> FMessage
  │ ◄──────────────── chat row, notification
  │                    <notification xmlns=w:interop><ping/> ◄─ server (trigger inferred)
  │ ◄──────────────── local notification "Manage requests"; reachability per integrator
  │ New group (flag 15732)
  ├──────────────────► GroupsCreateInteropGroup (LID + interop JIDs) ──► gid@interop.g.us
  │                    MEX notifications: create / participants / property; SUSPENDED -> composer blocked
```

---

## 15. المجهولات

| الموضوع | الحالة |
|-------|-------|
| صيغة السلك لـ IQ إشعار الموافقة | لم تُتتبَّع؛ المعروف فقط المرحلتان 160 (مقبول) و162 (يكتبها migrator) |
| الجسر على جهة الخادم، التسليم إلى integrator، التعامل مع المفاتيح في ذلك الطرف | غير مرئي في العميل؛ يستخدم العميل جلسات Signal وsender keys العادية |
| تغيير الهوية / رقم الأمان لجهات اتصال interop | لم يُتتبَّع |
| المكالمات، الاستطلاعات، التعديلات، السحب (revokes)، تغيير الهوية / رقم الأمان لمحادثات interop | لم يُعثر على مسار كود interop (لا سلسلة interop في كود المكالمات)؛ لم يُتتبَّع |
| استقبال PTV (`ptvMessage`) | الحقل مقبول، لم يُعثر على محلِّل |
| القيمة الحرفية 491 في مسار الفشل؛ أكواد الخطأ 810 / 800؛ محفزات FetchIntegrators عدا شاشة opt-in | غير محسومة |
| قارئو الأعلام 3953 و5759 و6613 و18670 و20999 و11518 و13532 و14070 | لا قارئ حرفي؛ قد تُقرأ عبر descriptors |
| إيصالات القراءة نحو جهات اتصال interop | `ClientPayload.interopData` (الحقل **38**، `C38671hT`: `accountId` 1، `token` 2، `enableReadReceipts` 3) موجود في المخطط؛ لا شيء في هذا البناء يملؤه |
| هل يفرض الخادم قاعدة المنطقة الأوروبية | نص الواجهة فقط؛ لا فحص في العميل |
