<!-- src-sha1: 5fa1223d0cb214989ef32453299c247d3ee92ecf -->
# WhatsApp حسابات المؤسسات (Org Accounts) — Full RE Report
**الإصدار:** 2.26.45.10 | **التاريخ:** 2026-11-15
**النطاق:** نموذج كيان حساب المؤسسة (`org_id`، دليل الأعضاء، تصنيف وسم العضو/الفريق)، تدفق الانضمام عبر رابط الدعوة، فحص توافر اسم العرض، الإلحاق المشروط بالبريد الإلكتروني (OTP)، فهرس عمليات `GraphQlOrgApi`/`OrgEmailCodeClient` (9 عمليات، `www` + `mex`)، التمييز عن Managed Account وعن تفويض WhatsApp Business API، ملاحظات تنفيذ Baileys/velowa

---

## 1. ما هو حساب المؤسسة

جميع العبارات تحليل ساكن للـ APK المفكَّك. المستوى: **found** = سلسلة/حقل حرفي مقروء عند موقع استدعاء، **inferred** = مستنتج من شكل الكود دون تتبّع استدعاء كامل من البداية إلى النهاية، **unknown** = غير محسوم.

"org" (الاسم الداخلي في كل مكان، لم يُقرأ أبداً مكتوباً بالكامل كـ"organization" في أي سلسلة) هو كيان عضوية له هويته الخاصة، ودليل أعضاء قابل للانضمام، ومسار إلحاق عبر رابط دعوة + OTP بريد إلكتروني، منفصل تماماً عن تسجيل الحساب برقم الهاتف وعن النظامين الآخرين المشابهين بالاسم ("managed") الموجودين أصلاً في هذا المستودع (القسم 7).

| الكيان | الاسم الداخلي | الحقول (found) | الدور |
|---|---|---|---|
| هوية المؤسسة | `org_id` | `org_id`، `org_name`، `org_member_count`، `org_icon_url`/`org_icon_handle`/`org_icon_full_url`، `org_description` | المؤسسة نفسها، تُحل من رابط دعوة |
| رابط الدعوة | `link_token` | يُنقل من البداية إلى النهاية من المُحيل/الرابط العميق وصولاً إلى عملية الانضمام النهائية | بيانات اعتماد انضمام تستخدم مرة واحدة(؟)؛ مدة الصلاحية الدقيقة `unknown` |
| هوية العضو داخل المؤسسة | `display_name` (+ `display_last_name` اختياري)، `member_tag` | اسم عرض لكل عضو يخضع لفحص توافر/سياسة خاص به، مستقل عن اسم الملف الشخصي الرئيسي للحساب | كيفية ظهور العضو داخل دليل المؤسسة |
| تصنيف الفريق/الدور | `team`، `team_options`، `selected_team` | موجودة كحقول حالة؛ دلالات قيم الفريق الفردية غير محلولة | تجميع الأعضاء داخل المؤسسة |
| علاقة الدليل | `relationship` (`OrgDirectory`)، القيمة الوحيدة المرصودة `"CONTACT"` | — | قيمة فلتر العلاقة الوحيدة المرصودة؛ تعيينات ordinal←string الأخرى `unknown` |

جميع أسماء الحقول هذه تُقرأ حرفياً كقيم `const-string` مباشرةً قبل استدعاء ضبط `GraphQlCallInput`/`LX/0jN` في `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali` و`com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali` (2.26.45.10)، إضافة إلى قائمة حقول كائن الحالة `OrgJoinViewModel` — كل ذلك **found**. ترتيب الخطوات الذي يربط هذه العمليات في تدفق واحد (القسم 3) **مستنتج** من كيفية تطابق حقول الحالة، لا من تسلسل استدعاء واحد مُتعقَّب.

---

## 2. فهرس العمليات

9 عمليات عبر نقلين، كلها في `com.whatsapp.orgs`. 7 على `www` (`GraphQlOrgApi`، GraphQL بمعرّف وثيقة دائم عبر `Lcom/facebook/pando/TreeWithGraphQL`)، و2 على `mex` (`OrgEmailCodeClient`). المتغيرات **found** من موقع الاستدعاء في كل صف أدناه.

| العملية | النقل | doc_id (2.26.45.10) | النوع | المتغيرات | الغرض |
|---|---|---|---|---|---|
| `OrgInvitePreview` | www | `29166886682947630` | Query | `link_token` | معاينة المؤسسة (الاسم/الأيقونة/عدد الأعضاء) قبل الالتزام بالانضمام |
| `OrgCheckDisplayName` | www | `28738875225734024` | Query | `display_name` | فحص توافر/سياسة لاسم عرض العضو داخل المؤسسة |
| `OrgCheckEmailEligibility` | www | `28705126895811065` | Query | `link_token`، `email` | هل هذا البريد الإلكتروني قابل للاستخدام لهذه دعوة المؤسسة المحدَّدة |
| `OrgSendEmailCode` | mex | `28659396457057459` | Mutation | `email` | إرسال رمز OTP بالبريد الإلكتروني |
| `OrgVerifyEmailCode` | mex | `29096159596657036` | Mutation | `email`، `code` | التحقق من رمز OTP بالبريد الإلكتروني |
| `OrgJoin` | www | `29366364109633604` | Mutation | `link_token`، `email`، `org_display_name`، `member_tag`، `org_display_last_name` | إرسال الانضمام النهائي |
| `OrgDirectory` | www | `28698253656512395` (مُغيَّرة من `28049955604655823` في 2.26.41.6) | Query | `org_id`، `relationship` (لم تُرصد سوى `"CONTACT"`)، `first`، `after` | دليل الأعضاء مقسَّم إلى صفحات، بعد الانضمام |
| `OrgMemberSearch` | www | `39884553687825642` (مُغيَّرة من `28199835469697557`) | Query | `query`، `org_id`، `first`، `after` | بحث ضمن دليل الأعضاء |
| `OrgLeaveMutation` | www | `28491454287217875` | Mutation | `org_id` | مغادرة المؤسسة، في أي وقت بعد الانضمام |
| `OrgList` | www | `28999557569709709` (مُغيَّرة من `27920891847589435`) | Query | `unknown` (لا يوجد موقع استدعاء ساكن يتجاوز doc_id/تغيّره) | إدراج المؤسسات التي ينتمي إليها الحساب |

جميع عمليات `www` السبع موجودة في صنف واحد، `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`؛ وعمليتا `mex` كلتاهما في `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`. نطاق/مخطط عمليات `www` هو `whatsapp-android-www`؛ وعمليات `mex` هو `whatsapp-android-mex`. `OrgDirectory`/`OrgList`/`OrgMemberSearch` كانت موجودة قبل 2.26.45.10 (رُصدت أولاً مقابل 2.26.41.6)؛ تغيّرت قيم doc_id بينهما (نفس الصنف، نفس أسماء الحقول) — السبع الأخرى جديدة في 2.26.45.10.

توجد عمليات بحث مساعدة في حزمة مجاورة، `com/whatsapp/work/publicidentity/` — ليست جزءاً من تدفق الانضمام نفسه، بل الطريقة التي يعلم بها عميل نظير أن شخصاً ينتمي إلى مؤسسة أصلاً قبل أي تدخّل لدعوة:

| العملية | النقل | doc_id | المتغيرات | الغرض |
|---|---|---|---|---|
| `WorkPublicContactInfoQuery` | www | `29154186964216430` | `lids` (قائمة) | حالة عمل/حساب تجاري لكل جهة اتصال، مجمَّعة (`CoalescingBatcher`، مؤخَّرة، حد أقصى 100 مفتاح في الجولة) |
| `WorkPublicOrgInfoQuery` | www | `28899689926378846` | `ids` (قائمة، أرقام مؤسسات) | معلومات مؤسسة عامة (`id`، `name`، حقلان نصّيان غامضان إضافيان — `inferred`: شعار/نطاق) للمؤسسات التي ينتمي إليها جهة اتصال |

---

## 3. تدفق الانضمام من البداية إلى النهاية

ترتيب **مستنتج**، مُجمَّع من أسماء حقول كائن الحالة `OrgJoinViewModel` (لا يوجد تسلسل استدعاء واحد مُتعقَّب يغطي هذا من البداية إلى النهاية):

### 3.1 الدخول

تصل الدعوة كرمز رابط، إما عبر مُحيل/رابط عميق (`OrgInviteReferrerOpener`، السلسلة الحرفية `org_invite_token_from_referrer` ← تصبح `link_token`) أو تُفتح مباشرة (`OrgInviteLandingActivity`، بحالات فشل `org_invite_landing_failure` / `org_invite_landing_already_in_org`).

### 3.2 المعاينة

`OrgInvitePreview(link_token)` تُعيد ما يكفي لتعبئة `org_name`، `org_member_count`، `org_icon_url`/`org_icon_handle`/`org_icon_full_url`، `org_description` قبل أن يلتزم المستخدم بأي شيء.

### 3.3 فحص اسم العرض

`OrgJoinActivity`/`OrgJoinViewModel` يجمع `display_name` (+ `display_last_name` اختياري) واختيار فريق (`team`/`team_options`/`selected_team`). `OrgCheckDisplayName(display_name)` هو بوّابة السياسة/التوافر؛ عند الرفض يضبط الاستمرار المتداخل `OrgJoinViewModel$checkName$2` `name_refusal` و/أو `last_name_refused` بشكل مستقل — يمكن رفض الاسم الأول والاسم الأخير كلٌّ على حدة.

### 3.4 أهلية البريد الإلكتروني وOTP

`OrgCheckEmailEligibility(link_token, email)` يفحص إمكانية استخدام بريد إلكتروني معيَّن لهذه الدعوة المحدَّدة. ثم ترسل `OrgSendEmailCode(email)` (mex) رمز OTP؛ وبعد أن يُدخله المستخدم، تتحقق منه `OrgVerifyEmailCode(email, code)` (mex). يمكن أن يُظهر التحقق `username_pending_email` / `rejoin_after_username` / `username_screen_open` — يمكن أن يُحجَب الانضمام خلف إعداد اسم المستخدم الخاص بالحساب الرئيسي نفسه، وهو ارتباط بنظام `WA_USERNAME.md` غير مرتبط بالمؤسسات في أي شيء آخر.

### 3.5 الانضمام

`OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)` هو الإرسال النهائي. النجاح يضبط `joined=true` ويعبّئ حقول المؤسسة (`org_id`، `org_name`، `org_member_count`، `org_icon_*`، `org_description`) في الحالة المحلية.

### 3.6 بعد الانضمام

`OrgDirectory(org_id, relationship="CONTACT", first, after)` تجلب دليل الأعضاء؛ `OrgMemberSearch(query, org_id, first, after)` تبحث فيه. `OrgLeaveMutation(org_id)` تُغادر، في أي وقت بعد الانضمام.

```
[Invite link / referrer]
  │ OrgInviteReferrerOpener: org_invite_token_from_referrer -> link_token
  │ (or OrgInviteLandingActivity: org_invite_landing_failure / _already_in_org)
  ▼
[OrgInvitePreview(link_token)]
  │  org_name, org_member_count, org_icon_*, org_description
  ▼
[OrgJoinActivity / OrgJoinViewModel]
  │  org_join_offline, step, team/team_options/selected_team, display_name, display_last_name
  ▼
[OrgCheckDisplayName(display_name)]
  │  -> name_refusal / last_name_refused on rejection
  ▼
[OrgCheckEmailEligibility(link_token, email)]
  ▼
[OrgSendEmailCode(email)]           -- mex, OTP send
  ▼
[user enters code]
  ▼
[OrgVerifyEmailCode(email, code)]   -- mex, OTP verify
  │  -> username_pending_email / rejoin_after_username / username_screen_open
  ▼
[OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)]
  │  -> joined=true, org_id/org_name/org_member_count/org_icon_*/org_description populated
  ▼
[OrgDirectory(org_id, relationship="CONTACT", first, after)]
[OrgMemberSearch(query, org_id, first, after)]
[OrgLeaveMutation(org_id)]
```

---

## 4. فروق أساسية — لا تخلط بينها

توجد ثلاثة مفاهيم "بنية حساب" غير مرتبطة في/حول هذا العميل. لا تتشارك كوداً ولا proto ولا فضاء doc_id.

| | حسابات المؤسسات (هذا التقرير) | Managed Account (`WA_MANAGED_ACCOUNT.md`) | تفويض Business API (BSP/Cloud API) |
|---|---|---|---|
| هوية الكيان | `org_id`، دليل خاص | `ManagedAccountConnection`، مُفهرَس بـ`connectionLid`/`connectionPnJid` | حقول شهادة الاسم الموثَّق (`host_storage`/`actual_actors`)، لا هوية كيان جديدة |
| العلاقة | انضمام تطوعي عبر رابط دعوة، N عضو لكل مؤسسة | راعٍ واحد ↔ تابع واحد، رابط إشراف | رقم تجاري تُديره Meta/مزوِّد عبر Cloud API |
| الإلحاق | رابط دعوة + OTP بريد إلكتروني + فحص توافر اسم العرض | رابط عميق + ربط بمبادرة الراعي (`ManagedAccountInitiateLinkingQuery` وغيرها) | تهيئة من جهة الخادم على منصة أعمال Meta؛ غير مرئية لهذا العميل سوى عبر العلامات الناتجة |
| موقع الكود | `com.whatsapp.orgs.*` | `com.whatsapp.managedaccount.*` / `pma.*` / `pmta.*` | لا حزمة مخصَّصة؛ تُشار إليها عبر حقول شهادة `w:biz` ونوع حساب `HOSTED` متعدد الأجهزة |
| النقل | GraphQL عبر `whatsapp-android-www` + `whatsapp-android-mex` (OTP) | `whatsapp-android-mex` فقط | حقول stanza من نوع `w:biz`، ليس بروتوكول انضمام/دعوة على الإطلاق |
| المغادرة/فكّ الربط | `OrgLeaveMutation(org_id)` | `ManagedAccountRevokeLinkingMutation` | غير قابل للتطبيق — لا انضمام/مغادرة لكل حساب؛ الرقم نفسه يُهيَّأ/يُزال من جهة الخادم |
| مفهوم الدليل | نعم — `OrgDirectory`/`OrgMemberSearch`، محدود بالعلاقة | لا | لا |

لا أحد من الثلاثة إعادة تسمية أو تطوّر للآخر: حساب المؤسسة لا يملك دلالات إشراف (لا حالة عمر/تخرّج، لا رمز PIN للراعي) ولا دلالات شهادة تجارية (لا `host_storage`/`actual_actors`، لا فحص بادئة المُصدِر)؛ إنه نموذج عضوية طوعي بسيط مزوَّد بدليل، يُضاف فوق حساب WhatsApp مسجَّل أصلاً. الاستنتاج المتعلق بتسمية المنتج ("ميزة WhatsApp الخاصة بالمؤسسات/المنظمات للشركات/المؤسسات") **مستنتج** من شكل الحقول فقط (`org_id` + دليل أعضاء + فحص توافر اسم العرض + تحقق نطاق البريد الإلكتروني) — لم تُقرأ أي نسخة تسويقية أو نص داخل العميل يُسمّي الميزة.

---

## 5. حالات الخطأ

لم يكن من الممكن بناء جدول رموز خطأ من مواقع الاستدعاء في هذا البناء — لم تُعثر أي سلاسل نجاح/فشل أو رموز خطأ عددية لشكل الاستجابة لأي من العمليات التسع في هذا التمرير. علامات الرفض الوحيدة المقروءة هي حقلا الحالة المنطقيان في `OrgJoinViewModel$checkName$2`:

| العرض | السبب | الدليل |
|---|---|---|
| رفض اسم العرض | فشل فحص السياسة/التوافر في `OrgCheckDisplayName` | ضبط `name_refusal` (found، حقل حالة) |
| رفض الاسم الأخير بشكل مستقل عن الاسم الأول | نفس الفحص، فرع خاص بالاسم الأخير | ضبط `last_name_refused` (found، حقل حالة) |
| حظر الانضمام بانتظار إعداد اسم المستخدم | نجاح `OrgVerifyEmailCode` يُحجَب بحالة اسم المستخدم الخاص بالحساب نفسه | `username_pending_email`/`rejoin_after_username`/`username_screen_open` (found، حقول حالة؛ الشرط الدقيق من جهة الخادم `unknown`) |
| فتح الدعوة أثناء كون المستخدم عضواً أصلاً | قطع مُبكِّر في صفحة الوصول | `org_invite_landing_already_in_org` (found، سلسلة حرفية) |
| رابط الدعوة غير صالح/منتهي | فشل عام في صفحة الوصول | `org_invite_landing_failure` (found، سلسلة حرفية؛ لم يُعثر على سبب فرعي مميَّز) |

---

## 6. ملاحظات تنفيذ Baileys / velowa

جميع العمليات التسع هي استدعاءات GraphQL/MEX قياسية بمعرّف وثيقة دائم على نفس نطاقي `whatsapp-android-www`/`whatsapp-android-mex` التي تنفّذها velowa أصلاً لميزات أخرى (اسم المستخدم، المجموعات) — لم تُعثر على نقل جديد، ولا طبقة تشفير أصلية خاصة بالمؤسسات.

| جاهز للنقل | غير جاهز للنقل |
|---|---|
| أسماء العمليات التسع + doc_ids + مفاتيح المتغيرات (القسم 2) — تكفي لتشكيل طلب | أسماء حقول الاستجابة غير معروفة لكل عملية سوى الأربع المقروءة صريحاً في حالة `OrgJoinViewModel` (القسم 1)؛ يجب أن يعامل العميل كل الاستجابات كـ JSON غامض حتى يؤكد التقاط فعلي الأشكال |
| مسار انتشار `link_token` (مُحيل ← معاينة ← انضمام) | ضبط الخطوات الدقيق — هل يفرض الخادم ترتيب القسم 3، أو هل يمكن مثلاً تجاوز `OrgCheckDisplayName`/`OrgCheckEmailEligibility` — `inferred`، غير مؤكَّد |
| شكل تصفيح `OrgDirectory`/`OrgMemberSearch` (`first`/`after`، نمط مؤشِّر قياسي) | تعداد `relationship`: لم يُؤكَّد سوى `"CONTACT"`؛ القيم الممكنة الأخرى `unknown`، فلا ينبغي للعميل افتراض أنها الفلتر الصالح الوحيد |
| `OrgLeaveMutation(org_id)` — عملية حقل واحد، تافهة التنفيذ | متغيرات `OrgList` كاملة (لا موقع استدعاء مُعثور عليه — يُرجَّح أنها ترسل `{}`، غير مؤكَّد) |
| `WorkPublicContactInfoQuery`/`WorkPublicOrgInfoQuery` لعمليات بحث للقراءة فقط عن "هل جهة الاتصال هذه في مؤسسة"، مستقلة عن تدفق الانضمام | شكل عنوان رابط الدعوة/الرابط العميق نفسه (المضيف، المسار، ترميز الرمز) — لم يُلتقط في هذا التمرير |

تنفيذ velowa الذي يحاول هذا التدفق ينبغي أن يتوقع اكتشاف أشكال الاستجابة تجريبياً مقابل حساب حقيقي، نفس التحذير الذي تحمله تقارير النقل "المستنتَج" الأخرى في هذا المستودع (مثل `WA_USERNAME.md`).

---

## 7. المجاهيل

| الموضوع | السبب |
|---|---|
| متغيرات `OrgList` | لا موقع استدعاء ساكن يتجاوز doc_id/تغيّره؛ يُرجَّح أنه `{}` لكن غير مؤكَّد |
| قيم تعداد `relationship` غير `"CONTACT"` | لم يُرصد سوى تعيين ordinal←string واحد (ordinal 0 ← `"CONTACT"`)؛ الفروع الأخرى غير مُغطاة في هذا التمرير |
| أشكال حقول الاستجابة لكل العمليات التسع | لا سلاسل/أسماء حقول من جهة الاستجابة عُثر عليها في أي موقع استدعاء؛ كل ما يتجاوز حقول حالة `OrgJoinViewModel` غامض |
| مدة صلاحية `link_token`/دلالات الاستخدام الواحد | غير مُتعقَّب؛ يُفترض استخدام واحد فقط بناءً على اصطلاح التسمية وحده |
| فرض الخادم لترتيب خطوات القسم 3 | مُجمَّع من شكل حقول الحالة، لا من سلسلة استدعاء تسلسلية مُتعقَّبة — قد يتمكن عميل من إعادة الترتيب أو تجاوز خطوات؛ غير مُختبَر |
| مجموعات قيم `member_tag`/`team` | الحقول موجودة (`team_options`، `member_tag`) لكن لم تُعثر قيم مُعدَّدة |
| شكل عنوان رابط الدعوة | لم يُلتقط في هذا التمرير |

---

## 8. الأدلة

تحليل ساكن لـ smali الخاص بـ WhatsApp Android 2.26.45.10، كل السلاسل الحرفية ومفاتيح المتغيرات مقروءة كـ`const-string` مباشرةً قبل استدعاء ضبط `GraphQlCallInput`/`LX/0jN` الخاص بها. لم تُلتقط أي حركة شبكة؛ كل العبارات المتعلقة بالنقل/شكل الاستجابة `inferred`. المصدر: `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`، `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`، `com/whatsapp/orgs/ui/join/OrgJoinActivity.smali`، `OrgJoinViewModel.smali`، `OrgJoinViewModel$checkName$2.smali`، `com/whatsapp/orgs/ui/invite/OrgInviteReferrerOpener.smali`، `com/whatsapp/orgs/ui/invite/OrgInviteLandingActivity.smali`، `com/whatsapp/work/publicidentity/graphql/MexWorkIdentityTransport.smali`.
