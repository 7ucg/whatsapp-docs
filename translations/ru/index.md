<!-- src-sha1: a10cc235881df66d01adf85a7dcdb73c2853c297 -->
---
hide:
  - navigation
  - toc
---

# WhatsApp Docs

Документация по внутреннему устройству **WhatsApp Android**, полученная методом реверс-инжиниринга. Статический анализ APK, без перехвата трафика.

<div class="grid cards" markdown>

-   :material-shield-lock: **[Система банов](WA_BAN_SYSTEM_DEEP_EN.md)**

    ---

    Жизненный цикл WFAC, BizIntegrityQuery, пометка как подозрительного, спам-сигналы, предотвращение.

    `APK 2.26.41.6`

-   :material-key-chain: **[TCToken и CSToken](WA_TCTOKEN_CSTOKEN.md)**

    ---

    Антиспам-токены аттестации, синхронизация NctSalt, станзы, поля proto, Baileys.

    `APK 2.26.41.6`

-   :material-robot-outline: **[Meta AI](WA_META_AI.md)**

    ---

    JID ботов, поля proto, протокол запрос/ответ, почему Baileys не работает.

    `APK 2.26.41.6`

-   :material-shield-alert: **[Жалобы](WA_REPORTING.md)**

    ---

    Типы жалоб, станза SMAX spam_list, 97 значений spam_flow, токены жалоб, процесс блокировки.

    `APK 2.26.41.6`

-   :material-fingerprint: **[Целостность клиента](WA_CLIENT_INTEGRITY.md)**

    ---

    Keystore attestation, Play Integrity, WASafe, флаги телеметрии, что отправляется.

    `APK 2.26.41.6`

-   :material-link-variant: **[Привязка устройств](WA_LINKED_DEVICE_PAIRING.md)**

    ---

    Сценарии QR и pair-кода, подписанная идентичность ADV, список устройств, отвязка.

    `APK 2.26.41.6`

-   :material-at: **[Username](WA_USERNAME.md)**

    ---

    Операции с username, ключ username, связь с LID, doc_id w:mex.

    `APK 2.26.41.6`

-   :material-lock-check: **[Безопасность аккаунта](WA_ACCOUNT_SECURITY.md)**

    ---

    Вход по паролю (конверт #PWD_WA), PIN, резервная почта, passkeys, доверенные устройства, нативный OPAQUE.

    `APK 2.26.41.6`

-   :material-sync: **[Синхронизация состояния](WA_APPSTATE_SYNC.md)**

    ---

    Коллекции syncd, патчи и снапшоты, MAC и LTHash, обмен ключами, 96 sync actions.

    `APK 2.26.41.6`

-   :material-lan-connect: **[Транспорт Noise](WA_NOISE_TRANSPORT.md)**

    ---

    chatd поверх TCP, рукопожатие Noise XX, ClientPayload, кодирование binary node, backoff переподключения, Tigon.

    `APK 2.26.41.6`

-   :material-phone-in-talk: **[Сигнализация звонков](WA_CALL_SIGNALING.md)**

    ---

    Stanza звонков, offer и call key, rekey, relay и медиа-путь, групповые звонки, ссылки, журнал звонков.

    `APK 2.26.41.6`

-   :material-cloud-upload: **[Загрузка медиа](WA_MEDIA_UPLOAD.md)**

    ---

    media_conn, URL загрузки и скачивания, медиаключи HKDF, AES-CBC + HMAC, докачка и повторы, коды результатов, нативное hardening.

    `APK 2.26.41.6`

-   :material-sync-multiple: **[USync](WA_USYNC.md)**

    ---

    Stanza USync, 4 режима, 10 контекстов, 30 типов sync, синхронизация контактов и устройств, LID-маппинг.

    `APK 2.26.41.6`

-   :material-account-group: **[История групп](WA_GROUP_HISTORY.md)**

    ---

    Пакет истории для новых участников, history sync companion-устройств, режимы адресации, лимиты.

    `APK 2.26.41.6`

-   :material-bullhorn: **[Списки рассылки](WA_BROADCAST_LISTS.md)**

    ---

    IQ списков w:b, fan-out, месячная квота, баны за спам-предупреждения, status@broadcast.

    `APK 2.26.41.6`

-   :material-chart-line: **[Аналитика WAM](WA_WAM_ANALYTICS.md)**

    ---

    Модель событий WAM, 4 канала, загрузка w:stats, приватная статистика, ежедневные события, формат буфера.

    `APK 2.26.41.6`

-   :material-flag: **[AB Props](WA_AB_PROPS.md)**

    ---

    Таблицы флагов (21 424 id), MobileConfig, синхронизация props, хранение, overrides, каталог флагов.

    `APK 2.26.41.6`

-   :material-database: **[Локальное хранилище](WA_LOCAL_STORAGE.md)**

    ---

    msgstore.db и wa.db, ключевые таблицы, prefs, кэши, бэкапы, пути очистки при выходе.

    `APK 2.26.41.6`

-   :material-key-chain-variant: **[Секреты сообщений](WA_MESSAGE_SECRETS.md)**

    ---

    messageSecret, ключи HKDF по сценариям, зашифрованные реакции, опросы и события, расширения stanza.

    `APK 2.26.41.6`

-   :material-swap-horizontal: **[Интероперабельность](WA_INTEROP.md)**

    ---

    Интероперабельность чатов со сторонними сервисами (отключена): IQ w:interop, InteropMessage, домены JID, согласие.

    `APK 2.26.41.6`

-   :material-shield-off: **[Обход блокировок](WA_CENSORSHIP_CIRCUMVENTION.md)**

    ---

    Прокси WhatsApp, SOCKS-туннель Psiphon, push разблокировки, relay регистрации, чего нет в сборке.

    `APK 2.26.41.6`

-   :material-view-dashboard: **[Серверный UI](WA_SERVER_DRIVEN_UI.md)**

    ---

    Phoenix, Bloks, native flows и WhatsApp Flows, форматы payload, действия, безопасность.

    `APK 2.26.41.6`

-   :material-account-off: **[Поверхность без аккаунта](WA_ACCOUNT_LESS_SURFACE.md)**

    ---

    Экраны до регистрации, deep links, хосты, идентификаторы, 97 экспортируемых компонентов.

    `APK 2.26.41.6`

</div>

!!! info "Скоро"
    Скоро появятся новые отчёты: новые темы и обновления для каждой новой версии APK.

## Ссылки

[:fontawesome-brands-github: GitHub](https://github.com/7ucg){ .md-button } [:material-source-repository: Репозиторий](https://github.com/7ucg/whatsapp-docs){ .md-button } [:fontawesome-brands-discord: Discord](https://discord.gg/R77JyK2Fu6){ .md-button } [:fontawesome-brands-telegram: Telegram](https://t.me/wegschleifen){ .md-button } [:material-history: Список изменений](CHANGELOG.md){ .md-button }

## Как читать отчёты

!!! success "found"
    Прочитано напрямую в декомпилированном коде APK.

!!! warning "inferred"
    Выведено из контекста кода или именования. Не подтверждено во время выполнения.

!!! failure "(2.26.26.4, not re-verified)"
    Перенесено из более старого APK. Считать возможно устаревшим.

Каждый отчёт заканчивается таблицей **Changes vs 2.26.26.4**. Обфусцированные имена классов (например, `C51530MtC`) меняются с каждой сборкой.

## Область

- Система банов: жизненный цикл WFAC, GraphQL BizIntegrityQuery, уровни доверия
- Пометка как подозрительного: когда, почему, сигналы, предотвращение
- Система жалоб: станзы SMAX, spam_list, типы жалоб
- Детали XMPP: структуры станз, бинарный словарь токенов
- Клиентские сигналы: dhash, скорость сообщений, лимиты рассылок, WaFA
- Жалобы, целостность клиента, привязка устройств, username
