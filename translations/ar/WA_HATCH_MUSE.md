<!-- src-sha1: aacd3c372c813b12cfe335ddb7b3323c8eed3863 -->
# WhatsApp وكيل الذكاء الاصطناعي Hatch/Muse — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-15
**النطاق:** داخليات وكيل Hatch/Muse للذكاء الاصطناعي — نقل VM موثَّق عبر بوّابة Noise، إثبات ناقل أصلي + SEV-SNP، مستوى التحكم والإلحاق عبر WAFFLE، تيار noVNC لمتصفح الوكيل، مساحة العمل (المساحات، التغذية، الأهداف، الأفكار، المخرجات، الموافقات، المهام المجدولة، الموصِّلات)، مخزن بيانات الاعتماد الآمن، استرداد هوية/PIN عبر CVM (`hatch/cvm`، Vesta OPAQUE)، شريحة الاشتراك المدفوع، الحكم على إمكانية الوصول، لماذا لا يمكن لـ Baileys/velowa تنفيذه

---

## 1. ما هو Hatch/Muse

**Hatch** هو الاسم الرمزي الداخلي لمنظومة وكيل الذكاء الاصطناعي في WhatsApp؛ **Muse** هو الاسم الظاهر للمستخدم للوكيل نفسه (`str29b7` "Muse manages emails, books tables, and more."). الوكيل ليس مجرد شخصية دردشة (ذلك هو Meta AI، مُغطى في `WA_META_AI.md`): إنه يُشغِّل **جهازاً افتراضياً سحابياً سرياً عن بُعد ("CVM")** قادر على تصفح الويب، وتشغيل مهام مجدولة، والاحتفاظ بنظام ملفات خاص به، واستدعاء خدمات طرف ثالث باسم المستخدم. كل ما في هذا التقرير تحليل ساكن `found`/`inferred` لنسخة 2.26.41.6 (`WA-APK-BETA/WhatsApp_2.26.41.6/`)، مع منطقة فرعية واحدة مُصحَّحة (§6، نظام هوية `hatch/cvm`) أُعيد التحقق منها مقابل smali من 2.26.45.10. **لا شيء في هذا التقرير `tested`** — لا يدعمه أي تشغيل فعلي على جهاز أو عبر Frida؛ ثغرات التأكيد الديناميكي مُشار إليها ضمن النص.

### 1.1 الكيانات الأساسية

| الكيان | المعنى |
|--------|------|
| Hatch | الاسم الرمزي الداخلي لمنظومة الوكيل الكاملة (VM، مساحة العمل، مخزن بيانات الاعتماد، طبقة الهوية/PIN) |
| Muse | اسم/شخصية الوكيل الظاهرة للمستخدم |
| CVM | "Cloud VM" / "جهاز افتراضي سري" — بيئة الحوسبة البعيدة للوكيل (AMD SEV-SNP) |
| `HatchVmEndpoint` (`C57830PwR`) | بنية اتصال VM مُحلَّلة: المضيف، `auth_token`، تاريخ الانتهاء، رمز مُحقَّق، خريطة معطيات `notary_token` |
| بوّابة Noise | جلسة Noise موثَّقة منفصلة إلى "بوّابة noise" تابعة لـ Meta، تُنقَل عبر Tigon، منفصلة عن جلسة Noise_XX/chatd الرئيسية لـ WA |
| مساحات الوكيل | تطبيقات ويب صغيرة يبنيها الوكيل ويستضيفها داخل CVM، تُمرَّر عبر وكيل عكسي إلى WebView على الهاتف |
| موصِّل (Connector) | رابط مُسجَّل بين الوكيل وخدمة طرف ثالث (Gmail، تقويم، Messenger، مسار دفع، نقطة نهاية مخصَّصة) |
| `hatch/cvm` (Vesta) | **نظام هوية الجهاز/VM واسترداد إثبات الشريحة** الخاص بالوكيل، PAKE من نوع OPAQUE محمي برمز PIN — **ليس** خزنة دفع (يُصحِّح تمريراً بحثياً سابقاً، انظر §6) |
| بوّابة الموافقة | تأكيد بوجود إنسان في الحلقة قبل إجراء خطير/لا رجعة فيه يقوم به الوكيل |

### 1.2 العلاقة بدردشة Meta AI

يمكن الوصول إلى Muse من سطح الدردشة نفسه الخاص بـ Meta AI، ويتشارك بعض البنية التحتية (الإعلان عن قدرة JID الخاص بالبوت — انظر §7) وقناة بيانات Hatch الوصفية بصيغة JSON الموثَّقة في `WA_META_AI.md` §5 (`HF1`/`HatchMetadataRequestManager`، `ProtocolMessage.aiMetadataOperation`). لكن نظام متصفح الوكيل/VM/مساحة العمل الذي يغطيه هذا التقرير هو **منظومة منفصلة وأكبر بكثير**: لا تنتقل عبر جلسة chatd/Noise_XX على الإطلاق، ولها نقل أصلي خاص بها، وتحفظ حالتها الخاصة (الأهداف، التغذية، المخرجات، الموافقات) من جهة الخادم داخل CVM. المعالجة الخاصة / عنقود TEE (Meta AI يجيب عن أسئلة حول دردشاتك الخاصة، البحث الخاص) هو نظام **ثالث ومستقل** — انظر §11 للتمييز الكامل.

---

## 2. نظرة عامة على البنية

### 2.1 خريطة الحزم

جميع أنشطة Hatch/الوكيل هي `android:exported="false"` — لا نقطة دخول عبر التطبيقات؛ كل شيء يُشغَّل داخل العملية من سطح الدردشة/الوكيل.

| الحزمة | الدور |
|---------|------|
| `com.whatsapp.hatch.vm` (`p085vm`) | مستوى تحكم/دورة حياة VM: `HatchVmLifecycleCoordinator`، `HatchVmApiClient`، `HatchVmWaker`، `HatchVmLeaseGate`، `GraphQlHatchAbraTokenProvider`، `HatchAbraTokenRevoker` |
| `com.whatsapp.hatch.onboarding` | `HatchWaffleOnboarding`، `HatchPairingAuthBrowsingActivity`، `HatchMuseConnectionActivator` |
| `com.whatsapp.hatch.computer` / `.conversation.browser` / `.conversation.approval` | `HatchComputerActivity` (سطح مكتب VM الكامل)، `HatchBrowserStreamActivity` (متصفح مباشر داخل الدردشة)، `HatchBrowserPreviewActivity` (بوّابة الموافقة) |
| `com.whatsapp.hatch.feed/goals/ideas/activity/approvalhistory` | واجهة مساحة العمل: التغذية، الأهداف + الأهداف الفرعية، الأفكار، سجل الموافقات |
| `com.whatsapp.hatch.artifacts/media` | المخرجات والملفات التي يُنتجها الوكيل |
| `com.whatsapp.hatch.connectors(.ui)` | فهرس الموصِّلات الخارجية، تدفقات الربط، إجراء البطاقة الافتراضية، وضع الصلاحيات لكل موصِّل |
| `com.whatsapp.hatch.identity.ui` | وثائق "عني" الخاصة بالوكيل |
| `com.whatsapp.hatch.scheduledtasks.impl` | واجهة المهام المتكررة على VM الوكيل |
| `com.whatsapp.hatch.cvm` / `.cvm.pin` | **ليست خزنة** — استرداد هوية الجهاز/VM محمي برمز PIN (Vesta OPAQUE)، §6 |
| `com.whatsapp.hatch.subscription(s).iap` | تدفق شراء الشريحة المدفوعة، §7 |
| `com.whatsapp.bot.agentspaces.*` | مستضيف "المساحات": `HatchSpaceActivity` + وكيل عكسي `HatchSpaceTunnel`، محوِّل `NoiseHatchVmTransport` |
| `com.whatsapp.bot.agentbrowser.*` | محرك المتصفح + نقل VM: `BrowserSessionController` (WebView لـ noVNC)، `NoiseVmConnection`/`WaNoiseChannel`، `agentbrowser.noise.carrier.*` (JNI أصلي) |
| `com.whatsapp.bot.securecredentials.*` | `SecureCredentialVault` — مخزن بيانات الاعتماد، من جهة الخادم داخل CVM |
| `com.whatsapp.bot.agentactivity/agentfeed/agentgoals/agentapprovals` | طبقة البيانات/التغذية خلف واجهة `hatch.*` |
| `com.whatsapp.bot.infra.vmmedia` | جلب خام لنظام ملفات VM الوكيل (`/fs/raw/`، `/media/raw/`) |
| `com.whatsapp.bot.quiz` | `AiQuizViewerActivity` — عارض اختبار richResponse، **ليس** ميزة VM (§2.3) |
| `com.crossapp.tigonhttp(.noise)` | حزمة HTTP الأصلية المشتركة بين التطبيقات **Tigon** التابعة لـ Meta + `NoiseChannelManagerHolder` |

### 2.2 ثلاث طبقات نقل متمايزة — لا تخلط بينها

هذه أهم حقيقة بنيوية منفردة، وقد أخطأ تمرير بحثي سابق في واحدة من الثلاث (§6.1 يُصحِّحها):

| # | النقل | يحمل | العائق لعميل طرف ثالث |
|---|-----------|---------|-----------------------------------|
| 1 | **قناة VM بوّابة Noise الموثَّقة** — `/v1/noise` عبر Tigon، ناقل أصلي `libwa-noise-gateway-carrier-jni.so` | كل ما يتفاعل معه الوكيل: HTTP متصفح-VM (`/api/*`، `/fs/*`، `/spaces/*`)، تيار شاشة noVNC، ميزات مساحة العمل، عمليات بيانات الاعتماد الآمنة | ناقل Noise+WebSocket الأصلي **و** إلحاق WAFFLE الرسمي — محجوب تماماً |
| 2 | **مستوى تحكم HTTPS عادي** إلى `hatch-api.meta.ai` | إيقاظ VM، رمز حامل Abra، رابط الإلحاق، **و** (مُصحَّح، §6) نقاط نهاية استرداد الهوية `hatch/vesta-auth/*` / `hatch/cvm-*` | النقل قابل للمراقبة عبر MITM من حيث المبدأ (جهاز مُجذَّر، تجاوز التثبيت)؛ تحتاج نقاط نهاية الهوية إضافةً إلى رياضيات OPAQUE الأصلية + ما بعد الكمّي (`libvesta_client_jni.so`) لإنتاج أجسام طلب صالحة |
| 3 | **MEX/GraphQL عادي** عبر نقل WhatsApp العادي `whatsapp-android-mex`/`whatsapp-android-www` | قراءات/حذوفات المهام المجدولة/التذكيرات (فردية وجماعية)، قراءة معلومات امتثال الاشتراك، سكّ رمز دفع Hatch | لا عائق أصلي/موثَّق — قابل للوصول بنفس طريقة أي عملية MEX أخرى |

الطبقة 1 هي ما يسمّيه التمرير البحثي الأصلي (2.26.41.6) "نقل VM Hatch" وهي الغالبية العظمى من سطح المنظومة. الطبقة 3 هي **الجزء الوحيد** من Hatch الذي يمكن لعميل بنمط Baileys/velowa تشغيله على الأرجح.

### 2.3 ليس جزءاً من VM — ارتباط الاختبار (quiz)

`com.whatsapp.bot.quiz.AiQuizViewerActivity` هو عارض بملء الشاشة لاختبار مُضمَّن في رسالة استجابة غنية (richResponse) مخزَّنة من بوت (بدائية اختبار "Jarvis" من richResponse — نطاق `WA_META_AI.md` §4.3/§6.3، لا Hatch). يُحمِّل الاختبار **من مخزن الرسائل المحلي** برقم صف + مفتاح + قسم (معطيات نية `ai_quiz_viewer_message_row_id`، `ai_quiz_viewer_quiz_key`، `ai_quiz_viewer_section_index`) — لا استدعاء شبكة، لا نقل VM. يُذكر هنا فقط لتجنُّب الخلط بينه وبين ميزة Hatch؛ انظر §11 للجدول الكامل للتمييز.

---

## 3. مستوى التحكم والإلحاق

### 3.1 إلحاق WAFFLE (`found`)

أول استخدام لسطح الوكيل يُشغِّل **`HatchWaffleOnboarding`**: يُثبت العميل أنه بناء WhatsApp أصلي وغير معدَّل عبر إثبات سلامة **WAFFLE** (نفس عائلة إثبات العميل الرسمي المستخدَمة في واجهة حظر `com.whatsapp.waffle.wfac` / ربط الحساب — انظر `WA_CLIENT_INTEGRITY.md` §11 لمكوِّن WFAC الشقيق). بقايا سجلات: `"waffle-onboarding"`، `"vm-credentials"`، `"pairing-url"`، `"HatchWaffleOnboarding/link pairing-url-received="`. لا يمكن لعميل طرف ثالث إنتاج رمز WAFFLE صالح، فلا يمكنه حتى تهيئة VM — هذا هو العائق الصلب من جهة الإلحاق، مستقلاً عن ناقل بوّابة Noise.

### 3.2 الربط (`found`)

`HatchPairingAuthBrowsingActivity` يفتح **رابط ربط** بنمط OAuth يربط حساب WhatsApp بوكيل/حساب Meta AI؛ يُسجَّل الاكتمال كـ `pairing-url-received`.

### 3.3 إيقاظ VM وحامل Abra (`found`)

`GraphQlHatchAbraTokenProvider` يسكّ رمز حامل GraphQL من نوع "Abra" لـ VM؛ ثم ينفّذ `HatchVmApiClient`:

```
POST https://hatch-api.meta.ai/hatch/vm/wake
{"vm_id": "...", "retry_count": N}
```

هذا HTTPS عادي، ليس قناة Noise. تُغذّي الاستجابة منطق النقطة النهائية المخزَّنة في `HatchVmLifecycleCoordinator` ("connect cached-endpoint"، "invalidateToken failed") وتُحَل إلى `HatchVmEndpoint` (`C57830PwR`): المضيف/عنوان URL الأساسي، `auth_token`، `bearerExpiresAtMs`، علم رمز مُحقَّق، وخريطة معطيات تحمل `notary_token` لـ `/v1/noise`. يتولى `HatchAbraTokenRevoker` الإلغاء.

**إمكانية الوصول:** استدعاء الإيقاظ وسكّ الرمز هما HTTPS/GraphQL عاديان، قابلان من حيث المبدأ للمراقبة عبر MITM على جهاز مُجذَّر مع تجاوز التثبيت — لكنهما عديما الفائدة دون حساب مُهيَّأ بـ WAFFLE، لأن الخادم لن يسلّم نقطة نهاية VM عاملة لعميل غير معروف (`inferred`؛ غير مؤكَّد بشكل مستقل من جهة الخادم).

---

## 4. نقل VM الموثَّق لمتصفح الوكيل

هذه هي النتيجة البارزة للمنظومة: VM متصفح الوكيل **لا** ينتقل عبر جلسة Noise/XMPP الرئيسية لـ WhatsApp. يفتح **جلسة Noise منفصلة إلى "بوّابة noise"** تابعة لـ Meta، تُنقَل عبر حزمة Tigon HTTP التابعة لـ Meta، من خلال مكتبة أصلية مخصَّصة، مع مُحقِّق إثبات ومفتاح مصادقة خاص مُشتَرَك اختياري.

### 4.1 تبادل المصافحة (`found`، `WaNoiseChannel`)

تأخذ `WaNoiseChannel` مضيف نقطة نهاية VM وتُلحق معطيات استعلام مُرمَّزة بـ URL قبل المصافحة:

| المعطى | المصدر |
|-------|--------|
| `auth_token` | `HatchVmEndpoint.auth_token` (حامل VM) |
| `notary_token` | القيمة لمفتاح `/v1/noise` في خريطة معطيات النقطة النهائية، فقط إذا لم تكن فارغة |
| `app_id` | ثابت app-id لـ WA (`inferred`، غير مُحلَّل من سلسلة حرفية) |
| `app_version` | سلسلة حرفية ثابتة `"2.26.41.6"` |

مسار المصافحة: **`/v1/noise`**. مهلة المصافحة **20000 ms**؛ ميزانية فتح القناة الكلية **60000 ms** (`NoiseVmConnection`). بقايا سجلات: `noise/open-start`، `noise/reused`، `noise/closed reason=...`، `noise/use-once`.

### 4.2 الناقل الأصلي والإثبات (`found`)

`NoiseGatewayCarrier` هو كائن JNI من نوع `com.facebook.jni.HybridData` يُحمَّل بواسطة `NoiseGatewayCarrierSoLoader` باسم **`libwa-noise-gateway-carrier-jni.so`** — وليس ملفاً منفصلاً في `lib/arm64-v8a/`، بل مُعبَّأ داخل كتلة `libs.so` الخاصة بـ superpack (لا يتوفر استخراج ساكن مطابق بايتياً).

نقاط الدخول الأصلية: `createNative(TigonServiceHolder, NoiseChannelManagerHolder)`، `start(endpoint, ..., byte[32]?, AttestationVerifierHolder, Stream0Listener)`، `sendWebsocketFrameNative`، `stopNative`، `cancelHandshakeNative`. ردود نداء `Stream0Listener` (`onWebSocketUpgraded`، `onTransportReady`، `onReady(NoiseHandshakeOutcome)`، `onMessage`، `onClose/onFailure`) تُظهر أن القناة **Noise مُغلَّفة داخل WebSocket**.

لدى `AttestationVerifierHolder` ثلاث بانيات أصلية:

| النسخة | المعنى |
|---------|------|
| `createNoOpNative()` | لا إثبات — النسخة المُنشأة في المسار المفكَّك المرصود في هذا التمرير |
| `createSnpNative(bool)` | إثبات حوسبة سرية AMD SEV-SNP |
| `createSnpPinnedToChipsNative(chips[], bool)` | SNP مُثبَّت على معرّفات شرائح مسموح بها محدَّدة |

**أي نسخة تعمل وقت التشغيل `unknown`** من هذا التمرير الساكن. وجد تمرير `hatch/cvm` في 2.26.45.10 (§6) بشكل مستقل نقاط النهاية الملموسة في مستوى التحكم التي تدرج/تثبت معرّفات شرائح SEV-SNP (`/hatch/cvm-chip-allowlist`، `/hatch/cvm-chip-selection`)، مما يؤكد أن نمط إثبات الشريحة المُثبَّتة بنية تحتية حقيقية، لا مسار كود خامل فقط.

`NoisePrivateAuthMode.REQUIRED` مع مفتاح 32 بايت هو نمط "مصادقة خاصة" اختياري بمفتاح مُشتَرَك مسبقاً (`inferred`: ربط قناة)؛ غير مملوء في المسار المرصود، `unknown` ما إذا كان يُستخدم أبداً.

### 4.3 نقل HTTP فوق Noise (`found`)

بعد رفع القناة، تُرسل `WaVmHttpTransportImpl`/`VmHttpClient` طلبات HTTP بصيغة JSON عادية عبر نفق Noise بواسطة Tigon. المحوِّل على مستوى التطبيق (`NoiseHatchVmTransport`، تستخدمه كل ميزات مساحة العمل في §5) يعرض أربعة أفعال:

| الفعل | الوسم | الاستخدام |
|------|-----|-----|
| `CQ4(url, accept)` | `hatch_vm_read` | قراءة GET |
| `AEV(method,url,body,…)` | `hatch_vm_call` | استدعاء عام لمرة واحدة |
| `CXY(method,url,headers,body,streaming)` | `hatch_vm_request` | طلب مُتدفِّق (120 ث، أو غير محدود عند `streaming`) |
| `Cly(url,body,…)` | `hatch_vm_subscribe` | اشتراك SSE/ثنائي الاتجاه طويل الأمد |

يحتفظ `NoiseChannelHolds` بعدّاد مراجع لـ"حيازات" مفتوحة؛ تُفكَّك القناة بعد تحرُّر آخر حيازة (فترة قابلة للضبط). سطح مسار HTTP لـ VM (`found`، سلاسل حرفية): `/v1/noise`، `/api/`، `/api/computer/subscribe`، `/api/artifacts/pin`، `/spaces/`، `/spaces/v2`، `/spaces/cvm/<slug>`، `/spaces/share/`، `/workspace/`، `/home/hatch/`، `/media/raw/`، `/fs/raw/`، إضافة إلى مسارات بيانات الاعتماد في §5.9.

### 4.4 تيار شاشة noVNC (`found`)

يحمل `assets/vmvnc/` عميل ويب **noVNC** حقيقياً (`novnc-rfb.js`، `vnc.html`، ترخيص MPL-2.0 `LICENSE.txt`) — مؤكَّد وجوده بشكل مستقل في كلا البناءين 2.26.41.6 و2.26.45.10 (`assets-sweep.md`). تُحمِّل `BrowserSessionController` العنوان `https://appassets.androidplatform.net/assets/vmvnc/vnc.html` في WebView. تعرّف الصفحة HTML كائن **`BridgedWebSocket`** يتجاوز `window.WebSocket`: يعتقد noVNC أنه فتح `wss://bridge.invalid/` (بروتوكول فرعي `binary`)، لكن كل إطار RFB يُمرَّر عبر جسر JS الخاص بأندرويد `window.AndroidVncBridge` (`socketSend`/`socketClose`/`socketOpen`، ردود نداء `window.__vncBridge.*`). يفسّر تعليق HTML المُرسَل نفسه السبب: **نقطة نهاية websockify الحقيقية تتطلب `Authorization: Bearer <jwt>`**، وهو ما لا يمكن لـ WebSocket في WebView ضبطه، فيمتلك الكود الأصلي المقبس الحقيقي (المفتوح عبر Tigon بحامل VM) ويقوم شيم JS فقط بترحيل الإطارات.

الخلاصة: يُبثُّ سطح المكتب/المتصفح الخاص بـ VM إلى الهاتف كـ **RFB (VNC) حقيقي عبر WebSocket مصادَق بحامل JWT**، نفسه مُنفَّق عبر بوّابة Noise الموثَّقة؛ تعرضه noVNC في WebView. ضبط الإدخال (`isViewOnly`، `isInputEnabled`، `isPanModeEnabled`، طرق التصغير/التكبير وإطار العرض) وتحديد الحجم (`BrowserViewerJson{width,height,devicePixelRatio}`) أصليا المنشأ. `inferred`: إطارات "عرض"/معاينة أخف وزناً (`BrowserTaskScreenshotJson`، `BrowserTaskPresentationJson`) تدعم `HatchBrowserStreamActivity` داخل الدردشة، مع حجز VNC التفاعلي الكامل لـ `HatchComputerActivity`.

### 4.5 حيازة التحكم (`found`)

تنفّذ `BrowserControlLeaseJson{controlOwner, taskId, controlExpiresAtMs}` + `BrowserControlGrantJson`/`BrowserControlEnvelopeJson` من يقود المتصفح (الوكيل أم إنسان "يتولى التحكم")، مُقيَّد بوقت عبر `controlExpiresAtMs`. يطلب `BrowserViewerRequestJson` فتحة عارض. لا تخلط بين **حيازة تحكم المتصفح** هذه و"مزايدة" اختيار الشريحة SEV-SNP غير المرتبطة في §6 — انظر §11.

### 4.6 تأطير نفق agentspaces (`found`)

يمرّر `HatchSpaceTunnel` WebView إلى تطبيقات "مساحات" مُستضافة على CVM عند `/spaces/cvm/<slug>` عبر `hatch_vm_*`. غلاف JSON صغير للبروتوكول: `{"type":"http.res",id,status,streaming}`، `{"type":"http.end",…}`، `{"type":"http.err",…}`، إضافة إلى دفع لإبطال التخزين المؤقت `{"type":"hatch:space:query-invalidated","spaceSlug":…,"payload":{"queryKeys":[…]}}`. **يحذف رؤوساً بينية ومُعرِّفة** قبل الترحيل — تشمل القائمة السوداء `authorization, cookie, host, origin, x-forwarded-*, x-real-ip, x-noise-connection-id` — مما يؤكد أن جانب CVM يُنهي خادم HTTP حقيقياً لا يُوصَل إليه إلا عبر معرّف اتصال Noise.

---

## 5. مساحة عمل الوكيل

كل ميزة أدناه مبنية على أربعة أفعال `NoiseHatchVmTransport` من §4.3، أي أن كل سلسلة مسار أدناه هي طلب HTTP *داخل* نفق Noise إلى CVM. التمهيد: يُرسل `HatchBootstrapRequest` `{"sections":[…]}` على طريقة اشتراك `channel.bootstrap` ويقرأ ردّاً `{"accepted":[…]}` — يُعلن العميل أي أقسام مساحة العمل يريد دفعها إليه. لا تبدأ `HatchSpacesSync` إلا عندما "يكون Hatch مربوطاً وتوجد نقطة نهاية VM" (حرّاس سجلّات `found`).

### 5.1 مساحات الوكيل

**المساحة** هي تطبيق ويب صغير/صفحة نتيجة تفاعلية يستضيفها الوكيل، مُقدَّمة من داخل CVM، مُعنوَنة بسلسلة `slug`. لا يحصل الهاتف على HTML مباشرة أبداً — بل يُوجَّه WebView محلي (`HatchSpaceActivity`) إلى النفق (§4.6)، الذي يبثُّ استجابات HTTP الخاصة بـ CVM إطاراً بإطار، فتستطيع المساحة أن تكون تطبيقاً حيّاً له حالة لا مخرجاً ثابتاً.

| الإجراء | الطريقة + المسار | ملاحظات |
|--------|---------------|-------|
| الفهرس | `GET /spaces/v2` | `{"spaces":[{"slug","preview_card_url","preview_image",…}]}` |
| حالة المشاركة | `GET /spaces/share/<slug>` | يُعيد رابط مشاركة إذا كانت مشترَكة+عامة |
| النشر | متعدد الخطوات (`publish`/`post`/`poll`) | قد يُعيد "needs confirmation" |
| إلغاء النشر | `DELETE /spaces/share/<slug>` | |
| الحذف | `DELETE /spaces/v2/<slug>?source=space` | |
| تثبيت/إلغاء تثبيت مخرج | `POST /api/artifacts/pin {"artifact_ref":…,"pinned":bool}` | يثبّت مخرج مساحة كـ artifact |

مثال من الواقع (`inferred`): يقول المستخدم "تتبّع رحلات إلى لشبونة بأقل من 200 يورو"؛ يبني Muse مساحة تتبُّع؛ يفتحها المستخدم مباشرة، وينشر رابطاً قابلاً للمشاركة، ويثبّت أفضل نتيجة كـ artifact.

### 5.2 التغذية والنشاط

يُحلِّل `HatchFeedApi` ملخصاً مؤرَّخاً من **إصدارات (editions)**، كل واحدة تحمل **وحدات (units)** (`unit_id, title, kicker, emoji, body_md, days`) — الإحاطة الدورية للوكيل. مدعومة بخط زمني النشاط: `GET /api/activity?limit=200` إلى سجلات (`timestamp, type, status, title, subtitle, messageId, taskLabel, details.goal{…}`)، تربط كل سجل برسالة دردشة واختيارياً بهدف. نقطة دخول التغذية المستقلة محظورة بعلم تنقيح في 41.6 (`str5508` "[Debug Only] Feed")؛ خط زمني النشاط الذي يغذّيها ليس كذلك.

### 5.3 الأهداف

`HatchGoalsApi`: قائمة `GET /api/goals?<query>`، تفصيل `GET /api/goals/<goal_id>`. الهدف غاية دائمة: `{goal_id, title, emoji, summary, momentum_status, sub_goals:[…], updates:[{text, effective_at}]}` — غاية قائمة بحالة صحة وسجل تحديثات مُطابَق بالوقت يُضيف الوكيل إليه. الدخول محظور بعلم تنقيح (`str5511` "[Debug Only] Goals").

### 5.4 الأفكار

إجراءات قابلة للتشغيل يقترحها الوكيل يمكن للمستخدم **تنفيذها** أو **إلغاءها** (`HatchIdeaDetailBottomSheet`). السلاسل: "This idea is already running."، "This idea isn't available anymore."، "No ideas right now. Check back later."، "Couldn't start that idea. Try again." مثال: يقترح الوكيل "صياغة ملخص الربع الثالث"؛ النقر على تنفيذ يبدأ مهمة جارية مُسجَّلة في التغذية/النشاط.

### 5.5 المخرجات ووسائط/ملفات مساحة العمل

المخرجات هي نتائج يُنتجها الوكيل (وثيقة، صورة، جدول بيانات، نتيجة مساحة)، تُثبَّت/يُلغى تثبيتها عبر `/api/artifacts/pin`. تعيش ملفات الوكيل في **نظام ملفات CVM حقيقي خاص بكل وكيل** (`com.whatsapp.bot.infra.vmmedia.HatchWorkspaceMediaApi`):

| الاستدعاء | المسار | الشكل |
|------|------|-------|
| المكتبة | `POST /fs/library {"preset":"media","limit":n,"offset":m}` | `{entries:[{path,size,modified_ms}],total,has_more}` |
| خام | `GET /fs/raw/<path>` | بايتات خام |
| صورة مصغَّرة | `GET /fs/thumbnail/<path>?p=sm` | |
| حذف | `POST /fs/delete {"path":…,"recursive":false}` | |

سلسلة تأكيد الحذف: "This file will be removed from your agent's files. You can't undo this."

### 5.6 وثائق الهوية

تُخزَّن وثائق "عني" الخاصة بالوكيل كـ**ملفات نصية عادية في نظام ملفات VM نفسه**، لا مخزن مخصَّص: `GET /fs/read {path,offset,len}` ← `{text,bytes,eof,not_found}`؛ `POST /fs/write {path,text|bytes,offset,append,overwrite,create_parent}`. يحرِّر المستخدم وثائق يقرأها الوكيل لاحقاً كسياق دائم.

### 5.7 الموافقات وسجل الموافقات

**البوّابة المباشرة:** قبل إجراء خطير/لا رجعة فيه، يرفع الوكيل طلب موافقة (`HatchBrowserPreviewActivity`، `str54e1` "Approval required"). **السجل/التدقيق:** `GET /approvals/history?record_schema=snapshot_v1&limit=50`، مُقسَّم بـ`next_cursor`، إلى سجل مُهيكَل لكل موافقة: `{approval_id, status, decision, outcome_label, summary_title, purpose_summary, scope_summary, requested_at_ms, permission_question, payload_preview, request_preview_document, display_name, icon_key, blocks, rows, fields, items, links, attachments, version, truncated}`. الدخول محظور بعلم تنقيح (`str54e8` "[Debug Only] Approval history")، أما السجلّ الكامن فليس كذلك.

### 5.8 المهام المجدولة — ثلاث تنفيذات متمايزة

| # | السطح | النقل | العمليات | قابل للوصول من عميل؟ |
|---|---------|-----------|-----|--------------------|
| a | تذكيرات Meta AI الفردية (`com.whatsapp.metaai.tasks`) | MEX عادي عبر `whatsapp-android-www` | **`GetMetaAiReminders`**، **`DeleteMetaAiReminder`** | **تقريباً نعم** — استعلام MEX دائم مُحدَّد بالاسم، لا عائق أصلي/موثَّق |
| b | المهام المجدولة للمجموعات (`com.whatsapp.bot.group.groupinstructions.impl`، جديدة في 41.6) | MEX عادي عبر `whatsapp-android-www` | **`GetMetaAiGroupReminders`** (معطى `groupId`)، **`DeleteMetaAiGroupReminder`** (`groupId`، `reminderId`) | **تقريباً نعم** — نفس المنطق |
| c | المهام المجدولة على VM Hatch (`com.whatsapp.hatch.scheduledtasks.impl`) | VM عبر Noise | تشغيلات متكررة على VM الوكيل، تُلغى عبر نقل VM | لا — أصلي فقط |

9a/9b هما العمليتان **الوحيدتان** في مساحة العمل التي يمكن لعميل طرف ثالث الوصول إليهما على الأرجح، لأنهما لا تلمسان لا ناقل بوّابة noise الأصلي ولا إلحاق WAFFLE. يبدو أن إنشاء تذكير يحدث من جهة الوكيل (عبر استدعاء أداة في دردشة Meta AI)، لا عبر طفرة (mutation) ظاهرة للعميل — توجد فقط عمليات Get + Delete. أرقام `doc_id` لكلا الزوجين `unknown` (حل استعلام دائم مُحدَّد بالاسم؛ غير مُلتقط بشكل مستقل). يسمح سطح group-instructions أيضاً للمشرف بضبط Meta AI الخاصة بالمجموعة (قواعد، وثائق مرجعية، نغمة) عبر `CustomizeGroupMetaAiActivity` — واجهة مجاورة، ليست هي نفسها عملية مهمة مجدولة.

### 5.9 الموصِّلات ومخزن بيانات الاعتماد الآمن

**الموصِّل** هو رابط مُسجَّل بين الوكيل وخدمة خارجية. يُصادق المستخدم مرة واحدة (OAuth / مفتاح API / اسم مستخدم+كلمة مرور / FoA / Stripe / Messenger)، وتُخزَّن بيانة الاعتماد الناتجة **من جهة الخادم داخل CVM، أبداً في Android Keystore** — تُنفّذ `SecureCredentialVault` كل العمليات كاستدعاءات HTTP عبر نفس نقل VM Noise-HTTP. لا توجد أي إشارة إلى `KeyStore` أو `EncryptedSharedPreferences` أو `AndroidKeyStore` في أي مكان ضمن `securecredentials/`.

نقاط نهاية بيانات الاعتماد (`found`، عبر قناة VM Noise):

| المسار | الدور |
|------|------|
| `POST /v1/credentials/capture` | دفع بيانة اعتماد مُلتقَطة |
| `POST /v1/credentials/catalog/update` | إدراج/تحديث؛ الحقول المرصودة: `username`، `password`؛ الصلاحية عبر تعداد قيمة سلكية `JA9` |
| `POST /v1/credentials/catalog/delete` | `{id}` ← `{ok}` |
| `GET /v1/custom-connectors/list` | |
| `POST /v1/custom-connectors/register` | شكل مفتاح API `{connector, api_key:{key}, replace_existing}` أو شكل OAuth `{connector, oauth_bootstrap:{client_id, client_secret?,…}, replace_existing}` ← `authorize_url` |

فهرس الموصِّلات + تدفقات الربط (`found`، عبر نفس القناة): `GET /api/connectors?surface=settings&icon_cdn=whatsapp` ← `{connectors:[{id,name,description,icon,state,is_custom,management_kind,supports_multiple_accounts,consent}]}`؛ معلومات ربط لكل موصِّل (`/connectors/<id>/connect/info`) ومسارات مصادقة خاصة بالنوع لـ OAuth، مفتاح API، اسم مستخدم/كلمة مرور (مع `two_factor_required`/`attempts_remaining`/`login_timeout_remaining_secs`)، **FoA** (حسابات عائلة التطبيقات)، **مرافق Messenger** (ربط دردشة محمي برمز PIN)، و**ربط Stripe** (المدفوعات). الصلاحيات لكل موصِّل (`GET/SET /permissions/connectors/<id>`، سلسلة واجهة "Agent permissions"). الموصِّلات المخصَّصة تحمل تحذير كود غير مُراجَع صريحاً ("Meta doesn't review custom connectors… supervise your agent's use").

بالتصميم، **لا يرى الوكيل الأسرار الخام**: "Securely store passwords for your agent to use"، "Shared with your agent without saving". إجراء **البطاقة الافتراضية** (`HatchConnectorCardActionActivity`) يسكّ بطاقة لمرة واحدة يستخدمها الوكيل للدفع فلا يُعرَض رقم البطاقة الحقيقي أبداً ("The agent will never see your credit card"). يوجد `assets/api_key.txt` في APK ويُعامَل كمادة بيانات اعتماد وفق عقد الأدلة لدى البرين — لم يُفتح/يُقتبَس هنا؛ `inferred` أنه مفتاح API على مستوى التطبيق/العميل لمستوى تحكم hatch-api/GraphQL، لا سرّ خاص بمستخدم معيَّن.

**إمكانية الوصول لكل §5:** أصلي فقط. كل سلسلة مسار أعلاه قابلة للاستخراج من APK؛ لا شيء منها قابل للتشغيل أو المراقبة (مُشفَّرة داخل نفق Noise) أو التقليد من عميل طرف ثالث، لأن كل واحد من هذه الاستدعاءات يحتاج نقل §4 الموثَّق إضافة إلى VM مُهيَّأ بـ WAFFLE.

---

## 6. استرداد هوية CVM — نظام PIN من نوع Vesta OPAQUE (`hatch/cvm`)

### 6.1 تصحيح تأطير "خزنة البطاقة الافتراضية"

وصف تمرير بحثي سابق (2.26.45.10) `hatch/cvm` + `hatch/cvm/pin` بأنه "خزنة بطاقة افتراضية محمية برمز PIN". **هذا التأطير خاطئ على مستوى طبقة التشفير.** يخلط بين منظومتين غير مرتبطتين:

- **`hatch.connectors` / `HatchConnectorCardActionActivity`** (§5.9) — تدفق منح موصِّل حقيقي ومنفصل لمسار دفع طرف ثالث (على الأرجح Stripe بشكل شبه مؤكَّد). لا يحتوي **على أي إشارة كود** إلى صنف `com.whatsapp.hatch.cvm` أو `com.facebook.vesta` (تم الفحص: لا مرجع ترافقي من smali الخاص بـ `hatch.connectors` إلى `HatchCvmPinActivity`/`HatchCvmVestaClient`/`HatchCvmKeyService`).
- **`hatch.cvm` / `hatch.cvm.pin`** هو نظام **تسجيل هوية CVM وإثبات شريحة الوكيل**، لا مخزن بطاقات. لا يخزِّن **أي بيانات دفع من أي نوع** — لا حقل PAN/CVV/فاتورة في أي مكان من الحزمة. ما يحميه هو **سرّ هوية الجهاز/VM المُستَرَد عبر تبادل مفتاح مُصادَق بكلمة مرور من نوع OPAQUE، مع PIN كلمة المرور**، مرتبط باختيار شريحة أجهزة AMD SEV-SNP لـ CVM.

رمز PIN **ليس فتحاً محلياً بحتاً**: مسار تسجيل الدخول في `HatchCvmKeyService` يرسل تبادل OPAQUE حقيقي ذهاباً وعودة إلى خادم خلفي من Meta (`hatch-api.meta.ai/hatch/vesta-auth/*`، HTTPS عادي) قبل استخراج/استرداد أي مادة مفتاح محلية. يفشل PIN الخاطئ **من جهة الخادم** ("wrong pin"، "crypto failed")، لا مقابل تجزئة محلية فقط.

والأهم، هذه الحركة هي **HTTPS عادي إلى `hatch-api.meta.ai`** — نفس مضيف مستوى التحكم مثل `/hatch/vm/wake` (§3.3) — **ليست** قناة VM الموثَّقة عبر بوّابة Noise فوق Tigon. فالزعم الشامل "نفس العوائق الصلبة كالنقل" من §4/§5 لا ينطبق هنا: العائق الحقيقي لهذه المنظومة تشفيري، لا نقل موثَّق.

### 6.2 السطح الأصلي

يُحمِّل `com.facebook.vesta.VestaClient` **`libvesta_client_jni.so`** (جديدة في 2.26.45.10). جميع الطرق الأصلية الـ19 المُعلَنة عليه تنفّذ **PAKE من نوع OPAQUE بـPIN كلمة مرور، مُغلَّفاً إضافة بطبقة KEM/توقيع ما بعد الكمّي**، إضافة إلى خطوة تحقق "مفتاح HSM" مرتبط بالجهاز:

| الطريقة الأصلية | الدور |
|---|---|
| `getApiVersionNative` / `getProtocolVersionNative` | تفاوض الإصدار |
| `beginLoginNative` / `finishLoginNative` (×2 تحميل زائد) | خطوتا تسجيل دخول OPAQUE 1 و2 (تُنتج مادة مفتاح جلسة/تصدير) |
| `beginRegisterNative` / `finishRegisterNative` / `finishRegisterProtoNative` | تسجيل OPAQUE (تسجيل PIN جديد) |
| `unpackLoginPayloadNative` / `unpackLoginPayloadProtoNative` | فكّ حمولة تسجيل الدخول المُحتجَزة من الخادم |
| `validateHsmKeyNative` / `validateHsmKeysWithOtaBundleNative` | تحقق زوج مفتاح مرتبط بالعتاد، اختيارياً مع حزمة OTA لتدوير مفتاح الجهاز |
| `verifyRestoreHistoryNative` | تحقق سجل استرداد/استعادة سابق |
| `pqWrapFinishLoginNative` / `pqWrapFinishRegisterNative` / `pqUnwrapFinishLoginResponseNative` | تغليف/فك تغليف ما بعد الكمّي لحمولات تسجيل الدخول/التسجيل |
| `pqWrapSchemeNative` | أي مخطط ما بعد الكمّي قيد الاستخدام (قيمة العودة `unknown` — تحتاج Frida) |

`libvesta_client_jni.so`، كناقل بوّابة Noise، مُعبَّأ داخل كتلة SUPERPACK الغامضة — لم يكن استخراج ساكن مطابق بايتياً ممكناً في هذا التمرير. `libvoprf-ed25519.so` (موجودة في نفس البناء) تتسق مع بدائية OPRF/VOPRF (لبنة OPAQUE الأساسية) لكنها **لم تُربَط** بشكل مستقل مع `VestaClient` — مُسجَّلة كمكتبة مجاورة محتمَلة، لا كمُثبَتة أنها نفس التنفيذ (`unknown`).

### 6.3 نقاط النهاية السلكية — HTTPS عادي إلى `hatch-api.meta.ai`

| المسار | الدور |
|---|---|
| `POST /hatch/vesta-auth/begin-login` | خطوة تسجيل دخول OPAQUE 1 |
| `POST /hatch/vesta-auth/finish-login` | خطوة تسجيل دخول OPAQUE 2، تُعيد الحمولة المُحتجَزة |
| `POST /hatch/vesta-auth/begin-register` | خطوة تسجيل OPAQUE 1 (PIN جديد/مُغيَّر) |
| `POST /hatch/vesta-auth/finish-register` | خطوة تسجيل OPAQUE 2 |
| `GET /hatch/vesta-auth/user-info` | `is_registered` + عدّادات محاولة/قفل |
| `GET /hatch/fetch_vms?notary_token=true[&vm_id=]` | إدراج/حل CVM(s) الخاص بالمستخدم |
| `POST /hatch/lease_vm` / `POST /hatch/cold-lease-cvm` | استئجار مثيل CVM (دافئ / بارد) |
| `GET /hatch/cvm-replace-state?env_id=` | انتقال حالة CVM |
| `GET /hatch/cvm-chip-allowlist?env_id=` | أي معرّفات شرائح SEV-SNP مسموح بها لهذا CVM |
| `POST /hatch/cvm-chip-selection` | تثبيت اختيار/مزايدة الشريحة |
| `GET /hatch/onboarding_statuses` | فحص حالة الإلحاق |
| `POST /hatch/vm/wake` | إيقاظ/استئناف CVM (أيضاً §3.3) |

لا شيء من هذه يلمس `/v1/noise` أو أفعال `hatch_vm_*` — مما يؤكد تصحيح §6.1. `/hatch/cvm-chip-allowlist` و`/hatch/cvm-chip-selection` هما أول **دليل سلكي ملموس** لنمط إثبات SEV-SNP "المُثبَّت على معرّفات شرائح محدَّدة" الذي وجدته §4.2 فقط كتوقيع باني أصلي.

تشمل DTOs السلكية (حقول `kotlinx.serialization` بالاسم التسلسلي، لا أسماء حقول Java مشوَّشة) تسمية تبادل الرسائل الثلاث الخاصة بـOPAQUE **L1/L2/L3** (`base64url_encoded_opaque_l1/l2/l3`، إضافة إلى صيغ `_sig`)، مفاتيح عامة "island" من نوع RSA/Ed25519 مرتبطة بالجهاز (مصدر `unknown` — HSM/Keystore مقابل صيغة داخلية خاصة بـVesta)، وسجل محلي (`HatchCvmJournal`: `candidate_chip_ids`، `accepted_chip_ids`، تعداد `bid_state` بقيم `PENDING/ACCEPTED/RETIRED`، `abra_user_id` — نفس هوية الحامل الخاصة بـ`GraphQlHatchAbraTokenProvider`).

### 6.4 ما يحميه PIN بالفعل

`HatchCvmKeyService.A00` (مسار الاسترداد): (1) ينفّذ تسجيل دخول OPAQUE (`begin-login` ثم `finish-login`، رياضيات أصلية)؛ (2) فقط عند النجاح، يستخرج/يستعيد `HatchCvmKeyProviderImpl` مادة المفتاح المحلية الفعلية من حمولة تسجيل الدخول المُحتجَزة؛ (3) يوجد مسار محو لحالة عدم تطابق مفتاح الجهاز أو إعادة ضبط صريحة. **PIN صحيح مطلوب لإتمام تبادل OPAQUE عميل↔خادم حقيقي** — لا يُفرِج الخادم عن الحمولة المُحتجَزة إلا عند نجاح `finish-login`، مُحدَّد المعدَّل ومُحقَّق من جهة الخادم (`attempts_remaining`، `login_timeout_remaining_secs` على كل استجابة). مهاجم يملك الجهاز لا PIN لا يستطيع تجاوز هذا بالقوة الغاشمة محلياً. السرّ المحمي هو **مادة مفتاح هوية CVM/الجهاز اللازمة لاستئناف جلسة VM السرية الخاصة بهذا المستخدم** — لا بيانة اعتماد دفع.

بشكل منفصل، تستخدم `HatchCvmPinReminder` مفتاح AES/GCM **محلي بحت** (الاسم المُستعار `hatch:pin-reminder:v1:...`) فقط لتشفير حالة إشعار "ذكّرني بضبط PIN" — غير مرتبط بتبادل Vesta وهو القطعة الوحيدة من التشفير غير القابلة للمراقبة سلكياً في هذه المنظومة.

### 6.5 الحكم على إمكانية الوصول لـ§6

المخطط السلكي قابل للاستخراج الكامل (أعلاه)؛ النقل HTTPS عادي، قابل من حيث المبدأ للمراقبة عبر MITM **دون** هزيمة إثبات WAFFLE أو ناقل بوّابة Noise الأصلي. لكن **المشاركة الفعلية** (تسجيل دخول/تسجيل حقيقي) غير ممكنة من APK وحده: كل حقل طلب/استجابة يُنتَج أو يُستهلَك بواسطة عمليات OPAQUE أصلية + تغليف/فك تغليف ما بعد الكمّي داخل `libvesta_client_jni.so`، المُعبَّأة في superpack دون استخراج مطابق بايتياً. يمكن لعميل التقاط وإعادة تشغيل *شكل* JSON النصي الصِّرف لكن لا يمكنه حساب `opaque_l1`/`l3` صالح، أو برهان زوج مفتاح island، أو حمولة مُغلَّفة بما بعد الكمّي — عائق **تشفيري**، يختلف بنيوياً عن عائق النقل الموثَّق في §4.

---

## 7. تحقيق الدخل — شريحة اشتراك Hatch المدفوعة

تضيف مجموعة اشتراك من عصر 2.26.45.10 شريحة مدفوعة حقيقية لـMuse. تدفق الشراء (سلسلة `inferred`، كل خطوة `found` منفردة):

1. يفحص العميل علم الميزة **`ai_hatch_in_app_subscriptions_enabled`** (سجل: "`ai_hatch_in_app_subscriptions_enabled` is off"). لم يُعثر على معرّف عددي للعلم — يُشار إليه بالاسم فقط.
2. ثابت الشريحة **`NME_SUBSCRIPTION`**؛ تُجلب تفاصيل المنتج لكل شريحة (`HatchSubscriptionPurchase$launch$2`، سجل "Fetching product details for tier"؛ اسم الشريحة مُدرَج بالاستبدال، لا SKU ثابت).
3. فحص الامتثال: **`WamoSubGetComplianceInfo`** (`whatsapp-android-mex`، مُحدَّد بالاسم، لا حقول إدخال مضبوطة عند موقع الاستدعاء — مُحدَّد بالجلسة/الهوية فقط).
4. سكّ رمز الدفع: **`HatchGenFrlPaymentsAccessTokenMutation`** (`GraphQlHatchFrlPaymentsTokenProvider`، نطاق `whatsapp-android-www`؛ لم يُعثر على توسيع "FRL" في أي سلسلة في هذا التمرير — `unknown`).
5. تشغيل Google Play Billing (`HatchManageSubscriptionViewModel$openBilling$1`) — `BillingClient` قياسي لأندرويد عبر SDK تجاري مشترَك من Meta (`com.facebook.payments.dcp.xapp.*`)، موسوم بـ`app="WHATSAPP"`.
6. عند الشراء، مُطابقة تنفيذ من جهة الخادم (`HatchSubscriptionPurchaseReconciler`)، على الأرجح عبر **`DCPFulfillIAPTransactionsMutation`** (`pay_dcp_fulfill_iap_transactions`، طلب Pando مباشر، الحقول `platform`/`app`/`purchase_tokens`/`subscription_purchase_tokens`/`upl_session_id`، كلها إلزامية عند موقع هذا الاستدعاء) — غير مؤكَّد بشكل مستقل أنه الاستدعاء الدقيق الذي يستخدمه هذا المُطابِق (`unknown`).

توجد أربع عمليات أخرى مُعلَنة فقط في فهرس الاستعلام الدائم (`IACQueryProductInfo`، `IACQuoteDisplay`، `IACSandboxPlatformMode`، `DCPInternalSandboxCreateSessionMutation`) **لا صنف استدعاء لها في أي مكان من smali** — `unknown` ما إذا كان ذلك كوداً ميتاً/مستقبلياً، أو بوّابة خادم/علم، أو موقع استدعاء مُركَّب بسلاسل يُفوِّته grep عادي.

**إمكانية الوصول:**

| العملية | النطاق | تحتاج | قابلة للوصول من عميل طرف ثالث؟ |
|---|---|---|---|
| `WamoSubGetComplianceInfo` | `whatsapp-android-mex` | جلسة mex مُصادَق عليها فقط | **نعم، من حيث المبدأ** — استعلام mex عادي بلا معطيات |
| `HatchGenFrlPaymentsAccessTokenMutation` | `whatsapp-android-www` | جلسة مُصادَق عليها | **قابلة للوصول على مستوى النقل**؛ قيمة الرمز المسكوك خارج التدفق المقصود `unknown` |
| `DCPFulfillIAPTransactionsMutation` | `whatsapp-schema` (Pando) | رمز شراء/اشتراك حقيقي موقَّع من Google Play Billing | **لا** — الطلب قابل التشكيل، لكن لا يمكن وضع شيء صادق فيه دون شراء Play Billing حقيقي عبر سياق `com.whatsapp` موقَّع |
| `IAC*` / `DCPInternalSandboxCreateSessionMutation` | `whatsapp-schema` | unknown (لا صنف استدعاء مُعثور عليه) | **غير معروف** |
| Google Play Billing نفسه | لا ينطبق | متجر Play + سياق تطبيق موقَّع | **لا** — ليس حتى استدعاء خادم WhatsApp |

---

## 8. الحكم على إمكانية الوصول

| المكوِّن | النقل | العائق | قابل للوصول من عميل طرف ثالث (Baileys/velowa)؟ |
|---|---|---|---|
| مساحات الوكيل، التغذية/النشاط، الأهداف، الأفكار، المخرجات، وسائط/ملفات مساحة العمل، وثائق الهوية، الموافقات+السجل، المهام المجدولة على VM Hatch، الموصِّلات (جميع التدفقات)، مخزن بيانات الاعتماد الآمن | قناة VM Noise الموثَّقة (§4) | ناقل بوّابة noise الأصلي `.so` + إلحاق WAFFLE | **لا** |
| مستوى التحكم (إيقاظ VM، رمز Abra، رابط الربط) | HTTPS عادي إلى `hatch-api.meta.ai` | تهيئة مرتبطة بـWAFFLE (الخادم لا يصدر VM عاملاً دونه) | **لا** (المخطط قابل للمراقبة عبر MITM؛ غير قابل للتشغيل بشكل مستقل) |
| استرداد هوية/PIN عبر CVM (`hatch/cvm`، Vesta OPAQUE) | HTTPS عادي إلى `hatch-api.meta.ai` | رياضيات OPAQUE الأصلية + ما بعد الكمّي في `libvesta_client_jni.so` | **لا** — عائق تشفيري، لا عائق نقل موثَّق |
| التذكيرات الفردية — `GetMetaAiReminders` / `DeleteMetaAiReminder` | MEX عادي، `whatsapp-android-www` | لا شيء مُعثور عليه | **تقريباً نعم** (doc_id `unknown`) |
| تذكيرات المجموعات — `GetMetaAiGroupReminders` / `DeleteMetaAiGroupReminder` | MEX عادي، `whatsapp-android-www` | لا شيء مُعثور عليه | **تقريباً نعم** (doc_id `unknown`) |
| معلومات امتثال الاشتراك — `WamoSubGetComplianceInfo` | MEX عادي، `whatsapp-android-mex` | لا شيء مُعثور عليه | **نعم، من حيث المبدأ** |
| سكّ رمز الدفع — `HatchGenFrlPaymentsAccessTokenMutation` | GraphQL عادي، `whatsapp-android-www` | لا شيء على مستوى النقل؛ قيمة الرمز العملية في أماكن أخرى غير معروفة | **قابلة للوصول على مستوى النقل** |
| تنفيذ IAP — `DCPFulfillIAPTransactionsMutation` | Pando GraphQL عادي، `whatsapp-schema` | تحتاج رمز Play Billing موقَّعاً حقيقياً | **لا** (لا شيء صادق يمكن إرساله) |
| عمليات `IAC*` / sandbox IAP | `whatsapp-schema` | لا صنف استدعاء مُعثور عليه | **غير معروف** |
| اختبار richResponse (bot.quiz) | مخزن الرسائل المحلي | لا شيء — ليست ميزة VM | الحمولة قابلة للاستخراج؛ تصل كرسالة بوت عادية |

الصفوف "تقريباً نعم"/"نعم، من حيث المبدأ" هي **كل** السطح القابل للوصول من عميل في هذه المنظومة. كل ما عداه — وهو معظم الوكيل — يحتاج إما الناقل الأصلي لبوّابة Noise إضافة إلى إثبات WAFFLE صالح، أو تشفير OPAQUE/ما بعد الكمّي الأصلي الذي لا يمكن استخراجه ساكناً من هذا APK.

---

## 9. Baileys / velowa

**الحكم: هذه المنظومة مستحيلة في JS لعميل طرف ثالث، نقطة انتهى — ليست ميزة ناقصة، بل عائق بنيوي.** لا يمكن لـvelowa (مشروع العميل النشط خلف هذه الوثائق) تنفيذ VM متصفح الوكيل/مساحة العمل الخاصة بـHatch/Muse للأسباب نفسها التي قدّمها التمرير البحثي الأصلي:

| العائق | لماذا لا يمكن تجاوزه في JS/WASM |
|---|---|
| `libwa-noise-gateway-carrier-jni.so` | كل مصافحة Noise وتأطير WebSocket لقناة VM كود أصلي داخل كتلة SUPERPACK الغامضة. لا توجد وثيقة بروتوكول لإعادة التنفيذ مقابلها — شكل السلك (معطيات الاستعلام، مسار `/v1/noise`، أفعال HTTP-over-Noise، بروتوكول RFB الفرعي لـnoVNC) مُستخرَج أعلاه، لكن تشفير Noise الفعلي (استخلاص المفتاح، مصادقة الإطار) موجود فقط مُترجَماً داخل ذلك `.so`. إعادة تنفيذه يعني عكس مكتبة أصلية مُجرَّدة، لا كتابة عميل مقابل مواصفة. |
| إثبات العميل الرسمي WAFFLE | يحجب إلحاق VM قبل فتح أي قناة Noise على الإطلاق. لا يمكن لعميل طرف ثالث إنتاج رمز WAFFLE صالح، فلا يمكنه تهيئة VM من الأساس — يحجب هذا حتى محاولة مصافحة Noise. |
| `libvesta_client_jni.so` (OPAQUE + ما بعد كمّي) | منفصل عمّا سبق: حتى حيث حركة استرداد الهوية (§6) هي HTTPS عادي وقابلة للمراقبة، رياضيات OPAQUE من جهة العميل (`opaque_l1`/`l3`، براهين زوج مفتاح "island"، التغليف ما بعد الكمّي) أصلية. التقاط شكل JSON لا يوفّر أي شيء لحساب طلب صالح. |
| إثبات AMD SEV-SNP | متعامد مع العميل — إنه VM *الخادم* الذي يثبت أصالته للتطبيق الرسمي — لكنه يؤكد أن التصميم بأكمله يفترض نظيراً أصلياً وموثَّقاً على الطرفين. |
| Tigon | حزمة HTTP الأصلية الداخلية المشتركة بين التطبيقات التابعة لـMeta تحمل كل طلب في §4 و§6؛ كائنات طلبها ليست شكلاً سلكياً عاماً ومُرقَّماً. |

ما يمكن لـvelowa (أو أي عميل بروتوكول) الوصول إليه دون لمس أي مما سبق: عمليات تذكير MEX الأربع المُحدَّدة بالاسم (§5.8) وعمليات GraphQL لامتثال الاشتراك/سكّ رمز الدفع (§7) — كلها تنتقل عبر نفس نقل WA MEX/GraphQL العادي الذي تتحدثه velowa أصلاً لكل شيء آخر في هذا المستودع. لا يُعطى مثال كود هنا لأن أياً من مصادر هذا التقرير لم تلتقط طلباً/استجابة ملموسة لتلك العمليات بما يتجاوز أسماء العمليات وأشكال المعطيات المُدرَجة أصلاً في §5.8/§7/§8؛ ابتكار بايتات حمولة سيُحرِّف مستوى الأدلة.

---

## 10. حالات الخطأ / نقاط حذر

| العرض | السبب | ملاحظة |
|---|---|---|
| "Computer is turned off on this VM" | VM غير مُهيَّأ/مُستيقظ لسطح سطح المكتب الكامل | سلسلة `HatchComputerActivity` |
| "Approval required" لا تُحَل أبداً إلى إجراء | المستخدم لم يؤكِّد بوّابة الموافقة | بالتصميم — إنسان في الحلقة |
| "This idea isn't available anymore." / "This idea is already running." | بطاقة الفكرة تجاوزها الزمن أو قيد التنفيذ أصلاً | `HatchIdeaDetailBottomSheet` |
| "No goals yet" / "No ideas right now. Check back later." / "No approvals yet" | أقسام مساحة عمل خالية، ليست خطأ | |
| "Couldn't load your agent's files" | فشل استدعاء `/fs/library` أو `/fs/raw/` عبر نفق Noise | |
| رسالة بنمط `PrivateSearchSessionManager` "thread superseded by a newer search, refusing" (نظام TEE مجاور، ليس Hatch) | مُدرَجة في §11 فقط لتجنُّب تلوُّث متقاطع لسلاسل الخطأ بين النظامين | انظر الفروق الأساسية |
| 400 "already exists; set replace_existing=true" | تسجيل موصِّل مخصَّص دون علم `replace_existing` | `HatchConnectorsListRequester` |
| "wrong pin" / "finish-login crypto failed" | فشل تسجيل دخول OPAQUE من جهة الخادم | مُحدَّد المعدَّل عبر `attempts_remaining`/`login_timeout_remaining_secs` |
| "hsm key missing" / "hsm key invalid" / "hsm key check failed" | فشل تحقق مفتاح HSM المرتبط بالجهاز داخل مسار استرداد Vesta | §6.4 |
| `noise/gave-up limit=deadline` | تجاوز ميزانية فتح قناة VM Noise (60 ث) | `NoiseVmConnection` |
| `NoiseHandshakeOutcome.VERIFICATION_FAILED` | فشل فحص الإثبات في مصافحة بوّابة Noise | §4.2 |
| "`ai_hatch_in_app_subscriptions_enabled` is off" | علم ميزة الاشتراك مُعطَّل من جهة الخادم | §7 |
| "HatchSubscriptionPurchase/purchase no compliance data" | نتيجة `WamoSubGetComplianceInfo` غائبة قبل محاولة شراء | §7 |

---

## 11. فروق أساسية — ما لا يجب الخلط فيه

| لا تخلط بين | الحقيقة |
|---|---|
| وكيل Hatch/Muse (هذا التقرير) مقابل **دردشة Meta AI** (`WA_META_AI.md`) | Meta AI جهة اتصال بوت يُوصَل إليها عبر `botInvokeMessage`/JIDs البوت على بروتو الرسالة العادي؛ Hatch/Muse وكيل منفصل يُشغِّل VM موثَّقاً عن بُعد. يتشاركان بعض البنية التحتية (قناة بيانات Hatch الوصفية بصيغة JSON عبر `ProtocolMessage.aiMetadataOperation`، أعلام قدرة مُعلَنة لـJID بوت Hatch `1807055946647697@bot`) لكنهما منظومتان بنيوياً متمايزتان |
| VM Hatch/Muse مقابل **المعالجة الخاصة / عنقود TEE** (ذكاء اصطناعي بسياق الدردشة، البحث الخاص) | عنقود TEE (`ClusterFetchPrekeyBundleConnection`، `IplsdHandshakeExecutor`، `PsiSearchToolHandler`، `TeePrefixCacheAnchor`) هو Meta AI يجيب عن أسئلة **حول دردشاتك المحلية الخاصة** عبر حاوية موثَّقة + بحث PSI — لا علاقة له بـVM متصفح وكيل Hatch. *إرسال* استعلام البحث الخاص ينتقل عبر رسالة دردشة بوت عادية (قابلة للوصول)، بينما يبقى حساب PSI/الحاوية نفسه أصلياً — شكل إمكانية وصول مختلف عن أي شيء في هذا التقرير |
| `hatch.cvm` (استرداد الهوية/الشريحة، §6) مقابل `hatch.connectors` (البطاقة الافتراضية / Stripe، §5.9) | ميزتان منفصلتان تتشاركان فقط كلمات عابرة "card"/"vault" في التأطير التسويقي؛ لا تبعية كود بينهما (مُتحقَّق) |
| مفتاح AES/GCM المحلي لـ`HatchCvmPinReminder` مقابل تبادل Vesta OPAQUE | تشفير حالة إشعار محلي بحت مقابل استرداد هوية حقيقي ذهاباً وعوداً مع الخادم — فقط الأخير هو "من جهة الخادم" في حجب PIN |
| حقول "bid_state"/"chip" (§6) مقابل **حيازة التحكم** في المتصفح (§4.5) | محاسبة اختيار شريحة عتاد SEV-SNP مقابل من يقود متصفح الوكيل (وكيل/إنسان) — ثلاثة استخدامات مختلفة لمصطلحات متداخلة ("bid"/"lease"/"control") في هذه القاعدة الكودية |
| مستوى تحكم Vesta بـHTTPS عادي (§3، §6) مقابل قناة VM بوّابة Noise الموثَّقة (§4) | نقلان مختلفان، عائقان مختلفان (رياضيات OPAQUE أصلية مقابل Noise أصلي + إثبات WAFFLE) — الخلط بينهما يُضخِّم مكان انطباق عائق النقل الموثَّق فعلياً |
| مساحات الوكيل (§5.1) مقابل مخرجات الوكيل (§5.5) | المساحة تطبيق مُستضاف حيّ له حالة؛ المخرج ناتج ثابت (نتيجة *مثبَّتة* لمساحة تصبح مخرجاً، لكن المساحة نفسها تبقى قيد التشغيل) |
| `com.whatsapp.bot.quiz.AiQuizViewerActivity` مقابل ميزة Hatch | يقرأ اختبار richResponse مُسلَّماً أصلاً كرسالة بوت عادية من التخزين المحلي — لا VM، لا استدعاء شبكة، ليس جزءاً من هذه المنظومة على الإطلاق |

---

## 12. التدفق من البداية إلى النهاية — جلسة مهمة متصفح-وكيل واحدة

```
[User, in chat]
    │  "book me a table for two tonight"
    ▼
[Onboarding, first use only]
    │  HatchWaffleOnboarding: official-client WAFFLE attestation
    │  HatchPairingAuthBrowsingActivity: pairing URL (account ↔ agent link)
    ▼
[Control plane]  plain HTTPS to hatch-api.meta.ai
    │  GraphQlHatchAbraTokenProvider → Abra bearer
    │  HatchVmApiClient: POST /hatch/vm/wake {vm_id, retry_count}
    │  → HatchVmEndpoint{host, auth_token, notary_token, ...}
    ▼
[Noise-gateway handshake]  native libwa-noise-gateway-carrier-jni.so over Tigon
    │  GET …<vmhost>…?auth_token&notary_token&app_id&app_version=2.26.41.6
    │  path /v1/noise, 20s handshake timeout, attestation verifier (noOp/SNP/SNP-pinned)
    ▼
[Attested Noise channel open]  (60s budget, ref-counted "holds")
    │
    ├──▶ hatch_vm_request /api/computer/subscribe  — live task state (SSE-style)
    │
    ├──▶ hatch_vm_call   — agent navigates the booking site inside the CVM
    │        │
    │        ▼
    │    [Phone shows it live]  noVNC (RFB) over JWT-bearer WebSocket, viewOnly
    │        unless user takes a BrowserControlLeaseJson "control lease"
    │
    ├──▶ Login needed → /v1/credentials/... fetched INSIDE the VM
    │        (SecureCredentialVault; raw secret never reaches the agent's
    │         reasoning context, per design)
    │
    ├──▶ Payment needed → HatchConnectorCardActionActivity mints a virtual card;
    │        real card number never exposed to the agent
    │
    ├──▶ Risky/irreversible step → HatchBrowserPreviewActivity "Approval required"
    │        user confirms → recorded in HatchApprovalHistoryApi
    │
    ▼
[Outcome]
    │  artifact/feed entry (hatch.artifacts / hatch.feed)
    │  optionally scheduled to recur (HatchScheduledTasksActivity, native VM path)
    ▼
[Noise channel teardown]  last "hold" released → noise/closed reason=unlink
```

بشكل منفصل (ليس جزءاً من نفس الجلسة، MEX/GraphQL عادي، لا نقل موثَّق متضمِّن):

```
[Client]  GetMetaAiReminders / GetMetaAiGroupReminders
    │  whatsapp-android-www, name-based persisted query
    ▼
[WA server]  reminder list (status SCHEDULED/CLAIMED/FULFILLED)

[Client]  DeleteMetaAiReminder / DeleteMetaAiGroupReminder
    ▼
[WA server]  reminder removed
```
