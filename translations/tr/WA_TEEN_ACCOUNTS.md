<!-- src-sha1: 03dc5e8e2a1874ff243bbae88accc3b09b397b6f -->
# WhatsApp Teen Hesabı Sponsor Onayı — Full RE Report
**Sürüm:** 2.26.45.10 | **Tarih:** 2026-11-15
**Kapsam:** `com.whatsapp.vpc.sponsor` paketi — bir reşit olmayanın ("teen") WhatsApp hesabı için bir ebeveyn/vasi ("sponsor") inceleme ekranı, navigasyon modeli, sponsor-tarafı yaş-doğrulama kapısı, üç sonuç ekranı (onaylandı/reddedildi/incelenemiyor), reddetme üzerine `account_deletion_time_ms` sonucu, neyin erişilebilir/wire-ile-izlenebilir olduğu ve olmadığı, ve `WA_MANAGED_ACCOUNT.md`'nin ebeveyn-denetimi sisteminden farkı

---

## 1. Bu ne

`2.26.45.10`'da yeni (`2.26.41.6` baseline'ında yok): `com.whatsapp.vpc.sponsor` altındaki dört sınıf,
bir ebeveyn/vasinin bir reşit olmayanın WhatsApp hesabı hakkında verdiği tek-seferlik bir inceleme
kararını uygular — onayla, reddet, veya inceleyemediğini bildir. Bu, mevcut `WA_MANAGED_ACCOUNT.md`
ebeveyn-denetimi ürününden yapısal olarak farklıdır (aşağıdaki bölüm 8 farkı ortaya koyar); Meta'nın
Instagram ve Facebook için zaten gönderdiği aynı teen-hesabı-güvenliği desenini WhatsApp'ın benimsemesi
olarak okunuyor: bir vasinin, bir reşit olmayanın hesap sahibi olmasına onay vermesi gerekiyor, reddetme
üzerine bir hesap-silme sonucu ile.

"VPC" istemcinin hiçbir yerinde açılmıyor; "Verified Parent/guardian Consent" (Doğrulanmış
Ebeveyn/Vasi Onayı), özelliğin şekli göz önüne alındığında en makul okumadır — **inferred**, found
bir string açılımı değil.

| Varlık | Sınıf | Rol |
|---|---|---|
| Host ekranı | `VpcSponsorActivity` | export edilmemiş, intent-filter yok — başlatma mekanizması çözülmemiş (§6) |
| View model | `X/B18` | gerekli başlatma argümanlarını tutar, yaş-kapısını çalıştırır, navigasyonu sürer |
| Nav/sonuç dispatcher'ı | `X/CaB` | paylaşımlı sınıf (ilgisiz yaş-doğrulama `ConsentFlowActivity`'si ve `WamoSubActivity`'yi de besler); `VpcSponsorActivity` olaylarını ele alan dal bu raporun izlediği şeydir |
| Onaylandı sonucu | `VpcSponsorApprovedFragment` | onay üzerine gösterilir |
| Reddedildi sonucu | `VpcSponsorDeclinedFragment` | reddetme üzerine gösterilir; silme geri sayımını gösterir |
| İncelenemiyor sonucu | `VpcSponsorCannotReviewFragment` | sponsor incelemek için doğrulanamadığında gösterilir |

Tüm bulgular decompile edilmiş APK'nın statik analizidir (`apktool` smali decode; büyük build'ler için
bu reponun güvenlik uygulamasına göre tam-APK JADX çalışması yok). Buradaki hiçbir şey wire üzerinde
yakalanmamış veya çalışma zamanında çalıştırılmamıştır. Kanıt kademeleri: **found** = smali'de doğrudan
okundu (bir literal string, alan veya sınıf); **inferred** = onu adlandıran bir literal olmadan kod
yapısından çıkarıldı; **unknown** = bu geçişte çözülmedi.

Aynı dört sınıf, alan/string düzeninde byte-byte değişmeden, `com.whatsapp.w4b`'de (WhatsApp Business)
`2.26.45.7`'de mevcuttur — sınıf varlığıyla **found**; bağımsız olarak yeniden izlenmemiştir, aşağıdaki
consumer-build izinin geçerli olduğu varsayılmıştır.

---

## 2. Navigasyon modeli

Ekran, kendi `toString()` literalleriyle (found) tanımlanan yedi uygulamaya sahip, sealed bir
destinasyon tipi tarafından (`LX/CvW`, sınıf varlığıyla found; arayüzün kendisi kendini-adlandıran
hiçbir string taşımıyor) sürülür:

| Sınıf | `toString()` | Ne yapar |
|---|---|---|
| `X/CSM` | `"AgeCollectionScreen"` | Meta'nın paylaşımlı çapraz-uygulama yaş-doğrulama akışına yönlendirir |
| `X/CSO` | `"ConsentNoticeScreen"` | gerçek onayla/reddet istemi — **bu paketin hiçbir yerinde render edilmiyor**, bkz §4 |
| `X/CSN` | `"ApprovedScreen"` | `VpcSponsorApprovedFragment`'i gösterir |
| `X/CSS` | `"DeclinedScreen(accountDeletionTimeMs=...)"` | `VpcSponsorDeclinedFragment`'i gösterir; bir `long` silme zaman damgası taşır |
| `X/CSR` | `"CannotReviewScreen(teenName=...)"` | `VpcSponsorCannotReviewFragment`'i gösterir; reşit olmayanın görünen adını taşır |
| `X/CSP` | `"ErrorExit"` | `vpc_sponsor_error_exit_dialog` dialog tag'ini gösterir, kapatıldığında activity'yi sonlandırır |
| `X/CSQ` | `"Exit"` | activity'yi hemen sonlandırır |

---

## 3. Gerekli başlatma argümanları ve sponsor yaş-kapısı

`X/B18`'in constructor'ı (found), activity'nin saved-state/navigasyon argümanlarından üç key okur,
ikisi gereklidir — eksik bir değer `IllegalStateException("Required value was null.")` fırlatır:

| Key | Tip | Notlar |
|---|---|---|
| `vpc_teen_name` | `String` | gerekli; reşit olmayanın görünen adı, daha sonra cannot-review ekranının bundle'ına düz `teen_name` olarak kopyalanır |
| `vpc_account_deletion_time_ms` | boxed sayı (`.longValue()`) | gerekli-mevcut, ama buradan okunan değer **atılır** — constructor bytecode'u okunarak doğrulandı, local hiçbir zaman bir alana saklanmıyor. Reddetme ekranının gerçekte gösterdiği sayı, incelemenin sonucu bir `DeclinedScreen` destinasyonu ürettiğinde daha sonra ayarlanan ayrı bir `X/CSS.A00` alanından gelir |
| `navigation` | nullable, `X/CSM.A00`'a karşı karşılaştırılır | eğer mevcut ve `AgeCollectionScreen` değilse, başlangıç destinasyonunu doğrudan tohumlar (örn. devam ettirilmiş/yeniden başlatılmış bir akış) |

Eğer bir başlangıç destinasyonu tohumlanmamışsa, `B18`,
`Lcom/whatsapp/dobverification/ContextualAgeCollectionRepository;->A06()Ljava/lang/Boolean;`'ı çağırır —
**nullable** bir boolean (found):

- **`null`** → `AgeCollectionScreen`'e navigasyon. Paylaşımlı `X/CaB` dispatcher'ı, bu durum için bir
  **Bloks yaş-doğrulama ekranı** başlatır — ilgisiz `ConsentFlowActivity`'nin kayıt-zamanı yaş
  kontrolleri için kullandığı aynı kod yolu (log satırı `"ConsentFlowActivity/navigate/launch Bloks age
  verification screen"`, paylaşımlı sınıfta found, vpc-özgü değil, ama vpc-sponsor'ın `AgeCollectionScreen`
  durumunun eriştiği dal).
- **`true`** → `ConsentNoticeScreen`'e navigasyon.
- **`false`** → `CannotReviewScreen(teenName)`'e navigasyon.

Bloks ekranı geri `VpcSponsorActivity.onAgeCollectionResult(ContextualAgeCollectionUsecaseApi$CACResult)`
üzerinden rapor eder (found, tam imza), aynı üç-yönlü kararı düz bir boolean yerine `CACResult`
alt-tipinden yeniden çalıştırır: bir boolean taşıyan bir sonuç yukarıdaki `true`/`false` dallarına
yeniden girer; kapatılmış/bloklanmış bir sonuç `Exit`'e yönlendirir; yaş-mevcut-değil veya başarısız
bir sonuç `ErrorExit`'e yönlendirir.

**Yorum (inferred, istemci-içinde adlandırılmamış):** *sponsor* — reşit olmayan değil — onayla/reddet
istemini görmeden önce Meta'nın paylaşımlı çapraz-uygulama yaş-doğrulama kontrolünü geçmelidir.
Bunu tamamlayamayan veya tamamlamak istemeyen bir sponsor hiçbir zaman gerçek onay kararına
ulaşmaz; yaş kontrolünün nasıl sonuçlandığına bağlı olarak `CannotReviewScreen`, `Exit` veya
`ErrorExit`'e yönlendirilir.

---

## 4. Onayla/reddet istemi bu paket tarafından render edilmiyor

`X/CaB`'nin `ConsentNoticeScreen` dalını okuyarak (found, tam bytecode): bu duruma ulaşıldığında, kod
navigasyon `StateFlow`'unun *mevcut* değerini `ConsentNoticeScreen`'e karşı yeniden kontrol eder —
ve hâlâ eşleşiyorsa, hiçbir şey render etmeden hemen `ErrorExit`'e yönlendirir. `com.whatsapp.vpc.sponsor`
veya izlenen `X/CaB` dalının hiçbir yerinde bu duruma hiçbir fragment, activity veya Bloks başlatması
bağlanmamıştır.

**Sonuç (inferred):** sponsorun üzerinde işlem yaptığı gerçek onayla/reddet UI'si bu paketten erişilebilir
native kod değildir. Yaş-kapısının da Bloks-güdümlü olması göz önüne alındığında, en tutarlı açıklama,
`VpcSponsorActivity` başlamadan *önce* başlatılan sunucu-render'lı bir Bloks ekranıdır, bu activity
sadece **sonucu** — onaylandı, reddedildi veya incelenemiyor — alıp eşleşen terminal fragment'i
göstermektedir. Bu geçişte onayla/reddet gönderiminin kendisi için hiçbir GraphQL/MEX operasyon adı
veya Bloks ekran id'si bulunamadı. **Unknown.**

---

## 5. Terminal sonuç ekranları

| Ekran | Okuduğu | Gösterdiği | Fragment'in kendi içindeki ağ çağrısı |
|---|---|---|---|
| `VpcSponsorApprovedFragment` | kendi argümanlarından hiçbir şey | başlık görseli, başlık/gövde metni, gövde içinde tıklanabilir bir `"manage"`-etiketli span, bir `"Done"` butonu | bulunamadı |
| `VpcSponsorDeclinedFragment` | `account_deletion_time_ms` (long, Fragment-arg bundle, `CSS.A00`'dan ayarlanır) | başlık görseli, başlık, silme zamanı **bir göreceli/süre string'i olarak biçimlendirilmiş** gövde metni (`LX/0Fg;->A05(LX/0Fc;J)Ljava/lang/String;` ile, çıplak bir zaman damgası değil), bir `"Done"` butonu | bulunamadı |
| `VpcSponsorCannotReviewFragment` | `teen_name` (String, Fragment-arg bundle, `CSR.A00`'dan ayarlanır) | başlık görseli, reşit olmayanın adını interpole eden başlık, gövde metni, kapatan bir `"OK"` butonu | bulunamadı |

**`account_deletion_time_ms`'in pratikte ne anlama geldiği:** reddetme ekranı bu değeri bir
göreceli-süre formatlayıcısı üzerinden biçimlendirir ve onu "kalan zaman" olarak gösterir, yani bu,
görüntüleyene silmenin zaten gerçekleştiğine dair bir bildirim değil **bir geri sayım** olarak
sunulur — formatlayıcı çağrısından found. Reddetmenin sunucu tarafında silmeyi gerçekten
*zamanladığı* mı, yoksa bu ekran render edildiğinde silmenin zaten hareket halinde olduğu mu
**unknown**'dır: bu paketteki hiçbir fragment kendi ağ çağrısını yapmaz; değer sadece ekranın
gösterdiği bir başlatma/navigasyon argümanı olarak gelir.

Bu üç ekranın tüm gövde metni (bu build'in `res/values/strings.xml`'inde `str5e24`-`str5e2c`)
literal yer-tutucu Lorem-ipsum metnidir — bu bir beta build'dir; düzen ve veri-bağlama found'dur,
nihai gönderilen metin **unknown**'dır.

---

## 6. Giriş noktası — çözülmemiş

`VpcSponsorActivity`, manifest'te `<intent-filter>` olmadan `android:exported="false"` olarak
deklare edilmiştir (found). Literal navigasyon-argümanı key'leri için (`vpc_teen_name`,
`vpc_account_deletion_time_ms`) ve `VpcSponsorActivity`'nin kendi dört sınıfı ile paylaşımlı
`X/CaB`/nav-altyapı yardımcı sınıfları dışında herhangi bir inşası için repo-çapında bir arama,
**decode edilmiş smali ağacının hiçbir yerinde hiçbir sonuç** vermiyor — negatif, found bir sonuç.

**Inferred:** bu istemcide hiçbir şey başlatma `Intent`'ini statik olarak inşa etmiyor. Bu
uygulamada başka yerlerde push-güdümlü navigasyonun nasıl çalıştığıyla tutarlı, en makul açıklama,
hedef activity'yi ve ekstralarını hardcoded bir çağrı noktasından değil çalışma zamanında push
payload verisinden çözen sunucu-güdümlü bir bildirim eylemidir — ama bu geçişte böyle bir dispatcher
tanımlanmamıştır. Bir sponsorun gerçekte nasıl bildirildiği ve bu ekrana yönlendirildiği **unknown**'dır.

---

## 7. Ağ yüzeyi

Akışın herhangi bir adımı için bu pakette hiçbir yerde hiçbir GraphQL/MEX operasyon adı, Bloks ekran
id'si veya binary-stanza `xmlns`'i bulunamadı: bir sponsoru bekleyen bir inceleme olduğu konusunda
bildirmek için değil, yaş-kapısı için değil (inferred Bloks, yakalanmış ekran id'si yok),
onayla/reddet gönderiminin kendisi için değil (§4), reddetme üzerine hesap-silme geri sayımını
gerçekte tetikleyen şey için değil. Bu akıştaki ağ-şekilli her şeyin, adlandırılmış, persisted bir
GraphQL/MEX query'si yerine Bloks'a binmesi inferred'dir — bu istemcide Meta'nın çapraz-uygulama
yaş-doğrulama araçlarının kalanının çalışma şekliyle tutarlı — ama bunların hiçbiri için bir
operasyon veya ekran tanımlayıcısı yakalanmadı.

---

## 8. Ayırt edilmesi gereken noktalar

### 8.1 vs. `WA_MANAGED_ACCOUNT.md` ("Managed account")

| `vpc.sponsor` (bu rapor) | `managedaccount.*` / PAA / PMA / PMTA (`WA_MANAGED_ACCOUNT.md` §2-8) |
|---|---|
| **Tek-seferlik bir inceleme kararı**: belirli bir reşit olmayanın hesabını onaylama, reddetme veya inceleyememeyi bildirme | Bağımsız olarak kayıtlı iki hesap arasında **devam eden bir denetim ilişkisi** |
| Hiçbir `w:mex` operasyonu bulunamadı; inferred Bloks, yakalanmış operasyon/ekran id'si yok | doc_id'lere sahip, `whatsapp-android-mex` schema'lı dokuz adlandırılmış `w:mex` `ManagedAccount*` operasyonu |
| Bu pakette hiçbir yerel ilişki kaydı bulunamadı | Yerel `ManagedAccountConnection` satırı (`connectionLid`, `role`, `linkTs`, `connectionPnJid`, ...) |
| Reddetme, **reşit olmayanın hesabının kendisi** için bir `account_deletion_time_ms` sonucu üretir | Bağlantıyı kaldırma (`ManagedAccountRevokeLinkingMutation`) denetimi sona erdirir; hiçbir hesap silinmez |
| Rol enum'u yok; sponsor basitçe "incelemecidir" | `EnumC08540Ng`: `NONE`/`DEPENDENT`/`SPONSOR`/`SPONSOR_ADMIN` |
| Giriş noktası çözülmemiş; activity export edilmemiş, deep link yok | Giriş noktası uygulama-içi bir deep link'tir (`ManagedAccountSponsorOnboardingViewModel`) |
| `managedaccount.*`/`pma.*`/`pmta.*` ile hiçbir sınıf, paket veya string paylaşmıyor | — |

Her iki paketteki hiçbir kod diğerine sınıf veya string ile referans vermiyor. Bir `vpc.sponsor`
onayının daha sonra bir `managedaccount.*` ilişkisi oluşturup oluşturmadığı veya onunla etkileşip
etkileşmediği izlenmedi; **unknown**.

### 8.2 vs. normal hesap oluşturma

Normal WhatsApp kaydı (`WA_ACCOUNT_LESS_SURFACE.md` / standart SMS/email OTP akışı), hiçbir vasi-inceleme
adımına sahip değildir; bir hesap, kendi sahibi kaydı tamamladığında aktif hale gelir. `vpc.sponsor`,
bazı bir tetikleyici (çözülmemiş, §6) ile hesabın devam eden varlığı arasına — farklı bir kişi
tarafından, farklı bir cihazda tutulan — harici bir onay kapısı sokar, reddetmenin bir silme sonucu
taşımasıyla. Bir hesabın en baştan bu vasi-inceleme durumuna neyin yönlendirdiği (kayıt sırasındaki
yaş, cihaz-üzerinde bir yaş sinyali, daha sonraki bir yeniden-sınıflandırma) bu pakette bulunamadı
ve **unknown**'dır.

---

## 9. Baileys / velowa erişilebilirlik notu

Bu akıştaki hiçbir şey, sadece-wire bir üçüncü-taraf istemci için erişilebilir değildir. Onayla/reddet
kararının kendisi, sponsorun kendi first-party istemcisinin render ettiği sunucu-render'lı bir Bloks
ekranı olarak inferred'dir (§4) — velowa'nın gönderebileceği veya gözlemleyebileceği bir mesaj, IQ veya
adlandırılmış GraphQL/MEX mutation'ı değildir. Sponsor-tarafı yaş-doğrulama kapısı (§3) da aynı şekilde
Bloks-güdümlüdür. Bu akışın herhangi bir parçası için bu build'in kataloglarında hiçbir doc_id, MEX
operasyon adı veya binary-node `xmlns`'i mevcut değildir. Burada uygulanacak hiçbir şey yoktur; bu
bölüm bunu ima edilmiş bırakmak yerine açıkça kaydetmek için var.

---

## 10. Bilinmeyenler

| Konu | Neden |
|---|---|
| "VPC"'nin açılımı | istemci-içinde hiçbir zaman açılmamış; Verified Parent/guardian Consent olarak inferred |
| `VpcSponsorActivity`'yi neyin başlattığı ve navigasyon argümanlarını ayarladığı | decode edilmiş ağacın hiçbir yerinde statik bir çağrı noktası bulunamadı; export edilmemiş, intent-filter yok |
| Onayla/reddet gönderiminin kendisi (ağ operasyonu, ekran id'si) | bu pakette uygulanmamış; inferred Bloks, yakalanmış tanımlayıcı yok |
| Reddetmenin sunucu tarafında silmeyi zamanlayıp zamanlamadığı, yoksa geri sayımın salt bilgilendirici mi olduğu | `VpcSponsorDeclinedFragment`'te ağ çağrısı yok; silmenin bu ekran render edildiğinde zaten sunucu tarafında başlatılmış olduğu varsayılıyor |
| Bir reşit olmayanın hesabını en baştan vasi incelemesine neyin yönlendirdiği | izlenmedi; bu pakette hiçbir tetikleyici koşul bulunamadı |
| Varsa, `managedaccount.*` ile ilişki | her iki yönde de çapraz referans bulunamadı |
| Tüm `vpc.sponsor` string'lerinin nihai gönderilen metni | bu beta build, Lorem-ipsum yer-tutucu metni gönderiyor |
| `ContextualAgeCollectionRepository.A06()`'nın null/true/false durumlarının "unknown/yeterli/yetersiz" ötesindeki tam semantiği | sadece kontrol akışından inferred; hiçbir alan veya enum adı bulunamadı |
| Gerçek trafik | sadece statik analiz; hiçbir şey çalışma zamanında yakalanmadı veya çalıştırılmadı |

---

## 11. Akış (kanıtın ulaştığı kadarıyla)

```
[Server / push — mechanism unresolved]
   │
   ▼
[VpcSponsorActivity starts] (launch args: vpc_teen_name, vpc_account_deletion_time_ms, navigation)
   │
   ▼
ContextualAgeCollectionRepository.A06() : Boolean?
   │
   ├─ null  ──► [Bloks age-verification screen] ──► onAgeCollectionResult(CACResult)
   │                                                     │
   │                                     ┌───────────────┼───────────────────┐
   │                                     ▼               ▼                   ▼
   │                             boolean payload   dismissed/blocked   no-age / failed
   │                             (re-enter below)      Exit               ErrorExit
   │
   ├─ true  ──► ConsentNoticeScreen
   │                 │
   │                 ▼
   │      [approve/decline prompt — not native to this package; inferred Bloks, unknown op]
   │                 │
   │      ┌──────────┼──────────────────┐
   │      ▼          ▼                  ▼
   │  ApprovedScreen  DeclinedScreen      (re-check of current state == ConsentNoticeScreen
   │      │          (accountDeletionTimeMs)   with no result yet falls to ErrorExit)
   │      ▼                 ▼
   │  VpcSponsorApproved  VpcSponsorDeclined
   │  Fragment ("Done")   Fragment (countdown text, "Done")
   │
   └─ false ──► CannotReviewScreen(teenName) ──► VpcSponsorCannotReviewFragment ("OK")
```
