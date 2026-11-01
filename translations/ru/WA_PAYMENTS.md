<!-- src-sha1: 1fe6d8278b8f0a0adfe50041466f968ec368a2e2 -->
# WhatsApp Платежи — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-11-01
**Область:** типы платёжных сообщений в чате (`sendPaymentMessage`, `requestPaymentMessage`, `declinePaymentRequestMessage`, `cancelPaymentRequestMessage`, разделённые платежи (split payments), приглашение/напоминание о платеже) и их proto-поля, мультирейловая архитектура клиента (India UPI, Brazil Pix, Mexico, Indonesia, универсальный рейл "UPR"), привязка VPA/банковского счёта и процесс онбординга UPI, встроенный слой учётных данных/PIN/привязки устройства NPCI "Common Library" (CL), синхронизация статуса транзакций, уровни шифрования (E2E чата vs NPCI credential blob), платёжные операции GraphQL/MEX (doc_id), правила автосчитывания OTP от NPCI, feature flags, обработка кодов отказа/ошибок

---

## 1. Что это (обзор)

WhatsApp Android использует единый общий протокол платежей в чате (proto-типы сообщений, переносимые внутри обычного E2E `Message`) плюс несколько специфичных для страны платёжных *рейлов* (rails), каждый со своим UI онбординга, операциями GraphQL и (для Индии) встроенной сторонней библиотекой учётных данных. Все находки — результат статического анализа декомпилированного APK; ничего не перехватывалось на канале передачи. Уровни достоверности: **found** = прочитано непосредственно в коде/ассетах, **inferred** = выведено из кода, **unknown** = не установлено. Обфусцированные имена меняются от сборки к сборке и были разрешены в 2.26.41.6 на основе стабильных строк (константы `FIELD_NUMBER`, имена AIDL-интерфейсов, каталоги GraphQL-операций, имена файлов ассетов).

| Слой | Имя/путь в 2.26.41.6 | Роль |
|-------|------------------------|------|
| Протокол сообщений чата | `DSJ` SendPaymentMessage, `C30605DSz` RequestPaymentMessage, `C30502DPa` DeclinePaymentRequestMessage, `DPZ` CancelPaymentRequestMessage, `DT0`/`C30535DQh` split payment, `C30586DSg` PaymentInviteMessage, `C43112IrN` PaymentReminderMessage, `DTS` PaymentInfo | поля в разделе 2 |
| Пакеты рейлов | `com.whatsapp.payments.{common,indiaupi,brazilpay,mexico,indonesia,globalorder,upr,dcp,remittances,split,paymentkey,productinfra,integrity,phoenix}` | один пакет на рынок/рейл, раздел 3 |
| Библиотека учётных данных India UPI | `org.npci.upi.security.{services,pinactivitycomponent}` (`CLRemoteService`, `CLRemoteServiceImpl`, `BinderC48420LDc`, `GetCredential`) | встроенная NPCI "Common Library" (CL), раздел 6 |
| Автосчитывание OTP | `assets/npci/npci_otp_rules.json`, потребитель `org.npci.upi.security.pinactivitycomponent.C0315u` | раздел 10 |
| Каталог GraphQL/MEX | `assets/whatsapp-android-www_client_persist_ids.json` (схема `whatsapp`), `whatsapp-android-mex_client_persist_ids.json` (схема `whatsapp_mex`) | doc_id, раздел 9 |
| Обработчик server push | `C24410wL` ("PaymentsMessageHandler", лог-тег `PaymentsMessageHandler`) | `<notification type="pay\|upi\|fbpay\|transaction\|account-recovery\|alert\|...">`, раздел 8 |
| Объект транзакции | `F7F` (локальная строка транзакции), `DTS` (PaymentInfo для канала/history-sync), строится функцией `EKY.A00` | раздел 8 |

Рейлы, определённые по именам пакетов/классов (found): **India UPI** (`indiaupi`), **Brazil Pix** (`brazilpay`), **Mexico** (`mexico`), **Indonesia** (`indonesia`), а также рейл-агностический пакет "**UPR**" (`upr` — онбординг, управление аккаунтом, bubble UI) и устаревшее упоминание Meta Pay/Novi, всё ещё присутствующее в коде enum/уведомлений (`FBPAY`, `NOVI`), хотя эти сервисы давно не действуют — приводится здесь только потому, что литеральные строки всё ещё существуют в 2.26.41.6. Ниже доказательства по каждому разделу помечены как **India/UPI-specific** или **общее**; не следует считать, что находки по UPI применимы к Pix/Mexico/Indonesia.

---

## 2. Типы платёжных сообщений и proto-поля

### 2.1 Расположение в `Message` (found)

Все типы платёжных сообщений являются прямыми полями верхнеуровневого proto `Message` (`C30628DTw`, тот же класс, что документирован в `WA_MESSAGE_SECRETS.md`). Большинство платёжных под-сообщений **не** предоставляют публичных констант `FIELD_NUMBER` на самом `Message`; номера ниже были восстановлены декодированием упакованной строки message-info `GeneratedMessageLite` этого класса (воспроизводимая кодировка по 2-3 символа на поле: символ номера поля, символ-маркер типа, символ индекса has-bit; индекс has-bit увеличивается ровно на единицу на каждую запись по всему сообщению из ~150 полей, что служит строгой внутренней проверкой согласованности декодирования).

| Поле (Message) | Номер | Тип |
|---|---|---|
| `sendPaymentMessage` | **16** | `SendPaymentMessage` (`DSJ`) |
| `requestPaymentMessage` | **22** | `RequestPaymentMessage` (`C30605DSz`) |
| `declinePaymentRequestMessage` | **23** | `DeclinePaymentRequestMessage` (`C30502DPa`) |
| `cancelPaymentRequestMessage` | **24** | `CancelPaymentRequestMessage` (`DPZ`) |
| `paymentInviteMessage` | **44** | `PaymentInviteMessage` (`C30586DSg`) |
| `splitPaymentMessage` | не декодировано в этом проходе | `SplitPaymentMessage` (`DT0`), `unknown` |
| `splitPaymentUpdateMessage` | не декодировано в этом проходе | `SplitPaymentUpdateMessage` (`C30535DQh`), `unknown` |
| `paymentReminderMessage` | не декодировано в этом проходе | `PaymentReminderMessage` (`C43112IrN`), `unknown` |

Классификатор уровня stanza `<message type="pay">` (общий с другими дополнительными типами) документирован в разделе `WA_MESSAGE_SECRETS.md`, посвящённом выбору типа (`AbstractC30999De0.A02`); здесь повторно не выводится.

### 2.2 SendPaymentMessage (`DSJ`, found)

| Поле | Номер | Тип | Назначение |
|---|---|---|---|
| `noteMessage` | **2** | `Message` (`C30628DTw`) | «заметка» (note), прикреплённая к платежу, сама является полноценным `Message` (обычно содержит только `extendedTextMessage` или стикер) |
| `requestMessageKey` | **3** | `MessageKey` (`BD5`) | присутствует, когда эта отправка является ответом на предыдущий `requestPaymentMessage` |
| `background` | **4** | `PaymentBackground` (`DTJ`) | раздел 2.7 |
| `transactionData` | **5** | string | непрозрачное значение; значение по умолчанию в декомпилированном исходнике — общая константа пустой строки, а не настоящий дефолт |

Номер поля 1 не используется/зарезервирован (для него нет константы `FIELD_NUMBER`).

### 2.3 RequestPaymentMessage (`C30605DSz`, found)

| Поле | Номер | Тип | Назначение |
|---|---|---|---|
| `currencyCodeIso4217` | **1** | string | код ISO 4217 |
| `amount1000` | **2** | int64 | сумма × 1000 (fixed-point, без десятичных знаков в значении на проводе) |
| `requestFrom` | **3** | string | идентификатор запрашивающего (строка JID, наблюдаемая в местах вызова) |
| `noteMessage` | **4** | `Message` | та же схема, что в 2.2 |
| `expiryTimestamp` | **5** | int64 | unix-секунды |
| `amount` | **6** | `Money` (`C30561DRh`) | структурированная сумма, раздел 2.7 |
| `background` | **7** | `PaymentBackground` (`DTJ`) | раздел 2.7 |

### 2.4 DeclinePaymentRequestMessage / CancelPaymentRequestMessage (found)

Оба сообщения минимальны — единственное поле, ссылающееся на исходный запрос:

| Класс | Поле | Номер | Тип |
|---|---|---|---|
| `DeclinePaymentRequestMessage` (`C30502DPa`) | `key` | **1** | `MessageKey` (`BD5`) |
| `CancelPaymentRequestMessage` (`DPZ`) | `key` | **1** | `MessageKey` (`BD5`) |

**Ни одно из сообщений не содержит поля причины/кода ошибки.** Decline и cancel на уровне протокола — это no-op, не несущие ничего, кроме «этот запрос (идентифицированный `key`) отклонён/отменён» — любой текст причины, показанный в UI, является исключительно локальным и не входит в передаваемую полезную нагрузку (found: у обоих классов не существует второго поля; см. раздел 12).

### 2.5 Split payments (found)

`SplitPaymentMessage` (`DT0`):

| Поле | Номер | Тип |
|---|---|---|
| `splitId` | **1** | string |
| `totalAmount` | **2** | `Money` |
| `description` | **3** | string |
| `requesterJid` | **4** | string |
| `participants` | **5** | repeated `SplitPaymentParticipant` (`C30558DRe`) |
| `createdAtMs` | **6** | int64 |
| `contextInfo` | **17** | `MessageContextInfo`-like (`C30617DTl`) |

`SplitPaymentUpdateMessage` (`C30535DQh`): `splitId` (**1**, string), `participantJid` (**2**, string) — пинг статуса по конкретному участнику, без собственной полезной нагрузки суммы/статуса.

### 2.6 PaymentInviteMessage / PaymentReminderMessage (found)

`PaymentInviteMessage` (`C30586DSg`): `serviceType` (**1**, int/enum — связан с кодами сервисов `UPI`/`PIX`/`NOVI`/`FBPAY`, встречающимися в разделе 8), `expiryTimestamp` (**2**, int64), `incentiveEligible` (**3**, bool), `referralId` (**4**, string), `inviteType` (**5**, int/enum).

`PaymentReminderMessage` (`C43112IrN`):

| Поле | Номер | Тип |
|---|---|---|
| `reminderId` | **1** | string |
| `instanceId` | **2** | string |
| `description` | **3** | string |
| `frequency` | **4** | int/enum |
| `status` | **5** | int/enum |
| `payeeVpa` | **6** | string |
| `payeeJid` | **7** | string |
| `payerJid` | **8** | string |
| `amount` | **9** | `Money` |

`payeeVpa` (поле 6) — это **буквальное поле VPA в протоколе передачи** — прямое подтверждение на уровне proto того, что виртуальные платёжные адреса (VPA) UPI передаются внутри сообщений чата, а не только через побочные каналы GraphQL.

### 2.7 Supporting types (found)

| Тип | Класс | Поля |
|---|---|---|
| `Money` | `C30561DRh` | `value` (**1**, int64), `offset` (**2**, int32 — смещение десятичной точки), `currencyCode` (**3**, string) |
| `MessageKey` | `BD5` | `remoteJid` (**1**, string), `fromMe` (**2**, bool), `id` (**3**, string), `participant` (**4**, string) |
| `PaymentBackground` | `DTJ` | `id` (**1**, string), `fileLength` (**2**, int64), `width` (**3**, int32), `height` (**4**, int32), `mimetype` (**5**, string), `placeholderArgb` (**6**, int32), `textArgb` (**7**, int32), `subtextArgb` (**8**, int32), `mediaData` (**9**, `MediaData` `C30588DSi`), `type` (**10**, enum) |

### 2.8 PaymentInfo — объект статуса транзакции (found)

`DTS` ("PaymentInfo") **не** является типом сообщения чата; он прикрепляется к `WebMessageInfo` (`C30626DTu`, носитель history-sync/companion, документированный в `WA_MESSAGE_SECRETS.md`) как `paymentInfo_` и `quotedPaymentInfo_`. Он представляет текущий известный статус платёжной транзакции и строится из локальной строки транзакции функцией `EKY.A00`:

| Поле | Номер | Тип | Примечание |
|---|---|---|---|
| `currencyDeprecated` | **1** | enum | устаревшее |
| `amount1000` | **2** | int64 | |
| `receiverJid` | **3** | string | |
| `status` | **4** | enum | грубый статус |
| `transactionTimestamp` | **5** | int64 | |
| `requestMessageKey` | **6** | `MessageKey` | |
| `expiryTimestamp` | **7** | int64 | |
| `futureproofed` | **8** | bool | устанавливается, когда локальный объект транзакции отправителя не содержит определяемой валюты/суммы (лазейка для эволюции схемы) |
| `currency` | **9** | string | |
| `txnStatus` | **10** | enum | более детальный статус (на уровне NPCI), отдельный enum от `status` |
| `useNoviFiatFormat` | **11** | bool | устаревший флаг формата отображения Meta Pay/Novi |
| `primaryAmount` | **12** | `Money` | |
| `exchangeAmount` | **13** | `Money` | отображение при конвертации валют |

**Имена** констант enum `status`/`txnStatus` стёрты обфускатором на уровне javalite-байткода (остаются только ординалы и классы `EnumVerifier`); их соответствие ординал→метка — `unknown` в рамках этого прохода. `EKY.A00` читает валюту/сумму локального объекта транзакции и, если они отсутствуют, устанавливает `futureproofed=true` вместо того, чтобы угадывать — найдено в коде (guard `f7fA00.A03 == 5 || !f7fA00.A0N()`).

---

## 3. Мультирейловая архитектура клиента ("payment-common-library")

Код платежей организован как один общий пакет UI/инфраструктуры плюс один пакет на каждый рыночный рейл (found, по структуре пакетов под `com.whatsapp.payments`):

| Пакет | Рейл | Содержимое (found) |
|---|---|---|
| `common` | общий | `p144ui` (универсальные нижние панели платежей, настройки, история транзакций, выбор метода), `pin` (UI ввода PIN, общий для всех рейлов), `paymentkeys`, `compliance`, `care` (CSAT), `qpl` (маркеры логирования качества/производительности) |
| `indiaupi` | India UPI | онбординг, привязка банка/VPA, мандаты, оплата счетов, UPI Lite, QR, восстановление аккаунта — раздел 4 |
| `brazilpay` | Brazil Pix | управление ключами Pix, регистрация биометрии/passkey, CPF |
| `mexico`, `indonesia` | локальные рейлы | присутствуют как пакеты; не исследовались далее факта существования в этом проходе (`unknown` детали) |
| `upr` | рейл-агностический | `nux` (онбординг), `accountmanagement`, `bubble` (панель опций платежа в чате), `shared` (выбор учреждения/типа счёта) — соответствует операциям GraphQL `GenUprPaymentConfig`/`GenUprPaymentConfigForViewer` (раздел 9); расшифровка "UPR" не встречена ни в одной найденной строке (`inferred`: "Universal/Unified Payment Rail") |
| `globalorder`, `remittances`, `split`, `paymentkey`, `productinfra`, `integrity`, `dcp`, `phoenix` | смешанное | присутствуют как пакеты; `integrity` содержит нижнюю панель «friction» для платежей (UI риска/step-up), для `dcp` и `phoenix` в этом проходе не было разрешено ни одного файла на двух верхних уровнях каталога (`unknown`) |

Межрейловый транспорт GraphQL оборачивается `PaymentsMexGraphQlClient$ApiEventCallBuilder` (`com.whatsapp.payments.indiaupi.common.graphql`, несмотря на имя пакета это общая обёртка MEX-вызовов, found) — она оборачивает каждый платёжный MEX-вызов callback'ами логирования QPL/событий start/success/failure (`FDA.BYz`) перед делегированием нижележащему транспорту `InterfaceC17070jD`. Это ближайший аналог «payment common library» на уровне **клиента** в этой сборке: один обфусцированный класс-обёртку вызовов, повторно используемый GraphQL-менеджерами India UPI (`IndiaUpiChangeMpinGraphqlManager`, `IndiaUpiCheckBalanceGraphqlManager`, `IndiaUpiEnrollIncentiveGraphqlManager` и т.д. — found, тот же пакет).

Отдельно для Индии поставляется встроенная **сторонняя** библиотека в принадлежащем NPCI пакете `org.npci.upi.security.*` (не `com.whatsapp.*`) — это и есть «CL» («Common Library»), на которую ссылаются собственные ассеты NPCI формата `.properties` (`version.properties`, `validation.properties`, `cl-*.properties`); она рассматривается в разделе 6. Собственный словарь ассетов NPCI (`salt`, `payInfo`, `controls`, `configuration`, `trust`, `keyXmlPayload`, `keyCode`) точно совпадает со строками ключей bundle, найденными в реализациях `CLRemoteService.Acc`/`Acf` этой сборки (раздел 6) — прямое подтверждение, в этой сборке, более раннего анализа, основанного только на ассетах. Буквальная расшифровка «Common Library» до сих пор не встречена ни в одной строке (`inferred`, теперь подтверждено самими именами классов `CLRemoteService`/`CLResultReceiver`/`CLRemoteServiceImpl`, что является новым доказательством в этом проходе).

---

## 4. Привязка VPA/банковского счёта и онбординг UPI (India-specific)

Имена Activity, восстановленные из `com.whatsapp.payments.indiaupi.*` (found, только факт существования классов и их имена — точный порядок навигации между ними — `inferred` по именам, НЕ прослежен через графы intent в этом проходе):

| Шаг | Activity/Fragment |
|---|---|
| Вход / value props | `IndiaUpiPaymentsValuePropsActivity`, `IndiaUpiPaymentsValuePropsBottomSheetActivity`, `IndiaUpiPaymentsTosActivity` |
| Проверка SIM | `IndiaUpiSimPickerDialogFragment`, `IndiaUpiSimVerificationActivity` |
| Выбор банка | `IndiaUpiBankPickerActivity` (пакет `onboarding`), `IndiaUpiBankAccountPickerActivity` |
| Проверка личности/карты | `IndiaUpiDebitCardVerificationActivity`, `IndiaUpiAadhaarCardVerificationActivity`, `IndiaUpiDobPickerActivity` |
| Привязка устройства | `IndiaUpiDeviceBindStepActivity` (криптография этого шага описана в разделе 6) |
| Настройка PIN | `IndiaUpiPinPrimerDialogFragment` / `...FullSheetActivity`, `IndiaUpiPinHandlerActivity`, `IndiaUpiPinSetUpCompletedActivity`, `IndiaUpiChangePinActivity`, `IndiaUpiForgotPinDialogFragment` |
| Завершение | `IndiaUpiBankAccountAddedLandingActivity`, `IndiaUpiPaymentsAccountSetupActivity` |
| Маппер номер→VPA | `IndiaUpiMapperValuePropsActivity` → `IndiaUpiMapperLinkActivity` → `IndiaUpiMapperPendingActivity` → `IndiaUpiMapperConfirmationActivity`; `IndiaUpiCreateCustomNumberActivity` для нестандартного номера телефона |
| Разрешение контакта по VPA | `IndiaUpiVpaContactInfoActivity`, `IndiaUpiSendPaymentToVpaFragment` |

«Mapper» здесь — собственный термин NPCI для службы каталога телефон↔VPA; четыре Activity `mapper.register.*` реализуют именно этот под-процесс регистрации (found: путь пакета `indiaupi.p148ui.mapper.register`).

GraphQL-операции, релевантные для привязки, с переменными, проверенными по месту вызова (found, из `com.whatsapp.payments.indiaupi.common.graphql.*` и связанных классов `X/*`; полный каталог см. в разделе 9):

| Операция | doc_id | Переменные (found) |
|---|---|---|
| `GetUpiBankList` | `27764018976534565` | `account_type`, `provider_type`, `request` |
| `GetUpiAccounts` | `25691302307224710` | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `GetUpiToken` | `25639185495767704` | `challenge`, `device_id`, `token_type`, `provider_type` |
| `GenCreatePaymentKey` | `24662763616751127` | `add_bank`, `account_holder_name`, `display_name`, `payment_method_type`, `payment_account`, … (шумный суперсет, вызывающий код общий для нескольких операций — см. оговорку в разделе 9) |
| `SetUpiChangeMpin` | `27149786891388216` | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |

---

## 5. Настройка платежей / онбординг (general, межрейловый)

Пакет `upr` реализует рейл-агностическую оболочку онбординга: `UprOnboardingActivity` → `UprOnboardingFragment` → `UprAccountTypePickerBottomSheet` → `AddPaymentMethodFragment` / `UprInstitutionPickerBottomSheet` (found, только имена классов; порядок флоу — `inferred`). Управление аккаунтом после настройки проходит через `UprAccountManagementActivity`/`UprAccountManagementListFragment`, а триггер платежа в чате появляется через `UprPaymentOptionsBottomSheet`/`UprPaymentAccountDetailBottomSheet` (пакет "bubble" — всплывающая панель опций платежа, открываемая из чата).

Серверная конфигурация для этой оболочки запрашивается через `GenUprPaymentConfig` (doc_id `26905963415743456`) и `GenUprPaymentConfigForViewer` (doc_id `37307071662269517`) — found в каталоге doc_id, не проверено независимо по месту вызова в этом проходе (`unknown` переменные).

---

## 6. NPCI "Common Library" (CL): учётные данные, PIN и привязка устройства (India/UPI-specific)

### 6.1 Архитектура (found)

Ввод PIN и обработка банковских учётных данных для India UPI делегируются встроенному AIDL-сервису Android, принадлежащему NPCI, полностью отдельному от собственного кода WhatsApp `com.whatsapp.*`:

```
org.npci.upi.security.services.CLRemoteService      <- AIDL interface
org.npci.upi.security.services.CLResultReceiver     <- AIDL callback interface
org.npci.upi.security.pinactivitycomponent.CLRemoteServiceImpl  <- Android Service, binds the AIDL
org.npci.upi.security.pinactivitycomponent.BinderC48420LDc      <- Binder implementation of CLRemoteService
org.npci.upi.security.pinactivitycomponent.GetCredential        <- PIN-entry Activity launched by the binder
org.npci.upi.security.pinactivitycomponent.Keypad               <- on-screen keypad widget
```

Методы `CLRemoteService` (found, сигнатуры интерфейса): `AQR(otpResultJson)`, `AZO(mode, nonce)` (challenge-response привязки устройства, раздел 6.2), `Acc(...)`/`Acf(...)` (запускают Activity ввода PIN с bundle учётных данных), `BBj(...)` (чтение баланса), `BVz/CRh/CRi(...)` (проверка device-cert/состояния), `BW1()` (проверка целостности устройства).

### 6.2 Привязка устройства и обмен учётными данными (found)

`BinderC48420LDc.AZO(mode, nonce)`:
- режим "initial": строит `deviceId|randomHex|nonce`, RSA-шифрует его встроенным сертификатом NPCI (`MYU.A00`), кодирует в base64, возвращает `"2.3-v1.8|" + ciphertext`. Префикс `2.3-v1.8` — это жёстко закодированная метка версии протокола CL (found, литерал).
- последующий режим: выводит AES-ключ из сохранённой записи учётных данных, шифрует ту же тройку `deviceId|randomHex|nonce` AES/GCM со свежим случайным IV, возвращает `ciphertext|iv` под тем же префиксом версии.

`BinderC48420LDc.Acc`/`Acf` строят `Bundle` с ключами `keyCode`, `keyXmlPayload`, `controls`, `configuration`, `salt`, `payInfo`, `trust`, `languagePref` и запускают с ним Activity `GetCredential` (found, литеральные строковые ключи) — это именно тот словарь, который более ранний анализ, основанный только на ассетах `version.properties`/`validation.properties`, предполагал (`inferred`) для схемы "CL" (`salt`, `payInfo`); код этой сборки подтверждает, что это настоящие ключи runtime-bundle, а не просто плейсхолдеры файлов ассетов.

`C51962N8y` (вспомогательный crypto-класс, используемый во всём binder):
- `A00`: генерирует **пару ключей RSA-2048 внутри Android KeyStore**, `CN=NPCI_CERT`, SHA-512/PSS, требует защищённого аппаратного обеспечения (`isInsideSecureHardware()`, иначе бросает исключение) и (в зависимости от SDK) аутентификации пользователя в коротком окне действия — это ключ привязки устройства.
- `A03`/`A04`: AES/GCM-NoPadding, 128-битный тег, явно переданный вызывающим кодом ключ и IV — шифрование/дешифрование на уровне сессии.
- `A02`: дайджест SHA-256 (хеширование challenge).
- `A01`: расшифровывает строку в формате `ciphertext|iv`, используя сохранённый AES-ключ — согласовано с форматом вывода `AZO` выше.

`BinderC48420LDc.BW1()` выполняет проверку на root/вмешательство (теги сборки, типичные пути бинарника `su`, зонд `which su`) **и** проверяет, что только что сгенерированный RSA-ключ обеспечен StrongBox/TEE; неудачная проверка приводит к тому, что `BW1()` возвращает `false`, что блокирует дальнейший путь выдачи учётных данных выше по цепочке (found: булево значение возврата потребляется логикой `CRh`/`CRi`, не прослежено независимо до сообщения в UI).

### 6.3 Что это значит для содержимого сообщений

Сам MPIN UPI никогда не появляется в сообщении чата или в proto-полях раздела 2 этого отчёта — он полностью обрабатывается внутри Activity `GetCredential` и обменивается с банком-эмитентом/свичем NPCI через описанный выше слой RSA/AES, производя непрозрачный *credential blob*, который в итоге и попадает в переменные GraphQL, такие как `new_mpin`/`old_mpin`/`mpin` в `SetUpiChangeMpin`/`CheckUpiBalance` (раздел 9). То, что строка, фактически переносимая переменной GraphQL, уже зашифрована NPCI (а не является клиентским plaintext, защищённым только TLS), — это **inferred** из назначения предшествующего вызову флоу CL, не подтверждено независимо чтением байтового содержимого места вызова GraphQL.

---

## 7. Уровни шифрования: E2E чата vs NPCI credential blob

В платеже участвуют два независимых уровня шифрования, которые не следует путать (раздел 13):

| Уровень | Защищает | Механизм | Доказательство |
|---|---|---|---|
| E2E сообщений чата | весь proto `Message`, включая каждое поле из раздела 2 (сумма, заметка, VPA в `payeeVpa`, JID, ссылки `MessageKey`) | стандартное шифрование сессии WhatsApp по протоколу Signal/Noise — вне рамок этого отчёта, см. другие RE-отчёты по этому уровню | здесь повторно не выводится |
| NPCI credential/device-binding blob | MPIN, challenge-response привязки устройства, полезные нагрузки риск-проверки, которыми обмениваются с банком-эмитентом через NPCI | RSA-2048 (KeyStore, привязан к TEE, `CN=NPCI_CERT`) для привязки устройства; AES/GCM-128 с явным IV для данных сессии; SHA-256 для хеширования challenge | раздел 6.2, found |

Второй уровень — **India/UPI-specific** и работает ниже/до GraphQL-вызова, никогда внутри proto `Message` чата. Для Brazil Pix или Mexico в этом проходе не найден отдельный платёжный уровень AES/RSA (`unknown` — не исследовалось).

---

## 8. Синхронизация статуса транзакции

### 8.1 Локальный объект и history sync (found)

`F7F` — это объект платёжной транзакции в памяти/локальный объект (получается через `D8X.A00(c13g)` из обобщённой строки сообщения `C13G`). `EKY.A00` преобразует его в `PaymentInfo` уровня передачи (`DTS`, раздел 2.8), прикреплённый к `WebMessageInfo.paymentInfo_`/`quotedPaymentInfo_` для экспорта history-sync/companion.

### 8.2 Статусные обновления от сервера (push) (found, `C24410wL` "PaymentsMessageHandler")

Канал push, видимый клиенту, — это stanza `<notification>` с атрибутом `type`, диспетчеризуемая `PaymentsMessageHandler.A0A`. Наблюдаемые значения `type` и их обработка:

| `type` | Обработка |
|---|---|
| `pay` (с `hash`) | декодируется base64 hash, ставится в очередь как обновление side-list USync (набор протоколов `EnumC21760rz.A0Q`, `C21820s6.A0N`) — повторно использует механизм USync, документированный в `WA_USYNC.md`, вместо того чтобы переносить сам статус |
| `transaction` | разбирает транзакцию через `C24880x6.A07`, логирует `onPaymentTransactionStatusUpdate`, обновляет локальный `F7F`, выводит строку ошибки транзакции в любой подключённый UI (`InterfaceC35566Fb1.BIp`), и (при включённых флагах **1746** + **5049**) может построить карточку order-summary «custom item» для образовательного пуша после платежа |
| `upi` | `consumer_status{value,dhash}` → `onPaymentConsumerStatusUpdate` (India-specific пинг доступности для потребителя, отличается от статуса транзакции) |
| `fbpay` | устаревший пинг доступности Meta Pay, тот же путь обработчика, что у `upi`, но с другим ключом offer-map |
| `account-recovery` | `service=UPI` или `service=BR`; управляет флоу восстановления аккаунта для Индии/Бразилии, под флагами **1644**/**2000** |
| `alert`, `step_up`, `merchant_status`, `merchant-update`, `account`, `kyc-state`, `invite`, `alias`, `age_verification_update`, `document_verification_status` | разные UI-подсказки/compliance-обновления, не статус транзакции |

### 8.3 Учёт синхронизации (found, строки ключей preference)

`payments_all_transactions_last_sync_time`, `payments_block_list_last_sync_time`, `payments_error_map_last_sync_time_millis` — существуют периодические синхронизации полного списка и карты ошибок (потребляющие классы не полностью прослежены в этом проходе; периодичность — `unknown`).

---

## 9. Платёжные операции GraphQL / MEX

### 9.1 Два транспорта, две схемы (found)

| Схема | Транспорт | Количество (в этой сборке) |
|---|---|---|
| `whatsapp` (каталог `www`) | persisted-doc_id GraphQL POST, сам механизм транспорта — `inferred` (не прослежен до места вызова HTTP/IQ в этом проходе) | 81 операция с платёжным тегом |
| `whatsapp_mex` (каталог `mex`) | `w:mex` IQ over the existing stanza connection (`xmlns="w:mex"`) | 1 операция с платёжным тегом: `PaymentsIsAccountRecoverable` (doc_id `27351347491148282`) |

Источник: `assets/whatsapp-android-www_client_persist_ids.json` и `assets/whatsapp-android-mex_client_persist_ids.json`, оба — собственные декларативные ассеты, считываемые во время выполнения (found, самый сильный уровень, не считая перехвата трафика — сами значения doc_id не «tested», лишь подтверждено их наличие в поставляемом ассете).

### 9.2 Показательные операции с переменными, проверенными по месту вызова (found)

| Операция | doc_id | Тип | Переменные |
|---|---|---|---|
| `GetUpiAccounts` | `25691302307224710` | Query | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `CheckUpiBalance` | `37205951525662520` | Query | `credential_fbid`, `device_id`, `mpin`, `seq_no`, `upi_bank_info`, `vpa`, `cl_version`, `device_ssid`, `request` |
| `SetUpiChangeMpin` | `27149786891388216` | Mutation | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |
| `GetUpiBankList` | `27764018976534565` | Query | `account_type`, `provider_type`, `request` |
| `GetUpiToken` | `25639185495767704` | Query | `challenge`, `device_id`, `token_type`, `provider_type` |
| `UpiCreateMandate` / `UpiAcceptMandate` | `26775212245448044` / `26786867597629452` | Mutation | общий вызывающий код (`C42562IuV`): `frequency_rule`, `mandate_no`, `purpose_code`, `recurrence_day`, `recurring_rule`, `ref_id`, `device_id`, `top_up_amount`, `provider_type`, `upi_banks`, `is_revocable`, … |
| `CreateEnrollment` | `34570903025891763` | Mutation | `participant_id`, `device_id` |
| `GenRaisePaymentComplaint` | `27569318002686860` | Query | `complaint_type`, `reason`, `transaction_ref_id`, `user_description` |
| `PaymentsIsAccountRecoverable` (MEX) | `27351347491148282` | Query | не найдено (вероятно `{}`) |

Наличие переменной `mpin` у `CheckUpiBalance`, встречающейся рядом с `cl_version`, согласуется с разделом 6.3: само имя переменной не доказывает, что содержимое предварительно зашифровано, но оно передаётся вместе с явной строкой версии протокола CL, что имеет смысл только если значение происходит из обмена CL.

**Оговорка (found как ограничение метода, а не находка о WhatsApp):** `GenCreatePaymentKey`, `RevokeEnrollment` и `BrSaveCPF` все сводятся к *одним и тем же* общим классам-вызывающим (`C42325Iq9`/`C42327IqB`, `RunnableC42211IoJ`) в каталоге источника, который возвращает каждый строковый литерал рядом с этим вызывающим кодом как «переменные» для всех трёх операций — это приводит к избыточному сбору (например, специфичные для Pix поля, такие как `pix_key`, появляются под операцией с UPI-именем). Длинные списки переменных для этих трёх конкретных операций следует считать шумным суперсетом, а не подтверждённой схемой по операции.

Оставшиеся операции в каталоге из 81 записи (полный список: `UpiPauseMandate`, `UpiResumeMandate`, `UpiRevokeMandate`, `UpiRejectMandate`, `UpiExecuteMandate`, `GetUpiLiteDetails`, `GetUpiP2mConfig`, `GetUpiPurposeLimitingKey`, `GetUpiSmsContentAndVmn`, `PaymentReminderCreate/Get/Cancel/Stop`, `GetBillReceipt`, `GetBillerPlans`, Brazil Pix (`GetPixInfo`, `GetPixBankList`, `GetMerchantPixInfo`, `CompletePixTransaction`, `GenPayWithPixPrecheck`), биометрия/passkey (`Br*Passkey*`, `BrAuthorizeBiometricPayment`), и операции подписки/промо `Wamo*`) каталогизированы со своими doc_id, но не были индивидуально повторно проверены по месту вызова в этом проходе — считать их наличие `found` (это литеральные записи в ассете 2.26.41.6), а точную форму запроса — `unknown`, если не указано иное выше.

---

## 10. Правила автосчитывания OTP от NPCI (India/UPI-specific)

`assets/npci/npci_otp_rules.json` (found, 5 правил) потребляется `org.npci.upi.security.pinactivitycomponent.C0315u` для автоматического извлечения 6-значного OTP из входящего SMS от банка/NPCI во время флоу UPI, исключительно для удобства набора — он не генерирует, не проверяет и не передаёт OTP. Все 5 правил используют общие `sender: ["[a-zA-Z]+"]` (алфавитный короткий код) и `otp: "\d{6}"`; различается только фраза-триггер (`"is your OTP"`, `"OTP is"`, `"one time password is"`, `"is your one time password"`, `".*OTP for Aadhaar.*"`). Вызывающий код может переопределить регулярное выражение количества цифр OTP во время выполнения (`\d{` + `i` + `}`), когда передаёт ненулевую длину. Тело, содержащее `"Aadhaar"`/`"AADHAAR"`, кешируется под ключом SharedPreferences `otp_type_aadhaar`, иначе — `otp_type_bank`.

Этот ассет и потребляющий класс не изменились по характеру по сравнению с более ранним анализом `2.26.34.4`; не были независимо сверены побайтово с 2.26.41.6 в этом проходе (`inferred` непрерывность, не переподтверждено).

---

## 11. Feature flags

Идентификаторы AB-prop считаны непосредственно из `PaymentsMessageHandler` (`C24410wL`, найденные места вызова), если не указано иное. Не найдено ни одного числового ID флага, управляющего самими proto-полями раздела 2 (они безусловны на проводе); все флаги, найденные в этом проходе, управляют *обработкой* server push или UI-подсказок.

| Флаг | Управляет |
|---|---|
| **1458** | удаляет локально кешированный алиас платежа UPI, когда сервер сообщает о его `deregistered` |
| **1644** | право на восстановление аккаунта UPI (`payments-enabled:account-recovery-enabled`) |
| **2000** | право на восстановление аккаунта Brazil Pix (аналогичный гейт для `service=BR`) |
| **1746** + **5049** (оба обязательны) | карточка обучения «custom item»/order-summary после транзакции, показываемая после завершённого платежа (образовательный пуш BIP) |
| **12214** | путь создания FB-пользователя во время восстановления аккаунта UPI (в противовес прямому вызову восстановления) |
| **423** | отслеживание использования приглашения платежей, более старый путь |
| **544** | отслеживание использования приглашения платежей, дополнительный путь (проверяется вместе с 423 через OR) |
| **20869** | проверка allow-list PSP во время обработки уведомления о восстановлении аккаунта; сопутствующий строковый pref `32353` (список PSP, включивших участие, через запятую, считывается через строковый AB prop, не числовой флаг) |

В этом проходе не найдено ID feature flag, специфично управляющих последовательностью Activity онбординга India-UPI (раздел 4) или путём привязки устройства NPCI CL (раздел 6) — `unknown`, не прослежено дальше класса-обработчика выше.

---

## 12. Коды причин ошибки/отказа

### 12.1 Decline/cancel внутри протокола (found)

Как установлено в разделе 2.4, `declinePaymentRequestMessage`/`cancelPaymentRequestMessage` несут **только** ссылку `MessageKey` на исходный запрос — ни enum причины, ни поля свободного текста. Клиент, показывающий «отклонено: недостаточно средств» или подобное, делает это на основании **локального** состояния (собственная копия UI отправителя или сопоставленный более поздний статус `transaction`/`PaymentInfo`, раздел 8), а не на основании чего-либо, передаваемого самим сообщением decline/cancel.

### 12.2 Поля статуса PaymentInfo (found существование, unknown соответствие)

`DTS.status_` (поле 4) и `DTS.txnStatus_` (поле 10) — отдельные поля типа enum (раздел 2.8). Их соответствие ординал→метка не удалось восстановить только из javalite-байткода (имена констант enum стёрты обфускацией классов `Internal.EnumVerifier` в этой сборке) — `unknown`. `futureproofed` (поле 8, bool) — это осознанная лазейка, устанавливаемая, когда локальный объект отправителя не содержит определяемой суммы/валюты, позволяющая получателю на более новом клиенте отрендерить статус, который он иначе не смог бы разобрать.

### 12.3 Карта ошибок от сервера (push) (found ключи pref, потребитель не полностью прослежен)

Ключи preference `payments_error_code`, `payments_error_text`, `payments_error_title`, `payments_error_map_tag`, `payments_error_map_last_sync_time_millis` указывают, что коды ошибок разрешаются по **синхронизируемой с сервером карте** (код → заголовок/текст), а не по фиксированному enum или таблице строк на клиенте. Это означает, что *текст* отказа/ошибки, показываемый пользователю, может меняться со временем/по регионам без обновления приложения. Класс, выполняющий эту синхронизацию, не был идентифицирован в этом проходе (`unknown`).

### 12.4 Отказы уровня NPCI CL (found, без структурированного кода)

`BinderC48420LDc.BW1()` (проверка целостности устройства), `CRH`/`CRh`/`CRi` (проверка device-cert/состояния) — все отказывают **тихо**: возвращают `false`/бросают исключение, без какого-либо кода ошибки, передаваемого через границу AIDL сверх булева значения. Поэтому любое видимое пользователю сообщение об отказе уровня CL конструируется полностью на стороне WhatsApp из булева результата, а не из кода, предоставленного NPCI (`inferred`, согласуется с формой AIDL-интерфейса в разделе 6.1, не имеющего методов, возвращающих код ошибки).

---

## 13. India/UPI-specific vs general — явное разделение

| Находка | Область |
|---|---|
| Proto-поля `sendPaymentMessage`/`requestPaymentMessage`/`declinePaymentRequestMessage`/`cancelPaymentRequestMessage`/split payment/`PaymentInviteMessage`/`PaymentReminderMessage` (раздел 2) | **общее** — одни и те же proto-поля `Message` независимо от рейла; `payeeVpa` (раздел 2.6) — единственное имя поля с UPI-окраской, но само поле безусловно присутствует в схеме |
| Объект статуса транзакции `PaymentInfo` (`DTS`) (разделы 2.8, 8) | **общая** структура; `useNoviFiatFormat` и устаревшие коды сервисов `FBPAY`/`NOVI`/`PIX`/`UPI` показывают, что один и тот же путь объекта/уведомления общий для всех рейлов |
| Пакеты рейлов `indiaupi`, `brazilpay`, `mexico`, `indonesia`, `upr` (раздел 3) | явно разделено по пакетам; `upr`/`common` рейл-агностические, остальные — для одной конкретной страны |
| Привязка VPA, флоу маппера UPI, Activity онбординга (раздел 4) | **India/UPI-only** |
| Библиотека учётных данных/привязки устройства NPCI "CL", криптография RSA/AES, автосчитывание OTP (разделы 6, 7, 10) | **India/UPI-only** — весь этот уровень отсутствует для Pix/Mexico/Indonesia в исследованном коде |
| Каталог doc_id GraphQL (раздел 9) | смешанное — сам каталог охватывает операции UPI, Pix, биометрии/passkey (Бразилия) и рейл-агностические (`Wamo*`, `Gen*`) операции в рамках одной схемы; область каждой конкретной операции определяется её именем/префиксом (`Br*` = Бразилия, `Upi*`/`GetUpi*`/`SetUpi*` = Индия) |
| Типы уведомлений `PaymentsMessageHandler` (раздел 8.2) | смешанное — типы вида `pay`/`transaction`/`alert`/`step_up`/`account` являются общими; тип `upi` и ветки `service=UPI` специфичны для Индии, ветки `service=BR` специфичны для Бразилии |

---

## 14. Заметка о Baileys

Клиенты в стиле Baileys могут конструировать и разбирать типы сообщений из раздела 2 (это обычные protobuf-поля стандартного `Message`) и в принципе могут вызывать doc_id GraphQL `whatsapp`/`whatsapp_mex` с вручную составленными переменными. Они **не могут** осмысленно завершить платёж UPI: обмен MPIN/привязкой устройства из раздела 6 проходит через встроенный, подписанный NPCI нативный компонент Android, привязанный к реальным доверительным отношениям с backend банка/NPCI (RSA-ключ, обеспеченный TEE, `CN=NPCI_CERT`), не имеющим аналога за пределами официального приложения. Поэтому `sendPaymentMessage` от Baileys — это протокольно корректное, но функционально нерабочее сообщение, если оно не сопровождается транзакцией, фактически авторизованной через реальный флоу NPCI.

---

## 15. Случаи ошибок / подводные камни

| Симптом | Причина | Исправление / примечание |
|---|---|---|
| Сообщение decline/cancel не содержит видимой причины на проводе | особенность протокола (раздел 2.4) — существует только обратная ссылка `MessageKey` | не ожидать кода причины от самого сообщения; сопоставлять с более поздним уведомлением `transaction` или локальным состоянием |
| Операция с учётными данными, управляемая `BW1()`, завершается с ошибкой без текста ошибки | у устройства нет StrongBox/TEE или оно имеет root | проявляется на стороне WhatsApp только как булев отказ; невозможно отличить от других отказов CL без дополнительного логирования |
| Переменные GraphQL `mpin`/`new_mpin`/`old_mpin` выглядят как plaintext в дампе места вызова декомпилированного кода | они производятся обменом CL (раздел 6.3), а не вводятся напрямую в вызов GraphQL | не предполагать передачу PIN в открытом виде без прослеживания реальных байтов во время выполнения — этот отчёт не заявляет, что это было сделано |
| `GenCreatePaymentKey`/`RevokeEnrollment`/`BrSaveCPF` показывают огромные списки переменных с Pix-окраской | избыточный сбор общего класса-вызывающего кода при извлечении каталога doc_id (раздел 9.2) | считать шумным, проверять по каждому полю перед тем, как на него опираться |
| Значения enum `txnStatus`/`status` невозможно назвать | обфусцированный `EnumVerifier` стирает имена констант | требует сопоставления строк во время выполнения (строки ресурсов UI, сопоставленные с ординалами), не выполнено в этом проходе |

---

## 16. Ключевые различия

| Не путать | Детали |
|---|---|
| E2E сообщения чата vs NPCI credential blob (раздел 7) | два отдельных криптографических уровня; второй — India/UPI-only и находится полностью за пределами proto `Message` |
| `DTS` PaymentInfo vs четыре типа платёжных сообщений чата | `DTS` — объект history-sync/статуса (`WebMessageInfo.paymentInfo_`), никогда самостоятельное отправляемое сообщение чата |
| `status` vs `txnStatus` на `DTS` | два независимых enum, разная степень детализации, оба непрозрачны на уровне ординала в этой сборке |
| схема `www`/`whatsapp` doc_id vs схема `mex`/`whatsapp_mex` doc_id | разный транспорт (persisted-doc_id GraphQL POST vs `w:mex` IQ); почти все платёжные операции в этой сборке находятся на стороне `www`/`whatsapp` |
| рейл-агностический онбординг "UPR" vs онбординг India UPI | UPR (`com.whatsapp.payments.upr`) — более новая, универсальная оболочка; специфичные для Индии Activity онбординга `indiaupi` (раздел 4) — отдельный, более старый и намного более крупный флоу, всё ещё присутствующий параллельно в 2.26.41.6 |
| NPCI "Common Library" (`org.npci.upi.*`) vs собственный код WhatsApp `com.whatsapp.payments.*` | первое — встроенный сторонний компонент со своей собственной поверхностью AIDL; код WhatsApp только запускает его и считывает в ответ непрозрачную строку/bundle |

---

## 17. Полный флоу (India UPI, случай отправки денег)

```
[Payer chat]                 [WhatsApp client]                    [NPCI CL component]            [NPCI / Issuer bank]
     │ tap "Pay"                    │                                      │                             │
     ▼                              ▼                                      │                             │
 open IndiaUpiSendPaymentActivity → IndiaUpiSendPaymentToVpaFragment       │                             │
     │                              │ amount/VPA/note entered              │                             │
     │                              ▼                                      │                             │
     │                     CLRemoteService.Acc(keyCode, keyXmlPayload,     │                             │
     │                       controls, configuration, salt, payInfo, …) ──►│                             │
     │                              │                                GetCredential activity (PIN pad)    │
     │                              │                                      │ user enters MPIN            │
     │                              │                             AZO(): RSA/AES challenge-response ────►│
     │                              │                                      │◄──── signed/verified ────── │
     │                              │◄──── opaque credential blob ─────────│                             │
     │                              │                                      │                             │
     │                     build RequestPaymentMessage / SendPaymentMessage (section 2)                  │
     │                              │ amount, note, requestMessageKey, background                        │
     │                              ▼                                                                     │
     │                     chat E2E encrypt, send as normal <message>                                    │
     │                              │                                                                     │
     │                     CheckUpiBalance / SetUpiChangeMpin / mandate GraphQL op ─────────────────────► │
     │                              │          (credential_fbid, device_id, mpin blob, vpa, seq_no)       │
     │                              │◄──────────────── result / error (section 12.3 error map) ────────── │
     ▼                              ▼                                                                     │
[Payee chat]            server pushes <notification type="transaction"> ──────────────────────────────── │
     │                              │  PaymentsMessageHandler.A0A updates local F7F,                      │
     │                              │  EKY.A00 builds PaymentInfo (DTS) for history sync                  │
     ▼                              ▼
 status shown in chat        transaction row updated, payments_all_transactions_last_sync_time bumped
```

---

## 18. Неизвестное

| Тема | Причина |
|---|---|
| Номера полей верхнеуровневого `Message` для `splitPaymentMessage`, `splitPaymentUpdateMessage`, `paymentReminderMessage` | декодирование info-строки не было проведено достаточно далеко в этом проходе; собственные поля под-сообщения (раздел 2.5/2.6) не затронуты |
| Соответствие меток enum `DTS.status_`/`txnStatus_` | обфусцированный `EnumVerifier`, имена констант стёрты |
| Точный механизм транспорта для вызовов persisted-doc_id GraphQL схемы `whatsapp` (`www`) | не прослежено до места вызова HTTP/IQ в этом проходе; повсюду помечено как `inferred` |
| Класс(ы)-потребители карты ошибок `payments_error_map_*`, синхронизируемой с сервером | ключи pref найдены, класс чтения/записи не идентифицирован |
| Содержимое пакетов `mexico`/`indonesia`/`dcp`/`phoenix` | существование пакета подтверждено, содержимое не исследовано |
| Несут ли переменные GraphQL `mpin`/`new_mpin`/`old_mpin` уже зашифрованный NPCI blob, или дополнительная защита применяется только на уровне TLS | выведено (`inferred`) из назначения флоу CL, не подтверждено осмотром реального байтового содержимого во время выполнения |
| ID feature flag (если таковые есть), управляющие последовательностью онбординга India-UPI или самим путём привязки устройства CL | не найдено в исследованных классах |
| Побайтовая непрерывность `npci_otp_rules.json` и ассетов `.properties` CL между `2.26.34.4` (предыдущий анализ) и `2.26.41.6` | не сверено повторно; потребляющие классы и словарь ключей runtime-bundle были независимо переподтверждены в 2.26.41.6, сами байты ассета — нет |
| Реальное поведение трафика / живой транзакции | только статический анализ, перехват трафика не выполнялся, живая транзакция не проводилась |
