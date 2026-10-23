<!-- src-sha1: 166366154a0dd7893ab70aa91166a96d5a2e788f -->
# WhatsApp Hesapsız Yüzey — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android istemcisinin kayıtlı hesap olmadan veya kayıt tamamlanmadan önce sunduğu yüzey — manifest export'ları (activity'ler, alias'lar, service'ler, receiver'lar, provider'lar), kayıt öncesi ekranlar ve kayıt durumuna göre yönlendirme, deep link'ler ve web link'leri, kimlik doğrulamasız HTTP ve Graph endpoint'leri, derlemeye gömülü host tablosu, oturumsuz destek formu, ban durumu ve itiraz giriş noktaları, girişten önce gönderilen tanımlayıcılar, üçüncü taraf IPC yüzeyleri, bilinmeyenler

---

## 1. Bu sürümde "hesapsız" ne demek

Tek bir "oturumsuz mod" yoktur. İstemci kullanıcı JID'i, kimliği doğrulanmış sohbet oturumu veya tamamlanmış bir kayıt tutmadığında birbirinden bağımsız birkaç yol çalışır. Her yol hesabın yerine farklı bir kimlik bilgisi koyar. Tüm ifadeler decompile edilmiş APK'nın statik analizidir (`versionCode 264100600`, target SDK 36, min SDK 23). Ağ üzerinde hiçbir şey gözlemlenmedi. Katmanlar: **found** = kodda veya manifest'te okundu, **inferred** = koddan çıkarıldı, **unknown** = statik olarak çözülemiyor. Savunma amaçlı dokümantasyon: yüzeyler ve kontroller tanımlanır, çalıştırılmaz.

Obfuscate edilmiş adlar build'e özgüdür ve 2.26.41.6'da kararlı string'lerden yeniden çözüldü.

| Yol | Hesabın yerini alan kimlik bilgisi | Taşıma | Ana sınıflar (2.26.41.6) |
|------|--------------------------------------|-----------|--------------------------|
| Telefon kaydı | `/v2/register`'a kadar yok; istek Noise static key paketini ve cihaz id'lerini taşır | HTTPS `/v2/*` | `K49`, `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Numara öncesi funnel logu | yalnızca phone id (`fdid`) | HTTPS `/v2/pre_pn_client_log` | `PrePnBaseFunnelLogger`, `K49` |
| Sohbet öncesi AB prop'ları | `ab_key` / `ab_hash` prefs | HTTPS `/v2/reg_onboard_abprop` | `K49.checkPreChatdABProps` |
| Ban durumu / itiraz | ban anında saklanan opak token + derlemeye gömülü uygulama istemci token'ı | HTTPS Graph `graph.<domain>/graphql` | `AbstractC40195HfH`, `C37409GLo`, `C37604GYf`, `C37414GLt` |
| Oturumsuz destek formu | yok; e-posta + serbest metin + `anid` | HTTPS multipart POST | `LoggedOutContactFormActivity`, `C47328KmN` |
| Crash / log yükleme | derlemeye gömülü uygulama token'ı | HTTPS `crashlogs.whatsapp.net` | `C10V`, `C05640An` |
| Statik varlıklar | yok | HTTPS GET | `static.whatsapp.net/*` |
| Anonim kimlik bilgili Graph (ACS / OHAI) | ACS token'ı veya OHAI key config'i, JID yok | HTTPS `acs.whatsapp.com/graphql` | `C31991Nz`, `R5t`, `N5I` |
| Companion kaydı | yok; null-JID Noise bağlantısına yalnızca burada izin verilir | Noise | `HandlerThreadC12340b0` |
| Gömülü DNS yedeği | yok | derlemeye gömülü tablo | `AbstractC47101wK`, `C36881dC` |

Burada kapsanmayanlar, bağlantılı raporlara bakın: kayıt adımları, OTP yöntemleri ve hata nedenleri ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) bölüm 3); kayıtta gönderilen attestation token'ları ([WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)); ban durum makinesi ve itiraz şifrelemesi ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) bölüm 2, 10); Noise girişi ve companion kaydı ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)); WAM telemetrisi ([WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)).

---

## 2. Manifest: export edilen bileşenler

### 2.1 Sayılar (found, `AndroidManifest.xml`, `<application>` altında ayrıştırıldı)

| Tür | Tanımlı | Export edilen (açık `true`; hiçbiri örtük varsayılana dayanmıyor) |
|------|---------:|----------------------------------------------------------------:|
| `activity` | 828 | 22 |
| `activity-alias` | 33 | 29 (14'ü devre dışı `AppIcon01..14` launcher alias'ı) |
| `service` | 61 | 16 |
| `receiver` | 68 | 19 |
| `provider` | 19 | 11 |
| Toplam | 1009 | 97 |

97 export edilen girdinin 20'si `enabled="false"` (14 ikon alias'ı, car-app service, ADM receiver, iOS-migration activity ve provider, iki Hindistan UPI intent receiver'ı); 24'ü `permission` / `readPermission` taşır; 6'sı WhatsApp tanımlı bir `signature` permission ile korunur; 56'sı etkin ve manifest permission'ı yoktur. Manifest'in ötesindeki her kontrol kodda yer alır (bölüm 9).

Özel permission'lar (found): `REGISTRATION`, `IDENTITY_VERIFICATION`, `MIGRATION_CONTENT_PROVIDER`, `BROADCAST`, `MAPS_RECEIVE`, `RECEIVE_ADM_MESSAGE`, `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` `protectionLevel="signature"` değerindedir. `com.whatsapp.sticker.READ` için `protectionLevel` yoktur (varsayılan normal).

### 2.2 Hesap olmadan çalışan giriş noktaları

| Bileşen | Export | Filtre | Kayıt öncesi neden erişilebilir |
|-----------|----------|--------|--------------------------------------|
| `com.whatsapp.Main` | evet | `MAIN` / `LAUNCHER`, `MULTIWINDOW_LAUNCHER` | tek launcher; kayıt durumuna göre yönlendirir (bölüm 3) |
| `com.whatsapp.home.ui.HomeActivity` + alias'lar `AcceptInviteLinkActivityDeepLink`, `EventDeepLink`, `HomeActivity` | evet | `chat.whatsapp.com`, `call.whatsapp.com`, `event.whatsapp.com`, `whatsapp://chat`, `call`, `event`, NFC `application/com.whatsapp.chat`, `.join` | `HomeActivity` içinde kayıt kontrolü bulunamadı (inferred: bir üst sınıf yönlendiriyor, çözülmedi) |
| 4 alias üzerinden `DeepLinkActivity` | alias evet, hedef hayır | bölüm 4'e bakın | link giriş noktası |
| `com.whatsapp.deeplink.ui.TpalOAuthRedirectActivity` | evet | `www.whatsapp.com/oauth_account_linking/login_redirect`, `/oauth_account_linking_mobile/login_redirect`, `whatsapp://third_party_oauth` | OAuth yönlendirme alıcısı, `noHistory` |
| `com.whatsapp.cuif.ConsentActivity` | evet | `whatsapp://consent` | `flow_name`, `source`, `extra_params`, `device_id`, `app_id` extra'larını okur; kayıt öncesi davranışı çözülmedi |
| `com.whatsapp.Conversation` | evet | `sms:` / `smsto:` `VIEW` / `SENDTO` | sistem SMS işleyicisi giriş noktası |
| `com.whatsapp.accountsync.ProfileActivity`, `CallContactLandingActivity` | evet | `content://com.android.contacts` MIME `vnd.com.whatsapp.profile`, `.voip.call`, `.video.call` | kişiler uygulaması entegrasyonu; `CallContactLandingActivity` için `CALL_PHONE` gerekir |
| `com.whatsapp.registration.ui.RegistrationCompletedReceiver` | evet, `REGISTRATION` signature | `com.whatsapp.SMBRegistrationCompleted` | kardeş uygulama sinyali |
| `com.whatsapp.registration.directmigration.MigrationProviderOrderedBroadcastReceiver`, `MigrationRequesterBroadcastReceiver` | evet, `REGISTRATION` signature | action'lar `initialMigrationInfoAction`, `recoveryTokenAction`, `setMigrationStateOnProviderSide`, `providerIsLoggedOutAction`, `providerAppMigrationSpaceNeededAction` | kayıt sırasında consumer / SMB kardeş uygulama migration'ı |
| `MigrationContentProvider`, `DirectMigrationContentProvider` | evet, `readPermission` `MIGRATION_CONTENT_PROVIDER` (signature) | authority'ler `com.whatsapp.provider.MigrationContentProvider`, `.DirectMigrationContentProvider` | aynı migration |
| `com.whatsapp.registration.app.verifyphone.SMSRetrieverAppInactiveReceiver` | evet, GMS `SEND` permission | `SMS_RETRIEVED` | uygulama etkin değilken SMS Retriever sonucu |
| `com.whatsapp.registration.core.accounttransfer.AccountTransferReceiver` | evet, permission yok | `com.google.android.gms.auth.START_ACCOUNT_EXPORT` | kod, işlem yapmadan önce güvenli keyguard ve bir özellik kontrolü ister (found) |
| `com.whatsapp.phoneid.PhoneIdRequestReceiver` | evet, permission yok | `com.facebook.GET_PHONE_ID` | phone id'yi güvenilen bir çağırana döndürür (bölüm 9.1) |
| `com.whatsapp.otpmessage.otp.OtpRequestedReceiver`, `OtpIdentityHashRequestedReceiver` | evet, permission yok | `com.whatsapp.otp.OTP_REQUESTED`, `ID_HASH_REQUESTED` | diğer uygulamalar için OTP otomatik doldurma el sıkışması (bölüm 9.3) |

### 2.3 Diğer export edilen girdiler (kayıtla ilgili değil, bütünlük için listelendi)

| Grup | Bileşenler | Geçit |
|-------|------------|------|
| Üçüncü taraf içerik | `Conversation` (`sms:` işleyicisi), `ExternalShareAlias` (`SEND`, `SEND_MULTIPLE`, `*/*`), `ContactPicker` (`PICK`, `CREATE_SHORTCUT`), `SetAsProfilePhoto` (`ATTACH_DATA`) | manifest'te yok |
| Sticker'lar | `SendStickerCommandActivity`, `AddThirdPartyStickerPackActivity` (+ alias), `StickerCommandProvider`, `WhitelistPackQueryContentProvider` | manifest'te yok |
| Meta ailesi IPC | `FamilyAppsCredentialsProvider`, `FamilyAppsUserValuesProvider`, `WaAccountsCenterService` (`com.whatsapp.wfl.OPERATION`), `QuickSendsContactsProvider`, `OrbitSsoProvider`, `OrbitMessagesProvider`, `OrbitCompanionLinkActivity`, `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | çağıran kontrolleri kodda (bölüm 9) |
| Cihaz companion'ları | `WearOsListenerService`, `GarminBindingServiceShim`, `IQGarminBindingService`, `TetheredService`, `WhatsAppCarAppService` (devre dışı) | manifest'te yok |
| Google entegrasyonu | `BackupNowService`, `BackupStateService`, `OsMigrationAppDataService` (`BACKUP`), `DeferredRestoreBroadcastReceiver` (`BACKUP`), `WakeUpService` (exposure notification permission) | kısmen |

Ayrıca export edilenler: ayar kancaları (`SettingsNotifications`, `SettingsDataUsageActivity`, `AppAuthenticationActivity` widget configure), çağrı giriş ekranları (`SystemDialerCallLandingActivity`, `VoiceMessagingActivity`), kütüphane receiver'ları (`WidgetProvider`, `BootReceiver`, `AppUpdatedReceiver`, `ExternalMediaStateReceiver`, `WAFbnsPreloadReceiver`, `FirebaseInstanceIdReceiver`, `BIND_JOB_SERVICE` / `DUMP` arkasındaki work-manager ve profile-install girdileri), Pixel girdileri (`com.google.permission.besties.API`) ve devre dışı Hindistan UPI ve iOS-migration girdileri. `IdentityVerificationActivity` (NFC `application/com.whatsapp.identity.ui`) `IDENTITY_VERIFICATION` signature permission'ını gerektirir.

### 2.4 Export edilmeyen kayıt öncesi bileşenler (found)

Export edilmeyen 806 activity her kayıt ekranını (bölüm 3.2), `LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity`, `BanAppealActivity`, `WfacBanActivity`, `PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity` sınıflarını içerir. Export edilmeyen üç alarm receiver'ı kayıt hatırlatıcılarını yürütür: `RegRetryVerificationReceiver` (`com.whatsapp.alarm.REGISTRATION_RETRY`, `SMS_RECEIVED_WHILE_INACTIVE`), `OnboardingIncompleteReceiver` (`ONBOARDING_INCOMPLETE`), `EnterPhoneNumberNotificationReceiver` (`ENTER_PHONE_NUMBER`). Export edilmeyen provider'lar: `FileProvider`, `SecureFileProvider`, `MediaProvider`, `AccountSwitchingContentProvider`, `RestartAppContentProvider`, `InstrumentationProvider` (tanımlandığı yerde hepsi `grantUriPermissions` ile).

### 2.5 Uygulama flag'leri ve ağ politikası (found)

| Öğe | Değer |
|------|-------|
| `debuggable` | `false` |
| `allowBackup` | `true`, ancak `fullBackupContent` ve `dataExtractionRules` (cloud-backup ve device-transfer) tüm domain'leri hariç tutar; iOS için çapraz platform aktarım girdisi yalnızca `bundleId` / `teamId` taşır |
| `networkSecurityConfig` base | `cleartextTrafficPermitted="true"`; trust anchor'lar `system` ve `user` (kullanıcı CA'ları için `overridePins="true"`) |
| Cleartext yasak | `whatsapp.com`, `whatsapp.net`, `wa.me`, `wl.co` (22 SHA-256 pin, süre sonu yok), `facebook.com`, `instagram.com`, `jiomart.com`, `hatch-api.meta.ai` |
| Pin kapsamı | pin seti `whatsapp.com` / `whatsapp.net` / `wa.me` / `wl.co` domain-config'inde durur; base trust anchor'ları miras alır, dolayısıyla pin'ler kullanıcı tarafından kurulan CA'lara uygulanmaz (`overridePins` platform davranışı) |
| Hiçbir domain-config dışındaki host'lar | `gstatic.com` (reCAPTCHA key) base config altına düşer (cleartext izinli; kod `https://` kullanır) |

---

## 3. Kayıt öncesi ekranlar ve durum yönlendirmesi

### 3.1 Kayıt durumuna göre `Main` yönlendirmesi (found, `Main.A5W` smali)

`Main` kayıt durumunu (`C0Gk.A02()`) ve saklanan kendi hesap nesnesini okur. Log tag'leri kararlı çapa noktalarıdır.

| Durum | Log tag | Hedef |
|------:|---------|-------------|
| 2 | `main/me/regname`, `main/no-me/regname` | ad girişi kayıt adımı (`RegisterName`) |
| 21 | `main/me/wfac ban` | `HBC.A00` üzerinden WFAC ban ekranı (`WfacBanActivity`) |
| 24, 38 | `main/me/backup otp` | yedek OTP / doğrulama adımı |
| 41 | `main/me/consent age ban` | yaş onayı ekranı |
| 45 | `main/me/paa onboarding`, `main/no-me/paa onboarding` | bağımlı / yönetilen hesap onboarding'i |
| 50 | `main/me/logged out, going to PrimaryLoginBackActivity` | login-back ekranı |
| 51 | `main/me/pending login-back verification` | login-back doğrulaması (extra `login_back_verification`) |
| 56 | `main/me/username`, `main/no-me/username` | kullanıcı adı adımı |
| any | `main/no-me/first-factor password` | birinci faktör parola dalı (kendi hesap nesnesi yok) |
| any | `main/invalid/registration state=` | geçersiz durum logu |

Aynı metot `VerifyPhoneNumber`, `DeviceConfirmationRegistrationActivity`, `ExportMigrationDataExportedActivity`, `BanAppealActivity` (extra `launch_source`), `DeleteAccountConfirmation` ve varsayılan `RegisterPhone` girişi için intent'ler oluşturur (found). `logged_out_phone_fallback_pending` tercihi `RegisterPhone`'dan devam ettirir (`main/me/logged-out phone fallback resume`). Basılmış bir IDV token'ı (`minted_idv_token`, `minted_idvtoken_expiry_time_secs`) kontrol edilir; süresi dolmuş veya boş olan düzeltme akışını sıfırlar. Hangi sayısal durumun hangi sunucu tarafı adıma karşılık geldiği tag adlarından inferred.

### 3.2 Kayıt ekranları (found, hepsi export edilmeyen)

| Grup | Activity'ler (aksi belirtilmedikçe `com.whatsapp.registration.app.*`) |
|-------|--------------------------------------------------------------|
| Giriş | `EULA` (tag `eula_screen` / `eula_with_language_selector`), `phonenumberentry.RegisterPhone`, `RegisterAsDependentActivity`, `RegTabletIntroActivity`, `RegTabletChooseOptionActivity` |
| İzinler | `RegPermissionsExplainerActivity`, `RegNotificationPermissionPrimerActivity` |
| Doğrulama | `verifyphone.VerifyPhoneNumber`, `sendsmstowa.SendSmsToWa`, `ManualSmsRequest`, `flashcall.PrimaryFlashCallEducationScreen`, `email.RegisterEmail`, `email.VerifyEmail`, `email.EmailEducationScreen`, `email.UnverifiedEmailSetupRegUpsellActivity`, `email.ConfirmEmailSetupRegUpsellActivity`, `backuptoken.BackupTokenEducationScreen`, `VerifyTwoFactorAuth` |
| Hesap savunması | `accountdefence.DeviceConfirmationRegistrationActivity`, `accountdefence.ui.OldDeviceSecureAccountActivity`, `OldDeviceSecureAccount2FaActivity`, `OldDeviceMoveAccountNoticeActivity` |
| Engeller | `parole.CustomRegistrationBlockActivity`, `downgrade.DowngradeFrictionActivity`, `com.whatsapp.userban.ui.BanAppealActivity` |
| Migration | `directmigration.RestoreFromConsumerDatabaseActivity`, `MigrationStartTransferActivity`, `RequestPermissionFromSisterAppActivity`, `com.whatsapp.migration.transfer.ui.*` |
| Ad / numara değiştirme | `RegisterName`, `phonenumberentry.ChangeNumber*` |
| Companion modu | `com.whatsapp.companionmode.registration.ui.RegisterAsCompanionActivity`, `RegisterAsCompanionEnterNumberActivity`, `RegisterAsCompanionLinkCodeActivity`, `CompanionBootstrapActivity`, `CompanionPostLogoutActivity` |
| Oturumsuz | `logout.ui.PrimaryLoginBackActivity`, `RemoveLoggedOutAccountsActivity`, `loginfailure.LogoutMessageActivity` |
| Destek | `inappsupport.ui.app.LoggedOutContactFormActivity`, `LoggedOutContactSuccessActivity` |

### 3.3 Dil ve ülke seçicileri (found)

| Öğe | Ayrıntı |
|------|--------|
| Dil | `EULA`'dan açılan `LanguageSelectorBottomSheet` (funnel olayı `language_selected`; `K49` içindeki metrikler `language_selector_clicked_count`, `language_selector_time_spent`); ayarlar tarafındaki `FullScreenLanguageSelectorActivity` export edilmez |
| Ülke adları | 63 çevrimdışı tablo `assets/country_names_<lang>.tsv` (`ISO code<TAB>name`); seçici için ağ araması bulunamadı |
| Numara ön doldurma | `RegisterPhone` Google telefon numarası ipuçlarını (`RegisterPhone/launchGooglePNHints`) ve telefon izni gerektiren bir "numaram nedir" SIM yolunu kullanır; EULA extra'ları `RegisterPhone.phone_number`, `country_code`, `auto_submit_after_prefill`, `one_click_from_eula` |
| `EULA` üzerindeki yasal linkler | `https://www.whatsapp.com/legal/terms-of-service` veya `/terms`, `privacy-policy` veya `privacy-policies` (config'e göre varyant) |

---

## 4. Deep link'ler ve web link'leri

### 4.1 Giriş alias'ları (found)

| Alias | Hedef | Filtreler |
|-------|--------|---------|
| `TextAndDirectChatDeepLink` | `DeepLinkActivity` | `http(s)://api.whatsapp.com`, `wa.me`; `https://[www.]whatsapp.com` yolları `/channel`, `/channel_status`, `/updates`, `/aimediainput`, `/aivoice`, `/dl`, `/privacy/disclosure`, `/wamo/status/link-{instagram,facebook}-in-house-ad`; şemalar `whatsapp`, `whatsapp-smb`, `whatsapp-consumer`, `whatsapp-sheet` (host listeleri, 100+ host) |
| `VerifyOtpDeepLink` | `DeepLinkActivity` | `http(s)://b.whatsapp.com`, `http(s)://v.whatsapp.com` |
| `FoaDeeplinkActivityAliasUniversalLink`, `FoaDeeplinkActivityAliasAppScheme` | `DeepLinkActivity` | bu manifest'te filtre yok (Meta ailesi deep-link kütüphanesi için tanımlı) |
| `AcceptInviteLinkActivityDeepLink` | `HomeActivity` | `chat.whatsapp.com` |

`DeepLinkActivity` kendisi export edilmez; her dış yol bir alias'tan geçer. `autoVerify="true"` taşıyan tüm filtreler yalnızca https host'larını kapsar. `whatsapp`, `whatsapp-consumer`, `whatsapp-smb` üzerindeki birkaç filtre hem `VIEW` hem de özel action `com.whatsapp.DEEP_LINK_REDIRECT` taşır; bu yüzden alias, herhangi bir uygulamadan gelen bu action'lı açık intent'e yanıt verir (found: filtre biçimi).

### 4.2 Kayıt öncesi durumu işleyen linkler (found)

| Link | Ayrıştırıcı çapası | Davranış |
|------|---------------|-----------|
| `https://[www.]whatsapp.com/dl?wsu=<6 digits>` | `IJB.A01`: yol `dl`, sorgu `wsu` `\d{6}` ile eşleşir, log `DeepLinkHelper/parseUri/web signup uri`, kod **193** | web kaydolma devri; değer istemci tarafında yalnızca regex ile doğrulanır |
| `whatsapp://s/signup` (tek yol segmenti `signup`) | `IJB.A01` kod **216**, ab-prop **25005** veya **25801** ile geçitli; işleyici `handleInAppSignupDeepLink` şema `whatsapp` ve sorgu `s` gerektirir | uygulama içi kaydolma; `signup_id` ile `ApiSignupFlowLogger` üzerinden loglar (host `s` eşleşmesi manifest'ten inferred) |
| `https://v.whatsapp.com/<code>`, `https://b.whatsapp.com/<code>` (son yol segmenti) ve `whatsapp://r?c=<code>` | `DeepLinkActivity` kayıt dalı, log `DeepLinkActivity/Registration deeplink/registration state:` | e-posta OTP linki. Durum 1 `RegisterPhone`'u extra `tapped_sms_link` ile açar; durum 2 `VerifyEmail`'i `email_otp`, `entrypoint`, `session_id`, `challenge_flow=false` ile açar ve `email_otp_deeplink_redirect_to_register_name` raporlar; diğer durumlar ayarlara yönlendirir (`settings_verification_email_address_verified`, inferred). Kod extra olarak iletilir; doğrulama sunucu tarafındadır (unknown) |
| `whatsapp://code-linking?auth=<nonce>` | kod **77**, işleyici `maybeStartCodeLinkingFlow`, ab-prop **4560** (`ENABLE_CODE_LINKING_DEEP_LINK_CODE`), 300000'lik pencereli pref `adl_deep_link_nonce` (birim ms olarak inferred) | bağlı cihaz kod akışı; flag kapalıysa veya nonce pencereden eskiyse atlanır |
| `whatsapp://help/<segment>` | kod **62**; çevrimdışı dal `DeepLinkActivity/help/no-connectivity` loglar | yardım makalesi |
| `whatsapp://support` | kod **30** (ayrıştırıcıdan çıkarıldı; işleyici `about/no-connectivity` loglar) | destek / hakkında ekranı, bağlantı gerekir |

### 4.3 Kayıt öncesi geçit

| Çapa | Bulgu | Katman |
|--------|---------|------|
| `DeepLinkActivity/deeplink not allowed before registration/` ve neden `not_allowed_before_registration` | mevcut; neden enum'u 0 değerini bu string'e eşler; sıradan linkler için neden 0'ı üreten kod izole edilemedi | found (string'ler), unknown (üretici) |
| Kod başına işleyiciler | her işleyici kayıt durumunu kendisi kontrol eder (switch gövdelerinde `C0Gk.A0C()` / `A02()` çağrıları) | found |
| Oturumsuz kodların izin listesi | yeniden çözülmedi: bu build'de `C02T` seri bir executor, `C02U` paylaşılan bir integer sabit sınıfıdır; dolayısıyla önceki sınıf adları eşleşmez | unknown |
| `IJB`, `IJC`, `IJD`, `IJE` tarafından oluşturulan `JXK` sonucu (`code`, `source`, neden) | `DeepLinkActivity.A0w` tarafından tüketilen ayrıştırıcı çıktısı | found |

İçeriği çözmek (bir sohbet, bir kanal, bir dizin) hâlâ hesap gerektirir: grup davet ve `wa.me/<phone>` işleyicileri kimliği doğrulanmış oturumu kullanır (işleyici adlarından inferred; burada baştan sona izlenmedi).

---

## 5. Hesapsız iletişim kurulan host'lar ve endpoint'ler

### 5.1 Kayıt HTTP'si (found)

16 yol, `AbstractC45307Jps` içinde XOR key 18, hepsi 2.26.41.6'da yeniden çözüldü: `/v2/exist`, `/v2/code`, `/v2/register`, `/v2/security`, `/v2/challenge`, `/v2/passkey_auth`, `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop`, `/v2/device_logout_send`, `/v2/device_logout_fetch`, `/v2/wfs`. İki ek sabit `ENC` ve `H` olarak çözülür (kullanımı unknown). İlk grubun alan listeleri [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) bölüm 3.1'dedir. Ana host `v.whatsapp.net`, derlemeye gömülü tablodaki addır (5.4); host ile yolu birleştiren kod wamsys / Kotlin stack'lerindedir ve burada okunmadı (inferred).

Seçici `K49.A0b` Kotlin stack'ini (`KotlinRegistrationBridge`) veya native `wamsys` stack'ini seçer; native stack önce bootstrap edilmelidir (`ensureWamsysForRegBootstrapped`, hata `FAIL_TO_INITIALIZE_WAMSYS`).

### 5.2 Diğer HTTPS endpoint'leri (found literal, kimlik doğrulama belirtildiği gibi)

| Host / URL | Yöntem | Koddaki kimlik doğrulama | Çağıran | Hesapsız mı? |
|------------|--------|--------------|--------|---------------|
| `https://www.whatsapp.com/contact/noclient/verification/` | multipart POST | yok | `C47328KmN` case 0 (destek formu) | evet |
| `https://graph.<pref_graphql_domain>/graphql` (varsayılan `graph.whatsapp.com`) | POST JSON | gövdede `access_token` içinde derlemeye gömülü uygulama istemci token'ı | `AbstractC40195HfH` ve alt sınıfları | evet (ban durumu / itiraz) |
| `https://crashlogs.whatsapp.net/wa_clb_data`, `/wa_fls_upload_check`, `/wa_profilo_data`, `/whatson_logs_upload` | POST | derlemeye gömülü uygulama token'ı (log yükleme `access_token`, `type`, `from_jid`, `ticket_id`, `build_id` ekler) | `C10V`, `C05640An`, `ExceptionsUploadService`, `ProfiloUploadService`, `CM8` | girişsiz çalışır; oturumsuzken `from_jid` içeriği unknown |
| `https://acs.whatsapp.com/graphql` | POST | ACS token'ı veya OHAI config'i (JID yok) | `C31991Nz`, `R5t` | evet (kimliksizleştirilmiş istekler) |
| `https://static.whatsapp.net/wa/static/{downloadable,network_resource,payments/*}`, `/sticker?...`, `/payments/background` | GET | yok | UI varlık yükleyicileri | evet |
| `https://mmg.whatsapp.net/proxygen/health`, base `https://mmg.whatsapp.net` (config 22436) | GET | yok | medya / sağlık | evet |
| `https://www.gstatic.com/recaptcha/verify_key/orcas/prod/android/verify_key.txt` | GET | yok | `C44464JbH` (`RequestCodeRepository`, `VerifyCodeRepository`, `VerifyPhoneNumber` tarafından kullanılır) | evet (kayıt captcha'sı) |
| `https://www.whatsapp.com/compliance/xfac/mint` | POST form | görülmedi | `CommonRemediationApi` (yaş düzeltmesi, `minted_idv_token`) | kayıt öncesi erişilebilir: unknown |
| `https://www.whatsapp.com/v1/auth/canonical/token/` | POST form `nonce`, `user_id`, `device_id`, `client_pub_key` | yok | `CanonicalUserCompanionDeviceManager` | companion / bağlı hesap yolu, saf kayıt öncesi değil |
| `https://api.whatsapp.net/support/add_bug_attachment` | multipart POST | `Authorization: Bearer <token>` | `PostBugAttachmentUploader` (uygulama içi hata raporu) | hayır (token'a bağlı) |
| `https://graph.whatsapp.net/v2.2/maps_configs?...&access_token=` (varsayılan `graph.facebook.com`) | GET | URL'de uygulama token'ı | `N6n` harita config'i | tetikleyici kayıt öncesi değil (inferred) |
| `https://api.whatsapp.net/calendar/integrations/` | istek | oturum | takvim özelliği | hayır |

Derlemeye gömülü token'lar: iki Facebook tarzı biçim vardır, Graph istemcisi varsayılanında `WA|<app_id>|<secret>` ve log yükleyicide `<app_id>|<secret>`. Değerler burada yeniden üretilmez. Kullanıcıyı değil, uygulamayı tanımlarlar.

### 5.3 DNS ve bağlantı bootstrap'i (found)

| Öğe | Ayrıntı |
|------|--------|
| Derlemeye gömülü tablo `AbstractC47101wK` | 18 ad için host'tan IPv4 / IPv6 listesine: `.whatsapp.net` altında `e1..e16`, `g`, `v` (her biri sondaki noktalı ikiziyle); ağ gerekmez |
| `C36881dC` (DnsCache) | kullanım sırası: birincil resolver, MNS DNS resolver (`DnsCache/resolveViaMnsDns`, bu dalda `v.whatsapp.net` string'i test edilir), ikincil resolver, sabit kodlu tablo; tabloda giriş yoksa sabit kodlu aramalar `no hardcoded ips found for <host>` ile başarısız olur, seçenek biti kapalıysa `hardcoded dns resolver disabled` ile atlanır |
| Sohbet host'u | `g.whatsapp.net` girdisi doğrudan okunur (`C36881dC.A01`) |

MNS resolver wire formatı native kodda yaşar: unknown.

### 5.4 Var olmayan REST yolları (found negatif)

Geçit veya config için kimlik doğrulamasız REST çekimi (`/gk`, `/props`, `/config`) bulunamadı. Giriş öncesi deney config'i kayıt HTTP'si üzerinden gelir: `/v2/reg_onboard_abprop` (`K49.checkPreChatdABProps`) `pref_pre_chatd_ab_hash` tercihinden `ab_hash`, `pref_pre_chatd_ab_key` tercihinden `ab_exposure`/`ab_key` ve ayrıca bölüm 7'deki cihaz alanlarını gönderir.

---

## 6. Oturumsuz destek formu (found)

`LoggedOutContactFormActivity` (export edilmeyen) bu build'deki tek tam hesapsız destek akışıdır.

| Intent extra (önek `com.whatsapp.inappsupport.ui.app.LoggedOutContactFormActivity.`) | Kullanım |
|------|-----|
| `PhoneNumber`, `CountryCode` | ön doldurulmuş numara; yoksa boş string |
| `From` | giriş noktası etiketi |
| `ServerStatus` | çağırandan geçirilen durum string'i (inferred: kayıt sunucusu durumu) |
| `IsRegistrationVerification` | boolean; başarıda bir takip çağrısı yapılır (hedef çözülmedi) |
| `SupportUserContext` (`K8W`) | giriş noktası ve CMS id'leri (`Entry point`, `Cms ids`) |

Form alanları: e-posta (öneri chip'leri `@gmail.com`, `@hotmail.com`, `@icloud.com`, `@outlook.com`, `@yahoo.com`), açıklama, `MediaStore`'dan seçilen en fazla 3 ekran görüntüsü.

Gönderim (`C47328KmN` case 0, tag `logged_out_contact_form`, anlamı çözülmemiş sondaki argüman 20):

| Parça | Ad | İçerik |
|------|------|---------|
| field | `email` | girilen e-posta |
| field | `message` | açıklama |
| field | `platform` | sabit `ANDROID` |
| field | `phone_number` | girilen numara |
| field | `debug_info` | `C10V.A08` tarafından oluşturulan metin (bölüm 7.3) |
| file | `log_data` | istemci logunun `logs.tar.gz` dosyası (önce döndürülür ve sıkıştırılır) |
| files | `attachment_<n>` | ekran görüntüleri JPEG kalite 80, 2048 px sınırıyla yeniden kodlanır, yalnızca 10 MiB veya daha küçükse tutulur |
| extra | `skip_saga_copy=true`, `saga_copy=true`, `pn` | `pn` = ikisi de boş değilse ülke kodu + numara |

Sonuç: HTTP durumu bir sonuç callback'ine (`C46422KQg`) gider; hata `Server error: <status>` veya `Network error` olarak görünür; başarı `LoggedOutContactSuccessActivity` açar (extra `...Email`). Durumdan başarıya tam eşleme okunmadı. Çağrı uygulama HTTP istemcisi üzerinden düz bir HTTPS POST'tur; GraphQL çağrısı değildir. Her gönderim için rastgele bir `anid` UUID'si (7.1) üretilir.

---

## 7. Girişten önce gönderilen tanımlayıcılar

### 7.1 Tanımlayıcı tablosu

| Tanımlayıcı | Nerede | Kaynak | Notlar | Katman |
|------------|-------|--------|-------|------|
| `fdid` | `/v2/pre_pn_client_log`, kayıt istekleri | `C38141gV.Ax2()`: rastgele `UUID.randomUUID()`, prefs içinde `phoneid_id` + `phoneid_timestamp` olarak saklanır | kayıt denemeleri arasında kalıcıdır; aynı id `PhoneIdRequestReceiver` tarafından döndürülür | found |
| `fid` | kayıt istekleri | `C47381wu.Ax2()`: prefs `phoneyid_id` + `phoneyid_timestamp`, yalnızca mevcutsa `<id>|<timestamp>` olarak gönderilir | ikincil aile id'si; değerin üreticisi izlenmedi | found (kullanım inferred) |
| `anid` | destek formu | `C11J.A01()`: çağrı başına `UUID.randomUUID()`, ayrıca WAM olayı olarak loglanır | gönderim başına rastgele id | found |
| `advertising_id` / `android_advertising_id` | `/v2/exist`, `/v2/code`, `/v2/register`; funnel logu | varsa Google reklam id'si | funnel logger'ın debug log string'inden hariç tutulur | found |
| `authkey`, `e_ident`, `e_keytype`, `e_regid`, `e_skey_id`, `e_skey_val`, `e_skey_sig`, `e_pq_last_resort_{id,val,sig}` | kayıt istekleri | `C45446JsB`: istemci Noise static key'i ve Signal key paketi | açık materyal | found |
| `gpia` | kayıt istekleri | Play Integrity standart token'ı, flag geçitli | bkz. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) | found |
| `ab_key`, `ab_hash`, `ab_exposure` | `/v2/exist`, `/v2/pre_pn_client_log`, `/v2/reg_onboard_abprop` | prefs `pref_pre_chatd_ab_key` / `pref_pre_chatd_ab_hash` | deney kovası | found |
| `device_country` | funnel logu | `TelephonyManager.getSimCountryIso()` büyük harfe çevrilir, yoksa `ZZ` | | found |
| `access_token` (uygulama) | Graph, log yükleme | derlenmiş sabit | uygulama kimliği, kullanıcı değil | found |
| `request_token` / `token` | ban durumu / itiraz | pref `wfac_ban_status_token` (durum) ve saklanan itiraz token'ı | opak, ban anında sunucu tarafından verilir ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md)) | found |
| `from_jid` | log yükleme | varsa hesap JID'i | oturumsuzken içerik unknown | found (alan), unknown (değer) |
| `registration_trace_id`, `request_id`, `nonce_encryption_key` | hesap kurtarma mutation'ı | `AccountRecoveryManager` (bölüm 8.2) | | found |

### 7.2 Kayıt isteklerindeki cihaz öznitelikleri (found, `K49` yardımcıları `A0O`, `A0Q`, `A0R`, `A0U`, `A0W`, `A0X`)

`network_radio_type`, `simnum` (`0` / `1`), `hasinrc` (`rc2` dosyası mevcut), `pid` (process id), `device_ram`, `sim_type`, `airplane_mode_type`, `cellular_strength` (sinyal seviyesi, varsayılan `5`), `roaming_type`, `preloads_app_manager_id`, `preloads_attribution`, `entrypoint` (`create_paa` veya `suma`), `tos_version` (`5`), `old_phone_number` (numara değiştirme akışı). Aynı sınıftaki telemetri metrik anahtarları (found, istekte kullanım doğrulanmadı): `network_operator_name`, `sim_operator_name`, `sim_state`, `read_phone_permission_granted`, `mistyped`, `c2dm_reg_id` (prefs'ten okunur).

### 7.3 Funnel log içeriği (found, `PrePnBaseFunnelLogger$sendPrePNFunnelLog$1`)

Numara oluşmadan önce istemci şunları gönderir: `current_screen`, `previous_screen` (pref `pref_previous_screen`, varsayılan `unknown`), `action_taken`, `event_name`, `access_funnel_type=wa`, `app_campaign_download_source`, `is_add_account_flow`, `android_advertising_id`, `ab_key`, `device_country`, `fdid`, yukarıdaki cihaz öznitelikleri ve `entrypoint`. Hesap ekleme veya oturumsuz yedek akışlarında ayrıca `primary_logout_session_id` ve `number_of_accounts` gönderir. wamsys bootstrap'i başarısız olursa gönderim atlanır.

### 7.4 Destek formunun `debug_info` alanı (found, `C10V.A08`, bu çağrıda JID argümanı `null`)

Metne yazılan etiketler: `useragent`, `Socket Conn`, `Connection`, `Server`, `Datacenter`, `Sim`, `Free Space Built-In` / `Removable`, `Network metered` / `restricted`, `Data roaming`, `Tel roaming`, `Diagnostic Codes`, `ABprops hash state`, `Screen reader`, `Fingerprint eligible`, yedekleme durumu alanları, `Is Companion`, `Number of Accounts`, `Mobile Build Id`, `wfl_state`, `isMetaVerified`, `Mistyped` / `Mistyped Last6` / `L Distance` (girilen numaranın SIM numarasıyla karşılaştırması) ve arama geçmişi varsa son arama tanımlayıcıları. `entity id` etiketi yalnızca bir JID geçirildiğinde yazılır; burada geçirilmez.

---

## 8. Kullanıcı oturumu olmadan Graph ve MEX çağrıları

### 8.1 Uygulama token'lı Graph istekleri (found)

Temel sınıf `AbstractC40195HfH.CND` `https://graph.<A0f()>/graphql` adresini oluşturur (`A0f()` = pref `pref_graphql_domain`, varsayılan `whatsapp.com`; alt sınıflar `GEV`, `GEX`, `GET`, `GEW`, `GEU` ve `C45F` Meta hesabı ailesi `facebook.com` / `instagram.com` değerine geçer). Gövde JSON: operasyon değişkenleri, `access_token` (alt sınıf vermezse derlenmiş token), `doc_id`, `lang`, `Content-Type`. Header `X-FB-Request-Analytics-Tags` yoksa eklenir.

| Sınıf | doc_id | Değişkenler | Amaç |
|-------|-------:|-----------|---------|
| `C37604GYf` | **4276154569100535** | `app_id` (`dev.app.id`), `request_token` | WFAC ban durumu poll'u (`WfacBanRepository/fetchBanStatus`, token pref `wfac_ban_status_token` içinden) |
| `C37409GLo` | **27883644401256929** veya **4276154569100535** (boolean) | aynı | `HG2.A01` üzerinden ban durumu |
| `C37414GLt` | **38509456535312323** veya **5473316762755318** (boolean) | `app_id`, `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}`; plaintext `{token, debug_info, description}`, context `WA_INAPP_BAN_APPEALS` | ban itirazı gönderimi (`C40191HfD`); ayrıntılar [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) bölüm 10'da |
| `C37408GLn` | **5803265299734043** | `app_id`, `client_pub_key` | amaç unknown (bir istemci public key'i gönderir); çağıran izlenmedi |
| `C37601GYc`, `GYd`, `GYe` | `GYd` **25453433540999208**, `GYe` **25974020015520396** (`GYc` kendi sınıfında id taşımaz) | `caller_name` `fx_waffle_contextual_pause_account_match`, `wa_waffle_certs`, `fx_waffle_foa_unpause` | Meta hesap bağlama yardımcıları |
| `C37605GYg`, `GYh`, `GYi` | **26573478745654327**, **26742313962085910**, **27503298369362501**, **28331348373116386**, **25840634418966704** | header `IG-Set-Waffle-Graphql-Access-Token`, anahtar `ACCESS_TOKEN` | Facebook / Instagram hesap bağlama; bağlı hesap token'ı gerekir (header ve anahtar adlarından inferred) |
| `C37413GLs` | **7236799486398397** | `batches`, `device_model`, `device_os`, `device_os_version`, `event_time`, `is_employee`, `primary_locale` | istemci olay batch'leri (değişken adlarından inferred) |

doc_id 6960707423955525 (eski build'ler için bildirilen eski bir itiraz mutation id'si) 2.26.41.6'da bulunmaz. İtiraz ve durum isteklerinin operasyon adları bu sınıflar tarafından taşınmaz (unknown).

[WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) bölüm 10'dan fark: `C37414GLt`, `C37409GLo` ve `C37604GYf` için host `graph.<pref_graphql_domain>`'dir (varsayılan `graph.whatsapp.com`); yalnızca yukarıda listelenen alt sınıflar bunu `facebook.com` olarak geçersiz kılar.

### 8.2 Kayıt zamanı veya oturumsuz çağrı noktası olan MEX operasyonları (found, şema `whatsapp-android-mex`)

doc_id'ler `assets/whatsapp-android-mex_client_persist_ids.json` dosyasından (ve belirtilen yerlerde `www` / `wamo` dosyalarından).

| Operasyon | doc_id | Çağrı noktası |
|-----------|-------:|-----------|
| `GetAutoConfConfidenceChallenge` | 25578301865133112 | `C40175Het`, `C40196HfI` (autoconf confidence ping'i) |
| `ValidateVerifierConfidence` | 25879669248324812 | `C40196HfI`, `C40197HfJ` |
| `FetchReachoutTimelockQuery` | 25627902213558773 | `RunnableC23952AUh` |
| `RemoveAccountReachoutTimelock` | 25040013452293167 | izlenmedi |
| `UserCountryCodeGet` | 25292528387076991 | `MexUserCountryCodeRepository` |
| `MobileConfigFetchQuery` | 29248978061376279 | izlenmedi |
| `SubmitAge`, `GetAgeExperience`, `SetAgeExperienceMutation` | 26049558371296621, 26567868986241476, 26051006311231325 | yaş akışları |
| `TosSetResult` | 25225843213776555 | şartların kabulü |
| `GetWaOldResponse` | 25784374561179853 | eski telefon üzerinden doğrulama |
| `WWWTriggerAcountRecovery` | 24896267680055094 | `AccountRecoveryManager` (değişkenler `nonce_encryption_key`, `use_case`, `registration_trace_id`, `request_id`) |
| `WWWCreateUser`, `WWWDeleteUser`, `WWWGetCertificates` | 8548056818544135, 7989555047767245, 25094190163544446 | hesap bağlama |
| `OhaiKeyConfigQuery` | 25069818679280758 | `N5I` (ACS / OHAI bootstrap'i) |
| `CreateEnforcementAppeal` | 26933630359642347 | newsletter enforcement istemcisi |
| `NewsletterCreateReportAppeal` (mex), `CreateGroupSuspensionAppealMutation` (www), `WamoReportPromoAppealV2Mutation` (wamo) | 27792557363683798, 25646047815072526, 26867425009592691 | itiraz operasyonları (hesaba bağlı; varlıklarda mevcut) |

MEX, sohbet bağlantısı (`WAChatdGraphQLClient`) üzerinden `<query query_id=...>` ile IQ `xmlns="w:mex"` olarak gönderilir (`C19370nI`). Bu operasyonların hesap öncesi bir oturumda çalışıp çalışmadığı belirlenmedi: bkz. 8.3.

### 8.3 JID'siz sohbet bağlantısı (found)

`ConnectionThread.connect` (`HandlerThreadC12340b0`) kendi JID'ini okur; null ise yalnızca companion-registration flag'i (`C06830Gm.A02()`) true ise devam eder, aksi halde ikinci bir JID kaynağını (`Ash()`) okur ve o da null ise `ConnectionThread/connect/ignored/jid null and not in companion reg` loglayıp döner. Dolayısıyla birincil telefon kaydı null-JID sohbet bağlantısı kullanmaz ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) bölüm 6.4 ile tutarlı). İkinci kaynağın anlamı inferred (saklanan veya bekleyen kayıt JID'i, çözülmedi). 8.2'deki kayıt zamanı MEX çağrılarını hangi oturumun taşıdığı unknown.

### 8.4 Kimliksizleştirilmiş istekler (found)

`PandoGraphQLRequest.requireAcsToken()` ve `requireOhaiConfig()` `C6GN` tarafından okunur; ACS token'ı veya OHAI config'i olmadan `@deidentified` işaretli bir istek exception fırlatır (`Request was marked with @deidentified, but no ... was provided`). `AcsOhaiConfig` alanları: proje adı, doc id, `graphQlUrl=https://acs.whatsapp.com/graphql`, surface, `tokenTtlSeconds`, `acsTokenMaxRedeemCount`. Hangi operasyonların flag'i taşıdığı `*_pando_flatbuffer_data.bin` varlıklarında kodlanmıştır: unknown.

---

## 9. Kod düzeyinde kontrolleri olan export edilmiş IPC yüzeyleri

Aksi belirtilmedikçe tüm girdiler manifest permission'ı olmadan export edilmiştir. Bu bölüm kodda bulunan kontrolleri listeler, güçlerine dair bir hüküm değildir.

### 9.1 `PhoneIdRequestReceiver` (`com.facebook.GET_PHONE_ID`)

Sıralı bir broadcast. Receiver sonuç extra'larından `auth` extra'ı olan bir `PendingIntent` okur ve `getCreatorPackage()` alır. Bir paket, imza sertifikası hash'i sabit kodlu bir izin kümesinde ise güvenilir sayılır (`AbstractC28130CKz.A04`, imza sertifikalarının SHA-1'i, değerler yeniden üretilmez; ikinci bir SHA-256 kümesi `CHA.A02` içinde kullanılır). Güvenilen bir çağıran, phone id'yi ve zaman damgasını broadcast sonucu olarak alır (`setResult(-1, id, {timestamp})`); flag **3651** izin verirse alternatif bir yol ikincil id'yi döndürür. Güven değişkeni etrafındaki decompile edilmiş kontrol akışı kısmidir, dolayısıyla kesin öncelik inferred.

### 9.2 Uygulama ailesi provider'ları (found)

| Bileşen | Bulunan kontroller |
|-----------|----------------|
| `FamilyAppsCredentialsProvider` | `getCallingPackage()`; seçim başına işleyici haritası; çağıran UID'si bir sertifikaya çözülür ve işleyicinin güvenilen kümesine karşı kontrol edilir (`C45775Jyk.A01`); link-manager uygunluğu (`WfalManager.A00`); feature flag'leri; link durumu işleyicinin uygun kümesinde olmalı; prefs `pref_foa_nta_ipc_bundle_auth_proof`, `pref_foa_nta_ipc_bundle`, `foa_nta_ipc_bundle_ttl` içinden 3 sütunlu bir cursor (auth proof, bundle, TTL) döndürür; süresi dolmuş veya eksik cache için hatalar. "NTA" açılımı unknown |
| `FamilyAppsUserValuesProvider` | tek seçim `foa_wo_wa_link_eligibility_values`, `getCallingPackage()` okunur |
| `WaAccountsCenterService` | action `com.whatsapp.wfl.OPERATION`; sınıf gövdesi decompile'da stub (kontroller unknown) |
| `QuickSendsContactsProvider` | `getCallingPackage()` doğrulama adımları loglanır (`validation_start` / `validation_end`); şifreli `.enc` fotoğraf dosyalarını ve kişi sütunlarını (`obfuscated_chat_id`, `display_name`, `profile_photo_uri`, `photo_key`) sunar |
| `OrbitSsoProvider` (`com.whatsapp.orbit.v2.sso`) | feature flag geçidi; çağıran paket bir izin listesinde olmalı (`AbstractC62035Rsx.A00`, aksi halde `SecurityException ... is not allowlisted`); herhangi bir metottan önce bir ön koşul kontrolü (`BS3()`); metotlar `get_profile` (`display_name`, `phone_number`, `avatar_uri`, `avatar_mime_type` döndürür), `get_accounts`, `get_nonce`, `get_token`; dosya yolu `avatar` salt okunur. İzin listesi `A01()` içinde paket adıyla eşleştirilir; sertifika kontrolü, varsa, bu metotta değildir (unknown). `BS3()` fonksiyonunun neyi test ettiği giriş durumu olarak inferred |
| `OrbitMessagesProvider` (`com.whatsapp.orbitmessages`) | dosya yalnızca `r` modunda, son segment `media`, `v1.` önekli `media_handle` değerleri AES-GCM ile çözülür; çağıran kontrolleri bulunamadı (unknown) |
| `OrbitCompanionLinkActivity` | `getCallingPackage()` ve extra `qr_data` okur; bekletme / onay zamanlayıcıları; `CompanionHelloConfirmationActivity` üzerinden yalnızca sonucu döndürür (`return_result_only`) |
| `InstrumentationService`, `InstrumentationAuthActivity`, `WhatsAppBugReportingBridgeActivity` | analiz edilmedi |

### 9.3 OTP el sıkışması (`OtpRequestedReceiver`)

Bir `PendingIntent` extra'sı `_ci_` (çağıran kimliği) ve isteğe bağlı bir UUID `request_id` (regex ile kontrol edilir) bekler. Oluşturan paketi üretilmiş bir değerle kaydeder, bir WAM olayı loglar ve flag **6617** açıksa veya paket config **7050** listesindeyse o pakete `request_id` taşıyan bir `com.whatsapp.otp.OTP_HANDSHAKE_CONFIRMATION` broadcast'iyle yanıt verir. Eksik `PendingIntent` reddedilir (`PendingIntent missing from handshake Intent`). Bu receiver'da kayıt kontrolü bulunamadı.

### 9.4 `AccountTransferReceiver`

Yalnızca `com.google.android.gms.auth.START_ACCOUNT_EXPORT` üzerinde, yalnızca cihazda güvenli keyguard varsa ve bir yetenek kontrolü geçerse (`AbstractC21360rJ.A01`) çalışır. Export'un kendisi arka plan executor'ında yürür (`C05X.A02(...).CVx`); içerik unknown.

---

## 10. Ban görünümü ve itiraz giriş noktaları

| Giriş | Mekanizma | Kanıt |
|-------|-----------|----------|
| WFAC durumunda soğuk başlangıç | `Main` durum 21, `HBC.A00` üzerinden `WfacBanActivity` başlatır | found (3.1) |
| `BanAppealActivity` | export edilmeyen; `Main` (extra `launch_source`) ve kalıcı ban akışı tarafından başlatılır | found |
| Ban durumu poll'u | Graph, `wfac_ban_status_token`, 5 sn throttle pref `wfac_last_ban_status_fetch_timestamp_ms` | found ([WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 2.2) |
| İtiraz gönderimi | şifreli `user_request` ile Graph (8.1) | found |
| Kayıt yanıtı | `/v2/register` alanları `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `custom_block_screen`, `version_upgrade` | found ([WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md) 3.3) |
| Destekle iletişim | `LoggedOutContactFormActivity` (bölüm 6), kayıt hataları için flag `IsRegistrationVerification` | found |
| Deep link'ler | `whatsapp://support`, `whatsapp://help`, `v.whatsapp.com` / `b.whatsapp.com` | found (4.2) |

İtiraz yolunun kullanıcı başına kimliği, sunucunun verdiği opak token'dır; telefon numarası veya cihaz id'si değildir (yukarıdaki token alan adları; türetme unknown).

---

## 11. Hata durumları ve tuzaklar

| Belirti | Neden | Notlar |
|---------|-------|-------|
| `ConnectionThread/connect/ignored/jid null and not in companion reg` | JID yok ve companion kaydı değil | kayıt öncesi normal; kayıt HTTPS kullanır |
| `FAIL_TO_INITIALIZE_WAMSYS` | native stack bootstrap'i başarısız (`ensureWamsysForRegBootstrapped`) | kayıt HTTP'si ve numara öncesi funnel logu atlanır |
| `DeepLinkActivity/deeplink not allowed before registration/` | link kodu geçit tarafından engellendi | izin listesi çözülmedi (4.3) |
| `Request was marked with @deidentified, but no ...` | ACS / OHAI config'i eksik | istek gönderilmedi |

---

## 12. Temel ayrımlar

| Karıştırmayın | Gerçek |
|----------------|------|
| Export edilmiş vs hesapsız erişilebilir | 97 export edilen girdi; çoğu kayıtlı hesap olana kadar yararlı bir şey yapmaz; yalnızca 2.2 ve 4.2'deki girdilerde kayıt durumu işleme vardır |
| Uygulama token'ı vs kullanıcı token'ı | derlenmiş `WA|<app_id>|<secret>` uygulamayı tanımlar; ban çağrıları kullanıcı oturumu değil, opak bir istek token'ı ekler |
| `fdid` vs reklam id'si | `fdid` yeniden kayıttan sağ çıkan, uygulamanın ürettiği bir UUID'dir; reklam id'si Google değeridir |
| Oturumsuz destek formu vs uygulama içi destek | form yazılan alanlarla `www.whatsapp.com/contact/noclient/verification/` adresine gönderir; uygulama içi destek oturumu kullanır (analiz edilmedi) |
| Kayıt HTTP'si vs sohbet bağlantısı | kayıt HTTPS `/v2/*`'dir; null-JID sohbet bağlantısı yalnızca companion kaydı içindir |

---

## 13. Tam akış

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

## 14. Bilinmeyenler

| Soru | Neden unknown |
|----------|-------------|
| Kayıt öncesi hangi link kodlarına izin verilir | izin listesi sınıfı yeniden çözülmedi; işleyiciler durumu tek tek kontrol eder, yalnızca dördü izlendi |
| Neden 0'ın (`not_allowed_before_registration`) üreticisi | büyük `DeepLinkActivity` switch'inde izole edilemedi |
| `/v2/*`, `ENC`, `H` sabitleri için host ve yol birleştirme | wamsys / Kotlin istek oluşturucuları okunmadı |
| Kayıt zamanı MEX operasyonlarını hangi oturum taşır | null-JID bağlantısı companion kaydı dışında reddedilir; `Ash()` kaynağı çözülmedi |
| Oturumsuzken log yüklemelerindeki `from_jid` içeriği | `AbstractC05620Al.A0G` soyuttur |
| Token'ların, kodların, itiraz payload'larının sunucu doğrulaması | sunucu tarafı |
| `@deidentified` taşıyan operasyonlar | `*_pando_flatbuffer_data.bin` içinde, şema yok |
| "NTA" anlamı, ikincil id `phoneyid_id` üreticisi, `c2dm_reg_id`'nin istek alanı olarak durumu | yalnızca adlar |
| `HomeActivity`'nin kayıtsızken başlatılıp başlatılamayacağı ve ne yaptığı | üst sınıf geçidi çözülmedi |
