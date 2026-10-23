<!-- src-sha1: 7a4b50013c0f196c95c57808469516becf9a34b7 -->
# WhatsApp Message Secrets — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** секрет `messageSecret` для каждого сообщения (генерация, `MessageContextInfo`, локальное хранилище, history sync), вывод ключей по use case (HKDF), IV / AAD для AES-GCM, зашифрованные add-on (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, правки `secretEncryptedMessage`), привязка идентичности отправителя / цели и повтор LID / PN, orphan-сообщения и fallback при отсутствии секрета, расширения stanza `<message>` (атрибуты, атрибуты `<enc>`, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, проверка поддержки на companion), feature flags, сравнение с Baileys

---

## 1. Что это (технически)

Каждое сообщение, которое позже может получить зашифрованное продолжение, несёт случайный 32-байтный секрет в собственном сквозным образом зашифрованном payload (`MessageContextInfo.messageSecret`). Продолжение (реакция, голос в опросе, ответ на событие, комментарий, правка) шифруется ключом, выведенным из этого секрета, id исходного сообщения, исходного отправителя и модификатора. Сервер пересылает продолжение как обычное E2E-сообщение, но не может ни прочитать его, ни перенаправить на другую цель, другому пользователю или в другой use case без нарушения аутентификации GCM. Все утверждения основаны на статическом анализе декомпилированного APK; на wire ничего не перехватывалось. Уровни: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не разрешено. Обфусцированные имена заново определены в 2.26.41.6 по стабильным строкам (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, строки use case, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

Тот же релиз определяет и расширения stanza `<message>` (раздел 10 и далее): атрибуты и дочерние узлы, которые классифицируют и маршрутизируют сообщение, но не несут его содержимое. Они собраны здесь, потому что `<meta polltype>` / `<meta event_type>` должны согласовываться с payload, зашифрованным секретом (7.4).

| Сущность | Имя в 2.26.41.6 | Роль |
|----------|-----------------|------|
| Crypto helper (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` шифрование, `A04` расшифровка (повтор по идентичности), `A02` определение целевого ключа |
| Носители параметров шифрования / расшифровки | `C32833ETl` / `C32854EUg` | данные, отправитель, целевой ключ, use case / IV, payload, ключи, отправитель |
| Вывод ключа | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, нулевая соль |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | нативный, 16-байтный тег |
| Поставщики AAD | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (нет) | дополнительные данные |
| Генератор секрета | `AbstractC33322EfC.A01` | `SecureRandom`, 32 байта |
| Хранилище секрета (`MessageSecretStore`) / extra в памяти | `C35311ad` (таблица `message_secret`) / `C35171aP` в сообщении `C13G` | сохранение и перенос |
| Маппер исходного ключа (`ReferentialKeyUtil`) | `C43661qB.A03` | ключ неотредактированного исходного сообщения |
| Обработчики реакций | `DU8` (отправка), ветка `F2P` (приём) | `reactionMessage` / `encReactionMessage` |
| Голос в опросе / ответ на событие / комментарий | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Правки, зашифрованные секретом (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Создание опроса / события (секрет берётся при приёме) | `F2N` / `F2M` | читает `messageSecret` в FMessage |
| Proto: контекст / сообщение / ключ | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Выбор `type` stanza | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Исходящие поставщики stanza | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), флаги `F68`, `F69` cap, `F6H` padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | строят дочерние узлы `<message>` |
| Аккумулятор `<meta>` | `EZV` (атрибуты `A01`, дочерние `A00`) | один узел `<meta>` |
| Построитель атрибутов `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Проверка поддержки на companion | `C34757F6a` + `AbstractC32927EXc` | allowlist типов и дочерних узлов |
| Парсеры входящих спецификаций | `C33474Ehg` (status / обычные), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | извлечение атрибутов и дочерних узлов |
| WAM-событие ошибки | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. Секрет сообщения

### 2.1 Где хранится (found)

`MessageContextInfo` (`C30624DTs`) — поле **35** в `Message` (`C30628DTw`). Релевантные поля:

| Поле | Номер | Тип | Назначение |
|------|-------|-----|------------|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | подсказка о списке устройств (к секрету не относится) |
| `messageSecret` | **3** | bytes (32) | секрет сообщения |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | время жизни add-on (pin: для unpin должно быть 0) |
| `botMessageSecret` | **6** | bytes (32) | bot-вариант секрета |
| `botMetadata` | **7** | message | bot-контекст |
| `reportingTokenVersion` | **8** | uint32 | версия reporting token этого сообщения |
| `messageAddOnExpiryType` | **9** | enum | срок действия add-on |
| `messageAssociation` | **10** | message | ассоциация |

Носитель history sync `WebMessageInfo` (`C30626DTu`) имеет собственное поле `messageSecret` **49** (found), используемое при экспорте сообщений на новый companion (раздел 2.4).

### 2.2 Генерация (found, условия частично inferred)

Секрет — это `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). Он прикрепляется до сериализации сообщения:

| Место | Условие |
|-------|---------|
| `C33166Ecf.A06` (подготовка отправки) | у сообщения нет секрета и выполняется хотя бы одно из: класс опроса `C13J`; `EZN.A01(msg)` (класс bot / add-on, с флагами типа чата **2200**, **11104**, **19303**); проверки по классу чата: группа с флагом **3143**, список рассылки с **3144**, статус с **3145**, проверка класса **3146**; `C35201aS.A00` (флаг **3142**, чат с самим собой / bot); сообщение-событие `C213509Ao` |
| `AJ0` (процессор отправки) | версия reporting-token `C35241aW.A05()` (AB int **8860**, ограничена `AbstractC35301ac.A00`) не равна нулю, и класс сообщения не исключён через `C35241aW.A02` (status, newsletter, отдельные классы add-on) |
| `C72h`, `C34455Exe`, `EPA` | объекты status (`AbstractC34478Ey1.A0R`) получают новый секрет при создании |
| `C33437Eh4` | bot-сообщение "request welcome", только если вызывающий код этого требует |
| `C9mW` | сообщение типа 117, флаг **24741**, если секрета нет |

Предикаты за `EZN.A01`, `C35201aS.A00` и проверками `3142`..`3146` разрешены не полностью; список выше говорит, что проверяет код, а не какие видимые пользователю сообщения подходят. Сообщения без секрета не могут получать зашифрованные add-on от этого клиента (раздел 9).

### 2.3 Локальное хранилище (found)

`C35311ad` пишет `message_secret(message_row_id, message_secret)` с семантикой replace (`MessageSecretStore/insertMessageSecret`) и читает последнюю строку для `message_row_id`. FMessage хранит его как extra `C35171aP` (`A0L` установить, `A0c` получить, `A0Q` = не пусто). Два процессора в `AbstractC17240jU` (`C35161aO` и анонимный) записывают его, когда extra помечен как изменённый и чат подходит.

### 2.4 Валидация при приёме и перенос (found)

| Шаг | Поведение |
|-----|-----------|
| Proto-валидатор `C33475Ehh.A0V` | `message_secret` должен быть ровно **32** байта, код ошибки **67**; bot-вариант (`bot_message_secret`, группа `whatsapp_security`) проверяется так же |
| Создание опроса `F2N` | копирует `messageSecret_` в новый FMessage (`A0L`) |
| Ответы на вопросы status `C34838F9e` | то же копирование для `statusQuestionAnswerMessage` |
| Экспорт history sync `C34388EwZ.A00` | записывает сохранённый секрет в `WebMessageInfo.messageSecret` (49) |
| Импорт history sync `C34388EwZ.C59` | копирует обратно (`A0L`) |
| Комментарии `C34387EwY` | пересобирает `MessageContextInfo` из `WebMessageInfo.messageSecret` для ветки комментариев |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) логирует `message_secret_error` **0** = отсутствует (соответствует коду ошибки 66) или **1** = неверная длина (67) для сообщений, которым нужен секрет (`AbstractC33322EfC.A00`: есть флаг и это не класс `C35281aa`).

---

## 3. Вывод ключа по use case

### 3.1 Формула (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract с 32-байтной нулевой солью (`AbstractC38971i1.A00(ikm, salt)`), затем цикл expand по RFC 5869. Основы HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) раздел 5.1. 32-байтный результат используется как ключ AES-256 (inferred по длине; нативный вызов принимает ключ как `byte[]`).

Входные данные:

| Вход | Источник | Примечания |
|------|----------|------------|
| `originalMessageId` | id ключа цели после `ReferentialKeyUtil` (`C43661qB.A03`) при шифровании; id ключа из proto `targetMessageKey` при расшифровке | для отредактированной цели это id **исходного** сообщения (лог `getOriginalKey`) |
| `targetSender` | автор исходного сообщения: сохранённый отправитель (`C12300aw.A01`) | `UserJid`, то есть без суффикса устройства (на уровне типов; строковая форма `user@server` — inferred) |
| `modifier` | автор add-on: собственный JID аккаунта (`C09A.A0G`, LID, возвращается `CUC()` / `Ash()`) при отправке, JID отправителя конверта при приёме | |
| `useCase` | строка из 3.2 | между четырьмя компонентами нет разделителя |

Собственный JID — это JID аккаунта типа LID (`C14080dr`, сервер `lid`, проверка "Invalid LID"). И `AnonymousClass091.Ash()`, и `CUC()` возвращают одно и то же поле.

### 3.2 Строки use case (found)

| Use case | Носитель | AAD | Java-литерал в 2.26.41.6 |
|----------|----------|-----|--------------------------|
| `Enc Reaction` | `encReactionMessage` | нет | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | нет | `F3W` |
| `Event Edit` | `secretEncryptedMessage` тип 1 | нет | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` тип 2 | нет | `F3Y.A00`, только с флагом **17811** |
| `Poll Edit` | `secretEncryptedMessage` тип 4 | нет | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` тип 5 | нет | `F3Y.A00` |
| `WASA` | bot-путь (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | двухэтапный, 3.3 |
| `Report Token` | ключ reporting token | нативный | Java-литерала нет; присутствует в `libwhatsapp.so`, выводится нативно (3.4) |

### 3.3 Вариант Bot / WASA (found, детали inferred)

Для use case `WASA` вывод двухэтапный, и во втором этапе строки use case нет:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` — модификатор, `jidB` — удалённый (чатовый) JID, который должен быть `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`); id — текущий ключ сообщения, если он есть, иначе целевой ключ (lambda `C33285Eeb.A03`). Нативный аналог: `WcmBotMessageSecretAPICreateWithMessageSecret`. Контекст Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Ключ reporting token (found / inferred)

`C33364Efs.A06` и `C33421Ego` вызывают `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: нативный объект выводит ключ для use case id **5**; Java-сторона передаёт только raw-строки JID. Строка `Report Token` присутствует в нативной библиотеке; сопоставление id 5 с этой строкой — inferred. Токен и загрузка: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. Структура AEAD

| Элемент | Значение | Уровень |
|---------|----------|---------|
| Шифр | AES-GCM, нативный (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; расшифровка `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Ключ | 32 байта из раздела 3 | found |
| IV | **12** случайных байт на каждое шифрование (`SecureRandom`); при расшифровке любой другой размер отклоняется | found |
| Тег | 16 байт; константа 16 передаётся в обоих вызовах; позиция (дописывается к ciphertext) выведена из расшифровки в Baileys | found / inferred |
| AAD | зависит от use case (3.2); `null`, если поставщик `C34631F1e` | found |
| Plaintext | сериализованный внутренний proto (таблица 5) | found |
| Результат | тройка `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| Пустой результат | лог `encryption values are invalid`, ошибка `Encryption using iJniBridge failed` | found |

Повтор голоса в опросе: если голос уже содержит IV и payload (`C30957Dd6.A03` / `A04`), повторно отправляется тот же ciphertext вместо нового шифрования (found, legacy-ветка `DUA`).

---

## 5. Носители и plaintext

| Носитель (поле в `Message`) | Класс | Поля | Расшифрованный plaintext |
|-----------------------------|-------|------|--------------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (очищается перед шифрованием), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (repeated bytes, хэши вариантов) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown, 1 going, 2 not going, 3 maybe), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | полный `Message` (тело комментария); plaintext-форма — `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | полный `Message` |
| `reactionMessage` **46** | `DSH` | plaintext-форма | обычная реакция |
| `conditionalRevealMessage` **120** | n/a | не схема message-secret (раздел 14.1) | запланированные сообщения |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. Значения 3 в этой сборке нет (`forNumber(3)` возвращает null, трактуется как unknown и отклоняется).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Сторона отправителя

### 6.1 Общий путь (found, `C33285Eeb.A03`)

1. Найти целевой FMessage по ключу (`target message not found. Cannot proceed further` -> ошибка 71).
2. Прочитать его секрет из `message_secret`; null или длина != 32 -> `message secret missing or invalid` (66).
3. Исходный ключ через `C43661qB.A03` (null -> ошибка 0). Целевой отправитель через `C12300aw.A01`.
4. В чате 1:1 (`C0DZ.A0k(chat)`) целевой отправитель преобразуется в пространство имён модификатора: модификатор LID и цель PN -> цель из PN в LID; модификатор PN и цель LID -> цель из LID в PN. В группах преобразования нет.
5. Только Event Response: флаг **15791**, чат 1:1 и модификатор типа account -> модификатор преобразуется в PN.
6. Случайный 12-байтный IV, вывод ключа (3.1), AES-GCM с AAD для данного use case.
7. Построить внешний `MessageKey` из целевого отправителя и исходного ключа (`C32717EOy.A01`); носитель содержит `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 По носителям (found)

| Носитель | Условие при отправке |
|----------|----------------------|
| Реакция (`DU8.ADr`) | шифруется **только** если чат — группа (`C0DZ.A0l`) с `group_type == 3` (`C0GQ.A0A`; устанавливается в `CMP` из `isDefaultSubgroup_`, то есть default-подгруппа сообщества, интерпретация inferred) и флаг контекста сериализации `A09` равен false. В любом другом чате отправляется обычный `reactionMessage`. `ReactionMessage.key` обнуляется перед шифрованием (ключ переносится во внешний `targetMessageKey`) |
| Голос в опросе (`DUA.ADr`) | флаг **6772** включён: общий helper, всегда зашифровано; выключен: legacy-ветка inline с тем же выводом и AAD (целевой отправитель = собственный LID для своих опросов, иначе JID, полученный из целевого ключа голоса; модификатор = собственный LID). `metadata` (`pollNameHash`, опционально `lastEditStanzaId`) проставляется, когда включён флаг **31593** |
| Ответ на событие (`DU9.ADr`) | всегда зашифровано; plaintext `EventResponseMessage` содержит `response`, `timestampMs`, `extraGuestCount` |
| Комментарий (`F3W.ADr`) | всегда зашифровано; plaintext — весь `Message` комментария; цель — родительский ключ `CommentMessageInfo` |
| Правка, зашифрованная секретом (`F3Y.C5S`) | только когда у сообщения есть информация о правке типа `E2Q` и контекст сериализации не forwarded / orphan; `MESSAGE_EDIT` дополнительно требует флаг **17811** (иначе `getUseCase` выбрасывает исключение). Для правок собственных сообщений две строки лога (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) показывают случаи, отправляемые как обычные правки; полное условие (флаги **37948**, **35457**) потеряно при декомпиляции |

Вложенные payload, зашифрованные секретом, отклоняются с обеих сторон (`nested_secret_encrypted_message`).

---

## 7. Сторона получателя

### 7.1 Расшифровка (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (модификатор) по носителям: собственный LID, если конверт от меня; опрос: JID отправителя (`c0df` или `B4g()`); ответ на событие: пользователь чата в 1:1, иначе пользователь конверта; комментарий: только LID (`C0DZ.A0Y`: типы 18, 19, 25), отправитель PN даёт ошибку 0; реакция: отправитель конверта только если это LID, иначе null.

### 7.2 Повтор по идентичности LID / PN (found структура, хвост inferred)

Первая попытка использует JID как есть. При неудаче helper сопоставляет оба JID с другим пространством имён (`C0YH.A0I` LID->PN, `A0F` PN->LID) и повторяет один раз; если оба уже были LID или сопоставление отсутствует, результат — ошибка **51** (расшифровка не удалась). Декомпилированный хвост повтора частично потерян, поэтому точный набор пробуемых пар — inferred. Проверкой служит аутентификация GCM: неверная пара не проходит, верная расшифровывается.

### 7.3 Родитель отсутствует: orphan (found)

| Носитель | Поведение, когда родитель не найден или является placeholder |
|----------|--------------------------------------------------------------|
| Реакция | FMessage типа **56** сохраняется с сырыми байтами `Message` (`DdA(key, 56, ts).A02`); расшифровка откладывается |
| Голос в опросе | `C30957Dd6.A02 = Message.toByteArray()`; сохраняется нерасшифрованным |
| Ответ на событие | `Dd7(key, target, bytes, ts)` сохраняется нерасшифрованным |
| Комментарий | placeholder `C34671Zb` с родительским ключом и строкой `-1` |
| Правка, зашифрованная секретом | `DeD(MessageOrphan)` с типом orphan **5**, причина **1** (родитель отсутствует) или **2** (placeholder) |

Повторная обработка при появлении родителя ожидается (orphan сохраняются вместе с сырыми байтами), но триггер повтора не прослежен (inferred).

### 7.4 Валидация после расшифровки (found)

| Случай | Проверка | Сбой |
|--------|----------|------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` должен быть `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | тип `POLL_ADD_OPTION` и второе поле stanza, равное `poll_add_option` (поле не разрешено) | `poll_add_option_stanza_invalid` (76) |
| Правка события | внутреннее сообщение типа 92, итоговый ключ равен внешнему ключу | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Правка опроса | внутренний тип 66, оба сообщения — опросы, одинаковые время окончания и флаги, правки вариантов согласованы с сохранёнными вариантами, timestamp не позже времени окончания | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Добавление варианта в опрос | внутренний тип 137, родитель — опрос, целевой ключ равен внешнему ключу, не позже времени окончания | `poll_add_option_past_end_time` |
| Приём правки опроса | AB int **24886** должен быть не равен нулю | ошибка 10016 ("futureproofing") |
| Приём добавления варианта в опрос | AB **25758** должен быть не равен нулю | ошибка 10017 |
| Голос в опросе | выбор должен быть допустим для опроса (`AbstractC33199EdC.A02`); timestamp голоса не позже времени окончания опроса | `poll_update_past_end_time`, `invalid poll vote selection` |
| Metadata голоса | `pollNameHash` + `lastEditStanzaId` сверяются с сохранённым опросом (`C32977EZa.A01`); "unstamped", если отсутствуют; несовпадение отбрасывает голос | `poll_update_tc_drop` |
| Форма голоса | IV ровно 12 (`poll_update_invalid_vote_enc_iv`), payload присутствует, sender timestamp присутствует | ошибка 11 |
| Ответ на событие | ключ, IV (12), payload присутствуют; родитель должен быть событием или sender-revoke сообщением | `parent message is not event message nor sender revoke` |

---

## 8. Привязка отправителя / цели

| Привязано ключом | Эффект |
|------------------|--------|
| id исходного сообщения | ciphertext нельзя повторно использовать на другом сообщении |
| JID целевого отправителя | нельзя приписать другому автору оригинала |
| JID модификатора | нельзя воспроизвести как add-on другого пользователя |
| Строка use case | ciphertext реакции не расшифровывается как голос, комментарий или правка |
| AAD (голос в опросе, ответ на событие) | дополнительно привязывает `targetId` и модификатора к тегу |

Не привязано: JID чата, timestamp, позиция ciphertext в ветке, количество предыдущих add-on. Получатель использует `participant` / `from` конверта как модификатор; он аутентифицируется E2E-сессией, а не секретом. Любой, кто владеет исходным секретом (каждый участник, получивший исходное сообщение, в группе), может вывести ключи для любого модификатора; схема предотвращает перенаправление на стороне relay, но не выдачу себя за другого участниками группы (inferred из конструкции).

---

## 9. Fallback при отсутствии секрета (found, если не помечено иначе)

| Ситуация | Отправитель | Получатель |
|----------|-------------|------------|
| У оригинала нет секрета | шифрование не удаётся (66); legacy-путь опроса: `invalid message_secret secretSize` | родитель есть, секрет null: ошибка **66**, логируется в error reporter с `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` код 0 |
| Секрет не 32 байта | шифрование отклоняется | ошибка **67**, код WAM 1 |
| Родитель не найден | ошибка шифрования 71 | сохраняется как orphan (7.3) |
| Реакция в чате, не являющемся default-подгруппой | вместо этого отправляется plaintext `reactionMessage` (секрет не нужен) | обрабатывается обычной веткой |
| Правка сообщения без флага 17811 | `getUseCase` выбрасывает исключение (`unknown message secret encrypted type`, код 0); избегает ли отправитель этого типа при выключенном флаге — не разрешено | то же исключение |
| Расшифровка add-on не удалась | n/a | add-on остаётся скрытым / недоступным; видимого fallback-текста не найдено (unknown) |
| Новый companion без оригинала | n/a | history sync переносит секрет в `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | устанавливается на сообщениях с информацией о правке (12.3) | сообщает получателю не показывать placeholder о сбое; потребитель флага не разрешён |

---

## 10. Stanza `<message>`: что добавляет клиент

Исходящие дочерние узлы строятся независимыми поставщиками (`InterfaceC35538FaZ`), которые добавляются в построитель stanza `C33150EcP`.

### 10.1 Атрибуты (found)

| Атрибут | Производитель / потребитель | Значения / смысл |
|---------|-----------------------------|------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (из proto): `secretEncryptedMessage` с `EVENT_EDIT` -> `event`, с `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` проваливается в `text` / `media`; поля реакции (обычные или enc) -> `reaction`; обновление / создание опроса -> `poll`; `encEventResponseMessage` и событие -> `event` |
| `edit` | спецификации приёма `C33474Ehg` (требует тег узла `status`; его связь с обычной stanza `<message>` не разрешена), `C23206A1f` (newsletter); acks `AbstractC33465EhX.A05` | `1`, `7`, `8` в `C33474Ehg`; `3` и `8` в спецификации newsletter; acks возвращают его, если не `0` / пусто; см. 10.2 |
| `category` | stanza, acks, retry receipts | `peer` выбирает путь peer-сообщений |
| `device_fanout` | `F6M` | `"false"` при целевых повторах one-to-one |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | транспорт | идентичность / жизненный цикл, не содержимое |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | парсеры идентичности (`AbstractC33466EhY`, `C34763F6g`) | алиасы PN / LID / username |

### 10.2 Значения `edit`

| Значение | Контекст | Уровень |
|----------|----------|---------|
| `1` | правка отправленного сообщения (разбирается в `C33474Ehg.A0L`) | found |
| `2` | pin в чате: путь приёма требует внутреннюю версию правки 2 (`Invalid edited version`) | inferred сопоставление с атрибутом |
| `3` | правка сообщения newsletter: разбирается только в спецификации newsletter (`C23206A1f.A0G`), и `EWW.A01` устанавливает версию правки 3, когда чат — newsletter (JID type 21, сервер `newsletter`) | found (это разрешает прежнее "unknown 3") |
| `7` | revoke отправителем (`C33474Ehg.A0M`) | found |
| `8` | удаление администратором (`C33474Ehg.A0S`, спецификация newsletter `A0H`) | found |
| `0` / пусто | обычное сообщение; в acks опускается | found |

Внутренняя версия правки (`EWW.A01`) равна `1` для обычных чатов и `3` для newsletter; правки в обычных чатах также устанавливают флаг скрытия `decrypt-fail` (12.3).

### 10.3 Прямые дочерние узлы (found)

| Дочерний узел | Производитель | Смысл |
|---------------|---------------|-------|
| `enc` | слой шифрования | ciphertext, см. раздел 11 |
| `participants` / `to` | `F6E` и fanout | ciphertext для каждого устройства |
| `device-identity` | `F6B` | подписанная идентичность устройства |
| `registration` | парсер `C33474Ehg.A04` | ровно 4 байта |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | не более AB int **20606** на stanza, включается **20605** |
| `cstoken` | `F6G` | токен холодного контакта |
| `padding` | `F6H` | случайные байты длиной `retryCount × 1571`, флаги **8311**, **9209** (`ta_pad` тоже присутствует) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (16-байтный HMAC), см. [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | раздел 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | бизнес-процессор `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | пустые флаговые узлы из битовой маски в построителе: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | парсер | непрозрачная бинарная категория (status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` при отправке на JID type 3 (список рассылки, inferred), флаги **16656** (отправлять) и **13537** (значение) |
| `verified_name` | business | сертификат верифицированного бизнеса |
| `unavailable`, `bypassed` | парсер | маркерные узлы; литерал `unavailable` в 2.26.41.6 не найден (на основе констант), семантика здесь не проверена |

---

## 11. Узел `<enc>`

### 11.1 Атрибуты (found, `AbstractC33466EhY.A09`)

| Атрибут | Значение | Условие |
|---------|----------|---------|
| `v` | `2` или `3` | версия ciphertext (парсер приёма принимает `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | сообщение Signal, prekey-сообщение, sender key, `frskmsg`, bot `msmsg`, маркер plaintext |
| `count` | счётчик повторов | опускается при 0 |
| `mediatype` | см. 11.2 | классификация media / interactive |
| `native_flow_name` | имя flow | native-flow сообщения |
| `duration` | int >= 0 | live location |
| `decrypt-fail` | `hide` | сообщение помечено как скрываемое (12.3) |
| `state` | `false` | отправки `pkmsg` под флагом в носителе ciphertext |
| `session_type` | `pq` | флаг носителя post-quantum сессии |
| `bucket` | string | когда задан в носителе ciphertext |

Проверки при приёме (`C33013EaB`): два узла `<enc>` в одном сообщении должны совпадать по счётчику повторов и версии ciphertext; `enc` в newsletter отклоняется (`Received enc message for newsletters`); `decrypt-fail=hide` учитывается только когда категория не `peer` и предикат чата `C1ZB.A0L` равен false.

### 11.2 Значения `mediatype`, принимаемые спецификацией (found, 37 записей)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. Enum `native_flow_name` (8 записей): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. Узел `<meta>`

Все атрибуты и дочерние узлы накапливаются в `EZV` обработчиками, которые вызывает `F6K` (по классу сообщения `FXq.AAl`, по add-on `FZH.AAl`), и выдаются как один `<meta>` (`C33150EcP.A00`). Пустой аккумулятор ничего не выдаёт.

### 12.1 Классификаторы операций (found)

| Атрибут | Значения | Производитель |
|---------|----------|---------------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | обработчики опросов |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | обработчики событий |
| `content_type` | `add_on` для класса add-on `AbstractC35181aQ` (включает реакции; голоса / ответы — inferred) в чатах, где `C0DZ.A0U` равен false; `status_notify` / `add_on` для уведомлений status | `F6K` |
| `type` | `scheduled_message` с `st` (секунды, опускается для класса сообщения unschedule) и дочерним `<key rkid="...">` (байты ключа опускаются для этого класса) | `F6K`, conditional reveal |
| `appdata` | свободная строка из `FZF.AVN()`; правка appdata отклоняется | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | сообщение member-tag `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (и другие) | `AJR` |
| `message_association_type` | токен ассоциации, плюс `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` при загрузках status | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | id / JID родителя | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; дочерний `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, плюс строки точек входа Meta AI (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` для чатов 1:1 под флагом **36091** (смысл не разрешён) | `F6K` |
| `view_once` | `true` для типов view-once под флагом **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (сообщение типа 108) | `F6K` |
| `share_pn` | `true` (сообщение типа 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | маршрутизация bot / thread | `F6K` |

### 12.2 Разбирается при приёме (found)

Входы `<meta>`, которые читает клиент: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (только групповые чаты), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (секунды, хранится в мс), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, и дочерние `mention_source/to`, `mentioned_users/to`. Meta newsletter добавляют `admin_profile`, `paid_partnership`, `ai_content` (перечислены из прежнего каталога; здесь заново не читались, unverified). `deprecated_lid_session` в 2.26.41.6 не найден.

---

## 13. `<biz>`, `<bot>`

### 13.1 `<biz>` (found, `C34748F5r.CM3`)

```xml
<biz native_flow_name="...">                       <!-- or -->
<biz>
  <interactive type="native_flow">
    <native_flow name="..."/>
  </interactive>
  <buttons/> | <list/>
</biz>
<hsm category="..." tag="..."/>                    <!-- sibling, template classification -->
```

Получатель читает имя flow (`native_flow_name` или вложенный `name`), затем классифицирует: присутствует `buttons`, присутствует `list` или native flow; при наличии имени и соседнего `hsm` сообщение становится шаблоном. Сбои валидации называются `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: классификатор `biz`, не согласующийся с зашифрованным payload, — это сбой валидации, а не другой тип сообщения. Прочие атрибуты `biz`, читаемые в других местах: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, дочерний `quality_control` с `decision_source`.

### 13.2 `<bot>` (found)

Исходящие (`F6M`): атрибуты `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, дочерний `tee_routing` (`tee_routing_token`, `tee_ik_id`). Входящие (`C34747F5q`): `<bot edit="full|...">` по умолчанию `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; без `<meta target_id>` сообщение не обрабатывается как ответ bot. Подробности: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Связанные схемы, не относящиеся к message-secret

### 14.1 Conditional reveal (запланированные сообщения)

`conditionalRevealMessage` (поле **120**) использует отдельный случайный ключ раскрытия (`<meta type="scheduled_message" st><key rkid>`); раскрытием управляет сервер. Нет HKDF от `messageSecret`. Внутреннее устройство протокола раскрытия не прослежено (unknown).

### 14.2 Reporting token

`reportingTokenVersion` (поле **8**) и 16-байтный `<reporting_token>` используют ключ нативного use case id 5 (3.4), а не Java HKDF. Содержимое токена: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Проверка поддержки на companion (found)

`CompanionSupportVerifier` (`C34757F6a`, только на companion, за флагом): не-`peer` сообщения принимаются, только если `type` входит в `{text, media, reaction, poll, event}` (или `pay` с дочерним `transaction` / `pay` типа remittance) и каждый прямой дочерний узел входит в `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. Иначе логируется `unsupported child node=` / `unsupported message type=` и сообщение классифицируется на companion как неподдерживаемое. Peer broadcast с `participants` на companion отбрасывается (`received peer broadcast message on companion-mode, dropping`, nack 415 / 18). Новый дочерний `cap` и `tctoken` / `cstoken` в списке отсутствуют; где они обрабатываются до этой проверки, не разрешено. `unavailable` и `participants` идут своими путями.

---

## 16. Feature flags (id как прочитаны в местах вызова; имена не разрешены)

| ID | Тип | Что контролирует |
|----|-----|------------------|
| **6772** | bool | голос в опросе: общий helper против legacy inline-шифрования |
| **31593** | bool | проставление `metadata` голоса в опросе |
| **17811** | bool | use case `Message Edit` (отправка и приём) |
| **37948**, **35457** | bool | условия обёртывания правок собственных сообщений |
| **24886** | int | приём правки опроса (0 = отклоняется, 10016) |
| **25758** | int | приём добавления варианта в опрос (0 = отклоняется, 10017) |
| **15791** | bool | преобразование модификатора ответа на событие LID -> PN в чатах 1:1 |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | генерация секрета по классу чата |
| **8860** | int | максимальная версия reporting-token (генерация секрета) |
| **24741** | bool | секрет для сообщения типа 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | дочерний `cap` и его значение |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool / int | включение `tctoken` / лимит на stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, исходники прочитаны, ничего не тестировалось)

Только факты, прочитанные в `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`.

| Тема | Baileys | Android |
|------|---------|---------|
| Ключ | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | идентично (3.1) |
| Use cases | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, плюс `Message Schedule` для enum 3 | те же строки; значение 3 в 2.26.41.6 не определено |
| AAD | `id\0modifier` для опроса и события, пусто для правки / комментария / реакции | то же |
| Идентичность | пробует кандидатов PN и LID для creator и modifier, GCM аутентифицирует верную пару | та же идея (7.2) |
| Отсутствующий секрет | логирует, отдаёт сырое обновление `encReactionMessage` / `pollUpdateMessage`, без расшифровки | сохраняется как orphan |
| Генерация секрета | `randomBytes(32)` для опроса, события и когда `messageContextInfo.messageSecret` отсутствует | 2.2 |
| Ключ reporting | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; reporting пропускается для реакций, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | нативный id 5 (3.4) |
| Сторона отправки | в прочитанных файлах не найдено отправителя для `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` или `encCommentMessage` | Android отправляет все четыре |

Вывод, прочитанный из кода: Baileys может расшифровывать получаемые продолжения, но в прочитанных файлах шифрования для них нет. Существует ли send-helper в другом месте, не искали.

---

## 18. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| Ошибка 11 | IV не 12 байт либо пустой payload / отсутствует поле | проверить `encIv` (поле 3, или 2 для `PollEncValue`) |
| Ошибка 51 | неверное пространство имён JID отправителя / цели (PN vs LID), неверный исходный id | повторить в обоих пространствах имён, использовать id исходного (неотредактированного) сообщения |
| Голос за отредактированный опрос не проходит | id ключа должен быть id исходного опроса, а не последней правки | определить исходный ключ |
| Комментарий от отправителя PN не проходит | расшифровка комментария требует отправителя LID | использовать LID |
| Правка опроса / добавление варианта отклонено | флаги **24886** / **25758** выключены, либо `polltype` в stanza не согласуется с `secretEncType` | отправлять согласованные `<meta polltype>` и тип |
| Сообщение игнорируется на companion | неизвестный дочерний узел или `type` | придерживаться allowlist (раздел 15) |
| Сообщение `<biz>` не поддерживается | классификатор не согласуется с payload | выводить классификатор из payload |

---

## 19. Ключевые различия

| Это | Не это |
|-----|--------|
| `messageSecret` (на сообщение, случайный, 32 байта) | media key, sender key, ключ app-state sync, ключ звонка |
| Ключ use case (HKDF, на цель / пользователя / use case) | сам секрет |
| `secretEncryptedMessage` (оборачивает полный `Message`) | `encReactionMessage` (оборачивает `ReactionMessage`) |
| AAD `Poll Vote` / `Event Response` = id + NUL + модификатор | правка / комментарий / реакция с пустым AAD |
| `targetMessageKey` во внешнем носителе | `ReactionMessage.key` внутри plaintext (очищается при отправке) |
| `meta polltype` / `event_type` (классификатор) | зашифрованный payload (содержимое) |
| атрибут stanza `edit` | `secretEncType` (use case шифрования) |
| `decrypt-fail="hide"` на `<enc>` | retry receipt / узел `retry` |

---

## 20. Полный flow (голос в опросе, 1:1 или группа)

```
[Creator]                                            [Server]                      [Voter]
   │ poll creation Message                              │                             │
   │ messageContextInfo.messageSecret = random 32       │                             │
   │ store message_secret[row]                          │                             │
   │ <message type="poll"><meta polltype="creation">────▶────────────────────────────▶ stores secret
   │                                                    │                             │
   │                                                    │      select options (hashes)│
   │                                                    │      secret = store[poll]   │
   │                                                    │      key = HKDF(secret,     │
   │                                                    │        pollId‖creator‖voter │
   │                                                    │        ‖"Poll Vote")        │
   │                                                    │      iv = random 12         │
   │                                                    │      ct = GCM(key, iv,      │
   │                                                    │        PollVoteMessage,     │
   │                                                    │        aad = pollId\0voter) │
   │              <message type="poll"><meta polltype="vote">                         │
   │◀────────────────────────────────────────────────────◀ pollUpdateMessage{key,vote{ct,iv},metadata,ts}
   │ parent found? no -> orphan, keep raw bytes         │                             │
   │ validate end time, enc iv = 12                     │                             │
   │ key = HKDF(secret, pollId‖creator‖voter‖"Poll Vote")                              │
   │ GCM-decrypt, fail -> retry PN/LID pair, else 51    │                             │
   │ check option hashes ⊂ poll options, stamp match    │                             │
   │ apply vote                                         │                             │
```

---

## 21. Неизвестное

| Пункт | Состояние |
|-------|-----------|
| Точные предикаты для `EZN.A01`, `C35201aS.A00`, флагов 3142-3146 | видно ограничение по классу чата, видимый пользователю набор не разрешён |
| Таблица нативных id use case (имена к id, кроме 5 = Report Token) | не читалась |
| Позиция тега GCM и размер ключа AES | выведены из констант и Baileys |
| Полное условие отправки собственного `MESSAGE_EDIT` обёрнутым или обычным (флаги 37948, 35457) | декомпилятор потерял поток управления |
| Смысл `acp="2"`, флага сериализации `A09`, второго поля stanza для poll-add-option | не разрешены |
| Потребитель `decrypt-fail="hide"` в разобранном конверте | флаг переносится в конверт, эффект не прослежен |
| Видимый пользователю результат для навсегда нерасшифровываемого add-on | fallback-текста не найдено |
| `unavailable`, `bypassed`, `deprecated_lid_session` | в 2.26.41.6 заново не проверялись |
