<!-- src-sha1: a10cc235881df66d01adf85a7dcdb73c2853c297 -->
---
hide:
  - navigation
  - toc
---

# WhatsApp Docs

توثيق مُستخرَج بالهندسة العكسية لآليات **WhatsApp Android** الداخلية. تحليل ساكن لملف APK، دون اعتراض حركة الشبكة.

<div class="grid cards" markdown>

-   :material-shield-lock: **[Ban System](WA_BAN_SYSTEM_DEEP_EN.md)**

    ---

    دورة حياة WFAC، وBizIntegrityQuery، ووسم الحسابات المشبوهة، وإشارات السبام، والوقاية.

    `APK 2.26.41.6`

-   :material-key-chain: **[TCToken & CSToken](WA_TCTOKEN_CSTOKEN.md)**

    ---

    رموز الإثبات لمكافحة السبام، ومزامنة NctSalt، وstanzas، وحقول proto، وBaileys.

    `APK 2.26.41.6`

-   :material-robot-outline: **[Meta AI](WA_META_AI.md)**

    ---

    معرّفات JID للبوتات، وحقول proto، وبروتوكول الطلب/الاستجابة، وسبب فشل Baileys.

    `APK 2.26.41.6`

-   :material-shield-alert: **[Reporting](WA_REPORTING.md)**

    ---

    أنواع البلاغات، وstanza ‏SMAX spam_list، و97 قيمة لـ spam_flow، ورموز الإبلاغ، ومسار الحظر.

    `APK 2.26.41.6`

-   :material-fingerprint: **[Client Integrity](WA_CLIENT_INTEGRITY.md)**

    ---

    إثبات Keystore، وPlay Integrity، وWASafe، وأعلام القياس عن بُعد، وما يُرسَل.

    `APK 2.26.41.6`

-   :material-link-variant: **[Linked-Device Pairing](WA_LINKED_DEVICE_PAIRING.md)**

    ---

    مساران للإقران: رمز QR ورمز الإقران، وهوية ADV الموقَّعة، وقائمة الأجهزة، وفكّ الربط.

    `APK 2.26.41.6`

-   :material-at: **[Username](WA_USERNAME.md)**

    ---

    عمليات اسم المستخدم، ومفتاح اسم المستخدم، وعلاقته بـ LID، وقيم doc_ids الخاصة بـ w:mex.

    `APK 2.26.41.6`

-   :material-lock-check: **[أمان الحساب](WA_ACCOUNT_SECURITY.md)**

    ---

    تسجيل الدخول بكلمة المرور (غلاف #PWD_WA)، رمز PIN، بريد الاسترداد، مفاتيح المرور، الأجهزة الموثوقة، OPAQUE الأصلي.

    `APK 2.26.41.6`

-   :material-sync: **[مزامنة الحالة](WA_APPSTATE_SYNC.md)**

    ---

    مجموعات syncd، الرقع واللقطات، MAC وLTHash، مشاركة المفاتيح، 96 إجراء مزامنة.

    `APK 2.26.41.6`

-   :material-lan-connect: **[نقل Noise](WA_NOISE_TRANSPORT.md)**

    ---

    chatd عبر TCP، مصافحة Noise XX، ClientPayload، ترميز binary node، تأخير إعادة الاتصال، Tigon.

    `APK 2.26.41.6`

-   :material-phone-in-talk: **[إشارات المكالمات](WA_CALL_SIGNALING.md)**

    ---

    Stanzas المكالمات، offer ومفتاح المكالمة، rekey، relay ومسار الوسائط، المكالمات الجماعية، الروابط، سجل المكالمات.

    `APK 2.26.41.6`

-   :material-cloud-upload: **[رفع الوسائط](WA_MEDIA_UPLOAD.md)**

    ---

    media_conn، روابط الرفع والتنزيل، مفاتيح الوسائط HKDF، AES-CBC + HMAC، الاستئناف وإعادة المحاولة، رموز النتائج، التحصين الأصلي.

    `APK 2.26.41.6`

-   :material-sync-multiple: **[USync](WA_USYNC.md)**

    ---

    Stanza الخاص بـ USync، 4 أوضاع، 10 سياقات، 30 نوع مزامنة، مزامنة جهات الاتصال والأجهزة، ربط LID.

    `APK 2.26.41.6`

-   :material-account-group: **[سجل المجموعات](WA_GROUP_HISTORY.md)**

    ---

    حزمة السجل للأعضاء الجدد، مزامنة السجل للأجهزة المرافقة، أوضاع العنونة، الحدود.

    `APK 2.26.41.6`

-   :material-bullhorn: **[قوائم البث](WA_BROADCAST_LISTS.md)**

    ---

    IQs قوائم w:b، التوزيع، الحصة الشهرية، حظر تحذيرات السبام، status@broadcast.

    `APK 2.26.41.6`

-   :material-chart-line: **[تحليلات WAM](WA_WAM_ANALYTICS.md)**

    ---

    نموذج أحداث WAM، 4 قنوات، رفع w:stats، إحصاءات خاصة، أحداث يومية، تنسيق المخزن المؤقت.

    `APK 2.26.41.6`

-   :material-flag: **[AB Props](WA_AB_PROPS.md)**

    ---

    جداول الأعلام (21,424 معرّفًا)، MobileConfig، مزامنة props، التخزين، overrides، فهرس الأعلام.

    `APK 2.26.41.6`

-   :material-database: **[التخزين المحلي](WA_LOCAL_STORAGE.md)**

    ---

    msgstore.db وwa.db، الجداول الرئيسية، prefs، الذاكرة المؤقتة، النسخ الاحتياطية، مسارات المسح عند تسجيل الخروج.

    `APK 2.26.41.6`

-   :material-key-chain-variant: **[أسرار الرسائل](WA_MESSAGE_SECRETS.md)**

    ---

    messageSecret، مفاتيح HKDF لكل حالة استخدام، التفاعلات والاستطلاعات والأحداث المشفّرة، امتدادات stanza.

    `APK 2.26.41.6`

-   :material-swap-horizontal: **[التشغيل البيني](WA_INTEROP.md)**

    ---

    التشغيل البيني للدردشات مع جهات خارجية (معطّل): IQs w:interop، InteropMessage، نطاقات JID، الموافقة.

    `APK 2.26.41.6`

-   :material-shield-off: **[تجاوز الحجب](WA_CENSORSHIP_CIRCUMVENTION.md)**

    ---

    وكيل WhatsApp، نفق SOCKS الخاص بـ Psiphon، دفع فك الحجب، ترحيل التسجيل، ما هو غير موجود.

    `APK 2.26.41.6`

-   :material-view-dashboard: **[واجهة يقودها الخادم](WA_SERVER_DRIVEN_UI.md)**

    ---

    Phoenix وBloks وnative flows وWhatsApp Flows، تنسيقات payload، الإجراءات، الأمان.

    `APK 2.26.41.6`

-   :material-account-off: **[السطح بدون حساب](WA_ACCOUNT_LESS_SURFACE.md)**

    ---

    شاشات ما قبل التسجيل، الروابط العميقة، المضيفات، المعرّفات، 97 مكوّنًا مصدّرًا.

    `APK 2.26.41.6`

</div>

!!! info "قريبًا"
    ستتوفر تقارير إضافية قريبًا: مواضيع جديدة وتحديثات لكل إصدار جديد من APK.

## Links

[:fontawesome-brands-github: GitHub](https://github.com/7ucg){ .md-button } [:material-source-repository: Repository](https://github.com/7ucg/whatsapp-docs){ .md-button } [:fontawesome-brands-discord: Discord](https://discord.gg/R77JyK2Fu6){ .md-button } [:fontawesome-brands-telegram: Telegram](https://t.me/wegschleifen){ .md-button } [:material-history: Changelog](CHANGELOG.md){ .md-button }

## كيفية قراءة التقارير

!!! success "found"
    قُرئ مباشرةً في شيفرة APK المفكوكة.

!!! warning "inferred"
    مستنتَج من سياق الشيفرة أو التسمية. لم يُؤكَّد أثناء التشغيل.

!!! failure "(2.26.26.4, not re-verified)"
    منقول من APK أقدم. يُعامَل على أنه قد يكون قديمًا.

ينتهي كل تقرير بجدول **Changes vs 2.26.26.4**. تتغير أسماء الأصناف المشوَّشة (مثل `C51530MtC`) مع كل إصدار بناء.

## النطاق

- نظام الحظر: دورة حياة WFAC، وGraphQL BizIntegrityQuery، ومستويات الثقة
- وسم الحسابات المشبوهة: متى ولماذا، والإشارات، والوقاية
- نظام البلاغات: stanzas من نوع SMAX، وspam_list، وأنواع البلاغات
- تفاصيل XMPP: بنى stanza، وقاموس الرموز الثنائي
- إشارات جهة العميل: dhash، وسرعة الرسائل، وحدود البث، وWaFA
- الإبلاغ، وسلامة العميل، وإقران الأجهزة المرتبطة، وأسماء المستخدمين
