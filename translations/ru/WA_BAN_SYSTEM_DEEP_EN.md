<!-- src-sha1: 8651b8d090e77403eb4a371175327e71510f2e61 -->
# WhatsApp Ban System — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** Процесс бана, жизненный цикл WFAC, сбор спам-сигналов, протокол GraphQL, система апелляций, маркировка подозрительных аккаунтов, профилактика

---

## 1. Обзор архитектуры

```
                         [Server]
                             │
       ┌─────────────────────┴──────────────────────────────┐
       ▼                                                     ▼
XMPP login <failure reason=…>                   MEX GraphQL (pull-based)
(HandlerThreadC12340b0.A13 → C45351tB,            │
 handled in C0ZH.handleMessage)                   ├── BizIntegrityQuery ──► BizIntegritySignalsManager
  │                                               │        └─► wa_biz_integrity_signals (SQLite, wa.db)
  ├─ 403 perm-ban ─► HGB.startPermanentBanFlow    │              ├── is_banned (INT)   (stored; no reader found)
  │      └─► BanAppealActivity (userban.ui)       │              ├── is_suspicious (INT)
  ├─ 416 / 402+code 106|107|109 (underage/U13)    │              ├── trust_tier (TEXT)
  │      └─► WfacManager.startUnderageBanFlow     │              ├── dhash (TEXT, server-supplied, opaque)
  ├─ 402 otherwise ─► SpamWarningActivity         │              ├── is_meta_verified (new in 2.26.41.6 vs report)
  ├─ 405 ─► pref software_forced_expiration (`t`)      │              ├── fmx_business_holdout_group (TEXT, new)
  └─ 406 ─► pref underage_account_banned            │              └── integrity_tags (JSON)
                                                  │
                                                  └── ban-status fetch (xwa2_fetch_wa_users, token)
                                                           └─► WfacBanRepository ──► SharedPreferences
                                                                 ├── wfac_ban_state = "BANNED" | "CHECKPOINTED" | "UNBANNED"
                                                                 ├── wfac_ban_violation_type
                                                                 ├── wfac_ban_violation_reason
                                                                 ├── wfac_ban_violation_source
                                                                 ├── wfac_last_ban_status_fetch_timestamp_ms (new)
                                                                 └── wfac_ban_status_token

  Main.A5W() (2.26.26.4: `Main.A5D()`; reads wfac_ban_state at start, registration state 21, log "main/me/wfac ban")
      └─► WfacBanActivity (hard ban UI; now `com.whatsapp.waffle.wfac.ui`, JADX pkg `p191ui`; intent built by `HBC`)

  SpamWarningActivity (pre-ban warning)       ◄── XMPP <failure reason=402> (C0ZH, type 2)
  SuspiciousFmxBottomSheetFragment (info sheet, opened from the FMX card buttons, see 7.2)
  SMB soft-enforcement banner                 ◄── XMPP business notification `biz_integrity_warning_notification` (see 7.4)
```

**Ключевой вывод (исправлен в 2.26.41.6):** синхронизация состояния бана (WFAC) происходит **по модели pull через MEX GraphQL**, но *события* бана и предупреждения в момент подключения приходят по XMPP в узле `<failure>` ответа на login (reason 402/403/416/406, раздел 8.1). Предупреждение о мягком принудительном исполнении для SMB — это бизнес-уведомление XMPP. Сигнализация о бане через `<stream:error>` не найдена (этот обработчик занимается только `code` 515/516, `conflict type="device_removed"` и отключением `ack`).

---

## 2. Жизненный цикл состояния бана (WFAC)

### 2.1 Машина состояний из четырёх значений

| Состояние | Значение | Смысл |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | Нет локального кэша (также фолбэк для любой нераспознанной строки) |
| `CHECKPOINTED` | 1 | Мягкое ограничение, может требоваться верификация. Строка сервера `NO_APPEAL_OPENED` отображается в `CHECKPOINTED` через `AbstractC38371GmM.A00` (новое) |
| `BANNED` | 3 | Жёсткий бан, аккаунт ограничен, апелляция возможна |
| `UNBANNED` | 2 | Полностью функционален |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (intent extra 0/1/2 kept, anything else -1; stored only for launch_source 2/3; default -1 via `HLK`; category names for 0/1/2 not found in 2.26.41.6, so the earlier SPAM/PHISHING/UNDERAGE mapping stays unverified)
wfac_last_ban_status_fetch_timestamp_ms → LONG (throttle, new)
```

Обёртка prefs: `HLK` (геттер состояния парсит через `C36188FnW.A00`: невалидная строка выбрасывает "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 Поток переходов состояний

```
Client connects
    │
    ▼
wfac_ban_status_token present? → NO → UNKNOWN_IN_CLIENT (no check)
    │ YES
    ▼
Registration state == 21? (fully registered)
    │ YES
    ▼
GraphQL: xwa2_fetch_wa_users (with token) (still present, `AWS`, `C46770Kc0`)
    │
    ▼
Throttle: skip if last fetch < 5000 ms ago (refreshInterval) or a fetch is in flight (generation counter); 60 s timeout runnable (new)
    │
    ▼
Response parsed by handler `C40191HfD` (obfuscated name 2.26.41.6; response class `C42252Ic7` / `C204538nH`)
    │
    ├── Stores via SharedPreferences: "wfac_ban_state" = state_string (stale generation responses discarded)
    ├── Error codes 1-4 logged separately; unknown → -1 (found, `C40191HfD`)
    └── Writers of `wfac_ban_state`: this handler (server string stored as is, `WfacBanRepository/storeBanState`), and `WfacBanActivity.onCreate` (launch_source 2/3 → "CHECKPOINTED"; launch_source 4 with `appeal_decision` "banned"/"unbanned" → "BANNED"/"UNBANNED"). No code path from `is_banned` (BizIntegrity) to `wfac_ban_state` was found.
```

### 2.4 Последовательность сброса бана

При успешной апелляции или освобождении аккаунта (`WfacBanViewModel.A0x` / `C36188FnW`, resetRegistration):
1. Очищаются: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`, `wfac_last_ban_status_fetch_timestamp_ms`, `support_ban_appeal_user_banned_from_chat_disconnect` (новое)
2. Выполняется выход пользователя (finishAffinity)
3. Перенаправление на экран входа

---

## 3. BizIntegrityQuery — протокол GraphQL

### 3.1 Технические детали

| Параметр | Значение |
|-----------|-------|
| Имя запроса | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (изменён; был `25975613018777537`, ротация в 2.26.38.10, подтверждена в каталоге persist-id 2.26.41.6; client_doc_id `14769534217004148908396994706`) |
| Схема | `whatsapp-android-mex` |
| Транспорт | MEX HTTP/2 POST → `/mex/query` |
| Формат JID | `<shortNum>@lid` (например, `1910@lid`) |

### 3.2 Запрос

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): объект input: `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`, класс результата `C48528LIw`. `privacy_token` добавляется только когда срабатывает гейт (`MZ4.A00`) и сохранён TC-token. Ответ (found, `C51015Mjl`): корень `xwa2_fetch_wa_users[]`, на каждого пользователя `integrity_signals_info` с полями `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers` (sic, буквальное имя ключа), `is_banned`, `is_suspicious`, `is_suspicious_start_chat`, `join_date_ms` (строка, парсится в long), `phone_country_code`, `trust_tier` (enum `M5B`), `is_mv_subscribed` (хранится как `is_meta_verified`), `meta_verified_info{mv_friction_eligibility}`, `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Перечень полей ниже — это реконструкция для 2.26.26.4 (inferred, не переверифицировано; форма переменной запроса `$userJids` отличается от формы input в 2.26.41.6):

```graphql
query BizIntegrityQuery($userJids: [ID!]!) {
  bizIntegrityQuery(jids: $userJids) {
    jid
    is_banned
    trust_tier
    is_suspicious
    is_suspicious_start_chat
    integrity_tags { tag, pipelineDS, taggedDates }
    dhash
    phone_country_code
    join_date_ms
    fb_linked_page_number_of_likes
    ig_linked_page_number_of_followers
    mv_friction_eligibility
    hide_safety_tools_for_business
    chat_row_id
    last_sync_ts
  }
}
```

### 3.3 DTO ответа — `BizIntegritySignals` (`C51530MtC`; был C39833Hhl в 2.26.26.4)

```
BizIntegritySignals(
  userJid, dhash, fbLinkedPageNumberOfLikes,
  igLinkedPageNumberOfFollowers, isBanned, isSuspicious,
  isSuspiciousStartChat, joinDateMs, phoneCountryCode,
  trustTier, isMetaVerified, mvFrictionEligibility, integrityTags,
  chatRowId, lastSyncTs, hideSafetyToolsForBusiness, fmxBusinessHoldoutGroup
)

Fields:
  integrityTags           → List of IntegrityTagInfo
  userJid                 → UserJid
  hideSafetyToolsForBiz   → Boolean
  isBanned                → Boolean  ← HARD BAN FLAG
  isSuspicious            → Boolean  ← SOFT ENFORCEMENT
  isSuspiciousStartChat   → Boolean
  isMetaVerified          → Boolean  (new)
  mvFrictionEligibility   → Boolean
  fmxBusinessHoldoutGroup → String   (new; stored as fmx_business_holdout_group, purpose unknown)
  chatRowId               → Long
  fbLinkedPageLikes       → Long (stored as REAL)
  igLinkedFollowers       → Long (stored as REAL)
  joinDateMs              → Long (stored as REAL)
  lastSyncTs              → Long
  dhash                   → String
  phoneCountryCode        → String
  trustTier               → String: "SUSPICIOUS" | "UNTIERED" | "TRUSTED"
```

### 3.4 DTO IntegrityTags

(`C51222Mno` список `C51359MqA`; сериализация в `LwI`, форма без изменений)

```
IntegrityTagInfo {
  tag         → String
  pipelineDS  → Date (originally Long ms)
  taggedDates → List<Date>
}
```

**Формат JSON в БД:**
```json
[
  {
    "tag": "automation_bulk_messaging",
    "pipelineDS": 1700000000000,
    "taggedDates": [1699000000000, 1699500000000]
  }
]
```

### 3.5 Триггерные события

| Триггер | Строка usecase |
|---------|---------------|
| Открытие чата | `"START_CHAT_CONTEXT"` (основной триггер) |
| После отправки сообщения | post-send хук |
| Запуск приложения / вход | фоновый планировщик |

### 3.6 Feature flags

| ID флага | Функция |
|---------|---------|
| 11061 | Триггер детекции подозрительного аккаунта (`N5r.A03`; присутствует; оценивается только для контактов, чей уровень verified-name начинается с `ent:`) |
| 11064 | Допуск к trust-сигналу при старте чата (вкл/выкл) (`BizIntegritySignalsManager.A04`; присутствует; по умолчанию false) |
| 11065 | TTL кэша trust-сигнала в секундах (`C51855N0t.A00`; по умолчанию 86400, найден в `C08J`) |
| 12709 | Допуск для контактов, у которых бизнес имеет `hostStorage == 2` (`C197628ax.A06`); по умолчанию false (присутствует) |
| 16349 | Принудительный путь запроса в `BizIntegritySignalsManager.A04` (присутствует; по умолчанию false) |
| 19793 | Новая строка в этой таблице: `N5r.A02`, гейтит повторное использование сохранённых сигналов в `C51855N0t.A02`; назначение выведено из использования; по умолчанию false |
| 12840 | JSON-конфиг по типу нарушения, значение по умолчанию `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`); потребитель не найден; назначение выведено из имён ключей (`max_dismiss_count`, `max_display_days`) и из строк типа, используемых баннером мягкого принудительного исполнения SMB (7.4) |
| 19893 | Логирование системного сообщения FMX-карточки (присутствует, `C198788cr`) |
| 26697 | BizIntegrity v2 (присутствует, `C34735F5e`) |
| 27269 | Раздельный подсчёт входящих/исходящих сообщений (присутствует) |
| 34166 | injection id, не feature flag (см. WA_AB_PROPS.md); используется писателем `start_chat_trust_signals` (`ContactInfoActivity`) |

In-memory кэш в `BizIntegritySignalsManager.A02`: записи действительны 60000 мс (found).

---

## 4. Маркировка подозрительных аккаунтов — когда, почему, как, профилактика (перепроверено в 2.26.41.6; элементы, которые не удалось обнаружить, отмечены на месте)

> **Основной вывод:** для флагов BizIntegrity (`is_suspicious`, `trust_tier`, `is_banned`) клиент ничего не вычисляет: они парсятся из ответа GraphQL (`C51015Mjl`) и только отображаются. Никакого клиентского порога или скоринга для них не найдено. Отдельно, локальная модель на устройстве выдаёт локальные вердикты о скаме (`odml_scam_alert_*`, 6.6, 7.6). Запрос BizIntegrity содержит только запрашиваемые JID, опциональный privacy token и telemetry context (3.2); не найдено, что клиент загружает свои локальные метрики куда-либо ещё.

### 4.1 Кто принимает решение?

```
Local inputs on the device (found):             Server response (found, 3.3):
────────────────────────────────                ──────────────────────────────
• message counts (in/out/threads)               • trust_tier
  via N54 logger (6.2)                          • is_suspicious / is_suspicious_start_chat
• on-device features isCountryMismatch,         • is_banned (stored, no reader found)
  mostRecentSenderScore (6.6)                   • integrity_tags, dhash, join_date_ms,
• BizIntegrity request: jid(s) +                  phone_country_code, FB/IG counts,
  optional privacy_token (TC-token)               is_mv_subscribed, mv_friction_eligibility
```

В клиенте не существует связи между локальными метриками и запросом BizIntegrity (3.2). Какие серверные сигналы формируют вердикт — из APK не видно (server-side ML выведено как предположение). У клиента **нет локального порога** вроде "больше X сообщений -> suspicious" для флагов BizIntegrity.

---

### 4.2 Иерархия уровней доверия (назначается сервером)

Найдено в APK WhatsApp как скомпилированный enum (`M5B` в 2.26.41.6; значения без изменений):

| Уровень | Смысл | Эффект |
|------|---------|--------|
| `SUSPICIOUS` | Наивысший риск — активно помечен | Все предупреждения активны, UI-фрикция, возможна блокировка отправки |
| `TIER_0` | Низший легитимный уровень (новые аккаунты) | Повышенный уровень допуска к фрикции |
| `TIER_1` | Стандартный пользователь | Обычный режим |
| `TIER_2` | Повышенное доверие | Меньше фрикции |
| `TIER_3` | Наивысшее легитимное доверие | Минимальная фрикция |
| `UNTIERED` | Оценка не проводилась | Проверка не применяется |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | Неизвестно | Фолбэк |

**Проверка на уровне кода** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 Сигналы вокруг вердикта

Клиент не прикрепляет приведённые ниже точки данных к запросу BizIntegrity (3.2). В таблице указано, где каждая из них встречается в клиенте; оценивает ли её сервер — предположение. Столбец «Вес риска» из предыдущего отчёта не имел клиентских подтверждений и убран.

| Сигнал | Где встречается в клиенте (2.26.41.6) | Роль |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | признак на устройстве (`integrityai.impl.InputFeatureProviderImpl`, флаг 31535) | Вход локальной модели на устройстве, не запроса |
| `mostRecentSenderScore` | признак на устройстве (флаг 31536) | То же |
| `dhash` | поле ответа, хранится как есть | Серверная opaque-строка; никакой клиентский код её не составляет (значение неизвестно; прежнее прочтение отчёта «отпечаток устройства» — предположение) |
| `join_date_ms`, `phone_country_code` | поля ответа | Хранятся; клиентского порога нет |
| Счётчики FB/IG | поля ответа (`fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers`) | Показываются на FMX-карточке (7.5) |
| `integrity_tags` | поле ответа `{tag, pipeline_date_ms, dates_ms[]}` | Хранится как JSON; значения тегов для клиента opaque |
| Privacy token | поле запроса `privacy_token{tctoken, timestamp}` | Опционально, только когда гейт `MZ4.A00` срабатывает и сохранён TC-token |
| Объём сообщений | локальный подсчёт (`N54`, 6.2) | Загрузка на сервер не найдена |
| Лимит рассылки | флаг 20278, по умолчанию `{"max_messages": 10000, "farthest_time_days": 30}` | Потребитель не найден (6.3) |

`isCountryMismatch` и `mostRecentSenderScore` — два конкретных ML-признака, найденных в клиенте (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`, 2.26.41.6). Флаг 31535 подаёт isCountryMismatch, 31536 — mostRecentSenderScore (found).

---

### 4.4 Когда запускается проверка GraphQL?

**Гейт допуска** (found, `BizIntegritySignalsManager.A04`; запрашиваемый JID — это собеседник чата):
1. Feature flag **11064** включён (по умолчанию false)
2. JID не одного из двух исключённых типов (`AbstractC24760wu.A03/A04`: bot JID и фиксированный JID телефонного номера)
3. Одно из: контакт — бизнес SMB (`N5r.A06`, уровень verified-name начинается с `smb:`), либо флаг **12709** включён и `hostStorage` контакта-бизнеса `== 2` (`C197628ax.A06`), либо (принудительный вызов, `A09`) флаг **16349** включён и выполняется `N5r.A04/A06` (`A04` = `!A01 && !SMB && !ENT`; семантика хелпера `N5r.A01` не разрешена, поэтому какие не-бизнес JID допускаются этим путём, остаётся открытым)
4. Для непринудительного пути: кэш истёк или локального кэша нет (`C51855N0t`)

Исправление относительно прежнего отчёта: в 2.26.41.6 обычный гейт не пропускает бизнес-аккаунты мимо проверки, а наоборот — отбирает их (SMB или hosted); принудительный путь (16349) может допускать и другие JID. Поток JADX для `A04` частично реструктурирован, поэтому эта трактовка основана на форме декомпиляции плюс телах хелперов, а не на smali.

**TTL кэша:** Feature flag **11065** в секундах, по умолчанию **86400 (24 часа)** (found, `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**Размер пачки:** разбиение на пачки по 975 JID в пути выборки GraphQL не существует (`BizIntegritySignalsManager.A03` передаёт список JID без изменений). Константа 975 относится к локальному батчингу SQL-подсчёта сообщений (6.2).

---

### 4.5 Известные значения integrity_tag

Строки `automation_bulk_messaging` и `spam` найдены в `C35896FgX` и `ViewOnClickListenerC39711HTl`, но там они сравниваются с `type` уведомления о мягком принудительном исполнении SMB (`HAR.A07`, см. 7.4), а не с `integrity_tags` из ответа BizIntegrity. Они также встречаются как ключ в значении по умолчанию флага 12840. Клиент вообще не перечисляет значения `integrity_tags`; JSON-блобы хранятся как opaque. Строка `business_policy_violation` не присутствует ни в java_src, ни в smali, ни в assets, ни в res 2.26.41.6.

| Тег | Смысл |
|-----|---------|
| `automation_bulk_messaging` | Тип уведомления о мягком принудительном исполнении (массовая/автоматизированная отправка); не показано, что является значением `integrity_tags` |
| `spam` | Тип уведомления о мягком принудительном исполнении (спам) |

---

### 4.6 Что конкретно приводит к suspicious — предположение на основе кода

Перепроверено в 2.26.41.6: клиент не содержит ни логики, ни порога, ни веса ни для одной строки ниже, а запрос BizIntegrity не содержит ни одной из этих метрик (3.2). Вся таблица остаётся **предположением** (догадкой о серверном поведении по тому, какие сигналы существуют в клиенте). Строка «Новый аккаунт (< 24ч)» не имеет подтверждения: проверки возраста аккаунта в клиенте не существует (см. 4.9 D).

| Поведение | Почему это рискованно | Вес |
|----------|---------------|--------|
| Высокое отношение исходящих к входящим (только отправка, без ответов) | Паттерн массовой рассылки | Очень высокий |
| Страна телефона ≠ страна IP | `isCountryMismatch = 1.0` | Очень высокий |
| Одинаковый dhash на нескольких аккаунтах | Триггер бана устройства | Очень высокий |
| Рассылка > 10 000 получателей / 30 дней | Жёсткий лимит, немедленная пометка | Высокий |
| Высокий `mostRecentSenderScore` (жалобы получателей) | ML-петля обратной связи | Высокий |
| Новый аккаунт (< 24ч, без контактов) | Низкая доверенность (клиентской проверки возраста не найдено) | Высокий |
| Нет связки FB/IG + высокая скорость исходящих | Отсутствие социального подтверждения | Средний |
| Существующие integrity_tags | Эффект предыдущего нарушения | Средний–высокий |
| `is_reach_out = 1` + старт множества чатов с незнакомцами | Паттерн холодных контактов | Средний |

### 4.7 Коды причин SpamWarning (предупреждение перед баном)

Без изменений в 2.26.41.6 (`SpamWarningActivity`: причина по умолчанию 100, срок действия по умолчанию -1; switch по 101, 102, 103, 104, 106, default покрывает 105/прочее).

Доставляется через intent-extra `spam_warning_reason_key`, устанавливается из атрибута `code` (>= 100) узла `<failure reason="402">` ответа на XMPP login, вместе с `expire`, `message`, `url` (found, `C0ZH.handleMessage` тип 2; см. 8.1):

| Код | Триггер | Обратный отсчёт? |
|------|---------|-----------|
| 101 | Обнаружена спам-активность | Да |
| 102 | Нарушение правил пересылки | Да |
| 103 | Спам статусов | Да |
| 104 | Пересылка ботом | Да |
| 105 | Общее / по умолчанию | Постоянно, если expiry = -1 |
| 106 | Другое нарушение | Да |
| default | Неизвестное нарушение | Постоянно, если expiry = -1, иначе отсчёт |

`expiry_in_seconds == -1` + онлайн: немедленное завершение (сервер снял предупреждение).

### 4.8 Категории SpamFlow, относящиеся к маркировке подозрительных

97 категорий в APK (found: `C9E2`, массив из 96 записей плюс `1_1_spam_banner_report`, добавленная последней, индексы от 0 до 96; прежнее число 92 и индексы в таблице устарели). Список сериализуется по имени внутри узла SMAX `spam_list` (атрибут `spam_flow` на каждую запись, опциональный `wi_trace_id` из 24 символов), так что индекс — это только позиция в клиентском массиве, а не значение на проводе. Новые: `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_suspicious_banner_block/_trust`, `odml_scam_alert_fmx_card_block/_trust`, `biz_spam_banner_block`, `1_1_spam_banner_block`, `chat_fmx_card_block`, `group_spam_banner_report`, `left_group_spam_banner_report`. Те, что непосредственно связаны с состоянием suspicious:

| Индекс | Категория | Смысл |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Сервер пометил как suspicious → блокировка FMX |
| 24 | `chat_fmx_card_block_suspicious` | Чат блокирован из-за флага suspicious |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Показаны инструменты безопасности для suspicious |
| 70 | `odml_scam_alert_bottom_sheet_block` | On-device ML скам → блокировка |
| 71 | `odml_scam_alert_bottom_sheet_trust` | On-device ML скам → доверие |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | Баннер спама 1:1 (помечено сервером) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Запрос доверия (помечено сервером) |
| 89 | `user_initiated_chat_suspicious_banner_block` | Баннер suspicious при старте чата |
| 94 | `1_1_old_spam_banner_block` | Устаревший баннер спама |
| 96 | `1_1_spam_banner_report` | Жалоба на спам 1:1 |

### 4.9 Защитные механизмы — что показывает клиент

Прежний список «защитных факторов» — это трактовка серверного ML, не имеющая клиентского подтверждения. Что фактически содержит 2.26.41.6:

#### A) Статус бизнес-аккаунта
Не пропуск проверки. Обычный гейт допуска отбирает контакты SMB (и контакты с `hostStorage == 2` под флагом 12709), см. 4.4. Флаг 2923 (прежнее название: «переключатель валидации не-бизнес-аккаунтов») не найден: ни проверки флага с таким ID, ни значения по умолчанию для него не существует в java_src или smali 2.26.41.6.

#### B) Meta Verified (mvFrictionEligibility)
Поле ответа `meta_verified_info.mv_friction_eligibility` (found, `C51015Mjl`), хранится как `mv_friction_eligibility`. `is_mv_subscribed` хранится отдельно как `is_meta_verified`. FMX-карточка (`C94p`) читает этот флаг и, при включённом флаге 15735, добавляет ссылку «подробнее». То, что это приводит к снижению порогов фрикции, в клиенте не видно (предположение).

#### C) Привязанные социальные аккаунты (FB/IG)
`fb_linked_page_number_of_likes` и `ig_linked_age_number_of_followers` парсятся как целые числа (`optInt`) и показываются на FMX-карточке (7.5). Это счётчики, а не булевы значения (found). Что сервер учитывает их как защитный фактор — предположение.

#### D) Льготный период по возрасту аккаунта
Не найдено. Единственное сравнение, похожее на возраст, — это TTL кэша для `last_sync_ts` относительно флага 11065 (4.4). `join_date_ms` хранится, но логики льготного окна в клиенте нет.

#### E) Белый список / список валидации (флаг 12709)
Изменено: проверка `C197628ax.A06(userJid)` — это `hostStorage == 2` на записи verified-name контакта (`AnonymousClass119`), локальное свойство, а не серверный список предварительного одобрения. Она делает контакт допустимым для запроса; она не вызывает ранний выход.

#### F) hideSafetyToolsForBusiness (поле из ответа)
Поле ответа `hide_safety_tools_for_business`, хранится в `hide_safety_tools_for_business`. Эффект на UI не перепроверен; прежнее утверждение, что оно только скрывает UI предупреждения и не меняет статус suspicious, не подтверждено.

---

### 4.10 Профилактика — что показывает код

Эта часть — рекомендации, выведенные из полей выше. В клиенте нет логики, подтверждающей что-либо из этого; каждый пункт следует считать **предположением**, кроме отмеченных как found.

**Поведенческие (предположение):**
- Поддерживать сбалансированное отношение исходящих/входящих
- Избегать несовпадения страны номера и сети (клиент подаёт `isCountryMismatch` в модель на устройстве, found; использование сервером — предположение)
- Оставаться в пределах конфигурации рассылки флага 20278 (10 000 сообщений / 30 дней; потребитель не найден)

**Качество аккаунта (предположение):**
- Количество связок FB/IG и Meta Verified показываются или хранятся клиентом (found); их влияние на вердикт — предположение
- Окно нового аккаунта (24ч) и блэклистинг по dhash не поддерживаются никаким клиентским кодом (см. 4.9 D и 4.3)

**Технические (found):**
- `privacy_token` (TC-token) добавляется в запрос BizIntegrity только когда срабатывает гейт `MZ4.A00` и сохранён TC-token

**По времени (found):**
- Кэшированные сигналы используются повторно, пока `last_sync_ts` не старше флага 11065 (по умолчанию 86400 с); менеджер дополнительно держит in-memory запись на 60000 мс
- Сигналы сохраняются в `wa_biz_integrity_signals` до перезаписи новым ответом

---

## 5. Локальные базы данных SQLite

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found, `C53116Nmn`, 17 столбцов включая `_id`): добавляет `is_meta_verified` и `fmx_business_holdout_group`; `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `join_date_ms`, `last_sync_ts` имеют тип REAL, `mv_friction_eligibility` и `is_meta_verified` без заявленного значения по умолчанию. Уникальные индексы `biz_integrity_signals_jid_index`, `biz_integrity_signals_chat_row_id_index`; триггер `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). Хранилище: `LwI` (метки `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`, `BizIntegritySignalsStore/saveBusinessIntegritySignals`). Схема ниже — версия для 2.26.26.4.

```sql
CREATE TABLE wa_biz_integrity_signals (
  jid                               TEXT PRIMARY KEY,
  join_date_ms                      LONG,
  trust_tier                        TEXT,     -- "SUSPICIOUS" | "TRUSTED" | ...
  is_suspicious                     INTEGER,  -- 0/1
  is_banned                         INTEGER,  -- 0/1
  dhash                             TEXT,     -- device fingerprint
  phone_country_code                TEXT,
  ig_linked_page_number_of_followers INTEGER,
  fb_linked_page_number_of_likes    INTEGER,
  is_meta_verified                  INTEGER,  -- new in 2.26.41.6
  mv_friction_eligibility           TEXT,
  integrity_tags                    TEXT,     -- JSON array
  chat_row_id                       LONG,
  last_sync_ts                      LONG,
  hide_safety_tools_for_business    INTEGER,  -- 0/1
  fmx_business_holdout_group        TEXT      -- new in 2.26.41.6
);
```

Writer/reader: `LwI` (хранилище), `BizIntegritySignalsManager.A06(UserJid)` читает in-memory `ConcurrentHashMap` (found: `A06` читает in-memory map, `A07` читает её с ленивой загрузкой из БД, `A0A` делает upsert и персистирует; имена `A08`/`A01` из 2.26.26.4 исчезли)

### 5.2 `wa.db` — `start_chat_trust_signals`

```sql
CREATE TABLE start_chat_trust_signals (  -- schema `AI0`, columns unchanged (is_sender_suspicious, is_sender_new_account, created_ts); writer `C198788cr`
  jid                   TEXT PRIMARY KEY,  -- FK to wa_contacts
  is_sender_suspicious  INTEGER,           -- 0/1
  is_sender_new_account INTEGER,           -- 0/1
  created_ts            LONG
);

CREATE TRIGGER start_chat_trust_signals_contact_delete
  BEFORE DELETE ON wa_contacts
  BEGIN DELETE FROM start_chat_trust_signals WHERE jid = old.jid; END;
```

Reader: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`; был C2M7.A0K) → возвращает кортеж `(is_sender_new_account, is_sender_suspicious)`

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

Метка запроса: `"GET_INTEGRITY_CHAT_INFO"` (пакетный запрос с `chat_row_id IN (...)`), хранилище `C33O`, схема `C08970Ox` (индекс `integrity_chat_info_chat_row_id_index`, триггер `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). Без изменений.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

Найдено в 2.26.41.6: схема `AHY` (столбцы `jid`, `last_delivered_sort_id` LONG, `last_read_sort_id` LONG), уникальный индекс `biz_integrity_chat_settings_index` по `jid`, триггер `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). Назначение неизвестно.

---

## 6. Сбор спам-сигналов (на стороне клиента)

(Перепроверено в 2.26.41.6; элементы, которые не удалось обнаружить, отмечены на месте.)

### 6.1 dhash

`dhash` — строка в ответе BizIntegrity (`integrity_signals_info.dhash`), хранится открытым текстом в `wa_biz_integrity_signals.dhash`. Никакой клиентский код её не составляет: не найдено ни модели устройства, ОС, версии приложения, номера, часового пояса, Android ID, ни build-отпечатка как входных данных, и ничего её не загружает. Прежнее описание «отпечаток устройства / серверный блэклист» не подтверждается; значение неизвестно. Другие строки `dhash` в APK (список блокировки, opt-out бизнеса) — это несвязанные хэши директорий.

---

### 6.2 Скорость отправки сообщений

Найдено: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`, хелпер `N54`) локально считает сообщения за интервал времени по списку JID, с алиасами SQL:
- `incoming_count`: сообщения с `from_me = 0`
- `incoming_threads_count`: уникальные `chat_row_id` для полученных сообщений
- `outgoing_count`: сообщения с `from_me = 1`
- `outgoing_threads_count`: уникальные `chat_row_id` для отправленных сообщений
- Счётчик удалённых сообщений: `messages_count_after_privacy_token` (также `messages_count`, `outgoing_messages_count`) из `integrity_deleted_chat_message_count`

Feature flag 27269 определяет, считаются ли входящие/исходящие отдельно или как общая сумма (found в том же обработчике).
Размер пачки: **975 JID** на один SQL-вызов обработки (found: `C20H.A1A(list, 975)`, разбиение по лимиту переменных SQLite, а не сетевая пачка).
Не найдено: разбиение по дням/часам, пер-контактная частота; куда идут счётчики после подсчёта, не прослежено.

---

### 6.3 Лимиты рассылки (бизнес-аккаунты)

Feature config 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found как значение по умолчанию в `C08J`/`C09W`).
- Лимит 10 000 сообщений за 30 дней — это значение по умолчанию конфига; потребитель этого JSON (код, который применяет его перед отправкой, `renewal_date`, пер-получательский троттлинг, классификация маркетинг/обычное) не найден: строки-ключи `max_messages`/`farthest_time_days` встречаются только в таблицах значений по умолчанию, а `renewal_date` в java_src не встречается вовсе.

---

### 6.4 Принудительное исполнение GAP (Global Abuse Prevention)

Найдено: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) пропускается, когда feature flag 14837 выключен, и сохраняет `LAST_MARKETING_MESSAGE_TIMESTAMP` в SharedPreferences (`C67902uK`), когда приходит более новое маркетинговое сообщение. Флаг 25631 гейтит другой путь триггера. Расшифровка «Global Abuse Prevention» в коде не встречается (название не подтверждено).

Отслеживаемое состояние (`ChatDescription`, found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Найдено: пакет `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`, `WaFaReportScheduler`, `FaReportRunner`, `WaFaReportSubmitter`, `FaTeeConnection`, `FaTeeAcsRepository`, `FaAcsWarmer`). Отчёты передаются через TEE-соединение, аутентифицированное через ACS (заголовки `x-acs-token`, `x-acs-configid`, `x-acs-project-name`; выборка публичного ключа OHAI). Время следующего запуска — в prefs `fa_next_report_run_timestamp`.
Не найдено: содержимое отчётов. Список метрик из прежнего отчёта (принятие фич, краши, задержки, RAM/хранилище/ОС, геофенсинг, данные сессии, тип подключения) не найден как код; содержимое отчёта определяется конфигурацией, поэтому из клиента его прочитать нельзя.

---

### 6.6 Извлечение ML-признаков (детекция скама на устройстве)

Два конкретных признака найдены в декомпилированном клиенте:
- `isCountryMismatch` (float 0.0/1.0): страна отправителя ≠ страна получателя → **ВЫСОКИЙ РИСК**
- `mostRecentSenderScore` (float): ML-репутационный балл отправителя

Feature flags 31535/31536 управляют их значениями (found). Отправка результатов на сервер для вторичного ML-скоринга — предположение.

---

## 7. UI-компоненты: Suspicious, предупреждения, бан

(Перепроверено в 2.26.41.6: `SpamWarningActivity` теперь `com.whatsapp.userban.spamwarning`, `SuspiciousFmxBottomSheetFragment` — `com.whatsapp.fmx` плюс новый подкласс `SuspiciousSmbFmxBottomSheetFragment`. Условия триггера из 7.2, 7.4 и 7.5 исправлены ниже.)

### 7.1 SpamWarningActivity

Параметры intent:
- `spam_warning_reason_key` (int): код причины
- `expiry_in_seconds`: отсчёт (-1 = постоянно)
- `spam_warning_message_key`: кастомный текст
- `faq_url_key`: ссылка на FAQ

Коды причин:

| Код | Смысл |
|------|---------|
| 100 | Общее предупреждение о спаме |
| 101 | Обнаружена спам-активность |
| 102 | Нарушение правил пересылки |
| 103 | Спам статусов |
| 104 | Пересылка ботом |
| 105 | Общее / постоянное |
| 106 | Прочие нарушения |

Если `expiry_in_seconds != -1` → показывается таймер обратного отсчёта.
Если `-1` + онлайн → немедленное завершение (сервер снял предупреждение).

### 7.2 Нижний лист Suspicious FMX (`SuspiciousFmxBottomSheetFragment`)

Найдено: информационный лист (ссылки «подробнее» `about-blocking-reporting`, `examples-of-scams`), а не блокировщик, управляемый состоянием. Открывается нажатием на кнопку состояния suspicious на FMX-карточке (`C93z.setupSuspiciousButtons`, вариант SMB `C94p` открывает `SuspiciousSmbFmxBottomSheetFragment`) и из `C512928n` (вариант SMB, когда контакт — бизнес, `A0T()`), через хелперы `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

Четыре условия триггера из прежнего отчёта (`is_suspicious == 1`, `is_suspicious_start_chat == 1`, `is_reach_out == 1`, `chat_fmx_card_block_suspicious == 1` как блокировка отправки) не подтверждаются: сам фрагмент ни одно из них не читает, а `chat_fmx_card_block_suspicious` — это имя категории SpamFlow (4.8), а не хранимый флаг. Что найдено: контекст старта чата показывается, когда `is_suspicious_start_chat` истинно (`StartChatContextUtils`), а FMX-карточка вычисляет `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 UI жёсткого бана WFAC

| Класс | Функция |
|-------|---------|
| `WfacBanActivity` | Точка входа, информация о бане + кнопка апелляции |
| `WfacBanInfoFragment` | Детали нарушения + ссылка на апелляцию |
| `WfacBanDecisionFragment` | Действие пользователя (апелляция подана) |
| `WfacUnbanDecisionFragment` | Подтверждение после апелляции |

Триггер (изменён): `Main.A5D()` исчез; его эквивалент — `Main.A5W()`, который читает `wfac_ban_state` при старте (switch по "UNBANNED" / "BANNED" / "CHECKPOINTED", registration state 21, лог "main/me/wfac ban") и запускает `WfacBanActivity` через `HBC`. Слушателя изменений SharedPreferences не найдено. `wfac_ban_state` записывается обработчиком выборки статуса бана и `WfacBanActivity.onCreate` (2.3). Путь login-failure (403) открывает более старую `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`) вместо этого. 2.26.41.6: классы теперь в `com.whatsapp.waffle.wfac.ui` (также `WfacBanBaseFragment`); активити открывается через intent-хелпер `HBC` и переход экрана `I1T` (`transitionToScreen`).

#### 7.3a Прогрев аттестации Play Integrity в апелляции на бан (новое в 2.26.45.10, found)

`com.whatsapp.userban.ui.BanAppealActivity` (экран апелляции на пути login-failure, выше) теперь запускает **прогрев аттестации Google Play Integrity** как часть собственного жизненного цикла, до фактической отправки апелляции — три новых класса в `com.whatsapp.userban.signals`:

| Класс | Роль |
|-------|------|
| `BanAppealPlayIntegrityPrewarmer` (тело корутины `$prewarm$1`) | Запрашивает/подготавливает токен Google Play Integrity заранее, до того как пользователь закончит заполнять форму апелляции |
| `BanAppealSignalsAggregator` | Объединяет прогретый токен с другими асинхронными источниками сигналов (каждый разрешается через свой типизированный `LX/05b;` deferred) в один агрегат |
| `BanAppealExistRequester` | Проверяет существование апелляции/бана и там же живут `appeal_token`, `backup_token` и сам запрос `ban_appeal` (`no_appeal_token` как логируемый случай отказа) |

`BanAppealActivity` конструирует `BanAppealPlayIntegrityPrewarmer$prewarm$1` прямо внутри своего метода resume-пути (переименован в smali как `A44`) и запускает его на coroutine scope — то есть прогрев начинается, как только открывается экран апелляции, а не в момент отправки, так что токен уже подготовлен к тому моменту, когда `BanAppealExistRequester` отправляет апелляцию. Прогреватель логирует четыре именованных исхода отказа как обычные строки: `"BanAppealPlayIntegrityPrewarmer/prewarm nonpositive_timeout"`, `"...prepare_failed"`, `"...api_error"`, `"...unavailable"` — единственное структурированное свидетельство его собственных режимов отказа; соответствующего строкового литерала для успешного пути не найдено (вероятно, просто кэшированный объект токена без строки лога).

**Недостижимо отдельно**: Play Integrity выдаёт токен, аттестованный Google, привязанный к конкретному устройству/приложению, который сторонний клиент не может подделать или воспроизвести для другого устройства — это поднимает порог для автоматизации апелляций, а не открывает новую поверхность для апелляции. Состояния бана `unbanReasonData`/`IN_REVIEW` и остальной поток апелляции (7.3, таблица из 7.3) не изменились по сути; усложнился только путь отправки за счёт этого шага аттестации.

### 7.4 Мягкое принудительное исполнение SMB

Изменено: триггером не является `is_suspicious=true` + `integrity_tags`, содержащий `"business_policy_violation"` (эта строка не существует в 2.26.41.6). Это бизнес-уведомление XMPP (обработчик `AnonymousClass142`, id уведомления 202) с дочерним узлом `biz_integrity_warning_notification > violation`:

| Атрибут | Использование |
|-----------|-----|
| `source` | источник нарушения (обязательный) |
| `type` | тип нарушения, например `automation_bulk_messaging`, `spam` (сравнивается в `C35896FgX`) |
| `severity` | например, `"severe"` меняет текст баннера (`C35896FgX`, `WABIEnforcementEducationFragment`) |
| `policy_url` | целевая ссылка (обязательный) |
| `priority` | int >= 0 (обязательный) |
| `status` | `active` (хранится, счётчики сбрасываются) или `inactive` (удаляется) |

Клиент строит `SMBSoftEnforcementNotification` (`HAR`) с `notificationType`, зафиксированным как `"warning"`, и `bannerNotificationTimeStamp` = время получения, и сохраняет JSON-массив в настройке `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) с ключами ниже. Счётчики на каждое уведомление — int-настройки `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

```json
[{
  "source": "...",
  "type": "automation_bulk_messaging",
  "severity": "severe",
  "notificationType": "warning",
  "policyUrl": "https://...",
  "status": "active",
  "bannerNotificationTimeStamp": 1700000000000,
  "priority": 1
}]
```

JSON из прежнего отчёта (`notification_type: soft_enforcement`, `violation_type`, `education_url`, `action_required`) в клиенте не присутствует. UI: `SMBSoftEnforcementEducationFragment`, `WABIEnforcementEducationFragment` в `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 FMX-карточка (карточка trust-сигнала)

Найдено: системное сообщение типа 129 (`0x81`, `C57172Xr`) создаётся в `C198788cr` ("Creating FMX card system message for chat", "ContactsProcessor/added contact info message"); флаг 19893 там гейтит только событие аналитики. Асинхронная запись в `start_chat_trust_signals` гейтится через `C1P2.A01()` (флаг не разрешён) и выполняется через `C65972r0`. Карточка (`C94p`) отображает число лайков FB и подписчиков IG, а также флаг фрикции Meta Verified; `"SUSPICIOUS".equals(trust_tier)` выбирает вариант для suspicious. Отображение возраста аккаунта и условие отображения «бизнес / неизвестный контакт» не найдены.

---

### 7.6 ODML Scam Alert (ML на устройстве)

Загружаемая ML-модель через ACS-токен `"WA_ODML"` (found в `OdmlModelDownloadClient`, `ODML_MODEL_DOWNLOAD`, id `27301080136160169`, TTL 345600 с = 4 дня; размер кэша 64 не найден). Переключается пользователем через `ScamDetectionSettingsActivity`. Funnel отслеживается через session ID / source / intent-extra точки входа.

---

## 8. XMPP и станзы (контекст бана)

(Перепроверено в 2.26.41.6 путём чтения обработчиков login и stream-error; раздел 8.1 исправлен. Прежняя проверка на 2.26.35.2 не видела push-сообщений о бане через XMPP; это наблюдение заменено путём login-failure ниже.)

### 8.1 `<failure>` при логине несёт баны и предупреждения

Прежнее утверждение «баны приходят только через MEX GraphQL» неверно для событий в момент подключения. `HandlerThreadC12340b0.A13` читает узел результата login; для `<failure>` берёт `reason` (int) и строит исключение `C45351tB` (found):

| `reason` | Тип | Читаемые атрибуты | Реакция клиента (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | Ошибка сервера, путь повторной попытки |
| 402 | 2 (по умолчанию) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `SpamWarningActivity` с `spam_warning_reason_key` = `code` (>= 100), `expiry_in_seconds`, текст, FAQ url |
| 402 + `appeal_token` + `code` 106 | 13 | то же | `ContextualAgeCollectionActivity` (extras `appealToken`, `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | то же | путь "U13 Banned PAA Pending" (prefs managed-account, онбординг) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | Постоянный бан: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (после задержки по флагу 19714, в мс) |
| 405 | 3 | `t` (секунды) | Записывает prefs `software_forced_expiration` |
| 406 | 5 | `code` | Prefs `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`; `violation_reason == "u13_checkpoint"` устанавливает `support_ban_appeal_user_banned_from_chat_disconnect` |
| прочее | 0 | - | Logout (путь "exception-password") |

Все типы failure также читают опциональные атрибуты UI для logout: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text`, `logout_main_button_url`, `logout_secondary_button_text`, `logout_secondary_button_url`. `location` читается из узла для маршрутизации.

`<stream:error>` (перехватчик чтения-компаньон, `C40601l6`): `code` 515 / 516, дочерний узел `conflict type="device_removed"` (дерегистрация), дочерний `ack` (кик). Специфичного для бана дочернего узла не найдено. `<presence type="unavailable">` и коды закрытия WebSocket не изучались.

### 8.2 Токены ошибок XMPP (бинарный словарь)

Словарь `AbstractC40911lb` (однобайтовый `A00`, двухбайтовый `A01`). Наличие токенов из прежней таблицы:

| Строка токена | В словаре |
|-------------|---------------|
| `stream:error` | да |
| `conflict` | да |
| `not-authorized` | да |
| `item-not-found` | да |
| `server-error` | да |
| `401` | да |
| `policy-violation` | не найден |
| `403` | не найден как токен (значение `reason` 403 читается как int-атрибут) |

Столбец «Смысл» прежнего отчёта (например, `403` = "Forbidden (ban-related)") был предположением; только смысл 403 теперь подтверждён обработкой `<failure>` выше. Также в словаре: `404`, `407`, `failure`, `locked`.

### 8.3 IQ-ответы для ограниченных аккаунтов

Не найдено. Ни пространство имён `urn:ietf:params:xml:ns:xmpp-stanzas`, ни тексты "Account restricted" / "User banned" не существуют в java_src или ресурсах 2.26.41.6, и токенов `forbidden` / `service-unavailable` в словаре нет. Примеры XML из прежнего отчёта не подтверждены и на них не следует опираться (возможно, они иллюстративные). Обработка ошибок на уровне отдельных IQ (например, парсеры `item-not-found`, `not-authorized`, такие как `K3P`, `C23205A1e`) не прослежена для ограниченных аккаунтов.

---

## 9. Полный поток данных (сквозной)

(Перепроверено в 2.26.41.6: doc_id `28596420510007620`, форма input `query_input`, имена классов выше. Стрелки `isBanned` -> `wfac_ban_state` -> `Main.A5D()` из диаграммы для 2.26.26.4 удалены, поскольку такой связи в коде не существует; см. разделы 1 и 2.3.)

```
[Open chat / send message]
           │
           ▼
  Check integrity_chat_info (is_reach_out?)
           │
           ▼
  Lookup start_chat_trust_signals (is_sender_suspicious? is_sender_new_account?)
           │
           ▼
  BizIntegritySignalsManager eligibility check — feature flag 11064
           │
    Flag active?
     YES │
         ▼
  BizIntegritySignalsGraphQLFetcher
    → HTTP/2 POST /mex/query
    → Variables: input{query_input:[{jid, privacy_token?}], telemetry{context:"INTERACTIVE"}}
    → doc_id: 28596420510007620
           │
           ▼
  Response → BizIntegritySignals DTO
           │
  wa_biz_integrity_signals (SQLite write, incl. is_banned, is_suspicious)
           │
    is_suspicious_start_chat? ──► start-chat context
    trust_tier == "SUSPICIOUS" ──► suspicious FMX card variant
           │                         └─► tap -> SuspiciousFmxBottomSheet (info only)
           ▼
  (is_banned: stored, no reader found)

  Separate path: XMPP login <failure reason=402|403|416> -> SpamWarningActivity /
  BanAppealActivity / WfacManager; WFAC state: Main.A5W -> WfacBanActivity
           │
           ▼
  [User submits appeal]
           │
           ▼
  Fetch purpose_public_keys (purpose_public_ek/ik/ik_sig, dummy ciphertext/nonce)
           │
           ▼
  Encrypt(form_data JSON {token, debug_info, description}, info "WA_INAPP_BAN_APPEALS", `C37414GLt`)
           │
           ▼
  Graph request to https://<host>.facebook.com/graphql by doc_id (section 10)
           │
           ▼
  Server review → wfac_ban_state update → WfacUnbanDecisionFragment
```

---

## 10. Запрос апелляции (2.26.41.6)

Найдено в `C37414GLt`: `variables` запроса в JSON несёт `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` и `app_id` (`"dev.app.id"`); открытый текст перед шифрованием — `{token, debug_info, description}`; метка контекста `"WA_INAPP_BAN_APPEALS"` (info для деривации ключа). Транспорт (found, `AbstractC40195HfH`): обычный POST к Facebook Graph на `https://<host>.facebook.com/graphql` с полями `doc_id` и `access_token`, не MEX. `C37414GLt` передаёт `doc_id` **38509456535312323**, когда `hg3.A04.A00()` истинно, иначе **5473316762755318**. Имя операции `submitBanAppeal` не встречается как строка в java_src, smali, assets или res 2.26.41.6, и ни один из doc_id не находится в каталоге запросов проекта, так что имя не подтверждено. Перед отправкой `C40191HfD` парсит первый ответ с `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}`, который даёт ключевой материал для шифрования.

---

## 11. Изменения относительно 2.26.26.4

| Элемент | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| doc_id BizIntegrityQuery | `25975613018777537` | `28596420510007620` (ротация в 2.26.38.10) |
| Форма запроса | список `$userJids` (реконструировано) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| Класс DTO | `C39833Hhl` | `C51530MtC` (17 полей: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 столбцов | + `is_meta_verified`, `fmx_business_holdout_group`; счётчики REAL |
| Хранилище / менеджер | `BizIntegritySignalsManager.A08/A01` | хранилище `LwI`, схема `C53116Nmn`, менеджер A02 с in-memory кэшем на 60 с |
| Reader start_chat_trust_signals | `C2M7.A0K` | `C57342Yp` |
| Enum уровня доверия | не зафиксирован, 7 значений | `M5B`, те же 7 значений |
| Пакет UI WFAC | `com.whatsapp.waffle.wfac` (плоский) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| Prefs WFAC | 5 ключей | + `wfac_last_ban_status_fetch_timestamp_ms` (троттлинг обновления 5 с), `support_ban_appeal_user_banned_from_chat_disconnect` очищается при сбросе |
| Парсинг состояния бана | 4 состояния | то же; `NO_APPEAL_OPENED` отображается в `CHECKPOINTED` |
| Флаги | 11061/11064/11065/12709/16349/19893/26697/27269 | все присутствуют; + 19793 (N5r.A02) |
| Коды SpamWarning 100-106 | есть | без изменений |
| integrity_tags | `automation_bulk_messaging`, `spam` | без изменений |
| SpamFlow | 92 категории | 97; добавлены `odml_scam_alert_*`, `biz_spam_banner_block` и прочие |
| ML-признаки | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | без изменений, в `integrityai.impl.InputFeatureProviderImpl` |
| Лимит рассылки 20278 | 10000 / 30 дней | без изменений |
| События бана/предупреждения в момент подключения | «нет сигнализации о бане через XMPP» | XMPP login `<failure>`: reason 402 (SpamWarning / U13), 403 (перм. бан -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | реагирует на изменение `wfac_ban_state` | исчез; `Main.A5W()` читает состояние при старте (reg state 21) и открывает `WfacBanActivity` через `HBC` |
| Писатели `wfac_ban_state` | не зафиксированы | обработчик выборки статуса бана `C40191HfD`; `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED по launch source); связи от `is_banned` нет |
| Допуск BizIntegrity | «бизнес-аккаунты пропускают проверку» | отбирает контакты SMB (уровень `smb:`) либо `hostStorage == 2` (12709); принудительный путь 16349; разбиения на пачки по 975 JID в выборке нет |
| Пачка из 975 | пачка GraphQL | локальный чанк SQL для подсчёта сообщений (`N54`) |
| Флаг 12709 | серверный белый список | локальная проверка `hostStorage == 2` |
| Флаг 2923, льготный период 24ч по возрасту аккаунта, составление `dhash` | заявлялось | не найдено в 2.26.41.6 |
| Значения `integrity_tags` | `automation_bulk_messaging`, `spam` | эти строки — значения `type` уведомления о мягком принудительном исполнении SMB, а не `integrity_tags` |
| Мягкое принудительное исполнение SMB | тег `business_policy_violation` + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`; сохранённые ключи JSON `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`; флаг 12840 |
| Индексы/количество SpamFlow | 92, например `odml_scam_alert_bottom_sheet_block` = 65 | 97 записей (`C9E2`), те же имена со смещёнными индексами (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | открывается по 4 условиям данных | информационный лист, открываемый из кнопок FMX-карточки / `C512928n` |
| Запрос апелляции | мутация MEX `submitBanAppeal` | Graph `https://<host>.facebook.com/graphql` по doc_id 38509456535312323 / 5473316762755318, перед которым идёт выборка `purpose_public_keys`; имя операции не найдено |
| `wa_biz_integrity_chat_settings` | не найдено | найдено (`AHY`) |
| Токены ошибок XMPP | токены `policy-violation`, `403` | не в словаре; `forbidden`/`service-unavailable` и тексты из 8.3 отсутствуют |

Остаётся открытым в 2.26.41.6: имена категорий за `wfac_ban_violation_source` 0/1/2; потребитель флага 20278 и флага 12840; семантика хелпера `N5r.A01`; содержимое отчётов WaFA; обработка ошибок на уровне отдельных IQ для ограниченных аккаунтов (8.3); отображение возраста аккаунта на FMX-карточке; флаг за `C1P2.A01()`.
