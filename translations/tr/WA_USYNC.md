<!-- src-sha1: 8e15828bcc50ba6f6a9c5388872afeef15451af0 -->
# WhatsApp USync — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** USync IQ (`xmlns="usync"`): mode'lar, context'ler ve sync türleri, istek ve yanıt stanza yapısı, sorgu protokolleri (contact, sidelist, status, text_status, picture, business, devices, disappearing_mode, lid, username), kişi sorgulama ve telefon numarası keşfi, cihaz listesi senkronizasyonu, key-index ve ADV kontrolleri, LID eşlemesi, gizlilik token'ı zenginleştirme, MEX `UsyncQuery` ve protokol bazlı yönlendirme, rate limit'ler ve backoff, istemci tetikleyicileri, feature flag'ler, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

USync, toplu "bu kullanıcı kim" sorgusudur. Tek bir IQ bir kullanıcı listesi ve bir protokol (veri türü) listesi taşır; sunucu her kullanıcı ve her protokol için yanıt verir. Aynı stanza yapısı dört işe hizmet eder: rehber yükleme ve indirme, tek telefon numarası sorguları, profil verisi yenileme (status, picture, business, disappearing mode) ve mesaj fan-out için cihaz listesi yenileme. Tüm ifadeler çözülmüş APK'nın statik analizinden gelir; hiçbir şey ağ üzerinde yakalanmadı. Katmanlar: **found** = kodda okundu, **inferred** = çıkarım, **unknown** = çözülmedi. Gizlenmiş (obfuscated) adlar build'e özgüdür ve 2.26.41.6 içinde yeniden çözümlenmiştir.

| Katman | 2.26.41.6 adı | Rol |
|--------|----------------|-----|
| Stanza oluşturucu / ayrıştırıcı | `C18670m9` (log etiketi `UniSyncProtocolHelper`): `A06` oluşturma, `A07` gönderme, `CFS` sonuç, `Brt` iq hatası, `Bog` teslim hatası | `<iq xmlns="usync">` oluşturur, `<usync>` sonucunu ayrıştırır |
| İstek modeli | `A05` (tür + kullanıcılar + seçenekler), `A0A` (kullanıcı bazlı oluşturucu), `C222649hm` (kullanıcı bazlı istek), `C222589hg` (bekleyen istek, iq id başına bir tane) | ne sorulacağı |
| Sync türü | `EnumC21760rz` (30 değer), `EnumC21770s0` context, `EnumC21780s1` mode, `EnumC21790s3` scope | `mode` / `context` attribute kaynağı |
| Tekil sorgular | `C23638AId` (`ContactQuerySync`) | telefon numarası, JID, username, LID'den username'e |
| Toplu senkronizasyon | `C18580m0` (`ContactSyncHelper`), anonim callback `X.0m7` | çoklu protokol senkronizasyonu, MEX ile klasik arasında seçim, backoff pref'leri |
| Herkese açık giriş noktaları | `C18230lP` (`ContactSyncMethods`), `C21810s5` builder, `C21830s7` istek, `C21820s6` protokol kümesi, `EnumC21800s4` reason (77 değer) | tüm özellikler bunları çağırır |
| Sonuç uygulayıcı | `N27` (`contactsyncresultupdater`), `C51909N4g` (`ContactSyncDevicesUpdater`) | DB'ye, LID eşlemesine, cihazlara yazar |
| Cihaz / ADV | `C23310uY` (`DeviceSyncManager`), `SyncDevicesJob`, `C24230w2` (`DeviceADVInfoHandler`) | cihaz yenileme job'ları, key-index doğrulaması |
| Gizlilik zenginleştirme | `C223659jg` (`ProfilePrivacyEnrichmentFetcher`), `C197138a8`, `C197148a9` | kullanıcı başına tctoken ve ortak grup |
| MEX varyantı | `C229259vZ` (`MexUsyncQueryHelper`), `M4I` (route), `M5H` (protokol biti) | `UsyncQuery` ve yönlendirme |
| Backoff deposu | `C18800mM`, prefs dosyası `contact_sync_prefs` | `*_sync_backoff`, `*_full_sync_wait` |

Belirleyici noktalar:

- Android oluşturucusu on sorgu çocuğu üretir: `contact`, `sidelist`, `status`, `text_status`, `picture`, `business`, `devices`, `disappearing_mode`, `lid`, `username`. `bot` çocuğu ve feature çocuğu **yoktur** (found, `A06` içindeki tüm string sabitleri). `reachability`, `linked_profiles`, `orgs` ve `ddm` yalnızca MEX varyantında bulunur (bölüm 8).
- Android'de dört mode ve on context vardır (bölüm 2); okunan giriş noktalarında her istek `sid`, `index="0"`, `last="true"` taşır.
- Kullanıcılar `<list>` (normal) veya `<side_list>` (rehber dışı kişiler) içine konur.
- Profil istekleri kullanıcı başına bir gizlilik kanıtı taşır (kayıtlı tctoken veya ortak bir grup JID'i), bkz. bölüm 7 ve WA_TCTOKEN_CSTOKEN.md.
- Username sorguları WA_USERNAME.md içinde ele alınır; bu rapor yalnızca ortak stanza parçalarını kaydeder.

---

## 2. Stanza zarfı

### 2.1 İstek (found, `C18670m9.A06`)

```xml
<iq xmlns="usync" id="0AB1" type="get">                       <!-- `to` added by the sender, inferred -->
  <usync sid="sync_sid_query_<uuid>" index="0" last="true"
         mode="query" context="interactive" [allow_mutation="true"]>
    <query>                                                   <!-- protocol children, section 3 -->
      <contact [addressing_mode="lid"]/> <devices version="2"/> <picture type="preview" size="N"/> ...
    </query>
    <list>      <user jid="..." [common_gid="..."]> per-user children </user> ... </list>
    <side_list> <user jid="LID" pn_jid="PN"> ... </user> ... </side_list>
  </usync>
</iq>
```

| Parça | Kural (kod) |
|-------|-------------|
| iq `id` | `C10140Tq.A0G()`: `"0"` + bir sayacın hex değeri, 65536'da başa sarar ("iqId too large" loglar) |
| `sid` | `AbstractC43461pq.A00(prefix)` = prefix + `_` + rastgele UUID; prefix'ler `sync_sid_query`, `ContactSyncHelper/sync_sid_<scope>`, `..._mex_profile` |
| `index` / `last` | çağrıdan gelir: `A07` her zaman `0` ve `true` geçirir |
| `mode`, `context` | sync türünün `EnumC21780s1.modeString`, `EnumC21770s0.contextString` değerleri |
| `allow_mutation="true"` | `A05.A04` true olduğunda set edilir: `C11980aQ.A0G()` geçerliyken full / delta türleri için oluşturulur (anlamı izlenmedi) |
| contact çocuğu | herhangi bir istek contact istediğinde (`A05.A03`) veya başka protokol istenmediğinde bulunur |
| REGISTRATION context | `A06(...)` yerine `C10140Tq.A0A(...)` üzerinden gönderilir (found); fark izlenmedi |
| Gönderme seçenekleri | iq timeout argümanı 32000 ms (`ContactQuerySync`) veya 128000 ms (`ContactSyncHelper`); göndericiye sayısal `102` geçirilir (anlamı unknown) |

### 2.2 Mode'lar (found, `EnumC21780s1`)

| `mode` | Anlamı |
|--------|--------|
| `full` | kapsamın tam yeniden senkronizasyonu |
| `delta` | yalnızca son senkronizasyondan beri değişenler |
| `query` | listelenen kullanıcıların sorgusu, durum değişikliği yok |
| `download` | sunucu tarafındaki kişi kümesini çek |

### 2.3 Context'ler (found, `EnumC21770s0`)

`metadata`, `registration`, `interactive`, `background`, `notification`, `message`, `add`, `voip`, `snapshot`, `wamo`.

### 2.4 Sync türleri (found, `EnumC21760rz`)

Ad, wire kodu, context / mode / scope. 10-15 ve 17-20 kodları kullanılmıyor. Scope `PB` = telefon rehberi, `SL` = side list, `MP` = çoklu protokol sorgusu. Kod loglanır ve metriklerde tutulur; stanza yalnızca context ve mode taşır.

| Adlar (kod) | Context / mode | Scope |
|-------------|----------------|-------|
| `REGISTRATION_FULL` (0) | registration / full | PB+SL |
| `INTERACTIVE_FULL` (1), `INTERACTIVE_DELTA` (2) | interactive / full, delta | PB+SL |
| `BACKGROUND_FULL` (3), `BACKGROUND_DELTA` (4) | background / full, delta | PB+SL |
| `NOTIFICATION_CONTACT` (5) | notification / delta | PB |
| `INTERACTIVE_QUERY` (6), `ADD_QUERY` (9) | interactive / query, add / query | PB |
| `NOTIFICATION_SIDELIST` (7) | notification / query | SL |
| `INTERACTIVE_DELTA_SIDELIST` (8) | interactive / delta | SL |
| `BACKGROUND_QUERY_PICTURES` (16), `BACKGROUND_MULTI_PROTOCOL_QUERY` (21), `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` (22) | background / query | MP |
| `REGISTRATION_COMPANION_MULTI_PROTOCOL_QUERY` (23) | registration / query | MP |
| `INTERACTIVE_MULTI_PROTOCOL_QUERY` (24), `MESSAGE_MULTI_PROTOCOL_QUERY` (25), `VOIP_MULTI_PROTOCOL_QUERY` (26) | interactive, message, voip / query | MP |
| `NOTIFICATION_MULTI_PROTOCOL_QUERY` (27), `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY` (28) | notification / query | MP |
| `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` (29), `WAMO_MULTI_PROTOCOL_QUERY` (38) | message, wamo / query | MP |
| `CONTACT_DONWLOAD` (30, sic) | background / download | PB |
| `CONTACT_FORCE_UPLOAD` (31) | metadata / delta | PB+SL |
| `CONTACT_UPLOAD` (32), `NATIVE_CONTACT_DELTA` (39) | background / delta | PB |
| `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` (33) | background / full | PB |
| `CONTACT_UPLOAD_SNAPSHOT` (34), `CONTACT_DOWNLOAD_SNAPSHOT` (35), `CONTACT_FULL_SYNC_SNAPSHOT` (36) | snapshot / delta, download, full | PB, PB, PB+SL |
| `CONTACT_RESTORE_FULL_SYNC` (37) | background / full | WA rehberi |

Yardımcılar: `A00()` = delta, `A01()` = full, `A02()` = full ve registration. Yalnızca `BACKGROUND_QUERY_PICTURES` picture sorgu türünü `image` yapar; diğer her tür `preview` ister.

---

## 3. Sorgu protokolleri

### 3.1 Genel bakış (found)

| Protokol | `<query>` çocuğu | Kullanıcı bazlı istek çocuğu | Yanıt çocuğu (kullanıcı başına) | Notlar |
|----------|------------------|------------------------------|--------------------------------|--------|
| contact | `<contact/>` | `<contact>+digits</contact>`, `<contact username=.. lid=.. pin=../>`, `<contact type="delete"/>`, boş `<contact/>` | `<contact type="in\|out\|invalid">text</contact>` | yalnızca `<list>` içinde |
| sidelist | `<sidelist [addressing_mode="lid"]/>` | `<sidelist type="delete"/>` | `<side_list>` içinde `<sidelist type=..>` | rehber dışı kullanıcılar |
| status | `<status/>` | önbellekte süre varsa `<status t="secs"/>` | `<status t code type>text</status>` | Hakkında metni |
| text_status | `<text_status/>` | yok | `<text_status last_update_time ephemeral_duration_sec text><emoji content/></text_status>` | flag **5839** |
| picture | `<picture type="image\|preview" [size="N"]/>` | `<picture id="N"/>` önbellekteki id | `<picture id direct_path hash/>` | gizlilikle zenginleştirilmiş |
| business | `<business><verified_name/><profile v="N"/></business>` | `<business><verified_name serial/><profile tag/></business>` | `<business pn_jid><verified_name verified_level host_storage actual_actors privacy_mode_ts>cert</verified_name>...</business>` | `v` = AB **471** & 0x3FFC (varsayılan 1140) |
| devices | `<devices version="2"/>` | `<devices device_hash ts expected_ts/>` | `<devices><device-list><device id key-index is_hosted/></device-list><key-index-list ts expected_ts>bytes</key-index-list></devices>` | bölüm 5 |
| disappearing_mode | `<disappearing_mode/>` | yok | `<disappearing_mode duration t ephemerality_disabled/>` | `ephemerality_disabled` yalnızca flag **21235** ile okunur |
| lid | `<lid/>` | PN kullanıcısının bilinen bir LID'i varsa `<lid jid="LID"/>` | `<lid val="LID"/>` | bölüm 6 |
| username | `<username/>` | `<username username="@known"/>` | `<username>text</username>` veya `contact@username` | bkz. WA_USERNAME.md |

`<user>` üzerindeki kullanıcı bazlı attribute'lar: `jid` (PN veya LID), `pn_jid` (side-list girdileri), `common_gid` (bölüm 7). Bir kullanıcı ayrıca kayıtlı token baytlarını tutan bir `<tctoken>` çocuğu içerebilir. Yanıtlarda `<user>` ayrıca `pn_jid` ve `new_jid` taşır; ayrıştırıcı `jid` değerini alır, `jid` eksikse `pn_jid` değerine döner.

### 3.2 Contact (found)

| Biçim | Koşul | Notlar |
|-------|-------|--------|
| `<contact>+15550001111</contact>` | telefon sorgusu | numara string'i çağıranın verdiği haliyle iletilir; JID tabanlı sorgularda `C23638AId.A05`, JID bir telefon numarası JID'i ise ve (`C11980aQ.A0M()` / AB **26739** açıksa veya tür `ADD_QUERY` ise) `+` ekler |
| `<contact>15550001111</contact>` | LID adreslemeli PN kullanıcısı (`C11980aQ.A0L()`, AB **14565**) | `+` olmadan rakamlar |
| `<contact username="u" [lid=".."] [pin=".."]/>` | username sorgusu | `lid` / `pin` yalnızca AB **12402** ile, aksi halde yalnızca `username` |
| `<contact type="delete"/>` | silinmiş işaretli istek | yükleme senkronizasyonunda rehberden kaldırma |
| `<contact/>` | username'i olmayan LID kullanıcısı | yer tutucu |
| query `<contact addressing_mode="lid"/>` | AB **14565** | LID adreslemeli kişi senkronizasyonu |
| query `metadata_version="3"` | delta türü ve bir dahili flag | flag okunan yolda yalnızca sabit bir false'tan atanır, bu yüzden büyük olasılıkla hiç gönderilmez (inferred) |

Yanıt `type`: `in` = kayıtlı (dahili kod 1), `out` = kayıtlı değil (2), `invalid` = numara geçersiz (3); başka herhangi bir değer bozuk-stream hatası fırlatır. Her `<contact>` metin içeriği kullanıcı başına bir listeye eklenir.

Sonuç düzeyi `<result><contact version refresh integrity snapshot_recovery>`: `version` sonuçta tutulur, `refresh` saniyeleri full-sync bekleme süresini besler (bölüm 9), `integrity` `pass` (varsayılan), `pending` veya `timelock` (dahili 1 / 2 / 3), `snapshot_recovery` (`pending` / `pass`) yalnızca flag **22410** ile okunur.

### 3.3 Status ve text status (found)

`<status>` sonuç işleme: `code` 401 / 403 / 404 ile `type="fail"` = gizlilik nedeniyle gizli (dahili durum 2); diğer `fail` = hata (0); hatasız boş olmayan metin = ayarlı (1, `t` * 1000 = ayarlanma zamanı); hatasız boş ve text-status flag'i kapalı = yok (3). Durum adları inferred.

Flag **5839** açıkken bir `<text_status>` çocuğu durum 1 / 3'ü geçersiz kılar: metin = `text`, emoji = `<emoji content>` (yokken varsayılan ""), ayarlanma zamanı = `last_update_time` saniye, sona erme = ayarlanma zamanı + `ephemeral_duration_sec` (0'dan büyükse) (durum 3). Gizli bir status (durum 2), boş string değil, 401 / 403 / 404 içeren bir hata düğümüdür.

### 3.4 Picture, business, disappearing mode (found)

| Protokol | İstek ayrıntısı | Yanıt ayrıştırma |
|----------|-----------------|------------------|
| picture | `type="preview"` ve `size` yalnızca AB `AbstractC36291cD.A06` 0'dan büyükse (300 ile sınırlı); kullanıcı bazlı `id` yalnızca önbellekte id varsa | `id` (int, `<picture>` yoksa -1), `direct_path`, `hash` |
| business | `profile v` = `C35756Fe7.A00()` = AB 471 & 16380; kullanıcı bazlı `serial` / `tag` yalnızca yerel business satırından | `pn_jid` (LID kullanıcısının PN'sini doldurur ve LID-PN çiftini saklar), `verified_name`: `verified_level`, `host_storage`, `actual_actors`, `privacy_mode_ts`, düğüm baytları = sertifika |

---

## 4. Kişi sorgulama ve telefon numarası keşfi

### 4.1 Tekil sorgular (found, `C23638AId`)

| Metot | Tür | Oluşturur | Sonuç |
|-------|-----|-----------|-------|
| `A0E(userJid, type, n)` | yalnızca `INTERACTIVE_QUERY` veya `ADD_QUERY` | kullanıcı JID'i + contact, status, picture, business, disappearing_mode, lid, username; **5751** ise devices; **5839** ise text_status | `C43621q7` |
| `A0C` / `A0A(type, n, number)` | aynı iki tür | telefon numarası `<contact>` olarak; aynı küme (status yalnızca çağıran true geçirirse) | `Pair(result, user)` |
| `A0B(type, n, number)` ("Lightweight") | herhangi | telefon + contact, lid; **5751** ise devices | `Pair` |
| `A0D(type, numbers)` | herhangi | çok sayıda numara: contact, status, picture, business, disappearing_mode, lid; **5839** ise text_status | kullanıcı dizisi |
| `A0F(lid)` | `INTERACTIVE_QUERY` | `<user jid=LID/>` + `<contact/><username/>` | bir LID'in username'i |
| `A0G(username, key)` | `INTERACTIVE_QUERY` | username (+ key) `<contact>` olarak; ayrıca status, picture, business, disappearing_mode, lid, username yalnızca **33609** false ise, **5839** ise text_status | WA_USERNAME.md |

Korumalar (found): ağ kontrolü (`network_unavailable` sonucu), JID veya numaraya göre anahtarlanan uçuş-içi tekilleştirme map'leri (ikinci çağrı "skip too frequent query" döndürür, zaman penceresi yok), çağrı başına `sid`, 32000 ms'ye kadar bekleme, ardından timeout sonucu. AB **14565** kapalıyken, bilinen telefon numarasına sahip bir LID JID'i istek oluşturulmadan önce o numaraya yeniden yazılır (`AbstractC197018Zw.A0Y`; yön, ardından gelen `+` öneki adımından inferred).

### 4.2 Sonuç kodları (`C43621q7`, adlar kullanımdan inferred)

0 `A04` ağ yok; 1 `A08` atlandı (gönderilecek bir şey yok veya çok sık); 2 `A07` değişikliklerle başarı (kişi-kaldırma yolu); 3 `A06` başarı; 4 `A03` hata (boş sonuç, timeout, hata); 5 `A05` rate limit (sonuç hatası 429); 6 `A02` exception. `A01()` 1, 2, 3 için true döner. Contact protokolü hatası 429 ile boş bir `<list>` 5 verir, başka herhangi bir boş liste 4 verir.

### 4.3 Hangi özellikler telefon rehberine ulaşır (found)

| Yol | Giriş | Tür | Protokoller (`C21820s6`) |
|-----|-------|-----|--------------------------|
| Arka plan full sync (yalnızca birincil) | `C18230lP.A0F(reason)` | `BACKGROUND_FULL` | orgs hariç hepsi |
| Zorlanan full sync | `A01` yardımcı, periyodik job `RunnableC23953AUi` case 23 | `BACKGROUND_FULL`; companion: `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` | contact (`A0J`) veya side list (`A0K`); companion: contact / side list hariç hepsi (`A0D`) |
| Zorla yükleme, delta yükleme, indirme | `A07(reason)`, `A0G(reason)`, `A0C()` | `CONTACT_FORCE_UPLOAD`, `CONTACT_UPLOAD`, `CONTACT_DONWLOAD` | contact + lid (`A0G`) |
| Yerel kişiler değişti | `A0J(reason, jids)` | `NATIVE_CONTACT_DELTA` | orgs hariç hepsi |
| Gecikmeli kayıt sonrası sync | `A0L` (pref `registration_contact_sync_delayed`) | `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` | contact + lid |
| İlk gösterimde side contact | `A0E(contact)` | birincil: `INTERACTIVE_DELTA_SIDELIST`; companion: `INTERACTIVE_MULTI_PROTOCOL_QUERY` | orgs hariç hepsi / contact, side list, orgs hariç hepsi |

Protokol kümeleri (`C21820s6` sabitleri, found): `A0S` username; `A0G` contact + lid; `A0P` status; `A0Q` text status; `A0O` picture; `A0F` business; `A0H` devices; `A0E` business + devices; `A0N` payment; `A0I` disappearing mode; `A0L` lid; `A0M` orgs; `A0D` contact, side list, orgs hariç hepsi; `A0R` lid'siz `A0D`; `A0J` contact + `A0D` kümesi; `A0K` side list + `A0D` kümesi; `A0C` orgs hariç hepsi. Contact veya side list senkronize edildiğinde LID örtük olarak dahildir.

`C21830s7` (SyncRequest) seçenekleri JSON olarak saklar: `sync_is_urgent`, `sync_only_if_changed`, `sync_only_if_registered`, `sync_clear_whatsapp_sync_data`, `sync_should_retry` ve protokol başına bir `sync_<protocol>` boolean'ı (found); builder varsayılan retry int 5 (anlamı inferred).

### 4.4 Bildirim güdümlü sorgular (found)

Sunucu bir numara yerine bir hash iter; istemci onu çözümler ve bir sorgu çalıştırır.

| Bildirim handler'ı | Payload | Sync | Protokoller |
|--------------------|---------|------|-------------|
| `AnonymousClass145` (contact update), `add` | `pn` (varsayılan) veya `lid` türünde en fazla 2 hash çocuğu; yalnızca birincil | `NOTIFICATION_CONTACT` | orgs hariç hepsi |
| aynı, update | base64 hash | `NOTIFICATION_SIDELIST` | status, picture, lid, username, text_status |
| `C1S0` status bildirimi | attribute `hash` (base64) | `NOTIFICATION_SIDELIST` (reason `NOTIFICATION_STATUS`) | yalnızca status |
| `C1S0` picture bildirimi | attribute `hash` | `NOTIFICATION_SIDELIST` (reason `NOTIFICATION_PICTURE`) | yalnızca picture |
| `AnonymousClass142` business bildirimi (`hash` ile jid'siz kaldırma) | base64 hash | `NOTIFICATION_SIDELIST` (reason `NOTIFICATION_BUSINESS`) | business kümesi (sabit çözümlenmedi) |

Hash, yerel kullanıcılarla `digest(user + "WA_ADD_NOTIF")` değerinin bayt-önek bazında karşılaştırılmasıyla eşleşir (`AbstractC43461pq.A04`); digest algoritmasını çağıran seçer (izlenmedi). Sunucu tetiklemeli bir "forced sync" (`RunnableC23951AUg`, reason `SERVER_FORACE_SYNC`) `BACKGROUND_FULL` veya companion türünü çalıştırır.

### 4.5 MEX mutation'ları üzerinden kişi senkronizasyonu (found, USync değil)

Build'de yeni: Kotlin kişi senkronizasyonu (`com.whatsapp.contact.sync.kmp`, `.handler`) usync IQ yerine `w:mex` mutation'ları kullanır. Config `whatsapp-android-mex`, doc_id'ler persist-id asset'inden.

| İşlem | doc_id | Değişkenler (found) | Yanıt |
|-------|--------|---------------------|-------|
| `ContactsDeltaSyncMutation` | `28247314474869813` | `context` (`SEARCH`, `OSAB_IMPORT`, `EMAIL_IMPORT`, `QR_SCAN`), `primary_contacts_add[]`, `primary_contacts_remove[]` (`lid`, `modifier` = `BEST_EFFORT_DOWNGRADE_TO_WA_SIDE_CONTACT`, `normalized_phone`), `side_contacts_add[]` | `xwa2_contacts_delta_sync`: `results[]` {`client_cached_lid`, `failed`, `detail` (union: raw_pn / primary_normalized_phone / lid / phone_status; side_status; username_status; email_status; normalized_phone)}, `retry_after_seconds` |
| `PrimaryContactsFullSyncMutation` | `36963099086669113` | okunmadı | okunmadı |
| `SideContactsFullSyncMutation` | `26880700761604398` | `context`, `cursor`, `side_contacts[]` (`client_cached_lid`, `normalized_phone`) sayfalı | yukarıdaki gibi `results[]`, `retry_after_seconds` |

Bu yolu usync yoluna karşı neyin kapılandırdığı bulunamadı (unknown). `retry_after_seconds`, usync `backoff` değerinin MEX karşılığıdır.

---

## 5. Cihaz listesi senkronizasyonu, key index, ADV

### 5.1 İstek ve yanıt (found)

İstek: sorgu çocuğu `<devices version="2"/>`; kullanıcı başına `<devices device_hash="H" ts="T" expected_ts="E"/>`, yalnızca bir hash varsa gönderilir (`ts`, `expected_ts` yalnızca 0'dan büyükse ve `expected_ts` `ts` değerinden büyükse). Değerler yerel cihaz satırından gelir (`C15070fj.A07/A00/A04`).

Kullanıcı başına yanıt: `<devices>` ya bir `<error code text>` içerir (kullanıcı durum -1 alır, log "parseUser/partial error") ya da:

| Düğüm | Attribute'lar | Ayrıştırılan |
|-------|---------------|--------------|
| `<device-list><device .../>` | `id` (int), `key-index`, `is_hosted` | `DeviceJid(user, id)` -> key index; JID'in hosted durumu ile `is_hosted` arasındaki uyuşmazlık `invalid-hosted-flag` raporlar |
| `<key-index-list ts expected_ts>` | `ts` (saniye), `expected_ts` (varsayılan 0), içerik baytları | imzalı key-index listesi, ham olarak saklanır |

Sonuç düzeyi `<devices>` backoff'lu bir `<error>` taşıyabilir (bölüm 9). MEX rotası: `include_devices` ve `devices{hash, timestamp, expected_timestamp}`; atılan sonuçlar için istemci log etiketleri: `devices_dropped_status_error`, `devices_status_indeterminate`, `devices_hash_match_noop`, `devices_dropped_empty_without_hash`, `devices_dropped_no_jid`, `devices_dropped_stale_timestamp`, `devices_dropped_adv_proto_missing`, `devices_dropped_adv_verify_failed`, `devices_dropped_adv_data_update_failed`, `devices_outcome_unset`.

### 5.2 Güncelleme kontrolleri (found, `C51909N4g`, `C24230w2`)

| Kontrol | Davranış |
|---------|----------|
| key-index listesi boş | "update keyIndex is empty", güncelleme yok |
| yanıt `ts` değeri saklanandan eski | "timestamp is less than existing one", atılır |
| bayat expected-ts retry | yanıt ts saklanandan düşük, `expected_ts` saklanan ts'ye eşit ve saklanan değer pref `adv_last_device_job_ts` değerinden eski: bir usync fetch hatası loglar ve WAM olayı `wam_adv_expected_ts_unavailable` (`C49716Ltt`) yayar, true döner (çağıran etkisi izlenmedi) |
| yeni cihaz bilgisi | `C51909N4g.A00`, yeni ts saklananın en az kadar olduğunda saklanan expected ts'yi temizler; hesap türü cihaz kümesinden türetilir (`C9U.A01`) |

### 5.3 ADV imzalı key-index doğrulaması (found, `C24230w2.A07`, `A04`)

| Adım | Ayrıntı |
|------|---------|
| Ayrıştırma | key-index baytları -> `ADVSignedKeyIndexList` (`C25786BAu`): `details` (**1**), `account_signature` (**2**), `account_signature_key` (**3**, isteğe bağlı) |
| Public key | birincil cihaz kimliği yerel kimlik deposundan; proto `account_signature_key` taşıyorsa ve yerel anahtardan farklıysa o anahtar kullanılır ve `adv` etiketlenir; her iki anahtar da yoksa: uyarı "no primary identity" |
| İmza | seçilen anahtarla `{0x06, 0x02} || details` üzerinde `account_signature` doğrulanır (`AbstractC30195DBc.A08`); hata "fail to verify account signature" loglar ve bir WAM olayı yayar (`C55912St`, 1 = yerel anahtar, 2 = adv anahtarı) |
| Details | `details` -> `ADVKeyIndexList` (`BCB`): `raw_id` (**1**), `timestamp` (**2**), `current_index` (**3**), `valid_indexes` (**4**), `account_type` (**5**) |
| Timestamp eşleşmesi | `details.timestamp`, `ts` attribute'una eşit olmalı, aksi halde "advTimestampMismatch" + WAM olayı `C2TD`, sonuç reddedilir |
| Yaş | `ts`, `min(35, AB 730)` günden eskiyse (varsayılan 35) ve `valid_indexes` 1'den fazla girdi içeriyorsa: "advListTimestampInvalid", reddedilir |
| Raw id | `raw_id` saklanandan farklı: "incoming key-index not matching local state, resetting"; companion üzerindeki kendi hesap `device_self_invalid_index_list` loglar; diğer kullanıcılar: yeni liste ayrıştırılmadıysa `C15070fj.A0G(user, "adv_key_index_list_validation_failed")` (etkisi izlenmedi) |
| Filtreleme | `filterDeviceWithKeyIndexList` (`C24230w2.A08`) bir cihazı birincilse veya `key-index` değeri 0'dan büyük ve `valid_indexes` içinde listeliyse tutar; aksi halde bir WAM olayıyla atılır (`C55932Sv`, index 0 ise 1). Saklanan daha büyük bir index yalnızca uyarı üretir |

### 5.4 Cihaz sync job'ları (found)

`DeviceSyncManager.A03(jids, type)` `SyncDevicesJob` kuyruğa alır (zaten uçuşta olan kullanıcıları atlar; bekleyen kullanıcılar yeniden başlatmalardan pref `pending_users_to_sync_device` içinde sağ çıkar). `syncType` sync türünü seçer:

| `syncType` | Sync türü | Context | Çağrıldığı yer (found) |
|------------|-----------|---------|------------------------|
| 0 / varsayılan | `INTERACTIVE_MULTI_PROTOCOL_QUERY` | interactive | — |
| 1 | `MESSAGE_MULTI_PROTOCOL_QUERY` | message | `SyncDevicesAndSendInvisibleMessageJob` (grup gönderme yolu `C22300su`, grup boyutu AB 934 ile AB 1946 arasında, mesaj anahtarı başına bir job) |
| 2 | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | notification | kendi cihazlarının hesap senkronizasyonu (`C41431mS`) |
| 3 | `BACKGROUND_MULTI_PROTOCOL_QUERY` | background | ADV gönderen kontrolü başarısız olan gelen mesaj veya status (`DecryptMessageRunnable` / `StatusProcessingRunnable`, log `invalid adv sender`), ADV metadata uyuşmazlıkları (`C24230w2`), bekleyen kullanıcıların yeniden oynatılması |
| 4 | `VOIP_MULTI_PROTOCOL_QUERY` | voip | birincil olmayan cihaz için çağrı şifreleme kurulumu (`C1A`, log `voip/encryption/schedule usync`) |
| 5, 6 | `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY`, `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` | notification, message | izlenmedi |

Yalnızca devices isteklerinde `C21820s6.A0H` kullanılır. `handleADVMetadata` (`C24230w2.A0A`) ayrıca, gelen bir mesajın ADV metadata'sı yerel durumla çelişen bir hosted hesap türü bildirdiğinde (cihazlar önce temizlenir) veya saklanandan daha yeni bir timestamp bildirdiğinde tür-3 yenilemesini tetikler.

---

## 6. LID eşlemesi

| Mekanizma | Ayrıntı (found) |
|-----------|-----------------|
| `lid` protokolü | sorgu `<lid/>`; kullanıcı bazlı `<lid jid=known LID/>` yalnızca bir PN kullanıcısının zaten saklı bir LID'i varsa; yanıt `<lid val="LID"/>` kullanıcı sonucunda saklanır |
| Eşleme yazma | `N27.A03(users)`: LID = `new_jid` (LID türünde bir JID ise) yoksa `lid` sonucu yoksa kullanıcı `jid` (LID ise); PN = `pn_jid` yoksa kullanıcı `jid` (PN ise); çiftler tek bir batch'te LID-PN eşleme deposuna gider |
| Business `pn_jid` | PN'si olmayan bir LID kullanıcısı PN'yi `<business pn_jid>` içinden alır; çift saklanır |
| Side list | LID adresleme açıkken istek kullanıcıları `jid` = LID ve `pn_jid` = PN taşır (`C11940aM.A05`, `C11500Zc.A00` ile çözülür, flag id izlenmedi); fallback'ler `Sidelist: No LID provided`, `waContact_null`, `usernameLid_null` loglar |
| Eksik LID onarımı | `MissingLidHandler` (`C32M`): `requestSyncDevicesAndLidIfMissingLids`, harici bir giriş noktası devam etmeden önce lid protokollü bir `MESSAGE_MULTI_PROTOCOL_QUERY` için 32000 ms bekler |
| Eşleme gözlemcisi | `ContactJidMapObserver` (`C0ZA`): bir LID-PN çifti ortaya çıktığında ve kullanımdan kalkmış bir kişi mevcutsa, yedek kişiyi ekler ve reason `LID_REQUEST` ile bir `BACKGROUND_DELTA` kuyruğa alır |

Eksik LID neden önemli: yalnızca PN'si olan bir kişiye LID-öncelikli gönderimde adreslenemez; sorgu çifti tam senkronizasyon olmadan doldurur (çağrı noktalarından inferred).

---

## 7. Gizlilik zenginleştirme (tctoken, ortak grup)

`ProfilePrivacyEnrichmentFetcher` (`C223659jg.A00`, log etiketi `ContactSyncHelper.privacyEnrichment`) gönderimden önce istek listesi üzerinde çalışır. Her kullanıcı için şunları getirir: (a) zaman damgasıyla saklı gizlilik token'ı (`C14820fK.A0M`, `C14820fK.A04.A02()` değerinden eskiyse atılır), (b) geçerli token yoksa kullanıcıyla paylaşılan bir grup JID'i (`C197178aC.A04` / toplu arama, kendi LID'ini gerektirir). Sonuç `C197148a9{ token C9oI, commonGroup, flag }`.

| Çıktı | Klasik usync | MEX `UsyncQuery` |
|-------|--------------|------------------|
| token | `<user>` içinde `<tctoken>token bytes</tctoken>` çocuğu | `privacy_token{tctoken, timestamp}` |
| ortak grup | `<user>` üzerinde `common_gid="..."` attribute'u | `common_group` |

Yalnızca picture veya status isteyen isteklere (AB **9667**, varsayılan true), text status (**20798**, varsayılan false), devices (**29769**), contact (**29770**), lid (**29771**) isteyenlere uygulanır (9667 hariç flag'lerin varsayılanı false). Token veya ortak grup olmadan sunucu yine yanıt verebilir ancak picture veya status'u atlayabilir (inferred; sunucu kuralı unknown). Token düzenlemesi ve `cstoken` WA_TCTOKEN_CSTOKEN.md içindedir.

İlgili: `PRIVACY_TOKEN_REFRESH` (`C735439k`), yalnızca picture kümesi `A0O` ile 10 kullanıcılık batch'lerle `BACKGROUND_QUERY_PICTURES` çalıştırır (found); amacın token ilişkisini yenilemek olduğu reason adından inferred.

---

## 8. MEX `UsyncQuery` ve protokol yönlendirme

### 8.1 İşlem (found, `C229259vZ.A01`)

`w:mex` işlemi `UsyncQuery`, doc_id `38635300486116501` (persist-id asset), yanıt sınıfı `C2IQ`. Zarf WA_USERNAME.md 2.2'deki gibidir.

| Değişken | Kaynak |
|----------|--------|
| `query_input[]` | kullanıcı başına: JID, `client_known_username`, `about_status{dhash}`, `picture{id}`, `business{serial, tag}`, `devices{hash, timestamp, expected_timestamp}`, `privacy_token{tctoken, timestamp}`, `common_group` |
| `telemetry.context` | küçük harfli context string'i |
| `include_username`, `include_reachability`, `include_linked_profiles`, `include_lid`, `include_about_status`, `include_picture`, `include_biz`, `include_ddm`, `include_devices`, `include_orgs` | herhangi bir kullanıcı protokolü istediğinde set edilen boolean'lar |
| `picture_field_input` | `type` `IMAGE` veya `PREVIEW`, önizlemeler için `preview_px` |
| `business_input` | `include_profile`, `include_vname`, `profile_version` |

MEX üzerinden taşınmayanlar: contact ve text_status. Yalnızca MEX'e özgü: reachability, linked profiles, orgs, ddm (disappearing mode). Username ve lid dışındaki yanıt ayrıntıları (WA_USERNAME.md) okunmadı (unknown).

### 8.2 MEX ne zaman kullanılır (found, `C18580m0`)

1. AB **37780** (int, varsayılan 0) sıfır değilse: protokol bazlı yönlendirme. Üst 16 bit = klasik usync üzerinden yönlendirilen bit maskesi (`SMAX`), alt 16 bit = MEX üzerinden yönlendirilen maske; aksi halde `DROP`. Bitler (`M5H`): status 4, picture 8, business 16, devices 32, disappearing_mode 128, username 512, text_status 1024, orgs 2048. İstek düzeyi bitler 1 (contact), 2 (`C70582ym.A07`, büyük olasılıkla side list, inferred) ve 256 "identity" maskesi olarak taşınır. Seçilen rotanın taşıyamadığı bir protokol `DROP` yapılır: MEX üzerinde text_status, SMAX üzerinde orgs. Log satırı `ContactSyncHelper/read_route type=.. contacts=.. identity=..,.. failed=..`.
2. Aksi halde AB **33432** ile (varsayılan false): ana istek için klasik sorgu, ardından devices için bir "mex profile follow-up" (`..._mex_profile`); `requested_users`, `is_delta_sync` ile not edilen ve sonucu `success`, `partial_success`, `no_result`, `timeout`, `exception`, `interrupted` olan bir metrik işaretçisi ile.
3. Aksi halde `A0F` istek başına karar verir: istek contact veya text_status içeriyorsa MEX reddedilir ("cantUseMex"), business için AB **9732**, username için AB **8421** gerekir; geri kalanı MEX üzerinden gidebilir (`C229259vZ`), 128000 ms beklemeyle.

Bu build'in varsayılan durumu: 37780 = 0, 33432 = false, 9732 = false, 8421 = false; yani bir sunucu AB override'ı bunu değiştirmedikçe USync klasik stanza üzerinden çalışır.

---

## 9. Rate limit'ler, hatalar, backoff

### 9.1 Hata biçimleri (found)

| Yer | Biçim | Ayrıştıran |
|-----|-------|------------|
| iq hatası | `<iq type="error"><error code backoff/></iq>` | `Brt`: `code`, `backoff` saniye * 1000, 3600000 ms ile sınırlı (yoksa -1); `BIz(type, sid, code, backoffMs)` çağırır, future'ı null ile tamamlar |
| teslim hatası | transport callback | `Bog`: future `C216419Uc` ile başarısız olur; JID başına sync durumu sıfırlanır (`C502424l.A01`) |
| protokol hatası | `<result><PROTO><error code text backoff/></PROTO></result>` | `C18670m9.A01`: `backoff` saniye * 1000, varsayılan 7200 s, sınır 3600000 ms (1 sa); `connection/unisynciq/parse/<proto>/error` loglar |
| protokol başarısı | `<PROTO refresh="n"/>` | `refresh` saniye * 1000 |
| kullanıcı düzeyi kısmi | `<devices><error code text/></devices>` | durum -1, kullanıcı korunur |
| MEX hatası | GraphQL hatası, yol alanı `<proto>_info`, isteğe bağlı backoff string'i | `C229259vZ.A00`: backoff varsayılan **7200**, sınır 3600000, bu yolda * 1000 dönüşümü yok (birimler belirsiz, unknown) |
| username key | contact sonucunda `42901` (requestor) ve `42902` (requestee) kodları | `C23638AId.A0G`, bkz. WA_USERNAME.md |

İstemci mantığında görülen kodlar: `429` (rate limit: sync sonucu 5), `503` (global backoff), `42901`, `42902`.

### 9.2 Backoff deposu (found, prefs dosyası `contact_sync_prefs`, `C18800mM`)

| Key | Ne zaman yazılır | Değer |
|-----|------------------|-------|
| `contact_sync_backoff` | backoff'u 0'dan büyük herhangi bir iq / contact-protokol hatası (`X.0m7.BIz`, `AO4.BIz`) | şimdi + backoff ms |
| `delta_sync_backoff` | aynı, mode delta ve kod 429 | şimdi + backoff |
| `global_backoff_time` | aynı, kod 503 | şimdi + backoff |
| `sidelist_sync_backoff` | `ContactQuerySync` callback'i `AO2.BIz`, backoff'u 0'dan büyük **herhangi** bir hatada | şimdi + backoff; kod 503 ayrıca `global_backoff_time` set eder (key adı sync scope'una uymuyor; found) |
| `contact_full_sync_wait`, `status_full_sync_wait`, `sidelist_full_sync_wait` | protokol sonucunun `refresh` attribute'u | ms; set edilmemişse = 86400000 (24 sa) |
| `status_`, `picture_`, `business_`, `devices_`, `disappearing_mode_`, `lid_`, `username_`, `text_status_`, `reachability_` `sync_backoff` | `BJ0` içinde protokol bazlı sonuç hata backoff'u | şimdi + backoff |
| `last_contact_full_sync`, `last_status_full_sync`, `last_sidelist_full_sync` | full sync tamamlanması | timestamp |

`C18800mM.A02()` contact, sidelist, status, picture, business, devices, delta, disappearing_mode, lid, reachability ve global key'lerini -1'e sıfırlar; `username_sync_backoff` ve `text_status_sync_backoff` bu listede değildir (found).

String aramasıyla bulunan okuyucular: `reachability_sync_backoff` (`C18580m0`), `text_status_sync_backoff` (`C3MA`), üç `*_full_sync_wait` key'i ve `last_*_full_sync` (periyodik job: `wait - now + last` en fazla 1800000 ms, 30 dk olduğunda full sync zamanı gelmiştir). `contact_sync_backoff`, `delta_sync_backoff`, `global_backoff_time` veya diğer protokol bazlı key'lerin okuyucusu bulunamadı (kontrolün key'i dinamik oluşturup oluşturmadığı unknown).

### 9.3 Yerel limitler (found)

Uçuş-içi tekilleştirme: JID başına bir `querySyncJid`, numara başına bir telefon sorgusu. Timeout'lar: tekil sorgu 32000 ms, batch 128000 ms, `C18230lP.A00` callback beklemesi için 180 sn (`C11980aQ.A09` ise sınırsız). Backoff sınırı 3600000 ms. Gizlilik token'ı yenileme batch'leri 10 kullanıcı. Sunucu tarafı hesap ve numara başına sorgu limitleri unknown.

---

## 10. USync'i ne tetikler

Reason = `EnumC21800s4` değeri (istemci etiketi, zamanlama ve metrikler için kullanılır). Tür = sync türü.

| İstemci özelliği | Reason | Tür | Protokoller |
|------------------|--------|-----|-------------|
| Kayıt tamamlandı | `REGISTRATION_FULL` (`C25100xS`, `CJ8`) | `REGISTRATION_FULL` (kod 0) | contact kümesi (companion varyantı izlenmedi) |
| Kişi onboarding | `NC_ONBOARDING` | `A0G` delta yükleme (`CONTACT_UPLOAD`) | contact + lid |
| Cihaz rehberi değişti (yalnızca birincil) | `DEVICE_ADDRESS_BOOK_CHANGE` | acil değişiklik delta'sı (`C18230lP.A02`) | izlenmedi |
| Periyodik ve zorlanan full sync | `PERIODIC_FORCE_SYNC`, `FORCE_SYNC` | `BACKGROUND_FULL` | contact / side list |
| Kişi seçici açık | `CONTACT_PICKER_FULL_SYNC`, `CONTACT_PICKER_USYNC_RETRY` | `INTERACTIVE_FULL` | izlenmedi |
| Kişi ekleme, numarayla yeni sohbet, deep link, kişisiz sohbet | `*_CONTACT_ADD` reason'ları mevcut; sorgu yoluna bağlı değil | `ADD_QUERY` (`C9AA`) / `INTERACTIVE_QUERY` (`C9AQ`, `C9AY`, `AWR`, `A1P`) | bkz. 4.1 |
| Kayıtlı olmayan bir kullanıcı veya business ile sohbet açma | `CONVERSATION_SIDE_CONTACT`, `SIDELIST_REQUEST` | AB **20988** (varsayılan true) ise telefon sorgusu (`INTERACTIVE_QUERY`), değilse `INTERACTIVE_DELTA_SIDELIST` | bkz. 4.1 / 4.3 |
| Yayın listesine mesaj gönderme | `LID_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | lid |
| Grup mesajı gönderme (boyut AB 934..1946 içinde) | `DEVICE_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | devices |
| ADV gönderen kontrolü başarısız gelen mesaj, ADV metadata uyuşmazlığı | `DEVICE_REQUEST` | `BACKGROUND_MULTI_PROTOCOL_QUERY` | devices |
| Çağrı şifreleme kurulumu | `DEVICE_REQUEST` | `VOIP_MULTI_PROTOCOL_QUERY` | devices |
| Kendi hesap senkronizasyonu | `DEVICE_REQUEST` | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | devices |
| Sunucu push'u: contact, status, picture, business, username değişikliği | `NOTIFICATION_*`, `USERNAME_UPDATE_NOTIFICATION` | `NOTIFICATION_CONTACT` / `NOTIFICATION_SIDELIST` | bildirime göre |
| Disappearing-mode ve text-status yenileme | `DM_FORCE_REFRESH`, `TEXT_STATUS_FORCE_REFRESH` | `BACKGROUND_MULTI_PROTOCOL_QUERY` (text status ayrıca `BACKGROUND_FULL`) | disappearing_mode / text_status |
| Hesap değiştirme | `ACCOUNT_SWITCH_REFRESH` | `BACKGROUND_FULL` | izlenmedi |
| Gizlilik token'ı yenileme | `PRIVACY_TOKEN_REFRESH` | `BACKGROUND_QUERY_PICTURES` | picture |
| LID-PN eşleme değişikliği | `LID_REQUEST` | `BACKGROUND_DELTA` | orgs hariç hepsi |
| Business sohbeti (mesaj eklendi, çağrı) | `BUSINESS_CONTACT_CHAT` (`C0LX`, `RunnableC23932ATn`) | `BACKGROUND_MULTI_PROTOCOL_QUERY` / `VOIP_MULTI_PROTOCOL_QUERY` | izlenmedi |

---

## 11. Feature flag'ler

Çağrı noktalarında okunduğu haliyle AB-prop id'leri; varsayılanlar bu build'in config tablolarından. Flag ID'leri kalın.

| Flag | Tür | Varsayılan | Kontrol ettiği |
|------|-----|------------|----------------|
| **5751** | bool | false | contact ve telefon numarası sorgularında devices iste |
| **5839** | bool | false | text_status protokolü (istek ve ayrıştırma) |
| **9667** | bool | true | picture / status istekleri için gizlilik zenginleştirme |
| **20798** | bool | false | text_status için gizlilik zenginleştirme |
| **29769**, **29770**, **29771** | bool | false | devices, contact, lid istekleri için gizlilik zenginleştirme |
| **9732** | bool | false | MEX üzerinden business |
| **8421** | bool | false | MEX üzerinden username |
| **37780** | int | 0 | protokol yönlendirme maskeleri (üst 16 SMAX, alt 16 MEX) |
| **33432** | bool | false | klasik sorgu + MEX profil follow-up ayrımı |
| **12402** | bool | false | username `contact` üzerinde `lid` ve `pin` |
| **14565** | bool | false | contact üzerinde `addressing_mode="lid"`, yalnızca rakamlardan oluşan PN metni |
| **26739** | bool | false | telefon numaralarında `+` öneki |
| **471** | int | 1140 | business `profile v` (0x3FFC ile maskelenir) |
| **730** | int | 35 | ADV key-index azami yaşı gün olarak (35 ile sınırlı) |
| **31261** | bool | false | kullanıcı başına bilinen `@username` ekler (`C223639je`) |
| **33609** | bool | true | true iken key-entry sorgusu `<username/>` içermez |
| **20988** | bool | true | kayıtlı olmayan business sohbetinde side-list sync yerine telefon sorgusu |

---

## 12. Baileys (`baron-baileys-v2`, `src/WAUSync` ve `Socket/socket.js` ile karşılaştırıldı)

| Konu | Baileys | Android 2.26.41.6 |
|------|---------|-------------------|
| zarf | `iq to=s.whatsapp.net type=get xmlns=usync` + `usync{context, mode, sid, last="true", index="0"}` | aynı attribute'lar; `to` örtük |
| mode'lar | `query` (varsayılan), `delta` | ayrıca `full`, `download` |
| context'ler | `interactive` (varsayılan), `background`, `message`; `voip` backoff kuralında görünür | ayrıca `registration`, `notification`, `add`, `voip`, `metadata`, `snapshot`, `wamo` |
| protokoller | sorgu çocuğu olarak `bot`, `feature`, `sidelist` ekler | `bot` / `feature` çocuğu yok; sidelist kullanıcıları `<side_list>` içine girer |
| contact | `<contact>phone</contact>`, `pin` / `lid` ile username, `type` | `+` ile telefon, `type="delete"`, username |
| status gizli | `<status>` üzerinde `code="401"` `''` verir | 401 / 403 / 404 ile `type="fail"` |
| gizlilik kanıtı | `<tctoken>` yalnızca status protokolü altında, kullanıcı token taşıyorsa | picture / status / diğerleri için `<tctoken>` ve `common_gid` |
| backoff | `error backoff` saniye * 1000, sınırsız | 1 sa ile sınırlı |

| Belirti (inferred) | Neden | Çözüm |
|--------------------|-------|-------|
| rehberde olmayanlar için picture / status eksik | tctoken yok, `common_gid` yok | kullanıcı başına saklı `<tctoken>` veya paylaşılan bir grup JID'i ekle |
| cihaz listesi reddedildi | bölüm 5.3'teki key-index `ts` / `raw_id` kontrolleri | `ts` değerinin imzalı `details.timestamp` değerine eşit olduğunu doğrula |
| backoff yok sayıldı | Baileys sunucu değerini sınırsız kullanır | 1 sa ile sınırla, protokol bazında bekle |

---

## 13. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| `ContactQuerySync/querySyncJid: rate-limit-error` | contact sonuç hatası 429, boş liste | dönen `backoff` kadar bekle, sorgu hızını düşür |
| `connection/unisynciq/parse/<proto>/error` | protokol bazlı hata düğümü | `backoff` değerini yalnızca o protokol için sakla |
| `handleSyncContactError ... code=503` | sunucu aşırı yükü | global backoff, sonra yeniden dene |
| `sidelist-jid-absent-from-response` | sunucu istenen bir side-list kullanıcısını atladı | istemci döngüyü önlemek için kullanıcıyı senkronize işaretler |
| `contactsyncDevicesupdater/update/verifyADVSignedKeyIndexList fail` | imza, proto veya timestamp kontrolü başarısız | cihaz satırı güncellenmedi, yenileme kuyruğa alındı |

---

## 14. Temel ayrımlar

| Karıştırma | Ayrıntı |
|------------|---------|
| sync türü vs reason | tür (`EnumC21760rz`) mode, context, scope seçer; reason (`EnumC21800s4`) yalnızca zamanlama ve metrikler için bir etikettir |
| `list` vs `side_list` | rehber kullanıcıları vs rehber dışı kullanıcılar (side contact'lar) |
| usync vs MEX `UsyncQuery` vs MEX kişi mutation'ları | ilgili veri için üç transport; yönlendirme flag'leri 8.2 ve 4.5'te |
| `<devices>` sonucu vs imzalı key index | imzalı liste doğrulanana kadar cihaz listesine güvenilmez (5.3) |
| `refresh` vs `backoff` | `refresh` = iyi bir sonucun ne kadar süre yeniden kullanılabileceği, `backoff` = bir hatadan sonra ne kadar uzak durulacağı |

---

## 15. Tam akış

```
[Feature]         [ContactSyncMethods]            [UniSync builder / MEX]                [Server]
  │ trigger (10)         │                                  │                               │
  ▼                      ▼                                  │                               │
 reason + type ──► SyncRequest (protocol set, users)        │                               │
                         │ enrich: tctoken / common_gid (7) │                               │
                         │ route per protocol (8)           ▼                               │
                         └──► classic: <iq xmlns=usync><usync sid index last mode context> ─►│
                         └──► MEX: w:mex UsyncQuery {query_input, include_*} ───────────────►│
                                                            │◄── <usync><result> per protocol│
                                                            │     <list> <side_list>         │
                                                            ▼                               │
                    parse: contact in/out, status, picture, business,                       │
                           devices + key-index-list, lid val, username                      │
                                  │                                                         │
        ┌─────────────────────────┼─────────────────────────┐                               │
        ▼                         ▼                         ▼                               │
 devices: verify ADV sig,   LID/PN pairs ──► mapping   result errors: 429 / 503 / backoff   │
 ts, raw_id, valid_indexes  store (N27.A03)            ──► prefs; refresh ──► full_sync_wait │
        │ ok                                                                                │
        ▼                                                                                   │
 device rows updated ──► message fan-out, call setup, side-list chats use the new data      │
```

---

## 16. Bilinmeyenler

| Konu | Neden |
|------|-------|
| iq'nun `to` attribute'u | gönderen tarafından eklenir; gönderen izlenmedi |
| `C10140Tq.A0A` (registration) ile `A06` farkı | izlenmedi |
| Sorgu hızı, numara başına limitler, bir isteyenin hangi protokolleri okuyabileceği için sunucu kuralları | istemci yalnızca hata kodlarını görür |
| `contact_sync_backoff`, `global_backoff_time`, `delta_sync_backoff` okuyucuları | string okuyucu bulunamadı |
| MEX backoff birimleri | `C229259vZ.A00` içinde `* 1000` yok |
| Üretimde hangi rotanın kazandığı | bu build'de tüm rota flag'leri varsayılan olarak kapalı; sunucu AB değerleri unknown |
| Gerçek trafik | yalnızca statik analiz |
