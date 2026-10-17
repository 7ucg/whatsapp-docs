<!-- src-sha1: 64389e16d6c478a5b57f43abf9ee01a01474f02f -->
# WhatsApp Meta AI — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** البنية الداخلية لـ Meta AI — الـ JIDs، التوجيه، حقول proto، طلبات بيانات Hatch الوصفية، عرض الاستجابة، سبب فشل Baileys، الإصلاح

---

## 1. ما هو Meta AI (تقنيًا)

Meta AI هو جهة اتصال بوت تُعنوَن بـ JIDs خاصة بالبوتات (الخادم `bot`)، مع حقول proto خاصة بالبوتات على أنواع الرسائل العادية، وقناة طلبات JSON منفصلة ("Hatch metadata") تُحمَل داخل `ProtocolMessage`. جميع العبارات هنا نتيجة تحليل ساكن لـ APK المفكَّك. المستوى: **found** = مقروء في الشيفرة، **inferred** = مستنتج من الشيفرة، **unknown** = غير محلول.

الأسماء في هذا التقرير التي كانت مبهَمة في 2.26.26.4 (`C1A2` و`B2Y` و`B2C` و`Azz` و`C26654Bv8`) أُعيد حلّها من مراسٍ ثابتة؛ ولا توجد بهذه الأسماء في 2.26.41.6.

| Entity | 2.26.41.6 name | Role |
|--------|----------------|------|
| BotJid | `C24770wv` | فئة JID، الخادم `"bot"`، النوع 26، سلسلة رقمية من 1-20 محرفًا، دون صفر بادئ |
| Bot JID constants | `AbstractC34361Xw` | ثوابت ومجموعات Hatch / Fallback / LID |
| JID mapping | `AbstractC24760wu` | ربط bot ↔ LID، تحويل هدف الرسائل الصادرة |
| Gating | `C39311it` | تحكم أعلام الميزات لكل JID (`A0E(Jid)`) |
| Hatch request manager | `HF1` (`HatchMetadataRequestManager`) | طلبات JSON، خريطة الطلبات المعلّقة |
| Hatch proto builder | `Hf6` | يبني `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | يحمل `botMetadata` |
| BotMetadata | `C30615DTj` | بيانات وصفية للبوت لكل رسالة |
| Bot profile record | `C199348dm` | الاسم، الوصف، سلسلة معرّف الشخصية (persona)، الصورة المصغرة |

---

## 2. JIDs الخاصة بـ Meta AI

### 2.1 JIDs الموجودة في الشيفرة

| Constant | Class | Role | Tier |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) عبر `AbstractC34361Xw.A00` | **Hatch**، الأساسي. الملف الافتراضي مبني في `C223219iv` من حمولة العلم **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) عبر `AbstractC34361Xw.A01` | Fallback. يتحكم به العلم 27083 | found |
| `165332417282214` | `C14080dr` (الخادم `"lid"`) عبر `AbstractC34361Xw.A02` | مقابل LID لـ `…698` | found |
| `1807055946647696` | لا شيء | Manus (قديم في 2.26.26.4): **غير موجود** في 2.26.41.6 | found (absent) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`)، بالإضافة إلى `A01` = `DeviceJid` الجهاز 0 | JID خادم البوت يُستخدم كهدف جلسة/جهاز لـ "bot envelope" (معالج طلب مزامنة CoEx v2 `C53148Nnt` يشفّر حمولة المزامنة إلى جهازه الأساسي، السجل `coexv2 attached bot envelope`)، ويُضاف إلى مجموعات أجهزة المستلمين (`C12M`)، ويُعامل كمرسل بوت في معالجة إيصالات إعادة المحاولة (`C33020EaI`). ليس شخصية محادثة | found (الاستخدام)؛ الغرض خارج ذلك inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID سجل ملف "Meta AI" الافتراضي المدمج (`C9i5.A00`: الاسم `Meta AI`، نص التعريف الافتراضي). عضو في اختبار bot-JID `AbstractC24760wu.A07` مع الصف التالي | found |
| `867051314767696555` | `AbstractC24760wu.A01` (مجموعة أحادية، `C24770wv`) | العضو الثاني في اختبار bot-JID `A07` (`A07(jid)` = `C24770wv` مساوٍ لـ `…135992` أو ضمن هذه المجموعة)؛ و`A07` يغذّي `AbstractC199328dk.A00` (محمول على فئة JID). الغرض الإضافي غير محلول | found (الاستخدام)، الغرض unknown |
| `17015557208` | `AbstractC24760wu.A04` | سلسلة مستخدم هاتف. `A04(jid)` صحيحة لـ LID `165332417282214` أو لهذا المستخدم الهاتفي؛ تُستخدم مع `A03` (أي JID بوت `C24770wv`، أو PN ضمن النطاقين 13135550000-13135559999 / 13165550000-13165550099) في `E76.A00` (الصنف 10 مقابل 1) وفي محمول الأهلية `C736539v.ARO`. تُقرأ كهوية PN لـ Meta AI؛ وما يفعله هذان المستهلكان بها غير محلول | found (الاستخدام)، الغرض unknown |

المجموعات في `AbstractC34361Xw`: `A05 = {…697, …698}`؛ `A03 = {…697, …698, 165332417282214}`؛ الخريطة `A04`: `…697 → […697]`، `…698 → […698, 165332417282214]`.

نوع JID: ذكر تقرير 2.26.26.4 الأربعة جميعها كـ `@s.whatsapp.net`. في 2.26.41.6 JIDs البوتات هي `C24770wv` مع `getServer() = "bot"`؛ و JID المجموعة/LID هو `C14080dr` بالخادم `"lid"`. ليست `s.whatsapp.net` (found).

جدول رقم الهاتف إلى bot-FBID: `AbstractC199338dl.A00` (`HashBiMap`، 1313555xxxx → FBID، نحو 200 إدخال، مثل `13135550002 → 867051314767696`). تستخدمه `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 تحويل التوجيه

```java
// AbstractC24760wu.A01  (getRemoteTargetJidForOutgoingMessage)
if (A08(jid))   // LID jid with user 165332417282214
    return new C24770wv("1807055946647698");
else            // phone jid
    return C0DZ.A08((UserJid) jid);   // PN -> bot JID via AbstractC199338dl table

// AbstractC24760wu.A00
if (jid is bot "1807055946647698") return new C14080dr("165332417282214");  // bot -> LID
if (jid is bot)                      return C0DZ.A07(userJid);              // bot -> phone jid
```

Found: JID البوت `…698` ↔ LID `165332417282214`؛ وجهات اتصال البوتات برقم الهاتف تُربط بـ JIDs البوتات. الدالة تؤكد "needs FBID migration" (found).

### 2.3 اللاحقة `$1`: تغيّرت

وضع تقرير 2.26.26.4 `$1` على JID التوجيه ("wire format"، `C1A2.A00()/A01()`). غير موجودة في 2.26.41.6:
- لا دالة توجيه تضيف `$1` إلى JID. التحويل في 2.2 ينتج JIDs بوتات عادية.
- تُضاف `$1` إلى سلسلة معرّف الشخصية المخزنة في سجل ملف البوت: `C24121Ab2` ينفذ `personaIdString = botFbid + "$1"`؛ و`C223219iv` يثبّت `"1807055946647697$1"` للملف الافتراضي لـ Hatch (found).
- هذه السلسلة (`C199348dm.A0A`) هي ما تكتبه `C33473Ehf.A0G` في `BotMetadata.personaId` (found).

إذن `$1` تنتمي إلى معرّف الشخصية، لا إلى JID الوجهة.

### 2.4 اكتشاف isMetaAI

```java
// C39311it
boolean A02() {                       // Hatch
  if (!BRD() || capability("ai_hatch_integration_enabled")) return flag(26189);
  return false;
}
boolean A0E(Jid jid) {
  if (jid == HATCH_697)                 return A02();
  if (jid == FALLBACK_698 || jid == LID_165332417282214) {
    if (!BRD() || capability("ai_maiba_wass_migration_receiving_enabled")) return flag(27083);
  }
  return false;
}
```

فرع Manus (العلم 25119) اختفى. معنى `BRD()` وبحث القدرة (`C09L.A04`) غير محلولين (unknown).

---

## 3. أعلام الميزات

| Flag ID | Use in 2.26.41.6 | Tier |
|---------|------------------|------|
| **25119** | يظهر فقط في جداول الأعلام (`C06510El`، الافتراضي `false` في `C08J`). لم يُعثر على قارئ. الاسم القديم `ai_bot_integration_enabled` غير موجود كسلسلة | found |
| **26189** | بوابة Hatch في `C39311it.A02()`. الافتراضي `false` (`C08J`) | found |
| **27083** | بوابة Fallback / LID في `C39311it.A0E()`. الافتراضي `false` | found |
| **26190** | إعداد JSON (`name`, `description`, `profile_thumb`) لملف Hatch الافتراضي، يُقرأ في `C223219iv` | found |
| **37227** | `C39311it.A03()`؛ `A05() = A02() && A03()`. عند كونه صحيحًا، تُعلَن القدرة `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) إلى Hatch (انظر 5)؛ و`A05` يتحكم أيضًا في telemetry/واجهة الموصلات (`C28147CLx`، `C1427261o`، `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. يعلن `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77)؛ ويتحكم أيضًا في توفر الموصلات (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. يعلن `HATCH_ARTIFACT_CARD_ENABLED` (79)؛ ويقرؤه أيضًا `HatchSpacesSync` و`C7WL` | found |

السلسلتان `ai_hatch_integration_enabled` و`ai_maiba_wass_migration_receiving_enabled` ليستا أسماء أعلام. هما إدخالان في قائمة سلاسل ميزات مبنية من العلمين 26189 / 27083 في `C25056AqU` (بجانب `username_supported` و`post_status_in_companion` و...)؛ و`ai_fbid_migration_receiving_enabled` تُضاف دون شرط. مستلم القائمة وغرضها غير مُتحقَّق منهما.

---

## 4. حقول Proto

### 4.1 Message (`C30628DTw`) المستوى الأعلى

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (حقل واحد `message` = 1) | الرسالة الصادرة ملفوفة للبوت؛ تُعيَّن في `F2K` و`C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | مهمة بوت |
| `botForwardedMessage` | **104** | `BD2` | يلف رسالة تحوي `richResponseMessage`؛ تُعيَّن في `F3E` |
| `richResponseMessage` | **97** | `DSY` | استجابة الذكاء الاصطناعي. الحقول: `messageType` 1، `submessages` 2، `unifiedResponse` 3، `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | موجود |
| `botGroupParticipantMessage` | **137** | `BD2` | موجود |
| `messageContextInfo` | **35** | `C30624DTs` | يحمل `botMetadata` |
| `protocolMessage` | **12** | `BD3` | يحمل `aiMetadataOperation` (31) |

الحقل **77** هو `commentMessage`، وليس `richResponseMessage` (تقرير 2.26.26.4 ذكر 77؛ خاطئ لهذا البناء، ومتسق مع بحث richResponseMessage المنفصل: 97).

### 4.2 WebMessageInfo (`C30626DTu`)، وليس ContextInfo

سرد تقرير 2.26.26.4 هذه كحقول ContextInfo. في 2.26.41.6 هي على `WebMessageInfo`:

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | يُعيَّن في `C34385EwW` من `C0DZ.A09(userJid)` (مستخدم الجهاز الأساسي للمستدعي) |
| `isSupportAiMessage` | **70** | bool | يُعيَّن في `C34378EwP.C57` عندما تحمل الرسالة بت العلم `268435456` ويمر فحص؛ ويُقرأ مجددًا في `C59`. مع `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | الاستشهادات |
| `botTargetId` | **73** | string | لا كاتب في العميل: `botTargetId_` يظهر فقط كقيمة افتراضية في المُنشئ وفي جدول مخطط `C30626DTu`، ولا يُسند في أي مكان آخر (grep على المصدر كاملًا) |
| `agentId` | **47** | string | موجود، لم يُحلَّل |

ظهور حقول WebMessageInfo هذه على السلك وكيفيته غير مُتحقَّق منه (unknown). "`true` لجميع رسائل Meta AI" غير مسنود: يُعيَّن لكل رسالة بحسب العلم، وليس دون شرط.

### 4.3 MessageContextInfo (`C30624DTs`)

| Field | Number | Type |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `personaId` | **2** | string | من سجل ملف البوت (`C199348dm.A0A`)، مثل `1807055946647697$1`. ليست `"meta_ai"` ثابتة |
| `pluginMetadata` | **3** | `DTL` | إعداد الإضافة |
| `invokerJid` | **5** | string | المستدعي |
| `aiConversationContext` | **20** | bytes | حالة المحادثة |
| `botResponseId` | **26** | string | معرّف الاستجابة |

حقول أخرى موجودة (الأسماء من `*_FIELD_NUMBER`، الأنواع لم تُقرأ): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

يُملأ `personaId` في `C33473Ehf.A0G`؛ وتعود الدالة مبكرًا إذا لم تكن لدى الملف سلسلة شخصية.

### 4.5 PluginMetadata (`DTL`)

| Field | Number | Type | Value |
|-------|--------|------|-------|
| `provider` | **1** | int32 | معرّف المزوّد |
| `pluginType` | **2** | enum `C4E0` | انظر أدناه |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

ثوابت `C4E0` (القيمة = ترتيب المُنشئ؛ كونها مساوية لرقم proto هو inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. القيم القديمة 8/9/15 لم تتغير؛ والـ enum أكبر.

### 4.6 Action oneof (`C61331Rfl`، enum الحالات `EnumC61601RkN`)

| Number | Case | Tier |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

هذا oneof لحقول إجراءات، وليس enum قيم عادي. موضع تضمينه لم يُتتبَّع (unknown).

### 4.7 عملية بيانات AI الوصفية (حامل Hatch)

| Message | Field | Number | Type |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. بروتوكول الطلب (Hatch metadata)

تُبنى الطلبات بواسطة `HF1` (`HatchMetadataRequestManager`)، فئة coroutine `HatchMetadataRequestManager$sendRequest$2`. يختلف غلاف JSON عن 2.26.26.4: `method` و`params` متداخلان تحت `payload`.

```json
{
  "version": 1,
  "type": "req",
  "payload": {
    "method": "<method_name>",
    "params": { },
    "accepts_encoding": ["gzip"]
  }
}
```

`params` و`accepts_encoding` اختياريان (found). معرّف الطلب ليس في JSON؛ هو `BB2.requestId` (سلسلة عشوائية من `C20F.A0x()`).

مسار الإرسال (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- الطلبات المعلّقة: `HF1.A04` (`ConcurrentHashMap`، requestId → continuation) و`HF1.A03` (requestId → `GuR`). تُمسحان كلتاهما في `finally`. ذكر تقرير 2.26.26.4 خريطة واحدة فقط `A02`.
- المهلة: تعيد `GDB.A00` وتسجّل `HatchMetadataRequestManager/sendRequest timed out method=`.
- العدد الصحيح `138` الممرَّر إلى `C37393GKy` غير محلول (unknown).
- الحامل هو `ProtocolMessage.aiMetadataOperation` (الحقل 31)، وليس رسالة محادثة عادية (تغيّر).
- الحزمة `com.whatsapp.bot.infra.message.aimetadata` تحتوي فئات `Ideas*Wire` / `Idea*Wire` (found). علاقتها بأسماء الدوال inferred فقط؛ لم تُعدَّد أسماء الدوال.
- جهة الاستقبال التي تُكمل `A04` لم تُتتبَّع. مطابقة الاستجابة مع `requestId` هي inferred من الخريطة `A04` و`BB2.requestId`.

**ادعاء عدم وجود فضاء أسماء XMPP مخصص:** لم يُرَ أي معالجة لـ `w:ai` / `wa:ai` في المسار المتتبَّع؛ مبني على الغياب، لم يُعاد التحقق منه بشكل شامل.

**إعلان القدرات (found، `C33284Eea`):** عندما تكون الوجهة JID الخاص بـ Hatch `…697` (`AbstractC34361Xw.A00`) وتنجح بوابة، يبني العميل `DPJ` (حقل enum متكرر وحيد `capabilities` = 1، القيم `EnumC32144E2q`) وتخزنه `C33473Ehf.A06` في `BotMetadata.capabilityMetadata` (13) للرسالة الصادرة، مع `BotMetadata.timezone` (8) = معرّف `TimeZone` للجهاز. القدرات المضافة بحسب البوابة:

| Gate | Capability (enum number) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

الأرقام هي الوسيط الثاني لمُنشئ الـ enum؛ كونها مساوية لأرقام proto هو inferred. يسرد الـ enum أيضًا قدرات الاستجابة الغنية (`RICH_RESPONSE_TABLE` و`RICH_RESPONSE_CODE` و`AI_MEMORY` و`PROGRESS_INDICATOR` و...).

**أمثلة الطلبات (found، مفاتيح `params` المقروءة في مواضع الاستدعاء؛ الهدف هو JID الخاص بـ Hatch `…697` ما لم يستخدم موضع الاستدعاء JID المحادثة):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | يُبنى في `HatchIdeasManager$execute$job$1` (المفاتيح لم تُقرأ)؛ مرفق callback من نوع `onPart` |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` مسلسلة إلى JSON؛ مرفق callback من نوع `onPart` |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` فقط عند عدم كونه فارغًا) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

شكل البايتات في `BB2.data` (شكل found، قيم مثالية):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

يُكتب `accepts_encoding` فقط عندما يكون `acceptsGzipResponse` لدى المستدعي صحيحًا؛ و`params` فقط عندما لا يكون null. يُسجَّل callback من نوع `onPart` في `A03` فقط عندما يمرره المستدعي.

**رسالة محادثة إلى البوت (أجزاء found):**
- تُلف `Message` الصادرة من جديد داخل `Message.botInvokeMessage` (`F2K`، `C33284Eea`)، والغلاف `BD2` يحمل الرسالة في الحقل 1. في `F2K` يُتخطى اللف (تُعيَّن الرسالة مباشرة) عندما تكون `C13S.A00()` خاطئة، أو تكون `A10` للرسالة خاطئة، أو يكون العلم **10646** مفعّلًا (found).
- يبني `BotMetadata` كل من `C33473Ehf.A0E` / `A0G`. تبحث `A0G` عن سجل الملف لـ JID البوت الهدف (`C199358dn.A06(userJid)`، سلسلة الشخصية `C199348dm.A0A`)؛ وإذا كانت تلك السلسلة فارغة تعود الدالة دون كتابة بيانات البوت، وإلا تعيّن `personaId` (2) وعند وجودها `suggestedPromptMetadata` (4) ورسائل فرعية أخرى. تُخزَّن سلسلة الشخصية عند إنشاء سجل الملف (`C24121Ab2` يبني `<id>$1`؛ و`C223219iv` يثبّت `1807055946647697$1` لـ Hatch). أما هل تقع `messageContextInfo` على `Message` الخارجية أم على الرسالة داخل `botInvokeMessage` فلم يُحسم.
- تُعيَّن `botMessageInvokerJid` / `isSupportAiMessage` على `WebMessageInfo` بواسطة خطافات D36 (`C34385EwW`، `C34378EwP`).

---

## 6. بروتوكول الاستجابة

### 6.1 النقل

لم يُعاد التحقق كما ورد في 2.26.26.4 ("رسائل عادية مع بايتات `hatchMetadataSync`"، الفئة `Azz`). Found: `hatchMetadataSync` موجود في `C25754B9o` داخل `ProtocolMessage.aiMetadataOperation`. يُفترض أن استجابات Hatch تصل بالطريقة نفسها وتُطابَق بـ `requestId` (inferred). طلبات Hatch هي استدعاءات دوال؛ ولم يثبت أنها مسار ردود المحادثة العادية.

### 6.2 البث / المقاطع: غير مدعوم كما وُصف

جدول 2.26.26.4 (`chunkOrder` و`isLastChunk` و`clientStreaming` و`serverStreaming` و`streamingSidecar`) كآلية بث واحدة لـ Meta AI غير مسنود في 2.26.41.6:

| Field | Where it is in 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` الحقل **7** (إشعار history-sync، `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) و`C25838BCy` الحقل **5** (history sync) |
| `isLastChunk` | `C55285Ou6` الحقل **8** (رسالة مع `attestationBundles` و`teeModelConfig` و`violationSignal`؛ متعلقة بـ TEE) |
| `streamingSidecar` | الحقل **18** في رسائل الصورة/الفيديو/الصوت (`C30607DTb`، `DTR`، `DTX`، `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | غير موجودة كحقول proto |

لم يُعثر على إعادة تجميع مقاطع لردود Meta AI. الموجود لـ Hatch: `GuR(method, onPart)` — callback من نوع `onPart` لكل طلب (found)؛ وأنه يحمل نتائج جزئية هو inferred من الاسم.

### 6.3 الاستجابة الغنية (الحقل 97)

`richResponseMessage` (`DSY`) = الحقل **97** في `Message`. توجد فئات عرض: `AiRichResponseFooterView` و`UnifiedResponseActionHandlerFactory` (الحزمة `com.whatsapp.conversationrow.botrichresponse`) (found). الاستشهادات: `WebMessageInfo.supportAiCitations` (72). أنواع المحتوى (صور، جداول، شيفرة) لم يُعاد التحقق منها هنا؛ انظر بحث richResponseMessage المنفصل.

### 6.4 مؤشر الكتابة

الصادر (found، `C199098dN.A01`، السجل `HandleMeComposing/handleComposing`): حالة محادثة XMPP قياسية، دون فضاء أسماء مخصص في الشيفرة المقروءة.
- الحالة العادية (لا بوت مذكور، أو JID بوت حُلّ إلى الافتراضي): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- بوت مذكور في المحادثة: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- يُرسل عبر `C10140Tq.A0X` مع IQ-type int 4.

الوارد (found، معالج stanza `C40511kx`): `<chatstate>` بابن `composing` (و`media` اختياري) يستدعي callback الكتابة العام مع `from`/`participant`؛ و`paused` يستدعي callback الإيقاف المؤقت. لم يُعثر على فرع خاص بالبوتات في هذا المعالج، فـ `composing` من JID بوت يمر بالمسار نفسه كأي جهة اتصال (inferred؛ لم يُلاحَظ stanza كتابة بوت من الخادم). `BotMetadata.progressIndicatorMetadata` (12) والقدرة `PROGRESS_INDICATOR` موجودان كآلية تقدم منفصلة داخل الرسالة (أسماء فقط، لم تُتتبَّع).

### 6.5 مزامنة ملف البوت

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) يجدول `BotProfileForChatListWorker` في `A03()`: طلب WorkManager موسوم `BotProfileSyncManager` مع `setBackoffCriteria(policy, 1, MINUTES)` وقيد (قيمة النوع غير محلولة). الدقيقة الواحدة هي **backoff** لإعادة المحاولة، وليست فترة دورية. عبارة 2.26.26.4 "every ~1 minute" غير مسنودة (تغيّر). `A02(groupJid, userJid)` يطلب ملفًا واحدًا (`requestBotProfileResult`). ليست جزءًا من مزامنة القائمة العادية (دون تغيير).

سجل الملف `C199348dm`: نوع البوت (`C1XY`)، jid، الاسم المعروض (`A09`)، الوصف (`A07`)، سلسلة الشخصية (`A0A`)، الصور المصغرة، الطابع الزمني.

### 6.6 سلاسل نوع البوت

`C718732k.A00(String)` تربط: `meta_ai` و`meta_ai_thread` و`tee_meta_ai_group` و`side_chat` و`manus` و`hatch` و`muse` و`third_party`؛ وأي شيء آخر يصبح `AnonymousClass399(str)`. هذه تسميات نوع البوت (تُستخدم أيضًا في مرشحات الواجهة)، وليست قيم `BotMetadata.personaId` (found).

---

## 7. التخزين

- `MetaAiMemoryStore`: لا توجد فئة بهذا الاسم في 2.26.41.6. المكافئ المعثور عليه هو جدول `meta_ai_memory` ينشئه صنف المخطط `C23621AHm` (found): `memory_id` TEXT و`memory_content` TEXT و`bot_jid_row_id` INTEGER، والفهرس `meta_ai_memory_memory_content_index` على `memory_content`. أي ملف قاعدة بيانات يحويه غير محلول. ذات صلة (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (واجهة؛ الاسم يقول deprecated)، SharedPrefs `meta_ai_memory_disclosure_seen` (شاشة تصميم المكالمة الصوتية، `C29434Cpx`)، وقدرات enum `AI_MEMORY` 4 و`AI_SHARED_MEMORY` 40 و`AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`)، و`BotMetadata.memoryMetadata` (15).
- مفتاح SharedPrefs `"meta_ai_forward_disclosure_seen"`: موجود، منطقي، يُقرأ في `C230589xr.A03` لـ `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: موجود في `com.whatsapp.metaai.incognito.infra` (found).
- تخزين منفصل لمحادثات Meta AI خارج `msgstore.db` (2.26.26.4، لم يُعاد التحقق): لم يُعثر على فئة مخزن محادثات؛ و`meta_ai_memory` يحوي حقائق الذاكرة فقط، فالادعاء لا مسنود ولا مدحوض.

---

## 8. لماذا لا يحصل Baileys على استجابة

جميع الصفوف **inferred**: مقارنة ساكنة بين متطلبات العميل ومسار إرسال طرف ثالث؛ دون اختبار حي.

| Issue | Basis in 2.26.41.6 | Tier |
|-------|--------------------|------|
| نوع JID الهدف خاطئ | JIDs البوتات تستخدم الخادم `bot` (`C24770wv`)، وليس `s.whatsapp.net`؛ وبوتات أرقام الهاتف تُربط عبر جدول PN→FBID | found (فئة JID)، inferred (الأثر) |
| `$1` على JID التوجيه | غير موجودة. `$1` على سلسلة معرّف الشخصية | found |
| غياب غلاف `botInvokeMessage` | يلف العميل `Message` الصادرة في الحقل 67 (`F2K`) | found، المتطلب inferred |
| غياب `messageContextInfo.botMetadata` | يكتب العميل فيه `personaId` و`invokerJid` وغيرهما | found، المتطلب inferred |
| `personaId = "meta_ai"` | ليس ما يرسله العميل؛ يرسل سلسلة شخصية الملف (مثل `1807055946647697$1`) | found |
| غياب `aiConversationContext` | الحقل 20 في `BotMetadata`؛ السلوك في الدور الأول unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | حقول WebMessageInfo تُعيَّن بخطافات العميل؛ متطلب الخادم unknown | unknown |
| `botTargetId` | لا كاتب في شيفرة العميل | found |
| الرد لا يُحلَّل | `richResponseMessage` هو الحقل 97 في `Message` | found |
| إعادة تجميع المقاطع | غير مدعومة بدليل 2.26.41.6 (انظر 6.2) | found |

---

## 9. إصلاح Baileys

لا يُدَّعى وجود تنفيذ يعمل. ما يلي رسم هيكلي لمواضع الحقول بحسب 2.26.41.6، موسوم **inferred**؛ لم يُشغَّل ضد خادم.

### 9.1 الهدف

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

هل تعمل سلسلة الخادم `bot` كهدف ترحيل (relay) في Baileys، وكيف يشتق الخادم `to` النهائي للـ stanza، أمر unknown.

### 9.2 موضع الحقول (الشكل فقط)

```ts
// inferred shape, field numbers found in 2.26.41.6
const content = {
  botInvokeMessage: {            // Message 67, wrapper with message = 1 (found; wrap is conditional, see 5)
    message: {
      extendedTextMessage: { text }
    }
  },
  // Placement of messageContextInfo (outer Message vs. inner message) is unresolved.
  messageContextInfo: {          // Message 35
    botMetadata: {               // MessageContextInfo 7
      personaId: '1807055946647697$1', // BotMetadata 2: profile persona string (found in C223219iv for Hatch)
      invokerJid: yourJid,             // BotMetadata 5: field exists; writer not read
      timezone: 'Europe/Berlin',       // BotMetadata 8: client sets the TimeZone ID when advertising capabilities (Hatch)
      capabilityMetadata: { capabilities: [/* EnumC32144E2q numbers, Hatch only */] } // BotMetadata 13
      // aiConversationContext (20): field exists; client write not traced, do not invent a value
    }
  }
}
```

- تضمين `botMetadata` في `messageContextInfo` (الحقل 7) **found**. و`capabilityMetadata` (13) و`timezone` (8) يكتبهما العميل فقط لوجهات Hatch (found)؛ متطلبهما على الخادم unknown. هل يملك proto الخاص بـ `baron-baileys-v2` هذه الحقول لم يُفحص؛ وإن لم يملكها وجب توسيع proto (inferred).
- `isSupportAiMessage` (70) و`botMessageInvokerJid` (58) حقلان في `WebMessageInfo`. هل يجب وجودهما على السلك unknown؛ لا تضعهما في `contextInfo` (كان ذلك خاطئًا في تقرير 2.26.26.4).
- `botTargetId`: لا كاتب في العميل في أي مكان من الشيفرة المفكَّكة (found)؛ لا تعيّنه.
- اللف الدقيق (`botInvokeMessage.message` يحوي الرسالة الحقيقية مقابل بجانبها) يتبع إعادة اللف في `F2K` / `C33284Eea`؛ والنتيجة المسلسلة الدقيقة لم تُستنسخ (unknown).

### 9.3 معالجة الاستجابة

- الردود الغنية: `Message.richResponseMessage` هو الحقل **97** (found). حلّل ذلك، لا الحقل 77.
- أزل معالجة المقاطع: `chunkOrder` / `isLastChunk` ليسا حقلي بث لـ Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) الخاص بـ Hatch هو قناة طلبات JSON؛ ولم يثبت أن ردود المحادثة العادية تستخدمه.

### 9.4 سياق المحادثة

`BotMetadata.aiConversationContext` (20) موجود. أن الخادم يعيد حالة محدَّثة في الردود وأنه يجب إرجاعها هو **inferred** (من اسم الحقل وتقرير 2.26.26.4)؛ غير مُتحقَّق منه.

---

## 10. التدفقات

### 10.1 رسالة محادثة إلى البوت (found جهة العميل، inferred جهة الخادم)

```
[Client] outgoing Message
    │  F2K / C33284Eea: Message.botInvokeMessage = BD2{ message = original }
    │  C33473Ehf: messageContextInfo.botMetadata{ personaId = profile.A0A, ... }
    │  D36 hooks: WebMessageInfo.botMessageInvokerJid (58), isSupportAiMessage (70)
    ▼
[Routing] AbstractC24760wu.A01: LID 165332417282214 → bot 1807055946647698
    │  phone JID → bot JID via PN→FBID table
    ▼
[WA Server] (not observed; inferred) → Meta AI backend
    ▼
[Client] incoming Message.richResponseMessage (97)  →  AiRichResponseFooterView / UnifiedResponseActionHandlerFactory
```

### 10.2 طلب بيانات Hatch الوصفية (found جهة العميل)

```
[Feature code] HF1.A01(jid, method, params)
    │  requestId = random; A03[requestId] = GuR(method, onPart); A04[requestId] = continuation
    ▼
JSON {"version":1,"type":"req","payload":{"method","params","accepts_encoding"}} → bytes
    ▼
Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
    ▼
[WA Server] (not observed)
    ▼
Response: matched by requestId (inferred) → continuation resumes; timeout → GDB.A00
```

---

## 11. التغييرات مقابل 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | قديم، العلم 25119 | غير موجود. 25119 فقط في جداول الأعلام، بلا قارئ |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697 و698 على الخادم `bot` (`C24770wv`)؛ 165332417282214 هو `lid` (`C14080dr`) |
| New JID constants | لا شيء مسرود | `1807055946647699` (CoEx v2 bot-envelope / هدف مجموعة الأجهزة)، `2942131436135992` (JID ملف Meta AI الافتراضي، اختبار bot-JID `A07`)، `867051314767696555` (عضو `A07` الثاني، الغرض unknown)، `17015557208` (PN لـ Meta AI، `A04`) |
| `$1` suffix | على JID التوجيه، `C1A2.A00/A01` | ليست على JID؛ تُضاف إلى سلسلة معرّف الشخصية (`C24121Ab2`، `C223219iv`) |
| Routing conversion | إضافة `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`، PN → bot عبر جدول FBID |
| Flag names 25119/26189/27083 | أسماء أعلام `ai_*` | السلاسل إدخالات قائمة ميزات (`C25056AqU`)؛ 26190 = JSON ملف Hatch؛ 37227/37852/37054 تتحكم في قيم قدرات Hatch 76 / 77 / 79 |
| `richResponseMessage` | الحقل 77 | الحقل 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 على "WebMessageInfo" | 67 / 100 / 104 على `Message`؛ وكذلك 131، 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73؛ `botTargetId` لا يُكتب أبدًا |
| BotMetadata location | "مضمَّن في الرسالة" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | سلسلة شخصية الملف، مثل `1807055946647697$1`؛ و`meta_ai` تسمية نوع بوت |
| Plugin types | 8, 9, 15 | نفسها، والـ enum له 18 قيمة (حتى 17) |
| Action enum | enum قيم 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Hatch JSON envelope | `method`, `params` في المستوى الأعلى | متداخلان تحت `payload`؛ ويضيف `accepts_encoding` |
| Hatch carrier | رسالة عادية، الفئة `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`؛ ويضيف `bizAiMetadataSync` (2) |
| Pending maps | واحدة (`A02`) | اثنتان: `A04` continuations، `A03` callbacks الأجزاء `GuR` |
| Streaming fields | جدول مقاطع واحد لـ Meta AI | `chunkOrder` (history sync)، `isLastChunk` (رسالة TEE)، `streamingSidecar` (وسائط)؛ `clientStreaming`/`serverStreaming` غير موجودة |
| Profile sync interval | "every ~1 min" | الدقيقة هي WorkManager backoff، وليست فترة دورية |
| `MetaAiMemoryStore` | موجود | غير موجود بالاسم؛ الجدول `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) موجود |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | موجودة | موجودة |
| Typing indicator (chatstates) | Found | Found: الصادر `<chatstate><composing/></chatstate>`، مع `<bot jid/>` عند ذكر بوت (`C199098dN.A01`)؛ الوارد `composing`/`paused` عبر المعالج العام `C40511kx`، بلا فرع خاص بالبوتات |
| Capability advertisement | غير موثّق | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) لـ Hatch؛ الأعلام 37227 / 37852 / 37054 تقابل قيم enum 76 / 77 / 79 |
| Hatch request examples | غير موثّقة | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
