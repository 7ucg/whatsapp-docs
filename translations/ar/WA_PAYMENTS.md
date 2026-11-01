<!-- src-sha1: 1fe6d8278b8f0a0adfe50041466f968ec368a2e2 -->
# WhatsApp المدفوعات — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-01
**النطاق:** أنواع رسائل الدفع داخل المحادثة (`sendPaymentMessage`، `requestPaymentMessage`، `declinePaymentRequestMessage`، `cancelPaymentRequestMessage`، تقسيم الدفعات، دعوة/تذكير الدفع) وحقولها في البروتو، بنية العميل متعددة المسارات (UPI في الهند، Pix في البرازيل، المكسيك، إندونيسيا، مسار "UPR" العام)، ربط VPA/الحساب المصرفي وتدفّق التأهيل في UPI، طبقة بيانات الاعتماد/PIN/ربط الجهاز الخاصة بمكتبة NPCI المضمَّنة ("Common Library" — CL)، مزامنة حالة المعاملة، طبقات التشفير (تشفير المحادثة من طرف إلى طرف مقابل كتلة بيانات اعتماد NPCI)، عمليات GraphQL/MEX للدفع (doc_ids)، قواعد القراءة التلقائية لرمز OTP الخاص بـ NPCI، أعلام الميزات، معالجة رموز الرفض/الخطأ

---

## 1. ما هو (نظرة عامة)

يشحن WhatsApp Android بروتوكول دفع واحد مشترك داخل المحادثة (أنواع رسائل بروتو محمولة داخل `Message` العادية والمشفرة من طرف إلى طرف) بالإضافة إلى عدة *مسارات* دفع خاصة بكل بلد، كل واحد منها له واجهة تأهيل خاصة به وعمليات GraphQL، وبالنسبة للهند، مكتبة بيانات اعتماد مضمَّنة من طرف ثالث. كل النتائج هي تحليل ساكن للـ APK المفكوك؛ لم يُلتقط شيء على الشبكة. المستويات: **found** = مقروء مباشرة في الكود/الأصول، **inferred** = مستنتج من الكود، **unknown** = غير محلول. الأسماء المبهمة خاصة بكل إصدار بناء وأُعيد حلها في 2.26.41.6 من سلاسل ثابتة (ثوابت `FIELD_NUMBER`، أسماء واجهات AIDL، كتالوجات عمليات GraphQL، أسماء ملفات الأصول).

| الطبقة | الاسم/المسار في 2.26.41.6 | الدور |
|-------|------------------------|------|
| بروتوكول رسائل المحادثة | `DSJ` SendPaymentMessage، `C30605DSz` RequestPaymentMessage، `C30502DPa` DeclinePaymentRequestMessage، `DPZ` CancelPaymentRequestMessage، `DT0`/`C30535DQh` تقسيم الدفعة، `C30586DSg` PaymentInviteMessage، `C43112IrN` PaymentReminderMessage، `DTS` PaymentInfo | الحقول في القسم 2 |
| حزم المسارات | `com.whatsapp.payments.{common,indiaupi,brazilpay,mexico,indonesia,globalorder,upr,dcp,remittances,split,paymentkey,productinfra,integrity,phoenix}` | حزمة واحدة لكل سوق/مسار، القسم 3 |
| مكتبة بيانات اعتماد UPI الهندية | `org.npci.upi.security.{services,pinactivitycomponent}` (`CLRemoteService`، `CLRemoteServiceImpl`، `BinderC48420LDc`، `GetCredential`) | مكتبة NPCI "Common Library" (CL) المضمَّنة، القسم 6 |
| القراءة التلقائية لـ OTP | `assets/npci/npci_otp_rules.json`، المستهلك `org.npci.upi.security.pinactivitycomponent.C0315u` | القسم 10 |
| كتالوج GraphQL/MEX | `assets/whatsapp-android-www_client_persist_ids.json` (مخطط `whatsapp`)، `whatsapp-android-mex_client_persist_ids.json` (مخطط `whatsapp_mex`) | doc_ids، القسم 9 |
| معالج دفع الخادم | `C24410wL` ("PaymentsMessageHandler"، وسم السجل `PaymentsMessageHandler`) | `<notification type="pay\|upi\|fbpay\|transaction\|account-recovery\|alert\|...">`، القسم 8 |
| كائن المعاملة | `F7F` (سجل المعاملة المحلي)، `DTS` (PaymentInfo السلكي/لمزامنة السجل)، يُبنى بواسطة `EKY.A00` | القسم 8 |

المسارات المحددة من أسماء الحزم/الفئات (found): **UPI الهند** (`indiaupi`)، **Pix البرازيل** (`brazilpay`)، **المكسيك** (`mexico`)، **إندونيسيا** (`indonesia`)، بالإضافة إلى حزمة عامة لا تخص مسارًا محددًا بعينه تُسمى "**UPR**" (`upr` — التأهيل، إدارة الحساب، واجهة الفقاعة) ومرجع قديم لـ Meta Pay/Novi ما يزال موجودًا في كود التعداد/الإشعارات (`FBPAY`، `NOVI`) رغم أن تلك الخدمات توقفت منذ زمن طويل — أُدرجت هنا فقط لأن السلاسل الحرفية ما زالت موجودة في 2.26.41.6. النتائج أدناه موسومة **خاصة بالهند/UPI** أو **عامة** حسب القسم؛ لا تفترض أن نتائج UPI تنطبق على Pix/المكسيك/إندونيسيا.

---

## 2. أنواع رسائل الدفع وحقول البروتو

### 2.1 الموضع داخل `Message` (found)

كل أنواع رسائل الدفع هي حقول مباشرة ضمن بروتو `Message` على المستوى الأعلى (`C30628DTw`، وهي الفئة نفسها الموثَّقة في `WA_MESSAGE_SECRETS.md`). معظم رسائل الدفع الفرعية **لا** تعرض ثوابت `FIELD_NUMBER` علنية على `Message` نفسها؛ الأرقام أدناه استُخرجت بفك ترميز سلسلة معلومات الرسالة المحزومة الخاصة بالفئة (`GeneratedMessageLite`) (ترميز قابل للتكرار بمعدل 2 أو 3 أحرف لكل حقل: حرف رقم الحقل، حرف علامة النوع، حرف فهرس الـ has-bit؛ فهرس has-bit يتزايد بمقدار واحد تمامًا لكل إدخال عبر الرسالة الكاملة البالغة نحو 150 حقلًا، وهذا فحص اتساق داخلي قوي على عملية الفك).

| الحقل (في `Message`) | الرقم | النوع |
|---|---|---|
| `sendPaymentMessage` | **16** | `SendPaymentMessage` (`DSJ`) |
| `requestPaymentMessage` | **22** | `RequestPaymentMessage` (`C30605DSz`) |
| `declinePaymentRequestMessage` | **23** | `DeclinePaymentRequestMessage` (`C30502DPa`) |
| `cancelPaymentRequestMessage` | **24** | `CancelPaymentRequestMessage` (`DPZ`) |
| `paymentInviteMessage` | **44** | `PaymentInviteMessage` (`C30586DSg`) |
| `splitPaymentMessage` | لم يُفك ترميزه في هذا التمرير | `SplitPaymentMessage` (`DT0`)، `unknown` |
| `splitPaymentUpdateMessage` | لم يُفك ترميزه في هذا التمرير | `SplitPaymentUpdateMessage` (`C30535DQh`)، `unknown` |
| `paymentReminderMessage` | لم يُفك ترميزه في هذا التمرير | `PaymentReminderMessage` (`C43112IrN`)، `unknown` |

مُصنِّف `<message type="pay">` على مستوى stanza (مشترك مع أنواع إضافية أخرى) موثَّق في `WA_MESSAGE_SECRETS.md` في قسم مُختار النوع (`AbstractC30999De0.A02`)؛ لم يُعَد استخراجه هنا.

### 2.2 SendPaymentMessage (`DSJ`، found)

| الحقل | الرقم | النوع | الاستخدام |
|---|---|---|---|
| `noteMessage` | **2** | `Message` (`C30628DTw`) | "الملاحظة" المرفقة بالدفعة هي نفسها رسالة `Message` كاملة (تحمل عادةً `extendedTextMessage` أو ملصقًا فقط) |
| `requestMessageKey` | **3** | `MessageKey` (`BD5`) | موجود عندما يكون هذا الإرسال ردًا على `requestPaymentMessage` سابقة |
| `background` | **4** | `PaymentBackground` (`DTJ`) | القسم 2.7 |
| `transactionData` | **5** | string | غير معروف المحتوى؛ القيمة الافتراضية في الكود المفكوك هي ثابت سلسلة نصية فارغة مشترك، ليست قيمة افتراضية حقيقية |

رقم الحقل 1 غير مستخدم/محجوز (لا يوجد ثابت `FIELD_NUMBER` له).

### 2.3 RequestPaymentMessage (`C30605DSz`، found)

| الحقل | الرقم | النوع | الاستخدام |
|---|---|---|---|
| `currencyCodeIso4217` | **1** | string | رمز ISO 4217 |
| `amount1000` | **2** | int64 | المبلغ × 1000 (نقطة ثابتة، بدون كسور في القيمة السلكية) |
| `requestFrom` | **3** | string | معرّف مُقدِّم الطلب (JID مرصود في مواقع الاستدعاء) |
| `noteMessage` | **4** | `Message` | نفس النمط في 2.2 |
| `expiryTimestamp` | **5** | int64 | ثوانٍ يونكس |
| `amount` | **6** | `Money` (`C30561DRh`) | مبلغ مُهيكل، القسم 2.7 |
| `background` | **7** | `PaymentBackground` (`DTJ`) | القسم 2.7 |

### 2.4 DeclinePaymentRequestMessage / CancelPaymentRequestMessage (found)

كلتا الرسالتين بسيطتان للغاية — حقل واحد يشير إلى الطلب الأصلي:

| الفئة | الحقل | الرقم | النوع |
|---|---|---|---|
| `DeclinePaymentRequestMessage` (`C30502DPa`) | `key` | **1** | `MessageKey` (`BD5`) |
| `CancelPaymentRequestMessage` (`DPZ`) | `key` | **1** | `MessageKey` (`BD5`) |

**لا تحمل أي من الرسالتين حقل سبب/رمز خطأ.** الرفض والإلغاء هما عمليتان لا أثر لهما في البروتوكول سوى "هذا الطلب (المحدَّد بـ `key`) مرفوض/ملغى"؛ أي نص سبب يظهر في الواجهة محلي فقط، وليس جزءًا من الحمولة السلكية (found: لا يوجد حقل ثانٍ على أي من الفئتين؛ انظر القسم 12).

### 2.5 تقسيم الدفعات (found)

`SplitPaymentMessage` (`DT0`):

| الحقل | الرقم | النوع |
|---|---|---|
| `splitId` | **1** | string |
| `totalAmount` | **2** | `Money` |
| `description` | **3** | string |
| `requesterJid` | **4** | string |
| `participants` | **5** | repeated `SplitPaymentParticipant` (`C30558DRe`) |
| `createdAtMs` | **6** | int64 |
| `contextInfo` | **17** | شبيه بـ `MessageContextInfo` (`C30617DTl`) |

`SplitPaymentUpdateMessage` (`C30535DQh`): `splitId` (**1**، string)، `participantJid` (**2**، string) — إشعار حالة لكل مشارك، بدون حمولة مبلغ/حالة خاصة به.

### 2.6 PaymentInviteMessage / PaymentReminderMessage (found)

`PaymentInviteMessage` (`C30586DSg`): `serviceType` (**1**، int/enum — يرتبط برموز الخدمة `UPI`/`PIX`/`NOVI`/`FBPAY` المرصودة في القسم 8)، `expiryTimestamp` (**2**، int64)، `incentiveEligible` (**3**، bool)، `referralId` (**4**، string)، `inviteType` (**5**، int/enum).

`PaymentReminderMessage` (`C43112IrN`):

| الحقل | الرقم | النوع |
|---|---|---|
| `reminderId` | **1** | string |
| `instanceId` | **2** | string |
| `description` | **3** | string |
| `frequency` | **4** | int/enum |
| `status` | **5** | int/enum |
| `payeeVpa` | **6** | string |
| `payeeJid` | **7** | string |
| `payerJid` | **8** | string |
| `amount` | **9** | `Money` |

`payeeVpa` (الحقل 6) هو **حقل VPA حرفي في بروتوكول السلك** — تأكيد مباشر على مستوى البروتو بأن عناوين الدفع الافتراضية لـ UPI تنتقل داخل رسائل المحادثة، وليس فقط عبر قنوات GraphQL الجانبية.

### 2.7 الأنواع الداعمة (found)

| النوع | الفئة | الحقول |
|---|---|---|
| `Money` | `C30561DRh` | `value` (**1**، int64)، `offset` (**2**، int32 — إزاحة الفاصلة العشرية)، `currencyCode` (**3**، string) |
| `MessageKey` | `BD5` | `remoteJid` (**1**، string)، `fromMe` (**2**، bool)، `id` (**3**، string)، `participant` (**4**، string) |
| `PaymentBackground` | `DTJ` | `id` (**1**، string)، `fileLength` (**2**، int64)، `width` (**3**، int32)، `height` (**4**، int32)، `mimetype` (**5**، string)، `placeholderArgb` (**6**، int32)، `textArgb` (**7**، int32)، `subtextArgb` (**8**، int32)، `mediaData` (**9**، `MediaData` `C30588DSi`)، `type` (**10**، enum) |

### 2.8 PaymentInfo — كائن حالة المعاملة (found)

`DTS` ("PaymentInfo") **ليست** نوع رسالة محادثة؛ بل مرفقة بـ `WebMessageInfo` (`C30626DTu`، حامل مزامنة السجل/الجهاز المرافق الموثَّق في `WA_MESSAGE_SECRETS.md`) كـ `paymentInfo_` و `quotedPaymentInfo_`. تمثّل الحالة المعروفة الحالية لمعاملة دفع، وتُبنى من سجل المعاملة المحلي بواسطة `EKY.A00`:

| الحقل | الرقم | النوع | ملاحظة |
|---|---|---|---|
| `currencyDeprecated` | **1** | enum | قديم |
| `amount1000` | **2** | int64 | |
| `receiverJid` | **3** | string | |
| `status` | **4** | enum | حالة عامة تقريبية |
| `transactionTimestamp` | **5** | int64 | |
| `requestMessageKey` | **6** | `MessageKey` | |
| `expiryTimestamp` | **7** | int64 | |
| `futureproofed` | **8** | bool | يُضبط عندما لا يكون لكائن المعاملة المحلي للمرسل عملة/مبلغ قابل للحل (منفذ احترازي لتطور المخطط) |
| `currency` | **9** | string | |
| `txnStatus` | **10** | enum | حالة أدق تفصيلًا (على مستوى NPCI)، تعداد مستقل عن `status` |
| `useNoviFiatFormat` | **11** | bool | علم قديم لتنسيق العرض لـ Meta Pay/Novi |
| `primaryAmount` | **12** | `Money` | |
| `exchangeAmount` | **13** | `Money` | عرض عابر للعملات |

أسماء ثوابت تعداد `status`/`txnStatus` ممحوّة بواسطة المُعتِّم على مستوى الـ javalite bytecode (لم يتبقَّ سوى الأرقام الترتيبية وفئات `EnumVerifier`)؛ تعيين الرقم الترتيبي إلى التسمية `unknown` في هذا التمرير. تقرأ `EKY.A00` العملة/المبلغ من كائن المعاملة المحلي، وعند غيابهما تضبط `futureproofed=true` بدلًا من التخمين — found في الكود (شرط `f7fA00.A03 == 5 || !f7fA00.A0N()`).

---

## 3. بنية العميل متعددة المسارات ("مكتبة الدفع المشتركة")

كود الدفع منظَّم كحزمة واحدة مشتركة للواجهة/البنية التحتية بالإضافة إلى حزمة واحدة لكل مسار سوق (found، من تخطيط الحزم تحت `com.whatsapp.payments`):

| الحزمة | المسار | المحتوى (found) |
|---|---|---|
| `common` | مشترك | `p144ui` (أوراق سفلية عامة للدفع، الإعدادات، سجل المعاملات، أدوات اختيار الطريقة)، `pin` (واجهة إدخال PIN مشتركة بين المسارات)، `paymentkeys`، `compliance`، `care` (CSAT)، `qpl` (علامات تسجيل الجودة/الأداء) |
| `indiaupi` | UPI الهند | التأهيل، ربط الحساب المصرفي/VPA، التفويضات، دفع الفواتير، UPI Lite، رمز QR، استعادة الحساب — القسم 4 |
| `brazilpay` | Pix البرازيل | إدارة مفاتيح Pix، تسجيل البيومتري/مفتاح المرور، CPF |
| `mexico`، `indonesia` | مسارات محلية | موجودة كحزم؛ لم تُستكشف أبعد من مجرد الوجود في هذا التمرير (`unknown` التفاصيل) |
| `upr` | غير مرتبط بمسار محدد | `nux` (التأهيل)، `accountmanagement`، `bubble` (ورقة خيارات الدفع داخل المحادثة)، `shared` (أدوات اختيار المؤسسة/نوع الحساب) — يرتبط بعمليات GraphQL `GenUprPaymentConfig`/`GenUprPaymentConfigForViewer` (القسم 9)؛ توسيع "UPR" غير مذكور حرفيًا في أي سلسلة وُجدت (`inferred`: "Universal/Unified Payment Rail") |
| `globalorder`، `remittances`، `split`، `paymentkey`، `productinfra`، `integrity`، `dcp`، `phoenix` | مختلطة | موجودة كحزم؛ `integrity` تحمل ورقة سفلية لـ "احتكاك" الدفع (واجهة مخاطر/خطوة تحقق إضافية)، لم تُحل أي ملفات تحت أعلى مستويين من الدليل لـ `dcp` و `phoenix` في هذا التمرير (`unknown`) |

النقل العابر للمسارات عبر GraphQL مُغلَّف بواسطة `PaymentsMexGraphQlClient$ApiEventCallBuilder` (`com.whatsapp.payments.indiaupi.common.graphql`، وعلى الرغم من اسم الحزمة فهو غلاف استدعاء MEX مشترك، found) — يُزيّن كل استدعاء MEX للدفع بنداءات بدء/نجاح/فشل لتسجيل QPL/الأحداث (`FDA.BYz`) قبل التفويض إلى طبقة النقل الأساسية `InterfaceC17070jD`. هذا هو أقرب تطابق في هذا البناء لـ "مكتبة دفع مشتركة" على مستوى **العميل**: فئة غلاف استدعاء مُعتَّمة واحدة، تُعاد استخدامها من قبل مدراء GraphQL لـ UPI الهند (`IndiaUpiChangeMpinGraphqlManager`، `IndiaUpiCheckBalanceGraphqlManager`، `IndiaUpiEnrollIncentiveGraphqlManager`، إلخ — found، نفس الحزمة).

بشكل منفصل، تشحن الهند مكتبة **من طرف ثالث** مضمَّنة تحت حزمة مملوكة لـ NPCI، `org.npci.upi.security.*` (لا `com.whatsapp.*`) — هذه هي "CL" ("Common Library") المشار إليها من أصول NPCI الخاصة بها (`.properties`) (`version.properties`، `validation.properties`، `cl-*.properties`) وهي مشمولة في القسم 6. مفردات أصول NPCI نفسها (`salt`، `payInfo`، `controls`، `configuration`، `trust`، `keyXmlPayload`، `keyCode`) تتطابق تمامًا مع سلاسل مفاتيح الحزمة (bundle-key) الحرفية الموجودة في تطبيقات `CLRemoteService.Acc`/`Acf` في هذا البناء (القسم 6) — تأكيد مباشر، في هذا البناء، لتحليل سابق يعتمد على الأصول فقط. التوسيع الحرفي "Common Library" ما يزال غير مذكور كسلسلة في أي مكان (`inferred`، ومؤكد الآن بأسماء فئات `CLRemoteService`/`CLResultReceiver`/`CLRemoteServiceImpl` نفسها، وهو دليل جديد في هذا التمرير).

---

## 4. ربط VPA / الحساب المصرفي وتأهيل UPI (خاص بالهند)

أسماء الأنشطة المستخرجة من `com.whatsapp.payments.indiaupi.*` (found، وجود الفئة والتسمية فقط — ترتيب التنقل الدقيق بينها `inferred` من التسمية ولم يُتعقَّب عبر رسوم بيانية للنوايا في هذا التمرير):

| الخطوة | النشاط/الجزء |
|---|---|
| الدخول / عروض القيمة | `IndiaUpiPaymentsValuePropsActivity`، `IndiaUpiPaymentsValuePropsBottomSheetActivity`، `IndiaUpiPaymentsTosActivity` |
| التحقق من بطاقة SIM | `IndiaUpiSimPickerDialogFragment`، `IndiaUpiSimVerificationActivity` |
| اختيار البنك | `IndiaUpiBankPickerActivity` (حزمة `onboarding`)، `IndiaUpiBankAccountPickerActivity` |
| التحقق من الهوية/البطاقة | `IndiaUpiDebitCardVerificationActivity`، `IndiaUpiAadhaarCardVerificationActivity`، `IndiaUpiDobPickerActivity` |
| ربط الجهاز | `IndiaUpiDeviceBindStepActivity` (انظر القسم 6 لتفاصيل التشفير وراء هذه الخطوة) |
| إعداد PIN | `IndiaUpiPinPrimerDialogFragment` / `...FullSheetActivity`، `IndiaUpiPinHandlerActivity`، `IndiaUpiPinSetUpCompletedActivity`، `IndiaUpiChangePinActivity`، `IndiaUpiForgotPinDialogFragment` |
| الإتمام | `IndiaUpiBankAccountAddedLandingActivity`، `IndiaUpiPaymentsAccountSetupActivity` |
| مُطابِق الرقم إلى VPA | `IndiaUpiMapperValuePropsActivity` → `IndiaUpiMapperLinkActivity` → `IndiaUpiMapperPendingActivity` → `IndiaUpiMapperConfirmationActivity`؛ `IndiaUpiCreateCustomNumberActivity` لرقم هاتف غير افتراضي |
| تحليل جهة اتصال VPA | `IndiaUpiVpaContactInfoActivity`، `IndiaUpiSendPaymentToVpaFragment` |

"Mapper" هو مصطلح NPCI الخاص بخدمة دليل رقم الهاتف↔VPA؛ أنشطة `mapper.register.*` الأربعة تنفّذ تدفّق التسجيل الفرعي المحدد هذا (found: مسار الحزمة `indiaupi.p148ui.mapper.register`).

عمليات GraphQL المتعلقة بالربط بمتغيرات مؤكدة من موقع الاستدعاء (found، من `com.whatsapp.payments.indiaupi.common.graphql.*` وفئات `X/*` ذات الصلة؛ انظر القسم 9 للكتالوج الكامل):

| العملية | doc_id | المتغيرات (found) |
|---|---|---|
| `GetUpiBankList` | `27764018976534565` | `account_type`، `provider_type`، `request` |
| `GetUpiAccounts` | `25691302307224710` | `bank_code`، `device_id`، `provider_type`، `account_type` |
| `GetUpiToken` | `25639185495767704` | `challenge`، `device_id`، `token_type`، `provider_type` |
| `GenCreatePaymentKey` | `24662763616751127` | `add_bank`، `account_holder_name`، `display_name`، `payment_method_type`، `payment_account`، … (مجموعة فائقة من الضجيج، المُستدعي مشترك بين عدة عمليات — انظر تحفظ القسم 9) |
| `SetUpiChangeMpin` | `27149786891388216` | `credential_fbid`، `device_id`، `new_mpin`، `old_mpin`، `seq_no`، `upi_bank_info`، `vpa` |

---

## 5. إعداد/تأهيل الدفع (عام، عابر للمسارات)

تنفّذ حزمة `upr` غلاف تأهيل غير مرتبط بمسار محدد: `UprOnboardingActivity` → `UprOnboardingFragment` → `UprAccountTypePickerBottomSheet` → `AddPaymentMethodFragment` / `UprInstitutionPickerBottomSheet` (found، أسماء الفئات فقط؛ ترتيب التدفق `inferred`). إدارة الحساب بعد الإعداد تمر عبر `UprAccountManagementActivity`/`UprAccountManagementListFragment`، ومحفز الدفع داخل المحادثة يظهر عبر `UprPaymentOptionsBottomSheet`/`UprPaymentAccountDetailBottomSheet` (حزمة "bubble" — ورقة خيارات الدفع العائمة التي تُفتح من محادثة).

تكوين الخادم لهذا الغلاف يُجلب عبر `GenUprPaymentConfig` (doc_id `26905963415743456`) و `GenUprPaymentConfigForViewer` (doc_id `37307071662269517`) — found في كتالوج doc_id، لم تُؤكد من موقع استدعاء مستقل في هذا التمرير (متغيرات `unknown`).

---

## 6. مكتبة NPCI "Common Library" (CL): بيانات الاعتماد وPIN وربط الجهاز (خاص بالهند/UPI)

### 6.1 البنية (found)

يُفوَّض إدخال PIN ومعالجة بيانات الاعتماد المصرفية في UPI الهند إلى خدمة AIDL مضمَّنة مملوكة لـ NPCI، منفصلة تمامًا عن كود WhatsApp الخاص (`com.whatsapp.*`):

```
org.npci.upi.security.services.CLRemoteService      <- AIDL interface
org.npci.upi.security.services.CLResultReceiver     <- AIDL callback interface
org.npci.upi.security.pinactivitycomponent.CLRemoteServiceImpl  <- Android Service, binds the AIDL
org.npci.upi.security.pinactivitycomponent.BinderC48420LDc      <- Binder implementation of CLRemoteService
org.npci.upi.security.pinactivitycomponent.GetCredential        <- PIN-entry Activity launched by the binder
org.npci.upi.security.pinactivitycomponent.Keypad               <- on-screen keypad widget
```

طرق `CLRemoteService` (found، توقيعات الواجهة): `AQR(otpResultJson)`، `AZO(mode, nonce)` (تحدّي/استجابة ربط الجهاز، القسم 6.2)، `Acc(...)`/`Acf(...)` (تشغيل نشاط PIN بحزمة بيانات اعتماد)، `BBj(...)` (قراءة الرصيد)، `BVz/CRh/CRi(...)` (التحقق من شهادة الجهاز/الحالة)، `BW1()` (فحص سلامة الجهاز).

### 6.2 ربط الجهاز وتبادل بيانات الاعتماد (found)

`BinderC48420LDc.AZO(mode, nonce)`:
- الوضع "الابتدائي": يبني `deviceId|randomHex|nonce`، يُشفّر بـ RSA مقابل شهادة NPCI المضمَّنة (`MYU.A00`)، يُرمّز base64، ويُعيد `"2.3-v1.8|" + ciphertext`. البادئة `2.3-v1.8` هي وسم إصدار بروتوكول CL ثابت (سلسلة حرفية found).
- الوضع اللاحق: يستخرج مفتاح AES من سجل بيانات الاعتماد المخزَّن، يُشفّر الثلاثية نفسها `deviceId|randomHex|nonce` بـ AES/GCM باستخدام IV عشوائي جديد، ويُعيد `ciphertext|iv` تحت نفس بادئة الإصدار.

تبني `BinderC48420LDc.Acc`/`Acf` كائن `Bundle` بمفاتيح `keyCode`، `keyXmlPayload`، `controls`، `configuration`، `salt`، `payInfo`، `trust`، `languagePref` وتشغّل نشاط `GetCredential` به (found، مفاتيح سلسلة حرفية) — هذه هي المفردات الدقيقة التي استنتج تحليل سابق يعتمد على الأصول فقط (`version.properties`/`validation.properties`) أن مخطط "CL" سيستخدمها (`salt`، `payInfo`)؛ يؤكد كود هذا البناء أنها مفاتيح حزمة حقيقية في وقت التشغيل، لا مجرد عناصر نائبة في ملف أصول.

`C51962N8y` (مساعد تشفير يُستخدم في كل مكان في الـ binder):
- `A00`: يُولِّد **زوج مفاتيح RSA-2048 داخل Android KeyStore**، `CN=NPCI_CERT`، SHA-512/PSS، يتطلب عتادًا آمنًا (`isInsideSecureHardware()`، يرمي استثناءً خلاف ذلك) ومصادقة مستخدم (حسب إصدار SDK) ضمن نافذة صلاحية قصيرة — هذا هو مفتاح ربط الجهاز.
- `A03`/`A04`: AES/GCM-NoPadding، وسم 128 بت، مفتاح وIV مُقدَّمان صريحًا من المُستدعي — تشفير/فك تشفير على مستوى الجلسة.
- `A02`: خلاصة SHA-256 (تجزئة التحدي).
- `A01`: يفك تشفير سلسلة بشكل `ciphertext|iv` باستخدام مفتاح AES مخزَّن — يتوافق مع تنسيق خروج `AZO` أعلاه.

تُشغّل `BinderC48420LDc.BW1()` فحص جذر/تلاعب (علامات البناء، مسارات ثنائي `su` الشائعة، فحص `which su`) **و** تتحقق من أن مفتاح RSA الذي تم توليده للتو مدعوم بـ StrongBox/TEE؛ فشل الفحص يجعل `BW1()` تُعيد `false`، وهذا يُحظِّر مسار إصدار بيانات الاعتماد في المرحلة الأعلى (found: قيمة بوليانية مُعادة تُستهلك في مسارات منطق `CRh`/`CRi`، لم تُتعقب بشكل مستقل حتى رسالة في الواجهة).

### 6.3 ما يعنيه هذا لمحتوى الرسالة

MPIN في UPI نفسه لا يظهر مطلقًا في رسالة محادثة أو في حقول البروتو في القسم 2 من هذا التقرير — يُعالَج بالكامل داخل نشاط `GetCredential` ويُتبادل مع البنك المُصدِر/محوّل NPCI عبر طبقة RSA/AES أعلاه، منتجًا *كتلة بيانات اعتماد* غامضة هي ما يصل في النهاية إلى متغيرات GraphQL مثل `new_mpin`/`old_mpin`/`mpin` في `SetUpiChangeMpin`/`CheckUpiBalance` (القسم 9). كون السلسلة التي يحملها متغير GraphQL فعليًا مشفرة مسبقًا من قِبل NPCI (بدلًا من كونها نصًا واضحًا من جهة العميل محمية فقط بـ TLS) هو أمر **مستنتج** من غرض تدفق CL الذي يسبق الاستدعاء، لا مؤكد بشكل مستقل من قراءة المحتوى الثنائي لموقع استدعاء GraphQL.

---

## 7. طبقات التشفير: تشفير المحادثة من طرف إلى طرف مقابل كتلة بيانات اعتماد NPCI

تتضمن عملية الدفع طبقتي تشفير مستقلتين، ويجب ألا تُخلطا ببعضهما (القسم 13):

| الطبقة | ما تحميه | الآلية | الدليل |
|---|---|---|---|
| تشفير المحادثة من طرف إلى طرف | بروتو `Message` بالكامل، بما في ذلك كل حقل في القسم 2 (المبلغ، الملاحظة، VPA في `payeeVpa`، JIDs، مراجع `MessageKey`) | تشفير جلسة WhatsApp القياسي القائم على بروتوكول Signal/Noise — خارج نطاق هذا التقرير، انظر تقارير RE أخرى لهذه الطبقة | لم يُستخرج هنا مجددًا |
| كتلة بيانات اعتماد/ربط جهاز NPCI | MPIN، تحدّي/استجابة ربط الجهاز، حمولات فحص المخاطر المتبادلة مع البنك المُصدِر عبر NPCI | RSA-2048 (KeyStore، مرتبط بـ TEE، `CN=NPCI_CERT`) لربط الجهاز؛ AES/GCM-128 مع IV صريح لبيانات الجلسة؛ SHA-256 لتجزئة التحدي | القسم 6.2، found |

الطبقة الثانية **خاصة بالهند/UPI** وتعمل أسفل/قبل استدعاء GraphQL، وليست مطلقًا داخل بروتو `Message` للمحادثة. لم يُعثر على طبقة AES/RSA خاصة بالدفع لـ Pix البرازيل أو المكسيك في هذا التمرير (`unknown` — لم تُستكشف).

---

## 8. مزامنة حالة المعاملة

### 8.1 الكائن المحلي ومزامنة السجل (found)

`F7F` هو كائن معاملة الدفع المحلي/في الذاكرة (يُجلب عبر `D8X.A00(c13g)` من سجل الرسالة العام `C13G`). تحوّله `EKY.A00` إلى `PaymentInfo` على مستوى السلك (`DTS`، القسم 2.8) المرفقة بـ `WebMessageInfo.paymentInfo_`/`quotedPaymentInfo_` لتصدير مزامنة السجل/الجهاز المرافق.

### 8.2 تحديثات الحالة المدفوعة من الخادم (found، `C24410wL` "PaymentsMessageHandler")

قناة الدفع المواجهة للعميل هي stanza من نوع `<notification>` بسمة `type` يُوزّعها `PaymentsMessageHandler.A0A`. قيم `type` المرصودة ومعالجتها:

| `type` | المعالجة |
|---|---|
| `pay` (مع `hash`) | تُفك ترميز hash بـ base64، تُدرج في قائمة انتظار كتحديث USync جانبي (`EnumC21760rz.A0Q`، مجموعة بروتوكول `C21820s6.A0N`) — يُعاد استخدام آلية USync الموثَّقة في `WA_USYNC.md` بدلًا من حمل الحالة نفسها |
| `transaction` | تحلّل المعاملة بواسطة `C24880x6.A07`، تُسجّل `onPaymentTransactionStatusUpdate`، تُحدّث `F7F` المحلية، تُظهر نص خطأ معاملة لأي واجهة متصلة (`InterfaceC35566Fb1.BIp`)، و(مقيَّدة بالأعلام **1746** + **5049**) يمكن أن تبني بطاقة "عنصر مخصص" لملخص الطلب لحافز تعليمي بعد الدفع |
| `upi` | `consumer_status{value,dhash}` → `onPaymentConsumerStatusUpdate` (إشعار أهلية مستهلك خاص بالهند، مستقل عن حالة المعاملة) |
| `fbpay` | إشعار أهلية Meta Pay القديم، نفس مسار المعالج كـ `upi` بمفتاح خريطة عروض مختلف |
| `account-recovery` | `service=UPI` أو `service=BR`؛ يُشغّل تدفّقات استعادة الحساب للهند/البرازيل، مقيَّدة بالأعلام **1644**/**2000** |
| `alert`، `step_up`، `merchant_status`، `merchant-update`، `account`، `kyc-state`، `invite`، `alias`، `age_verification_update`، `document_verification_status` | إشعارات واجهة متنوعة/تحديثات امتثال، ليست حالة معاملة |

### 8.3 دفاتر المزامنة (found، سلاسل مفاتيح تفضيلات)

`payments_all_transactions_last_sync_time`، `payments_block_list_last_sync_time`، `payments_error_map_last_sync_time_millis` — توجد مزامنات دورية للقائمة الكاملة وخريطة الأخطاء (فئات المستهلك لم تُتعقب بالكامل في هذا التمرير؛ `unknown` التكرار).

---

## 9. عمليات GraphQL / MEX للدفع

### 9.1 نقلان، مخططان (found)

| المخطط | النقل | العدد (في هذا البناء) |
|---|---|---|
| `whatsapp` (كتالوج `www`) | POST عبر GraphQL بمستند-معرَّف (doc_id)، آلية النقل نفسها `inferred` (لم تُتعقب إلى موقع استدعاء HTTP/IQ في هذا التمرير) | 81 عملية موسومة بالدفع |
| `whatsapp_mex` (كتالوج `mex`) | `w:mex` IQ عبر اتصال stanza الموجود (`xmlns="w:mex"`) | عملية واحدة موسومة بالدفع: `PaymentsIsAccountRecoverable` (doc_id `27351347491148282`) |

المصدر: `assets/whatsapp-android-www_client_persist_ids.json` و `assets/whatsapp-android-mex_client_persist_ids.json`، كلاهما أصول تصريحية من الطرف الأول تُقرأ وقت التشغيل (found، أقوى مستوى دون التقاط فعلي للشبكة — قيم doc_id نفسها ليست "tested"، مجرد مؤكدة الوجود في الأصول المشحونة).

### 9.2 عمليات تمثيلية بمتغيرات مؤكدة من موقع الاستدعاء (found)

| العملية | doc_id | النوع | المتغيرات |
|---|---|---|---|
| `GetUpiAccounts` | `25691302307224710` | Query | `bank_code`، `device_id`، `provider_type`، `account_type` |
| `CheckUpiBalance` | `37205951525662520` | Query | `credential_fbid`، `device_id`، `mpin`، `seq_no`، `upi_bank_info`، `vpa`، `cl_version`، `device_ssid`، `request` |
| `SetUpiChangeMpin` | `27149786891388216` | Mutation | `credential_fbid`، `device_id`، `new_mpin`، `old_mpin`، `seq_no`، `upi_bank_info`، `vpa` |
| `GetUpiBankList` | `27764018976534565` | Query | `account_type`، `provider_type`، `request` |
| `GetUpiToken` | `25639185495767704` | Query | `challenge`، `device_id`، `token_type`، `provider_type` |
| `UpiCreateMandate` / `UpiAcceptMandate` | `26775212245448044` / `26786867597629452` | Mutation | مُستدعٍ مشترك (`C42562IuV`): `frequency_rule`، `mandate_no`، `purpose_code`، `recurrence_day`، `recurring_rule`، `ref_id`، `device_id`، `top_up_amount`، `provider_type`، `upi_banks`، `is_revocable`، … |
| `CreateEnrollment` | `34570903025891763` | Mutation | `participant_id`، `device_id` |
| `GenRaisePaymentComplaint` | `27569318002686860` | Query | `complaint_type`، `reason`، `transaction_ref_id`، `user_description` |
| `PaymentsIsAccountRecoverable` (MEX) | `27351347491148282` | Query | لم يُعثر على شيء (يُحتمل `{}`) |

وجود متغير `mpin` في `CheckUpiBalance`، مقروءًا بجانب `cl_version`، يتوافق مع القسم 6.3: اسم المتغير بمفرده لا يثبت أن المحتوى مُشفَّر مسبقًا، لكنه ينتقل بجانب سلسلة إصدار بروتوكول CL صريحة، وهذا لا يكون منطقيًا إلا إذا كانت القيمة نشأت من تبادل CL.

**تحفّظ (found كقيد، لا كنتيجة عن WhatsApp):** تتحلّل `GenCreatePaymentKey`، `RevokeEnrollment`، و`BrSaveCPF` جميعًا إلى *نفس* فئات المُستدعي المشتركة (`C42325Iq9`/`C42327IqB`، `RunnableC42211IoJ`) في كتالوج المصدر، والذي يُعيد كل سلسلة حرفية قريبة من ذلك المُستدعي كـ "متغيرات" للعمليات الثلاث — هذا يُفرط في التجميع (مثلًا حقول خاصة بـ Pix مثل `pix_key` تظهر تحت عملية مُسمَّاة بـ UPI). تعامل مع القوائم الطويلة للمتغيرات لتلك العمليات الثلاث المحددة كمجموعة فائقة من الضجيج، لا كمخطط مؤكد لكل عملية.

العمليات المتبقية في الكتالوج المكوَّن من 81 إدخالًا (القائمة الكاملة: `UpiPauseMandate`، `UpiResumeMandate`، `UpiRevokeMandate`، `UpiRejectMandate`، `UpiExecuteMandate`، `GetUpiLiteDetails`، `GetUpiP2mConfig`، `GetUpiPurposeLimitingKey`، `GetUpiSmsContentAndVmn`، `PaymentReminderCreate/Get/Cancel/Stop`، `GetBillReceipt`، `GetBillerPlans`، Pix البرازيل (`GetPixInfo`، `GetPixBankList`، `GetMerchantPixInfo`، `CompletePixTransaction`، `GenPayWithPixPrecheck`)، البيومتري/مفتاح المرور (`Br*Passkey*`، `BrAuthorizeBiometricPayment`)، وعمليات `Wamo*` للاشتراك/الترويج) مُفهرَسة بـ doc_ids الخاصة بها ولكن لم تُعاد التحقق منها فرديًا مقابل موقع استدعاء في هذا التمرير — تعامل مع وجودها كـ `found` (هي إدخالات حرفية في أصل 2.26.41.6) وشكل طلبها الدقيق كـ `unknown` إلا إذا كانت مذكورة أعلاه.

---

## 10. قواعد القراءة التلقائية لرمز OTP الخاصة بـ NPCI (خاص بالهند/UPI)

`assets/npci/npci_otp_rules.json` (found، 5 قواعد) يستهلكه `org.npci.upi.security.pinactivitycomponent.C0315u` لاستخراج رمز OTP من 6 أرقام تلقائيًا من رسالة SMS واردة من البنك/NPCI خلال تدفّق UPI، لمجرد راحة الكتابة فقط — لا يُولِّد الرمز ولا يُصادق عليه ولا يُرسله. كل القواعد الخمس تشترك `sender: ["[a-zA-Z]+"]` (رمز قصير أبجدي) و `otp: "\d{6}"`؛ فقط عبارة التحفيز تختلف (`"is your OTP"`، `"OTP is"`، `"one time password is"`، `"is your one time password"`، `".*OTP for Aadhaar.*"`). يمكن للمُستدعي تجاوز تعبير عدد أرقام OTP وقت التشغيل (`\d{` + `i` + `}`) عند تمرير طول غير صفري. نص يحتوي على `"Aadhaar"`/`"AADHAAR"` يُخزَّن مؤقتًا تحت مفتاح SharedPreferences `otp_type_aadhaar`، وبخلاف ذلك `otp_type_bank`.

هذا الأصل وفئة المستهلك لم يتغيرا من الناحية النوعية عن تحليل سابق لإصدار `2.26.34.4`؛ لم يُعاد الفرق بايتًا ببايت مقابل 2.26.41.6 في هذا التمرير (`inferred` استمرارية، لم تُعاد التحقق).

---

## 11. أعلام الميزات

مُعرِّفات AB-prop كما قُرئت مباشرة في `PaymentsMessageHandler` (`C24410wL`، مواقع استدعاء found) إلا إذا ذُكر خلاف ذلك. لم يُعثر على أي مُعرِّف علم رقمي يُقيِّد حقول البروتو في القسم 2 نفسها (تلك غير مشروطة على السلك)؛ كل الأعلام التي وُجدت في هذا التمرير تُقيِّد *معالجة* دفعات الخادم أو إشعارات الواجهة.

| العلم | يتحكم في |
|---|---|
| **1458** | يزيل لقب UPI محفوظًا محليًا بمجرد أن يُعلن الخادم أنه `deregistered` |
| **1644** | أهلية استعادة حساب UPI (`payments-enabled:account-recovery-enabled`) |
| **2000** | أهلية استعادة حساب Pix البرازيل (بوابة معادلة لـ `service=BR`) |
| **1746** + **5049** (كلاهما مطلوب) | بطاقة "عنصر مخصص"/ملخص طلب تعليمية تُعرض بعد إتمام دفعة (حافز تعليمي BIP) |
| **12214** | مسار إنشاء مستخدم FB خلال استعادة حساب UPI (مقابل استدعاء الاستعادة المباشر) |
| **423** | تتبّع دعوة الدفعات المُستخدمة، المسار الأقدم |
| **544** | تتبّع دعوة الدفعات المُستخدمة، مسار إضافي (يُفحص مع 423 عبر OR) |
| **20869** | فحص قائمة السماح لـ PSP خلال معالجة إشعار استعادة الحساب؛ تفضيل سلسلة مرافق `32353` (قائمة PSP مُفعَّلة مفصولة بفواصل، تُقرأ عبر AB prop بقيمة سلسلة، لا علم رقمي) |

لم يُعثر على أي معرّف علم ميزة يُقيِّد تسلسل نشاط تأهيل UPI الهند (القسم 4) أو مسار ربط جهاز NPCI CL (القسم 6) على وجه التحديد في هذا التمرير — `unknown`، لم يُتعقب أبعد من فئة المعالج أعلاه.

---

## 12. رموز الرفض/الخطأ

### 12.1 الرفض/الإلغاء داخل البروتوكول (found)

كما تقرَّر في القسم 2.4، `declinePaymentRequestMessage`/`cancelPaymentRequestMessage` تحمل **فقط** مرجع `MessageKey` إلى الطلب الأصلي — بدون تعداد سبب، بدون حقل نص حر. العميل الذي يُظهر "مرفوض: رصيد غير كافٍ" أو ما شابه يفعل ذلك من حالة **محلية** (نسخة واجهة المرسل نفسه، أو حالة `transaction`/`PaymentInfo` مرتبطة لاحقًا، القسم 8)، لا من أي شيء تنقله رسالة الرفض/الإلغاء نفسها.

### 12.2 حقول حالة PaymentInfo (found وجودها، التعيين unknown)

`DTS.status_` (الحقل 4) و `DTS.txnStatus_` (الحقل 10) حقلان مستقلان من نوع enum (القسم 2.8). لم يمكن استرجاع تعيين الرقم الترتيبي إلى التسمية من الـ javalite bytecode فقط (أسماء ثوابت التعداد ممحوّة بتعتيم فئات `Internal.EnumVerifier` في هذا البناء) — `unknown`. `futureproofed` (الحقل 8، bool) هو منفذ احترازي متعمَّد يُضبط عندما لا يملك كائن المرسل المحلي مبلغًا/عملة قابلة للحل، مما يسمح لمستقبل على عميل أحدث بعرض حالة لم يكن يستطيع تحليلها بخلاف ذلك.

### 12.3 خريطة الأخطاء المدفوعة من الخادم (found مفاتيح التفضيلات، المستهلك لم يُتعقب بالكامل)

مفاتيح التفضيلات `payments_error_code`، `payments_error_text`، `payments_error_title`، `payments_error_map_tag`، `payments_error_map_last_sync_time_millis` تشير إلى أن رموز الخطأ تُحل مقابل **خريطة مُزامنة من الخادم** (رمز → عنوان/نص)، وليست تعدادًا أو جدول سلاسل ثابتًا من جهة العميل. هذا يعني أن نص الرفض/الخطأ المعروض للمستخدم يمكن أن يتغير بمرور الوقت/حسب المنطقة دون تحديث التطبيق. الفئة التي تنفّذ هذه المزامنة لم تُحدَّد في هذا التمرير (`unknown`).

### 12.4 أعطال طبقة NPCI CL (found، بدون كود مُهيكل)

`BinderC48420LDc.BW1()` (فحص سلامة الجهاز)، `CRH`/`CRh`/`CRi` (التحقق من شهادة/حالة الجهاز) تفشل جميعها **بصمت** — تُعيد `false`/ترمي استثناءً، بدون رمز خطأ مُظهَر عبر حدود AIDL باستثناء القيمة البوليانية. أي رسالة مرئية للمستخدم بشأن فشل طبقة CL تُبنى بالكامل من جانب WhatsApp من نتيجة القيمة البوليانية، وليس من رمز مُقدَّم من NPCI (`inferred`، متوافق مع شكل واجهة AIDL في القسم 6.1 التي لا تملك طرقًا تُعيد رمز خطأ).

---

## 13. خاص بالهند/UPI مقابل عام — التقسيم الصريح

| النتيجة | النطاق |
|---|---|
| حقول البروتو لـ `sendPaymentMessage`/`requestPaymentMessage`/`declinePaymentRequestMessage`/`cancelPaymentRequestMessage`/تقسيم الدفعة/`PaymentInviteMessage`/`PaymentReminderMessage` (القسم 2) | **عام** — نفس حقول بروتو `Message` بصرف النظر عن المسار؛ `payeeVpa` (القسم 2.6) هو الحقل الوحيد المسمى بنكهة UPI لكن الحقل نفسه موجود بلا شرط في المخطط |
| كائن حالة المعاملة `PaymentInfo` (`DTS`) (القسم 2.8، 8) | بنية **عامة**؛ `useNoviFiatFormat` ورموز الخدمة القديمة `FBPAY`/`NOVI`/`PIX`/`UPI` تُظهر أن نفس مسار الكائن/الإشعار مشترك بين كل المسارات |
| حزم المسارات `indiaupi`، `brazilpay`، `mexico`، `indonesia`، `upr` (القسم 3) | مُقسَّمة صريحًا بالحزمة؛ `upr`/`common` غير مرتبطتين بمسار محدد، والباقي خاص بدولة واحدة |
| ربط VPA، تدفّق mapper UPI، أنشطة التأهيل (القسم 4) | **خاص بالهند/UPI فقط** |
| مكتبة بيانات اعتماد/ربط جهاز NPCI "CL"، تشفير RSA/AES، القراءة التلقائية لـ OTP (الأقسام 6، 7، 10) | **خاص بالهند/UPI فقط** — هذه الطبقة بالكامل غائبة عن Pix/المكسيك/إندونيسيا في الكود المُستكشَف |
| كتالوج doc_id لـ GraphQL (القسم 9) | مختلط — الكتالوج نفسه يمتد عبر UPI وPix والبيومتري/مفتاح المرور (البرازيل) والعمليات غير المرتبطة بمسار محدد (`Wamo*`، `Gen*`) تحت مخطط واحد؛ نطاق كل عملية يتبع اسمها/بادئتها (`Br*` = البرازيل، `Upi*`/`GetUpi*`/`SetUpi*` = الهند) |
| أنواع إشعار `PaymentsMessageHandler` (القسم 8.2) | مختلط — أنواع مثل `pay`/`transaction`/`alert`/`step_up`/`account` عامة؛ نوع `upi` وفروع `service=UPI` خاصة بالهند، وفروع `service=BR` خاصة بالبرازيل |

---

## 14. ملاحظة Baileys

يمكن لعملاء على طراز Baileys بناء وتحليل أنواع رسائل القسم 2 (هي حقول protobuf عادية على `Message` القياسية)، ويمكنهم مبدئيًا استدعاء doc_ids لـ GraphQL لـ `whatsapp`/`whatsapp_mex` بمتغيرات مبنية يدويًا. **لا يمكنهم** إتمام دفعة UPI بشكل معنوي: تبادل MPIN/ربط الجهاز في القسم 6 يعمل عبر مكوّن Android أصلي مضمَّن ومُوقَّع من NPCI، مرتبط بعلاقة ثقة حقيقية مع البنك المُصدِر/محور NPCI (مفتاح RSA مدعوم بـ TEE، `CN=NPCI_CERT`) لا يوجد له نظير خارج التطبيق الرسمي. لذا فإن `sendPaymentMessage` مرسلة من Baileys هي رسالة صحيحة بروتوكوليًا لكنها غير فعّالة وظيفيًا إلا إذا اقترنت بمعاملة تمت المصادقة عليها فعليًا عبر تدفّق NPCI الحقيقي.

---

## 15. حالات الخطأ / المزالق

| العارض | السبب | الحل / الملاحظة |
|---|---|---|
| رسالة الرفض/الإلغاء بلا سبب مرئي على السلك | تصميم البروتوكول (القسم 2.4) — لا يوجد سوى مرجع `MessageKey` | لا تتوقع رمز سبب من الرسالة نفسها؛ اربطه بإشعار `transaction` لاحق أو حالة محلية |
| عملية بيانات اعتماد مقيَّدة بـ `BW1()` تفشل بلا نص خطأ | الجهاز يفتقر إلى StrongBox/TEE، أو هو مُجذَّر (rooted) | تُظهَر فقط كفشل بوليانية من جانب WhatsApp؛ لا يمكن تمييزها عن أعطال CL أخرى بدون تسجيل إضافي |
| متغيرات GraphQL `mpin`/`new_mpin`/`old_mpin` تبدو كنص واضح في تفريغ موقع استدعاء مفكوك | تُنتَج من تبادل CL (القسم 6.3)، ولا تُكتب مباشرة في استدعاء GraphQL | لا تفترض نقل PIN نصًا واضحًا دون تتبع البايتات الفعلية وقت التشغيل — هذا التقرير لا يدّعي أنه فعل ذلك |
| `GenCreatePaymentKey`/`RevokeEnrollment`/`BrSaveCPF` تُظهر قوائم متغيرات ضخمة بنكهة Pix | إفراط تجميع فئة مُستدعٍ مشترك في استخراج كتالوج doc_id (القسم 9.2) | تعامل معها كضجيج، تحقق لكل حقل قبل الاعتماد عليها |
| تعذّر تسمية قيم تعداد `txnStatus`/`status` | `EnumVerifier` المُعتَّمة تمحو أسماء الثوابت | يتطلب ربط سلاسل وقت التشغيل (سلاسل موارد الواجهة المُطابَقة للأرقام الترتيبية)، لم يُنفَّذ في هذا التمرير |

---

## 16. تمييزات أساسية

| لا تخلط بين | التفصيل |
|---|---|
| تشفير المحادثة من طرف إلى طرف مقابل كتلة بيانات اعتماد NPCI (القسم 7) | طبقتا تشفير مستقلتان؛ الثانية خاصة بالهند/UPI فقط وتقع بالكامل خارج بروتو `Message` |
| `DTS` PaymentInfo مقابل أنواع رسائل الدفع الأربعة في المحادثة | `DTS` كائن مزامنة سجل/حالة (`WebMessageInfo.paymentInfo_`)، وليست أبدًا رسالة محادثة قابلة للإرسال بمفردها |
| `status` مقابل `txnStatus` على `DTS` | تعدادان مستقلان، تفصيل مختلف، كلاهما غامض على مستوى الرقم الترتيبي في هذا البناء |
| مخطط `www`/`whatsapp` مقابل مخطط `mex`/`whatsapp_mex` لـ doc_ids | نقل مختلف (POST عبر GraphQL بمستند-معرَّف مقابل `w:mex` IQ)؛ معظم عمليات الدفع على جانب `www`/`whatsapp` في هذا البناء |
| تأهيل "UPR" غير مرتبط بمسار محدد مقابل تأهيل UPI الهند | UPR (`com.whatsapp.payments.upr`) غلاف عام أحدث؛ أنشطة تأهيل `indiaupi` الخاصة بالهند (القسم 4) تدفّق منفصل، أقدم، وأكبر بكثير، ما يزال موجودًا جنبًا إلى جنب في 2.26.41.6 |
| مكتبة NPCI "Common Library" (`org.npci.upi.*`) مقابل كود WhatsApp الخاص (`com.whatsapp.payments.*`) | الأولى مكوّن من طرف ثالث مضمَّن بواجهة AIDL خاصة به؛ كود WhatsApp فقط يُشغّله ويقرأ سلسلة/حزمة غامضة مُعادة |

---

## 17. التدفّق الكامل (UPI الهند، حالة إرسال الأموال)

```
[Payer chat]                 [WhatsApp client]                    [NPCI CL component]            [NPCI / Issuer bank]
     │ tap "Pay"                    │                                      │                             │
     ▼                              ▼                                      │                             │
 open IndiaUpiSendPaymentActivity → IndiaUpiSendPaymentToVpaFragment       │                             │
     │                              │ amount/VPA/note entered              │                             │
     │                              ▼                                      │                             │
     │                     CLRemoteService.Acc(keyCode, keyXmlPayload,     │                             │
     │                       controls, configuration, salt, payInfo, …) ──►│                             │
     │                              │                                GetCredential activity (PIN pad)    │
     │                              │                                      │ user enters MPIN            │
     │                              │                             AZO(): RSA/AES challenge-response ────►│
     │                              │                                      │◄──── signed/verified ────── │
     │                              │◄──── opaque credential blob ─────────│                             │
     │                              │                                      │                             │
     │                     build RequestPaymentMessage / SendPaymentMessage (section 2)                  │
     │                              │ amount, note, requestMessageKey, background                        │
     │                              ▼                                                                     │
     │                     chat E2E encrypt, send as normal <message>                                    │
     │                              │                                                                     │
     │                     CheckUpiBalance / SetUpiChangeMpin / mandate GraphQL op ─────────────────────► │
     │                              │          (credential_fbid, device_id, mpin blob, vpa, seq_no)       │
     │                              │◄──────────────── result / error (section 12.3 error map) ────────── │
     ▼                              ▼                                                                     │
[Payee chat]            server pushes <notification type="transaction"> ──────────────────────────────── │
     │                              │  PaymentsMessageHandler.A0A updates local F7F,                      │
     │                              │  EKY.A00 builds PaymentInfo (DTS) for history sync                  │
     ▼                              ▼
 status shown in chat        transaction row updated, payments_all_transactions_last_sync_time bumped
```

---

## 18. المجهولات

| الموضوع | السبب |
|---|---|
| أرقام حقول `Message` على المستوى الأعلى لـ `splitPaymentMessage`، `splitPaymentUpdateMessage`، `paymentReminderMessage` | فك ترميز سلسلة المعلومات لم يُستكمل بعيدًا في هذا التمرير؛ حقول الرسالة الفرعية الخاصة (القسم 2.5/2.6) غير متأثرة |
| تعيين تسمية تعداد `DTS.status_`/`txnStatus_` | `EnumVerifier` مُعتَّمة، أسماء الثوابت ممحوّة |
| آلية النقل الدقيقة لاستدعاءات GraphQL بمستند-معرَّف من مخطط `whatsapp` (`www`) | لم تُتعقب إلى موقع استدعاء HTTP/IQ في هذا التمرير؛ موسومة `inferred` في كل مكان |
| فئة(فئات) المستهلك لخريطة الأخطاء المُزامنة من الخادم `payments_error_map_*` | مفاتيح التفضيلات وُجدت، فئة القراءة/الكتابة لم تُحدَّد |
| محتويات حزم `mexico`/`indonesia`/`dcp`/`phoenix` | وجود الحزمة مؤكد، المحتويات لم تُستكشف |
| هل متغيرات GraphQL `mpin`/`new_mpin`/`old_mpin` تحمل كتلة مُشفَّرة مسبقًا من NPCI أم أن حماية إضافية تُطبَّق فقط على مستوى TLS | مستنتج من غرض تدفّق CL، لم يُؤكد بفحص محتوى البايت الفعلي وقت التشغيل |
| معرّفات أعلام الميزات (إن وُجدت) التي تُقيِّد تسلسل تأهيل UPI الهند أو مسار ربط جهاز CL نفسه | لم يُعثر على شيء في الفئات المُستكشَفة |
| استمرارية `npci_otp_rules.json` وأصول `.properties` الخاصة بـ CL بايتًا ببايت بين `2.26.34.4` (تحليل سابق) و `2.26.41.6` | لم تُعاد المُفاضلة؛ أُعيد تأكيد الفئات المستهلكة ومفردات مفاتيح الحزمة وقت التشغيل بشكل مستقل في 2.26.41.6، لم تُفاضَل بايتات الأصل نفسها |
| سلوك الشبكة/المعاملة المباشر الفعلي | تحليل ساكن فقط، بدون التقاط شبكة، بدون تنفيذ معاملة مباشرة |
