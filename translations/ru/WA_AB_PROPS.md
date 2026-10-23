<!-- src-sha1: 4762669c756eee4725aaf5af56633f2b59edd479 -->
# WhatsApp AB Props — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** AB props / feature flags на Android: числовые id флагов и типизированные таблицы значений по умолчанию, типизированные ридеры и опции чтения, слой MobileConfig (Stable IDs, типы unit, `params_map_v4_u*`, `MetaConfigFetchMutation`), IQ синхронизации props (`xmlns="abt"`: hash, refresh, refresh_id, delta, expo-ключи, веса сэмплирования), props уровня группы, props до регистрации, локальные (офлайн) эксперименты, хранение на устройстве, логирование exposure, пути override и отладки, связь с id флагов из других отчётов, каталог флагов по областям, сравнение с Baileys

---

## 1. Что это (технически)

AB props — это управляемые сервером feature flags клиента. Каждый флаг идентифицируется только числовым **config code** (например, `20548`); имён флагов в APK нет. Клиент поставляется с типизированной таблицей значений по умолчанию для каждого кода, запрашивает у сервера переопределения через IQ, сохраняет ответ в SharedPreferences и читает его через один абстрактный класс-ридер. Рядом работает второй, производный от Meta слой (MobileConfig), который может стать источником истины. Все утверждения получены статическим анализом декомпилированного APK; в сети ничего не перехватывалось. Уровни: **found** = прочитано в коде или данных, **inferred** = выведено, **unknown** = не выяснено. Обфусцированные имена зависят от сборки и заново определены в 2.26.41.6.

| Слой | Имя в 2.26.41.6 | Роль |
|------|-----------------|------|
| Базовый ридер | `C00D` (abstract) | типизированные аксессоры, кэши, exposure, переключатель MobileConfig |
| Основное хранилище | `C08J` (`extends C00D`, prefs `ab-props`) | содержит пять карт значений по умолчанию, читает все обычные флаги |
| Хранилище pre-chatd | `C0D9` (prefs `ab-prechatd-props`) | флаги, получаемые по HTTP до подключения аккаунта |
| Приватное хранилище | `C0ER` (prefs `ab-private-abprop`) | значения локальных экспериментов, те же значения по умолчанию, что у `C08J` |
| Опции чтения | `C00F` (`AbPropsOptions`) | режим exposure + закрепление первого доступа |
| Типизированные дескрипторы | `C054909t` ABPropBoolean, `C055109v` ABPropInt, `C1OT` ABPropFloat, `C055009u` ABPropString, `C055209w` ABPropJson | id + значение по умолчанию в точке вызова |
| Менеджер синхронизации | `C0D2` (`ABPropsManager`) | хранение, hash, refresh, backup, обновление pre-chatd |
| Запрос / ответ | `C27646BzW` (запрос), `C28894Cgv` (ответ + ошибка) | `<iq xmlns="abt">` |
| Триггер | ветка default в `RunnableC48591z1` (лог `MessageHandler/maybeGetNewAbProps`), `C1S0` — обработчик `<... abprops/>` | когда отправляется fetch |
| Props групп | `C41861nA` (`GroupAbPropsManager`), `C502324k` (триггер), `C28900Ch1` (ответ) | значения по группам |
| MobileConfig | `C053409d` (фабрика), `C054709r` (`InterfaceC054609q`), `C06510El` (таблица Stable ID), `C34081Wt` / `C34091Wu` (типизированные лямбды), `C06460Eg`, `C053809h` (таблица overrides), `CQN` + `C29448CqB` (fetcher), `C41251mA` (координатор fetch) | движок на нативной основе, MEX fetch |
| Exposure | `C42831om`, `BxP`, `C27952CBv`, событие WAM `C44051qo` (5504) | ключи exposure |
| Offline AB | `C24976ApB`, `C27629BzE`, `C60839RQl`, `ON0` / `ON1` / `C53973OMy`, `ConfigVariable` | локальное назначение экспериментов |
| Наблюдатели | `C0NE` (3 колбэка), 46 реализаций, например `CY8` | реакция на изменённые значения |

Ключевые моменты:

- Пространство id флагов — единое числовое пространство (максимальный id **39140**, 21 424 id со значением по умолчанию). `C05Z.A00(n)`, `C1XG.A0I(n)`, целые типы IQ и id WAM — другие числовые пространства (раздел 12).
- Имена до клиента не доходят. Их нет ни в таблицах значений по умолчанию, ни в ответе синхронизации (только `config_code`), ни в ресурсах.
- Есть три параллельных пути синхронизации: `abt` IQ (уровень пользователя), `abt` IQ с `group=` (уровень группы) и MEX fetch MobileConfig (раздел 4).

---

## 2. Модель флагов

### 2.1 Типы и таблицы значений по умолчанию (found, `C08J`)

Пять неизменяемых карт строятся в конструкторе `C08J` (`buildKeepingLast`, поэтому дублирующиеся put в декомпилированном коде безвредны). Количества — уникальные id на карту:

| Тип | Карта | Аксессоры в `C00D` | Id | Пример |
|-----|-------|--------------------|----|--------|
| bool | `A1A()` | `A15(id)`, `A18(ABPropBoolean)`, `A0E(...)` | 16 668 (1 237 по умолчанию `true`) | `9667` true |
| int | `A1C()` | `A0b(id)`, `A0f(ABPropInt)`, `A02(...)` | 3 530 | `996` 604800 |
| float | `A1B()` | `A0Z(id)`, `A0a(ABPropFloat)`, `A00(...)` | 177 | `31535` 0.0 |
| string | `A1E()` | `A0j(id)`, `A0n(ABPropString)`, `A08(...)` | 867 | `34350` regex |
| JSON | `A1D()` | `A0p(id)`, `A0r(ABPropJson)`, `A09(...)` | 182 | `21995` `{}` |

Ни один id не присутствует в двух картах. Статические литеральные чтения (`A15(n)`, `A0b(n)`, `A0j(n)`, `A0Z(n)`, `A0p(n)`): 16 355 мест вызова в `p000X` и `com`; чтения через дескрипторы идут сверх этого (места создания: 492 ABPropBoolean, 482 из них различных, 259 ABPropInt, 30 ABPropFloat, 66 ABPropString, 12 ABPropJson).

Разрешение значения по умолчанию (found, `C00D.A0D`, `A01`):

| Шаг | Правило |
|-----|---------|
| 1 | значение, кэшированное в памяти для этого процесса |
| 2 | сохранённое серверное значение в prefs `ab-props` под ключом `String.valueOf(id)` |
| 3 | значение по умолчанию из карты типа данного id |
| 4 | значение по умолчанию дескриптора ABPropX в точке вызова (только если в карте нет записи) |
| 5 | ничего: `IllegalArgumentException("Unknown BooleanField: <id>")` (int: `Unknown IntField`) |

Для всех 482 различных дескрипторов ABPropBoolean id есть в карте, а production-значение по умолчанию дескриптора равно значению по умолчанию в карте. `debugDefaultValue` у ABPropBoolean отличается от production-значения у 182 из них, но нигде не читается, кроме `equals` / `hashCode` / `toString` (smali: поле `A02` упоминается только внутри `09t`; аксессоры используют только id и production-значение). В этой сборке оно не влияет на выполнение.

### 2.2 Разбор значения при сохранении (found, `C0D2.A00`)

| Карта id | Хранится как | Разбор |
|----------|--------------|--------|
| bool | `putBoolean` | `Integer.parseInt(config_value) != 0` (формат в сети `"1"` / `"0"`) |
| int | `putInt` | `Integer.parseInt` |
| float | `putFloat` | `Float.parseFloat` |
| string | `putString` | как есть |
| JSON | `putString` | проверяется через `new JSONObject(...)`; при ошибке логируется `ABPropsManager/invalid format for config; configCode=...`, prop не сохраняется |
| id нет ни в одной карте | `putString` | сохраняется как строка; типизированное чтение такого id не имеет значения по умолчанию и бросает исключение (2.1 шаг 5) |

В отличие от таблицы WA Web (неизвестные коды отбрасываются), Android сохраняет неизвестные коды как строки (found).

### 2.3 Опции чтения (found, `C00F` = `AbPropsOptions`)

| Константа | exposureOptions | firstAccessValue | Применение |
|-----------|-----------------|------------------|------------|
| `A03` | WITH_EXPOSURE_LOGGING (1) | false | по умолчанию для всех обычных чтений (`A15`, `A0b`, ...) |
| `A02` | WITH_EXPOSURE_LOGGING | true | `A19(...)`, `A16`, чтения при начальной загрузке MobileConfig |
| `A06` / `A05` | WITHOUT_EXPOSURE_LOGGING (0) | false / true | `A00()` выводит их |
| `A04` | WITH_URGENT_EXPOSURE_LOGGING (2) | false | хранилище pre-chatd, когда флаг **24317** включён |

`firstAccessValue = true` закрепляет первое прочитанное в процессе значение в `C00D.A07` (ConcurrentHashMap); последующие чтения этого id возвращают закреплённое значение даже после синхронизации (found, `C00D.A0D`, `A0i`). Обычные чтения используют кэш `A0P`, который `A0s()` очищает после каждой синхронизации.

### 2.4 Путь чтения и источник истины (found, `C00D.A07` smali; названия переключателей выведены из использования)

```
read(id)
  ├─ A14() true  (A0E && A0b && !A0S)  and A08 set  and MobileConfig context present
  │      └─► MobileConfig value via C34081Wt/C34091Wu  (Stable ID lookup, C054709r.B6F)
  └─ else
         ├─ legacy value: cache A0P ► prefs "ab-props" ► default map
         └─ if A0E && A0G (shadow): also read MobileConfig and compare (A0C)
```

| Поле | Источник | Значение (inferred) |
|------|----------|---------------------|
| `A0F` | pref `23048` (bool), только `C08J` | MobileConfig инициализирован для этого аккаунта |
| `A0E` | `A0F` или pref `27668` (int) > 0 | MobileConfig активен (только `C08J`; false для `C0D9`, `C0ER`) |
| `A0b` | pref `24896` | MobileConfig — источник истины |
| `A0S` | pref `25403`, перечитывается в `A0s()` | override обратно на legacy-путь |
| `A0G` | pref `22646` | shadow-сравнение включено |
| `A0c` | pref `38895` == 1 | кэш на чтение `A0d` для значений MobileConfig |
| `A08` | AtomicBoolean, устанавливается в `C054709r.BN4` (инициализация MobileConfig) | MobileConfig готов; только тогда выбирается путь MobileConfig (found); в конструкторе сбрасывается в false |

Все шесть сами являются AB props, читаются прямо из файла prefs при конструировании (found). Shadow-режим строит запись сравнения `N25` и отправляет событие field-stats (`C56612Vl`, значение `mobile_config_inconsistent_value`) с сэмплированием 1 из флага **22647** (по умолчанию 10) (found). Когда источником является MobileConfig, а у id нет Stable ID, типизированная лямбда возвращает `false` / `0` / `""` с источником значения `INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`, а не значение из карты по умолчанию (found в `C34081Wt`; влияние на 70 id, имеющих только значение по умолчанию, inferred).

---

## 3. Слой MobileConfig

### 3.1 Stable IDs (found, `C06510El.A0J`)

`long[39141]`, индексируется config code, 21 380 ненулевых записей. `C054709r.B6F(id)` возвращает запись (0 = нет). 21 354 id есть и в картах значений по умолчанию, и в этой таблице; 70 id только в значениях по умолчанию, 26 только в Stable ID.

| Биты | Поле | Свидетельство |
|------|------|---------------|
| 0-15 | индекс слота | `C053809h.A00`: `j & 65535`; значение inferred |
| 32-47 | индекс конфигурации, `0..20780`, по одному на запись в порядке id | `C06460Eg.A00`: `(j >>> 32) & 65535`, `C053409d.A08(int)` |
| 48-53 | тип значения: 1 bool, 2 int, 3 string или JSON, 4 float | перекрёстная сверка с картами значений по умолчанию, без исключений |
| 54-59 | тип unit: 1 SESSIONLESS (564 id), 2 SESSIONBASED (20 781), 6 GROUP (35) | перекрёстная сверка; раздел 3.2 |
| 60-63 | значение `2` тогда и только тогда, когда bool по умолчанию `true` | 1 231 из 1 231 id; 6 id с true по умолчанию не имеют Stable ID |

### 3.2 Типы unit и `params_map_v4_u*` (found)

`assets/params_map_v4_u<N>.txt` загружается `N3E`, где `N` = тип unit MobileConfig (`AbstractC24817AmY.A00`): 0 NULL_VALUE, 1 SESSIONLESS, 2 SESSIONBASED, 3 PAGEID, 4 ADMINID, 6 GROUP, 7 FAMILY_DEVICE_ID, 8 FRLID, 9 AD_ACCOUNT_ID, 10 WEARABLE_DEVICE_OWNER_ID. Суффикс — тип unit, а не ширина значения. Нативная библиотека содержит ту же строку формата `params_map_v4_u%d.txt` (`libmobileconfig-jni.so`).

| Файл | Unit | Записей | Ключ версии | Id внутри диапазона кодов WA |
|------|------|---------|-------------|------------------------------|
| `u1` | SESSIONLESS (доступен до входа) | 575 | 565 | 564 |
| `u2` | SESSIONBASED | 20 844 | 20785 | 20 781 |
| `u4` | ADMINID | 72 | 2 | 0 (id 112607..121623) |
| `u6` | GROUP | 35 | 35 | 35 |

Запись (8 байт, два little-endian u32, раскладка заголовка как в файле: magic `v4`, проверка `0x7fff`, ключ версии, количество, 32-символьный hash):

| Поле | Находка |
|------|---------|
| `int2 >> 12` | config code WA: для `u1`/`u2`/`u6` совпадает с таблицей Stable-ID (564 / 20 781 / 35 совпадений) и картами значений по умолчанию; младшие 12 бит равны 0 у всех записей, кроме нескольких |
| младшие 16 бит `int1` | маска типа значения: `0x881` bool, `0x1001` int, `0x1801` string/JSON, `0x2001` float (`u2`); бит 15 установлен ровно для bool по умолчанию `true` (25 + 1 206 = 1 231) |
| `int1 >> 16` | сквозной номер слота (inferred) |
| id `u4` | вне диапазона кодов WA; назначение unknown |

Младшие 9 бит `int1` равны только 1 или 129; это не id параметра.

35 id GROUP (found): 18205, 23245, 23246, 23397, 23398, 24075, 26013, 26269, 26270, 26862, 27009, 27025, 27247, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 33673, 34075, 34277, 34333, 35211, 35227, 35639, 35772, 36156, 36504, 36505, 37523, 37524, 38082, 38083. Флаг **18205** читается по группам в `GroupAbPropsManager` (раздел 4.7).

### 3.3 MobileConfig fetch через MEX (found, `CQN`, `C29448CqB`)

MEX-мутация `MetaConfigFetchMutation`, схема `whatsapp-android-www`, doc_id **28207206725568030**, корневое поле `xwa2_mobile_config_fetch`. Поля ввода, задаваемые в `CQN`: `api_version`, `fetch_type`, `unit_type`, `unit_id`, `device_id`, `query_hash`, `query_string`, `bln_queries`, `mc_debug_id`, `mobile_app_universe_type`; всегда null на прочитанных путях: `batch_size`, `bln_li_hashes`, `bool_opt_policy`, `contact_point`. Лог: `WAMobileConfigFetcher/fetchWwwConfigs/request unit_type=...`. Ответ: blob конфигурации, передаваемый нативному менеджеру (`onComplete(true, blob)`), а также `ep_refresh_id` и `ab_key`. `ab_key` сохраняется как `mc_expo:sys:ab_key`.

`C41251mA` (`MobileConfigFetchCoordinatorImpl`) решает, когда этот fetch запускается после fetch AB props: ABPropInt **36185** (по умолчанию 0) выбирает опцию: значение 2 ждёт возобновления офлайна (`waiting for offline resume`), любое другое значение запрашивает сразу; значение 1 сверяет сохранённую версию fetch по unit с версией `abprops` (`C054709r.A01`), delta-запрос сравнивает версию приложения последнего handle с `2.26.41.6`. `C054709r.CpO` вызывает `updateConfigs`, лог колбэка `WAMobileConfigFetcher/updateConfigs() callback: succeeded=`; при успехе сохраняется `last_full_fetch_ms:<unit>:<key>`.

Stanza `<success>` при логине также несёт `mc_ep_version` (версия emergency-push MobileConfig) рядом с `props` и `abprops` (found, `HandlerThreadC12340b0`); потребитель не прослежен.

---

## 4. Синхронизация props

### 4.1 Запрос (found, `C27646BzW.A00(boolean force, boolean delta, int refreshId)`)

```xml
<iq to="s.whatsapp.net" type="get" id="..." xmlns="abt">
  <props protocol="1" hash="<stored config_hash | empty>" [refresh_id="<last_version>"]/>
</iq>
```

| Атрибут | Правило |
|---------|---------|
| `protocol` | константа `1` |
| `hash` | сохранённый `ab_props:sys:config_hash`; пустая строка, если задан `force` или `delta` либо ничего не сохранено |
| `refresh_id` | только если задан `delta` и `refreshId > 0`; значение = сохранённый `ab_props:sys:last_version` |
| отправка | `MessageClient.A0W(callback, node, id, 220, 32000L)`: целочисленный тип IQ-запроса 220, таймаут 32 000 мс |

### 4.2 Ответ (found, `C28894Cgv.CFS`)

```xml
<iq type="result"><props ab_key="..." hash="..." refresh="86400" refresh_id="N" [delta_update="true"]>
  <prop config_code="20548" config_value="1" config_expo_key="..."/>     <!-- one per changed flag -->
  <prop event_code="1094" sampling_weight="N"/>                         <!-- event sampling, no config_code -->
</props><erid>...</erid></iq>
```

| Элемент | Обработка |
|---------|-----------|
| `config_code` + `config_value` | типизированное сохранение по 2.2, ключ `String.valueOf(code)` |
| `config_expo_key` | сохраняется как `<code>_expo_key`, если не пуст и значение было сохранено (ключ exposure эксперимента / группы, в которой состоит аккаунт; формат ключа unknown) |
| `ab_key` | сохраняется как `ab_props:sys:config_key`; устанавливается как атрибут WAM **4473** (оба канала), когда MobileConfig не является источником |
| `hash` | хэш содержимого всего набора; сохраняется как `ab_props:sys:config_hash`; ответ без hash и без `delta_update` не меняет значений |
| `refresh` | секунды, по умолчанию 86400; сохраняется x 1000 мс в `ab_props:sys:refresh`, минимум 600 000 мс; delta не обновляет |
| `refresh_id` | версия набора; сохраняется как `ab_props:sys:last_version` (также после delta) |
| `delta_update="true"` | слияние в существующие prefs; hash, key, refresh и `last_refresh_time` не затрагиваются |
| hash присутствует | предыдущие prefs копируются в `ab-props-backup` (предварительно очищается) |
| полное обновление (hash есть, не delta) | хранилище очищается (сохраняются `refresh` и `last_exposure_keys`), все props записываются заново |
| `event_code` + `sampling_weight` | строки без `config_code`; перезаписываются в prefs `field-stats-events-sampling` (ключ = код события, значение = вес); код **1094** также устанавливает `app_launch_event_sampling_weight` |
| `<erid>` | зашифрованный rid: при включённом флаге **3664** очищается, при включённом **6084** и изменённом значении сохраняется как `encrypted_rid` |

После успешного полного обновления: `last_refresh_time` = сейчас (мс), `fetch_app_version` = `2.26.41.6`, счётчики ошибок сбрасываются, наблюдатели уведомляются (4.8).

### 4.3 Триггеры (found, если не отмечено иное)

| Триггер | Условие |
|---------|---------|
| логин `<success abprops="N">` (также `props`, `mc_ep_version`) | версия `N` > сохранённого `last_version`: запрос с `force` + `delta` + `refresh_id`; режим DELTA (лог `versionMismatch`) |
| тот же путь | `last_refresh_time + refresh < now` либо `now < last_refresh_time` (часы переведены назад; ветка прочитана в smali, декомпиляция опускает else): обычный запрос с сохранённым hash; режим FULL (лог `AB Props too old`) |
| входящий дочерний элемент `<... abprops/>` (маршрутизируется вместе с дочерними `log` и `push-config`; родитель `ib` inferred) | `forceFetchABPropsAndMobileConfig`: `A00(true, false, 0)` (пустой hash, полный), когда отправка сообщений готова; затем MobileConfig `BMu` + `CpO` |
| регистрация | pre-chatd fetch (4.6); офлайн-назначение (6) |

### 4.4 Интервал refresh и ошибки (found)

| Элемент | Значение |
|---------|----------|
| интервал по умолчанию | `ab_props:sys:refresh` по умолчанию 86 400 000 мс |
| серверный `refresh` | секунды, x 1000, минимум 600 000 мс |
| учитываемые коды ошибок | 207, 304, 400-503 (`C28894Cgv.Brt`); прочие коды только логируют `unknown error code` |
| учёт повторов | `fetch_attemp_count` +1 на ошибку; при 3 `last_refresh_time` = сейчас и счётчик сбрасывается, так что следующая попытка ждёт один интервал |
| последняя ошибка | `ab_props:sys:last_error_code`, очищается при успехе |
| сбой доставки (`Bog`) | no-op |

### 4.5 Чтения во время окна fetch

`<props>` может прийти после того, как первые экраны прочитали флаги. Первое чтение id до появления данных использует значение по умолчанию; при закреплении `firstAccessValue` (2.3) закреплённое значение по умолчанию остаётся на весь процесс (found); экраны регистрации ждут с таймаутом онлайн-props (строки логов `RegisterPhoneViewModel/cancelOnlineAbPropsTimeout`, `OnlineAbpropsAsyncStatus`, found; точное время ожидания unknown).

### 4.6 Props pre-chatd (found, `C44707Jfc`, `C43414Iwr`, `K49`, `C0D2.A08`)

До подключения аккаунта HTTP-клиент регистрации вызывает `checkPreChatdABProps` (`reg-onboard-abprop-request`) с `ab_hash` (pref `pref_pre_chatd_ab_hash`). Результат содержит новый hash, JSON-массив `expConfigs` из `{config_code, config_value, config_expo_key}`, `ab_key` и задержку до следующего fetch (`pref_pre_chatd_ab_next_fetch_time` = сейчас + задержка). `C0D2.A08` очищает хранилище pre-chatd (`A04`) и перезаписывает его с теми же правилами типизации (2.2) в prefs `ab-prechatd-props`. Exposure хранится в `pref_expo_keys` (JSON-массив `<expo_key>,<timestamp>`) и отправляется через лог воронки регистрации (`abprop_exposure` / `ab_prechatd_exposure`, с `ab_key` из `pref_pre_chatd_ab_key`), а не через WAM 5504. Чтения pre-chatd используют опции `A04` (urgent), когда флаг **24317** включён, иначе `A03`.

### 4.7 Props уровня группы (found, `C41861nA`, `C502324k`, `C28900Ch1`)

```xml
<iq to="s.whatsapp.net" type="get" xmlns="abt"><props group="<group jid>" hash="<cached | empty>"/></iq>
```

Тот же тип 220 и 32 000 мс, что в 4.1. Массив атрибутов запроса состоит из двух элементов: `group` и `hash` (smali). Условия: флаг **16206** (master) и открытие группового чата (`COK` / `Bnc`); пропускается с `reason=cacheValid` до `_nextRefreshTimeInSeconds` либо с `reason=disabled`. Ответ: `hash`, `refresh`, ограниченный диапазоном 600..604 800 с (по умолчанию 86 400), `refresh_id`, `<prop config_code config_value config_expo_key>`, типизируется теми же картами значений по умолчанию (bool, int, float, иначе string). Id находятся в общем пространстве id; тип unit GROUP (3.2) помечает 35 id, предназначенных для этого, а чтение флага для группы выполняется через `A04(groupJid, id)`. Чтения возвращают `null`, когда у группы нет сохранённого значения (вызывающий код тогда использует запасной вариант, не прослежено). Ключи в prefs групп (`groupAbProps`, имя inferred из `C00E`): `<jid>_<id>_value`, `<jid>_<id>_exposureKey`, `<jid>_exposureKeysSet`, `<jid>_nextRefreshTimeInSeconds`, `<jid>_lastRefreshHash`. Типа JSON для значений групп нет.

### 4.8 Наблюдатели (found)

У `C0NE` три колбэка: `BhX` до записи новых значений (событие 34), `Bfk` и `C2K` после (события 33, 32). Пример `CY8` (`PQKeysUploadABPropsObserver`): запоминает флаг **21198** в `BhX`; если в `Bfk` он сменился с `true` на `false`, логирует `PQ_KEYS_UPLOAD_CODE changed from true to false, deleting all kyber prekeys` и ставит в очередь `DeleteKyberPreKeysJob`. 46 классов реализуют `C0NE` (количество по grep).

---

## 5. Хранение на устройстве

| Файл prefs / ключ | Содержимое |
|-------------------|------------|
| `ab-props` (`C08J`, `C0D2.A00`) | значение `<id>`, `<id>_expo_key` и ключи `ab_props:sys:*` ниже |
| `ab_props:sys:config_hash`, `config_key`, `last_version`, `refresh`, `last_refresh_time`, `fetch_app_version`, `fetch_attemp_count`, `last_error_code` | состояние синхронизации |
| `ab_props:sys:last_exposure_keys` (набор строк), `last_daily_expo_key_update` | состояние exposure |
| `ab_props:sys:private_experimentation_id` | случайный id для локальных экспериментов (6) |
| `ab_offline_props:offline_exposure_strings`, `ab_offline_props:offline_exposure_hash_strings` | exposure офлайн-экспериментов (в `ab-props`) |
| `ab-props-backup` | копия предыдущего хранилища, перезаписывается при каждом полном обновлении |
| `ab-prechatd-props` | значения pre-chatd плюс `pref_expo_keys` |
| `ab-private-abprop` | `last_read_time_ms` (обновляется не чаще раза в час) и приватные значения |
| `mc_expo:sys:ab_key`, `mc_expo:sys:last_exposure_keys`, `mc_expo:sys:last_exposure_keys_without_logging` | состояние exposure на стороне MobileConfig |
| `field-stats-events-sampling` | код события -> вес сэмплирования |
| `groupAbProps` | значения групп (4.7) |
| `<dataDir>/mobileconfig/mc_overrides.json`, `id_name_mapping.json` | таблица overrides MobileConfig, карта id-имя (имена файлов найдены в `C053409d`; в APK отсутствуют) |
| `pref_pre_chatd_ab_hash`, `pref_pre_chatd_ab_key`, `pref_pre_chatd_ab_next_fetch_time`, `pref_is_blocking_prechatd_exposure` | состояние pre-chatd (prefs регистрации) |

Все файлы открываются через `C00S.A05(name)` (handle `SharedPreferences` в приватном каталоге данных приложения); добавляет ли эта фабрика шифрование или обфускацию, не проверялось (unknown).

---

## 6. Exposure, эксперименты, группы

### 6.1 Логирование exposure (found)

| Шаг | Деталь |
|-----|--------|
| 1 | чтение с логированием exposure (2.3) вызывает `A0B(options, this, "<id>_expo_key")` -> `A12` |
| 2 | непустой expo-ключ, ещё отсутствующий в `last_exposure_keys`: добавляется и сохраняется |
| 3 | основное хранилище: `C42831om.A01` отправляет событие WAM **5504** `WamWefrClientExposure` (`wam_wefr_client_exposure`) с debounce не менее 1 с; `BxP` вызывает рантайм WAM (`C0D6.CYl(value, 5029, ...)`; «атрибут» inferred по форме вызова) с ключами через запятую (слияние по источникам, когда флаг **31830** включён) |
| 4 | после полной синхронизации в наборе остаются только ключи, которые новый ответ всё ещё содержит |
| 5 | ежедневная повторная отправка: по колбэку перехода на передний план `A0A0.BvR`, когда с `last_daily_expo_key_update` прошло более 24 ч (`sent_with_daily` = true) |
| 6 | pre-chatd: поток-пульс `C27952CBv` отправляет лог воронки (4.6); режим URGENT запускает его немедленно |

Поля WAM 5504 (имена Falco): `dedup_key`, `device_exp_id`, `exposure_key`, `from_metaconfig`, `sent_with_daily`. `device_exp_id` — строка, производная от объекта идентичности устройства (`C09E.A0J().A03()`); вывод не прослежен (unknown).

### 6.2 Id экспериментов и групп

| Id | Где | Значение |
|----|-----|----------|
| `config_expo_key` | на каждый `<prop>` | ключ exposure ветки эксперимента; непрозрачен для клиента, только сравнивается и логируется |
| `ab_key` | атрибут `<props>` | ключ всего назначенного набора; атрибут WAM 4473 |
| `refresh_id` | атрибут `<props>` | версия набора; сравнивается с `abprops` из `<success>` при логине |
| `hash` | атрибут `<props>` | хэш содержимого, используемый для «без изменений» |
| `private_experimentation_id` | локально | случайный id, используемый как unit для локальных экспериментов |
| `device_id`, `unit_id` | MEX fetch | идентичность unit MobileConfig |

Серверный таргетинг (страна, когорта, процент) не виден; клиент видит только итоговые значения (unknown).

### 6.3 Веса сэмплирования (found)

Строки `<prop event_code sampling_weight>` питают логгер field-stats: на каждое событие вес сэмплирования 1 из N. Событие **1094** (запуск приложения) дублируется в `app_launch_event_sampling_weight`. Ключ — код события WAM, а не id флага.

---

## 7. Локальное вычисление, overrides, пути отладки

### 7.1 Offline AB (found, `C24976ApB`, `C27629BzE`, `C60839RQl`)

Эксперименты, скомпилированные в APK (`C60839RQl.A00`, список `ON0` -> `ON1` -> `C53973OMy` -> `ConfigVariable{id, name, value, type}`), вычисляются по локальной карте информации о пользователе и записываются в хранилище `ab-props` с теми же правилами типизации. Условия (дерево `RM2`) могут использовать только свойства `platform`, `app_version`, `app_build`, `release_channel`, `os_version` (`C0ER.A0B`). Ключи информации о пользователе: `device_id`, `app_build`, `release_channel`, `app_version`, `os_version`, `platform`, `country` (страна SIM), `private_experimentation_id`. В этой бете `app_build` и `release_channel` — константа `beta`. При назначении ключи синхронизации (`config_hash`, `last_refresh_time`, `fetch_app_version`, `last_version`) удаляются, чтобы следующий онлайн-fetch был полным, а критический лог `abprops-offline-assigned-after-registration-verified` срабатывает, когда назначение происходит при `registration_state == 3`. Определения экспериментов здесь не перечислены (unknown).

### 7.2 Overrides MobileConfig (found, эффект inferred)

`C053809h` загружает `mc_overrides.json` (`hasOverridesFile`, `boolOverrideForParam`, `intOverrideForParam`, `stringOverrideForParam`, `doubleOverrideForParam`, ключ — упакованный 64-битный Stable ID), `C053409d.getOrCreateOverridesTable` возвращает её движку. Overrides применяются только к пути MobileConfig, не к legacy-пути prefs. Обращается ли движок к таблице в release-сборке, unknown; свидетельств теста во время выполнения нет.

### 7.3 Deep link `override-abprops` (found)

Хост в манифесте `whatsapp-consumer://override-abprops` (exported alias `DeepLinkActivity`). `IJB` отображает его на id назначения 154. `DeepLinkActivity.A0w` разбирает сегмент пути `bugbash` и параметры запроса `feature_name`, `feature_id`, `category`, `min_app_version`, `ready_to_test_time` и `variants` (JSON-массив в base64 из `{label, abprops:[{abprop_key, abprop_value}]}`) в `BugBashSession` / `BugBashVariant`. Существует причина ошибки `abprop_override_not_allowed`. Кода, который записывает `abprop_key` / `abprop_value` в какое-либо хранилище props, не найдено: `BugBashVariant` упоминается только парсером и его сериализатором, а `bugbash_session` только читается (`C51723Mxj`). Условие допуска и путь применения unknown.

### 7.4 Прочее

| Путь | Деталь |
|------|--------|
| ABPropBoolean `debugDefaultValue` | объявлено (182 отличаются), никогда не читается (2.1) |
| Debug UI | `com.whatsapp.backup.debugscreen.BackupAbPropsUiState` (только имя класса, debug-экран бэкапа) |
| Профайлер на чтение | prefs `31165` (int) и `32010` (bool) питают `C00D.A0H/A0I/A0J` и класс-счётчик (`Pr8`); назначение не выяснено |

---

## 8. Id флагов, упомянутые в других отчётах (проверено в 2.26.41.6)

Каждый id найден в картах значений по умолчанию и в таблице Stable-ID. Типы — типы карт.

| Отчёт | Результат |
|-------|-----------|
| `WA_BAN_SYSTEM_DEEP_EN.md` | 11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 присутствуют, bool по умолчанию false; 12840 и 20278 — карты **JSON** (значения по умолчанию совпадают); 31535 / 31536 — **float**, по умолчанию 0.0. **34166 не флаг**: нет значения по умолчанию, нет Stable ID; `ContactInfoActivity.A0K = C1XG.A0I(34166)` — id внедрения (соседние 34165, 34168, 34169 того же вида). 2923 отсутствует (как и указано) |
| `WA_TCTOKEN_CSTOKEN.md` | все 16 id присутствуют; значения по умолчанию: 996 / 865 / 26897 = 604800, 997 / 909 = 4, 3802 / 22012 = 26, 4063 = 0, 20606 = 2000, все bool id false. `299` — целочисленный тип IQ-запроса privacy-token IQ, а не флаг |
| `WA_META_AI.md` | 25119, 26189, 27083, 37227, 37852, 37054 bool false; **26190 — JSON**, по умолчанию `""` |
| `WA_USERNAME.md` | все 18 присутствуют с задокументированными значениями по умолчанию; **34350 — запись строковой карты** (regex), **21995 — запись карты JSON** |
| `WA_USYNC.md` | все 21 id флагов присутствуют с задокументированными значениями по умолчанию (730 = 35, 471 = 1140, 9667 / 33609 / 20988 = true) |

То же пространство кодов встречается в WA Web: для 11 имён props, известных из публичной таблицы props WA Web, запись Android имеет тот же код, тип и значение по умолчанию (например, 22797 JSON `{}`, 32276 string `info_card, list_card`, 26270 int 1209600, 35639 int -1, 12539 bool true, 25071 / 1133 / 23245 / 28357 / 27009 / 6939 bool false) (found для стороны Android, inferred для «тот же prop»). Id только для Web (3042, 30590, 24037, 25322) не имеют значения по умолчанию в Android. 12 из 16 id уровня группы в Web — это id unit GROUP в Android (3.2).

---

## 9. Именование и категории

| Тема | Находка |
|------|---------|
| Имена | таблица читаемых имён в dex или assets не найдена (поиск двух известных legacy-имён флагов совпал только со строками логов); `id_name_mapping.json` — лишь имя файла времени выполнения в `C053409d` |
| Имена в логах | несколько строк логов повторно используют имена: `PQ_KEYS_UPLOAD_CODE` (21198), `abprop_override_not_allowed`; имена из старых сборок или из WA Web — единственный путь к семантике |
| Категории | поля категории нет. Структура задаётся типом unit (SESSIONLESS 564, SESSIONBASED 20 781, GROUP 35) и типом значения |
| Чаще всего читаются | чаще всего читаемые литеральные id: **20548** (bool true, 511 мест), **9970** (false, 312), **1107** (false, 151), **12267** (true, 147), **1600** (string `{"allowed_product_type":"none"}`, 146), **27008** (false, 104), **13989** (int 7, 87). Семантика не выяснена |

---

## 10. Каталог флагов по областям (значения по умолчанию найдены в `C08J`; использование взято из других отчётов и перепроверено здесь)

### 10.1 Синхронизация и инфраструктура MobileConfig

| Флаг | Тип | По умолчанию | Что контролирует |
|------|-----|--------------|------------------|
| **23048** | bool | false | MobileConfig инициализирован (`A0F`) |
| **27668** | int | 0 | `AbstractC06100Cm.A0E`; > 0 активирует MobileConfig (`A0E`) |
| **24896** | bool | false | MobileConfig — источник истины (inferred) |
| **25403** | bool | false | возврат к legacy-источнику (inferred) |
| **22646** | bool | false | shadow-сравнение |
| **22647** | int | 10 | сэмплирование shadow-лога |
| **38895** | int | 0 | `== 1`: кэш MobileConfig на чтение |
| **26524**, **28443**, **30441**, **30556** | bool | false | опции фабрики MobileConfig (`CbW`, `BMu`) |
| **26525** | int | 600 | опция фабрики MobileConfig (`CbW`), единица не выяснена |
| **26640** | bool | false | параметр инициализации MobileConfig (`BN4`) |
| **35778** / **36185** | int | 0 | фаза инициализации / опция времени fetch (`C054709r.APn`, `C41251mA.A00`) |
| **24317** | bool (SESSIONLESS) | false | чтения pre-chatd используют urgent exposure |
| **31830** | bool | false | слияние атрибута exposure 5029 по источникам |
| **16206** | bool | false | master-условие props групп |
| **18205** | bool (GROUP) | false | чтение по группам в `GroupAbPropsManager` |
| **3664** / **6084** | bool | false | очистка / установка `encrypted_rid` |
| **21198** | bool | false | `PQ_KEYS_UPLOAD`: загрузка prekeys Kyber; `true` -> `false` удаляет их |

### 10.2 Баны и integrity (`WA_BAN_SYSTEM_DEEP_EN.md`)

11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 (bool false); 12840 (JSON `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}`); 20278 (JSON `{"max_messages": 10000, "farthest_time_days": 30}`); 31535 / 31536 (float 0.0).

### 10.3 Privacy token и cstoken (`WA_TCTOKEN_CSTOKEN.md`)

| Флаг | Тип | По умолчанию |
|------|-----|--------------|
| **996** / **997** | int | 604800 / 4 |
| **865** / **909** | int | 604800 / 4 |
| **4063** | int | 0 |
| **3802** / **22012** | int | 26 / 26 |
| **20605** / **14303** / **15491** | bool | false |
| **20606** | int | 2000 |
| **24915** / **24941** / **18639** / **25253** | bool | false |
| **26897** | int | 604800 |

### 10.4 Meta AI, username, USync

| Отчёт | Флаги (по умолчанию) |
|-------|----------------------|
| `WA_META_AI.md` | **26189**, **27083**, **25119** (нет ридера), **37227**, **37852**, **37054**: bool false; **26190** JSON `""` |
| `WA_USERNAME.md` | **4745**, **20189**, **23817**, **21199**, **16033**, **8421**, **12402**, **28678**: bool false; **21995** JSON `{}`; **20494** 3, **20459** 35, **34347** 4, **34348** 6, **28127** 30, **29327** 60; **34350** string `^([0-9]{4}\|[A-Z0-9]{6})$` |
| `WA_USYNC.md` | **5751**, **5839**, **20798**, **29769**-**29771**, **9732**, **33432**, **14565**, **26739**, **31261**: bool false; **9667**, **33609**, **20988**: true; **730** 35, **471** 1140, **37780** 0 |

### 10.5 Уровень группы (unit GROUP, 35 id)

Bool false: 18205, 23245, 23246, 26013, 26269, 26862, 27009, 27025, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 34075, 35211, 35772, 36156, 36504, 36505, 38082, 38083. Int: 26270 (1209600 с = 14 дней), 27247 (0), 23397 / 23398 / 24075 / 34277 / 34333 / 35227 / 35639 / 37523 / 37524 (-1). String: 33673 (`none`). Имена для 26270, 23245, 23246, 26269, 30905, 30906, 28357, 28358, 27009, 27025, 35639, 35772 взяты из WA Web (история группы и настройки опросов; inferred).

---

## 11. Baileys (`baron-baileys-v2`, `src/Socket/chats.js`)

| Тема | Baileys | Android 2.26.41.6 |
|------|---------|-------------------|
| запрос пользователя | `fetchABProps(protocol='1', hash, refreshId)`: `<props protocol hash? refresh_id?>` в `xmlns="abt"` | та же форма; `hash` присутствует всегда (пустой при force), `refresh_id` только с delta |
| запрос группы | только `{ group }` | `group` + `hash` (массив из 2 в smali) |
| ключи ответа | `reduceBinaryNodeToDictionary(props, 'prop')`: словарь `config_code` -> `config_value` | типизированное хранение; `config_expo_key`, строки `event_code`, `hash`, `refresh`, `refresh_id`, `delta_update` все используются |
| поиск | по имени флага (`abProps['stella_interop_enabled']`) | только по числовому коду |
| legacy props | `fetchProps`: `xmlns="w"` `<props protocol="2" hash>` именованные props | построитель не найден; имена встречаются только в словаре токенов stanza (`AbstractC40911lb`) |
| refresh | нет (один раз за соединение) | интервал + проверка версии + push |

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| `abProps['<name>']` равен `undefined` | ответ `abt` содержит только `config_code` | ключ по коду; пространство кодов — то, что в разделе 8 |
| в словаре появляется ключ `undefined` | у строк `event_code` / `sampling_weight` нет `config_code` | пропускать строки без `config_code` |
| устаревшие значения | нет обработки hash / refresh / `refresh_id`, нет delta | сохранять `hash`, `refresh`, `refresh_id`; отправлять `hash` и `refresh_id` в следующем запросе |
| bool читается как truthy-строка | `config_value` равно `"1"` / `"0"` | разбирать по типу (`!= 0`) |

---

## 12. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| `ABPropsManager/onABPropError; unknown error code: N` | ошибка вне 207 / 304 / 400-503 | нет; счётчик не увеличивается |
| 3 неудачных fetch, нет повтора в течение суток | `fetch_attemp_count` достиг 3, `last_refresh_time` = сейчас | ждать один интервал или повышения версии `abprops` при логине |
| `AbPropProtocolHelper/onReceiveABProps failed to parse response` (`C49828Lvo`) | некорректный `<props>` | исключение пробрасывается повторно, хранилище не тронуто |
| `ABPropsManager/invalid format for config; configCode=N; value=V` | нечисловое int/float или некорректный JSON | этот prop пропускается |
| `IllegalArgumentException: Unknown BooleanField: N` | типизированное чтение id без значения по умолчанию в карте и без значения по умолчанию в дескрипторе | добавить значение по умолчанию; `N` — config code |
| чтение MobileConfig возвращает `false` / `0` / `""` | у id нет Stable ID (`INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`) | читать через legacy-путь |
| `WAMCEvaluation/invalid json format; key=N` | значение JSON-флага не разбирается на пути MobileConfig | возвращается пустой `JSONObject` |
| `GroupAbPropsClient/malformedResponse ... noPropsChild` / `parseFailed` | ответ группы без `<props>` или ошибка разбора | значение группы не сохраняется |
| `GroupAbProps/fetchSkip reason=cacheValid` / `disabled` | до `_nextRefreshTimeInSeconds` / флаг 16206 выключен | нет |
| `ABPreChatdProps/exception ... error add expo key` | повреждён JSON `pref_expo_keys` | ключ не добавлен |

---

## 13. Ключевые различия

| Не путать | Деталь |
|-----------|--------|
| config code и id внедрения | `A15(20548)` — флаг; `C05Z.A00(66)`, `C1XG.A0I(34166)`, `C00C.A02(61)` — id зависимостей |
| config code и тип IQ-запроса | `A0W(..., 220, 32000L)` (220 здесь, 299 в privacy-token IQ) — целочисленный тип запроса |
| config code и id WAM | 5504 — событие, 5029 и 4473 — атрибуты WAM, 1094 — код события в строках сэмплирования |
| config code и Stable ID | код (<= 39140) индексирует таблицу; Stable ID — 64-битный спецификатор MobileConfig |
| `abt` IQ, props `w` и таблица БД `props` | `abt` = числовые AB props; legacy props `w` = именованные серверные props; SQL-таблица `props` = локальное хранилище ключ-значение |
| props пользователя и props группы | то же пространство id, те же карты; значения групп хранятся в `groupAbProps`, ключ — jid группы, unit GROUP |
| `ab_key`, `config_expo_key`, `hash`, `refresh_id` | ключ набора / ключ эксперимента на каждый prop / хэш содержимого / версия |
| `abprops` при логине и `<props refresh_id>` | текущая версия сервера и версия, сохранённая из последнего ответа |
| MEX `MetaConfigFetchMutation` и `abt` | blob MobileConfig и legacy числовые props; оба работают, когда MobileConfig активен |
| production-значение по умолчанию и debug-значение по умолчанию | читается только production-значение |
| закрепление первого доступа и обычный кэш | закреплённые значения переживают синхронизации до конца процесса |
| офлайн-назначение и онлайн | офлайн-эксперименты пишут в то же хранилище, затем принудительно запускают полный онлайн-fetch |

---

## 14. Полный поток

```
[Server]            [Login]                 [C0D2 / C27646BzW]               [C08J reads]         [WAM]
   │ <success abprops=N props mc_ep_version>   │                                   │                 │
   ├──────────────────►│ N > last_version? or  │                                   │                 │
   │                   │ last_refresh+refresh<now                                  │                 │
   │                   ├──────────────────────►│ <iq xmlns=abt>                    │                 │
   │◄───────────────────────────────────────── │  <props protocol=1 hash [refresh_id]>             │
   │ <props ab_key hash refresh refresh_id [delta_update]>                          │                 │
   │   <prop config_code config_value config_expo_key/> ... <prop event_code sampling_weight/>      │
   ├──────────────────────────────────────────►│ typed store per id (bool/int/float/string/JSON)   │
   │                                           │ backup, hash, refresh, last_version, ab_key       │
   │                                           ├─ observers BhX ► write ► Bfk / C2K ──────────────►│
   │                                           │ A0s(): clear read cache                           │
   │                                           │                                   │                 │
   │ <ib><abprops/>  (force, empty hash) ─────►│                                   │                 │
   │                                           │                                   │                 │
   │                                      A15(id) / A0b(id) / A0j(id)...           │                 │
   │                                           │          cache ► prefs ► default map ► (descriptor)│
   │                                           │          MobileConfig path if A0E && A0b && !A0S   │
   │                                           │                                   ├ first read ────►│ 5504 exposure
   │                                           │                                   │ + 24 h resend   │ 5029, 4473
   │                                           │                                   │                 │
   │ MEX MetaConfigFetchMutation ◄─────────────┼── C41251mA (option 36185) ────────┤                 │
   │ xwa2_mobile_config_fetch {blob, ep_refresh_id, ab_key} ───► native MobileConfig, Stable IDs    │
   │                                           │                                   │                 │
   │ <iq xmlns=abt><props group hash> (group opened, flag 16206) ► groupAbProps ► A04(groupJid,id)   │
```

---

## 15. Неизвестное

| Тема | Причина |
|------|---------|
| Семантика флагов | имён нет; семантика только там, где её определяет место вызова или другой отчёт |
| Серверное назначение | таргетинг, проценты раскатки, определения экспериментов в клиенте отсутствуют |
| Родительская stanza push-дочернего элемента `abprops` | обработчик зарегистрирован под кодом сообщения 235; `ib` inferred |
| Связь между `abprops` при логине и аргументом версии триггера | триггер принимает `Integer`; разбор логина устанавливает `AtomicReference`; связь inferred |
| `mc_overrides.json` MobileConfig в release-сборках | код таблицы есть; свидетельств, что к ней обращаются или что пользователь приложения может в неё писать, нет |
| Условие допуска и путь применения `override-abprops` | причина `abprop_override_not_allowed` существует; записи в хранилище props не найдено |
| Вывод `device_exp_id`, формат `config_expo_key` | не прослежено |
| Биты 0-15 Stable-ID, записи unit `u4`, `int1 >> 16` | значение не выяснено |
| Prefs `31165`, `32010`, флаг `35778`, значения `36185` 1 / 2 | прочитано частично (`Pr8`, координатор) |
| Поведение 70 id, имеющих только значение по умолчанию, под MobileConfig | типизированная лямбда возвращает нулевые значения (found); влияние на функции не прослежено |
| Семантика delta на стороне сервера | какие props несёт delta |
| Реальный трафик и актуальные выдаваемые значения | только статический анализ |
