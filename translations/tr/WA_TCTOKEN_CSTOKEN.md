<!-- src-sha1: abf07b893763b0d9ab0f43cb7e9b4dab51809e14 -->
# WhatsApp TCToken & CSToken — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** TCToken ve CSToken — ne oldukları, nasıl çalıştıkları, Android APK iç yapısı, Baileys implementasyonu

---

## 1. Genel Bakış: Bu token'lar nedir?

| Token | Tam ad | Kim üretir | Ne zaman kullanılır | Amaç |
|-------|--------|-----------|---------------------|------|
| **tctoken** | Trusted Contact Token | WA sunucusu | Sıcak kişi (mevcut ilişki) | Gönderici ile alıcı arasında önceki bir temas olduğunu kanıtlar — spam karşıtı doğrulama |
| **cstoken** | Cold-Start Token (NCT fallback) | İstemci (HMAC-SHA256, Android Java'da found) | Soğuk kişi (kayıtlı tctoken yok) | tctoken yokken yedek spam karşıtı sinyal |

**Temel kural (found):** 1:1 mesaj stanza'sında `cstoken` yalnızca depoda alıcı için geçerli bir tctoken bulunmadığında eklenir (`NctTokenMessageSendStanzaContributor/ skipped - tctoken present`). `tctoken` ayrı bir contributor tarafından eklenir (`PrivacyTokenMessageSendStanzaContributor`).

Her iki token da spam karşıtı sinyaldir. Sunucunun bunlarla ne yaptığı istemciden görünmez (inferred: spam / yeni sohbet sınırlaması, salt tetikleyicisi olarak bkz. `NewChatMessageCappingAsyncInit`).

Tüm token'lar, inferred / not re-verified olarak işaretlenmedikçe kanıt seviyesi **found**'dır (2.26.41.6'nın statik JADX okuması). Hiçbir şey çalışma zamanında tested edilmemiştir.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 Nedir

İki JID arasındaki güvenilir ilişkiyi doğrulayan, sunucu tarafından verilen ikili (binary) bir token. Sunucu üretir ve dağıtır. İstemci saklar ve yeniden gönderir. Token baytları istemci için opaktır (imzalanan veri / algoritma: unknown).

### 2.2 Nasıl istenir / yenilenir

**Job:** `GeneratePrivacyTokenJob` — job adı `"generate-tc-token"`. Token taşımaz: sunucudan yeni bir tane (yeniden) vermesini ister (bkz. 2.4).

**Manager:** `PrivacyTokenSendManager` (`C230709y3`)

**Tetikleme mantığı (found):**
- Giriş noktaları `C230709y3.A01(C14080dr, UserJid)`, `A02(UserJid)`, `A04(UserJid)`; `A05` uçuştaki (in-flight) istekler için tekilleştirme kümesidir (`A03` buradan siler).
- `A04`: bucket tabanlı. Feature flag **996** = saniye cinsinden bucket uzunluğu (<= 0 ise "Bad bucket configuration" loglanır ve now − 15724800 s = 182 güne geri düşülür). Saklanan zaman damgası mevcut bucket'a veya sonrasına düşüyorsa job atlanır.
- SharedPrefs anahtarı `"privacy_token_last_batch_time_sec"` (`A04` ve `AHP` içinde okunur) son batch zamanını izler. Flag **4063** (int), bununla ve gerçek verilme (real-issue) zaman damgasıyla birlikte kullanılan bir bucket ofsetidir.
- Flag **14303** (bool) JID'nin nasıl normalize edileceğini seçer (`A00`): açıkken `PrivacyTokenStore.A0L` (PN → LID eşlemesi); kapalıyken JID mapper üzerinden LID → PN. Flag **15491** (bool) benzer şekilde depodaki PN/LID çift aramasını devre dışı bırakır (`A02`, `A0Q`).

**Tazelik doğrulaması (found):**
```java
// C14820fK.A0Y(UserJid)  — token for sending
C9oI c9oI = A0M(userJid);
if (c9oI == null || c9oI.A00 < this.A04.A02()) return null;  // expired or missing
return c9oI.A01;
```
Geçerlilik kapısı `C14830fL` (TokenBucketValidity):
- `A02()` (alınan token'lar) = `A00(len=flag 865, validBuckets=flag 909)`
- `A01()` (gönderilen zaman damgası geçerliliği) = `min(A00(flag 996, flag 997), A02())`
- `A00(len, n)` = `max((now/len − (n−1)) * len, now − 15724800)` (15724800 s = 182 gün sert alt sınır).

### 2.3 Depolama

**Veritabanı tabloları (`wa.db`), `C23627AHs` / `C23628AHt` tarafından oluşturulur (found):**

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
(`jid` sütunu / birincil anahtar için sütun tipleri okunan iki şema sınıfında görünmüyor; `jid` sütunu tüm sorgularda anahtar olarak kullanılıyor. Kesin DDL tipleri inferred.)

**Depolama yöneticisi:** `PrivacyTokenStore` (`C14820fK`), DB erişimi `C14840fM` üzerinden
- Bellek içi önbellek: `C12420b9(10, "privacytokendatacache")`
- Ana metotlar:
  - `A0P(UserJid, byte[], long)` — alınan token'ı saklar; yalnızca yeni zaman damgası daha yeniyse üzerine yazar ("UPDATE_RECEIVED_TOKEN_IF_NEWER")
  - `A0Y(UserJid)` — gönderim için token baytları (süresi dolmuşsa null)
  - `A0M(UserJid)` — token + zaman damgasını okur
  - `A0O(UserJid)` / `A0N(UserJid)` — gönderen taraf `(timestamp, real_issue_timestamp)` (önbellekli; `A0O`, `A04.A01()` değerinden eski girdileri atar)
  - `A0V(UserJid, long)` / `A0W(UserJid, long)` — gönderilen zaman damgasını günceller (`A0V` ayrıca `real_issue_timestamp` değerini null yapar)
  - `A0X(UserJid, Integer)` — flag **865** ve **3802** / **22012** kullanan real-issue güncellik kontrolü
  - `A0U()` — önbelleği doldurur (foreground'da `NewChatMessageCappingAsyncInit` tarafından çağrılır)

**Veri tipleri:** `C9oI` = `(A00=timestamp, A01=byte[] token)`; `C220519e9` = `(A00=sent timestamp, A01=Long real_issue_timestamp)`.

### 2.4 XMPP stanza'ları

**Giden istek (found, `GeneratePrivacyTokenJob.A0M`)** — kişiye değil, sunucu JID'sine (`C19380nJ.A00`) gönderilir. Token baytı taşımaz; kişiyi, tipi ve saklanan zaman damgasını belirtir:

```xml
<iq id="[id]" to="[server]" type="set" xmlns="privacy">
  <tokens>
    <token jid="[contact-jid]" type="trusted_contact" t="[stored-timestamp]"/>
  </tokens>
</iq>
```

`A0W(callback, node, id, 299, 32000L)` ile gönderilir (`C10140Tq`, `MessageClient`): zaman aşımı **32,000 ms** (found). `299`, IQ istek-tipi int'idir: `A0A` bunu `MessageClient/sendIqWithCallbackInternal ... type=` olarak loglar ve bekleyen callback ile birlikte saklar (found). Birçok IQ çağrı noktasının paylaştığı, istek türü başına bir id'dir (aynı slot 1, 2, 14, 114, 237, 254, 264, 415 gibi değerler taşır), feature flag değildir. Hangi değerin hangi isteği adlandırdığı istemcide listelenmez. Job yeniden denemesi: `A0O`, hata node kodu 4xx olmadıkça yeniden dener. Geçerli bir saklanmış token zaman damgası yoksa job iptal olur ("Token timestamp ... missing or too old to send").

**Gelen (found, `C1S0` case 4888, handler `X.0vv`)** — sözlük token'ı **234** için kayıtlı (`"privacy_token"`, tablo `AbstractC32331E9w`):

```xml
<notification from="[contact-jid]" sender_lid="[lid]?" t="[t]">
  <tokens>
    <token type="trusted_contact" t="[unix-timestamp]">[binary-token-bytes]</token>
  </tokens>
</notification>
```
Yalnızca `type="trusted_contact"` olan çocuklar saklanır; içerik yoksa "required token element to contain data" hatası fırlatılır. Depo anahtarı varsa `sender_lid`, yoksa `from`'dur. `t`, üst öğenin `t` değerine geri düşer. Zaman damgası `A0P` ile aranır; daha yeni olmayan token'ları yok sayar.

**Giden tctoken eki (found)** — `1..120` token baytı `PrivacyTokenStore.A0Y` kaynaklı:

| Nerede | Sınıf | Şekil |
|--------|-------|-------|
| 1:1 mesaj stanza'sı | `PrivacyTokenMessageSendStanzaContributor` (`F6I`) | `<tctoken>[bytes]</tctoken>` çocuğu; beklenip eksikse `expected token, but missing` loglar ve `C99E.A07` nedenini raporlar. Flag **20605** cihazın kullanıcı JID'sine geçirir |
| Multi-device fanout | `AbstractC33466EhY.A01` | `<tctoken>` kullanıcı başına bir kez, ilk `<to jid=...>` cihaz node'u içine eklenir; flag **20605** (bool) ve flag **20606** (stanza başına maks. kullanıcı) ile sınırlıdır |
| Profil resmi IQ'su `w:profile:picture` | `C197098a4.A00` | `<picture ...><tctoken>` çocuğu |
| Presence subscribe | `HandlerThreadC21920sG` case 12 / `C18320lY.A07` | `<presence type="subscribe"><tctoken>` |

### 2.5 GraphQL entegrasyonu

Saklanan token, çeşitli GraphQL girdilerine ek bağlam olarak eklenir:

```java
// BizIntegritySignalsGraphQLFetcher / IntegrityFeaturesContextFetcher / C229259vZ / C23694AKh / C20L.A0M
node = GraphQlCallInput("tctoken", base64(token));   // string field
node.put("timestamp", String.valueOf(c9oI.A00));
query_input.put("privacy_token", node);
```

Alanlar: `tctoken` (token, Base64 / string kodlu), `timestamp`; `privacy_token` altında iç içe. 2.26.41.6'daki çağıranlar: BizIntegritySignals, IntegrityFeaturesContext (`use_case INTEGRITY_FEATURES_CONTEXT`), `C229259vZ`, `C23694AKh`, `C20L`.

### 2.6 Proto tanımı

`JidGroupInfo` mesajında değil: 2.26.41.6'da bu adda bir sınıf yok. Kalıcı token alanları `Conversation` proto'sundadır (`BD1`, `id` = 1, `messages` = 2) (found, `*_FIELD_NUMBER` sabitleri):

| Alan | Numara | Tip |
|------|--------|-----|
| `tcToken` | **21** | bytes |
| `tcTokenTimestamp` | **22** | int64 |
| `contactPrimaryIdentityKey` | **23** | bytes |
| `tcTokenSenderTimestamp` | **28** | int64 |

2.26.26.4'teki `JidGroupInfo.tcToken = 8` / `contactPrimaryIdentityKey = 9` iddiası bu build için geçerli değildir.

---

## 3. CSToken / NCT Token (Cold-Start Token)

### 3.1 Nedir

Alıcı JID dizesi üzerinde, hesap genelindeki bir salt (`nctSalt`) ile anahtarlanan, **istemcide hesaplanan bir HMAC**. tctoken yokken kullanılan yedektir.

**Formül (found, Android `AbstractC38971i1.A00(data, key)`):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8(recipientJid.toString()))
```
Çıktı: 32 bayt, ham. Kod yalnızca dizenin boş olmadığını kontrol eder (log: `NctTokenGenerator/ recipient LID is empty`); bu, alıcının bir LID olduğunu düşündürür (inferred). Kesin `<user>@lid` girdi biçimi, 2.26.26.4 raporundaki yalnızca WA Web'e ait bir ifadedir; Android için geçerli değildir ve APK'dan kontrol edilemez.

### 3.2 NctSalt — nereden gelir

Salt, birincil cihazda yerel olarak üretilir ve companion'lara **App-State-Sync** ve **HistorySync** ile dağıtılır.

**Üretim (found, `NctSaltProvider` = `C67592to.A00()`):**
```java
byte[] salt = loadFromSharedPrefs();            // C2X8.A04()
if (salt == null) {
    if (companionDevice) return null;           // "skipped - companion device"
    salt = new byte[32]; SecureRandom.nextBytes(salt);
    C2X8.A03(salt);                             // persist
    putLong("nct_salt_last_sync_ts", 0L);
}
```
Depolama `C2X8`: SharedPrefs anahtarı `"nct_salt"`, Base64 (`NO_WRAP`). Yani kaynak, birincil cihazdaki yerel `SecureRandom`'dır (found); sunucu üretimi değildir.

**Tetikleyici (found, `NewChatMessageCappingAsyncInit` = `C2AE`)**: uygulama foreground'a geldiğinde / async-init'te:
- Flag **24915** (bool): NCT salt oluşturmayı ve senkronizasyonu etkinleştirir.
- `nct_salt_last_sync_ts == 0` ise veya flag **26897** (int, saniye) > 0 ve geçen süre >= bu aralık ise: yeni `nct_salt_last_sync_ts` yazılır ve bir SyncD push zamanlanır (`C3MD` case 36 → `SyncdUpdateHelperImpl/syncNctSalt`).

**Senkronizasyon mutasyonu (found, `NctSaltSyncMutation` = `C52032Bk`)**: ham `byte[]` salt taşır, action `EnumC24865AnN.A0x` (`"NctSaltSyncAction"`, anahtar `"nct_salt_sync"`), `SyncActionValue` alan **80**'e sarılır. `C12440bB.A0U/A0O` ile companion'lara push edilir.

**Companion'da alma (found, `C0XG` içindeki `NctSaltSyncMutationHandler`)**: companion üzerindeyken `A0S`, salt'ı `C2X8.A03` ile saklar ("Received NCT salt from primary, storing"). Handler flag **25253** (bool) ile etkinleştirilir.

**HistorySync (found, `CMP`)**: `HistorySync.nctSalt` (`C25838BCy.nctSalt_`, presence biti 512) `C2X8.A03` ile saklanır ("stored NCT salt from history sync"). Alan numarası **19** (`C25838BCy.NCT_SALT_FIELD_NUMBER`, found).

### 3.3 Proto alanları

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

DB: `"nct_salt"` sütunu `wa.db` şemasında kayıtlı (`C09E`, girdi `C33501Un("nct_salt", ...)`). 2.26.26.4 raporu `nctSalt = 12` değerini `ConversationThreadInfo`'ya atfetmişti; 2.26.41.6'da bu adda bir sınıf ve HistorySync dışında `nctSalt` alanı yok (`nctSalt_` yalnızca `C25838BCy` içinde, numara 19; `Conversation` `BD1`'de salt alanı yok).

### 3.4 HMAC hesabı ve stanza (Android vs Web)

| Yön | Android 2.26.41.6 | WA Web (yalnızca Web, Android için geçerli değil; APK'dan kontrol edilemez) |
|-----|------------------|--------|
| Salt senkronizasyonu (NctSaltSyncAction) | Implemente (alan 80) | Evet |
| Salt depolama | SharedPrefs `"nct_salt"` | IndexedDB `"WAWebNctSalt"` |
| HMAC-SHA256 hesabı | **Java'da found** (`AbstractC38971i1`, `javax.crypto.Mac`) | JavaScript |
| Token'ın stanza'ya eklenmesi | **Java'da found** (`NctTokenMessageSendStanzaContributor` = `F6G`) | `<cstoken>` node'u |

**Stanza contributor (found, `F6G.ASY`)**, sırasıyla:
```
flag 24941 off                    → nothing
recipient not a 1:1 user JID      → skip ("not a 1:1 user JID")
flag 18639 on and recipient is GUEST_E2EE → skip ("guest recipient")
PrivacyTokenStore.A0Y(user) != null → skip ("tctoken present")
recipient string empty            → log "recipient LID is empty", fail
salt == null                      → log "no salt available", fail
else  <cstoken>[32 bytes]</cstoken> appended to the message stanza
```
Her istisna yakalanır ve loglanır (`skipping cstoken due to ...`); gönderim devam eder.

```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

Flag **24941** (bool) = Android'de CSToken gönderim kapısı; **18639** (bool) = misafir alıcı hariç tutma.

---

## 4. Token Karşılaştırması

| | TCToken | CSToken |
|-|---------|---------|
| Veren | WA sunucusu | İstemci (HMAC) |
| Algoritma | Sunucu tanımlı (opak binary) | HMAC-SHA256 |
| Anahtar materyali | Sunucu üretimi | `nctSalt` (yerel `SecureRandom`, App-State / HistorySync ile senkronize) |
| İmzalanan veri | Bilinmiyor (opak) | `utf8(recipient JID string)` (LID biçimi inferred) |
| Ne zaman vardır | Önceki temas kurulmuş, süresi dolmamış | Salt varken ve geçerli tctoken yokken |
| Öncelik | Birinci (tctoken kazanır) | Yalnızca yedek |
| Stanza | Mesajda / `<to>` node'unda / resim IQ'sunda / presence'ta `<tctoken>` çocuğu; sunucuya `xmlns="privacy"` istek IQ'su | Mesajda `<cstoken>` çocuğu |
| GraphQL | Birkaç integrity sorgusunda gönderilir | GraphQL'de görülmedi |
| Depolama | DB'de `wa_trusted_contacts` (+ `_send`) | SharedPrefs `"nct_salt"` |
| Alıcı başına | Evet (JID başına bir tane) | Hayır (tek salt, alıcı başına hesaplanır) |

---

## 5. Baileys Implementasyonu

Bu bölümdeki her şey yukarıdaki protokol bilgilerinden çıkarılmış (inferred) implementasyon rehberidir, dekompile edilmiş bir artefakt değildir. Stanza şekilleri 2.26.41.6'ya göre ayarlanmıştır; TypeScript tested değildir.

### 5.1 TCToken

**Alma ve saklama:**
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
(Olay adında kullanılan notification `type` öznitelik değeri inferred'dir; Android handler'ı sözlük token'ı 234 üzerinden anahtarlanır.)

**tctoken ile gönderme:** saklanan baytları mesaj stanza'sının `<tctoken>` çocuğu olarak ekleyin (1..120 bayt), ayrı bir IQ olarak değil:
```ts
const stored = (await authState.keys.get('tc-token', [recipientJid]))[recipientJid]
if (stored && !isExpired(stored.timestamp)) {
  stanza.content.push({ tag: 'tctoken', attrs: {}, content: stored.token })
}
```

**Yenileme (istek IQ'su, şekil Android'de found):**
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

**nctSalt'ı App-State-Sync'ten yakalama:**
```ts
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    authState.keys.set({ 'nct-salt': { default: Buffer.from(nctSaltAction.salt) } })
  }
}
```
Birincil cihaz istemcisi bunun yerine 32 rastgele baytı kendisi üretir (`NctSaltProvider`'ın yaptığı gibi) ve mutasyonu push eder.

**cstoken hesaplama ve ekleme:**
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
`recipientJid` = Android'in geçirdiği dize (1:1 alıcının `Jid.toString()` değeri); LID biçiminin kullanılması inferred'dir.

**Ortaya çıkan stanza:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 Tam gönderim akışı

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

### 5.4 NctSaltSyncAction için proto (Baileys proto yaması)

Zaten yoksa proto'nuza ekleyin:
```protobuf
message NctSaltSyncAction {
  bytes salt = 1;
}

// In SyncActionValue:
NctSaltSyncAction nctSaltSyncAction = 80;
```

---

## 6. Gating / Feature Flag'ler

| Flag | Değer | Neyi kontrol eder |
|------|-------|-------------------|
| **24915** | bool | NCT salt oluşturma + senkronizasyon etkin (`C2AE`) |
| **26897** | int (saniye) | Salt yeniden senkronizasyonları arası asgari aralık |
| **24941** | bool | CSToken stanza contributor açık/kapalı (`F6G`) |
| **18639** | bool | GUEST_E2EE alıcılar için cstoken'ı atla |
| **25253** | bool | `NctSaltSyncMutationHandler`'ı etkinleştirir |
| **996** | int (saniye) | Gönderilen token bucket uzunluğu (job tetikleyicisi, `C230709y3.A04`; ayrıca `C14830fL.A01`) |
| **997** | int | Geçerli gönderilen token bucket sayısı (`C14830fL.A01`) |
| **865** / **909** | int | Alınan token bucket uzunluğu / geçerli bucket sayısı (`C14830fL.A02`) |
| **4063** | int | `A04` yeniden verme kontrolündeki bucket ofseti |
| **3802** / **22012** | int | `A0X` içindeki geçerli bucket sayısı (real-issue güncelliği) |
| **20605** | bool | Cihaz başına `<to>` node'larında tctoken; `F6I` içinde cihaz-kullanıcı JID seçimi |
| **20606** | int | Fanout stanza'sı başına `<tctoken>` taşıyan maks. kullanıcı |
| **14303** / **15491** | bool | Manager / depodaki PN/LID normalizasyon davranışı |
| `wa_nct_token_send_enabled` | AB-prop (Web) | Yalnızca WA Web CSToken gönderim kapısı; Android için geçerli değil (dize APK'da yok; Android kapısı flag 24941) |

Flag anlamları kullanımdan okunmuştur; canlı sunucu değerleri unknown.

---

## 7. Hata durumları ve nelere dikkat edilmeli

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| cstoken eklenmedi, normal gönderim | tctoken mevcut, flag 24941 kapalı, misafir alıcı veya 1:1 değil | Beklenen davranış (Android log dizeleri 3.4'te) |
| Android logu `NctTokenGenerator/ no salt available` | SharedPrefs'te salt yok ve cihaz companion (oluşturamaz) | NctSaltSyncAction / HistorySync'i bekleyin |
| Android logu `recipient LID is empty` | Üreticiye boş JID dizesi geçirildi | Alıcı JID'sinin çözümlendiğinden emin olun |
| Gönderimden sonra sunucu `463` hatası | LID dize biçimi yanlış | (2.26.26.4, not re-verified; 2.26.41.6'nın mesaj gönderimi, `F6G`, `AbstractC38971i1` veya privacy-token job yollarında 463 handler'ı yok. Bulunan tek uygulama düzeyi 463 dalı `NewGroup` içindeki grup oluşturma `onError`'dır, ilgisiz) |
| `GeneratePrivacyTokenJob` başarısız | Sunucudan 4xx yeniden denenmez; diğer hatalar yeniden denenir | Bucket döndükten sonra yeniden isteyin |
| Saklanan token yok sayıldı | `C14830fL.A02()` değerinden eski veya bucket süresi dolmuş | Yeni `privacy_token` notification'ını bekleyin |

---

## 8. Temel ayrımlar

- **tctoken** ≠ **privacy_token** isimlendirme düzeyinde: `privacy_token` GraphQL iç içe alanı, XMPP sözlük token'ı (234) ve `xmlns="privacy"` ad alanıdır; `tctoken` stanza çocuk adı, GraphQL string alanı ve proto alanıdır. Aynı temel token, farklı bağlamlarda.
- **ACSToken** — Android'de bir ACS-token yapılandırma nesnesi (`C31991Nz`: `docId`, `graphQlUrl` = `https://acs.whatsapp.com/graphql`, `surface`, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`) ve ilgili bir arayüzde `hasAcsToken()` vardır (found). "Status/Channels kredilendirmesi için Privacy Pass kör token'ları" açıklaması ve `WAACSTokenUtils` adı, 2.26.26.4'ten gelen yalnızca WA Web'e ait iddialardır (Android için geçerli değil, doğrulanmadı). tctoken/cstoken gönderim yoluyla bir bağlantı bulunmadı.
- **counter_abuse_token** — Mobilde sunucu-ACK metadata'sı (dize 2.26.41.6'da var: `C37961fH`, `C13X`, `C09550Rf` içinde DB sütunu). Gönderici tarafından oluşturulan bir token değildir.
- **nctSalt** hesap geneli geçerlidir (tüm alıcılar için aynı salt). Alıcı başına farklılaşma HMAC girdisinde olur (alıcı JID dizesi).
- `xmlns="privacy"` IQ'su yalnızca `jid`/`type`/`t` taşıyan **sunucuya bir istektir**, token baytları için bir taşıyıcı değildir; token baytları `<tctoken>` çocuklarında taşınır ve notification ile gelir.

---

## 9. 2.26.26.4'e göre değişiklikler

| Öğe | 2.26.26.4 | 2.26.41.6 |
|-----|-----------|-----------|
| Gönderim manager'ı | `C73O` | `C230709y3` (giriş noktaları A01/A02/A04 ve in-flight kümesi A05) |
| Token deposu / önbellek | `C07730Zd` / `C07760Zg` | `C14820fK` / `C12420b9` "privacytokendatacache" |
| Token veri tipi | `C151666s4` | `C9oI` (token+ts); yeni `C220519e9` (sent ts + real_issue ts) |
| Geçerlilik kapısı | `C07740Ze.A02()` | `C14830fL.A02()` (flag 865/909; 182 günlük alt sınır); gönderen taraf A01 (996/997) |
| Tablo / sütun adları | `wa_trusted_contacts(_send)` | değişmedi; ayrıca 3 index found |
| Flag 996 / 24915 / 26897 | listelenmişti | değişmedi; birçok yeni flag found (bkz. 6) |
| SharedPrefs anahtarları | `privacy_token_last_batch_time_sec`, `nct_salt`, `nct_salt_last_sync_ts` | değişmedi |
| Giden tc IQ şekli | alıcıya `<trusted_contact jid type t><token>bytes</token></trusted_contact>` | sunucuya `<tokens><token jid type="trusted_contact" t/></tokens>`, token baytı yok (rapor koddan düzeltildi) |
| IQ zaman aşımı / tip int | 32,000 ms / 299 | değişmedi; 299 bir IQ istek-tipi id'sidir, flag değil |
| Sözlük `privacy_token` | 234 | 234 (handler 234'te kayıtlı) |
| Gelen token | belgelenmemişti | notification handler `X.0vv` (`C1S0` case 4888), `sender_lid` tercih edilir |
| Mesaj stanza'sında tctoken | belgelenmemişti | `F6I` ile `<tctoken>` çocuğu; ayrıca fanout `<to>` (`AbstractC33466EhY`), resim IQ'su, presence |
| GraphQL tctoken | yalnızca BizIntegrity | ayrıca IntegrityFeaturesContext, `C229259vZ`, `C23694AKh`, `C20L` |
| Android'de CSToken HMAC | bulunamadı (belki native) | Java'da found: `AbstractC38971i1` + `F6G`; anahtar salt, veri = alıcı JID dizesi |
| Android'de CSToken `<cstoken>` ekleme | bulunamadı | found: `NctTokenMessageSendStanzaContributor` (`F6G`), kapılar flag 24941 / 18639 |
| Salt sağlayıcı | `C57682i2` ("server-generated" ifadesi) | `C67592to`: yalnızca birincil cihazda yerel `SecureRandom` 32 bayt, companion'lar atlar |
| Salt senkronizasyon mutasyonu | `C177317vA` | `C52032Bk` (action `nct_salt_sync`); handler `C0XG`, flag 25253 |
| Salt tetikleyicisi | `C37511mA` | `C2AE` (`NewChatMessageCappingAsyncInit`) |
| HistorySync'te salt | belgelenmemişti | `CMP` tarafından saklanan `HistorySync.nctSalt` (`C25838BCy`) |
| `ConversationThreadInfo` içinde `nctSalt = 12` | iddia edilmişti | bulunamadı; `nctSalt_` HistorySync'te var |
| SyncActionValue alan 80 | `C8MG`/`C8HG` | `C49639Lse` / `C49554LrH`, alan 80 doğrulandı |
| `JidGroupInfo.tcToken = 8`, `contactPrimaryIdentityKey = 9` | iddia edilmişti | `JidGroupInfo` yok; `Conversation` (`BD1`): `tcToken` 21, `tcTokenTimestamp` 22, `contactPrimaryIdentityKey` 23, `tcTokenSenderTimestamp` 28 |
| `NctSaltSyncAction.salt` numarası | belirtilmemişti | 1 (tek alan) |
| `HistorySync.nctSalt` numarası | belirtilmemişti | 19 |
| IQ tip int'i `299` | "flag 299" | `MessageClient`'a geçirilen IQ istek-tipi id'si, flag değil |
| `wa_nct_token_send_enabled`, WA Web sütunu | iddia edilmişti | Yalnızca Web, Android için geçerli değil; Android kapısı flag 24941 |
| `463` | iddia edilmişti | gönderim yolunda kod noktası yok; doğrulanmadı |
| ACSToken | "string not found" | ACS yapılandırma sınıfı `C31991Nz` found (`acs.whatsapp.com/graphql`); Privacy Pass açıklaması yalnızca Web/doğrulanmadı |
