<!-- src-sha1: 4ca6293d8bc9da2aebc5db6f104c88b12dce1bd0 -->
# WhatsApp Client Integrity — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** سلامة عميل Android وإثباته — إثبات مفتاح Keystore ("blacknoise")، وPlay Integrity (واجهة Java القياسية وواجهة native الكلاسيكية)، ومكتبة token الأصلية WASafe، وstanzas `integrity_payload` / `keystore_attestation`، ومعامل التسجيل `gpia`، والتحقق الذاتي من توقيع التطبيق، وflag مصدر التثبيت، والقياس عن بعد لـ root / المحاكي / العميل المعدّل (`wam_daily`)، وما هو مُتحكَّم به مقابل ما يُبلَّغ عنه فقط، وما يبقى unknown

---

## 1. ما هي "سلامة العميل" في هذا الإصدار

لا توجد بوابة واحدة. ينتج العميل عدة أدلة وإشارات مستقلة؛ وكل واحدة منها تُنشأ على الجهاز وتُرسل إلى الخادم. لم يُعثر على كود من جهة العميل يرفض العمل على عميل معدّل أو مُجذَّر (rooted) أو أُعيد توقيعه. كل العبارات تحليل ثابت لـ APK المفكوك (`versionCode 264100600`). المستويات: **found** = قُرئ في الكود، **inferred** = مستنتج، **unknown** = لا يمكن حسمه ثابتًا.

الأسماء المشوَّشة خاصة بكل إصدار وأعيد حلّها من سلاسل ثابتة في 2.26.41.6.

| الآلية | تنتج | تُرسل بوصفها | استخدام الخادم |
|-----------|----------|---------|-----------|
| إثبات مفتاح Keystore، وسم السجل الداخلي `blacknoise` (`C25730yT`) | سلسلة شهادات DER لمفتاح EC من `AndroidKeyStore` مع تحدّي الإثبات | stanza `<ib><keystore_attestation>`؛ تسليم وقت التسجيل إلى native؛ ومساري passkey واقتران الجهاز المرافق | unknown (غير قابل للملاحظة) |
| Play Integrity، واجهة Java القياسية (`C45007Jkc`) | Standard Integrity token (`gpia`) | معامل تسجيل HTTP باسم `gpia`؛ وtoken اقتران الجهاز المرافق ("md-pairing") | unknown |
| Play Integrity، واجهة native الكلاسيكية (`libwhatsapp.so`، `WAJIntegrityGpiaStatusRequest`) | Classic Integrity token عبر JNI | `<ib><integrity_payload>` (المصب في Java found؛ والصلة بالمنتِج native inferred) | unknown |
| WASafe (`libwasafe.so`, `libwasafedeps.so`) | كتلة مشفرة بأسلوب ECIES للبيانات التي يمررها المستدعي، base64 | المصب unknown | unknown |
| التحقق الذاتي من توقيع التطبيق (`AbstractC38241gg`, `C27965CCj`) | قيمة 0/1 | سمة WAM المشتركة **6251** | unknown |
| flag مصدر التثبيت (`CHH`) | قيمة منطقية لمُثبِّت `com.android.vending` | سمات WAM `install_source_official`، **10255** | unknown |
| flags حالة الجهاز (`Cdt` → `C0Fp`) | `is_rooted`, `is_genymotion`, `is_monkeyrunner_running`, `is_using_custom_rom`, `is_whatsapp_plus_user` | حدث WAM `wam_daily` | unknown |
| تشخيصات الدعم (`C00L.A0F`) | وسم "rted" | سلاسل التواصل مع الدعم / تقرير التصحيح | للدعم فقط |

ليست إثبات سلامة العميل، فلا تخلط بينها (انظر 11): `com.whatsapp.integrityai` (كشف الاحتيال على الجهاز)، و `bizintegritysignals`، وواجهة حظر WFAC (`com.whatsapp.waffle.wfac`)، وربط الحسابات (`com.whatsapp.waffle`).

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| إثبات Keystore | `C25730yT` | زوج المفاتيح، وسلسلة الشهادات، والتوقيع (`A00`/`A01` الاسم المستعار، `A02` توليد، `A03` السلسلة، `A07` توقيع) |
| enum وضع الإثبات | `C02U` | `C02U.A00` = ديناميكي، `C02U.A01` = ثابت |
| runnable مُرسِل الـ stanza | `RunnableC48591z1` الحالة 3 عبر `C41141ly` | يرسل `keystore_attestation` |
| معالج الاتصال | `A01` في معالج الاتصال (`smali/X/0Yq`) | يجدول `sendKeystoreAttestation` |
| عمل وقت التسجيل | `C25810yb`, `KZ2` الحالة 39, `K49.A0s` | إثبات ثابت إلى native، الوسم `regtime_ka` |
| تسخين مسبق للجهاز المرافق | `H1K` (إثبات)، `H1J` (Play Integrity) | تخزين السلسلة / الـ token مؤقتًا للاقتران |
| غلاف Play Integrity | `C45007Jkc` | تحضير + طلب بالواجهة القياسية |
| HTTP التسجيل | `K49` | يضيف `gpia` إلى معاملات الطلب |
| جسر JNI | `com.whatsapp.wamsys.JniBridge` | `sendAttestationResult`، واستدعاءات `jnidispatch*`، و`wsafeplatform_context` |
| بوابة التوقيع | `AbstractC38241gg` | نافذة إصدار + SHA-1 لشهادة التوقيع |
| مُحقِّق التوقيع | `C27965CCj` | اسم الحزمة + SHA-256 لشهادة التوقيع مقابل القيم المضمّنة |
| future مصدر التثبيت | `CHH` | `install_source_official` |
| حدث WAM اليومي | `C0Fp` (`getEventNameForFalco()` = `wam_daily`) | flags الجهاز |
| مالئ flags WAM | `Cdt` (smali) | يملأ قيم `C0Fp` المنطقية |
| مساعدات root / المحاكي | `C00L` | `A0F` root، `A0C` محاكي، `A0B` ROM مخصص، `A0D` أتمتة الاختبار |

---

## 2. إثبات مفتاح Keystore ("blacknoise")

### 2.1 توليد المفتاح (`C25730yT.A02`)

كله خلف ab-prop **1934** (`A06()`، الافتراضي `true`).

| البند | القيمة | المستوى |
|------|-------|------|
| Keystore | `AndroidKeyStore` | found |
| غرض المفتاح | `4` (`PURPOSE_SIGN`)، digests ‏`SHA-256` و `SHA-512`، مصادقة المستخدم غير مطلوبة | found |
| الخوارزمية | ab-prop **2076**، الافتراضي `"EC"`؛ و `"RSA"` يضيف حشو `PKCS1` | found |
| خوارزمية التوقيع | ab-prop **2075**، الافتراضي `"SHA256withECDSA"` | found |
| أساس الاسم المستعار | ab-prop **2074**، الافتراضي `the_well_of_wishes_awaits_in_the_crypt_of_decay`؛ والاحتياطي المضمّن `my_personal_mini_pony` عندما تكون الخاصية null | found |
| الاسم المستعار | ديناميكي: `<base>[_<suffix>]`؛ ثابت: `<base>_static[_<suffix>]`؛ اللاحقة = UUID عشوائي مخزّن في prefs ‏`ka_key_store_dynamic_alias_suffix` / `ka_key_store_static_alias_suffix`، يُدوَّر عندما يجد التجديد لاحقة موجودة | found |
| صلاحية الشهادة | now + ab-prop **2079** ثانية (الافتراضي 86400) | found |
| تحدّي الإثبات | يُضبط فقط على SDK >= 24 | found |
| إثبات خصائص الجهاز | `setDevicePropertiesAttestationIncluded(true)` على SDK >= 31؛ وعند `ProviderException` يُعاد بدونه (السجل `blacknoise/disbabling device ids att`) | found |

تخطيط تحدّي الإثبات (found):

```
challenge = BE64(unix_seconds) ‖ 0x1F ‖ nonce
nonce     = caller-supplied bytes, else SecureRandom(ab-prop 2078 bytes, default 32)
```

### 2.2 التحديث والتقييد

| Pref / prop | المعنى | الافتراضي | المستوى |
|-------------|---------|---------|------|
| `ka_refresh_ts` + ab-prop **2079** | يُعاد إنشاء المفتاح الديناميكي عندما يكون أقدم من هذا | 86400 s | found |
| `ka_static_refresh_ts` + ab-prop **4878** | تحديث المفتاح الثابت | 600 s | found |
| `ka_retried_ts` + ab-prop **2427** | ديناميكي: محاولة التجديد مبكرة جدًا -> السجل `regeneration attempted too soon, waiting` | 600 s | found |
| `A04()` | يحذف الاسمين المستعارين ويصفّر كل prefs ‏`ka_*` | – | found |

### 2.3 سلسلة الشهادات (`C25730yT.A03`)

`keyStore.getCertificateChain(alias)`، وكل شهادة `getEncoded()` (DER)، تُدمج بترتيب معكوس (الجذر أولًا، والورقة أخيرًا) في مصفوفة بايتات واحدة. السلسلة الفارغة تسجّل `empty list of certificates found`. تُبلَّغ الإخفاقات إلى مُبلِّغ الأخطاء باسم `attestation-creation` و `attestation-nocertchain` و `attestation-nosign` (found). يُسجَّل التوقيت باسم `att-gen` / `att-sign` (found).

### 2.4 التوقيع (`C25730yT.A07`)

`Signature.getInstance(prop 2075)` على حمولة من المستدعي بالمفتاح الثابت. إدخال المفتاح المفقود -> `attestation-nosign` "cannot sign payload, att pair missing". لم يُعثر على مستدعي `A07` في الكود المفكوك (فجوات في الفك محتملة)؛ وموضع إرسال التوقيع unknown.

### 2.5 أربعة مستهلكين للسلسلة

| # | المُشغِّل | الوضع | Nonce | المصب | المستوى |
|---|---------|------|-------|------|------|
| 1 | اتصال الخادم (`handleConnected` في معالج الاتصال، اسم الـ job ‏`sendKeystoreAttestation`) | ديناميكي (`C02U.A00`) | المفتاح العام الثابت للعميل (Noise) (`C25710yR.A0H()`) | `<ib><keystore_attestation>chain</keystore_attestation></ib>` عبر `C10140Tq.A0X(node, 6)` | found |
| 2 | التسجيل (`K49.A0s`، الـ job ‏`regtime_ka`، runnable ‏`KZ2` الحالة 39) | ثابت (`C02U.A01`) | المفتاح العام الثابت للعميل | `JniBridge.jvidispatchIOO(1, ctx, chain)` إلى native، مع إعادة محاولة/تراجع (ab-props **2863** 1000 ms، **2864** 5 محاولات)؛ و `K49.A0s` ينتظر حتى ab-prop **4696** (1880 ms) عند الطلب | found (استخدام native unknown) |
| 3 | بدء تسجيل الجهاز المرافق (`C0YS` ‏`startcompanionreg` -> `H1K.A00`) | ديناميكي | المفتاح العام الثابت للعميل | مخزّن مؤقتًا في `H1K` (الحقل `A02`)، يُحدَّث بمساعد على نمط `KeyAttestationLifetimeManager`؛ خلف ab-props ‏**6430** (الافتراضي `true`)، **7217** (bucket)، الفاصل **6431** (600000 ms)، المحاولات **6433**/**6434** | found (التخزين المؤقت)؛ مستهلك البايتات المخزّنة غير محسوم: unknown |
| 4 | واجهة passkey على الخادم (`I16` الحالة 18، `PasskeyServerApiImpl`) | ديناميكي | بايتات يوفرها الخادم | تُعاد إلى مستدعي passkey | found (ما يفعله المستدعي unknown) |

بوابة الـ stanza للحالة #1: `A06()` و ab-prop **1935** (الافتراضي `true`)، ومرة واحدة على الأكثر لكل ab-prop **2067** ثانية (الافتراضي 86400)، تُخزَّن في pref ‏`ka_stanza_sent_ts`. السلسلة الفارغة (null) تسجّل `blacknoise: got null attestation chain in custom stanza` ولا ترسل شيئًا (found).

شكل الـ stanza (found):

```
<ib>
  <keystore_attestation>[binary: DER certs, root first]</keystore_attestation>
</ib>
```

`keystore_attestation` هو أيضًا رمز قاموسي (القاموس الثاني، `AbstractC40911lb.A01[0]`)، فيُرمَّز كرمز على الشبكة (found).

الربط: لأن الـ nonce في #1 إلى #3 هو المفتاح العام الثابت لـ Noise الخاص بالعميل، يحمل امتداد التحدي في سلسلة الشهادات مفتاح الهوية، فيربط مفتاح العتاد بالمفتاح الثابت للحساب (inferred من اختيار الـ nonce؛ فحص الخادم unknown).

---

## 3. Play Integrity

### 3.1 واجهة Java القياسية (`C45007Jkc`)

| البند | القيمة | المستوى |
|------|-------|------|
| الواجهة | `IntegrityManagerFactory.createStandard` -> `StandardIntegrityManager` | found |
| رقم مشروع السحابة | `293955441834` (`PrepareIntegrityTokenRequest.setCloudProjectNumber`) | found |
| التحضير (`A00(callback, tag)`) | موسوم بتسمية؛ يُتخطى إذا كان موفّر token موجودًا؛ يرفض دون شبكة؛ بحد أقصى 5 تحضيرات كل 60 s (pref ‏`pref_gpia_prepare_call_count_in_last_interval`) | found |
| الطلب (`A01(callback, nonce, tag)`) | `StandardIntegrityTokenRequest.setRequestHash(nonce)`؛ يفشل بالرمز 1003 إن لم يوجد موفّر | found |
| رموز الأخطاء الداخلية (`JCX`) | 1001 لا شبكة، 1002 استدعاءات تحضير كثيرة، 1003 غير مُحضَّر، 1004 مهلة (`C47238Kk7`)، 1005 لا مفتاح ثابت (`Kmc`) | found |
| أحداث مُبلِّغ الأخطاء (`GKY`) | `ka_at_md_generate_attestation`, `gpia_at_md_prepare`, `gpia_at_md_generate_attestation` | found |

مواضع استدعاء التحضير (found): `RegisterPhone` (الوسم `register_phone`)، `VerifyPhoneNumber` (الوسم `verify_phone`)، اقتران الجهاز المرافق (الوسم `md-pairing`، `H1J`)، إضافة إلى مسار إعادة محاولة في `C41354Hz3`.

### 3.2 معامل HTTP للتسجيل `gpia`

`K49.A0V` يضيف حقلًا واحدًا إلى خريطة طلب HTTP للتسجيل:

```java
if (!flag(3753)) return;               // default false
nonce = Base64(static_public_key, NO_PADDING|NO_WRAP);   // C47343Kmc case 48
token = request(nonce, tag="reg");     // timeout ab-prop 4263, default 1800
map.put("gpia", token);
```

| البند | القيمة | المستوى |
|------|-------|------|
| البوابة | ab-prop **3753**، الافتراضي `false` | found |
| Nonce | base64 (flags 3) للمفتاح العام الثابت للعميل (`C25710yR.A0H()`)؛ مفتاح null -> الخطأ 1005 | found |
| يُضاف في | `checkIfExists` (مساران في الكود)، `verifySecurityCode` | found |
| طلبات أخرى (طلب الرمز، التسجيل النهائي) | `A0V` لا تُستدعى هناك في الكود المفكوك | found (غياب في الفك) |
| مقياس التوقيت | `gpia-param-prepare` | found |

الافتراضي `false` يعني أن المعامل لا يُرسل إلا عندما يفعّل الخادم الخاصية 3753. وهل يشترطه خادم التسجيل: unknown.

### 3.3 token اقتران الجهاز المرافق

`H1J` (خلف `A07(...)`، الخاصية **7006** الافتراضي `false`، الفاصل **7007** = 21600000 ms) يحضّر ("md-pairing") و `I16` الحالة 3 تطلب token بـ nonce = base64(المفتاح العام الثابت، flags 3)، ومهلة الخاصية **7010** (1000 ms). تُسجَّل الإخفاقات باسم `gpia_at_md_prepare` / `gpia_at_md_generate_attestation`. مستهلك الـ token غير محسوم (unknown).

### 3.4 واجهة native الكلاسيكية و `integrity_payload`

سلاسل في `libwhatsapp.so` (found): `WAJIntegrityGpiaStatusRequest`, `WAJIntegrityGpiaStatusRequestAttributes`, `_WAJIntegrityTriggerGPIAWithRequestAttributes`, `_WAJIntegritySendResponseOrRetry`, `_WCAAPIGenerateGPIAParamOnMain`، وتواقيع JNI لـ `IntegrityManagerFactory.create(Context)` و `IntegrityTokenRequest.Builder` (`setNonce`, `setCloudProjectNumber`) و `IntegrityManager.requestIntegrityToken`. إذن يقود كود native بنفسه Play Integrity (الطلب الكلاسيكي) عبر JNI.

المصب في Java (found):

```java
// JniBridge.jnidispatch... case 3  (callback "sendAttestationResult")
node = <ib><integrity_payload>{string}</integrity_payload></ib>   // C10140Tq.A0X(node, 194)
metric type "safety-net-attestation", result "success"/"failed"
```

سلسلة نوع المقياس `safety-net-attestation` تسمية قديمة؛ ولا تُستخدم واجهة SafetyNet (انظر 10). العبارة "native ‏`WAJIntegrityGpiaStatusRequest` ينتج سلسلة `integrity_payload`" هي **inferred** من الأسماء؛ ولم تُتتبع سلسلة الاستدعاء داخل كود native المجرّد. وما الذي يطلق طلب حالة native (جدول من العميل أم طلب من الخادم) unknown.

يقرأ native الـ ab-props عبر `jnidispatchIII(feature, kind)`؛ المعرّفات المعيَّنة (found): النوع 0: 12->13178، 13->13456، 15->22925، 16->24048؛ النوع 1: 13->13455. و `jnidispatchO(1)` تُرجع سلسلة ab-prop ‏**10266** (الافتراضي فارغ). الغرض من هذه الخصائص unknown.

### 3.5 مستخدمو Play Integrity الآخرون

| الفئة | الاستخدام | المستوى |
|-------|-----|------|
| عائلة `JK4`, `KM0` | reCAPTCHA Enterprise SDK ‏(`recaptcha.net`) بـ `StandardIntegrityManager` خاص به؛ تذهب النتيجة إلى معامل HTTP ‏`recaptcha` (`K49.A0Z`) عند وجودها | found |
| `KLL`, `KLN`, `C42885In8`… | تنفيذ Play Core integrity مضمّن (كود مكتبة) | found |

---

## 4. مكتبة WASafe native

### 4.1 جهة Java

| الخطاف | السلوك | المستوى |
|------|-----------|------|
| `jnidispatchI(4)` | يحمّل `libwasafe.so` (`"wasafe"`)، ويسجّل `WCAAPIEnsureSafeLibraryLoaded libwasafe.so load failed` عند `UnsatisfiedLinkError` | found |
| `jnidispatchI(5)` | يُرجع pref ‏`runtime_override` من SharedPreferences ‏`wsafeplatform_context`، وإلا الثابت `1090327562` | found |
| سمة WAM ‏**15611** | الثابت نفسه، يُكتب كسلسلة `1090327562` في السمات المشتركة | found |

معنى `1090327562` unknown (مرشح: قيمة runtime / نوع كشف في WASafe، غير متحقق منه).

### 4.2 `libwasafe.so` (14480 بايت، arm64، مجرّد من الرموز)

الصادرات: `WASafeSignalsCreate`, `WASafeSignalsConfigure`, `WASafeSignalsPrepare`, `WASafeSignalsGetBase64EncodedData`, `WASafeSignalsRelease`, `WASafeStatus`. الواردات: libc (`stat`, `rand`, `srand`, `gettimeofday`, `malloc`…) و `WASafeDepsCrypto*` من `libwasafedeps.so`.

| الدالة | السلوك المفكوك | المستوى |
|----------|---------------------|------|
| `WASafeSignalsConfigure(x)` | تخزّن `x` (نوع الكشف) في متغير عام، وتمسح متغيرًا عامًا ثانيًا | found |
| `WASafeSignalsPrepare()` | تكتب ثابت الحالة `0x1092` في متغير عام؛ ولا عمل آخر | found |
| `WASafeSignalsGetBase64EncodedData()` | تمرر بيانات/طول السياق عبر التشفير+base64 (`sub_6a00`) وتُرجع `{ptr, len}` | found |

هذا الإصدار من `libwasafe.so` لا يحوي جمع إشارات: لا سلاسل root أو مصحح أو hook أو محاكي أو مسارات ملفات، وواردة نظام الملفات الوحيدة هي `stat`. كما تحوي `libwhatsapp.so` سلسلة `WASafeSignalsStub` والدالة `WAIntegrityPrepareSafeSignals(WASafeDetectionType)` بوسمي السجل `safesignals/prepare` و `safesignals/generate` (found). مصدر البيانات التي تُشفَّر unknown.

### 4.3 `libwasafedeps.so`

الصادرات `WASafeDepsCryptoInputCreate`, `...SetServerPublicKey`, `...SetData`, `...EncryptBase64`, `...ResultGetData/GetLength/Release`؛ الواردات mbedtls (`ctr_drbg`, `entropy`, `gcm_setkey`, `gcm_crypt_and_tag`). البنية (found من الواردات والأسماء): مفتاح مؤقت عشوائي، وسر مشترك مع مفتاح عام للخادم، وAES-GCM، وbase64. لم يُعد فك المنحنى الدقيق وKDF لهذا الإصدار؛ وبناء Curve25519 ECDH + AES-GCM هو **inferred**. قيمة المفتاح العام للخادم وتدويره: unknown.

---

## 5. التحقق الذاتي من توقيع التطبيق ومصدر التثبيت

### 5.1 البوابة (`AbstractC38241gg.A00`)

```java
long vc = versionCode;
if (vc < 264100600 || vc > 264100608) return 0;          // outside window
sha1 = Base64(SHA-1(signatures[0]), 11);
return "OKD31QX-GP7GT780Psqq8xDb15k".equals(sha1) ? 1 : 0;
```

تبدأ نافذة الإصدار عند `versionCode` لهذا الإصدار (264100600). تُخزَّن النتيجة مؤقتًا في متغير static.

### 5.2 المُحقِّق (`C27965CCj.A00(pkg, certBytes)`)

| الخطوة | السلوك | المستوى |
|------|-----------|------|
| 1 | اسم الحزمة مُقنَّع بـ XOR بمفتاح من 5 بايتات ويُقارن بمصفوفتي بايتات مضمّنتين تُفكّان إلى `com.whatsapp` و `com.whatsapp.w4b` | found |
| 2 | إذا لم تكن الحزمة أيًّا منهما: تُرجع `true` فورًا | found |
| 3 | وإلا SHA-256 لبايتات الشهادة، مُقنَّع بـ XOR ويُقارن بقيمتين مضمّنتين من 32 بايتًا؛ تطابق -> `false`، عدم تطابق -> `true` | found |

فشل فك هذه الدالة؛ والخطوات قُرئت من تفريغ التعليمات.

### 5.3 المستهلك

داخل WAM ‏`initializeCommonAttributes` (runnable ‏`RunnableC29340CoR`):

```java
long r = AbstractC38241gg.A00(ctx);          // 1 only when version window + SHA-1 match
if (r == 1) r = verifier(pkg, cert) ? 0 : 1;
common attribute 6251 = r;                   // 1 = both checks passed, 0 = otherwise
```

إذن **6251 = 1** تعني "شهادة التوقيع تطابق قيم WhatsApp المضمّنة" (found)؛ و 0 تعني عدم تطابق أو إصدارًا خارج النافذة (found). تُبلَّغ القيمة في القياس عن بعد فقط. لا شيء في العميل يتفاعل معها (لم يُعثر على مسار كود يقرأ النتيجة للحظر أو التخفيض). استخدام الخادم: unknown.

### 5.4 مصدر التثبيت

`getInstallSourceInfo().getInstallingPackageName()` (SDK >= 30، وإلا `getInstallerPackageName`) يُقارن بـ `com.android.vending` (`C18970md`, `RunnableC29340CoR`): يُخزَّن في future ‏`CHH.A01`. يُبلَّغ كسمة WAM ‏**10255** وكـ `install_source_official` في مجموعات سمات التسجيل (`HO4`, `C08650Nr`, `AbstractC35718FdU`). وكذلك الحقل `install_source` في `C0Fp` (`wam_daily`). استخدامات منفصلة للمقارنة نفسها تختار مُثبِّت وحدة Voltron (`AbstractC12860bs`) (found). النتيجة قياس عن بعد مع توجيه تنزيل الوحدات؛ ولا إنفاذ.

---

## 6. إشارات root والمحاكي والعميل المعدّل

### 6.1 flags الجهاز في `wam_daily`

`C0Fp` هو حدث `wam_daily` (`getEventNameForFalco()`)؛ وحقوله أدناه تُملأ في `Cdt` (smali). مُبلَّغ عنها، غير مُنفَّذ بها (found).

| الحقل | المصدر | المستوى |
|-------|--------|------|
| `is_rooted` | `C00L.A0F(telephony helper)` | found |
| `is_using_custom_rom` | `C00L.A0B()` (سلاسل النواة/المصنّع/العرض: cyanogen, debug, Darky, XDAndroid, MIUI…) | found |
| `is_whatsapp_plus_user` | ينجح `Class.forName("org.acra.ACRA")` (الفئة غائبة من هذا APK؛ تُضمَّن عادة بواسطة عملاء الأطراف الثالثة) | found (الفحص)؛ "تُضمَّن عادة" inferred |
| `is_genymotion` | فحص حزمة لمنطقة `com.genymotion.superuser` في `Cdt`؛ الشرط الدقيق متتبَّع جزئيًا | found (الفحص)، المنطق inferred |
| `is_monkeyrunner_running` | المصدر غير محسوم | unknown |
| `google_play_services_available`, `google_play_services_version`, `install_source` | موجودة في الحدث نفسه | found |

### 6.2 استدلال root في `C00L.A0F`

مخزّن في متغير static. صحيح عند تحقق أي مما يلي: `Build.TAGS` يحوي `test-keys`؛ ‏`/system/app/Superuser.apk` موجود؛ ملف `su` قابل للتنفيذ في `/system/bin/su` أو `/system/xbin/su` (`canExecute`)، مع تسجيل إضافي `app/dly`؛ منتج/طراز/مصنّع شبيه بالمحاكي (`sdk`) أو عدم وجود SIM/telephony (الـ flag ‏`z` يُستخدم للاحقة السجل فقط، found). المساعدات ذات الصلة: `A0C` محاكي (العلامة/الجهاز `generic`، و `goldfish`، و `ranchu`، و `google_sdk`، و `Emulator`، و `Android SDK built for x86`، و `Genymotion`)، و `A0D` أتمتة الاختبار (خاصية النظام `fb.running_sapienz`).

### 6.3 أين تُستهلك `A0F`

| المستهلك | الاستخدام | المستوى |
|----------|-----|------|
| باني تقرير التصحيح `C10V` | يلحق `DC-RTED` (root) و `DC-BACRM` (ROM مخصص) بنص التشخيص | found |
| خريطة تشخيصات التواصل مع الدعم `C1Z` | المفتاح `diagnostic` = `rted ` (و `nw-wap ` إذا كان `org.acra.ACRA` موجودًا) | found |
| `C28049CFz` (حالة تدفق التحقق) | سياق التواصل مع الدعم `register-phone-rtd` في شاشة رقم الهاتف | found |
| `Cdt` | `wam_daily.is_rooted` | found |
| `KH2` (مُبلِّغ الأعطال `lacrima`) | `ExtraDeviceInfoCollector` يكتب flag الـ root (`test-keys` و `Superuser.apk` و `su` على `PATH`) في تقارير الأعطال | found |

لا شيء من هذه يحجب التسجيل أو المراسلة (found: لا فرع ينهي التدفق بناءً على هذه القيم المنطقية). وهل يزن الخادم flags ‏`wam_daily`: unknown.

### 6.4 غير موجود

| الفحص | النتيجة |
|-------|--------|
| سلاسل Magisk وXposed (`de.robv`) وSubstrate وFrida في كود WhatsApp (`libwhatsapp.so`، Java) | غير موجودة |
| `ro.kernel.qemu`، فحص ذاتي لـ `FLAG_DEBUGGABLE` | غير موجود |
| قائمة حزم محظورة لعملاء معدّلين مسمّين (GB, FM, Plus) | غير موجودة |
| فحص ذاتي لـ CRC الخاص بـ dex / الأصول | غير موجود في هذه الجولة (لم يُبحث بشكل شامل) |
| فحص المفتاح المدعوم بالعتاد (`KeyInfo.isInsideSecureHardware`) في كود الإثبات الخاص بـ WhatsApp نفسه | غير موجود (فقط في فئات المكتبات `BinderC48420LDc`, `C51962N8y`) |
| `FetchIntegritySignals`, `IntegrityChallengeResponse`, `relax_integrity_constraints_for_bb_wa_tenured_accounts` | غير موجودة في أي مكان من APK (Java, smali, assets, native) |
| واجهة `SafetyNet` | غير موجودة |

`isDebuggerConnected` تظهر فقط في كاشف ANR (`SigquitBasedANRDetector`) ومساعدات الأعطال.

---

## 7. feature flags و ab-props

| المعرّف | القيمة / الافتراضي | ما يتحكم فيه |
|----|-----------------|----------|
| **1934** | `true` | البوابة الرئيسية لـ blacknoise (`C25730yT.A06`) |
| **1935** | `true` | إرسال stanza ‏`keystore_attestation` بعد الاتصال |
| **2067** | 86400 | الحد الأدنى للثواني بين إرسالات الـ stanza |
| **2074** | `the_well_of_wishes_awaits_in_the_crypt_of_decay` | أساس الاسم المستعار للمفتاح |
| **2075** | `SHA256withECDSA` | خوارزمية التوقيع |
| **2076** | `EC` | خوارزمية المفتاح |
| **2078** | 32 | طول الـ nonce العشوائي |
| **2079** | 86400 | صلاحية الشهادة وثواني التحديث الديناميكي |
| **2427** | 600 | الحد الأدنى للثواني بين التجديدات الديناميكية |
| **4878** | 600 | ثواني التحديث الثابت |
| **2863** / **2864** | 1000 / 5 | أساس التراجع وقت التسجيل (ms) / المحاولات |
| **4696** | 1880 | انتظار التسجيل للإثبات (ms) |
| **3753** | `false` | معامل التسجيل `gpia` |
| **4263** | 1800 | مهلة طلب `gpia` |
| **6430** | `true` | تسخين مسبق لإثبات الجهاز المرافق (`H1K`) |
| **6431** | 600000 | عمر ذاكرة إثبات الجهاز المرافق المؤقتة (ms) |
| **6433** / **6434** | 5 / 1000 | محاولات / مهلة مدير عمر إثبات الجهاز المرافق |
| **7217** | 1 | معامل bucket لإثبات الجهاز المرافق |
| **7006** | `false` | تسخين مسبق لـ Play Integrity للجهاز المرافق (`H1J`) |
| **7007** | 21600000 | عمر ذاكرة token الجهاز المرافق المؤقتة (ms) |
| **7009** / **7010** | 5 / 1000 | محاولات / مهلة Play Integrity للجهاز المرافق |
| **10266** | سلسلة فارغة | سلسلة تُسلَّم إلى native عبر `jnidispatchO(1)` |
| **26215** | `false` | مسار بديل لـ verifySecurityCode في `K49` (غير خاص بالسلامة) |

الافتراضيات هي القيم المضمّنة وقت الترجمة؛ ويمكن للخادم تجاوز ab-props (found: جدول الخصائص؛ قيم الخادم unknown).

---

## 8. حالات الخطأ

| العَرَض | السبب | الحل / ملاحظة |
|---------|-------|-----------|
| لا stanza ‏`keystore_attestation` | الخاصية 1934 أو 1935 false؛ أُرسل خلال آخر 2067 s؛ سلسلة null | بالتصميم |
| تقرير خطأ `attestation-creation` | فشل توليد المفتاح (`ProviderException`، لا TEE) | يُعاد لاحقًا، مقيَّد بـ 2427 |
| `attestation-nocertchain` | فشل `getCertificateChain` أو فارغ | – |
| `attestation-nosign` | استُدعيت `A07` دون إدخال مفتاح ثابت | – |
| `blacknoise/regeneration attempted too soon, waiting` | `ka_retried_ts` ضمن 600 s | انتظر |
| `blacknoise: not boostrapped for reg` | `C25810yb.A00` false وقت التسجيل | يُتخطى الإثبات لذلك التسجيل |
| Play Integrity ‏1001 / 1002 / 1003 / 1004 / 1005 | لا شبكة / > 5 تحضيرات لكل 60 s / غير مُحضَّر / مهلة / لا مفتاح ثابت | رموز داخلية (`JCX`) |
| `gpia` مفقود في طلب التسجيل | الخاصية 3753 false أو فشل الطلب (نتيجة null توضع فارغة) | انظر 3.2 |
| `libwasafe.so load failed` | `UnsatisfiedLinkError` | يُسجَّل فقط |
| سمة التوقيع 6251 = 0 | APK أُعيد توقيعه، أو شهادة مختلفة، أو إصدار خارج `264100600..264100608` | قياس عن بعد فقط |

---

## 9. Baileys / عملاء البروتوكول

| البند | العبارة | المستوى |
|------|-----------|------|
| فحوص جهة التطبيق | عميل بروتوكول خالص لا يشغّل أي كود مما سبق | found (بالتعريف) |
| stanzas ‏`keystore_attestation` / `integrity_payload` | العميل الذي يحذفها لا يرسلها ببساطة؛ وهل يرفض الخادم هذه الحسابات أو يقيّدها أو يعلّمها: unknown | unknown |
| معامل التسجيل `gpia` | اختياري افتراضيًا (الخاصية 3753 ‏`false`)؛ الإنفاذ على الخادم لكل منطقة/حساب: unknown | unknown |
| تزوير الإثبات | يجب أن تنتهي السلسلة بجذور العتاد/Google وتحمل التحدي؛ لا سر في العميل لنسخه، والتحقق يقع على الخادم | inferred |
| خطر معروف | سياسة الخادم تعتمد على بيانات لا يستطيع هذا التقرير ملاحظتها (السلوك، عمر الحساب) | unknown |

الحل: لا شيء قابل للاشتقاق ثابتًا. إرسال قيم مفبركة غير مدعوم بأي دليل وُجد هنا.

---

## 10. فروق أساسية

| لا تخلط بين | الحقيقة |
|----------------|------|
| سلسلة المقياس `safety-net-attestation` و SafetyNet | تسمية فقط؛ الحمولة تأتي من Play Integrity؛ ولا توجد واجهة SafetyNet في الكود |
| `keystore_attestation` و `integrity_payload` | stanzas مختلفة: سلسلة شهادات DER (بايتات) مقابل سلسلة token لـ Play Integrity؛ ومنتِجان مختلفان (Java/Keystore مقابل native/Play) |
| `gpia` في Java (الواجهة القياسية، request hash) و GPIA الكلاسيكي في native | واجهتان ومصبّان مختلفان (معامل HTTP مقابل `<ib>`)؛ بناء nonce في متغير native لم يُتتبع |
| الإثبات الثابت مقابل الديناميكي | الاسم المستعار الثابت `..._static` (التسجيل)، والاسم المستعار الديناميكي (بعد الاتصال، الجهاز المرافق، passkey) |
| Nonce | المفتاح العام الثابت للعميل في ثلاثة مستهلكين؛ وبايتات الخادم في مستهلك passkey |
| `blacknoise` و WASafe | إثبات Keystore (Java) مقابل مكتبة native لكتلة مشفرة |
| WASafe و "signals" | `libwasafe.so` في هذا الإصدار لا تجمع شيئًا؛ الاسم يوحي بإشارات، والكود لا |
| 6251 و 10255 | تطابق التوقيع مقابل مُثبِّت Play |
| `is_whatsapp_plus_user` وقائمة سماح لعملاء معدّلين | فحص فئة انعكاسي واحد؛ لا توجد قائمة سماح |
| `integrityai`, `bizintegritysignals` | ميزات سلامة المحتوى / الأعمال (كشف الاحتيال، واجهة إشارات الأعمال)، وليست إثبات عميل |
| WFAC / `waffle` | واجهة الحظر وربط الحسابات، وليست مكوّن إثبات |
| الإبلاغ مقابل الإنفاذ | كل نتائج root والمحاكي والتوقيع والمُثبِّت التي وُجدت هي قياس عن بعد أو نص دعم |

---

## 11. مكونات ذات صلة ليست إثبات عميل

| المكوّن | الحقائق | المستوى |
|-----------|-------|------|
| `com.whatsapp.integrityai` | `IntegrityAiOrchestrator`, `ScamDetectorImpl`، تنزيل النماذج (`IntegrityAiModelDownloadCoordinator`، فئة الجهاز)، واجهة الاشتراك `ScamDetectionSettingsActivity`؛ وسم مخزن النتائج `IntegrityAi/ScamDetectionResultStore`؛ مصنِّف native باسم `kaleidoscope` لم يُعاد التحقق منه في هذا الإصدار | found (البنية)؛ الجزء native unknown |
| `com.whatsapp.bizintegritysignals` | جالب GraphQL ومدير لإشارات سلامة الأعمال المعروضة في الواجهة | found |
| `com.whatsapp.waffle.wfac` | واجهة قرار الحظر (`WfacBanActivity`, `WfacBanDecisionFragment`, `WfacUnbanDecisionFragment`) | found |
| `com.whatsapp.waffle.accountlinking` وما يجاورها | ربط الحسابات، وSSO، والنشر المتقاطع، وفحص العمر | found |

---

## 12. المسار الكامل

```
[Registration screens: RegisterPhone / VerifyPhoneNumber]
    │  C45007Jkc.A00  prepareIntegrityToken (cloud project 293955441834, tag register_phone / verify_phone)
    │  K49.A0s  "regtime_ka": C25730yT.A03(static)  nonce = static pubkey
    │      └── JniBridge.jvidispatchIOO(1, ctx, chain)  ──►  [native wamsys]  (use unknown)
    ▼
[K49 HTTP: exist / verifySecurityCode]
    │  if ab-prop 3753:  gpia = standard-API token, requestHash = b64(static pubkey)
    ▼
[WA registration server]  (validation not observed)

[Connected session]
    │  handleConnected ─► job "sendKeystoreAttestation"
    │  ab-props 1934 && 1935, once per 86400 s
    │  C25730yT.A03(dynamic, nonce = static pubkey) ─ AndroidKeyStore EC key, challenge = ts ‖ 0x1F ‖ nonce
    ▼
<ib><keystore_attestation>DER chain, root first</keystore_attestation></ib>
    ▼
[WA server]  (use unknown)

[Native libwhatsapp]  WAJIntegrityGpiaStatusRequest ─► classic IntegrityManager via JNI   (inferred link)
    │  JniBridge callback sendAttestationResult
    ▼
<ib><integrity_payload>token</integrity_payload></ib>   (node code 194)
    ▼
[WA server]  (use unknown)

[Companion pairing]
    │  C0YS startcompanionreg ─► H1K (chain cache) + H1J (GPIA token, tag md-pairing)
    ▼  consumer of cached bytes/token: unknown

[Telemetry, daily and common attributes]
    │  6251 signature match, 10255 Play installer, 15611 wasafe constant
    │  wam_daily: is_rooted, is_genymotion, is_using_custom_rom, is_whatsapp_plus_user, install_source
    ▼
[WA server]  (use unknown)
```

---

## 13. Unknowns

| السؤال | لماذا unknown |
|----------|-------------|
| تحقق الخادم وإنفاذه لأي token | جهة الخادم، لم تُلاحظ حركة شبكة |
| ما الذي يطلق `WAJIntegrityGpiaStatusRequest` في native وكيف يُبنى الـ nonce | كود native المجرّد لم يُتتبع (مفكّك المكتبة الكبيرة غير متاح هنا) |
| مصدر بيانات مدخلات WASafe ومعنى `1090327562` | لم يُعثر على منتِج في native المجرّد |
| استخدام native لبايتات الإثبات وقت التسجيل | مدخل JNI فقط (`jvidispatchIOO(1)`) مرئي |
| مستهلكو السلسلة المخزّنة في `H1K` وtoken ‏`H1J` | مواضع الاستدعاء غير محسومة في الكود المفكوك |
| معنى ab-prop ‏10266 ومعرّفات ميزات `jnidispatchIII` | قيم فقط |
| مصدر `is_monkeyrunner_running`، والشرط الدقيق لـ `is_genymotion` | لم يُتتبع |
| مستدعو `C25730yT.A07` (التوقيع) | لم يُعثر على أي منها؛ فجوات في الفك محتملة |
| هل يوجد أي إنفاذ لـ flags القياس عن بعد | لم يُعثر على فرع في العميل؛ الخادم unknown |
