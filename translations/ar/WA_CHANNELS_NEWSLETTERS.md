<!-- src-sha1: 42c77add3dafd5b90522b32d91692dff968b2f54 -->
# WhatsApp القنوات والنشرات (Channels & Newsletters) — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-01
**النطاق:** نطاق JID الخاص بـ `@newsletter` والتسمية الداخلية "newsletter"، المتابعة/إلغاء المتابعة، إنشاء القناة، أدوار الإدارة ونقل الصلاحيات، حقول البروتو الستة `newsletterAdmin*`/`newsletterFollower*`/`newsletterScheduledMessage`، بيانات القناة الوصفية (الاسم، الوصف، الصورة، التوثيق، الحالة)، التفاعلات على المنشورات، عدادات المشاهدة/المتابعين، تدفق دعوة/إلغاء/قبول الإدارة، عمليات GraphQL/MEX الخاصة بالنشرات (doc_ids)، التخزين المحلي، أعلام الميزات (feature flags)، حالات الخطأ

---

## 1. ما هي من الناحية التقنية

"القناة" (channel) هي الاسم الموجّه للمستهلك لما يسميه العميل داخليًا **newsletter**: JID بث من واحد إلى متعدد مع تخزين من جانب الخادم (غير مشفر من طرف إلى طرف)، ومجموعة صغيرة من الأدوار (مالك/مشرف/مشترك/ضيف)، وغالبية عمليات مستوى التحكم تمر عبر `w:mex` GraphQL بدلًا من طلبات XMPP IQ التقليدية. أما تسليم المحتوى (جلب المنشورات، جلب الحالات، الرسائل المجدولة، الاشتراك في التحديثات المباشرة) فلا يزال يستخدم مساحة اسم IQ مخصصة ضمن XMPP، وهي `xmlns="newsletter"`. جميع المعطيات هنا ناتجة عن تحليل ساكن (static analysis) للـ APK المُفكَّك؛ لم يُسجَّل أي شيء على السلك (wire). المستويات: **found** = قُرئ في الكود، **inferred** = مُستنتج من الكود، **unknown** = غير محسوم. وعلى عكس معظم تقارير هذا المستودع التي تتعامل مع أسماء مشوَّشة (obfuscated)، فإن حزمة النشرات المرئية للعميل (`com.whatsapp.newsletter.*`، 122 ملفًا) تأتي بأسماء صفوف وأساليب (classes/methods) **مقروءة** في 2.26.41.6؛ فقط البنية التحتية المشتركة (JID، بروتو الرسائل، باني الـ IQ) مشوَّشة، ويُعاد حلّها هنا من سلاسل نصية مستقرة.

خارج النطاق: قوائم البث التقليدية (classic broadcast lists) و`status@broadcast` — انظر [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md). آليات البحث عن جهات الاتصال/الأجهزة المُعاد استخدامها من قبل النشرات (وليست خاصة بالنشرات) — انظر [WA_USYNC.md](WA_USYNC.md).

| الكيان | القيمة | المستوى |
|--------|-------|------|
| خادم JID | `newsletter` (مثال: `120363000000000000@newsletter`) | found |
| `Jid.getType()` | **21** | found |
| التشفير | `EnumC14260eC.NON_E2EE` — محتوى القناة **غير مشفر من طرف إلى طرف** | found |
| صف النموذج المحلي | `C2130898y` ("NewsletterInfo")، يمتد من صف المحادثة العام `C14220e7` | found |
| صف JID | `C1Y7` (`NewsletterJid`) | found |
| رابط الدعوة | `https://whatsapp.com/channel/<invite_code>` | found |
| جدول قاعدة البيانات المحلي | `newsletter` (يتضمن الأعمدة `membership`، `invite_code`، مفهرسة) | found |

| المكوّن | الاسم في 2.26.41.6 | الدور |
|-----------|----------------|------|
| محلّل JID | `C0DL.A03` (مُبدِّل على سلسلة الخادم)، `C1Y7` (JID)، `C1Y8` (رفيق/ذاكرة تخزين مؤقت لـ JID) | يتحقق من الرقم المعرّف (بلا صفر بادئ)، يبني/يخزّن `C1Y7` مؤقتًا |
| محدِّدات (predicates) JID | `C0DZ.A0a(jid)` = `getType()==21`؛ `C0DZ.A0M` يضم النوع 21 إلى المجموعة التي تحتوي أيضًا المجموعات (18)، قوائم البث (3)، الحالة (5) إلخ | isNewsletter / مجموعة "قادرة على استلام متعددي المستقبلين" |
| النموذج المحلي | `C2130898y` | الدور، التوثيق، الإسكات (mute)، إعداد التفاعل، الحالة، العدادات |
| الأدوار | `C9U5` (تعداد محلي)، `C9U4` (تعداد سلسلة نصية على السلك) | القسم 4 |
| مهمة البيانات الوصفية | `BaseMetadataNewsletterGraphqlJob`، `GetNewsletterAdminMetadataJob` | `NewsletterMetadata` / `NewsletterAdminMetadataQuery` |
| مهمة التحديث | `UpdateNewsletterGraphqlJob` | `NewsletterMetadataUpdate` |
| مهمة الإنشاء/الحذف | ضمن `com.whatsapp.newsletter.editcreate`، `com.whatsapp.newsletter.delete` | `NewsletterCreate(Verified)` / `NewsletterDelete` |
| جلب الرسائل | `GetNewsletterMessagesJob`، `GetNewsletterMessagesUpdatesJob`، `GetNewsletterMyAddOnMessagesJob`، `SendNewsletterMessageJob`، `SendViewReceiptJob` | `com.whatsapp.newsletter.messages.job` |
| جلب الحالة (تحديثات القناة) | `GetNewsletterStatusesJob`، `GetNewsletterStatusUpdatesJob`، `GetStatusMyAddOnsJob` | `com.whatsapp.newsletter.status.job` |
| باني IQ | `C9EN` (باني `xmlns="newsletter"`)، `C9E2` (مجموعات قيم دور العرض / العنصر الفرعي) | القسم 6 |
| إرسال دعوة الإدارة | `C9m6` (`UserActionsNewsletterMessaging`)، `C213489Am` | القسم 5.4 |
| مخزن التفاعلات | `C12H`، `C23768ANd` ← جدول `newsletter_message_reaction` | القسم 7 |

---

## 2. JID والنطاق (domain)

### 2.1 التحليل (found، `C0DL.A03`)

```java
// X.0DL (C0DL)
public C1Y7 A03(String str, String str2) throws C09B {
    String strTrim = str.trim();
    if (strTrim.isEmpty() || "0".equals(strTrim) || strTrim.indexOf("0") == 0)
        throw new C09B("Identifier must be a valid number starting with non-zero");
    if (!"newsletter".equals(str2)) throw new C09B(...);
    // cache lookup/insert, returns C1Y7(str)
}
```

تُعيد `C1Y7.getServer()` السلسلة الحرفية `"newsletter"`؛ وتُعيد `getType()` القيمة `21`. نفس قاعدة "الرقم المعرّف بلا صفر بادئ" المطبقة على أنواع JID الأخرى متعددة الأطراف (المجموعات، قوائم البث — انظر [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §2.1). موجِّه JID العام `C0DZ.A01` ينتقل إلى `C1Y7.A03.A02(str)` كحالته الافتراضية عندما تكون السلسلة ليست أحد الأفراد المعروفين (singleton)، ولا `UserJid`، ولا `GroupJid` — أي أن `@newsletter` هو النطاق الافتراضي (fallback) في ذلك المحلّل (found).

### 2.2 الانتماء لمجموعة الأنواع (found، `C0DZ.java`)

```java
public static boolean A0a(Jid jid) { return jid != null && jid.getType() == 21; }   // isNewsletter
public static boolean A0M(Jid jid) {
    int type = jid.getType();
    return type==0||type==1||type==18||type==22||type==3||type==7||type==21||type==26||type==28;
}
```
`A0a` هو المحدِّد المخصص للنشرات. أما `A0M` فيجمع النوع 21 مع المجموعات (18/22)، قوائم البث (3)، المجموعة الكبرى/community (7) وأنواع أخرى في مجموعة أوسع "قادرة على المشاركين المتعددين" (الهدف الدقيق من هذا التجميع غير مُتابَع بالكامل؛ مُستنتَج أنه يتحكم في بنية مشاركين/جلسات مشتركة).

---

## 3. المتابعة / إلغاء المتابعة

المتابعة **ليست** اشتراكًا عبر stanza؛ بل هي عملية تحويل (mutation) عبر `w:mex`، والدور المحلي (`C9U5`) يتبدّل بين `GUEST` و`SUBSCRIBED`.

| العملية | doc_id | المتغيرات (found) |
|-----------|--------|--------------------|
| `NewsletterJoin` | `24658527423838739` | `entry_point`، `record`، `recipient_account_id`، `sessions`، `jid`، `fetch_and_validate_vname`، `call_offer`، `request_bottom_sheet_fragment` |
| `NewsletterLeave` | `25758579043742316` | نفس شكل `NewsletterJoin` تمامًا |

يُبنى كلاهما بواسطة نفس الصف، `X/RunnableC24381AnW.java` (found). مجموعة المتغيرات المشتركة (`entry_point`، `call_offer`، `request_bottom_sheet_fragment`) تشير إلى أن المتابعة/إلغاء المتابعة يعيدان استخدام غلاف تحويل عام لـ "إجراء محادثة" (chat action) يُستخدم أيضًا للمكالمات والإجراءات المُطلَقة من الورقة السفلية (bottom sheet) في أماكن أخرى من التطبيق (inferred).

تحولات الدور المحلي على كائن `C2130898y` ("NewsletterInfo"):

| المساعد (Helper) | الشرط | المعنى |
|--------|-----------|---------|
| `A0p()` | `!muted && role==ADMIN` | مشرف |
| `A0q()` | `!muted && (role==ADMIN \|\| role==OWNER)` | مشرف أو مالك |
| `A0r()` | `role==SUBSCRIBED` | يتابع |
| `A0s()` | `role==GUEST` | لا يتابع (يُستخدم لإجبار `fetch_viewer_metadata=true` عند تحديث البيانات الوصفية — found في `BaseMetadataNewsletterGraphqlJob`) |
| `A0u()` | `!muted && role==OWNER` | مالك |

سلسلة خطأ واجهة المستخدم عند فشل المتابعة: `str1c0d` "Couldn't follow channel"، `str1c0e` "Couldn't follow channel. Check your device's internet connection and try again." (found، `res/values/strings.xml`).

---

## 4. الأدوار

يوجد تعدادان متوازيان للأدوار: تعداد محلي محفوظ، وتعداد سلسلة نصية على السلك يُستخدم في متغيرات/استجابات GraphQL.

### 4.1 الدور المحلي (found، `C9U5`)

```java
GUEST=0 (A03), SUBSCRIBED=1 (A05), ADMIN=2 (A02), OWNER=3 (A04)
```
تُحوِّل `C9U5.A00()` الترتيب (ordinal) إلى رتبة أولوية: GUEST←4، SUBSCRIBED←3، ADMIN←2، OWNER←1 (الأقل = الأكثر امتيازًا؛ الهدف — ترتيب فرز قوائم الإدارة — inferred).

### 4.2 الدور على السلك (found، `C9U4`، `serverValue` = اسم العنصر في التعداد)

```
UNSET_OR_UNRECOGNIZED_ENUM_VALUE, ADMIN, GUEST, OWNER, SUBSCRIBER
```
يُستخدم كقيمة سمة `view_role` على العنصر الفرعي `smax:any` في طلبات IQ الخاصة بـ XMPP للنشرات (القسم 6)، وكقيمة `viewer_metadata.role` في GraphQL (القسم 8).

### 4.3 الصلاحيات ونقل الإدارة

| الإجراء | عملية GraphQL | doc_id |
|--------|-----------|--------|
| دعوة مستخدم كمشرف | `NewsletterAdminInvite` | `26278681041745438` |
| إلغاء دعوة إدارة معلّقة | `NewsletterAdminInviteRevoke` | `24369392486051948` |
| قبول دعوة إدارة | `NewsletterAcceptAdminInvite` | `24934958956134858` |
| تنزيل رتبة مشرف | `NewsletterAdminDemote` | `25054538847517281` |
| نقل الملكية | `NewsletterChangeOwner` | `24737692515842078` |
| جلب دفعة من ملفات تعريف المشرفين | `NewsletterAdminProfilesQuery` | `28089989690595314` |
| تحديث ملف تعريف المشرف (الاسم/الصورة) | `NewsletterAdminProfileUpdate` | `25959584293627630` |
| البيانات الوصفية الكاملة للإدارة (حقول خاصة بالمشرفين فقط) | `NewsletterAdminMetadataQuery` | `26882701001369256` |
| بوابة الصلاحيات (Capabilities gate) | `NewslettersAdminCapabilitiesQuery` | `27579307995002556` |

تعداد إجراءات تدفق دعوة الإدارة (found، `EnumC215899Sc`، يُستخدم من قِبل `AdminInviteErrorDialog`): `NOT_SUPPORTED=0`، `INVITE=1`، `ACCEPT_INVITE=2`، `REVOKE=3`، `DISMISS=4`.

سلاسل خطأ واجهة المستخدم (found): `str0095` "Couldn't accept the admin invite. Please try again."، `str106c`/`str2bed` "Couldn't transfer ownership. Please try again(.)/ later."، `str2300`/`str2abd` "Channel admin invite"، `str22fb` "Invite %s as admin?"، `str2bd8` "Invite as channel admin".

---

## 5. دعوة الإدارة — رسالة بين عميل وعميل، لا GraphQL فقط

تملك تجربة دعوة الإدارة آليتين **منفصلتين** تعملان معًا: عملية تحويل عبر MEX (`NewsletterAdminInvite`، منح من جانب الخادم)، و**رسالة** عادية ثنائية (1:1) مشفرة من طرف إلى طرف تحمل حمولة الدعوة إلى المدعو، مبنيّة بشكل مستقل عن MEX.

### 5.1 البروتو (found، يؤكد ويوسّع المادة الأولية في `Messages/newsletterAdminInviteMessage`)

`Message.newsletterAdminInviteMessage` — الحقل **78** في `Message` (`C30628DTw`)، من النوع `NewsletterAdminInviteMessage` (مشوَّش إلى `C30596DSq` في 2.26.41.6؛ ثوابت JADX على الصف نفسه، وليس رقم الحقل على `Message`، إذ لم يكن ثابت حقل دعوة الإدارة ضمن المجموعة المستخرجة بـ grep — الحقل 78 يطابق مرجعًا سابقًا في WAProto.proto، ويتأكد بشكل مستقل من تطابق جميع الحقول الأخرى أدناه بدقة):

| الحقل | الرقم | النوع |
|-------|-------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `inviteExpiration` | **5** | int64 |
| `contextInfo` | **6** | `ContextInfo` |

ثوابت أرقام الحقول المؤكَّدة `CAPTION_FIELD_NUMBER=4`، `CONTEXT_INFO_FIELD_NUMBER=6`، `INVITE_EXPIRATION_FIELD_NUMBER=5`، `JPEG_THUMBNAIL_FIELD_NUMBER=3`، `NEWSLETTER_JID_FIELD_NUMBER=1`، `NEWSLETTER_NAME_FIELD_NUMBER=2` مقروءة مباشرة من `C30596DSq` (found) — تطابق خريطة حقول سابقة تمامًا لهذا الإصدار.

### 5.2 مسار الإرسال (found، `C9m6` = `UserActionsNewsletterMessaging`)

```java
public final void A00(Context context, C1Y7 c1y7, String name, String caption, HashMap userJidToExpiration) {
    byte[] thumbnail = A01(context, c1y7);           // JPEG of the channel picture, quality 80
    for (entry in userJidToExpiration) {
        C213489Am item = new C213489Am(..., 94, ...); // message-type tag 94
        item.A01 = c1y7;          // newsletterJid
        item.A03 = name;          // newsletterName
        item.A00 = entry.value;   // inviteExpiration
        item.A02 = caption;
        item.A0O(thumbnail, false);
        // enqueued as a normal E2E message to the invitee's UserJid
    }
}
```
سطر السجل: `"UserActionsNewsletterMessaging/userActionSendNewsletterAdminInviteMessages"`. تُرسَل رسالة واحدة لكل مدعو، تحمل كل منها طابع انتهاء صلاحية خاصًا بها — أي أن الدعوة هي **رسالة مشفرة من طرف إلى طرف لكل مستقبل**، في حين أن عملية `NewsletterAdminInvite` عبر MEX (من جانب الخادم) هي سجل المنح الرسمي (العلاقة بين المسارين مُستنتَجة؛ كلاهما موجود في الكود، والترتيب/التبعية بينهما غير مُتابَع).

### 5.3 القبول

يستدعي عميل المدعو `NewsletterAcceptAdminInvite` (MEX). يحمل طلبه بالفعل مجموعة متغيرات جلب البيانات الوصفية الكاملة (`fetch_followers_count`، `fetch_state`، `fetch_verification`، `fetch_viewer_metadata`، …) — أي أن قبول الدعوة وإعادة جلب بيانات القناة الوصفية يحدثان في جولة طلب/استجابة واحدة (found، المتغيرات من `X/AbstractC23610Aaw.java`).

---

## 6. رسائل النشرات الأخرى: دعوة المتابعين، ملف تعريف المشرف، المجدولة

### 6.1 `newsletterFollowerInviteMessage` / `newsletterFollowerInviteMessageV2`

مؤكَّد في 2.26.41.6 تمامًا كما تنص المادة الأولية، وأُعيد التحقق منه هنا بشكل مستقل: كلا حقلَي `Message` موجودان (`NEWSLETTER_FOLLOWER_INVITE_MESSAGE_FIELD_NUMBER` = **108**، `NEWSLETTER_FOLLOWER_INVITE_MESSAGE_V2_FIELD_NUMBER` = **113**، كلاهما found كثابتَين مسمّيَين على `C30628DTw`)، و**كلاهما يشير إلى نفس نوع الرسالة الفرعية**، `C30585DSf`:

| الحقل | الرقم | النوع |
|-------|-------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `contextInfo` | **5** | `ContextInfo` |

سبب وجود رقمَي حقل لنوع واحد لا يزال **unknown** — لم يُعثر على انقسام سلوكي على مستوى جافا في هذا التمرير أيضًا (متوافق مع نتيجة سابقة).

### 6.2 `newsletterAdminProfileMessage` / `newsletterAdminProfileStatusMessage` / `newsletterScheduledMessage`

الثلاثة مؤكَّدون كثوابت مسمّاة على `C30628DTw` (`NEWSLETTER_ADMIN_PROFILE_MESSAGE_FIELD_NUMBER` = **116**، `NEWSLETTER_ADMIN_PROFILE_STATUS_MESSAGE_FIELD_NUMBER` = **126**، `NEWSLETTER_SCHEDULED_MESSAGE_FIELD_NUMBER` = **132**)، وجميعها الثلاثة تشير إلى نفس نوع الغلاف العام ذي الحقل الواحد، `BD2` (= `FutureProofMessage`):

```java
public final class BD2 { public C30628DTw message_; }   // field "message", number 1, type Message (recursive)
```

لا يوجد صف عرض/تحقق (render/validator) خاص بأي من الثلاثة (found، يطابق ملاحظة سابقة لـ `newsletterAdminProfileMessage` و`newsletterScheduledMessage`). يملك `newsletterScheduledMessage` سطح عرض مخصّصًا غير مرتبط بالبروتو: الجدول المحلي `newsletter_scheduled_message` (`chat_row_id`، `scheduled_server_id`، مفهرس بشكل فريد) والعنصر الفرعي للـ IQ على السلك `<scheduled_messages/>` (القسم 6.3) — *ميزة* الجدولة حقيقية ومُتابَعة؛ فقط حقل البروتو `Message.newsletterScheduledMessage` نفسه يبقى غلافًا غير موسَّع.

### 6.3 الجداول المحلية ذات الصلة

`newsletter_scheduled_message`، `newsletter_admin_profile` (`chat_row_id`، `admin_profile_id`، `timestamp`) تدعمان `NewsletterAdminProfilesQuery`/`NewsletterAdminProfileUpdate` وواجهة الجدولة على التوالي (found، `C0SG.java`، `C0S3.java`).

---

## 7. منشورات القناة: الجلب، الإرسال، التفاعلات، عدادات المشاهدة

### 7.1 مساحة اسم IQ لـ XMPP: `newsletter` (found، `C9EN`)

يستخدم جلب المحتوى وعدد قليل من إجراءات الكتابة مساحة اسم IQ مخصصة، منفصلة عن MEX:

```xml
<iq xmlns="newsletter" type="get" to="<jid>@newsletter" id="…">
  <messages count="N">
    <smax:any type="jid" jid="<jid>@newsletter" view_role="admin|guest|owner|subscriber"/>
    <before count="N"/> <!-- or <after count="N"/> -->
  </messages>
</iq>
```

| العنصر الفرعي | المُنشِئ (Constructor) | الغرض |
|---------------|-------------|------|
| `<messages count/>` + `<before>`/`<after>` | `C9EN(C9EB, C9E2, id, count)` | تقسيم منشورات القناة إلى صفحات |
| `<message_updates count since/>` | `C9EN(C1Y7, C9E8, Long, id, count)` | مزامنة تفاضلية للمنشورات المعدَّلة/المحذوفة |
| `<statuses count/>` | `C9EN(C9E9, C9E2, id, count)` | جلب حالة/تحديث القناة |
| `<status_updates count since/>` | `C9EN(C1Y7, C9EA, Long, id, count)` | مزامنة تفاضلية لمنشورات الحالة |
| `<scheduled_messages count/>` | `C9EN(C1Y7, C31085Dfd, id, count)` | المنشورات المجدولة المعلّقة |
| `<question_responses server_id count/>` (عادي ومع `type="status"`) | `C9EN(...)` | إجابات استبيان/سؤال على منشور |
| `<my_question_responses server_id/>` | `C9EN(C1Y7, String, long)` | إجابات المستدعي الخاصة |
| `<my_addons type="status" limit jid/>` | `C9EN(C1Y7, String, int, long)` | تفاعلات/إضافات المستدعي الخاصة |
| `<live_updates/>` (`type="set"`) | `C9EN(C1Y7, String)` | الاشتراك في البث المباشر لقناة |

تحمل سمة `view_role` على `smax:any` سلسلة دور المستدعي الخاصة (`C9U4`) (مشرف/ضيف/مالك/مشترك) مع كل طلب IQ لجلب المحتوى — يبدو أن الخادم يتحكم في محتوى الاستجابة (مثل الحقول الخاصة بالمشرفين فقط) على مستوى كل طلب، لا عبر حالة الجلسة فقط (inferred).

### 7.2 الإرسال (found، `SendNewsletterMessageJob`) وإيصالات المشاهدة

يعيد النشر في القناة استخدام خط أنابيب الإرسال القياسي (غير مُفصَّل أكثر هنا؛ تلفّ المهمة آلية stanza `<message>` العادية). مشاهدة منشور فعل صريح ومنفصل عن إيصالات التسليم/القراءة:

```java
// com.whatsapp.newsletter.messages.job.SendViewReceiptJob
<receipt to="<jid>@newsletter" id="…" type="view">
  <list><item server_id="…"/> …</list>
</receipt>
```
يجمع إيصال `view` واحد عدة معرفات رسائل من الخادم في دفعة واحدة. هذه هي الآلية التي تُغذّي **عداد المشاهدة** لكل منشور الظاهر في واجهة القناة (found؛ العداد نفسه مُجمَّع من جانب الخادم — العميل يُرسل التقرير فقط، ولا يقرأ عددًا عبر هذا الـ IQ أبدًا).

### 7.3 التفاعلات (found)

التفاعلات على منشورات القناة **مُجمَّعة، وليست مُسنَدة** في التخزين المحلي:

```sql
CREATE UNIQUE INDEX newsletter_message_reaction_index
  ON newsletter_message_reaction (message_row_id, reaction);
-- columns include: reaction, reaction_count
```
أي سطر واحد لكل زوج `(رسالة، إيموجي)` مع عدّاد جارٍ، لا سطر واحد لكل مستخدم متفاعل — بما يطابق واجهة القناة التي تعرض عددًا إجماليًا لكل إيموجي بدلًا من قائمة المتفاعلين كما في المستخدمين العاديين. يحتفظ `newsletter_my_reaction_orphan_message` (`chat_row_id`، `server_message_id`، مفهرس بشكل فريد) بتفاعل المستدعي **الخاص** عندما يصل قبل المنشور الذي يستهدفه، لتسويته بعد وصول المنشور.

تظهر هوية المتفاعلين فقط للمشرفين، عبر استعلام MEX مخصص:

| العملية | doc_id | المتغيرات |
|-----------|--------|-----------|
| `NewsletterReactionSendersList` | `25219734117717032` | `server_id` |

سياسة التفاعل قابلة للتهيئة لكل قناة (القسم 8.2، `reaction_codes`): `ALL`، `BASIC`، `BLOCKLIST`، `NONE` (سلاسل نصية على السلك، انظر `C9U3`/`C9TA` أدناه).

### 7.4 عدادات المتابعين / المشاهدة في البيانات الوصفية

تُعاد `thread_metadata.followers_count` كجزء من `NewsletterMetadata` (القسم 8.1). توجد أيضًا عملية مُقسَّمة إلى صفحات مخصصة:

| العملية | doc_id | المتغيرات |
|-----------|--------|-----------|
| `NewsletterFollowers` | `25646542368289354` | `newsletter_id`، `count` |

عدادات المشاهدة لكل منشور لا تُعاد عبر عملية مستقلة موثَّقة في هذا التمرير؛ يُستنتَج أنها تعيش داخل البيانات الوصفية لكل رسالة ضمن استجابة IQ `messages`/`message_updates` (القسم 7.1)، التي لم تُوسَّع أكثر هنا (اسم الحقل الدقيق unknown).

---

## 8. بيانات القناة الوصفية (شكل استجابة GraphQL)

### 8.1 استجابة `NewsletterMetadata` (found، السلسلة `C208048tR → C208038tQ → C208028tP`، عقدة GraphQL `xwa2_newsletter`)

```
xwa2_newsletter {
  id
  refresh_after_interval_sec
  state { type }                                    // C9UA
  status_metadata { last_status_sent_time, last_status_server_id }
  thread_metadata {
    creation_time
    description { text, id }
    followers_count
    handle
    invite                                           // invite code / link token
    name { text, id }
    picture { direct_path, type, url, id }
    pinned_messages[]
    preview
    settings { reaction_codes { value } }            // C9U3
    verification                                     // EnumC216369Tx
    verification_source                              // EnumC216219Ti
    wamo_sub { plan_id }
  }
  viewer_metadata {
    role                                             // C9U4
    settings[]                                       // { type, value } = EnumC216349Tv / EnumC216359Tw
    wamo_sub_status                                  // EnumC216229Tj
  }
}
```

### 8.2 التعدادات (found)

| التعداد | القيم (سلاسل `server-value` حيثما تنطبق) |
|------|---|
| `state.type` (`C9UA`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `ACTIVE`، `DELETED`، `GEOSUSPENDED`، `NON_EXISTING`، `SUSPENDED` |
| `verification` (`EnumC216369Tx`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `UNVERIFIED`، `VERIFIED` |
| `verification_source` (`EnumC216219Ti`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `LEGACY_MANUAL_REVIEW`، `META_VERIFIED_SUBSCRIPTION` |
| `viewer_metadata.role` (`C9U4`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `ADMIN`، `GUEST`، `OWNER`، `SUBSCRIBER` |
| `wamo_sub_status` (`EnumC216229Tj`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `ACTIVE`، `INACTIVE` |
| `settings[].type` (`EnumC216349Tv`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `MUTE_ADMIN_ACTIVITY`، `MUTE_FOLLOWER_ACTIVITY` |
| `settings[].value` (`EnumC216359Tw`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `OFF`، `ON` |
| `reaction_codes.value` (`C9U3`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `ALL`، `BASIC`، `BLOCKLIST`، `NONE` |

انعكاسات محلية على `C2130898y` ("NewsletterInfo"): حالة التوثيق `EnumC216079Su` (`NOT_VERIFIED=0`، `VERIFIED=1`)، مصدر التوثيق `C9T1` (`UNKNOWN_VERIFICATION_SOURCE=0`، `META_VERIFIED_SUBSCRIPTION=1`، `LEGACY_MANUAL_REVIEW=2`)، حالة التنفيذ (enforcement) `C9T2` (`NOT_ENFORCED`، `SUSPENDED`، `GEOSUSPENDED` — مقيَّدة القراءة خلف العلم **3877** في `A0w`/`A0x`)، الحالة المحلية "النشطة" `C9T3` (`NOT_SET`، `INACTIVE`، `ACTIVE`)، تقدّم الترحيل/الإنشاء `C9T9` (`NOT_STARTED`، `IN_PROGRESS`، `FAILED`، `COMPLETED`)، ظهور الدليل (directory visibility) `EnumC216039Sq` (`PUBLIC`، `PRIVATE`)، وإعداد التفاعل المحلي `C9TA` (`DEFAULT=0`←سلك `"BASIC"`، `ALL=1`←`"ALL"`، `NONE=2`←`"NONE"`، `BLOCKLIST=3`←`"BLOCKLIST"` — التخطيط مقروء من `UpdateNewsletterGraphqlJob.A0M`).

### 8.3 التحديث (found، `UpdateNewsletterGraphqlJob` ← `NewsletterMetadataUpdate`)

```js
// GraphQl input built for doc_id 27150690864552229
updates: {
  description?: string,   // "" clears
  name?: string,
  picture?: base64,        // "" clears
  admin_profiles_enabled?: { settings: { admin_profiles_enabled, reaction_codes: { value: "ALL"|"BASIC"|"NONE"|"BLOCKLIST" } } }
}
newsletter_id: <jid>
fetch_image: true, fetch_preview: true, fetch_name: true,
fetch_viewer_metadata / fetch_state / fetch_verification / fetch_followers_count: <bool, usually mirrors viewer role>
```

### 8.4 سلاسل واجهة المستخدم للتوثيق (found)

`str136f` "New verified channel"، `str2be2`/`str2be3` "Create verified channel"/أيقونة، `str2c51` "Verified channels"، `str2c78` "Your verified badge will be removed from this channel. Your Meta Verified subscription will remain active."، `str2ca9` "Sorry, you cannot change the name of a verified channel from the app. Please contact customer support for assistance." — أي أن القنوات الموثَّقة تملك اسمًا غير قابل للتغيير يُفرَض من جانب الخادم (واجهة مستخدم من جانب العميل فقط؛ جانب التنفيذ unknown).

---

## 9. عمليات GraphQL / MEX الخاصة بالنشرات (doc_ids)

جميع doc_ids أدناه أُعيد التحقق منها بشكل مستقل لهذا الإصدار مقابل `assets/whatsapp-android-mex_client_persist_ids.json` داخل `WhatsApp_2.26.41.6.apk` (found — doc_ids إدخالات أصول (asset) ثابتة، غير مشوَّشة، ومستقرة عبر مقارنة الإصدارات التي جُرِّبت هنا). توجد 46 عملية `Newsletter*` في ذلك الأصل إجمالًا؛ هذه هي العمليات غير المُفصَّلة في مكان آخر من هذا التقرير:

| العملية | doc_id | الغرض (مُستنتَج من الاسم/المتغيرات) |
|-----------|--------|------------------------------------------|
| `NewsletterCreate` | `27009199332109318` | إنشاء قناة |
| `NewsletterCreateVerified` | `27777918425146464` | إنشاء قناة موثَّقة مسبقًا (حسابات مميَّزة) |
| `NewsletterDelete` | `31838460859131915` | حذف قناة |
| `NewsletterUpdateVerification` | `27133493439664458` | طلب/تحديث حالة التوثيق |
| `NewsletterHide` / `NewsletterUnhide` | `25033614912931367` / `24551592861177484` | تبديل ظهور الدليل (العداد المحلي `EnumC216039Sq`) |
| `NewsletterFollowing` | `26856957210673444` | قائمة القنوات التي يتابعها الحساب |
| `NewsletterDirectoryList` / `Search` / `CategoryPreview` | `27480627564903390` / `27887355094203575` / `27432651036395658` | تصفّح الدليل العام |
| `NewsletterSimilar` / `NewsletterRecommended` | `36410329795280256` / `26638880912457992` | الاكتشاف |
| `NewsletterInsights` | `24672564052397921` | تحليلات المالك/المشرف |
| `NewsletterPinMessages` / `NewsletterUnpinMessages` | `28521965914059511` / `37386851567568720` | إدارة تثبيت المنشورات (`message_ids`) |
| `NewsletterBlockUser` | `25106066249006236` | حظر متابع |
| `NewsletterLogExposures` | `24606408825709914` | تيليمتري انطباعات الدليل |
| `NewsletterLinkPreviewCheck` | `24188786150796507` | التحقق من نطاقات معاينة الروابط في المنشورات |
| `NewsletterPollVoterList` | `24803802869271956` | المصوّتون في استبيان على منشور (`jid`، `vote_hash`) |
| `NewsletterQuestionResponseStateUpdate` | `24896618076668076` | حالة إدارة الأسئلة والأجوبة |
| `NewsletterLabelAiContent` / `NewsletterLabelPaidPartnership` | `27470054215955630` / `26221505494211174` | وسم كل منشور بـ "منتج بالذكاء الاصطناعي" / "شراكة مدفوعة" |
| `NewsletterChangeWamoSub` / `Enable`/`DisableWamoSub` | `25201342542835866` / `25122474967344830` / `31916794074578680` | حالة اشتراك تحقيق الدخل (monetization) في واتساب |
| `NewsletterUserReports` / `NewsletterCreateReportAppeal` | `27149305681394065` / `27792557363683798` | الإبلاغ عن التجاوزات / الاستئناف |
| `NewsletterEnforcements` / `NewsletterEnforcementAlertStates` | `27089116857425014` / `27640745535604048` | حالة التنفيذ/التعليق (حزمة خاصة `com.whatsapp.newsletterenforcements`) |
| `NewsletterUpdateUserSetting` | `24935528202764688` | تفضيل واجهة مستخدم لكل مستخدم (مثل عدّاد تلميح منتقي جهات الاتصال) |
| `FetchNewsletterRankingFeatures` | `24742757908756088` | جلب إشارات الترتيب (الدليل/التوصية) |

جميعها طلبات `w:mex` IQ (`type="get"`)، مخطط `whatsapp_mex`، وآلية النقل مؤكَّدة عبر نمط الاستدعاء المشترك `C16880is`/`TreeWithGraphQL` الملاحَظ في §5–8 (found). أشكال الاستجابة بما يتجاوز `NewsletterMetadata` في §8 لم تُوسَّع في هذا التمرير (unknown).

---

## 10. التخزين

| الجدول | الأعمدة الأساسية (found) |
|-------|----------------------|
| `newsletter` | `membership` (مفهرس)، `invite_code` (مفهرس) |
| `newsletter_message` | فريد على `(chat_row_id, server_message_id)`؛ `is_autodelete_eligible` (مفهرس) |
| `newsletter_message_reaction` | فريد على `(message_row_id, reaction)`؛ `reaction`، `reaction_count` |
| `newsletter_my_reaction_orphan_message` | فريد على `(chat_row_id, server_message_id)` — تفاعل المستدعي الخاص الواصل قبل المنشور الذي يستهدفه |
| `newsletter_admin_profile` | فريد على `(chat_row_id, admin_profile_id)`؛ `timestamp` (مفهرس) |
| `newsletter_subscribers` | مفهرس على `(chat_row_id, type_of_fetch)` |
| `newsletter_scheduled_message` | فريد على `(chat_row_id, scheduled_server_id)` |
| `newsletter_interaction` | مفهرس على `timestamp_ms` و`(newsletter_jid_row_id, timestamp_ms)` |
| `newsletter_linked_account` | مفهرس على `chat_row_id` |
| `newsletter_pinned_message` | مفهرس على `(chat_row_id, pin_timestamp_ms)` |
| `newsletter_media_clear` | فريد على `(chat_row_id, media_type)` |

يُعاد استخدام البنية التحتية المشتركة للمحادثة (`chat`/`chat_view`، أعمدة `message` الأساسية) تمامًا كما مع أي محادثة من نوع `Jid`، مماثل للمجموعات/قوائم البث (انظر [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §3.5) — لم يُفصَّل مجددًا هنا.

---

## 11. أعلام الميزات (feature flags)

المعرّفات كما قُرئت في مواقع الاستدعاء داخل `com.whatsapp.newsletter.*`؛ لم تُحسَم كل القيم الافتراضية في هذا التمرير (مُشار إليها حيثما عُرفت).

| المعرّف (ID) | يتحكم في |
|----|----------|
| **3877** | يقيّد قراءة مساعدات حالة التنفيذ المحلية `A0w`/`A0x` (فحوصات `SUSPENDED`/`GEOSUSPENDED`) على `C2130898y` |
| **1777** | مُحدِّد الدولة في مرشِّحات الدليل |
| **5276** | عرض هوية القناة خلال واجهة ترحيل newsletter→شيء ما |
| **6445** | `ShareNewsletterInviteLinkActivity` |
| **6618** | `ViewNewsletterProfilePhoto` |
| **7237** | `NewsletterStatusView` |
| **9096** | `SendNewsletterMessageJob` |
| **12989** | `NewsletterDirectoryCategoriesActivity` |
| **15754** | علامة أداء "messages_fetch_end" في `GetNewsletterMessagesJob` |
| **17985** | `ForwardCounterAcsRepository` (عداد المنشورات المُعاد توجيهها) |
| **19889** | `ForwardCounterApi` |
| **23797** | `NewsletterDescriptionView` |

القيم الافتراضية الدقيقة ومدى السلوك المقيَّد الكامل لم يُتابَعا بما يتجاوز "الصف قابل للوصول فقط عندما يكون العلم مفعّلًا" (مُستنتَج من شكل موقع الاستدعاء)؛ عامِل هذا الجدول كخريطة لمكان البحث، لا كتأكيد للقيم الافتراضية المفعّلة/المعطَّلة (unknown لمعظم الصفوف).

---

## 12. حالات الخطأ

| العرض (Symptom) | السبب | الحل / السلوك المتوقَّع |
|---------|-------|--------------------------|
| "Couldn't follow channel" (`str1c0d`/`str1c0e`) | فشل `NewsletterJoin` أو انعدام الاتصال | إعادة المحاولة؛ التحقق من الاتصال |
| "Couldn't accept the admin invite. Please try again." (`str0095`) | فشل `NewsletterAcceptAdminInvite` | إعادة المحاولة |
| "Couldn't transfer ownership…" (`str106c`/`str2bed`) | فشل `NewsletterChangeOwner` | إعادة المحاولة لاحقًا |
| "Sorry, you cannot change the name of a verified channel from the app." (`str2ca9`) | القناة `VERIFIED`؛ الاسم غير قابل للتغيير من جانب العميل | الاتصال بالدعم (من جانب الخادم؛ التنفيذ الدقيق unknown) |
| تفاعل المستدعي الخاص بلا منشور مطابق بعد | سباق بين stanza/حدث التفاعل ووصول المنشور نفسه | يُحتفَظ به في `newsletter_my_reaction_orphan_message` حتى يصل المنشور، ثم تُسوَّى الحالة |
| `state.type` = `SUSPENDED`/`GEOSUSPENDED` | إجراء تنفيذ (enforcement) ضد القناة | جلب المحتوى لا يزال يُعيد `state`؛ يُفترَض أن إجراءات النشر/الإدارة محظورة من جانب الخادم (البوابة الدقيقة unknown) |
| `state.type` = `DELETED`/`NON_EXISTING` | القناة محذوفة أو لم توجد أبدًا | يجب أن يحذف العميل سطر `newsletter` المحلي (مسار التطبيق غير مُتابَع) |
| إجراء دعوة إدارة = `NOT_SUPPORTED` (`EnumC215899Sc`) | محاولة دعوة/قبول/إلغاء في سياق غير مدعوم (مثل الدور، البناء) | مربع حوار خطأ عام، بلا زر إعادة محاولة (`str5735`) |

---

## 13. تمييزات أساسية

| لا تخلط بين | الفرق |
|----------------|------------|
| النشرة (`@newsletter`، النوع 21) مقابل قائمة البث (`@broadcast`، النوع 3) | النشرة: مخزَّنة على الخادم، غير مشفرة من طرف إلى طرف، نموذج متابعة عام، أدوار؛ قائمة البث: توزيع مفتاح المرسِل (sender-key) مشفر من طرف إلى طرف إلى جهات اتصال محفوظة فقط — انظر [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) |
| IQ بـ `xmlns="newsletter"` مقابل عمليات GraphQL `Newsletter*` عبر `w:mex` | IQ = جلب/تقسيم إلى صفحات/اشتراك في المحتوى (الرسائل، الحالات، المجدولة، التحديثات المباشرة)؛ MEX = البيانات الوصفية، الأدوار، الدليل، الإدارة، تحقيق الدخل |
| `newsletterAdminInviteMessage` (رسالة مشفرة من طرف إلى طرف 1:1، الحقل 78) مقابل `NewsletterAdminInvite` (تحويل عبر MEX) | الرسالة هي الإشعار الخاص بكل مستقبل بطابع انتهاء صلاحيته الخاص؛ عملية MEX هي المنح من جانب الخادم — كلاهما موجود، والعلاقة مُستنتَجة |
| `newsletterFollowerInviteMessage` (الحقل 108) مقابل `newsletterFollowerInviteMessageV2` (الحقل 113) | نوع حمولة مماثل تمامًا (`C30585DSf`)؛ سبب التكرار unknown |
| الدور المحلي `C9U5` (GUEST/SUBSCRIBED/ADMIN/OWNER) مقابل الدور على السلك `C9U4` (…GUEST/ADMIN/OWNER/SUBSCRIBER) | نفس الأربعة أدوار، بترتيب (ordinal) مختلف وتهجٍّة/ترتيب سلسلة نصية مختلفَين — لا تفترض توافق الترتيب (ordinal) |
| قيمة `reaction_codes` على السلك (`ALL`/`BASIC`/`BLOCKLIST`/`NONE`، من `C9U3`) مقابل خريطة الترتيب إلى السلسلة المحلية `C9TA` | الترتيب المحلي 0 (`DEFAULT`) يُسلسَل إلى سلسلة السلك `"BASIC"`، لا `"DEFAULT"` |
| تخزين التفاعل لكل منشور (`newsletter_message_reaction`، عدّاد مُجمَّع) مقابل تفاعلات الرسائل العادية | تخزِّن القنوات سطرًا واحدًا لكل زوج `(رسالة، إيموجي)` مع عدّاد، لا سطرًا واحدًا لكل مستخدم متفاعل |

---

## 14. التدفق الكامل

```
[Admin]  create channel
    │   NewsletterCreate / NewsletterCreateVerified (MEX) ──► [WA Server] allocates <id>@newsletter
    ▼
[Admin]  set name/description/picture, reaction policy
    │   UpdateNewsletterGraphqlJob ──► NewsletterMetadataUpdate (MEX)
    ▼
[Admin]  invite co-admin
    │   C9m6: per-recipient E2E message (newsletterAdminInviteMessage, field 78, own expiration)
    │   + NewsletterAdminInvite (MEX, server-side grant)
    ▼
[Invitee]  NewsletterAcceptAdminInvite (MEX) ──► role GUEST/SUBSCRIBED → ADMIN (C9U5)

[User]  discover channel (directory / shared link https://whatsapp.com/channel/<code>)
    ▼
[Client]  NewsletterJoin (MEX) ──► role → SUBSCRIBED
    ▼
[Client]  <iq xmlns="newsletter" type="get"><messages count view_role=subscriber/></iq>
    │◄── posts, paginated by before/after server_id
    ▼
[User]  views post ──► <receipt type="view"><list><item server_id/></list></receipt> (view count)
[User]  reacts ──► newsletter_message_reaction (aggregate count, own reaction may be orphaned until post lands)

[Admin]  moderates: NewsletterReactionSendersList (who reacted), NewsletterBlockUser,
         NewsletterPinMessages/Unpin, NewsletterUpdateVerification, NewsletterChangeOwner
    ▼
[Owner]  delete channel ──► NewsletterDelete (MEX)
```

---

## 15. مجاهيل (Unknowns)

| العنصر | السبب |
|------|--------|
| العلاقة/الترتيب الدقيق بين رسالة دعوة الإدارة المشفرة من طرف إلى طرف ومنح `NewsletterAdminInvite` عبر MEX | كلاهما موجود في الكود؛ أيّهما السلطة المرجعية، أو هل أحدهما يُفعِّل الآخر، غير مُتابَع |
| سبب تشارك `newsletterFollowerInviteMessage` (108) و`…V2` (113) نوع بروتو واحد | لم يُعثر على انقسام سلوكي على مستوى جافا |
| اسم/موقع حقل عدّاد المشاهدة لكل منشور في استجابة جلب الرسائل | يُستنتَج أنه موجود داخل حمولة IQ لـ `messages`/`message_updates`؛ غير موسَّع |
| التنفيذ من جانب الخادم لعدم قابلية تغيير اسم القنوات الموثَّقة | العميل يعرض فقط سلسلة خطأ ثابتة |
| شكل الاستجابة الكامل لمعظم عمليات MEX بما يتجاوز `NewsletterMetadata` | لم تُقرأ في هذا التمرير |
| القيم الافتراضية لمعظم أعلام الميزات في §11 | قابلية الوصول للصف فقط، لم تُؤكَّد الحالة الافتراضية |
| حركة البيانات / سلوك الخادم الفعلي | لم يُسجَّل شيء؛ تحليل ساكن فقط |

---

## 16. Baileys

غير مُغطّى: `baron-baileys-v2` (فرع (fork) Baileys المستخدم كخط أساس للمقارنة في تقارير هذا المستودع الأخرى) ليس لديه حتى وقت كتابة هذا تنفيذ موثَّق ومُتحقَّق منه مقابل هذا APK لميزة النشرات/القنوات. لم يُفحَص أي كود من جانب Baileys لهذا التقرير. إضافة قسم Baileys دون وقائع مُتحقَّق منها سيخالف قواعد الإثبات في هذا المستودع. إذا/عندما يوفّر `baron-baileys-v2` دعم النشرات، ينبغي ملء هذا القسم مقابل JID (النوع 21، الخادم `newsletter`)، وطلبات IQ بـ `xmlns="newsletter"` في §7.1، ومعرّفات doc_ids لـ MEX في §9.
