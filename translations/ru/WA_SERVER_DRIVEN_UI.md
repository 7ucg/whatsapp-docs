<!-- src-sha1: 193c35598b4e82f9c32a0c5d2cee4dbf2d708588 -->
# WhatsApp Server-Driven UI — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** Серверно-управляемые экраны и действия на Android: конечный автомат действий Phoenix/FCS (IQ `xmlns="phoenix"`, типы состояний, операторы choice, реестр ресурсов), экраны Bloks (GraphQL-запрос, doc id и маршрутизация по app-id, JSON-payload, id функций Lispy, пространства имён действий, запросы компонентов, кэши), native flow messages (реестр кнопок NFM), WhatsApp Flows (мост WebView, политика хоста SecureWebView, flow JSON), AI rich response и карточка FMX (что не является серверно-управляемым), скрипты встроенного браузера (мост iabjs и nonce), песочница и feature-флаги, значение для Baileys

---

## 1. Что это (технически)

В WhatsApp Android нет единого движка серверно-управляемого UI. Существуют четыре независимых механизма; каждый получает описание с сервера (или читает его из сообщения) и управляет нативным кодом. Все утверждения получены статическим анализом декомпилированного APK; на проводе ничего не перехватывалось. Уровни: **found** = прочитано в коде или данных, **inferred** = выведено, **unknown** = не выяснено. Обфусцированные имена привязаны к сборке и заново определены в 2.26.41.6.

| Механизм | Что описывает | Носитель | Рендерер / исполнитель | Где используется |
|-----------|-----------|---------|---------------------|------------------|
| Phoenix (имена классов говорят FCS «flow configuration service», тег лога FDS) | Управление потоком: состояния `resource` / `choice` / `pass` / `succeed` / `subflow` | IQ `<iq xmlns="phoenix">` с дочерним `<fds>` | конечный автомат `QKb`, обработчики ресурсов (`AbstractC57917Pxu`) | Онбординг платежей, address message, опрос бизнеса, потоки карт в Бразилии |
| Bloks | Экраны: дерево компонентов + скрипты Lispy + асинхронные запросы компонентов | HTTPS GraphQL POST на `graph.<domain>/graphql` | host-activity и фрагменты на Litho/RenderCore | Платежи, поддержка, подписки, согласие, привязка Accounts Center, minishops, опросы, согласие бизнеса на Meta AI |
| Native flow messages (NFM) | Кнопки интерактивных сообщений (`nativeFlowInfo` name + JSON параметров) | Сообщение (protobuf) | диспетчер `C33370Efz` на около 40 классов действий | CTA-кнопки, `address_message`, `galaxy_message` (Flows) |
| Веб-приложение WhatsApp Flows | Flow JSON, отображаемый размещённым веб-приложением | HTTPS (`flows.whatsapp.net`) в `SecureWebView` + канал сообщений `WhatsAppBridge` | `WaFlowsWebViewBottomsheetModalActivity` / `FlowsWebBottomSheetContainer` | Бизнес-формы (`galaxy_message`, flexible checkout) |

Ключевые моменты:

- Phoenix — слой управления, Bloks — слой представления. Состояние Phoenix `resource` с id `open_bloks_screen_graphql` открывает экран Bloks; действия Bloks `wa.action.phoenix.*` возвращают в конечный автомат (раздел 3.5; связка выведена из имён).
- Bloks — не MEX и не IQ. Это GraphQL POST в стиле Meta (`doc_id` + `variables`) по HTTPS (found, `AbstractC40195HfH`). Phoenix — это IQ. Класс результата запроса эндпоинта Flows (`AnonymousClass456`) использует общую базу парсера ответов с Bloks; его транспорт не выяснен (раздел 4.5).
- Серверный контент не может назвать произвольный нативный код. Каждый маршрут проходит через фиксированный реестр: id ресурсов Phoenix (15 в коде), id функций Bloks (681 именованная), имена кнопок NFM (39), методы моста Flows (30), allow-list xmlns для Bloks IQ (2 записи).
- Проверка подписи payload для Bloks или Phoenix не найдена. `BloksTrustedPayload` (`verifiedRoot`) существует и не имеет ссылок (found, smali и Java).
- Не серверно-управляемые: карточка доверия FMX (системное сообщение, создаваемое клиентом), AI rich response (фиксированный набор компонентов protobuf), три файла `assets/json/bloks_*_template.json` (заготовки загрузки/ошибки, не продуктовые экраны).

Связанные отчёты: AB props (IQ `abt`, id флагов) в `WA_AB_PROPS.md`; AI rich response в `WA_META_AI.md`, раздел 6.3. Фреймворк с названием Genie не обнаружен (поиск по строкам; отсутствие не доказано).

---

## 2. Конечный автомат действий Phoenix

### 2.1 Компоненты (found, имена 2.26.41.6)

| Роль | Класс | Примечания |
|------|-------|-----------|
| Среда выполнения | `QKb` | Тег лога `FcsStateMachine`; `A03` выполняет одно состояние, `A04` переходит по `next` или снимает со стека, `A05` завершает |
| Менеджер FDS | `C58392QJx` | Запускает конфиг (`A08`), отправляет IQ (`A07`), строит карту состояний из ответа (`A01`) |
| Построитель IQ | `C31107Dfz` (конструктор с `C9E1`), `C9E1`, `C31085Dfd` | `xmlns="phoenix"` |
| Парсеры ответа | `F7J` (`<iq><fds>`), `F8I` (случаи 17-20, 27, 28), `F7Y` resource, `F7Z` choice, `C34784F7b` pass, `C34783F7a` succeed, `C34785F7c` subflow, `C34786F7d` version_check | Универсальный парсер схемы атрибутов (`C197428ac`) |
| Разобранные состояния | `P2W` resource, `P2U` choice, `P2T` pass, `P2S` succeed, `P2V` subflow, `C31057DfB` version_check | Общая часть `P2Q`: `name`, `input_path`, `input_selector`, `next`, `result_selector`, `result_path` (`C33411Ege.A03`) |
| Состояния времени выполнения | `C55819P7c` resource, `C55817P7a` choice, `C55818P7b` pass, `P7Z` succeed, `C55820P7d` subflow | Отображение в `C58392QJx.A01` |
| Базовый ресурс | `AbstractC57917Pxu` | `A02()` = id ресурса, `A04(...)` = выполнение с картой параметров, id по умолчанию `throw_error` |
| Привязка / реестр | `C51E` (id + ленивый обработчик), `InterfaceC148426Oz.CP3()`, объединение `C138515tp` | Реестры: `C135435oi`, `C135425oh`, `C135415og`, `C53207NpW`..`C53211Npa` |
| Операторы / ошибки / колбэк | `RsJ` (28 операторов), `AbstractC56245PPq`; `Q6G` (`catch`); `C57560Pry` (`A00(error, result)`, `A01(result)`) | |

### 2.2 Запрос: IQ (found, `C31107Dfz`, `C58392QJx.A07`)

```
<iq xmlns="phoenix" type="get|set" id="...">
  <fds config="<config name>" state="<start state>" parameters="<json>">
    <context ... parameters='{"session-id":"...","bloks-versioning-id":"13c6e3b8...(64 hex)"}'/>
  </fds>
</iq>
```

| Элемент | Значение | Уровень |
|------|-------|------|
| `type` | `get` при старте (`A08`), `get` или `set` для ресурса `send_fds_iq` | found |
| Целочисленные типы IQ / таймаут | 302 (get), 303 (set), 32000 мс | found |
| `state`, `parameters` | записываются только если не пусты; `parameters` = JSON из ненулевых записей | found |
| `bloks-versioning-id` | константная 64-hex строка, одно и то же значение в каждом построителе запросов Bloks (раздел 3.2) | found |
| Вложенность узла context | `<context>` несёт JSON; точная вложенность внутреннего узла не выяснена | unknown |

Ответ (found, `F7J`, `F8I`):

| Элемент | Содержимое | Для чего используется |
|---------|---------|----------|
| `<fds>` атрибуты `state`, `parameters` | подсказка старта | разобрано, дальше не прослежено |
| `<states start_at="...">` + `<state ...>`+ | программа (раздел 2.3) | инициализация `QKb`, лог `initializeStateMachine num_states` |
| `<next_screens>` + `<screen is_entry_screen app_id bloks_server_params sources>` | экраны Bloks для предзагрузки | `C58392QJx.A06` (предзагрузка) |
| `<screen_data parameters>` | blob данных экрана | разобрано |
| `<persist_data>` + `<data ...>` | значения, которые хранит хост | `C58392QJx.A02` (колбэк на ключ) |

Ошибка IQ возвращается вызывающему как `error` (`BtN`), ожидающая запись менеджера удаляется.

### 2.3 Типы состояний (found)

Парсер принимает список дискриминаторов `FDSResourceState|FDSChoiceState|FDSSucceedState|FDSPassState|FDSSubflowState|FDSVersionCheckState` (`F8I`, случай 27). Атрибут `type` — фиксированная строка из второго столбца.

| Тип | `type` | Собственные атрибуты | Поведение при выполнении |
|------|--------|----------------|-------------------|
| Resource | `resource` | `id` (id ресурса), `parameters`, `merge`, `merge_param`, `catch` | Ищет `id` в реестре; отсутствующий id даёт ошибку `ResourceNotFound`; запускает обработчик; результат объединяется по `merge`; переходит к `next` |
| Choice | `choice` | `default` (резервное следующее состояние), `catch`, дочерние `<choice choice="{json}"/>`+ (один ключ оператора + `next`) | Вычисляет операторы на входном JSON; побеждает первое совпадение, иначе `default`; требуется минимум один choice |
| Pass | `pass` | `parameters` | Переписывает данные и переходит к `next`, без обработчика |
| Succeed | `succeed` | нет | Терминальный успех (`A05` без ошибки) |
| Subflow | `subflow` | `launch_mode` (`child` или `embedded`), `config`, `parameters`, `catch` | `child`: новые менеджер и конечный автомат; `embedded`: загружает другой конфиг в ту же сессию (выведено из `C55820P7d`) |
| Version check | `version_check` | `default`, дочерний `<choice>` | Разбирается (`C31057DfB`), но не имеет ветки в `C58392QJx.A01`; состояние отбрасывается (found); переход в него завершился бы ошибкой `state not found for name` (inferred) |

В парсере нет состояния `fail`; манифест всё же перечисляет `fail` (2.7).

Селекторы и данные (found):

- `input_selector` по умолчанию `"$"`; строка `"null"` отключает его (`C58392QJx.A01`). `result_selector` и слияние параметров проходят через `AbstractC58328QFo`. Движок в стиле JSONPath используется для `catch` (`Q2G`, выражения вида `$.[i].error_equals`) (found); что селекторы используют тот же движок, выведено (inferred).
- Режимы `merge` в `QKb.A03`: `replace` (по умолчанию), `merge`, `incremental_merge`, `wae_commerce_merge` (found).
- `catch` = JSON-массив `{error_equals:[names], next:<state>}`; пустой `error_equals` совпадает со всем (found, `Q6G.A00`). Неперехваченные ошибки завершают автомат с этой ошибкой (`A05`).
- Ошибки, поднимаемые самим интерпретатором: `ResourceNotFound`, `FailToResume`, `unsupportedComparisonTypes`, `comparingValuesWithDifferentTypes`, `genericChoiceStateError`; ошибка обработчика по умолчанию `NOT_CATCHABLE_ERROR` (`C5I7.A03`) (found).

### 2.4 Операторы choice (found, `RsJ.A00`)

28 классов. Манифест перечисляет 21; семь устаревших имён есть только в коде.

| Группа | Имена |
|-------|-------|
| Boolean | `and`, `or`, `not`, `booleanEquals` |
| Равенство | `eq`, `neq`, `eq_any`, `neq_any`, `eq_path`, `neq_path`, `eq_any_path`, `neq_any_path`, `stringEquals` |
| Упорядочивание | `gt`, `gte`, `lt`, `lte`, `gt_path`, `gte_path`, `lt_path`, `lte_path`, `numericalEquals`, `numericalGreaterThan`, `numericalGreaterThanEqual`, `numericalLessThan`, `numericalLessThanEqual` |
| Прочее | `isPresent`, `regex_match` (`variable` + `regex_match`) |

Каждый оператор выбирается по наличию ключа в JSON choice (`AbstractC56245PPq.A00`); `JSONException` переводит к следующему оператору. Варианты `_path` сравнивают со значением, полученным по пути (выведено из имени); точное разрешение не читалось.

### 2.5 Реестр ресурсов (found)

Регистрируется через `InterfaceC148426Oz.CP3()`; id хранятся в поставщиках `C05T.A00(n)`. Реестры `C53207NpW`..`C53211Npa` возвращают набор, только когда `L8E.A1T()` истинно (`C18780mK.A03()` равно `C21610rj.A0E`); что означает этот предикат, неизвестно.

| Id ресурса | Обработчик | В `phoenix-features.json` | Поведение |
|-------------|---------|----------------------------|-----------|
| `open_bloks_screen_graphql` | `C954246c` | да | Открывает экран Bloks; параметр `app_id` обязателен (иначе приведение типа падает) |
| `open_bloks_screen` | `C954346d` | нет | То же, `fetch_channel` = `GRAPHQL` (использует `bloks_server_params`) или `STATIC` (использует `fetch_channel_params.static_url`, ставит `should_load_bloks_through_cdn: true`); другие значения бросают исключение |
| `send_fds_iq` | анонимный в `AbstractC79003We` | да | Параметры `config`, `type` (`GET`/`SET`), `state`, `parameters`; нужен живой менеджер FDS по job id; отсутствие менеджера или конфига пишет ошибку в лог и завершается с `NOT_CATCHABLE_ERROR` |
| `abprop_fetch` | анонимный в `AbstractC79003We` | нет | Параметры `code` (int), `abprop_type` (`string`/`json`/`boolean`/`float`/`integer`), `default_value`; возвращает `abprop_value`, прочитанное из хранилища AB; allow-list для `code` не замечен |
| `client_dasl_query` | `C954746h` | да | Требует параметр `query`, иначе пишет `No parameters` и завершается ошибкой; запрос выполняется в фоновом исполнителе |
| `dismiss_bottom_sheet` | `C955346n` | да | Закрывает текущий sheet |
| `native_flow_call_manager` | `C954946j` | да | Требует `phone_number`; оставляет только цифры и `+`; запускает `ACTION_DIAL` (`tel:`) с `FLAG_ACTIVITY_NEW_TASK` (только звонилка, без автозвонка) |
| `request_permission` | `C955046k` | нет | Запрос разрешения Android (связь с `FcsRequestPermissionActivity` выведена) |
| `throw_error` | `C954446e` | нет | Поднимает карту `error`; ищет сообщение по `error_map_type` + `code` |
| `payment_encrypt_with_public_key` | `C31703Dr4` | да | Параметры `data_value`, `data_type`, `key_scope`, `provider_name`, `network` (gated) |
| `br_verify_card_deeplink` | `C955446o` | да | Отправляет broadcast, ограниченный пакетом, `com.whatsapp.payments.phoenix.action.launch_activity_for_phoenix_result` с `app_to_app_partner_app_package`, `app_to_app_partner_intent_action`, `app_to_app_request_payload` (gated) |
| `br_verify_card_check_if_app_exists` | `C31702Dr3` | нет | Gated |
| `native_br_compliance`, `native_br_p2m_checkout_address`, `native_card_encryption_resource` | `C955146l`, `C955246m`, анонимный | нет | Платежи в Бразилии, gated, кроме ресурса карт |

Имена только из манифеста (в этой сборке записи в реестре нет): `error_response`, `native_flow_npci_common_library` (поддерево `mode.collect`), `native_p2m_lite_compliance`, `native_p2m_lite_hpp_checkout`, `open_bloks_screen_static`. У `open_bloks_screen_static` нет обработчика; путь STATIC находится внутри `open_bloks_screen` как `fetch_channel`.

### 2.6 Точки запуска (found)

`new C57778Pva(config, params, startState)` создаётся в: `address_message` (`C31337Djk`, NFM), `biz_survey` (`C57417PpS`), `br_merchant_onboarding` (`C33140EcF`), `br_p2m_checkout_add_card`, `br_p2p_verify_card` (`C32703EOj`), а также во входе через deep link, который передаёт названный сервером конфиг со стартовым состоянием `DeepLink` (`RunnableC46615KYo`, случай 18, referral `deeplink`). Строки `add_card_phoenix`, `verify_card_phoenix` существуют; их роль как имён конфигов выведена (inferred). Сама программа конфига приходит с сервера; в APK не поставляется ничего, кроме манифеста возможностей.

### 2.7 Манифест возможностей

`assets/versioning/phoenix-features.json` (1,218 Б, идентичен копии из 2.26.34.4): верхний уровень `pass`, `choice` (21 оператор), `resource` (12 id плюс `input_selector`, `parameters`, `result_selector`, `result_path`), `succeed`, `fail`. Его использование во время выполнения не найдено (строковых ссылок нет); рассматривать как список имён. Авторитетен код (2.4, 2.5).

---

## 3. Bloks

### 3.1 Host-поверхности (found)

| Host | Роль |
|------|------|
| `WaBloksActivity`, `WaBloksBottomSheetActivity`, `BloksCDSBottomSheetActivity`, `BloksCDSPreloadCDSBottomSheetActivity` | Полноэкранный режим, bottom sheet, sheet CDS (дизайн-система) |
| `WaSqBloksActivity`, `WaBloksScreenQueryFragment` | Host для screen-query (типы `screen_query` и `legacy_screen`) |
| `WaFcsModalActivity`, `WaFcsBottomSheetModalActivity`, `WaFcsPreloadedBloksActivity`; `SurveyCanonicalBloksActivity` (+ sheet) | Экраны, размещаемые Phoenix; опросы |
| Продуктовые host | `CommonBloksActivity`, `SupportBloksActivity`, `BrazilPayBloksActivity`, `ConsumerSubscriptionBloksActivity`, `DigitalCommerceDcpBloksActivity`, `CsatSurveyBloksActivity`, `AppointmentBloksHostActivity` (exported false), `WaBackupStorageBloksActivity` (exported false) |

Ни одна activity Bloks, Flows или Phoenix не объявляет intent filter; `targetSdkVersion` равен 36, поэтому activity без `android:exported` не экспортируются (found, манифест). Bloks может также встраивать компонент `WebView` (`AndroidBridge.updateSize`, действие `bk.action.WebViewWithOnChange`) (found).

### 3.2 Запрос: GraphQL по HTTPS (found, `AbstractC40195HfH`, `C45J`)

| Элемент | Значение |
|------|-------|
| URL | `https://graph.<domain>/graphql<path>`; `<domain>` = pref `pref_graphql_domain`, по умолчанию `whatsapp.com`; несколько классов запросов принудительно ставят `facebook.com`; `<path>` пуст или `/extensions` для варианта Flows |
| Строка запроса | `?_emp=1` добавляется, когда AB prop **549** включён (по умолчанию false) |
| Тело | JSON `{"variables": "<json string>", "access_token": ..., "doc_id": <long>, "lang": ..., "Content-Type": "application/json"}` |
| Токен | токен запроса, если задан, иначе статическая строка токена уровня приложения, встроенная в клиент (значение не приводится) |
| Заголовки | `X-FB-Friendly-Name: WABloksAppRootQuery-<app_id>`, `X-FB-Request-Analytics-Tags` |
| `variables` | `app_id`, ключ версии, `params` (JSON-строка), `bloks_theme_params` |
| Имя ключа версии | `version`, `versioning_id` или `bloks_version` в зависимости от класса запроса; значение — та же 64-hex константа, что и в Phoenix |
| Вариант до согласия (`C136975rF`) | добавляет `app_version`, `locale`, `df_token`, `enc_token`, `disclosure_id`, `is_paused`, `country_code`, `encrypted_rid` |
| Вариант Extensions (`C132735kG`, случай 2) | `extension_id` (= `flow_id` для версий flow message 2, 3, 4), `business_jid`, `screen_id`, `bloks_version` |
| Ошибки | `errors[].extensions.error_code` (по умолчанию 417), `is_retryable`; `error.code` 3489039 запускает проверку целостности и повтор, 1675012 даёт `Bad Request` (путь до согласия) |

Корневые поля ответа (`AnonymousClass451.A05`): payload находится в `data.<root>.payload` (JSON-строка).

| Doc id | Корневое поле | Используется (found) |
|--------|------------|-----------------|
| 3651100555017197 | `whatsapp_bloks_getlayout` | маршрут по умолчанию; minishops link/pdp/storefront |
| 3958953970834604 | `whatsapp_bloks_getprivatelayout` | по умолчанию для `C5LX.A00()`; уведомление о конфиденциальности minishops, предпросмотр товаров |
| 9404809712971896 | `whatsapp_bloks_getlayout` | семейства с маршрутизацией по regex (3.3) |
| 9943385105682204 | `whatsapp_bloks_getprivatelayout` | `logged_out.cxthelp.whatsapp` |
| 6019334944816363 | Layout Flows (корень `whatsapp_galaxy_bloks_getflowlayout` существует в `AnonymousClass424`; связь между ними выведена) | `com.bloks.www.whatsapp.galaxy.flow.v2`, `...commerce.galaxy_message`, `...commerce.extensions_message_v2` |
| 36103976949247233 | `wamo_bloks_get_layout` | поверхности WAMO |
| 9676557989071413 | не сопоставлен корневому полю | образцы/care платежей, `novi.care.*`, согласие `whatsapp.ai.biz.*` |

Doc id 26891716230495873 (pix playground) и 25865201793138751 присутствуют в таблицах маршрутизации без выясненного корневого поля.

### 3.3 Маршрутизация по app-id (found)

Экран адресуется через `app_id` (точечное имя, `com.bloks.www.*`). Таблицы маршрутизации сопоставляют `app_id` с дескриптором запроса `C5LX(doc id, вариант фабрики запросов)`: десять таблиц с фиксированными наборами (`InterfaceC148576Pp`: `C132235jS`..`C132335jc`) и таблицы regex (`InterfaceC148726Qe`: `C132345jd`..`C132465jp`).

| Семейство | Шаблон или пример | Doc id |
|--------|--------------------|--------|
| Хаб заказов / платежей | `orders_hub(\..+)*`, `fbpay_hub`, `payment.mft.wallet.fbpay_hub`, `(payment.)?mft.wallet.*`, `payment.(bloks.(commerce|ecp).checkout|fbpay.ecp).*` | 9404809712971896 |
| `gai` / `sna` / AI-стикеры (смысл семейства выведен из имён) | `bloks.nme.gai`, `wa.nme.gai`, `wa.sna`, `whatsapp.ai.stickers.*` | 9404809712971896 |
| Подписки | `dcp.subscriptions?(\..+)*` | 9404809712971896 |
| Поддержка | `(csf|cxthelp)(\..+)+` | 9404809712971896 |
| Minishops | `minishops.link.app`, `.whatsapp.pdp`, `.storefront.wa` | 3651100555017197 |
| Согласие бизнес-AI | `whatsapp.ai.biz.{learn_more,consent,assistant_consent,third_party_consent,meta_ai_consent}` | 9676557989071413 |
| Playground / отладка | `wa.playground.payments.br.pix.*` (вариант 9) ; `whatsapp.payments.phoenix.{debug,demo_*,multi_*}`, `payments.whatsapp.f2care`, `novi.care.*` (вариант 10) | 26891716230495873 ; 9676557989071413 |

В коде находятся 87 различных литеральных id `com.bloks.www.*`; остальные приходят с сервера и маршрутизируются семействами regex. В `AnonymousClass514` есть две защиты по шаблону: id `consent(...)` могут нести `extra_params_json.whatsapp_bloks_networking_feature_override`; `payment.mft.security.*` с `ptt_use_case = WALLET` выбирает вспомогательный класс запроса `wallet_canonical` (found).

### 3.4 Формат payload (found)

Потоковый JSON-парсер `AbstractC122255Jb`; верхний объект содержит `payload` (строка) и `layout.bloks_payload`.

| Ключ `bloks_payload` | Значение |
|---------------------|---------|
| `tree` | Корневой компонент (раздел ниже); `action` вместо `tree` для payload только с действием |
| `ft` | Таблица функций: id в строку выражения |
| `data`, `values`, `templates`, `props` | Записи данных (`id`, `type`, `data`, `scoped`), выражения значений, шаблоны, таблица имён props |
| `embedded_payloads`, `hoisted_async_components` | Вложенные payload по id |
| `referenced`, `referenced_external`, `referenced_embedded_payloads`, `referenced_templates`, `referenced_ft_entries`, `referenced_values`, `referenced_ct`, `ct` | Списки зависимостей для частичных/потоковых payload |
| `component_queries` | Асинхронные запросы компонентов (`id`, `app_id_expr`, `params`, `client_params`, `targets`, `cache_ttl_expr`, `disk_cache_enabled`, `is_scoped`) |
| `error_attribution` | `logging_id`, `source_map_id` |
| `depth`, `step_debugger_metadata.breakpoints` | Глубина потока, отладчик |

Кодирование дерева (`C5AN`): узел — объект с единственным ключом в виде одной кодовой точки; эта кодовая точка является id компонента (`AbstractC105654gT.A00` = `codePointAt(0)`); ключи атрибутов также являются одиночными кодовыми точками (`!`=33 id, `#`=35 child, `&`=38, `+`=43 для теневого компонента 13347). Отображение id компонента в имя в assets отсутствует (unknown).

Id функций («Lispy», `C122545Ki`): узел скрипта — JSON-массив, первый элемент которого — функция: `"#<name>"` именованная, точечное имя, разрешаемое через таблицу имён `AbstractC111054pC.A01`, или строка в base-36, разбираемая через `Integer.parseInt(s, 36)`. Типизированные константы имеют фиксированные id: 17809 `bool.Const`, 18327 `f32.Const`, 18338 `f64.Const`, 19222 `i32.Const`, 19237 `i64.Const`. В таблице имён 681 запись, id от 17293 до 26071.

Расшифровано по поставляемым шаблонам (токен base-36, id, имя в таблице; found): `e2a` 18226 `core.If`; `e25` 18221 `core.GetArg`; `e2f` 18231 `core.TakeLast`; `e1w` 18212 `core.Apply`; `dng` 17692 `bloks.GetParameter`; `dnt` 17705 `bloks.GetVariable2`; `f4g` 19600 `map.Get`; `f6m` 19678 `mins.CallRuntime`; `igq` 23930 `core.AsNonnull`; `fjm` 20146 `screen.callback.DidFetchSucceed`; `foz` 20339 `ttrc.MarkerStart` (все под `bk.action.`); `h9h` 22373 указан с литеральным именем `null`.

Текстовая форма `\t(...)` в `ft` и строках выражений — другая сериализация; то, что она использует те же id в base-36, следует из согласованности приведённых выше расшифровок (inferred). Текстовый парсер не читался.

Согласование возможностей (inferred): 64-hex `bloks-versioning-id` отправляется с каждым запросом; в таблице 50 имён возможностей `bk.versioning.*` (например `SupportsFunctionTables`, `TemplatePayloads`, `AsyncComponentBatchedWireProtocol`, `SupportsLispySignatureMinification`). То, что хеш идентифицирует этот набор возможностей, выведено (inferred).

Поставляемые assets (`assets/json/bloks_screen_template.json`, `bloks_bottomsheet_template.json`, `bloks_cds_base_screen_template.json`, 9,028 / 9,124 / 11,443 Б, идентичны 2.26.34.4): корневой шаблон со спиннером в `tree`, одной записью `component_queries`, целью которой является `genScreenContent`, и резервным экраном ошибки в `embedded_payloads` (`Something went wrong` / `Please try again later` в двух из трёх). Это заготовки; продуктовые экраны приходят из результата запроса.

### 3.5 Пространства имён действий (found, `AbstractC111054pC`)

| Префикс | Количество в таблице id | Примеры |
|--------|-------------------|----------|
| `bk.action.core/bool/num/i32/i64/f32/string/array/map/math` | 113 | `core.If`, `core.Let`, `core.While`, `array.Map`, `string.*` |
| `bk.action.mins.*` | 36 | `CallRuntime`, `PutByVal`, `Raise` (ВМ minscript) |
| `bk.action.bloks.*` | 61 | `OpenScreen`, `OpenBottomSheet`, `Inflate`, `FetchAsyncComponents`, `WriteLocalState`, `ReplaceChildren`, `WriteGlobalConsistencyStore` |
| `bk.action.cds.*`, `bk.callbacks.cds.*` | 13 + | `OpenCdsBottomSheet`, `PushCdsBottomSheet`, `UnwindToScreen` |
| `bk.action.animated/animation/timer/collection/textinput/text_input/video` | 58 | Поведение UI |
| `bk.action.qpl/ttrc/trace` | 14 / 11 / 2 | Маркеры задержки (`ttrc.MarkerStart`) |
| `bk.action.privacy.consent.*` | 10 | `OpenFlow`, `LaunchConsent`, `ShutdownExperience` |
| `bk.action.waffle.*`, `bk.fx.*`, `bk.waffle.*` | 37 / 11 / 2 | Привязка Accounts Center: `EncryptPassword`, `DeleteLocalUserCredentials`, `GetProfilePictureUrl`, `UnpauseWithNativeAuthBlob`, `PregenerateAndCacheRSAKeyPairs` |
| `bk.action.mft.*`, `bk.action.frontier.*`, `bk.action.apt.PleEncrypt`, `bk.action.commerce.GetPaymentToken`, `bk.action.payments.GetCreditCardMetaData` | 5 / 5 / 1 / 1 / 1 | Платежи: `ModularGeneratePTT`, `LaunchGooglePaySheet`, `IsLuhnCompliant` |
| `bk.action.navigation.OpenUrl`, `bk.fx.action.OpenURLInIAB`, `bk.action.acp.OpenUrlExternally`, `bk.action.OpenUniversalLink`, `bk.action.DeeplinkToOtherAppOrDirectToAppStore`, `bk.action.bloks.IsAppInstalled` | 6 | Переходы из Bloks наружу |
| `bk.action.io.clipboard.SetString`, `bk.action.RequestPermission`, `bk.action.media.LoadAlbums`, `bk.fx.action.media.OpenMediaPicker`, `bk.action.foa.media.OpenCamera` | 5 | Доступ к устройству |
| `wa.action.*` | 75 | Host-действия WhatsApp (таблица ниже) |
| `wa.callbacks.*` | 10 | `FormInputOnTextChange`, `CodeInputOnTextChange`, `DatePickerOnDateSet`, `CameraViewOnMediaCaptured`, `ListViewItemSelected` |
| `bk.versioning.*`, `wa.versioning.image.base64` | 50 / 1 | Имена возможностей |

Значимые `wa.action.*` (id от 22391 до 26071):

| Группа | Имена |
|-------|-------|
| Сеть | `IQRequest`, `AsyncRequest`, `UploadMedia`, `UploadProfilePicture` |
| Мост Phoenix | `phoenix.FdsIq`, `FdsIqV2`, `FcsReturnResult`, `FcsReturnResultV2`, `FcsReturnResumableData`, `statemachine.GoBack`, `GoBackV2` |
| Состояние приложения | `GetAbPropValue`, `GetAppType`, `GetIntentParameter`, `LoadScreenParam`, `SaveScreenParam`, `IsDarkModeEnabled` |
| Навигация | `OpenUrl`, `RouteToNativeScreen`, `RouteToNativeBenefitDetail(V2)`, `navigation.OpenChat`, `OpenContactInfo`, `OpenNativeActionSheet`, `FinishActivity(WithResult)`, `PopScreen` |
| Сообщения / коммерция | `commerce.SendNFMReplyMessage`, `commerce.ActionWithCallback`, `share.Text`, `bonsai.SubmitFeedback`, `care.OpenContactSupport`, `care.OpenReportThisPayment` |
| Телеметрия | `SendFieldStat(V2)`, `StartFieldStatTimer`, `GetFieldStatEventId`, `perf.TrackPerformance`, `novi.EncryptLogEvent(V2)` |
| Deeplink | `RegDeeplinkListener`, `DeregDeeplinkListener` |

Защита, найденная в действии Bloks IQ (`C129575f5.A0Y`, лог `IQRequestHelper/sendIQRequest: Invalid XMLNS`): проходят только xmlns `w:pay` и `urn:xmpp:whatsapp:account` (`C33327EfH.A02`); всё остальное вызывает колбэк `on_failure`. Таким образом, скрипты Bloks могут отправлять IQ только в этих двух пространствах имён (found). Реализации обработчиков большинства остальных id `wa.action.*` не прослеживались (их код вызывается по числовому id).

### 3.6 Запросы компонентов и кэширование (found)

- `component_query` загружает асинхронный компонент по `app_id` тем же путём GraphQL (менеджер `C5L9`, тег лога `BloksComponentQueryManager`); `app_id_expr`, `params`, `client_params` и `cache_ttl_expr` — выражения Lispy, вычисляемые на клиенте.
- Два уровня кэша: кэш в памяти (`cache_src: memory`, `cache_age`) и дисковый кэш с ключом на каждый запрос (`BloksComponentQueryDiskCache`; классы `C5NA`, `C5NN`, `C136885r6`). Дисковые записи сериализованы средствами Java (`ComponentQueryDiskCacheRecord`: `DiskCacheData{initialResponse, extensions}`, `responseTimestampMs`, `BloksComponentQueryResources`); метаданные хранятся под `__disk_metadata`; ввод-вывод выполняет `Bloks_ACQ_ReadWriteThread`. `disk_cache_enabled` — переключатель на уровне запроса.
- Действия `bk.action.AsyncComponentCacheWrite`, `bloks.ClearCachedAsyncComponents`, `bloks.InvalidateCachedAsyncComponents` позволяют payload управлять кэшем.
- Каталог, предел размера и вытеснение дискового кэша: unknown. Java-десериализация записей кэша, на которые влияет сервер, происходит только из собственного кэша приложения (выведено из пути кода).

---

## 4. Native flow messages и WhatsApp Flows

### 4.1 Реестр кнопок NFM (found, `AbstractC30032D4u`, случай 442, класс `EYT`)

Интерактивное сообщение несёт кнопки с `nativeFlowInfo.name` и JSON параметров. Диспетчеризация: `C33370Efz.A05` ищет имя в карте (`C0VA`) примерно из 40 подклассов `AbstractC33168Ech`; неизвестные имена пишут `can not recognize NFM action` и отбрасываются; действие может быть отключено gate (счётчики `wa:nfm_dispatch_gate_blocked` / `_observed`).

| Набор | Имена |
|-----|-------|
| Поддерживаемые имена кнопок (39) | `cta_catalog`, `review_and_pay`, `review_and_pay_v2`, `cta_call`, `cta_url`, `cta_copy`, `cta_pix_code_copy`, `offer_payment_account`, `form_message`, `open_webview`, `catalog_message`, `voice_call`, `video_call`, `landline_call`, `quick_reply`, `single_select`, `view_product`, `call_permission_request`, `cta_app_link`, `appointment`, `automated_greeting_message_view_catalog`, `send_location`, `order_status`, `booking_confirmation`, `booking_status`, `psi_nux_opt_in`, `psi_tos_opt_in`, `psi_opt_outs`, `account_authentication_request`, `request_contact_info`, `agent_api_key`, `otp`, `payment_reminder`, `cta_reminder`, `payment_request`, `api_signup`, `inapp_signup`, `split_payment`, `send_payment` |
| Второй набор | `address_message`, `galaxy_message` (запускают flow; роль выведена из использования) |
| Allow-list смешанных/quick-reply | `C33370Efz.A08`: `cta_url`, `cta_call`, `voice_call`, `video_call`, `cta_copy`, `menu_options`, `cta_reminder`, `view_product`, `cta_app_link`, `galaxy_message`, `otp`, `booking_*`, ... |

- `address_message` запускает конфиг Phoenix `address_message` (`C31337Djk`, found).
- `galaxy_message` открывает WhatsApp Flows (4.2).
- Ответы flow хранятся в `message_ui_elements_reply` (`flow_id`, `element_type` 8) и `interactive_message_bloks_widget` (found, SQL).

### 4.2 Параметры и запуск `galaxy_message` (found, `C31338Djl`, `C31337Djk`)

| Ключ в JSON параметров | Назначение |
|--------------------|-----|
| `flow_id` | должен соответствовать `\d+` для действия Flows v2 |
| `flow_token`, `flow_cta` | обязательны вместе с `flow_id` (путь Flows v2) |
| `flow_message_version` | `2`, `3`, `4` выбирают переменные extension запроса Bloks |
| `flow_action` (`navigate` по умолчанию, `data_exchange`), `flow_action_payload` (объект) | первый экран / канал данных |
| `mode` | `draft` помечает черновик flow (`is_draft`) |
| `form_type` | направляет в `FlexCheckoutNativeFormActivity` (flexible checkout) |
| `flow_token_signature`, `www_proxy_secret` | передаются странице, только когда AB prop **14825** включён |

JID бизнеса-отправителя берётся из чата (`FlowsV2Action`); без него запуск прерывается (`cannot launch flow without business jid`). Существуют два рендерера: веб-приложение (4.3) и путь через Bloks (`com.bloks.www.whatsapp.galaxy.flow.v2`, раздел 3.2). Какой из них берёт конкретное сообщение, не выяснено; AB props **22787** (отдельная activity или bottom sheet) и **14222** читаются на веб-пути.

### 4.3 Веб-приложение Flows (found)

| Элемент | Значение |
|------|-------|
| Базовые URL (строковые AB props) | **7153** `https://flows.whatsapp.net/flows` (предзагрузка, `C35814Ff9`), **6060** то же значение по умолчанию (загрузка flow JSON `EP6`: база + `/json/` + flow id, выведено из порядка построителя), **7125** `.../flows/cache_management/` (очиститель кэша `C39066GzF`, интервал **7126** = 1382400), **16723** `.../flows-app/catalog` (каталог) |
| Host | `SecureWebView` (`com.facebook.secure.securewebview`): доступ к файлам и content выключен; загрузка разрешена, только если схема `https` И хост равен хосту launch URL или его поддомену (`GAP.A00`, `H26`, объединяются через AND в `GAL`); иначе в лог пишется `Uri is blocked` |
| Launch URL | из bundle (`url`, по умолчанию `about:blank`); база — AB prop, поэтому сервер может её сменить; политика хоста следует за launch URL (выведенное следствие) |
| Предзагрузка | `FlowsWebPreloader` загружает AB **7153** в скрытом WebView (`setCacheMode(2)`); версия кэша service worker отслеживается через `flows_service_workers_cache_version` |
| Внедрение в страницу | тег `meta` с viewport, `layoutDirection`, `locale`, `timeZone`, `supportedStyles` |
| Мост | `window.WhatsAppBridge.invoke(method, data, cb)`; нативная сторона создаёт `MessageChannel` и отправляет `init-port` с портом 1 (`HQD`); сообщения — JSON `{method, data, callbackID}`; ответы `{callbackID, responseData}` |
| Привязка к origin | Скрипт моста внедряется через `evaluateJavascript` в любую страницу, которую показывает WebView; порт отправляется на цель `Uri.EMPTY`; ограничение опирается на политику URL SecureWebView (inferred) |
| Flow JSON | `flow_json` загружается `EP6.A01` (HTTP GET, хранится на диске как сериализованная строка, ключ `<id>_<id2>`), только когда AB **8552** включён; `FlowsWebViewDataRepository` собирает bundle (`flow_json`, `flow_action_payload`, `creation_source`, id сессий) |
| Публичный ключ | `WAExtensionsGetPublicKey` возвращает публичный ключ эндпоинта, полученный GraphQL-вызовом метаданных (ошибки `extensions-metadata-graphql-*`, режим `required` или `optional`); использование для шифрования данных выполняется на стороне страницы (inferred) |

Методы моста, обрабатываемые нативно (30; `C41342Hyk`, `FlowsWebBottomSheetContainer.CKc`):

| Группа | Методы |
|-------|---------|
| Сессия | `WAExtensionsGetFlowData`, `WAExtensionsDataChannelExchange`, `WAExtensionsNavigate`, `WAExtensionsComplete`, `WAExtensionsClose`, `WAExtensionsGetPublicKey`, `WAExtensionsGetClientAbProps` |
| UI | `WAFlowsShowNativeInputDialogComponent`, `WAExtensionsConfigureNavBar`, `WAFlowsMediaSelect`, `WAFlowsMediaRetry`, `WAFlowsMediaDelete`, `WAFlowsCopyText`, `WAFlowsOpenURL`, `WAExtensionsLearnMore`, `WAExtensionsContextualHelp` |
| Бизнес | `WAExtensionsSpamReport`, `WAExtensionsReportItem`, `WAFlowsDownloadResponse`, `WAFlowsMarketingDisclosureState`, `WAFlowsMarketingDisclosureUserAction` |
| Корзина | `WAFlowsStoreShoppingFlowContext`, `WAFlowsGetCart`, `WAFlowsSetCartItem`, `WAFlowsClearCart` |
| Телеметрия | `WAMLogger`, `WAQPLLogger.start`, `.end`, `.annotate`, `.point` |

Замечания об обработке: `WAFlowsOpenURL` запускает `ACTION_VIEW` только для URL `https`, иначе показывает snackbar; `WAExtensionsGetClientAbProps` возвращает любой AB prop по коду и типу (`bool`, `int`, `float`, `string`, `json`) без замеченного allow-list (`C37367GJs`); неизвестные методы попадают в обработчик по умолчанию (`GJW`); ввод, который не удаётся разобрать, даёт `extensions-bridge-api-input-parse-error`.

### 4.4 Завершение flow

`WAExtensionsComplete` завершает сессию, и клиент отправляет сообщение-ответ native-flow (столбцы `native_flow_response_*`; параметры несут `wa_flow_response_params`, `flow_creation_source`, `response_message`) (found по именам; путь отправки не прослежен).

### 4.5 Запрос эндпоинта Flows

Класс результата `AnonymousClass456` читает корень `whatsapp_galaxy_forward_flow_data_response` или `xwa_flows_make_flow_endpoint_request` и `status_code`: 200 ok, 421 и 504 отображаются в отдельные исходы, остальные — общая ошибка (found). Выполняется ли это поверх MEX или стека HTTPS GraphQL, неизвестно (база парсера общая с Bloks).

---

## 5. Поверхности, не являющиеся UI, описываемым сервером

### 5.1 AI rich response (переносится в сообщении, фиксированные компоненты)

Protobuf `richResponseMessage` (см. `WA_META_AI.md`, раздел 6.3). Enum типов подсообщений `EnumC32139E2l` (found): `AI_RICH_RESPONSE_UNKNOWN` 0, `GRID_IMAGE` 1, `TEXT` 2, `INLINE_IMAGE` 3, `TABLE` 4, `CODE` 5, `DYNAMIC` 6, `MAP` 7, `LATEX` 8, `CONTENT_ITEMS` 9; классы подсветки кода (`KEYWORD`, `STRING`, `NUMBER`, `METHOD`, `COMMENT`, `DEFAULT`); метаданные dynamic `IMAGE`, `GIF`. Клиент отображает фиксированный набор; действия — загрузка файла / пересылка (`UnifiedResponseActionHandlerFactory`). Нет ни языка скриптов, ни DSL действий.

### 5.2 Карточка FMX

Карточка FMX (`LE7`, фабрика view-model `fmxViewModelFactory`, тег аватара `fmx-card-v2`) создаётся клиентом как системное сообщение (`C198788cr`: `Creating FMX card system message for chat`); счётчики вроде `fmxBizEnterpriseSenders`, `fmxMissingLidMapping`, `fmxSuspiciousBottomSheetCacheMiss` показывают, что она управляется локальными сигналами. Передаёт ли сервер какой-либо текст карточки, неизвестно. Рассматривать как нативный UI.

### 5.3 Скрипты встроенного браузера (iabjs)

В `res/raw/iabjs_*` 15 скриптов в 2.26.41.6 (на четыре больше, чем в наборе 2.26.34.4): `autofill_execute_callback`, `autofill_language_detect`, `autofill_payment_detection`, `otp_autofill` новые. Host `WaInAppBrowsingActivity` (exported false).

| Элемент | Значение (found) |
|------|---------------|
| Объект моста | `iabjs_unified_bridge`: `addWebMessageListener(name, allowedOrigins, listener, jsWorld)` в изолированном мире JS `iab_js`, когда поддерживается (`HJY.A05`); запасной вариант `addJavascriptInterface("iabjs_unified_bridge")` (`RunnableC40709HoJ`) |
| Сторона страницы | `window.__call_iabjs_unified_bridge(method, nonce, payload)` отправляет `{method, payload, nonce}`; nonce подставляется в `window.__iabjs_unified_bridge_nonce="%s"` при внедрении |
| Нативная проверка | `C39590HNn`: JSON `nonce` должен совпадать с nonce, сохранённым в обработчике (генерируется один раз на обработчик через `AbstractC48382LBd.A00().toString()`, похоже на UUID, inferred); несовпадение записывает `invalid_nonce` и отбрасывает вызов; метод `iabjs_register_proxy` регистрирует мир; остальные методы идут слушателям с ключом (мир, метод) |
| Новое в этой сборке | `iabjs_autofill_payment_detection` классифицирует поля в `cc-number`, `cc-exp`, `cc-exp-month`, `cc-exp-year`, `cc-csc`, `cc-name` по `autocomplete` или regex по name/id/placeholder; `iabjs_otp_autofill` заполняет `input[autocomplete="one-time-code"]`; `iabjs_autofill_language_detect` отправляет `languageDetermined` |
| Набор разрешённых origin | `Set`, передаваемый вызывающим; содержимое не прослежено (unknown) |
| Устаревший запасной вариант | у `addJavascriptInterface` нет фильтра по origin (поведение платформы, inferred) |

Восемь из 11 более старых скриптов побайтово идентичны копиям 2.26.34.4; `detect_login_forms`, `navigation_performance_logger_android`, `iabjs_bridge_init` изменились (453 Б против 433 Б для инициализации моста).

---

## 6. Песочница и сводка по безопасности

| Контроль | Где | Уровень |
|---------|-------|------|
| Id ресурсов Phoenix зафиксированы в коде; неизвестный id даёт `ResourceNotFound` | `QKb.A03` | found |
| Операторы Phoenix зафиксированы (28); несовпавший оператор пропускается | `RsJ`, `AbstractC56245PPq` | found |
| Действие Bloks IQ ограничено xmlns `w:pay`, `urn:xmpp:whatsapp:account` | `C33327EfH.A02` | found |
| Id функций Bloks зафиксированы (681 именованная) | `AbstractC111054pC`, `C122545Ki` | found |
| Имена NFM зафиксированы (39 + 2); неизвестные отбрасываются | `AbstractC30032D4u`, `C33370Efz` | found |
| Host Flows: только https + launch-host (или поддомен), без доступа к file/content | `SecureWebView`, `GAP`, `H26` | found |
| Мост Flows: фиксированный список методов; `WAFlowsOpenURL` только https | `FlowsWebBottomSheetContainer` | found |
| iabjs: проверка nonce, изолированный мир, набор origin | `C39590HNn`, `HJY` | found |
| Broadcast Phoenix `br_verify_card_deeplink` ограничен собственным пакетом | `C955446o` | found |
| Все activity Bloks, Flows, Phoenix без intent filter; targetSdk 36 | манифест | found |
| Проверка подписи или хеша содержимого Bloks/Phoenix | не обнаружена; `BloksTrustedPayload` без ссылок | found (отсутствие в просмотренных путях) |
| Сервер может читать AB props по коду (`abprop_fetch`, `WAExtensionsGetClientAbProps`) | allow-list не замечен | found |
| Доверие к транспорту (TLS pinning, обработка токена для запросов graph) | не анализировалось | unknown |

Следствие (inferred): доверие опирается на транспорт и перечисленные выше реестры; скомпрометированная или вредоносная серверная программа ограничена этими реестрами, но в реестры входят помощники шифрования платежей, обработка учётных данных Accounts Center, `ACTION_DIAL`, открытие URL и чтение AB.

---

## 7. Кэширование и предзагрузка

Запросы компонентов Bloks: память + диск, TTL по `cache_ttl_expr` (3.6). Phoenix: перечисленные сервером `next_screens` предзагружаются в `WaFcsPreloadedBloksActivity`; записи `persist_data` идут слушателям по ключам (found). Flows web: предзагрузка WebView, версия кэша service worker, плановый очиститель (AB 7125/7126), дисковый кэш flow JSON, маркер бана метаданных `extensions_metadata_banned_<id>_<id>` в prefs (found).

---

## 8. Feature-флаги (значения по умолчанию из `C08J`; смысл — по месту чтения)

| ID | Тип | По умолчанию | Читается в | Эффект |
|----|------|---------|---------|--------|
| **549** | bool | false | `AbstractC40195HfH.A03` | Добавляет `?_emp=1` к URL GraphQL (если не `C0GD.A02()`) |
| **7153** | string | `https://flows.whatsapp.net/flows` | `C35814Ff9` | URL предзагрузки Flows |
| **6060** | string | то же | `EP6`, `C33350Efe` | База Flows для `/json/<id>` |
| **7125** | string | `.../flows/cache_management/` | `C39066GzF` | URL очистителя кэша Flows |
| **7126** | int | 1382400 | `C39066GzF` | Интервал/включение очистителя (единица неизвестна; > 0 включает) |
| **8552** | bool | false | `FlowsWebViewDataRepository.A07` | Загружать flow JSON нативно и передавать странице |
| **14825** | bool | false | `FlowsWebViewDataRepository.A06` | Передавать `www_proxy_secret` и `flow_token_signature` |
| **22787** | bool | false | `C31338Djl` | Flows в отдельной activity или в bottom sheet |
| **24781** | bool | false | `FlowsWebBottomSheetContainer` | Без него восстановленный sheet закрывается сам |
| **14222** | bool | false | `C31338Djl` | Gate в пути запуска Flows (точный эффект неизвестен) |
| **5333**, **1319** | bool | false / false | `C45J`, вариант Flows | Оба включены: ошибки layout Flows сообщаются как `extensions-layout-unexpected-error` |

Id флагов используют числовое пространство `WA_AB_PROPS.md`.

---

## 9. Baileys (`baron-baileys-v2`)

У клиента Baileys нет рендерера, поэтому Bloks и веб-часть Flows недоступны. Затронуть можно часть, переносимую в сообщении, и, в принципе, IQ.

| Цель | Что работает | Почему может не сработать | Исправление |
|------|------------|-------------------|-----|
| Отправить кнопку Flow | `interactiveMessage.nativeFlowMessage.buttons[]` с `name: 'galaxy_message'` и `buttonParamsJson`, содержащим ключи из 4.2 (`flow_message_version`, `flow_id`, `flow_token`, `flow_cta`, `flow_action`, `flow_action_payload`) | Получателю нужен контекст JID бизнеса, числовой `flow_id`, `flow_token`, `flow_cta`; отправители-пользователи (не бизнес), вероятно, не будут приняты (inferred) | Отправлять с зарегистрированного бизнес-аккаунта; держать `flow_id` числовым |
| Использовать неизвестное имя кнопки | нет | `C33370Efz` отбрасывает имена вне 39 + 2 | Использовать имя из 4.1 |
| Получить программу Phoenix | `<iq xmlns="phoenix" type="get"><fds config=... /></iq>` | Сервер решает по состоянию аккаунта/приложения; содержимое ответа не перехватывалось | Не пробовалось; считать unknown |
| Прочитать экран Bloks | неприменимо | Нужны токен graph, doc id и `bloks-versioning-id`; пути в Baileys нет | Вне области |

---

## 10. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|-------|-----|
| `ResourceNotFound`, flow завершается | состояние `resource` называет id, которого нет в реестре (или gated-id Бразилии в несоответствующей сборке) | Использовать id из 2.5 |
| `state not found for name: <x>` | `next` указывает на отсутствующее состояние или на состояние `version_check` (отбрасывается в `C58392QJx.A01`) | Объявить цель поддерживаемым типом |
| `unsupportedComparisonTypes` / `comparingValuesWithDifferentTypes` | Оператор применён к неверным типам | Согласовать типы; использовать `catch`; `NOT_CATCHABLE_ERROR` перехватить нельзя |
| `FdsIqResource/execute: can't find FdsManager from the job_id` | `send_fds_iq` вне живой сессии | Выполнять внутри сессии, которая его запустила |
| Bloks `Invalid XMLNS` | `wa.action.IQRequest` с xmlns вне allow-list | Только `w:pay`, `urn:xmpp:whatsapp:account` |
| `FcsScreenOpenerBloksDelegate: app_id is not present` | `open_bloks_screen*` без `app_id` | Передать `app_id` |
| `error.code` 3489039 | Потребована проверка целостности (запрос до согласия) | Клиент повторяет после проверки |
| Страница Flows пуста, в логе `Uri is blocked` | Навигация вышла за launch host или использовала не-https схему | Держать контент на launch host |
| `extensions-bridge-api-input-parse-error` | Сообщение моста не является корректным JSON ожидаемой формы | Отправлять `{method, data, callbackID}` |
| iabjs `invalid_nonce` | Неверный или отсутствующий nonce | Использовать внедрённый `__iabjs_unified_bridge_nonce` |

---

## 11. Ключевые различия

| Не путать | Различие |
|----------------|------------|
| Phoenix и Bloks | Phoenix = поток управления поверх IQ; Bloks = экраны поверх GraphQL; они встречаются в `open_bloks_screen*` и `wa.action.phoenix.*` |
| FCS и FDS | Встречаются оба: `flowconfigurationservice` (пакет, `FcsStateMachine`) и `FDS` (менеджер IQ, `<fds>`, лог `FDSManage`); расшифровки «FDS» в коде нет |
| Манифест и код | `phoenix-features.json` перечисляет 12 id ресурсов и 21 оператор; в коде 15 id ресурсов и 28 операторов; приоритет у кода |
| `open_bloks_screen_static` и `open_bloks_screen` + `fetch_channel=STATIC` | Обработчик есть только у второго |
| Ключи дерева Bloks и опкоды | Ключи дерева — кодовые точки компонентов; головы скриптов — id функций (base-36) |
| Flows web и Flows Bloks | Два рендерера для `galaxy_message`: WebView (`flows.whatsapp.net`) и `com.bloks.www.whatsapp.galaxy.flow.v2` |
| Bloks GraphQL и MEX | Bloks отправляет POST на `graph.<domain>/graphql` с `doc_id`; MEX — уровень запросов поверх XMPP, используемый в других местах |
| nonce iabjs и мост Flows | iabjs использует nonce на обработчик в конверте; у моста Flows nonce нет, он опирается на рукопожатие порта и политику URL |
| Rich response и Bloks | Rich response — фиксированный набор protobuf; Bloks — программируемое дерево |

---

## 12. Полный поток

```
[Server]                                          [WhatsApp client]
   │  message: interactive nativeFlowInfo name        │
   ├─────────────────────────────────────────────────►│ C33370Efz: name in registry? gated?
   │        address_message              galaxy_message│
   │             ▼                              ▼      │
   │  Phoenix start C58392QJx.A08       Flows launch C31338Djl: SecureWebView (https, launch host)
   │  IQ <iq xmlns="phoenix"><fds config>      + MessageChannel init-port, or Bloks galaxy.flow.v2
   │◄────────────────────────────────────────────────┤
   │  <fds><states start_at><state type=..>           │
   ├─────────────────────────────────────────────────►│ QKb.A03 loop: resource | choice(28 ops) | pass | subflow | succeed
   │                                                  │ resource -> registry: open_bloks_screen_graphql, send_fds_iq, abprop_fetch, ...
   │  POST graph.<domain>/graphql {doc_id, variables{app_id, versioning id, params}}  (route by app_id: C5LX)
   │◄────────────────────────────────────────────────┤
   │  layout.bloks_payload {tree, ft, component_queries, ...}
   ├─────────────────────────────────────────────────►│ AbstractC122255Jb: tree (code-point keys) + Lispy (base-36 ids)
   │                                                  │ user action -> bk.* / wa.* function id
   │◄── IQ (w:pay | urn:xmpp:whatsapp:account only) ──┤ wa.action.IQRequest
   │                                                  │ wa.action.phoenix.FdsIq / FcsReturnResult -> back into QKb (next / catch / end)
   │◄── WAExtensionsComplete -> native-flow response ─┤
```

---

## 13. Неизвестное

| Элемент | Статус |
|------|--------|
| Расшифровка «FDS»; смысл gate `L8E.A1T()` | unknown |
| Отображение кодовых точек компонентов в имена; имена Lispy сверх перечисленных 681; парсер текстовой формы | unknown |
| Код обработчиков большинства id `wa.action.*` / `bk.action.*` (вызываются по числовому id) | unknown |
| Реальный серверный контент: ни одна программа Phoenix и ни один экран Bloks не перехвачены | unknown (только статический анализ) |
| Транспорт `xwa_flows_make_flow_endpoint_request`; рендерер, который берёт `galaxy_message`; эффект AB **14222** | unknown |
| Расположение, размер, вытеснение дискового кэша; набор разрешённых origin iabjs; серверная целостность помимо TLS | unknown |
| Существует ли фреймворк в стиле Genie в другой сборке | unknown |
