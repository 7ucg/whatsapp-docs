<!-- src-sha1: 73855f4f8148d9b0ef853f43cef4adbe0cb996a5 -->
# WhatsApp Kullanıcı Adı — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Kullanıcı adı kontrolü / ayarlama / rezervasyon / silme, kullanıcı adı key'i (PIN), LID ilişkisi, gizlilik ve görünürlük, w:mex GraphQL operasyonları (doc_id'ler, değişkenler, yanıtlar), bildirimler, USync araması, doğrulama kuralları, feature flag'leri, Baileys notları

---

## 1. Bir kullanıcı adı teknik olarak nedir

Bir kullanıcı adı, bir kişinin telefon numarasını açığa çıkarmadan erişilebilir olmasını sağlamak için bir hesaba bağlı sunucu-tarafı bir handle'dır. Tüm ifadeler decompile edilmiş APK'nın statik analizidir. Kademe: **found** = kod veya asset'lerde okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi.

Özellik üç katman üzerine inşa edilmiştir:

| Katman | Transport | Kullanımı |
|-------|-----------|----------|
| Kendi kendini yönetme | `w:mex` IQ, persisted GraphQL (config `whatsapp-android-mex`) | kontrol, ayarlama / rezervasyon / silme, alma, key (PIN) ayarlama / silme, çoklu-kontrol |
| Başkalarının araması | USync (`xmlns="usync"`) ve MEX `UsyncQuery` varyantı | `@username`'i (+ key) bir LID'e çözme, bilinen bir JID'in kullanıcı adını çekme |
| Push | MEX bildirimleri | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Çapraz-cihaz | app-state senkronizasyonu (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (`username`'i taşır) |

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| Kullanıcı adı yöneticisi | `C122815Lj` | `UsernameGet`, `UsernameSet` çağrıları, yerel durum güncellemesi, rate-limit hook'u |
| Uygunluk kontrolü | `C67402tT` | `UsernameCheck` çağrısı + yanıt eşlemesi |
| Çoklu kontrol | `C76333Kg` | `UsernameCheckMulti`, 10'luk parçalar |
| Key API'si | `MexUsernamePinProtocolApi` | `UsernamePinSet` (key ayarlama / silme) |
| Yerel durum / tercihler | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| Durum enum'u | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Uygunluk modu | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Rate-limit deposu | `C67942uO` | 429 / 503 / 529 sonrası backoff |
| Yerel validator | `C82003fB.A04`, `C1187754z` | uzunluk, karakter kümesi, nokta kuralları, regex |
| Key validator'u | `C1176550d` (+ `AbstractC111284pZ`) | key formatı |
| Key giriş VM'i | `UsernamePinEntryViewModel` | yabancı bir kullanıcı adı için key gönderimi |
| USync istemcisi | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | klasik usync stanza builder'ı/parser'ı |
| MEX USync | `C229259vZ`, `O0F` | `include_username` ile `UsyncQuery` |
| Bildirim handler'ları | `C49822Lvi`, `C49821Lvh`, `AbstractC20380p4`'te anonim `X.2YG` | ayarlama / silme / güncelleme |

İsimlendirme: PIN'in kullanıcıya-görünen adı **kullanıcı adı key'idir** (string'ler "Username key", "Add a username key to control who can contact you"). Wire ve kod `pin` der.

---

## 2. MEX operasyonları (doc_id'ler)

### 2.1 doc_id'lerin yaşadığı yer

doc_id'ler `java_src`'de literal değildir. İstemci, operasyon adını (`"UsernameSet"`, ...) `"whatsapp-android-mex"` config adıyla gönderir (found, `C16880is`). Sayısal id, `assets/whatsapp-android-mex_client_persist_ids.json`'dan okunur: `EnumC17010j7.WHATSAPP_ANDROID_MEX`, o dosyaya eşlenir, `C17040jA.CMg(op)`, `doc_id` alanını döndürür, `AGb(op)` `client_doc_id` alanını (found). İkisinden hangisinin `query_id` attribute'unu doldurduğu sonuna kadar izlenmedi (unknown); 2.26.26.4'teki önceki yakalamalar `query_id`'nin `doc_id`'ye eşit olduğunu gösteriyor.

Aşağıdaki doc_id'ler 2.26.41.6'nın asset'inde **found**:

| Operasyon | doc_id | Tip | Çağrı noktası | Yanıt sınıfı |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | bulunamadı | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Notlar:
- `UsernameGetRecommendationsQuery`: isim sadece asset JSON'ında geçiyor. `java_src`'de hiçbir sınıf ona string ile referans vermiyor (found). Değişkenler ve yanıt unknown.
- Üç bildirim adının (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) persist-id asset'inde girdisi yok. Bunlar bildirim tipleridir, istekler değil (bkz 7).
- Asset her operasyon için `operation_name_hash`, `operation_text_hash` ve `client_doc_id`'ye sahiptir. Örnek `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Zarf

`C19370nI` / `C19310nC`'de inşa edilir (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Alan | Kural (kod) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | her operasyon için `get`, mutation'lar dahil |
| `query_id` attribute'u | sadece 1 ile 20 karakter arasındaysa ayarlanır |
| gövde | JSON `{"queryId": ..., "variables": {...}}`, 1 ile 8448000 byte arası |
| null değişkenler | `C16770ig.A03(k, null)` ve `A02(k, null)`, key'i atlar, bu yüzden eksik bir değer key'in gönderilmediği anlamına gelir |

Canlı oturumların wire stanza'ları burada yeniden üretilmemiştir; bu build sadece statik olarak analiz edilmiştir.

---

## 3. Operasyonlar detaylı olarak

### 3.1 UsernameCheck

Değişkenler (found, `C67402tT.A00`):

| Değişken | Tip | Koşul |
|----------|------|-----------|
| `username` | string | her zaman |
| `include_suggestions` | bool | her zaman (UI, typed-check yolunda `C64H` durumu 21'de `false` geçirir) |
| `source` | string | sadece null-olmayansa |
| `session_id` | string | sadece null-olmayansa |

`source` eşlemesi (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, diğer -> null (gönderilmez).

Yanıt yolu (found, `C77183Np` varsayılan dalı): `data.xwa2_username_check`

| Alan | Tip | Kullanım |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | sadece `INVALID` ise okunur |
| `rejection_reasons` | `C4G8` listesi | sadece `INVALID` ise okunur |
| `suggestions_eligible` | bool | alan null olduğunda `true`'ya varsayılan |

`C4G8` değerleri (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Eşleme: `SUCCESS` -> `C76283Kb` (mevcut); `INVALID` -> `C76303Kd` (mevcut değil, öneriler + nedenler taşır); `UNSET` -> hiçbir dal bir sonuç atamaz (callback önceki/null değişkeni alır; davranış unknown). Aktif yerel backoff -> `C76293Kc` (tercihlerden rate-limit koduyla hata, bkz 5.3); isteğin kendisinin başarısızlık callback'i okunmadı.

Reddetme nedenleri, hesap-bağlama metnini tetikler ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). `C82003fB`'de `UNSET` dışındaki herhangi bir neden, 40601 kodlu yerel hata yolunu tetikler (`A08(40601L)`); boş veya sadece-`UNSET` bir liste "Username isn't allowed." gösterir. Döngü etrafındaki tam kontrol akışı sadece kısmen decompile edilmiştir (inferred).

### 3.2 UsernameCheckMulti

| Değişken | Tip | Notlar |
|----------|------|-------|
| `usernames` | **list<string>** | `A00.A0B("usernames", list)` üzerinden dizi; doc_id kataloğu bunu `str` olarak tipler, kod bir liste gönderir |

Toplu işleme (`C76333Kg.AG5`): liste ilk 10 ve kalan olarak bölünür; kalan, flag **29327**'nin (varsayılan 60, birim çözülmemiş) gecikmesinden sonra işlenir. Boş liste, bir istek yapmadan boş bir harita döndürür.

Yanıt yolu `data.xwa2_username_check_multi.results[]` (found): her öğenin `username`'i ve `response.result`'u vardır (aynı `EnumC59782gh`). Eşleme: `SUCCESS` -> mevcut, `INVALID` -> mevcut değil (öneri yok, `suggestions_eligible=false`), başka herhangi bir şey -> hata. Sonuçta eksik olan isimler hata olarak işaretlenir.

Tüketici: `UsernameAvailabilityCache`, isim-başına `EnumC59192fk`'yı (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) saklar. Amacı (Facebook / Instagram kullanıcı adı önerileri için prefetch, string `foa_username_prefetch_cache`) inferred'dir.

### 3.3 UsernameSet (oluşturma / değiştirme / rezervasyon / silme)

Değişkenler (found, `C122815Lj.A00`):

| Değişken | Tip | Koşul |
|----------|------|-----------|
| `username` | string | null olduğunda atlanır (**silme**) |
| `reserved` | bool | her zaman gönderilir |
| `session_id` | string | sadece boş-olmayansa (`C1YW.A08`) |
| `source` | string | sadece source int'i null-olmayansa (bkz 3.1) |
| `pin` | string | sadece null-olmayansa |

`reserved` hesaplanır, sabit değildir (found). Argüman `z` (force) = true, `false` verir. Aksi halde: mevcut durum `ACTIVATED` veya `CREATED`, `false` verir; mevcut durum `RESERVED` veya uygunluk modu `RESERVATION`, `true` verir; diğer tüm durumlar `false` verir. Yani `reserved:true`, sadece rezervasyon modundaki veya zaten bir rezervasyon tutan hesaplar için gönderilir.

Silme, aynı operasyonun bir modudur: `username == null` -> log tag'i `delete`, aksi halde `set` (key için `MexUsernamePinProtocolApi`'de de). Null bir kullanıcı adıyla `username` key'i değişkenlerde yoktur (found).

İstemci-tarafı koruma: göndermeden önce, rate-limit deposu aktif bir backoff bildirirse, çağrı yerel olarak `username_creation_rate_limit_error_code` ile ve "rate limit expiration time not reached" metniyle başarısız olur (found, `C122815Lj.A03`).

Başarı işleme (`C122815Lj.A01`, found):

| Koşul | Yazılan yerel durum (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| kullanıcı adı null veya boş | `UNSET`, key tercihi temizlenir |
| `reserved` doğruydu | `RESERVED` |
| etkinleştirme flag'i | `ACTIVATED` |
| aksi halde | durum `ACTIVATED` idiyse ve ad saklanmış adla eşleşiyorsa `ACTIVATED`, aksi halde `CREATED` |
| `source` int'i 1 veya 2 | pref `username_set_via_account_linking` = (int == 2) |
| `pin` gönderildi | pref `username_pin` güncellenir |
| teen flag'i | pref `is_teen_account` = true |

Pref yazımı `Voip.REJECT_REASON_DECLINED`'dır, bu bu build'de boş string'dir `""` (found).

Hata işleme (`C138725uA` durumu 2):

| HTTP-benzeri kod | İstemci eylemi |
|----------------|---------------|
| 429, 503, 529 | backoff saklanır (5.3) |
| 304 | başarı olarak ele alınır ("not modified"), yerel durum hâlâ güncellenir |
| bağlantı yok (`C213639Bb`) | `C4BO` "no network" sonucu |
| diğer | `C4BN(code, message)` |

### 3.4 UsernameGet

Değişkenler: yok (çağrı boş bir değişken kümesi inşa eder, found, `C122815Lj.A02`). `@Deprecated` olarak işaretlenmiş, bir suspend varyantıyla değiştirilmiş.

Yanıt (found, `C138815uJ` durumu 34): `data.xwa2_username_get.username_info`

| Alan | Kullanım |
|-------|-----|
| `username` | saklanır; eksikse boş string |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **key, açık olarak döndürülür ve `username_pin` tercihinde saklanır**; eksikse boş string |

Durum eşlemesi: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> saklanan kullanıcı adı döndürülenle eşleşiyorsa ve yerel durum `RESERVED` veya `ACTIVATED` idiyse `ACTIVATED`, aksi halde `CREATED`; null durum veya null `username_info` -> `UNSET`.

Sunucudan hata durumu 404, yerel kullanıcı adını, key'i ve durumu temizler (log `clearSelfUsernameData NOT_FOUND`).

Çağrının bir heartbeat olarak kullanılıp kullanılmadığı unknown'dır; eski "polling heartbeat" notu bu build'in kodu tarafından desteklenmiyor.

### 3.5 UsernamePinSet (kullanıcı adı key'i)

Değişkenler (found): `pin` (string), null olduğunda atlanır.

| Eylem | Değişkenler |
|--------|-----------|
| key ayarlama | `{"pin": "<key>"}` |
| key silme | `{}` (`A02`, `A00(null)`'u çağırır) |

İkisi için de operasyon adı `UsernamePinSet`'tir; ayrı bir doğrulama operasyonu yoktur. Yabancı bir key'in doğrulaması USync'te yapılır (4). Bağlı değilse: istek yapmadan `C213639Bb("UsernamePinSet")` döndürür.

Key, `UsernameSet`'e de (`pin` değişkeni) binebilir. `C81793ej.A0x`, bir kullanıcı adı yerel olarak zaten saklanmışken (`A00 != null`) mevcut kullanıcı adı ve yeni `pin` ile `UsernameSet`'i kullanır, aksi halde `UsernamePinSet`'i kullanır (found).

Yanıt sınıfı `C48557LJz`'nin okunan dosyalarda alan erişimi yok; yanıt şekli unknown'dır.

---

## 4. Diğer kullanıcıların araması

### 4.1 Klasik USync, kullanıcı adıyla (key akışı)

`C18670m9.A06`'da inşa edilir (jadx bu metodda başarısız oldu, smali'den okundu `X/0m9.smali`). `C222649hm` istek girdisi başına: alan `A0C` = kullanıcı adı, `A0D` = key, `A05` = LID.

Kişi çocuğunun attribute'ları (smali'de found): `username` her zaman; `lid`, bir LID yerel olarak bilindiğinde; `pin`, bir key ayarlıysa. Ekstra attribute'lar flag **12402** (varsayılan `false`) tarafından gated'dir: flag kapalıyken, sadece `username` yazılır (found). Node adı `contact`, çocuk `contact`'ı ve onun `username` attribute'unu okuyan yanıt parser'ından inferred'dir (`C18670m9` satır ~969-975).

```xml
<iq xmlns="usync" to="[server]" type="get">
  <usync mode="query" context="interactive" sid="..." index="0" last="true">
    <list>
      <user><contact username="name" lid="LID" pin="KEY"/></user>
    </list>
    <query><contact/> ... </query>
  </usync>
</iq>
```

Giriş noktası: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), `submitPinForUsername` tarafından çağrılır. Senkronizasyon tipi `EnumC21760rz.A0J`, timeout 32000 ms. Attribute kümesi `contact`, `pin`, `username`, `AbstractC40921lc`'nin log-redaction kümelerinde yer alır (found).

Yerel ön-çözme: `A0M.Aol(username)`, `lid_display_name` tablosunda `UPPER(username) = UPPER(?)` olan `lid_row_id`'yi arar, en yeni satır önce (found, `C1S0`). LID, bilindiğinde `lid` attribute'una girer.

### 4.2 Sonuç değerlendirmesi (key girişi)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Sonuç | Koşul |
|---------|---------|
| doğru key | sonuç `UserJid` bir LID'dir (`C14080dr`) |
| yanlış key | sonuçta LID yok: log `[un-pin] incorrect PIN`, hata metni "Wrong key entered" |
| ağ yok | `C9qA` kodu 1 |
| genel altyapı hatası | `C9qA` kodu 2 |
| istek-yapan rate limiti | `C225769os.A01` doğru: "Too many attempts made. Try later." |
| istenen rate limiti | `C225769os.A00` doğru: "This account can't be reached with their key right now..." |

İstemci-tarafı cache'lenmiş rate-limit kontrolü, flag **16033** açık ve JSON config **21995**'in `enable_key_rate_limit`'i doğru (varsayılan doğru) olduğunda önce çalışır: `C30P.A00`, kendi LID'ine ve hedef kullanıcı adına karşı. Kullanıcı adından `@` çıkarılır (`C0CX.A0i(username, '@')`).

Başarıda sonuç bir **LID**'dir, sohbet daha sonra LID'e adreslenir (`C14080dr` kontrolünden inferred; sohbet-açma adımı izlenmedi).

### 4.3 Bilinen bir LID'nin kullanıcı adını getirme

`C23638AId` (satır ~600-650), `<list><user jid="LID"/></list><query><contact/><username/></query>` ile bir usync inşa eder, mod/context `EnumC21760rz.A0J`'den (found). Parser, `username`'i `<usync>` sonucunun bir çocuğu olarak okur (`C18670m9` satır 586, sadece istek onu talep ettiyse).

### 4.4 MEX USync (`UsyncQuery`)

`C229259vZ.A01`, `UsyncQuery`'yi (yukarıdaki doc_id) inşa eder. İlgili parçalar (found):

| Değişken | Kullanım |
|----------|-----|
| `query_input[]` | kullanıcı başına bir girdi: JID (`C493020r.A0C`), opsiyonel `client_known_username` (sadece kullanıcı adı istendiğinde ve boş-olmayansa) |
| `include_username` | bool, herhangi bir girdi kullanıcı adını istediğinde ayarlanır |
| `include_lid` | bool, `lid_info` ister |
| `telemetry.context` | küçük-harfli USync context'i |

Kullanıcı-başına yanıt: `jid`, `username_info`, `lid_info` (`O0F`). `username_info`, tip hash'ine göre polimorfiktir: `username`'i tutan bir değer tipi, veya `EnumC216389Tz`'nin `status`'una sahip bir durum tipi: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED`, "username not allowed to be queried" olarak loglanır ve saklanan kullanıcı adını temizler; `NO_CHANGE` onu tutar. `lid_info.lid_jid`, LID'i taşır.

Gate: `ContactSyncHelper`, bir kullanıcı adı istendiğinde flag **8421** açık olmadığı sürece "cantUseMex as username ab prop is off" logu ile MEX yolunu reddeder (found; varsayılan `false`).

---

## 5. Doğrulama, limitler, hatalar

### 5.1 Kullanıcı adı formatı (yerel)

Validator `C82003fB.A04` (found), bu sırayla kontrol eder:

| Sıra | Kontrol | Hata id'si (`C02U`) | Mesaj string'i |
|-------|-------|-------------------|----------------|
| 1 | her karakter `[A-Za-z0-9_.]` içinde | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | uzunluk >= min (flag **20494**, varsayılan 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | uzunluk <= maks (flag **20459**, varsayılan 35) | 1 | aynı string |
| 4 | öncü `.` yok, sonlanan `.` yok, `..` yok | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | en az bir ASCII harf | 4 | "Choose a username with at least one letter" |
| 6 | regex (aşağıda) | geçer veya 2 ile başarısız olur | yok |

Regex, `C1187754z.A02()` tarafından inşa edilir (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

Case validator tarafından normalize edilmez; yerel arama `Aol`, `UPPER()` ile karşılaştırır, bu yüzden eşleştirme yerel olarak case-insensitive'dır (found). Sunucunun isimleri case-insensitive olarak ele alıp almadığı unknown'dır. Öncü alt çizgi regex tarafından izin verilir; UI metni "start with a letter" der, bu regex'ten daha katıdır (found, uyuşmazlık).

UI ayrıca web linklerini reddeder: "Enter only your username, not a web link" (string mevcut, kontrol izlenmedi).

### 5.2 Kullanıcı adı key formatı

`C1176550d.A00` (found): flag **34350** bir regex string'idir, varsayılan `^([0-9]{4}|[A-Z0-9]{6})$`. Flag string'i boşsa, fallback tam olarak dört rakamdır. Geçersiz regex `[un-pin] invalid username_key_regex`'i loglar ve her şeyi kabul eder. Uzunluk sınırları flag'leri **34347** (min, 4) ve **34348** (maks, 6), sadece `UsernamePinEntryViewModel.A0w`'deki hata mesajı yolunu besler. Sunucu-tarafı kurallar unknown'dır.

Yani eski "4-digit PIN" notu eksiktir: gönderilen varsayılan, dört rakam veya altı büyük-harf alfanümerik kabul eder.

### 5.3 Rate limitleri ve backoff

`C67942uO` (found), sadece flag **28678** (varsayılan `false`) ile aktif:

| Öğe | Değer |
|------|-------|
| tetikleyici | `UsernameSet` hatası 429, 503 veya 529 |
| süre | int saniye olarak ayrıştırılmış `Retry-After`-benzeri string (`C23680AJt.A00`), aksi halde flag **28127** (varsayılan 30) saniye |
| depolama | tercihler `username_creation_rate_limit_backoff_expiry` (ms), `username_creation_rate_limit_error_code` |
| etki | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet`, süre dolana kadar yerel olarak başarısız olur |

### 5.4 Hata kodundan mesaja (`C82003fB.A02`, found)

| Kod | Mesaj |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403, 404, 429 | "Couldn't complete your request. Try again." |
| 500, 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406, 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| diğer | "We couldn't complete your request. Try again." |

40601'den 40603'e, izin verilen kümedir `AbstractC111104pH.A01`'de (kodda sadece 40603 görülüyor). Sunucu semantikleri, istemci metninin ötesinde unknown'dır.

---

## 6. LID ilişkisi

İşaretlenmediyse hepsi found.

| Gerçek | Kanıt |
|------|------|
| Kullanıcı adı aramaları bir telefon JID'ine değil, bir **LID**'e çözülür | key başarı testi `userJid instanceof C14080dr` (LID sınıfı); MEX usync'te `lid_info.lid_jid` |
| Kullanıcı adı -> LID yerel haritası | tablo `lid_display_name` (kolonlar `username`, `lid_row_id`), `C1S0`'da query |
| Bildirimler kullanıcıyı LID ile tanımlar | ayarlama / silme handler'ları `LidUserJid`'i ayrıştırır (hata metni "Failed to parse LidUserJid") |
| Silme bildirimi bir telefon JID'i taşıyabilir | handler `isPnPresent`'i kontrol eder; PN mevcutken bir PN JID'i cast eder ve işlem yapar, PN olmadan döner |
| Kişi senkronizasyon eylemi | `ContactAction`, `lid_jid` (3), `pn_jid` (5)'in yanında `username`'e (6) sahiptir; ayrıca `LidContactAction` (`lid_contact`, SyncActionValue alanı 61) |
| Sohbet başlatma modu | SyncActionValue alanı **59** `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Sadece senkronizasyon codec'i bulundu; UI kodunda tüketici yok (unknown) |
| Companion özellik string'i | bir companion bağlarken primary özellik listesine `username_supported` (flag 4745 veya 20189), `username_reservation_only_mode` (sadece 20189), `username_account_linking_enabled` (flag 21199) ekler (`C25056AqU`) |

Inferred: sadece bir kullanıcı adı olarak var olan bir kullanıcı, sahibi telefon numarasını paylaşana kadar sadece LID üzerinden erişilebilirdir; "If you continue, your phone number will show in existing username chats and calls" (silme dialog'u) string'leri bunu destekler ama PN açığa çıkma yolu izlenmedi.

---

## 7. Bildirimler

Handler'lar `AbstractC23194A0r`'ı extend eder ve `AbstractC20380p4`'te kayıtlıdır (found):

| Bildirim | Handler | Davranış |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | payload `xwa2_notify_username_on_change`: LID'i (alan hash'i 107143) ve kullanıcı adını okur; `InterfaceC11470Yz.BNU(lid, username)` üzerinden saklar; kişi mevcutsa ve eşleşen türdeyse, kişiyi yeniler (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | payload `xwa2_notify_username_delete`: LID'i ve PN'i okur (hash -983979708); PN mevcutken silme güncellemesini çalıştırır (`C53594Nzh`) |
| `UsernameUpdateNotification` | anonim `X.2YG` | payload'dan bir base64 hash'i okur, neden `USERNAME_UPDATE_NOTIFICATION` ve `EnumC21760rz.A0Q` (`NOTIFICATION_SIDELIST` context'i, mod `query`; bkz WA_USYNC.md) ile bir USync isteği inşa eder, log `usync triggered for hash` |

Kullanıcıya gösterilen metin: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", yani sunucu bir kullanıcı adını yeniden atayabilir (iptal, `is_username_revoked` tercihi, `revocation_banner_dismissed_<username>`).

---

## 8. Feature flag'leri

Flag ID'leri, `C08J` üzerinden okunan AB-prop id'leridir (varsayılanlar `C08J` tablolarından). Aşağıdaki tüm varsayılanlar bu build'den okunmuştur.

| Flag | Tip | Varsayılan | Kontrol ettiği |
|------|------|---------|----------|
| **4745** | bool | false | primary: kullanıcı adı oluşturma (`CREATION` modu); ayrıca `username_supported` olarak reklam edilir |
| **20189** | bool | false | primary: sadece-rezervasyon modu (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: kullanıcı adı özellikleri hiç (aksi halde `DISABLED`) |
| **21199** | bool | false | hesap bağlama (FB / IG) etkin, `username_account_linking_enabled` olarak reklam edilir |
| **16033** | bool | false | key özellikleri için ana gate (`C79343Xx.A00`): key rate limiti, key upsell'i, WABI kullanıcı adı görünümü |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (JSON key'i yokken hepsi varsayılan doğru) |
| **8421** | bool | false | kullanıcı adı istekleri için MEX `UsyncQuery`'ye izin verir |
| **12402** | bool | false | usync `contact` node'una `lid` ve `pin` attribute'larını ekler |
| **20494** / **20459** | int | 3 / 35 | min / maks kullanıcı adı uzunluğu |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | key regex'i |
| **34347** / **34348** | int | 4 / 6 | key uzunluk sınırları (hata mesajı) |
| **28678** | bool | false | rate-limit backoff deposunu etkinleştirir |
| **28127** | int | 30 | varsayılan backoff saniyeleri |
| **29327** | int | 60 | `UsernameCheckMulti`'nin ikinci partisi öncesi gecikme |

Companion uygunluğu (`C224069kP.A00`, bytecode-seviyesi okuma):

```
companion (identity of the A02 check inferred from the "open WhatsApp on your primary device" strings):
  23817 off, or pref username_reservation_creation_supported_on_primary false  -> DISABLED
  pref username_account_linking_enabled_on_primary true                         -> COMPANION_READ_ONLY
  state RESERVED                                                                -> COMPANION_READ_ONLY
  state not UNSET                                                               -> CREATION
  state UNSET and pref username_reservation_only_mode_on_primary true           -> COMPANION_READ_ONLY
  state UNSET otherwise                                                         -> CREATION
primary:
  4745 on -> CREATION;  else 20189 on -> RESERVATION;  else DISABLED
```

Üç `*_on_primary` tercihi sadece burada okunuyor; nerede yazıldıkları bulunamadı (unknown).

---

## 9. Gizlilik ve görünürlük

| Açı | Bulgu | Kademe |
|--------|---------|------|
| Amaç | "Keep your phone number private with a username"; numarayı kayıtlı olmayanlar yerine kullanıcı adını görür | found (string'ler) |
| İlk iletişim | bir key ayarlıyken, "etkileşimde bulunmadığınız" kişiler kullanıcı adıyla iletişime geçmeden önce key'i girmelidir | found (string'ler) |
| Key paylaşımı | kullanıcı adı paylaşımı eylemi key'i içerebilir (pref `username_share_include_pin`, `C138535tr`'de taşındı); string'ler "Share your username and key" | found |
| Numaranın gizlendiği yer | topluluk yöneticileri ve kanal yöneticileri, bir kullanıcı adı ayarlanmadıkça numarayı görür; kanal takipçileri hiçbirini görmez | found (string'ler) |
| Grup / thread telemetrisi | mesaj gönderme telemetrisinde `has_username`, `has_username_pin`, `is_username_thread` alanları (`DZ1`, `RQG`) | found |
| Key'in durgun hali | kendi key'i `UsernameGet` tarafından döndürülür ve düz tercihlerde `username_pin`'de saklanır | found |
| Üçüncü-taraf sohbetleri | "Usernames and contacts added to third-party chats will not save to your phone" | found (string) |
| Business | "This username is only available on WhatsApp Business", bir reddetme metni olarak görünür | found (string) |
| Kimin sorgulayabileceği | MEX usync durumu `NOT_ALLOWED`, sunucunun istek-başına kullanıcı adı ifşasını reddedebildiğini gösterir | found (enum), kural unknown |
| Reşit olmayanlar | pref `is_teen_account`; ebeveyn metinleri "Your child created the username ..." | found |

Sunucu tarafından uygulanan görünürlük kuralları (bir kullanıcı adını kimin çözebileceği, key rate limitleri, yeniden atama) istemciden unknown'dır.

### 9a. Telefon-numarası-paylaşımı hedef kitle kontrolleri (2.26.45.10'da yeni, found)

Ayrı bir `com.whatsapp.pnsharing` paketi, kullanıcı adının kendi 9'daki görünürlük kurallarından bağımsız olarak, hesabın telefon numarasını kimin görebileceğini kontrol eder. Smali'de düz `const-string` literallerinden iki yeni `whatsapp-android-mex` operasyonunun ikisi de `found`'dur (decompile gerekmiyor, `PnSharingAudienceUpdater.smali` / `PnSharingListFetcher.smali` / `PnSharingListUpdater.smali`):

| Operasyon | doc_id | Tip |
|-----------|--------|------|
| `UsernamePhoneNumberPrivacyUpdateMutation` | `28835748819379698` | mutation |
| `UsernamePhoneNumberPrivacyGetQuery` | `29264643203229836` | query |

Hedef kitle ayarı, paylaşımlı, pnsharing'e-özgü-olmayan `LX/BWW` enum'unun (toplam 13 üye, bu çağrı yolundan sadece bu 4'üne erişilebilir) 4 değerinden biridir:

| ordinal | `LX/BWW` üyesi | `setting` değeri |
|---|---|---|
| 0 | `A02` | `ALL` |
| 1 | `A07` | `MYCONTACTS` |
| 2 | `A08` | `MYCONTACTSEXCEPT` |
| 3 | `A09` | `NONE` |

**`UsernamePhoneNumberPrivacyUpdateMutation` artımlıdır, tam-değiştirme değildir.** İki çağrı noktası onu besler:

- `PnSharingAudienceUpdater.A00` — sadece üst-seviye ayar değişikliği, liste girdisi yok.
- `PnSharingListUpdater.A01` — üç hedef kitle listesinden birine karşı girdi-başına ekleme/çıkarma.

Üst-seviye alanlar (found):

| Alan | Tip | Anlam |
|-------|------|---------|
| `setting` | string | `ALL` / `MYCONTACTS` / `MYCONTACTSEXCEPT` / `NONE`, yukarıdaki tabloya bakın |
| `input` | nesne | nested payload, aşağıya bakın |

`input` alanları (found, 3 `MYCONTACTS`-olmayan ayardan hangisi aktifse ona göre `allow_list` / `contact_exclude_list` / `deny_list` altında nested — `MYCONTACTS` hiçbir liste key'i göndermez):

| Alan | Tip | Anlam |
|-------|------|---------|
| `dhash` | string | hedef kitle listesinin içerik hash'i, cache geçersizleştirme / çakışma algılama için kullanılır (yanında `"...changed since it was read"` log string'i) |
| `entries` | nesne listesi | artımlı EKLE/SİL girdileri, tam liste değiştirmesi değil |

`entries[]` öğe alanları (found, `PnSharingListUpdater.A00(Integer, Integer)` tarafından inşa edilir):

| Alan | Tip | Anlam |
|-------|------|---------|
| `entry_type` | string | `USER` veya `GROUP` |
| `operation` | string | `ADD` veya `DEL` |
| `group_jid` | string, nullable | sadece `entry_type=GROUP` olduğunda ayarlanır |
| `pn_jid` | string, nullable | girdi çıplak bir telefon numarasıysa ayarlanır (`PhoneUserJid`) |
| `user_jid` | string, nullable | girdi çözülmüş bir kişi `Jid`'iyse ayarlanır |
| `username` | string, nullable | schema'da alan var ama gözlenen hiçbir çağrı noktası onu doldurmuyor; `inferred` amacı: henüz-kişi-olmayan bir telefon numarasını bir görünen adla eşleştirme, `UsernameSet`-tarzı istisnalarla tutarlı — herhangi bir çağıranın onu gerçekten ayarlayıp ayarlamadığı `unknown` |

Girdi başına `group_jid` / `pn_jid` / `user_jid`'den tam olarak biri doldurulur (found); diğer ikisi null kalır.

`UsernamePhoneNumberPrivacyGetQuery`, okuma-tarafı karşılığıdır (found, `PnSharingListFetcher.smali`): 3 hedef kitle listesinin tümünü bir kerede çeken, her biri cache doğrulaması için kendi `dhash`'iyle (yerel cache'lenmiş hash, veya yoksa literal string `"none"`) key'lenen tek bir toplu round trip.

**Çözülmemiş doc_id:** persisted-query kataloğu ayrıca `PnSharingPhoneNumberFetch`'i (doc_id `29229648029980096`, tip query) listeler. Bu literal için tüm decode edilmiş 2.26.45.10 smali ağacını (tüm shard'lar, sadece `com/whatsapp/pnsharing/` değil) grep'lemek hiçbir çağrı noktası bulmuyor — sadece gönderilen asset `whatsapp-android-mex_client_persist_ids.json` ona referans veriyor. Onu neyin çağırdığı ve ne gönderdiği **unknown**'dır. Sadece isimle en olası aday (**inferred**, daha fazlası değil): kişi-başına/grup-başına bir telefon-numarası-görünürlüğü çekmesi, yani yukarıdaki toplu 3-liste query'sinin tek-öğe karşılığı — doğrulanmamış.

---

## 10. Baileys notları

2.2'deki zarf geneldir; bir Baileys istemcisi onu inşa edebilir. Bu **inferred**'dir, burada test edilmemiştir.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| Risk | Neden |
|------|--------|
| doc_id sürüklenmesi | id'ler bu build'in asset'ine aittir; diğer build'ler farklı olabilir (unknown) |
| `session_id` | kod onu mevcut olduğunda gönderir; sunucunun kontrol ve ayarlama için aynı değeri gerektirip gerektirmediği unknown'dır |
| key attribute'ları | `contact` üzerindeki `lid` / `pin`, flag 12402'nin ardındadır; sunucu bunları flag'i olmayan istemciler için görmezden gelebilir (unknown) |
| yerel kurallar | uzunluk, karakter kümesi ve nokta kuralları istemci-tarafıdır; sunucu kuralları unknown'dır |

---

## 11. Ayırt edilmesi gereken noktalar

| Karıştırılmaması gereken | Fark |
|----------------|------------|
| Kullanıcı adı key'i vs hesap PIN'i / 2FA | Kullanıcı adı key'i (`UsernamePinSet`'teki `pin`, `username_pin` pref'i), kullanıcı adı üzerinden ilk iletişimi gater. Kayıt 2FA'sıyla ilgisizdir |
| `reserved` değişkeni vs `UsernamePinSet` | `reserved`, `UsernameSet`'e aittir ve bir rezervasyonu işaretler; key'in kendi operasyonu vardır |
| `RESERVED` durumu | yerel `C4DU.RESERVED` / sunucu `state=RESERVED`, henüz kullanılabilir olmayan tutulan bir isimdir; `ACTIVATED` ve `CREATED` kullanılabilirdir |
| Silme | silme operasyonu yoktur; `username` olmadan `UsernameSet` siler; key silme, `{}` ile `UsernamePinSet`'tir |
| Kontrol sonucu `INVALID` | alınmış, bağlama-gereken ve format sorunlarını kapsar; detay `rejection_reasons`'dadır |
| Kullanıcı adı vs LID | kullanıcı adı bir handle'dır; adresleme kimliği LID'dir |
| `source` int'leri | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; `C02U` hata id'leriyle aynı int'ler değildir |
| doc_id vs `client_doc_id` | ikisi de asset'tedir; yakalanan id'ler `doc_id`'ye eşittir |
| Bildirimler vs operasyonlar | üç `Username*Notification` tipi push handler'larıdır, istek değildir |
| Repolar-arası etiketler | `25975613018777537`, bu build'in persist-id asset'inde yoktur; `25741205615468935`, bu build'de `GetTextStatusList`'tir. İkisi de burada bir kullanıcı-adı operasyonu değildir |

---

## 12. Baştan sona akış

```
[User]                [Client]                              [Server]
  │ type name           │                                      │
  ▼                     │                                      │
 local validate ────────┤ charset, 3..35, dots, regex (5.1)    │
  │ ok                  ▼                                      │
  │              UsernameCheck {username, include_suggestions,  │
  │                             source, session_id}  ─────────►│
  │                     │◄──── xwa2_username_check {result,    │
  │                     │       suggestions, rejection_reasons}│
  │ SUCCESS             │                                      │
  ▼                     ▼                                      │
 confirm ─────────► UsernameSet {username, reserved,           │
                      session_id, source, [pin]} ─────────────►│
                        │◄──── ok | 304 | 40601..40603 | 429/503/529
                        ▼                                      │
                  write prefs: state, username_pin             │
                  429/503/529 -> backoff (flag 28678)          │
                                                               │
 [Owner sets key] ► UsernamePinSet {pin} | {} (delete) ───────►│

 [Other user, first contact]
  │ enter @name + key
  ▼
 validate key (flag 34350) ► usync contact{username,[lid],[pin]} ──►[Server]
                        │◄──── user jid (LID) | no LID | rate-limit flags
                        ▼
              LID  = open chat addressed to the LID
              none = "Wrong key entered"
              limit = "Too many attempts" / "can't be reached"

 [Server push]
   UsernameSetNotification (lid, username)  -> update local map
   UsernameDeleteNotification (lid, pn)     -> update contact
   UsernameUpdateNotification (hash)        -> usync delta
```

---

## 13. Bilinmeyenler

| Konu | Neden |
|-------|--------|
| `query_id`'yi besleyen tam accessor | `doc_id` vs `client_doc_id` tüketicisi IQ builder'ına kadar izlenmedi |
| `UsernamePinSet`, `UsernameSet`'in yanıt şekli | yanıt sınıflarının okunan kodda alan erişimi yok |
| `UsernameGetRecommendationsQuery` | çağrı noktası yok, değişken yok |
| Sunucu-tarafı kullanıcı adı ve key kuralları | istemci sadece yerel olarak doğrular |
| Sunucuda 40601-40603'ün anlamı | sadece istemci string'leri bulundu |
| `*_on_primary` tercihlerinin kökeni | yazıcı bulunamadı |
| `username_chat_start_mode` etkisi | tüketici bulunamadı |
| `UsernameGet` kullanım deseni (heartbeat) | okunan kod tarafından desteklenmiyor |
| Doğru bir key sonrası sohbet-açma adımı | LID kontrolünün ötesinde izlenmedi |
| Gerçek trafik | sadece statik analiz |
