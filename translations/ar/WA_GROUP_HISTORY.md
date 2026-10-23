<!-- src-sha1: 0c8270cd51a33a8c9e23ceb0a6129e273e5cb070 -->
# WhatsApp سجل المجموعة — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** مشاركة سجل المجموعة على Android (أحدث رسائل المجموعة المرسلة إلى الأعضاء الجدد): إعداد المشرف `member_share_group_history_mode`، أهلية المرسِل والمستقبِل، مسار الانضمام بالإضافة / الموافقة والمهمة المعلّقة، اختيار الرسائل وحدودها، `MessageHistoryBundle` (الحقل 70) و`MessageHistoryNotice` (الحقل 102)، بروتو `GroupHistory` الداخلي، تشفير وسائط الحزمة ورفعها، تحقق المستقبِل والاستيراد، بيانات المجموعة الوصفية (المشاركون، عنونة LID مقابل PN، علاقات المجتمع)، استخدام sender-key، رموز الإبلاغ، HistorySync للأجهزة المرافقة (`HistorySyncConfig`، أنواع المزامنة، عمليات peer عند الطلب)، feature flags، Baileys

---

## 1. ما هو (تقنيًا)

تتيح مشاركة سجل المجموعة لعضو في المجموعة (مشرف، أو أي عضو إذا سمح المشرف) أن يدفع حزمة من أحدث رسائل المجموعة إلى من أُضيفوا للتو، فيرى القادم الجديد السياق. وهي رسالة مجموعة عادية مشفّرة من طرف إلى طرف، حمولتها ملف وسائط (protobuf من إدخالات `WebMessageInfo`). وهي **ليست** HistorySync الخاص بالأجهزة المرافقة (القسم 11)، مع أن كليهما يشترك في كلمة "history" وبعض flags القدرات.

جميع العبارات مصدرها التحليل الساكن لـ APK المفكَّك؛ لم يُلتقط شيء على الشبكة. المستويات: **found** = قُرئ في الشيفرة أو الموارد، **inferred** = مستنتج من الشيفرة، **unknown** = لم يُحل. أُعيد حل الأسماء المموّهة في 2.26.41.6 انطلاقًا من سلاسل ثابتة (`FMessageGroupHistoryBundleProtobuf`، `GroupHistorySendPermissionChecker`، `PendingSendGroupHistoryJob`، `member_share_group_history_mode`، `Group History`).

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| رسالة الحزمة | `C213539Ar` (`FMessageGroupHistoryBundle`)، نوع FMessage **117** | رسالة وسائط خارجية، `Message.messageHistoryBundle` الحقل **70** |
| رسالة الإشعار | `C213519Ap` (`FMessageGroupHistoryNotice`)، نوع FMessage **118** | صف "أُرسل السجل"، `Message.messageHistoryNotice` الحقل **102** |
| مُسلسِل / محلل الحزمة | `C34677F2y` (`FMessageGroupHistoryBundleProtobuf`) | بناء الرسالة الخارجية والتحقق منها |
| مُسلسِل / محلل الإشعار | `C34678F2z` (`FMessageGroupHistoryNoticeProtobuf`) | بناء الإشعار والتحقق منه |
| بانِي الحزمة | `C9mW.A00` (+ `C231239yy`، `FMessageGroupHistoryBundleFactory`) | الاختيار والتعبئة وكتابة الملف وإنشاء رسالة الوسائط |
| اختيار الرسائل | `A0G` (`GroupHistoryMessageManager`) | SQL للعدّ والصفوف |
| الأهلية | `A1W` (`GroupHistorySendPermissionChecker`)، `C230099x1` (البوابات) | فحوص المرسِل / المستقبِل / نقطة الدخول |
| المهمة المعلّقة | `PendingSendGroupHistoryJob`، `SendGroupHistoryJobRequirement` | مهمة دائمة بعد الإضافة |
| مزوّد المتطلبات | `C197318aR` (`SendGroupHistoryRequirementProvider`) | أحداث الإضافة / الموافقة تحرّر المهمة |
| المستقبِل | `GroupHistoryBundleProcessor`، `GroupHistoryBundleFileProcessor` | التنزيل والتحليل والإدراج |
| المدققات / المُدرج | `C33241Eds`، `C34360Ew7`، `C34361Ew8`، `C33413Egg` (`GroupHistoryMessageValidator` / `GroupHistoryMessageInserter`) | فحوص كل رسالة وإدراج DB |
| صف نوع الوسائط | `C15530gU.A0F` | `group-history`، `GROUP_HISTORY`، HKDF info `Group History`، المعرّف **117** |
| واجهة الإعدادات | `com.whatsapp.grouphistory.setting.ui.*`، `GroupPermissionsActivity` (`C201678ic`) | حوار الكمية، مفتاح التذييل، مفتاح الإذن |

توجد رسالتان مختلفتان لكل مشاركة: **الحزمة** (تحمل البيانات، تُرسل إلى المجموعة) و**الإشعار** (يحمل الأعداد والمستقبِلين فقط، يُرسل بعد مغادرة الحزمة للجهاز، القسم 5.4).

---

## 2. بيانات المجموعة الوصفية والإعدادات

### 2.1 عقدة معلومات المجموعة (`<group>`، مسار XMPP القديم `C23201A1a.A0C`)

تُحلَّل بالمساعد نفسه في استعلامات `w:g2` وإشعارات المجموعة؛ ويوجد نظير MEX/SMAX (`AbstractC23204A1d`، `AN6`، `C23690AKd`). الحقول ذات الصلة هنا وبالعنونة فقط:

| السمة / الابن | النوع | الاستخدام |
|-------------------|------|-----|
| `id`، `creation`، `subject`، `s_t`، `s_o`، `s_o_pn`، `creator`، `creator_pn` | attrs | الهوية؛ نظائر `_pn` تحمل JID الهاتف بجانب LID |
| `addressing_mode` | `lid` أو `pn` | يُخزَّن في `wa_group_admin_settings.addressing_mode`؛ أي قيمة غير `pn` تُقرأ على أنها `lid` (`AbstractC268510t`) |
| `<group_history/>` | ابن فارغ | وجود منطقي؛ يُخزَّن كـ `history_enabled`؛ المعنى مستنتج (flag خاص بالمجموعة) |
| `<member_share_group_history_mode>` | نص | إعداد المشرف، 2.4 |
| `<member_add_mode>` | `all_member_add` / غيره | `member_add_mode` 1 / 0 |
| `parent`، `default_sub_group`، `linked_parent jid`، `general_chat` | أبناء | نوع المجموعة، 2.3 |

### 2.2 المشاركون والعنونة (found)

`<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`، `C23205A1e.A0J`):

| السمة | الاستخدام في سجل المجموعة |
|-----------|-----------------------|
| `jid` | المشارك، LID أو PN بحسب `addressing_mode`؛ يُفحص JID من نوع PN مع سمة `phone_number` بحثًا عن عدم تطابق |
| `lid`، `phone_number` | صيغة العنوان الأخرى؛ تُخزَّن عبر مستودع ربط JID |
| `join_time` | long موجب (ثوانٍ، مستنتج)؛ يُخزَّن لكل مشارك؛ أساس "انضم منذ وقت طويل" |
| `group_history_sent` | `"true"` / `"false"`، Boolean؛ يغذي `group_participant_user.group_history_send_state` (الربط مستنتج، 3.2) |

قوائم المستقبِلين والمرسِلين في بيانات الحزمة الوصفية (القسم 6.2) هي سلاسل JID. تُطبّعها المهمة إلى وضع عنونة المجموعة قبل الاستخدام: يربط `PendingSendGroupHistoryJob.A01` كل مستقبِل بـ **LID** الخاص به عندما تكون المجموعة معنونة بـ LID (`C30194DBb.A05`)، وإلا يربط LID بـ PN (`C0YH.A0G` / `AbstractC197018Zw.A0Y`). عند إضافة مشارك تقبل المهمة الصيغتين (يعطي `C0YH.A0J` النظير) لمطابقة مجموعات المتطلبات. أي صيغة تصل إلى الشبكة يعتمد على وضع المجموعة (مستنتج من شيفرة الربط).

### 2.3 علاقات المجتمع والمجموعة الأم

يصنّف `C23201A1a.A01` عقدة المجموعة: **0** عادية، **1** أم مجتمع (`parent`)، **2** مجموعة فرعية مرتبطة (`linked_parent`)، **3** مجموعة فرعية افتراضية (`default_sub_group`)، **6** دردشة عامة. يقرأ `A03` JID الأم من `linked_parent jid`. القيمة الافتراضية لـ `membership_approval_mode` في المجموعات الفرعية تأتي من `parent/default_membership_approval_mode="request_required"`.

Found: يفحص `A1W` **نوع JID** فقط (النوعان 1 و2 يمران عبر `C0DZ.A0l`: مجموعة `@g.us` ومجموعة `@temp` الخاصة بـ `C99Q`)، وليس دور المجتمع. يقبل المستقبِل النوع 1 فقط (`C0DZ.A0b`). هل تُستبعد المجموعة الأم / مجموعة الإعلانات ببوابات من جهة الخادم أو بتجارب لكل مجموعة (23245 / 30905 لكل مجموعة) غير معروف. رسائل التعليقات (تعليقات إعلانات المجتمع) وأبناء الربط تسافر في قوائم منفصلة (6.1)؛ يُسقط المستقبِل التعليق أو الابن الذي لا تكون أمه في الحزمة (`orphan_parent_not_in_bundle`، `invalid_comment`).

### 2.4 إعداد المشرف `member_share_group_history_mode`

| قيمة الشبكة | Enum (`EnumC216299Tq`) | int محلي | المعنى |
|------------|------------------------|-----------|---------|
| غائبة / غير معروفة | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` 0 | 0 | غير مضبوط |
| `admin_share` | `ADMIN_SHARE` 1 | 1 | المشرفون فقط يرسلون السجل |
| `all_member_share` | `ALL_MEMBER_SHARE` 2 | 2 | يجوز لأي عضو الإرسال |
| `all_member_share_toggle_on` | `ALL_MEMBER_SHARE_TOGGLE_ON` 3 | 2 | مثل 2؛ صيغة تظهر في الإشعارات (التمييز مستنتج) |

الربط: `AbstractC227759t3.A01(String)` (سلسلة إلى int)، `A00(enum)` (enum إلى int، و2 و3 إلى 2).

| البند | التفاصيل (found) |
|------|---------------|
| الضبط | مفتاح `GroupPermissionsActivity` (`C201678ic.A04`): عملية MEX ‏`SetGroupProperty` (العميل `whatsapp-android-mex`، صنف الإدخال `C204518nF`) مع `member_share_group_history_mode` = `ALL_MEMBER_SHARE` أو `ADMIN_SHARE`. يحمل الإدخال نفسه أيضًا `allow_admin_reports`، `allow_non_admin_sub_group_creation`، `announcement`، `hidden_group`، `locked`، `member_add_mode`، `member_link_mode`، `membership_approval_mode_enabled`، `participant_label_enabled`، `subject` |
| الإشعار | إشعار المجموعة (`w:gp2`، مستنتج) الابن `member_share_group_history_mode` (`C22270sr`) يستدعي `A0g(actor, group, mode int, ts)`: يحدّث الوضع المخزَّن ويُدرج رسالة نظام |
| رسالة النظام | "turned on / off recent history sharing for new members" بست صيغ (الفاعل `%s`، "Recent history sharing was ..."، "You ...")، لكل منها "Tap to change" أو "Tap to learn more" |
| History sync | يعيد `GroupShareGroupHistoryModeHistorySync` إنشاء رسالة النظام للأجهزة المرافقة؛ ويفعل `GroupChangeHistoryEnabledHistorySync` الشيء نفسه لـ `history_enabled` |
| DB | `wa_group_admin_settings`: `share_group_history_setting_mode`، `group_history_toggle_mode`، `history_enabled`، `earliest_group_history_message_timestamp_ms` |

معنى `group_history_toggle_mode` (int، منفصل عن وضع المشاركة) غير محلول؛ يُقرأ العمود للمجموعات التي تكون قيمته فيها غير صفرية و`group_state = 0`. نصوص الواجهة: "Admins can choose if members are allowed to send message history"، "Admins control if history is sent"، "When adding someone to the group, members have the choice to send up to 100 recent messages".

---

## 3. الأهلية

### 3.1 المرسِل (`A1W.A03`، found)

| # | الشرط | وإلا |
|---|-----------|------|
| 1 | kill switch **35987** مفعّل (متطلبات المرسِل المسبقة) | `PREREQUISITES_DISABLED` |
| 2 | نوع JID للمجموعة 1 أو 2 | `GROUP_TYPE_NOT_ELIGIBLE` |
| 3 | صف جهة اتصال المجموعة موجود | `GROUP_NOT_FOUND` |
| 4 | أنا في المجموعة، وإما أنا admin / superadmin، أو (`require_membership_approval` = false و`member_add_mode` = 1 ووضع المشاركة = 2) | `SENDER_NOT_ELIGIBLE` (يسرد السجل القيم الثلاث) |
| 5 | توجد رسالة قابلة للمشاركة على الأقل (عدّ `A0G.A00` > 0) | `NO_SHAREABLE_MESSAGES` (ويصحح أيضًا أبكر طابع زمني مخزَّن، `A0A`) |
| 6 | بوابة نقطة الدخول `A1W.A02` (3.3) | `EXPERIMENT_DISABLED` |

إذن لا يستطيع العضو العادي الإرسال إلا في المجموعات التي يجوز لأي أحد فيها إضافة أعضاء، ولا تلزم فيها موافقة، وفعّل المشرف `all_member_share`.

### 3.2 المستقبِل (لكل مستخدم مُضاف، found)

| الفحص | رمز النتيجة |
|-------|-------------|
| المستقبِل ليس bot (`AbstractC24760wu.A03`) | `RECEIVER_NOT_ELIGIBLE` |
| جهة اتصال المستقبِل ليست "no longer active" (`externalUserState`، `A07`) | `RECEIVER_INACTIVE` |
| صف المشارك موجود لـ (المجموعة، المستخدم) | `NOT_IN_GROUP` |
| `now - join_time` أقل من flag **30333** (الوحدة غير محلولة) و`group_history_send_state` فارغ أو 1 | `NOT_NEW_OR_ALREADY_SENT` |

`group_history_send_state` (عمود في `group_participant_user`، يكتبه `C14850fN.A0R`): 1 = لا يزال مؤهلًا، 2 = أُرسل بالفعل (found من فرع "already sent" ومسار الإلغاء الذي يعيد 2 إلى 1). ربط سمة الشبكة `group_history_sent` بالحالة مستنتج.

### 3.3 البوابات (`C230099x1`، `A1W.A02`)

كل بوابة هي `global flag OR per-group exposure` (`C41861nA.A04(group, id)`):

| المساعد | عام | معرّف لكل مجموعة | الاستخدام |
|--------|--------|----------------|-----|
| `A01` | **26451** | 30905 | نقطة الدخول `AFTER_JOIN` |
| `A02` | **15313** | 23245 | إرسال السجل أثناء الإضافة (`A1W.A0B`)، ويتحكم أيضًا في `onGroupParticipantsAdded` |
| `A03` | **29973** | 30906 | المستدعون لم يُتتبعوا |

نقاط الدخول (`C9SA`): `AFTER_JOIN`، `FROM_MENTION`، `FROM_CONTACT_MESSAGE`. ترتبط `FROM_MENTION` و`FROM_CONTACT_MESSAGE` إضافةً بـ kill switches ‏**35554** / **35555** وبالبوابة `A02`. قطبية الفحص المركّب غير محلولة (تدفق فك التجميع مشوّش حول `A1W.A09`).

---

## 4. مسار الانضمام (جهة المرسِل)

### 4.1 نقاط دخول الواجهة (found)

| نقطة الدخول | الصنف | ما يحدث |
|-------|-------|--------------|
| منتقي إضافة الأعضاء | `VoipParticipantPickerFragment` + `GroupHistoryAddMembersSettingFooterView` | تذييل "Send message history to approved members" مع مفتاح ورابط "recent messages"؛ الضغط يفتح حوار الكمية؛ حالة المفتاح تُحفظ (`is_group_history_toggled`) |
| شاشة الموافقة على العضوية | `GroupMembershipApprovalRequestsFragment` (`C24002AWf`) | حوار الكمية نفسه قبل الموافقة |
| ورقة ما بعد الانضمام | `GroupHistoryAfterJoinSendBottomSheetFragment` | "Send message history to %1$s?" (اسم أو اسمان) |
| إشارة / جهة اتصال مشاركة | نقطتا الدخول `FROM_MENTION`، `FROM_CONTACT_MESSAGE` | أسماء فقط؛ السلوك لم يُتتبع |

نص التأكيد عند أول استخدام: "Group history messages are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them." (العداد `group_history_confirmation_dialog_confirmed_times`).

### 4.2 خيارات الكمية (`C229129vL.A00(n)`، found)

`n` = العدد من `A0G.A00` (الرسائل التي تقع ضمن الحدود في 5.1).

| n | الخيارات |
|---|---------|
| 0 | لا شيء ("No message history to view") |
| 1..25 | خيار واحد، `n`، موسوم "all" ("Last %d (all)") |
| > 25 | `k = min(4, ceil(n/25))`، `step = max(25, n/k)`؛ الخيارات `step`، `2*step`، ... حتى `k-1` خطوة، ثم `n` (موسوم "all" عند شرط حجم في الخطوة الأخيرة؛ المقارنة الدقيقة غير محلولة) |

ثم تُعكس القائمة بواسطة `C0CG.A0Z` (مستنتج: الأكبر أولًا)؛ يُحدَّد الإدخال الأول مسبقًا. يظهر دائمًا تنبيه الرسائل المثبتة ("All available pinned messages will be included").

### 4.3 IQ الإضافة وربط الأحداث (found)

```xml
<iq xmlns="w:g2" type="set" to="GROUP@g.us" id="…">
  <add>                                       <!-- optional transparency_acknowledged="true" -->
    <participant jid="USER"><privacy>bytes</privacy></participant>   <!-- privacy child optional -->
  </add>
</iq>
```

Found بقراءة الباني (`C11410Yt`): لا تُضاف أي سمة خاصة بالسجل إلى طلب الإضافة؛ قرار السجل محلي بالكامل. الأحداث التي تحرّر المهمة المعلّقة (`C197318aR`، المهلة 32 ث للـ IQ نفسه):

| الحدث | المعالج | الأثر |
|-------|---------|--------|
| طُلب السجل | `CCP(params, group, requestId, receivers, nonReceivers, approvedByMe)` | حفظ `PendingSendGroupHistoryJob`؛ تذكّر العدد المختار في `A08[requestId]`؛ ضبط `group_history_usage_activated` |
| أُجيب IQ الإضافة | `BfO(C222169gu)` | تخزين خريطة النتائج لكل طلب |
| أُضيف المشاركون (إشعار) | `BvD` (فقط عند البوابة `A02`) | الإضافة إلى مجموعتي "added by me" / "added by others" |
| أُجيبت الموافقة على العضوية | `C05(group, user, requestId, approved)` | تخزين المستخدم الموافَق عليه (أو فارغ) |

### 4.4 المهمة المعلّقة (`PendingSendGroupHistoryJob`، found)

الحقول: `permanentGroupRawJid`، `requestId`، `messageCount`، `lastMessageSortId`، `groupHistoryReceiverRawJids`، `groupHistoryNonReceiverRawJids`، `approvedByMeRawJids`، `jobScheduledServerTimeInMillis`، `expirationTimeInMins`. معرّف المهمة الدائم `group-pending-send-group-history`، المتطلب `SendGroupHistoryJobRequirement` (يجب أن تُحلَّل كل JIDs المستقبِلين وإلا `invalid group history receiver jid`).

| الخطوة | التفاصيل |
|------|--------|
| يتحقق المتطلب عندما | انتهت صلاحية المهمة؛ أو وصلت نتيجة الإضافة / الموافقة لـ `requestId`؛ أو يكون مستقبِل في مجموعة "added by others" وغير موافَق عليه مني؛ أو أصبح مستقبِل مشاركًا الآن (`A0r`) |
| انتهاء الصلاحية | `scheduled + flag 19034` دقيقة؛ المهمة المنتهية: إلغاء، إعادة حالة المشارك من 2 إلى 1 |
| التشغيل | تقسيم المستقبِلين إلى منضمّين وبقية؛ البقية تدخل في مهمة معلّقة **جديدة** (نفس معرّف الطلب، مع ترشيح غير المستقبِلين)؛ المنضمّون يحصلون على الحزمة (`C9mW.A00`) |
| مستقبِلو bot | مستقبِل bot من نوع TEE (`AbstractC197238aI.A00`) يعالجه ختم مشاركة سجل منفصل (`A04`، 5.5) |
| حارس التكرار | خريطة `C197318aR.A09` من (المجموعة، المستخدم) إلى وقت الإرسال؛ تُقلَّم الإدخالات الأقدم من `19034` دقيقة (حد أدنى 5) |

---

## 5. الاختيار والحدود والتعبئة

### 5.1 اختيار الصفوف (`A0G`، `AbstractC494421h.A00`، found)

```sql
SELECT … FROM available_message_view [ / with association join when 24033 ]
WHERE timestamp >= (scheduledTimeMs - flag18406 s)
  AND chat_row_id = ? AND sort_id <= ?                 -- anchor = last message at scheduling time
  AND view_mode IS NOT 1 AND view_mode IS NOT 3
  AND message_type IN (shareable types)                -- from the type registry, BUv()
  AND (association_type IS NULL OR association_type IN (supported))   -- only when 24033
  AND (from_me = 0 OR status NOT IN (-1,0,1,2,7,20,21,22))
  AND (expire_timestamp IS NULL OR expire_timestamp >= now OR keep_in_chat = 1)
ORDER BY sort_id DESC LIMIT n
```

| المعامل | المصدر |
|-----------|--------|
| `n` | استعلام العدّ يستخدم flag **18405** كـ LIMIT؛ استعلام الإرسال يستخدم العدد الذي اختاره المستخدم |
| النافذة | flag **18406** (ثوانٍ) قبل وقت الجدولة؛ نص الواجهة يعد بـ "up to 100" رسالة |
| الأنواع القابلة للمشاركة | سجل لكل نوع FMessage (`C222979iT.A00`، `C1ZP.BUv()` صحيح)، مع تجاوز لكل رسالة (`C30039D5b`)؛ غير مسرودة هنا |
| الرسائل الخاصة | فقط التي غادرت الجهاز (`status` ليس ضمن مجموعة المعلّق / الفاشل `AbstractC494421h.A00`) |
| المؤقتة | تُتخطى المنتهية غير المحفوظة |

إذا عُرف sort id لما بعد الانضمام (`C14650f0.A05`)، يرتكز العدّ عليه ("post-join query")؛ وإلا يرتكز على أحدث رسالة ("pre-join query").

### 5.2 القوائم في الحزمة (found، `C9mW.A00`)

| القائمة | المحتوى | الحد |
|------|---------|-------|
| `messages` | الصفوف المختارة (القابلة للمشاركة فقط) | `n` |
| `uncountedAssociatedMessageLists` | أبناء مرتبطون بأم مختارة (عناصر ألبوم، استطلاعات، ...)، مجمّعون بـ `(parent key, association type)`؛ فقط عند **24033** | لا تُحتسب في `messageCount` |
| `commentMessages` | تعليقات على الرسائل المختارة (`C14780fG.A02(list, flag 6050, …)`) | flag **6050** (مستنتج أنه السقف) |
| `outOfWindowPinnedMessages` | رسائل مثبتة أقدم من أقدم رسالة مختارة؛ غير وسائط فقط؛ مرشّحة بمجموعة القابل للمشاركة | كل المتاح (نص التنبيه)؛ سقف المستقبِل flag **19811** (مستنتج) |

أنواع الربط (`C13O`، 21 قيمة): `FUTURE` 0 (وهو أيضًا الاحتياطي)، `MEDIA_ALBUM` 1، `BOT_PLUGIN` 2، `EVENT_COVER_IMAGE` 3، `HD_VIDEO_DUAL_UPLOAD` 5، `STATUS_EXTERNAL_RESHARE` 6، `MEDIA_POLL` 7، `POLL_ADD_OPTION` 20، `STREAMED_HD_VIDEO_DUAL_UPLOAD` 22 وأنواع أخرى للحالة / الملصقات / الرفع المزدوج.

### 5.3 التعبئة (found)

1. يُسلسَل بروتو `GroupHistory` (6.1) إلى ملف بامتداد `proto` (`File … A0Z(C15530gU.A0F, "proto")`)؛ لم تُعثر على خطوة ضغط.
2. تُنشأ FMessage جديدة من النوع 117 في دردشة المجموعة والملف وسائطها (`mimetype application/protobuf`) وتُسلَّم إلى مسار إرسال رسائل الوسائط العادي (الرفع والتشفير، القسم 7).
3. الحقول المحلية على FMessage: عدد الرسائل، أقدم طابع زمني في النافذة (ثوانٍ)، أقدم طابع زمني إجمالًا (الأدنى مع الرسائل المثبتة)، المستقبِلون، غير المستقبِلين، أحجام قوائم الرسائل المعبأة، حجم الملف، وقت البناء (قياس عن بعد).
4. إذا كان **24741** مفعّلًا وليس للرسالة سر، يُولَّد سر رسالة جديد لها، ثم تُحسب رموز الإبلاغ لكل رسالة أصلية (القسم 9).

### 5.4 الإشعار بعد الإرسال (found، `ANQ.C0M`)

عندما تبلغ الحزمة الحالة **1** (أو **24** عند تفعيل flag **28787**) ولم يُرسل الإشعار بعد (`A00 != 1`)، ينشئ الجهاز إشعارًا من النوع 118 في المجموعة نفسها بأعداد الحزمة وأطرها الزمنية ومستقبِليها ويرسله (`C33166Ecf.A06`). يستلمه كل أعضاء المجموعة؛ والمسمّون في `historyReceivers` يعلّمونه إضافةً (`AbstractC30028D4q.A1B`).

### 5.5 مشاركة سجل bot من نوع TEE (found، موجز)

لمستقبِل bot، يختم `C9mW.A01` الرسائل المختارة التي تحمل سر رسالة بإثبات (`AbstractC33322EfC.A02(sender, botJid, "TEE History Share", stanzaId, secret)`) ويرسل إشعارًا تسرد `botHistoryShareSyncMetadata` فيه `(stanzaId, messageSecretProof)`. انظر تقرير Meta AI لسياق bot: [WA_META_AI.md](./WA_META_AI.md). مسار bot لا يرفع حزمة.

---

## 6. صيغة الشبكة

### 6.1 الملف الداخلي: `GroupHistory` (`DSN`)

| الحقل | الرقم | النوع | المحتوى |
|-------|--------|------|---------|
| `messages` | **1** | repeated `WebMessageInfo` (`C30626DTu`) | الرسائل المعدودة |
| `uncountedAssociatedMessageLists` | **2** | repeated `UncountedAssociatedMessageList` (`C30578DRy`) | `messages` **1** (repeated WebMessageInfo)، `parentMessage` **2** (`MessageKey`، `BD5`)، `associationType` **3** (enum `C13O`) |
| `commentMessages` | **3** | repeated `WebMessageInfo` | التعليقات |
| `outOfWindowPinnedMessages` | **4** | repeated `WebMessageInfo` | المثبتات |

يحلل المستقبِل البايتات نفسها مرة ثانية على أنها `GroupHistoryWithMessageBytes` (`C30576DRw`: أرقام الحقول الأربعة نفسها؛ الإدخالات `C30543DQp` مع `key` **1** (`MessageKey`) و`message` **2** (bytes)؛ قوائم الربط `DPH` تقرأ `messages` **1** فقط). تحتفظ هذه الصيغة بالبايتات المسلسلة الأصلية لكل رسالة (تُستخدم للتحقق من رمز الإبلاغ ومعالجة السر، مستنتج).

### 6.2 الرسالة الخارجية: `Message.messageHistoryBundle` (`DT6`، الحقل **70**)

| الحقل | الرقم | النوع | القيمة / الاستخدام |
|-------|--------|------|-------------|
| `mimetype` | **1** | string | يجب أن يساوي `application/protobuf` |
| `fileSha256` | **2** | bytes | 32 بايت، hash النص الواضح |
| `mediaKey` | **3** | bytes | مفتاح الوسائط |
| `fileEncSha256` | **4** | bytes | 32 بايت، hash النص المشفّر |
| `directPath` | **5** | string | مسار الرفع؛ الفارغ يُسجَّل ولا يُعد قاتلًا وقت التحليل |
| `mediaKeyTimestamp` | **6** | int64 | ثوانٍ |
| `contextInfo` | **7** | `ContextInfo` | قياسي |
| `messageHistoryMetadata` | **8** | `MessageHistoryMetadata` (`C30583DSd`) | أدناه |

`MessageHistoryMetadata`:

| الحقل | الرقم | النوع | القاعدة عند الاستلام |
|-------|--------|------|-----------------|
| `historyReceivers` | **1** | repeated string | واحد على الأقل؛ ويجب أن يكون المستخدم الحالي مدرجًا |
| `oldestMessageTimestampInWindow` | **2** | int64 | موجود و> 0 |
| `messageCount` | **3** | int64 | موجود و> 0 |
| `nonHistoryReceivers` | **4** | repeated string | اختياري |
| `oldestMessageTimestampInBundle` | **5** | int64 | اختياري (يشمل المثبتات) |

### 6.3 الإشعار: `Message.messageHistoryNotice` (`DRY`، الحقل **102**)

`contextInfo` **1**، `messageHistoryMetadata` **2** (النوع نفسه، مطلوب مع قواعد المستقبِلين والطابع الزمني والعدد)، `botHistoryShareSyncMetadata` **3** (`C25765B9z`: `botJid` **1**، `historyShareMessages` **3** repeated `BA2` = `stanzaId` **1**، `messageSecretProof` **2**). لا يحتوي التخطيط lite على الحقل **2** في `C25765B9z`؛ ويوجد قطع (cutoff) كحالة محلية فقط (`C213519Ap.A03`).

### 6.4 مستوى الـ stanza (found)

| البند | الحزمة (117) | الإشعار (118) |
|------|--------------|--------------|
| `type` للـ stanza | `media` | غير خاص بالوسائط |
| نوع وسائط `<enc>` | `group_history` (`C30106D7q`؛ ضمن مجموعة أنواع وسائط enc المسموحة `C9E2` / `C33474Ehg`) | لا شيء |
| `<meta appdata="…">` | **غير مضبوط** (`C213539Ar` لا ينفّذ `FZF`) | `group_history` (`C213519Ap.AVN`؛ يكتبه `F6K`) |
| فحص المستقبِل | `A0O == "media"` و`A0J == "group_history"` وإلا الخطأ 11 | `appdata == group_history` وإلا الخطأ 76 |
| `<reporting>` | اختياري، القسم 9 | لا شيء |

يُتخطى الفحصان عند ضبط أعلام الغلاف `A0V` / `A0U` (المعنى غير محلول). الحزمة التي تصل بنوع وسائط `group_history` دون رسالة مطابقة، وappdata الإشعار على نوع غريب، يرفضهما `GroupHistoryBundleDeserializationValidator` / `GroupHistoryNoticeDeserializationValidator` (`F3b` / `F3c`).

### 6.5 علامات `WebMessageInfo` (`C30626DTu`، found)

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `isGroupHistoryMessage` | **57** | bool | استُوردت الرسالة من حزمة |
| `reportingTokenInfo` | **62** | message | وسم الإبلاغ (انظر تقرير Reporting) |
| `groupHistoryIndividualMessageInfo` | **74** | `C30549DQv` | `bundleMessageKey` **1** (`MessageKey`)، `editedAfterReceivedAsHistory` **2** (bool) |
| `groupHistoryBundleInfo` | **75** | `C30548DQu` | `deprecatedMessageHistoryBundle` **1**، `processState` **2** (enum `EnumC32128E2a`) |

`processState`: `NOT_INJECTED` 0، `INJECTED` 1، `INJECTED_PARTIAL` 2، `INJECTION_FAILED` 3، `INJECTION_FAILED_NO_RETRY` 4، `DEDUPED` 5.

---

## 7. التشفير والوسائط

| الطبقة | Found |
|-------|-------|
| نقل الرسالة | توزيع مجموعة عادي: تُشفَّر رسالة 117 كأي رسالة مجموعة (`skmsg` بـ sender-key لكل مجموعة مع توزيع sender-key المعتاد على الأجهزة). الأساسيات لا تُكرَّر هنا؛ صيغة `<enc>` في الـ stanza موجودة في [WA_CALL_SIGNALING.md](./WA_CALL_SIGNALING.md) في القسم الخاص بـ `<enc>`. حالة sender-key لكل جهاز تعيش في `group_participant_device` (`sent_sender_key`، `sent_add_on_sender_key`، `sent_sender_key_bucket`) |
| صف الوسائط | `C15530gU.A0F`: نوع الرفع `group-history`، نوع الملف `GROUP_HISTORY`، HKDF info ‏`Group History`، المعرّف 117 |
| المفتاح / الشفرة | مفتاح وسائط عشوائي، HKDF-SHA256 مع info ‏`Group History`، AES-256-CBC، HMAC-SHA256 مقتطع إلى 10 بايتات يُلحق، و`fileSha256` / `fileEncSha256` في البروتو: المخطط العام في [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) القسم 6 (توسيع 80 بايت على Android)؛ يُطبَّق على هذا النوع عبر مسار الإرسال المشترك (مستنتج، قُرئ صف النوع فقط) |
| عنوان الرفع | `https://<host>/mms/group-history/<hash>?…`؛ تركيب `mms/<upload type>` found للجدول (القسم 4 من تقرير الوسائط)؛ المسار الحرفي لهذا النوع لم يُلتقط (مستنتج) |
| التنزيل | تنزيل وسائط قياسي باستخدام `mediaKey` و`directPath` والـ hashes؛ نص الفشل `GroupHistoryBundleProcessor/download failed for … with reason …` |
| إعادة استخدام المفتاح | مفتاح وسائط الحزمة مستقل عن مفاتيح الرسائل المحتواة |

يعمل المستقبِل دائمًا من `mediaKey` الخاص بالبروتو؛ وتُرفض الحزمة التي لا تكون hashes فيها 32 بايتًا (`bogus sha-256 hash received`، الخطأ 14).

---

## 8. المستقبِل: التحقق والاستيراد

### 8.1 فحوص وقت التحليل (`C34677F2y.CM7`، found)

| الفحص | الخطأ |
|-------|-------|
| JID الدردشة مجموعة (`A0l`) | 11 `chatJid is not a group` |
| الغلاف `media` + نوع وسائط enc ‏`group_history` | 11 |
| `mimetype == application/protobuf` | 11 |
| وجود `fileSha256`، `mediaKey`، `fileEncSha256`، `mediaKeyTimestamp`، والبيانات الوصفية | 11 |
| `historyReceivers` غير فارغ، الطابع الزمني للنافذة > 0، العدد > 0 | 11 |
| المستخدم الحالي في `historyReceivers` (ليس للرسائل الخاصة) | 11 `current user is not in history receivers list` |
| البوابة **15311** مغلقة | FMessage بديلة `C35281aa` بالرمز **82** ("Update to the latest version of WhatsApp to see it") |
| أطوال الـ hash 32 | 14 |

الإشعار (`C34678F2z`): دردشة مجموعة، appdata، بيانات وصفية بمستقبِلين / طابع زمني / عدد؛ البوابة **15722** المغلقة تعطي البديل بالرمز **10008**.

### 8.2 المعالجة (`GroupHistoryBundleProcessor`، found ما لم يُذكر خلاف ذلك)

1. المشغّل: إضافة رسالة (`C0G`) ومرة أخرى عند حالة الوسائط 3 (`C0M`). المرشَّحة هي دردشة مجموعة (النوع 1)، ليست مني، الحالة 0 أو 5، وأنا في قائمة المستقبِلين، وأحدث من flag **25910** (الوحدة غير محلولة؛ وإلا "Message history expired").
2. إزالة التكرار (flag **30462**): إذا عولجت حزمة بالفعل لجلسة الانضمام نفسها تُعلَّم الجديدة كمكررة (`deduped_bundle_for_join_session`)، الواجهة: "%1$s also sent you message history, which you already got from someone else".
3. تنزيل الوسائط؛ الفشل يعرض "Couldn't download message history from %1$s".
4. تحليل الملف مرتين (`DSN`، `DRw`)؛ فشل التحليل: `protobuf_parse_failed`.
5. إيجاد المرساة: أحدث رسالة انضمام إلى المجموعة ("failed to find latest group join message, adding messages before the first message in chat" عند عدم وجودها)؛ مرساة قديمة جدًا: `anchor_message_too_old`.
6. التحقق من كل رسالة وإدراجها (8.3)؛ ربط كل صف مُدرج بالحزمة (`group_history_bundle_association`: `bundle_message_key_id`، `message_row_id`، `message_sort_id`)؛ تعليم `isGroupHistoryMessage`.
7. المثبتات خارج النافذة: السقف (flag **19811**، مستنتج)، وتطبيق حالة التثبيت المشتركة (`applySharedPin`).
8. تطبيق أختام مشاركة سجل bot المعلّقة (`BotHistoryShareHelper`)، ثم القياس عن بعد (`group_history_receiver_user_journey`).

تُوضع الصفوف المستوردة قبل مرساة الانضمام، فتظهر فوق سطر "you were added" (مستنتج من منطق المرساة).

### 8.3 التحقق لكل رسالة (`C33241Eds`، `C34360Ew7`، `C34361Ew8`، `C33413Egg`، found)

| سبب التخطي | السبب |
|-------------|-------|
| `invalid_jid` | `key.remoteJid` يختلف عن دردشة الحزمة |
| `non_hex_id` | `key.id` ليس hex فقط |
| `timestamp_too_old` | `messageTimestamp` ليس أحدث من الحد الأدنى المسموح (حقول السجل `msgTs`، `allowedTs`، `diff`؛ الحد مشتق من حالة محلية، الصيغة غير محلولة) |
| `parse_failed`، `pin_not_parsed` | لم يُحلَّل بروتو الإدخال |
| `not_shareable` | نوع الرسالة غير مسموح للاستيراد |
| `no_local_copy` | تثبيت مشترك تُخطيت رسالته وهي ليست محلية |
| `max_limit_reached` | بلوغ السقف |
| `timestamp_after_anchor` | رسالة أحدث من مرساة الانضمام |
| `already_exists`، `duplicate`، `expired` | موجودة محليًا، مكررة في الملف، مؤقتة منتهية وغير محفوظة |
| `orphan_parent_not_in_bundle`، `invalid_comment` | تعليق / ابن ربط بلا أمه في الملف |
| `insert_exception`، `anchor_messages_failed`، `insert_messages_exception` | أخطاء DB محلية |

إضافةً: تحتاج الرسالة إلى حفظ `messageSecret` الخاص بها (سجلات `messageSecretLost`، `noMessageSecret`)؛ والنسخة المحلية تفوز عندما توجد رسالة بمحتوى مختلف (`keeping local …`).

الجداول المتأثرة (found): `group_history_bundle_association` (`bundle_message_key_id`، `message_row_id`، `message_sort_id`)، `group_history_share_reporting_info` (`stanza_id`، `reporting_tag`، `send_timestamp`، `added_timestamp`، `reporting_token`، `reporting_token_version`، `is_send`، `validation_policy`)، `group_participant_user.group_history_send_state`، `wa_group_admin_settings` (2.4).

---

## 9. رموز الإبلاغ (موجز)

قسم الـ stanza للحزمة عند تفعيل **24741** (`F6C`، `GhsReportingTokenMessageSendStanzaContributor`):

```xml
<reporting>
  <message id="ORIGINAL_STANZA_ID"><reporting_token v="N">16 bytes</reporting_token></message>
  …
</reporting>
```

اشتقاق الرمز وتخزينه في [WA_REPORTING.md](./WA_REPORTING.md) (القسم 6.2)؛ جزء من اشتقاق المفتاح يعمل في شيفرة native، فلا يمكن إعادة إنتاج البايتات الدقيقة من Java وحدها. عند الاستلام، وعند تفعيل **5718** و**24742**، يؤدي غياب رمز لرسالة مستوردة إلى قياس عن بعد `GROUP_HISTORY_MESSAGE_MISSING_FROM_PUBLIC_STANZA` (ومعه **13063** صف تشخيص داخلي)؛ وتُدرج الرسالة مع ذلك في هذا المسار (مستنتج من تدفق التحكم). هل يشترط الخادم الرموز: unknown.

---

## 10. HistorySync للأجهزة المرافقة (ذو صلة، وليس سجل مجموعة)

أساسيات الاقتران وapp-state في [WA_LINKED_DEVICE_PAIRING.md](./WA_LINKED_DEVICE_PAIRING.md) و[WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md). فقط ما يخص بيانات المجموعة:

### 10.1 `HistorySyncConfig` (`C44601rs`، يعلنه الجهاز المرافق؛ أرقام الحقول من تخطيط lite)

| الحقل | # | قيمة الجهاز المرافق (found) |
|-------|---|-------------------------|
| `fullSyncDaysLimit`، `fullSyncSizeMbLimit` | 1, 2 | flags ‏**15284**، **15283** |
| `storageQuotaMb`، `initialSyncMaxMessagesPerChat` | 3, 20 | غير مضبوط في الفرع المتتبَّع |
| `recentSyncDaysLimit` | 5 | 0 |
| `supportMessageAssociation`، `supportHostedGroupMsg`، `supportAddOnHistorySyncMigration` | 14, 11, 13 | true |
| `supportGroupHistory` | 15 | flag **20658** |
| `onDemandReady` / `completeOnDemandReady` | 16 / 18 | `!` flag **18953** / false |
| `thumbnailSyncDaysLimit` | 19 | flag **21217** |
| `supportHatchHistory` / قائمة قنوات bot | 22 / 23 | flag **26445** / فرع على **26614** |
| سجل المكالمات، سجل bot وCAG، `supportNewsletter`، `supportInlineContacts`، ... | 4, 6-8, 12, 24-27 | true (الباقي false) |

الحقول المتبقية (`supportBizHostedMsg` 9، `supportRecentSyncChunkMessageCountTuning` 10، `supportGuestChat` 17، `supportManusHistory` 21، `supportUniversalReachChat` 26، `supportOmittedConversationIndex` 27) لا تُفصَّل هنا.

### 10.2 أنواع المزامنة والرسائل

| الرسالة | الحقل | المحتوى |
|---------|-------|---------|
| `HistorySync` (`C25838BCy`) | `syncType` **1**، `conversations` **2**، `statusV3Messages` **3**، `chunkOrder` **5**، `progress` **6**، `pushnames` **7**، `globalSettings` **8**، `threadIdUserSecret` **9**، `threadDsTimeframeOffset` **10**، `recentStickers` **11**، `pastParticipants` **12**، `callLogRecords` **13**، `aiWaitListState` **14**، `phoneNumberToLidMappings` **15**، `companionMetaNonce` **16**، `shareableChatIdentifierEncryptionKey` **17**، `accounts` **18**، `nctSalt` **19**، `inlineContacts` **20/21**، `omittedConversations` **23/24** | محادثات المجموعات تسافر في `conversations`؛ و`pastParticipants` (**12**) يسرد أعضاء المجموعة السابقين |
| `HistorySyncNotification` (`C25834BCt`) | `fileSha256` **1**، `fileLength` **2**، `mediaKey` **3**، `fileEncSha256` **4**، `directPath` **5**، `syncType` **6**، `chunkOrder` **7**، `originalMessageId` **8**، `progress` **9**، `oldestMsgInChunkTimestampSec` **10**، `initialHistBootstrapInlinePayload` **11**، `peerDataRequestSessionId` **12**، `fullHistorySyncOnDemandRequestMetadata` **13**، `encHandle` **14**، `messageAccessStatus` **15** | جزء مُحال بالوسائط؛ الحمولة هي `HistorySync` |

أنواع المزامنة: `INITIAL_BOOTSTRAP` 0، `INITIAL_STATUS_V3` 1، `FULL` 2، `RECENT` 3، `PUSH_NAME` 4، `NON_BLOCKING_DATA` 5، `ON_DEMAND` 6، وفي enum ذي 9 قيم (`EnumC26456Bdr`) أيضًا `NO_HISTORY` 7 و`MESSAGE_ACCESS_STATUS` 8 (`EnumC26449Bdk` هو الصيغة ذات 7 قيم).

### 10.3 عمليات بيانات peer عند الطلب (`EnumC26460Bdv`، found)

| العملية | المعرّف | حقل الطلب (`C25823BCh`) | حقل الاستجابة (`C25828BCm`) |
|-----------|----|-----------------------------|------------------------------|
| `HISTORY_SYNC_ON_DEMAND` | 3 | `historySyncOnDemandRequest` **4** (`BCR`: `chatJid` **1**، `oldestMsgId` **2**، `oldestMsgFromMe` **3**، `onDemandMsgCount` **4**، `oldestMsgTimestampMs` **5**، `accountLid` **6**، `supportInlineResponse` **7**) | غير معرّف؛ يصل السجل كـ `HistorySyncNotification` (مستنتج) |
| `FULL_HISTORY_SYNC_ON_DEMAND` | 6 | `fullHistorySyncOnDemandRequest` **6** (`BBB`: `requestMetadata` **1** `BBA`، `historySyncConfig` **2**، `fullHistorySyncOnDemandConfig` **3** `C156516k5`: `historyFromTimestamp` **1**، `historyDurationDays` **2**) | `fullHistorySyncOnDemandRequestResponse` **6** |
| `PLACEHOLDER_MESSAGE_RESEND` | 4 | **5** | **4** |
| `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` | 8 | **7** | **8** |

يحتفظ الجهاز الأساسي بصف لكل مزامنة في `msg_history_sync` (`device_id`، `sync_type`، `last_processed_msg_row_id`، `oldest_msg_row_id`، `sent_msgs_count`، `chunk_order`، `sent_bytes`، `last_chunk_timestamp`، `status`، `peer_msg_row_id`، `oldest_message_to_sync_row_id`، `session_id`، `size_limit_bytes`، `full_history_on_demand_request_id`، …). حدود الخادم على حجم الجزء وأعداد الرسائل غير ظاهرة في شيفرة العميل المقروءة هنا (unknown). لا توجد عملية عند الطلب خاصة بسجل مشترك لمجموعة.

### 10.4 سجل المجموعة على الأجهزة المرافقة

| البند | Found |
|------|-------|
| القدرة | `supportGroupHistory` (flag **20658**) في `companion-props`؛ تُخزَّن على الجهاز الأساسي كـ `support_group_history` (تقرير الاقتران، القسم 6.2)؛ المستهلك لم يُتتبع |
| تسليم الحزمة | الحزمة رسالة مجموعة عادية، فيستلمها كل جهاز لدى المستقبِل؛ سلاسل الأجهزة المرتبطة ("Open WhatsApp on your phone and visit this group to see it") توحي ببديل هناك (مستنتج) |
| بناء مزامنة الجهاز الأساسي | يحمل `BuildHistorySyncParams` (`C33151EcQ`) القيم `supportGroupHistory`، `pullGroupHistoryUncountedChildren`، `maxCommentsToAdd`، `supportMessageAssociation`؛ المستهلكون لم يُتتبعوا |
| رسائل النظام | تُعاد بناء تغييرات وضع المشاركة، وhistory-enabled، وإضافة الأعضاء / الرابط / وضع الموافقة للأجهزة المرافقة بواسطة أصناف `Group*HistorySync` |

---

## 11. Feature flags والحدود

معرّفات flags بالخط العريض؛ القيم يوفرها الخادم، والقيم الافتراضية المترجمة لم تُحل (نص الواجهة يقول "up to 100" رسالة).

| Flag | النوع | يتحكم في | المستوى |
|------|------|----------|------|
| **35987** | bool | kill switch لمتطلبات المرسِل المسبقة | found |
| **15313** / 23245 | bool / مجموعة | البوابة `A02`، إرسال السجل أثناء الإضافة | found |
| **26451** / 30905 | bool / مجموعة | البوابة `A01`، نقطة الدخول `AFTER_JOIN` | found |
| **29973** / 30906 | bool / مجموعة | البوابة `A03` | found (الاستخدام unknown) |
| **35554**، **35555** | bool | `FROM_MENTION`، `FROM_CONTACT_MESSAGE` | القطبية inferred |
| **18405** | int | LIMIT لاستعلام العدّ (سقف حجم العرض) | found |
| **18406** | int، ث | نافذة الرجوع قبل وقت الجدولة | found |
| **19034** | int، دقيقة | انتهاء المهمة المعلّقة، تقليم التكرار (حد أدنى 5) | found |
| **30333** | long | أقصى وقت منذ الانضمام للمستقبِل | found (الوحدة غير محلولة) |
| **24033** | bool | قوائم الربط ومرشّح الربط | found |
| **6050** | int | سقف جمع التعليقات | inferred |
| **24741** | bool | بناء رموز الإبلاغ عند الإرسال | found |
| **28787** | bool | محفّز الإشعار بالحالة 24 بدل 1 | found |
| **20658** | bool | الجهاز المرافق يعلن `supportGroupHistory` | found |
| **15311** | bool | الاستلام: قبول الحزمة (مغلق: بديل 82) | found |
| **15722** | bool | الاستلام: قبول الإشعار (مغلق: بديل 10008) | found |
| **30462** | bool | الاستلام: إزالة التكرار لكل جلسة انضمام | found |
| **25910** | long | الاستلام: نافذة حداثة الحزمة | found (الوحدة غير محلولة) |
| **19811** | int | الاستلام: سقف المثبتات خارج النافذة | inferred |
| **24034** / **25037** | bool / int | الاستلام: معالجة أبناء الربط ومعاملها int | inferred |
| **26039** | bool | بوابة المُدرج (ثلاثة مواضع) | found (الاستخدام unknown) |
| **5718** + **24742** | bool | الاستلام: التحقق من رمز الإبلاغ | found |
| **13063** | bool | صف تشخيص داخلي عند غياب الرمز | found |

---

## 12. حالات الخطأ

| العَرَض | السبب | الحل |
|---------|-------|-----|
| لا خيار "send history" | المرسِل غير مؤهل (3.1)، أو المجموعة غير متسقة LID / PN، أو لا رسائل قابلة للمشاركة | يفعّل المشرف `all_member_share` ووضع إضافة الأعضاء `all_member_add` وبلا موافقة؛ أو الإرسال كمشرف |
| يعرض المستقبِل "Update to the latest version" | البوابة 15311 / 15722 مغلقة أو نوع غير معروف | لا شيء على العميل |
| رفض الحزمة، الخطأ 11 | MIME خاطئ، نوع غلاف، نوع وسائط، حقل ناقص، أنا لست في `historyReceivers` | البناء وفق القسم 6 |
| رفض الحزمة، الخطأ 14 | hash ليس 32 بايتًا | تصحيح الـ hashes |
| رفض الإشعار، الخطأ 11 / 76 | appdata ليس `group_history` (التحليل، 11)؛ appdata الإشعار على نوع آخر (المدقق، 76) | ضبط `appdata=group_history` على النوع 118 فقط |
| رسائل ناقصة بعد الاستيراد | أسباب التخطي في 8.3 (`timestamp_too_old`، `not_shareable`، `invalid_jid`) | يجب أن تكون المفاتيح معرّفات hex لنفس المجموعة |
| "Couldn't download message history" | فشل تنزيل الوسائط (`directPath` منتهٍ، عدم تطابق المفتاح) | إعادة المحاولة؛ إعادة الإرسال |
| المهمة لا تعمل أبدًا | لم يُرَ حدث الإضافة أو الموافقة، لم يصبح المستقبِلون مشاركين، انتهت صلاحية المهمة (19034) | إعادة الإضافة وإعادة الإرسال |

---

## 13. فروق أساسية

| لا تخلط بين | وبين |
|----------------|------|
| حزمة سجل المجموعة (النوع 117، `application/protobuf`، `group-history`) | إشعار HistorySync للجهاز المرافق (`HistorySyncNotification`، `md-msg-hist`) |
| الحزمة (بيانات، بلا appdata) | الإشعار (أعداد ومستقبِلون، `appdata=group_history`) |
| `member_share_group_history_mode` (من يجوز له الإرسال) | `group_history_toggle_mode` / `history_enabled` (المعنى غير محلول) |
| `historyReceivers` (يحصلون على البيانات) | `nonHistoryReceivers` (أُضيفوا ولا يستلمون) |
| `oldestMessageTimestampInWindow` (**2**) | `oldestMessageTimestampInBundle` (**5**، يشمل المثبتات خارج النافذة) |
| عدد `messages` (`messageCount`) | أبناء الربط والتعليقات غير المعدودة |
| `supportGroupHistory` في `HistorySyncConfig` (قدرة الجهاز) | إعداد المشرف |

---

## 14. Baileys (`baron-baileys-v2` 1.5.17)

فقط الوقائع المقروءة في `src/Utils/group-history.js`، `src/Socket/groups.js`، `src/Socket/messages-recv.js`، `src/Socket/aigroups.js`، `src/Utils/validate-connection.js`، `WAProto/index.js`. لم يُختبر شيء مقابل خادم؛ ولا يُدّعى أي فشل.

| الموضوع | Baileys | Android |
|-------|---------|---------|
| Proto | `GroupHistory`، `GroupHistoryWithMessageBytes`، `GroupHistoryBundleInfo`، `GroupHistoryIndividualMessageInfo`، `Message.messageHistoryBundle`، `messageHistoryNotice`، `HistorySyncConfig.supportGroupHistory` موجودة في `WAProto` | 6 |
| المفكّك | يحاول `decodeGroupHistory` ‏`zlib.inflateSync`، ويرجع إلى البايتات الخام؛ وضع `GroupHistoryWithMessageBytes` اختياري؛ يطبّع `processGroupHistory` القوائم الأربع | لا ضغط على Android؛ يُقرأ protobuf خام |
| استلام الحزمة | لا شيفرة تعالج `messageHistoryBundle` (تنزيل الوسائط، التحقق، الإدراج) | القسم 8 |
| إرسال الحزمة | لا شيء | القسم 5 |
| قدرة الجهاز المرافق | `supportGroupHistory: true` في `HistorySyncConfig` المعلَن | flag 20658 |
| إعداد المجموعة | يُقرأ `member_share_group_history_mode` من بيانات المجموعة الوصفية؛ `groupSetProperty(jid, property, value)` عبر MEX؛ إشعار mex ‏`NotificationGroupMemberShareGroupHistoryModePropertyUpdate` يصدر `groups.update { memberShareHistoryMode }` | 2.4 |
| `aiGroupCreate` | يقبل `memberShareGroupHistoryMode` (الافتراضي `all_member_share`) لكنه لا يضعه في stanza الإنشاء في الشيفرة المقروءة | لا ينطبق |
| سمات المشاركين | `group_history_sent`، `join_time` غير محللة | 2.2 |
| العنونة | يُقرأ `addressing_mode` من عقدة المجموعة، والافتراضي `lid` عند الإرسال | 2.2 |

النتيجة المقصورة على ما قُرئ: عميل Baileys الذي يعلن `supportGroupHistory` لا يستطيع استيراد حزمة مستلمة، لأنه لا يوجد مستهلك في الشيفرة المصدرية. وعلى المرسِل اتباع الأقسام 5 إلى 7 (إرسال بعد الإضافة، نوع `media` مع نوع وسائط enc ‏`group_history`، نوع وسائط `group-history` مع HKDF info ‏`Group History`، إشعار مع appdata)؛ هل يقبل الخادم حزمة بلا رموز `<reporting>`: unknown.

---

## 15. التدفق الكامل

```
[Admin]  switch "Send message history" ─► MEX SetGroupProperty member_share_group_history_mode=ALL_MEMBER_SHARE|ADMIN_SHARE
     │
     ▼
[WA Server]  w:gp2 notification member_share_group_history_mode ─► all members: store mode, system message

[Sender]  add members (picker / approval screen / post-join sheet)
     │   A1W.A09: gate 35987, group type, sender (admin or all_member_share + all_member_add + no approval),
     │            receiver (join age, send_state), shareable messages
     │   A0G.A00 count ─► amount options (<=25 one option, else up to 4)
     ▼
iq set w:g2 <add><participant jid/></add>          (no history attribute)
     │
     ▼
[WA Server]  result ─► BfO / C05 / BvD events ─► PendingSendGroupHistoryJob requirement met
     │
     ▼
[Sender]  A0M: split joined / remaining (remaining re-queued) ─► C9mW.A00
     │   rows: timestamp >= scheduled - 18406 s, sort_id <= anchor, LIMIT n
     │   + association lists (24033) + comments (6050) + out-of-window pins
     │   GroupHistory proto ─► file ─► FMessage 117, mimetype application/protobuf
     ▼
upload  /mms/group-history  (HKDF info "Group History", AES-CBC + HMAC-10)       [WA_MEDIA_UPLOAD]
     │
     ▼
group message  type=media, enc mediatype=group_history, Message.messageHistoryBundle(70)
     │          metadata: receivers, nonReceivers, oldest ts (window / bundle), count
     │          optional <reporting><message id><reporting_token v/></message></reporting> (24741)
     ▼
[Receivers' devices]  C34677F2y checks (group, media, MIME, hashes, me in historyReceivers, gate 15311)
     │   download + decrypt ─► parse DSN / DRw ─► dedupe (30462) ─► anchor = join message
     │   validate each WebMessageInfo (jid, hex id, timestamp, type) ─► insert before anchor
     │   group_history_bundle_association, isGroupHistoryMessage=57
     ▼
[Sender]  bundle status 1 (24 with 28787) ─► notice type 118, appdata group_history, same metadata
     │
     ▼
[All members]  system row "<name> sent message history that starts on <date>"
```

---

## 16. المجهولات

| البند | الحالة |
|------|--------|
| قواعد القبول لدى الخادم، الاحتفاظ، حدود الحجم، اشتراط رمز الإبلاغ | من جهة الخادم، غير مرصودة |
| القيم الافتراضية لـ 18405 و18406 و19034 و25910 و30333 | يوفرها الخادم، الافتراضيات غير محلولة |
| الحد الأدنى الدقيق لـ `timestamp_too_old` ووحدة 25910 / 30333 | غير محلول |
| قطبية `A1W.A02` لكل نقطة دخول؛ استخدام البوابة `A03` وflag 26039 | فك تجميع مشوّش / لم يُتتبع |
| معنى العمود `group_history_toggle_mode` والابن `<group_history/>` | الأسماء found، الدلالات inferred فقط |
| قائمة أنواع الرسائل القابلة للمشاركة (سجل `BUv()`) | غير مسرودة |
| عرض الجهاز المرافق للحزمة؛ مستهلك `support_group_history` على الجهاز الأساسي | لم يُتتبع |
| الجزء native من اشتقاق مفتاح رمز الإبلاغ | native، لم يُقرأ |
| الحركة على الشبكة | لم يُلتقط شيء؛ كل التدفقات من الشيفرة |
