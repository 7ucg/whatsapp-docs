<!-- src-sha1: 5fa1223d0cb214989ef32453299c247d3ee92ecf -->
# WhatsApp Org Hesapları — Full RE Report
**Sürüm:** 2.26.45.10 | **Tarih:** 2026-11-15
**Kapsam:** org-hesabı varlık modeli (org_id, üye dizini, üye-etiketi/ekip taksonomisi), davet-linki katılma akışı, görünen-ad uygunluk kontrolü, email-gated onboarding (OTP), `GraphQlOrgApi`/`OrgEmailCodeClient` operasyon kataloğu (9 operasyon, `www` + `mex`), Managed Account ile ve WhatsApp Business API delegasyonu ile olan farkı, Baileys/velowa uygulama notları

---

## 1. Org hesabı nedir

Tüm ifadeler decompile edilmiş APK'nın statik analizidir. Kademe: **found** = bir çağrı noktasında doğrudan okunan string/alan, **inferred** = izlenmiş baştan sona bir çağrı olmadan kod şeklinden çıkarılan, **unknown** = çözülmemiş.

Bir "org" (hiçbir okunan string'de "organization"a açılmayan, baştan sona dahili isimlendirme), kendi kimliği, katılınabilir bir üye dizini ve davet-linki-artı-email-OTP onboarding yolu olan, hesabın kendi telefon-numarası kaydından ve bu repoda zaten bulunan diğer iki "managed" benzeri sistemden (bölüm 7) tamamen ayrı bir üyelik varlığıdır.

| Varlık | Dahili ad | Alanlar (found) | Rol |
|---|---|---|---|
| Org kimliği | `org_id` | `org_id`, `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description` | bir davet linkinden çözülen org'un kendisi |
| Davet linki | `link_token` | referrer/deep-link'ten nihai katılma mutation'ına kadar baştan sona taşınır | tek-kullanımlık(?) katılma kimlik bilgisi; tam ömrü `unknown` |
| Org içindeki üye kimliği | `display_name` (+ opsiyonel `display_last_name`), `member_tag` | hesabın ana profil adından bağımsız, kendi uygunluk/policy kontrolüne tabi üye-başına görünen ad | bir üyenin org'un dizini içinde nasıl gösterildiği |
| Ekip/rol taksonomisi | `team`, `team_options`, `selected_team` | durum alanları olarak found; tekil team değerlerinin anlamı çözülmemiş | org içindeki üyelerin gruplanması |
| Dizin ilişkisi | `relationship` (`OrgDirectory`), gözlenen tek değer `"CONTACT"` | — | gözlenen tek ilişki-filtresi değeri; diğer ordinal→string eşlemeleri `unknown` |

Bu alan isimlerinin tamamı, `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali` ve `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`'de (2.26.45.10) bir `GraphQlCallInput`/`LX/0jN` setter çağrısından hemen önce `const-string` literal olarak okunur, ayrıca `OrgJoinViewModel` durum-nesnesi alan listesi de — hepsi **found**. Bu operasyonları bir akışa dizen adım sıralaması (bölüm 3), tek bir izlenmiş çağrı dizisinden değil, durum alanlarının nasıl hizalandığından **inferred**'dir.

---

## 2. Operasyon kataloğu

İki transport üzerinde 9 operasyon, hepsi `com.whatsapp.orgs` içinde. 7'si `www` üzerinde (`GraphQlOrgApi`, `Lcom/facebook/pando/TreeWithGraphQL` üzerinden persisted-doc_id GraphQL), 2'si `mex` üzerinde (`OrgEmailCodeClient`). Aşağıdaki her satırda değişkenler çağrı noktasından **found**'dur.

| Op | Transport | doc_id (2.26.45.10) | Tip | Değişkenler | Amaç |
|---|---|---|---|---|---|
| `OrgInvitePreview` | www | `29166886682947630` | Query | `link_token` | katılmayı taahhüt etmeden önce org'u önizle (isim/ikon/üye sayısı) |
| `OrgCheckDisplayName` | www | `28738875225734024` | Query | `display_name` | üyenin org içindeki görünen adı için uygunluk/policy kontrolü |
| `OrgCheckEmailEligibility` | www | `28705126895811065` | Query | `link_token`, `email` | bu email bu belirli org davetinde kullanılabilir mi |
| `OrgSendEmailCode` | mex | `28659396457057459` | Mutation | `email` | email OTP gönder |
| `OrgVerifyEmailCode` | mex | `29096159596657036` | Mutation | `email`, `code` | email OTP'yi doğrula |
| `OrgJoin` | www | `29366364109633604` | Mutation | `link_token`, `email`, `org_display_name`, `member_tag`, `org_display_last_name` | nihai katılma gönderimi |
| `OrgDirectory` | www | `28698253656512395` (2.26.41.6'da `28049955604655823`'ten rotasyon) | Query | `org_id`, `relationship` (sadece `"CONTACT"` gözlendi), `first`, `after` | katılım-sonrası sayfalanmış üye dizini |
| `OrgMemberSearch` | www | `39884553687825642` (`28199835469697557`'den rotasyon) | Query | `query`, `org_id`, `first`, `after` | üye dizini içinde arama |
| `OrgLeaveMutation` | www | `28491454287217875` | Mutation | `org_id` | katılımdan sonra her an org'dan ayrılma |
| `OrgList` | www | `28999557569709709` (`27920891847589435`'ten rotasyon) | Query | `unknown` (doc_id/rotasyon dışında statik çağrı noktası bulunamadı) | hesabın üyesi olduğu org'ları listeleme |

7 `www` operasyonunun tümü bir sınıfta yaşar, `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`; her iki `mex` operasyonu da `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`'de. `www` operasyonları için namespace/schema `whatsapp-android-www`'dir; `mex` operasyonları için `whatsapp-android-mex`'tir. `OrgDirectory`/`OrgList`/`OrgMemberSearch`, 2.26.45.10'dan önce vardı (ilk olarak 2.26.41.6'ya karşı yakalandı); doc_id'leri iki build arasında döndü (aynı sınıf, aynı alan isimleri) — diğer 7'si 2.26.45.10'da yenidir.

Yardımcı arama operasyonları bir paket ötede mevcuttur, `com/whatsapp/work/publicidentity/` — katılma akışının kendisinin parçası değil, ama herhangi bir davet devreye girmeden önce bir eşin istemcisinin birinin bir org'a ait olduğunu öğrenme biçimi:

| Op | Transport | doc_id | Değişkenler | Amaç |
|---|---|---|---|---|
| `WorkPublicContactInfoQuery` | www | `29154186964216430` | `lids` (liste) | kişi-başına work/business-hesap durumu, toplu (`CoalescingBatcher`, debounced, tur başına maks 100 key) |
| `WorkPublicOrgInfoQuery` | www | `28899689926378846` | `ids` (liste, org id'leri) | bir kişinin ait olduğu org'lar için genel org bilgisi (`id`, `name`, 2 ek opak string alan — `inferred`: logo/domain) |

---

## 3. Baştan sona katılma akışı

`OrgJoinViewModel`'in durum-nesnesi alan isimlerinden derlenmiş **inferred** sıralama (bunu baştan sona kapsayan tek bir izlenmiş çağrı dizisi yoktur):

### 3.1 Giriş

Davet, bir link token olarak gelir, ya bir referrer/deep-link üzerinden (`OrgInviteReferrerOpener`, literal `org_invite_token_from_referrer` → `link_token` olur) ya da doğrudan açılarak (`OrgInviteLandingActivity`, başarısızlık durumları `org_invite_landing_failure` / `org_invite_landing_already_in_org` ile).

### 3.2 Önizleme

`OrgInvitePreview(link_token)`, kullanıcı herhangi bir şeye taahhüt etmeden önce `org_name`, `org_member_count`, `org_icon_url`/`org_icon_handle`/`org_icon_full_url`, `org_description`'ı doldurmaya yetecek bilgiyi döndürür.

### 3.3 Görünen-ad kontrolü

`OrgJoinActivity`/`OrgJoinViewModel`, `display_name`'i (+ opsiyonel `display_last_name`) ve bir ekip seçimini (`team`/`team_options`/`selected_team`) toplar. `OrgCheckDisplayName(display_name)`, policy/uygunluk kapısıdır; reddedilmesinde nested continuation `OrgJoinViewModel$checkName$2`, `name_refusal` ve/veya `last_name_refused`'u bağımsız olarak ayarlar — ad ve soyad her biri kendi başına reddedilebilir.

### 3.4 Email uygunluğu ve OTP

`OrgCheckEmailEligibility(link_token, email)`, belirli bir email'in bu belirli davet için kullanılıp kullanılamayacağını kontrol eder. Ardından `OrgSendEmailCode(email)` (mex) OTP'yi gönderir; kullanıcı onu girdikten sonra `OrgVerifyEmailCode(email, code)` (mex) onu doğrular. Doğrulama `username_pending_email` / `rejoin_after_username` / `username_screen_open`'ı yüzeye çıkarabilir — katılma, ana hesabın kendi username kurulumunun ardına gated edilebilir, orglarla aksi halde ilgisiz olan `WA_USERNAME.md`'nin sistemine bir bağımlılık.

### 3.5 Katılma

`OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)` nihai gönderimdir. Başarı, `joined=true`'yu ayarlar ve org alanlarını (`org_id`, `org_name`, `org_member_count`, `org_icon_*`, `org_description`) yerel durumda doldurur.

### 3.6 Katılım sonrası

`OrgDirectory(org_id, relationship="CONTACT", first, after)` üye dizinini çeker; `OrgMemberSearch(query, org_id, first, after)` içinde arar. `OrgLeaveMutation(org_id)`, katılımdan sonra her an ayrılır.

```
[Invite link / referrer]
  │ OrgInviteReferrerOpener: org_invite_token_from_referrer -> link_token
  │ (or OrgInviteLandingActivity: org_invite_landing_failure / _already_in_org)
  ▼
[OrgInvitePreview(link_token)]
  │  org_name, org_member_count, org_icon_*, org_description
  ▼
[OrgJoinActivity / OrgJoinViewModel]
  │  org_join_offline, step, team/team_options/selected_team, display_name, display_last_name
  ▼
[OrgCheckDisplayName(display_name)]
  │  -> name_refusal / last_name_refused on rejection
  ▼
[OrgCheckEmailEligibility(link_token, email)]
  ▼
[OrgSendEmailCode(email)]           -- mex, OTP send
  ▼
[user enters code]
  ▼
[OrgVerifyEmailCode(email, code)]   -- mex, OTP verify
  │  -> username_pending_email / rejoin_after_username / username_screen_open
  ▼
[OrgJoin(link_token, email, org_display_name, member_tag, org_display_last_name)]
  │  -> joined=true, org_id/org_name/org_member_count/org_icon_*/org_description populated
  ▼
[OrgDirectory(org_id, relationship="CONTACT", first, after)]
[OrgMemberSearch(query, org_id, first, after)]
[OrgLeaveMutation(org_id)]
```

---

## 4. Ayırt edilmesi gereken noktalar — karıştırmayın

Bu istemcinin içinde/çevresinde ilgisiz üç "hesap yapısı" kavramı vardır. Hiçbir kod, proto veya doc_id alanını paylaşmazlar.

| | Org Hesapları (bu rapor) | Managed Account (`WA_MANAGED_ACCOUNT.md`) | Business API delegasyonu (BSP/Cloud API) |
|---|---|---|---|
| Varlık kimliği | `org_id`, kendi dizini | `connectionLid`/`connectionPnJid` ile anahtarlanan `ManagedAccountConnection` | doğrulanmış-ad sertifika alanları (`host_storage`/`actual_actors`), yeni bir varlık id'si yok |
| İlişki | davet linki ile gönüllü katılım, org başına N üye | bir sponsor ↔ bir bağımlı, bir denetim bağlantısı | Meta/bir sağlayıcı tarafından Cloud API üzerinden işletilen bir işletme numarası |
| Onboarding | davet linki + email OTP + görünen-ad uygunluk kontrolü | deep link + sponsor-başlatılan bağlama (`ManagedAccountInitiateLinkingQuery` vb.) | Meta'nın işletme platformunda sunucu tarafı provisioning; bu istemciye sonuçtaki işaretler dışında görünmez |
| Kod konumu | `com.whatsapp.orgs.*` | `com.whatsapp.managedaccount.*` / `pma.*` / `pmta.*` | özel bir paket yok; `w:biz` sertifika alanları ve multi-device `HOSTED` hesap tipi üzerinden sinyallenir |
| Transport | `whatsapp-android-www` GraphQL + `whatsapp-android-mex` (OTP) | sadece `whatsapp-android-mex` | `w:biz` stanza alanları, hiç bir katılma/davet protokolü değil |
| Ayrılma/bağlantıyı kaldırma | `OrgLeaveMutation(org_id)` | `ManagedAccountRevokeLinkingMutation` | uygulanamaz — hesap-başına katılma/ayrılma yok; numaranın kendisi sunucu tarafında provision/deprovision edilir |
| Dizin kavramı | evet — `OrgDirectory`/`OrgMemberSearch`, ilişki-kapsamlı | hayır | hayır |

Bunlardan hiçbiri diğerinin yeniden adlandırılması veya evrimi değildir: bir org hesabının denetim semantiği yoktur (yaş/graduation durumu yok, sponsor PIN yok) ve işletme-sertifikası semantiği yoktur (`host_storage`/`actual_actors` yok, issuer-prefix kontrolü yok); zaten kayıtlı bir WhatsApp hesabının üzerine katmanlanmış düz, gönüllü bir dizin-ile-üyelik modelidir. Ürün-isimlendirme sonucu ("şirketler/kurumlar için WhatsApp'ın kendi organizasyonlar özelliği"), sadece alan şeklinden **inferred**'dir (`org_id` + üye dizini + görünen-ad-uygunluk-kontrolü + email-domain doğrulaması) — bu özelliği adlandıran hiçbir pazarlama veya istemci-içi metin okunmamıştır.

---

## 5. Hata durumları

Bu build'in çağrı noktalarından bir hata-kodu tablosu oluşturulamadı — bu geçişte 9 operasyonun hiçbiri için yanıt-şekli literali (başarı/başarısızlık alan isimleri, sayısal hata kodları) bulunamadı. Okunan tek reddetme sinyalleri, `OrgJoinViewModel$checkName$2` içindeki iki boolean durum alanıdır:

| Belirti | Neden | Kanıt |
|---|---|---|
| Görünen ad reddedildi | `OrgCheckDisplayName` policy/uygunluk başarısızlığı | `name_refusal` ayarlanır (found, durum alanı) |
| Soyadı addan bağımsız olarak reddedildi | aynı kontrol, soyadına-özel dal | `last_name_refused` ayarlanır (found, durum alanı) |
| Katılma, username kurulumu bekleyerek bloklandı | `OrgVerifyEmailCode` başarısı, hesabın kendi username durumuna gated olur | `username_pending_email`/`rejoin_after_username`/`username_screen_open` (found, durum alanları; tam sunucu koşulu `unknown`) |
| Davet, zaten üyeyken açıldı | landing page short-circuit'i | `org_invite_landing_already_in_org` (found, string literal) |
| Davet linki geçersiz/süresi dolmuş | genel landing başarısızlığı | `org_invite_landing_failure` (found, string literal; ayrı bir alt-neden bulunamadı) |

---

## 6. Baileys / velowa uygulama notları

9 operasyonun tümü, velowa'nın diğer özellikler (username, gruplar) için zaten uyguladığı aynı `whatsapp-android-www`/`whatsapp-android-mex` namespace'leri üzerinde standart persisted-doc_id GraphQL/MEX çağrılarıdır — orglara özgü yeni bir transport veya native kripto katmanı bulunmadı.

| Wire-ready | Wire-ready değil |
|---|---|
| 9 operasyon adının + doc_id'nin + değişken key'inin tamamı (bölüm 2) — bir isteği şekillendirmeye yeter | Her operasyon için yanıt alan isimleri, `OrgJoinViewModel` durumuna açıkça okunan dört operasyon dışında unknown'dır (bölüm 1); bir istemci, canlı bir capture şekilleri doğrulayana kadar tüm yanıtları opak JSON olarak ele almalıdır |
| `link_token` yayılım yolu (referrer → önizleme → katılma) | Tam adım gating'i — sunucunun bölüm 3'teki sıralamayı zorunlu kılıp kılmadığı, veya örn. `OrgCheckDisplayName`/`OrgCheckEmailEligibility`'nin atlanıp atlanamayacağı — `inferred`'dir, doğrulanmamış |
| `OrgDirectory`/`OrgMemberSearch` sayfalama şekli (`first`/`after`, standart cursor deseni) | `relationship` enum'u: sadece `"CONTACT"` doğrulanmıştır; diğer olası değerler `unknown`'dır, bu yüzden bir istemci bunun tek geçerli filtre olduğunu varsaymamalıdır |
| `OrgLeaveMutation(org_id)` — tek-alanlı mutation, uygulaması önemsiz | `OrgList`'in değişkenlerinin tamamı (çağrı noktası bulunamadı — muhtemelen `{}` gönderiyor, doğrulanmamış) |
| Katılma akışından bağımsız, salt-okunur "bu kişi bir org'da mı" sorguları için `WorkPublicContactInfoQuery`/`WorkPublicOrgInfoQuery` | Davet-linki URL/deep-link formatının kendisi (host, path, token kodlaması) — bu geçişte yakalanmadı |

Bu akışı deneyen bir velowa uygulaması, bu repodaki diğer `inferred`-transport raporların (örn. `WA_USERNAME.md`) zaten taşıdığı aynı uyarıyla, yanıt şekillerini canlı bir hesaba karşı deneysel olarak keşfetmeyi beklemelidir.

---

## 7. Bilinmeyenler

| Konu | Neden |
|---|---|
| `OrgList`'in değişkenleri | doc_id + rotasyon dışında statik çağrı noktası bulunamadı; muhtemelen `{}` ama doğrulanmamış |
| `"CONTACT"` dışındaki `relationship` enum değerleri | sadece bir ordinal→string eşlemesi gözlendi (ordinal 0 → `"CONTACT"`); diğer dallar bu geçişte kapsanmadı |
| 9 operasyonun tümü için yanıt alan şekilleri | hiçbir çağrı noktasında yanıt-tarafı literal/alan adı bulunamadı; `OrgJoinViewModel` durum alanları dışındaki her şey opaktır |
| `link_token` ömrü/tek-kullanım semantiği | izlenmedi; sadece isimlendirme kuralına göre tek-kullanımlık varsayıldı |
| Bölüm 3'teki adım sıralamasının sunucu tarafında zorunlu kılınması | durum-alanı şeklinden derlendi, izlenmiş sıralı bir çağrı zincirinden değil — bir istemci adımları yeniden sıralayabilir veya atlayabilir; test edilmedi |
| `member_tag`/`team` değer kümeleri | alanlar var (`team_options`, `member_tag`) ama sayılmış değerler bulunamadı |
| Davet-linki URL formatı | bu geçişte yakalanmadı |

---

## 8. Kanıt

WhatsApp Android 2.26.45.10 smali'nin statik analizi, tüm literaller ve değişken key'leri `GraphQlCallInput`/`LX/0jN` setter çağrılarından hemen önce `const-string` olarak okundu. Hiçbir trafik yakalanmadı; tüm transport/yanıt-şekli ifadeleri `inferred`'dir. Kaynak: `com/whatsapp/orgs/data/graphql/GraphQlOrgApi.smali`, `com/whatsapp/orgs/data/graphql/mex/OrgEmailCodeClient.smali`, `com/whatsapp/orgs/ui/join/OrgJoinActivity.smali`, `OrgJoinViewModel.smali`, `OrgJoinViewModel$checkName$2.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteReferrerOpener.smali`, `com/whatsapp/orgs/ui/invite/OrgInviteLandingActivity.smali`, `com/whatsapp/work/publicidentity/graphql/MexWorkIdentityTransport.smali`.
