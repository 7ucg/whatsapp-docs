<!-- src-sha1: 7460884998f14495a9fdb811db77f25ed82ce6f6 -->
# WhatsApp Ban System — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** Процесс бана, жизненный цикл WFAC, сбор спам-сигналов, протокол GraphQL, система апелляций, пометка suspicious, предотвращение

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

**Ключевая находка (исправлена в 2.26.41.6):** синхронизация состояния бана (WFAC) работает **по pull-модели через MEX GraphQL**, но *события* бана и предупреждений в момент подключения приходят по XMPP в узле login `<failure>` (reason 402/403/416/406, раздел 8.1). Предупреждение SMB soft-enforcement приходит как XMPP-уведомление для бизнеса. Сигналов бана через `<stream:error>` не найдено (этот обработчик работает только с `code` 515/516, `conflict type="device_removed"` и `ack`-киками).

---

## 2. Жизненный цикл состояния бана (WFAC)

### 2.1 Автомат из четырёх состояний

| Состояние | Значение | Смысл |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | Локального кэша нет (также fallback для любой нераспознанной строки) |
| `CHECKPOINTED` | 1 | Мягкое ограничение, может потребоваться верификация. Серверная строка `NO_APPEAL_OPENED` отображается в `CHECKPOINTED` через `AbstractC38371GmM.A00` (новое) |
| `BANNED` | 3 | Жёсткий бан, аккаунт ограничен, апелляция возможна |
| `UNBANNED` | 2 | Полностью работоспособен |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (intent extra 0/1/2 kept, anything else -1; stored only for launch_source 2/3; default -1 via `HLK`; category names for 0/1/2 not found in 2.26.41.6, so the earlier SPAM/PHISHING/UNDERAGE mapping stays unverified)
wfac_last_ban_status_fetch_timestamp_ms → LONG (throttle, new)
```

Обёртка prefs: `HLK` (геттер состояния разбирает значение через `C36188FnW.A00`: неверная строка бросает "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

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

При успешной апелляции или снятии ограничений с аккаунта (`WfacBanViewModel.A0x` / `C36188FnW`, resetRegistration):
1. Очищает: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`, `wfac_last_ban_status_fetch_timestamp_ms`, `support_ban_appeal_user_banned_from_chat_disconnect` (новое)
2. Выполняет выход пользователя (finishAffinity)
3. Перенаправляет на экран входа

---

## 3. BizIntegrityQuery — протокол GraphQL

### 3.1 Технические детали

| Параметр | Значение |
|-----------|-------|
| Имя запроса | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (изменён; был `25975613018777537`, ротирован в 2.26.38.10, подтверждён в каталоге persist-id 2.26.41.6; client_doc_id `14769534217004148908396994706`) |
| Схема | `whatsapp-android-mex` |
| Транспорт | MEX HTTP/2 POST → `/mex/query` |
| Формат JID | `<shortNum>@lid` (например `1910@lid`) |

### 3.2 Запрос

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): входной объект `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`, класс результата `C48528LIw`. `privacy_token` добавляется только если совпадает gate (`MZ4.A00`) и есть сохранённый TC-token. Ответ (found, `C51015Mjl`): корень `xwa2_fetch_wa_users[]`, для каждого пользователя `integrity_signals_info` с полями `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers` (sic, буквальный ключ), `is_banned`, `is_suspicious`, `is_suspicious_start_chat`, `join_date_ms` (строка, парсится в long), `phone_country_code`, `trust_tier` (enum `M5B`), `is_mv_subscribed` (сохраняется как `is_meta_verified`), `meta_verified_info{mv_friction_eligibility}`, `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Приведённый ниже список полей — реконструкция 2.26.26.4 (inferred, не перепроверено; форма переменных запроса `$userJids` отличается от формы входных данных 2.26.41.6):

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

### 3.3 DTO ответа — `BizIntegritySignals` (`C51530MtC`; в 2.26.26.4 был C39833Hhl)

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

(`C51222Mno` — список `C51359MqA`; сериализация в `LwI`, форма не изменилась)

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

### 3.5 События-триггеры

| Триггер | Строка usecase |
|---------|---------------|
| Открытие чата | `"START_CHAT_CONTEXT"` (основной триггер) |
| После отправки сообщения | post-send hook |
| Запуск приложения / вход | фоновый планировщик |

### 3.6 Feature-флаги

| ID флага | Функция |
|---------|---------|
| 11061 | Триггер обнаружения suspicious-аккаунта (`N5r.A03`; present; оценивается только для контактов, у которых уровень verified-name начинается с `ent:`) |
| 11064 | Допуск сигнала доверия start-chat (вкл/выкл) (`BizIntegritySignalsManager.A04`; present; по умолчанию false) |
| 11065 | TTL кэша сигналов доверия в секундах (`C51855N0t.A00`; по умолчанию 86400, found в `C08J`) |
| 12709 | Допуск для контактов, у которых business `hostStorage == 2` (`C197628ax.A06`); по умолчанию false (present) |
| 16349 | Путь принудительного запроса в `BizIntegritySignalsManager.A04` (present; по умолчанию false) |
| 19793 | Новое в этой таблице: `N5r.A02`, управляет повторным использованием сохранённых сигналов в `C51855N0t.A02`; назначение inferred из использования; по умолчанию false |
| 12840 | JSON-конфиг с ключом по типу нарушения, по умолчанию `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`); потребитель не найден; назначение inferred по именам ключей (`max_dismiss_count`, `max_display_days`) и по строкам типов, используемым баннером SMB soft-enforcement (7.4) |
| 19893 | Логирование системного сообщения карточки FMX (present, `C198788cr`) |
| 26697 | BizIntegrity v2 (present, `C34735F5e`) |
| 27269 | Раздельный подсчёт входящих/исходящих сообщений (present) |
| 34166 | Писатель start_chat_trust_signals (present, `ContactInfoActivity`) |

Кэш в памяти в `BizIntegritySignalsManager.A02`: записи действительны 60000 мс (found).

---

## 4. Пометка Suspicious — когда, почему, как, предотвращение (перепроверено в 2.26.41.6; пункты, которые не удалось найти, помечены на месте)

> **Ключевая находка:** для флагов BizIntegrity (`is_suspicious`, `trust_tier`, `is_banned`) клиент ничего не вычисляет: они разбираются из ответа GraphQL (`C51015Mjl`) и только отображаются. Клиентских порогов или скоринга для них не найдено. Отдельно, модель на устройстве формирует локальные вердикты о скаме (`odml_scam_alert_*`, 6.6, 7.6). Запрос BizIntegrity содержит только запрашиваемые JID, необязательный privacy token и контекст телеметрии (3.2); отправка локальных метрик клиентом куда-либо ещё не найдена.

### 4.1 Кто решает?

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

Стрелки от локальных метрик к запросу BizIntegrity в клиенте нет (3.2). Какие серверные сигналы формируют вердикт, из APK не видно (серверный ML inferred). У клиента **нет локального порога** вида «более X сообщений -> suspicious» для флагов BizIntegrity.

---

### 4.2 Иерархия Trust Tier (назначается сервером)

Найдено в APK WhatsApp как скомпилированный enum (`M5B` в 2.26.41.6; значения не изменились):

| Tier | Смысл | Эффект |
|------|---------|--------|
| `SUSPICIOUS` | Наивысший риск — активно помечен | Все предупреждения активны, трение в UI, возможна блокировка отправки |
| `TIER_0` | Низший легитимный уровень (новые аккаунты) | Повышенная допустимость трения |
| `TIER_1` | Стандартный пользователь | Норма |
| `TIER_2` | Повышенное доверие | Меньше трения |
| `TIER_3` | Наивысшее легитимное доверие | Минимальное трение |
| `UNTIERED` | Нет оценки | Проверка не применяется |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | Неизвестно | Fallback |

**Проверка на уровне кода** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 Сигналы вокруг вердикта

Клиент не прикрепляет перечисленные ниже данные к запросу BizIntegrity (3.2). Таблица показывает, где каждый из них встречается в клиенте; оценивает ли его сервер — inferred. Столбец «Risk weight» из прежнего отчёта не имел клиентских подтверждений и удалён.

| Сигнал | Где встречается в клиенте (2.26.41.6) | Роль |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | признак на устройстве (`integrityai.impl.InputFeatureProviderImpl`, флаг 31535) | Вход модели на устройстве, не запроса |
| `mostRecentSenderScore` | признак на устройстве (флаг 31536) | То же |
| `dhash` | поле ответа, сохраняется как есть | Непрозрачная строка от сервера; клиентский код её не формирует (значение unknown; прежняя трактовка отчёта как «отпечаток устройства» — inferred) |
| `join_date_ms`, `phone_country_code` | поля ответа | Сохраняются; клиентского порога нет |
| Счётчики FB/IG | поля ответа (`fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers`) | Показываются на карточке FMX (7.5) |
| `integrity_tags` | поле ответа `{tag, pipeline_date_ms, dates_ms[]}` | Сохраняется как JSON; значения тегов непрозрачны для клиента |
| Privacy token | поле запроса `privacy_token{tctoken, timestamp}` | Необязательно, только при совпадении gate `MZ4.A00` и наличии сохранённого TC-token |
| Объём сообщений | локальный подсчёт (`N54`, 6.2) | Отправка на сервер не найдена |
| Лимит рассылки | флаг 20278, по умолчанию `{"max_messages": 10000, "farthest_time_days": 30}` | Потребитель не найден (6.3) |

`isCountryMismatch` и `mostRecentSenderScore` — два конкретных ML-признака, найденных в клиенте (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`, 2.26.41.6). Флаг 31535 поставляет isCountryMismatch, 31536 — mostRecentSenderScore (found).

---

### 4.4 Когда запускается проверка GraphQL?

**Gate допуска** (found, `BizIntegritySignalsManager.A04`; запрашиваемый JID — собеседник по чату):
1. Feature-флаг **11064** включён (по умолчанию false)
2. JID не относится к двум исключённым типам (`AbstractC24760wu.A03/A04`: JID ботов и один фиксированный JID с номером телефона)
3. Одно из: контакт — SMB-бизнес (`N5r.A06`, уровень verified-name начинается с `smb:`), либо включён флаг **12709** и у бизнеса контакта `hostStorage == 2` (`C197628ax.A06`), либо (принудительный вызов, `A09`) включён флаг **16349** и выполняется `N5r.A04/A06` (`A04` = `!A01 && !SMB && !ENT`; семантика вспомогательного метода `N5r.A01` не выяснена, поэтому какие небизнес-JID это допускает — открытый вопрос)
4. Для непринудительного пути: кэш истёк или локального кэша нет (`C51855N0t`)

Поправка к прежнему отчёту: в 2.26.41.6 обычный gate не пропускает бизнес-аккаунты, а выбирает их (SMB или hosted); принудительный путь (16349) может допускать другие JID. Поток JADX для `A04` частично перестроен, поэтому такое чтение получено из формы декомпилята и тел вспомогательных методов, а не из smali.

**TTL кэша:** Feature-флаг **11065** в секундах, по умолчанию **86400 (24 часа)** (found, `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**Размер пакета:** разбиения на 975 JID в пути GraphQL-запроса нет (`BizIntegritySignalsManager.A03` передаёт список JID без изменений). Константа 975 относится к локальной пакетной обработке SQL при подсчёте сообщений (6.2).

---

### 4.5 Известные значения integrity_tag

Строки `automation_bulk_messaging` и `spam` найдены в `C35896FgX` и `ViewOnClickListenerC39711HTl`, но там они сравниваются с `type` уведомления SMB soft-enforcement (`HAR.A07`, см. 7.4), а не с `integrity_tags` из ответа BizIntegrity. Они также встречаются как ключ значения по умолчанию флага 12840. Клиент вообще не перечисляет значения `integrity_tags`; JSON-блобы хранятся непрозрачно. `business_policy_violation` отсутствует как строка в java_src, smali, assets и res версии 2.26.41.6.

| Тег | Смысл |
|-----|---------|
| `automation_bulk_messaging` | Тип уведомления soft-enforcement (массовая/автоматизированная рассылка); не доказано, что это значение `integrity_tags` |
| `spam` | Тип уведомления soft-enforcement (спам) |

---

### 4.6 Что конкретно ведёт к suspicious — inferred из кода

Перепроверено в 2.26.41.6: в клиенте нет логики, порога или веса ни для одной строки ниже, и запрос BizIntegrity не содержит ни одной из этих метрик (3.2). Вся таблица остаётся **inferred** (предположение о поведении сервера по тому, какие сигналы есть в клиенте). Строка «New account (< 24h)» ничем не подкреплена: проверки возраста аккаунта в клиенте нет (см. 4.9 D).

| Поведение | Почему рискованно | Вес |
|----------|---------------|--------|
| Много исходящих при малом числе входящих (только отправка, без ответов) | Шаблон массовой рассылки | Очень высокий |
| Страна телефона ≠ страна IP | `isCountryMismatch = 1.0` | Очень высокий |
| Один и тот же dhash на нескольких аккаунтах | Триггер бана устройства | Очень высокий |
| Рассылка > 10,000 получателей / 30 дней | Жёсткий лимит, немедленный флаг | Высокий |
| Высокий `mostRecentSenderScore` (жалобы получателей) | ML-петля обратной связи | Высокий |
| Новый аккаунт (< 24h, нет контактов) | Низкая достоверность (клиентской проверки возраста не найдено) | Высокий |
| Нет связи с FB/IG + высокая исходящая активность | Отсутствие социального подтверждения | Средний |
| Существующие integrity_tags | Эффект прежнего нарушения | Средний–высокий |
| `is_reach_out = 1` + начало множества чатов с неизвестными | Шаблон холодных контактов | Средний |

### 4.7 Коды причин SpamWarning (предупреждение перед баном)

Без изменений в 2.26.41.6 (`SpamWarningActivity`: причина по умолчанию 100, срок по умолчанию -1; switch по 101, 102, 103, 104, 106, default покрывает 105/прочее).

Передаются через intent extra `spam_warning_reason_key`, задаваемый из атрибута `code` (>= 100) XMPP login `<failure reason="402">` вместе с `expire`, `message`, `url` (found, `C0ZH.handleMessage` тип 2; см. 8.1):

| Код | Триггер | Обратный отсчёт? |
|------|---------|-----------|
| 101 | Обнаружена спам-активность | Да |
| 102 | Нарушение при пересылке | Да |
| 103 | Спам в статусах | Да |
| 104 | Пересылка ботом | Да |
| 105 | Общее / по умолчанию | Постоянно, если expiry = -1 |
| 106 | Прочее нарушение | Да |
| default | Неизвестное нарушение | Постоянно, если expiry = -1, иначе обратный отсчёт |

`expiry_in_seconds == -1` + онлайн: немедленное завершение (сервер снял предупреждение).

### 4.8 Категории SpamFlow, относящиеся к пометке suspicious

97 категорий в APK (found: `C9E2`, массив из 96 элементов плюс `1_1_spam_banner_report`, добавленный последним, индексы от 0 до 96; прежнее число 92 и индексы в таблице заменены). Список сериализуется по именам внутри SMAX-узла `spam_list` (атрибут `spam_flow` для каждого элемента, необязательный `wi_trace_id` из 24 символов), поэтому индекс — лишь позиция в клиентском массиве, а не значение на проводе. Новые: `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_suspicious_banner_block/_trust`, `odml_scam_alert_fmx_card_block/_trust`, `biz_spam_banner_block`, `1_1_spam_banner_block`, `chat_fmx_card_block`, `group_spam_banner_report`, `left_group_spam_banner_report`. Напрямую связанные с состоянием suspicious:

| Индекс | Категория | Смысл |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Помечено сервером как suspicious → блок FMX |
| 24 | `chat_fmx_card_block_suspicious` | Чат заблокирован из-за флага suspicious |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Инструменты безопасности показаны для suspicious |
| 70 | `odml_scam_alert_bottom_sheet_block` | ML на устройстве: скам → блок |
| 71 | `odml_scam_alert_bottom_sheet_trust` | ML на устройстве: скам → доверие |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | Спам-баннер 1:1 (помечено сервером) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Запрос доверия (помечено сервером) |
| 89 | `user_initiated_chat_suspicious_banner_block` | Suspicious-баннер при начале чата |
| 94 | `1_1_old_spam_banner_block` | Устаревший спам-баннер |
| 96 | `1_1_spam_banner_report` | Жалоба на спам 1:1 |

### 4.9 Механизмы защиты — что показывает клиент

Прежний список «защитных факторов» — это трактовка серверного ML без клиентского подкрепления. Что реально содержит 2.26.41.6:

#### A) Статус бизнеса
Не пропуск. Обычный gate допуска выбирает SMB-контакты (и контакты с `hostStorage == 2` при флаге 12709), см. 4.4. Флаг 2923 (ранее: «переключатель валидации небизнеса») не найден: проверки флага с таким ID и значения по умолчанию в конфиге для него нет ни в java_src, ни в smali версии 2.26.41.6.

#### B) Meta Verified (mvFrictionEligibility)
Поле ответа `meta_verified_info.mv_friction_eligibility` (found, `C51015Mjl`), сохраняется как `mv_friction_eligibility`. `is_mv_subscribed` сохраняется отдельно как `is_meta_verified`. Карточка FMX (`C94p`) читает этот флаг и при включённом флаге 15735 добавляет ссылку «learn more». Что это снижает пороги трения — в клиенте не видно (inferred).

#### C) Привязанные соцсети (FB/IG)
`fb_linked_page_number_of_likes` и `ig_linked_age_number_of_followers` разбираются как целые числа (`optInt`) и показываются на карточке FMX (7.5). Это счётчики, а не булевы значения (found). Что сервер считает их защитными — inferred.

#### D) Льготный период по возрасту аккаунта
Не найдено. Единственное сравнение, похожее на возраст, — TTL кэша по `last_sync_ts` относительно флага 11065 (4.4). `join_date_ms` сохраняется, но логики льготного окна в клиенте нет.

#### E) Whitelist / список валидации (флаг 12709)
Изменено: проверка `C197628ax.A06(userJid)` — это `hostStorage == 2` в записи verified-name контакта (`AnonymousClass119`), локальное свойство, а не серверный список предварительного одобрения. Она делает контакт допустимым для запроса; досрочного возврата не происходит.

#### F) hideSafetyToolsForBusiness (поле из ответа)
Поле ответа `hide_safety_tools_for_business`, сохраняется в `hide_safety_tools_for_business`. Влияние на UI заново не прослежено; прежнее утверждение, что оно лишь скрывает UI предупреждений и не меняет статус suspicious, не проверено.

---

### 4.10 Предотвращение — что раскрывает код

Эта часть — рекомендации, выведенные из полей выше. В клиенте нет логики, подтверждающей что-либо из этого; считайте каждый пункт **inferred**, кроме помеченных found.

**Поведенческое (inferred):**
- Поддерживайте баланс соотношения исходящих/входящих
- Избегайте несовпадения страны номера и сети (клиент передаёт `isCountryMismatch` модели на устройстве, found; использование сервером inferred)
- Оставайтесь в пределах конфига рассылки флага 20278 (10,000 сообщений / 30 дней; потребитель не найден)

**Качество аккаунта (inferred):**
- Количество привязанных FB/IG и Meta Verified показываются или сохраняются клиентом (found); их влияние на вердикт inferred
- Окно нового аккаунта (24h) и занесение dhash в чёрный список не подкреплены никаким клиентским кодом (см. 4.9 D и 4.3)

**Технические (found):**
- `privacy_token` (TC-token) добавляется в запрос BizIntegrity только когда совпадает gate `MZ4.A00` и сохранён TC-token

**Тайминг (found):**
- Кэшированные сигналы используются повторно, пока `last_sync_ts` не станет старше значения флага 11065 (по умолчанию 86400 с); менеджер дополнительно держит запись в памяти на 60000 мс
- Сигналы сохраняются в `wa_biz_integrity_signals`, пока не будут перезаписаны новым ответом

---

## 5. Локальные базы данных SQLite

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found, `C53116Nmn`, 17 столбцов включая `_id`): добавлены `is_meta_verified` и `fmx_business_holdout_group`; `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `join_date_ms`, `last_sync_ts` имеют тип REAL, у `mv_friction_eligibility` и `is_meta_verified` значение по умолчанию не задано. Уникальные индексы `biz_integrity_signals_jid_index`, `biz_integrity_signals_chat_row_id_index`; триггер `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). Хранилище: `LwI` (метки `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`, `BizIntegritySignalsStore/saveBusinessIntegritySignals`). Схема ниже — версия 2.26.26.4.

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

Запись/чтение: `LwI` (хранилище), `BizIntegritySignalsManager.A06(UserJid)` читает из `ConcurrentHashMap` в памяти (found: `A06` читает карту в памяти, `A07` читает её с ленивой загрузкой из БД, `A0A` делает upsert и сохраняет; имена `A08`/`A01` из 2.26.26.4 исчезли)

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

Чтение: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`; ранее C2M7.A0K) → возвращает кортеж `(is_sender_new_account, is_sender_suspicious)`

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

Найдено в 2.26.41.6: схема `AHY` (столбцы `jid`, `last_delivered_sort_id` LONG, `last_read_sort_id` LONG), уникальный индекс `biz_integrity_chat_settings_index` по `jid`, триггер `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). Роль unknown.

---

## 6. Сбор спам-сигналов (на стороне клиента)

(Перепроверено в 2.26.41.6; пункты, которые не удалось найти, помечены на месте.)

### 6.1 dhash

`dhash` — строка в ответе BizIntegrity (`integrity_signals_info.dhash`), хранится открытым текстом в `wa_biz_integrity_signals.dhash`. Клиентский код её не формирует: входных данных вроде модели устройства, ОС, версии приложения, номера, часового пояса, Android ID или build-fingerprint не найдено, и ничто их не отправляет. Прежнее описание «отпечаток устройства / серверный чёрный список» не подтверждено; значение unknown. Прочие строки `dhash` в APK (список блокировок, business opt-out) — несвязанные хэши каталогов.

---

### 6.2 Скорость отправки сообщений

Found: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`, helper `N54`) локально считает сообщения за промежуток времени для списка JID, с SQL-алиасами:
- `incoming_count`: сообщения с `from_me = 0`
- `incoming_threads_count`: уникальные `chat_row_id` для полученных сообщений
- `outgoing_count`: сообщения с `from_me = 1`
- `outgoing_threads_count`: уникальные `chat_row_id` для отправленных сообщений
- Количество удалённых сообщений: `messages_count_after_privacy_token` (также `messages_count`, `outgoing_messages_count`) из `integrity_deleted_chat_message_count`

Feature-флаг 27269 определяет, считаются ли входящие/исходящие раздельно или общим итогом (found в том же обработчике).
Размер пакета: **975 JID** за один вызов обработки SQL (found: `C20H.A1A(list, 975)`, фрагмент по лимиту переменных SQLite, а не сетевой пакет).
Не найдено: разбиение по дням/часам, скорость на контакт; куда уходят счётчики после подсчёта, не прослежено.

---

### 6.3 Лимиты рассылки (бизнес-аккаунты)

Feature-конфиг 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found как значение по умолчанию в `C08J`/`C09W`).
- Лимит 10,000 сообщений за 30 дней — значение конфига по умолчанию; потребитель этого JSON (код, применяющий его перед отправкой, `renewal_date`, ограничение по получателям, различение marketing и обычных сообщений) не найден: строки ключей `max_messages`/`farthest_time_days` встречаются только в таблицах значений по умолчанию, а `renewal_date` в java_src не встречается.

---

### 6.4 GAP enforcement (Global Abuse Prevention)

Found: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) пропускается при выключенном feature-флаге 14837 и сохраняет `LAST_MARKETING_MESSAGE_TIMESTAMP` в SharedPreferences (`C67902uK`), когда приходит более новое маркетинговое сообщение. Флаг 25631 управляет другим путём триггера. Расшифровки «Global Abuse Prevention» в коде нет (название не проверено).

Отслеживаемое состояние (`ChatDescription`, found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Found: пакет `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`, `WaFaReportScheduler`, `FaReportRunner`, `WaFaReportSubmitter`, `FaTeeConnection`, `FaTeeAcsRepository`, `FaAcsWarmer`). Отчёты идут через TEE-соединение, аутентифицированное с помощью ACS (заголовки `x-acs-token`, `x-acs-configid`, `x-acs-project-name`; получение публичного ключа OHAI). Время следующего запуска — в pref `fa_next_report_run_timestamp`.
Не найдено: содержимое отчётов. Список метрик из прежнего отчёта (принятие функций, сбои, задержки, RAM/хранилище/ОС, геозоны, данные сессий, тип соединения) как код не найден; содержимое отчётов определяется конфигом, поэтому из клиента его прочитать нельзя.

---

### 6.6 Извлечение ML-признаков (обнаружение скама на устройстве)

Два конкретных признака найдены в декомпилированном клиенте:
- `isCountryMismatch` (float 0.0/1.0): страна отправителя ≠ страна получателя → **HIGH RISK**
- `mostRecentSenderScore` (float): ML-оценка репутации отправителя

Feature-флаги 31535/31536 управляют их значениями (found). Результаты отправляются на сервер для вторичного ML-скоринга (inferred).

---

## 7. Компоненты UI: Suspicious, предупреждения, бан

(Перепроверено в 2.26.41.6: `SpamWarningActivity` теперь `com.whatsapp.userban.spamwarning`, `SuspiciousFmxBottomSheetFragment` — `com.whatsapp.fmx` плюс новый подкласс `SuspiciousSmbFmxBottomSheetFragment`. Условия срабатывания в 7.2, 7.4 и 7.5 исправлены ниже.)

### 7.1 SpamWarningActivity

Параметры intent:
- `spam_warning_reason_key` (int): код причины
- `expiry_in_seconds`: обратный отсчёт (-1 = постоянно)
- `spam_warning_message_key`: произвольный текст
- `faq_url_key`: ссылка на FAQ

Коды причин:

| Код | Смысл |
|------|---------|
| 100 | Общее спам-предупреждение |
| 101 | Обнаружена спам-активность |
| 102 | Нарушение при пересылке |
| 103 | Спам в статусах |
| 104 | Пересылка ботом |
| 105 | Общее / постоянно |
| 106 | Прочие нарушения |

Если `expiry_in_seconds != -1` → показывается таймер обратного отсчёта.
Если `-1` + онлайн → немедленное завершение (сервер снял предупреждение).

### 7.2 Suspicious FMX Bottom Sheet (`SuspiciousFmxBottomSheetFragment`)

Found: информационная панель (ссылки «learn more» `about-blocking-reporting`, `examples-of-scams`), а не блокировщик, управляемый состоянием. Она открывается нажатием кнопки suspicious-состояния на карточке FMX (`C93z.setupSuspiciousButtons`, SMB-вариант `C94p` открывает `SuspiciousSmbFmxBottomSheetFragment`) и из `C512928n` (SMB-вариант, когда контакт — бизнес, `A0T()`), через helpers `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

Четыре условия срабатывания из прежнего отчёта (`is_suspicious == 1`, `is_suspicious_start_chat == 1`, `is_reach_out == 1`, `chat_fmx_card_block_suspicious == 1` как блокировка отправки) не подтверждены: сам фрагмент не читает ни одно из них, а `chat_fmx_card_block_suspicious` — имя категории SpamFlow (4.8), а не сохранённый флаг. Что найдено: контекст start-chat показывается, когда `is_suspicious_start_chat` истинно (`StartChatContextUtils`), а карточка FMX вычисляет `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 UI жёсткого бана WFAC

| Класс | Функция |
|-------|---------|
| `WfacBanActivity` | Точка входа, информация о бане + кнопка апелляции |
| `WfacBanInfoFragment` | Детали нарушения + ссылка на апелляцию |
| `WfacBanDecisionFragment` | Действие пользователя (апелляция отправлена) |
| `WfacUnbanDecisionFragment` | Подтверждение после апелляции |

Триггер (изменён): `Main.A5D()` исчез; его эквивалент — `Main.A5W()`, который при старте читает `wfac_ban_state` (switch по "UNBANNED" / "BANNED" / "CHECKPOINTED", состояние регистрации 21, лог "main/me/wfac ban") и запускает `WfacBanActivity` через `HBC`. Слушателя изменений SharedPreferences не найдено. `wfac_ban_state` записывается обработчиком запроса статуса бана и `WfacBanActivity.onCreate` (2.3). Путь login-failure (403) вместо этого открывает более старый `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`). 2.26.41.6: классы теперь в `com.whatsapp.waffle.wfac.ui` (также `WfacBanBaseFragment`); activity открывается через intent-helper `HBC` и переход экрана `I1T` (`transitionToScreen`).

### 7.4 SMB Soft Enforcement

Изменено: триггер — не `is_suspicious=true` + `integrity_tags`, содержащие `"business_policy_violation"` (такой строки в 2.26.41.6 нет). Это XMPP-уведомление для бизнеса (обработчик `AnonymousClass142`, id уведомления 202) с дочерним элементом `biz_integrity_warning_notification > violation`:

| Атрибут | Использование |
|-----------|-----|
| `source` | источник нарушения (обязательный) |
| `type` | тип нарушения, например `automation_bulk_messaging`, `spam` (сравнивается в `C35896FgX`) |
| `severity` | например `"severe"` меняет текст баннера (`C35896FgX`, `WABIEnforcementEducationFragment`) |
| `policy_url` | цель ссылки (обязательный) |
| `priority` | int >= 0 (обязательный) |
| `status` | `active` (сохраняется, счётчики сбрасываются) или `inactive` (удаляется) |

Клиент строит `SMBSoftEnforcementNotification` (`HAR`) с `notificationType`, жёстко заданным как `"warning"`, и `bannerNotificationTimeStamp` = время получения, и сохраняет JSON-массив в preference `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) с ключами ниже. Счётчики по уведомлениям — int-preferences `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

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

JSON из прежнего отчёта (`notification_type: soft_enforcement`, `violation_type`, `education_url`, `action_required`) в клиенте отсутствует. UI: `SMBSoftEnforcementEducationFragment`, `WABIEnforcementEducationFragment` в `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 Карточка FMX (карточка сигнала доверия)

Found: системное сообщение типа 129 (`0x81`, `C57172Xr`) создаётся в `C198788cr` ("Creating FMX card system message for chat", "ContactsProcessor/added contact info message"); флаг 19893 там лишь управляет аналитическим событием. Асинхронная запись в `start_chat_trust_signals` управляется `C1P2.A01()` (флаг не определён) и выполняется через `C65972r0`. Карточка (`C94p`) отображает счётчики лайков FB и подписчиков IG и флаг трения Meta Verified; `"SUSPICIOUS".equals(trust_tier)` выбирает suspicious-вариант. Отображение возраста аккаунта и условие показа «business/unknown contact» не найдены.

---

### 7.6 ODML Scam Alert (ML на устройстве)

Загружаемая ML-модель через ACS-токен `"WA_ODML"` (found в `OdmlModelDownloadClient`, `ODML_MODEL_DOWNLOAD`, id `27301080136160169`, TTL 345600 с = 4 дня; размер кэша 64 не найден). Пользователь может переключать через `ScamDetectionSettingsActivity`. Воронка отслеживается через intent extras: session ID / source / entry point.

---

## 8. XMPP и станзы (контекст бана)

(Перепроверено в 2.26.41.6 чтением обработчиков login и stream-error; раздел 8.1 исправлен. Более ранняя проверка 2.26.35.2 не обнаружила XMPP-push бана; это наблюдение заменено путём login-failure ниже.)

### 8.1 Login `<failure>` несёт баны и предупреждения

Прежнее утверждение «баны приходят только через MEX GraphQL» неверно для событий в момент подключения. `HandlerThreadC12340b0.A13` читает узел результата login; для `<failure>` он берёт `reason` (int) и строит исключение `C45351tB` (found):

| `reason` | Тип | Читаемые атрибуты | Реакция клиента (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | Ошибка сервера, путь повтора |
| 402 | 2 (по умолчанию) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `SpamWarningActivity` с `spam_warning_reason_key` = `code` (>= 100), `expiry_in_seconds`, текстом, FAQ url |
| 402 + `appeal_token` + `code` 106 | 13 | то же | `ContextualAgeCollectionActivity` (extras `appealToken`, `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | то же | Путь "U13 Banned PAA Pending" (prefs управляемого аккаунта, onboarding) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | Перманентный бан: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (после задержки флага 19714 в мс) |
| 405 | 3 | `t` (секунды) | Записывает pref `software_forced_expiration` |
| 406 | 5 | `code` | Pref `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`; `violation_reason == "u13_checkpoint"` устанавливает `support_ban_appeal_user_banned_from_chat_disconnect` |
| other | 0 | - | Выход из аккаунта (путь "exception-password") |

Все типы failure также читают необязательные атрибуты UI выхода: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text`, `logout_main_button_url`, `logout_secondary_button_text`, `logout_secondary_button_url`. `location` читается из узла для маршрутизации.

`<stream:error>` (сопутствующий read interceptor, `C40601l6`): `code` 515 / 516, дочерний `conflict type="device_removed"` (deregister), дочерний `ack` (kick). Дочернего элемента, специфичного для бана, не найдено. `<presence type="unavailable">` и коды закрытия WebSocket не исследовались.

### 8.2 Токены ошибок XMPP (бинарный словарь)

Словарь `AbstractC40911lb` (однобайтовый `A00`, двухбайтовый `A01`). Наличие токенов из прежней таблицы:

| Строка токена | В словаре |
|-------------|---------------|
| `stream:error` | yes |
| `conflict` | yes |
| `not-authorized` | yes |
| `item-not-found` | yes |
| `server-error` | yes |
| `401` | yes |
| `policy-violation` | not found |
| `403` | not found as a token (the `reason` value 403 is read as an int attribute) |

Столбец «Meaning» из прежнего отчёта (например `403` = «Forbidden (ban-related)») был inferred; подкреплено только значение 403 обработкой `<failure>` выше. Также в словаре: `404`, `407`, `failure`, `locked`.

### 8.3 IQ-ответы для ограниченных аккаунтов

Не найдено. Ни пространство имён `urn:ietf:params:xml:ns:xmpp-stanzas`, ни тексты "Account restricted" / "User banned" не существуют в java_src или ресурсах 2.26.41.6, и токенов `forbidden` / `service-unavailable` в словаре нет. XML-примеры из прежнего отчёта не проверены, и полагаться на них не следует (возможно, они иллюстративные). Обработка ошибок по отдельным IQ (например парсеры `item-not-found`, `not-authorized` вроде `K3P`, `C23205A1e`) для ограниченных аккаунтов не прослеживалась.

---

## 9. Полный поток данных (End-to-End)

(Перепроверено в 2.26.41.6: doc_id `28596420510007620`, форма входных данных `query_input`, имена классов выше. Стрелки `isBanned` -> `wfac_ban_state` -> `Main.A5D()` из диаграммы 2.26.26.4 удалены, так как такой связи в коде нет; см. разделы 1 и 2.3.)

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

Found в `C37414GLt`: JSON `variables` запроса содержит `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` и `app_id` (`"dev.app.id"`); открытый текст до шифрования — `{token, debug_info, description}`; метка контекста `"WA_INAPP_BAN_APPEALS"` (info для вывода ключа). Транспорт (found, `AbstractC40195HfH`): обычный POST Facebook Graph на `https://<host>.facebook.com/graphql` с `doc_id` и полем `access_token`, не MEX. `C37414GLt` передаёт `doc_id` **38509456535312323**, когда `hg3.A04.A00()` истинно, иначе **5473316762755318**. Имя операции `submitBanAppeal` не встречается как строка в java_src, smali, assets или res версии 2.26.41.6, и ни один из doc_id нет в каталоге запросов проекта, поэтому имя не проверено. Перед отправкой `C40191HfD` разбирает первый ответ с `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}`, который поставляет ключевой материал для шифрования.

---

## 11. Изменения относительно 2.26.26.4

| Элемент | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| doc_id BizIntegrityQuery | `25975613018777537` | `28596420510007620` (ротирован в 2.26.38.10) |
| Форма запроса | список `$userJids` (реконструировано) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| Класс DTO | `C39833Hhl` | `C51530MtC` (17 полей: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 столбцов | + `is_meta_verified`, `fmx_business_holdout_group`; счётчики REAL |
| Хранилище / менеджер | `BizIntegritySignalsManager.A08/A01` | хранилище `LwI`, схема `C53116Nmn`, менеджер A02 с кэшем в памяти 60 с |
| Читатель start_chat_trust_signals | `C2M7.A0K` | `C57342Yp` |
| Enum trust tier | не зафиксирован, 7 значений | `M5B`, те же 7 значений |
| Пакет UI WFAC | `com.whatsapp.waffle.wfac` (плоский) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| Prefs WFAC | 5 ключей | + `wfac_last_ban_status_fetch_timestamp_ms` (троттлинг обновления 5 с), `support_ban_appeal_user_banned_from_chat_disconnect` очищается при сбросе |
| Разбор состояния бана | 4 состояния | то же; `NO_APPEAL_OPENED` отображается в `CHECKPOINTED` |
| Флаги | 11061/11064/11065/12709/16349/19893/26697/27269/34166 | все present; + 19793 (N5r.A02) |
| Коды SpamWarning 100-106 | да | без изменений |
| integrity_tags | `automation_bulk_messaging`, `spam` | без изменений |
| SpamFlow | 92 категории | 97; добавлены `odml_scam_alert_*`, `biz_spam_banner_block` и другие |
| ML-признаки | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | без изменений, в `integrityai.impl.InputFeatureProviderImpl` |
| Лимит рассылки 20278 | 10000 / 30 дней | без изменений |
| События бана/предупреждений при подключении | «нет XMPP-сигналов бана» | XMPP login `<failure>`: reason 402 (SpamWarning / U13), 403 (перм. бан -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | реагирует на изменение `wfac_ban_state` | исчез; `Main.A5W()` читает состояние при старте (reg state 21) и открывает `WfacBanActivity` через `HBC` |
| Писатели `wfac_ban_state` | не зафиксированы | обработчик запроса статуса бана `C40191HfD`; `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED по источнику запуска); связи с `is_banned` нет |
| Допуск BizIntegrity | «бизнес-аккаунты пропускают проверку» | выбирает SMB-контакты (уровень `smb:`) или `hostStorage == 2` (12709); принудительный путь 16349; разбиения на 975 JID в запросе нет |
| Пакет 975 | пакет GraphQL | локальный фрагмент SQL при подсчёте сообщений (`N54`) |
| Флаг 12709 | серверный whitelist | локальная проверка `hostStorage == 2` |
| Флаг 2923, льготный период 24h по возрасту аккаунта, формирование `dhash` | заявлено | не найдено в 2.26.41.6 |
| Значения `integrity_tags` | `automation_bulk_messaging`, `spam` | эти строки — значения `type` уведомления SMB soft-enforcement, а не `integrity_tags` |
| SMB soft enforcement | тег `business_policy_violation` + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`; ключи сохранённого JSON `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`; флаг 12840 |
| Индексы/число SpamFlow | 92, например `odml_scam_alert_bottom_sheet_block` = 65 | 97 элементов (`C9E2`), те же имена на сдвинутых индексах (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | открывается по 4 условиям данных | информационная панель, открываемая из кнопок карточки FMX / `C512928n` |
| Запрос апелляции | мутация MEX `submitBanAppeal` | Graph `https://<host>.facebook.com/graphql` по doc_id 38509456535312323 / 5473316762755318, перед ним запрос `purpose_public_keys`; имя операции не найдено |
| `wa_biz_integrity_chat_settings` | не найдено | найдено (`AHY`) |
| Токены ошибок XMPP | токены `policy-violation`, `403` | отсутствуют в словаре; `forbidden`/`service-unavailable` и тексты 8.3 отсутствуют |

Всё ещё открыто в 2.26.41.6: названия категорий за `wfac_ban_violation_source` 0/1/2; потребитель флага 20278 и флага 12840; семантика helper `N5r.A01`; содержимое отчётов WaFA; обработка ошибок по отдельным IQ для ограниченных аккаунтов (8.3); отображение возраста аккаунта на карточке FMX; флаг за `C1P2.A01()`.
