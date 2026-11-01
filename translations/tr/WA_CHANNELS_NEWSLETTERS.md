<!-- src-sha1: 42c77add3dafd5b90522b32d91692dff968b2f54 -->
# WhatsApp Kanallar ve Bültenler — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** `@newsletter` JID domain'i ve dahili "newsletter" adlandırması, follow/unfollow, kanal oluşturma, admin rolleri ve devir, altı `newsletterAdmin*`/`newsletterFollower*`/`newsletterScheduledMessage` proto alanı, kanal metadata'sı (ad, açıklama, resim, doğrulama, durum), post'lardaki reaksiyonlar, görüntülenme/takipçi sayıları, admin davet/iptal/kabul akışı, GraphQL/MEX newsletter operasyonları (doc_id'ler), yerel depolama, feature flag'ler, hata durumları

---

## 1. Teknik olarak ne

Bir "kanal", istemcinin dahili olarak **newsletter** dediği şeyin tüketici adıdır: sunucu tarafında (E2E olmayan) depolamaya sahip bire-çok yayın JID'i, küçük bir rol seti (owner/admin/subscriber/guest) ve kontrol düzlemi operasyonlarının çoğu klasik XMPP IQ'ları yerine `w:mex` GraphQL üzerinden taşınır. İçerik dağıtımı (post fetch, status fetch, zamanlanmış mesajlar, canlı güncelleme aboneliği) hâlâ ayrı bir XMPP IQ namespace'i kullanır: `xmlns="newsletter"`. Tüm ifadeler derlenmiş APK'nın statik analizine dayanır; ağ üzerinde hiçbir şey yakalanmadı. Tier'ler: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi. Bu repodaki çoğu obfuscated-isim raporunun aksine, istemci tarafında görünen newsletter paketi (`com.whatsapp.newsletter.*`, 122 dosya) 2.26.41.6'da **okunabilir sınıf ve metod adlarıyla** geliyor; yalnızca paylaşılan altyapı (JID, mesaj proto'su, IQ builder'ları) obfuscated ve burada kararlı string'lerden yeniden çözüldü.

Kapsam dışı: klasik broadcast listeleri ve `status@broadcast` — bkz. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md). Newsletter'lar tarafından yeniden kullanılan (newsletter'a özgü olmayan) kişi/cihaz lookup mekaniği — bkz. [WA_USYNC.md](WA_USYNC.md).

| Varlık | Değer | Tier |
|--------|-------|------|
| JID sunucusu | `newsletter` (örn. `120363000000000000@newsletter`) | found |
| `Jid.getType()` | **21** | found |
| Şifreleme | `EnumC14260eC.NON_E2EE` — kanal içeriği **uçtan uca şifreli değildir** | found |
| Yerel model sınıfı | `C2130898y` ("NewsletterInfo"), generic chat satırı `C14220e7`'yi extend eder | found |
| JID sınıfı | `C1Y7` (`NewsletterJid`) | found |
| Davet linki | `https://whatsapp.com/channel/<invite_code>` | found |
| Yerel DB tablosu | `newsletter` (sütunlar: `membership`, `invite_code`, indeksli) | found |

| Bileşen | 2.26.41.6 adı | Rol |
|-----------|----------------|------|
| JID parser | `C0DL.A03` (sunucu-string switch), `C1Y7` (JID), `C1Y8` (JID companion/cache) | sayısal id'yi doğrular, baştan sıfır yok, `C1Y7`'yi inşa eder/cache'ler |
| JID predicate'leri | `C0DZ.A0a(jid)` = `getType()==21`; `C0DZ.A0M` tip 21'i, gruplar (18), broadcast list (3), status (5) vb. içeren sete dahil eder | isNewsletter / multi-recipient-capable set |
| Yerel model | `C2130898y` | rol, doğrulama, sessize alma, reaksiyon ayarı, durum, sayaçlar |
| Roller | `C9U5` (yerel enum), `C9U4` (wire string enum) | bölüm 4 |
| Metadata job'u | `BaseMetadataNewsletterGraphqlJob`, `GetNewsletterAdminMetadataJob` | `NewsletterMetadata` / `NewsletterAdminMetadataQuery` |
| Güncelleme job'u | `UpdateNewsletterGraphqlJob` | `NewsletterMetadataUpdate` |
| Oluşturma/silme job'u | `com.whatsapp.newsletter.editcreate`, `com.whatsapp.newsletter.delete` altında | `NewsletterCreate(Verified)` / `NewsletterDelete` |
| Mesaj fetch | `GetNewsletterMessagesJob`, `GetNewsletterMessagesUpdatesJob`, `GetNewsletterMyAddOnMessagesJob`, `SendNewsletterMessageJob`, `SendViewReceiptJob` | `com.whatsapp.newsletter.messages.job` |
| Status (kanal güncellemeleri) fetch | `GetNewsletterStatusesJob`, `GetNewsletterStatusUpdatesJob`, `GetStatusMyAddOnsJob` | `com.whatsapp.newsletter.status.job` |
| IQ builder | `C9EN` (`xmlns="newsletter"` constructor'lar), `C9E2` (view-role / child-node değer setleri) | bölüm 6 |
| Admin davet gönderimi | `C9m6` (`UserActionsNewsletterMessaging`), `C213489Am` | bölüm 5.4 |
| Reaksiyon deposu | `C12H`, `C23768ANd` → tablo `newsletter_message_reaction` | bölüm 7 |

---

## 2. JID ve domain

### 2.1 Parsing (found, `C0DL.A03`)

```java
// X.0DL (C0DL)
public C1Y7 A03(String str, String str2) throws C09B {
    String strTrim = str.trim();
    if (strTrim.isEmpty() || "0".equals(strTrim) || strTrim.indexOf("0") == 0)
        throw new C09B("Identifier must be a valid number starting with non-zero");
    if (!"newsletter".equals(str2)) throw new C09B(...);
    // cache lookup/insert, returns C1Y7(str)
}
```

`C1Y7.getServer()` literal `"newsletter"` string'ini döner; `getType()` `21` döner. Diğer multi-party JID tipleriyle aynı baştan-sıfır-yok sayısal-id kuralı (gruplar, broadcast listeleri — bkz. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §2.1). Generic JID router `C0DZ.A01`, string bilinen bir singleton, bir `UserJid` ya da bir `GroupJid` olmadığında default case olarak `C1Y7.A03.A02(str)`'ye düşer — yani `@newsletter`, bu parser'daki fallback domain'dir (found).

### 2.2 Tip-set üyeliği (found, `C0DZ.java`)

```java
public static boolean A0a(Jid jid) { return jid != null && jid.getType() == 21; }   // isNewsletter
public static boolean A0M(Jid jid) {
    int type = jid.getType();
    return type==0||type==1||type==18||type==22||type==3||type==7||type==21||type==26||type==28;
}
```
`A0a`, dedike newsletter predicate'idir. `A0M`, tip 21'i gruplar (18/22), broadcast list (3), community (7) ve diğerleriyle birlikte daha geniş bir "multi-participant-capable" sete gruplar (tam grupların amacı eksiksiz izlenmedi; paylaşılan participant/session makinesini gate'lediği çıkarsanıyor, inferred).

---

## 3. Follow / unfollow

Follow etmek bir stanza aboneliği **değildir**; bir `w:mex` mutasyonudur, ve yerel rol (`C9U5`) `GUEST` ile `SUBSCRIBED` arasında döner.

| Operasyon | doc_id | Değişkenler (found) |
|-----------|--------|--------------------|
| `NewsletterJoin` | `24658527423838739` | `entry_point`, `record`, `recipient_account_id`, `sessions`, `jid`, `fetch_and_validate_vname`, `call_offer`, `request_bottom_sheet_fragment` |
| `NewsletterLeave` | `25758579043742316` | `NewsletterJoin` ile aynı biçim |

Her ikisi de aynı sınıf tarafından inşa edilir: `X/RunnableC24381AnW.java` (found). Paylaşılan değişken seti (`entry_point`, `call_offer`, `request_bottom_sheet_fragment`), join/leave'in uygulamanın başka yerindeki aramalar ve bottom-sheet tetikli aksiyonlar için de kullanılan generic bir "chat action" mutation wrapper'ını yeniden kullandığını düşündürüyor (inferred).

`C2130898y` ("NewsletterInfo") nesnesi üzerindeki yerel rol geçişleri:

| Yardımcı | Koşul | Anlamı |
|--------|-----------|---------|
| `A0p()` | `!muted && role==ADMIN` | admin mi |
| `A0q()` | `!muted && (role==ADMIN \|\| role==OWNER)` | admin veya owner mı |
| `A0r()` | `role==SUBSCRIBED` | follow ediyor mu |
| `A0s()` | `role==GUEST` | follow etmiyor (metadata yenilemesinde `fetch_viewer_metadata=true`'yu zorlamak için kullanılır — `BaseMetadataNewsletterGraphqlJob`'da found) |
| `A0u()` | `!muted && role==OWNER` | owner mı |

Follow başarısızlığında UI hata string'i: `str1c0d` "Kanal takip edilemedi", `str1c0e` "Kanal takip edilemedi. Cihazınızın internet bağlantısını kontrol edip yeniden deneyin." (found, `res/values/strings.xml`).

---

## 4. Roller

İki paralel rol enum'u var: kalıcı yerel bir enum ve GraphQL değişkenlerinde/yanıtlarında kullanılan bir wire string enum'u.

### 4.1 Yerel rol (found, `C9U5`)

```java
GUEST=0 (A03), SUBSCRIBED=1 (A05), ADMIN=2 (A02), OWNER=3 (A04)
```
`C9U5.A00()`, ordinal'i bir öncelik rütbesine eşler: GUEST→4, SUBSCRIBED→3, ADMIN→2, OWNER→1 (daha düşük = daha ayrıcalıklı; amacı — admin listeleri için sıralama düzeni — inferred).

### 4.2 Wire rolü (found, `C9U4`, `serverValue` = enum adı)

```
UNSET_OR_UNRECOGNIZED_ENUM_VALUE, ADMIN, GUEST, OWNER, SUBSCRIBER
```
Newsletter XMPP IQ'larının `smax:any` alt elemanında `view_role` attribute değeri olarak (bölüm 6) ve GraphQL `viewer_metadata.role` değeri olarak (bölüm 8) kullanılır.

### 4.3 Yetkiler ve devir

| Aksiyon | GraphQL op | doc_id |
|--------|-----------|--------|
| Bir kullanıcıyı admin olarak davet et | `NewsletterAdminInvite` | `26278681041745438` |
| Bekleyen bir admin davetini iptal et | `NewsletterAdminInviteRevoke` | `24369392486051948` |
| Bir admin davetini kabul et | `NewsletterAcceptAdminInvite` | `24934958956134858` |
| Bir admin'i düşür | `NewsletterAdminDemote` | `25054538847517281` |
| Sahipliği devret | `NewsletterChangeOwner` | `24737692515842078` |
| Admin profillerinin toplu fetch'i | `NewsletterAdminProfilesQuery` | `28089989690595314` |
| Admin profili güncelleme (ad/foto) | `NewsletterAdminProfileUpdate` | `25959584293627630` |
| Admin metadata'sı (tam, admin'e özel alanlar) | `NewsletterAdminMetadataQuery` | `26882701001369256` |
| Yetki gate'i | `NewslettersAdminCapabilitiesQuery` | `27579307995002556` |

Admin-davet akışı aksiyon enum'u (found, `EnumC215899Sc`, `AdminInviteErrorDialog` tarafından kullanılır): `NOT_SUPPORTED=0`, `INVITE=1`, `ACCEPT_INVITE=2`, `REVOKE=3`, `DISMISS=4`.

UI hata string'leri (found): `str0095` "Admin daveti kabul edilemedi. Lütfen tekrar deneyin.", `str106c`/`str2bed` "Sahiplik devredilemedi. Lütfen tekrar deneyin(.)/ sonra.", `str2300`/`str2abd` "Kanal admin daveti", `str22fb` "%s admin olarak davet edilsin mi?", `str2bd8` "Kanal admin'i olarak davet et".

---

## 5. Admin daveti — client-to-client mesaj, sadece GraphQL değil

Admin-davet UX'inde birlikte çalışan **iki** ayrı mekanizma var: bir MEX mutasyonu (`NewsletterAdminInvite`, sunucu tarafı verme) ve davet payload'unu davet edilen kişiye taşıyan, MEX'ten bağımsız inşa edilen normal uçtan uca **1:1 mesaj**.

### 5.1 Proto (found, `Messages/newsletterAdminInviteMessage` başlangıç materyalini doğrular ve genişletir)

`Message.newsletterAdminInviteMessage` — `Message`'in **78** numaralı alanı (`C30628DTw`), tip `NewsletterAdminInviteMessage` (2.26.41.6'da obfuscated `C30596DSq`; JADX sabitleri sınıfın kendisinde, `Message` üzerindeki alan numarasında değil, çünkü grep'lenen sette admin-davet alan sabiti yoktu — alan 78, daha önceki bir WAProto.proto referansıyla eşleşiyor ve aşağıdaki diğer her alanın tam olarak belgelendiği şekilde çözülmesiyle bağımsız olarak doğrulanıyor):

| Alan | Numara | Tip |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `inviteExpiration` | **5** | int64 |
| `contextInfo` | **6** | `ContextInfo` |

Doğrulanmış alan-numarası sabitleri `CAPTION_FIELD_NUMBER=4`, `CONTEXT_INFO_FIELD_NUMBER=6`, `INVITE_EXPIRATION_FIELD_NUMBER=5`, `JPEG_THUMBNAIL_FIELD_NUMBER=3`, `NEWSLETTER_JID_FIELD_NUMBER=1`, `NEWSLETTER_NAME_FIELD_NUMBER=2` doğrudan `C30596DSq`'dan okundu (found) — bu sürüm için daha önceki bir alan haritasıyla tam eşleşiyor.

### 5.2 Gönderim yolu (found, `C9m6` = `UserActionsNewsletterMessaging`)

```java
public final void A00(Context context, C1Y7 c1y7, String name, String caption, HashMap userJidToExpiration) {
    byte[] thumbnail = A01(context, c1y7);           // JPEG of the channel picture, quality 80
    for (entry in userJidToExpiration) {
        C213489Am item = new C213489Am(..., 94, ...); // message-type tag 94
        item.A01 = c1y7;          // newsletterJid
        item.A03 = name;          // newsletterName
        item.A00 = entry.value;   // inviteExpiration
        item.A02 = caption;
        item.A0O(thumbnail, false);
        // enqueued as a normal E2E message to the invitee's UserJid
    }
}
```
Log satırı: `"UserActionsNewsletterMessaging/userActionSendNewsletterAdminInviteMessages"`. Her davet edilen kişiye bir mesaj gönderilir, her biri kendi son kullanma zaman damgasını taşır — yani davet **alıcı-başına bir E2E mesajıdır**, MEX `NewsletterAdminInvite` op'u (sunucu tarafı) ise yetkili verme kaydıdır (iki yol arasındaki ilişki inferred; ikisi de kodda mevcut, sıra/bağımlılık izlenmedi).

### 5.3 Kabul

Davet edilen kişinin istemcisi `NewsletterAcceptAdminInvite`'ı (MEX) çağırır. İsteği zaten tam metadata-fetch değişken setini taşır (`fetch_followers_count`, `fetch_state`, `fetch_verification`, `fetch_viewer_metadata`, …) — bir daveti kabul etmek ve kanalın metadata'sını yeniden fetch etmek bir round trip'tir (found, değişkenler `X/AbstractC23610Aaw.java`'dan).

---

## 6. Diğer newsletter mesajları: follower daveti, admin profili, zamanlanmış

### 6.1 `newsletterFollowerInviteMessage` / `newsletterFollowerInviteMessageV2`

2.26.41.6'da başlangıç materyalinin belirttiği şekilde doğrulandı ve burada bağımsız olarak yeniden doğrulandı: her iki `Message` alanı da mevcut (`NEWSLETTER_FOLLOWER_INVITE_MESSAGE_FIELD_NUMBER` = **108**, `NEWSLETTER_FOLLOWER_INVITE_MESSAGE_V2_FIELD_NUMBER` = **113**, ikisi de `C30628DTw` üzerinde isimli sabit olarak found), ve **ikisi de aynı alt-mesaj tipine** eşleniyor, `C30585DSf`:

| Alan | Numara | Tip |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `contextInfo` | **5** | `ContextInfo` |

Bir tip için neden iki alan numarası olduğu hâlâ **unknown** — bu geçişte de Java katmanında davranışsal bir ayrım bulunmadı (daha önceki bir bulguyla uyumlu).

### 6.2 `newsletterAdminProfileMessage` / `newsletterAdminProfileStatusMessage` / `newsletterScheduledMessage`

Üçü de `C30628DTw` üzerinde isimli sabit olarak mevcut (`NEWSLETTER_ADMIN_PROFILE_MESSAGE_FIELD_NUMBER` = **116**, `NEWSLETTER_ADMIN_PROFILE_STATUS_MESSAGE_FIELD_NUMBER` = **126**, `NEWSLETTER_SCHEDULED_MESSAGE_FIELD_NUMBER` = **132**), ve üçü de aynı generic tek-alanlı wrapper tipine çözülüyor, `BD2` (= `FutureProofMessage`):

```java
public final class BD2 { public C30628DTw message_; }   // field "message", number 1, type Message (recursive)
```

Üçü için de alana özel render/validator sınıfı yok (found, `newsletterAdminProfileMessage` ve `newsletterScheduledMessage` için daha önceki bir notla eşleşiyor). `newsletterScheduledMessage`'ın gerçekten dedike, mesaj-olmayan bir yüzeyi var: yerel tablo `newsletter_scheduled_message` (`chat_row_id`, `scheduled_server_id`, unique-indeksli) ve wire IQ alt elemanı `<scheduled_messages/>` (bölüm 6.3) — zamanlama *özelliği* gerçek ve izlendi; sadece `Message.newsletterScheduledMessage` proto alanının kendisi genişletilmemiş bir wrapper olarak kalıyor.

### 6.3 İlgili yerel tablolar

`newsletter_scheduled_message`, `newsletter_admin_profile` (`chat_row_id`, `admin_profile_id`, `timestamp`), sırasıyla `NewsletterAdminProfilesQuery`/`NewsletterAdminProfileUpdate`'i ve zamanlama UI'sını destekler (found, `C0SG.java`, `C0S3.java`).

---

## 7. Kanal post'ları: fetch, gönderim, reaksiyonlar, görüntülenme sayıları

### 7.1 XMPP IQ namespace'i `newsletter` (found, `C9EN`)

İçerik getirme ve birkaç yazma aksiyonu, MEX'ten ayrı dedike bir IQ namespace'i kullanır:

```xml
<iq xmlns="newsletter" type="get" to="<jid>@newsletter" id="…">
  <messages count="N">
    <smax:any type="jid" jid="<jid>@newsletter" view_role="admin|guest|owner|subscriber"/>
    <before count="N"/> <!-- or <after count="N"/> -->
  </messages>
</iq>
```

| Alt eleman | Constructor | Amaç |
|---------------|-------------|---------|
| `<messages count/>` + `<before>`/`<after>` | `C9EN(C9EB, C9E2, id, count)` | kanal post'larını sayfalama |
| `<message_updates count since/>` | `C9EN(C1Y7, C9E8, Long, id, count)` | düzenlenen/silinen post'ların delta senkronizasyonu |
| `<statuses count/>` | `C9EN(C9E9, C9E2, id, count)` | kanal status/güncelleme fetch'i |
| `<status_updates count since/>` | `C9EN(C1Y7, C9EA, Long, id, count)` | status post'larının delta senkronizasyonu |
| `<scheduled_messages count/>` | `C9EN(C1Y7, C31085Dfd, id, count)` | bekleyen zamanlanmış post'lar |
| `<question_responses server_id count/>` (düz ve `type="status"`) | `C9EN(...)` | bir post üzerindeki anket/soru yanıtları |
| `<my_question_responses server_id/>` | `C9EN(C1Y7, String, long)` | çağıranın kendi yanıtları |
| `<my_addons type="status" limit jid/>` | `C9EN(C1Y7, String, int, long)` | çağıranın kendi reaksiyonları/ek-öğeleri |
| `<live_updates/>` (`type="set"`) | `C9EN(C1Y7, String)` | bir kanal için canlı push'a abone ol |

`smax:any` üzerindeki `view_role` attribute'u, çağıranın kendi `C9U4` rol string'ini (admin/guest/owner/subscriber) her içerik-fetch IQ'suyla taşır — sunucu, yanıt içeriğini (örn. admin'e özel alanları) saf oturum durumuna göre değil, istek-bazında gate'liyor gibi görünüyor (inferred).

### 7.2 Gönderim (found, `SendNewsletterMessageJob`) ve görüntülenme makbuzları

Bir kanala post göndermek standart gönderim pipeline'ını yeniden kullanır (burada daha fazla detaylandırılmadı; job, normal `<message>` stanza makinesini sarar). Bir post'u görüntülemek, teslimat/okundu makbuzlarından açık ve ayrıdır:

```java
// com.whatsapp.newsletter.messages.job.SendViewReceiptJob
<receipt to="<jid>@newsletter" id="…" type="view">
  <list><item server_id="…"/> …</list>
</receipt>
```
Bir `view` makbuzu birden fazla sunucu mesaj id'sini toplu halde taşır. Kanal UI'sinde gösterilen post-başı **görüntülenme sayısını** besleyen mekanizma bu (found; sayacın kendisi sunucu tarafında toplanıyor — istemci sadece bildiriyor, bu IQ üzerinden bir sayıyı geri okumuyor).

### 7.3 Reaksiyonlar (found)

Kanal post'larındaki reaksiyonlar yerel depolamada **toplanmış, atfedilmemiş** haldedir:

```sql
CREATE UNIQUE INDEX newsletter_message_reaction_index
  ON newsletter_message_reaction (message_row_id, reaction);
-- columns include: reaction, reaction_count
```
yani her `(mesaj, emoji)` çifti için çalışan bir sayaçla bir satır var, reaksiyon veren her kullanıcı için bir satır değil — bu, kanal UI'sinin normal kullanıcılarda olduğu gibi bir reaksiyon veren listesi değil, emoji-başı toplam sayı göstermesiyle örtüşüyor. `newsletter_my_reaction_orphan_message` (`chat_row_id`, `server_message_id`, unique-indeksli), çağıranın hedefledği post'tan önce gelen **kendi** reaksiyonunu, post geldiğinde uzlaştırılmak üzere tutar.

Kimin reaksiyon verdiği sadece admin'lere, dedike bir MEX sorgusuyla görünür:

| Operasyon | doc_id | Değişkenler |
|-----------|--------|-----------|
| `NewsletterReactionSendersList` | `25219734117717032` | `server_id` |

Reaksiyon politikası kanal-başına yapılandırılabilir (bölüm 8.2, `reaction_codes`): `ALL`, `BASIC`, `BLOCKLIST`, `NONE` (wire string'ler, aşağıda `C9U3`/`C9TA`'ya bakın).

### 7.4 Metadata'daki follower / görüntülenme sayıları

`thread_metadata.followers_count`, `NewsletterMetadata`'nın (bölüm 8.1) bir parçası olarak döner. Dedike sayfalanmış bir op da var:

| Operasyon | doc_id | Değişkenler |
|-----------|--------|-----------|
| `NewsletterFollowers` | `25646542368289354` | `newsletter_id`, `count` |

Post-başı görüntülenme sayıları bu geçişte belgelenmiş bağımsız bir op tarafından döndürülmüyor; `messages`/`message_updates` IQ'sunun (bölüm 7.1) döndürdüğü mesaj-başı metadata'nın içinde yaşadıkları çıkarsanıyor, burada daha fazla genişletilmedi (tam alan adı unknown).

---

## 8. Kanal metadata'sı (GraphQL yanıt biçimi)

### 8.1 `NewsletterMetadata` yanıtı (found, zincir `C208048tR → C208038tQ → C208028tP`, GraphQL node `xwa2_newsletter`)

```
xwa2_newsletter {
  id
  refresh_after_interval_sec
  state { type }                                    // C9UA
  status_metadata { last_status_sent_time, last_status_server_id }
  thread_metadata {
    creation_time
    description { text, id }
    followers_count
    handle
    invite                                           // invite code / link token
    name { text, id }
    picture { direct_path, type, url, id }
    pinned_messages[]
    preview
    settings { reaction_codes { value } }            // C9U3
    verification                                     // EnumC216369Tx
    verification_source                              // EnumC216219Ti
    wamo_sub { plan_id }
  }
  viewer_metadata {
    role                                             // C9U4
    settings[]                                       // { type, value } = EnumC216349Tv / EnumC216359Tw
    wamo_sub_status                                  // EnumC216229Tj
  }
}
```

### 8.2 Enum'lar (found)

| Enum | Değerler (uygulanabilir yerlerde server-value string'leri) |
|------|---|
| `state.type` (`C9UA`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `DELETED`, `GEOSUSPENDED`, `NON_EXISTING`, `SUSPENDED` |
| `verification` (`EnumC216369Tx`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `UNVERIFIED`, `VERIFIED` |
| `verification_source` (`EnumC216219Ti`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `LEGACY_MANUAL_REVIEW`, `META_VERIFIED_SUBSCRIPTION` |
| `viewer_metadata.role` (`C9U4`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ADMIN`, `GUEST`, `OWNER`, `SUBSCRIBER` |
| `wamo_sub_status` (`EnumC216229Tj`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `INACTIVE` |
| `settings[].type` (`EnumC216349Tv`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `MUTE_ADMIN_ACTIVITY`, `MUTE_FOLLOWER_ACTIVITY` |
| `settings[].value` (`EnumC216359Tw`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `OFF`, `ON` |
| `reaction_codes.value` (`C9U3`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `BASIC`, `BLOCKLIST`, `NONE` |

`C2130898y` ("NewsletterInfo") üzerindeki yerel yansımalar: doğrulama durumu `EnumC216079Su` (`NOT_VERIFIED=0`, `VERIFIED=1`), doğrulama kaynağı `C9T1` (`UNKNOWN_VERIFICATION_SOURCE=0`, `META_VERIFIED_SUBSCRIPTION=1`, `LEGACY_MANUAL_REVIEW=2`), uygulama durumu `C9T2` (`NOT_ENFORCED`, `SUSPENDED`, `GEOSUSPENDED` — `A0w`/`A0x`'te okuma için flag **3877** arkasında gate'lenmiş), yerel "aktif" durum `C9T3` (`NOT_SET`, `INACTIVE`, `ACTIVE`), göç/oluşturma ilerlemesi `C9T9` (`NOT_STARTED`, `IN_PROGRESS`, `FAILED`, `COMPLETED`), dizin görünürlüğü `EnumC216039Sq` (`PUBLIC`, `PRIVATE`) ve yerel reaksiyon ayarı `C9TA` (`DEFAULT=0`→wire `"BASIC"`, `ALL=1`→`"ALL"`, `NONE=2`→`"NONE"`, `BLOCKLIST=3`→`"BLOCKLIST"` — eşleme `UpdateNewsletterGraphqlJob.A0M`'den okundu).

### 8.3 Güncelleme (found, `UpdateNewsletterGraphqlJob` → `NewsletterMetadataUpdate`)

```js
// GraphQl input built for doc_id 27150690864552229
updates: {
  description?: string,   // "" clears
  name?: string,
  picture?: base64,        // "" clears
  admin_profiles_enabled?: { settings: { admin_profiles_enabled, reaction_codes: { value: "ALL"|"BASIC"|"NONE"|"BLOCKLIST" } } }
}
newsletter_id: <jid>
fetch_image: true, fetch_preview: true, fetch_name: true,
fetch_viewer_metadata / fetch_state / fetch_verification / fetch_followers_count: <bool, usually mirrors viewer role>
```

### 8.4 Doğrulama UI string'leri (found)

`str136f` "Yeni doğrulanmış kanal", `str2be2`/`str2be3` "Doğrulanmış kanal oluştur"/ikon, `str2c51` "Doğrulanmış kanallar", `str2c78` "Doğrulanmış rozetiniz bu kanaldan kaldırılacak. Meta Verified aboneliğiniz aktif kalacak.", `str2ca9` "Üzgünüz, doğrulanmış bir kanalın adını uygulamadan değiştiremezsiniz. Lütfen yardım için müşteri desteğiyle iletişime geçin." — yani doğrulanmış kanalların sunucu tarafında zorlanan değişmez bir adı var (istemci tarafı sadece UX; zorlama tarafı unknown).

---

## 9. GraphQL / MEX newsletter operasyonları (doc_id'ler)

Aşağıdaki tüm doc_id'ler, bu build için `WhatsApp_2.26.41.6.apk` içindeki `assets/whatsapp-android-mex_client_persist_ids.json`'a karşı bağımsız olarak yeniden doğrulandı (found — doc_id'ler obfuscated değil statik asset girdileridir, ve burada denenen sürüm karşılaştırmasında kararlı). O asset'te toplamda 46 `Newsletter*` operasyonu var; bu raporun başka yerinde detaylandırılmayanlar:

| Operasyon | doc_id | Amaç (ad/değişkenlerden inferred) |
|-----------|--------|------------------------------------------|
| `NewsletterCreate` | `27009199332109318` | bir kanal oluştur |
| `NewsletterCreateVerified` | `27777918425146464` | önceden doğrulanmış bir kanal oluştur (ayrıcalıklı hesaplar) |
| `NewsletterDelete` | `31838460859131915` | bir kanalı sil |
| `NewsletterUpdateVerification` | `27133493439664458` | doğrulama durumunu talep et/güncelle |
| `NewsletterHide` / `NewsletterUnhide` | `25033614912931367` / `24551592861177484` | dizin görünürlüğü anahtarı (yerel `EnumC216039Sq`) |
| `NewsletterFollowing` | `26856957210673444` | hesabın takip ettiği kanal listesi |
| `NewsletterDirectoryList` / `Search` / `CategoryPreview` | `27480627564903390` / `27887355094203575` / `27432651036395658` | genel dizin gezinimi |
| `NewsletterSimilar` / `NewsletterRecommended` | `36410329795280256` / `26638880912457992` | keşif |
| `NewsletterInsights` | `24672564052397921` | owner/admin analitiği |
| `NewsletterPinMessages` / `NewsletterUnpinMessages` | `28521965914059511` / `37386851567568720` | sabitlenmiş-post yönetimi (`message_ids`) |
| `NewsletterBlockUser` | `25106066249006236` | bir takipçiyi engelle |
| `NewsletterLogExposures` | `24606408825709914` | dizin impression telemetri'si |
| `NewsletterLinkPreviewCheck` | `24188786150796507` | post'lardaki link önizleme domain'lerini doğrula |
| `NewsletterPollVoterList` | `24803802869271956` | bir post'taki anket oyları (`jid`, `vote_hash`) |
| `NewsletterQuestionResponseStateUpdate` | `24896618076668076` | Soru-Cevap moderasyon durumu |
| `NewsletterLabelAiContent` / `NewsletterLabelPaidPartnership` | `27470054215955630` / `26221505494211174` | post-başı AI-üretimi / ücretli-ortaklık etiketi |
| `NewsletterChangeWamoSub` / `Enable`/`DisableWamoSub` | `25201342542835866` / `25122474967344830` / `31916794074578680` | WhatsApp monetizasyon aboneliği durumu |
| `NewsletterUserReports` / `NewsletterCreateReportAppeal` | `27149305681394065` / `27792557363683798` | kötüye kullanım bildirimi / itiraz |
| `NewsletterEnforcements` / `NewsletterEnforcementAlertStates` | `27089116857425014` / `27640745535604048` | zorlama/askıya alma durumu (kendi `com.whatsapp.newsletterenforcements` paketi) |
| `NewsletterUpdateUserSetting` | `24935528202764688` | kullanıcı-başı UI tercihi (örn. kişi-seçici tooltip sayısı) |
| `FetchNewsletterRankingFeatures` | `24742757908756088` | sıralama sinyali fetch'i (dizin/öneri) |

Tümü `w:mex` IQ'ları (`type="get"`), şema `whatsapp_mex`, transport §5–8'de görülen paylaşılan `C16880is`/`TreeWithGraphQL` çağrı deseniyle doğrulandı (found). §8'in `NewsletterMetadata`'sının ötesindeki yanıt biçimleri bu geçişte genişletilmedi (unknown).

---

## 10. Depolama

| Tablo | Anahtar sütunlar (found) |
|-------|----------------------|
| `newsletter` | `membership` (indeksli), `invite_code` (indeksli) |
| `newsletter_message` | `(chat_row_id, server_message_id)` üzerinde unique; `is_autodelete_eligible` (indeksli) |
| `newsletter_message_reaction` | `(message_row_id, reaction)` üzerinde unique; `reaction`, `reaction_count` |
| `newsletter_my_reaction_orphan_message` | `(chat_row_id, server_message_id)` üzerinde unique — çağıranın kendi reaksiyonu, hedefinden önce gelmiş |
| `newsletter_admin_profile` | `(chat_row_id, admin_profile_id)` üzerinde unique; `timestamp` (indeksli) |
| `newsletter_subscribers` | `(chat_row_id, type_of_fetch)` üzerinde indeksli |
| `newsletter_scheduled_message` | `(chat_row_id, scheduled_server_id)` üzerinde unique |
| `newsletter_interaction` | `timestamp_ms` ve `(newsletter_jid_row_id, timestamp_ms)` üzerinde indeksli |
| `newsletter_linked_account` | `chat_row_id` üzerinde indeksli |
| `newsletter_pinned_message` | `(chat_row_id, pin_timestamp_ms)` üzerinde indeksli |
| `newsletter_media_clear` | `(chat_row_id, media_type)` üzerinde unique |

Paylaşılan chat altyapısı (`chat`/`chat_view`, `message` çekirdek sütunları), herhangi bir `Jid`-tipli chat için olduğu gibi, gruplar/broadcast listelerindeki gibi yeniden kullanılır (bkz. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §3.5) — burada yeniden detaylandırılmadı.

---

## 11. Feature flag'ler

ID'ler `com.whatsapp.newsletter.*` içindeki çağrı noktalarında okunduğu şekilde; varsayılanların tümü bu geçişte çözülmedi (bilinenler işaretli).

| ID | Kontrol ettiği |
|----|----------|
| **3877** | `C2130898y` üzerindeki yerel zorlama-durumu yardımcılarının (`A0w`/`A0x`) okunmasını gate'ler (`SUSPENDED`/`GEOSUSPENDED` kontrolleri) |
| **1777** | dizin filtrelerinde ülke seçici |
| **5276** | newsletter→başka-bir-şey göçü UI'si sırasında kanal-kimliği görünümü |
| **6445** | `ShareNewsletterInviteLinkActivity` |
| **6618** | `ViewNewsletterProfilePhoto` |
| **7237** | `NewsletterStatusView` |
| **9096** | `SendNewsletterMessageJob` |
| **12989** | `NewsletterDirectoryCategoriesActivity` |
| **15754** | `GetNewsletterMessagesJob`'da perf-tracker "messages_fetch_end" marker'ı |
| **17985** | `ForwardCounterAcsRepository` (iletilmiş-post sayacı) |
| **19889** | `ForwardCounterApi` |
| **23797** | `NewsletterDescriptionView` |

Kesin varsayılan değerler ve gate'lenen davranışın tam kapsamı "sınıf sadece flag açıkken erişilebilir" ötesinde izlenmedi (çağrı-noktası biçiminden inferred); bu tabloyu, nereye bakılacağının bir haritası olarak ele alın, onaylanmış açık/kapalı varsayılanlar olarak değil (çoğu satır için unknown).

---

## 12. Hata durumları

| Semptom | Neden | Düzeltme / beklenen davranış |
|---------|-------|--------------------------|
| "Kanal takip edilemedi" (`str1c0d`/`str1c0e`) | `NewsletterJoin` başarısız oldu veya bağlantı yok | yeniden dene; bağlantıyı kontrol et |
| "Admin daveti kabul edilemedi. Lütfen tekrar deneyin." (`str0095`) | `NewsletterAcceptAdminInvite` başarısız oldu | yeniden dene |
| "Sahiplik devredilemedi…" (`str106c`/`str2bed`) | `NewsletterChangeOwner` başarısız oldu | daha sonra yeniden dene |
| "Üzgünüz, doğrulanmış bir kanalın adını uygulamadan değiştiremezsiniz." (`str2ca9`) | kanal `VERIFIED`; ad istemci tarafında değişmez | destekle iletişime geç (sunucu tarafı; kesin zorlama unknown) |
| Kendi reaksiyonunun eşleşen bir post'u yok henüz | reaksiyon stanza'sı/olayı post'un kendi teslimatıyla yarıştı | post gelene kadar `newsletter_my_reaction_orphan_message`'da tutulur, sonra uzlaştırılır |
| `state.type` = `SUSPENDED`/`GEOSUSPENDED` | kanala karşı zorlama aksiyonu | içerik fetch'i hâlâ `state`'i döndürür; gönderi/admin aksiyonları muhtemelen sunucu tarafında bloklanır (kesin gate unknown) |
| `state.type` = `DELETED`/`NON_EXISTING` | kanal silindi veya hiç var olmadı | istemci yerel `newsletter` satırını düşürmeli (uygulama yolu izlenmedi) |
| Admin-davet aksiyonu = `NOT_SUPPORTED` (`EnumC215899Sc`) | davet/kabul/iptal desteklenmeyen bir bağlamda denendi (örn. rol, build) | generic hata dialog'u, yeniden deneme butonu yok (`str5735`) |

---

## 13. Karıştırılmayacaklar

| Karıştırma | Fark |
|----------------|------------|
| Newsletter (`@newsletter`, tip 21) vs broadcast list (`@broadcast`, tip 3) | newsletter: sunucu-depolamalı, E2E değil, genel follow modeli, roller; broadcast list: sadece kayıtlı kişilere E2E sender-key fan-out — bkz. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) |
| `xmlns="newsletter"` IQ vs `w:mex` `Newsletter*` GraphQL op'ları | IQ = içerik fetch/sayfalama/abonelik (mesajlar, status'lar, zamanlanmışlar, canlı-güncellemeler); MEX = metadata, roller, dizin, moderasyon, monetizasyon |
| `newsletterAdminInviteMessage` (E2E 1:1 mesaj, alan 78) vs `NewsletterAdminInvite` (MEX mutasyonu) | mesaj, kendi son kullanma süresine sahip alıcı-başı bildirimdir; MEX op'u sunucu tarafı verme kaydıdır — ikisi de mevcut, ilişki inferred |
| `newsletterFollowerInviteMessage` (alan 108) vs `newsletterFollowerInviteMessageV2` (alan 113) | aynı payload tipi (`C30585DSf`); çiftlenme sebebi unknown |
| Yerel rol `C9U5` (GUEST/SUBSCRIBED/ADMIN/OWNER) vs wire rolü `C9U4` (…GUEST/ADMIN/OWNER/SUBSCRIBER) | aynı dört rol, farklı ordinal düzen ve farklı string büyük/küçük harf-sırası — ordinal uyumluluğu varsaymayın |
| `reaction_codes` wire değeri (`ALL`/`BASIC`/`BLOCKLIST`/`NONE`, `C9U3`'ten) vs yerel `C9TA` ordinal-string eşlemesi | yerel ordinal 0 (`DEFAULT`), `"DEFAULT"` değil wire string `"BASIC"`'e serialize olur |
| Post-başı reaksiyon depolaması (`newsletter_message_reaction`, toplam sayı) vs normal mesaj reaksiyonları | kanallar her `(mesaj, emoji)` için bir sayaçla bir satır depolar, reaksiyon veren her kullanıcı için bir satır değil |

---

## 14. Komple akış

```
[Admin]  create channel
    │   NewsletterCreate / NewsletterCreateVerified (MEX) ──► [WA Server] allocates <id>@newsletter
    ▼
[Admin]  set name/description/picture, reaction policy
    │   UpdateNewsletterGraphqlJob ──► NewsletterMetadataUpdate (MEX)
    ▼
[Admin]  invite co-admin
    │   C9m6: per-recipient E2E message (newsletterAdminInviteMessage, field 78, own expiration)
    │   + NewsletterAdminInvite (MEX, server-side grant)
    ▼
[Invitee]  NewsletterAcceptAdminInvite (MEX) ──► role GUEST/SUBSCRIBED → ADMIN (C9U5)

[User]  discover channel (directory / shared link https://whatsapp.com/channel/<code>)
    ▼
[Client]  NewsletterJoin (MEX) ──► role → SUBSCRIBED
    ▼
[Client]  <iq xmlns="newsletter" type="get"><messages count view_role=subscriber/></iq>
    │◄── posts, paginated by before/after server_id
    ▼
[User]  views post ──► <receipt type="view"><list><item server_id/></list></receipt> (view count)
[User]  reacts ──► newsletter_message_reaction (aggregate count, own reaction may be orphaned until post lands)

[Admin]  moderates: NewsletterReactionSendersList (who reacted), NewsletterBlockUser,
         NewsletterPinMessages/Unpin, NewsletterUpdateVerification, NewsletterChangeOwner
    ▼
[Owner]  delete channel ──► NewsletterDelete (MEX)
```

---

## 15. Bilinmeyenler

| Öğe | Sebep |
|------|--------|
| E2E admin-davet mesajı ve MEX `NewsletterAdminInvite` vermesi arasındaki kesin ilişki/sıralama | ikisi de kodda mevcut; hangisinin yetkili olduğu, veya birinin diğerini tetikleyip tetiklemediği izlenmedi |
| `newsletterFollowerInviteMessage` (108) ve `…V2` (113)'ün neden bir proto tipini paylaştığı | Java katmanında davranışsal bir ayrım bulunmadı |
| Mesaj-fetch yanıtındaki post-başı görüntülenme-sayısı alan adı/konumu | `messages`/`message_updates` IQ payload'u içinde var olduğu çıkarsanıyor; genişletilmedi |
| Doğrulanmış kanallarda değişmez adın sunucu tarafı zorlanması | istemci sadece statik bir hata string'i gösteriyor |
| `NewsletterMetadata`'nın ötesindeki çoğu MEX op'unun tam yanıt biçimi | bu geçişte okunmadı |
| §11'deki çoğu feature flag için varsayılan değerler | sadece sınıf-erişilebilirliği, onaylanmış varsayılan durum değil |
| Trafik / canlı sunucu davranışı | hiçbir şey yakalanmadı; sadece statik analiz |

---

## 16. Baileys

Kapsanmadı: `baron-baileys-v2` (bu repodaki diğer raporlarda karşılaştırma temeli olarak kullanılan Baileys fork'u), yazım anında bu APK'ya karşı doğrulanmış, onaylı bir newsletter/channel implementasyonuna sahip değil. Bu rapor için Baileys tarafı kod incelenmedi. Kontrol edilmiş gerçekler olmadan bir Baileys bölümü eklemek bu reponun kanıt kurallarını ihlal eder. `baron-baileys-v2` newsletter desteği sunduğunda, bu bölüm JID'e (tip 21, sunucu `newsletter`), §7.1'in `xmlns="newsletter"` IQ'larına ve §9'un MEX doc_id'lerine karşı doldurulmalıdır.
