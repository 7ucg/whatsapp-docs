<!-- src-sha1: c9f42e3645bee848584358bb7a4660a293218e2e -->
# WhatsApp الفعاليات (Events) — تقرير RE كامل
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-01
**النطاق:** الفعاليات على طراز التقويم (`eventMessage`، `eventInviteMessage`، `eventCoverImage`)، رد الحضور المشفر (`encEventResponseMessage` / `EventResponseMessage`)، نظام تطبيق "Events v2" الفرعي (`com.whatsapp.eventsv2.*`: قاعدة بيانات محلية، مزامنة GraphQL، إشعارات MEX الدفعية (push)، خط أنابيب صورة الغلاف، رابط الدعوة/رمز QR)، دورة الحياة (إنشاء/تعديل/إلغاء/حذف/مغادرة)، حالات الرد (RSVP)، قواعد ظهور الضيوف/الموقع، سياق المجموعة مقابل المحادثة الفردية مقابل المجتمع (community)، قيد الجهاز المرافق (companion-device)، فهرس عمليات GraphQL، التذكيرات

---

## 1. ما هي

"الفعالية" (Event) هي عنصر على طراز التقويم (اسم، وصف، نطاق زمني، موقع، رابط مكالمة فيديو/صوت اختياري) يمكن نشره في محادثة فردية، أو مجموعة، أو مشاركته عبر رابط/رمز QR مستقل، مع إمكانية رد الضيوف (قادم / ربما / غير قادم). تُشحن الميزة عبر سطحي اتصال سلكي في آنٍ واحد: رسالة محادثة مشفرة طرف-لطرف عادية (`Message.eventMessage` / `Message.eventInviteMessage`) تعرض بطاقة الدعوة في سجل المحادثة، وخط تحكم GraphQL + دفع MEX مواز (`com.whatsapp.eventsv2.*`، حزمة جديدة في 2.26.41.6) يحافظ على مزامنة قاعدة بيانات فعاليات محلية بشكل مستقل عن سجل المحادثة. تشفير الرد (RSVP) (استخدام HKDF لحالة "Event Response"، AES-GCM) مُشترك مع التفاعلات/الاستطلاعات/التعليقات وموثّق في `WA_MESSAGE_SECRETS.md`؛ هذا التقرير يغطي طبقة نموذج الفعالية ودورة حياتها فقط.

| الكيان | حقل `Message` | النوع (مبهم) | الدور |
|--------|-----------------|-------------|------|
| `eventMessage` | **75** | `EventMessage` | فعالية التقويم الأساسية، تُنشر في محادثة |
| `encEventResponseMessage` | **76** | `EncEventResponseMessage` (`DRN`) | رد RSVP مشفر لاحق |
| `eventCoverImage` | **85** | `FutureProofMessage` | مُغلِّف عام، يحمل صورة الغلاف كـ `imageMessage` متداخلة |
| `eventInviteMessage` | **122** | `EventInviteMessage` (`DTQ`) | بطاقة دعوة "Events v2"، فئة شاملة لـ `eventMessage` |
| `eventResponses` (متكرر) | **61**، على مكافئ `WebMessageInfo` (`C30626DTu`) | `EventResponse` | تجميع رد RSVP لكل ضيف محمول في مزامنة السجل |
| `eventAdditionalMetadata` | **64**، نفس الحاوية | `EventAdditionalMetadata` | قيمة بوليانية مفردة `isStale` |

جميع حقول الـ proto وحقول نص RSVP الصريح أدناه أُعيدت قراءتها مباشرةً من فئات 2.26.41.6 (`DRP`، `DRN`، `DU9`، `E2D`، `C9T8` — **found**) وتمت مطابقتها مع حاوية `Message` ذات المستوى الأعلى في `Tools/proto-extractor/research/2.26.41.6/whatsapp-deobfuscated.proto`. المستويات: **found** = مقروء في الكود/النصوص، **inferred** = مُستنتَج، **unknown** = غير محسوم.

---

## 2. `EventMessage` (الحقل 75) — الفعالية الأساسية

غير متغيّر منذ فهرس عصر 2.26.35.2؛ لا يزال يحتوي 12 حقلاً في 2.26.41.6.

| الحقل | # | النوع | ملاحظات |
|-------|---|------|-------|
| `contextInfo` | 1 | `ContextInfo` | حامل الاقتباس/الإشارات القياسي |
| `isCanceled` | 2 | بوليان | يُضبط بواسطة إجراء الإلغاء |
| `name` | 3 | نص (string) | عنوان الفعالية |
| `description` | 4 | نص (string) | |
| `location` | 5 | `Message.LocationMessage` | دبوس موقع ثابت (خط العرض/الطول/الاسم/العنوان)، *ليس* مباشراً (live) |
| `joinLink` | 6 | نص (string) | رابط انضمام عام (حقل قديم؛ يُستبدَل برابط دعوة Events v2 للفعاليات الجديدة) |
| `startTime` | 7 | int64 | ثوانٍ يونكس (unix) |
| `endTime` | 8 | int64 | ثوانٍ يونكس (unix) |
| `extraGuestsAllowed` | 9 | بوليان | مفتاح "+1" |
| `isScheduleCall` | 10 | بوليان | نفس النموذج المستخدم لمدخل "جدولة مكالمة" |
| `hasReminder` | 11 | بوليان | |
| `reminderOffsetSec` | 12 | int64 | ثوانٍ قبل `startTime` |

يُملأ `reminderOffsetSec` من قائمة اختيار ثابتة (`EventReminderBottomSheet`، نصوص **found**): "أبداً"، "وقت الفعالية"، "15 دقيقة قبل"، "30 دقيقة قبل"، "ساعة واحدة قبل"، "يوم واحد قبل". خريطة الثواني 0/900/1800/3600/86400 **مُستنتَجة (inferred)** (لم تُقرأ كقيم صريحة؛ جدول تحويل الخيار إلى ثوانٍ موجود في فئة — `BXa`/`C27637BzN` — لم يحلّ jadx مجمع ثوابتها).

---

## 3. `EventInviteMessage` (الحقل 122، مبهم `DTQ`) — دعوة "Events v2"

نمت من 9 إلى 13 حقلاً عبر الإصدارات؛ يحمل 2.26.41.6 جميع الـ 13. **تصحيح للمادة الأصلية**: الملف الموثَّق `Messages/eventInviteMessage/info.md` (المأخوذ في 2.26.35.2) يتوقف عند الحقل 9 (`callLink`) ويفوّت الحقول 10–13، المؤكَّد وجودها في هذا الإصدار بقراءة مباشرة لـ `DTQ`:

| الحقل | # | النوع | أُضيف في | ملاحظات |
|-------|---|------|-------|-------|
| `contextInfo` | 1 | `ContextInfo` | أساسي | |
| `eventId` | 2 | نص (string) | أساسي | معرّف الفعالية المخصَّص من الخادم |
| `eventTitle` | 3 | نص (string) | أساسي | |
| `jpegThumbnail` | 4 | bytes | أساسي | صورة مصغّرة مضمَّنة لصورة الغلاف |
| `startTime` | 5 | int64 | أساسي | |
| `caption` | 6 | نص (string) | أساسي | |
| `isCanceled` | 7 | بوليان | أساسي | |
| `endTime` | 8 | int64 | أساسي | |
| `callLink` | 9 | نص (string) | أساسي | على غرار `https://call.whatsapp.com/video/...` |
| `coverImageHandle` | 10 | نص (string) | 2.26.38.10 | إشارة مقبض وسائط (handle)، بديل عن `jpegThumbnail` المضمَّنة |
| `locationName` | 11 | نص (string) | 2.26.38.10 | تسمية الموقع المقروءة للبشر |
| `lastUpdatedTsUsec` | 12 | int64 | 2.26.38.10 | ميكروثوانٍ؛ تتقدّم مع كل `UpdateEvent` |
| `status` | 13 | int32 (تعداد مفتوح) | **2.26.41.6** | حالة على مستوى الفعالية؛ فئة التعداد غير قابلة للاستعادة إحصائياً |

`status` (13) هو الحقل السلكي الجديد الوحيد في هذا الإصدار. أسماء أعضاء تعداده **غير معروفة (unknown)** على مستوى الـ proto — لم يتمكن jadx من استعادة الفئة الداعمة لهذا التعداد المفتوح من نوع int32. مع ذلك، تم استرجاع المفردات الخاصة بحالة RSVP الموجَّهة لـ GraphQL، أي `rsvp_status`/`UpdateEvent.status`، بشكل مستقل (§6)، وهي مرشّح معقول لكنه غير مؤكَّد لنفس الدلالات؛ ولم يُثبَت أن الاثنين يتشاركان تمثيلاً سلكياً واحداً.

---

## 4. `eventCoverImage` (الحقل 85) — مُغلِّف صورة الغلاف

`FutureProofMessage { optional Message message = 1; }` — نفس المُغلِّف العام المستخدم لـ `lottieStickerMessage`، `statusMentionMessage`، وغيرها. لا حقول خاصة بالفعاليات؛ الحقل `message` المتداخل يحمل `imageMessage` عادية. كود المستهلك (`EventCoverImageLoader`، `EventCoverImageThumbnailCreator`، `EventCoverImageUrlResolver`) يتعامل معها كمرفق صورة عادي — لم يُعثَر على تحقّق إضافي خاص بالفعاليات بعد فكّ تغليف المُغلِّف العام.

يدعم Events v2 أيضاً صور غلاف **جاهزة مسبقاً** (`EventPresetCoverImagesRepository`، كتالوج مجلوب عبر GraphQL، متغيّرات `cover_image_blob`/`is_preset_image` على `CreateEvent`/`UpdateEvent`) كبديل عن صورة مرفوعة من المستخدم.

---

## 5. الرد (RSVP): `encEventResponseMessage` و `EventResponseMessage`

### 5.1 الشكل السلكي (found، قراءة مباشرة لـ `DRN`/`DRP`/`E2D`)

| الحامل | الحقل | # | النوع |
|---------|-------|---|------|
| `EncEventResponseMessage` (`DRN`، الحقل 76) | `eventCreationMessageKey` | 1 | `MessageKey` (`BD5`) |
| | `encPayload` | 2 | bytes |
| | `encIv` | 3 | bytes |
| `EventResponseMessage` (`DRP`، النص الصريح بعد AES-GCM) | `response` | 1 | تعداد `E2D` |
| | `timestampMs` | 2 | int64 |
| | `extraGuestCount` | 3 | int32 |

قيم `E2D` (found، `E2D.java`): **0 UNKNOWN، 1 GOING، 2 NOT_GOING، 3 MAYBE**.

هذا يؤكد مباشرةً `WA_MESSAGE_SECRETS.md` §"encEventResponseMessage **76**" ويحلّ تعارضاً في تفريغ الـ proto المُستخرَج تلقائياً (`Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`، والذي — نتيجة علّة موضَّحة في نصّه الخاص في استعادة أسماء الحقول، "missing name slot at field #3" — يسرد `EventResponseMessage` بالترتيب `timestampMs=1، extraGuestCount=2، field3=3`). القراءة المباشرة للفئة (سلسلة ترتيب حقول `BUILD_MESSAGE_INFO` في `DRP` وثوابت `RESPONSE_FIELD_NUMBER=1`/`TIMESTAMP_MS_FIELD_NUMBER=2`/`EXTRA_GUEST_COUNT_FIELD_NUMBER=3`) تحسم الأمر: **`response` هو الحقل 1، لا الحقل 3.**

### 5.2 مسار الإرسال (found، `DU9.ADr`)

يبني `DU9` (معالج حالة استخدام رد الفعالية، يمتد من `F2P`) كائن `DRP` من تعداد على مستوى التطبيق `C9T8` (`UNKNOWN=0، GOING=1، NOT_GOING=2، MAYBE=3` — مطابق عدديّاً لـ `E2D`، ما يؤكد أنه مرآة مباشرة 1:1 عبر المحوِّل `EW0.A01`) مع ختم زمني وعدد ضيوف إضافي (int) `extraGuestCount`، ويشفّره باستخدام حالة استخدام HKDF المسمّاة `"Event Response"` عبر `MessageSecretCryptoHelper` (`C33285Eeb.A03`)، ثم يُغلّف النص المشفّر/IV/مفتاح الرسالة الأصلية في كائن `DRN`. تضع `AAl()` ختم `<meta event_type="response">` في الطابع (stanza) الصادرة. تفاصيل التشفير (اشتقاق HKDF، AES-GCM، AAD = `targetId‖0x00‖modifier`، إعادة محاولة المُرسل/LID) **لا تُكرَّر هنا** — انظر `WA_MESSAGE_SECRETS.md` §2–9، 16.

### 5.3 ثلاثة تعدادات أخرى على شكل RSVP (found) — نقطة التباس

إلى جانب التعداد السلكي `E2D` ومرآته `C9T8`، يُعرِّف التطبيق ما لا يقل عن ثلاثة تعدادات *أخرى* لحالة RSVP بترتيب أعضاء **مختلف**، تُستخدم كل منها في طبقة مختلفة:

| التعداد (مبهم) | الأعضاء (الترتيب العددي) | يُستخدم في |
|---|---|---|
| `E2D` | 0 UNKNOWN، 1 GOING، 2 NOT_GOING، 3 MAYBE | النص الصريح السلكي `EventResponseMessage.response` |
| `C9T8` | 0 UNKNOWN، 1 GOING، 2 NOT_GOING، 3 MAYBE | مرآة `E2D` على مستوى التطبيق، تُمرَّر إلى `DU9.ADr` |
| `C9T6` | 0 GOING، 1 NOT_GOING، 2 MAYBE، 3 NO_RESPONSE | ترتيب `dbValue` المحلي (`EventRsvpBottomSheet`، قاعدة البيانات المحلية)، **بلا خانة UNKNOWN**، ويحمل `NO_RESPONSE` بدلاً منها |
| `C9U0` | سلاسل `serverValue`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`، `GOING`، `MAYBE`، `NOT_GOING`، `NO_RESPONSE` | متغيّر GraphQL `rsvp_status` (`UpdateEventRsvp`، `JoinEventViaLink`) |

هذا يحلّ جزءاً من ثغرة "تعداد RSVP غير معروف" المذكورة لسطح GraphQL في `Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`: متغيّر **GraphQL** `rsvp_status` يأخذ السلاسل الصريحة `GOING` / `MAYBE` / `NOT_GOING` / `NO_RESPONSE` (found، `C9U0.serverValue`، المستهلك `C207188s3.B2x()` الذي يقرأ المفتاح `"rsvp_status"`). تعداد `EventInviteMessage.status` السلكي (الحقل 13، §3) يظل غير مُستعاد، و**لم يُثبَت** أنه يتشارك هذه المفردات.

مجموعة خامسة ومنفصلة من قيم "تسمية الحالة" الصحيحة (found، `C2115191e.A00`، تُستخدم لرقعة إعادة التوجيه/المعاينة في المحادثة) تُطابِق `1 GOING، 2 GOING_WITH_GUEST، 3 NOT_GOING، 4 MAYBE، 5 NOT_RESPONDED، 6 CANCELED، default CREATOR` — مجموعة تسميات عرض/تصحيح واجهة مستخدم، لا قيمة سلكية.

---

## 6. سطح GraphQL لـ Events v2 (مخطط `www`، doc_id موجودة)

توجد 16 عملية مُثبَّتة (persisted) في ملف `whatsapp-android-www_client_persist_ids.json` المشحون؛ تم استرجاع المتغيّرات من مواقع الاستدعاء في الـ APK (موثَّقة في `Querys/www/guides/events.md`، الذي راجعه هذا التقرير بدلاً من إعادة استخلاصه).

| العملية | doc_id | العملية | doc_id |
|----|--------|----|--------|
| `CreateEvent` | `27122934507384369` | `UpdateEvent` | `27442441785378771` |
| `DeleteEvent` | `24671535952543811` | `UpdateEventRsvp` | `27592470423757790` |
| `GetEvent` | `27529572846713636` | `ListEvents` | `27633532006268526` |
| `GetEventCoverImage` | `28048111841543330` | `AddEventInvitations` | `28162575909992756` |
| `GetEventLinkPreview` | `27639296169058396` | `RemoveEventInvitations` | `27696932319970038` |
| `GetOrCreateEventInviteLink` | `26392982740362906` | `RemoveSelfEventInvitation` | `27063717026648637` |
| `JoinEventViaLink` | `27669318929396727` | `RotateEventInviteLink` | `27134834146102810` |
| `ValidateCachedEventIDs` | `27508030125525954` | mex `LogEventInviteCreate` | `27409709725288255` |

المتغيّرات المسترجَعة الرئيسية (found): تأخذ `CreateEvent`/`UpdateEvent` كلاً من `chat_jid`، `description`، `max_additional_guests`، `is_group_based_event`، `is_shareable`، `cover_image_handle`/`cover_image_blob`/`is_preset_image`، `location_address`/`location_web_url`، `call_link_media_type`، `call_link_waiting_room_enabled`؛ ويأخذ `UpdateEvent` إضافةً `clear_location`، `clear_location_coordinates`، `hide_invitee_list`، `link_id`، `status`. تأخذ `UpdateEventRsvp`/`JoinEventViaLink` كلاً من `event_id`/`link_token`، `rsvp_status`، `extra_guest_count`. النقل (transport) **inferred** (طلب POST بـ `doc_id` مُثبَّت، على نفس نمط عمليات `www` الأخرى)؛ لم يُسجَّل أي اتصال فعلي.

### 6.1 إشعارات MEX الدفعية (found، منفصلة عن سحب GraphQL أعلاه)

يحلّل `DefaultEventsNotificationRepository` مخططي حمولة دفع **MEX** — `xwa2_notify_event_on_invite` و `xwa2_notify_event_on_update` (أسماء عُقَد صريحة في الاستثناءات المرفوعة، found) — تحمل `start_ts_sec`، `cover_image.handle`/`cover_image.uri`، الموقع، وحقول رابط المكالمة، ويُدرِجها مباشرةً في قاعدة بيانات الفعاليات المحلية (`DefaultLocalEventsDataSource.upsertEvents`). هذا يعني أن فعالية ما يمكن أن تظهر في قائمة الفعاليات المحلية للجهاز **دون** أن يكون الجهاز قد استلم أبداً طبقة رسالة المحادثة (`eventMessage`/`eventInviteMessage`) الخاصة بها — فالخادم يدفع إشعارات الدعوة/التحديث فعلياً عبر MEX بشكل مستقل عن تسليم المحادثة. عند الدعوة الأولى، تكون حالة RSVP المحلية الافتراضية `NO_RESPONSE` (`C9T6.A05.dbValue`).

---

## 7. التخزين المحلي والجسر القديم

`EventsDatabaseDataSource` (قاعدة بيانات محلية على طراز Room) هي المخزن الأساسي لـ Events v2؛ `GraphqlEventsDataSource` يملؤها من عمليات §6؛ `FMessageEventsDataSource` يربط النموذج **الأقدم** المعتمد فقط على رسائل المحادثة (`eventMessage`/`eventInviteMessage` كصفوف `FMessage` عادية، الفئة `C213509Ao` — وهي أيضاً الفئة التي تتحكم في توليد `messageSecret` لرسائل الفعاليات وفق `WA_MESSAGE_SECRETS.md` §"prepare send") بنفس تيار `observeEventPreviews()` الذي تستهلكه واجهة المستخدم. عملياً: فعالية أُنشئت بعميل أقدم (أو قبل وجود Events v2) لا تزال تُعرَض من رسالة المحادثة؛ فعالية أُنشئت عبر Events v2 مدعومة بقاعدة بيانات ومُزامَنة عبر GraphQL، مع عمل رسالة المحادثة كبطاقة دعوة قابلة للمشاركة.

---

## 8. إجراءات دورة الحياة

| الإجراء | من | الآلية | الأثر |
|--------|-----|-----------|--------|
| **إنشاء** | أي عضو محادثة (مجموعة) / أي من الطرفين (محادثة فردية) / أي شخص في سياق مؤهَّل لرمز QR | `CreateEvent` (GraphQL) ثم نشر `eventInviteMessage` في المحادثة | يخصّص الخادم `eventId`؛ يجمع `EventComposerFragment` الاسم/الوصف/الوقت/الموقع/الغلاف/التذكير/مفتاح الضيف/نوع وسائط رابط المكالمة |
| **تحديث** | المضيف | `UpdateEvent` (GraphQL)؛ يتقدّم `lastUpdatedTsUsec` (الحقل 12) | نص إشعار مستهدَف يعتمد على الحقول التي تغيّرت: "تم تحديث تاريخ الفعالية."، "...التاريخ والموقع..."، "...التاريخ والوقت..."، "...التاريخ والوقت والموقع..."، "...تم تحديث الموقع."، "...تم تحديث الوقت."، "...الوقت والموقع..." (جميعها found، نصوص مختلفة لكل اختلاف) |
| **إلغاء** | المضيف | يضبط `isCanceled`/`status`؛ مربع حوار تأكيد "إلغاء الفعالية" / "هل تريد بالتأكيد إلغاء هذه الفعالية؟" | "تم إلغاء الفعالية"؛ نص إشعار "%1$s قام بإلغاء %2$s"؛ "لن يتمكن الضيوف من الرد على الفعالية بعد الآن." / "لن تتمكن من الرد على الفعالية بعد الآن." — يُغلَق الرد (RSVP) |
| **حذف** | المضيف | `DeleteEvent` (GraphQL) | يُزال من قائمة فعاليات المضيف المحلية؛ تبقى رسالة/رسائل الدعوة في المحادثة ظاهرة؛ "سيرى من في قائمة الضيوف أن الفعالية قد حُذفت." |
| **مغادرة** | ضيف | إجراء محلي، لا يترتب عليه تغيير في الرد | يتوقف الضيف عن استلام تحديثات الفعالية اللاحقة: "لا يمكنك رؤية تغييرات الفعالية إلا التي حدثت قبل مغادرتك." |
| **إزالة ضيف** | المضيف | يُزيل الضيف؛ **يعيد ضبط رابط الدعوة** (`RotateEventInviteLink`) | "تمت إزالة الضيف وإعادة ضبط رابط الفعالية" — تدبير صريح لمنع العودة؛ إزالة ضيف انضمّ عبر الرابط **لا** تُبطِل بشكل رجعي الآخرين الذين استخدموا ذلك الرابط فعلاً |
| **الإبلاغ عن فعالية** | ضيف | يرسل بلاغاً إلى WhatsApp | "لن يعرف أحد في الفعالية بهذا البلاغ."؛ قد يؤدي أيضاً إلى مغادرة الفعالية |
| **تعليق** (إجراء إداري) | من جهة الخادم (تطبيق سياسات) | منفصل عن الإلغاء | "تم تعليق الفعالية"، "لا يمكن تغييرها الآن"؛ حالة مقفلة لا يستطيع المضيف الخروج منها بالتعديل |

إزالة المدعوّين فرادى (`RemoveEventInvitations`) منفصلة عن إزالة ضيف منضمّ (`RemoveEventGuestUseCase`)؛ وتكمِّل `AddEventInvitations`/`RemoveSelfEventInvitation` إدارة قائمة الدعوة.

---

## 9. واجهة ومراحل الرد (RSVP)

يعرض `EventRsvpBottomSheet` أربع خيارات دائرية مرتبطة بمعرّفات الموارد `rsvp_going_btn`، `rsvp_going_with_guest_btn` (تظهر فقط عند ضبط `extraGuestsAllowed` واختيار المُشاهد عدد ضيوف > 0)، `rsvp_not_going_btn`، `rsvp_maybe_btn`؛ لا يُحدَّد أي زر لحالة عدم الرد/`NO_RESPONSE`. التسميات (found، strings.xml): "قادم"، "قادم مع ضيف"، "ربما"، "غير قادم". يمكن للضيف أيضاً إضافة عدد "+1" (`extraGuestCount`، الحقل السلكي 3 من `EventResponseMessage`)، مقيَّداً بـ `EventMessage.extraGuestsAllowed` (الحقل 9) / "لا يمكنك إيقاف 'السماح بالضيوف' لهذه الفعالية." بعد أن يكون الضيوف قد ردّوا فعلاً بإضافة "+1".

الرد من غير مستخدمي WhatsApp مدعوم بشكل صريح عبر رابط الانضمام: "يمكن للضيوف الرد حتى لو لم يكونوا على WhatsApp." — يأخذ `JoinEventViaLink` قيمة `rsvp_status` مباشرةً دون جلسة WA موثَّقة، أي أن مسار `encEventResponseMessage` المشفَّر ليس قناة الرد الوحيدة؛ ردود الضيوف القادمة عبر الرابط تمر عبر GraphQL بنص صريح بدلاً من ذلك.

---

## 10. نموذج الظهور والخصوصية

هذه هي أهم حقيقة "لا يُلتبَس بها" بخصوص الفعاليات: على عكس محتوى المحادثة العادي، **بيانات الفعالية الوصفية مُفصح عنها صريحاً للخادم**، وليست مشفّرة طرف-لطرف بشكل خالص.

| النص (found) | المورد | المعنى |
|---|---|---|
| "تفاصيل الفعالية مرئية للضيوف ولـ WhatsApp." | `str19d9` | الاسم/الوصف/الوقت/الموقع مقروءة من جهة الخادم (ما يتوافق مع كونها متغيّرات GraphQL لـ `CreateEvent`/`UpdateEvent`، وليست بايتات proto مشفَّرة فقط) |
| "تفاصيل الفعالية مرئية للضيوف ولـ WhatsApp. تظل رسائلك ومكالماتك الشخصية مشفّرة من طرف إلى طرف." | `str1a3f` | تحديد صريح للنطاق: ضمان التشفير من طرف إلى طرف *لا* يمتد إلى تفاصيل الفعالية |
| "سيكون اسمك وردّك مرئيين للضيوف الآخرين ولـ WhatsApp." | `str1a08` | هوية الرد وإجابته مرئية للخادم أيضاً (ما يتوافق مع كون `UpdateEventRsvp` تحويلة GraphQL بنص صريح، منفصلة عن صدى `encEventResponseMessage` المشفَّر في طبقة المحادثة) |
| "رُدّ لترى موقع الفعالية والمزيد." / "رُدّ لترى الموقع" | `str19c7`/`str19c4` | الموقع **مقيَّد بالرد (RSVP)** للضيوف الذين لم يردّوا بعد |
| "لا يمكنك رؤية إلا الضيوف الموجودين في جهات اتصالك أو من راسلتهم على WhatsApp." | `str1974` | ظهور قائمة الضيوف مقيَّد بشبكة جهات اتصال/محادثات المُشاهد نفسه، وليس القائمة الكاملة |
| "يمكن لأي شخص معه الرابط رؤية الفعالية ومشاركتها مع آخرين، حتى لو لم يكن على WhatsApp." | `str198b` | رابط الدعوة/رمز QR يتجاوز العضوية كلياً — حيازة الرابط هي وسيلة التحكم بالوصول |

إذن: تشفير `encEventResponseMessage` من طرف إلى طرف (HKDF + AES-GCM، §5، `WA_MESSAGE_SECRETS.md`) يحمي حمولة الرد (RSVP) **في سجل المحادثة / أمام جهة التمرير (relay)**، لكن نفس إجابة الرد وبيانات الفعالية الوصفية الخاصة بها تُرسَل أيضاً بشكل مستقل إلى الخادم بنص صريح عبر خط تحكم GraphQL للمزامنة، والاكتشاف، والضيوف القادمين عبر الرابط (غير مستخدمي WA). الطبقتان لا تتنافيان — تتعايشان لنفس الفعالية.

---

## 11. سياق المجموعة مقابل المحادثة الفردية مقابل المجتمع

- **محادثة فردية**: يمكن لأي من الطرفين إنشاء فعالية؛ متغيّر GraphQL `is_group_based_event` يكون false.
- **محادثة مجموعة**: `is_group_based_event: true`؛ يعرض المُنشئ (composer) "أُنشئت لـ:" مع تحديد المجموعة؛ يمكن أيضاً استقدام الدعوات من عضوية المجموعة (`EventInviteFromGroupsLoadController`، `EventInviteGroupFetcher`) مما يسمح للمضيف بدعوة أشخاص من مجموعات مشتركة أخرى.
- **المجتمع (Community)**: تظهر الفعاليات أيضاً على مستوى المجتمع — "فعاليات في الإعلانات"، "فعاليات المجتمع"، "عرض كل فعاليات المجتمع" (نصوص found) — قائمة فعاليات على مستوى المجتمع منفصلة عن فعاليات مجموعة واحدة.
- **مستقل / قائم على الرابط**: لا يلزم ربط فعالية بأي محادثة؛ ينتج `GetOrCreateEventInviteLink` + `EventInviteLinkQrActivity` رابطاً/رمز QR قابلاً للمشاركة ومستقلاً عن عضوية المحادثة (§10، `str198b`).

تصنيف دعم الجهاز المرافق لـ `eventMessage` (`WA_MESSAGE_SECRETS.md` §15، `CompanionSupportVerifier`) يسمح بطابع (stanza) `type="event"` على جهاز مرتبط (مرافق، companion) — أي أن فقاعة الدعوة يمكن أن *تُستلَم وتُخزَّن* هناك فعلاً — لكن التفاعل معها محجوب: `EventsCompanionRedirectDialog` + النص "لعرض أو الرد على هذه الفعالية، استخدم WhatsApp على جهازك الأساسي." (found) يُعيد توجيه مستخدمي الجهاز المرافق بعيداً عن واجهة Events v2 بالكامل. هذا تقسيم مقصود: تسليم الطابع (stanza) متوافق مع الجهاز المرافق، لكن التفاعل على مستوى الميزة مقيَّد بالجهاز الأساسي فقط.

---

## 12. التذكيرات والإشعارات

| الآلية | المُحرِّك | found/inferred |
|---|---|---|
| `hasReminder`/`reminderOffsetSec` (الحقلان السلكيان 11/12 من `EventMessage`) | يضبطه المضيف، خيارات القائمة أبداً / وقت الفعالية / 15 دقيقة / 30 دقيقة / ساعة / يوم قبل البداية | found (نصوص واجهة المستخدم)؛ خريطة الثواني مُستنتَجة (inferred) |
| إشعار بدء دائم | "يحصل الضيوف أيضاً على إشعار في وقت الفعالية." (`str1a47`) | found — مستقل عن التذكير المخصَّص، يحصل كل ضيف على إشعار عند بدء الفعالية |
| "السماح بتذكيرات فعاليات دقيقة" | طلب إذن نظام التشغيل لمنبّهات الوقت الدقيق | found |
| إشعارات التحديث | النص يختلف حسب الحقول التي تغيّرت (§8) | found |
| إشعار الإلغاء | "%1$s قام بإلغاء %2$s. عرض الفعالية" | found |
| دفع MEX (`xwa2_notify_event_on_invite`/`_on_update`) | مزامنة بدأها الخادم، مستقلة عن تسليم المحادثة | found (§6.1) |

---

## 13. علامات الميزات (Feature flags)

لم يُسترجَع في هذه الجولة أي معرّف عددي لعلامة ميزة (feature flag) يتحكم بسلوك Events v2 — على عكس نقاط الدخول المعزولة من نوع بوليان/int في `WA_MESSAGE_SECRETS.md`، فإن أدوات الوصول الخاصة بحقن التبعيات (dependency injection) في حزمة `eventsv2.*` (`C05T.A00(NNNNN)`، `C05Z.A00(NNNNN)`) هي معرّفات بحث مكوّن/أحادية (singleton)، وليست قراءات لعلامات؛ ولم يُعثَر على فحص بوليان على طراز `AbstractC...Gatekeeper` مرتبط بعلامة عددية يتحكم بإنشاء الفعالية، أو الرد، أو إعادة توجيه الجهاز المرافق. العلامتان الموثّقتان فعلاً لمسار تشفير RSVP المشترك تظلان ذوات الصلة: **15791** (تحويل مُعدِّل رد الفعالية LID→PN في المحادثات الفردية) وآلية القائمة البيضاء للجهاز المرافق/مُصنِّف نوع الرسالة في `WA_MESSAGE_SECRETS.md` §15–16. غير معروف ما إذا كانت علامة إيقاف طارئ (kill-switch) منفصلة تتحكم في واجهة Events v2 نفسها.

---

## 14. Baileys

لم يُعثَر في `baron-baileys-v2` 1.5.17 على أي معالجة لإرسال أو استلام `eventMessage`/`eventInviteMessage`، ولا على أي تشفير لرد `encEventResponseMessage`، بما يتجاوز ما يوثّقه `WA_MESSAGE_SECRETS.md` §17 فعلاً لمسار تشفير الإضافة المشترك (يمكنه فك تشفير `encEventResponseMessage` واردة باستخدام جدول حالة الاستخدام العام، لكن لا يوجد كود خاص بمُرسِل الفعالية أو نموذجها). `eventMessage` و `eventInviteMessage` من ناحية أخرى حقلا `Message` عاديان وقابلان للإرسال عبر `snowi.sendjson` بالحقول الصريحة في §2/§3 — تركيب أحدهما لا يتطلب مساعد التشفير على الإطلاق، فقط `encEventResponseMessage` (الرد) يتطلّبه. لا يوجد عميل GraphQL في Baileys لعمليات `www` في §6؛ تلك تتطلب مسار طلب POST بـ GraphQL بـ `doc_id` مُثبَّت غير مُنفَّذ.

| الموضوع | Baileys | Android |
|---|---|---|
| إرسال `eventMessage`/`eventInviteMessage` | حقل `Message` عادي، يمكن الوصول إليه عبر `snowi.sendjson` | نفس الشيء |
| تشفير `encEventResponseMessage` | غير مُنفَّذ (فك تشفير فقط، مسار حالة الاستخدام العام) | `DU9.ADr` + `MessageSecretCryptoHelper` |
| عمليات GraphQL لـ Events v2 (§6) | غير مُنفَّذة | `GraphqlEventsDataSource` |
| مزامنة دفع MEX (§6.1) | غير مُنفَّذة | `DefaultEventsNotificationRepository` |

---

## 15. حالات الخطأ / نقاط الالتباس

| العرض | السبب | ملاحظة |
|---|---|---|
| فشل فك تشفير الرد / خطأ 51 | مفتاح رسالة أصلية خاطئ، أو عدم تطابق نطاق المُرسِل/الهدف (PN مقابل LID) | مشترك مع مسار تصويت الاستطلاع / التعليق، انظر `WA_MESSAGE_SECRETS.md` §18 |
| فعالية ظاهرة في قائمة الفعاليات لكنها لم تظهر أبداً في المحادثة | دفع MEX (`xwa2_notify_event_on_invite`) زامنها بشكل مستقل عن تسليم المحادثة | §6.1 |
| الموقع/قائمة الضيوف مفقودة عند مدعوّ | لم يردّ بعد (الموقع مقيَّد)، أو الضيف غير موجود في جهات اتصال/محادثات المُشاهد (قائمة الضيوف مقيَّدة) | §10 |
| الضيف المُزال لا يزال قادراً على الرد عبر رابط قديم | إزالة الضيف تعيد ضبط الرابط لسجل *ذلك* الضيف فقط، وباقي حاملي الرابط المُشارَك فعلاً غير متأثرين | §8، `str19ed` |
| "لا يمكن تغيير الفعالية" / الفعالية مقفلة | الفعالية مُعلَّقة لأسباب سياسية، وليس مجرد مُلغاة | §8 |
| الجهاز المرافق لا يستطيع فتح الفعالية | التفاعل مع Events v2 مقيَّد بالجهاز الأساسي حتى لو كان الطابع (stanza) نفسه قابلاً للتسليم إلى الجهاز المرافق | §11 |
| لا يمكن تحليل/إنتاج `EventInviteMessage.status` (13) بدقة | فئة التعداد غير قابلة للاستعادة إحصائياً؛ **لم يُثبَت** أنها مطابقة لمفردات `rsvp_status`/`status` في GraphQL | §3، §5.3 |

---

## 16. فروق أساسية

| هذا | وليس هذا |
|---|---|
| `eventMessage` (الحقل 75، أساسي، 12 حقلاً، ثابت منذ ما قبل 41.6) | `eventInviteMessage` (الحقل 122، `DTQ`، 13 حقلاً، البطاقة النشطة لـ "Events v2") |
| `encEventResponseMessage` (صدى RSVP مشفَّر من طرف إلى طرف في المحادثة) | `UpdateEventRsvp`/`JoinEventViaLink` (رد RSVP بنص صريح عبر GraphQL، مرئي للخادم) |
| إلغاء (يضبط `isCanceled`، يُغلِق الرد، تبقى الفعالية ظاهرة) | حذف (يُزال من قائمة المضيف؛ تبقى دعوات المحادثة، مُعلَّمة كمحذوفة) |
| حذف (بدأه المضيف، يؤثر على نسخة المضيف + يُعلِّمها كمحذوفة للآخرين) | مغادرة (بدأها الضيف، يتوقف الضيف عن رؤية التحديثات اللاحقة) |
| تعليق (قفل إداري من الخادم) | إلغاء (إجراء من المضيف) |
| إزالة ضيف + إعادة ضبط الرابط (المضيف، يُبطِل نسخة *ذلك* الضيف من الرابط) | إزالة دعوة (المضيف، قبل أن ينضمّ الضيف) |
| تعداد RSVP المرآوي السلكي `E2D`/`C9T8` (GOING=1، NOT_GOING=2، MAYBE=3، UNKNOWN=0) | تعداد قاعدة البيانات المحلية `C9T6` (GOING=0، NOT_GOING=1، MAYBE=2، NO_RESPONSE=3) — ترتيب مختلف، نفس المفهوم |
| تعداد سلسلة GraphQL `C9U0` لـ `rsvp_status` (`GOING`/`MAYBE`/`NOT_GOING`/`NO_RESPONSE`) | تعداد int32 سلكي مفتوح `EventInviteMessage.status` (الحقل 13) — غير مُستعاد، لم يُثبَت تطابقه |
| ظهور قائمة الضيوف (مقيَّد بجهات اتصال المُشاهد) | ظهور الفعالية عبر الرابط/رمز QR (مفتوح لأي شخص يحوز الرابط) |

---

## 17. التسلسل الكامل (فعالية مجموعة، إنشاء → رد → تحديث)

```
[Host]                                   [WhatsApp server / GraphQL+MEX]           [Guest]
   │ CreateEvent (GraphQL, www)                   │                                   │
   │  chat_jid, description, location, cover──────▶ stores event, assigns eventId     │
   │◀──────────────────────────────────────────── eventId                             │
   │ compose eventInviteMessage (eventId,          │                                   │
   │   coverImageHandle, locationName, ...)        │                                   │
   │ <message type="event"> (E2E, chat plane)──────┼──────────────────────────────────▶ renders invite card
   │                                                │  xwa2_notify_event_on_invite      │
   │                                                ├──────────────────────────────────▶ event appears in
   │                                                │  (MEX push, independent of chat)    Events list too
   │                                                │                                   │ opens EventRsvpBottomSheet
   │                                                │                                   │ picks Going/Maybe/Not going
   │                                                │◀───────── UpdateEventRsvp (GraphQL, plaintext rsvp_status)
   │                                                │◀───────── encEventResponseMessage (E2E, chat plane)
   │  guest list / "Going" badge updates            │  xwa2_notify_event_on_update?     │
   │  (location now visible to guest)               │  (on edits)                       │
   │                                                │                                   │
   │ UpdateEvent (change location/time)─────────────▶ lastUpdatedTsUsec advances         │
   │                                                ├──────────────────────────────────▶ "Event date and location
   │                                                │                                      have been updated."
```

---

## 18. مجهولات (Unknowns)

| البند | الحالة |
|---|---|
| أسماء أعضاء تعداد `EventInviteMessage.status` (الحقل 13) | غير قابلة للاستعادة إحصائياً؛ سلاسل GraphQL `rsvp_status`/`status` (§5.3) مُشابه معقول لكن غير مؤكَّد |
| ثواني `reminderOffsetSec` الدقيقة لكل خيار في القائمة | مُستنتَجة (0/900/1800/3600/86400)، مجمع الثوابت غير مُحسوم |
| صيغة رابط الانضمام / رمز QR (`chat.whatsapp.com/event/...` أو ما شابه) | لم تُعثَر عليها في النصوص أو مرشِّحات نية البيان (manifest intent filters) في هذه الجولة |
| معرّفات علامات ميزات عددية تتحكم في إنشاء/رد/إعادة توجيه الجهاز المرافق لـ Events v2 | لم تُعثَر عليها (انظر §13) |
| العلاقة الدقيقة بين `EventInviteMessage.status` وتعدادي التطبيق المحليين `C9T6`/`C9T8` | غير متتبَّعة |
| سلوك "طلب موافقة للانضمام" (`str1a34`) | النص موجود؛ مسار الكود غير متتبَّع |
| هل تُملأ حقول مزامنة السجل `eventResponses`(61)/`eventAdditionalMetadata`(64) عند المزامنة الصادرة، الواردة، أو كلتيهما | غير متتبَّع |
