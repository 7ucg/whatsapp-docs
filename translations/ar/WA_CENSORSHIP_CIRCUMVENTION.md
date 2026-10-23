<!-- src-sha1: 5428e0461d6ea8f961256e4ead0fe3df30ea4164 -->
# WhatsApp تجاوز الرقابة — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** بدائل الاتصال في Android عند حظر chatd: WhatsApp Proxy الذي يضبطه المستخدم (واجهة الإعدادات، التخزين، رابط المشاركة، الاستخدام في chatd والوسائط)، خدمة الوكيل التي يقودها الخادم (نفق Psiphon، وحدة Voltron، بوابات المنطقة وVPN، نفق SOCKS مع ترويسة PROXY v2)، قائمة IP البديلة (`<ib><fbip>`، الملف `fbips`)، دفعة إلغاء الحظر (`fbips`، `unblocking_props`، `psl`)، سلسلة DNS البديلة، مزودو مرحّل التسجيل واستراتيجيات إعادة المحاولة، دورا Tigon وDGW، تتبّع حالة الاتصال والتشخيص، تداخل إعادة المحاولة، feature flags، الآليات غير الموجودة، مقارنة مع Baileys

---

## 1. ما هو موجود في هذا الإصدار

كل العبارات مستمدة من التحليل الساكن لـ APK المفكوك؛ لم يُلتقط أي شيء على السلك. المستويات: **found** = مقروء في الشيفرة أو الموارد، **inferred** = مستنتج، **unknown** = غير محسوم. الأسماء المشوشة تخص كل إصدار على حدة وأُعيد حلّها في 2.26.41.6. نقل chatd والمصافحة وسلّم المضيفين وback-off موجودة في [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) ولا تتكرر هنا.

| الآلية | الحالة | نقاط الدخول | المستوى |
|--------|--------|-------------|---------|
| WhatsApp Proxy (مرحّل دردشة ووسائط يضبطه المستخدم) | موجود، واجهة للمستخدم، خلف feature flag | `SettingsUserProxyActivity`, `SettingsSetupUserProxyActivity`, `C12660bX`, `C12690ba`، الخطوة 12 من تسلسل chatd | found |
| خدمة الوكيل (نفق Psiphon، وحدة Voltron `proxyservice`) | موجودة، يقودها الخادم، بلا واجهة للمستخدم | `C12760bh` (المنسّق)، `C42448IfJ` / `S6G`, `ca.psiphon.PsiphonTunnel`, `ProxyServiceBroadcaster` | found؛ المكتبة الأصلية ليست في APK |
| قائمة IP البديلة | موجودة | `<ib><fbip>` في `C40581l4`, `C36821d6`، الملف `fbips` | found |
| جدول المضيف إلى IP المضمّن في الشيفرة، سلّم المضيفين | موجود | `AbstractC47101wK` (18 اسم مضيف)، `C37151de` | found |
| سلسلة DNS البديلة (المنصة / MNS، UDP إلى 8.8.8.8 و8.8.4.4 مضمّنة في الشيفرة) | موجودة | `C36881dC`, `QG1` | found |
| دفعة إلغاء الحظر (`nt` = `unblocking`) | موجودة | `CLl` (المحلّل)، `C28139CLl`, `C28912ChD`, `C27946CBo` | found |
| مرحّل التسجيل (مزودو cloud-function) واستراتيجيات إعادة المحاولة | موجود، للتسجيل فقط | `res/raw/domain_fronting_providers.tsv`, `C45421Jrl`, `RetryingHttpClient` | found |
| Tigon / DGW كبديل لـ chatd | غير موجود | إعداد DGW fallback موجود لكنه مبني معطّلاً | found |

غير موجود في هذا الإصدار (يُعدّ غيابًا في Java المفكوكة وmanifest والموارد؛ الشيفرة الأصلية لم تُفحص):

| الغائب | الدليل |
|--------|--------|
| chatd عبر WebSocket أو HTTP long-poll أو MQTT | لا حرفية `wss://` أو `/ws/chat` في Java؛ `mqtt` فقط في تسميات التحليلات وتدفقات DGW (انظر تقرير Noise القسم 13) |
| Android `VpnService` | لا خدمة ولا `BIND_VPN_SERVICE` في manifest؛ Psiphon يعمل في وضع الوكيل المحلي |
| وكيل SOCKS أو HTTP-CONNECT يضبطه المستخدم لـ chatd | الخطوة 12 تبني مقبسًا مباشرًا إلى `host:chatPort`، بلا مصافحة وكيل |
| وكيل النظام (`http.proxyHost`, `https.proxyHost`) لـ chatd | لا يقرأه التسلسل ولا شيفرة المقبس؛ يقرأه Tigon فقط وكحارس (القسم 4.6) |
| Domain fronting أو مرحّل لـ chatd | قائمة المزودين يستهلكها عميل التسجيل فقط (القسم 7) |
| Tor وSnowflake وغيرها من وسائل النقل القابلة للتوصيل | لا شيفرة ولا موارد |

نقاط تحسم بقية التقرير:

- توجد آليتا وكيل مستقلتان لا تعملان معًا: وكيل المستخدم (الخطوة 12، نهائية) وخدمة وكيل Psiphon (نفق SOCKS يحل محل الاتصالات المباشرة في مجموعة جزئية من الخطوات). عند ضبط وكيل مستخدم يُتجاهل إعداد الخدمة (`ConnectionSequence/socketConfigForUserProxy/skipping socks proxy in favor of user proxy`).
- مع وكيل مستخدم صالح يكون للتسلسل هدف واحد بالضبط. الخطوة 12 تنتقل إلى 16 (مستنفدة)؛ لا رجوع إلى المضيفين المباشرين (found، `C37031dS.A0G`).
- `libgojni.so` تُسلَّم داخل الوحدة القابلة للتنزيل. APK يحوي manifest الوحدة فقط؛ طلب النفق واختيار البروتوكول وسلوك مكافحة DPI غير معروفة.

---

## 2. الموضع في تسلسل اتصال chatd

أرقام الخطوات هي أرقام تقرير Noise القسم 2.2. المصدر: `C37031dS.A0G`, `C37151de`, `C37061dV`.

| الشرط | الأثر |
|-------|-------|
| عنوان تصحيح مضبوط | الخطوة 1 فقط |
| وكيل مستخدم صالح (مفعّل، المضيف صالح، flag **2784**) | الخطوة 0 تذهب إلى 12 وهي نهائية؛ إعداد Psiphon يُتجاهل |
| لا وكيل مستخدم، إعداد Psiphon موجود (`C37061dV.A00 != null`) | الخطوات 5 و8 و13 تبقى؛ 6 و7 و9 و10 و11 و14 و15 تُتخطى (`ConnectionThread/Skipping sequence N due to active proxy`)؛ 2 و3 و4 تُتخطى ما لم يكن flag **23630** مفعّلاً |
| لا وكيل مستخدم ولا إعداد Psiphon | السلّم دون تعديل: 2, 3, 4, 5, 8, 9, [15], 13, 14, 6, 10, 7, 11 |

جدول التخطي هو packed switch في bytecode الخاص بـ `C37031dS.A0G` (الخطوات 2 إلى 15 مرتبطة بـ إبقاء / تخطي / يعتمد على flag). الخطوة 8 تبني إعدادها من IP حرفي دون إعداد الوكيل، لذا تبقى ضمن تشغيل بوكيل نشط لكنها على الأرجح تتصل مباشرة (inferred). الخطوتان 5 و13 تحلّان عبر `C37151de.A03`: مع إعداد Psiphon ودون وكيل مستخدم يحمل إعداد المقبس المُرجَع `ProxyServiceConfig` (`C46661vS`) واسم مضيف غير محلول، فيحدث DNS عند مخرج النفق (`DNSResolutionMethod` 7 `SOCKS_PROXY`، الرمز الداخلي 8 في `C37181dh`).

ترتيب الخطوة 0 حين لا يوجد عنوان تصحيح (found؛ فرع Java المفكوك للخطوة 1 يبدو معكوسًا، وbytecode يؤكد): وكيل المستخدم، ثم إدخالات التجاوز التي يوفرها الخادم (2)، ثم سلسلة المضيف المضبوطة (3)، ثم 5.

---

## 3. WhatsApp Proxy (يضبطه المستخدم)

### 3.1 مدخل الإعدادات والشاشات (found)

| الشاشة | الصنف | المحتوى |
|--------|-------|---------|
| الإعدادات > التخزين والبيانات > Proxy | `SettingsUserProxyActivity` (manifest `com.whatsapp.settings.ui.proxy.*`، غير مصدَّر) | مفتاح `Use proxy`، سطر المضيف، صفّا حالة الدردشة والوسائط، عنصر قائمة المشاركة، نص معلومات (`Only use a proxy if you're unable to connect to WhatsApp. Your IP address may be visible to the proxy provider…`، الرابط `whatsapp-proxy`) |
| إعداد الوكيل | `SettingsSetupUserProxyActivity` | إدخال المضيف، `Ports (Optional)` مع `Chat port` (يظهر الافتراضي `Default` للمنفذ 443)، `Media port` (`Default` للمنفذ 587)، `Use TLS`، زر الحفظ |
| مدخل البحث في الإعدادات | `C23869ARc` الصنف الفرعي `C215199Jq` | المفتاح `proxy` |
| الحذف | نقرة مطوّلة على سطر المضيف (`ViewOnLongClickListenerC46012K9h`، `Delete Proxy?`)، الإجراء في `KZA` | يمسح المضيف، يعيد منفذ الوسائط 587 وTLS إلى true، الحالتان 0، `proxy_enabled` false |

التحقق: `K09.A01` (IP حرفي)، `K09.A02` (مضيف مع `:port` اختياري، regex مبني من `JRQ.A02`)؛ الأخطاء `Enter a valid host`, `Enter a valid port`. تحليل IPv6 موجود في `K09.A00`.

### 3.2 التخزين (found، `C12660bX`, `C12690ba`)

ملف SharedPreferences باسم `user_proxy_setting_pref`.

| المفتاح | النوع | الافتراضي | الاستخدام |
|---------|-------|-----------|-----------|
| `proxy_enabled` | bool | false | حالة المفتاح؛ فعّال فقط حين يكون flag **2784** مفعّلاً (`C12690ba.A03`) |
| `proxy_ip_address` | string | لا شيء | `host:chatPort` (`ProxySetting.A04`)؛ يُحلَّل المنفذ عند القراءة، الافتراضي 443 |
| `proxy_media_port` | int | 587 | منفذ مرحّل الوسائط |
| `proxy_use_tls` | bool | true | غلاف TLS لمقبس الدردشة |
| `proxy_connection_status` | int | 0 | حالة الدردشة المعروضة في الواجهة (القسم 3.5) |
| `proxy_media_connection_status` | int | 0 | حالة الوسائط المعروضة في الواجهة |

`ProxySetting` (`C45598Jv6`) = `domain`, `ip`, `chatPort`, `mediaPort`, `useChatTls`؛ المضيف الذي هو IP حرفي يذهب إلى `ip`، وإلا إلى `domain`. `C12660bX.A03()` يعيده فقط عند التفعيل وflag **2784** مفعّل والمضيف أو IP صالح؛ وهذا هو الكائن الذي يتلقاه تسلسل الاتصال.

### 3.3 رابط المشاركة والاستيراد (found)

المشاركة: عنصر القائمة يبني `https://wa.me/proxy?host=<host>&chatPort=<n>&mediaPort=<n>&chatTLS=<true|false>` بالموضوع `WhatsApp Proxy` والنص `Connect to WhatsApp using proxy. <url>`.

الاستيراد: `DeepLinkActivity` (النوع `DEEP_LINK_PROXY`، بادئة السجل `PROXY:`) يتطلب flag **2784**، وله سبب رفض `proxy_has_segments` (الشرط مستنتج من الاسم)، ثم يبدأ `SettingsSetupUserProxyActivity` مع extras `intent_host_name`, `intent_chat_port`, `intent_media_port`, `intent_use_tls`, `source=deeplink`.

| الاستعلام | التحليل | الافتراضي |
|-----------|---------|-----------|
| `host` | string | لا شيء |
| `chatPort` | int | 443 |
| `mediaPort` | int | 587 |
| `chatTLS` | الغياب أو `true` أو `1` يعطي true؛ أي قيمة أخرى false | true |

الاستيراد يملأ شاشة الإعداد مسبقًا فقط؛ الحفظ ما زال يتطلب المستخدم (found). معالج `DeepLinkActivity` قُرئ من bytecode (غير مفكوك إلى Java).

### 3.4 الاستخدام من chatd (found)

الخطوة 12 (`C37151de.A02` الحالة 12): المضيف = `domain` أو `ip`، المنفذ = `chatPort`، بت TLS = `useChatTls`. يمر المضيف عبر سلسلة المحلّلات العادية (القسم 6). ثم تعمل مصافحة Noise فوق هذا المقبس (داخل TLS عند `useChatTls`). حفظ الوكيل أو تبديل المفتاح يستدعي `C11380Yq.A0C(...)` (إعادة اتصال قسرية) ويُطلق `wam_user_proxy_set`.

ما يفعله مضيف الوكيل بالتدفق غير مرئي من جهة العميل. كون مرحّل WhatsApp Proxy يمرّر بايتات chatd الخام مستنتج (inferred) من غياب أي تبادل SOCKS أو CONNECT.

### 3.5 مستهلكون آخرون (found)

| المستهلك | السلوك |
|----------|--------|
| رفع / تنزيل الوسائط | flag **4073** يجعل سلطة الوسائط `proxy-host:mediaPort`؛ فحص الصحة في [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| مسارات رفع WAM | callback الأصلي `jnidispatchO(0)` يعيد `https://<proxy-host>:<mediaPort>/deidentified_telemetry` حين يكون flag **4074** مفعّلاً، إضافة إلى مضيفي `media_conn` حين يكون flag **4020** مفعّلاً (انظر [WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)) |
| واجهة الحالة | `C42103IXl.A00`: 1 `Connecting…`، 2 `Connected`، 3 `Couldn't connect to proxy`، 4 `Disconnected`، 5 `No network`، غير ذلك `Not Set`؛ حالة الدردشة تغذيها مراقبة الاتصال `C28890Cgr` |
| مسارات Psiphon HTTP وTigon | تُعطَّل ما دام وكيل المستخدم موجودًا (`C17420jn.A01`, `C12790bk`: `User proxy is set, skipping`) |
| القياس عن بُعد | `WamUserProxySet {connectionSuccess, proxySet}` (`C43286IuN`) يُرسل حين تصبح الحالة 2 (true) أو 3 / 4 (false) وعند تغيّر الوكيل |

---

## 4. خدمة الوكيل (Psiphon)

### 4.1 الوحدة والمكتبة (found)

| العنصر | القيمة |
|--------|--------|
| التسليم | وحدة Voltron `proxyservice` مع تقسيمات لكل ABI `proxyservice.config.{arm64_v8a,armeabi_v7a,x86,x86_64}` في `assets/app_modules.json`؛ manifest الوحدة يسرد `assets/proxyservice/libs.txt` و`assets/proxyservice/voltron_meta_embedded_server_entries` و`lib/<abi>/libgojni.so` لكل تقسيم |
| جانب Java | `ca.psiphon.PsiphonTunnel` (مكتبة المنبع، `loadLibrary("gojni")`, `Psi.start`, `importPushPayload`)، الخدمة المضيفة `S6G` / `C42448IfJ`، المنسّق `C12760bh`، محمّل الوحدة `C46743KbZ` |
| الوضع | وكيل HTTP وSOCKS محلي على `localhost`؛ بلا `VpnService` |
| تحميل المكتبة | مكتبات APK المقسّمة تُضاف إلى مصادر SoLoader (`proxy_service/Added module SoSource`)؛ نص السجل يسمّي `libproxyservice.so` رغم أن manifest الوحدة فيه `libgojni.so` فقط |

`libgojni.so` غير موجودة في APK (تُسلَّم مع الوحدة). بنيتها الداخلية (مجموعة البروتوكولات، الطلب، كيفية استخدام `AdditionalParameters`) غير معروفة.

### 4.2 مورد الإعداد `res/raw/proxyservice_config.json` (found)

دون تغيير منذ 2.26.34.4. يقرؤه `C42448IfJ.getPsiphonConfig`؛ عنصر نائب تنسيق `ClientVersion` يُملأ بـ versionCode للتطبيق (`264100600`).

| الحقل | القيمة / الاستخدام |
|-------|--------------------|
| `SponsorId`, `PropagationChannelId`, `ClientPlatform` | معرّفات سداسية عشرية معتمة من 16 خانة؛ المنصة `meta` |
| `ServerEntrySignaturePublicKey`, `PushPayloadSignaturePublicKey`, `RemoteServerListSignaturePublicKey` | مفاتيح base64 بحجم 32 بايت و32 بايت و548 بايت (بحجم RSA)؛ دور التحقق مستنتج من الأسماء |
| `AdditionalParameters` | 5300 محرف base64 (3975 بايت)، معتم، غير مفكوك |
| `Emit*` (عنوان العميل، إشعارات التشخيص، معاملات الشبكة)، `DisableServerEntriesReporter` | كلها true؛ تغذي `onClientAddress`, `onDiagnosticMessage` |
| `ConnectionWorkerPoolSize`, `EstablishTunnelTimeoutSeconds` | 30، 0 |
| `TransformHostNameProbability`, `TLSFragmentClientHelloProbability` | 0.9، 0.5 (مقابض مكافحة DPI للمحرك الأصلي؛ الأثر مستنتج من الأسماء) |
| `EnableLightProxy`, `LightProxyLimitDestinationAddresses` | true؛ `g.whatsapp.net` و`g-fallback.whatsapp.net` على المنافذ 80 و443 و5222 |

تغييرات وقت التشغيل: كائن JSON من flag **23879** (مصدر flag قبل تسجيل الدخول) أو **23846** (المصدر العادي) يُدمج مفتاحًا مفتاحًا فوق الملف. وضع استيراد PSL (`C42448IfJ.A03`) يفرض `DisableTunnels=true` و`EnableLightProxy=false`. تُقرأ إدخالات الخادم المضمّنة من `assets/proxyservice/voltron_meta_embedded_server_entries` (أو من zip الوحدة) حين يكون flag **23730** / **23731** مفعّلاً؛ التنسيق: عدد int32 بترتيب big-endian، ثم عدد مرات (طول int32، بايتات)، كل إدخال مرمّز سداسيًا عشريًا، واحد في كل سطر (`C45480Jst.A01`).

يُختار مصدرا flag بواسطة `C17280jY.A00`: عدم وجود حساب مسجَّل الدخول، أو عدم تحديث AB props قط، يختار المجموعة السابقة لتسجيل الدخول. لذا صُممت الخدمة لتعمل قبل التسجيل أيضًا (inferred من الشرط).

### 4.3 آلة الحالات (found، `AbstractC17380jj`, `C12760bh.A0B`)

| الرمز | الحالة | تُضبط عندما |
|-------|--------|-------------|
| 0 / 1 / 2 | `uninitialized` / `not_in_region_allowlist` / `initializing` | ابتدائية / رُفضت المنطقة (السبب يحمل المنطقة) / قُبل البدء |
| 3 / 4 | `disabled` / `downloading_module` | بوابة مثل `vpn_in_use` / تنزيل Voltron جارٍ |
| 5 / 6 / 7 | `connecting` / `connected` / `disconnected` | `onConnecting` / `BmZ` (المنافذ جاهزة) / `BpU` |
| 8 / 9 | `download_failed` / `library_load_failed` | فشل تثبيت الوحدة / `UnsatisfiedLinkError` |
| 10 | `shutdown` | `A04(reason)`، مثل `country_check`, `has_external_connectivity` |

حين تكون الحالة 2 أو 4 أو 5 تنتظر حزمة HTTP الوكيل: `C17420jn.A05(true)` يسلّح latch مهلته flag **29362** (ms، الافتراضي 0، فقط عند تسجيل الدخول).

### 4.4 مشغّلات البدء والإيقاف (found)

| المشغّل | المسار |
|---------|--------|
| البدء البارد لمعالج الرسائل | الحالة الافتراضية في `C1W6` تستدعي `C12760bh.A03(…, null)` |
| استئناف التطبيق | `C18980me` و`C28912ChD` يستدعيان `A0A()` (إعادة إشعار النفق، أو إعادة التشغيل إن كان متوقفًا) |
| دفعة إلغاء الحظر مع `psl` | `C28912ChD.BIb`: `A03(…, C46772Kc2(psl))`؛ بدون `psl`، فقط `A0A()` عند `C17280jY.A02()` (flags **28186** / **28189**) |

بوابات البدء في `A03`:

1. منطقة الجهاز = بلد SIM، وإلا بلد الشبكة، وإلا بلد locale (`AbstractC16510i9`)؛ يجب أن تكون ضمن القائمة المفصولة بفواصل بأحرف صغيرة من flag **18724** (قبل تسجيل الدخول) / **18725** (`C17280jY.A03`). وإلا الحالة 1.
2. فحص VPN (`C17280jY.A01`، flags **24068** / **24067** تتجاوزه): VPN نشط يعطي `vpn_in_use`، الحالة 3.
3. flag **25452** يحدد الترتيب: مفعّل، تعمل بوابة VPN والمسبار بعد تنزيل الوحدة؛ معطّل، قبله.
4. المسبار (flag **18875**، `Q53`): HTTP GET للعنوان في flag **18871** (المهلة **18874**، المحاولات **18873**، التأخير **18872**) عبر الحزمة العادية. أي استجابة HTTP تُعدّ نجاحًا (`KUI.CF3`): `Probe succeeded. Removing proxy from http and tigon`، يُضبط `A0N` (اتصال خارجي)، يُمسح الوكيل من HTTP وTigon، ويعمل فحص الإيقاف.
5. مهلة علامة البدء: flag **25850** ثانية (التعليق التوضيحي `init_timed_out`).

شروط الإيقاف:

| الشرط | النتيجة |
|-------|---------|
| منطقة العميل التي أبلغ عنها Psiphon غير مسموحة (flag **19067** مفعّل) | `country_check`، إيقاف |
| نجح المسبار (`A0N`) وأُبلغ عن جلسة chatd مباشرة جيدة (`A0O`)، flag **19613** مفعّل | `has_external_connectivity`، إيقاف |
| جلسة chatd مباشرة جيدة (`HandlerThreadC12340b0.A0e`: الخدمة نشطة، الجلسة أطول من flag **19372** (الافتراضي 5، الوحدة غير محسومة)، المسار ليس `SOCKS_PROXY`) | `C12760bh.A09()` مع `C37061dV.A00()`: تُتجاهل خدمة الوكيل طوال عمر العملية (`good_direct_chatd_session`) |
| flag **19144** سالب عند البدء | يُتجاهل طوال عمر العملية (`abprop_config`) |

### 4.5 التكامل مع chatd (found)

`C37061dV` (`ConnectionProxyConfig`) يحوّل حالة broadcaster إلى `ProxyServiceConfig` الذي يستخدمه التسلسل.

| الحقل | المصدر |
|-------|--------|
| `address` | `localhost` حين يكون النفق الثقيل أو الوكيل الخفيف قائمًا، وإلا فارغ |
| `port` | منفذ SOCKS (`ProxyServiceBroadcaster.A01(true)`: الثقيل، أو الخفيف عند السماح) |
| `proxyServiceClientIP` | `onClientAddress` |
| `httpProxyHost`, `httpProxyPort` | `localhost` ومنفذ HTTP حين لا يكون صفرًا |
| `isLightProxy` | `isLightProxy()` (الوكيل الخفيف قائم، النفق الثقيل غير متصل) |

القواعد:

- يُسقَط الإعداد حين يكون العنوان أو المنفذ فارغًا (`updateProxyServiceConfig`)، أو حين تكون المنطقة التي أبلغ عنها Psiphon غير مسموحة (`dropping due to unsupported client region`).
- `C37061dV.A02` (يُستدعى عند كل بدء اتصال) يعيد الإعداد فقط حين تكون منطقة الجهاز مسموحة، ولا VPN نشط، والخدمة غير متوقفة، وتجاهل عمر العملية غير مضبوط. حين يكون flag **24645** مفعّلاً يُستخدم الإعداد المخزَّن مؤقتًا دون هذه الفحوص.
- قد يُحجب خيط الاتصال لمدة flag **19144** ms (`awaitProxyServiceConfig`) في انتظار الإعداد قبل الخطوة 5 حين لا يوجد إعداد بعد.
- الإعداد المتغيّر يضبط علَم إعادة الضبط، وحين يكون flag **36306** مفعّلاً تُعاد الاتصال بالسبب `proxy_service_update`.

المقبس (فرع else في `C37031dS.A01`، الصنف `C48201yM` = `ConnectionSocketTunnel`):

```java
Socket s = new Socket(new Proxy(Proxy.Type.SOCKS, new InetSocketAddress(cfg.address, cfg.port)));
s.connect(InetSocketAddress.createUnresolved(host, port), 30000);   // g.whatsapp.net / g-fallback.whatsapp.net
c37861f7.A00(out, cfg.proxyServiceClientIP, port);                    // PROXY v2 header, skipped when flag 26334 is on
```

ترويسة PROXY v2 (`C37861f7`، السجل `ProxyHeaderWriter`): توقيع من 12 بايت `0D 0A 0D 0A 00 0D 0A 51 55 49 54 0A`، ثم `21`، العائلة `11` (IPv4) أو `21` (IPv6)، طول 16 بت، عنوان المصدر (IP العميل، وعنوان صفري حين لا يُحلَّل)، عنوان وجهة صفري، منفذ المصدر 0، منفذ الوجهة = منفذ الهدف، ثم TLV واحد `E8 00 01 50`. معنى TLV غير معروف. كون الحافة (edge) تقبل الترويسة أو تشترطها مستنتج (inferred) من وجودها فقط.

سجلات توقيت الاتصال لكل محاولة تستخدم المراحل `DNS` و`SOCKET` و`TLS` والحزم `PLATFORM` و`MNS` و`SOCKS_PROXY` (`C37811f2`, `EnumC37801f1`, `EnumC37821f3`).

### 4.6 مستهلكون آخرون للوكيل المحلي (found)

| المستهلك | الصنف | السلوك |
|----------|-------|--------|
| حزمة WA HTTP | `C17420jn` (`WaHttpUrlConnectionWithProxyService`) | `Proxy(HTTP, localhost:httpPort)`؛ للمضيفين المنتهين بـ `.whatsapp.net` و`.whatsapp.com` و`.fbcdn.net` و`.facebook.com` و`.instagram.com` و`.cdninstagram.com` و`.fbsbx.com` يضيف `X-Forwarded-For: <client IP>` و`using-wa-proxy-service: 1` |
| عملاء Tigon (MNS) | `C12790bk` (`WATigonProxyObserver`) | `setInAppProxyHostAndPort`؛ يُتخطى حين تكون flags **26734** / **26735** (Tigon) أو **19905** / **19906** (WA proxy) مفعّلة، أو يوجد وكيل مستخدم، أو `http.proxyHost` / `https.proxyHost` مضبوط، أو نجح المسبار سلفًا |
| VoIP | `CQO`, `JNIUtils.socksProxyPort` | `Voip.updateProxy(socksPort)` حين يسمح flag **34525** (بوابة ثانية **36980** في `Buh()`) |
| WebView | `C39826HXw` | قاعدة `PROXY_OVERRIDE` للنطاقات في flag **25539** |
| سجل معلومات الشبكة | `C12500bH` | `network_info_socks_proxy_active[...]`, `socks_proxy_connected` / `socks_proxy_disconnected` |

يقرأ Tigon أيضًا خصائص وكيل النظام بنفسه (`TigonHttpClientBase.setSystemProxyHostAndPort`) مع مفتاح رجوع إلى الاتصال المباشر؛ وهذا مستقل عن الخدمة.

### 4.7 التشخيص (found)

`C42448IfJ.onDiagnosticMessage` يحلّل `ConnectedServer:{json}` إلى `candidate_number` و`protocol` و`client_replay_type` (`bootstrap`, `replay`, `non-replay`) و`server_entry_source`. العلامات 79499422 (البدء)، 79496324 (الاتصال)، 79501264 (المسبار، مع التعليقين `has_vpn` و`has_system_http_proxy`).

---

## 5. نقاط النهاية البديلة ودفعة إلغاء الحظر

### 5.1 `<ib><fbip>` (found، `C40581l4`, `C36821d6.A02`)

`<ib><fbip>text</fbip></ib>`: يُقسَّم النص على `,`. إدخال واحد `CLEAR` يحذف الملف. كل إدخال ستة حقول مفصولة بـ `|`:

```
ip|port|ts|ttl|secure|override       exp = (ts + ttl) * 1000
```

| الحقل | الاستخدام |
|-------|-----------|
| `ip`, `port` | نقطة النهاية؛ رمز المحلّل 4 (`FALLBACK`) |
| `ts`, `ttl` | الانتهاء بـ ms؛ تُزال الإدخالات المنتهية عند التحميل |
| `secure` | بت غلاف TLS لنقطة النهاية |
| `override` | الإدخالات true تذهب إلى الخطوة 2 (تُجرَّب قبل `g.whatsapp.net`)، وfalse إلى الخطوة 8 (بعد `:80`) |

الاستمرارية: الملف `fbips` في مجلد ملفات التطبيق، JSON `{"fbips":[{"ip","port","exp","secure","override","resolver"}]}` (`C36821d6.A00`). تُبلَّغ أخطاء التحميل بصيغة `fallback-manager/load-error` و`save-error`.

### 5.2 الجدول المضمّن في الشيفرة (found)

`AbstractC47101wK`: 18 اسم مضيف (`e1` إلى `e16`، `g`، `v` تحت `.whatsapp.net`، بصيغتي العادية ومع النقطة الأخيرة)، لكل منها عدة عناوين IPv4. تستخدمه الخطوتان 6 / 10 والمحلّل المضمّن. إدخال `v.whatsapp.net` لا يستخدمه أي محلّل في هذا الإصدار (الـ stub الخاص بمحلّله يعيد null).

### 5.3 دفعة إلغاء الحظر (found)

تحليل الدفعة (`CLl`، `PushPayloadParser/fromJSON`): قيم `nt` هي `pre_reg` و`post_reg` و`voip_call_offer_1on1` و`voip_call_offer_group` و`call_terminate` و`message` و`group_message` و`wfac_ban` و`unblocking`. وسائل النقل المسجَّلة: `ADM` و`GCM` و`FBNS`. يُفك تشفير الحمولة (`PushEncryptionHelper`، الحقول `payload` و`IV` و`tag`، المفتاح من `push:push_pkey_data`؛ الشفرة AES-GCM مستنتجة من أسماء الحقول).

`nt` = `unblocking` يحمل (`UnblockingPushPayload`, `BQY`):

| مفتاح JSON | الحقل | المعالجة |
|------------|-------|----------|
| `fbips` | `fbips` | يُقسَّم على `,`، ويُمرَّر إلى `C36821d6.A02` (التنسيق نفسه كما في 5.1) |
| `unblocking_props` | `unblockingProps` | `version\|a\|b`؛ النسخة الأعلى من 0 تُتجاهل؛ خريطتان `id=value;id=value` يحلّلهما `C27946CBo.A00`؛ `processPreChatdProps` يطبّق أزواج `config_code` / `config_value`، و`processPostChatdProps` الخريطة الثانية (إسناد الخرائط إلى المراحل مستنتج جزئيًا) |
| `psl` | `proxyServerList` | base64، يُستورد إلى Psiphon بـ `importPushPayload` (`C46772Kc2`) |

استيراد `psl`: النفق نشط، يُستورد مباشرة؛ النفق غير نشط، يبدأ كائن نفق مؤقت في وضع استيراد PSL (`DisableTunnels`)، يستورد، ويتوقف (`Cold-importing push payload`). يُتخطى حين تكون الحالة `not_in_region_allowlist`. توسيع PSL على أنه "push server list" مستنتج (inferred) من المفتاح ومن الحقل `PushPayloadSignaturePublicKey`.

---

## 6. سلسلة DNS البديلة (found)

`C36881dC.A03` يستشير أولاً ذاكرة مؤقتة (تغذيها `fbips`، بإدخالات لها انتهاء؛ تحكمها flag)، ثم يمر على أربعة محلّلات بالترتيب:

| # | المحلّل | رمز المحلّل | ملاحظات |
|---|---------|-------------|---------|
| 0 | stub لـ `v.whatsapp.net` | لا شيء | يعيد null |
| 1 | DNS المنصة / MNS (`DnsCache/resolveViaMnsDns`) | 5 / 6 / 7 | يعيد المحاولة مرة (`primary dns resolver failed, retrying...`) |
| 2 | الثانوي: DNS عبر UDP مبني يدويًا إلى 8.8.8.8 و8.8.4.4 المنفذ 53 (`QG1`) | 1 `GOOGLE` | UDP صريح، لا DoH ولا DoT |
| 3 | الجدول المضمّن في الشيفرة | 2 `HARDCODED` | `no hardcoded ips found for <host>` عند الغياب |

flag **13545** (string) يقنّع المحلّلات: `secondary` يعطّل المضمّن، `hardcoded` يعطّل محلّل UDP، `none` يعطّلهما معًا (منطق البتات في `C37151de.A01`). أخطاء `EPERM` يُعاد رميها حين يكون مفتاح يتحكم به flag مضبوطًا. رموز المحلّلات تصل إلى `ClientPayload.dnsSource` (تقرير Noise القسم 6.5).

---

## 7. مرحّل التسجيل (found)

النطاق: HTTP التسجيل (`RegistrationHttpManager` = `K49`, `KotlinRegistrationBridge`, `RetryingHttpClient`) إلى `https://v.whatsapp.net`. لا يمس chatd.

### 7.1 قائمة المزودين

المورد `res/raw/domain_fronting_providers.tsv`، الأعمدة `name` و`url template` و`host`:

| الاسم | القالب | المضيف |
|-------|--------|--------|
| `amazon` | `https://y9yrsygcg6.execute-api.us-east-1.amazonaws.com/s/s?_={PATH}&{QS}` | `y9yrsygcg6.execute-api.us-east-1.amazonaws.com` |
| `google` | `https://us-central1-propane-fusion-170222.cloudfunctions.net/s?_={PATH}&{QS}` | `us-central1-propane-fusion-170222.cloudfunctions.net` |

`C45421Jrl` يحمّلها (الأسطر التي فيها أقل من 3 رموز تسجّل `domain-fronting-providers/load/bad-line`) ويحتفظ بثلاث قوائم: قابلة للوصول (`A05`)، غير مختبرة (`A06`)، غير قابلة للوصول (`A04`). `K49.A0K` يمررها إلى كل نداء تسجيل بهذا الترتيب.

### 7.2 المسبار

`EULA.onCreate` يبدأ المسبار مرة كل 900000 ms على الأكثر (يُتخطى حين `C06810Gk(930).A07()`، المعنى غير محسوم): يفتح `https://v.whatsapp.net`؛ عند `IOException` (`DomainFrontingManager/probe-regd/cant connect to regd`) يخلط المزودين ويرسل GET لكل قالب مع `{PATH}=/` و`{QS}` فارغ، مهلة اتصال وقراءة 60 ثانية، الترويسات `Host` = مضيف المزود وuser agent التطبيق. HTTP 200 ينقل المزود إلى قائمة القابلين للوصول، وأي فشل إلى قائمة غير القابلين للوصول (`domainFrontingProvider/cant reach`).

### 7.3 استراتيجيات المحاولة (`RetryingHttpClient`, `C44407JaE`, `C44975Jk4`)

| الاستراتيجية | الطلب | الحالة في 2.26.41.6 |
|--------------|-------|----------------------|
| `ORIGINAL` | العنوان العادي | دائمًا المحاولة 1 |
| `HOST` | العنوان نفسه مع IP معطى | القائمة فارغة في هذا الإصدار |
| `PROXY` | عبر IP وكيل معطى | القائمة فارغة في هذا الإصدار |
| `DOMAIN_FRONTING` | القالب مع استبدال `{PATH}` و`{QS}` بالمسار الأصلي والاستعلام الخام؛ الترويسات `Host` = مضيف المزود، `X-Forwarded-Host` = المضيف الأصلي | حتى حدود قائمة المزودين |

الترتيب: ORIGINAL، إدخالات HOST، إدخالات PROXY، المزودون؛ 4 محاولات على الأكثر. مضيف URL وترويسة `Host` متساويان في القالبين، لذا هو مرحّل cloud-function (يعيد المزود توجيه الطلب إلى `X-Forwarded-Host`، inferred) لا SNI / Host fronting الكلاسيكي.

قاعدة إعادة المحاولة: رموز النتيجة 2 و5 و7 و12 غير قابلة لإعادة المحاولة (`non-retryable error`)، وكل فشل آخر يستمر (`failed attempt N ... reason`)؛ معاني الرموز غير محسومة. التأخير قبل المحاولة `n` > 1:

```
delay = clamp(r * (n*n - 1) * 4 * 1000, 0, 60000) ms      // r from a random double, assumed uniform in [0,1)
```

`RetryingHttpClient/executePostWithRetry/applying backoff`, `all retries exhausted`. flags حمولة إثبات نقطة النهاية لكل مسار موجودة في `AbstractC44143JQf` ولا علاقة لها بالترحيل.

---

## 8. Tigon وDGW

| العنصر | الحالة | المستوى |
|--------|--------|---------|
| Tigon HTTP (`TigonHttpClient`، عملاء MNS) | عميل HTTP(S)؛ يأخذ وكيل Psiphon HTTP وخصائص وكيل النظام (القسم 4.6)؛ ليس وسيلة نقل لـ chatd | found |
| عميل DGW (`AbstractC20460pC`) | مبني بالنطاق `gateway.facebook.com`، إعداد fallback `null`، إعداد personalization `null` | found |
| `DGWFallbackConfig` | `isFallbackEnabled`, `fallbackDomain`, `numFailuresForFallback`, `fallbackReasons`, `isHardcodedIpFallbackEnabled`؛ null يعطي كل شيء معطّلاً؛ باني Java لا يفعّله أبدًا، والافتراضات الأصلية غير معروفة | found / unknown |
| مستخدمو DGW | `WaFalcoStreamingRegistration` (بث القياس عن بُعد) فقط؛ انظر تقرير Noise القسم 13 | found |

السلاسل الأصلية (`distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`، وتسميات throttling وzero-rating) تصف دواخل DGW. لا شيء يربط DGW بالتعافي من chatd المحظور (inferred من الغياب).

---

## 9. تتبّع حالة الاتصال والتشخيص

| العنصر | الموضع | المحتوى |
|--------|--------|---------|
| استمرارية التسلسل | prefs `connection_sequence_state`, `connection_sequence_attempts`, `last_successful_connection_step`, `_host`, `_port` | نقطة الاستئناف، خطوة HISTORY (تقرير Noise 2.2) |
| سجلات كل محاولة | `C37811f2` | المرحلة `DNS` / `SOCKET` / `TLS`، الحزمة `PLATFORM` / `MNS` / `SOCKS_PROXY`، التوقيت، الخطأ |
| الحمولة | `ClientPayload.dnsSource`, `connectAttemptCount` | المحلّل أو المسار الذي أنتج المقبس |
| خدمة الوكيل | `C12760bh.A06()`, `A08()` | رمز الحالة (4.3)؛ `A08()` يعيد `both` أو `heavy` أو `light` أو null |
| وكيل المستخدم | حالات `user_proxy_setting_pref`, `wam_user_proxy_set` | الواجهة والتحليلات |
| سجل معلومات الشبكة | `C12500bH` | `network_info_is_vpn`, `_is_airplane`, `_is_data_saver`, `_is_cellular_enabled`, `_socks_proxy_active`, `socks_proxy_connected` / `_disconnected` |
| وسوم السجل | `proxy_service/`, `ConnectionProxyConfig/`, `WaConnectivityProber/`, `WATigonProxyObserver/`, `ConnectionThread/Skipping sequence` | البوابات وتغيّرات الحالة |

---

## 10. تداخل إعادة المحاولة وback-off

الـ back-off نفسه (وحدات Fibonacci، سقف 15 دقيقة، alarms) في تقرير Noise القسم 10. تضيف هذه الميزة:

| التفاعل | الأثر |
|---------|-------|
| حفظ وكيل المستخدم أو تبديله أو حذفه | إعادة اتصال قسرية (`C11380Yq.A0C(...)`) |
| تغيّر إعداد خدمة الوكيل | إعادة ضبط التسلسل؛ إعادة اتصال `proxy_service_update` حين يكون flag **36306** مفعّلاً |
| ضبط وكيل المستخدم | تسلسل بخطوة واحدة؛ كل محاولة فاشلة تعود إلى back-off الاتصال الكامل |
| انتظار الإعداد / انتظار HTTP | خيط الاتصال يُحجب حتى flag **19144** ms قبل الخطوة 5؛ حزمة HTTP حتى flag **29362** ms أثناء بدء الخدمة |
| التسجيل | حد خاص من 4 محاولات وتأخير تربيعي (القسم 7.3)، غير مشترك مع chatd |

---

## 11. Feature flags (المعرّفات كما قُرئت في الشيفرة؛ القيم من جهة الخادم)

| المعرّف | النوع | يتحكم في |
|---------|-------|----------|
| **2784** | bool | ميزة وكيل المستخدم (حالة التفعيل، deep link) |
| **4020**, **4073**, **4074** | bool | مضيفو media_conn إلى الأصلي؛ الوسائط عبر وكيل المستخدم؛ مسار القياس عن بُعد عبر وكيل المستخدم |
| **18875** | bool | مسبار الاتصال |
| **18871**-**18874** | string, ints | عنوان المسبار، التأخير، المحاولات، المهلة |
| **18724**, **18725** | string | المناطق المسموحة (قبل تسجيل الدخول / المصدر العادي) |
| **19067** | bool | إعادة فحص المنطقة عند الاتصال |
| **19613** | bool | الإيقاف عند الاتصال الخارجي |
| **19144** | int | انتظار الإعداد ms؛ السالب يتجاهل الخدمة للعملية |
| **19372** | int | عتبة الجلسة الجيدة (الافتراضي 5) |
| **19905**, **19906**, **26734**, **26735** | bool | تعطيل WA proxy لـ HTTP / Tigon (قبل تسجيل الدخول / العادي) |
| **23630** | bool | السماح بالخطوات 2-4 تحت الوكيل (مصرَّح مفعّلاً افتراضيًا، inferred) |
| **23730**, **23731** | bool | إدخالات الخادم المضمّنة (قبل تسجيل الدخول / العادي) |
| **23846**, **23879** | JSON | تجاوز إعداد Psiphon (العادي / قبل تسجيل الدخول) |
| **24067**, **24068** | bool | السماح بالخدمة أثناء نشاط VPN |
| **24645** | bool | استخدام إعداد الخدمة المخزَّن مؤقتًا دون بوابات |
| **25452** | bool | ترتيب بوابة VPN والمسبار نسبة إلى تنزيل الوحدة |
| **25539** | string | قائمة النطاقات المسموحة لوكيل WebView |
| **25850** | int | مهلة علامة البدء بالثواني |
| **26334** | bool | تخطي ترويسة PROXY v2 |
| **28186**, **28189** | bool | استئناف الخدمة عند push بدون `psl` |
| **29362** | int | انتظار HTTP للوكيل ms |
| **34525**, **36980** | bool | تمرير منفذ SOCKS إلى VoIP |
| **36306** | bool | إعادة الاتصال عند تحديث خدمة الوكيل |
| **13545** | string | قناع محلّل DNS |

flags سلّم chatd وkeepalive (**20801**, **22916**, **30712**, **33512**, **7831**-**7834**, **15103**) في تقرير Noise القسم 12.

---

## 12. Baileys (`baron-baileys-v2`، مفحوص مقابل مصدره)

| الجانب | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| النقل | `ws` WebSocket إلى `wss://web.whatsapp.com/ws/chat` (`waWebSocketUrl`) | TCP Noise خام |
| الوكيل | `config.agent` يُمرَّر إلى `new WebSocket(url, { agent })`؛ الرفع يستخدم `fetchAgent` | مرحّل WhatsApp Proxy، نفق Psiphon |
| المضيفون البديلون | عنوان واحد قابل للضبط | سلّم `g` و`g-fallback` و`eN`، المنافذ 443 / 5222 / 80 |
| `<ib><fbip>`، دفعة إلغاء الحظر | غير معالَج | معالَج |

```ts
const sock = makeWASocket({ agent: new SocksProxyAgent(proxyUrl), fetchAgent: new SocksProxyAgent(proxyUrl) })
```

| سبب الفشل | السبب | الحل |
|-----------|-------|------|
| مضيف WhatsApp Proxy الخاص بـ Android يرفض Baileys | المرحّل يتحدث TCP Noise خامًا على منفذ الدردشة (inferred)؛ Baileys يرسل ترقية WebSocket | استخدم وكيل HTTP أو SOCKS يصل إلى `web.whatsapp.com` |
| لا تعافٍ بعد الحظر | لا معالجة لـ `fbip`، لا قناة push | وفّر `agent` أو عنوانًا جديدًا |

---

## 13. حالات الخطأ

| العَرَض | السبب | الحل |
|---------|-------|------|
| `Couldn't connect to proxy` | مضيف وكيل المستخدم غير قابل للوصول أو إعداد TLS خاطئ | تحقق من المضيف و`Chat port` و`Use TLS`؛ التسلسل بلا رجوع مباشر |
| `Enter a valid host` / `Enter a valid port` | التحقق في `K09` | صحّح الإدخال |
| رابط الوكيل لا يفعل شيئًا | flag **2784** معطّل، أو مقاطع مسار إضافية (`proxy_has_segments`) | لا شيء من جهة العميل |
| `proxy_service/Proxy service detected user region not in region allowlist.` | المنطقة التي أبلغ عنها Psiphon رُفضت بقائمة flag **18724** / **18725** | لا شيء من جهة العميل |
| الحالة `disabled`، السبب `vpn_in_use` | VPN نشط، flags **24067** / **24068** معطّلة | عطّل VPN أو flag |
| `RetryingHttpClient/executePostWithRetry/all retries exhausted` | فشلت كل المحاولات | انتظر؛ الحد 4 |

---

## 14. فروق أساسية

| لا تخلط بين | التفصيل |
|-------------|---------|
| وكيل المستخدم وخدمة الوكيل | وكيل المستخدم = مضيف مختار، الخطوة 12، نهائي، رابط مشاركة؛ خدمة الوكيل = نفق Psiphon SOCKS يقوده الخادم للخطوتين 5 و13؛ يستبعد أحدهما الآخر |
| `C48201yM` والخطوة 12 | `C48201yM` هو مقبس نفق SOCKS لخدمة الوكيل؛ الخطوة 12 هي وكيل المستخدم وتستخدم مقبسًا عاديًا أو TLS |
| الوكيل الخفيف والنفق الثقيل | الوكيل الخفيف محصور في وجهات `g` / `g-fallback` الست المسرودة؛ النفق الثقيل هو جلسة Psiphon الكاملة |
| `fbip` مقابل دفعة `fbips` مقابل `fallback_*` | `<ib><fbip>` ودفعة `fbips` يعطيان عناوين IP بديلة لـ chatd؛ `fallback_hostname` / `fallback_ip*` سمات `media_conn` (تقرير Noise القسم 16) |
| مرحّل التسجيل وchatd | قائمة المزودين لا تغذي تسلسل الدردشة أبدًا |
| WhatsApp Proxy ووكيل النظام | وكيل النظام لا يُقرأ من أجل chatd |

---

## 15. التدفق الكامل

```
[Operator]  push nt=unblocking {fbips, unblocking_props, psl}   or   <ib><fbip>...</fbip></ib>
     │  fbips file updated ; props applied ; psl imported (temporary tunnel if inactive)
     ▼
[Client]  C12760bh gates: region (SIM > network > locale), no VPN, flags ; Voltron proxyservice download
     │  PsiphonTunnel.startTunneling(embedded entries) ─► localhost SOCKS + HTTP ports ─► state 6
     ▼
[ProxyServiceBroadcaster]  C37061dV builds ProxyServiceConfig ─► sequence reset ("proxy_service_update")
     │
     ├── user proxy set ─► step 12 only: host:chatPort (+TLS) ─► Noise ─► end (no direct fallback)
     ▼
[ConnectionThread]  steps 5, 13 (2-4 if flag 23630) ─► SOCKS CONNECT g / g-fallback (unresolved host)
     │  PROXY v2 header (client IP) ─► Noise handshake (Noise report section 4)
     ▼
[Server]  login success; session > threshold and route != SOCKS_PROXY ─► proxy ignored for the process
     ▼
[Failure]  timeout / socket error ─► next step ─► exhausted ─► Fibonacci backoff (Noise report section 10)

[Registration]  v.whatsapp.net ─► ORIGINAL ─► relay providers (Host + X-Forwarded-Host) ─► <= 4 attempts
```

---

## 16. المجهولات

| العنصر | الحالة |
|--------|--------|
| أي سلوك على السلك (النفق، قبول PROXY v2، استجابة المرحّل، تمرير WhatsApp Proxy) | لم يُلتقط شيء؛ لا عنصر `tested` |
| دواخل `libgojni.so`، البروتوكولات، `AdditionalParameters`، محتوى الإدخالات المضمّنة | الوحدة الأصلية ليست في APK |
| محتوى قائمة المناطق المسموحة، عنوان المسبار، كل قيم flags | من جهة الخادم |
| معنى TLV `E8 00 01 50` في ترويسة PROXY v2 | unknown |
| إسناد خريطتَي `unblocking_props` إلى مرحلتي ما قبل chatd وما بعده، شفرة push | مستنتج جزئيًا |
| وحدة flag **19372**، معاني الرموز في إعادة محاولة التسجيل (2 و5 و7 و12)، سلوك الشرط خلف `C06810Gk(930).A07()` | غير محسوم |
| توجيه `wa.me/proxy` الوارد قبل `DeepLinkActivity` (مرشحات manifest تغطي `wa.me`) | لم يُتتبع ما بعد النشاط |
| هل يبقى إعداد DGW fallback في جانب Java معطّلاً في الأصلي، وأي بديل أصلي فقط | unknown |
| سلوك إدخالات الخطوة 8 ضمن تشغيل نشط لـ Psiphon | مستنتج: مباشر |
