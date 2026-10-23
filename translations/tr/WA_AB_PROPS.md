<!-- src-sha1: 4762669c756eee4725aaf5af56633f2b59edd479 -->
# WhatsApp AB Props — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android'de AB props / feature flag'ler: sayısal flag id'leri ve tipli varsayılan tablolar, tipli okuyucular ve okuma seçenekleri, MobileConfig katmanı (Stable ID'ler, unit tipleri, `params_map_v4_u*`, `MetaConfigFetchMutation`), props sync IQ (`xmlns="abt"`: hash, refresh, refresh_id, delta, expo key'leri, sampling weight'ler), grup düzeyi props, kayıt öncesi (pre-registration) props, cihaz üstü (offline) deneyler, cihazda depolama, exposure loglama, override ve debug yolları, diğer raporlarda anılan flag id'leriyle ilişki, alana göre flag kataloğu, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

AB props, istemcinin sunucu tarafından yönetilen feature flag'leridir. Her flag yalnızca sayısal bir **config code** ile tanımlanır (örn. `20548`); APK içinde hiçbir flag adı yoktur. İstemci her kod için tipli bir varsayılan tablo taşır, sunucudan override'ları bir IQ üzerinden ister, yanıtı SharedPreferences'ta saklar ve tek bir soyut okuyucu sınıf üzerinden okur. Yanında ikinci, Meta kökenli bir katman (MobileConfig) çalışır ve doğruluk kaynağı haline gelebilir. Tüm ifadeler decompile edilmiş APK'nın statik analizinden gelir; ağ üzerinde hiçbir şey yakalanmadı. Tier'lar: **found** = kodda veya veride okundu, **inferred** = çıkarım, **unknown** = çözülmedi. Obfuscate edilmiş adlar build'e özgüdür ve 2.26.41.6'da yeniden çözüldü.

| Katman | 2.26.41.6 adı | Rol |
|--------|----------------|-----|
| Okuyucu taban sınıf | `C00D` (abstract) | tipli erişimciler, cache'ler, exposure, MobileConfig anahtarı |
| Ana store | `C08J` (`extends C00D`, prefs `ab-props`) | beş varsayılan map'i tutar, tüm normal flag'leri okur |
| Pre-chatd store | `C0D9` (prefs `ab-prechatd-props`) | hesap bağlanmadan önce HTTP ile çekilen flag'ler |
| Özel store | `C0ER` (prefs `ab-private-abprop`) | cihaz üstü deney değerleri, `C08J` ile aynı varsayılanlar |
| Okuma seçenekleri | `C00F` (`AbPropsOptions`) | exposure modu + ilk erişimde sabitleme |
| Tipli descriptor'lar | `C054909t` ABPropBoolean, `C055109v` ABPropInt, `C1OT` ABPropFloat, `C055009u` ABPropString, `C055209w` ABPropJson | id + çağrı noktası varsayılanı |
| Sync yöneticisi | `C0D2` (`ABPropsManager`) | depolama, hash, refresh, yedek, pre-chatd güncelleme |
| İstek / yanıt | `C27646BzW` (istek), `C28894Cgv` (yanıt + hata) | `<iq xmlns="abt">` |
| Tetikleyici | `RunnableC48591z1` default dalı (log `MessageHandler/maybeGetNewAbProps`), `<... abprops/>` için `C1S0` handler'ı | bir fetch'in ne zaman gönderildiği |
| Grup props | `C41861nA` (`GroupAbPropsManager`), `C502324k` (tetikleyici), `C28900Ch1` (yanıt) | grup başına değerler |
| MobileConfig | `C053409d` (factory), `C054709r` (`InterfaceC054609q`), `C06510El` (Stable-ID tablosu), `C34081Wt` / `C34091Wu` (tipli lambda'lar), `C06460Eg`, `C053809h` (override tablosu), `CQN` + `C29448CqB` (fetcher), `C41251mA` (fetch koordinatörü) | native destekli motor, MEX fetch |
| Exposure | `C42831om`, `BxP`, `C27952CBv`, WAM event `C44051qo` (5504) | exposure key'leri |
| Offline AB | `C24976ApB`, `C27629BzE`, `C60839RQl`, `ON0` / `ON1` / `C53973OMy`, `ConfigVariable` | yerel deney ataması |
| Gözlemciler | `C0NE` (3 callback), 46 implementer, örn. `CY8` | değişen değerlere tepki verir |

Belirleyici noktalar:

- Flag id uzayı tek bir sayısal uzaydır (en yüksek id **39140**, varsayılanı olan 21.424 id). `C05Z.A00(n)`, `C1XG.A0I(n)`, IQ tip int'leri ve WAM id'leri farklı sayı uzaylarıdır (bölüm 12).
- Adlar istemciye hiç ulaşmaz. Ne varsayılan tablolarda, ne sync yanıtında (yalnızca `config_code`), ne de bir resource içinde yer alır.
- Üç paralel sync yolu vardır: `abt` IQ (kullanıcı düzeyi), `group=` ile `abt` IQ (grup düzeyi) ve MobileConfig MEX fetch (bölüm 4).

---

## 2. Flag modeli

### 2.1 Tipler ve varsayılan tablolar (found, `C08J`)

`C08J` constructor'ında beş değişmez map kurulur (`buildKeepingLast`, dolayısıyla decompile'daki tekrarlı put'lar zararsızdır). Sayılar map başına benzersiz id'lerdir:

| Tip | Map | `C00D` üzerindeki erişimciler | Id'ler | Örnek |
|-----|-----|-------------------------------|--------|-------|
| bool | `A1A()` | `A15(id)`, `A18(ABPropBoolean)`, `A0E(...)` | 16.668 (1.237 varsayılan `true`) | `9667` true |
| int | `A1C()` | `A0b(id)`, `A0f(ABPropInt)`, `A02(...)` | 3.530 | `996` 604800 |
| float | `A1B()` | `A0Z(id)`, `A0a(ABPropFloat)`, `A00(...)` | 177 | `31535` 0.0 |
| string | `A1E()` | `A0j(id)`, `A0n(ABPropString)`, `A08(...)` | 867 | `34350` regex |
| JSON | `A1D()` | `A0p(id)`, `A0r(ABPropJson)`, `A09(...)` | 182 | `21995` `{}` |

Hiçbir id iki map'te birden yer almaz. Statik literal okumalar (`A15(n)`, `A0b(n)`, `A0j(n)`, `A0Z(n)`, `A0p(n)`): `p000X` ve `com` içinde 16.355 çağrı noktası; descriptor okumaları bunlara ek olarak gelir (oluşturma noktaları: 492 ABPropBoolean, 482'si benzersiz, 259 ABPropInt, 30 ABPropFloat, 66 ABPropString, 12 ABPropJson).

Varsayılan çözümleme (found, `C00D.A0D`, `A01`):

| Adım | Kural |
|------|-------|
| 1 | değer bu process için bellekte cache'lenmiş |
| 2 | prefs `ab-props` içinde `String.valueOf(id)` anahtarı altında saklanan sunucu değeri |
| 3 | id'nin tipine ait map'teki varsayılan |
| 4 | bir ABPropX descriptor'ının çağrı noktası varsayılanı (yalnızca map'te giriş yoksa) |
| 5 | yok: `IllegalArgumentException("Unknown BooleanField: <id>")` (int: `Unknown IntField`) |

482 benzersiz ABPropBoolean descriptor'ının tamamı için id map'te mevcuttur ve descriptor'ın production varsayılanı map varsayılanına eşittir. ABPropBoolean'ın `debugDefaultValue` değeri 182 tanesinde production varsayılanından farklıdır, ancak `equals` / `hashCode` / `toString` dışında hiçbir yerde okunmaz (smali: `A02` alanına yalnızca `09t` içinde başvurulur; erişimciler yalnızca id ve production varsayılanını kullanır). Bu build'de çalışma zamanı etkisi yoktur.

### 2.2 Saklarken değer ayrıştırma (found, `C0D2.A00`)

| Id'nin map'i | Saklanış | Ayrıştırma |
|--------------|----------|------------|
| bool | `putBoolean` | `Integer.parseInt(config_value) != 0` (wire biçimi `"1"` / `"0"`) |
| int | `putInt` | `Integer.parseInt` |
| float | `putFloat` | `Float.parseFloat` |
| string | `putString` | olduğu gibi |
| JSON | `putString` | `new JSONObject(...)` ile doğrulanır; hata `ABPropsManager/invalid format for config; configCode=...` loglar ve prop saklanmaz |
| hiçbir map'te olmayan id | `putString` | string olarak saklanır; böyle bir id'nin tipli okuması varsayılana sahip değildir ve exception fırlatır (2.1 adım 5) |

WA Web tablosunun (bilinmeyen kodlar atılır) aksine, Android bilinmeyen kodları string olarak tutar (found).

### 2.3 Okuma seçenekleri (found, `C00F` = `AbPropsOptions`)

| Sabit | exposureOptions | firstAccessValue | Kullanım |
|-------|-----------------|------------------|----------|
| `A03` | WITH_EXPOSURE_LOGGING (1) | false | tüm düz okumalar için varsayılan (`A15`, `A0b`, ...) |
| `A02` | WITH_EXPOSURE_LOGGING | true | `A19(...)`, `A16`, MobileConfig bootstrap okumaları |
| `A06` / `A05` | WITHOUT_EXPOSURE_LOGGING (0) | false / true | `A00()` bunları türetir |
| `A04` | WITH_URGENT_EXPOSURE_LOGGING (2) | false | flag **24317** açıkken pre-chatd store |

`firstAccessValue = true`, process içinde okunan ilk değeri `C00D.A07` (ConcurrentHashMap) içinde sabitler; bu id'nin sonraki okumaları, bir sync'ten sonra bile sabitlenmiş değeri döndürür (found, `C00D.A0D`, `A0i`). Düz okumalar, her sync'ten sonra `A0s()` tarafından temizlenen `A0P` cache'ini kullanır.

### 2.4 Okuma yolu ve doğruluk kaynağı (found, `C00D.A07` smali; anahtarların adları kullanımdan çıkarıldı)

```
read(id)
  ├─ A14() true  (A0E && A0b && !A0S)  and A08 set  and MobileConfig context present
  │      └─► MobileConfig value via C34081Wt/C34091Wu  (Stable ID lookup, C054709r.B6F)
  └─ else
         ├─ legacy value: cache A0P ► prefs "ab-props" ► default map
         └─ if A0E && A0G (shadow): also read MobileConfig and compare (A0C)
```

| Alan | Kaynak | Anlam (inferred) |
|------|--------|------------------|
| `A0F` | pref `23048` (bool), yalnızca `C08J` | MobileConfig bu hesap için başlatıldı |
| `A0E` | `A0F` veya pref `27668` (int) > 0 | MobileConfig aktif (yalnızca `C08J`; `C0D9`, `C0ER` için false) |
| `A0b` | pref `24896` | MobileConfig doğruluk kaynağı |
| `A0S` | pref `25403`, `A0s()` içinde yeniden okunur | legacy yola geri dönüş override'ı |
| `A0G` | pref `22646` | shadow karşılaştırma açık |
| `A0c` | pref `38895` == 1 | MobileConfig değerleri için okuma başına cache `A0d` |
| `A08` | AtomicBoolean, `C054709r.BN4` (MobileConfig init) içinde set edilir | MobileConfig hazır; MobileConfig yolu ancak o zaman izlenir (found); constructor'da false'a sıfırlanır |

Altısı da kendileri birer AB prop'tur ve constructor sırasında doğrudan prefs dosyasından okunur (found). Shadow modu bir karşılaştırma kaydı `N25` oluşturur ve flag **22647**'de (varsayılan 10) 1/N örneklenen bir field-stats event'i (`C56612Vl`, değer `mobile_config_inconsistent_value`) gönderir (found). MobileConfig kaynak olduğunda ve bir id'nin Stable ID'si yoksa, tipli lambda varsayılan map değerini değil, değer kaynağı `INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP` ile `false` / `0` / `""` döndürür (`C34081Wt` içinde found; yalnızca varsayılanı olan 70 id üzerindeki etki inferred).

---

## 3. MobileConfig katmanı

### 3.1 Stable ID'ler (found, `C06510El.A0J`)

Config code ile indekslenen `long[39141]`, 21.380 sıfırdan farklı giriş. `C054709r.B6F(id)` girişi döndürür (0 = yok). 21.354 id hem varsayılan map'lerde hem bu tabloda bulunur; 70 id yalnızca varsayılanda, 26 id yalnızca Stable-ID'de bulunur.

| Bitler | Alan | Kanıt |
|--------|------|-------|
| 0-15 | slot indeksi | `C053809h.A00`: `j & 65535`; anlamı inferred |
| 32-47 | config indeksi, `0..20780`, id sırasına göre her giriş için bir tane | `C06460Eg.A00`: `(j >>> 32) & 65535`, `C053409d.A08(int)` |
| 48-53 | değer tipi: 1 bool, 2 int, 3 string veya JSON, 4 float | varsayılan map'lerle çapraz tablo, istisnasız |
| 54-59 | unit tipi: 1 SESSIONLESS (564 id), 2 SESSIONBASED (20.781), 6 GROUP (35) | çapraz tablo; bölüm 3.2 |
| 60-63 | bool varsayılanı `true` ise ve yalnızca o zaman değer `2` | 1.231 id'nin 1.231'i; 6 true-varsayılanlı id'nin Stable ID'si yok |

### 3.2 Unit tipleri ve `params_map_v4_u*` (found)

`assets/params_map_v4_u<N>.txt`, `N` = MobileConfig unit tipi (`AbstractC24817AmY.A00`) olmak üzere `N3E` tarafından yüklenir: 0 NULL_VALUE, 1 SESSIONLESS, 2 SESSIONBASED, 3 PAGEID, 4 ADMINID, 6 GROUP, 7 FAMILY_DEVICE_ID, 8 FRLID, 9 AD_ACCOUNT_ID, 10 WEARABLE_DEVICE_OWNER_ID. Sonek unit tipidir, değer genişliği değildir. Native kütüphane aynı format string'ini taşır: `params_map_v4_u%d.txt` (`libmobileconfig-jni.so`).

| Dosya | Unit | Giriş | Sürüm anahtarı | WA kod aralığı içindeki id'ler |
|-------|------|-------|----------------|-------------------------------|
| `u1` | SESSIONLESS (login öncesi kullanılabilir) | 575 | 565 | 564 |
| `u2` | SESSIONBASED | 20.844 | 20785 | 20.781 |
| `u4` | ADMINID | 72 | 2 | 0 (id'ler 112607..121623) |
| `u6` | GROUP | 35 | 35 | 35 |

Giriş (8 bayt, iki little-endian u32, header düzeni dosyadaki gibi: magic `v4`, `0x7fff` kontrolü, sürüm anahtarı, sayı, 32 karakterlik hash):

| Alan | Bulgu |
|------|-------|
| `int2 >> 12` | WA config code: `u1`/`u2`/`u6` için Stable-ID tablosu (564 / 20.781 / 35 eşleşme) ve varsayılan map'lerle eşleşir; alt 12 bit birkaç giriş dışında hepsinde 0 |
| `int1` alt 16 bit | değer tipi maskesi: `0x881` bool, `0x1001` int, `0x1801` string/JSON, `0x2001` float (`u2`); bit 15 tam olarak `true` bool varsayılanlarında set (25 + 1.206 = 1.231) |
| `int1 >> 16` | ardışık slot numarası (inferred) |
| `u4` id'leri | WA kod aralığı dışında; amacı unknown |

`int1`'in alt 9 biti yalnızca 1 veya 129'dur; parametre id'si değildir.

35 GROUP id'si (found): 18205, 23245, 23246, 23397, 23398, 24075, 26013, 26269, 26270, 26862, 27009, 27025, 27247, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 33673, 34075, 34277, 34333, 35211, 35227, 35639, 35772, 36156, 36504, 36505, 37523, 37524, 38082, 38083. Flag **18205** `GroupAbPropsManager` tarafından grup başına okunur (bölüm 4.7).

### 3.3 MEX üzerinden MobileConfig fetch (found, `CQN`, `C29448CqB`)

MEX mutation `MetaConfigFetchMutation`, schema `whatsapp-android-www`, doc_id **28207206725568030**, root field `xwa2_mobile_config_fetch`. `CQN` içinde set edilen input alanları: `api_version`, `fetch_type`, `unit_type`, `unit_id`, `device_id`, `query_hash`, `query_string`, `bln_queries`, `mc_debug_id`, `mobile_app_universe_type`; okunan yollarda her zaman null: `batch_size`, `bln_li_hashes`, `bool_opt_policy`, `contact_point`. Log: `WAMobileConfigFetcher/fetchWwwConfigs/request unit_type=...`. Yanıt: native yöneticiye verilen bir config blob'u (`onComplete(true, blob)`), ayrıca `ep_refresh_id` ve `ab_key`. `ab_key`, `mc_expo:sys:ab_key` olarak saklanır.

`C41251mA` (`MobileConfigFetchCoordinatorImpl`), bu fetch'in bir AB-props fetch'inden sonra ne zaman çalışacağına karar verir: ABPropInt **36185** (varsayılan 0) seçeneği belirler: değer 2 offline resume'u bekler (`waiting for offline resume`), diğer her değer hemen fetch eder; değer 1, saklanan unit başına fetch sürümünü `abprops` sürümüyle karşılaştırır (`C054709r.A01`), bir delta isteği en son handle'ın uygulama sürümünü `2.26.41.6` ile karşılaştırır. `C054709r.CpO`, `updateConfigs` çağırır, callback logu `WAMobileConfigFetcher/updateConfigs() callback: succeeded=`; başarı `last_full_fetch_ms:<unit>:<key>` saklar.

Login'in `<success>` stanza'sı da `props` ve `abprops` yanında `mc_ep_version` (MobileConfig'in emergency-push sürümü) taşır (found, `HandlerThreadC12340b0`); tüketicisi izlenmedi.

---

## 4. Props sync

### 4.1 İstek (found, `C27646BzW.A00(boolean force, boolean delta, int refreshId)`)

```xml
<iq to="s.whatsapp.net" type="get" id="..." xmlns="abt">
  <props protocol="1" hash="<stored config_hash | empty>" [refresh_id="<last_version>"]/>
</iq>
```

| Öznitelik | Kural |
|-----------|-------|
| `protocol` | sabit `1` |
| `hash` | saklanan `ab_props:sys:config_hash`; `force` veya `delta` set ise ya da hiçbir şey saklı değilse boş string |
| `refresh_id` | yalnızca `delta` set ve `refreshId > 0` ise; değer = saklanan `ab_props:sys:last_version` |
| gönderim | `MessageClient.A0W(callback, node, id, 220, 32000L)`: IQ request-type int 220, timeout 32.000 ms |

### 4.2 Yanıt (found, `C28894Cgv.CFS`)

```xml
<iq type="result"><props ab_key="..." hash="..." refresh="86400" refresh_id="N" [delta_update="true"]>
  <prop config_code="20548" config_value="1" config_expo_key="..."/>     <!-- one per changed flag -->
  <prop event_code="1094" sampling_weight="N"/>                         <!-- event sampling, no config_code -->
</props><erid>...</erid></iq>
```

| Öğe | İşleme |
|-----|--------|
| `config_code` + `config_value` | 2.2'ye göre tipli saklama, anahtar `String.valueOf(code)` |
| `config_expo_key` | boş değilse ve değer saklandıysa `<code>_expo_key` olarak saklanır (hesabın içinde bulunduğu deneyin / grubun exposure key'i; key biçimi unknown) |
| `ab_key` | `ab_props:sys:config_key` olarak saklanır; MobileConfig kaynak değilken WAM attribute **4473** olarak set edilir (her iki kanal) |
| `hash` | tüm setin içerik hash'i; `ab_props:sys:config_hash` olarak saklanır; hash'siz ve `delta_update`'siz bir yanıt hiçbir değeri değiştirmez |
| `refresh` | saniye, varsayılan 86400; `ab_props:sys:refresh` içinde x 1000 ms olarak saklanır, alt sınır 600.000 ms; delta tarafından güncellenmez |
| `refresh_id` | setin sürümü; `ab_props:sys:last_version` olarak saklanır (delta sonrasında da) |
| `delta_update="true"` | mevcut prefs'e birleştirilir; hash, key, refresh ve `last_refresh_time` olduğu gibi bırakılır |
| hash mevcut | önceki prefs `ab-props-backup`'a kopyalanır (önce temizlenir) |
| tam güncelleme (hash mevcut, delta değil) | store temizlenir (`refresh` ve `last_exposure_keys` korunur), tüm props yazılır |
| `event_code` + `sampling_weight` | `config_code`'suz satırlar; prefs `field-stats-events-sampling` içine yeniden yazılır (key = event code, değer = weight); kod **1094** ayrıca `app_launch_event_sampling_weight` set eder |
| `<erid>` | şifreli rid: flag **3664** açıkken temizlenir, **6084** açık ve değer değişmişse `encrypted_rid` olarak saklanır |

Başarılı bir tam güncellemeden sonra: `last_refresh_time` = şimdi (ms), `fetch_app_version` = `2.26.41.6`, hata sayaçları sıfırlanır, gözlemciler bilgilendirilir (4.8).

### 4.3 Tetikleyiciler (işaretlenmedikçe found)

| Tetikleyici | Koşul |
|-------------|-------|
| login `<success abprops="N">` (ayrıca `props`, `mc_ep_version`) | sürüm `N` > saklanan `last_version`: `force` + `delta` + `refresh_id` ile istek; mod DELTA (log `versionMismatch`) |
| aynı yol | `last_refresh_time + refresh < now` veya `now < last_refresh_time` (saat geri alındı; dal smali'de okundu, decompile else'i atlıyor): saklanan hash ile normal istek; mod FULL (log `AB Props too old`) |
| gelen `<... abprops/>` child'ı (`log` ve `push-config` child'larıyla yönlendirilir; parent `ib` inferred) | `forceFetchABPropsAndMobileConfig`: mesaj gönderimi hazır olduğunda `A00(true, false, 0)` (boş hash, full); ardından MobileConfig `BMu` + `CpO` |
| kayıt | pre-chatd fetch (4.6); offline atama (6) |

### 4.4 Refresh aralığı ve hatalar (found)

| Öğe | Değer |
|-----|-------|
| varsayılan aralık | `ab_props:sys:refresh` varsayılanı 86.400.000 ms |
| sunucu `refresh` | saniye, x 1000, alt sınır 600.000 ms |
| sayılan hata kodları | 207, 304, 400-503 (`C28894Cgv.Brt`); diğer kodlar yalnızca `unknown error code` loglar |
| yeniden deneme muhasebesi | hata başına `fetch_attemp_count` +1; 3'te `last_refresh_time` = şimdi ve sayaç sıfırlanır, böylece sonraki deneme bir aralık bekler |
| son hata | `ab_props:sys:last_error_code`, başarıda temizlenir |
| teslim hatası (`Bog`) | no-op |

### 4.5 Fetch penceresi sırasındaki okumalar

`<props>`, ilk ekranlar flag'leri okuduktan sonra gelebilir. Veri mevcut olmadan bir id'nin ilk okuması varsayılanı kullanır; `firstAccessValue` sabitlemesiyle (2.3) sabitlenen varsayılan process boyunca kalır (found); kayıt ekranları online props için bir timeout ile bekler (log string'leri `RegisterPhoneViewModel/cancelOnlineAbPropsTimeout`, `OnlineAbpropsAsyncStatus`, found; tam bekleme süresi unknown).

### 4.6 Pre-chatd props (found, `C44707Jfc`, `C43414Iwr`, `K49`, `C0D2.A08`)

Hesap bağlanmadan önce kayıt HTTP istemcisi, `ab_hash` (pref `pref_pre_chatd_ab_hash`) ile `checkPreChatdABProps` (`reg-onboard-abprop-request`) çağırır. Sonuç yeni bir hash, `{config_code, config_value, config_expo_key}` içeren bir `expConfigs` JSON dizisi, bir `ab_key` ve bir sonraki fetch gecikmesi taşır (`pref_pre_chatd_ab_next_fetch_time` = şimdi + gecikme). `C0D2.A08` pre-chatd store'u temizler (`A04`) ve aynı tipleme kurallarıyla (2.2) prefs `ab-prechatd-props` içine yeniden yazar. Exposure `pref_expo_keys` içinde tutulur (`<expo_key>,<timestamp>` JSON dizisi) ve WAM 5504 ile değil, kayıt funnel logu (`abprop_exposure` / `ab_prechatd_exposure`, `ab_key` ile birlikte `pref_pre_chatd_ab_key`'den) üzerinden gönderilir. Pre-chatd okumaları flag **24317** açıkken `A04` (urgent) seçeneklerini, aksi halde `A03` kullanır.

### 4.7 Grup düzeyi props (found, `C41861nA`, `C502324k`, `C28900Ch1`)

```xml
<iq to="s.whatsapp.net" type="get" xmlns="abt"><props group="<group jid>" hash="<cached | empty>"/></iq>
```

4.1 ile aynı tip 220 ve 32.000 ms. İstek öznitelik dizisi iki girişe sahiptir: `group` ve `hash` (smali). Geçit: flag **16206** (master) ve açılan bir grup konuşması (`COK` / `Bnc`); `_nextRefreshTimeInSeconds`'a kadar `reason=cacheValid` ile veya `reason=disabled` ile atlanır. Yanıt: `hash`, 600..604.800 s aralığına sıkıştırılmış `refresh` (varsayılan 86.400), `refresh_id`, `<prop config_code config_value config_expo_key>`, aynı varsayılan map'lere göre tiplenir (bool, int, float, aksi halde string). Id'ler paylaşılan id uzayındadır; GROUP unit tipi (3.2) bunun için tasarlanmış 35 id'yi işaretler ve bir grup için okunan flag `A04(groupJid, id)`'dir. Grubun saklı değeri yoksa okumalar `null` döndürür (çağıran o zaman fallback yapar, izlenmedi). Grup prefs'indeki key'ler (`groupAbProps`, ad `C00E`'den inferred): `<jid>_<id>_value`, `<jid>_<id>_exposureKey`, `<jid>_exposureKeysSet`, `<jid>_nextRefreshTimeInSeconds`, `<jid>_lastRefreshHash`. Grup değerleri için JSON tipi yoktur.

### 4.8 Gözlemciler (found)

`C0NE` üç callback'e sahiptir: yeni değerler yazılmadan önce `BhX` (event 34), yazıldıktan sonra `Bfk` ve `C2K` (event 33, 32). Örnek `CY8` (`PQKeysUploadABPropsObserver`): `BhX` içinde flag **21198**'i hatırlar; `Bfk` içinde `true`'dan `false`'a geçtiyse `PQ_KEYS_UPLOAD_CODE changed from true to false, deleting all kyber prekeys` loglar ve `DeleteKyberPreKeysJob` kuyruğa alır. `C0NE`'yi 46 sınıf implemente eder (grep sayısı).

---

## 5. Cihazda depolama

| Prefs dosyası / key | İçerik |
|---------------------|--------|
| `ab-props` (`C08J`, `C0D2.A00`) | `<id>` değeri, `<id>_expo_key` ve aşağıdaki `ab_props:sys:*` key'leri |
| `ab_props:sys:config_hash`, `config_key`, `last_version`, `refresh`, `last_refresh_time`, `fetch_app_version`, `fetch_attemp_count`, `last_error_code` | sync durumu |
| `ab_props:sys:last_exposure_keys` (string set), `last_daily_expo_key_update` | exposure durumu |
| `ab_props:sys:private_experimentation_id` | cihaz üstü deneyler için rastgele id (6) |
| `ab_offline_props:offline_exposure_strings`, `ab_offline_props:offline_exposure_hash_strings` | offline-deney exposure'ı (`ab-props` içinde) |
| `ab-props-backup` | önceki store'un kopyası, her tam güncellemede yeniden yazılır |
| `ab-prechatd-props` | pre-chatd değerleri artı `pref_expo_keys` |
| `ab-private-abprop` | `last_read_time_ms` (en fazla saatlik güncellenir) ve özel değerler |
| `mc_expo:sys:ab_key`, `mc_expo:sys:last_exposure_keys`, `mc_expo:sys:last_exposure_keys_without_logging` | MobileConfig tarafı exposure durumu |
| `field-stats-events-sampling` | event code'dan sampling weight'e |
| `groupAbProps` | grup değerleri (4.7) |
| `<dataDir>/mobileconfig/mc_overrides.json`, `id_name_mapping.json` | MobileConfig override tablosu, id-ad eşlemesi (dosya adları `C053409d` içinde found; APK'da yok) |
| `pref_pre_chatd_ab_hash`, `pref_pre_chatd_ab_key`, `pref_pre_chatd_ab_next_fetch_time`, `pref_is_blocking_prechatd_exposure` | pre-chatd durumu (kayıt prefs'i) |

Tüm dosyalar `C00S.A05(name)` üzerinden açılır (uygulamaya özel veri dizininde bir `SharedPreferences` handle'ı); bu factory'nin şifreleme veya obfuscation ekleyip eklemediği kontrol edilmedi (unknown).

---

## 6. Exposure, deneyler, gruplar

### 6.1 Exposure loglama (found)

| Adım | Ayrıntı |
|------|---------|
| 1 | exposure loglamalı bir okuma (2.3) `A0B(options, this, "<id>_expo_key")` -> `A12` çağırır |
| 2 | `last_exposure_keys` içinde henüz olmayan boş olmayan expo key: eklenir ve kalıcılaştırılır |
| 3 | ana store: `C42831om.A01`, en az 1 sn debounce ile WAM event **5504** `WamWefrClientExposure` (`wam_wefr_client_exposure`) gönderir; `BxP`, virgülle birleştirilmiş key'lerle WAM runtime'ı çağırır (`C0D6.CYl(value, 5029, ...)`; "attribute" çağrı biçiminden inferred) (flag **31830** açıkken kaynak başına birleştirme) |
| 4 | tam sync sonrasında yalnızca yeni yanıtın hâlâ taşıdığı key'ler sette kalır |
| 5 | günlük yeniden gönderim: foreground callback `A0A0.BvR` üzerinde, `last_daily_expo_key_update`'ten bu yana 24 saatten fazla geçtiğinde (`sent_with_daily` = true) |
| 6 | pre-chatd: `C27952CBv` pulse thread'i funnel logunu gönderir (4.6); URGENT modu bunu hemen tetikler |

WAM 5504 alanları (Falco adları): `dedup_key`, `device_exp_id`, `exposure_key`, `from_metaconfig`, `sent_with_daily`. `device_exp_id`, cihaz kimliği nesnesinden (`C09E.A0J().A03()`) türetilen bir string'dir; türetme izlenmedi (unknown).

### 6.2 Deney ve grup id'leri

| Id | Nerede | Anlam |
|----|--------|-------|
| `config_expo_key` | `<prop>` başına | deney kolunun exposure key'i; istemci için opak, yalnızca karşılaştırılır ve loglanır |
| `ab_key` | `<props>` özniteliği | atanan setin tamamının key'i; WAM attribute 4473 |
| `refresh_id` | `<props>` özniteliği | setin sürümü; login `<success>`'ın `abprops` değeriyle karşılaştırılır |
| `hash` | `<props>` özniteliği | "değişiklik yok" için kullanılan içerik hash'i |
| `private_experimentation_id` | yerel | cihaz üstü deneylerde unit olarak kullanılan rastgele id |
| `device_id`, `unit_id` | MEX fetch | MobileConfig unit kimliği |

Sunucu tarafı hedefleme (ülke, kohort, yüzde) görünmez; istemci yalnızca ortaya çıkan değerleri görür (unknown).

### 6.3 Sampling weight'ler (found)

`<prop event_code sampling_weight>` satırları field-stats logger'ı besler: event başına 1/N örnekleme weight'i. Event **1094** (app launch) `app_launch_event_sampling_weight`'e yansıtılır. Key bir flag id'si değil, bir WAM event code'udur.

---

## 7. Yerel değerlendirme, override'lar, debug yolları

### 7.1 Offline AB (found, `C24976ApB`, `C27629BzE`, `C60839RQl`)

APK içine derlenmiş deneyler (`C60839RQl.A00`, `ON0` -> `ON1` -> `C53973OMy` -> `ConfigVariable{id, name, value, type}` listesi) yerel bir user-info map'ine karşı değerlendirilir ve aynı tipleme kurallarıyla `ab-props` store'una yazılır. Koşullar (`RM2` ağacı) yalnızca `platform`, `app_version`, `app_build`, `release_channel`, `os_version` özelliklerini kullanabilir (`C0ER.A0B`). User-info key'leri: `device_id`, `app_build`, `release_channel`, `app_version`, `os_version`, `platform`, `country` (SIM ülkesi), `private_experimentation_id`. Bu beta'da `app_build` ve `release_channel` sabit `beta`'dır. Atamada sync key'leri (`config_hash`, `last_refresh_time`, `fetch_app_version`, `last_version`) kaldırılır, böylece sonraki online fetch full olur ve atama `registration_state == 3` iken gerçekleşirse kritik bir log `abprops-offline-assigned-after-registration-verified` tetiklenir. Deney tanımları burada sıralanmadı (unknown).

### 7.2 MobileConfig override'ları (found, etki inferred)

`C053809h`, `mc_overrides.json` dosyasını yükler (`hasOverridesFile`, `boolOverrideForParam`, `intOverrideForParam`, `stringOverrideForParam`, `doubleOverrideForParam`, paketlenmiş 64-bit Stable ID ile anahtarlanır), `C053409d.getOrCreateOverridesTable` bunu motora döndürür. Override'lar yalnızca MobileConfig yolu için geçerlidir, legacy prefs yolu için değil. Motorun bir release build'de tabloya başvurup başvurmadığı unknown; çalışma zamanı testine dair kanıt yok.

### 7.3 `override-abprops` deep link (found)

Manifest host'u `whatsapp-consumer://override-abprops` (exported `DeepLinkActivity` alias). `IJB` bunu hedef id 154'e eşler. `DeepLinkActivity.A0w`, `bugbash` path segmentini ve `feature_name`, `feature_id`, `category`, `min_app_version`, `ready_to_test_time` ve `variants` (`{label, abprops:[{abprop_key, abprop_value}]}` içeren base64 JSON dizisi) sorgu parametrelerini `BugBashSession` / `BugBashVariant` içine ayrıştırır. Bir hata nedeni `abprop_override_not_allowed` mevcuttur. `abprop_key` / `abprop_value` değerlerini herhangi bir prop store'una yazan kod bulunmadı: `BugBashVariant`'a yalnızca ayrıştırıcı ve serializer'ı başvurur ve `bugbash_session` yalnızca okunur (`C51723Mxj`). Geçit koşulu ve uygulama yolu unknown.

### 7.4 Diğer

| Yol | Ayrıntı |
|-----|---------|
| ABPropBoolean `debugDefaultValue` | tanımlı (182'si farklı), hiç okunmaz (2.1) |
| Debug UI | `com.whatsapp.backup.debugscreen.BackupAbPropsUiState` (yalnızca sınıf adı, backup debug ekranı) |
| Okuma başına profiler | prefs `31165` (int) ve `32010` (bool) `C00D.A0H/A0I/A0J` ve bir sayaç sınıfını (`Pr8`) besler; amaç çözülmedi |

---

## 8. Diğer raporlarda anılan flag id'leri (2.26.41.6'da doğrulandı)

Her id varsayılan map'lerde ve Stable-ID tablosunda arandı. Tipler map tipleridir.

| Rapor | Sonuç |
|-------|-------|
| `WA_BAN_SYSTEM_DEEP_EN.md` | 11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 mevcut, bool varsayılan false; 12840 ve 20278 **JSON** map'leridir (varsayılanlar eşleşiyor); 31535 / 31536 **float**, varsayılan 0.0. **34166 bir flag değildir**: varsayılanı yok, Stable ID'si yok; `ContactInfoActivity.A0K = C1XG.A0I(34166)` bir injection id'sidir (komşuları 34165, 34168, 34169 aynı türdendir). 2923 yok (raporlandığı gibi) |
| `WA_TCTOKEN_CSTOKEN.md` | 16 id'nin tamamı mevcut; varsayılanlar: 996 / 865 / 26897 = 604800, 997 / 909 = 4, 3802 / 22012 = 26, 4063 = 0, 20606 = 2000, tüm bool id'ler false. `299`, privacy-token IQ'sunun IQ request-type int'idir, flag değildir |
| `WA_META_AI.md` | 25119, 26189, 27083, 37227, 37852, 37054 bool false; **26190 JSON**, varsayılan `""` |
| `WA_USERNAME.md` | 18'inin tamamı belgelenen varsayılanlarla mevcut; **34350 bir string map girişi** (regex), **21995 bir JSON map girişi** |
| `WA_USYNC.md` | 21 flag id'sinin tamamı belgelenen varsayılanlarla mevcut (730 = 35, 471 = 1140, 9667 / 33609 / 20988 = true) |

Aynı kod uzayı WA Web'de de görünür: herkese açık WA Web prop tablosundan bilinen 11 prop adı için Android girişi aynı koda, tipe ve varsayılana sahiptir (örn. 22797 JSON `{}`, 32276 string `info_card, list_card`, 26270 int 1209600, 35639 int -1, 12539 bool true, 25071 / 1133 / 23245 / 28357 / 27009 / 6939 bool false) (Android tarafı için found, "aynı prop" için inferred). Yalnızca Web'de bulunan id'lerin (3042, 30590, 24037, 25322) Android varsayılanı yoktur. 16 Web grup düzeyi id'sinden 12'si Android GROUP unit id'leridir (3.2).

---

## 9. Adlandırma ve kategoriler

| Konu | Bulgu |
|------|-------|
| Adlar | dex veya asset'lerde okunabilir ad tablosu bulunamadı (iki bilinen legacy flag adı için yapılan arama yalnızca log string'leriyle eşleşti); `id_name_mapping.json`, `C053409d` içinde yalnızca bir çalışma zamanı dosya adıdır |
| Loglardaki adlar | birkaç log string'i adları yeniden kullanır: `PQ_KEYS_UPLOAD_CODE` (21198), `abprop_override_not_allowed`; eski build'lerden veya WA Web'den gelen adlar semantiğe giden tek yoldur |
| Kategoriler | kategori alanı yok. Yapı unit tipinden (SESSIONLESS 564, SESSIONBASED 20.781, GROUP 35) ve değer tipinden gelir |
| En çok okunan | en çok okunan literal id'ler: **20548** (bool true, 511 nokta), **9970** (false, 312), **1107** (false, 151), **12267** (true, 147), **1600** (string `{"allowed_product_type":"none"}`, 146), **27008** (false, 104), **13989** (int 7, 87). Semantik çözülmedi |

---

## 10. Alana göre flag kataloğu (varsayılanlar `C08J` içinde found; kullanım diğer raporlardan okundu ve burada yeniden kontrol edildi)

### 10.1 Sync ve MobileConfig altyapısı

| Flag | Tip | Varsayılan | Kontrol ettiği |
|------|-----|------------|----------------|
| **23048** | bool | false | MobileConfig başlatıldı (`A0F`) |
| **27668** | int | 0 | `AbstractC06100Cm.A0E`; > 0 MobileConfig'i etkinleştirir (`A0E`) |
| **24896** | bool | false | MobileConfig doğruluk kaynağı (inferred) |
| **25403** | bool | false | legacy kaynağa geri dönüş (inferred) |
| **22646** | bool | false | shadow karşılaştırma |
| **22647** | int | 10 | shadow-log örneklemesi |
| **38895** | int | 0 | `== 1`: okuma başına MobileConfig cache'i |
| **26524**, **28443**, **30441**, **30556** | bool | false | MobileConfig factory seçenekleri (`CbW`, `BMu`) |
| **26525** | int | 600 | MobileConfig factory seçeneği (`CbW`), birim çözülmedi |
| **26640** | bool | false | MobileConfig init parametresi (`BN4`) |
| **35778** / **36185** | int | 0 | init fazı / fetch zamanlama seçeneği (`C054709r.APn`, `C41251mA.A00`) |
| **24317** | bool (SESSIONLESS) | false | pre-chatd okumaları urgent exposure kullanır |
| **31830** | bool | false | exposure attribute 5029'un kaynak başına birleştirilmesi |
| **16206** | bool | false | grup props'un master geçidi |
| **18205** | bool (GROUP) | false | `GroupAbPropsManager` içinde grup başına okuma |
| **3664** / **6084** | bool | false | `encrypted_rid`'i temizle / set et |
| **21198** | bool | false | `PQ_KEYS_UPLOAD`: Kyber prekey yüklemesi; `true`'dan `false`'a geçiş bunları siler |

### 10.2 Ban ve bütünlük (`WA_BAN_SYSTEM_DEEP_EN.md`)

11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 (bool false); 12840 (JSON `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}`); 20278 (JSON `{"max_messages": 10000, "farthest_time_days": 30}`); 31535 / 31536 (float 0.0).

### 10.3 Privacy token ve cstoken (`WA_TCTOKEN_CSTOKEN.md`)

| Flag | Tip | Varsayılan |
|------|-----|------------|
| **996** / **997** | int | 604800 / 4 |
| **865** / **909** | int | 604800 / 4 |
| **4063** | int | 0 |
| **3802** / **22012** | int | 26 / 26 |
| **20605** / **14303** / **15491** | bool | false |
| **20606** | int | 2000 |
| **24915** / **24941** / **18639** / **25253** | bool | false |
| **26897** | int | 604800 |

### 10.4 Meta AI, username, USync

| Rapor | Flag'ler (varsayılan) |
|-------|-----------------------|
| `WA_META_AI.md` | **26189**, **27083**, **25119** (okuyucu yok), **37227**, **37852**, **37054**: bool false; **26190** JSON `""` |
| `WA_USERNAME.md` | **4745**, **20189**, **23817**, **21199**, **16033**, **8421**, **12402**, **28678**: bool false; **21995** JSON `{}`; **20494** 3, **20459** 35, **34347** 4, **34348** 6, **28127** 30, **29327** 60; **34350** string `^([0-9]{4}\|[A-Z0-9]{6})$` |
| `WA_USYNC.md` | **5751**, **5839**, **20798**, **29769**-**29771**, **9732**, **33432**, **14565**, **26739**, **31261**: bool false; **9667**, **33609**, **20988**: true; **730** 35, **471** 1140, **37780** 0 |

### 10.5 Grup düzeyi (unit GROUP, 35 id)

Bool false: 18205, 23245, 23246, 26013, 26269, 26862, 27009, 27025, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 34075, 35211, 35772, 36156, 36504, 36505, 38082, 38083. Int: 26270 (1209600 s = 14 gün), 27247 (0), 23397 / 23398 / 24075 / 34277 / 34333 / 35227 / 35639 / 37523 / 37524 (-1). String: 33673 (`none`). 26270, 23245, 23246, 26269, 30905, 30906, 28357, 28358, 27009, 27025, 35639, 35772 için adlar WA Web'den gelir (grup geçmişi ve anket ayarları; inferred).

---

## 11. Baileys (`baron-baileys-v2`, `src/Socket/chats.js`)

| Konu | Baileys | Android 2.26.41.6 |
|------|---------|-------------------|
| kullanıcı isteği | `fetchABProps(protocol='1', hash, refreshId)`: `xmlns="abt"` içinde `<props protocol hash? refresh_id?>` | aynı biçim; `hash` her zaman mevcut (zorlandığında boş), `refresh_id` yalnızca delta ile |
| grup isteği | yalnızca `{ group }` | `group` + `hash` (smali, 2'lik dizi) |
| yanıt key'leri | `reduceBinaryNodeToDictionary(props, 'prop')`: `config_code` -> `config_value` sözlüğü | tipli store; `config_expo_key`, `event_code` satırları, `hash`, `refresh`, `refresh_id`, `delta_update` hepsi kullanılır |
| arama | flag adıyla (`abProps['stella_interop_enabled']`) | yalnızca sayısal kodla |
| legacy props | `fetchProps`: `xmlns="w"` `<props protocol="2" hash>` adlandırılmış props | builder bulunamadı; adlar yalnızca stanza token sözlüğünde görünür (`AbstractC40911lb`) |
| refresh | yok (bağlantı başına bir kez) | aralık + sürüm kontrolü + push |

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| `abProps['<name>']` `undefined` | `abt` yanıtı yalnızca `config_code` taşır | kodla anahtarla; kod uzayı bölüm 8'dekidir |
| sözlükte `undefined` bir key beliriyor | `event_code` / `sampling_weight` satırlarında `config_code` yok | `config_code`'suz satırları atla |
| eski değerler | hash / refresh / `refresh_id` işleme yok, delta yok | `hash`, `refresh`, `refresh_id` sakla; sonraki istekte `hash` ve `refresh_id` gönder |
| bool, truthy string olarak okunuyor | `config_value` `"1"` / `"0"` | tipe göre ayrıştır (`!= 0`) |

---

## 12. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| `ABPropsManager/onABPropError; unknown error code: N` | 207 / 304 / 400-503 dışında hata | yok; sayaç ilerlemez |
| 3 başarısız fetch, bir gün boyunca yeniden deneme yok | `fetch_attemp_count` 3'e ulaştı, `last_refresh_time` = şimdi | bir aralık veya login `abprops` sürüm artışını bekle |
| `AbPropProtocolHelper/onReceiveABProps failed to parse response` (`C49828Lvo`) | bozuk `<props>` | exception yeniden fırlatılır, store'a dokunulmaz |
| `ABPropsManager/invalid format for config; configCode=N; value=V` | sayısal olmayan int/float veya geçersiz JSON | o prop atlanır |
| `IllegalArgumentException: Unknown BooleanField: N` | map varsayılanı ve descriptor varsayılanı olmayan bir id'nin tipli okuması | varsayılan ekle; `N` bir config code'dur |
| MobileConfig okuması `false` / `0` / `""` döndürüyor | id'nin Stable ID'si yok (`INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`) | legacy yoldan oku |
| `WAMCEvaluation/invalid json format; key=N` | JSON flag değeri MobileConfig yolunda ayrıştırılamıyor | boş `JSONObject` döndürülür |
| `GroupAbPropsClient/malformedResponse ... noPropsChild` / `parseFailed` | `<props>`'suz grup yanıtı veya kötü ayrıştırma | grup değeri saklanmaz |
| `GroupAbProps/fetchSkip reason=cacheValid` / `disabled` | `_nextRefreshTimeInSeconds` öncesi / flag 16206 kapalı | yok |
| `ABPreChatdProps/exception ... error add expo key` | bozuk `pref_expo_keys` JSON | key eklenmez |

---

## 13. Temel ayrımlar

| Karıştırma | Ayrıntı |
|------------|---------|
| config code - injection id | `A15(20548)` bir flag'dir; `C05Z.A00(66)`, `C1XG.A0I(34166)`, `C00C.A02(61)` bağımlılık id'leridir |
| config code - IQ request type | `A0W(..., 220, 32000L)` (burada 220, privacy-token IQ'sunda 299) bir request-type int'idir |
| config code - WAM id'leri | 5504 bir event'tir, 5029 ve 4473 WAM attribute'larıdır, 1094 sampling satırlarında bir event code'udur |
| config code - Stable ID | kod (<= 39140) tabloyu indeksler; Stable ID 64-bit bir MobileConfig specifier'ıdır |
| `abt` IQ - `w` props - DB `props` tablosu | `abt` = sayısal AB props; legacy `w` props = adlandırılmış sunucu props'u; SQL tablosu `props` = yerel key-value store |
| kullanıcı props - grup props | aynı id uzayı, aynı map'ler; grup değerleri `groupAbProps` içinde group jid ile anahtarlanarak yaşar, unit GROUP |
| `ab_key` - `config_expo_key` - `hash` - `refresh_id` | set key'i / prop başına deney key'i / içerik hash'i / sürüm |
| login `abprops` - `<props refresh_id>` | sunucunun güncel sürümü - son yanıttan saklanan sürüm |
| MEX `MetaConfigFetchMutation` - `abt` | MobileConfig blob'u - legacy sayısal props; MobileConfig aktifken ikisi de çalışır |
| production varsayılanı - debug varsayılanı | yalnızca production varsayılanı okunur |
| ilk erişimde sabitleme - normal cache | sabitlenen değerler process sonuna kadar sync'lerden sağ çıkar |
| offline atama - online | offline deneyler aynı store'a yazar, ardından full online fetch'i zorlar |

---

## 14. Tam akış

```
[Server]            [Login]                 [C0D2 / C27646BzW]               [C08J reads]         [WAM]
   │ <success abprops=N props mc_ep_version>   │                                   │                 │
   ├──────────────────►│ N > last_version? or  │                                   │                 │
   │                   │ last_refresh+refresh<now                                  │                 │
   │                   ├──────────────────────►│ <iq xmlns=abt>                    │                 │
   │◄───────────────────────────────────────── │  <props protocol=1 hash [refresh_id]>             │
   │ <props ab_key hash refresh refresh_id [delta_update]>                          │                 │
   │   <prop config_code config_value config_expo_key/> ... <prop event_code sampling_weight/>      │
   ├──────────────────────────────────────────►│ typed store per id (bool/int/float/string/JSON)   │
   │                                           │ backup, hash, refresh, last_version, ab_key       │
   │                                           ├─ observers BhX ► write ► Bfk / C2K ──────────────►│
   │                                           │ A0s(): clear read cache                           │
   │                                           │                                   │                 │
   │ <ib><abprops/>  (force, empty hash) ─────►│                                   │                 │
   │                                           │                                   │                 │
   │                                      A15(id) / A0b(id) / A0j(id)...           │                 │
   │                                           │          cache ► prefs ► default map ► (descriptor)│
   │                                           │          MobileConfig path if A0E && A0b && !A0S   │
   │                                           │                                   ├ first read ────►│ 5504 exposure
   │                                           │                                   │ + 24 h resend   │ 5029, 4473
   │                                           │                                   │                 │
   │ MEX MetaConfigFetchMutation ◄─────────────┼── C41251mA (option 36185) ────────┤                 │
   │ xwa2_mobile_config_fetch {blob, ep_refresh_id, ab_key} ───► native MobileConfig, Stable IDs    │
   │                                           │                                   │                 │
   │ <iq xmlns=abt><props group hash> (group opened, flag 16206) ► groupAbProps ► A04(groupJid,id)   │
```

---

## 15. Unknown'lar

| Konu | Neden |
|------|-------|
| Flag semantiği | ad yok; semantik yalnızca bir çağrı noktası veya başka bir raporun çözdüğü yerlerde |
| Sunucu tarafı atama | hedefleme, rollout yüzdeleri, deney tanımları istemcide yok |
| `abprops` push child'ının parent stanza'sı | handler mesaj kodu 235 altında kayıtlı; `ib` inferred |
| Login `abprops` ile tetikleyicinin sürüm argümanı arasındaki bağlantı | tetikleyici bir `Integer` alır; login ayrıştırması bir `AtomicReference` set eder; bağlantı inferred |
| Release build'lerde MobileConfig `mc_overrides.json` | tablo kodu mevcut; uygulama kullanıcısı tarafından başvurulduğuna veya yazılabildiğine dair kanıt yok |
| `override-abprops` geçidi ve uygulama yolu | `abprop_override_not_allowed` nedeni mevcut; bir prop store'una yazan bir writer bulunamadı |
| `device_exp_id` türetmesi, `config_expo_key` biçimi | izlenmedi |
| Stable-ID bit 0-15, `u4` unit girişleri, `int1 >> 16` | anlamı çözülmedi |
| Prefs `31165`, `32010`, flag `35778`, `36185` değerleri 1 / 2 | kısmen okundu (`Pr8`, koordinatör) |
| MobileConfig altında yalnızca varsayılanı olan 70 id'nin davranışı | tipli lambda sıfır değerler döndürür (found); özellikler üzerindeki etki izlenmedi |
| Sunucu tarafı delta semantiği | bir delta'nın hangi props'u taşıdığı |
| Gerçek trafik ve canlı sunulan değerler | yalnızca statik analiz |
