<!-- src-sha1: 166366154a0dd7893ab70aa91166a96d5a2e788f -->
# WhatsApp Account-less Surface — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** ما يعرضه عميل Android دون حساب مسجَّل أو قبل اكتمال التسجيل — العناصر المصدَّرة في manifest (activities وaliases وservices وreceivers وproviders)، شاشات ما قبل التسجيل وتوجيه حالة التسجيل، الروابط العميقة وروابط الويب، نقاط HTTP وGraph غير المصادَق عليها، جدول المضيفين المضمَّن في الكود، نموذج الدعم عند تسجيل الخروج، نقاط الدخول إلى حالة الحظر والاستئناف، المعرّفات المرسلة قبل تسجيل الدخول، أسطح IPC لأطراف ثالثة، ما يبقى مجهولًا

---

## 1. ماذا تعني "بلا حساب" في هذا الإصدار

لا يوجد "وضع تسجيل خروج" واحد. تعمل عدة مسارات مستقلة بينما لا يملك العميل JID للمستخدم، ولا جلسة دردشة مصادَق عليها، أو يكون التسجيل غير مكتمل. يستبدل كل مسار بيانات اعتماد مختلفة بالحساب. جميع العبارات هنا تحليل ساكن لـ APK المفكَّك (`versionCode 264100600`, target SDK 36, min SDK 23). لم يُلاحَظ شيء على الشبكة. المستويات: **found** = مقروء في الكود أو manifest، **inferred** = مستنتج من الكود، **unknown** = غير قابل للحل ساكنًا. توثيق دفاعي: تُوصَف الأسطح وعناصر التحكم ولا تُستغَل.

أسماء الـ obfuscation خاصة بكل build، وأُعيد حلّها من سلاسل ثابتة في 2.26.41.6.

| المسار | بيانات الاعتماد التي تحلّ محل الحساب | النقل | الفئات الرئيسية (2.26.41.6) |
|------|--------------------------------------|-----------|--------------------------|
| تسجيل رقم الهاتف | لا شيء حتى `/v2/register`؛ يحمل الطلب حزمة مفتاح Noise الساكن ومعرّفات الجهاز | HTTPS `/v2/*` | `K49`, `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| سجل مسار ما قبل الرقم | معرّف الهاتف (`fdid`) فقط | HTTPS `/v2/pre_pn_client_log` | `PrePnBaseFunnelLogger`, `K49` |
| AB props قبل الدردشة | prefs `ab_key` / `ab_hash` | HTTPS `/v2/reg_onboard_abprop` | `K49.checkPreChatdABProps` |
| حالة الحظر / الاستئناف | token معتم يُخزَّن وقت الحظر + client token للتطبيق مضمَّن في الكود | HTTPS Graph `graph.<domain>/graphql` | `AbstractC40195HfH`, `C37409GLo`, `C37604GYf`, `C37414GLt` |
| نموذج الدعم عند تسجيل الخروج | لا شيء؛ بريد إلكتروني + نص حر + `anid` | HTTPS multipart POST | `LoggedOutContactFormActivity`, `C47328KmN` |
| رفع الأعطال / السجلات | token التطبيق المضمَّن في الكود | HTTPS `crashlogs.whatsapp.net` | `C10V`, `C05640An` |
| الأصول الثابتة | لا شيء | HTTPS GET | `static.whatsapp.net/*` |
| Graph ببيانات اعتماد مجهولة (ACS / OHAI) | ACS token أو إعداد مفتاح OHAI، بلا JID | HTTPS `acs.whatsapp.com/graphql` | `C31991Nz`, `R5t`, `N5I` |
| تسجيل الجهاز المصاحب | لا شيء؛ اتصال Noise بـ JID فارغ مسموح هنا فقط | Noise | `HandlerThreadC12340b0` |
| بديل DNS المضمَّن | لا شيء | جدول مضمَّن في الكود | `AbstractC47101wK`, `C36881dC` |

غير مشمول هنا، راجع التقارير المرتبطة: خطوات التسجيل وطرق OTP وأسباب الفشل ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) القسم 3)؛ رموز attestation المرسلة عند التسجيل ([WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md))؛ آلة حالات الحظر وتشفير الاستئناف ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) القسمان 2 و10)؛ تسجيل الدخول عبر Noise وتسجيل الجهاز المصاحب ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md))؛ قياسات WAM عن بُعد ([WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)).

---

## 2. Manifest: المكوّنات المصدَّرة

### 2.1 الأعداد (found, `AndroidManifest.xml`، مفسَّر تحت `<application>`)

| النوع | المعلَن | المصدَّر (`true` صريح؛ لم يُعتمد على الافتراضي الضمني في أي منها) |
|------|---------:|----------------------------------------------------------------:|
| `activity` | 828 | 22 |
| `activity-alias` | 33 | 29 (منها 14 aliases معطَّلة لأيقونات التشغيل `AppIcon01..14`) |
| `service` | 61 | 16 |
| `receiver` | 68 | 19 |
| `provider` | 19 | 11 |
| الإجمالي | 1009 | 97 |

من بين 97 عنصرًا مصدَّرًا: 20 منها `enabled="false"` (14 alias أيقونة، وservice لتطبيق السيارة، وreceiver لـ ADM، وactivity وprovider لترحيل iOS، وreceiverان لنوايا UPI في الهند)؛ 24 تحمل `permission` / `readPermission`؛ 6 محمية بإذن `signature` معرَّف من WhatsApp؛ 56 مفعَّلة بلا أي إذن في manifest. أي فحص يتجاوز manifest موجود في الكود (القسم 9).

الأذونات المخصصة (found): `REGISTRATION`, `IDENTITY_VERIFICATION`, `MIGRATION_CONTENT_PROVIDER`, `BROADCAST`, `MAPS_RECEIVE`, `RECEIVE_ADM_MESSAGE`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` ذات `protectionLevel="signature"`. الإذن `com.whatsapp.sticker.READ` بلا `protectionLevel` (الافتراضي normal).

### 2.2 نقاط الدخول التي تعمل بلا حساب

| المكوّن | مصدَّر | Filter | سبب إمكانية الوصول قبل التسجيل |
|-----------|----------|--------|--------------------------------------|
| `com.whatsapp.Main` | نعم | `MAIN` / `LAUNCHER`, `MULTIWINDOW_LAUNCHER` | launcher وحيد؛ يوجّه بحسب حالة التسجيل (القسم 3) |
| `com.whatsapp.home.ui.HomeActivity` + aliases `AcceptInviteLinkActivityDeepLink`, `EventDeepLink`, `HomeActivity` | نعم | `chat.whatsapp.com`, `call.whatsapp.com`, `event.whatsapp.com`, `whatsapp://chat`, `call`, `event`, NFC `application/com.whatsapp.chat`, `.join` | لا فحص للتسجيل في `HomeActivity` نفسها (inferred: فئة أساسية تعيد التوجيه، لم تُحَل) |
| `DeepLinkActivity` عبر 4 aliases | alias نعم، الهدف لا | انظر القسم 4 | نقطة دخول الروابط |
| `com.whatsapp.deeplink.ui.TpalOAuthRedirectActivity` | نعم | `www.whatsapp.com/oauth_account_linking/login_redirect`, `/oauth_account_linking_mobile/login_redirect`, `whatsapp://third_party_oauth` | مستقبِل إعادة توجيه OAuth، `noHistory` |
| `com.whatsapp.cuif.ConsentActivity` | نعم | `whatsapp://consent` | يقرأ extras `flow_name`, `source`, `extra_params`, `device_id`, `app_id`؛ السلوك قبل التسجيل لم يُحَل |
| `com.whatsapp.Conversation` | نعم | `sms:` / `smsto:` `VIEW` / `SENDTO` | نقطة دخول معالج SMS في النظام |
| `com.whatsapp.accountsync.ProfileActivity`, `CallContactLandingActivity` | نعم | `content://com.android.contacts` MIME `vnd.com.whatsapp.profile`, `.voip.call`, `.video.call` | تكامل مع تطبيق جهات الاتصال؛ `CallContactLandingActivity` تحتاج `CALL_PHONE` |
| `com.whatsapp.registration.ui.RegistrationCompletedReceiver` | نعم، إذن `REGISTRATION` signature | `com.whatsapp.SMBRegistrationCompleted` | إشارة من التطبيق الشقيق |
| `com.whatsapp.registration.directmigration.MigrationProviderOrderedBroadcastReceiver`, `MigrationRequesterBroadcastReceiver` | نعم، إذن `REGISTRATION` signature | actions `initialMigrationInfoAction`, `recoveryTokenAction`, `setMigrationStateOnProviderSide`, `providerIsLoggedOutAction`, `providerAppMigrationSpaceNeededAction` | ترحيل بين التطبيق الاستهلاكي / SMB الشقيق وقت التسجيل |
| `MigrationContentProvider`, `DirectMigrationContentProvider` | نعم، `readPermission` `MIGRATION_CONTENT_PROVIDER` (signature) | authorities `com.whatsapp.provider.MigrationContentProvider`, `.DirectMigrationContentProvider` | الترحيل نفسه |
| `com.whatsapp.registration.app.verifyphone.SMSRetrieverAppInactiveReceiver` | نعم، إذن GMS `SEND` | `SMS_RETRIEVED` | نتيجة SMS Retriever عندما يكون التطبيق غير نشط |
| `com.whatsapp.registration.core.accounttransfer.AccountTransferReceiver` | نعم، بلا إذن | `com.google.android.gms.auth.START_ACCOUNT_EXPORT` | يتطلب الكود keyguard آمنًا وفحص ميزة قبل التنفيذ (found) |
| `com.whatsapp.phoneid.PhoneIdRequestReceiver` | نعم، بلا إذن | `com.facebook.GET_PHONE_ID` | يعيد معرّف الهاتف إلى مستدعٍ موثوق (القسم 9.1) |
| `com.whatsapp.otpmessage.otp.OtpRequestedReceiver`, `OtpIdentityHashRequestedReceiver` | نعم، بلا إذن | `com.whatsapp.otp.OTP_REQUESTED`, `ID_HASH_REQUESTED` | مصافحة OTP autofill لتطبيقات أخرى (القسم 9.3) |

### 2.3 مدخلات مصدَّرة أخرى (لا علاقة لها بالتسجيل، مذكورة للاكتمال)

| المجموعة | المكوّنات | الحماية |
|-------|------------|------|
| محتوى الأطراف الثالثة | `Conversation` (معالج `sms:`), `ExternalShareAlias` (`SEND`, `SEND_MULTIPLE`, `*/*`), `ContactPicker` (`PICK`, `CREATE_SHORTCUT`), `SetAsProfilePhoto` (`ATTACH_DATA`) | لا شيء في manifest |
| الملصقات | `SendStickerCommandActivity`, `AddThirdPartyStickerPackActivity` (+ alias), `StickerCommandProvider`, `WhitelistPackQueryContentProvider` | لا شيء في manifest |
| IPC لعائلة Meta | `FamilyAppsCredentialsProvider`, `FamilyAppsUserValuesProvider`, `WaAccountsCenterService` (`com.whatsapp.wfl.OPERATION`), `QuickSendsContactsProvider`, `OrbitSsoProvider`, `OrbitMessagesProvider`, `OrbitCompanionLinkActivity`, `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | فحوص المستدعي في الكود (القسم 9) |
| الأجهزة المصاحبة | `WearOsListenerService`, `GarminBindingServiceShim`, `IQGarminBindingService`, `TetheredService`, `WhatsAppCarAppService` (معطَّل) | لا شيء في manifest |
| تكامل Google | `BackupNowService`, `BackupStateService`, `OsMigrationAppDataService` (`BACKUP`), `DeferredRestoreBroadcastReceiver` (`BACKUP`), `WakeUpService` (إذن إشعار التعرض) | جزئيًا |

مصدَّر أيضًا: خطافات الإعدادات (`SettingsNotifications`, `SettingsDataUsageActivity`, إعداد widget لـ `AppAuthenticationActivity`)، وصفحات هبوط المكالمات (`SystemDialerCallLandingActivity`, `VoiceMessagingActivity`)، وreceivers المكتبات (`WidgetProvider`, `BootReceiver`, `AppUpdatedReceiver`, `ExternalMediaStateReceiver`, `WAFbnsPreloadReceiver`, `FirebaseInstanceIdReceiver`، ومدخلات work-manager وتثبيت profile خلف `BIND_JOB_SERVICE` / `DUMP`)، ومدخلات Pixel (`com.google.permission.besties.API`)، ومدخلات UPI الهندية وترحيل iOS المعطَّلة. `IdentityVerificationActivity` (NFC `application/com.whatsapp.identity.ui`) تتطلب إذن signature `IDENTITY_VERIFICATION`.

### 2.4 مكوّنات ما قبل التسجيل غير المصدَّرة (found)

تشمل الـ 806 activity غير المصدَّرة كل شاشات التسجيل (القسم 3.2) و`LoggedOutContactFormActivity` و`LoggedOutContactSuccessActivity` و`BanAppealActivity` و`WfacBanActivity` و`PrimaryLoginBackActivity` و`RemoveLoggedOutAccountsActivity`. ثلاثة alarm receivers غير مصدَّرة تدير تذكيرات التسجيل: `RegRetryVerificationReceiver` (`com.whatsapp.alarm.REGISTRATION_RETRY`, `SMS_RECEIVED_WHILE_INACTIVE`) و`OnboardingIncompleteReceiver` (`ONBOARDING_INCOMPLETE`) و`EnterPhoneNumberNotificationReceiver` (`ENTER_PHONE_NUMBER`). providers غير المصدَّرة: `FileProvider`, `SecureFileProvider`, `MediaProvider`, `AccountSwitchingContentProvider`, `RestartAppContentProvider`, `InstrumentationProvider` (جميعها مع `grantUriPermissions` حيث يُعلَن).

### 2.5 أعلام التطبيق وسياسة الشبكة (found)

| العنصر | القيمة |
|------|-------|
| `debuggable` | `false` |
| `allowBackup` | `true`، لكن `fullBackupContent` و`dataExtractionRules` (النسخ الاحتياطي السحابي ونقل الجهاز) يستثنيان كل النطاقات؛ مدخل النقل بين المنصات لـ iOS يحمل `bundleId` / `teamId` فقط |
| `networkSecurityConfig` الأساسي | `cleartextTrafficPermitted="true"`؛ trust anchors هي `system` و`user` (`overridePins="true"` لـ CA المستخدم) |
| Cleartext محظور | `whatsapp.com`, `whatsapp.net`, `wa.me`, `wl.co` (22 pin من نوع SHA-256، بلا انتهاء)، `facebook.com`, `instagram.com`, `jiomart.com`, `hatch-api.meta.ai` |
| نطاق الـ pin | مجموعة الـ pins موضوعة على domain-config لـ `whatsapp.com` / `whatsapp.net` / `wa.me` / `wl.co`؛ وهي ترث trust anchors الأساسية، فلا تنطبق الـ pins على CA المثبَّتة من المستخدم (سلوك المنصة لـ `overridePins`) |
| مضيفون خارج أي domain-config | `gstatic.com` (مفتاح reCAPTCHA) يقع تحت الإعداد الأساسي (cleartext مسموح؛ الكود يستخدم `https://`) |

---

## 3. شاشات ما قبل التسجيل وتوجيه الحالة

### 3.1 توجيه `Main` بحسب حالة التسجيل (found, smali لـ `Main.A5W`)

يقرأ `Main` حالة التسجيل (`C0Gk.A02()`) وكائن الحساب الذاتي المخزَّن. وسوم السجل مراسٍ ثابتة.

| الحالة | وسم السجل | الوجهة |
|------:|---------|-------------|
| 2 | `main/me/regname`, `main/no-me/regname` | خطوة إدخال الاسم في التسجيل (`RegisterName`) |
| 21 | `main/me/wfac ban` | شاشة حظر WFAC عبر `HBC.A00` (`WfacBanActivity`) |
| 24, 38 | `main/me/backup otp` | خطوة OTP / التحقق من النسخة الاحتياطية |
| 41 | `main/me/consent age ban` | شاشة موافقة العمر |
| 45 | `main/me/paa onboarding`, `main/no-me/paa onboarding` | onboarding للحساب التابع / المُدار |
| 50 | `main/me/logged out, going to PrimaryLoginBackActivity` | شاشة العودة لتسجيل الدخول |
| 51 | `main/me/pending login-back verification` | التحقق من العودة لتسجيل الدخول (extra `login_back_verification`) |
| 56 | `main/me/username`, `main/no-me/username` | خطوة اسم المستخدم |
| any | `main/no-me/first-factor password` | فرع كلمة مرور العامل الأول (بلا كائن حساب ذاتي) |
| any | `main/invalid/registration state=` | سجل الحالة غير الصالحة |

تبني الطريقة نفسها intents (found) لـ `VerifyPhoneNumber` و`DeviceConfirmationRegistrationActivity` و`ExportMigrationDataExportedActivity` و`BanAppealActivity` (extra `launch_source`) و`DeleteAccountConfirmation` ومدخل `RegisterPhone` الافتراضي. تفضّل المتابعةَ عند `RegisterPhone` قيمةُ التفضيل `logged_out_phone_fallback_pending` (`main/me/logged-out phone fallback resume`). يُفحص IDV token مُصدَر (`minted_idv_token`, `minted_idvtoken_expiry_time_secs`)، والمنتهي أو الفارغ يعيد ضبط مسار المعالجة. أيّ الحالات الرقمية يقابل أي خطوة في الخادم هو inferred من أسماء الوسوم.

### 3.2 شاشات التسجيل (found, كلها غير مصدَّرة)

| المجموعة | Activities (`com.whatsapp.registration.app.*` ما لم يُذكر خلاف ذلك) |
|-------|--------------------------------------------------------------|
| الدخول | `EULA` (الوسم `eula_screen` / `eula_with_language_selector`), `phonenumberentry.RegisterPhone`, `RegisterAsDependentActivity`, `RegTabletIntroActivity`, `RegTabletChooseOptionActivity` |
| الأذونات | `RegPermissionsExplainerActivity`, `RegNotificationPermissionPrimerActivity` |
| التحقق | `verifyphone.VerifyPhoneNumber`, `sendsmstowa.SendSmsToWa`, `ManualSmsRequest`, `flashcall.PrimaryFlashCallEducationScreen`, `email.RegisterEmail`, `email.VerifyEmail`, `email.EmailEducationScreen`, `email.UnverifiedEmailSetupRegUpsellActivity`, `email.ConfirmEmailSetupRegUpsellActivity`, `backuptoken.BackupTokenEducationScreen`, `VerifyTwoFactorAuth` |
| حماية الحساب | `accountdefence.DeviceConfirmationRegistrationActivity`, `accountdefence.ui.OldDeviceSecureAccountActivity`, `OldDeviceSecureAccount2FaActivity`, `OldDeviceMoveAccountNoticeActivity` |
| الحجب | `parole.CustomRegistrationBlockActivity`, `downgrade.DowngradeFrictionActivity`, `com.whatsapp.userban.ui.BanAppealActivity` |
| الترحيل | `directmigration.RestoreFromConsumerDatabaseActivity`, `MigrationStartTransferActivity`, `RequestPermissionFromSisterAppActivity`, `com.whatsapp.migration.transfer.ui.*` |
| الاسم / تغيير الرقم | `RegisterName`, `phonenumberentry.ChangeNumber*` |
| وضع الجهاز المصاحب | `com.whatsapp.companionmode.registration.ui.RegisterAsCompanionActivity`, `RegisterAsCompanionEnterNumberActivity`, `RegisterAsCompanionLinkCodeActivity`, `CompanionBootstrapActivity`, `CompanionPostLogoutActivity` |
| تسجيل الخروج | `logout.ui.PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`, `loginfailure.LogoutMessageActivity` |
| الدعم | `inappsupport.ui.app.LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity` |

### 3.3 منتقيات اللغة والبلد (found)

| العنصر | التفصيل |
|------|--------|
| اللغة | `LanguageSelectorBottomSheet` تُفتح من `EULA` (حدث المسار `language_selected`؛ المقاييس `language_selector_clicked_count`, `language_selector_time_spent` في `K49`)؛ `FullScreenLanguageSelectorActivity` في جهة الإعدادات غير مصدَّرة |
| أسماء البلدان | 63 جدولًا دون اتصال `assets/country_names_<lang>.tsv` (`ISO code<TAB>name`)؛ لم يُعثر على بحث شبكي للمنتقي |
| تعبئة الرقم مسبقًا | تستخدم `RegisterPhone` تلميحات أرقام الهاتف من Google (`RegisterPhone/launchGooglePNHints`) ومسار "ما رقمي" عبر SIM الذي يحتاج إذن هاتف؛ extras في EULA: `RegisterPhone.phone_number`, `country_code`, `auto_submit_after_prefill`, `one_click_from_eula` |
| الروابط القانونية في `EULA` | `https://www.whatsapp.com/legal/terms-of-service` أو `/terms`، `privacy-policy` أو `privacy-policies` (المتغير بحسب الإعداد) |

---

## 4. الروابط العميقة وروابط الويب

### 4.1 Aliases الدخول (found)

| Alias | الهدف | Filters |
|-------|--------|---------|
| `TextAndDirectChatDeepLink` | `DeepLinkActivity` | `http(s)://api.whatsapp.com`, `wa.me`; مسارات `https://[www.]whatsapp.com` هي `/channel`, `/channel_status`, `/updates`, `/aimediainput`, `/aivoice`, `/dl`, `/privacy/disclosure`, `/wamo/status/link-{instagram,facebook}-in-house-ad`؛ المخططات `whatsapp`, `whatsapp-smb`, `whatsapp-consumer`, `whatsapp-sheet` (قوائم مضيفين، أكثر من 100 مضيف) |
| `VerifyOtpDeepLink` | `DeepLinkActivity` | `http(s)://b.whatsapp.com`, `http(s)://v.whatsapp.com` |
| `FoaDeeplinkActivityAliasUniversalLink`, `FoaDeeplinkActivityAliasAppScheme` | `DeepLinkActivity` | لا filter في هذا manifest (معلَنة لمكتبة الروابط العميقة لعائلة Meta) |
| `AcceptInviteLinkActivityDeepLink` | `HomeActivity` | `chat.whatsapp.com` |

`DeepLinkActivity` نفسها غير مصدَّرة؛ كل مسار خارجي يمر عبر alias. جميع filters ذات `autoVerify="true"` تغطي مضيفي https فقط. عدة filters على `whatsapp` و`whatsapp-consumer` و`whatsapp-smb` تحمل `VIEW` والـ action المخصص `com.whatsapp.DEEP_LINK_REDIRECT` معًا، فيستجيب alias لـ intent صريح بهذا الـ action من أي تطبيق (found: شكل filter).

### 4.2 الروابط التي تتعامل مع حالة ما قبل التسجيل (found)

| الرابط | مرساة المحلل | السلوك |
|------|---------------|-----------|
| `https://[www.]whatsapp.com/dl?wsu=<6 digits>` | `IJB.A01`: المسار `dl`، والاستعلام `wsu` المطابق لـ `\d{6}`، السجل `DeepLinkHelper/parseUri/web signup uri`، الرمز **193** | تسليم التسجيل من الويب؛ القيمة تُتحقق بـ regex فقط في جهة العميل |
| `whatsapp://s/signup` (مقطع مسار وحيد `signup`) | `IJB.A01` الرمز **216**، مقيَّد بـ ab-props **25005** أو **25801**؛ المعالج `handleInAppSignupDeepLink` يتطلب المخطط `whatsapp` والاستعلام `s` | تسجيل داخل التطبيق؛ يسجّل عبر `ApiSignupFlowLogger` مع `signup_id` (اقتران المضيف `s` inferred من manifest) |
| `https://v.whatsapp.com/<code>`, `https://b.whatsapp.com/<code>` (آخر مقطع مسار) و`whatsapp://r?c=<code>` | فرع التسجيل في `DeepLinkActivity`، السجل `DeepLinkActivity/Registration deeplink/registration state:` | رابط OTP عبر البريد الإلكتروني. الحالة 1 تفتح `RegisterPhone` مع extra `tapped_sms_link`؛ الحالة 2 تفتح `VerifyEmail` مع `email_otp` و`entrypoint` و`session_id` و`challenge_flow=false` وتبلّغ `email_otp_deeplink_redirect_to_register_name`؛ الحالات الأخرى تعيد التوجيه إلى الإعدادات (`settings_verification_email_address_verified`, inferred). يُمرَّر الرمز كـ extra؛ والتحقق في جهة الخادم (unknown) |
| `whatsapp://code-linking?auth=<nonce>` | الرمز **77**، المعالج `maybeStartCodeLinkingFlow`، ab-prop **4560** (`ENABLE_CODE_LINKING_DEEP_LINK_CODE`)، التفضيل `adl_deep_link_nonce` بنافذة 300000 (الوحدة inferred بالميلي ثانية) | مسار رمز الجهاز المرتبط؛ يُتخطى عندما يكون العلم مطفأً أو يكون nonce أقدم من النافذة |
| `whatsapp://help/<segment>` | الرمز **62**؛ فرع عدم الاتصال يسجّل `DeepLinkActivity/help/no-connectivity` | مقال مساعدة |
| `whatsapp://support` | الرمز **30** (مستخرج من المحلل؛ المعالج يسجّل `about/no-connectivity`) | شاشة الدعم / حول، تحتاج اتصالًا |

### 4.3 بوابة ما قبل التسجيل

| المرساة | النتيجة | المستوى |
|--------|---------|------|
| `DeepLinkActivity/deeplink not allowed before registration/` والسبب `not_allowed_before_registration` | موجودان؛ تقابل enum الأسباب القيمة 0 بهذه السلسلة؛ لم يُعزل منتِج السبب 0 للروابط العادية | found (السلاسل)، unknown (المنتِج) |
| معالجات لكل رمز | كل معالج يفحص حالة التسجيل بنفسه (استدعاءات `C0Gk.A0C()` / `A02()` في أجسام switch) | found |
| قائمة السماح لرموز تسجيل الخروج | لم تُحَل من جديد: `C02T` منفِّذ تسلسلي في هذا الـ build و`C02U` فئة ثوابت صحيحة مشتركة، فلا تقابل أسماء الفئات السابقة | unknown |
| نتيجة `JXK` (`code`, `source`, السبب) تبنيها `IJB` و`IJC` و`IJD` و`IJE` | مخرج المحلل تستهلكه `DeepLinkActivity.A0w` | found |

تحليل المحتوى (دردشة أو قناة أو دليل) ما زال يحتاج حسابًا: معالجات دعوة المجموعة و`wa.me/<phone>` تستخدم الجلسة المصادَق عليها (inferred من أسماء المعالجات؛ لم يُتتبع من البداية إلى النهاية هنا).

---

## 5. المضيفون ونقاط الاتصال دون حساب

### 5.1 HTTP التسجيل (found)

16 مسارًا، مفتاح XOR هو 18 في `AbstractC45307Jps`، كلها فُكّت من جديد في 2.26.41.6: `/v2/exist`, `/v2/code`, `/v2/register`, `/v2/security`, `/v2/challenge`, `/v2/passkey_auth`, `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop`, `/v2/device_logout_send`, `/v2/device_logout_fetch`, `/v2/wfs`. ثابتان آخران يُفكّان إلى `ENC` و`H` (الاستخدام unknown). قوائم الحقول للمجموعة الأولى في [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) القسم 3.1. المضيف الأساسي `v.whatsapp.net` هو الاسم في الجدول المضمَّن (5.4)؛ الكود الذي يضم المضيف والمسار موجود في حزم wamsys / Kotlin ولم يُقرأ هنا (inferred).

يختار المحدِّد `K49.A0b` حزمة Kotlin (`KotlinRegistrationBridge`) أو حزمة `wamsys` الأصلية؛ ويجب أن تُهيَّأ الحزمة الأصلية أولًا (`ensureWamsysForRegBootstrapped`، الخطأ `FAIL_TO_INITIALIZE_WAMSYS`).

### 5.2 نقاط HTTPS أخرى (literal found، المصادقة كما هو مذكور)

| المضيف / URL | الطريقة | المصادقة في الكود | المستدعي | بلا حساب؟ |
|------------|--------|--------------|--------|---------------|
| `https://www.whatsapp.com/contact/noclient/verification/` | multipart POST | لا شيء | `C47328KmN` الحالة 0 (نموذج الدعم) | نعم |
| `https://graph.<pref_graphql_domain>/graphql` (الافتراضي `graph.whatsapp.com`) | POST JSON | client token للتطبيق مضمَّن في الكود داخل الجسم `access_token` | `AbstractC40195HfH` وفئاتها الفرعية | نعم (حالة الحظر / الاستئناف) |
| `https://crashlogs.whatsapp.net/wa_clb_data`, `/wa_fls_upload_check`, `/wa_profilo_data`, `/whatson_logs_upload` | POST | token التطبيق المضمَّن (رفع السجلات يضيف `access_token` و`type` و`from_jid` و`ticket_id` و`build_id`) | `C10V`, `C05640An`, `ExceptionsUploadService`, `ProfiloUploadService`, `CM8` | يعمل دون تسجيل دخول؛ محتوى `from_jid` عند تسجيل الخروج unknown |
| `https://acs.whatsapp.com/graphql` | POST | ACS token أو إعداد OHAI (بلا JID) | `C31991Nz`, `R5t` | نعم (طلبات مجهَّلة الهوية) |
| `https://static.whatsapp.net/wa/static/{downloadable,network_resource,payments/*}`, `/sticker?...`, `/payments/background` | GET | لا شيء | محمِّلات أصول الواجهة | نعم |
| `https://mmg.whatsapp.net/proxygen/health`, الأساس `https://mmg.whatsapp.net` (الإعداد 22436) | GET | لا شيء | الوسائط / الفحص الصحي | نعم |
| `https://www.gstatic.com/recaptcha/verify_key/orcas/prod/android/verify_key.txt` | GET | لا شيء | `C44464JbH` (تستخدمها `RequestCodeRepository` و`VerifyCodeRepository` و`VerifyPhoneNumber`) | نعم (captcha التسجيل) |
| `https://www.whatsapp.com/compliance/xfac/mint` | POST form | لم يُرَ شيء | `CommonRemediationApi` (معالجة العمر، `minted_idv_token`) | قابل للوصول قبل التسجيل: unknown |
| `https://www.whatsapp.com/v1/auth/canonical/token/` | POST form `nonce`, `user_id`, `device_id`, `client_pub_key` | لا شيء | `CanonicalUserCompanionDeviceManager` | مسار الجهاز المصاحب / الحساب المرتبط، ليس ما قبل التسجيل الخالص |
| `https://api.whatsapp.net/support/add_bug_attachment` | multipart POST | `Authorization: Bearer <token>` | `PostBugAttachmentUploader` (تقرير الأعطال داخل التطبيق) | لا (مرتبط بـ token) |
| `https://graph.whatsapp.net/v2.2/maps_configs?...&access_token=` (الافتراضي `graph.facebook.com`) | GET | token التطبيق في URL | إعداد الخرائط `N6n` | المحفِّز ليس ما قبل التسجيل (inferred) |
| `https://api.whatsapp.net/calendar/integrations/` | طلب | الجلسة | ميزة التقويم | لا |

Tokens المضمَّنة: يوجد شكلان بنمط Facebook، `WA|<app_id>|<secret>` في الافتراضي لعميل Graph و`<app_id>|<secret>` في رافع السجلات. لا تُعاد القيم هنا. فهي تعرّف التطبيق لا المستخدم.

### 5.3 تهيئة DNS والاتصال (found)

| العنصر | التفصيل |
|------|--------|
| الجدول المضمَّن `AbstractC47101wK` | المضيف إلى قائمة IPv4 / IPv6 لـ 18 اسمًا: `e1..e16` و`g` و`v` تحت `.whatsapp.net` (لكل منها نظير بنقطة لاحقة)؛ لا حاجة إلى شبكة |
| `C36881dC` (DnsCache) | ترتيب الاستخدام: المحلل الأساسي، محلل MNS DNS (`DnsCache/resolveViaMnsDns`، تُختبر السلسلة `v.whatsapp.net` في ذلك الفرع)، المحلل الثانوي، الجدول المضمَّن؛ تفشل عمليات البحث المضمَّنة بالرسالة `no hardcoded ips found for <host>` عندما لا يحوي الجدول مدخلًا وتُتخطى بالرسالة `hardcoded dns resolver disabled` عندما يكون بت الخيار مطفأً |
| مضيف الدردشة | مدخل `g.whatsapp.net` يُقرأ مباشرة (`C36881dC.A01`) |

صيغة سلك محلل MNS موجودة في الكود الأصلي: unknown.

### 5.4 مسارات REST غير الموجودة (found negative)

لم يُعثر على REST غير مصادَق عليه لجلب gating أو الإعدادات (`/gk`, `/props`, `/config`). إعداد التجارب قبل تسجيل الدخول يصل عبر HTTP التسجيل: `/v2/reg_onboard_abprop` (`K49.checkPreChatdABProps`) يرسل `ab_hash` من التفضيل `pref_pre_chatd_ab_hash`، و`ab_exposure`/`ab_key` من `pref_pre_chatd_ab_key`، إضافة إلى حقول الجهاز في القسم 7.

---

## 6. نموذج الدعم عند تسجيل الخروج (found)

`LoggedOutContactFormActivity` (غير مصدَّرة) هي مسار الدعم الوحيد بلا حساب كليًا في هذا الإصدار.

| Intent extra (البادئة `com.whatsapp.inappsupport.ui.app.LoggedOutContactFormActivity.`) | الاستخدام |
|------|-----|
| `PhoneNumber`, `CountryCode` | رقم مُعبَّأ مسبقًا؛ سلسلة فارغة عند الغياب |
| `From` | وسم نقطة الدخول |
| `ServerStatus` | سلسلة حالة يمررها المستدعي (inferred: حالة خادم التسجيل) |
| `IsRegistrationVerification` | منطقي؛ عند النجاح يُجرى استدعاء لاحق (الهدف لم يُحَل) |
| `SupportUserContext` (`K8W`) | نقطة الدخول ومعرّفات CMS (`Entry point`, `Cms ids`) |

حقول النموذج: البريد الإلكتروني (شرائح اقتراح `@gmail.com`, `@hotmail.com`, `@icloud.com`, `@outlook.com`, `@yahoo.com`)، الوصف، حتى 3 لقطات شاشة تُنتقى من `MediaStore`.

الإرسال (`C47328KmN` الحالة 0، الوسم `logged_out_contact_form`، الوسيط الأخير 20 ذو معنى غير محلول):

| الجزء | الاسم | المحتوى |
|------|------|---------|
| field | `email` | البريد المكتوب |
| field | `message` | الوصف |
| field | `platform` | القيمة الحرفية `ANDROID` |
| field | `phone_number` | الرقم المكتوب |
| field | `debug_info` | نص يبنيه `C10V.A08` (القسم 7.3) |
| file | `log_data` | `logs.tar.gz` لسجل العميل (يُدوَّر ويُضغط أولًا) |
| files | `attachment_<n>` | لقطات شاشة يُعاد ترميزها إلى JPEG بجودة 80 وحد 2048 px، وتُحفظ فقط عندما يكون حجمها 10 MiB أو أقل |
| extra | `skip_saga_copy=true`, `saga_copy=true`, `pn` | `pn` = رمز البلد + الرقم عندما يكون كلاهما غير فارغ |

النتيجة: تذهب حالة HTTP إلى callback للنتيجة (`C46422KQg`)؛ ويظهر الفشل بصيغة `Server error: <status>` أو `Network error`؛ والنجاح يفتح `LoggedOutContactSuccessActivity` (extra `...Email`). لم يُقرأ التقابل الدقيق بين الحالة والنجاح. الاستدعاء POST عبر HTTPS عادي بواسطة عميل HTTP للتطبيق؛ وهو ليس استدعاء GraphQL. يُولَّد `anid` عشوائي من نوع UUID (7.1) لكل إرسال.

---

## 7. المعرّفات المرسلة قبل تسجيل الدخول

### 7.1 جدول المعرّفات

| المعرّف | أين | المصدر | ملاحظات | المستوى |
|------------|-------|--------|-------|------|
| `fdid` | `/v2/pre_pn_client_log`، طلبات التسجيل | `C38141gV.Ax2()`: `UUID.randomUUID()` عشوائي يُخزَّن كـ `phoneid_id` + `phoneid_timestamp` في prefs | يبقى عبر محاولات التسجيل؛ المعرّف نفسه تعيده `PhoneIdRequestReceiver` | found |
| `fid` | طلبات التسجيل | `C47381wu.Ax2()`: prefs `phoneyid_id` + `phoneyid_timestamp`، يُرسل بصيغة `<id>|<timestamp>` فقط عند وجودهما | معرّف عائلة ثانوي؛ منتِج القيمة لم يُتتبع | found (الاستخدام inferred) |
| `anid` | نموذج الدعم | `C11J.A01()`: `UUID.randomUUID()` لكل استدعاء، ويُسجَّل أيضًا كحدث WAM | معرّف عشوائي لكل إرسال | found |
| `advertising_id` / `android_advertising_id` | `/v2/exist`, `/v2/code`, `/v2/register`؛ سجل المسار | معرّف Google الإعلاني عند توفره | مستثنى من سلسلة سجل التصحيح الخاصة بمسجِّل المسار | found |
| `authkey`, `e_ident`, `e_keytype`, `e_regid`, `e_skey_id`, `e_skey_val`, `e_skey_sig`, `e_pq_last_resort_{id,val,sig}` | طلبات التسجيل | `C45446JsB`: مفتاح Noise الساكن للعميل وحزمة مفاتيح Signal | مادة عامة | found |
| `gpia` | طلبات التسجيل | Play Integrity standard token، مقيَّد بعلم | انظر [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) | found |
| `ab_key`, `ab_hash`, `ab_exposure` | `/v2/exist`, `/v2/pre_pn_client_log`, `/v2/reg_onboard_abprop` | prefs `pref_pre_chatd_ab_key` / `pref_pre_chatd_ab_hash` | شريحة التجربة | found |
| `device_country` | سجل المسار | `TelephonyManager.getSimCountryIso()` بأحرف كبيرة، و`ZZ` عند الغياب | | found |
| `access_token` (التطبيق) | Graph، رفع السجلات | ثابت مضمَّن | هوية التطبيق لا المستخدم | found |
| `request_token` / `token` | حالة الحظر / الاستئناف | التفضيل `wfac_ban_status_token` (الحالة) وtoken الاستئناف المخزَّن | معتم، يصدره الخادم وقت الحظر ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md)) | found |
| `from_jid` | رفع السجلات | JID الحساب عند وجوده | المحتوى عند تسجيل الخروج unknown | found (الحقل)، unknown (القيمة) |
| `registration_trace_id`, `request_id`, `nonce_encryption_key` | mutation استرداد الحساب | `AccountRecoveryManager` (القسم 8.2) | | found |

### 7.2 سمات الجهاز في طلبات التسجيل (found, مساعدات `K49` هي `A0O` و`A0Q` و`A0R` و`A0U` و`A0W` و`A0X`)

`network_radio_type`, `simnum` (`0` / `1`), `hasinrc` (الملف `rc2` موجود), `pid` (معرّف العملية), `device_ram`, `sim_type`, `airplane_mode_type`, `cellular_strength` (مستوى الإشارة، الافتراضي `5`), `roaming_type`, `preloads_app_manager_id`, `preloads_attribution`, `entrypoint` (`create_paa` أو `suma`), `tos_version` (`5`), `old_phone_number` (مسار تغيير الرقم). مفاتيح مقاييس القياس عن بُعد في الفئة نفسها (found، استخدامها في الطلب غير مؤكد): `network_operator_name`, `sim_operator_name`, `sim_state`, `read_phone_permission_granted`, `mistyped`, `c2dm_reg_id` (يُقرأ من prefs).

### 7.3 محتوى سجل المسار (found, `PrePnBaseFunnelLogger$sendPrePNFunnelLog$1`)

قبل وجود رقم يرسل العميل: `current_screen` و`previous_screen` (التفضيل `pref_previous_screen`، الافتراضي `unknown`) و`action_taken` و`event_name` و`access_funnel_type=wa` و`app_campaign_download_source` و`is_add_account_flow` و`android_advertising_id` و`ab_key` و`device_country` و`fdid` وسمات الجهاز أعلاه و`entrypoint`. في مسارات إضافة حساب أو بديل تسجيل الخروج يرسل أيضًا `primary_logout_session_id` و`number_of_accounts`. يُتخطى الإرسال عندما يفشل تهيئة wamsys.

### 7.4 `debug_info` في نموذج الدعم (found, `C10V.A08`, وسيط JID يكون `null` في هذا الاستدعاء)

التسميات المكتوبة في النص: `useragent`, `Socket Conn`, `Connection`, `Server`, `Datacenter`, `Sim`, `Free Space Built-In` / `Removable`, `Network metered` / `restricted`, `Data roaming`, `Tel roaming`, `Diagnostic Codes`, `ABprops hash state`, `Screen reader`, `Fingerprint eligible`، حقول حالة النسخ الاحتياطي، `Is Companion`, `Number of Accounts`, `Mobile Build Id`, `wfl_state`, `isMetaVerified`, `Mistyped` / `Mistyped Last6` / `L Distance` (مقارنة الرقم المكتوب برقم SIM)، إضافة إلى معرّفات آخر مكالمة عندما يوجد سجل مكالمات. التسمية `entity id` لا تُكتب إلا عند تمرير JID، وهو غير ممرَّر هنا.

---

## 8. استدعاءات Graph وMEX بلا جلسة مستخدم

### 8.1 طلبات Graph بـ token التطبيق (found)

الفئة الأساسية `AbstractC40195HfH.CND` تبني `https://graph.<A0f()>/graphql` (`A0f()` = التفضيل `pref_graphql_domain`، الافتراضي `whatsapp.com`؛ الفئات الفرعية `GEV` و`GEX` و`GET` و`GEW` و`GEU` ومفتاح عائلة حسابات Meta `C45F` تتحول إلى `facebook.com` / `instagram.com`). جسم JSON: متغيرات العملية، `access_token` (token مضمَّن عندما لا تمرر الفئة الفرعية شيئًا)، `doc_id`، `lang`، `Content-Type`. يُضاف الترويس `X-FB-Request-Analytics-Tags` عند غيابه.

| الفئة | doc_id | المتغيرات | الغرض |
|-------|-------:|-----------|---------|
| `C37604GYf` | **4276154569100535** | `app_id` (`dev.app.id`)، `request_token` | استطلاع حالة حظر WFAC (`WfacBanRepository/fetchBanStatus`، token من التفضيل `wfac_ban_status_token`) |
| `C37409GLo` | **27883644401256929** أو **4276154569100535** (منطقي) | نفسها | حالة الحظر عبر `HG2.A01` |
| `C37414GLt` | **38509456535312323** أو **5473316762755318** (منطقي) | `app_id`, `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}`؛ النص الصريح `{token, debug_info, description}`، السياق `WA_INAPP_BAN_APPEALS` | تقديم استئناف الحظر (`C40191HfD`)؛ التفاصيل في [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) القسم 10 |
| `C37408GLn` | **5803265299734043** | `app_id`, `client_pub_key` | الغرض unknown (يرسل مفتاحًا عامًا للعميل)؛ المستدعي لم يُتتبع |
| `C37601GYc`, `GYd`, `GYe` | `GYd` **25453433540999208**, `GYe` **25974020015520396** (`GYc` لا تحمل معرّفًا في فئتها) | `caller_name` `fx_waffle_contextual_pause_account_match`, `wa_waffle_certs`, `fx_waffle_foa_unpause` | مساعدات ربط حسابات Meta |
| `C37605GYg`, `GYh`, `GYi` | **26573478745654327**, **26742313962085910**, **27503298369362501**, **28331348373116386**, **25840634418966704** | الترويس `IG-Set-Waffle-Graphql-Access-Token`، المفتاح `ACCESS_TOKEN` | ربط حسابات Facebook / Instagram؛ يلزم token حساب مرتبط (inferred من أسماء الترويس والمفتاح) |
| `C37413GLs` | **7236799486398397** | `batches`, `device_model`, `device_os`, `device_os_version`, `event_time`, `is_employee`, `primary_locale` | دفعات أحداث العميل (inferred من أسماء المتغيرات) |

الـ doc_id 6960707423955525 (معرّف mutation استئناف قديم أُبلغ عنه في builds أقدم) لا يرد في 2.26.41.6. أسماء عمليات طلبات الاستئناف والحالة لا تحملها هذه الفئات (unknown).

الفرق عن [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) القسم 10: بالنسبة لـ `C37414GLt` و`C37409GLo` و`C37604GYf` يكون المضيف `graph.<pref_graphql_domain>` (الافتراضي `graph.whatsapp.com`)؛ والفئات الفرعية المذكورة أعلاه وحدها تتجاوزه إلى `facebook.com`.

### 8.2 عمليات MEX ذات موقع استدعاء وقت التسجيل أو عند تسجيل الخروج (found, المخطط `whatsapp-android-mex`)

doc_ids من `assets/whatsapp-android-mex_client_persist_ids.json` (وملفي `www` / `wamo` حيث يُذكر).

| العملية | doc_id | موقع الاستدعاء |
|-----------|-------:|-----------|
| `GetAutoConfConfidenceChallenge` | 25578301865133112 | `C40175Het`, `C40196HfI` (ping ثقة autoconf) |
| `ValidateVerifierConfidence` | 25879669248324812 | `C40196HfI`, `C40197HfJ` |
| `FetchReachoutTimelockQuery` | 25627902213558773 | `RunnableC23952AUh` |
| `RemoveAccountReachoutTimelock` | 25040013452293167 | لم يُتتبع |
| `UserCountryCodeGet` | 25292528387076991 | `MexUserCountryCodeRepository` |
| `MobileConfigFetchQuery` | 29248978061376279 | لم يُتتبع |
| `SubmitAge`, `GetAgeExperience`, `SetAgeExperienceMutation` | 26049558371296621, 26567868986241476, 26051006311231325 | مسارات العمر |
| `TosSetResult` | 25225843213776555 | قبول الشروط |
| `GetWaOldResponse` | 25784374561179853 | التحقق عبر الهاتف القديم |
| `WWWTriggerAcountRecovery` | 24896267680055094 | `AccountRecoveryManager` (المتغيرات `nonce_encryption_key` و`use_case` و`registration_trace_id` و`request_id`) |
| `WWWCreateUser`, `WWWDeleteUser`, `WWWGetCertificates` | 8548056818544135, 7989555047767245, 25094190163544446 | ربط الحسابات |
| `OhaiKeyConfigQuery` | 25069818679280758 | `N5I` (تهيئة ACS / OHAI) |
| `CreateEnforcementAppeal` | 26933630359642347 | عميل إنفاذ القنوات |
| `NewsletterCreateReportAppeal` (mex), `CreateGroupSuspensionAppealMutation` (www), `WamoReportPromoAppealV2Mutation` (wamo) | 27792557363683798, 25646047815072526, 26867425009592691 | عمليات استئناف (مرتبطة بحساب؛ موجودة في assets) |

يُرسل MEX كـ IQ `xmlns="w:mex"` مع `<query query_id=...>` (`C19370nI`) عبر اتصال الدردشة (`WAChatdGraphQLClient`). هل تعمل هذه العمليات على جلسة ما قبل الحساب غير مثبت: انظر 8.3.

### 8.3 اتصال الدردشة بلا JID (found)

يقرأ `ConnectionThread.connect` (`HandlerThreadC12340b0`) الـ JID الذاتي؛ وعندما يكون فارغًا يتابع فقط إذا كان علم تسجيل الجهاز المصاحب (`C06830Gm.A02()`) صحيحًا، وإلا يقرأ مصدر JID ثانيًا (`Ash()`)، وإن كان فارغًا أيضًا يسجّل `ConnectionThread/connect/ignored/jid null and not in companion reg` ويعود. لذلك لا يستخدم تسجيل الهاتف الأساسي اتصال دردشة بـ JID فارغ (متسق مع [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) القسم 6.4). معنى المصدر الثاني inferred (JID مخزَّن أو قيد التسجيل، لم يُحَل). أي جلسة تحمل استدعاءات MEX وقت التسجيل في 8.2 هو unknown.

### 8.4 الطلبات مجهَّلة الهوية (found)

`PandoGraphQLRequest.requireAcsToken()` و`requireOhaiConfig()` تقرؤهما `C6GN`؛ الطلب الموسوم `@deidentified` بلا ACS token أو إعداد OHAI يرمي استثناءً (`Request was marked with @deidentified, but no ... was provided`). حقول `AcsOhaiConfig`: اسم المشروع، doc id، `graphQlUrl=https://acs.whatsapp.com/graphql`، السطح، `tokenTtlSeconds`، `acsTokenMaxRedeemCount`. أي العمليات تحمل العلم مرمَّز في assets `*_pando_flatbuffer_data.bin`: unknown.

---

## 9. أسطح IPC المصدَّرة مع فحوص على مستوى الكود

جميع المدخلات مصدَّرة بلا إذن في manifest ما لم يُذكر خلاف ذلك. يسرد هذا القسم عناصر التحكم الموجودة في الكود، لا حكمًا على قوتها.

### 9.1 `PhoneIdRequestReceiver` (`com.facebook.GET_PHONE_ID`)

بث مرتَّب. يقرأ المستقبِل extra من نوع `PendingIntent` باسم `auth` من extras النتيجة ويأخذ `getCreatorPackage()`. تُعتبر الحزمة موثوقة عندما يكون hash شهادة توقيعها في مجموعة سماح مضمَّنة (`AbstractC28130CKz.A04`، SHA-1 لشهادات التوقيع، القيم لا تُعاد؛ تُستخدم مجموعة SHA-256 ثانية في `CHA.A02`). المستدعي الموثوق يحصل على معرّف الهاتف وطابعه الزمني كنتيجة البث (`setResult(-1, id, {timestamp})`)؛ ومسار بديل يعيد المعرّف الثانوي عندما يسمح العلم **3651**. تدفق التحكم المفكَّك حول متغير الثقة جزئي، لذا الأسبقية الدقيقة inferred.

### 9.2 Providers عائلة التطبيقات (found)

| المكوّن | عناصر التحكم الموجودة |
|-----------|----------------|
| `FamilyAppsCredentialsProvider` | `getCallingPackage()`؛ خريطة معالجات لكل selection؛ يُحَل UID المستدعي إلى شهادة ويُفحص مقابل المجموعة الموثوقة للمعالج (`C45775Jyk.A01`)؛ أهلية مدير الربط (`WfalManager.A00`)؛ feature flags؛ يجب أن تكون حالة الربط ضمن المجموعة المؤهلة للمعالج؛ يعيد cursor من 3 أعمدة (إثبات المصادقة، الحزمة، TTL) من prefs `pref_foa_nta_ipc_bundle_auth_proof` و`pref_foa_nta_ipc_bundle` و`foa_nta_ipc_bundle_ttl`؛ أخطاء للذاكرة المؤقتة المنتهية أو المفقودة. توسيع "NTA" unknown |
| `FamilyAppsUserValuesProvider` | selection واحد `foa_wo_wa_link_eligibility_values`، تُقرأ `getCallingPackage()` |
| `WaAccountsCenterService` | الـ action `com.whatsapp.wfl.OPERATION`؛ جسم الفئة stub في التفكيك (الفحوص unknown) |
| `QuickSendsContactsProvider` | خطوات تحقق `getCallingPackage()` مسجَّلة (`validation_start` / `validation_end`)؛ يقدّم ملفات صور `.enc` مشفرة وأعمدة جهات الاتصال (`obfuscated_chat_id`, `display_name`, `profile_photo_uri`, `photo_key`) |
| `OrbitSsoProvider` (`com.whatsapp.orbit.v2.sso`) | بوابة feature flag؛ يجب أن تكون حزمة المستدعي في قائمة سماح (`AbstractC62035Rsx.A00`، وإلا `SecurityException ... is not allowlisted`)؛ فحص شرط مسبق (`BS3()`) قبل أي طريقة؛ الطرق `get_profile` (تعيد `display_name` و`phone_number` و`avatar_uri` و`avatar_mime_type`) و`get_accounts` و`get_nonce` و`get_token`؛ مسار الملف `avatar` للقراءة فقط. تُطابَق قائمة السماح باسم الحزمة في `A01()`؛ فحص الشهادة، إن وُجد، ليس في تلك الطريقة (unknown). ما يختبره `BS3()` هو inferred حالة تسجيل الدخول |
| `OrbitMessagesProvider` (`com.whatsapp.orbitmessages`) | تُفتح الملفات بالوضع `r` فقط، آخر مقطع `media`، قيم `media_handle` ذات البادئة `v1.` تُفك بـ AES-GCM؛ فحوص المستدعي لم تُحدَّد (unknown) |
| `OrbitCompanionLinkActivity` | تقرأ `getCallingPackage()` وextra `qr_data`؛ مؤقتات الإمساك / الموافقة؛ تعيد النتيجة فقط (`return_result_only`) عبر `CompanionHelloConfirmationActivity` |
| `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | لم تُحلَّل |

### 9.3 مصافحة OTP (`OtpRequestedReceiver`)

تتوقع extra من نوع `PendingIntent` باسم `_ci_` (هوية المستدعي) و`request_id` اختياريًا من نوع UUID (يُفحص بـ regex). تسجّل حزمة المنشئ مقابل قيمة مولَّدة، وتسجّل حدث WAM، وعندما يكون العلم **6617** مفعَّلًا أو تكون الحزمة في القائمة من الإعداد **7050**، ترد ببث `com.whatsapp.otp.OTP_HANDSHAKE_CONFIRMATION` إلى تلك الحزمة يحمل `request_id`. غياب `PendingIntent` يُرفض (`PendingIntent missing from handshake Intent`). لم يُعثر على فحص للتسجيل في هذا المستقبِل.

### 9.4 `AccountTransferReceiver`

تعمل فقط على `com.google.android.gms.auth.START_ACCOUNT_EXPORT`، وفقط عندما يملك الجهاز keyguard آمنًا ويجتاز فحص القدرة (`AbstractC21360rJ.A01`). يعمل التصدير نفسه على منفِّذ في الخلفية (`C05X.A02(...).CVx`)؛ المحتوى unknown.

---

## 10. عرض الحظر ونقاط دخول الاستئناف

| المدخل | الآلية | الدليل |
|-------|-----------|----------|
| بدء بارد في حالة WFAC | الحالة 21 في `Main` تبدأ `WfacBanActivity` عبر `HBC.A00` | found (3.1) |
| `BanAppealActivity` | غير مصدَّرة؛ يبدأها `Main` (extra `launch_source`) ومسار الحظر الدائم | found |
| استطلاع حالة الحظر | Graph، `wfac_ban_status_token`، تقييد 5 ثوانٍ عبر التفضيل `wfac_last_ban_status_fetch_timestamp_ms` | found ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 2.2) |
| تقديم الاستئناف | Graph مع `user_request` مشفَّر (8.1) | found |
| رد التسجيل | حقول `/v2/register`: `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `custom_block_screen`, `version_upgrade` | found ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) 3.3) |
| التواصل مع الدعم | `LoggedOutContactFormActivity` (القسم 6)، العلم `IsRegistrationVerification` لأخطاء التسجيل | found |
| الروابط العميقة | `whatsapp://support`, `whatsapp://help`, `v.whatsapp.com` / `b.whatsapp.com` | found (4.2) |

هوية كل مستخدم في مسار الاستئناف هي token المعتم الصادر من الخادم، لا رقم هاتف ولا معرّف جهاز (أسماء حقول token أعلاه؛ آلية الاشتقاق unknown).

---

## 11. حالات الخطأ والمزالق

| العَرَض | السبب | ملاحظات |
|---------|-------|-------|
| `ConnectionThread/connect/ignored/jid null and not in companion reg` | لا JID وليس تسجيل جهاز مصاحب | طبيعي قبل التسجيل؛ التسجيل يستخدم HTTPS |
| `FAIL_TO_INITIALIZE_WAMSYS` | فشلت تهيئة الحزمة الأصلية (`ensureWamsysForRegBootstrapped`) | يُتخطى HTTP التسجيل وسجل مسار ما قبل الرقم |
| `DeepLinkActivity/deeplink not allowed before registration/` | رمز الرابط محجوب بالبوابة | قائمة السماح لم تُحَل (4.3) |
| `Request was marked with @deidentified, but no ...` | إعداد ACS / OHAI مفقود | الطلب لا يُرسل |

---

## 12. فروقات أساسية

| لا تخلط بين | الحقيقة |
|----------------|------|
| مصدَّر مقابل قابل للوصول بلا حساب | 97 مدخلًا مصدَّرًا؛ معظمها لا يفعل شيئًا مفيدًا حتى يوجد حساب مسجَّل؛ المدخلات في 2.2 و4.2 فقط لها معالجة لحالة التسجيل |
| token التطبيق مقابل token المستخدم | `WA|<app_id>|<secret>` المضمَّن يعرّف التطبيق؛ استدعاءات الحظر تضيف request token معتمًا، لا جلسة مستخدم |
| `fdid` مقابل المعرّف الإعلاني | `fdid` هو UUID يولّده التطبيق ويبقى عبر إعادة التسجيل؛ المعرّف الإعلاني هو قيمة Google |
| نموذج الدعم عند تسجيل الخروج مقابل الدعم داخل التطبيق | يرسل النموذج POST إلى `www.whatsapp.com/contact/noclient/verification/` بحقول مكتوبة؛ أما الدعم داخل التطبيق فيستخدم الجلسة (لم يُحلَّل) |
| HTTP التسجيل مقابل اتصال الدردشة | التسجيل هو HTTPS `/v2/*`؛ اتصال الدردشة بـ JID فارغ لتسجيل الجهاز المصاحب فقط |

---

## 13. التدفق الكامل

```
[App launch / link tap]
    │  Main (only launcher)  or  DeepLinkActivity alias (wa.me, whatsapp.com/dl, v|b.whatsapp.com, whatsapp://...)
    ▼
[Main.A5W]  registration state ──► 2 regname │ 21 WFAC ban │ 41 age consent │ 45 PAA │ 50/51 login-back │ 56 username
    │  default
    ▼
[EULA]  language bottom sheet, ToS / privacy links
    │        └── /v2/pre_pn_client_log  (fdid, screens, device attrs, advertising id)   [ab_key via /v2/reg_onboard_abprop]
    ▼
[RegisterPhone]  hints / SIM number / country names (offline)
    │  /v2/exist  (fdid, fid, authkey, e_* key bundle, device attrs, gpia?)
    ▼
[VerifyPhoneNumber]  reCAPTCHA key GET (gstatic) ── /v2/code ── /v2/register
    │                        │
    │                        ├── ok  ──► RegisterName ──► account exists (leaves this report)
    │                        └── fail: violation_type / appeal_token / custom_block_screen
    │                                      │
    │                                      ▼
    │                         [WfacBanActivity / BanAppealActivity]
    │                                 Graph POST graph.whatsapp.com/graphql
    │                                 doc 4276154569100535 | 27883644401256929  (status, request_token)
    │                                 doc 38509456535312323 | 5473316762755318  (appeal, encrypted)
    ▼
[Help needed]
    LoggedOutContactFormActivity ──► POST www.whatsapp.com/contact/noclient/verification/
                                      email, message, platform=ANDROID, phone_number, debug_info, logs.tar.gz, <=3 JPEG
    ▼
[Background, any state]
    crashlogs.whatsapp.net uploads  │  static.whatsapp.net assets  │  acs.whatsapp.com (ACS/OHAI)
    DNS: system ► MNS ► secondary ► compiled table (e1..e16, g, v)
```

---

## 14. المجهولات

| السؤال | سبب كونه مجهولًا |
|----------|-------------|
| أي رموز الروابط مسموحة قبل التسجيل | فئة قائمة السماح لم تُحَل من جديد؛ المعالجات تفحص الحالة فرديًا، وأربعة فقط تُتبعت |
| منتِج السبب 0 (`not_allowed_before_registration`) | لم يُعزل في switch الكبيرة في `DeepLinkActivity` |
| ضم المضيف والمسار لـ `/v2/*` وثوابت `ENC` و`H` | بُناة الطلبات في wamsys / Kotlin لم تُقرأ |
| أي جلسة تحمل عمليات MEX وقت التسجيل | اتصال JID الفارغ مرفوض خارج تسجيل الجهاز المصاحب؛ مصدر `Ash()` غير محلول |
| محتوى `from_jid` في رفع السجلات أثناء تسجيل الخروج | `AbstractC05620Al.A0G` مجردة |
| تحقق الخادم من tokens والرموز وحمولات الاستئناف | جهة الخادم |
| العمليات التي تحمل `@deidentified` | في `*_pando_flatbuffer_data.bin`، بلا مخطط |
| معنى "NTA"، ومنتِج المعرّف الثانوي `phoneyid_id`، واستخدام `c2dm_reg_id` كحقل في الطلب | أسماء فقط |
| هل يمكن تشغيل `HomeActivity` وهي غير مسجَّلة وماذا تفعل | بوابة الفئة الأساسية لم تُحَل |
