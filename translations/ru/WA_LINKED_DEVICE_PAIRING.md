<!-- src-sha1: 6458e557973884f0b2c8c175f4607447365f03a6 -->
# WhatsApp Привязка связанного устройства — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** сторона основного устройства при привязке companion-устройства, поток QR, поток номер телефона/код привязки, стансы `pair-device` и `pair-success`, ключевой материал, подписанная идентичность устройства ADV и список индекса ключей, список устройств и лимиты, отвязка, ошибки, сравнение с Baileys

---

## 1. Что это (технически)

Связанное устройство (companion) — это второй endpoint того же аккаунта. Основной телефон авторизует его, производя подписанную идентичность ADV (account device verification) над ключом идентичности companion-устройства. Все утверждения — статический анализ декомпилированного APK; ничего не было захвачено по протоколу. Уровень: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не разрешено.

Обфусцированные имена специфичны для сборки и были повторно разрешены из стабильных строк в 2.26.41.6.

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|----------------|------|
| Оркестратор QR/привязки | `C45850K0w` (префикс лога `CompanionDeviceQrHandler`) | разбирает QR, строит proto ADV, отправляет `pair-device` |
| Строитель IQ `pair-device` | `RunnableC46606KYf` | строит IQ |
| Помощник запроса/ответа `pair-device` | `KRI` (`devicePairRequest/*`) | отправка, повтор, разбор подсказок `device` / `companion-props` / повтора |
| Маршрутизатор ошибок | `C44661Jem` | сопоставляет серверный код ошибки с колбэком UI |
| Парсер строки QR | `C45741Jxy` → `C45423Jrn` | полезная нагрузка QR в данные привязки |
| Разобранные данные привязки | `C44423JaU` | ref, ключи companion, секрет adv, платформа |
| Утилита ADV | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, индекс ключа, метка времени, построение и подпись списка индекса ключей |
| Обновлятор списка индекса ключей | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | отправляет подписанный список на сервер |
| Верификатор ADV | `C24230w2` (`DeviceADVInfoHandler`) | проверяет идентичности и списки, видимые по протоколу |
| Обработчик уведомления о списке устройств | анонимный класс в `C1S0` (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | уведомление `devices` |
| Обработчик уведомления с кодом привязки | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | id уведомления 252 |
| Менеджер кода привязки (основной) | `KZ3` (ввод кода, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | поток с кодом привязки |
| Утилита криптографии кода привязки | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Менеджер устройств | `C0XQ` (`companion-device-manager`) | список, выход |
| Помощник удаления | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Обёртка Signal curve | `C38851hm` | провайдер `org.whispersystems.curve25519` "best" |
| Proto-классы ADV | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | см. раздел 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `companion-props` в результате `pair-device` |
| Свойства клиента | `C43107IrI` | дочерний `client-props` |
| Тип аккаунта/шифрования | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

В UI основного устройства существуют три режима входа (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

Тот же APK также содержит код регистрации для роли companion (конечный автомат `C0YS`, логи `companion/registration/*`). Это вне области; описаны только части, нужные для объяснения того, что получает основное устройство (раздел 9.6).

---

## 2. Пути привязки — обзор

| Путь | Триггер на основном устройстве | Основное устройство отправляет | Секрет, связывающий основное и companion-устройство |
|------|--------------------|---------------|----------------------------------------|
| QR | сканирование `https://wa.me/settings/linked_devices#<payload>` (или `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` из поля 4 QR |
| Номер телефона + код | `notification` `link_code_companion_reg` стадия `companion_hello`, пользователь вводит 8-символьный код | `primary_hello`, затем (после `companion_finish`) тот же `pair-device` | `adv secret`, выводимый из двух результатов X25519 плюс случайное значение (раздел 4.4) |

Оба пути сходятся в одном объекте `C44423JaU` и одном IQ `pair-device` (found: `KYB` строит `C44423JaU` из bundle `companion_finish` тем же конструктором `C45850K0w.A01`, что используется для QR).

---

## 3. Поток QR (сторона основного устройства)

### 3.1 Полезная нагрузка QR

`C45741Jxy.A01` отрезает префикс `https://wa.me/settings/linked_devices#` или `whatsapp://settings/linked_devices#` и URL-декодирует остальное. `A02` разбивает по `,` (found):

| Idx | Содержимое | Кодирование | Использование |
|-----|---------|----------|-----|
| 0 | `ref` | string | ссылка привязки; ref, начинающийся с `CAPI_`, отклоняется (`invalid ref`) |
| 1 | публичный ключ companion-устройства | base64 | отправляется как `pub-key`, соль для ключа nonce (3.4). Имя предположено: статический ключ Noise (`companion_server_auth_key_pub` в пути кода) |
| 2 | ключ идентичности companion-устройства | base64, 32 байта, парсер добавляет `0x05` (тип Curve25519) | подписывается подписью аккаунта |
| 3 | `adv secret` | base64 | ключ HMAC для обёртки ADV |
| 4 | код платформы (опционально) | один символ | сопоставляется с типом платформы; `j` = hosted-устройство |

- Менее 3 частей: `qrData/processQR/error/invalid_code parts`. Отсутствующий ключ идентичности или секрет adv (старый 3-польный QR): `invalid qr code, missing companion identity key or adv secret` → локальный код **-9**.
- Таблица символов платформы (не связана с `EnumC26221BZl`, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Используется только для проверки hosted и логирования (3.2).

### 3.2 Локальные проверки до отправки чего-либо

| Проверка | Код | Локальный код |
|-------|------|------------|
| У QR есть ключ идентичности и secret adv | `C45850K0w.A01` | -9 |
| Флаг hosted согласован: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| Другая привязка уже выполняется (`kri.A0N`, или менеджер companion-устройств занят) | `A04` | -17 |
| Локальная метка времени ADV валидна (`C24270w6.A00() != -1`) | `A04` | -8 |
| Hosted companion-устройство | `A04`: `Hosted pairing is not supported` | -10 |
| Требуется защитное трение (friction) | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (повтор с вызовами) |

Hosted-привязка блокируется на стороне клиента в этой сборке (`pairing for hosted device is not supported on the consumer build`).

### 3.3 Перед IQ: очистка syncd и индекс ключа

1. Если состояние syncd "грязное" (`sync-manager/shouldCleanUpSyncdOnPairing`), приложение сначала очищает syncd, затем продолжает (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (в `RunnableC46617KYr`):
   - нет сохранённого rawId или индекса: новый случайный rawId, индекс 1;
   - нет привязанных companion-устройств: `rawId + 1`, индекс остаётся 1;
   - companion-устройства существуют: `currentIndex + 1`; при переполнении rawId + 1, и все устройства разлогиниваются (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (раздел 5.4).

### 3.4 Что строится

В `C45850K0w.A00`, с `E` = ключ идентичности companion-устройства (32 Б, сырой), `P` = пара ключей идентичности основного устройства (Curve25519), `S` = secret adv:

| Шаг | Операция | Уровень |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | подпись аккаунта = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; префикс `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` оставлена пустой: companion-устройство добавляет её) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = сериализация шага 3, hmac = HMAC-SHA256(key = S, data = байты шага 3), accountType}`; для hosted данные — `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) из `C24270w6.A01`, подписывается `A02` → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | ключ nonce `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 Б)`, оборачивается как дочерний `pem` | found (вывод); назначение предположено |
| 7 | опциональный `encryption-metadata` (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, из `AuthProofHelper` (шифрование пароля аккаунта, метка `rsa2048`) | found (структура); что это доказывает — unknown |
| 8 | опциональный `client-props` (`C43107IrI`, раздел 3.6) | found |

Деталь по шагу 6: узел `pem` помечен `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 дней`, `key_id=1`, но его дочерний элемент несёт `key.getEncoded()` 32-байтного вывода HKDF (`SecretKeySpec`, алгоритм `AES-GCM`). Метка и содержимое не совпадают; причина unknown. Использование сервером предположено (сервер шифрует посообщенческий nonce для companion-устройства; см. столбец `companion_meta_nonce`).

### 3.5 IQ `pair-device` (основное устройство → сервер)

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

Found: все имена дочерних элементов, значение атрибута `ts` (метка времени списка индекса ключей), таймаут **32000 мс** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` — `1` для значения записи 3 и `2` для значения записи 5 (значение этих целых чисел unknown). Точный порядок дочерних элементов и ветка `companion_qr_origin_source` частично искажены декомпилятором; считать порядок непроверенным.

### 3.6 `client-props` (`C43107IrI`)

| Поле | Номер | Тип | Устанавливается когда |
|-------|--------|------|----------|
| `isChatDbLidMigrated` | **1** | bool | миграция LID БД чатов завершена |
| `isSyncdPureLidSession` | **2** | bool | присутствует флаг чистой сессии LID syncd |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | флаг восстановления |
| `isHsThumbnailSyncEnabled` | **4** | bool | флаг синхронизации миниатюр истории |
| `subscriptionSyncPayload` | **5** | bytes | строится, когда включена синхронизация md (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | JID бота БД мигрирован |

### 3.7 Обработка результата (`KRI.CFS`)

Дочерние элементы успешного результата (found):

| Дочерний | Использование |
|-------|-----|
| `device` атрибут `jid` | новый `DeviceJid` companion-устройства; id устройства **99** сопоставляется с записью платформы hosted |
| `companion-props` | proto `DeviceProps` (`C43105IrG`): `os` **1** (string), `version` **2** (message), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (message) |
| атрибут `ts` у `retry-ts` | сервер запрашивает более новую метку времени; приложение повторяет (`RunnableC46585KXj`) |
| `retry-after-challenges` | дочерние `friction` (атрибут `variant`, должен быть `1`, опциональный `location` "lat,lon") или `passkey-create` (атрибут `created`) |
| `retry-with-method` | дочерние `qr-code` или `shortcake-with-passkeys`; если присутствует второй, 32-байтный ключ передачи (HKDF от adv secret, info `shortcake-passkey-handoff-v1`) сохраняется (`PairingHandoffKeyHolder`), ограничено abprop |

При успехе приложение сохраняет запись устройства `CJY` (случайная 24-байтная base64 строка, `adv_key_index` = текущий индекс, `requireFullSync`), сохраняет метку времени списка индекса ключей как `adv_timestamp_sec` (`C24270w6.A05`) и запускает состояние синхронизации истории (`C8N`).

Сбой доставки (`Bog`): до **3** повторов, задержка `3000 * 3^(n-1)` мс (3 с, 9 с, 27 с), если флаг повтора включён (found); затем колбэк ошибки.

---

## 4. Поток номер телефона/код привязки (сторона основного устройства)

### 4.1 Шаги

| # | Направление | Станса / действие | Класс |
|---|-----------|-----------------|-------|
| 1 | companion → сервер → основное устройство | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | основное устройство | сохраняет hello, показывает push-уведомление → `CompanionHelloConfirmationActivity` / экран ввода кода | `C10J`, `C77`, `JYJ` |
| 3 | пользователь | вводит 8-символьный код | `LinkedDevicesEnterCodeActivity` |
| 4 | основное устройство → сервер | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (таймаут 120000 мс) |
| 5 | сервер → основное устройство | `notification` `stage=companion_finish` | `C10J` → `KYB` кейс 0 |
| 6 | основное устройство → сервер | IQ `pair-device` (раздел 3.5) | `C45850K0w` |
| 7 | другие стадии | `refresh_code` (основное устройство запрашивает обновление кода, атрибут `force_manual_refresh`) | `C10J` |

### 4.2 Уведомление `companion_hello` (found)

| Дочерний | Использование |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | эфемерный ключ X25519 companion-устройства, обёрнутый кодом (4.3) |
| `companion_server_auth_key_pub` | позже становится `pub-key` в `pair-device` |
| `link_code_pairing_ref` | ссылка сессии (строка) |
| `companion_platform_id` | строка id платформы |
| `companion_platform_display` | отображаемое имя |
| атрибут `should_show_push_notification` | `true` → push-уведомление |

Сохраняемое состояние (`C77`/`CE4`, SharedPrefs JSON `companion_reg_with_link_code_companion_hello_info_json`): ref, id платформы, обёрнутый ключ, ключ сервера auth, срок действия `сейчас + min(360000, флаг 3816 * 1000)` мс. Истёкшее или отсутствующее hello → "companion hello is null or expired" (состояние UI 2). Более новое hello с другим ref отменяет предыдущий ref (`KRJ.A00(oldRef, "true")`).

### 4.3 Криптография кода и обёртки (found)

| Элемент | Значение |
|------|-------|
| Код | 5 случайных байт → 8 символов, по 5 бит, алфавит `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 символа, без `0 I O U`) (`K1T.A00`, генерируется companion-устройством) |
| Код → ключ | PBKDF2-HMAC-SHA256, **131072** итераций, 256 бит, пароль = символы кода, соль = первые 32 байта обёрнутого блоба (`K1T.A02`) |
| Обёрнутый эфемерный ключ | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, открытый текст = 32-байтный публичный ключ X25519; длина должна быть ≥ 48 |
| Ответ основного устройства | основное устройство создаёт собственную пару эфемерных ключей, оборачивает свой публичный ключ тем же образом (свежая 32-байтная соль, 16-байтный IV, тот же код) |

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

Дочерние элементы уведомления `companion_finish`: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. Обработка на основном устройстве в `KYB` кейс 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (сохранён при `primary_hello`).
2. Раскладка bundle `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, минимум 44 байта.
3. Ключ = HKDF-SHA256(salt = salt bundle, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 Б).
4. Открытый текст = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Проверки: идентичность основного устройства должна равняться собственному ключу идентичности; идентичность companion-устройства должна равняться `companion_identity_public` из уведомления; иначе ref отбрасывается, и UI получает состояние ошибки.
6. `adv secret = HKDF-SHA256(salt = 32 нулевых байт, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 Б)` (`K1T.A03`).
7. Ключ передачи = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (также хранится в `C44423JaU`).
8. `C44423JaU` строится с `pub-key` = `companion_server_auth_key_pub`, идентичностью companion-устройства, adv secret → тот же IQ `pair-device`, что у QR.

Внешний эфемерный ECDH существует (это IKM HKDF шага 3). Замечание из более ранней сборки говорило "на этой стадии нет ECDH"; для этой сборки это неверно.

Маркеры ошибок на стороне основного устройства: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

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
| | | `deviceSignature` | **4** | bytes (устанавливается companion-устройством) |
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

Номера полей и типы протокола читаются из сгенерированной информации о сообщении; имена совпадают с каноническими сообщениями ADV. Имена enum: значения `EnumC32116E1o`: E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 Префиксы подписей и алгоритмы

| Префикс | Константа | Подписываемые/MAC-защищаемые данные | Подписывающий | Уровень |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | подпись аккаунта: `‖ details ‖ идентичность companion-устройства` | ключ идентичности основного устройства | found |
| `06 05` | `A0G` | hosted-вариант подписи аккаунта; также добавляется перед данными HMAC для hosted | ключ идентичности основного устройства / secret adv | found |
| `06 01` | `A0H` | подпись устройства: `‖ details ‖ идентичность companion-устройства ‖ accountSignatureKey` | ключ идентичности companion-устройства | found (сторона проверки) |
| `06 06` | `A0I` | hosted-вариант подписи устройства | ключ идентичности companion-устройства | found (сторона проверки) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | ключ идентичности основного устройства | found |
| `06 07` | `A0K` | аттестация не-E2EE ("гибридная") (`AeaUtils`), не префикс списка индекса ключей | ключ идентичности основного устройства | found |

- Примитив подписи: `C38851hm.A00("best")` загружает `org.whispersystems.curve25519.OpportunisticCurve25519Provider`; `A03` = `calculateSignature(random 64 Б, priv, msg)`, `A01` = `verifySignature` (64-байтная подпись), `A02` = `calculateAgreement`. Ключи — 32 байта с типом-байтом `5`. Так что это подписи Curve25519 библиотеки Signal curve25519 (в стиле XEdDSA, предположено из библиотеки, не из названия алгоритма). Выбор провайдера нативный vs Java решается в runtime (неизвестно, какой используется на конкретном устройстве).
- HMAC: `HmacSHA256` через `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 Список индекса ключей

`C24270w6.A01` строит `ADVKeyIndexList`; `validIndexes` — это набор, состоящий из (found): одной записи для слота основного устройства (значение 0, когда не в режиме companion-устройства; условие ветки предположено), `adv_key_index` каждого сохранённого companion-устройства (`CJY.A07`) и `currentIndex`. `A02` подписывает `06 02 ‖ details`.

`C24250w4.A00` отправляет его как:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Таймаут 32000 мс. Ограничение `A02`: флаг **477** не нулевой, companion-устройства присутствуют (или режим companion-устройства), не в режиме companion-устройства. При сбое `adv_key_index_list_update_retry_count` увеличивается; выше **5** приложение логирует `adv-key-index-list-update … fails for more than 5 times` и разлогинивает все companion-устройства (`C24270w6.A03`). Успех очищает счётчики (`A05`).

### 5.4 Правило метки времени (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = часы, скорректированные NTP, `srv` = серверное время. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. Если `last + 1 > now + 86400`, значение недействительно (-1, логируется `getTimestampSec invalid ts`), что блокирует привязку локальным кодом -8. Монотонно на каждый аккаунт (found).

### 5.5 Проверка по протоколу (`C24230w2`)

Для любой идентичности устройства, которую видит основное устройство (собственные и companion-устройства контактов), оно проверяет, по порядку (found):

1. ключ идентичности основного устройства известен (сохранён, или `accountSignatureKey` из списка), иначе `no primary key`;
2. ключ идентичности companion-устройства разбирается (`0x05`+32 Б), иначе `invalid companion public key`;
3. подпись аккаунта над `prefix ‖ details ‖ идентичность companion-устройства`, иначе `fail to verify account signature`;
4. подпись устройства над `06 01 ‖ details ‖ идентичность companion-устройства ‖ accountSignatureKey` (hosted `06 06`), иначе устройство отклоняется;
5. список индекса ключей: подпись над `06 02 ‖ details` ключом основного устройства; `adv timestamp` списка должен быть согласован (`advTimestampMismatch`, `advListTimestampInvalid`); несовпадающий входящий индекс ключа сбрасывает локальное состояние (`incoming key-index not matching local state, resetting`); больший индекс для того же уже присутствующего устройства отбрасывает более старую запись (`filterDeviceWithKeyIndexList`).

---

## 6. Список устройств, запись и лимиты

### 6.1 Уведомление `devices` (получает основное устройство)

`notification` с дочерним `add` или `remove` (что-либо иное: `unknown type of device notification`). Атрибуты и дочерние элементы (found): `device_hash`, опциональный `device_lid_hash` плюс `lid`, записи `device` (jid, индекс ключа), опциональный `key-index-list` (bytes, атрибут `ts`, `expected_ts`). Если уведомление несёт атрибут `offline`, пользователь ставится в очередь на более позднюю синхронизацию; иначе выполняется задача синхронизации (`SyncDeviceNotificationRunnable`). Список принимается только если его метка времени не старше сохранённого `adv_timestamp_sec` (иначе `local ts is larger than notification one`).

### 6.2 Сохранённая запись устройства (таблица `devices`, `C1h8`)

| Группа | Столбцы (found) |
|-------|-----------------|
| Идентичность | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Время | `last_active`, `login_time`, `logout_time` |
| Синхронизация | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Возможности | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

Значения `platform_type` приходят из `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Лимиты и флаги

| Флаг / элемент | Значение | Уровень |
|-------------|---------|------|
| **15550** | целое число: максимум связанных устройств (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` блокирует "привязать устройство"; сканер QR получает дополнительный `at_device_limit`; `OrbitCompanionLinkActivity` отказывает при достижении) | found (использование); значение по умолчанию unknown (abprop, доставляемый сервером); существует метрическое поле `md_linked_devices_max_devices_limit` |
| **3816** | секунды, в течение которых `companion_hello` остаётся валидным, ограничено 360 с | found |
| **477** | ограничение (не ноль) для обновлений списка индекса ключей | found |
| **18193** | добавляет `friction` (вариант 1) к анонсируемым `challenges/supported` | found (использование); эффект на сервере unknown |
| **28161** | добавляет второй анонсируемый вызов (`passkey-create`) | сопоставление предположено (декомпилятор потерял ветку) |
| **29500** | ограничение hosted-привязки, используемое в проверке защитного режима | found (чтение), значение предположено |
| **31019** | добавляет атрибут `exclude_hosted_companion=true` к удалению всех по некоторым причинам | found |

Применяет ли сервер ограничение независимо от клиентской проверки — unknown. У основного устройства нет клиентского таймаута неактивности для companion-устройств в прочитанном здесь коде; серверное истечение неактивных companion-устройств — unknown.

---

## 7. Отвязка (сторона основного устройства)

### 7.1 Одно устройство

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, таймаут 32000 мс. Результат может нести дочерний `coex_token` (передаётся обработчику совместного существования). Сбой доставки или ошибка вызывает колбэк сбоя с кодом -1 (found).

### 7.2 Все устройства

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Пустой локальный список сразу переходит к колбэку успеха. Строки причин, замеченные в коде: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; список может быть длиннее, исходное выражение обрезано).

### 7.3 Автоматические триггеры отвязки (found)

| Триггер | Причина |
|---------|--------|
| Обновление списка индекса ключей не удалось более 5 раз | `adv-key-index-list-update`, выход для всех |
| Переполнение индекса ключа | сброс `A03` |
| Неверный статус ADV / неизвестное companion-устройство (`KZD` кейс 43) | `invalid_adv_status` |
| Переход типа аккаунта hosted ↔ E2EE | исключает все устройства (лог `handleADVMetadata`) |
| Сервер отправляет уведомление `devices` типа `remove` | локальная запись удаляется (предположено) |
| Действие пользователя на экране связанных устройств / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found для монитора; путь UI предположен) |

Удаление аккаунта целиком (`urn:xmpp:whatsapp:account` `remove`) — это другой IQ, не связанный с отвязкой companion-устройства.

---

## 8. Случаи ошибок

### 8.1 Серверные коды, обрабатываемые `C44661Jem.A01`

| Код | Колбэк | UI | Уровень |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | состояние "companion too old" | found |
| 404 / 405 / 443 / 445 | обычный `C2w` | сопоставление строк `C44648JeY`: у 405 и 443 отдельные тексты; 404/405/443/445 делят один заголовок | found (строки по id); точное значение 404/443/445 unknown |
| прочее | обычный `C2w` | привязка не удалась | found |

`InstrumentationAuthActivity` называет коды результата 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, иначе `PAIRING_FAILED` (found). Сопоставление серверного 405 со случаем consumer/SMB предположено из id строки.

### 8.2 Локальные коды

| Код | Причина | Исправление |
|------|-------|-----|
| -8 | неверная локальная метка времени ADV (часы vs последний сохранённый ts + 1) | исправить время устройства; строка UI "invalid device time" |
| -9 | у QR отсутствует ключ идентичности / adv secret | использовать текущий QR |
| -10 | hosted-привязка на consumer-сборке | н/д |
| -13 | несоответствие платформы и флага hosted | н/д |
| -17 | выполняется другая привязка | подождать; запрос живёт до 32 с |
| -20 | сервер запросил вызовы (`retry-after-challenges`) | завершить вызов friction / passkey |
| -1 | запрос удаления не отправлен или не удался | повторить |

### 8.3 Сбои кода привязки

| Симптом (лог) | Причина |
|---------------|-------|
| `companion hello is null or expired` | код введён после истечения срока (флаг 3816, максимум 360 с) |
| `decryption fail` (hello) | неверный код (ключ PBKDF2 отличается; AES-CTR без тега, так что неверный код даёт случайный ключ, перехватывается на более поздних шагах; предположено) |
| `primary identity doesn't match` | bundle был построен для другого ключа основного устройства |
| `companion identity doesn't match` | уведомление и bundle не согласуются |
| `invalid-primary-adv-key-length` / `adv public key is 0` | проверки роли companion-устройства на эфемерном ключе основного устройства |

---

## 9. Ключевые различия

### 9.1 Не путать

| A | B |
|---|---|
| `pair-device`, отправленный **основным устройством** (этот отчёт) | `pair-device`, **получаемый** приложением в роли companion (обработчик `AbstractC40501kw`, id 242, несёт ссылки для QR) |
| `ADVSignedDeviceIdentity` (подписан, без HMAC) | `ADVSignedDeviceIdentityHMAC` (обёртка, отправляемая в `device-identity`) |
| дочерний `device-identity` у `pair-device` (обёртка HMAC) | дочерний `device-identity` в исходящих стансах сообщений (идентичность аккаунта, прикреплённая companion-устройством; настройка `adv_signed_identity`) |
| подпись аккаунта (ключ основного устройства, префикс `06 00`) | подпись устройства (ключ companion-устройства, префикс `06 01`) |
| префикс списка индекса ключей `06 02` | `06 07` (аттестация не-E2EE) |
| QR `pub-key` / `companion_server_auth_key_pub` | ключ идентичности companion-устройства (тот, что получает подпись аккаунта) |
| `rawId` (id на весь аккаунт, меняется при сбросе) | `keyIndex` (на каждое companion-устройство) |
| символ платформы QR (`EnumC26332BbY`) | протокольный `DeviceProps.platformType` (`EnumC25120ArW`), иная нумерация |

### 9.2 Hosted-устройство

Id устройства JID **99** (`device_id should be 99 for hosted device`), маркер регистрации/отвязки `hosted_device_pairing`, префиксы подписи `06 05` / `06 06`, `exclude_hosted_companion`. Основное устройство отказывается привязывать hosted-устройство в этой сборке (локальный -10). Всё, что сверх этих строк — unknown.

### 9.3 Shortcake

`retry-with-method` может перечислять `shortcake-with-passkeys`; приложение затем сохраняет ключ передачи и переключает UI. `ShortcakeJni` выставляет `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` и `nativeResponderStart/Finish` (found). Транскрипт handshake нативный и здесь не декомпилирован: unknown.

#### 9.3a Тихая привязка — привязка tethered/periferальных companion-устройств + миграция эпохи (новое в 2.26.45.10, found)

**Четвёртый** механизм привязки, уже трёх вышеперечисленных (классический ADV/QR, код привязки/CRSC, hosted-устройство): тихая привязка **tethered/периферийных companion-устройств** — носимых устройств и умных очков, `DeviceProps.platformType` `WEAR_OS` / `AR_WRIST` / `AR_DEVICE` / `SMARTGLASSES`. Пакет `com.whatsapp.instrumentation.product.silentlinking` (`SilentLinkingNativeRegistration`, `SilentLinkingSessionManager$Session`).

**"Тихая" означает без сканирования QR, не без взаимодействия с пользователем.** Строки телеметрии (found) показывают поток подтверждения коротким кодом: `"code displayed to user"` → `"user confirmed code on primary"` → `"companion registration start"`. Периферийное устройство показывает короткий код, и пользователь подтверждает его на телефоне — та же модель присутствия пользователя, что у потока кода привязки (§4), только без изображения QR. Точка входа — UI апселла носимого устройства после звонка (`PostCallWearableUpsellBottomSheet`, `com.whatsapp.calling.wearableupsell`), питающий `SilentLinkingVerificationActivity` (`android:exported="false"`, только внутреннее, без deep link). Триггер — только клиентский UI: ни в одном из классов не найдено точки входа `AlarmManager`/`WorkManager`/серверного push, и логики "отвязать"/"распарить"/"существующее устройство" где-либо в них не встречается — это устанавливает привязку, а не тихо удаляет существующую.

`SilentLinkingNativeRegistration` берёт слот регистрации из уже существующего бокового канала CRSC v2/v3 (`CompanionRegOverSideChannelV2Manager`/`V3Manager`, та же инфраструктура, что в §4) для передачи получившейся регистрации идентичности. Собственно обмен ключами companion-устройства — отдельное, ранее не документированное семейство protobuf:

**Семейство конвертов RPC Shortcake** (found, имена/номера полей из smali, не декомпилировано отдельно в Java):

| Класс | Роль |
|-------|------|
| `LX/R9f` | Верхнеуровневый `oneof`-конверт: `protocolVersion`(1), `bootstrapAndHello`(2), `finishAndReady`(3), `peripheralAck`(4), `postCommitProofEnvelope`(5), `readinessRequestEnvelope`(6), `readinessResponseEnvelope`(7), `exactCleanupRequest`(8), `exactCleanupReceipt`(9) |
| `LX/RAN` | Bootstrap&Hello: `linkId`(1), `setupAttemptId`(2), `epochId`(3), `purpose`(4), `hnSignPub`(5), `hnEpoch1EphPub`(6, классический эфемерный ECDH), `hnMlkemPub`(7, публичный ключ ML-KEM-768), `protocolVersion`(8), `selectedCapabilities`(9), `migrationContextHash`(10), `hnDeviceSerial`(11) |
| `LX/RA1` | Конверт, обёрнутый шифротекстом Signal: `signalCiphertext`(1), `signalMessageType`(2), `peripheralHello`(3), `signalRequestId`(4), `companionAdvFingerprint`(5), `primarySignalPeerFingerprint`(6) — связывает handshake с отпечатком собственной идентичности ADV companion-устройства (§5) |
| `LX/RAW` | Второй `oneof`-конверт, сторона миграции эпохи: `rpcRequest`(1), `rpcResponse`(2), `primaryReady`(3), `peripheralAck`(4), `rotationControl`(5), `requestStatus`(6), `migrationPostCommitProof`(7), `migrationStatusRequest`(8), `migrationStatusResponse`(9), `migrationProbeRequest`(10), `migrationProbeResponse`(11) |
| `LX/RUe` | Enum `PERIPHERAL_PROPS_PLATFORM_{UNKNOWN,IOS,ANDROID}` — собственная ОС периферийного устройства |

`RAN.hnEpoch1EphPub` (классический) рядом с `RAN.hnMlkemPub` (ML-KEM-768) подтверждает **гибридный обмен ключами классический-ECDH + постквантовый**, не только PQ. Это **первый постквантовый криптографический механизм, документированный в этом отчёте**: ML-KEM-768 (FIPS 203 / Kyber-768), выполняемый через нативный `ShortcakeJni` (liboqs `OQS_KEM_ml_kem_768`, оборачиваемый `KEMPublicKey`/`KEMSecretKey` libsignal — найдено нативной декомпиляцией в отдельном проходе, см. brain `research/2.26.36.1/shortcake-kem-native.md`). Эта схема на стороне Java — это фрейминг транскрипта, который одного только нативного анализа оставил unknown; сам байтовый handshake Responder-Start/Finish остаётся только нативным и unknown.

**Метки контекста HKDF** (found, строковые литералы в `LX/SdB`, KDF = HMAC-SHA256 / HKDF-SHA256, тот же примитив, что у KDF обёртки кода привязки в §4.3): `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_V1`, `WA_TETHERED_EPOCH1_HN_KEY_POP_V1`, `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_HASH_V1`, `WA_TETHERED_EPOCH1_PRIMARY_FINISH_V1`, `WA_TETHERED_EPOCH1_WA_KEY_POP_V1`, `WA_TETHERED_EPOCH1_HYBRID_KX_V1`, `WA_TETHERED_LINK_IDENTITY_CONTEXT_V1`. ("HN" = сторона основного устройства/телефона; не раскрыто где-либо в дереве, вероятно "Host/Home Network".)

**Ротация/миграция эпохи (найденные строки, предположенная роль).** `LX/TIR` несёт обширный словарь ошибок миграции (`"Invalid migration frame version"`, `"Migration epoch mismatch"`, `"Migration shadow serial mismatch"`, `migration_shadow` и т.д.), в сочетании с `RAN.epochId` и полями ротации/probe-миграции/статуса/доказательства фиксации у `RAW`. Читая всё вместе, это фоновый **протокол ротации ключевой эпохи для уже установленной tethered-связи** — `SilentLinkingSessionManager$Session` периодически повторно вызывает `SilentLinkingNativeRegistration`, чтобы прокрутить ключи Shortcake под новым `epochId`, с путём probe/status/promotion/replay и откатом "теневой" записи. Это предположенное повествование над найденными строками/полями; это не механизм восстановления для утраченной классической сессии companion-устройства и не серверно-инициированная отвязка. Конкретное условие триггера для цикла ротации и точный транспорт по протоколу для `R9f`/`RAW` (полезная нагрузка бокового канала CRSC vs. выделенная станса/IQ) — unknown.

**Нулевая релевантность для Baileys/velowa.** Ограничено нативной криптографией `ShortcakeJni` и внутренней (`exported="false"`) активностью, достижимой только из внутриприложенческого UI, целиком в пределах собственной категории носимых устройств/умных очков WhatsApp. Это не затрагивает классическую привязку companion-устройства ADV/CRSC (§2-§4, то, что реализует сторонний клиент multi-device), и не найдено механизма, которым это могло бы отвязать или тихо повторно привязать Web/Desktop companion-устройство.

### 9.4 Трение / защитный режим

`pair-device` анонсирует поддерживаемые вызовы и возвращает выполненные при повторе. Основное устройство решает локально требовать трение, когда защитный режим включён (`C271211x.A0N()`) и вызов трения ещё не выполнен; это решение принимается до первого IQ (`defense mode friction triggered`). Серверная политика, которая отправляет `retry-after-challenges`, не видна (unknown).

### 9.5 Нет клиентской аттестации companion-устройства

Ничто в полезной нагрузке pair-device не доказывает, какое программное обеспечение запускает companion-устройство: `ref`, `pub-key`, ключ идентичности, secret adv и символ платформы самодекларируются QR. Что доказывают подписи — это то, что это основное устройство авторизовало именно этот ключ идентичности. Любая проверка "официальный клиент" — на стороне сервера (вердикт 465 обрабатывается только на стороне клиента).

### 9.6 Код роли companion-устройства в том же APK (кратко)

| Элемент | Находка |
|------|---------|
| Дочерние элементы IQ `companion_hello` | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; атрибут `should_show_push_notification` (found, `C0YS`) |
| код | `K1T.A00` base32 от 5 случайных байт (4.3) |
| ротация QR | IQ `pair-device-rotate-qr` с атрибутами `stage` 0/1/2 и опциональным `sentinel`, дочерний `ref` |
| входящие IQ md | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (id 242, 243, 266, 278, 279) |
| содержимое `pair-success` и ответ companion-устройства `pair-device-sign` | не трассировано в этой сборке: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Сравнение с локальным исходным кодом; только совпадения и одно различие, которые были проверены с обеих сторон.

| Элемент | APK 2.26.41.6 | `baron-baileys-v2` | Результат |
|------|---------------|--------------------|--------|
| Полезная нагрузка QR | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | совпадает (4 поля) |
| Вывод кода привязки | PBKDF2-SHA256 131072 итераций, алфавит `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, тот же алфавит (`crypto.js`, `generics.js`) | совпадает |
| Bundle ключа | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, открытый текст identity ‖ identity ‖ random32 | та же раскладка (`messages-recv.js`) | совпадает |
| adv secret | HKDF(нулевая соль, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | совпадает |
| Обёртка HMAC | HMAC-SHA256(adv secret, [06 05 для hosted ‖] байты ADVSignedDeviceIdentity) | то же (`validate-connection.js`) | совпадает |
| Сообщения подписи аккаунта / устройства | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | то же | совпадает |
| Hosted-префикс списка индекса ключей | верификатор и подписывающий используют `06 02` для каждого списка; `06 07` — префикс аттестации не-E2EE | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` используется, когда `accountType == HOSTED` (`chats.js`) | **отличается**; поток hosted не используется этой consumer-сборкой, так что эффект различия unknown |

Утверждения "почему это не работает" не делается: companion-устройство Baileys, следующее совпадающим строкам, согласуется с тем, что здесь разбирает основное устройство; принятие сервером статически не проверяемо.

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

### 11.2 Поток кода привязки

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
