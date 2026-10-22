<!-- src-sha1: b8a925dee480430088a421b7aba690bc2f641a5f -->
# WhatsApp أمان الحساب — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-22
**النطاق:** التحقق من رقم الهاتف لحساب موجود (HTTP التسجيل `/v2/*`)، وطرق العامل الثاني، ورمز PIN للتحقق بخطوتين والبريد الإلكتروني للاسترداد، وكلمة مرور الحساب (غلاف `#PWD_WA`، والاعتماد على المستخدم الأساسي canonical-user)، والشيفرة الأصلية OPAQUE / VOPRF وما تخدمه فعليًا، وتسجيل الدخول بمفتاح المرور passkey وإدارته، والأجهزة الموثوقة، واسترداد الحساب (تبادل nonce للمستخدم الأساسي)، وتسجيل الخروج الناعم / العودة إلى الدخول، وعمليات w:mex (doc_ids والمتغيرات وجذور الاستجابة)، وfeature flags، وملاحظات Baileys

---

## 1. ما هو (من الناحية التقنية)

"أمان الحساب" في عميل Android ليس نظامًا فرعيًا واحدًا. إنه خمس آليات مستقلة مبنية فوق مسار التسجيل برقم الهاتف. كل العبارات مصدرها التحليل الساكن لـ APK المفكوك؛ ولم يتم التقاط أي شيء على الشبكة. المستوى: **found** = قُرئ في الشيفرة أو الأصول، **inferred** = مستنتج من الشيفرة، **unknown** = غير محسوم. أسماء الفئات المبهمة (obfuscated) تتغير مع كل إصدار وقد أُعيد حلها في 2.26.41.6.

| الآلية | أين تُفرض | بيانات الاعتماد | الفئات الرئيسية في العميل (2.26.41.6) |
|-----------|---------------------|------------|-------------------------------|
| التحقق من الهاتف (OTP) | HTTP التسجيل، `/v2/exist` → `/v2/code` → `/v2/register` | SMS / صوت / flash / جهاز قديم / OTP بالبريد / silent auth | `K49` (`RegistrationHttpManager`)، `KotlinRegistrationBridge`، `AbstractC45307Jps` |
| العامل الثاني عند التسجيل | `/v2/register` بالسبب `security_code`، ثم `VerifyTwoFactorAuth` | PIN من 6 أرقام، كلمة مرور الحساب، OTP بالبريد | `VerifyTwoFactorAuth`، `EnumC43759JAu`، `HOZ` |
| التحقق بخطوتين (PIN + البريد) | IQ `urn:xmpp:whatsapp:account` `<2fa>` | PIN من 6 أرقام، بريد استرداد اختياري | `C1DP` (`TwoFactorAuthManager`)، `C1DT` (`TwoFactorXmppMethods`) |
| كلمة مرور الحساب | w:mex (`whatsapp-android-mex`، `whatsapp-android-www`) | 8-20 حرفًا، حرف + رقم | `PasswordRepository`، `PasswordServerApiImpl`، `CanonicalPasswordService` |
| مفتاح المرور (WebAuthn) | `/v2/passkey_auth` عند الدخول؛ IQ `passkey` أو w:mex للإدارة | passkey المنصة عبر Credential Manager | `PasskeyServerApiImpl`، `PasskeyCreateFlow`، `PasskeyVerifier`، `K15` |
| الجهاز الموثوق | w:mex | سجل على الخادم مفتاحه `ANDROID_ID` مُجزَّأ | `TrustedDevicesServerApiImpl`، `RegTrustedDeviceGraphQLHelper` |
| تسجيل الخروج الناعم / العودة إلى الدخول | w:mex | لا شيء (علم حالة) | `LogoutManager`، `LogoutPushManager` |
| استرداد الحساب | w:mex، مستخدم Meta الأساسي | غلاف RSA/AES لسر يولده العميل | `AccountRecoveryManager` |

نقطتان تحسمان التقرير كله:

- آلة حالة OPAQUE في `libwhatsapp.so` مرتبطة بكلمة مرور **النسخ الاحتياطي المشفر من طرف إلى طرف** (معالجات `encb/*`)، وليس بكلمة مرور الحساب (القسم 6).
- كلمة مرور الحساب في هذا الإصدار تُنشأ وتُغيَّر عبر `XfbWaCreatePasswordMutation` / `XfbWaChangePasswordMutation` بغلاف RSA/AES (`#PWD_WA:11`)، وفقط إذا كان التطبيق يحمل بيانات اعتماد المستخدم الأساسي لدى Meta (القسم 5).

---

## 2. وسائل النقل وفهرس العمليات

### 2.1 أربع وسائل نقل

| وسيلة النقل | الاستخدام | الدليل |
|-----------|----------|----------|
| HTTPS `/v2/<name>` (حزمة التسجيل) | التحقق من الهاتف، العامل الثاني عند الدخول، تأكيد passkey، تأكيد الجهاز | found: ثوابت المسارات في `AbstractC45307Jps` (القسم 3.1) |
| IQ `xmlns="urn:xmpp:whatsapp:account"` | ضبط PIN / البريد وفحصهما وجلبهما؛ OTP بريد الحساب؛ اسم المستخدم وغيره | found |
| IQ `xmlns="passkey"` (معرّفات smax 125 و126 و129) | بدء / إنهاء / مسح passkey القديمة | found، مقيّدة بالـ flags 10452 / 10453 / 10461 |
| IQ `xmlns="w:mex"` | كل عمليات GraphQL أدناه | found |

### 2.2 غلاف w:mex ومصدر doc_id

تُرسل المتغيرات بصيغة JSON. تقريبًا كل mutation يلف حقوله في كائن واحد: الدالة المساعدة `AbstractC197058a0.A17(obj, vars)` تخزّن الكائن تحت المفتاح `input` (found). الاستثناءات: mutation كلمة المرور من نوع `Xfb*` يضعان `encrypted_password` تحت `data` (found)؛ و`PasskeyDeleteMutation` يستخدم `input` أيضًا (عبر `c16770ig.A00(obj, "input")`).

قيم doc_id ليست ثوابت حرفية في الشيفرة. يرسل العميل اسم العملية مع اسم التهيئة (`whatsapp-android-mex`، `whatsapp-android-www`، `whatsapp-android-facebook-schema`)؛ ويُقرأ المعرّف الرقمي من `assets/whatsapp-android-{mex,www,facebook-schema}_client_persist_ids.json` (found). كل doc_id أدناه قُرئ من تلك الأصول في 2.26.41.6 وتم فحص اسم العملية مقابل موضع استدعاء. لا شيء منها `tested`.

### 2.3 فهرس العمليات (مواضع الاستدعاء موجودة)

المتغيرات داخل `input` ما لم يُذكر خلاف ذلك. "الجذر" هو اسم كائن الاستجابة الذي يقرؤه العميل.

| العملية | doc_id | التهيئة | المتغيرات | الجذر والحقول المقروءة |
|-----------|--------|--------|-----------|----------------------|
| `HasPasswordQuery` | `25379221318423478` | mex | لا شيء | `xwa2_has_password`: `has_password`, `upgrade_needed` |
| `DeletePasswordMutation` | `27247058691550586` | mex | لا شيء | `xwa2_delete_password`: `success`, `twofa_auto_disabled`؛ الخطأ 409 يعني "يتطلب بريدًا إلكترونيًا" |
| `GetTwofaQuery` | `27608881388708005` | mex | `device_id` | `xwa2_get_twofa`: `twofa_enabled`, `twofa_methods[]{method,value,state}`, `is_device_trusted`, `latitude`, `longitude` |
| `SetTwofaMutation` | `28092515560345874` | mex | `twofa_enabled` (bool)، `device_id` | `xwa2_set_twofa`: `success`, `twofa_already_enabled`, `is_device_trusted` |
| `WaPasswordEncryptionKeyQuery` | `27318258844468227` | www | لا شيء | `wa_password_encryption_key`: `public_key` (PEM)، `key_id` |
| `XfbWaCreatePasswordMutation` | `36595298760118580` | www | `data.encrypted_password` (ليس تحت `input`) | `xfb_wa_create_password` (حقول النجاح / الخطأ غير محلولة) |
| `XfbWaChangePasswordMutation` | `27534818572826036` | www | `data.encrypted_password` | `xfb_wa_change_password` |
| `AddTrustedDeviceMutation` | `24522952587403287` | mex | `device_id`, `device_name` | `xwa2_add_trusted_device.list_of_trusted_device[]` |
| `UntrustTrustedDeviceMutation` | `26574930682133620` | mex | `device_id`, `reason` (`"REREG"` في الاستدعاء الوحيد) | الجذر غير محلول |
| `DeleteTrustedDeviceMutation` | `33867503889559538` | mex | `device_id` | `xwa2_delete_trusted_device` (bool) |
| `GetTrustedDevicesQuery` | `27391232653862770` | mex | `device_id` | `xwa2_get_trusted_devices.list_of_trusted_device[]`: `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` |
| `WhatsappTrustedDeviceRegistration` | `27335489319457030` | facebook-schema | `client_mutation_id`، `payment_type="TRUST_BINDING"`، `platform_trust_token`، و`actor_id` / `logging_id` / `product_id` بقيمة null | ربط ثقة المدفوعات (`RunnableC53437NtS`)، وليس الجهاز الموثوق لتسجيل الدخول |
| `RegistrationPasskeyStartRegisterMutation` | `25415371271434748` | mex | لا شيء | `xwa2_passkey_start_register.credential_create` (سلسلة نصية) |
| `RegistrationPasskeyFinishRegisterMutation` | `24611221275218156` | mex | `credential`, `key_attestation` | `xwa2_passkey_finish_register` (bool) |
| `RegistrationPasskeyEnableMutation` | `25147880151540247` | mex | `credential` | `xwa2_passkey_enable` (bool) |
| `RegistrationPasskeyClear` | `25111972538494859` | mex | لا شيء | `xwa2_passkey_clear` (bool) |
| `RegistrationPasskeyUpdateClientEncryptionStatusMutation` | `24866837389649930` | mex | `credential`, `status` (true) | `xwa2_passkey_update_client_encryption_status` (bool) |
| `PasskeyListExistResponseQuery` | `26930537423220681` | mex | لا شيء | `xwa2_passkey_exist_v2`: `result`, `uuid`, `passkeys[]{credential,create_ts_s,used_ts_s,password_manager,aaguid,usecases,is_disabled}` |
| `PasskeyDeleteMutation` | `25225683640428243` | mex | `credential_ids` (قائمة) | `xwa2_passkey_delete.credential_ids` |
| `AccountLoginMutation` | `27298465499757127` | mex | `phone_number` (سلسلة JID خام) | غير مقروءة |
| `AccountLogoutMutation` | `26863447609979194` | mex | `enabled_biometric` (bool)، `phone_number` | غير مقروءة؛ مهلة العميل 5 ثوانٍ |
| `WWWTriggerAcountRecovery` | `24896267680055094` | mex | `nonce_encryption_key` (PEM بصيغة base64)، `use_case`، `registration_trace_id`، `request_id` | يُسلَّم nonce عبر إشعار (القسم 9) |
| `WWWExchangeNonceForAccessToken` | `25727187160203620` | mex | `nonce`, `use_case`, `encrypted_password`, `request_id`, `registration_trace_id` | رمز الوصول (access token) |
| `WWWGetNonceForCompanionDevice` | `24635485196143064` | mex | `fbid`, `nonce_encryption_key`, `encrypted_password`, `request_id`, `registration_trace_id` | المستخدم الأساسي للجهاز المرافق |
| `RegAccountTransferVerifyTokenMutation` | `7580940708621318` | mex | `token` | فحص OTP لنقل الحساب، مهلة 60 ثانية |
| `ValidateVerifierConfidence` | `25879669248324812` | mex | `authResponse` (base64) | ping ثقة autoconf |
| `GetRegistrationUpsells` / `GetDynamicRegistrationUpsells` / `RegistrationDynamicUpsellShown` | `24265038133175291` / `32273353145641323` / `25435755019399064` | mex | shown: `input="PASSKEYS"` (سلسلة نصية) | جدولة عروض الترقية (upsell) في التسجيل |

### 2.4 عمليات موجودة في الأصول بلا موضع استدعاء في هذا الإصدار

بُحث عنها بالاسم في `java_src` وsmali؛ لا يوجد أي مرجع (found). متغيراتها واستجاباتها غير معروفة.

| العملية | doc_id |
|-----------|--------|
| `SetPasswordMutation` | `33855141324134176` |
| `CheckPasswordMutation` | `26881928138061632` |
| `PasskeyExistResponseQuery` | `25188064727509430` |
| `PasskeyRequestChallengeMutation` | `26311497405176139` |
| `PasskeyVerifyChallengeMutation` | `26876394218624479` |
| `RegistrationPasskeyDisableMutation` | `27775237998742831` |

في 2.26.41.6 لا يستخدم تسجيل الدخول بـ passkey الـ mutations الخاصة بالطلب / التحقق؛ بل يستخدم `/v2/passkey_auth` (القسم 7.1). عمليات passkey الخاصة بالمدفوعات (`PaymentsPasskey*`) وبالبرازيل (`BrPasskey*`) أسطح منفصلة وغير مشمولة.

---

## 3. التحقق من رقم الهاتف لحساب موجود

### 3.1 حزمة التسجيل ونقاط النهاية

`K49` (`RegistrationHttpManager`) يبني الطلبات ويحلل النتائج. توجد حزمتا HTTP: جسر Kotlin (`KotlinRegistrationBridge`، `RetryingHttpClient`) وعميل `wamsys` الأصلي الذي يُبلغ عبر `AbstractC45509Jtc` و`JniBridge.jvidispatch*`. المحدِّد `K49.A0b` يعيد true إذا ضُبطت التهيئة 24762 أو الـ flag **24763** (found)؛ وتنتهي وسوم السجل بـ `/kotlin` أو `/wamsys`.

المسارات مُعمّاة بـ XOR 0x12 في `AbstractC45307Jps` وتُفك إلى (found):

| المسار | دالة Kotlin | الحقول المرسلة (إضافة إلى حقول الجهاز / e2e) |
|------|-----------------|------------------------------------------|
| `/v2/exist` | `performSameDeviceCheck` / `checkIfExists` | `lg`, `cc`, `in`, `foa_backup_token`, `client_capabilities`, `advertising_id`, `context`, `id`, `backup_token` |
| `/v2/challenge` | `challengeRequest` | تحدي الدخول؛ الاستجابة `login`, `challenge`, `retry_after` |
| `/v2/code` | `generateAuthCode` | `token`, `method`, `context`, `advertising_id`, `clicked_education_link`, `manage_call_permission`, `call_log_permission`, `client_start_message` |
| `/v2/register` | `registerPhoneNumber` | `code`, `auth_response` (bytes)، `method`, `context`, `advertising_id`، إضافة إلى مدخلات map مثل `security_code`, `reset`, `wipe_token`, `cred_token` |
| `/v2/security` | `verifySecurityCode` | `code`, `reset`, `wipe_token` (مسار قديم، الـ flag 26215 معطّل) |
| `/v2/passkey_auth` | `passkeyAuth` | `lg`, `context`, `credential` (نتيجة التأكيد assertion) |
| `/v2/device_logout_send`, `/v2/device_logout_fetch` | `sendAccountDefenceDeviceConfirmation`, `fetchAccountDefenceDeviceConfirmation` | `token` |
| `/v2/wfs` | `wfsAuth` | مصادقة Meta SSO ("WFS")، الاستجابة `login`, `wa_ac_machine_id`, `lid` |
| `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop` | الموافقة، سجلات القمع funnel، التحقق الصامت، AB props | غير خاصة بالأمان |

### 3.2 الخطوات

| # | الخطوة | الدليل |
|---|------|----------|
| 1 | `/v2/exist` يعيد حالة الحساب: طرق OTP المؤهلة، أزمنة الانتظار، `second_factor_methods`، `is_device_trusted`، `passkey_auth_challenge`، `password_eligible`، حالة المسح wipe | found (3.3) |
| 2 | إذا كان `passkey_auth_challenge` موجودًا وغير منتهي الصلاحية، يُعرض الدخول بـ passkey (القسم 7.1) | found |
| 3 | يختار المستخدم طريقة؛ `/v2/code` مع `method` | found |
| 4 | يكتب المستخدم OTP؛ `/v2/register` مع `code` و`method` | found |
| 5 | `status=ok` ينهي التسجيل (يُقرأ من النتيجة `login` و`lid` و`ent_access_token` و`ent_canonical_fbid`). `status=fail` مع سبب (3.5) | found |
| 6 | السبب `security_code` يعني أن للحساب عاملًا ثانيًا: `VerifyTwoFactorAuth` يجمع PIN أو كلمة المرور أو OTP البريد ويستدعي `/v2/register` مرة أخرى (3.6) | اسم السبب found؛ التنقل inferred |
| 7 | بعد النجاح: `RegisterName`، تسجيل الجهاز الموثوق (القسم 8)، عرض passkey (القسم 7.2) | found |

"الحساب الموجود" ليس واجهة API منفصلة: يجيب الخادم على `/v2/exist` و`/v2/register` لرقم له حساب بالفعل بنفس مفردات status / reason. حقول مثل `possible_migration` و`need_chat_restore_pn_verify` و`acc_tr_eligible` (نقل الحساب) و`wa_old_eligible` (التحقق عبر الهاتف القديم) تدل على أن الخادم يوجّه مسارات الحسابات الموجودة عبر الاستدعاءين نفسيهما (الحقول found، والمعنى inferred من الأسماء).

### 3.3 حقول استجابة `/v2/exist` التي يقرؤها العميل

| الحقل | النوع | الاستخدام |
|-------|------|-----|
| `status` (`ok`/`fail`)، `reason` | string | النتيجة |
| `login`, `lid` | string | معرّفات الحساب العائدة إلى العميل (المستهلك لم يُتتبَّع) |
| `is_device_trusted` | bool | يُخزَّن كـ `pref_is_device_trusted`؛ يخفي خانة الجهاز الموثوق |
| `second_factor_methods` | مصفوفة string | تُخزَّن كـ `pref_second_factor_methods`؛ القيم سلاسل سلكية من `EnumC43759JAu` |
| `passkey_auth_challenge`, `passkey_credential` | string | يُخزَّن التحدي كـ `reg_passkey_auth_challenge` مع طابع زمني؛ تلميح معرّف credential |
| `password_eligible` | int | أهلية عرض كلمة المرور (upsell) |
| `sms_wait`, `voice_wait`, `wa_old_wait`, `email_otp_wait`, `send_sms_wait`, `silent_auth_wait`, `retry_after` | string | فترات التهدئة لكل قناة |
| `sms_length`, `voice_length`, `wa_old_length`, `email_otp_length` | int | طول الرمز المتوقع |
| `email_otp_eligible`, `wa_old_eligible`, `silent_auth_eligible`, `carrier_silent_auth_eligible`, `send_sms_eligible`, `acc_tr_eligible` | int | أهلية الطريقة |
| `email`, `wa_old_device_name` | string | البريد المقنّع / تسمية الجهاز القديم (التقنيع لم يُتحقق منه) |
| `reset_method`, `wipe_type`, `wipe_token`, `wipe_wait`, `wipe_expiry_time`, `server_time` | مختلط | مسار نسيان PIN (3.7) |
| `fallback_methods`, `recommended_method`, `num_visible_dbs_methods` | مصفوفة / int | ترتيب الواجهة |
| `ent_access_token`, `ent_canonical_fbid` (في `/v2/register`) | string | بيانات اعتماد المستخدم الأساسي لدى Meta |
| `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `version_upgrade`, `custom_block_screen` | مختلط | شاشات الحظر / الترقية (انظر تقرير الحظر) |

### 3.4 طرق OTP

ورقة طلب الرمز الموجَّهة من الخادم (`RequestServerDrivenOtpCodeBottomSheetFragment`، `C46760Kbq`) تعرض سلاسل `method` التالية (found): `sms`, `voice`, `flash`, `wa_old`, `email_otp`, `password`, `passkey`, `send_sms`. أما `silent_auth` و`account transfer` فلكل منهما حقول أهلية خاصة.

### 3.5 أسباب فشل `/v2/register` (المحلل في `KotlinRegistrationBridge`)

| `reason` | المعنى (found: الاسم؛ المعنى inferred) |
|----------|-----------------------------------------|
| `incorrect` | رمز خاطئ أو PIN خاطئ |
| `security_code` | العامل الثاني مطلوب |
| `second_code`, `device_confirm_or_second_code` | العامل الثاني أو تأكيد الجهاز مطلوب |
| `too_many_guesses`, `guessed_too_fast` | تحديد معدل التخمينات؛ يُعاد `guess_wait` |
| `stale`, `mismatch`, `missing`, `format_wrong` | الرمز منتهي / غير مطابق / غائب / بصيغة خاطئة |
| `sms_required` | يجب التحقق عبر SMS |
| `blocked`, `not_allowed`, `limited_release` | محظور، غير مسموح، بوابة إطلاق تدريجي |
| `temporarily_unavailable` | عابر |
| `challenge` | جولة تحدي مطلوبة (`/v2/challenge`) |
| `reset_too_soon` | طُلبت إعادة تعيين PIN المنسي مبكرًا جدًا |
| `consent`, `consent_parent_linking_already_registered` | شاشات الموافقة |

### 3.6 طرق العامل الثاني

`EnumC43759JAu` (found): `twofac_pin`, `password`, `email_otp`, `oauth_email`, `sms`, `voice`, `flash`, `wipe_full`, `wipe_offline`. مع الـ flag **28755** تُدار الشاشة بواسطة `second_factor_methods` ("2FA الديناميكي"، سلسلة السياق `twofac_dynamic`)، و"التحقق بطريقة أخرى" يفتح `Dynamic2faMethodSelectionBottomSheet`.

`K49.A0o` (`verifySecurityCode`):

| الشرط | السلك (Wire) |
|-----------|------|
| الـ flag 26215 معطّل | قديم: `/v2/security` مع `code` (و`reset` و`wipe_token` عند إعادة التعيين) |
| الـ flag 26215 مفعّل، الطريقة ليست `password` | `/v2/register` مع `security_code` = السر بنص صريح في map الطلب، و`method` |
| الـ flag 26215 مفعّل، الطريقة `password` | تُشفَّر كلمة المرور أولًا بواسطة `HOZ.A08` إلى `#PWD_WA:11:<epoch>:<blob>` (القسم 5.3)؛ يُرسل blob في موضع `code` من `/v2/register`؛ إذا فشل التشفير يبلّغ QPL عن `PASSWORD_ENCRYPT_FAILED` |

يأتي مفتاح الغلاف من `WaPasswordEncryptionKeyQuery` عبر `CanonicalPasswordService.A04(..., true)` (يُستدعى من `C47204KjV`، found). أما أي حقل بالضبط يحمل blob على السلك فقد قُرئ من ترتيب وسائط الـ constructor، وليس من طلب ملتقط (inferred).

### 3.7 نسيان PIN، والمسح wipe، وإعادة التعيين بالبريد

يمكن لـ `/v2/exist` أو `/v2/register` أن يعيد `reset_method` و`wipe_type` (`offline` أو `full`) و`wipe_wait` (ثوانٍ) و`wipe_token` و`wipe_expiry_time` و`server_time` (found). `VerifyTwoFactorAuth.A03` يربطها بأربع حالات (found): 0 غير مسموح، 1 في فترة تهدئة ("0_7 days, offline_info")، 2 `offline` ("7_30")، 3 `full` ("over 30"). استدعاء إعادة التعيين يرسل `reset=<mode>` و`wipe_token`؛ و`wipe_full` و`wipe_offline` طريقتان للعامل الثاني (3.6). ما الذي يحذفه الخادم في المسح `offline` مقابل `full` غير معروف.

---

## 4. التحقق بخطوتين (PIN) وبريد الاسترداد

### 4.1 حالة العميل

`C1DP` (`TwoFactorAuthManager`) يحتفظ بـ PIN محليًا (found): المفتاح `two_factor_auth_code`، مشفّرًا اختياريًا (`two_factor_auth_using_encryption`، يفك تشفيره `C1DP.A01` عبر مساعد keystore). يُستخدم لتنبيه دوري "تحقق من PIN": فواصل التذكير 6 ساعات، 12 ساعة، يوم، يوم، 3 أيام، 7 أيام (`C1DP.A0I`، المفاتيح `two_factor_auth_nag_time`، `two_factor_auth_nag_interval`). مفاتيح prefs أخرى: `two_factor_auth_email_set`, `two_factor_auth_dynamic_validated`, `two_factor_auth_last_code_correctness`, `pref_2fa_{sms,voice,flash,email_otp}_wait_time`.

### 4.2 stanzas من نوع IQ (`xmlns="urn:xmpp:whatsapp:account"`، مهلة 32 ثانية)

| الإجراء | Stanza | الاستجابة المقروءة | الفئة |
|--------|--------|---------------|-------|
| جلب الحالة (smax 114) | `type=get` `<2fa/>` | `<2fa>`: وجود الابن `code` يعني أن PIN مضبوط؛ وجود الابن `email` يضبط `two_factor_auth_email_set` | `C1DT.A00`, `C28896Cgx` |
| ضبط PIN / البريد | `type=set` `<2fa><code>PIN</code><email>addr</email></2fa>` (كل ابن اختياري) | النجاح يكتب prefs؛ رمز الخطأ + النص إلى المستمعين | `C1DP.A07`, `C28899Ch0` |
| فحص PIN | `type=get` `<2fa><code>PIN</code></2fa>` | `<2fa>` يحتوي `code` يعني صحيحًا | مسار `VerifyTwoFactorAuthCodeDialogFragment`، `HandlerC25225AtN` |

PIN من 6 أرقام (`SetCodeFragment`، فحص الطول `== 6`). الضبط من النوع 1 والتأكيد من النوع 2. `Fetch2FAEmailStatusJob` يعيد قراءة الحالة (32 ث) لمعرفة ما إذا تم التحقق من البريد. هل يعيد الخادم أبناء غير `code` / `email` غير معروف.

### 4.3 OTP بريد الحساب (منفصل عن `<2fa><email>`)

`C31107Dfz` يبني، و`KRB` يحلل (بادئة السجل `EmailVerificationXmppMethods`):

| الخطوة | Stanza | الاستجابة |
|------|--------|----------|
| طلب OTP | `type=set` `<verify_email><lg/><lc/></verify_email>` (اللغة / locale، 2-3 أحرف) | `verify_email.wait_time` |
| التحقق من OTP | `type=get` `<verify_email><code>NNNNNN</code></verify_email>` (6 أحرف) | `verify_email.code_match` (`true`/`false`)، `wait_time` |

عنوان البريد نفسه غير موجود في هذه الـ stanzas (يُضبط سابقًا، المسار لم يُتتبَّع). يستخدمه `VerifyEmailActivity` والعامل الثاني `email_otp`.

### 4.4 PIN مقابل كلمة المرور مقابل GetTwofa

`GetTwofaQuery` يعيد `twofa_methods[]{method,value,state}`. `PasswordUpsellEligibility` يبحث عن السلسلتين `password` و`pin` في تلك القائمة (found). `SetTwofaMutation` يُستدعى فقط بعد إنشاء كلمة مرور، بأفضل جهد، مع معرّف الجهاز المُجزَّأ (القسم 5.2)؛ و`twofa_auto_enabled` / `twofa_auto_disabled` هما علما النتيجة. PIN نفسه لا يُرسل أبدًا عبر w:mex.

---

## 5. كلمة مرور الحساب

### 5.1 الكيانات

| الكيان | الدور |
|--------|------|
| `PasswordRepository` | التنسيق: `setPassword`, `getTwofa`، معرّف الجهاز (`computeDeviceId`) |
| `PasswordServerApiImpl` | `HasPasswordQuery`, `DeletePasswordMutation`, `GetTwofaQuery`, `SetTwofaMutation` |
| `CanonicalPasswordService` | جلب المفتاح، `A03` للإنشاء، `A02` للتغيير (mutations من نوع `Xfb*`، المخطط `whatsapp-android-www`) |
| `HOZ` | تشفير الغلاف (`A08` → `#PWD_WA:11`) |
| `PasswordCredentialManager` | يحفظ بيانات الاعتماد في Android Credential Manager (`saveCredential`، يُتخطى بدون رقم E.164) |
| الواجهة | `CreatePasswordActivity`, `ReplacePinWithPasswordActivity`, `PasswordUpgradeFragment`, `SettingsPassword`, `TrustThisDeviceActivity` |

### 5.2 الضبط / التغيير / الحذف

`PasswordRepository.setPassword` يحتاج أولًا إلى بيانات اعتماد المستخدم الأساسي؛ وبدونها يفشل بالرسالة "No canonical credentials available to set password" (found). أي أن كلمة المرور مرتبطة بالمستخدم الأساسي لدى Meta، وليس برقم WhatsApp فقط.

```
setPassword(pw, isChange, enableTwofa)
  isChange  -> CanonicalPasswordService.A02  XfbWaChangePasswordMutation
  !isChange -> CanonicalPasswordService.A03  XfbWaCreatePasswordMutation
               then, if enableTwofa: GetTwofa/SetTwofa best effort (device_id = base64(SHA-256(ANDROID_ID)))
each: A04 = key fetch (WaPasswordEncryptionKeyQuery) + HOZ.A08 -> data.encrypted_password
```

`device_id` هو `K2M.A01(android_id)` = Base64 (flag 2، بدون التفاف) لـ SHA-256 من `Settings.Secure.ANDROID_ID` (found). الحذف لا يرسل متغيرات؛ والرمز الشبيه بـ HTTP وهو 409 يُترجم إلى نتيجة "محظور، يتطلب بريدًا إلكترونيًا" (found). القواعد المحلية في `CreatePasswordActivity`: الطول من 8 إلى 20، حرف واحد على الأقل ورقم واحد على الأقل، ويجب أن يتطابق التأكيد (found).

### 5.3 غلاف `#PWD_WA:11` (`HOZ.A02` / `A08`)

```
epoch   = current time in seconds
aesKey  = random 32 B (AES-256)         iv = random 12 B
ct||tag = AES-GCM(aesKey, iv, utf8(secret))    // no AAD on this path
wrapped = RSA/ECB/PKCS1Padding(serverPublicKey, aesKey)
blob    = 0x01 | key_id(1 B) | iv(12) | len(wrapped) as uint16 LE | wrapped | tag(16) | ct
out     = "#PWD_WA:11:" + epoch + ":" + base64(blob, URL_SAFE | NO_WRAP | NO_PADDING)
```

يجب أن يكون `key_id` من 1 إلى 255 (`CanonicalPasswordService.A01`). يُحلَّل مفتاح RSA من PEM بصيغة X.509 SPKI؛ ومسار PKCS1 لا يفحص حجم المعامل modulus (اختبار ≥ 4096 بت موجود فقط في `HOZ.A06`، وهو متغير OAEP مختلف). يُستخدم الغلاف نفسه في ثلاثة مواضع (found): العامل الثاني عند التسجيل (3.6)، وإنشاء / تغيير كلمة المرور الأساسية (5.2)، والاسترداد (`exchangeNonce`، القسم 9، ملفوفًا في JSON `{version:1,timestamp,password}`).

متغيرات أخرى في `HOZ` (ليست `#PWD_WA:11`): `A03` و`A06` تستخدمان RSA-OAEP-SHA-256 مع IV صفري وAAD (مسار Waffle SSO يكتب `#PWD_WAFFLE` في `C40069Hd8` / `C40090HdT`).

---

## 6. OPAQUE وVOPRF والتشفير الأصلي

### 6.1 ما هو موجود

| العنصر | الموضع | المستوى |
|------|-------|------|
| `WESOpaqueClientRegistrationStartResult` (.rodata `0xaebae`)، `...LoginStartResult` (`0xaebd5`)، `...RegistrationFinishResult` (`0xaeda9`)، `...LoginFinishResult` (`0xaedd1`)، `...RegistrationState` (`0x115042`)، `...LoginState` (`0x115072`) | سلاسل `libwhatsapp.so` | found |
| `OPAQUE_PBKDF2_SALT` (`0x17e129`)، `VOPRF06-HashToGroup-` (`0x19465a`)، `VOPRF06-Finalize-` (`0x19466f`) | سلاسل `libwhatsapp.so` | found |
| `org/whispersystems/curve25519/NativeVOPRFExtension` | المكتبة نفسها؛ فئة Java فيها `nativeBlind` و`nativeUnBlind` و`nativePcdBlind` | found |
| `libvoprf-ed25519.so`, `libvoprf-ristretto.so` | مكتبتان منفصلتان، تصدّران `JNI_OnLoad` فقط؛ مغلّفات Java هي `com.facebook.privacy.acs.VoprfEd25519` / `VoprfRistretto` | found |

### 6.2 الدوال التي تشير إلى السلاسل (arm64، vaddr)

| الدالة | الحجم | المحتوى | المستوى |
|----------|------|---------|------|
| `fcn.0075a1c0` | 644 B | تشير إلى `VOPRF06-HashToGroup-`؛ mbedTLS SHA-512 init / update ×6 / finish، ثم تمريرة SHA-512 ثانية | found |
| `fcn.0075b550` | 712 B | تشير إلى `VOPRF06-Finalize-` و`OPAQUE_PBKDF2_SALT`؛ SHA-512 على transcript الإنهاء، ثم `mbedtls_pkcs5_pbkdf2_hmac` | found |
| `fcn.0075a618`, `fcn.0075ad40` | - | كلتاهما تستدعي `fcn.0075b550`، ثم `mbedtls_hkdf_extract` + ثلاث `mbedtls_hkdf_expand` (md type `0xb`) | found |
| `fcn.0075a0d4` | - | تستدعي `fcn.0075a1c0` | found |

استدعاء PBKDF2 في `fcn.0075b550` (التفكيك disassembly): طول كلمة المرور `0x40` (64 B، ناتج OPRF)، طول الملح `0x12` = 18 = طول الوسم `OPAQUE_PBKDF2_SALT` ويُهيَّأ المخزن المؤقت من ذلك الوسم، الطول المشتق `0x40`، عدد التكرارات يمرره المستدعي (ليس ثابتًا في هذه الدالة)، md type `0xb`. القيمة `0xb` تساوي SHA-512 في ترقيم mbedTLS 3.6 (inferred من قيمة enum وأطوال 64 بايت). إذن ناتج OPRF يغذي PBKDF2-HMAC-SHA-512 مع وسم ASCII كملح (found لشكل الاستدعاء، inferred لدالة التجزئة).

أدوار الدوال (blind وfinalize وregistration-finish وlogin-finish) inferred من شكل الاستدعاء. المجموعة / ciphersuite (المنحنى، المعرّف الملحق ببادئتي `VOPRF06-`)، وتخطيطات بايتات KE1 / KE2 / KE3، ومحتويات الغلاف، ونوع AKE **unknown**؛ وقد قُرئت الشيفرة الأصلية كتفكيك disassembly للدوال المذكورة، وليس كشيفرة مُفكَّكة decompiled.

### 6.3 من يستدعيها: النسخ الاحتياطي المشفر، وليس كلمة مرور الحساب

مدخل Java لآلة الحالة هو بروتوكول النسخ الاحتياطي المشفر (بادئة السجل `encb/`):

| الفئة | الدور (found) |
|-------|--------------|
| `EncBackupViewModel` | ينشئ `C61447Rhg` (معالج الدخول) مع سلسلة كلمة مرور النسخ الاحتياطي للمستخدم |
| `AbstractC62498S8e` | يرسل IQs هي `sendInitRegIq`, `sendBeginRegIq`, `sendFinishRegIq`, `sendInitLoginIq`, `finishLoginOnSuccess`, `sendDeleteAccountIq` (`EncryptedBackupProtocolHelper`) |
| `C62510S8q` (smali `X/S8q`) | معالج الاستجابة؛ `jvidispatchOOO(0xb, password, ...)` يعيد حالة الدخول (`Rtz`)، و`jvidispatchOO(0x20, state)` الرسالة التالية |
| `C62511S8r` | استجابة begin-login: يتحقق من `l2` بواسطة `l2_sig` و`ed_pub` (Ed25519)، ويقرأ `count` و`backoff` و`max_attempts`، ثم `jvidispatchOIOOO(1, 100000L, state, ...)` |
| `RunnableC29321Co8` | finish-login: `jvidispatchOIOO(1, 100000L, state, ...)`، يقرأ حقول النموذج، ويفك تشفير مفتاح النسخ الاحتياطي بـ AES-GCM، ويبني proto `C25803BBm` (`backupKeyData_`, `r3_`, `opaqueChallenge_`, `transcript_`) |

يُمرَّر `100000` إلى استدعاءات الإنهاء الأصلية في التسجيل والدخول كليهما (found). وهو على الأرجح عدد تكرارات PBKDF2 (inferred: الدالة الأصلية تأخذه كمعامل). أن فهارس `jvidispatch` هذه تصل إلى شيفرة `WESOpaque*` أمر inferred من الوسائط (سلسلة كلمة المرور داخلة، وكائنات الحالة بين الاستدعاءات، وحقول `l2` / `r3`) ومن غياب أي مستهلك آخر؛ لا يوجد رمز Java يسمّي OPAQUE. شيفرة كلمة مرور الحساب (القسم 5) لا تلمسها أبدًا.

### 6.4 VOPRF الآخر: رموز Meta ACS

لـ `NativeVOPRFExtension` و`libvoprf-ed25519.so` مستهلكان في Java هما `C1N9` (`ACSTokenProviderImpl`، بادئة السجل `ACSToken/`) و`KYL`: عامل التعمية blinding factor، الرمز المعمّى الموقَّع، إثبات DLEQ، إزالة التعمية، السر المشترك (سلاسل found هي `blinding_factor_string` و`shared_secret_string` و`ACSToken/processSignedBlindedToken`). العمليات المطابقة في الأصول هي `WaAcsGetConfig` (`27388182297440754`) و`WaAcsIssueCredentials` (`26645395115100537`)؛ لا يظهر أي من الاسمين في الشيفرة، لذا فإن نقل طلب الرمز لم يُتتبَّع. هذا رمز اعتماد مجهول الهوية وليس تسجيل دخول بكلمة مرور.

### 6.5 ماذا يعني هذا لـ "الدخول بكلمة المرور"

| الادعاء | الحالة في 2.26.41.6 |
|-------|---------------------|
| الدخول بكلمة مرور الحساب يستخدم OPAQUE | غير مدعوم في الشيفرة: تُرسل كلمة المرور كغلاف RSA/AES (`#PWD_WA:11`)، ولا تُبنى أي رسالة OPAQUE في المسارات المقروءة؛ و`SetPasswordMutation` و`CheckPasswordMutation` بلا موضع استدعاء |
| يوجد عميل OPAQUE أصلي | found |
| يخدم كلمة مرور النسخ الاحتياطي المشفر | found (المستدعي في Java)، والربط بالرموز الأصلية inferred |
| الخادم يخزن verifier بدل كلمة المرور لكلمة مرور الحساب | unknown |

سلاسل Java التي تبدو كدليل على OPAQUE لكنها غير ذات صلة (found): `opaqueChallenge_` (proto إقلاع النسخ الاحتياطي أعلاه)، `opaquePayload_` (`C61318RfY`، إطار الترحيل المقيَّد tethered migration)، `OpaqueConfig` / `prefersOpaqueConfig` (تهيئة bitmap في `EnumC167127Ba`)، `OpaqueKey(` (`C44715Jfl`، غلاف سلسلة)، `KE1` (`X.KE1` فئة Android Compose)، `opaque_client_data` (عمود مزامنة السجل).

---

## 7. مفاتيح المرور (WebAuthn)

### 7.1 الدخول وقت التسجيل

| الخطوة | الدليل |
|------|----------|
| `/v2/exist` يعيد `passkey_auth_challenge`؛ `K15.A03` يقبله ما دام أحدث من `SignalCredentialStateController.MAX_RETRY_TIME` | found |
| `PasskeyVerifier.onPasskeyChallengeReceived` ينفذ تأكيد assertion لـ credential قابل للاكتشاف عبر `androidx.credentials` (`PasskeyLowLevelAndroidApiImpl.loginWithPasskey`)؛ والمرحلة تُحفظ في pref `passkey_login_stage` | found |
| `K49.A0l` يرسل النتيجة كـ `credential` إلى `/v2/passkey_auth` | found |
| الاستجابة: `status` (`ok`/`fail`)، `reason` (`temporarily_unavailable`, `disabled`)، `credential_create` (string)، `login`، `cred_token` | found |
| يُخزَّن `cred_token` لكل رقم هاتف في `passkey_disabled_cred_token_map` ويُعاد إرساله كـ `cred_token` في الطلبات اللاحقة عندما يكون الـ flag **25565** مفعّلًا | found؛ الغرض (إثبات أن passkey عُطّلت) inferred |

تُسجَّل نتائج جانب العميل كـ `passkey_client_login_{cancelled,nopasskey,ineligible,error,success}`. تُستخدم `prepareGetCredential` فقط على Android 14+ (SDK 34) والـ flag **21638** (found).

### 7.2 الإنشاء والإدارة

عرض (upsell) بعد خطوة 2FA: `VerifyTwoFactorAuth.onCheckPasskeyUpsellAfter2FA` يستخدم `PasskeyCreateEducationScreen` أو ورقة سفلية؛ والـ flag **20409** يبدّل بين التدفق الضابط control ومسار الترقية السريعة (QP)، والـ flag **16591** يضيف فحص أهلية (found).

| العملية | بوابة MEX | بديل IQ (`xmlns="passkey"`) |
|-----------|----------|---------------------------------|
| بدء التسجيل | flag **10453** | smax 125، `type=get` |
| إنهاء التسجيل | flag **10452** | smax 126، `type=set` |
| المسح clear | flag **10461** | smax 129، `type=set` |
| القائمة / الوجود، الحذف، التفعيل، تحديث حالة التشفير | دائمًا MEX | لا شيء |

`credential_create` من start-register يُخزَّن مؤقتًا في `passkey_create_challenge`. إنهاء التسجيل يرسل `credential` و`key_attestation`؛ ولا يُبنى حمل الإثبات attestation إلا إذا كان الـ flag **28809** مفعّلًا (base64 لإثبات المفتاح، `getKeyAttestationPayload`). الـ flag **8877** يلف start / finish في مساعد إعادة محاولة / مهلة (`C29707Cw7`، الدور inferred). `PasskeyRandomizedDailyCronJob` و`PasskeyExistsCache` يحدّثان قائمة الوجود؛ واستجابة exists تخزّن `uuid` في `reg_passkey_exists_uuid`.

### 7.3 PRF والتشفير من جهة العميل

`PasskeyPrfSecrets` يستخدم مُدخل PRF الثابت `WhatsAppPasskeyStaticPrfInputV1` ويخزّن مفتاحًا جذريًا مشتقًا من PRF في `prf_derived_root_key.key` (وسم مفتاح التغليف `prf_derived_root_key_file_encapsulation_key`). `RegistrationPasskeyUpdateClientEncryptionStatusMutation` يخبر الخادم بأن passkey تُستخدم للتشفير من جهة العميل. المستهلك هو مسار النسخ الاحتياطي المشفر (`VerifyPasskeyFragment`، inferred من موقع الفئة).

---

## 8. الأجهزة الموثوقة

| العنصر | القيمة |
|------|-------|
| `device_id` | `Base64(SHA-256(ANDROID_ID))` (بدون التفاف)، `K2M.A01` |
| `device_name` | `<MANUFACTURER>-<MODEL>` (`HO4.A00`) |
| الخانة | تظهر في `VerifyPhoneNumber` و`VerifyTwoFactorAuth` عندما يكون الـ flag **30530** مفعّلًا و`pref_is_device_trusted` خاطئًا؛ المفاتيح `pref_trusted_device_checkbox_shown` / `_checked` |
| إتمام التسجيل (`RegisterName`) | عند الموافقة: `AddTrustedDeviceMutation`؛ عند عدمها: `UntrustTrustedDeviceMutation` مع `reason="REREG"` (`C29652Cu9`، found) |
| الإعدادات | `TrustedDevicesRepository` يسرد (`GetTrustedDevicesQuery`) ويزيل (`DeleteTrustedDeviceMutation`)؛ `TrustThisDeviceActivity` |
| الأثر | يُعاد `is_device_trusted` من `/v2/exist` و`/v2/register` و`GetTwofa` و`SetTwofa`؛ ويستخدمه العميل لتخطي الخانة. أن الجهاز الموثوق يتخطى مطالبة PIN / كلمة المرور أمر inferred؛ ولا توجد شيفرة في العميل تتخطى العامل الثاني |

عناصر `list_of_trusted_device[]` تحمل `device_id` و`device_name` و`latitude` و`longitude` و`last_ts` (موقع آخر استخدام يوفره الخادم؛ كيفية اشتقاقه unknown).

---

## 9. استرداد الحساب (المستخدم الأساسي لدى Meta)

`AccountRecoveryManager` لا يسترد محادثات WhatsApp ولا حساب رقم الهاتف. إنه يعيد إنشاء بيانات اعتماد المستخدم الأساسي لدى Meta لحساب مرتبط بـ FB (found).

| الخطوة | التفصيل |
|------|--------|
| المُشغّل | `maybeRecoverAccount`: لا مستخدم أساسي، أو بيانات الاعتماد غير صالحة؛ المتغير المؤجل مقيّد بالـ flag **16017** |
| مفتاح العميل | يولّد زوج مفاتيح، ويرسل المفتاح العام (PEM، base64) كـ `nonce_encryption_key` في `WWWTriggerAcountRecovery` مع `use_case` و`registration_trace_id` و`request_id` |
| Nonce | يصل عبر إشعار؛ انتهاء المهلة ينتج "Account Recovery Failed due to Nonce notification timeout" |
| التبادل | `WWWExchangeNonceForAccessToken` مع `nonce` و`use_case` و`request_id` و`registration_trace_id` و`encrypted_password` = غلاف `#PWD_WA:11` لسر عشوائي من العميل داخل JSON `{version:1,timestamp,password}` |
| الجهاز المرافق | `WWWGetNonceForCompanionDevice` و`WWWTradeNonceForAccessTokens` تفعلان الشيء نفسه للأجهزة المرتبطة (`CompanionCanonicalUserNonceManager`, `CompanionCanonicalUserAccessTokenJob`) |
| ذات صلة | `WWWValidateCanonicalUser`, `WWWCanonicalUserValid`, `WWWAppGenerateCanonicalNonce` (مواضع الاستدعاء موجودة؛ الحقول غير مقروءة) |

الإملاء `Acount` من WhatsApp نفسها. أما خوارزمية مفتاح تشفير nonce (الزوج يأتي من `N6T.A02`) فغير محلولة.

---

## 10. تسجيل الدخول والخروج

`LogoutManager` ينفذ تسجيل خروج ناعمًا (متعدد الحسابات) ومسار العودة إلى الدخول (found).

| الإجراء | السلك (Wire) | ملاحظات |
|--------|------|-------|
| الخروج | `AccountLogoutMutation` `{phone_number, enabled_biometric}` | `enabled_biometric` من إعداد القياسات الحيوية؛ مهلة 5 ثوانٍ، ثم يتابع الخروج محليًا ("timed out, proceeding with logout") |
| Push | `LogoutPushManager` يعطّل / يعيد تفعيل GCM push (`"re-enable"` عند التراجع) | found |
| محلي | `markCurrentAccountLoggedOut`, `removeLoggedOutAccountWithCleanup`, `deleteGmsBackupState`، وواجهة اختيارية لحذف المحادثات (`DeleteChatsOnLogoutDialog`, `LoggedOutChatsFragmentDialog`) | found |
| العودة إلى الدخول | `AccountLoginMutation` `{phone_number}`، ثم `loginBack` → `actionReconnect`؛ انتظار حتى 7 ثوانٍ للاتصال | `PrimaryLoginBackActivity` |

إنه علم حالة على جانب الخادم في إعداد متعدد الحسابات، وليس تسجيل الدخول برقم الهاتف في القسم 3، وليس إزالة جهاز مرتبط. الـ flag **28385** يُقرأ في `LogoutManager` (الدور غير محلول).

---

## 11. Feature flags

المعرّفات بخط عريض. الأنواع: B = AB prop منطقي، C = تهيئة. الأسماء غير موجودة في العميل؛ الدور هو ما تفعله الشيفرة بالـ flag.

| المعرّف | الموضع | ما يتحكم به |
|----|-------|----------|
| **24762** (C) / **24763** (B) | `K49.A0b` | حزمة التسجيل Kotlin بدل `wamsys` الأصلية |
| **26215** | `K49` التحقق / إعادة تعيين رمز الأمان | العامل الثاني عند التسجيل عبر `/v2/register`، ويفعّل غلاف كلمة المرور؛ معطّل = `/v2/security` القديم |
| **25565** | `K49.A0M` | إرسال `cred_token` المخزَّن |
| **28755** | `VerifyTwoFactorAuth` | اختيار طريقة 2FA الديناميكي من `second_factor_methods` |
| **30530** | `VerifyPhoneNumber`, `VerifyTwoFactorAuth` | خانة الجهاز الموثوق |
| **20409** | `VerifyTwoFactorAuth` | عرض passkey بعد 2FA عبر QP مقابل الضابط control |
| **16591** | `VerifyTwoFactorAuth` | فحص أهلية passkey قبل العرض |
| **21638** | `PasskeyAndroidApi` | `prepareGetCredential` (Android 14+) |
| **10452** / **10453** / **10461** | `PasskeyServerApiImpl` | MEX بدل IQ للإنهاء / البدء / المسح |
| **28809** | `PasskeyServerApiImpl` | حمل إثبات المفتاح key attestation |
| **8877**, **31281** | `PasskeyCreateFlow` | غلاف إعادة المحاولة؛ مسار passkey بديل للمدفوعات (الأدوار inferred) |
| **5156** | `SetCodeFragment` | عرض "إضافة بريد إلكتروني" بعد ضبط PIN |
| **5711** | `TwoFactorAuthActivity`, `SetCodeFragment` | التخطيط فقط (يخفي مؤشر الصفحة) |
| **16017** | `AccountRecoveryManager` | معالجة nonce المؤجلة |
| **28385** | `LogoutManager` | غير محلول |

---

## 12. حالات الخطأ

| العرض | السبب | الحل / ملاحظة |
|---------|-------|------------|
| `/v2/register` بالسبب `security_code` أو `second_code` | للحساب عامل ثانٍ | أرسل PIN / كلمة المرور / OTP البريد عبر `/v2/register` (3.6) |
| `PASSWORD_ENCRYPT_FAILED` (QPL) | فشل جلب المفتاح، أو `key_id` خارج 1-255، أو استثناء تشفير (سجلات `encryptRegistrationPassword/*`) | أعد المحاولة؛ العميل يُجهض المحاولة |
| `reset_too_soon` | إعادة تعيين PIN المنسي قبل انقضاء `wipe_wait` | انتظر؛ حالة الواجهة 1 |
| `too_many_guesses` / `guessed_too_fast` | حد تخمين PIN أو OTP | انتظر `guess_wait` |
| `No canonical credentials available to set password` | لا يوجد مستخدم أساسي لدى Meta على الجهاز | أكمل إعداد المستخدم الأساسي أولًا |
| فشل إنشاء / تغيير كلمة المرور | حمولة `xfb_wa_*` غير ناجحة؛ رمز الخطأ يربطه `CanonicalPasswordService.A00` | enum أخطاء الواجهة `EnumC49982M3j` |
| `DeletePassword` 409 | البريد الإلكتروني للحساب مطلوب قبل الإزالة | أضف البريد أولًا |
| `Account Recovery Failed due to Nonce notification timeout` | لم يُستلم الإشعار | أعد تشغيل المُشغّل |
| `...passwordPublicKeyStr is null` / `passwordKeyIdStr is null` | شهادة التشفير مفقودة في تبادل الاسترداد | أعد المحاولة |
| `LogoutManager/callLogoutApi/timed out` | لا استجابة خلال 5 ثوانٍ | يتابع الخروج محليًا |
| Passkey: `NoCredentialException`, `NotAllowedError`، GMS قديمة جدًا، خدمات Play مفقودة | إخفاقات Credential Manager | يعود إلى الطرق الأخرى |

---

## 13. فروق أساسية

| A | B |
|---|---|
| شيفرة OPAQUE الأصلية (كلمة مرور النسخ الاحتياطي المشفر، IQs من نوع HSM `encb/*`) | كلمة مرور الحساب (`XfbWa*` + `#PWD_WA:11`) |
| `libvoprf-*.so` + `NativeVOPRFExtension` (رموز ACS المجهولة) | آلة حالة OPAQUE (`WESOpaque*`) |
| PIN (IQ `<2fa>`، 6 أرقام) | كلمة المرور (w:mex، 8-20 حرفًا) |
| `<2fa><email>` (بريد الاسترداد لإعادة تعيين PIN) | مسار OTP `<verify_email>` والعامل الثاني `email_otp` |
| `SetTwofaMutation` (علم لكل معرّف جهاز بعد كلمة المرور) | IQ ضبط PIN |
| الجهاز الموثوق (الدخول، `AddTrustedDeviceMutation`) | `WhatsappTrustedDeviceRegistration` (ربط ثقة المدفوعات) |
| `AccountLogoutMutation` (خروج ناعم) | فك ارتباط جهاز مرافق (`remove-companion-device`) والخروج بسبب الحظر |
| `WWWTriggerAcountRecovery` (بيانات اعتماد المستخدم الأساسي) | مسح نسيان PIN (`wipe_*`, `/v2/security`) |
| `#PWD_WA:11` (WhatsApp) | `#PWD_WAFFLE` (Waffle SSO) |
| عمليات `PasskeyServerApiImpl` (passkeys الحساب) | `PaymentsPasskey*`, `BrPasskey*` |
| `/v2/passkey_auth` (تأكيد الدخول) | `PasskeyRequestChallengeMutation` / `PasskeyVerifyChallengeMutation` (بلا موضع استدعاء) |

---

## 14. Baileys (`baron-baileys-v2`)

مقارنة مع `src/Socket/privacy.js` و`src/Socket/registration.js`.

| العنصر | APK 2.26.41.6 | Baileys | النتيجة |
|------|---------------|---------|--------|
| doc_ids للأجهزة الموثوقة والدخول والخروج وكلمات المرور وpasskeys | الأصول | الأرقام نفسها | مطابق |
| `accountLogin` / `accountLogout` | `input{phone_number}` / `input{phone_number, enabled_biometric}` | نفسه | مطابق |
| `getTrustedDevices` | `input{device_id}` يُرسل دائمًا | `{}` | يختلف؛ سلوك الخادم بدون `device_id` غير معروف |
| السبب الافتراضي لـ `untrustTrustedDevice` | `"REREG"` في الاستدعاء الوحيد | `'USER_INITIATED'` | يختلف، الأسباب الأخرى غير معروفة |
| عمليات passkey | المتغيرات `credential` و`key_attestation` و`credential_ids`؛ الجذور `xwa2_passkey_*` | لا شيء منفَّذ في الملفات المقروءة | استخدم أشكال APK |
| `SetPassword` / `CheckPassword` | بلا موضع استدعاء | doc_ids فقط | غير متحقق منه، لا تعتمد عليه |
| تشفير `#PWD_WA:11` | القسم 5.3 | غير موجود في شجرة `src` المقروءة | نفّذه من القسم 5.3 |

لماذا يفشل عميل مستقل على هذه المسارات (inferred، لم يُختبر شيء): نقاط نهاية التسجيل تتوقع حقول الطلب المحمية e2e التي يبنيها التطبيق (`C45446JsB`)؛ واستدعاءات كلمة المرور والاسترداد تحتاج بيانات اعتماد المستخدم الأساسي؛ وتأكيد passkey يحتاج مصادِقًا من المنصة.

---

## 15. التدفقات الكاملة

### 15.1 التحقق من رقم له حساب موجود

```
[User]            [Client]                                   [Server]
  │ enter number    │                                           │
  ▼                 ▼                                           │
            POST /v2/exist ───────────────────────────────────►│
                    │◄── methods, waits, second_factor_methods, │
                    │    passkey_auth_challenge, is_device_trusted
  passkey? ─yes──►  Credential Manager assertion                │
                    POST /v2/passkey_auth {credential} ────────►│
                    │◄── status, login, cred_token              │
  no                ▼                                           │
            POST /v2/code {method} ─────────────────────────────►│  OTP sent (sms/voice/flash/wa_old/email_otp)
  type OTP ──►  POST /v2/register {code, method} ───────────────►│
                    │◄── ok | fail(reason)                      │
   reason=security_code / second_code                           │
  PIN / password ─► POST /v2/register {security_code | #PWD_WA blob, method}
                    │◄── ok (login, lid, ent_access_token)      │
                    ▼                                           │
        optional: AddTrustedDeviceMutation | UntrustTrustedDeviceMutation(REREG)
        optional: passkey upsell -> StartRegister -> Credential Manager -> FinishRegister
  forgot PIN ─────► reset=<mode>, wipe_token (after wipe_wait) ─►│
```

### 15.2 ضبط PIN وبريد الاسترداد

```
[Client]  IQ get <2fa/> ───────────────► [Server]  <2fa>[<code/>][<email/>]
[Client]  IQ set <2fa><code>NNNNNN</code><email>x</email></2fa> ──► ok | error(code,text)
[Client]  Fetch2FAEmailStatusJob: IQ get <2fa/> until <email> present
[Client]  IQ get <2fa><code>NNNNNN</code></2fa> ──► <2fa><code/></2fa> = correct   (periodic reminder)
```

### 15.3 إنشاء كلمة مرور للحساب

```
[Client]  canonical credentials present? ── no ─► fail
[Client]  WaPasswordEncryptionKeyQuery ──► public_key (PEM), key_id (1..255)
[Client]  HOZ.A08: AES-GCM + RSA-PKCS1 wrap -> "#PWD_WA:11:<epoch>:<blob>"
[Client]  XfbWaCreatePasswordMutation {data:{encrypted_password}} ──► success
[Client]  (best effort) GetTwofaQuery / SetTwofaMutation {input:{twofa_enabled:true, device_id}}
```

---

## 16. المجهولات

| الموضوع | السبب |
|-------|--------|
| ciphersuite الخاص بـ OPAQUE (المجموعة، المعرّف بعد `VOPRF06-`)، وتخطيطات KE1 / KE2 / KE3 والغلاف، ونوع AKE | شيفرة أصلية، قُرئ تفكيك 4 دوال فقط |
| ربط فهارس `jvidispatch` الخاصة بالنسخ الاحتياطي المشفر بشيفرة `WESOpaque*` | حسب شكل الوسائط، وليس حسب الرمز |
| عدد تكرارات PBKDF2 لدالة KSF في OPAQUE | يُمرَّر كمعامل؛ و`100000` هو القيمة الحرفية التي تمررها مستدعيات Java |
| هل يوجد مسار يرسل كلمة مرور الحساب عبر OPAQUE | لم يُعثر على مسار كهذا؛ لا يمكن استبعاد المغلّفات المخفية خلف dispatch رقمي |
| استجابات `XfbWa*` و`AccountLogin` و`AccountLogout` و`UntrustTrustedDevice` | الجذر والحقول غير مقروءة |
| العمليات بلا موضع استدعاء (2.4) | المتغيرات والاستجابات غير معروفة |
| الحقل الدقيق الذي يحمل blob الـ `#PWD_WA` في `/v2/register` | مشتق من ترتيب الـ constructor |
| معنى الحقلين `login` و`lid` العائدين من `/v2/exist` و`/v2/passkey_auth` | المستهلكون لم يُتتبَّعوا |
| أثر `wipe_full` / `wipe_offline` على الخادم | العميل يعرض النص فقط |
| هل يتخطى الجهاز الموثوق العامل الثاني | على جانب الخادم؛ لا منطق تخطٍّ في العميل |
| خوارزمية زوج مفاتيح الاسترداد (`N6T.A02`) | لم تُقرأ |
| أدوار الـ flags 8877 و31281 و28385 | بوابات فقط |
| حركة المرور الفعلية | تحليل ساكن فقط |
