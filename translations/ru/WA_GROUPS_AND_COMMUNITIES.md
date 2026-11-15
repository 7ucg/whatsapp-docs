<!-- src-sha1: 900bf74a45a7fabc6e7b8c42ef4df8074e676084 -->
# WhatsApp Группы и сообщества — Full RE Report
**Версия:** 2.26.41.6 (поверхность протокола membership-approval/join-approval дополнительно проверена на 2.26.45.10, отмечено в тексте) | **Дата:** 2026-11-15
**Область:** структурная модель группы и сообщества (родительская группа, связанные подгруппы, подгруппа по умолчанию, общий чат), адресация JID, устаревшая поверхность протокола `w:g2`/`w:gp2`, каталог GraphQL-операций группы/сообщества `whatsapp-android-mex`, потоки создания/приглашения/административных действий, ссылки-приглашения и одобрение вступления в сообщество (`QueryMembershipApprovalRequests`, `GroupMembershipRequestUpdate`, устаревший резервный путь `w:g2` и предполагаемая операция отправки `JoinMembershipForm`).

---

## 1. Что это

WhatsApp **сообщество** (community) не является отдельной адресуемой сущностью. Это **группа** — то же пространство JID, тот же парсер узла `<group>`, та же таблица `wa_group_admin_settings` — которая играет роль **родительской группы** для набора **связанных подгрупп**. Этот отчёт сводит вместе модель группы/сообщества, разбросанную по [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2 (классификация, адресация), [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) (таблицы БД), [WA_REPORTING.md](WA_REPORTING.md) (поверхность report-to-admin `w:g2`) и [WA_POLLS.md](WA_POLLS.md) (вариант опроса для подгруппы по умолчанию), и добавляет каталог MEX-операций группы/сообщества и находку про одобрение вступления в сообщество на 2.26.45.10.

### 1.1 Сущности

| Сущность | Адресация | Отношение | Уровень |
|--------|-----------|----------|------|
| Группа | собственный JID `@g.us` | — | found |
| Сообщество | **то же** пространство JID `@g.us`, что и у группы; классифицируется, но не типизируется отдельно | группа, выступающая родителем | found |
| Родительская группа | тип узла `<group>` **1** (присутствует дочерний элемент `parent`) | верхний уровень сообщества | found |
| Связанная подгруппа | тип узла `<group>` **2** (дочерний элемент `linked_parent jid`) | `linked_parent jid` указывает на JID родителя | found |
| Подгруппа по умолчанию | тип узла `<group>` **3** (дочерний элемент `default_sub_group`) | автоматически создаваемая подгруппа сообщества; локально `group_type` **3**, также триггер для `pollCreationMessageV2` (WA_POLLS §1) | found |
| Общий чат | тип узла `<group>` **6** (дочерний элемент `general_chat`) | чат сообщества в стиле объявлений | found |
| Обычная группа | тип узла `<group>` **0** | не связана с сообществом | found |

Классификация и извлечение JID родителя: `C23201A1a.A01` (типы 0/1/2/3/6 выше), `C23201A1a.A03` (читает JID родителя из `linked_parent jid`) — оба `found` в [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.3, здесь приводятся по ссылке, а не выводятся заново. `membership_approval_mode` для подгруппы по умолчанию наследуется от родителя: `parent/default_membership_approval_mode="request_required"`.

---

## 2. Модель адресации и участников

Сжато из [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1–2.2 (полные детали там; специфичные для group-history поля здесь опущены):

- узел `<group>`, устаревший путь `C23201A1a.A0C` (общий с уведомлениями группы); существует двойник MEX/SMAX (`AbstractC23204A1d`, `AN6`, `C23690AKd`).
- Основные атрибуты: `id`, `creation`, `subject`, `s_t`/`s_o`/`s_o_pn`, `creator`/`creator_pn` (двойники `_pn` несут телефонный JID рядом с LID).
- `addressing_mode` (`lid` / `pn`) — хранится в `wa_group_admin_settings.addressing_mode`; всё, что не `pn`, читается как `lid`.
- `<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`). `type` — атрибут роли участника в рамках группы, определяющий административный статус; `jid`/`lid`/`phone_number` несут две формы адреса в зависимости от `addressing_mode`.

Отдельного ключа вида `community_jid` или `newsletter_jid` нигде в клиенте не существует — подтверждено свежим кодовым доказательством в §11.3 ниже, что согласуется с моделью §1 "сообщество — это группа".

---

## 3. Устаревший протокол (`w:g2` / `w:gp2`)

Операции с группами до появления MEX всё ещё выполняются как бинарные XMPP IQ в пространстве имён `w:g2`; `w:gp2` фигурирует как один из вариантов push-стансы `notification` (инвентаризация в `Protocols/xml-stanzas`, `Protocols/xmpp-namespaces-android`, `found`). Конкретный, структурно восстановленный пример (`found`, `WASmaxGroupsGetGroupInfoRPC`):

```
iq[id=<stanzaId>, to=<groupJid>, type="get", xmlns="w:g2"]
  query[request=<string>, phash=<string?>]
    add_request[admin=<userJid>, code=<string>, expiration=<int>]   (optional, min=0 max=1)
```

Варианты ответа: `ClientError` / `ServerError` / `Success` (полные метаданные группы: участники, тема, дата создания, описание, настройки эфемерности). То же пространство имён несёт не связанные с этим операции над группами, документированные в другом месте репозитория и здесь не повторяемые:

- Report-to-admin (`<iq to=groupJid type=set xmlns=w:g2><reports><report message_id=.../></reports></iq>`) и переключатель admin-report (`allow_admin_reports`/`not_allow_admin_reports`) — [WA_REPORTING.md](WA_REPORTING.md) §9.
- Устаревший резервный путь для запросов на одобрение вступления — §11.2 ниже.

---

## 4. Поверхность MEX GraphQL

Каталог persisted-query `whatsapp-android-mex`, `found in` в поставляемом ассете `whatsapp-android-mex_client_persist_ids.json`. Значения `doc_id` меняются при каждой сборке APK (зафиксировано 95 ротаций между 2.26.41.6 и 2.26.45.10, `Querys/graphql-diff-2.26.41.6-to-2.26.45.10.md` в brain) — таблицы ниже — это снапшот 2.26.41.6.

### 4.1 Операции группы (21)

| Операция | doc_id (2.26.41.6) | Тип |
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
| `JoinMembershipForm` | `28997137096573014` (новое только в каталоге 2.26.45.10) | unknown |
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

### 4.2 Операции сообщества (4)

| Операция | doc_id (2.26.41.6) | Тип |
|---|---|---|
| `QueryCommunityParticipantCount` | `31981537024824321` | Query |
| `QuerySubgroupParticipantCount` | `24784259781196779` | Query |
| `QuerySubgroups` | `25554052094203120` | Query |
| `UpdateCommunityOwner` | `24781435194845316` | Mutation |

В этом каталоге не существует операции с именем `CreateCommunity` — `unknown`, является ли создание сообщества локальным клиентским мастером, который сцепляет `CreateGroup` + вызовы связывания, или серверным неявным повышением группы до родительской; в этом проходе не разрешено.

### 4.3 Переменные, восстановленные из точек вызова в APK (`found`)

| Операция | Переменные | Точка вызова |
|---|---|---|
| `CreateGroup` | `participants`, `subject`, `expiration_time_in_sec`, `trigger`, `member_add_mode`, `member_link_mode`, `member_share_group_history_mode`, `username`, `user_lid` | `X/C36500G6k.java` |
| `AddParticipantsToGroupV2` | `mode`, `user_lid`, `username`, `group_id`, `participants`, `add_participants_metadata`, `input` | `X/C08600aH.java` |
| `AddParticipantsToGroupsV3` | `mode`, `group_ids`, `participants`, `tctoken`, `privacy_token`, `add_participants_metadata` | `X/RunnableC24380AnV.java` |
| `QueryGroupInfo` | `group_jid`, `query_context`, `input` | `X/C08630aK.java` |
| `QueryGroupInfoByCode` | `invite_code`, `query_context`, `get`, `input` | `X/C08600aH.java` |
| `QueryLinkedGroupInfo` | `group_jid`, `sub_group_jid_hint`, `query_context`, `input` | `X/JOF.java` |
| `QueryBatchGetGroups` | `group_jid`, `query_context`, `groups`, `request_context` | `X/FGG.java` |
| `QueryParticipatingGroups` | `input` | `X/C16710ou.java` |
| `SetGroupProperty` | см. §9 | `X/A18.java`, `X/A19.java` |
| `SetGroupResetInviteLink` | `group_id`, `query_context`, `group_input`, `group_jid`, `max_use`, `seconds_for_expiry` | `X/C54392a5.java` |
| `AllowNonAdminGroupCreation` | `allow_non_admin_sub_group_creation` (bool) | `com/whatsapp/community/mex/AllowNonAdminSubGroupCreationGraphQlHandler.java` |
| `QuerySuggestedGroups` | `group_input` | `com/whatsapp/community/mex/GetSuggestedGroupsGraphQlHandler.java` |
| `QuerySubgroups` | `group_input` | `com/whatsapp/community/mex/GetSubgroupsGraphQlHandler.java` |
| `UpdateCommunityOwner` | `new_role`, `group_id`, `role_updates`, `user_jid` | `com/whatsapp/community/mex/TransferCommunityOwnershipGraphQlHandler.java` |
| `GroupsStoreAndSendInvitesSMSMutation` | `server_sent_sms`, `participants`, `entry_point`, `is_bundle_invite`, `participant`, `group_jid` | `com/whatsapp/invite/api/ServerSentGroupInviteMutationHelper.java`, `com/whatsapp/invite/ui/SMSPreviewGroupInviteBottomSheetFragment.java` |
| `GroupsStoreInvitesSMSMutation` | `partcipants` (sic), `group_jid` | `X/C67052zD.java` |
| `AddParticipantsToInteropGroup` | `gid`, `participants`, `jid`, `input` | `X/C3ZT.java` |
| `QueryInteropGroupInfo` | `gid`, `group_input` | `X/C3ZT.java` |

Для остальных (`GetPreRegGroupAddRequestsQuery`, `GroupsCreateInteropGroup`, `LeaveInteropGroup`, `QueryCommunityParticipantCount`, `QuerySubgroupParticipantCount`) точка вызова статически не восстановлена: `unknown`, вероятно отправляют `{}`.

---

## 5. Создание группы

`CreateGroup` (§4.3) задаёт `member_add_mode`, `member_link_mode`, `member_share_group_history_mode` в момент создания — те же три административных свойства, которые позже редактирует `SetGroupProperty` (§9). `trigger` — строковый тег точки входа (`found`, точный набор значений в этом проходе не перечислен).

---

## 6. Ссылки-приглашения и инвайты

| Элемент | Детали | Уровень |
|------|--------|------|
| Сброс/создание ссылки-приглашения | `SetGroupResetInviteLink`: `group_id`, `group_jid`, `max_use`, `seconds_for_expiry` | found |
| Разрешение кода приглашения | `QueryGroupInfoByCode`: `invite_code` -> информация о группе | found |
| SMS-приглашение (пакетное) | `GroupsStoreAndSendInvitesSMSMutation`: `participants`, `entry_point`, `is_bundle_invite`, `server_sent_sms` | found |
| SMS-приглашение (только сохранение) | `GroupsStoreInvitesSMSMutation`: `group_jid`, participants | found |
| Список разрешений/запретов | БД `wa_group_add_allow_list`, `wa_group_add_black_list` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |
| Приглашения не-пользователям WhatsApp | БД `group_non_wa_invites` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) | found |

### 6.1 Форма сообщения `groupInviteMessage`

`Message.groupInviteMessage`, поле **28**, вложенный тип `Message.GroupInviteMessage` (найдено в WAProto.proto):

| Поле | # | Тип |
|-------|---|------|
| `groupJid` | 1 | string |
| `inviteCode` | 2 | string |
| `inviteExpiration` | 3 | int64 |
| `groupName` | 4 | string |
| `jpegThumbnail` | 5 | bytes |
| `caption` | 6 | string |
| `contextInfo` | 7 | ContextInfo |
| `groupType` | 8 | enum `GroupType` |

`GroupType`: `DEFAULT` = 0, `PARENT` = 1 — само сообщение-приглашение различает обычное приглашение в группу от приглашения в сообщество (родительскую группу), что согласуется с моделью §1 "сообщество — это классифицированная группа". В том же proto-файле существует отдельный, не связанный с этим верхнеуровневый тип `GroupInviteMessage`; эта таблица охватывает только вложенный `Message.GroupInviteMessage`, используемый в поле 28.

---

## 7. Участники: добавление, предложение, перечисление

| Операция | Назначение (предположение по имени + переменным) |
|---|---|
| `AddParticipantsToGroupV2` / `V3` | добавить одного или нескольких пользователей в одну или несколько групп |
| `QueryParticipatingGroups` | перечислить группы, в которых состоит вызывающий |
| `QueryBatchGetGroups` | пакетное получение метаданных для набора JID групп |
| `QuerySuggestedGroups` | поверхность предложений сообществ/групп; БД `member_suggested_groups_v2` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md)) |
| `QuerySubgroups` / `QuerySubgroupParticipantCount` / `QueryCommunityParticipantCount` | счётчики уровня сообщества по связанным подгруппам |

Атрибут `<participant type=...>` (§2) несёт флаг admin/роли в рамках группы, а `group_participant_user.rank` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §3.6) сохраняет его локально — таким образом ранг администратора существует как понятие, но в этом каталоге не найдено явной MEX-операции повышения/понижения или удаления участника (21/4 операций группы/сообщества выше являются исчерпывающими для 2.26.41.6). **Unknown**: идёт ли этот путь по-прежнему чисто через устаревший IQ со списком участников `w:g2` (согласуется с тем, что само имя `AddParticipantsToGroupV2` подразумевает существование предшественника V1) или под каким-то именем операции вне подстрок-корзин `group`/`community`; в этом проходе не разрешено.

---

## 8. Interop-группы (кратко)

`AddParticipantsToInteropGroup`, `GroupsCreateInteropGroup`, `QueryInteropGroupInfo`, `LeaveInteropGroup` — параллельный небольшой набор операций над группами для групп, связанных мостом со сторонними сервисами ("interop"). Здесь вне области, за исключением их перечисления; модель согласия/моста interop, в которую они встроены, см. [WA_INTEROP.md](WA_INTEROP.md).

---

## 9. Административные настройки — `SetGroupProperty`

**Переменные** (`found`, `X/A18.java`, `X/A19.java`):

| Поле | Тип | Значение | Уровень |
|-------|------|---------|------|
| `group_id` | str | целевая группа | found |
| `subject` | str | название группы | found |
| `description` | str | описание группы | found |
| `previous_id` | str | маркер оптимистичной конкурентности / предыдущего значения (предположение) | inferred |
| `member_add_mode` | str | кто может добавлять участников (`all_member_add` / другое, зеркалирует устаревший дочерний элемент `<member_add_mode>`, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.1) | found |
| `member_link_mode` | str | режим разрешения на ссылку-приглашение (предположение по имени) | inferred |
| `member_share_group_history_mode` | str | `ADMIN_SHARE` / `ALL_MEMBER_SHARE`, полный enum и маппинг системных сообщений в [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4 — здесь не повторяется | found |
| `membership_approval_mode_enabled` | bool | включает/выключает фильтрацию запросов на вступление для этой группы — см. §11 | found |
| `limit_sharing`, `limit_sharing_enabled`, `limit_sharing_trigger` | str/bool/str | переключатель ограничения пересылки для этой группы (предположение: ограничение "limit sharing" на пересылку) | inferred |
| `input` | str | объект-обёртка/контекст (структура не раскрыта) | unknown |

Серверный аналог уведомления и полный список колонок `wa_group_admin_settings` (`restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `require_membership_approval`, `addressing_mode`, `allow_member_labels`, …) находятся в [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4 — перекрёстная ссылка, не дублируется.

---

## 10. Структура, специфичная для сообщества

| Элемент | Детали | Уровень |
|------|--------|------|
| Перечисление подгрупп | `QuerySubgroups` (`group_input`) | found |
| Счётчики подгрупп/сообщества | `QuerySubgroupParticipantCount`, `QueryCommunityParticipantCount` | found (операции существуют), unknown (переменные) |
| Поиск связанной группы | `QueryLinkedGroupInfo` (`group_jid`, `sub_group_jid_hint`) — разрешает подгруппу по её родителю | found |
| Передача владения | `UpdateCommunityOwner` (`new_role`, `group_id`, `role_updates`, `user_jid`) | found |
| Переключатель создания подгрупп не-администраторами | `AllowNonAdminGroupCreation` (`allow_non_admin_sub_group_creation` bool) | found |
| Вариант опроса для подгруппы по умолчанию | `pollCreationMessageV2` — слот опроса, используемый когда чат является подгруппой по умолчанию (`group_type == 3`) — [WA_POLLS.md](WA_POLLS.md) §1, §3.3 | found |
| Таблицы БД | `subgroup_info`, `community_settings`, `group_relationship` ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4) | found |

---

## 11. Одобрение вступления и одобрение вступления в сообщество

### 11.1 Группы: фильтрация запросов на вступление

`membership_approval_mode_enabled` (`SetGroupProperty`, §9) включает фильтрацию вступления с одобрением админа для группы; `wa_group_admin_settings.require_membership_approval` — сохраняемый флаг ([WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). Для **подгруппы** сообщества значение по умолчанию наследуется от родителя: `parent/default_membership_approval_mode="request_required"` (§1.1, `C23201A1a`). Хранение ожидающих запросов разделено по тому, кто может их одобрять: `group_membership_approval_requests` (видно администратору) и `non_admin_group_membership_approval_requests`; `group_membership_form_questions` содержит настроенные администратором вопросы, на которые должен ответить вступающий, а `group_membership_count` отслеживает агрегированные счётчики (все `found`, [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md) §4). `group_membership_form_questions` — конкретное клиентское доказательство существования потока формы вступления — напрямую относящееся к `JoinMembershipForm` ниже.

### 11.2 Поверхность протокола: основной путь MEX + устаревший резервный путь

`com/whatsapp/group/data/GroupFetchAllMembershipApprovalRequestsJob` (`found`, smali 2.26.45.10) реализует "получить ожидающие одобрения администратора запросы на вступление" для `groupJidRawString`, с runtime-переключением через `LX/00E;->A0G(LX/00E;LX/00g;)Z` по идентификатору флага `LX/4WC;->A04` (читается через `LX/00U;->A03(0x10d4)`):

| Путь | Условие | Механизм |
|------|-----------|----------|
| MEX | флаг включён | `GraphQlCallInput` с `query_context="INTERACTIVE"` и целевым `GroupJid`, операция **`QueryMembershipApprovalRequests`** в пространстве имён `whatsapp-android-mex` |
| Устаревший бинарный IQ | флаг выключен (резерв `LX/0RD`) | `<iq type="get" xmlns="w:g2" to="<group_jid>" id="..."><membership_approval_requests/></iq>` |

`doc_id` для `QueryMembershipApprovalRequests` меняется обычным образом между сборками: `28845604101745223` (2.26.41.6) → `28584744077887639` (2.26.45.10). Административная мутация одобрения/отказа `GroupMembershipRequestUpdate` — её аналог (`29469157542702726` → `28746221238391491`, тот же паттерн обычной ротации); её точка вызова в этом проходе не трассирована, но это единственная административная мутация уровня group-membership в каталоге (§4.1).

`JoinMembershipForm` (doc_id `28997137096573014`) — действительно новая операция в каталоге 2.26.45.10 — отсутствует в 2.26.41.6, не ротация существующей операции. Её имя в сочетании с таблицей `group_membership_form_questions` (§11.1) делает её наилучшим кандидатом на мутацию отправки со стороны вступающего "ответить на вопросы формы вступления администратора и запросить вступление" — но её точка вызова в этом проходе не трассирована. **Inferred**, а не found, для её точной роли и схемы.

### 11.3 Одобрение вступления в сообщество конкретно (2.26.45.10, found)

Новый пакет `com/whatsapp/community/product/joinapproval/`, один класс: `CommunityJoinApprovalNuxBottomSheet` — локальный пояснительный лист UI ("для вступления в это сообщество потребуется одобрение администратора"), сам не является точкой сетевого вызова.

- Конструируется `LX/3IN;->C3f` с аргументами bundle `"group_jid"` (собственный JID сообщества, читается как строка raw-JID группы) и `"community_name"`.
- Обработчик основной кнопки `LX/3Ge;->C3f`, `pswitch_28`: читает сохранённый `GroupJid`, вызывает `LX/122;->A01(Context, GroupJid, Integer)Intent`, запускает через `LX/0KC;->A02`, закрывает лист.

**Ключевая находка:** сообщество адресуется через `group_jid`, а не через отдельный ключ вида `community_jid`/`newsletter_jid` — это прямое подтверждение кодом, а не просто соглашение об именовании, модели §1/§2 "сообщество — это группа". В каталоге нигде не существует операции вида `Community*ApprovalRequests`; ожидающие запросы на вступление в сообщество идут по той же самой паре MEX `QueryMembershipApprovalRequests` / `GroupMembershipRequestUpdate` (и тому же устаревшему резервному пути `w:g2`), что использует обычная группа, потому что задача одобрения вступления видит только `groupJidRawString`.

### 11.4 Вердикт

| Утверждение | Уровень |
|-------|------|
| Сообщество адресуется через `group_jid`, тот же путь кода, что у групп | found |
| Список ожидающих запросов: MEX `QueryMembershipApprovalRequests` | found |
| Одобрение/отказ: MEX `GroupMembershipRequestUpdate` | found (операция существует, каталогизирована); точка вызова не трассирована |
| Устаревший резервный путь: `<iq xmlns="w:g2"><membership_approval_requests/></iq>` | found |
| Переключатель фичи, выбирающий MEX vs. устаревший путь | found (идентификатор флага, но не его текущее состояние раскатки) |
| Сторона отправки — `JoinMembershipForm` | inferred |
| Точная схема/переменные `JoinMembershipForm` | unknown |
| Серверная логика принятия/валидации | unknown (только статический анализ, перехвата трафика не было) |

---

## 12. Перекрёстная ссылка на локальное хранилище

Полные списки колонок находятся в [WA_LOCAL_STORAGE.md](WA_LOCAL_STORAGE.md); это таблица-указатель, а не дубликат:

| Таблица | Роль |
|-------|------|
| `wa_group_admin_settings` | административные настройки группы (режим адресации, история, одобрение, ограничение пересылки, ...) |
| `group_participant_user`, `group_past_participant_user`, `group_participant_device` | текущие/прошлые участники, ранг, состояние sender-key на уровне устройства |
| `group_membership_approval_requests`, `non_admin_group_membership_approval_requests` | ожидающие запросы на вступление, разделённые по видимости для одобряющего |
| `group_membership_form_questions` | настроенные администратором вопросы формы вступления (§11.1, §11.2) |
| `group_membership_count` | агрегированные счётчики |
| `subgroup_info`, `community_settings`, `group_relationship` | структура сообщества/подгруппы |
| `member_suggested_groups_v2` | поверхность предложенных групп |
| `group_suspension_appeal` | состояние апелляции на приостановку группы |
| `group_non_wa_invites` | приглашения контактам, не являющимся пользователями WhatsApp |
| `group_root_key_mapping` | маппинг корневого sender-key |

---

## 13. Примечания по реализации Baileys / velowa

Все MEX-операции группы/сообщества используют тот же конверт IQ `w:mex`, что и любой другой persisted query в этом репозитории (`Protocols/mex-graphql`, `graphql-invocation-guide.md`):

```js
const res = await sock.query({
  tag: 'iq', attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '<doc_id>' },
    content: Buffer.from(JSON.stringify({ queryId: '<doc_id>', variables })) }],
})
```

Устаревшее получение метаданных группы/участников остаётся на `w:g2` и уже реализовано в большинстве библиотек WA Web (вызовы вида `groupMetadata`, `groupQuery`); одобрение вступления требует явного добавления IQ из §11.2 — большинство библиотек его не запрашивают.

| Почему это не работает | Исправление |
|---------------|-----|
| Захардкоженный `doc_id` для любой операции группы/сообщества | `doc_id` меняется при каждой сборке APK (подтверждено: только между 2.26.38.10 и 2.26.41.6 поменялось 4 операции группы); обновлять из актуального извлечения каталога, не фиксировать |
| Предположение, что одобрение вступления всегда идёт через устаревший `w:g2` | Это управляется флагом; как только флаг включён на сервере для аккаунта, ожидающие запросы отображаются только через MEX `QueryMembershipApprovalRequests` — реализуйте оба пути или только MEX на будущее |
| Предположение, что у сообщества свой тип JID | Это не так — адресуйте его собственным JID `@g.us` родительской группы, как любую операцию с группой |
| Попытка программно отправить запрос на вступление с фильтрацией | Схема `JoinMembershipForm` не раскрыта (только предполагаемая роль); пока нельзя реализовать с уверенностью |

---

## 14. Ключевые различия

- **Сообщество — это классифицированная группа, а не отдельная сущность.** Нет `community_jid`; собственный JID сообщества — это JID группы с типом узла 1 (`parent`).
- **`member_share_group_history_mode`** (кто может делиться недавней историей с новыми участниками, [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md) §2.4) не связано с **`membership_approval_mode_enabled`** (фильтрация запросов на вступление, §9/§11) — оба являются полями `SetGroupProperty`, но управляют разными функциями.
- **Report-to-admin в `w:g2`** ([WA_REPORTING.md](WA_REPORTING.md) §9) и **резервный путь membership-approval-requests в `w:g2`** (§11.2) используют общее пространство имён, но это не связанные между собой дочерние узлы (`reports`/`allow_admin_reports` против `membership_approval_requests`).
- **`JoinMembershipForm`** — предполагаемая операция отправки, не подтверждённая — не считать её found.
- **Повышение/понижение/удаление участника** — в этом каталоге не выявлено MEX-операции; считать нерешённым, а не "идёт только через устаревший `w:g2`" (предположение, а не доказательство).

---

## 15. Поток одобрения вступления в сообщество (по текущим доказательствам)

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

## 16. Открытые вопросы / подводные камни

- Переменные/форма ответа `JoinMembershipForm`: unknown, точка вызова не трассирована.
- Собственные переменные `GroupMembershipRequestUpdate`: в этом проходе не восстановлены из точки вызова (подтверждено только существование операции).
- Повышение/понижение/удаление участника: MEX-операция не выявлена; "только устаревший путь" vs. "отсутствует в каталоге" не разрешено.
- `CreateCommunity`: такой MEX-операции не существует; путь создания сообщества не разрешён (рабочая гипотеза — клиентский мастер, сцепляющий `CreateGroup` + вызовы связывания, не подтверждена).
- Все утверждения в §11, кроме существования таблиц БД, — это статический анализ; ничто здесь не проверено трафиком (согласно контракту доказательств — для этого отчёта не выполнялось живое взаимодействие с сервером).
