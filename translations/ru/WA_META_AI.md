<!-- src-sha1: 92bebfe6214e20e4e50526fbb6583d35cc44e808 -->
# WhatsApp Meta AI — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** внутренности Meta AI — JID, маршрутизация, поля proto, запросы метаданных Hatch, рендеринг ответа, почему Baileys не работает, исправление

---

## 1. Что такое Meta AI (технически)

Meta AI — это бот-контакт, адресуемый особыми bot-JID (сервер `bot`), со специфичными для бота полями proto на обычных типах сообщений и отдельным JSON-каналом запросов ("метаданные Hatch"), передаваемым в `ProtocolMessage`. Все утверждения — статический анализ декомпилированного APK. Уровень: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не разрешено.

Имена в этом отчёте, которые были обфусцированы в 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`), были повторно разрешены от стабильных якорей; под этими именами они не существуют в 2.26.41.6.

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| BotJid | `C24770wv` | класс JID, сервер `"bot"`, тип 26, числовая строка 1-20 символов, без ведущего 0 |
| Константы bot JID | `AbstractC34361Xw` | константы и наборы Hatch / Fallback / LID |
| Маппинг JID | `AbstractC24760wu` | маппинг bot ↔ LID, конверсия исходящей цели |
| Ограничение | `C39311it` | ограничение по флагу функции для JID (`A0E(Jid)`) |
| Менеджер запросов Hatch | `HF1` (`HatchMetadataRequestManager`) | JSON-запросы, карта ожидающих |
| Строитель proto Hatch | `Hf6` | строит `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | хранит `botMetadata` |
| BotMetadata | `C30615DTj` | метаданные бота на сообщение |
| Запись профиля бота | `C199348dm` | имя, описание, строка id персоны, миниатюра |

---

## 2. JID Meta AI

### 2.1 JID, найденные в коде

| Константа | Класс | Роль | Уровень |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) через `AbstractC34361Xw.A00` | **Hatch**, основной. Профиль по умолчанию строится в `C223219iv` из полезной нагрузки флага **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) через `AbstractC34361Xw.A01` | Резервный. Ограничен флагом 27083 | found |
| `165332417282214` | `C14080dr` (сервер `"lid"`) через `AbstractC34361Xw.A02` | LID-аналог `…698` | found |
| `1807055946647696` | нет | Manus (устаревшее в 2.26.26.4): **отсутствует** в 2.26.41.6 | found (отсутствует) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), плюс `A01` = `DeviceJid` устройство 0 | JID bot-сервера, используемый как цель сессии/устройства для "bot-конверта" (обработчик запроса синхронизации CoEx v2 `C53148Nnt` шифрует полезную нагрузку синхронизации для своего основного устройства, лог `coexv2 attached bot envelope`), добавляется в наборы устройств-получателей (`C12M`), и обрабатывается как отправитель-бот в обработке квитанций повтора (`C33020EaI`). Не чат-персона | found (использование); назначение сверх этого — предположение |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID встроенной записи профиля "Meta AI" по умолчанию (`C9i5.A00`: имя `Meta AI`, текст вступления по умолчанию). Член теста bot-JID `AbstractC24760wu.A07` вместе со следующей строкой | found |
| `867051314767696555` | `AbstractC24760wu.A01` (синглтон-набор, `C24770wv`) | Второй член теста bot-JID `A07` (`A07(jid)` = `C24770wv`, равный `…135992` или входящий в этот набор); `A07` питает `AbstractC199328dk.A00` (предикат по классу JID). Дальнейшее назначение не разрешено | found (использование), назначение unknown |
| `17015557208` | `AbstractC24760wu.A04` | Строка пользователя-телефона. `A04(jid)` истинно для LID `165332417282214` или для этого пользователя-телефона; используется с `A03` (любой bot-JID `C24770wv`, или PN в диапазонах 13135550000-13135559999 / 13165550000-13165550099) в `E76.A00` (класс 10 vs 1) и в предикате допустимости `C736539v.ARO`. Читается как PN-идентичность Meta AI; что эти два потребителя делают с этим, не разрешено | found (использование), назначение unknown |

Наборы в `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; карта `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Тип JID: отчёт на 2.26.26.4 перечислял все четыре как `@s.whatsapp.net`. В 2.26.41.6 bot-JID — это `C24770wv` с `getServer() = "bot"`; групповой/LID-JID — это `C14080dr` с сервером `"lid"`. Не `s.whatsapp.net` (found).

Таблица номер телефона → bot-FBID: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, около 200 записей, например `13135550002 → 867051314767696`). Используется `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 Конверсия маршрутизации

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

Found: bot-JID `…698` ↔ LID `165332417282214`; bot-контакты с номером телефона сопоставляются с bot-JID. Метод содержит assert "needs FBID migration" (found).

### 2.3 Суффикс `$1`: изменился

Отчёт на 2.26.26.4 помещал `$1` на маршрутизируемый JID ("формат протокола", `C1A2.A00()/A01()`). В 2.26.41.6 не найдено:
- Ни одна функция маршрутизации не добавляет `$1` к JID. Конверсия в 2.2 производит обычные bot-JID.
- `$1` добавляется к строке id персоны, хранящейся в записи профиля бота: `C24121Ab2` делает `personaIdString = botFbid + "$1"`; `C223219iv` захардкоживает `"1807055946647697$1"` для профиля Hatch по умолчанию (found).
- Эта строка (`C199348dm.A0A`) — это то, что `C33473Ehf.A0G` записывает в `BotMetadata.personaId` (found).

Так что `$1` принадлежит id персоны, а не целевому JID.

### 2.4 Обнаружение isMetaAI

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

Ветка Manus (флаг 25119) исчезла. Значение `BRD()` и поиска возможности (`C09L.A04`) не разрешены (unknown).

---

## 3. Флаги функций

| ID флага | Использование в 2.26.41.6 | Уровень |
|---------|------------------|------|
| **25119** | Появляется только в таблицах флагов (`C06510El`, по умолчанию `false` в `C08J`). Читателя не найдено. Старое имя `ai_bot_integration_enabled` не найдено как строка | found |
| **26189** | Ограничение Hatch в `C39311it.A02()`. По умолчанию `false` (`C08J`) | found |
| **27083** | Ограничение Fallback / LID в `C39311it.A0E()`. По умолчанию `false` | found |
| **26190** | JSON-конфигурация (`name`, `description`, `profile_thumb`) для профиля Hatch по умолчанию, читается в `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Когда истинно, возможность `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) анонсируется Hatch (см. 5); `A05` также ограничивает телеметрию/UI коннекторов (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Анонсирует `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); также ограничивает доступность коннекторов (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Анонсирует `HATCH_ARTIFACT_CARD_ENABLED` (79); также читается `HatchSpacesSync` и `C7WL` | found |

Строки `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` — не имена флагов. Это записи списка функций-строк, построенного из флагов 26189 / 27083 в `C25056AqU` (наряду с `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` добавляется безусловно. Получатель и назначение этого списка не проверены.

---

## 4. Поля Proto

### 4.1 Message (`C30628DTw`) верхнего уровня

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (единственное поле `message` = 1) | Исходящее сообщение, обёрнутое для бота; устанавливается в `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Задача бота |
| `botForwardedMessage` | **104** | `BD2` | Оборачивает сообщение, несущее `richResponseMessage`; устанавливается в `F3E` |
| `richResponseMessage` | **97** | `DSY` | Ответ AI. Поля: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Присутствует |
| `botGroupParticipantMessage` | **137** | `BD2` | Присутствует |
| `messageContextInfo` | **35** | `C30624DTs` | Несёт `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Несёт `aiMetadataOperation` (31) |

Поле **77** — это `commentMessage`, не `richResponseMessage` (в отчёте на 2.26.26.4 было 77; неверно для этой сборки, и согласуется с отдельным исследованием richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), не ContextInfo

Отчёт на 2.26.26.4 перечислял их как поля ContextInfo. В 2.26.41.6 они находятся на `WebMessageInfo`:

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Устанавливается в `C34385EwW` из `C0DZ.A09(userJid)` (пользователь основного устройства вызывающего) |
| `isSupportAiMessage` | **70** | bool | Устанавливается в `C34378EwP.C57`, когда сообщение несёт бит флага `268435456` и проверка проходит; читается обратно в `C59`. Совместно с `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Цитаты |
| `botTargetId` | **73** | string | Нет записывающего в клиенте: `botTargetId_` появляется только как значение по умолчанию конструктора и в таблице схемы `C30626DTu`, никогда не присваивается в другом месте (grep по всему исходнику) |
| `agentId` | **47** | string | Присутствует, не анализировалось |

Появляются ли эти поля WebMessageInfo в протоколе и как — не проверено (unknown). Утверждение "`true` для всех сообщений Meta AI" не подтверждается: оно устанавливается на уровне флага сообщения, не безусловно.

### 4.3 MessageContextInfo (`C30624DTs`)

| Поле | Номер | Тип |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `personaId` | **2** | string | Из записи профиля бота (`C199348dm.A0A`), например `1807055946647697$1`. Не фиксированная `"meta_ai"` |
| `pluginMetadata` | **3** | `DTL` | Конфигурация плагина |
| `invokerJid` | **5** | string | Вызывающий |
| `aiConversationContext` | **20** | bytes | Состояние диалога |
| `botResponseId` | **26** | string | Id ответа |

Прочие присутствующие поля (имена из `*_FIELD_NUMBER`, типы не прочитаны): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` заполняется в `C33473Ehf.A0G`; метод возвращается рано, если у профиля нет строки персоны.

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

Константы `C4E0` (значение = ordinal конструктора; равенство номеру proto предполагается): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Старые значения 8/9/15 не изменились; enum стал больше.

### 4.6 Oneof действия (`C61331Rfl`, enum кейса `EnumC61601RkN`)

| Номер | Кейс | Уровень |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Это oneof полей действия, не обычный value-enum. Где это встроено, не трассировано (unknown).

### 4.7 Операция метаданных AI (носитель Hatch)

| Сообщение | Поле | Номер | Тип |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Протокол запроса (метаданные Hatch)

Запросы строятся `HF1` (`HatchMetadataRequestManager`), классом корутины `HatchMetadataRequestManager$sendRequest$2`. JSON-конверт отличается от 2.26.26.4: `method` и `params` вложены под `payload`.

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

`params` и `accepts_encoding` опциональны (found). Id запроса не находится в JSON; это `BB2.requestId` (случайная строка из `C20F.A0x()`).

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

- Ожидающие запросы: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) и `HF1.A03` (requestId → `GuR`). Обе очищаются в `finally`. В отчёте на 2.26.26.4 была названа только одна карта `A02`.
- Таймаут: возвращает `GDB.A00` и логирует `HatchMetadataRequestManager/sendRequest timed out method=`.
- Целое число `138`, передаваемое в `C37393GKy`, не разрешено (unknown).
- Носитель — это `ProtocolMessage.aiMetadataOperation` (поле 31), не обычное сообщение чата (изменилось).
- Пакет `com.whatsapp.bot.infra.message.aimetadata` содержит классы `Ideas*Wire` / `Idea*Wire` (found). Их связь с именами методов только предполагается; имена методов не были перечислены.
- Сторона получения, завершающая `A04`, не трассирована. Сопоставление ответа с `requestId` предполагается из карты `A04` и `BB2.requestId`.

**Утверждение "нет собственного пространства имён XMPP"**: ни обработки `w:ai` / `wa:ai` не замечено в трассированном пути; основано на отсутствии, не перепроверено исчерпывающе.

**Анонс возможностей (found, `C33284Eea`):** когда цель — bot-JID Hatch `…697` (`AbstractC34361Xw.A00`), и ограничение проходит, клиент строит `DPJ` (единственное repeated поле enum `capabilities` = 1, значения `EnumC32144E2q`), и `C33473Ehf.A06` сохраняет его в `BotMetadata.capabilityMetadata` (13) исходящего сообщения, вместе с `BotMetadata.timezone` (8) = ID `TimeZone` устройства. Возможности, добавляемые по ограничению:

| Ограничение | Возможность (номер enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| флаг **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| флаг **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| флаг **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Числа — это второй аргумент конструктора enum; их равенство номерам proto предполагается. Enum также перечисляет возможности rich-response (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Примеры запросов (found, ключи `params` прочитаны в точках вызова; цель — bot-JID Hatch `…697`, если только точка вызова не использует JID беседы):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | строится в `HatchIdeasManager$execute$job$1` (ключи не прочитаны); прикреплён колбэк `onPart` |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire`, сериализуется в JSON; прикреплён колбэк `onPart` |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` только когда непусто) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Форма байт в `BB2.data` (найденная форма, примерные значения):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` записывается только когда у вызывающего `acceptsGzipResponse` истинно; `params` только когда не null. Колбэк `onPart` регистрируется в `A03` только когда вызывающий его передаёт.

**Сообщение чата боту (найденные части):**
- Исходящий `Message` переоборачивается в `Message.botInvokeMessage` (`F2K`, `C33284Eea`), обёртка `BD2` хранит сообщение в поле 1. В `F2K` обёртка пропускается (сообщение устанавливается напрямую), когда `C13S.A00()` ложно, `A10` сообщения ложно, или включён флаг **10646** (found).
- `BotMetadata` строится `C33473Ehf.A0E` / `A0G`. `A0G` ищет запись профиля для целевого bot-JID (`C199358dn.A06(userJid)`, строка персоны `C199348dm.A0A`); если эта строка пуста, метод возвращается без записи метаданных бота, иначе устанавливает `personaId` (2) и, если присутствует, `suggestedPromptMetadata` (4) и дальнейшие под-сообщения. Строка персоны сохраняется при создании записи профиля (`C24121Ab2` строит `<id>$1`; `C223219iv` захардкоживает `1807055946647697$1` для Hatch). Попадает ли `messageContextInfo` на внешний `Message` или на сообщение внутри `botInvokeMessage`, не разрешено.
- `botMessageInvokerJid` / `isSupportAiMessage` устанавливаются на `WebMessageInfo` хуками D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Протокол ответа

### 6.1 Транспорт

Не перепроверено, как было заявлено в 2.26.26.4 ("обычные сообщения с байтами `hatchMetadataSync`", класс `Azz`). Найдено: `hatchMetadataSync` находится в `C25754B9o` внутри `ProtocolMessage.aiMetadataOperation`. Предположительно ответы Hatch приходят тем же образом и сопоставляются по `requestId` (inferred). Запросы Hatch — это вызовы методов; не показано, что это путь обычных ответов чата.

### 6.2 Потоковая передача / куски: не поддерживается, как описано

Таблица в отчёте 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`), как единый механизм потоковой передачи Meta AI, не подтверждается в 2.26.41.6:

| Поле | Где оно находится в 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` поле **7** (уведомление синхронизации истории, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) и `C25838BCy` поле **5** (синхронизация истории) |
| `isLastChunk` | `C55285Ou6` поле **8** (сообщение с `attestationBundles`, `teeModelConfig`, `violationSignal`; относится к TEE) |
| `streamingSidecar` | поле **18** на сообщениях изображение/видео/аудио (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | не найдены как поля proto |

Не найдено сборки кусков ответов Meta AI. Что существует для Hatch: `GuR(method, onPart)` — колбэк `onPart` на каждый запрос (found); что он несёт частичные результаты, предполагается из имени.

### 6.3 Rich response (поле 97)

`richResponseMessage` (`DSY`) = поле **97** у `Message`. Существуют классы рендеринга: `AiRichResponseFooterView` и `UnifiedResponseActionHandlerFactory` (пакет `com.whatsapp.conversationrow.botrichresponse`) (found). Цитаты: `WebMessageInfo.supportAiCitations` (72). Типы содержимого (изображения, таблицы, код) здесь не перепроверялись; см. отдельное исследование richResponseMessage.

### 6.4 Индикатор набора текста

Исходящее (found, `C199098dN.A01`, лог `HandleMeComposing/handleComposing`): стандартное состояние чата XMPP, собственного пространства имён в прочитанном коде нет.
- Обычный случай (без упомянутого бота, или bot-JID, разрешённый в стандартный): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Бот упомянут в чате: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Отправляется через `C10140Tq.A0X` с int-типом IQ 4.

Входящее (found, обработчик стансы `C40511kx`): `<chatstate>` с дочерним `composing` (опциональный `media`) вызывает обычный колбэк составления с `from`/`participant`; `paused` вызывает колбэк паузы. В этом обработчике не найдено ветки, специфичной для бота, так что `composing` от bot-JID идёт тем же путём, что и от любого контакта (inferred; серверная станса набора текста бота не наблюдалась). `BotMetadata.progressIndicatorMetadata` (12) и возможность `PROGRESS_INDICATOR` существуют как отдельный механизм прогресса внутри сообщения (только имена, не трассировано).

### 6.5 Синхронизация профиля бота

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) планирует `BotProfileForChatListWorker` в `A03()`: запрос WorkManager с тегом `BotProfileSyncManager` с `setBackoffCriteria(policy, 1, MINUTES)` и ограничением (тип значения не разрешён). 1 минута — это **backoff** повтора, не период. Утверждение из 2.26.26.4 "каждую ~1 минуту" не подтверждается (изменилось). `A02(groupJid, userJid)` запрашивает один профиль (`requestBotProfileResult`). Не часть обычной синхронизации ростера (без изменений).

Запись профиля `C199348dm`: тип бота (`C1XY`), jid, отображаемое имя (`A09`), описание (`A07`), строка персоны (`A0A`), миниатюры, метка времени.

### 6.6 Строки типа бота

`C718732k.A00(String)` сопоставляет: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; всё остальное становится `AnonymousClass399(str)`. Это метки типа бота (также используются в фильтрах UI), не значения `BotMetadata.personaId` (found).

---

## 7. Хранилище

- `MetaAiMemoryStore`: класса с таким именем в 2.26.41.6 нет. Найденный эквивалент — таблица `meta_ai_memory`, созданная классом схемы `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, индекс `meta_ai_memory_memory_content_index` на `memory_content`. Какой файл БД её хранит, не разрешено. Связанное (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; имя говорит "deprecated"), SharedPrefs `meta_ai_memory_disclosure_seen` (экран дизайна голосового звонка, `C29434Cpx`), enum возможностей `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), и `BotMetadata.memoryMetadata` (15).
- Ключ SharedPrefs `"meta_ai_forward_disclosure_seen"`: присутствует, boolean, читается в `C230589xr.A03` для `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: присутствует в `com.whatsapp.metaai.incognito.infra` (found).
- Отдельное хранение чатов Meta AI вне `msgstore.db` (2.26.26.4, не перепроверено): класса хранилища чатов не найдено; `meta_ai_memory` хранит только факты памяти, так что утверждение ни подтверждается, ни опровергается.

### 7.1 Private Search как вид треда bot-чата (новое в 2.26.45.10, found)

Новые классы (`com.whatsapp.privateai.privatesearch`, `com.whatsapp.searchui.search.psisearch`):

| Класс | Роль |
|-------|------|
| `PrivateSearchSessionManager` | Отслеживает единственный активный/самый недавний тред Private Search; отказывается возобновить тред, заменённый более новым поиском |
| `PrivateSearchThreadsManager` | Создаёт тред бота вида `PRIVATE_SEARCH`; расширяет `LX/1gu`, ту же базу `BotThreadsManager`, что уже использует `IncognitoAiThreadsManager` (выше) |
| `PsiSearchManager` (обфусцированный `LX/JjA`) | Владеет потоком отправки запроса/продолжения ("echo") |
| `PsiSearchDialogFragment` | UI диалога; аргумент `"kind"` со значением `"TURN_ON_PRIVATE_PROCESSING"` явно показывает шлюз согласия Private Processing |
| `PsiSearchUnifiedResponseRenderer` | Рендерит ответ бота |

Private Search реализован как ещё один **вид треда bot-чата**, не новый сетевой примитив. `PrivateSearchThreadsManager` вызывает общий конструктор bot-треда `LX/1gv;->A00(LX/2p4, ...)` с 5-значным enum `LX/2p4`: `UNKNOWN`(0) / `DEFAULT`(1) / `INCOGNITO`(2) / `SIDE_CHAT`(3) / `PRIVATE_SEARCH`(4). `PsiSearchManager` повторно проверяет вид треда против этого дискриминатора перед отправкой, отклоняя пустой запрос или тред не вида `PRIVATE_SEARCH`.

**Путь отправки запроса (found).** `PsiSearchManager.onEchoSelected` строит исходящее сообщение через ту же общую утилиту создания сообщений, которую используют другие отправки чата, `LX/D1D;->A05(...)`, затем диспетчеризует результат через обычную очередь исходящих сообщений (`LX/JjA;->A0H:LX/0JB;->D2A`). Ни один вызов GraphQL/MEX/IQ не появляется где-либо в этом пути — это тот же механизм обёртки `botInvokeMessage` (поле 67) в bot-JID, документированный в §11 ("Сообщение чата боту"), повторно используемый буквально и не выведенный заново здесь.

**Что остаётся нативным (перекрёстная ссылка).** Конвейер извлечения PSI/TEE, фактически отвечающий на запрос — `TeeClientToolOrchestrator`, `PsiSearchToolHandler` (клиентский инструмент `wa_search`), `IplsdHandshakeExecutor`, опирающийся на нативные `libpsi.so`/`libxplat_psi.so` — не изменился с 2.26.41.6 и документирован в исследовании Labyrinth/TEE в brain (здесь не выводится заново); ничего из этого не затрагивается пятью классами выше, которые только строят исходящее сообщение и рендерят ответ.

**Вердикт достижимости: достижима отправка, недостижима ценность.** Отправка инициации поиска достижима сторонним клиентом ровно в том же смысле, что уже достижим чат Meta AI (§8, §11) — ничего нового, что нужно преодолеть. Что недостижимо — это фактическая приватность-сохраняющая ценность функции: поиск PSI на устройстве по локальной БД чатов и круговой обмен с аттестованным enclave — нативные, а исходящий `Message` не несёт никакого предвычисленного материала PSI. Сторонний клиент, отправляющий обычный текст bot-JID Private Search, получил бы то, что серверная сторона бота делает с не-PSI-обработанным открытым текстовым запросом, а не собственную семантику приватного поиска WhatsApp (unknown, не проверено ни в одну сторону).

### 7.2 Остановка генерации перенесена с пути протокольного сообщения (новое в 2.26.45.10)

Строка ошибки `promptMessageKey` (присутствующая с 2.26.35.8, привязанная к `FMessageStopGeneration` / `ProtocolMessage.extraJson_`, тип 26) имеет **ноль совпадений** во всех 14 DEX-файлах в 2.26.45.10 (found, исчерпывающее сканирование строк). Базовое поле `extraJson_` всё ещё объявлено на `LX/DHC;` (хост-класс `ProtocolMessage`), но на него ссылаются только внутри объявления поля этого же класса и массива рефлексии — ни геттера, ни какого-либо другого класса в приложении, читающего его, нет (found). D8 полностью удалил отладочную информацию в этой сборке (ноль восстановимых имён файлов `DBG_SET_FILE` среди 34 255 методов в `classes6.dex`), так что обфусцированный класс, который раньше реализовывал `FMessageStopGeneration`, не удалось определить по отладочным метаданным; три строки имён `.kt`-файлов для него сохраняются только как осиротевшие записи в пуле строк, не как достижимый код (found).

Найден вместо этого новый, **необфусцированный** класс `com/meta/metaai/stopgeneration/data/StopGenerationRepository`, чей `A00(threadIdentifier, messageIdentifier, messageIdString, surface, mode, Continuation)` запускает мутацию Pando GraphQL `MetaAIStopGenerationMutation` (операция `xfb_genai_stop_generation`), с полями `thread_identifier`, `message_identifier`, `message_id_string`, `surface`, `mode`, проверяемыми обобщёнными не-строково-ключевыми null-проверками (`LX/00m;->A09`) — без текста ошибки в стиле `promptMessageKey`.

Наилучшее объяснение (**inferred**, не доказано): остановка генерации перенесена на эту GraphQL-мутацию для этой поверхности, а не старая проверка протокольного сообщения была переименована на месте. Является ли устаревший путь `protocolMessage`/тип-26/`extraJson_` теперь мёртвым кодом, сохранён для совместимости со старыми клиентами, или всё ещё достижим из какого-то нетрассированного вызывающего — **unknown** — в этой сборке вызывающий не найден, но статическое сканирование одного DEX не может доказать удаление.

---

## 8. Почему Baileys не получает ответ

Все строки — **inferred**: статическое сравнение требований клиента со сторонним путём отправки; без живого теста.

| Проблема | Основание в 2.26.41.6 | Уровень |
|-------|--------------------|------|
| Неверный тип целевого JID | Bot-JID используют сервер `bot` (`C24770wv`), не `s.whatsapp.net`; боты с номером телефона сопоставляются через таблицу PN→FBID | found (класс JID), inferred (эффект) |
| `$1` на маршрутизируемом JID | Не присутствует. `$1` — на строке id персоны | found |
| Отсутствует обёртка `botInvokeMessage` | Клиент оборачивает исходящий `Message` в поле 67 (`F2K`) | found, требование — предположение |
| Отсутствует `messageContextInfo.botMetadata` | Клиент записывает в него `personaId`, `invokerJid` и т.д. | found, требование — предположение |
| `personaId = "meta_ai"` | Не то, что отправляет клиент; он отправляет строку персоны профиля (например, `1807055946647697$1`) | found |
| Отсутствует `aiConversationContext` | Поле 20 у `BotMetadata`; поведение на первом ходе unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Поля WebMessageInfo, устанавливаемые хуками клиента; серверное требование unknown | unknown |
| `botTargetId` | Нет записывающего в коде клиента | found |
| Ответ не разбирается | `richResponseMessage` — это поле 97 у `Message` | found |
| Сборка кусков | Не подтверждается доказательствами из 2.26.41.6 (см. 6.2) | found |

---

## 9. Верификация подписи бота (аутентичность содержимого)

Отдельно от всего вышеперечисленного: механизм, позволяющий **принимающему** клиенту проверить, что содержимое `richResponseMessage` действительно пришло от бэкенда AI Meta, независимо от того, кто передал сообщение. Статические находки ниже — `found` в коде 2.26.41.6; результат воспроизведения в 9.4 — `tested` (живой, на собственном аккаунте автора — не перехват трафика, легитимный клиент, составляющий и передающий своё собственное сообщение).

### 9.1 Расположение в proto

`BotMetadata.verificationMetadata` — поле **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), тип `DPC`/`BotSignatureVerificationMetadata` (toString раскрывает настоящее имя): `proofs[]`, каждый — `BotSignatureVerificationUseCaseProof` с `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (repeated bytes, DER X.509).

### 9.2 Алгоритм верификации

Класс `C33259EeB`, внутреннее имя `BotSignatureVerificationUtils` (из строк лога):

1. **Валидация цепочки сертификатов** у `certificateChain` против якоря доверия, через `HFg.A01(date, certs, true)`.
2. **Построение подписанных байт**: `"1" + <строка номера телефона> + <байты unifiedResponse>` — подпись связывает **содержимое и номер телефона вместе**, не только содержимое.
3. **Проверка EdDSA** (лог: `"EdDSA signature verification result"`) с использованием сырого ключа Ed25519, извлечённого из SubjectPublicKeyInfo листового сертификата.
4. **Режим применения**, читается из конфигурации **19590**, enum `EnumC32057Dzg`: `NONE` (`"none"`, выключено, всегда проходит), `LOG_ONLY` (`"log_only"`, проверка + лог, никогда не блокирует), `ENFORCE_BLOCKING` (`"enforce_blocking"`, неудачная проверка возвращает `false`). Результат сохраняется как `E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, хранится в столбце SQLite `bot_message_info.signature_validation_status` (у таблицы также есть `bot_client_public_key`).

### 9.3 Шлюз рендеринга строки

`C30085D6v.A00` (диспетчер типа строки) и `EOK`/`C32608EKo`: если статус подписи `FAILED` и включён флаг **27635** → замаскированная строка `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Независимо, если JID отправителя не присутствует в локально синхронизированном хранилище профилей бота (`C224899mg`, та же синхронизация, что у `BotProfileSyncManagerImpl`) и включён флаг **27355** → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), предпросмотр с согласием, а не жёсткая блокировка.

### 9.4 Реальный захват и живое воспроизведение (tested)

Настоящий ответ Meta AI, захваченный клиентской стороной в реальной беседе (собственный аккаунт, расшифрован собственным клиентом автора — не перехват трафика), нёс:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, 64-байтная (размера Ed25519) `signature`, `certificateChain` из 2 элементов.
- Листовой сертификат: `CN=svc:wa-bot-msg-leaf`, ключ Ed25519, выпущен `Meta WA SS Int CA 2025-09`, цепочка к `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`), срок действия ≈7 месяцев (автоматически ротируемый сервисный сертификат) — закрытый ключ подписи существует только в бэкенде Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — имя бэкенда бота, ранее не документированное (см. также "Hatch" в разделах 1–6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, поле-сосед `botMetadata`.
- Форма доставки: `protocolMessage` с `type: MESSAGE_EDIT`, `editedMessage.richResponseMessage` (первый ответ в треде приходит заранее обёрнутым как правка заглушки), `key.remoteJid` = собственный JID автора.

**Тест:** точный `richResponseMessage` + `messageContextInfo.botMetadata` (подпись и цепочка сертификатов побайтово неизменны) были переданы через `relayMessage` с собственного устройства автора — не bot-JID `867051314767696@bot` — на собственный номер автора (тот же номер, что уже встроен в подписанные байты).

**Результат:** содержимое отрендерилось с полным оформлением "AI" и настоящим текстом, помеченное "Forwarded". Некоторые доставки идентичной полезной нагрузки вместо этого показали "WhatsApp can't verify the security of this media. Only download if you trust the sender." с действием Download; нажатие Download раскрывало идентичное содержимое, совпадая со статусом `DOWNLOAD_CONSENT_ACCEPTED` и путём кода "unknown sender with unconsented content" из 9.3. Одна доставка показала вместо этого обычный резервный вариант "your version of WhatsApp doesn't support it"; причина не установлена (unknown).

**Вывод (tested):** криптографическая проверка в 9.2 привязывается к *(содержимое, номер телефона)*, не к идентичности или JID живого отправителя. Валидно подписанный `richResponseMessage` может быть воспроизведён от отправителя не-бота и всё равно пройти верификацию подписи, пока номер получателя совпадает с номером, встроенным в подпись — принимающий клиент рендерит это как подлинный AI-контент (в лучшем случае ограничено однокликовым, косметическим шагом согласия "unknown sender", не жёсткой блокировкой). Это механизм аутентичности содержимого, а не аутентичности отправителя; собственное шифрование слоя Signal у WhatsApp, а не эта подпись — это то, что аутентифицирует живого отправителя.

### 9.5 Проверка списка отозванных сертификатов (CRL) (новое в 2.26.45.10, found)

Шаг валидации цепочки в 9.2 (шаг 1, "валидация цепочки сертификатов... через `HFg.A01`") получил проверку CRL как против листового, так и против промежуточного сертификата в `certificateChain`, перед проверкой подписи Ed25519 над (телефон, содержимое) (9.2 шаг 3). Классы: `BotPkiCrlGraphQLFetcher`/`BotPkiCrlManager` (`com/whatsapp/bot/infra/message/signature/`), вызываются из класса валидации цепочки 2.26.45.10 `BotSignatureVerificationCertificateManager` (`LX/HEe` — переименованный наследник `BotSignatureVerificationUtils`/`C33259EeB` из 9.2; тот же класс, подтверждено общими строками лога `"Certificate chain validation successful"`/`"Parsed <n> certificates from chain"`).

- **Операция GraphQL**: `FetchBotPKICRL` на `whatsapp-android-mex` — поле запроса `crl_name`, ответ `xwa2FetchFeaturePkiCrl`, содержащий CRL как сырой DER-блоб байт (не предварительно разобранный список отозванных серийных номеров) плюс метки времени `fetchedAt`/`nextUpdate` и счётчик отозванных записей.
- **Два используемых CRL**, по имени: `whatsapp_simple_signal` для **листового** сертификата, `whatsapp_feature` для **промежуточного** сертификата (строки лога `"...Leaf certificate CRL validation passed"` / `"...is revoked"` / `"...CRL unavailable..."`, та же пара для "Intermediate").
- **Якорь доверия**: 40-летний корневой сертификат, закреплённый как PEM-литерал внутри `LX/HEe` — `CN=Meta WA Feature Root CA`, `O=Meta Platforms Inc.`, ключ EC, действителен с 2025-09-04 по 2065-09-04. Собственная подпись каждого полученного CRL проверяется против публичного ключа соответствующего эмитента (`X509CRL.verify(...)`), прежде чем его список отозванных будет доверен — за исключением `whatsapp_simple_signal`, для которого сделано особое исключение, пропускающее этот шаг самопроверки (причина `inferred`, не разрешена).
- **Кэширование/обновление**: кэш `SharedPreferences` на каждый `crlName` (`crl-data`/`crl-fetched-at`/`crl-next-update`), предзагружается один раз при инициализации приложения после регистрации пользователя и готовности БД (лог: `"BotPkiCrlManager/...starting CRL prefetch"`), обновляется по таймеру, привязанному к собственному `nextUpdate` CRL (с полом в 60с), и получается по требованию с окном backoff, если кэш отсутствует/устарел на момент проверки.
- **Эффект**: отозванный листовой или промежуточный сертификат не проходит валидацию цепочки так же, как уже просроченный — это питает существующий статус `E05` (`FAILED`) и шлюз `ENFORCE_BLOCKING`/`LOG_ONLY`/`NONE` из 9.2 шаг 4, не новый, отдельный путь применения.
- **Уровень**: found — операция, пространство имён, оба crlName, механика кэша/обновления, точки вызова, закреплённый корневой сертификат. Inferred — точная раскладка байт отозванной записи (серийный номер vs. полные байты сертификата) и причина, по которой `whatsapp_simple_signal` пропускает самопроверку CRL. Всё статический анализ; на практике не наблюдалось ни одного отозванного сертификата.
- **Поверхность клиента/Baileys**: `FetchBotPKICRL` — конкретная, именованная операция MEX, достижимая так же, как и другие операции `whatsapp-android-mex`, но она только питает клиентские решения о доверии к сертификатам сообщений бота — она не влияет на то, что может передать отправитель, не являющийся клиентом (результат воспроизведения из 9.4 не затрагивается: отзыв меняет исходы только для фактически отозванного сертификата, что здесь никогда не задействуется).

---

## 10. Исправление для Baileys

Рабочая реализация не заявляется. Далее — структурный набросок того, где находятся поля согласно 2.26.41.6, отмеченный **inferred**; это не было запущено против сервера.

### 9.1 Цель

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Работает ли строка сервера `bot` как целевой relay для Baileys, и как сервер выводит финальный `to` стансы — unknown.

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

- Встраивание `botMetadata` в `messageContextInfo` (поле 7) — **found**. `capabilityMetadata` (13) и `timezone` (8) записываются клиентом только для целей Hatch (found); их серверное требование unknown. Проверено ли, есть ли уже эти поля в proto у `baron-baileys-v2` — не проверено; если нет, proto нужно расширить (inferred).
- `isSupportAiMessage` (70) и `botMessageInvokerJid` (58) — это поля `WebMessageInfo`. Должны ли они присутствовать в протоколе — unknown; не помещать их в `contextInfo` (это было неверно в отчёте 2.26.26.4).
- `botTargetId`: нет записывающего в клиенте где-либо в декомпилированном коде (found); не устанавливать его.
- Точное оборачивание (`botInvokeMessage.message`, содержащий настоящее сообщение, vs. рядом с ним) следует переоборачиванию `F2K` / `C33284Eea`; точный сериализованный результат не воспроизведён (unknown).

### 9.3 Обработка ответа

- Rich-ответы: `Message.richResponseMessage` — это поле **97** (found). Разбирать именно это, не поле 77.
- Убрать обработку кусков: `chunkOrder` / `isLastChunk` — не поля потоковой передачи Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) Hatch — это канал JSON-запросов; не показано, что обычные ответы чата используют его.

### 9.4 Контекст беседы

`BotMetadata.aiConversationContext` (20) существует. То, что сервер возвращает обновлённое состояние в ответах и что его нужно отправлять обратно — это **inferred** (из имени поля и отчёта 2.26.26.4); не проверено.

---

## 11. Потоки

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

### 10.2 Запрос метаданных Hatch (found на стороне клиента)

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
| JID `1807055946647696` (Manus) | Устаревший, флаг 25119 | Отсутствует. 25119 только в таблицах флагов, читателя нет |
| JID 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 — сервер `bot` (`C24770wv`); 165332417282214 — `lid` (`C14080dr`) |
| Новые константы JID | не перечислялись | `1807055946647699` (CoEx v2 bot-конверт / цель набора устройств), `2942131436135992` (JID профиля Meta AI по умолчанию, тест bot-JID `A07`), `867051314767696555` (второй член `A07`, назначение unknown), `17015557208` (PN Meta AI, `A04`) |
| Суффикс `$1` | На маршрутизируемом JID, `C1A2.A00/A01` | Не на JID; добавляется к строке id персоны (`C24121Ab2`, `C223219iv`) |
| Конверсия маршрутизации | добавление `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot через таблицу FBID |
| Имена флагов 25119/26189/27083 | имена флагов `ai_*` | Строки — записи списка функций (`C25056AqU`); 26190 = JSON профиля Hatch; 37227/37852/37054 ограничивают значения возможностей Hatch 76 / 77 / 79 |
| `richResponseMessage` | Поле 77 | Поле 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 на "WebMessageInfo" | 67 / 100 / 104 на `Message`; также 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` никогда не записывается |
| Расположение BotMetadata | "встроено в сообщение" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Строка персоны профиля, например `1807055946647697$1`; `meta_ai` — метка типа бота |
| Типы плагинов | 8, 9, 15 | Те же, у enum 18 значений (до 17) |
| Enum действия | Value-enum 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| JSON-конверт Hatch | `method`, `params` верхнего уровня | Вложены под `payload`; добавляется `accepts_encoding` |
| Носитель Hatch | Обычное сообщение, класс `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; добавляется `bizAiMetadataSync` (2) |
| Верификация подписи бота | не документирована | Новое: `BotMetadata.verificationMetadata` (27), EdDSA + цепочка сертификатов X.509 над (содержимое, номер телефона); проверено живьём, привязывается к номеру телефона, не к живому отправителю (раздел 9) |
| Карты ожидающих | Одна (`A02`) | Две: `A04` continuations, `A03` колбэки частей `GuR` |
| Поля потоковой передачи | Одна таблица кусков Meta AI | `chunkOrder` (синхронизация истории), `isLastChunk` (сообщение TEE), `streamingSidecar` (медиа); `clientStreaming`/`serverStreaming` не найдены |
| Интервал синхронизации профиля | "каждую ~1 мин" | 1 мин — это backoff WorkManager, не период |
| `MetaAiMemoryStore` | Присутствовал | Не найден по имени; найдена таблица `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Присутствовали | Присутствуют |
| Индикатор набора текста (chatstates) | Найден | Найден: исходящий `<chatstate><composing/></chatstate>`, с `<bot jid/>`, когда упомянут бот (`C199098dN.A01`); входящий `composing`/`paused` через обычный обработчик `C40511kx`, без специфичной для бота ветки |
| Анонс возможностей | не документирован | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) для Hatch; флаги 37227 / 37852 / 37054 сопоставляются со значениями enum 76 / 77 / 79 |
| Примеры запросов Hatch | не документированы | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
