<!-- src-sha1: 4a0b884541f4221f33fe16d1a5659612eb6bac89 -->
# WhatsApp Meta AI — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** внутреннее устройство Meta AI — JID, маршрутизация, поля proto, запросы Hatch metadata, рендеринг ответов, почему Baileys не работает, исправление

---

## 1. Что такое Meta AI (технически)

Meta AI — это бот-контакт, адресуемый специальными bot JID (сервер `bot`), с bot-специфичными полями proto в обычных типах сообщений и отдельным JSON-каналом запросов ("Hatch metadata"), переносимым внутри `ProtocolMessage`. Все утверждения — статический анализ декомпилированного APK. Уровень достоверности: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не установлено.

Имена в этом отчёте, обфусцированные в 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`), были повторно разрешены по стабильным опорным точкам; под этими именами они не существуют в 2.26.41.6.

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| BotJid | `C24770wv` | класс JID, сервер `"bot"`, тип 26, числовая строка 1-20 символов, без ведущего 0 |
| Константы bot JID | `AbstractC34361Xw` | константы и наборы Hatch / Fallback / LID |
| Отображение JID | `AbstractC24760wu` | отображение bot ↔ LID, конвертация исходящего целевого адреса |
| Гейтинг | `C39311it` | гейтинг по feature-флагу для конкретного JID (`A0E(Jid)`) |
| Менеджер запросов Hatch | `HF1` (`HatchMetadataRequestManager`) | JSON-запросы, карта ожидающих |
| Построитель proto Hatch | `Hf6` | строит `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | хранит `botMetadata` |
| BotMetadata | `C30615DTj` | метаданные бота для конкретного сообщения |
| Запись профиля бота | `C199348dm` | имя, описание, строка ID персоны, миниатюра |

---

## 2. JID Meta AI

### 2.1 JID, найденные в коде

| Константа | Класс | Роль | Уровень |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) через `AbstractC34361Xw.A00` | **Hatch**, основной. Профиль по умолчанию строится в `C223219iv` из данных флага **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) через `AbstractC34361Xw.A01` | Fallback. Гейт флагом 27083 | found |
| `165332417282214` | `C14080dr` (сервер `"lid"`) через `AbstractC34361Xw.A02` | LID-эквивалент `…698` | found |
| `1807055946647696` | нет | Manus (legacy в 2.26.26.4): **отсутствует** в 2.26.41.6 | found (отсутствие) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), плюс `A01` = `DeviceJid` устройство 0 | JID bot-сервера, используемый как цель сессии/устройства для "bot envelope" (обработчик запроса синхронизации CoEx v2 `C53148Nnt` шифрует payload синхронизации на своё основное устройство, лог `coexv2 attached bot envelope`), добавляется в наборы устройств получателя (`C12M`), и обрабатывается как bot-отправитель в обработке retry-receipt (`C33020EaI`). Не чат-персона | found (использование); назначение сверх этого — inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID встроенной записи профиля "Meta AI" по умолчанию (`C9i5.A00`: имя `Meta AI`, стандартный текст вступления). Член проверки bot-JID `AbstractC24760wu.A07` вместе со следующей строкой | found |
| `867051314767696555` | `AbstractC24760wu.A01` (синглтон-набор, `C24770wv`) | Второй член проверки `A07` для bot-JID (`A07(jid)` = `C24770wv`, равный `…135992` или входящий в этот набор); `A07` подаётся в `AbstractC199328dk.A00` (предикат класса JID). Дальнейшее назначение не установлено | found (использование), назначение неизвестно |
| `17015557208` | `AbstractC24760wu.A04` | строка пользователя-телефона. `A04(jid)` истинно для LID `165332417282214` либо для этого пользователя-телефона; используется вместе с `A03` (любой bot JID `C24770wv`, или PN в диапазонах 13135550000-13135559999 / 13165550000-13165550099) в `E76.A00` (класс 10 против 1) и в предикате пригодности `C736539v.ARO`. Выглядит как PN-идентичность Meta AI; что делают с ней эти два потребителя — не установлено | found (использование), назначение неизвестно |

Наборы в `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; карта `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Тип JID: отчёт по 2.26.26.4 указывал все четыре как `@s.whatsapp.net`. В 2.26.41.6 bot JID — это `C24770wv` с `getServer() = "bot"`; групповой/LID JID — `C14080dr` с сервером `"lid"`. Не `s.whatsapp.net` (found).

Таблица номер телефона → bot-FBID: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, около 200 записей, например `13135550002 → 867051314767696`). Используется `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 Конвертация маршрутизации

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

Найдено: bot JID `…698` ↔ LID `165332417282214`; bot-контакты с номером телефона отображаются на bot JID. Метод сопровождается ассертом "needs FBID migration" (found).

### 2.3 Суффикс `$1`: изменился

Отчёт по 2.26.26.4 помещал `$1` на маршрутизирующий JID ("wire format", `C1A2.A00()/A01()`). В 2.26.41.6 не найдено:
- Ни одна функция маршрутизации не добавляет `$1` к JID. Конвертация из раздела 2.2 даёт обычные bot JID.
- `$1` добавляется к строке ID персоны, хранящейся в записи профиля бота: `C24121Ab2` делает `personaIdString = botFbid + "$1"`; `C223219iv` хардкодит `"1807055946647697$1"` для профиля Hatch по умолчанию (found).
- Именно эту строку (`C199348dm.A0A`) `C33473Ehf.A0G` записывает в `BotMetadata.personaId` (found).

Таким образом `$1` принадлежит ID персоны, а не целевому JID.

### 2.4 Детекция isMetaAI

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

Ветка Manus (флаг 25119) отсутствует. Смысл `BRD()` и поиска capability (`C09L.A04`) не установлен (unknown).

---

## 3. Feature-флаги

| ID флага | Использование в 2.26.41.6 | Уровень |
|---------|------------------|------|
| **25119** | Встречается только в таблицах флагов (`C06510El`, по умолчанию `false` в `C08J`). Читатель не найден. Старое имя `ai_bot_integration_enabled` не найдено как строка | found |
| **26189** | Гейт Hatch в `C39311it.A02()`. По умолчанию `false` (`C08J`) | found |
| **27083** | Гейт Fallback / LID в `C39311it.A0E()`. По умолчанию `false` | found |
| **26190** | JSON-конфиг (`name`, `description`, `profile_thumb`) для профиля Hatch по умолчанию, читается в `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Когда истинно, capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) заявляется для Hatch (см. раздел 5); `A05` также гейтит connector-телеметрию/UI (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Заявляет `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); также гейтит доступность connector (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Заявляет `HATCH_ARTIFACT_CARD_ENABLED` (79); также читается `HatchSpacesSync` и `C7WL` | found |

Строки `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` — не имена флагов. Это элементы списка feature-строк, построенного из флагов 26189 / 27083 в `C25056AqU` (наряду с `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` добавляется безусловно. Получатель и назначение списка не подтверждены.

---

## 4. Поля proto

### 4.1 Message (`C30628DTw`), верхний уровень

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (единственное поле `message` = 1) | исходящее сообщение, обёрнутое для бота; задаётся в `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | задача бота |
| `botForwardedMessage` | **104** | `BD2` | оборачивает сообщение, содержащее `richResponseMessage`; задаётся в `F3E` |
| `richResponseMessage` | **97** | `DSY` | ответ AI. Поля: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | присутствует |
| `botGroupParticipantMessage` | **137** | `BD2` | присутствует |
| `messageContextInfo` | **35** | `C30624DTs` | содержит `botMetadata` |
| `protocolMessage` | **12** | `BD3` | содержит `aiMetadataOperation` (31) |

Поле **77** — это `commentMessage`, а не `richResponseMessage` (в отчёте по 2.26.26.4 было 77; для этой сборки неверно, что согласуется с отдельным исследованием richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), не ContextInfo

Отчёт по 2.26.26.4 перечислял их как поля ContextInfo. В 2.26.41.6 они находятся на `WebMessageInfo`:

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | задаётся в `C34385EwW` из `C0DZ.A09(userJid)` (пользователь основного устройства инициатора) |
| `isSupportAiMessage` | **70** | bool | задаётся в `C34378EwP.C57`, когда у сообщения установлен бит флага `268435456` и проверка проходит; считывается обратно в `C59`. Совместно с `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | цитаты |
| `botTargetId` | **73** | string | в клиенте нет writer-а: `botTargetId_` встречается только как значение по умолчанию в конструкторе и в таблице схемы `C30626DTu`, больше нигде не присваивается (grep по всему исходнику) |
| `agentId` | **47** | string | присутствует, не анализировалось |

Появляются ли эти поля WebMessageInfo на проводе и как — не подтверждено (unknown). Утверждение "`true` для всех сообщений Meta AI" не подтверждается: поле устанавливается в зависимости от флага конкретного сообщения, а не безусловно.

### 4.3 MessageContextInfo (`C30624DTs`)

| Поле | Номер | Тип |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `personaId` | **2** | string | из записи профиля бота (`C199348dm.A0A`), например `1807055946647697$1`. Не фиксированное `"meta_ai"` |
| `pluginMetadata` | **3** | `DTL` | конфигурация плагина |
| `invokerJid` | **5** | string | инициатор |
| `aiConversationContext` | **20** | bytes | состояние диалога |
| `botResponseId` | **26** | string | ID ответа |

Прочие присутствующие поля (имена из `*_FIELD_NUMBER`, типы не прочитаны): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` заполняется в `C33473Ehf.A0G`; метод возвращается раньше срока, если у профиля нет строки персоны.

### 4.5 PluginMetadata (`DTL`)

| Поле | Номер | Тип | Значение |
|-------|--------|------|-------|
| `provider` | **1** | int32 | ID провайдера |
| `pluginType` | **2** | enum `C4E0` | см. ниже |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

Константы `C4E0` (значение = порядковый номер конструктора; равенство номеру proto — inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Старые значения 8/9/15 не изменились; перечисление стало больше.

### 4.6 oneof Action (`C61331Rfl`, enum вариантов `EnumC61601RkN`)

| Номер | Вариант | Уровень |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Это oneof полей действия, а не простое перечисление значений. Где оно встроено — не прослежено (unknown).

### 4.7 AI metadata operation (носитель Hatch)

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

Запросы строятся `HF1` (`HatchMetadataRequestManager`), класс корутины `HatchMetadataRequestManager$sendRequest$2`. JSON-конверт отличается от 2.26.26.4: `method` и `params` вложены в `payload`.

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

`params` и `accepts_encoding` опциональны (found). ID запроса не находится в JSON; это `BB2.requestId` (случайная строка из `C20F.A0x()`).

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

- Ожидающие запросы: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) и `HF1.A03` (requestId → `GuR`). Обе очищаются в `finally`. Отчёт по 2.26.26.4 называл только одну карту `A02`.
- Таймаут: возвращает `GDB.A00` и логирует `HatchMetadataRequestManager/sendRequest timed out method=`.
- Целое число `138`, передаваемое в `C37393GKy`, не установлено (unknown).
- Носитель — `ProtocolMessage.aiMetadataOperation` (поле 31), а не обычное чат-сообщение (изменилось).
- Пакет `com.whatsapp.bot.infra.message.aimetadata` содержит классы `Ideas*Wire` / `Idea*Wire` (found). Их связь с именами методов — только inferred; имена методов не перечислялись исчерпывающе.
- Сторона получения, которая завершает `A04`, не была прослежена. Сопоставление ответа с `requestId` выводится (inferred) из карты `A04` и `BB2.requestId`.

Утверждение об **отсутствии кастомного пространства имён XMPP**: в прослеженном пути не встречено обработки `w:ai` / `wa:ai`; основано на отсутствии, не проверено исчерпывающе.

**Заявление возможностей (found, `C33284Eea`):** когда цель — Hatch JID `…697` (`AbstractC34361Xw.A00`) и гейт проходит, клиент строит `DPJ` (единственное repeated-поле `capabilities` = 1, значения `EnumC32144E2q`), и `C33473Ehf.A06` сохраняет его в `BotMetadata.capabilityMetadata` (13) исходящего сообщения, вместе с `BotMetadata.timezone` (8) = ID `TimeZone` устройства. Возможности, добавляемые по гейтам:

| Гейт | Возможность (номер enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| флаг **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| флаг **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| флаг **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Номера — это второй аргумент конструктора enum; их равенство номерам proto — inferred. Перечисление также содержит возможности rich-response (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Примеры запросов (found, ключи `params` прочитаны в местах вызова; цель — Hatch JID `…697`, если место вызова не использует JID беседы):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | строится в `HatchIdeasManager$execute$job$1` (ключи не прочитаны); прикреплён callback `onPart` |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire`, сериализованный в JSON; прикреплён callback `onPart` |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` только когда непусто) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Форма байтов в `BB2.data` (найденная форма, примерные значения):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` записывается только когда у вызывающего `acceptsGzipResponse` истинно; `params` — только когда не null. Callback `onPart` регистрируется в `A03` только если вызывающий его передал.

**Чат-сообщение боту (найденные части):**
- Исходящий `Message` переоборачивается в `Message.botInvokeMessage` (`F2K`, `C33284Eea`), обёртка `BD2` держит сообщение в поле 1. В `F2K` оборачивание пропускается (сообщение устанавливается напрямую), когда `C13S.A00()` ложно, `A10` сообщения ложно, либо включён флаг **10646** (found).
- `BotMetadata` строится `C33473Ehf.A0E` / `A0G`. `A0G` ищет запись профиля для целевого bot JID (`C199358dn.A06(userJid)`, строка персоны `C199348dm.A0A`); если эта строка пуста, метод возвращается без записи bot-метаданных, иначе устанавливает `personaId` (2) и, если присутствует, `suggestedPromptMetadata` (4) и дальнейшие подсообщения. Строка персоны сохраняется при создании записи профиля (`C24121Ab2` строит `<id>$1`; `C223219iv` хардкодит `1807055946647697$1` для Hatch). Попадает ли `messageContextInfo` на внешний `Message` или на сообщение внутри `botInvokeMessage` — не установлено.
- `botMessageInvokerJid` / `isSupportAiMessage` устанавливаются на `WebMessageInfo` хуками D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Протокол ответа

### 6.1 Транспорт

Не подтверждено повторно, как заявлено в 2.26.26.4 ("обычные сообщения с байтами `hatchMetadataSync`", класс `Azz`). Найдено: `hatchMetadataSync` находится в `C25754B9o` внутри `ProtocolMessage.aiMetadataOperation`. Предположительно ответы Hatch приходят тем же путём и сопоставляются по `requestId` (inferred). Запросы Hatch — это вызовы методов; не показано, что это путь обычных чат-ответов.

### 6.2 Стриминг / чанки: не поддерживается в описанном виде

Таблица из 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) как единый механизм стриминга Meta AI не поддерживается в 2.26.41.6:

| Поле | Где находится в 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` поле **7** (уведомление о синхронизации истории, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) и `C25838BCy` поле **5** (синхронизация истории) |
| `isLastChunk` | `C55285Ou6` поле **8** (сообщение с `attestationBundles`, `teeModelConfig`, `violationSignal`; относится к TEE) |
| `streamingSidecar` | поле **18** на сообщениях изображение/видео/аудио (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | не найдены как поля proto |

Повторная сборка чанков ответов Meta AI не найдена. Что есть для Hatch: `GuR(method, onPart)` — callback `onPart` на запрос (found); что он несёт частичные результаты — выводится из названия (inferred).

### 6.3 Rich response (поле 97)

`richResponseMessage` (`DSY`) = поле **97** в `Message`. Классы рендеринга существуют: `AiRichResponseFooterView` и `UnifiedResponseActionHandlerFactory` (пакет `com.whatsapp.conversationrow.botrichresponse`) (found). Цитаты: `WebMessageInfo.supportAiCitations` (72). Типы контента (изображения, таблицы, код) здесь не проверялись повторно; см. отдельное исследование richResponseMessage.

### 6.4 Индикатор набора текста

Исходящий (found, `C199098dN.A01`, лог `HandleMeComposing/handleComposing`): стандартное chat state XMPP, кастомного пространства имён в прочитанном коде нет.
- Обычный случай (нет упомянутого бота, либо bot JID разрешился в стандартный): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Бот упомянут в чате: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Отправляется через `C10140Tq.A0X` с типом IQ int 4.

Входящий (found, обработчик станзы `C40511kx`): `<chatstate>` с дочерним `composing` (опционально `media`) вызывает общий callback composing с `from`/`participant`; `paused` вызывает callback paused. В этом обработчике не найдено bot-специфичной ветки, поэтому `composing` от bot-JID идёт тем же путём, что и от любого контакта (inferred; серверная станза набора текста бота не наблюдалась). `BotMetadata.progressIndicatorMetadata` (12) и возможность `PROGRESS_INDICATOR` существуют как отдельный механизм прогресса внутри сообщения (только названия, не прослежено).

### 6.5 Синхронизация профиля бота

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) планирует `BotProfileForChatListWorker` в `A03()`: запрос WorkManager с тегом `BotProfileSyncManager` и `setBackoffCriteria(policy, 1, MINUTES)` плюс ограничение (значение типа не установлено). 1 минута — это **backoff** повтора, а не период. Заявление "каждую ~1 минуту" из 2.26.26.4 не подтверждается (изменилось). `A02(groupJid, userJid)` запрашивает один профиль (`requestBotProfileResult`). Не часть обычной синхронизации ростера (без изменений).

Запись профиля `C199348dm`: тип бота (`C1XY`), jid, отображаемое имя (`A09`), описание (`A07`), строка персоны (`A0A`), миниатюры, временная метка.

### 6.6 Строки типов бота

`C718732k.A00(String)` отображает: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; всё остальное становится `AnonymousClass399(str)`. Это метки типов бота (также используются в UI-фильтрах), а не значения `BotMetadata.personaId` (found).

---

## 7. Хранение

- `MetaAiMemoryStore`: класса с таким именем в 2.26.41.6 нет. Найденный эквивалент — таблица `meta_ai_memory`, создаваемая классом схемы `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, индекс `meta_ai_memory_memory_content_index` на `memory_content`. Какой файл базы данных её хранит — не установлено. Связанное (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; название говорит "deprecated"), SharedPrefs `meta_ai_memory_disclosure_seen` (экран дизайна голосового звонка, `C29434Cpx`), перечисления возможностей `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), и `BotMetadata.memoryMetadata` (15).
- Ключ SharedPrefs `"meta_ai_forward_disclosure_seen"`: присутствует, boolean, читается в `C230589xr.A03` для `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: присутствует в `com.whatsapp.metaai.incognito.infra` (found).
- Отдельное хранение чатов Meta AI вне `msgstore.db` (2.26.26.4, не проверено повторно): класс хранилища чатов не найден; `meta_ai_memory` хранит только факты памяти, поэтому утверждение ни подтверждается, ни опровергается.

---

## 8. Почему Baileys не получает ответ

Все строки — **inferred**: статическое сравнение требований клиента со сторонним путём отправки; без живого теста.

| Проблема | Основание в 2.26.41.6 | Уровень |
|-------|--------------------|------|
| Неверный тип целевого JID | Bot JID используют сервер `bot` (`C24770wv`), не `s.whatsapp.net`; боты с номером телефона отображаются через таблицу PN→FBID | found (класс JID), inferred (эффект) |
| `$1` на маршрутизирующем JID | Отсутствует. `$1` находится на строке ID персоны | found |
| Отсутствует обёртка `botInvokeMessage` | Клиент оборачивает исходящий `Message` в поле 67 (`F2K`) | found, требование — inferred |
| Отсутствует `messageContextInfo.botMetadata` | Клиент записывает в него `personaId`, `invokerJid` и т.д. | found, требование — inferred |
| `personaId = "meta_ai"` | Не то, что отправляет клиент; он отправляет строку персоны профиля (например, `1807055946647697$1`) | found |
| Отсутствует `aiConversationContext` | Поле 20 `BotMetadata`; поведение на первом шаге неизвестно | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Поля WebMessageInfo, устанавливаемые хуками клиента; требование сервера неизвестно | unknown |
| `botTargetId` | В коде клиента нет writer-а | found |
| Ответ не разбирается | `richResponseMessage` — это поле 97 `Message` | found |
| Сборка чанков | Не поддерживается по данным 2.26.41.6 (см. 6.2) | found |

---

## 9. Проверка подписи бота (аутентичность контента)

Отдельно от всего вышеперечисленного: механизм, позволяющий **принимающему** клиенту проверить, что содержимое `richResponseMessage` действительно пришло от AI-backend Meta, независимо от того, кто ретранслировал сообщение. Статические находки ниже — `found` в коде 2.26.41.6; результат реплея в 9.4 — `tested` (живой, на собственном аккаунте автора — не перехват трафика, а легитимный клиент, составляющий и ретранслирующий своё собственное сообщение).

### 9.1 Расположение в proto

`BotMetadata.verificationMetadata` — поле **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), тип `DPC`/`BotSignatureVerificationMetadata` (настоящее имя раскрывается toString): `proofs[]`, каждый — `BotSignatureVerificationUseCaseProof` с `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (repeated bytes, DER X.509).

### 9.2 Алгоритм проверки

Класс `C33259EeB`, внутреннее имя `BotSignatureVerificationUtils` (из строк лога):

1. **Валидация цепочки сертификатов** `certificateChain` относительно корня доверия, через `HFg.A01(date, certs, true)`.
2. **Построение подписываемых байтов**: `"1" + <строка номера телефона> + <байты unifiedResponse>` — подпись связывает **контент и номер телефона вместе**, а не только контент.
3. **Проверка EdDSA** (лог: `"EdDSA signature verification result"`), используя сырой ключ Ed25519, извлечённый из SubjectPublicKeyInfo листового сертификата.
4. **Режим применения**, читается из конфига **19590**, enum `EnumC32057Dzg`: `NONE` (`"none"`, выключено, всегда проходит), `LOG_ONLY` (`"log_only"`, проверяет + логирует, никогда не блокирует), `ENFORCE_BLOCKING` (`"enforce_blocking"`, неудачная проверка возвращает `false`). Результат хранится как `E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, сохраняется в столбце SQLite `bot_message_info.signature_validation_status` (в таблице также есть `bot_client_public_key`).

### 9.3 Гейт рендеринга строки

`C30085D6v.A00` (диспетчер типа строки) и `EOK`/`C32608EKo`: если статус подписи `FAILED` и включён флаг **27635** → замаскированная строка `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Независимо от этого, если JID отправителя отсутствует в локально синхронизированном хранилище bot-профилей (`C224899mg`, та же синхронизация, что и `BotProfileSyncManagerImpl`) и включён флаг **27355** → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), превью с согласием, а не жёсткая блокировка.

### 9.4 Реальный захват и живой реплей (tested)

Настоящий ответ Meta AI, захваченный на стороне клиента в реальной беседе (собственный аккаунт, расшифрован собственным клиентом автора — не перехват трафика), содержал:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, `signature` размером 64 байта (размер Ed25519), `certificateChain` из 2 записей.
- Листовой сертификат: `CN=svc:wa-bot-msg-leaf`, ключ Ed25519, выпущен `Meta WA SS Int CA 2025-09`, цепочка к `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`), срок действия ≈7 месяцев (автоматически обновляемый служебный сертификат) — закрытый подписывающий ключ существует только в backend Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — имя bot-backend, ранее не документированное (см. также "Hatch" в разделах 1-6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, соседнее поле с `botMetadata`.
- Форма доставки: `protocolMessage` с `type: MESSAGE_EDIT`, `editedMessage.richResponseMessage` (первый ответ в теме приходит заранее обёрнутым как правка заглушки), `key.remoteJid` = собственный JID автора.

**Тест:** точно тот же `richResponseMessage` + `messageContextInfo.botMetadata` (подпись и цепочка сертификатов побайтово неизменны) был переретранслирован через `relayMessage` с собственного устройства автора — не с bot JID `867051314767696@bot` — на собственный номер автора (тот же номер, что уже встроен в подписанные байты).

**Результат:** контент отрендерился с полным "AI"-оформлением и настоящим текстом, с меткой "Forwarded". В некоторых доставках того же самого payload вместо этого показывалось "WhatsApp can't verify the security of this media. Only download if you trust the sender." с действием Download; нажатие Download раскрывало тот же контент, что соответствует статусу `DOWNLOAD_CONSENT_ACCEPTED` и пути кода "unknown sender with unconsented content" из 9.3. Одна доставка показала общий фолбэк "ваша версия WhatsApp не поддерживает это" вместо этого; причина не установлена (unknown).

**Вывод (tested):** криптографическая проверка из 9.2 связывает *(контент, номер телефона)*, а не живую идентичность или JID отправителя. Валидно подписанный `richResponseMessage` можно повторно отправить от отправителя, не являющегося ботом, и он всё равно пройдёт проверку подписи — при условии, что номер получателя совпадает с номером, заложенным в подпись; принимающий клиент рендерит это как настоящий AI-контент (максимум с гейтингом в виде одного косметического шага согласия "unknown sender", а не жёсткой блокировки). Это механизм аутентичности контента, а не аутентичности отправителя; именно собственное шифрование WhatsApp на уровне Signal, а не эта подпись, аутентифицирует живого отправителя.

---

## 10. Исправление для Baileys

Рабочая реализация не заявляется. Далее — структурный набросок того, где находятся поля по данным 2.26.41.6, помеченный как **inferred**; против сервера не проверялось.

### 9.1 Цель

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Работает ли строка сервера `bot` как целевой адрес реле Baileys и как сервер выводит итоговый `to` станзы — неизвестно.

### 9.2 Расположение полей (только форма)

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

- Вложение `botMetadata` в `messageContextInfo` (поле 7) — **found**. `capabilityMetadata` (13) и `timezone` (8) записываются клиентом только для целей Hatch (found); их требование на стороне сервера неизвестно. Не проверено, есть ли эти поля уже в proto `baron-baileys-v2`; если нет, proto нужно расширить (inferred).
- `isSupportAiMessage` (70) и `botMessageInvokerJid` (58) — это поля `WebMessageInfo`. Должны ли они присутствовать на проводе — неизвестно; не помещайте их в `contextInfo` (это было ошибкой в отчёте 2.26.26.4).
- `botTargetId`: в декомпилированном коде нигде нет writer-а клиента (found); не устанавливайте его.
- Точное оборачивание (`botInvokeMessage.message`, содержащее настоящее сообщение, против альтернативы) следует за переоборачиванием `F2K` / `C33284Eea`; точный сериализованный результат не воспроизведён (unknown).

### 9.3 Обработка ответа

- Rich-ответы: `Message.richResponseMessage` — это поле **97** (found). Разбирайте его, а не поле 77.
- Удалите обработку чанков: `chunkOrder` / `isLastChunk` не являются полями стриминга Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) Hatch — это канал JSON-запросов; не показано, что обычные чат-ответы используют его.

### 9.4 Контекст беседы

`BotMetadata.aiConversationContext` (20) существует. То, что сервер возвращает обновлённое состояние в ответах и что его нужно отправлять обратно, — это **inferred** (из имени поля и отчёта 2.26.26.4); не подтверждено.

---

## 11. Потоки

### 10.1 Чат-сообщение боту (найдено на стороне клиента, inferred на стороне сервера)

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

### 10.2 Запрос Hatch metadata (найдено на стороне клиента)

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

## 12. Изменения относительно 2.26.26.4

| Элемент | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, флаг 25119 | Отсутствует. 25119 только в таблицах флагов, читателя нет |
| JID 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 — сервер `bot` (`C24770wv`); 165332417282214 — `lid` (`C14080dr`) |
| Новые константы JID | не перечислены | `1807055946647699` (цель CoEx v2 bot-envelope / набора устройств), `2942131436135992` (JID профиля Meta AI по умолчанию, проверка bot-JID `A07`), `867051314767696555` (второй член `A07`, назначение неизвестно), `17015557208` (PN Meta AI, `A04`) |
| Суффикс `$1` | На маршрутизирующем JID, `C1A2.A00/A01` | Не на JID; добавлен к строке ID персоны (`C24121Ab2`, `C223219iv`) |
| Конвертация маршрутизации | добавление `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot через таблицу FBID |
| Имена флагов 25119/26189/27083 | имена флагов `ai_*` | Строки — элементы feature-списка (`C25056AqU`); 26190 = JSON-профиль Hatch; 37227/37852/37054 гейтят значения возможностей Hatch 76 / 77 / 79 |
| `richResponseMessage` | Поле 77 | Поле 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 на "WebMessageInfo" | 67 / 100 / 104 на `Message`; также 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` никогда не записывается |
| Расположение BotMetadata | "встроено в сообщение" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Строка персоны профиля, например `1807055946647697$1`; `meta_ai` — метка типа бота |
| Типы плагинов | 8, 9, 15 | Те же, перечисление содержит 18 значений (до 17) |
| Enum Action | Value enum 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| JSON-конверт Hatch | `method`, `params` на верхнем уровне | Вложены в `payload`; добавлено `accepts_encoding` |
| Носитель Hatch | Обычное сообщение, класс `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; добавлено `bizAiMetadataSync` (2) |
| Проверка подписи бота | не документировано | Новое: `BotMetadata.verificationMetadata` (27), EdDSA + цепочка сертификатов X.509 над (контент, номер телефона); проверено живым тестом, связывает с номером телефона, а не с живым отправителем (раздел 9) |
| Карты ожидающих | Одна (`A02`) | Две: `A04` continuations, `A03` callback-и `GuR` |
| Поля стриминга | Одна таблица чанков Meta AI | `chunkOrder` (синхронизация истории), `isLastChunk` (сообщение TEE), `streamingSidecar` (медиа); `clientStreaming`/`serverStreaming` не найдены |
| Интервал синхронизации профиля | "каждую ~1 минуту" | 1 минута — это backoff WorkManager, а не период |
| `MetaAiMemoryStore` | Присутствует | По имени не найден; найдена таблица `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Присутствуют | Присутствуют |
| Индикатор набора текста (chatstates) | Найден | Найден: исходящий `<chatstate><composing/></chatstate>`, с `<bot jid/>` при упоминании бота (`C199098dN.A01`); входящий `composing`/`paused` через общий обработчик `C40511kx`, bot-специфичной ветки нет |
| Заявление возможностей | не документировано | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) для Hatch; флаги 37227 / 37852 / 37054 отображаются на значения enum 76 / 77 / 79 |
| Примеры запросов Hatch | не документировано | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
