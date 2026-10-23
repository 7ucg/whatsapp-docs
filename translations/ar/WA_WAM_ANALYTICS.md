<!-- src-sha1: c6955a2c041a57de36c902dfa247b0b65dc0b530 -->
# WhatsApp تحليلات WAM — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** قياسات WAM ("WhatsApp Metrics") عن بُعد في Android: نموذج الأحداث (معرّفات الأحداث، الحقول، القنوات REGULAR / REALTIME / PRIVATE / channel 3)، مسار التسجيل في Java، أخذ العينات وأوزان كل حدث، بيئة التشغيل الأصلية (`libwhatsapp.so`)، السمات المشتركة، المخازن المؤقتة على القرص، صيغة WAM السلكية، الرفع العادي (`w:stats` IQ)، الرفع الخاص (credential IQ + نقل منفصل)، `wam_daily` والمهمة اليومية cron، معرّفات private-stats وتدويرها، معالجة الخصوصية، feature flags، عائلات الأحداث البارزة، المقارنة مع Baileys، وما يبقى مجهولًا

---

## 1. ما هو WAM في هذا الإصدار

WAM هو مسار قياسات من جهة العميل: تُنشأ أحداث مُنمَّطة في Java (أو تُحوَّل من إحصاءات المكالمات الأصلية)، ثم تُؤخذ منها عينات، وتُسلَّم إلى بيئة تشغيل أصلية تُسلسلها إلى مخازن مؤقتة ثنائية مخزّنة تحت `files/wam/`، ثم تُرفع إلى الخادم. هو قياس صادر فقط. لا يعتمد عليه شيء في بروتوكول الدردشة. كل العبارات مستمدة من التحليل الساكن لـ APK المفكوك (`versionCode 264100600`) مع السلاسل الأصلية في `libwhatsapp.so` وبنية ملفات المخزن المؤقت الموجودة في دليل بيانات تطبيق من هذا الإصدار. المستويات: **found** = قُرئ في الشيفرة أو في ملف مخزن مؤقت، **inferred** = مستنتج، **unknown** = غير قابل للحل بالتحليل الساكن. الأسماء المشوشة خاصة بكل إصدار وأُعيد حلّها من سلاسل ثابتة في 2.26.41.6 (سلاسل السجل، أسماء الأحداث `wam_*`، قيم سمات IQ).

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| الفئة الأساسية للحدث | `C0Fc` | `code` و`samplingRate` و`bufferChannel` و`psId`؛ دوال مجردة `getFieldsMap()` (معرّفات رقمية)، `getFieldsMapForFalco()` (أسماء)، `getEventNameForFalco()`، `validate()` |
| صف أخذ العينات | `C036300x` | مستويات الوزن؛ `A00` هو الوزن الذي يستخدمه المُعاين |
| محلّل أخذ العينات | `C0Fg` + `C06580Fh` | تجاوز وزن كل حدث من prefs `field-stats-events-sampling` |
| Logger (واجهة WAM runtime) | `C06650Fo` (`InterfaceC06640Fn`)؛ `C40098Hdb` يوزّع إليه وإلى Falco logger في Java `C40099Hdc` | `CNW` إرسال، `CNI` إرسال مع أخذ عينات، `CXW` flush، `CUj` إعادة ضبط، `CXZ` flush مع انتظار (2500 ms)؛ التهيئة في `RunnableC29323CoA` الحالة 33 |
| جسر JNI | `com.whatsapp.wamsys.JniBridge` | `jvidispatch*` من Java إلى الأصلي، `jnidispatch*` من الأصلي إلى Java |
| السمات المشتركة | `C06590Fi` (`CYl(value, attrId, channel)`)، التهيئة في `RunnableC29340CoR` الحالة 0 | سمات عامة لكل قناة |
| معالج AB-props | `C28894Cgv` | يحلل `<props>` بما فيها `event_code` / `sampling_weight` |
| الحدث اليومي | `C0Fp` (`wam_daily`، المعرّف 1158) | حالة الجهاز والتطبيق |
| المهمة اليومية cron | `C28643Ccj` (`WamDailyEventDailyCron`)، المنبّه في `BEL` (`DailyCronAction`) | تبني `C0Fp` وترسله |
| حدث المكالمة | `com.whatsapp.fieldstats.events.WamCall` (المعرّف 462) | يُنشأ من إحصاءات المكالمة الأصلية، ويُرسل بواسطة `C24895Anr` |
| بيئة التشغيل الأصلية | `libwhatsapp.so` (`WAMRuntime`, `WAMBufferStore`, `WAMTransportRegular`, `WAMTransportPrivate`, `WAMPSIDProfile`) | المخازن المؤقتة، المعرّفات، الرفع |

ليس WAM، لا تخلط (انظر 17): Falco shadow logger في جهة Java (`C40099Hdc`, `FFLogger`)، ومُرسِل الأعطال والسجلات الموسوم بـ `wam-event/<name>`، ورموز ACS لمشاريع أخرى، والكلمة `fieldstats` التي تستخدمها إحصاءات المكالمات الأصلية (`prepare_wa_call_fieldstats`).

إشارات سلامة العميل التي تنتقل داخل WAM (`is_rooted`, `is_genymotion`, `is_whatsapp_plus_user`، والسمتان 6251 و10255) موصوفة في [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) ويُشار إليها هنا فقط.

---

## 2. نموذج الأحداث

### 2.1 فئة الحدث (`C0Fc`)

كل حدث فئة مولَّدة؛ المُنشئ هو `super(code, samplingTuple, bufferChannel, psId)`، مثلًا `wam_daily`: `super(1158, new C036300x(1, 1, 1, false), 0, -1)`، و`getEventNameForFalco() = "wam_daily"`، و`internalFalcoMigrationBatchNumber() = 12`.

| العضو | المعنى | المستوى |
|--------|---------|------|
| `code` | معرّف الحدث الرقمي (1158 لـ `wam_daily`، 460 `wam_login`، 462 `wam_call`، 854 `wam_message_send`) | found |
| `samplingRate` | `C036300x(a, b, c, flag)` يُخزَّن كـ `A02=a, A01=b, A00=b, A03=c`؛ المُعاين يستخدم `A00 = b`. الافتراضي `C0Fc.DEFAULT_SAMPLING_RATE = (1, 20, 20)` | found |
| `bufferChannel` | 0..3، انظر 2.2 | found |
| `psId` | `-1` = غير خاص؛ وإلا فهو hash لمفتاح private-stats، انظر 2.3 | found |
| `getFieldsMap()` / `getFieldsMapForFalco()` | معرّف الحقل الرقمي إلى القيمة (يُمرَّر إلى الأصلي) / الاسم بصيغة snake_case إلى القيمة | found |
| `validate()` | قائمة المخالفات (`.nonnull` وقواعد مشابهة)، انظر 3.2 | found |
| `serialize(C3T8)` | الجسم هو `throw new NullPointerException("serialize")`؛ التسلسل أصلي | found |

تستخدم الحقول أنواع Java المغلّفة (`Boolean`, `Integer`, `Long`, `Double`, `String`). تنتقل enums والمؤقتات كأعداد صحيحة (inferred من دالة ضبط السمة التي تقبل فقط null / String / Integer / Long / Double / Boolean). لدى `wam_daily` 218 خانة رقمية و205 خانات مسمّاة (13 خانة رقمية null فقط)، مطابقة للعدد في 2.26.35.8 السابق.

### 2.2 القنوات

| `bufferChannel` | الأحداث (المحلَّلة) | الاسم (التسميات inferred؛ Java يستخدم أعدادًا صحيحة عادية) | المستوى |
|-----------------|-----------------|------|------|
| 0 | 824 | REGULAR | found |
| 1 | 8 | REALTIME | found |
| 2 | 168 | PRIVATE (يتطلب معرّف private-stats، انظر 2.3) | found |
| 3 | 8 | private-stats مجهول في الزمن الحقيقي، "RTPS" في سلاسل السجل الأصلية (تسمية inferred) | found / inferred |

المجموع المحلَّل: 1,008 فئة حدث بمعرّفات متمايزة. يُمرَّر التعيين دون تغيير إلى الأصلي (وسيط القناة 0..3 في `jvidispatchIIIIIOO`). أي قيمة أخرى ترمي `IllegalArgumentException("Unsupported channel type")`.

أحداث REALTIME (المعرّفات): 2098 `wam_ui_action_real_time`, 5504 `wam_wefr_client_exposure`, 5278 `wam_android_test_realtime`, 6640 `wam_wefr_group_client_exposure`, 6088 `wam_restore_contacts_realtime_event`, 4290 `wam_wa_fs_chat_transfer`, 2872 `wam_xplatform_migration_export`, 6266 `wam_cac_client_event` (found).

أحداث القناة 3: 5164 `wam_wam_test_anonymous_realtime`, 7312 `wam_mm_signal_undisclosed`, 7352 `wam_mm_signal_realtime`, 6160 `wam_wamo_video_event`, 6158 `wam_wamo_ctwa_1pd_conversion`, 7956 `wam_wamo_promo_pog_impression`, 5712 `wam_wamo_promo_reporting_events`, 7350 `wam_wamo_alv2_link_click` (found). تُسقط `C06650Fo.A01` حدث القناة 3 ما لم يكن رمزه في مصفوفتين مضمّنتين في الشيفرة (`AbstractC38512Gog.A00` 3 معرّفات، `A01` 5 معرّفات). هذه المعرّفات الثمانية هي بالضبط أحداث القناة 3 الثمانية، لذلك لا يُسقط الفحص شيئًا في هذا الإصدار (inferred من مجموعات المعرّفات).

### 2.3 معرّفات Private-stats (`psId`)

| `psId` (int) | سلسلة المفتاح في ملف الـ profile الأصلي | التدوير (أيام) | الأحداث | المستوى |
|--------------|-----------------------------------|-----------------|--------|------|
| `-1` | لا شيء (غير خاص) | – | 832 (regular + realtime) | found |
| `0` | `none` (القيمة العامة 6005 للمخزن المؤقت تحمل السلسلة `none`) | – | 94 (86 خاصة + 8 من القناة 3) | found؛ تعيين "none" inferred |
| `113760892` | `default_ps_id` | أبدًا (`-1`) | 66 | found |
| `56300709` | `id_pre_metrics` | أبدًا (`-1`) | 1 (`wam_ps_app_launch`) | found |
| `248614979` | `id_ttl_daily` | 1 | 4 | found |
| `42196056` / `191000728` | `id_ttl_weekly` / `id_ttl_monthly` | 7 / 30 | 0 | found |
| `37887164` | `id_ttl_90_days` | 90 | 1 (`wam_clock_skew_difference_t`) | found |
| `152546501` | `group_exit_experience_id` | 30 | 4 | found |
| `216763284` | `group_safety_check_id` | 30 | 6 | found |

قُرئت سلاسل المفاتيح وأيام التدوير من ملفات `WAMMetadataPSIDProfile-*` الثمانية (انظر 6.3)، وأعداد الأحداث من فئات الأحداث.

### 2.4 الأوزان عبر الكتالوج

الوزن الفعّال في المخطط `A00` لكل حدث (يُحتفظ بالحدث باحتمال 1/الوزن ويُخزَّن الوزن مع الحدث):

| الوزن | الأحداث | أمثلة |
|--------|--------|-----------------|
| 1 (دائمًا) | 826 | `wam_daily`, `wam_registration_complete`, `wam_blocking_funnel` |
| 5 / 10 | 6 / 12 | `wam_message_send` (5)، `wam_message_context_menu_actions` (10)، `wam_ui_action_real_time` (10) |
| 20 | 135 | `wam_message_delete_actions`, `wam_message_high_retry_count`، وكل الأحداث على `DEFAULT_SAMPLING_RATE` (81) |
| 100 / 200 | 4 / 2 | `wam_login_stage_reliability` (100) |
| 1000 | 17 | `wam_message_stanza_receive`, `wam_call_stanza_receive`, `wam_status_stanza_receive`, `wam_iq_send`, `wam_push_latency`, `wam_db_perf` |
| 10000 | 4 | `wam_receipt_stanza_receive`, `wam_android_profilo_usage`, `wam_android_message_target_perf`, `wam_notification_highlight_result` |

الوزن ليس مفتاح تفعيل: يستطيع الخادم تجاوزه لكل حدث (8.2). حدث واحد بوزن ثابت وقت البناء لم يُصنَّف.

---

## 3. مسار التسجيل في Java

### 3.1 مسار الإرسال

`CNW` = `CNI(event, null, false)`: يحلّ الوزن (8.1)، ويشغّل قائمة السماح للقناة 3 (`A01`)، ثم ينفّذ runnable `X.1Fc` على منفّذ WAM (`C06600Fj.A01`):

| الخطوة | السلوك | المستوى |
|------|-----------|------|
| مزلاج وقت التشغيل | `C06650Fo.A0K` (`CountDownLatch`) يحجب المنفّذ حتى تُهيَّأ السمات المشتركة ("wamruntime/initializeCommonAttributes: runtime initialized") | found |
| التحقق | يعمل `event.validate()` للقناتين 0 و1 فقط (وليس لفئة حدث التحقق `C40251kT`). تتحول كل مخالفة إلى `wam_wam_validation_error_event` (المعرّف 5560) مع رمز الحدث المخالف وقيمة جلسة عشوائية وأجزاء القاعدة مفصولة بـ `;` | found |
| أوضاع Logger (`A04`) | `3`: للرموز في مجموعة مهيأة يكتب `traceIdInt` (64 بت عشوائي) في الحدث بالـ reflection؛ `10`: للأحداث التي تجتاز `C06630Fm` (Falco migration batch 1..16، وليست في قائمة الرفض) يكتب `dedupKey` (64 بت عشوائي)؛ `1` / `3`: يرسلان إضافةً حدث Falco (`_test$<name>` / `<name>_shadow`) | found |
| الإرسال | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fieldsMap)` بعد التأكد من تحميل المكتبة | found |
| مشغّل رفع السجلات | خاصية AB النصية **31314** تحمل `"code:N;code:M"`؛ إذا كان `Random.nextInt(N)==0` للرمز المُرسَل، يُطلب من مُبلِّغ الأعطال والسجلات رفع سجلات الجهاز بالوسم `wam-event/<falco name>`. هذا يرفع السجلات، لا المخزن المؤقت لـ WAM | found |

`dedup_key` و`trace_id_int` حقلان في مخطط الحدث (موجودان في `wam_login`, `wam_app_launch`, `wam_message_send`)؛ هما عشوائيان لكل حدث وليسا معرّفات مستخدم (inferred من المولّد).

### 3.2 قواعد التحقق

في `C0Fp` (`wam_daily`) يُبلَّغ دائمًا عن الحقل `ai_widget_installed` كمخالفة لأنه لا يوجد عضو في Java يسنده (القاعدة `daily .nonnull`)، وعن `default_after_read_enabled` حين يكون عضوه null. النتيجة (inferred): كل حدث يومي على القناة 0 ينتج أيضًا أحداث تحقق (المعرّف 5560).

### 3.3 مشغّلات flush ودورة الحياة

| المشغّل | الاستدعاء | العملية الأصلية | المستوى |
|---------|------|-----------|------|
| اتصال معالج الاتصال | `C0A4.BvO` -> `CKt(0)` | `jvidispatchIIO(4, 0, ctx)` | found |
| جارٍ الاتصال / انقطع | `BvP`, `BvQ` -> `CKt(1)` | `jvidispatchIIO(4, 1, ctx)` | found |
| اكتمال معالجة الرسائل غير المتصلة (`XmppStateManager/offlineProcessComplete`، ويمسح أيضًا `C0A2.A07`) | `BvR` -> `CXW(false)` فقط إذا كانت خاصية AB **9654** | `jvidispatchIO(10, ctx)` (flush للمخازن النشطة) | found |
| flush صريح | `Bba()` -> `CXW(true)`؛ و`CXZ()` يفعل flush وينتظر حتى 2500 ms | `jvidispatchIO(10, ctx)` | found |
| نهاية المكالمة | `C24895Anr.A02` يرسل `WamCall`، ثم `Bba()` إذا كانت المكالمة موسومة أو خاصية AB **16047** | flush | found |
| إعادة التسجيل / إزالة الحساب | `C25100xS` ("RegistrationManager/reregister/rm-me") -> `CUj()` | `jvidispatchIO(12, ctx)` ("wamruntime/resetruntime") | found |

وسيط الحالة 0/1 هو حالة اتصال XMPP المنعكسة في وسائط النقل الأصلية (سلسلة السجل "wameta/transport/status - %d"). معنى 0 = متصل مقروء من تعيين callback وليس من الشيفرة الأصلية (inferred). حالات `C0A2.A04`: 1 جارٍ الاتصال، 2 متصل، 3 منقطع، 4 متوقف؛ و`A07` تكون true من الاتصال حتى انتهاء معالجة الرسائل غير المتصلة، لذا `A0N()` تعني "متصل ولا يزال يستنزف الرسائل غير المتصلة".

### 3.4 واجهة JNI

| الاتجاه | التوقيع | الغرض | المستوى |
|-----------|-----------|---------|------|
| Java إلى الأصلي | `jvidispatchIOOOO(0, path, networkSession, ctx, config)` | تهيئة runtime (السجل "WAJContextInitWAMRuntime")، انظر 4 | found |
| Java إلى الأصلي | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)` | تسجيل حدث | found |
| Java إلى الأصلي | `jvidispatchIIIOO(0, channel, attrId, String, ctx)` / `jvidispatchIIIO(4, channel, attrId, ctx)` / `jvidispatchIIIIO(1, channel, attrId, bool, ctx)` / `jvidispatchIIIDO` / متغيرات int وlong | ضبط سمة مشتركة (null، سلسلة، منطقي، double، عدد صحيح) | found |
| Java إلى الأصلي | `jvidispatchIIO(4, state, ctx)` / `jvidispatchIO(10, ctx)` / `jvidispatchIO(12, ctx)` | حالة الاتصال / flush / إعادة ضبط | found |
| Java إلى الأصلي | `jvidispatchIOOOO(4, ctx, signedCredential, acsPublicKey, configId)` | نتيجة credential IQ (الكل null عند الفشل) | found |
| الأصلي إلى Java | `jnidispatchIO(6, byte[])` | إرسال مخزن مؤقت عادي واحد كـ `w:stats` IQ، يعيد 1 عند `result` | found |
| الأصلي إلى Java | `jnidispatchIO(7, byte[32])` | إرسال طلب credential الخاص بـ `privatestats` | found |

---

## 4. تهيئة وقت التشغيل

`RunnableC29323CoA` الحالة 33 تبني خريطة config وتستدعي التهيئة الأصلية مرة واحدة. المسار هو `<filesDir>/wam`.

| مفتاح config | خاصية AB | النوع | المعنى المرجَّح | المستوى |
|------------|---------|------|---------------|------|
| `platform_code` | – | int `2` | معرّف منصة Android | found |
| `beacon_probability` | **6977** | int | احتمال حالة "beaconing" الأصلية لكل حدث (`WAMBeacon`) | found؛ المعنى inferred |
| `storage_size` | **9822** (x 1024) | long | سقف تخزين المخزن المؤقت (من KiB إلى بايت)؛ يسجّل الأصلي "no-enough-storage" ويُسقط الأحداث | found؛ الوحدة inferred |
| `buffer_timeout` | **12399** | int | مؤقت تدوير المخزن المؤقت | found؛ المعنى inferred |
| `throttling_percentage` / `throttling_exempt` | **9457** / **9456** | int / string | تقييد الرفع وقائمة الاستثناء | found؛ المعنى inferred، الصيغة unknown |
| `enable_extra_logging` | **14310** | bool | تسجيل أصلي مفصّل | found |
| `enable_ps_upload_v2` | **15205** | bool (فقط عند التفعيل) | "beginning upload v2 logic" الأصلية على النقل الخاص | found |
| `enable_aggregation` / `aggregation_config` | **11981** / **11982** | bool (فقط عند التفعيل) / string | يفعّل `WAGAggregation` مع قواعده | found؛ الصيغة unknown |

يتلقى الاستدعاء نفسه كائن `networkSession` أنشأته `C25810yb`؛ استخدام أغلفة HTTP الأصلية له inferred. القيم الافتراضية لخصائص AB يسلّمها الخادم ولم تُحلّ.

---

## 5. السمات المشتركة (العامة)

تُكتب السمات العامة بواسطة `RunnableC29340CoR` الحالة 0 عبر `C06590Fi.CYl(value, attrId, channel)` مع القنوات 0..3. دالة مساعدة تضبط القنوات الأربع دفعة واحدة؛ وغيرها يضبط 0 و1 فقط. لذلك تحصل القنوات الخاصة (2، 3) على مجموعة مخفّضة.

| معرّف السمة | مصدر القيمة | القنوات | المستوى |
|---------|--------------|----------|------|
| 3 / 5 | MNC / MCC محلَّلان من `TelephonyManager.getNetworkOperator()` (5 أو 6 أرقام، GSM فقط) | 0 1 2 3 | found |
| 11 / 1659 / 1657 | رمز المنصة `2` / رمز المنصة `2` / ثابت `3` | 0 1 2 3 | found |
| 13 / 15 / 17 / 21 | `Build.MODEL-Build.MANUFACTURER` / `Build.VERSION.RELEASE` (يُتخطى مع خاصية AB **12637**) / إصدار التطبيق `2.26.41.6` / `true` (علَم beta inferred؛ مضمَّن في الشيفرة في APK الـ beta هذا) | 0 1 2 3 | found |
| 287 / 289 / 495 | `Build.MANUFACTURER` / `Build.MODEL` / سلسلة جهاز (لم تُحلّ) | 0 1 | found |
| 655 / 689 / 2617 | مقاييس ذاكرة الجهاز وفئته (`C38271gj`, `IJJ.A02/1048576`, `C38261gi`) | 0 1 2 3 | found؛ الأسماء inferred |
| 4473 | مفتاح AB config (`ab_key` من آخر استجابة `<props>`، يُعاد ضبطه عند كل تحديث AB) | 0 1 | found |
| 5029 | معرّفات تعرّض لتجارب AB مفصولة بفواصل (`BxP`)؛ ومع خاصية AB **31830** خريطة مدمجة من `ab-props` و`ab-private-abprop` | 0 1؛ وموجودة أيضًا في مخزن مؤقت خاص (القناة 2) | found |
| 6251 / 10255 | فحص توقيع التطبيق / علَم مثبّت Play | 6251: 0 1 2 3؛ 10255: 0 1 | found، انظر [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |
| 12017, 12027, 14507, 15265, 15611, 23, 707, 7335, 13293, 23043 | قيم متنوعة لحالة التطبيق (12027 منطقي من كائن حالة الحساب، 707 `primary_platform_name` فقط حين يكون 12027 true، 13293 = خاصية AB **3664**، 15611 ثابت WASafe (انظر [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md))، 7335 `true` بعد تشغيل hooks التهيئة) | غالبًا 0 1؛ 13293 الأربع كلها | found؛ المعاني inferred أو unknown |
| 47 | وقت الإيداع commit، int32 ثوانٍ، يُضاف أصليًا | الكل | found (ملف مخزن مؤقت) |
| 6005 | قيمة معرّف private-stats (سلسلة UUID أو `none`)، تُضاف أصليًا | المخازن الخاصة | found (ملف مخزن مؤقت) |
| 2795, 105 / 6833 | مضافة أصليًا، للمخازن العادية فقط / قيمة من `C21730rv`، للقناتين 2 و3 فقط | 0 / 2 3 | found؛ المعاني unknown |

لا يوجد رقم هاتف أو JID أو معرّف حساب بين السمات المشتركة التي تكتبها Java. يرتبط النقل العادي بالحساب عبر الاتصال الموثَّق الذي يُرسَل عليه (inferred، انظر 9).

---

## 6. التخزين الأصلي

سلاسل `libwhatsapp.so` (`WAMBufferStoreImpl`, `WAMPSIDProfileStoreImpl`, `WAMPrivateCredentialStoreImpl`, `WAMMetadataStoreImpl`) وملفات دليل بيانات مثبّت لـ 2.26.41.6 متطابقة.

### 6.1 الدليل `files/wam/`

| الملف | المحتوى | المستوى |
|------|---------|------|
| `wamt-a-<channel>-0-<seq>` | مخزن مؤقت نشط، 65,559 بايت (محجوز مسبقًا، مبطَّن بالأصفار)؛ السلسلة الأصلية `wamt-o` توحي بمخازن مُدوَّرة (inferred) | found |
| `wam-metadata` | حاوية `MTD` v4 مع عدّادات لكل قناة؛ التسلسل التالي المخزَّن للقناة 0 يساوي أعلى تسلسل في الملفات زائد واحد | found؛ البنية inferred |
| `WAMMetadataPSIDProfile-<n>-<keyHash>` | profile واحد لـ private-stats لكل hash مفتاح (شوهدت 8 ملفات) | found |
| `WAMMetadataPrivateCredential-<n>` | credential مخزَّن للنقل الخاص (`signed_credential`، مفتاح، معرّف config؛ v2، ~120 بايت) | found؛ البنية inferred |

الرقم الثالث في اسم الملف هو معرّف تدفق (السجل "wameta/buffer/rotated stream id: %d, channel: %d, buffer sequenceNumber: %d"؛ دائمًا `0` في العيّنة)، والأخير هو تسلسل المخزن المؤقت.

### 6.2 بنية ملف المخزن المؤقت

```
off  0   "WMT" 03                      container magic, version 3
off  4   u32 LE  used length           = (end of used data) - 31   (checked in 2 files)
off  8   u32 LE  ?                     counter, meaning unknown
off 12   u32 LE  event count           equals the number of event markers decoded
off 16   u32 LE  ?                     close to the used length (+4, +6, +31 in samples)
off 20   u32     ?                     check value (inferred), algorithm unknown
off 24   "WAM" 05                      WAM header: magic + protocol version 5
off 28   u8  0                         flag byte (0 in all samples)
off 29   u16 LE  buffer sequence       equals the number in the file name
off 31   u8  channel                   0 regular, 2 private in samples
off 32   TLV entries                   globals first, then events
```

found لكل بايت مذكور بقيمة؛ الحقول المعلَّمة بـ "?" غير معروفة.

### 6.3 Profile الخاص بـ private-stats

`WAMMetadataPSIDProfile-<n>-<keyHash>` (من 78 إلى 90 بايت)، البنية مقروءة من الملفات الثمانية كلها:

```
u8 version(2) │ i32 LE keyHash │ i32 LE rotationDays │ u8 ? │ float64 LE (timestamp, inferred) │ u32 ? (1) │
u32 keyLen │ u32 uuidLen(36) │ key string (e.g. "id_ttl_daily") │ UUID string
```

أيام التدوير المقروءة من الملفات: -1 (`default_ps_id`, `id_pre_metrics`)، 1، 7، 30، 30، 30، 90 (انظر 2.3). تسمّي السلاسل الأصلية العمليات `WAMPSIDProfileRotatePSID`، و"psid delegated rotation was not persisted" وفحوص التلف (`invalid rotationInDays`). الـ UUID هو ما يدخل في القيمة العامة 6005 للمخازن الخاصة. هل يُدفع التدوير بالوقت المحلي أم بالخادم: unknown.

---

## 7. الصيغة السلكية لـ WAM

مؤكدة على مخازن حقيقية: محلِّل مكتوب وفق مخطط الوسوم أدناه حلّل القيم العامة والأحداث في مخزنين (عادي وخاص) دون بقايا.

### 7.1 ترميز الإدخال

كل إدخال هو `[tag][field id][payload]`.

| الجزء | الترميز | المستوى |
|------|----------|------|
| النصف الأدنى من الوسم | الدور: `0` عام، `1` علامة حدث، `2` حقل؛ أو `0x04` الأخير في المجموعة؛ أو `0x08` معرّف الحقل `u16 LE` بدل `u8` | found |
| النصف الأعلى من الوسم | نوع القيمة: `0x00` null، `0x10` عدد صحيح 0، `0x20` عدد صحيح 1، `0x30` int8، `0x40` int16 LE، `0x50` int32 LE، `0x60` int64 LE، `0x70` float64 LE، `0x80` سلسلة (طول u8)، `0x90` سلسلة (طول u16 LE)، `0xA0` سلسلة (طول u32 LE) | found لـ int 0/1 وint8 وint16 وint32 وسلسلة u8 وu16 (كلها فُكَّت من المخازن)؛ والبقية inferred من المخطط ومن مرمِّز Baileys |
| الأعداد الصحيحة، السلاسل، ترتيب البايت | أصغر شكل للعدد الصحيح (0 و1 يقيمان في الوسم)؛ سلاسل UTF-8؛ little-endian في كل مكان (ترميز stanza هو big-endian) | found |

### 7.2 علامة الحدث

علامة الحدث هي الدور `1` مع معرّف الحدث كمعرّف حقل. قيمتها هي وزن أخذ العينات، مخزّنًا موجبًا في المخازن: الأحداث ذات وزن المخطط 20 (`wam_secure_file_usage`, `wam_whatsapp_quick_promotion_client_eligibility_waterfall`) تحمل 20، والأحداث ذات الوزن 1 تحمل 1 (found). تليها الحقول بالدور `2` (علَم آخر حقل `0x04` لم يُفحص). تُكتب كتلة عامة (الدور `0`) حين تتغير السمات، فتتكرر القيم العامة بين الأحداث (وقت الإيداع 47 يُعاد كتابته مرات عديدة، found).

حمولة IQ بين 4 و126,976 بايت (9). كونها تساوي المخزن المؤقت من الإزاحة 24 (رأس `WAM` فصاعدًا) لا تبيّنه الشيفرة؛ هو inferred من البنية ومن إرسال Baileys للرأس نفسه (15).

---

## 8. أخذ العينات وأوزان كل حدث

### 8.1 الحل (`C0Fg.A00`، مبسّط)

```
override = prefs(code == 1094 ? "app_launch_event_sampling_weight" : "field-stats-events-sampling"[code], 0)
weight   = override != 0 ? override : schema.A00         // sampler becomes (|w|,|w|,|w|,|w|) for an override
keep     = random.nextInt(sampler.A00) == 0              // 1-in-N; null return = "(dropped)"
```

| البند | القيمة | المستوى |
|------|-------|------|
| التجاوزات المحلية | ملف prefs `field-stats-events-sampling` (المفتاح = رمز الحدث) و`app_launch_event_sampling_weight` (الحدث 1094)؛ الوزن 1 يُحتفظ به دائمًا | found |
| الحارس الأصلي | "wameta/logger event weight exceeds max, dropped"؛ الحد أصلي | found؛ القيمة unknown |
| أخذ العينات لكل مكالمة | `WamCall`: الحقل `logSampleRatio` (المعرّف 1120) للحدث يحدد الوزن، `new C036300x(i, i)` | found |

### 8.2 التسليم من الخادم (استجابة AB props)

`C28894Cgv.CFS` يعالج نتيجة AB-props (العقدة `<props>`). كل ابن `<prop>` إما خاصية config أو إدخال أخذ عينات لحدث:

```
<props ab_key hash refresh refresh_id delta_update>
  <prop config_code config_value config_expo_key/>    -> ab-props
  <prop event_code="854" sampling_weight="5"/>        -> field-stats-events-sampling
</props>
```

حين لا يكون `hash` فارغًا تُمسح prefs أخذ العينات وتُعاد كتابتها من كل أزواج `event_code`/`sampling_weight`؛ والإدخال 1094 يكتب أيضًا `app_launch_event_sampling_weight` (ويزيله عند الغياب). إذن يتحكم الخادم بأوزان كل حدث، وتُرسل الأوزان مع كل حدث ليتمكن الخادم من تحجيم الأعداد (inferred من انتقال الحقل مع الحدث؛ استخدام الخادم unknown).

إذن يشكّل الخادم WAM عبر AB props وأوزان أخذ العينات وcredential الخاص؛ لا يُدفع شيء على IQ الرفع نفسه (يحصل IQ على `result` فقط).

---

## 9. الرفع العادي (`w:stats`)

يستدعي الأصلي `JniBridge.jnidispatchIO(6, bytes)`. تبني Java وترسل:

```
<iq xmlns="w:stats" to="s.whatsapp.net" type="set" id="..">
  <add t="<unix seconds>">[binary: WAM buffer]</add>
</iq>
```

| البند | القيمة | المستوى |
|------|-------|------|
| النقل | تدفق الدردشة العادي الموثَّق (`C10140Tq`)، كأي IQ | found |
| `t`، الحدود، المهلة | `t` = ثواني unix الحالية (تُضاف فقط ضمن 1,577,865,600..4,102,473,600)؛ تُفحص الحمولة مقابل 4..126,976 بايت؛ مهلة IQ هي 32,000 ms (انتظار متزامن) | found |
| النجاح | سمة الاستجابة `type == "result"` -> المحاسبة `C0VI.A02(len, 32)`، يعيد 1 | found |
| الفشل | نوع آخر أو مقاطعة -> يسجّل "FieldStatsXmppImpl/error sending fieldstats IQ"، يعيد 0 (الأصلي يقرر إعادة المحاولة؛ توجد "_WAMTransportManagerUploadFailedPermanently") | found |
| التأجيل أثناء مكالمة | يعيد 0 مع السجل "WamJniBridge/upload postponed" إذا كانت مكالمة نشطة، ما لم تكن خاصية AB **15507** مفعّلة، أو كانت المكالمة جماعية وخاصية AB **468** مفعّلة | found (تدفق المفكِّك، والقيمة الافتراضية لعلَم المجموعة مفترضة false) |
| التأجيل أثناء معالجة الرسائل غير المتصلة | يعيد 0 إذا كانت `C0A2.A0N()` (متصل والرسائل غير المتصلة لم تُستنزف بعد) وخاصية AB **9654** مفعّلة؛ ومع 9654 معطّلة يُرسل IQ | found |
| ربط الحساب / الضغط | لا معرّف حساب في الحمولة، الخادم يرى الجلسة الموثَّقة؛ لا ضغط على مسار Java | inferred / found |

الخاصية 9654 نفسها تفعّل flush عند `offlineProcessComplete` (3.3). معًا: مع 9654 مفعّلة، تنتظر الرفوعات حتى تُستنزف طابور الرسائل غير المتصلة ويعمل flush في تلك اللحظة (inferred من موضعَي الاستدعاء؛ توقيت إعادة المحاولة بعد محاولة مؤجلة أصلي وunknown).

---

## 10. الرفع الخاص

القناتان الخاصتان (2 و3) لا تُرسلان كـ `w:stats`. يرفع `WAMTransportPrivate` الأصلي عبر نقل HTTP منفصل (`WCIHTTPImpl`) مع credential مجهول. كل ما يلي مصدره سلاسل السجل الأصلية ومعالج credential في Java.

### 10.1 طلب credential

```
<iq xmlns="privatestats" to="s.whatsapp.net" type="get" id="..">
  <sign_credential version="1">
    <blinded_credential>[32 bytes]</blinded_credential>
  </sign_credential>
</iq>
```

| الجزء | التفصيل | المستوى |
|------|--------|------|
| المرسِل | `JniBridge.jnidispatchIO(7, byte[32])`؛ رمز الخطأ في متتبّع IQ هو 239، المهلة 32,000 ms | found |
| الاستجابة (`KRL.CFS`) | `<sign_credential t=..><signed_credential/><acs_public_key/><config_id/></sign_credential>`؛ تُسلَّم مصفوفات البايت الثلاث إلى الأصلي بـ `jvidispatchIOOOO(4, ctx, ...)`؛ عند الخطأ أو انعدام الاستجابة يتلقى الأصلي قيم null | found |
| القياس عن بُعد | الحدث 2242 `wam_sign_credential` (القناة العادية) مع الحالة 3 = فشل، 1 = نجاح، والزمن المنقضي | found |
| التحقق والتخزين | السلاسل الأصلية "Invalid signature received from server"، "fails validation" (العميل يتحقق من التوقيع)؛ يُخزَّن في `WAMMetadataPrivateCredential-<n>`، ويُجدَّد عند 401 ("send failed, renew credentials") | found |
| المخطط | طلب معمّى، استجابة موقَّعة، مفتاح ACS العام: credential مجهول، فلا يربط credential الرفوع الخاصة بالحساب | inferred |

مُرسِل عام منفصل `C1N8` يستخدم فضاء الأسماء نفسه مع `<sign_credential version="2">` و`project_name` لمشاريع ACS الأخرى (prefs `acs_token_*`)؛ وليس مسار WAM.

### 10.2 الرفع

| البند | التفصيل | المستوى |
|------|--------|------|
| نقاط النهاية | سجلات أصلية "url/received"، "fetch_endpoints/custom_endpoints - got endpoints: %d"، "invalid_ps_endpoint, ignoring"؛ لا literal لعنوان URL في Java ولا في `libwhatsapp.so` | found؛ مصدر القائمة unknown |
| معالجة الفشل والمؤقت | "try next endpoint"، "have next credentials"، "401, no more endpoints"؛ مؤقت النقل ("timer/started - interval: %.1f seconds") يبدأ عند "connection_ready" ويتوقف عند "connection_unavailable" | found؛ الفترة unknown |
| الزمن الحقيقي الخاص | مخازن لكل حدث: "create_buffer/realtime/buffer-created ... event id"، "sendsingleeventimpl/realtime" | found |
| الترويسات، تأطير الجسم، الضغط | غير مرئية | unknown |

Falco logger `C40099Hdc` بالوضع 9 يُسقط الأحداث ذات القناة 2 أو 3 أو psId من مساره الخاص ويحسبها كـ `wa:dropped_private_stats` (found)، فلا تُكرَّر الأحداث الخاصة في ذلك logger (inferred).

---

## 11. `wam_daily` والأحداث الدورية

معرّف الحدث 1158، اسم Falco هو `wam_daily`، القناة 0، الوزن 1، 218 حقلًا رقميًا / 205 مسمّى. لحقول root والمحاكي وROM المخصص والعميل المعدَّل، انظر [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)؛ هنا يُسجَّل المسار الداخلي فقط.

### 11.1 الجدولة (found)

| القطعة | التفصيل |
|-------|--------|
| المنبّه | `BEL.A01`: منتصف الليل المحلي التالي + jitter عشوائي `nextInt(AB prop 5529)` (الوحدة محوَّلة بواسطة `C20D.A02`)، الإجراء `com.whatsapp.action.DAILY_CRON` |
| التعويض | الإجراء `com.whatsapp.action.DAILY_CATCHUP_CRON`، يُعاد كل 15 دقيقة ما دام "last_daily_cron" ليس من اليوم |
| الحارس | يتخطى مع "too frequent" إذا كان cron قد عمل اليوم (pref `last_daily_cron`)؛ يتخطى كل مهام cron أثناء جريان نقل دردشة؛ المهام التي تحتاج مخزن الرسائل تُتخطى حين لا يكون جاهزًا |
| المنفّذ | يمرّ على مجموعة DI من مهام `InterfaceC29983D2n` cron (`Bo5`)؛ `C28643Ccj` (الوسم `WamDailyEventDailyCron`) يعمل فقط حين `anonymousClass091.BS3()` (حالة الحساب، المعنى لم يُحلّ) |

### 11.2 التعبئة

`C28643Ccj.Bo5` تنشئ `new C0Fp()`، وتستدعي `C4k(C0Fp)` على كل مُعبّئ في مجموعة DI (28 ملفًا تعرّف مُعبّئ `C4k(C0Fp)`)، ثم `CNW(c0Fp)` بوزن المخطط الافتراضي. مُعبّئ أعلام الجهاز هو smali فقط في هذا الإصدار (`smali_classes7/X/Cdt.smali`؛ المفكِّك يفشل عليه) ويقرأ ويكتب pref `last_daily_event` (ms بالساعة الجدارية)، ويسند `time_delta_since_last_event`. الفرع المفكوك يغيّر الدلتا من 0 إلى 1 فقط، لذلك لا يُقدَّم ادعاء عن وحدة أو وتيرة لهذا الحقل. `last_daily_event` ليس المجدوِل (المنبّه في 11.1 هو المجدوِل).

يُصدر cron نفسه حدثًا خاصًا بـ Falco فقط هو `wam_daily_permission` (مع أخذ عينات): حالة إذن جهات الاتصال، وإذن المعرض، ومنح الكاميرا / تسجيل الصوت / الموقع التقريبي والدقيق، وإعداد إشعارات نظام التشغيل، وأحجام دفتر العناوين، وأعداد الخيوط الاختيارية (خاصية AB **25576**) و`profile_photo_is_set` (خاصية AB **34207**)، و`os_version` (found).

### 11.3 أحداث دورية أخرى

أحداث أخرى عند بدء التطبيق ودورية: 1094 `wam_app_launch` (الوزن قابل للتجاوز بـ `app_launch_event_sampling_weight`)، 3300 `wam_ps_app_launch` (خاص، `id_pre_metrics`)، 3178 `wam_clock_skew_difference_t` (خاص، `id_ttl_90_days`)، عائلة `*_daily` (5798 `wam_reaction_daily`, 3680 `wam_polls_daily_stats`؛ المشغّلات inferred).

---

## 12. معالجة الخصوصية

| الجانب | النتيجة | المستوى |
|--------|---------|------|
| معرّفات ثابتة في الدُفعات | لا JID ولا رقم هاتف في السمات المشتركة التي تكتبها Java؛ `dedup_key` و`trace_id_int` عشوائيان لكل حدث؛ القناة العادية موثَّقة بالتدفق الذي تنتقل عليه | found / inferred |
| معرّفات Private-stats | UUID لكل مفتاح في `WAMMetadataPSIDProfile-*`، القيمة العامة 6005 في المخازن الخاصة؛ التدوير 1 أو 7 أو 30 أو 90 يومًا أو أبدًا | found |
| credential مجهول | رمز معمّى يوقّعه الخادم للرفوعات الخاصة (10.1) | found؛ عدم قابلية الربط inferred |
| معرّفات مجزّأة وصريحة | توجد حقول معرّفات مجزّأة (`hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids`, `message_key_hash`, `invited_user_hash`؛ دالة hash لم تُتتبَّع)؛ وتوجد أيضًا سلاسل بنوع JID (`reported_jid`, `e2e_sender_jid`؛ التجزئة قبل التسجيل لم تُتتبَّع) | found (الأسماء)، unknown |
| إعادة الضبط | إزالة الحساب وإعادة التسجيل تستدعيان إعادة الضبط الأصلية (`jvidispatchIO(12)`)؛ إعادة ضبط profiles الخاصة بـ PSID بها غير مبيَّنة | found / unknown |
| إلغاء اشتراك المستخدم | لم يوجد إعداد أو سلسلة أو علَم يعطّل WAM؛ السلسلة الوحيدة الشبيهة بالموافقة في الموارد تخص تشخيصات الدعم. قد يوجد إعداد في مسارات شيفرة لم تُبحث | unknown |
| تحكم الخادم | أوزان كل حدث (8.2)، AB props (13)، config الخاص بـ `throttling_*` و`beacon_probability` (4)؛ الخوارزميات أصلية | found؛ unknown |

---

## 13. Feature flags (خصائص AB كما قُرئت في مسارات الشيفرة أعلاه)

| الخاصية | النوع | ما تتحكم به |
|------|------|----------|
| **9654** | bool | flush عند اكتمال معالجة الرسائل غير المتصلة (3.3)؛ تأجيل الرفع أثناء استنزاف الرسائل غير المتصلة (9) |
| **15507** / **468** / **16047** | bool | عدم تأجيل الرفع أثناء مكالمة / أثناء مكالمة جماعية / flush بعد أحداث المكالمة |
| **6977**, **9822**, **12399**, **9457**, **9456**, **14310**, **15205**, **11981**, **11982** | مختلطة | مفاتيح config لتهيئة runtime (القسم 4) |
| **31314** | string | `"code:N;..."` معدل مشغّل رفع السجلات لكل رمز حدث |
| **5529** | int | jitter المهمة اليومية cron |
| **12637** | bool | يتخطى إصدار نظام التشغيل والشركة المصنّعة والسمات المرافقة (15، 287، 21، 12027، 707) |
| **31830** / **25576** / **34207** | bool | قائمة AB الخاصة المدمجة في السمة 5029 / حقول `wam_daily_permission` الاختيارية |
| **34494..34507, 35169, 35170** | – | مصفوفة في `AbstractC38513Goh.A01` (16 معرّفًا، بعدد Falco migration batches 1..16 نفسه)؛ الاستخدام inferred |

كل القيم يسندها الخادم؛ لم تُحلّ القيم الافتراضية.

---

## 14. عائلات الأحداث البارزة

الأسماء هي أسماء Falco؛ المعرّفات والقنوات من فئات الأحداث. قوائم الحقول هي الحقول المسمّاة في `getFieldsMapForFalco()`.

### 14.1 الرسائل

| الحدث | المعرّف | القناة / الوزن | حقول بارزة |
|-------|----|-------------|----------------|
| `wam_message_send` | 854 | 0 / 5 | 89 حقلًا: `message_send_result`, `message_send_t`, `message_type_str`, `e2e_ciphertext_type`, `e2e_ciphertext_version`, `is_pq`, `is_lid`, `retry_count`, `resend_count`, `message_is_forward`, `message_is_fanout`, `message_distribution_type`, `participant_count`, `device_count`, `message_key_hash`, `is_view_once`، والزوال، والتعديل/الإلغاء، وحقول البوت والذكاء الاصطناعي الخاص |
| `wam_message_receive` | 450 | 0 / 20 | 58 حقلًا: `message_receive_t0..t2`, `message_queue_time`, `message_is_offline`, `offline_count`, `stanza_process_count`, `padding_bytes_size`, `message_addressing_mode`, `server_addressing_mode`, `session_scope`، وحقول الملصقات وبطاقات الاتصال |
| `wam_e2e_message_send` / `_recv` | 476 / 478 | 0 / 20 | `e2e_successful`, `e2e_failure_reason`, `e2e_destination`, `group_encryption_state`, `enc_retry_count`, `pq_receive_gate_state` |
| `wam_e2e_message_decrypt_fail_sender` | 3524 | خاص (ps `none`) | `e2e_sender_jid`, `e2e_failure_reason`, `retry_count` |

### 14.2 المكالمات

`WamCall` (المعرّف 462، القناة 0) يُنشأ من الإحصاءات الأصلية (`ConvertFieldStats`، "can not construct com/whatsapp/fieldstats/events/WamCall") ولديه نحو 1,700 حقل مسمّى (1,716 موضع `put` في خريطة Falco). `WamJoinableCall` هو المعرّف 2572. أخذ العينات هو `logSampleRatio` (الحقل 1120)، ويُفعل flush للحدث عند نهاية المكالمة (3.3). أحداث مكالمات أخرى: 2582 `wam_call_stanza_receive` (الوزن 1000)، 3452 `wam_call_critical_events`، 4568 `wam_call_user_journey`. تشوير المكالمات نفسه في [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md).

### 14.3 تسجيل الدخول والتسجيل

| الحدث | المعرّف | الحقول |
|-------|----|--------|
| `wam_login` | 460 | `login_result`, `login_t`, `connection_origin`, `connection_t`, `login_dns_resolver`, `login_ip_source`, `login_port`, `login_resolved_pop`, `login_socket_provider`, `noise_protocol_version`, `retry_count`, `server_error_code`, `passive`, `long_connect`, `network_is_vpn`, `android_keystore_state`, `pending_acks_count`, `unprocessed_message_count` (30 خانة)؛ انظر [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) |
| `wam_reg_init` / `wam_registration_complete` | 2046 / 1342 | توقيتات البدء (`contacts_sync_t`, `groups_init_t`, `total_t`)؛ 30 حقلًا منها `registration_t`, `addressbook_size`, `contacts_permission_authorization_status`, `device_identifier`, `google_account_list_hashed_reg`, `invited_user_hash`, `is_new_jid`، وحقول صورة الملف الشخصي والأذونات |
| `wam_account_encryption_attestation` | 8164 | الاسم يوحي بنتيجة attestation (inferred)؛ انظر [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |

### 14.4 الرسائل المزعجة والإبلاغ والحظر

التدفقات في [WA_REPORTING.md](WA_REPORTING.md) و[WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) (`wam_wfacp_ban_action`، المعرّف 5028)؛ جانب WAM:

| الحدث | المعرّف | القناة | الحقول |
|-------|----|---------|--------|
| `wam_spam_report_perf` | 6310 | 0 | `report_spam_flow`, `report_status`, `report_attempt_count`, `report_duration_ms`, `report_error_code` |
| `wam_report_conversation_context` | 4608 | 0 | `reported_jid`, `spam_flow`, `estimated_num_messages_sent/received`, `is_chat_maybe_suspicious`, `is_in_addressbook`, `first_entry_point`, `num_call_msgs_to_report` |
| `wam_blocking_funnel` / `wam_reporting_funnel` | 4920 / 4924 | 0 | `block_flow_action`, `hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids` |
| `wam_reporting_token_validation_failure` | 5466 | 0 | `reporting_token_validation_failure_reason`, `reporting_token_version`, `is_part_of_group_history` |
| `wam_reporting_token_validation_failure_sender`, `wam_reporting_token_additional_client_validation` | 6094, 6702 | 2 (`default_ps_id`) | متغيرات جهة المرسل |
| `wam_message_template_blocks` | 3002 | 2 (`default_ps_id`) | أسباب حظر قوالب الأعمال |

### 14.5 التجارب

`wam_wefr_client_exposure` (المعرّف 5504، realtime) يسجّل التعرّض مع `exposure_key`, `device_exp_id`, `user_lid`, `guest_id`, `is_canonical_ent_present`, `sent_with_daily`. يحمل حقل LID للمستخدم (found؛ استخدام الخادم unknown). `wam_ui_action_real_time` (2098، الوزن 10) يحمل فقط `chatd_internet_connectivity` و`dedup_key`.

---

## 15. Baileys (`baron-baileys-v2`، مقارَن بشيفرته المصدرية)

يرسل Baileys مخازن WAM المؤقتة بنفس IQ الذي يستخدمه عميل Android.

| الجانب | Baileys (`src/Socket/socket.js`, `src/WAM/encode.js`) | Android 2.26.41.6 | المستوى |
|--------|--------------------------------------------------------|-------------------|------|
| stanza الرفع | `<iq to=s.whatsapp.net xmlns="w:stats" type="set"><add t=…>buffer</add></iq>` | مطابق | found في الاثنين |
| الرأس | `"WAM"`، بايت الإصدار 5، البايت 4 = `1`، تسلسل `u16 BE` عند 5، القناة `0` عند 7 | `"WAM"`، الإصدار 5، البايت 4 = `0`، تسلسل `u16 LE` عند 29، القناة عند 31 (في الملف مع حاوية `WMT` أمامه) | found في الاثنين |
| ترميز القيم | `0/1` في الوسم، int8، int16/int32 LE، float64 LE، سلاسل بطول u8/u16 LE/u32 LE، علَم المعرّف الواسع `0x08` | البتات نفسها | found في الاثنين |
| وزن الحدث | يُكتب كـ `-weight` | يُخزَّن موجبًا في ملفات المخزن | found في الاثنين |
| القنوات، flush | العادية فقط؛ flush كل 30 ث وبعد تسجيل الدخول، الإخفاقات تُسجَّل فقط | 0..3؛ تدوير ونقل أصليان | found |

الفرق في ترتيب بايتات التسلسل وإشارة الوزن ليس خطأً أثبته هذا التقرير: ملفات Android على القرص لا يلزم أن تساوي البايتات التي يرفعها النقل الأصلي، ولم يُرصد محلِّل الخادم. لا شيء في مسارات شيفرة الدردشة المقروءة هنا ينتظر حالة WAM؛ هل يتفاعل الخادم مع رفع مفقود أو غير معتاد: unknown (19).

---

## 16. حالات الخطأ

| العَرَض | السبب | الحل / ملاحظة |
|---------|-------|------------|
| حدث مفقود في المخازن | فشل سحب الوزن (1 من N)، قائمة السماح للقناة 3، سقف التخزين، "weight exceeds max" الأصلية، "have to drop event" | افحص الوزن 2.4 وAB props 8.2، 4 |
| الحدث اليومي ينتج أحداث تحقق | تفشل قاعدة `ai_widget_installed` لكل `wam_daily` (3.2) | متوقع في هذا الإصدار |
| "WamJniBridge/upload postponed" | مكالمة نشطة دون 15507 / 468، أو لا يزال طابور الرسائل غير المتصلة يُستنزف مع 9654 | عابر؛ الأصلي يعيد المحاولة (inferred) |
| "FieldStatsXmppImpl/error sending fieldstats IQ" | خطأ IQ، مهلة (32 ث) أو مقاطعة | إعادة محاولة أصلية / مسار فشل دائم |
| "Cannot log before WAM runtime is initialized" / "after ... terminated" | ترتيب دورة الحياة الأصلية | Java تنتظر على `A0K`؛ الإنهاء حالة أصلية |
| يفشل الرفع الخاص بـ 401 | رُفض credential | يُجدَّد عبر IQ `privatestats` (10.1) |

---

## 17. فروق أساسية

| الزوج | الفرق |
|------|------------|
| WAM مقابل Falco | أحداث WAM تمر عبر runtime الأصلي والمخازن المؤقتة؛ Falco logger في Java (`C40099Hdc`, `FFLogger`) مسار موازٍ يعيد استخدام فئات الأحداث نفسها باسم Falco. Falco migration batch 1..16 لكل حدث (`internalFalcoMigrationBatchNumber`) |
| وزن الحدث مقابل feature flag | الوزن = أخذ عينات 1 من N ومضاعِف يُرسل مع الحدث؛ العلامات تتحكم فقط في سلوك النقل |
| الرفع العادي مقابل الخاص | العادي = `w:stats` IQ على تدفق الدردشة؛ الخاص = نقل HTTP منفصل مع credential معمّى |
| `psId` مقابل القيمة العامة 6005 | `psId` هو hash مفتاح ثابت في فئة الحدث؛ 6005 هو UUID دوّار يُكتب أصليًا في المخازن الخاصة |
| معرّف الحقل مقابل المعرّف العام | الفضاءان الرقميان يتداخلان (47 عام؛ والحقل 47 لحدث ما مختلف)؛ دور الوسم يزيل الالتباس |
| `wam-event/<name>` مقابل رفع WAM | الأول يرفع سجلات الجهاز عبر مُبلِّغ الأعطال، والثاني يرفع مخازن القياسات |
| المخزن المؤقت على القرص مقابل الحمولة السلكية | الملف فيه حاوية `WMT` وحشو؛ بنية حمولة IQ inferred |

---

## 18. التدفق الكامل

```
[App code / native call stats]  new Event(...) / ConvertFieldStats -> WamCall
    ▼
[C06650Fo.CNW / CNI]  weight = override (prefs) or schema A00, keep 1-in-N ; validate (ch 0,1) -> event 5560
    ▼
[WAM executor]  jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)
    ▼
[libwhatsapp.so WAMRuntime]  encode TLV (LE), add globals (47 commit time, 6005 psId UUID, common attrs)
    ▼
[files/wam/wamt-a-<channel>-0-<seq>]  "WMT" container + "WAM" 5 header, 64 KiB
    │  rotate (buffer_timeout) / flush (offline-complete with 9654, Bba, call end, CXZ)
    ├── channel 0, 1 ─────────────────────────────┬── channel 2, 3 ───────────────────────────────┐
    ▼                                             ▼                                              
jnidispatchIO(6, bytes)                       jnidispatchIO(7, 32 bytes blinded token)
    │  postponed in calls / offline drain          │  <iq xmlns="privatestats" type="get">
    ▼                                             ▼
<iq xmlns="w:stats" type="set"><add t=..>     [WA server] signed_credential, acs_public_key, config_id
  bytes</add></iq>  on the chat stream              │  stored, renewed on 401
    ▼                                             ▼
[WA server] type="result" -> return 1         HTTP upload, endpoint list source unknown -> [private-stats backend]

[WA server] <props> response: event_code -> sampling_weight, config_code -> AB props  ──►  prefs (8.2)
[DailyCronAction alarm: next local midnight + jitter(5529)] -> C28643Ccj populates C0Fp (wam_daily 1158) -> CNW (same path, channel 0)
```

---

## 19. المجهولات

| السؤال | سبب كونه unknown |
|----------|-------------|
| البايتات الدقيقة لحمولة الرفع مقابل ملف المخزن المؤقت | النقل الأصلي لم يُفكَّك؛ لم تُرَ إلا حدود IQ |
| الضغط وتأطير الرأس في الرفوعات الخاصة، مصدر قائمة نقاط النهاية | لا literal في Java أو السلاسل؛ مسار HTTP الأصلي لم يُتتبَّع |
| فترة التدوير الأصلية، جدول إعادة المحاولة، أقصى وزن، قواعد الإسقاط، خوارزمية beaconing | شيفرة أصلية مجرَّدة من الرموز، ولا مفكِّك للمكتبة الكبيرة استُخدم هنا |
| معنى السمات 495 و6833 و2795 و105 وعدة سمات أعلام؛ حقول `WMT` عند الإزاحات 8 و16 و20؛ حقول `MTD` | المصادر لم تُحلّ، القيم فقط |
| هل يعتمد أي سلوك للخادم على WAM مفقود أو غير معتاد | جهة الخادم |
| تجزئة حقول `*_jid`؛ وجود إلغاء اشتراك موجّه للمستخدم | لم يُتتبَّع لكل حدث / لم يوجد (الغياب ليس دليلًا) |
| توقيت إعادة المحاولة الأصلي، مشغّل تدوير PSID (وقت العميل أم تعليمات الخادم)، القيم الافتراضية لـ AB props | المنطق الأصلي لم يُتتبَّع؛ القيم الافتراضية تأتي من config الخادم |
| مشغّل مهام cron اليومية غير `wam_daily` | قُرئ فقط سجل cron ومهمة `wam_daily` cron |
