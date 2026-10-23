<!-- src-sha1: 8678a730de6a0b84185733d9edd5ef1ba49ca935 -->
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
