<!-- src-sha1: b8a925dee480430088a421b7aba690bc2f641a5f -->
# WhatsApp Hesap Güvenliği — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-22
**Kapsam:** mevcut bir hesaba telefon numarası doğrulaması (`/v2/*` kayıt HTTP'si), ikinci faktör yöntemleri, iki adımlı doğrulama PIN'i ve kurtarma e-postası, hesap parolası (`#PWD_WA` zarfı, canonical-user bağımlılığı), OPAQUE / VOPRF native kodu ve fiilen neye hizmet ettiği, passkey ile giriş ve yönetim, güvenilir cihazlar, hesap kurtarma (canonical user nonce değişimi), soft logout / login-back, w:mex işlemleri (doc_id'ler, değişkenler, yanıt kökleri), feature flag'ler, Baileys notları

---

## 1. Nedir (teknik olarak)

Android istemcisinde "hesap güvenliği" tek bir alt sistem değildir. Telefon numarası kayıt akışının üzerine yerleştirilmiş beş bağımsız mekanizmadır. Tüm ifadeler çözülmüş (decompiled) APK'nın statik analizine dayanır; ağ üzerinde hiçbir şey yakalanmadı. Katman: **found** = kodda veya asset'lerde okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi. Karartılmış (obfuscated) adlar derlemeye özgüdür ve 2.26.41.6 içinde yeniden çözümlendi.

| Mekanizma | Nerede uygulanır | Kimlik bilgisi | Ana istemci sınıfları (2.26.41.6) |
|-----------|---------------------|------------|-------------------------------|
| Telefon doğrulaması (OTP) | kayıt HTTP'si, `/v2/exist` → `/v2/code` → `/v2/register` | SMS / sesli arama / flash / eski cihaz / e-posta OTP / sessiz kimlik doğrulama | `K49` (`RegistrationHttpManager`), `KotlinRegistrationBridge`, `AbstractC45307Jps` |
| Kayıtta ikinci faktör | `/v2/register` reason `security_code`, ardından `VerifyTwoFactorAuth` | 6 haneli PIN, hesap parolası, e-posta OTP | `VerifyTwoFactorAuth`, `EnumC43759JAu`, `HOZ` |
| İki adımlı doğrulama (PIN + e-posta) | IQ `urn:xmpp:whatsapp:account` `<2fa>` | 6 haneli PIN, isteğe bağlı kurtarma e-postası | `C1DP` (`TwoFactorAuthManager`), `C1DT` (`TwoFactorXmppMethods`) |
| Hesap parolası | w:mex (`whatsapp-android-mex`, `whatsapp-android-www`) | 8-20 karakter, harf + rakam | `PasswordRepository`, `PasswordServerApiImpl`, `CanonicalPasswordService` |
| Passkey (WebAuthn) | girişte `/v2/passkey_auth`; yönetim için IQ `passkey` veya w:mex | Credential Manager üzerinden platform passkey'i | `PasskeyServerApiImpl`, `PasskeyCreateFlow`, `PasskeyVerifier`, `K15` |
| Güvenilir cihaz | w:mex | hash'lenmiş `ANDROID_ID` ile anahtarlanan sunucu tarafı kayıt | `TrustedDevicesServerApiImpl`, `RegTrustedDeviceGraphQLHelper` |
| Soft logout / login-back | w:mex | yok (durum bayrağı) | `LogoutManager`, `LogoutPushManager` |
| Hesap kurtarma | w:mex, Meta canonical user | istemcinin ürettiği bir sırrın RSA/AES zarfı | `AccountRecoveryManager` |

Raporun tamamını belirleyen iki nokta:

- `libwhatsapp.so` içindeki OPAQUE durum makinesi hesap parolasına değil, **uçtan uca şifreli yedek** parolasına (`encb/*` handler'ları) bağlıdır (bölüm 6).
- Bu derlemede hesap parolası, `XfbWaCreatePasswordMutation` / `XfbWaChangePasswordMutation` ile bir RSA/AES zarfı (`#PWD_WA:11`) kullanılarak oluşturulur ve değiştirilir; bunun için uygulamanın Meta canonical-user kimlik bilgilerine sahip olması gerekir (bölüm 5).

---

## 2. Taşıyıcılar ve işlem kataloğu

### 2.1 Dört taşıyıcı

| Taşıyıcı | Kullanım | Kanıt |
|-----------|----------|----------|
| HTTPS `/v2/<name>` (kayıt yığını) | telefon doğrulaması, girişte ikinci faktör, passkey assertion, cihaz onayı | found: `AbstractC45307Jps` içindeki yol sabitleri (bölüm 3.1) |
| IQ `xmlns="urn:xmpp:whatsapp:account"` | PIN / e-posta set, check ve get; hesap e-postası OTP; kullanıcı adı vb. | found |
| IQ `xmlns="passkey"` (smax id 125, 126, 129) | eski passkey start / finish / clear | found, flag 10452 / 10453 / 10461 ile kapılı |
| IQ `xmlns="w:mex"` | aşağıdaki tüm GraphQL işlemleri | found |

### 2.2 w:mex zarfı ve doc_id kaynağı

Değişkenler JSON olarak gönderilir. Hemen hemen her mutation alanlarını tek bir nesneye sarar: yardımcı `AbstractC197058a0.A17(obj, vars)` nesneyi `input` anahtarı altında saklar (found). İstisnalar: iki `Xfb*` parola mutation'ı `encrypted_password` değerini `data` altına koyar (found); `PasskeyDeleteMutation` da `input` kullanır (`c16770ig.A00(obj, "input")` üzerinden).

doc_id'ler kodda sabit değer olarak bulunmaz. İstemci işlem adını ve bir yapılandırma adını (`whatsapp-android-mex`, `whatsapp-android-www`, `whatsapp-android-facebook-schema`) gönderir; sayısal id `assets/whatsapp-android-{mex,www,facebook-schema}_client_persist_ids.json` dosyalarından okunur (found). Aşağıdaki her doc_id 2.26.41.6 içinde bu asset'lerden okundu ve işlem adı bir çağrı noktasıyla doğrulandı. Hiçbiri `tested` değildir.

### 2.3 İşlem kataloğu (çağrı noktaları mevcut)

Değişkenler, aksi belirtilmedikçe `input` içindedir. "Kök", istemcinin okuduğu yanıt nesnesinin adıdır.

| İşlem | doc_id | Yapılandırma | Değişkenler | Kök ve okunan alanlar |
|-----------|--------|--------|-----------|----------------------|
| `HasPasswordQuery` | `25379221318423478` | mex | yok | `xwa2_has_password`: `has_password`, `upgrade_needed` |
| `DeletePasswordMutation` | `27247058691550586` | mex | yok | `xwa2_delete_password`: `success`, `twofa_auto_disabled`; hata 409 "e-posta gerekli" anlamına gelir |
| `GetTwofaQuery` | `27608881388708005` | mex | `device_id` | `xwa2_get_twofa`: `twofa_enabled`, `twofa_methods[]{method,value,state}`, `is_device_trusted`, `latitude`, `longitude` |
| `SetTwofaMutation` | `28092515560345874` | mex | `twofa_enabled` (bool), `device_id` | `xwa2_set_twofa`: `success`, `twofa_already_enabled`, `is_device_trusted` |
| `WaPasswordEncryptionKeyQuery` | `27318258844468227` | www | yok | `wa_password_encryption_key`: `public_key` (PEM), `key_id` |
| `XfbWaCreatePasswordMutation` | `36595298760118580` | www | `data.encrypted_password` (`input` altında değil) | `xfb_wa_create_password` (başarı / hata alanları çözülmedi) |
| `XfbWaChangePasswordMutation` | `27534818572826036` | www | `data.encrypted_password` | `xfb_wa_change_password` |
| `AddTrustedDeviceMutation` | `24522952587403287` | mex | `device_id`, `device_name` | `xwa2_add_trusted_device.list_of_trusted_device[]` |
| `UntrustTrustedDeviceMutation` | `26574930682133620` | mex | `device_id`, `reason` (tek çağrıda `"REREG"`) | kök çözülmedi |
| `DeleteTrustedDeviceMutation` | `33867503889559538` | mex | `device_id` | `xwa2_delete_trusted_device` (bool) |
| `GetTrustedDevicesQuery` | `27391232653862770` | mex | `device_id` | `xwa2_get_trusted_devices.list_of_trusted_device[]`: `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` |
| `WhatsappTrustedDeviceRegistration` | `27335489319457030` | facebook-schema | `client_mutation_id`, `payment_type="TRUST_BINDING"`, `platform_trust_token`, null `actor_id` / `logging_id` / `product_id` | ödeme trust binding'i (`RunnableC53437NtS`), giriş için güvenilir cihaz değil |
| `RegistrationPasskeyStartRegisterMutation` | `25415371271434748` | mex | yok | `xwa2_passkey_start_register.credential_create` (string) |
| `RegistrationPasskeyFinishRegisterMutation` | `24611221275218156` | mex | `credential`, `key_attestation` | `xwa2_passkey_finish_register` (bool) |
| `RegistrationPasskeyEnableMutation` | `25147880151540247` | mex | `credential` | `xwa2_passkey_enable` (bool) |
| `RegistrationPasskeyClear` | `25111972538494859` | mex | yok | `xwa2_passkey_clear` (bool) |
| `RegistrationPasskeyUpdateClientEncryptionStatusMutation` | `24866837389649930` | mex | `credential`, `status` (true) | `xwa2_passkey_update_client_encryption_status` (bool) |
| `PasskeyListExistResponseQuery` | `26930537423220681` | mex | yok | `xwa2_passkey_exist_v2`: `result`, `uuid`, `passkeys[]{credential,create_ts_s,used_ts_s,password_manager,aaguid,usecases,is_disabled}` |
| `PasskeyDeleteMutation` | `25225683640428243` | mex | `credential_ids` (liste) | `xwa2_passkey_delete.credential_ids` |
| `AccountLoginMutation` | `27298465499757127` | mex | `phone_number` (ham JID string'i) | okunmuyor |
| `AccountLogoutMutation` | `26863447609979194` | mex | `enabled_biometric` (bool), `phone_number` | okunmuyor; 5 sn istemci zaman aşımı |
| `WWWTriggerAcountRecovery` | `24896267680055094` | mex | `nonce_encryption_key` (base64 PEM), `use_case`, `registration_trace_id`, `request_id` | nonce bildirimle iletilir (bölüm 9) |
| `WWWExchangeNonceForAccessToken` | `25727187160203620` | mex | `nonce`, `use_case`, `encrypted_password`, `request_id`, `registration_trace_id` | erişim token'ı |
| `WWWGetNonceForCompanionDevice` | `24635485196143064` | mex | `fbid`, `nonce_encryption_key`, `encrypted_password`, `request_id`, `registration_trace_id` | companion canonical user |
| `RegAccountTransferVerifyTokenMutation` | `7580940708621318` | mex | `token` | hesap aktarımı OTP kontrolü, 60 sn zaman aşımı |
| `ValidateVerifierConfidence` | `25879669248324812` | mex | `authResponse` (base64) | autoconf güven ping'i |
| `GetRegistrationUpsells` / `GetDynamicRegistrationUpsells` / `RegistrationDynamicUpsellShown` | `24265038133175291` / `32273353145641323` / `25435755019399064` | mex | shown: `input="PASSKEYS"` (string) | kayıt upsell zamanlaması |

### 2.4 Bu derlemede çağrı noktası olmayan, asset'lerdeki işlemler

`java_src` ve smali içinde ada göre arandı; referans yok (found). Değişkenleri ve yanıtları bilinmiyor.

| İşlem | doc_id |
|-----------|--------|
| `SetPasswordMutation` | `33855141324134176` |
| `CheckPasswordMutation` | `26881928138061632` |
| `PasskeyExistResponseQuery` | `25188064727509430` |
| `PasskeyRequestChallengeMutation` | `26311497405176139` |
| `PasskeyVerifyChallengeMutation` | `26876394218624479` |
| `RegistrationPasskeyDisableMutation` | `27775237998742831` |

2.26.41.6 içinde passkey ile giriş request / verify mutation'larını kullanmaz; `/v2/passkey_auth` kullanır (bölüm 7.1). Ödemeler (`PaymentsPasskey*`) ve Brezilya (`BrPasskey*`) passkey işlemleri ayrı yüzeylerdir ve kapsanmamıştır.

---

## 3. Mevcut bir hesaba telefon numarası doğrulaması

### 3.1 Kayıt yığını ve endpoint'ler

`K49` (`RegistrationHttpManager`) istekleri oluşturur ve sonuçları ayrıştırır. İki HTTP yığını vardır: Kotlin köprüsü (`KotlinRegistrationBridge`, `RetryingHttpClient`) ve `AbstractC45509Jtc` ile `JniBridge.jvidispatch*` üzerinden erişilen native bir `wamsys` istemcisi. Seçici `K49.A0b`, yapılandırma 24762 veya flag **24763** ayarlıysa true döndürür (found); log etiketleri `/kotlin` veya `/wamsys` ile biter.

Yollar `AbstractC45307Jps` içinde XOR 0x12 ile karartılmıştır ve şuna çözülür (found):

| Yol | Kotlin fonksiyonu | Gönderilen alanlar (cihaz / e2e alanlarının dışında) |
|------|-----------------|------------------------------------------|
| `/v2/exist` | `performSameDeviceCheck` / `checkIfExists` | `lg`, `cc`, `in`, `foa_backup_token`, `client_capabilities`, `advertising_id`, `context`, `id`, `backup_token` |
| `/v2/challenge` | `challengeRequest` | giriş challenge'ı; yanıt `login`, `challenge`, `retry_after` |
| `/v2/code` | `generateAuthCode` | `token`, `method`, `context`, `advertising_id`, `clicked_education_link`, `manage_call_permission`, `call_log_permission`, `client_start_message` |
| `/v2/register` | `registerPhoneNumber` | `code`, `auth_response` (bayt), `method`, `context`, `advertising_id`, ayrıca `security_code`, `reset`, `wipe_token`, `cred_token` gibi map girdileri |
| `/v2/security` | `verifySecurityCode` | `code`, `reset`, `wipe_token` (eski yol, flag 26215 kapalı) |
| `/v2/passkey_auth` | `passkeyAuth` | `lg`, `context`, `credential` (assertion sonucu) |
| `/v2/device_logout_send`, `/v2/device_logout_fetch` | `sendAccountDefenceDeviceConfirmation`, `fetchAccountDefenceDeviceConfirmation` | `token` |
| `/v2/wfs` | `wfsAuth` | Meta SSO ("WFS") kimlik doğrulaması, yanıt `login`, `wa_ac_machine_id`, `lid` |
| `/v2/consent`, `/v2/client_log`, `/v2/pre_pn_client_log`, `/v2/autoconf`, `/v2/autoconf_verifier`, `/v2/invite_preview`, `/v2/reg_onboard_abprop` | onay, huni logları, sessiz doğrulama, AB prop'ları | güvenliğe özgü değil |

### 3.2 Adımlar

| # | Adım | Kanıt |
|---|------|----------|
| 1 | `/v2/exist` hesap durumunu döndürür: hangi OTP yöntemlerinin uygun olduğu, bekleme süreleri, `second_factor_methods`, `is_device_trusted`, `passkey_auth_challenge`, `password_eligible`, wipe durumu | found (3.3) |
| 2 | `passkey_auth_challenge` mevcutsa ve süresi dolmamışsa passkey ile giriş sunulur (bölüm 7.1) | found |
| 3 | Kullanıcı bir yöntem seçer; `method` ile `/v2/code` | found |
| 4 | Kullanıcı OTP'yi yazar; `code` ve `method` ile `/v2/register` | found |
| 5 | `status=ok` kaydı sonlandırır (`login`, `lid`, `ent_access_token`, `ent_canonical_fbid` sonuçtan okunur). `status=fail` bir reason ile gelir (3.5) | found |
| 6 | Reason `security_code`, hesabın ikinci faktörü olduğu anlamına gelir: `VerifyTwoFactorAuth` PIN, parola veya e-posta OTP'sini toplar ve `/v2/register` çağrısını yeniden yapar (3.6) | reason adı found; gezinme inferred |
| 7 | Başarıdan sonra: `RegisterName`, güvenilir cihaz kaydı (bölüm 8), passkey upsell (bölüm 7.2) | found |

"Mevcut hesap" ayrı bir API değildir: sunucu, hesabı zaten olan bir numara için `/v2/exist` ve `/v2/register` çağrılarını aynı status / reason sözlüğüyle yanıtlar. `possible_migration`, `need_chat_restore_pn_verify`, `acc_tr_eligible` (hesap aktarımı) ve `wa_old_eligible` (eski telefon üzerinden doğrulama) gibi alanlar, sunucunun mevcut hesap akışlarını aynı iki çağrı üzerinden yönlendirdiğini gösterir (alanlar found, anlamları adlardan inferred).

### 3.3 İstemcinin okuduğu `/v2/exist` yanıt alanları

| Alan | Tür | Kullanım |
|-------|------|-----|
| `status` (`ok`/`fail`), `reason` | string | sonuç |
| `login`, `lid` | string | istemciye döndürülen hesap tanımlayıcıları (tüketici izlenmedi) |
| `is_device_trusted` | bool | `pref_is_device_trusted` olarak saklanır; güvenilir cihaz onay kutusunu gizler |
| `second_factor_methods` | string dizisi | `pref_second_factor_methods` olarak saklanır; değerler `EnumC43759JAu` wire string'leridir |
| `passkey_auth_challenge`, `passkey_credential` | string | challenge zaman damgasıyla `reg_passkey_auth_challenge` olarak saklanır; credential id ipucu |
| `password_eligible` | int | parola upsell uygunluğu |
| `sms_wait`, `voice_wait`, `wa_old_wait`, `email_otp_wait`, `send_sms_wait`, `silent_auth_wait`, `retry_after` | string | kanal başına bekleme süreleri |
| `sms_length`, `voice_length`, `wa_old_length`, `email_otp_length` | int | beklenen kod uzunluğu |
| `email_otp_eligible`, `wa_old_eligible`, `silent_auth_eligible`, `carrier_silent_auth_eligible`, `send_sms_eligible`, `acc_tr_eligible` | int | yöntem uygunluğu |
| `email`, `wa_old_device_name` | string | maskelenmiş e-posta / eski cihaz etiketi (maskeleme doğrulanmadı) |
| `reset_method`, `wipe_type`, `wipe_token`, `wipe_wait`, `wipe_expiry_time`, `server_time` | karışık | PIN'imi unuttum akışı (3.7) |
| `fallback_methods`, `recommended_method`, `num_visible_dbs_methods` | dizi / int | arayüz sıralaması |
| `ent_access_token`, `ent_canonical_fbid` (`/v2/register` içinde) | string | Meta canonical-user kimlik bilgileri |
| `violation_type`, `violated_policy`, `appeal_token`, `in_app_ban_appeal`, `version_upgrade`, `custom_block_screen` | karışık | yasak / yükseltme ekranları (bkz. ban raporu) |

### 3.4 OTP yöntemleri

Sunucu güdümlü kod isteme sayfası (`RequestServerDrivenOtpCodeBottomSheetFragment`, `C46760Kbq`) şu `method` string'lerini sunar (found): `sms`, `voice`, `flash`, `wa_old`, `email_otp`, `password`, `passkey`, `send_sms`. `silent_auth` ve `account transfer` kendi uygunluk alanlarına sahiptir.

### 3.5 `/v2/register` hata reason'ları (`KotlinRegistrationBridge` içindeki ayrıştırıcı)

| `reason` | Anlam (found: ad; anlam inferred) |
|----------|-----------------------------------------|
| `incorrect` | yanlış kod veya yanlış PIN |
| `security_code` | ikinci faktör gerekli |
| `second_code`, `device_confirm_or_second_code` | ikinci faktör veya cihaz onayı gerekli |
| `too_many_guesses`, `guessed_too_fast` | tahminlerde oran sınırı; `guess_wait` döndürülür |
| `stale`, `mismatch`, `missing`, `format_wrong` | kodun süresi dolmuş / eşleşmiyor / yok / hatalı biçimli |
| `sms_required` | SMS ile doğrulanmalı |
| `blocked`, `not_allowed`, `limited_release` | yasaklı, izin verilmiyor, kademeli yayın kapısı |
| `temporarily_unavailable` | geçici |
| `challenge` | challenge turu gerekli (`/v2/challenge`) |
| `reset_too_soon` | PIN'imi unuttum sıfırlaması çok erken istendi |
| `consent`, `consent_parent_linking_already_registered` | onay ekranları |

### 3.6 İkinci faktör yöntemleri

`EnumC43759JAu` (found): `twofac_pin`, `password`, `email_otp`, `oauth_email`, `sms`, `voice`, `flash`, `wipe_full`, `wipe_offline`. Flag **28755** ile ekran `second_factor_methods` tarafından yönlendirilir ("dynamic 2FA", bağlam string'i `twofac_dynamic`) ve "başka bir yolla doğrula" `Dynamic2faMethodSelectionBottomSheet` açar.

`K49.A0o` (`verifySecurityCode`):

| Koşul | Wire |
|-----------|------|
| flag 26215 kapalı | eski: `code` ile `/v2/security` (sıfırlama sırasında `reset` ve `wipe_token` ile) |
| flag 26215 açık, yöntem `password` değil | `/v2/register` ile `security_code` = istek map'inde düz metin sır, `method` |
| flag 26215 açık, yöntem `password` | parola önce `HOZ.A08` ile `#PWD_WA:11:<epoch>:<blob>` biçiminde şifrelenir (bölüm 5.3); blob, `/v2/register` isteğinin `code` konumunda gönderilir; şifreleme başarısız olursa QPL `PASSWORD_ENCRYPT_FAILED` bildirir |

Zarfın anahtarı `CanonicalPasswordService.A04(..., true)` aracılığıyla `WaPasswordEncryptionKeyQuery` ile gelir (`C47204KjV` içinden çağrılır, found). Blob'u wire üzerinde tam olarak hangi istek alanının taşıdığı, yakalanmış bir istekten değil kurucu argüman sırasından okundu (inferred).

### 3.7 PIN'imi unuttum, wipe ve e-posta ile sıfırlama

`/v2/exist` veya `/v2/register` şunları döndürebilir: `reset_method`, `wipe_type` (`offline` veya `full`), `wipe_wait` (saniye), `wipe_token`, `wipe_expiry_time`, `server_time` (found). `VerifyTwoFactorAuth.A03` bunları dört duruma eşler (found): 0 izin yok, 1 bekleme süresinde ("0_7 days, offline_info"), 2 `offline` ("7_30"), 3 `full` ("over 30"). Sıfırlama çağrısı `reset=<mode>` ve `wipe_token` gönderir; `wipe_full` ve `wipe_offline` ikinci faktör yöntemleridir (3.6). Sunucunun `offline` ile `full` wipe'ta neyi sildiği bilinmiyor.

---

## 4. İki adımlı doğrulama (PIN) ve kurtarma e-postası

### 4.1 İstemci durumu

`C1DP` (`TwoFactorAuthManager`) PIN'i yerel olarak tutar (found): pref `two_factor_auth_code`, isteğe bağlı olarak şifreli (`two_factor_auth_using_encryption`, `C1DP.A01` tarafından bir keystore yardımcısı üzerinden çözülür). Periyodik "PIN'inizi doğrulayın" uyarısı için kullanılır: uyarı aralıkları 6 sa, 12 sa, 1 g, 1 g, 3 g, 7 g (`C1DP.A0I`, pref'ler `two_factor_auth_nag_time`, `two_factor_auth_nag_interval`). Diğer pref'ler: `two_factor_auth_email_set`, `two_factor_auth_dynamic_validated`, `two_factor_auth_last_code_correctness`, `pref_2fa_{sms,voice,flash,email_otp}_wait_time`.

### 4.2 IQ stanza'ları (`xmlns="urn:xmpp:whatsapp:account"`, 32 sn zaman aşımı)

| Eylem | Stanza | Okunan yanıt | Sınıf |
|--------|--------|---------------|-------|
| Durumu al (smax 114) | `type=get` `<2fa/>` | `<2fa>`: `code` alt öğesinin bulunması PIN'in ayarlı olduğu anlamına gelir; `email` alt öğesinin bulunması `two_factor_auth_email_set` değerini ayarlar | `C1DT.A00`, `C28896Cgx` |
| PIN / e-posta ayarla | `type=set` `<2fa><code>PIN</code><email>addr</email></2fa>` (her alt öğe isteğe bağlı) | başarı pref'leri yazar; hata kodu + metni dinleyicilere iletilir | `C1DP.A07`, `C28899Ch0` |
| PIN kontrol | `type=get` `<2fa><code>PIN</code></2fa>` | `code` içeren `<2fa>` doğru anlamına gelir | `VerifyTwoFactorAuthCodeDialogFragment` yolu, `HandlerC25225AtN` |

PIN 6 hanelidir (`SetCodeFragment`, uzunluk kontrolü `== 6`). Set tip 1, onay tip 2'dir. `Fetch2FAEmailStatusJob`, e-postanın doğrulanıp doğrulanmadığını görmek için durumu yeniden okur (32 sn). Sunucunun `code` / `email` alt öğelerinden fazlasını döndürüp döndürmediği bilinmiyor.

### 4.3 Hesap e-postası OTP'si (`<2fa><email>`'den ayrı)

`C31107Dfz` oluşturur, `KRB` ayrıştırır (log öneki `EmailVerificationXmppMethods`):

| Adım | Stanza | Yanıt |
|------|--------|----------|
| OTP iste | `type=set` `<verify_email><lg/><lc/></verify_email>` (dil / yerel ayar, 2-3 karakter) | `verify_email.wait_time` |
| OTP doğrula | `type=get` `<verify_email><code>NNNNNN</code></verify_email>` (6 karakter) | `verify_email.code_match` (`true`/`false`), `wait_time` |

E-posta adresinin kendisi bu stanza'larda yoktur (daha önce ayarlanır, yol izlenmedi). `VerifyEmailActivity` ve `email_otp` ikinci faktörü tarafından kullanılır.

### 4.4 PIN, parola ve GetTwofa karşılaştırması

`GetTwofaQuery`, `twofa_methods[]{method,value,state}` döndürür. `PasswordUpsellEligibility` bu listede `password` ve `pin` string'lerini arar (found). `SetTwofaMutation` yalnızca bir parola oluşturulduktan sonra, hash'lenmiş cihaz id'siyle, en iyi çaba (best effort) esasına göre çağrılır (bölüm 5.2); `twofa_auto_enabled` / `twofa_auto_disabled` sonuç bayraklarıdır. PIN'in kendisi w:mex üzerinden asla gönderilmez.

---

## 5. Hesap parolası

### 5.1 Varlıklar

| Varlık | Rol |
|--------|------|
| `PasswordRepository` | orkestrasyon: `setPassword`, `getTwofa`, cihaz id'si (`computeDeviceId`) |
| `PasswordServerApiImpl` | `HasPasswordQuery`, `DeletePasswordMutation`, `GetTwofaQuery`, `SetTwofaMutation` |
| `CanonicalPasswordService` | anahtar getirme, `A03` oluşturma, `A02` değiştirme (`Xfb*` mutation'ları, şema `whatsapp-android-www`) |
| `HOZ` | zarf şifreleme (`A08` → `#PWD_WA:11`) |
| `PasswordCredentialManager` | kimlik bilgisini Android Credential Manager'a kaydeder (`saveCredential`, E.164 numarası yoksa atlanır) |
| Arayüz | `CreatePasswordActivity`, `ReplacePinWithPasswordActivity`, `PasswordUpgradeFragment`, `SettingsPassword`, `TrustThisDeviceActivity` |

### 5.2 Ayarla / değiştir / sil

`PasswordRepository.setPassword` önce canonical kimlik bilgilerine ihtiyaç duyar; bunlar yoksa "No canonical credentials available to set password" ile başarısız olur (found). Yani parola yalnızca WhatsApp numarasına değil, Meta canonical user'a bağlanır.

```
setPassword(pw, isChange, enableTwofa)
  isChange  -> CanonicalPasswordService.A02  XfbWaChangePasswordMutation
  !isChange -> CanonicalPasswordService.A03  XfbWaCreatePasswordMutation
               then, if enableTwofa: GetTwofa/SetTwofa best effort (device_id = base64(SHA-256(ANDROID_ID)))
each: A04 = key fetch (WaPasswordEncryptionKeyQuery) + HOZ.A08 -> data.encrypted_password
```

`device_id`, `K2M.A01(android_id)` yani `Settings.Secure.ANDROID_ID` değerinin SHA-256'sının Base64'üdür (flag 2, wrap yok) (found). Silme değişken göndermez; HTTP benzeri kod 409, "engellendi, e-posta gerekli" sonucuna eşlenir (found). `CreatePasswordActivity` içindeki yerel kurallar: uzunluk 8 ila 20, en az bir harf ve bir rakam, onay eşleşmeli (found).

### 5.3 `#PWD_WA:11` zarfı (`HOZ.A02` / `A08`)

```
epoch   = current time in seconds
aesKey  = random 32 B (AES-256)         iv = random 12 B
ct||tag = AES-GCM(aesKey, iv, utf8(secret))    // no AAD on this path
wrapped = RSA/ECB/PKCS1Padding(serverPublicKey, aesKey)
blob    = 0x01 | key_id(1 B) | iv(12) | len(wrapped) as uint16 LE | wrapped | tag(16) | ct
out     = "#PWD_WA:11:" + epoch + ":" + base64(blob, URL_SAFE | NO_WRAP | NO_PADDING)
```

`key_id` 1 ile 255 arasında olmalıdır (`CanonicalPasswordService.A01`). RSA anahtarı PEM'den X.509 SPKI olarak ayrıştırılır; PKCS1 yolu modül boyutunu denetlemez (≥ 4096 bit testi yalnızca farklı bir OAEP varyantı olan `HOZ.A06` içinde vardır). Aynı zarf üç yerde kullanılır (found): kayıt ikinci faktörü (3.6), canonical oluşturma / değiştirme (5.2) ve kurtarma (`exchangeNonce`, bölüm 9, JSON `{version:1,timestamp,password}` içine sarılı).

`HOZ` içindeki diğer varyantlar (`#PWD_WA:11` değil): `A03` ve `A06` sıfır IV ve AAD ile RSA-OAEP-SHA-256 kullanır (Waffle SSO yolu `C40069Hd8` / `C40090HdT` içinde `#PWD_WAFFLE` yazar).

---

## 6. OPAQUE, VOPRF ve native kripto

### 6.1 Mevcut olanlar

| Öğe | Nerede | Katman |
|------|-------|------|
| `WESOpaqueClientRegistrationStartResult` (.rodata `0xaebae`), `...LoginStartResult` (`0xaebd5`), `...RegistrationFinishResult` (`0xaeda9`), `...LoginFinishResult` (`0xaedd1`), `...RegistrationState` (`0x115042`), `...LoginState` (`0x115072`) | `libwhatsapp.so` string'leri | found |
| `OPAQUE_PBKDF2_SALT` (`0x17e129`), `VOPRF06-HashToGroup-` (`0x19465a`), `VOPRF06-Finalize-` (`0x19466f`) | `libwhatsapp.so` string'leri | found |
| `org/whispersystems/curve25519/NativeVOPRFExtension` | aynı kütüphane; Java sınıfında `nativeBlind`, `nativeUnBlind`, `nativePcdBlind` var | found |
| `libvoprf-ed25519.so`, `libvoprf-ristretto.so` | ayrı kütüphaneler, yalnızca `JNI_OnLoad` export eder; Java sarmalayıcıları `com.facebook.privacy.acs.VoprfEd25519` / `VoprfRistretto` | found |

### 6.2 String'lere başvuran fonksiyonlar (arm64, vaddr)

| Fonksiyon | Boyut | İçerik | Katman |
|----------|------|---------|------|
| `fcn.0075a1c0` | 644 B | `VOPRF06-HashToGroup-` değerine başvurur; mbedTLS SHA-512 init / update ×6 / finish, ardından ikinci bir SHA-512 geçişi | found |
| `fcn.0075b550` | 712 B | `VOPRF06-Finalize-` ve `OPAQUE_PBKDF2_SALT` değerlerine başvurur; finalize transkripti üzerinde SHA-512, ardından `mbedtls_pkcs5_pbkdf2_hmac` | found |
| `fcn.0075a618`, `fcn.0075ad40` | - | ikisi de `fcn.0075b550` fonksiyonunu çağırır, ardından `mbedtls_hkdf_extract` + üç `mbedtls_hkdf_expand` (md tipi `0xb`) | found |
| `fcn.0075a0d4` | - | `fcn.0075a1c0` fonksiyonunu çağırır | found |

`fcn.0075b550` içindeki PBKDF2 çağrısı (disassembly): parola uzunluğu `0x40` (64 B, OPRF çıktısı), salt uzunluğu `0x12` = 18 = `OPAQUE_PBKDF2_SALT` etiketinin uzunluğu ve tampon bu etiketten başlatılır, türetilen uzunluk `0x40`, iterasyon sayısı çağırandan geçirilir (bu fonksiyonda sabit değil), md tipi `0xb`. Md tipi `0xb`, mbedTLS 3.6 numaralandırmasında SHA-512'ye eşittir (enum değerinden ve 64 baytlık uzunluklardan inferred). Yani OPRF çıktısı, ASCII etiketi salt olarak kullanan PBKDF2-HMAC-SHA-512'ye beslenir (çağrı şekli için found, hash için inferred).

Fonksiyonların rolleri (blind, finalize, registration-finish, login-finish) çağrı şeklinden inferred. Grup / şifre takımı (curve, `VOPRF06-` öneklerine eklenen id), KE1 / KE2 / KE3 bayt düzenleri, zarf içeriği ve AKE varyantı **unknown**; native kod, belirtilen fonksiyonların disassembly'si olarak okundu, decompile edilmedi.

### 6.3 Kim çağırıyor: şifreli yedek, hesap parolası değil

Durum makinesinin Java girişi şifreli yedek protokolüdür (log öneki `encb/`):

| Sınıf | Rol (found) |
|-------|--------------|
| `EncBackupViewModel` | kullanıcının yedek parolası string'iyle `C61447Rhg` (login handler) oluşturur |
| `AbstractC62498S8e` | `sendInitRegIq`, `sendBeginRegIq`, `sendFinishRegIq`, `sendInitLoginIq`, `finishLoginOnSuccess`, `sendDeleteAccountIq` IQ'larını gönderir (`EncryptedBackupProtocolHelper`) |
| `C62510S8q` (smali `X/S8q`) | yanıt handler'ı; `jvidispatchOOO(0xb, password, ...)` login durumunu (`Rtz`) döndürür, `jvidispatchOO(0x20, state)` sonraki mesajı |
| `C62511S8r` | begin-login yanıtı: `l2` değerini `l2_sig` ve `ed_pub` ile doğrular (Ed25519), `count`, `backoff`, `max_attempts` değerlerini okur, ardından `jvidispatchOIOOO(1, 100000L, state, ...)` |
| `RunnableC29321Co8` | finish-login: `jvidispatchOIOO(1, 100000L, state, ...)`, model alanlarını okur, yedek anahtarını AES-GCM ile çözer, `C25803BBm` proto'sunu oluşturur (`backupKeyData_`, `r3_`, `opaqueChallenge_`, `transcript_`) |

`100000`, hem register hem login içinde native finish çağrılarına geçirilir (found). Büyük olasılıkla PBKDF2 iterasyon sayısıdır (inferred: native fonksiyon bunu parametre olarak alır). Bu `jvidispatch` indekslerinin `WESOpaque*` koduna düştüğü, argümanlardan (giren parola string'i, çağrılar arasındaki durum nesneleri, `l2` / `r3` alanları) ve başka tüketicinin bulunmamasından inferred; hiçbir Java sembolü OPAQUE adını taşımaz. Hesap parolası kodu (bölüm 5) bunlara hiç dokunmaz.

### 6.4 Diğer VOPRF: Meta ACS token'ları

`NativeVOPRFExtension` ve `libvoprf-ed25519.so` için Java tüketicileri `C1N9` (`ACSTokenProviderImpl`, log öneki `ACSToken/`) ve `KYL`'dir: blinding factor, imzalı kör token, DLEQ kanıtı, unblind, paylaşılan sır (found string'ler `blinding_factor_string`, `shared_secret_string`, `ACSToken/processSignedBlindedToken`). Asset'lerdeki eşleşen işlemler `WaAcsGetConfig` (`27388182297440754`) ve `WaAcsIssueCredentials` (`26645395115100537`); ikisinin adı da kodda geçmez, dolayısıyla token isteğinin taşıyıcısı izlenmedi. Bu anonim bir kimlik bilgisi token'ıdır, parola ile giriş değildir.

### 6.5 "Parola ile giriş" için bunun anlamı

| İddia | 2.26.41.6 içindeki durum |
|-------|---------------------|
| Hesap parolasıyla giriş OPAQUE kullanır | kod tarafından desteklenmiyor: parola bir RSA/AES zarfı (`#PWD_WA:11`) olarak gönderilir, okunan yollarda hiçbir OPAQUE mesajı oluşturulmaz; `SetPasswordMutation` ve `CheckPasswordMutation` için çağrı noktası yok |
| Native bir OPAQUE istemcisi var | found |
| Şifreli yedek parolasına hizmet eder | found (Java çağıranı), native sembollere bağlanma inferred |
| Sunucu, hesap parolası için parola yerine bir verifier saklar | unknown |

OPAQUE kanıtı gibi görünen ama ilgisiz Java string'leri (found): `opaqueChallenge_` (yukarıdaki yedek bootstrap proto'su), `opaquePayload_` (`C61318RfY`, tethered migration frame'i), `OpaqueConfig` / `prefersOpaqueConfig` (`EnumC167127Ba` içindeki bitmap yapılandırması), `OpaqueKey(` (`C44715Jfl`, bir string sarmalayıcı), `KE1` (`X.KE1` bir Android Compose sınıfıdır), `opaque_client_data` (history-sync sütunu).

---

## 7. Passkey'ler (WebAuthn)

### 7.1 Kayıt sırasında giriş

| Adım | Kanıt |
|------|----------|
| `/v2/exist`, `passkey_auth_challenge` döndürür; `K15.A03` bunu `SignalCredentialStateController.MAX_RETRY_TIME` süresinden genç olduğu sürece kabul eder | found |
| `PasskeyVerifier.onPasskeyChallengeReceived`, `androidx.credentials` üzerinden discoverable-credential assertion çalıştırır (`PasskeyLowLevelAndroidApiImpl.loginWithPasskey`); aşama `passkey_login_stage` pref'inde tutulur | found |
| `K49.A0l` sonucu `credential` olarak `/v2/passkey_auth` adresine gönderir | found |
| Yanıt: `status` (`ok`/`fail`), `reason` (`temporarily_unavailable`, `disabled`), `credential_create` (string), `login`, `cred_token` | found |
| `cred_token`, telefon numarası başına `passkey_disabled_cred_token_map` içinde saklanır ve flag **25565** açıkken sonraki isteklerde `cred_token` olarak geri gönderilir | found; amaç (bir passkey'in devre dışı bırakıldığını kanıtlamak) inferred |

İstemci tarafı sonuçlar `passkey_client_login_{cancelled,nopasskey,ineligible,error,success}` olarak loglanır. `prepareGetCredential` yalnızca Android 14+ (SDK 34) ve flag **21638** ile kullanılır (found).

### 7.2 Oluşturma ve yönetim

2FA adımından sonra upsell: `VerifyTwoFactorAuth.onCheckPasskeyUpsellAfter2FA`, `PasskeyCreateEducationScreen` veya bir bottom sheet kullanır; flag **20409** kontrol akışı ile quick-promotion (QP) yolu arasında geçiş yapar, flag **16591** bir uygunluk kontrolü ekler (found).

| İşlem | MEX kapısı | IQ yedeği (`xmlns="passkey"`) |
|-----------|----------|---------------------------------|
| start register | flag **10453** | smax 125, `type=get` |
| finish register | flag **10452** | smax 126, `type=set` |
| clear | flag **10461** | smax 129, `type=set` |
| list / exists, delete, enable, update encryption status | her zaman MEX | yok |

Start-register'dan gelen `credential_create`, `passkey_create_challenge` içinde önbelleğe alınır. Finish register `credential` ve `key_attestation` gönderir; attestation payload'ı yalnızca flag **28809** açıksa oluşturulur (key attestation'ın base64'ü, `getKeyAttestationPayload`). Flag **8877**, start / finish işlemlerini bir retry / timeout yardımcısına sarar (`C29707Cw7`, rol inferred). `PasskeyRandomizedDailyCronJob` ve `PasskeyExistsCache` exists listesini yeniler; exists yanıtı `uuid` değerini `reg_passkey_exists_uuid` içinde saklar.

### 7.3 PRF ve istemci tarafı şifreleme

`PasskeyPrfSecrets` statik PRF girdisi `WhatsAppPasskeyStaticPrfInputV1` değerini kullanır ve PRF'ten türetilen kök anahtarı `prf_derived_root_key.key` içinde saklar (kapsülleme anahtarı etiketi `prf_derived_root_key_file_encapsulation_key`). `RegistrationPasskeyUpdateClientEncryptionStatusMutation`, passkey'in istemci tarafı şifreleme için kullanıldığını sunucuya bildirir. Tüketici şifreli yedek akışıdır (`VerifyPasskeyFragment`, sınıf konumundan inferred).

---

## 8. Güvenilir cihazlar

| Öğe | Değer |
|------|-------|
| `device_id` | `Base64(SHA-256(ANDROID_ID))` (wrap yok), `K2M.A01` |
| `device_name` | `<MANUFACTURER>-<MODEL>` (`HO4.A00`) |
| Onay kutusu | flag **30530** açıksa ve `pref_is_device_trusted` false ise `VerifyPhoneNumber` ve `VerifyTwoFactorAuth` üzerinde gösterilir; pref'ler `pref_trusted_device_checkbox_shown` / `_checked` |
| Kayıt tamamlama (`RegisterName`) | kabul edildiyse: `AddTrustedDeviceMutation`; kabul edilmediyse: `reason="REREG"` ile `UntrustTrustedDeviceMutation` (`C29652Cu9`, found) |
| Ayarlar | `TrustedDevicesRepository` listeler (`GetTrustedDevicesQuery`) ve kaldırır (`DeleteTrustedDeviceMutation`); `TrustThisDeviceActivity` |
| Etki | `is_device_trusted`, `/v2/exist`, `/v2/register`, `GetTwofa` ve `SetTwofa` tarafından döndürülür; istemci bunu onay kutusunu atlamak için kullanır. Güvenilir bir cihazın PIN / parola istemini atladığı inferred; hiçbir istemci kodu ikinci faktörü atlamaz |

`list_of_trusted_device[]` girdileri `device_id`, `device_name`, `latitude`, `longitude`, `last_ts` taşır (son kullanımın konumu sunucu tarafından sağlanır; nasıl türetildiği bilinmiyor).

---

## 9. Hesap kurtarma (Meta canonical user)

`AccountRecoveryManager`, WhatsApp sohbetlerini veya telefon numarası hesabını kurtarmaz. FB bağlantılı bir hesabın Meta canonical-user kimlik bilgilerini yeniden oluşturur (found).

| Adım | Ayrıntı |
|------|--------|
| Tetikleyici | `maybeRecoverAccount`: canonical user yok veya kimlik bilgileri geçersiz; ertelenmiş varyant flag **16017** ile kapılı |
| İstemci anahtarı | bir anahtar çifti üretir, genel anahtarı (PEM, base64) `nonce_encryption_key` olarak `use_case`, `registration_trace_id`, `request_id` ile `WWWTriggerAcountRecovery` içinde gönderir |
| Nonce | bildirimle gelir; zaman aşımı "Account Recovery Failed due to Nonce notification timeout" üretir |
| Değişim | `WWWExchangeNonceForAccessToken`: `nonce`, `use_case`, `request_id`, `registration_trace_id`, `encrypted_password` = JSON `{version:1,timestamp,password}` içindeki rastgele bir istemci sırrının `#PWD_WA:11` zarfı |
| Companion | `WWWGetNonceForCompanionDevice`, `WWWTradeNonceForAccessTokens` bağlı cihazlar için aynısını yapar (`CompanionCanonicalUserNonceManager`, `CompanionCanonicalUserAccessTokenJob`) |
| İlgili | `WWWValidateCanonicalUser`, `WWWCanonicalUserValid`, `WWWAppGenerateCanonicalNonce` (çağrı noktaları var; alanlar okunmadı) |

`Acount` yazımı WhatsApp'ın kendisine aittir. Nonce şifreleme anahtarının algoritmasının ne olduğu (çift `N6T.A02` içinden gelir) çözülmedi.

---

## 10. Giriş ve çıkış

`LogoutManager` bir soft logout (çoklu hesap) ve login-back yolunu uygular (found).

| Eylem | Wire | Notlar |
|--------|------|-------|
| Logout | `AccountLogoutMutation` `{phone_number, enabled_biometric}` | `enabled_biometric` bir biyometrik ayardan gelir; 5 sn zaman aşımı, ardından logout yerel olarak sürer ("timed out, proceeding with logout") |
| Push | `LogoutPushManager` GCM push'u devre dışı bırakır / yeniden etkinleştirir (geri almada `"re-enable"`) | found |
| Yerel | `markCurrentAccountLoggedOut`, `removeLoggedOutAccountWithCleanup`, `deleteGmsBackupState`, isteğe bağlı sohbet silme arayüzü (`DeleteChatsOnLogoutDialog`, `LoggedOutChatsFragmentDialog`) | found |
| Login back | `AccountLoginMutation` `{phone_number}`, ardından `loginBack` → `actionReconnect`; bağlantı için 7 sn'ye kadar bekler | `PrimaryLoginBackActivity` |

Bu, çoklu hesap kurulumunun sunucu tarafındaki bir durum bayrağıdır; bölüm 3'teki telefon numarası girişi değildir ve bağlı bir cihazın kaldırılması da değildir. Flag **28385** `LogoutManager` içinde okunur (rol çözülmedi).

---

## 11. Feature flag'ler

ID'ler kalın yazılmıştır. Türler: B = boolean AB prop, C = yapılandırma. Adlar istemcide yoktur; rol, kodun flag ile ne yaptığıdır.

| ID | Nerede | Kontrol ettiği |
|----|-------|----------|
| **24762** (C) / **24763** (B) | `K49.A0b` | native `wamsys` yerine Kotlin kayıt yığını |
| **26215** | `K49` verify / reset security code | `/v2/register` üzerinden kayıt ikinci faktörü, parola zarfını etkinleştirir; kapalı = eski `/v2/security` |
| **25565** | `K49.A0M` | saklanan `cred_token` değerini gönder |
| **28755** | `VerifyTwoFactorAuth` | `second_factor_methods` üzerinden dinamik 2FA yöntem seçimi |
| **30530** | `VerifyPhoneNumber`, `VerifyTwoFactorAuth` | güvenilir cihaz onay kutusu |
| **20409** | `VerifyTwoFactorAuth` | 2FA sonrası QP passkey upsell'e karşı kontrol |
| **16591** | `VerifyTwoFactorAuth` | upsell öncesi passkey uygunluk kontrolü |
| **21638** | `PasskeyAndroidApi` | `prepareGetCredential` (Android 14+) |
| **10452** / **10453** / **10461** | `PasskeyServerApiImpl` | finish / start / clear için IQ yerine MEX |
| **28809** | `PasskeyServerApiImpl` | key attestation payload'ı |
| **8877**, **31281** | `PasskeyCreateFlow` | retry sarmalayıcısı; alternatif ödemeler-passkey yolu (roller inferred) |
| **5156** | `SetCodeFragment` | PIN ayarlandıktan sonra "e-posta ekle" teklifi |
| **5711** | `TwoFactorAuthActivity`, `SetCodeFragment` | yalnızca düzen (sayfa göstergesini gizler) |
| **16017** | `AccountRecoveryManager` | ertelenmiş nonce işleme |
| **28385** | `LogoutManager` | çözülmedi |

---

## 12. Hata durumları

| Belirti | Neden | Çözüm / not |
|---------|-------|--------------|
| `/v2/register` reason `security_code` veya `second_code` | hesabın ikinci faktörü var | PIN / parola / e-posta OTP'sini `/v2/register` ile gönderin (3.6) |
| `PASSWORD_ENCRYPT_FAILED` (QPL) | anahtar getirme başarısız, `key_id` 1-255 dışında veya kripto istisnası (`encryptRegistrationPassword/*` logları) | yeniden deneyin; istemci denemeyi iptal eder |
| `reset_too_soon` | PIN'imi unuttum sıfırlaması `wipe_wait` dolmadan yapıldı | bekleyin; arayüz durumu 1 |
| `too_many_guesses` / `guessed_too_fast` | PIN veya OTP tahmin sınırı | `guess_wait` kadar bekleyin |
| `No canonical credentials available to set password` | cihazda Meta canonical user yok | önce canonical-user kurulumunu tamamlayın |
| Parola oluşturma / değiştirme başarısız | `xfb_wa_*` payload'ı başarılı değil; hata kodu `CanonicalPasswordService.A00` tarafından eşlenir | arayüz hata enum'u `EnumC49982M3j` |
| `DeletePassword` 409 | kaldırmadan önce hesap e-postası gerekli | önce e-posta ekleyin |
| `Account Recovery Failed due to Nonce notification timeout` | bildirim alınmadı | tetiklemeyi yeniden deneyin |
| `...passwordPublicKeyStr is null` / `passwordKeyIdStr is null` | kurtarma değişiminde şifreleme sertifikası eksik | yeniden deneyin |
| `LogoutManager/callLogoutApi/timed out` | 5 sn içinde yanıt yok | logout yerel olarak devam eder |
| Passkey: `NoCredentialException`, `NotAllowedError`, GMS çok eski, Play services eksik | Credential Manager hataları | diğer yöntemlere geri düşer |

---

## 13. Temel ayrımlar

| A | B |
|---|---|
| OPAQUE native kodu (şifreli yedek parolası, HSM `encb/*` IQ'ları) | hesap parolası (`XfbWa*` + `#PWD_WA:11`) |
| `libvoprf-*.so` + `NativeVOPRFExtension` (ACS anonim token'ları) | OPAQUE durum makinesi (`WESOpaque*`) |
| PIN (IQ `<2fa>`, 6 hane) | parola (w:mex, 8-20 karakter) |
| `<2fa><email>` (PIN sıfırlama için kurtarma e-postası) | `<verify_email>` OTP akışı ve `email_otp` ikinci faktörü |
| `SetTwofaMutation` (paroladan sonra cihaz id'si başına flag) | PIN set IQ'su |
| Güvenilir cihaz (giriş, `AddTrustedDeviceMutation`) | `WhatsappTrustedDeviceRegistration` (ödeme trust binding'i) |
| `AccountLogoutMutation` (soft logout) | companion bağlantısını kaldırma (`remove-companion-device`) ve ban logout'u |
| `WWWTriggerAcountRecovery` (canonical user kimlik bilgileri) | PIN'imi unuttum wipe'ı (`wipe_*`, `/v2/security`) |
| `#PWD_WA:11` (WhatsApp) | `#PWD_WAFFLE` (Waffle SSO) |
| `PasskeyServerApiImpl` işlemleri (hesap passkey'leri) | `PaymentsPasskey*`, `BrPasskey*` |
| `/v2/passkey_auth` (giriş assertion'ı) | `PasskeyRequestChallengeMutation` / `PasskeyVerifyChallengeMutation` (çağrı noktası yok) |

---

## 14. Baileys (`baron-baileys-v2`)

`src/Socket/privacy.js` ve `src/Socket/registration.js` ile karşılaştırıldı.

| Öğe | APK 2.26.41.6 | Baileys | Sonuç |
|------|---------------|---------|--------|
| güvenilir cihazlar, giriş, çıkış, parolalar, passkey'ler için doc_id'ler | asset'ler | aynı numaralar | eşleşiyor |
| `accountLogin` / `accountLogout` | `input{phone_number}` / `input{phone_number, enabled_biometric}` | aynı | eşleşiyor |
| `getTrustedDevices` | `input{device_id}` her zaman gönderilir | `{}` | farklı; `device_id` olmadan sunucu davranışı bilinmiyor |
| `untrustTrustedDevice` varsayılan reason | tek çağrıda `"REREG"` | `'USER_INITIATED'` | farklı, diğer reason'lar bilinmiyor |
| passkey işlemleri | değişkenler `credential`, `key_attestation`, `credential_ids`; kökler `xwa2_passkey_*` | okunan dosyalarda hiçbiri uygulanmamış | APK şekillerini kullanın |
| `SetPassword` / `CheckPassword` | çağrı noktası yok | yalnızca doc_id'ler | doğrulanmadı, güvenmeyin |
| `#PWD_WA:11` şifreleme | bölüm 5.3 | okunan `src` ağacında yok | bölüm 5.3'e göre uygulayın |

Bağımsız bir istemcinin bu yollarda neden başarısız olduğu (inferred, hiçbir şey test edilmedi): kayıt endpoint'leri uygulamanın oluşturduğu e2e korumalı istek alanlarını bekler (`C45446JsB`); parola ve kurtarma çağrıları canonical-user kimlik bilgileri gerektirir; passkey assertion bir platform authenticator'ı gerektirir.

---

## 15. Tam akışlar

### 15.1 Hesabı zaten olan bir numarayı doğrulama

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

### 15.2 PIN ve kurtarma e-postası ayarlama

```
[Client]  IQ get <2fa/> ───────────────► [Server]  <2fa>[<code/>][<email/>]
[Client]  IQ set <2fa><code>NNNNNN</code><email>x</email></2fa> ──► ok | error(code,text)
[Client]  Fetch2FAEmailStatusJob: IQ get <2fa/> until <email> present
[Client]  IQ get <2fa><code>NNNNNN</code></2fa> ──► <2fa><code/></2fa> = correct   (periodic reminder)
```

### 15.3 Hesap parolası oluşturma

```
[Client]  canonical credentials present? ── no ─► fail
[Client]  WaPasswordEncryptionKeyQuery ──► public_key (PEM), key_id (1..255)
[Client]  HOZ.A08: AES-GCM + RSA-PKCS1 wrap -> "#PWD_WA:11:<epoch>:<blob>"
[Client]  XfbWaCreatePasswordMutation {data:{encrypted_password}} ──► success
[Client]  (best effort) GetTwofaQuery / SetTwofaMutation {input:{twofa_enabled:true, device_id}}
```

---

## 16. Bilinmeyenler

| Konu | Neden |
|-------|--------|
| OPAQUE şifre takımı (grup, `VOPRF06-` sonrasındaki id), KE1 / KE2 / KE3 ve zarf düzenleri, AKE varyantı | native, yalnızca 4 fonksiyonun disassembly'si olarak okundu |
| Şifreli yedek `jvidispatch` indekslerinin `WESOpaque*` koduna bağlanması | sembol ile değil, argüman şekli ile |
| OPAQUE KSF için PBKDF2 iterasyon sayısı | parametre olarak geçirilir; `100000`, Java çağıranlarının geçirdiği literal değerdir |
| Herhangi bir yolun hesap parolasını OPAQUE üzerinden gönderip göndermediği | böyle bir yol bulunamadı; sayısal dispatch'in arkasına gizlenmiş sarmalayıcılar dışlanamaz |
| `XfbWa*`, `AccountLogin`, `AccountLogout`, `UntrustTrustedDevice` yanıtları | kök ve alanlar okunmadı |
| Çağrı noktası olmayan işlemler (2.4) | değişkenler ve yanıtlar bilinmiyor |
| `#PWD_WA` blob'unu `/v2/register` içinde taşıyan tam alan | kurucu sırasından türetildi |
| `/v2/exist` ve `/v2/passkey_auth` tarafından döndürülen `login`, `lid` alanlarının anlamı | tüketiciler izlenmedi |
| `wipe_full` / `wipe_offline` işlemlerinin sunucudaki etkisi | istemci yalnızca metin gösterir |
| Güvenilir bir cihazın ikinci faktörü atlayıp atlamadığı | sunucu tarafı; istemcide atlama mantığı yok |
| Kurtarma anahtar çiftinin algoritması (`N6T.A02`) | okunmadı |
| 8877, 31281, 28385 numaralı flag'lerin rolleri | yalnızca kapılar |
| Gerçek trafik | yalnızca statik analiz |
