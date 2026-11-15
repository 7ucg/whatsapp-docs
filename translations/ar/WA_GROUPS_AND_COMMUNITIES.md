<!-- src-sha1: 900bf74a45a7fabc6e7b8c42ef4df8074e676084 -->
# WhatsApp المجموعات والمجتمعات — Full RE Report
**الإصدار:** 2.26.41.6 (سطح النقل لموافقة العضوية/الانضمام تم التحقق منه أيضاً على 2.26.45.10، مذكور ضمن النص) | **التاريخ:** 2026-11-15
**النطاق:** النموذج البنيوي للمجموعة مقابل المجتمع (المجموعة الأم، المجموعات الفرعية المرتبطة، المجموعة الفرعية الافتراضية، الدردشة العامة)، عنونة JID، سطح النقل القديم `w:g2`/`w:gp2`، فهرس عمليات GraphQL لمجموعات/مجتمعات `whatsapp-android-mex`، تدفقات الإنشاء/الدعوة/إجراءات الإدارة، روابط الدعوة، وموافقة الانضمام إلى المجتمع (`QueryMembershipApprovalRequests`، `GroupMembershipRequestUpdate`، الحل البديل القديم `w:g2`، وعملية الإرسال المستنتجة `JoinMembershipForm`).

---

## 1. ما هو

**المجتمع (community)** في WhatsApp ليس كياناً قابلاً للعنونة مستقلاً. إنه **مجموعة** — نفس فضاء JID، نفس محلِّل عقدة `<group>`، نفس جدول `wa_group_admin_settings` — يؤدي دور **مجموعة أم (parent group)** لمجموعة من **المجموعات الفرعية المرتبطة**. يجمع هذا التقرير نموذج المجموعة/المجتمع المتناثر أصلاً بين [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2 (التصنيف، العنونة)، [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) (جداول قاعدة البيانات)، [WA_REPORTING.md](WA_REPORTING.md) (سطح الإبلاغ للمشرف `w:g2`) و[WA_POLLS.md](WA_POLLS.md) (نسخة الاستطلاع للمجموعة الفرعية الافتراضية)، ويضيف فهرس عمليات MEX للمجموعة/المجتمع واكتشاف موافقة الانضمام إلى المجتمع في 2.26.45.10.

### 1.1 الكيانات

| الكيان | العنونة | العلاقة | المستوى |
|--------|-----------|----------|------|
| مجموعة | JID خاص بها من نوع `@g.us` | — | found |
| مجتمع | **نفس** فضاء JID من نوع `@g.us` الخاص بالمجموعة؛ مصنَّف، وليس ذا نوع مستقل | مجموعة تؤدي دور الأم | found |
| مجموعة أم | عقدة `<group>` من النوع **1** (وجود عنصر فرعي `parent`) | قمة المجتمع | found |
| مجموعة فرعية مرتبطة | عقدة `<group>` من النوع **2** (عنصر فرعي `linked_parent jid`) | `linked_parent jid` يشير إلى JID الخاص بالأم | found |
| مجموعة فرعية افتراضية | عقدة `<group>` من النوع **3** (عنصر فرعي `default_sub_group`) | مجموعة فرعية تُنشأ تلقائياً ضمن المجتمع؛ `group_type` **3** محلياً، وهي أيضاً المشغِّل لـ `pollCreationMessageV2` (WA_POLLS §1) | found |
| الدردشة العامة | عقدة `<group>` من النوع **6** (عنصر فرعي `general_chat`) | دردشة على مستوى المجتمع بنمط إعلانات | found |
| مجموعة عادية | عقدة `<group>` من النوع **0** | لا علاقة بمجتمع | found |

التصنيف واستخراج JID الخاص بالأم: `C23201A1a.A01` (الأنواع 0/1/2/3/6 أعلاه)، `C23201A1a.A03` (يقرأ JID الأم من `linked_parent jid`) — كلاهما `found` في [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.3، مُستشهَد به هنا لا مُستنتَج من جديد. `membership_approval_mode` لمجموعة فرعية يأخذ قيمته الافتراضية من `parent/default_membership_approval_mode="request_required"`.

---

## 2. نموذج العنونة والمشاركين

مُلخَّص من [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1–2.2 (التفاصيل الكاملة هناك؛ الحقول الخاصة بتاريخ المجموعة محذوفة هنا):

- عقدة `<group>`، المسار القديم `C23201A1a.A0C` (مشترك مع إشعارات المجموعة)؛ توجد نسخة مزدوجة من MEX/SMAX (`AbstractC23204A1d`، `AN6`، `C23690AKd`).
- السمات الأساسية: `id`، `creation`، `subject`، `s_t`/`s_o`/`s_o_pn`، `creator`/`creator_pn` (النسخ المزدوجة بامتداد `_pn` تحمل JID الهاتف بجوار LID).
- `addressing_mode` (`lid` / `pn`) — مخزَّن في `wa_group_admin_settings.addressing_mode`؛ أي قيمة غير `pn` تُقرأ كـ `lid`.
- `<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`، `C23205A1e.A0J`). `type` هو سمة الدور لكل مجموعة الكامنة وراء حالة المشرف؛ `jid`/`lid`/`phone_number` تحمل شكلي العنونة تبعاً لـ `addressing_mode`.

لا يوجد مفتاح من نوع `community_jid` أو `newsletter_jid` مستقل في أي مكان من العميل — تأكَّد ذلك بدليل كود طازج في §11.3 أدناه، وهو متسق مع نموذج "المجتمع مجموعة" في §1.

---

## 3. بروتوكول النقل القديم (`w:g2` / `w:gp2`)

عمليات المجموعة من ما قبل MEX لا تزال تعمل كـ IQ ثنائية XMPP ضمن النطاق `w:g2`؛ `w:gp2` مُدرج كأحد أشكال نقل الإشعارات الدفعية `notification` (فهارس `Protocols/xml-stanzas`، `Protocols/xmpp-namespaces-android`، `found`). مثال ملموس أُعيد بناؤه بنيوياً (`found`، `WASmaxGroupsGetGroupInfoRPC`):

```
iq[id=<stanzaId>, to=<groupJid>, type="get", xmlns="w:g2"]
  query[request=<string>, phash=<string?>]
    add_request[admin=<userJid>, code=<string>, expiration=<int>]   (optional, min=0 max=1)
```

أشكال الاستجابة: `ClientError` / `ServerError` / `Success` (بيانات تعريفية كاملة للمجموعة: المشاركون، الموضوع، الإنشاء، الوصف، إعدادات الرسائل المؤقتة). يحمل النطاق نفسه عمليات مجموعة غير مرتبطة موثَّقة في مواضع أخرى من هذا المستودع ولا تُعاد هنا:

- الإبلاغ للمشرف (`<iq to=groupJid type=set xmlns=w:g2><reports><report message_id=.../></reports></iq>`) ومفتاح تبديل إبلاغ المشرف (`allow_admin_reports`/`not_allow_admin_reports`) — [WA_REPORTING.md](WA_REPORTING.md) §9.
- الحل البديل القديم لطلبات موافقة العضوية — §11.2 أدناه.

---

## 4. سطح MEX GraphQL

فهرس الاستعلامات الدائمة (persisted-query) الخاص بـ `whatsapp-android-mex`، `found in` أصل `whatsapp-android-mex_client_persist_ids.json` المرفق. قيم `doc_id` تتغير مع كل بناء APK (95 تغييراً مُسجَّلاً بين 2.26.41.6 و2.26.45.10، `Querys/graphql-diff-2.26.41.6-to-2.26.45.10.md` في البرين) — الجداول أدناه هي لقطة من 2.26.41.6.

### 4.1 عمليات المجموعة (21)

| العملية | doc_id (2.26.41.6) | النوع |
|---|---|---|
| `AddParticipantsToGroupV2` | `28425601030437902` | Mutation |
| `AddParticipantsToGroupsV3` | `26857242513977310` | Mutation |
| `AddParticipantsToInteropGroup` | `25732168276369451` | Mutation |
| `AllowNonAdminGroupCreation` | `32024438593867697` | Query |
| `CreateGroup` | `38588807217433890` | Mutation |
| `GetPreRegGroupAddRequestsQuery` | `25018599251091282` | Query |
| `GroupMembershipRequestUpdate` | `29469157542702726` | Mutation |
| `GroupsCreateInteropGroup` | `25726817620301611` | Mutation |
| `GroupsStoreAndSendInvitesSMSMutation` | `27018112604523582` | Mutation |
| `GroupsStoreInvitesSMSMutation` | `25508574885415377` | Mutation |
| `JoinMembershipForm` | `28997137096573014` (جديدة في فهرس 2.26.45.10 فقط) | unknown |
| `LeaveInteropGroup` | `25346167795013271` | Query |
| `QueryBatchGetGroups` | `28340966318889583` | Query |
| `QueryGroupInfo` | `38342717635376065` | Query |
| `QueryGroupInfoByCode` | `27616410928049563` | Query |
| `QueryInteropGroupInfo` | `32734144032867938` | Query |
| `QueryLinkedGroupInfo` | `28221051120830416` | Query |
| `QueryMembershipApprovalRequests` | `28845604101745223` | Query |
| `QueryParticipatingGroups` | `28394594513526802` | Query |
| `QuerySuggestedGroups` | `26012055225051917` | Query |
| `SetGroupProperty` | `24688994337458819` | Mutation |
| `SetGroupResetInviteLink` | `24812851838367451` | Mutation |

### 4.2 عمليات المجتمع (4)

| العملية | doc_id (2.26.41.6) | النوع |
|---|---|---|
| `QueryCommunityParticipantCount` | `31981537024824321` | Query |
| `QuerySubgroupParticipantCount` | `24784259781196779` | Query |
| `QuerySubgroups` | `25554052094203120` | Query |
| `UpdateCommunityOwner` | `24781435194845316` | Mutation |

لا توجد عملية باسم `CreateCommunity` في هذا الفهرس — `unknown` ما إذا كان إنشاء المجتمع معالجاً محلياً (wizard) يسلسل `CreateGroup` مع عمليات الربط، أو ترقية ضمنية من جهة الخادم لمجموعة إلى أم؛ لم يُحسم في هذا التمرير.

### 4.3 المتغيرات المستخرجة من مواقع الاستدعاء في APK (`found`)

| العملية | المتغيرات | موقع الاستدعاء |
|---|---|---|
| `CreateGroup` | `participants`، `subject`، `expiration_time_in_sec`، `trigger`، `member_add_mode`، `member_link_mode`، `member_share_group_history_mode`، `username`، `user_lid` | `X/C36500G6k.java` |
| `AddParticipantsToGroupV2` | `mode`، `user_lid`، `username`، `group_id`، `participants`، `add_participants_metadata`، `input` | `X/C08600aH.java` |
| `AddParticipantsToGroupsV3` | `mode`، `group_ids`، `participants`، `tctoken`، `privacy_token`، `add_participants_metadata` | `X/RunnableC24380AnV.java` |
| `QueryGroupInfo` | `group_jid`، `query_context`، `input` | `X/C08630aK.java` |
| `QueryGroupInfoByCode` | `invite_code`، `query_context`، `get`، `input` | `X/C08600aH.java` |
| `QueryLinkedGroupInfo` | `group_jid`، `sub_group_jid_hint`، `query_context`، `input` | `X/JOF.java` |
| `QueryBatchGetGroups` | `group_jid`، `query_context`، `groups`، `request_context` | `X/FGG.java` |
| `QueryParticipatingGroups` | `input` | `X/C16710ou.java` |
| `SetGroupProperty` | انظر §9 | `X/A18.java`، `X/A19.java` |
| `SetGroupResetInviteLink` | `group_id`، `query_context`، `group_input`، `group_jid`، `max_use`، `seconds_for_expiry` | `X/C54392a5.java` |
| `AllowNonAdminGroupCreation` | `allow_non_admin_sub_group_creation` (bool) | `com/whatsapp/community/mex/AllowNonAdminSubGroupCreationGraphQlHandler.java` |
| `QuerySuggestedGroups` | `group_input` | `com/whatsapp/community/mex/GetSuggestedGroupsGraphQlHandler.java` |
| `QuerySubgroups` | `group_input` | `com/whatsapp/community/mex/GetSubgroupsGraphQlHandler.java` |
| `UpdateCommunityOwner` | `new_role`، `group_id`، `role_updates`، `user_jid` | `com/whatsapp/community/mex/TransferCommunityOwnershipGraphQlHandler.java` |
| `GroupsStoreAndSendInvitesSMSMutation` | `server_sent_sms`، `participants`، `entry_point`، `is_bundle_invite`، `participant`، `group_jid` | `com/whatsapp/invite/api/ServerSentGroupInviteMutationHelper.java`، `com/whatsapp/invite/ui/SMSPreviewGroupInviteBottomSheetFragment.java` |
| `GroupsStoreInvitesSMSMutation` | `partcipants` (كذا)، `group_jid` | `X/C67052zD.java` |
| `AddParticipantsToInteropGroup` | `gid`، `participants`، `jid`، `input` | `X/C3ZT.java` |
| `QueryInteropGroupInfo` | `gid`، `group_input` | `X/C3ZT.java` |

الباقي (`GetPreRegGroupAddRequestsQuery`، `GroupsCreateInteropGroup`، `LeaveInteropGroup`، `QueryCommunityParticipantCount`، `QuerySubgroupParticipantCount`) لا يوجد له موقع استدعاء ساكن مستخرَج: `unknown`، يُرجَّح أنه يرسل `{}`.

---

## 5. إنشاء مجموعة

تضبط `CreateGroup` (§4.3) القيم `member_add_mode`، `member_link_mode`، `member_share_group_history_mode` عند الإنشاء — وهي نفس خصائص الإدارة الثلاث التي يعدّلها `SetGroupProperty` لاحقاً (§9). `trigger` هو وسم نصي لنقطة الدخول (`found`، مجموعة القيم الدقيقة غير مُحصاة في هذا التمرير).

---

## 6. روابط الدعوة والدعوات

| العنصر | التفاصيل | المستوى |
|------|--------|------|
| إعادة ضبط/إنشاء رابط دعوة | `SetGroupResetInviteLink`: `group_id`، `group_jid`، `max_use`، `seconds_for_expiry` | found |
| حل رمز دعوة | `QueryGroupInfoByCode`: `invite_code` -> بيانات المجموعة | found |
| دعوة SMS (مجمَّعة) | `GroupsStoreAndSendInvitesSMSMutation`: `participants`، `entry_point`، `is_bundle_invite`، `server_sent_sms` | found |
| دعوة SMS (تخزين فقط) | `GroupsStoreInvitesSMSMutation`: `group_jid`، المشاركون | found |
| قائمة السماح/الحظر | قاعدة بيانات `wa_group_add_allow_list`، `wa_group_add_black_list` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |
| دعوات غير WhatsApp | قاعدة بيانات `group_non_wa_invites` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |

### 6.1 شكل النقل `groupInviteMessage`

`Message.groupInviteMessage`، الحقل **28**، النوع المتداخل `Message.GroupInviteMessage` (موجود في WAProto.proto):

| الحقل | # | النوع |
|-------|---|------|
| `groupJid` | 1 | string |
| `inviteCode` | 2 | string |
| `inviteExpiration` | 3 | int64 |
| `groupName` | 4 | string |
| `jpegThumbnail` | 5 | bytes |
| `caption` | 6 | string |
| `contextInfo` | 7 | ContextInfo |
| `groupType` | 8 | enum `GroupType` |

`GroupType`: `DEFAULT` = 0، `PARENT` = 1 — رسالة الدعوة نفسها تميّز بين دعوة مجموعة عادية ودعوة مجتمع (مجموعة أم)، بما يتسق مع نموذج "المجتمع مجموعة مصنَّفة" في §1. يوجد نوع آخر منفصل باسم `GroupInviteMessage` على المستوى الأعلى من ملف الـ proto نفسه؛ هذا الجدول يغطي فقط `Message.GroupInviteMessage` المتداخل المستخدَم في الحقل 28.

---

## 7. المشاركون: الإضافة، الاقتراح، التعداد

| العملية | الغرض (مستنتج من الاسم والمتغيرات) |
|---|---|
| `AddParticipantsToGroupV2` / `V3` | إضافة مستخدم واحد أو أكثر إلى مجموعة واحدة أو أكثر |
| `QueryParticipatingGroups` | إدراج المجموعات التي يكون المستدعي عضواً فيها |
| `QueryBatchGetGroups` | جلب دفعي للبيانات التعريفية لمجموعة من JIDs الخاصة بالمجموعات |
| `QuerySuggestedGroups` | سطح اقتراحات المجموعات/المجتمعات؛ قاعدة بيانات `member_suggested_groups_v2` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) |
| `QuerySubgroups` / `QuerySubgroupParticipantCount` / `QueryCommunityParticipantCount` | أعداد على مستوى المجتمع عبر المجموعات الفرعية المرتبطة |

سمة `<participant type=...>` (§2) تحمل علم الدور/الإدارة لكل مجموعة، ويحفظها محلياً `group_participant_user.rank` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §3.6) — إذن فمفهوم رتبة المشرف قائم، لكن لم تُعثر أي عملية MEX صريحة للترقية/التنزيل أو إزالة المشارك في هذا الفهرس (21/4 عملية مجموعة/مجتمع أعلاه شاملة لـ 2.26.41.6). **غير معروف**: هل لا يزال هذا المسار يعمل بشكل خالص كـ IQ قديم من نوع قائمة مشاركين `w:g2` (متسق مع اسم `AddParticipantsToGroupV2` نفسه الذي يُفهم منه وجود نسخة V1 سابقة)، أو تحت اسم عملية خارج مجموعتي الأسماء الفرعية `group`/`community`؛ لم يُحسم في هذا التمرير.

---

## 8. مجموعات Interop (باختصار)

`AddParticipantsToInteropGroup`، `GroupsCreateInteropGroup`، `QueryInteropGroupInfo`، `LeaveInteropGroup` — مجموعة صغيرة موازية من عمليات المجموعة لمجموعات "interop" المرتبطة بتطبيقات طرف ثالث. خارج نطاق هذا التقرير إلا من حيث السرد؛ انظر [WA_INTEROP.md](WA_INTEROP.md) لنموذج موافقة/ربط interop الذي تندرج ضمنه.

---

## 9. إعدادات الإدارة — `SetGroupProperty`

**المتغيرات** (`found`، `X/A18.java`، `X/A19.java`):

| الحقل | النوع | المعنى | المستوى |
|-------|------|---------|------|
| `group_id` | str | المجموعة المستهدفة | found |
| `subject` | str | اسم المجموعة | found |
| `description` | str | وصف المجموعة | found |
| `previous_id` | str | علامة تزامن تفاؤلية / قيمة سابقة (مستنتج) | inferred |
| `member_add_mode` | str | من يمكنه إضافة أعضاء (`all_member_add` / غيرها، يعكس العنصر الفرعي القديم `<member_add_mode>`، [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1) | found |
| `member_link_mode` | str | وضع صلاحية رابط الدعوة (مستنتج من الاسم) | inferred |
| `member_share_group_history_mode` | str | `ADMIN_SHARE` / `ALL_MEMBER_SHARE`، التعداد الكامل وتخطيط رسائل النظام في [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4 — غير مكرَّر هنا | found |
| `membership_approval_mode_enabled` | bool | يفعّل/يعطّل بوّابة طلب الانضمام لهذه المجموعة — انظر §11 | found |
| `limit_sharing`، `limit_sharing_enabled`، `limit_sharing_trigger` | str/bool/str | مفتاح تبديل حد إعادة التوجيه لهذه المجموعة (مستنتج: تقييد إعادة التوجيه "limit sharing") | inferred |
| `input` | str | كائن غلاف/سياق (الشكل غير محلول) | unknown |

النظير من جهة إشعار الخادم والقائمة الكاملة لأعمدة `wa_group_admin_settings` (`restrict_mode`، `announcement_group`، `no_frequently_forwarded`، `ephemeral_duration`، `require_membership_approval`، `addressing_mode`، `allow_member_labels`، ...) موجودة في [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4 — مُشار إليها بالترابط، غير مكرَّرة.

---

## 10. البنية الخاصة بالمجتمع

| العنصر | التفاصيل | المستوى |
|------|--------|------|
| تعداد المجموعات الفرعية | `QuerySubgroups` (`group_input`) | found |
| أعداد المجموعة الفرعية/المجتمع | `QuerySubgroupParticipantCount`، `QueryCommunityParticipantCount` | found (العمليات موجودة)، unknown (المتغيرات) |
| البحث عن المجموعة المرتبطة | `QueryLinkedGroupInfo` (`group_jid`، `sub_group_jid_hint`) — يحل مجموعة فرعية بمعرفة أمها | found |
| نقل الملكية | `UpdateCommunityOwner` (`new_role`، `group_id`، `role_updates`، `user_jid`) | found |
| مفتاح إنشاء مجموعة فرعية بدون إدارة | `AllowNonAdminGroupCreation` (`allow_non_admin_sub_group_creation` bool) | found |
| نسخة الاستطلاع للمجموعة الفرعية الافتراضية | `pollCreationMessageV2` هي فتحة الاستطلاع المستخدَمة عندما تكون الدردشة مجموعة فرعية افتراضية (`group_type == 3`) — [WA_POLLS.md](WA_POLLS.md) §1، §3.3 | found |
| جداول قاعدة البيانات | `subgroup_info`، `community_settings`، `group_relationship` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4) | found |

---

## 11. موافقة العضوية وموافقة الانضمام إلى المجتمع

### 11.1 المجموعات: بوّابة طلب الانضمام

`membership_approval_mode_enabled` (`SetGroupProperty`، §9) يفعّل بوّابة الانضمام الخاضعة لموافقة المشرف لمجموعة ما؛ `wa_group_admin_settings.require_membership_approval` هو العلم المحفوظ ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). بالنسبة لـ**مجموعة فرعية** تابعة لمجتمع، تأتي القيمة الافتراضية من الأم بدلاً من ذلك: `parent/default_membership_approval_mode="request_required"` (§1.1، `C23201A1a`). يُقسَّم تخزين الطلبات المعلَّقة حسب من يمكنه الموافقة: `group_membership_approval_requests` (مرئي للمشرف) و`non_admin_group_membership_approval_requests`؛ يحمل `group_membership_form_questions` أسئلة يضبطها المشرف ويجب على طالب الانضمام الإجابة عليها، ويتابع `group_membership_count` الأعداد الإجمالية (جميعها `found`، [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). يمثّل `group_membership_form_questions` الدليل الملموس من جهة العميل على وجود تدفق استمارة عضوية — وهو ذو صلة مباشرة بـ `JoinMembershipForm` أدناه.

### 11.2 سطح النقل: مسار MEX الأساسي + الحل البديل القديم

`com/whatsapp/group/data/GroupFetchAllMembershipApprovalRequestsJob` (`found`، smali من 2.26.45.10) ينفّذ "جلب طلبات الانضمام المعلَّقة بانتظار موافقة المشرف" لـ `groupJidRawString`، ويُضبَط وقت التشغيل بواسطة `LX/00E;->A0G(LX/00E;LX/00g;)Z` مقابل معرّف العلم `LX/4WC;->A04` (يُقرأ عبر `LX/00U;->A03(0x10d4)`):

| المسار | الشرط | الآلية |
|------|-----------|--------|
| MEX | العلم مُفعَّل | `GraphQlCallInput` بـ `query_context="INTERACTIVE"` والهدف `GroupJid`، العملية **`QueryMembershipApprovalRequests`** على النطاق `whatsapp-android-mex` |
| IQ ثنائي قديم | العلم مُعطَّل (حل بديل `LX/0RD`) | `<iq type="get" xmlns="w:g2" to="<group_jid>" id="..."><membership_approval_requests/></iq>` |

يتغير `doc_id` الخاص بـ `QueryMembershipApprovalRequests` بالشكل الطبيعي بين البناءات: `28845604101745223` (2.26.41.6) → `28584744077887639` (2.26.45.10). عملية الموافقة/الرفض الخاصة بالمشرف، `GroupMembershipRequestUpdate`، هي النظير المقابل (`29469157542702726` → `28746221238391491`، بنفس نمط التغيّر الطبيعي)؛ موقع استدعائها لم يُتعقَّب في هذا التمرير، لكنها العملية الوحيدة من جهة المشرف على عضوية المجموعة في هذا الفهرس (§4.1).

`JoinMembershipForm` (doc_id `28997137096573014`) جديدة فعلاً في فهرس 2.26.45.10 — غائبة عن 2.26.41.6، وليست تغيّراً لعملية موجودة. اسمها، مع جدول `group_membership_form_questions` (§11.1)، يجعلها أفضل مرشّح لعملية الإرسال التي "تجيب عن أسئلة استمارة العضوية التي ضبطها المشرف وتطلب الانضمام" — لكن موقع استدعائها لم يُتعقَّب في هذا التمرير. **مستنتج**، لا موجود بالدليل، بالنسبة لدورها ومخططها الدقيق.

### 11.3 موافقة الانضمام إلى المجتمع على وجه التحديد (2.26.45.10، found)

حزمة جديدة `com/whatsapp/community/product/joinapproval/`، صنف واحد: `CommunityJoinApprovalNuxBottomSheet` — صحيفة شرح محلية للواجهة ("ستحتاج إلى موافقة المشرف للانضمام إلى هذا المجتمع")، وليست موقع استدعاء شبكة بنفسها.

- يُنشئها `LX/3IN;->C3f` بمعطيات bundle هي `"group_jid"` (JID الخاص بالمجتمع نفسه، يُقرأ كسلسلة JID خام للمجموعة) و`"community_name"`.
- معالج الزر الأساسي `LX/3Ge;->C3f`، `pswitch_28`: يقرأ `GroupJid` المخزَّن، يستدعي `LX/122;->A01(Context, GroupJid, Integer)Intent`، يشغّله عبر `LX/0KC;->A02`، ثم يُغلق الصحيفة.

**نتيجة رئيسية:** المجتمع مُعنوَن بـ `group_jid`، لا بمفتاح مستقل من نوع `community_jid`/`newsletter_jid` — تأكيد مباشر من الكود، لا من اصطلاح التسمية فقط، لنموذج "المجتمع مجموعة" في §1/§2. لا توجد عملية بنمط `Community*ApprovalRequests` في أي مكان من الفهرس؛ تنتقل طلبات انضمام المجتمع المعلَّقة عبر زوج MEX نفسه `QueryMembershipApprovalRequests` / `GroupMembershipRequestUpdate` (ونفس الحل البديل القديم `w:g2`) الذي تستخدمه المجموعة العادية، لأن مهمّة موافقة العضوية لا ترى سوى `groupJidRawString`.

### 11.4 الحكم النهائي

| الزعم | المستوى |
|-------|------|
| المجتمع مُعنوَن بـ `group_jid`، نفس مسار الكود كالمجموعات | found |
| إدراج الطلبات المعلَّقة: MEX `QueryMembershipApprovalRequests` | found |
| الموافقة/الرفض: MEX `GroupMembershipRequestUpdate` | found (العملية موجودة ومُفهرَسة)؛ موقع الاستدعاء غير مُتعقَّب |
| الحل البديل القديم: `<iq xmlns="w:g2"><membership_approval_requests/></iq>` | found |
| علم الميزة الذي يختار بين MEX والقديم | found (معرّف العلم، وليس حالة طرحه الحالية) |
| جهة الإرسال هي `JoinMembershipForm` | inferred |
| المخطط/المتغيرات الدقيقة لـ `JoinMembershipForm` | unknown |
| منطق القبول/التحقق من جهة الخادم | unknown (تحليل ساكن فقط، لا التقاط لحركة شبكة) |

---

## 12. الإشارة المرجعية إلى التخزين المحلي

القوائم الكاملة للأعمدة موجودة في [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)؛ هذا جدول إشاري، لا مكرَّر:

| الجدول | الدور |
|-------|------|
| `wa_group_admin_settings` | إعدادات الإدارة لكل مجموعة (وضع العنونة، التاريخ، الموافقة، حد إعادة التوجيه، ...) |
| `group_participant_user`، `group_past_participant_user`، `group_participant_device` | المشاركون الحاليون/السابقون، الرتبة، حالة مفتاح المرسل لكل جهاز |
| `group_membership_approval_requests`، `non_admin_group_membership_approval_requests` | طلبات الانضمام المعلَّقة، مقسَّمة حسب رؤية الموافق |
| `group_membership_form_questions` | أسئلة استمارة العضوية التي يضبطها المشرف (§11.1، §11.2) |
| `group_membership_count` | الأعداد الإجمالية |
| `subgroup_info`، `community_settings`، `group_relationship` | بنية المجتمع/المجموعة الفرعية |
| `member_suggested_groups_v2` | سطح المجموعات المقترحة |
| `group_suspension_appeal` | حالة التماس تعليق المجموعة |
| `group_non_wa_invites` | الدعوات لجهات اتصال غير WhatsApp |
| `group_root_key_mapping` | تعيين مفتاح الجذر لمفتاح المرسل |

---

## 13. ملاحظات التنفيذ لـ Baileys / velowa

تستخدم جميع عمليات MEX الخاصة بالمجموعة/المجتمع نفس غلاف IQ من نوع `w:mex` المستخدَم لكل استعلام دائم آخر في هذا المستودع (`Protocols/mex-graphql`، `graphql-invocation-guide.md`):

```js
const res = await sock.query({
  tag: 'iq', attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '<doc_id>' },
    content: Buffer.from(JSON.stringify({ queryId: '<doc_id>', variables })) }],
})
```

تبقى عملية جلب بيانات المجموعة/المشاركين القديمة على `w:g2` وهي مُنفَّذة بالفعل في معظم مكتبات WA Web (دوال بنمط `groupMetadata`، `groupQuery`)؛ موافقة العضوية تحتاج إضافة IQ من §11.2 صريحاً — معظم المكتبات لا تستعلمها.

| سبب الفشل | الحل |
|---------------|-----|
| تثبيت `doc_id` ثابت لأي عملية مجموعة/مجتمع | `doc_id` يتغير مع كل بناء APK (مؤكَّد: تغيّرت 4 عمليات مجموعة بين 2.26.38.10 و2.26.41.6 وحدها)؛ أعِد استخراجه من فهرس حالي، لا تثبّته |
| افتراض أن موافقة العضوية دائماً عبر `w:g2` القديم | هي مضبوطة بعلم ميزة؛ متى فُعِّل العلم من جهة الخادم لحساب ما، لا تظهر الطلبات المعلَّقة إلا عبر MEX `QueryMembershipApprovalRequests` — نفِّذ المساريْن أو MEX فقط للمستقبل |
| افتراض أن للمجتمع نوع JID خاصاً به | ليس كذلك — عالجه بـ JID الخاص بالمجموعة الأم `@g.us` نفسه، تماماً كأي عملية مجموعة |
| محاولة إرسال طلب انضمام مُقيَّد برمجياً | مخطط `JoinMembershipForm` غير محلول (دوره مستنتج فقط)؛ غير قابل للتنفيذ بثقة حتى الآن |

---

## 14. فروق أساسية يجب عدم الخلط بينها

- **المجتمع مجموعة مصنَّفة، لا كيان مستقل.** لا يوجد `community_jid`؛ JID الخاص بالمجتمع نفسه هو JID مجموعة من النوع 1 (`parent`).
- **`member_share_group_history_mode`** (من يمكنه مشاركة التاريخ الحديث مع المنضمين الجدد، [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4) غير مرتبط بـ **`membership_approval_mode_enabled`** (بوّابة طلب الانضمام، §9/§11) — كلاهما حقلان في `SetGroupProperty` لكنهما يتحكمان في ميزتين مختلفتين.
- **الإبلاغ للمشرف عبر `w:g2`** ([WA_REPORTING.md](WA_REPORTING.md) §9) و**الحل البديل لطلبات موافقة العضوية عبر `w:g2`** (§11.2) يتشاركان النطاق لكنهما عنصران فرعيان غير مرتبطين (`reports`/`allow_admin_reports` مقابل `membership_approval_requests`).
- **`JoinMembershipForm`** عملية إرسال مستنتجة، لا مؤكَّدة — لا تُعامَل كـ found.
- **الترقية/التنزيل/إزالة المشارك** لا توجد لها عملية MEX محدَّدة في هذا الفهرس؛ تُعامَل كغير محسومة، لا كـ"تعمل فقط عبر `w:g2` القديم" (افتراض، لا دليل).

---

## 15. تدفق موافقة الانضمام إلى المجتمع (كما تُثبِت الأدلة الحالية)

```
[Member]                         [Client]                              [Server / whatsapp-android-mex]
   │ taps "Request to join"         │                                        │
   ├────────────────────────────────▶ CommunityJoinApprovalNuxBottomSheet    │
   │                                 │  (local explainer, group_jid+name)    │
   │ taps primary button             │                                        │
   ├────────────────────────────────▶ LX/3Ge;->C3f pswitch_28                │
   │                                 │  -> LX/122;->A01(ctx, GroupJid, int)  │
   │                                 │     Intent into group/community flow  │
   │                                 │  (submit side, inferred)              │
   │                                 ├───────────────────────────────────────▶ JoinMembershipForm (inferred)
   │                                 │                                        │
[Admin]                           [Client]                                 │
   │ opens pending-requests screen   │                                        │
   ├────────────────────────────────▶ GroupFetchAllMembershipApprovalRequestsJob
   │                                 │  flag on  ─▶ QueryMembershipApprovalRequests (MEX)
   │                                 │  flag off ─▶ <iq xmlns="w:g2"><membership_approval_requests/></iq>
   │                                 │                                        │
   │ approves / denies               │                                        │
   ├────────────────────────────────▶ GroupMembershipRequestUpdate (MEX) ────▶ server
```

---

## 16. عناصر مفتوحة / نقاط حذر

- متغيرات/شكل استجابة `JoinMembershipForm`: غير معروف، غير مُتعقَّب من موقع استدعاء.
- متغيرات `GroupMembershipRequestUpdate` نفسها: لم تُستخرج من موقع استدعاء في هذا التمرير (العملية مؤكَّد وجودها فقط).
- الترقية/التنزيل/إزالة المشارك: لا عملية MEX محدَّدة؛ قديمة فقط أم غائبة من الفهرس — غير محسوم.
- `CreateCommunity`: لا توجد عملية MEX بهذا الاسم؛ مسار إنشاء المجتمع غير محسوم (تسلسل معالج العميل بين `CreateGroup` والربط هو التخمين العامل، لا المؤكَّد).
- جميع الزعومات في §11 خارج وجود جداول قاعدة البيانات هي تحليل ساكن؛ لا شيء هنا مختبَر بحركة شبكة (وفق عقد الأدلة — لم يُجرَ أي تفاعل مع خادم حي لهذا التقرير).
