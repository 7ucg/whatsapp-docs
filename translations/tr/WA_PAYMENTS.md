<!-- src-sha1: 1fe6d8278b8f0a0adfe50041466f968ec368a2e2 -->
# WhatsApp Payments — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** sohbet içi ödeme mesaj tipleri (`sendPaymentMessage`, `requestPaymentMessage`, `declinePaymentRequestMessage`, `cancelPaymentRequestMessage`, bölüşmeli ödemeler, ödeme daveti/hatırlatma) ve proto alanları, çok-raylı (multi-rail) istemci mimarisi (Hindistan UPI, Brezilya Pix, Meksika, Endonezya, jenerik "UPR" rayı), VPA/banka hesabı bağlama ve UPI onboarding akışı, gömülü NPCI "Common Library" (CL) kimlik bilgisi/PIN/cihaz bağlama katmanı, işlem durumu senkronizasyonu, şifreleme katmanlaması (sohbet E2E vs NPCI kimlik bilgisi blob'u), GraphQL/MEX ödeme operasyonları (doc_id'ler), NPCI OTP otomatik okuma kuralları, feature flag'ler, red/hata kodu işleme

---

## 1. Ne olduğu (genel bakış)

WhatsApp Android, normal E2E `Message` içinde taşınan tek bir paylaşılan sohbet içi ödeme protokolü (proto mesaj tipleri) ile birlikte, her biri kendi onboarding arayüzüne, GraphQL operasyonlarına ve (Hindistan için) gömülü bir üçüncü taraf kimlik bilgisi kütüphanesine sahip çeşitli ülkeye özgü ödeme *rayları* (rail) gönderir. Tüm bulgular decompile edilmiş APK'nın statik analizine dayanır; hatta hiçbir şey ağ üzerinde yakalanmadı. Seviyeler: **found** = doğrudan kod/asset içinde okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi. Obfuscate edilmiş adlar build'e özeldir ve 2.26.41.6'da sabit string'lerden (`FIELD_NUMBER` sabitleri, AIDL arayüz adları, GraphQL operasyon katalogları, asset dosya adları) yeniden çözüldü.

| Katman | 2.26.41.6 adı / yolu | Rol |
|-------|------------------------|------|
| Sohbet mesaj protokolü | `DSJ` SendPaymentMessage, `C30605DSz` RequestPaymentMessage, `C30502DPa` DeclinePaymentRequestMessage, `DPZ` CancelPaymentRequestMessage, `DT0`/`C30535DQh` bölüşmeli ödeme, `C30586DSg` PaymentInviteMessage, `C43112IrN` PaymentReminderMessage, `DTS` PaymentInfo | bölüm 2'deki alanlar |
| Ray paketleri | `com.whatsapp.payments.{common,indiaupi,brazilpay,mexico,indonesia,globalorder,upr,dcp,remittances,split,paymentkey,productinfra,integrity,phoenix}` | pazar/ray başına bir paket, bölüm 3 |
| Hindistan UPI kimlik bilgisi kütüphanesi | `org.npci.upi.security.{services,pinactivitycomponent}` (`CLRemoteService`, `CLRemoteServiceImpl`, `BinderC48420LDc`, `GetCredential`) | gömülü NPCI "Common Library" (CL), bölüm 6 |
| OTP otomatik okuma | `assets/npci/npci_otp_rules.json`, tüketici `org.npci.upi.security.pinactivitycomponent.C0315u` | bölüm 10 |
| GraphQL/MEX katalog | `assets/whatsapp-android-www_client_persist_ids.json` (şema `whatsapp`), `whatsapp-android-mex_client_persist_ids.json` (şema `whatsapp_mex`) | doc_id'ler, bölüm 9 |
| Sunucu push handler'ı | `C24410wL` ("PaymentsMessageHandler", log tag'ı `PaymentsMessageHandler`) | `<notification type="pay\|upi\|fbpay\|transaction\|account-recovery\|alert\|...">`, bölüm 8 |
| İşlem nesnesi | `F7F` (yerel işlem satırı), `DTS` (wire/history-sync PaymentInfo), `EKY.A00` tarafından inşa edilir | bölüm 8 |

Paket/sınıf adlarından (found) tanımlanan raylar: **Hindistan UPI** (`indiaupi`), **Brezilya Pix** (`brazilpay`), **Meksika** (`mexico`), **Endonezya** (`indonesia`), ayrıca raydan bağımsız bir "**UPR**" paketi (`upr` — onboarding, hesap yönetimi, bubble arayüzü) ve enum/bildirim kodunda halen bulunan eski bir Meta Pay/Novi referansı (`FBPAY`, `NOVI`) — bu servisler uzun süredir aktif olmasa da literal string'ler 2.26.41.6'da halen mevcut olduğu için burada tutuldu. Aşağıdaki kanıtlar bölüm başına **Hindistan/UPI'ye özgü** veya **genel** olarak etiketlenmiştir; UPI bulgularının Pix/Meksika/Endonezya için de geçerli olduğunu varsaymayın.

---

## 2. Ödeme mesaj tipleri ve proto alanları

### 2.1 `Message` içindeki yerleşim (found)

Tüm ödeme mesaj tipleri üst seviye `Message` proto'sunun (`C30628DTw`, `WA_MESSAGE_SECRETS.md`'de belgelenen aynı sınıf) doğrudan alanlarıdır. Ödeme alt mesajlarının çoğu `Message`'ın kendisi üzerinde genel `FIELD_NUMBER` sabitleri **sunmaz**; aşağıdaki numaralar, sınıfın paketlenmiş `GeneratedMessageLite` mesaj-bilgi string'i decode edilerek kurtarıldı (tekrarlanabilir, alan başına 2-ya-da-3 karakterlik bir kodlama: alan-numarası karakteri, tip-işareti karakteri, has-bit indeks karakteri; has-bit indeksi, ~150 alanlık mesajın tamamında girdi başına tam olarak bir artar — bu, decode üzerinde güçlü bir iç tutarlılık kontrolüdür).

| Alan (Message) | Numara | Tip |
|---|---|---|
| `sendPaymentMessage` | **16** | `SendPaymentMessage` (`DSJ`) |
| `requestPaymentMessage` | **22** | `RequestPaymentMessage` (`C30605DSz`) |
| `declinePaymentRequestMessage` | **23** | `DeclinePaymentRequestMessage` (`C30502DPa`) |
| `cancelPaymentRequestMessage` | **24** | `CancelPaymentRequestMessage` (`DPZ`) |
| `paymentInviteMessage` | **44** | `PaymentInviteMessage` (`C30586DSg`) |
| `splitPaymentMessage` | bu geçişte decode edilmedi | `SplitPaymentMessage` (`DT0`), `unknown` |
| `splitPaymentUpdateMessage` | bu geçişte decode edilmedi | `SplitPaymentUpdateMessage` (`C30535DQh`), `unknown` |
| `paymentReminderMessage` | bu geçişte decode edilmedi | `PaymentReminderMessage` (`C43112IrN`), `unknown` |

Stanza seviyesindeki `<message type="pay">` sınıflandırıcısı (diğer eklenti tipleriyle paylaşılır) `WA_MESSAGE_SECRETS.md`'de tip seçici (`AbstractC30999De0.A02`) bölümünde belgelenmiştir; burada yeniden türetilmedi.

### 2.2 SendPaymentMessage (`DSJ`, found)

| Alan | Numara | Tip | Kullanım |
|---|---|---|---|
| `noteMessage` | **2** | `Message` (`C30628DTw`) | bir ödemeye eklenen "not" kendisi tam bir `Message`'dır (normalde sadece bir `extendedTextMessage` veya sticker taşır) |
| `requestMessageKey` | **3** | `MessageKey` (`BD5`) | bu gönderim önceki bir `requestPaymentMessage`'a yanıt olduğunda mevcuttur |
| `background` | **4** | `PaymentBackground` (`DTJ`) | bölüm 2.7 |
| `transactionData` | **5** | string | opak; decompile edilmiş kaynaktaki varsayılan değer paylaşılan boş-string sabitidir, gerçek bir varsayılan değer değil |

Alan numarası 1 kullanılmıyor/ayrılmış (bunun için bir `FIELD_NUMBER` sabiti yok).

### 2.3 RequestPaymentMessage (`C30605DSz`, found)

| Alan | Numara | Tip | Kullanım |
|---|---|---|---|
| `currencyCodeIso4217` | **1** | string | ISO 4217 kodu |
| `amount1000` | **2** | int64 | tutar × 1000 (sabit noktalı, wire değerinde ondalık yok) |
| `requestFrom` | **3** | string | talep eden kimliği (çağrı noktalarında gözlenen JID string'i) |
| `noteMessage` | **4** | `Message` | 2.2 ile aynı desen |
| `expiryTimestamp` | **5** | int64 | unix saniye |
| `amount` | **6** | `Money` (`C30561DRh`) | yapılandırılmış tutar, bölüm 2.7 |
| `background` | **7** | `PaymentBackground` (`DTJ`) | bölüm 2.7 |

### 2.4 DeclinePaymentRequestMessage / CancelPaymentRequestMessage (found)

Her iki mesaj da minimaldir — orijinal talebe referans veren tek bir alan:

| Sınıf | Alan | Numara | Tip |
|---|---|---|---|
| `DeclinePaymentRequestMessage` (`C30502DPa`) | `key` | **1** | `MessageKey` (`BD5`) |
| `CancelPaymentRequestMessage` (`DPZ`) | `key` | **1** | `MessageKey` (`BD5`) |

**Hiçbir mesaj bir sebep/hata kodu alanı taşımıyor.** Decline ve cancel, "bu talep (`key` ile tanımlanan) reddedildi/iptal edildi" ötesinde protokol düzeyinde no-op'tur; arayüzde gösterilen herhangi bir sebep metni yerel olup wire payload'ının bir parçası değildir (found: her iki sınıfta da ikinci bir alan yok; bkz. bölüm 12).

### 2.5 Bölüşmeli ödemeler (found)

`SplitPaymentMessage` (`DT0`):

| Alan | Numara | Tip |
|---|---|---|
| `splitId` | **1** | string |
| `totalAmount` | **2** | `Money` |
| `description` | **3** | string |
| `requesterJid` | **4** | string |
| `participants` | **5** | tekrarlı `SplitPaymentParticipant` (`C30558DRe`) |
| `createdAtMs` | **6** | int64 |
| `contextInfo` | **17** | `MessageContextInfo`-benzeri (`C30617DTl`) |

`SplitPaymentUpdateMessage` (`C30535DQh`): `splitId` (**1**, string), `participantJid` (**2**, string) — katılımcı başına durum ping'i, kendi tutar/durum payload'ı yok.

### 2.6 PaymentInviteMessage / PaymentReminderMessage (found)

`PaymentInviteMessage` (`C30586DSg`): `serviceType` (**1**, int/enum — bölüm 8'de görülen `UPI`/`PIX`/`NOVI`/`FBPAY` servis kodlarına bağlı), `expiryTimestamp` (**2**, int64), `incentiveEligible` (**3**, bool), `referralId` (**4**, string), `inviteType` (**5**, int/enum).

`PaymentReminderMessage` (`C43112IrN`):

| Alan | Numara | Tip |
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

`payeeVpa` (alan 6), wire protokolünde **literal bir VPA alanıdır** — UPI sanal ödeme adreslerinin sadece GraphQL yan kanalları üzerinden değil, sohbet mesajları içinde de seyahat ettiğinin doğrudan proto-seviyesinde onayıdır.

### 2.7 Destekleyici tipler (found)

| Tip | Sınıf | Alanlar |
|---|---|---|
| `Money` | `C30561DRh` | `value` (**1**, int64), `offset` (**2**, int32 — ondalık nokta ofseti), `currencyCode` (**3**, string) |
| `MessageKey` | `BD5` | `remoteJid` (**1**, string), `fromMe` (**2**, bool), `id` (**3**, string), `participant` (**4**, string) |
| `PaymentBackground` | `DTJ` | `id` (**1**, string), `fileLength` (**2**, int64), `width` (**3**, int32), `height` (**4**, int32), `mimetype` (**5**, string), `placeholderArgb` (**6**, int32), `textArgb` (**7**, int32), `subtextArgb` (**8**, int32), `mediaData` (**9**, `MediaData` `C30588DSi`), `type` (**10**, enum) |

### 2.8 PaymentInfo — işlem durumu nesnesi (found)

`DTS` ("PaymentInfo") bir sohbet mesaj tipi **değildir**; `WebMessageInfo`'ya (`C30626DTu`, `WA_MESSAGE_SECRETS.md`'de belgelenen history-sync/companion taşıyıcısı) `paymentInfo_` ve `quotedPaymentInfo_` olarak eklenir. Bir işlemin bilinen güncel durumunu temsil eder, yerel işlem satırından `EKY.A00` tarafından inşa edilir:

| Alan | Numara | Tip | Not |
|---|---|---|---|
| `currencyDeprecated` | **1** | enum | eski (legacy) |
| `amount1000` | **2** | int64 | |
| `receiverJid` | **3** | string | |
| `status` | **4** | enum | kaba durum |
| `transactionTimestamp` | **5** | int64 | |
| `requestMessageKey` | **6** | `MessageKey` | |
| `expiryTimestamp` | **7** | int64 | |
| `futureproofed` | **8** | bool | gönderenin yerel işlem nesnesinde çözümlenebilir bir para birimi/tutar olmadığında ayarlanır (şema-evrimi kaçış kapısı) |
| `currency` | **9** | string | |
| `txnStatus` | **10** | enum | daha ince taneli durum (NPCI seviyesinde), `status`'tan ayrı bir enum |
| `useNoviFiatFormat` | **11** | bool | eski Meta Pay/Novi görüntü-formatı bayrağı |
| `primaryAmount` | **12** | `Money` | |
| `exchangeAmount` | **13** | `Money` | çapraz para birimi görüntüleme |

`status`/`txnStatus` enum sabit **adları** obfuscator tarafından javalite-bytecode seviyesinde silinmiştir (sadece ordinaller + `EnumVerifier` sınıfları kalır); ordinal→etiket eşlemesi bu geçişte `unknown`'dır. `EKY.A00`, yerel işlem nesnesinin para birimi/tutarını okur ve bu mevcut olmadığında tahmin etmek yerine `futureproofed=true` ayarlar — kodda bulundu (`f7fA00.A03 == 5 || !f7fA00.A0N()` guard'ı).

---

## 3. Çok-raylı istemci mimarisi ("payment-common-library")

Ödeme kodu, bir paylaşılan arayüz/altyapı paketi ile her pazar rayı için bir paket şeklinde organize edilmiştir (found, `com.whatsapp.payments` altındaki paket düzeninden):

| Paket | Ray | İçerik (found) |
|---|---|---|
| `common` | paylaşılan | `p144ui` (jenerik ödeme bottom sheet'leri, ayarlar, işlem geçmişi, yöntem seçicileri), `pin` (raylar arasında paylaşılan PIN giriş arayüzü), `paymentkeys`, `compliance`, `care` (CSAT), `qpl` (kalite/performans loglama işaretleri) |
| `indiaupi` | Hindistan UPI | onboarding, banka/VPA bağlama, mandate'ler, fatura ödemeleri, UPI Lite, QR, hesap kurtarma — bölüm 4 |
| `brazilpay` | Brezilya Pix | Pix anahtarı yönetimi, biyometrik/passkey kaydı, CPF |
| `mexico`, `indonesia` | yerel raylar | paket olarak mevcut; bu geçişte varlıklarının dışında araştırılmadı (`unknown` detay) |
| `upr` | raydan bağımsız | `nux` (onboarding), `accountmanagement`, `bubble` (sohbet içi ödeme seçenekleri sheet'i), `shared` (kurum/hesap tipi seçicileri) — `GenUprPaymentConfig`/`GenUprPaymentConfigForViewer` GraphQL operasyonlarına denk gelir (bölüm 9); "UPR" açılımı hiçbir string'de yazılı değildir (`inferred`: "Universal/Unified Payment Rail") |
| `globalorder`, `remittances`, `split`, `paymentkey`, `productinfra`, `integrity`, `dcp`, `phoenix` | karma | paket olarak mevcut; `integrity` bir ödeme "friction" bottom sheet'i (risk/step-up arayüzü) içerir, `dcp` ve `phoenix` için bu geçişte üst iki dizin seviyesinde dosya bulunamadı (`unknown`) |

Raylar arası GraphQL taşıması `PaymentsMexGraphQlClient$ApiEventCallBuilder` (`com.whatsapp.payments.indiaupi.common.graphql`, paket adına rağmen paylaşılan MEX çağrı sarmalayıcısıdır, found) ile sarmalanır — alttaki `InterfaceC17070jD` taşımasına devretmeden önce her ödeme MEX çağrısını QPL/olay-loglama başlangıç/başarı/başarısızlık callback'leriyle (`FDA.BYz`) donatır. Bu build'de, **istemci** seviyesinde bir "payment common library"ye en yakın eşleşme budur: tek bir obfuscate edilmiş çağrı-sarmalayıcı sınıfı, Hindistan UPI'nin GraphQL yöneticileri (`IndiaUpiChangeMpinGraphqlManager`, `IndiaUpiCheckBalanceGraphqlManager`, `IndiaUpiEnrollIncentiveGraphqlManager`, vb. — found, aynı paket) tarafından yeniden kullanılır.

Ayrıca Hindistan, NPCI'ye ait `org.npci.upi.security.*` paketi (`com.whatsapp.*` değil) altında gömülü bir **üçüncü taraf** kütüphane gönderir — bu, NPCI'nin kendi `.properties` asset'leri (`version.properties`, `validation.properties`, `cl-*.properties`) tarafından referans verilen "CL" ("Common Library")'dir ve bölüm 6'da ele alınmıştır. NPCI asset'lerinin kendi kelime dağarcığı (`salt`, `payInfo`, `controls`, `configuration`, `trust`, `keyXmlPayload`, `keyCode`), bu build'in `CLRemoteService.Acc`/`Acf` implementasyonlarında bulunan tam bundle-key string'leriyle (bölüm 6) eşleşir — bu, önceki sadece-asset'e-dayalı bir analizin doğrudan doğrulamasıdır. "Common Library" ifadesinin literal açılımı hâlâ hiçbir string'de yazılı değildir (`inferred`, şimdi `CLRemoteService`/`CLResultReceiver`/`CLRemoteServiceImpl` sınıf adlarının kendisiyle doğrulandı — bu geçişte yeni kanıt).

---

## 4. VPA / banka hesabı bağlama ve UPI onboarding (Hindistan'a özgü)

`com.whatsapp.payments.indiaupi.*`'den kurtarılan aktivite adları (found, sadece sınıf varlığı ve adlandırma — aralarındaki tam navigasyon sırası adlandırmadan `inferred`'dir ve bu geçişte intent grafikleri üzerinden izlenmedi):

| Adım | Activity/Fragment |
|---|---|
| Giriş / değer önerileri | `IndiaUpiPaymentsValuePropsActivity`, `IndiaUpiPaymentsValuePropsBottomSheetActivity`, `IndiaUpiPaymentsTosActivity` |
| SIM doğrulama | `IndiaUpiSimPickerDialogFragment`, `IndiaUpiSimVerificationActivity` |
| Banka seçimi | `IndiaUpiBankPickerActivity` (`onboarding` paketi), `IndiaUpiBankAccountPickerActivity` |
| Kimlik/kart doğrulama | `IndiaUpiDebitCardVerificationActivity`, `IndiaUpiAadhaarCardVerificationActivity`, `IndiaUpiDobPickerActivity` |
| Cihaz bağlama | `IndiaUpiDeviceBindStepActivity` (bu adımın arkasındaki kriptografi için bkz. bölüm 6) |
| PIN kurulumu | `IndiaUpiPinPrimerDialogFragment` / `...FullSheetActivity`, `IndiaUpiPinHandlerActivity`, `IndiaUpiPinSetUpCompletedActivity`, `IndiaUpiChangePinActivity`, `IndiaUpiForgotPinDialogFragment` |
| Tamamlanma | `IndiaUpiBankAccountAddedLandingActivity`, `IndiaUpiPaymentsAccountSetupActivity` |
| Numara-VPA eşleyici | `IndiaUpiMapperValuePropsActivity` → `IndiaUpiMapperLinkActivity` → `IndiaUpiMapperPendingActivity` → `IndiaUpiMapperConfirmationActivity`; varsayılan olmayan bir mobil numara için `IndiaUpiCreateCustomNumberActivity` |
| VPA kişi çözümleme | `IndiaUpiVpaContactInfoActivity`, `IndiaUpiSendPaymentToVpaFragment` |

"Mapper" burada NPCI'nin telefon-numarası↔VPA dizin servisi için kullandığı kendi terimidir; dört `mapper.register.*` aktivitesi bu özel kayıt alt-akışını uygular (found: paket yolu `indiaupi.p148ui.mapper.register`).

Çağrı noktası doğrulamalı değişkenlerle bağlama ile ilgili GraphQL operasyonları (found, `com.whatsapp.payments.indiaupi.common.graphql.*` ve ilgili `X/*` sınıflarından; tam katalog için bölüm 9'a bakın):

| Operasyon | doc_id | Değişkenler (found) |
|---|---|---|
| `GetUpiBankList` | `27764018976534565` | `account_type`, `provider_type`, `request` |
| `GetUpiAccounts` | `25691302307224710` | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `GetUpiToken` | `25639185495767704` | `challenge`, `device_id`, `token_type`, `provider_type` |
| `GenCreatePaymentKey` | `24662763616751127` | `add_bank`, `account_holder_name`, `display_name`, `payment_method_type`, `payment_account`, … (gürültülü superset, birkaç operasyon arasında paylaşılan çağıran — bkz. bölüm 9 uyarısı) |
| `SetUpiChangeMpin` | `27149786891388216` | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |

---

## 5. Ödeme kurulumu / onboarding (genel, raylar arası)

`upr` paketi raydan bağımsız bir onboarding kabuğu uygular: `UprOnboardingActivity` → `UprOnboardingFragment` → `UprAccountTypePickerBottomSheet` → `AddPaymentMethodFragment` / `UprInstitutionPickerBottomSheet` (found, sadece sınıf adları; akış sırası `inferred`). Kurulum sonrası hesap yönetimi `UprAccountManagementActivity`/`UprAccountManagementListFragment` üzerinden gider, sohbet içi ödeme tetikleyicisi ise `UprPaymentOptionsBottomSheet`/`UprPaymentAccountDetailBottomSheet` ("bubble" paketi — bir sohbetten açılan yüzen ödeme seçenekleri sheet'i) üzerinden görünür.

Bu kabuk için sunucu tarafı yapılandırma `GenUprPaymentConfig` (doc_id `26905963415743456`) ve `GenUprPaymentConfigForViewer` (doc_id `37307071662269517`) üzerinden alınır — doc_id katalogunda found, bu geçişte bağımsız olarak çağrı noktasında doğrulanmadı (`unknown` değişkenler).

---

## 6. NPCI "Common Library" (CL): kimlik bilgisi, PIN ve cihaz bağlama (Hindistan/UPI'ye özgü)

### 6.1 Mimari (found)

Hindistan UPI PIN girişi ve banka kimlik bilgisi işlemesi, WhatsApp'ın kendi `com.whatsapp.*` kodundan tamamen ayrı, NPCI'ye ait gömülü bir Android AIDL servisine devredilir:

```
org.npci.upi.security.services.CLRemoteService      <- AIDL interface
org.npci.upi.security.services.CLResultReceiver     <- AIDL callback interface
org.npci.upi.security.pinactivitycomponent.CLRemoteServiceImpl  <- Android Service, binds the AIDL
org.npci.upi.security.pinactivitycomponent.BinderC48420LDc      <- Binder implementation of CLRemoteService
org.npci.upi.security.pinactivitycomponent.GetCredential        <- PIN-entry Activity launched by the binder
org.npci.upi.security.pinactivitycomponent.Keypad               <- on-screen keypad widget
```

`CLRemoteService` metotları (found, arayüz imzaları): `AQR(otpResultJson)`, `AZO(mode, nonce)` (cihaz bağlama challenge/response, bölüm 6.2), `Acc(...)`/`Acf(...)` (bir kimlik bilgisi bundle'ı ile PIN aktivitesini başlatır), `BBj(...)` (bakiye okuma), `BVz/CRh/CRi(...)` (cihaz-sertifikası / durum doğrulama), `BW1()` (cihaz bütünlük kontrolü).

### 6.2 Cihaz bağlama ve kimlik bilgisi alışverişi (found)

`BinderC48420LDc.AZO(mode, nonce)`:
- "initial" modu: `deviceId|randomHex|nonce` oluşturur, bunu gömülü bir NPCI sertifikasına karşı RSA ile şifreler (`MYU.A00`), base64 kodlar, `"2.3-v1.8|" + ciphertext` döndürür. `2.3-v1.8` öneki sabit kodlanmış bir CL protokol-sürüm etiketidir (found literal).
- sonraki modu: saklanan kimlik bilgisi kaydından bir AES anahtarı türetir, aynı `deviceId|randomHex|nonce` üçlüsünü taze rastgele bir IV ile AES/GCM şifreler, aynı sürüm öneki altında `ciphertext|iv` döndürür.

`BinderC48420LDc.Acc`/`Acf`, `keyCode`, `keyXmlPayload`, `controls`, `configuration`, `salt`, `payInfo`, `trust`, `languagePref` anahtarlarıyla bir `Bundle` inşa eder ve `GetCredential` aktivitesini bununla başlatır (found, literal string anahtarlar) — bu, `version.properties`/`validation.properties`'in sadece-asset'e-dayalı önceki bir analizinin "CL" şemasının kullanacağını çıkardığı (`salt`, `payInfo`) tam kelime dağarcığıdır; bu build'in kodu, bunların gerçek çalışma zamanı bundle anahtarları olduğunu, sadece asset-dosyası yer tutucuları olmadığını doğrular.

Binder boyunca kullanılan kripto yardımcısı `C51962N8y`:
- `A00`: Android KeyStore içinde bir **RSA-2048 anahtar çifti** oluşturur, `CN=NPCI_CERT`, SHA-512/PSS, güvenli donanım gerektirir (`isInsideSecureHardware()`, aksi halde fırlatır) ve (SDK'ya bağlı olarak) kısa bir geçerlilik penceresinde kullanıcı kimlik doğrulaması gerektirir — bu, cihaz bağlama anahtarıdır.
- `A03`/`A04`: AES/GCM-NoPadding, 128-bit tag, açık çağıran-sağlanan anahtar ve IV — oturum seviyesinde şifreleme/şifre çözme.
- `A02`: SHA-256 özeti (challenge hash'leme).
- `A01`: saklanan bir AES anahtarı kullanarak `ciphertext|iv` şeklindeki bir string'i şifresini çözer — yukarıdaki `AZO` çıkış formatıyla eşleşir.

`BinderC48420LDc.BW1()`, bir root/tamper kontrolü (build tag'leri, yaygın `su` ikili dosya yolları, `which su` probe'u) çalıştırır **ve** az önce oluşturulan RSA anahtarının StrongBox/TEE destekli olduğunu doğrular; başarısız bir kontrol `BW1()`'in `false` döndürmesine neden olur, bu da kimlik bilgisi verilme yolunu yukarıda gatekeeper'lar (found: boolean dönüş değeri `CRh`/`CRi` mantık yollarında tüketilir, bağımsız olarak bir arayüz mesajına kadar izlenmedi).

### 6.3 Bunun mesaj içeriği için anlamı

UPI MPIN'inin kendisi hiçbir zaman bir sohbet mesajında veya bu raporun bölüm 2 proto alanlarında görünmez — tamamen `GetCredential` aktivitesi içinde işlenir ve yukarıdaki RSA/AES katmanı üzerinden ihraç eden banka/NPCI anahtarı ile değiştirilir, sonunda `SetUpiChangeMpin`/`CheckUpiBalance` (bölüm 9) GraphQL değişkenleri `new_mpin`/`old_mpin`/`mpin` gibi alanlara ulaşan opak bir *kimlik bilgisi blob'u* üretir. GraphQL değişkeninin taşıdığı string'in gerçekten zaten NPCI tarafından şifrelenmiş olduğu (yalnızca TLS ile korunan istemci-düz-metni yerine) **inferred**'dir — çağrıyı önceleyen CL akışının amacından çıkarılmıştır, GraphQL çağrı noktasının byte içeriğini okuyarak bağımsız olarak doğrulanmamıştır.

---

## 7. Şifreleme katmanlaması: sohbet E2E vs NPCI kimlik bilgisi blob'u

Bir ödemede iki bağımsız şifreleme katmanı yer alır ve bunlar birbirine karıştırılmamalıdır (bölüm 13):

| Katman | Korunan | Mekanizma | Kanıt |
|---|---|---|---|
| Sohbet mesajı E2E | bölüm 2'deki her alan (tutar, not, `payeeVpa` içindeki VPA, JID'ler, `MessageKey` referansları) dahil tüm `Message` proto'su | WhatsApp'ın standart Signal-protokolü/Noise oturum şifrelemesi — bu rapor kapsamı dışında, bu katman için diğer RE raporlarına bakın | burada yeniden türetilmedi |
| NPCI kimlik bilgisi/cihaz bağlama blob'u | MPIN, cihaz bağlama challenge/response, NPCI üzerinden ihraç eden banka ile değiştirilen risk-kontrolü payload'ları | cihaz bağlama için RSA-2048 (KeyStore, TEE-bağlı, `CN=NPCI_CERT`); oturum verisi için açık IV'li AES/GCM-128; challenge hash'leme için SHA-256 | bölüm 6.2, found |

İkinci katman **Hindistan/UPI'ye özgüdür** ve GraphQL çağrısının altında/öncesinde çalışır, hiçbir zaman sohbet `Message` proto'su içinde değil. Bu geçişte Brezilya Pix veya Meksika için ödemeye özgü bir AES/RSA katmanı bulunamadı (`unknown` — araştırılmadı).

---

## 8. İşlem durumu senkronizasyonu

### 8.1 Yerel nesne ve history sync (found)

`F7F`, (jenerik mesaj satırı `C13G`'den `D8X.A00(c13g)` ile alınan) bellek içi/yerel ödeme-işlemi nesnesidir. `EKY.A00`, bunu history-sync/companion export için `WebMessageInfo.paymentInfo_`/`quotedPaymentInfo_`'ya eklenen wire-seviyesinde `PaymentInfo`'ya (`DTS`, bölüm 2.8) dönüştürür.

### 8.2 Sunucudan itilen durum güncellemeleri (found, `C24410wL` "PaymentsMessageHandler")

İstemciye bakan push kanalı, `PaymentsMessageHandler.A0A` tarafından dispatch edilen bir `type` niteliğine sahip `<notification>` stanza'sıdır. Gözlenen `type` değerleri ve işlemleri:

| `type` | İşleme |
|---|---|
| `pay` (`hash` ile) | base64 hash decode edilir, yan-liste USync yenilemesi olarak kuyruğa alınır (`EnumC21760rz.A0Q`, `C21820s6.A0N` protokol seti) — durumun kendisini taşımak yerine `WA_USYNC.md`'de belgelenen USync mekanizmasını yeniden kullanır |
| `transaction` | işlemi `C24880x6.A07` ile ayrıştırır, `onPaymentTransactionStatusUpdate`'i loglar, yerel `F7F`'i günceller, bağlı herhangi bir arayüze bir işlem hata string'i gösterir (`InterfaceC35566Fb1.BIp`) ve (flag **1746** + **5049** ile gated) ödeme sonrası eğitim dürtmesi için bir sipariş-özeti "custom item" kartı oluşturabilir |
| `upi` | `consumer_status{value,dhash}` → `onPaymentConsumerStatusUpdate` (Hindistan'a özgü tüketici-uygunluk ping'i, işlem durumundan ayrı) |
| `fbpay` | eski Meta Pay uygunluk ping'i, farklı bir offer-map anahtarıyla `upi` ile aynı handler yolu |
| `account-recovery` | `service=UPI` veya `service=BR`; Hindistan/Brezilya hesap kurtarma akışlarını yönlendirir, flag **1644**/**2000** ile gated |
| `alert`, `step_up`, `merchant_status`, `merchant-update`, `account`, `kyc-state`, `invite`, `alias`, `age_verification_update`, `document_verification_status` | çeşitli arayüz dürtmeleri/uyumluluk güncellemeleri, işlem durumu değil |

### 8.3 Senkronizasyon defteri (found, tercih-anahtarı string'leri)

`payments_all_transactions_last_sync_time`, `payments_block_list_last_sync_time`, `payments_error_map_last_sync_time_millis` — periyodik tam-liste ve hata-map senkronizasyonları mevcuttur (tüketici sınıfları bu geçişte tam olarak izlenmedi; `unknown` periyot).

---

## 9. GraphQL / MEX ödeme operasyonları

### 9.1 İki taşıma, iki şema (found)

| Şema | Taşıma | Sayı (bu build) |
|---|---|---|
| `whatsapp` (`www` katalog) | kalıcı-doc_id GraphQL POST, taşıma mekanizmasının kendisi `inferred` (bu geçişte bir HTTP/IQ çağrı noktasına kadar izlenmedi) | 81 ödeme-etiketli operasyon |
| `whatsapp_mex` (`mex` katalog) | mevcut stanza bağlantısı üzerinden `w:mex` IQ (`xmlns="w:mex"`) | 1 ödeme-etiketli operasyon: `PaymentsIsAccountRecoverable` (doc_id `27351347491148282`) |

Kaynak: `assets/whatsapp-android-www_client_persist_ids.json` ve `assets/whatsapp-android-mex_client_persist_ids.json`, ikisi de çalışma zamanında okunan first-party deklaratif asset'ler (found, bir trafik yakalamadan sonraki en güçlü seviye — doc_id değerlerinin kendisi "tested" değildir, yalnızca gönderilen asset içinde mevcut olduğu doğrulanmıştır).

### 9.2 Çağrı noktası doğrulamalı değişkenlerle temsili operasyonlar (found)

| Operasyon | doc_id | Tip | Değişkenler |
|---|---|---|---|
| `GetUpiAccounts` | `25691302307224710` | Query | `bank_code`, `device_id`, `provider_type`, `account_type` |
| `CheckUpiBalance` | `37205951525662520` | Query | `credential_fbid`, `device_id`, `mpin`, `seq_no`, `upi_bank_info`, `vpa`, `cl_version`, `device_ssid`, `request` |
| `SetUpiChangeMpin` | `27149786891388216` | Mutation | `credential_fbid`, `device_id`, `new_mpin`, `old_mpin`, `seq_no`, `upi_bank_info`, `vpa` |
| `GetUpiBankList` | `27764018976534565` | Query | `account_type`, `provider_type`, `request` |
| `GetUpiToken` | `25639185495767704` | Query | `challenge`, `device_id`, `token_type`, `provider_type` |
| `UpiCreateMandate` / `UpiAcceptMandate` | `26775212245448044` / `26786867597629452` | Mutation | paylaşılan çağıran (`C42562IuV`): `frequency_rule`, `mandate_no`, `purpose_code`, `recurrence_day`, `recurring_rule`, `ref_id`, `device_id`, `top_up_amount`, `provider_type`, `upi_banks`, `is_revocable`, … |
| `CreateEnrollment` | `34570903025891763` | Mutation | `participant_id`, `device_id` |
| `GenRaisePaymentComplaint` | `27569318002686860` | Query | `complaint_type`, `reason`, `transaction_ref_id`, `user_description` |
| `PaymentsIsAccountRecoverable` (MEX) | `27351347491148282` | Query | bulunamadı (muhtemelen `{}`) |

`CheckUpiBalance`'ın `cl_version` ile birlikte okunan bir `mpin` değişkeninin varlığı, bölüm 6.3 ile tutarlıdır: değişken adının kendisi içeriğin önceden şifrelendiğini kanıtlamaz, ancak açık bir CL protokol-sürümü string'iyle birlikte seyahat etmesi, bu değerin ancak CL alışverişinden geldiğinde mantıklı olduğunu gösterir.

**Uyarı (bir sınırlama olarak found, WhatsApp hakkında bir bulgu değil):** `GenCreatePaymentKey`, `RevokeEnrollment` ve `BrSaveCPF`'nin hepsi kaynak katalogdaki *aynı* paylaşılan çağıran sınıflara (`C42325Iq9`/`C42327IqB`, `RunnableC42211IoJ`) çözümlenir, bu da o çağıranın yakınındaki her string literal'i her üç operasyon için de "değişkenler" olarak döndürür — bu fazla toplar (örn. Pix'e özgü alanlar olan `pix_key`, UPI-adlı bir operasyon altında görünür). Bu üç özel operasyon için uzun değişken listelerini gürültülü bir superset olarak değerlendirin, doğrulanmış operasyon-başına şema olarak değil.

81 girdilik katalogdaki kalan operasyonlar (tam liste: `UpiPauseMandate`, `UpiResumeMandate`, `UpiRevokeMandate`, `UpiRejectMandate`, `UpiExecuteMandate`, `GetUpiLiteDetails`, `GetUpiP2mConfig`, `GetUpiPurposeLimitingKey`, `GetUpiSmsContentAndVmn`, `PaymentReminderCreate/Get/Cancel/Stop`, `GetBillReceipt`, `GetBillerPlans`, Brezilya Pix (`GetPixInfo`, `GetPixBankList`, `GetMerchantPixInfo`, `CompletePixTransaction`, `GenPayWithPixPrecheck`), biyometrik/passkey (`Br*Passkey*`, `BrAuthorizeBiometricPayment`) ve `Wamo*` abonelik/promosyon operasyonları) doc_id'leriyle katalogdadır ama bu geçişte bireysel olarak bir çağrı noktasına karşı yeniden doğrulanmadı — varlıklarını `found` olarak değerlendirin (2.26.41.6 asset'inde literal girdilerdir) ve yukarıda listelenmedikçe tam talep şekillerini `unknown` olarak değerlendirin.

---

## 10. NPCI OTP otomatik okuma kuralları (Hindistan/UPI'ye özgü)

`assets/npci/npci_otp_rules.json` (found, 5 kural), bir UPI akışı sırasında gelen bir banka/NPCI SMS'inden 6 haneli bir OTP'yi otomatik olarak çıkarmak için `org.npci.upi.security.pinactivitycomponent.C0315u` tarafından tüketilir — bu, sadece yazma kolaylığı içindir, OTP'yi üretmez, doğrulamaz veya iletmez. Tüm 5 kural `sender: ["[a-zA-Z]+"]`'i (alfabetik kısa kod) ve `otp: "\d{6}"`'yi paylaşır; sadece tetikleyici ifade farklıdır (`"is your OTP"`, `"OTP is"`, `"one time password is"`, `"is your one time password"`, `".*OTP for Aadhaar.*"`). Çağıran, sıfır olmayan bir uzunluk geçtiğinde çalışma zamanında OTP hane-sayısı regex'ini (`\d{` + `i` + `}`) geçersiz kılabilir. `"Aadhaar"`/`"AADHAAR"` içeren bir gövde `otp_type_aadhaar` SharedPreferences anahtarı altında önbelleğe alınır, aksi halde `otp_type_bank`.

Bu asset ve tüketici sınıfı, önceki bir `2.26.34.4` analizinden tür olarak değişmemiştir; bu geçişte 2.26.41.6'ya karşı byte-byte yeniden diff edilmedi (`inferred` süreklilik, yeniden doğrulanmadı).

---

## 11. Feature flag'ler

`PaymentsMessageHandler`'da (`C24410wL`, found çağrı noktaları) doğrudan okunan AB-prop id'leri, aksi belirtilmedikçe. Bölüm 2 proto alanlarının kendisini gate eden hiçbir sayısal flag id bulunamadı (bunlar wire üzerinde şartsızdır); bu geçişte bulunan tüm flag'ler sunucu push'larının veya arayüz dürtmelerinin *işlenmesini* gate eder.

| Flag | Kontrol ettiği |
|---|---|
| **1458** | sunucu bir UPI ödeme takma adını `deregistered` olarak raporladığında yerel olarak önbelleğe alınmış takma adı kaldırır |
| **1644** | UPI hesap kurtarma uygunluğu (`payments-enabled:account-recovery-enabled`) |
| **2000** | Brezilya Pix hesap kurtarma uygunluğu (`service=BR` için eşdeğer geçit) |
| **1746** + **5049** (ikisi de gerekli) | tamamlanan bir ödeme sonrası gösterilen işlem sonrası "custom item"/sipariş-özeti eğitim kartı (BIP eğitim dürtmesi) |
| **12214** | UPI hesap kurtarma sırasında FB-kullanıcı-oluşturma yolu (doğrudan kurtarma çağrısına karşı) |
| **423** | ödemeler davet-kullanıldı takibi, eski yol |
| **544** | ödemeler davet-kullanıldı takibi, ek yol (423 ile OR üzerinden birlikte kontrol edilir) |
| **20869** | hesap-kurtarma bildirimi işlenirken PSP allow-list kontrolü; eşlik eden string tercih `32353` (virgülle ayrılmış opt-in PSP listesi, sayısal bir flag değil, string-değerli bir AB prop üzerinden okunur) |

Bu geçişte Hindistan-UPI onboarding aktivite sırasını (bölüm 4) veya NPCI CL cihaz bağlama yolunu (bölüm 6) özel olarak gate eden hiçbir feature-flag id'si bulunamadı — `unknown`, yukarıdaki handler sınıfının ötesinde izlenmedi.

---

## 12. Hata / red sebebi kodları

### 12.1 Protokol içi red/iptal (found)

Bölüm 2.4'te belirlendiği gibi, `declinePaymentRequestMessage`/`cancelPaymentRequestMessage` **sadece** orijinal taleple ilişkili bir `MessageKey` referansı taşır — sebep enum'u yok, serbest metin alanı yok. "reddedildi: yetersiz bakiye" veya benzeri gösteren bir istemci, bunu decline/cancel mesajının kendisinin ilettiği bir şeyden değil, **yerel** durumdan (gönderenin kendi arayüz kopyası veya ilişkilendirilmiş sonraki bir `transaction`/`PaymentInfo` durumu, bölüm 8) yapıyordur.

### 12.2 PaymentInfo durum alanları (varlık found, eşleme unknown)

`DTS.status_` (alan 4) ve `DTS.txnStatus_` (alan 10) ayrı enum-tipli alanlardır (bölüm 2.8). Ordinal→etiket eşlemeleri sadece javalite bytecode'undan kurtarılamadı (enum sabit adları, build'in `Internal.EnumVerifier` sınıflarının obfuscation'ı tarafından silinmiştir) — `unknown`. `futureproofed` (alan 8, bool), gönderenin yerel nesnesinin çözümlenebilir bir tutar/para birimi olmadığında ayarlanan kasıtlı bir kaçış kapısıdır, daha yeni bir istemcideki bir alıcının aksi halde ayrıştıramayacağı bir durumu render etmesine izin verir.

### 12.3 Sunucudan itilen hata map'i (found tercih anahtarları, tüketici tam izlenmedi)

Tercih anahtarları `payments_error_code`, `payments_error_text`, `payments_error_title`, `payments_error_map_tag`, `payments_error_map_last_sync_time_millis`, hata kodlarının sabit bir istemci-tarafı enum veya string tablosuna karşı değil, **sunucu-senkronize bir map**'e (kod → başlık/metin) karşı çözüldüğünü gösterir. Bu, bir kullanıcıya gösterilen red/hata *metninin* bir uygulama güncellemesi olmadan zaman/bölgeye göre değişebileceği anlamına gelir. Bu senkronizasyonu yapan sınıf bu geçişte tanımlanmadı (`unknown`).

### 12.4 NPCI CL katmanı başarısızlıkları (found, yapılandırılmış kod yok)

`BinderC48420LDc.BW1()` (cihaz bütünlük kontrolü), `CRH`/`CRh`/`CRi` (cihaz-sertifikası/durum doğrulama) hepsi **sessizce** başarısız olur — AIDL sınırı boyunca boolean'ın ötesinde hiçbir hata kodu yüzeye çıkarmadan `false` döndürür/fırlatır. Bir CL-katmanı başarısızlığı için kullanıcıya görünen herhangi bir mesaj, bu nedenle tamamen WhatsApp tarafında boolean sonuçtan inşa edilir, NPCI tarafından sağlanan bir koddan değil (`inferred`, bölüm 6.1'deki AIDL arayüz şeklinde hata-kodu-döndüren metot olmamasıyla tutarlı).

---

## 13. Hindistan/UPI'ye özgü vs genel — açık ayrım

| Bulgu | Kapsam |
|---|---|
| `sendPaymentMessage`/`requestPaymentMessage`/`declinePaymentRequestMessage`/`cancelPaymentRequestMessage`/bölüşmeli ödeme/`PaymentInviteMessage`/`PaymentReminderMessage` proto alanları (bölüm 2) | **genel** — raydan bağımsız olarak aynı `Message` proto alanları; `payeeVpa` (bölüm 2.6) UPI-tadında olan tek alan adıdır ama alanın kendisi şemada şartsız olarak mevcuttur |
| `PaymentInfo` (`DTS`) işlem-durumu nesnesi (bölüm 2.8, 8) | **genel** yapı; `useNoviFiatFormat` ve eski `FBPAY`/`NOVI`/`PIX`/`UPI` servis kodları, aynı nesne/bildirim yolunun tüm raylar arasında paylaşıldığını gösterir |
| Ray paketleri `indiaupi`, `brazilpay`, `mexico`, `indonesia`, `upr` (bölüm 3) | paket bazında açıkça bölünmüş; `upr`/`common` raydan bağımsız, geri kalanı tek-ülkelik |
| VPA bağlama, UPI mapper akışı, onboarding aktiviteleri (bölüm 4) | **sadece Hindistan/UPI** |
| NPCI "CL" kimlik bilgisi/cihaz bağlama kütüphanesi, RSA/AES kripto, OTP otomatik okuma (bölüm 6, 7, 10) | **sadece Hindistan/UPI** — bu katmanın tamamı araştırılan kodda Pix/Meksika/Endonezya için yoktur |
| GraphQL doc_id katalogu (bölüm 9) | karma — katalogun kendisi tek bir şema altında UPI, Pix, biyometrik/passkey (Brezilya) ve raydan bağımsız (`Wamo*`, `Gen*`) operasyonları kapsar; her operasyonun kapsamı kendi adını/önekini takip eder (`Br*` = Brezilya, `Upi*`/`GetUpi*`/`SetUpi*` = Hindistan) |
| `PaymentsMessageHandler` bildirim tipleri (bölüm 8.2) | karma — `pay`/`transaction`/`alert`/`step_up`/`account` tarzı tipler jeneriktir; `upi` tipi ve `service=UPI` dalları Hindistan'a özgüdür, `service=BR` dalları Brezilya'ya özgüdür |

---

## 14. Baileys notu

Baileys-tarzı istemciler bölüm 2'deki mesaj tiplerini inşa edebilir ve ayrıştırabilir (standart `Message` üzerinde düz protobuf alanlarıdır) ve prensipte `whatsapp`/`whatsapp_mex` GraphQL doc_id'lerini el yapımı değişkenlerle çağırabilir. Bir UPI ödemesini anlamlı şekilde tamamlaya**mazlar**: bölüm 6'daki MPIN/cihaz bağlama alışverişi, resmi uygulama dışında eşdeğeri olmayan gerçek bir banka/NPCI arka uç güven ilişkisine (TEE destekli RSA anahtarı, `CN=NPCI_CERT`) bağlı, gömülü, NPCI-imzalı bir native Android bileşeni üzerinden çalışır. Bir Baileys `sendPaymentMessage`'ı, bu nedenle gerçek NPCI akışından gerçekten yetkilendirilmiş bir işlemle eşleştirilmedikçe protokol-doğru ama işlevsel olarak etkisiz bir mesajdır.

---

## 15. Hata durumları / dikkat edilmesi gerekenler

| Belirti | Sebep | Düzeltme / not |
|---|---|---|
| Decline/cancel mesajının wire'da görünür bir sebebi yok | protokol tasarımı (bölüm 2.4) — sadece bir `MessageKey` geri-referansı var | mesajın kendisinden bir sebep kodu beklemeyin; sonraki bir `transaction` bildirimi veya yerel durumla ilişkilendirin |
| `BW1()` ile gate edilen kimlik bilgisi operasyonu hata metni olmadan başarısız oluyor | cihazda StrongBox/TEE yok, veya root'lanmış | WhatsApp tarafına sadece boolean bir başarısızlık olarak yüzeye çıkar; ek loglama olmadan diğer CL başarısızlıklarından ayırt edilemez |
| `mpin`/`new_mpin`/`old_mpin` GraphQL değişkenleri decompile edilmiş bir çağrı-noktası dökümünde düz metin gibi görünüyor | bunlar CL alışverişi (bölüm 6.3) tarafından üretilir, GraphQL çağrısına doğrudan yazılmaz | çalışma zamanındaki gerçek byte'ları izlemeden düz-metin PIN iletimi varsaymayın — bu rapor bunu yaptığını iddia etmiyor |
| `GenCreatePaymentKey`/`RevokeEnrollment`/`BrSaveCPF` çok büyük, Pix-tadında değişken listeleri gösteriyor | doc_id katalog çıkarımında paylaşılan çağıran sınıfı fazla toplaması (bölüm 9.2) | gürültülü olarak değerlendirin, güvenmeden önce alan başına doğrulayın |
| `txnStatus`/`status` enum değerleri adlandırılamıyor | obfuscate edilmiş `EnumVerifier` sabit adlarını siler | çalışma zamanı string ilişkilendirmesi gerektirir (ordinallere eşlenen arayüz kaynak string'leri), bu geçişte yapılmadı |

---

## 16. Karıştırılmaması gereken ayrımlar

| Karıştırılmaması gereken | Detay |
|---|---|
| sohbet-mesajı E2E vs NPCI kimlik bilgisi blob'u (bölüm 7) | iki ayrı kripto katmanı; ikincisi sadece Hindistan/UPI'ye özgüdür ve `Message` proto'sunun tamamen dışında oturur |
| `DTS` PaymentInfo vs dört sohbet ödeme mesaj tipi | `DTS` bir history-sync/durum nesnesidir (`WebMessageInfo.paymentInfo_`), hiçbir zaman bağımsız olarak gönderilebilir bir sohbet mesajı değildir |
| `DTS` üzerinde `status` vs `txnStatus` | iki bağımsız enum, farklı taneli (granularity), bu build'de ordinal seviyesinde ikisi de opak |
| `www`/`whatsapp` şema vs `mex`/`whatsapp_mex` şema doc_id'leri | farklı taşıma (kalıcı-doc_id GraphQL POST vs `w:mex` IQ); bu build'de ödeme operasyonlarının neredeyse tamamı `www`/`whatsapp` tarafındadır |
| "UPR" raydan bağımsız onboarding vs Hindistan UPI onboarding | UPR (`com.whatsapp.payments.upr`) daha yeni, jenerik bir kabuktur; Hindistan'a özgü `indiaupi` onboarding aktiviteleri (bölüm 4) 2.26.41.6'da hâlâ yan yana bulunan ayrı, daha eski, çok daha büyük bir akıştır |
| NPCI "Common Library" (`org.npci.upi.*`) vs WhatsApp'ın kendi `com.whatsapp.payments.*` kodu | ilki kendi AIDL yüzeyine sahip üçüncü taraf gömülü bir bileşendir; WhatsApp kodu sadece onu başlatır ve opak bir string/bundle'ı geri okur |

---

## 17. Tam akış (Hindistan UPI, para gönderme durumu)

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

## 18. Bilinmeyenler

| Konu | Sebep |
|---|---|
| `splitPaymentMessage`, `splitPaymentUpdateMessage`, `paymentReminderMessage` için üst seviye `Message` alan numaraları | bilgi-string decode'u bu geçişte yeterince ileri taşınmadı; alt mesajın kendi alanları (bölüm 2.5/2.6) etkilenmemiştir |
| `DTS.status_`/`txnStatus_` enum etiket eşlemesi | obfuscate edilmiş `EnumVerifier`, sabit adları silinmiş |
| `whatsapp`-şemalı (`www`) kalıcı-doc_id GraphQL çağrıları için tam taşıma mekanizması | bu geçişte bir HTTP/IQ çağrı noktasına kadar izlenmedi; her yerde `inferred` olarak işaretlendi |
| `payments_error_map_*` sunucu-senkronize hata map'i için tüketici sınıf(lar)ı | tercih anahtarları bulundu, okuyan/yazan sınıf tanımlanmadı |
| `mexico`/`indonesia`/`dcp`/`phoenix` paket içeriği | paket varlığı doğrulandı, içeriği araştırılmadı |
| GraphQL `mpin`/`new_mpin`/`old_mpin` değişkenlerinin halihazırda NPCI-şifreli bir blob mu taşıdığı yoksa ek korumanın sadece TLS seviyesinde uygulanıp uygulanmadığı | CL akışının amacından çıkarıldı, gerçek çalışma zamanı byte içeriği incelenerek doğrulanmadı |
| Hindistan-UPI onboarding sırasını veya CL cihaz bağlama yolunun kendisini gate eden feature-flag id'leri (varsa) | araştırılan sınıflarda bulunamadı |
| `npci_otp_rules.json` ve `.properties` CL asset'lerinin `2.26.34.4` (önceki bir analiz) ile `2.26.41.6` arasındaki byte-byte sürekliliği | yeniden diff edilmedi; tüketen sınıflar ve çalışma zamanı bundle-key kelime dağarcığı 2.26.41.6'da bağımsız olarak yeniden doğrulandı, asset byte'larının kendisi değil |
| Gerçek trafik / canlı işlem davranışı | sadece statik analiz, trafik yakalama yok, canlı işlem gerçekleştirilmedi |
