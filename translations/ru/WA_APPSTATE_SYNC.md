<!-- src-sha1: f9c1d644c604d99d2f1b54082218c3f75d2cf8a7 -->
# WhatsApp Синхронизация App-State — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** синхронизация app-state (syncd) на Android: пять коллекций, IQ `w:sync:app:state`, патчи / снапшоты / внешние blob, мутации SET/REMOVE, вывод ключей мутаций и шифрование записей, index / value MAC, LT-Hash, MAC снапшотов и патчей, sync-ключи (генерация, share, request, истечение), валидация исходящих и входящих данных, каталог sync-действий (96 действий: chat, label, contact, nctSalt …), обработка фатальных ошибок и повторов, восстановление снапшота, feature-флаги, сравнение с Baileys

---

## 1. Что это (технически)

Синхронизация app-state реплицирует небольшое состояние аккаунта (mute, pin, archive, star, контакты, метки, настройки …) между основным телефоном и каждым связанным устройством. Сервер хранит только сквозно зашифрованные записи, упорядочивает их по коллекциям и отдаёт версионированные патчи. Все утверждения основаны на статическом анализе декомпилированного APK; на проводе ничего не перехватывалось. Уровни: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не выяснено. Обфусцированные имена заново определены в 2.26.41.6 по стабильным строкам (`WhatsApp Mutation Keys`, `WhatsApp Patch Integrity`, `w:sync:app:state`, имена коллекций, префиксы логов).

| Сущность | Имя в 2.26.41.6 | Роль |
|----------|-----------------|------|
| Менеджер синхронизации | `C12440bB` (`sync-manager/*`) | планирование, `A0S` фатальный сбой, `A0Q` удаление всех данных |
| Обработчик запросов / построитель IQ / парсер | `C53148Nnt` / `C46361ux` / `N90` | отправка IQ, сборка `<sync>`, разбор результата |
| Устаревший обработчик ответов | `SyncResponseHandler` (`consumer/companiondevice/p049iq`) | устаревший путь применения, обработка фатальных ошибок `A08` |
| Движок KMP | `com.whatsapp.kmp.syncd.syncdengine.*` | `OutgoingProcessor`, `IncomingProcessor`, `SyncdResponseHandler`, `SyncdResponseProcessor`, `CollectionHandler`, `crypto/*` |
| Enum коллекций / enum действий | `EnumC24862AnK` / `EnumC24865AnN` | 5 коллекций / 96 wire-имён действий |
| Действие в коллекцию | `AbstractC24863AnL.A00` | switch по ordinal |
| Базовый класс мутации / обработчика | `AbstractC24864AnM` / `AbstractC25077Aqp` | ожидающая мутация / обработчик действия |
| Менеджер ключей / хранилище | `C12800bm` (`SyncdKeyManager`) / `C13620d6` (таблица `crypto_info`) | генерация, share, request, истечение, сохранение ключей |
| Key id / ключ / данные ключа | `CGH` / `C51259MoT` / `C51361MqC` | 6-байтовый id / id + данные / данные, отпечаток `C8H`, ts |
| Ключи мутаций | `MhX` | результат HKDF, 5 срезов |
| Носители share / request | `C26102BPk` (FMessage 38) / `C26101BPj` (39) | peer-сообщения |
| LT-Hash, HKDF | `AbstractC50511MVx.A00` + `KmpLtHash16`, `AbstractC38961i0` | 128-байтовый хеш, RFC 5869 |
| Криптография (устаревшая / KMP) | `C52959NkE` / `KmpSyncdCryptoHelper`, `KmpSyncdEncryptor`, `KmpSyncdDecryptor`, `KmpSyncdIncomingAntiTamperingValidator` | идентичные формулы |
| Внешние blob | `C17650kB` (загрузка), `KmpExternalMutationsUploaderImpl` | тип MMS `md-app-state` |
| Bootstrap / delete-all / восстановление | `C24986ApL` / `C17630k8` / `KmpSyncdFatalErrorRecovery` | конечный автомат, `delete_all_data`, выдача снапшота |
| Виды фатальных ошибок / устаревшее исключение | `Lx6` / `C49784Lv2` | 70 именованных видов / int `errorCode` |

Две реализации одного протокола сосуществуют. Движок KMP выбирается тремя управляемыми сервером булевыми флагами, значения которых по умолчанию в скомпилированном коде равны **false** (**15909** crypto, **20682** incoming, **18234** outgoing, раздел 12). Какой путь используется на конкретном аккаунте, неизвестно. Формулы MAC и шифрования в обоих путях идентичны (сопоставлены в `C52959NkE` и `KmpSyncd*`).

Основное и companion-устройство выполняют один и тот же код. Найденные различия: только основное создаёт мутации `contact` / `lid_contact` (`Companion cannot create contact mutations`); только companion отправляет `return_snapshot="true"`; обработка фатальных ошибок различается (11.3).

---

## 2. Коллекции

| Wire-имя | Ordinal enum | Критическая | Бит лога (`C17530jy.A00`) | Действия |
|----------|--------------|-------------|---------------------------|----------|
| `regular` | 0 | нет | 3 | 35 |
| `regular_low` | 1 | нет | 5 | 36 |
| `regular_high` | 2 | нет | 4 | 19 |
| `critical_block` | 3 | да | 1 | 4 |
| `critical_unblock_low` | 4 | да | 2 | 2 |

Критическое множество = `{critical_block, critical_unblock_low}` (`EnumC24862AnK.A01`). `A00()` отображает ordinal в 1..5; потребитель не прослежен.

На Android `critical_block` содержит действия настроек аккаунта (`setting_pushName`, `setting_locale`, `setting_securityNotification`, `generated_wui`), **а не** список блокировок; `contact` и `lid_contact` находятся в `critical_unblock_low`. Ни одно действие из 96 в enum не названо по признаку блокировки (found).

**Bootstrap (companion, частично inferred).** `syncd_bootstrap_state` (`C24986ApL`) проходит 0 → 4. Found: критическое множество синхронизировано → состояние 2 и сигнал «critical blocking complete»; все некритические коллекции синхронизированы → состояние 4; состояние 3 — шаг history sync (inferred). Причины сбоя: `critical_sync_timeout`, `history_sync_failure`, `syncd_failure`; лог watchdog `syncd-critical-bootstrap-timeout`. На основном устройстве при сопряжении companion выполняется `prepareCriticalDataUpload`: history sync, затем `shareAllKeys`; если ключа нет и включён флаг **27528**, сначала генерируется ключ.

---

## 3. Уровень IQ

### 3.1 Запрос (found, `C46361ux`)

```xml
<iq to="s.whatsapp.net" xmlns="w:sync:app:state" type="set" id="…">
  <sync data_namespace="3">
    <collection name="regular_low" order="1" version="41" return_snapshot="true">
      <patch>…SyncdPatch bytes…</patch>
    </collection>
  </sync>
  <coex><bot>…enc node…</bot></coex>      <!-- optional -->
</iq>
```

| Атрибут | Значение |
|---------|----------|
| `data_namespace` | константа `3` на `<sync>` |
| `order` | `0` для `critical_unblock_low`, иначе `1`; значение неизвестно |
| `version` | локально сохранённая версия коллекции (`C17540jz.A02`); опускается, если её нет |
| `return_snapshot` | `"true"` только для companion с версией null или 0 |
| `<patch>` | только если есть ожидающие локальные мутации |
| `<coex><bot>` | coexistence-v2: используемые sync-ключи шифруются для бота (`sync-request-handler/coexv2 *`); при ошибке IQ уходит без него, а ключи передаются вне основного канала |

Тайм-аут 32 с; один IQ может содержать несколько коллекций.

### 3.2 Результат (found, `N90`)

```xml
<iq type="result"><sync>
  <collection name="X" type="error"><error code="409" text="…"/> [<patches>…]</collection>
  <collection name="X" version="42"/>                    <!-- outgoing patch acked -->
  <collection name="X" has_more_patches="true">
    <snapshot>ExternalBlobReference bytes</snapshot>    <!-- companion bootstrap -->
    <patches><patch>SyncdPatch bytes</patch>…</patches>
  </collection>
</sync></iq>
```

Отсутствие `<sync>` или пустое тело `<snapshot>` / `<patch>` → временный сбой. Коллекция без версии, патчей и снапшота сохраняется как голое имя (значение inferred: ничего нового). Тела снапшотов — всегда `ExternalBlobReference`, никогда не встроенные записи.

Ошибки коллекции (`M4T`): -1 `UNKNOWN` повторяемая; 400 / 404 / 405 / 406 фатальные (`Xmpp*ForCollection`); 409 `CONFLICT` применить приложенные патчи и повторить, иначе повторяемая (условие ветки в декомпиляте неоднозначно); 500 повторяемая.

Глобальная ошибка IQ (`C53148Nnt.Brt`, `backoff` в секундах):

| Код | Обработка |
|-----|-----------|
| 400, 404, 405, 406 | фатальная; устаревшие коды 64, 65, 66, 67; виды KMP 55-58 |
| прочие 4xx | без повтора, `client_error:<code>` |
| 5xx | повтор через `max(server backoff, client delay)`, `server_error:<code>` |
| прочие | `global_error:<code>` |

Временные сбои старше 7 дней (`first_transient_server_failure_timestamp` > 604 800 000 мс) эскалируют до фатальных. Прочие нефатальные причины: `network_error`, `sqlite_full`, `unexpected_error`, `mms_local_io`, `mms_upload`.

---

## 4. Сообщения protobuf

Номера восстановлены из классов 2.26.41.6, сверены с порядком объявления и, где есть, со сгенерированными константами `*_FIELD_NUMBER` (`*`).

| Сообщение (класс) | Поля (номер) |
|-------------------|--------------|
| `SyncdPatch` (`C49631LsW`, lite `Lp6`) | version **1** `SyncdVersion{uint64=1}`, mutations **2**, externalMutations **3** `ExternalBlobReference`, snapshotMac **4**, patchMac **5**, keyId **6** `KeyId{bytes id=1}`, exitCode **7** `ExitCode{uint64 code=1; string text=2}`, deviceIndex **8**, clientDebugData **9** |
| `SyncdMutation` (`C49601Ls2`) | operation **1** (`SET`=0, `REMOVE`=1), record **2** |
| `SyncdRecord` (`C49610LsB`) | index **1** `SyncdIndex{bytes blob=1}` (index MAC), value **2** `SyncdValue{bytes blob=1}`, keyId **3** |
| `SyncdMutations` (`C49583Lrk`) | mutations **1** (тело внешнего патча) |
| `SyncdSnapshot` (`C49617LsI`, lite `C49419Lob`) | version **1**, records **2**, mac **3**, keyId **4** |
| `SyncActionData` (`C49612LsD`) | index **1** (строковый массив JSON в UTF-8), value **2** `SyncActionValue` (`BD4`), padding **3** (всегда пуст), version **4** int32 |
| `ExternalBlobReference` (`C49439Lov`) * | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `AppStateSyncKeyShare` (`C25704B7n`) * / `AppStateSyncKey` (`C25764B9y`) * | keys **1** / keyId **1** (`B89{keyId=1}`), keyData **2** |
| `AppStateSyncKeyData` (`BB9`) * | keyData **1** (32 байта), fingerprint **2**, timestamp **3** (мс) |
| `AppStateSyncKeyFingerprint` (`BBU`) * | rawId **1**, currentIndex **2**, deviceIndexes **3** |
| `AppStateSyncKeyRequest` (`C25703B7m`) * | keyIds **1** |
| `AppStateFatalExceptionNotification` (`C25763B9x`) * | collectionNames **1**, timestamp **2** |
| `SyncDCollectionFatalRecoveryRequest` | collectionName **1**, timestamp **2** |
| `SyncDSnapshotFatalRecoveryResponse` | collectionSnapshot **1**, isCompressed **2** |
| `SyncdSnapshotRecovery` (`C49432Loo`) * / `SyncdPlainTextRecord` (`C49416LoY`) * | version **1**, collectionName **2**, mutationRecords **3**, collectionLthash **4** / value **1** `SyncActionData`, keyId **2**, mac **3** |
| `KeyExpiration` (`B8Y`) | expiredKeyEpoch **1** |
| `SyncActionValue` (`BD4`) * | timestamp **1** (int64; SET без него завершается ошибкой), по одному полю на действие (10.1) |

Носители (found, `*`): `ProtocolMessage` (`BD3`) `appStateSyncKeyShare` поле **7** / тип **6**, `appStateSyncKeyRequest` поле **8** / тип **7**, `appStateFatalExceptionNotification` поле **10** / тип **10** (`EnumC26463Bdz`). `PeerDataOperationRequestMessage.syncdCollectionFatalRecoveryRequest` поле **7**, тип запроса `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` = **8** (`EnumC26460Bdv`); ответ `syncdSnapshotFatalRecoveryResponse` поле **8** (`C25828BCm`). Client-props companion (`C43107IrI`): `isSyncdPureLidSession` **2**, `isSyncdSnapshotRecoveryEnabled` **3**. Внутренние номера FMessage: key share **38**, key request **39**, fatal notification **50**. Share и request передаются как peer-сообщения на один `DeviceJid` (`SendPeerMessageJob`), приоритет share `high`.

---

## 5. Ключи мутаций и шифрование записей

### 5.1 Вывод ключей (found, `MhX`, так же в `C52959NkE`)

```
expanded = HKDF-SHA256(ikm = keyData(32), salt = 32 × 0x00, info = "WhatsApp Mutation Keys", L = 160)
```

| Байты | Поле `MhX` | Назначение |
|-------|------------|------------|
| 0-31 | `A00` | ключ index, HMAC-SHA256 |
| 32-63 | `A03` | ключ шифрования value, AES-256-CBC |
| 64-95 | `A04` | ключ MAC value, HMAC-SHA512 |
| 96-127 | `A02` | ключ MAC снапшота, HMAC-SHA256 |
| 128-159 | `A01` | ключ MAC патча, HMAC-SHA256 |

HKDF — это `AbstractC38961i0.A00`: extract = `HMAC-SHA256(32 zero bytes, ikm)`, expand по RFC 5869. `C17930kd` кеширует объекты `MhX` (5 записей, inferred). Sync-ключ случаен (раздел 7), не выводится из ключей Signal.

### 5.2 Шифрование одной мутации (found, `KmpSyncdEncryptor`, `C52959NkE`)

```
index    = JSON string array, element 0 = action wire name, e.g. ["mute","<jid>"]
plain    = SyncActionData{ index = UTF8(index), value = SyncActionValue, padding = "", version }
iv       = SecureRandom(16)
ct       = AES-256-CBC/PKCS5(valueEncKey, iv, plain)
aad      = op ‖ keyId(6)                 op: 0x01 SET, 0x02 REMOVE
valueMac = HMAC-SHA512(valueMacKey, aad ‖ iv ‖ ct ‖ len8)[0..32)      len8 = 8-byte big-endian aad length (7)
indexMac = HMAC-SHA256(indexKey, UTF8(index))
record   = SyncdRecord{ index.blob = indexMac, value.blob = iv ‖ ct ‖ valueMac, keyId }
```

Длина padding равна `max(0, −indexLen − valueLen)`, всегда пуст. Минимальный blob 48 байт. SET→0x01 предполагает, что локальная константа операции для SET равна 0 (inferred; на проводе SET=0). Содержимое value у REMOVE inferred пустое (ветка `mqt != null`).

### 5.3 Расшифровка (found, `KmpSyncdDecryptor`)

| Шаг | Проверка | Сбой |
|-----|----------|------|
| 1 | разделить `iv = [0..16)`, `ct = [16..n−32)`, `mac = [n−32..n)` | `Cipher text too short` |
| 2 | найти ключ по `record.keyId` | ошибки ключей (7.2) |
| 3 | пересчитать value MAC, сравнить | `Data MAC mismatch` (`DecryptionFailed`) |
| 4 | расшифровать AES-CBC, разобрать `SyncActionData` | `ActionDataProtobufDeserializationFailed` |
| 5 | присутствуют index, version, (для SET) value и timestamp | `MISSING_INDEX`, `MISSING_VERSION`, `MISSING_VALUE`, `MISSING_ACTION_TIMESTAMP` |
| 6 | index — JSON `String[]`, непустой, без пустых элементов | `keyArray length should have action name` |
| 7 | пересчитать index MAC по строке index | `Index MAC mismatch` |

Value MAC проверяется до расшифровки, index MAC — последним. Затем действие определяется по элементу 0 (`Unknown mutation name:`).

---

## 6. LT-Hash, MAC снапшота и MAC патча

**LT-Hash** (found, `AbstractC50511MVx`, `KmpLtHash16`): 128 байт, читаемые как 64 little-endian u16-лейна; пустой = 128 нулевых байт.

```
expanded(valueMac) = HKDF-SHA256(ikm = valueMac(32), salt = 32 × 0x00, info = "WhatsApp Patch Integrity", L = 128)
lane'[i]           = (lane[i] ± expanded[i]) mod 2^16         + add, − subtract
```

Входящее обновление (`KmpSyncdCryptoHelper.A01`): для каждого index в патче **вычесть** сохранённый `mutation_mac` существующей записи, затем **прибавить** value MAC операций SET. `checkLtHashConsistency` (`C17520jx`) перестраивает хеш из всех сохранённых значений `mutation_mac` и сравнивает с сохранённым хешем (логирует `ltHashFromMutations` / `ltHashFromDb`, последние 16 hex-символов, если не включён флаг **624**); запускается из ежедневного cron, когда истекло число часов из флага **1104** (по умолчанию 0 = выкл.), и после несовпадения snapshot MAC при флаге **1783**.

**MAC** (found):

```
version8    = 8-byte big-endian version
snapshotMac = HMAC-SHA256(snapshotMacKey, ltHash(128) ‖ version8 ‖ UTF8(collection))
patchMac    = HMAC-SHA256(patchMacKey,   snapshotMac ‖ valueMac₁ ‖ … ‖ valueMacₙ ‖ version8 ‖ UTF8(collection))
```

`valueMacᵢ` = последние 32 байта каждого value blob, в порядке патча. Исходящие: version = сохранённая + 1 для обоих MAC (`C50707Mbo(old + 1)`). Входящий patch MAC использует `snapshot_mac`, переданный в патче; пересчитанный snapshot MAC сравнивается отдельно.

| Входящая проверка | Несовпадение |
|-------------------|--------------|
| patch MAC | фатальная `MacMismatchPatch` (32) |
| snapshot MAC в снапшоте | фатальная `SnapshotMacMismatchInSnapshot` (52) |
| snapshot MAC в патче | **не фатальна** на пути KMP: `snapshot mac mismatch but do not throw fatal`, нефатальный код отчёта 60, опциональная проверка согласованности (**1783**); потребитель возвращаемого флага не выяснен |
| отсутствует `snapshot_mac` / `patch_mac` | фатальные `MissingSnapshotMac` (39) / `MissingPatchSnapshotMac` (40) / `MissingPatchMac` (41) |

---

## 7. Sync-ключи

### 7.1 Ключ, генерация, активный ключ (found)

| Элемент | Значение |
|---------|----------|
| Key id (`CGH`) | 6 байт: `deviceId` (2, BE) ‖ `epoch` (4, BE); `SyncdKeyId{deviceId=, epoch=}` |
| Данные ключа | 32 случайных байта |
| Таблица `crypto_info` | `device_id, epoch, key_data, timestamp, fingerprint, stale_timestamp` |
| Отпечаток | `rawId`, `currentIndex`, `deviceIndexes` состояния ADV key-index аккаунта на момент создания |
| Генерация (`C12800bm.A05`) | `epoch = max(stored max, in-memory) + 1` (если 0, сначала случайное в [0,65536)); только если нет находящегося в полёте нового share; при отсутствии других устройств ключ сохраняется сразу, иначе share (peer 38, `isNewlyGeneratedKey=true`) уходит каждому companion, а ключ сохраняется после того, как это сообщение было **отправлено** (`CXB.Bss`) |
| Активный ключ | последняя строка `crypto_info`, младше **14488** дней (по умолчанию 30) и с валидным отпечатком, иначе при следующей записи создаётся новый ключ |
| Проверка отпечатка (`A0B`) | `rawId` равен локальному ADV raw id; `deviceIndexes ∪ (currentIndex+1 … local currentIndex)` равно локальному множеству device-index; иначе `one of a peer device is no longer registered` |
| Sentinel (`sentinel`, `KeyExpiration`) | `C25048AqM.A00` строит по одному на коллекцию (все пять) с `expiredKeyEpoch` = наибольшая локальная epoch |
| `expireKeysWithEpochIfActive` (`A08`) | устанавливает `timestamp = 0` у последнего ключа, если его epoch ≤ заданной; вызов при получении sentinel не прослежен (inferred) |
| Устаревшие ключи | ежедневный cron помечает ключи, на которые не ссылается `syncd_mutations`, удаляет через **14496** дней (по умолчанию 31) |
| Re-key | сохранённая запись под другим ключом заменяется через `findMutationWithExpiredKey`; точная форма REMOVE+SET inferred |

### 7.2 Запрос и отсутствующие ключи (found, `C12800bm.A07`)

1. Неизвестные key id сохраняются в `missing_keys(device_id, epoch, collection_name)` и запрашиваются peer-сообщениями key-request (тип 39) у каждого другого зарегистрированного устройства, пропуская уже ожидающие id (`missing_key_counter`).
2. Отвечающий отправляет share для имеющихся у него ключей (`A0C`, `isNewlyGeneratedKey=false`).
3. Без ответа **14492** дней (по умолчанию 7, самое старое peer-сообщение типа 39, ежедневный cron) → фатальная **31** (`TimeoutWhileWaitingForMissingKey`).
4. Никто не может предоставить: `MissingKeyOnAllClients`; некого спросить: `RequestingMissingKeyWithNoClients`; нет для шифрования: `MissingActiveKeyForEncryption`.

Share — это payload `ProtocolMessage` сквозно зашифрованных peer-сообщений (found). Валидация отпечатка входящего share на стороне получателя не найдена (unknown).

---

## 8. Исходящие патчи и внешние blob

**Сборка** (found, `OutgoingProcessor`, `KmpSyncdEncryptionProcessor`): ожидающие мутации (`pending_mutations`, `is_ready_to_sync=1`) разделяются по коллекциям; повторяющийся index в одном патче отклоняется (`SameIndexForMultipleMutationsInOutgoingPatch`); определяется активный ключ; каждая мутация шифруется (5.2); новый LT-Hash из сохранённого хеша (6); `snapshotMac` / `patchMac` с версией сохранённая + 1; `SyncdPatch{version, mutations | externalMutations, snapshotMac, patchMac, keyId, deviceIndex?, clientDebugData?}`; IQ (3.1); результат несёт новую версию. `deviceIndex` (поле 8) управляется флагом **14486** (по умолчанию true; потребитель не прослежен).

**Правило внешней загрузки** (found, `OutgoingProcessor`): `(mutationCount > P14494 or bytes > P14495 × 1024) and bytes > P5097 × 1024`, значения по умолчанию 100 / 10 / 0, поэтому любой патч свыше 100 мутаций или примерно 10 КБ уходит во внешний blob. Blob — сообщение `SyncdMutations`; патч тогда несёт `externalMutations` и не содержит встроенных `mutations` (наличие обоих отклоняется: `PatchWithBothInlineAndExternalMutations`). Ошибки загрузки: `Upload transient network error`, `Upload local I/O failure`, `Upload failed`.

**Транспорт blob** (found, `C17650kB`, `C49831Lvs`, `C15530gU`):

| Элемент | Значение |
|---------|----------|
| Тип медиа / info HKDF media-key | `md-app-state` (путь MMS `mms`) / `WhatsApp App State Keys` |
| Обязательные поля ссылки | mediaKey, directPath, fileSha256, fileEncSha256 (отсутствие любого → `MissingExternalBlobReference*`) |
| Статус загрузки | 5 = истёк (`ExternalPatchExpired` 3 / `SnapshotExpired` 49, фатальные); временные статусы повторяются; остальные фатальные |
| Содержимое | внешний патч → `SyncdMutations`; снапшот → `SyncdSnapshot` |

Общая раскладка расширения media-key здесь повторно не читалась (inferred общая).

**Отладочные данные** (found): `clientDebugData` = `PatchDebugData` (`C49633LsY`: `collection_name`, `current_lthash`, `new_lthash`, `new_lthash_subtract`, `patch_version`, `number_add/remove/override`, `sender_platform`, `is_sender_primary`, `first_four_bytes_from_a_hash_of_snapshot_mac_key`), записывается только при флаге **6614** (по умолчанию false); получатель логирует его после несовпадения patch MAC.

---

## 9. Входящие патчи и снапшоты

| # | Проверка (found) | Сбой: вид KMP (id) / устаревший код |
|---|------------------|-------------------------------------|
| 1 | у патча есть `version` | `MissingPatchVersion` (7) / 8 |
| 2 | нет дубликата версии в одном ответе | `DuplicatePatchVersionInCollection` (8) / 9 |
| 3 | не одновременно встроенные и внешние мутации | `PatchWithBothInlineAndExternalMutations` (13) / 14 |
| 4 | `version == stored + 1` (`verifyCollectionVersion`) | `ServerDidNotSendAllPatches` (64) |
| 5 | у патча есть `exit_code` | устаревшие 36 (код 100), 37 (101), 38 (прочие); аналог KMP не выяснен |
| 6 | расшифровать все мутации (5.3) | `DecryptionFailed` (6), виды формы |
| 7 | нет повторяющегося index среди SET или среди REMOVE | `SameIndexForMultipleMutationsInPatch` (5) |
| 8 | цикл межиндексной зависимости | `CyclicMutationDependencyInPatch` (37) |
| 9 | пересчитать LT-Hash, patch MAC, snapshot MAC (6) | `MacMismatchPatch` (32) / нефатально |
| 10 | применить через обработчик действия (SQLite), сохранить версию + хеш | логи `Cyclic mutation dependency`, `SQLite error` |

Снапшоты: получает только companion в процессе bootstrap (`Only companion devices that are undergoing bootstrap should receive and handle snapshots`). Скачать blob, расшифровать записи как мутации патча, отклонить повторяющиеся index (`SameIndexForMultipleMutationsInSnapshot`, 59), перестроить хеш, сравнить `snapshot.mac`; затем применить патчи `has_more_patches`. `applySnapshot keyMap contains null value, retry` повторно запрашивает ключи. Осиротевшие мутации (родительский чат отсутствует) сохраняются с `are_dependencies_missing=1`, индексируются по `chat_jid` и применяются позже (`SyncdCrossIndexDependencyUtil`).

---

## 10. Типы sync-действий

### 10.1 Каталог (found, `EnumC24865AnN` + `AbstractC24863AnL.A00`)

Номер = поле `SyncActionValue` для значения; `-` = нет соответствующей константы в `BD4` (поле значения неизвестно). Элемент 0 index — wire-имя; остальные элементы специфичны для действия и не перечислены.

| Коллекция | Wire-имя = поле |
|-----------|-----------------|
| `critical_block` (4) | `setting_securityNotification` -, `setting_pushName` 7, `setting_locale` 16, `generated_wui` 52 |
| `critical_unblock_low` (2) | `contact` 3, `lid_contact` 61 |
| `regular_high` (19) | `star` 2, `mute` 4, `deleteMessageForMe` 18, `clearChat` 21, `deleteChat` 22, `userStatusMute` 29, `ugc_bot` 43, `status_privacy` 44, `favorites` 56, `waffle_account_link_state` 58, `ctwaPerCustomerDataSharing` 62, `maiba_ai_features_control` 68, `status_post_opt_in_notification_preferences_action` 71, `private_processing_setting` 74, **`nct_salt_sync` 80**, `biz_ai_settings_nudge` 87, `wasa_root_secret` 89, `shared_device_allowlist` 94, `ai_thread_delete` - |
| `regular` (35) | `quick_reply` 8, `label_message` -, `label_edit` 14, `label_jid` 15, `primary_feature` 24, `deviceAgent` 27, `subscription` 28, `agentChatAssignment` 35, `agentChatAssignmentOpenedStatus` 36, `pnForLidChat` 37, `marketingMessage` 38, `marketingMessageBroadcast` 39, `external_web_beta` 40, `setting_relayAllCalls` 41, `call_log` 42, `delete_individual_call_log` 46, `label_reordering` 47, `setting_disableLinkPreviews` 53, `usernameChatStartMode` 59, `notificationActivitySetting` 60, `setting_channels_personalised_recommendation_optout` -, `broadcast_jid` -, `detected_outcomes_status_action` 66, `business_broadcast_list` 69, `music_user_id` 70, `avatar_updated_action` 72, `galaxy_flow_action` -, `newsletter_saved_interests` 75, `business_broadcast_campaign` 81, `business_broadcast_insights_sync` 82, `subscriptions_sync_v2` 84, `label_sublist` 91, `ctwa_message_received` 93, `shareOwnPn` -, `broadcast` - |
| `regular_low` (36) | `pin_v1` 5, `recent_emoji_weights_action` 11, `archive` 17, `sentinel` 19, `markChatAsRead` 20, `setting_unarchiveChats` 23, `android_unsupported_actions` 26, `time_format` 30, `nux` 31, `primary_version` 32, `favoriteSticker` 33, `removeRecentSticker` 34, `bot_welcome_request` 45, `payment_info` 48, `custom_payment_methods` 49, `lock` 50, `setting_chatLock` 51, `device_capabilities` 54, `note_edit` 55, `merchant_payment_partner` 57, `payment_tos` 63, `ai_thread_rename` 76, `interactive_message_action` 77, `settings_sync` 78, `out_contact` 79, `customer_data` 83, `thread_pin` 85, `setting_autoOrganizeBusinessChat` 86, `coexV2Version` 88, `lock_message` 90, `device_capabilities_v2` 92, `contact_manager_metadata` 95, `business_folder_activation` 96, `group_history_toggle` 97, `bb_pro_pending_customer_base_action` 98, `community_nesting_state` 99 |

В `BD4` нет константы для номеров полей 6, 9, 10, 12, 13, 25, 65, 67, 73. Группы по назначению (inferred по именам): состояние чата (`mute`, `pin_v1`, `thread_pin`, `archive`, `markChatAsRead`, `clearChat`, `deleteChat`, `deleteMessageForMe`, `star`, `lock*`); метки (`label_*`); контакты (`contact`, `lid_contact`, `out_contact`, `pnForLidChat`, `shareOwnPn`); настройки аккаунта (`setting_*`, `time_format`, `status_privacy`); ключи и токены (`sentinel`, `nct_salt_sync`, `wasa_root_secret`, `generated_wui`, `shared_device_allowlist`); бизнес, AI, звонки, платежи (остальное).

### 10.2 Избранные значения (found)

| Действие | Значение |
|----------|----------|
| `nct_salt_sync` (ordinal 73, `regular_high`) | `NctSaltSyncAction{bytes salt=1}` в поле **80** `SyncActionValue`; так основное устройство доставляет NCT salt на companion, происхождение и использование в `WA_TCTOKEN_CSTOKEN.md` (3.2) |
| `contact` (`ContactAction`) | fullName 1, firstName 2, lidJid 3, saveOnPrimaryAddressbook 4, pnJid 5, username 6, birthday 7; создаётся только основным устройством, поэтому companion в bootstrap получает адресную книгу раньше любой коллекции `regular*` |
| `mute` (`MuteAction`) | muted 1, muteEndTimestamp 2, autoMuted 3, muteEveryoneMentionEndTimestamp 4 |
| `sentinel` | `KeyExpiration{expiredKeyEpoch}` (7.1) |
| `android_unsupported_actions` (26), флаг **14490** (по умолчанию false) | путь «Android unsupported mutation»; семантика неизвестна |

---

## 11. Фатальные ошибки, повтор и восстановление

### 11.1 Фатальные виды KMP (found, `Lx6.A00`; id внутренние, не значения на проводе)

| Группа | Id и имена |
|--------|------------|
| Транспорт | 53 `XmppBadRequestForCollection`, 54 `…NotFoundForCollection`, 55 `XmppBadRequestGlobalError`, 56 `…NotFoundGlobalError`, 57 `…BadMethodGlobalError`, 58 `…NotAcceptableGlobalError` |
| Форма патча / снапшота | 4 `MissingOrEmptyIndex`, 5 `SameIndexForMultipleMutationsInPatch`, 7 `MissingPatchVersion`, 8 `DuplicatePatchVersionInCollection`, 13 `PatchWithBothInlineAndExternalMutations`, 37 `CyclicMutationDependencyInPatch`, 38 `MissingSnapshotVersion`, 47 `MissingPatchKeyId`, 50 `MissingSnapshotKeyId`, 59 `SameIndexForMultipleMutationsInSnapshot`, 64 `ServerDidNotSendAllPatches`, 65 `ServerSentEarlierPatch`, 71 `InvalidSnapshotRecords` |
| Форма мутации / действия | 10-12, 14-16, 19-24 (`MissingMutationVersion/Value/Index/Operation/Record/KeyId`, `MissingActionIndex/Value/Version/Timestamp`, `InvalidMutationIndex`, `InvalidActionIndex`) |
| Криптография | 6 `DecryptionFailed`, 9 `EncryptionFailed`, 31 `MacMismatchSnapshot`, 32 `MacMismatchPatch`, 39-41 `Missing*Mac`, 51 `SnapshotMacMismatchInPatch`, 52 `SnapshotMacMismatchInSnapshot` |
| Ключи | 29 `MissingKeyOnAllClients`, 30 `TimeoutWhileWaitingForMissingKey`, 46 `InvalidKeyShareKeyId`, 48 `InvalidKeyShareKeyData`, 62, 66-69 (`RequestingMissingKeyWithNoClients`, `MissingKeyForMutationInLocalSnapshot`, `MissingActiveKeyAfterRotation`, `MissingActiveKeyForEncryption`, `MissingCurrentEpochForActiveKeyValidation`) |
| Blob / protobuf | 3 `ExternalPatchExpired`, 49 `SnapshotExpired`, 42-45 и 72 `MissingExternalBlobReference*`, 60 / 61 сбой разбора ссылки / снапшота, 17 / 18 / 25-28 виды (де)сериализации, 34-36 `TerminalPatch*` |
| Локальные | 33 `DbStoreNotReady`, 63 `DbStoreNotReadyLowDiskSpace`, 70 `SameIndexForMultipleMutationsInOutgoingPatch` |

### 11.2 Устаревшие числовые коды (found, `C49784Lv2.errorCode`, попадают в WAM `md_fatal_error`; отдельная нумерация)

8 / 9 / 14 (`N90`: нет версии / дубликат версии / встроенные + внешние), 18 / 69 (сбой разбора патча / снапшота), 36 / 37 / 38 (`exit_code` 100 / 101 / прочие), 64-67 (глобальные ошибки IQ 400 / 404 / 405 / 406), 71 (разрешение ключа не удалось после запроса отсутствующего ключа), 31 (тайм-аут ожидания ключа), 60 (нефатальное несовпадение snapshot MAC в патче, `A0F(60, collection, false)`). Соответствие видам KMP не выяснено.

### 11.3 Реакция на фатальный сбой (found, `SyncResponseHandler.A08`, `C12440bB.A0S/A0Q`)

| Роль | Действие |
|------|----------|
| Любая | лог `app-state-sync-handle-fatal-exception`, WAM `md_fatal_error`, сбросить текущую синхронизацию |
| Флаг **25799** | companion: `companion_syncd_dirty=true`; основное: `C17630k8.A01(1)` (причина dirty 1, inferred) |
| Основное | `A0Q(1)` удаляет все данные syncd. Dirty-автомат (`C17630k8`, цепочка от `A0Q` inferred): счётчик `syncd_dirty` до 4, `syncd_dirty_reason`, `<iq xmlns="w:sync:app:state" type="set"><delete_all_data/></iq>` (атрибут type inferred), `logoutAllCompanionDevices` |
| Companion | `companion_syncd_dirty=true`, peer-сообщение `AppStateFatalExceptionNotification` (FMessage 50) основному устройству (device 0), ожидание 5 с, выход из аккаунта с `syncd_failure` или `syncd_error_during_bootstrap` |

Окно повтора delete-all **14493** минут (по умолчанию 360). Основное устройство выполняет очистку, когда companion был снят с регистрации и ни одного не осталось (`shouldCleanUpSyncd`).

### 11.4 Восстановление снапшота (found, `KmpSyncdFatalErrorRecovery`)

Включается client-prop `isSyncdSnapshotRecoveryEnabled`. Companion отправляет операцию peer data `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` (8) с `SyncDCollectionFatalRecoveryRequest{collectionName}`. Отвечающий строит `SyncdSnapshotRecovery` из своих хранимых **открытых** мутаций (`syncd_mutations`, `collection_versions.version / lt_hash`), сжимает gzip и возвращает `SyncDSnapshotFatalRecoveryResponse`. Отказы: `Invalid collection name` (запрос для `critical_block`), `Collection version/ltHash invalid`, `Snapshot keyId invalid`, `Mutation count (…) more than the limit`, `Mutation snapshot data size (…) more than the limit`, `Error encoding mutation data`, `Compression failed` (props лимитов не выяснены). Открытый текст передаётся внутри сквозно зашифрованного peer-сообщения. Применение на стороне companion не прослежено (unknown).

---

## 12. Локальное состояние и feature-флаги

| Хранилище | Содержимое (found) |
|-----------|--------------------|
| `syncd_mutations` | `mutation_index` (уникальный), `mutation_value`, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name` |
| `collection_versions` / `pending_mutations` / `missing_keys` / `crypto_info` | `collection_name, version, lt_hash` / исходящая очередь (`is_ready_to_sync`) / запросы ключей / sync-ключи |
| Prefs | `syncd_bootstrap_state`, `companion_syncd_critical_bootstrap_state`, `syncd_dirty`, `syncd_dirty_reason`, `companion_syncd_dirty`, `syncd_last_companion_dereg_time`, `syncd_last_lthash_consistency_check_time`, `first_transient_server_failure_timestamp` |

Ежедневный cron (`C46413KPv`) отчитывается счётчиками `mutation_counter`, `invalid_action_counter`, `upload_conflict_counter`, `unsupported_action_counter`, `cross_index_conflict_counter`, `unset_action_mutation_counter`, `key_rotation_remove_counter`, `missing_key_counter`.

| ID флага | Тип / по умолчанию | Что управляет |
|----------|--------------------|---------------|
| **15909**, **20682**, **18234** | bool / false | `XplatSyncdEncryptionManager` против варианта по умолчанию (`AbstractC17550k0`); KMP incoming (`RunnableC53542Nwj`); KMP outgoing (`C12440bB`). Только значения по умолчанию из компиляции, реальное значение неизвестно. Имя 15909 в более ранней сборке: `KMP_SYNCD_ENGINE_CRYPTO_ENABLED` (inferred повторное использование ID) |
| **14488** / **14496** / **14492** | int / 30 / 31 / 7 | возраст активного ключа, хранение устаревших ключей, тайм-аут ожидания ключа (дни) |
| **14493** | int / 360 | окно delete-all / dereg (минуты) |
| **14494**, **14495**, **5097** | int / 100, 10, 0 | пороги внешнего патча |
| **14497** | int / 1000 | лимит загрузки мутаций из БД (inferred) |
| **1104** / **1783** | int 0 / bool false | интервал проверки согласованности (ч) / проверка после несовпадения snapshot MAC |
| **6614** | bool / false | `clientDebugData` в патчах |
| **25799** | bool / false | обработка dirty-состояния при фатальном сбое |
| **27528** | bool / false | генерировать ключ, если у основного его нет |
| **14486** | bool / true | `deviceIndex` в патчах (потребитель не прослежен) |
| **14489**, **14490**, **1221**, **624** | int 90 / bool false / bool false / bool | ограничение `min()` в `C15310g7` (не выяснено) / путь unsupported-mutation / статистика мутаций / полные хеши в логах |

---

## 13. Случаи ошибок

| Симптом | Причина | Решение |
|---------|---------|---------|
| `Data MAC mismatch` | неверный ключ, изменённый blob, неверный байт op или keyId в AAD | ключ, указанный в `record.keyId`; AAD = `op ‖ keyId`, op 1 SET / 2 REMOVE |
| `Index MAC mismatch` | строка index отличается побайтово (пробелы в JSON) | считать MAC от точной UTF-8 строки `SyncActionData.index` |
| фатальная 64 `ServerDidNotSendAllPatches` | версия патча ≠ сохранённая + 1 | пересинхронизироваться с сохранённой версии; запросить снапшот, если состояние потеряно |
| несовпадение patch MAC (32) | дрейф LT-Hash, ширина version8, snapshot MAC из неверного источника | сначала использовать `snapshot_mac` патча; версия как 8-байтовое big-endian |
| `PatchWithBothInlineAndExternalMutations` | заданы оба поля | отправлять одно |
| `MissingActionTimestamp` | `SyncActionValue.timestamp` отсутствует у SET | задать поле 1 |
| ключ отсутствует | share не получен | запрос типа 39; фатальная 31 через 7 дней |
| `one of a peer device is no longer registered` | список устройств изменился с момента создания ключа | ключ непригоден как активный; сгенерировать новый |
| ошибка IQ 400 / 404 / 405 / 406 | неверная форма запроса, неизвестная коллекция | фатальная; исправить запрос |
| `ExternalPatchExpired` / `SnapshotExpired` | статус blob 5 | восстановление снапшота или повторное сопряжение |
| выход companion `syncd_failure` | неустранимый фатальный сбой | повторное сопряжение или восстановление снапшота, если включено |

---

## 14. Ключевые различия

| Не путать | С |
|-----------|---|
| Sync-ключ (32 случайных байта на device+epoch) | ключи мутаций (результат HKDF, пять срезов) |
| Index MAC (HMAC-SHA256 по строке index) | value MAC (HMAC-SHA512, усечённый до 32, по AAD + iv + ct + len) |
| Value MAC (на мутацию) | snapshot MAC (LT-Hash + version + collection) и patch MAC (snapshot MAC + все value MAC) |
| узел `<snapshot>` (`ExternalBlobReference`) | proto `SyncdSnapshot` (содержимое blob); аналогично `externalMutations` и `SyncdMutations` |
| `critical_block` на Android (настройки аккаунта) | коллекция списка блокировок (не найдена) |
| типы `ProtocolMessage` 6 / 7 / 10 | номера полей 7 / 8 / 10 |
| Поле 7 запроса peer data | поле 8 ответа peer data |
| id видов KMP (`Lx6`) | устаревшие int `errorCode` |
| `sentinel` (маркер истечения ключа во всех пяти коллекциях) | `primary_version`, `android_unsupported_actions` |
| Таблицы действий / коллекций WhatsApp Web | таблица Android здесь (96 действий, другое распределение) |

---

## 15. Baileys (`baron-baileys-v2` 1.5.17)

Только факты, прочитанные в `src/Utils/chat-utils.js`, `src/Socket/chats.js`, `src/Utils/process-message.js`. Ничего не проверялось на сервере; никакой сбой не утверждается.

| Тема | Baileys | Android |
|------|---------|---------|
| Расширение ключей, LT-Hash | нативный мост `expandAppStateKeys`, `LTHashAntiTampering` (128 байт); те же имена пяти срезов | 5.1, 6 |
| Value MAC | `HMAC-SHA512(op ‖ keyId ‖ data ‖ 8 bytes, last = len)[0..32)`, op 1 / 2 | идентично |
| Snapshot / patch MAC | те же входы и порядок; `ver8` записывает только младшие 32 бита | полное 64-битное big-endian |
| Index, padding | `JSON.stringify(index)`, пустой padding | так же |
| Внешний blob | `downloadContentFromMessage(blob, 'md-app-state')` | тот же тип медиа |
| Коллекции | `critical_block, critical_unblock_low, regular_high, regular_low, regular` | те же имена |
| Узел запроса | `<sync>` без атрибутов; `<collection name version return_snapshot>`, `return_snapshot` всегда `'true'`/`'false'` | `data_namespace="3"`, `order`, `return_snapshot` только когда true |
| Отправка патча | `version = state.version − 1`, `return_snapshot='false'` | сохранённая версия |
| Непрерывность версий | не проверяется (`newState.version = patchVersion`); отсутствующая версия патча становится версией коллекции + 1 | должна равняться stored + 1 |
| Snapshot MAC в патче | пересчитывается, бросает `failed to verify LTHash` | нефатально на пути KMP |
| Key share | сохраняет только `keyData` на base64 key id; `myAppStateKeyId` = последний ключ в сообщении | хранит отпечаток и timestamp, проверяет отпечаток, выбирает последний валидный ключ |
| Fatal notification | логируется, эмитируется как `app-state.sync-error` | companion отправляет, основное действует |
| Повтор | `MAX_SYNC_ATTEMPTS = 2`, повтор с принудительным снапшотом, отсутствующий ключ паркует коллекцию | раздел 11 |
| NCT salt | `nctSaltSyncAction.salt` сохраняется как `nct-salt` | 10.2 |

В исходниках Baileys отсутствуют: `data_namespace`, `order`, обработка `exit_code`, восстановление снапшота. Влияние на сервер неизвестно.

---

## 16. Полные потоки

### 16.1 Основное устройство записывает изменение (пример `mute`)

```
[User]  → handler builds mutation  ["mute","<chatJid>"]  MuteAction  collection regular_high
     │
     ▼
[SyncManager C12440bB]  pending_mutations ; active key (≤ 30 d, fingerprint ok) else generate, share (peer 38)
     │
     ▼
[Encrypt]  iv ; AES-CBC ; aad = 01 ‖ keyId ; valueMac ; indexMac
     │     ltHash' = ltHash − oldValueMac + newValueMac ; ver = stored + 1 ; snapshotMac ; patchMac
     │     SyncdPatch inline, or externalMutations above the thresholds (md-app-state upload)
     ▼
iq set w:sync:app:state  <sync data_namespace=3><collection name order version><patch/></collection></sync>
     │
     ▼
[WA Server]  (not observed) orders patch, assigns version
     │
     ▼
Result <collection name version="N+1"/>  →  store version, hash, mutation_mac
     │
     ▼
[Companions]  sync (16.2)
```

### 16.2 Companion получает данные

```
[Companion]  iq set  <collection name version=V [return_snapshot=true if V=0]/>
     │
     ▼
Result <collection has_more_patches?> [<snapshot ExternalBlobReference/>] <patches><patch/>…</patches>
     │
     ├─ snapshot ─► download md-app-state ─► SyncdSnapshot ─► decrypt ─► hash ─► snapshot MAC
     └─ each patch (V+1 …) ─► version check ─► external blob? download SyncdMutations
            │  key unknown ─► missing_keys + peer 39 ─► [Primary] peer 38 share
            │  decrypt (valueMac → AES → SyncActionData → indexMac) ; ltHash − old + new
            │  patchMac ; snapshotMac ; action handler apply (are_dependencies_missing for orphans)
            ▼
         store version, hash ; has_more_patches → repeat
```

### 16.3 Фатальный сбой

```
[Companion]  patch MAC mismatch / key timeout / version gap
     ├─ recovery enabled ─► peer data op 8 {collectionName} ─► [Primary] SyncdSnapshotRecovery (gzip)
     └─ else companion_syncd_dirty ; peer AppStateFatalExceptionNotification ; 5 s ; logout syncd_failure
               ▼
         [Primary]  delete syncd data ; iq <delete_all_data/> ; logout companions ; re-pair
```

---

## 17. Неизвестное

| Элемент | Статус |
|---------|--------|
| Активный движок (устаревший или KMP) на аккаунт | серверные флаги |
| Значение атрибута `order` | unknown |
| Проверка отпечатка входящего key share на стороне получателя | не найдена |
| Применение полученного `sentinel` (`expireKeysWithEpochIfActive`) | не прослежено |
| Соответствие вид KMP ↔ устаревший код; триггер `ServerSentEarlierPatch`; значение `exit_code` 100 / 101 | не выяснено |
| Поле значения у 9 действий с пометкой `-` | unknown |
| Применение восстановления снапшота, props лимитов | не прослежено |
| Порядок на сервере, хранение, правила слияния | на стороне сервера |
| Трафик | ничего не перехвачено |
