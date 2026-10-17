<!-- src-sha1: 2c3f9604f03ccc7f3d3160d18810a86e62b8172f -->
# WhatsApp Linked-Device Pairing — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** сторона основного устройства при привязке companion, поток QR, поток номер телефона / pair-код, станзы `pair-device` и `pair-success`, ключевой материал, подписанная идентичность устройства ADV и список key-index, список устройств и лимиты, отвязка, ошибки, сравнение с Baileys

---

## 1. Что это (технически)

Привязанное устройство (companion) — вторая конечная точка того же аккаунта. Основной телефон авторизует его, создавая подписанную идентичность ADV (account device verification) над identity-ключом companion. Все утверждения основаны на статическом анализе декомпилированного APK; на проводе ничего не захватывалось. Уровни: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не выяснено.

Обфусцированные имена зависят от сборки и были заново определены по стабильным строкам в 2.26.41.6.

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| Оркестратор QR/pair | `C45850K0w` (префикс лога `CompanionDeviceQrHandler`) | разбирает QR, строит протоколы ADV, отправляет `pair-device` |
| Сборщик IQ `pair-device` | `RunnableC46606KYf` | строит IQ |
| Помощник запрос/ответ `pair-device` | `KRI` (`devicePairRequest/*`) | отправка, повтор, разбор `device` / `companion-props` / подсказок retry |
| Маршрутизатор ошибок | `C44661Jem` | сопоставляет код ошибки сервера с callback UI |
| Парсер строки QR | `C45741Jxy` → `C45423Jrn` | payload QR в данные привязки |
| Разобранные данные привязки | `C44423JaU` | ref, ключи companion, adv secret, платформа |
| Утилита ADV | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, key index, timestamp, сборка и подпись key-index-list |
| Обновитель key-index-list | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | отправляет подписанный список на сервер |
| Верификатор ADV | `C24230w2` (`DeviceADVInfoHandler`) | проверяет идентичности и списки, виденные на проводе |
| Обработчик уведомления о списке устройств | анонимный класс в `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | уведомление `devices` |
| Обработчик уведомления link-code | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | id уведомления 252 |
| Менеджер link-code (primary) | `KZ3` (ввод кода, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | поток pair-кода |
| Крипто-утилита link-code | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Менеджер устройств | `C0XQ` (`companion-device-manager`) | список, logout |
| Помощник удаления | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Обёртка кривой Signal | `C38851hm` | провайдер `org.whispersystems.curve25519` "best" |
| Классы proto ADV | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | см. раздел 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `companion-props` в результате `pair-device` |
| Client props | `C43107IrI` | дочерний `client-props` |
| Тип аккаунта/шифрования | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

В UI основного устройства существуют три режима входа (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

Тот же APK содержит и код регистрации в роли companion (конечный автомат `C0YS`, логи `companion/registration/*`). Он вне области; описаны только части, нужные для объяснения того, что получает primary (раздел 9.6).

---

## 2. Пути привязки вкратце

| Путь | Триггер на primary | Primary отправляет | Секрет, связывающий primary и companion |
|------|--------------------|---------------|----------------------------------------|
| QR | сканирование `https://wa.me/settings/linked_devices#<payload>` (или `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` из поля 4 QR |
| Номер телефона + код | `notification` `link_code_companion_reg` stage `companion_hello`, пользователь вводит 8-символьный код | `primary_hello`, позже (после `companion_finish`) тот же `pair-device` | `adv secret`, полученный из двух результатов X25519 плюс random (раздел 4.4) |

Оба пути сходятся в одном объекте `C44423JaU` и одном IQ `pair-device` (found: `KYB` строит `C44423JaU` из пакета `companion_finish` тем же конструктором, который `C45850K0w.A01` использует для QR).

---

## 3. Поток QR (сторона primary)

### 3.1 Payload QR

`C45741Jxy.A01` отбрасывает префикс `https://wa.me/settings/linked_devices#` или `whatsapp://settings/linked_devices#` и URL-декодирует остальное. `A02` делит по `,` (found):

| Idx | Содержимое | Кодирование | Использование |
|-----|---------|----------|-----|
| 0 | `ref` | string | ссылка привязки; ref, начинающийся с `CAPI_`, отклоняется (`invalid ref`) |
| 1 | публичный ключ companion | base64 | отправляется как `pub-key`, salt для ключа nonce (3.4). Имя inferred: статический ключ Noise (`companion_server_auth_key_pub` в пути кода) |
| 2 | identity-ключ companion | base64, 32 байта, парсер добавляет в начало `0x05` (тип Curve25519) | над ним ставится подпись аккаунта |
| 3 | `adv secret` | base64 | ключ HMAC для обёртки ADV |
| 4 | код платформы (необязательно) | один символ | сопоставляется с типом платформы; `j` = hosted-устройство |

- Менее 3 частей: `qrData/processQR/error/invalid_code parts`. Отсутствует identity-ключ или adv secret (старый QR из 3 полей): `invalid qr code, missing companion identity key or adv secret` → локальный код **-9**.
- Таблица символов платформы (не зависит от `EnumC26221BZl`, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Используется только для проверки hosted и логирования (3.2).

### 3.2 Локальные проверки перед отправкой

| Проверка | Код | Локальный код |
|-------|------|------------|
| QR содержит identity-ключ и adv secret | `C45850K0w.A01` | -9 |
| флаг hosted согласован: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| уже выполняется другая привязка (`kri.A0N` или менеджер companion-устройств занят) | `A04` | -17 |
| локальный timestamp ADV валиден (`C24270w6.A00() != -1`) | `A04` | -8 |
| hosted companion | `A04`: `Hosted pairing is not supported` | -10 |
| нужно friction в режиме защиты | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (повтор с challenges) |

Привязка hosted блокируется на стороне клиента в этой сборке (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Перед IQ: очистка syncd и key index

1. Если состояние syncd грязное (`sync-manager/shouldCleanUpSyncdOnPairing`), приложение сначала очищает syncd, затем продолжает (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (в `RunnableC46617KYr`):
   - нет сохранённого rawId или индекса: новый случайный rawId, индекс 1;
   - нет привязанных companion: `rawId + 1`, индекс остаётся 1;
   - companion существуют: `currentIndex + 1`; при переполнении rawId + 1 и выполняется logout всех устройств (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (раздел 5.4).

### 3.4 Что строится

В `C45850K0w.A00`, где `E` = identity-ключ companion (32 Б, сырой), `P` = пара identity-ключей primary (Curve25519), `S` = adv secret:

| Шаг | Операция | Уровень |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | подпись аккаунта = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; префикс `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` оставлена пустой: её добавляет companion) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = сериализованный шаг 3, hmac = HMAC-SHA256(key = S, data = байты шага 3), accountType}`; для hosted данные — `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) из `C24270w6.A01`, подписан `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | ключ nonce `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, обёрнут как дочерний `pem` | found (вывод); назначение inferred |
| 7 | необязательный `encryption-metadata` (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, из `AuthProofHelper` (шифрование пароля аккаунта, метка `rsa2048`) | found (структура); что это доказывает, unknown |
| 8 | необязательный `client-props` (`C43107IrI`, раздел 3.6) | found |

Деталь по шагу 6: узел `pem` помечен `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 days`, `key_id=1`, но его дочерний элемент несёт `key.getEncoded()` 32-байтного выхода HKDF (`SecretKeySpec` алгоритм `AES-GCM`). Метка и содержимое не совпадают; почему, unknown. Использование сервером — inferred (сервер шифрует nonce устройства для companion; ср. столбец `companion_meta_nonce`).

### 3.5 IQ `pair-device` (primary → сервер)

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <pair-device>
    <ref>…</ref>                                    <!-- QR field 0 -->
    <pub-key>…</pub-key>                            <!-- QR field 1 -->
    <device-identity>ADVSignedDeviceIdentityHMAC</device-identity>
    <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
    <client-props>…</client-props>                  <!-- optional -->
    <pem version="1" algorithm="rsa2048"><pem>…</pem><ttl ts_s="432000"/><key_id>1</key_id></pem>
    <encryption-metadata version="1" algorithm="rsa2048">…</encryption-metadata>   <!-- optional -->
    <companion_qr_origin_source>1|2</companion_qr_origin_source>
    <challenges><supported><friction variant="1"/><passkey-create/></supported>
                <completed>…</completed></challenges>                              <!-- optional -->
  </pair-device>
</iq>
```

Found: все имена дочерних элементов, значение атрибута `ts` (timestamp key-index-list), таймаут **32000 мс** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` равен `1` для значения входа 3 и `2` для значения входа 5 (смысл int входа unknown). Точный порядок дочерних элементов и ветка `companion_qr_origin_source` частично искажены декомпилятором; порядок считать непроверенным.

### 3.6 `client-props` (`C43107IrI`)

| Поле | Номер | Тип | Устанавливается, когда |
|-------|--------|------|------------|
| `isChatDbLidMigrated` | **1** | bool | миграция LID в БД чатов завершена |
| `isSyncdPureLidSession` | **2** | bool | есть флаг syncd pure-LID |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | флаг восстановления |
| `isHsThumbnailSyncEnabled` | **4** | bool | флаг синхронизации миниатюр истории |
| `subscriptionSyncPayload` | **5** | bytes | строится, когда включена md-синхронизация (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | БД bot JID мигрирована |

### 3.7 Обработка результата (`KRI.CFS`)

Дочерние элементы успешного результата (found):

| Дочерний | Использование |
|-------|-----|
| `device` атрибут `jid` | новый `DeviceJid` companion; id устройства **99** сопоставляется с записью платформы hosted |
| `companion-props` | proto `DeviceProps` (`C43105IrG`): `os` **1** (string), `version` **2** (message), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (message) |
| `retry-ts` атрибут `ts` | сервер просит более новый timestamp; приложение повторяет (`RunnableC46585KXj`) |
| `retry-after-challenges` | дочерние `friction` (атрибут `variant`, должен быть `1`, необязательный `location` "lat,lon") или `passkey-create` (атрибут `created`) |
| `retry-with-method` | дочерние `qr-code` или `shortcake-with-passkeys`; если присутствует второй, 32-байтный ключ handoff (HKDF от adv secret, info `shortcake-passkey-handoff-v1`) откладывается (`PairingHandoffKeyHolder`), под управлением abprop |

При успехе приложение сохраняет запись устройства `CJY` (случайная 24-байтная строка base64, `adv_key_index` = текущий индекс, `requireFullSync`), сохраняет timestamp key-index-list как `adv_timestamp_sec` (`C24270w6.A05`) и запускает состояние history sync (`C8N`).

Сбой доставки (`Bog`): до **3** повторов, задержка `3000 * 3^(n-1)` мс (3 с, 9 с, 27 с), если включён флаг retry (found); затем error callback.

---

## 4. Поток номер телефона / pair-код (сторона primary)

### 4.1 Шаги

| # | Направление | Станза / действие | Класс |
|---|-----------|-----------------|-------|
| 1 | companion → сервер → primary | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | primary | сохраняет hello, показывает push-уведомление → `CompanionHelloConfirmationActivity` / экран ввода кода | `C10J`, `C77`, `JYJ` |
| 3 | пользователь | вводит 8-символьный код | `LinkedDevicesEnterCodeActivity` |
| 4 | primary → сервер | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (таймаут 120000 мс) |
| 5 | сервер → primary | `notification` `stage=companion_finish` | `C10J` → `KYB` case 0 |
| 6 | primary → сервер | IQ `pair-device` (раздел 3.5) | `C45850K0w` |
| 7 | другие stage | `refresh_code` (primary просит обновить код, атрибут `force_manual_refresh`) | `C10J` |

### 4.2 Уведомление `companion_hello` (found)

| Дочерний | Использование |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | эфемерный ключ X25519 companion, обёрнутый кодом (4.3) |
| `companion_server_auth_key_pub` | позже становится `pub-key` в `pair-device` |
| `link_code_pairing_ref` | ref сессии (string) |
| `companion_platform_id` | строка id платформы |
| `companion_platform_display` | отображаемое имя |
| атрибут `should_show_push_notification` | `true` → push-уведомление |

Сохраняемое состояние (`C77`/`CE4`, JSON в SharedPrefs `companion_reg_with_link_code_companion_hello_info_json`): ref, id платформы, обёрнутый ключ, серверный ключ auth, срок действия `now + min(360000, flag 3816 * 1000)` мс. Просроченный или отсутствующий hello → "companion hello is null or expired" (состояние UI 2). Более новый hello с другим ref отменяет предыдущий ref (`KRJ.A00(oldRef, "true")`).

### 4.3 Код и крипто-обёртка (found)

| Элемент | Значение |
|------|-------|
| Код | 5 случайных байт → 8 символов по 5 бит, алфавит `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 символа, без `0 I O U`) (`K1T.A00`, генерируется companion) |
| Код → ключ | PBKDF2-HMAC-SHA256, **131072** итераций, 256 бит, пароль = символы кода, salt = первые 32 байта обёрнутого блоба (`K1T.A02`) |
| Обёрнутый эфемерный ключ | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, plaintext = 32-байтный публичный ключ X25519; длина должна быть ≥ 48 |
| Ответ primary | primary создаёт собственную эфемерную пару ключей, оборачивает свой публичный ключ так же (новый salt 32 Б, IV 16 Б, тот же код) |

### 4.4 `primary_hello` и `companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

Дочерние элементы уведомления `companion_finish`: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Обработка на primary в `KYB` case 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (сохраняется во время `primary_hello`).
2. Структура пакета `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, минимум 44 байта.
3. Ключ = HKDF-SHA256(salt = salt пакета, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 Б).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Проверки: identity primary должна равняться собственному identity-ключу; identity companion должна равняться `companion_identity_public` из уведомления; иначе ref отбрасывается и UI получает состояние ошибки.
6. `adv secret = HKDF-SHA256(salt = 32 нулевых байта, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 Б)` (`K1T.A03`).
7. Ключ handoff = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (также сохраняется в `C44423JaU`).
8. `C44423JaU` строится с `pub-key` = `companion_server_auth_key_pub`, identity companion, adv secret → тот же IQ `pair-device`, что и в QR.

Внешний эфемерный ECDH существует (это IKM HKDF на шаге 3). В заметке более ранней сборки сказано "no ECDH in this stage"; для этой сборки это неверно.

Маркеры ошибок на стороне primary: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. Подписанная идентичность устройства ADV

### 5.1 Поля proto (found, из строк раскладки lite-proto)

| Сообщение | Класс | Поле | Номер | Тип |
|---------|-------|-------|--------|------|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | enum (`EnumC32116E1o`) |
| | | `deviceType` | **5** | enum (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (устанавливает companion) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | packed uint32 |
| | | `accountType` | **5** | enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (только hosted) |

Номера полей и wire-типы прочитаны из сгенерированной информации о сообщениях; имена совпадают с каноническими сообщениями ADV. Имена enum: значения `EnumC32116E1o` E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Префиксы подписей и алгоритмы

| Префикс | Константа | Подписываемые / MAC-данные | Подписант | Уровень |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | подпись аккаунта: `‖ details ‖ companion identity pub` | identity-ключ primary | found |
| `06 05` | `A0G` | hosted-вариант подписи аккаунта; также добавляется в начало данных HMAC для hosted | identity-ключ primary / adv secret | found |
| `06 01` | `A0H` | подпись устройства: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | identity-ключ companion | found (сторона проверки) |
| `06 06` | `A0I` | hosted-вариант подписи устройства | identity-ключ companion | found (сторона проверки) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | identity-ключ primary | found |
| `06 07` | `A0K` | аттестация non-E2EE ("hybrid") (`AeaUtils`), не префикс key-index-list | identity-ключ primary | found |

- Примитив подписи: `C38851hm.A00("best")` загружает `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (подпись 64 байта), `A02` = `calculateAgreement`. Ключи по 32 байта с байтом типа `5`. То есть подписи Curve25519 библиотеки Signal curve25519 (стиль XEdDSA, inferred из библиотеки, а не из названия алгоритма). Выбор провайдера native или Java определяется во время выполнения (какой используется на конкретном устройстве, unknown).
- HMAC: `HmacSHA256` через `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Key-index list

`C24270w6.A01` строит `ADVKeyIndexList`; `validIndexes` — набор, состоящий из (found): одной записи для слота primary (значение 0, когда не в режиме companion; условие ветки inferred), `adv_key_index` каждого сохранённого companion (`CJY.A07`) и `currentIndex`. `A02` подписывает `06 02 ‖ details`.

`C24250w4.A00` отправляет его как:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Таймаут 32000 мс. Шлюз `A02`: флаг **477** ненулевой, companion присутствуют (или режим companion), не в режиме companion. При сбое `adv_key_index_list_update_retry_count` увеличивается; выше **5** приложение логирует `adv-key-index-list-update … fails for more than 5 times` и выполняет logout всех companion (`C24270w6.A03`). Успех очищает счётчики (`A05`).

### 5.4 Правило timestamp (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = часы с поправкой NTP, `srv` = время сервера. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. Если `last + 1 > now + 86400`, значение недопустимо (-1, лог `getTimestampSec invalid ts`), что блокирует привязку с локальным кодом -8. Монотонно для аккаунта (found).

### 5.5 Проверка на проводе (`C24230w2`)

Для любой идентичности устройства, которую видит primary (свои и companion контактов), он проверяет по порядку (found):

1. identity-ключ primary известен (сохранён или `accountSignatureKey` из списка), иначе `no primary key`;
2. identity-ключ companion разбирается (`0x05`+32 Б), иначе `invalid companion public key`;
3. подпись аккаунта над `prefix ‖ details ‖ companion identity`, иначе `fail to verify account signature`;
4. подпись устройства над `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (hosted `06 06`), иначе устройство отклоняется;
5. key-index-list: подпись над `06 02 ‖ details` ключом primary; `adv timestamp` списка должен быть согласован (`advTimestampMismatch`, `advListTimestampInvalid`); несовпадающий входящий key index сбрасывает локальное состояние (`incoming key-index not matching local state, resetting`); больший индекс для уже присутствующего устройства отбрасывает старую запись (`filterDeviceWithKeyIndexList`).

---

## 6. Список устройств, запись и лимиты

### 6.1 Уведомление `devices` (получает primary)

`notification` с дочерним `add` или `remove` (всё остальное: `unknown type of device notification`). Атрибуты и дочерние элементы (found): `device_hash`, необязательные `device_lid_hash` плюс `lid`, записи `device` (jid, key index), необязательный `key-index-list` (bytes, атрибуты `ts`, `expected_ts`). Если у уведомления есть атрибут `offline`, пользователь ставится в очередь для последующей синхронизации; иначе запускается задача синхронизации (`SyncDeviceNotificationRunnable`). Список принимается, только если его timestamp не старше сохранённого `adv_timestamp_sec` (иначе `local ts is larger than notification one`).

### 6.2 Сохранённая запись устройства (таблица `devices`, `C1h8`)

| Группа | Столбцы (found) |
|-------|-----------------|
| Идентичность | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Время | `last_active`, `login_time`, `logout_time` |
| Синхронизация | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Возможности | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

Значения `platform_type` берутся из `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Лимиты и флаги

| Флаг / элемент | Значение | Уровень |
|-------------|---------|------|
| **15550** | целое: максимум привязанных устройств (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` блокирует "link a device"; сканер QR получает extra `at_device_limit`; `OrbitCompanionLinkActivity` отказывает при достижении) | found (использование); значение по умолчанию unknown (abprop, доставляемый сервером); существует поле метрик `md_linked_devices_max_devices_limit` |
| **3816** | секунды, в течение которых `companion_hello` остаётся действительным, ограничено 360 с | found |
| **477** | шлюз (ненулевой) для обновлений key-index-list | found |
| **18193** | добавляет `friction` (variant 1) в объявляемые `challenges/supported` | found (использование); эффект на сервере unknown |
| **28161** | добавляет второй объявляемый challenge (`passkey-create`) | маппинг inferred (декомпилятор потерял ветку) |
| **29500** | шлюз hosted-привязки, используемый в проверке режима защиты | found (чтение), смысл inferred |
| **31019** | добавляет атрибут `exclude_hosted_companion=true` в remove-all по некоторым причинам | found |

Применяет ли сервер лимит независимо от клиентской проверки, unknown. В прочитанном здесь коде у primary нет клиентского таймаута неактивности для companion; серверное истечение простаивающих companion unknown.

---

## 7. Отвязка (сторона primary)

### 7.1 Одно устройство

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, таймаут 32000 мс. Результат может нести дочерний `coex_token` (передаётся обработчику coexistence). Сбой доставки или ошибка вызывает failure callback с кодом -1 (found).

### 7.2 Все устройства

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Пустой локальный список сразу ведёт к success callback. Строки причин, замеченные в коде: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; список может быть длиннее, исходное выражение усечено).

### 7.3 Триггеры автоматической отвязки (found)

| Триггер | Причина |
|---------|--------|
| обновление key-index-list завершилось сбоем более 5 раз | `adv-key-index-list-update`, logout всех |
| переполнение key index | сброс `A03` |
| недопустимый статус ADV / неизвестный companion (`KZD` case 43) | `invalid_adv_status` |
| переход типа аккаунта hosted ↔ E2EE | выгоняет все устройства (лог `handleADVMetadata`) |
| сервер присылает уведомление `devices` типа `remove` | локальная запись удаляется (inferred) |
| действие пользователя на экране linked-devices / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found для монитора; путь UI inferred) |

Удаление аккаунта целиком (`urn:xmpp:whatsapp:account` `remove`) — другой IQ, не связанный с отвязкой companion.

---

## 8. Случаи ошибок

### 8.1 Коды сервера, обрабатываемые `C44661Jem.A01`

| Код | Callback | UI | Уровень |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | состояние "companion too old" | found |
| 404 / 405 / 443 / 445 | общий `C2w` | сопоставление строк `C44648JeY`: у 405 и 443 свои тексты; 404/405/443/445 имеют общий заголовок | found (строки по id); точный смысл 404/443/445 unknown |
| другой | общий `C2w` | привязка не удалась | found |

`InstrumentationAuthActivity` называет коды результата 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, иначе `PAIRING_FAILED` (found). Сопоставление серверного 405 со случаем consumer/SMB — inferred по id строки.

### 8.2 Локальные коды

| Код | Причина | Исправление |
|------|-------|-----|
| -8 | локальный timestamp ADV недопустим (часы против последнего сохранённого ts + 1) | исправить время устройства; строка UI "invalid device time" |
| -9 | в QR нет identity-ключа / adv secret | использовать актуальный QR |
| -10 | hosted-привязка в consumer-сборке | n/a |
| -13 | несоответствие платформы и флага hosted | n/a |
| -17 | выполняется другая привязка | подождать; запрос живёт до 32 с |
| -20 | сервер запросил challenges (`retry-after-challenges`) | пройти challenge friction / passkey |
| -1 | запрос удаления не отправлен или завершился ошибкой | повторить |

### 8.3 Сбои link-code

| Симптом (лог) | Причина |
|------------------|-------|
| `companion hello is null or expired` | код введён после истечения (флаг 3816, максимум 360 с) |
| `decryption fail` (hello) | неверный код (ключ PBKDF2 отличается; у AES-CTR нет тега, поэтому неверный код даёт мусорный ключ, который ловится на последующих шагах; inferred) |
| `primary identity doesn't match` | пакет был построен для другого ключа primary |
| `companion identity doesn't match` | уведомление и пакет расходятся |
| `invalid-primary-adv-key-length` / `adv public key is 0` | проверки в роли companion над эфемерным ключом primary |

---

## 9. Ключевые различия

### 9.1 Не путать

| A | B |
|---|---|
| `pair-device`, отправляемый **primary** (этот отчёт) | `pair-device`, **получаемый** приложением в роли companion (обработчик `AbstractC40501kw`, id 242, несёт refs для QR) |
| `ADVSignedDeviceIdentity` (подписан, без HMAC) | `ADVSignedDeviceIdentityHMAC` (обёртка, отправляемая в `device-identity`) |
| дочерний `device-identity` в `pair-device` (обёртка HMAC) | дочерний `device-identity` в исходящих станзах сообщений (идентичность аккаунта, прикрепляемая companion; pref `adv_signed_identity`) |
| подпись аккаунта (ключ primary, префикс `06 00`) | подпись устройства (ключ companion, префикс `06 01`) |
| префикс key-index-list `06 02` | `06 07` (аттестация non-E2EE) |
| `pub-key` QR / `companion_server_auth_key_pub` | identity-ключ companion (тот, что получает подпись аккаунта) |
| `rawId` (id всего аккаунта, меняется при сбросе) | `keyIndex` (для каждого companion) |
| символ платформы QR (`EnumC26332BbY`) | `DeviceProps.platformType` на проводе (`EnumC25120ArW`), другая нумерация |

### 9.2 Hosted-устройство

Id устройства в JID **99** (`device_id should be 99 for hosted device`), маркер регистрации/отвязки `hosted_device_pairing`, префиксы подписей `06 05` / `06 06`, `exclude_hosted_companion`. Primary отказывается привязывать hosted-устройство в этой сборке (локально -10). Всё сверх этих строк unknown.

### 9.3 Shortcake

`retry-with-method` может перечислять `shortcake-with-passkeys`; тогда приложение сохраняет ключ handoff и переключает UI. `ShortcakeJni` предоставляет `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` и `nativeResponderStart/Finish` (found). Транскрипт handshake нативный и здесь не декомпилировался: unknown.

### 9.4 Friction / режим защиты

`pair-device` объявляет поддерживаемые challenges и при повторе возвращает `completed`. Primary решает локально требовать friction, когда включён режим защиты (`C271211x.A0N()`) и challenge friction ещё не пройден; это решение принимается до первого IQ (`defense mode friction triggered`). Серверная политика, посылающая `retry-after-challenges`, не видна (unknown).

### 9.5 Нет клиентской аттестации companion

Ничто в payload pair-device не доказывает, какое ПО запускает companion: `ref`, `pub-key`, identity-ключ, adv secret и символ платформы декларируются самим QR. Подписи доказывают лишь то, что этот аккаунт primary авторизовал этот identity-ключ. Любая проверка "официального клиента" — на стороне сервера (вердикт 465 обрабатывается на клиенте только как результат).

### 9.6 Код роли companion в том же APK (кратко)

| Элемент | Находка |
|------|---------|
| Дочерние элементы IQ `companion_hello` | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; атрибут `should_show_push_notification` (found, `C0YS`) |
| код | `K1T.A00` base32 от 5 случайных байт (4.3) |
| ротация QR | IQ `pair-device-rotate-qr` с атрибутами `stage` 0/1/2 и необязательным `sentinel`, дочерний `ref` |
| входящие md IQ | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (id 242, 243, 266, 278, 279) |
| содержимое `pair-success` и ответ companion `pair-device-sign` | не прослежено в этой сборке: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Сравнено с локальным исходным кодом; только совпадения и одно различие, проверенные с обеих сторон.

| Элемент | APK 2.26.41.6 | `baron-baileys-v2` | Результат |
|------|---------------|--------------------|--------|
| Payload QR | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | совпадает (4 поля) |
| Получение pair-кода | PBKDF2-SHA256 131072 ит., алфавит `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, тот же алфавит (`crypto.js`, `generics.js`) | совпадает |
| Пакет ключей | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, plaintext identity ‖ identity ‖ random32 | та же раскладка (`messages-recv.js`) | совпадает |
| adv secret | HKDF(нулевой salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | совпадает |
| Обёртка HMAC | HMAC-SHA256(adv secret, [06 05 для hosted ‖] байты ADVSignedDeviceIdentity) | то же (`validate-connection.js`) | совпадает |
| Сообщения подписи аккаунта / устройства | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | то же | совпадает |
| Hosted-префикс key-index-list | проверка и подпись используют `06 02` для каждого списка; `06 07` — префикс аттестации non-E2EE | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` используется при `accountType == HOSTED` (`chats.js`) | **отличается**; hosted-поток не задействуется этой consumer-сборкой, поэтому эффект различия unknown |

Утверждений "почему не работает" не делается: companion на Baileys, следующий совпавшим строкам, согласуется с тем, что primary здесь разбирает; принятие сервером статически не проверяется.

---

## 11. Полные потоки

### 11.1 Поток QR

```
[Companion]  shows QR  https://wa.me/settings/linked_devices#ref,noisePub,identityPub,advSecret[,platform]
     │
     ▼
[Primary]    scan → C45741Jxy.A02 → C45423Jrn → C44423JaU
     │       checks: -9 / -13 / -17 / -8 / -10 ; defense mode → challenges (-20)
     │       incrementCurrentKeyIndex ; ts = C24270w6.A00()
     │       details  = ADVDeviceIdentity{rawId, ts, keyIndex, accountType, deviceType}
     │       accSig   = Curve25519.sign(P.priv, 06 00 ‖ details ‖ companionIdentity)
     │       signed   = ADVSignedDeviceIdentity{details, P.pub, accSig}
     │       wrapper  = ADVSignedDeviceIdentityHMAC{signed, HMAC-SHA256(advSecret, signed)}
     │       list     = ADVSignedKeyIndexList (sig 06 02)
     │       K        = HKDF(salt = noisePub, IKM = advSecret, "Canonical Ent Companion Nonce Encrypt")
     ▼
iq set xmlns=md  <pair-device> ref, pub-key, device-identity, key-index-list ts, client-props, pem, … </pair-device>
     │
     ▼
[WA Server]   (not observed) validates, creates device jid, sends pair-device / pair-success to the companion
     │
     ▼
Result to primary: <device jid/> <companion-props/>   (or retry-ts / retry-after-challenges / retry-with-method / error 465, 496, …)
     │
     ▼
[Primary]    store CJY record, adv_timestamp_sec = list ts, start history sync
     │
     ▼
[Server → Primary]  notification devices add{device_hash, device…, key-index-list ts}  → SyncDeviceNotificationRunnable → verify (5.5)
```

### 11.2 Поток pair-кода

```
[Companion]  iq link_code_companion_reg stage=companion_hello
     │         wrapped_ephemeral = salt32 ‖ iv16 ‖ AES-CTR(PBKDF2(code, salt), ephPub)
     ▼
[WA Server]  → notification stage=companion_hello  → [Primary] C10J (id 252)
     │                                               store hello (ttl ≤ 360 s), push notification
     │                                               user types 8-char code
     ▼
[Primary]    unwrap companion eph pub ; make own eph pair ; eph = X25519(...)
     │         iq link_code_companion_reg stage=primary_hello
     │             wrapped_primary_ephemeral_pub, primary_identity_pub, link_code_pairing_ref
     ▼
[Companion]  eph = X25519(...) ; bundle = salt32 ‖ nonce12 ‖ GCM(HKDF(eph, salt), companionId ‖ primaryId ‖ random32)
     │         iq stage=companion_finish
     ▼
[WA Server]  → notification stage=companion_finish → [Primary] KYB
     │            decrypt, check both identities, advSecret = HKDF0(eph ‖ DH(id) ‖ random, "adv_secret")
     ▼
[Primary]    pair-device IQ (same as 11.1, pub-key = companion_server_auth_key_pub)
     ▼
(11.1 continues)
```

### 11.3 Отвязка

```
[Primary UI / auto trigger]
     │   remove-companion-device jid=… reason=…     (or all="true")
     ▼
iq set xmlns=md  →  [WA Server]  →  result (optional coex_token)
     │
     ▼
[Primary]   remove local record, new key-index-list on next update (iq key-index-list ts)
[Server → other devices]  notification devices remove{…}
```
