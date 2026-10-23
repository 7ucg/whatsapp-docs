<!-- src-sha1: a1b0d0e9f7c1a5fa3cd781b21b55668d3205ba24 -->
# WhatsApp Username — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** проверка / установка / резервирование / удаление username, ключ username (PIN), связь с LID, приватность и видимость, операции w:mex GraphQL (doc_id, переменные, ответы), уведомления, поиск через USync, правила валидации, feature-флаги, заметки по Baileys

---

## 1. Что такое username (технически)

Username — это серверный идентификатор, привязанный к аккаунту; он нужен, чтобы с контактом можно было связаться без раскрытия номера телефона. Все утверждения основаны на статическом анализе декомпилированного APK. Уровни: **found** = прочитано в коде или ассетах, **inferred** = выведено из кода, **unknown** = не выяснено.

Функция построена на трёх слоях:

| Слой | Транспорт | Для чего используется |
|-------|-----------|----------|
| Управление собой | `w:mex` IQ, persisted GraphQL (конфиг `whatsapp-android-mex`) | check, set / reserve / delete, get, set / delete ключа (PIN), multi-check |
| Поиск других | USync (`xmlns="usync"`) и вариант MEX `UsyncQuery` | разрешить `@username` (+ ключ) в LID, получить username известного JID |
| Push | уведомления MEX | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Между устройствами | app-state sync (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (содержит `username`) |

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| Менеджер username | `C122815Lj` | вызовы `UsernameGet`, `UsernameSet`, обновление локального состояния, хук rate-limit |
| Проверка доступности | `C67402tT` | вызов `UsernameCheck` + маппинг ответа |
| Multi check | `C76333Kg` | `UsernameCheckMulti`, порции по 10 |
| API ключа | `MexUsernamePinProtocolApi` | `UsernamePinSet` (установка / удаление ключа) |
| Локальное состояние / prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| Enum состояния | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Режим допустимости | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Хранилище rate-limit | `C67942uO` | backoff после 429 / 503 / 529 |
| Локальный валидатор | `C82003fB.A04`, `C1187754z` | длина, набор символов, правила для точек, regex |
| Валидатор ключа | `C1176550d` (+ `AbstractC111284pZ`) | формат ключа |
| VM ввода ключа | `UsernamePinEntryViewModel` | отправка ключа для чужого username |
| Клиент USync | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | сборщик / парсер классической станзы usync |
| MEX USync | `C229259vZ`, `O0F` | `UsyncQuery` с `include_username` |
| Обработчики уведомлений | `C49822Lvi`, `C49821Lvh`, анонимный `X.2YG` в `AbstractC20380p4` | set / delete / update |

Именование: в интерфейсе PIN называется **username key** (строки "Username key", "Add a username key to control who can contact you"). В протоколе и коде используется `pin`.

---

## 2. Операции MEX (doc_id)

### 2.1 Где находятся doc_id

doc_id не хранятся литералами в `java_src`. Клиент отправляет имя операции (`"UsernameSet"`, ...) вместе с именем конфига `"whatsapp-android-mex"` (found, `C16880is`). Числовой id читается из `assets/whatsapp-android-mex_client_persist_ids.json`: `EnumC17010j7.WHATSAPP_ANDROID_MEX` указывает на этот файл, `C17040jA.CMg(op)` возвращает поле `doc_id`, `AGb(op)` — поле `client_doc_id` (found). Какой из двух аксессоров заполняет атрибут `query_id`, до конца не прослежено (unknown); более ранние захваты на 2.26.26.4 показывают `query_id`, равный `doc_id`.

Приведённые ниже doc_id **found** в ассете 2.26.41.6:

| Операция | doc_id | Тип | Место вызова | Класс ответа |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | не найдено | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Примечания:
- `UsernameGetRecommendationsQuery`: имя встречается только в JSON ассета. Ни один класс в `java_src` не ссылается на него по строке (found). Переменные и ответ unknown.
- У трёх имён уведомлений (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) нет записи в persist-id ассете. Это типы уведомлений, а не запросы (см. 7).
- В ассете для каждой операции есть `operation_name_hash`, `operation_text_hash` и `client_doc_id`. Пример `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Конверт

Строится в `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Поле | Правило (код) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | `get` для каждой операции, включая мутации |
| атрибут `query_id` | устанавливается, только если длина от 1 до 20 символов |
| тело | JSON `{"queryId": ..., "variables": {...}}`, от 1 до 8448000 байт |
| null-переменные | `C16770ig.A03(k, null)` и `A02(k, null)` пропускают ключ, то есть отсутствующее значение означает, что ключ не отправляется |

Станзы живых сессий с провода здесь не приводятся; эта сборка анализировалась только статически.

---

## 3. Операции подробно

### 3.1 UsernameCheck

Переменные (found, `C67402tT.A00`):

| Переменная | Тип | Условие |
|----------|------|-----------|
| `username` | string | всегда |
| `include_suggestions` | bool | всегда (UI передаёт `false` в пути typed-check `C64H` case 21) |
| `source` | string | только если не null |
| `session_id` | string | только если не null |

Маппинг `source` (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, иначе -> null (не отправляется).

Путь ответа (found, ветка по умолчанию `C77183Np`): `data.xwa2_username_check`

| Поле | Тип | Использование |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | читается только при `INVALID` |
| `rejection_reasons` | список `C4G8` | читается только при `INVALID` |
| `suggestions_eligible` | bool | по умолчанию `true`, если поле null |

Значения `C4G8` (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Маппинг: `SUCCESS` -> `C76283Kb` (доступен); `INVALID` -> `C76303Kd` (недоступен, несёт suggestions + reasons); `UNSET` -> ни одна ветка не присваивает результат (callback получает предыдущую/null переменную; поведение unknown). Активный локальный backoff -> `C76293Kc` (ошибка с кодом rate-limit из prefs, см. 5.3); failure-callback самого запроса не прочитан.

Причины отклонения определяют текст про связывание аккаунтов ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). В `C82003fB` любая причина, кроме `UNSET`, запускает локальный путь ошибки с кодом 40601 (`A08(40601L)`); пустой список или список только с `UNSET` показывает "Username isn't allowed." Точный поток управления вокруг цикла декомпилирован лишь частично (inferred).

### 3.2 UsernameCheckMulti

| Переменная | Тип | Примечания |
|----------|------|-------|
| `usernames` | **list<string>** | массив через `A00.A0B("usernames", list)`; каталог doc_id типизирует его как `str`, код отправляет список |

Пакетная обработка (`C76333Kg.AG5`): список делится на первые 10 и остаток; остаток обрабатывается после задержки флага **29327** (по умолчанию 60, единица не выяснена). Пустой список возвращает пустую карту без запроса.

Путь ответа `data.xwa2_username_check_multi.results[]` (found): каждый элемент содержит `username` и `response.result` (тот же `EnumC59782gh`). Маппинг: `SUCCESS` -> доступен, `INVALID` -> недоступен (без suggestions, `suggestions_eligible=false`), всё остальное -> ошибка. Имена, отсутствующие в результате, помечаются как ошибка.

Потребитель: `UsernameAvailabilityCache` хранит `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) для каждого имени. Назначение (предзагрузка для подсказок username из Facebook / Instagram, строка `foa_username_prefetch_cache`) — inferred.

### 3.3 UsernameSet (создание / изменение / резервирование / удаление)

Переменные (found, `C122815Lj.A00`):

| Переменная | Тип | Условие |
|----------|------|-----------|
| `username` | string | опускается при null (**delete**) |
| `reserved` | bool | отправляется всегда |
| `session_id` | string | только если не пуст (`C1YW.A08`) |
| `source` | string | только если int источника не null (см. 3.1) |
| `pin` | string | только если не null |

`reserved` вычисляется, а не константа (found). Аргумент `z` (force) = true даёт `false`. Иначе: текущее состояние `ACTIVATED` или `CREATED` даёт `false`; текущее состояние `RESERVED` или режим допустимости `RESERVATION` даёт `true`; все остальные случаи дают `false`. Таким образом `reserved:true` отправляется только для аккаунтов в режиме резервирования или уже имеющих резерв.

Delete — это режим той же операции: `username == null` -> лог-тег `delete`, иначе `set` (также в `MexUsernamePinProtocolApi` для ключа). При null username ключа `username` нет в переменных (found).

Клиентская защита: перед отправкой, если хранилище rate-limit сообщает об активном backoff, вызов завершается локальной ошибкой с `username_creation_rate_limit_error_code` и текстом "rate limit expiration time not reached" (found, `C122815Lj.A03`).

Обработка успеха (`C122815Lj.A01`, found):

| Условие | Записываемое локальное состояние (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username null или пуст | `UNSET`, pref ключа очищается |
| `reserved` был true | `RESERVED` |
| флаг activate | `ACTIVATED` |
| иначе | `ACTIVATED`, если состояние было `ACTIVATED` и имя совпадает с сохранённым, иначе `CREATED` |
| int `source` равен 1 или 2 | pref `username_set_via_account_linking` = (int == 2) |
| отправлен `pin` | pref `username_pin` обновляется |
| флаг teen | pref `is_teen_account` = true |

Запись pref — это `Voip.REJECT_REASON_DECLINED`, который в этой сборке равен пустой строке `""` (found).

Обработка ошибок (`C138725uA` case 2):

| HTTP-подобный код | Действие клиента |
|----------------|---------------|
| 429, 503, 529 | сохраняется backoff (5.3) |
| 304 | считается успехом ("not modified"), локальное состояние всё равно обновляется |
| нет соединения (`C213639Bb`) | результат `C4BO` "no network" |
| другой | `C4BN(code, message)` |

### 3.4 UsernameGet

Переменные: нет (вызов строит пустой набор переменных, found, `C122815Lj.A02`). Помечен `@Deprecated`, заменён suspend-вариантом.

Ответ (found, `C138815uJ` case 34): `data.xwa2_username_get.username_info`

| Поле | Использование |
|-------|-----|
| `username` | сохраняется; пустая строка, если отсутствует |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **ключ возвращается в открытом виде и сохраняется в pref `username_pin`**; пустая строка, если отсутствует |

Маппинг состояний: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED`, если сохранённый username равен возвращённому и локальное состояние было `RESERVED` или `ACTIVATED`, иначе `CREATED`; null state или null `username_info` -> `UNSET`.

Ошибка 404 от сервера очищает локальный username, ключ и состояние (лог `clearSelfUsernameData NOT_FOUND`).

Используется ли вызов как heartbeat — unknown; прежняя заметка "polling heartbeat" не подтверждается кодом этой сборки.

### 3.5 UsernamePinSet (ключ username)

Переменные (found): `pin` (string), опускается при null.

| Действие | Переменные |
|--------|-----------|
| установить ключ | `{"pin": "<key>"}` |
| удалить ключ | `{}` (`A02` вызывает `A00(null)`) |

Имя операции в обоих случаях `UsernamePinSet`; отдельной операции проверки нет. Проверка чужого ключа выполняется в USync (4). Нет соединения: возвращает `C213639Bb("UsernamePinSet")` без запроса.

Ключ может также передаваться в `UsernameSet` (переменная `pin`). `C81793ej.A0x` использует `UsernameSet` с существующим username и новым `pin`, когда username уже сохранён локально (`A00 != null`), и `UsernamePinSet` в остальных случаях (found).

У класса ответа `C48557LJz` в прочитанных файлах нет обращений к полям; форма ответа unknown.

---

## 4. Поиск других пользователей

### 4.1 Классический USync по username (поток с ключом)

Строится в `C18670m9.A06` (jadx упал на этом методе, прочитано из smali `X/0m9.smali`). Для каждой записи запроса `C222649hm`: поле `A0C` = username, `A0D` = ключ, `A05` = LID.

Атрибуты дочернего узла contact (found в smali): `username` всегда; `lid`, когда LID известен локально; `pin`, когда ключ установлен. Дополнительные атрибуты управляются флагом **12402** (по умолчанию `false`): когда флаг выключен, записывается только `username` (found). Имя узла `contact` — inferred из парсера ответа, который читает дочерний `contact` и его атрибут `username` (`C18670m9` строки ~969-975).

```xml
<iq xmlns="usync" to="[server]" type="get">
  <usync mode="query" context="interactive" sid="..." index="0" last="true">
    <list>
      <user><contact username="name" lid="LID" pin="KEY"/></user>
    </list>
    <query><contact/> ... </query>
  </usync>
</iq>
```

Точка входа: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), вызывается из `submitPinForUsername`. Тип синхронизации `EnumC21760rz.A0J`, таймаут 32000 мс. Набор атрибутов `contact`, `pin`, `username` входит в наборы редактирования логов `AbstractC40921lc` (found).

Локальное предварительное разрешение: `A0M.Aol(username)` ищет `lid_row_id` в таблице `lid_display_name`, где `UPPER(username) = UPPER(?)`, сначала самая новая строка (found, `C1S0`). LID, если известен, попадает в атрибут `lid`.

### 4.2 Оценка результата (ввод ключа)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Исход | Условие |
|---------|-----------|
| верный ключ | `UserJid` результата — LID (`C14080dr`) |
| неверный ключ | в результате нет LID: лог `[un-pin] incorrect PIN`, текст ошибки "Wrong key entered" |
| нет сети | `C9qA` код 1 |
| общая инфраструктурная ошибка | `C9qA` код 2 |
| rate limit запрашивающего | `C225769os.A01` true: "Too many attempts made. Try later." |
| rate limit запрашиваемого | `C225769os.A00` true: "This account can't be reached with their key right now..." |

Клиентская проверка кэшированного rate-limit выполняется первой, когда включён флаг **16033** и в JSON-конфиге **21995** `enable_key_rate_limit` равен true (по умолчанию true): `C30P.A00` для собственного LID и для целевого username. Из username убирается `@` (`C0CX.A0i(username, '@')`).

При успехе результатом является **LID**, чат затем адресуется на LID (inferred из проверки `C14080dr`; шаг открытия чата не прослежен).

### 4.3 Получение username известного LID

`C23638AId` (строки ~600-650) строит usync с `<list><user jid="LID"/></list><query><contact/><username/></query>`, режим/контекст из `EnumC21760rz.A0J` (found). Парсер читает `username` как дочерний элемент результата `<usync>` (`C18670m9` строка 586, только если запрос его запрашивал).

### 4.4 MEX USync (`UsyncQuery`)

`C229259vZ.A01` строит `UsyncQuery` (doc_id выше). Существенные части (found):

| Переменная | Использование |
|----------|-----|
| `query_input[]` | одна запись на пользователя: JID (`C493020r.A0C`), необязательный `client_known_username` (только если username запрашивается и не пуст) |
| `include_username` | bool, устанавливается, когда любая запись запрашивает username |
| `include_lid` | bool, запрашивает `lid_info` |
| `telemetry.context` | USync-контекст в нижнем регистре |

Ответ для каждого пользователя: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` полиморфен по хэшу типа: тип-значение, содержащий `username`, или тип-статус с `status` из `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED` логируется как "username not allowed to be queried" и очищает сохранённый username; `NO_CHANGE` сохраняет его. `lid_info.lid_jid` несёт LID.

Шлюз: `ContactSyncHelper` отклоняет путь MEX с логом "cantUseMex as username ab prop is off", если при запросе username не включён флаг **8421** (found; по умолчанию `false`).

---

## 5. Валидация, лимиты, ошибки

### 5.1 Формат username (локально)

Валидатор `C82003fB.A04` (found), проверки в таком порядке:

| Порядок | Проверка | Id ошибки (`C02U`) | Строка сообщения |
|-------|-------|-------------------|----------------|
| 1 | каждый символ в `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | длина >= min (флаг **20494**, по умолчанию 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | длина <= max (флаг **20459**, по умолчанию 35) | 1 | та же строка |
| 4 | нет ведущей `.`, нет завершающей `.`, нет `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | хотя бы одна ASCII-буква | 4 | "Choose a username with at least one letter" |
| 6 | regex (ниже) | проходит или не проходит с 2 | n/a |

Regex, строится `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

Регистр валидатором не нормализуется; локальный поиск `Aol` сравнивает через `UPPER()`, поэтому локально сопоставление нечувствительно к регистру (found). Нечувствителен ли к регистру сервер — unknown. Ведущее подчёркивание разрешено regex; текст UI говорит "start with a letter", что строже regex (found, расхождение).

UI также отклоняет веб-ссылки: "Enter only your username, not a web link" (строка есть, проверка не прослежена).

### 5.2 Формат ключа username

`C1176550d.A00` (found): флаг **34350** — строка regex, по умолчанию `^([0-9]{4}|[A-Z0-9]{6})$`. Если строка флага пуста, запасной вариант — ровно четыре цифры. Невалидный regex логирует `[un-pin] invalid username_key_regex` и принимает что угодно. Границы длины, флаги **34347** (min, 4) и **34348** (max, 6), питают только путь сообщения об ошибке в `UsernamePinEntryViewModel.A0w`. Серверные правила unknown.

Таким образом, прежняя заметка "4-digit PIN" неполна: поставляемое значение по умолчанию принимает четыре цифры или шесть заглавных буквенно-цифровых символов.

### 5.3 Rate limit и backoff

`C67942uO` (found), активно только с флагом **28678** (по умолчанию `false`):

| Элемент | Значение |
|------|-------|
| триггер | ошибка `UsernameSet` 429, 503 или 529 |
| длительность | строка типа `Retry-After`, разобранная как int секунд (`C23680AJt.A00`), иначе флаг **28127** (по умолчанию 30) секунд |
| хранение | prefs `username_creation_rate_limit_backoff_expiry` (мс), `username_creation_rate_limit_error_code` |
| эффект | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` локально завершаются ошибкой до истечения |

### 5.4 Код ошибки в сообщение (`C82003fB.A02`, found)

| Код | Сообщение |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403, 404, 429 | "Couldn't complete your request. Try again." |
| 500, 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406, 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| другой | "We couldn't complete your request. Try again." |

40601-40603 входят в разрешённый набор `AbstractC111104pH.A01` (в прочитанном коде виден только 40603). Их серверная семантика unknown, кроме клиентского текста.

---

## 6. Связь с LID

Всё found, если не указано иное.

| Факт | Подтверждение |
|------|----------|
| Поиск по username разрешается в **LID**, а не в phone JID | тест успеха ключа `userJid instanceof C14080dr` (класс LID); `lid_info.lid_jid` в MEX usync |
| Локальная карта username -> LID | таблица `lid_display_name` (столбцы `username`, `lid_row_id`), запрос в `C1S0` |
| Уведомления идентифицируют пользователя по LID | обработчики set / delete разбирают `LidUserJid` (текст ошибки "Failed to parse LidUserJid") |
| Уведомление delete может нести phone JID | обработчик проверяет `isPnPresent`; при наличии PN приводит PN JID и действует, без PN возвращается |
| Действие синхронизации контакта | `ContactAction` содержит `username` (6) рядом с `lid_jid` (3), `pn_jid` (5); также `LidContactAction` (`lid_contact`, поле SyncActionValue 61) |
| Режим начала чата | поле SyncActionValue **59** `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Найден только sync-кодек; потребителя в UI-коде нет (unknown) |
| Строка функции companion | при привязке companion primary добавляет в свой список функций `username_supported` (флаг 4745 или 20189), `username_reservation_only_mode` (только 20189), `username_account_linking_enabled` (флаг 21199) (`C25056AqU`) |

Inferred: пользователь, существующий только как username, доступен только через LID, пока владелец не поделится номером телефона; строки "If you continue, your phone number will show in existing username chats and calls" (диалог удаления) это подтверждают, но путь раскрытия PN не прослежен.

---

## 7. Уведомления

Обработчики наследуют `AbstractC23194A0r` и регистрируются в `AbstractC20380p4` (found):

| Уведомление | Обработчик | Поведение |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | payload `xwa2_notify_username_on_change`: читает LID (хэш поля 107143) и username; сохраняет через `InterfaceC11470Yz.BNU(lid, username)`; если контакт существует и подходящего вида, обновляет контакт (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | payload `xwa2_notify_username_delete`: читает LID и PN (хэш -983979708); при наличии PN запускает обновление удаления (`C53594Nzh`) |
| `UsernameUpdateNotification` | анонимный `X.2YG` | читает base64-хэш из payload, строит запрос USync с причиной `USERNAME_UPDATE_NOTIFICATION` и `EnumC21760rz.A0Q` (контекст `NOTIFICATION_SIDELIST`, режим `query`; см. WA_USYNC.md), лог `usync triggered for hash` |

Текст, показываемый пользователю: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", то есть сервер может переназначить username (отзыв, pref `is_username_revoked`, `revocation_banner_dismissed_<username>`).

---

## 8. Feature-флаги

Id флагов — это id AB-prop, читаемые через `C08J` (значения по умолчанию из таблиц `C08J`). Все приведённые ниже значения по умолчанию прочитаны в этой сборке.

| Флаг | Тип | По умолчанию | Что управляет |
|------|------|---------|----------|
| **4745** | bool | false | primary: создание username (режим `CREATION`); также объявляется как `username_supported` |
| **20189** | bool | false | primary: режим только резервирования (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: функции username вообще (иначе `DISABLED`) |
| **21199** | bool | false | связывание аккаунтов (FB / IG) включено, объявляется как `username_account_linking_enabled` |
| **16033** | bool | false | главный шлюз функций ключа (`C79343Xx.A00`): rate limit ключа, upsell ключа, WABI-вид username |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (все по умолчанию true, когда ключ JSON отсутствует) |
| **8421** | bool | false | разрешает MEX `UsyncQuery` для запросов username |
| **12402** | bool | false | добавляет атрибуты `lid` и `pin` в узел `contact` usync |
| **20494** / **20459** | int | 3 / 35 | мин / макс длина username |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | regex ключа |
| **34347** / **34348** | int | 4 / 6 | границы длины ключа (сообщение об ошибке) |
| **28678** | bool | false | включает хранилище backoff rate-limit |
| **28127** | int | 30 | секунды backoff по умолчанию |
| **29327** | int | 60 | задержка перед второй порцией `UsernameCheckMulti` |

Допустимость для companion (`C224069kP.A00`, чтение на уровне байткода):

```
companion (identity of the A02 check inferred from the "open WhatsApp on your primary device" strings):
  23817 off, or pref username_reservation_creation_supported_on_primary false  -> DISABLED
  pref username_account_linking_enabled_on_primary true                         -> COMPANION_READ_ONLY
  state RESERVED                                                                -> COMPANION_READ_ONLY
  state not UNSET                                                               -> CREATION
  state UNSET and pref username_reservation_only_mode_on_primary true           -> COMPANION_READ_ONLY
  state UNSET otherwise                                                         -> CREATION
primary:
  4745 on -> CREATION;  else 20189 on -> RESERVATION;  else DISABLED
```

Три pref `*_on_primary` читаются только здесь; где они записываются, не найдено (unknown).

---

## 9. Приватность и видимость

| Аспект | Находка | Уровень |
|--------|---------|------|
| Назначение | "Keep your phone number private with a username"; люди, у которых номер не сохранён, видят username вместо него | found (строки) |
| Первый контакт | при установленном ключе люди, с которыми "you haven't interacted with", должны ввести ключ, прежде чем связаться с username | found (строки) |
| Передача ключа | действие share username может включать ключ (pref `username_share_include_pin`, мигрирован в `C138535tr`); строки "Share your username and key" | found |
| Где номер скрыт | администраторы сообществ и каналов видят номер, если не установлен username; подписчики канала не видят ни то, ни другое | found (строки) |
| Телеметрия групп / тредов | поля `has_username`, `has_username_pin`, `is_username_thread` в телеметрии отправки сообщений (`DZ1`, `RQG`) | found |
| Ключ в покое | собственный ключ возвращается `UsernameGet` и хранится в открытых prefs `username_pin` | found |
| Сторонние чаты | "Usernames and contacts added to third-party chats will not save to your phone" | found (строка) |
| Business | "This username is only available on WhatsApp Business" появляется как текст отклонения | found (строка) |
| Кто может запрашивать | статус MEX usync `NOT_ALLOWED` показывает, что сервер может отказать в раскрытии username для отдельного запрашивающего | found (enum), правило unknown |
| Несовершеннолетние | pref `is_teen_account`; тексты для родителей "Your child created the username ..." | found |

Правила видимости, применяемые сервером (кто может разрешить username, rate limit ключей, переназначение), со стороны клиента unknown.

---

## 10. Заметки по Baileys

Конверт из 2.2 универсален; клиент Baileys может его построить. Это **inferred**, здесь не tested.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| Риск | Причина |
|------|--------|
| дрейф doc_id | id принадлежат ассету этой сборки; в других сборках могут отличаться (unknown) |
| `session_id` | код отправляет его, если он есть; требует ли сервер одно и то же значение для check и set — unknown |
| атрибуты ключа | `lid` / `pin` в `contact` скрыты за флагом 12402; сервер может игнорировать их для клиентов без флага (unknown) |
| локальные правила | правила длины, набора символов и точек клиентские; серверные правила unknown |

---

## 11. Ключевые различия

| Не путать | Различие |
|----------------|------------|
| Ключ username и PIN аккаунта / 2FA | Ключ username (`pin` в `UsernamePinSet`, pref `username_pin`) управляет первым контактом через username. Он не связан с 2FA регистрации |
| переменная `reserved` и `UsernamePinSet` | `reserved` относится к `UsernameSet` и помечает резервирование; у ключа своя операция |
| состояние `RESERVED` | локальное `C4DU.RESERVED` / серверное `state=RESERVED` — удерживаемое имя, ещё непригодное для использования; `ACTIVATED` и `CREATED` пригодны |
| Delete | операции delete нет; `UsernameSet` без `username` удаляет; удаление ключа — `UsernamePinSet` с `{}` |
| Результат check `INVALID` | покрывает занятость, требование привязки и проблемы формата; детали в `rejection_reasons` |
| Username и LID | username — это handle; адресующая идентичность — LID |
| int `source` | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; это не те же int, что id ошибок `C02U` |
| doc_id и `client_doc_id` | оба есть в ассете; захваченные id равны `doc_id` |
| Уведомления и операции | три типа `Username*Notification` — push-обработчики, не запросы |
| Метки из других репозиториев | `25975613018777537` отсутствует в persist-id ассете этой сборки; `25741205615468935` в этой сборке — `GetTextStatusList`. Ни то, ни другое не является операцией username здесь |

---

## 12. Сквозной поток

```
[User]                [Client]                              [Server]
  │ type name           │                                      │
  ▼                     │                                      │
 local validate ────────┤ charset, 3..35, dots, regex (5.1)    │
  │ ok                  ▼                                      │
  │              UsernameCheck {username, include_suggestions,  │
  │                             source, session_id}  ─────────►│
  │                     │◄──── xwa2_username_check {result,    │
  │                     │       suggestions, rejection_reasons}│
  │ SUCCESS             │                                      │
  ▼                     ▼                                      │
 confirm ─────────► UsernameSet {username, reserved,           │
                      session_id, source, [pin]} ─────────────►│
                        │◄──── ok | 304 | 40601..40603 | 429/503/529
                        ▼                                      │
                  write prefs: state, username_pin             │
                  429/503/529 -> backoff (flag 28678)          │
                                                               │
 [Owner sets key] ► UsernamePinSet {pin} | {} (delete) ───────►│

 [Other user, first contact]
  │ enter @name + key
  ▼
 validate key (flag 34350) ► usync contact{username,[lid],[pin]} ──►[Server]
                        │◄──── user jid (LID) | no LID | rate-limit flags
                        ▼
              LID  = open chat addressed to the LID
              none = "Wrong key entered"
              limit = "Too many attempts" / "can't be reached"

 [Server push]
   UsernameSetNotification (lid, username)  -> update local map
   UsernameDeleteNotification (lid, pn)     -> update contact
   UsernameUpdateNotification (hash)        -> usync delta
```

---

## 13. Unknowns

| Тема | Причина |
|-------|--------|
| Точный аксессор, питающий `query_id` | потребитель `doc_id` и `client_doc_id` не прослежен до сборщика IQ |
| Форма ответа `UsernamePinSet`, `UsernameSet` | у классов ответа нет обращений к полям в прочитанном коде |
| `UsernameGetRecommendationsQuery` | нет места вызова, нет переменных |
| Серверные правила username и ключа | клиент валидирует только локально |
| Значение 40601-40603 на сервере | найдены только клиентские строки |
| Происхождение prefs `*_on_primary` | запись не найдена |
| Эффект `username_chat_start_mode` | потребитель не найден |
| Схема использования `UsernameGet` (heartbeat) | не подтверждается прочитанным кодом |
| Шаг открытия чата после верного ключа | не прослежен дальше проверки LID |
| Реальный трафик | только статический анализ |
