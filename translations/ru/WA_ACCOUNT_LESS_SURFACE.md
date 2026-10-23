<!-- src-sha1: 166366154a0dd7893ab70aa91166a96d5a2e788f -->
# WhatsApp Поверхность без аккаунта — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** что Android-клиент предоставляет без зарегистрированного аккаунта или до завершения регистрации — экспорты манифеста (activities, aliases, services, receivers, providers), экраны до регистрации и маршрутизация по состоянию регистрации, deep links и веб-ссылки, HTTP- и Graph-эндпоинты без аутентификации, вшитая таблица хостов, форма обращения в поддержку без входа в аккаунт, статус бана и точки входа апелляции, идентификаторы, отправляемые до входа, IPC-поверхности для сторонних приложений, что остаётся неизвестным

---

## 1. Что означает "без аккаунта" в этой сборке

Единого "режима без входа" нет. Несколько независимых путей работают, пока у клиента нет user JID, нет аутентифицированной чат-сессии или регистрация не завершена. Каждый путь подставляет вместо аккаунта свой credential. Все утверждения основаны на статическом анализе декомпилированного APK (`versionCode 264100600`, target SDK 36, min SDK 23). Ничего не наблюдалось в трафике. Уровни: **found** = прочитано в коде или манифесте, **inferred** = выведено из кода, **unknown** = статически не определяется. Защитная документация: поверхности и средства контроля описываются, но не эксплуатируются.

Обфусцированные имена индивидуальны для каждой сборки и заново определены по стабильным строкам в 2.26.41.6.

| Путь | Credential, заменяющий аккаунт | Транспорт | Основные классы (2.26.41.6) |
|------|--------------------------------------|-----------|--------------------------|
| Регистрация по номеру телефона | нет до `/v2/register`; запрос содержит набор статических ключей Noise и идентификаторы устройства | HTTPS `/v2/*` | `K49`, `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Лог воронки до ввода номера | только phone id (`fdid`) | HTTPS `/v2/pre_pn_client_log` | `PrePnBaseFunnelLogger`, `K49` |
| AB props до чата | prefs `ab_key` / `ab_hash` | HTTPS `/v2/reg_onboard_abprop` | `K49.checkPreChatdABProps` |
| Статус бана / апелляция | непрозрачный токен, сохранённый в момент бана, + вшитый client token приложения | HTTPS Graph `graph.<domain>/graphql` | `AbstractC40195HfH`, `C37409GLo`, `C37604GYf`, `C37414GLt` |
| Форма поддержки без входа | нет; email + свободный текст + `anid` | HTTPS multipart POST | `LoggedOutContactFormActivity`, `C47328KmN` |
| Выгрузка crash-логов / логов | вшитый токен приложения | HTTPS `crashlogs.whatsapp.net` | `C10V`, `C05640An` |
| Статические ресурсы | нет | HTTPS GET | `static.whatsapp.net/*` |
| Graph с анонимными credentials (ACS / OHAI) | ACS-токен или конфигурация ключа OHAI, без JID | HTTPS `acs.whatsapp.com/graphql` | `C31991Nz`, `R5t`, `N5I` |
| Регистрация companion | нет; Noise-подключение с null-JID допускается только здесь | Noise | `HandlerThreadC12340b0` |
| Встроенный DNS fallback | нет | вшитая таблица | `AbstractC47101wK`, `C36881dC` |

Не рассматривается здесь, см. связанные отчёты: шаги регистрации, методы OTP и причины сбоев ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) раздел 3); токены аттестации, отправляемые при регистрации ([WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)); конечный автомат бана и шифрование апелляции ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) разделы 2, 10); вход через Noise и регистрация companion ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)); телеметрия WAM ([WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)).

---

## 2. Манифест: экспортируемые компоненты

### 2.1 Количества (found, `AndroidManifest.xml`, разбор внутри `<application>`)

| Тип | Объявлено | Экспортировано (явное `true`; неявное значение по умолчанию не использовалось) |
|------|---------:|----------------------------------------------------------------:|
| `activity` | 828 | 22 |
| `activity-alias` | 33 | 29 (14 — отключённые алиасы лаунчера `AppIcon01..14`) |
| `service` | 61 | 16 |
| `receiver` | 68 | 19 |
| `provider` | 19 | 11 |
| Итого | 1009 | 97 |

Из 97 экспортируемых записей: 20 имеют `enabled="false"` (14 алиасов иконок, сервис car-app, ADM receiver, activity и provider миграции с iOS, два India UPI intent receivers); 24 имеют `permission` / `readPermission`; 6 защищены определённым WhatsApp разрешением уровня `signature`; 56 включены и не имеют разрешения в манифесте. Любые проверки сверх манифеста находятся в коде (раздел 9).

Пользовательские разрешения (found): `REGISTRATION`, `IDENTITY_VERIFICATION`, `MIGRATION_CONTENT_PROVIDER`, `BROADCAST`, `MAPS_RECEIVE`, `RECEIVE_ADM_MESSAGE`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` имеют `protectionLevel="signature"`. У `com.whatsapp.sticker.READ` нет `protectionLevel` (по умолчанию normal).

### 2.2 Точки входа, работающие без аккаунта

| Компонент | Экспортирован | Фильтр | Почему доступен до регистрации |
|-----------|----------|--------|--------------------------------------|
| `com.whatsapp.Main` | да | `MAIN` / `LAUNCHER`, `MULTIWINDOW_LAUNCHER` | единственный лаунчер; маршрутизирует по состоянию регистрации (раздел 3) |
| `com.whatsapp.home.ui.HomeActivity` + алиасы `AcceptInviteLinkActivityDeepLink`, `EventDeepLink`, `HomeActivity` | да | `chat.whatsapp.com`, `call.whatsapp.com`, `event.whatsapp.com`, `whatsapp://chat`, `call`, `event`, NFC `application/com.whatsapp.chat`, `.join` | в самом `HomeActivity` проверка регистрации не найдена (inferred: перенаправляет базовый класс, не разрешён) |
| `DeepLinkActivity` через 4 алиаса | алиас да, цель нет | см. раздел 4 | точка входа для ссылок |
| `com.whatsapp.deeplink.ui.TpalOAuthRedirectActivity` | да | `www.whatsapp.com/oauth_account_linking/login_redirect`, `/oauth_account_linking_mobile/login_redirect`, `whatsapp://third_party_oauth` | приёмник OAuth-редиректа, `noHistory` |
| `com.whatsapp.cuif.ConsentActivity` | да | `whatsapp://consent` | читает extras `flow_name`, `source`, `extra_params`, `device_id`, `app_id`; поведение до регистрации не определено |
| `com.whatsapp.Conversation` | да | `sms:` / `smsto:` `VIEW` / `SENDTO` | точка входа системного обработчика SMS |
| `com.whatsapp.accountsync.ProfileActivity`, `CallContactLandingActivity` | да | `content://com.android.contacts` MIME `vnd.com.whatsapp.profile`, `.voip.call`, `.video.call` | интеграция с приложением контактов; `CallContactLandingActivity` требует `CALL_PHONE` |
| `com.whatsapp.registration.ui.RegistrationCompletedReceiver` | да, signature `REGISTRATION` | `com.whatsapp.SMBRegistrationCompleted` | сигнал от родственного приложения |
| `com.whatsapp.registration.directmigration.MigrationProviderOrderedBroadcastReceiver`, `MigrationRequesterBroadcastReceiver` | да, signature `REGISTRATION` | actions `initialMigrationInfoAction`, `recoveryTokenAction`, `setMigrationStateOnProviderSide`, `providerIsLoggedOutAction`, `providerAppMigrationSpaceNeededAction` | миграция между consumer- и SMB-приложениями во время регистрации |
| `MigrationContentProvider`, `DirectMigrationContentProvider` | да, `readPermission` `MIGRATION_CONTENT_PROVIDER` (signature) | authorities `com.whatsapp.provider.MigrationContentProvider`, `.DirectMigrationContentProvider` | та же миграция |
| `com.whatsapp.registration.app.verifyphone.SMSRetrieverAppInactiveReceiver` | да, разрешение GMS `SEND` | `SMS_RETRIEVED` | результат SMS Retriever, когда приложение неактивно |
| `com.whatsapp.registration.core.accounttransfer.AccountTransferReceiver` | да, без разрешения | `com.google.android.gms.auth.START_ACCOUNT_EXPORT` | перед действием код требует защищённый keyguard и проверку feature (found) |
| `com.whatsapp.phoneid.PhoneIdRequestReceiver` | да, без разрешения | `com.facebook.GET_PHONE_ID` | возвращает phone id доверенному вызывающему (раздел 9.1) |
| `com.whatsapp.otpmessage.otp.OtpRequestedReceiver`, `OtpIdentityHashRequestedReceiver` | да, без разрешения | `com.whatsapp.otp.OTP_REQUESTED`, `ID_HASH_REQUESTED` | handshake автозаполнения OTP для других приложений (раздел 9.3) |

### 2.3 Прочие экспортируемые записи (не связаны с регистрацией, перечислены для полноты)

| Группа | Компоненты | Gate |
|-------|------------|------|
| Контент третьих сторон | `Conversation` (обработчик `sms:`), `ExternalShareAlias` (`SEND`, `SEND_MULTIPLE`, `*/*`), `ContactPicker` (`PICK`, `CREATE_SHORTCUT`), `SetAsProfilePhoto` (`ATTACH_DATA`) | нет в манифесте |
| Стикеры | `SendStickerCommandActivity`, `AddThirdPartyStickerPackActivity` (+ алиас), `StickerCommandProvider`, `WhitelistPackQueryContentProvider` | нет в манифесте |
| IPC семейства Meta | `FamilyAppsCredentialsProvider`, `FamilyAppsUserValuesProvider`, `WaAccountsCenterService` (`com.whatsapp.wfl.OPERATION`), `QuickSendsContactsProvider`, `OrbitSsoProvider`, `OrbitMessagesProvider`, `OrbitCompanionLinkActivity`, `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | проверки вызывающего в коде (раздел 9) |
| Устройства-компаньоны | `WearOsListenerService`, `GarminBindingServiceShim`, `IQGarminBindingService`, `TetheredService`, `WhatsAppCarAppService` (отключён) | нет в манифесте |
| Интеграция с Google | `BackupNowService`, `BackupStateService`, `OsMigrationAppDataService` (`BACKUP`), `DeferredRestoreBroadcastReceiver` (`BACKUP`), `WakeUpService` (разрешение exposure notification) | частично |

Также экспортируются: хуки настроек (`SettingsNotifications`, `SettingsDataUsageActivity`, настройка виджета `AppAuthenticationActivity`), приземление звонков (`SystemDialerCallLandingActivity`, `VoiceMessagingActivity`), receivers библиотек (`WidgetProvider`, `BootReceiver`, `AppUpdatedReceiver`, `ExternalMediaStateReceiver`, `WAFbnsPreloadReceiver`, `FirebaseInstanceIdReceiver`, записи work-manager и profile-install за `BIND_JOB_SERVICE` / `DUMP`), записи Pixel (`com.google.permission.besties.API`), а также отключённые записи India UPI и миграции с iOS. `IdentityVerificationActivity` (NFC `application/com.whatsapp.identity.ui`) требует signature-разрешение `IDENTITY_VERIFICATION`.

### 2.4 Неэкспортируемые компоненты до регистрации (found)

806 неэкспортируемых activities включают все экраны регистрации (раздел 3.2), `LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity`, `BanAppealActivity`, `WfacBanActivity`, `PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`. Три неэкспортируемых alarm receivers управляют напоминаниями о регистрации: `RegRetryVerificationReceiver` (`com.whatsapp.alarm.REGISTRATION_RETRY`, `SMS_RECEIVED_WHILE_INACTIVE`), `OnboardingIncompleteReceiver` (`ONBOARDING_INCOMPLETE`), `EnterPhoneNumberNotificationReceiver` (`ENTER_PHONE_NUMBER`). Неэкспортируемые providers: `FileProvider`, `SecureFileProvider`, `MediaProvider`, `AccountSwitchingContentProvider`, `RestartAppContentProvider`, `InstrumentationProvider` (все с `grantUriPermissions`, где объявлено).

### 2.5 Флаги приложения и сетевая политика (found)

| Параметр | Значение |
|------|-------|
| `debuggable` | `false` |
| `allowBackup` | `true`, но `fullBackupContent` и `dataExtractionRules` (cloud-backup и device-transfer) исключают все домены; запись кроссплатформенного переноса для iOS содержит только `bundleId` / `teamId` |
| `networkSecurityConfig` base | `cleartextTrafficPermitted="true"`; trust anchors `system` и `user` (`overridePins="true"` для пользовательских CA) |
| Cleartext запрещён | `whatsapp.com`, `whatsapp.net`, `wa.me`, `wl.co` (22 пина SHA-256, без срока действия), `facebook.com`, `instagram.com`, `jiomart.com`, `hatch-api.meta.ai` |
| Область пинов | набор пинов находится в domain-config для `whatsapp.com` / `whatsapp.net` / `wa.me` / `wl.co`; он наследует базовые trust anchors, поэтому пины не применяются к пользовательским CA (поведение платформы для `overridePins`) |
| Хосты вне любого domain-config | `gstatic.com` (ключ reCAPTCHA) подпадает под базовую конфигурацию (cleartext разрешён; код использует `https://`) |

---

## 3. Экраны до регистрации и маршрутизация по состоянию

### 3.1 Маршрутизация `Main` по состоянию регистрации (found, smali `Main.A5W`)

`Main` читает состояние регистрации (`C0Gk.A02()`) и сохранённый объект собственного аккаунта. Теги логов — стабильные якоря.

| Состояние | Тег лога | Назначение |
|------:|---------|-------------|
| 2 | `main/me/regname`, `main/no-me/regname` | шаг регистрации с вводом имени (`RegisterName`) |
| 21 | `main/me/wfac ban` | экран WFAC-бана через `HBC.A00` (`WfacBanActivity`) |
| 24, 38 | `main/me/backup otp` | шаг backup OTP / верификации |
| 41 | `main/me/consent age ban` | экран согласия по возрасту |
| 45 | `main/me/paa onboarding`, `main/no-me/paa onboarding` | онбординг зависимого / управляемого аккаунта |
| 50 | `main/me/logged out, going to PrimaryLoginBackActivity` | экран возврата входа |
| 51 | `main/me/pending login-back verification` | верификация возврата входа (extra `login_back_verification`) |
| 56 | `main/me/username`, `main/no-me/username` | шаг имени пользователя |
| any | `main/no-me/first-factor password` | ветка пароля первого фактора (нет объекта собственного аккаунта) |
| any | `main/invalid/registration state=` | лог недопустимого состояния |

Тот же метод строит intents (found) для `VerifyPhoneNumber`, `DeviceConfirmationRegistrationActivity`, `ExportMigrationDataExportedActivity`, `BanAppealActivity` (extra `launch_source`), `DeleteAccountConfirmation` и входа `RegisterPhone` по умолчанию. Preference `logged_out_phone_fallback_pending` возобновляет работу на `RegisterPhone` (`main/me/logged-out phone fallback resume`). Выпущенный IDV-токен (`minted_idv_token`, `minted_idvtoken_expiry_time_secs`) проверяется, и истёкший или пустой сбрасывает процесс remediation. Какие числовые состояния соответствуют каким серверным шагам, выведено по именам тегов (inferred).

### 3.2 Экраны регистрации (found, все неэкспортируемые)

| Группа | Activities (`com.whatsapp.registration.app.*`, если не указано иное) |
|-------|--------------------------------------------------------------|
| Вход | `EULA` (тег `eula_screen` / `eula_with_language_selector`), `phonenumberentry.RegisterPhone`, `RegisterAsDependentActivity`, `RegTabletIntroActivity`, `RegTabletChooseOptionActivity` |
| Разрешения | `RegPermissionsExplainerActivity`, `RegNotificationPermissionPrimerActivity` |
| Верификация | `verifyphone.VerifyPhoneNumber`, `sendsmstowa.SendSmsToWa`, `ManualSmsRequest`, `flashcall.PrimaryFlashCallEducationScreen`, `email.RegisterEmail`, `email.VerifyEmail`, `email.EmailEducationScreen`, `email.UnverifiedEmailSetupRegUpsellActivity`, `email.ConfirmEmailSetupRegUpsellActivity`, `backuptoken.BackupTokenEducationScreen`, `VerifyTwoFactorAuth` |
| Защита аккаунта | `accountdefence.DeviceConfirmationRegistrationActivity`, `accountdefence.ui.OldDeviceSecureAccountActivity`, `OldDeviceSecureAccount2FaActivity`, `OldDeviceMoveAccountNoticeActivity` |
| Блокировки | `parole.CustomRegistrationBlockActivity`, `downgrade.DowngradeFrictionActivity`, `com.whatsapp.userban.ui.BanAppealActivity` |
| Миграция | `directmigration.RestoreFromConsumerDatabaseActivity`, `MigrationStartTransferActivity`, `RequestPermissionFromSisterAppActivity`, `com.whatsapp.migration.transfer.ui.*` |
| Имя / смена номера | `RegisterName`, `phonenumberentry.ChangeNumber*` |
| Режим companion | `com.whatsapp.companionmode.registration.ui.RegisterAsCompanionActivity`, `RegisterAsCompanionEnterNumberActivity`, `RegisterAsCompanionLinkCodeActivity`, `CompanionBootstrapActivity`, `CompanionPostLogoutActivity` |
| Выход из аккаунта | `logout.ui.PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`, `loginfailure.LogoutMessageActivity` |
| Поддержка | `inappsupport.ui.app.LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity` |

### 3.3 Выбор языка и страны (found)

| Элемент | Деталь |
|------|--------|
| Язык | `LanguageSelectorBottomSheet` открывается из `EULA` (событие воронки `language_selected`; метрики `language_selector_clicked_count`, `language_selector_time_spent` в `K49`); `FullScreenLanguageSelectorActivity` на стороне настроек неэкспортируемый |
| Названия стран | 63 офлайн-таблицы `assets/country_names_<lang>.tsv` (`ISO code<TAB>name`); сетевого поиска для выбора страны не найдено |
| Предзаполнение номера | `RegisterPhone` использует подсказки номера Google (`RegisterPhone/launchGooglePNHints`) и путь SIM "what's my number", требующий разрешения на телефон; extras EULA `RegisterPhone.phone_number`, `country_code`, `auto_submit_after_prefill`, `one_click_from_eula` |
| Юридические ссылки на `EULA` | `https://www.whatsapp.com/legal/terms-of-service` или `/terms`, `privacy-policy` или `privacy-policies` (вариант определяется конфигурацией) |

---

## 4. Deep links и веб-ссылки

### 4.1 Алиасы точек входа (found)

| Алиас | Цель | Фильтры |
|-------|--------|---------|
| `TextAndDirectChatDeepLink` | `DeepLinkActivity` | `http(s)://api.whatsapp.com`, `wa.me`; `https://[www.]whatsapp.com` пути `/channel`, `/channel_status`, `/updates`, `/aimediainput`, `/aivoice`, `/dl`, `/privacy/disclosure`, `/wamo/status/link-{instagram,facebook}-in-house-ad`; схемы `whatsapp`, `whatsapp-smb`, `whatsapp-consumer`, `whatsapp-sheet` (списки хостов, 100+ хостов) |
| `VerifyOtpDeepLink` | `DeepLinkActivity` | `http(s)://b.whatsapp.com`, `http(s)://v.whatsapp.com` |
| `FoaDeeplinkActivityAliasUniversalLink`, `FoaDeeplinkActivityAliasAppScheme` | `DeepLinkActivity` | в этом манифесте фильтра нет (объявлены для deep-link библиотеки семейства Meta) |
| `AcceptInviteLinkActivityDeepLink` | `HomeActivity` | `chat.whatsapp.com` |

Сам `DeepLinkActivity` не экспортируется; каждый внешний путь проходит через алиас. Все фильтры с `autoVerify="true"` покрывают только https-хосты. Несколько фильтров на `whatsapp`, `whatsapp-consumer`, `whatsapp-smb` содержат и `VIEW`, и пользовательское действие `com.whatsapp.DEEP_LINK_REDIRECT`, поэтому алиас отвечает на явный intent с этим действием от любого приложения (found: форма фильтра).

### 4.2 Ссылки, обрабатывающие состояние до регистрации (found)

| Ссылка | Якорь парсера | Поведение |
|------|---------------|-----------|
| `https://[www.]whatsapp.com/dl?wsu=<6 digits>` | `IJB.A01`: путь `dl`, query `wsu`, соответствующий `\d{6}`, лог `DeepLinkHelper/parseUri/web signup uri`, код **193** | передача из веб-регистрации; значение на клиенте проверяется только regex |
| `whatsapp://s/signup` (один сегмент пути `signup`) | `IJB.A01` код **216**, ограничен ab-props **25005** или **25801**; обработчик `handleInAppSignupDeepLink` требует схему `whatsapp` и query `s` | регистрация в приложении; логируется через `ApiSignupFlowLogger` с `signup_id` (связка хоста `s` выведена из манифеста, inferred) |
| `https://v.whatsapp.com/<code>`, `https://b.whatsapp.com/<code>` (последний сегмент пути) и `whatsapp://r?c=<code>` | ветка регистрации `DeepLinkActivity`, лог `DeepLinkActivity/Registration deeplink/registration state:` | ссылка email-OTP. Состояние 1 открывает `RegisterPhone` с extra `tapped_sms_link`; состояние 2 открывает `VerifyEmail` с `email_otp`, `entrypoint`, `session_id`, `challenge_flow=false` и сообщает `email_otp_deeplink_redirect_to_register_name`; другие состояния перенаправляют в настройки (`settings_verification_email_address_verified`, inferred). Код передаётся как extra; верификация происходит на сервере (unknown) |
| `whatsapp://code-linking?auth=<nonce>` | код **77**, обработчик `maybeStartCodeLinkingFlow`, ab-prop **4560** (`ENABLE_CODE_LINKING_DEEP_LINK_CODE`), pref `adl_deep_link_nonce` с окном 300000 (единица измерения выведена как мс, inferred) | процесс привязки устройства по коду; пропускается, когда флаг выключен или nonce старше окна |
| `whatsapp://help/<segment>` | код **62**; офлайн-ветка логирует `DeepLinkActivity/help/no-connectivity` | справочная статья |
| `whatsapp://support` | код **30** (извлечён из парсера; обработчик логирует `about/no-connectivity`) | экран поддержки / о приложении, нужно подключение |

### 4.3 Gate до регистрации

| Якорь | Находка | Tier |
|--------|---------|------|
| `DeepLinkActivity/deeplink not allowed before registration/` и причина `not_allowed_before_registration` | присутствует; enum причин сопоставляет значение 0 с этой строкой; источник причины 0 для обычных ссылок не выделен | found (строки), unknown (источник) |
| Обработчики по кодам | каждый обработчик сам проверяет состояние регистрации (вызовы `C0Gk.A0C()` / `A02()` в телах switch) | found |
| Allowlist кодов без входа | не определён заново: `C02T` в этой сборке — последовательный executor, а `C02U` — общий класс целочисленных констант, поэтому прежние имена классов не соответствуют | unknown |
| Результат `JXK` (`code`, `source`, reason), строится `IJB`, `IJC`, `IJD`, `IJE` | выход парсера, потребляется `DeepLinkActivity.A0w` | found |

Для разрешения содержимого (чат, канал, каталог) всё ещё нужен аккаунт: обработчики инвайтов в группы и `wa.me/<phone>` используют аутентифицированную сессию (inferred по именам обработчиков; сквозная трассировка здесь не проводилась).

---

## 5. Хосты и эндпоинты, к которым обращаются без аккаунта

### 5.1 HTTP регистрации (found)

16 путей, ключ XOR 18 в `AbstractC45307Jps`, все заново декодированы в 2.26.41.6: `/v2/exist`, `/v2/code`, `/v2/register`, `/v2/security`, `/v2/challenge`, `/v2/passkey_auth`, `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop`, `/v2/device_logout_send`, `/v2/device_logout_fetch`, `/v2/wfs`. Ещё две константы декодируются в `ENC` и `H` (назначение unknown). Списки полей для первой группы приведены в [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) раздел 3.1. Базовый хост `v.whatsapp.net` — имя из вшитой таблицы (5.4); код, соединяющий хост и путь, находится в стеках wamsys / Kotlin и здесь не читался (inferred).

Селектор `K49.A0b` выбирает стек Kotlin (`KotlinRegistrationBridge`) или нативный стек `wamsys`; нативный стек должен быть инициализирован первым (`ensureWamsysForRegBootstrapped`, ошибка `FAIL_TO_INITIALIZE_WAMSYS`).

### 5.2 Прочие HTTPS-эндпоинты (found литерал, аутентификация как указано)

| Хост / URL | Метод | Аутентификация в коде | Вызывающий | Без аккаунта? |
|------------|--------|--------------|--------|---------------|
| `https://www.whatsapp.com/contact/noclient/verification/` | multipart POST | нет | `C47328KmN` case 0 (форма поддержки) | да |
| `https://graph.<pref_graphql_domain>/graphql` (по умолчанию `graph.whatsapp.com`) | POST JSON | вшитый client token приложения в теле `access_token` | `AbstractC40195HfH` и подклассы | да (статус бана / апелляция) |
| `https://crashlogs.whatsapp.net/wa_clb_data`, `/wa_fls_upload_check`, `/wa_profilo_data`, `/whatson_logs_upload` | POST | вшитый токен приложения (выгрузка логов добавляет `access_token`, `type`, `from_jid`, `ticket_id`, `build_id`) | `C10V`, `C05640An`, `ExceptionsUploadService`, `ProfiloUploadService`, `CM8` | работает без входа; содержимое `from_jid` без входа unknown |
| `https://acs.whatsapp.com/graphql` | POST | ACS-токен или конфигурация OHAI (без JID) | `C31991Nz`, `R5t` | да (деидентифицированные запросы) |
| `https://static.whatsapp.net/wa/static/{downloadable,network_resource,payments/*}`, `/sticker?...`, `/payments/background` | GET | нет | загрузчики ресурсов UI | да |
| `https://mmg.whatsapp.net/proxygen/health`, base `https://mmg.whatsapp.net` (config 22436) | GET | нет | медиа / health | да |
| `https://www.gstatic.com/recaptcha/verify_key/orcas/prod/android/verify_key.txt` | GET | нет | `C44464JbH` (используется `RequestCodeRepository`, `VerifyCodeRepository`, `VerifyPhoneNumber`) | да (captcha регистрации) |
| `https://www.whatsapp.com/compliance/xfac/mint` | POST form | не замечена | `CommonRemediationApi` (возрастная remediation, `minted_idv_token`) | доступен до регистрации: unknown |
| `https://www.whatsapp.com/v1/auth/canonical/token/` | POST form `nonce`, `user_id`, `device_id`, `client_pub_key` | нет | `CanonicalUserCompanionDeviceManager` | путь companion / связанного аккаунта, не чистая регистрация |
| `https://api.whatsapp.net/support/add_bug_attachment` | multipart POST | `Authorization: Bearer <token>` | `PostBugAttachmentUploader` (баг-репорт в приложении) | нет (привязан к токену) |
| `https://graph.whatsapp.net/v2.2/maps_configs?...&access_token=` (по умолчанию `graph.facebook.com`) | GET | токен приложения в URL | конфигурация карт `N6n` | триггер не относится к регистрации (inferred) |
| `https://api.whatsapp.net/calendar/integrations/` | запрос | сессия | функция календаря | нет |

Вшитые токены: существуют две формы в стиле Facebook, `WA|<app_id>|<secret>` в значении по умолчанию клиента Graph и `<app_id>|<secret>` в загрузчике логов. Значения здесь не приводятся. Они идентифицируют приложение, а не пользователя.

### 5.3 Начальная загрузка DNS и подключения (found)

| Элемент | Деталь |
|------|--------|
| Вшитая таблица `AbstractC47101wK` | хост в список IPv4 / IPv6 для 18 имён: `e1..e16`, `g`, `v` под `.whatsapp.net` (каждое с двойником с завершающей точкой); сеть не нужна |
| `C36881dC` (DnsCache) | порядок использования: основной resolver, MNS DNS resolver (`DnsCache/resolveViaMnsDns`, в этой ветке проверяется строка `v.whatsapp.net`), вторичный resolver, жёстко заданная таблица; жёсткие lookups завершаются ошибкой `no hardcoded ips found for <host>`, когда в таблице нет записи, и пропускаются с `hardcoded dns resolver disabled`, когда бит опции выключен |
| Чат-хост | запись `g.whatsapp.net` читается напрямую (`C36881dC.A01`) |

Формат обмена resolver MNS находится в нативном коде: unknown.

### 5.4 REST-пути, которых не существует (found negative)

Неаутентифицированного REST-запроса для gating или конфигурации (`/gk`, `/props`, `/config`) не найдено. Эксперименты до входа приходят по HTTP регистрации: `/v2/reg_onboard_abprop` (`K49.checkPreChatdABProps`) отправляет `ab_hash` из pref `pref_pre_chatd_ab_hash`, `ab_exposure`/`ab_key` из `pref_pre_chatd_ab_key`, а также поля устройства из раздела 7.

---

## 6. Форма поддержки без входа (found)

`LoggedOutContactFormActivity` (неэкспортируемая) — единственный полностью безаккаунтный процесс поддержки в этой сборке.

| Intent extra (префикс `com.whatsapp.inappsupport.ui.app.LoggedOutContactFormActivity.`) | Назначение |
|------|-----|
| `PhoneNumber`, `CountryCode` | предзаполненный номер; пустая строка при отсутствии |
| `From` | метка точки входа |
| `ServerStatus` | строка статуса, переданная вызывающим (inferred: статус сервера регистрации) |
| `IsRegistrationVerification` | boolean; при успехе выполняется последующий вызов (цель не определена) |
| `SupportUserContext` (`K8W`) | точка входа и CMS ids (`Entry point`, `Cms ids`) |

Поля формы: email (чипы-подсказки `@gmail.com`, `@hotmail.com`, `@icloud.com`, `@outlook.com`, `@yahoo.com`), описание, до 3 скриншотов, выбираемых из `MediaStore`.

Отправка (`C47328KmN` case 0, тег `logged_out_contact_form`, завершающий аргумент 20 с неопределённым смыслом):

| Часть | Имя | Содержимое |
|------|------|---------|
| field | `email` | введённый email |
| field | `message` | описание |
| field | `platform` | литерал `ANDROID` |
| field | `phone_number` | введённый номер |
| field | `debug_info` | текст, построенный `C10V.A08` (раздел 7.3) |
| file | `log_data` | `logs.tar.gz` клиентского лога (предварительно ротируется и сжимается) |
| files | `attachment_<n>` | скриншоты, перекодированные в JPEG качества 80, ограничение 2048 px, сохраняются только при размере 10 MiB или меньше |
| extra | `skip_saga_copy=true`, `saga_copy=true`, `pn` | `pn` = код страны + номер, когда оба непусты |

Результат: HTTP-статус передаётся в callback результата (`C46422KQg`); сбой отображается как `Server error: <status>` или `Network error`; успех открывает `LoggedOutContactSuccessActivity` (extra `...Email`). Точное сопоставление статуса с успехом не читалось. Вызов — обычный HTTPS POST через HTTP-клиент приложения; это не вызов GraphQL. Случайный UUID `anid` (7.1) генерируется для каждой отправки.

---

## 7. Идентификаторы, отправляемые до входа

### 7.1 Таблица идентификаторов

| Идентификатор | Где | Источник | Примечания | Tier |
|------------|-------|--------|-------|------|
| `fdid` | `/v2/pre_pn_client_log`, запросы регистрации | `C38141gV.Ax2()`: случайный `UUID.randomUUID()`, сохраняется как `phoneid_id` + `phoneid_timestamp` в prefs | сохраняется между попытками регистрации; тот же id возвращает `PhoneIdRequestReceiver` | found |
| `fid` | запросы регистрации | `C47381wu.Ax2()`: prefs `phoneyid_id` + `phoneyid_timestamp`, отправляется как `<id>|<timestamp>` только при наличии | вторичный идентификатор семейства; источник значения не прослежен | found (назначение inferred) |
| `anid` | форма поддержки | `C11J.A01()`: `UUID.randomUUID()` при каждом вызове, также логируется как событие WAM | случайный id для каждой отправки | found |
| `advertising_id` / `android_advertising_id` | `/v2/exist`, `/v2/code`, `/v2/register`; лог воронки | рекламный id Google, если доступен | исключён из строки debug-лога логгера воронки | found |
| `authkey`, `e_ident`, `e_keytype`, `e_regid`, `e_skey_id`, `e_skey_val`, `e_skey_sig`, `e_pq_last_resort_{id,val,sig}` | запросы регистрации | `C45446JsB`: клиентский статический ключ Noise и набор ключей Signal | публичный материал | found |
| `gpia` | запросы регистрации | стандартный токен Play Integrity, под флагом | см. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) | found |
| `ab_key`, `ab_hash`, `ab_exposure` | `/v2/exist`, `/v2/pre_pn_client_log`, `/v2/reg_onboard_abprop` | prefs `pref_pre_chatd_ab_key` / `pref_pre_chatd_ab_hash` | группа эксперимента | found |
| `device_country` | лог воронки | `TelephonyManager.getSimCountryIso()` в верхнем регистре, `ZZ` при отсутствии | | found |
| `access_token` (приложение) | Graph, выгрузка логов | вшитая константа | идентичность приложения, не пользователя | found |
| `request_token` / `token` | статус бана / апелляция | pref `wfac_ban_status_token` (статус) и сохранённый токен апелляции | непрозрачный, выдаётся сервером в момент бана ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md)) | found |
| `from_jid` | выгрузка логов | JID аккаунта при наличии | содержимое без входа unknown | found (поле), unknown (значение) |
| `registration_trace_id`, `request_id`, `nonce_encryption_key` | мутация восстановления аккаунта | `AccountRecoveryManager` (раздел 8.2) | | found |

### 7.2 Атрибуты устройства в запросах регистрации (found, хелперы `K49` `A0O`, `A0Q`, `A0R`, `A0U`, `A0W`, `A0X`)

`network_radio_type`, `simnum` (`0` / `1`), `hasinrc` (файл `rc2` присутствует), `pid` (id процесса), `device_ram`, `sim_type`, `airplane_mode_type`, `cellular_strength` (уровень сигнала, `5` по умолчанию), `roaming_type`, `preloads_app_manager_id`, `preloads_attribution`, `entrypoint` (`create_paa` или `suma`), `tos_version` (`5`), `old_phone_number` (процесс смены номера). Ключи метрик телеметрии в том же классе (found, использование в запросах не подтверждено): `network_operator_name`, `sim_operator_name`, `sim_state`, `read_phone_permission_granted`, `mistyped`, `c2dm_reg_id` (читается из prefs).

### 7.3 Содержимое лога воронки (found, `PrePnBaseFunnelLogger$sendPrePNFunnelLog$1`)

До появления номера клиент отправляет: `current_screen`, `previous_screen` (pref `pref_previous_screen`, по умолчанию `unknown`), `action_taken`, `event_name`, `access_funnel_type=wa`, `app_campaign_download_source`, `is_add_account_flow`, `android_advertising_id`, `ab_key`, `device_country`, `fdid`, перечисленные выше атрибуты устройства и `entrypoint`. В процессах добавления аккаунта или fallback без входа также отправляются `primary_logout_session_id` и `number_of_accounts`. Отправка пропускается при сбое инициализации wamsys.

### 7.4 `debug_info` формы поддержки (found, `C10V.A08`, аргумент JID в этом вызове равен `null`)

Метки, записываемые в текст: `useragent`, `Socket Conn`, `Connection`, `Server`, `Datacenter`, `Sim`, `Free Space Built-In` / `Removable`, `Network metered` / `restricted`, `Data roaming`, `Tel roaming`, `Diagnostic Codes`, `ABprops hash state`, `Screen reader`, `Fingerprint eligible`, поля статуса бэкапа, `Is Companion`, `Number of Accounts`, `Mobile Build Id`, `wfl_state`, `isMetaVerified`, `Mistyped` / `Mistyped Last6` / `L Distance` (сравнение введённого номера с номером SIM), а также идентификаторы последних звонков, если есть история звонков. Метка `entity id` записывается только при передаче JID, чего здесь не происходит.

---

## 8. Вызовы Graph и MEX без пользовательской сессии

### 8.1 Graph-запросы с токеном приложения (found)

Базовый класс `AbstractC40195HfH.CND` строит `https://graph.<A0f()>/graphql` (`A0f()` = pref `pref_graphql_domain`, по умолчанию `whatsapp.com`; подклассы `GEV`, `GEX`, `GET`, `GEW`, `GEU` и семейство Meta-аккаунтов `C45F` переключаются на `facebook.com` / `instagram.com`). Тело JSON: переменные операции, `access_token` (вшитый токен, когда подкласс не передаёт свой), `doc_id`, `lang`, `Content-Type`. Заголовок `X-FB-Request-Analytics-Tags` добавляется при отсутствии.

| Класс | doc_id | Переменные | Назначение |
|-------|-------:|-----------|---------|
| `C37604GYf` | **4276154569100535** | `app_id` (`dev.app.id`), `request_token` | опрос статуса WFAC-бана (`WfacBanRepository/fetchBanStatus`, токен из pref `wfac_ban_status_token`) |
| `C37409GLo` | **27883644401256929** или **4276154569100535** (boolean) | то же | статус бана через `HG2.A01` |
| `C37414GLt` | **38509456535312323** или **5473316762755318** (boolean) | `app_id`, `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}`; plaintext `{token, debug_info, description}`, контекст `WA_INAPP_BAN_APPEALS` | отправка апелляции на бан (`C40191HfD`); подробности в [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) раздел 10 |
| `C37408GLn` | **5803265299734043** | `app_id`, `client_pub_key` | назначение unknown (отправляет публичный ключ клиента); вызывающий не прослежен |
| `C37601GYc`, `GYd`, `GYe` | `GYd` **25453433540999208**, `GYe` **25974020015520396** (`GYc` не несёт id в собственном классе) | `caller_name` `fx_waffle_contextual_pause_account_match`, `wa_waffle_certs`, `fx_waffle_foa_unpause` | помощники привязки аккаунтов Meta |
| `C37605GYg`, `GYh`, `GYi` | **26573478745654327**, **26742313962085910**, **27503298369362501**, **28331348373116386**, **25840634418966704** | заголовок `IG-Set-Waffle-Graphql-Access-Token`, ключ `ACCESS_TOKEN` | привязка аккаунтов Facebook / Instagram; требуется токен привязанного аккаунта (inferred по именам заголовка и ключа) |
| `C37413GLs` | **7236799486398397** | `batches`, `device_model`, `device_os`, `device_os_version`, `event_time`, `is_employee`, `primary_locale` | пакеты клиентских событий (inferred по именам переменных) |

doc_id 6960707423955525 (устаревший id мутации апелляции, о котором сообщалось для старых сборок) в 2.26.41.6 не встречается. Имена операций запросов апелляции и статуса этими классами не несутся (unknown).

Отличие от [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) раздел 10: для `C37414GLt`, `C37409GLo` и `C37604GYf` хост — `graph.<pref_graphql_domain>` (по умолчанию `graph.whatsapp.com`); только перечисленные выше подклассы переопределяют его на `facebook.com`.

### 8.2 Операции MEX с местом вызова во время регистрации или без входа (found, схема `whatsapp-android-mex`)

doc_ids из `assets/whatsapp-android-mex_client_persist_ids.json` (и файлов `www` / `wamo`, где указано).

| Операция | doc_id | Место вызова |
|-----------|-------:|-----------|
| `GetAutoConfConfidenceChallenge` | 25578301865133112 | `C40175Het`, `C40196HfI` (ping уверенности autoconf) |
| `ValidateVerifierConfidence` | 25879669248324812 | `C40196HfI`, `C40197HfJ` |
| `FetchReachoutTimelockQuery` | 25627902213558773 | `RunnableC23952AUh` |
| `RemoveAccountReachoutTimelock` | 25040013452293167 | не прослежено |
| `UserCountryCodeGet` | 25292528387076991 | `MexUserCountryCodeRepository` |
| `MobileConfigFetchQuery` | 29248978061376279 | не прослежено |
| `SubmitAge`, `GetAgeExperience`, `SetAgeExperienceMutation` | 26049558371296621, 26567868986241476, 26051006311231325 | возрастные процессы |
| `TosSetResult` | 25225843213776555 | принятие условий |
| `GetWaOldResponse` | 25784374561179853 | верификация через старый телефон |
| `WWWTriggerAcountRecovery` | 24896267680055094 | `AccountRecoveryManager` (переменные `nonce_encryption_key`, `use_case`, `registration_trace_id`, `request_id`) |
| `WWWCreateUser`, `WWWDeleteUser`, `WWWGetCertificates` | 8548056818544135, 7989555047767245, 25094190163544446 | привязка аккаунтов |
| `OhaiKeyConfigQuery` | 25069818679280758 | `N5I` (начальная загрузка ACS / OHAI) |
| `CreateEnforcementAppeal` | 26933630359642347 | клиент enforcement для newsletter |
| `NewsletterCreateReportAppeal` (mex), `CreateGroupSuspensionAppealMutation` (www), `WamoReportPromoAppealV2Mutation` (wamo) | 27792557363683798, 25646047815072526, 26867425009592691 | операции апелляции (привязаны к аккаунту; присутствуют в assets) |

MEX отправляется как IQ `xmlns="w:mex"` с `<query query_id=...>` (`C19370nI`) через чат-соединение (`WAChatdGraphQLClient`). Выполняются ли эти операции в сессии до появления аккаунта, не установлено: см. 8.3.

### 8.3 Чат-соединение без JID (found)

`ConnectionThread.connect` (`HandlerThreadC12340b0`) читает собственный JID; если он null, соединение продолжается только при истинном флаге регистрации companion (`C06830Gm.A02()`), иначе читается второй источник JID (`Ash()`), и если он тоже null, логируется `ConnectionThread/connect/ignored/jid null and not in companion reg` и происходит возврат. Таким образом, регистрация основного телефона не использует чат-соединение с null-JID (согласуется с [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) раздел 6.4). Смысл второго источника выведен (сохранённый или ожидающий регистрации JID, не определён; inferred). Какая сессия несёт вызовы MEX времени регистрации из 8.2, unknown.

### 8.4 Деидентифицированные запросы (found)

`PandoGraphQLRequest.requireAcsToken()` и `requireOhaiConfig()` читаются `C6GN`; запрос, помеченный `@deidentified`, без ACS-токена или конфигурации OHAI выбрасывает исключение (`Request was marked with @deidentified, but no ... was provided`). Поля `AcsOhaiConfig`: имя проекта, doc id, `graphQlUrl=https://acs.whatsapp.com/graphql`, surface, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`. Какие операции несут этот флаг, закодировано в assets `*_pando_flatbuffer_data.bin`: unknown.

---

## 9. Экспортируемые IPC-поверхности с проверками в коде

Все записи экспортируются без разрешения в манифесте, если не указано иное. Этот раздел перечисляет найденные в коде средства контроля, а не вердикт об их стойкости.

### 9.1 `PhoneIdRequestReceiver` (`com.facebook.GET_PHONE_ID`)

Упорядоченный broadcast. Receiver читает extra `auth` типа `PendingIntent` из extras результата и берёт `getCreatorPackage()`. Пакет считается доверенным, когда хеш его сертификата подписи входит в жёстко заданный allow-набор (`AbstractC28130CKz.A04`, SHA-1 сертификатов подписи, значения не приводятся; второй набор SHA-256 используется в `CHA.A02`). Доверенный вызывающий получает phone id и его timestamp как результат broadcast (`setResult(-1, id, {timestamp})`); альтернативный путь возвращает вторичный id, когда это допускает флаг **3651**. Декомпилированный поток управления вокруг переменной доверия частичный, поэтому точный приоритет выведен (inferred).

### 9.2 Providers семейства приложений (found)

| Компонент | Найденные средства контроля |
|-----------|----------------|
| `FamilyAppsCredentialsProvider` | `getCallingPackage()`; карта обработчиков по selection; UID вызывающего разрешается в сертификат и проверяется по доверенному набору обработчика (`C45775Jyk.A01`); допустимость link-manager (`WfalManager.A00`); feature flags; состояние привязки должно входить в допустимый набор обработчика; возвращает 3-колоночный cursor (auth proof, bundle, TTL) из prefs `pref_foa_nta_ipc_bundle_auth_proof`, `pref_foa_nta_ipc_bundle`, `foa_nta_ipc_bundle_ttl`; ошибки для истёкшего или отсутствующего кэша. Расшифровка "NTA" unknown |
| `FamilyAppsUserValuesProvider` | один selection `foa_wo_wa_link_eligibility_values`, читается `getCallingPackage()` |
| `WaAccountsCenterService` | action `com.whatsapp.wfl.OPERATION`; тело класса в декомпиляции — заглушка (проверки unknown) |
| `QuickSendsContactsProvider` | шаги валидации `getCallingPackage()` логируются (`validation_start` / `validation_end`); отдаёт зашифрованные файлы фото `.enc` и столбцы контактов (`obfuscated_chat_id`, `display_name`, `profile_photo_uri`, `photo_key`) |
| `OrbitSsoProvider` (`com.whatsapp.orbit.v2.sso`) | gate по feature flag; пакет вызывающего должен быть в allow-list (`AbstractC62035Rsx.A00`, иначе `SecurityException ... is not allowlisted`); проверка предусловия (`BS3()`) перед любым методом; методы `get_profile` (возвращает `display_name`, `phone_number`, `avatar_uri`, `avatar_mime_type`), `get_accounts`, `get_nonce`, `get_token`; путь файла `avatar` только для чтения. Allow-list сопоставляется по имени пакета в `A01()`; проверка сертификата, если есть, не в этом методе (unknown). Что проверяет `BS3()`, выведено как состояние входа (inferred) |
| `OrbitMessagesProvider` (`com.whatsapp.orbitmessages`) | файлы открываются только в режиме `r`, последний сегмент `media`, значения `media_handle` с префиксом `v1.` расшифровываются AES-GCM; проверки вызывающего не найдены (unknown) |
| `OrbitCompanionLinkActivity` | читает `getCallingPackage()` и extra `qr_data`; таймеры удержания / согласия; возвращает только результат (`return_result_only`) через `CompanionHelloConfirmationActivity` |
| `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | не анализировались |

### 9.3 Handshake OTP (`OtpRequestedReceiver`)

Ожидает extra `PendingIntent` `_ci_` (идентичность вызывающего) и необязательный UUID `request_id` (проверяется regex). Записывает пакет-создатель напротив сгенерированного значения, логирует событие WAM и, когда флаг **6617** включён или пакет есть в списке из config **7050**, отвечает broadcast `com.whatsapp.otp.OTP_HANDSHAKE_CONFIRMATION` этому пакету с `request_id`. Отсутствующий `PendingIntent` отклоняется (`PendingIntent missing from handshake Intent`). Проверки регистрации в этом receiver не найдено.

### 9.4 `AccountTransferReceiver`

Действует только на `com.google.android.gms.auth.START_ACCOUNT_EXPORT`, и только когда на устройстве есть защищённый keyguard и проходит проверка возможностей (`AbstractC21360rJ.A01`). Сам экспорт выполняется на фоновом executor (`C05X.A02(...).CVx`); содержимое unknown.

---

## 10. Точки входа просмотра бана и апелляции

| Вход | Механизм | Evidence |
|-------|-----------|----------|
| Холодный старт в состоянии WFAC | `Main` состояние 21 запускает `WfacBanActivity` через `HBC.A00` | found (3.1) |
| `BanAppealActivity` | неэкспортируемая; запускается `Main` (extra `launch_source`) и процессом перманентного бана | found |
| Опрос статуса бана | Graph, `wfac_ban_status_token`, throttle 5 с в pref `wfac_last_ban_status_fetch_timestamp_ms` | found ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 2.2) |
| Отправка апелляции | Graph с зашифрованным `user_request` (8.1) | found |
| Ответ регистрации | поля `/v2/register` `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `custom_block_screen`, `version_upgrade` | found ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) 3.3) |
| Обращение в поддержку | `LoggedOutContactFormActivity` (раздел 6), флаг `IsRegistrationVerification` для ошибок регистрации | found |
| Deep links | `whatsapp://support`, `whatsapp://help`, `v.whatsapp.com` / `b.whatsapp.com` | found (4.2) |

Идентичность пользователя на пути апелляции — это непрозрачный токен, выданный сервером, а не номер телефона или id устройства (имена полей токена выше; происхождение unknown).

---

## 11. Случаи ошибок и подводные камни

| Симптом | Причина | Примечания |
|---------|-------|-------|
| `ConnectionThread/connect/ignored/jid null and not in companion reg` | нет JID и это не регистрация companion | норма до регистрации; регистрация использует HTTPS |
| `FAIL_TO_INITIALIZE_WAMSYS` | сбой инициализации нативного стека (`ensureWamsysForRegBootstrapped`) | HTTP регистрации и лог воронки до ввода номера пропускаются |
| `DeepLinkActivity/deeplink not allowed before registration/` | код ссылки заблокирован gate | allowlist не определён (4.3) |
| `Request was marked with @deidentified, but no ...` | отсутствует конфигурация ACS / OHAI | запрос не отправлен |

---

## 12. Ключевые различия

| Не путать | Факт |
|----------------|------|
| Экспортируемое vs доступное без аккаунта | 97 экспортируемых записей; большинство ничего полезного не делают, пока нет зарегистрированного аккаунта; только записи из 2.2 и 4.2 обрабатывают состояние регистрации |
| Токен приложения vs токен пользователя | вшитый `WA|<app_id>|<secret>` идентифицирует приложение; вызовы по бану добавляют непрозрачный request token, а не пользовательскую сессию |
| `fdid` vs рекламный id | `fdid` — сгенерированный приложением UUID, переживающий повторную регистрацию; рекламный id — значение Google |
| Форма поддержки без входа vs поддержка в приложении | форма отправляет POST на `www.whatsapp.com/contact/noclient/verification/` с введёнными полями; поддержка в приложении использует сессию (не анализировалась) |
| HTTP регистрации vs чат-соединение | регистрация идёт по HTTPS `/v2/*`; чат-подключение с null-JID только для регистрации companion |

---

## 13. Полный процесс

```
[App launch / link tap]
    │  Main (only launcher)  or  DeepLinkActivity alias (wa.me, whatsapp.com/dl, v|b.whatsapp.com, whatsapp://...)
    ▼
[Main.A5W]  registration state ──► 2 regname │ 21 WFAC ban │ 41 age consent │ 45 PAA │ 50/51 login-back │ 56 username
    │  default
    ▼
[EULA]  language bottom sheet, ToS / privacy links
    │        └── /v2/pre_pn_client_log  (fdid, screens, device attrs, advertising id)   [ab_key via /v2/reg_onboard_abprop]
    ▼
[RegisterPhone]  hints / SIM number / country names (offline)
    │  /v2/exist  (fdid, fid, authkey, e_* key bundle, device attrs, gpia?)
    ▼
[VerifyPhoneNumber]  reCAPTCHA key GET (gstatic) ── /v2/code ── /v2/register
    │                        │
    │                        ├── ok  ──► RegisterName ──► account exists (leaves this report)
    │                        └── fail: violation_type / appeal_token / custom_block_screen
    │                                      │
    │                                      ▼
    │                         [WfacBanActivity / BanAppealActivity]
    │                                 Graph POST graph.whatsapp.com/graphql
    │                                 doc 4276154569100535 | 27883644401256929  (status, request_token)
    │                                 doc 38509456535312323 | 5473316762755318  (appeal, encrypted)
    ▼
[Help needed]
    LoggedOutContactFormActivity ──► POST www.whatsapp.com/contact/noclient/verification/
                                      email, message, platform=ANDROID, phone_number, debug_info, logs.tar.gz, <=3 JPEG
    ▼
[Background, any state]
    crashlogs.whatsapp.net uploads  │  static.whatsapp.net assets  │  acs.whatsapp.com (ACS/OHAI)
    DNS: system ► MNS ► secondary ► compiled table (e1..e16, g, v)
```

---

## 14. Неизвестное

| Вопрос | Почему unknown |
|----------|-------------|
| Какие коды ссылок разрешены до регистрации | класс allowlist не определён заново; обработчики проверяют состояние по отдельности, прослежены только четыре |
| Источник причины 0 (`not_allowed_before_registration`) | не выделен в большом switch `DeepLinkActivity` |
| Соединение хоста и пути для `/v2/*`, констант `ENC`, `H` | построители запросов wamsys / Kotlin не читались |
| Какая сессия несёт операции MEX времени регистрации | подключение с null-JID отклоняется вне регистрации companion; источник `Ash()` не определён |
| Содержимое `from_jid` в выгрузках логов без входа | `AbstractC05620Al.A0G` абстрактный |
| Серверная валидация токенов, кодов, payload апелляции | серверная сторона |
| Операции с `@deidentified` | в `*_pando_flatbuffer_data.bin`, схемы нет |
| Смысл "NTA", источника вторичного id `phoneyid_id`, `c2dm_reg_id` как поля запроса | только имена |
| Можно ли запустить `HomeActivity` без регистрации и что она делает | gate базового класса не определён |
