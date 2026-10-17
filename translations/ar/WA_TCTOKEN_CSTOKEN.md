<!-- src-sha1: abf07b893763b0d9ab0f43cb7e9b4dab51809e14 -->
# WhatsApp TCToken & CSToken — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** TCToken و CSToken — ما هما، وكيف يعملان، وآليات APK الداخلية في Android، وتنفيذ Baileys

---

## 1. نظرة عامة: ما هذه الـ tokens؟

| Token | الاسم الكامل | الجهة المُصدِرة | وقت الاستخدام | الغرض |
|-------|-----------|--------------|-----------|---------|
| **tctoken** | Trusted Contact Token | خادم WA | جهة اتصال دافئة (علاقة قائمة) | يثبت وجود تواصل سابق بين المرسل والمستلم — إثبات مضاد للبريد المزعج |
| **cstoken** | Cold-Start Token (بديل NCT) | العميل (HMAC-SHA256، found في Android Java) | جهة اتصال باردة (لا يوجد tctoken مخزّن) | إشارة بديلة مضادة للبريد المزعج عند غياب tctoken |

**القاعدة الأساسية (found):** في stanza الرسالة 1:1 لا يُرفق `cstoken` إلا إذا كان المخزن لا يحتوي على tctoken صالح للمستلم (`NctTokenMessageSendStanzaContributor/ skipped - tctoken present`). يُرفق `tctoken` عبر contributor منفصل (`PrivacyTokenMessageSendStanzaContributor`).

كلا الـ tokens إشارتان مضادتان للبريد المزعج. ما يفعله الخادم بهما غير ظاهر من جهة العميل (inferred: تحديد سقف للبريد المزعج / للمحادثات الجديدة، انظر `NewChatMessageCappingAsyncInit` بوصفه المُشغِّل للـ salt).

جميع الـ tokens ضمن مستوى الدليل **found** (قراءة JADX ثابتة للإصدار 2.26.41.6) ما لم يُشر إلى inferred / not re-verified. لم يُختبر شيء وقت التشغيل.

---

## 2. TCToken (Trusted Contact Token)

### 2.1 ما هو

token ثنائي يُصدره الخادم ويثبت علاقة موثوقة بين JIDين. يولّده الخادم ويوزّعه. يخزّنه العميل ويعيد إرساله. بايتات الـ token معتمة بالنسبة للعميل (البيانات الموقّعة / الخوارزمية: unknown).

### 2.2 كيف يُطلب / يُحدَّث

**Job:** `GeneratePrivacyTokenJob` — اسم الـ job هو `"generate-tc-token"`. لا يحمل token: بل يطلب من الخادم (إعادة) إصداره (انظر 2.4).

**Manager:** `PrivacyTokenSendManager` (`C230709y3`)

**منطق التشغيل (found):**
- نقاط الدخول `C230709y3.A01(C14080dr, UserJid)` و `A02(UserJid)` و `A04(UserJid)`؛ و `A05` مجموعة لمنع التكرار أثناء التنفيذ (`A03` يزيل منها).
- `A04`: قائم على buckets. الـ flag **996** = طول الـ bucket بالثواني (إذا كان <= 0 يسجّل "Bad bucket configuration" ويعود إلى now − 15724800 s = 182 يومًا). يُتخطى الـ job إذا وقع الطابع الزمني المخزّن في الـ bucket الحالي أو بعده.
- مفتاح SharedPrefs `"privacy_token_last_batch_time_sec"` (يُقرأ في `A04` وفي `AHP`) يتتبع وقت آخر دفعة. الـ flag **4063** (int) هو إزاحة bucket تُستخدم معه ومع الطابع الزمني للإصدار الفعلي.
- الـ flag **14303** (bool) يحدد كيفية تطبيع الـ JID (`A00`): عند التفعيل `PrivacyTokenStore.A0L` (ربط PN → LID)؛ وعند التعطيل LID → PN عبر JID mapper. الـ flag **15491** (bool) يعطّل بالمثل البحث المزدوج PN/LID في المخزن (`A02`, `A0Q`).

**التحقق من الصلاحية (found):**
```java
// C14820fK.A0Y(UserJid)  — token for sending
C9oI c9oI = A0M(userJid);
if (c9oI == null || c9oI.A00 < this.A04.A02()) return null;  // expired or missing
return c9oI.A01;
```
بوابة الانتهاء `C14830fL` (TokenBucketValidity):
- `A02()` (الـ tokens المستلمة) = `A00(len=flag 865, validBuckets=flag 909)`
- `A01()` (صلاحية الطابع الزمني للإرسال) = `min(A00(flag 996, flag 997), A02())`
- `A00(len, n)` = `max((now/len − (n−1)) * len, now − 15724800)` (15724800 s = 182 يومًا كحد أدنى صارم).

### 2.3 التخزين

**جداول قاعدة البيانات (`wa.db`)، أنشأها `C23627AHs` / `C23628AHt` (found):**

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
(أنواع أعمدة `jid` / المفتاح الأساسي غير ظاهرة في فئتي المخطط المقروءتين؛ يُستخدم العمود `jid` مفتاحًا في جميع الاستعلامات. أنواع DDL الدقيقة inferred.)

**مدير التخزين:** `PrivacyTokenStore` (`C14820fK`)، والوصول إلى قاعدة البيانات عبر `C14840fM`
- ذاكرة تخزين مؤقت في الذاكرة: `C12420b9(10, "privacytokendatacache")`
- الدوال الرئيسية:
  - `A0P(UserJid, byte[], long)` — تخزين token مستلم؛ لا يستبدل إلا إذا كان الطابع الزمني الجديد أحدث ("UPDATE_RECEIVED_TOKEN_IF_NEWER")
  - `A0Y(UserJid)` — بايتات الـ token للإرسال (null إذا انتهت صلاحيته)
  - `A0M(UserJid)` — قراءة token مع الطابع الزمني
  - `A0O(UserJid)` / `A0N(UserJid)` — جهة الإرسال `(timestamp, real_issue_timestamp)` (مخزّنة مؤقتًا؛ `A0O` تُسقط الإدخالات الأقدم من `A04.A01()`)
  - `A0V(UserJid, long)` / `A0W(UserJid, long)` — تحديث طابع الإرسال الزمني (`A0V` يجعل `real_issue_timestamp` فارغًا أيضًا)
  - `A0X(UserJid, Integer)` — فحص حداثة الإصدار الفعلي باستخدام الـ flags **865** و **3802** / **22012**
  - `A0U()` — ملء الذاكرة المؤقتة (تُستدعى من `NewChatMessageCappingAsyncInit` عند الانتقال إلى المقدمة)

**أنواع البيانات:** `C9oI` = `(A00=timestamp, A01=byte[] token)`؛ `C220519e9` = `(A00=sent timestamp, A01=Long real_issue_timestamp)`.

### 2.4 stanzas في XMPP

**الطلب الصادر (found، `GeneratePrivacyTokenJob.A0M`)** — يُرسل إلى JID الخادم (`C19380nJ.A00`)، لا إلى جهة الاتصال. لا يحمل بايتات token؛ بل يسمّي جهة الاتصال والنوع والطابع الزمني المخزّن:

```xml
<iq id="[id]" to="[server]" type="set" xmlns="privacy">
  <tokens>
    <token jid="[contact-jid]" type="trusted_contact" t="[stored-timestamp]"/>
  </tokens>
</iq>
```

يُرسل عبر `A0W(callback, node, id, 299, 32000L)` (`C10140Tq`، `MessageClient`): المهلة **32,000 ms** (found). العدد `299` هو int نوع طلب IQ: تسجّله `A0A` في `MessageClient/sendIqWithCallbackInternal ... type=` وتخزّنه مع الـ callback المعلّق (found). هو معرّف لكل نوع طلب تشترك فيه مواضع استدعاء IQ كثيرة (الخانة نفسها تحمل قيمًا مثل 1 و 2 و 14 و 114 و 237 و 254 و 264 و 415)، وليس feature flag. أي قيمة تسمّي أي طلب غير مدرج في العميل. إعادة محاولة الـ job: `A0O` تعيد المحاولة ما لم يكن رمز عقدة الخطأ 4xx. يُجهض الـ job ("Token timestamp ... missing or too old to send") إذا لم يوجد طابع زمني صالح لـ token مخزّن.

**الوارد (found، `C1S0` الحالة 4888، المعالج `X.0vv`)** — مسجّل للرمز القاموسي **234** (`"privacy_token"`، الجدول `AbstractC32331E9w`):

```xml
<notification from="[contact-jid]" sender_lid="[lid]?" t="[t]">
  <tokens>
    <token type="trusted_contact" t="[unix-timestamp]">[binary-token-bytes]</token>
  </tokens>
</notification>
```
لا تُخزَّن إلا العناصر الفرعية ذات `type="trusted_contact"`؛ والمحتوى المفقود يطلق "required token element to contain data". مفتاح التخزين هو `sender_lid` إن وُجد وإلا `from`. يعود `t` إلى `t` الخاص بالعنصر الأب. البحث عن الطابع الزمني عبر `A0P` التي تتجاهل الـ tokens غير الأحدث.

**إرفاق tctoken الصادر (found)** — بايتات token `1..120` من `PrivacyTokenStore.A0Y`:

| الموضع | الفئة | الشكل |
|-------|-------|-------|
| stanza الرسالة 1:1 | `PrivacyTokenMessageSendStanzaContributor` (`F6I`) | عنصر فرعي `<tctoken>[bytes]</tctoken>`؛ إذا كان مفقودًا لكنه متوقع يسجّل `expected token, but missing` ويبلّغ السبب `C99E.A07`. الـ flag **20605** يبدّل إلى user JID الخاص بالجهاز |
| fanout متعدد الأجهزة | `AbstractC33466EhY.A01` | يُضاف `<tctoken>` مرة واحدة لكل مستخدم داخل أول عقدة جهاز `<to jid=...>`؛ مقيَّد بالـ flag **20605** (bool) والـ flag **20606** (الحد الأقصى للمستخدمين لكل stanza) |
| IQ صورة الملف الشخصي `w:profile:picture` | `C197098a4.A00` | عنصر فرعي `<picture ...><tctoken>` |
| الاشتراك في presence | `HandlerThreadC21920sG` الحالة 12 / `C18320lY.A07` | `<presence type="subscribe"><tctoken>` |

### 2.5 التكامل مع GraphQL

يُرفق الـ token المخزّن بوصفه سياقًا إضافيًا في عدة مدخلات GraphQL:

```java
// BizIntegritySignalsGraphQLFetcher / IntegrityFeaturesContextFetcher / C229259vZ / C23694AKh / C20L.A0M
node = GraphQlCallInput("tctoken", base64(token));   // string field
node.put("timestamp", String.valueOf(c9oI.A00));
query_input.put("privacy_token", node);
```

الحقول: `tctoken` (الـ token، مرمّز Base64 / سلسلة نصية)، `timestamp`، متداخلة تحت `privacy_token`. المستدعون في 2.26.41.6: BizIntegritySignals، IntegrityFeaturesContext (`use_case INTEGRITY_FEATURES_CONTEXT`)، `C229259vZ`، `C23694AKh`، `C20L`.

### 2.6 تعريف proto

ليس ضمن رسالة `JidGroupInfo`: لا توجد فئة بهذا الاسم في 2.26.41.6. حقول الـ token المحفوظة موجودة على proto الـ `Conversation` (`BD1`، `id` = 1، `messages` = 2) (found، ثوابت `*_FIELD_NUMBER`):

| الحقل | الرقم | النوع |
|-------|--------|------|
| `tcToken` | **21** | bytes |
| `tcTokenTimestamp` | **22** | int64 |
| `contactPrimaryIdentityKey` | **23** | bytes |
| `tcTokenSenderTimestamp` | **28** | int64 |

الادعاء الوارد في 2.26.26.4 `JidGroupInfo.tcToken = 8` / `contactPrimaryIdentityKey = 9` لا ينطبق على هذا الإصدار.

---

## 3. CSToken / NCT Token (Cold-Start Token)

### 3.1 ما هو

**HMAC يحسبه العميل** على سلسلة JID المستلم، بمفتاح هو salt على مستوى الحساب (`nctSalt`). وهو البديل عند غياب tctoken.

**الصيغة (found، Android `AbstractC38971i1.A00(data, key)`):**
```
cstoken = HMAC-SHA256(key=nctSalt, data=utf8(recipientJid.toString()))
```
المخرجات: 32 بايت، خام. يتحقق الكود فقط من أن السلسلة غير فارغة (السجل: `NctTokenGenerator/ recipient LID is empty`)، مما يوحي بأن المستلم LID (inferred). أما شكل المدخل الدقيق `<user>@lid` فهو ادعاء خاص بـ WA Web فقط من تقرير 2.26.26.4؛ ولا ينطبق على Android ولا يمكن التحقق منه من APK.

### 3.2 NctSalt — من أين يأتي

يُولَّد الـ salt محليًا على الجهاز الأساسي ويوزَّع على الأجهزة المرافقة عبر **App-State-Sync** و **HistorySync**.

**التوليد (found، `NctSaltProvider` = `C67592to.A00()`):**
```java
byte[] salt = loadFromSharedPrefs();            // C2X8.A04()
if (salt == null) {
    if (companionDevice) return null;           // "skipped - companion device"
    salt = new byte[32]; SecureRandom.nextBytes(salt);
    C2X8.A03(salt);                             // persist
    putLong("nct_salt_last_sync_ts", 0L);
}
```
التخزين `C2X8`: مفتاح SharedPrefs `"nct_salt"`، Base64 (`NO_WRAP`). إذن المصدر هو `SecureRandom` محلي على الجهاز الأساسي (found)، وليس مولَّدًا من الخادم.

**المُشغِّل (found، `NewChatMessageCappingAsyncInit` = `C2AE`)**: عند انتقال التطبيق إلى المقدمة / async-init:
- الـ flag **24915** (bool): يفعّل إنشاء NCT salt ومزامنته.
- إذا كان `nct_salt_last_sync_ts == 0` أو كان الـ flag **26897** (int، ثوانٍ) > 0 وانقضى زمن >= ذلك الفاصل: يكتب `nct_salt_last_sync_ts` الجديد ويجدول دفع SyncD (`C3MD` الحالة 36 → `SyncdUpdateHelperImpl/syncNctSalt`).

**طفرة المزامنة (found، `NctSaltSyncMutation` = `C52032Bk`)**: تحمل `byte[]` خامًا للـ salt، والإجراء `EnumC24865AnN.A0x` (`"NctSaltSyncAction"`، المفتاح `"nct_salt_sync"`)، ملفوفًا في `SyncActionValue` الحقل **80**. تُدفع إلى الأجهزة المرافقة عبر `C12440bB.A0U/A0O`.

**الاستلام على الجهاز المرافق (found، `NctSaltSyncMutationHandler` في `C0XG`)**: عند العمل كجهاز مرافق، تخزّن `A0S` الـ salt عبر `C2X8.A03` ("Received NCT salt from primary, storing"). المعالج مفعّل بالـ flag **25253** (bool).

**HistorySync (found، `CMP`)**: يُخزَّن `HistorySync.nctSalt` (`C25838BCy.nctSalt_`، بت الحضور 512) عبر `C2X8.A03` ("stored NCT salt from history sync"). رقم الحقل **19** (`C25838BCy.NCT_SALT_FIELD_NUMBER`، found).

### 3.3 حقول proto

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

DB: العمود `"nct_salt"` مسجّل في مخطط `wa.db` (`C09E`، الإدخال `C33501Un("nct_salt", ...)`). نسب تقرير 2.26.26.4 القيمة `nctSalt = 12` إلى `ConversationThreadInfo`؛ لا توجد فئة بهذا الاسم ولا حقل `nctSalt` خارج HistorySync في 2.26.41.6 (`nctSalt_` موجود فقط في `C25838BCy`، الرقم 19؛ و `Conversation` `BD1` لا يحوي حقل salt).

### 3.4 حساب HMAC والـ stanza (Android مقابل Web)

| الجانب | Android 2.26.41.6 | WA Web (خاص بـ Web فقط، لا ينطبق على Android؛ لا يمكن التحقق منه من APK) |
|--------|------------------|--------|
| مزامنة الـ salt (NctSaltSyncAction) | منفَّذة (الحقل 80) | نعم |
| تخزين الـ salt | SharedPrefs `"nct_salt"` | IndexedDB `"WAWebNctSalt"` |
| حساب HMAC-SHA256 | **Found في Java** (`AbstractC38971i1`، `javax.crypto.Mac`) | JavaScript |
| حقن الـ token في الـ stanza | **Found في Java** (`NctTokenMessageSendStanzaContributor` = `F6G`) | عقدة `<cstoken>` |

**stanza contributor (found، `F6G.ASY`)**، بالترتيب:
```
flag 24941 off                    → nothing
recipient not a 1:1 user JID      → skip ("not a 1:1 user JID")
flag 18639 on and recipient is GUEST_E2EE → skip ("guest recipient")
PrivacyTokenStore.A0Y(user) != null → skip ("tctoken present")
recipient string empty            → log "recipient LID is empty", fail
salt == null                      → log "no salt available", fail
else  <cstoken>[32 bytes]</cstoken> appended to the message stanza
```
أي استثناء يُلتقط ويُسجَّل (`skipping cstoken due to ...`)؛ ويستمر الإرسال.

```xml
<message ...>
  ...
  <cstoken>[32 raw bytes]</cstoken>
</message>
```

الـ flag **24941** (bool) = بوابة إرسال CSToken على Android؛ و **18639** (bool) = استثناء المستلم الضيف.

---

## 4. مقارنة الـ Tokens

| | TCToken | CSToken |
|-|---------|---------|
| الجهة المُصدِرة | خادم WA | العميل (HMAC) |
| الخوارزمية | يحددها الخادم (ثنائي معتم) | HMAC-SHA256 |
| مادة المفتاح | يولّدها الخادم | `nctSalt` (`SecureRandom` محلي، يُزامَن عبر App-State / HistorySync) |
| البيانات الموقّعة | غير معروفة (معتمة) | `utf8(recipient JID string)` (شكل LID inferred) |
| يوجد عندما | تأسس تواصل سابق ولم تنته الصلاحية | عند وجود salt وغياب tctoken صالح |
| الأولوية | الأولى (tctoken يتقدم) | بديل فقط |
| Stanza | عنصر فرعي `<tctoken>` في الرسالة / عقدة `<to>` / IQ الصورة / presence؛ IQ الطلب `xmlns="privacy"` إلى الخادم | عنصر فرعي `<cstoken>` في الرسالة |
| GraphQL | يُرسل في عدة استعلامات سلامة | لم يُرَ في GraphQL |
| التخزين | `wa_trusted_contacts` (+ `_send`) في DB | SharedPrefs `"nct_salt"` |
| لكل مستلم | نعم (واحد لكل JID) | لا (salt واحد، يُحسب لكل مستلم) |

---

## 5. تنفيذ Baileys

كل ما في هذا القسم إرشاد للتنفيذ (inferred من حقائق البروتوكول أعلاه)، وليس قطعة مفكوكة من التطبيق. أشكال الـ stanza مُعدَّلة لتوافق 2.26.41.6؛ كود TypeScript غير مختبر.

### 5.1 TCToken

**الاستلام والتخزين:**
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
(قيمة السمة `type` للـ notification المستخدمة في اسم الحدث inferred؛ ومعالج Android مرتبط بالرمز القاموسي 234.)

**الإرسال مع tctoken:** أرفق البايتات المخزّنة كعنصر فرعي `<tctoken>` في stanza الرسالة (1..120 بايت)، وليس كـ IQ منفصل:
```ts
const stored = (await authState.keys.get('tc-token', [recipientJid]))[recipientJid]
if (stored && !isExpired(stored.timestamp)) {
  stanza.content.push({ tag: 'tctoken', attrs: {}, content: stored.token })
}
```

**التحديث (IQ الطلب، الشكل found على Android):**
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

**التقاط nctSalt من App-State-Sync:**
```ts
// SyncActionValue field 80 = nctSaltSyncAction
function onMutation(mutation: any) {
  const nctSaltAction = mutation?.syncAction?.value?.nctSaltSyncAction
  if (nctSaltAction?.salt) {
    authState.keys.set({ 'nct-salt': { default: Buffer.from(nctSaltAction.salt) } })
  }
}
```
أما عميل الجهاز الأساسي فينشئ بنفسه 32 بايتًا عشوائيًا (كما يفعل `NctSaltProvider`) ويدفع الطفرة.

**حساب cstoken وإرفاقه:**
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
`recipientJid` = السلسلة التي يمررها Android (`Jid.toString()` للمستلم 1:1)؛ واستخدام شكل LID inferred.

**الـ stanza الناتج:**
```xml
<message to="..." type="text" ...>
  <enc .../>
  <cstoken><!-- 32 raw bytes --></cstoken>
</message>
```

### 5.3 مسار الإرسال الكامل

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

### 5.4 Proto الخاص بـ NctSaltSyncAction (تصحيح proto لـ Baileys)

أضِف إلى proto الخاص بك إن لم يكن موجودًا:
```protobuf
message NctSaltSyncAction {
  bytes salt = 1;
}

// In SyncActionValue:
NctSaltSyncAction nctSaltSyncAction = 80;
```

---

## 6. التحكم / Feature Flags

| Flag | القيمة | ما يتحكم فيه |
|------|-------|---------|
| **24915** | bool | تفعيل إنشاء NCT salt ومزامنته (`C2AE`) |
| **26897** | int (ثوانٍ) | الحد الأدنى للفاصل بين إعادات مزامنة الـ salt |
| **24941** | bool | تشغيل/إيقاف CSToken stanza contributor (`F6G`) |
| **18639** | bool | تخطي cstoken للمستلمين GUEST_E2EE |
| **25253** | bool | يفعّل `NctSaltSyncMutationHandler` |
| **996** | int (ثوانٍ) | طول bucket الـ token المرسل (مُشغِّل الـ job، `C230709y3.A04`؛ وكذلك `C14830fL.A01`) |
| **997** | int | عدد buckets الـ token المرسل الصالحة (`C14830fL.A01`) |
| **865** / **909** | int | طول bucket الـ token المستلم / عدد الـ buckets الصالحة (`C14830fL.A02`) |
| **4063** | int | إزاحة bucket في فحص إعادة الإصدار في `A04` |
| **3802** / **22012** | int | عدد الـ buckets الصالحة في `A0X` (حداثة الإصدار الفعلي) |
| **20605** | bool | tctoken في عقد `<to>` لكل جهاز؛ اختيار user JID الجهاز في `F6I` |
| **20606** | int | الحد الأقصى للمستخدمين الحاملين `<tctoken>` لكل stanza من fanout |
| **14303** / **15491** | bool | سلوك تطبيع PN/LID في المدير / المخزن |
| `wa_nct_token_send_enabled` | AB-prop (Web) | بوابة إرسال CSToken خاصة بـ WA Web فقط؛ لا تنطبق على Android (السلسلة غير موجودة في APK؛ بوابة Android هي الـ flag 24941) |

دلالات الـ flags مقروءة من الاستخدام؛ والقيم الحية على الخادم unknown.

---

## 7. حالات الخطأ وما يجب مراقبته

| العَرَض | السبب | الحل |
|---------|-------|-----|
| لا يُرفق cstoken، إرسال عادي | tctoken موجود، أو الـ flag 24941 معطّل، أو مستلم ضيف، أو غير 1:1 | متوقع (سلاسل سجل Android في 3.4) |
| سجل Android `NctTokenGenerator/ no salt available` | لا salt في SharedPrefs والجهاز مرافق (لا يستطيع الإنشاء) | انتظر NctSaltSyncAction / HistorySync |
| سجل Android `recipient LID is empty` | سلسلة JID فارغة مررت إلى المولّد | تأكد من حلّ JID المستلم |
| خطأ `463` من الخادم بعد الإرسال | صيغة سلسلة LID خاطئة | (2.26.26.4, not re-verified; no 463 handler in the message-send, `F6G`, `AbstractC38971i1` or privacy-token job paths of 2.26.41.6. The only app-level 463 branch found is the create-group `onError` in `NewGroup`, unrelated) |
| فشل `GeneratePrivacyTokenJob` | لا تُعاد محاولة 4xx من الخادم؛ وتُعاد الأخطاء الأخرى | أعد الطلب بعد تدوير الـ bucket |
| تجاهل token مخزّن | أقدم من `C14830fL.A02()` أو انتهى الـ bucket | انتظر إشعار `privacy_token` جديدًا |

---

## 8. فروق أساسية

- **tctoken** ≠ **privacy_token** على مستوى التسمية: `privacy_token` هو حقل GraphQL المتداخل والرمز القاموسي في XMPP (234) ومساحة الأسماء `xmlns="privacy"`؛ أما `tctoken` فهو اسم العنصر الفرعي في stanza وحقل السلسلة في GraphQL وحقل proto. هو الـ token الأساسي نفسه في سياقات مختلفة.
- **ACSToken** — لدى Android كائن إعداد ACS-token (`C31991Nz`: `docId`, `graphQlUrl` = `https://acs.whatsapp.com/graphql`, `surface`, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`) والدالة `hasAcsToken()` على واجهة ذات صلة (found). أما وصف "Privacy Pass blind tokens for Status/Channels crediting" والاسم `WAACSTokenUtils` فهما ادعاءان خاصان بـ WA Web فقط من 2.26.26.4 (لا ينطبقان على Android، غير متحقق منهما). لم يُعثر على صلة بمسار إرسال tctoken/cstoken.
- **counter_abuse_token** — بيانات وصفية لـ ACK الخادم على الجوال (السلسلة موجودة في 2.26.41.6: `C37961fH`, `C13X`، عمود DB في `C09550Rf`). ليس token يبنيه المرسل.
- **nctSalt** على مستوى الحساب (الـ salt نفسه لجميع المستلمين). التمييز لكل مستلم يحدث في مدخل HMAC (سلسلة JID المستلم).
- الـ IQ ذو `xmlns="privacy"` هو **طلب إلى الخادم** يحمل `jid`/`type`/`t` فقط، وليس ناقلًا لبايتات الـ token؛ إذ تنتقل بايتات الـ token في عناصر `<tctoken>` الفرعية وتصل عبر notification.

---

## 9. التغييرات مقابل 2.26.26.4

| البند | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| مدير الإرسال | `C73O` | `C230709y3` (نقاط الدخول A01/A02/A04 مع مجموعة التنفيذ A05) |
| مخزن الـ token / الذاكرة المؤقتة | `C07730Zd` / `C07760Zg` | `C14820fK` / `C12420b9` "privacytokendatacache" |
| نوع بيانات الـ token | `C151666s4` | `C9oI` (token+ts)؛ جديد `C220519e9` (sent ts + real_issue ts) |
| بوابة الانتهاء | `C07740Ze.A02()` | `C14830fL.A02()` (flags 865/909؛ حد أدنى 182 يومًا)؛ جهة الإرسال A01 (996/997) |
| أسماء الجداول / الأعمدة | `wa_trusted_contacts(_send)` | دون تغيير؛ إضافة إلى 3 فهارس found |
| Flag 996 / 24915 / 26897 | مدرجة | دون تغيير؛ وُجدت flags جديدة كثيرة (انظر 6) |
| مفاتيح SharedPrefs | `privacy_token_last_batch_time_sec`, `nct_salt`, `nct_salt_last_sync_ts` | دون تغيير |
| شكل IQ الصادر لـ tc | `<trusted_contact jid type t><token>bytes</token></trusted_contact>` إلى المستلم | `<tokens><token jid type="trusted_contact" t/></tokens>` إلى الخادم، دون بايتات token (صُحّح التقرير من الكود) |
| مهلة IQ / int النوع | 32,000 ms / 299 | دون تغيير؛ 299 معرّف نوع طلب IQ وليس flag |
| القاموس `privacy_token` | 234 | 234 (المعالج مسجّل عند 234) |
| token الوارد | غير موثق | معالج notification `X.0vv` (`C1S0` الحالة 4888)، `sender_lid` مفضّل |
| tctoken في stanza الرسالة | غير موثق | عنصر فرعي `<tctoken>` عبر `F6I`؛ وكذلك fanout `<to>` (`AbstractC33466EhY`)، IQ الصورة، presence |
| tctoken في GraphQL | BizIntegrity فقط | كذلك IntegrityFeaturesContext و `C229259vZ` و `C23694AKh` و `C20L` |
| HMAC الخاص بـ CSToken على Android | غير موجود (ربما native) | found في Java: `AbstractC38971i1` + `F6G`؛ المفتاح salt، البيانات = سلسلة JID المستلم |
| حقن `<cstoken>` الخاص بـ CSToken على Android | غير موجود | found: `NctTokenMessageSendStanzaContributor` (`F6G`)، البوابات flags 24941 / 18639 |
| مزوّد الـ salt | `C57682i2` (صياغة "server-generated") | `C67592to`: 32 بايت من `SecureRandom` محلي على الأساسي فقط، والمرافقة تتخطى |
| طفرة مزامنة الـ salt | `C177317vA` | `C52032Bk` (الإجراء `nct_salt_sync`)؛ المعالج `C0XG`، الـ flag 25253 |
| مُشغِّل الـ salt | `C37511mA` | `C2AE` (`NewChatMessageCappingAsyncInit`) |
| الـ salt في HistorySync | غير موثق | `HistorySync.nctSalt` (`C25838BCy`) يخزّنه `CMP` |
| `nctSalt = 12` في `ConversationThreadInfo` | مدّعى | غير موجود؛ `nctSalt_` موجود في HistorySync |
| حقل SyncActionValue رقم 80 | `C8MG`/`C8HG` | `C49639Lse` / `C49554LrH`، الحقل 80 مؤكد |
| `JidGroupInfo.tcToken = 8`, `contactPrimaryIdentityKey = 9` | مدّعى | لا يوجد `JidGroupInfo`؛ `Conversation` (`BD1`): `tcToken` 21, `tcTokenTimestamp` 22, `contactPrimaryIdentityKey` 23, `tcTokenSenderTimestamp` 28 |
| رقم `NctSaltSyncAction.salt` | غير مذكور | 1 (الحقل الوحيد) |
| رقم `HistorySync.nctSalt` | غير مذكور | 19 |
| int النوع `299` للـ IQ | "flag 299" | معرّف نوع طلب IQ يمرر إلى `MessageClient`، وليس flag |
| `wa_nct_token_send_enabled`، عمود WA Web | مدّعى | خاص بـ Web فقط، لا ينطبق على Android؛ بوابة Android هي الـ flag 24941 |
| `463` | مدّعى | لا موضع في الكود على مسار الإرسال؛ غير متحقق منه |
| ACSToken | "string not found" | فئة إعداد ACS `C31991Nz` found (`acs.whatsapp.com/graphql`)؛ وصف Privacy Pass خاص بـ Web/غير متحقق منه |
