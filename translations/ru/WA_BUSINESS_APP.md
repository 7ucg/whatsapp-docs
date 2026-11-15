<!-- src-sha1: 349e8112a4dcc4567ce203cf21c4c37e5bb47173 -->
# WhatsApp Business App — Full RE Report
**Версия:** 2.26.45.7 (Business) vs 2.26.45.10 (consumer) | **Дата:** 2026-11-15
**Область:** структурное различие между APK WhatsApp Business (`com.whatsapp.w4b`) и потребительским WhatsApp (`com.whatsapp`) — корневые пакеты, эксклюзивные для Business, стек React Native, различие нативных библиотек, асимметрия каталога doc_id GraphQL/MEX/`www`/`facebook-schema`, различие разрешений; разграничение с WhatsApp Business API/Cloud API и с Managed Account

---

## 1. Обзор

WhatsApp Business — это отдельное приложение (`com.whatsapp.w4b`), а не переключение режима внутри потребительского WhatsApp. Оно делит ядро протокола Signal, транспорт Noise и большую часть UI чата с потребительским WhatsApp, но поставляется с собственным набором пакетов для функций, доступных только бизнесу, и включает зависимость — полноценный runtime React Native — которую потребительское приложение не несёт вообще.

Этот отчёт охватывает только **само приложение**, сравниваемое как APK с потребительским WhatsApp. Это отдельная ось от двух других "бизнес"-смежных концепций, уже документированных в этом репозитории:

| Концепция | Что это | Отчёт |
|---|---|---|
| **Приложение WhatsApp Business** (этот отчёт) | Отдельный клиентский APK (`com.whatsapp.w4b`), который бизнес устанавливает на телефон, со своим UI для каталога, меток, сообщений об отсутствии, рекламы | здесь |
| **WhatsApp Business API / Cloud API** | Серверная инфраструктура, которая хостит/передаёт сообщения бизнес-номера, используется вместо или вместе с приложением Business; сигнализируется в любом клиенте только через поля сертификата verified-name (`host_storage`, `actual_actors`, префикс эмитента `smb:`/`ent:`) и баннеры совместного существования `business_state_id` | `WA_MANAGED_ACCOUNT.md` §9 |
| **Managed Account** | Собственный потребительский аккаунт несовершеннолетнего, под супервизией родителя/опекуна (`ManagedAccount*`/PAA/PMA/PMTA); не связано ни с одной из бизнес-концепций, для бизнес-случая не существует метки "managed" | `WA_MANAGED_ACCOUNT.md` §1-8 |

Один бизнес может комбинировать все три: запустить приложение Business на устройстве, делегировать часть своего трафика провайдеру Cloud API (совместное существование), при этом аккаунт собеседника в чате остаётся обычным потребительским аккаунтом. См. §9 о том, как они взаимодействуют.

Источник доказательств: статическое сравнение пакетов/ассетов/манифеста между `WA-Business_2.26.45.7.apk` и `WhatsApp_2.26.45.10.apk` (текущая пара бета-версий на момент сравнения, не сравнение версии с версией). Полный декомпил jadx не выполнялся ни для одной из сторон (жёсткое правило безопасности); все находки ниже — на уровне дерева smali apktool, JSON ассетов и реконструированного манифеста. Уровни соответствуют контракту доказательств brain `found`/`inferred`/`unknown`.

---

## 2. Различие на уровне пакетов — found

Сравнение каждой директории под `smali*/` в каждом дереве apktool: у Business 4281 уникальная директория-путь пакета (15 деревьев `smali_classesN`), у потребительского — 3710 (14 деревьев). 853 пути существуют только в Business, 282 — только в потребительском. 45 корневых пакетов верхнего уровня `com/whatsapp/*` эксклюзивны для Business (сама корневая директория отсутствует в потребительском, не только подпуть).

### 2.1 Корневые пакеты, эксклюзивные для Business, по кластерам функций

| Кластер | Корневые пакеты | Примечания |
|---|---|---|
| Сообщения об отсутствии / приветствие / быстрый ответ | `businessaway`, `businessgreeting`, `businessquickreply`, `businessmissedcallfollowup` | основные функции автоответа SMB |
| Метки / агенты / назначение чата | `chatassignment`, `authagent`, `authagentfeaturecontrol`, `smbmultideviceagents`, `businesscontactmanager`, плюс `lists/smb/labels` (подпуть; корень `lists` общий) | места агентов и редактирование меток |
| Настройка профиля / верификация | `businessregistration`, `protectedbusinessaccounts`, `metaverified` | |
| Каталог/заказы (сторона управления) | `ordermanagement` | сам просмотр/редактирование каталога (`catalog`, `businessproduct`, `businesscollection`) — **общий** — см. §2.2 |
| Реклама / интеграция Meta Ads | `ads4ads`, `adscreation`, `adcreationinterfaces` | см. §3 про связь с React Native |
| Биллинг / подписки (уровни API) | `metabilling`, `metabillingui`, `subscription`, `billingui` | |
| Совместное существование приложения и API | `coexistence`, `connectedaccounts`, `linkedaccounts`, `dynamicaudience` | мосты к стороне Cloud API, §9 |
| Бизнес-агент Meta AI | `bizai`, `genai`, `maiba` | |
| Бизнес-инструментарий / соответствие | `businesstools`, `businessinsights`, `rapidfeedbacksurvey`, `reportblocksharing`, `statistics`, `integrityenforcementsinfra`, `eligibilitychecker`, `googleeligibilityapi`, `smb`, `smbauth`, `waloginmbs`, `marketingmessage`, `marketingmessagemanagement`, `mediatemplates`, `bizdatasharing`, `bizgallerypicker`, `bizmedia` | |

### 2.2 Общие корни с подпакетами, эксклюзивными для Business

Некоторые корни существуют в обоих приложениях, потому что потребитель может просматривать/потреблять данные бизнес-стороны, но подпакеты редактирования/управления — только в Business:

- `com/whatsapp/businessprofile/` — общий корень; `businessprofileaddress`, `businessprofilecategory`, `businessprofileedit` (+ `boostmedia`, `businessprofilecompleteness`), `businessvertical`, `businesscompliance/smb/...` — только в Business. Потребительская версия сохраняет только подпакеты просмотра профиля на стороне чтения.
- `com/whatsapp/lists/` — общий корень (модель данных/UI меток, `labelitem` в обоих); подпакет **редактирования** меток `lists/smb/labels` — только в Business.
- `catalog`, `businessproduct` (+ `businessproductlist`), `businesscollection` — общие корни, подтверждённо присутствующие в дереве smali потребительского приложения как UI **просмотра** каталога/продукта, отображаемый при просмотре бизнес-чата.

Итоговая форма: просмотр каталога/продукта, просмотр бизнес-профиля и отображение меток — общие; редактирование каталога/профиля, сообщения об отсутствии/приветствия/быстрого ответа, редактирование меток, авторизация агента/мультиустройства, создание рекламы и совместное существование с Cloud API — эксклюзивны для Business.

### 2.3 Пакеты, эксклюзивные для потребительского приложения — found, без кластеризации

282 пути существуют только в потребительском приложении. Выборочная проверка не выявила тематического кластера, сопоставимого по размеру с набором, эксклюзивным для Business; основная масса — вложенные дочерние элементы меньшего числа корней, эксклюзивных для потребителя. Глубоко не исследовано — перечислено как открытый пробел в §8.

---

## 3. Стек React Native — found, эксклюзивно для Business

Неожиданная находка: Business поставляется с полным стеком React Native, отсутствующим в потребительском приложении на уровне пакетов, а не просто как дополнительный модуль функции.

| Пакет | Business | Потребительский |
|---|---|---|
| `com/facebook/react/*` (bridge, fabric, animated, devsupport, turbomodule, …) | 88 директорий | 0 |
| `com/facebook/catalyst/*`, `com/facebook/fbreact/*` (модули-мосты RN, i18n, safe-area) | присутствует | отсутствует |
| `com/facebook/hermes/*` | 3 директории | 1 директория — только разрозненная ссылка, нет `com/facebook/react` в пару к ней, т.е. не рабочий runtime RN |
| `com/caverock/androidsvg`, `com/crossapp/graphql/facebook/*` | присутствует | отсутствует |

Подтверждено на уровне нативных библиотек (§4): `libreactnative.so` (runtime RN), `libappmodules.so` (нативный загрузчик JS-бандла RN) и `libimagepipeline.so` (Fresco, конвейер изображений RN) — файлы `.so`, эксклюзивные для Business.

**Inferred**, не подтверждено: некоторая поверхность, доступная только в Business — наиболее вероятно создание рекламы (`adscreation/lwi/react/*` имеет подпакет `react` прямо внутри `lwi`), Meta-биллинг или онбординг совместного существования — реализована как встроенные экраны React Native, а не нативный UI Android. Какая конкретная функция(и) использует стек RN не подтверждено одними только именами пакетов; требовался бы точечный декомпил классов `adscreation/lwi/react/activity`. Это самая очевидная оставшаяся "удивительная зависимость": бизнес-приложение для обмена сообщениями встраивает кросс-платформенный JS UI runtime, судя по всему, только для одного или нескольких экранов (создание рекламы — наиболее вероятное совпадение по названию).

---

## 4. Различие нативных библиотек — found

Сравнение `superpack_index.csv` (собственный манифест библиотек контейнера SUPERPACK_OB) между выводами реконструкции двух приложений:

| | Количество |
|---|---|
| Проиндексировано библиотек в потребительском | 84 |
| Проиндексировано библиотек в Business | 89 |

**Эксклюзивно для Business (5):** `libappmodules.so`, `libimagepipeline.so`, `libreactnative.so`, `libwacomponents.so` (название предполагает библиотеку мостовых компонентов RN авторства WhatsApp, не стоковый RN), `libzstddecoder.so` (вероятно декомпрессия бандла/ассетов RN).

**Эксклюзивно для потребительского приложения:** ни одной — каждое имя библиотеки потребительского приложения также присутствует в индексе Business.

6 библиотек, декомпилированных device-oracle, общих для обоих приложений (`libwhatsapp.so`, `libwhatsappmerged.so`, `libwasafe.so`, `libvoprf-ed25519.so`, `libohai.so`, `libcurve25519.so`), идентичны между двумя приложениями (одинаковые размеры, одинаковое число символов/экспортов) — ядро протокола Signal/аттестации/целостности клиента не затронуто сборкой Business. Стек React Native + Fresco эксклюзивен для Business как на уровне пакетов Java/Kotlin, так и на уровне нативных библиотек — согласованная находка на двух уровнях.

---

## 5. Различие каталога doc_id GraphQL / MEX / `www` / `facebook-schema` — found

Каждое приложение поставляется со своим каталогом doc_id `assets/whatsapp-android-<schema>_client_persist_ids.json`, прочитанным прямо из дерева ассетов, декодированного apktool (декомпил не требуется).

| Схема | Операции Business | Операции потребительского | Только в Business | Только в потребительском |
|---|---|---|---|---|
| `mex` | 242 | 242 | 0 | 0 — идентичный набор |
| `wamo` | 22 | 22 | 0 | 0 — идентичный набор |
| `www` | 237 | 244 | 4 | 11 |
| `facebook-schema` | 224 | 17 | 215 | 7 |

### 5.1 `mex` и `wamo` — идентичны между приложениями

Оба каталога имеют совершенно одинаковые имена операций в обоих APK (разность множеств пуста, не просто равна по количеству). Business не несёт специфичной для Business поверхности MEX/GraphQL на этом уровне схемы — он полностью разделяет каталог потребительского приложения.

### 5.2 `www` — небольшая асимметрия

- Только в Business (4): `BPAccessTokenAndSessionCookiesMutation`, `CatkitTypeaheadProxy`, `WACreateEnforcementAppeal`, `WAGetEnforcementAppealStatus`.
- Только в потребительском (11): `WaAutofillAcknowledgeWalletTerms`, `WaAutofillFetchContactData`, `WaAutofillFetchSettings`, `WaAutofillSaveContactData`, `WaAutofillUpdateNegativeInteraction`, `WaAutofillUpdateSaveCvv`, `WaCreateLabyrinthBackupMutation`, `WaDeleteLabyrinthAccountMutation`, `WaDeleteLabyrinthThreadsMutation`, `WaRotateLabyrinthEpochMutation`, `WaUploadLabyrinthMessagesMutation`.

Потребительское приложение несёт собственные операции личных платежей/автозаполнения (`WaAutofill*`) и сквозного резервного копирования чата (`WaCreateLabyrinthBackupMutation` и т.д. — система резервного копирования чатов WhatsApp, внутренне называемая "Labyrinth"), которых нет в Business; Business несёт пару операций апелляции на принудительные меры в отношении аккаунта и сессии/typeahead, которые не нужны потребительскому приложению.

### 5.3 `facebook-schema` — главная находка: 215 операций только в Business

Именно здесь живёт реальная специфичная для Business поверхность GraphQL — не в `mex`/`wamo`, которые побайтово идентичны между двумя приложениями. Business несёт 224 операции в этой схеме против 17 у потребительского приложения; 17 операций потребительского приложения — не связанные операции личных платежей/коммерческих nonce (`AcDcCreateCanonicalDigitalCommerceNonce`, `WaAutofillAddPayCreditCard`, `WaGetServerEncryptionKey` и т.д.), которых нет в Business.

215 операций, доступных только в Business, кластеризованы по имени (описательная группировка, выведенная из статического анализа, не подтверждённая функциональная таксономия):

| Кластер | Примеры операций |
|---|---|
| База знаний / AI-ответ / симуляция ("коуч") | `FetchAIAbilities`, `KnowledgeRepoFetchV2`, `UpdateAIKnowledge`, `DeleteAIKnowledge`, `CoachSimulationMessage`, `CoachSuggestedReply`, `StartSimulation`, `SubmitSimulationFeedback`, `FetchSuggestedReply`, `MarkSuggestedReplyUsed` |
| Бизнес-агент Meta AI / MAIBA | `MAIBAOnboarding`, `MAIBACompleteParallelOnboarding`, `Maiba1pCalendarEvents`, `MaibaGetCurrentCatalog`, `MaibaDownloadLeadGenFlow`, `MetaAIBizAgentWAAIHome`, `MetaAIBizAgentWACoachingMutation` |
| Lead-gen / встречи | `CreateLeadGenFlow`, `GetLeadGenFlowLeads`, `UpdateLeadStages`, `CreateAppointmentFlow`, `GetAppointmentPrefill`, `GetDefaultAvailability` |
| Auth agent / SMB multi-agent / вход | `AuthAgentCompanyInfoQuery`, `AuthAgentFeaturePolicyQuery`, `AddSmbAgentAndCoexQr`, `SmbRegistrationInit`, `WALoginClaimAuthChallenge`, `WALoginConfirmAuthChallenge` |
| Совместное существование приложения и Cloud API | `CoexUnifiedOnboarding`, `CoexMultiAppEligiblity`, `CoexAppsAndServicesOffboardProduct`, `CoexCompanionPairingStatusCallback`, `CoexistenceQRCodeFetch` |
| Click-to-WhatsApp реклама (CTWA) | `CTWACreateLookAlikeAudienceMutation`, `CTWAPreviousAdsRecommendationQuery`, `CtwaLinkedMediaQuery`, `CtwaNativeUploadAdMediaMutation` |
| Рекламный аккаунт / допуск | `AdAccountEligibilityCheckerQuery`, `OnboardToWhatsAppAdAccount`, `WhatsAppBizFetchAdDefaults`, `WhatsAppBizGetEstimatedAdReach` |
| Управление каталогом (сторона записи) | `WhatsAppCatalogAddProduct`, `WhatsAppCatalogEditProduct`, `WhatsAppCatalogDeleteProduct`, `WhatsAppCatalogCreateCollections`, `WhatsAppCatalogProductVisibilityUpdate` |
| Маркетинговая рассылка ("Pro") | `BusinessBroadcastProCampaignContent`, `BusinessBroadcastProCustomAudiencesQuery`, `BusinessBroadcastProInsights`, `WAMarketingMessagesCustomAudienceCreateMutation` |
| Менеджер контактов / профили клиентов | `BizContactManagerProfiles`, `ContactManagerAccessState`, `WACustomerProfiles`, `UpsertWACustomerProfiles`, `DeleteWACustomerProfile` |
| Биллинг / подписка (уровни, оплачиваемые Meta) | `FetchSubscriptionState`, `FetchSubscriptionStateV2`, `WaSmbMetaOneTierPaymentPrefetchTargetQuery`, `AcceptBizAiPaymentTerms` |
| Экспорт истории чата / интеграция 3P (GDrive) | `FetchChatHistoryExportStatus`, `GDriveGetFiles`, `UploadHistoricalMetadata`, `Disconnect3PPartners` |
| Привязанный аккаунт IG/FB | `SetIGDisplayContactInfoMutation`, `WAFBPageProfileImportGet`, `WhatsAppBusinessLinkedAccountsQuery` |
| Инфраструктура QE/feature-flag (бизнес-сторона) | `CheckQEBool`, `WaFetchQEBool`, `WaFetchQEString`, `WhatsAppGraphQLCheckQE` |

Полный список из 215 имён воспроизводим из файлов ассетов двух приложений, упомянутых выше; здесь не воспроизводится буквально. **Значения** doc_id для `www`/`facebook-schema` (а не только имена операций) не сравнивались — общее имя операции в принципе может нести разный doc_id между двумя приложениями; не проверено.

---

## 6. Различие разрешений — found

Из инвентаризации манифеста каждого приложения:

| | Эксклюзивно для Business | Эксклюзивно для потребительского |
|---|---|---|
| Разрешение | `com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` | `android.permission.RECEIVE_SMS` |

Оба приложения дополнительно запрашивают разрешения на само-broadcast/maps собственного пакета под соответствующими именами пакетов (`com.whatsapp.w4b.*` vs `com.whatsapp.*`) — это эквиваленты друг друга с изменённым именем пакета, не функционально новое, и не учтены выше.

Business не запрашивает приём SMS. **Inferred**, не подтверждено кодом: согласуется с тем, что аккаунты Business чаще регистрируются через путь Cloud/Business API, а не полагаются на автоматическое чтение SMS на устройстве для OTP — но это рассуждение не проверено по коду потока регистрации в этом проходе.

---

## 7. Примечание Baileys / velowa

Почти ничто из поверхности этого отчёта не достижимо из обычного клиента WhatsApp Web (velowa или любой реализации протокола Noise/multi-device):

- Каталоги `mex`/`wamo` **идентичны** потребительским — ничего специфичного для Business там не добавляется; любой клиент WA Web уже имеет те же doc_id.
- 215 операций `facebook-schema` (§5.3) — это настоящая специфичная для Business поверхность GraphQL, но это потоки, управляемые UI самого **приложения** Business (редактирование каталога, создание рекламы, коучинг/MAIBA, онбординг совместного существования, авторизация агента), закрытые состоянием собственного аккаунта приложения Business и, в нескольких кластерах, целиком серверной стороной WhatsApp Business API/Cloud API (совместное существование, биллинг, рекламные аккаунты). Клиент WA Web, говорящий на обычном протоколе multi-device, не имеет пути к большинству из них — это вообще не функции протокола передачи данных, это вызовы REST/GraphQL, которые собственный UI приложения Business делает к бэкенду бизнес-платформы Meta.
- Поверхность React Native для создания рекламы (§3) — только UI Android-приложения (встроенные экраны JS, рендерящиеся `libreactnative.so`); ничто в ней не идёт через протокол передачи чата.
- Единственная область с какой-либо релевантностью для протокола multi-device — совместное существование (`coexistence`/`connectedaccounts`/`linkedaccounts`), представление устройства/сессии которого покрыто существующей документацией в `WA_MANAGED_ACCOUNT.md` §9.3 и `WA_LINKED_DEVICE_PAIRING.md` (тип аккаунта `HOSTED`, id устройства 99, `platformType` 23/25-27) — эта часть уже настолько далеко, насколько может дойти взгляд только со стороны клиента.

Итого: этот отчёт полезен для понимания того, что *содержит* APK Business, но не как источник новой поверхности протокола передачи данных для velowa.

---

## 8. Что этот отчёт НЕ проверил

| Пробел | Почему | Нужное продолжение |
|---|---|---|
| Различие proto/протокола передачи данных между двумя приложениями | `unknown`, не предполагается идентичным. Этап proto пайплайна реконструкции не выполнялся ни для одной из сборок (`protoc_ok=False` с обеих сторон); более глубокая экстракция proto, использованная в другом месте этого прохода обновления версии (1089 сообщений, `protoc` exit 0), выполнялась только против уже существующего декомпила jadx потребительского приложения — эквивалентного декомпила для `com.whatsapp.w4b` в этом рабочем пространстве не существует. Для его получения нужен полный прогон jadx по APK, запрещённый жёстким правилом безопасности этой сессии (ранее уже приводил к сбою машины анализа). Отсутствие доказательства — не доказательство отсутствия. | Точечная экстракция jadx по одному классу или одному DEX, ограниченная только классами сообщений/proto (не полный декомпил APK) |
| Какая функция(и) рендерится через стек React Native, эксклюзивный для Business | Только корреляция по имени пакета/библиотеки (`adscreation/lwi/react/*` — наиболее вероятное совпадение по названию, но не подтверждено) | Точечный декомпил классов `com/whatsapp/adscreation/lwi/react/*` |
| Кластер пакетов, эксклюзивных для потребительского приложения (282 пути) | В этом проходе тематически не кластеризован — более низкий приоритет, учитывая фокус задачи на поверхности, эксклюзивной для Business | Выделенный проход по различию из 282 путей |
| **Значения** doc_id `www`/`facebook-schema` | Сравнивались только **имена** операций; общее имя может нести разный doc_id в каждом приложении | Сравнение на уровне значений обоих JSON-файлов ассетов |
| Полный список операций `facebook-schema` из 215 / переменные / формы ответов | Кластеризация только по ключевому слову имени; восстановление точки вызова или поля ответа не предпринималось | Целевая трассировка точки вызова по каждому кластеру, как сделано для MEX-операций в других отчётах |

---

## 9. Ключевые различия

| A | B |
|---|---|
| **Приложение** WhatsApp Business (`com.whatsapp.w4b`) — отдельный APK со своим набором пакетов, этот отчёт | WhatsApp Business **API / Cloud API** — серверный хостинг/передача сообщений бизнес-номера; нет отдельного клиентского APK, сигнализируется в любом клиенте через поля сертификата verified-name (`WA_MANAGED_ACCOUNT.md` §9) |
| Пакеты `coexistence`/`connectedaccounts`/`linkedaccounts` приложения Business — собственный UI приложения для соединения с провайдером Cloud API | Баннеры совместного существования `business_state_id`, видимые клиентом **собеседника** (потребительским или Business), когда бизнес-номер одновременно использует приложение и API (`WA_MANAGED_ACCOUNT.md` §9.2) |
| Managed Account (`ManagedAccount*`, PAA/PMA/PMTA) — собственный **потребительский** аккаунт несовершеннолетнего под родительской супервизией | Приложение Business — аккаунт бизнеса, совершенно не связанная концепция, нет пересечения кода/схемы |
| Каталоги doc_id `mex`/`wamo` — побайтово идентичные наборы имён операций в обоих приложениях | Каталог doc_id `facebook-schema` — 215 операций существуют только в Business; именно здесь фактически живёт специфичная для Business поверхность GraphQL |
| **Просмотр** каталога/профиля/меток — общие корневые пакеты, присутствуют и в потребительском (так что потребительский пользователь может просматривать каталог бизнеса) | **Редактирование** каталога/профиля/меток — корневые пакеты, эксклюзивные для Business (сторона записи, доступная только самому бизнесу) |

---

## 10. Итог

Подтверждает ожидаемую форму на входе — каталог, бизнес-профиль/верификация, метки, быстрые ответы/приветствие/сообщения об отсутствии, кластер авторизации агента/мультиустройства в коде, доступном только в Business, с половиной просмотра/отображения каждой функции, общей с потребительским приложением — и добавляет две находки, которые не предполагались изначально:

1. **`facebook-schema` — это место, где фактически живёт реальная специфичная для Business поверхность GraphQL** (215 операций только в Business: AI-коуч/база знаний, MAIBA, lead-gen, auth-agent, совместное существование, реклама CTWA, операции записи каталога, маркетинговая рассылка, биллинг), а не основные каталоги `mex`/`wamo`, которые представляют собой побайтово идентичные наборы имён операций между двумя приложениями.
2. **Business поставляется с полным стеком React Native + Fresco** (`com.facebook.react.*`, `libreactnative.so`, `libimagepipeline.so`, `libwacomponents.so`), полностью отсутствующим в потребительском приложении, как на уровне пакетов, так и на уровне нативных библиотек — наиболее вероятно обслуживая экраны создания рекламы, но точная граница функции не подтверждена без точечного декомпила.

Различие proto/протокола передачи данных не удалось выполнить в этом проходе (§8) и зафиксировано как unknown, а не как предполагаемо идентичное.
