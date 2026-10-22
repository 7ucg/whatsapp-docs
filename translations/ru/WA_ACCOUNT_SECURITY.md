<!-- src-sha1: b8a925dee480430088a421b7aba690bc2f641a5f -->
# WhatsApp Безопасность аккаунта — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-22
**Область:** верификация номера телефона для существующего аккаунта (регистрационный HTTP `/v2/*`), методы второго фактора, PIN двухэтапной проверки и резервный email, пароль аккаунта (конверт `#PWD_WA`, зависимость от canonical user), нативный код OPAQUE / VOPRF и что он реально обслуживает, вход и управление passkey, доверенные устройства, восстановление аккаунта (обмен nonce canonical user), soft logout / login-back, операции w:mex (doc_id, переменные, корни ответов), feature-флаги, заметки по Baileys

---

## 1. Что это (технически)

«Безопасность аккаунта» в Android-клиенте не является единой подсистемой. Это пять независимых механизмов поверх процесса регистрации по номеру телефона. Все утверждения основаны на статическом анализе декомпилированного APK; в сети ничего не перехватывалось. Уровни: **found** = прочитано в коде или ассетах, **inferred** = выведено из кода, **unknown** = не выяснено. Обфусцированные имена зависят от сборки и заново определены в 2.26.41.6.

| Механизм | Где применяется | Учётные данные | Основные клиентские классы (2.26.41.6) |
|-----------|---------------------|------------|-------------------------------|
| Верификация телефона (OTP) | регистрационный HTTP, `/v2/exist` → `/v2/code` → `/v2/register` | SMS / голос / flash / старое устройство / email OTP / silent auth | `K49` (`RegistrationHttpManager`), `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Второй фактор при регистрации | `/v2/register` с причиной `security_code`, затем `VerifyTwoFactorAuth` | 6-значный PIN, пароль аккаунта, email OTP | `VerifyTwoFactorAuth`, `EnumC43759JAu`, `HOZ` |
| Двухэтапная проверка (PIN + email) | IQ `urn:xmpp:whatsapp:account` `<2fa>` | 6-значный PIN, необязательный резервный email | `C1DP` (`TwoFactorAuthManager`), `C1DT` (`TwoFactorXmppMethods`) |
| Пароль аккаунта | w:mex (`whatsapp-android-mex`, `whatsapp-android-www`) | 8-20 символов, буква + цифра | `PasswordRepository`, `PasswordServerApiImpl`, `CanonicalPasswordService` |
| Passkey (WebAuthn) | `/v2/passkey_auth` при входе; IQ `passkey` или w:mex для управления | платформенный passkey через Credential Manager | `PasskeyServerApiImpl`, `PasskeyCreateFlow`, `PasskeyVerifier`, `K15` |
| Доверенное устройство | w:mex | серверная запись с ключом в виде хешированного `ANDROID_ID` | `TrustedDevicesServerApiImpl`, `RegTrustedDeviceGraphQLHelper` |
| Soft logout / login-back | w:mex | нет (флаг состояния) | `LogoutManager`, `LogoutPushManager` |
| Восстановление аккаунта | w:mex, Meta canonical user | RSA/AES-конверт секрета, сгенерированного клиентом | `AccountRecoveryManager` |

Два момента, определяющих весь отчёт:

- Конечный автомат OPAQUE в `libwhatsapp.so` привязан к паролю **сквозного шифрованного бэкапа** (обработчики `encb/*`), а не к паролю аккаунта (раздел 6).
- Пароль аккаунта в этой сборке создаётся и меняется через `XfbWaCreatePasswordMutation` / `XfbWaChangePasswordMutation` с RSA/AES-конвертом (`#PWD_WA:11`), и только если у приложения есть учётные данные Meta canonical user (раздел 5).

---

## 2. Транспорты и каталог операций

### 2.1 Четыре транспорта

| Транспорт | Назначение | Подтверждение |
|-----------|----------|----------|
| HTTPS `/v2/<name>` (регистрационный стек) | верификация телефона, второй фактор при входе, passkey-assertion, подтверждение устройства | found: константы путей в `AbstractC45307Jps` (раздел 3.1) |
| IQ `xmlns="urn:xmpp:whatsapp:account"` | установка / проверка / получение PIN и email; OTP email аккаунта; username и т. д. | found |
| IQ `xmlns="passkey"` (smax id 125, 126, 129) | устаревшие passkey start / finish / clear | found, под флагами 10452 / 10453 / 10461 |
| IQ `xmlns="w:mex"` | все GraphQL-операции ниже | found |

### 2.2 Конверт w:mex и источник doc_id

Переменные отправляются как JSON. Почти каждая мутация оборачивает свои поля в один объект: хелпер `AbstractC197058a0.A17(obj, vars)` сохраняет объект под ключом `input` (found). Исключения: две мутации паролей `Xfb*` кладут `encrypted_password` под `data` (found); `PasskeyDeleteMutation` тоже использует `input` (через `c16770ig.A00(obj, "input")`).

doc_id не являются литералами в коде. Клиент отправляет имя операции и имя конфига (`whatsapp-android-mex`, `whatsapp-android-www`, `whatsapp-android-facebook-schema`); числовой id читается из `assets/whatsapp-android-{mex,www,facebook-schema}_client_persist_ids.json` (found). Каждый doc_id ниже прочитан из этих ассетов в 2.26.41.6, а имя операции сверено с местом вызова. Ни один не `tested`.

### 2.3 Каталог операций (места вызова есть)

Переменные находятся внутри `input`, если не указано иное. «Корень» — имя объекта ответа, которое читает клиент.

| Операция | doc_id | Конфиг | Переменные | Корень и читаемые поля |
|-----------|--------|--------|-----------|----------------------|
| `HasPasswordQuery` | `25379221318423478` | mex | нет | `xwa2_has_password`: `has_password`, `upgrade_needed` |
| `DeletePasswordMutation` | `27247058691550586` | mex | нет | `xwa2_delete_password`: `success`, `twofa_auto_disabled`; ошибка 409 означает «нужен email» |
| `GetTwofaQuery` | `27608881388708005` | mex | `device_id` | `xwa2_get_twofa`: `twofa_enabled`, `twofa_methods[]{method,value,state}`, `is_device_trusted`, `latitude`, `longitude` |
| `SetTwofaMutation` | `28092515560345874` | mex | `twofa_enabled` (bool), `device_id` | `xwa2_set_twofa`: `success`, `twofa_already_enabled`, `is_device_trusted` |
| `WaPasswordEncryptionKeyQuery` | `27318258844468227` | www | нет | `wa_password_encryption_key`: `public_key` (PEM), `key_id` |
| `XfbWaCreatePasswordMutation` | `36595298760118580` | www | `data.encrypted_password` (не под `input`) | `xfb_wa_create_password` (поля успеха / ошибки не выяснены) |
| `XfbWaChangePasswordMutation` | `27534818572826036` | www | `data.encrypted_password` | `xfb_wa_change_password` |
| `AddTrustedDeviceMutation` | `24522952587403287` | mex | `device_id`, `device_name` | `xwa2_add_trusted_device.list_of_trusted_device[]` |
| `UntrustTrustedDeviceMutation` | `26574930682133620` | mex | `device_id`, `reason` (`"REREG"` в единственном вызове) | корень не выяснен |
| `DeleteTrustedDeviceMutation` | `33867503889559538` | mex | `device_id` | `xwa2_delete_trusted_device` (bool) |
| `GetTrustedDevicesQuery` | `27391232653862770` | mex | `device_id` | `xwa2_get_trusted_devices.list_of_trusted_device[]`: `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` |
| `WhatsappTrustedDeviceRegistration` | `27335489319457030` | facebook-schema | `client_mutation_id`, `payment_type="TRUST_BINDING"`, `platform_trust_token`, null `actor_id` / `logging_id` / `product_id` | trust binding платежей (`RunnableC53437NtS`), а не доверенное устройство для входа |
| `RegistrationPasskeyStartRegisterMutation` | `25415371271434748` | mex | нет | `xwa2_passkey_start_register.credential_create` (строка) |
| `RegistrationPasskeyFinishRegisterMutation` | `24611221275218156` | mex | `credential`, `key_attestation` | `xwa2_passkey_finish_register` (bool) |
| `RegistrationPasskeyEnableMutation` | `25147880151540247` | mex | `credential` | `xwa2_passkey_enable` (bool) |
| `RegistrationPasskeyClear` | `25111972538494859` | mex | нет | `xwa2_passkey_clear` (bool) |
| `RegistrationPasskeyUpdateClientEncryptionStatusMutation` | `24866837389649930` | mex | `credential`, `status` (true) | `xwa2_passkey_update_client_encryption_status` (bool) |
| `PasskeyListExistResponseQuery` | `26930537423220681` | mex | нет | `xwa2_passkey_exist_v2`: `result`, `uuid`, `passkeys[]{credential,create_ts_s,used_ts_s,password_manager,aaguid,usecases,is_disabled}` |
| `PasskeyDeleteMutation` | `25225683640428243` | mex | `credential_ids` (список) | `xwa2_passkey_delete.credential_ids` |
| `AccountLoginMutation` | `27298465499757127` | mex | `phone_number` (сырая строка JID) | не читается |
| `AccountLogoutMutation` | `26863447609979194` | mex | `enabled_biometric` (bool), `phone_number` | не читается; клиентский таймаут 5 с |
| `WWWTriggerAcountRecovery` | `24896267680055094` | mex | `nonce_encryption_key` (base64 PEM), `use_case`, `registration_trace_id`, `request_id` | nonce доставляется уведомлением (раздел 9) |
| `WWWExchangeNonceForAccessToken` | `25727187160203620` | mex | `nonce`, `use_case`, `encrypted_password`, `request_id`, `registration_trace_id` | access token |
| `WWWGetNonceForCompanionDevice` | `24635485196143064` | mex | `fbid`, `nonce_encryption_key`, `encrypted_password`, `request_id`, `registration_trace_id` | canonical user для companion |
| `RegAccountTransferVerifyTokenMutation` | `7580940708621318` | mex | `token` | проверка OTP переноса аккаунта, таймаут 60 с |
| `ValidateVerifierConfidence` | `25879669248324812` | mex | `authResponse` (base64) | ping уровня доверия autoconf |
| `GetRegistrationUpsells` / `GetDynamicRegistrationUpsells` / `RegistrationDynamicUpsellShown` | `24265038133175291` / `32273353145641323` / `25435755019399064` | mex | shown: `input="PASSKEYS"` (строка) | планирование upsell при регистрации |

### 2.4 Операции в ассетах без места вызова в этой сборке

Поиск по имени в `java_src` и smali; ссылок нет (found). Их переменные и ответы неизвестны.

| Операция | doc_id |
|-----------|--------|
| `SetPasswordMutation` | `33855141324134176` |
| `CheckPasswordMutation` | `26881928138061632` |
| `PasskeyExistResponseQuery` | `25188064727509430` |
| `PasskeyRequestChallengeMutation` | `26311497405176139` |
| `PasskeyVerifyChallengeMutation` | `26876394218624479` |
| `RegistrationPasskeyDisableMutation` | `27775237998742831` |

В 2.26.41.6 вход по passkey не использует мутации request / verify; он использует `/v2/passkey_auth` (раздел 7.1). Операции passkey для платежей (`PaymentsPasskey*`) и Бразилии (`BrPasskey*`) — отдельные поверхности и здесь не рассматриваются.

---

## 3. Верификация номера телефона для существующего аккаунта

### 3.1 Регистрационный стек и эндпоинты

`K49` (`RegistrationHttpManager`) строит запросы и разбирает результаты. Существуют два HTTP-стека: Kotlin-мост (`KotlinRegistrationBridge`, `RetryingHttpClient`) и нативный клиент `wamsys`, доступный через `AbstractC45509Jtc` и `JniBridge.jvidispatch*`. Селектор `K49.A0b` возвращает true, если установлен конфиг 24762 или флаг **24763** (found); теги логов заканчиваются на `/kotlin` или `/wamsys`.

Пути обфусцированы XOR 0x12 в `AbstractC45307Jps` и декодируются в (found):

| Путь | Kotlin-функция | Отправляемые поля (помимо полей устройства / e2e) |
|------|-----------------|------------------------------------------|
| `/v2/exist` | `performSameDeviceCheck` / `checkIfExists` | `lg`, `cc`, `in`, `foa_backup_token`, `client_capabilities`, `advertising_id`, `context`, `id`, `backup_token` |
| `/v2/challenge` | `challengeRequest` | challenge при входе; ответ `login`, `challenge`, `retry_after` |
| `/v2/code` | `generateAuthCode` | `token`, `method`, `context`, `advertising_id`, `clicked_education_link`, `manage_call_permission`, `call_log_permission`, `client_start_message` |
| `/v2/register` | `registerPhoneNumber` | `code`, `auth_response` (байты), `method`, `context`, `advertising_id`, плюс записи карты, такие как `security_code`, `reset`, `wipe_token`, `cred_token` |
| `/v2/security` | `verifySecurityCode` | `code`, `reset`, `wipe_token` (устаревший путь, флаг 26215 выключен) |
| `/v2/passkey_auth` | `passkeyAuth` | `lg`, `context`, `credential` (результат assertion) |
| `/v2/device_logout_send`, `/v2/device_logout_fetch` | `sendAccountDefenceDeviceConfirmation`, `fetchAccountDefenceDeviceConfirmation` | `token` |
| `/v2/wfs` | `wfsAuth` | Meta SSO («WFS») auth, ответ `login`, `wa_ac_machine_id`, `lid` |
| `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop` | согласие, логи воронки, silent-верификация, AB-свойства | не относятся к безопасности |

### 3.2 Шаги

| # | Шаг | Подтверждение |
|---|------|----------|
| 1 | `/v2/exist` возвращает состояние аккаунта: какие методы OTP доступны, время ожидания, `second_factor_methods`, `is_device_trusted`, `passkey_auth_challenge`, `password_eligible`, состояние wipe | found (3.3) |
| 2 | Если `passkey_auth_challenge` присутствует и не истёк, предлагается вход по passkey (раздел 7.1) | found |
| 3 | Пользователь выбирает метод; `/v2/code` с `method` | found |
| 4 | Пользователь вводит OTP; `/v2/register` с `code` и `method` | found |
| 5 | `status=ok` завершает регистрацию (из результата читаются `login`, `lid`, `ent_access_token`, `ent_canonical_fbid`). `status=fail` с причиной (3.5) | found |
| 6 | Причина `security_code` означает, что у аккаунта есть второй фактор: `VerifyTwoFactorAuth` собирает PIN, пароль или email OTP и снова вызывает `/v2/register` (3.6) | имя причины found; навигация inferred |
| 7 | После успеха: `RegisterName`, регистрация доверенного устройства (раздел 8), passkey upsell (раздел 7.2) | found |

«Существующий аккаунт» — не отдельный API: сервер отвечает на `/v2/exist` и `/v2/register` для номера, у которого уже есть аккаунт, с тем же словарём status / reason. Поля вроде `possible_migration`, `need_chat_restore_pn_verify`, `acc_tr_eligible` (перенос аккаунта) и `wa_old_eligible` (верификация через старый телефон) показывают, что сервер направляет сценарии существующих аккаунтов через те же два вызова (поля found, значение inferred по именам).

### 3.3 Поля ответа `/v2/exist`, читаемые клиентом

| Поле | Тип | Использование |
|-------|------|-----|
| `status` (`ok`/`fail`), `reason` | string | результат |
| `login`, `lid` | string | идентификаторы аккаунта, возвращаемые клиенту (потребитель не прослежен) |
| `is_device_trusted` | bool | сохраняется как `pref_is_device_trusted`; скрывает чекбокс доверенного устройства |
| `second_factor_methods` | массив строк | сохраняется как `pref_second_factor_methods`; значения — wire-строки `EnumC43759JAu` |
| `passkey_auth_challenge`, `passkey_credential` | string | challenge сохраняется как `reg_passkey_auth_challenge` с отметкой времени; подсказка с id credential |
| `password_eligible` | int | допустимость upsell пароля |
| `sms_wait`, `voice_wait`, `wa_old_wait`, `email_otp_wait`, `send_sms_wait`, `silent_auth_wait`, `retry_after` | string | кулдауны по каналам |
| `sms_length`, `voice_length`, `wa_old_length`, `email_otp_length` | int | ожидаемая длина кода |
| `email_otp_eligible`, `wa_old_eligible`, `silent_auth_eligible`, `carrier_silent_auth_eligible`, `send_sms_eligible`, `acc_tr_eligible` | int | допустимость метода |
| `email`, `wa_old_device_name` | string | замаскированный email / метка старого устройства (маскирование не проверено) |
| `reset_method`, `wipe_type`, `wipe_token`, `wipe_wait`, `wipe_expiry_time`, `server_time` | смешанный | сценарий «забыл PIN» (3.7) |
| `fallback_methods`, `recommended_method`, `num_visible_dbs_methods` | массив / int | порядок элементов UI |
| `ent_access_token`, `ent_canonical_fbid` (в `/v2/register`) | string | учётные данные Meta canonical user |
| `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `version_upgrade`, `custom_block_screen` | смешанный | экраны бана / обновления (см. отчёт о банах) |

### 3.4 Методы OTP

Серверно управляемый лист запроса кода (`RequestServerDrivenOtpCodeBottomSheetFragment`, `C46760Kbq`) предлагает следующие строки `method` (found): `sms`, `voice`, `flash`, `wa_old`, `email_otp`, `password`, `passkey`, `send_sms`. У `silent_auth` и `account transfer` есть собственные поля допустимости.

### 3.5 Причины отказа `/v2/register` (парсер в `KotlinRegistrationBridge`)

| `reason` | Значение (found: имя; значение inferred) |
|----------|-----------------------------------------|
| `incorrect` | неверный код или неверный PIN |
| `security_code` | требуется второй фактор |
| `second_code`, `device_confirm_or_second_code` | требуется второй фактор или подтверждение устройства |
| `too_many_guesses`, `guessed_too_fast` | ограничение частоты попыток; возвращается `guess_wait` |
| `stale`, `mismatch`, `missing`, `format_wrong` | код просрочен / не совпадает / отсутствует / неверного формата |
| `sms_required` | нужно верифицироваться по SMS |
| `blocked`, `not_allowed`, `limited_release` | заблокирован, запрещён, ограничение раскатки |
| `temporarily_unavailable` | временная ошибка |
| `challenge` | требуется раунд challenge (`/v2/challenge`) |
| `reset_too_soon` | сброс PIN запрошен слишком рано |
| `consent`, `consent_parent_linking_already_registered` | экраны согласия |

### 3.6 Методы второго фактора

`EnumC43759JAu` (found): `twofac_pin`, `password`, `email_otp`, `oauth_email`, `sms`, `voice`, `flash`, `wipe_full`, `wipe_offline`. При флаге **28755** экран управляется `second_factor_methods` («динамическая 2FA», строка контекста `twofac_dynamic`), а «подтвердить другим способом» открывает `Dynamic2faMethodSelectionBottomSheet`.

`K49.A0o` (`verifySecurityCode`):

| Условие | Wire |
|-----------|------|
| флаг 26215 выключен | устаревший путь: `/v2/security` с `code` (и `reset`, `wipe_token` при сбросе) |
| флаг 26215 включён, метод не `password` | `/v2/register` с `security_code` = секрет открытым текстом в карте запроса, `method` |
| флаг 26215 включён, метод `password` | пароль сначала шифруется `HOZ.A08` в `#PWD_WA:11:<epoch>:<blob>` (раздел 5.3); blob отправляется в позиции `code` в `/v2/register`; при сбое шифрования QPL сообщает `PASSWORD_ENCRYPT_FAILED` |

Ключ для конверта приходит из `WaPasswordEncryptionKeyQuery` через `CanonicalPasswordService.A04(..., true)` (вызывается из `C47204KjV`, found). Какое именно поле запроса несёт blob на wire, определено по порядку аргументов конструктора, а не по перехваченному запросу (inferred).

### 3.7 Забытый PIN, wipe и сброс по email

`/v2/exist` или `/v2/register` могут вернуть `reset_method`, `wipe_type` (`offline` или `full`), `wipe_wait` (секунды), `wipe_token`, `wipe_expiry_time`, `server_time` (found). `VerifyTwoFactorAuth.A03` отображает их в четыре состояния (found): 0 не разрешено, 1 в кулдауне («0_7 days, offline_info»), 2 `offline` («7_30»), 3 `full` («over 30»). Вызов сброса отправляет `reset=<mode>` и `wipe_token`; `wipe_full` и `wipe_offline` — методы второго фактора (3.6). Что сервер удаляет при `offline` и `full` wipe, неизвестно.

---

## 4. Двухэтапная проверка (PIN) и резервный email

### 4.1 Состояние клиента

`C1DP` (`TwoFactorAuthManager`) хранит PIN локально (found): pref `two_factor_auth_code`, при необходимости зашифрованный (`two_factor_auth_using_encryption`, расшифровывается `C1DP.A01` через хелпер keystore). Используется для периодического напоминания «подтвердите PIN»: интервалы 6 ч, 12 ч, 1 д, 1 д, 3 д, 7 д (`C1DP.A0I`, prefs `two_factor_auth_nag_time`, `two_factor_auth_nag_interval`). Другие prefs: `two_factor_auth_email_set`, `two_factor_auth_dynamic_validated`, `two_factor_auth_last_code_correctness`, `pref_2fa_{sms,voice,flash,email_otp}_wait_time`.

### 4.2 IQ-станзы (`xmlns="urn:xmpp:whatsapp:account"`, таймаут 32 с)

| Действие | Станза | Читаемый ответ | Класс |
|--------|--------|---------------|-------|
| Получить статус (smax 114) | `type=get` `<2fa/>` | `<2fa>`: наличие дочернего `code` означает, что PIN задан; наличие дочернего `email` устанавливает `two_factor_auth_email_set` | `C1DT.A00`, `C28896Cgx` |
| Задать PIN / email | `type=set` `<2fa><code>PIN</code><email>addr</email></2fa>` (каждый дочерний элемент необязателен) | успех записывает prefs; код ошибки + текст передаются слушателям | `C1DP.A07`, `C28899Ch0` |
| Проверить PIN | `type=get` `<2fa><code>PIN</code></2fa>` | `<2fa>` с `code` означает верный PIN | путь `VerifyTwoFactorAuthCodeDialogFragment`, `HandlerC25225AtN` |

PIN состоит из 6 цифр (`SetCodeFragment`, проверка длины `== 6`). Установка — тип 1, подтверждение — тип 2. `Fetch2FAEmailStatusJob` перечитывает статус (32 с), чтобы узнать, подтверждён ли email. Возвращает ли сервер больше дочерних элементов, чем `code` / `email`, неизвестно.

### 4.3 OTP email аккаунта (отдельно от `<2fa><email>`)

`C31107Dfz` строит, `KRB` разбирает (префикс лога `EmailVerificationXmppMethods`):

| Шаг | Станза | Ответ |
|------|--------|----------|
| запрос OTP | `type=set` `<verify_email><lg/><lc/></verify_email>` (язык / локаль, 2-3 символа) | `verify_email.wait_time` |
| проверка OTP | `type=get` `<verify_email><code>NNNNNN</code></verify_email>` (6 символов) | `verify_email.code_match` (`true`/`false`), `wait_time` |

Сам адрес email в этих станзах отсутствует (задаётся раньше, путь не прослежен). Используется `VerifyEmailActivity` и вторым фактором `email_otp`.

### 4.4 PIN против пароля против GetTwofa

`GetTwofaQuery` возвращает `twofa_methods[]{method,value,state}`. `PasswordUpsellEligibility` ищет в этом списке строки `password` и `pin` (found). `SetTwofaMutation` вызывается только после создания пароля, по принципу best effort, с хешированным id устройства (раздел 5.2); `twofa_auto_enabled` / `twofa_auto_disabled` — флаги результата. Сам PIN через w:mex никогда не отправляется.

---

## 5. Пароль аккаунта

### 5.1 Сущности

| Сущность | Роль |
|--------|------|
| `PasswordRepository` | оркестрация: `setPassword`, `getTwofa`, id устройства (`computeDeviceId`) |
| `PasswordServerApiImpl` | `HasPasswordQuery`, `DeletePasswordMutation`, `GetTwofaQuery`, `SetTwofaMutation` |
| `CanonicalPasswordService` | получение ключа, `A03` создание, `A02` смена (мутации `Xfb*`, схема `whatsapp-android-www`) |
| `HOZ` | шифрование конверта (`A08` → `#PWD_WA:11`) |
| `PasswordCredentialManager` | сохраняет credential в Android Credential Manager (`saveCredential`, пропускается без номера E.164) |
| UI | `CreatePasswordActivity`, `ReplacePinWithPasswordActivity`, `PasswordUpgradeFragment`, `SettingsPassword`, `TrustThisDeviceActivity` |

### 5.2 Установка / смена / удаление

`PasswordRepository.setPassword` сначала требует canonical-учётные данные; без них завершается ошибкой «No canonical credentials available to set password» (found). Таким образом, пароль привязан к Meta canonical user, а не только к номеру WhatsApp.

```
setPassword(pw, isChange, enableTwofa)
  isChange  -> CanonicalPasswordService.A02  XfbWaChangePasswordMutation
  !isChange -> CanonicalPasswordService.A03  XfbWaCreatePasswordMutation
               then, if enableTwofa: GetTwofa/SetTwofa best effort (device_id = base64(SHA-256(ANDROID_ID)))
each: A04 = key fetch (WaPasswordEncryptionKeyQuery) + HOZ.A08 -> data.encrypted_password
```

`device_id` — это `K2M.A01(android_id)` = Base64 (флаг 2, без переноса) от SHA-256 от `Settings.Secure.ANDROID_ID` (found). Удаление не отправляет переменных; HTTP-подобный код 409 отображается в результат «заблокировано, нужен email» (found). Локальные правила в `CreatePasswordActivity`: длина от 8 до 20, минимум одна буква и одна цифра, подтверждение должно совпадать (found).

### 5.3 Конверт `#PWD_WA:11` (`HOZ.A02` / `A08`)

```
epoch   = current time in seconds
aesKey  = random 32 B (AES-256)         iv = random 12 B
ct||tag = AES-GCM(aesKey, iv, utf8(secret))    // no AAD on this path
wrapped = RSA/ECB/PKCS1Padding(serverPublicKey, aesKey)
blob    = 0x01 | key_id(1 B) | iv(12) | len(wrapped) as uint16 LE | wrapped | tag(16) | ct
out     = "#PWD_WA:11:" + epoch + ":" + base64(blob, URL_SAFE | NO_WRAP | NO_PADDING)
```

`key_id` должен быть от 1 до 255 (`CanonicalPasswordService.A01`). RSA-ключ разбирается из PEM как X.509 SPKI; путь PKCS1 не проверяет размер модуля (проверка ≥ 4096 бит есть только в `HOZ.A06`, другом варианте OAEP). Один и тот же конверт используется в трёх местах (found): второй фактор при регистрации (3.6), canonical create / change (5.2) и восстановление (`exchangeNonce`, раздел 9, обёрнут в JSON `{version:1,timestamp,password}`).

Другие варианты в `HOZ` (не `#PWD_WA:11`): `A03` и `A06` используют RSA-OAEP-SHA-256 с нулевым IV и AAD (путь Waffle SSO записывает `#PWD_WAFFLE` в `C40069Hd8` / `C40090HdT`).

---

## 6. OPAQUE, VOPRF и нативная криптография

### 6.1 Что присутствует

| Элемент | Где | Уровень |
|------|-------|------|
| `WESOpaqueClientRegistrationStartResult` (.rodata `0xaebae`), `...LoginStartResult` (`0xaebd5`), `...RegistrationFinishResult` (`0xaeda9`), `...LoginFinishResult` (`0xaedd1`), `...RegistrationState` (`0x115042`), `...LoginState` (`0x115072`) | строки `libwhatsapp.so` | found |
| `OPAQUE_PBKDF2_SALT` (`0x17e129`), `VOPRF06-HashToGroup-` (`0x19465a`), `VOPRF06-Finalize-` (`0x19466f`) | строки `libwhatsapp.so` | found |
| `org/whispersystems/curve25519/NativeVOPRFExtension` | та же библиотека; у Java-класса есть `nativeBlind`, `nativeUnBlind`, `nativePcdBlind` | found |
| `libvoprf-ed25519.so`, `libvoprf-ristretto.so` | отдельные библиотеки, экспортируют только `JNI_OnLoad`; Java-обёртки `com.facebook.privacy.acs.VoprfEd25519` / `VoprfRistretto` | found |

### 6.2 Функции, ссылающиеся на строки (arm64, vaddr)

| Функция | Размер | Содержимое | Уровень |
|----------|------|---------|------|
| `fcn.0075a1c0` | 644 B | ссылается на `VOPRF06-HashToGroup-`; mbedTLS SHA-512 init / update ×6 / finish, затем второй проход SHA-512 | found |
| `fcn.0075b550` | 712 B | ссылается на `VOPRF06-Finalize-` и `OPAQUE_PBKDF2_SALT`; SHA-512 по транскрипту finalize, затем `mbedtls_pkcs5_pbkdf2_hmac` | found |
| `fcn.0075a618`, `fcn.0075ad40` | - | обе вызывают `fcn.0075b550`, затем `mbedtls_hkdf_extract` + три `mbedtls_hkdf_expand` (md type `0xb`) | found |
| `fcn.0075a0d4` | - | вызывает `fcn.0075a1c0` | found |

Вызов PBKDF2 в `fcn.0075b550` (дизассемблирование): длина пароля `0x40` (64 B, вывод OPRF), длина соли `0x12` = 18 = длина метки `OPAQUE_PBKDF2_SALT`, причём буфер инициализируется из этой метки, длина выходного ключа `0x40`, число итераций передаётся вызывающим (в этой функции не константа), md type `0xb`. Md type `0xb` соответствует SHA-512 в нумерации mbedTLS 3.6 (inferred по значению enum и 64-байтовым длинам). Итак, вывод OPRF подаётся в PBKDF2-HMAC-SHA-512 с ASCII-меткой в качестве соли (found для формы вызова, inferred для хеша).

Роли функций (blind, finalize, registration-finish, login-finish) выведены по форме вызовов (inferred). Группа / ciphersuite (кривая, id, добавляемый к префиксам `VOPRF06-`), раскладки байтов KE1 / KE2 / KE3, содержимое конверта и вариант AKE — **unknown**; нативный код читался как дизассемблирование указанных функций, а не как декомпиляция.

### 6.3 Кто его вызывает: зашифрованный бэкап, а не пароль аккаунта

Java-вход для конечного автомата — протокол зашифрованного бэкапа (префикс лога `encb/`):

| Класс | Роль (found) |
|-------|--------------|
| `EncBackupViewModel` | создаёт `C61447Rhg` (обработчик входа) со строкой пароля бэкапа пользователя |
| `AbstractC62498S8e` | отправляет IQ `sendInitRegIq`, `sendBeginRegIq`, `sendFinishRegIq`, `sendInitLoginIq`, `finishLoginOnSuccess`, `sendDeleteAccountIq` (`EncryptedBackupProtocolHelper`) |
| `C62510S8q` (smali `X/S8q`) | обработчик ответов; `jvidispatchOOO(0xb, password, ...)` возвращает состояние входа (`Rtz`), `jvidispatchOO(0x20, state)` — следующее сообщение |
| `C62511S8r` | ответ begin-login: проверяет `l2` по `l2_sig` и `ed_pub` (Ed25519), читает `count`, `backoff`, `max_attempts`, затем `jvidispatchOIOOO(1, 100000L, state, ...)` |
| `RunnableC29321Co8` | finish-login: `jvidispatchOIOO(1, 100000L, state, ...)`, читает поля модели, расшифровывает ключ бэкапа через AES-GCM, строит proto `C25803BBm` (`backupKeyData_`, `r3_`, `opaqueChallenge_`, `transcript_`) |

`100000` передаётся в нативные finish-вызовы и при регистрации, и при входе (found). Это вероятное число итераций PBKDF2 (inferred: нативная функция принимает его как параметр). То, что эти индексы `jvidispatch` попадают в код `WESOpaque*`, выведено по аргументам (строка пароля на входе, объекты состояния между вызовами, поля `l2` / `r3`) и по отсутствию других потребителей (inferred); ни одно Java-имя не упоминает OPAQUE. Код пароля аккаунта (раздел 5) к ним никогда не обращается.

### 6.4 Другой VOPRF: токены Meta ACS

У `NativeVOPRFExtension` и `libvoprf-ed25519.so` есть Java-потребители `C1N9` (`ACSTokenProviderImpl`, префикс лога `ACSToken/`) и `KYL`: blinding factor, подписанный blinded-токен, DLEQ-доказательство, unblind, shared secret (found строки `blinding_factor_string`, `shared_secret_string`, `ACSToken/processSignedBlindedToken`). Соответствующие операции в ассетах — `WaAcsGetConfig` (`27388182297440754`) и `WaAcsIssueCredentials` (`26645395115100537`); ни одно имя не встречается в коде, поэтому транспорт запроса токена не прослежен. Это токен анонимных credentials, а не вход по паролю.

### 6.5 Что это значит для «входа по паролю»

| Утверждение | Статус в 2.26.41.6 |
|-------|---------------------|
| Вход по паролю аккаунта использует OPAQUE | кодом не подтверждается: пароль отправляется как RSA/AES-конверт (`#PWD_WA:11`), в прочитанных путях ни одно сообщение OPAQUE не строится; у `SetPasswordMutation` и `CheckPasswordMutation` нет места вызова |
| Нативный клиент OPAQUE существует | found |
| Он обслуживает пароль зашифрованного бэкапа | found (Java-вызывающий), привязка к нативным символам inferred |
| Сервер хранит verifier вместо пароля для пароля аккаунта | unknown |

Java-строки, похожие на свидетельство OPAQUE, но не связанные с ним (found): `opaqueChallenge_` (proto начальной загрузки бэкапа выше), `opaquePayload_` (`C61318RfY`, фрейм tethered-миграции), `OpaqueConfig` / `prefersOpaqueConfig` (битовая карта конфигурации в `EnumC167127Ba`), `OpaqueKey(` (`C44715Jfl`, строковая обёртка), `KE1` (`X.KE1` — класс Android Compose), `opaque_client_data` (столбец history-sync).

---

## 7. Passkey (WebAuthn)

### 7.1 Вход во время регистрации

| Шаг | Подтверждение |
|------|----------|
| `/v2/exist` возвращает `passkey_auth_challenge`; `K15.A03` принимает его, пока он моложе `SignalCredentialStateController.MAX_RETRY_TIME` | found |
| `PasskeyVerifier.onPasskeyChallengeReceived` выполняет assertion discoverable credential через `androidx.credentials` (`PasskeyLowLevelAndroidApiImpl.loginWithPasskey`); стадия хранится в pref `passkey_login_stage` | found |
| `K49.A0l` отправляет результат как `credential` в `/v2/passkey_auth` | found |
| Ответ: `status` (`ok`/`fail`), `reason` (`temporarily_unavailable`, `disabled`), `credential_create` (string), `login`, `cred_token` | found |
| `cred_token` сохраняется для каждого номера телефона в `passkey_disabled_cred_token_map` и отправляется обратно как `cred_token` в последующих запросах при включённом флаге **25565** | found; назначение (доказать, что passkey был отключён) inferred |

Клиентские исходы логируются как `passkey_client_login_{cancelled,nopasskey,ineligible,error,success}`. `prepareGetCredential` используется только на Android 14+ (SDK 34) и при флаге **21638** (found).

### 7.2 Создание и управление

Upsell после шага 2FA: `VerifyTwoFactorAuth.onCheckPasskeyUpsellAfter2FA` использует `PasskeyCreateEducationScreen` или bottom sheet; флаг **20409** переключает между контрольным сценарием и путём quick-promotion (QP), флаг **16591** добавляет проверку допустимости (found).

| Операция | Гейт MEX | Резерв IQ (`xmlns="passkey"`) |
|-----------|----------|---------------------------------|
| start register | флаг **10453** | smax 125, `type=get` |
| finish register | флаг **10452** | smax 126, `type=set` |
| clear | флаг **10461** | smax 129, `type=set` |
| list / exists, delete, enable, update encryption status | всегда MEX | нет |

`credential_create` из start-register кэшируется в `passkey_create_challenge`. Finish register отправляет `credential` и `key_attestation`; payload attestation строится только при включённом флаге **28809** (base64 key attestation, `getKeyAttestationPayload`). Флаг **8877** оборачивает start / finish в хелпер retry / timeout (`C29707Cw7`, роль inferred). `PasskeyRandomizedDailyCronJob` и `PasskeyExistsCache` обновляют список exists; ответ exists сохраняет `uuid` в `reg_passkey_exists_uuid`.

### 7.3 PRF и клиентское шифрование

`PasskeyPrfSecrets` использует статический вход PRF `WhatsAppPasskeyStaticPrfInputV1` и хранит корневой ключ, выведенный через PRF, в `prf_derived_root_key.key` (метка ключа инкапсуляции `prf_derived_root_key_file_encapsulation_key`). `RegistrationPasskeyUpdateClientEncryptionStatusMutation` сообщает серверу, что passkey используется для клиентского шифрования. Потребитель — сценарий зашифрованного бэкапа (`VerifyPasskeyFragment`, inferred по расположению класса).

---

## 8. Доверенные устройства

| Элемент | Значение |
|------|-------|
| `device_id` | `Base64(SHA-256(ANDROID_ID))` (без переноса), `K2M.A01` |
| `device_name` | `<MANUFACTURER>-<MODEL>` (`HO4.A00`) |
| Чекбокс | показывается на `VerifyPhoneNumber` и `VerifyTwoFactorAuth`, когда флаг **30530** включён и `pref_is_device_trusted` равен false; prefs `pref_trusted_device_checkbox_shown` / `_checked` |
| Завершение регистрации (`RegisterName`) | согласился: `AddTrustedDeviceMutation`; не согласился: `UntrustTrustedDeviceMutation` с `reason="REREG"` (`C29652Cu9`, found) |
| Настройки | `TrustedDevicesRepository` выводит список (`GetTrustedDevicesQuery`) и удаляет (`DeleteTrustedDeviceMutation`); `TrustThisDeviceActivity` |
| Эффект | `is_device_trusted` возвращается `/v2/exist`, `/v2/register`, `GetTwofa` и `SetTwofa`; клиент использует его, чтобы пропустить чекбокс. То, что доверенное устройство пропускает запрос PIN / пароля, — inferred; клиентский код второй фактор не пропускает |

Записи `list_of_trusted_device[]` содержат `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` (местоположение последнего использования предоставляет сервер; как оно определяется, неизвестно).

---

## 9. Восстановление аккаунта (Meta canonical user)

`AccountRecoveryManager` не восстанавливает чаты WhatsApp или аккаунт по номеру телефона. Он заново создаёт учётные данные Meta canonical user для аккаунта, связанного с FB (found).

| Шаг | Подробности |
|------|--------|
| Триггер | `maybeRecoverAccount`: нет canonical user или учётные данные недействительны; отложенный вариант под флагом **16017** |
| Ключ клиента | генерирует пару ключей, отправляет публичный ключ (PEM, base64) как `nonce_encryption_key` в `WWWTriggerAcountRecovery` с `use_case`, `registration_trace_id`, `request_id` |
| Nonce | приходит уведомлением; таймаут даёт «Account Recovery Failed due to Nonce notification timeout» |
| Обмен | `WWWExchangeNonceForAccessToken` с `nonce`, `use_case`, `request_id`, `registration_trace_id`, `encrypted_password` = конверт `#PWD_WA:11` случайного клиентского секрета внутри JSON `{version:1,timestamp,password}` |
| Companion | `WWWGetNonceForCompanionDevice`, `WWWTradeNonceForAccessTokens` делают то же для связанных устройств (`CompanionCanonicalUserNonceManager`, `CompanionCanonicalUserAccessTokenJob`) |
| Связанное | `WWWValidateCanonicalUser`, `WWWCanonicalUserValid`, `WWWAppGenerateCanonicalNonce` (места вызова есть; поля не читаются) |

Написание `Acount` — собственное написание WhatsApp. Какой алгоритм у ключа шифрования nonce (пара приходит из `N6T.A02`), не выяснено.

---

## 10. Вход и выход

`LogoutManager` реализует soft logout (мультиаккаунт) и путь login-back (found).

| Действие | Wire | Примечания |
|--------|------|-------|
| Logout | `AccountLogoutMutation` `{phone_number, enabled_biometric}` | `enabled_biometric` из биометрической настройки; таймаут 5 с, затем выход продолжается локально («timed out, proceeding with logout») |
| Push | `LogoutPushManager` отключает / повторно включает GCM push (`"re-enable"` при откате) | found |
| Локально | `markCurrentAccountLoggedOut`, `removeLoggedOutAccountWithCleanup`, `deleteGmsBackupState`, необязательный UI удаления чатов (`DeleteChatsOnLogoutDialog`, `LoggedOutChatsFragmentDialog`) | found |
| Login back | `AccountLoginMutation` `{phone_number}`, затем `loginBack` → `actionReconnect`; ожидание соединения до 7 с | `PrimaryLoginBackActivity` |

Это флаг состояния на серверной стороне мультиаккаунтной конфигурации, а не вход по номеру телефона из раздела 3 и не удаление связанного устройства. Флаг **28385** читается в `LogoutManager` (роль не выяснена).

---

## 11. Feature-флаги

ID выделены жирным. Типы: B = boolean AB prop, C = config. Имён в клиенте нет; роль — это то, что код делает с флагом.

| ID | Где | Что контролирует |
|----|-------|----------|
| **24762** (C) / **24763** (B) | `K49.A0b` | Kotlin-стек регистрации вместо нативного `wamsys` |
| **26215** | `K49` verify / reset security code | второй фактор регистрации через `/v2/register`, включает конверт пароля; выкл. = устаревший `/v2/security` |
| **25565** | `K49.A0M` | отправка сохранённого `cred_token` |
| **28755** | `VerifyTwoFactorAuth` | динамический выбор метода 2FA из `second_factor_methods` |
| **30530** | `VerifyPhoneNumber`, `VerifyTwoFactorAuth` | чекбокс доверенного устройства |
| **20409** | `VerifyTwoFactorAuth` | passkey upsell через QP после 2FA против контроля |
| **16591** | `VerifyTwoFactorAuth` | проверка допустимости passkey перед upsell |
| **21638** | `PasskeyAndroidApi` | `prepareGetCredential` (Android 14+) |
| **10452** / **10453** / **10461** | `PasskeyServerApiImpl` | MEX вместо IQ для finish / start / clear |
| **28809** | `PasskeyServerApiImpl` | payload key attestation |
| **8877**, **31281** | `PasskeyCreateFlow` | обёртка retry; альтернативный путь passkey для платежей (роли inferred) |
| **5156** | `SetCodeFragment` | предложить «добавить email» после установки PIN |
| **5711** | `TwoFactorAuthActivity`, `SetCodeFragment` | только раскладка (скрывает индикатор страниц) |
| **16017** | `AccountRecoveryManager` | отложенная обработка nonce |
| **28385** | `LogoutManager` | не выяснено |

---

## 12. Случаи ошибок

| Симптом | Причина | Исправление / примечание |
|---------|-------|------------|
| `/v2/register` с причиной `security_code` или `second_code` | у аккаунта есть второй фактор | отправить PIN / пароль / email OTP через `/v2/register` (3.6) |
| `PASSWORD_ENCRYPT_FAILED` (QPL) | сбой получения ключа, `key_id` вне 1-255 или исключение криптографии (логи `encryptRegistrationPassword/*`) | повторить; клиент прерывает попытку |
| `reset_too_soon` | сброс забытого PIN до истечения `wipe_wait` | подождать; состояние UI 1 |
| `too_many_guesses` / `guessed_too_fast` | лимит попыток PIN или OTP | подождать `guess_wait` |
| `No canonical credentials available to set password` | на устройстве нет Meta canonical user | сначала завершить настройку canonical user |
| Не удалось создать / сменить пароль | payload `xfb_wa_*` неуспешен; код ошибки отображается `CanonicalPasswordService.A00` | enum ошибок UI `EnumC49982M3j` |
| `DeletePassword` 409 | перед удалением нужен email аккаунта | сначала добавить email |
| `Account Recovery Failed due to Nonce notification timeout` | уведомление не получено | повторить триггер |
| `...passwordPublicKeyStr is null` / `passwordKeyIdStr is null` | сертификат шифрования отсутствует при обмене восстановления | повторить |
| `LogoutManager/callLogoutApi/timed out` | нет ответа за 5 с | выход продолжается локально |
| Passkey: `NoCredentialException`, `NotAllowedError`, слишком старый GMS, отсутствуют сервисы Play | сбои Credential Manager | переход к другим методам |

---

## 13. Ключевые различия

| A | B |
|---|---|
| Нативный код OPAQUE (пароль зашифрованного бэкапа, IQ `encb/*` с HSM) | пароль аккаунта (`XfbWa*` + `#PWD_WA:11`) |
| `libvoprf-*.so` + `NativeVOPRFExtension` (анонимные токены ACS) | конечный автомат OPAQUE (`WESOpaque*`) |
| PIN (IQ `<2fa>`, 6 цифр) | пароль (w:mex, 8-20 символов) |
| `<2fa><email>` (резервный email для сброса PIN) | сценарий OTP `<verify_email>` и второй фактор `email_otp` |
| `SetTwofaMutation` (флаг для каждого id устройства после пароля) | IQ установки PIN |
| Доверенное устройство (вход, `AddTrustedDeviceMutation`) | `WhatsappTrustedDeviceRegistration` (trust binding платежей) |
| `AccountLogoutMutation` (soft logout) | отвязка companion (`remove-companion-device`) и выход при бане |
| `WWWTriggerAcountRecovery` (учётные данные canonical user) | wipe забытого PIN (`wipe_*`, `/v2/security`) |
| `#PWD_WA:11` (WhatsApp) | `#PWD_WAFFLE` (Waffle SSO) |
| операции `PasskeyServerApiImpl` (passkey аккаунта) | `PaymentsPasskey*`, `BrPasskey*` |
| `/v2/passkey_auth` (assertion при входе) | `PasskeyRequestChallengeMutation` / `PasskeyVerifyChallengeMutation` (нет места вызова) |

---

## 14. Baileys (`baron-baileys-v2`)

Сравнение с `src/Socket/privacy.js` и `src/Socket/registration.js`.

| Элемент | APK 2.26.41.6 | Baileys | Результат |
|------|---------------|---------|--------|
| doc_id для доверенных устройств, входа, выхода, паролей, passkey | ассеты | те же номера | совпадает |
| `accountLogin` / `accountLogout` | `input{phone_number}` / `input{phone_number, enabled_biometric}` | то же | совпадает |
| `getTrustedDevices` | `input{device_id}` отправляется всегда | `{}` | отличается; поведение сервера без `device_id` неизвестно |
| причина `untrustTrustedDevice` по умолчанию | `"REREG"` в единственном вызове | `'USER_INITIATED'` | отличается, другие причины неизвестны |
| операции passkey | переменные `credential`, `key_attestation`, `credential_ids`; корни `xwa2_passkey_*` | не реализованы в прочитанных файлах | использовать формы из APK |
| `SetPassword` / `CheckPassword` | нет места вызова | только doc_id | не проверено, не полагаться |
| шифрование `#PWD_WA:11` | раздел 5.3 | отсутствует в прочитанном дереве `src` | реализовать по разделу 5.3 |

Почему самостоятельный клиент не работает на этих путях (inferred, ничего не тестировалось): регистрационные эндпоинты ожидают защищённые e2e поля запроса, которые строит приложение (`C45446JsB`); вызовы пароля и восстановления требуют учётных данных canonical user; passkey-assertion требует платформенного аутентификатора.

---

## 15. Полные сценарии

### 15.1 Верификация номера, у которого уже есть аккаунт

```
[User]            [Client]                                   [Server]
  │ enter number    │                                           │
  ▼                 ▼                                           │
            POST /v2/exist ───────────────────────────────────►│
                    │◄── methods, waits, second_factor_methods, │
                    │    passkey_auth_challenge, is_device_trusted
  passkey? ─yes──►  Credential Manager assertion                │
                    POST /v2/passkey_auth {credential} ────────►│
                    │◄── status, login, cred_token              │
  no                ▼                                           │
            POST /v2/code {method} ─────────────────────────────►│  OTP sent (sms/voice/flash/wa_old/email_otp)
  type OTP ──►  POST /v2/register {code, method} ───────────────►│
                    │◄── ok | fail(reason)                      │
   reason=security_code / second_code                           │
  PIN / password ─► POST /v2/register {security_code | #PWD_WA blob, method}
                    │◄── ok (login, lid, ent_access_token)      │
                    ▼                                           │
        optional: AddTrustedDeviceMutation | UntrustTrustedDeviceMutation(REREG)
        optional: passkey upsell -> StartRegister -> Credential Manager -> FinishRegister
  forgot PIN ─────► reset=<mode>, wipe_token (after wipe_wait) ─►│
```

### 15.2 Установка PIN и резервного email

```
[Client]  IQ get <2fa/> ───────────────► [Server]  <2fa>[<code/>][<email/>]
[Client]  IQ set <2fa><code>NNNNNN</code><email>x</email></2fa> ──► ok | error(code,text)
[Client]  Fetch2FAEmailStatusJob: IQ get <2fa/> until <email> present
[Client]  IQ get <2fa><code>NNNNNN</code></2fa> ──► <2fa><code/></2fa> = correct   (periodic reminder)
```

### 15.3 Создание пароля аккаунта

```
[Client]  canonical credentials present? ── no ─► fail
[Client]  WaPasswordEncryptionKeyQuery ──► public_key (PEM), key_id (1..255)
[Client]  HOZ.A08: AES-GCM + RSA-PKCS1 wrap -> "#PWD_WA:11:<epoch>:<blob>"
[Client]  XfbWaCreatePasswordMutation {data:{encrypted_password}} ──► success
[Client]  (best effort) GetTwofaQuery / SetTwofaMutation {input:{twofa_enabled:true, device_id}}
```

---

## 16. Неизвестное

| Тема | Причина |
|-------|--------|
| Ciphersuite OPAQUE (группа, id после `VOPRF06-`), раскладки KE1 / KE2 / KE3 и конверта, вариант AKE | нативный код, прочитано только дизассемблирование 4 функций |
| Привязка индексов `jvidispatch` зашифрованного бэкапа к коду `WESOpaque*` | по форме аргументов, а не по символу |
| Число итераций PBKDF2 для KSF OPAQUE | передаётся параметром; `100000` — литерал, который передают Java-вызывающие |
| Отправляет ли какой-либо путь пароль аккаунта через OPAQUE | такой путь не найден; обёртки за числовой диспетчеризацией исключить нельзя |
| Ответы `XfbWa*`, `AccountLogin`, `AccountLogout`, `UntrustTrustedDevice` | корень и поля не прочитаны |
| Операции без места вызова (2.4) | переменные и ответы неизвестны |
| Точное поле, несущее blob `#PWD_WA` в `/v2/register` | выведено из порядка аргументов конструктора |
| Значение полей `login`, `lid`, возвращаемых `/v2/exist` и `/v2/passkey_auth` | потребители не прослежены |
| Эффект `wipe_full` / `wipe_offline` на сервере | клиент показывает только текст |
| Пропускает ли доверенное устройство второй фактор | на стороне сервера; клиентской логики пропуска нет |
| Алгоритм пары ключей восстановления (`N6T.A02`) | не прочитан |
| Роли флагов 8877, 31281, 28385 | только гейты |
| Фактический трафик | только статический анализ |
