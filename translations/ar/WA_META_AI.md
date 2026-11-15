<!-- src-sha1: 92bebfe6214e20e4e50526fbb6583d35cc44e808 -->
# WhatsApp Meta AI — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** داخليات Meta AI — JIDs، التوجيه، حقول proto، طلبات بيانات Hatch الوصفية، عرض الاستجابة، لماذا يفشل Baileys، الحل

---

## 1. ما هو Meta AI (تقنياً)

Meta AI جهة اتصال بوت تُعنوَن بـJIDs بوت خاصة (الخادم `bot`)، بحقول proto خاصة بالبوت على أنواع الرسائل العادية وقناة طلب JSON منفصلة ("بيانات Hatch الوصفية") تُحمَل في `ProtocolMessage`. كل العبارات تحليل ساكن للـAPK المفكَّك. المستوى: **found** = مقروء في الكود، **inferred** = مُستنتَج من الكود، **unknown** = غير محسوم.

الأسماء في هذا التقرير التي كانت مُشوَّشة في 2.26.26.4 (`C1A2`، `B2Y`، `B2C`، `Azz`، `C26654Bv8`) أُعيد حلّها من مراسي ثابتة؛ لا توجد بهذه الأسماء في 2.26.41.6.

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| BotJid | `C24770wv` | صنف JID، الخادم `"bot"`، النوع 26، سلسلة عددية من 1-20 حرفاً، بلا صفر بادئ |
| ثوابت JID البوت | `AbstractC34361Xw` | ثوابت ومجموعات Hatch / Fallback / LID |
| تخطيط JID | `AbstractC24760wu` | تخطيط بوت ↔ LID، تحويل الهدف الخارج |
| الضبط | `C39311it` | ضبط علم الميزة لكل JID (`A0E(Jid)`) |
| مدير طلب Hatch | `HF1` (`HatchMetadataRequestManager`) | طلبات JSON، خريطة معلَّقة |
| باني بروتو Hatch | `Hf6` | يبني `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | بروتو `Message` |
| WebMessageInfo | `C30626DTu` | بروتو `WebMessageInfo` |
| ProtocolMessage | `BD3` | بروتو `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | يحمل `botMetadata` |
| BotMetadata | `C30615DTj` | بيانات بوت وصفية لكل رسالة |
| سجل ملف تعريف البوت | `C199348dm` | الاسم، الوصف، سلسلة معرّف الشخصية، الصورة المصغَّرة |

---

## 2. JIDs الخاصة بـMeta AI

### 2.1 JIDs مُعثور عليها في الكود

| الثابت | الصنف | الدور | المستوى |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) عبر `AbstractC34361Xw.A00` | **Hatch**، الأساسي. يُبنى الملف الشخصي الافتراضي في `C223219iv` من حمولة العلم **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) عبر `AbstractC34361Xw.A01` | Fallback. مضبوط بالعلم 27083 | found |
| `165332417282214` | `C14080dr` (الخادم `"lid"`) عبر `AbstractC34361Xw.A02` | نظير LID لـ`…698` | found |
| `1807055946647696` | لا شيء | Manus (قديم في 2.26.26.4): **غير موجود** في 2.26.41.6 | found (غائب) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`)، إضافة إلى `A01` = `DeviceJid` الجهاز 0 | JID خادم بوت يُستخدَم كهدف جلسة/جهاز لـ"غلاف بوت" (معالِج طلب مزامنة CoEx v2 `C53148Nnt` يشفِّر حمولة المزامنة إلى جهازه الأساسي، سجل `coexv2 attached bot envelope`)، يُضاف إلى مجموعات أجهزة المستقبل (`C12M`)، ويُعامَل كمُرسِل بوت في معالجة إيصالات إعادة المحاولة (`C33020EaI`). ليس شخصية دردشة | found (الاستخدام)؛ الغرض بما يتجاوز ذلك مستنتج |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID سجل الملف الشخصي الافتراضي المُضمَّن "Meta AI" (`C9i5.A00`: الاسم `Meta AI`، نص المقدمة الافتراضي). عضو في فحص JID البوت `AbstractC24760wu.A07` إلى جوار الصف التالي | found |
| `867051314767696555` | `AbstractC24760wu.A01` (مجموعة singleton، `C24770wv`) | العضو الثاني في فحص `A07` لـJID البوت (`A07(jid)` = `C24770wv` يساوي `…135992` أو في هذه المجموعة)؛ يُغذِّي `A07` دالة `AbstractC199328dk.A00` (مُسنَد من فئة JID). الغرض الإضافي غير محسوم | found (الاستخدام)، الغرض غير معروف |
| `17015557208` | `AbstractC24760wu.A04` | سلسلة مستخدم هاتف. `A04(jid)` صحيحة لـLID `165332417282214` أو لمستخدم هذا الهاتف؛ تُستخدَم مع `A03` (أي JID بوت `C24770wv`، أو PN في نطاقات 13135550000-13135559999 / 13165550000-13165550099) في `E76.A00` (الفئة 10 مقابل 1) وفي المُسنَد `C736539v.ARO` للأهلية. تُقرأ كهوية PN الخاصة بـMeta AI؛ ما يفعله هذان المُستهلِكان بها غير محسوم | found (الاستخدام)، الغرض غير معروف |

المجموعات في `AbstractC34361Xw`: `A05 = {…697, …698}`؛ `A03 = {…697, …698, 165332417282214}`؛ الخريطة `A04`: `…697 → […697]`، `…698 → […698, 165332417282214]`.

نوع JID: أدرج تقرير 2.26.26.4 الأربعة كـ`@s.whatsapp.net`. في 2.26.41.6 JIDs البوت هي `C24770wv` بـ`getServer() = "bot"`؛ والمجموعة/LID هي `C14080dr` بالخادم `"lid"`. ليس `s.whatsapp.net` (found).

جدول رقم الهاتف إلى FBID البوت: `AbstractC199338dl.A00` (`HashBiMap`، 1313555xxxx ← FBID، حوالي 200 إدخال، مثل `13135550002 → 867051314767696`). يستخدمه `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

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

مُعثور عليه: JID البوت `…698` ↔ LID `165332417282214`؛ جهات اتصال البوت برقم هاتف تُخطَّط إلى JIDs بوت. تطرح الدالة "needs FBID migration" (found).

### 2.3 بادئة `$1`: تغيَّرت

وضع تقرير 2.26.26.4 `$1` على JID التوجيه ("شكل السلك"، `C1A2.A00()/A01()`). غير مُعثور عليها في 2.26.41.6:
- لا دالة توجيه تُلحِق `$1` بـJID. التحويل في 2.2 يُنتج JIDs بوت صِرفة.
- تُلحَق `$1` بسلسلة معرّف الشخصية المُخزَّنة في سجل الملف الشخصي للبوت: `C24121Ab2` تُنفِّذ `personaIdString = botFbid + "$1"`؛ `C223219iv` تُثبِّت `"1807055946647697$1"` للملف الافتراضي الخاص بـHatch (found).
- تلك السلسلة (`C199348dm.A0A`) هي ما يكتبه `C33473Ehf.A0G` في `BotMetadata.personaId` (found).

فـ`$1` تنتمي إلى معرّف الشخصية، لا إلى JID الوجهة.

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

فرع Manus (العلم 25119) غائب. معنى `BRD()` والبحث عن القدرة (`C09L.A04`) غير محسوم (غير معروف).

---

## 3. أعلام الميزات

| معرّف العلم | الاستخدام في 2.26.41.6 | المستوى |
|---------|------------------|------|
| **25119** | يظهر فقط في جداول الأعلام (`C06510El`، الافتراضي `false` في `C08J`). لا قارئ مُعثور عليه. الاسم القديم `ai_bot_integration_enabled` غير مُعثور عليه كسلسلة | found |
| **26189** | بوّابة Hatch في `C39311it.A02()`. الافتراضي `false` (`C08J`) | found |
| **27083** | بوّابة Fallback / LID في `C39311it.A0E()`. الافتراضي `false` | found |
| **26190** | إعداد JSON (`name`، `description`، `profile_thumb`) للملف الافتراضي الخاص بـHatch، يُقرأ في `C223219iv` | found |
| **37227** | `C39311it.A03()`؛ `A05() = A02() && A03()`. عندما صحيح، تُعلَن القدرة `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) لـHatch (انظر 5)؛ `A05` تضبط أيضاً قياس/واجهة الموصِّل عن بُعد (`C28147CLx`، `C1427261o`، `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. تُعلِن `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77)؛ تضبط أيضاً توافر الموصِّل (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. تُعلِن `HATCH_ARTIFACT_CARD_ENABLED` (79)؛ تقرؤها أيضاً `HatchSpacesSync` و`C7WL` | found |

السلاسل `ai_hatch_integration_enabled`، `ai_maiba_wass_migration_receiving_enabled` ليست أسماء أعلام. إنها إدخالات لقائمة سلاسل ميزات مبنية من الأعلام 26189 / 27083 في `C25056AqU` (إلى جوار `username_supported`، `post_status_in_companion`، ...)؛ تُضاف `ai_fbid_migration_receiving_enabled` دون شرط. مستلِم القائمة والغرض منها غير مؤكَّدين.

---

## 4. حقول Proto

### 4.1 Message (`C30628DTw`) على المستوى الأعلى

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (حقل واحد `message` = 1) | رسالة خارجة مُغلَّفة للبوت؛ تُضبَط في `F2K`، `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | مهمة بوت |
| `botForwardedMessage` | **104** | `BD2` | تُغلِّف رسالة تحمل `richResponseMessage`؛ تُضبَط في `F3E` |
| `richResponseMessage` | **97** | `DSY` | استجابة الذكاء الاصطناعي. الحقول: `messageType` 1، `submessages` 2، `unifiedResponse` 3، `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | موجود |
| `botGroupParticipantMessage` | **137** | `BD2` | موجود |
| `messageContextInfo` | **35** | `C30624DTs` | يحمل `botMetadata` |
| `protocolMessage` | **12** | `BD3` | يحمل `aiMetadataOperation` (31) |

الحقل **77** هو `commentMessage`، لا `richResponseMessage` (كان 77 في تقرير 2.26.26.4؛ خطأ لهذا البناء، ويتسق مع بحث `richResponseMessage` المنفصل: 97).

### 4.2 WebMessageInfo (`C30626DTu`)، لا ContextInfo

أدرج تقرير 2.26.26.4 هذه كحقول ContextInfo. في 2.26.41.6 هي على `WebMessageInfo`:

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | تُضبَط في `C34385EwW` من `C0DZ.A09(userJid)` (مستخدم الجهاز الأساسي للمُستدعي) |
| `isSupportAiMessage` | **70** | bool | تُضبَط في `C34378EwP.C57` عندما تحمل الرسالة بت علم `268435456` وينجح فحص؛ تُقرأ في `C59`. إلى جوار `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | رسالة مُكرَّرة | الاستشهادات |
| `botTargetId` | **73** | string | لا كاتب في العميل: `botTargetId_` تظهر فقط كقيمة افتراضية في الباني وفي جدول مخطط `C30626DTu`، لا تُعيَّن في أي مكان آخر (بحث grep كامل للمصدر) |
| `agentId` | **47** | string | موجود، لم يُحلَّل |

ما إذا كانت حقول WebMessageInfo هذه تظهر على السلك وكيف، غير مؤكَّد (غير معروف). "`true` لكل رسائل Meta AI" غير مدعوم: تُضبَط بحسب علم كل رسالة، لا دون شرط.

### 4.3 MessageContextInfo (`C30624DTs`)

| الحقل | الرقم | النوع |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `personaId` | **2** | string | من سجل ملف البوت (`C199348dm.A0A`)، مثل `1807055946647697$1`. ليست `"meta_ai"` ثابتة |
| `pluginMetadata` | **3** | `DTL` | إعداد الإضافة |
| `invokerJid` | **5** | string | المُستدعي |
| `aiConversationContext` | **20** | bytes | حالة المحادثة |
| `botResponseId` | **26** | string | معرّف الاستجابة |

حقول أخرى موجودة (الأسماء من `*_FIELD_NUMBER`، الأنواع غير مقروءة): `suggestedPromptMetadata` 4، `searchMetadata` 6، `memuMetadata` 7، `timezone` 8، `modelMetadata` 10، `messageDisclaimerText` 11، `progressIndicatorMetadata` 12، `capabilityMetadata` 13، `imagineMetadata` 14، `memoryMetadata` 15، `renderingMetadata` 16، `botMetricsMetadata` 17، `botLinkedAccountsMetadata` 18، `richResponseSourcesMetadata` 19، `botPromotionMessageMetadata` 21، `botModeSelectionMetadata` 22، `botQuotaMetadata` 23، `botAgeCollectionMetadata` 24، `conversationStarterPromptId` 25، `verificationMetadata` 27، `unifiedResponseMutation` 28، `botMessageOriginMetadata` 29، `inThreadSurveyMetadata` 30، `botThreadInfo` 31، `sessionTransparencyMetadata` 33، `botDocumentMessageMetadata` 34، `botGroupMetadata` 35، `botRenderingConfigMetadata` 36، `botInfrastructureDiagnostics` 37، `aiMediaCollectionMetadata` 38، `commandMetadata` 39، `resolvedToolCallMetadata` 40، `subscriptionUpsellMetadata` 41، `pttPromptMetadata` 42، `botHistoryShareMetadata` 43، `responseStoppedByUser` 44.

تُملأ `personaId` في `C33473Ehf.A0G`؛ تُعيد مبكراً إذا لم يحمل الملف الشخصي سلسلة شخصية.

### 4.5 PluginMetadata (`DTL`)

| الحقل | الرقم | النوع | القيمة |
|-------|--------|------|-------|
| `provider` | **1** | int32 | معرّف المزوِّد |
| `pluginType` | **2** | تعداد `C4E0` | انظر أدناه |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

ثوابت `C4E0` (القيمة = ترتيب الباني؛ تساوي رقم proto مستنتج): UNSET 0، ANIMATE 1، BACKDROP 2، EDIT 3، EDIT_FLASH 4، FEELS 5، FLASH 6، FLASH_TO_BASE 7، **IMAGINE 8**، **MEMU 9**، REIMAGINE 10، RESTYLE 11، SAM 12، STICKERS 13، VIDEO 14، **MEMU_AND_IMAGINE 15**، MEMU_STICKERS 16، IMAGINE_USER_UPLOADED_IMAGE 17. القيم القديمة 8/9/15 غير مُغيَّرة؛ التعداد أكبر.

### 4.6 oneof الإجراء (`C61331Rfl`، تعداد الحالة `EnumC61601RkN`)

| الرقم | الحالة | المستوى |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

هذا oneof لحقول إجراء، لا تعداد قيمة صِرف. أين يُضمَّن لم يُتعقَّب (غير معروف).

### 4.7 عملية بيانات الذكاء الاصطناعي الوصفية (ناقل Hatch)

| الرسالة | الحقل | الرقم | النوع |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. بروتوكول الطلب (بيانات Hatch الوصفية)

تُبنى الطلبات بواسطة `HF1` (`HatchMetadataRequestManager`)، صنف coroutine `HatchMetadataRequestManager$sendRequest$2`. غلاف JSON يختلف عن 2.26.26.4: `method` و`params` متداخلان تحت `payload`.

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

`params` و`accepts_encoding` اختياريان (found). معرّف الطلب ليس في JSON؛ إنه `BB2.requestId` (سلسلة عشوائية من `C20F.A0x()`).

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

- الطلبات المعلَّقة: `HF1.A04` (`ConcurrentHashMap`، requestId ← continuation) و`HF1.A03` (requestId ← `GuR`). كلاهما يُمحى في `finally`. أدرج تقرير 2.26.26.4 خريطة واحدة فقط باسم `A02`.
- المهلة: تُعيد `GDB.A00` وتُسجِّل `HatchMetadataRequestManager/sendRequest timed out method=`.
- العدد الصحيح `138` المُمرَّر إلى `C37393GKy` غير محسوم (غير معروف).
- الناقل هو `ProtocolMessage.aiMetadataOperation` (الحقل 31)، لا رسالة دردشة صِرفة (مُغيَّر).
- تحتوي الحزمة `com.whatsapp.bot.infra.message.aimetadata` أصناف `Ideas*Wire` / `Idea*Wire` (found). علاقتها بأسماء الطرق مستنتجة فقط؛ أسماء الطرق لم تُعدَّد.
- جانب الاستلام الذي يُكمِل `A04` لم يُتعقَّب. مطابقة استجابة بـ`requestId` مستنتجة من خريطة `A04` و`BB2.requestId`.

زعم **لا نطاق XMPP مخصَّص**: لا معالجة `w:ai` / `wa:ai` مرصودة في المسار المُتعقَّب؛ قائم على الغياب، لا مُعاد التحقق منه باستفاضة.

**الإعلان عن القدرة (found، `C33284Eea`):** عندما تكون الوجهة JID Hatch `…697` (`AbstractC34361Xw.A00`) وتنجح بوّابة، يبني العميل `DPJ` (حقل تعداد مُكرَّر واحد `capabilities` = 1، القيم `EnumC32144E2q`) ويُخزِّن `C33473Ehf.A06` ذلك في `BotMetadata.capabilityMetadata` (13) الخاصة بالرسالة الخارجة، إلى جوار `BotMetadata.timezone` (8) = معرّف `TimeZone` الجهاز. القدرات المُضافة لكل بوّابة:

| البوّابة | القدرة (رقم التعداد) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| العلم **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| العلم **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| العلم **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

الأعداد هي المعطى الثاني لباني التعداد؛ كونها تساوي أرقام proto مستنتج. يُسرِد التعداد أيضاً قدرات الاستجابة الغنية (`RICH_RESPONSE_TABLE`، `RICH_RESPONSE_CODE`، `AI_MEMORY`، `PROGRESS_INDICATOR`، ...).

**أمثلة طلب (found، مفاتيح `params` مقروءة عند مواقع الاستدعاء؛ الهدف JID Hatch `…697` إلا إذا استخدم موقع الاستدعاء JID المحادثة):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | مبنية في `HatchIdeasManager$execute$job$1` (المفاتيح غير مقروءة)؛ رد نداء `onPart` مُرفَق |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` مُسلسَل إلى JSON؛ رد نداء `onPart` مُرفَق |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` فقط عندما تكون غير فارغة) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

شكل البايتات في `BB2.data` (شكل مُعثور عليه، قيم مثال):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

تُكتَب `accepts_encoding` فقط عندما يكون `acceptsGzipResponse` الخاص بالمُستدعي صحيحاً؛ `params` فقط عندما تكون غير فارغة. يُسجَّل رد النداء `onPart` في `A03` فقط عندما يُمرِّر المُستدعي واحداً.

**رسالة دردشة للبوت (أجزاء مُعثور عليها):**
- يُعاد تغليف `Message` الخارجة في `Message.botInvokeMessage` (`F2K`، `C33284Eea`)، ويحمل الغلاف `BD2` الرسالة في الحقل 1. في `F2K` يُتجاوَز التغليف (تُضبَط الرسالة مباشرة) عندما يكون `C13S.A00()` خاطئاً، أو `A10` الخاص بالرسالة خاطئ، أو العلم **10646** مُفعَّل (found).
- يُبنى `BotMetadata` بواسطة `C33473Ehf.A0E` / `A0G`. يبحث `A0G` عن سجل الملف الشخصي لـJID البوت الهدف (`C199358dn.A06(userJid)`، سلسلة الشخصية `C199348dm.A0A`)؛ إذا كانت تلك السلسلة فارغة تُعيد الدالة دون كتابة بيانات بوت وصفية، وإلا تضبط `personaId` (2) و، عند وجودها، `suggestedPromptMetadata` (4) ورسائل فرعية إضافية. تُخزَّن سلسلة الشخصية عند إنشاء سجل الملف الشخصي (`C24121Ab2` تبني `<id>$1`؛ `C223219iv` تُثبِّت `1807055946647697$1` لـHatch). ما إذا كان `messageContextInfo` يقع على `Message` الخارجية أو على الرسالة داخل `botInvokeMessage` لم يُحسَم.
- تُضبَط `botMessageInvokerJid` / `isSupportAiMessage` على `WebMessageInfo` بواسطة خطّافات D36 (`C34385EwW`، `C34378EwP`).

---

## 6. بروتوكول الاستجابة

### 6.1 النقل

لم يُعَد التحقق منه كما وُرِد في 2.26.26.4 ("رسائل عادية ببايتات `hatchMetadataSync`"، الصنف `Azz`). مُعثور عليه: `hatchMetadataSync` تعيش في `C25754B9o` داخل `ProtocolMessage.aiMetadataOperation`. يُفترَض أن استجابات Hatch تصل بالطريقة نفسها وتُطابَق بـ`requestId` (مستنتج). طلبات Hatch استدعاءات طرق؛ لم يُظهَر أنها مسار ردود الدردشة العادية.

### 6.2 البث/الأجزاء: غير مدعوم كما ورد وصفه

جدول 2.26.26.4 (`chunkOrder`، `isLastChunk`، `clientStreaming`، `serverStreaming`، `streamingSidecar`) كآلية بث واحدة لـMeta AI غير مدعوم في 2.26.41.6:

| الحقل | أين في 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` الحقل **7** (إشعار مزامنة تاريخ، `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) و`C25838BCy` الحقل **5** (مزامنة تاريخ) |
| `isLastChunk` | `C55285Ou6` الحقل **8** (رسالة بـ`attestationBundles`، `teeModelConfig`، `violationSignal`؛ خاص بـTEE) |
| `streamingSidecar` | الحقل **18** على رسائل الصورة/الفيديو/الصوت (`C30607DTb`، `DTR`، `DTX`، `C30614DTi`) |
| `clientStreaming`، `serverStreaming` | غير مُعثور عليهما كحقلي proto |

لا إعادة تجميع أجزاء لردود Meta AI مُعثور عليها. ما يوجد لـHatch: `GuR(method, onPart)` — رد نداء `onPart` لكل طلب (found)؛ أنه يحمل نتائج جزئية مستنتج من الاسم.

### 6.3 الاستجابة الغنية (الحقل 97)

`richResponseMessage` (`DSY`) = الحقل **97** على `Message`. توجد أصناف عرض: `AiRichResponseFooterView` و`UnifiedResponseActionHandlerFactory` (الحزمة `com.whatsapp.conversationrow.botrichresponse`) (found). الاستشهادات: `WebMessageInfo.supportAiCitations` (72). أنواع المحتوى (الصور، الجداول، الكود) لم تُعَد التحقق منها هنا؛ انظر بحث `richResponseMessage` المنفصل.

### 6.4 مؤشر الكتابة

الصادر (found، `C199098dN.A01`، سجل `HandleMeComposing/handleComposing`): حالة دردشة XMPP قياسية، لا نطاق مخصَّص في الكود المقروء.
- الحالة الصِّرفة (لا بوت مذكور، أو JID بوت مُحلَّل إلى الافتراضي): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- بوت مذكور في الدردشة: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- يُرسَل عبر `C10140Tq.A0X` بنوع IQ عدداً صحيحاً 4.

الوارد (found، معالِج stanza `C40511kx`): `<chatstate>` بعنصر فرعي `composing` (اختياري `media`) يستدعي رد نداء الكتابة العام بـ`from`/`participant`؛ `paused` يستدعي رد نداء التوقف. لا فرع خاص بالبوت مُعثور عليه في هذا المعالِج، فـ`composing` من JID بوت يمر بنفس المسار كأي جهة اتصال (مستنتج؛ لم تُرصَد stanza كتابة بوت من جهة الخادم). `BotMetadata.progressIndicatorMetadata` (12) والقدرة `PROGRESS_INDICATOR` موجودان كآلية تقدُّم منفصلة داخل الرسالة (أسماء فقط، لم تُتعقَّب).

### 6.5 مزامنة ملف تعريف البوت

تُجدوِل `BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) `BotProfileForChatListWorker` في `A03()`: طلب WorkManager موسوم `BotProfileSyncManager` بـ`setBackoffCriteria(policy, 1, MINUTES)` وشرط (قيمة النوع غير محسومة). الدقيقة الواحدة هي **تأخير تصاعدي** لإعادة المحاولة، لا فترة دورية. "كل ~دقيقة واحدة" في 2.26.26.4 غير مدعومة (تغيَّرت). يطلب `A02(groupJid, userJid)` ملفاً شخصياً واحداً (`requestBotProfileResult`). ليست جزءاً من مزامنة القائمة العادية (غير مُغيَّر).

سجل الملف الشخصي `C199348dm`: نوع البوت (`C1XY`)، JID، اسم العرض (`A09`)، الوصف (`A07`)، سلسلة الشخصية (`A0A`)، الصور المصغَّرة، الطابع الزمني.

### 6.6 سلاسل نوع البوت

يُخطِّط `C718732k.A00(String)`: `meta_ai`، `meta_ai_thread`، `tee_meta_ai_group`، `side_chat`، `manus`، `hatch`، `muse`، `third_party`؛ أي شيء آخر يصبح `AnonymousClass399(str)`. هذه تسميات نوع بوت (تُستخدَم أيضاً في مُرشِّحات الواجهة)، لا قيم `BotMetadata.personaId` (found).

---

## 7. التخزين

- `MetaAiMemoryStore`: لا صنف بهذا الاسم في 2.26.41.6. المُكافئ المُعثور عليه جدول `meta_ai_memory` مُنشَأ بصنف مخطط `C23621AHm` (found): `memory_id` TEXT، `memory_content` TEXT، `bot_jid_row_id` INTEGER، فهرس `meta_ai_memory_memory_content_index` على `memory_content`. أي ملف قاعدة بيانات يحمله غير محسوم. ذو صلة (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (واجهة؛ الاسم يقول قديم)، تفضيلات مشترَكة `meta_ai_memory_disclosure_seen` (شاشة تصميم المكالمة الصوتية، `C29434Cpx`)، تعدادات القدرة `AI_MEMORY` 4، `AI_SHARED_MEMORY` 40، `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`)، و`BotMetadata.memoryMetadata` (15).
- مفتاح تفضيلات مشترَكة `"meta_ai_forward_disclosure_seen"`: موجود، منطقي، يُقرأ في `C230589xr.A03` لـ`ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: موجود في `com.whatsapp.metaai.incognito.infra` (found).
- تخزين منفصل لدردشات Meta AI خارج `msgstore.db` (2.26.26.4، لم يُعَد التحقق منه): لا صنف مخزن دردشة مُعثور عليه؛ `meta_ai_memory` يحمل حقائق ذاكرة فقط، فالزعم غير مدعوم ولا مرفوض.

### 7.1 البحث الخاص كنوع خيط دردشة بوت (جديد في 2.26.45.10، found)

أصناف جديدة (`com.whatsapp.privateai.privatesearch`، `com.whatsapp.searchui.search.psisearch`):

| الصنف | الدور |
|-------|------|
| `PrivateSearchSessionManager` | يتعقَّب خيط البحث الخاص النشط/الأحدث الوحيد؛ يرفض استئناف خيط تجاوزه بحث أحدث |
| `PrivateSearchThreadsManager` | يُنشئ خيط بوت من نوع `PRIVATE_SEARCH`؛ يرث `LX/1gu`، نفس أساس `BotThreadsManager` الذي تستخدمه أصلاً `IncognitoAiThreadsManager` (أعلاه) |
| `PsiSearchManager` (مُشوَّش `LX/JjA`) | يملك تدفق إرسال الاستعلام/المتابعة ("echo") |
| `PsiSearchDialogFragment` | واجهة حوار؛ معطى `"kind"` قيمته `"TURN_ON_PRIVATE_PROCESSING"` يُظهر بوّابة الاشتراك في المعالجة الخاصة ضمنياً |
| `PsiSearchUnifiedResponseRenderer` | يعرض رد البوت |

البحث الخاص مُنفَّذ كنوع **خيط دردشة بوت** إضافي، لا بدائية شبكة جديدة. تستدعي `PrivateSearchThreadsManager` باني خيط البوت المشترَك `LX/1gv;->A00(LX/2p4, ...)` بتعداد ذو 5 قيم `LX/2p4`: `UNKNOWN`(0) / `DEFAULT`(1) / `INCOGNITO`(2) / `SIDE_CHAT`(3) / `PRIVATE_SEARCH`(4). تُعيد `PsiSearchManager` التحقق من نوع الخيط مقابل هذا المُميِّز قبل الإرسال، ترفض استعلاماً فارغاً أو خيطاً ليس من نوع `PRIVATE_SEARCH`.

**مسار إرسال الاستعلام (مُعثور عليه).** تبني `PsiSearchManager.onEchoSelected` الرسالة الخارجة عبر نفس أداة إنشاء الرسالة العامة التي تستخدمها إرسالات دردشة أخرى، `LX/D1D;->A05(...)`، ثم تُوزِّع النتيجة عبر قائمة انتظار الرسائل الخارجة العادية (`LX/JjA;->A0H:LX/0JB;->D2A`). لا يظهر أي استدعاء GraphQL/MEX/IQ في أي مكان من هذا المسار — إنها آلية `botInvokeMessage` (الحقل 67) ذاتها المُغلِّفة لـJID البوت الموثَّقة في §11 ("رسالة دردشة للبوت")، مُعاد استخدامها حرفياً ولا تُستنتَج من جديد هنا.

**ما يبقى أصلياً (إشارة متقاطعة).** خط أنابيب الاستخلاص PSI/TEE الذي يُجيب فعلياً عن الاستعلام — `TeeClientToolOrchestrator`، `PsiSearchToolHandler` (أداة عميل `wa_search`)، `IplsdHandshakeExecutor`، مدعوماً بـ`libpsi.so`/`libxplat_psi.so` الأصليَّين — غير مُغيَّر عن 2.26.41.6 وموثَّق في بحث Labyrinth/TEE الخاص بالبرين (لا يُستنتَج من جديد هنا)؛ لا شيء منه تلمسه الأصناف الخمسة أعلاه، التي تبني فقط الرسالة الخارجة وتعرض الرد.

**الحكم على إمكانية الوصول: إرسال قابل للوصول، قيمة غير قابلة للوصول.** إرسال بدء البحث قابل للوصول من عميل طرف ثالث بالضبط بنفس معنى دردشة Meta AI أصلاً (§8، §11) — لا شيء جديد يجب هزيمته. ما ليس قابلاً للوصول هو القيمة الفعلية الحافظة للخصوصية للميزة: البحث PSI على الجهاز في قاعدة بيانات الدردشة المحلية ورحلة الذهاب والعودة عبر الحاوية الموثَّقة أصليان، ولا تحمل `Message` الخارجة أي مادة PSI محسوبة مسبقاً. عميل طرف ثالث يرسل نصاً صِرفاً إلى JID بوت البحث الخاص سيحصل على ما يفعله البوت من جهة الخادم باستعلام نص صِرف بلا PSI، لا دلالات البحث الخاص الحقيقية لـWhatsApp (غير معروف، لم يُؤكَّد بأي اتجاه).

### 7.2 إيقاف التوليد انتقل خارج مسار رسالة السلك (جديد في 2.26.45.10)

سلسلة خطأ `promptMessageKey` (موجودة منذ 2.26.35.8، مرتبطة بـ`FMessageStopGeneration` / `ProtocolMessage.extraJson_`، النوع 26) لها **صفر نتائج** عبر كل ملفات DEX الأربعة عشر في 2.26.45.10 (found، فحص سلسلة شامل). لا يزال الحقل الأساسي `extraJson_` مُعلَناً على `LX/DHC;` (صنف مستضيف `ProtocolMessage`) لكن لا يُشار إليه إلا داخل إعلان حقل الصنف نفسه ومصفوفة الانعكاس (reflection) — لا جالب (getter)، لا صنف آخر في التطبيق يقرأه (found). جرّد D8 معلومات التنقيح بالكامل في هذا البناء (صفر أسماء ملفات `DBG_SET_FILE` قابلة للاستعادة عبر 34,255 طريقة في `classes6.dex`)، فالصنف المُشوَّش الذي كان يدعم `FMessageStopGeneration` لا يمكن تحديده من البيانات الوصفية للتنقيح؛ تنجو سلاسل أسماء ملفات `.kt` الثلاث الخاصة به فقط كإدخالات حوض سلاسل منفردة، لا كود قابل للوصول (found).

مُعثور عليه بدلاً من ذلك: صنف جديد **غير مُشوَّش** `com/meta/metaai/stopgeneration/data/StopGenerationRepository` تُشغِّل دالته `A00(threadIdentifier, messageIdentifier, messageIdString, surface, mode, Continuation)` طفرة Pando GraphQL `MetaAIStopGenerationMutation` (عملية `xfb_genai_stop_generation`)، بحقول `thread_identifier`، `message_identifier`، `message_id_string`، `surface`، `mode`، مُحقَّقة بفحوصات فراغ عامة غير مُفهرَسة بسلسلة (`LX/00m;->A09`) — لا نص خطأ بنمط `promptMessageKey`.

أفضل تفسير (**مستنتج**، غير مُثبَت): انتقل إيقاف التوليد إلى هذه الطفرة GraphQL لهذا السطح، بدلاً من إعادة تسمية فحص رسالة السلك القديم في مكانه. ما إذا كان مسار `protocolMessage`/النوع-26/`extraJson_` القديم كوداً ميتاً الآن، أو محفوظاً لتوافق العملاء الأقدم، أو لا يزال قابلاً للوصول من مُستدعٍ غير مُتعقَّب، **غير معروف** — لم يُعثر على مُستدعٍ في هذا البناء، لكن فحص ساكن لـDEX واحد لا يمكنه إثبات الإزالة.

---

## 8. لماذا لا يحصل Baileys على استجابة

كل الصفوف **مستنتجة**: مقارنة ساكنة لمتطلبات العميل مع مسار إرسال طرف ثالث؛ لا اختبار حي.

| المشكلة | الأساس في 2.26.41.6 | المستوى |
|-------|--------------------|------|
| نوع JID هدف خاطئ | JIDs البوت تستخدم الخادم `bot` (`C24770wv`)، لا `s.whatsapp.net`؛ بوتات رقم الهاتف تُخطَّط عبر جدول PN←FBID | found (صنف JID)، inferred (الأثر) |
| `$1` على JID التوجيه | غير موجودة. `$1` على سلسلة معرّف الشخصية | found |
| غلاف `botInvokeMessage` غائب | يُغلِّف العميل `Message` الخارجة في الحقل 67 (`F2K`) | found، المتطلب مستنتج |
| `messageContextInfo.botMetadata` غائب | يكتب العميل `personaId`، `invokerJid`، إلخ فيه | found، المتطلب مستنتج |
| `personaId = "meta_ai"` | ليس ما يرسله العميل؛ يرسل سلسلة شخصية الملف الشخصي (مثل `1807055946647697$1`) | found |
| `aiConversationContext` غائبة | الحقل 20 من `BotMetadata`؛ السلوك عند أول دور غير معروف | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | حقلا WebMessageInfo تُضبطان بخطّافات العميل؛ متطلب الخادم غير معروف | unknown |
| `botTargetId` | لا كاتب في كود العميل | found |
| الرد لا يُحلَّل | `richResponseMessage` هو الحقل 97 في `Message` | found |
| إعادة تجميع الأجزاء | غير مدعومة بدليل 2.26.41.6 (انظر 6.2) | found |

---

## 9. التحقق من توقيع البوت (أصالة المحتوى)

منفصل عن كل ما سبق: آلية تتيح للعميل **المستقبل** التحقق من أن محتوى `richResponseMessage` جاء حقاً من الخلفية التابعة لذكاء Meta الاصطناعي، بصرف النظر عن من رحَّل الرسالة. النتائج الساكنة أدناه `found` في كود 2.26.41.6؛ نتيجة إعادة التشغيل في 9.4 هي `tested` (حية، على حساب المُؤلِّف نفسه — لا اعتراض حركة، عميل مشروع يُنشئ ويُرحِّل رسالته هو نفسه).

### 9.1 موقع البروتو

`BotMetadata.verificationMetadata` — الحقل **27** (`messageContextInfo` (35) ← `botMetadata` (7) ← `verificationMetadata` (27))، النوع `DPC`/`BotSignatureVerificationMetadata` (يكشف `toString` الاسم الحقيقي): `proofs[]`، كل منها `BotSignatureVerificationUseCaseProof` بـ`version` (int)، `useCase` (تعداد `WA_BOT_MSG` / `WA_TEE_BOT_MSG`)، `signature` (bytes)، `certificateChain` (بايتات مُكرَّرة، DER X.509).

### 9.2 خوارزمية التحقق

الصنف `C33259EeB`، الاسم الداخلي `BotSignatureVerificationUtils` (من سلاسل السجل):

1. **تحقق سلسلة الشهادات** من `certificateChain` مقابل مرساة ثقة، عبر `HFg.A01(date, certs, true)`.
2. **بناء البايتات المُوقَّعة**: `"1" + <phone-number string> + <unifiedResponse bytes>` — يربط التوقيع **المحتوى ورقم الهاتف معاً**، لا المحتوى وحده.
3. **تحقق EdDSA** (سجل: `"EdDSA signature verification result"`) باستخدام مفتاح Ed25519 الخام المُستخرَج من SubjectPublicKeyInfo الخاص بشهادة الورقة (leaf).
4. **وضع الإنفاذ**، يُقرأ من الإعداد **19590**، تعداد `EnumC32057Dzg`: `NONE` (`"none"`، مُعطَّل، يمر دائماً)، `LOG_ONLY` (`"log_only"`، يحقق + يسجِّل، لا يحجب أبداً)، `ENFORCE_BLOCKING` (`"enforce_blocking"`، فحص فاشل يُعيد `false`). النتيجة تُخزَّن كـ`E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`، تُحفَظ في عمود SQLite `bot_message_info.signature_validation_status` (الجدول يحمل أيضاً `bot_client_public_key`).

### 9.3 بوّابة عرض الصف

`C30085D6v.A00` (موزِّع نوع الصف) و`EOK`/`C32608EKo`: إذا كانت حالة التوقيع `FAILED` والعلم **27635** مُفعَّل ← صف مُقنَّع `ConversationRowAiUnknownSenderMasked` ("فشل التحقق من التوقيع"). بشكل مستقل، إذا لم يكن JID المُرسِل موجوداً في مخزن ملف البوت المُزامَن محلياً (`C224899mg`، نفس مزامنة `BotProfileSyncManagerImpl`) والعلم **27355** مُفعَّل ← `ConversationRowAiUnknownSenderPreview` ("مُرسِل غير معروف بمحتوى بلا موافقة")، معاينة مضبوطة بموافقة لا حجب صلب.

### 9.4 التقاط حقيقي وإعادة تشغيل حية (tested)

رد حقيقي من Meta AI، مُلتقَط من جانب العميل في محادثة حقيقية (حساب المُؤلِّف الخاص، فُكَّ تشفيره بعميل المُؤلِّف نفسه — لا اعتراض حركة)، حمل:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`، `useCase: "WA_BOT_MSG"`، `signature` بطول 64 بايت (حجم Ed25519)، `certificateChain` بإدخالين.
- شهادة الورقة: `CN=svc:wa-bot-msg-leaf`، مفتاح Ed25519، صادرة عن `Meta WA SS Int CA 2025-09`، تتسلسل إلى `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`)، صلاحية ≈7 أشهر (شهادة خدمة تتجدد تلقائياً) — مفتاح التوقيع الخاص موجود فقط في خلفية Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — اسم خلفية بوت لم يُوثَّق سابقاً (انظر أيضاً "Hatch" في الأقسام 1-6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`، حقل شقيق لـ`botMetadata`.
- شكل التسليم: `protocolMessage` بـ`type: MESSAGE_EDIT`، `editedMessage.richResponseMessage` (الرد الأول في خيط يصل مُغلَّفاً مسبقاً كتحرير لعنصر نائب)، `key.remoteJid` = JID المُؤلِّف نفسه.

**الاختبار:** `richResponseMessage` + `messageContextInfo.botMetadata` نفسهما بالضبط (التوقيع وسلسلة الشهادات غير مُغيَّرين بايتياً) رُحِّلا عبر `relayMessage` من جهاز المُؤلِّف نفسه — لا JID البوت `867051314767696@bot` — إلى رقم المُؤلِّف نفسه (نفس الرقم المُضمَّن أصلاً في البايتات المُوقَّعة).

**النتيجة:** عُرض المحتوى بتنسيق "الذكاء الاصطناعي" الكامل والنص الحقيقي، موسوماً "Forwarded". بعض تسليمات الحمولة المطابقة عرضت بدلاً من ذلك "WhatsApp can't verify the security of this media. Only download if you trust the sender." بإجراء تنزيل؛ النقر على تنزيل كشف المحتوى نفسه، مُطابِقاً حالة `DOWNLOAD_CONSENT_ACCEPTED` ومسار الكود "مُرسِل غير معروف بمحتوى بلا موافقة" في 9.3. عرض تسليم واحد احتياطي عام "your version of WhatsApp doesn't support it" بدلاً من ذلك؛ السبب غير مُحدَّد (غير معروف).

**الخلاصة (tested):** الفحص التشفيري في 9.2 يرتبط بـ*(المحتوى، رقم الهاتف)*، لا بهوية المُرسِل الحي أو JID الخاص به. يمكن إعادة تشغيل `richResponseMessage` موقَّعة بصلاحية من مُرسِل ليس بوتاً وتظل تنجح في التحقق من التوقيع، ما دام رقم المستقبل يطابق الرقم المُضمَّن في التوقيع — يعرضه العميل المستقبل كمحتوى ذكاء اصطناعي حقيقي (محجوباً على الأكثر بخطوة موافقة تجميلية بنقرة واحدة "مُرسِل غير معروف"، لا حجب صلب). هذه آلية أصالة محتوى، لا آلية أصالة مُرسِل؛ تشفير طبقة Signal الخاص بـWhatsApp نفسه، لا هذا التوقيع، هو ما يُوثِّق هوية المُرسِل الحي.

### 9.5 فحص قائمة إلغاء الشهادات (CRL) (جديد في 2.26.45.10، found)

اكتسبت خطوة تحقق السلسلة في 9.2 (الخطوة 1، "تحقق سلسلة الشهادات... عبر `HFg.A01`") فحص CRL مقابل شهادتي الورقة والوسيطة في `certificateChain` كليهما، قبل فحص توقيع Ed25519 على (الهاتف، المحتوى) (9.2 الخطوة 3). الأصناف: `BotPkiCrlGraphQLFetcher`/`BotPkiCrlManager` (`com/whatsapp/bot/infra/message/signature/`)، تُستدعى من صنف تحقق السلسلة في 2.26.45.10 `BotSignatureVerificationCertificateManager` (`LX/HEe` — الخليفة المُعاد تسميته لـ`BotSignatureVerificationUtils`/`C33259EeB` من 9.2؛ نفس الصنف، مؤكَّد بسلاسل سجل مشترَكة `"Certificate chain validation successful"`/`"Parsed <n> certificates from chain"`).

- **عملية GraphQL**: `FetchBotPKICRL` على `whatsapp-android-mex` — حقل الطلب `crl_name`، الاستجابة `xwa2FetchFeaturePkiCrl` تحمل CRL كـblob بايتات DER خام (لا قائمة تسلسل مُلغى مُحلَّلة مسبقاً) إضافة إلى طوابع زمنية `fetchedAt`/`nextUpdate` وعدد إدخالات مُلغاة.
- **قائمتا CRL قيد الاستخدام**، بالاسم: `whatsapp_simple_signal` لشهادة **الورقة**، `whatsapp_feature` للشهادة **الوسيطة** (سلاسل سجل `"...Leaf certificate CRL validation passed"` / `"...is revoked"` / `"...CRL unavailable..."`، نفس الزوج لـ"Intermediate").
- **مرساة الثقة**: شهادة جذر عمرها 40 سنة مُثبَّتة كسلسلة PEM حرفية داخل `LX/HEe` — `CN=Meta WA Feature Root CA`، `O=Meta Platforms Inc.`، مفتاح EC، صالحة من 2025-09-04 إلى 2065-09-04. تُفحَص توقيع كل CRL مُستخرَجة بنفسها مقابل المفتاح العام للمُصدِر المعني (`X509CRL.verify(...)`) قبل الوثوق بقائمتها المُلغاة — إلا `whatsapp_simple_signal`، المعامَلة بشكل خاص لتجاوز خطوة التحقق الذاتي هذه (السبب `مستنتج`، غير محسوم).
- **التخزين المؤقت/التحديث**: تخزين مؤقت `SharedPreferences` لكل `crlName` (`crl-data`/`crl-fetched-at`/`crl-next-update`)، يُجلَب مسبقاً مرة واحدة عند بدء التطبيق بعد تسجيل المستخدم وجهوزية قاعدة البيانات (سجل: `"BotPkiCrlManager/...starting CRL prefetch"`)، يُحدَّث بمؤقت مرتبط بـ`nextUpdate` الخاصة بـCRL نفسها (بحد أدنى 60 ثانية)، ويُجلَب عند الطلب بنافذة تأخير تصاعدي إذا كان التخزين المؤقت غائباً/قديماً عند تشغيل فحص.
- **الأثر**: شهادة ورقة أو وسيطة مُلغاة تفشل في تحقق السلسلة بنفس طريقة شهادة منتهية أصلاً — يُغذِّي هذا حالة `E05` الموجودة (`FAILED`) وبوّابة `ENFORCE_BLOCKING`/`LOG_ONLY`/`NONE` من 9.2 الخطوة 4، لا مسار إنفاذ جديد مستقل.
- **المستوى**: found — العملية، النطاق، كلا اسمي crlName، آليات التخزين المؤقت/التحديث، مواقع الاستدعاء، شهادة الجذر المُثبَّتة. مستنتج — تخطيط بايتات الإدخال المُلغى الدقيق (التسلسل مقابل بايتات الشهادة الكاملة) وسبب تجاوز `whatsapp_simple_signal` التحقق الذاتي من CRL. كل تحليل ساكن؛ لم تُرصَد شهادة مُلغاة عملياً.
- **سطح العميل/Baileys**: `FetchBotPKICRL` عملية MEX مُسمّاة وملموسة قابلة للوصول بنفس طريقة عمليات `whatsapp-android-mex` الأخرى، لكنها تُغذِّي فقط قرارات ثقة من جانب العميل حول شهادات رسائل البوت — لا أثر لها على ما يستطيع مُرسِل غير عميل ترحيله (نتيجة إعادة التشغيل في 9.4 غير مُتأثِّرة: الإلغاء يُغيِّر النتائج فقط لشهادة مُلغاة فعلياً، وهذا لا يحدث أبداً هنا).

---

## 10. حل Baileys

لا يُزعَم تنفيذ عامل. ما يلي مخطط بنيوي لأين تعيش الحقول وفق 2.26.41.6، موسوم **inferred**؛ لم يُشغَّل مقابل خادم.

### 9.1 الهدف

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

ما إذا كانت سلسلة خادم `bot` تعمل كهدف ترحيل لـBaileys، وكيف يستخلص الخادم `to` النهائي لـstanza، غير معروف.

### 9.2 موضع الحقل (الشكل فقط)

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

- تضمين `botMetadata` في `messageContextInfo` (الحقل 7) **مُعثور عليه**. تُكتَب `capabilityMetadata` (13) و`timezone` (8) من جانب العميل فقط لوجهات Hatch (found)؛ متطلبهما من جهة الخادم غير معروف. ما إذا كان بروتو `baron-baileys-v2` يحمل هذه الحقول أصلاً لم يُفحَص؛ إذا لم يكن، يجب توسيع البروتو (مستنتج).
- `isSupportAiMessage` (70) و`botMessageInvokerJid` (58) حقلا `WebMessageInfo`. ما إذا كان يجب حضورهما على السلك غير معروف؛ لا تضعهما في `contextInfo` (ذلك كان خاطئاً في تقرير 2.26.26.4).
- `botTargetId`: لا كاتب للعميل في أي مكان من الكود المفكَّك (found)؛ لا تضبطه.
- التغليف الدقيق (`botInvokeMessage.message` يحمل الرسالة الحقيقية مقابل بجوارها) يتبع إعادة التغليف في `F2K` / `C33284Eea`؛ النتيجة المُسلسَلة الدقيقة لم تُستنسَخ (غير معروف).

### 9.3 معالجة الاستجابة

- الردود الغنية: `Message.richResponseMessage` هو الحقل **97** (found). حلِّل ذلك، لا الحقل 77.
- إزالة معالجة الأجزاء: `chunkOrder` / `isLastChunk` ليسا حقلي بث خاصين بـMeta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) الخاصة بـHatch هي قناة طلب JSON؛ لم يُظهَر أن ردود الدردشة العادية تستخدمها.

### 9.4 سياق المحادثة

`BotMetadata.aiConversationContext` (20) موجودة. أن الخادم يُعيد حالة محدَّثة في الردود وأنها يجب أن تُعاد ضمن الصدى هو **مستنتج** (من اسم الحقل وتقرير 2.26.26.4)؛ غير مؤكَّد.

---

## 11. التدفقات

### 10.1 رسالة دردشة للبوت (مُعثور عليه من جانب العميل، مستنتج من جانب الخادم)

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

### 10.2 طلب بيانات Hatch الوصفية (مُعثور عليه من جانب العميل)

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

## 12. التغييرات مقابل 2.26.26.4

| العنصر | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | قديم، العلم 25119 | غير موجود. 25119 فقط في جداول الأعلام، لا قارئ |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697، 698 خادم `bot` (`C24770wv`)؛ 165332417282214 خادم `lid` (`C14080dr`) |
| ثوابت JID جديدة | لا شيء مُدرَج | `1807055946647699` (غلاف بوت CoEx v2 / هدف مجموعة أجهزة)، `2942131436135992` (JID الملف الافتراضي لـMeta AI، فحص JID البوت `A07`)، `867051314767696555` (العضو الثاني في `A07`، الغرض غير معروف)، `17015557208` (PN الخاص بـMeta AI، `A04`) |
| بادئة `$1` | على JID التوجيه، `C1A2.A00/A01` | ليست على JID؛ تُلحَق بسلسلة معرّف الشخصية (`C24121Ab2`، `C223219iv`) |
| تحويل التوجيه | إلحاق `$1` | `AbstractC24760wu.A01`: LID `165332417282214` ← بوت `…698`، PN ← بوت عبر جدول FBID |
| أسماء الأعلام 25119/26189/27083 | أسماء أعلام `ai_*` | السلاسل إدخالات قائمة ميزات (`C25056AqU`)؛ 26190 = JSON ملف Hatch؛ 37227/37852/37054 تضبط قيم قدرة Hatch 76 / 77 / 79 |
| `richResponseMessage` | الحقل 77 | الحقل 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 على "WebMessageInfo" | 67 / 100 / 104 على `Message`؛ أيضاً 131، 137 |
| `botMessageInvokerJid`، `isSupportAiMessage`، `supportAiCitations`، `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73؛ `botTargetId` لا تُكتَب أبداً |
| موقع BotMetadata | "مُضمَّن في الرسالة" | `Message.messageContextInfo` (35) ← `botMetadata` (7) |
| `personaId` | `"meta_ai"` | سلسلة شخصية الملف الشخصي، مثل `1807055946647697$1`؛ `meta_ai` تسمية نوع بوت |
| أنواع الإضافة | 8، 9، 15 | نفسها، التعداد يحمل 18 قيمة (حتى 17) |
| تعداد الإجراء | تعداد قيمة 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| غلاف JSON لـHatch | `method`، `params` على المستوى الأعلى | متداخلان تحت `payload`؛ تُضاف `accepts_encoding` |
| ناقل Hatch | رسالة قياسية، الصنف `Azz` | `ProtocolMessage.aiMetadataOperation` (31) ← `C25754B9o`؛ تُضاف `bizAiMetadataSync` (2) |
| التحقق من توقيع البوت | غير موثَّق | جديد: `BotMetadata.verificationMetadata` (27)، EdDSA + سلسلة شهادة X.509 على (المحتوى، رقم الهاتف)؛ مُختبَر حياً، يرتبط برقم الهاتف لا بالمُرسِل الحي (القسم 9) |
| خرائط معلَّقة | واحدة (`A02`) | اثنتان: استمراريات `A04`، ردود نداء جزء `A03` من نوع `GuR` |
| حقول البث | جدول أجزاء واحد لـMeta AI | `chunkOrder` (مزامنة تاريخ)، `isLastChunk` (رسالة TEE)، `streamingSidecar` (وسائط)؛ `clientStreaming`/`serverStreaming` غير مُعثور عليهما |
| فترة مزامنة الملف الشخصي | "كل ~دقيقة واحدة" | الدقيقة الواحدة تأخير تصاعدي لـWorkManager، لا فترة دورية |
| `MetaAiMemoryStore` | موجود | غير مُعثور عليه بالاسم؛ جدول `meta_ai_memory` (`C23621AHm`: `memory_id`، `memory_content`، `bot_jid_row_id`) مُعثور عليه |
| `MetaAiIncognitoSessionManager`، `meta_ai_forward_disclosure_seen`، `AiRichResponseFooterView`، `UnifiedResponseActionHandlerFactory`، `BotProfileSyncManagerImpl`، `BotProfileForChatListWorker` | موجودة | موجودة |
| مؤشر الكتابة (chatstates) | مُعثور عليه | مُعثور عليه: صادر `<chatstate><composing/></chatstate>`، مع `<bot jid/>` عند ذكر بوت (`C199098dN.A01`)؛ وارد `composing`/`paused` عبر معالِج عام `C40511kx`، لا فرع خاص بالبوت |
| الإعلان عن القدرة | غير موثَّق | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) لـHatch؛ الأعلام 37227 / 37852 / 37054 تُخطَّط إلى قيم تعداد 76 / 77 / 79 |
| أمثلة طلب Hatch | غير موثَّقة | `ideas.detail`، `ideas.execute`، `ideas.complete_all`، `channel.bootstrap`، `hitl.approval.decide`، `hitl.payment.select` |
