<!-- src-sha1: b8f7c5d44373d4a7bc19be29e7bd26af81a86f85 -->
# WhatsApp Секреты сообщений — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** посообщенческий `messageSecret` (генерация, `MessageContextInfo`, локальное хранилище, синхронизация истории), вывод ключа по случаю использования (HKDF), AES-GCM IV / AAD, зашифрованные дополнения (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, правки `secretEncryptedMessage`), привязка идентичности отправителя/цели и повтор LID/PN, сироты и резервные варианты при отсутствующем секрете, расширения стансы `<message>` (атрибуты, атрибуты `<enc>`, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, дополнение, проверка поддержки companion), флаги функций, сравнение с Baileys

---

## 1. Что это (технически)

Каждое сообщение, которое впоследствии может получить зашифрованное дополнение, несёт случайный 32-байтный секрет в собственной сквозной зашифрованной полезной нагрузке (`MessageContextInfo.messageSecret`). Дополнение (реакция, голос в опросе, ответ на событие, комментарий, правка) шифруется ключом, выведенным из этого секрета, id исходного сообщения, исходного отправителя и модификатора. Сервер передаёт дополнение как обычное E2E-сообщение, но не может его прочитать или перенести на другую цель, пользователя или случай использования без нарушения аутентификации GCM. Все утверждения — статический анализ декомпилированного APK; ничего не было захвачено по протоколу. Уровни: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не разрешено. Обфусцированные имена были повторно разрешены в 2.26.41.6 из стабильных строк (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, строки случаев использования, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

Тот же релиз также определяет расширения стансы `<message>` (раздел 10 и далее): атрибуты и дочерние узлы, которые классифицируют и маршрутизируют сообщение, но не несут его содержимое. Они сгруппированы здесь, потому что `<meta polltype>` / `<meta event_type>` должны согласовываться с зашифрованной секретом полезной нагрузкой (7.4).

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| Помощник криптографии (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` шифрование, `A04` расшифровка (повтор идентичности), `A02` разрешение ключа цели |
| Носители параметров шифрования/расшифровки | `C32833ETl` / `C32854EUg` | данные, отправитель, ключ цели, случай использования / IV, полезная нагрузка, ключи, отправитель |
| Вывод ключа | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, нулевая соль |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | нативное, 16-байтный тег |
| Поставщики AAD | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (нет) | дополнительные данные |
| Генератор секрета | `AbstractC33322EfC.A01` | `SecureRandom`, 32 байта |
| Хранилище секрета (`MessageSecretStore`) / in-memory дополнение | `C35311ad` (таблица `message_secret`) / `C35171aP` на сообщении `C13G` | сохранение и перенос |
| Маппер исходного ключа (`ReferentialKeyUtil`) | `C43661qB.A03` | ключ неотредактированного исходного сообщения |
| Обработчики реакций | `DU8` (отправка), ветка `F2P` (получение) | `reactionMessage` / `encReactionMessage` |
| Голос в опросе / ответ на событие / комментарий | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Зашифрованные секретом правки (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Создание опроса / события (секрет берётся при получении) | `F2N` / `F2M` | читает `messageSecret` в FMessage |
| Proto: контекст / сообщение / ключ | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Выбор `type` стансы | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Участники, формирующие исходящую стансу | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` флаги, `F69` cap, `F6H` дополнение, `F6L` / `F6C` отчётность, `F6G` cstoken, `F6I` tctoken, `F6B` идентичность устройства, `F6X` hsm | строят дочерние элементы `<message>` |
| Аккумулятор `<meta>` | `EZV` (атрибуты `A01`, дочерние элементы `A00`) | один узел `<meta>` |
| Строитель атрибутов `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Проверка поддержки companion | `C34757F6a` + `AbstractC32927EXc` | тип и белый список дочерних элементов |
| Парсеры входящей спецификации | `C33474Ehg` (status / обычный), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | извлечение атрибутов и дочерних элементов |
| Событие ошибки WAM | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. Посообщенческий секрет

### 2.1 Где он находится (found)

`MessageContextInfo` (`C30624DTs`) — поле **35** у `Message` (`C30628DTw`). Релевантные здесь поля:

| Поле | Номер | Тип | Использование |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | подсказка списка устройств (не связано с секретом) |
| `messageSecret` | **3** | bytes (32) | посообщенческий секрет |
| `paddingBytes` | **4** | bytes | дополнение |
| `messageAddOnDurationInSecs` | **5** | uint32 | срок жизни дополнения (pin: для unpin должен быть 0) |
| `botMessageSecret` | **6** | bytes (32) | вариант секрета для бота |
| `botMetadata` | **7** | message | контекст бота |
| `reportingTokenVersion` | **8** | uint32 | версия токена отчётности этого сообщения |
| `messageAddOnExpiryType` | **9** | enum | срок истечения дополнения |
| `messageAssociation` | **10** | message | связь |

Носитель синхронизации истории `WebMessageInfo` (`C30626DTu`) имеет собственное поле `messageSecret` **49** (found), используемое при экспорте сообщений на новое companion-устройство (раздел 2.4).

### 2.2 Генерация (found, условия частично предположены)

Секрет — это `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). Он прикрепляется до сериализации сообщения:

| Место | Условие |
|-------|-----------|
| `C33166Ecf.A06` (подготовка отправки) | у сообщения нет секрета и хотя бы одно из: класс опроса `C13J`; `EZN.A01(msg)` (класс бот/дополнение, с флагами типа чата **2200**, **11104**, **19303**); ограничения по классу чата: группа с флагом **3143**, список рассылки с **3144**, статус с **3145**, ограничение по классу **3146**; `C35201aS.A00` (флаг **3142**, собственный/бот-чат); сообщение события `C213509Ao` |
| `AJ0` (процессор отправки) | версия токена отчётности `C35241aW.A05()` (AB int **8860**, ограничено `AbstractC35301ac.A00`) не нулевая, и класс сообщения не исключён `C35241aW.A02` (статус, newsletter, отдельные классы дополнений) |
| `C72h`, `C34455Exe`, `EPA` | объекты статуса (`AbstractC34478Ey1.A0R`) получают свежий секрет при создании |
| `C33437Eh4` | сообщение бота "request welcome", только когда его вызывающий запрашивает |
| `C9mW` | тип сообщения 117, флаг **24741**, когда секрета нет |

Предикаты за `EZN.A01`, `C35201aS.A00` и ограничениями `3142`..`3146` не полностью разрешены; список выше показывает, что код проверяет, а не какие видимые пользователю сообщения подходят. Сообщения без секрета не могут получить от этого клиента зашифрованные дополнения (раздел 9).

### 2.3 Локальное хранение (found)

`C35311ad` записывает `message_secret(message_row_id, message_secret)` с семантикой replace (`MessageSecretStore/insertMessageSecret`) и читает последнюю строку для `message_row_id`. FMessage хранит его как дополнение `C35171aP` (`A0L` установка, `A0c` получение, `A0Q` = непусто). Два процессора в `AbstractC17240jU` (`C35161aO` и один анонимный) записывают его, когда дополнение "грязное" и чат подходит.

### 2.4 Валидация и перенос на стороне получения (found)

| Шаг | Поведение |
|------|------|
| Валидатор proto `C33475Ehh.A0V` | `message_secret` должен быть ровно **32** байта, код ошибки **67**; вариант для бота (`bot_message_secret`, группа `whatsapp_security`) валидируется так же |
| Создание опроса `F2N` | копирует `messageSecret_` в новый FMessage (`A0L`) |
| Ответы на вопрос статуса `C34838F9e` | та же копия для `statusQuestionAnswerMessage` |
| Экспорт синхронизации истории `C34388EwZ.A00` | записывает сохранённый секрет в `WebMessageInfo.messageSecret` (49) |
| Импорт синхронизации истории `C34388EwZ.C59` | копирует его обратно (`A0L`) |
| Комментарии `C34387EwY` | восстанавливает `MessageContextInfo` из `WebMessageInfo.messageSecret` для треда комментариев |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`) логирует `message_secret_error` **0** = отсутствует (сопоставляется с кодом ошибки 66) или **1** = неверная длина (67) для сообщений, требующих секрет (`AbstractC33322EfC.A00`: имеет флаг и не класс `C35281aa`).

---

## 3. Вывод ключа по случаю использования

### 3.1 Формула (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract с 32-байтной нулевой солью (`AbstractC38971i1.A00(ikm, salt)`), затем цикл expand по RFC 5869. Основы HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) раздел 5.1. 32-байтный вывод используется как ключ AES-256 (предположение из длины; нативный вызов принимает ключ как `byte[]`).

Входные данные:

| Вход | Источник | Примечания |
|-------|--------|-------|
| `originalMessageId` | id ключа цели после `ReferentialKeyUtil` (`C43661qB.A03`) при шифровании; id ключа из proto `targetMessageKey` при расшифровке | для отредактированной цели это **исходный** id сообщения (лог `getOriginalKey`) |
| `targetSender` | автор исходного сообщения: сохранённый отправитель (`C12300aw.A01`) | `UserJid`, без суффикса устройства (уровень типа; строковая форма `user@server` предполагается) |
| `modifier` | автор дополнения: собственный JID аккаунта (`C09A.A0G`, LID, возвращается `CUC()` / `Ash()`) при отправке, JID отправителя конверта при получении | |
| `useCase` | строка из 3.2 | без разделителя между четырьмя компонентами |

Собственный JID — это JID аккаунта LID (`C14080dr`, сервер `lid`, проверка "Invalid LID"). И `AnonymousClass091.Ash()`, и `CUC()` возвращают то же поле.

### 3.2 Строки случая использования (found)

| Случай использования | Носитель | AAD | Литерал Java в 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | нет | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | нет | `F3W` |
| `Event Edit` | `secretEncryptedMessage` тип 1 | нет | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` тип 2 | нет | `F3Y.A00`, только с флагом **17811** |
| `Poll Edit` | `secretEncryptedMessage` тип 4 | нет | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` тип 5 | нет | `F3Y.A00` |
| `WASA` | путь бота (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | двухэтапный, 3.3 |
| `Report Token` | ключ токена отчётности | нативно | нет литерала Java; присутствует в `libwhatsapp.so`, выводится нативно (3.4) |

### 3.3 Вариант для бота / WASA (found, детали предположены)

Для случая использования `WASA` вывод состоит из двух этапов, и на втором нет строки случая использования:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` — это модификатор, а `jidB` — удалённый (чат) JID, который должен быть `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`); id — это текущий ключ сообщения, если присутствует, иначе ключ цели (лямбда `C33285Eeb.A03`). Нативный аналог: `WcmBotMessageSecretAPICreateWithMessageSecret`. Контекст Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Ключ токена отчётности (found / inferred)

`C33364Efs.A06` и `C33421Ego` вызывают `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: нативный объект выводит ключ для id случая использования **5**; сторона Java только передаёт сырые строки JID. Строка `Report Token` существует в нативной библиотеке; сопоставление id 5 с этой строкой предполагается. Токен и загрузка: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. Раскладка AEAD

| Элемент | Значение | Уровень |
|------|-------|------|
| Шифр | AES-GCM, нативно (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; расшифровка `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Ключ | 32 байта из раздела 3 | found |
| IV | **12** случайных байт на каждое шифрование (`SecureRandom`); расшифровка отклоняет любой другой размер | found |
| Тег | 16 байт; константа 16 передаётся в обоих вызовах; позиция (добавлен к шифротексту) предположена из расшифровки Baileys | found / inferred |
| AAD | на каждый случай использования (3.2); `null`, когда поставщик — `C34631F1e` | found |
| Открытый текст | сериализованный внутренний proto (таблица 5) | found |
| Вывод | тройка `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| Пустой результат | лог `encryption values are invalid`, ошибка `Encryption using iJniBridge failed` | found |

Повтор голоса в опросе: если голос уже несёт IV и полезную нагрузку (`C30957Dd6.A03` / `A04`), тот же шифротекст отправляется повторно вместо повторного шифрования (found, устаревшая ветка `DUA`).

---

## 5. Носители и открытые тексты

| Носитель (поле в `Message`) | Класс | Поля | Расшифрованный открытый текст |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (очищается перед шифрованием), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (repeated bytes, хэши вариантов) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown, 1 going, 2 not going, 3 maybe), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | полный `Message` (тело комментария); форма открытого текста — `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | полный `Message` |
| `reactionMessage` **46** | `DSH` | форма открытого текста | обычная реакция |
| `conditionalRevealMessage` **120** | н/д | не схема message-secret (раздел 14.1) | запланированные сообщения |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. Значение 3 в этой сборке не существует (`forNumber(3)` возвращает null, обрабатывается как unknown и отклоняется).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Сторона отправителя

### 6.1 Общий путь (found, `C33285Eeb.A03`)

1. Разрешить целевое FMessage по ключу (`target message not found. Cannot proceed further` -> ошибка 71).
2. Прочитать его секрет из `message_secret`; null или длина != 32 -> `message secret missing or invalid` (66).
3. Исходный ключ через `C43661qB.A03` (null -> ошибка 0). Отправитель цели через `C12300aw.A01`.
4. В чате 1:1 (`C0DZ.A0k(chat)`) отправитель цели конвертируется в пространство имён модификатора: модификатор LID и цель PN -> цель сопоставляется с PN в LID; модификатор PN и цель LID -> цель сопоставляется с LID в PN. В группах без конверсии.
5. Только Event Response: флаг **15791**, чат 1:1 и модификатор типа аккаунта -> модификатор конвертируется в PN.
6. Случайный 12-байтный IV, вывод ключа (3.1), AES-GCM с AAD случая использования.
7. Построить внешний `MessageKey` из отправителя цели и исходного ключа (`C32717EOy.A01`); носитель хранит `targetMessageKey`, `encIv`, `encPayload`.

### 6.2 На каждый носитель (found)

| Носитель | Ограничение при отправке |
|---------|--------------|
| Реакция (`DU8.ADr`) | шифруется **только** если чат — группа (`C0DZ.A0l`) с `group_type == 3` (`C0GQ.A0A`; устанавливается в `CMP` из `isDefaultSubgroup_`, т.е. подгруппа по умолчанию сообщества, интерпретация предположена) и флаг контекста сериализации `A09` ложен. В любом другом чате отправляется обычный `reactionMessage`. `ReactionMessage.key` обнуляется перед шифрованием (ключ переносится во внешний `targetMessageKey`) |
| Голос в опросе (`DUA.ADr`) | флаг **6772** включён: общий помощник, всегда шифруется; выключен: устаревшая встроенная ветка с тем же выводом и AAD (отправитель цели = собственный LID для собственных опросов, иначе JID, выводимый из ключа цели голоса; модификатор = собственный LID). `metadata` (`pollNameHash`, опциональный `lastEditStanzaId`) ставится, когда включён флаг **31593** |
| Ответ на событие (`DU9.ADr`) | всегда шифруется; открытый текст `EventResponseMessage` имеет `response`, `timestampMs`, `extraGuestCount` |
| Комментарий (`F3W.ADr`) | всегда шифруется; открытый текст — это весь `Message` комментария; цель — родительский ключ `CommentMessageInfo` |
| Зашифрованная секретом правка (`F3Y.C5S`) | только когда у сообщения есть информация о правке типа `E2Q` и контекст сериализации не является пересланным/сиротой; `MESSAGE_EDIT` дополнительно требует флаг **17811** (иначе `getUseCase` бросает исключение). Для правок собственных сообщений две строки лога (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) показывают случаи, отправляемые как обычные правки; полное условие (флаги **37948**, **35457**) было потеряно при декомпиляции |

Вложенные зашифрованные секретом полезные нагрузки отклоняются с обеих сторон (`nested_secret_encrypted_message`).

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

`senderUserJid` (модификатор) на каждый носитель: собственный LID, когда конверт от меня; опрос: JID отправителя (`c0df` или `B4g()`); ответ на событие: пользователь чата в 1:1, иначе пользователь конверта; комментарий: только LID (`C0DZ.A0Y`: типы 18, 19, 25), отправитель PN завершается ошибкой 0; реакция: отправитель конверта, только если это LID, иначе null.

### 7.2 Повтор идентичности LID / PN (found структура, конец предположен)

Первая попытка использует JID как заданы. При сбое помощник сопоставляет оба JID в другое пространство имён (`C0YH.A0I` LID->PN, `A0F` PN->LID) и повторяет один раз; если оба уже были LID или маппинг отсутствует, результат — ошибка **51** (расшифровка не удалась). Декомпилированный конец повтора частично потерян, так что точный набор опробованных пар предположен. Проверка — это аутентификация GCM: неверная пара не проходит, правильная расшифровывается.

### 7.3 Родитель отсутствует: сироты (found)

| Носитель | Поведение, когда родитель не найден или является заглушкой |
|---------|-----------------------------------------------------------|
| Реакция | FMessage типа **56** хранится с сырыми байтами `Message` (`DdA(key, 56, ts).A02`); расшифровка отложена |
| Голос в опросе | `C30957Dd6.A02 = Message.toByteArray()`; хранится нерасшифрованным |
| Ответ на событие | хранится `Dd7(key, target, bytes, ts)`, нерасшифрованным |
| Комментарий | заглушка `C34671Zb` с ключом родителя и строкой `-1` |
| Зашифрованная секретом правка | `DeD(MessageOrphan)` с типом сироты **5**, причина **1** (родитель отсутствует) или **2** (заглушка) |

Повторное воспроизведение при появлении родителя ожидается (сироты сохраняются с сырыми байтами), но триггер повторного воспроизведения не трассирован (inferred).

### 7.4 Валидация после расшифровки (found)

| Случай | Проверка | Сбой |
|------|-------|---------|
| Станса `type=poll` + `<meta polltype="edit">` | `secretEncType` должен быть `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | тип `POLL_ADD_OPTION` и второе поле стансы, равное `poll_add_option` (поле не разрешено) | `poll_add_option_stanza_invalid` (76) |
| Правка события | тип внутреннего сообщения 92, получившийся ключ равен внешнему ключу | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Правка опроса | внутренний тип 66, оба сообщения — опросы, то же время окончания и флаги, правки вариантов согласуются с сохранёнными вариантами, метка времени не после времени окончания | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Добавление варианта опроса | внутренний тип 137, родитель — опрос, ключ цели равен внешнему ключу, не после времени окончания | `poll_add_option_past_end_time` |
| Получение правки опроса | AB int **24886** должен быть не нулём | ошибка 10016 ("futureproofing") |
| Получение добавления варианта опроса | AB **25758** должен быть не нулём | ошибка 10017 |
| Голос в опросе | выбор должен быть валиден для опроса (`AbstractC33199EdC.A02`); метка времени голоса не после времени окончания опроса | `poll_update_past_end_time`, `invalid poll vote selection` |
| Метаданные голоса в опросе | `pollNameHash` + `lastEditStanzaId` проверяются против сохранённого опроса (`C32977EZa.A01`); "unstamped" при отсутствии; несовпадение отбрасывает голос | `poll_update_tc_drop` |
| Форма голоса в опросе | IV ровно 12 (`poll_update_invalid_vote_enc_iv`), полезная нагрузка присутствует, метка времени отправителя присутствует | ошибка 11 |
| Ответ на событие | ключ, IV (12), полезная нагрузка присутствуют; родитель должен быть сообщением события или sender-revoke | `parent message is not event message nor sender revoke` |

---

## 8. Привязка отправитель / цель

| Привязано ключом | Эффект |
|------------------|--------|
| Id исходного сообщения | шифротекст не может быть повторно использован для другого сообщения |
| JID отправителя цели | не может быть приписан другому исходному автору |
| JID модификатора | не может быть повторно воспроизведён как дополнение другого пользователя |
| Строка случая использования | шифротекст реакции не расшифровывается как голос, комментарий или правка |
| AAD (голос в опросе, ответ на событие) | дополнительно привязывает `targetId` и модификатор к тегу |

Не привязано: JID чата, метка времени, позиция шифротекста в треде, число предыдущих дополнений. Конверт `participant` / `from` — это то, что получатель использует как модификатор; это аутентифицируется сессией E2E, а не секретом. Любой, владеющий исходным секретом (каждый участник, получивший исходное сообщение, в группе), может вывести ключи для любого модификатора; схема предотвращает ретаргетинг на стороне ретрансляции, а не имперсонацию участниками группы (предположено из конструкции).

---

## 9. Резервные варианты при отсутствующем секрете (found, если не отмечено иначе)

| Ситуация | Отправитель | Получатель |
|-----------|--------|----------|
| У исходного нет секрета | шифрование не удаётся (66); устаревший путь опроса: `invalid message_secret secretSize` | родитель присутствует, секрет null: ошибка **66**, логируется в репортер ошибок с `parentMsgRowId`, `parentType`, `parentHasSecret`; `wam_message_secret_errors` код 0 |
| Секрет не 32 байта | шифрование отклонено | ошибка **67**, код WAM 1 |
| Родитель не найден | ошибка шифрования 71 | сохраняется как сирота (7.3) |
| Реакция в чате не являющемся подгруппой по умолчанию | вместо этого отправляется открытый `reactionMessage` (секрет не нужен) | обрабатывается обычной веткой |
| Правка сообщения без флага 17811 | `getUseCase` бросает исключение (`unknown message secret encrypted type`, код 0); избегает ли отправитель этого типа, когда флаг выключен — не разрешено | то же исключение |
| Расшифровка дополнения не удаётся | н/д | дополнение остаётся скрытым/недоступным; видимого текста резервного варианта не найдено (unknown) |
| Новое companion-устройство без исходного | н/д | синхронизация истории несёт секрет в `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | устанавливается на сообщениях с информацией о правке (12.3) | говорит получателю не показывать заглушку сбоя; потребитель флага не разрешён |

---

## 10. Станса `<message>`: что добавляет клиент

Исходящие дочерние элементы строятся независимыми участниками (`InterfaceC35538FaZ`), которые добавляют их к строителю стансы `C33150EcP`.

### 10.1 Атрибуты (found)

| Атрибут | Производитель / потребитель | Значения / смысл |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (из proto): `secretEncryptedMessage` с `EVENT_EDIT` -> `event`, с `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`; `MESSAGE_EDIT` проваливается до `text` / `media`; поля реакции (обычные или зашифрованные) -> `reaction`; обновление/создание опроса -> `poll`; `encEventResponseMessage` и событие -> `event` |
| `edit` | спецификации получения `C33474Ehg` (требует тег узла `status`; его отношение к обычной стансе `<message>` не разрешено), `C23206A1f` (newsletter); квитанции `AbstractC33465EhX.A05` | `1`, `7`, `8` в `C33474Ehg`; `3` и `8` в спецификации newsletter; квитанции отражают это, если не `0` / пусто; см. 10.2 |
| `category` | станса, квитанции, квитанции повтора | `peer` выбирает путь сообщения-между-устройствами |
| `device_fanout` | `F6M` | `"false"` на целевых повторах один-к-одному |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | транспорт | идентичность / жизненный цикл, не содержимое |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | парсеры идентичности (`AbstractC33466EhY`, `C34763F6g`) | псевдонимы PN / LID / username |

### 10.2 Значения `edit`

| Значение | Контекст | Уровень |
|-------|---------|------|
| `1` | правка отправленного сообщения (разбирается в `C33474Ehg.A0L`) | found |
| `2` | закрепление в чате: путь получения требует внутреннюю версию правки 2 (`Invalid edited version`) | сопоставление с атрибутом предположено |
| `3` | правка сообщения newsletter: разбирается только в спецификации newsletter (`C23206A1f.A0G`), и `EWW.A01` устанавливает версию правки 3, когда чат — newsletter (тип JID 21, сервер `newsletter`) | found (это разрешает более раннее "неизвестное 3") |
| `7` | отзыв отправителем (`C33474Ehg.A0M`) | found |
| `8` | удаление администратором (`C33474Ehg.A0S`, спецификация newsletter `A0H`) | found |
| `0` / пусто | обычное сообщение; пропускается в квитанциях | found |

Внутренняя версия правки (`EWW.A01`) — `1` для обычных чатов и `3` для newsletter; правки обычных чатов также устанавливают флаг скрытия `decrypt-fail` (12.3).

### 10.3 Прямые дочерние элементы (found)

| Дочерний элемент | Производитель | Значение |
|-------|----------|---------|
| `enc` | слой шифрования | шифротекст, см. раздел 11 |
| `participants` / `to` | `F6E` и fanout | шифротексты на устройство |
| `device-identity` | `F6B` | подписанная идентичность устройства |
| `registration` | парсер `C33474Ehg.A04` | ровно 4 байта |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | максимум AB int **20606** на стансу, включено **20605** |
| `cstoken` | `F6G` | токен холодного контакта |
| `padding` | `F6H` | случайные байты, длина `retryCount × 1571`, флаги **8311**, **9209** (также присутствует `ta_pad`) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (16-байтный HMAC), см. [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | раздел 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | бизнес-процессор `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | пустые узлы-флаги из битовой маски в строителе: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | парсер | непрозрачная бинарная категория (статус) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` при отправке на JID типа 3 (список рассылки, предположение), флаги **16656** (эмиссия) и **13537** (значение) |
| `verified_name` | бизнес | сертификат верифицированного бизнеса |
| `unavailable`, `bypassed` | парсер | маркерные узлы; литерал `unavailable` в 2.26.41.6 не совпал (основано на константе), семантика здесь не проверена |

---

## 11. Узел `<enc>`

### 11.1 Атрибуты (found, `AbstractC33466EhY.A09`)

| Атрибут | Значение | Условие |
|-----------|-------|-----------|
| `v` | `2` или `3` | версия шифротекста (парсер получения принимает `EncVersion2`, `EncVersion3`, futureproof) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | сообщение Signal, prekey-сообщение, sender key, `frskmsg`, бот `msmsg`, маркер открытого текста |
| `count` | счётчик повторов | пропускается при 0 |
| `mediatype` | см. 11.2 | классификация медиа / интерактивности |
| `native_flow_name` | имя потока | сообщения native-flow |
| `duration` | int >= 0 | живая геолокация |
| `decrypt-fail` | `hide` | сообщение помечено как скрываемое (12.3) |
| `state` | `false` | отправка `pkmsg` под флагом в носителе шифротекста |
| `session_type` | `pq` | флаг постквантовой сессии носителя |
| `bucket` | string | когда установлен на носителе шифротекста |

Проверки получения (`C33013EaB`): два узла `<enc>` в одном сообщении должны согласовываться по счётчику повторов и версии шифротекста; `enc` в newsletter отклоняется (`Received enc message for newsletters`); `decrypt-fail=hide` учитывается только когда категория не `peer` и предикат чата `C1ZB.A0L` ложен.

### 11.2 Значения `mediatype`, принимаемые спецификацией (found, 37 записей)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. Enum `native_flow_name` (8 записей): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. Узел `<meta>`

Все атрибуты и дочерние элементы накапливаются в `EZV` обработчиками, которые вызывает `F6K` (на класс сообщения `FXq.AAl`, на дополнение `FZH.AAl`), и выдаются как один `<meta>` (`C33150EcP.A00`). Пустой аккумулятор ничего не выдаёт.

### 12.1 Классификаторы операции (found)

| Атрибут | Значения | Производитель |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | обработчики опроса |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | обработчики события |
| `content_type` | `add_on` для класса дополнения `AbstractC35181aQ` (включает реакции; голоса/ответы предположены) в чатах, где `C0DZ.A0U` ложен; `status_notify` / `add_on` для уведомлений статуса | `F6K` |
| `type` | `scheduled_message` с `st` (секунды, пропускается для класса сообщения unschedule) и дочерним `<key rkid="...">` (байты ключа пропускаются для этого класса) | `F6K`, условное раскрытие |
| `appdata` | произвольная строка `FZF.AVN()`; редактирование appdata отклоняется | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | сообщение метки участника `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (и другие) | `AJR` |
| `message_association_type` | токен связи, плюс `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` при загрузках статуса | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | id / JID родителя | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; дочерний `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, плюс строки точки входа Meta AI (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | `2` для чатов 1:1 под флагом **36091** (значение не разрешено) | `F6K` |
| `view_once` | `true` для типов однократного просмотра под флагом **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (тип сообщения 108) | `F6K` |
| `share_pn` | `true` (тип сообщения 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | маршрутизация бота / треда | `F6K` |

### 12.2 Разбирается при получении (found)

Входные данные `<meta>`, которые читает клиент: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (только групповые чаты), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (секунды, хранится в мс), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, и дочерние элементы `mention_source/to`, `mentioned_users/to`. Meta newsletter добавляют `admin_profile`, `paid_partnership`, `ai_content` (перечислено из более раннего каталога; здесь не перепроверено, не подтверждено). `deprecated_lid_session` подтверждён как отсутствующий на 2.26.45.10: исчерпывающий регистронезависимый grep по всему декодированному дереву 2.26.45.10 и WA Business 2.26.45.7 не нашёл точного или близкого совпадения (`found`); предполагается как намеренное удаление переходного флага миграции PN→LID, не переименование (`inferred`).

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

Получатель читает имя потока (`native_flow_name` или вложенное `name`), затем классифицирует: присутствует `buttons`, присутствует `list`, или native flow; с именем и соседом `hsm` это становится шаблоном. Сбои валидации называются `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: классификатор `biz`, не согласующийся с зашифрованной полезной нагрузкой — это сбой валидации, а не иной тип сообщения. Другие атрибуты `biz`, читаемые в другом месте: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, дочерний `quality_control` с `decision_source`.

### 13.2 `<bot>` (found)

Исходящий (`F6M`): атрибуты `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, дочерний `tee_routing` (`tee_routing_token`, `tee_ik_id`). Входящий (`C34747F5q`): `<bot edit="full|...">` по умолчанию `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; без `<meta target_id>` сообщение не обрабатывается как ответ бота. Детали: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Связанные схемы, не относящиеся к message-secret

### 14.1 Условное раскрытие (запланированные сообщения)

`conditionalRevealMessage` (поле **120**) использует отдельный случайный ключ раскрытия (`<meta type="scheduled_message" st><key rkid>`); сервер управляет раскрытием. Без HKDF от `messageSecret`. Внутренние детали протокола раскрытия не трассированы (unknown).

### 14.2 Токен отчётности

`reportingTokenVersion` (поле **8**) и 16-байтный `<reporting_token>` используют нативный ключ случая использования id 5 (3.4), не Java HKDF. Содержимое токена: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Проверка поддержки companion (found)

`CompanionSupportVerifier` (`C34757F6a`, только на companion, за флагом): сообщения, не являющиеся `peer`, принимаются только если `type` входит в `{text, media, reaction, poll, event}` (или `pay` с дочерним `transaction` денежного перевода / `pay`) и каждый прямой дочерний элемент входит в `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. Иначе он логирует `unsupported child node=` / `unsupported message type=`, и сообщение классифицируется как неподдерживаемое на companion. Peer-широковещательное сообщение с `participants` на companion отбрасывается (`received peer broadcast message on companion-mode, dropping`, nack 415 / 18). Новый дочерний элемент `cap` и `tctoken` / `cstoken` не в списке; где они обрабатываются до этой проверки, не разрешено. `unavailable` и `participants` идут своими собственными путями.

---

## 16. Флаги функций (id, как прочитаны в точках вызова; имена не разрешены)

| ID | Тип | Управляет |
|----|------|----------|
| **6772** | bool | голос в опросе: общий помощник vs устаревшее встроенное шифрование |
| **31593** | bool | проставление `metadata` голоса в опросе |
| **17811** | bool | случай использования `Message Edit` (отправка и получение) |
| **37948**, **35457** | bool | условия для оборачивания правок собственных сообщений |
| **24886** | int | получение правки опроса (0 = отклонено, 10016) |
| **25758** | int | получение добавления варианта опроса (0 = отклонено, 10017) |
| **15791** | bool | модификатор ответа на событие LID -> PN в чатах 1:1 |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | генерация секрета по классу чата |
| **8860** | int | максимальная версия токена отчётности (генерация секрета) |
| **24741** | bool | секрет для типа сообщения 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | дочерний элемент `cap` и его значение |
| **8311**, **9209** | bool | дополнение |
| **20605**, **20606** | bool / int | включение `tctoken` / предел на стансу |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, прочитан исходный код, ничего не проверено)

Только факты, прочитанные в `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`.

| Тема | Baileys | Android |
|-------|---------|---------|
| Ключ | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | идентично (3.1) |
| Случаи использования | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, плюс `Message Schedule` для enum 3 | те же строки; значение 3 не определено в 2.26.41.6 |
| AAD | `id\0modifier` для опроса и события, пусто для правки / комментария / реакции | то же |
| Идентичность | пробует кандидатов PN и LID для создателя и модификатора, GCM аутентифицирует правильную пару | та же идея (7.2) |
| Отсутствующий секрет | логирует, выдаёт сырое обновление `encReactionMessage` / `pollUpdateMessage`, без расшифровки | хранится как сирота |
| Генерация секрета | `randomBytes(32)` для опроса, события и когда `messageContextInfo.messageSecret` отсутствует | 2.2 |
| Ключ отчётности | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; отчётность пропускается для реакций, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` | нативный id 5 (3.4) |
| Сторона отправки | в прочитанных файлах не найдено отправителя для `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` или `encCommentMessage` | Android отправляет все четыре |

Следствие, прочитанное из кода: Baileys может расшифровывать получаемые дополнения, но прочитанные файлы не содержат шифрования для них. Существует ли помощник отправки в другом месте, не искалось.

---

## 18. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|-------|-----|
| Ошибка 11 | IV не 12 байт или пустая полезная нагрузка / отсутствующее поле | проверить `encIv` (поле 3, или 2 для `PollEncValue`) |
| Ошибка 51 | неверное пространство имён JID отправителя/цели (PN vs LID), неверный исходный id | повторить в обоих пространствах имён, использовать исходный (неотредактированный) id сообщения |
| Голос за отредактированный опрос не удаётся | id ключа должен быть исходным id опроса, не id последней правки | разрешить исходный ключ |
| Комментарий от отправителя PN не удаётся | расшифровка комментария требует отправителя LID | использовать LID |
| Правка опроса / добавление варианта отклонено | флаги **24886** / **25758** выключены, или `polltype` стансы не согласуется с `secretEncType` | отправлять соответствующий `<meta polltype>` и тип |
| Сообщение игнорируется на companion | неизвестный дочерний узел или `type` | придерживаться белого списка (раздел 15) |
| Сообщение `<biz>` не поддерживается | классификатор не согласуется с полезной нагрузкой | выводить классификатор из полезной нагрузки |

---

## 19. Ключевые различия

| Это | Не это |
|------|----------|
| `messageSecret` (на сообщение, случайный, 32 байта) | ключ медиа, sender key, ключ синхронизации состояния приложения, ключ звонка |
| Ключ случая использования (HKDF, на цель / пользователя / случай использования) | сам секрет |
| `secretEncryptedMessage` (оборачивает полный `Message`) | `encReactionMessage` (оборачивает `ReactionMessage`) |
| AAD `Poll Vote` / `Event Response` = id + NUL + модификатор | правка / комментарий / реакция с пустым AAD |
| `targetMessageKey` во внешнем носителе | `ReactionMessage.key` внутри открытого текста (очищается при отправке) |
| `meta polltype` / `event_type` (классификатор) | зашифрованная полезная нагрузка (содержимое) |
| атрибут стансы `edit` | `secretEncType` (случай использования шифрования) |
| `decrypt-fail="hide"` на `<enc>` | квитанция повтора / узел `retry` |

---

## 20. Полный поток (голос в опросе, 1:1 или группа)

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

| Элемент | Статус |
|------|-------|
| Точные предикаты для `EZN.A01`, `C35201aS.A00`, флагов 3142-3146 | ограничение по классу чата наблюдается, видимый пользователю набор не разрешён |
| Таблица нативных id случаев использования (имена в id, кроме 5 = Report Token) | не прочитана |
| Позиция тега GCM и размер ключа AES | предположены из констант и Baileys |
| Полное условие отправки правок собственного `MESSAGE_EDIT` обёрнутыми vs обычными (флаги 37948, 35457) | декомпилятор потерял поток управления |
| Значение `acp="2"`, флага сериализации `A09`, второго поля стансы poll-add-option | не разрешено |
| Потребитель `decrypt-fail="hide"` на разобранном конверте | флаг переносится в конверт, эффект не трассирован |
| Видимый пользователю результат постоянно нерасшифровываемого дополнения | резервного текста не найдено |
| `unavailable`, `bypassed` | не перепроверено в 2.26.41.6 |
| `deprecated_lid_session` | подтверждён как отсутствующий на 2.26.45.10 (исчерпывающий grep, деревья WhatsApp и WA Business); удаление vs. переименование — `inferred`, не доказано |
