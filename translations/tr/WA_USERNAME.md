<!-- src-sha1: 9e1058e3eb76214c55e35cbbb05dda93127364b1 -->
# WhatsApp Kullanıcı Adı — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Kullanıcı adı kontrol / ayarlama / rezerve etme / silme, kullanıcı adı anahtarı (PIN), LID ilişkisi, gizlilik ve görünürlük, w:mex GraphQL işlemleri (doc_id'ler, değişkenler, yanıtlar), bildirimler, USync sorgusu, doğrulama kuralları, feature flag'leri, Baileys notları

---

## 1. Kullanıcı adı nedir (teknik olarak)

Kullanıcı adı, bir hesaba bağlı, sunucu tarafında tutulan bir tanıtıcıdır (handle); bir kişiye telefon numarası açığa çıkmadan ulaşılabilmesi için kullanılır. Tüm ifadeler çözülmüş (decompile edilmiş) APK'nın statik analizine dayanır. Kademe: **found** = kodda veya asset'lerde okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi.

Özellik üç katman üzerine kurulu:

| Katman | Taşıma | Kullanım |
|-------|-----------|----------|
| Kendi hesabını yönetme | `w:mex` IQ, persisted GraphQL (config `whatsapp-android-mex`) | kontrol, ayarlama / rezerve etme / silme, alma, anahtar (PIN) ayarlama / silme, çoklu kontrol |
| Başkalarını sorgulama | USync (`xmlns="usync"`) ve MEX `UsyncQuery` varyantı | `@username` (+ anahtar) değerini LID'e çözme, bilinen bir JID'in kullanıcı adını alma |
| Push | MEX bildirimleri | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Cihazlar arası | app-state sync (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (`username` taşır) |

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| Kullanıcı adı yöneticisi | `C122815Lj` | `UsernameGet`, `UsernameSet` çağrıları, yerel durum güncellemesi, rate-limit hook'u |
| Uygunluk kontrolü | `C67402tT` | `UsernameCheck` çağrısı + yanıt eşleme |
| Çoklu kontrol | `C76333Kg` | `UsernameCheckMulti`, 10'luk parçalar |
| Anahtar API'si | `MexUsernamePinProtocolApi` | `UsernamePinSet` (anahtar ayarlama / silme) |
| Yerel durum / prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| Durum enum'u | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Uygunluk modu | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Rate-limit deposu | `C67942uO` | 429 / 503 / 529 sonrası backoff |
| Yerel doğrulayıcı | `C82003fB.A04`, `C1187754z` | uzunluk, karakter kümesi, nokta kuralları, regex |
| Anahtar doğrulayıcı | `C1176550d` (+ `AbstractC111284pZ`) | anahtar formatı |
| Anahtar girişi VM | `UsernamePinEntryViewModel` | yabancı bir kullanıcı adı için anahtar gönderme |
| USync istemcisi | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | klasik usync stanza oluşturucu / ayrıştırıcı |
| MEX USync | `C229259vZ`, `O0F` | `include_username` ile `UsyncQuery` |
| Bildirim işleyicileri | `C49822Lvi`, `C49821Lvh`, `AbstractC20380p4` içindeki anonim `X.2YG` | ayarlama / silme / güncelleme |

Adlandırma: PIN'in kullanıcıya görünen adı **username key**'dir ("Username key", "Add a username key to control who can contact you" metinleri). Wire ve kod `pin` der.

---

## 2. MEX işlemleri (doc_id'ler)

### 2.1 doc_id'ler nerede duruyor

doc_id'ler `java_src` içinde literal olarak yer almaz. İstemci işlem adını (`"UsernameSet"`, ...) `"whatsapp-android-mex"` config adıyla birlikte gönderir (found, `C16880is`). Sayısal id `assets/whatsapp-android-mex_client_persist_ids.json` dosyasından okunur: `EnumC17010j7.WHATSAPP_ANDROID_MEX` bu dosyaya eşlenir, `C17040jA.CMg(op)` `doc_id` alanını, `AGb(op)` `client_doc_id` alanını döndürür (found). İki erişimciden hangisinin `query_id` özniteliğini doldurduğu sonuna kadar izlenmedi (unknown); 2.26.26.4 üzerindeki önceki yakalamalar `query_id` değerinin `doc_id`'ye eşit olduğunu gösteriyor.

Aşağıdaki doc_id'ler 2.26.41.6 asset'inde **found**:

| İşlem | doc_id | Tür | Çağrı yeri | Yanıt sınıfı |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | none found | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Notlar:
- `UsernameGetRecommendationsQuery`: ad yalnızca asset JSON'unda geçer. `java_src` içinde hiçbir sınıf buna string olarak başvurmaz (found). Değişkenler ve yanıt unknown.
- Üç bildirim adının (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) persist-id asset'inde girdisi yoktur. Bunlar istek değil, bildirim türleridir (bkz. 7).
- Asset, işlem başına `operation_name_hash`, `operation_text_hash` ve `client_doc_id` içerir. Örnek `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Zarf (envelope)

`C19370nI` / `C19310nC` içinde oluşturulur (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Alan | Kural (kod) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | mutation'lar dahil her işlem için `get` |
| `query_id` özniteliği | yalnızca 1 ila 20 karakter ise ayarlanır |
| gövde | JSON `{"queryId": ..., "variables": {...}}`, 1 ila 8448000 bayt |
| null değişkenler | `C16770ig.A03(k, null)` ve `A02(k, null)` anahtarı atlar; yani değerin olmaması anahtarın gönderilmediği anlamına gelir |

Canlı oturumlardaki wire stanza'ları burada yeniden üretilmemiştir; bu derleme yalnızca statik olarak analiz edildi.

---

## 3. İşlemlerin ayrıntısı

### 3.1 UsernameCheck

Değişkenler (found, `C67402tT.A00`):

| Değişken | Tür | Koşul |
|----------|------|-----------|
| `username` | string | her zaman |
| `include_suggestions` | bool | her zaman (UI, yazılan-kontrol yolunda `false` geçirir, `C64H` case 21) |
| `source` | string | yalnızca null değilse |
| `session_id` | string | yalnızca null değilse |

`source` eşlemesi (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, diğer -> null (gönderilmez).

Yanıt yolu (found, `C77183Np` default dalı): `data.xwa2_username_check`

| Alan | Tür | Kullanım |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | yalnızca `INVALID` iken okunur |
| `rejection_reasons` | `C4G8` listesi | yalnızca `INVALID` iken okunur |
| `suggestions_eligible` | bool | alan null ise varsayılan `true` |

`C4G8` değerleri (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Eşleme: `SUCCESS` -> `C76283Kb` (uygun); `INVALID` -> `C76303Kd` (uygun değil, suggestions + reasons taşır); `UNSET` -> hiçbir dal sonuç atamaz (callback önceki/null değişkeni alır; davranış unknown). Etkin yerel backoff -> `C76293Kc` (prefs'ten rate-limit koduyla hata, bkz. 5.3); isteğin kendi başarısızlık callback'i okunmadı.

Reddetme nedenleri hesap bağlama metnini yönlendirir ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). `C82003fB` içinde `UNSET` dışındaki herhangi bir neden, 40601 koduyla yerel hata yolunu tetikler (`A08(40601L)`); boş veya yalnızca `UNSET` içeren bir liste "Username isn't allowed." gösterir. Döngü etrafındaki tam kontrol akışı yalnızca kısmen decompile edilebildi (inferred).

### 3.2 UsernameCheckMulti

| Değişken | Tür | Notlar |
|----------|------|-------|
| `usernames` | **list<string>** | `A00.A0B("usernames", list)` ile dizi; doc_id kataloğu bunu `str` olarak tiplendirir, kod bir liste gönderir |

Gruplama (`C76333Kg.AG5`): liste ilk 10 ve geri kalan olarak bölünür; geri kalan, flag **29327** gecikmesinden sonra işlenir (varsayılan 60, birim çözülemedi). Boş liste, istek yapmadan boş bir map döndürür.

Yanıt yolu `data.xwa2_username_check_multi.results[]` (found): her öğe `username` ve `response.result` içerir (aynı `EnumC59782gh`). Eşleme: `SUCCESS` -> uygun, `INVALID` -> uygun değil (suggestion yok, `suggestions_eligible=false`), diğer her şey -> hata. Sonuçta bulunmayan adlar hata olarak işaretlenir.

Tüketici: `UsernameAvailabilityCache`, ad başına `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) saklar. Amaç (Facebook / Instagram kullanıcı adı önerileri için önceden getirme, string `foa_username_prefetch_cache`) inferred.

### 3.3 UsernameSet (oluşturma / değiştirme / rezerve etme / silme)

Değişkenler (found, `C122815Lj.A00`):

| Değişken | Tür | Koşul |
|----------|------|-----------|
| `username` | string | null ise atlanır (**delete**) |
| `reserved` | bool | her zaman gönderilir |
| `session_id` | string | yalnızca boş değilse (`C1YW.A08`) |
| `source` | string | yalnızca source int'i null değilse (bkz. 3.1) |
| `pin` | string | yalnızca null değilse |

`reserved` sabit değil, hesaplanır (found). Argüman `z` (force) = true ise `false` verir. Aksi halde: mevcut durum `ACTIVATED` veya `CREATED` ise `false`; mevcut durum `RESERVED` veya uygunluk modu `RESERVATION` ise `true`; diğer tüm durumlarda `false`. Dolayısıyla `reserved:true` yalnızca rezervasyon modundaki veya zaten rezervasyonu olan hesaplar için gönderilir.

Silme, aynı işlemin bir modudur: `username == null` -> log etiketi `delete`, aksi halde `set` (anahtar için `MexUsernamePinProtocolApi` içinde de aynı). Null username ile `username` anahtarı değişkenlerde yer almaz (found).

İstemci tarafı koruma: göndermeden önce rate-limit deposu etkin bir backoff bildirirse çağrı yerel olarak `username_creation_rate_limit_error_code` ile ve "rate limit expiration time not reached" metniyle başarısız olur (found, `C122815Lj.A03`).

Başarı işleme (`C122815Lj.A01`, found):

| Koşul | Yazılan yerel durum (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username null veya boş | `UNSET`, anahtar pref'i temizlenir |
| `reserved` true idi | `RESERVED` |
| activate flag'i | `ACTIVATED` |
| aksi | durum `ACTIVATED` idiyse ve ad saklanan adla aynıysa `ACTIVATED`, değilse `CREATED` |
| `source` int'i 1 veya 2 | pref `username_set_via_account_linking` = (int == 2) |
| `pin` gönderildi | pref `username_pin` güncellenir |
| teen flag'i | pref `is_teen_account` = true |

Pref yazımı `Voip.REJECT_REASON_DECLINED` ile yapılır; bu derlemede bu, boş string `""` değeridir (found).

Hata işleme (`C138725uA` case 2):

| HTTP benzeri kod | İstemci eylemi |
|----------------|---------------|
| 429, 503, 529 | backoff saklanır (5.3) |
| 304 | başarı sayılır ("not modified"), yerel durum yine güncellenir |
| bağlantı yok (`C213639Bb`) | `C4BO` "no network" sonucu |
| diğer | `C4BN(code, message)` |

### 3.4 UsernameGet

Değişkenler: yok (çağrı boş bir değişken kümesi oluşturur, found, `C122815Lj.A02`). `@Deprecated` işaretli, yerini bir suspend varyantı aldı.

Yanıt (found, `C138815uJ` case 34): `data.xwa2_username_get.username_info`

| Alan | Kullanım |
|-------|-----|
| `username` | saklanır; yoksa boş string |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **anahtar açık metin olarak döndürülür ve `username_pin` pref'inde saklanır**; yoksa boş string |

Durum eşlemesi: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> saklanan username döndürülenle aynıysa ve yerel durum `RESERVED` veya `ACTIVATED` idiyse `ACTIVATED`, değilse `CREATED`; null state veya null `username_info` -> `UNSET`.

Sunucudan gelen 404 hatası yerel username'i, anahtarı ve durumu temizler (log `clearSelfUsernameData NOT_FOUND`).

Çağrının heartbeat olarak kullanılıp kullanılmadığı unknown; eski "polling heartbeat" notu bu derlemenin koduyla desteklenmiyor.

### 3.5 UsernamePinSet (kullanıcı adı anahtarı)

Değişkenler (found): `pin` (string), null ise atlanır.

| Eylem | Değişkenler |
|--------|-----------|
| anahtarı ayarla | `{"pin": "<key>"}` |
| anahtarı sil | `{}` (`A02`, `A00(null)` çağırır) |

İkisi için de işlem adı `UsernamePinSet`'tir; ayrı bir doğrulama işlemi yoktur. Yabancı bir anahtarın doğrulaması USync içinde yapılır (4). Bağlı değilse: istek yapmadan `C213639Bb("UsernamePinSet")` döndürür.

Anahtar `UsernameSet` içinde de taşınabilir (`pin` değişkeni). `C81793ej.A0x`, yerelde zaten bir username saklıysa (`A00 != null`) mevcut username ve yeni `pin` ile `UsernameSet` kullanır, aksi halde `UsernamePinSet` kullanır (found).

`C48557LJz` yanıt sınıfında, okunan dosyalarda alan erişimi yok; yanıt şekli unknown.

---

## 4. Diğer kullanıcıları sorgulama

### 4.1 Kullanıcı adına göre klasik USync (anahtar akışı)

`C18670m9.A06` içinde oluşturulur (jadx bu metotta başarısız oldu, `X/0m9.smali` smali'sinden okundu). `C222649hm` istek girdisi başına: alan `A0C` = username, `A0D` = anahtar, `A05` = LID.

`contact` alt düğümünün öznitelikleri (smali'de found): `username` her zaman; yerelde bir LID biliniyorsa `lid`; bir anahtar ayarlıysa `pin`. Ek öznitelikler flag **12402** ile kapılıdır (varsayılan `false`): flag kapalıyken yalnızca `username` yazılır (found). `contact` düğüm adı, yanıt ayrıştırıcısından çıkarılmıştır (inferred); ayrıştırıcı `contact` alt düğümünü ve onun `username` özniteliğini okur (`C18670m9` satır ~969-975).

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

Giriş noktası: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), `submitPinForUsername` tarafından çağrılır. Sync türü `EnumC21760rz.A0J`, timeout 32000 ms. `contact`, `pin`, `username` öznitelik kümesi `AbstractC40921lc` içindeki log-redaksiyon kümelerinde yer alır (found).

Yerel ön çözümleme: `A0M.Aol(username)`, `lid_display_name` tablosunda `UPPER(username) = UPPER(?)` koşuluyla `lid_row_id` değerini arar, en yeni satır önce (found, `C1S0`). LID biliniyorsa `lid` özniteliğine girer.

### 4.2 Sonuç değerlendirmesi (anahtar girişi)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Sonuç | Koşul |
|---------|-----------|
| doğru anahtar | sonuç `UserJid` bir LID'dir (`C14080dr`) |
| yanlış anahtar | sonuçta LID yok: log `[un-pin] incorrect PIN`, hata metni "Wrong key entered" |
| ağ yok | `C9qA` kod 1 |
| genel altyapı hatası | `C9qA` kod 2 |
| requestor rate limit | `C225769os.A01` true: "Too many attempts made. Try later." |
| requestee rate limit | `C225769os.A00` true: "This account can't be reached with their key right now..." |

İstemci tarafı önbellekli rate-limit kontrolü önce çalışır; bunun için flag **16033** açık olmalı ve JSON config **21995** içinde `enable_key_rate_limit` true olmalıdır (varsayılan true): `C30P.A00`, hem kendi LID'ine hem hedef username'e karşı. Username'den `@` temizlenir (`C0CX.A0i(username, '@')`).

Başarıda sonuç bir **LID**'dir, sohbet daha sonra LID'e adreslenir (`C14080dr` kontrolünden inferred; sohbet açma adımı izlenmedi).

### 4.3 Bilinen bir LID'in kullanıcı adını alma

`C23638AId` (satır ~600-650), `<list><user jid="LID"/></list><query><contact/><username/></query>` içeren bir usync oluşturur; mode/context `EnumC21760rz.A0J`'den gelir (found). Ayrıştırıcı `username` değerini `<usync>` sonucunun alt düğümü olarak okur (`C18670m9` satır 586, yalnızca istek bunu istediyse).

### 4.4 MEX USync (`UsyncQuery`)

`C229259vZ.A01`, `UsyncQuery` oluşturur (doc_id yukarıda). İlgili kısımlar (found):

| Değişken | Kullanım |
|----------|-----|
| `query_input[]` | kullanıcı başına bir girdi: JID (`C493020r.A0C`), isteğe bağlı `client_known_username` (yalnızca username istendiyse ve boş değilse) |
| `include_username` | bool, herhangi bir girdi username istediğinde ayarlanır |
| `include_lid` | bool, `lid_info` ister |
| `telemetry.context` | küçük harfe çevrilmiş USync context'i |

Kullanıcı başına yanıt: `jid`, `username_info`, `lid_info` (`O0F`). `username_info`, tür hash'ine göre polimorfiktir: `username` tutan bir değer türü veya `EnumC216389Tz` değerinde `status` taşıyan bir durum türü: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED`, "username not allowed to be queried" olarak loglanır ve saklanan username'i temizler; `NO_CHANGE` onu korur. `lid_info.lid_jid` LID'i taşır.

Kapı: `ContactSyncHelper`, bir username istendiğinde flag **8421** açık değilse MEX yolunu "cantUseMex as username ab prop is off" logu ile reddeder (found; varsayılan `false`).

---

## 5. Doğrulama, limitler, hatalar

### 5.1 Kullanıcı adı formatı (yerel)

Doğrulayıcı `C82003fB.A04` (found), kontroller bu sırayla:

| Sıra | Kontrol | Hata id'si (`C02U`) | Mesaj string'i |
|-------|-------|-------------------|----------------|
| 1 | her karakter `[A-Za-z0-9_.]` içinde | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | uzunluk >= min (flag **20494**, varsayılan 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | uzunluk <= max (flag **20459**, varsayılan 35) | 1 | aynı string |
| 4 | başta `.` yok, sonda `.` yok, `..` yok | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | en az bir ASCII harf | 4 | "Choose a username with at least one letter" |
| 6 | regex (aşağıda) | geçer veya 2 ile başarısız olur | n/a |

`C1187754z.A02()` tarafından oluşturulan regex (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

Büyük/küçük harf doğrulayıcı tarafından normalize edilmez; yerel sorgu `Aol` `UPPER()` ile karşılaştırır, yani eşleşme yerelde büyük/küçük harfe duyarsızdır (found). Sunucunun adları büyük/küçük harfe duyarsız ele alıp almadığı unknown. Başta alt çizgiye regex izin verir; UI metni "start with a letter" der, bu regex'ten daha katıdır (found, uyuşmazlık).

UI ayrıca web bağlantılarını reddeder: "Enter only your username, not a web link" (string mevcut, kontrol izlenmedi).

### 5.2 Kullanıcı adı anahtarı formatı

`C1176550d.A00` (found): flag **34350** bir regex string'idir, varsayılan `^([0-9]{4}|[A-Z0-9]{6})$`. Flag string'i boşsa yedek, tam olarak dört rakamdır. Geçersiz regex `[un-pin] invalid username_key_regex` loglar ve her şeyi kabul eder. Uzunluk sınırları, flag'ler **34347** (min, 4) ve **34348** (max, 6), yalnızca `UsernamePinEntryViewModel.A0w` içindeki hata mesajı yolunu besler. Sunucu tarafı kuralları unknown.

Dolayısıyla eski "4 haneli PIN" notu eksiktir: gönderilen varsayılan, dört rakamı veya altı büyük harfli alfasayısal karakteri kabul eder.

### 5.3 Rate limit'ler ve backoff

`C67942uO` (found), yalnızca flag **28678** ile etkin (varsayılan `false`):

| Öğe | Değer |
|------|-------|
| tetikleyici | `UsernameSet` hatası 429, 503 veya 529 |
| süre | `Retry-After` benzeri string, int saniye olarak ayrıştırılır (`C23680AJt.A00`), aksi halde flag **28127** (varsayılan 30) saniye |
| depolama | prefs `username_creation_rate_limit_backoff_expiry` (ms), `username_creation_rate_limit_error_code` |
| etki | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` süre dolana kadar yerel olarak başarısız olur |

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

40601 ile 40603, izin verilen küme `AbstractC111104pH.A01` içindedir (okunan kodda yalnızca 40603 görünüyor). Sunucu anlamları, istemci metninin ötesinde unknown.

---

## 6. LID ilişkisi

Aksi belirtilmedikçe hepsi found.

| Olgu | Kanıt |
|------|----------|
| Kullanıcı adı sorguları bir telefon JID'ine değil, bir **LID**'e çözülür | anahtar başarı testi `userJid instanceof C14080dr` (LID sınıfı); MEX usync'te `lid_info.lid_jid` |
| Yerel username -> LID eşlemesi | tablo `lid_display_name` (sütunlar `username`, `lid_row_id`), sorgu `C1S0` içinde |
| Bildirimler kullanıcıyı LID ile tanımlar | set / delete işleyicileri `LidUserJid` ayrıştırır (hata metni "Failed to parse LidUserJid") |
| Delete bildirimi bir telefon JID'i taşıyabilir | işleyici `isPnPresent` kontrol eder; PN varken bir PN JID'ine cast eder ve işlem yapar, PN yokken döner |
| Kişi sync eylemi | `ContactAction`, `lid_jid` (3), `pn_jid` (5) yanında `username` (6) içerir; ayrıca `LidContactAction` (`lid_contact`, SyncActionValue alanı 61) |
| Sohbet başlatma modu | SyncActionValue alanı **59** `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Yalnızca sync codec'i bulundu; UI kodunda tüketici yok (unknown) |
| Companion feature string'i | bir companion bağlanırken primary, feature listesine `username_supported` (flag 4745 veya 20189), `username_reservation_only_mode` (yalnızca 20189), `username_account_linking_enabled` (flag 21199) ekler (`C25056AqU`) |

Inferred: yalnızca kullanıcı adı olarak var olan bir kullanıcıya, sahibi telefon numarasını paylaşana kadar yalnızca LID üzerinden ulaşılabilir; "If you continue, your phone number will show in existing username chats and calls" (silme diyaloğu) string'leri bunu destekler, ancak PN'in açığa çıkma yolu izlenmedi.

---

## 7. Bildirimler

İşleyiciler `AbstractC23194A0r` sınıfını genişletir ve `AbstractC20380p4` içinde kaydedilir (found):

| Bildirim | İşleyici | Davranış |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | payload `xwa2_notify_username_on_change`: LID'i (alan hash'i 107143) ve username'i okur; `InterfaceC11470Yz.BNU(lid, username)` ile saklar; kişi varsa ve eşleşen türdeyse kişiyi yeniler (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | payload `xwa2_notify_username_delete`: LID ve PN'i okur (hash -983979708); PN varsa silme güncellemesini çalıştırır (`C53594Nzh`) |
| `UsernameUpdateNotification` | anonim `X.2YG` | payload'dan base64 bir hash okur, `USERNAME_UPDATE_NOTIFICATION` nedeni ve `EnumC21760rz.A0Q` ile bir USync isteği oluşturur (delta tarzı sync, inferred), log `usync triggered for hash` |

Kullanıcıya gösterilen metin: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)"; yani sunucu bir kullanıcı adını yeniden atayabilir (iptal, `is_username_revoked` pref'i, `revocation_banner_dismissed_<username>`).

---

## 8. Feature flag'leri

Flag ID'leri, `C08J` üzerinden okunan AB-prop id'leridir (varsayılanlar `C08J` tablolarından). Aşağıdaki tüm varsayılanlar bu derlemeden okundu.

| Flag | Tür | Varsayılan | Kontrol ettiği |
|------|------|---------|----------|
| **4745** | bool | false | primary: kullanıcı adı oluşturma (`CREATION` modu); ayrıca `username_supported` olarak duyurulur |
| **20189** | bool | false | primary: yalnızca rezervasyon modu (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: kullanıcı adı özellikleri hiç (aksi halde `DISABLED`) |
| **21199** | bool | false | hesap bağlama (FB / IG) etkin, `username_account_linking_enabled` olarak duyurulur |
| **16033** | bool | false | anahtar özellikleri için ana kapı (`C79343Xx.A00`): anahtar rate limit, anahtar upsell, WABI username görünümü |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (JSON anahtarı yoksa hepsi varsayılan true) |
| **8421** | bool | false | username istekleri için MEX `UsyncQuery`'ye izin verir |
| **12402** | bool | false | usync `contact` düğümüne `lid` ve `pin` öznitelikleri ekler |
| **20494** / **20459** | int | 3 / 35 | min / max kullanıcı adı uzunluğu |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | anahtar regex'i |
| **34347** / **34348** | int | 4 / 6 | anahtar uzunluk sınırları (hata mesajı) |
| **28678** | bool | false | rate-limit backoff deposunu etkinleştirir |
| **28127** | int | 30 | varsayılan backoff saniyesi |
| **29327** | int | 60 | `UsernameCheckMulti` ikinci grubundan önceki gecikme |

Companion uygunluğu (`C224069kP.A00`, bytecode düzeyinde okuma):

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

Üç `*_on_primary` pref'i yalnızca burada okunur; nerede yazıldıkları bulunamadı (unknown).

---

## 9. Gizlilik ve görünürlük

| Husus | Bulgu | Kademe |
|--------|---------|------|
| Amaç | "Keep your phone number private with a username"; numarayı kayıtlı tutmayan kişiler bunun yerine kullanıcı adını görür | found (strings) |
| İlk temas | bir anahtar ayarlıyken, "you haven't interacted with" kişiler kullanıcı adıyla iletişime geçmeden önce anahtarı girmelidir | found (strings) |
| Anahtar paylaşımı | kullanıcı adı paylaşma eylemi anahtarı içerebilir (pref `username_share_include_pin`, `C138535tr` içinde taşındı); "Share your username and key" string'leri | found |
| Numaranın gizlendiği yerler | topluluk yöneticileri ve kanal yöneticileri, kullanıcı adı ayarlanmadıkça numarayı görür; kanal takipçileri hiçbirini görmez | found (strings) |
| Grup / thread telemetrisi | mesaj gönderme telemetrisinde `has_username`, `has_username_pin`, `is_username_thread` alanları (`DZ1`, `RQG`) | found |
| Anahtarın depolanması | kendi anahtarı `UsernameGet` tarafından döndürülür ve düz prefs `username_pin` içinde saklanır | found |
| Üçüncü taraf sohbetleri | "Usernames and contacts added to third-party chats will not save to your phone" | found (string) |
| Business | "This username is only available on WhatsApp Business" bir ret metni olarak görünür | found (string) |
| Kim sorgulayabilir | MEX usync durumu `NOT_ALLOWED`, sunucunun kullanıcı adı ifşasını isteyen başına reddedebildiğini gösterir | found (enum), kural unknown |
| Reşit olmayanlar | pref `is_teen_account`; ebeveyn metinleri "Your child created the username ..." | found |

Sunucunun uyguladığı görünürlük kuralları (bir kullanıcı adını kimin çözebileceği, anahtar rate limit'leri, yeniden atama) istemciden unknown.

---

## 10. Baileys notları

2.2'deki zarf geneldir; bir Baileys istemcisi bunu oluşturabilir. Bu **inferred**'dır, burada test edilmedi.

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
| doc_id kayması | id'ler bu derlemenin asset'ine aittir; diğer derlemeler farklı olabilir (unknown) |
| `session_id` | kod mevcutsa gönderir; sunucunun check ve set için aynı değeri isteyip istemediği unknown |
| anahtar öznitelikleri | `contact` üzerindeki `lid` / `pin` flag 12402'nin arkasındadır; sunucu bunları flag'i olmayan istemciler için yok sayabilir (unknown) |
| yerel kurallar | uzunluk, karakter kümesi ve nokta kuralları istemci tarafındadır; sunucu kuralları unknown |

---

## 11. Temel ayrımlar

| Karıştırılmaması gerekenler | Fark |
|----------------|------------|
| Username key ile hesap PIN'i / 2FA | Username key (`UsernamePinSet` içindeki `pin`, `username_pin` pref'i) kullanıcı adı üzerinden ilk teması kapılar. Kayıt 2FA'sı ile ilgisi yoktur |
| `reserved` değişkeni ile `UsernamePinSet` | `reserved`, `UsernameSet`'e aittir ve bir rezervasyonu işaretler; anahtarın kendi işlemi vardır |
| `RESERVED` durumu | yerel `C4DU.RESERVED` / sunucu `state=RESERVED` tutulan ama henüz kullanılamayan bir addır; `ACTIVATED` ve `CREATED` kullanılabilir |
| Silme | silme işlemi yoktur; `username` olmadan `UsernameSet` siler; anahtar silme `{}` ile `UsernamePinSet`'tir |
| Kontrol sonucu `INVALID` | alınmış, bağlama gerektiren ve format sorunlarını kapsar; ayrıntı `rejection_reasons` içindedir |
| Kullanıcı adı ile LID | kullanıcı adı bir tanıtıcıdır; adresleme kimliği LID'dir |
| `source` int'leri | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; `C02U` hata id'leriyle aynı int'ler değildir |
| doc_id ile `client_doc_id` | ikisi de asset'tedir; yakalanan id'ler `doc_id`'ye eşittir |
| Bildirimler ile işlemler | üç `Username*Notification` türü push işleyicileridir, istek değildir |
| Repo'lar arası etiketler | `25975613018777537` bu derlemenin persist-id asset'inde yoktur; `25741205615468935` bu derlemede `GetTextStatusList`'tir. İkisi de burada bir kullanıcı adı işlemi değildir |

---

## 12. Uçtan uca akış

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

## 13. Unknown'lar

| Konu | Neden |
|-------|--------|
| `query_id`'yi besleyen tam erişimci | `doc_id` ile `client_doc_id` tüketicisi IQ oluşturucuya kadar izlenmedi |
| `UsernamePinSet`, `UsernameSet` yanıt şekli | yanıt sınıflarında okunan kodda alan erişimi yok |
| `UsernameGetRecommendationsQuery` | çağrı yeri yok, değişken yok |
| Sunucu tarafı kullanıcı adı ve anahtar kuralları | istemci yalnızca yerelde doğrular |
| 40601-40603'ün sunucudaki anlamı | yalnızca istemci string'leri bulundu |
| `*_on_primary` pref'lerinin kaynağı | yazan yer bulunamadı |
| `username_chat_start_mode` etkisi | tüketici bulunamadı |
| `UsernameGet` kullanım deseni (heartbeat) | okunan kodla desteklenmiyor |
| Doğru anahtardan sonra sohbet açma adımı | LID kontrolünün ötesine izlenmedi |
| Gerçek trafik | yalnızca statik analiz |
