<!-- src-sha1: aacd3c372c813b12cfe335ddb7b3323c8eed3863 -->
# WhatsApp Hatch/Muse AI-агент — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-11-15
**Область:** внутренности AI-агента Hatch/Muse — аттестованный транспорт VM через Noise-шлюз, нативная аттестация carrier + SEV-SNP, control plane и онбординг WAFFLE, поток noVNC agent-browser, рабочее пространство (spaces, feed, goals, ideas, artifacts, approvals, запланированные задачи, коннекторы), безопасное хранилище учётных данных, восстановление идентичности/PIN CVM (`hatch/cvm`, Vesta OPAQUE), платный уровень подписки, вердикт достижимости, почему Baileys/velowa не может это реализовать

---

## 1. Что такое Hatch/Muse

**Hatch** — внутреннее кодовое имя подсистемы AI-агента WhatsApp; **Muse** — пользовательское имя самого агента (`str29b7` "Muse manages emails, books tables, and more."). Агент — не просто персона чата (это Meta AI, описан в `WA_META_AI.md`): он управляет **удалённой конфиденциальной VM ("CVM")**, которая может просматривать веб, выполнять запланированные задачи, иметь собственную файловую систему и вызывать сторонние сервисы от имени пользователя. Всё в этом отчёте — статический анализ уровня `found`/`inferred` для 2.26.41.6 (`WA-APK-BETA/WhatsApp_2.26.41.6/`), с одной исправленной подобластью (§6, система идентичности `hatch/cvm`), повторно проверенной по smali 2.26.45.10. **Ничто в этом отчёте не является `tested`** — ни один прогон на устройстве/через Frida не подтверждает ничего из этого; пробелы динамической проверки отмечены по месту.

### 1.1 Основные сущности

| Сущность | Значение |
|--------|---------|
| Hatch | Внутреннее кодовое имя всей подсистемы агента (VM, рабочее пространство, хранилище учётных данных, слой идентичности/PIN) |
| Muse | Пользовательское имя/персона агента |
| CVM | "Cloud VM" / "confidential VM" — удалённая вычислительная среда агента (AMD SEV-SNP) |
| `HatchVmEndpoint` (`C57830PwR`) | Разрешённая структура подключения к VM: хост, `auth_token`, срок действия, провалидированный токен, карта параметров `notary_token` |
| Noise-шлюз | Отдельная аттестованная Noise-сессия к Meta "noise gateway", передаваемая через Tigon, отличная от основной сессии WA Noise_XX/chatd |
| Agent spaces | Мини веб-приложения, которые агент строит и хостит внутри CVM, реверс-проксируемые в WebView телефона |
| Коннектор | Зарегистрированная привязка между агентом и сторонним сервисом (Gmail, календарь, Messenger, платёжная система, произвольный эндпоинт) |
| `hatch/cvm` (Vesta) | **Система восстановления идентичности устройства/VM и аттестации чипа** агента, PIN-защищённая OPAQUE PAKE — **не** платёжное хранилище (исправляет более раннее исследование, см. §6) |
| Approval gate | Подтверждение с участием человека перед рискованным/необратимым действием агента |

### 1.2 Связь с чатом Meta AI

Muse доступен из той же поверхности чата, что и Meta AI, и использует часть общей инфраструктуры (анонс возможностей через bot-JID — см. §7) и канал JSON-метаданных Hatch, описанный в `WA_META_AI.md` §5 (`HF1`/`HatchMetadataRequestManager`, `ProtocolMessage.aiMetadataOperation`). Но система agent-browser/VM/workspace, которую покрывает этот отчёт — это **отдельная, значительно большая подсистема**: она вообще не идёт через сессию chatd/Noise_XX, имеет собственный нативный транспорт и сохраняет собственное состояние (goals, feed, artifacts, approvals) на стороне сервера в CVM. Private Processing / кластер TEE (Meta AI, отвечающий на вопросы о собственных чатах пользователя, Private Search) — это **третья, отдельная** система — полное разграничение см. в §11.

---

## 2. Обзор архитектуры

### 2.1 Карта пакетов

Все активности Hatch/агента имеют `android:exported="false"` — нет точки входа из другого приложения; всё запускается в процессе из поверхности чата/агента.

| Пакет | Роль |
|---------|------|
| `com.whatsapp.hatch.vm` (`p085vm`) | Control plane / жизненный цикл VM: `HatchVmLifecycleCoordinator`, `HatchVmApiClient`, `HatchVmWaker`, `HatchVmLeaseGate`, `GraphQlHatchAbraTokenProvider`, `HatchAbraTokenRevoker` |
| `com.whatsapp.hatch.onboarding` | `HatchWaffleOnboarding`, `HatchPairingAuthBrowsingActivity`, `HatchMuseConnectionActivator` |
| `com.whatsapp.hatch.computer` / `.conversation.browser` / `.conversation.approval` | `HatchComputerActivity` (полный десктоп VM), `HatchBrowserStreamActivity` (живой браузер в чате), `HatchBrowserPreviewActivity` (approval gate) |
| `com.whatsapp.hatch.feed/goals/ideas/activity/approvalhistory` | UI рабочего пространства: feed, goals + подцели, ideas, история одобрений |
| `com.whatsapp.hatch.artifacts/media` | Артефакты и файлы, созданные агентом |
| `com.whatsapp.hatch.connectors(.ui)` | Каталог сторонних коннекторов, потоки подключения, действие с виртуальной картой, режим разрешений по коннектору |
| `com.whatsapp.hatch.identity.ui` | Документы "о себе" агента |
| `com.whatsapp.hatch.scheduledtasks.impl` | UI повторяющихся задач VM агента |
| `com.whatsapp.hatch.cvm` / `.cvm.pin` | **Не хранилище** — PIN-защищённое восстановление идентичности устройства/VM (Vesta OPAQUE), §6 |
| `com.whatsapp.hatch.subscription(s).iap` | Поток покупки платного уровня, §7 |
| `com.whatsapp.bot.agentspaces.*` | Хост "Spaces": `HatchSpaceActivity` + реверс-прокси `HatchSpaceTunnel`, адаптер `NoiseHatchVmTransport` |
| `com.whatsapp.bot.agentbrowser.*` | Движок браузера + транспорт VM: `BrowserSessionController` (noVNC WebView), `NoiseVmConnection`/`WaNoiseChannel`, `agentbrowser.noise.carrier.*` (нативный JNI) |
| `com.whatsapp.bot.securecredentials.*` | `SecureCredentialVault` — хранилище учётных данных, на стороне сервера в CVM |
| `com.whatsapp.bot.agentactivity/agentfeed/agentgoals/agentapprovals` | Слой данных/feed за UI `hatch.*` |
| `com.whatsapp.bot.infra.vmmedia` | Прямое получение файловой системы VM агента (`/fs/raw/`, `/media/raw/`) |
| `com.whatsapp.bot.quiz` | `AiQuizViewerActivity` — просмотрщик квиза richResponse, **не** функция VM (§2.3) |
| `com.crossapp.tigonhttp(.noise)` | Общий кросс-приложенческий нативный HTTP-стек Meta **Tigon** + `NoiseChannelManagerHolder` |

### 2.2 Три разных транспорта — не путать их

Это самый важный структурный факт, и более раннее исследование ошиблось в отношении одного из трёх (§6.1 исправляет это):

| # | Транспорт | Что несёт | Блокер для стороннего клиента |
|---|-----------|---------|-----------------------------------|
| 1 | **Аттестованный канал Noise-шлюза VM** — `/v1/noise` через Tigon, нативная `libwa-noise-gateway-carrier-jni.so` | Всё интерактивное для агента: HTTP браузера-VM (`/api/*`, `/fs/*`, `/spaces/*`), поток экрана noVNC, функции рабочего пространства, CRUD безопасных учётных данных | Нативный Noise+WebSocket carrier **и** онбординг официального клиента WAFFLE — жёстко блокировано |
| 2 | **Обычный HTTPS control plane** к `hatch-api.meta.ai` | Пробуждение VM, Abra bearer-токен, URL пэйринга, **и** (исправлено, §6) эндпоинты восстановления идентичности `hatch/vesta-auth/*` / `hatch/cvm-*` | Транспорт принципиально наблюдаем через MITM (устройство с root, обход pinning); эндпоинты идентичности дополнительно требуют нативной математики OPAQUE + постквантовых вычислений (`libvesta_client_jni.so`) для формирования валидных тел запроса |
| 3 | **Обычный MEX/GraphQL** через обычный транспорт WhatsApp `whatsapp-android-mex`/`whatsapp-android-www` | Чтение+удаление запланированных задач/напоминаний (1:1 и группа), чтение информации о соответствии подписки, выпуск токена платежей Hatch | Нативного/аттестованного блокера не найдено — достижимо так же, как любая другая MEX-операция |

Транспорт 1 — это то, что оригинальное (2.26.41.6) исследование называет "транспортом Hatch VM", и это подавляющее большинство поверхности подсистемы. Транспорт 3 — это **единственная** часть Hatch, которую клиент в стиле Baileys/velowa может правдоподобно использовать.

### 2.3 Не часть VM — связь с квизом

`com.whatsapp.bot.quiz.AiQuizViewerActivity` — полноэкранный просмотрщик квиза, встроенного в сохранённое richResponse-сообщение бота (примитив квиза richResponse "Jarvis" — территория `WA_META_AI.md` §4.3/§6.3, не Hatch). Он загружает квиз **из локального хранилища сообщений** по row id + key + section (intent extras `ai_quiz_viewer_message_row_id`, `ai_quiz_viewer_quiz_key`, `ai_quiz_viewer_section_index`) — без сетевого вызова, без транспорта VM. Упоминается здесь только чтобы не быть принятым за функцию Hatch; полное разграничение см. в §11.

---

## 3. Control plane и онбординг

### 3.1 Онбординг WAFFLE (`found`)

Первое использование поверхности агента запускает **`HatchWaffleOnboarding`**: клиент доказывает, что он является подлинной, немодифицированной сборкой WhatsApp через аттестацию целостности **WAFFLE** (та же семья аттестации официального клиента, что и UI блокировки `com.whatsapp.waffle.wfac` / привязка аккаунта — см. `WA_CLIENT_INTEGRITY.md` §11 про родственный компонент WFAC). Следы в логах: `"waffle-onboarding"`, `"vm-credentials"`, `"pairing-url"`, `"HatchWaffleOnboarding/link pairing-url-received="`. Сторонний клиент не может сформировать валидный токен WAFFLE, поэтому он даже не может выделить VM — это жёсткий блокер со стороны онбординга, независимый от carrier Noise-шлюза.

### 3.2 Пэйринг (`found`)

`HatchPairingAuthBrowsingActivity` открывает **URL пэйринга** в стиле OAuth, который связывает аккаунт WhatsApp с агентом/аккаунтом Meta AI; завершение логируется как `pairing-url-received`.

### 3.3 Пробуждение VM и bearer-токен Abra (`found`)

`GraphQlHatchAbraTokenProvider` выпускает GraphQL bearer-токен "Abra" для VM; затем `HatchVmApiClient` выполняет:

```
POST https://hatch-api.meta.ai/hatch/vm/wake
{"vm_id": "...", "retry_count": N}
```

Это обычный HTTPS, не Noise-канал. Ответ питает логику кэшированного эндпоинта `HatchVmLifecycleCoordinator` ("connect cached-endpoint", "invalidateToken failed") и разрешается в `HatchVmEndpoint` (`C57830PwR`): host/базовый URL, `auth_token`, `bearerExpiresAtMs`, флаг провалидированного токена и карта параметров, несущая `notary_token` для `/v1/noise`. `HatchAbraTokenRevoker` обрабатывает инвалидацию.

**Достижимость:** вызов пробуждения и выпуск токена — обычный HTTPS/GraphQL, в принципе наблюдаемый через MITM на устройстве с root и обходом pinning — но бесполезный без аккаунта, прошедшего провижининг WAFFLE, поскольку сервер не выдаст рабочий эндпоинт VM нераспознанному клиенту (`inferred`; не подтверждено независимо на стороне сервера).

---

## 4. Аттестованный транспорт VM agent-browser

Это главная находка подсистемы: VM agent-browser **не** идёт через основную сессию Noise/XMPP WhatsApp. Она открывает **отдельную Noise-сессию** к Meta "noise gateway", передаваемую через HTTP-стек Tigon Meta, через выделенную нативную библиотеку, с верификатором аттестации и опциональным предварительно разделённым ключом private-auth.

### 4.1 Handshake (`found`, `WaNoiseChannel`)

`WaNoiseChannel` берёт хост эндпоинта VM и добавляет URL-кодированные query-параметры до handshake:

| Параметр | Источник |
|-------|--------|
| `auth_token` | `HatchVmEndpoint.auth_token` (bearer VM) |
| `notary_token` | значение для ключа `/v1/noise` в карте параметров эндпоинта, только если не пусто |
| `app_id` | константа app-id WA (`inferred`, не разрешена буквально) |
| `app_version` | захардкоженный литерал `"2.26.41.6"` |

Путь handshake: **`/v1/noise`**. Таймаут handshake **20000 мс**; общий бюджет открытия канала **60000 мс** (`NoiseVmConnection`). Следы в логах: `noise/open-start`, `noise/reused`, `noise/closed reason=...`, `noise/use-once`.

### 4.2 Нативный carrier и аттестация (`found`)

`NoiseGatewayCarrier` — JNI-объект `com.facebook.jni.HybridData`, загружаемый `NoiseGatewayCarrierSoLoader` как **`libwa-noise-gateway-carrier-jni.so`** — не отдельный файл в `lib/arm64-v8a/`, он упакован внутри суперпак-блоба `libs.so` (побайтовая статическая экстракция недоступна).

Нативные точки входа: `createNative(TigonServiceHolder, NoiseChannelManagerHolder)`, `start(endpoint, ..., byte[32]?, AttestationVerifierHolder, Stream0Listener)`, `sendWebsocketFrameNative`, `stopNative`, `cancelHandshakeNative`. Колбэки `Stream0Listener` (`onWebSocketUpgraded`, `onTransportReady`, `onReady(NoiseHandshakeOutcome)`, `onMessage`, `onClose/onFailure`) показывают, что канал — это **Noise, обёрнутый внутри WebSocket**.

`AttestationVerifierHolder` имеет три нативных конструктора:

| Вариант | Значение |
|---------|---------|
| `createNoOpNative()` | Без аттестации — вариант, инстанцируемый в декомпилированном пути, наблюдаемом в этом проходе |
| `createSnpNative(bool)` | Аттестация конфиденциальных вычислений AMD SEV-SNP |
| `createSnpPinnedToChipsNative(chips[], bool)` | SNP, закреплённая за конкретными разрешёнными идентификаторами чипов |

**Какой вариант выполняется в runtime — `unknown`** из этого статического прохода. Проход `hatch/cvm` 2.26.45.10 (§6) независимо обнаружил конкретные эндпоинты control plane, которые разрешают в allowlist/фиксируют идентификаторы чипов SEV-SNP (`/hatch/cvm-chip-allowlist`, `/hatch/cvm-chip-selection`), подтверждая, что режим аттестации с закреплённым чипом — это реальная инфраструктура, а не просто спящий путь кода.

`NoisePrivateAuthMode.REQUIRED` плюс 32-байтовый ключ — опциональный режим "private auth" с предварительно разделённым ключом (`inferred`: привязка канала); не заполнен в наблюдаемом пути, `unknown`, используется ли он вообще.

### 4.3 Транспорт HTTP-через-Noise (`found`)

После того как канал открыт, `WaVmHttpTransportImpl`/`VmHttpClient` отправляют обычные JSON HTTP-запросы через туннель Noise через Tigon. Адаптер на уровне приложения (`NoiseHatchVmTransport`, используемый каждой функцией рабочего пространства в §5) выставляет четыре глагола:

| глагол | тег | использование |
|------|-----|-----|
| `CQ4(url, accept)` | `hatch_vm_read` | GET-чтение |
| `AEV(method,url,body,…)` | `hatch_vm_call` | обычный одноразовый вызов |
| `CXY(method,url,headers,body,streaming)` | `hatch_vm_request` | потоковый запрос (120 с, или без ограничения при `streaming`) |
| `Cly(url,body,…)` | `hatch_vm_subscribe` | долгоживущая SSE/дуплексная подписка |

`NoiseChannelHolds` ведёт счёт открытых "удержаний" (holds); канал закрывается после освобождения последнего hold (настраиваемый интервал). Поверхность HTTP-путей VM (`found`, строковые литералы): `/v1/noise`, `/api/`, `/api/computer/subscribe`, `/api/artifacts/pin`, `/spaces/`, `/spaces/v2`, `/spaces/cvm/<slug>`, `/spaces/share/`, `/workspace/`, `/home/hatch/`, `/media/raw/`, `/fs/raw/`, плюс пути учётных данных в §5.9.

### 4.4 Поток экрана noVNC (`found`)

`assets/vmvnc/` поставляет настоящий веб-клиент **noVNC** (`novnc-rfb.js`, `vnc.html`, MPL-2.0 `LICENSE.txt`) — подтверждено независимо присутствующим как в сборке 2.26.41.6, так и в 2.26.45.10 (`assets-sweep.md`). `BrowserSessionController` загружает `https://appassets.androidplatform.net/assets/vmvnc/vnc.html` в WebView. HTML определяет **`BridgedWebSocket`**, переопределяющий `window.WebSocket`: noVNC считает, что он открыл `wss://bridge.invalid/` (субпротокол `binary`), но каждый RFB-фрейм ретранслируется через Android JS-мост `window.AndroidVncBridge` (`socketSend`/`socketClose`/`socketOpen`, колбэки `window.__vncBridge.*`). Собственный комментарий в поставляемом HTML объясняет почему: **реальный эндпоинт websockify требует `Authorization: Bearer <jwt>`**, который WebSocket в WebView не может установить, поэтому реальный сокет принадлежит нативному коду (открыт через Tigon с bearer-токеном VM), а JS-прокладка только ретранслирует фреймы.

Итого: десктоп/браузер VM стримится на телефон как настоящий **RFB (VNC) через WebSocket с аутентификацией JWT-bearer**, сам по себе туннелируемый через аттестованный Noise-шлюз; noVNC отображает его в WebView. Управление вводом (`isViewOnly`, `isInputEnabled`, `isPanModeEnabled`, методы зума/видового окна) и размер (`BrowserViewerJson{width,height,devicePixelRatio}`) управляются нативно. `inferred`: более лёгкие статичные кадры "present"/предпросмотра (`BrowserTaskScreenshotJson`, `BrowserTaskPresentationJson`) обслуживают `HatchBrowserStreamActivity` в чате, тогда как полная интерактивная VNC зарезервирована для `HatchComputerActivity`.

### 4.5 Лизинг управления (`found`)

`BrowserControlLeaseJson{controlOwner, taskId, controlExpiresAtMs}` + `BrowserControlGrantJson`/`BrowserControlEnvelopeJson` реализуют, кто управляет браузером (агент vs. человек, "взять управление"), ограниченный по времени через `controlExpiresAtMs`. `BrowserViewerRequestJson` запрашивает слот просмотрщика. Не путать этот **лизинг управления браузером** с не связанной "заявкой" (bid) выбора чипа SEV-SNP в §6 — см. §11.

### 4.6 Фрейминг туннеля agentspaces (`found`)

`HatchSpaceTunnel` проксирует WebView к приложениям "spaces", хостящимся в CVM, по адресу `/spaces/cvm/<slug>` через `hatch_vm_*`. Небольшой протокол JSON-конверта: `{"type":"http.res",id,status,streaming}`, `{"type":"http.end",…}`, `{"type":"http.err",…}`, плюс push для инвалидации кэша `{"type":"hatch:space:query-invalidated","spaceSlug":…,"payload":{"queryKeys":[…]}}`. Он **удаляет hop-by-hop и идентифицирующие заголовки** перед ретрансляцией — в чёрный список входят `authorization, cookie, host, origin, x-forwarded-*, x-real-ip, x-noise-connection-id` — что подтверждает, что сторона CVM завершает настоящий HTTP-сервер, доступный только через идентификатор соединения Noise.

---

## 5. Рабочее пространство агента

Каждая функция ниже построена на четырёх глаголах `NoiseHatchVmTransport` из §4.3, т.е. каждый путь-литерал ниже — это HTTP-запрос *внутри* туннеля Noise к CVM. Bootstrap: `HatchBootstrapRequest` отправляет `{"sections":[…]}` на метод подписки `channel.bootstrap` и читает в ответ `{"accepted":[…]}` — клиент заявляет, какие секции рабочего пространства он хочет получать. `HatchSpacesSync` запускается только когда "Hatch привязан и существует эндпоинт VM" (`found`, защитные условия в логах).

### 5.1 Agent spaces

**Space** — мини веб-приложение/интерактивная страница результата, хостящаяся агентом, обслуживаемая изнутри CVM, адресуемая строковым `slug`. Телефон никогда не получает HTML напрямую — локальный WebView (`HatchSpaceActivity`) направлен на туннель (§4.6), который стримит HTTP-ответы CVM обратно фрейм за фреймом, так что space может быть живым, сохраняющим состояние приложением, а не статичным артефактом.

| действие | метод + путь | заметки |
|--------|---------------|-------|
| каталог | `GET /spaces/v2` | `{"spaces":[{"slug","preview_card_url","preview_image",…}]}` |
| статус публикации | `GET /spaces/share/<slug>` | возвращает URL шаринга, если опубликовано и публично |
| публикация | многошаговый (`publish`/`post`/`poll`) | может вернуть "требуется подтверждение" |
| снять с публикации | `DELETE /spaces/share/<slug>` | |
| удаление | `DELETE /spaces/v2/<slug>?source=space` | |
| закрепить/снять закрепление артефакта | `POST /api/artifacts/pin {"artifact_ref":…,"pinned":bool}` | закрепляет результат space как артефакт |

Пример из реального мира (`inferred`): пользователь говорит "следи за рейсами в Лиссабон дешевле €200"; Muse строит трекер space; пользователь открывает его живьём, публикует ссылку для шаринга и закрепляет лучший результат как артефакт.

### 5.2 Feed и активность

`HatchFeedApi` декодирует датированный дайджест **выпусков (editions)**, каждый из которых содержит **юниты** (`unit_id, title, kicker, emoji, body_md, days`) — периодический брифинг агента. Поддерживается лентой активности: `GET /api/activity?limit=200` в записи (`timestamp, type, status, title, subtitle, messageId, taskLabel, details.goal{…}`), связывающие каждую запись с сообщением чата и опционально с целью. Самостоятельная точка входа Feed защищена debug-флагом в 41.6 (`str5508` "[Debug Only] Feed"); лента активности, питающая её, не защищена.

### 5.3 Goals (цели)

`HatchGoalsApi`: список `GET /api/goals?<query>`, детали `GET /api/goals/<goal_id>`. Цель — устойчивая задача: `{goal_id, title, emoji, summary, momentum_status, sub_goals:[…], updates:[{text, effective_at}]}` — постоянная задача со статусом здоровья и журналом обновлений с временными метками, в который агент добавляет записи. Точка входа защищена debug-флагом (`str5511` "[Debug Only] Goals").

### 5.4 Ideas (идеи)

Предложенные агентом исполняемые действия, которые пользователь может **Execute** или **Cancel** (`HatchIdeaDetailBottomSheet`). Строки: "This idea is already running.", "This idea isn't available anymore.", "No ideas right now. Check back later.", "Couldn't start that idea. Try again." Пример: агент предлагает "Набросать итоги Q3"; нажатие Execute запускает выполняющуюся задачу, записанную в feed/activity.

### 5.5 Артефакты и медиа/файлы рабочего пространства

Артефакты — результаты, созданные агентом (документ, изображение, таблица, результат space), закрепляемые/снимаемые с закрепления через `/api/artifacts/pin`. Файлы агента живут в **настоящей файловой системе CVM для каждого агента** (`com.whatsapp.bot.infra.vmmedia.HatchWorkspaceMediaApi`):

| вызов | путь | форма |
|------|------|-------|
| библиотека | `POST /fs/library {"preset":"media","limit":n,"offset":m}` | `{entries:[{path,size,modified_ms}],total,has_more}` |
| raw | `GET /fs/raw/<path>` | raw-байты |
| миниатюра | `GET /fs/thumbnail/<path>?p=sm` | |
| удаление | `POST /fs/delete {"path":…,"recursive":false}` | |

Строка подтверждения удаления: "This file will be removed from your agent's files. You can't undo this."

### 5.6 Документы идентичности

Документы "о себе" агента хранятся как **обычные текстовые файлы в той же файловой системе VM**, не в выделенном хранилище: `GET /fs/read {path,offset,len}` → `{text,bytes,eof,not_found}`; `POST /fs/write {path,text|bytes,offset,append,overwrite,create_parent}`. Пользователь редактирует документы, которые агент затем читает как постоянный контекст.

### 5.7 Approvals и история одобрений

**Живой gate:** перед рискованным/необратимым действием агент поднимает запрос одобрения (`HatchBrowserPreviewActivity`, `str54e1` "Approval required"). **История/аудит:** `GET /approvals/history?record_schema=snapshot_v1&limit=50`, постранично через `next_cursor`, в структурированную запись на каждое одобрение: `{approval_id, status, decision, outcome_label, summary_title, purpose_summary, scope_summary, requested_at_ms, permission_question, payload_preview, request_preview_document, display_name, icon_key, blocks, rows, fields, items, links, attachments, version, truncated}`. Точка входа защищена debug-флагом (`str54e8` "[Debug Only] Approval history"), сам лог не защищён.

### 5.8 Запланированные задачи — три разные реализации

| # | Поверхность | Транспорт | Операции | Достижимо клиентом? |
|---|---------|-----------|-----|--------------------|
| a | Напоминания Meta AI 1:1 (`com.whatsapp.metaai.tasks`) | обычный MEX через `whatsapp-android-www` | **`GetMetaAiReminders`**, **`DeleteMetaAiReminder`** | **Условно да** — именованный persisted-query MEX, без аттестованного/нативного блокера |
| b | Запланированные задачи группы (`com.whatsapp.bot.group.groupinstructions.impl`, новое в 41.6) | обычный MEX через `whatsapp-android-www` | **`GetMetaAiGroupReminders`** (параметр `groupId`), **`DeleteMetaAiGroupReminder`** (`groupId`, `reminderId`) | **Условно да** — то же обоснование |
| c | Запланированные задачи VM Hatch (`com.whatsapp.hatch.scheduledtasks.impl`) | Noise VM | повторяющиеся запуски VM агента, отменяемые через транспорт VM | Нет — только нативное |

9a/9b — это **единственные** операции рабочего пространства, которые сторонний клиент может правдоподобно достичь, потому что они не касаются ни нативного carrier noise-шлюза, ни онбординга WAFFLE. Создание напоминания, судя по всему, происходит на стороне агента (через вызов инструмента в чате Meta AI), а не через видимую клиенту мутацию — присутствуют только операции Get + Delete. Числовые `doc_id` для обеих пар — `unknown` (разрешение именованного persisted-query; не захвачено независимо). Поверхность group-instructions также позволяет администратору настраивать Meta AI группы (правила, справочные документы, тон) через `CustomizeGroupMetaAiActivity` — соседний UI, сам по себе не операция запланированных задач.

### 5.9 Коннекторы и безопасное хранилище учётных данных

**Коннектор** — зарегистрированная привязка между агентом и внешним сервисом. Пользователь аутентифицируется один раз (OAuth / API-ключ / имя пользователя+пароль / FoA / Stripe / Messenger), и получившаяся учётная запись хранится **на стороне сервера внутри CVM, никогда в Android Keystore** — `SecureCredentialVault` выполняет все операции как HTTP-вызовы через тот же транспорт Noise-HTTP VM. Ни одной ссылки на `KeyStore`, `EncryptedSharedPreferences` или `AndroidKeyStore` нигде в `securecredentials/` не существует.

Эндпоинты учётных данных (`found`, через Noise-канал VM):

| путь | роль |
|------|------|
| `POST /v1/credentials/capture` | отправить захваченную учётную запись |
| `POST /v1/credentials/catalog/update` | upsert; наблюдаемые поля: `username`, `password`; разрешение через wireValue enum `JA9` |
| `POST /v1/credentials/catalog/delete` | `{id}` → `{ok}` |
| `GET /v1/custom-connectors/list` | |
| `POST /v1/custom-connectors/register` | форма API-ключа `{connector, api_key:{key}, replace_existing}` или форма OAuth `{connector, oauth_bootstrap:{client_id, client_secret?,…}, replace_existing}` → `authorize_url` |

Каталог коннекторов + потоки подключения (`found`, через тот же канал): `GET /api/connectors?surface=settings&icon_cdn=whatsapp` → `{connectors:[{id,name,description,icon,state,is_custom,management_kind,supports_multiple_accounts,consent}]}`; информация подключения по коннектору (`/connectors/<id>/connect/info`) и специфичные для типа пути авторизации для OAuth, API-ключа, имени пользователя/пароля (с `two_factor_required`/`attempts_remaining`/`login_timeout_remaining_secs`), **FoA** (аккаунты Family-of-Apps), **спутник Messenger** (привязка чата, защищённая PIN) и **привязка Stripe** (платежи). Разрешения — по коннектору (`GET/SET /permissions/connectors/<id>`, строка UI "Agent permissions"). Пользовательские коннекторы несут явное предупреждение о непроверенном коде ("Meta не проверяет пользовательские коннекторы… следите за использованием вашим агентом").

По дизайну агент **не видит исходные секреты**: "Securely store passwords for your agent to use", "Shared with your agent without saving". Действие **виртуальной карты** (`HatchConnectorCardActionActivity`) выпускает одноразовую карту, которую агент использует для платежей, так что настоящий номер карты никогда не раскрывается ("The agent will never see your credit card"). `assets/api_key.txt` существует в APK и рассматривается как учётный материал согласно контракту доказательств brain — здесь не открывается/не цитируется; `inferred`, что это API-ключ уровня клиента/приложения для control plane hatch-api/GraphQL, а не секрет на уровне пользователя.

**Достижимость для всего §5:** только нативное. Каждый литерал пути выше восстановим из APK; ничто из этого не управляемо, не наблюдаемо (зашифровано внутри туннеля Noise) и не воспроизводимо со стороннего клиента, потому что каждый из этих вызовов требует аттестованного транспорта из §4 плюс VM, провизионированную через WAFFLE.

---

## 6. Восстановление идентичности CVM — система Vesta OPAQUE PIN (`hatch/cvm`)

### 6.1 Исправление формулировки "хранилище виртуальных карт"

Более раннее исследование (2.26.45.10) описывало `hatch/cvm` + `hatch/cvm/pin` как "хранилище виртуальных карт, защищённое PIN". **Эта формулировка неверна на уровне криптослоя.** Она объединяет две не связанные между собой подсистемы:

- **`hatch.connectors` / `HatchConnectorCardActionActivity`** (§5.9) — настоящий, отдельный поток выдачи коннектора для сторонней платёжной системы (почти наверняка Stripe). Он имеет **нулевые ссылки в коде** на какой-либо класс `com.whatsapp.hatch.cvm` или `com.facebook.vesta` (проверено: нет перекрёстных ссылок из smali `hatch.connectors` на `HatchCvmPinActivity`/`HatchCvmVestaClient`/`HatchCvmKeyService`).
- **`hatch.cvm` / `hatch.cvm.pin`** — это система регистрации идентичности и аттестации чипа конфиденциальной VM агента, а не хранилище карт. Она не хранит **никаких платёжных данных какого-либо вида** — нигде в пакете нет поля PAN/CVV/биллинга. Что она защищает — это **секрет идентичности устройства/VM, восстанавливаемый через обмен ключами с паролевой аутентификацией OPAQUE, где PIN служит паролем**, привязанный к выбору аппаратного чипа AMD SEV-SNP для CVM.

PIN **не является разблокировкой только на локальном уровне**: путь входа `HatchCvmKeyService` выполняет полный обмен OPAQUE с бэкендом Meta (`hatch-api.meta.ai/hatch/vesta-auth/*`, обычный HTTPS) прежде чем какой-либо локальный ключевой материал будет получен/восстановлен. Неверный PIN отклоняется **на стороне сервера** ("wrong pin", "crypto failed"), а не просто против локального хэша.

Критически важно, что этот трафик — **обычный HTTPS к `hatch-api.meta.ai`** — тот же хост control plane, что и `/hatch/vm/wake` (§3.3) — **а не** аттестованный канал VM Noise-шлюза через Tigon. Поэтому общее утверждение "те же жёсткие блокеры, что у транспорта" из §4/§5 здесь не применяется: реальный блокер для этой подсистемы — криптографический, а не аттестации транспорта.

### 6.2 Нативная поверхность

`com.facebook.vesta.VestaClient` загружает **`libvesta_client_jni.so`** (новое в 2.26.45.10). Все 19 заявленных на нём нативных методов реализуют **OPAQUE PAKE с PIN в роли пароля, дополнительно обёрнутую постквантовым слоем KEM/подписи**, плюс шаг проверки привязанного к устройству "HSM-ключа":

| нативный метод | роль |
|---|---|
| `getApiVersionNative` / `getProtocolVersionNative` | согласование версии |
| `beginLoginNative` / `finishLoginNative` (×2 перегрузки) | шаги 1 и 2 входа OPAQUE (производит сессионный/экспортный ключевой материал) |
| `beginRegisterNative` / `finishRegisterNative` / `finishRegisterProtoNative` | регистрация OPAQUE (регистрация нового PIN) |
| `unpackLoginPayloadNative` / `unpackLoginPayloadProtoNative` | декодирование эскроу-полезной нагрузки входа от сервера |
| `validateHsmKeyNative` / `validateHsmKeysWithOtaBundleNative` | валидация аппаратно привязанной пары ключей, опционально с OTA-пакетом ротации ключа устройства |
| `verifyRestoreHistoryNative` | проверка записи истории предыдущего восстановления |
| `pqWrapFinishLoginNative` / `pqWrapFinishRegisterNative` / `pqUnwrapFinishLoginResponseNative` | постквантовая обёртка/развёртка полезных нагрузок входа/регистрации |
| `pqWrapSchemeNative` | какая PQ-схема используется (возвращаемое значение `unknown` — требуется Frida) |

`libvesta_client_jni.so`, как и carrier Noise-шлюза, упакован внутри непрозрачного блоба SUPERPACK — побайтовая статическая экстракция в этом проходе была невозможна. `libvoprf-ed25519.so` (присутствует в той же сборке) согласуется с примитивом OPRF/VOPRF (базовый строительный блок OPAQUE), но **не был** независимо перекрёстно связан с `VestaClient` — зафиксирован как правдоподобная соседняя библиотека, не доказана как та же реализация (`unknown`).

### 6.3 Эндпоинты протокола — обычный HTTPS к `hatch-api.meta.ai`

| путь | роль |
|---|---|
| `POST /hatch/vesta-auth/begin-login` | шаг 1 входа OPAQUE |
| `POST /hatch/vesta-auth/finish-login` | шаг 2 входа OPAQUE, возвращает эскроу-полезную нагрузку |
| `POST /hatch/vesta-auth/begin-register` | шаг 1 регистрации OPAQUE (новый/изменённый PIN) |
| `POST /hatch/vesta-auth/finish-register` | шаг 2 регистрации OPAQUE |
| `GET /hatch/vesta-auth/user-info` | `is_registered` + счётчики попыток/блокировки |
| `GET /hatch/fetch_vms?notary_token=true[&vm_id=]` | список/разрешение CVM(-ов) пользователя |
| `POST /hatch/lease_vm` / `POST /hatch/cold-lease-cvm` | выделить инстанс CVM (тёплый / холодный) |
| `GET /hatch/cvm-replace-state?env_id=` | переход конечного автомата состояния CVM |
| `GET /hatch/cvm-chip-allowlist?env_id=` | какие идентификаторы чипов SEV-SNP разрешены для этой CVM |
| `POST /hatch/cvm-chip-selection` | зафиксировать выбор/заявку чипа |
| `GET /hatch/onboarding_statuses` | проверка статуса онбординга |
| `POST /hatch/vm/wake` | пробудить/возобновить CVM (также §3.3) |

Ни один из них не касается `/v1/noise` или глаголов `hatch_vm_*` — что подтверждает исправление §6.1. `/hatch/cvm-chip-allowlist` и `/hatch/cvm-chip-selection` — первое **конкретное доказательство по протоколу** режима аттестации SEV-SNP "закреплена за конкретными идентификаторами чипов", который §4.2 нашёл только как сигнатуру нативного конструктора.

DTO протокола (поля serial-name `kotlinx.serialization`, не обфусцированные имена полей Java) включают собственное именование **L1/L2/L3** трёхсообщенческого обмена OPAQUE (`base64url_encoded_opaque_l1/l2/l3`, плюс варианты `_sig`), привязанные к устройству **публичные ключи "island" RSA/Ed25519** (происхождение `unknown` — HSM/Keystore vs. внутренний формат Vesta), и локальный журнал (`HatchCvmJournal`: `candidate_chip_ids`, `accepted_chip_ids`, enum `bid_state` `PENDING/ACCEPTED/RETIRED`, `abra_user_id` — та же bearer-идентичность, что у `GraphQlHatchAbraTokenProvider`).

### 6.4 Что фактически защищает PIN

`HatchCvmKeyService.A00` (путь восстановления): (1) выполняет вход OPAQUE (`begin-login`, затем `finish-login`, нативная математика); (2) только при успехе `HatchCvmKeyProviderImpl` получает/восстанавливает фактический локальный ключевой материал из эскроу-полезной нагрузки входа; (3) существует путь очистки при несовпадении ключа устройства или явном сбросе. **Для завершения настоящего обмена OPAQUE между клиентом и сервером требуется правильный PIN** — сервер выдаёт эскроу-полезную нагрузку только при корректном finish-login, с ограничением частоты и серверной проверкой (`attempts_remaining`, `login_timeout_remaining_secs` в каждом ответе). Атакующий с устройством, но без PIN, не может перебрать это локально. Защищаемый секрет — это **ключевой материал идентичности CVM/устройства, необходимый для возобновления конфиденциальной VM-сессии этого пользователя** — не платёжная учётная запись.

Отдельно, `HatchCvmPinReminder` использует **только локальный** ключ AES/GCM (псевдоним `hatch:pin-reminder:v1:...`) исключительно для шифрования состояния уведомления "напомнить установить PIN" — не связано с обменом Vesta и является единственным элементом криптографии в этой подсистеме, не наблюдаемым по протоколу.

### 6.5 Вердикт достижимости для §6

Схема протокола полностью восстановима (выше); транспорт — обычный HTTPS, в принципе наблюдаемый через MITM **без** преодоления аттестации WAFFLE или нативного carrier Noise-шлюза. Но **фактическое участие** (настоящий вход/регистрация) невозможно только из APK: каждое поле запроса/ответа производится или потребляется нативными операциями OPAQUE + постквантовой обёртки/развёртки внутри `libvesta_client_jni.so`, упакованного в superpack без доступной побайтовой экстракции. Клиент мог бы захватить и воспроизвести *форму* открытого JSON, но не может вычислить валидный `opaque_l1`/`l3`, доказательство пары ключей "island" или PQ-обёрнутую полезную нагрузку — **криптографический** блокер, структурно отличный от блокера аттестованного транспорта в §4.

---

## 7. Монетизация — платный уровень подписки Hatch

Кластер подписки эры 2.26.45.10 добавляет настоящий, оплачиваемый уровень для Muse. Поток покупки (цепочка `inferred`, каждый шаг `found` по отдельности):

1. Клиент проверяет флаг функции **`ai_hatch_in_app_subscriptions_enabled`** (лог: "`ai_hatch_in_app_subscriptions_enabled` is off"). Числового идентификатора флага для него не найдено — на него ссылаются только по имени.
2. Константа уровня **`NME_SUBSCRIPTION`**; детали продукта получаются по уровню (`HatchSubscriptionPurchase$launch$2`, лог "Fetching product details for tier"; имя уровня интерполируется, не захардкоженный SKU).
3. Проверка соответствия: **`WamoSubGetComplianceInfo`** (`whatsapp-android-mex`, именованный, без установленных полей ввода в точке вызова — только в рамках сессии/идентичности).
4. Выпуск токена платежей: **`HatchGenFrlPaymentsAccessTokenMutation`** (`GraphQlHatchFrlPaymentsTokenProvider`, пространство имён `whatsapp-android-www`; расшифровка "FRL" не найдена в какой-либо строке в этом проходе — `unknown`).
5. Запуск Google Play Billing (`HatchManageSubscriptionViewModel$openBilling$1`) — стандартный Android `BillingClient` через общий commerce SDK Meta (`com.facebook.payments.dcp.xapp.*`), тег `app="WHATSAPP"`.
6. При покупке — серверная сверка выполнения (`HatchSubscriptionPurchaseReconciler`), вероятно через **`DCPFulfillIAPTransactionsMutation`** (`pay_dcp_fulfill_iap_transactions`, прямой запрос Pando, поля `platform`/`app`/`purchase_tokens`/`subscription_purchase_tokens`/`upl_session_id`, все обязательны в этой точке вызова) — не подтверждено независимо как точный вызов, который использует этот сверщик (`unknown`).

Четыре дополнительных операции, заявленных только в каталоге persisted-query (`IACQueryProductInfo`, `IACQuoteDisplay`, `IACSandboxPlatformMode`, `DCPInternalSandboxCreateSessionMutation`), не имеют **ни одного вызывающего класса, найденного где-либо в smali** — `unknown`, является ли это мёртвым/будущим кодом, флагом/вентилем на стороне сервера, или точкой вызова через конкатенацию строк, которую простой grep упускает.

**Достижимость:**

| операция | пространство имён | требует | достижима ли сторонним клиентом? |
|---|---|---|---|
| `WamoSubGetComplianceInfo` | `whatsapp-android-mex` | только аутентифицированной mex-сессии | **Да, в принципе** — обычный mex-запрос без параметров |
| `HatchGenFrlPaymentsAccessTokenMutation` | `whatsapp-android-www` | аутентифицированной сессии | **Достижимо на уровне транспорта**; ценность выпущенного токена вне предполагаемого потока — `unknown` |
| `DCPFulfillIAPTransactionsMutation` | `whatsapp-schema` (Pando) | подлинного, подписанного Google токена покупки/подписки Play Billing | **Нет** — запрос можно сформировать, но ничего правдивого нельзя в него вложить без настоящей покупки Play Billing через подписанный контекст `com.whatsapp` |
| `IAC*` / `DCPInternalSandboxCreateSessionMutation` | `whatsapp-schema` | unknown (вызывающий класс не найден) | **Unknown** |
| Сам Google Play Billing | н/д | Play Store + подписанный контекст приложения | **Нет** — это даже не вызов сервера WhatsApp |

---

## 8. Вердикт достижимости

| Компонент | Транспорт | Блокер | Достижимо из стороннего (Baileys/velowa) клиента? |
|---|---|---|---|
| Agent spaces, feed/activity, goals, ideas, artifacts, медиа/файлы рабочего пространства, документы идентичности, approvals+история, запланированные задачи VM Hatch, коннекторы (все потоки), безопасное хранилище учётных данных | Аттестованный канал Noise VM (§4) | нативный carrier noise-шлюза `.so` + онбординг WAFFLE | **Нет** |
| Control plane (пробуждение VM, токен Abra, URL пэйринга) | обычный HTTPS к `hatch-api.meta.ai` | провижининг, закрытый WAFFLE (сервер не выдаст рабочую VM без этого) | **Нет** (схема наблюдаема через MITM; не управляема независимо) |
| Восстановление идентичности/PIN CVM (`hatch/cvm`, Vesta OPAQUE) | обычный HTTPS к `hatch-api.meta.ai` | нативная математика OPAQUE + постквантовая в `libvesta_client_jni.so` | **Нет** — криптографический блокер, а не блокер аттестованного транспорта |
| Напоминания 1:1 — `GetMetaAiReminders` / `DeleteMetaAiReminder` | обычный MEX, `whatsapp-android-www` | не найдено | **Условно да** (doc_id `unknown`) |
| Напоминания группы — `GetMetaAiGroupReminders` / `DeleteMetaAiGroupReminder` | обычный MEX, `whatsapp-android-www` | не найдено | **Условно да** (doc_id `unknown`) |
| Информация о соответствии подписки — `WamoSubGetComplianceInfo` | обычный MEX, `whatsapp-android-mex` | не найдено | **Да, в принципе** |
| Выпуск токена платежей — `HatchGenFrlPaymentsAccessTokenMutation` | обычный GraphQL, `whatsapp-android-www` | ничего на уровне транспорта; практическая ценность токена где-либо ещё неизвестна | **Достижимо на уровне транспорта** |
| Выполнение IAP — `DCPFulfillIAPTransactionsMutation` | обычный Pando GraphQL, `whatsapp-schema` | требует подлинного подписанного токена Play Billing | **Нет** (нечего правдивого отправить) |
| `IAC*` / sandbox-операции IAP | `whatsapp-schema` | вызывающий класс не найден | **Unknown** |
| richResponse-квиз (bot.quiz) | локальное хранилище сообщений | нет — не функция VM | полезная нагрузка восстановима; приходит как обычное сообщение бота |

Строки "Условно да"/"Да, в принципе" — это **вся** поверхность этой подсистемы, достижимая клиентом. Всё остальное — что составляет большую часть агента — требует либо нативного carrier Noise-шлюза вместе с валидной аттестацией WAFFLE, либо нативной криптографии OPAQUE/постквантовой, которая не может быть статически извлечена из этого APK.

---

## 9. Baileys / velowa

**Вердикт: эта подсистема невозможна в JS для стороннего клиента, точка — не отсутствующая функция, а структурная.** velowa (активный клиентский проект за этой документацией) не может реализовать VM agent-browser или workspace Hatch/Muse по тем же причинам, что назвало оригинальное исследование:

| Блокер | Почему это не обойти в JS/WASM |
|---|---|
| `libwa-noise-gateway-carrier-jni.so` | Весь handshake Noise и фрейминг WebSocket для канала VM — это нативный код внутри непрозрачного блоба SUPERPACK. Нет протокольного документа, против которого можно реализовывать — форма протокола (query-параметры, путь `/v1/noise`, глаголы HTTP-через-Noise, субпротокол noVNC RFB) восстановлена выше, но фактическая криптография Noise (вывод ключей, аутентификация фреймов) существует только скомпилированной внутри этого `.so`. Реимплементировать это означает реверс-инжинирить урезанную нативную библиотеку, а не писать клиент по спецификации. |
| Аттестация официального клиента WAFFLE | Блокирует онбординг VM до того, как вообще открывается какой-либо Noise-канал. Сторонний клиент не может сформировать валидный токен WAFFLE, поэтому он не может провизионировать VM вообще — это блокирует даже попытку Noise handshake. |
| `libvesta_client_jni.so` (OPAQUE + PQ) | Отдельно от вышеуказанного: даже там, где трафик восстановления идентичности (§6) — обычный HTTPS и наблюдаем, клиентская математика OPAQUE (`opaque_l1`/`l3`, доказательства пары ключей "island", постквантовая обёртка) — нативная. Захват формы JSON не даёт ничего, с чем можно вычислить валидный запрос. |
| Аттестация AMD SEV-SNP | Ортогонально клиенту — это *сервер*, чья VM доказывает официальному приложению свою подлинность — но подтверждает, что весь дизайн предполагает нативного, аттестованного партнёра на обеих сторонах. |
| Tigon | Внутренний кросс-приложенческий нативный HTTP-стек Meta несёт каждый запрос в §4 и §6; его объекты запроса не являются публичным, версионированным форматом протокола. |

Что velowa (или любой протокольный клиент) *мог бы* достичь без касания чего-либо из вышеперечисленного: четыре именованные MEX-операции напоминаний (§5.8) и GraphQL-операции соответствия подписки/выпуска токена платежей (§7) — все они идут через тот же обычный транспорт WA MEX/GraphQL, который velowa уже использует для всего остального в этом репозитории. Пример кода здесь не приводится, потому что ни один исходный материал этого отчёта не захватил конкретный запрос/ответ для этих операций сверх имён операций и форм параметров, уже перечисленных в §5.8/§7/§8; придумывание байтов полезной нагрузки искажало бы уровень доказательности.

---

## 10. Случаи ошибок / подводные камни

| Симптом | Причина | Примечание |
|---|---|---|
| "Computer is turned off on this VM" | VM не провизионирована/не пробуждена для поверхности полного десктопа | строка `HatchComputerActivity` |
| "Approval required" никогда не разрешается в действие | пользователь не подтвердил approval gate | по дизайну — с участием человека |
| "This idea isn't available anymore." / "This idea is already running." | карточка идеи заменена или уже выполняется | `HatchIdeaDetailBottomSheet` |
| "No goals yet" / "No ideas right now. Check back later." / "No approvals yet" | пустые секции рабочего пространства, не ошибка | |
| "Couldn't load your agent's files" | вызов `/fs/library` или `/fs/raw/` не удался через туннель Noise | |
| "thread superseded by a newer search, refusing" в стиле `PrivateSearchSessionManager` (соседняя система TEE, не Hatch) | перечислено в §11 только чтобы избежать перекрёстного загрязнения строк ошибок между двумя системами | см. Ключевые различия |
| 400 "already exists; set replace_existing=true" | регистрация пользовательского коннектора без флага `replace_existing` | `HatchConnectorsListRequester` |
| "wrong pin" / "finish-login crypto failed" | вход OPAQUE не удался на стороне сервера | ограничено по частоте через `attempts_remaining`/`login_timeout_remaining_secs` |
| "hsm key missing" / "hsm key invalid" / "hsm key check failed" | валидация привязанного к устройству HSM-ключа не удалась внутри пути восстановления Vesta | §6.4 |
| `noise/gave-up limit=deadline` | превышен бюджет открытия канала Noise VM (60 с) | `NoiseVmConnection` |
| `NoiseHandshakeOutcome.VERIFICATION_FAILED` | проверка аттестации не удалась на handshake Noise-шлюза | §4.2 |
| "`ai_hatch_in_app_subscriptions_enabled` is off" | флаг функции подписки отключён на стороне сервера | §7 |
| "HatchSubscriptionPurchase/purchase no compliance data" | результат `WamoSubGetComplianceInfo` отсутствует перед попыткой покупки | §7 |

---

## 11. Ключевые различия — что НЕ путать

| Не путать | Факт |
|---|---|
| Агент Hatch/Muse (этот отчёт) vs. **чат Meta AI** (`WA_META_AI.md`) | Meta AI — это бот-контакт, достижимый через `botInvokeMessage`/bot-JID на обычном протоколе сообщения; Hatch/Muse — отдельный агент, управляющий удалённой аттестованной VM. Они используют часть общей инфраструктуры (канал JSON-метаданных Hatch через `ProtocolMessage.aiMetadataOperation`, флаги возможностей, анонсируемые bot-JID Hatch `1807055946647697@bot`), но архитектурно это разные подсистемы |
| VM Hatch/Muse vs. **Private Processing / кластер TEE** (AI в контексте чата, Private Search) | Кластер TEE (`ClusterFetchPrekeyBundleConnection`, `IplsdHandshakeExecutor`, `PsiSearchToolHandler`, `TeePrefixCacheAnchor`) — это Meta AI, отвечающий на вопросы **о собственных локальных чатах пользователя** через аттестованный enclave + поиск PSI — не имеет ничего общего с VM agent-browser Hatch. *Отправка запроса* Private Search идёт через обычное сообщение чата с ботом (достижимо), тогда как сами вычисления PSI/enclave остаются нативными — иная форма достижимости, чем что-либо в этом отчёте |
| `hatch.cvm` (восстановление идентичности/чипа, §6) vs. `hatch.connectors` (виртуальная карта / Stripe, §5.9) | Две раздельные функции, в продуктовой формулировке делящие только разговорные слова "карта"/"хранилище"; между ними нет зависимости в коде (проверено) |
| Локальный ключ AES/GCM `HatchCvmPinReminder` vs. обмен Vesta OPAQUE | Шифрование состояния уведомления только локально vs. настоящее восстановление идентичности с полным обменом с сервером — только последнее является защитой PIN "на стороне сервера" |
| Поля "bid_state"/"chip" (§6) vs. **лизинг управления** браузером (§4.5) | Учёт выбора аппаратного чипа SEV-SNP vs. кто управляет браузером агента (агент/человек) — три разных использования пересекающейся терминологии ("bid"/"lease"/"control") в этой кодовой базе |
| Обычный control plane HTTPS Vesta (§3, §6) vs. аттестованный канал Noise-шлюза VM (§4) | Разные транспорты, разные блокеры (нативная математика OPAQUE vs. нативный Noise + аттестация WAFFLE) — объединение их преувеличивает, где фактически применяется блокер аттестованного транспорта |
| Agent spaces (§5.1) vs. артефакты, созданные агентом (§5.5) | Space — это живое, сохраняющее состояние хостящееся приложение; артефакт — статичный результат (*закреплённый результат* space становится артефактом, но сам space продолжает работать) |
| `com.whatsapp.bot.quiz.AiQuizViewerActivity` vs. функция Hatch | Читает квиз richResponse, уже доставленный как обычное сообщение бота, из локального хранилища — без VM, без сетевого вызова, вообще не часть этой подсистемы |

---

## 12. Сквозной поток — одна сессия задачи agent-browser

```
[User, in chat]
    │  "book me a table for two tonight"
    ▼
[Onboarding, first use only]
    │  HatchWaffleOnboarding: official-client WAFFLE attestation
    │  HatchPairingAuthBrowsingActivity: pairing URL (account ↔ agent link)
    ▼
[Control plane]  plain HTTPS to hatch-api.meta.ai
    │  GraphQlHatchAbraTokenProvider → Abra bearer
    │  HatchVmApiClient: POST /hatch/vm/wake {vm_id, retry_count}
    │  → HatchVmEndpoint{host, auth_token, notary_token, ...}
    ▼
[Noise-gateway handshake]  native libwa-noise-gateway-carrier-jni.so over Tigon
    │  GET …<vmhost>…?auth_token&notary_token&app_id&app_version=2.26.41.6
    │  path /v1/noise, 20s handshake timeout, attestation verifier (noOp/SNP/SNP-pinned)
    ▼
[Attested Noise channel open]  (60s budget, ref-counted "holds")
    │
    ├──▶ hatch_vm_request /api/computer/subscribe  — live task state (SSE-style)
    │
    ├──▶ hatch_vm_call   — agent navigates the booking site inside the CVM
    │        │
    │        ▼
    │    [Phone shows it live]  noVNC (RFB) over JWT-bearer WebSocket, viewOnly
    │        unless user takes a BrowserControlLeaseJson "control lease"
    │
    ├──▶ Login needed → /v1/credentials/... fetched INSIDE the VM
    │        (SecureCredentialVault; raw secret never reaches the agent's
    │         reasoning context, per design)
    │
    ├──▶ Payment needed → HatchConnectorCardActionActivity mints a virtual card;
    │        real card number never exposed to the agent
    │
    ├──▶ Risky/irreversible step → HatchBrowserPreviewActivity "Approval required"
    │        user confirms → recorded in HatchApprovalHistoryApi
    │
    ▼
[Outcome]
    │  artifact/feed entry (hatch.artifacts / hatch.feed)
    │  optionally scheduled to recur (HatchScheduledTasksActivity, native VM path)
    ▼
[Noise channel teardown]  last "hold" released → noise/closed reason=unlink
```

Отдельно (не часть той же сессии, обычный MEX/GraphQL, без участия аттестованного транспорта):

```
[Client]  GetMetaAiReminders / GetMetaAiGroupReminders
    │  whatsapp-android-www, name-based persisted query
    ▼
[WA server]  reminder list (status SCHEDULED/CLAIMED/FULFILLED)

[Client]  DeleteMetaAiReminder / DeleteMetaAiGroupReminder
    ▼
[WA server]  reminder removed
```
