<!-- src-sha1: 349e8112a4dcc4567ce203cf21c4c37e5bb47173 -->
# WhatsApp تطبيق الأعمال (Business App) — Full RE Report
**الإصدار:** 2.26.45.7 (Business) مقابل 2.26.45.10 (المستهلك) | **التاريخ:** 2026-11-15
**النطاق:** فرق بنيوي بين APK الخاص بـWhatsApp Business (`com.whatsapp.w4b`) ومستهلِك WhatsApp (`com.whatsapp`) — جذور حزم خاصة بـBusiness، حزمة React Native، فرق المكتبات الأصلية، عدم تماثل فهرس doc_id لـGraphQL/MEX/`www`/`facebook-schema`، فرق الصلاحيات؛ التمييز عن WhatsApp Business API/Cloud API وعن Managed Account

---

## 1. نظرة عامة

WhatsApp Business تطبيق منفصل (`com.whatsapp.w4b`)، لا وضع تبديل داخل WhatsApp المستهلك. يتشارك نواة بروتوكول Signal، ونقل Noise، ومعظم واجهة الدردشة مع WhatsApp المستهلك، لكنه يشحن مجموعة حزم خاصة به لميزات خاصة بالأعمال فقط، ويحمل تبعية — بيئة تشغيل React Native كاملة — لا يحملها المستهلك على الإطلاق.

يغطي هذا التقرير **التطبيق نفسه** فقط، كفرق APK مقابل WhatsApp المستهلك. هذا محور مختلف عن مفهومين آخرين متعلقين بـ"الأعمال" موثَّقين أصلاً في هذا المستودع:

| المفهوم | ما هو | التقرير |
|---|---|---|
| **تطبيق WhatsApp Business** (هذا التقرير) | APK عميل متمايز (`com.whatsapp.w4b`) يُثبِّته نشاط تجاري على هاتف، بواجهته الخاصة للكتالوج، الوسوم، رسائل الغياب، الإعلانات | هنا |
| **WhatsApp Business API / Cloud API** | بنية تحتية من جهة الخادم تستضيف/تُرحِّل رسائل رقم تجاري، تُستخدم بدلاً من تطبيق Business أو جنباً إلى جنب معه؛ تُشار إليها في أي عميل فقط عبر حقول شهادة الاسم الموثَّق (`host_storage`، `actual_actors`، بادئة المُصدِر `smb:`/`ent:`) ولافتات تعايش `business_state_id` | `WA_MANAGED_ACCOUNT.md` §9 |
| **Managed Account** | حساب مستهلك خاص بقاصر، يخضع لإشراف ولي أمر (`ManagedAccount*`/PAA/PMA/PMTA)؛ غير مرتبط بأي من مفهومي الأعمال، ولا توجد تسمية "managed" لحالة الأعمال | `WA_MANAGED_ACCOUNT.md` §1-8 |

يمكن لنشاط تجاري واحد الجمع بين الثلاثة: تشغيل تطبيق Business على جهاز، مع تفويض أجزاء من حركته إلى مزوِّد Cloud API (التعايش)، في حين يكون حساب الطرف المحاوِر حساب مستهلك عادياً. انظر §9 لكيفية تفاعل هذه المفاهيم.

مصدر الأدلة: فرق ساكن للحزم/الموارد/البيان بين `WA-Business_2.26.45.7.apk` و`WhatsApp_2.26.45.10.apk` (الزوج التجريبي الحالي وقت الفرق، لا مقارنة بين إصدارين متتاليين من نفس التطبيق). لم يُشغَّل فك تجميع jadx كامل لأي من الطرفين (قاعدة أمان صارمة للجلسة)؛ كل النتائج أدناه بمستوى شجرة smali من apktool، JSON للموارد، وبيان مُعاد بناؤه. تتبع المستويات عقد الأدلة الخاص بالبرين `found`/`inferred`/`unknown`.

---

## 2. الفرق على مستوى الحزم — found

بمقارنة كل دليل تحت `smali*/` في شجرة apktool لكل تطبيق: يحتوي Business على 4,281 مسار دليل حزمة فريد (15 شجرة `smali_classesN`)، والمستهلك على 3,710 (14 شجرة). 853 مساراً موجودة فقط في Business، و282 فقط في المستهلك. 45 جذر حزمة من المستوى الأعلى `com/whatsapp/*` خاصة بـBusiness حصراً (الدليل الجذري نفسه غائب عن المستهلك، لا مجرد مسار فرعي).

### 2.1 جذور الحزم الخاصة بـBusiness حصراً، مُجمَّعة حسب الميزة

| المجموعة | جذور الحزم | ملاحظات |
|---|---|---|
| رسائل الغياب / الترحيب / الرد السريع | `businessaway`، `businessgreeting`، `businessquickreply`، `businessmissedcallfollowup` | ميزات الرد التلقائي الأساسية لـSMB |
| الوسوم / الوكلاء / تخصيص الدردشة | `chatassignment`، `authagent`، `authagentfeaturecontrol`، `smbmultideviceagents`، `businesscontactmanager`، إضافة إلى `lists/smb/labels` (مسار فرعي؛ جذر `lists` مشترَك) | مقاعد الوكلاء وتحرير الوسوم |
| إعداد/توثيق الملف الشخصي | `businessregistration`، `protectedbusinessaccounts`، `metaverified` | |
| الكتالوج/الطلبات (جانب الإدارة) | `ordermanagement` | تصفح/تحرير الكتالوج نفسه (`catalog`، `businessproduct`، `businesscollection`) **مشترَك** — انظر §2.2 |
| الإعلانات / تكامل Meta Ads | `ads4ads`، `adscreation`، `adcreationinterfaces` | انظر §3 لارتباط React Native |
| الفوترة / الاشتراكات (شرائح API) | `metabilling`، `metabillingui`، `subscription`، `billingui` | |
| تعايش التطبيق مع API | `coexistence`، `connectedaccounts`، `linkedaccounts`، `dynamicaudience` | جسور إلى جانب Cloud API، §9 |
| وكيل أعمال Meta AI | `bizai`، `genai`، `maiba` | |
| أدوات/امتثال الأعمال | `businesstools`، `businessinsights`، `rapidfeedbacksurvey`، `reportblocksharing`، `statistics`، `integrityenforcementsinfra`، `eligibilitychecker`، `googleeligibilityapi`، `smb`، `smbauth`، `waloginmbs`، `marketingmessage`، `marketingmessagemanagement`، `mediatemplates`، `bizdatasharing`، `bizgallerypicker`، `bizmedia` | |

### 2.2 جذور مشترَكة بحزم فرعية خاصة بـBusiness

توجد بعض الجذور في كلا التطبيقين لأن المستهلك يستطيع عرض/استهلاك بيانات جانب الأعمال، لكن حزم التحرير/الإدارة الفرعية خاصة بـBusiness فقط:

- `com/whatsapp/businessprofile/` — جذر مشترَك؛ `businessprofileaddress`، `businessprofilecategory`، `businessprofileedit` (+ `boostmedia`، `businessprofilecompleteness`)، `businessvertical`، `businesscompliance/smb/...` خاصة بـBusiness فقط. يحتفظ المستهلك فقط بحزم عرض الملف الشخصي الفرعية من جانب القراءة.
- `com/whatsapp/lists/` — جذر مشترَك (نموذج/واجهة بيانات الوسوم، `labelitem` في كلاهما)؛ حزمة **تحرير** الوسوم الفرعية `lists/smb/labels` خاصة بـBusiness فقط.
- `catalog`، `businessproduct` (+ `businessproductlist`)، `businesscollection` — جذور مشترَكة، مؤكَّد وجودها في شجرة smali الخاصة بالمستهلك كواجهة **تصفح** الكتالوج/المنتج المعروضة عند عرض دردشة تجارية.

الشكل الصافي: تصفح الكتالوج/المنتج، وعرض الملف الشخصي التجاري، وعرض الوسوم مشترَكة؛ تحرير الكتالوج/الملف الشخصي، ورسائل الغياب/الترحيب/الرد السريع، وتحرير الوسوم، ومصادقة الوكيل/الأجهزة المتعددة، وإنشاء الإعلانات، وتعايش Cloud-API خاصة بـBusiness حصراً.

### 2.3 حزم خاصة بالمستهلك حصراً — found، غير مُجمَّعة

282 مساراً موجودة فقط في المستهلك. لم يُظهر فحص عشوائي مجموعة موضوعية مماثلة في الحجم للمجموعة الخاصة بـBusiness؛ الغالبية أبناء مُتداخلون لعدد أصغر من الجذور الخاصة بالمستهلك فقط. لم يُغَصّ فيه عميقاً — مُدرَج كثغرة مفتوحة في §8.

---

## 3. حزمة React Native — found، خاصة بـBusiness حصراً

نتيجة غير متوقَّعة: يحمل Business حزمة React Native كاملة غائبة عن المستهلك على مستوى الحزمة، لا مجرد وحدة ميزة إضافية.

| الحزمة | Business | المستهلك |
|---|---|---|
| `com/facebook/react/*` (bridge، fabric، animated، devsupport، turbomodule، …) | 88 دليلاً | 0 |
| `com/facebook/catalyst/*`، `com/facebook/fbreact/*` (وحدات جسر RN، i18n، المنطقة الآمنة) | موجودة | غائبة |
| `com/facebook/hermes/*` | 3 أدلة | دليل واحد — مرجع عابر فقط، لا `com/facebook/react` ليُزاوَج معه، أي لا بيئة تشغيل RN عاملة |
| `com/caverock/androidsvg`، `com/crossapp/graphql/facebook/*` | موجودة | غائبة |

مؤكَّد أيضاً على مستوى المكتبة الأصلية (§4): `libreactnative.so` (بيئة تشغيل RN)، `libappmodules.so` (مُحمِّل حزمة JS الأصلي لـRN)، و`libimagepipeline.so` (Fresco، خط أنابيب الصور لـRN) ملفات `.so` خاصة بـBusiness حصراً.

**مستنتج**، غير مؤكَّد: من المرجَّح أن بعض السطح الخاص بـBusiness فقط — الأكثر منطقية هو إنشاء الإعلانات (`adscreation/lwi/react/*` تحتوي حزمة فرعية `react` مباشرة داخل `lwi`)، أو Meta-billing، أو إلحاق التعايش — مُنفَّذ كشاشات React Native مُضمَّنة لا واجهة أندرويد أصلية. أي ميزة (ميزات) محدَّدة تستخدم حزمة RN غير مؤكَّد من أسماء الحزم وحدها؛ يحتاج ذلك فك تجميع محدود النطاق لأصناف `adscreation/lwi/react/activity`. هذا هو أوضح "اعتماد غير متوقَّع" متبقٍّ: تطبيق مراسلة تجاري يُضمِّن بيئة تشغيل JS عابرة للمنصات، على ما يبدو لشاشة واحدة أو قليلة فقط (إنشاء الإعلانات هو التطابق الأقوى بالاسم).

---

## 4. فرق المكتبات الأصلية — found

مقارنة `superpack_index.csv` (بيان المكتبات الخاص بحاوية SUPERPACK_OB) بين مخرجات إعادة بناء التطبيقين:

| | العدد |
|---|---|
| المكتبات المفهرسة للمستهلك | 84 |
| المكتبات المفهرسة لـBusiness | 89 |

**خاصة بـBusiness حصراً (5):** `libappmodules.so`، `libimagepipeline.so`، `libreactnative.so`، `libwacomponents.so` (الاسم يشير إلى مكتبة مكوِّنات جسر RN من تأليف WhatsApp، لا RN القياسية)، `libzstddecoder.so` (يُرجَّح أنها لفك ضغط حزمة/موارد RN).

**خاصة بالمستهلك حصراً:** لا شيء — كل اسم مكتبة في المستهلك يظهر أيضاً في فهرس Business.

المكتبات الست المفكَّكة بـoracle الجهاز المشترَكة بين التطبيقين (`libwhatsapp.so`، `libwhatsappmerged.so`، `libwasafe.so`، `libvoprf-ed25519.so`، `libohai.so`، `libcurve25519.so`) متطابقة بين التطبيقين (نفس الأحجام، نفس عدد الرموز/التصديرات) — نواة بروتوكول Signal/الإثبات/سلامة العميل لم تُلمَس في بناء Business. حزمة React Native + Fresco خاصة بـBusiness حصراً على كلا مستوى حزم Java/Kotlin ومستوى المكتبة الأصلية — نتيجة متماسكة بطبقتين.

---

## 5. فرق فهرس doc_id لـGraphQL / MEX / `www` / `facebook-schema` — found

يشحن كل تطبيق فهرس doc_id الخاص به `assets/whatsapp-android-<schema>_client_persist_ids.json`، مقروءاً مباشرة من شجرة موارد apktool المُفكَّكة (لا حاجة إلى فك تجميع).

| المخطط | عمليات Business | عمليات المستهلك | خاصة بـBusiness | خاصة بالمستهلك |
|---|---|---|---|---|
| `mex` | 242 | 242 | 0 | 0 — مجموعة مطابقة |
| `wamo` | 22 | 22 | 0 | 0 — مجموعة مطابقة |
| `www` | 237 | 244 | 4 | 11 |
| `facebook-schema` | 224 | 17 | 215 | 7 |

### 5.1 `mex` و`wamo` — متطابقان بين التطبيقين

يحمل كلا الفهرسين نفس أسماء العمليات تماماً في كلا APK (الفرق بين المجموعتين فارغ، لا مجرد تساوٍ في العدد). لا يحمل Business سطح MEX/GraphQL خاصاً به على مستوى هذا المخطط — يتشارك فهرس المستهلك كاملاً.

### 5.2 `www` — عدم تماثل صغير

- خاصة بـBusiness (4): `BPAccessTokenAndSessionCookiesMutation`، `CatkitTypeaheadProxy`، `WACreateEnforcementAppeal`، `WAGetEnforcementAppealStatus`.
- خاصة بالمستهلك (11): `WaAutofillAcknowledgeWalletTerms`، `WaAutofillFetchContactData`، `WaAutofillFetchSettings`، `WaAutofillSaveContactData`، `WaAutofillUpdateNegativeInteraction`، `WaAutofillUpdateSaveCvv`، `WaCreateLabyrinthBackupMutation`، `WaDeleteLabyrinthAccountMutation`، `WaDeleteLabyrinthThreadsMutation`، `WaRotateLabyrinthEpochMutation`، `WaUploadLabyrinthMessagesMutation`.

يحمل المستهلك عمليات المدفوعات الشخصية/التعبئة التلقائية الخاصة به (`WaAutofill*`) ونسخ الاحتياطي المشفَّر من طرف إلى طرف للدردشات (`WaCreateLabyrinthBackupMutation` وغيرها — نظام نسخ احتياطي الدردشات الخاص بـWhatsApp، "Labyrinth" داخلياً) التي لا يحملها Business؛ يحمل Business عمليتين أو ثلاثاً من استئناف إنفاذ الحساب وجلسة/اقتراح نصي لا يحتاجها المستهلك.

### 5.3 `facebook-schema` — النتيجة الرئيسية: 215 عملية خاصة بـBusiness

هنا يعيش سطح GraphQL الحقيقي الخاص بـBusiness — لا `mex`/`wamo`، المتطابقتان بايتياً بين التطبيقين. يحمل Business 224 عملية في هذا المخطط مقابل 17 للمستهلك؛ الـ17 الخاصة بالمستهلك هي عمليات مدفوعات شخصية/nonce تجاري غير مرتبطة (`AcDcCreateCanonicalDigitalCommerceNonce`، `WaAutofillAddPayCreditCard`، `WaGetServerEncryptionKey`، إلخ) لا يحملها Business.

العمليات الـ215 الخاصة بـBusiness، مُجمَّعة بالاسم (تجميع وصفي، مُستخرَج من التحليل الساكن، لا تصنيف وظيفي مؤكَّد):

| المجموعة | أمثلة العمليات |
|---|---|
| قاعدة المعرفة / الرد بالذكاء الاصطناعي / المحاكاة ("coach") | `FetchAIAbilities`، `KnowledgeRepoFetchV2`، `UpdateAIKnowledge`، `DeleteAIKnowledge`، `CoachSimulationMessage`، `CoachSuggestedReply`، `StartSimulation`، `SubmitSimulationFeedback`، `FetchSuggestedReply`، `MarkSuggestedReplyUsed` |
| وكيل أعمال Meta AI / MAIBA | `MAIBAOnboarding`، `MAIBACompleteParallelOnboarding`، `Maiba1pCalendarEvents`، `MaibaGetCurrentCatalog`، `MaibaDownloadLeadGenFlow`، `MetaAIBizAgentWAAIHome`، `MetaAIBizAgentWACoachingMutation` |
| توليد العملاء المحتملين / المواعيد | `CreateLeadGenFlow`، `GetLeadGenFlowLeads`، `UpdateLeadStages`، `CreateAppointmentFlow`، `GetAppointmentPrefill`، `GetDefaultAvailability` |
| وكيل المصادقة / وكلاء SMB متعددون / تسجيل الدخول | `AuthAgentCompanyInfoQuery`، `AuthAgentFeaturePolicyQuery`، `AddSmbAgentAndCoexQr`، `SmbRegistrationInit`، `WALoginClaimAuthChallenge`، `WALoginConfirmAuthChallenge` |
| تعايش التطبيق مع Cloud-API | `CoexUnifiedOnboarding`، `CoexMultiAppEligiblity`، `CoexAppsAndServicesOffboardProduct`، `CoexCompanionPairingStatusCallback`، `CoexistenceQRCodeFetch` |
| إعلانات النقر إلى WhatsApp (CTWA) | `CTWACreateLookAlikeAudienceMutation`، `CTWAPreviousAdsRecommendationQuery`، `CtwaLinkedMediaQuery`، `CtwaNativeUploadAdMediaMutation` |
| حساب الإعلانات / الأهلية | `AdAccountEligibilityCheckerQuery`، `OnboardToWhatsAppAdAccount`، `WhatsAppBizFetchAdDefaults`، `WhatsAppBizGetEstimatedAdReach` |
| إدارة الكتالوج (جانب الكتابة) | `WhatsAppCatalogAddProduct`، `WhatsAppCatalogEditProduct`، `WhatsAppCatalogDeleteProduct`، `WhatsAppCatalogCreateCollections`، `WhatsAppCatalogProductVisibilityUpdate` |
| بث رسائل تسويقية ("Pro") | `BusinessBroadcastProCampaignContent`، `BusinessBroadcastProCustomAudiencesQuery`، `BusinessBroadcastProInsights`، `WAMarketingMessagesCustomAudienceCreateMutation` |
| مدير جهات الاتصال / ملفات العملاء | `BizContactManagerProfiles`، `ContactManagerAccessState`، `WACustomerProfiles`، `UpsertWACustomerProfiles`، `DeleteWACustomerProfile` |
| الفوترة / الاشتراك (شرائح تُفوَّتر بواسطة Meta) | `FetchSubscriptionState`، `FetchSubscriptionStateV2`، `WaSmbMetaOneTierPaymentPrefetchTargetQuery`، `AcceptBizAiPaymentTerms` |
| تصدير تاريخ الدردشة / تكامل جهة ثالثة (GDrive) | `FetchChatHistoryExportStatus`، `GDriveGetFiles`، `UploadHistoricalMetadata`، `Disconnect3PPartners` |
| حساب IG/FB مربوط | `SetIGDisplayContactInfoMutation`، `WAFBPageProfileImportGet`، `WhatsAppBusinessLinkedAccountsQuery` |
| بنية أعلام الميزات/QE (جانب الأعمال) | `CheckQEBool`، `WaFetchQEBool`، `WaFetchQEString`، `WhatsAppGraphQLCheckQE` |

القائمة الكاملة للأسماء الـ215 قابلة للاستنساخ من ملفات موارد التطبيقين المذكورة أعلاه؛ لا تُستنسَخ حرفياً هنا. **قيم** doc_id لـ`www`/`facebook-schema` (لا أسماء العمليات فقط) لم تُفرَّق — قد يحمل اسم عملية مشترَك مبدئياً doc_id مختلفاً بين التطبيقين؛ لم يُفحَص.

---

## 6. فرق الصلاحيات — found

من فهرس بيان كل تطبيق:

| | خاصة بـBusiness حصراً | خاصة بالمستهلك حصراً |
|---|---|---|
| الصلاحية | `com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` | `android.permission.RECEIVE_SMS` |

يطلب كل تطبيق إضافة إلى ذلك صلاحيات بث ذاتي/خرائط خاصة بحزمته تحت اسم حزمته (`com.whatsapp.w4b.*` مقابل `com.whatsapp.*`) — هذه مُكافِئات مُشوَّشة بالاسم لحزمة لبعضها البعض، لا جديدة وظيفياً، ولا تُحصى أعلاه.

لا يطلب Business استقبال SMS. **مستنتج**، غير مؤكَّد من الكود: يتسق مع كون حسابات Business غالباً ما تُسجَّل عبر مسار Cloud/Business API بدلاً من الاعتماد على القراءة التلقائية لرسائل SMS على الجهاز لـOTP — لكن هذا الاستدلال غير مُتحقَّق مقابل أي كود لتدفق التسجيل في هذا التمرير.

---

## 7. ملاحظة Baileys / velowa

لا شيء تقريباً من سطح هذا التقرير قابل للوصول من عميل WhatsApp Web عادي (velowa أو أي تنفيذ لبروتوكول Noise/الأجهزة المتعددة):

- فهرسا `mex`/`wamo` **متطابقان** مع المستهلك — لا شيء خاص بـBusiness يُضاف هناك؛ أي عميل WA Web يملك أصلاً نفس قيم doc_id.
- العمليات الـ215 الخاصة بـ`facebook-schema` (§5.3) هي سطح GraphQL الحقيقي الخاص بـBusiness، لكنها تدفقات موجَّهة بواجهة **تطبيق** Business نفسه (تحرير الكتالوج، إنشاء الإعلانات، التدريب/MAIBA، إلحاق التعايش، مصادقة الوكيل) ومحجوبة خلف حالة حساب تطبيق Business نفسه، وفي عدة مجموعات، خلف جانب خادم WhatsApp Business API/Cloud API كاملاً (التعايش، الفوترة، حسابات الإعلانات). عميل WA Web يتحدث بروتوكول الأجهزة المتعددة العادي لا مسار له لمعظم هذه — ليست ميزات بروتوكول سلكي على الإطلاق، بل استدعاءات REST/GraphQL تجريها واجهة تطبيق Business نفسه مقابل خلفية منصة الأعمال لدى Meta.
- سطح React Native لإنشاء الإعلانات (§3) هو واجهة تطبيق أندرويد فقط (شاشات JS مُضمَّنة تُعرَض بواسطة `libreactnative.so`)؛ لا شيء منه ينتقل عبر بروتوكول السلك الخاص بالدردشة.
- المنطقة الوحيدة ذات الصلة بروتوكول الأجهزة المتعددة هي التعايش (`coexistence`/`connectedaccounts`/`linkedaccounts`)، التي يُغطَّى تمثيلها على مستوى الجهاز/الجلسة بالفعل في الوثائق الموجودة في `WA_MANAGED_ACCOUNT.md` §9.3 و`WA_LINKED_DEVICE_PAIRING.md` (نوع الحساب `HOSTED`، معرّف الجهاز 99، `platformType` 23/25-27) — هذا الجزء بالفعل بأقصى ما يمكن لعرض من جانب العميل فقط الوصول إليه.

الخلاصة: هذا التقرير مفيد لفهم ما *يحتويه* APK الخاص بـBusiness، لا كمصدر سطح بروتوكول سلكي جديد لـvelowa.

---

## 8. ما لم يتحقَّق منه هذا التقرير

| الثغرة | السبب | المتابعة اللازمة |
|---|---|---|
| فرق مخطط proto/السلك بين التطبيقين | `unknown`، لا مستنتج كمتماثل. لم تُشغَّل مرحلة proto في خط أنابيب إعادة البناء لأي من البناءين (`protoc_ok=False` في الطرفين)؛ استخراج proto الأعمق المستخدَم في مواضع أخرى من تمرير تحديث الإصدار هذا (1089 رسالة، خروج `protoc` بـ0) عمل فقط مقابل فك تجميع jadx الموجود أصلاً للمستهلك — لا يوجد فك تجميع مُكافِئ لـ`com.whatsapp.w4b` في مساحة العمل هذه. إنتاج أحدها يحتاج تشغيل jadx كامل لـAPK، محظور بقاعدة أمان صارمة لهذه الجلسة (تسبَّب سابقاً في تعطُّل آلة التحليل). غياب الدليل ليس دليلاً على الغياب. | استخراج jadx لصنف واحد أو DEX واحد محدود بأصناف الرسالة/proto فقط (لا فك تجميع كامل لـAPK) |
| أي ميزة (ميزات) تُعرَض عبر حزمة React Native الخاصة بـBusiness | ترابط اسم حزمة/مكتبة فقط (`adscreation/lwi/react/*` هو التطابق الأقوى بالاسم، لكنه غير مؤكَّد) | فك تجميع محدود النطاق لأصناف `com/whatsapp/adscreation/lwi/react/*` |
| مجموعة الحزم الخاصة بالمستهلك حصراً (282 مساراً) | غير مُجمَّعة موضوعياً في هذا التمرير — أولوية أدنى بالنظر إلى تأطير المهمة على سطح Business الخاص | تمرير مخصَّص على فرق الـ282 مساراً |
| **قيم** doc_id لـ`www`/`facebook-schema` | فُرِّقت فقط **أسماء** العمليات؛ قد يحمل اسم مشترَك doc_id مختلفاً لكل تطبيق | فرق على مستوى القيمة لكلا ملفي JSON الخاصين بالموارد |
| القائمة الكاملة للعمليات الـ215 في `facebook-schema` / المتغيرات / أشكال الاستجابة | التجميع بكلمة مفتاحية بالاسم فقط؛ لا محاولة لاستخراج موقع استدعاء أو حقل استجابة | تتبع موقع استدعاء مُستهدَف لكل مجموعة، كما فُعل لعمليات MEX في تقارير أخرى |

---

## 9. فروق أساسية

| A | B |
|---|---|
| **تطبيق** WhatsApp Business (`com.whatsapp.w4b`) — APK متمايز بمجموعة حزمه الخاصة، هذا التقرير | WhatsApp Business **API / Cloud API** — استضافة/ترحيل رسائل رقم تجاري من جهة الخادم؛ لا APK عميل مخصَّص، يُشار إليه في أي عميل عبر حقول شهادة الاسم الموثَّق (`WA_MANAGED_ACCOUNT.md` §9) |
| حزم `coexistence`/`connectedaccounts`/`linkedaccounts` الخاصة بتطبيق Business — واجهة التطبيق الخاصة به للربط بمزوِّد Cloud API | لافتات تعايش `business_state_id` التي يراها عميل **نظير** (مستهلك أو Business) عندما يُشغِّل رقم تجاري التطبيق وAPI في آن واحد (`WA_MANAGED_ACCOUNT.md` §9.2) |
| Managed Account (`ManagedAccount*`، PAA/PMA/PMTA) — حساب **مستهلك** خاص بقاصر تحت إشراف ولي الأمر | تطبيق Business — حساب نشاط تجاري، مفهوم غير مرتبط على الإطلاق، لا تداخل كود/مخطط |
| فهرسا doc_id لـ`mex`/`wamo` — مجموعتا أسماء عمليات متطابقتان بايتياً في كلا التطبيقين | فهرس doc_id لـ`facebook-schema` — 215 عملية موجودة فقط في Business؛ هنا يعيش سطح GraphQL الخاص بـBusiness فعلياً |
| **عرض** الكتالوج/الملف الشخصي/الوسم — جذور حزم مشترَكة، موجودة في المستهلك أيضاً (فيستطيع مستخدم المستهلك تصفح كتالوج نشاط تجاري) | **تحرير** الكتالوج/الملف الشخصي/الوسم — جذور حزم خاصة بـBusiness حصراً (جانب الكتابة الذي لا يصل إليه إلا النشاط التجاري نفسه) |

---

## 10. الخلاصة

يؤكد الشكل المتوقَّع مسبقاً — الكتالوج، الملف الشخصي/التوثيق التجاري، الوسوم، تجميع الردود السريعة/الترحيب/الغياب، ومصادقة الوكيل/الأجهزة المتعددة في كود خاص بـBusiness فقط، مع نصف العرض/الظهور من كل ميزة مشترَكاً مع المستهلك — ويضيف نتيجتين غير متوقَّعتين:

1. **`facebook-schema` هو المكان الذي يعيش فيه سطح GraphQL الحقيقي الخاص بـBusiness** (215 عملية خاصة بـBusiness: مدرِّب/قاعدة معرفة بالذكاء الاصطناعي، MAIBA، توليد العملاء المحتملين، وكيل المصادقة، التعايش، إعلانات CTWA، عمليات كتابة الكتالوج، البث التسويقي، الفوترة)، لا فهرسا `mex`/`wamo` الرئيسيان، المتطابقان بايتياً في أسماء العمليات بين التطبيقين.
2. **يحمل Business حزمة React Native + Fresco كاملة** (`com.facebook.react.*`، `libreactnative.so`، `libimagepipeline.so`، `libwacomponents.so`) غائبة تماماً عن المستهلك، على مستوى الحزمة والمكتبة الأصلية كلاهما — على الأرجح لدعم شاشات إنشاء الإعلانات، لكن حدود الميزة الدقيقة غير مؤكَّدة دون فك تجميع محدود النطاق.

فرق مخطط proto/السلك لم يُتمكَّن من إجرائه في هذا التمرير (§8) ويُسجَّل كـunknown، لا كمستنتج بأنه متماثل.
