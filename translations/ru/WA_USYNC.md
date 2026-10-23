<!-- src-sha1: 8e15828bcc50ba6f6a9c5388872afeef15451af0 -->
# WhatsApp USync — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** USync IQ (`xmlns="usync"`): режимы, контексты и типы синхронизации, структура stanza запроса и ответа, протоколы запросов (contact, sidelist, status, text_status, picture, business, devices, disappearing_mode, lid, username), поиск контактов и обнаружение номеров телефонов, синхронизация списка устройств, проверки key-index и ADV, маппинг LID, обогащение privacy-токенами, MEX `UsyncQuery` и маршрутизация по протоколам, лимиты частоты и backoff, клиентские триггеры, feature-флаги, сравнение с Baileys

---

## 1. Что это (технически)

USync — массовый запрос «кто этот пользователь». Один IQ несёт список пользователей и список протоколов (типов данных); сервер отвечает по каждому пользователю и по каждому протоколу. Одна и та же форма stanza обслуживает четыре задачи: выгрузка и загрузка адресной книги, одиночный поиск по номеру телефона, обновление данных профиля (статус, картинка, business, disappearing mode) и обновление списка устройств для message fan-out. Все утверждения получены статическим анализом декомпилированного APK; на проводе ничего не перехватывалось. Уровни: **found** = прочитано в коде, **inferred** = выведено, **unknown** = не выяснено. Обфусцированные имена привязаны к сборке и заново определены в 2.26.41.6.

| Слой | Имя в 2.26.41.6 | Роль |
|------|-----------------|------|
| Построитель / парсер stanza | `C18670m9` (тег лога `UniSyncProtocolHelper`): `A06` сборка, `A07` отправка, `CFS` результат, `Brt` ошибка iq, `Bog` сбой доставки | собирает `<iq xmlns="usync">`, разбирает результат `<usync>` |
| Модель запроса | `A05` (тип + пользователи + опции), `A0A` (построитель по пользователю), `C222649hm` (запрос по пользователю), `C222589hg` (ожидающий запрос, один на iq id) | что спрашивать |
| Тип синхронизации | `EnumC21760rz` (30 значений), `EnumC21770s0` контекст, `EnumC21780s1` режим, `EnumC21790s3` scope | источник атрибутов `mode` / `context` |
| Одиночные запросы | `C23638AId` (`ContactQuerySync`) | номер телефона, JID, username, LID в username |
| Пакетная синхронизация | `C18580m0` (`ContactSyncHelper`), анонимный callback `X.0m7` | мультипротокольная синхронизация, выбор MEX или classic, prefs backoff |
| Публичные точки входа | `C18230lP` (`ContactSyncMethods`), построитель `C21810s5`, запрос `C21830s7`, набор протоколов `C21820s6`, причина `EnumC21800s4` (77 значений) | их вызывают все функции |
| Применение результата | `N27` (`contactsyncresultupdater`), `C51909N4g` (`ContactSyncDevicesUpdater`) | записывает БД, карту LID, устройства |
| Устройства / ADV | `C23310uY` (`DeviceSyncManager`), `SyncDevicesJob`, `C24230w2` (`DeviceADVInfoHandler`) | задачи обновления устройств, проверка key-index |
| Privacy-обогащение | `C223659jg` (`ProfilePrivacyEnrichmentFetcher`), `C197138a8`, `C197148a9` | tctoken и общая группа для каждого пользователя |
| Вариант MEX | `C229259vZ` (`MexUsyncQueryHelper`), `M4I` (маршрут), `M5H` (бит протокола) | `UsyncQuery` и маршрутизация |
| Хранилище backoff | `C18800mM`, файл prefs `contact_sync_prefs` | `*_sync_backoff`, `*_full_sync_wait` |

Ключевые моменты:

- Построитель Android выдаёт десять дочерних элементов запроса: `contact`, `sidelist`, `status`, `text_status`, `picture`, `business`, `devices`, `disappearing_mode`, `lid`, `username`. Дочернего элемента `bot` и дочернего элемента feature **нет** (found, все строковые константы `A06`). `reachability`, `linked_profiles`, `orgs` и `ddm` существуют только в варианте MEX (раздел 8).
- В Android четыре режима и десять контекстов (раздел 2); каждый запрос несёт `sid`, `index="0"`, `last="true"` в прочитанных точках входа.
- Пользователи идут в `<list>` (обычные) или в `<side_list>` (контакты вне адресной книги).
- Запросы профиля несут привязанное к пользователю privacy-доказательство (сохранённый tctoken или JID общей группы), см. раздел 7 и WA_TCTOKEN_CSTOKEN.md.
- Поиск по username описан в WA_USERNAME.md; этот отчёт фиксирует только общие части stanza.

---

## 2. Конверт stanza

### 2.1 Запрос (found, `C18670m9.A06`)

```xml
<iq xmlns="usync" id="0AB1" type="get">                       <!-- `to` added by the sender, inferred -->
  <usync sid="sync_sid_query_<uuid>" index="0" last="true"
         mode="query" context="interactive" [allow_mutation="true"]>
    <query>                                                   <!-- protocol children, section 3 -->
      <contact [addressing_mode="lid"]/> <devices version="2"/> <picture type="preview" size="N"/> ...
    </query>
    <list>      <user jid="..." [common_gid="..."]> per-user children </user> ... </list>
    <side_list> <user jid="LID" pn_jid="PN"> ... </user> ... </side_list>
  </usync>
</iq>
```

| Часть | Правило (код) |
|-------|---------------|
| iq `id` | `C10140Tq.A0G()`: `"0"` + hex счётчика, оборачивается на 65536 (в лог пишется "iqId too large") |
| `sid` | `AbstractC43461pq.A00(prefix)` = prefix + `_` + случайный UUID; префиксы `sync_sid_query`, `ContactSyncHelper/sync_sid_<scope>`, `..._mex_profile` |
| `index` / `last` | из вызова: `A07` всегда передаёт `0` и `true` |
| `mode`, `context` | `EnumC21780s1.modeString`, `EnumC21770s0.contextString` типа синхронизации |
| `allow_mutation="true"` | ставится, когда `A05.A04` равен true: строится для типов full / delta, когда выполняется `C11980aQ.A0G()` (смысл не прослежен) |
| дочерний contact | присутствует, когда любой запрос просит contact (`A05.A03`) или когда другой протокол не запрошен |
| контекст REGISTRATION | отправляется через `C10140Tq.A0A(...)` вместо `A06(...)` (found); отличие не прослежено |
| Опции отправки | аргумент таймаута iq 32000 мс (`ContactQuerySync`) или 128000 мс (`ContactSyncHelper`); числовое `102` передаётся отправителю (смысл неизвестен) |

### 2.2 Режимы (found, `EnumC21780s1`)

| `mode` | Значение |
|--------|----------|
| `full` | полная пересинхронизация scope |
| `delta` | только изменения с последней синхронизации |
| `query` | запрос перечисленных пользователей, без изменения состояния |
| `download` | загрузка набора контактов с сервера |

### 2.3 Контексты (found, `EnumC21770s0`)

`metadata`, `registration`, `interactive`, `background`, `notification`, `message`, `add`, `voip`, `snapshot`, `wamo`.

### 2.4 Типы синхронизации (found, `EnumC21760rz`)

Имя, код на проводе, контекст / режим / scope. Коды 10-15 и 17-20 не используются. Scope `PB` = телефонная книга, `SL` = side list, `MP` = мультипротокольный запрос. Код логируется и сохраняется в метриках; stanza несёт только контекст и режим.

| Имена (код) | Контекст / режим | Scope |
|-------------|------------------|-------|
| `REGISTRATION_FULL` (0) | registration / full | PB+SL |
| `INTERACTIVE_FULL` (1), `INTERACTIVE_DELTA` (2) | interactive / full, delta | PB+SL |
| `BACKGROUND_FULL` (3), `BACKGROUND_DELTA` (4) | background / full, delta | PB+SL |
| `NOTIFICATION_CONTACT` (5) | notification / delta | PB |
| `INTERACTIVE_QUERY` (6), `ADD_QUERY` (9) | interactive / query, add / query | PB |
| `NOTIFICATION_SIDELIST` (7) | notification / query | SL |
| `INTERACTIVE_DELTA_SIDELIST` (8) | interactive / delta | SL |
| `BACKGROUND_QUERY_PICTURES` (16), `BACKGROUND_MULTI_PROTOCOL_QUERY` (21), `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` (22) | background / query | MP |
| `REGISTRATION_COMPANION_MULTI_PROTOCOL_QUERY` (23) | registration / query | MP |
| `INTERACTIVE_MULTI_PROTOCOL_QUERY` (24), `MESSAGE_MULTI_PROTOCOL_QUERY` (25), `VOIP_MULTI_PROTOCOL_QUERY` (26) | interactive, message, voip / query | MP |
| `NOTIFICATION_MULTI_PROTOCOL_QUERY` (27), `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY` (28) | notification / query | MP |
| `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` (29), `WAMO_MULTI_PROTOCOL_QUERY` (38) | message, wamo / query | MP |
| `CONTACT_DONWLOAD` (30, sic) | background / download | PB |
| `CONTACT_FORCE_UPLOAD` (31) | metadata / delta | PB+SL |
| `CONTACT_UPLOAD` (32), `NATIVE_CONTACT_DELTA` (39) | background / delta | PB |
| `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` (33) | background / full | PB |
| `CONTACT_UPLOAD_SNAPSHOT` (34), `CONTACT_DOWNLOAD_SNAPSHOT` (35), `CONTACT_FULL_SYNC_SNAPSHOT` (36) | snapshot / delta, download, full | PB, PB, PB+SL |
| `CONTACT_RESTORE_FULL_SYNC` (37) | background / full | адресная книга WA |

Хелперы: `A00()` = delta, `A01()` = full, `A02()` = full и registration. Только `BACKGROUND_QUERY_PICTURES` делает тип запроса picture равным `image`; все остальные типы просят `preview`.

---

## 3. Протоколы запросов

### 3.1 Обзор (found)

| Протокол | Дочерний элемент `<query>` | Дочерний элемент запроса по пользователю | Дочерний элемент ответа (по пользователю) | Примечания |
|----------|----------------------------|-------------------------------------------|--------------------------------------------|------------|
| contact | `<contact/>` | `<contact>+digits</contact>`, `<contact username=.. lid=.. pin=../>`, `<contact type="delete"/>`, пустой `<contact/>` | `<contact type="in\|out\|invalid">text</contact>` | только в `<list>` |
| sidelist | `<sidelist [addressing_mode="lid"]/>` | `<sidelist type="delete"/>` | `<sidelist type=..>` в `<side_list>` | пользователи вне адресной книги |
| status | `<status/>` | `<status t="secs"/>`, когда есть кэшированное время | `<status t code type>text</status>` | текст About |
| text_status | `<text_status/>` | нет | `<text_status last_update_time ephemeral_duration_sec text><emoji content/></text_status>` | флаг **5839** |
| picture | `<picture type="image\|preview" [size="N"]/>` | `<picture id="N"/>` кэшированный id | `<picture id direct_path hash/>` | с privacy-обогащением |
| business | `<business><verified_name/><profile v="N"/></business>` | `<business><verified_name serial/><profile tag/></business>` | `<business pn_jid><verified_name verified_level host_storage actual_actors privacy_mode_ts>cert</verified_name>...</business>` | `v` = AB **471** & 0x3FFC (по умолчанию 1140) |
| devices | `<devices version="2"/>` | `<devices device_hash ts expected_ts/>` | `<devices><device-list><device id key-index is_hosted/></device-list><key-index-list ts expected_ts>bytes</key-index-list></devices>` | раздел 5 |
| disappearing_mode | `<disappearing_mode/>` | нет | `<disappearing_mode duration t ephemerality_disabled/>` | `ephemerality_disabled` читается только с флагом **21235** |
| lid | `<lid/>` | `<lid jid="LID"/>`, когда у PN-пользователя есть известный LID | `<lid val="LID"/>` | раздел 6 |
| username | `<username/>` | `<username username="@known"/>` | `<username>text</username>` или `contact@username` | см. WA_USERNAME.md |

Атрибуты по пользователю в `<user>`: `jid` (PN или LID), `pn_jid` (записи side-list), `common_gid` (раздел 7). Пользователь может также содержать дочерний элемент `<tctoken>` с сохранёнными байтами токена. В ответах `<user>` имеет также `pn_jid` и `new_jid`; парсер берёт `jid`, при отсутствии `jid` использует `pn_jid`.

### 3.2 Contact (found)

| Форма | Условие | Примечания |
|-------|---------|------------|
| `<contact>+15550001111</contact>` | поиск по телефону | строка номера передаётся как дана вызывающим; для поиска по JID `C23638AId.A05` добавляет префикс `+`, когда JID — это JID номера телефона и (включён `C11980aQ.A0M()` / AB **26739** или тип `ADD_QUERY`) |
| `<contact>15550001111</contact>` | PN-пользователь с LID-адресацией (`C11980aQ.A0L()`, AB **14565**) | цифры без `+` |
| `<contact username="u" [lid=".."] [pin=".."]/>` | поиск по username | `lid` / `pin` только с AB **12402**, иначе только `username` |
| `<contact type="delete"/>` | запрос помечен удалённым | удаление из адресной книги при upload-синхронизации |
| `<contact/>` | LID-пользователь без username | заглушка |
| query `<contact addressing_mode="lid"/>` | AB **14565** | contact-синхронизация с LID-адресацией |
| query `metadata_version="3"` | тип delta и внутренний флаг | флаг в прочитанном пути присваивается только из константы false, поэтому, вероятно, никогда не отправляется (inferred) |

`type` в ответе: `in` = зарегистрирован (внутренний код 1), `out` = не зарегистрирован (2), `invalid` = номер недействителен (3); любое другое значение выбрасывает ошибку повреждённого потока. Текстовое содержимое каждого `<contact>` добавляется в список по пользователю.

Уровень результата `<result><contact version refresh integrity snapshot_recovery>`: `version` хранится в результате, секунды `refresh` идут в ожидание full-sync (раздел 9), `integrity` — `pass` (по умолчанию), `pending` или `timelock` (внутренние 1 / 2 / 3), `snapshot_recovery` (`pending` / `pass`) читается только с флагом **22410**.

### 3.3 Status и text status (found)

Обработка результата `<status>`: `type="fail"` с `code` 401 / 403 / 404 = скрыто приватностью (внутреннее состояние 2); прочий `fail` = сбой (0); непустой текст без ошибки = установлен (1, `t` * 1000 = время установки); пусто без ошибки и при выключенном флаге text-status = нет (3). Имена состояний — inferred.

При включённом флаге **5839** дочерний `<text_status>` переопределяет состояние 1 / 3: текст = `text`, emoji = `<emoji content>` (по умолчанию "", если отсутствует), время установки = секунды `last_update_time`, срок действия = время установки + `ephemeral_duration_sec`, если оно больше 0 (состояние 3). Скрытый статус (состояние 2) — это узел ошибки с 401 / 403 / 404, а не пустая строка.

### 3.4 Picture, business, disappearing mode (found)

| Протокол | Деталь запроса | Разбор ответа |
|----------|----------------|---------------|
| picture | `type="preview"` плюс `size` только когда AB `AbstractC36291cD.A06` больше 0 (ограничен 300); `id` по пользователю только при наличии кэшированного id | `id` (int, -1 при отсутствии `<picture>`), `direct_path`, `hash` |
| business | `profile v` = `C35756Fe7.A00()` = AB 471 & 16380; `serial` / `tag` по пользователю только из локальной строки business | `pn_jid` (заполняет PN у LID-пользователя и сохраняет пару LID-PN), `verified_name`: `verified_level`, `host_storage`, `actual_actors`, `privacy_mode_ts`, байты узла = сертификат |

---

## 4. Поиск контактов и обнаружение номеров телефонов

### 4.1 Одиночные запросы (found, `C23638AId`)

| Метод | Тип | Что собирает | Результат |
|-------|-----|--------------|-----------|
| `A0E(userJid, type, n)` | только `INTERACTIVE_QUERY` или `ADD_QUERY` | JID пользователя + contact, status, picture, business, disappearing_mode, lid, username; devices при **5751**; text_status при **5839** | `C43621q7` |
| `A0C` / `A0A(type, n, number)` | те же два типа | номер телефона как `<contact>`; тот же набор (status только когда вызывающий передаёт true) | `Pair(result, user)` |
| `A0B(type, n, number)` ("Lightweight") | любой | телефон + contact, lid; devices при **5751** | `Pair` |
| `A0D(type, numbers)` | любой | много номеров: contact, status, picture, business, disappearing_mode, lid; text_status при **5839** | массив пользователей |
| `A0F(lid)` | `INTERACTIVE_QUERY` | `<user jid=LID/>` + `<contact/><username/>` | username для LID |
| `A0G(username, key)` | `INTERACTIVE_QUERY` | username (+ key) как `<contact>`; также status, picture, business, disappearing_mode, lid, username только если **33609** равен false, text_status при **5839** | WA_USERNAME.md |

Защиты (found): проверка сети (результат `network_unavailable`), dedupe in-flight запросов в картах с ключом JID или номер (второй вызов возвращает "skip too frequent query", без временного окна), `sid` на каждый вызов, ожидание до 32000 мс, затем результат таймаута. При выключенном AB **14565** LID JID с известным номером телефона переписывается в этот номер до построения запроса (`AbstractC197018Zw.A0Y`; направление выведено из следующего шага с префиксом `+`, inferred).

### 4.2 Коды результата (`C43621q7`, имена выведены из использования)

0 `A04` сеть недоступна; 1 `A08` пропущено (нечего отправлять или слишком часто); 2 `A07` успех с изменениями (путь удаления контакта); 3 `A06` успех; 4 `A03` сбой (пустой результат, таймаут, ошибка); 5 `A05` rate limited (ошибка результата 429); 6 `A02` исключение. `A01()` истинно для 1, 2, 3. Пустой `<list>` с ошибкой contact-протокола 429 даёт 5, любой другой пустой список даёт 4.

### 4.3 Какие функции доходят до телефонной книги (found)

| Путь | Вход | Тип | Протоколы (`C21820s6`) |
|------|------|-----|------------------------|
| Фоновая полная синхронизация (только primary) | `C18230lP.A0F(reason)` | `BACKGROUND_FULL` | всё, кроме orgs |
| Принудительная полная синхронизация | хелпер `A01`, периодическая задача `RunnableC23953AUi` case 23 | `BACKGROUND_FULL`; companion: `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` | contact (`A0J`) или side list (`A0K`); companion: всё, кроме contact / side list (`A0D`) |
| Принудительная выгрузка, delta-выгрузка, загрузка | `A07(reason)`, `A0G(reason)`, `A0C()` | `CONTACT_FORCE_UPLOAD`, `CONTACT_UPLOAD`, `CONTACT_DONWLOAD` | contact + lid (`A0G`) |
| Изменились нативные контакты | `A0J(reason, jids)` | `NATIVE_CONTACT_DELTA` | всё, кроме orgs |
| Отложенная синхронизация после регистрации | `A0L` (pref `registration_contact_sync_delayed`) | `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` | contact + lid |
| Side contact при первом показе | `A0E(contact)` | primary: `INTERACTIVE_DELTA_SIDELIST`; companion: `INTERACTIVE_MULTI_PROTOCOL_QUERY` | всё, кроме orgs / всё, кроме contact, side list, orgs |

Наборы протоколов (константы `C21820s6`, found): `A0S` username; `A0G` contact + lid; `A0P` status; `A0Q` text status; `A0O` picture; `A0F` business; `A0H` devices; `A0E` business + devices; `A0N` payment; `A0I` disappearing mode; `A0L` lid; `A0M` orgs; `A0D` всё, кроме contact, side list, orgs; `A0R` как `A0D` без lid; `A0J` contact + набор `A0D`; `A0K` side list + набор `A0D`; `A0C` всё, кроме orgs. LID подразумевается, когда синхронизируется contact или side list.

`C21830s7` (SyncRequest) сохраняет опции как JSON: `sync_is_urgent`, `sync_only_if_changed`, `sync_only_if_registered`, `sync_clear_whatsapp_sync_data`, `sync_should_retry` и по одному булеву `sync_<protocol>` на протокол (found); значение по умолчанию в builder — retry int 5 (смысл inferred).

### 4.4 Поиск по уведомлениям (found)

Сервер присылает hash вместо номера; клиент его разрешает и выполняет запрос.

| Обработчик уведомления | Payload | Sync | Протоколы |
|------------------------|---------|------|-----------|
| `AnonymousClass145` (обновление контакта), `add` | до 2 дочерних элементов hash типа `pn` (по умолчанию) или `lid`; только primary | `NOTIFICATION_CONTACT` | всё, кроме orgs |
| то же, update | hash в base64 | `NOTIFICATION_SIDELIST` | status, picture, lid, username, text_status |
| `C1S0` уведомление status | атрибут `hash` (base64) | `NOTIFICATION_SIDELIST` (причина `NOTIFICATION_STATUS`) | только status |
| `C1S0` уведомление picture | атрибут `hash` | `NOTIFICATION_SIDELIST` (причина `NOTIFICATION_PICTURE`) | только picture |
| `AnonymousClass142` уведомление business (удаление без jid с `hash`) | hash в base64 | `NOTIFICATION_SIDELIST` (причина `NOTIFICATION_BUSINESS`) | набор business (константа не определена) |

Hash сопоставляется с локальными пользователями по `digest(user + "WA_ADD_NOTIF")`, сравниваемому по префиксу байтов (`AbstractC43461pq.A04`); алгоритм digest выбирает вызывающий (не прослежено). Инициированная сервером «принудительная синхронизация» (`RunnableC23951AUg`, причина `SERVER_FORACE_SYNC`) запускает `BACKGROUND_FULL` или companion-тип.

### 4.5 Синхронизация контактов через MEX-мутации (found, не USync)

Новое в этой сборке: Kotlin-синхронизация контактов (`com.whatsapp.contact.sync.kmp`, `.handler`) использует мутации `w:mex` вместо usync IQ. Конфиг `whatsapp-android-mex`, doc_ids из persist-id asset.

| Операция | doc_id | Переменные (found) | Ответ |
|----------|--------|--------------------|-------|
| `ContactsDeltaSyncMutation` | `28247314474869813` | `context` (`SEARCH`, `OSAB_IMPORT`, `EMAIL_IMPORT`, `QR_SCAN`), `primary_contacts_add[]`, `primary_contacts_remove[]` (`lid`, `modifier` = `BEST_EFFORT_DOWNGRADE_TO_WA_SIDE_CONTACT`, `normalized_phone`), `side_contacts_add[]` | `xwa2_contacts_delta_sync`: `results[]` {`client_cached_lid`, `failed`, `detail` (union: raw_pn / primary_normalized_phone / lid / phone_status; side_status; username_status; email_status; normalized_phone)}, `retry_after_seconds` |
| `PrimaryContactsFullSyncMutation` | `36963099086669113` | не прочитано | не прочитано |
| `SideContactsFullSyncMutation` | `26880700761604398` | `context`, `cursor`, `side_contacts[]` (`client_cached_lid`, `normalized_phone`) постранично | `results[]` как выше, `retry_after_seconds` |

Что разграничивает этот путь и путь usync, не найдено (unknown). `retry_after_seconds` — MEX-эквивалент usync `backoff`.

---

## 5. Синхронизация списка устройств, key index, ADV

### 5.1 Запрос и ответ (found)

Запрос: дочерний элемент query `<devices version="2"/>`; по пользователю `<devices device_hash="H" ts="T" expected_ts="E"/>`, отправляется только при наличии hash (`ts`, `expected_ts` только когда больше 0 и `expected_ts` больше `ts`). Значения берутся из локальной строки устройства (`C15070fj.A07/A00/A04`).

Ответ по пользователю: `<devices>` либо содержит `<error code text>` (пользователь получает состояние -1, лог "parseUser/partial error"), либо:

| Узел | Атрибуты | Разбирается в |
|------|----------|---------------|
| `<device-list><device .../>` | `id` (int), `key-index`, `is_hosted` | `DeviceJid(user, id)` -> key index; несовпадение hosted-состояния JID и `is_hosted` сообщает `invalid-hosted-flag` |
| `<key-index-list ts expected_ts>` | `ts` (секунды), `expected_ts` (по умолчанию 0), байты содержимого | подписанный список key-index, хранится как есть |

`<devices>` уровня результата может нести `<error>` с backoff (раздел 9). Маршрут MEX: `include_devices` плюс `devices{hash, timestamp, expected_timestamp}`; метки клиентского лога для отброшенных результатов: `devices_dropped_status_error`, `devices_status_indeterminate`, `devices_hash_match_noop`, `devices_dropped_empty_without_hash`, `devices_dropped_no_jid`, `devices_dropped_stale_timestamp`, `devices_dropped_adv_proto_missing`, `devices_dropped_adv_verify_failed`, `devices_dropped_adv_data_update_failed`, `devices_outcome_unset`.

### 5.2 Проверки обновления (found, `C51909N4g`, `C24230w2`)

| Проверка | Поведение |
|----------|-----------|
| список key-index пуст | "update keyIndex is empty", без обновления |
| `ts` ответа старше сохранённого | "timestamp is less than existing one", отбрасывается |
| повтор устаревшего expected-ts | ts ответа ниже сохранённого, `expected_ts` равен сохранённому ts, а сохранённое значение старше pref `adv_last_device_job_ts`: логируется ошибка usync fetch и эмитируется WAM-событие `wam_adv_expected_ts_unavailable` (`C49716Ltt`), возвращается true (эффект у вызывающего не прослежен) |
| информация о новом устройстве | `C51909N4g.A00` очищает сохранённый expected ts, когда новый ts не меньше сохранённого; тип аккаунта выводится из набора устройств (`C9U.A01`) |

### 5.3 Проверка подписанного ADV key-index (found, `C24230w2.A07`, `A04`)

| Шаг | Деталь |
|-----|--------|
| Parse | байты key-index -> `ADVSignedKeyIndexList` (`C25786BAu`): `details` (**1**), `account_signature` (**2**), `account_signature_key` (**3**, необязателен) |
| Публичный ключ | идентичность primary-устройства из локального identity store; если proto несёт `account_signature_key` и он отличается от локального ключа, используется этот ключ с пометкой `adv`; без обоих ключей: предупреждение "no primary identity" |
| Подпись | проверка `account_signature` над `{0x06, 0x02} || details` выбранным ключом (`AbstractC30195DBc.A08`); при сбое лог "fail to verify account signature" и WAM-событие (`C55912St`, 1 = локальный ключ, 2 = adv-ключ) |
| Details | `details` -> `ADVKeyIndexList` (`BCB`): `raw_id` (**1**), `timestamp` (**2**), `current_index` (**3**), `valid_indexes` (**4**), `account_type` (**5**) |
| Совпадение timestamp | `details.timestamp` должен равняться атрибуту `ts`, иначе "advTimestampMismatch" + WAM-событие `C2TD`, результат отклоняется |
| Возраст | если `ts` старше `min(35, AB 730)` дней (по умолчанию 35) и в `valid_indexes` более 1 записи: "advListTimestampInvalid", отклоняется |
| Raw id | `raw_id` отличается от сохранённого: "incoming key-index not matching local state, resetting"; собственный аккаунт на companion логирует `device_self_invalid_index_list`; другие пользователи: `C15070fj.A0G(user, "adv_key_index_list_validation_failed")`, когда новый список не разобран (эффект не прослежен) |
| Фильтрация | `filterDeviceWithKeyIndexList` (`C24230w2.A08`) оставляет устройство, если оно primary либо его `key-index` больше 0 и есть в `valid_indexes`; иначе оно отбрасывается с WAM-событием (`C55932Sv`, 1 при индексе 0). Больший сохранённый индекс даёт только предупреждение |

### 5.4 Задачи синхронизации устройств (found)

`DeviceSyncManager.A03(jids, type)` ставит в очередь `SyncDevicesJob` (пропускает пользователей, уже находящихся в обработке; ожидающие пользователи переживают перезапуски в pref `pending_users_to_sync_device`). `syncType` выбирает тип синхронизации:

| `syncType` | Тип синхронизации | Контекст | Откуда вызывается (found) |
|------------|-------------------|----------|---------------------------|
| 0 / по умолчанию | `INTERACTIVE_MULTI_PROTOCOL_QUERY` | interactive | — |
| 1 | `MESSAGE_MULTI_PROTOCOL_QUERY` | message | `SyncDevicesAndSendInvisibleMessageJob` (путь отправки в группу `C22300su`, размер группы между AB 934 и AB 1946, одна задача на ключ сообщения) |
| 2 | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | notification | синхронизация аккаунта собственных устройств (`C41431mS`) |
| 3 | `BACKGROUND_MULTI_PROTOCOL_QUERY` | background | входящее сообщение или статус с неудачной проверкой ADV-отправителя (`DecryptMessageRunnable` / `StatusProcessingRunnable`, лог `invalid adv sender`), несовпадения ADV-метаданных (`C24230w2`), повтор ожидающих пользователей |
| 4 | `VOIP_MULTI_PROTOCOL_QUERY` | voip | настройка шифрования звонка для неосновного устройства (`C1A`, лог `voip/encryption/schedule usync`) |
| 5, 6 | `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY`, `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` | notification, message | не прослежено |

Запросы только devices используют `C21820s6.A0H`. `handleADVMetadata` (`C24230w2.A0A`) также запускает обновление типа 3, когда ADV-метаданные входящего сообщения сообщают hosted-тип аккаунта, расходящийся с локальным состоянием (устройства предварительно очищаются), или более новый timestamp, чем сохранённый.

---

## 6. Маппинг LID

| Механизм | Деталь (found) |
|----------|----------------|
| протокол `lid` | query `<lid/>`; `<lid jid=known LID/>` по пользователю только когда у PN-пользователя уже есть сохранённый LID; ответ `<lid val="LID"/>` сохраняется в результате пользователя |
| Запись маппинга | `N27.A03(users)`: LID = `new_jid` (если это JID типа LID), иначе результат `lid`, иначе `jid` пользователя, если это LID; PN = `pn_jid`, иначе `jid` пользователя, если это PN; пары идут в хранилище маппинга LID-PN одним пакетом |
| Business `pn_jid` | LID-пользователь без PN получает PN из `<business pn_jid>`; пара сохраняется |
| Side list | пользователи запроса несут `jid` = LID и `pn_jid` = PN при включённой LID-адресации (`C11940aM.A05`, разрешается через `C11500Zc.A00`, id флага не прослежен); fallback-и логируют `Sidelist: No LID provided`, `waContact_null`, `usernameLid_null` |
| Починка отсутствующего LID | `MissingLidHandler` (`C32M`): `requestSyncDevicesAndLidIfMissingLids` ждёт 32000 мс запрос `MESSAGE_MULTI_PROTOCOL_QUERY` с протоколом lid, прежде чем продолжить внешней точке входа |
| Наблюдатель маппинга | `ContactJidMapObserver` (`C0ZA`): когда появляется пара LID-PN и существует устаревший контакт, добавляет заменяющий контакт и ставит в очередь `BACKGROUND_DELTA` с причиной `LID_REQUEST` |

Почему важен отсутствующий LID: контакт только с PN нельзя адресовать при LID-first отправке; запрос заполняет пару без полной синхронизации (inferred из мест вызова).

---

## 7. Privacy-обогащение (tctoken, общая группа)

`ProfilePrivacyEnrichmentFetcher` (`C223659jg.A00`, метка лога `ContactSyncHelper.privacyEnrichment`) проходит по списку запросов перед отправкой. Для каждого пользователя он получает (a) сохранённый privacy-токен с его timestamp (`C14820fK.A0M`, отбрасывается, если старше `C14820fK.A04.A02()`), (b) при отсутствии действительного токена — JID группы, общей с пользователем (`C197178aC.A04` / массовый поиск, нужен собственный LID). Результат `C197148a9{ token C9oI, commonGroup, flag }`.

| Выход | Classic usync | MEX `UsyncQuery` |
|-------|---------------|------------------|
| token | `<tctoken>token bytes</tctoken>` как дочерний элемент `<user>` | `privacy_token{tctoken, timestamp}` |
| общая группа | атрибут `common_gid="..."` у `<user>` | `common_group` |

Применяется только к запросам, которые просят picture или status (AB **9667**, по умолчанию true), text status (**20798**, по умолчанию false), devices (**29769**), contact (**29770**), lid (**29771**) (флаги по умолчанию false, кроме 9667). Без токена и без общей группы сервер всё равно может ответить, но может опустить picture или status (inferred; серверное правило unknown). Выдача токена и `cstoken` описаны в WA_TCTOKEN_CSTOKEN.md.

Связанное: `PRIVACY_TOKEN_REFRESH` (`C735439k`) выдаёт `BACKGROUND_QUERY_PICTURES` с набором только picture `A0O` пакетами по 10 пользователей (found); что цель — обновить ассоциацию токена, выведено из названия причины (inferred).

---

## 8. MEX `UsyncQuery` и маршрутизация протоколов

### 8.1 Операция (found, `C229259vZ.A01`)

Операция `w:mex` `UsyncQuery`, doc_id `38635300486116501` (persist-id asset), класс ответа `C2IQ`. Конверт как в WA_USERNAME.md 2.2.

| Переменная | Источник |
|------------|----------|
| `query_input[]` | по пользователю: JID, `client_known_username`, `about_status{dhash}`, `picture{id}`, `business{serial, tag}`, `devices{hash, timestamp, expected_timestamp}`, `privacy_token{tctoken, timestamp}`, `common_group` |
| `telemetry.context` | строка контекста в нижнем регистре |
| `include_username`, `include_reachability`, `include_linked_profiles`, `include_lid`, `include_about_status`, `include_picture`, `include_biz`, `include_ddm`, `include_devices`, `include_orgs` | булевы, ставятся, когда протокол запрашивает любой пользователь |
| `picture_field_input` | `type` `IMAGE` или `PREVIEW`, `preview_px` для превью |
| `business_input` | `include_profile`, `include_vname`, `profile_version` |

Через MEX не передаются: contact и text_status. Только в MEX: reachability, linked profiles, orgs, ddm (disappearing mode). Детали ответа, кроме username и lid (WA_USERNAME.md), не читались (unknown).

### 8.2 Когда используется MEX (found, `C18580m0`)

1. AB **37780** (int, по умолчанию 0) ненулевой: маршрутизация по протоколам. Старшие 16 бит = битовая маска, маршрутизируемая через classic usync (`SMAX`), младшие 16 бит = маска, маршрутизируемая через MEX; иначе `DROP`. Биты (`M5H`): status 4, picture 8, business 16, devices 32, disappearing_mode 128, username 512, text_status 1024, orgs 2048. Биты уровня запроса 1 (contact), 2 (`C70582ym.A07`, вероятно side list, inferred) и 256 идут как маска «identity». Протокол, который выбранный маршрут передать не может, получает `DROP`: text_status в MEX, orgs в SMAX. Строка лога: `ContactSyncHelper/read_route type=.. contacts=.. identity=..,.. failed=..`.
2. Иначе при AB **33432** (по умолчанию false): classic-запрос для основного запроса, затем «mex profile follow-up» (`..._mex_profile`) для devices, с маркером метрик, аннотированным `requested_users`, `is_delta_sync`, исходом `success`, `partial_success`, `no_result`, `timeout`, `exception`, `interrupted`.
3. Иначе `A0F` решает по запросу: MEX отклоняется, когда запрос содержит contact или text_status ("cantUseMex"), нужен AB **9732** для business и AB **8421** для username; остальное может идти через MEX (`C229259vZ`), с ожиданием 128000 мс.

Состояние по умолчанию в этой сборке: 37780 = 0, 33432 = false, 9732 = false, 8421 = false, поэтому USync работает через classic stanza, если серверный AB-override не изменит это.

---

## 9. Лимиты частоты, ошибки, backoff

### 9.1 Формы ошибок (found)

| Где | Форма | Кем разбирается |
|-----|-------|-----------------|
| ошибка iq | `<iq type="error"><error code backoff/></iq>` | `Brt`: `code`, секунды `backoff` * 1000 с ограничением 3600000 мс (-1 при отсутствии); вызывает `BIz(type, sid, code, backoffMs)`, завершает future значением null |
| сбой доставки | callback транспорта | `Bog`: future завершается ошибкой `C216419Uc`; сбрасывается состояние синхронизации по JID (`C502424l.A01`) |
| ошибка протокола | `<result><PROTO><error code text backoff/></PROTO></result>` | `C18670m9.A01`: секунды `backoff` * 1000, по умолчанию 7200 с, ограничение 3600000 мс (1 ч); логирует `connection/unisynciq/parse/<proto>/error` |
| успех протокола | `<PROTO refresh="n"/>` | секунды `refresh` * 1000 |
| частичная ошибка пользователя | `<devices><error code text/></devices>` | состояние -1, пользователь сохраняется |
| ошибка MEX | ошибка GraphQL, поле пути `<proto>_info`, необязательная строка backoff | `C229259vZ.A00`: backoff по умолчанию **7200**, ограничение 3600000, без умножения на 1000 в этом пути (единицы неясны, unknown) |
| ключ username | коды `42901` (requestor) и `42902` (requestee) в результате contact | `C23638AId.A0G`, см. WA_USERNAME.md |

Коды, встречающиеся в клиентской логике: `429` (rate limit: результат синхронизации 5), `503` (глобальный backoff), `42901`, `42902`.

### 9.2 Хранилище backoff (found, файл prefs `contact_sync_prefs`, `C18800mM`)

| Ключ | Когда записывается | Значение |
|------|--------------------|----------|
| `contact_sync_backoff` | любая ошибка iq / contact-протокола с backoff больше 0 (`X.0m7.BIz`, `AO4.BIz`) | now + backoff мс |
| `delta_sync_backoff` | то же, режим delta и код 429 | now + backoff |
| `global_backoff_time` | то же, код 503 | now + backoff |
| `sidelist_sync_backoff` | callback `ContactQuerySync` `AO2.BIz` при **любой** ошибке с backoff больше 0 | now + backoff; код 503 также ставит `global_backoff_time` (имя ключа не соответствует scope синхронизации; found) |
| `contact_full_sync_wait`, `status_full_sync_wait`, `sidelist_full_sync_wait` | атрибут `refresh` результата протокола | мс; не задано = 86400000 (24 ч) |
| `status_`, `picture_`, `business_`, `devices_`, `disappearing_mode_`, `lid_`, `username_`, `text_status_`, `reachability_` `sync_backoff` | backoff ошибки результата протокола в `BJ0` | now + backoff |
| `last_contact_full_sync`, `last_status_full_sync`, `last_sidelist_full_sync` | завершение полной синхронизации | timestamp |

`C18800mM.A02()` сбрасывает в -1 ключи contact, sidelist, status, picture, business, devices, delta, disappearing_mode, lid, reachability и global; `username_sync_backoff` и `text_status_sync_backoff` в этом списке отсутствуют (found).

Читатели, найденные поиском по строкам: `reachability_sync_backoff` (`C18580m0`), `text_status_sync_backoff` (`C3MA`), три ключа `*_full_sync_wait` и `last_*_full_sync` (периодическая задача: полная синхронизация назначается, когда `wait - now + last` не больше 1800000 мс, 30 мин). Читателей `contact_sync_backoff`, `delta_sync_backoff`, `global_backoff_time` и других ключей по протоколам не найдено (unknown, не строит ли проверка ключ динамически).

### 9.3 Локальные лимиты (found)

Dedupe in-flight: один `querySyncJid` на JID, один телефонный запрос на номер. Таймауты: 32000 мс одиночный запрос, 128000 мс пакетный, 180 с для ожидания callback `C18230lP.A00` (без ограничения при `C11980aQ.A09`). Ограничение backoff 3600000 мс. Пакеты обновления privacy-токена по 10 пользователей. Серверные лимиты запросов на аккаунт и на номер неизвестны.

---

## 10. Что запускает USync

Причина = значение `EnumC21800s4` (клиентская метка, используется для планирования и метрик). Тип = тип синхронизации.

| Клиентская функция | Причина | Тип | Протоколы |
|--------------------|---------|-----|-----------|
| Регистрация завершена | `REGISTRATION_FULL` (`C25100xS`, `CJ8`) | `REGISTRATION_FULL` (код 0) | набор contact (companion-вариант не прослежен) |
| Онбординг контактов | `NC_ONBOARDING` | `A0G` delta-выгрузка (`CONTACT_UPLOAD`) | contact + lid |
| Изменилась адресная книга устройства (только primary) | `DEVICE_ADDRESS_BOOK_CHANGE` | срочная on-change delta (`C18230lP.A02`) | не прослежено |
| Периодическая и принудительная полная синхронизация | `PERIODIC_FORCE_SYNC`, `FORCE_SYNC` | `BACKGROUND_FULL` | contact / side list |
| Открытие выбора контакта | `CONTACT_PICKER_FULL_SYNC`, `CONTACT_PICKER_USYNC_RETRY` | `INTERACTIVE_FULL` | не прослежено |
| Добавление контакта, новый чат по номеру, deep link, чат без контакта | причины `*_CONTACT_ADD` существуют; не привязаны к пути запроса | `ADD_QUERY` (`C9AA`) / `INTERACTIVE_QUERY` (`C9AQ`, `C9AY`, `AWR`, `A1P`) | см. 4.1 |
| Открытие чата с несохранённым пользователем или business | `CONVERSATION_SIDE_CONTACT`, `SIDELIST_REQUEST` | телефонный запрос (`INTERACTIVE_QUERY`) при AB **20988** (по умолчанию true), иначе `INTERACTIVE_DELTA_SIDELIST` | см. 4.1 / 4.3 |
| Отправка сообщения в список рассылки | `LID_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | lid |
| Отправка группового сообщения (размер в пределах AB 934..1946) | `DEVICE_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | devices |
| Входящее сообщение с неудачной проверкой ADV-отправителя, несовпадение ADV-метаданных | `DEVICE_REQUEST` | `BACKGROUND_MULTI_PROTOCOL_QUERY` | devices |
| Настройка шифрования звонка | `DEVICE_REQUEST` | `VOIP_MULTI_PROTOCOL_QUERY` | devices |
| Синхронизация собственного аккаунта | `DEVICE_REQUEST` | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | devices |
| Push с сервера: изменение contact, status, picture, business, username | `NOTIFICATION_*`, `USERNAME_UPDATE_NOTIFICATION` | `NOTIFICATION_CONTACT` / `NOTIFICATION_SIDELIST` | по уведомлению |
| Обновление disappearing-mode и text-status | `DM_FORCE_REFRESH`, `TEXT_STATUS_FORCE_REFRESH` | `BACKGROUND_MULTI_PROTOCOL_QUERY` (text status также `BACKGROUND_FULL`) | disappearing_mode / text_status |
| Переключение аккаунта | `ACCOUNT_SWITCH_REFRESH` | `BACKGROUND_FULL` | не прослежено |
| Обновление privacy-токена | `PRIVACY_TOKEN_REFRESH` | `BACKGROUND_QUERY_PICTURES` | picture |
| Изменение маппинга LID-PN | `LID_REQUEST` | `BACKGROUND_DELTA` | всё, кроме orgs |
| Business-чат (добавлено сообщение, звонок) | `BUSINESS_CONTACT_CHAT` (`C0LX`, `RunnableC23932ATn`) | `BACKGROUND_MULTI_PROTOCOL_QUERY` / `VOIP_MULTI_PROTOCOL_QUERY` | не прослежено |

---

## 11. Feature-флаги

Id AB-prop в том виде, как они читаются в местах вызова; значения по умолчанию из таблиц конфигурации этой сборки. ID флагов выделены жирным.

| Флаг | Тип | По умолчанию | Что контролирует |
|------|-----|--------------|------------------|
| **5751** | bool | false | запрос devices в contact-запросах и запросах по номеру телефона |
| **5839** | bool | false | протокол text_status (запрос и разбор) |
| **9667** | bool | true | privacy-обогащение для запросов picture / status |
| **20798** | bool | false | privacy-обогащение для text_status |
| **29769**, **29770**, **29771** | bool | false | privacy-обогащение для запросов devices, contact, lid |
| **9732** | bool | false | business через MEX |
| **8421** | bool | false | username через MEX |
| **37780** | int | 0 | маски маршрутизации протоколов (старшие 16 SMAX, младшие 16 MEX) |
| **33432** | bool | false | разделение: classic-запрос + MEX profile follow-up |
| **12402** | bool | false | `lid` и `pin` в `contact` для username |
| **14565** | bool | false | `addressing_mode="lid"` в contact, PN-текст только из цифр |
| **26739** | bool | false | префикс `+` у номеров телефонов |
| **471** | int | 1140 | business `profile v` (маскируется 0x3FFC) |
| **730** | int | 35 | максимальный возраст ADV key-index в днях (ограничен 35) |
| **31261** | bool | false | добавляет известный `@username` для каждого пользователя (`C223639je`) |
| **33609** | bool | true | при true запрос по key-entry опускает `<username/>` |
| **20988** | bool | true | телефонный запрос вместо side-list синхронизации в несохранённом business-чате |

---

## 12. Baileys (`baron-baileys-v2`, сравнение с его `src/WAUSync` и `Socket/socket.js`)

| Тема | Baileys | Android 2.26.41.6 |
|------|---------|-------------------|
| конверт | `iq to=s.whatsapp.net type=get xmlns=usync` + `usync{context, mode, sid, last="true", index="0"}` | те же атрибуты; `to` подразумевается |
| режимы | `query` (по умолчанию), `delta` | также `full`, `download` |
| контексты | `interactive` (по умолчанию), `background`, `message`; `voip` встречается в его правиле backoff | плюс `registration`, `notification`, `add`, `voip`, `metadata`, `snapshot`, `wamo` |
| протоколы | добавляет `bot`, `feature`, `sidelist` как дочерний элемент query | нет дочерних `bot` / `feature`; пользователи sidelist идут в `<side_list>` |
| contact | `<contact>phone</contact>`, username с `pin` / `lid`, `type` | телефон с `+`, `type="delete"`, username |
| статус скрыт | `code="401"` у `<status>` даёт `''` | `type="fail"` с 401 / 403 / 404 |
| privacy-доказательство | `<tctoken>` только под протоколом status, когда у пользователя есть токен | `<tctoken>` для picture / status / прочих и `common_gid` |
| backoff | секунды `error backoff` * 1000, без ограничения | ограничен 1 ч |

| Симптом (inferred) | Причина | Исправление |
|--------------------|---------|-------------|
| picture / status отсутствуют у не-контактов | нет tctoken, нет `common_gid` | прикладывать сохранённый `<tctoken>` или JID общей группы для каждого пользователя |
| список устройств отклонён | проверки `ts` / `raw_id` key-index из раздела 5.3 | проверить, что `ts` равен подписанному `details.timestamp` |
| backoff игнорируется | Baileys использует серверное значение без ограничения | ограничить 1 ч, ждать по протоколу |

---

## 13. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| `ContactQuerySync/querySyncJid: rate-limit-error` | ошибка результата contact 429, пустой список | подождать возвращённый `backoff`, снизить частоту запросов |
| `connection/unisynciq/parse/<proto>/error` | узел ошибки по протоколу | сохранять `backoff` только для этого протокола |
| `handleSyncContactError ... code=503` | перегрузка сервера | глобальный backoff, повторить позже |
| `sidelist-jid-absent-from-response` | сервер опустил запрошенного пользователя side-list | клиент помечает пользователя как синхронизированного, чтобы избежать цикла |
| `contactsyncDevicesupdater/update/verifyADVSignedKeyIndexList fail` | не пройдена проверка подписи, proto или timestamp | строка устройства не обновляется, обновление ставится в очередь |

---

## 14. Ключевые различия

| Не путать | Деталь |
|-----------|--------|
| тип синхронизации vs причина | тип (`EnumC21760rz`) выбирает режим, контекст, scope; причина (`EnumC21800s4`) — лишь метка для планирования и метрик |
| `list` vs `side_list` | пользователи адресной книги vs пользователи вне адресной книги (side contacts) |
| usync vs MEX `UsyncQuery` vs MEX-мутации contact | три транспорта для связанных данных; флаги маршрутизации в 8.2 и 4.5 |
| результат `<devices>` vs подписанный key index | список устройств не считается доверенным, пока подписанный список не пройдёт проверку (5.3) |
| `refresh` vs `backoff` | `refresh` = как долго можно переиспользовать хороший результат, `backoff` = как долго держаться в стороне после ошибки |

---

## 15. Полный поток

```
[Feature]         [ContactSyncMethods]            [UniSync builder / MEX]                [Server]
  │ trigger (10)         │                                  │                               │
  ▼                      ▼                                  │                               │
 reason + type ──► SyncRequest (protocol set, users)        │                               │
                         │ enrich: tctoken / common_gid (7) │                               │
                         │ route per protocol (8)           ▼                               │
                         └──► classic: <iq xmlns=usync><usync sid index last mode context> ─►│
                         └──► MEX: w:mex UsyncQuery {query_input, include_*} ───────────────►│
                                                            │◄── <usync><result> per protocol│
                                                            │     <list> <side_list>         │
                                                            ▼                               │
                    parse: contact in/out, status, picture, business,                       │
                           devices + key-index-list, lid val, username                      │
                                  │                                                         │
        ┌─────────────────────────┼─────────────────────────┐                               │
        ▼                         ▼                         ▼                               │
 devices: verify ADV sig,   LID/PN pairs ──► mapping   result errors: 429 / 503 / backoff   │
 ts, raw_id, valid_indexes  store (N27.A03)            ──► prefs; refresh ──► full_sync_wait │
        │ ok                                                                                │
        ▼                                                                                   │
 device rows updated ──► message fan-out, call setup, side-list chats use the new data      │
```

---

## 16. Неизвестное

| Тема | Причина |
|------|---------|
| атрибут `to` у iq | добавляется отправителем; отправитель не прослежен |
| Отличие `C10140Tq.A0A` (registration) от `A06` | не прослежено |
| Серверные правила частоты запросов, лимитов на номер, какие протоколы может читать запрашивающий | клиент видит только коды ошибок |
| Читатели `contact_sync_backoff`, `global_backoff_time`, `delta_sync_backoff` | читатель по строке не найден |
| Единицы backoff в MEX | нет `* 1000` в `C229259vZ.A00` |
| Какой маршрут побеждает в production | все флаги маршрутизации по умолчанию выключены в этой сборке; серверные значения AB неизвестны |
| Фактический трафик | только статический анализ |
