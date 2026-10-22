<!-- src-sha1: f9c1d644c604d99d2f1b54082218c3f75d2cf8a7 -->
# WhatsApp مزامنة حالة التطبيق — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** مزامنة حالة التطبيق (syncd) على Android: خمس مجموعات، وطلب IQ ‏`w:sync:app:state`، والتصحيحات (patches) / اللقطات (snapshots) / الكتل الخارجية (blobs)، وتعديلات SET/REMOVE، واشتقاق مفاتيح التعديلات وتشفير السجلات، وMAC للفهرس / للقيمة، وLT-Hash، وMAC للقطة وللتصحيح، ومفاتيح المزامنة (التوليد والمشاركة والطلب والانتهاء)، والتحقق الصادر والوارد، وكتالوج إجراءات المزامنة (96 إجراءً: chat وlabel وcontact وnctSalt …)، ومعالجة الأخطاء القاتلة وإعادة المحاولة، واستعادة اللقطة، وأعلام الميزات، ومقارنة مع Baileys

---

## 1. ما هي (تقنيًا)

تنسخ مزامنة حالة التطبيق حالةً صغيرة لكل حساب (كتم، تثبيت، أرشفة، تمييز بنجمة، جهات اتصال، تصنيفات، إعدادات …) بين الهاتف الأساسي وكل جهاز مرتبط. يخزّن الخادم سجلات مشفّرة من طرف إلى طرف فقط، ويرتّبها لكل مجموعة ويقدّم تصحيحات مرقّمة بالإصدارات. كل العبارات مبنية على التحليل الساكن لشيفرة APK بعد فك تجميعها؛ لم يُلتقط شيء على الشبكة. المستوى: **found** = قُرئ في الشيفرة، **inferred** = مستنتج من الشيفرة، **unknown** = غير محلول. أُعيد حلّ الأسماء المشوشة (obfuscated) في 2.26.41.6 اعتمادًا على سلاسل ثابتة (`WhatsApp Mutation Keys` و`WhatsApp Patch Integrity` و`w:sync:app:state` وأسماء المجموعات وبادئات السجلات).

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| مدير المزامنة | `C12440bB` (`sync-manager/*`) | الجدولة، `A0S` فشل قاتل، `A0Q` حذف كل البيانات |
| معالج الطلب / باني IQ / المحلل | `C53148Nnt` / `C46361ux` / `N90` | إرسال IQ، بناء `<sync>`، تحليل النتيجة |
| معالج الاستجابة القديم | `SyncResponseHandler` (`consumer/companiondevice/p049iq`) | مسار التطبيق القديم، معالجة القاتل `A08` |
| محرك KMP | `com.whatsapp.kmp.syncd.syncdengine.*` | `OutgoingProcessor` و`IncomingProcessor` و`SyncdResponseHandler` و`SyncdResponseProcessor` و`CollectionHandler` و`crypto/*` |
| تعداد المجموعات / تعداد الإجراءات | `EnumC24862AnK` / `EnumC24865AnN` | 5 مجموعات / 96 اسم إجراء في السلك |
| الإجراء إلى المجموعة | `AbstractC24863AnL.A00` | switch على الترتيب (ordinal) |
| أساس التعديل / أساس المعالج | `AbstractC24864AnM` / `AbstractC25077Aqp` | تعديل معلّق / معالج إجراء |
| مدير المفاتيح / المخزن | `C12800bm` (`SyncdKeyManager`) / `C13620d6` (الجدول `crypto_info`) | توليد المفاتيح ومشاركتها وطلبها وإنهاء صلاحيتها وحفظها |
| معرّف المفتاح / المفتاح / بيانات المفتاح | `CGH` / `C51259MoT` / `C51361MqC` | معرّف من 6 بايت / المعرّف + البيانات / البيانات، بصمة `C8H`، ts |
| مفاتيح التعديلات | `MhX` | ناتج HKDF، 5 شرائح |
| حاملات المشاركة / الطلب | `C26102BPk` (FMessage 38) / `C26101BPj` (39) | رسائل peer |
| LT-Hash وHKDF | `AbstractC50511MVx.A00` + `KmpLtHash16`، `AbstractC38961i0` | تجزئة من 128 بايت، RFC 5869 |
| التشفير (قديم / KMP) | `C52959NkE` / `KmpSyncdCryptoHelper` و`KmpSyncdEncryptor` و`KmpSyncdDecryptor` و`KmpSyncdIncomingAntiTamperingValidator` | صيغ متطابقة |
| الكتل الخارجية | `C17650kB` (تنزيل)، `KmpExternalMutationsUploaderImpl` | نوع MMS ‏`md-app-state` |
| الإقلاع / حذف الكل / الاستعادة | `C24986ApL` / `C17630k8` / `KmpSyncdFatalErrorRecovery` | آلة حالات، `delete_all_data`، تقديم اللقطة |
| الأنواع القاتلة / الاستثناء القديم | `Lx6` / `C49784Lv2` | 70 نوعًا مسمّى / عدد صحيح `errorCode` |

يتعايش تطبيقان للبروتوكول نفسه. يُختار محرك KMP بثلاث قيم منطقية يتحكم بها الخادم وقيمها الافتراضية المترجمة **false** (**15909** تشفير، **20682** وارد، **18234** صادر، القسم 12). المسار الذي يعمل عليه حساب ما غير معروف. صيغ MAC والتشفير متطابقة في الاثنين (قورنت في `C52959NkE` و`KmpSyncd*`).

يشغّل الأساسي والمرافق (companion) الشيفرة نفسها. الفروق الموجودة: الأساسي وحده ينشئ تعديلات `contact` / `lid_contact` (`Companion cannot create contact mutations`)؛ المرافق وحده يرسل `return_snapshot="true"`؛ معالجة القاتل تختلف (11.3).

---

## 2. المجموعات

| الاسم في السلك | ترتيب التعداد | حرجة | بت السجل (`C17530jy.A00`) | الإجراءات |
|-----------|--------------|----------|--------------------------|---------|
| `regular` | 0 | لا | 3 | 35 |
| `regular_low` | 1 | لا | 5 | 36 |
| `regular_high` | 2 | لا | 4 | 19 |
| `critical_block` | 3 | نعم | 1 | 4 |
| `critical_unblock_low` | 4 | نعم | 2 | 2 |

المجموعة الحرجة = `{critical_block, critical_unblock_low}` (`EnumC24862AnK.A01`). تحوّل `A00()` الترتيب إلى 1..5؛ المستهلك لم يُتتبع.

على Android تحتوي `critical_block` على إجراءات إعدادات الحساب (`setting_pushName` و`setting_locale` و`setting_securityNotification` و`generated_wui`)، **وليس** قائمة حظر؛ أما `contact` و`lid_contact` فتقعان في `critical_unblock_low`. لا يوجد إجراء في تعداد الـ96 مسمّى باسم الحظر (found).

**الإقلاع (المرافق، جزئيًا inferred).** تعمل `syncd_bootstrap_state` (`C24986ApL`) من 0 إلى 4. Found: اكتمال مزامنة المجموعة الحرجة → الحالة 2 وإشارة "critical blocking complete"؛ اكتمال مزامنة كل المجموعات غير الحرجة → الحالة 4؛ الحالة 3 هي خطوة مزامنة السجل (inferred). أسباب الفشل: `critical_sync_timeout` و`history_sync_failure` و`syncd_failure`؛ سجل المراقب (watchdog) هو `syncd-critical-bootstrap-timeout`. على الأساسي، يشغّل ربط جهاز مرافق `prepareCriticalDataUpload`: مزامنة السجل ثم `shareAllKeys`؛ وإن لم يوجد مفتاح مع العلم **27528** يُولَّد مفتاح أولًا.

---

## 3. طبقة IQ

### 3.1 الطلب (found، `C46361ux`)

```xml
<iq to="s.whatsapp.net" xmlns="w:sync:app:state" type="set" id="…">
  <sync data_namespace="3">
    <collection name="regular_low" order="1" version="41" return_snapshot="true">
      <patch>…SyncdPatch bytes…</patch>
    </collection>
  </sync>
  <coex><bot>…enc node…</bot></coex>      <!-- optional -->
</iq>
```

| السمة | القيمة |
|-----------|-------|
| `data_namespace` | ثابت `3` على `<sync>` |
| `order` | ‏`0` لـ `critical_unblock_low`، و`1` لغيرها؛ المعنى غير معروف |
| `version` | إصدار المجموعة المخزّن محليًا (`C17540jz.A02`)؛ يُحذف إن لم يوجد |
| `return_snapshot` | ‏`"true"` فقط للمرافق عندما يكون الإصدار null أو 0 |
| `<patch>` | فقط عند وجود تعديلات محلية معلّقة |
| `<coex><bot>` | coexistence-v2: مفاتيح المزامنة المستخدمة تُشفَّر إلى bot ‏(`sync-request-handler/coexv2 *`)؛ عند الفشل يذهب IQ بدونها وتُشارَك المفاتيح خارج النطاق |

المهلة 32 ثانية؛ قد يحمل IQ واحد عدة مجموعات.

### 3.2 النتيجة (found، `N90`)

```xml
<iq type="result"><sync>
  <collection name="X" type="error"><error code="409" text="…"/> [<patches>…]</collection>
  <collection name="X" version="42"/>                    <!-- outgoing patch acked -->
  <collection name="X" has_more_patches="true">
    <snapshot>ExternalBlobReference bytes</snapshot>    <!-- companion bootstrap -->
    <patches><patch>SyncdPatch bytes</patch>…</patches>
  </collection>
</sync></iq>
```

غياب `<sync>` أو جسم `<snapshot>` / `<patch>` فارغ → فشل عابر. تبقى المجموعة التي ليس فيها إصدار ولا تصحيحات ولا لقطة اسمًا مجردًا (المعنى inferred: لا جديد). أجسام اللقطات دائمًا `ExternalBlobReference`، ولا تكون سجلات مضمّنة أبدًا.

أخطاء المجموعة (`M4T`): ‏-1 ‏`UNKNOWN` قابل لإعادة المحاولة؛ 400 / 404 / 405 / 406 قاتلة (`Xmpp*ForCollection`)؛ 409 ‏`CONFLICT` تُطبَّق التصحيحات المرفقة ثم يُعاد المحاولة، وإلا قابل لإعادة المحاولة (شرط الفرع ملتبس في فك التجميع)؛ 500 قابل لإعادة المحاولة.

خطأ IQ العام (`C53148Nnt.Brt`، ‏`backoff` بالثواني):

| الرمز | المعالجة |
|------|----------|
| 400، 404، 405، 406 | قاتل؛ الرموز القديمة 64 و65 و66 و67؛ أنواع KMP ‏55-58 |
| أخرى 4xx | بلا إعادة محاولة، `client_error:<code>` |
| 5xx | إعادة المحاولة بعد `max(server backoff, client delay)`، `server_error:<code>` |
| غير ذلك | `global_error:<code>` |

تتصاعد الإخفاقات العابرة الأقدم من 7 أيام (`first_transient_server_failure_timestamp` > 604 800 000 ms) إلى قاتلة. أسباب أخرى غير قاتلة: `network_error` و`sqlite_full` و`unexpected_error` و`mms_local_io` و`mms_upload`.

---

## 4. رسائل Protobuf

الأرقام مستخلصة من فئات 2.26.41.6، ومفحوصة مقابل ترتيب التصريح، وعند وجودها مقابل ثوابت `*_FIELD_NUMBER` المولّدة (`*`).

| الرسالة (الفئة) | الحقول (الرقم) |
|-----------------|-----------------|
| `SyncdPatch` (`C49631LsW`, lite `Lp6`) | version **1** `SyncdVersion{uint64=1}`, mutations **2**, externalMutations **3** `ExternalBlobReference`, snapshotMac **4**, patchMac **5**, keyId **6** `KeyId{bytes id=1}`, exitCode **7** `ExitCode{uint64 code=1; string text=2}`, deviceIndex **8**, clientDebugData **9** |
| `SyncdMutation` (`C49601Ls2`) | operation **1** (`SET`=0, `REMOVE`=1), record **2** |
| `SyncdRecord` (`C49610LsB`) | index **1** `SyncdIndex{bytes blob=1}` (MAC الفهرس), value **2** `SyncdValue{bytes blob=1}`, keyId **3** |
| `SyncdMutations` (`C49583Lrk`) | mutations **1** (جسم التصحيح الخارجي) |
| `SyncdSnapshot` (`C49617LsI`, lite `C49419Lob`) | version **1**, records **2**, mac **3**, keyId **4** |
| `SyncActionData` (`C49612LsD`) | index **1** (مصفوفة نصوص JSON بترميز UTF-8), value **2** `SyncActionValue` (`BD4`), padding **3** (فارغ دائمًا), version **4** int32 |
| `ExternalBlobReference` (`C49439Lov`) * | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `AppStateSyncKeyShare` (`C25704B7n`) * / `AppStateSyncKey` (`C25764B9y`) * | keys **1** / keyId **1** (`B89{keyId=1}`), keyData **2** |
| `AppStateSyncKeyData` (`BB9`) * | keyData **1** (32 بايت), fingerprint **2**, timestamp **3** (ms) |
| `AppStateSyncKeyFingerprint` (`BBU`) * | rawId **1**, currentIndex **2**, deviceIndexes **3** |
| `AppStateSyncKeyRequest` (`C25703B7m`) * | keyIds **1** |
| `AppStateFatalExceptionNotification` (`C25763B9x`) * | collectionNames **1**, timestamp **2** |
| `SyncDCollectionFatalRecoveryRequest` | collectionName **1**, timestamp **2** |
| `SyncDSnapshotFatalRecoveryResponse` | collectionSnapshot **1**, isCompressed **2** |
| `SyncdSnapshotRecovery` (`C49432Loo`) * / `SyncdPlainTextRecord` (`C49416LoY`) * | version **1**, collectionName **2**, mutationRecords **3**, collectionLthash **4** / value **1** `SyncActionData`, keyId **2**, mac **3** |
| `KeyExpiration` (`B8Y`) | expiredKeyEpoch **1** |
| `SyncActionValue` (`BD4`) * | timestamp **1** (int64؛ يفشل SET بدونه), حقل واحد لكل إجراء (10.1) |

الحاملات (found، `*`): ‏`ProtocolMessage` (`BD3`) ‏`appStateSyncKeyShare` الحقل **7** / النوع **6**، و`appStateSyncKeyRequest` الحقل **8** / النوع **7**، و`appStateFatalExceptionNotification` الحقل **10** / النوع **10** (`EnumC26463Bdz`). ‏`PeerDataOperationRequestMessage.syncdCollectionFatalRecoveryRequest` الحقل **7**، ونوع الطلب `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` = **8** (`EnumC26460Bdv`)؛ والاستجابة `syncdSnapshotFatalRecoveryResponse` الحقل **8** (`C25828BCm`). خصائص العميل للمرافق (`C43107IrI`): ‏`isSyncdPureLidSession` **2**، و`isSyncdSnapshotRecoveryEnabled` **3**. أرقام FMessage الداخلية: مشاركة المفتاح **38**، طلب المفتاح **39**، الإشعار القاتل **50**. تسافر المشاركة والطلب كرسائل peer إلى `DeviceJid` واحد (`SendPeerMessageJob`)، وأولوية المشاركة `high`.

---

## 5. مفاتيح التعديلات وتشفير السجلات

### 5.1 اشتقاق المفاتيح (found، `MhX`، ومثله في `C52959NkE`)

```
expanded = HKDF-SHA256(ikm = keyData(32), salt = 32 × 0x00, info = "WhatsApp Mutation Keys", L = 160)
```

| البايتات | حقل `MhX` | الاستخدام |
|-------|-------------|-----|
| 0-31 | `A00` | مفتاح الفهرس، HMAC-SHA256 |
| 32-63 | `A03` | مفتاح تشفير القيمة، AES-256-CBC |
| 64-95 | `A04` | مفتاح MAC القيمة، HMAC-SHA512 |
| 96-127 | `A02` | مفتاح MAC اللقطة، HMAC-SHA256 |
| 128-159 | `A01` | مفتاح MAC التصحيح، HMAC-SHA256 |

HKDF هو `AbstractC38961i0.A00`: الاستخراج = `HMAC-SHA256(32 zero bytes, ikm)`، والتوسيع وفق RFC 5869. تخزّن `C17930kd` كائنات `MhX` مؤقتًا (5 مدخلات، inferred). مفتاح المزامنة عشوائي (القسم 7)، وليس مشتقًا من مفاتيح Signal.

### 5.2 تشفير تعديل واحد (found، `KmpSyncdEncryptor`، `C52959NkE`)

```
index    = JSON string array, element 0 = action wire name, e.g. ["mute","<jid>"]
plain    = SyncActionData{ index = UTF8(index), value = SyncActionValue, padding = "", version }
iv       = SecureRandom(16)
ct       = AES-256-CBC/PKCS5(valueEncKey, iv, plain)
aad      = op ‖ keyId(6)                 op: 0x01 SET, 0x02 REMOVE
valueMac = HMAC-SHA512(valueMacKey, aad ‖ iv ‖ ct ‖ len8)[0..32)      len8 = 8-byte big-endian aad length (7)
indexMac = HMAC-SHA256(indexKey, UTF8(index))
record   = SyncdRecord{ index.blob = indexMac, value.blob = iv ‖ ct ‖ valueMac, keyId }
```

طول الحشو (padding) هو `max(0, −indexLen − valueLen)`، وهو فارغ دائمًا. أصغر حجم للكتلة 48 بايت. تحويل SET→0x01 يفترض أن ثابت العملية المحلي يساوي 0 لـ SET (inferred؛ في السلك SET=0). محتوى القيمة في REMOVE فارغ (inferred، فرع `mqt != null`).

### 5.3 فك التشفير (found، `KmpSyncdDecryptor`)

| الخطوة | الفحص | الفشل |
|------|-------|---------|
| 1 | تقسيم `iv = [0..16)`، `ct = [16..n−32)`، `mac = [n−32..n)` | `Cipher text too short` |
| 2 | حلّ المفتاح عبر `record.keyId` | أخطاء المفاتيح (7.2) |
| 3 | إعادة حساب MAC القيمة ومقارنته | `Data MAC mismatch` (`DecryptionFailed`) |
| 4 | فك AES-CBC وتحليل `SyncActionData` | `ActionDataProtobufDeserializationFailed` |
| 5 | وجود الفهرس والإصدار و(لـ SET) القيمة والطابع الزمني | `MISSING_INDEX` و`MISSING_VERSION` و`MISSING_VALUE` و`MISSING_ACTION_TIMESTAMP` |
| 6 | الفهرس `String[]` بصيغة JSON، غير فارغ، بلا عنصر فارغ | `keyArray length should have action name` |
| 7 | إعادة حساب MAC الفهرس على نص الفهرس | `Index MAC mismatch` |

يُفحص MAC القيمة قبل فك التشفير، وMAC الفهرس أخيرًا. ثم يُحلّ الإجراء عبر العنصر 0 (`Unknown mutation name:`).

---

## 6. LT-Hash وMAC اللقطة وMAC التصحيح

**LT-Hash** (found، `AbstractC50511MVx`، `KmpLtHash16`): ‏128 بايت تُقرأ كـ 64 مسارًا u16 بترتيب little-endian؛ الفارغ = 128 بايت أصفار.

```
expanded(valueMac) = HKDF-SHA256(ikm = valueMac(32), salt = 32 × 0x00, info = "WhatsApp Patch Integrity", L = 128)
lane'[i]           = (lane[i] ± expanded[i]) mod 2^16         + add, − subtract
```

التحديث الوارد (`KmpSyncdCryptoHelper.A01`): لكل فهرس في التصحيح، **اطرح** `mutation_mac` المخزّن للسجل الموجود، ثم **أضف** MAC القيم الخاصة بتعديلات SET. تعيد `checkLtHashConsistency` (`C17520jx`) بناء التجزئة من كل قيم `mutation_mac` المخزّنة وتقارنها بالتجزئة المخزّنة (تسجّل `ltHashFromMutations` / `ltHashFromDb`، آخر 16 خانة hex ما لم يُفعَّل العلم **624**)؛ وتعمل من cron اليومي عندما تنقضي ساعات العلم **1104** (الافتراضي 0 = معطّل) وبعد عدم تطابق MAC اللقطة مع العلم **1783**.

**MACs** (found):

```
version8    = 8-byte big-endian version
snapshotMac = HMAC-SHA256(snapshotMacKey, ltHash(128) ‖ version8 ‖ UTF8(collection))
patchMac    = HMAC-SHA256(patchMacKey,   snapshotMac ‖ valueMac₁ ‖ … ‖ valueMacₙ ‖ version8 ‖ UTF8(collection))
```

‏`valueMacᵢ` = آخر 32 بايت من كتلة كل قيمة، بترتيب التصحيح. الصادر: الإصدار = المخزّن + 1 لكلا الـ MAC (`C50707Mbo(old + 1)`). يستخدم MAC التصحيح الوارد `snapshot_mac` المحمول في التصحيح؛ ويقارَن MAC اللقطة المعاد حسابه على حدة.

| الفحص الوارد | عدم التطابق |
|----------------|----------|
| MAC التصحيح | قاتل `MacMismatchPatch` (32) |
| MAC اللقطة داخل لقطة | قاتل `SnapshotMacMismatchInSnapshot` (52) |
| MAC اللقطة داخل تصحيح | **غير قاتل** على مسار KMP: `snapshot mac mismatch but do not throw fatal`، رمز تقرير غير قاتل 60، فحص اتساق اختياري (**1783**)؛ مستهلك العلم المُعاد غير محلول |
| غياب `snapshot_mac` / `patch_mac` | قاتل `MissingSnapshotMac` (39) / `MissingPatchSnapshotMac` (40) / `MissingPatchMac` (41) |

---

## 7. مفاتيح المزامنة

### 7.1 المفتاح والتوليد والمفتاح النشط (found)

| البند | القيمة |
|------|-------|
| معرّف المفتاح (`CGH`) | 6 بايت: ‏`deviceId` (2، BE) ‖ `epoch` (4، BE)؛ ‏`SyncdKeyId{deviceId=, epoch=}` |
| بيانات المفتاح | 32 بايت عشوائية |
| الجدول `crypto_info` | `device_id, epoch, key_data, timestamp, fingerprint, stale_timestamp` |
| البصمة | ‏`rawId` و`currentIndex` و`deviceIndexes` من حالة فهرس مفاتيح ADV للحساب عند الإنشاء |
| التوليد (`C12800bm.A05`) | ‏`epoch = max(stored max, in-memory) + 1` (عشوائي في [0,65536) أولًا إذا كان 0)؛ فقط إن لم تكن هناك مشاركة مولَّدة حديثًا قيد الإرسال؛ بلا جهاز آخر يُحفظ المفتاح فورًا، وإلا تُرسل مشاركة (peer 38، `isNewlyGeneratedKey=true`) إلى كل مرافق ويُحفظ المفتاح بعد **إرسال** تلك الرسالة (`CXB.Bss`) |
| المفتاح النشط | أحدث صف في `crypto_info`، أحدث من **14488** يومًا (الافتراضي 30) وصالح البصمة، وإلا يُنشأ مفتاح جديد عند الكتابة التالية |
| فحص البصمة (`A0B`) | ‏`rawId` يساوي raw id المحلي لـ ADV؛ و`deviceIndexes ∪ (currentIndex+1 … local currentIndex)` يساوي مجموعة فهارس الأجهزة المحلية؛ وإلا `one of a peer device is no longer registered` |
| الحارس (`sentinel`، `KeyExpiration`) | تبني `C25048AqM.A00` واحدًا لكل مجموعة (الخمس كلها) مع `expiredKeyEpoch` = أعلى epoch محلي |
| `expireKeysWithEpochIfActive` (`A08`) | تضبط `timestamp = 0` على أحدث مفتاح عندما يكون epoch الخاص به ≤ epoch المعطى؛ المستدعي عند استلام حارس لم يُتتبع (inferred) |
| المفاتيح القديمة (stale) | يعلّم cron اليومي المفاتيح غير المشار إليها من `syncd_mutations`، ويحذفها بعد **14496** يومًا (الافتراضي 31) |
| إعادة التشفير بمفتاح جديد (Re-key) | يُستبدل سجل مخزّن تحت مفتاح مختلف عبر `findMutationWithExpiredKey`؛ شكل REMOVE+SET الدقيق inferred |

### 7.2 الطلب والمفاتيح المفقودة (found، `C12800bm.A07`)

1. تُخزَّن معرّفات المفاتيح المجهولة في `missing_keys(device_id, epoch, collection_name)` وتُطلب برسائل peer لطلب المفاتيح (النوع 39) إلى كل جهاز مسجّل آخر، مع تخطي المعرّفات المعلّقة أصلًا (`missing_key_counter`).
2. يرسل المستجيب مشاركة للمفاتيح التي يملكها (`A0C`، `isNewlyGeneratedKey=false`).
3. دون إجابة طوال **14492** يومًا (الافتراضي 7، أقدم رسالة peer من النوع 39، cron يومي) → قاتل **31** (`TimeoutWhileWaitingForMissingKey`).
4. لا أحد يستطيع توفيره: `MissingKeyOnAllClients`؛ لا أحد لسؤاله: `RequestingMissingKeyWithNoClients`؛ لا مفتاح للتشفير: `MissingActiveKeyForEncryption`.

المشاركات حمولات `ProtocolMessage` ضمن رسائل peer مشفّرة من طرف إلى طرف (found). لم يُعثر على تحقق من البصمة في جهة المستلم لمشاركة واردة (unknown).

---

## 8. التصحيحات الصادرة والكتل الخارجية

**البناء** (found، `OutgoingProcessor`، `KmpSyncdEncryptionProcessor`): تُقسَّم التعديلات المعلّقة (`pending_mutations`، `is_ready_to_sync=1`) لكل مجموعة؛ يُرفض الفهرس المكرر في تصحيح واحد (`SameIndexForMultipleMutationsInOutgoingPatch`)؛ يُحلّ المفتاح النشط؛ يُشفَّر كل تعديل (5.2)؛ LT-Hash جديد من التجزئة المخزّنة (6)؛ ‏`snapshotMac` / `patchMac` بإصدار المخزّن + 1؛ ‏`SyncdPatch{version, mutations | externalMutations, snapshotMac, patchMac, keyId, deviceIndex?, clientDebugData?}`؛ ثم IQ (3.1)؛ وتحمل النتيجة الإصدار الجديد. يخضع `deviceIndex` (الحقل 8) للعلم **14486** الافتراضي true (المستهلك لم يُتتبع).

**قاعدة الرفع الخارجي** (found، `OutgoingProcessor`): ‏`(mutationCount > P14494 or bytes > P14495 × 1024) and bytes > P5097 × 1024`، والقيم الافتراضية 100 / 10 / 0، فأي تصحيح فوق 100 تعديل أو نحو 10 KB يذهب خارجيًا. الكتلة رسالة `SyncdMutations`؛ ويحمل التصحيح حينها `externalMutations` ولا يحمل `mutations` مضمّنة (وجود الاثنين معًا مرفوض: `PatchWithBothInlineAndExternalMutations`). أخطاء الرفع: `Upload transient network error` و`Upload local I/O failure` و`Upload failed`.

**نقل الكتل** (found، `C17650kB`، `C49831Lvs`، `C15530gU`):

| البند | القيمة |
|------|-------|
| نوع الوسائط / info الخاص بـ HKDF لمفتاح الوسائط | ‏`md-app-state` (مسار MMS ‏`mms`) / `WhatsApp App State Keys` |
| حقول المرجع المطلوبة | mediaKey وdirectPath وfileSha256 وfileEncSha256 (غياب أي منها → `MissingExternalBlobReference*`) |
| حالة التنزيل | 5 = منتهي (`ExternalPatchExpired` 3 / `SnapshotExpired` 49، قاتل)؛ الحالات العابرة تُعاد محاولتها؛ والبقية قاتلة |
| المحتوى | تصحيح خارجي → `SyncdMutations`؛ لقطة → `SyncdSnapshot` |

لم يُعد هنا قراءة تخطيط توسيع مفتاح الوسائط المشترك (مشترك، inferred).

**بيانات التصحيح (debug)** (found): ‏`clientDebugData` = `PatchDebugData` (`C49633LsY`: ‏`collection_name` و`current_lthash` و`new_lthash` و`new_lthash_subtract` و`patch_version` و`number_add/remove/override` و`sender_platform` و`is_sender_primary` و`first_four_bytes_from_a_hash_of_snapshot_mac_key`)، لا تُكتب إلا مع العلم **6614** (الافتراضي false)؛ ويسجّلها المستلم بعد عدم تطابق MAC التصحيح.

---

## 9. التصحيحات واللقطات الواردة

| # | الفحص (found) | الفشل: نوع KMP (المعرّف) / الرمز القديم |
|---|---------------|--------------------------------------|
| 1 | للتصحيح `version` | `MissingPatchVersion` (7) / 8 |
| 2 | لا إصدار مكرر في استجابة واحدة | `DuplicatePatchVersionInCollection` (8) / 9 |
| 3 | ليست التعديلات مضمّنة وخارجية معًا | `PatchWithBothInlineAndExternalMutations` (13) / 14 |
| 4 | ‏`version == stored + 1` (`verifyCollectionVersion`) | `ServerDidNotSendAllPatches` (64) |
| 5 | وجود `exit_code` في التصحيح | قديم 36 (الرمز 100)، 37 (101)، 38 (غير ذلك)؛ المقابل في KMP غير محلول |
| 6 | فك تشفير كل التعديلات (5.3) | `DecryptionFailed` (6)، أنواع الشكل |
| 7 | لا فهرس مكرر بين تعديلات SET أو بين تعديلات REMOVE | `SameIndexForMultipleMutationsInPatch` (5) |
| 8 | دورة اعتماد عبر الفهارس | `CyclicMutationDependencyInPatch` (37) |
| 9 | إعادة حساب LT-Hash وMAC التصحيح وMAC اللقطة (6) | `MacMismatchPatch` (32) / غير قاتل |
| 10 | التطبيق عبر معالج كل إجراء (SQLite)، وتخزين الإصدار والتجزئة | يسجّل `Cyclic mutation dependency` و`SQLite error` |

اللقطات: يستلم لقطة المرافق الذي يُقلع فقط (`Only companion devices that are undergoing bootstrap should receive and handle snapshots`). تُنزَّل الكتلة، وتُفك تشفير السجلات كتعديلات التصحيح، وتُرفض الفهارس المكررة (`SameIndexForMultipleMutationsInSnapshot`، 59)، وتُعاد بناء التجزئة، ويُقارَن `snapshot.mac`؛ ثم تُطبَّق تصحيحات `has_more_patches`. ‏`applySnapshot keyMap contains null value, retry` يعيد طلب المفاتيح. تُخزَّن التعديلات اليتيمة (الدردشة الأم مفقودة) مع `are_dependencies_missing=1`، وتُفهرس بـ `chat_jid`، وتُعاد تطبيقها لاحقًا (`SyncdCrossIndexDependencyUtil`).

---

## 10. أنواع إجراءات المزامنة

### 10.1 الكتالوج (found، `EnumC24865AnN` + `AbstractC24863AnL.A00`)

الرقم = حقل `SyncActionValue` الخاص بالقيمة؛ ‏`-` = لا ثابت مطابق في `BD4` (حقل القيمة غير معروف). العنصر 0 في الفهرس هو اسم السلك؛ والعناصر التالية خاصة بكل إجراء ولم تُحصَ.

| المجموعة | اسم السلك = الحقل |
|------------|-------------------|
| `critical_block` (4) | `setting_securityNotification` -, `setting_pushName` 7, `setting_locale` 16, `generated_wui` 52 |
| `critical_unblock_low` (2) | `contact` 3, `lid_contact` 61 |
| `regular_high` (19) | `star` 2, `mute` 4, `deleteMessageForMe` 18, `clearChat` 21, `deleteChat` 22, `userStatusMute` 29, `ugc_bot` 43, `status_privacy` 44, `favorites` 56, `waffle_account_link_state` 58, `ctwaPerCustomerDataSharing` 62, `maiba_ai_features_control` 68, `status_post_opt_in_notification_preferences_action` 71, `private_processing_setting` 74, **`nct_salt_sync` 80**, `biz_ai_settings_nudge` 87, `wasa_root_secret` 89, `shared_device_allowlist` 94, `ai_thread_delete` - |
| `regular` (35) | `quick_reply` 8, `label_message` -, `label_edit` 14, `label_jid` 15, `primary_feature` 24, `deviceAgent` 27, `subscription` 28, `agentChatAssignment` 35, `agentChatAssignmentOpenedStatus` 36, `pnForLidChat` 37, `marketingMessage` 38, `marketingMessageBroadcast` 39, `external_web_beta` 40, `setting_relayAllCalls` 41, `call_log` 42, `delete_individual_call_log` 46, `label_reordering` 47, `setting_disableLinkPreviews` 53, `usernameChatStartMode` 59, `notificationActivitySetting` 60, `setting_channels_personalised_recommendation_optout` -, `broadcast_jid` -, `detected_outcomes_status_action` 66, `business_broadcast_list` 69, `music_user_id` 70, `avatar_updated_action` 72, `galaxy_flow_action` -, `newsletter_saved_interests` 75, `business_broadcast_campaign` 81, `business_broadcast_insights_sync` 82, `subscriptions_sync_v2` 84, `label_sublist` 91, `ctwa_message_received` 93, `shareOwnPn` -, `broadcast` - |
| `regular_low` (36) | `pin_v1` 5, `recent_emoji_weights_action` 11, `archive` 17, `sentinel` 19, `markChatAsRead` 20, `setting_unarchiveChats` 23, `android_unsupported_actions` 26, `time_format` 30, `nux` 31, `primary_version` 32, `favoriteSticker` 33, `removeRecentSticker` 34, `bot_welcome_request` 45, `payment_info` 48, `custom_payment_methods` 49, `lock` 50, `setting_chatLock` 51, `device_capabilities` 54, `note_edit` 55, `merchant_payment_partner` 57, `payment_tos` 63, `ai_thread_rename` 76, `interactive_message_action` 77, `settings_sync` 78, `out_contact` 79, `customer_data` 83, `thread_pin` 85, `setting_autoOrganizeBusinessChat` 86, `coexV2Version` 88, `lock_message` 90, `device_capabilities_v2` 92, `contact_manager_metadata` 95, `business_folder_activation` 96, `group_history_toggle` 97, `bb_pro_pending_customer_base_action` 98, `community_nesting_state` 99 |

لا يملك `BD4` ثابتًا لأرقام الحقول 6 و9 و10 و12 و13 و25 و65 و67 و73. مجموعات الغرض (inferred من الأسماء): حالة الدردشة (`mute` و`pin_v1` و`thread_pin` و`archive` و`markChatAsRead` و`clearChat` و`deleteChat` و`deleteMessageForMe` و`star` و`lock*`)؛ التصنيفات (`label_*`)؛ جهات الاتصال (`contact` و`lid_contact` و`out_contact` و`pnForLidChat` و`shareOwnPn`)؛ إعدادات الحساب (`setting_*` و`time_format` و`status_privacy`)؛ المفاتيح والرموز (`sentinel` و`nct_salt_sync` و`wasa_root_secret` و`generated_wui` و`shared_device_allowlist`)؛ الأعمال والذكاء الاصطناعي والمكالمات والمدفوعات (الباقي).

### 10.2 قيم مختارة (found)

| الإجراء | القيمة |
|--------|-------|
| `nct_salt_sync` (الترتيب 73، `regular_high`) | ‏`NctSaltSyncAction{bytes salt=1}` في الحقل **80** من `SyncActionValue`؛ هكذا يسلّم الأساسي ملح NCT إلى المرافقين، أما المصدر والاستخدام ففي `WA_TCTOKEN_CSTOKEN.md` (3.2) |
| `contact` (`ContactAction`) | fullName 1, firstName 2, lidJid 3, saveOnPrimaryAddressbook 4, pnJid 5, username 6, birthday 7؛ ينشئه الأساسي فقط، فيحصل المرافق الذي يُقلع على دفتر عناوينه قبل أي مجموعة `regular*` |
| `mute` (`MuteAction`) | muted 1, muteEndTimestamp 2, autoMuted 3, muteEveryoneMentionEndTimestamp 4 |
| `sentinel` | `KeyExpiration{expiredKeyEpoch}` (7.1) |
| `android_unsupported_actions` (26)، العلم **14490** (الافتراضي false) | مسار "Android unsupported mutation"؛ الدلالة غير معروفة |

---

## 11. الأخطاء القاتلة وإعادة المحاولة والاستعادة

### 11.1 أنواع KMP القاتلة (found، `Lx6.A00`؛ المعرّفات داخلية وليست قيم سلك)

| المجموعة | المعرّفات والأسماء |
|-------|---------------|
| النقل | 53 `XmppBadRequestForCollection`, 54 `…NotFoundForCollection`, 55 `XmppBadRequestGlobalError`, 56 `…NotFoundGlobalError`, 57 `…BadMethodGlobalError`, 58 `…NotAcceptableGlobalError` |
| شكل التصحيح / اللقطة | 4 `MissingOrEmptyIndex`, 5 `SameIndexForMultipleMutationsInPatch`, 7 `MissingPatchVersion`, 8 `DuplicatePatchVersionInCollection`, 13 `PatchWithBothInlineAndExternalMutations`, 37 `CyclicMutationDependencyInPatch`, 38 `MissingSnapshotVersion`, 47 `MissingPatchKeyId`, 50 `MissingSnapshotKeyId`, 59 `SameIndexForMultipleMutationsInSnapshot`, 64 `ServerDidNotSendAllPatches`, 65 `ServerSentEarlierPatch`, 71 `InvalidSnapshotRecords` |
| شكل التعديل / الإجراء | 10-12, 14-16, 19-24 (`MissingMutationVersion/Value/Index/Operation/Record/KeyId`, `MissingActionIndex/Value/Version/Timestamp`, `InvalidMutationIndex`, `InvalidActionIndex`) |
| التشفير | 6 `DecryptionFailed`, 9 `EncryptionFailed`, 31 `MacMismatchSnapshot`, 32 `MacMismatchPatch`, 39-41 `Missing*Mac`, 51 `SnapshotMacMismatchInPatch`, 52 `SnapshotMacMismatchInSnapshot` |
| المفاتيح | 29 `MissingKeyOnAllClients`, 30 `TimeoutWhileWaitingForMissingKey`, 46 `InvalidKeyShareKeyId`, 48 `InvalidKeyShareKeyData`, 62, 66-69 (`RequestingMissingKeyWithNoClients`, `MissingKeyForMutationInLocalSnapshot`, `MissingActiveKeyAfterRotation`, `MissingActiveKeyForEncryption`, `MissingCurrentEpochForActiveKeyValidation`) |
| الكتل / protobuf | 3 `ExternalPatchExpired`, 49 `SnapshotExpired`, 42-45 و72 `MissingExternalBlobReference*`, 60 / 61 فشل تحليل المرجع / اللقطة, 17 / 18 / 25-28 أنواع (de)serialisation, 34-36 `TerminalPatch*` |
| محلي | 33 `DbStoreNotReady`, 63 `DbStoreNotReadyLowDiskSpace`, 70 `SameIndexForMultipleMutationsInOutgoingPatch` |

### 11.2 الرموز الرقمية القديمة (found، `C49784Lv2.errorCode`، تغذّي WAM ‏`md_fatal_error`؛ ترقيم منفصل)

8 / 9 / 14 (`N90`: لا إصدار / إصدار مكرر / مضمّن + خارجي)، 18 / 69 (فشل تحليل التصحيح / اللقطة)، 36 / 37 / 38 (‏`exit_code` ‏100 / 101 / غير ذلك)، 64-67 (أخطاء IQ العامة 400 / 404 / 405 / 406)، 71 (فشل حلّ المفتاح بعد طلب المفتاح المفقود)، 31 (مهلة انتظار المفتاح)، 60 (عدم تطابق غير قاتل لـ MAC اللقطة في تصحيح، `A0F(60, collection, false)`). التطابق مع أنواع KMP غير محلول.

### 11.3 ردّ الفعل على فشل قاتل (found، `SyncResponseHandler.A08`، `C12440bB.A0S/A0Q`)

| الدور | الإجراء |
|------|--------|
| أي دور | تسجيل `app-state-sync-handle-fatal-exception`، وWAM ‏`md_fatal_error`، ومسح المزامنة الجارية |
| العلم **25799** | المرافق: `companion_syncd_dirty=true`؛ الأساسي: `C17630k8.A01(1)` (سبب التلوث 1، inferred) |
| الأساسي | ‏`A0Q(1)` حذف كل بيانات syncd. آلة التلوث (`C17630k8`، السلسلة من `A0Q` inferred): عدّاد `syncd_dirty` حتى 4، و`syncd_dirty_reason`، و`<iq xmlns="w:sync:app:state" type="set"><delete_all_data/></iq>` (سمة type inferred)، و`logoutAllCompanionDevices` |
| المرافق | ‏`companion_syncd_dirty=true`، ورسالة peer ‏`AppStateFatalExceptionNotification` (FMessage 50) إلى الأساسي (الجهاز 0)، وانتظار 5 ثوانٍ، وتسجيل خروج بـ `syncd_failure` أو `syncd_error_during_bootstrap` |

نافذة إعادة محاولة حذف الكل **14493** دقيقة (الافتراضي 360). ينظّف الأساسي عندما أُلغي تسجيل مرافق ولم يبقَ أي مرافق (`shouldCleanUpSyncd`).

### 11.4 استعادة اللقطة (found، `KmpSyncdFatalErrorRecovery`)

مشروطة بخاصية العميل `isSyncdSnapshotRecoveryEnabled`. يرسل المرافق عملية بيانات peer ‏`COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` (8) مع `SyncDCollectionFatalRecoveryRequest{collectionName}`. يبني المستجيب `SyncdSnapshotRecovery` من تعديلاته المخزّنة **النصية الصريحة** (`syncd_mutations`، و`collection_versions.version / lt_hash`)، ويضغطها بـ gzip ويعيد `SyncDSnapshotFatalRecoveryResponse`. حالات الرفض: `Invalid collection name` (طلب لـ `critical_block`) و`Collection version/ltHash invalid` و`Snapshot keyId invalid` و`Mutation count (…) more than the limit` و`Mutation snapshot data size (…) more than the limit` و`Error encoding mutation data` و`Compression failed` (خصائص الحدود لم تُحلّ). يسافر النص الصريح داخل رسالة peer مشفّرة من طرف إلى طرف. لم يُتتبع تطبيق جهة المرافق (unknown).

---

## 12. الحالة المحلية وأعلام الميزات

| المخزن | المحتوى (found) |
|-------|-----------------|
| `syncd_mutations` | `mutation_index` (فريد)، `mutation_value`، `mutation_version`، `collection_name`، `are_dependencies_missing`، `mutation_mac`، `device_id`، `epoch`، `chat_jid`، `mutation_name` |
| `collection_versions` / `pending_mutations` / `missing_keys` / `crypto_info` | ‏`collection_name, version, lt_hash` / طابور الصادر (`is_ready_to_sync`) / طلبات المفاتيح / مفاتيح المزامنة |
| Prefs | `syncd_bootstrap_state`, `companion_syncd_critical_bootstrap_state`, `syncd_dirty`, `syncd_dirty_reason`, `companion_syncd_dirty`, `syncd_last_companion_dereg_time`, `syncd_last_lthash_consistency_check_time`, `first_transient_server_failure_timestamp` |

يبلّغ cron اليومي (`C46413KPv`) عن العدّادات `mutation_counter` و`invalid_action_counter` و`upload_conflict_counter` و`unsupported_action_counter` و`cross_index_conflict_counter` و`unset_action_mutation_counter` و`key_rotation_remove_counter` و`missing_key_counter`.

| معرّف العلم | النوع / الافتراضي | ما يتحكم به |
|---------|----------------|----------|
| **15909**, **20682**, **18234** | bool / false | ‏`XplatSyncdEncryptionManager` مقابل الافتراضي (`AbstractC17550k0`)؛ KMP الوارد (`RunnableC53542Nwj`)؛ KMP الصادر (`C12440bB`). قيم افتراضية مترجمة فقط، والقيمة الحية غير معروفة. اسم 15909 في بناء سابق: `KMP_SYNCD_ENGINE_CRYPTO_ENABLED` (إعادة استخدام المعرّف inferred) |
| **14488** / **14496** / **14492** | int / 30 / 31 / 7 | عمر المفتاح النشط، مدة الاحتفاظ بالمفاتيح القديمة، مهلة انتظار المفتاح (أيام) |
| **14493** | int / 360 | نافذة حذف الكل / إلغاء التسجيل (دقائق) |
| **14494**, **14495**, **5097** | int / 100, 10, 0 | عتبات التصحيح الخارجي |
| **14497** | int / 1000 | حد تحميل تعديلات قاعدة البيانات (inferred) |
| **1104** / **1783** | int 0 / bool false | فاصل فحص الاتساق (ساعات) / فحص بعد عدم تطابق MAC اللقطة |
| **6614** | bool / false | `clientDebugData` في التصحيحات |
| **25799** | bool / false | معالجة حالة التلوث عند الفشل القاتل |
| **27528** | bool / false | توليد مفتاح عندما لا يملك الأساسي أي مفتاح |
| **14486** | bool / true | `deviceIndex` في التصحيحات (المستهلك لم يُتتبع) |
| **14489**, **14490**, **1221**, **624** | int 90 / bool false / bool false / bool | حد `min()` في `C15310g7` (غير محلول) / مسار التعديلات غير المدعومة / إحصاءات التعديلات / تجزئات كاملة في السجلات |

---

## 13. حالات الخطأ

| العَرَض | السبب | الإصلاح |
|---------|-------|-----|
| `Data MAC mismatch` | مفتاح خاطئ، أو كتلة معبوث بها، أو بايت op أو keyId خاطئ في AAD | المفتاح المسمّى في `record.keyId`؛ ‏AAD = `op ‖ keyId`، ‏op 1 SET / 2 REMOVE |
| `Index MAC mismatch` | نص الفهرس يختلف بايتًا ببايت (مسافات JSON) | احسب MAC على نص UTF-8 الدقيق لـ `SyncActionData.index` |
| قاتل 64 `ServerDidNotSendAllPatches` | إصدار التصحيح ≠ المخزّن + 1 | أعد المزامنة من الإصدار المخزّن؛ اطلب لقطة إن فُقدت الحالة |
| عدم تطابق MAC التصحيح (32) | انحراف LT-Hash، أو عرض version8، أو MAC لقطة من مصدر خاطئ | استخدم `snapshot_mac` الخاص بالتصحيح أولًا؛ الإصدار بصيغة 8 بايت big-endian |
| `PatchWithBothInlineAndExternalMutations` | الحقلان مضبوطان معًا | أرسل واحدًا |
| `MissingActionTimestamp` | غياب `SyncActionValue.timestamp` في SET | اضبط الحقل 1 |
| مفتاح مفقود | لم تُستلم المشاركة | طلب من النوع 39؛ قاتل 31 بعد 7 أيام |
| `one of a peer device is no longer registered` | تغيّرت قائمة الأجهزة منذ إنشاء المفتاح | المفتاح غير صالح كمفتاح نشط؛ ولّد مفتاحًا جديدًا |
| خطأ IQ ‏400 / 404 / 405 / 406 | شكل طلب سيئ، مجموعة مجهولة | قاتل؛ صحّح الطلب |
| `ExternalPatchExpired` / `SnapshotExpired` | حالة الكتلة 5 | استعادة اللقطة أو إعادة الربط |
| تسجيل خروج المرافق `syncd_failure` | فشل قاتل غير قابل للاسترداد | أعد الاقتران، أو استعادة اللقطة إن كانت مفعّلة |

---

## 14. فروق أساسية

| لا تخلط بين | وبين |
|----------------|------|
| مفتاح المزامنة (32 بايت عشوائية لكل جهاز+epoch) | مفاتيح التعديلات (ناتج HKDF، خمس شرائح) |
| MAC الفهرس (HMAC-SHA256 على نص الفهرس) | MAC القيمة (HMAC-SHA512 مقتطع إلى 32 على AAD + iv + ct + len) |
| MAC القيمة (لكل تعديل) | MAC اللقطة (LT-Hash + الإصدار + المجموعة) وMAC التصحيح (MAC اللقطة + كل MAC القيم) |
| عقدة `<snapshot>` (هي `ExternalBlobReference`) | رسالة `SyncdSnapshot` proto (محتوى الكتلة)؛ وكذلك `externalMutations` مقابل `SyncdMutations` |
| `critical_block` على Android (إعدادات الحساب) | مجموعة قائمة حظر (لم توجد) |
| أنواع `ProtocolMessage` ‏6 / 7 / 10 | أرقام الحقول 7 / 8 / 10 |
| حقل طلب peer data رقم 7 | حقل استجابة peer data رقم 8 |
| معرّفات أنواع KMP (`Lx6`) | أعداد `errorCode` القديمة |
| `sentinel` (علامة انتهاء المفتاح في المجموعات الخمس كلها) | `primary_version` و`android_unsupported_actions` |
| جداول إجراءات / مجموعات WhatsApp Web | جدول Android هنا (96 إجراءً، توزيع مختلف) |

---

## 15. Baileys (`baron-baileys-v2` 1.5.17)

فقط الوقائع المقروءة في `src/Utils/chat-utils.js` و`src/Socket/chats.js` و`src/Utils/process-message.js`. لم يُختبر شيء مقابل خادم؛ ولا يُدّعى أي فشل.

| الموضوع | Baileys | Android |
|-------|---------|---------|
| توسيع المفاتيح، LT-Hash | جسر native ‏`expandAppStateKeys`، ‏`LTHashAntiTampering` (128 بايت)؛ أسماء الشرائح الخمس نفسها | 5.1، 6 |
| MAC القيمة | ‏`HMAC-SHA512(op ‖ keyId ‖ data ‖ 8 bytes, last = len)[0..32)`، ‏op 1 / 2 | متطابق |
| MAC اللقطة / التصحيح | المدخلات والترتيب نفسهما؛ ‏`ver8` يكتب الـ 32 بت الدنيا فقط | 64 بت كاملة big-endian |
| الفهرس، الحشو | ‏`JSON.stringify(index)`، حشو فارغ | نفسه |
| الكتلة الخارجية | ‏`downloadContentFromMessage(blob, 'md-app-state')` | نوع الوسائط نفسه |
| المجموعات | ‏`critical_block, critical_unblock_low, regular_high, regular_low, regular` | الأسماء نفسها |
| عقدة الطلب | ‏`<sync>` بلا سمات؛ ‏`<collection name version return_snapshot>`، و`return_snapshot` دائمًا `'true'`/`'false'` | ‏`data_namespace="3"`، و`order`، و`return_snapshot` فقط عند true |
| إرسال التصحيح | ‏`version = state.version − 1`، ‏`return_snapshot='false'` | الإصدار المخزّن |
| استمرارية الإصدار | لا تُفحص (`newState.version = patchVersion`)؛ إصدار تصحيح مفقود يصبح إصدار المجموعة + 1 | يجب أن يساوي المخزّن + 1 |
| MAC اللقطة في تصحيح | يُعاد حسابه، ويرمي `failed to verify LTHash` | غير قاتل على مسار KMP |
| مشاركة المفتاح | يخزّن `keyData` فقط لكل معرّف مفتاح base64؛ ‏`myAppStateKeyId` = آخر مفتاح في الرسالة | يحتفظ بالبصمة والطابع الزمني، ويتحقق من البصمة، ويختار أحدث مفتاح صالح |
| الإشعار القاتل | يُسجَّل، ويُصدر كحدث `app-state.sync-error` | المرافق يرسل، والأساسي يتصرف |
| إعادة المحاولة | ‏`MAX_SYNC_ATTEMPTS = 2`، وإعادة محاولة بلقطة قسرية، والمفتاح المفقود يوقف المجموعة | القسم 11 |
| ملح NCT | ‏`nctSaltSyncAction.salt` يُخزَّن كـ `nct-salt` | 10.2 |

غير موجود في مصدر Baileys: ‏`data_namespace` و`order` ومعالجة `exit_code` واستعادة اللقطة. الأثر على الخادم غير معروف.

---

## 16. التدفقات الكاملة

### 16.1 الأساسي يكتب تغييرًا (مثال `mute`)

```
[User]  → handler builds mutation  ["mute","<chatJid>"]  MuteAction  collection regular_high
     │
     ▼
[SyncManager C12440bB]  pending_mutations ; active key (≤ 30 d, fingerprint ok) else generate, share (peer 38)
     │
     ▼
[Encrypt]  iv ; AES-CBC ; aad = 01 ‖ keyId ; valueMac ; indexMac
     │     ltHash' = ltHash − oldValueMac + newValueMac ; ver = stored + 1 ; snapshotMac ; patchMac
     │     SyncdPatch inline, or externalMutations above the thresholds (md-app-state upload)
     ▼
iq set w:sync:app:state  <sync data_namespace=3><collection name order version><patch/></collection></sync>
     │
     ▼
[WA Server]  (not observed) orders patch, assigns version
     │
     ▼
Result <collection name version="N+1"/>  →  store version, hash, mutation_mac
     │
     ▼
[Companions]  sync (16.2)
```

### 16.2 المرافق يسحب

```
[Companion]  iq set  <collection name version=V [return_snapshot=true if V=0]/>
     │
     ▼
Result <collection has_more_patches?> [<snapshot ExternalBlobReference/>] <patches><patch/>…</patches>
     │
     ├─ snapshot ─► download md-app-state ─► SyncdSnapshot ─► decrypt ─► hash ─► snapshot MAC
     └─ each patch (V+1 …) ─► version check ─► external blob? download SyncdMutations
            │  key unknown ─► missing_keys + peer 39 ─► [Primary] peer 38 share
            │  decrypt (valueMac → AES → SyncActionData → indexMac) ; ltHash − old + new
            │  patchMac ; snapshotMac ; action handler apply (are_dependencies_missing for orphans)
            ▼
         store version, hash ; has_more_patches → repeat
```

### 16.3 فشل قاتل

```
[Companion]  patch MAC mismatch / key timeout / version gap
     ├─ recovery enabled ─► peer data op 8 {collectionName} ─► [Primary] SyncdSnapshotRecovery (gzip)
     └─ else companion_syncd_dirty ; peer AppStateFatalExceptionNotification ; 5 s ; logout syncd_failure
               ▼
         [Primary]  delete syncd data ; iq <delete_all_data/> ; logout companions ; re-pair
```

---

## 17. المجهولات

| البند | الحالة |
|------|--------|
| المحرك الفعّال (قديم أو KMP) لكل حساب | أعلام الخادم |
| معنى السمة `order` | unknown |
| فحص البصمة في جهة المستلم لمشاركة مفتاح واردة | لم يُعثر عليه |
| جهة تطبيق `sentinel` المستلَم (`expireKeysWithEpochIfActive`) | لم يُتتبع |
| التطابق بين أنواع KMP والرموز القديمة؛ مُحفِّز `ServerSentEarlierPatch`؛ معنى `exit_code` ‏100 / 101 | غير محلول |
| حقل القيمة للإجراءات التسعة المعلّمة بـ `-` | unknown |
| جهة تطبيق استعادة اللقطة، خصائص الحدود | لم يُتتبع |
| ترتيب الخادم والاحتفاظ وقواعد الدمج | جهة الخادم |
| حركة الشبكة | لم يُلتقط شيء |
