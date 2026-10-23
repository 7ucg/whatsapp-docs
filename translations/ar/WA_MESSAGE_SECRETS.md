<!-- src-sha1: 7a4b50013c0f196c95c57808469516becf9a34b7 -->
# WhatsApp أسرار الرسائل — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** `messageSecret` الخاص بكل رسالة (التوليد، `MessageContextInfo`، التخزين المحلي، مزامنة السجل)، اشتقاق المفاتيح حسب حالة الاستخدام (HKDF)، IV / AAD في AES-GCM، الإضافات المشفرة (`encReactionMessage`، `pollUpdateMessage`، `encEventResponseMessage`، `encCommentMessage`، تعديلات `secretEncryptedMessage`)، ربط هوية المرسل / الهدف وإعادة المحاولة بين LID / PN، الرسائل اليتيمة وبدائل غياب السر، امتدادات stanza الخاصة بـ `<message>` (السمات، سمات `<enc>`، `<meta>`، `<biz>`، `<bot>`، `<hsm>`، `<reporting>`، `<cap>`، الحشو، فحص دعم الجهاز المرافق)، أعلام الميزات، المقارنة مع Baileys

---

## 1. ما هو (تقنيًا)

كل رسالة يمكن أن تتلقى لاحقًا متابعة مشفرة تحمل سرًا عشوائيًا بطول 32 بايت داخل حمولتها المشفرة من طرف إلى طرف (`MessageContextInfo.messageSecret`). تُشفَّر المتابعة (تفاعل، تصويت، رد على حدث، تعليق، تعديل) بمفتاح مشتق من هذا السر ومن معرّف الرسالة الأصلية والمرسل الأصلي والمعدِّل. يمرر الخادم المتابعة كرسالة E2E عادية، لكنه لا يستطيع قراءتها ولا نقلها إلى هدف أو مستخدم أو حالة استخدام أخرى دون كسر مصادقة GCM. كل العبارات مبنية على التحليل الساكن لـ APK المفكوك؛ لم يُلتقط شيء على الشبكة. المستويات: **found** = مقروء في الكود، **inferred** = مستنتج من الكود، **unknown** = غير محلول. أُعيد حل الأسماء المبهمة في 2.26.41.6 انطلاقًا من سلاسل ثابتة (`MessageSecretCryptoHelper/`، `MessageEncUtils/`، سلاسل حالات الاستخدام، `FMessage*Protobuf/`، `SecretEncryptedMessagePreProcessor/`، `CompanionSupportVerifier/`).

يعرّف الإصدار نفسه أيضًا امتدادات stanza الخاصة بـ `<message>` (من القسم 10 فصاعدًا): سمات وعُقد فرعية تصنّف الرسالة وتوجّهها دون أن تحمل محتواها. جُمعت هنا لأن `<meta polltype>` / `<meta event_type>` يجب أن يتوافقا مع الحمولة المشفرة بالسر (7.4).

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| مساعد التشفير (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` تشفير، `A04` فك تشفير (إعادة محاولة الهوية)، `A02` حل مفتاح الهدف |
| حاملات معاملات التشفير / فك التشفير | `C32833ETl` / `C32854EUg` | البيانات، المرسل، مفتاح الهدف، حالة الاستخدام / IV، الحمولة، المفاتيح، المرسل |
| اشتقاق المفتاح | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256، salt صفري |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`، `AbstractC32243E6m.A00` (`MessageEncUtils`) | native، وسم 16 بايت |
| مزوّدو AAD | `FXU`: `C34633F1g` (Poll Vote)، `C34632F1f` (Event Response)، `C34634F1h` (WASA)، `C34631F1e` (لا شيء) | بيانات إضافية |
| مولّد السر | `AbstractC33322EfC.A01` | `SecureRandom`، 32 بايت |
| مخزن السر (`MessageSecretStore`) / الإضافة في الذاكرة | `C35311ad` (الجدول `message_secret`) / `C35171aP` على الرسالة `C13G` | الحفظ والحمل |
| مُعيِّن المفتاح الأصلي (`ReferentialKeyUtil`) | `C43661qB.A03` | مفتاح الرسالة الأصلية غير المعدّلة |
| معالجات التفاعلات | `DU8` (إرسال)، فرع `F2P` (استقبال) | `reactionMessage` / `encReactionMessage` |
| تصويت الاستطلاع / رد الحدث / تعليق | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| التعديلات المشفرة بالسر (`SecretEncryptedMessagePreProcessor`) | `F3Y`، enum `E2Q` | `secretEncryptedMessage` |
| إنشاء الاستطلاع / الحدث (يُؤخذ السر عند الاستقبال) | `F2N` / `F2M` | يقرأ `messageSecret` إلى FMessage |
| Proto: السياق / الرسالة / المفتاح | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| مُختار `type` الخاص بـ stanza | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| المساهمون في stanza الصادر | `InterfaceC35538FaZ`: `F6K` (meta)، `F6M` (bot)، أعلام `F68`، `F69` cap، `F6H` الحشو، `F6L` / `F6C` reporting، `F6G` cstoken، `F6I` tctoken، `F6B` device-identity، `F6X` hsm | بناء أبناء `<message>` |
| مجمّع `<meta>` | `EZV` (السمات `A01`، الأبناء `A00`) | عقدة `<meta>` واحدة |
| باني سمات `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| فحص دعم الجهاز المرافق | `C34757F6a` + `AbstractC32927EXc` | قائمة سماح للأنواع والأبناء |
| محلّلات المواصفات الواردة | `C33474Ehg` (status / عادي)، `C23206A1f` (newsletter)، `C34747F5q` (bot)، `C34748F5r` (biz) | استخراج السمات والأبناء |
| حدث خطأ WAM | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. السر الخاص بكل رسالة

### 2.1 مكانه (found)

`MessageContextInfo` (`C30624DTs`) هو الحقل **35** في `Message` (`C30628DTw`). الحقول ذات الصلة هنا:

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | تلميح قائمة الأجهزة (لا علاقة له بالسر) |
| `messageSecret` | **3** | bytes (32) | السر الخاص بكل رسالة |
| `paddingBytes` | **4** | bytes | حشو |
| `messageAddOnDurationInSecs` | **5** | uint32 | مدة بقاء الإضافة (التثبيت: يجب أن تكون 0 لإلغاء التثبيت) |
| `botMessageSecret` | **6** | bytes (32) | نسخة البوت من السر |
| `botMetadata` | **7** | message | سياق البوت |
| `reportingTokenVersion` | **8** | uint32 | إصدار reporting token لهذه الرسالة |
| `messageAddOnExpiryType` | **9** | enum | انتهاء صلاحية الإضافة |
| `messageAssociation` | **10** | message | الارتباط |

حامل مزامنة السجل `WebMessageInfo` (`C30626DTu`) له حقل `messageSecret` خاص به رقمه **49** (found)، يُستخدم عند تصدير الرسائل إلى جهاز مرافق جديد (القسم 2.4).

### 2.2 التوليد (found، الشروط مستنتجة جزئيًا)

السر هو `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). يُرفق قبل تسلسل الرسالة:

| المكان | الشرط |
|-------|-----------|
| `C33166Ecf.A06` (تحضير الإرسال) | الرسالة بلا سر وتحقق واحد على الأقل مما يلي: فئة الاستطلاع `C13J`؛ `EZN.A01(msg)` (فئة bot / add-on، مع أعلام نوع الدردشة **2200**، **11104**، **19303**)؛ بوابات فئة الدردشة: مجموعة مع العلم **3143**، قائمة بث مع **3144**، status مع **3145**، بوابة الفئة **3146**؛ `C35201aS.A00` (العلم **3142**، دردشة ذاتية / bot)؛ رسالة الحدث `C213509Ao` |
| `AJ0` (معالج الإرسال) | إصدار reporting-token `C35241aW.A05()` (AB int **8860**، محدود بـ `AbstractC35301ac.A00`) غير صفري وفئة الرسالة غير مستثناة بواسطة `C35241aW.A02` (status، newsletter، فئات add-on مختارة) |
| `C72h`، `C34455Exe`، `EPA` | كائنات status (`AbstractC34478Ey1.A0R`) تحصل على سر جديد عند الإنشاء |
| `C33437Eh4` | رسالة bot "request welcome"، فقط عندما يطلب المستدعي ذلك |
| `C9mW` | نوع الرسالة 117، العلم **24741**، عند غياب السر |

لم تُحل بالكامل المسندات خلف `EZN.A01` و`C35201aS.A00` وبوابات `3142`..`3146`؛ القائمة أعلاه تذكر ما يفحصه الكود، لا أي الرسائل المرئية للمستخدم تؤهَّل. الرسائل التي بلا سر لا يمكنها استقبال إضافات مشفرة من هذا العميل (القسم 9).

### 2.3 التخزين المحلي (found)

يكتب `C35311ad` الجدول `message_secret(message_row_id, message_secret)` بدلالات الاستبدال (`MessageSecretStore/insertMessageSecret`) ويقرأ آخر صف لـ `message_row_id`. تحتفظ FMessage به كإضافة `C35171aP` (`A0L` ضبط، `A0c` جلب، `A0Q` = غير فارغ). معالجان في `AbstractC17240jU` (`C35161aO` وآخر مجهول) يكتبانه عندما تكون الإضافة متسخة وتكون الدردشة مؤهلة.

### 2.4 التحقق عند الاستقبال والنقل (found)

| الخطوة | السلوك |
|------|-----------|
| مدقق proto `C33475Ehh.A0V` | يجب أن يكون `message_secret` بطول **32** بايت بالضبط، رمز الخطأ **67**؛ نسخة البوت (`bot_message_secret`، المجموعة `whatsapp_security`) تُدقَّق بالطريقة نفسها |
| إنشاء الاستطلاع `F2N` | ينسخ `messageSecret_` إلى FMessage الجديدة (`A0L`) |
| إجابات أسئلة status `C34838F9e` | النسخ نفسه لـ `statusQuestionAnswerMessage` |
| تصدير مزامنة السجل `C34388EwZ.A00` | يكتب السر المخزن في `WebMessageInfo.messageSecret` (49) |
| استيراد مزامنة السجل `C34388EwZ.C59` | ينسخه عائدًا (`A0L`) |
| التعليقات `C34387EwY` | يعيد بناء `MessageContextInfo` من `WebMessageInfo.messageSecret` لسلسلة التعليقات |

يسجّل `wam_message_secret_errors` (`DZ7`، `C273212s.A00`) القيمة `message_secret_error` **0** = مفقود (يُعيَّن إلى رمز الخطأ 66) أو **1** = طول غير صالح (67) للرسائل التي تتطلب سرًا (`AbstractC33322EfC.A00`: لها العلم وليست من الفئة `C35281aa`).

---

## 3. اشتقاق المفتاح حسب حالة الاستخدام

### 3.1 الصيغة (found، `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = extract مع salt صفري بطول 32 بايت (`AbstractC38971i1.A00(ikm, salt)`)، ثم حلقة expand وفق RFC 5869. أساسيات HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) القسم 5.1. يُستخدم الناتج بطول 32 بايت كمفتاح AES-256 (مستنتج من الطول؛ الاستدعاء native يأخذ المفتاح كـ `byte[]`).

المدخلات:

| المدخل | المصدر | ملاحظات |
|-------|--------|-------|
| `originalMessageId` | معرّف مفتاح الهدف بعد `ReferentialKeyUtil` (`C43661qB.A03`) عند التشفير؛ معرّف المفتاح من proto `targetMessageKey` عند فك التشفير | بالنسبة لهدف معدَّل هذا هو معرّف الرسالة **الأصلية** (سجل `getOriginalKey`) |
| `targetSender` | مؤلف الرسالة الأصلية: المرسل المخزن (`C12300aw.A01`) | `UserJid`، أي بلا لاحقة جهاز (على مستوى النوع؛ الصيغة النصية `user@server` مستنتجة) |
| `modifier` | مؤلف الإضافة: JID حسابه (`C09A.A0G`، وهو LID، يعيده `CUC()` / `Ash()`) عند الإرسال، وJID مرسل الظرف عند الاستقبال | |
| `useCase` | سلسلة من 3.2 | لا فاصل بين المكونات الأربعة |

JID الخاص هو JID حساب LID (`C14080dr`، الخادم `lid`، فحص "Invalid LID"). كل من `AnonymousClass091.Ash()` و`CUC()` يعيد الحقل نفسه.

### 3.2 سلاسل حالات الاستخدام (found)

| حالة الاستخدام | الحامل | AAD | القيمة الحرفية في Java ضمن 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | لا شيء | `DU8`، `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`، `C0ZG`، `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`، `F2P`، `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | لا شيء | `F3W` |
| `Event Edit` | `secretEncryptedMessage` النوع 1 | لا شيء | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` النوع 2 | لا شيء | `F3Y.A00`، فقط مع العلم **17811** |
| `Poll Edit` | `secretEncryptedMessage` النوع 4 | لا شيء | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` النوع 5 | لا شيء | `F3Y.A00` |
| `WASA` | مسار bot (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | مرحلتان، 3.3 |
| `Report Token` | مفتاح reporting token | native | لا قيمة حرفية في Java؛ موجودة في `libwhatsapp.so`، تُشتق natively (3.4) |

### 3.3 نسخة Bot / WASA (found، التفاصيل inferred)

لحالة الاستخدام `WASA` للاشتقاق مرحلتان ولا توجد سلسلة حالة استخدام في الثانية:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` هو المعدِّل و`jidB` هو JID البعيد (الدردشة)، ويجب أن يكون `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`)؛ المعرّف هو مفتاح الرسالة الحالية إن وُجد، وإلا مفتاح الهدف (lambda في `C33285Eeb.A03`). النظير native: `WcmBotMessageSecretAPICreateWithMessageSecret`. سياق Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 مفتاح reporting token (found / inferred)

يستدعي `C33364Efs.A06` و`C33421Ego` الدالة `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: الكائن native يشتق المفتاح لمعرّف حالة الاستخدام **5**؛ جهة Java تمرر فقط السلاسل الخام للـ JID. السلسلة `Report Token` موجودة في المكتبة native؛ ربط المعرّف 5 بتلك السلسلة مستنتج. الـ token والرفع: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. تخطيط AEAD

| العنصر | القيمة | المستوى |
|------|-------|------|
| الشيفرة | AES-GCM، native (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`؛ فك التشفير `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| المفتاح | 32 بايت من القسم 3 | found |
| IV | **12** بايت عشوائية لكل عملية تشفير (`SecureRandom`)؛ فك التشفير يرفض أي حجم آخر | found |
| الوسم | 16 بايت؛ الثابت 16 يُمرَّر في الاستدعاءين؛ الموضع (ملحق بنهاية النص المشفر) مستنتج من فك تشفير Baileys | found / inferred |
| AAD | حسب حالة الاستخدام (3.2)؛ `null` عندما يكون المزوّد `C34631F1e` | found |
| النص الصريح | proto الداخلي المتسلسل (الجدول 5) | found |
| المخرج | الثلاثية `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| نتيجة فارغة | سجل `encryption values are invalid`، الخطأ `Encryption using iJniBridge failed` | found |

إعادة محاولة التصويت: إذا كان التصويت يحمل IV وحمولة بالفعل (`C30957Dd6.A03` / `A04`) يُعاد إرسال النص المشفر نفسه بدل إعادة التشفير (found، فرع `DUA` القديم).

---

## 5. الحوامل والنصوص الصريحة

| الحامل (حقل في `Message`) | الفئة | الحقول | النص الصريح بعد فك التشفير |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**، `encPayload` **2**، `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (يُمسح قبل التشفير)، `text` **2**، `groupingKey` **3**، `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**، `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**، `encIv` **2**)، `metadata` **3** (`C30532DQe`: `pollNameHash` **1**، `lastEditStanzaId` **2**)، `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (bytes مكررة، hashes الخيارات) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**، `encPayload` **2**، `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown، 1 going، 2 not going، 3 maybe)، `timestampMs` **2**، `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**، `encPayload` **2**، `encIv` **3** | `Message` كاملة (متن التعليق)؛ الصيغة الصريحة هي `commentMessage` **77** (`DQV`: `message` **1**، `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**، `encPayload` **2**، `encIv` **3**، `secretEncType` **4** | `Message` كاملة |
| `reactionMessage` **46** | `DSH` | الصيغة الصريحة | تفاعل صريح |
| `conditionalRevealMessage` **120** | n/a | ليس من مخطط message-secret (القسم 14.1) | رسائل مجدولة |

`SecretEncType` (`E2Q`): `UNKNOWN` 0، `EVENT_EDIT` **1**، `MESSAGE_EDIT` **2**، `POLL_EDIT` **4**، `POLL_ADD_OPTION` **5**. القيمة 3 غير موجودة في هذا البناء (`forNumber(3)` تعيد null، وتُعامل كمجهولة وتُرفض).

`MessageKey` (`BD5`): `remoteJid` **1**، `fromMe` **2**، `id` **3**، `participant` **4**.

---

## 6. جهة المرسل

### 6.1 المسار المشترك (found، `C33285Eeb.A03`)

1. حل FMessage الهدف بالمفتاح (`target message not found. Cannot proceed further` -> الخطأ 71).
2. قراءة سرها من `message_secret`؛ null أو الطول != 32 -> `message secret missing or invalid` (66).
3. المفتاح الأصلي عبر `C43661qB.A03` (null -> الخطأ 0). مرسل الهدف عبر `C12300aw.A01`.
4. في دردشة 1:1 (`C0DZ.A0k(chat)`) يُحوَّل مرسل الهدف إلى فضاء أسماء المعدِّل: المعدِّل LID والهدف PN -> يُعيَّن الهدف من PN إلى LID؛ المعدِّل PN والهدف LID -> يُعيَّن الهدف من LID إلى PN. في المجموعات لا تحويل.
5. Event Response فقط: العلم **15791**، دردشة 1:1 ومعدِّل من نوع حساب -> يُحوَّل المعدِّل إلى PN.
6. IV عشوائي بطول 12 بايت، اشتقاق المفتاح (3.1)، AES-GCM مع AAD حالة الاستخدام.
7. بناء `MessageKey` الخارجي من مرسل الهدف والمفتاح الأصلي (`C32717EOy.A01`)؛ يحتوي الحامل `targetMessageKey` و`encIv` و`encPayload`.

### 6.2 لكل حامل (found)

| الحامل | بوابة الإرسال |
|---------|--------------|
| التفاعل (`DU8.ADr`) | يُشفَّر **فقط** إذا كانت الدردشة مجموعة (`C0DZ.A0l`) مع `group_type == 3` (`C0GQ.A0A`؛ يُضبط في `CMP` من `isDefaultSubgroup_`، أي مجموعة فرعية افتراضية لمجتمع، والتفسير inferred) وعلم سياق التسلسل `A09` خاطئ. في كل دردشة أخرى يُرسل `reactionMessage` الصريح. يُصفَّر `ReactionMessage.key` قبل التشفير (ينتقل المفتاح إلى `targetMessageKey` الخارجي) |
| تصويت الاستطلاع (`DUA.ADr`) | العلم **6772** مفعّل: مساعد مشترك، مشفر دائمًا؛ معطّل: فرع قديم مضمَّن بالاشتقاق وAAD نفسيهما (مرسل الهدف = LID الخاص للاستطلاعات الخاصة، وإلا JID المشتق من مفتاح هدف التصويت؛ المعدِّل = LID الخاص). يُختم `metadata` (`pollNameHash`، و`lastEditStanzaId` اختياريًا) عندما يكون العلم **31593** مفعّلًا |
| رد الحدث (`DU9.ADr`) | مشفر دائمًا؛ `EventResponseMessage` الصريح فيه `response` و`timestampMs` و`extraGuestCount` |
| التعليق (`F3W.ADr`) | مشفر دائمًا؛ النص الصريح هو `Message` التعليق بكاملها؛ الهدف هو مفتاح الأب في `CommentMessageInfo` |
| التعديل المشفر بالسر (`F3Y.C5S`) | فقط عندما تحمل الرسالة معلومات تعديل من النوع `E2Q` وسياق التسلسل ليس معاد توجيه / يتيم؛ `MESSAGE_EDIT` يحتاج إضافة إلى العلم **17811** (وإلا يرمي `getUseCase` استثناء). لتعديلات الرسائل الخاصة يظهر سطرا سجل (`sending the Message Yourself edit unwrapped`، `sending the agent reply edit unwrapped`) يدلان على حالات تُرسل كتعديلات صريحة؛ الشرط الكامل (الأعلام **37948**، **35457**) ضاع في فك التجميع |

تُرفض الحمولات المشفرة بالسر المتداخلة على الجهتين (`nested_secret_encrypted_message`).

---

## 7. جهة المستقبل

### 7.1 فك التشفير (found، `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (المعدِّل) حسب الحامل: LID الخاص عندما يكون الظرف مني؛ الاستطلاع: JID المرسل (`c0df` أو `B4g()`)؛ رد الحدث: مستخدم الدردشة في 1:1 وإلا مستخدم الظرف؛ التعليق: LID فقط (`C0DZ.A0Y`: الأنواع 18، 19، 25)، ومرسل PN يفشل بالخطأ 0؛ التفاعل: مرسل الظرف فقط إن كان LID، وإلا null.

### 7.2 إعادة محاولة الهوية LID / PN (found للبنية، الذيل inferred)

تستخدم المحاولة الأولى الـ JID كما هي. عند الفشل يعيّن المساعد الـ JID كليهما إلى فضاء الأسماء الآخر (`C0YH.A0I` من LID إلى PN، `A0F` من PN إلى LID) ويعيد المحاولة مرة واحدة؛ وإذا كان كلاهما LID أصلًا أو التعيين مفقودًا تكون النتيجة الخطأ **51** (فشل فك التشفير). ضاع جزء من ذيل إعادة المحاولة في فك التجميع، لذا فمجموعة الأزواج المجرَّبة بالضبط مستنتجة. الفحص هو مصادقة GCM: الزوج الخاطئ يفشل والصحيح يفك التشفير.

### 7.3 الأب مفقود: الرسائل اليتيمة (found)

| الحامل | السلوك عند عدم العثور على الأب أو كونه بديلًا مؤقتًا |
|---------|-----------------------------------------------------------|
| التفاعل | تُخزَّن FMessage من النوع **56** مع بايتات `Message` الخام (`DdA(key, 56, ts).A02`)؛ يؤجَّل فك التشفير |
| تصويت الاستطلاع | `C30957Dd6.A02 = Message.toByteArray()`؛ يُخزَّن دون فك تشفير |
| رد الحدث | `Dd7(key, target, bytes, ts)` يُخزَّن دون فك تشفير |
| التعليق | بديل مؤقت `C34671Zb` مع مفتاح الأب وصف `-1` |
| التعديل المشفر بالسر | `DeD(MessageOrphan)` بنوع يتيم **5**، السبب **1** (الأب غائب) أو **2** (بديل مؤقت) |

إعادة التشغيل عند وصول الأب متوقعة (اليتامى تُحفظ مع البايتات الخام) لكن محفّز إعادة التشغيل لم يُتتبَّع (inferred).

### 7.4 التحقق بعد فك التشفير (found)

| الحالة | الفحص | الفشل |
|------|-------|---------|
| Stanza `type=poll` + `<meta polltype="edit">` | يجب أن يكون `secretEncType` هو `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | النوع `POLL_ADD_OPTION` وحقل stanza ثانٍ يساوي `poll_add_option` (الحقل غير محلول) | `poll_add_option_stanza_invalid` (76) |
| تعديل الحدث | نوع الرسالة الداخلية 92، والمفتاح الناتج يساوي المفتاح الخارجي | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| تعديل الاستطلاع | النوع الداخلي 66، الرسالتان استطلاعان، نفس وقت الانتهاء والأعلام، تعديلات الخيارات متسقة مع الخيارات المخزنة، الطابع الزمني ليس بعد وقت الانتهاء | `poll_edit_invalid_edits`، `poll_edit_invalid_option_edits`، `poll_edit_invalid_time` |
| إضافة خيار للاستطلاع | النوع الداخلي 137، الأب استطلاع، مفتاح الهدف يساوي المفتاح الخارجي، ليس بعد وقت الانتهاء | `poll_add_option_past_end_time` |
| استقبال تعديل الاستطلاع | يجب أن يكون AB int **24886** غير صفري | الخطأ 10016 ("futureproofing") |
| استقبال إضافة خيار للاستطلاع | يجب أن يكون AB **25758** غير صفري | الخطأ 10017 |
| تصويت الاستطلاع | يجب أن يكون الاختيار صالحًا للاستطلاع (`AbstractC33199EdC.A02`)؛ الطابع الزمني للتصويت ليس بعد وقت انتهاء الاستطلاع | `poll_update_past_end_time`، `invalid poll vote selection` |
| بيانات وصفية للتصويت | يُفحص `pollNameHash` + `lastEditStanzaId` مقابل الاستطلاع المخزن (`C32977EZa.A01`)؛ "unstamped" عند الغياب؛ عدم التطابق يُسقط التصويت | `poll_update_tc_drop` |
| شكل تصويت الاستطلاع | IV بطول 12 بالضبط (`poll_update_invalid_vote_enc_iv`)، الحمولة موجودة، الطابع الزمني للمرسل موجود | الخطأ 11 |
| رد الحدث | المفتاح وIV (12) والحمولة موجودة؛ يجب أن يكون الأب حدثًا أو رسالة سحب من المرسل | `parent message is not event message nor sender revoke` |

---

## 8. ربط المرسل / الهدف

| ما يربطه المفتاح | الأثر |
|------------------|--------|
| معرّف الرسالة الأصلية | لا يمكن إعادة استخدام نص مشفر على رسالة أخرى |
| JID مرسل الهدف | لا يمكن نسبته إلى مؤلف أصلي مختلف |
| JID المعدِّل | لا يمكن إعادة تشغيله كإضافة لمستخدم آخر |
| سلسلة حالة الاستخدام | نص مشفر لتفاعل لا يُفك كتصويت أو تعليق أو تعديل |
| AAD (تصويت الاستطلاع، رد الحدث) | يربط إضافة إلى ذلك `targetId` والمعدِّل داخل الوسم |

غير مربوط: JID الدردشة، الطابع الزمني، موضع النص المشفر في السلسلة، عدد الإضافات السابقة. المعدِّل الذي يستخدمه المستقبل هو `participant` / `from` في الظرف؛ وهو موثَّق بجلسة E2E لا بالسر. أي حائز للسر الأصلي (كل مشارك استقبل الرسالة الأصلية، في المجموعة) يستطيع اشتقاق مفاتيح لأي معدِّل؛ المخطط يمنع إعادة التوجيه من جهة المرحِّل، لا انتحال الهوية من أعضاء المجموعة (inferred من البناء).

---

## 9. بدائل غياب السر (found ما لم يُذكر خلاف ذلك)

| الحالة | المرسل | المستقبل |
|-----------|--------|----------|
| الأصل بلا سر | يفشل التشفير (66)؛ المسار القديم للاستطلاع: `invalid message_secret secretSize` | الأب موجود والسر null: الخطأ **66**، يُسجَّل في مُبلِّغ الأخطاء مع `parentMsgRowId` و`parentType` و`parentHasSecret`؛ الرمز 0 في `wam_message_secret_errors` |
| السر ليس 32 بايت | يُرفض التشفير | الخطأ **67**، رمز WAM 1 |
| الأب غير موجود | خطأ التشفير 71 | يُخزَّن كيتيم (7.3) |
| تفاعل في دردشة ليست مجموعة فرعية افتراضية | يُرسل `reactionMessage` الصريح بدلًا منه (لا حاجة لسر) | يعالجه الفرع الصريح |
| تعديل رسالة دون العلم 17811 | يرمي `getUseCase` استثناء (`unknown message secret encrypted type`، الرمز 0)؛ هل يتجنب المرسل النوع عندما يكون العلم معطلًا غير محلول | الاستثناء نفسه |
| فشل فك تشفير الإضافة | n/a | تبقى الإضافة مخفية / غير متاحة؛ لم يُعثر على نص بديل مرئي (unknown) |
| جهاز مرافق جديد بلا الأصل | n/a | مزامنة السجل تحمل السر في `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | يُضبط على الرسائل التي لها معلومات تعديل (12.3) | يخبر المستقبل ألا يعرض بديل الفشل؛ مستهلك العلم غير محلول |

---

## 10. stanza `<message>`: ما يضيفه العميل

تُبنى الأبناء الصادرة بواسطة مساهمين مستقلين (`InterfaceC35538FaZ`) يلحقون بباني stanza `C33150EcP`.

### 10.1 السمات (found)

| السمة | المنتِج / المستهلِك | القيم / المعنى |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`، `media`، `reaction`، `poll`، `event`، `pay`، `medianotify`، `scheduled-call` (من proto): `secretEncryptedMessage` مع `EVENT_EDIT` -> `event`، ومع `POLL_EDIT` / `POLL_ADD_OPTION` -> `poll`؛ `MESSAGE_EDIT` يسقط إلى `text` / `media`؛ حقول التفاعل (صريحة أو enc) -> `reaction`؛ تحديث / إنشاء استطلاع -> `poll`؛ `encEventResponseMessage` وحدث -> `event` |
| `edit` | مواصفات الاستقبال `C33474Ehg` (تتطلب وسم العقدة `status`؛ علاقته بـ stanza `<message>` العادي غير محلولة)، `C23206A1f` (newsletter)؛ الإقرارات `AbstractC33465EhX.A05` | `1`، `7`، `8` في `C33474Ehg`؛ `3` و`8` في مواصفات newsletter؛ تعكسه الإقرارات ما لم يكن `0` / فارغًا؛ انظر 10.2 |
| `category` | stanza، الإقرارات، إيصالات إعادة المحاولة | `peer` يختار مسار peer-message |
| `device_fanout` | `F6M` | `"false"` في إعادات المحاولة الموجهة 1:1 |
| `addressing_mode`، `participant`، `recipient`، `expiration`، `offline`، `dhash`، `sts` | النقل | هوية / دورة حياة، لا محتوى |
| `peer_recipient_pn`، `peer_recipient_lid`، `peer_recipient_username`، `recipient_latest_lid`، `participant_username`، `sender_account_kind`، `sender_country_code`، `eph_setting` | محلّلات الهوية (`AbstractC33466EhY`، `C34763F6g`) | أسماء بديلة PN / LID / username |

### 10.2 قيم `edit`

| القيمة | السياق | المستوى |
|-------|---------|------|
| `1` | تعديل رسالة مرسلة (يُحلَّل في `C33474Ehg.A0L`) | found |
| `2` | تثبيت في الدردشة: مسار الاستقبال يتطلب إصدار التعديل الداخلي 2 (`Invalid edited version`) | الربط بالسمة inferred |
| `3` | تعديل رسالة newsletter: يُحلَّل فقط في مواصفات newsletter (`C23206A1f.A0G`)، و`EWW.A01` يضبط إصدار التعديل 3 عندما تكون الدردشة newsletter (نوع JID 21، الخادم `newsletter`) | found (يحل "unknown 3" السابقة) |
| `7` | سحب من المرسل (`C33474Ehg.A0M`) | found |
| `8` | حذف من المشرف (`C33474Ehg.A0S`، مواصفات newsletter `A0H`) | found |
| `0` / فارغ | رسالة عادية؛ تُحذف من الإقرارات | found |

إصدار التعديل الداخلي (`EWW.A01`) هو `1` للدردشات العادية و`3` لـ newsletters؛ تعديلات الدردشات العادية تضبط أيضًا علم إخفاء `decrypt-fail` (12.3).

### 10.3 الأبناء المباشرون (found)

| الابن | المنتِج | المعنى |
|-------|----------|---------|
| `enc` | طبقة التشفير | النص المشفر، انظر القسم 11 |
| `participants` / `to` | `F6E` وfanout | نصوص مشفرة لكل جهاز |
| `device-identity` | `F6B` | هوية الجهاز الموقّعة |
| `registration` | المحلّل `C33474Ehg.A04` | 4 بايت بالضبط |
| `tctoken` | `F6I`، `AbstractC33466EhY.A01` | AB int **20606** على الأكثر لكل stanza، يُفعَّل بـ **20605** |
| `cstoken` | `F6G` | token جهة الاتصال الباردة |
| `padding` | `F6H` | بايتات عشوائية، الطول `retryCount × 1571`، الأعلام **8311**، **9209** (`ta_pad` موجود أيضًا) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (HMAC بطول 16 بايت)، انظر [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | القسم 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`، `TRANSACTIONAL`، `NON_TRANSACTIONAL`، `OTHER`؛ `tag`: `AUTHENTICATION`، `UTILITY`، `MARKETING` |
| `biz` | معالج الأعمال `C34748F5r` | 13.1 |
| `automated`، `multicast`، `url_text`، `url_number` | `F68` | عقد أعلام فارغة من قناع بتات في الباني: `2` url_text، `4` url_number، `64` multicast، `128` automated |
| `rcat` | المحلّل | فئة ثنائية معتمة (status) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` عند الإرسال إلى JID من النوع 3 (قائمة بث، inferred)، الأعلام **16656** (إصدار) و**13537** (القيمة) |
| `verified_name` | الأعمال | شهادة النشاط التجاري الموثّق |
| `unavailable`، `bypassed` | المحلّل | عقد علامة؛ الحرفية `unavailable` لم تُطابَق في 2.26.41.6 (قائمة على ثابت)، والدلالات غير متحقق منها هنا |

---

## 11. عقدة `<enc>`

### 11.1 السمات (found، `AbstractC33466EhY.A09`)

| السمة | القيمة | الشرط |
|-----------|-------|-----------|
| `v` | `2` أو `3` | إصدار النص المشفر (محلّل الاستقبال يقبل `EncVersion2` و`EncVersion3` وfutureproof) |
| `type` | `msg`، `pkmsg`، `skmsg`، `frskmsg`، `msmsg`، `none` | رسالة Signal، رسالة prekey، sender key، `frskmsg`، bot `msmsg`، علامة نص صريح |
| `count` | عدد إعادات المحاولة | يُحذف عندما يكون 0 |
| `mediatype` | انظر 11.2 | تصنيف الوسائط / التفاعلي |
| `native_flow_name` | اسم التدفق | رسائل native-flow |
| `duration` | int >= 0 | الموقع المباشر |
| `decrypt-fail` | `hide` | الرسالة مُعلَّمة بقابلية الإخفاء (12.3) |
| `state` | `false` | إرسالات `pkmsg` تحت علم في حامل النص المشفر |
| `session_type` | `pq` | علم حامل جلسة ما بعد الكم |
| `bucket` | سلسلة | عند ضبطه على حامل النص المشفر |

فحوص الاستقبال (`C33013EaB`): يجب أن تتفق عقدتا `<enc>` في رسالة واحدة على عدد إعادات المحاولة وإصدار النص المشفر؛ `enc` على newsletter مرفوض (`Received enc message for newsletters`)؛ يُحترم `decrypt-fail=hide` فقط عندما لا تكون الفئة `peer` ويكون مسند الدردشة `C1ZB.A0L` خاطئًا.

### 11.2 قيم `mediatype` المقبولة في المواصفات (found، 37 مدخلًا)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. enum `native_flow_name` (8 مدخلات): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. عقدة `<meta>`

تُجمع كل السمات والأبناء في `EZV` بواسطة المعالجات التي يستدعيها `F6K` (لكل فئة رسالة `FXq.AAl`، ولكل add-on `FZH.AAl`) وتُصدر كـ `<meta>` واحدة (`C33150EcP.A00`). المجمّع الفارغ لا يُصدر شيئًا.

### 12.1 مصنِّفات العمليات (found)

| السمة | القيم | المنتِج |
|-----------|--------|----------|
| `polltype` | `creation`، `edit` (`F2N`)، `vote` (`DUA`)، `add_option` (`F2L`، `F4E`) | معالجات الاستطلاع |
| `event_type` | `creation`، `edit` (`F2M`)، **`response`** (`DU9`) | معالجات الأحداث |
| `content_type` | `add_on` لفئة add-on `AbstractC35181aQ` (تشمل التفاعلات؛ التصويتات / الردود inferred) في الدردشات التي يكون فيها `C0DZ.A0U` خاطئًا؛ `status_notify` / `add_on` لإشعارات status | `F6K` |
| `type` | `scheduled_message` مع `st` (ثوانٍ، تُحذف لفئة رسالة إلغاء الجدولة) والابن `<key rkid="...">` (بايتات المفتاح تُحذف لتلك الفئة) | `F6K`، الكشف الشرطي |
| `appdata` | سلسلة حرة من `FZF.AVN()`؛ تعديل appdata مرفوض | `F6K` |
| `tag_reason` | `user_update`، `new_member`، `rereg_recovery_request`، `rereg_recovery_response`، `user_delete` | رسالة وسم العضو `F3F` |
| `context_source` | `channels_invitation`، `event_invitation` (وغيرها) | `AJR` |
| `message_association_type` | token الارتباط، إضافة إلى `hd_image_dual_upload`، `hevc_video_dual_upload`، `av1_video_dual_upload` في رفع status | `F4G`، `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`، `thread_msg_sender_jid` | معرّف / JID الأب | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`، `allowlist`، `denylist`، `customlist`؛ `is_group_status` `true`؛ الابن `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`، `group_status`، `general`، إضافة إلى سلاسل نقاط دخول Meta AI (`favicon`، `chat_list`، `nullstate_*`، `typeahead_*`، ...) | `F6K`، `EnumC14320eI`، `C198208bu` |
| `acp` | `2` لدردشات 1:1 تحت العلم **36091** (المعنى غير محلول) | `F6K` |
| `view_once` | `true` لأنواع العرض لمرة واحدة تحت العلم **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (نوع الرسالة 108) | `F6K` |
| `share_pn` | `true` (نوع الرسالة 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`، `image`، `video`، `mixed` | `F6K` |
| `destination_id`، `conversation_thread_id`، `thread_origin`، `peripheral` | توجيه bot / السلسلة | `F6K` |

### 12.2 ما يُحلَّل عند الاستقبال (found)

مدخلات `<meta>` التي يقرؤها العميل: `polltype`، `event_type`، `target_id`، `target_sender_jid`، `target_chat_jid`، `target_chat_jid_lid`، `from`، `capi` (دردشات المجموعات فقط)، `thread_msg_id`، `message_association_type`، `status_mentioned`، `push_eligible`، `session_scope`، `content_type`، `tm_csat_exp_ts`، `tm_csat_cooldown` (ثوانٍ، تُخزَّن بالملّي ثانية)، `is_wamo_sub`، `original_msg_t`، `msg_edit_t`، والأبناء `mention_source/to`، `mentioned_users/to`. تضيف metas الخاصة بـ newsletter: `admin_profile`، `paid_partnership`، `ai_content` (مأخوذة من الفهرس السابق؛ لم تُعد قراءتها هنا، غير متحقق منها). `deprecated_lid_session` لم يُعثر عليها في 2.26.41.6.

---

## 13. `<biz>`، `<bot>`

### 13.1 `<biz>` (found، `C34748F5r.CM3`)

```xml
<biz native_flow_name="...">                       <!-- or -->
<biz>
  <interactive type="native_flow">
    <native_flow name="..."/>
  </interactive>
  <buttons/> | <list/>
</biz>
<hsm category="..." tag="..."/>                    <!-- sibling, template classification -->
```

يقرأ المستقبل اسم التدفق (`native_flow_name` أو `name` المتداخل)، ثم يصنّف: وجود `buttons`، أو وجود `list`، أو native flow؛ ومع وجود اسم وشقيق `hsm` يصبح قالبًا. تسمى إخفاقات التحقق `InvalidTemplateMessage` و`InvalidListMessage` و`InvalidButtonMessage` و`InvalidInconsistentFlowName` و`InvalidFlowNotOwned` و`InvalidDeeplyNested`: مصنِّف `biz` المخالف للحمولة المشفرة هو إخفاق تحقق، لا نوع رسالة مختلف. سمات `biz` أخرى تُقرأ في أماكن أخرى: `campaign_id`، `notification_cta`، `privacy_mode_ts`، `host_storage`، `actual_actors`، `biz_bot`، الابن `quality_control` مع `decision_source`.

### 13.2 `<bot>` (found)

الصادر (`F6M`): السمات `type` (`request_welcome`، `prompt`، `command`، `search`، `memu_onboarding`، `memu_invoke`، `voice`، `voice_background`، `text_input`، `live_ai`، `feedback`)، `client_thread_id`، `mode_selected`، `persona_type` (`1p`، `ugc`، `3p`)، `local_automated_type` (`1p_partial`)، `agent_engagement_type`، `is_lid`، الابن `tee_routing` (`tee_routing_token`، `tee_ik_id`). الوارد (`C34747F5q`): `<bot edit="full|...">` والافتراضي `full`، `edit_target_id`، `sender_timestamp_ms`، `type`، `client_thread_id`؛ بدون `<meta target_id>` لا تُعالج الرسالة كاستجابة bot. التفاصيل: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. مخططات ذات صلة ليست من message-secret

### 14.1 الكشف الشرطي (الرسائل المجدولة)

يستخدم `conditionalRevealMessage` (الحقل **120**) مفتاح كشف عشوائيًا منفصلًا (`<meta type="scheduled_message" st><key rkid>`)؛ الخادم يتحكم بالكشف. لا HKDF من `messageSecret`. دواخل بروتوكول الكشف لم تُتتبَّع (unknown).

### 14.2 Reporting token

يستخدم `reportingTokenVersion` (الحقل **8**) و`<reporting_token>` بطول 16 بايت مفتاح معرّف حالة الاستخدام native رقم 5 (3.4)، لا HKDF في Java. محتوى الـ token: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. مدقق دعم الجهاز المرافق (found)

`CompanionSupportVerifier` (`C34757F6a`، على الجهاز المرافق فقط، خلف علم): الرسائل غير `peer` تُقبل فقط إذا كان `type` ضمن `{text, media, reaction, poll, event}` (أو `pay` مع ابن `transaction` / `pay` للحوالة) وكل ابن مباشر ضمن `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. وإلا يسجّل `unsupported child node=` / `unsupported message type=` وتُصنَّف الرسالة غير مدعومة على الجهاز المرافق. بث peer مع `participants` على جهاز مرافق يُسقط (`received peer broadcast message on companion-mode, dropping`، nack 415 / 18). الابن الجديد `cap` و`tctoken` / `cstoken` ليسوا في القائمة؛ مكان معالجتهم قبل هذا الفحص غير محلول. `unavailable` و`participants` تمر عبر مساراتها الخاصة.

---

## 16. أعلام الميزات (المعرّفات كما تُقرأ في مواضع الاستدعاء؛ الأسماء غير محلولة)

| المعرّف | النوع | ما يتحكم به |
|----|------|----------|
| **6772** | bool | تصويت الاستطلاع: المساعد المشترك مقابل التشفير القديم المضمَّن |
| **31593** | bool | ختم `metadata` لتصويت الاستطلاع |
| **17811** | bool | حالة الاستخدام `Message Edit` (إرسال واستقبال) |
| **37948**، **35457** | bool | شروط تغليف تعديلات الرسائل الخاصة |
| **24886** | int | استقبال تعديل الاستطلاع (0 = مرفوض، 10016) |
| **25758** | int | استقبال إضافة خيار للاستطلاع (0 = مرفوض، 10017) |
| **15791** | bool | تحويل معدِّل رد الحدث من LID إلى PN في دردشات 1:1 |
| **3142**-**3146**، **2200**، **11104**، **19303** | bool | توليد السر حسب فئة الدردشة |
| **8860** | int | أقصى إصدار reporting-token (توليد السر) |
| **24741** | bool | سر لنوع الرسالة 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**، **13537** | bool | الابن `cap` وقيمته |
| **8311**، **9209** | bool | الحشو |
| **20605**، **20606** | bool / int | تفعيل `tctoken` / الحد لكل stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17، المصدر مقروء، لم يُختبر شيء)

فقط حقائق مقروءة في `src/Utils/process-message.js` و`src/Utils/reporting-utils.js` و`src/Utils/messages.js` و`src/Socket/messages-send.js`.

| الموضوع | Baileys | Android |
|-------|---------|---------|
| المفتاح | `key0 = HMAC-SHA256(key = 0×32, secret)`؛ `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | مطابق (3.1) |
| حالات الاستخدام | `Poll Vote`، `Event Response`، `Enc Comment`، `Enc Reaction`، `Event Edit`، `Message Edit`، `Poll Edit`، `Poll Add Option`، إضافة إلى `Message Schedule` للقيمة 3 في enum | السلاسل نفسها؛ القيمة 3 غير معرّفة في 2.26.41.6 |
| AAD | `id\0modifier` للاستطلاع والحدث، فارغ للتعديل / التعليق / التفاعل | مطابق |
| الهوية | يجرّب مرشحي PN وLID للمنشئ والمعدِّل، وGCM يصادق الزوج الصحيح | الفكرة نفسها (7.2) |
| سر مفقود | يسجّل، ويصدر تحديث `encReactionMessage` / `pollUpdateMessage` الخام، دون فك تشفير | يُخزَّن كيتيم |
| توليد السر | `randomBytes(32)` للاستطلاع والحدث وعندما يكون `messageContextInfo.messageSecret` مفقودًا | 2.2 |
| مفتاح reporting | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`؛ يُتخطى reporting للتفاعلات و`encReactionMessage` و`encEventResponseMessage` و`pollUpdateMessage` | native المعرّف 5 (3.4) |
| جهة الإرسال | لم يُعثر على مرسِل لـ `pollUpdateMessage` أو `encReactionMessage` أو `encEventResponseMessage` أو `encCommentMessage` في الملفات المقروءة | Android يرسل الأربعة جميعًا |

النتيجة المقروءة من الكود: يستطيع Baileys فك تشفير المتابعات التي يستقبلها لكن الملفات المقروءة لا تحتوي تشفيرًا لها. لم يُبحث عن وجود مساعد إرسال في مكان آخر.

---

## 18. حالات الخطأ

| العَرَض | السبب | الحل |
|---------|-------|-----|
| الخطأ 11 | IV ليس 12 بايت أو الحمولة فارغة / حقل مفقود | افحص `encIv` (الحقل 3، أو 2 لـ `PollEncValue`) |
| الخطأ 51 | فضاء أسماء JID المرسل / الهدف خاطئ (PN مقابل LID)، أو المعرّف الأصلي خاطئ | أعد المحاولة بفضاءي الأسماء، واستخدم معرّف الرسالة الأصلية (غير المعدّلة) |
| فشل التصويت لاستطلاع معدَّل | يجب أن يكون معرّف المفتاح هو معرّف الاستطلاع الأصلي لا معرّف آخر تعديل | حلّ المفتاح الأصلي |
| فشل تعليق من مرسل PN | فك تشفير التعليق يتطلب مرسل LID | استخدم LID |
| رفض تعديل الاستطلاع / إضافة خيار | الأعلام **24886** / **25758** معطلة، أو `polltype` في stanza يخالف `secretEncType` | أرسل `<meta polltype>` والنوع المتطابقين |
| تجاهل الرسالة على جهاز مرافق | عقدة فرعية أو `type` غير معروف | التزم بقائمة السماح (القسم 15) |
| رسالة `<biz>` غير مدعومة | المصنِّف يخالف الحمولة | اشتق المصنِّف من الحمولة |

---

## 19. فروق أساسية

| هذا | ليس هذا |
|------|----------|
| `messageSecret` (لكل رسالة، عشوائي، 32 بايت) | مفتاح الوسائط، sender key، مفتاح مزامنة حالة التطبيق، مفتاح المكالمة |
| مفتاح حالة الاستخدام (HKDF، لكل هدف / مستخدم / حالة استخدام) | السر نفسه |
| `secretEncryptedMessage` (يغلّف `Message` كاملة) | `encReactionMessage` (يغلّف `ReactionMessage`) |
| AAD لـ `Poll Vote` / `Event Response` = المعرّف + NUL + المعدِّل | تعديل / تعليق / تفاعل مع AAD فارغ |
| `targetMessageKey` في الحامل الخارجي | `ReactionMessage.key` داخل النص الصريح (يُمسح عند الإرسال) |
| `meta polltype` / `event_type` (مصنِّف) | الحمولة المشفرة (المحتوى) |
| سمة stanza `edit` | `secretEncType` (حالة استخدام التشفير) |
| `decrypt-fail="hide"` على `<enc>` | إيصال إعادة المحاولة / عقدة `retry` |

---

## 20. التدفق الكامل (تصويت استطلاع، 1:1 أو مجموعة)

```
[Creator]                                            [Server]                      [Voter]
   │ poll creation Message                              │                             │
   │ messageContextInfo.messageSecret = random 32       │                             │
   │ store message_secret[row]                          │                             │
   │ <message type="poll"><meta polltype="creation">────▶────────────────────────────▶ stores secret
   │                                                    │                             │
   │                                                    │      select options (hashes)│
   │                                                    │      secret = store[poll]   │
   │                                                    │      key = HKDF(secret,     │
   │                                                    │        pollId‖creator‖voter │
   │                                                    │        ‖"Poll Vote")        │
   │                                                    │      iv = random 12         │
   │                                                    │      ct = GCM(key, iv,      │
   │                                                    │        PollVoteMessage,     │
   │                                                    │        aad = pollId\0voter) │
   │              <message type="poll"><meta polltype="vote">                         │
   │◀────────────────────────────────────────────────────◀ pollUpdateMessage{key,vote{ct,iv},metadata,ts}
   │ parent found? no -> orphan, keep raw bytes         │                             │
   │ validate end time, enc iv = 12                     │                             │
   │ key = HKDF(secret, pollId‖creator‖voter‖"Poll Vote")                              │
   │ GCM-decrypt, fail -> retry PN/LID pair, else 51    │                             │
   │ check option hashes ⊂ poll options, stamp match    │                             │
   │ apply vote                                         │                             │
```

---

## 21. المجهولات

| العنصر | الحالة |
|------|-------|
| المسندات الدقيقة لـ `EZN.A01` و`C35201aS.A00` والأعلام 3142-3146 | رُصدت بوابات حسب فئة الدردشة، والمجموعة المرئية للمستخدم غير محلولة |
| جدول معرّفات حالات الاستخدام native (الأسماء إلى معرّفات غير 5 = Report Token) | لم يُقرأ |
| موضع وسم GCM وحجم مفتاح AES | مستنتج من الثوابت ومن Baileys |
| الشرط الكامل لإرسال `MESSAGE_EDIT` الخاص مغلَّفًا مقابل صريحًا (الأعلام 37948، 35457) | فك التجميع أضاع تدفق التحكم |
| معنى `acp="2"`، وعلم التسلسل `A09`، وحقل stanza الثاني لإضافة خيار الاستطلاع | غير محلول |
| مستهلك `decrypt-fail="hide"` على الظرف المحلَّل | العلم محمول إلى الظرف، والأثر لم يُتتبَّع |
| النتيجة المرئية للمستخدم لإضافة لا يمكن فك تشفيرها نهائيًا | لم يُعثر على نص بديل |
| `unavailable`، `bypassed`، `deprecated_lid_session` | لم يُعاد التحقق منها في 2.26.41.6 |
