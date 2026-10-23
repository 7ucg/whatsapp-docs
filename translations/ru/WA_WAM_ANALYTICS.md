<!-- src-sha1: c6955a2c041a57de36c902dfa247b0b65dc0b530 -->
# WhatsApp WAM Analytics — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** Android-телеметрия WAM ("WhatsApp Metrics"), модель событий (id событий, поля, каналы REGULAR / REALTIME / PRIVATE / channel 3), Java-конвейер логирования, сэмплирование и веса событий, нативный рантайм (`libwhatsapp.so`), общие атрибуты, буферы на диске, wire-формат WAM, регулярная выгрузка (`w:stats` IQ), приватная выгрузка (IQ с credential + отдельный транспорт), `wam_daily` и ежедневный cron, private-stats id и их ротация, обработка приватности, feature flags, заметные семейства событий, сравнение с Baileys, что остаётся неизвестным

---

## 1. Что такое WAM в этой сборке

WAM — клиентский конвейер метрик: типизированные события создаются в Java (или конвертируются из нативной статистики звонков), проходят сэмплирование, передаются нативному рантайму, который сериализует их в бинарные буферы в `files/wam/`, и выгружаются на сервер. Это только исходящая телеметрия. От неё ничто в chat-протоколе не зависит. Все утверждения основаны на статическом анализе декомпилированного APK (`versionCode 264100600`), нативных строках `libwhatsapp.so` и структуре файлов буферов, найденных в каталоге данных приложения этой сборки. Tiers: **found** = прочитано в коде или в файле буфера, **inferred** = выведено, **unknown** = статически не определяется. Обфусцированные имена уникальны для каждой сборки и заново определены в 2.26.41.6 по стабильным строкам (строки логов, имена `wam_*` событий, значения атрибутов IQ).

| Сущность | Имя в 2.26.41.6 | Роль |
|----------|-----------------|------|
| Базовый класс события | `C0Fc` | `code`, `samplingRate`, `bufferChannel`, `psId`; абстрактные `getFieldsMap()` (числовые id), `getFieldsMapForFalco()` (имена), `getEventNameForFalco()`, `validate()` |
| Кортеж сэмплирования | `C036300x` | уровни весов; `A00` — вес, используемый сэмплером |
| Резолвер сэмплирования | `C0Fg` + `C06580Fh` | переопределение веса события из prefs `field-stats-events-sampling` |
| Логгер (фасад WAM-рантайма) | `C06650Fo` (`InterfaceC06640Fn`); `C40098Hdb` передаёт события ему и Java-логгеру Falco `C40099Hdc` | `CNW` отправка, `CNI` отправка с сэмплированием, `CXW` flush, `CUj` сброс, `CXZ` flush с ожиданием (2500 ms); init в `RunnableC29323CoA` case 33 |
| JNI-мост | `com.whatsapp.wamsys.JniBridge` | `jvidispatch*` Java в native, `jnidispatch*` native в Java |
| Общие атрибуты | `C06590Fi` (`CYl(value, attrId, channel)`), init в `RunnableC29340CoR` case 0 | глобальные атрибуты по каналам |
| Обработчик AB-props | `C28894Cgv` | разбирает `<props>`, включая `event_code` / `sampling_weight` |
| Ежедневное событие | `C0Fp` (`wam_daily`, id 1158) | состояние устройства и приложения |
| Ежедневный cron | `C28643Ccj` (`WamDailyEventDailyCron`), alarm в `BEL` (`DailyCronAction`) | собирает и отправляет `C0Fp` |
| Событие звонка | `com.whatsapp.fieldstats.events.WamCall` (id 462) | создаётся из нативной статистики звонков, отправляется через `C24895Anr` |
| Нативный рантайм | `libwhatsapp.so` (`WAMRuntime`, `WAMBufferStore`, `WAMTransportRegular`, `WAMTransportPrivate`, `WAMPSIDProfile`) | буферы, id, выгрузки |

Не WAM, не путать (см. 17): Java-теневой логгер Falco (`C40099Hdc`, `FFLogger`), загрузчик крэшей и логов с тегом `wam-event/<name>`, ACS-токены для других проектов и слово `fieldstats`, используемое нативной статистикой звонков (`prepare_wa_call_fieldstats`).

Сигналы целостности клиента, которые передаются внутри WAM (`is_rooted`, `is_genymotion`, `is_whatsapp_plus_user`, атрибуты 6251 и 10255), описаны в [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) и здесь лишь упоминаются.

---

## 2. Модель событий

### 2.1 Класс события (`C0Fc`)

Каждое событие — сгенерированный класс; конструктор `super(code, samplingTuple, bufferChannel, psId)`, например `wam_daily`: `super(1158, new C036300x(1, 1, 1, false), 0, -1)`, `getEventNameForFalco() = "wam_daily"`, `internalFalcoMigrationBatchNumber() = 12`.

| Член | Значение | Tier |
|------|----------|------|
| `code` | числовой id события (1158 для `wam_daily`, 460 `wam_login`, 462 `wam_call`, 854 `wam_message_send`) | found |
| `samplingRate` | `C036300x(a, b, c, flag)` хранится как `A02=a, A01=b, A00=b, A03=c`; сэмплер использует `A00 = b`. По умолчанию `C0Fc.DEFAULT_SAMPLING_RATE = (1, 20, 20)` | found |
| `bufferChannel` | 0..3, см. 2.2 | found |
| `psId` | `-1` = не приватное; иначе хэш ключа private-stats, см. 2.3 | found |
| `getFieldsMap()` / `getFieldsMapForFalco()` | числовой id поля в значение (передаётся в native) / имя в snake_case в значение | found |
| `validate()` | список нарушений (`.nonnull` и подобные правила), см. 3.2 | found |
| `serialize(C3T8)` | тело — `throw new NullPointerException("serialize")`; сериализация нативная | found |

Поля используют упакованные типы Java (`Boolean`, `Integer`, `Long`, `Double`, `String`). Enum и таймеры передаются как целые числа (inferred из сеттера атрибутов, который принимает только null / String / Integer / Long / Double / Boolean). У `wam_daily` 218 числовых слотов и 205 именованных (13 числовых слотов только null), совпадает с более ранним подсчётом для 2.26.35.8.

### 2.2 Каналы

| `bufferChannel` | События (разобрано) | Имя (метки inferred; Java использует простые int) | Tier |
|-----------------|---------------------|------|------|
| 0 | 824 | REGULAR | found |
| 1 | 8 | REALTIME | found |
| 2 | 168 | PRIVATE (нужен private-stats id, см. 2.3) | found |
| 3 | 8 | анонимный realtime private-stats, "RTPS" в нативных строках логов (метка inferred) | found / inferred |

Всего разобрано: 1,008 классов событий с различными id. Отображение передаётся в native без изменений (аргумент канала `jvidispatchIIIIIOO` 0..3). Любое другое значение бросает `IllegalArgumentException("Unsupported channel type")`.

REALTIME-события (id): 2098 `wam_ui_action_real_time`, 5504 `wam_wefr_client_exposure`, 5278 `wam_android_test_realtime`, 6640 `wam_wefr_group_client_exposure`, 6088 `wam_restore_contacts_realtime_event`, 4290 `wam_wa_fs_chat_transfer`, 2872 `wam_xplatform_migration_export`, 6266 `wam_cac_client_event` (found).

События channel 3: 5164 `wam_wam_test_anonymous_realtime`, 7312 `wam_mm_signal_undisclosed`, 7352 `wam_mm_signal_realtime`, 6160 `wam_wamo_video_event`, 6158 `wam_wamo_ctwa_1pd_conversion`, 7956 `wam_wamo_promo_pog_impression`, 5712 `wam_wamo_promo_reporting_events`, 7350 `wam_wamo_alv2_link_click` (found). `C06650Fo.A01` отбрасывает событие channel 3, если его код не входит в два жёстко заданных массива (`AbstractC38512Gog.A00` 3 id, `A01` 5 id). Эти 8 id — ровно 8 событий channel 3, поэтому в этой сборке проверка ничего не отбрасывает (inferred из наборов id).

### 2.3 Private-stats id (`psId`)

| `psId` (int) | Строка ключа в нативном файле профиля | Ротация (дни) | События | Tier |
|--------------|---------------------------------------|---------------|---------|------|
| `-1` | нет (не приватное) | – | 832 (regular + realtime) | found |
| `0` | `none` (глобальный 6005 в буфере содержит строку `none`) | – | 94 (86 private + 8 channel 3) | found; соответствие "none" inferred |
| `113760892` | `default_ps_id` | никогда (`-1`) | 66 | found |
| `56300709` | `id_pre_metrics` | никогда (`-1`) | 1 (`wam_ps_app_launch`) | found |
| `248614979` | `id_ttl_daily` | 1 | 4 | found |
| `42196056` / `191000728` | `id_ttl_weekly` / `id_ttl_monthly` | 7 / 30 | 0 | found |
| `37887164` | `id_ttl_90_days` | 90 | 1 (`wam_clock_skew_difference_t`) | found |
| `152546501` | `group_exit_experience_id` | 30 | 4 | found |
| `216763284` | `group_safety_check_id` | 30 | 6 | found |

Строки ключей и дни ротации прочитаны из восьми файлов `WAMMetadataPSIDProfile-*` (см. 6.3), количество событий — из классов событий.

### 2.4 Веса по каталогу

Эффективный вес схемы `A00` для события (событие сохраняется с вероятностью 1/вес, вес хранится вместе с событием):

| Вес | События | Типичные представители |
|-----|---------|------------------------|
| 1 (всегда) | 826 | `wam_daily`, `wam_registration_complete`, `wam_blocking_funnel` |
| 5 / 10 | 6 / 12 | `wam_message_send` (5), `wam_message_context_menu_actions` (10), `wam_ui_action_real_time` (10) |
| 20 | 135 | `wam_message_delete_actions`, `wam_message_high_retry_count`, все события с `DEFAULT_SAMPLING_RATE` (81) |
| 100 / 200 | 4 / 2 | `wam_login_stage_reliability` (100) |
| 1000 | 17 | `wam_message_stanza_receive`, `wam_call_stanza_receive`, `wam_status_stanza_receive`, `wam_iq_send`, `wam_push_latency`, `wam_db_perf` |
| 10000 | 4 | `wam_receipt_stanza_receive`, `wam_android_profilo_usage`, `wam_android_message_target_perf`, `wam_notification_highlight_result` |

Вес не является переключателем функции: сервер может переопределить его для каждого события (8.2). Одно событие с константным весом сборки не было отнесено ни к одной группе.

---

## 3. Java-конвейер логирования

### 3.1 Путь отправки

`CNW` = `CNI(event, null, false)`: определить вес (8.1), выполнить allowlist channel 3 (`A01`), затем запустить runnable `X.1Fc` на WAM-executor (`C06600Fj.A01`):

| Шаг | Поведение | Tier |
|-----|-----------|------|
| Runtime latch | `C06650Fo.A0K` (`CountDownLatch`) блокирует executor, пока не инициализированы общие атрибуты ("wamruntime/initializeCommonAttributes: runtime initialized") | found |
| Валидация | `event.validate()` выполняется только для каналов 0 и 1 (не для класса события валидации `C40251kT`). Каждое нарушение становится `wam_wam_validation_error_event` (id 5560) с кодом проблемного события, случайным значением сессии и частями правила, соединёнными через `;` | found |
| Режимы логгера (`A04`) | `3`: для кодов из настроенного набора записывает `traceIdInt` (случайные 64 бита) в событие через reflection; `10`: для событий, проходящих `C06630Fm` (Falco migration batch 1..16, не в deny list), записывает `dedupKey` (случайные 64 бита); `1` / `3`: дополнительно отправляют событие Falco (`_test$<name>` / `<name>_shadow`) | found |
| Dispatch | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fieldsMap)` после проверки, что библиотека загружена | found |
| Триггер выгрузки логов | AB string prop **31314** содержит `"code:N;code:M"`; если `Random.nextInt(N)==0` для отправляемого кода, у репортера крэшей и логов запрашивается выгрузка логов устройства с тегом `wam-event/<falco name>`. Выгружаются логи, не буфер WAM | found |

`dedup_key` и `trace_id_int` — поля схемы события (есть в `wam_login`, `wam_app_launch`, `wam_message_send`); они случайны для каждого события и не являются идентификаторами пользователя (inferred из генератора).

### 3.2 Правила валидации

В `C0Fp` (`wam_daily`) поле `ai_widget_installed` всегда сообщается как нарушение, потому что его не обеспечивает ни один Java-член (правило `daily .nonnull`), а `default_after_read_enabled` — когда его член равен null. Следствие (inferred): каждое ежедневное событие на канале 0 также порождает события валидации (id 5560).

### 3.3 Триггеры flush и жизненного цикла

| Триггер | Вызов | Нативная операция | Tier |
|---------|-------|-------------------|------|
| Обработчик соединения подключён | `C0A4.BvO` -> `CKt(0)` | `jvidispatchIIO(4, 0, ctx)` | found |
| Подключение / отключение | `BvP`, `BvQ` -> `CKt(1)` | `jvidispatchIIO(4, 1, ctx)` | found |
| Обработка офлайн-сообщений завершена (`XmppStateManager/offlineProcessComplete`, также очищает `C0A2.A07`) | `BvR` -> `CXW(false)` только при AB prop **9654** | `jvidispatchIO(10, ctx)` (flush активных буферов) | found |
| Явный flush | `Bba()` -> `CXW(true)`; `CXZ()` делает flush и ждёт до 2500 ms | `jvidispatchIO(10, ctx)` | found |
| Конец звонка | `C24895Anr.A02` отправляет `WamCall`, затем `Bba()`, если звонок помечен или AB prop **16047** | flush | found |
| Перерегистрация / удаление аккаунта | `C25100xS` ("RegistrationManager/reregister/rm-me") -> `CUj()` | `jvidispatchIO(12, ctx)` ("wamruntime/resetruntime") | found |

Аргумент состояния 0/1 — состояние XMPP-соединения, зеркалируемое в нативные транспорты (строка лога "wameta/transport/status - %d"). Значение 0 = connected прочитано из отображения коллбэков, а не из нативного кода (inferred). Состояния `C0A2.A04`: 1 connecting, 2 connected, 3 disconnected, 4 stopped; `A07` равен true от подключения до завершения обработки офлайн-сообщений, поэтому `A0N()` означает "подключён и всё ещё получает офлайн-сообщения".

### 3.4 JNI-поверхность

| Направление | Сигнатура | Назначение | Tier |
|-------------|-----------|------------|------|
| Java в native | `jvidispatchIOOOO(0, path, networkSession, ctx, config)` | инициализация рантайма (лог "WAJContextInitWAMRuntime"), см. 4 | found |
| Java в native | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)` | логирование события | found |
| Java в native | `jvidispatchIIIOO(0, channel, attrId, String, ctx)` / `jvidispatchIIIO(4, channel, attrId, ctx)` / `jvidispatchIIIIO(1, channel, attrId, bool, ctx)` / `jvidispatchIIIDO` / варианты int, long | установка общего атрибута (null, string, boolean, double, integer) | found |
| Java в native | `jvidispatchIIO(4, state, ctx)` / `jvidispatchIO(10, ctx)` / `jvidispatchIO(12, ctx)` | состояние соединения / flush / сброс | found |
| Java в native | `jvidispatchIOOOO(4, ctx, signedCredential, acsPublicKey, configId)` | результат credential IQ (все null при ошибке) | found |
| Native в Java | `jnidispatchIO(6, byte[])` | отправить один регулярный буфер как `w:stats` IQ, возвращает 1 при `result` | found |
| Native в Java | `jnidispatchIO(7, byte[32])` | отправить запрос credential `privatestats` | found |

---

## 4. Инициализация рантайма

`RunnableC29323CoA` case 33 строит конфигурационную map и один раз вызывает native init. Путь — `<filesDir>/wam`.

| Ключ конфигурации | AB prop | Тип | Вероятное значение | Tier |
|-------------------|---------|-----|--------------------|------|
| `platform_code` | – | int `2` | id платформы Android | found |
| `beacon_probability` | **6977** | int | вероятность нативного статуса "beaconing" для каждого события (`WAMBeacon`) | found; значение inferred |
| `storage_size` | **9822** (x 1024) | long | лимит хранилища буферов (KiB в байты); native логирует "no-enough-storage" и отбрасывает события | found; единица inferred |
| `buffer_timeout` | **12399** | int | таймер ротации буфера | found; значение inferred |
| `throttling_percentage` / `throttling_exempt` | **9457** / **9456** | int / string | троттлинг выгрузки и список исключений | found; значение inferred, формат unknown |
| `enable_extra_logging` | **14310** | bool | подробное нативное логирование | found |
| `enable_ps_upload_v2` | **15205** | bool (только когда включено) | нативная логика "beginning upload v2 logic" на приватном транспорте | found |
| `enable_aggregation` / `aggregation_config` | **11981** / **11982** | bool (только когда включено) / string | включает `WAGAggregation` с его правилами | found; формат unknown |

Тот же вызов получает объект `networkSession`, созданный `C25810yb`; его использование нативными HTTP-обёртками inferred. Значения AB props по умолчанию приходят с сервера и не были определены.

---

## 5. Общие (глобальные) атрибуты

Глобальные атрибуты записываются `RunnableC29340CoR` case 0 через `C06590Fi.CYl(value, attrId, channel)` для каналов 0..3. Один хелпер задаёт сразу все четыре канала; остальные задают только 0 и 1. Поэтому приватные каналы (2, 3) получают сокращённый набор.

| Attr id | Источник значения | Каналы | Tier |
|---------|-------------------|--------|------|
| 3 / 5 | MNC / MCC, разобранные из `TelephonyManager.getNetworkOperator()` (5 или 6 цифр, только GSM) | 0 1 2 3 | found |
| 11 / 1659 / 1657 | код платформы `2` / код платформы `2` / константа `3` | 0 1 2 3 | found |
| 13 / 15 / 17 / 21 | `Build.MODEL-Build.MANUFACTURER` / `Build.VERSION.RELEASE` (пропускается при AB prop **12637**) / версия приложения `2.26.41.6` / `true` (флаг beta inferred; зашит в этом beta APK) | 0 1 2 3 | found |
| 287 / 289 / 495 | `Build.MANUFACTURER` / `Build.MODEL` / строка устройства (не определена) | 0 1 | found |
| 655 / 689 / 2617 | метрики памяти и класса устройства (`C38271gj`, `IJJ.A02/1048576`, `C38261gi`) | 0 1 2 3 | found; имена inferred |
| 4473 | ключ AB-конфигурации (`ab_key` из последнего ответа `<props>`, переустанавливается при каждом обновлении AB) | 0 1 | found |
| 5029 | id экспозиции AB-экспериментов через запятую (`BxP`); при AB prop **31830** объединённая map из `ab-props` и `ab-private-abprop` | 0 1; также присутствует в приватном буфере (канал 2) | found |
| 6251 / 10255 | проверка подписи приложения / флаг установщика Play | 6251: 0 1 2 3; 10255: 0 1 | found, см. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |
| 12017, 12027, 14507, 15265, 15611, 23, 707, 7335, 13293, 23043 | разные значения состояния приложения (12027 boolean из объекта состояния аккаунта, 707 `primary_platform_name` только когда 12027 равен true, 13293 = AB prop **3664**, 15611 константа WASafe (см. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)), 7335 `true` после выполнения init-хуков) | в основном 0 1; 13293 все четыре | found; значения inferred или unknown |
| 47 | время коммита, int32 секунды, добавляется нативно | все | found (файл буфера) |
| 6005 | значение private-stats id (строка UUID или `none`), добавляется нативно | приватные буферы | found (файл буфера) |
| 2795, 105 / 6833 | добавляется нативно, только регулярные буферы / значение из `C21730rv`, только каналы 2 и 3 | 0 / 2 3 | found; значения unknown |

Среди общих атрибутов, записываемых Java, нет ни номера телефона, ни JID, ни id аккаунта. Регулярный транспорт привязан к аккаунту аутентифицированным соединением, по которому отправляется (inferred, см. 9).

---

## 6. Нативное хранилище

Строки из `libwhatsapp.so` (`WAMBufferStoreImpl`, `WAMPSIDProfileStoreImpl`, `WAMPrivateCredentialStoreImpl`, `WAMMetadataStoreImpl`) и файлы установленного каталога данных 2.26.41.6 согласуются.

### 6.1 Каталог `files/wam/`

| Файл | Содержимое | Tier |
|------|------------|------|
| `wamt-a-<channel>-0-<seq>` | активный буфер, 65,559 байт (преаллоцирован, заполнен нулями); нативная строка `wamt-o` намекает на ротированные буферы (inferred) | found |
| `wam-metadata` | контейнер `MTD` v4 со счётчиками по каналам; сохранённая следующая последовательность для канала 0 равна наибольшей последовательности файлов плюс один | found; структура inferred |
| `WAMMetadataPSIDProfile-<n>-<keyHash>` | один профиль private-stats на хэш ключа (видно 8 файлов) | found |
| `WAMMetadataPrivateCredential-<n>` | сохранённый credential для приватного транспорта (`signed_credential`, ключ, config id; v2, ~120 байт) | found; структура inferred |

Третье число в имени файла — id потока (лог "wameta/buffer/rotated stream id: %d, channel: %d, buffer sequenceNumber: %d"; в образце всегда `0`), последнее — последовательность буфера.

### 6.2 Структура файла буфера

```
off  0   "WMT" 03                      container magic, version 3
off  4   u32 LE  used length           = (end of used data) - 31   (checked in 2 files)
off  8   u32 LE  ?                     counter, meaning unknown
off 12   u32 LE  event count           equals the number of event markers decoded
off 16   u32 LE  ?                     close to the used length (+4, +6, +31 in samples)
off 20   u32     ?                     check value (inferred), algorithm unknown
off 24   "WAM" 05                      WAM header: magic + protocol version 5
off 28   u8  0                         flag byte (0 in all samples)
off 29   u16 LE  buffer sequence       equals the number in the file name
off 31   u8  channel                   0 regular, 2 private in samples
off 32   TLV entries                   globals first, then events
```

Found для каждого перечисленного байта со значением; поля, отмеченные "?", неизвестны.

### 6.3 Профиль private-stats

`WAMMetadataPSIDProfile-<n>-<keyHash>` (78–90 байт), структура прочитана из всех восьми файлов:

```
u8 version(2) │ i32 LE keyHash │ i32 LE rotationDays │ u8 ? │ float64 LE (timestamp, inferred) │ u32 ? (1) │
u32 keyLen │ u32 uuidLen(36) │ key string (e.g. "id_ttl_daily") │ UUID string
```

Дни ротации, прочитанные из файлов: -1 (`default_ps_id`, `id_pre_metrics`), 1, 7, 30, 30, 30, 90 (см. 2.3). Нативные строки называют операции `WAMPSIDProfileRotatePSID`, "psid delegated rotation was not persisted" и проверки повреждения (`invalid rotationInDays`). UUID — это то, что попадает в глобальный 6005 приватных буферов. Управляется ли ротация локальным временем или сервером — unknown.

---

## 7. Wire-формат WAM

Подтверждено на реальных буферах: декодер, написанный по схеме тегов ниже, разобрал глобальные атрибуты и события двух буферов (регулярного и приватного) без остатка.

### 7.1 Кодирование записи

Каждая запись — `[tag][field id][payload]`.

| Часть | Кодирование | Tier |
|-------|-------------|------|
| Младший ниббл тега | роль: `0` global, `1` маркер события, `2` поле; OR `0x04` последний в группе; OR `0x08` id поля — `u16 LE` вместо `u8` | found |
| Старший ниббл тега | тип значения: `0x00` null, `0x10` int 0, `0x20` int 1, `0x30` int8, `0x40` int16 LE, `0x50` int32 LE, `0x60` int64 LE, `0x70` float64 LE, `0x80` строка (длина u8), `0x90` строка (длина u16 LE), `0xA0` строка (длина u32 LE) | found для int 0/1, int8, int16, int32, строки u8 и u16 (все декодированы из буферов); остальные inferred из схемы и кодировщика Baileys |
| Целые, строки, порядок байт | наименьшая форма целого (0 и 1 живут в теге); строки UTF-8; везде little-endian (кодек stanza — big-endian) | found |

### 7.2 Маркер события

Маркер события — роль `1` с id события в качестве id поля. Его значение — вес сэмплирования, хранится в буферах положительным: события с весом схемы 20 (`wam_secure_file_usage`, `wam_whatsapp_quick_promotion_client_eligibility_waterfall`) несут 20, события с весом 1 несут 1 (found). Далее идут поля с ролью `2` (флаг последнего поля `0x04` не проверялся). Блок глобальных атрибутов (роль `0`) записывается при изменении атрибутов, поэтому глобальные значения повторяются между событиями (время коммита 47 переписывается много раз, found).

Полезная нагрузка IQ составляет от 4 до 126,976 байт (9). Что она равна буферу от смещения 24 (начиная с заголовка `WAM`) — кодом не показано; это inferred из структуры и из того, что Baileys отправляет тот же заголовок (15).

---

## 8. Сэмплирование и веса событий

### 8.1 Определение веса (`C0Fg.A00`, упрощённо)

```
override = prefs(code == 1094 ? "app_launch_event_sampling_weight" : "field-stats-events-sampling"[code], 0)
weight   = override != 0 ? override : schema.A00         // sampler becomes (|w|,|w|,|w|,|w|) for an override
keep     = random.nextInt(sampler.A00) == 0              // 1-in-N; null return = "(dropped)"
```

| Элемент | Значение | Tier |
|---------|----------|------|
| Локальные переопределения | файл prefs `field-stats-events-sampling` (ключ = код события) и `app_launch_event_sampling_weight` (событие 1094); вес 1 сохраняется всегда | found |
| Нативная защита | "wameta/logger event weight exceeds max, dropped"; лимит нативный | found; значение unknown |
| Сэмплирование по звонку | `WamCall`: поле `logSampleRatio` (id 1120) события определяет вес, `new C036300x(i, i)` | found |

### 8.2 Доставка с сервера (ответ AB props)

`C28894Cgv.CFS` обрабатывает результат AB-props (узел `<props>`). Каждый дочерний `<prop>` — либо config prop, либо запись сэмплирования события:

```
<props ab_key hash refresh refresh_id delta_update>
  <prop config_code config_value config_expo_key/>    -> ab-props
  <prop event_code="854" sampling_weight="5"/>        -> field-stats-events-sampling
</props>
```

Когда `hash` непустой, prefs сэмплирования очищаются и переписываются из всех пар `event_code`/`sampling_weight`; запись 1094 также записывает `app_launch_event_sampling_weight` (и удаляет его, если записи нет). Итак, сервер управляет весами событий, а веса отправляются обратно с каждым событием, чтобы сервер мог масштабировать счётчики (inferred из того, что поле передаётся вместе с событием; использование сервером unknown).

Таким образом, сервер формирует поведение WAM через AB props, веса сэмплирования и приватный credential; ничего не отправляется через сам IQ выгрузки (IQ получает только `result`).

---

## 9. Регулярная выгрузка (`w:stats`)

Native вызывает `JniBridge.jnidispatchIO(6, bytes)`. Java строит и отправляет:

```
<iq xmlns="w:stats" to="s.whatsapp.net" type="set" id="..">
  <add t="<unix seconds>">[binary: WAM buffer]</add>
</iq>
```

| Элемент | Значение | Tier |
|---------|----------|------|
| Транспорт | обычный аутентифицированный chat-поток (`C10140Tq`), как и любой IQ | found |
| `t`, границы, таймаут | `t` = текущие unix-секунды (добавляется только в пределах 1,577,865,600..4,102,473,600); полезная нагрузка проверяется на 4..126,976 байт; таймаут IQ 32,000 ms (синхронное ожидание) | found |
| Успех | атрибут ответа `type == "result"` -> учёт `C0VI.A02(len, 32)`, возврат 1 | found |
| Ошибка | другой type или прерывание -> лог "FieldStatsXmppImpl/error sending fieldstats IQ", возврат 0 (повторы решает native; существует "_WAMTransportManagerUploadFailedPermanently") | found |
| Откладывается во время звонка | возврат 0 с логом "WamJniBridge/upload postponed", если звонок активен, кроме случая, когда AB prop **15507** включён, либо звонок групповой и включён AB prop **468** | found (поток декомпилятора, значение по умолчанию группового флага предполагается false) |
| Откладывается во время обработки офлайн-сообщений | возврат 0, если `C0A2.A0N()` (подключён и офлайн-сообщения ещё не получены) и AB prop **9654** включён; при выключенном 9654 IQ отправляется | found |
| Связь с аккаунтом / сжатие | в полезной нагрузке нет id аккаунта, сервер видит аутентифицированную сессию; на Java-пути сжатия нет | inferred / found |

Тот же prop 9654 включает flush при `offlineProcessComplete` (3.3). Вместе: при включённом 9654 выгрузки ждут, пока очередь офлайн-сообщений не будет разобрана, и в этот момент выполняется flush (inferred по двум местам вызова; тайминг повтора после отложенной попытки нативный и unknown).

---

## 10. Приватная выгрузка

Приватные каналы (2 и 3) не отправляются как `w:stats`. Нативный `WAMTransportPrivate` выгружает через отдельный HTTP-транспорт (`WCIHTTPImpl`) с анонимным credential. Всё ниже получено из нативных строк логов и Java-обработчика credential.

### 10.1 Запрос credential

```
<iq xmlns="privatestats" to="s.whatsapp.net" type="get" id="..">
  <sign_credential version="1">
    <blinded_credential>[32 bytes]</blinded_credential>
  </sign_credential>
</iq>
```

| Часть | Деталь | Tier |
|-------|--------|------|
| Отправитель | `JniBridge.jnidispatchIO(7, byte[32])`; код ошибки в трекере IQ 239, таймаут 32,000 ms | found |
| Ответ (`KRL.CFS`) | `<sign_credential t=..><signed_credential/><acs_public_key/><config_id/></sign_credential>`; три массива байт передаются в native через `jvidispatchIOOOO(4, ctx, ...)`; при ошибке или отсутствии ответа native получает null | found |
| Телеметрия | событие 2242 `wam_sign_credential` (регулярный канал) со статусом 3 = ошибка, 1 = успех, и затраченным временем | found |
| Проверка и хранение | нативные строки "Invalid signature received from server", "fails validation" (клиент проверяет подпись); хранится в `WAMMetadataPrivateCredential-<n>`, обновляется при 401 ("send failed, renew credentials") | found |
| Схема | ослеплённый запрос, подписанный ответ, публичный ключ ACS: анонимный credential, поэтому credential не связывает приватные выгрузки с аккаунтом | inferred |

Отдельный общий отправитель `C1N8` использует то же пространство имён с `<sign_credential version="2">` и `project_name` для других проектов ACS (prefs `acs_token_*`); это не путь WAM.

### 10.2 Выгрузка

| Элемент | Деталь | Tier |
|---------|--------|------|
| Endpoints | нативные логи "url/received", "fetch_endpoints/custom_endpoints - got endpoints: %d", "invalid_ps_endpoint, ignoring"; нет литерала URL ни в Java, ни в `libwhatsapp.so` | found; источник списка unknown |
| Обработка ошибок и таймер | "try next endpoint", "have next credentials", "401, no more endpoints"; таймер транспорта ("timer/started - interval: %.1f seconds") запускается при "connection_ready", останавливается при "connection_unavailable" | found; интервал unknown |
| Realtime private | буферы по событиям: "create_buffer/realtime/buffer-created ... event id", "sendsingleeventimpl/realtime" | found |
| Заголовки, фрейминг тела, сжатие | не видны | unknown |

Java-логгер Falco `C40099Hdc` в режиме 9 отбрасывает со своего пути события с каналом 2 или 3 либо с psId и считает их как `wa:dropped_private_stats` (found), поэтому приватные события не дублируются в этот логгер (inferred).

---

## 11. `wam_daily` и периодические события

Событие id 1158, имя Falco `wam_daily`, канал 0, вес 1, 218 числовых / 205 именованных полей. Поля root, эмулятора, кастомной ROM и мод-клиента см. в [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md); здесь зафиксирована только внутренняя механика.

### 11.1 Планирование (found)

| Элемент | Деталь |
|---------|--------|
| Alarm | `BEL.A01`: следующая локальная полночь + случайный jitter `nextInt(AB prop 5529)` (единица преобразуется `C20D.A02`), action `com.whatsapp.action.DAILY_CRON` |
| Догон | action `com.whatsapp.action.DAILY_CATCHUP_CRON`, повтор каждые 15 минут, пока "last_daily_cron" не сегодняшний |
| Защита | пропуск с "too frequent", если cron уже выполнялся сегодня (pref `last_daily_cron`); пропуск всех cron, пока идёт перенос чатов; cron, которым нужно хранилище сообщений, пропускаются, если оно не готово |
| Executor | перебирает DI-набор crons `InterfaceC29983D2n` (`Bo5`); `C28643Ccj` (тег `WamDailyEventDailyCron`) выполняется только при `anonymousClass091.BS3()` (состояние аккаунта, значение не определено) |

### 11.2 Заполнение

`C28643Ccj.Bo5` создаёт `new C0Fp()`, вызывает `C4k(C0Fp)` у каждого популятора из DI-набора (28 файлов определяют популятор `C4k(C0Fp)`), затем `CNW(c0Fp)` с весом схемы по умолчанию. Популятор флагов устройства в этой сборке только в smali (`smali_classes7/X/Cdt.smali`; декомпилятор на нём падает), читает и пишет pref `last_daily_event` (wall-clock ms), присваивая `time_delta_since_last_event`. Декомпилированная ветка меняет delta только с 0 на 1, поэтому утверждений о единице или периодичности для этого поля не делается. `last_daily_event` не является планировщиком (им является alarm в 11.1).

Тот же cron порождает событие только для Falco `wam_daily_permission` (сэмплируется): статус разрешения на контакты, разрешение на галерею, разрешения на камеру / запись аудио / приблизительную и точную геолокацию, настройка уведомлений ОС, размеры адресной книги, необязательные счётчики потоков (AB prop **25576**) и `profile_photo_is_set` (AB prop **34207**), `os_version` (found).

### 11.3 Другие периодические события

Другие события старта приложения и периодические: 1094 `wam_app_launch` (вес можно переопределить через `app_launch_event_sampling_weight`), 3300 `wam_ps_app_launch` (приватное, `id_pre_metrics`), 3178 `wam_clock_skew_difference_t` (приватное, `id_ttl_90_days`), семейство `*_daily` (5798 `wam_reaction_daily`, 3680 `wam_polls_daily_stats`; триггеры inferred).

---

## 12. Обработка приватности

| Аспект | Находка | Tier |
|--------|---------|------|
| Стабильные id в пакетах | нет JID или номера телефона в общих атрибутах, записываемых Java; `dedup_key` и `trace_id_int` случайны для каждого события; регулярный канал аутентифицируется потоком, по которому передаётся | found / inferred |
| Private-stats id | UUID на ключ в `WAMMetadataPSIDProfile-*`, глобальный 6005 в приватных буферах; ротация 1, 7, 30, 90 дней или никогда | found |
| Анонимный credential | ослеплённый токен, подписанный сервером, для приватных выгрузок (10.1) | found; несвязываемость inferred |
| Хэшированные и открытые id | существуют поля с хэшированными id (`hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids`, `message_key_hash`, `invited_user_hash`; хэш-функция не прослежена); существуют и строки типа JID (`reported_jid`, `e2e_sender_jid`; хэширование перед логированием не прослежено) | found (имена), unknown |
| Сброс | удаление аккаунта и перерегистрация вызывают нативный сброс (`jvidispatchIO(12)`); сброс профилей PSID этим вызовом не показан | found / unknown |
| Отказ пользователя | не найдено ни настройки, ни строки, ни флага, отключающих WAM; единственная строка в ресурсах, похожая на согласие, относится к диагностике поддержки. Настройка может существовать в не просмотренных путях кода | unknown |
| Контроль сервера | веса событий (8.2), AB props (13), конфигурация `throttling_*` и `beacon_probability` (4); алгоритмы нативные | found; unknown |

---

## 13. Feature flags (AB props, как они читаются в рассмотренных путях кода)

| Prop | Тип | Что контролирует |
|------|-----|------------------|
| **9654** | bool | flush при завершении обработки офлайн-сообщений (3.3); выгрузка откладывается, пока разбираются офлайн-сообщения (9) |
| **15507** / **468** / **16047** | bool | выгрузка не откладывается во время звонка / во время группового звонка / flush после событий звонка |
| **6977**, **9822**, **12399**, **9457**, **9456**, **14310**, **15205**, **11981**, **11982** | mixed | ключи конфигурации init рантайма (раздел 4) |
| **31314** | string | `"code:N;..."` частота триггера выгрузки логов по коду события |
| **5529** | int | jitter ежедневного cron |
| **12637** | bool | пропускает версию ОС, производителя и сопутствующие атрибуты (15, 287, 21, 12027, 707) |
| **31830** / **25576** / **34207** | bool | объединённый приватный список AB в атрибуте 5029 / необязательные поля `wam_daily_permission` |
| **34494..34507, 35169, 35170** | – | массив в `AbstractC38513Goh.A01` (16 id, столько же, сколько Falco migration batch 1..16); использование inferred |

Все значения назначаются сервером; значения по умолчанию не определены.

---

## 14. Заметные семейства событий

Имена — имена Falco; id и каналы взяты из классов событий. Списки полей — именованные поля `getFieldsMapForFalco()`.

### 14.1 Сообщения

| Событие | id | Канал / вес | Заметные поля |
|---------|----|-------------|---------------|
| `wam_message_send` | 854 | 0 / 5 | 89 полей: `message_send_result`, `message_send_t`, `message_type_str`, `e2e_ciphertext_type`, `e2e_ciphertext_version`, `is_pq`, `is_lid`, `retry_count`, `resend_count`, `message_is_forward`, `message_is_fanout`, `message_distribution_type`, `participant_count`, `device_count`, `message_key_hash`, `is_view_once`, эфемерность, edit/revoke, поля бота и private-AI |
| `wam_message_receive` | 450 | 0 / 20 | 58 полей: `message_receive_t0..t2`, `message_queue_time`, `message_is_offline`, `offline_count`, `stanza_process_count`, `padding_bytes_size`, `message_addressing_mode`, `server_addressing_mode`, `session_scope`, поля стикеров и контактных карточек |
| `wam_e2e_message_send` / `_recv` | 476 / 478 | 0 / 20 | `e2e_successful`, `e2e_failure_reason`, `e2e_destination`, `group_encryption_state`, `enc_retry_count`, `pq_receive_gate_state` |
| `wam_e2e_message_decrypt_fail_sender` | 3524 | private (ps `none`) | `e2e_sender_jid`, `e2e_failure_reason`, `retry_count` |

### 14.2 Звонки

`WamCall` (id 462, канал 0) создаётся из нативной статистики (`ConvertFieldStats`, "can not construct com/whatsapp/fieldstats/events/WamCall") и имеет примерно 1,700 именованных полей (1,716 мест `put` в map Falco). `WamJoinableCall` — id 2572. Сэмплирование — `logSampleRatio` (поле 1120), а событие сбрасывается в конце звонка (3.3). Другие события звонков: 2582 `wam_call_stanza_receive` (вес 1000), 3452 `wam_call_critical_events`, 4568 `wam_call_user_journey`. Сам call signaling описан в [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md).

### 14.3 Логин и регистрация

| Событие | id | Поля |
|---------|----|------|
| `wam_login` | 460 | `login_result`, `login_t`, `connection_origin`, `connection_t`, `login_dns_resolver`, `login_ip_source`, `login_port`, `login_resolved_pop`, `login_socket_provider`, `noise_protocol_version`, `retry_count`, `server_error_code`, `passive`, `long_connect`, `network_is_vpn`, `android_keystore_state`, `pending_acks_count`, `unprocessed_message_count` (30 слотов); см. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) |
| `wam_reg_init` / `wam_registration_complete` | 2046 / 1342 | тайминги init (`contacts_sync_t`, `groups_init_t`, `total_t`); 30 полей, включая `registration_t`, `addressbook_size`, `contacts_permission_authorization_status`, `device_identifier`, `google_account_list_hashed_reg`, `invited_user_hash`, `is_new_jid`, поля фото профиля и разрешений |
| `wam_account_encryption_attestation` | 8164 | имя намекает на результат аттестации (inferred); см. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |

### 14.4 Спам, жалобы, блокировка

Потоки описаны в [WA_REPORTING.md](WA_REPORTING.md) и [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) (`wam_wfacp_ban_action`, id 5028); сторона WAM:

| Событие | id | Канал | Поля |
|---------|----|-------|------|
| `wam_spam_report_perf` | 6310 | 0 | `report_spam_flow`, `report_status`, `report_attempt_count`, `report_duration_ms`, `report_error_code` |
| `wam_report_conversation_context` | 4608 | 0 | `reported_jid`, `spam_flow`, `estimated_num_messages_sent/received`, `is_chat_maybe_suspicious`, `is_in_addressbook`, `first_entry_point`, `num_call_msgs_to_report` |
| `wam_blocking_funnel` / `wam_reporting_funnel` | 4920 / 4924 | 0 | `block_flow_action`, `hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids` |
| `wam_reporting_token_validation_failure` | 5466 | 0 | `reporting_token_validation_failure_reason`, `reporting_token_version`, `is_part_of_group_history` |
| `wam_reporting_token_validation_failure_sender`, `wam_reporting_token_additional_client_validation` | 6094, 6702 | 2 (`default_ps_id`) | варианты на стороне отправителя |
| `wam_message_template_blocks` | 3002 | 2 (`default_ps_id`) | причины блокировки бизнес-шаблонов |

### 14.5 Эксперименты

`wam_wefr_client_exposure` (id 5504, realtime) логирует экспозицию с `exposure_key`, `device_exp_id`, `user_lid`, `guest_id`, `is_canonical_ent_present`, `sent_with_daily`. Он несёт поле LID пользователя (found; использование сервером unknown). `wam_ui_action_real_time` (2098, вес 10) несёт только `chatd_internet_connectivity` и `dedup_key`.

---

## 15. Baileys (`baron-baileys-v2`, сравнение с его исходным кодом)

Baileys отправляет буферы WAM тем же IQ, что и Android-клиент.

| Аспект | Baileys (`src/Socket/socket.js`, `src/WAM/encode.js`) | Android 2.26.41.6 | Tier |
|--------|--------------------------------------------------------|-------------------|------|
| Stanza выгрузки | `<iq to=s.whatsapp.net xmlns="w:stats" type="set"><add t=…>buffer</add></iq>` | то же | found both |
| Заголовок | `"WAM"`, байт версии 5, байт 4 = `1`, последовательность `u16 BE` на 5, канал `0` на 7 | `"WAM"`, версия 5, байт 4 = `0`, последовательность `u16 LE` на 29, канал на 31 (в файле с контейнером `WMT` впереди) | found both |
| Кодирование значений | `0/1` в теге, int8, int16/int32 LE, float64 LE, строки с длиной u8/u16 LE/u32 LE, флаг широкого id `0x08` | те же биты | found both |
| Вес события | записывается как `-weight` | хранится положительным в файлах буфера | found both |
| Каналы, flush | только регулярный; flush каждые 30 с и после логина, ошибки только логируются | 0..3; нативная ротация и транспорты | found |

Различие в порядке байт последовательности и знаке веса не является ошибкой, доказанной этим отчётом: файлы Android на диске не обязаны совпадать с байтами, которые выгружает нативный транспорт, а парсер сервера не наблюдался. Ничто в просмотренных здесь путях chat-кода не ждёт состояния WAM; реагирует ли сервер на отсутствующую или необычную выгрузку — unknown (19).

---

## 16. Случаи ошибок

| Симптом | Причина | Исправление / примечание |
|---------|---------|--------------------------|
| Событие отсутствует в буферах | не прошёл бросок веса (1-in-N), allowlist channel 3, лимит хранилища, нативные "weight exceeds max", "have to drop event" | проверить вес 2.4 и AB props 8.2, 4 |
| Ежедневное событие порождает события валидации | правило `ai_widget_installed` не выполняется для каждого `wam_daily` (3.2) | ожидаемо в этой сборке |
| "WamJniBridge/upload postponed" | звонок активен без 15507 / 468, либо очередь офлайн-сообщений ещё разбирается при 9654 | временно; native повторяет (inferred) |
| "FieldStatsXmppImpl/error sending fieldstats IQ" | ошибка IQ, таймаут (32 с) или прерывание | путь нативного повтора / постоянной ошибки |
| "Cannot log before WAM runtime is initialized" / "after ... terminated" | порядок нативного жизненного цикла | Java ждёт на `A0K`; terminate — нативное состояние |
| Приватная выгрузка падает с 401 | credential отклонён | обновить через IQ `privatestats` (10.1) |

---

## 17. Ключевые различия

| Пара | Различие |
|------|----------|
| WAM vs Falco | события WAM проходят через нативный рантайм и буферы; Java-логгер Falco (`C40099Hdc`, `FFLogger`) — параллельный путь, повторно использующий те же классы событий по имени Falco. Falco migration batch 1..16 задаётся для каждого события (`internalFalcoMigrationBatchNumber`) |
| Вес события vs feature flag | вес = сэмплирование 1-in-N и множитель, отправляемый с событием; флаги только управляют поведением транспорта |
| Регулярная vs приватная выгрузка | регулярная = `w:stats` IQ в chat-потоке; приватная = отдельный HTTP-транспорт с ослеплённым credential |
| `psId` vs глобальный 6005 | `psId` — статический хэш ключа в классе события; 6005 — ротируемый UUID, записываемый нативно в приватные буферы |
| Id поля vs id глобального | числовые пространства пересекаются (47 — глобальный; поле 47 события — другое); различает роль в теге |
| `wam-event/<name>` vs выгрузка WAM | первое выгружает логи устройства через репортер крэшей, второе выгружает буферы метрик |
| Буфер на диске vs wire-нагрузка | у файла есть контейнер `WMT` и заполнение; структура полезной нагрузки IQ inferred |

---

## 18. Полный поток

```
[App code / native call stats]  new Event(...) / ConvertFieldStats -> WamCall
    ▼
[C06650Fo.CNW / CNI]  weight = override (prefs) or schema A00, keep 1-in-N ; validate (ch 0,1) -> event 5560
    ▼
[WAM executor]  jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)
    ▼
[libwhatsapp.so WAMRuntime]  encode TLV (LE), add globals (47 commit time, 6005 psId UUID, common attrs)
    ▼
[files/wam/wamt-a-<channel>-0-<seq>]  "WMT" container + "WAM" 5 header, 64 KiB
    │  rotate (buffer_timeout) / flush (offline-complete with 9654, Bba, call end, CXZ)
    ├── channel 0, 1 ─────────────────────────────┬── channel 2, 3 ───────────────────────────────┐
    ▼                                             ▼                                              
jnidispatchIO(6, bytes)                       jnidispatchIO(7, 32 bytes blinded token)
    │  postponed in calls / offline drain          │  <iq xmlns="privatestats" type="get">
    ▼                                             ▼
<iq xmlns="w:stats" type="set"><add t=..>     [WA server] signed_credential, acs_public_key, config_id
  bytes</add></iq>  on the chat stream              │  stored, renewed on 401
    ▼                                             ▼
[WA server] type="result" -> return 1         HTTP upload, endpoint list source unknown -> [private-stats backend]

[WA server] <props> response: event_code -> sampling_weight, config_code -> AB props  ──►  prefs (8.2)
[DailyCronAction alarm: next local midnight + jitter(5529)] -> C28643Ccj populates C0Fp (wam_daily 1158) -> CNW (same path, channel 0)
```

---

## 19. Неизвестное

| Вопрос | Почему unknown |
|--------|----------------|
| Точные байты полезной нагрузки выгрузки в сравнении с файлом буфера | нативный транспорт не дизассемблирован; видны только границы IQ |
| Сжатие и фрейминг заголовков приватных выгрузок, источник списка endpoints | нет литерала в Java или строках; нативный HTTP-путь не прослежен |
| Интервал нативной ротации, расписание повторов, максимум веса, правила отбрасывания, алгоритм beaconing | нативный код stripped, для крупной библиотеки здесь не использовался декомпилятор |
| Значение атрибутов 495, 6833, 2795, 105 и ряда флаговых атрибутов; поля `WMT` на смещениях 8, 16, 20; поля `MTD` | источники не определены, только значения |
| Зависит ли какое-либо поведение сервера от отсутствующего или необычного WAM | сторона сервера |
| Хэширование полей `*_jid`; наличие пользовательского отказа | не прослежено для каждого события / не найдено (отсутствие не доказательство) |
| Тайминг нативных повторов, триггер ротации PSID (время клиента или указание сервера), значения AB props по умолчанию | нативная логика не прослежена; значения по умолчанию приходят из конфигурации сервера |
| Триггер ежедневных cron, кроме `wam_daily` | прочитаны только реестр cron и cron `wam_daily` |
