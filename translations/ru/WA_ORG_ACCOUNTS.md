<!-- src-sha1: 5fa1223d0cb214989ef32453299c247d3ee92ecf -->
# WhatsApp Корпоративные аккаунты (Org Accounts) — Full RE Report
**Версия:** 2.26.45.10 | **Дата:** 2026-11-15
**Область:** модель сущности org-аккаунта (org_id, справочник участников, таксономия member-tag/team), поток вступления по ссылке-приглашению, проверка доступности отображаемого имени, онбординг с подтверждением email (OTP), каталог операций `GraphQlOrgApi`/`OrgEmailCodeClient` (9 операций, `www` + `mex`), различие от Managed Account и от делегирования WhatsApp Business API, примечания по реализации Baileys/velowa

---

## 1. Что такое org-аккаунт

Все утверждения — статический анализ декомпилированного APK. Уровень: **found** = буквальное чтение строки/поля в точке вызова, **inferred** = выведено из формы кода без трассировки сквозного вызова, **unknown** = не разрешено.

"Org" (внутреннее название повсюду, ни в одной прочитанной строке не раскрывается как "organization") — это сущность членства со своей собственной идентичностью, присоединяемым справочником участников и путём онбординга "ссылка-приглашение + email-OTP", полностью отдельная от собственной регистрации аккаунта по номеру телефона и от двух других похожих на "managed" систем, уже описанных в этом репозитории (раздел 7).

| Сущность | Внутреннее имя | Поля (found) | Роль |
|---|---|---|---|
| Идентичность org | `org_id` | `org_id`, `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` | сама org, разрешённая из ссылки-приглашения |
| Ссылка-приглашение | `link_token` | передаётся сквозным образом от referrer/deep-link до финальной мутации вступления | credential для вступления, вероятно одноразовый(?); точный срок жизни `unknown` |
| Идентичность участника внутри org | `display_name` (+ опциональное `display_last_name`), `member_tag` | отображаемое имя участника, подлежащее собственной проверке доступности/политики, независимо от основного имени профиля аккаунта | как участник отображается в справочнике org |
| Таксономия команды/роли | `team`, `team_options`, `selected_team` | найдены как поля состояния; семантика отдельных значений team не раскрыта | группировка участников внутри org |
| Отношение справочника | `relationship` (`OrgDirectory`), единственное наблюдаемое значение `"CONTACT"` | — | единственное наблюдаемое значение фильтра отношений; другие маппинги ordinal→string — `unknown` |

Все эти имена полей читаются буквально как литералы `const-string` непосредственно перед вызовом сеттера `GraphQlCallInput`/`LX/0jN` в `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali` и `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali` (2.26.45.10), плюс список полей объекта состояния `OrgJoinViewModel` — всё **found**. Порядок шагов, связывающий эти операции в поток (раздел 3), является **inferred**, выведенным из того, как выстраиваются поля состояния, а не из единой трассированной последовательности вызовов.

---

## 2. Каталог операций

9 операций в двух транспортах, все в `com.whatsapp.orgs`. 7 на `www` (`GraphQlOrgApi`, GraphQL с persisted-doc_id через `Lcom/facebook/pando/TreeWithGraphQL`), 2 на `mex` (`OrgEmailCodeClient`). Переменные во всех строках ниже — **found** из точки вызова.

| Операция | Транспорт | doc_id (2.26.45.10) | Тип | Переменные | Назначение |
|---|---|---|---|---|---|
| `OrgInvitePreview` | www | `29166886682947630` | Query | `link_token` | предпросмотр org (имя/иконка/число участников) до подтверждения вступления |
| `OrgCheckDisplayName` | www | `28738875225734024` | Query | `display_name` | проверка доступности/политики отображаемого имени участника внутри org |
| `OrgCheckEmailEligibility` | www | `28705126895811065` | Query | `link_token`, `email` | можно ли использовать этот email для данного конкретного приглашения в org |
| `OrgSendEmailCode` | mex | `28659396457057459` | Mutation | `email` | отправка email OTP |
| `OrgVerifyEmailCode` | mex | `29096159596657036` | Mutation | `email`, `code` | проверка email OTP |
| `OrgJoin` | www | `29366364109633604` | Mutation | `link_token`, `email`, `org_display_name`, `member_tag`, `org_display_last_name` | финальная отправка вступления |
| `OrgDirectory` | www | `28698253656512395` (ротация от `28049955604655823` в 2.26.41.6) | Query | `org_id`, `relationship` (наблюдалось только `"CONTACT"`), `first`, `after` | постраничный справочник участников, после вступления |
| `OrgMemberSearch` | www | `39884553687825642` (ротация от `28199835469697557`) | Query | `query`, `org_id`, `first`, `after` | поиск по справочнику участников |
| `OrgLeaveMutation` | www | `28491454287217875` | Mutation | `org_id` | выход из org, в любой момент после вступления |
| `OrgList` | www | `28999557569709709` (ротация от `27920891847589435`) | Query | `unknown` (точка вызова статически не найдена, кроме doc_id/ротации) | список org, в которых состоит аккаунт |

Все 7 операций `www` находятся в одном классе, `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`; обе операции `mex` — в `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`. Пространство имён/схема для операций `www` — `whatsapp-android-www`; для операций `mex` — `whatsapp-android-mex`. `OrgDirectory`/`OrgList`/`OrgMemberSearch` существовали до 2.26.45.10 (впервые зафиксированы на 2.26.41.6); их doc_id поменялись между двумя сборками (тот же класс, те же имена полей) — остальные 7 новые в 2.26.45.10.

Вспомогательные операции поиска существуют в соседнем пакете, `com/whatsapp/work/publicidentity/` — не являются частью самого потока вступления, но это способ, которым клиент другого участника узнаёт о принадлежности кого-то к org вообще, ещё до какого-либо приглашения:

| Операция | Транспорт | doc_id | Переменные | Назначение |
|---|---|---|---|---|
| `WorkPublicContactInfoQuery` | www | `29154186964216430` | `lids` (список) | статус work/business-аккаунта по каждому контакту, пакетно (`CoalescingBatcher`, с дебаунсом, максимум 100 ключей за раунд) |
| `WorkPublicOrgInfoQuery` | www | `28899689926378846` | `ids` (список, идентификаторы org) | публичная информация об org (`id`, `name`, 2 дополнительных непрозрачных строковых поля — `inferred`: логотип/домен) для org, в которых состоит контакт |

---

## 3. Сквозной поток вступления

**Inferred** порядок, собранный из имён полей объекта состояния `OrgJoinViewModel` (ни одна единая трассированная последовательность вызовов не покрывает это сквозным образом):

### 3.1 Вход

Приглашение приходит в виде токена ссылки, либо через referrer/deep-link (`OrgInviteReferrerOpener`, литерал `org_invite_token_from_referrer` → становится `link_token`), либо открывается напрямую (`OrgInviteLandingActivity`, с состояниями отказа `org_invite_landing_failure` / `org_invite_landing_already_in_org`).

### 3.2 Предпросмотр

`OrgInvitePreview(link_token)` возвращает достаточно данных для заполнения `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` до того, как пользователь что-либо подтвердит.

### 3.3 Проверка отображаемого имени

`OrgJoinActivity`/`OrgJoinViewModel` собирает `display_name` (+ опциональное `display_last_name`) и выбор команды (`team`/`team_options`/`selected_team`). `OrgCheckDisplayName(display_name)` — проверка политики/доступности; при отказе вложенное продолжение `OrgJoinViewModel$checkName$2` устанавливает `name_refusal` и/или `last_name_refused` независимо друг от друга — имя и фамилия могут быть отклонены каждая по отдельности.

### 3.4 Проверка пригодности email и OTP

`OrgCheckEmailEligibility(link_token, email)` проверяет, может ли данный email быть использован для этого конкретного приглашения. `OrgSendEmailCode(email)` (mex) затем отправляет OTP; после того как пользователь его вводит, `OrgVerifyEmailCode(email, code)` (mex) проверяет его. Верификация может выдать `username_pending_email` / `rejoin_after_username` / `username_screen_open` — вступление может быть заблокировано до завершения настройки username основного аккаунта, зависимость от системы `WA_USERNAME.md`, в остальном не связанной с org.

### 3.5 Вступление

`OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)` — финальная отправка. При успехе устанавливается `joined=true` и заполняются поля org (`org_id`, `org_name`, `org_member_count`, `org_icon_*`, `org_description`) в локальном состоянии.

### 3.6 После вступления

`OrgDirectory(org_id, relationship="CONTACT", first, after)` получает справочник участников; `OrgMemberSearch(query, org_id, first, after)` ищет по нему. `OrgLeaveMutation(org_id)` выполняет выход в любой момент после вступления.

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

## 4. Ключевые различия — не путать

В этом клиенте и вокруг него существуют три не связанных друг с другом концепции "структуры аккаунта". Они не имеют общего кода, общего proto, общего пространства doc_id.

| | Org Accounts (этот отчёт) | Managed Account (`WA_MANAGED_ACCOUNT.md`) | Делегирование Business API (BSP/Cloud API) |
|---|---|---|---|
| Идентичность сущности | `org_id`, собственный справочник | `ManagedAccountConnection`, с ключом `connectionLid`/`connectionPnJid` | поля сертификата verified-name (`host_storage`/`actual_actors`), без нового идентификатора сущности |
| Отношение | добровольное вступление по ссылке-приглашению, N участников на org | один спонсор ↔ один подопечный, связь супервизии | бизнес-номер, управляемый Meta/провайдером через Cloud API |
| Онбординг | ссылка-приглашение + email OTP + проверка доступности отображаемого имени | deep link + связывание, инициированное спонсором (`ManagedAccountInitiateLinkingQuery` и т.д.) | серверное провижининг на бизнес-платформе Meta; невидимо для этого клиента, кроме итоговых маркеров |
| Расположение кода | `com.whatsapp.orgs.*` | `com.whatsapp.managedaccount.*` / `pma.*` / `pmta.*` | нет отдельного пакета; сигнализируется через поля сертификата `w:biz` и тип аккаунта multi-device `HOSTED` |
| Транспорт | GraphQL `whatsapp-android-www` + `whatsapp-android-mex` (OTP) | только `whatsapp-android-mex` | поля стансы `w:biz`, вообще не протокол вступления/приглашения |
| Выход/отвязка | `OrgLeaveMutation(org_id)` | `ManagedAccountRevokeLinkingMutation` | не применимо — нет вступления/выхода на уровне аккаунта; сам номер провижинится/депровижинится на сервере |
| Концепция справочника | да — `OrgDirectory`/`OrgMemberSearch`, с ограничением по отношению | нет | нет |

Ни одна из трёх систем не является переименованием или эволюцией другой: у org-аккаунта нет семантики супервизии (нет состояния возраста/выпуска, нет PIN спонсора) и нет семантики бизнес-сертификата (нет `host_storage`/`actual_actors`, нет проверки префикса эмитента); это простая, добровольная модель членства со справочником, наложенная на уже зарегистрированный аккаунт WhatsApp. Продуктовый вывод о названии ("собственная функция WhatsApp для организаций компаний/учреждений") — **inferred** только из формы полей (`org_id` + справочник участников + проверка доступности отображаемого имени + верификация домена email) — никакой маркетинговый или внутриклиентский текст, называющий эту функцию, не был прочитан.

---

## 5. Случаи ошибок

В этой сборке по точкам вызова не удалось построить таблицу кодов ошибок — для всех 9 операций в этом проходе не найдено литералов формы ответа (имена полей успеха/неудачи, числовые коды ошибок). Единственные прочитанные сигналы отказа — два булевых поля состояния в `OrgJoinViewModel$checkName$2`:

| Симптом | Причина | Доказательство |
|---|---|---|
| Отображаемое имя отклонено | отказ проверки политики/доступности `OrgCheckDisplayName` | устанавливается `name_refusal` (found, поле состояния) |
| Фамилия отклонена независимо от имени | та же проверка, ветка специфичная для фамилии | устанавливается `last_name_refused` (found, поле состояния) |
| Вступление заблокировано в ожидании настройки username | успех `OrgVerifyEmailCode` блокируется состоянием username собственного аккаунта | `username_pending_email`/`rejoin_after_username`/`username_screen_open` (found, поля состояния; точное серверное условие `unknown`) |
| Приглашение открыто при уже имеющемся членстве | срабатывание проверки на странице перехода | `org_invite_landing_already_in_org` (found, строковый литерал) |
| Ссылка-приглашение недействительна/истекла | общий отказ страницы перехода | `org_invite_landing_failure` (found, строковый литерал; отдельная под-причина не найдена) |

---

## 6. Примечания по реализации Baileys / velowa

Все 9 операций — стандартные вызовы persisted-doc_id GraphQL/MEX в тех же пространствах имён `whatsapp-android-www`/`whatsapp-android-mex`, которые velowa уже реализует для других функций (username, группы) — не найдено ни нового транспорта, ни нативного криптографического слоя, специфичного для org.

| Готово для передачи по проводу | Не готово для передачи по проводу |
|---|---|
| Все 9 имён операций + doc_id + ключи переменных (раздел 2) — достаточно, чтобы сформировать запрос | Имена полей ответа неизвестны для каждой операции, кроме четырёх, явно читаемых в состояние `OrgJoinViewModel` (раздел 1); клиент должен считать все ответы непрозрачным JSON, пока живой захват не подтвердит формы |
| Путь распространения `link_token` (referrer → предпросмотр → вступление) | Точное управление шагами — соблюдает ли сервер порядок из раздела 3, или, например, можно пропустить `OrgCheckDisplayName`/`OrgCheckEmailEligibility` — это `inferred`, не подтверждено |
| Форма пагинации `OrgDirectory`/`OrgMemberSearch` (`first`/`after`, стандартный паттерн курсора) | Enum `relationship`: подтверждено только `"CONTACT"`; другие возможные значения `unknown`, так что клиент не должен считать это единственным допустимым фильтром |
| `OrgLeaveMutation(org_id)` — мутация с одним полем, тривиально реализуемая | Переменные `OrgList` целиком (точка вызова не найдена — вероятно отправляется `{}`, не подтверждено) |
| `WorkPublicContactInfoQuery`/`WorkPublicOrgInfoQuery` для поисков только на чтение "состоит ли этот контакт в org", независимо от потока вступления | Сам формат URL ссылки-приглашения/deep-link (хост, путь, кодирование токена) — не захвачен в этом проходе |

Реализация velowa, пытающаяся воспроизвести этот поток, должна ожидать эмпирического обнаружения форм ответа на живом аккаунте — та же оговорка, что уже сопровождает другие отчёты с `inferred`-транспортом в этом репозитории (например, `WA_USERNAME.md`).

---

## 7. Неизвестное

| Тема | Причина |
|---|---|
| Переменные `OrgList` | точка вызова статически не найдена, кроме doc_id + ротации; вероятно `{}`, но не подтверждено |
| Значения enum `relationship`, отличные от `"CONTACT"` | наблюдался только один маппинг ordinal→string (ordinal 0 → `"CONTACT"`); другие ветки этим проходом не покрыты |
| Формы полей ответа для всех 9 операций | на стороне ответа ни в одной точке вызова не найдено литералов/имён полей; всё, кроме полей состояния `OrgJoinViewModel`, непрозрачно |
| Срок жизни/семантика одноразовости `link_token` | не трассировано; одноразовость предполагается только по соглашению об именовании |
| Серверное принуждение к порядку шагов из раздела 3 | собрано из формы полей состояния, а не из трассированной последовательной цепочки вызовов — клиент потенциально может переставить или пропустить шаги; не проверено |
| Наборы значений `member_tag`/`team` | поля существуют (`team_options`, `member_tag`), но перечисленные значения не найдены |
| Формат URL ссылки-приглашения | не захвачен в этом проходе |

---

## 8. Доказательства

Статический анализ smali WhatsApp Android 2.26.45.10, все литералы и ключи переменных прочитаны как `const-string` непосредственно перед вызовом их сеттера `GraphQlCallInput`/`LX/0jN`. Перехвата трафика не производилось; все утверждения о транспорте/форме ответа — `inferred`. Источник: `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`, `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`, `com/whatsapp/orgs/ui/join/OrgJoinActivity.smali`, `OrgJoinViewModel.smali`, `OrgJoinViewModel$checkName$2.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteReferrerOpener.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteLandingActivity.smali`, `com/whatsapp/work/publicidentity/graphql/MexWorkIdentityTransport.smali`.
