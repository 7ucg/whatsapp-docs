<!-- src-sha1: e4fe5d62fca781d0449295a5d549413929d95191 -->
# WhatsApp قوائم البث — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** قوائم البث الكلاسيكية وبث الحالات (status) على Android: نموذج JID من نوع `@broadcast` (قائمة / حالة / موقع)، إنشاء القائمة، حدود العضوية وقواعد المستلمين، IQ من نوع `w:b` (جلب القوائم، حذف قائمة، الحصة)، حالة التطبيق `business_broadcast_list`، ترحيل LID، التخزين المحلي، الاستنساخ لكل مستلم عند الإدراج، stanza الإرسال (توزيع sender-key، `phash`، `bucketing`، `<cap>`، إعدادات الرسائل المؤقتة لكل مستلم)، تجميع ack والإيصالات، الحصة الشهرية للبث، حظر تحذير السبام، GAP، النشر على `status@broadcast` (`SendE2eStatusJob`، الأجزاء، الدلاء اليدوية)، أوضاع خصوصية الحالة، الأصدقاء المقرّبون والجماهير المخصصة، الرد على الحالة / التفاعل / الإشارة / الإشعار، جداول الحالة، feature flags، مقارنة مع Baileys

---

## 1. ما هو (تقنيًا)

توجد ثلاثة JID من نوع `broadcast` على الخادم. جميعها JID "متعددة المشاركين" (`AbstractC20660pZ`، نفس الأساس الذي تستخدمه المجموعات) وتتشارك مسار إرسال واحدًا: يشفّر المرسل مرة واحدة باستخدام sender key ويسلّم المفتاح إلى كل جهاز مستلم بشكل ثنائي (pairwise). جميع العبارات هنا نتيجة تحليل ساكن للـ APK المفكَّك؛ لم يُلتقط أي شيء على الشبكة. المستويات: **found** = قُرئ في الكود، **inferred** = مستنتج من الكود، **unknown** = غير محلول. لا شيء هنا **tested**. أُعيد حل الأسماء المبهمة (obfuscated) في 2.26.41.6 انطلاقًا من سلاسل ثابتة (`BroadcastListManager/…`، `BroadcastXmppMethods/…`، `StatusParticipantUserManager/…`، `SendE2eStatusJob/…`، وأسماء الجداول والـ prefs).

| الكيان | شكل JID | `Jid.getType()` | الصنف | الدور |
|--------|---------|-----------------|-------|-------|
| قائمة بث كلاسيكية | `<id>@broadcast` | 3 | `C99P` | قائمة على الجهاز الأساسي، يتلقى المستلمون نسخًا 1:1 |
| بث الحالة | `status@broadcast` | 5 | `C199018dF` | منشورات الحالة، يُختار الجمهور لكل منشور |
| بث الموقع | `location@broadcast` | 6 | `BOC` | موجود في نموذج JID؛ لم يُتتبَّع استخدامه (الموقع المباشر مستنتج من الاسم) |
| مستخدم الحالة الوهمي الخاص | `status_me` (محلي) | 11 | `C0Dh` | اسم مستعار محلي فقط، وليس JID على الشبكة (الدور inferred) |

خارج النطاق: القنوات newsletters (`SendNewsletterStatusJob` مهمة منفصلة)، حملات Business والإحصاءات، بثوث نظام Android.

| المكوّن | الاسم في 2.26.41.6 | الدور |
|---------|--------------------|-------|
| محلل JID / المساعدات | `C0DJ.A00` / `C0DZ.A0P`, `A0Q`, `A0h` | الخادم `broadcast`: المستخدم `location` → `BOC`، `status` → `C199018dF`، وإلا `C99P`؛ المساعدات تعيد true لأي بث (3, 5, 6) / قائمة (3) / حالة (5) |
| مخصّص / مدير القوائم | `C0YJ.A0E` / `A0K` (`BroadcastListManager`) | معرّف قائمة جديد / إضافة المشاركين وإزالتهم |
| مرشّح LID والترحيل | `C70552yj` (`BroadcastListLidMigrationHelper`), `C0UV` (مهمة الترحيل) | PN → LID |
| مدير / مخزن المشاركين | `C22300su` (`A0j` إضافة، `A0k` إزالة), `C14850fN` (`ParticipantUserStore`) | مشترك مع المجموعات |
| IQ القوائم | `C18240lQ` (`BroadcastXmppMethods`), `AKU` (معالج النتيجة), `BroadcastListQuotaProtocol` + `C9EN` | جلب القوائم، حذف قائمة، الحصة |
| عميل الحصة | `C720733k` (repository), `C2EX` (view model), `C74823Ej` (مستمع الرسائل) | السقف الشهري |
| طفرة حالة التطبيق | `C224469lG` (dispatch), `C26057BNq` (`BusinessBroadcastListMutation`) | `business_broadcast_list` |
| الاستنساخ عند الإدراج | `C231399zG` (`BroadcastCloneOnInsertProcessor`), `AJO` | نسخ محلية لكل مستلم |
| Ack / الإيصالات | `C22500tF`, `C22790ti` (`MainMessageStore`), `C269411e` (`MessageStatusStore`) | ack الخادم، تقسيم الإيصالات |
| المشفّر / المهام | `F6P` (`E2eMessageEncryptor`), `SendE2EMessageJob`, `SendE2eStatusJob` | sender key، SKDM، بناء stanza |
| المدقّق الوارد | `C34757F6a` (`CompanionSupportVerifier`) | يُسقط نسخ القوائم على الأجهزة المرافقة (companions) |
| جمهور الحالة | `C11550Zh` (`StatusInfoStore`), `C182877r0` (distribution info), `C23140uH` (`StatusParticipantUserManager`), `C1889082i` (`StatusCustomListStore`), `C23340ub` (إعداد bucketing) | أوضاع الخصوصية، القوائم، الدلاء |
| مزامنة خصوصية الحالة | `C48386LBh` (`StatusPrivacySyncMutation`), `C49626LsR` (Wire `StatusPrivacyAction`), `M7H` (enum الوضع) | إجراء حالة التطبيق 44 |

---

## 2. نموذج JID

### 2.1 التحليل (found)

| القاعدة | القيمة |
|---------|--------|
| الخادم | `broadcast` |
| المستخدم `status` / `location` | كائنات مفردة `C199018dF` / `BOC` |
| أي مستخدم آخر | `C99P`: الطول 1..20، أول محرف `1`..`9`، باقي المحارف `0`..`9`، وإلا يُرمى `C09B` |

قاعدة منع الصفر البادئ مقروءة من باني `C99P` (يقارن smali مع `0x31`/`0x39`، والباقي `0x30`..`0x39`). القائمة ليست `g.us`، لكنها تعيد استخدام آلية مشاركي المجموعات (3.5).

### 2.2 التخصيص (found, `C0YJ.A0E`)

المعرّف هو `System.currentTimeMillis() / 1000` متبوعًا بـ `@broadcast`، ويُزاد بثانية واحدة طالما توجد قائمة بهذا المعرّف محليًا. تُفحص الفرادة مقابل قائمة الدردشات المحلية فقط؛ لا يسبق التخصيص أي نداء إلى الخادم (لا يوجد IQ للإنشاء، 3.3). لا يمكن تحديد ما إذا كان الخادم يقبل معرّفًا اعتباطيًا بشكل ساكن.

---

## 3. دورة حياة القائمة

### 3.1 الإنشاء (found، جزئيًا inferred)

```
[Picker]  "New broadcast" (menu item hidden when BRD() = companion mode), max 256 selected
     ▼
createBroadcastList callback (C222519hZ):
     │   C0YJ.A0E()                                allocate <seconds>@broadcast
     │   A0K.A04(jid, users): C70552yj.A00 → LID filter ; C22300su.A0h → local participants ; contact entry (name "")
     ▼
compose flow opens; system message "You created broadcast list "X" with N recipients"
```

لا يصدر `A0K.A04` أي IQ ولا طفرة لحالة التطبيق (found). أول حدث مرئي للخادم هو أول إرسال إلى JID القائمة (4.2)؛ أن الخادم يشتق حالة القائمة منه أمر inferred. يُعاد استخدام نفس التخصيص لدعوات متابعي القنوات (`userActionSendNewsletterFollowerInviteMessages`، found).

### 3.2 حدود العضوية وقواعد المستلمين

| القاعدة | القيمة | المستوى |
|---------|--------|---------|
| الحد الأقصى للمستلمين | 256: يرفض `ContactPickerFragmentKt.A39` الحالة `selected.size() > 256` (`Broadcast to a maximum of %d people at a time`)؛ حد المنتقي `min(256, groupLimit - 1)` | found |
| مصدر المستلمين | منتقي جهات الاتصال؛ نص الإذن `To create a broadcast … allow WhatsApp access to your contacts`؛ جهات الاتصال المحظورة: `To add to broadcast list, unblock %s` | found |
| يجب أن يكون المرسل محفوظًا لدى المستلم | نص واجهة فقط (`Only contacts who have you in their address book will receive your broadcast messages.`)؛ التطبيق يتم على الخادم | found (النص)، unknown (التطبيق) |
| عنونة LID | يعيد `A0K.A01` دائمًا `lid`؛ يُسقط مشاركو PN الذين لا يملكون ربط LID (`lid-broadcast-filtered-participants`) | found |
| ربط مفقود عند الإرسال | `missing_pn_lid_mapping_for_broadcast`: يُتخطى الاستنساخ، ويرمي المشفّر `E39(device, 4)` | found |
| مجموعة مشاركين فارغة | `saveGroupParticipants/broadcast_would_be_cleared`؛ مع flag **30111** (الافتراضي true) يُحتفظ بالمشاركين المخزّنين | found |

### 3.3 IQ الخادم (found)

ثلاثة IQ فقط تمس القوائم. لا يوجد IQ للإنشاء أو التعديل.

```xml
<!-- restore: BroadcastXmppMethods/sendGetBroadcastLists -->
<iq to="s.whatsapp.net" xmlns="w:b" type="get" id="…"><lists/></iq>
<iq type="result"><lists>
  <list id="1760000000@broadcast" name="Family">
    <recipient jid="<lid>@lid" pn_jid="<pn>@s.whatsapp.net" username="…"/>   <!-- pn_jid, username read for LID recipients -->
  </list>
</lists></iq>

<!-- delete: sendDeleteBroadcastList -->
<iq to="s.whatsapp.net" xmlns="w:b" type="set" id="…"><delete><list id="1760000000@broadcast"/></delete></iq>

<!-- quota (5.1) -->
<iq to="s.whatsapp.net" xmlns="w:b" smax_id="143" type="get" id="…"/>
```

تستخدم الثلاثة مهلة 32 ثانية. ينشئ `AKU` (نتيجة الجلب) لكل `<list>` بلا دردشة أو إدخال جهة اتصال محلي: الدردشة (`A0K.A00`، رسالة نظام من النوع 9) وإدخال جهة اتصال، ويخزّن خرائط `pn_jid` و`username`. يُرسل الحذف عبر `C18240lQ.A01` ويتبعه REMOVE في حالة التطبيق (3.4).

محفّز الاستعادة (found): يضبط `RegistrationInitializer/shouldrefreshlists` الـ pref `refresh_broadcast_lists=true` ويرسل get-lists (مع get-privacy-settings) بعد التسجيل؛ يكرر `MessageHandlerCallback/ready` ذلك ما دام الـ pref بقيمة true؛ ويمسحه `AKU`. إذن يحفظ الخادم القوائم لكل حساب (found بالاستلزام). كيف يعرف الخادم قائمةً ما غير مرئي من جهة العميل (unknown، انظر 3.1).

### 3.4 طفرة حالة التطبيق (found)

| البند | القيمة |
|-------|--------|
| الإجراء | `BusinessBroadcastListAction`، الاسم على الشبكة `business_broadcast_list` (`EnumC24865AnN.A0H`، الترتيب 62)، الحقل **69** في `SyncActionValue`، المجموعة `regular`، إصدار API 7 |
| الفهرس | `["business_broadcast_list", "<list jid>"]` |
| العملية | SET عند الإضافة والإزالة وإعادة التسمية؛ REMOVE مع `deleted=true` ومشاركين فارغين واسم `""` عند حذف القائمة (`A0T`, `syncBusinessBroadcastListRemoval`) |
| البوابة | `C12440bB.A0b()` (syncd غير محظور أو companion-dirty)؛ خطافات Business (`storeForBroadcast`, `onAudienceChanged`, `getCustomAudienceFbidForBroadcast`) غائبة في هذا الـ APK |
| المستدعون | `A0K.A03` / `A05` (إضافة / إزالة)، إعادة التسمية في `BroadcastListChatInfoActivity`، `C24085AaS` (مجموعة المشاركين) |
| جهة التطبيق | لا يشير أي معالج إلى `EnumC24865AnN.A0H`؛ لا يوجد إلا الكاتب (`C26057BNq`) ومُعرّف الحقل في `BD4`، لذا سلوك التطبيق لدى المستهلك unknown |

| الحقل | الرقم | النوع | القيمة / الاستخدام |
|-------|-------|-------|--------------------|
| `deleted` | **1** | bool | أُزيلت القائمة |
| `participants` | **2** | repeated `BroadcastListParticipant` | الجمهور (`lid_jid` **1** مطلوب، `pn_jid` **2**) |
| `list_name` | **3** | string | الموضوع |
| `label_ids` | **4** | repeated string | جمهور التسميات (بديل عن participants، لا يجتمعان أبدًا) |
| `audience_expression` | **5** | string | جمهور ديناميكي (Business) |
| `custom_audience_fbid` | **6** | string | Business فقط |

نفس المجموعة: `BusinessBroadcastCampaignAction` (81)، `BusinessBroadcastInsightsAction` (82)، `MarketingMessageBroadcastAction` (39)؛ وقيمتا enum فقط `BusinessBroadcastAssociationAction` (59) و`BusinessBroadcastAction` (94). الأساسيات: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md).

### 3.5 ترحيل LID، التخزين، الأجهزة المرافقة

تحوّل `BroadcastListLidMigrationTask` (`C0UV`) كل قائمة من مشاركي PN إلى مشاركي LID: usync واحد لجلب LID المفقودة (يُسجَّل الفشل كـ `usync_failed` وتتابع المهمة)، ثم يزيل `C70552yj.A03` مشاركي PN ويضيف مجموعة LID في معاملة واحدة.

| المخزن | المحتوى | المستوى |
|--------|---------|---------|
| `chat` / `chat_view`, `jid.type = 3`, `subject`, `created_timestamp`, `hidden` | دردشة القائمة (`C222989iV`) | found |
| `group_participant_user` (`group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `label`, `add_timestamp`), `group_participant_device` | المستلمون، مشترك مع المجموعات | found |
| `wa_group_admin_settings` (`jid`, `addressing_mode`, `group_state`) | وضع العنونة لكل قائمة (تعدّ القياسات عن بُعد صفوف `@broadcast`) | found |
| أعمدة `message`: `broadcast`, `recipient_count`, `participant_hash`, `key_id`, `chat_row_id`, `from_me` | رسالة القائمة وبيانات ack | found |
| `message_broadcast_ephemeral` (`message_row_id`, `shared_secret`) | سر لكل رسالة للرسائل المؤقتة في القوائم | found |

الأجهزة المرافقة (found): تُضاف عناصر القائمة `New broadcast` / `Broadcast lists` فقط عندما تكون `BRD()` false؛ يرمي `C34757F6a` الاستثناء `E3A(415, "received peer broadcast message on companion-mode, dropping", 18)` لنسخة قائمة من الحساب نفسه تحمل `<participants>`؛ ولا يوجد معالج تطبيق للإجراء 69.

---

## 4. الإرسال إلى قائمة

### 4.1 التوزيع المحلي (found, `C231399zG`)

```java
// A02(msg): msg.fromMe, not one of two excluded message classes, status 0 or 2 (or 4 with flag 26867)
msg.A0Z = true;                                   // message.broadcast = 1
for (recipient : msg.A0A())                       // recipient list stored on the FMessage
    normalized = lidMapper.A0C(recipient);        // null → missing_pn_lid_mapping_for_broadcast, skip
    store.add(cloneFactory.A00(msg, new C1ZA(normalized, msg.key.id, true)));   // own row in the recipient's 1:1 chat
```

| الخاصية | القيمة |
|---------|--------|
| معرّف الرسالة | متطابق لرسالة القائمة وكل نسخة (يُنسخ `key_id`، والدردشة فقط تختلف) |
| العدّادات | `recipient_count` (`FMessage.A06`) على صف القائمة؛ يرتفع عدّاد مراجع ملف الوسائط بعدد النسخ |
| التكرارات | يُسجَّل `SQLiteConstraintException` عند مفتاح نسخة موجود ويُتخطى |
| الرسائل المؤقتة | تأخذ النسخة الإعداد الخاص بكل مستلم من خريطة الرسائل المؤقتة (بمفتاح الجهاز الأساسي للمستلم)؛ صفوف الانتهاء في `message_ephemeral` |

### 4.2 صيغة الشبكة (found، جزئيًا inferred)

stanza واحد موجّه إلى JID القائمة (مثال، قيم السمات توضيحية). يعيد التشفير استخدام مسار المجموعات (`F6P` مُنمَّط على `AbstractC20660pZ`): نص مشفّر واحد بـ sender-key بالإضافة إلى رسائل توزيع sender-key لكل جهاز. لا تتكرر هنا أساسيات sender-key والجلسات.

```xml
<message to="1760000000@broadcast" type="text" id="3EB0…" t="…" phash="2:AbCdEf==" addressing_mode="lid">
  <participants>
    <to jid="<recipient device jid>"><enc v="2" type="pkmsg|msg" …/></to>   <!-- SKDM wrapped pairwise -->
  </participants>
  <enc v="2" type="skmsg" …/>                                                <!-- message under the sender key -->
  <cap client_capping_ready="true|false"/>                                   <!-- flag 16656 only -->
</message>
```

| السمة | المصدر | ملاحظات |
|-------|--------|---------|
| `to`, `type`, `id`, `t` | JID الدردشة (`C33150EcP.A07`), `AbstractC30999De0.A02`, `C1ZA.A01`, `originalTimestamp` | `to` هو JID القائمة (inferred من الباني المشترك)؛ `t` فقط عندما لا يساوي صفرًا |
| `phash` | `groupParticipantHash` | 4.3 |
| `bucketing` | `eva.A05` | `primcomp` عندما flag **28183** وعدد المشاركين ≥ **28185** (512)؛ تبقى القوائم (≤ 256) غير مضبوطة عمليًا (inferred) |
| `addressing_mode` | `lid` | يُحذف لـ JID من النوع 28 |
| `participant`, `recipient`, `recipient_pn`, `peer_recipient_pn`, `peer_recipient_username` | حقول المهمة | إرسالات peer / إعادة المحاولة / DSM |
| `edit`, `expiration`, `device_fanout="false"`, `privacy_sensitive="1"` | حقول المهمة | اختيارية |

تأتي العناصر الفرعية من المساهمين (`InterfaceC35538FaZ.ASY`, `processStanzaNodeParamsUsingNewFramework`). يضيف `F69` العنصر `<cap client_capping_ready="…"/>` لدردشات القوائم عندما يكون flag **16656** مفعّلًا؛ والقيمة هي flag **13537**.

| الخطوة | التفصيل | المستوى |
|--------|---------|---------|
| أجهزة المستلمين | مجموعة مدير المشاركين مطروحًا منها أنواع الأجهزة 26 / 27 (`F6P.A07`، الأجهزة المستضافة inferred)؛ لدردشات القوائم يضيف `AxolotlMultiDeviceSessionRequirement` أجهزة الحساب المرافقة الخاصة (`BPE`: المستخدم نفسه، غير أساسي) إلى مجموعة أهداف SKDM | found / inferred |
| اسم sender key | (عنوان الجهاز الخاص، سلسلة `groupId` من `A0J`)؛ يُكتب `A0J` في `SenderKeyDistributionMessage.groupId`؛ الحالة `-1002` من `encryptForGroup` = sender key غير صالح، يُدوَّر | found |
| كتل مؤقتة لكل مستلم | `F6P.A0A` (`buildBroadcastListEphemeralSettings`): لكل جهاز مستلم مفقود من الخريطة الثنائية (تُتخطى الأجهزة المرافقة الخاصة) يبني `EphemeralSetting(expiration or afterReadDuration, timestamp)` ويشفّره أصليًا (native) بالـ `shared_secret` الخاص بالرسالة (`JniBridge.jvidispatchOOOOOOO`)؛ إعداد مفقود يرمي `E39(device, 4)`. الغرض (مؤقتات لكل مستلم داخل stanza واحد) inferred | found / inferred |
| الأجهزة الخاصة | تُغلَّف الرسالة في `DeviceSentMessage` مع `destinationJid = list` و`phash` لأجهزة المستلمين (`C33284Eea.A01`) | found |
| الحجم | `BoundedStanzaSizeException` → `stanza-too-large` / `large payload` | found |

### 4.3 `phash` (found, `AbstractC44221r5`)

`<version>:` + base64 (`NO_WRAP`، مع إبقاء الحشو) لأول 6 بايتات من SHA-256 على أجهزة المستلمين المرتبة. الإصدار `2:` يحسب hash لسلاسل `user.0:device@server` (flag **16731** false، الافتراضي)؛ الإصدار `3:` يحسب hash للسلاسل الخام للأجهزة (flag **16731** true). يُستخدم لـ stanza المجموعات والقوائم والحالات.

### 4.4 Ack والإيصالات (found)

| الحدث | المعالجة |
|-------|----------|
| ack الخادم | `C22500tF` → `C22790ti.A04`: لدردشات القوائم (وليس الحالة) يحدّث `message` حيث `chat_row_id IN (list chat, every clone chat) AND from_me = 1 AND key_id = ?` بالقيم `status` و`receipt_server_timestamp` و`recipient_count`؛ ويرجع إلى مسح بحسب `timestamp/from_me/key_id` (`UPDATE_RCV_BROADCAST_SERVER_SQL`، السجل `message-table-scan`) عندما تكون قائمة المستلمين أقصر من `recipient_count` |
| إيصال المستلم | `MessageStatusStore.splitStatusUpdateReceipts`: يُربط إيصال مفتاح القائمة بالنسخة `(normalized recipient, same id, fromMe)` ويُطبَّق على النسخة (`broadcast-individual`) وعلى الرسالة المتعددة؛ تُسقط خفض الحالة (`broadcast-statusdowngrade`)؛ النسخة المجهولة تسجّل `nosuchmessage for broadcast` |

قاعدة الحالة الملخصة لصف القائمة وما يعرضه هاتف المستلم غير محلولة (unknown).

---

## 5. الحدود وضوابط إساءة الاستخدام

### 5.1 الحصة الشهرية للبث (found، مسار المستهلك)

```
iq get xmlns=w:b smax_id=143
  → <limits is_heavy_sender="true|false" messages_left="N" total_limit="M"/>
    <timeframe start_ts_s="…" reset_ts_s="…" end_ts_s="…"/>
```

فحوص النطاق في العميل: `messages_left` 0..300، `total_limit` 1..300، الطوابع الزمنية 2020-01-01..2100-01-01. تُربط أكواد IQ الخطأ بنتائج العميل: `400` → 3، `401` → 4، `403` → 5، `500` → 1، غير ذلك → 0، عدم وجود اتصال أو فشل التسليم → 2 (`consumer_broadcast_capping_iq_error_response`).

| الآلية | التفصيل |
|--------|---------|
| التخزين المؤقت | prefs `broadcast_quota_messages_left`, `_message_limit`, `_last_timestamp_fetched_ms`, `_heavy_sender`, `_start_timestamp`, `_end_timestamp`, `_reset_timestamp` |
| التحديث | عندما يتجاوز الوقت منذ آخر جلب قيمة flag **13818** بالدقائق (الافتراضي 1440) أو now ≥ `reset_ts_s` (التركيبة مشوّشة في فك التجميع، OR inferred) |
| الإنقاص / الزيادة | `C74823Ej`: لكل رسالة قائمة مضافة موسومة `broadcast` وليست ضمن مجموعة أنواع الرسائل المعفاة (`C2EX.A00`)، لكل رسالة وليس لكل مستلم؛ تُعاد الزيادة عند حذف رسائل القائمة غير المرسلة، بحد أقصى `total_limit` |
| الحظر قبل الإرسال | المسند في `C20M`: دردشة قائمة وflags **16585** و**13537** و`messages_left == 0` ← يُرفض الإرسال، وتظهر ورقة سفلية `You've reached the broadcast limit for this month` |
| الواجهة / القياس عن بُعد | `Send up to %d broadcasts per month`، ورقة التهيئة للمرسلين الكثيفين (`CappingBroadcastManager`)؛ `wam_broadcast_list` (`blLimit`, `currentBlSends`, `numBlLists`, `broadcastListSize`) |

قيمة السقف يوفرها الخادم؛ لا يوجد في العميل إلا فحص النطاق. خطافات جانب Business (`isSmbPremiumBroadcastCappingEnabled`) هي stubs في هذا الـ APK.

### 5.2 حظر تحذير السبام (found)

تأخذ `SpamWarningActivity` كودًا من الخادم (`spam_warning_reason_key`)، و`expiry_in_seconds`، ونصًا اختياريًا من الخادم ورابط FAQ. الأكواد: **101** رسائل إلى أشخاص لا يملكون المرسل في دفتر عناوينهم، **102** حظر كثير، **103** مجموعات تضم أشخاصًا لم يحفظوا المرسل، **104** نفس الرسالة إلى عدد كبير من الأشخاص، **106** رسائل كثيرة جدًا إلى قائمة بث؛ وغيرها يعرض حظر شروط الخدمة العام. مسار التسليم وباقي سطح الحظر: [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md). العتبات على جانب الخادم (unknown).

### 5.3 الإعداد 20278 وGAP

- الإعداد **20278** موجود فقط كسلسلة افتراضية `{"max_messages": 10000, "farthest_time_days": 30}` في جدولي افتراضيات. لا يوجد أي مرجع آخر لـ `max_messages` / `farthest_time_days` في كود المستهلك، لذا لم يُعثر على قارئ. وهو ليس سقف قوائم المستهلك (5.1)؛ استخدامه unknown (افتراضي لجانب Business).
- GAP (`com.whatsapp.gapenforcement`، flag **14837**، الافتراضي false) على جانب الاستقبال: يقيّم `GapEnforcementTrigger.onMarketingMessageReceived` و`RulesManager` قواعد صندوق الوارد لسلاسل الرسائل التسويقية (`parseMaxMmThreadsInTopInboxSize`, `parseNoConsecutiveInTopInboxSize`, `parseMinNUpdatedP`) ويسجّلان نتائج الدقة؛ لا يعمل على الأجهزة المرافقة ولا يحد من الإرسال من القوائم. توسيع الاختصار غير موجود في الـ APK (unknown).

---

## 6. status@broadcast

### 6.1 مسار الإرسال (found)

لدى `SendE2eStatusJob` نوع (`EnumC32060Dzj`): `STATUS` 0 (المنشور، الجدول `status`)، `STATUS_ADD_ON` 1 (التفاعلات وغيرها من الإضافات، `status_add_on`)، `STATUS_NOTIFY` 2 (إشعارات الرد / إعادة المشاركة / الإشارة، `status_notify`). يستخدم stanza باني السمات الوارد في 4.2 بالإضافة إلى مساهمي `<meta>` (مثال، قيم السمات توضيحية):

```xml
<message to="status@broadcast" type="media" id="3EB0…" phash="2:…" bucketing="manual" addressing_mode="lid">
  <participants><to jid="<device>"><enc v="2" type="pkmsg|msg"/></to>…</participants>
  <enc v="2" type="skmsg" bucket="f1"/>                      <!-- one per bucket when bucketed -->
  <meta status_setting="contacts" session_scope="status"/>
</message>
```

| السمة | القيم المقبولة (مجموعات قيم stanza، `C9E2`) |
|-------|---------------------------------------------|
| `status_setting` | `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist` |
| `content_type` | `add_on`, `status_notify` |
| `message_association_type` | `av1_video_dual_upload`, `hd_image_dual_upload`, `hd_video_dual_upload`, `hevc_video_dual_upload` |
| `interaction_type` | `question`, `question_reshare` (مع `parent_server_id`, `response_server_id`) |
| `bucketing` | `manual`, `primcomp`, `threebuckets` (`threebuckets` فقط في مجموعة القيم) |

| البند | التفصيل |
|-------|---------|
| مهلة ack | 300000 ms (`no ack within 300000ms`) |
| الأجزاء | تُقسَّم الجماهير الكبيرة: `status_send_part` (`status_row_id`, `part_code`, `is_first_part`, `device_count`, `state`, `sent_timestamp`, `ack_timestamp`, `error_code`, `stanza_devices_hash`)؛ تتبع الأجهزة في `status_receipt_device` (`uuid`, `receipt_device_jid`, `receipt_device_timestamp`, `primary_device_version`, `part_code`) |
| حالة المجموعة | `buildGroupStatus called with non-PermanentGroupJid`؛ `is_group_status`؛ حقول Message 92 / 96 / 103 |
| إخفاقات البناء | `StatusStanzaBuildFailureReason`: `MISSING_RETRY_CIPHERTEXT`, `TARGETS_UNRESOLVABLE`, `PART_ATTEMPT_PERSISTENCE_FAILED`, `CANONICAL_ACK_PENDING`, `EMPTY_FANOUT`, `NON_CURRENT_BATCH`, `MISSING_SENDER_KEY_CIPHERTEXT`, `UNKNOWN` |
| إخفاقات المهمة | `encryption_limit`, `out_of_memory`, `payload_too_large`, `stanza_error`, `stanza_too_large` (يُعالَج عندما يكون flag **29113** مفعّلًا), `unrecoverable_error` |

### 6.2 الجمهور: أوضاع الخصوصية (found)

يُحل الجمهور على جانب المرسل ويُوسَّع إلى أجهزة مستلمين صريحة؛ السمة `status_setting` تسمّي الوضع فقط. الحالة المحلية: `C11550Zh` (prefs `status_distribution`, `status_distribution_modes`, `status_white_list`, `status_black_list`).

| الوضع المحلي | الاسم | `status_setting` | `M7H` على الشبكة (حالة التطبيق) |
|--------------|-------|------------------|----------------------------------|
| 0 | جهات اتصالي | `contacts` | `CONTACTS` 2 |
| 1 | المشاركة مع فقط | `allowlist` | `ALLOW_LIST` 0 |
| 2 | جهات اتصالي باستثناء | `denylist` | `DENY_LIST` 1 |
| 3 | بديل غير مضبوط في `C182877r0.A01()`؛ ترفضه طفرة المزامنة (`StatusPrivacySyncMutation invalid status setting`) | | |
| 4 | جمهور مخصص / الأصدقاء المقرّبون | `customlist` / `closefriends` (inferred) | `CUSTOM_LIST` 4 (`CLOSE_FRIENDS` 3 موجود في enum، غير مُنتَج) |

الربط من المحلي إلى الشبكة (found, `C48386LBh.A04`): 1 → 0، 2 → 1، 4 → 4، وغير ذلك 2. تُسجَّل أسماء الأوضاع 0..2 أيضًا بواسطة مهمة الإرسال بالشكل `contacts` / `allowlist` / `denylist`.

تستخدم قوائم الخصوصية على الخادم IQ من نوع `privacy`، الفئة `status` (اسم الفئة من `AboutStatusPrivacyActivity`):

```xml
<iq to="s.whatsapp.net" xmlns="privacy" type="get" id="…">
  <privacy addressing_mode="lid"><list name="status" value="contact_allowlist|contact_blacklist" dhash="…"/></privacy>
</iq>
<iq xmlns="privacy" type="set"><privacy><category name="status" value="contacts|contact_blacklist|contact_allowlist"/></privacy></iq>
```

(`AbstractC230749y7.A02`, `C228009tS`, `C18260lS.A0P`؛ الجلب عبر MEX / SMAX / shadow بحسب flag **23463**، والضبط عبر MEX عندما **23639**، وإلا SMAX.)

### 6.3 الجماهير المخصصة والأصدقاء المقرّبون (found)

نصوص الواجهة: `New: Close friends`, `People you include see a purple ring on your status`, `Create audience`, `Choose name & emoji`.

| البند | القيمة |
|-------|--------|
| الجدول `status_privacy_custom_list` | `row_id` (PK), `list_id` (unique), `name`, `emoji`, `is_selected` (الافتراضي 0), `member_jids`, `source_group_jids`, `allow_list_selected`؛ محفوظ في كل من مخزن الرسائل ومخزن الحالة (`*_MSGSTORE_DB`, `*_STATUS_DB`) |
| حالة التطبيق | `status_privacy` (الترتيب 38، `regular_high`، الحقل **44**)؛ `StatusPrivacyAction`: `mode` **1**, `user_jid` **2**, `shareToFB` **3**, `shareToIG` **4**, `custom_lists` **5**, `modes` **6**؛ `StatusCustomList`: `list_id` **1**, `name` **2**, `emoji` **3**, `is_selected` **4**, `user_jid` **5** |
| سجل لكل منشور | `status_message_info`: `status_distribution_mode`, `selected_audience_list`, `audience_type`, `status_audience_custom_list_name`, `_emoji` |
| التحقق | `StatusParticipantUserManager/validateAudience` (يتضمن فحص `HAS_STATUS_AUDIENCE` على `wa_contacts`)، `StatusEmptyAudienceGuard` في المحررات |

ذات صلة: `userStatusMute` (الترتيب 23، الحقل 29، `muted`). تتطلب الأوضاع المتزامنة المتعددة flag **28731**، ومخزن القوائم المخصصة **27031** (كلاهما الافتراضي false؛ مساعدات إعداد الحالة `A0F` / `A0I` تتحكم بهذا أيضًا، غير محلولة).

### 6.4 دلاء sender-key اليدوية (found)

| البند | التفصيل |
|-------|---------|
| الجدول `manual_user_group_bucket` | `row_id`, `user_jid_row_id`, `multi_participant_jid_row_id`, `status_audience`, `bucket`؛ فهرس فريد على المستخدم + المجموعة |
| أسماء الجماهير / بادئات الدلاء | `contacts` → `c`، `close_friends` → `f`، `allow_list` → `a`، `close_friends:<id>` → بادئة مشتقة؛ الأسماء الأخرى ترمي `Unknown manual SKB audience name` |
| المخزن / التخطيط | `ManualBucketStore/assignUsersToBuckets`, `deleteRowsForBuckets`, `getHoldersByBucketForGroup`؛ `ManualBucketingUtils/planSend`, `trimToEncBudget`؛ `SenderKeyBucketingRollback/cleanupBucketedState` |
| Flags | **28184** + سقف الطرح **34545** (0 = الجميع) يفعّلان التقسيم اليدوي للحالة (`C23340ub.A01`) |

### 6.5 الرد، التفاعل، الإشارة، الإشعار (found)

| التفاعل | الآلية |
|---------|--------|
| الرد | رسالة 1:1 عادية تقتبس الحالة (`status_reply`: `status_row_id`, `ref_id`, `reply_timestamp`)؛ `Message.statusQuotedMessage` (الحقل **109**) لردود الأسئلة |
| التفاعل / الإضافة | نوع المهمة `STATUS_ADD_ON`؛ `status_add_on` (`status_row_id`, `type`, `uuid`, `sender_user_jid`, `state`, `sender_timestamp`, `is_revoked`, `content_proto`, `secret`)؛ بوابات لكل منشور `cannot_receive_reactions`, `can_receive_multi_reactions` |
| الإشارة | `status_message_info.is_mentioned`, `status_mentions`, `status_mention_source`؛ `Message.statusMentionMessage` (الحقل **87**) غلاف بحقل واحد (`message` **1**) يُفكّ كما `viewOnceMessage` (`C35228FOg`)؛ باقي الدلالات inferred |
| الإشعار | `Message.statusNotificationMessage` (الحقل **98**): `responseMessageKey` **1**, `originalMessageKey` **2**, `type` **3** (1 أضف خاصتك، 2 إعادة مشاركة، 3 إعادة مشاركة إجابة سؤال، 4 رد على حالة مجموعة)؛ يُخزَّن في `status_notify` |
| حقول ذات صلة | `groupStatusMentionMessage` **92**, `groupStatusMessage` **96**, `groupStatusMessageV2` **103**, `statusQuestionAnswerMessage` **105**, `statusStickerInteractionMessage` **110** |

### 6.6 تخزين الحالة (found)

| الجدول | الأعمدة الرئيسية |
|--------|------------------|
| `status` (مخزن الحالة) | `uuid`, `sender_user_jid`, `status_info_row_id`, `type`, `timestamp`, `server_receipt_timestamp`, `state`, `secret`, `content_proto`, `origin`, `flags`, `audience_type`, `stanza_xml`, `batch_state` |
| `status` (مخزن الرسائل، ملخص قديم)، `status_info` | `jid_row_id` / `chat_jid`, `unseen_count` / `unread_count`, `total_count`, `unread_count_close_friends` |
| `status_message_info` | `message_row_id`, `status_distribution_mode` (3 عند عدم الضبط)، بوابات الإشارة / التفاعل / إعادة المشاركة، `is_group_status`, `ranking_version`، أعمدة الجمهور (6.3) |
| `status_send_part`, `status_receipt_device`, `manual_user_group_bucket` | حالة الإرسال (6.1، 6.4) |

الجدولان المسمّيان `status` لهما أعمدة منفصلة تمامًا ويقيمان في قاعدتي بيانات مختلفتين (inferred من الوسمين `MSGSTORE_DB` / `STATUS_DB`). الجداول الأخرى (`status_media_link`, `status_seen_receipt`, `status_ranking*`, `status_interactions*`) مذكورة بالاسم فقط.

---

## 7. Feature flags

المعرّفات كما قُرئت في مواضع الاستدعاء؛ الافتراضيات من جداول الافتراضيات المترجمة.

| المعرّف | الافتراضي | يتحكم في |
|---------|-----------|----------|
| **13537** | false | تقييد بث المستهلك (capping): صفحة القوائم الرئيسية، جلب / إنقاص الحصة، قيمة `client_capping_ready` |
| **16585** | true | حظر إرسال القوائم عندما `messages_left == 0` |
| **16656** | false | يضيف `<cap client_capping_ready/>` إلى stanza القوائم |
| **13818** | 1440 | فترة تحديث الحصة (بالدقائق) |
| **15515** | true | مساعد واجهة التقييد (`C33z.A08`، مع 13537) |
| **19790** | false | عند true، يتخطى الاستنساخ عند الإدراج ربط الرسالة المقتبسة |
| **26867** | true | فرع الاستنساخ عند الإدراج للرسائل المرسلة بالحالة 4 (المعنى غير محلول) |
| **30111** | true | الإبقاء على مشاركي القائمة المخزّنين عندما يؤدي الحفظ إلى مسحهم |
| **16731** | false | متغير `phash` بالإصدار `3:` بدل `2:` |
| **28183** / **28184** | false / false | التقسيم الرئيسي `primcomp` / التقسيم اليدوي للحالة |
| **28185** / **28199** / **34545** | 512 / 2 / 0 | عتبة المشاركين للتقسيم / العدد الصحيح الثاني (غير محلول) / سقف الطرح |
| **28731** / **27031** | false / false | أوضاع حالة متعددة / مخزن القوائم المخصصة |
| **29113** | false | معالجة stanza-too-large للحالة |
| **23463** / **23639** / **23874** | 0 / false / false | بروتوكول جلب الخصوصية (1 MEX، 2 shadow، وإلا SMAX) / ضبط الخصوصية عبر MEX / مسار جلب قائمة الخصوصية |
| **14837** | false | GAP enforcement |
| **20278** (string) | `{"max_messages": 10000, "farthest_time_days": 30}` | افتراضي حد البث في Business، بلا قارئ لدى المستهلك |

---

## 8. Baileys (`baron-baileys-v2`، جرى الفحص مقابل مصدره)

| المجال | التنفيذ | الحكم مقابل 2.26.41.6 |
|--------|---------|------------------------|
| إرسال الحالة | `messages-send.js`: `isStatus`, `statusJidList` تُلحق بقائمة المشاركين، `<meta status_setting session_scope="status">` | يطابق 6.1 / 6.2؛ لا يُتحقق من `statusPrivacy` (الصالح: `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist`) |
| حجم الجمهور | `statusJidList` صريحة، بلا دلاء، بلا سمة `bucketing` | الجماهير الكبيرة تصطدم بحدود stanza (6.1) |
| حذف قائمة | `deleteBroadcastList`: `w:b` set، `<delete><list id/></delete>` | يطابق 3.3 |
| الحصة | `fetchBroadcastListQuota`: `xmlns="w:biz"` مع العنصر الفرعي `<broadcast_list_quota/>` | الطلب لا يطابق (`w:b`، `smax_id=143`، بلا عنصر فرعي)؛ تحليل الاستجابة يطابق |
| جلب القوائم / حالة التطبيق / إرسال القائمة | غير منفَّذ / يُصدَر `businessBroadcastListAction` كـ `settings.update` / `isJidBroadcast` لفك الترميز فقط | انظر أدناه |

| العَرَض | السبب | الإصلاح |
|---------|-------|---------|
| إرسال قائمة كلاسيكية يُسقط أو يُرفض | القوائم حالة للجهاز الأساسي: الأجهزة المرافقة تخفي الميزة، وتُسقط نسخ قوائم الحساب نفسه التي تحمل `participants` (415)، ولا يوجد IQ للإنشاء | لا تستهدف JID القوائم من جهاز مرافق؛ أرسل رسائل 1:1 لكل مستلم أو استخدم `status@broadcast` مع `statusJidList` |
| تعذّر حل المستلمين | لا بحث عن الأعضاء للقوائم على الأجهزة المرافقة؛ المشاركون معنونون بـ LID ومرشّحون بحسب الربط | حل LID عبر usync أولًا |
| أخطاء طلب الحصة | مساحة اسم خاطئة | `xmlns="w:b"`، `smax_id` 143، `type="get"`، `to="s.whatsapp.net"` |

الإرسالات 1:1 المنفصلة متوافقة من حيث النقل لكنها ليست قائمة كلاسيكية (لا دردشة قائمة ولا معرّف مشترك ولا حصة).

---

## 9. حالات الخطأ

| العَرَض | السبب | الإصلاح |
|---------|-------|---------|
| `missing_pn_lid_mapping_for_broadcast`, `lid-broadcast-filtered-participants` | PN المستلم بلا ربط LID | اجلب LID (usync) قبل الإضافة أو الإرسال |
| 415 `received peer broadcast message on companion-mode` | نسخة قائمة تحمل `participants` على جهاز مرافق | متوقع، الأجهزة المرافقة لا تعالج إرسالات القوائم |
| الإرسال محظور، ورقة الحد | `messages_left == 0` مع 13537 و16585 | انتظر `reset_ts_s`، احذف رسائل القائمة غير المرسلة |
| كود الحظر 106 | رسائل كثيرة جدًا إلى قائمة بث | انتظر `expiry_in_seconds` |
| `broadcast_would_be_cleared` | حفظ المشاركين بمجموعة فارغة | flag 30111 يُبقي على المشاركين |
| `EMPTY_FANOUT` | الجمهور حُلّ إلى صفر أجهزة | أصلح الجمهور، ينبغي أن يحظر `StatusEmptyAudienceGuard` قبل ذلك |
| `stanza_too_large`, `payload_too_large` | أجهزة أو حمولة كثيرة جدًا | الأجزاء / الدلاء (6.1، 6.4)، flag 29113 |

---

## 10. فروق أساسية

| لا تخلط بين | الفرق |
|-------------|-------|
| القائمة (النوع 3) و`status@broadcast` (النوع 5) | القائمة: مستلمون مخزّنون، نسخ لكل مستلم، حصة شهرية؛ الحالة: جمهور لكل منشور، بلا نسخ، جداول خاصة |
| القائمة والمجموعة | نفس مخزن المشاركين ومسار sender-key؛ القائمة للجهاز الأساسي فقط، المستلمون ليسوا أعضاء ويرون دردشات 1:1 |
| قوائم الخادم `w:b` وإجراء حالة التطبيق 69 | `w:b` يستعيد القوائم بعد التسجيل؛ الإجراء 69 يُكتب للمزامنة وليس له معالج تطبيق لدى المستهلك |
| الحصة (`w:b` smax 143، ≤ 300) والإعداد 20278 (10,000 / 30 يومًا) | الحصة يوفرها الخادم وتُفرض عبر الواجهة؛ 20278 بلا قارئ لدى المستهلك |
| الحصة وكود الحظر 106 وGAP | سقف مرن مع الواجهة / حظر مؤقت يصدره الخادم / قواعد صندوق وارد على جانب الاستقبال |
| IQ `privacy` والجماهير المخصصة | الـ IQ يحمل ثلاثة أوضاع للخادم؛ القوائم المخصصة والأصدقاء المقرّبون محليون بالإضافة إلى إجراء حالة التطبيق 44 |

---

## 11. التدفق الكامل

```
[User]  New broadcast → select ≤ 256 contacts
     ▼
[Client]  C0YJ.A0E → <seconds>@broadcast ; A0K.A04 → LID filter, group_participant_user rows
     │     send → message.broadcast = 1 ; C231399zG clones into each recipient chat (same key id)
     │     quota gate: 13537 + 16585, messages_left > 0
     ▼
[SendE2EMessageJob]  F6P: skmsg + SKDM per device (pkmsg/msg) + ephemeral blobs ; DSM to own devices (phash)
     ▼
<message to="<id>@broadcast" phash id><participants>…</participants><enc type="skmsg"/><cap/></message>
     ▼
[WA Server]  (not observed) fan-out, ack
     ▼
ack → C22500tF updates list row + all clones ; receipts → splitStatusUpdateReceipts ; quota decremented on add

[User]  status: choose audience (contacts / allow / deny / close friends / custom)
     ▼
[Client]  validateAudience → StatusEmptyAudienceGuard ; users → LID → devices ; buckets c / f / a when 28184 on
     ▼
[SendE2eStatusJob]  type STATUS ; status_send_part rows ; sender key per bucket
     ▼
<message to="status@broadcast" phash bucketing><participants>…</participants><enc type="skmsg" bucket/><meta status_setting session_scope/></message>
     ▼
[WA Server]  (not observed) ack within 300 s ; viewers reply / react
     ▼
status_add_on / status_notify / status_reply rows ; status_receipt_device bookkeeping
```

---

## 12. المجهولات

| البند | الحالة |
|-------|--------|
| كيف يسجّل الخادم قائمة (توجد فقط IQ الجلب / الحذف / الحصة) | التسجيل عند الإرسال inferred |
| قاعدة الخادم بأن يحفظ المستلمون المرسل؛ حجم القائمة وقيم الحصة | جانب الخادم (نص الواجهة وفحوص النطاق فقط) |
| سلوك تطبيق إجراء حالة التطبيق 69 لدى المستهلك | لم يُعثر على معالج |
| ما يتلقاه المستلمون لرسالة قائمة؛ قاعدة الإيصال الملخّص لصف القائمة | غير مرئي من جهة المرسل |
| تركيبة تحديث الحصة، مجموعة أنواع الرسائل المعفاة | فك التجميع مشوّش / لم يُتتبَّع |
| وضع الحالة المحلي 3، `threebuckets`، flags 28199 و26867 و15515، `A0F` / `A0I` لإعداد الحالة | غير محلولة |
| استخدام `location@broadcast`؛ توسيع "GAP" | لم يُتتبَّع / غير موجود في الـ APK |
| حركة الشبكة | لم يُلتقط شيء |
