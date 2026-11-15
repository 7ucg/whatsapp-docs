<!-- src-sha1: 349e8112a4dcc4567ce203cf21c4c37e5bb47173 -->
# WhatsApp Business Uygulaması — Full RE Report
**Sürüm:** 2.26.45.7 (Business) vs 2.26.45.10 (consumer) | **Tarih:** 2026-11-15
**Kapsam:** WhatsApp Business APK'sının (`com.whatsapp.w4b`) consumer WhatsApp'a (`com.whatsapp`) karşı yapısal diff'i — Business'a özel paket kökleri, React Native stack'i, native-kütüphane diff'i, GraphQL/MEX/`www`/`facebook-schema` doc_id kataloğu asimetrisi, izin diff'i; WhatsApp Business API/Cloud API'den ve Managed Account'tan farkı

---

## 1. Genel bakış

WhatsApp Business, consumer WhatsApp içinde bir mod değiştirici değil, ayrı bir uygulamadır (`com.whatsapp.w4b`). Signal-protokolü çekirdeğini, Noise transport'unu ve sohbet UI'sinin çoğunu consumer WhatsApp ile paylaşır, ama business-özel özellikler için kendi paket kümesini gönderir ve consumer'ın hiç taşımadığı bir bağımlılık — tam bir React Native runtime'ı — paketler.

Bu rapor sadece **uygulamanın kendisini** consumer WhatsApp'a karşı APK olarak diff'lenmiş şekilde kapsar. Bu, bu repoda zaten belgelenmiş diğer iki "business"-bitişik kavramdan farklı bir eksendir:

| Kavram | Ne olduğu | Rapor |
|---|---|---|
| **WhatsApp Business uygulaması** (bu rapor) | Bir işletmenin bir telefona kurduğu, kataloğu, etiketleri, otomatik yanıtları, reklamları için kendi UI'sine sahip ayrı bir istemci APK'sı (`com.whatsapp.w4b`) | burada |
| **WhatsApp Business API / Cloud API** | Bir işletme numarasının mesajlarını barındıran/relay eden, Business uygulaması yerine ya da onunla birlikte kullanılan sunucu tarafı altyapı; herhangi bir istemcide sadece doğrulanmış-ad sertifika alanları (`host_storage`, `actual_actors`, issuer prefix `smb:`/`ent:`) ve `business_state_id` coexistence banner'ları üzerinden sinyallenir | `WA_MANAGED_ACCOUNT.md` §9 |
| **Managed Account** | Bir ebeveyn/vasi tarafından denetlenen bir reşit olmayanın kendi consumer hesabı (`ManagedAccount*`/PAA/PMA/PMTA); her iki business kavramıyla da ilgisizdir, business durumu için "managed" etiketi yoktur | `WA_MANAGED_ACCOUNT.md` §1-8 |

Tek bir işletme üçünü birleştirebilir: bir cihazda Business uygulamasını çalıştırabilir, trafiğinin bir kısmını bir Cloud API sağlayıcısına devredebilir (coexistence), sohbet ortağının hesabı sıradan bir consumer hesabı olurken. Bunların nasıl etkileştiği için bkz §9.

Kanıt kaynağı: `WA-Business_2.26.45.7.apk` ile `WhatsApp_2.26.45.10.apk` (diff zamanındaki mevcut beta çifti, sürüm-üstü-sürüm bir karşılaştırma değil) arasında statik bir paket/asset/manifest diff'i. Her iki tarafta da tam-APK jadx decompile çalıştırılmadı (sert güvenlik kuralı); aşağıdaki tüm bulgular apktool smali-ağacı, asset-JSON ve reconstruct-manifest seviyesindedir. Kademeler, brain'in evidence contract'ına göre `found`/`inferred`/`unknown`'dır.

---

## 2. Paket-seviyesi diff — found

Her apktool ağacındaki `smali*/` altındaki her dizini karşılaştırarak: Business'ın 4.281 benzersiz paket-yolu dizini var (15 `smali_classesN` ağacı), consumer'ın 3.710 (14 ağaç). 853 yol sadece Business'ta, 282 yol sadece consumer'da bulunuyor. 45 üst-seviye `com/whatsapp/*` paket kökü Business'a özeldir (kök dizinin kendisi consumer'da yok, sadece bir alt-yol değil).

### 2.1 Özellik kümesine göre Business'a özel paket kökleri

| Küme | Paket kökleri | Notlar |
|---|---|---|
| Otomatik-yanıt / karşılama / hızlı-yanıt mesajlaşması | `businessaway`, `businessgreeting`, `businessquickreply`, `businessmissedcallfollowup` | temel SMB otomatik-yanıt özellikleri |
| Etiketler / temsilciler / sohbet atama | `chatassignment`, `authagent`, `authagentfeaturecontrol`, `smbmultideviceagents`, `businesscontactmanager`, artı `lists/smb/labels` (alt-yol; `lists` kökü paylaşımlıdır) | temsilci koltukları ve etiket düzenleme |
| Profil kurulumu / doğrulama | `businessregistration`, `protectedbusinessaccounts`, `metaverified` | |
| Katalog/siparişler (yönetim tarafı) | `ordermanagement` | kataloğun kendisine göz atma/düzenleme (`catalog`, `businessproduct`, `businesscollection`) **paylaşımlıdır** — bkz §2.2 |
| Reklamlar / Meta Ads entegrasyonu | `ads4ads`, `adscreation`, `adcreationinterfaces` | React Native bağlantısı için bkz §3 |
| Faturalama / abonelikler (API katmanları) | `metabilling`, `metabillingui`, `subscription`, `billingui` | |
| Uygulama-API coexistence | `coexistence`, `connectedaccounts`, `linkedaccounts`, `dynamicaudience` | Cloud API tarafına köprüler, §9 |
| Meta AI business agent | `bizai`, `genai`, `maiba` | |
| Business araçları / compliance | `businesstools`, `businessinsights`, `rapidfeedbacksurvey`, `reportblocksharing`, `statistics`, `integrityenforcementsinfra`, `eligibilitychecker`, `googleeligibilityapi`, `smb`, `smbauth`, `waloginmbs`, `marketingmessage`, `marketingmessagemanagement`, `mediatemplates`, `bizdatasharing`, `bizgallerypicker`, `bizmedia` | |

### 2.2 Business'a özel alt-paketleri olan paylaşımlı kökler

Bazı kökler her iki uygulamada da bulunur çünkü consumer, business-tarafı veriyi görüntüleyebilir/tüketebilir, ama düzenleme/yönetim alt-paketleri sadece Business'tadır:

- `com/whatsapp/businessprofile/` — paylaşımlı kök; `businessprofileaddress`, `businessprofilecategory`, `businessprofileedit` (+ `boostmedia`, `businessprofilecompleteness`), `businessvertical`, `businesscompliance/smb/...` sadece Business'tadır. Consumer sadece okuma-tarafı profil-görüntüleme alt-paketlerini tutar.
- `com/whatsapp/lists/` — paylaşımlı kök (etiket veri modeli/UI'si, her ikisinde de `labelitem`); etiket-**düzenleme** alt-paketi `lists/smb/labels` sadece Business'tadır.
- `catalog`, `businessproduct` (+ `businessproductlist`), `businesscollection` — paylaşımlı kökler, consumer'ın smali ağacında, bir business sohbeti görüntülerken gösterilen katalog/ürün **göz atma** UI'si olarak mevcut olduğu doğrulanmıştır.

Net şekil: katalog/ürün görüntüleme, business-profil görüntüleme ve etiket görüntüleme paylaşımlıdır; katalog/profil düzenleme, otomatik-yanıt/karşılama/hızlı-yanıt mesajlaşması, etiket düzenleme, temsilci/multi-device auth, reklam oluşturma ve Cloud-API coexistence Business'a özeldir.

### 2.3 Consumer'a özel paketler — found, kümelenmemiş

282 yol sadece consumer'da bulunur. Hızlı bir kontrol, Business'a-özel kümeyle boyut olarak karşılaştırılabilir tematik bir küme ortaya çıkarmadı; büyük kısmı daha küçük sayıda consumer-sadece kökün iç içe çocuklarıdır. Derinlemesine incelenmedi — §8'de açık bir boşluk olarak listelenmiştir.

---

## 3. React Native stack'i — found, Business'a özel

Beklenmedik bulgu: Business, sadece ekstra bir özellik modülü değil, paket seviyesinde consumer'da bulunmayan tam bir React Native stack'i paketler.

| Paket | Business | Consumer |
|---|---|---|
| `com/facebook/react/*` (bridge, fabric, animated, devsupport, turbomodule, …) | 88 dizin | 0 |
| `com/facebook/catalyst/*`, `com/facebook/fbreact/*` (RN bridge modülleri, i18n, safe-area) | mevcut | yok |
| `com/facebook/hermes/*` | 3 dizin | 1 dizin — sadece başıboş bir referans, onunla eşleşecek `com/facebook/react` yok, yani çalışan bir RN runtime'ı değil |
| `com/caverock/androidsvg`, `com/crossapp/graphql/facebook/*` | mevcut | yok |

Native-kütüphane seviyesinde doğrulandı (§4): `libreactnative.so` (RN runtime'ı), `libappmodules.so` (RN JS bundle'ının native yükleyicisi) ve `libimagepipeline.so` (Fresco, RN'nin görüntü hattı), Business'a özel `.so` dosyalarıdır.

**Inferred**, doğrulanmamış: bazı Business-sadece yüzeyler — en olası reklam oluşturma (`adscreation/lwi/react/*`, `lwi`'nin doğrudan içinde bir `react` alt-paketine sahiptir), Meta-billing veya coexistence onboarding'i — native Android UI'si yerine gömülü React Native ekranları olarak uygulanmıştır. Hangi belirli özellik(ler)in RN stack'ini kullandığı sadece paket adlarından doğrulanmamıştır; `adscreation/lwi/react/activity` sınıflarının kapsamlı bir decompile'ı gerekir. Bu, kalan en açık "şaşırtıcı bağımlılık"tır: bir business mesajlaşma uygulaması, görünüşe göre sadece bir veya birkaç ekran için, çapraz-platform bir JS UI runtime'ı gömüyor (reklam oluşturma en güçlü isimlendirme eşleşmesidir).

---

## 4. Native kütüphane diff'i — found

İki uygulamanın reconstruct çıktıları arasında `superpack_index.csv`'yi (SUPERPACK_OB konteynerinin kendi kütüphane manifestosu) karşılaştırıldı:

| | Sayı |
|---|---|
| Kataloglanmış consumer kütüphaneleri | 84 |
| Kataloglanmış Business kütüphaneleri | 89 |

**Business'a özel (5):** `libappmodules.so`, `libimagepipeline.so`, `libreactnative.so`, `libwacomponents.so` (isim, stock RN değil, WhatsApp-yazımı bir RN bridge-bileşen kütüphanesi olduğunu ima ediyor), `libzstddecoder.so` (muhtemelen RN bundle/asset sıkıştırma açma).

**Consumer'a özel:** yok — her consumer kütüphane adı Business indeksinde de görünüyor.

Her iki uygulama tarafından paylaşılan 6 cihaz-oracle-decompile edilmiş kütüphane (`libwhatsapp.so`, `libwhatsappmerged.so`, `libwasafe.so`, `libvoprf-ed25519.so`, `libohai.so`, `libcurve25519.so`), iki uygulama arasında aynıdır (aynı boyutlar, aynı sembol/export sayıları) — Signal-protokolü/attestation/client-integrity çekirdeği Business build'i tarafından değiştirilmemiştir. React Native + Fresco stack'i, hem Java/Kotlin paket seviyesinde hem de native-kütüphane seviyesinde Business'a özeldir — tutarlı, iki-katmanlı bir bulgu.

---

## 5. GraphQL / MEX / `www` / `facebook-schema` doc_id kataloğu diff'i — found

Her uygulama kendi `assets/whatsapp-android-<schema>_client_persist_ids.json` doc_id kataloğunu gönderir, apktool-decode edilmiş asset ağacından doğrudan okunur (decompile'a gerek yok).

| Schema | Business operasyonları | Consumer operasyonları | Business-sadece | Consumer-sadece |
|---|---|---|---|---|
| `mex` | 242 | 242 | 0 | 0 — özdeş küme |
| `wamo` | 22 | 22 | 0 | 0 — özdeş küme |
| `www` | 237 | 244 | 4 | 11 |
| `facebook-schema` | 224 | 17 | 215 | 7 |

### 5.1 `mex` ve `wamo` — uygulamalar arasında özdeş

Her iki katalog da her iki APK'da tam olarak aynı operasyon adlarına sahip (küme farkı sıfırdır, sadece sayıca eşit değildir). Business, bu schema seviyesinde Business'a-özgü hiçbir MEX/GraphQL yüzeyi taşımıyor — consumer kataloğunu bütünüyle paylaşıyor.

### 5.2 `www` — küçük bir asimetri

- Business-sadece (4): `BPAccessTokenAndSessionCookiesMutation`, `CatkitTypeaheadProxy`, `WACreateEnforcementAppeal`, `WAGetEnforcementAppealStatus`.
- Consumer-sadece (11): `WaAutofillAcknowledgeWalletTerms`, `WaAutofillFetchContactData`, `WaAutofillFetchSettings`, `WaAutofillSaveContactData`, `WaAutofillUpdateNegativeInteraction`, `WaAutofillUpdateSaveCvv`, `WaCreateLabyrinthBackupMutation`, `WaDeleteLabyrinthAccountMutation`, `WaDeleteLabyrinthThreadsMutation`, `WaRotateLabyrinthEpochMutation`, `WaUploadLabyrinthMessagesMutation`.

Consumer, Business'ın sahip olmadığı kendi kişisel-ödemeler/autofill (`WaAutofill*`) ve E2E sohbet-yedekleme (`WaCreateLabyrinthBackupMutation` vb. — WhatsApp'ın sohbet-yedekleme sistemi, dahili olarak "Labyrinth") operasyonlarını taşır; Business, consumer'ın gerek duymadığı birkaç hesap-enforcement-itirazı ve oturum/typeahead operasyonu taşır.

### 5.3 `facebook-schema` — manşet bulgu: 215 Business-sadece operasyon

Gerçek Business-özgü GraphQL yüzeyi burada yaşar — iki uygulama arasında byte-özdeş olan `mex`/`wamo`'da değil. Business bu schema'da 224 operasyon taşıyor, consumer'ın 17'sine karşı; consumer'ın 17'si Business'ın taşımadığı ilgisiz kişisel-ödeme/ticaret-nonce operasyonlarıdır (`AcDcCreateCanonicalDigitalCommerceNonce`, `WaAutofillAddPayCreditCard`, `WaGetServerEncryptionKey`, vb.).

215 Business-sadece operasyon, isme göre kümelenmiş (açıklayıcı gruplama, statik-analiz-türevli, doğrulanmış bir işlevsel taksonomi değil):

| Küme | Örnek operasyonlar |
|---|---|
| Bilgi tabanı / AI-yanıt / simülasyon ("coach") | `FetchAIAbilities`, `KnowledgeRepoFetchV2`, `UpdateAIKnowledge`, `DeleteAIKnowledge`, `CoachSimulationMessage`, `CoachSuggestedReply`, `StartSimulation`, `SubmitSimulationFeedback`, `FetchSuggestedReply`, `MarkSuggestedReplyUsed` |
| Meta AI biz agent / MAIBA | `MAIBAOnboarding`, `MAIBACompleteParallelOnboarding`, `Maiba1pCalendarEvents`, `MaibaGetCurrentCatalog`, `MaibaDownloadLeadGenFlow`, `MetaAIBizAgentWAAIHome`, `MetaAIBizAgentWACoachingMutation` |
| Lead-gen / randevular | `CreateLeadGenFlow`, `GetLeadGenFlowLeads`, `UpdateLeadStages`, `CreateAppointmentFlow`, `GetAppointmentPrefill`, `GetDefaultAvailability` |
| Auth agent / SMB multi-agent / login | `AuthAgentCompanyInfoQuery`, `AuthAgentFeaturePolicyQuery`, `AddSmbAgentAndCoexQr`, `SmbRegistrationInit`, `WALoginClaimAuthChallenge`, `WALoginConfirmAuthChallenge` |
| Uygulama-Cloud-API coexistence | `CoexUnifiedOnboarding`, `CoexMultiAppEligiblity`, `CoexAppsAndServicesOffboardProduct`, `CoexCompanionPairingStatusCallback`, `CoexistenceQRCodeFetch` |
| Click-to-WhatsApp reklamları (CTWA) | `CTWACreateLookAlikeAudienceMutation`, `CTWAPreviousAdsRecommendationQuery`, `CtwaLinkedMediaQuery`, `CtwaNativeUploadAdMediaMutation` |
| Reklam hesabı / uygunluk | `AdAccountEligibilityCheckerQuery`, `OnboardToWhatsAppAdAccount`, `WhatsAppBizFetchAdDefaults`, `WhatsAppBizGetEstimatedAdReach` |
| Katalog yönetimi (yazma tarafı) | `WhatsAppCatalogAddProduct`, `WhatsAppCatalogEditProduct`, `WhatsAppCatalogDeleteProduct`, `WhatsAppCatalogCreateCollections`, `WhatsAppCatalogProductVisibilityUpdate` |
| Pazarlama-mesajı yayını ("Pro") | `BusinessBroadcastProCampaignContent`, `BusinessBroadcastProCustomAudiencesQuery`, `BusinessBroadcastProInsights`, `WAMarketingMessagesCustomAudienceCreateMutation` |
| Kişi yöneticisi / müşteri profilleri | `BizContactManagerProfiles`, `ContactManagerAccessState`, `WACustomerProfiles`, `UpsertWACustomerProfiles`, `DeleteWACustomerProfile` |
| Faturalama / abonelik (Meta-faturalı katmanlar) | `FetchSubscriptionState`, `FetchSubscriptionStateV2`, `WaSmbMetaOneTierPaymentPrefetchTargetQuery`, `AcceptBizAiPaymentTerms` |
| Sohbet-geçmişi dışa aktarma / 3P (GDrive) entegrasyonu | `FetchChatHistoryExportStatus`, `GDriveGetFiles`, `UploadHistoricalMetadata`, `Disconnect3PPartners` |
| Bağlı IG/FB hesabı | `SetIGDisplayContactInfoMutation`, `WAFBPageProfileImportGet`, `WhatsAppBusinessLinkedAccountsQuery` |
| QE/feature-flag altyapısı (business-tarafı) | `CheckQEBool`, `WaFetchQEBool`, `WaFetchQEString`, `WhatsAppGraphQLCheckQE` |

Tam 215-isimlik liste, yukarıda alıntılanan iki uygulamanın asset dosyalarından yeniden üretilebilir; burada kelimesi kelimesine yeniden üretilmemiştir. `www`/`facebook-schema` doc_id **değerleri** (sadece operasyon adları değil) diff'lenmemiştir — paylaşımlı bir operasyon adı, prensip olarak iki uygulama arasında hâlâ farklı bir doc_id taşıyabilir; kontrol edilmemiştir.

---

## 6. İzin diff'i — found

Her uygulamanın manifest envanterinden:

| | Business'a özel | Consumer'a özel |
|---|---|---|
| İzin | `com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` | `android.permission.RECEIVE_SMS` |

Her iki uygulama ek olarak kendi paket adları altında (`com.whatsapp.w4b.*` vs `com.whatsapp.*`) kendi-paket self-broadcast/maps izinleri talep ediyor — bunlar birbirinin paket-adı-değiştirilmiş eşdeğerleridir, işlevsel olarak yeni değildir ve yukarıda sayılmamıştır.

Business, SMS-alma talep etmiyor. **Inferred**, koddan doğrulanmamış: Business hesaplarının OTP için cihaz-üzerinde SMS otomatik-okumaya güvenmek yerine daha çok bir Cloud/Business API yolundan kayıt olmasıyla tutarlı — ama bu mantık bu geçişte hiçbir kayıt-akışı koduna karşı doğrulanmamıştır.

---

## 7. Baileys / velowa notu

Bu raporun yüzeyinin neredeyse hiçbiri sıradan bir WhatsApp Web istemcisinden (velowa veya herhangi bir Noise/multi-device-protokolü uygulaması) erişilebilir değildir:

- `mex`/`wamo` katalogları consumer'ınkiyle **özdeştir** — orada Business'a özgü eklenecek hiçbir şey yok; herhangi bir WA Web istemcisi zaten aynı doc_id'lere sahiptir.
- 215 `facebook-schema` operasyonu (§5.3) gerçek Business-özgü GraphQL yüzeyidir, ama bunlar Business-**uygulama**-UI-güdümlü akışlardır (katalog düzenleme, reklam oluşturma, coaching/MAIBA, coexistence onboarding'i, agent auth), Business uygulamasının kendi hesap durumunun ardına ve birkaç kümede tamamen WhatsApp Business API/Cloud API sunucu tarafının ardına gated edilmiştir (coexistence, faturalama, reklam hesapları). Sıradan multi-device protokolünü konuşan bir WA Web istemcisinin bunların çoğuna ulaşacak bir yolu yoktur — bunlar hiç wire-protokolü özellikleri değildir, Business uygulamasının kendi UI'sinin Meta'nın business-platform backend'ine karşı yaptığı REST/GraphQL çağrılarıdır.
- Reklam-oluşturma React Native yüzeyi (§3) sadece Android-uygulama-UI'sidir (`libreactnative.so` tarafından render edilen gömülü JS ekranları); bununla ilgili hiçbir şey sohbet wire protokolüne binmez.
- Herhangi bir multi-device-protokolü ilgisi olan tek alan coexistence'tır (`coexistence`/`connectedaccounts`/`linkedaccounts`), cihaz/oturum temsili `WA_MANAGED_ACCOUNT.md` §9.3 ve `WA_LINKED_DEVICE_PAIRING.md`'deki (hesap tipi `HOSTED`, cihaz id'si 99, `platformType` 23/25-27) mevcut belgelemede kapsanmıştır — bu kısım, sadece-istemci-tarafı bir görünümün gidebileceği kadar ileridedir zaten.

Sonuç: bu rapor, Business APK'sının *ne içerdiğini* anlamak için kullanışlıdır, velowa için yeni bir wire-protokolü yüzeyi kaynağı olarak değil.

---

## 8. Bu rapor NEYİ doğrulamadı

| Boşluk | Neden | İzlenecek adım |
|---|---|---|
| İki uygulama arasında proto/wire-schema diff'i | `unknown`, inferred-same değil. Reconstruct pipeline'ının proto aşaması her iki build için de çalışmadı (her iki tarafta da `protoc_ok=False`); bu sürüm-yenileme geçişinde başka yerde kullanılan daha derin proto çıkarımı (1089 mesaj, `protoc` exit 0) sadece consumer'ın önceden var olan jadx decompile'ına karşı çalıştı — bu çalışma alanında `com.whatsapp.w4b` için eşdeğer bir decompile mevcut değil. Bir tane üretmek, bu oturumun sert güvenlik kuralı tarafından yasaklanan (daha önce analiz makinesini çökertti) tam-APK bir jadx çalışması gerektirir. Kanıtın yokluğu, yokluğun kanıtı değildir. | Sadece mesaj/proto sınıflarına kapsamlı tek-sınıf veya tek-DEX jadx çıkarımı (tam-APK decompile değil) |
| Hangi özellik(ler)in Business'a-özel React Native stack'i üzerinden render edildiği | Sadece paket/kütüphane-adı korelasyonu (`adscreation/lwi/react/*` en güçlü isimlendirme eşleşmesi, ama doğrulanmamış) | `com/whatsapp/adscreation/lwi/react/*` sınıflarının kapsamlı decompile'ı |
| Consumer-sadece paket kümesi (282 yol) | Bu geçişte tematik olarak kümelenmedi — görevin Business'a-özel yüzey çerçevelemesi göz önüne alındığında daha düşük öncelikli | 282-yol diff'i üzerinde özel bir geçiş |
| `www`/`facebook-schema` doc_id **değerleri** | Sadece operasyon **adları** diff'lendi; paylaşımlı bir ad, uygulama başına farklı bir doc_id taşıyabilir | Her iki asset JSON'ının değer-seviyesi diff'i |
| Tam 215-operasyonluk `facebook-schema` listesi / değişkenler / yanıt şekilleri | Kümeleme sadece isim anahtar sözcüğüne göredir; hiçbir çağrı-noktası veya yanıt-alanı geri kazanımı denenmedi | Diğer raporların MEX operasyonları için yapıldığı gibi küme-başına hedefli çağrı-noktası izleme |

---

## 9. Ayırt edilmesi gereken noktalar

| A | B |
|---|---|
| WhatsApp Business **uygulaması** (`com.whatsapp.w4b`) — kendi paket kümesine sahip ayrı bir APK, bu rapor | WhatsApp Business **API / Cloud API** — bir işletme numarasının mesajlarının sunucu tarafı barındırması/relay'i; özel bir istemci APK'sı yok, herhangi bir istemcide doğrulanmış-ad sertifika alanları üzerinden sinyallenir (`WA_MANAGED_ACCOUNT.md` §9) |
| Business uygulamasının `coexistence`/`connectedaccounts`/`linkedaccounts` paketleri — uygulamanın bir Cloud API sağlayıcısına köprülenmesi için kendi UI'si | Bir işletme numarası uygulamayı ve API'yi aynı anda çalıştırdığında bir **eş**in istemcisi (consumer veya Business) tarafından görülen `business_state_id` coexistence banner'ları (`WA_MANAGED_ACCOUNT.md` §9.2) |
| Managed Account (`ManagedAccount*`, PAA/PMA/PMTA) — ebeveyn denetimi altındaki bir reşit olmayanın kendi **consumer** hesabı | Business uygulaması — bir işletmenin hesabı, tamamen ilgisiz bir kavram, kod/schema örtüşmesi yok |
| `mex`/`wamo` doc_id katalogları — her iki uygulamada byte-özdeş operasyon-adı kümeleri | `facebook-schema` doc_id kataloğu — 215 operasyon sadece Business'ta var; Business-özgü GraphQL yüzeyi gerçekte burada yaşar |
| Katalog/profil/etiket **görüntüleme** — consumer'da da bulunan paylaşımlı paket kökleri (böylece bir consumer kullanıcısı bir işletmenin kataloğuna göz atabilir) | Katalog/profil/etiket **düzenleme** — Business'a özel paket kökleri (sadece işletmenin kendisinin erişebildiği yazma tarafı) |

---

## 10. Özet

Baştan beklenen şekli doğrular — katalog, business-profil/doğrulama, etiketler, hızlı-yanıtlar/karşılama/otomatik-yanıt mesajlaşması, temsilci/multi-device auth kümesi Business-sadece kodda, her birinin görüntüleme/gösterim yarısı consumer ile paylaşımlı — ve beklenmeyen iki bulgu ekler:

1. **Gerçek Business-özgü GraphQL yüzeyi `facebook-schema`'da yaşar** (215 Business-sadece operasyon: AI-coach/bilgi-tabanı, MAIBA, lead-gen, auth-agent, coexistence, CTWA reklamları, katalog yazma operasyonları, pazarlama yayını, faturalama), iki uygulama arasında byte-özdeş operasyon-adı kümeleri olan ana `mex`/`wamo` katalogları değil.
2. **Business, tamamen consumer'da bulunmayan, tam bir React Native + Fresco stack'i paketler** (`com.facebook.react.*`, `libreactnative.so`, `libimagepipeline.so`, `libwacomponents.so`), hem paket hem native-kütüphane seviyesinde — en olası reklam-oluşturma ekranlarının arkasında, ama kesin özellik sınırı kapsamlı bir decompile olmadan doğrulanmamıştır.

Proto/wire-schema diff'i bu geçişte yapılamadı (§8) ve unknown olarak kaydedildi, inferred-same değil.
