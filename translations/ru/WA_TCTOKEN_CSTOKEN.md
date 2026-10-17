<!-- src-sha1: abf07b893763b0d9ab0f43cb7e9b4dab51809e14 -->
# WhatsApp TCToken и CSToken — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** TCToken и CSToken — что это, как работают, внутреннее устройство Android APK, реализация в Baileys

---

## 1. Обзор: что это за токены?

| Токен | Полное название | Кто выпускает | Когда используется | Назначение |
|-------|-----------------|---------------|--------------------|------------|
| **tctoken** | Trusted Contact Token | Сервер WA | Тёплый контакт (существующая связь) | Подтверждает, что у отправителя и получателя был предыдущий контакт — антиспам-аттестация |
| **cstoken** | Cold-Start Token (запасной вариант NCT) | Клиент (HMAC-SHA256, found в Android Java) | Холодный контакт (нет сохранённого tctoken) | Запасной антиспам-сигнал, когда tctoken отсутствует |

**Основное правило (found):** в stanza сообщения 1:1 `cstoken` прикрепляется только тогда, когда в хранилище нет действительного tctoken для получателя (`NctTokenMessageSendStanzaContributor/ skipped - tctoken present`). `tctoken` прикрепляется отдельным contributor (`PrivacyTokenMessageSendStanzaContributor`).

Оба токена являются антиспам-сигналами. Что сервер делает с ними, со стороны клиента не видно (inferred: ограничение спама / новых чатов, см. `NewChatMessageCappingAsyncInit` как триггер salt).

Все токены относятся к уровню доказательств **found** (статический разбор JADX версии 2.26.41.6), если не помечено inferred / not re-verified. Во время выполнения ничего не tested.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 Что это

Выданный сервером бинарный токен, подтверждающий доверительную связь между двумя JID. Сервер генерирует и распространяет его. Клиент хранит и повторно отправляет его. Байты токена непрозрачны для клиента (подписываемые данные / алгоритм: unknown).

### 2.2 Как запрашивается / обновляется

**Job:** `GeneratePrivacyTokenJob` — имя job `"generate-tc-token"`. Он не несёт токен: он просит сервер (пере)выпустить его (см. 2.4).

**Manager:** `PrivacyTokenSendManager` (`C230709y3`)

**Логика триггера (found):**
- Точки входа `C230709y3.A01(C14080dr, UserJid)`, `A02(UserJid)`, `A04(UserJid)`; `A05` — набор дедупликации запросов в работе (`A03` удаляет из него).
- `A04`: на основе bucket. Feature flag **996** = длина bucket в секундах (<= 0 пишет в лог "Bad bucket configuration" и переходит на now − 15724800 s = 182 дня). Job пропускается, если сохранённая временная метка попадает в текущий bucket или позже.
- Ключ SharedPrefs `"privacy_token_last_batch_time_sec"` (читается в `A04` и в `AHP`) отслеживает время последнего batch. Flag **4063** (int) — смещение bucket, используемое вместе с ним и временной меткой реального выпуска.
- Flag **14303** (bool) выбирает способ нормализации JID (`A00`): при включении — `PrivacyTokenStore.A0L` (отображение PN → LID); при выключении — LID → PN через JID mapper. Flag **15491** (bool) аналогично отключает двойной поиск PN/LID в store (`A02`, `A0Q`).

**Проверка свежести (found):**
```java
// C14820fK.A0Y(UserJid)  — token for sending
C9oI c9oI = A0M(userJid);
if (c9oI == null || c9oI.A00 < this.A04.A02()) return null;  // expired or missing
return c9oI.A01;
```
Шлюз срока действия `C14830fL` (TokenBucketValidity):
- `A02()` (полученные токены) = `A00(len=flag 865, validBuckets=flag 909)`
- `A01()` (валидность отправленной временной метки) = `min(A00(flag 996, flag 997), A02())`
- `A00(len, n)` = `max((now/len − (n−1)) * len, now − 15724800)` (15724800 s = 182 дня, жёсткая нижняя граница).

### 2.3 Хранение

**Таблицы базы данных (`wa.db`), создаются `C23627AHs` / `C23628AHt` (found):**

```sql
-- Incoming tokens (received from contacts)
CREATE TABLE wa_trusted_contacts (
  jid                         TEXT PRIMARY KEY,
  incoming_tc_token           BLOB,
  incoming_tc_token_timestamp LONG
);
CREATE INDEX incoming_tc_token_timestamp_index ON wa_trusted_contacts (incoming_tc_token_timestamp);

-- Outgoing token tracking
CREATE TABLE wa_trusted_contacts_send (
  jid                     TEXT PRIMARY KEY,
  sent_tc_token_timestamp LONG,
  real_issue_timestamp    LONG
);
CREATE INDEX sent_tc_token_timestamp_index ON wa_trusted_contacts_send (sent_tc_token_timestamp);
CREATE INDEX sent_real_issue_timestamp_index ON wa_trusted_contacts_send (real_issue_timestamp);
```
(Типы столбцов для `jid` / первичного ключа не показаны в двух прочитанных классах схемы; столбец `jid` используется как ключ во всех запросах. Точные типы DDL — inferred.)

**Менеджер хранилища:** `PrivacyTokenStore` (`C14820fK`), доступ к БД через `C14840fM`
- Кэш в памяти: `C12420b9(10, "privacytokendatacache")`
- Ключевые методы:
  - `A0P(UserJid, byte[], long)` — сохранить полученный токен; перезаписывает, только если новая временная метка новее ("UPDATE_RECEIVED_TOKEN_IF_NEWER")
  - `A0Y(UserJid)` — байты токена для отправки (null, если истёк)
  - `A0M(UserJid)` — прочитать токен + временную метку
  - `A0O(UserJid)` / `A0N(UserJid)` — на стороне отправки `(timestamp, real_issue_timestamp)` (кэшируется; `A0O` отбрасывает записи старше `A04.A01()`)
  - `A0V(UserJid, long)` / `A0W(UserJid, long)` — обновить временную метку отправки (`A0V` также обнуляет `real_issue_timestamp`)
  - `A0X(UserJid, Integer)` — проверка актуальности реального выпуска по flags **865** и **3802** / **22012**
  - `A0U()` — заполнить кэш (вызывается из `NewChatMessageCappingAsyncInit` при переходе на передний план)

**Типы данных:** `C9oI` = `(A00=timestamp, A01=byte[] token)`; `C220519e9` = `(A00=sent timestamp, A01=Long real_issue_timestamp)`.

### 2.4 Stanza XMPP

**Исходящий запрос (found, `GeneratePrivacyTokenJob.A0M`)** — отправляется на JID сервера (`C19380nJ.A00`), а не контакту. Он не несёт байтов токена; в нём указаны контакт, тип и сохранённая временная метка:

```xml
<iq id="[id]" to="[server]" type="set" xmlns="privacy">
  <tokens>
    <token jid="[contact-jid]" type="trusted_contact" t="[stored-timestamp]"/>
  </tokens>
</iq>
```

Отправляется через `A0W(callback, node, id, 299, 32000L)` (`C10140Tq`, `MessageClient`): таймаут **32 000 мс** (found). `299` — int типа IQ-запроса: `A0A` пишет его в лог как `MessageClient/sendIqWithCallbackInternal ... type=` и сохраняет вместе с ожидающим callback (found). Это id вида запроса, общий для многих мест вызова IQ (тот же слот несёт значения вроде 1, 2, 14, 114, 237, 254, 264, 415), а не feature flag. Какое значение какому запросу соответствует, в клиенте не перечислено. Повтор job: `A0O` повторяет, если код узла ошибки не 4xx. Job прерывается ("Token timestamp ... missing or too old to send"), если нет ни одной действительной сохранённой временной метки токена.

**Входящий (found, `C1S0` case 4888, обработчик `X.0vv`)** — зарегистрирован для токена словаря **234** (`"privacy_token"`, таблица `AbstractC32331E9w`):

```xml
<notification from="[contact-jid]" sender_lid="[lid]?" t="[t]">
  <tokens>
    <token type="trusted_contact" t="[unix-timestamp]">[binary-token-bytes]</token>
  </tokens>
</notification>
```
Сохраняются только дочерние элементы с `type="trusted_contact"`; отсутствие содержимого выбрасывает "required token element to contain data". Ключ хранилища — `sender_lid`, если он есть, иначе `from`. `t` по умолчанию берётся из родительского `t`. Поиск временной метки через `A0P`, который игнорирует не более новые токены.

**Исходящее прикрепление tctoken (found)** — байты токена `1..120` из `PrivacyTokenStore.A0Y`:

| Где | Класс | Форма |
|-----|-------|-------|
| Stanza сообщения 1:1 | `PrivacyTokenMessageSendStanzaContributor` (`F6I`) | дочерний `<tctoken>[bytes]</tctoken>`; если отсутствует, но ожидался, пишет в лог `expected token, but missing` и сообщает причину `C99E.A07`. Flag **20605** переключает на user JID устройства |
| Multi-device fanout | `AbstractC33466EhY.A01` | `<tctoken>` добавляется один раз на пользователя внутри первого узла устройства `<to jid=...>`; ограничено flag **20605** (bool) и flag **20606** (максимум пользователей на stanza) |
| IQ изображения профиля `w:profile:picture` | `C197098a4.A00` | дочерний `<picture ...><tctoken>` |
| Подписка на presence | `HandlerThreadC21920sG` case 12 / `C18320lY.A07` | `<presence type="subscribe"><tctoken>` |

### 2.5 Интеграция с GraphQL

Сохранённый токен прикрепляется как дополнительный контекст в нескольких входах GraphQL:

```java
// BizIntegritySignalsGraphQLFetcher / IntegrityFeaturesContextFetcher / C229259vZ / C23694AKh / C20L.A0M
node = GraphQlCallInput("tctoken", base64(token));   // string field
node.put("timestamp", String.valueOf(c9oI.A00));
query_input.put("privacy_token", node);
```

Поля: `tctoken` (токен, Base64 / строковая кодировка), `timestamp`, вложены в `privacy_token`. Вызывающие стороны в 2.26.41.6: BizIntegritySignals, IntegrityFeaturesContext (`use_case INTEGRITY_FEATURES_CONTEXT`), `C229259vZ`, `C23694AKh`, `C20L`.

### 2.6 Определение proto

Не в сообщении `JidGroupInfo`: класса с таким именем в 2.26.41.6 нет. Поля сохраняемого токена находятся в proto `Conversation` (`BD1`, `id` = 1, `messages` = 2) (found, константы `*_FIELD_NUMBER`):

| Поле | Номер | Тип |
|------|-------|-----|
| `tcToken` | **21** | bytes |
| `tcTokenTimestamp` | **22** | int64 |
| `contactPrimaryIdentityKey` | **23** | bytes |
| `tcTokenSenderTimestamp` | **28** | int64 |

Утверждение из 2.26.26.4 `JidGroupInfo.tcToken = 8` / `contactPrimaryIdentityKey = 9` не подтверждается для этой сборки.

---

## 3. CSToken / NCT Token (Cold-Start Token)

### 3.1 Что это

**HMAC, вычисляемый клиентом** над строкой JID получателя с ключом в виде salt уровня аккаунта (`nctSalt`). Это запасной вариант, когда tctoken отсутствует.

**Формула (found, Android `AbstractC38971i1.A00(data, key)`):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8(recipientJid.toString()))
```
Результат: 32 байта, raw. Код проверяет лишь то, что строка не пуста (лог: `NctTokenGenerator/ recipient LID is empty`), что позволяет предположить, что получатель — LID (inferred). Точная форма входа `<user>@lid` — утверждение только для WA Web из отчёта 2.26.26.4; к Android оно не применимо и не проверяется по APK.

### 3.2 NctSalt — откуда берётся

Salt генерируется локально на основном устройстве и распространяется на companion-устройства через **App-State-Sync** и **HistorySync**.

**Генерация (found, `NctSaltProvider` = `C67592to.A00()`):**
```java
byte[] salt = loadFromSharedPrefs();            // C2X8.A04()
if (salt == null) {
    if (companionDevice) return null;           // "skipped - companion device"
    salt = new byte[32]; SecureRandom.nextBytes(salt);
    C2X8.A03(salt);                             // persist
    putLong("nct_salt_last_sync_ts", 0L);
}
```
Хранилище `C2X8`: ключ SharedPrefs `"nct_salt"`, Base64 (`NO_WRAP`). Итак, источник — локальный `SecureRandom` на основном устройстве (found), а не генерация сервером.

**Триггер (found, `NewChatMessageCappingAsyncInit` = `C2AE`)**: при переходе приложения на передний план / async-init:
- Flag **24915** (bool): включает создание и синхронизацию NCT salt.
- Если `nct_salt_last_sync_ts == 0` или flag **26897** (int, секунды) > 0 и прошло >= этого интервала: записать новый `nct_salt_last_sync_ts` и запланировать push SyncD (`C3MD` case 36 → `SyncdUpdateHelperImpl/syncNctSalt`).

**Мутация синхронизации (found, `NctSaltSyncMutation` = `C52032Bk`)**: несёт сырой salt `byte[]`, действие `EnumC24865AnN.A0x` (`"NctSaltSyncAction"`, ключ `"nct_salt_sync"`), обёрнуто в поле **80** `SyncActionValue`. Отправляется на companion-устройства через `C12440bB.A0U/A0O`.

**Приём на companion (found, `NctSaltSyncMutationHandler` в `C0XG`)**: на companion `A0S` сохраняет salt через `C2X8.A03` ("Received NCT salt from primary, storing"). Обработчик включается flag **25253** (bool).

**HistorySync (found, `CMP`)**: `HistorySync.nctSalt` (`C25838BCy.nctSalt_`, бит присутствия 512) сохраняется через `C2X8.A03` ("stored NCT salt from history sync"). Номер поля **19** (`C25838BCy.NCT_SALT_FIELD_NUMBER`, found).

### 3.3 Поля proto

```protobuf
// NctSaltSyncAction (C49554LrH): single field "salt" (ByteString)
message NctSaltSyncAction {
  bytes salt = 1;               // found: the only field; size/serialise helpers are called with tag 1 (C49650Lsp case 28)
}

// SyncActionValue (C49639Lse)
message SyncActionValue {
  NctSaltSyncAction nctSaltSyncAction = 80;  // found: NAq.A03(C49554LrH.A00, nct_salt_sync_action, 80)
}

// HistorySync (C25838BCy)
message HistorySync {
  bytes nctSalt = 19;           // found: NCT_SALT_FIELD_NUMBER = 19
}
```

БД: столбец `"nct_salt"` зарегистрирован в схеме `wa.db` (`C09E`, запись `C33501Un("nct_salt", ...)`). Отчёт 2.26.26.4 приписывал `nctSalt = 12` классу `ConversationThreadInfo`; класса с таким именем и поля `nctSalt` вне HistorySync в 2.26.41.6 нет (`nctSalt_` есть только в `C25838BCy`, номер 19; в `Conversation` `BD1` поля salt нет).

### 3.4 Вычисление HMAC и stanza (Android против Web)

| Аспект | Android 2.26.41.6 | WA Web (только Web, не применимо к Android; не проверяется по APK) |
|--------|-------------------|--------|
| Синхронизация salt (NctSaltSyncAction) | Реализована (поле 80) | Да |
| Хранение salt | SharedPrefs `"nct_salt"` | IndexedDB `"WAWebNctSalt"` |
| Вычисление HMAC-SHA256 | **Found в Java** (`AbstractC38971i1`, `javax.crypto.Mac`) | JavaScript |
| Внедрение токена в stanza | **Found в Java** (`NctTokenMessageSendStanzaContributor` = `F6G`) | узел `<cstoken>` |

**Contributor stanza (found, `F6G.ASY`)**, по порядку:
```
flag 24941 off                    → nothing
recipient not a 1:1 user JID      → skip ("not a 1:1 user JID")
flag 18639 on and recipient is GUEST_E2EE → skip ("guest recipient")
PrivacyTokenStore.A0Y(user) != null → skip ("tctoken present")
recipient string empty            → log "recipient LID is empty", fail
salt == null                      → log "no salt available", fail
else  <cstoken>[32 bytes]</cstoken> appended to the message stanza
```
Любое исключение перехватывается и пишется в лог (`skipping cstoken due to ...`); отправка продолжается.

```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

Flag **24941** (bool) = шлюз отправки CSToken на Android; **18639** (bool) = исключение получателей guest.

---

## 4. Сравнение токенов

| | TCToken | CSToken |
|-|---------|---------|
| Кто выпускает | Сервер WA | Клиент (HMAC) |
| Алгоритм | Определяется сервером (непрозрачный бинарный) | HMAC-SHA256 |
| Ключевой материал | Генерируется сервером | `nctSalt` (локальный `SecureRandom`, синхронизируется через App-State / HistorySync) |
| Подписываемые данные | Неизвестны (непрозрачны) | `utf8(recipient JID string)` (форма LID inferred) |
| Существует, когда | Установлен предыдущий контакт, не истёк | Когда salt существует и нет действительного tctoken |
| Приоритет | Первый (tctoken побеждает) | Только запасной вариант |
| Stanza | Дочерний `<tctoken>` в сообщении / узле `<to>` / IQ изображения / presence; запросный IQ `xmlns="privacy"` к серверу | Дочерний `<cstoken>` в сообщении |
| GraphQL | Отправляется в нескольких integrity-запросах | В GraphQL не замечен |
| Хранение | `wa_trusted_contacts` (+ `_send`) в БД | SharedPrefs `"nct_salt"` |
| На получателя | Да (по одному на JID) | Нет (один salt, вычисляется на каждого получателя) |

---

## 5. Реализация в Baileys

Всё в этом разделе — рекомендации по реализации (inferred из приведённых выше фактов протокола), а не декомпилированный артефакт. Формы stanza приведены к 2.26.41.6; TypeScript не tested.

### 5.1 TCToken

**Приём и сохранение:**
```ts
// Incoming tokens arrive as a notification, not an IQ set
// <notification from=jid [sender_lid=lid]><tokens><token type="trusted_contact" t=ts>bytes</token></tokens></notification>
sock.ws.on('CB:notification,type:privacy_token', async (node) => {
  const tokens = getBinaryNodeChild(node, 'tokens')
  if (!tokens) return
  for (const tk of getBinaryNodeChildren(tokens, 'token')) {
    if (tk.attrs.type !== 'trusted_contact') continue
    const jid = node.attrs.sender_lid || node.attrs.from
    const timestamp = parseInt(tk.attrs.t || node.attrs.t)
    if (tk.content) {
      await authState.keys.set({ 'tc-token': { [jid]: { token: Buffer.from(tk.content as Uint8Array), timestamp } } })
    }
  }
})
// Only overwrite when the new timestamp is newer (Android: UPDATE_RECEIVED_TOKEN_IF_NEWER)
```
(Значение атрибута `type` уведомления, используемое в имени события, — inferred; обработчик Android привязан к токену словаря 234.)

**Отправка с tctoken:** прикрепите сохранённые байты как дочерний `<tctoken>` stanza сообщения (1..120 байт), а не отдельным IQ:
```ts
const stored = (await authState.keys.get('tc-token', [recipientJid]))[recipientJid]
if (stored && !isExpired(stored.timestamp)) {
  stanza.content.push({ tag: 'tctoken', attrs: {}, content: stored.token })
}
```

**Обновление (запросный IQ, форма found на Android):**
```ts
await sock.query({
  tag: 'iq',
  attrs: { type: 'set', xmlns: 'privacy', to: S_WHATSAPP_NET },
  content: [{ tag: 'tokens', attrs: {}, content: [{
    tag: 'token', attrs: { jid: contactJid, type: 'trusted_contact', t: String(storedTimestamp) }
  }]}]
})
```

### 5.2 CSToken

**Получение nctSalt из App-State-Sync:**
```ts
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    authState.keys.set({ 'nct-salt': { default: Buffer.from(nctSaltAction.salt) } })
  }
}
```
Клиент основного устройства вместо этого сам создал бы 32 случайных байта (как это делает `NctSaltProvider`) и отправил бы мутацию.

**Вычисление и прикрепление cstoken:**
```ts
import { createHmac } from 'crypto'

async function buildCsTokenNode(recipientJid: string, authState: AuthenticationState, tcTokenBuffer?: Buffer) {
  if (tcTokenBuffer?.length) return null          // tctoken takes priority
  const salt = (await authState.keys.get('nct-salt', ['default']))['default']
  if (!salt || !recipientJid) return null
  const cs = createHmac('sha256', salt).update(Buffer.from(recipientJid, 'utf8')).digest() // 32 bytes
  return { tag: 'cstoken', attrs: {}, content: cs }
}
```
`recipientJid` = строка, которую передаёт Android (`Jid.toString()` получателя 1:1); использование формы LID — inferred.

**Итоговая stanza:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 Полный процесс отправки

```
relayMessage(jid, msg)
    │
    ▼
is 1:1 user JID? → NO → skip token attachment
    │ YES
    ▼
valid tc-token in store for this JID?
    │
    ├── YES → <tctoken> child in stanza, no cstoken
    │
    └── NO (cold contact)
            │
            ▼
        load nct-salt → missing → log "no salt" + skip
            │ salt available
            ▼
        cstoken = HMAC-SHA256(salt, utf8(recipient JID string))
        attach <cstoken> node to message stanza
```

### 5.4 Proto для NctSaltSyncAction (патч proto для Baileys)

Добавьте в свой proto, если ещё нет:
```protobuf
message NctSaltSyncAction {
  bytes salt = 1;
}

// In SyncActionValue:
NctSaltSyncAction nctSaltSyncAction = 80;
```

---

## 6. Gating / Feature Flags

| Flag | Значение | Что контролирует |
|------|----------|------------------|
| **24915** | bool | Создание и синхронизация NCT salt включены (`C2AE`) |
| **26897** | int (секунды) | Минимальный интервал между повторными синхронизациями salt |
| **24941** | bool | Contributor stanza CSToken вкл/выкл (`F6G`) |
| **18639** | bool | Пропуск cstoken для получателей GUEST_E2EE |
| **25253** | bool | Включает `NctSaltSyncMutationHandler` |
| **996** | int (секунды) | Длина bucket отправленного токена (триггер job, `C230709y3.A04`; также `C14830fL.A01`) |
| **997** | int | Число действительных bucket отправленного токена (`C14830fL.A01`) |
| **865** / **909** | int | Длина bucket полученного токена / число действительных bucket (`C14830fL.A02`) |
| **4063** | int | Смещение bucket в проверке повторного выпуска `A04` |
| **3802** / **22012** | int | Число действительных bucket в `A0X` (актуальность реального выпуска) |
| **20605** | bool | tctoken в узлах `<to>` на каждое устройство; выбор JID пользователя устройства в `F6I` |
| **20606** | int | Максимум пользователей с `<tctoken>` на stanza fanout |
| **14303** / **15491** | bool | Поведение нормализации PN/LID в manager / store |
| `wa_nct_token_send_enabled` | AB-prop (Web) | Шлюз отправки CSToken только для WA Web; к Android не применимо (строки нет в APK; шлюз Android — flag 24941) |

Семантика flag считана из использования; актуальные серверные значения unknown.

---

## 7. Случаи ошибок и на что обращать внимание

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| cstoken не прикреплён, отправка обычная | tctoken есть, flag 24941 выключен, получатель guest или не 1:1 | Ожидаемо (строки лога Android в 3.4) |
| Лог Android `NctTokenGenerator/ no salt available` | В SharedPrefs нет salt, а устройство — companion (создать не может) | Дождаться NctSaltSyncAction / HistorySync |
| Лог Android `recipient LID is empty` | Генератору передана пустая строка JID | Убедиться, что JID получателя разрешён |
| Ошибка сервера `463` после отправки | Неверный формат строки LID | (2.26.26.4, not re-verified; обработчика 463 нет в путях отправки сообщения, `F6G`, `AbstractC38971i1` и job privacy-token версии 2.26.41.6. Единственная найденная ветка 463 на уровне приложения — `onError` создания группы в `NewGroup`, не связана) |
| `GeneratePrivacyTokenJob` завершается ошибкой | 4xx от сервера не повторяется; прочие ошибки повторяются | Запросить повторно после смены bucket |
| Сохранённый токен игнорируется | Старше `C14830fL.A02()` или bucket истёк | Дождаться нового уведомления `privacy_token` |

---

## 8. Ключевые различия

- **tctoken** ≠ **privacy_token** на уровне именования: `privacy_token` — вложенное поле GraphQL, токен словаря XMPP (234) и пространство имён `xmlns="privacy"`; `tctoken` — имя дочернего элемента stanza, строковое поле GraphQL и поле proto. Один и тот же токен в разных контекстах.
- **ACSToken** — в Android есть объект конфигурации ACS-токена (`C31991Nz`: `docId`, `graphQlUrl` = `https://acs.whatsapp.com/graphql`, `surface`, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`) и `hasAcsToken()` в связанном интерфейсе (found). Описание «слепые токены Privacy Pass для зачисления Status/Channels» и имя `WAACSTokenUtils` — утверждения только для WA Web из 2.26.26.4 (к Android не применимы, не проверены). Связи с путём отправки tctoken/cstoken не найдено.
- **counter_abuse_token** — метаданные серверного ACK на мобильных (строка присутствует в 2.26.41.6: `C37961fH`, `C13X`, столбец БД в `C09550Rf`). Не токен, создаваемый отправителем.
- **nctSalt** действует на уровне аккаунта (один salt для всех получателей). Различие по получателям происходит во входе HMAC (строка JID получателя).
- IQ `xmlns="privacy"` — это **запрос к серверу**, несущий только `jid`/`type`/`t`, а не транспорт для байтов токена; байты токена идут в дочерних `<tctoken>` и приходят через notification.

---

## 9. Изменения относительно 2.26.26.4

| Элемент | 2.26.26.4 | 2.26.41.6 |
|---------|-----------|-----------|
| Send manager | `C73O` | `C230709y3` (точки входа A01/A02/A04 плюс набор запросов в работе A05) |
| Хранилище / кэш токенов | `C07730Zd` / `C07760Zg` | `C14820fK` / `C12420b9` "privacytokendatacache" |
| Тип данных токена | `C151666s4` | `C9oI` (token+ts); новый `C220519e9` (sent ts + real_issue ts) |
| Шлюз срока действия | `C07740Ze.A02()` | `C14830fL.A02()` (flags 865/909; нижняя граница 182 дня); сторона отправки A01 (996/997) |
| Имена таблиц / столбцов | `wa_trusted_contacts(_send)` | без изменений; плюс найдено 3 индекса |
| Flag 996 / 24915 / 26897 | перечислены | без изменений; найдено много новых flags (см. 6) |
| Ключи SharedPrefs | `privacy_token_last_batch_time_sec`, `nct_salt`, `nct_salt_last_sync_ts` | без изменений |
| Форма исходящего tc IQ | `<trusted_contact jid type t><token>bytes</token></trusted_contact>` получателю | `<tokens><token jid type="trusted_contact" t/></tokens>` серверу, без байтов токена (отчёт исправлен по коду) |
| Таймаут IQ / int типа | 32 000 мс / 299 | без изменений; 299 — id типа IQ-запроса, а не flag |
| Словарь `privacy_token` | 234 | 234 (обработчик зарегистрирован на 234) |
| Входящий токен | не документирован | обработчик notification `X.0vv` (`C1S0` case 4888), предпочтителен `sender_lid` |
| tctoken в stanza сообщения | не документирован | дочерний `<tctoken>` через `F6I`; также fanout `<to>` (`AbstractC33466EhY`), IQ изображения, presence |
| GraphQL tctoken | только BizIntegrity | также IntegrityFeaturesContext, `C229259vZ`, `C23694AKh`, `C20L` |
| HMAC CSToken на Android | не найден (возможно, native) | found в Java: `AbstractC38971i1` + `F6G`; ключ salt, данные = строка JID получателя |
| Внедрение `<cstoken>` CSToken на Android | не найдено | found: `NctTokenMessageSendStanzaContributor` (`F6G`), шлюзы flags 24941 / 18639 |
| Salt provider | `C57682i2` (формулировка «server-generated») | `C67592to`: локальный `SecureRandom` 32 байта только на основном устройстве, companion пропускают |
| Мутация синхронизации salt | `C177317vA` | `C52032Bk` (действие `nct_salt_sync`); обработчик `C0XG`, flag 25253 |
| Триггер salt | `C37511mA` | `C2AE` (`NewChatMessageCappingAsyncInit`) |
| Salt в HistorySync | не документирован | `HistorySync.nctSalt` (`C25838BCy`), сохраняется `CMP` |
| `nctSalt = 12` в `ConversationThreadInfo` | заявлено | не найдено; `nctSalt_` существует в HistorySync |
| Поле 80 SyncActionValue | `C8MG`/`C8HG` | `C49639Lse` / `C49554LrH`, поле 80 подтверждено |
| `JidGroupInfo.tcToken = 8`, `contactPrimaryIdentityKey = 9` | заявлено | `JidGroupInfo` нет; `Conversation` (`BD1`): `tcToken` 21, `tcTokenTimestamp` 22, `contactPrimaryIdentityKey` 23, `tcTokenSenderTimestamp` 28 |
| Номер `NctSaltSyncAction.salt` | не указан | 1 (единственное поле) |
| Номер `HistorySync.nctSalt` | не указан | 19 |
| Int типа IQ `299` | "flag 299" | id типа IQ-запроса, передаваемый в `MessageClient`, а не flag |
| `wa_nct_token_send_enabled`, столбец WA Web | заявлено | только Web, к Android не применимо; шлюз Android — flag 24941 |
| `463` | заявлено | места в коде на пути отправки нет; не подтверждено |
| ACSToken | "string not found" | найден класс конфигурации ACS `C31991Nz` (`acs.whatsapp.com/graphql`); описание Privacy Pass только для Web/не подтверждено |
