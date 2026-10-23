<!-- src-sha1: e4fe5d62fca781d0449295a5d549413929d95191 -->
# WhatsApp Списки рассылки — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** классические списки рассылки и status-рассылки на Android: модель JID `@broadcast` (list / status / location), создание списка, лимиты участников и правила получателей, IQ `w:b` (получение списков, удаление списка, квота), app-state `business_broadcast_list`, миграция на LID, локальное хранилище, клонирование для каждого получателя при вставке, stanza отправки (sender-key fan-out, `phash`, `bucketing`, `<cap>`, эфемерные настройки по получателям), агрегация ack и receipt, месячная квота рассылок, баны за spam-warning, GAP, публикация в `status@broadcast` (`SendE2eStatusJob`, части, ручные buckets), режимы приватности status, близкие друзья и пользовательские аудитории, ответ на status / реакция / упоминание / notify, таблицы status, feature-флаги, сравнение с Baileys

---

## 1. Что это (технически)

Существуют три серверных JID `broadcast`. Все они являются «multi-participant» JID (`AbstractC20660pZ`, та же база, что у групп) и используют один конвейер отправки: отправитель шифрует один раз sender key и передаёт ключ каждому устройству получателя попарно. Все утверждения основаны на статическом анализе декомпилированного APK; на проводе ничего не перехватывалось. Tier: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не выяснено. Ничего здесь не **tested**. Обфусцированные имена заново определены в 2.26.41.6 по стабильным строкам (`BroadcastListManager/…`, `BroadcastXmppMethods/…`, `StatusParticipantUserManager/…`, `SendE2eStatusJob/…`, имена таблиц и prefs).

| Сущность | Форма JID | `Jid.getType()` | Класс | Роль |
|--------|----------|-----------------|-------|------|
| Классический список рассылки | `<id>@broadcast` | 3 | `C99P` | список основного устройства, получатели получают копии 1:1 |
| Status-рассылка | `status@broadcast` | 5 | `C199018dF` | публикации status, аудитория выбирается для каждой публикации |
| Рассылка геолокации | `location@broadcast` | 6 | `BOC` | есть в модели JID; использование не прослежено (live location выведено по имени) |
| Псевдопользователь собственного status | `status_me` (локальный) | 11 | `C0Dh` | локальный алиас, не JID на проводе (роль inferred) |

Вне области: newsletters (`SendNewsletterStatusJob` — отдельная задача), кампании и аналитика Business, Android OS broadcasts.

| Компонент | Имя в 2.26.41.6 | Роль |
|-----------|----------------|------|
| Парсер JID / хелперы | `C0DJ.A00` / `C0DZ.A0P`, `A0Q`, `A0h` | сервер `broadcast`: user `location` → `BOC`, `status` → `C199018dF`, иначе `C99P`; хелперы true для любого broadcast (3, 5, 6) / list (3) / status (5) |
| Аллокатор / менеджер списков | `C0YJ.A0E` / `A0K` (`BroadcastListManager`) | новый id списка / добавление и удаление участников |
| Фильтр и миграция LID | `C70552yj` (`BroadcastListLidMigrationHelper`), `C0UV` (задача миграции) | PN → LID |
| Менеджер / хранилище участников | `C22300su` (`A0j` добавление, `A0k` удаление), `C14850fN` (`ParticipantUserStore`) | общие с группами |
| IQ списков | `C18240lQ` (`BroadcastXmppMethods`), `AKU` (обработчик результата), `BroadcastListQuotaProtocol` + `C9EN` | получение списков, удаление списка, квота |
| Клиент квоты | `C720733k` (repository), `C2EX` (view model), `C74823Ej` (слушатель сообщений) | месячный лимит |
| Мутация app-state | `C224469lG` (dispatch), `C26057BNq` (`BusinessBroadcastListMutation`) | `business_broadcast_list` |
| Клонирование при вставке | `C231399zG` (`BroadcastCloneOnInsertProcessor`), `AJO` | локальные копии для каждого получателя |
| Ack / receipts | `C22500tF`, `C22790ti` (`MainMessageStore`), `C269411e` (`MessageStatusStore`) | серверный ack, разбор receipt |
| Шифратор / задачи | `F6P` (`E2eMessageEncryptor`), `SendE2EMessageJob`, `SendE2eStatusJob` | sender key, SKDM, сборка stanza |
| Верификатор входящих | `C34757F6a` (`CompanionSupportVerifier`) | отбрасывает копии списков на companion-устройствах |
| Аудитория status | `C11550Zh` (`StatusInfoStore`), `C182877r0` (информация о распространении), `C23140uH` (`StatusParticipantUserManager`), `C1889082i` (`StatusCustomListStore`), `C23340ub` (конфигурация bucketing) | режимы приватности, списки, buckets |
| Синхронизация приватности status | `C48386LBh` (`StatusPrivacySyncMutation`), `C49626LsR` (Wire `StatusPrivacyAction`), `M7H` (enum режимов) | действие app-state 44 |

---

## 2. Модель JID

### 2.1 Разбор (found)

| Правило | Значение |
|------|-------|
| Сервер | `broadcast` |
| User `status` / `location` | синглтоны `C199018dF` / `BOC` |
| Любой другой user | `C99P`: длина 1..20, первый символ `1`..`9`, остальные `0`..`9`, иначе выбрасывается `C09B` |

Правило отсутствия ведущего нуля прочитано в конструкторе `C99P` (smali сравнивает с `0x31`/`0x39`, остальные `0x30`..`0x39`). Список не относится к `g.us`, но использует механизм участников групп (3.5).

### 2.2 Выделение id (found, `C0YJ.A0E`)

Id — это `System.currentTimeMillis() / 1000`, за которым следует `@broadcast`; увеличивается на одну секунду, пока локально существует список с таким id. Уникальность проверяется только по локальному списку чатов; перед выделением нет обращения к серверу (IQ создания не существует, 3.3). Принимает ли сервер произвольный id, статически определить нельзя.

---

## 3. Жизненный цикл списка

### 3.1 Создание (found, частично inferred)

```
[Picker]  "New broadcast" (menu item hidden when BRD() = companion mode), max 256 selected
     ▼
createBroadcastList callback (C222519hZ):
     │   C0YJ.A0E()                                allocate <seconds>@broadcast
     │   A0K.A04(jid, users): C70552yj.A00 → LID filter ; C22300su.A0h → local participants ; contact entry (name "")
     ▼
compose flow opens; system message "You created broadcast list "X" with N recipients"
```

`A0K.A04` не отправляет IQ и не создаёт мутацию app-state (found). Первое видимое серверу событие — первая отправка на JID списка (4.2); то, что сервер выводит состояние списка из неё, — inferred. То же выделение id используется для приглашений подписчиков newsletter (`userActionSendNewsletterFollowerInviteMessages`, found).

### 3.2 Лимиты участников и правила получателей

| Правило | Значение | Tier |
|------|-------|------|
| Макс. получателей | 256: `ContactPickerFragmentKt.A39` отклоняет `selected.size() > 256` (`Broadcast to a maximum of %d people at a time`); граница picker `min(256, groupLimit - 1)` | found |
| Источник получателей | contact picker; текст разрешения `To create a broadcast … allow WhatsApp access to your contacts`; заблокированные контакты: `To add to broadcast list, unblock %s` | found |
| У получателя отправитель должен быть сохранён | только текст UI (`Only contacts who have you in their address book will receive your broadcast messages.`); проверка выполняется на сервере | found (текст), unknown (проверка) |
| Адресация LID | `A0K.A01` всегда возвращает `lid`; участники PN без соответствия LID отбрасываются (`lid-broadcast-filtered-participants`) | found |
| Отсутствует соответствие при отправке | `missing_pn_lid_mapping_for_broadcast`: клон пропускается, шифратор выбрасывает `E39(device, 4)` | found |
| Пустой набор участников | `saveGroupParticipants/broadcast_would_be_cleared`; при флаге **30111** (по умолчанию true) сохранённые участники остаются | found |

### 3.3 Серверные IQ (found)

Списков касаются только три IQ. IQ создания или редактирования нет.

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

Все три используют таймаут 32 с. `AKU` (результат get) для каждого `<list>` без локального чата или записи контакта создаёт чат (`A0K.A00`, системное сообщение типа 9) и запись контакта и сохраняет карты `pn_jid` и `username`. Delete отправляется через `C18240lQ.A01` и сопровождается app-state REMOVE (3.4).

Триггер восстановления (found): `RegistrationInitializer/shouldrefreshlists` устанавливает pref `refresh_broadcast_lists=true` и после регистрации отправляет get-lists (вместе с get-privacy-settings); `MessageHandlerCallback/ready` повторяет это, пока pref равен true; `AKU` сбрасывает его. Следовательно, сервер хранит списки для каждого аккаунта (found по следствию). Как он узнаёт о списке, на стороне клиента не видно (unknown, см. 3.1).

### 3.4 Мутация app-state (found)

| Элемент | Значение |
|------|-------|
| Действие | `BusinessBroadcastListAction`, имя на проводе `business_broadcast_list` (`EnumC24865AnN.A0H`, ordinal 62), поле `SyncActionValue` **69**, коллекция `regular`, версия API 7 |
| Индекс | `["business_broadcast_list", "<list jid>"]` |
| Операция | SET при добавлении, удалении, переименовании; REMOVE с `deleted=true`, пустыми participants, именем `""` при удалении списка (`A0T`, `syncBusinessBroadcastListRemoval`) |
| Условие | `C12440bB.A0b()` (syncd не заблокирован или companion-dirty); хуки Business (`storeForBroadcast`, `onAudienceChanged`, `getCustomAudienceFbidForBroadcast`) в этом APK отсутствуют |
| Вызывающие | `A0K.A03` / `A05` (добавление / удаление), переименование в `BroadcastListChatInfoActivity`, `C24085AaS` (набор участников) |
| Сторона применения | ни один обработчик не ссылается на `EnumC24865AnN.A0H`; существуют только writer (`C26057BNq`) и аксессор поля в `BD4`, поэтому поведение применения на стороне потребителя unknown |

| Поле | Номер | Тип | Значение / использование |
|-------|--------|------|-------------|
| `deleted` | **1** | bool | список удалён |
| `participants` | **2** | repeated `BroadcastListParticipant` | аудитория (`lid_jid` **1** обязательно, `pn_jid` **2**) |
| `list_name` | **3** | string | название |
| `label_ids` | **4** | repeated string | аудитория по меткам (альтернатива participants, никогда оба) |
| `audience_expression` | **5** | string | динамическая аудитория (Business) |
| `custom_audience_fbid` | **6** | string | только Business |

Та же коллекция: `BusinessBroadcastCampaignAction` (81), `BusinessBroadcastInsightsAction` (82), `MarketingMessageBroadcastAction` (39); только в enum: `BusinessBroadcastAssociationAction` (59) и `BusinessBroadcastAction` (94). Основы: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md).

### 3.5 Миграция LID, хранилище, companion-устройства

`BroadcastListLidMigrationTask` (`C0UV`) преобразует каждый список из участников PN в участников LID: один usync для недостающих LID (сбой логируется как `usync_failed`, задача продолжается), затем `C70552yj.A03` удаляет участников PN и добавляет набор LID в одной транзакции.

| Хранилище | Содержимое | Tier |
|-------|---------|------|
| `chat` / `chat_view`, `jid.type = 3`, `subject`, `created_timestamp`, `hidden` | чат списка (`C222989iV`) | found |
| `group_participant_user` (`group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `label`, `add_timestamp`), `group_participant_device` | получатели, общие с группами | found |
| `wa_group_admin_settings` (`jid`, `addressing_mode`, `group_state`) | режим адресации для каждого списка (телеметрия считает строки `@broadcast`) | found |
| столбцы `message`: `broadcast`, `recipient_count`, `participant_hash`, `key_id`, `chat_row_id`, `from_me` | данные сообщения списка и ack | found |
| `message_broadcast_ephemeral` (`message_row_id`, `shared_secret`) | секрет для каждого сообщения для исчезающих сообщений списка | found |

Companion-устройства (found): пункты меню `New broadcast` / `Broadcast lists` добавляются только если `BRD()` равно false; `C34757F6a` выбрасывает `E3A(415, "received peer broadcast message on companion-mode, dropping", 18)` для копии списка собственного аккаунта, содержащей `<participants>`; у действия 69 нет обработчика применения.

---

## 4. Отправка в список

### 4.1 Локальный fan-out (found, `C231399zG`)

```java
// A02(msg): msg.fromMe, not one of two excluded message classes, status 0 or 2 (or 4 with flag 26867)
msg.A0Z = true;                                   // message.broadcast = 1
for (recipient : msg.A0A())                       // recipient list stored on the FMessage
    normalized = lidMapper.A0C(recipient);        // null → missing_pn_lid_mapping_for_broadcast, skip
    store.add(cloneFactory.A00(msg, new C1ZA(normalized, msg.key.id, true)));   // own row in the recipient's 1:1 chat
```

| Свойство | Значение |
|----------|-------|
| Id сообщения | одинаков для сообщения списка и каждого клона (`key_id` копируется, отличается только чат) |
| Счётчики | `recipient_count` (`FMessage.A06`) в строке списка; счётчик ссылок на медиафайл увеличивается на число клонов |
| Дубликаты | `SQLiteConstraintException` по существующему ключу клона логируется и пропускается |
| Исчезающие сообщения | клон берёт настройку для получателя из эфемерной карты (ключ — основное устройство получателя); строки истечения в `message_ephemeral` |

### 4.2 Формат на проводе (found, частично inferred)

Одна stanza, адресованная на JID списка (пример, значения атрибутов иллюстративные). Шифрование использует путь групп (`F6P` типизирован на `AbstractC20660pZ`): один шифротекст sender key плюс попарные сообщения распространения sender key для каждого устройства. Основы sender key и сессий здесь не повторяются.

```xml
<message to="1760000000@broadcast" type="text" id="3EB0…" t="…" phash="2:AbCdEf==" addressing_mode="lid">
  <participants>
    <to jid="<recipient device jid>"><enc v="2" type="pkmsg|msg" …/></to>   <!-- SKDM wrapped pairwise -->
  </participants>
  <enc v="2" type="skmsg" …/>                                                <!-- message under the sender key -->
  <cap client_capping_ready="true|false"/>                                   <!-- flag 16656 only -->
</message>
```

| Атрибут | Источник | Примечания |
|-----------|--------|-------|
| `to`, `type`, `id`, `t` | JID чата (`C33150EcP.A07`), `AbstractC30999De0.A02`, `C1ZA.A01`, `originalTimestamp` | `to` — JID списка (inferred по общему builder); `t` только если не ноль |
| `phash` | `groupParticipantHash` | 4.3 |
| `bucketing` | `eva.A05` | `primcomp` при флаге **28183** и числе участников ≥ **28185** (512); списки (≤ 256) на практике остаются без значения (inferred) |
| `addressing_mode` | `lid` | опускается для JID типа 28 |
| `participant`, `recipient`, `recipient_pn`, `peer_recipient_pn`, `peer_recipient_username` | поля задачи | peer / retry / DSM отправки |
| `edit`, `expiration`, `device_fanout="false"`, `privacy_sensitive="1"` | поля задачи | опционально |

Дочерние элементы формируются contributors (`InterfaceC35538FaZ.ASY`, `processStanzaNodeParamsUsingNewFramework`). `F69` добавляет `<cap client_capping_ready="…"/>` для чатов списков при включённом флаге **16656**; значение берётся из флага **13537**.

| Шаг | Деталь | Tier |
|------|--------|------|
| Устройства получателей | набор менеджера участников минус типы устройств 26 / 27 (`F6P.A07`, hosted-устройства inferred); для чатов списков `AxolotlMultiDeviceSessionRequirement` добавляет собственные companion-устройства (`BPE`: собственный user, не основное) в целевой набор SKDM | found / inferred |
| Имя sender key | (адрес собственного устройства, строка `groupId` `A0J`); `A0J` записывается в `SenderKeyDistributionMessage.groupId`; статус `-1002` от `encryptForGroup` = недействительный sender key, ротируется | found |
| Эфемерные блоки для каждого получателя | `F6P.A0A` (`buildBroadcastListEphemeralSettings`): для каждого устройства получателя, отсутствующего в попарной карте (собственные companion-устройства пропускаются), строит `EphemeralSetting(expiration or afterReadDuration, timestamp)` и шифрует нативно с `shared_secret` сообщения (`JniBridge.jvidispatchOOOOOOO`); отсутствие настройки выбрасывает `E39(device, 4)`. Назначение (таймеры для каждого получателя внутри одной stanza) inferred | found / inferred |
| Собственные устройства | сообщение оборачивается в `DeviceSentMessage` с `destinationJid = list` и `phash` устройств получателей (`C33284Eea.A01`) | found |
| Размер | `BoundedStanzaSizeException` → `stanza-too-large` / `large payload` | found |

### 4.3 `phash` (found, `AbstractC44221r5`)

`<version>:` + base64 (`NO_WRAP`, padding сохраняется) первых 6 байт SHA-256 от отсортированных устройств получателей. Версия `2:` хеширует строки `user.0:device@server` (флаг **16731** false, по умолчанию); версия `3:` хеширует исходные строки устройств (флаг **16731** true). Используется для stanza групп, списков и status.

### 4.4 Ack и receipts (found)

| Событие | Обработка |
|-------|----------|
| Серверный ack | `C22500tF` → `C22790ti.A04`: для чатов списков (не status) обновляет `message`, где `chat_row_id IN (list chat, every clone chat) AND from_me = 1 AND key_id = ?`, полями `status`, `receipt_server_timestamp`, `recipient_count`; при списке получателей короче `recipient_count` переходит на сканирование по `timestamp/from_me/key_id` (`UPDATE_RCV_BROADCAST_SERVER_SQL`, лог `message-table-scan`) |
| Receipt получателя | `MessageStatusStore.splitStatusUpdateReceipts`: receipt для ключа списка сопоставляется с клоном `(normalized recipient, same id, fromMe)` и применяется к клону (`broadcast-individual`) и multi-сообщению; понижения статуса отбрасываются (`broadcast-statusdowngrade`); неизвестный клон логирует `nosuchmessage for broadcast` |

Правило итогового статуса строки списка и то, что показывает телефон получателя, не выяснены (unknown).

---

## 5. Лимиты и защита от злоупотреблений

### 5.1 Месячная квота рассылок (found, путь потребителя)

```
iq get xmlns=w:b smax_id=143
  → <limits is_heavy_sender="true|false" messages_left="N" total_limit="M"/>
    <timeframe start_ts_s="…" reset_ts_s="…" end_ts_s="…"/>
```

Проверки диапазона на клиенте: `messages_left` 0..300, `total_limit` 1..300, метки времени 2020-01-01..2100-01-01. Коды ошибок IQ отображаются в результаты клиента: `400` → 3, `401` → 4, `403` → 5, `500` → 1, прочие → 0, нет соединения или сбой доставки → 2 (`consumer_broadcast_capping_iq_error_response`).

| Механизм | Деталь |
|-----------|--------|
| Кэш | prefs `broadcast_quota_messages_left`, `_message_limit`, `_last_timestamp_fetched_ms`, `_heavy_sender`, `_start_timestamp`, `_end_timestamp`, `_reset_timestamp` |
| Обновление | когда время с последней загрузки превышает флаг **13818** минут (по умолчанию 1440) или now ≥ `reset_ts_s` (комбинация искажена в декомпиляции, OR inferred) |
| Уменьшение / увеличение | `C74823Ej`: для каждого добавленного сообщения списка с флагом `broadcast`, не входящего в исключённый набор типов сообщений (`C2EX.A00`), на сообщение, а не на получателя; увеличивается обратно при удалении неотправленных сообщений списка, не выше `total_limit` |
| Блокировка перед отправкой | предикат в `C20M`: чат списка и флаги **16585** и **13537** и `messages_left == 0` → отправка отклонена, bottom sheet `You've reached the broadcast limit for this month` |
| UI / телеметрия | `Send up to %d broadcasts per month`, onboarding sheet для heavy senders (`CappingBroadcastManager`); `wam_broadcast_list` (`blLimit`, `currentBlSends`, `numBlLists`, `broadcastListSize`) |

Значение лимита задаётся сервером; на клиенте есть только проверка диапазона. Хуки стороны Business (`isSmbPremiumBroadcastCappingEnabled`) в этом APK — заглушки.

### 5.2 Баны spam-warning (found)

`SpamWarningActivity` принимает серверный код (`spam_warning_reason_key`), `expiry_in_seconds`, необязательный серверный текст и URL FAQ. Коды: **101** сообщения людям, у которых отправителя нет в адресной книге, **102** слишком много блокировок, **103** группы с людьми, не сохранившими отправителя, **104** одинаковое сообщение слишком многим людям, **106** слишком много сообщений в список рассылки; остальные показывают общий бан за нарушение условий использования. Путь доставки и остальная поверхность банов: [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md). Пороги находятся на сервере (unknown).

### 5.3 Конфигурация 20278 и GAP

- Конфигурация **20278** существует только как строка по умолчанию `{"max_messages": 10000, "farthest_time_days": 30}` в двух таблицах значений по умолчанию. Других ссылок на `max_messages` / `farthest_time_days` в коде потребителя нет, поэтому читатель не найден. Это не лимит списков для потребителя (5.1); использование unknown (значение по умолчанию на стороне Business).
- GAP (`com.whatsapp.gapenforcement`, флаг **14837**, по умолчанию false) работает на стороне приёма: `GapEnforcementTrigger.onMarketingMessageReceived` и `RulesManager` оценивают правила inbox для тредов маркетинговых сообщений (`parseMaxMmThreadsInTopInboxSize`, `parseNoConsecutiveInTopInboxSize`, `parseMinNUpdatedP`) и логируют результаты точности; не запускается на companion-устройствах и не ограничивает отправку из списков. Расшифровки аббревиатуры в APK нет (unknown).

---

## 6. status@broadcast

### 6.1 Конвейер отправки (found)

У `SendE2eStatusJob` есть тип (`EnumC32060Dzj`): `STATUS` 0 (публикация, таблица `status`), `STATUS_ADD_ON` 1 (реакции и другие add-on, `status_add_on`), `STATUS_NOTIFY` 2 (уведомления об ответе / репосте / упоминании, `status_notify`). Stanza использует построитель атрибутов из 4.2 плюс contributors `<meta>` (пример, значения атрибутов иллюстративные):

```xml
<message to="status@broadcast" type="media" id="3EB0…" phash="2:…" bucketing="manual" addressing_mode="lid">
  <participants><to jid="<device>"><enc v="2" type="pkmsg|msg"/></to>…</participants>
  <enc v="2" type="skmsg" bucket="f1"/>                      <!-- one per bucket when bucketed -->
  <meta status_setting="contacts" session_scope="status"/>
</message>
```

| Атрибут | Допустимые значения (наборы значений stanza, `C9E2`) |
|-----------|---------------------------------------------|
| `status_setting` | `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist` |
| `content_type` | `add_on`, `status_notify` |
| `message_association_type` | `av1_video_dual_upload`, `hd_image_dual_upload`, `hd_video_dual_upload`, `hevc_video_dual_upload` |
| `interaction_type` | `question`, `question_reshare` (с `parent_server_id`, `response_server_id`) |
| `bucketing` | `manual`, `primcomp`, `threebuckets` (`threebuckets` только в наборе значений) |

| Элемент | Деталь |
|------|--------|
| Таймаут ack | 300000 мс (`no ack within 300000ms`) |
| Части | большие аудитории разбиваются: `status_send_part` (`status_row_id`, `part_code`, `is_first_part`, `device_count`, `state`, `sent_timestamp`, `ack_timestamp`, `error_code`, `stanza_devices_hash`); отслеживание устройств в `status_receipt_device` (`uuid`, `receipt_device_jid`, `receipt_device_timestamp`, `primary_device_version`, `part_code`) |
| Групповой status | `buildGroupStatus called with non-PermanentGroupJid`; `is_group_status`; поля Message 92 / 96 / 103 |
| Сбои сборки | `StatusStanzaBuildFailureReason`: `MISSING_RETRY_CIPHERTEXT`, `TARGETS_UNRESOLVABLE`, `PART_ATTEMPT_PERSISTENCE_FAILED`, `CANONICAL_ACK_PENDING`, `EMPTY_FANOUT`, `NON_CURRENT_BATCH`, `MISSING_SENDER_KEY_CIPHERTEXT`, `UNKNOWN` |
| Сбои задачи | `encryption_limit`, `out_of_memory`, `payload_too_large`, `stanza_error`, `stanza_too_large` (обрабатывается при включённом флаге **29113**), `unrecoverable_error` |

### 6.2 Аудитория: режимы приватности (found)

Аудитория определяется на стороне отправителя и разворачивается в явные устройства получателей; атрибут `status_setting` лишь маркирует режим. Локальное состояние: `C11550Zh` (prefs `status_distribution`, `status_distribution_modes`, `status_white_list`, `status_black_list`).

| Локальный режим | Название | `status_setting` | Wire `M7H` (app-state) |
|------------|------|------------------|------------------------|
| 0 | My contacts | `contacts` | `CONTACTS` 2 |
| 1 | Only share with | `allowlist` | `ALLOW_LIST` 0 |
| 2 | My contacts except | `denylist` | `DENY_LIST` 1 |
| 3 | запасное значение `C182877r0.A01()` при отсутствии настройки; отклоняется мутацией синхронизации (`StatusPrivacySyncMutation invalid status setting`) | | |
| 4 | пользовательская аудитория / близкие друзья | `customlist` / `closefriends` (inferred) | `CUSTOM_LIST` 4 (`CLOSE_FRIENDS` 3 есть в enum, не используется) |

Отображение локального режима на wire (found, `C48386LBh.A04`): 1 → 0, 2 → 1, 4 → 4, иначе 2. Имена режимов 0..2 также логируются задачей отправки как `contacts` / `allowlist` / `denylist`.

Серверные списки приватности используют IQ `privacy`, категория `status` (имя категории из `AboutStatusPrivacyActivity`):

```xml
<iq to="s.whatsapp.net" xmlns="privacy" type="get" id="…">
  <privacy addressing_mode="lid"><list name="status" value="contact_allowlist|contact_blacklist" dhash="…"/></privacy>
</iq>
<iq xmlns="privacy" type="set"><privacy><category name="status" value="contacts|contact_blacklist|contact_allowlist"/></privacy></iq>
```

(`AbstractC230749y7.A02`, `C228009tS`, `C18260lS.A0P`; get идёт через MEX / SMAX / shadow по флагу **23463**, set — через MEX при **23639**, иначе SMAX.)

### 6.3 Пользовательские аудитории и близкие друзья (found)

Строки UI: `New: Close friends`, `People you include see a purple ring on your status`, `Create audience`, `Choose name & emoji`.

| Элемент | Значение |
|------|-------|
| Таблица `status_privacy_custom_list` | `row_id` (PK), `list_id` (unique), `name`, `emoji`, `is_selected` (по умолчанию 0), `member_jids`, `source_group_jids`, `allow_list_selected`; хранится и в хранилище сообщений, и в хранилище status (`*_MSGSTORE_DB`, `*_STATUS_DB`) |
| App-state | `status_privacy` (ordinal 38, `regular_high`, поле **44**); `StatusPrivacyAction`: `mode` **1**, `user_jid` **2**, `shareToFB` **3**, `shareToIG` **4**, `custom_lists` **5**, `modes` **6**; `StatusCustomList`: `list_id` **1**, `name` **2**, `emoji` **3**, `is_selected` **4**, `user_jid` **5** |
| Запись для каждой публикации | `status_message_info`: `status_distribution_mode`, `selected_audience_list`, `audience_type`, `status_audience_custom_list_name`, `_emoji` |
| Валидация | `StatusParticipantUserManager/validateAudience` (включает проверку `HAS_STATUS_AUDIENCE` по `wa_contacts`), `StatusEmptyAudienceGuard` в композерах |

Связанное: `userStatusMute` (ordinal 23, поле 29, `muted`). Несколько одновременных режимов требуют флага **28731**, хранилище пользовательских списков — **27031** (оба по умолчанию false; хелперы status-config `A0F` / `A0I` также управляют этим, не выяснено).

### 6.4 Ручные buckets sender key (found)

| Элемент | Деталь |
|------|--------|
| Таблица `manual_user_group_bucket` | `row_id`, `user_jid_row_id`, `multi_participant_jid_row_id`, `status_audience`, `bucket`; уникальный индекс по user + group |
| Имена аудиторий / префиксы buckets | `contacts` → `c`, `close_friends` → `f`, `allow_list` → `a`, `close_friends:<id>` → производный префикс; другие имена выбрасывают `Unknown manual SKB audience name` |
| Хранилище / планирование | `ManualBucketStore/assignUsersToBuckets`, `deleteRowsForBuckets`, `getHoldersByBucketForGroup`; `ManualBucketingUtils/planSend`, `trimToEncBudget`; `SenderKeyBucketingRollback/cleanupBucketedState` |
| Флаги | **28184** + предел rollout **34545** (0 = все) включают ручной bucketing для status (`C23340ub.A01`) |

### 6.5 Ответ, реакция, упоминание, notify (found)

| Взаимодействие | Механизм |
|-------------|-----------|
| Ответ | обычное сообщение 1:1 с цитированием status (`status_reply`: `status_row_id`, `ref_id`, `reply_timestamp`); `Message.statusQuotedMessage` (поле **109**) для ответов на вопросы |
| Реакция / add-on | тип задачи `STATUS_ADD_ON`; `status_add_on` (`status_row_id`, `type`, `uuid`, `sender_user_jid`, `state`, `sender_timestamp`, `is_revoked`, `content_proto`, `secret`); условия для каждой публикации `cannot_receive_reactions`, `can_receive_multi_reactions` |
| Упоминание | `status_message_info.is_mentioned`, `status_mentions`, `status_mention_source`; `Message.statusMentionMessage` (поле **87**) — обёртка из одного поля (`message` **1**), разворачивается как `viewOnceMessage` (`C35228FOg`); дальнейшая семантика inferred |
| Notify | `Message.statusNotificationMessage` (поле **98**): `responseMessageKey` **1**, `originalMessageKey` **2**, `type` **3** (1 add yours, 2 reshare, 3 question-answer reshare, 4 group status reply); хранится в `status_notify` |
| Связанные поля | `groupStatusMentionMessage` **92**, `groupStatusMessage` **96**, `groupStatusMessageV2` **103**, `statusQuestionAnswerMessage` **105**, `statusStickerInteractionMessage` **110** |

### 6.6 Хранилище status (found)

| Таблица | Ключевые столбцы |
|-------|-------------|
| `status` (хранилище status) | `uuid`, `sender_user_jid`, `status_info_row_id`, `type`, `timestamp`, `server_receipt_timestamp`, `state`, `secret`, `content_proto`, `origin`, `flags`, `audience_type`, `stanza_xml`, `batch_state` |
| `status` (хранилище сообщений, устаревшая сводка), `status_info` | `jid_row_id` / `chat_jid`, `unseen_count` / `unread_count`, `total_count`, `unread_count_close_friends` |
| `status_message_info` | `message_row_id`, `status_distribution_mode` (3 при отсутствии значения), условия упоминаний / реакций / репостов, `is_group_status`, `ranking_version`, столбцы аудитории (6.3) |
| `status_send_part`, `status_receipt_device`, `manual_user_group_bucket` | состояние отправки (6.1, 6.4) |

Две таблицы с именем `status` имеют непересекающиеся столбцы и находятся в разных базах данных (inferred по меткам `MSGSTORE_DB` / `STATUS_DB`). Прочие таблицы (`status_media_link`, `status_seen_receipt`, `status_ranking*`, `status_interactions*`) перечислены только по имени.

---

## 7. Feature-флаги

Id — как прочитано в местах вызова; значения по умолчанию — из скомпилированных таблиц значений по умолчанию.

| ID | По умолчанию | Управляет |
|----|---------|----------|
| **13537** | false | capping рассылок для потребителя: главная списков, загрузка / уменьшение квоты, значение `client_capping_ready` |
| **16585** | true | блокировка отправки в списки при `messages_left == 0` |
| **16656** | false | добавляет `<cap client_capping_ready/>` в stanza списков |
| **13818** | 1440 | интервал обновления квоты (минуты) |
| **15515** | true | UI-хелпер capping (`C33z.A08`, вместе с 13537) |
| **19790** | false | при true клонирование при вставке пропускает сопоставление цитируемых сообщений |
| **26867** | true | ветка клонирования при вставке для отправленных сообщений со status 4 (смысл не выяснен) |
| **30111** | true | сохранять участников списка, когда сохранение их очистило бы |
| **16731** | false | вариант `phash` `3:` вместо `2:` |
| **28183** / **28184** | false / false | главный переключатель bucketing `primcomp` / ручной bucketing status |
| **28185** / **28199** / **34545** | 512 / 2 / 0 | порог участников bucketing / второе целое (не выяснено) / предел rollout |
| **28731** / **27031** | false / false | несколько режимов status / хранилище пользовательских списков |
| **29113** | false | обработка слишком большой stanza для status |
| **23463** / **23639** / **23874** | 0 / false / false | протокол privacy get (1 MEX, 2 shadow, иначе SMAX) / privacy set через MEX / путь загрузки списка privacy |
| **14837** | false | GAP enforcement |
| **20278** (string) | `{"max_messages": 10000, "farthest_time_days": 30}` | значение по умолчанию лимита рассылок Business, читателя на стороне потребителя нет |

---

## 8. Baileys (`baron-baileys-v2`, проверено по его исходному коду)

| Область | Реализация | Вердикт относительно 2.26.41.6 |
|------|----------------|---------------------------|
| Отправка status | `messages-send.js`: `isStatus`, `statusJidList` добавляется к списку участников, `<meta status_setting session_scope="status">` | совпадает с 6.1 / 6.2; `statusPrivacy` не валидируется (допустимые: `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist`) |
| Масштаб аудитории | явный `statusJidList`, без buckets, без атрибута `bucketing` | большие аудитории упираются в лимиты stanza (6.1) |
| Удаление списка | `deleteBroadcastList`: `w:b` set, `<delete><list id/></delete>` | совпадает с 3.3 |
| Квота | `fetchBroadcastListQuota`: `xmlns="w:biz"` с дочерним `<broadcast_list_quota/>` | запрос не совпадает (`w:b`, `smax_id=143`, без дочернего элемента); разбор ответа совпадает |
| Получение списков / app-state / отправка в список | не реализовано / `businessBroadcastListAction` отправляется как `settings.update` / `isJidBroadcast` только для декодирования | см. ниже |

| Симптом | Причина | Исправление |
|---------|-------|-----|
| отправка в классический список отбрасывается или отклоняется | списки — состояние основного устройства: companion-устройства скрывают функцию, отбрасывают копии списков собственного аккаунта с `participants` (415), IQ создания не существует | не адресовать JID списков с companion-устройства; отправлять сообщения 1:1 каждому получателю или использовать `status@broadcast` с `statusJidList` |
| получатели не определяются | на companion-устройствах нет поиска участников списков; участники адресуются через LID и фильтруются по соответствию | сначала определить LID через usync |
| ошибки запроса квоты | неверный namespace | `xmlns="w:b"`, `smax_id` 143, `type="get"`, `to="s.whatsapp.net"` |

Отдельные отправки 1:1 совместимы по транспорту, но не являются классическим списком (нет чата списка, общего id или квоты).

---

## 9. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|-------|-----|
| `missing_pn_lid_mapping_for_broadcast`, `lid-broadcast-filtered-participants` | у PN получателя нет соответствия LID | получить LID (usync) перед добавлением или отправкой |
| 415 `received peer broadcast message on companion-mode` | копия списка с `participants` на companion-устройстве | ожидаемо, companion-устройства не обрабатывают отправки в списки |
| отправка заблокирована, sheet лимита | `messages_left == 0` при 13537 и 16585 | дождаться `reset_ts_s`, удалить неотправленные сообщения списка |
| код бана 106 | слишком много сообщений в список рассылки | дождаться `expiry_in_seconds` |
| `broadcast_would_be_cleared` | сохранение участников с пустым набором | флаг 30111 сохраняет участников |
| `EMPTY_FANOUT` | аудитория разрешилась в ноль устройств | исправить аудиторию, `StatusEmptyAudienceGuard` должен блокировать раньше |
| `stanza_too_large`, `payload_too_large` | слишком много устройств или слишком большой payload | части / buckets (6.1, 6.4), флаг 29113 |

---

## 10. Ключевые различия

| Не путать | Различие |
|----------------|------------|
| Список (тип 3) и `status@broadcast` (тип 5) | список: сохранённые получатели, клоны для каждого получателя, месячная квота; status: аудитория для каждой публикации, без клонов, собственные таблицы |
| Список и группа | то же хранилище участников и путь sender key; список только для основного устройства, получатели не являются участниками и видят чаты 1:1 |
| Серверные списки `w:b` и действие app-state 69 | `w:b` восстанавливает списки после регистрации; действие 69 записывается для синхронизации и не имеет обработчика применения на стороне потребителя |
| Квота (`w:b` smax 143, ≤ 300) и конфигурация 20278 (10 000 / 30 дней) | квота задаётся сервером и контролируется в UI; у 20278 нет читателя на стороне потребителя |
| Квота, код бана 106 и GAP | мягкий лимит с UI / временный бан, выдаваемый сервером / правила inbox на стороне приёма |
| IQ `privacy` и пользовательские аудитории | IQ хранит три серверных режима; пользовательские списки и близкие друзья — локально плюс действие app-state 44 |

---

## 11. Полный поток

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

## 12. Неизвестное

| Элемент | Статус |
|------|--------|
| Как сервер регистрирует список (существуют только IQ get / delete / quota) | регистрация при отправке inferred |
| Серверное правило, что у получателей должен быть сохранён отправитель; размер списка и значения квоты | на стороне сервера (только текст UI и проверки диапазона) |
| Поведение применения действия app-state 69 на стороне потребителя | обработчик не найден |
| Что получатели получают при сообщении в список; правило итогового receipt строки списка | не видно со стороны отправителя |
| Комбинация обновления квоты, исключённый набор типов сообщений | декомпиляция искажена / не прослежено |
| Локальный режим status 3, `threebuckets`, флаги 28199, 26867, 15515, status-config `A0F` / `A0I` | не выяснено |
| Использование `location@broadcast`; расшифровка «GAP» | не прослежено / нет в APK |
| Трафик | ничего не перехвачено |
