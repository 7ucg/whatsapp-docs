<!-- src-sha1: 8d1c772149420abe245fd6a70c2b6615d2ab4fc5 -->
# WhatsApp Interop — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** взаимодействие с чатами сторонних мессенджеров на Android (в стиле DMA): гейтинг функции и AB-флаги, уведомление о согласии и opt-in, список интеграторов, домены interop JID и бинарный тег JID, обнаружение пользователей (`w:interop` FetchUsers), `w:interop` IQ set, ограниченный plaintext `InteropMessage` и поддерживаемые типы сообщений, отличия в шифровании и stanza, interop-группы (MEX-операции, уведомления, add-privacy), ping доступности, блокировка и жалоба, хранилище, случаи ошибок, отличия от нативных чатов, сравнение с Baileys

---

## 1. Что это (технически)

Interop позволяет аккаунту WhatsApp обмениваться личными и групповыми сообщениями с аккаунтами других мессенджеров («интеграторов»). Клиент никогда не обращается к этим приложениям напрямую. Он общается с серверами WhatsApp, которые представляют каждый сторонний аккаунт как синтетический JID в домене `interop` (группы: `interop.g.us`). Все утверждения получены статическим анализом декомпилированного APK; ничего не перехватывалось в сети и не запускалось против сервера. Уровни: **found** = прочитано в коде или ресурсах, **inferred** = выведено из кода, **unknown** = не выяснено. Обфусцированные имена уникальны для каждой сборки и заново определены в 2.26.41.6 по стабильным строкам (`InteropOptInManager/`, `InteropChatMessageHandler/`, `IntegratorManager/`, `w:interop`, `integrator_display_name`, `xwa2_interop_*`).

Состояние в этой сборке:

| Часть | Состояние в 2.26.41.6 |
|------|--------------------|
| Код | **Присутствует и полный**: UI (10 activity плюс фрагменты и диалоги), IQ-клиент, MEX-операции групп и privacy, строгий конвейер приёма, хранилище, обработчик уведомлений |
| Серверный переключатель | **По умолчанию выключен**: корневой AB-флаг **7495** по умолчанию `false`; каждый interop-флаг, читаемый в коде, по умолчанию `false` (раздел 2) |
| Регион | Текст продукта ограничивает функцию пользователями с номером телефона европейского региона; **проверка страны на стороне клиента не найдена** (принудительное применение предположительно на сервере, через флаг 7495 и список интеграторов; inferred) |
| Интеграторы | **Не зашиты в код**: ни имени интегратора, ни фиксированного id интегратора в коде, ресурсах или assets; список приходит с сервера (раздел 4) |

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| Гейт (`InteropRolloutManager`, имя выведено из getter; inferred) | `C32001Oa` | `A01` допустим, `A02` допустим и основное устройство, `A00` группы, `A03` единый inbox |
| IQ-клиент / построители / парсеры | `DmaInteropRPCManager` (`com.whatsapp.infra.smax.generated.dmainterop.outgoing`); `C31107Dfz` (cases 20-23), `C31106Dfy`; `C214369Ee`, `C9EQ`, `C9EP`, `C214389Eg`, `A1J` | пять RPC `w:interop`, строгий разбор схемы |
| Интеграторы | `C227409sQ` менеджер, `C23765ANa` хранилище, `A3X` (`IntegratorInfo`), `InteropUiCache` = `SharedPreferencesOnSharedPreferenceChangeListenerC20390p5` (prefs `interop_ui`) | список, состояние opt-in, кэш UI |
| JID | `C99O` пользователь, `C41021lm` устройство, `C55529Oy6` группа, `C9YC` парсер; writer `C40411kn.A00`, reader `C24610wf` (tag 244) | раздел 3 |
| Приём | `ENP` -> `C34471Exu` (`DecryptionCallbackInterop`) -> `C34720F4p` (`InteropChatMessageHandler`); `DTF` (plaintext из 9 полей), `EUQ` (`ParseInteropMessageParams`) | строгий конвейер |
| Реестр типов | `C32718EOz`; `FBN` текст, `FBK` изображение, `FBL` видео, `FBJ` GIF, `FBH` аудио, `FBI` документ, `FBM` реакция, `FBG` неподдерживаемое | protobuf <-> FMessage |
| Отправка | `C33446EhE` (ветка), `F6P` (`E2eMessageEncryptor`), `F6K` (`<meta>`) | исходящие |
| Группы / privacy | `InteropGroupsManager`, `C3R2`, только smali `C3Rb` / `C3Qh`; `C0WQ` (уведомления); `InteropPrivacySettingsManager`, `C3Q4` / `C3Q1` / `C29664Cuh` | MEX |
| Opt-in | `C229349vm` (`InteropOptInManager`), `ARH`, `A4N`, `C224669lg` / `C24380wI` (уведомление), `PaaInteropMigrator` | мастер, согласие |
| Ping | анонимный `X.0xL` в `C1S0` (`InteropNotificationHandler`), id 270 в `AbstractC32331E9w` | уведомление |
| Аналитика | `AnonymousClass590` | WAM 6684, 7044, 7168, 6680 |

---

## 2. Гейтинг функции

### 2.1 Цепочка гейтов (found, `C32001Oa`)

| Метод | Условие | Применение |
|--------|-----------|----------|
| `A01()` | аккаунт не является зависимым (dependent) по правилам age-experience (`C14980fa.A00` -> `C08520Ne.A03()` -> `C08530Nf.A03()` false; тип dependent `EnumC08540Ng.DEPENDENT`) **и** AB **7495** | всё; папка в списке чатов, badge, compose |
| `A02()` | `A01()` и не companion (`AnonymousClass091.BRD()` false, т.е. `registration_device_id` равен 0) | менеджер opt-in, настройки, выбор интегратора, обработчик уведомлений |
| `A00()` | `A01()` и AB **15732** | пункт «New group», шаг group privacy |
| `A03()` | `A01()` и AB **11479** | шаг единого inbox и объединённый inbox |

`InteropSettingsActivity.onResume` (вызывает `finish()`), `InteropOptInSelectIntegratorsActivity.onCreate`, `InteropOptInManager` и обработчик уведомлений `w:interop` повторно проверяют `A02()`.

### 2.2 AB-флаги (found: id, значение по умолчанию и места вызова; имена из таблицы имён более старой сборки, сопоставлены по id, **inferred**)

| Флаг | Прежнее имя (inferred) | По умолчанию | Читается в | Что контролирует |
|------|------------------------|---------|---------|----------|
| **7495** | `IS_USER_INTEROP_ELIGIBLE` | false | `C32001Oa.A01`, `C224669lg.A01`, `C230679y0` (badge), `RunnableC23952AUh` (Home), `C0Y5` | корневой гейт; состояние badge на Home |
| **15732** | `INTEROP_GROUP_MESSAGING_ENABLED` | false | `C32001Oa.A00` | создание группы, шаг group privacy |
| **11479** | `WA_INTEROP_UNIFIED_INBOX_ENABLED` | false | `C32001Oa.A03`; id также зарегистрирован в `C33251Ee2` | шаг выбора типа inbox, объединённый inbox |
| **25512** | `INTEROP_CONTACT_MASTER_ENABLED` | false | `C0ZT`, `C51044MkK`, `C201508iH`, `C93z`, `InteropSelectChatTypeActivity` | пункт «New contact», сохранённые interop-контакты, разрешение имён |
| **5760** | `INTEROP_PROTOBUF_VALIDATION_ENABLED` | false | `ENP.A00` | направляет interop JID в строгий конвейер `InteropMessage` (8.1) |
| **38723** | без имени | false | `EA0.A00` (descriptor) | распространение sender key внутри interop-групп (строка лога `interop_group_skdm_processing_enabled`) |
| **23701** | `DMA_INFLATE_VIEW_ONDEMAND_ANDROID` | true | `C1R9` | inflate заголовка interop в списке чатов по требованию |

Определены со значениями по умолчанию, но литерального читателя не найдено (использование unknown): **3953** `INTEROP_CLIENT_UX_ENABLED`, **5759** `INTEROP_BOOTSTRAP_ENABLED`, **6613** `INTEROP_WS8_ENABLED`, **18670** `INTEROP_ADD_GROUP_PARTICIPANT_CLIENT_ENABLED`, **20999**, **11518**, **13532**, **14070** (все false); **22752**, **24016**, **24256**, **23652**, **24275**, **24098** (настройка UI `DMA_*`, все true). Флаг **11619** (`ENABLE_DMA_GROUP_JID`) отсутствует в таблицах значений по умолчанию. Механизм: WA_AB_PROPS.md.

### 2.3 Гейты вне AB (found)

- Уведомление о согласии **20240306** на стадии **160** (`C24380wI.A0D`): настройки показывают экран конфигурации только если оно принято, иначе стартовый экран opt-in (5.1).
- Зависимый аккаунт (`C14980fa`): не допускается; `PaaInteropMigrator` выходит из interop-групп и сбрасывает уведомление (5.5).
- Основное устройство (`A02()`): companion-устройства не могут выполнить opt-in или настройку.

---

## 3. Идентичность: JID и домены

### 3.1 Домены (found)

| Вид | Класс | Тип JID | Формат | Валидация |
|------|-------|----------|--------|------------|
| Interop-пользователь | `C99O` (`InteropUserJid`) | **22** | `{integrator}-{account}@interop` | дефис (последний разделяет); integrator 1-3 цифры, без ведущего `0`, разбирается как int; account 1-15 цифр, без ведущего `0` |
| Interop-устройство | `C41021lm` | **23** | `{integrator}-{account}:{device}@interop` | индекс устройства должен быть **0**, иначе `C09B` ("Interop device JIDs must have device index 0") |
| Interop-группа | `C55529Oy6` (`GroupJid`) | **28** | `{gid}@interop.g.us` | gid 1-20 цифр, первая цифра 1-9, без `-` |

- `C0DZ.A0W` = тип 22, `A0X` = 22 или 23 (1:1), `A0V` = 28, `A0U` = `A0X` или `A0V` (любой interop-чат); используется в 128 классах. `C41021lm.getRawString()` всегда выводит `:0`. Фабрика (`UserJid.JID_FACTORY.A04(str, "interop")`, `C9YC.A00`) бросает `C09B` ("Invalid interop JID: ...") при любом нарушении правил.
- Id интеграторов в ответах IQ ограничены диапазоном 1-999 (то же, что правило трёх цифр). Id групп не имеют устаревшей формы `creator-timestamp`; MEX-операции групп принимают gid без домена (`InteropGroupsManager.A00` отрезает `@...`).

### 3.2 Бинарный токен (found)

Tag **244** `JID_INTEROP` (writer `C40411kn.A00`, attribute reader `C24610wf`): строка `user` (id аккаунта, или gid для групп) -> u16 **device** -> u16 **integrator** -> байт **domain**.

Байт domain: **0** = `interop`, **2** = `interop.g.us`; любое другое значение бросает исключение ("invalid domain received for JID_INTEROP tuple"). Кортеж группы должен содержать device 0 и integrator 0 (иначе "invalid interop group jid"). Reader отображает domain 0 как `{integrator}-{user}[:{device}]@interop` (device опускается, когда равен 0). Tag **245** (отдельная форма interop JID в других клиентах) не имеет обработчика в этой сборке (grep по `C24610wf` / `C40411kn`).

### 3.3 Маппинг и отображение (found)

| Тема | Факт |
|-------|------|
| LID / PN | `WaJidMapRepository/setJidMapping refused mapping for interop JID`; interop JID является собственным адресом Signal и id чата |
| Имя | источник имени `INTEROP_NAME` (`C0Y7`), значение из поля `display_name` контакта (`c06290Dn.A07().A00.A0b`); парсер stanza сообщения читает `notify` и `display_name` для каждого сообщения (`AbstractC33377Eg6.A02`); использование `display_name` как push-имени для interop выведено (inferred) |
| Участники группы | разбор участников `w:g2` сохраняет interop JID в записи участника (`C23201A1a` -> `C228499uF.A00(c99o, ...)`), плюс `display_name`, `lid`, `phone_number`, `join_time` |
| Данные профиля | нет фото профиля и имени: "Profile name and photo are not available in third-party chats" (строка); только иконка интегратора (кэш 8 MiB `cache/interop_image_cache`, загрузчик `interop_image_loader`) |

---

## 4. Интеграторы

### 4.1 Модель (found)

Ни имени интегратора, ни фиксированного id, ни таблицы типов идентификаторов нет в коде, `res/` или `assets/`; сервер решает, какие интеграторы существуют, их id, имена и поддержку групп. `A3X`: `A00` id, `A03` имя, `A02` статус (`ONBOARDING`, `ACTIVE`, `REMOVED`), `A04` URL иконки, `A05` optedIn, `A01` тип идентификатора (`USERNAME`, `PHONE`, `EMAIL`), `A06` supportsGroupMessaging. Интегратор для JID: `C99O.A00` -> `C227409sQ.A00` -> `A3X`.

### 4.2 Получение (found, `C31107Dfz` case 20, парсер `C214369Ee`)

Запрос `<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><integrator fetch="all"/></iq>` (`to` = серверный JID, класс `C19380nJ.A00`). Результат: `<integrator_list opted_in="true"><integrator id status identifier_type name icon opted_in><features group_messaging/></integrator>...</integrator_list>` (имена атрибутов найдены; форма узла `features` выведена из пути `features/group_messaging`; inferred).

Карта атрибутов: `status` = `onboarding` / `active` / `removed`; `identifier_type` = `username` / `pn` / `email`; `features` -> `group_messaging` = `true` / `false`; `opted_in` по умолчанию `true`. Ограничения парсера: 0-999 интеграторов, id 1-999; запись без `name` или `icon` отбрасывается; неизвестный статус или тип идентификатора бросает исключение. Ошибки IQ: `bad-request` (400), `internal-server-error` (500) (`A1J.A02` / `A04`).

Корутина обновления (`C24110Aar` case 34, лог `IntegratorManager/refreshIntegrators`) записывает таблицу (5.6) и pref `group_capable_integrators`. Найденные триггеры: открытие экрана opt-in; общий обработчик `<ack error>` (`C13X`) удаляет все строки `integrator_display_name`, когда interop-сообщение 1:1 отклонено (`C24110Aar` case 35). Другие триггеры не выяснены.

---

## 5. Согласие, opt-in, настройки

### 5.1 Уведомление о согласии (found)

Id уведомления **20240306** — это privacy disclosure (`C24380wI`, класс `PrivacyDisclosureDataManager`). Стадия **160** = принято (`A0D`); стадии 105-399 считаются «допустимо/показано» (`A02`). `InteropOptInManager.A01` (`C229349vm`):

```
A02() false -> log "interop is not enabled, stop"
notice 20240306 != 160 -> render notice (C32411Pr.A05); ARH.onUserOptedIn sets has_previously_onboarded and continues; dismiss / deny / error stop
else -> InteropOptInSelectIntegratorsActivity(entryPoint)
```

Стадию **162** записывает `PaaInteropMigrator` (`C24380wI.A09(null, 20240306, 162, false)`); значение неизвестно (это не 160, поэтому после этого уведомление считается непринятым).

### 5.2 Мастер (found, `A4N`, `InteropOptInSelectIntegratorsActivity`)

```
Select integrators (list from table, header "Select the third-party apps you want people to message you from.")
   ▼
[AB 11479] Unified inbox option (COMBINED | SEPARATED) ──► else skip
   ▼
[AB 15732] Group privacy setting ("Who can add me to third-party groups") ──► else skip
   ▼
InteropOptInManager.A01: notice not accepted -> consent notice (5.1); accepted -> straight on
   ▼  onUserOptedIn
SetOptInIntegrators IQ (full list)
```

Если уведомление уже принято (редактирование из настроек), экран выбора скрывает кнопки cancel и continue, а `C201718ig.A00` сохраняет напрямую (сохранение при изменении выведено; inferred); тип inbox и group privacy — отдельные строки фрагмента конфигурации. Шаг group privacy, как выведено, заканчивается в `A01` (лог `BaseInteropOptInViewModel onOptInContinue`; inferred). Точки входа — int (`entryPoint`), логируется в WAM (5.6).

### 5.3 SetOptInIntegrators (found, `C31107Dfz` case 23, парсер `C9EP`)

```xml
<iq type="set" xmlns="w:interop" to="s.whatsapp.net" id=".."><opt_in_integrators><integrator_list>
  <integrator id="12"/> ...      <!-- 0..999 entries, the full desired state -->
</integrator_list></opt_in_integrators></iq>   <!-- result: integrator_list/integrator[@id], each with an optional error child -->
```

Обработка на клиенте (`C24113Aau` case 40): ошибки по каждому интегратору собираются; таблица перезаписывается одной транзакцией (`opt_in_status` сбрасывается для всех, затем выставляется для запрошенных минус неудачные id). Отдельной stanza для opt-out нет: диалоги opt-out и путь «turn off» используют тот же set с более коротким списком (выведено из отсутствия любой другой stanza opt-out; путь с пустым списком не прослеживался; inferred).

Сопоставление ошибок в UI (`InteropOptInSelectIntegratorsActivity.A0X`): коды **500**, **810**, **800** -> "Apps can't be saved right now. Please try again later."; любой другой или null код -> "Apps can't be saved right now."

### 5.4 Экраны настроек (found, `AndroidManifest.xml`)

Экраны (все в `AndroidManifest.xml`): `InteropSettingsActivity` с фрагментами Main / Optin / Config (стартовый экран, когда уведомление не принято, иначе конфигурация; FAQ справки `317021344671277`); `InteropOptInSelectIntegratorsActivity` (приложения); `InteropUnifiedInboxOptionActivity` ("Manage inbox", COMBINED против SEPARATED); `InteropGroupPrivacySettingUpdateActivity` и `...AddBlocklistPickerActivity` (9.4); `InteropReachNotificationSettingsActivity` ("Third-party chat requests", 6.3); `InteropOptOutDialogFragment` / `...IntegratorDialogFragment` ("Turn off third-party chats?"); `InteropConversationsActivity` (список папки); `InteropComposeSelectIntegratorActivity`, `...EnterInfoActivity`, `InteropSelectChatTypeActivity` (новый чат / группа / контакт).

### 5.5 Opt-out и мигратор (found)

После opt-out существующие чаты становятся только для чтения (баннер в composer "Third-party chats are turned off. You can't send messages in this chat, and you won't receive messages."). `PaaInteropMigrator` (`C0q`): запускается, когда аккаунт является зависимым (`C20K.A1W` = restricted) **и** уведомление принято; вызывает `LeaveInteropGroup` (`groups_to_leave`, коды ответа из {200, 400, 401, 403, 404, 405} считаются завершением), затем записывает стадию уведомления 162. Расшифровка «PAA» выведена (age-experience; inferred); связь с зависимым аккаунтом найдена.

### 5.6 Сохранённое состояние и аналитика (found)

| Хранилище | Ключи / схема |
|-------|---------------|
| prefs `interop_ui` | `unified_inbox_option` (UNKNOWN / COMBINED / SEPARATED), `who_can_add_me_to_interop_groups` (int), `who_can_add_me_to_interop_groups_hash`, `who_can_add_me_to_interop_groups_deny_list` (set), `optedInIntegratorNames` (set) + ключи имён по id, `interop_reach_enabled` (по умолчанию true), `interop_reach_integrators` (массив int), `interop_reach_notifs` (set из `id:name:display_name:t`), `suspended_interop_groups` (set из gid), `has_previously_onboarded`, `group_capable_integrators`; prefs `interop_badge_prefs`: `pref_interop_badge_disabled`, `pref_interop_badge_account_state`, `pref_interop_badge_third_party_chats_state` |
| таблица `integrator_display_name` | `integrator_id` INTEGER PK, `display_name` TEXT, `status` INTEGER, `icon_path` TEXT по умолчанию `''`, `opt_in_status` INTEGER по умолчанию 0, `identifier_type` INTEGER по умолчанию 0, `group_messaging_supported` INTEGER; индекс `integrator_opt_in_index` по `opt_in_status` |
| другие таблицы | `wa_block_list_interop` (уникальный индекс по `jid`); строки `wa_address_book` с `raw_contact_id = -5` и `jid LIKE '{id}-%@interop'` (`SAVED_INTEROP_CONTACTS`), не записываются в контакты телефона |
| WAM | 6684 (доставка баннера), 7044 (процесс onboarding, session id `InteropOnboardingSessionIdManager`), 7168 (действие пользователя), 6680 (сторонний inbox); событие 1158 содержит `interopContactsSize`, `interopContactsSizePerIntegrator` |

---

## 6. `w:interop` IQ set

Пять RPC `DmaInteropRPCManager` проходят через `MessageClientSmaxWrapper`; каждый IQ несёт `type`, `xmlns="w:interop"`, `to` = серверный JID, `id`.

| Операция | Тип | Тело | Лимит | Результат |
|-----------|------|------|-------|--------|
| FetchIntegrators | get | `<integrator fetch="all"/>` | - | 4.2 |
| FetchUsers | get | `<users><user external_id integrator_id/></users>` | **1-20 users** | 7.2 |
| SetOptInIntegrators | set | `<opt_in_integrators><integrator_list><integrator id/>` | 0-999 | 5.3 |
| GetReachabilitySettings | get | `<reachability_settings/>` | - | 6.3 |
| SetReachabilitySettings | set | `<reachability_settings enabled="true\|false"><integrator id/>...` | 0-999 | результат / ошибка |
| Block / unblock | set | `<blocklist><item action="block\|unblock" jid="{interop JID}"/></blocklist>` | - | результат; ошибки `IQErrorBadRequest`, `IQErrorInternalServerError` |

### 6.1 Блокировка и жалоба (found)

Блокировка interop использует `xmlns="w:interop"` (`C31106Dfy`, helper `C9EF`, лог `InteropBlocklistHelper/getInteropBlocklist/error code:`) и таблицу `wa_block_list_interop`. UI: "Blocked in third-party chats"; диалог блокировки сообщает, что люди, заблокированные в WhatsApp, всё ещё могут связаться с пользователем в стороннем приложении. Жалоба на спам использует общий поток спама (`spam_flow`, `C9E2`) с текстом диалога для каждого интегратора. Маршрутизация уведомлений: `AbstractC32331E9w` сопоставляет xmlns `w:interop` с обработчиком id **270**; `EnumC32096E0u.NOTIFICATION_W_INTEROP` = `"w:interop"`.

### 6.2 Уведомление ping (found, анонимный `X.0xL` в `C1S0`)

`<notification xmlns="w:interop" t=".."><ping display_name=".."><X id=".." name=".."/></ping></notification>` (тег `X` первого потомка `ping` кодом не проверяется).

Принимается только первый потомок с именем `ping` (иначе лог `unknown tag=`). При истинном `A02()` он добавляет `id:name:display_name:t` в pref `interop_reach_notifs`, показывает локальное уведомление в канале `critical_app_alerts@1` (текст "Chatting with people on third-party apps is an optional WhatsApp feature in the European Region.", действие "Manage requests", приёмник отклонения `InteropNotificationDismissReceiver`) и логирует WAM 6684. Серверный триггер (кто-то из интегратора пытался связаться с пользователем) выведен из текста настроек "Get notified when someone wants to message you from a third-party app." (inferred).

### 6.3 Доступность (found)

Настройки задаются для каждого **интегратора** (потомки `<integrator id>`, предел 0-999), а не для каждого пользователя. Значение `enabled` по умолчанию `true` в `interop_reach_enabled`. Кода подписки на presence для interop JID не найдено (выведено: доступность заменяет её; inferred).

---

## 7. Обнаружение пользователей

### 7.1 FetchUsers (found, `C31107Dfz` case 21, парсер `C9EQ`)

Interop JID приходят только из этого IQ; в USync нет протокола interop (WA_USYNC.md).

```xml
<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><users>
  <user external_id="alice@example.org" integrator_id="12"/>          <!-- 1..20 -->
</users></iq>
<!-- result -->
<users>
  <user jid="12-105012705411308@interop" external_id=".." normalized_external_id=".." integrator_id="12"/>
  <user external_id=".." normalized_external_id=".." integrator_id="12"><error code="404" text="item-not-found"/></user>
</users>
```

Результаты по пользователю: успех `user[@jid]` (`C9DG`, jid разбирается как `C99O`); `item-not-found` код по умолчанию **404** (`C9DH`); `forbidden` по умолчанию **403** (`C9DF`); `internal-server-error` (`C9DE`).

Ошибки всего IQ: `bad-request`, `internal-server-error`. Списки результатов в `C9FA`: не найдено, forbidden, ошибка сервера, карта разрешённых `{(external_id, integrator) -> UserJid}`. И запрос, и ответ отвергают 0 или более **20** пользователей.

### 7.2 Ввод идентификатора и сохранённые контакты (found, `InteropComposeEnterInfoActivity`)

| Тип идентификатора | UI | Значение, отправляемое как `external_id` |
|-----------------|----|------------------------------|
| `USERNAME` | одно поле ("Enter Username") | текст |
| `PHONE` | выбор страны + номер | код страны и номер, склеенные (фильтр по символам, правило не прослеживалось) |
| `EMAIL` | одно поле | текст |

Поток: выбор приложения (`InteropComposeSelectIntegratorActivity`, интеграторы с opt-in из таблицы) -> тип чата (`InteropSelectChatTypeActivity`: "New chat", "New group" если AB 15732 и интегратор поддерживает группы, "New contact" если AB 25512) -> ввод id -> FetchUsers -> открытие чата по возвращённому JID. Строки: "This user can't be found" (не найден), "This user is already a group member" (добавление в группу), "Couldn't create the chat. Please try again.".

При AB 25512 `ContactFormActivity.verifyInteropIdentifierAndSave` разрешает id через FetchUsers (`C24113Aau` case 41) и сохраняет строку `wa_address_book` (raw_contact_id -5); "Usernames and contacts added to third-party chats will not save to your phone."

---

## 8. Обмен сообщениями

### 8.1 Выбор конвейера (found)

Расшифровка (`ENP.A00`): когда AB **5760** включён и JID чата удовлетворяет `A0U` (interop 1:1 или interop-группа), шифротекст обрабатывается `C34471Exu` (`DecryptionCallbackInterop`); иначе работают обычные callbacks. Типы шифротекста, обрабатываемые `ENP`, обычные: **0** (`msg`), **1** (`pkmsg`), **2** (`skmsg`, sender key), **4** (путь бота, не interop). Значит, interop использует те же сессии Signal и sender keys, что и нативные чаты.

```
<message from="12-123[:0]@interop" ..><enc type=pkmsg|msg|skmsg v=2>...</enc></message>
   │  ENP.decryptMessage (Signal / sender key)
   ▼
C34471Exu.handlePlaintext
   │  remove padding (last byte = pad length; empty / zero / >= length fails, log DecryptUtil/removePadding)
   │  C33369Efy.A03(E0T.INTEROP_MESSAGE, ...)          ── message pipeline type "interop_message"
   ▼
C34720F4p (InteropChatMessageHandler)
   │  parse bytes as DTF (InteropMessage subset)
   │  unknown-field check -> failure 70
   │  C32718EOz.A00(EUQ) -> FMessage via type handlers; SKDM (group) processed if AB 38723
   ▼
store, receipt, notification
```

Сообщение об ошибке: `C34720F4p.A00` возвращает `C33063Eaz(reason)` и вызывает `A0Y(null, key, reason, 491)` на пути receipt; `C34471Exu` вызывает `C33369Efy.A07(.., 491, reason, ..)` для недопустимого plaintext. Литерал **491** общий для обоих (значение не выяснено).

### 8.2 Подмножество plaintext `InteropMessage` (found, `DTF`)

Plaintext — **не** полный `Message`. `DTF` объявляет ровно эти поля с теми же номерами, что и в полном `Message`:

| Поле | Номер | Тип | Обработчик | Примечания |
|-------|--------|------|---------|-------|
| `conversation` | **1** | string | `FBN` | простой текст |
| `senderKeyDistributionMessage` | **2** | message | `C34720F4p` | id группы + axolotl SKDM; id группы должен совпадать с чатом, когда чат является группой |
| `imageMessage` | **3** | message | `FBK` | |
| `extendedTextMessage` | **6** | message | `FBN` | поля превью ссылки |
| `documentMessage` | **7** | message | `FBI` | не когда `type` stanza равен `medianotify` |
| `audioMessage` | **8** | message | `FBH` | голосовые сообщения через `ptt` |
| `videoMessage` | **9** | message | `FBL` (без `gifPlayback`) / `FBJ` (`gifPlayback`) | |
| `reactionMessage` | **46** | message | `FBM` | |
| `ptvMessage` | **66** | message | не найден | принимается схемой и проверяется на неизвестные поля; парсера FMessage в реестре нет (приём видеозаметок не выяснен) |

Проверка неизвестных полей читает счётчик неизвестных полей через reflection из `DTF` и из подсообщений image, video, PTV, audio, document, extended text и reaction; счётчик 1 или больше возвращает ошибку **70**. Поля вне `DTF` поэтому приводят к отказу сообщения: например `messageContextInfo` (35), `protocolMessage` (12), sticker, contact, location, poll (выведено из схемы; влияние конкретного поля не проверялось; inferred).

### 8.3 Поддерживаемые типы сообщений и лимиты (found)

| Тип | Правила, применяемые при приёме (причина ошибки) |
|------|--------------------------------------------|
| Текст, видео | `conversation` или `extendedTextMessage.text`, обрезается до **65536** символов; превью ссылки только если `matchedText` является допустимым URL, содержащимся в тексте; заголовок и описание обрезаются до 65536; тип превью сопоставляется с 0, 1, 4, 5, 6, 7; видео и GIF используют общий медиа-парсер `C33395EgO.A05` (`gifPlayback` выбирает `FBJ`) |
| Изображение | `mediaKey` обязателен (16); `fileLength` >= 0 (13); `fileSha256` 32 байта (14); `fileEncSha256` 32 байта, если задан (14); mime **только `image/jpeg` или `image/png`** (17); `directPath`, ширина, высота копируются; тройка thumbnail (direct path, sha, enc sha) необязательна; progressive scans принимаются при 2-20 длинах сканов, `scansSidecar` длина / 10 равна количеству и сумма помещается в int |
| Аудио | `mediaKey` обязателен (16); `fileLength` > 0 (13); хеши 32 байта (14); mime должен быть известным аудиотипом (17); флаг `ptt`; `waveform` сохраняется только при 1-192 байтах; `backgroundArgb`; `seconds` |
| Документ | `mediaKey` обязателен (16); `fileLength` >= 0 (13); хеши 32 байта (14); `title` обрезается до 65536; JPEG thumbnail сохраняется, если проходит проверку размера |
| Реакция | `key.id` и `key.remoteJid` непусты; `text` вместе с ненулевой версией правки отвергается (warning `edit version and text message are both set`); `senderTimestampMs` сохраняется; stanza с `type="reaction"` должна дать сообщение-реакцию (иначе ошибка **76**) |
| Ответ / цитата | `ContextInfo` с `stanzaId`, `participant`, цитируемым сообщением (снова разбирается как `DTF`, `ContextInfoProtobufInterop`), `quotedType`; на стороне отправки `InteropContextInfoBuilder` сериализует цитируемое сообщение рекурсивно |

Не принимаются (вне 9 полей): стикеры, контакты, геолокации, опросы, события, шаблоны, view-once. Выбор вложений скрывает пункты contact, location, poll, event, group status, imagine, payment, pix и remittance для interop-чатов (проверки `A0L`, `A0M`, `A0P`, `A0Q`, `A0R`, `A0T`, `A0U`, `A0X` в `ConversationAttachmentContentView`); document, camera, gallery и audio не закрыты interop-проверками (выведено, что остаются доступными; inferred). Исчезающие сообщения не поддерживаются ("disappearing messages are not supported in third-party chats", также исключены из настройки таймера по умолчанию). Байты медиа идут по обычному медиа-пути WhatsApp (ключ, хеши и `directPath` в сообщении; значение аналитики источника загрузки 15 = `interop`).

### 8.4 Сторона отправки (found)

| Шаг | Поведение |
|------|-----------|
| Сериализатор | `C33446EhE`: JID чата типа 22/23 (`A0X`) использует interop-сериализатор (`C32718EOz.A01` с `ADs` для каждого типа, логи `buildE2eInteropMessage`); остальные чаты используют обычный построитель, поэтому interop-**группы** (тип 28) идут через обычный построитель |
| Неподдерживаемый класс FMessage | обработчик `FBG` -> бросает `E3G` 70 до отправки; неверный класс для обработчика -> `E3G` 0 |
| Проверки изображения | mime `image/jpeg` или `image/png`, иначе `E3G` 17 (`null` становится `image/jpeg`); хеш не 32 байта `E3G` 14; нет media key `E3G` 16; участники stanza `F6B`, `F6G`, `F6I`, `F68`, `F69`, `F6H`, `F6M`, `F6X` не имеют interop-ветки (прикрепление не выяснено) |
| Encryptor (`F6P`) | для interop-чатов (`A0U`) encryptor пропускает `C33284Eea.A02` (добавляет метаданные списка устройств через `AbstractC30999De0.A03`; inferred) и пропускает `paddingBytes` (размер из AB 1723) |
| `<meta>` (`F6K`) | `content_type="add_on"` пропускается для interop-чатов |
| Reporting token (`F6L`) | пропускается, когда цель является JID interop-устройства |
| Список устройств / ADV | индекс interop-устройства всегда 0; `DeviceADVInfoHandler` имеет interop-проверку на входе (`C24230w2`, ранний выход выведен; inferred); multi-device fan-out невозможен (выведено: одно устройство на контакт; inferred) |

Дальнейшие отличия от нативных сообщений: interop-чаты используют тип конвейера `interop_message` (`E0T`) вместо типов text / media / reaction; значение типа чата WAM 5 в событии decrypt (`AbstractC33424Egr`) и 6 в событии `FNR` (нативные 3 / 1); add-ons с message secret (голоса в опросах, зашифрованные реакции, см. WA_MESSAGE_SECRETS.md) не входят в 9 полей, поэтому не могут попасть в interop-чаты (inferred).

---

## 9. Interop-группы

### 9.1 Модель (found)

Группа — это `{gid}@interop.g.us` (тип 28). Участники — аккаунты WhatsApp (добавляются как пользовательские JID **LID**; найдено на пути добавления, путь создания, как выведено, такой же; inferred) и interop JID. Метаданные группы приходят из MEX вместо `w:g2`: `C11410Yt.A0F` вызывает `GroupXmppMethods/sendGetInteropGroupInfo` для типа 28. Состояние: `UNSET`, `ACTIVE`, `SUSPENDED`; приостановленные gid хранятся в pref `suspended_interop_groups`. Баннеры в composer: приостановленная группа "You can't send messages to this group because all third-party members have left."; opt-out или удаление "... because you're no longer a member."

### 9.2 MEX-операции (found; doc ids из `assets/whatsapp-android-mex_client_persist_ids.json`)

| Операция | doc_id | Корневое поле | Вход | Выход / примечания |
|-----------|--------|-----------|-------|----------------|
| `GroupsCreateInteropGroup` | `25726817620301611` | `xwa2_interop_group_create` | `input.participants[{jid}]` | `group`: `gid`, `creation_time`, `creator_v2`, `display_name`, `participants_v2`; subject не отправляется |
| `LeaveInteropGroup` | `25346167795013271` | `xwa2_interop_group_leave` | `input.groups_to_leave[{gid}]` | `response_code` для каждой группы; {200, 400, 401, 403, 404, 405} считаются окончательными |
| `AddParticipantsToInteropGroup` | `25732168276369451` | `xwa2_interop_add_participants_to_group` | `input.gid`, `input.participants[{jid}]` | участники WhatsApp сначала отображаются PN в LID; LID `null` прерывает вызов |
| `QueryInteropGroupInfo` | `32734144032867938` | `xwa2_interop_group_query_by_id` | `group_input.gid` | `state`, `gid`, `creation_time`, `creator_v2`, `participants_v2` |
| `InteropPrivacySettingsQuery` | `24849123668112654` | `xwa2_fetch_wa_users` -> `interop_privacy_settings` | `interop_privacy_settings_query_input{feature, dhash}` для собственного LID | `settings_data`, `dhash`, `denied_contacts[{jid}]` |
| `InteropPrivacySettingsUpdate` | `25421856497452763` | `xwa2_interop_privacy_setting_update` | `feature`, `setting` | `success` |
| `InteropPrivacySettingWithContactListUpdate` | `24913399124998598` | `xwa2_interop_privacy_setting_with_contact_list_update` | `contact_list_type`, `contacts`, `dhash` (`none`, если отсутствует), `feature`, `setting` | `success` |

Ошибки создания и добавления показываются как "This group couldn't be created" / "Make sure everyone you add to this group has third-party chats turned on." / "A group with these members already exists." (найденные строки). Для создания группы нужен хотя бы один пользователь выбранного интегратора ("To create this third-party group, you need to select at least one %1$s user.").

### 9.3 MEX-уведомления (found, `C0WQ`)

| Уведомление | Обработчик | Эффект |
|--------------|---------|--------|
| `NotificationInteropGroupCreateUpdate` | ветка `AbstractC23194A0r` (лог `CreateInteropGroupNotificationHandler/`) | создаёт локальную группу по `gid`, создателю и участникам |
| `NotificationInteropGroupParticipantsUpdate` (`Xwa2NotifyInteropGroupOnParticipantChange`) | `A0B` | добавляет участников с источником `general_chat_auto_add`, удаляет вышедших участников; рано возвращается (`no updates needed to gid=`), когда `C22300su.A15()` false |
| `NotificationInteropGroupPropertyUpdate` | `A0C` | `state` ACTIVE или SUSPENDED -> `suspended_interop_groups` |

### 9.4 Кто может добавлять меня (found, feature `GROUPADD`)

Enum настройки `C9U8`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `MYCONTACTS`, `MYCONTACTSEXCEPT`, `MYCONTACTS_AND_ENABLED_INTEROP_INTEGRATORS`, `NONE`. Вариант со списком контактов несёт deny list (`contact_list_type`, `contacts`). Текст: "You can only be added to third-party chats by people who either use or have selected the same messaging app." Настройка хранится для собственного LID и кэшируется с `dhash`; применение на стороне сервера (inferred), клиент лишь показывает настройку.

---

## 10. Список чатов, модель тредов, UI

| Элемент | Факт (found) |
|------|--------------|
| Тред | один чат на interop JID (1:1) или на gid; хранится в обычных таблицах чатов; отдельной таблицы тредов нет |
| Папка | `InteropConversationsActivity` / `Fragment`; header view `InteropView` в списке чатов (`C31071Ju`, лог `ChatListInteropChatsDelegate/`); показывается, когда пользователь допустим и уведомление принято, или когда interop-чаты уже существуют; скрыта, когда inbox COMBINED |
| Режим inbox | SEPARATED: папка внутри основного inbox или в меню «More»; COMBINED: interop-чаты в списке на вкладке Chats (filter chip `interop` в фильтрах чатов, `THIRD_PARTY_FILTER`) |
| Строка / поиск | подпись с именем интегратора и badge-иконка на аватаре; сторонние чаты не включаются в результаты поиска |
| Баннер / badge | "You're messaging someone outside of WhatsApp. Third-party apps may have different security."; badge на Home из `pref_interop_badge_*`, управляется AB 7495 (`C230679y0`) |

---

## 11. Baileys (`baron-baileys-v2` 1.5.17, `src/Socket/interop.js`, `WABinary/decode.js`, исходный код прочитан, ничего не тестировалось)

| Тема | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| Интеграторы | зашиты `12` (BirdyChat, email) и `13` (Haiket, pn) | нет в клиенте; список с сервера |
| Пакетный поиск | `INTEROP_BATCH_MAX = 256` | **20** (построитель запроса и парсер ответа) |
| Opt-out | `<opt_out_integrators><integrator_list>` | такого узла нет; IQ opt-in с более коротким списком |
| Установка reachability | `<reachability_settings enabled><user external_id integrator_id/>` | потомки `<integrator id/>` |
| Согласие | IQ `tos` `trackable id=20240306 result=105`, затем `160` | уведомление 20240306 стадия 160 = принято (found); wire-форма IQ уведомления не прослеживалась |
| Бинарный JID | reader кортежа 244 бросает исключение, если domain не 0; tag 245 обрабатывается | tag 244 с domain 0 **и** 2 (группы); tag 245 нет |
| Уведомления | `type="interop"` с `stella_interop_enabled`, `peer_device_presence`, `ig_profile`, fbid | обработчик `w:interop` id 270 обрабатывает только `ping` |
| Отправка / приём | простой текст как `conversation`, reporting token пропускается; комментарий в `Defaults/index.js`: приём interop не реализован | сериализатор ограничен 9 полями; строгий парсер `InteropMessage`; MEX-id групп и уведомления идентичны по охвату |

Почему не работает (выведено из сравниваемого выше кода; inferred):

| Симптом | Причина | Исправление |
|---------|-------|-----|
| Ошибка декодирования на JID interop-группы | reader кортежа отвергает байт domain 2 | принимать domain 2 -> `{gid}@interop.g.us`, требовать device и integrator 0 |
| Получатель отбрасывает сообщение с ошибкой неизвестного поля | любое поле вне 9 (например `messageContextInfo` с `messageSecret`, `protocolMessage`) вызывает отказ, если получатель выполняет тот же строгий разбор (inferred; отправки interop через Baileys для этих полей не прослеживались) | собирать `Message` только с полями 1, 2, 3, 6, 7, 8, 9, 46 (и 66) |
| Opt-out не действует | `opt_out_integrators` не существует в клиенте | отправлять SetOptInIntegrators с оставшимися id |
| Ничего не приходит в companion-сессиях | у interop-контактов только device 0 | держать interop на основной сессии |

---

## 12. Случаи ошибок

| Симптом | Причина | Где |
|---------|-------|-------|
| Interop-экраны сразу закрываются или не появляются | `C32001Oa.A02()` false: флаг 7495 выключен, зависимый аккаунт или companion-устройство | 2.1 |
| "Apps can't be saved right now" | сбой SetOptInIntegrators; коды 500 / 810 / 800 дают текст "try again later" | 5.3 |
| "This user can't be found" | FetchUsers `item-not-found` (404) | 7.1 |
| Исключение недопустимого interop JID | integrator не 1-3 цифры / ведущий 0, account не 1-15 цифр, индекс устройства не 0 | 3.1 |
| Группа не создана / composer отключён | ошибка MEX create или дубликат набора участников / opt-out, группа приостановлена, больше не участник | 9.1, 9.2 |
| Входящее сообщение отброшено, причина 70 / 13 / 14 / 16 / 17 / 76 / 26 | неизвестное поле или тип без обработчика / неверный размер / неверная длина хеша / нет media key / недопустимый mime / несоответствие типа реакции / исключение разбора | 8.2, 8.3 |
| Group SKDM игнорируется | AB 38723 выключен (лог `sender key distribution message skipped`) | 8.1 |
| Имена интеграторов пропали после ошибки отправки | ack error стёр `integrator_display_name` | 4.2 |

---

## 13. Ключевые различия

| Не путать | Факт |
|----------------|------|
| `w:interop` против USync | обнаружение контактов — это FetchUsers в `w:interop` (максимум 20), а не протокол USync |
| `@interop` / `@interop.g.us` / `@g.us` | пользователь и устройство, группа, нативная группа; interop JID никогда не отображается в LID или PN |
| `InteropMessage` против `Message` | приём принимает 9 полей; отправка опускает context и padding для interop |
| privacy-токен `trusted_contact` | общая задача privacy-токена (WA_TCTOKEN_CSTOKEN.md); кода, специфичного для interop, в этой сборке не найдено |
| «interop» в UPI | `IndiaUpiInterOpHybridActivity`, `IndiaUpiInteropSendToUpiActivity`, флаги заметки платежа `isInterop` — функции платежей, не связаны |
| «interop» в Compose / EXIF | `androidx.compose.ui.viewinterop`, `InteroperabilityIFDPointer` — это библиотеки |
| Допустим против opt-in против согласия | флаг 7495 = допустим; `opted_in` по интегратору приходит с сервера; согласие = уведомление 20240306 стадия 160 |

---

## 14. Полный поток

```
[User]              [Client]                                   [WA server]              [Integrator app]
  │ Settings > Third-party chats
  ├──────────────────► A02(): flag 7495, primary, not dependent
  │                    notice 20240306 != 160 ──► show ──► accept ──► stage 160
  │ apps (+ inbox type, + group privacy)
  ├──────────────────► SetOptInIntegrators ─────────────────► opted_in list; table rewritten
  │ New chat > app > id
  ├──────────────────► FetchUsers (1..20) ──────────────────► jid 12-<account>@interop / 404 / 403 / 500
  │ send text / image / video / audio / doc / reaction
  ├──────────────────► restricted Message (no context, no padding), Signal encrypt, device 0
  │                    <message to=..@interop> ─────────────► bridge (inferred) ───► [Integrator app]
  │                    <message from=..@interop><enc/> ◄──────────────────────────── reply
  │                    ENP -> DecryptionCallbackInterop -> DTF parse (unknown field -> 70) -> FBx -> FMessage
  │ ◄──────────────── chat row, notification
  │                    <notification xmlns=w:interop><ping/> ◄─ server (trigger inferred)
  │ ◄──────────────── local notification "Manage requests"; reachability per integrator
  │ New group (flag 15732)
  ├──────────────────► GroupsCreateInteropGroup (LID + interop JIDs) ──► gid@interop.g.us
  │                    MEX notifications: create / participants / property; SUSPENDED -> composer blocked
```

---

## 15. Неизвестное

| Тема | Состояние |
|-------|-------|
| Wire-форма IQ уведомления о согласии | не прослеживалась; известны только стадии 160 (принято) и 162 (записывается мигратором) |
| Серверный мост, доставка интегратору, обработка ключей на той стороне | не видно в клиенте; клиент использует обычные сессии Signal и sender keys |
| Смена идентичности / safety number для interop-контактов | не прослеживалось |
| Звонки, опросы, правки, отзывы, смена идентичности / safety number для interop-чатов | interop-пути в коде не найдено (в коде звонков нет interop-строк); не прослеживалось |
| Приём PTV (`ptvMessage`) | поле принимается, парсер не найден |
| Литерал 491 на пути ошибки; коды ошибок 810 / 800; триггеры FetchIntegrators, кроме экрана opt-in | не выяснено |
| Читатели флагов 3953, 5759, 6613, 18670, 20999, 11518, 13532, 14070 | нет литерального читателя; могут читаться через descriptors |
| Read receipts для interop-контактов | `ClientPayload.interopData` (поле **38**, `C38671hT`: `accountId` 1, `token` 2, `enableReadReceipts` 3) существует в схеме; ничто в этой сборке его не заполняет |
| Применяет ли сервер правило европейского региона | только текст UI; клиентской проверки нет |
