<!-- src-sha1: 5428e0461d6ea8f961256e4ead0fe3df30ea4164 -->
# WhatsApp Обход цензуры — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** запасные способы подключения Android при блокировке chatd: пользовательский WhatsApp Proxy (UI настроек, хранение, ссылка для обмена, использование в chatd и media), серверно управляемый proxy service (туннель Psiphon, модуль Voltron, ограничения по региону и VPN, SOCKS-туннель с заголовком PROXY v2), список запасных IP (`<ib><fbip>`, файл `fbips`), push разблокировки (`fbips`, `unblocking_props`, `psl`), цепочка DNS fallback, провайдеры relay для регистрации и стратегии повторных попыток, роли Tigon и DGW, отслеживание состояния соединения и диагностика, взаимодействие повторных попыток, feature flags, отсутствующие механизмы, сравнение с Baileys

---

## 1. Что присутствует в этой сборке

Все утверждения получены статическим анализом декомпилированного APK; в сети ничего не перехватывалось. Уровни: **found** = прочитано в коде или ресурсах, **inferred** = выведено, **unknown** = не разрешено. Обфусцированные имена привязаны к сборке и заново определены в 2.26.41.6. Транспорт chatd, handshake, лестница хостов и backoff описаны в [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) и здесь не повторяются.

| Механизм | Состояние | Точки входа | Уровень |
|-----------|-------|--------------|------|
| WhatsApp Proxy (настраиваемый пользователем relay для чата и media) | присутствует, есть UI, за feature flag | `SettingsUserProxyActivity`, `SettingsSetupUserProxyActivity`, `C12660bX`, `C12690ba`, шаг 12 последовательности chatd | found |
| Proxy service (туннель Psiphon, модуль Voltron `proxyservice`) | присутствует, управляется сервером, без пользовательского UI | `C12760bh` (оркестратор), `C42448IfJ` / `S6G`, `ca.psiphon.PsiphonTunnel`, `ProxyServiceBroadcaster` | found; нативной библиотеки в APK нет |
| Список запасных IP | присутствует | `<ib><fbip>` в `C40581l4`, `C36821d6`, файл `fbips` | found |
| Зашитая в код таблица хост-IP, лестница хостов | присутствует | `AbstractC47101wK` (18 имён хостов), `C37151de` | found |
| Цепочка DNS fallback (платформа / MNS, UDP к 8.8.8.8 и 8.8.4.4, зашито в код) | присутствует | `C36881dC`, `QG1` | found |
| Push разблокировки (`nt` = `unblocking`) | присутствует | `CLl` parser, `C28139CLl`, `C28912ChD`, `C27946CBo` | found |
| Relay для регистрации (провайдеры cloud-функций) и стратегии повторных попыток | присутствует, только для регистрации | `res/raw/domain_fronting_providers.tsv`, `C45421Jrl`, `RetryingHttpClient` | found |
| Tigon / DGW как fallback для chatd | отсутствует | конфиг DGW fallback существует, но собирается выключенным | found |

Отсутствует в этой сборке (найдено как отсутствие в декомпилированной Java, манифесте и ресурсах; нативный код не исследовался):

| Отсутствует | Свидетельство |
|--------|----------|
| chatd поверх WebSocket, HTTP long-poll или MQTT | нет литералов `wss://` или `/ws/chat` в Java; `mqtt` только в аналитике и метках потоков DGW (см. раздел 13 отчёта Noise) |
| Android `VpnService` | нет сервиса и `BIND_VPN_SERVICE` в манифесте; Psiphon работает в режиме local-proxy |
| Настраиваемый пользователем SOCKS- или HTTP-CONNECT-прокси для chatd | шаг 12 строит прямой сокет к `host:chatPort`, без proxy handshake |
| Системный прокси (`http.proxyHost`, `https.proxyHost`) для chatd | не читается последовательностью или кодом сокета; читается только Tigon и как guard (раздел 4.6) |
| Domain fronting или relay для chatd | список провайдеров используется только клиентом регистрации (раздел 7) |
| Tor, Snowflake, другие pluggable transports | код или ресурсы не найдены |

Моменты, определяющие остальную часть отчёта:

- Существуют два независимых механизма прокси, которые никогда не работают одновременно: пользовательский прокси (шаг 12, терминальный) и proxy service Psiphon (SOCKS-туннель, заменяющий прямые подключения для подмножества шагов). При заданном пользовательском прокси конфиг сервиса игнорируется (`ConnectionSequence/socketConfigForUserProxy/skipping socks proxy in favor of user proxy`).
- При валидном пользовательском прокси у последовательности ровно одна цель. Шаг 12 переходит к 16 (исчерпано); возврата к прямым хостам нет (found, `C37031dS.A0G`).
- `libgojni.so` доставляется внутри загружаемого модуля. В APK лежит только манифест модуля; набор вызовов туннеля, выбор протокола и анти-DPI поведение неизвестны.

---

## 2. Место в последовательности подключения chatd

Номера шагов соответствуют разделу 2.2 отчёта Noise. Источник: `C37031dS.A0G`, `C37151de`, `C37061dV`.

| Условие | Эффект |
|-----------|--------|
| Задан debug-адрес | только шаг 1 |
| Валидный пользовательский прокси (включён, хост валиден, flag **2784**) | шаг 0 переходит к 12, который терминальный; конфиг Psiphon игнорируется |
| Нет пользовательского прокси, есть конфиг Psiphon (`C37061dV.A00 != null`) | шаги 5, 8, 13 сохраняются; 6, 7, 9, 10, 11, 14, 15 пропускаются (`ConnectionThread/Skipping sequence N due to active proxy`); 2, 3, 4 пропускаются, если не включён flag **23630** |
| Нет пользовательского прокси, нет конфига Psiphon | неизменённая лестница: 2, 3, 4, 5, 8, 9, [15], 13, 14, 6, 10, 7, 11 |

Таблица пропусков — это packed switch в байткоде `C37031dS.A0G` (шаги со 2 по 15 отображаются на keep / skip / зависит от flag). Шаг 8 строит конфиг из IP-литерала без конфига прокси, поэтому в запуске с активным прокси он сохраняется, но, предположительно, подключается напрямую (inferred). Шаги 5 и 13 разрешаются через `C37151de.A03`: при наличии конфига Psiphon и отсутствии пользовательского прокси возвращаемый конфиг сокета несёт `ProxyServiceConfig` (`C46661vS`) и неразрешённое имя хоста, поэтому DNS выполняется на выходе туннеля (`DNSResolutionMethod` 7 `SOCKS_PROXY`, внутренний код 8 в `C37181dh`).

Порядок шага 0 при отсутствии debug-адреса (found; декомпилированная Java-ветка для шага 1 выглядит инвертированной, байткод подтверждает): пользовательский прокси, затем записи override от сервера (2), затем сконфигурированная строка хоста (3), затем 5.

---

## 3. WhatsApp Proxy (настраиваемый пользователем)

### 3.1 Вход в настройки и экраны (found)

| Экран | Класс | Содержимое |
|--------|-------|---------|
| Settings > Storage and data > Proxy | `SettingsUserProxyActivity` (manifest `com.whatsapp.settings.ui.proxy.*`, не exported) | переключатель `Use proxy`, строка хоста, строки статуса chat и media, пункт меню «поделиться», информационный текст (`Only use a proxy if you're unable to connect to WhatsApp. Your IP address may be visible to the proxy provider…`, ссылка `whatsapp-proxy`) |
| Set up proxy | `SettingsSetupUserProxyActivity` | ввод хоста, `Ports (Optional)` с `Chat port` (по умолчанию отображается как `Default` для 443), `Media port` (`Default` для 587), `Use TLS`, кнопка сохранения |
| Запись в поиске настроек | `C23869ARc` подкласс `C215199Jq` | ключ `proxy` |
| Удаление | долгое нажатие на строку хоста (`ViewOnLongClickListenerC46012K9h`, `Delete Proxy?`), действие в `KZA` | очищает хост, сбрасывает media port 587 и TLS true, статусы 0, `proxy_enabled` false |

Валидация: `K09.A01` (IP-литерал), `K09.A02` (хост с необязательным `:port`, regex строится из `JRQ.A02`); ошибки `Enter a valid host`, `Enter a valid port`. Разбор IPv6 есть в `K09.A00`.

### 3.2 Хранение (found, `C12660bX`, `C12690ba`)

Файл SharedPreferences `user_proxy_setting_pref`.

| Ключ | Тип | По умолчанию | Использование |
|-----|------|---------|-----|
| `proxy_enabled` | bool | false | состояние переключателя; действует только при включённом flag **2784** (`C12690ba.A03`) |
| `proxy_ip_address` | string | нет | `host:chatPort` (`ProxySetting.A04`); порт разбирается при чтении, по умолчанию 443 |
| `proxy_media_port` | int | 587 | порт media relay |
| `proxy_use_tls` | bool | true | TLS-обёртка для сокета чата |
| `proxy_connection_status` | int | 0 | статус чата, показываемый в UI (раздел 3.5) |
| `proxy_media_connection_status` | int | 0 | статус media, показываемый в UI |

`ProxySetting` (`C45598Jv6`) = `domain`, `ip`, `chatPort`, `mediaPort`, `useChatTls`; хост, являющийся IP-литералом, попадает в `ip`, иначе в `domain`. `C12660bX.A03()` возвращает его только если прокси включён, flag **2784** включён и хост или IP валиден; именно этот объект получает последовательность подключения.

### 3.3 Ссылка для обмена и импорта (found)

Share: пункт меню строит `https://wa.me/proxy?host=<host>&chatPort=<n>&mediaPort=<n>&chatTLS=<true|false>` с темой `WhatsApp Proxy` и текстом `Connect to WhatsApp using proxy. <url>`.

Import: `DeepLinkActivity` (тип `DEEP_LINK_PROXY`, префикс лога `PROXY:`) требует flag **2784**, имеет причину отклонения `proxy_has_segments` (условие выведено из имени), затем запускает `SettingsSetupUserProxyActivity` с extras `intent_host_name`, `intent_chat_port`, `intent_media_port`, `intent_use_tls`, `source=deeplink`.

| Query | Разбор | По умолчанию |
|-------|-------|---------|
| `host` | string | нет |
| `chatPort` | int | 443 |
| `mediaPort` | int | 587 |
| `chatTLS` | отсутствует, `true` или `1` даёт true; любое другое значение false | true |

Импорт лишь предзаполняет экран настройки; для сохранения по-прежнему нужен пользователь (found). Обработчик `DeepLinkActivity` прочитан из байткода (в Java не декомпилируется).

### 3.4 Использование в chatd (found)

Шаг 12 (`C37151de.A02` case 12): host = `domain` или `ip`, port = `chatPort`, бит TLS = `useChatTls`. Хост проходит через обычную цепочку резолверов (раздел 6). Затем поверх этого сокета выполняется Noise handshake (внутри TLS при `useChatTls`). Сохранение прокси или переключение вызывает `C11380Yq.A0C(...)` (принудительное переподключение) и отправляет `wam_user_proxy_set`.

Что хост прокси делает с потоком, на стороне клиента не видно. Пересылка relay WhatsApp Proxy сырых байтов chatd выведена (inferred) из отсутствия какого-либо обмена SOCKS или CONNECT.

### 3.5 Другие потребители (found)

| Потребитель | Поведение |
|----------|-----------|
| Media upload / download | flag **4073** делает media authority равным `proxy-host:mediaPort`; health check в [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| Маршруты загрузки WAM | нативный callback `jnidispatchO(0)` возвращает `https://<proxy-host>:<mediaPort>/deidentified_telemetry` при включённом flag **4074**, плюс хосты `media_conn` при включённом flag **4020** (см. [WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)) |
| UI статуса | `C42103IXl.A00`: 1 `Connecting…`, 2 `Connected`, 3 `Couldn't connect to proxy`, 4 `Disconnected`, 5 `No network`, иначе `Not Set`; статус чата поступает от наблюдателя соединения `C28890Cgr` |
| Маршруты Psiphon HTTP и Tigon | отключены, пока существует пользовательский прокси (`C17420jn.A01`, `C12790bk`: `User proxy is set, skipping`) |
| Телеметрия | `WamUserProxySet {connectionSuccess, proxySet}` (`C43286IuN`) отправляется, когда статус становится 2 (true) или 3 / 4 (false), и при изменении прокси |

---

## 4. Proxy service (Psiphon)

### 4.1 Модуль и библиотека (found)

| Элемент | Значение |
|------|-------|
| Доставка | модуль Voltron `proxyservice` плюс сплиты по ABI `proxyservice.config.{arm64_v8a,armeabi_v7a,x86,x86_64}` в `assets/app_modules.json`; манифест модуля перечисляет `assets/proxyservice/libs.txt`, `assets/proxyservice/voltron_meta_embedded_server_entries` и `lib/<abi>/libgojni.so` для каждого сплита |
| Java-часть | `ca.psiphon.PsiphonTunnel` (upstream-библиотека, `loadLibrary("gojni")`, `Psi.start`, `importPushPayload`), хост-сервис `S6G` / `C42448IfJ`, оркестратор `C12760bh`, загрузчик модуля `C46743KbZ` |
| Режим | локальный HTTP- и SOCKS-прокси на `localhost`; без `VpnService` |
| Загрузка библиотеки | библиотеки split APK добавляются в источники SoLoader (`proxy_service/Added module SoSource`); строка лога называет `libproxyservice.so`, хотя в манифесте модуля есть только `libgojni.so` |

`libgojni.so` в APK отсутствует (доставляется вместе с модулем). Её внутреннее устройство (набор протоколов, dialing, использование `AdditionalParameters`) неизвестно.

### 4.2 Ресурс конфигурации `res/raw/proxyservice_config.json` (found)

Не менялся с 2.26.34.4. Читается `C42448IfJ.getPsiphonConfig`; плейсхолдер формата `ClientVersion` заполняется versionCode приложения (`264100600`).

| Поле | Значение / использование |
|-------|-------------|
| `SponsorId`, `PropagationChannelId`, `ClientPlatform` | непрозрачные 16-hex идентификаторы; платформа `meta` |
| `ServerEntrySignaturePublicKey`, `PushPayloadSignaturePublicKey`, `RemoteServerListSignaturePublicKey` | base64-ключи на 32 байта, 32 байта и 548 байт (размер RSA); роль проверки выведена из имён |
| `AdditionalParameters` | 5300 символов base64 (3975 байт), непрозрачно, не декодировано |
| `Emit*` (адрес клиента, диагностические уведомления, сетевые параметры), `DisableServerEntriesReporter` | все true; питают `onClientAddress`, `onDiagnosticMessage` |
| `ConnectionWorkerPoolSize`, `EstablishTunnelTimeoutSeconds` | 30, 0 |
| `TransformHostNameProbability`, `TLSFragmentClientHelloProbability` | 0.9, 0.5 (анти-DPI параметры нативного движка; эффект выведен из имён) |
| `EnableLightProxy`, `LightProxyLimitDestinationAddresses` | true; `g.whatsapp.net` и `g-fallback.whatsapp.net` на портах 80, 443, 5222 |

Изменения во время работы: JSON-объект из flag **23879** (источник flag до входа в аккаунт) или **23846** (обычный источник) сливается ключ за ключом поверх файла. Режим PSL import (`C42448IfJ.A03`) принудительно устанавливает `DisableTunnels=true`, `EnableLightProxy=false`. Встроенные записи серверов читаются из `assets/proxyservice/voltron_meta_embedded_server_entries` (или из zip модуля) при включённом flag **23730** / **23731**; формат: big-endian int32 count, затем count раз (int32 length, bytes), каждая запись в hex, по одной на строку (`C45480Jst.A01`).

Два источника flag выбираются `C17280jY.A00`: отсутствие залогиненного аккаунта или ни разу не обновлённые AB props выбирают набор до входа. Следовательно, сервис рассчитан на работу и до регистрации (inferred из предиката).

### 4.3 Конечный автомат (found, `AbstractC17380jj`, `C12760bh.A0B`)

| Код | Состояние | Устанавливается, когда |
|------|-------|----------|
| 0 / 1 / 2 | `uninitialized` / `not_in_region_allowlist` / `initializing` | начальное / регион отклонён (причина содержит регион) / запуск принят |
| 3 / 4 | `disabled` / `downloading_module` | gate, например `vpn_in_use` / идёт загрузка Voltron |
| 5 / 6 / 7 | `connecting` / `connected` / `disconnected` | `onConnecting` / `BmZ` (порты готовы) / `BpU` |
| 8 / 9 | `download_failed` / `library_load_failed` | сбой установки модуля / `UnsatisfiedLinkError` |
| 10 | `shutdown` | `A04(reason)`, например `country_check`, `has_external_connectivity` |

Пока состояние 2, 4 или 5, HTTP-стек ждёт прокси: `C17420jn.A05(true)` взводит latch, таймаут которого задаёт flag **29362** (мс, по умолчанию 0, только при входе в аккаунт).

### 4.4 Триггеры запуска и остановки (found)

| Триггер | Путь |
|---------|------|
| Холодный старт message handler | default case в `C1W6` вызывает `C12760bh.A03(…, null)` |
| Возобновление приложения | `C18980me`, `C28912ChD` вызывают `A0A()` (повторно уведомить туннель или перезапустить, если остановлен) |
| Push разблокировки с `psl` | `C28912ChD.BIb`: `A03(…, C46772Kc2(psl))`; без `psl` только `A0A()` при `C17280jY.A02()` (flags **28186** / **28189**) |

Gates запуска в `A03`:

1. Регион устройства = страна SIM, иначе страна сети, иначе страна локали (`AbstractC16510i9`); должен входить в список через запятую в нижнем регистре из flag **18724** (до входа) / **18725** (`C17280jY.A03`). Иначе состояние 1.
2. Проверка VPN (`C17280jY.A01`, flags **24068** / **24067** обходят её): активный VPN даёт `vpn_in_use`, состояние 3.
3. Flag **25452** определяет порядок: включён, VPN gate и prober запускаются после загрузки модуля; выключен, до неё.
4. Prober (flag **18875**, `Q53`): HTTP GET по URL из flag **18871** (таймаут **18874**, попытки **18873**, задержка **18872**) через обычный стек. Любой HTTP-ответ считается успехом (`KUI.CF3`): `Probe succeeded. Removing proxy from http and tigon`, устанавливается `A0N` (внешняя связность), прокси убирается из HTTP и Tigon, выполняется проверка shutdown.
5. Таймаут маркера старта: flag **25850** секунд (аннотация `init_timed_out`).

Условия остановки:

| Условие | Результат |
|-----------|--------|
| Сообщённый Psiphon регион клиента не разрешён (flag **19067** включён) | `country_check`, shutdown |
| Prober успешен (`A0N`) и сообщена хорошая прямая сессия chatd (`A0O`), flag **19613** включён | `has_external_connectivity`, shutdown |
| Хорошая прямая сессия chatd (`HandlerThreadC12340b0.A0e`: сервис активен, сессия длиннее flag **19372** (по умолчанию 5, единица не определена), маршрут не `SOCKS_PROXY`) | `C12760bh.A09()` плюс `C37061dV.A00()`: proxy service игнорируется до конца жизни процесса (`good_direct_chatd_session`) |
| Flag **19144** отрицателен при запуске | игнорируется до конца жизни процесса (`abprop_config`) |

### 4.5 Интеграция с chatd (found)

`C37061dV` (`ConnectionProxyConfig`) превращает состояние broadcaster в `ProxyServiceConfig`, который использует последовательность.

| Поле | Источник |
|-------|--------|
| `address` | `localhost`, когда heavy tunnel или light proxy поднят, иначе пусто |
| `port` | порт SOCKS (`ProxyServiceBroadcaster.A01(true)`: heavy, либо light, когда разрешён) |
| `proxyServiceClientIP` | `onClientAddress` |
| `httpProxyHost`, `httpProxyPort` | `localhost` и порт HTTP, если не ноль |
| `isLightProxy` | `isLightProxy()` (light proxy поднят, heavy tunnel не подключён) |

Правила:

- Конфиг отбрасывается, если address или port пусты (`updateProxyServiceConfig`) либо сообщённый Psiphon регион не разрешён (`dropping due to unsupported client region`).
- `C37061dV.A02` (вызывается при каждом старте соединения) возвращает конфиг только если регион устройства разрешён, VPN не активен, сервис не остановлен и не установлен игнор на время жизни процесса. При включённом flag **24645** кэшированный конфиг используется без этих проверок.
- Поток соединения может блокироваться на flag **19144** мс (`awaitProxyServiceConfig`) в ожидании конфига перед шагом 5, если конфига ещё нет.
- Изменение конфига устанавливает флаг сброса и, при включённом flag **36306**, переподключает с причиной `proxy_service_update`.

Сокет (`C37031dS.A01` else-ветка, класс `C48201yM` = `ConnectionSocketTunnel`):

```java
Socket s = new Socket(new Proxy(Proxy.Type.SOCKS, new InetSocketAddress(cfg.address, cfg.port)));
s.connect(InetSocketAddress.createUnresolved(host, port), 30000);   // g.whatsapp.net / g-fallback.whatsapp.net
c37861f7.A00(out, cfg.proxyServiceClientIP, port);                    // PROXY v2 header, skipped when flag 26334 is on
```

Заголовок PROXY v2 (`C37861f7`, лог `ProxyHeaderWriter`): 12-байтовая сигнатура `0D 0A 0D 0A 00 0D 0A 51 55 49 54 0A`, `21`, семейство `11` (IPv4) или `21` (IPv6), 16-битная длина, адрес источника (IP клиента, нулевой адрес, если не разбирается), нулевой адрес назначения, порт источника 0, порт назначения = целевой порт, затем один TLV `E8 00 01 50`. Значение TLV неизвестно. Принимает ли edge заголовок или требует его, выведено (inferred) только из его наличия.

Записи тайминга соединения по каждой попытке используют стадии `DNS`, `SOCKET`, `TLS` и стеки `PLATFORM`, `MNS`, `SOCKS_PROXY` (`C37811f2`, `EnumC37801f1`, `EnumC37821f3`).

### 4.6 Другие потребители локального прокси (found)

| Потребитель | Класс | Поведение |
|----------|-------|-----------|
| HTTP-стек WA | `C17420jn` (`WaHttpUrlConnectionWithProxyService`) | `Proxy(HTTP, localhost:httpPort)`; для хостов, оканчивающихся на `.whatsapp.net`, `.whatsapp.com`, `.fbcdn.net`, `.facebook.com`, `.instagram.com`, `.cdninstagram.com`, `.fbsbx.com`, добавляет `X-Forwarded-For: <client IP>` и `using-wa-proxy-service: 1` |
| Клиенты Tigon (MNS) | `C12790bk` (`WATigonProxyObserver`) | `setInAppProxyHostAndPort`; пропускается, когда включены flags **26734** / **26735** (Tigon) или **19905** / **19906** (WA proxy), существует пользовательский прокси, задан `http.proxyHost` / `https.proxyHost` или probe уже успешен |
| VoIP | `CQO`, `JNIUtils.socksProxyPort` | `Voip.updateProxy(socksPort)`, когда разрешает flag **34525** (второй gate **36980** в `Buh()`) |
| WebView | `C39826HXw` | правило `PROXY_OVERRIDE` для доменов из flag **25539** |
| Лог сетевой информации | `C12500bH` | `network_info_socks_proxy_active[...]`, `socks_proxy_connected` / `socks_proxy_disconnected` |

Tigon также сам читает свойства системного прокси (`TigonHttpClientBase.setSystemProxyHostAndPort`) с переключателем direct-fallback; это не зависит от сервиса.

### 4.7 Диагностика (found)

`C42448IfJ.onDiagnosticMessage` разбирает `ConnectedServer:{json}` в `candidate_number`, `protocol`, `client_replay_type` (`bootstrap`, `replay`, `non-replay`), `server_entry_source`. Маркеры 79499422 (старт), 79496324 (подключение), 79501264 (prober, аннотации `has_vpn`, `has_system_http_proxy`).

---

## 5. Запасные endpoints и push разблокировки

### 5.1 `<ib><fbip>` (found, `C40581l4`, `C36821d6.A02`)

`<ib><fbip>text</fbip></ib>`: text разбивается по `,`. Единственная запись `CLEAR` удаляет файл. Каждая запись состоит из шести полей, разделённых `|`:

```
ip|port|ts|ttl|secure|override       exp = (ts + ttl) * 1000
```

| Поле | Использование |
|-------|-----|
| `ip`, `port` | endpoint; код резолвера 4 (`FALLBACK`) |
| `ts`, `ttl` | срок действия в мс; истёкшие записи удаляются при загрузке |
| `secure` | бит TLS-обёртки для endpoint |
| `override` | записи true идут на шаг 2 (пробуются до `g.whatsapp.net`), записи false на шаг 8 (после `:80`) |

Хранение: файл `fbips` в каталоге файлов приложения, JSON `{"fbips":[{"ip","port","exp","secure","override","resolver"}]}` (`C36821d6.A00`). Ошибки загрузки сообщаются как `fallback-manager/load-error`, `save-error`.

### 5.2 Зашитая в код таблица (found)

`AbstractC47101wK`: 18 имён хостов (`e1` до `e16`, `g`, `v` под `.whatsapp.net`, обычная форма и форма с точкой на конце), у каждого несколько адресов IPv4. Используется шагами 6 / 10 и зашитым резолвером. Запись `v.whatsapp.net` не используется ни одним резолвером в этой сборке (заглушка резолвера возвращает null).

### 5.3 Push разблокировки (found)

Разбор push (`CLl`, `PushPayloadParser/fromJSON`): значения `nt` `pre_reg`, `post_reg`, `voip_call_offer_1on1`, `voip_call_offer_group`, `call_terminate`, `message`, `group_message`, `wfac_ban`, `unblocking`. Логируемые транспорты: `ADM`, `GCM`, `FBNS`. Payload расшифровывается (`PushEncryptionHelper`, поля `payload`, `IV`, `tag`, ключ из `push:push_pkey_data`; шифр выведен как AES-GCM из имён полей).

`nt` = `unblocking` несёт (`UnblockingPushPayload`, `BQY`):

| Ключ JSON | Поле | Обработка |
|----------|-------|----------|
| `fbips` | `fbips` | разбивается по `,`, передаётся в `C36821d6.A02` (тот же формат, что в 5.1) |
| `unblocking_props` | `unblockingProps` | `version\|a\|b`; version выше 0 игнорируется; две карты `id=value;id=value` разбираются `C27946CBo.A00`; `processPreChatdProps` применяет пары `config_code` / `config_value`, `processPostChatdProps` вторую карту (сопоставление карт фазам частично выведено) |
| `psl` | `proxyServerList` | base64, импортируется в Psiphon через `importPushPayload` (`C46772Kc2`) |

Импорт `psl`: туннель активен, импорт напрямую; туннель неактивен, временный объект туннеля стартует в режиме PSL import (`DisableTunnels`), импортирует, останавливается (`Cold-importing push payload`). Пропускается, когда состояние `not_in_region_allowlist`. Расшифровка PSL как «push server list» выведена (inferred) из ключа и поля `PushPayloadSignaturePublicKey`.

---

## 6. Цепочка DNS fallback (found)

`C36881dC.A03` сначала обращается к кэшу (питается из `fbips`, записи с истечением; управляется flag), затем последовательно проходит четыре резолвера:

| # | Резолвер | Код резолвера | Примечания |
|---|----------|---------------|-------|
| 0 | заглушка для `v.whatsapp.net` | нет | возвращает null |
| 1 | платформенный / MNS DNS (`DnsCache/resolveViaMnsDns`) | 5 / 6 / 7 | одна повторная попытка (`primary dns resolver failed, retrying...`) |
| 2 | вторичный: собранный вручную UDP DNS к 8.8.8.8 и 8.8.4.4 порт 53 (`QG1`) | 1 `GOOGLE` | простой UDP, без DoH или DoT |
| 3 | зашитая в код таблица | 2 `HARDCODED` | `no hardcoded ips found for <host>`, если нет записи |

Flag **13545** (string) маскирует резолверы: `secondary` отключает зашитую таблицу, `hardcoded` отключает UDP-резолвер, `none` отключает оба (битовая логика в `C37151de.A01`). Ошибки `EPERM` пробрасываются повторно, когда установлен управляемый flag переключатель. Коды резолверов попадают в `ClientPayload.dnsSource` (раздел 6.5 отчёта Noise).

---

## 7. Relay для регистрации (found)

Область: HTTP регистрации (`RegistrationHttpManager` = `K49`, `KotlinRegistrationBridge`, `RetryingHttpClient`) к `https://v.whatsapp.net`. Chatd не затрагивает.

### 7.1 Список провайдеров

Ресурс `res/raw/domain_fronting_providers.tsv`, столбцы `name`, `url template`, `host`:

| Имя | Шаблон | Хост |
|------|----------|------|
| `amazon` | `https://y9yrsygcg6.execute-api.us-east-1.amazonaws.com/s/s?_={PATH}&{QS}` | `y9yrsygcg6.execute-api.us-east-1.amazonaws.com` |
| `google` | `https://us-central1-propane-fusion-170222.cloudfunctions.net/s?_={PATH}&{QS}` | `us-central1-propane-fusion-170222.cloudfunctions.net` |

`C45421Jrl` загружает его (строки менее чем с 3 токенами логируют `domain-fronting-providers/load/bad-line`) и хранит три списка: доступные (`A05`), непроверенные (`A06`), недоступные (`A04`). `K49.A0K` передаёт их каждому вызову регистрации в этом порядке.

### 7.2 Probe

`EULA.onCreate` запускает probe не чаще чем раз в 900000 мс (пропускается, когда `C06810Gk(930).A07()`, значение не определено): открыть `https://v.whatsapp.net`; при `IOException` (`DomainFrontingManager/probe-regd/cant connect to regd`) провайдеры перемешиваются и к каждому шаблону выполняется GET с `{PATH}=/` и пустым `{QS}`, таймаут connect и read 60 с, заголовки `Host` = хост провайдера и user agent приложения. HTTP 200 переносит провайдера в список доступных, любая ошибка в список недоступных (`domainFrontingProvider/cant reach`).

### 7.3 Стратегии попыток (`RetryingHttpClient`, `C44407JaE`, `C44975Jk4`)

| Стратегия | Запрос | Состояние в 2.26.41.6 |
|----------|---------|--------------------|
| `ORIGINAL` | обычный URL | всегда попытка 1 |
| `HOST` | тот же URL с заданным IP | список в этой сборке пуст |
| `PROXY` | через заданный IP прокси | список в этой сборке пуст |
| `DOMAIN_FRONTING` | шаблон, где `{PATH}` и `{QS}` заменены исходным путём и сырым query; заголовки `Host` = хост провайдера, `X-Forwarded-Host` = исходный хост | в пределах списка провайдеров |

Порядок: ORIGINAL, записи HOST, записи PROXY, провайдеры; не более 4 попыток. Хост в URL и заголовок `Host` совпадают в обоих шаблонах, поэтому это relay через cloud-функцию (запрос пересылается провайдером на `X-Forwarded-Host`, inferred), а не классический SNI / Host fronting.

Правило повтора: коды результата 2, 5, 7, 12 не повторяются (`non-retryable error`), любая другая ошибка продолжает (`failed attempt N ... reason`); значения кодов не определены. Задержка перед попыткой `n` > 1:

```
delay = clamp(r * (n*n - 1) * 4 * 1000, 0, 60000) ms      // r from a random double, assumed uniform in [0,1)
```

`RetryingHttpClient/executePostWithRetry/applying backoff`, `all retries exhausted`. Флаги payload аттестации endpoint по путям находятся в `AbstractC44143JQf` и к relay отношения не имеют.

---

## 8. Tigon и DGW

| Элемент | Состояние | Уровень |
|------|-------|------|
| Tigon HTTP (`TigonHttpClient`, клиенты MNS) | HTTP(S)-клиент; принимает HTTP-прокси Psiphon и свойства системного прокси (раздел 4.6); не транспорт chatd | found |
| Клиент DGW (`AbstractC20460pC`) | собирается с доменом `gateway.facebook.com`, fallback-конфигом `null`, конфигом персонализации `null` | found |
| `DGWFallbackConfig` | `isFallbackEnabled`, `fallbackDomain`, `numFailuresForFallback`, `fallbackReasons`, `isHardcodedIpFallbackEnabled`; null даёт всё выключенным; Java-builder никогда его не включает, нативные значения по умолчанию неизвестны | found / unknown |
| Пользователи DGW | только `WaFalcoStreamingRegistration` (потоковая телеметрия); см. раздел 13 отчёта Noise | found |

Нативные строки (`distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, метки throttling и zero-rating) описывают внутреннее устройство DGW. Ничто не связывает DGW с восстановлением после блокировки chatd (inferred из отсутствия).

---

## 9. Отслеживание состояния соединения и диагностика

| Элемент | Где | Содержимое |
|------|-------|---------|
| Сохранение последовательности | prefs `connection_sequence_state`, `connection_sequence_attempts`, `last_successful_connection_step`, `_host`, `_port` | точка возобновления, шаг HISTORY (отчёт Noise 2.2) |
| Записи по каждой попытке | `C37811f2` | стадия `DNS` / `SOCKET` / `TLS`, стек `PLATFORM` / `MNS` / `SOCKS_PROXY`, тайминг, ошибка |
| Payload | `ClientPayload.dnsSource`, `connectAttemptCount` | резолвер или маршрут, создавший сокет |
| Proxy service | `C12760bh.A06()`, `A08()` | код состояния (4.3); `A08()` возвращает `both`, `heavy`, `light` или null |
| Пользовательский прокси | статусы `user_proxy_setting_pref`, `wam_user_proxy_set` | UI и аналитика |
| Лог сетевой информации | `C12500bH` | `network_info_is_vpn`, `_is_airplane`, `_is_data_saver`, `_is_cellular_enabled`, `_socks_proxy_active`, `socks_proxy_connected` / `_disconnected` |
| Теги логов | `proxy_service/`, `ConnectionProxyConfig/`, `WaConnectivityProber/`, `WATigonProxyObserver/`, `ConnectionThread/Skipping sequence` | gates и изменения состояния |

---

## 10. Взаимодействие повторных попыток и backoff

Сам backoff (единицы Фибоначчи, ограничение 15 минут, alarms) описан в разделе 10 отчёта Noise. Эта функциональность добавляет:

| Взаимодействие | Эффект |
|-------------|--------|
| Пользовательский прокси сохранён, переключён, удалён | принудительное переподключение (`C11380Yq.A0C(...)`) |
| Изменения конфига proxy service | сброс последовательности; переподключение `proxy_service_update` при включённом flag **36306** |
| Задан пользовательский прокси | одношаговая последовательность; каждая неудачная попытка возвращается к backoff всего подключения |
| Ожидание конфига / HTTP | поток соединения блокируется до flag **19144** мс перед шагом 5; HTTP-стек до flag **29362** мс, пока сервис стартует |
| Регистрация | собственный лимит в 4 попытки и квадратичная задержка (раздел 7.3), не разделяется с chatd |

---

## 11. Feature flags (id как прочитаны в коде; значения серверные)

| Id | Тип | Что контролирует |
|----|------|----------|
| **2784** | bool | функция пользовательского прокси (состояние enabled, deep link) |
| **4020**, **4073**, **4074** | bool | хосты media_conn для native; media через пользовательский прокси; маршрут телеметрии через пользовательский прокси |
| **18875** | bool | prober связности |
| **18871**-**18874** | string, ints | URL probe, задержка, попытки, таймаут |
| **18724**, **18725** | string | разрешённые регионы (источник до входа / обычный) |
| **19067** | bool | повторная проверка региона при подключении |
| **19613** | bool | shutdown при внешней связности |
| **19144** | int | ожидание конфига в мс; отрицательное значение игнорирует сервис на время процесса |
| **19372** | int | порог хорошей сессии (по умолчанию 5) |
| **19905**, **19906**, **26734**, **26735** | bool | отключить WA proxy для HTTP / Tigon (до входа / обычный) |
| **23630** | bool | шаги 2-4 разрешены под прокси (объявлено включённым по умолчанию, inferred) |
| **23730**, **23731** | bool | встроенные записи серверов (до входа / обычный) |
| **23846**, **23879** | JSON | override конфига Psiphon (обычный / до входа) |
| **24067**, **24068** | bool | разрешить сервис при активном VPN |
| **24645** | bool | использовать кэшированный конфиг сервиса без gates |
| **25452** | bool | порядок VPN gate и prober относительно загрузки модуля |
| **25539** | string | allowlist доменов прокси для WebView |
| **25850** | int | таймаут маркера старта в секундах |
| **26334** | bool | пропустить заголовок PROXY v2 |
| **28186**, **28189** | bool | возобновить сервис по push без `psl` |
| **29362** | int | ожидание прокси в HTTP, мс |
| **34525**, **36980** | bool | передать порт SOCKS в VoIP |
| **36306** | bool | переподключение при обновлении proxy service |
| **13545** | string | маска DNS-резолверов |

Flags лестницы chatd и keepalive (**20801**, **22916**, **30712**, **33512**, **7831**-**7834**, **15103**) описаны в разделе 12 отчёта Noise.

---

## 12. Baileys (`baron-baileys-v2`, проверено по его исходному коду)

| Аспект | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Транспорт | WebSocket `ws` к `wss://web.whatsapp.com/ws/chat` (`waWebSocketUrl`) | сырой TCP Noise |
| Прокси | `config.agent` передаётся в `new WebSocket(url, { agent })`; загрузки используют `fetchAgent` | relay WhatsApp Proxy, туннель Psiphon |
| Запасные хосты | один настраиваемый URL | лестница `g`, `g-fallback`, `eN`, порты 443 / 5222 / 80 |
| `<ib><fbip>`, push разблокировки | не обрабатываются | обрабатываются |

```ts
const sock = makeWASocket({ agent: new SocksProxyAgent(proxyUrl), fetchAgent: new SocksProxyAgent(proxyUrl) })
```

| Почему не работает | Причина | Исправление |
|--------------|-------|-----|
| Хост Android WhatsApp Proxy отклоняет Baileys | relay говорит на сыром TCP Noise на порту чата (inferred); Baileys отправляет WebSocket upgrade | использовать HTTP- или SOCKS-прокси, достигающий `web.whatsapp.com` |
| Нет восстановления после блокировки | нет обработки `fbip`, нет push-канала | подставить новый `agent` или URL |

---

## 13. Ошибки

| Симптом | Причина | Исправление |
|---------|-------|-----|
| `Couldn't connect to proxy` | хост пользовательского прокси недоступен или неверная настройка TLS | проверить хост, `Chat port`, `Use TLS`; у последовательности нет прямого fallback |
| `Enter a valid host` / `Enter a valid port` | валидация в `K09` | исправить ввод |
| Ссылка на прокси ничего не делает | flag **2784** выключен или лишние сегменты пути (`proxy_has_segments`) | на стороне клиента ничего |
| `proxy_service/Proxy service detected user region not in region allowlist.` | сообщённый Psiphon регион отклонён списком flag **18724** / **18725** | на стороне клиента ничего |
| Состояние `disabled`, причина `vpn_in_use` | VPN активен, flags **24067** / **24068** выключены | отключить VPN или flag |
| `RetryingHttpClient/executePostWithRetry/all retries exhausted` | все попытки провалились | подождать; лимит 4 |

---

## 14. Ключевые различия

| Не путать | Детали |
|----------------|--------|
| Пользовательский прокси и proxy service | пользовательский прокси = выбранный хост, шаг 12, терминальный, ссылка для обмена; proxy service = серверно управляемый SOCKS-туннель Psiphon для шагов 5 и 13; они исключают друг друга |
| `C48201yM` и шаг 12 | `C48201yM` — сокет SOCKS-туннеля proxy service; шаг 12 — пользовательский прокси и использует обычный или TLS-сокет |
| Light proxy и heavy tunnel | light proxy ограничен шестью перечисленными назначениями `g` / `g-fallback`; heavy tunnel — полная сессия Psiphon |
| `fbip` и push `fbips` и `fallback_*` | `<ib><fbip>` и push `fbips` дают запасные IP chatd; `fallback_hostname` / `fallback_ip*` — атрибуты `media_conn` (раздел 16 отчёта Noise) |
| Relay регистрации и chatd | список провайдеров никогда не питает последовательность чата |
| WhatsApp Proxy и системный прокси | системный прокси для chatd не читается |

---

## 15. Полный поток

```
[Operator]  push nt=unblocking {fbips, unblocking_props, psl}   or   <ib><fbip>...</fbip></ib>
     │  fbips file updated ; props applied ; psl imported (temporary tunnel if inactive)
     ▼
[Client]  C12760bh gates: region (SIM > network > locale), no VPN, flags ; Voltron proxyservice download
     │  PsiphonTunnel.startTunneling(embedded entries) ─► localhost SOCKS + HTTP ports ─► state 6
     ▼
[ProxyServiceBroadcaster]  C37061dV builds ProxyServiceConfig ─► sequence reset ("proxy_service_update")
     │
     ├── user proxy set ─► step 12 only: host:chatPort (+TLS) ─► Noise ─► end (no direct fallback)
     ▼
[ConnectionThread]  steps 5, 13 (2-4 if flag 23630) ─► SOCKS CONNECT g / g-fallback (unresolved host)
     │  PROXY v2 header (client IP) ─► Noise handshake (Noise report section 4)
     ▼
[Server]  login success; session > threshold and route != SOCKS_PROXY ─► proxy ignored for the process
     ▼
[Failure]  timeout / socket error ─► next step ─► exhausted ─► Fibonacci backoff (Noise report section 10)

[Registration]  v.whatsapp.net ─► ORIGINAL ─► relay providers (Host + X-Forwarded-Host) ─► <= 4 attempts
```

---

## 16. Неизвестное

| Элемент | Статус |
|------|--------|
| Любое поведение в сети (туннель, приём PROXY v2, ответ relay, пересылка WhatsApp Proxy) | ничего не перехвачено; ни один пункт не `tested` |
| Внутреннее устройство `libgojni.so`, протоколы, `AdditionalParameters`, содержимое встроенных записей | нативного модуля нет в APK |
| Содержимое списка разрешённых регионов, URL probe, все значения flags | на стороне сервера |
| Значение TLV `E8 00 01 50` в заголовке PROXY v2 | unknown |
| Сопоставление двух карт `unblocking_props` фазам до и после chatd, шифр push | частично выведено |
| Единица flag **19372**, значения кодов в повторе регистрации (2, 5, 7, 12), предикат за `C06810Gk(930).A07()` | не определено |
| Входящая маршрутизация `wa.me/proxy` до `DeepLinkActivity` (фильтры манифеста покрывают `wa.me`) | не прослежено дальше activity |
| Остаётся ли Java-конфиг DGW fallback выключенным в native, и любой native-only fallback | unknown |
| Поведение записей шага 8 внутри запуска с активным Psiphon | inferred прямое |
