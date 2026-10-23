<!-- src-sha1: 95a792ca8e841aadc06a8e3fae785590574c4eba -->
# WhatsApp نقل Noise — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** نقل الدردشة في Android (chatd): نقاط الاتصال وتسلسل الاتصال، وتوجيه edge، وتأطير TCP، ومصافحة Noise XX / IK / PQ، وفحوص سلسلة الشهادات، وClientPayload (UserAgent وDevicePairingData ونوع الاتصال / سببه)، وتشفير النقل والعدّادات، وترميز العقد الثنائي، ونتيجة تسجيل الدخول وأكواد الفشل، وkeepalive، وتراجع إعادة الاتصال (backoff)، وstream:error، وأعلام الميزات، والنواقل ذات الصلة (Tigon HTTP وDistribGW وقناة Tigon Noise وMQTT)، ومقارنة مع Baileys

---

## 1. ما هو (تقنيًا)

chatd هو الاتصال الوحيد طويل العمر الذي يحمل كل stanza (الرسائل والإيصالات وIQ والحضور والإشعارات). في Android هو مقبس TCP عادي (وليس WebSocket) يشغّل مصافحة Noise، ثم إطارات AES-GCM مسبوقة بالطول، يحمل كل منها عقدة واحدة مرمّزة ثنائيًا. كل ما يرد هنا مصدره التحليل الساكن لـ APK المفكَّك؛ ولم يُلتقط أي شيء على الشبكة. المستويات: **found** = مقروء في الكود، **inferred** = مستنتج، **unknown** = غير محلول. الأسماء المشوّشة (obfuscated) خاصة بكل بناء وأُعيد حلّها في 2.26.41.6.

| الطبقة | الاسم في 2.26.41.6 | الدور |
|-------|----------------|------|
| خيط الاتصال | `HandlerThreadC12340b0` (وسم السجل `ConnectionThread`) | الاتصال، المصافحة، تسجيل الدخول، حلقة القراءة، قطع الاتصال |
| تسلسل الاتصال / DNS | `C37151de` (الحالات)، `C37031dS` (`A0G` للتقدّم، `A0D` مصنع المقبس)، `C36881dC`، `AbstractC47101wK` (جدول مضمّن من المضيف إلى IP)، `C36821d6` (عناوين IP الاحتياطية) | أي مضيف / منفذ / وكيل (proxy) يأتي تاليًا |
| مشغّل المصافحة | `C38791hg` (سجلات `NoiseSocket/*`) | بايتات المقدمة، ClientHello، ServerHello، فحوص الشهادات، ClientFinish |
| حالة Noise | `C38921hv` (+ `C38941hx` للـ hash، `C38981i2` لـ AES-GCM، `AbstractC38961i0` لـ HKDF)، `C40331kf` (مفاتيح النقل + العدّادات) | Java خالص |
| إدخال/إخراج الإطارات، مرمّز العقد | `C38891hs` / `C38901ht`؛ `C40411kn` (المرمِّز)، `C24610wf` (فاكّ الترميز)، `AbstractC40911lb` (القاموس) | التأطير، XML ثنائي |
| Protos | `C39211ii`، `C39161id`، `C39231ik`، `C39241il` (المصافحة)؛ `C24843Amz`، `C24842Amy`، `C24841Amx`، `C25757B9r`، `BC0` (الشهادات)؛ `C38001fP`، `C38051fp`، `C38661hS` (الحمولة) | رسائل السلك |
| الثقة، PQ | `AbstractC44011qk` (الجذر المثبّت)؛ `C38811hi`، `AbstractC38821hj`، `AbstractC38831hk`، `C38761hd` (إعداد PQ، مفاتيح الخادم الساكنة) | هوية الخادم، هجين ML-KEM-512 |
| بانِي الحمولة | المساهمون في `AbstractC43901qZ` يجمعهم `C37991fK` | ClientPayload |
| Keepalive، المؤقتات، إعادة الاتصال | `C14U` (`ClientPingManager`)، `C9EN` (ping IQ)، `HandlerC21850s9`، `C11380Yq` (`MessageHandler`)، `C0X9` (backoff) | ping، المهلات، إعادة المحاولة |
| التحكم الوارد | `C40581l4` (`<ib>`)، `C40601l6` / `C37961fH.A1B` (`stream:error`) | إشعارات الخادم |

نقاط تحسم بقية التقرير:

- آلة حالة Noise وHKDF وAES-GCM وترميز الإطارات كلها **Java**. فقط Curve25519 (`org.whispersystems.curve25519`، `OpportunisticCurve25519Provider`، native مع بديل Java) واستدعاءات ML-KEM (`KEMKeyPair.generateNative`، `KEMSecretKey.decapsulateNative`) هي native. لا يوجد تنفيذ native لـ chatd لإجراء هندسة عكسية عليه (found).
- ترويسة المقدمة هي الثابت `WA 06 03` في هذا البناء (القسم 3.1). عدد إصدار البروتوكول الممرَّر إلى `C38791hg` مثبّت على 6 في موضع الاستدعاء الوحيد، لذا فإن فرع الشهادة المسطّحة للإصدار 5 غير قابل للوصول عمليًا (found؛ قابلية الوصول inferred من موضع الاستدعاء الثابت الوحيد).
- لا يرسل `devicePairingData` إلا اتصال بلا JID للمستخدم، وهو ما لا يسمح به `ConnectionThread` إلا في تسجيل الجهاز المرافق (companion). وهو ليس أثرًا من آثار تسجيل الهاتف الأساسي في هذا البناء (القسم 6.4).
- الـ stanzas الصادرة في مسار الإرسال الرئيسي مضغوطة بـ DEFLATE (الأعلام `3`)، وليس الواردة فقط (القسم 8.1).

---

## 2. نقاط الاتصال وتسلسل الاتصال

### 2.1 المضيفات والمنافذ (found)

| المضيف | الموضع | ملاحظات |
|------|-------|-------|
| `g.whatsapp.net` | `C37151de` الخطوتان 5 و9؛ `C36881dC.A01` (عناوين IP مضمّنة) | مضيف الدردشة الأساسي |
| `g-fallback.whatsapp.net` | الخطوتان 13 و14 | المضيف الثاني |
| `e1` ... `e16.whatsapp.net` | `C37151de.A0F` (16 إدخالًا)، الخطوتان 7 و11 | `ConnectionSequence/getEdgeHost`؛ اختيار عشوائي، أو المضيف المخزَّن في السجل |
| جدول IP المضمّن | `AbstractC47101wK.A00`، الخطوتان 6 و10 | يربط المضيف بقائمة IP، ويغطي مضيفات `eN` و`g.whatsapp.net` |
| قائمة `<ib><fbip>` | `C40581l4` إلى `C36821d6.A02` | عناوين IP مفصولة بفواصل، يحفظها مدير الاحتياط (مدخل الخطوتين 2 / 8، inferred) |
| وكيل المستخدم / SOCKS | الخطوة 12، `C48201yM` | `java.net.Proxy.Type.SOCKS`، مهلة الاتصال 30000 ms |

المنافذ: 443 و5222 (اختيار عشوائي لكل محاولة، `C37151de.A00`؛ ويسحب المُنشئ أيضًا رمية عملة واحدة ترتّب المنافذ للخطوتين 3 و4)، و80 لخطوات `:80`. يُعاد استخدام منفذ آخر اتصال ناجح عندما يكون العلم **33512** مفعّلًا (found).

### 2.2 حالات التسلسل (found، `C37151de.A02`، التقدّم في `C37031dS.A0G`)

| الخطوة | الهدف |
|------|--------|
| 0 | البداية، تختار أول خطوة قابلة للتطبيق |
| 1 | `InetSocketAddress` للتنقيح / التجاوز (طرفية) |
| 2 | إدخالات نقاط الاتصال المقدَّمة من الخادم والتي يكون فيها البت `A04` مضبوطًا (القائمة `A0A`)، واحدًا تلو الآخر؛ لكل إدخال بت TLS خاص به `A05` |
| 3, 4 | سلسلة المضيف المهيّأة `A07` على المنفذين (443 / 5222 بترتيب عشوائي) |
| 5 | `g.whatsapp.net` على 443 (العلم **20801**) أو 443 / 5222 عشوائيًا |
| 8 | إدخالات مقدَّمة من الخادم بلا البت `A04` (القائمة `A09`)؛ ترتيب الفروع في الكود المفكَّك غير واضح |
| 9 | `g.whatsapp.net:80` |
| 15 | HISTORY: إعادة محاولة الخطوة / المضيف / المنفذ المخزَّن من آخر نجاح (يُدرج بعد 9 عندما تكون خطوة السجل صالحة والعلم **22916** معطّلًا) |
| 13, 14 | `g-fallback.whatsapp.net` على 443 / 5222، ثم `:80` |
| 6, 10 | IP مضمّن لـ `g.whatsapp.net`، ثم `:80` |
| 7, 11 | مضيف edge عشوائي `eN.whatsapp.net`، ثم `:80` |
| 12 | وكيل المستخدم (طرفية) |
| 16 | استُنفدت الخيارات |

الترتيب بعد الخطوة 9 (found): 9، [15]، 13، 14، 6، 10، 7، 11، 16. يُخزَّن آخر نجاح في التفضيلات `last_successful_connection_step` و`_host` و`_port` (found، `C37031dS.A00`). تسجّل الخطوات 2 إلى 4 `Skipping sequence ... due to active proxy` ما دام إعداد خدمة SOCKS نشطًا والعلم **23630** معطّلًا (دلالة التخطي inferred).

### 2.3 المقبس (found، `C37031dS.A0D`)

| الجانب | القيمة |
|--------|-------|
| المقبس | TCP عادي؛ Happy Eyeballs عند وجود عناوين IPv4 وIPv6 معًا (`ConnectionSocketFactory/try_connect/using-happyEyeball`) |
| غلاف TLS | يختار بت الإعداد `A07` مصنع `SSLSocketFactory`؛ يُضبط لكل إدخال مقدَّم من الخادم (`A05`)، وللخطوة 1 على المنفذ 443، ولمضيفات edge (الخطوة 7) على المنفذ 443. تُنشأ الخطوة 5 (`g.whatsapp.net`) والبت معطّل |
| مهلة المقبس | 30000 ms تُضبط عبر `CeF(30000)` (الدلالة inferred: مهلة قراءة) |
| TCP keepalive | `configureTcpKeepalive`: عندما يكون العلم **7831** مفعّلًا ويدعمه المقبس، يُفعَّل keepalive وتُطبَّق ثلاثة أعداد صحيحة من الأعلام **7832** (الافتراضي 2) و**7833** (الافتراضي 10) و**7834** (الافتراضي 10) (idle / interval / count بالاستنتاج) |
| تخزين الإخراج مؤقتًا | عندما يكون العلم **33751** مفعّلًا، يُغلَّف الكاتب بـ `BufferedOutputStream` لتخرج بايتات المقدمة وClientHello في كتابة واحدة (found) |

كون نقاط الاتصال المغلّفة بـ TLS تحمل بايتات Noise نفسها داخل TLS أمر inferred من مسار الكود (يتلقى `C38791hg` تدفقات فقط)؛ ويوجد مقياس باسم `chatd_non_secure_tls_wrapper_resumption` في مكتبة native.

### 2.4 حل DNS (found)

يُبلَّغ عن `DNSResolutionMethod` في `ClientPayload.dnsSource` (القسم 6.5): `SYSTEM` و`GOOGLE` و`HARDCODED` و`OVERRIDE` و`FALLBACK` و`MNS` و`MNS_SECONDARY` و`SOCKS_PROXY`. يضبط العلم **13545** (سلسلة؛ القيم `secondary` و`hardcoded` و`none` يتعرّف عليها `C37151de.A01`) سلسلة المحلِّل. تُستخدم الإجابات المخزنة مؤقتًا من عمليات بحث سابقة حتى انتهاء صلاحيتها قبل إجراء بحث جديد (`C36881dC.A03`).

---

## 3. التأطير

### 3.1 البايتات قبل أول إطار (found، `C38791hg`)

```
[ 'E' 'D' 00 01 | len24 | routing_info ]     only when routing_info is non-empty
[ 'W' 'A' 06 03 ]                             always
[ len24 | HandshakeMessage{clientHello} ]     first frame
```

- ترويسة edge: السحر `45 44 00 01` (`C38791hg.A0B`)، ثم طول الكتلة في 3 بايتات big-endian، ثم بايتات `routing_info` (تفضيل، base64 بلا حشو أو التفاف؛ يخزّنه `C38801hh.A00`، بحد أقصى 256 بايتًا: "The routing info should be smaller than 256 bytes."). خام على المقبس، خارج نص Noise (transcript).
- المقدمة: `57 41 06 03` = "WA"، البروتوكول 6، القاموس 3 (`C38791hg.A04`)؛ وهي أيضًا prologue الخاص بـ Noise (4.2). يعيد فرع else القيمة `57 41 05 03`، لكن المُنشئ يثبّت الإصدار على 6.

### 3.2 بنية الإطار (found)

كل إطار هو طول من 3 بايتات big-endian (`AbstractC38721hZ.A04` / `A00`؛ يجب أن تكون الكتابات أقل من 2^24، وإلا `data too large to write`) يتبعه الجسم: protobuf المصافحة أثناء المصافحة، ونص AES-GCM المشفَّر بعدها.

القارئ (`C38891hs`): 3 بايتات طول بالضبط، ثم الجسم. أثناء قراءة ServerHello، إذا كانت بايتات الطول الثلاثة تساوي ASCII `GOA` (`47 4F 41`، `C38891hs.A01`) يُطلق `X.1sn` (السجل `socket/goaway`)؛ أما مسار القراءة بعد المصافحة (`C24610wf.Be0`) فلا يحتوي على هذا الفحص. تُتخطى الإطارات المفكوكة الفارغة؛ وإطار مفكوك من بايت واحد يُطلق `header only frame received`. يُطلق stanza يتجاوز حد الحجم الاختياري (`InterfaceC40421ko.AqJ`) الاستثناء `C31990DyW` عند الترميز.

### 3.3 رسائل المصافحة (found، أرقام الحقول من أصناف protobuf)

| الرسالة (الصنف) | الحقول (الرقم بالخط العريض) |
|-----------------|-------------------------|
| `HandshakeMessage` (`C39211ii`) | clientHello **2**, serverHello **3**, clientFinish **4** |
| `ClientHello` (`C39161id`) | ephemeral **1**, static **2**, payload **3**, useExtended **4**, extendedCiphertext **5**, paddedBytes **6**, sendServerHelloPaddedBytes **7**, simulateXxkemFs **8**, pqMode **9**, extendedEphemeral **10** |
| `ServerHello` (`C39231ik`) | ephemeral **1**, static **2**, payload **3**, extendedStatic **4**, paddingBytes **5**, extendedCiphertext **6** |
| `ClientFinish` (`C39241il`) | static **1**, payload **2**, extendedCiphertext **3**, paddedBytes **4**, simulateXxkemFs **5** |

المُعيِّنات (setters) الظاهرة في المشغّل: ClientHello الكامل لـ XX يضبط `ephemeral` (+ `pqMode` في متغيرات PQ)؛ وClientHello الاستئنافي يضبط `ephemeral` و`static` و`payload` و`extendedCiphertext` و`extendedEphemeral` و`pqMode`؛ وClientFinish يضبط `static` و`payload` و`extendedCiphertext`. حقول الحشو والمحاكاة معرَّفة لكن لم يُعثر على مُعيِّن لها في المشغّل (الاستخدام unknown).

---

## 4. مصافحة Noise

### 4.1 أسماء الأنماط (found، الحقول الساكنة في `C38921hv`)

| الثابت | الاسم | يُستخدم عندما |
|----------|------|-----------|
| `A07` | `Noise_XX_25519_AESGCM_SHA256` (محشو بـ NUL حتى 32 بايتًا) | مصافحة كاملة، PQ معطّل |
| `A0H` | `Noise_IK_25519_AESGCM_SHA256` (محشو حتى 32) | استئناف بمفتاح الخادم الساكن المخزَّن، PQ معطّل |
| `A06` | `Noise_XXfallback_25519_AESGCM_SHA256` | رفض الخادم لـ IK (4.4) |
| `A0E`, `A0C`, `A08` | `Noise_XXkem_`، `Noise_XXkem-FS_`، `Noise_XXkemEph_` + `25519_MLKEM512_AESGCM_SHA256` | كاملة، PQ مفعّل |
| `A0F`, `A0D`, `A0G` | `Noise_IKkem+`، `Noise_IKkem-FS+`، `Noise_IKkem2+` + `X25519+MLKEM512+AESGCM256+SHA256` | استئناف، PQ مفعّل |
| `A09`, `A0B`, `A0A` | `Noise_XXkemfallback_`، `Noise_XXkem-FSfallback_`، `Noise_XXkemEphfallback_` + `25519_MLKEM512_AESGCM_SHA256` | احتياطات PQ |

الاسم الأطول من 32 بايتًا يُهشَّر بـ SHA-256، وإلا فالقيمة المحشوة بطول 32 بايتًا هي الـ hash الابتدائي (found، مُنشئ `C38921hv`).

إعداد PQ (`NoisePQConfig`): الوضع `NONE` / `ENABLE` / `ENFORCE` (العلم **20161**، عدد صحيح: 1 تفعيل، من 2 إلى 4 إلزام، وغير ذلك لا شيء)؛ المتغير `IKKEM` و`IKKEM_FS` و`XXKEM_EPH_IKKEM2` و`XXKEM_EPH_ONLY` (العلم **34536**، سلسلة، الافتراضي `IKKEM`). المصافحة الكاملة: وضع PQ `NONE` يستخدم `A07`؛ وإلا فالمتغير `IKKEM_FS` يختار `A0C`، و`XXKEM_EPH_ONLY` و`XXKEM_EPH_IKKEM2` يختاران `A08`، و`IKKEM` يختار `A0E` (found في مُنشئ `C38791hg`). تقترن أسماء `IKkem*` بمسار الاستئناف؛ ولم يُتتبَّع تعيين متغيراتها بدقة.

### 4.2 الحالة المتناظرة (found، `C38921hv`)

```
h  = name (padded, or SHA256(name) if > 32 bytes)         // C38941hx.A00 = name
ck = h                                                    // A02
h  = SHA256(h || prologue)                                // prologue = WA 06 03
mixHash(d):  h = SHA256(h || d)
mixKey(dh):  okm = HKDF-SHA256(salt = ck, ikm = dh, info = none, 64)
             ck  = okm[0:32] ; k = AES-256-GCM key okm[32:64] ; n = 0
encrypt(p):  c = AES-GCM(k, iv = 00000000 || n_be64, aad = h, p) ; n++ ; mixHash(c)
decrypt(c):  p = AES-GCM(k, iv = 00000000 || n_be64, aad = h, c) ; n++ ; mixHash(c)
             (no key yet: encrypt / decrypt pass through and only mixHash)
split():     okm = HKDF-SHA256(salt = ck, ikm = empty, info = none, 64)
             sendKey = okm[0:32] ; recvKey = okm[32:64]
```

HKDF مكتوب يدويًا (`AbstractC38961i0`): extract = `HMAC(key = salt, data = ikm)`، وexpand بعدّاد من بايت واحد. IV: 12 بايتًا، أول 4 أصفار، وآخر 8 هي العدّاد big-endian (`AbstractC38721hZ.A02`). الوسم (tag) 128 بت (GCM على نمط BouncyCastle `C39061iT`). DH هو Curve25519 `calculateAgreement` عبر `C38851hm.A00("best")`.

### 4.3 تسلسل XX الكامل (found)

| # | الاتجاه | المحتوى | عمليات الحالة |
|---|-----------|---------|------------------|
| 1 | C إلى S | `ClientHello{ephemeral}` (+ `pqMode` في متغيرات PQ) | `mixHash(e_c)` |
| 2 | S إلى C | `ServerHello{ephemeral, static, payload}` | `mixHash(e_s)`؛ `mixKey(DH(e_c, e_s))`؛ `s_s = decrypt(static)`؛ `mixKey(DH(e_c, s_s))`؛ `cert = decrypt(payload)` |
| 3 | محلي | فحوص الشهادة (القسم 5) | يجب أن يساوي المفتاح في الشهادة `s_s` |
| 4 | C إلى S | `ClientFinish{static, payload}` | `static = encrypt(s_c)`؛ `mixKey(DH(s_c, e_s))`؛ `payload = encrypt(ClientPayload)` |
| 5 | محلي | split | `sendKey` و`recvKey`، وكلا العدّادين 0 |

يطابق الترتيب في `C38791hg.A03` (smali) نص XX القياسي. يأتي `s_c` الساكن للعميل والـ ephemeral من أزواج المفاتيح `C38711hY`؛ ويوفّر `C38771he.A01` المفتاح الساكن (مفتاح Noise الدائم للعميل، "authKey" في سجلات قطع الاتصال). أما كونه مساويًا للمفتاح المرفوع عند التسجيل فهو inferred.

### 4.4 الاستئناف (IK) والاحتياط (found للبنية، تفاصيل الخطوات inferred)

عند وجود مفاتيح خادم ساكنة مخزَّنة (`C38771he.A00` غير null، `C38761hd`) يسجّل المشغّل `NoiseSocket/handshakeStart mode=... rs=...` ويشغّل `handshakeResume`: يُدخَل المفتاح العام الساكن المخزَّن للخادم في الحالة بالـ hash (`C38921hv.A06`)، ويحمل ClientHello الـ ephemeral والساكن المشفَّر للعميل و`ClientPayload` المشفَّر في رسالة واحدة (القسم 3.3). إذا ردّ الخادم بمفتاح ساكن، فالسجل هو `handshakeResume server hello has static key, falling back` ويطلق `C38791hg` الاستثناء `X.1t8` حاملًا ServerHello، وهو ما يختار أسماء `Noise_XXfallback_*`. نص الاحتياط الدقيق inferred من معدِّل الاحتياط القياسي في Noise. تُحفظ مفاتيح الخادم الساكنة بعد تسجيل دخول ناجح عندما تتغير (`A1m`: المفتاح الكلاسيكي عبر `Ce3`، ومفتاح PQ عبر `Ce2`).

### 4.5 مادة ما بعد الكم (found كموجودة؛ تفاصيل السلك unknown جزئيًا)

- KEM: ML-KEM-512 (سلسلة الخوارزمية `MLKEM512`، `C38791hg.A0C`). TLV للمفتاح العام PQ للخادم: النوع `0x02`، الطول 800؛ ترويسة TLV من النوع `0x01` تحمل اسم الخوارزمية؛ TLV النص المشفَّر FS من النوع `0x04`، الطول 768 (من سلاسل الأخطاء `Expected TLV PK type 0x02` و`length 800` و`Expected TLV header type 0x01` و`Expected FS ciphertext length 768`).
- التغليف (`C38921hv.A07`): تُنتج `KEMPublicKey.A00()` النص المشفَّر + السر المشترك؛ يمر النص المشفَّر عبر `mixHash` والسر المشترك عبر `mixKey`. فك التغليف: `KEMSecretKey.decapsulateNative`.
- التسليم: يُقرأ `<success static_pq_key="base64">` فقط عندما لا يكون وضع PQ `NONE` ويكون المتغير `IKKEM_FS` (`A18`)؛ وبدونه يكون السجل `handshake missing serverStaticPQ forcing full handshake` (`C38791hg.A01`).

عرض حقل الطول في TLV والموضع الدقيق داخل `ServerHello.payload` لم يُفكّا. تأتي دوال ML-KEM native من أصناف Signal KEM؛ والمكتبة التي تنفّذها لم تُحدَّد.

---

## 5. فحوص شهادة الخادم (found، `C38791hg.A03`)

يحلّل إصدار البروتوكول 6 (القيمة الوحيدة المستخدمة) `ServerHello.payload` على أنه `CertChain`:

`CertChain` (`C24843Amz`): leaf **1**, intermediate **2**. كل منهما `NoiseCertificate` (`C24842Amy`): details **1** (bytes)، signature **2** (bytes). يُحلَّل `details` على أنه chain `Details` (`C24841Amx`): serial **1**, issuerSerial **2**, key **3**, notBefore **4**, notAfter **5**.

الفحوص (بادئة السجل `wa6:`؛ ترتيب التقييم لم يُستعد بالكامل، فالدالة المفكَّكة ناقصة):

1. يُحلَّل كلا `details` على أنه chain `Details`.
2. `intermediate.issuerSerial == 0` و`leaf.issuerSerial == intermediate.serial`.
3. `leaf.key` يساوي الساكن `s_s` للخادم في المصافحة ("noise certificate key does not match proposed server static key").
4. يتحقق توقيع intermediate على `intermediate.details` بمفتاح الجذر المثبّت للمُصدِر `WhatsAppLongTerm1` (`AbstractC44011qk.A00`).
5. يتحقق توقيع leaf على `leaf.details` بالمفتاح `key` الخاص بـ intermediate.

لا تُقرأ `notBefore` / `notAfter` في مسار السلسلة. يُطلق الفشل `X.1so` (السجل `socket/invalid-certificate-exception`).

الجذر المثبّت (المفتاح العام، found، `AbstractC44011qk.A01`): `142375574d0a587166aae71ebe516437c4a28b73e3695c6ce1f7f9545da8ee6b`.

الصيغة المسطّحة (كود ميت عند الإصدار الثابت 6): `NoiseCertificate{details = 1, signature = 2}` (`C25757B9r`)، و`Details` مسطّح `{serial = 1, issuer = 2, expires = 3, subject = 4, key = 5}` (`BC0`). يتحقق الكود من التوقيع الوحيد بالمفتاح المثبّت حسب اسم المُصدِر، ويقارن `key` بـ `s_s`، ويرفض عندما تكون `expires` (بالثواني) أقل من الوقت الحالي (السجل `noise certificate expired`).

---

## 6. ClientPayload

### 6.1 الحقول (found، `C38001fP`؛ الأرقام من الواصف)

| الحقل | الرقم | النوع | يُضبط بواسطة في 2.26.41.6 |
|-------|--------|------|---------------------|
| username | **1** | int64 | الجزء الرقمي للمستخدم من JID تسجيل الدخول (مستخدم LID لتسجيل دخول LID) |
| passive | **3** | bool | علم وضع الاتصال في معلومات الجلسة (7.2) |
| userAgent | **5** | `UserAgent` | 6.2 |
| webInfo | **6** | `WebInfo` | لا يضبطه المساهمون الذين قُرئوا |
| pushName | **7** | string | اسم push للحساب، إن لم يكن فارغًا |
| sessionId | **9** | int32 | معرّف جلسة لكل اتصال (`C37121db`) |
| shortConnect | **10** | bool | `C11750a1.A03()` |
| connectType / connectReason | **12** / **13** | enum | 6.5 |
| shards | **14** | repeated int32 | غير مضبوط |
| dnsSource | **15** | message | `dnsMethod` **15**, `appCached` **16** |
| connectAttemptCount | **16** | int32 | عدد المحاولات حتى الآن |
| device | **18** | int32 | وضع companion: التفضيل `registration_device_id` |
| devicePairingData | **19** | message | 6.3 / 6.4 |
| product | **20** | enum | `WHATSAPP_LID` لتسجيل دخول LID، وإلا الافتراضي `WHATSAPP` |
| oc / lc | **23** / **24** | bool / int32 | `oc`: نتيجة فحص البناء أو التوقيع (`AbstractC38241gg`، الاسم لم يُوسَّع)؛ `lc`: التفضيل `connection_lc` |
| pull | **33** | bool | **لا يُضبط أبدًا في هذا البناء** (لم يُعثر على كاتب) |
| yearClass / memClass | **36** / **37** | int32 | استدلالات فئة الجهاز (`C38261gi`، `C38271gj`) |
| trafficAnonymization | **40** | enum | `STANDARD` عندما `C17830kT.A0L()` وإلا `OFF` |
| lidDbMigrated | **41** | bool | فقط مع JID للمستخدم وبدون companion |
| connectionSequenceInfo | **43** | int32 | عدّاد 0-31 مشتق من خطوة التسلسل |
| paaLink | **44** | bool | `C0NZ.A02()` |
| preacksCount / processingQueueSize | **45** / **46** | int32 | حالة الطابور (الأعلام **20485** / **22413**) |
| pairedPeripherals | **47** | repeated string | `smart_glasses`, `garmin` |
| messageSts | **49** | int64 | الطابع الزمني لآخر رسالة، إن عُرف |

معرَّفة لكن غير مضبوطة هنا: fbCat **21**, fbUserAgent **22**, iosAppExtension **30**, fbAppId **31**, fbDeviceId **32**, paddingBytes **34**, interopData **38** (`accountId` **1**, `token` **2**, `enableReadReceipts` **3**), accountType **42**, testIsolationId **48**.

### 6.2 UserAgent (found، `C38051fp`)

| الحقل | الرقم | القيمة في هذا البناء |
|-------|--------|---------------------|
| platform | **1** | `ANDROID` (0)، ثابت |
| appVersion | **2** | `{primary 1, secondary 2, tertiary 3, quaternary 4}` محلَّلة من `2.26.41.6` |
| mcc / mnc | **3** / **4** | `getNetworkOperator()`، الافتراضي `000` |
| osVersion / manufacturer / device / osBuildNumber | **5** / **6** / **7** / **8** | سلاسل النظام |
| phoneId | **9** | معرّف على مستوى الجهاز (`C38141gV`) |
| releaseChannel | **10** | `BETA` (1) في هذا البناء التجريبي؛ `RELEASE 0, BETA 1, ALPHA 2, DEBUG 3` |
| localeLanguageIso6391 / localeCountryIso31661Alpha2 | **11** / **12** | تُتخطى عند `zz` / `ZZ` |
| deviceBoard / deviceExpId | **13** / **14** | سلسلة اللوحة إن لم تكن فارغة؛ معرّف التجربة |
| deviceType | **15** | `PHONE` و`TABLET` و`DESKTOP` و`VR` حسب فئة الجهاز |
| deviceModelType | **16** | |
| distributionChannel | **17** | غير مضبوط |

`UserAgent.Platform` (`EnumC38071fr`، 0-40): 0 ANDROID, 1 IOS, 10 SMB_ANDROID, 12 SMB_IOS, 13 WINDOWS, 14 WEB, 24 MACOS, 29 WEAROS, 33 IPAD, 35 SMART_GLASSES, 39 WORK_ANDROID, 40 WORK_IOS (الباقي محذوف).

### 6.3 DevicePairingRegistrationData (found، `C38661hS`)

حقول `DevicePairingRegistrationData`: eRegid **1** (معرّف تسجيل من 4 بايتات)، eKeytype **2** (`05`)، eIdent **3** (المفتاح العام للهوية)، eSkeyId **4**، eSkeyVal **5**، eSkeySig **6** (معرّف signed prekey ومفتاحه العام وتوقيعه)، buildHash **7**، deviceProps **8** (`DeviceProps` مسلسل).

`buildHash`: يحسب الكود `Base64.decode(hexMD5("2.26.41.6"), 0)` (تعيد `C00L.A04` الـ MD5 السداسي عشري بأحرف صغيرة وبطول 32 حرفًا، ثم يُمرَّر إلى فاكّ base64)، فينتج 24 بايتًا وليس الملخص (digest) ذا 16 بايتًا (found كما قُرئ).

`DeviceProps` (`C43105IrG`): os **1** (سلسلة نظام التشغيل)، version **2** (`AppVersion`)، platformType **3**، requireFullSync **4** (= true)، historySyncConfig **5**. تُجمَّع كتلة مزامنة السجل بواسطة صنف يسجّل باسم `CompanionRegInfoProvider`؛ وحقولها (أيام المزامنة الكاملة / حدود الحجم، المزامنة الحديثة، مزامنة الصور المصغرة، أعلام الدعم مثل سجلات المكالمات وسجل البوتات وسجل المجموعات) تتحكم بها الأعلام **15284** و**15283** و**21217** و**20658** و**18953** و**26445** و**26614**.

### 6.4 أي متغير يُرسل (found)

- تسجيل الدخول، الأساسي (JID المستخدم معروف): username وpassive وuserAgent وpushName وsessionId وshortConnect وconnectType وconnectReason وdnsSource وconnectAttemptCount وconnectionSequenceInfo وlc وoc وyearClass وmemClass وtrafficAnonymization وlidDbMigrated وmessageSts وعدّادات الطابور وpaaLink وpairedPeripherals؛ و`product = WHATSAPP_LID` لتسجيلات دخول LID.
- تسجيل الدخول، companion: نفسه مع `device = registration_device_id`.
- تسجيل companion (JID المستخدم null): بلا username؛ مع `devicePairingData` (حزمة المفاتيح + `DeviceProps`) و`device`.

يُظهر `ConnectionThread/connect/ignored/jid null and not in companion reg` أن JID الفارغ مرفوض خارج تسجيل companion. يسجّل الهاتف الأساسي عبر HTTPS `/v2/*` (انظر تقرير أمان الحساب)؛ ولم يُعثر على أي استخدام لـ `devicePairingData` في التسجيل الأساسي.

### 6.5 التعدادات المستخدمة (found)

| التعداد | القيم |
|------|--------|
| `ConnectReason` (`EnumC38391gv`) | 0 PUSH, 1 USER_ACTIVATED, 2 SCHEDULED, 3 ERROR_RECONNECT, 4 NETWORK_SWITCH, 5 PING_RECONNECT, 6 UNKNOWN |
| `ConnectType` (`EnumC38311gn`) | 0 CELLULAR_UNKNOWN, 1 WIFI_UNKNOWN, 100 EDGE, 101 IDEN, 112 HSPAP؛ أما بقية أسماء الشبكات الخلوية (UMTS وEVDO وGPRS وHSDPA وHSUPA وHSPA وCDMA ...) فتأخذ أرقامها من ثوابت غير مباشرة لم تُحَل |
| `Product` (`EnumC38561hI`) | 0 WHATSAPP, 1 MESSENGER, 2 INTEROP, 3 INTEROP_MSGR, 4 WHATSAPP_LID |
| `DNSResolutionMethod` (`EnumC38321go`) | 0 SYSTEM, 1 GOOGLE, 2 HARDCODED, 3 OVERRIDE, 4 FALLBACK, 5 MNS, 6 MNS_SECONDARY, 7 SOCKS_PROXY |

سبب الاتصال كما يُكتب في هذا البناء: الافتراضي `UNKNOWN`؛ وعندما يكون الطابع الزمني لمعلومات الجلسة ضمن 10 ثوانٍ، تعطي الحالة 1 القيمة `USER_ACTIVATED` وتعطي الحالة 2 القيمة `PUSH`. القيم الأخرى معرَّفة لكن هذا المساهم لا يختارها.

---

## 7. بعد المصافحة

### 7.1 نتيجة تسجيل الدخول (found، `HandlerThreadC12340b0.A13`)

تُقرأ العقد الواردة الأولى في حلقة. لا يُقبل `web` إلا عند إرسال web ref (وإلا `web node given during login without any web ref provided`). أي شيء غير `web` و`success` و`failure` يُطلق `unexpected node received during login sequence`.

سمات `<success>` المقروءة:

السمات المقروءة: `t` (وقت الخادم بالثواني، يُخزَّن؛ وغير الرقمي يُطلق `invalid server time`)، `props`، `abprops`، `mc_ep_version` (عدّادات إصدار الإعداد)، `lid` (LID الحساب، يقارَن بالـ LID المخزَّن؛ وعدم التطابق يبلّغ `lid-chatd-lid-mismatch`)، `pn` (JID المستخدم للهاتف)، `static_pq_key` (مفتاح PQ للخادم بصيغة base64، 4.5).

### 7.2 الوضع السلبي مقابل النشط (found)

يأتي `passive` في الحمولة من معلومات الجلسة (`C37981fJ.A0A`)؛ وحقول السجل `forcePassiveMode` و`enablePassiveModeBasedOnQueueSize` و`duplexActive`. بعد تسجيل الدخول يغادر العميل الوضع السلبي بـ IQ من نوع set يبنيه `AbstractC44071qq`:

```xml
<iq id="..." xmlns="passive" type="set" to="s.whatsapp.net"><active/></iq>   <!-- or <passive/> -->
```

تُرسل الإقرارات المسبقة (pre-acks) أولًا عند وجودها في الطابور (`ConnectionThread/send preacks`). ينطلق مؤقت بمدة 32000 ms (`HandlerC21850s9.A02`) عند الإرسال؛ وإن لم تصل إشارة نشاط الاتصال فإنه يطلق السبب 10 (`connection active timeout`).

### 7.3 النشرات الإعلامية (found، `C40581l4`)

أبناء `<ib>` المعالَجون: `edge_routing` (الابن `routing_info`، يُخزَّن، القسم 3.1)، و`fbip` (عناوين IP مفصولة بفواصل إلى مدير الاحتياط)، و`client_expiration` (`t`، بالثواني، يُحوَّل إلى ms)، و`dirty` و`offline_preview` و`location` و`notice` و`recovery_nonce` و`safetynet` و`sonar` (`url`) و`streamdebug` و`thread_metadata` و`gpia` و`age_experience` و`accept_paa_link` و`peer_device_presence`. `dns_domain` غير موجود (غائب عن عميل Android).

---

## 8. ترميز العقد الثنائي

### 8.1 محتوى الإطار والأعلام (found، `C40411kn.Csv`، `C24610wf.Be0`)

بعد فك تشفير AES-GCM يبدأ النص الصريح ببايت أعلام واحد:

| البت | المعنى |
|-----|---------|
| `2` | الباقي تدفق zlib (DEFLATE)؛ يفكّه فاكّ الترميز ويُبقي بايت الأعلام |
| `1` | التجزئة؛ يطلق فاكّ الترميز `server to client stanza fragmentation not supported` |

المرمِّز: `Csv(node, flags)` مع `flags & 2` يضغط بـ deflate (`DeflaterOutputStream`) ويضيف `02` في البداية؛ وإلا يكتب بايت أعلام `00`. تستدعي مسارات الإرسال الرئيسية في `HandlerThreadC12340b0` وخيط الكتابة `HandlerThreadC21920sG` الدالة `Csv(node, 3)`، لذا فتلك الـ stanzas مضغوطة. تُستدعى `Csu(node)` (= الأعلام 1، غير مضغوطة) من `C40851lV` الذي يبدو مرسِلًا في مرحلة تسجيل الدخول (inferred). علامة نهاية التدفق هي `00` + list(1) + الرمز `02` (`Clp`، `xmlstreamend`).

### 8.2 بايتات الوسوم (found)

| البايت | الاسم | الجسم |
|------|------|------|
| 0 | قائمة فارغة / غائب | لا شيء |
| 1, 2 | `xmlstreamstart`, `xmlstreamend` | يرفضها فاكّ الترميز كسلاسل |
| 3..235 | رمز من بايت واحد | فهرس في الجدول `A00` ذي 236 إدخالًا |
| 236..239 | القاموس 0..3 | بايت فهرس واحد في `A01[tag - 236]` (256 إدخالًا لكل منها) |
| 244 / 247 | JID_INTEROP / AD_JID | `user:str, device:u16, integrator:u16, domain:u8` / `domain:u8, device:u8, user:str` |
| 248 / 249 | LIST_8 / LIST_16 | `count:u8` / `count:u16` |
| 250 | JID_PAIR | `user:str or 00, server:str` |
| 251 / 255 | HEX_8 / NIBBLE_8 | `lenAndOdd:u8` + نِبلات (nibbles) مُحزَّمة |
| 252 / 253 / 254 | BINARY_8 / _20 / _32 | `len:u8` / `len:u20` (3 بايتات) / `len:u32`، ثم البايتات |

الوسمان 245 و246 غير موجودين في هذا المرمِّز. كل الأعداد الصحيحة متعددة البايتات big-endian.

### 8.3 بنية العقدة (found، `C40411kn.A01`)

```
list(size)  description  (key value)*  [content]
size = 1 + 2 * attrCount + (content ? 1 : 0)
```

الحجم الفردي يعني بلا محتوى. فاكّ الترميز: عدد السمات = `((size - 2) + size % 2) / 2`. المحتوى إما كتلة بايتات (`252 / 253 / 254`) أو قائمة أبناء. عقدة تحوي كتلة وأبناء معًا تطلق `more than one source of inner data`. ترويسة القائمة: 0 للفارغة، و248 لما دون 256 إدخالًا، و249 لما دون 65536، وإلا `list too long`.

### 8.4 سلّم السلاسل (found، `C40411kn.A05` / `A06`)

| الخانة | الترتيب المجرَّب |
|------|-------------|
| description | رمز، قاموس، JID (إن أمكن تحليله)، UTF-8 مسبوق بالطول |
| مفتاح السمة | رمز، قاموس، UTF-8 |
| قيمة السمة | رمز، قاموس، JID، مُحزَّم، UTF-8 |
| بايتات المحتوى | BINARY خام (`A06(bytes, false)`)، لا يُرمَّز أبدًا ولا يُحزَّم |

التحزيم (`A06` مع علم التحزيم، لقيم السمات فقط): طول أقل من 128 وكل الأحرف في `[0-9-.]` يعطي NIBBLE_8 (`255`؛ `0-9` = 0..9، `-` = 10، `.` = 11)؛ وطول أقل من 128 وكل الأحرف في `[0-9A-F]` يعطي HEX_8 (`251`)؛ وبت الطول الفردي هو `0x80` في بايت الطول. الأطوال 256 فأكثر تستخدم BINARY_20 حتى 1 MiB، وBINARY_32 بعد ذلك. خريطة nibble لفاكّ الترميز: 10 `-`، 11 `.`، 12 `:` (لا يُصدرها المرمِّز أبدًا).

### 8.5 JIDs (found، `C40411kn.A00`، `C24610wf.A02`)

| JID | الترميز |
|-----|----------|
| مستخدم interop (`C99O`، النوع 22) | `244, user, device u16, integrator u16, 00`؛ يُفك إلى `{integrator}-{user}[:device]@interop` |
| مجموعة interop (`C55529Oy6`، النوع 28، الخادم `interop.g.us`) | `244, user, 0000, 0000, 02`؛ يشترط فاكّ الترميز أن يكون device وintegrator مساويين 0 |
| وجود agent أو device | `247, domainByte, device, user`؛ البت `1` من domainByte = LID، والبت `128` = hosted |
| غير ذلك | `250, user (or 00), server` |

تعيين خادم AD_JID: `0` `s.whatsapp.net`، `1` `lid`، `128` `hosted`، `129` `hosted.lid`. يُتوقع الجهاز `99` بالضبط عندما يكون بت hosted مضبوطًا؛ ويُسجَّل عدم التطابق ويُقبل JID مع ذلك. تطلق JIDs غير المطابقة `failed to write jid`.

### 8.6 القاموس (found، `AbstractC40911lb`)

236 رمزًا من بايت واحد (الفهرس 0 هو null) وأربعة قواميس من 256 إدخالًا؛ وإصدار القاموس هو آخر بايت في المقدمة، `03`. الفهارس التي أُعيد حلّها في هذا البناء:

| الرمز | الفهرس | الرمز | الفهرس |
|-------|-------|-------|-------|
| `s.whatsapp.net` | 3 | `iq` / `ack` / `message` | 25 / 27 / 19 |
| `type`, `id`, `from`, `to` | 4, 8, 6, 17 | `get` / `set` / `result` / `error` | 41 / 90 / 20 / 168 |
| `routing_info` / `edge_routing` | 39 / 40 | `urn:xmpp:ping` / `ping` / `w:p` | 43 / 86 / 87 |
| `handshake` / `success` | 53 / 76 | `stream:error` / `not-authorized` | 157 / 209 |
| القاموس 0: `active` / `conflict` / `replaced` / `passive` | 1 / 14 / 17 / 24 | القاموس 1: `dirty` / `server-error` / `pair-device` | 1 / 145 / 238 |
| القاموس 2: `failure` / `rate-overlimit` | 60 / 239 | `call` / `usync` / `w:m` | 100 / 121 / 194 |

بعض الرموز في الجدول ثوابت Java مستوردة من أصناف أخرى (مثل `enc`)؛ ولم تُحَل بقائمة الفهارس هذه. تتغير الفهارس بين البناءات؛ فلا تُعاد استخدامها عبر الإصدارات.

---

## 9. Keepalive والمؤقتات

| المؤقت | القيمة | المستوى |
|-------|-------|------|
| ping العميل | `<iq type="get" xmlns="w:p" to="s.whatsapp.net"/>` (`C9EN`)؛ يجب أن يحمل الرد `from` و`id` و`t` ضمن 1577865600..4102473600 و`type="result"` (`C14U`) | found |
| مهلة ping | `clamp(flag 15103, 8000, 32000)` ms؛ عند انتهاء المهلة يعمل `C14R.CY1()` مرة واحدة لكل ping (ردّ فعل إعادة الاتصال inferred) | found / inferred |
| فاصل ping | العلم **15270** (الأول)، **15183** (اللاحقة)؛ runnable مؤجَّل أو منبّه (alarm) `com.whatsapp.alarm.CLIENT_PING_TIMEOUT`، يختاره العلم **6493** | found، القيم من جهة الخادم |
| ping الخادم | `<iq type="get" xmlns="urn:xmpp:ping" t="...">` (`AbstractC40501kw`) | found |
| إقرار الوضع النشط | 32000 ms، ثم قطع الاتصال بالسبب 10 | found |
| إيصال الرسالة | بعد 45000 ms من الإرسال ولا يزال غير مقَرّ به: إعادة اتصال بالسبب 9 (`HandlerC21850s9`) | found |
| مهلة تسجيل الخروج / مهلة المقبس | 10000 ms / 30000 ms | found |

---

## 10. إعادة الاتصال والتراجع (found، `C11380Yq.A07`، `C0X9`)

يجدول `C11380Yq` إعادة الاتصال عبر `AlarmManager` (`com.whatsapp.MessageHandler.RECONNECT_ACTION`، الإضافة `connect_reason` بالقيمة 3). وحدة التأخير 10 ثوانٍ (0x2710 ms في smali).

| الخطوة | القاعدة |
|------|------|
| العدّاد | `C0X9(1, 17280)`: فيبوناتشي بالوحدات، المتتالية 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ... بحد أقصى 17280 وحدة (48 ساعة) |
| إعادة المحاولة الأولى | 0 وحدة: `scheduleReconnect/immediate` |
| الاهتزاز (jitter) | `d = units * 10 s`؛ تأخير منتظم في `[d / 2, 1.5 d)` |
| الحد الأعلى | عندما يكون علم المستدعي مضبوطًا، تصبح التأخيرات الأكبر من 15 دقيقة 15 دقيقة مع إزاحة عشوائية في `-30 .. +29` ms (`backoff clamped to ~15mins`) |
| إعادة الضبط | تعيد `A02()` ضبط العدّاد عند طلب إعادة اتصال `reset` |
| التجاوزات | `force` يمسح الموعد النهائي المعلّق؛ `force_no_ongoing_backoff` يتخطى الانتظار؛ `reset` يعيد ضبط العدّاد |
| لا شبكة | `handleDisconnected/retry/network_unavailable` ينتظر الاتصال (المنبّه `CONNECTIVITY_RETRY_ACTION`) |

ضمن المحاولة الواحدة يجتاز تسلسل الاتصال في القسم 2.2 المضيفات والمنافذ؛ ويُطبَّق backoff بين المحاولات الفاشلة للاتصال بأكمله.

---

## 11. أخطاء التدفق وأكواد الفشل

### 11.1 `<failure reason="N">` عند تسجيل الدخول (found، `A13`)

| السبب | المعالجة | السمات الإضافية المقروءة |
|--------|----------|-----------------------|
| 5xx | فشل خادم قابل لإعادة المحاولة، `C45351tB(type 4)` | لا شيء |
| 402 | عائلة الحظر؛ النوع 13 (الكود 106 مع `appeal_token`)، 14 (الكود 107)، 15 (الكود 109)، وإلا 2 | `appeal_token`, `code`, `expire`, `message`, `url`, `age_collection` |
| 403 | النوع 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` |
| 405 | النوع 3، `expiration_time = t * 1000` | `t` |
| 406 | النوع 5 | `code` |
| 416 | النوع 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` |
| أخرى | النوع 0 (مسار تسجيل الخروج العام) | لا شيء |

كل فشل يقرأ أيضًا حقول واجهة تسجيل الخروج الاختيارية `logout_message_header` و`logout_message_subtext` و`logout_message_locale` و`logout_main_button_text` / `_url` و`logout_secondary_button_text` / `_url` (`A17`). لم يُتتبَّع تعيين أعداد الأنواع الصحيحة إلى الشاشات الموجّهة للمستخدم؛ ودلالات حظر الحساب يغطيها تقرير الحظر.

### 11.2 `<stream:error code="N">` (found، `C40601l6`، `C37961fH.A1B`)

| الحالة | المعالجة |
|------|----------|
| أي `stream:error` | يُسجَّل `ConnectionThreadRequestsImpl/stream/error` مع الابن الأول؛ وتُرسل رسالة تحمل `errorCode` إلى `MessageHandler` |
| الكود 500-599 | يضبط `MessageHandler` علمًا ويشغّل تمريرة إعادة اتصال (`onConnectionStreamError`) |
| الابن `ack` | يُعامل كطرد بسبب ack (ack-kick): يُبحث عن الـ stanza المعلّق بذلك المعرّف، وتُصدر المقاييس، ويتوقف الاتصال (يُطلق `1t7`) |
| الابن `conflict type="device_removed"` | companion فقط: إلغاء التسجيل (`C24100vp.A02`)، ما لم تكن الحالة 9 |
| 515 / 516 (مسار companion) | تُمرَّر كرسائل مصنَّفة؛ والفرع المفكَّك للكود 515 غير واضح |
| `<error code="479">` | يُبلَّغ `smax-invalid` (`SmaxInvalidError`) |
| `<error class="status" id=...>` | يُفشل رد نداء إقرار الحالة المعلّق |

### 11.3 إخفاقات المصافحة والمقبس (found كوسوم سجل، ردود الفعل مُتتبَّعة جزئيًا)

| وسم السجل | السبب |
|---------|-------|
| `socket/goaway` (`X.1sn`) | بايتات طول ServerHello تساوي `GOA` |
| `socket/invalid-certificate-exception` (`X.1so`) | فشل فحص سلسلة الشهادات (5)؛ يستدعي `C37031dS.A0C` |
| `socket/disconnect/invalid-server-static-key` (`X.1sp`)، `.../authKey` (`X.1sm`) | رفض الساكن للخادم؛ مشكلة في مفتاح العميل الساكن |
| `socket/disconnect/noise` (`X.1sr`) | استثناء بروتوكول (بيانات مصافحة سيئة، أحجام TLV)؛ ويُعاد إطلاق فشل AEAD `X.1t9` وخطأ مدخل KEM `X.1tC` ضمن هذه العائلة |
| `socket/disconnect/io`، `socket/closed`، `socket/error/EPERM` | أخطاء I/O، شبكة محجوبة |
| `connect/not-allowed/clock`، `software-expired`، `login-failed`، `quit-flag-set` | بوابات ما قبل الاتصال |
| `ReaderThread/corrupt-stream-error` | تدفق عقد تالف؛ و`next-port/corrupt-stream-exception` ينقل إلى المنفذ التالي |

---

## 12. أعلام الميزات (المعرّفات كما قُرئت في `AbstractC36791d3` ومواضع الاستدعاء)

| المعرّف | النوع | يتحكم في |
|----|------|----------|
| **20161**, **34536** | int, string | وضع PQ (1 تفعيل، 2-4 إلزام)، متغير PQ (الافتراضي `IKKEM`) |
| **38643**, **15716** | string, bool | اختيار KEM (`MLKEM768` معروف)، بوابة له؛ الأثر غير محلول |
| **33751** | bool | كاتب بمخزن مؤقت للمقدمة + ClientHello |
| **22916**, **30712**, **33512** | bool | تعطيل خطوة HISTORY؛ تحميل سجل آخر نجاح؛ إعادة استخدام المنفذ المخزَّن |
| **20801**, **23630**, **24645** | bool | الخطوة 5 على 443 ثابتة؛ الخطوات 2-4 تحت إعداد SOCKS؛ مصدر إعداد خدمة SOCKS |
| **13545** | string | وضع محلِّل DNS (`secondary` / `hardcoded` / `none`) |
| **7831**-**7834** | bool, ints | تفعيل TCP keepalive ومعاملاته |
| **15103**, **15270**, **15183**, **6493** | int, bool | مهلة ping، الفواصل، طريقة الجدولة |
| **20485**, **22413** | bool | حالة الطابور في الحمولة |

كل القيم من جهة الخادم؛ والقيم الافتراضية هي المترجمة في تصريحات الأعلام.

---

## 13. نواقل أخرى

| الناقل | الحالة في 2.26.41.6 | المستوى |
|-----------|--------------------|------|
| عميل Tigon HTTP | `com/crossapp/tigonhttp/TigonHttpClient*`، `com/facebook/tigon/**`، `com/whatsapp/infra/tigon/WAHucClient`، المصادقة عبر `WATigonAsyncAuthServiceHolder`؛ سلاسل HTTP/2 وHTTP/3 (`MNS/mvfst-mobile`، `MNS/ngtcp2`) في `libwhatsappmerged.so` | الأصناف والسلاسل found؛ الاستخدام لكل ميزة inferred |
| DistribGW (DGW) | `com/facebook/distribgw/client/*`، `RequestStreamDGWBuilder`؛ التسجيل الوحيد من جهة التطبيق الذي عُثر عليه: `WaFalcoStreamingRegistration.nativeRegisterStreaming(DGWClient)`؛ السلاسل `distribgw_tigon_tunnel` و`DGW_MQTTBYPASS` و`XPLAT_RS_MQTT` و`XPLAT_RS_STARGATE` و`wa_request_stream` | found؛ صيغة السلك unknown |
| عميل MQTT | لا يوجد؛ يظهر `mqtt` فقط في أسماء أحداث التحليلات وتسميات أنواع تدفق DGW | found |
| GraphQL عبر chatd | `com.whatsapp.pando.chatd.WAChatdGraphQLClient`، `WAChatdGraphQLCallbacks`، `WATigonMexdServiceHolder` | الأسماء found؛ يمر عبر chatd كمسار w:mex inferred |

### 13.1 قناة Tigon Noise (كومة Noise ثانية، native)

هذا ناقل مختلف عن chatd. الأدلة سلاسل وأسماء أصناف، وليست منطقًا مفكَّكًا.

- الحامل: WebSocket فوق كومة شبكة MNS (`NoiseCarrierWebSocket`، `Stream0Listener`)؛ تدفقات مرقَّمة مع تدفق تحكم 0 وإعادة تجميع القطع (`noise.framer.*`).
- نتائج المصافحة (`NoiseHandshakeOutcome`): `LEGACY_PEER_VERIFIED` و`PRIVATE_AUTH_PEER_VERIFIED` و`ENROLLMENT_REQUIRED` و`KEY_REQUIRED` و`VERIFICATION_FAILED`؛ `NoisePrivateAuthMode`: `MIGRATION` و`REQUIRED`؛ وأخطاء مثل `noise.handshake.attestation_failed` و`chip_binding_rejected` و`private_auth.vm_proof_failed`.
- الإثبات (Attestation): مدقّق AMD SEV-SNP (`NoiseSevSnpAttestationVerifier`، فحوص سلسلة VCEK / ASK / ARK، ربط معرّف الشريحة)؛ التسميات `hatch.noise-auth.key.v1` و`.client-proof.v1` و`.vm-proof.v1`.
- التحكم بالطلب: `NoiseConnectionDemandRejectionReason` القيم `OFFLINE` و`BACKGROUND` و`PAUSED` و`SESSION_ENDED` و`RETRY_EXHAUSTED` و`INTERNAL`.
- مستخدمو Java: `WaVmHttpTransportImpl`، `NoiseVmConnection` (المسار `/v1/noise`، الخطوات `hatch-noise status=opening` / `result=ready`)، `NoiseGatewayCarrier`. الغرض (HTTP عبر Noise إلى VM حوسبة سرية لمتصفح الوكيل) inferred من الأسماء وسلاسل الإثبات.

لا شيء هنا يشارك الكود مع مصافحة chatd في القسم 4؛ وتطابق اسم النمط لا يعني تطابق التأطير أو prologue أو الحمولة.

---

## 14. Baileys (`baron-baileys-v2`، مؤكَّد مقابل مصدره)

| الجانب | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| ترويسة المقدمة | `NOISE_WA_HEADER = [87, 65, 6, 3]` | `57 41 06 03` |
| النمط | `NOISE_MODE = 'Noise_XX_25519_AESGCM_SHA256\0\0\0\0'` | الاسم المحشو نفسه بطول 32 بايتًا |
| شهادة الخادم | فك `CertChain`؛ يُفحص توقيع leaf بمفتاح intermediate؛ ويُفحص intermediate بالجذر المثبّت `142375574d0a...da8ee6b`؛ يجب أن يكون `issuerSerial` مساويًا 0 | السلسلة نفسها وبايتات الجذر نفسها؛ ويشترط APK إضافةً `leaf.issuerSerial == intermediate.serial` |
| توجيه edge | يخزّن `routing_info` من `<ib><edge_routing>`؛ ويلحقه كاستعلام `ED=<base64url>` على `wss://web.whatsapp.com/ws/chat` | يخزّنه (بحد أقصى 256 بايتًا)؛ ويرسل `45 44 00 01 len24 blob` خامًا قبل المقدمة |
| Keepalive | `<iq type="get" xmlns="w:p"/>` بلا أبناء، الفاصل الافتراضي 30000 ms، مهلة الاتصال 20000 ms | IQ نفسه؛ الفاصل والمهلة من أعلام الخادم |
| حمولة تسجيل الدخول | `passive`، `pull` بقيمة true، `username`، `device`، `connectType WIFI_UNKNOWN`، `connectReason USER_ACTIVATED`، `lidDbMigrated false`، `releaseChannel RELEASE` | بلا `pull`، و`connectReason` من حالة الجلسة، و`releaseChannel BETA` في هذا البناء |
| حمولة التسجيل | `passive false`، `pull false`، `devicePairingData` | `devicePairingData` فقط لاتصال تسجيل companion |
| النقل | إطارات WebSocket | TCP خام، إطارات بطول 3 بايتات |

الفروق المؤكَّدة المهمة لنقل بنمط Android: تلميح edge هو معامل استعلام في عنوان WebSocket في Baileys لكنه ترويسة خام قبل المقدمة في Android؛ ولا يفرض Baileys الشرط `leaf.issuerSerial == intermediate.serial`؛ ويرسل Baileys `pull` و`passive` بقيمة true عند تسجيل الدخول بينما لا تحتوي حمولة Android على `pull`. يحتفظ Baileys بالمفتاح الساكن للخادم لإعادة اتصال سريعة (يذكر تعليق في الكود `NoiseIkSession`)، وهو يطابق استئناف IK في القسم 4.4 من حيث القصد فقط؛ ولم تُقارَن صيغته على السلك.

---

## 15. حالات الخطأ

| العَرَض | السبب | الإصلاح |
|---------|-------|-----|
| `GOA` في أول ثلاثة بايتات | goaway من الخادم أثناء المصافحة | جرّب نقطة الاتصال التالية |
| `Handshake message does not contain server hello!` | أول إطار من الخادم ليس ServerHello | افحص prologue وترويسة edge |
| `noise certificate key does not match proposed server static key` | مفتاح leaf يختلف عن الساكن في المصافحة | تحقق من السلسلة قبل ClientFinish |
| `server to client stanza fragmentation not supported` | البت `1` من الأعلام مضبوط | غير مدعوم من العميل |
| `unexpected node received during login sequence` | العقدة الأولى ليست `web` أو `success` أو `failure` | لا شيء |
| `noise-pq-static-key-decode-failed` | `static_pq_key` ليس base64 صالحًا | لا يُخزَّن المفتاح، ويُبلَّغ مرة واحدة |
| `scheduleReconnect backoff=...` | إخفاقات متكررة | انتظر انقضاء backoff أو أجبر إعادة الاتصال |

---

## 16. فروق أساسية

| لا تخلط بين | التفصيل |
|----------------|--------|
| Noise في chatd مقابل قناة Tigon Noise | Java مقابل native، حامل TCP مقابل WebSocket، غرض مختلف؛ تطابق اسم النمط لا يعني شيئًا عن التأطير أو الحمولة |
| ترويسة المقدمة مقابل ترويسة edge | `WA 06 03` يُهشَّر كـ prologue؛ أما `ED 00 01 len blob` فليس جزءًا من النص (transcript) |
| مضيف edge `eN.whatsapp.net` مقابل `routing_info` | المضيفات تأتي من تسلسل العميل؛ و`routing_info` كتلة معتمة تُعاد في ترويسة edge |
| `fallback_hostname` / `fallback_ip4` / `fallback_ip6` | سمات مضيفات `media_conn` (CDN)، وليست احتياطات chatd؛ احتياطات chatd تأتي من `<ib><fbip>` والجدول المضمّن |
| علم الحمولة `passive` مقابل IQ ‏`<passive/>` | العلم يُضبط عند الاتصال؛ أما IQ فيحوّل إلى الوضع النشط بعد ذلك |
| `devicePairingData` مقابل التسجيل عبر HTTP | بيانات الاقتران تخص اتصال تسجيل companion |
| طول الإطار مقابل حجم القائمة | الطول من 3 بايتات يلفّ النص المشفَّر؛ وحجم القائمة يعدّ خانات العقدة |
| إصدار البروتوكول مقابل إصدار القاموس | كلاهما في المقدمة: `06` و`03` |
| `stream:error` مقابل `failure` | `failure` يجيب على تسجيل الدخول؛ أما `stream:error` فيمكن أن يصل في أي وقت |

---

## 17. التدفق الكامل

```
[Connection thread]  C37031dS.A0G picks step (history, g, g-fallback, hard-coded, eN, proxy)
     │  DNS ─► TCP connect ─► optional TLS wrapper
     ▼
[Client]  write [ED 00 01 len24 routing_info]?  [WA 06 03]        h = SHA256(name) ; h = SHA256(h || WA 06 03)
     │  frame1: HandshakeMessage{clientHello{ephemeral}}           mixHash(e_c)    (resume: + static + payload)
     ▼
[Server]  frame2: serverHello{ephemeral, static, payload}
     │  mixHash(e_s) ; mixKey(ee) ; s_s = decrypt(static) ; mixKey(es) ; cert = decrypt(payload)
     │  CertChain: leaf.key == s_s ; intermediate by pinned root ; leaf by intermediate
     ▼
[Client]  frame3: clientFinish{static = enc(s_c), payload = enc(ClientPayload)}      mixKey(se) ; split
     ▼
[Server]  [len24 | AES-GCM(flags | node)] ─► <success t props abprops lid pn static_pq_key/>  or  <failure reason/>
     ▼
[Client]  <iq xmlns="passive" type="set"><active/></iq> (+ pre-acks) ; steady state both ways, own counter per direction
     │  ping <iq xmlns="w:p"/> ; ib / notification / message / receipt / call ...
     ▼
[Failure]  stream:error / ping timeout / socket error ─► disconnect ─► Fibonacci backoff ─► next attempt
```

---

## 18. المجهولات

| البند | الحالة |
|------|--------|
| حركة السلك من أي نوع | لم يُلتقط شيء؛ لا بند منها `tested` |
| نص استئناف IK والاحتياط | البنية found، والخطوات inferred |
| موضع مفتاح PQ في `ServerHello.payload`، وعرض طول TLV، والمكتبة وراء استدعاءات ML-KEM | لم يُفك / لم تُحدَّد |
| ما تحمله نقاط الاتصال المغلّفة بـ TLS داخل TLS | inferred من مسار الكود |
| قيم ping وTCP-keepalive | أعلام الخادم |
| أعداد أنواع الفشل الصحيحة 0-15 إلى شاشات العميل؛ أثر العلمين **38643** و**15716** | لم تُتتبَّع / غير محلولة |
| حقول الحمولة بلا كاتب (`webInfo` و`shards` و`fb*` و`accountType` و`testIsolationId` و`paddingBytes` و`pull`) | لم يُعثر على شيء في هذا البناء |
| مصافحة قناة Tigon Noise وتأطيرها؛ بروتوكول سلك DGW ومستخدموه | native، سلاسل فقط |
| سلاسل القاموس التي هي ثوابت Java مستوردة (مثل `enc`) | لم تُحَل في قائمة الفهارس |
