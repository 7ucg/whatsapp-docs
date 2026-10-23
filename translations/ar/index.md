<!-- src-sha1: 8f4d70e43bcc01687d4132028db5748cbcddb901 -->
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
