<!-- src-sha1: 3f456309f1ce11a70a08dd912d84e40193c760ad -->
# WhatsApp Yönetilen Hesap — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** istemci tarafında görünen "managed account" ebeveyn denetimi sistemi (sponsor/dependent bağlama, roller, yaş deneyimi, PIN, gizlilik ayarları, bağlantıyı kaldırma, w:mex işlemleri, yerel depolama, feature flag'ler); bir Business Solution Provider tarafından Cloud API üzerinden işletilen işletme numaraları için ayrı, ilgisiz sinyal kümesi (doğrulanmış ad sertifikası issuer'ı, host-storage/actual-actors alanları, coexistence arayüzü, hosted multi-device hesap türü); ikisinin birbirinden nasıl ayırt edildiği

---

## 1. Bu istemcide "managed" ne anlama gelir

2.26.41.6'da dışarıdan bakan bir okurun "managed account" diyeceği iki ilgisiz sistem kullanılır. Hiçbir kod, proto veya w:mex schema'sı paylaşmazlar. Tüm ifadeler çözülmüş (decompiled) APK'nın statik analizine dayanır; ağ üzerinde hiçbir şey yakalanmadı. Katman: **found** = kodda veya asset'lerde okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi.

| Sistem | Koddaki iç ad(lar) | "Managed" olan ne | Nerede | Bölüm |
|---|---|---|---|---|
| Ebeveyn denetimi | `com.whatsapp.managedaccount.*`, `com.whatsapp.pma.*`, `com.whatsapp.pmta.*`; iç kod adları **PAA**, **PMA**, **PMTA** (paket/sınıf/pref adlarında bulundu, string'lerde hiçbir zaman açılmadı) | reşit olmayanın ("dependent") kendi WhatsApp hesabı, bir ebeveyn/vasi ("sponsor") hesabı tarafından denetlenir | `w:mex`, yerel SQLite/SharedPrefs | 2-8 |
| İşletme numarasının bir sağlayıcıya devredilmesi | istemcide hiçbir yerde "BSP" veya "tech provider" string'i yok; arayüz bunu "a secure service from Meta" veya "other companies" olarak adlandırıyor | bir **işletmenin** WhatsApp numarası; mesajları işletmenin kendi cihazı yerine Meta'nın bulut altyapısı ve/veya üçüncü taraf bir sağlayıcı tarafından barındırılır/işlenir | doğrulanmış ad sertifikası (`w:biz`), multi-device "barındırılan" hesap türü | 9 |

String kaynakları `str2fc9`/`str3139` ("Managed account"), `str30ae`, `str3109`, `str439d`/`str439f` ve ait oldukları ayarlar ekranı **tamamen** ebeveyn sistemine aittir (bölüm 2). Bir BSP tarafından işletilen bir işletme için istemcide hiçbir yerde "Managed account" etiketi yoktur; bu durum yalnızca sertifika alanları ve sohbet/arama banner'ları üzerinden sinyallenir (bölüm 9). Terimi kullanmadan önce yapılması gereken temel düzeltme şu: bir *işletme* numarası hakkında "managed account" diyen bir reverse-engineering notu veya ticket, bölüm 9'dan bahsediyordur, kodda `ManagedAccount*` adını taşıyan herhangi bir şeyden değil.

---

## 2. Ebeveyn denetimi: roller ve hesap ilişkisi

### 2.1 Roller

`EnumC08540Ng` (found), her sabit için bir debug etiketiyle:

| Rol | Debug etiketi | Kim |
|---|---|---|
| `NONE` | "None" | denetim ilişkisi yok |
| `DEPENDENT` | "Dependent" | reşit olmayanın kendi hesabı |
| `SPONSOR` | "Sponsor" | ebeveyn/vasi hesabı |
| `SPONSOR_ADMIN` | "Sponsor Admin" | yükseltilmiş haklara sahip bir sponsor (tam ek haklar izlenmedi) |

Mevcut cihazın rolü, yerel durumdan `SharedPreferencesOnSharedPreferenceChangeListenerC08490Nb.A04()` tarafından okunur ve `C08530Nf` tarafından cache'lenir ("ManagedAccountStartupPreferences", adı log tag'i `ManagedAccountStartupPreferences/...`'ten inferred).

### 2.2 İlişki hesap-hesap'tır, cihaz-cihaz değil

Dependent'ın **kendi telefon numarası ve kendi tam WhatsApp kaydı** vardır (kendi birincil cihazı, varsa kendi multi-device companion'ları). Sponsor da aynı şekilde normal, bağımsız olarak kayıtlı bir hesaptır. İkisini birbirine bağlayan şey, yerel olarak şu şekilde yansıtılan sunucu taraflı bir kayıttır:

```
ManagedAccountConnection(
  connectionLid,      // C14080dr — the dependent's LID, found
  role,                // EnumC08540Ng, found
  linkTs,              // long, link creation time, found
  connectionPnJid,     // PhoneUserJid — the dependent's phone-number JID, found
  graduationState,      // C4DV, section 2.3
  ageExperience)        // EnumC96934Gf, section 2.3
```

(`AnonymousClass586`, found; alanlar kendi `toString`'i tarafından doğrulandı.) Bu paket içinde hiçbir yerde pairing QR, ADV imzası veya companion key exchange yoktur — `WA_LINKED_DEVICE_PAIRING.md` bölüm 5'teki gerçek companion-device protokolüyle karşılaştırın, bu ilgisizdir. Onboarding giriş noktası, bir scan tabanlı akış değil, `ManagedAccountSponsorOnboardingViewModel` (paket `managedaccount.deeplink`, found) tarafından işlenen bir deep link'tir.

### 2.3 Yaş deneyimi ve graduation

`EnumC96934Gf` (found): `UNKNOWN`, `U13`, `U16_BR`, `U18_BR`, `U18`, `STANDARD` (Brezilya'nın kendi yaş bantları var). Bu enum üzerindeki `A00()`, `U16_BR`, `U18_BR`, `U18` için true döner — kodun "yaş sınırını aşmak üzere" olarak ele aldığı durumlar.

`C4DV` (graduation state, found): `PRE_GRADUATION`, `GRADUATION`, `PRE_GRADUATION_IMMINENT`, `UNKNOWN`. `ManagedAccountGraduationManager` ve onun `triggerTeenGraduationEagerly` yolu (found), bir dependent'ı bir yaş eşiğine yaklaştıkça/aştıkça denetimden çıkarır; `ManagedAccountPmtaSponsorGraduationNuxActivity` ve `ManagedAccountSponsorGraduationNuxActivity`, bu geçiş için sponsor tarafı NUX'u gösterir.

`ManagedAccountLinkingRepository.A00` (found), linking çağrısından gelen bir HTTP 409 conflict üzerine age experience'ı yeniden fetch eder; yani sunucu, saklanan age experience bayat olduğu için linking'i reddedebilir ve istemci yeniden denemeden önce `WaAgeExperienceRepository`'yi yeniden query'lemelidir.

---

## 3. Linking akışı ve w:mex işlemleri

### 3.1 İşlem kataloğu

Aşağıdaki dokuz işlem adı ve `doc_id` değerinin tamamı bu derlemede `assets/whatsapp-android-mex_client_persist_ids.json`'dan doğrudan okundu (found) — üçüncü taraf bir istemciden inferred değil. Dokuzunun hepsi için schema `whatsapp-android-mex`'tir (asset key: `whatsapp_mex`).

| İşlem | doc_id | Call site bulundu | Değişkenler (bu derleme) |
|---|---|---|---|
| `ManagedAccountInitiateLinkingQuery` | `26671873552498548` | `MexManagedAccountInitiateLinkingApi.A00` | `input:{"dummy": null}` — **`phone_number` gönderilmiyor**; bu çağrının dependent'ın numarasını taşıdığı yönündeki önceki bir varsayım bu call site için geçerli değil |
| `ManagedAccountQuery` | `27232244463035262` | `ManagedAccountStateSynchronizer.A01` | `input:{"unused": null}` — **`jid` yok**; query bu call site'ta session-bound'dur, JID ile parametrize edilmez |
| `ManagedAccountValidateLinkingQuery` | `35449808311284430` | referenced (assets'te ad eşleşmesi); değişkenler bu derlemede bir call site'a kadar izlenmedi | unknown |
| `ManagedAccountAcceptLinkingMutation` | `26708926155457677` | referenced; değişkenler izlenmedi | unknown |
| `ManagedAccountCompleteLinkingMutation` | `26866501363013203` | referenced; değişkenler izlenmedi | unknown |
| `ManagedAccountRevokeLinkingMutation` | `27435058196100677` | referenced; değişkenler izlenmedi | unknown |
| `ManagedAccountSyncActivities` | `26594352680227840` | referenced; değişkenler izlenmedi | unknown |
| `ManagedAccountUpdatePinMutation` | `27653949584193082` | referenced; değişkenler izlenmedi | unknown |
| `ManagedAccountGetSponsorAgeVerificationInfoQuery` | `26433623289634522` | referenced; değişkenler izlenmedi | unknown |

Dokuzunun hiçbiri için generic success/error wrapper'larının ötesinde response body okunmadı; `ManagedAccountInitiateLinkingQuery`'nin success sonucu (`C135065o7`, `toString()` literally `"PAA Initiate Linking Success"`, found) iki string ve alan adları çözülmemiş bir int taşır — büyük olasılıkla bir linking token/deep-link URL'si ve bir expiry, ama bu inferred'dır, adlandırılmış bir alandan okunmadı.

Ayrı, mex olmayan bir yol vardır: `C14E.java` (`PaaAcceptLinkingIBHandler`), bir `sponsor_jid` attribute'u taşıyan gelen bir stanza/notification'ı parse eder (found) — bu, `AcceptLinkingMutation`'ın kendi request'i değil, arayüzü tetikleyen bir server push'tur.

### 3.2 Teslim hatasında retry

`MexManagedAccountInitiateLinkingApi.A01`, initiate çağrısını hata kodu **471** ("delivery failure") üzerine caller tarafından sağlanan bir sayıya kadar retry eder, `MexManagedAccountInitiateLinkingApi/requestSponsorLinkingMaterial delivery failure, retrying` logunu yazar (found).

---

## 4. Device/session modeli

Sponsor ve dependent arasında **companion tarzı bir device link yoktur**, ve her iki hesap ile herhangi bir WhatsApp tarafından işletilen altyapı arasında da yoktur. Her taraf, sıradan, bağımsız olarak kayıtlı bir WhatsApp hesabıdır (kendi telefon numarası, kendi birincil cihazı, `WA_LINKED_DEVICE_PAIRING.md`'de açıklanan normal multi-device sistemi altında kendi isteğe bağlı linked device'ları). Denetim ilişkisi, dependent'ın LID'i ve telefon-numarası JID'i ile keylenen (bölüm 2.2), her iki tarafa `w:mex` üzerinden senkronize edilen sunucu taraflı bir kayıttır; yeni bir session, pairing veya ADV identity değildir.

Bu, bölüm 9'daki BSP/Cloud-API durumundan yapısal bir farktır; orada işletme numarasının "cihazı" hiç bir telefon değildir — bunun mevcut multi-device modelinde nasıl temsil edildiği için bölüm 9.3'e bakın.

---

## 5. Ayarlar ve izinler

### 5.1 Dependent tarafı gizlilik ekranı

`DependentAccountPrivacyActivity` (found), ayarları `C9SE` enum'u üzerinden üç bölüme gruplar:

| Bölüm | `C9SE` sabiti | İçerik |
|---|---|---|
| Görünürlük | `VISIBILITY` (0) | dependent'ın profil bilgisini kimin görebileceği |
| İletişim | `CONTACT` (1) | dependent'a kimin ulaşabileceği |
| Sponsor kontrolü | `SPONSOR_CONTROL` (2) | dependent'ın değil, sponsor'ın kontrol ettiği ayarlar |

Ekran, string `str2fc8` üzerinden "parental controls"a çıkar: *"Your account is managed by your parent or guardian. They can make changes in parental controls."* Böyle bir kontrol için yerel bir pref gate'i vardır: `privacy_dependent_account_messages` (int, default `1`), `C08520Ne.A06()` tarafından okunur ve yalnızca hesap bir sponsor olduğunda consulted edilir (found) — yani dependent'a kimin mesaj atabileceği, dependent'ın ayarladığı bir değer değil, **sponsor'ın** app state'inin gate'lediği bir şeydir.

### 5.2 Sponsor tarafı kontroller

`SponsorControlsHubActivity` (found), dependent'ları listeleyen (fragment/log tag `"sponsor-controls-dependents"`) sponsor'ın hub'ıdır, her dependent için bir contact-photo adapter'ı vardır. `SponsorControlsDependentInfoActivity`, bir dependent'ın detayını açar. `ManageNotificationsActivity` / `ManageNotificationsFragment` ve `ActivityAlertsFragment` / `ManagedAccountDependentActivityAlertHandler`, **activity alert**'leri yapılandırır ve iletir — sponsor'a dependent'ın app activity'si hakkında notification'lar (`ManagedAccountSyncActivities`, bölüm 3.1, veri kaynağıdır, `ManagedAccountAlertInfoActivity`'de flag **31562** ile gate'lenir, found).

### 5.3 PIN

`SponsorPinSetupFragment`, `SponsorPinConfirmFragment`, `ManagedAccountChangePinActivity`/`ManagedAccountChangePinFragment`/`ManagedAccountConfirmChangePinFragment` (found, sınıf varlığıyla), sponsor tarafından ayarlanan PIN oluşturma ve değiştirmeyi implement eder; mutation `ManagedAccountUpdatePinMutation`'dır (bölüm 3.1; tam `old_pin`/`new_pin` alan adları bu derlemede doğrulanmadı — unknown). Dependent tarafı bir sync, özellikle eksik bir PIN için başarısız olabilir: `ManagedAccountStateSynchronizer`, `"ManagedAccountStateSynchronizer/fetchAndSync missing sponsor PIN for child user"` logunu yazar ve server/response tipi `C135095oA` olduğunda bir error sonucu döner (found) — dependent'ın state sync'i sponsor'ın PIN'inin ayarlanmış olmasına bağlıdır.

### 5.4 Unlink

`ManagedAccountUnlinkAccountSettingsActivity` (found), fragment argument'larında taşınan flag'lere bağlı olarak birkaç onay metninden birini gösterir: `is_pmta` (ayrı bir "PMTA" alt varyantı), `is_teen_dependent`, ve dependent'ın bir push name'inin olup olmadığı — string'ler `str49cb`…`str49d3`, örn. *"Your account will no longer be managed by %1$s"* / *"...by your parent"*. `ManagedAccountRevokeLinkingMutation` (bölüm 3.1), bu aksiyonu desteklediği inferred edilen wire işlemidir; activity'nin kendisinin bunu doğrudan çağırdığı bu geçişte izlenmedi.

### 5.5 Reauthentication gate'i

`ManagedAccountAuthInterstitialActivity`, `PmaAuthInterstitialFragment`'i host eder (paket `com.whatsapp.pma.product.dependent.fragments`, found) ve bir `extra_auth_entry_point` string'i ile başlatılır — belirli bir entry point'ten managed-account ekranlarına girişi gate'leyen bir re-authentication adımı. Tam auth mekanizması (device PIN, biyometrik, hesap parolası) izlenmedi.

### 5.6 Debug surface'leri

`ManagedAccountDebugConnectionActivity` ve `ManagedAccountDebugPinAuthActivity` bu derlemede mevcuttur (found). Bu geçişte, bunların release UI'dan mı yoksa yalnızca internal/debug bir build flag'inden mi erişilebilir olduğu belirlenemedi (inferred: sadece debug, adlandırma convention'ı ve production ekranlarından keşfedilen hiçbir launch path'in olmaması nedeniyle).

---

## 6. Depolama

| Depo | Key'ler / kolonlar | İçerik |
|---|---|---|
| Yerel ilişki kaydı | `connectionLid`, `role`, `linkTs`, `connectionPnJid`, `graduationState`, `ageExperience` (bölüm 2.2) | her sponsor↔dependent bağlantısı için bir satır |
| SharedPrefs | `paa_graduation_nux_pending`, `paa_sponsor_blocked`, `paa_nux_education_banner_dismissed`, `paa_nux_education_banner_start_timestamp`, `paa_review_privacy_settings_banner_dismissed_dependent_<lid>`, `privacy_dependent_account_messages` | NUX/banner dismissal durumu, sponsor-blocked flag'i, onaylanmış tek dependent-messaging gate'i |

Tüm key'ler `C08530Nf`, `ManagedAccountBannerManager`, `C08520Ne` içinde verbatim bulundu.

---

## 7. UI indicator string'leri

| String id | Metin | Nerede kullanılıyor |
|---|---|---|
| `str2629` | "Create a parent-managed account" | onboarding girişi |
| `str2fc9` / `str3139` | "Managed account" | badge/etiket |
| `str30ae` | "Managed accounts can't see this message. Learn why" | kısıtlanmış içerik |
| `str3109` | "This is a managed account. Learn more" | chat/profil bildirimi |
| `str3751` / `str3752` / `str3754` | ineligibility message'ları ("isn't eligible for a parent-managed account", "Couldn't create parent-managed account") | onboarding hatası |
| `str439d` / `str439f` | "Settings for managed accounts" / "View activity and choose settings for managed accounts" | settings giriş noktası |
| `str2fc8` | "Your account is managed by your parent or guardian..." | `DependentAccountPrivacyActivity` |
| `str49cb`-`str49d3` | unlink onay varyantları | `ManagedAccountUnlinkAccountSettingsActivity` |

`ManagedAccountNotAvailableActivity` ve `ManagedAccountAgeUnknownActivity` (sınıf adıyla found), iki durumu daha destekler — feature'ın sunulmaması ve hesabın yaşının belirlenememesi — tam copy çözülmedi.

---

## 8. Feature flag'ler

| ID | Nerede | Kontrol ettiği |
|---|---|---|
| **30174** | `C08520Ne.A02`, `ManagedAccountSponsorUpsellActivity` | sponsor-upsell uygunluğu |
| **31562** | `ManagedAccountAlertInfoActivity` | activity-alerts feature gate'i |
| **34268** | `C08520Ne.A01` | ek bir izin kontrolü (rol, gate'in kendisinin ötesinde çözülmedi) |
| **16763** | `C08520Ne.A04` | çözülmemiş boolean gate |
| **33355** | `C08520Ne.A05` | çözülmemiş boolean gate, dependent'a veya ikincil bir arayüze koşullu |

---

## 9. Bir sağlayıcıya devredilen işletme numaraları (Cloud API / BSP)

Bu, gerçekte "bir sağlayıcı tarafından on-behalf-of işletilen bir işletme hesabı"na karşılık gelen sistemdir. Bölüm 2-8 ile hiçbir sınıf, proto veya w:mex schema'sı paylaşmaz. Bu derlemede kullanıcıya "BSP," "tech provider," "Business Solution Provider," "on-premises API" veya "Cloud API" diyen hiçbir string yoktur; sinyal yapısaldır.

### 9.1 Verified-name sertifikası: issuer prefix'i ve `PrivacyMode`

İstemci, her işletme JID'i için kolonlarla (found, `AbstractC218419al`) yerel bir verified-name sertifika kaydı saklar: `verified_name`, `industry`, `city`, `country`, `verified_level`, `cert_blob`, `identity_unconfirmed_since`, `host_storage`, `actual_actors`, `privacy_mode_ts`. Bu son üç alan, bir `w:biz` stanza'sının `<biz host_storage="" actual_actors="" privacy_mode_ts=""/>` tarzı bir child'ından (found, birden çok call site, örn. `O0F.java`, `C18670m9.java`, `AbstractC24816AmW.java`) `AnonymousClass118`'e ("`PrivacyMode`" kendi `toString()`'ine göre) parse edilir; bunun iki integer alanı şunlardır:

| Alan | Kodda görülen değerler | Anlam |
|---|---|---|
| `hostStorage` | 0 (default/unset), 1, 2 | işletmenin mesajlarını hangi altyapının sakladığı/relay ettiği; public WhatsApp Business Platform terimleri on-premises (self-hosted) vs. Meta-hosted (Cloud API) vs. üçüncü, dual/transitional bir duruma **inferred** eşleme — istemcide bu üç değer için adlandırılmış sabit yoktur |
| `actualActors` | 0 (default/unset), 1, 2 | hesabı günlük olarak kimin fiilen işlettiği; self-operated vs. bir sağlayıcı tarafından işletilme'ye **inferred** eşleme — bu istemcide de yine adlandırılmış sabit yok |

Aynı sertifika wrapper'ı üzerinde (`AnonymousClass119.A02()`/`A03()`) bağımsız olarak found edilen ikinci bir sinyal, sertifikanın **issuer string'ini** (alan `A07`) okur ve onu prefix'e göre sınıflandırır (found, exact code):

```java
public boolean A01() { return this.A01 == 2; }        // hostStorage == 2
public boolean A02() { return this.A07 != null && this.A07.startsWith("ent:"); }
public boolean A03() { return this.A07 != null && this.A07.startsWith("smb:"); }
```

`"ent:"` ve `"smb:"`, bu istemcinin ayırt ettiği iki issuer prefix'idir (found, literal string'ler). `smb:`, normal, self-operated WhatsApp Business uygulaması için verilmiş bir sertifikayla eşleşir; `ent:`, bir enterprise/API-entegre yol için verilmiş bir sertifikayla eşleşir — bu, "self-managed business account" vs. "BSP/Cloud-API-managed business account"ın en yakın first-party, kod seviyesindeki karşılığıdır (prefix'lerin bu iki gerçek-dünya kategorisine eşlenmesi, prefix'lerin kendisinden ve bunların `AbstractC198638cc.A00` içinde nasıl tüketildiğinden **inferred**'dır, istemci içi herhangi bir dokümantasyon string'inden değil).

`AbstractC198638cc.A00`, issuer kontrolünü ve ayrı bir boolean'ı (`A09`, anlamı çözülmedi — muhtemelen "certificate missing/revoked", bölüm 9.2'deki kullanıcıya görünen "no longer an official business account" copy'siyle tutarlı) 4 değerli bir "client" koduna katlar (found):

```java
public static final int A00(AnonymousClass119 c) {
    if (c != null) {
        if (c.A09) return 4;
        if (c.A03()) return 2;   // smb: issuer
        if (c.A02()) return 3;   // ent: issuer
    }
    return 1;                    // default / no certificate
}
```

### 9.2 Coexistence banner'ları ve `business_state_id`

`C198628cb` ("`BusinessState`" kendi `toString()`'ine göre), sertifikanın `PrivacyMode`'unu (9.1), 4 değerli "client" kodunu ve bir `isVerified` boolean'ını, arayüzün `business_state_id` dediği tek bir düzleştirilmiş integer'a birleştirir (found, `EncryptionChangeDialogFragment` içinde `c198628cb.A02()`'den set edilir ve `PrivacyInfoBottomSheet`/`ContactInfoActivity`'de aynı şekilde okunur). Mapping fonksiyonu, 18 açık `(client, actualActors, hostStorage, flag)` tuple'ını **0-17** id'lerine pattern-match eder; tam tablo yeniden oluşturulamadı (JADX bu spesifik method için bir region-overflow hatası bildiriyor, ve birkaç branch decompiler tarafından birleştirilmiş), ancak aşağıdaki doğrudan koddan tespit edilmiştir:

- id **15**, "client" kodu diğer alanlardan bağımsız olarak 4'e (certificate missing/revoked) eşit olduğunda her zaman ulaşılır.
- id'ler **5, 6, 9, 10**, bir side-gate method'u `A05()` (chat üzerinde ilgisiz bir block/mute tarzı kontrol) true olduğunda erişilebilen tek id'lerdir, ve `hostStorage == 2` olduğunda normal yol üzerinden de erişilebilirler — bunlar tutarlı bir şekilde sade *"This business uses a secure service from Meta to manage this chat/call"* string'lerini tetikler (`str080d`/`str080f`/`str0c9c`/`str0f5a`, found, `C23324A5w`/`ContactInfoActivity`'de resource-id ile doğrulanmış call site'lar).
- id'ler **16** ve **17**, kalan durumlardır (ne bilinen bir tuple ne de id 15) ve "multiple tools" / "no longer an official business account" string ailesini tetikler (`str38ef`-`str38fb`, `str08b3`-`str08c7`): *"This business has chosen to use multiple tools to chat with its customers... Chats between only you and this business are managed by a secure service from Meta... this business is using the WhatsApp Business app"* — yani numaranın aynı anda hem bir cihazdaki Business uygulaması hem de bir API-hosted yol üzerinden erişilebilir olduğu **coexistence** durumu; flag'ler **12729**, **18047**, **23933**, **7131**, **29343** ile gate'lenir (found, `PrivacyInfoBottomSheet`/`ContactInfoActivity`'de, her biri aynı durum için eski ve yeni bir string çiftini seçer).

İlgisiz multi-device akışındaki `remove-companion-device` IQ sonucu, bir `coex_token` child'ı taşıyabilir (`WA_LINKED_DEVICE_PAIRING.md` §7.1) — aynı "coexistence" kavramı, tüketici o taraftan da izlenmedi.

### 9.3 Sağlayıcı-hosted bir numara için device/session modeli

Tamamen Meta tarafından hosted bir işletme numarası (hiç fiziksel cihaz olmayan Cloud API durumu), yeni bir sistem içinde değil, **mevcut** multi-device sistemi içinde temsil edilir:

- account type `HOSTED` (`EnumC32116E1o`, değer 1) ve device id **99**, bu durum için ayrılmıştır (`WA_LINKED_DEVICE_PAIRING.md` §5.1, §9.2).
- primary'nin kendi linked device'ları için sakladığı `companion-props.platformType` enumeration'ı, **23 = `CLOUD_API`** değerini içerir (`WA_LINKED_DEVICE_PAIRING.md` §6.2), **27 = `BUSINESS_BACK_OFFICE`** ve **25/26 = `WAIL`/`WASS`** ile birlikte — tümü sıradan telefon/desktop/web'lerle aynı enum içinde yer alan business-infrastructure platform tipleri.
- bu rapordaki consumer build, primary tarafından hosted bir cihazı pair etmeyi aktif olarak **reddeder** (yerel hata kodu **-10**, `WA_LINKED_DEVICE_PAIRING.md` §3.2) — hosted/Cloud-API provisioning, bu istemcinin başlattığı bir şey değildir; istemci yalnızca bunu zaten sahip olan hesaplarda ortaya çıkan account type ve platform marker'larını gözlemler.

BSP/Cloud-API ilişkisinin kendisi için bu APK'da hiçbir yerde pairing, ADV imzası veya companion-key akışı bulunamadı; account security'nin canonical-user/password mekanizması (`WA_ACCOUNT_SECURITY.md`) ve multi-device identity mekanizması, bir BSP'nin bir numarayı işletmeye nasıl başladığıyla ilgisizdir — bu provisioning tamamen sunucu tarafında / Meta'nın business platformunda gerçekleşir ve yukarıdaki marker'ların ötesinde bu istemcide hiçbir iz bırakmaz.

### 9.4 Telemetri

`wam_ts_navigation` logging event'i (`C1EO`, found), loglanan her navigation için üç bağımsız business-context boolean'ı taşır: `is_cloudapi`, `is_onpremises`, `is_smb`, ayrıca `is_canonical_ent_present` ve `is_meta_ai_thread`. `ChatDescription` (`com.whatsapp.gapenforcement.dto`) ayrıca `isEnterpriseBusiness`'i taşır. Her iki sınıf da, bölüm 9.1/9.2'nin zaten açıkladığının ötesinde bu boolean'ların nasıl hesaplandığını açığa çıkarmaz; bunlar yalnızca raporlama amaçlıdır ve okunan dosyalarda kullanıcıya görünen hiçbir davranışı gate'lemez.

---

## 10. Temel ayrımlar

| A | B |
|---|---|
| "Managed account" (`ManagedAccount*`, PAA/PMA/PMTA) — bir ebeveyn tarafından denetlenen **reşit olmayanın kendi hesabı** | Cloud API üzerinden bir sağlayıcı tarafından **işletilen** bir işletme numarası — bu durum için hiçbir yerde "managed account" string'i yok |
| Sponsor/dependent link: iki bağımsız, normal şekilde kayıtlı WhatsApp hesabı, device pairing yok | hosted işletme numarası: bir hesap, `accountType=HOSTED`, device id 99, hiç companion device yok |
| `w:mex` `ManagedAccount*` işlemleri, schema `whatsapp-android-mex` (bölüm 3.1) | `w:biz` üzerinden verified-name sertifika alanları (`host_storage`, `actual_actors`) — farklı stanza, farklı schema |
| `business_state_id` coexistence banner'ları (aynı anda self-managed Business uygulaması **ve** API-hosted) | tamamen self-managed bir işletme (kendi cihazındaki normal WhatsApp Business uygulaması, issuer prefix `smb:`) |
| `is_smb` telemetri flag'i (Business uygulamasını kullanan small/medium business) | `is_cloudapi` / `is_onpremises` telemetri flag'leri (API tarafı hosting) |
| `ManagedAccountRevokeLinkingMutation` (ebeveyn denetimini sonlandırır) | `remove-companion-device` (ilgisiz: bir linked device'ı kaldırır; bkz. `WA_LINKED_DEVICE_PAIRING.md` §7) |

---

## 11. Tam akışlar

### 11.1 Ebeveyn denetimi: bir dependent'ı linklemek

```
[Sponsor]                                  [Server]                         [Dependent]
   │ deep link / in-app entry                  │                                 │
   ▼                                            │                                 │
ManagedAccountInitiateLinkingQuery (no vars) ──►│
   │◄── linking material (token/URL, expiry)    │
   │  share with dependent (deep link / code)   │
   │                                            │                                 │
   │                                            │◄── dependent opens link ───────│
   │                                            │   ManagedAccountValidateLinkingQuery {linking_token, sponsor_jid} (assets; call site not traced)
   │                                            │   ManagedAccountAcceptLinkingMutation {linking_token} (assets; call site not traced)
   │◄── notification: sponsor_jid (PaaAcceptLinkingIBHandler) ────────────────────│
   │                                            │   ManagedAccountCompleteLinkingMutation {linking_token} (assets; call site not traced)
   ▼                                            │                                 ▼
local ManagedAccountConnection row created on both sides (role=SPONSOR / DEPENDENT, connectionLid, connectionPnJid, linkTs)
   │                                            │                                 │
   ▼                                            │                                 ▼
periodic ManagedAccountQuery (no vars) + ManagedAccountSyncActivities ──────────► sponsor controls hub / activity alerts
```

### 11.2 Bir sağlayıcıya devredilen işletme numarası: peer'ın istemcisinin gördüğü

```
[Peer opens a chat/profile/call with the business number]
   │
   ▼
local verified-name cert for that JID: host_storage, actual_actors, privacy_mode_ts, issuer (smb:/ent:)
   │
   ▼
C198628cb.A02() → business_state_id (0-17)
   │
   ├─ id 15 (certificate missing/revoked)          → "no longer an official business account" (str08b3 family)
   ├─ ids 5/6/9/10 (hostStorage==2, or chat-gated)  → "uses a secure service from Meta to manage this chat/call" (str080d/f family)
   └─ ids 16/17 (coexistence residual states)       → "uses multiple tools... Business app AND a secure service from Meta" (str38ef-fb family)
```

---

## 12. Bilinmeyenler

| Konu | Neden |
|---|---|
| Tam tuple→`business_state_id` tablosu (18 değerin tümü) | `C198628cb.A02()` üzerinde decompiler region-overflow'u; birkaç branch birleştirilmiş |
| `smb:`/`ent:` issuer-prefix proxy'sinin ötesinde `hostStorage`/`actualActors`'ın tam sayısal anlamı | bu istemcide adlandırılmış sabit yok; on-premises/Cloud-API/BSP terimlerine eşleme, public Business Platform terminolojisinden inferred'dır, koddan okunmamıştır |
| `ManagedAccountValidateLinkingQuery`, `AcceptLinkingMutation`, `CompleteLinkingMutation`, `RevokeLinkingMutation`, `SyncActivities`, `UpdatePinMutation`, `GetSponsorAgeVerificationInfoQuery`'nin değişkenleri/response alanları | doc_id'ler assets'te doğrulandı; bu derlemede değişken adlarıyla bir call site bulunamadı |
| "client" kodu 4'ü besleyen `A09` boolean'ının anlamı | yalnızca bir gate olarak tüketiliyor; isim veya yorum yok |
| `SPONSOR_ADMIN` vs `SPONSOR`'ın ek hakları | rol var; farklılaştırılmış davranış izlenmedi |
| PAA / PMA / PMTA kod adlarının açılımı | string'lerde veya yorumlarda hiçbir zaman yazılmadı; yalnızca kullanım bağlamı |
| `ManagedAccountDebugConnectionActivity`/`DebugPinAuthActivity`'nin release build'lerden erişilebilirliği | adlandırma sadece-debug olduğunu öneriyor; her iki yönde de launch path bulunamadı |
| Cloud-API-hosted bir numaranın sunucu taraflı provisioning'i (bölüm 9.3) | tamamen sunucu tarafında; bu istemci bunu hiçbir zaman başlatmaz ve yalnızca ortaya çıkan marker'ları gözlemler |
| Herhangi bir istemci kodunun "doğrudan Meta tarafından işletilen" ile "Meta'nın Cloud API'si üzerinden üçüncü taraf bir BSP tarafından işletilen"i ayırt edip edemediği | ikisi de aynı `hostStorage`/`actualActors`/platform-type sinyallerine çöküyor gibi görünüyor; ayrı bir BSP identifier alanı bulunamadı |
| Gerçek trafik | yalnızca statik analiz |
