<!-- src-sha1: 73855f4f8148d9b0ef853f43cef4adbe0cb996a5 -->
# WhatsApp Username (имя пользователя) — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** проверка/установка/резервирование/удаление username, ключ username (PIN), отношение к LID, приватность и видимость, операции w:mex GraphQL (doc_id, переменные, ответы), уведомления, поиск через USync, правила валидации, флаги функций, примечания по Baileys

---

## 1. Что такое username (технически)

Username — это серверный хендл, привязанный к аккаунту, используемый для того, чтобы с контактом можно было связаться без раскрытия номера телефона. Все утверждения — статический анализ декомпилированного APK. Уровень: **found** = прочитано в коде или ассетах, **inferred** = выведено из кода, **unknown** = не разрешено.

Функция построена на трёх слоях:

| Слой | Транспорт | Используется для |
|-------|-----------|----------|
| Управление собственным username | IQ `w:mex`, persisted GraphQL (конфигурация `whatsapp-android-mex`) | проверка, установка/резервирование/удаление, получение, установка/удаление ключа (PIN), множественная проверка |
| Поиск других | USync (`xmlns="usync"`) и вариант MEX `UsyncQuery` | разрешение `@username` (+ ключ) в LID, получение username известного JID |
| Push | уведомления MEX | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Межустройственное | синхронизация состояния приложения (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (несёт `username`) |

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| Менеджер username | `C122815Lj` | вызовы `UsernameGet`, `UsernameSet`, обновление локального состояния, хук ограничения частоты |
| Проверка доступности | `C67402tT` | вызов `UsernameCheck` + маппинг ответа |
| Множественная проверка | `C76333Kg` | `UsernameCheckMulti`, порциями по 10 |
| API ключа | `MexUsernamePinProtocolApi` | `UsernamePinSet` (установка / удаление ключа) |
| Локальное состояние / настройки | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| Enum состояния | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Режим допустимости | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Хранилище ограничения частоты | `C67942uO` | backoff после 429 / 503 / 529 |
| Локальный валидатор | `C82003fB.A04`, `C1187754z` | длина, набор символов, правила точек, regex |
| Валидатор ключа | `C1176550d` (+ `AbstractC111284pZ`) | формат ключа |
| View model ввода ключа | `UsernamePinEntryViewModel` | отправка ключа для чужого username |
| Клиент USync | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | классический конструктор/парсер стансы usync |
| MEX USync | `C229259vZ`, `O0F` | `UsyncQuery` с `include_username` |
| Обработчики уведомлений | `C49822Lvi`, `C49821Lvh`, анонимный `X.2YG` в `AbstractC20380p4` | установка / удаление / обновление |

Именование: видимое пользователю название PIN — **ключ username** (строки "Username key", "Add a username key to control who can contact you"). В протоколе и коде это `pin`.

---

## 2. Операции MEX (doc_id)

### 2.1 Где находятся doc_id

doc_id не являются литералами в `java_src`. Клиент отправляет имя операции (`"UsernameSet"`, ...) с именем конфигурации `"whatsapp-android-mex"` (found, `C16880is`). Числовой id читается из `assets/whatsapp-android-mex_client_persist_ids.json`: `EnumC17010j7.WHATSAPP_ANDROID_MEX` сопоставляется с этим файлом, `C17040jA.CMg(op)` возвращает поле `doc_id`, `AGb(op)` — поле `client_doc_id` (found). Который из двух аксессоров заполняет атрибут `query_id`, до конца не трассировано (unknown); более ранние захваты на 2.26.26.4 показывают, что `query_id` равен `doc_id`.

doc_id ниже — **found** в ассете 2.26.41.6:

| Операция | doc_id | Тип | Точка вызова | Класс ответа |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | не найдена | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Примечания:
- `UsernameGetRecommendationsQuery`: имя встречается только в JSON ассета. Ни один класс в `java_src` не ссылается на него по строке (found). Переменные и ответ unknown.
- Три имени уведомлений (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) не имеют записи в ассете persist-id. Это типы уведомлений, не запросы (см. 7).
- Ассет имеет `operation_name_hash`, `operation_text_hash` и `client_doc_id` на каждую операцию. Пример `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

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
| атрибут `query_id` | устанавливается только если от 1 до 20 символов |
| тело | JSON `{"queryId": ..., "variables": {...}}`, от 1 до 8448000 байт |
| переменные со значением null | `C16770ig.A03(k, null)` и `A02(k, null)` пропускают ключ, так что отсутствующее значение означает, что ключ не отправляется |

Протокольные стансы живых сессий здесь не воспроизводятся; эта сборка была проанализирована только статически.

---

## 3. Операции подробно

### 3.1 UsernameCheck

Переменные (found, `C67402tT.A00`):

| Переменная | Тип | Условие |
|----------|------|-----------|
| `username` | string | всегда |
| `include_suggestions` | bool | всегда (UI передаёт `false` в пути с типизированной проверкой `C64H`, кейс 21) |
| `source` | string | только если не null |
| `session_id` | string | только если не null |

Маппинг `source` (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, иное -> null (не отправляется).

Путь ответа (found, ветка по умолчанию `C77183Np`): `data.xwa2_username_check`

| Поле | Тип | Использование |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | читается только при `INVALID` |
| `rejection_reasons` | список `C4G8` | читается только при `INVALID` |
| `suggestions_eligible` | bool | по умолчанию `true`, когда поле null |

Значения `C4G8` (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Маппинг: `SUCCESS` -> `C76283Kb` (доступно); `INVALID` -> `C76303Kd` (недоступно, несёт предложения + причины); `UNSET` -> ни одна ветка не присваивает результат (колбэк получает предыдущую/null переменную; поведение unknown). Активный локальный backoff -> `C76293Kc` (ошибка с кодом ограничения частоты из настроек, см. 5.3); колбэк сбоя самого запроса не был прочитан.

Причины отклонения определяют текст про привязку аккаунта ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). В `C82003fB` любая причина, кроме `UNSET`, запускает локальный путь ошибки с кодом 40601 (`A08(40601L)`); пустой список или список, состоящий только из `UNSET`, показывает "Username isn't allowed." Точный поток управления вокруг цикла декомпилирован лишь частично (inferred).

### 3.2 UsernameCheckMulti

| Переменная | Тип | Примечания |
|----------|------|-------|
| `usernames` | **list<string>** | массив через `A00.A0B("usernames", list)`; каталог doc_id типизирует его как `str`, код отправляет список |

Пакетирование (`C76333Kg.AG5`): список разбивается на первые 10 и остальные; остальные обрабатываются после задержки из флага **29327** (по умолчанию 60, единица не разрешена). Пустой список возвращает пустую карту без запроса.

Путь ответа `data.xwa2_username_check_multi.results[]` (found): каждый элемент имеет `username` и `response.result` (тот же `EnumC59782gh`). Маппинг: `SUCCESS` -> доступно, `INVALID` -> недоступно (без предложений, `suggestions_eligible=false`), что-либо ещё -> ошибка. Имена, отсутствующие в результате, отмечаются как ошибка.

Потребитель: `UsernameAvailabilityCache` хранит `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) на каждое имя. Назначение (предзагрузка для предложений username Facebook / Instagram, строка `foa_username_prefetch_cache`) предполагается.

### 3.3 UsernameSet (создание / изменение / резервирование / удаление)

Переменные (found, `C122815Lj.A00`):

| Переменная | Тип | Условие |
|----------|------|-----------|
| `username` | string | не передаётся, когда null (**удаление**) |
| `reserved` | bool | всегда отправляется |
| `session_id` | string | только если непусто (`C1YW.A08`) |
| `source` | string | только если int источника не null (см. 3.1) |
| `pin` | string | только если не null |

`reserved` — вычисляемое значение, не константа (found). Аргумент `z` (принуждение) = true даёт `false`. Иначе: текущее состояние `ACTIVATED` или `CREATED` даёт `false`; текущее состояние `RESERVED` или режим допустимости `RESERVATION` дают `true`; все прочие случаи дают `false`. Так что `reserved:true` отправляется только для аккаунтов в режиме резервирования или уже удерживающих резервирование.

Удаление — это режим той же операции: `username == null` -> тег лога `delete`, иначе `set` (также в `MexUsernamePinProtocolApi` для ключа). При null username ключ `username` отсутствует в переменных (found).

Защита на стороне клиента: до отправки, если хранилище ограничения частоты сообщает об активном backoff, вызов завершается локальной ошибкой с `username_creation_rate_limit_error_code` и текстом "rate limit expiration time not reached" (found, `C122815Lj.A03`).

Обработка успеха (`C122815Lj.A01`, found):

| Условие | Записываемое локальное состояние (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username null или пусто | `UNSET`, настройка ключа очищается |
| `reserved` было true | `RESERVED` |
| флаг активации | `ACTIVATED` |
| иначе | `ACTIVATED`, если состояние было `ACTIVATED` и имя совпадает с сохранённым, иначе `CREATED` |
| int `source` равен 1 или 2 | настройка `username_set_via_account_linking` = (int == 2) |
| отправлен `pin` | обновляется настройка `username_pin` |
| флаг teen | настройка `is_teen_account` = true |

Запись настройки — `Voip.REJECT_REASON_DECLINED`, что в этой сборке — пустая строка `""` (found).

Обработка ошибок (`C138725uA` кейс 2):

| Код в стиле HTTP | Действие клиента |
|----------------|---------------|
| 429, 503, 529 | сохраняется backoff (5.3) |
| 304 | обрабатывается как успех ("не изменено"), локальное состояние всё равно обновляется |
| нет соединения (`C213639Bb`) | результат `C4BO` "no network" |
| прочее | `C4BN(code, message)` |

### 3.4 UsernameGet

Переменные: нет (вызов строит пустой набор переменных, found, `C122815Lj.A02`). Отмечен `@Deprecated`, заменён на suspend-вариант.

Ответ (found, `C138815uJ` кейс 34): `data.xwa2_username_get.username_info`

| Поле | Использование |
|-------|-----|
| `username` | сохраняется; пустая строка при отсутствии |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **ключ возвращается в открытом виде и хранится в настройке `username_pin`**; пустая строка при отсутствии |

Маппинг состояния: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED`, если сохранённый username совпадает с возвращённым, а локальное состояние было `RESERVED` или `ACTIVATED`, иначе `CREATED`; null state или null `username_info` -> `UNSET`.

Случай ошибки 404 от сервера очищает локальный username, ключ и состояние (лог `clearSelfUsernameData NOT_FOUND`).

Используется ли вызов как heartbeat — unknown; старое замечание "polling heartbeat" не подтверждается кодом этой сборки.

### 3.5 UsernamePinSet (ключ username)

Переменные (found): `pin` (string), не передаётся, когда null.

| Действие | Переменные |
|--------|-----------|
| установка ключа | `{"pin": "<key>"}` |
| удаление ключа | `{}` (`A02` вызывает `A00(null)`) |

Имя операции для обоих случаев — `UsernamePinSet`; отдельной операции верификации нет. Верификация чужого ключа выполняется в USync (4). Не подключено: возвращает `C213639Bb("UsernamePinSet")` без запроса.

Ключ также может идти в `UsernameSet` (переменная `pin`). `C81793ej.A0x` использует `UsernameSet` с существующим username и новым `pin`, когда username уже сохранён локально (`A00 != null`), и `UsernamePinSet` в противном случае (found).

Класс ответа `C48557LJz` не имеет обращений к полям в прочитанных файлах; форма ответа unknown.

---

## 4. Поиск других пользователей

### 4.1 Классический USync по username (поток с ключом)

Строится в `C18670m9.A06` (jadx не справился с этим методом, прочитано из smali `X/0m9.smali`). На запись запроса `C222649hm`: поле `A0C` = username, `A0D` = ключ, `A05` = LID.

Атрибуты дочернего элемента contact (найдены в smali): `username` всегда; `lid`, когда LID известен локально; `pin`, когда установлен ключ. Дополнительные атрибуты ограничены флагом **12402** (по умолчанию `false`): когда флаг выключен, записывается только `username` (found). Имя узла `contact` выведено из парсера ответа, который читает дочерний элемент `contact` и его атрибут `username` (`C18670m9`, строки ~969-975).

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

Точка входа: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), вызывается `submitPinForUsername`. Тип синхронизации `EnumC21760rz.A0J`, таймаут 32000 мс. Набор атрибутов `contact`, `pin`, `username` входит в наборы редактирования логов `AbstractC40921lc` (found).

Локальное предварительное разрешение: `A0M.Aol(username)` ищет `lid_row_id` в таблице `lid_display_name`, где `UPPER(username) = UPPER(?)`, сначала самая новая строка (found, `C1S0`). LID, если известен, идёт в атрибут `lid`.

### 4.2 Оценка результата (ввод ключа)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Исход | Условие |
|---------|---------|
| правильный ключ | результат `UserJid` — это LID (`C14080dr`) |
| неправильный ключ | результат не содержит LID: лог `[un-pin] incorrect PIN`, текст ошибки "Wrong key entered" |
| нет сети | `C9qA` код 1 |
| общая инфраструктурная ошибка | `C9qA` код 2 |
| ограничение частоты запрашивающего | `C225769os.A01` истинно: "Too many attempts made. Try later." |
| ограничение частоты запрашиваемого | `C225769os.A00` истинно: "This account can't be reached with their key right now..." |

Кэшированная на клиенте проверка ограничения частоты выполняется первой, когда флаг **16033** включён, а JSON-конфигурация **21995** имеет `enable_key_rate_limit` = true (по умолчанию true): `C30P.A00` проверяет против собственного LID и против username цели. Из username удаляется `@` (`C0CX.A0i(username, '@')`).

При успехе результат — это **LID**, затем чат адресуется этому LID (выведено из проверки `C14080dr`; шаг открытия чата не трассирован).

### 4.3 Получение username известного LID

`C23638AId` (строки ~600-650) строит usync с `<list><user jid="LID"/></list><query><contact/><username/></query>`, режим/контекст из `EnumC21760rz.A0J` (found). Парсер читает `username` как дочерний элемент результата `<usync>` (`C18670m9`, строка 586, только когда это запрашивалось).

### 4.4 MEX USync (`UsyncQuery`)

`C229259vZ.A01` строит `UsyncQuery` (doc_id выше). Релевантные части (found):

| Переменная | Использование |
|----------|-----|
| `query_input[]` | одна запись на пользователя: JID (`C493020r.A0C`), опциональный `client_known_username` (только когда username запрошен и непуст) |
| `include_username` | bool, устанавливается, когда любая запись запрашивает username |
| `include_lid` | bool, запрашивает `lid_info` |
| `telemetry.context` | контекст USync в нижнем регистре |

Ответ на пользователя: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` полиморфен по хэшу типа: тип-значение, несущий `username`, или тип-статус со `status` из `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED` логируется как "username not allowed to be queried" и очищает сохранённый username; `NO_CHANGE` оставляет его. `lid_info.lid_jid` несёт LID.

Ограничение: `ContactSyncHelper` отказывается от пути MEX с логом "cantUseMex as username ab prop is off", если флаг **8421** не включён, когда запрошен username (found; по умолчанию `false`).

---

## 5. Валидация, лимиты, ошибки

### 5.1 Формат username (локальный)

Валидатор `C82003fB.A04` (found), проверки в этом порядке:

| Порядок | Проверка | Id ошибки (`C02U`) | Строка сообщения |
|-------|-------|-------------------|----------------|
| 1 | каждый символ в `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | длина >= минимум (флаг **20494**, по умолчанию 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | длина <= максимум (флаг **20459**, по умолчанию 35) | 1 | та же строка |
| 4 | нет начальной `.`, нет конечной `.`, нет `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | хотя бы одна буква ASCII | 4 | "Choose a username with at least one letter" |
| 6 | regex (ниже) | проходит или не проходит с 2 | н/д |

Regex, построенный `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

Регистр не нормализуется валидатором; локальный поиск `Aol` сравнивает через `UPPER()`, так что локальное сопоставление регистронезависимо (found). Обрабатывает ли сервер имена без учёта регистра — unknown. Начальное подчёркивание разрешено regex-ом; текст UI говорит "начинается с буквы", что строже, чем regex (found, несовпадение).

UI также отклоняет веб-ссылки: "Enter only your username, not a web link" (строка присутствует, проверка не трассирована).

### 5.2 Формат ключа username

`C1176550d.A00` (found): флаг **34350** — строка regex, по умолчанию `^([0-9]{4}|[A-Z0-9]{6})$`. Если строка флага пуста, резервный вариант — ровно четыре цифры. Невалидный regex логирует `[un-pin] invalid username_key_regex` и принимает что угодно. Флаги границ длины **34347** (минимум, 4) и **34348** (максимум, 6) питают только путь сообщения об ошибке в `UsernamePinEntryViewModel.A0w`. Серверные правила unknown.

Так что старое замечание "4-значный PIN" неполно: поставляемый по умолчанию вариант принимает четыре цифры или шесть букв/цифр верхнего регистра.

### 5.3 Ограничения частоты и backoff

`C67942uO` (found), активен только при флаге **28678** (по умолчанию `false`):

| Элемент | Значение |
|------|-------|
| триггер | ошибка `UsernameSet` 429, 503 или 529 |
| длительность | строка в стиле `Retry-After`, разбираемая как int секунд (`C23680AJt.A00`), иначе флаг **28127** (по умолчанию 30) секунд |
| хранение | настройки `username_creation_rate_limit_backoff_expiry` (мс), `username_creation_rate_limit_error_code` |
| эффект | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` завершаются локальной ошибкой до истечения срока |

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
| прочее | "We couldn't complete your request. Try again." |

40601-40603 входят в разрешённый набор `AbstractC111104pH.A01` (в прочитанном коде показан только 40603). Их серверная семантика unknown, сверх текста клиента.

---

## 6. Отношение к LID

Всё found, если не отмечено иное.

| Факт | Доказательство |
|------|------|
| Поиск username разрешается в **LID**, не в телефонный JID | тест успеха ключа `userJid instanceof C14080dr` (класс LID); `lid_info.lid_jid` в MEX usync |
| Локальная карта username -> LID | таблица `lid_display_name` (столбцы `username`, `lid_row_id`), запрос в `C1S0` |
| Уведомления идентифицируют пользователя по LID | обработчики установки/удаления разбирают `LidUserJid` (текст ошибки "Failed to parse LidUserJid") |
| Уведомление об удалении может нести телефонный JID | обработчик проверяет `isPnPresent`; при наличии PN приводит к типу PN JID и действует, без PN — возвращается |
| Действие синхронизации контакта | `ContactAction` имеет `username` (6) рядом с `lid_jid` (3), `pn_jid` (5); также `LidContactAction` (`lid_contact`, поле SyncActionValue 61) |
| Режим начала чата | поле SyncActionValue **59** `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Найден только кодек синхронизации; потребителя в коде UI нет (unknown) |
| Строка функции спутника | при привязке companion-устройства основное устройство добавляет `username_supported` (флаг 4745 или 20189), `username_reservation_only_mode` (только 20189), `username_account_linking_enabled` (флаг 21199) в свой список возможностей (`C25056AqU`) |

Inferred: пользователь, существующий только как username, достижим только через LID, пока владелец не поделится номером телефона; строки "If you continue, your phone number will show in existing username chats and calls" (диалог удаления) подтверждают это, но путь раскрытия PN не был трассирован.

---

## 7. Уведомления

Обработчики расширяют `AbstractC23194A0r` и регистрируются в `AbstractC20380p4` (found):

| Уведомление | Обработчик | Поведение |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | полезная нагрузка `xwa2_notify_username_on_change`: читает LID (хэш поля 107143) и username; сохраняет через `InterfaceC11470Yz.BNU(lid, username)`; если контакт существует и совпадающего вида, обновляет контакт (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | полезная нагрузка `xwa2_notify_username_delete`: читает LID и PN (хэш -983979708); при наличии PN выполняет обновление удаления (`C53594Nzh`) |
| `UsernameUpdateNotification` | анонимный `X.2YG` | читает base64-хэш из полезной нагрузки, строит запрос USync с причиной `USERNAME_UPDATE_NOTIFICATION` и `EnumC21760rz.A0Q` (контекст `NOTIFICATION_SIDELIST`, режим `query`; см. WA_USYNC.md), лог `usync triggered for hash` |

Текст, показываемый пользователю: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", т.е. сервер может переназначить username (отзыв, настройка `is_username_revoked`, `revocation_banner_dismissed_<username>`).

---

## 8. Флаги функций

Id флагов — это id свойств AB, читаемые через `C08J` (значения по умолчанию из таблиц `C08J`). Все значения по умолчанию ниже прочитаны из этой сборки.

| Флаг | Тип | По умолчанию | Управляет |
|------|------|---------|----------|
| **4745** | bool | false | основное устройство: создание username (режим `CREATION`); также анонсируется как `username_supported` |
| **20189** | bool | false | основное устройство: режим только резервирования (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: функции username вообще (иначе `DISABLED`) |
| **21199** | bool | false | привязка аккаунта (FB / IG) включена, анонсируется как `username_account_linking_enabled` |
| **16033** | bool | false | главное ограничение для функций ключа (`C79343Xx.A00`): ограничение частоты ключа, предложение ключа, просмотр username WABI |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (все по умолчанию true, когда ключ JSON отсутствует) |
| **8421** | bool | false | разрешает MEX `UsyncQuery` для запросов username |
| **12402** | bool | false | добавляет атрибуты `lid` и `pin` к узлу `contact` usync |
| **20494** / **20459** | int | 3 / 35 | минимальная / максимальная длина username |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | regex ключа |
| **34347** / **34348** | int | 4 / 6 | границы длины ключа (сообщение об ошибке) |
| **28678** | bool | false | включает хранилище backoff ограничения частоты |
| **28127** | int | 30 | секунды backoff по умолчанию |
| **29327** | int | 60 | задержка перед второй порцией `UsernameCheckMulti` |

Допустимость companion (`C224069kP.A00`, прочитано на уровне байткода):

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

Три настройки `*_on_primary` прочитаны только здесь; где они записываются — не найдено (unknown).

---

## 9. Приватность и видимость

| Аспект | Находка | Уровень |
|--------|---------|------|
| Назначение | "Keep your phone number private with a username"; люди, у которых номер не сохранён, видят username вместо него | found (строки) |
| Первый контакт | при установленном ключе люди, "с которыми вы не взаимодействовали", должны ввести ключ перед обращением к username | found (строки) |
| Шаринг ключа | действие шаринга username может включать ключ (настройка `username_share_include_pin`, перенесена в `C138535tr`); строки "Share your username and key" | found |
| Где номер скрыт | администраторы сообществ и администраторы каналов видят номер, если не установлен username; подписчики канала не видят ни того, ни другого | found (строки) |
| Телеметрия группы / треда | поля `has_username`, `has_username_pin`, `is_username_thread` в телеметрии отправки сообщения (`DZ1`, `RQG`) | found |
| Хранение ключа | собственный ключ возвращается `UsernameGet` и хранится в открытых настройках `username_pin` | found |
| Чаты со сторонними сервисами | "Usernames and contacts added to third-party chats will not save to your phone" | found (строка) |
| Business | "This username is only available on WhatsApp Business" появляется как текст отказа | found (строка) |
| Кто может запрашивать | серверный статус MEX usync `NOT_ALLOWED` показывает, что сервер может отказать в раскрытии username по запросу | found (enum), правило unknown |
| Несовершеннолетние | настройка `is_teen_account`; тексты для родителей "Your child created the username ..." | found |

Правила видимости, применяемые сервером (кто может разрешить username, ограничения частоты ключа, переназначение), неизвестны из клиента.

### 9a. Контроль аудитории раскрытия номера телефона (новое в 2.26.45.10, found)

Отдельный пакет `com.whatsapp.pnsharing` управляет тем, кто может видеть номер телефона аккаунта, независимо от собственных правил видимости username в разделе 9. Две новые операции `whatsapp-android-mex`, обе **found** из простых литералов `const-string` в smali (декомпил не требуется, `PnSharingAudienceUpdater.smali` / `PnSharingListFetcher.smali` / `PnSharingListUpdater.smali`):

| Операция | doc_id | Тип |
|-----------|--------|------|
| `UsernamePhoneNumberPrivacyUpdateMutation` | `28835748819379698` | mutation |
| `UsernamePhoneNumberPrivacyGetQuery` | `29264643203229836` | query |

Настройка аудитории — одно из 4 значений общего, не специфичного для pnsharing enum `LX/BWW` (всего 13 членов, только эти 4 достижимы из этого пути вызова):

| ordinal | элемент `LX/BWW` | значение `setting` |
|---|---|---|
| 0 | `A02` | `ALL` |
| 1 | `A07` | `MYCONTACTS` |
| 2 | `A08` | `MYCONTACTSEXCEPT` |
| 3 | `A09` | `NONE` |

**`UsernamePhoneNumberPrivacyUpdateMutation` — инкрементальная, а не полная замена.** Её питают две точки вызова:

- `PnSharingAudienceUpdater.A00` — только изменение настройки верхнего уровня, без записей списка.
- `PnSharingListUpdater.A01` — добавление/удаление отдельной записи против одного из трёх списков аудитории.

Поля верхнего уровня (found):

| Поле | Тип | Значение |
|-------|------|---------|
| `setting` | string | `ALL` / `MYCONTACTS` / `MYCONTACTSEXCEPT` / `NONE`, см. таблицу выше |
| `input` | object | вложенная полезная нагрузка, см. ниже |

Поля `input` (found, вложены под `allow_list` / `contact_exclude_list` / `deny_list`, в зависимости от того, какая из 3 настроек, отличных от `MYCONTACTS`, активна — `MYCONTACTS` не отправляет ключ списка):

| Поле | Тип | Значение |
|-------|------|---------|
| `dhash` | string | хэш содержимого списка аудитории, используется для инвалидации кэша / обнаружения конфликтов (рядом строка лога "...changed since it was read") |
| `entries` | список объектов | инкрементальные записи ADD/DEL, не полная замена списка |

Поля элемента `entries[]` (found, строятся `PnSharingListUpdater.A00(Integer, Integer)`):

| Поле | Тип | Значение |
|-------|------|---------|
| `entry_type` | string | `USER` или `GROUP` |
| `operation` | string | `ADD` или `DEL` |
| `group_jid` | string, может быть null | устанавливается только когда `entry_type=GROUP` |
| `pn_jid` | string, может быть null | устанавливается, когда запись — обычный номер телефона (`PhoneUserJid`) |
| `user_jid` | string, может быть null | устанавливается, когда запись — разрешённый контакт `Jid` |
| `username` | string, может быть null | поле существует в схеме, но ни одна наблюдаемая точка вызова его не заполняет; `inferred` назначение: сопоставление ещё не контакта-номера телефона с отображаемым именем, согласуется с исключениями в стиле `UsernameSet` — `unknown`, устанавливает ли его фактически хоть один вызывающий |

Ровно одно из `group_jid` / `pn_jid` / `user_jid` заполнено на каждую запись (found); два остальных остаются null.

`UsernamePhoneNumberPrivacyGetQuery` — аналог на стороне чтения (found, `PnSharingListFetcher.smali`): один пакетный запрос, получающий все 3 списка аудитории за раз, каждый ключуется своим собственным `dhash` (локально кэшированный хэш, или буквальная строка `"none"`, если отсутствует) для валидации кэша.

**Неразрешённый doc_id:** каталог persisted-query также перечисляет `PnSharingPhoneNumberFetch` (doc_id `29229648029980096`, тип query). Поиск по всему декодированному дереву smali 2.26.45.10 (все шарды, не только `com/whatsapp/pnsharing/`) по этому литералу не находит точки вызова — на него ссылается только поставляемый ассет `whatsapp-android-mex_client_persist_ids.json`. Что его вызывает и что оно отправляет — **unknown**. Вероятный кандидат только по имени (**inferred**, не больше): получение видимости номера телефона на отдельный контакт/группу, т.е. однопредметный аналог пакетного запроса из 3 списков выше — не подтверждено.

---

## 10. Примечания по Baileys

Конверт из 2.2 универсален; клиент Baileys может его построить. Это **inferred**, здесь не проверено.

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
| Дрейф doc_id | id принадлежат ассету этой сборки; в других сборках могут отличаться (unknown) |
| `session_id` | код отправляет его, когда он присутствует; требует ли сервер одно и то же значение для проверки и установки — unknown |
| атрибуты ключа | `lid` / `pin` на `contact` находятся под флагом 12402; сервер может игнорировать их для клиентов без флага (unknown) |
| локальные правила | длина, набор символов и правила точек — на стороне клиента; серверные правила unknown |

---

## 11. Ключевые различия

| Не путать | Различие |
|----------------|------------|
| Ключ username vs PIN аккаунта / 2FA | Ключ username (`pin` в `UsernamePinSet`, настройка `username_pin`) ограничивает первый контакт через username. Не связан с 2FA регистрации |
| Переменная `reserved` vs `UsernamePinSet` | `reserved` относится к `UsernameSet` и отмечает резервирование; у ключа своя операция |
| Состояние `RESERVED` | локальное `C4DU.RESERVED` / серверное `state=RESERVED` — удерживаемое имя, ещё не готовое к использованию; `ACTIVATED` и `CREATED` готовы к использованию |
| Удаление | отдельной операции удаления нет; `UsernameSet` без `username` удаляет; удаление ключа — это `UsernamePinSet` с `{}` |
| Результат проверки `INVALID` | покрывает занятость, необходимость привязки аккаунта и проблемы формата; детали в `rejection_reasons` |
| Username vs LID | username — хендл; адресующая идентичность — это LID |
| Int `source` | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; не те же числа, что id ошибок `C02U` |
| doc_id vs `client_doc_id` | оба находятся в ассете; захваченные id равны `doc_id` |
| Уведомления vs операции | три типа `Username*Notification` — это обработчики push, не запросы |
| Метки из других репозиториев | `25975613018777537` отсутствует в ассете persist-id этой сборки; `25741205615468935` — это `GetTextStatusList` в этой сборке. Ни один из них здесь не является операцией username |

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

## 13. Неизвестное

| Тема | Причина |
|-------|--------|
| Точный аксессор, питающий `query_id` | потребитель `doc_id` vs `client_doc_id` не трассирован до построителя IQ |
| Форма ответа `UsernamePinSet`, `UsernameSet` | у классов ответа нет обращений к полям в прочитанном коде |
| `UsernameGetRecommendationsQuery` | нет точки вызова, нет переменных |
| Серверные правила username и ключа | клиент только валидирует локально |
| Значение 40601-40603 на сервере | найдены только строки клиента |
| Происхождение настроек `*_on_primary` | писатель не найден |
| Эффект `username_chat_start_mode` | потребитель не найден |
| Паттерн использования `UsernameGet` (heartbeat) | не подтверждается прочитанным кодом |
| Шаг открытия чата после правильного ключа | не трассирован дальше проверки LID |
| Фактический трафик | только статический анализ |
