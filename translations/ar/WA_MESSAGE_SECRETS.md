<!-- src-sha1: b8f7c5d44373d4a7bc19be29e7bd26af81a86f85 -->
# WhatsApp أسرار الرسائل — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** `messageSecret` لكل رسالة (التوليد، `MessageContextInfo`، المخزن المحلي، مزامنة التاريخ)، استخلاص مفتاح حالة الاستخدام (HKDF)، IV / AAD من نوع AES-GCM، الإضافات المشفَّرة (`encReactionMessage`، `pollUpdateMessage`، `encEventResponseMessage`، `encCommentMessage`، تحريرات `secretEncryptedMessage`)، ربط هوية المُرسِل/الهدف وإعادة محاولة LID/PN، الأيتام والحلول البديلة لغياب السرّ، امتدادات stanza من نوع `<message>` (السمات، سمات `<enc>`، `<meta>`، `<biz>`، `<bot>`، `<hsm>`، `<reporting>`، `<cap>`، الحشو، فحص دعم الرفيق)، أعلام الميزات، مقارنة Baileys

---

## 1. ما هو (تقنياً)

كل رسالة قابلة لاستقبال متابعة مشفَّرة لاحقاً تحمل سرّاً عشوائياً بطول 32 بايت في حمولتها المشفَّرة من طرف إلى طرف الخاصة بها (`MessageContextInfo.messageSecret`). تُشفَّر المتابعة (تفاعل، تصويت استطلاع، استجابة فعالية، تعليق، تحرير) بمفتاح مُستخلَص من ذلك السرّ، معرّف الرسالة الأصلية، المُرسِل الأصلي والمُعدِّل. يُرحِّل الخادم المتابعة كرسالة E2E عادية لكن لا يستطيع قراءتها أو نقلها إلى هدف أو مستخدم أو حالة استخدام أخرى دون كسر مصادقة GCM. كل العبارات تحليل ساكن للـAPK المفكَّك؛ لم يُلتقط شيء على السلك. المستويات: **found** = مقروء في الكود، **inferred** = مُستنتَج من الكود، **unknown** = غير محسوم. أُعيد حل الأسماء المُشوَّشة في 2.26.41.6 من سلاسل ثابتة (`MessageSecretCryptoHelper/`، `MessageEncUtils/`، سلاسل حالة الاستخدام، `FMessage*Protobuf/`، `SecretEncryptedMessagePreProcessor/`، `CompanionSupportVerifier/`).

يُعرِّف نفس الإصدار أيضاً امتدادات stanza من نوع `<message>` (القسم 10 وما بعده): سمات وعناصر فرعية تُصنِّف وتُوجِّه رسالة لكن لا تحمل محتواها. تُجمَّع هنا لأن `<meta polltype>` / `<meta event_type>` يجب أن تتفق مع الحمولة المشفَّرة بالسرّ (7.4).

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| مساعد التشفير (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` تشفير، `A04` فك تشفير (إعادة محاولة الهوية)، `A02` حل مفتاح الهدف |
| حاملا معطيات التشفير/فك التشفير | `C32833ETl` / `C32854EUg` | البيانات، المُرسِل، مفتاح الهدف، حالة الاستخدام/IV، الحمولة، المفاتيح، المُرسِل |
| استخلاص المفتاح | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256، ملح صفري |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`، `AbstractC32243E6m.A00` (`MessageEncUtils`) | أصلي، وسم بطول 16 بايت |
| مزوِّدو AAD | `FXU`: `C34633F1g` (Poll Vote)، `C34632F1f` (Event Response)، `C34634F1h` (WASA)، `C34631F1e` (لا شيء) | بيانات إضافية |
| مُولِّد السرّ | `AbstractC33322EfC.A01` | `SecureRandom`، 32 بايت |
| مخزن السرّ (`MessageSecretStore`) / إضافة في الذاكرة | `C35311ad` (جدول `message_secret`) / `C35171aP` على الرسالة `C13G` | الحفظ والحمل |
| مخطِّط المفتاح الأصلي (`ReferentialKeyUtil`) | `C43661qB.A03` | مفتاح الرسالة الأصلية غير المُحرَّرة |
| معالِجات التفاعل | `DU8` (الإرسال)، فرع `F2P` (الاستلام) | `reactionMessage` / `encReactionMessage` |
| تصويت الاستطلاع/استجابة الفعالية/التعليق | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| تحريرات مشفَّرة بسرّ (`SecretEncryptedMessagePreProcessor`) | `F3Y`، تعداد `E2Q` | `secretEncryptedMessage` |
| إنشاء استطلاع/فعالية (السرّ يُؤخذ عند الاستلام) | `F2N` / `F2M` | يقرأ `messageSecret` في FMessage |
| البروتو: السياق/الرسالة/المفتاح | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| مُحدِّد `type` الخاص بـstanza | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| مساهمو stanza الخارج | `InterfaceC35538FaZ`: `F6K` (meta)، `F6M` (bot)، `F68` (أعلام)، `F69` (cap)، `F6H` (حشو)، `F6L` / `F6C` (تقارير)، `F6G` (cstoken)، `F6I` (tctoken)، `F6B` (هوية الجهاز)، `F6X` (hsm) | يبنون عناصر `<message>` الفرعية |
| مُجمِّع `<meta>` | `EZV` (السمات `A01`، العناصر الفرعية `A00`) | عقدة `<meta>` واحدة |
| باني سمات `<enc>` | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| فحص دعم الرفيق | `C34757F6a` + `AbstractC32927EXc` | قائمة سماح للنوع والعنصر الفرعي |
| مُحلِّلات مخطط الوارد | `C33474Ehg` (حالة/عادي)، `C23206A1f` (نشرة)، `C34747F5q` (بوت)، `C34748F5r` (أعمال) | استخراج السمات والعناصر الفرعية |
| حدث WAM للخطأ | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. السرّ الخاص بالرسالة

### 2.1 أين يعيش (found)

`MessageContextInfo` (`C30624DTs`) هو الحقل **35** من `Message` (`C30628DTw`). الحقول ذات الصلة هنا:

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | رسالة / int | إشارة قائمة الأجهزة (غير متعلقة بالسرّ) |
| `messageSecret` | **3** | bytes (32) | السرّ الخاص بالرسالة |
| `paddingBytes` | **4** | bytes | الحشو |
| `messageAddOnDurationInSecs` | **5** | uint32 | مدة عمر الإضافة (دبوس: يجب أن تكون 0 لإلغاء التثبيت) |
| `botMessageSecret` | **6** | bytes (32) | نسخة البوت من السرّ |
| `botMetadata` | **7** | رسالة | سياق البوت |
| `reportingTokenVersion` | **8** | uint32 | نسخة رمز الإبلاغ لهذه الرسالة |
| `messageAddOnExpiryType` | **9** | تعداد | انتهاء الإضافة |
| `messageAssociation` | **10** | رسالة | الارتباط |

يحمل ناقل مزامنة التاريخ `WebMessageInfo` (`C30626DTu`) حقل `messageSecret` خاصاً به بالرقم **49** (found)، يُستخدَم عند تصدير الرسائل إلى رفيق جديد (القسم 2.4).

### 2.2 التوليد (found، الشروط مستنتجة جزئياً)

السرّ هو `SecureRandom.nextBytes(byte[32])` (`AbstractC33322EfC.A01`). يُرفَق قبل تسلسل الرسالة:

| الموضع | الشرط |
|-------|-------|
| `C33166Ecf.A06` (تحضير الإرسال) | الرسالة بلا سرّ وواحد على الأقل من: صنف استطلاع `C13J`؛ `EZN.A01(msg)` (صنف بوت/إضافة، بأعلام نوع دردشة **2200**، **11104**، **19303**)؛ بوّابات نوع الدردشة: مجموعة بالعلم **3143**، قائمة بث بـ**3144**، حالة بـ**3145**، بوّابة صنف **3146**؛ `C35201aS.A00` (العلم **3142**، دردشة ذاتية/بوت)؛ رسالة فعالية `C213509Ao` |
| `AJ0` (مُعالِج الإرسال) | نسخة رمز الإبلاغ `C35241aW.A05()` (علم AB عددي **8860**، محدود بـ`AbstractC35301ac.A00`) غير صفرية وصنف الرسالة لا يُستبعَد بواسطة `C35241aW.A02` (حالة، نشرة، أصناف إضافة مختارة) |
| `C72h`، `C34455Exe`، `EPA` | أجسام الحالة (`AbstractC34478Ey1.A0R`) تحصل على سرّ جديد عند الإنشاء |
| `C33437Eh4` | رسالة "طلب ترحيب" بوت، فقط عندما يطلبها مُستدعيها |
| `C9mW` | نوع الرسالة 117، العلم **24741**، عندما لا يوجد شيء |

المُسندات الكامنة وراء `EZN.A01`، `C35201aS.A00` وبوّابات `3142`..`3146` لم تُحسَم كاملاً؛ القائمة أعلاه تذكر ما يفحصه الكود، لا أي رسائل ظاهرة للمستخدم تؤهَّل. الرسائل بلا سرّ لا تستطيع استقبال إضافات مشفَّرة من هذا العميل (القسم 9).

### 2.3 التخزين المحلي (found)

يكتب `C35311ad` `message_secret(message_row_id, message_secret)` بدلالات استبدال (`MessageSecretStore/insertMessageSecret`) ويقرأ آخر صف لـ`message_row_id`. تحتفظ FMessage به كإضافة `C35171aP` (`A0L` ضبط، `A0c` جلب، `A0Q` = غير فارغ). يكتبه معالِجان في `AbstractC17240jU` (`C35161aO` وآخر مجهول) عندما تكون الإضافة متسخة (dirty) وتتأهَّل الدردشة.

### 2.4 التحقق والنقل من جانب الاستلام (found)

| الخطوة | السلوك |
|------|-----------|
| مُحقِّق البروتو `C33475Ehh.A0V` | يجب أن يكون `message_secret` بالضبط **32** بايت، رمز خطأ **67**؛ نسخة البوت (`bot_message_secret`، المجموعة `whatsapp_security`) تُحقَّق بالطريقة نفسها |
| إنشاء الاستطلاع `F2N` | ينسخ `messageSecret_` في FMessage الجديدة (`A0L`) |
| إجابات سؤال الحالة `C34838F9e` | نسخ مماثل لـ`statusQuestionAnswerMessage` |
| تصدير مزامنة التاريخ `C34388EwZ.A00` | يكتب السرّ المخزَّن في `WebMessageInfo.messageSecret` (49) |
| استيراد مزامنة التاريخ `C34388EwZ.C59` | ينسخه إلى الخلف (`A0L`) |
| التعليقات `C34387EwY` | تُعيد بناء `MessageContextInfo` من `WebMessageInfo.messageSecret` لخيط التعليق |

تُسجِّل `wam_message_secret_errors` (`DZ7`، `C273212s.A00`) `message_secret_error` **0** = غائب (يُخطَّط إلى رمز خطأ 66) أو **1** = طول غير صحيح (67) للرسائل التي تتطلب سرّاً (`AbstractC33322EfC.A00`: تحمل العلم وليست من صنف `C35281aa`).

---

## 3. استخلاص مفتاح حالة الاستخدام

### 3.1 الصيغة (found، `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = استخراج بملح صفري بطول 32 بايت (`AbstractC38971i1.A00(ikm, salt)`)، ثم حلقة التوسيع RFC 5869. أساسيات HKDF: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) القسم 5.1. تُستخدَم المخرجات بطول 32 بايت كمفتاح AES-256 (مستنتج من الطول؛ الاستدعاء الأصلي يأخذ المفتاح كـ`byte[]`).

المُدخلات:

| المُدخل | المصدر | ملاحظات |
|-------|--------|-------|
| `originalMessageId` | معرّف مفتاح الهدف بعد `ReferentialKeyUtil` (`C43661qB.A03`) عند التشفير؛ معرّف المفتاح من `targetMessageKey` الخاصة بالبروتو عند فك التشفير | لهدف مُحرَّر هذا هو معرّف الرسالة **الأصلي** (سجل `getOriginalKey`) |
| `targetSender` | مؤلِّف الرسالة الأصلية: المُرسِل المخزَّن (`C12300aw.A01`) | `UserJid`، فلا لاحقة جهاز (على مستوى النوع؛ الشكل النصي `user@server` مستنتج) |
| `modifier` | مؤلِّف الإضافة: JID الحساب الخاص (`C09A.A0G`، LID، يُعيده `CUC()` / `Ash()`) عند الإرسال، JID المُرسِل للغلاف عند الاستلام | |
| `useCase` | سلسلة من 3.2 | لا فاصل بين الأربعة عناصر |

JID الخاص هو JID حساب من نوع LID (`C14080dr`، الخادم `lid`، فحص "Invalid LID"). كلا `AnonymousClass091.Ash()` و`CUC()` يُعيدان نفس الحقل.

### 3.2 سلاسل حالة الاستخدام (found)

| حالة الاستخدام | الناقل | AAD | السلسلة الحرفية في Java في 2.26.41.6 |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | لا شيء | `DU8`، `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`، `C0ZG`، `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`، `F2P`، `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | لا شيء | `F3W` |
| `Event Edit` | `secretEncryptedMessage` النوع 1 | لا شيء | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` النوع 2 | لا شيء | `F3Y.A00`، فقط بالعلم **17811** |
| `Poll Edit` | `secretEncryptedMessage` النوع 4 | لا شيء | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` النوع 5 | لا شيء | `F3Y.A00` |
| `WASA` | مسار البوت (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | مرحلتان، 3.3 |
| `Report Token` | مفتاح رمز الإبلاغ | أصلي | لا سلسلة Java حرفية؛ موجودة في `libwhatsapp.so`، مُستخلَصة أصلياً (3.4) |

### 3.3 نسخة البوت/WASA (found، التفاصيل مستنتجة)

لحالة الاستخدام `WASA` يحمل الاستخلاص مرحلتين ولا سلسلة حالة استخدام في الثانية:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` هو المُعدِّل و`jidB` هو JID البعيد (الدردشة)، الذي يجب أن يكون `UserJid` (`WASA info jid must be a UserJid (hatch_jid)`)؛ المعرّف هو مفتاح الرسالة الحالي عند وجوده، وإلا مفتاح الهدف (lambda في `C33285Eeb.A03`). النظير الأصلي: `WcmBotMessageSecretAPICreateWithMessageSecret`. سياق Meta AI: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 مفتاح رمز الإبلاغ (found / inferred)

يستدعي `C33364Efs.A06` و`C33421Ego` `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`: يستخلص الكائن الأصلي المفتاح لمعرّف حالة الاستخدام **5**؛ جانب Java يمرِّر فقط سلاسل JID الخام. السلسلة `Report Token` موجودة في المكتبة الأصلية؛ تخطيط المعرّف 5 إلى تلك السلسلة مستنتج. الرمز والرفع: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. تخطيط AEAD

| العنصر | القيمة | المستوى |
|------|-------|------|
| التشفير | AES-GCM، أصلي (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`؛ فك التشفير `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| المفتاح | 32 بايت من القسم 3 | found |
| IV | **12** بايت عشوائية لكل تشفير (`SecureRandom`)؛ يرفض فك التشفير أي حجم آخر | found |
| الوسم | 16 بايت؛ الثابت 16 يُمرَّر في كلا الاستدعاءين؛ الموضع (مُلحَق بنص التشفير) مستنتج من فك تشفير Baileys | found / inferred |
| AAD | لكل حالة استخدام (3.2)؛ `null` عندما يكون المزوِّد `C34631F1e` | found |
| النص الصِّرف | البروتو الداخلي المُسلسَل (الجدول 5) | found |
| المخرَج | ثلاثية `(encIv, encPayload, targetMessageKey)` (`C53966OMp`) | found |
| نتيجة فارغة | سجل `encryption values are invalid`، خطأ `Encryption using iJniBridge failed` | found |

إعادة محاولة تصويت الاستطلاع: إذا كان التصويت يحمل أصلاً IV وحمولة (`C30957Dd6.A03` / `A04`) يُعاد إرسال نفس نص التشفير بدلاً من إعادة التشفير (found، فرع `DUA` القديم).

---

## 5. النواقل والنصوص الصِّرفة

| الناقل (الحقل في `Message`) | الصنف | الحقول | النص الصِّرف المفكوك التشفير |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**، `encPayload` **2**، `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (يُمحى قبل التشفير)، `text` **2**، `groupingKey` **3**، `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**، `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**، `encIv` **2**)، `metadata` **3** (`C30532DQe`: `pollNameHash` **1**، `lastEditStanzaId` **2**)، `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (بايتات مُكرَّرة، تجزئات الخيار) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**، `encPayload` **2**، `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 غير معروف، 1 going، 2 not going، 3 maybe)، `timestampMs` **2**، `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**، `encPayload` **2**، `encIv` **3** | `Message` كاملة (نص التعليق)؛ شكل النص الصِّرف هو `commentMessage` **77** (`DQV`: `message` **1**، `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**، `encPayload` **2**، `encIv` **3**، `secretEncType` **4** | `Message` كاملة |
| `reactionMessage` **46** | `DSH` | شكل نص صِرف | تفاعل صِرف |
| `conditionalRevealMessage` **120** | لا ينطبق | ليس مخطط السرّ الخاص بالرسالة (القسم 14.1) | رسائل مجدولة |

`SecretEncType` (`E2Q`): `UNKNOWN` 0، `EVENT_EDIT` **1**، `MESSAGE_EDIT` **2**، `POLL_EDIT` **4**، `POLL_ADD_OPTION` **5**. القيمة 3 غير موجودة في هذا البناء (`forNumber(3)` تُعيد null، تُعامَل كغير معروفة وتُرفَض).

`MessageKey` (`BD5`): `remoteJid` **1**، `fromMe` **2**، `id` **3**، `participant` **4**.

---

## 6. جانب المُرسِل

### 6.1 المسار المشترَك (found، `C33285Eeb.A03`)

1. حل FMessage الهدف بالمفتاح (`target message not found. Cannot proceed further` ← خطأ 71).
2. قراءة سرّه من `message_secret`؛ فارغ أو طوله != 32 ← `message secret missing or invalid` (66).
3. المفتاح الأصلي عبر `C43661qB.A03` (فارغ ← خطأ 0). مُرسِل الهدف عبر `C12300aw.A01`.
4. في دردشة فردية (`C0DZ.A0k(chat)`) يُحوَّل مُرسِل الهدف إلى فضاء أسماء المُعدِّل: LID المُعدِّل وPN الهدف ← يُخطَّط PN الهدف إلى LID؛ PN المُعدِّل وLID الهدف ← يُخطَّط LID الهدف إلى PN. في المجموعات لا تحويل.
5. استجابة الفعالية فقط: العلم **15791**، دردشة فردية ومُعدِّل من نوع حساب ← يُحوَّل المُعدِّل إلى PN.
6. IV عشوائي بطول 12 بايت، استخلاص المفتاح (3.1)، AES-GCM بـAAD حالة الاستخدام.
7. بناء `MessageKey` الخارجي من مُرسِل الهدف والمفتاح الأصلي (`C32717EOy.A01`)؛ يحمل الناقل `targetMessageKey`، `encIv`، `encPayload`.

### 6.2 لكل ناقل (found)

| الناقل | البوّابة عند الإرسال |
|---------|--------------|
| التفاعل (`DU8.ADr`) | يُشفَّر **فقط** إذا كانت الدردشة مجموعة (`C0DZ.A0l`) بـ`group_type == 3` (`C0GQ.A0A`؛ تُضبَط في `CMP` من `isDefaultSubgroup_`، أي مجموعة فرعية افتراضية ضمن مجتمع، التفسير مستنتج) وعلم سياق التسلسل `A09` خاطئ. في أي دردشة أخرى تُرسَل `reactionMessage` الصِّرفة. يُمحى `ReactionMessage.key` قبل التشفير (ينتقل المفتاح إلى `targetMessageKey` الخارجي) |
| تصويت الاستطلاع (`DUA.ADr`) | العلم **6772** مُفعَّل: مساعد مشترَك، يُشفَّر دائماً؛ مُعطَّل: فرع مضمَّن قديم بنفس الاستخلاص وAAD (مُرسِل الهدف = LID الخاص لاستطلاعاته هو، وإلا JID المُستخلَص من مفتاح هدف التصويت؛ المُعدِّل = LID الخاص). تُختَم `metadata` (`pollNameHash`، `lastEditStanzaId` اختياري) عندما يكون العلم **31593** مُفعَّلاً |
| استجابة الفعالية (`DU9.ADr`) | تُشفَّر دائماً؛ `EventResponseMessage` الصِّرفة تحمل `response`، `timestampMs`، `extraGuestCount` |
| التعليق (`F3W.ADr`) | يُشفَّر دائماً؛ النص الصِّرف هو كل `Message` التعليق؛ الهدف هو مفتاح `CommentMessageInfo` الأم |
| تحرير مشفَّر بسرّ (`F3Y.C5S`) | فقط عندما تحمل الرسالة معلومات تحرير من نوع `E2Q` وسياق التسلسل ليس مُعاد توجيهه/يتيماً؛ `MESSAGE_EDIT` تحتاج إضافة إلى ذلك العلم **17811** (وإلا تطرح `getUseCase`). لتحريرات الرسائل الخاصة يُظهر سطرا سجل (`sending the Message Yourself edit unwrapped`، `sending the agent reply edit unwrapped`) حالات تُرسَل كتحريرات صِرفة؛ الشرط الكامل (الأعلام **37948**، **35457**) فُقد في فك التجميع |

تُرفَض الحمولات المشفَّرة بسرّ المتداخلة على كلا الجانبين (`nested_secret_encrypted_message`).

---

## 7. جانب المستقبل

### 7.1 فك التشفير (found، `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (المُعدِّل) لكل ناقل: LID الخاص عندما يكون الغلاف من نفسي؛ استطلاع: JID المُرسِل (`c0df` أو `B4g()`)؛ استجابة فعالية: مستخدم الدردشة في 1:1 وإلا مستخدم الغلاف؛ التعليق: LID فقط (`C0DZ.A0Y`: الأنواع 18، 19، 25)، مُرسِل PN يفشل برمز خطأ 0؛ التفاعل: مُرسِل الغلاف فقط إذا كان LID، وإلا فارغ.

### 7.2 إعادة محاولة هوية LID/PN (البنية مُعثور عليها، الذيل مستنتج)

تستخدم المحاولة الأولى JIDs كما وردت. عند الفشل يُخطِّط المساعد كلا JID إلى فضاء الاسم الآخر (`C0YH.A0I` LID←PN، `A0F` PN←LID) ويعيد المحاولة مرة واحدة؛ إذا كان كلاهما أصلاً LID أو التخطيط غائب تكون النتيجة خطأ **51** (فشل فك التشفير). ذيل إعادة المحاولة المُفكَّك مفقود جزئياً، فمجموعة الزوجين المُجرَّبين الدقيقة مستنتجة. الفحص هو مصادقة GCM: زوج خاطئ يفشل، الزوج الصحيح يفكّ التشفير.

### 7.3 الأصل غائب: الأيتام (found)

| الناقل | السلوك عندما يكون الأصل غير مُعثور عليه أو عنصراً نائباً |
|---------|-----------------------------------------------------------|
| التفاعل | تُخزَّن FMessage من النوع **56** ببايتات `Message` الخام (`DdA(key, 56, ts).A02`)؛ يُؤجَّل فك التشفير |
| تصويت الاستطلاع | `C30957Dd6.A02 = Message.toByteArray()`؛ يُخزَّن غير مفكوك التشفير |
| استجابة الفعالية | `Dd7(key, target, bytes, ts)` يُخزَّن غير مفكوك التشفير |
| التعليق | عنصر نائب `C34671Zb` بمفتاح الأصل وصف `-1` |
| تحرير مشفَّر بسرّ | `DeD(MessageOrphan)` بنوع يتيم **5**، سبب **1** (الأصل غائب) أو **2** (عنصر نائب) |

يُتوقَّع إعادة التشغيل عندما يصل الأصل (تُحفَظ الأيتام بالبايتات الخام) لكن مُحفِّز إعادة التشغيل لم يُتعقَّب (مستنتج).

### 7.4 التحقق بعد فك التشفير (found)

| الحالة | الفحص | الفشل |
|------|-------|---------|
| stanza `type=poll` + `<meta polltype="edit">` | يجب أن يكون `secretEncType` هو `POLL_EDIT` | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | النوع `POLL_ADD_OPTION` وحقل stanza ثانٍ يساوي `poll_add_option` (الحقل غير محسوم) | `poll_add_option_stanza_invalid` (76) |
| تحرير الفعالية | نوع الرسالة الداخلية 92، المفتاح الناتج يساوي المفتاح الخارجي | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| تحرير الاستطلاع | النوع الداخلي 66، الرسالتان استطلاعان، نفس وقت الانتهاء والأعلام، تحريرات الخيار متسقة مع الخيارات المخزَّنة، الطابع الزمني ليس بعد وقت الانتهاء | `poll_edit_invalid_edits`، `poll_edit_invalid_option_edits`، `poll_edit_invalid_time` |
| إضافة خيار الاستطلاع | النوع الداخلي 137، الأصل استطلاع، مفتاح الهدف يساوي المفتاح الخارجي، ليس بعد وقت الانتهاء | `poll_add_option_past_end_time` |
| استلام تحرير الاستطلاع | يجب أن يكون علم AB عددي **24886** غير صفري | خطأ 10016 ("futureproofing") |
| استلام إضافة خيار الاستطلاع | يجب أن يكون AB **25758** غير صفري | خطأ 10017 |
| تصويت الاستطلاع | يجب أن يكون الاختيار صالحاً للاستطلاع (`AbstractC33199EdC.A02`)؛ طابع زمني التصويت ليس بعد وقت انتهاء الاستطلاع | `poll_update_past_end_time`، `invalid poll vote selection` |
| بيانات تعريف تصويت الاستطلاع | يُفحَص `pollNameHash` + `lastEditStanzaId` مقابل الاستطلاع المخزَّن (`C32977EZa.A01`)؛ "unstamped" عند الغياب؛ عدم التطابق يُسقِط التصويت | `poll_update_tc_drop` |
| شكل تصويت الاستطلاع | IV بالضبط 12 (`poll_update_invalid_vote_enc_iv`)، الحمولة حاضرة، طابع زمني المُرسِل حاضر | خطأ 11 |
| استجابة الفعالية | المفتاح، IV (12)، الحمولة حاضرة؛ يجب أن يكون الأصل رسالة فعالية أو رسالة إبطال مُرسِل | `parent message is not event message nor sender revoke` |

---

## 8. ربط المُرسِل/الهدف

| مُقيَّد بواسطة المفتاح | الأثر |
|------------------|------|
| معرّف الرسالة الأصلي | لا يمكن إعادة استخدام نص تشفير على رسالة أخرى |
| JID مُرسِل الهدف | لا يمكن إسناده لمؤلِّف أصلي مختلف |
| JID المُعدِّل | لا يمكن إعادة تشغيله كإضافة مستخدم آخر |
| سلسلة حالة الاستخدام | لا يفكّ نص تشفير تفاعل كتصويت، تعليق، أو تحرير |
| AAD (تصويت استطلاع، استجابة فعالية) | يربط إضافة إلى ذلك `targetId` والمُعدِّل في الوسم |

غير مُقيَّد: JID الدردشة، الطابع الزمني، موضع نص التشفير في الخيط، عدد الإضافات السابقة. غلاف `participant` / `from` هو ما يستخدمه المستقبل كمُعدِّل؛ يُصادَق عليه بواسطة جلسة E2E، لا بواسطة السرّ. أي شخص يحمل السرّ الأصلي (كل مشارك استقبل الرسالة الأصلية، في مجموعة) يستطيع استخلاص مفاتيح لأي مُعدِّل؛ المخطط يمنع إعادة التوجيه من جانب الترحيل، لا التنكُّر بواسطة أعضاء المجموعة (مستنتج من البناء).

---

## 9. الحلول البديلة لغياب السرّ (found إلا إذا أُشير إلى غيره)

| الحالة | المُرسِل | المستقبل |
|-----------|--------|----------|
| الأصل بلا سرّ | يفشل التشفير (66)؛ مسار الاستطلاع القديم: `invalid message_secret secretSize` | الأصل حاضر، السرّ فارغ: خطأ **66**، يُسجَّل لمُقرِّر الخطأ بـ`parentMsgRowId`، `parentType`، `parentHasSecret`؛ رمز `wam_message_secret_errors` 0 |
| السرّ ليس 32 بايت | يُرفَض التشفير | خطأ **67**، رمز WAM 1 |
| الأصل غير مُعثور عليه | خطأ تشفير 71 | يُخزَّن كيتيم (7.3) |
| تفاعل في دردشة ليست مجموعة فرعية افتراضية | تُرسَل `reactionMessage` صِرفة بدلاً من ذلك (لا سرّ لازم) | يُعالَج بالفرع الصِّرف |
| تحرير رسالة دون العلم 17811 | تطرح `getUseCase` (`unknown message secret encrypted type`، الرمز 0)؛ ما إذا كان المُرسِل يتجنب النوع عندما يكون العلم مُعطَّلاً غير محسوم | نفس الطرح |
| فشل فك تشفير الإضافة | لا ينطبق | تبقى الإضافة مخفية/غير متاحة؛ لا نص حل بديل ظاهر مُعثور عليه (غير معروف) |
| رفيق جديد دون الأصل | لا ينطبق | تحمل مزامنة التاريخ السرّ في `WebMessageInfo.messageSecret` (2.4) |
| `<enc decrypt-fail="hide">` | تُضبَط على رسائل تحمل معلومات تحرير (12.3) | تُخبر المستقبل بعدم إظهار عنصر نائب للفشل؛ مُستهلِك العلم غير محسوم |

---

## 10. stanza من نوع `<message>`: ما يضيفه العميل

تُبنى العناصر الفرعية الخارجة بمساهمين مستقلين (`InterfaceC35538FaZ`) تُلحِق ببانى stanza `C33150EcP`.

### 10.1 السمات (found)

| السمة | المُنتِج/المُستهلِك | القيم/المعنى |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`، `media`، `reaction`، `poll`، `event`، `pay`، `medianotify`، `scheduled-call` (من البروتو): `secretEncryptedMessage` بـ`EVENT_EDIT` ← `event`، بـ`POLL_EDIT` / `POLL_ADD_OPTION` ← `poll`؛ `MESSAGE_EDIT` تسقط إلى `text` / `media`؛ حقول التفاعل (صِرفة أو مشفَّرة) ← `reaction`؛ تحديث/إنشاء استطلاع ← `poll`؛ `encEventResponseMessage` وفعالية ← `event` |
| `edit` | مخططات الاستلام `C33474Ehg` (تتطلب وسم عقدة `status`؛ علاقتها بـstanza `<message>` الصِّرفة غير محسومة)، `C23206A1f` (نشرة)؛ إقرارات `AbstractC33465EhX.A05` | `1`، `7`، `8` في `C33474Ehg`؛ `3` و`8` في مخطط النشرة؛ الإقرارات تُصدِّيها إلا `0`/فارغة؛ انظر 10.2 |
| `category` | stanza، الإقرارات، إيصالات إعادة المحاولة | `peer` يختار مسار رسالة النظير |
| `device_fanout` | `F6M` | `"false"` على إعادة محاولات فردية مُستهدَفة |
| `addressing_mode`، `participant`، `recipient`، `expiration`، `offline`، `dhash`، `sts` | النقل | الهوية/دورة الحياة، لا المحتوى |
| `peer_recipient_pn`، `peer_recipient_lid`، `peer_recipient_username`، `recipient_latest_lid`، `participant_username`، `sender_account_kind`، `sender_country_code`، `eph_setting` | مُحلِّلات الهوية (`AbstractC33466EhY`، `C34763F6g`) | أسماء بديلة PN/LID/اسم مستخدم |

### 10.2 قيم `edit`

| القيمة | السياق | المستوى |
|-------|---------|------|
| `1` | تحرير رسالة مُرسَلة (يُحلَّل في `C33474Ehg.A0L`) | found |
| `2` | تثبيت في الدردشة: مسار الاستلام يتطلب نسخة تحرير داخلية 2 (`Invalid edited version`) | تخطيط مستنتج للسمة |
| `3` | تحرير رسالة نشرة: يُحلَّل فقط في مخطط النشرة (`C23206A1f.A0G`)، و`EWW.A01` تضبط نسخة تحرير 3 عندما تكون الدردشة نشرة (نوع JID 21، الخادم `newsletter`) | found (هذا يحل "unknown 3" السابق) |
| `7` | إبطال من جانب المُرسِل (`C33474Ehg.A0M`) | found |
| `8` | حذف المشرف (`C33474Ehg.A0S`، مخطط النشرة `A0H`) | found |
| `0`/فارغة | رسالة عادية؛ تُحذَف من الإقرارات | found |

نسخة التحرير الداخلية (`EWW.A01`) هي `1` للدردشات العادية و`3` للنشرات؛ تحريرات الدردشة العادية تضبط أيضاً علم إخفاء `decrypt-fail` (12.3).

### 10.3 العناصر الفرعية المباشرة (found)

| العنصر الفرعي | المُنتِج | المعنى |
|-------|----------|------|
| `enc` | طبقة التشفير | نص التشفير، انظر القسم 11 |
| `participants` / `to` | `F6E` ونشر التوزيع | نصوص تشفير لكل جهاز |
| `device-identity` | `F6B` | هوية جهاز موقَّعة |
| `registration` | المُحلِّل `C33474Ehg.A04` | 4 بايتات بالضبط |
| `tctoken` | `F6I`، `AbstractC33466EhY.A01` | بحد أقصى علم AB عددي **20606** لكل stanza، مُفعَّل بـ**20605** |
| `cstoken` | `F6G` | رمز جهة اتصال بارد |
| `padding` | `F6H` | بايتات عشوائية، طول `retryCount × 1571`، الأعلام **8311**، **9209** (`ta_pad` موجود أيضاً) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (HMAC بطول 16 بايت)، انظر [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | القسم 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`، `TRANSACTIONAL`، `NON_TRANSACTIONAL`، `OTHER`؛ `tag`: `AUTHENTICATION`، `UTILITY`، `MARKETING` |
| `biz` | معالِج الأعمال `C34748F5r` | 13.1 |
| `automated`، `multicast`، `url_text`، `url_number` | `F68` | عناصر علم فارغة من قناع بت في الباني: `2` url_text، `4` url_number، `64` multicast، `128` automated |
| `rcat` | المُحلِّل | فئة ثنائية غامضة (الحالة) |
| `cap` | `F69` | `<cap client_capping_ready="true|false">` على إرسالات إلى JID من النوع 3 (قائمة بث، مستنتج)، الأعلام **16656** (الإصدار) و**13537** (القيمة) |
| `verified_name` | الأعمال | شهادة تجارية موثَّقة |
| `unavailable`، `bypassed` | المُحلِّل | عناصر علامة؛ السلسلة الحرفية `unavailable` غير مُطابَقة في 2.26.41.6 (قائمة على ثابت)، الدلالات غير مؤكَّدة هنا |

---

## 11. عقدة `<enc>`

### 11.1 السمات (found، `AbstractC33466EhY.A09`)

| السمة | القيمة | الشرط |
|-----------|-------|-----------|
| `v` | `2` أو `3` | إصدار نص التشفير (مُحلِّل الاستلام يقبل `EncVersion2`، `EncVersion3`، تحوُّط مستقبلي) |
| `type` | `msg`، `pkmsg`، `skmsg`، `frskmsg`، `msmsg`، `none` | رسالة Signal، رسالة مفتاح مسبق، مفتاح مُرسِل، `frskmsg`، بوت `msmsg`، علامة نص صِرف |
| `count` | عدد إعادة المحاولة | يُحذَف عندما يكون 0 |
| `mediatype` | انظر 11.2 | تصنيف وسائط/تفاعلي |
| `native_flow_name` | اسم التدفق | رسائل التدفق الأصلي |
| `duration` | int >= 0 | الموقع المباشر |
| `decrypt-fail` | `hide` | رسالة موسومة قابلة للإخفاء (12.3) |
| `state` | `false` | إرسالات `pkmsg` تحت علم في ناقل نص التشفير |
| `session_type` | `pq` | علم ناقل جلسة ما بعد الكمّي |
| `bucket` | string | عندما يُضبَط على ناقل نص التشفير |

فحوصات الاستلام (`C33013EaB`): يجب أن تتفق عقدتا `<enc>` في رسالة واحدة على عدد إعادة المحاولة وإصدار نص التشفير؛ تُرفَض `enc` على نشرة (`Received enc message for newsletters`)؛ `decrypt-fail=hide` يُحترَم فقط عندما لا تكون الفئة `peer` ويكون مُسنَد الدردشة `C1ZB.A0L` خاطئاً.

### 11.2 قيم `mediatype` التي يقبلها المخطط (found، 37 إدخالاً)

`audio`، `avatar_sticker`، `buttons_response`، `cataloglink`، `collection`، `contact`، `contact_array`، `document`، `feed_reshare`، `genai_sticker`، `gif`، `group_history`، `history`، `image`، `instant_image`، `list_response`، `location`، `motion_photo`، `motion_video`، `music`، `native_flow_response`، `order`، `product`، `productlink`، `ptt`، `ptv`، `request_location`، `request_location_update`، `sticker`، `sticker_pack`، `story_reply`، `url`، `user_created_sticker`، `vcard`، `video`، `xma`، `1p_sticker`. تعداد `native_flow_name` (8 إدخالات): `a2ui_reply_action`، `account_authentication_request`، `address_message`، `api_signup`، `call_permission_request`، `form_message`، `galaxy_message`، `menu_options`. `sticker_type`: `avatar`.

---

## 12. عقدة `<meta>`

تُجمَّع كل السمات والعناصر الفرعية في `EZV` بواسطة المعالِجات التي تستدعيها `F6K` (لكل صنف رسالة `FXq.AAl`، لكل إضافة `FZH.AAl`) وتُصدَر كـ`<meta>` واحدة (`C33150EcP.A00`). مُجمِّع فارغ لا يُصدِر شيئاً.

### 12.1 مُصنِّفات العملية (found)

| السمة | القيم | المُنتِج |
|-----------|--------|----------|
| `polltype` | `creation`، `edit` (`F2N`)، `vote` (`DUA`)، `add_option` (`F2L`، `F4E`) | معالِجات الاستطلاع |
| `event_type` | `creation`، `edit` (`F2M`)، **`response`** (`DU9`) | معالِجات الفعالية |
| `content_type` | `add_on` لصنف الإضافة `AbstractC35181aQ` (يشمل التفاعلات؛ التصويتات/الاستجابات مستنتجة) في دردشات حيث `C0DZ.A0U` خاطئة؛ `status_notify` / `add_on` لإشعارات الحالة | `F6K` |
| `type` | `scheduled_message` بـ`st` (ثوانٍ، يُحذَف لصنف رسالة إلغاء الجدولة) وعنصر فرعي `<key rkid="...">` (بايتات المفتاح تُحذَف لذلك الصنف) | `F6K`، الكشف المشروط |
| `appdata` | سلسلة حرة من `FZF.AVN()`؛ تحرير appdata يُرفَض | `F6K` |
| `tag_reason` | `user_update`، `new_member`، `rereg_recovery_request`، `rereg_recovery_response`، `user_delete` | رسالة وسم العضو `F3F` |
| `context_source` | `channels_invitation`، `event_invitation` (وأخرى) | `AJR` |
| `message_association_type` | رمز الارتباط، إضافة إلى `hd_image_dual_upload`، `hevc_video_dual_upload`، `av1_video_dual_upload` على رفعات الحالة | `F4G`، `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`، `thread_msg_sender_jid` | معرّف/JID الأصل | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`، `allowlist`، `denylist`، `customlist`؛ `is_group_status` `true`؛ عنصر فرعي `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`، `group_status`، `general`، إضافة إلى سلاسل نقطة دخول Meta AI (`favicon`، `chat_list`، `nullstate_*`، `typeahead_*`، ...) | `F6K`، `EnumC14320eI`، `C198208bu` |
| `acp` | `2` للدردشات الفردية تحت العلم **36091** (المعنى غير محسوم) | `F6K` |
| `view_once` | `true` لأنواع المرة الواحدة تحت العلم **11282** | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (نوع الرسالة 108) | `F6K` |
| `share_pn` | `true` (نوع الرسالة 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`، `image`، `video`، `mixed` | `F6K` |
| `destination_id`، `conversation_thread_id`، `thread_origin`، `peripheral` | توجيه البوت/الخيط | `F6K` |

### 12.2 يُحلَّل عند الاستلام (found)

مُدخلات `<meta>` التي يقرؤها العميل: `polltype`، `event_type`، `target_id`، `target_sender_jid`، `target_chat_jid`، `target_chat_jid_lid`، `from`، `capi` (دردشات المجموعة فقط)، `thread_msg_id`، `message_association_type`، `status_mentioned`، `push_eligible`، `session_scope`، `content_type`، `tm_csat_exp_ts`، `tm_csat_cooldown` (ثوانٍ، تُخزَّن بالمللي ثانية)، `is_wamo_sub`، `original_msg_t`، `msg_edit_t`، والعناصر الفرعية `mention_source/to`، `mentioned_users/to`. تضيف بيانات meta الخاصة بالنشرة `admin_profile`، `paid_partnership`، `ai_content` (مُدرَجة من الفهرس السابق؛ لم تُعَد قراءتها هنا، غير مؤكَّدة). `deprecated_lid_session` مؤكَّد غيابها منذ 2.26.45.10: بحث grep شامل غير حسّاس لحالة الأحرف عبر شجرة 2.26.45.10 المُفكَّكة كاملة وWA Business 2.26.45.7 لم يُعثر على أي تطابق دقيق أو قريب (`found`)؛ مستنتج أنها إزالة مقصودة لعلم ترحيل PN←LID الانتقالي، لا إعادة تسمية (`inferred`).

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

يقرأ المستقبل اسم التدفق (`native_flow_name` أو `name` المتداخل)، ثم يُصنِّف: `buttons` حاضر، `list` حاضر، أو تدفق أصلي؛ بوجود اسم وشقيق `hsm` يصبح قالباً. فشل التحقق يحمل الأسماء `InvalidTemplateMessage`، `InvalidListMessage`، `InvalidButtonMessage`، `InvalidInconsistentFlowName`، `InvalidFlowNotOwned`، `InvalidDeeplyNested`: مُصنِّف `biz` يتعارض مع الحمولة المشفَّرة فشل تحقق، لا نوع رسالة مختلف. سمات `biz` أخرى تُقرأ في مواضع أخرى: `campaign_id`، `notification_cta`، `privacy_mode_ts`، `host_storage`، `actual_actors`، `biz_bot`، العنصر الفرعي `quality_control` بـ`decision_source`.

### 13.2 `<bot>` (found)

الخارج (`F6M`): السمات `type` (`request_welcome`، `prompt`، `command`، `search`، `memu_onboarding`، `memu_invoke`، `voice`، `voice_background`، `text_input`، `live_ai`، `feedback`)، `client_thread_id`، `mode_selected`، `persona_type` (`1p`، `ugc`، `3p`)، `local_automated_type` (`1p_partial`)، `agent_engagement_type`، `is_lid`، العنصر الفرعي `tee_routing` (`tee_routing_token`، `tee_ik_id`). الوارد (`C34747F5q`): `<bot edit="full|...">` الافتراضي `full`، `edit_target_id`، `sender_timestamp_ms`، `type`، `client_thread_id`؛ دون `<meta target_id>` لا تُعالَج الرسالة كاستجابة بوت. التفاصيل: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. مخططات ذات صلة ليست سرّ الرسالة

### 14.1 الكشف المشروط (الرسائل المجدولة)

تستخدم `conditionalRevealMessage` (الحقل **120**) مفتاح كشف عشوائي منفصل (`<meta type="scheduled_message" st><key rkid>`)؛ يتحكم الخادم في الكشف. لا HKDF من `messageSecret`. داخليات بروتوكول الكشف لم تُتعقَّب (غير معروف).

### 14.2 رمز الإبلاغ

يستخدم `reportingTokenVersion` (الحقل **8**) و`<reporting_token>` بطول 16 بايت مفتاح معرّف حالة الاستخدام الأصلي 5 (3.4)، لا HKDF في Java. محتوى الرمز: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. فاحص دعم الرفيق (found)

`CompanionSupportVerifier` (`C34757F6a`، فقط على رفيق، خلف علم): تُقبَل الرسائل غير `peer` فقط إذا كان `type` في `{text, media, reaction, poll, event}` (أو `pay` بعنصر فرعي حوالة `transaction` / `pay`) وكان كل عنصر فرعي مباشر في `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}`. وإلا تُسجِّل `unsupported child node=` / `unsupported message type=` وتُصنَّف الرسالة غير مدعومة على الرفيق. بث نظير بـ`participants` على رفيق يُسقَط (`received peer broadcast message on companion-mode, dropping`، nack 415 / 18). العنصر الفرعي الجديد `cap` و`tctoken` / `cstoken` ليسا في القائمة؛ أين يُعالَجان قبل هذا الفحص غير محسوم. `unavailable` و`participants` تمران بمساريهما الخاصين.

---

## 16. أعلام الميزات (المعرّفات كما تُقرأ في مواقع الاستدعاء؛ الأسماء غير محسومة)

| المعرّف | النوع | يتحكم في |
|----|------|----------|
| **6772** | bool | تصويت الاستطلاع: مساعد مشترَك مقابل تشفير مضمَّن قديم |
| **31593** | bool | ختم `metadata` تصويت الاستطلاع |
| **17811** | bool | حالة استخدام `Message Edit` (إرسال واستلام) |
| **37948**، **35457** | bool | شروط تغليف تحريرات الرسائل الخاصة |
| **24886** | int | استلام تحرير الاستطلاع (0 = رفض، 10016) |
| **25758** | int | استلام إضافة خيار الاستطلاع (0 = رفض، 10017) |
| **15791** | bool | مُعدِّل استجابة الفعالية LID ← PN في دردشات 1:1 |
| **3142**-**3146**، **2200**، **11104**، **19303** | bool | توليد السرّ بحسب صنف الدردشة |
| **8860** | int | أقصى نسخة رمز إبلاغ (توليد السرّ) |
| **24741** | bool | السرّ لنوع الرسالة 117 |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**، **13537** | bool | عنصر `cap` وقيمته |
| **8311**، **9209** | bool | الحشو |
| **20605**، **20606** | bool / int | تفعيل `tctoken` / الحد الأقصى لكل stanza |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17، قراءة المصدر، لا شيء مُختبَر)

حقائق مقروءة فقط في `src/Utils/process-message.js`، `src/Utils/reporting-utils.js`، `src/Utils/messages.js`، `src/Socket/messages-send.js`.

| الموضوع | Baileys | أندرويد |
|-------|---------|---------|
| المفتاح | `key0 = HMAC-SHA256(key = 0×32, secret)`؛ `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | مطابق (3.1) |
| حالات الاستخدام | `Poll Vote`، `Event Response`، `Enc Comment`، `Enc Reaction`، `Event Edit`، `Message Edit`، `Poll Edit`، `Poll Add Option`، إضافة إلى `Message Schedule` للقيمة 3 | نفس السلاسل؛ القيمة 3 غير مُعرَّفة في 2.26.41.6 |
| AAD | `id\0modifier` للاستطلاع والفعالية، فارغة للتحرير/التعليق/التفاعل | مطابق |
| الهوية | يجرِّب مرشَّحي PN وLID للمؤلِّف والمُعدِّل، يُصادِق GCM الزوج الصحيح | نفس الفكرة (7.2) |
| سرّ غائب | يسجِّل، يُصدِر تحديث `encReactionMessage` / `pollUpdateMessage` الخام، لا فك تشفير | يُخزَّن كيتيم |
| توليد السرّ | `randomBytes(32)` للاستطلاع، الفعالية وعندما يكون `messageContextInfo.messageSecret` غائباً | 2.2 |
| مفتاح الإبلاغ | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`؛ يُتخطَّى الإبلاغ للتفاعلات، `encReactionMessage`، `encEventResponseMessage`، `pollUpdateMessage` | معرّف أصلي 5 (3.4) |
| جانب الإرسال | لم يُعثر على مُرسِل لـ`pollUpdateMessage`، `encReactionMessage`، `encEventResponseMessage` أو `encCommentMessage` في الملفات المقروءة | أندرويد يرسل الأربعة كلها |

النتيجة المقروءة من الكود: يستطيع Baileys فك تشفير متابعات يستقبلها لكن الملفات المقروءة لا تحتوي تشفيراً لها. ما إذا كان مساعد إرسال موجوداً في مكان آخر لم يُبحَث.

---

## 18. حالات الخطأ

| العرض | السبب | الحل |
|---------|-------|-----|
| خطأ 11 | IV ليس 12 بايت أو حمولة فارغة/حقل غائب | فحص `encIv` (الحقل 3، أو 2 لـ`PollEncValue`) |
| خطأ 51 | فضاء اسم JID مُرسِل/هدف خاطئ (PN مقابل LID)، معرّف أصلي خاطئ | إعادة محاولة كلا الفضاءين، استخدام معرّف الرسالة الأصلي (غير المُحرَّر) |
| تصويت لاستطلاع مُحرَّر يفشل | يجب أن يكون معرّف المفتاح معرّف الاستطلاع الأصلي، لا معرّف آخر تحرير | حل المفتاح الأصلي |
| تعليق من مُرسِل PN يفشل | فك تشفير التعليق يتطلب مُرسِل LID | استخدام LID |
| تحرير/إضافة خيار استطلاع مرفوضة | الأعلام **24886** / **25758** مُعطَّلة، أو `polltype` في stanza يتعارض مع `secretEncType` | إرسال `<meta polltype>` والنوع المطابقين |
| رسالة مُتجاهَلة على رفيق | عنصر فرعي أو `type` غير معروف | الالتزام بقائمة السماح (القسم 15) |
| رسالة `<biz>` غير مدعومة | المُصنِّف يتعارض مع الحمولة | استخلاص المُصنِّف من الحمولة |

---

## 19. فروق أساسية

| هذا | لا هذا |
|------|----------|
| `messageSecret` (لكل رسالة، عشوائي، 32 بايت) | مفتاح الوسائط، مفتاح المُرسِل، مفتاح مزامنة حالة التطبيق، مفتاح المكالمة |
| مفتاح حالة الاستخدام (HKDF، لكل هدف/مستخدم/حالة استخدام) | السرّ نفسه |
| `secretEncryptedMessage` (تُغلِّف `Message` كاملة) | `encReactionMessage` (تُغلِّف `ReactionMessage`) |
| AAD لـ`Poll Vote` / `Event Response` = المعرّف + NUL + المُعدِّل | تحرير/تعليق/تفاعل بـAAD فارغة |
| `targetMessageKey` في الناقل الخارجي | `ReactionMessage.key` داخل النص الصِّرف (يُمحى عند الإرسال) |
| `meta polltype` / `event_type` (المُصنِّف) | الحمولة المشفَّرة (المحتوى) |
| سمة stanza `edit` | `secretEncType` (حالة استخدام التشفير) |
| `decrypt-fail="hide"` على `<enc>` | إيصال إعادة المحاولة / عقدة `retry` |

---

## 20. التدفق الكامل (تصويت استطلاع، فردي أو مجموعة)

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

## 21. المجاهيل

| العنصر | الحالة |
|------|-------|
| المُسندات الدقيقة لـ`EZN.A01`، `C35201aS.A00`، الأعلام 3142-3146 | ضبط لكل صنف دردشة مرصود، المجموعة الظاهرة للمستخدم غير محسومة |
| جدول معرّفات حالة الاستخدام الأصلي (الأسماء إلى المعرّفات بما يتجاوز 5 = Report Token) | لم يُقرأ |
| موضع وسم GCM وحجم مفتاح AES | مستنتج من الثوابت وBaileys |
| الشرط الكامل لإرسال تحريرات `MESSAGE_EDIT` الخاصة مُغلَّفة مقابل صِرفة (الأعلام 37948، 35457) | فقد المُفكِّك مسار التحكم |
| معنى `acp="2"`، علم التسلسل `A09`، حقل stanza ثانٍ لإضافة خيار الاستطلاع | غير محسوم |
| مُستهلِك `decrypt-fail="hide"` على الغلاف المُحلَّل | العلم محمول في الغلاف، الأثر لم يُتعقَّب |
| النتيجة الظاهرة للمستخدم لإضافة لا يمكن فك تشفيرها دائماً | لا نص حل بديل مُعثور عليه |
| `unavailable`، `bypassed` | لم تُعَد التحقق منها في 2.26.41.6 |
| `deprecated_lid_session` | مؤكَّد غيابها منذ 2.26.45.10 (بحث grep شامل، شجرتا WhatsApp وWA Business)؛ الإزالة مقابل إعادة التسمية `inferred`، غير مُثبَتة |
