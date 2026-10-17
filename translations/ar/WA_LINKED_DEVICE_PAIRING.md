<!-- src-sha1: 2c3f9604f03ccc7f3d3160d18810a86e62b8172f -->
# WhatsApp إقران الأجهزة المرتبطة — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** جانب الجهاز الأساسي من إقران الجهاز المرافق، ومسار QR، ومسار رقم الهاتف / رمز الإقران، وstanzas من نوع `pair-device` و`pair-success`، ومواد المفاتيح، وهوية الجهاز الموقَّعة ADV وقائمة فهارس المفاتيح، وقائمة الأجهزة وحدودها، وفكّ الربط، والأخطاء، ومقارنة Baileys

---

## 1. ما هو (من الناحية التقنية)

الجهاز المرتبط (companion) هو نقطة طرفية ثانية للحساب نفسه. يخوّله الهاتف الأساسي بإنشاء هوية موقَّعة ADV (التحقق من أجهزة الحساب) على مفتاح هوية الجهاز المرافق. جميع العبارات هي نتيجة تحليل ساكن لـ APK المفكوك؛ لم يُلتقط شيء على الشبكة. المستوى: **found** = قُرئ في الشيفرة، **inferred** = مستنتَج من الشيفرة، **unknown** = لم يُحسم.

الأسماء المشوَّشة تختلف حسب البناء، وأُعيد تحديدها من سلاسل ثابتة في 2.26.41.6.

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| منسّق QR/الإقران | `C45850K0w` (بادئة السجل `CompanionDeviceQrHandler`) | يحلّل QR، ويبني بروتوكولات ADV، ويرسل `pair-device` |
| باني IQ الخاص بـ `pair-device` | `RunnableC46606KYf` | يبني الـ IQ |
| مساعد الطلب/الاستجابة لـ `pair-device` | `KRI` (`devicePairRequest/*`) | الإرسال، وإعادة المحاولة، وتحليل `device` / `companion-props` / تلميحات إعادة المحاولة |
| موجّه الأخطاء | `C44661Jem` | يربط رمز خطأ الخادم باستدعاء واجهة المستخدم |
| محلل سلسلة QR | `C45741Jxy` → `C45423Jrn` | من حمولة QR إلى بيانات الإقران |
| بيانات الإقران المحلَّلة | `C44423JaU` | ref، ومفاتيح الجهاز المرافق، وadv secret، والمنصة |
| أداة ADV | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId، وفهرس المفتاح، والطابع الزمني، وبناء قائمة فهارس المفاتيح وتوقيعها |
| محدّث قائمة فهارس المفاتيح | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | يدفع القائمة الموقَّعة إلى الخادم |
| مدقّق ADV | `C24230w2` (`DeviceADVInfoHandler`) | يتحقق من الهويات والقوائم المرصودة على الشبكة |
| معالج إشعار قائمة الأجهزة | صنف مجهول داخل `C1S0` (`DeviceUpdateNotificationHandler`)، و`RunnableC29334CoL` | إشعار `devices` |
| معالج إشعار رمز الربط | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | معرّف الإشعار 252 |
| مدير رمز الربط (الأساسي) | `KZ3` (إدخال الرمز، `primary_hello`)، `KYB` (`companion_finish`)، `C10L`، `C77` | مسار رمز الإقران |
| أداة تشفير رمز الربط | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF، وPBKDF2، وbase32 |
| مدير الأجهزة | `C0XQ` (`companion-device-manager`) | القائمة، وتسجيل الخروج |
| مساعد الإزالة | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| غلاف منحنى Signal | `C38851hm` | المزوّد "best" في `org.whispersystems.curve25519` |
| أصناف ADV proto | `C25815BBy`، `C25792BBb`، `C25785BAt`، `C25786BAu`، `BCB` | انظر القسم 5 |
| DeviceProps | `C43105IrG` (التعداد `EnumC25120ArW`) | `companion-props` في نتيجة `pair-device` |
| Client props | `C43107IrI` | العنصر الابن `client-props` |
| نوع الحساب/التشفير | `EnumC32116E1o` | `E2EE` 0، `HOSTED` 1، `NON_E2EE` 2 |

توجد ثلاثة أوضاع دخول في واجهة الجهاز الأساسي (`EnumC26221BZl`): ‏`QR_CODE` و`PHONE_NUMBER_AND_CODE` و`EXTERNAL_DEEPLINK_QR_CODE` (found).

يحتوي APK نفسه أيضًا على شيفرة تسجيل بدور الجهاز المرافق (آلة الحالات `C0YS`، وسجلات `companion/registration/*`). وهي خارج النطاق؛ يُوصف فقط ما يلزم لشرح ما يستقبله الجهاز الأساسي (القسم 9.6).

---

## 2. مسارات الإقران في لمحة

| المسار | المُحفِّز على الجهاز الأساسي | ما يرسله الأساسي | السر الذي يربط الأساسي بالمرافق |
|------|--------------------|---------------|----------------------------------------|
| QR | مسح `https://wa.me/settings/linked_devices#<payload>` (أو `whatsapp://settings/linked_devices#<payload>`) | `iq xmlns=md` ‏`pair-device` | ‏`adv secret` من الحقل 4 في QR |
| رقم الهاتف + الرمز | `notification` ‏`link_code_companion_reg` بالمرحلة `companion_hello`، ويكتب المستخدم رمزًا من 8 محارف | `primary_hello`، ثم لاحقًا (بعد `companion_finish`) نفس `pair-device` | ‏`adv secret` مشتق من نتيجتي X25519 مع قيمة عشوائية (القسم 4.4) |

يلتقي المساران عند كائن `C44423JaU` واحد وIQ ‏`pair-device` واحد (found: يبني `KYB` الكائن `C44423JaU` من حزمة `companion_finish` بنفس المُنشئ الذي يستخدمه `C45850K0w.A01` لـ QR).

---

## 3. مسار QR (جهة الأساسي)

### 3.1 حمولة QR

يزيل `C45741Jxy.A01` البادئة `https://wa.me/settings/linked_devices#` أو `whatsapp://settings/linked_devices#` ويفكّ ترميز URL للباقي. ويقسّم `A02` على `,` (found):

| الفهرس | المحتوى | الترميز | الاستخدام |
|-----|---------|----------|-----|
| 0 | `ref` | سلسلة | مرجع الإقران؛ يُرفض ref الذي يبدأ بـ `CAPI_` (`invalid ref`) |
| 1 | المفتاح العام للجهاز المرافق | base64 | يُرسَل كـ `pub-key`، وهو salt لمفتاح nonce (3.4). الاسم مستنتَج: مفتاح Noise الثابت (`companion_server_auth_key_pub` في مسار الشيفرة) |
| 2 | مفتاح هوية الجهاز المرافق | base64، 32 بايت، يضيف المحلل `0x05` في البداية (نوع Curve25519) | يوقَّع عليه بتوقيع الحساب |
| 3 | `adv secret` | base64 | مفتاح HMAC لغلاف ADV |
| 4 | رمز المنصة (اختياري) | محرف واحد | يُربط بنوع منصة؛ ‏`j` = جهاز hosted |

- أقل من 3 أجزاء: `qrData/processQR/error/invalid_code parts`. غياب مفتاح الهوية أو adv secret (QR قديم بثلاثة حقول): `invalid qr code, missing companion identity key or adv secret` ← الرمز المحلي **-9**.
- جدول محارف المنصة (مستقل عن `EnumC26221BZl`، وهو `EnumC26332BbY`): ‏`0` UNKNOWN، `1` CHROME، `2` EDGE، `3` FIREFOX، `4` IE، `5` OPERA، `6` SAFARI، `7` DESKTOP، `8` UWP، `9` OTHER_WEB، `a` IOS_TABLET، `b` IOS_PHONE، `c` IOS_CATALYST، `d` ANDROID_TABLET، `e` ANDROID_PHONE، `f` ANDROID_AMBIGUOUS، `g` WEAR_OS، `i` AR_DEVICE، `j` HOSTED_DEVICE، `k` VR، `l` SMARTGLASSES، `n` WAIL_WAI، `o` WAIL_ALEXA (found). يُستخدم فقط لفحص hosted وللتسجيل (3.2).

### 3.2 الفحوص المحلية قبل إرسال أي شيء

| الفحص | الشيفرة | الرمز المحلي |
|-------|------|------------|
| يحتوي QR على مفتاح الهوية وadv secret | `C45850K0w.A01` | -9 |
| اتساق علم hosted: ‏`(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| إقران آخر قيد التنفيذ (`kri.A0N`، أو مدير الأجهزة المرافقة مشغول) | `A04` | -17 |
| الطابع الزمني المحلي لـ ADV صالح (`C24270w6.A00() != -1`) | `A04` | -8 |
| جهاز مرافق hosted | ‏`A04`: `Hosted pairing is not supported` | -10 |
| الحاجة إلى friction في وضع الدفاع | ‏`RunnableC46606KYf`: `defense mode friction triggered` | -20 (إعادة محاولة مع challenges) |

إقران hosted محظور من جهة العميل في هذا البناء (`pairing for hosted device is not supported on the consumer build`).

### 3.3 قبل الـ IQ: تنظيف syncd وفهرس المفتاح

1. إذا كانت حالة syncd متسخة (`sync-manager/shouldCleanUpSyncdOnPairing`)، ينظّف التطبيق syncd أولًا ثم يتابع (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. ‏`incrementCurrentKeyIndex` (في `RunnableC46617KYr`):
   - لا rawId أو فهرس مخزّن: rawId عشوائي جديد، والفهرس 1؛
   - لا أجهزة مرافقة مرتبطة: ‏`rawId + 1`، ويبقى الفهرس 1؛
   - توجد أجهزة مرافقة: ‏`currentIndex + 1`؛ عند التجاوز يزداد rawId بمقدار 1 ويُسجَّل خروج جميع الأجهزة (`C24270w6.A03`).
3. ‏`ts = C24270w6.A00()` (القسم 5.4).

### 3.4 ما الذي يُبنى

في `C45850K0w.A00`، حيث `E` = مفتاح هوية الجهاز المرافق (32 بايت، خام)، و`P` = زوج مفاتيح هوية الجهاز الأساسي (Curve25519)، و`S` = adv secret:

| الخطوة | العملية | المستوى |
|------|-----------|------|
| 1 | ‏`ADVDeviceIdentity` ‏`{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | توقيع الحساب = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`؛ البادئة `06 00` (لـ hosted ‏`06 05`) | found |
| 3 | ‏`ADVSignedDeviceIdentity` ‏`{details, accountSignatureKey = P.pub, accountSignature}` (يُترك `deviceSignature` فارغًا: يضيفه الجهاز المرافق) | found |
| 4 | ‏`ADVSignedDeviceIdentityHMAC` ‏`{details = serialized step 3, hmac = HMAC-SHA256(key = S, data = step 3 bytes), accountType}`؛ وفي hosted تكون البيانات `06 05 ‖ bytes` | found |
| 5 | ‏`BCB` (ADVKeyIndexList) من `C24270w6.A01`، يوقَّع بواسطة `A02` ← `ADVSignedKeyIndexList` (5.3) | found |
| 6 | مفتاح nonce ‏`K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`، يُغلَّف كعنصر ابن `pem` | found (الاشتقاق)؛ الغرض inferred |
| 7 | ‏`encryption-metadata` اختياري (`C38898Gvq`): ‏`encrypted_key` و`nonce` و`encrypted_data` و`auth_tag`، من `AuthProofHelper` (تشفير كلمة مرور الحساب، التسمية `rsa2048`) | found (البنية)؛ ما يُثبته unknown |
| 8 | ‏`client-props` اختياري (`C43107IrI`، القسم 3.6) | found |

تفصيل الخطوة 6: العقدة `pem` موسومة بـ `version=1` و`algorithm=rsa2048` و`ttl ts_s = 5 days` و`key_id=1`، لكن ابنها يحمل `key.getEncoded()` لمخرج HKDF ذي 32 بايت (خوارزمية `SecretKeySpec` هي `AES-GCM`). التسمية والمحتوى غير متطابقين؛ السبب unknown. استخدام الخادم inferred (يشفّر الخادم nonce لكل جهاز إلى الجهاز المرافق؛ قارن العمود `companion_meta_nonce`).

### 3.5 الـ IQ ‏`pair-device` (الأساسي ← الخادم)

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

Found: جميع أسماء العناصر الابنة، وقيمة السمة `ts` (الطابع الزمني لقائمة فهارس المفاتيح)، والمهلة **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). قيمة `companion_qr_origin_source` هي `1` لقيمة الدخول 3 و`2` لقيمة الدخول 5 (معنى أعداد الدخول unknown). ترتيب العناصر الابنة بالضبط وفرع `companion_qr_origin_source` مشوَّهان جزئيًا بفعل المفكِّك؛ يُعامَل الترتيب على أنه غير متحقق منه.

### 3.6 ‏`client-props` (‏`C43107IrI`)

| الحقل | الرقم | النوع | يُضبط عند |
|-------|--------|------|-----------|
| `isChatDbLidMigrated` | **1** | bool | اكتمال ترحيل LID في قاعدة بيانات المحادثات |
| `isSyncdPureLidSession` | **2** | bool | وجود علم syncd pure-LID |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | علم الاستعادة |
| `isHsThumbnailSyncEnabled` | **4** | bool | علم مزامنة الصور المصغرة لسجل المحادثات |
| `subscriptionSyncPayload` | **5** | bytes | يُبنى عند تفعيل مزامنة md (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | ترحيل قاعدة بيانات JID للبوتات |

### 3.7 معالجة النتيجة (`KRI.CFS`)

العناصر الابنة لنتيجة النجاح (found):

| العنصر الابن | الاستخدام |
|-------|-----|
| `device` السمة `jid` | ‏`DeviceJid` للجهاز المرافق الجديد؛ يُربط معرّف الجهاز **99** بمدخل منصة hosted |
| `companion-props` | بروتو `DeviceProps` (`C43105IrG`): ‏`os` **1** (سلسلة)، `version` **2** (رسالة)، `platformType` **3** (تعداد)، `requireFullSync` **4** (bool)، `historySyncConfig` **5** (رسالة) |
| `retry-ts` السمة `ts` | يطلب الخادم طابعًا زمنيًا أحدث؛ يعيد التطبيق المحاولة (`RunnableC46585KXj`) |
| `retry-after-challenges` | عناصر ابنة `friction` (السمة `variant`، يجب أن تكون `1`، و`location` اختيارية "lat,lon") أو `passkey-create` (السمة `created`) |
| `retry-with-method` | عناصر ابنة `qr-code` أو `shortcake-with-passkeys`؛ إذا وُجد الثاني يُخزَّن مفتاح التسليم ذو 32 بايت (HKDF من adv secret، info هو `shortcake-passkey-handoff-v1`) (`PairingHandoffKeyHolder`)، ويتحكم بذلك abprop |

عند النجاح يخزّن التطبيق سجل الجهاز `CJY` (سلسلة base64 عشوائية من 24 بايت، و`adv_key_index` = الفهرس الحالي، و`requireFullSync`)، ويحفظ الطابع الزمني لقائمة فهارس المفاتيح كـ `adv_timestamp_sec` (`C24270w6.A05`)، ويبدأ حالة مزامنة السجل (`C8N`).

فشل التسليم (`Bog`): حتى **3** محاولات، بتأخير `3000 * 3^(n-1)` ms (3 ثوانٍ، 9 ثوانٍ، 27 ثانية) إذا كان علم إعادة المحاولة مفعّلًا (found)؛ ثم استدعاء الخطأ.

---

## 4. مسار رقم الهاتف / رمز الإقران (جهة الأساسي)

### 4.1 الخطوات

| # | الاتجاه | Stanza / إجراء | الصنف |
|---|-----------|-----------------|-------|
| 1 | المرافق ← الخادم ← الأساسي | ‏`notification` ‏`link_code_companion_reg`، ‏`stage=companion_hello` | `C10J` (المعرّف 252) |
| 2 | الأساسي | يخزّن hello، ويعرض إشعارًا فوريًا ← `CompanionHelloConfirmationActivity` / شاشة إدخال الرمز | `C10J`، `C77`، `JYJ` |
| 3 | المستخدم | يكتب الرمز المكوَّن من 8 محارف | `LinkedDevicesEnterCodeActivity` |
| 4 | الأساسي ← الخادم | ‏`iq xmlns=md type=set` ‏`link_code_companion_reg stage=primary_hello` | `KZ3` (المهلة 120000 ms) |
| 5 | الخادم ← الأساسي | ‏`notification` ‏`stage=companion_finish` | `C10J` ← `KYB` الحالة 0 |
| 6 | الأساسي ← الخادم | IQ ‏`pair-device` (القسم 3.5) | `C45850K0w` |
| 7 | مراحل أخرى | ‏`refresh_code` (يطلب الأساسي تحديث الرمز، السمة `force_manual_refresh`) | `C10J` |

### 4.2 إشعار `companion_hello` (found)

| العنصر الابن | الاستخدام |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | مفتاح X25519 المؤقت للجهاز المرافق، مغلَّف بالرمز (4.3) |
| `companion_server_auth_key_pub` | يصبح لاحقًا `pub-key` في `pair-device` |
| `link_code_pairing_ref` | مرجع الجلسة (سلسلة) |
| `companion_platform_id` | سلسلة معرّف المنصة |
| `companion_platform_display` | اسم العرض |
| السمة `should_show_push_notification` | ‏`true` ← إشعار فوري |

الحالة المحفوظة (`C77`/`CE4`، JSON في SharedPrefs ‏`companion_reg_with_link_code_companion_hello_info_json`): ref، ومعرّف المنصة، والمفتاح المغلَّف، ومفتاح مصادقة الخادم، وانتهاء الصلاحية `now + min(360000, flag 3816 * 1000)` ms. hello منتهي أو غائب ← "companion hello is null or expired" (حالة واجهة المستخدم 2). يلغي hello أحدث بـ ref مختلف الـ ref السابق (`KRJ.A00(oldRef, "true")`).

### 4.3 الرمز وتشفير الغلاف (found)

| البند | القيمة |
|------|-------|
| الرمز | 5 بايتات عشوائية ← 8 محارف، 5 بتات لكل محرف، الأبجدية `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 رمزًا، دون `0 I O U`) (`K1T.A00`، يولّده الجهاز المرافق) |
| من الرمز إلى المفتاح | PBKDF2-HMAC-SHA256، **131072** تكرارًا، 256 بت، كلمة المرور = محارف الرمز، salt = أول 32 بايت من الكتلة المغلَّفة (`K1T.A02`) |
| المفتاح المؤقت المغلَّف | ‏`[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`، النص الصريح = مفتاح X25519 العام ذو 32 بايت؛ يجب ألا يقل الطول عن 48 |
| رد الأساسي | ينشئ الأساسي زوج مفاتيح مؤقتًا خاصًا به، ويغلّف مفتاحه العام بالطريقة نفسها (salt جديد من 32 بايت، وIV من 16 بايت، والرمز نفسه) |

### 4.4 ‏`primary_hello` و`companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

العناصر الابنة لإشعار `companion_finish`: ‏`link_code_pairing_wrapped_key_bundle` و`companion_identity_public` و`link_code_pairing_ref`. معالجة الأساسي في `KYB` الحالة 0:

1. ‏`eph = X25519(primary eph priv, companion eph pub)` (مخزَّن وقت `primary_hello`).
2. تخطيط الحزمة `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`، بحد أدنى 44 بايت.
3. المفتاح = HKDF-SHA256(salt = bundle salt, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. النص الصريح = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. الفحوص: يجب أن تساوي هوية الأساسي مفتاح هويته الخاص؛ ويجب أن تساوي هوية المرافق `companion_identity_public` من الإشعار؛ وإلا يُسقَط ref وتتلقى واجهة المستخدم حالة خطأ.
6. ‏`adv secret = HKDF-SHA256(salt = 32 zero bytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. مفتاح التسليم = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (يُخزَّن أيضًا في `C44423JaU`).
8. يُبنى `C44423JaU` بـ `pub-key` = `companion_server_auth_key_pub`، وهوية المرافق، وadv secret ← نفس IQ ‏`pair-device` كما في QR.

ECDH المؤقت الخارجي موجود (وهو IKM لـ HKDF في الخطوة 3). ملاحظة في بناء سابق قالت "no ECDH in this stage"؛ وهذا خطأ في هذا البناء.

علامات الأخطاء في جهة الأساسي: `getCompanionPairingDataOnCompanionFinish ref not exists` و`decryption fail` و`primary identity doesn't match` و`companion identity doesn't match` و`invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. هوية الجهاز الموقَّعة ADV

### 5.1 حقول Proto (found، من سلاسل تخطيط lite-proto)

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
| | | `deviceSignature` | **4** | bytes (يضبطه المرافق) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | تعداد |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | packed uint32 |
| | | `accountType` | **5** | تعداد |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (hosted فقط) |

أرقام الحقول وأنواع الأسلاك مقروءة من معلومات الرسالة المولَّدة؛ والأسماء تطابق رسائل ADV القياسية. أسماء التعداد: ‏`EnumC32116E1o` القيم E2EE 0، HOSTED 1، NON_E2EE 2.

### 5.2 بادئات التوقيع والخوارزميات

| البادئة | الثابت | البيانات الموقَّعة / الموثَّقة بـ MAC | الموقِّع | المستوى |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | توقيع الحساب: ‏`‖ details ‖ companion identity pub` | مفتاح هوية الأساسي | found |
| `06 05` | `A0G` | صيغة hosted من توقيع الحساب؛ وتُضاف أيضًا في بداية بيانات HMAC في hosted | مفتاح هوية الأساسي / adv secret | found |
| `06 01` | `A0H` | توقيع الجهاز: ‏`‖ details ‖ companion identity pub ‖ accountSignatureKey` | مفتاح هوية المرافق | found (جهة التحقق) |
| `06 06` | `A0I` | صيغة hosted من توقيع الجهاز | مفتاح هوية المرافق | found (جهة التحقق) |
| `06 02` | `A0J` | ‏`ADVSignedKeyIndexList`: ‏`‖ details` | مفتاح هوية الأساسي | found |
| `06 07` | `A0K` | إثبات non-E2EE ("hybrid") (`AeaUtils`)، وليس بادئة قائمة فهارس المفاتيح | مفتاح هوية الأساسي | found |

- أداة التوقيع: يحمّل `C38851hm.A00("best")` الصنف `org.whispersystems.curve25519.OpportunisticCurve25519Provider`؛ ‏`A03` = `calculateSignature(random 64 B, priv, msg)`، و`A01` = `verifySignature` (توقيع 64 بايت)، و`A02` = `calculateAgreement`. المفاتيح 32 بايت مع بايت نوع `5`. أي أنها توقيعات Curve25519 من مكتبة Signal curve25519 (على نمط XEdDSA، inferred من المكتبة لا من اسم الخوارزمية). اختيار المزوّد native أم Java يُحسم وقت التشغيل (unknown أيهما يُستخدم على جهاز معيّن).
- HMAC: ‏`HmacSHA256` عبر `javax.crypto.Mac` (`AbstractC38971i1.A00`).

### 5.3 قائمة فهارس المفاتيح

يبني `C24270w6.A01` الرسالة `ADVKeyIndexList`؛ و`validIndexes` مجموعة تتألف من (found): مدخل واحد لفتحة الأساسي (القيمة 0 حين لا يكون في وضع المرافق؛ شرط الفرع inferred)، و`adv_key_index` لكل جهاز مرافق مخزَّن (`CJY.A07`)، و`currentIndex`. يوقّع `A02` الصيغة `06 02 ‖ details`.

يدفعها `C24250w4.A00` هكذا:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

المهلة 32000 ms. البوابة `A02`: العلم **477** غير صفري، وجود أجهزة مرافقة (أو وضع المرافق)، وعدم الوجود في وضع المرافق. عند الفشل يزداد `adv_key_index_list_update_retry_count`؛ وإذا تجاوز **5** يسجّل التطبيق `adv-key-index-list-update … fails for more than 5 times` ويسجّل خروج جميع الأجهزة المرافقة (`C24270w6.A03`). النجاح يصفّر العدّادات (`A05`).

### 5.4 قاعدة الطابع الزمني (`C24270w6.A00`)

‏`last` = قيمة SharedPrefs ‏`adv_timestamp_sec`؛ و`now` = الساعة المصحَّحة بـ NTP، و`srv` = وقت الخادم. ‏`ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. إذا كان `last + 1 > now + 86400` فالقيمة غير صالحة (-1، وتُسجَّل `getTimestampSec invalid ts`)، ما يمنع الإقران بالرمز المحلي -8. رتيب (monotonic) لكل حساب (found).

### 5.5 التحقق على الشبكة (`C24230w2`)

لكل هوية جهاز يراها الأساسي (أجهزته المرافقة وأجهزة جهات الاتصال) يفحص بالترتيب (found):

1. مفتاح هوية الأساسي معروف (مخزَّن، أو `accountSignatureKey` من القائمة)، وإلا `no primary key`؛
2. مفتاح هوية المرافق قابل للتحليل (`0x05`+32 B)، وإلا `invalid companion public key`؛
3. توقيع الحساب على `prefix ‖ details ‖ companion identity`، وإلا `fail to verify account signature`؛
4. توقيع الجهاز على `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` (في hosted ‏`06 06`)، وإلا يُرفض الجهاز؛
5. قائمة فهارس المفاتيح: التوقيع على `06 02 ‖ details` بمفتاح الأساسي؛ ويجب أن يكون `adv timestamp` للقائمة متسقًا (`advTimestampMismatch` و`advListTimestampInvalid`)؛ فهرس مفتاح وارد غير مطابق يعيد ضبط الحالة المحلية (`incoming key-index not matching local state, resetting`)؛ وفهرس أكبر للجهاز نفسه موجود مسبقًا يُسقِط المدخل الأقدم (`filterDeviceWithKeyIndexList`).

---

## 6. قائمة الأجهزة والسجل والحدود

### 6.1 إشعار `devices` (يستقبله الأساسي)

‏`notification` مع عنصر ابن `add` أو `remove` (أي شيء آخر: `unknown type of device notification`). السمات والعناصر الابنة (found): ‏`device_hash`، و`device_lid_hash` اختياري مع `lid`، ومدخلات `device` (jid، وفهرس المفتاح)، و`key-index-list` اختياري (bytes، والسمتان `ts` و`expected_ts`). إذا حمل الإشعار السمة `offline` يُوضع المستخدم في الطابور للمزامنة لاحقًا؛ وإلا تعمل مهمة مزامنة (`SyncDeviceNotificationRunnable`). لا تُقبل القائمة إلا إذا لم يكن طابعها الزمني أقدم من `adv_timestamp_sec` المخزَّن (وإلا `local ts is larger than notification one`).

### 6.2 سجل الجهاز المخزَّن (جدول `devices`، ‏`C1h8`)

| المجموعة | الأعمدة (found) |
|-------|-----------------|
| الهوية | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| الوقت | `last_active`, `login_time`, `logout_time` |
| المزامنة | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| القدرات | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

قيم `platform_type` تأتي من `companion-props.platformType` (`EnumC25120ArW`): 0 UNKNOWN، 1 CHROME، 2 FIREFOX، 3 IE، 4 OPERA، 5 SAFARI، 6 EDGE، 7 DESKTOP، 8 IPAD، 9 ANDROID_TABLET، 10 OHANA، 11 ALOHA، 12 CATALINA، 13 TCL_TV، 14 IOS_PHONE، 15 IOS_CATALYST، 16 ANDROID_PHONE، 17 ANDROID_AMBIGUOUS، 18 WEAR_OS، 19 AR_WRIST، 20 AR_DEVICE، 21 UWP، 22 VR، 23 CLOUD_API، 24 SMARTGLASSES، 25 WAIL، 26 WASS، 27 BUSINESS_BACK_OFFICE، 28 WAIL_WAI، 29 WAIL_ALEXA، 30 AUTOMOTIVE (found).

### 6.3 الحدود والأعلام

| العلم / البند | المعنى | المستوى |
|-------------|---------|------|
| **15550** | عدد صحيح: الحد الأقصى للأجهزة المرتبطة (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: ‏`loggedInDeviceCount >= max` يمنع "ربط جهاز"؛ ويحصل ماسح QR على `at_device_limit` إضافي؛ ويرفض `OrbitCompanionLinkActivity` عند بلوغه) | found (الاستخدام)؛ القيمة الافتراضية unknown (abprop يسلّمه الخادم)؛ حقل المقاييس `md_linked_devices_max_devices_limit` موجود |
| **3816** | عدد الثواني التي يبقى فيها `companion_hello` صالحًا، بحد أقصى 360 ث | found |
| **477** | بوابة (غير صفر) لتحديثات قائمة فهارس المفاتيح | found |
| **18193** | يضيف `friction` (variant 1) إلى `challenges/supported` المعلَن | found (الاستخدام)؛ الأثر على الخادم unknown |
| **28161** | يضيف التحدي المعلَن الثاني (`passkey-create`) | ربط inferred (فقد المفكِّك الفرع) |
| **29500** | بوابة إقران hosted المستخدمة في فحص وضع الدفاع | found (قراءة)، المعنى inferred |
| **31019** | يضيف السمة `exclude_hosted_companion=true` إلى remove-all لبعض الأسباب | found |

هل يفرض الخادم الحد بمعزل عن فحص العميل: unknown. لا يوجد في الشيفرة المقروءة هنا مهلة خمول من جهة العميل للأجهزة المرافقة لدى الأساسي؛ وانتهاء صلاحية الأجهزة الخاملة من جهة الخادم unknown.

---

## 7. فكّ الربط (جهة الأساسي)

### 7.1 جهاز واحد

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

‏`C28905Ch6.A00`، المهلة 32000 ms. قد تحمل النتيجة عنصرًا ابنًا `coex_token` (يُمرَّر إلى معالج التواجد المشترك). فشل التسليم أو الخطأ يستدعي استدعاء الفشل بالرمز -1 (found).

### 7.2 جميع الأجهزة

‏`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

القائمة المحلية الفارغة تنتقل مباشرة إلى استدعاء النجاح. سلاسل الأسباب المرصودة في الشيفرة: `user_initiated` و`unknown_companion` و`invalid_adv_status` و`lid_migration_peer_sync_limit_exceeded` و`lid_migration_peer_sync_message_failed` و`lid_migration_missing_mappings_in_peer_sync_message` (found؛ قد تكون القائمة أطول، فتعبير المصدر مبتور).

### 7.3 محفِّزات فكّ الربط التلقائي (found)

| المحفِّز | السبب |
|---------|--------|
| فشل تحديث قائمة فهارس المفاتيح أكثر من 5 مرات | ‏`adv-key-index-list-update`، تسجيل خروج الكل |
| تجاوز فهرس المفتاح | إعادة ضبط `A03` |
| حالة ADV غير صالحة / جهاز مرافق غير معروف (`KZD` الحالة 43) | `invalid_adv_status` |
| انتقال نوع الحساب hosted ↔ E2EE | يُخرج جميع الأجهزة (سجل `handleADVMetadata`) |
| يرسل الخادم إشعار `devices` من النوع `remove` | يُزال السجل المحلي (inferred) |
| إجراء المستخدم في شاشة الأجهزة المرتبطة / `EavesdropMonitor/disconnectDevice` | ‏`user_initiated` (found للمراقب؛ مسار واجهة المستخدم inferred) |

إزالة الحساب بالكامل (`urn:xmpp:whatsapp:account` ‏`remove`) هي IQ مختلف ولا علاقة له بفكّ ربط الأجهزة المرافقة.

---

## 8. حالات الخطأ

### 8.1 رموز الخادم التي يعالجها `C44661Jem.A01`

| الرمز | الاستدعاء | واجهة المستخدم | المستوى |
|------|----------|----|------|
| **465** | `Blp` ← `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` ← `onCompanionTooOld` | حالة "companion too old" | found |
| 404 / 405 / 443 / 445 | عام `C2w` | ربط السلاسل `C44648JeY`: للرمزين 405 و443 نصوص مخصصة؛ والرموز 404/405/443/445 تشترك في عنوان واحد | found (السلاسل بالمعرّف)؛ المعنى الدقيق لـ 404/443/445 unknown |
| غير ذلك | عام `C2w` | فشل الإقران | found |

يسمّي `InstrumentationAuthActivity` رموز النتائج 1 `CONSUMER_SMB_CROSS_PAIRING`، 2 `UNSUPPORTED_PRIMARY_VERSION`، 3 `INVALID_QR_CODE`، 4 `COMPANION_PLATFORM_RESTRICTED`، 5 `COMPANION_TOO_OLD`، 6 `MAX_DEVICE_LIMIT_REACHED`، وما عدا ذلك `PAIRING_FAILED` (found). ربط 405 من الخادم بحالة consumer/SMB هو inferred من معرّف السلسلة.

### 8.2 الرموز المحلية

| الرمز | السبب | الإصلاح |
|------|-------|-----|
| -8 | الطابع الزمني المحلي لـ ADV غير صالح (الساعة مقابل آخر ts مخزَّن + 1) | صحّح وقت الجهاز؛ سلسلة واجهة المستخدم "invalid device time" |
| -9 | QR يفتقد مفتاح الهوية / adv secret | استخدم QR حديثًا |
| -10 | إقران hosted على بناء consumer | لا ينطبق |
| -13 | عدم تطابق المنصة مع علم hosted | لا ينطبق |
| -17 | إقران آخر قيد التنفيذ | انتظر؛ يعيش الطلب حتى 32 ث |
| -20 | طلب الخادم challenges (`retry-after-challenges`) | أكمل تحدي friction / passkey |
| -1 | لم يُرسَل طلب الإزالة أو فشل | أعد المحاولة |

### 8.3 إخفاقات رمز الربط

| العَرَض (السجل) | السبب |
|--------------|-------|
| `companion hello is null or expired` | كُتب الرمز بعد انتهاء الصلاحية (العلم 3816، بحد أقصى 360 ث) |
| `decryption fail` (hello) | رمز خاطئ (يختلف مفتاح PBKDF2؛ وAES-CTR بلا وسم، فالرمز الخاطئ ينتج مفتاحًا عشوائيًا يُكشف في خطوات لاحقة؛ inferred) |
| `primary identity doesn't match` | بُنيت الحزمة لمفتاح أساسي آخر |
| `companion identity doesn't match` | الإشعار والحزمة غير متفقين |
| `invalid-primary-adv-key-length` / `adv public key is 0` | فحوص بدور المرافق على المفتاح المؤقت للأساسي |

---

## 9. فروق أساسية

### 9.1 ما لا يجب الخلط بينه

| A | B |
|---|---|
| `pair-device` يرسله **الأساسي** (هذا التقرير) | `pair-device` **يستقبله** تطبيق بدور المرافق (المعالج `AbstractC40501kw`، المعرّف 242، ويحمل مراجع QR) |
| `ADVSignedDeviceIdentity` (موقَّع، بلا HMAC) | `ADVSignedDeviceIdentityHMAC` (الغلاف المرسَل في `device-identity`) |
| العنصر الابن `device-identity` في `pair-device` (غلاف HMAC) | العنصر الابن `device-identity` في stanzas الرسائل الصادرة (هوية الحساب يرفقها المرافق؛ التفضيل `adv_signed_identity`) |
| توقيع الحساب (مفتاح الأساسي، البادئة `06 00`) | توقيع الجهاز (مفتاح المرافق، البادئة `06 01`) |
| بادئة قائمة فهارس المفاتيح `06 02` | ‏`06 07` (إثبات non-E2EE) |
| ‏`pub-key` في QR / ‏`companion_server_auth_key_pub` | مفتاح هوية المرافق (الذي يحصل على توقيع الحساب) |
| ‏`rawId` (معرّف على مستوى الحساب يتغير عند إعادة الضبط) | ‏`keyIndex` (لكل جهاز مرافق) |
| محرف منصة QR (`EnumC26332BbY`) | ‏`DeviceProps.platformType` على الشبكة (`EnumC25120ArW`)، بترقيم مختلف |

### 9.2 جهاز hosted

معرّف جهاز JID ‏**99** (`device_id should be 99 for hosted device`)، وعلامة التسجيل/إلغاء الإقران `hosted_device_pairing`، وبادئات التوقيع `06 05` / `06 06`، و`exclude_hosted_companion`. يرفض الأساسي إقران جهاز hosted في هذا البناء (محلي -10). كل ما عدا هذه السلاسل unknown.

### 9.3 Shortcake

قد يسرد `retry-with-method` العنصر `shortcake-with-passkeys`؛ عندها يخزّن التطبيق مفتاح تسليم ويبدّل واجهة المستخدم. يعرض `ShortcakeJni` الدوال `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` و`nativeResponderStart/Finish` (found). نص المصافحة native ولم يُفكّ هنا: unknown.

### 9.4 Friction / وضع الدفاع

يعلن `pair-device` عن التحديات المدعومة ويعيد `completed` منها عند إعادة المحاولة. يقرر الأساسي محليًا طلب friction حين يكون وضع الدفاع مفعّلًا (`C271211x.A0N()`) ولم يكتمل تحدي friction بعد؛ ويُتخذ هذا القرار قبل أول IQ (`defense mode friction triggered`). سياسة جهة الخادم التي ترسل `retry-after-challenges` غير مرئية (unknown).

### 9.5 لا إثبات من جهة العميل للجهاز المرافق

لا شيء في حمولة pair-device يثبت أي برنامج يشغّله المرافق: ‏`ref` و`pub-key` ومفتاح الهوية وadv secret ومحرف المنصة كلها مُعلَنة ذاتيًا من QR. ما تثبته التوقيعات هو أن حساب الأساسي هذا خوّل مفتاح الهوية ذاك. أي فحص "عميل رسمي" يتم في جهة الخادم (حكم 465 يُعالَج فقط في جهة العميل).

### 9.6 شيفرة دور المرافق في APK نفسه (موجز)

| البند | النتيجة |
|------|---------|
| العناصر الابنة لـ IQ ‏`companion_hello` | `link_code_pairing_wrapped_companion_ephemeral_pub`، `companion_server_auth_key_pub`، `companion_platform_id`، `companion_platform_display`، `link_code_pairing_nonce`؛ والسمة `should_show_push_notification` (found، `C0YS`) |
| الرمز | ‏`K1T.A00` base32 لـ 5 بايتات عشوائية (4.3) |
| تدوير QR | IQ ‏`pair-device-rotate-qr` بالسمات `stage` ‏0/1/2 و`sentinel` اختياري، والعنصر الابن `ref` |
| IQs واردة من نوع md | ‏`pair-device` و`pair-success` و`ref` و`companion_reg_refresh` و`integrity` (المعرّفات 242 و243 و266 و278 و279) |
| محتوى `pair-success` ورد المرافق `pair-device-sign` | لم يُتتبَّعا في هذا البناء: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

قورن بالمصدر المحلي؛ فقط التطابقات وفرق واحد جرى فحصه على الجانبين.

| البند | APK 2.26.41.6 | `baron-baileys-v2` | النتيجة |
|------|---------------|--------------------|--------|
| حمولة QR | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | تطابق (4 حقول) |
| اشتقاق رمز الإقران | PBKDF2-SHA256 ‏131072 تكرارًا، الأبجدية `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`، الأبجدية نفسها (`crypto.js`، `generics.js`) | تطابق |
| حزمة المفاتيح | ‏`[salt32 ‖ nonce12 ‖ GCM]`، info هو `link_code_pairing_key_bundle_encryption_key`، النص الصريح identity ‖ identity ‖ random32 | التخطيط نفسه (`messages-recv.js`) | تطابق |
| adv secret | ‏HKDF(zero salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | تطابق |
| غلاف HMAC | ‏HMAC-SHA256(adv secret, [06 05 for hosted ‖] ADVSignedDeviceIdentity bytes) | نفسه (`validate-connection.js`) | تطابق |
| رسائل توقيع الحساب / الجهاز | ‏`06 00 ‖ details ‖ companionIdentity`؛ ‏`06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | نفسها | تطابق |
| بادئة قائمة فهارس المفاتيح في hosted | يستخدم المدقّق والموقِّع `06 02` لكل قائمة؛ و`06 07` هي بادئة إثبات non-E2EE | ‏`WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` تُستخدم حين `accountType == HOSTED` (`chats.js`) | **يختلف**؛ مسار hosted لا يُمارَس في بناء consumer هذا، فأثر الاختلاف unknown |

لا يُقدَّم أي ادعاء "لماذا يفشل": مرافق Baileys الذي يتبع الصفوف المتطابقة متسق مع ما يحلله الأساسي هنا؛ وقبول الخادم غير قابل للتحقق بالتحليل الساكن.

---

## 11. المسارات الكاملة

### 11.1 مسار QR

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

### 11.2 مسار رمز الإقران

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
