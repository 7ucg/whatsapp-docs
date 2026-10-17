<!-- src-sha1: 4ca6293d8bc9da2aebc5db6f104c88b12dce1bd0 -->
# WhatsApp Client Integrity — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** целостность и аттестация клиента Android — аттестация ключа Keystore ("blacknoise"), Play Integrity (стандартный Java API и классический native API), native-библиотека токенов WASafe, stanza `integrity_payload` / `keystore_attestation`, параметр регистрации `gpia`, самопроверка подписи приложения, флаг источника установки, телеметрия root / эмулятор / модифицированный клиент (`wam_daily`), что блокируется, а что только сообщается, что остаётся unknown

---

## 1. Что такое «целостность клиента» в этой сборке

Единого шлюза нет. Клиент создаёт несколько независимых доказательств и сигналов; каждый из них создаётся на устройстве и отправляется серверу. Клиентского кода, отказывающегося запускаться на изменённом, рутованном или переподписанном клиенте, не найдено. Все утверждения основаны на статическом анализе декомпилированного APK (`versionCode 264100600`). Уровни: **found** = прочитано в коде, **inferred** = выведено, **unknown** = статически не определить.

Обфусцированные имена зависят от сборки и были заново определены в 2.26.41.6 по стабильным строкам.

| Механизм | Что создаёт | Как отправляется | Использование сервером |
|----------|-------------|------------------|------------------------|
| Аттестация ключа Keystore, внутренний тег лога `blacknoise` (`C25730yT`) | Цепочка сертификатов DER ключа EC `AndroidKeyStore` с challenge аттестации | stanza `<ib><keystore_attestation>`; передача в native при регистрации; пути passkey и сопряжения companion | unknown (не наблюдается) |
| Play Integrity, стандартный Java API (`C45007Jkc`) | Токен Standard Integrity (`gpia`) | параметр HTTP-регистрации `gpia`; токен сопряжения companion ("md-pairing") | unknown |
| Play Integrity, классический native API (`libwhatsapp.so`, `WAJIntegrityGpiaStatusRequest`) | Токен Classic Integrity через JNI | `<ib><integrity_payload>` (Java-приёмник found; связь с native-производителем inferred) | unknown |
| WASafe (`libwasafe.so`, `libwasafedeps.so`) | Зашифрованный в стиле ECIES blob данных, переданных вызывающим, base64 | приёмник unknown | unknown |
| Самопроверка подписи приложения (`AbstractC38241gg`, `C27965CCj`) | значение 0/1 | общий атрибут WAM **6251** | unknown |
| Флаг источника установки (`CHH`) | boolean об установщике `com.android.vending` | атрибуты WAM `install_source_official`, **10255** | unknown |
| Флаги состояния устройства (`Cdt` → `C0Fp`) | `is_rooted`, `is_genymotion`, `is_monkeyrunner_running`, `is_using_custom_rom`, `is_whatsapp_plus_user` | событие WAM `wam_daily` | unknown |
| Диагностика поддержки (`C00L.A0F`) | тег "rted" | строки contact-us / отладочного отчёта | только поддержка |

Не аттестация целостности, не путать (см. 11): `com.whatsapp.integrityai` (обнаружение мошенничества на устройстве), `bizintegritysignals`, UI блокировки WFAC (`com.whatsapp.waffle.wfac`), связывание аккаунтов (`com.whatsapp.waffle`).

| Сущность | Имя в 2.26.41.6 | Роль |
|----------|-----------------|------|
| Аттестация Keystore | `C25730yT` | пара ключей, цепочка сертификатов, подпись (алиас `A00`/`A01`, `A02` генерация, `A03` цепочка, `A07` подпись) |
| Enum режима аттестации | `C02U` | `C02U.A00` = dynamic, `C02U.A01` = static |
| Runnable отправителя stanza | `RunnableC48591z1` case 3 через `C41141ly` | отправляет `keystore_attestation` |
| Обработчик подключения | `A01` в обработчике соединения (`smali/X/0Yq`) | планирует `sendKeystoreAttestation` |
| Работа при регистрации | `C25810yb`, `KZ2` case 39, `K49.A0s` | статическая аттестация в native, тег `regtime_ka` |
| Предварительный прогрев companion | `H1K` (аттестация), `H1J` (Play Integrity) | кэш цепочки / токена для сопряжения |
| Обёртка Play Integrity | `C45007Jkc` | подготовка + запрос standard API |
| HTTP регистрации | `K49` | добавляет `gpia` в параметры запроса |
| JNI-мост | `com.whatsapp.wamsys.JniBridge` | `sendAttestationResult`, callbacks `jnidispatch*`, `wsafeplatform_context` |
| Шлюз подписи | `AbstractC38241gg` | окно версий + SHA-1 сертификата подписи |
| Верификатор подписи | `C27965CCj` | имя пакета + SHA-256 сертификата подписи против встроенных значений |
| Future источника установки | `CHH` | `install_source_official` |
| Ежедневное событие WAM | `C0Fp` (`getEventNameForFalco()` = `wam_daily`) | флаги устройства |
| Заполнитель флагов WAM | `Cdt` (smali) | заполняет boolean-поля `C0Fp` |
| Помощники root / эмулятор | `C00L` | `A0F` root, `A0C` эмулятор, `A0B` custom ROM, `A0D` автоматизация тестов |

---

## 2. Аттестация ключа Keystore ("blacknoise")

### 2.1 Генерация ключа (`C25730yT.A02`)

Всё управляется ab-prop **1934** (`A06()`, по умолчанию `true`).

| Элемент | Значение | Уровень |
|---------|----------|---------|
| Keystore | `AndroidKeyStore` | found |
| Назначение ключа | `4` (`PURPOSE_SIGN`), digests `SHA-256`, `SHA-512`, аутентификация пользователя не требуется | found |
| Алгоритм | ab-prop **2076**, по умолчанию `"EC"`; `"RSA"` добавляет padding `PKCS1` | found |
| Алгоритм подписи | ab-prop **2075**, по умолчанию `"SHA256withECDSA"` | found |
| Основа алиаса | ab-prop **2074**, по умолчанию `the_well_of_wishes_awaits_in_the_crypt_of_decay`; жёстко заданный резерв `my_personal_mini_pony`, когда prop равен null | found |
| Алиас | dynamic: `<base>[_<suffix>]`; static: `<base>_static[_<suffix>]`; суффикс = случайный UUID, хранящийся в prefs `ka_key_store_dynamic_alias_suffix` / `ka_key_store_static_alias_suffix`, меняется, когда при регенерации обнаруживается существующий суффикс | found |
| Срок действия сертификата | now + ab-prop **2079** секунд (по умолчанию 86400) | found |
| Challenge аттестации | задаётся только на SDK >= 24 | found |
| Аттестация свойств устройства | `setDevicePropertiesAttestationIncluded(true)` на SDK >= 31; при `ProviderException` повтор без неё (лог `blacknoise/disbabling device ids att`) | found |

Структура challenge аттестации (found):

```
challenge = BE64(unix_seconds) ‖ 0x1F ‖ nonce
nonce     = caller-supplied bytes, else SecureRandom(ab-prop 2078 bytes, default 32)
```

### 2.2 Обновление и ограничение частоты

| Pref / prop | Значение | По умолчанию | Уровень |
|-------------|----------|--------------|---------|
| `ka_refresh_ts` + ab-prop **2079** | dynamic-ключ пересоздаётся, когда старше этого | 86400 s | found |
| `ka_static_refresh_ts` + ab-prop **4878** | обновление static-ключа | 600 s | found |
| `ka_retried_ts` + ab-prop **2427** | dynamic: регенерация предпринята слишком рано -> лог `regeneration attempted too soon, waiting` | 600 s | found |
| `A04()` | удаляет оба алиаса и обнуляет все prefs `ka_*` | – | found |

### 2.3 Цепочка сертификатов (`C25730yT.A03`)

`keyStore.getCertificateChain(alias)`, у каждого сертификата `getEncoded()` (DER), конкатенация в обратном порядке (root первым, leaf последним) в один массив байтов. Пустая цепочка пишет в лог `empty list of certificates found`. Сбои передаются в error reporter как `attestation-creation`, `attestation-nocertchain`, `attestation-nosign` (found). Время логируется как `att-gen` / `att-sign` (found).

### 2.4 Подпись (`C25730yT.A07`)

`Signature.getInstance(prop 2075)` над данными вызывающего статическим ключом. Отсутствие записи ключа -> `attestation-nosign` "cannot sign payload, att pair missing". Вызывающих `A07` в декомпилированном коде не найдено (возможны пробелы декомпиляции); куда была бы отправлена подпись — unknown.

### 2.5 Четыре потребителя цепочки

| # | Триггер | Режим | Nonce | Приёмник | Уровень |
|---|---------|-------|-------|----------|---------|
| 1 | Сервер подключён (`handleConnected` в обработчике соединения, имя job `sendKeystoreAttestation`) | dynamic (`C02U.A00`) | статический (Noise) публичный ключ клиента (`C25710yR.A0H()`) | `<ib><keystore_attestation>chain</keystore_attestation></ib>` через `C10140Tq.A0X(node, 6)` | found |
| 2 | Регистрация (`K49.A0s`, job `regtime_ka`, runnable `KZ2` case 39) | static (`C02U.A01`) | статический публичный ключ клиента | `JniBridge.jvidispatchIOO(1, ctx, chain)` в native, с повтором/backoff (ab-props **2863** 1000 мс, **2864** 5 попыток); `K49.A0s` ждёт до ab-prop **4696** (1880 мс), когда его об этом просят | found (использование в native unknown) |
| 3 | Начало регистрации companion (`C0YS` `startcompanionreg` -> `H1K.A00`) | dynamic | статический публичный ключ клиента | кэшируется в `H1K` (поле `A02`), обновляется помощником в стиле `KeyAttestationLifetimeManager`; управляется ab-props **6430** (по умолчанию `true`), **7217** (bucket), интервал **6431** (600000 мс), повторы **6433**/**6434** | found (кэш); потребитель кэшированных байтов не выяснен: unknown |
| 4 | Серверный API passkey (`I16` case 18, `PasskeyServerApiImpl`) | dynamic | байты, предоставленные сервером | возвращается вызывающему passkey | found (что делает вызывающий — unknown) |

Шлюз stanza для #1: `A06()` и ab-prop **1935** (по умолчанию `true`), и не чаще одного раза в ab-prop **2067** секунд (по умолчанию 86400), хранится в pref `ka_stanza_sent_ts`. Null-цепочка пишет в лог `blacknoise: got null attestation chain in custom stanza` и ничего не отправляет (found).

Форма stanza (found):

```
<ib>
  <keystore_attestation>[binary: DER certs, root first]</keystore_attestation>
</ib>
```

`keystore_attestation` также является токеном словаря (второй словарь, `AbstractC40911lb.A01[0]`), поэтому кодируется в сети как токен (found).

Привязка: поскольку nonce в #1–#3 — это собственный статический публичный ключ Noise клиента, расширение challenge цепочки сертификатов несёт ключ идентичности, связывая аппаратный ключ со статическим ключом аккаунта (inferred из выбора nonce; серверная проверка unknown).

---

## 3. Play Integrity

### 3.1 Стандартный Java API (`C45007Jkc`)

| Элемент | Значение | Уровень |
|---------|----------|---------|
| API | `IntegrityManagerFactory.createStandard` -> `StandardIntegrityManager` | found |
| Номер облачного проекта | `293955441834` (`PrepareIntegrityTokenRequest.setCloudProjectNumber`) | found |
| Prepare (`A00(callback, tag)`) | с меткой tag; пропускается, если провайдер токена уже существует; отказ без сети; максимум 5 prepare за 60 s (pref `pref_gpia_prepare_call_count_in_last_interval`) | found |
| Request (`A01(callback, nonce, tag)`) | `StandardIntegrityTokenRequest.setRequestHash(nonce)`; завершается с 1003, если нет провайдера | found |
| Внутренние коды ошибок (`JCX`) | 1001 нет сети, 1002 слишком много вызовов prepare, 1003 не подготовлено, 1004 таймаут (`C47238Kk7`), 1005 нет статического ключа (`Kmc`) | found |
| События error reporter (`GKY`) | `ka_at_md_generate_attestation`, `gpia_at_md_prepare`, `gpia_at_md_generate_attestation` | found |

Места вызова prepare (found): `RegisterPhone` (tag `register_phone`), `VerifyPhoneNumber` (tag `verify_phone`), сопряжение companion (tag `md-pairing`, `H1J`), плюс путь повтора в `C41354Hz3`.

### 3.2 Параметр HTTP регистрации `gpia`

`K49.A0V` добавляет одно поле в карту HTTP-запроса регистрации:

```java
if (!flag(3753)) return;               // default false
nonce = Base64(static_public_key, NO_PADDING|NO_WRAP);   // C47343Kmc case 48
token = request(nonce, tag="reg");     // timeout ab-prop 4263, default 1800
map.put("gpia", token);
```

| Элемент | Значение | Уровень |
|---------|----------|---------|
| Шлюз | ab-prop **3753**, по умолчанию `false` | found |
| Nonce | base64 (flags 3) статического публичного ключа клиента (`C25710yR.A0H()`); null-ключ -> ошибка 1005 | found |
| Добавляется в | `checkIfExists` (два пути кода), `verifySecurityCode` | found |
| Другие запросы (запрос кода, финальная регистрация) | `A0V` там в декомпилированном коде не вызывается | found (отсутствие в декомпиляции) |
| Метрика времени | `gpia-param-prepare` | found |

По умолчанию `false` означает, что параметр отправляется, только когда сервер включает prop 3753. Требует ли его сервер регистрации: unknown.

### 3.3 Токен сопряжения companion

`H1J` (управляется `A07(...)`, prop **7006** по умолчанию `false`, интервал **7007** = 21600000 мс) подготавливает ("md-pairing"), а `I16` case 3 запрашивает токен с nonce = base64(статический публичный ключ, flags 3), таймаут prop **7010** (1000 мс). Сбои логируются как `gpia_at_md_prepare` / `gpia_at_md_generate_attestation`. Потребитель токена не выяснен (unknown).

### 3.4 Классический native API и `integrity_payload`

Строки в `libwhatsapp.so` (found): `WAJIntegrityGpiaStatusRequest`, `WAJIntegrityGpiaStatusRequestAttributes`, `_WAJIntegrityTriggerGPIAWithRequestAttributes`, `_WAJIntegritySendResponseOrRetry`, `_WCAAPIGenerateGPIAParamOnMain`, и сигнатуры JNI для `IntegrityManagerFactory.create(Context)`, `IntegrityTokenRequest.Builder` (`setNonce`, `setCloudProjectNumber`), `IntegrityManager.requestIntegrityToken`. Таким образом, native-код сам управляет Play Integrity (классический запрос) через JNI.

Java-приёмник (found):

```java
// JniBridge.jnidispatch... case 3  (callback "sendAttestationResult")
node = <ib><integrity_payload>{string}</integrity_payload></ib>   // C10140Tq.A0X(node, 194)
metric type "safety-net-attestation", result "success"/"failed"
```

Строка типа метрики `safety-net-attestation` — устаревшая метка; API SafetyNet не используется (см. 10). Утверждение «native `WAJIntegrityGpiaStatusRequest` создаёт строку `integrity_payload`» **inferred** по именам; цепочка вызовов внутри stripped native-кода не прослежена. Что запускает native-запрос статуса (расписание клиента или запрос сервера) — unknown.

Native читает ab-props через `jnidispatchIII(feature, kind)`; сопоставленные ID (found): kind 0: 12->13178, 13->13456, 15->22925, 16->24048; kind 1: 13->13455. `jnidispatchO(1)` возвращает строку ab-prop **10266** (по умолчанию пустая). Назначение этих props unknown.

### 3.5 Другие пользователи Play Integrity

| Класс | Использование | Уровень |
|-------|---------------|---------|
| семейство `JK4`, `KM0` | SDK reCAPTCHA Enterprise (`recaptcha.net`) со своим `StandardIntegrityManager`; результат попадает в параметр HTTP `recaptcha` (`K49.A0Z`), когда присутствует | found |
| `KLL`, `KLN`, `C42885In8`… | встроенная реализация integrity из Play Core (код библиотеки) | found |

---

## 4. Native-библиотека WASafe

### 4.1 Java-сторона

| Hook | Поведение | Уровень |
|------|-----------|---------|
| `jnidispatchI(4)` | загружает `libwasafe.so` (`"wasafe"`), при `UnsatisfiedLinkError` пишет в лог `WCAAPIEnsureSafeLibraryLoaded libwasafe.so load failed` | found |
| `jnidispatchI(5)` | возвращает pref `runtime_override` из SharedPreferences `wsafeplatform_context`, иначе константу `1090327562` | found |
| Атрибут WAM **15611** | та же константа, записанная как строка `1090327562` в общих атрибутах | found |

Значение `1090327562` unknown (кандидат: значение типа runtime / обнаружения WASafe, не проверено).

### 4.2 `libwasafe.so` (14480 байт, arm64, stripped)

Экспорты: `WASafeSignalsCreate`, `WASafeSignalsConfigure`, `WASafeSignalsPrepare`, `WASafeSignalsGetBase64EncodedData`, `WASafeSignalsRelease`, `WASafeStatus`. Импорты: libc (`stat`, `rand`, `srand`, `gettimeofday`, `malloc`…) и `WASafeDepsCrypto*` из `libwasafedeps.so`.

| Функция | Декомпилированное поведение | Уровень |
|---------|-----------------------------|---------|
| `WASafeSignalsConfigure(x)` | сохраняет `x` (тип обнаружения) в глобальную переменную, очищает вторую глобальную | found |
| `WASafeSignalsPrepare()` | записывает константу статуса `0x1092` в глобальную переменную; другой работы нет | found |
| `WASafeSignalsGetBase64EncodedData()` | пропускает данные/длину контекста через encrypt+base64 (`sub_6a00`) и возвращает `{ptr, len}` | found |

Эта сборка `libwasafe.so` не содержит сбора сигналов: нет строк про root, отладчик, hook, эмулятор или пути файлов, а единственный импорт файловой системы — `stat`. `libwhatsapp.so` также содержит строку `WASafeSignalsStub` и `WAIntegrityPrepareSafeSignals(WASafeDetectionType)` с тегами лога `safesignals/prepare` и `safesignals/generate` (found). Откуда берутся шифруемые данные — unknown.

### 4.3 `libwasafedeps.so`

Экспортирует `WASafeDepsCryptoInputCreate`, `...SetServerPublicKey`, `...SetData`, `...EncryptBase64`, `...ResultGetData/GetLength/Release`; импортирует mbedtls (`ctr_drbg`, `entropy`, `gcm_setkey`, `gcm_crypt_and_tag`). Структура (found по импортам и именам): случайный эфемерный ключ, общий секрет с публичным ключом сервера, AES-GCM, base64. Точная кривая и KDF для этой сборки заново не декомпилировались; конструкция Curve25519 ECDH + AES-GCM — **inferred**. Значение публичного ключа сервера и его ротация: unknown.

---

## 5. Самопроверка подписи приложения и источник установки

### 5.1 Шлюз (`AbstractC38241gg.A00`)

```java
long vc = versionCode;
if (vc < 264100600 || vc > 264100608) return 0;          // outside window
sha1 = Base64(SHA-1(signatures[0]), 11);
return "OKD31QX-GP7GT780Psqq8xDb15k".equals(sha1) ? 1 : 0;
```

Окно версий начинается с `versionCode` этой сборки (264100600). Результат кэшируется в static.

### 5.2 Верификатор (`C27965CCj.A00(pkg, certBytes)`)

| Шаг | Поведение | Уровень |
|-----|-----------|---------|
| 1 | Имя пакета маскируется XOR 5-байтовым ключом и сравнивается с двумя встроенными массивами байтов, декодирующимися в `com.whatsapp` и `com.whatsapp.w4b` | found |
| 2 | Если пакет ни тот, ни другой: сразу возвращает `true` | found |
| 3 | Иначе SHA-256 байтов сертификата, маскированный XOR, сравнивается с двумя встроенными 32-байтовыми значениями; совпадение -> `false`, несовпадение -> `true` | found |

Декомпиляция этого метода не удалась; шаги прочитаны из дампа инструкций.

### 5.3 Потребитель

Внутри WAM `initializeCommonAttributes` (runnable `RunnableC29340CoR`):

```java
long r = AbstractC38241gg.A00(ctx);          // 1 only when version window + SHA-1 match
if (r == 1) r = verifier(pkg, cert) ? 0 : 1;
common attribute 6251 = r;                   // 1 = both checks passed, 0 = otherwise
```

Итак, **6251 = 1** означает «сертификат подписи совпадает со встроенными значениями WhatsApp» (found); 0 означает несовпадение или сборку вне окна (found). Значение только сообщается в телеметрии. Ничто в клиенте на него не реагирует (путей кода, читающих результат для блокировки или ухудшения работы, не найдено). Использование сервером: unknown.

### 5.4 Источник установки

`getInstallSourceInfo().getInstallingPackageName()` (SDK >= 30, иначе `getInstallerPackageName`), сравнивается с `com.android.vending` (`C18970md`, `RunnableC29340CoR`): сохраняется в future `CHH.A01`. Сообщается как атрибут WAM **10255** и как `install_source_official` в наборах атрибутов логирования (`HO4`, `C08650Nr`, `AbstractC35718FdU`). Также поле `C0Fp` `install_source` (`wam_daily`). Отдельные применения того же сравнения выбирают установщик модулей Voltron (`AbstractC12860bs`) (found). Результат — телеметрия плюс маршрутизация загрузки модулей; принуждения не найдено.

---

## 6. Сигналы root, эмулятора и модифицированного клиента

### 6.1 Флаги устройства `wam_daily`

`C0Fp` — это событие `wam_daily` (`getEventNameForFalco()`); его поля ниже заполняются в `Cdt` (smali). Сообщаются, не принудительно применяются (found).

| Поле | Источник | Уровень |
|------|----------|---------|
| `is_rooted` | `C00L.A0F(telephony helper)` | found |
| `is_using_custom_rom` | `C00L.A0B()` (строки kernel/manufacturer/display: cyanogen, debug, Darky, XDAndroid, MIUI…) | found |
| `is_whatsapp_plus_user` | `Class.forName("org.acra.ACRA")` успешен (класса нет в этом APK; обычно входит в состав сторонних клиентов) | found (проверка); «обычно входит» inferred |
| `is_genymotion` | проверка пакета `com.genymotion.superuser` в области `Cdt`; точное условие прослежено частично | found (проверка), логика inferred |
| `is_monkeyrunner_running` | источник не выяснен | unknown |
| `google_play_services_available`, `google_play_services_version`, `install_source` | присутствуют в том же событии | found |

### 6.2 Эвристика root `C00L.A0F`

Кэшируется в static. Истинно, если выполняется любое из: `Build.TAGS` содержит `test-keys`; существует `/system/app/Superuser.apk`; исполняемый `su` в `/system/bin/su` или `/system/xbin/su` (`canExecute`), с дополнительным логированием `app/dly`; похожие на эмулятор product/model/manufacturer (`sdk`) или отсутствие SIM/телефонии (флаг `z` используется только для суффикса лога, found). Связанные помощники: `A0C` эмулятор (бренд/устройство `generic`, `goldfish`, `ranchu`, `google_sdk`, `Emulator`, `Android SDK built for x86`, `Genymotion`), `A0D` автоматизация тестов (системное свойство `fb.running_sapienz`).

### 6.3 Где потребляется `A0F`

| Потребитель | Использование | Уровень |
|-------------|---------------|---------|
| построитель отладочного отчёта `C10V` | добавляет `DC-RTED` (root) и `DC-BACRM` (custom ROM) в текст диагностики | found |
| карта диагностики contact-us `C1Z` | ключ `diagnostic` = `rted ` (и `nw-wap `, если присутствует `org.acra.ACRA`) | found |
| `C28049CFz` (состояние потока верификации) | контекст contact-us `register-phone-rtd` на экране номера телефона | found |
| `Cdt` | `wam_daily.is_rooted` | found |
| `KH2` (crash reporter `lacrima`) | `ExtraDeviceInfoCollector` записывает флаг root (`test-keys`, `Superuser.apk`, `su` в `PATH`) в отчёты о сбоях | found |

Ничто из этого не блокирует регистрацию или обмен сообщениями (found: ни одна ветвь не завершает процесс по этим boolean). Учитывает ли сервер флаги `wam_daily`: unknown.

### 6.4 Не найдено

| Проверка | Результат |
|----------|-----------|
| Строки Magisk, Xposed (`de.robv`), Substrate, Frida в коде WhatsApp (`libwhatsapp.so`, Java) | не найдено |
| `ro.kernel.qemu`, самопроверка `FLAG_DEBUGGABLE` | не найдено |
| Список запрещённых пакетов для именованных мод-клиентов (GB, FM, Plus) | не найдено |
| Самопроверка CRC dex / assets | не найдено в этом проходе (не искалось исчерпывающе) |
| Проверка аппаратно защищённого ключа (`KeyInfo.isInsideSecureHardware`) в собственном коде аттестации WhatsApp | не найдено (только в классах библиотек `BinderC48420LDc`, `C51962N8y`) |
| `FetchIntegritySignals`, `IntegrityChallengeResponse`, `relax_integrity_constraints_for_bb_wa_tenured_accounts` | нигде в APK не найдено (Java, smali, assets, native) |
| API `SafetyNet` | не найдено |

`isDebuggerConnected` встречается только в детекторе ANR (`SigquitBasedANRDetector`) и помощниках сбоев.

---

## 7. Feature flags и ab-props

| ID | Значение / по умолчанию | Что контролирует |
|----|-------------------------|------------------|
| **1934** | `true` | главный шлюз blacknoise (`C25730yT.A06`) |
| **1935** | `true` | отправка stanza `keystore_attestation` после подключения |
| **2067** | 86400 | минимум секунд между отправками stanza |
| **2074** | `the_well_of_wishes_awaits_in_the_crypt_of_decay` | основа алиаса ключа |
| **2075** | `SHA256withECDSA` | алгоритм подписи |
| **2076** | `EC` | алгоритм ключа |
| **2078** | 32 | длина случайного nonce |
| **2079** | 86400 | срок действия сертификата и секунды обновления dynamic |
| **2427** | 600 | минимум секунд между dynamic-регенерациями |
| **4878** | 600 | секунды обновления static |
| **2863** / **2864** | 1000 / 5 | основа backoff при регистрации (мс) / попытки |
| **4696** | 1880 | ожидание аттестации при регистрации (мс) |
| **3753** | `false` | параметр регистрации `gpia` |
| **4263** | 1800 | таймаут запроса `gpia` |
| **6430** | `true` | предварительный прогрев аттестации companion (`H1K`) |
| **6431** | 600000 | возраст кэша аттестации companion (мс) |
| **6433** / **6434** | 5 / 1000 | попытки / таймаут lifetime-manager аттестации companion |
| **7217** | 1 | модуль bucket аттестации companion |
| **7006** | `false` | предварительный прогрев Play Integrity companion (`H1J`) |
| **7007** | 21600000 | возраст кэша токена companion (мс) |
| **7009** / **7010** | 5 / 1000 | попытки / таймаут Play Integrity companion |
| **10266** | пустая строка | строка, передаваемая в native через `jnidispatchO(1)` |
| **26215** | `false` | альтернативный путь verifySecurityCode в `K49` (не специфичен для integrity) |

По умолчанию — встроенные при компиляции значения; сервер может переопределять ab-props (found: таблица props; серверные значения unknown).

---

## 8. Случаи ошибок

| Симптом | Причина | Исправление / примечание |
|---------|---------|--------------------------|
| Нет stanza `keystore_attestation` | prop 1934 или 1935 false; отправлено за последние 2067 s; null-цепочка | по замыслу |
| отчёт об ошибке `attestation-creation` | сбой генерации ключа (`ProviderException`, нет TEE) | повтор позже, ограничивается 2427 |
| `attestation-nocertchain` | `getCertificateChain` не удался или пуст | – |
| `attestation-nosign` | `A07` вызван без записи статического ключа | – |
| `blacknoise/regeneration attempted too soon, waiting` | `ka_retried_ts` в пределах 600 s | ждать |
| `blacknoise: not boostrapped for reg` | `C25810yb.A00` false в момент регистрации | аттестация пропущена для этой регистрации |
| Play Integrity 1001 / 1002 / 1003 / 1004 / 1005 | нет сети / > 5 prepare за 60 s / не подготовлено / таймаут / нет статического ключа | внутренние коды (`JCX`) |
| `gpia` отсутствует в запросе регистрации | prop 3753 false или запрос не удался (null-результат помещён как пустой) | см. 3.2 |
| `libwasafe.so load failed` | `UnsatisfiedLinkError` | только лог |
| Атрибут подписи 6251 = 0 | переподписанный APK, другой сертификат или сборка вне `264100600..264100608` | только телеметрия |

---

## 9. Baileys / протокольные клиенты

| Элемент | Утверждение | Уровень |
|---------|-------------|---------|
| Проверки на стороне приложения | Чисто протокольный клиент никогда не запускает ни один из приведённого выше кода | found (по определению) |
| stanza `keystore_attestation` / `integrity_payload` | Клиент, который их опускает, просто их не отправляет; отклоняет ли сервер такие аккаунты, ограничивает или помечает: unknown | unknown |
| Параметр регистрации `gpia` | Опционален по умолчанию (prop 3753 `false`); принудительное применение на сервере по региону/аккаунту: unknown | unknown |
| Подделка аттестации | Цепочка должна опираться на аппаратные/Google-корни и нести challenge; клиентского секрета для копирования нет, проверка выполняется на сервере | inferred |
| Известный риск | Серверная политика зависит от данных, которые этот отчёт не может наблюдать (поведение, возраст аккаунта) | unknown |

Исправление: статически не выводится. Отправка сфабрикованных значений не подтверждается ни одним найденным здесь свидетельством.

---

## 10. Ключевые различия

| Не путать | Факт |
|-----------|------|
| Строка метрики `safety-net-attestation` и SafetyNet | только метка; payload приходит из Play Integrity; API SafetyNet в коде нет |
| `keystore_attestation` и `integrity_payload` | разные stanza: цепочка сертификатов DER (байты) против строки токена Play Integrity; разные производители (Java/Keystore против native/Play) |
| Java `gpia` (standard API, request hash) и native classic GPIA | разные API и приёмники (параметр HTTP против `<ib>`); построение nonce в native-варианте не прослежено |
| Static и dynamic аттестация | static-алиас `..._static` (регистрация), dynamic-алиас (после подключения, companion, passkey) |
| Nonce | статический публичный ключ клиента у трёх потребителей; байты сервера у потребителя passkey |
| `blacknoise` и WASafe | аттестация Keystore (Java) против native-библиотеки зашифрованного blob |
| WASafe и «signals» | `libwasafe.so` этой сборки ничего не собирает; имя подразумевает сигналы, код — нет |
| 6251 и 10255 | совпадение подписи против установщика Play |
| `is_whatsapp_plus_user` и allowlist мод-клиентов | одна рефлексивная проверка класса; allowlist не существует |
| `integrityai`, `bizintegritysignals` | функции безопасности контента / бизнеса (обнаружение мошенничества, UI бизнес-сигналов), не аттестация клиента |
| WFAC / `waffle` | UI блокировки и связывание аккаунтов, не компонент аттестации |
| Отчёт и принуждение | все найденные результаты root, эмулятора, подписи и установщика — телеметрия или текст для поддержки |

---

## 11. Связанные компоненты, не являющиеся аттестацией клиента

| Компонент | Факты | Уровень |
|-----------|-------|---------|
| `com.whatsapp.integrityai` | `IntegrityAiOrchestrator`, `ScamDetectorImpl`, загрузка моделей (`IntegrityAiModelDownloadCoordinator`, уровень устройства), UI с согласием `ScamDetectionSettingsActivity`; тег хранилища результатов `IntegrityAi/ScamDetectionResultStore`; native-классификатор с именем `kaleidoscope` в этой сборке заново не проверялся | found (структура); native-часть unknown |
| `com.whatsapp.bizintegritysignals` | GraphQL fetcher и manager для сигналов бизнес-целостности, показываемых в UI | found |
| `com.whatsapp.waffle.wfac` | UI решения о блокировке (`WfacBanActivity`, `WfacBanDecisionFragment`, `WfacUnbanDecisionFragment`) | found |
| `com.whatsapp.waffle.accountlinking` и соседние | связывание аккаунтов, SSO, кросспостинг, проверка возраста | found |

---

## 12. Сквозной процесс

```
[Registration screens: RegisterPhone / VerifyPhoneNumber]
    │  C45007Jkc.A00  prepareIntegrityToken (cloud project 293955441834, tag register_phone / verify_phone)
    │  K49.A0s  "regtime_ka": C25730yT.A03(static)  nonce = static pubkey
    │      └── JniBridge.jvidispatchIOO(1, ctx, chain)  ──►  [native wamsys]  (use unknown)
    ▼
[K49 HTTP: exist / verifySecurityCode]
    │  if ab-prop 3753:  gpia = standard-API token, requestHash = b64(static pubkey)
    ▼
[WA registration server]  (validation not observed)

[Connected session]
    │  handleConnected ─► job "sendKeystoreAttestation"
    │  ab-props 1934 && 1935, once per 86400 s
    │  C25730yT.A03(dynamic, nonce = static pubkey) ─ AndroidKeyStore EC key, challenge = ts ‖ 0x1F ‖ nonce
    ▼
<ib><keystore_attestation>DER chain, root first</keystore_attestation></ib>
    ▼
[WA server]  (use unknown)

[Native libwhatsapp]  WAJIntegrityGpiaStatusRequest ─► classic IntegrityManager via JNI   (inferred link)
    │  JniBridge callback sendAttestationResult
    ▼
<ib><integrity_payload>token</integrity_payload></ib>   (node code 194)
    ▼
[WA server]  (use unknown)

[Companion pairing]
    │  C0YS startcompanionreg ─► H1K (chain cache) + H1J (GPIA token, tag md-pairing)
    ▼  consumer of cached bytes/token: unknown

[Telemetry, daily and common attributes]
    │  6251 signature match, 10255 Play installer, 15611 wasafe constant
    │  wam_daily: is_rooted, is_genymotion, is_using_custom_rom, is_whatsapp_plus_user, install_source
    ▼
[WA server]  (use unknown)
```

---

## 13. Unknowns

| Вопрос | Почему unknown |
|--------|----------------|
| Серверная проверка и принудительное применение любого токена | серверная сторона, трафик не наблюдался |
| Что запускает native `WAJIntegrityGpiaStatusRequest` и как строится nonce | stripped native-код не прослежен (декомпилятор для большой библиотеки здесь недоступен) |
| Откуда берутся входные данные WASafe и что означает `1090327562` | производитель в stripped native не найден |
| Использование в native байтов аттестации при регистрации | виден только вход JNI (`jvidispatchIOO(1)`) |
| Потребители кэшированной цепочки `H1K` и токена `H1J` | места вызова не выяснены в декомпилированном коде |
| Значение ab-prop 10266 и ID функций `jnidispatchIII` | только значения |
| Источник `is_monkeyrunner_running`, точное условие `is_genymotion` | не прослежено |
| Вызывающие `C25730yT.A07` (подпись) | не найдены; возможны пробелы декомпиляции |
| Существует ли какое-либо принуждение для флагов телеметрии | клиентская ветвь не найдена; сервер unknown |
