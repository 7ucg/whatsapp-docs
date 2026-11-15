<!-- src-sha1: 6458e557973884f0b2c8c175f4607447365f03a6 -->
# WhatsApp ربط الأجهزة المرتبطة — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** جانب الجهاز الأساسي في ربط الرفيق، تدفق QR، تدفق رقم الهاتف/رمز الربط، stanzas من نوع `pair-device` و`pair-success`، مادة المفتاح، هوية الجهاز الموقَّعة ADV وقائمة فهرس المفتاح، قائمة الأجهزة وحدودها، فكّ الربط، الأخطاء، مقارنة Baileys

---

## 1. ما هو (تقنياً)

الجهاز المرتبط (الرفيق) هو نقطة نهاية ثانية لنفس الحساب. يُصرِّح الهاتف الأساسي به بإنتاج هوية موقَّعة ADV (التحقق من جهاز الحساب) على مفتاح هوية الرفيق. كل العبارات تحليل ساكن للـAPK المفكَّك؛ لم يُلتقط شيء على السلك. المستوى: **found** = مقروء في الكود، **inferred** = مُستنتَج من الكود، **unknown** = غير محسوم.

الأسماء المُشوَّشة خاصة بكل بناء وأُعيد حلّها من سلاسل ثابتة في 2.26.41.6.

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| منسِّق QR/الربط | `C45850K0w` (بادئة السجل `CompanionDeviceQrHandler`) | يُحلِّل QR، يبني بروتوهات ADV، يرسل `pair-device` |
| باني IQ لـ`pair-device` | `RunnableC46606KYf` | يبني IQ |
| مساعد طلب/استجابة `pair-device` | `KRI` (`devicePairRequest/*`) | الإرسال، إعادة المحاولة، تحليل `device` / `companion-props` / إشارات إعادة المحاولة |
| موزِّع الخطأ | `C44661Jem` | يُخطِّط رمز خطأ الخادم إلى رد نداء الواجهة |
| مُحلِّل سلسلة QR | `C45741Jxy` → `C45423Jrn` | حمولة QR إلى بيانات الربط |
| بيانات الربط المُحلَّلة | `C44423JaU` | المرجع، مفاتيح الرفيق، سرّ adv، المنصة |
| أداة ADV | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId، فهرس المفتاح، الطابع الزمني، بناء وتوقيع قائمة فهرس المفتاح |
| مُحدِّث قائمة فهرس المفتاح | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | يدفع القائمة الموقَّعة للخادم |
| مُحقِّق ADV | `C24230w2` (`DeviceADVInfoHandler`) | يحقِّق الهويات والقوائم المرصودة على السلك |
| معالِج إشعار قائمة الأجهزة | صنف مجهول في `C1S0` (`DeviceUpdateNotificationHandler`)، `RunnableC29334CoL` | إشعار `devices` |
| معالِج إشعار رمز الربط | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | معرّف إشعار 252 |
| مدير رمز الربط (الأساسي) | `KZ3` (الرمز المُدخَل، `primary_hello`)، `KYB` (`companion_finish`)، `C10L`، `C77` | تدفق رمز الربط |
| أداة تشفير رمز الربط | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF، PBKDF2، base32 |
| مدير الجهاز | `C0XQ` (`companion-device-manager`) | القائمة، تسجيل الخروج |
| مساعد الإزالة | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| غلاف منحنى Signal | `C38851hm` | مزوِّد `org.whispersystems.curve25519` "best" |
| أصناف بروتو ADV | `C25815BBy`، `C25792BBb`، `C25785BAt`، `C25786BAu`، `BCB` | انظر القسم 5 |
| DeviceProps | `C43105IrG` (تعداد `EnumC25120ArW`) | `companion-props` في نتيجة `pair-device` |
| خصائص العميل | `C43107IrI` | العنصر الفرعي `client-props` |
| نوع الحساب/التشفير | `EnumC32116E1o` | `E2EE` 0، `HOSTED` 1، `NON_E2EE` 2 |

توجد ثلاثة أوضاع دخول في واجهة الأساسي (`EnumC26221BZl`): `QR_CODE`، `PHONE_NUMBER_AND_CODE`، `EXTERNAL_DEEPLINK_QR_CODE` (found).

يحمل نفس APK أيضاً كود تسجيل دور الرفيق (آلة حالة `C0YS`، سجلات `companion/registration/*`). خارج النطاق؛ تُوصَف فقط الأجزاء اللازمة لشرح ما يستقبله الأساسي (القسم 9.6).

---

## 2. تدفقات الربط بنظرة سريعة

| التدفق | المُحفِّز على الأساسي | يرسل الأساسي | السرّ الذي يربط الأساسي والرفيق |
|------|--------------------|---------------|----------------------------------------|
| QR | مسح `https://wa.me/settings/linked_devices#<payload>` (أو `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` `pair-device` | `adv secret` من حقل QR رقم 4 |
| رقم الهاتف + رمز | `notification` `link_code_companion_reg` بمرحلة `companion_hello`، يكتب المستخدم رمزاً من 8 أحرف | `primary_hello`، ثم (بعد `companion_finish`) نفس `pair-device` | `adv secret` مُستخلَص من نتيجتي X25519 إضافة إلى عشوائي (القسم 4.4) |

يتقاطع كلا التدفقين على جسم `C44423JaU` واحد وIQ `pair-device` واحدة (found: تبني `KYB` جسم `C44423JaU` من حزمة `companion_finish` بنفس الباني `C45850K0w.A01` المُستخدَم لـQR).

---

## 3. تدفق QR (جانب الأساسي)

### 3.1 حمولة QR

يحذف `C45741Jxy.A01` البادئة `https://wa.me/settings/linked_devices#` أو `whatsapp://settings/linked_devices#` ويفكّ ترميز URL للباقي. تُقسِّم `A02` على `,` (found):

| الفهرس | المحتوى | الترميز | الاستخدام |
|-----|---------|----------|-----|
| 0 | `ref` | سلسلة | مرجع الربط؛ مرجع يبدأ بـ`CAPI_` يُرفَض (`invalid ref`) |
| 1 | مفتاح عام للرفيق | base64 | يُرسَل كـ`pub-key`، ملح لمفتاح النونس (3.4). الاسم مستنتج: مفتاح Noise ثابت (`companion_server_auth_key_pub` في مسار الكود) |
| 2 | مفتاح هوية الرفيق | base64، 32 بايت، يُسبِق المُحلِّل `0x05` (نوع Curve25519) | يُوقَّع عليه بتوقيع الحساب |
| 3 | `adv secret` | base64 | مفتاح HMAC لغلاف ADV |
| 4 | رمز المنصة (اختياري) | حرف واحد | يُخطَّط إلى نوع منصة؛ `j` = جهاز مُستضاف |

- أقل من 3 أجزاء: `qrData/processQR/error/invalid_code parts`. مفتاح هوية أو سرّ adv غائب (QR قديم بثلاثة حقول): `invalid qr code, missing companion identity key or adv secret` ← رمز محلي **-9**.
- جدول حرف المنصة (مستقل عن `EnumC26221BZl`، `EnumC26332BbY`): `0` UNKNOWN، `1` CHROME، `2` EDGE، `3` FIREFOX، `4` IE، `5` OPERA، `6` SAFARI، `7` DESKTOP، `8` UWP، `9` OTHER_WEB، `a` IOS_TABLET، `b` IOS_PHONE، `c` IOS_CATALYST، `d` ANDROID_TABLET، `e` ANDROID_PHONE، `f` ANDROID_AMBIGUOUS، `g` WEAR_OS، `i` AR_DEVICE، `j` HOSTED_DEVICE، `k` VR، `l` SMARTGLASSES، `n` WAIL_WAI، `o` WAIL_ALEXA (found). يُستخدَم فقط لفحص الاستضافة والتسجيل (3.2).

### 3.2 فحوصات محلية قبل إرسال أي شيء

| الفحص | الكود | الرمز المحلي |
|-------|------|------------|
| QR يحمل مفتاح هوية وسرّ adv | `C45850K0w.A01` | -9 |
| علم الاستضافة متسق: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| ربط آخر قيد التشغيل أصلاً (`kri.A0N`، أو مدير جهاز الرفيق مشغول) | `A04` | -17 |
| طابع زمني ADV محلي صالح (`C24270w6.A00() != -1`) | `A04` | -8 |
| رفيق مُستضاف | `A04`: `Hosted pairing is not supported` | -10 |
| احتكاك وضع الدفاع لازم | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (إعادة محاولة مع تحديات) |

ربط الاستضافة محجوب من جانب العميل في هذا البناء (`pairing for hosted device is not supported on the consumer build`).

### 3.3 قبل IQ: تنظيف syncd وفهرس المفتاح

1. إذا كانت حالة syncd متسخة (`sync-manager/shouldCleanUpSyncdOnPairing`)، يُنظِّف التطبيق أولاً syncd، ثم يستمر (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (في `RunnableC46617KYr`):
   - لا rawId أو فهرس مخزَّن: rawId عشوائي جديد، الفهرس 1؛
   - لا رفقاء مرتبطون: `rawId + 1`، الفهرس يبقى 1؛
   - رفقاء موجودون: `currentIndex + 1`؛ عند الفائض rawId + 1 وتُسجَّل خروج كل الأجهزة (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (القسم 5.4).

### 3.4 ما يُبنى

في `C45850K0w.A00`، بـ`E` = مفتاح هوية الرفيق (32 بايت، خام)، `P` = زوج مفتاح هوية الأساسي (Curve25519)، `S` = سرّ adv:

| الخطوة | العملية | المستوى |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | توقيع الحساب = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`؛ البادئة `06 00` (مستضاف `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` تُترَك فارغة: يضيفها الرفيق) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = serialized step 3, hmac = HMAC-SHA256(key = S, data = step 3 bytes), accountType}`؛ للاستضافة البيانات هي `06 05 ‖ bytes` | found |
| 5 | `BCB` (ADVKeyIndexList) من `C24270w6.A01`، موقَّعة بـ`A02` ← `ADVSignedKeyIndexList` (5.3) | found |
| 6 | مفتاح نونس `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`، مُغلَّف كعنصر فرعي `pem` | found (الاستخلاص)؛ الغرض مستنتج |
| 7 | `encryption-metadata` اختياري (`C38898Gvq`): `encrypted_key`، `nonce`، `encrypted_data`، `auth_tag`، من `AuthProofHelper` (تشفير كلمة مرور الحساب، تسمية `rsa2048`) | found (البنية)؛ ما تُثبته غير معروف |
| 8 | `client-props` اختياري (`C43107IrI`، القسم 3.6) | found |

تفصيل الخطوة 6: عنصر `pem` موسوم `version=1`، `algorithm=rsa2048`، `ttl ts_s = 5 days`، `key_id=1`، لكن عنصره الفرعي يحمل `key.getEncoded()` لمخرج HKDF بطول 32 بايت (خوارزمية `SecretKeySpec` من نوع `AES-GCM`). التسمية والمحتوى لا يتطابقان؛ السبب غير معروف. الاستخدام من جهة الخادم مستنتج (يشفِّر الخادم نونس خاصاً بالجهاز للرفيق؛ قارن عمود `companion_meta_nonce`).

### 3.5 IQ من نوع `pair-device` (الأساسي ← الخادم)

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <pair-device>
    <ref>…</ref>                                    <!-- QR field 0 -->
    <pub-key>…</pub-key>                            <!-- QR field 1 -->
    <device-identity>ADVSignedDeviceIdentityHMAC</device-identity>
    <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
    <client-props>…</client-props>                  <!-- optional -->
    <pem version="1" algorithm="rsa2048"><pem>…</pem><ttl ts_s="432000"/><key_id>1</key_id></pem>
    <encryption-metadata version="1" algorithm="rsa2048">…</encryption-metadata>   <!-- optional -->
    <companion_qr_origin_source>1|2</companion_qr_origin_source>
    <challenges><supported><friction variant="1"/><passkey-create/></supported>
                <completed>…</completed></challenges>                              <!-- optional -->
  </pair-device>
</iq>
```

مُعثور عليه: كل أسماء العناصر الفرعية، قيمة سمة `ts` (طابع زمني قائمة فهرس المفتاح)، مهلة **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source` هي `1` لقيمة إدخال 3 و`2` لقيمة إدخال 5 (معنى أعداد الإدخال غير معروف). ترتيب العناصر الفرعية الدقيق وفرع `companion_qr_origin_source` مُشوَّشان جزئياً بواسطة المُفكِّك؛ عامل الترتيب كغير مؤكَّد.

### 3.6 `client-props` (`C43107IrI`)

| الحقل | الرقم | النوع | يُضبَط عندما |
|-------|--------|------|----------|
| `isChatDbLidMigrated` | **1** | bool | ترحيل LID لقاعدة بيانات الدردشة اكتمل |
| `isSyncdPureLidSession` | **2** | bool | علم syncd LID الصِّرف حاضر |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | علم الاسترداد |
| `isHsThumbnailSyncEnabled` | **4** | bool | علم مزامنة الصورة المصغَّرة لمزامنة التاريخ |
| `subscriptionSyncPayload` | **5** | bytes | يُبنى عندما تكون مزامنة md مُفعَّلة (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | JID بوت لقاعدة البيانات مُرحَّل |

### 3.7 معالجة النتيجة (`KRI.CFS`)

عناصر نتيجة النجاح (found):

| العنصر الفرعي | الاستخدام |
|-------|-----|
| سمة `jid` في `device` | `DeviceJid` الرفيق الجديد؛ معرّف الجهاز **99** يُخطَّط إلى إدخال منصة الاستضافة |
| `companion-props` | بروتو `DeviceProps` (`C43105IrG`): `os` **1** (سلسلة)، `version` **2** (رسالة)، `platformType` **3** (تعداد)، `requireFullSync` **4** (منطقي)، `historySyncConfig` **5** (رسالة) |
| سمة `ts` في `retry-ts` | يطلب الخادم طابعاً زمنياً أحدث؛ يعيد التطبيق المحاولة (`RunnableC46585KXj`) |
| `retry-after-challenges` | عناصر فرعية `friction` (سمة `variant`، يجب أن تكون `1`، `location` "lat,lon" اختياري) أو `passkey-create` (سمة `created`) |
| `retry-with-method` | عناصر فرعية `qr-code` أو `shortcake-with-passkeys`؛ إذا وُجد الثاني يُخزَّن مفتاح التسليم بطول 32 بايت (HKDF لسرّ adv، المعلومات `shortcake-passkey-handoff-v1`) (`PairingHandoffKeyHolder`)، مضبوط بخاصية AB |

عند النجاح يخزِّن التطبيق سجل `CJY` (سلسلة base64 عشوائية بطول 24 بايت، `adv_key_index` = الفهرس الحالي، `requireFullSync`)، يحفظ طابع زمني قائمة فهرس المفتاح كـ`adv_timestamp_sec` (`C24270w6.A05`)، ويبدأ حالة مزامنة التاريخ (`C8N`).

فشل التسليم (`Bog`): حتى **3** إعادات محاولة، التأخير `3000 * 3^(n-1)` ms (3 ث، 9 ث، 27 ث) إذا كان علم إعادة المحاولة مُفعَّلاً (found)؛ ثم رد نداء الخطأ.

---

## 4. تدفق رقم الهاتف/رمز الربط (جانب الأساسي)

### 4.1 الخطوات

| # | الاتجاه | Stanza/إجراء | الصنف |
|---|-----------|-----------------|-------|
| 1 | الرفيق ← الخادم ← الأساسي | `notification` `link_code_companion_reg`، `stage=companion_hello` | `C10J` (المعرّف 252) |
| 2 | الأساسي | يخزِّن hello، يعرض إشعار دفع ← `CompanionHelloConfirmationActivity` / شاشة إدخال الرمز | `C10J`، `C77`، `JYJ` |
| 3 | المستخدم | يكتب الرمز من 8 أحرف | `LinkedDevicesEnterCodeActivity` |
| 4 | الأساسي ← الخادم | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (مهلة 120000 ms) |
| 5 | الخادم ← الأساسي | `notification` `stage=companion_finish` | `C10J` ← `KYB` الحالة 0 |
| 6 | الأساسي ← الخادم | IQ `pair-device` (القسم 3.5) | `C45850K0w` |
| 7 | مراحل أخرى | `refresh_code` (يطلب الأساسي تحديث الرمز، سمة `force_manual_refresh`) | `C10J` |

### 4.2 إشعار `companion_hello` (found)

| العنصر الفرعي | الاستخدام |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | مفتاح X25519 عابر للرفيق، مُغلَّف بالرمز (4.3) |
| `companion_server_auth_key_pub` | يصبح لاحقاً `pub-key` في `pair-device` |
| `link_code_pairing_ref` | مرجع الجلسة (سلسلة) |
| `companion_platform_id` | سلسلة معرّف المنصة |
| `companion_platform_display` | اسم العرض |
| سمة `should_show_push_notification` | `true` ← إشعار دفع |

الحالة المحفوظة (`C77`/`CE4`، تفضيلات مشترَكة بصيغة JSON `companion_reg_with_link_code_companion_hello_info_json`): المرجع، معرّف المنصة، المفتاح المُغلَّف، مفتاح مصادقة الخادم، انتهاء `now + min(360000, flag 3816 * 1000)` ms. hello منتهٍ أو غائب ← "companion hello is null or expired" (حالة واجهة 2). hello أحدث بمرجع مختلف يُلغي المرجع السابق (`KRJ.A00(oldRef, "true")`).

### 4.3 تشفير الرمز والتغليف (found)

| العنصر | القيمة |
|------|-------|
| الرمز | 5 بايتات عشوائية ← 8 أحرف، 5 بتات لكل حرف، الأبجدية `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 رمزاً، لا `0 I O U`) (`K1T.A00`، يُولِّده الرفيق) |
| الرمز ← المفتاح | PBKDF2-HMAC-SHA256، **131072** تكراراً، 256 بتاً، كلمة المرور = أحرف الرمز، الملح = أول 32 بايت من الحمولة المُغلَّفة (`K1T.A02`) |
| المفتاح العابر المُغلَّف | `[ملح 32 ‖ IV 16 ‖ نص تشفير AES-256-CTR]`، النص الصِّرف = مفتاح عام X25519 بطول 32 بايت؛ يجب أن يكون الطول ≥ 48 |
| ردّ الأساسي | يُنشئ الأساسي زوج مفتاحه العابر الخاص، يُغلِّف مفتاحه العام بالطريقة نفسها (ملح 32 بايت جديد، IV 16 بايت، نفس الرمز) |

### 4.4 `primary_hello` و`companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

عناصر إشعار `companion_finish`: `link_code_pairing_wrapped_key_bundle`، `companion_identity_public`، `link_code_pairing_ref`. معالجة الأساسي في `KYB` الحالة 0:

1. `eph = X25519(primary eph priv, companion eph pub)` (مخزَّن وقت `primary_hello`).
2. تخطيط الحزمة `[ملح 32 ‖ نونس 12 ‖ نص تشفير+وسم AES-256-GCM]`، الحد الأدنى 44 بايت.
3. المفتاح = HKDF-SHA256(الملح = ملح الحزمة، IKM = `eph`، المعلومات = `link_code_pairing_key_bundle_encryption_key`، 32 بايت).
4. النص الصِّرف = `مفتاح هوية الرفيق العام (32) ‖ مفتاح هوية الأساسي العام (32) ‖ عشوائي (32)`.
5. الفحوصات: يجب أن تساوي هوية الأساسي مفتاح الهوية الخاص به؛ يجب أن تساوي هوية الرفيق `companion_identity_public` من الإشعار؛ وإلا يُستبعَد المرجع وتحصل الواجهة على حالة خطأ.
6. `adv secret = HKDF-SHA256(salt = 32 zero bytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. مفتاح التسليم = HKDF(سرّ adv، المعلومات `shortcake-passkey-handoff-v1`) (يُخزَّن أيضاً في `C44423JaU`).
8. يُبنى `C44423JaU` بـ`pub-key` = `companion_server_auth_key_pub`، هوية الرفيق، سرّ adv ← نفس IQ `pair-device` كـQR.

تبادل ECDH العابر الخارجي موجود (إنه IKM لـHKDF في الخطوة 3). ملاحظة من بناء سابق ذكرت "لا ECDH في هذه المرحلة"؛ هذا خاطئ لهذا البناء.

علامات الخطأ على جانب الأساسي: `getCompanionPairingDataOnCompanionFinish ref not exists`، `decryption fail`، `primary identity doesn't match`، `companion identity doesn't match`، `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. هوية الجهاز الموقَّعة ADV

### 5.1 حقول البروتو (found، من سلاسل تخطيط البروتو الخفيف)

| الرسالة | الصنف | الحقل | الرقم | النوع |
|---------|-------|-------|--------|------|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | تعداد (`EnumC32116E1o`) |
| | | `deviceType` | **5** | تعداد (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (يضبطه الرفيق) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | تعداد |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | uint32 مُكرَّر مُحشوّ |
| | | `accountType` | **5** | تعداد |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (مستضاف فقط) |

أرقام الحقول وأنواع السلك مقروءة من معلومات الرسالة المُولَّدة؛ الأسماء تطابق رسائل ADV القياسية. أسماء التعداد: `EnumC32116E1o` القيم E2EE 0، HOSTED 1، NON_E2EE 2.

### 5.2 بادئات التوقيع والخوارزميات

| البادئة | الثابت | البيانات المُوقَّعة/المُصادَق عليها بـMAC | الموقِّع | المستوى |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | توقيع الحساب: `‖ details ‖ companion identity pub` | مفتاح هوية الأساسي | found |
| `06 05` | `A0G` | نسخة الاستضافة من توقيع الحساب؛ تُسبِق أيضاً بيانات HMAC للاستضافة | مفتاح هوية الأساسي / سرّ adv | found |
| `06 01` | `A0H` | توقيع الجهاز: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | مفتاح هوية الرفيق | found (جانب التحقق) |
| `06 06` | `A0I` | نسخة الاستضافة من توقيع الجهاز | مفتاح هوية الرفيق | found (جانب التحقق) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | مفتاح هوية الأساسي | found |
| `06 07` | `A0K` | إثبات غير E2EE ("هجين") (`AeaUtils`)، لا بادئة قائمة فهرس مفتاح | مفتاح هوية الأساسي | found |

- أساسية التوقيع: `C38851hm.A00("best")` يُحمِّل `org.whispersystems.curve25519.OpportunisticCurve25519Provider`؛ `A03` = `calculateSignature(random 64 B, priv, msg)`، `A01` = `verifySignature` (توقيع بطول 64 بايت)، `A02` = `calculateAgreement`. المفاتيح بطول 32 بايت ببايت نوع `5`. فتوقيعات Curve25519 من مكتبة curve25519 الخاصة بـSignal (بنمط XEdDSA، مستنتج من المكتبة، لا من اسم الخوارزمية). اختيار المزوِّد أصلي مقابل Java يُحسَم وقت التشغيل (غير معروف أي منهما يُستخدَم على جهاز معيَّن).
- HMAC: `HmacSHA256` عبر `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 قائمة فهرس المفتاح

يبني `C24270w6.A01` `ADVKeyIndexList`؛ `validIndexes` مجموعة مُشكَّلة من (found): إدخال واحد لفتحة الأساسي (القيمة 0 عندما لا يكون في وضع الرفيق؛ شرط الفرع مستنتج)، `adv_key_index` لكل رفيق مخزَّن (`CJY.A07`)، و`currentIndex`. تُوقِّع `A02` على `06 02 ‖ details`.

يدفعها `C24250w4.A00` كـ:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

مهلة 32000 ms. بوّابة `A02`: العلم **477** غير صفري، رفقاء حاضرون (أو وضع رفيق)، ليس في وضع رفيق. عند الفشل يزداد `adv_key_index_list_update_retry_count`؛ فوق **5** يسجِّل التطبيق `adv-key-index-list-update … fails for more than 5 times` ويسجِّل خروج كل الرفقاء (`C24270w6.A03`). يمحو النجاح العدّادات (`A05`).

### 5.4 قاعدة الطابع الزمني (`C24270w6.A00`)

`last` = تفضيلات مشترَكة `adv_timestamp_sec`؛ `now` = ساعة مُصحَّحة بـNTP، `srv` = وقت الخادم. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. إذا كان `last + 1 > now + 86400` تكون القيمة غير صالحة (-1، مُسجَّلة `getTimestampSec invalid ts`)، وهذا يحجب الربط برمز محلي -8. أحادي الاتجاه لكل حساب (found).

### 5.5 التحقق على السلك (`C24230w2`)

لأي هوية جهاز يراها الأساسي (رفقاؤه ورفقاء جهات اتصاله) يفحص، بالترتيب (found):

1. مفتاح هوية الأساسي معروف (مخزَّن، أو `accountSignatureKey` من القائمة)، وإلا `no primary key`؛
2. مفتاح هوية الرفيق يُحلَّل (`0x05`+32 بايت)، وإلا `invalid companion public key`؛
3. توقيع الحساب على `prefix ‖ details ‖ companion identity`، وإلا `fail to verify account signature`؛
4. توقيع الجهاز على `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (الاستضافة `06 06`)، وإلا يُرفَض الجهاز؛
5. قائمة فهرس المفتاح: توقيع على `06 02 ‖ details` بمفتاح الأساسي؛ يجب أن يكون `adv timestamp` الخاص بالقائمة متسقاً (`advTimestampMismatch`، `advListTimestampInvalid`)؛ فهرس مفتاح وارد غير مطابق يُعيد ضبط الحالة المحلية (`incoming key-index not matching local state, resetting`)؛ فهرس أكبر لنفس الجهاز موجود أصلاً يُسقِط الإدخال الأقدم (`filterDeviceWithKeyIndexList`).

---

## 6. قائمة الأجهزة، السجل والحدود

### 6.1 إشعار `devices` (يستقبله الأساسي)

`notification` بعنصر فرعي `add` أو `remove` (أي شيء آخر: `unknown type of device notification`). السمات والعناصر الفرعية (found): `device_hash`، `device_lid_hash` اختياري إضافة إلى `lid`، إدخالات `device` (JID، فهرس المفتاح)، `key-index-list` اختياري (بايتات، سمة `ts`، `expected_ts`). إذا حمل الإشعار سمة `offline` يُوضَع المستخدم في قائمة انتظار مزامنة لاحقة؛ وإلا تُشغَّل مهمة مزامنة (`SyncDeviceNotificationRunnable`). تُقبَل القائمة فقط إذا لم يكن طابعها الزمني أقدم من `adv_timestamp_sec` المخزَّن (`local ts is larger than notification one` وإلا).

### 6.2 سجل الجهاز المخزَّن (جدول `devices`، `C1h8`)

| المجموعة | الأعمدة (found) |
|-------|-----------------|
| الهوية | `device_id`، `platform_type`، `device_os`، `adv_key_index`، `companion_meta_nonce`، `instrumentation_device_id`، `nickname`، `place_name` |
| الوقت | `last_active`، `login_time`، `logout_time` |
| المزامنة | `full_sync_required`، `full_sync_days_limit`، `full_sync_size_mb_limit`، `recent_sync_days_limit`، `storage_quota_mb`، `inline_initial_hist_sync_payload_enabled`، `history_sync_config_protobuf`، `history_sync_access_type`، `on_demand_ready` |
| القدرة | `support_hosted_group_msg`، `support_biz_hosted_msg`، `support_group_history`، `support_call_log_history`، `support_message_association`، `support_add_on_history_sync_migration`، `support_guest_chat`، `support_bot_user_agent_chat_history`، `support_fbid_bot_chat_history`، `support_manus_history`، `support_hatch_history`، `support_cag_reactions_and_polls_history`، `support_recent_sync_chunk_message_tuning`، `supported_bot_channel_fbids` |

تأتي قيم `platform_type` من `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN، 1 CHROME، 2 FIREFOX، 3 IE، 4 OPERA، 5 SAFARI، 6 EDGE، 7 DESKTOP، 8 IPAD، 9 ANDROID_TABLET، 10 OHANA، 11 ALOHA، 12 CATALINA، 13 TCL_TV، 14 IOS_PHONE، 15 IOS_CATALYST، 16 ANDROID_PHONE، 17 ANDROID_AMBIGUOUS، 18 WEAR_OS، 19 AR_WRIST، 20 AR_DEVICE، 21 UWP، 22 VR، 23 CLOUD_API، 24 SMARTGLASSES، 25 WAIL، 26 WASS، 27 BUSINESS_BACK_OFFICE، 28 WAIL_WAI، 29 WAIL_ALEXA، 30 AUTOMOTIVE (found).

### 6.3 الحدود والأعلام

| العلم/العنصر | المعنى | المستوى |
|-------------|---------|------|
| **15550** | عدد صحيح: الحد الأقصى للأجهزة المرتبطة (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` يحجب "ربط جهاز"؛ يحصل ماسح QR على `at_device_limit` إضافياً؛ ترفض `OrbitCompanionLinkActivity` عند الوصول للحد) | found (الاستخدام)؛ القيمة الافتراضية غير معروفة (خاصية AB تُسلَّم من الخادم)؛ حقل قياس `md_linked_devices_max_devices_limit` موجود |
| **3816** | ثوانٍ تبقى `companion_hello` صالحة، بحد أقصى 360 ث | found |
| **477** | بوّابة (غير صفرية) لتحديثات قائمة فهرس المفتاح | found |
| **18193** | يضيف `friction` (النسخة 1) إلى `challenges/supported` المُعلَنة | found (الاستخدام)؛ الأثر على الخادم غير معروف |
| **28161** | يضيف التحدي المُعلَن الثاني (`passkey-create`) | تخطيط مستنتج (فقد المُفكِّك الفرع) |
| **29500** | بوّابة ربط الاستضافة المُستخدَمة في فحص وضع الدفاع | found (القراءة)، المعنى مستنتج |
| **31019** | يضيف سمة `exclude_hosted_companion=true` لإزالة الكل لأسباب معيَّنة | found |

ما إذا كان الخادم يفرض الحد بشكل مستقل عن فحص العميل غير معروف. لا مهلة خمول من جانب العميل للرفقاء في الكود المقروء هنا؛ انتهاء صلاحية الرفقاء الخاملين من جهة الخادم غير معروف.

---

## 7. فكّ الربط (جانب الأساسي)

### 7.1 جهاز واحد

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`، مهلة 32000 ms. قد تحمل النتيجة عنصراً فرعياً `coex_token` (يُمرَّر إلى معالِج التعايش). فشل التسليم أو الخطأ يستدعي رد نداء الفشل برمز -1 (found).

### 7.2 كل الأجهزة

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

قائمة محلية فارغة تقصر الدائرة إلى رد نداء النجاح. سلاسل الأسباب المرصودة في الكود: `user_initiated`، `unknown_companion`، `invalid_adv_status`، `lid_migration_peer_sync_limit_exceeded`، `lid_migration_peer_sync_message_failed`، `lid_migration_missing_mappings_in_peer_sync_message` (found؛ القائمة قد تكون أطول، تعبير المصدر مُقتطَع).

### 7.3 محفِّزات فكّ الربط الآلي (found)

| المحفِّز | السبب |
|---------|--------|
| فشل تحديث قائمة فهرس المفتاح أكثر من 5 مرات | `adv-key-index-list-update`، تسجيل خروج الجميع |
| فائض فهرس المفتاح | إعادة ضبط `A03` |
| حالة ADV غير صالحة/رفيق غير معروف (`KZD` الحالة 43) | `invalid_adv_status` |
| انتقال نوع حساب استضافة ↔ E2EE | يُطرَد كل الأجهزة (سجل `handleADVMetadata`) |
| يرسل الخادم إشعار `devices` من نوع `remove` | يُزال السجل المحلي (مستنتج) |
| إجراء مستخدم في شاشة الأجهزة المرتبطة / `EavesdropMonitor/disconnectDevice` | `user_initiated` (found للمُراقِب؛ مسار الواجهة مستنتج) |

إزالة الحساب كاملاً (`urn:xmpp:whatsapp:account` `remove`) IQ مختلفة وغير مرتبطة بفكّ ربط الرفيق.

---

## 8. حالات الخطأ

### 8.1 رموز الخادم التي يعالجها `C44661Jem.A01`

| الرمز | رد النداء | الواجهة | المستوى |
|------|----------|----|------|
| **465** | `Blp` ← `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` ← `onCompanionTooOld` | حالة "companion too old" | found |
| 404 / 405 / 443 / 445 | `C2w` عام | تخطيط سلسلة `C44648JeY`: 405 و443 لهما نصان مخصَّصان؛ 404/405/443/445 تتشارك عنواناً واحداً | found (السلاسل بالمعرّف)؛ المعنى الدقيق لـ404/443/445 غير معروف |
| غيره | `C2w` عام | فشل الربط | found |

تُسمِّي `InstrumentationAuthActivity` رموز النتيجة 1 `CONSUMER_SMB_CROSS_PAIRING`، 2 `UNSUPPORTED_PRIMARY_VERSION`، 3 `INVALID_QR_CODE`، 4 `COMPANION_PLATFORM_RESTRICTED`، 5 `COMPANION_TOO_OLD`، 6 `MAX_DEVICE_LIMIT_REACHED`، وإلا `PAIRING_FAILED` (found). تخطيط 405 من الخادم إلى حالة المستهلك/SMB مستنتج من معرّف السلسلة.

### 8.2 الرموز المحلية

| الرمز | السبب | الحل |
|------|-------|-----|
| -8 | طابع زمني ADV محلي غير صالح (الساعة مقابل آخر ts مخزَّن + 1) | تصحيح وقت الجهاز؛ سلسلة واجهة "invalid device time" |
| -9 | QR يفتقد مفتاح الهوية/سرّ adv | استخدام QR حالي |
| -10 | ربط استضافة على بناء المستهلك | لا ينطبق |
| -13 | عدم تطابق علم المنصة مع الاستضافة | لا ينطبق |
| -17 | ربط آخر قيد التشغيل | الانتظار؛ يدوم الطلب حتى 32 ث |
| -20 | طلب الخادم تحديات (`retry-after-challenges`) | إكمال تحدي الاحتكاك/مفتاح المرور |
| -1 | طلب الإزالة لم يُرسَل أو فشل | إعادة المحاولة |

### 8.3 فشل رمز الربط

| العرض (السجل) | السبب |
|---------------|-------|
| `companion hello is null or expired` | الرمز مكتوب بعد الانتهاء (العلم 3816، بحد أقصى 360 ث) |
| `decryption fail` (hello) | رمز خاطئ (مفتاح PBKDF2 يختلف؛ AES-CTR لا وسم له، فرمز خاطئ يُعطي مفتاحاً عشوائياً، يُلتقَط في خطوات لاحقة؛ مستنتج) |
| `primary identity doesn't match` | الحزمة بُنيت لمفتاح أساسي آخر |
| `companion identity doesn't match` | الإشعار والحزمة يتعارضان |
| `invalid-primary-adv-key-length` / `adv public key is 0` | فحوصات دور الرفيق على مفتاح الأساسي العابر |

---

## 9. فروق أساسية

### 9.1 لا تخلط بين

| A | B |
|---|---|
| `pair-device` التي يرسلها **الأساسي** (هذا التقرير) | `pair-device` التي **يستقبلها** تطبيق بدور رفيق (المعالِج `AbstractC40501kw`، المعرّف 242، يحمل مراجع لـQR) |
| `ADVSignedDeviceIdentity` (موقَّعة، دون HMAC) | `ADVSignedDeviceIdentityHMAC` (الغلاف المُرسَل في `device-identity`) |
| العنصر الفرعي `device-identity` في `pair-device` (غلاف HMAC) | العنصر الفرعي `device-identity` في stanzas الرسائل الخارجة (هوية الحساب المُرفَقة من رفيق؛ تفضيلة `adv_signed_identity`) |
| توقيع الحساب (مفتاح الأساسي، البادئة `06 00`) | توقيع الجهاز (مفتاح الرفيق، البادئة `06 01`) |
| بادئة قائمة فهرس المفتاح `06 02` | `06 07` (إثبات غير E2EE) |
| `pub-key` / `companion_server_auth_key_pub` في QR | مفتاح هوية الرفيق (الذي يحصل على توقيع الحساب) |
| `rawId` (معرّف على مستوى الحساب يتغيَّر عند إعادة الضبط) | `keyIndex` (لكل رفيق) |
| حرف منصة QR (`EnumC26332BbY`) | `DeviceProps.platformType` السلكي (`EnumC25120ArW`)، ترقيم مختلف |

### 9.2 الجهاز المُستضاف

معرّف جهاز JID **99** (`device_id should be 99 for hosted device`)، علامة تسجيل/فكّ ربط `hosted_device_pairing`، بادئتا توقيع `06 05` / `06 06`، `exclude_hosted_companion`. يرفض الأساسي ربط جهاز مُستضاف في هذا البناء (محلي -10). كل ما يتجاوز هذه السلاسل غير معروف.

### 9.3 Shortcake

يمكن أن تحمل `retry-with-method` `shortcake-with-passkeys`؛ يخزِّن التطبيق بعد ذلك مفتاح تسليم ويُبدِّل الواجهة. تُعرِّض `ShortcakeJni` `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` و`nativeResponderStart/Finish` (found). نصّ المصافحة أصلي ولم يُفكَّك هنا: غير معروف.

#### 9.3أ الربط الصامت — ربط رفيق مُقيَّد/محيطي + ترحيل عصر (جديد في 2.26.45.10، found)

آلية ربط **رابعة**، أضيق من الثلاث أعلاه (ADV/QR القياسي، رمز الربط/CRSC، الجهاز المُستضاف): ربط صامت لرفقاء **مُقيَّدين/محيطيين** — أجهزة قابلة للارتداء ونظارات ذكية، `DeviceProps.platformType` `WEAR_OS` / `AR_WRIST` / `AR_DEVICE` / `SMARTGLASSES`. الحزمة `com.whatsapp.instrumentation.product.silentlinking` (`SilentLinkingNativeRegistration`، `SilentLinkingSessionManager$Session`).

**"صامت" تعني لا مسح QR، لا غياب تفاعل المستخدم.** سلاسل القياس عن بُعد (found) تُظهر تدفق تأكيد برمز قصير: `"code displayed to user"` ← `"user confirmed code on primary"` ← `"companion registration start"`. يعرض الجهاز المحيطي رمزاً قصيراً ويؤكِّده المستخدم على الهاتف — نفس نموذج حضور المستخدم كتدفق رمز الربط (§4)، فقط دون صورة QR. نقطة الدخول هي واجهة ترقية الجهاز القابل للارتداء بعد المكالمة (`PostCallWearableUpsellBottomSheet`، `com.whatsapp.calling.wearableupsell`) تُغذِّي `SilentLinkingVerificationActivity` (`android:exported="false"`، داخلي فقط، لا رابط عميق). المُحفِّز هو واجهة العميل فقط: لم يُعثر على أي نقطة دخول `AlarmManager`/`WorkManager`/دفع من الخادم في أي من الصنفين، ولا يظهر أي منطق `unlink`/`unpair`/"جهاز موجود" في أي منهما — هذا يُنشئ ربطاً، لا يُزيل أحداً صمتاً.

يستأجر `SilentLinkingNativeRegistration` فتحة تسجيل من القناة الجانبية CRSC v2/v3 الموجودة (`CompanionRegOverSideChannelV2Manager`/`V3Manager`، نفس بنية §4) لنقل تسجيل الهوية الناتج. تبادل مفتاح الرفيق الفعلي عائلة protobuf منفصلة، غير موثَّقة سابقاً:

**عائلة غلاف RPC الخاصة بـShortcake** (found، أسماء/أرقام الحقول من smali، لم تُفكَّك بشكل مستقل إلى Java):

| الصنف | الدور |
|-------|------|
| `LX/R9f` | غلاف `oneof` على المستوى الأعلى: `protocolVersion`(1)، `bootstrapAndHello`(2)، `finishAndReady`(3)، `peripheralAck`(4)، `postCommitProofEnvelope`(5)، `readinessRequestEnvelope`(6)، `readinessResponseEnvelope`(7)، `exactCleanupRequest`(8)، `exactCleanupReceipt`(9) |
| `LX/RAN` | Bootstrap&Hello: `linkId`(1)، `setupAttemptId`(2)، `epochId`(3)، `purpose`(4)، `hnSignPub`(5)، `hnEpoch1EphPub`(6، ECDH عابر كلاسيكي)، `hnMlkemPub`(7، مفتاح عام ML-KEM-768)، `protocolVersion`(8)، `selectedCapabilities`(9)، `migrationContextHash`(10)، `hnDeviceSerial`(11) |
| `LX/RA1` | غلاف مُغلَّف بنص تشفير Signal: `signalCiphertext`(1)، `signalMessageType`(2)، `peripheralHello`(3)، `signalRequestId`(4)، `companionAdvFingerprint`(5)، `primarySignalPeerFingerprint`(6) — يربط المصافحة بطابع هوية ADV الخاص بالرفيق نفسه (§5) |
| `LX/RAW` | غلاف `oneof` ثانٍ، جانب ترحيل العصر: `rpcRequest`(1)، `rpcResponse`(2)، `primaryReady`(3)، `peripheralAck`(4)، `rotationControl`(5)، `requestStatus`(6)، `migrationPostCommitProof`(7)، `migrationStatusRequest`(8)، `migrationStatusResponse`(9)، `migrationProbeRequest`(10)، `migrationProbeResponse`(11) |
| `LX/RUe` | تعداد `PERIPHERAL_PROPS_PLATFORM_{UNKNOWN,IOS,ANDROID}` — نظام تشغيل الجهاز المحيطي نفسه |

`RAN.hnEpoch1EphPub` (كلاسيكي) إلى جوار `RAN.hnMlkemPub` (ML-KEM-768) يؤكِّد **تبادل مفتاح هجيناً من ECDH كلاسيكي + ما بعد الكمّي**، لا PQ فقط. هذه **أول آلية تشفير ما بعد كمّي موثَّقة في هذا التقرير**: ML-KEM-768 (FIPS 203 / Kyber-768)، تُشغَّل عبر `ShortcakeJni` الأصلية (liboqs `OQS_KEM_ml_kem_768`، مُغلَّفة بـ`KEMPublicKey`/`KEMSecretKey` الخاصة بـlibsignal — مُعثور عليها بفك تجميع أصلي في تمرير منفصل، انظر البرين `research/2.26.36.1/shortcake-kem-native.md`). هذا المخطط من جانب Java هو تأطير النصّ الذي تركه التحليل الأصلي وحده غير معروف؛ تبقى المصافحة الفعلية Responder-Start/Finish على مستوى البايت أصلية فقط وغير معروفة.

**تسميات سياق HKDF** (found، سلاسل حرفية في `LX/SdB`، KDF = HMAC-SHA256 / HKDF-SHA256، نفس الأساسية المُستخدَمة في KDF تغليف رمز الربط في §4.3): `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_V1`، `WA_TETHERED_EPOCH1_HN_KEY_POP_V1`، `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_HASH_V1`، `WA_TETHERED_EPOCH1_PRIMARY_FINISH_V1`، `WA_TETHERED_EPOCH1_WA_KEY_POP_V1`، `WA_TETHERED_EPOCH1_HYBRID_KX_V1`، `WA_TETHERED_LINK_IDENTITY_CONTEXT_V1`. ("HN" = جانب الأساسي/الهاتف؛ غير مُوسَّع في أي مكان من الشجرة، على الأرجح "Host/Home Network".)

**تدوير/ترحيل العصر (سلاسل مُعثور عليها، الدور مستنتج).** يحمل `LX/TIR` مفردات خطأ ترحيل وافرة (`"Invalid migration frame version"`، `"Migration epoch mismatch"`، `"Migration shadow serial mismatch"`، `migration_shadow`، إلخ)، مع `RAN.epochId` وحقول التدوير/فحص الترحيل/الحالة/إثبات ما بعد الالتزام الخاصة بـ`RAW`. بقراءتها معاً هذا بروتوكول **تدوير مفتاح-عصر في الخلفية لربط مُقيَّد مُؤسَّس أصلاً** — تستدعي `SilentLinkingSessionManager$Session` دورياً `SilentLinkingNativeRegistration` لتدوير مفاتيح Shortcake تحت `epochId` جديد، بمسار فحص/حالة/ترقية/إعادة تشغيل و"إرجاع سجل ظلّ". هذا سرد مستنتج فوق سلاسل/حقول مُعثور عليها؛ ليس آلية استرداد لجلسة رفيق كلاسيكية مفقودة، ولا فكّ ربط مدفوع من الخادم. الشرط الدقيق المُحفِّز لدورة تدوير، والنقل السلكي الدقيق لـ`R9f`/`RAW` (حمولة القناة الجانبية CRSC مقابل stanza/IQ مخصَّصة)، غير معروفان.

**صلة صفرية بـBaileys/velowa.** محجوبة خلف تشفير `ShortcakeJni` الأصلي ونشاط داخلي (`exported="false"`) لا يُوصَل إليه إلا من واجهة داخل التطبيق، محدودة كلياً بفئة رفيق الأجهزة القابلة للارتداء/النظارات الذكية الخاصة بـWhatsApp نفسه. لا تلمس ربط الرفيق الكلاسيكي ADV/CRSC (§2-§4، ما يُنفِّذه عميل أجهزة متعددة لطرف ثالث)، ولم يُعثر على أي آلية تفكّ بها ربط رفيق Web/Desktop أو تُعيد ربطه صمتاً.

### 9.4 الاحتكاك/وضع الدفاع

تُعلِن `pair-device` التحديات المدعومة وتُعيد المُكتمَلة عند إعادة المحاولة. يقرر الأساسي محلياً طلب الاحتكاك عندما يكون وضع الدفاع مُفعَّلاً (`C271211x.A0N()`) وتحدي الاحتكاك لم يكتمل بعد؛ يُتَّخذ هذا القرار قبل أول IQ (`defense mode friction triggered`). سياسة من جهة الخادم تُرسِل `retry-after-challenges` غير ظاهرة (غير معروف).

### 9.5 لا إثبات من جانب العميل للرفيق

لا شيء في حمولة pair-device يُثبت أي برنامج يُشغِّله الرفيق: `ref`، `pub-key`، مفتاح الهوية، سرّ adv وحرف المنصة كلها مُعلَنة ذاتياً من QR. ما تُثبته التوقيعات هو أن هذا الحساب الأساسي صرَّح بمفتاح الهوية ذلك. أي فحص "عميل رسمي" من جهة الخادم (الحكم 465 يُعالَج فقط من جانب العميل).

### 9.6 كود دور الرفيق في نفس APK (باختصار)

| العنصر | النتيجة |
|------|---------|
| عناصر IQ `companion_hello` | `link_code_pairing_wrapped_companion_ephemeral_pub`، `companion_server_auth_key_pub`، `companion_platform_id`، `companion_platform_display`، `link_code_pairing_nonce`؛ سمة `should_show_push_notification` (found، `C0YS`) |
| الرمز | base32 لـ5 بايتات عشوائية في `K1T.A00` (4.3) |
| تدوير QR | IQ `pair-device-rotate-qr` بسمات `stage` 0/1/2 و`sentinel` اختيارية، عنصر فرعي `ref` |
| IQs md الواردة | `pair-device`، `pair-success`، `ref`، `companion_reg_refresh`، `integrity` (المعرّفات 242، 243، 266، 278، 279) |
| محتوى `pair-success` ورد `pair-device-sign` الخاص بالرفيق | لم يُتعقَّب في هذا البناء: غير معروف |

---

## 10. Baileys (`baron-baileys-v2`)

مُقارَن مع المصدر المحلي؛ فقط التطابقات وفرق واحد تم فحصهما على كلا الجانبين.

| العنصر | APK 2.26.41.6 | `baron-baileys-v2` | النتيجة |
|------|---------------|--------------------|--------|
| حمولة QR | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | تطابق (4 حقول) |
| استخلاص رمز الربط | PBKDF2-SHA256 131072 تكراراً، الأبجدية `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`، نفس الأبجدية (`crypto.js`، `generics.js`) | تطابق |
| حزمة المفتاح | `[salt32 ‖ nonce12 ‖ GCM]`، المعلومات `link_code_pairing_key_bundle_encryption_key`، النص الصِّرف identity ‖ identity ‖ random32 | نفس التخطيط (`messages-recv.js`) | تطابق |
| سرّ adv | HKDF(ملح صفري، `eph ‖ DH(identity) ‖ random`، المعلومات `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | تطابق |
| غلاف HMAC | HMAC-SHA256(سرّ adv، [06 05 للاستضافة ‖] بايتات ADVSignedDeviceIdentity) | مطابق (`validate-connection.js`) | تطابق |
| رسائل توقيع الحساب/الجهاز | `06 00 ‖ details ‖ companionIdentity`؛ `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | مطابق | تطابق |
| بادئة قائمة فهرس مفتاح الاستضافة | يستخدم المُحقِّق والموقِّع `06 02` لكل قائمة؛ `06 07` هي بادئة الإثبات غير E2EE | `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` مُستخدَمة عندما `accountType == HOSTED` (`chats.js`) | **يختلف**؛ لا يُشغَّل تدفق الاستضافة من هذا بناء المستهلك، فأثر الفرق غير معروف |

لا يُطرَح زعم "لماذا يفشل": رفيق Baileys يتبع الصفوف المتطابقة متسق مع ما يُحلِّله الأساسي هنا؛ القبول من الخادم غير قابل للتحقق ساكناً.

---

## 11. التدفقات الكاملة

### 11.1 تدفق QR

```
[Companion]  shows QR  https://wa.me/settings/linked_devices#ref,noisePub,identityPub,advSecret[,platform]
     │
     ▼
[Primary]    scan → C45741Jxy.A02 → C45423Jrn → C44423JaU
     │       checks: -9 / -13 / -17 / -8 / -10 ; defense mode → challenges (-20)
     │       incrementCurrentKeyIndex ; ts = C24270w6.A00()
     │       details  = ADVDeviceIdentity{rawId, ts, keyIndex, accountType, deviceType}
     │       accSig   = Curve25519.sign(P.priv, 06 00 ‖ details ‖ companionIdentity)
     │       signed   = ADVSignedDeviceIdentity{details, P.pub, accSig}
     │       wrapper  = ADVSignedDeviceIdentityHMAC{signed, HMAC-SHA256(advSecret, signed)}
     │       list     = ADVSignedKeyIndexList (sig 06 02)
     │       K        = HKDF(salt = noisePub, IKM = advSecret, "Canonical Ent Companion Nonce Encrypt")
     ▼
iq set xmlns=md  <pair-device> ref, pub-key, device-identity, key-index-list ts, client-props, pem, … </pair-device>
     │
     ▼
[WA Server]   (not observed) validates, creates device jid, sends pair-device / pair-success to the companion
     │
     ▼
Result to primary: <device jid/> <companion-props/>   (or retry-ts / retry-after-challenges / retry-with-method / error 465, 496, …)
     │
     ▼
[Primary]    store CJY record, adv_timestamp_sec = list ts, start history sync
     │
     ▼
[Server → Primary]  notification devices add{device_hash, device…, key-index-list ts}  → SyncDeviceNotificationRunnable → verify (5.5)
```

### 11.2 تدفق رمز الربط

```
[Companion]  iq link_code_companion_reg stage=companion_hello
     │         wrapped_ephemeral = salt32 ‖ iv16 ‖ AES-CTR(PBKDF2(code, salt), ephPub)
     ▼
[WA Server]  → notification stage=companion_hello  → [Primary] C10J (id 252)
     │                                               store hello (ttl ≤ 360 s), push notification
     │                                               user types 8-char code
     ▼
[Primary]    unwrap companion eph pub ; make own eph pair ; eph = X25519(...)
     │         iq link_code_companion_reg stage=primary_hello
     │             wrapped_primary_ephemeral_pub, primary_identity_pub, link_code_pairing_ref
     ▼
[Companion]  eph = X25519(...) ; bundle = salt32 ‖ nonce12 ‖ GCM(HKDF(eph, salt), companionId ‖ primaryId ‖ random32)
     │         iq stage=companion_finish
     ▼
[WA Server]  → notification stage=companion_finish → [Primary] KYB
     │            decrypt, check both identities, advSecret = HKDF0(eph ‖ DH(id) ‖ random, "adv_secret")
     ▼
[Primary]    pair-device IQ (same as 11.1, pub-key = companion_server_auth_key_pub)
     ▼
(11.1 continues)
```

### 11.3 فكّ الربط

```
[Primary UI / auto trigger]
     │   remove-companion-device jid=… reason=…     (or all="true")
     ▼
iq set xmlns=md  →  [WA Server]  →  result (optional coex_token)
     │
     ▼
[Primary]   remove local record, new key-index-list on next update (iq key-index-list ts)
[Server → other devices]  notification devices remove{…}
```
