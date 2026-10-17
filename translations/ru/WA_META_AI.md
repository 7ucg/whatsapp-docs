<!-- src-sha1: 64389e16d6c478a5b57f43abf9ee01a01474f02f -->
# WhatsApp Meta AI — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** Внутреннее устройство Meta AI — JID, маршрутизация, поля proto, запросы Hatch metadata, отрисовка ответов, почему Baileys не работает, исправление

---

## 1. Что такое Meta AI (технически)

Meta AI — это контакт-бот, адресуемый специальными bot JID (сервер `bot`), с bot-специфичными полями proto в обычных типах сообщений и отдельным каналом JSON-запросов («Hatch metadata»), передаваемым в `ProtocolMessage`. Все утверждения основаны на статическом анализе декомпилированного APK. Уровни: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не выяснено.

Имена в этом отчёте, обфусцированные в 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`), были заново определены по стабильным якорям; под этими именами в 2.26.41.6 их не существует.

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| BotJid | `C24770wv` | Класс JID, сервер `"bot"`, тип 26, числовая строка 1-20 символов, без ведущего 0 |
| Константы bot JID | `AbstractC34361Xw` | Константы и наборы Hatch / Fallback / LID |
| Отображение JID | `AbstractC24760wu` | отображение bot ↔ LID, преобразование целевого JID исходящего сообщения |
| Gating | `C39311it` | gating по feature-флагам для каждого JID (`A0E(Jid)`) |
| Менеджер запросов Hatch | `HF1` (`HatchMetadataRequestManager`) | JSON-запросы, карта ожидающих запросов |
| Построитель proto Hatch | `Hf6` | строит `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | содержит `botMetadata` |
| BotMetadata | `C30615DTj` | bot-метаданные для каждого сообщения |
| Запись профиля бота | `C199348dm` | имя, описание, строка persona ID, миниатюра |

---

## 2. JID Meta AI

### 2.1 JID, найденные в коде

| Константа | Класс | Роль | Уровень |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) через `AbstractC34361Xw.A00` | **Hatch**, основной. Профиль по умолчанию строится в `C223219iv` из payload флага **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) через `AbstractC34361Xw.A01` | Fallback. Управляется флагом 27083 | found |
| `165332417282214` | `C14080dr` (сервер `"lid"`) через `AbstractC34361Xw.A02` | LID-аналог `…698` | found |
| `1807055946647696` | нет | Manus (legacy в 2.26.26.4): в 2.26.41.6 **отсутствует** | found (absent) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), плюс `A01` = `DeviceJid` device 0 | JID bot-сервера, используемый как цель сессии/устройства для «bot envelope» (обработчик запроса синхронизации CoEx v2 `C53148Nnt` шифрует payload синхронизации для своего основного устройства, лог `coexv2 attached bot envelope`), добавляется в наборы устройств получателей (`C12M`) и трактуется как bot-отправитель при обработке retry-receipt (`C33020EaI`). Не персона чата | found (использование); назначение сверх этого inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID встроенной записи профиля «Meta AI» по умолчанию (`C9i5.A00`: имя `Meta AI`, вводный текст по умолчанию). Входит в проверку bot JID `AbstractC24760wu.A07` вместе со следующей строкой | found |
| `867051314767696555` | `AbstractC24760wu.A01` (одноэлементный набор, `C24770wv`) | Второй элемент проверки bot JID `A07` (`A07(jid)` = `C24770wv`, равный `…135992` или входящий в этот набор); `A07` питает `AbstractC199328dk.A00` (предикат класса JID). Дальнейшее назначение не выяснено | found (использование), назначение unknown |
| `17015557208` | `AbstractC24760wu.A04` | Строка пользователя-телефона. `A04(jid)` истинно для LID `165332417282214` или для этого пользователя-телефона; используется с `A03` (любой bot JID `C24770wv`, или PN в диапазонах 13135550000-13135559999 / 13165550000-13165550099) в `E76.A00` (класс 10 vs 1) и в предикате допуска `C736539v.ARO`. Выглядит как PN-идентичность Meta AI; что эти два потребителя с ней делают, не выяснено | found (использование), назначение unknown |

Наборы в `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; карта `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Тип JID: отчёт 2.26.26.4 указывал все четыре как `@s.whatsapp.net`. В 2.26.41.6 bot JID — это `C24770wv` с `getServer() = "bot"`; групповой/LID — `C14080dr` с сервером `"lid"`. Не `s.whatsapp.net` (found).

Таблица номер телефона → bot-FBID: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, около 200 записей, например `13135550002 → 867051314767696`). Используется в `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 Преобразование маршрутизации

```java
// AbstractC24760wu.A01  (getRemoteTargetJidForOutgoingMessage)
if (A08(jid))   // LID jid with user 165332417282214
    return new C24770wv("1807055946647698");
else            // phone jid
    return C0DZ.A08((UserJid) jid);   // PN -> bot JID via AbstractC199338dl table

// AbstractC24760wu.A00
if (jid is bot "1807055946647698") return new C14080dr("165332417282214");  // bot -> LID
if (jid is bot)                      return C0DZ.A07(userJid);              // bot -> phone jid
```

Found: bot JID `…698` ↔ LID `165332417282214`; контакты-боты с номерами телефонов отображаются в bot JID. Метод утверждает "needs FBID migration" (found).

### 2.3 Суффикс `$1`: изменено

Отчёт 2.26.26.4 помещал `$1` на JID маршрутизации («wire format», `C1A2.A00()/A01()`). В 2.26.41.6 не найдено:
- Ни одна функция маршрутизации не добавляет `$1` к JID. Преобразование из 2.2 даёт обычные bot JID.
- `$1` добавляется к строке persona ID, хранящейся в записи профиля бота: `C24121Ab2` делает `personaIdString = botFbid + "$1"`; `C223219iv` жёстко задаёт `"1807055946647697$1"` для профиля Hatch по умолчанию (found).
- Эту строку (`C199348dm.A0A`) `C33473Ehf.A0G` записывает в `BotMetadata.personaId` (found).

Итак, `$1` относится к persona ID, а не к целевому JID.

### 2.4 Определение isMetaAI

```java
// C39311it
boolean A02() {                       // Hatch
  if (!BRD() || capability("ai_hatch_integration_enabled")) return flag(26189);
  return false;
}
boolean A0E(Jid jid) {
  if (jid == HATCH_697)                 return A02();
  if (jid == FALLBACK_698 || jid == LID_165332417282214) {
    if (!BRD() || capability("ai_maiba_wass_migration_receiving_enabled")) return flag(27083);
  }
  return false;
}
```

Ветка Manus (флаг 25119) удалена. Смысл `BRD()` и поиска capability (`C09L.A04`) не выяснен (unknown).

---

## 3. Feature-флаги

| ID флага | Использование в 2.26.41.6 | Уровень |
|---------|------------------|------|
| **25119** | Встречается только в таблицах флагов (`C06510El`, по умолчанию `false` в `C08J`). Читателя не найдено. Старое имя `ai_bot_integration_enabled` как строка не найдено | found |
| **26189** | Gate Hatch в `C39311it.A02()`. По умолчанию `false` (`C08J`) | found |
| **27083** | Gate Fallback / LID в `C39311it.A0E()`. По умолчанию `false` | found |
| **26190** | JSON-конфиг (`name`, `description`, `profile_thumb`) для профиля Hatch по умолчанию, читается в `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Когда истинно, capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) объявляется Hatch (см. 5); `A05` также управляет телеметрией/UI коннектора (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Объявляет `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); также управляет доступностью коннектора (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Объявляет `HATCH_ARTIFACT_CARD_ENABLED` (79); также читается в `HatchSpacesSync` и `C7WL` | found |

Строки `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` не являются именами флагов. Это элементы списка feature-строк, построенного из флагов 26189 / 27083 в `C25056AqU` (рядом с `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` добавляется безусловно. Получатель и назначение списка не проверены.

---

## 4. Поля proto

### 4.1 Message (`C30628DTw`), верхний уровень

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (одно поле `message` = 1) | Исходящее сообщение, обёрнутое для бота; устанавливается в `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Задача бота |
| `botForwardedMessage` | **104** | `BD2` | Оборачивает сообщение с `richResponseMessage`; устанавливается в `F3E` |
| `richResponseMessage` | **97** | `DSY` | Ответ AI. Поля: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Присутствует |
| `botGroupParticipantMessage` | **137** | `BD2` | Присутствует |
| `messageContextInfo` | **35** | `C30624DTs` | Содержит `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Содержит `aiMetadataOperation` (31) |

Поле **77** — это `commentMessage`, а не `richResponseMessage` (в отчёте 2.26.26.4 было 77; для этой сборки неверно, и согласуется с отдельным исследованием richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), не ContextInfo

Отчёт 2.26.26.4 указывал их как поля ContextInfo. В 2.26.41.6 они находятся в `WebMessageInfo`:

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Устанавливается в `C34385EwW` из `C0DZ.A09(userJid)` (пользователь основного устройства вызывающего) |
| `isSupportAiMessage` | **70** | bool | Устанавливается в `C34378EwP.C57`, когда у сообщения установлен бит флага `268435456` и проверка проходит; считывается обратно в `C59`. Вместе с `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Цитаты |
| `botTargetId` | **73** | string | В клиенте нет записи: `botTargetId_` встречается только как значение конструктора по умолчанию и в таблице схемы `C30626DTu`, нигде больше не присваивается (grep по всему исходнику) |
| `agentId` | **47** | string | Присутствует, не анализировалось |

Появляются ли эти поля WebMessageInfo на проводе и как — не проверено (unknown). «`true` для всех сообщений Meta AI» не подтверждено: оно устанавливается по флагу сообщения, а не безусловно.

### 4.3 MessageContextInfo (`C30624DTs`)

| Поле | Номер | Тип |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `personaId` | **2** | string | Из записи профиля бота (`C199348dm.A0A`), например `1807055946647697$1`. Не фиксированное `"meta_ai"` |
| `pluginMetadata` | **3** | `DTL` | Конфиг плагина |
| `invokerJid` | **5** | string | Вызывающий |
| `aiConversationContext` | **20** | bytes | Состояние беседы |
| `botResponseId` | **26** | string | ID ответа |

Другие присутствующие поля (имена из `*_FIELD_NUMBER`, типы не читались): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` заполняется в `C33473Ehf.A0G`; метод досрочно возвращается, если у профиля нет строки persona.

### 4.5 PluginMetadata (`DTL`)

| Поле | Номер | Тип | Значение |
|-------|--------|------|-------|
| `provider` | **1** | int32 | ID провайдера |
| `pluginType` | **2** | enum `C4E0` | См. ниже |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

Константы `C4E0` (значение = порядковый номер в конструкторе; равенство номеру proto — inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Прежние значения 8/9/15 не изменились; enum стал больше.

### 4.6 Action oneof (`C61331Rfl`, enum вариантов `EnumC61601RkN`)

| Номер | Вариант | Уровень |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Это oneof из полей действий, а не простой enum значений. Куда он встраивается, не прослежено (unknown).

### 4.7 Операция AI metadata (носитель Hatch)

| Сообщение | Поле | Номер | Тип |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Протокол запросов (Hatch metadata)

Запросы строятся в `HF1` (`HatchMetadataRequestManager`), класс корутины `HatchMetadataRequestManager$sendRequest$2`. JSON-конверт отличается от 2.26.26.4: `method` и `params` вложены в `payload`.

```json
{
  "version": 1,
  "type": "req",
  "payload": {
    "method": "<method_name>",
    "params": { },
    "accepts_encoding": ["gzip"]
  }
}
```

`params` и `accepts_encoding` необязательны (found). ID запроса не находится в JSON; это `BB2.requestId` (случайная строка из `C20F.A0x()`).

Путь отправки (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Ожидающие запросы: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) и `HF1.A03` (requestId → `GuR`). Обе очищаются в `finally`. Отчёт 2.26.26.4 называл только одну карту `A02`.
- Таймаут: возвращает `GDB.A00` и логирует `HatchMetadataRequestManager/sendRequest timed out method=`.
- Целое `138`, передаваемое в `C37393GKy`, не выяснено (unknown).
- Носитель — `ProtocolMessage.aiMetadataOperation` (поле 31), а не обычное сообщение чата (изменено).
- Пакет `com.whatsapp.bot.infra.message.aimetadata` содержит классы `Ideas*Wire` / `Idea*Wire` (found). Их связь с именами методов только inferred; имена методов не перечислялись.
- Принимающая сторона, завершающая `A04`, не прослежена. Сопоставление ответа с `requestId` inferred по карте `A04` и `BB2.requestId`.

Утверждение **об отсутствии пользовательского XMPP namespace**: обработки `w:ai` / `wa:ai` в прослеженном пути не замечено; основано на отсутствии, исчерпывающе не перепроверено.

**Объявление capability (found, `C33284Eea`):** когда адресат — JID Hatch `…697` (`AbstractC34361Xw.A00`) и gate проходит, клиент строит `DPJ` (одно повторяющееся enum-поле `capabilities` = 1, значения `EnumC32144E2q`), и `C33473Ehf.A06` сохраняет его в `BotMetadata.capabilityMetadata` (13) исходящего сообщения вместе с `BotMetadata.timezone` (8) = ID `TimeZone` устройства. Capability, добавляемые по gate:

| Gate | Capability (номер enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| флаг **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| флаг **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| флаг **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Номера — второй аргумент конструктора enum; равенство номерам proto inferred. Enum также перечисляет capability rich-response (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Примеры запросов (found, ключи `params` прочитаны в местах вызова; цель — JID Hatch `…697`, если место вызова не использует JID беседы):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | строится в `HatchIdeasManager$execute$job$1` (ключи не читались); прикреплён callback `onPart` |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire`, сериализованный в JSON; прикреплён callback `onPart` |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` только когда не пуст) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Форма байтов в `BB2.data` (found форма, примерные значения):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` записывается только когда у вызывающего `acceptsGzipResponse` истинно; `params` — только когда не null. Callback `onPart` регистрируется в `A03` только когда вызывающий его передаёт.

**Сообщение чата боту (found части):**
- Исходящее `Message` переупаковывается в `Message.botInvokeMessage` (`F2K`, `C33284Eea`), обёртка `BD2` держит сообщение в поле 1. В `F2K` обёртка пропускается (сообщение задаётся напрямую), когда `C13S.A00()` ложно, `A10` сообщения ложно или включён флаг **10646** (found).
- `BotMetadata` строится в `C33473Ehf.A0E` / `A0G`. `A0G` ищет запись профиля для целевого bot JID (`C199358dn.A06(userJid)`, строка persona `C199348dm.A0A`); если строка пуста, метод возвращается, не записывая bot-метаданные, иначе устанавливает `personaId` (2) и, если есть, `suggestedPromptMetadata` (4) и дальнейшие подсообщения. Строка persona сохраняется при создании записи профиля (`C24121Ab2` строит `<id>$1`; `C223219iv` жёстко задаёт `1807055946647697$1` для Hatch). Попадает ли `messageContextInfo` во внешний `Message` или в сообщение внутри `botInvokeMessage`, не выяснено.
- `botMessageInvokerJid` / `isSupportAiMessage` устанавливаются в `WebMessageInfo` хуками D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Протокол ответов

### 6.1 Транспорт

Не перепроверено в том виде, как заявлено в 2.26.26.4 («обычные сообщения с байтами `hatchMetadataSync`», класс `Azz`). Found: `hatchMetadataSync` находится в `C25754B9o` внутри `ProtocolMessage.aiMetadataOperation`. Ответы Hatch, по-видимому, приходят тем же путём и сопоставляются по `requestId` (inferred). Запросы Hatch — это вызовы методов; не показано, что это путь обычных ответов чата.

### 6.2 Стриминг / чанки: не подтверждено в описанном виде

Таблица 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) как единый механизм стриминга Meta AI в 2.26.41.6 не подтверждена:

| Поле | Где оно находится в 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` поле **7** (уведомление history-sync, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) и `C25838BCy` поле **5** (history sync) |
| `isLastChunk` | `C55285Ou6` поле **8** (сообщение с `attestationBundles`, `teeModelConfig`, `violationSignal`; связано с TEE) |
| `streamingSidecar` | поле **18** в сообщениях image/video/audio (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | как поля proto не найдены |

Сборки чанков ответов Meta AI не найдено. Что есть для Hatch: `GuR(method, onPart)` — callback `onPart` на каждый запрос (found); что он несёт частичные результаты, inferred по имени.

### 6.3 Rich response (поле 97)

`richResponseMessage` (`DSY`) = поле **97** в `Message`. Классы отрисовки существуют: `AiRichResponseFooterView` и `UnifiedResponseActionHandlerFactory` (пакет `com.whatsapp.conversationrow.botrichresponse`) (found). Цитаты: `WebMessageInfo.supportAiCitations` (72). Типы содержимого (изображения, таблицы, код) здесь не перепроверялись; см. отдельное исследование richResponseMessage.

### 6.4 Индикатор набора

Исходящий (found, `C199098dN.A01`, лог `HandleMeComposing/handleComposing`): стандартное XMPP-состояние чата, в прочитанном коде нет пользовательского namespace.
- Простой случай (бот не упомянут или bot JID разрешён в JID по умолчанию): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Бот упомянут в чате: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Отправляется через `C10140Tq.A0X` с IQ-типом int 4.

Входящий (found, обработчик станзы `C40511kx`): `<chatstate>` с дочерним `composing` (необязательный `media`) вызывает общий callback composing с `from`/`participant`; `paused` вызывает callback paused. Bot-специфичной ветки в этом обработчике не найдено, поэтому `composing` от bot JID идёт тем же путём, что и от любого контакта (inferred; серверная станза набора от бота не наблюдалась). `BotMetadata.progressIndicatorMetadata` (12) и capability `PROGRESS_INDICATOR` существуют как отдельный механизм прогресса внутри сообщения (только имена, не прослежено).

### 6.5 Синхронизация профиля бота

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) планирует `BotProfileForChatListWorker` в `A03()`: запрос WorkManager с тегом `BotProfileSyncManager`, с `setBackoffCriteria(policy, 1, MINUTES)` и ограничением (значение типа не выяснено). 1 минута — это **backoff** повтора, а не период. Утверждение 2.26.26.4 «каждые ~1 минуту» не подтверждено (изменено). `A02(groupJid, userJid)` запрашивает один профиль (`requestBotProfileResult`). Не часть обычной синхронизации ростера (без изменений).

Запись профиля `C199348dm`: тип бота (`C1XY`), jid, отображаемое имя (`A09`), описание (`A07`), строка persona (`A0A`), миниатюры, временная метка.

### 6.6 Строки типов ботов

`C718732k.A00(String)` отображает: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; всё остальное превращается в `AnonymousClass399(str)`. Это метки типов ботов (также используются в фильтрах UI), а не значения `BotMetadata.personaId` (found).

---

## 7. Хранилище

- `MetaAiMemoryStore`: класса с таким именем в 2.26.41.6 нет. Найденный эквивалент — таблица `meta_ai_memory`, создаваемая классом схемы `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, индекс `meta_ai_memory_memory_content_index` по `memory_content`. В каком файле БД она находится, не выяснено. Связанное (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; в названии «deprecated»), SharedPrefs `meta_ai_memory_disclosure_seen` (экран дизайна голосового вызова, `C29434Cpx`), enum capability `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`) и `BotMetadata.memoryMetadata` (15).
- Ключ SharedPrefs `"meta_ai_forward_disclosure_seen"`: присутствует, boolean, читается в `C230589xr.A03` для `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: присутствует в `com.whatsapp.metaai.incognito.infra` (found).
- Отдельное хранение чатов Meta AI вне `msgstore.db` (2.26.26.4, не перепроверено): класса хранилища чатов не найдено; `meta_ai_memory` содержит только факты памяти, поэтому утверждение ни подтверждено, ни опровергнуто.

---

## 8. Почему Baileys не получает ответ

Все строки **inferred**: статическое сравнение требований клиента с путём отправки сторонней библиотеки; живого теста не было.

| Проблема | Основание в 2.26.41.6 | Уровень |
|-------|--------------------|------|
| Неверный тип целевого JID | Bot JID используют сервер `bot` (`C24770wv`), а не `s.whatsapp.net`; боты с номерами телефонов отображаются через таблицу PN→FBID | found (класс JID), inferred (эффект) |
| `$1` на JID маршрутизации | Отсутствует. `$1` находится в строке persona ID | found |
| Нет обёртки `botInvokeMessage` | Клиент оборачивает исходящее `Message` в поле 67 (`F2K`) | found, требование inferred |
| Нет `messageContextInfo.botMetadata` | Клиент записывает в него `personaId`, `invokerJid` и т. д. | found, требование inferred |
| `personaId = "meta_ai"` | Клиент отправляет не это, а строку persona профиля (например `1807055946647697$1`) | found |
| Нет `aiConversationContext` | Поле 20 в `BotMetadata`; поведение на первом ходу unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Поля WebMessageInfo, устанавливаемые хуками клиента; требование сервера unknown | unknown |
| `botTargetId` | В клиентском коде нет записи | found |
| Ответ не разобран | `richResponseMessage` — это поле 97 в `Message` | found |
| Сборка чанков | Не подтверждено данными 2.26.41.6 (см. 6.2) | found |

---

## 9. Исправление для Baileys

Рабочая реализация не заявляется. Далее — структурный набросок того, где располагаются поля согласно 2.26.41.6, помечен как **inferred**; на сервере не запускался.

### 9.1 Цель

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Работает ли строка сервера `bot` как цель relay в Baileys и как сервер выводит итоговый `to` станзы, unknown.

### 9.2 Размещение полей (только форма)

```ts
// inferred shape, field numbers found in 2.26.41.6
const content = {
  botInvokeMessage: {            // Message 67, wrapper with message = 1 (found; wrap is conditional, see 5)
    message: {
      extendedTextMessage: { text }
    }
  },
  // Placement of messageContextInfo (outer Message vs. inner message) is unresolved.
  messageContextInfo: {          // Message 35
    botMetadata: {               // MessageContextInfo 7
      personaId: '1807055946647697$1', // BotMetadata 2: profile persona string (found in C223219iv for Hatch)
      invokerJid: yourJid,             // BotMetadata 5: field exists; writer not read
      timezone: 'Europe/Berlin',       // BotMetadata 8: client sets the TimeZone ID when advertising capabilities (Hatch)
      capabilityMetadata: { capabilities: [/* EnumC32144E2q numbers, Hatch only */] } // BotMetadata 13
      // aiConversationContext (20): field exists; client write not traced, do not invent a value
    }
  }
}
```

- Встраивание `botMetadata` в `messageContextInfo` (поле 7) — **found**. `capabilityMetadata` (13) и `timezone` (8) записываются клиентом только для адресатов Hatch (found); их требование на стороне сервера unknown. Есть ли эти поля уже в proto `baron-baileys-v2`, не проверено; если нет, proto нужно расширить (inferred).
- `isSupportAiMessage` (70) и `botMessageInvokerJid` (58) — поля `WebMessageInfo`. Обязаны ли они присутствовать на проводе, unknown; не помещайте их в `contextInfo` (в отчёте 2.26.26.4 это было неверно).
- `botTargetId`: нигде в декомпилированном коде нет записи клиента (found); не устанавливайте его.
- Точная обёртка (`botInvokeMessage.message`, содержащий настоящее сообщение, vs. рядом) следует переупаковке `F2K` / `C33284Eea`; точный сериализованный результат не воспроизводился (unknown).

### 9.3 Обработка ответов

- Rich-ответы: `Message.richResponseMessage` — поле **97** (found). Разбирайте его, а не поле 77.
- Уберите обработку чанков: `chunkOrder` / `isLastChunk` не являются полями стриминга Meta AI (6.2).
- Hatch `ProtocolMessage.aiMetadataOperation` (31) — канал JSON-запросов; не показано, что обычные ответы чата используют его.

### 9.4 Контекст беседы

`BotMetadata.aiConversationContext` (20) существует. Что сервер возвращает обновлённое состояние в ответах и что его нужно отправлять обратно — **inferred** (по имени поля и отчёту 2.26.26.4); не проверено.

---

## 10. Потоки

### 10.1 Сообщение чата боту (found на стороне клиента, inferred на стороне сервера)

```
[Client] outgoing Message
    │  F2K / C33284Eea: Message.botInvokeMessage = BD2{ message = original }
    │  C33473Ehf: messageContextInfo.botMetadata{ personaId = profile.A0A, ... }
    │  D36 hooks: WebMessageInfo.botMessageInvokerJid (58), isSupportAiMessage (70)
    ▼
[Routing] AbstractC24760wu.A01: LID 165332417282214 → bot 1807055946647698
    │  phone JID → bot JID via PN→FBID table
    ▼
[WA Server] (not observed; inferred) → Meta AI backend
    ▼
[Client] incoming Message.richResponseMessage (97)  →  AiRichResponseFooterView / UnifiedResponseActionHandlerFactory
```

### 10.2 Запрос Hatch metadata (found на стороне клиента)

```
[Feature code] HF1.A01(jid, method, params)
    │  requestId = random; A03[requestId] = GuR(method, onPart); A04[requestId] = continuation
    ▼
JSON {"version":1,"type":"req","payload":{"method","params","accepts_encoding"}} → bytes
    ▼
Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
    ▼
[WA Server] (not observed)
    ▼
Response: matched by requestId (inferred) → continuation resumes; timeout → GDB.A00
```

---

## 11. Изменения относительно 2.26.26.4

| Элемент | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, флаг 25119 | Отсутствует. 25119 только в таблицах флагов, читателя нет |
| JID 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 — сервер `bot` (`C24770wv`); 165332417282214 — `lid` (`C14080dr`) |
| Новые константы JID | не перечислены | `1807055946647699` (цель bot-envelope CoEx v2 / набора устройств), `2942131436135992` (JID профиля Meta AI по умолчанию, проверка bot JID `A07`), `867051314767696555` (второй элемент `A07`, назначение unknown), `17015557208` (PN Meta AI, `A04`) |
| Суффикс `$1` | На JID маршрутизации, `C1A2.A00/A01` | Не на JID; добавляется к строке persona ID (`C24121Ab2`, `C223219iv`) |
| Преобразование маршрутизации | добавление `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot через таблицу FBID |
| Имена флагов 25119/26189/27083 | имена флагов `ai_*` | Строки — элементы списка feature-строк (`C25056AqU`); 26190 = JSON профиля Hatch; 37227/37852/37054 управляют значениями capability Hatch 76 / 77 / 79 |
| `richResponseMessage` | Поле 77 | Поле 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 в "WebMessageInfo" | 67 / 100 / 104 в `Message`; также 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` никогда не записывается |
| Расположение BotMetadata | «встроено в сообщение» | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Строка persona профиля, например `1807055946647697$1`; `meta_ai` — метка типа бота |
| Типы плагинов | 8, 9, 15 | Те же, в enum 18 значений (до 17) |
| Enum действий | Enum значений 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| JSON-конверт Hatch | `method`, `params` на верхнем уровне | Вложены в `payload`; добавлен `accepts_encoding` |
| Носитель Hatch | Стандартное сообщение, класс `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; добавлен `bizAiMetadataSync` (2) |
| Карты ожидающих запросов | Одна (`A02`) | Две: `A04` continuation, `A03` callbacks частей `GuR` |
| Поля стриминга | Одна таблица чанков Meta AI | `chunkOrder` (history sync), `isLastChunk` (сообщение TEE), `streamingSidecar` (медиа); `clientStreaming`/`serverStreaming` не найдены |
| Интервал синхронизации профиля | «каждые ~1 мин» | 1 мин — backoff WorkManager, а не период |
| `MetaAiMemoryStore` | Присутствует | По имени не найден; найдена таблица `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Присутствуют | Присутствуют |
| Индикатор набора (chatstates) | Найдено | Найдено: исходящий `<chatstate><composing/></chatstate>`, с `<bot jid/>` при упоминании бота (`C199098dN.A01`); входящие `composing`/`paused` через общий обработчик `C40511kx`, bot-специфичной ветки нет |
| Объявление capability | не документировано | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) для Hatch; флаги 37227 / 37852 / 37054 соответствуют значениям enum 76 / 77 / 79 |
| Примеры запросов Hatch | не документированы | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
