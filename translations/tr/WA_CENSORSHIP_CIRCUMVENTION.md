<!-- src-sha1: 5428e0461d6ea8f961256e4ead0fe3df30ea4164 -->
# WhatsApp Sansür Aşma — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** chatd engellendiğinde Android bağlantı yedekleri: kullanıcı tarafından yapılandırılan WhatsApp Proxy (ayar arayüzü, depolama, paylaşım bağlantısı, chatd ve medya kullanımı), sunucu güdümlü proxy servisi (Psiphon tüneli, Voltron modülü, bölge ve VPN kapıları, PROXY v2 başlıklı SOCKS tüneli), yedek IP listesi (`<ib><fbip>`, `fbips` dosyası), engel kaldırma push'u (`fbips`, `unblocking_props`, `psl`), DNS yedek zinciri, kayıt röle sağlayıcıları ve yeniden deneme stratejileri, Tigon ve DGW rolleri, bağlantı durumu takibi ve tanılama, yeniden deneme etkileşimi, feature flag'ler, bulunmayan mekanizmalar, Baileys karşılaştırması

---

## 1. Bu derlemede bulunanlar

Tüm ifadeler derlenmiş APK'nın statik analizinden gelir; hiçbir şey ağ üzerinde yakalanmadı. Katmanlar: **found** = kodda veya kaynaklarda okundu, **inferred** = çıkarım yapıldı, **unknown** = çözümlenemedi. Gizlenmiş (obfuscated) adlar derlemeye özeldir ve 2.26.41.6 içinde yeniden çözümlendi. chatd taşıması, el sıkışma, host merdiveni ve backoff [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) içindedir ve burada tekrarlanmaz.

| Mekanizma | Durum | Giriş noktaları | Katman |
|-----------|-------|-----------------|--------|
| WhatsApp Proxy (kullanıcı tarafından yapılandırılan sohbet ve medya rölesi) | mevcut, kullanıcı arayüzü var, feature flag'li | `SettingsUserProxyActivity`, `SettingsSetupUserProxyActivity`, `C12660bX`, `C12690ba`, chatd dizisinin 12. adımı | found |
| Proxy servisi (Psiphon tüneli, Voltron modülü `proxyservice`) | mevcut, sunucu güdümlü, kullanıcı arayüzü yok | `C12760bh` (orkestratör), `C42448IfJ` / `S6G`, `ca.psiphon.PsiphonTunnel`, `ProxyServiceBroadcaster` | found; native kütüphane APK içinde yok |
| Yedek IP listesi | mevcut | `C40581l4` ve `C36821d6` içinde `<ib><fbip>`, dosya `fbips` | found |
| Sabit kodlu host-IP tablosu, host merdiveni | mevcut | `AbstractC47101wK` (18 host adı), `C37151de` | found |
| DNS yedek zinciri (platform / MNS, 8.8.8.8 ve 8.8.4.4'e UDP, sabit kodlu) | mevcut | `C36881dC`, `QG1` | found |
| Engel kaldırma push'u (`nt` = `unblocking`) | mevcut | `CLl` ayrıştırıcı, `C28139CLl`, `C28912ChD`, `C27946CBo` | found |
| Kayıt rölesi (cloud-function sağlayıcıları) ve yeniden deneme stratejileri | mevcut, yalnızca kayıt için | `res/raw/domain_fronting_providers.tsv`, `C45421Jrl`, `RetryingHttpClient` | found |
| chatd yedeği olarak Tigon / DGW | mevcut değil | DGW yedek yapılandırması var ama devre dışı derlenmiş | found |

Bu derlemede mevcut değil (derlenmiş Java, manifest ve kaynaklarda yokluk olarak bulundu; native kod incelenmedi):

| Bulunmayan | Kanıt |
|------------|-------|
| WebSocket, HTTP long-poll veya MQTT üzerinden chatd | Java'da `wss://` veya `/ws/chat` literali yok; `mqtt` yalnızca analitik ve DGW akış etiketlerinde geçer (bkz. Noise raporu bölüm 13) |
| Android `VpnService` | manifestte servis veya `BIND_VPN_SERVICE` yok; Psiphon yerel proxy modunda çalışır |
| chatd için kullanıcı tarafından yapılandırılabilir SOCKS veya HTTP-CONNECT proxy | 12. adım `host:chatPort` için doğrudan soket kurar, proxy el sıkışması yok |
| chatd için sistem proxy'si (`http.proxyHost`, `https.proxyHost`) | dizi veya soket kodu tarafından okunmaz; yalnızca Tigon ve bir koruma olarak okunur (bölüm 4.6) |
| chatd için domain fronting veya röle | sağlayıcı listesini yalnızca kayıt istemcisi kullanır (bölüm 7) |
| Tor, Snowflake, diğer takılabilir taşımalar | kod veya kaynak bulunamadı |

Raporun geri kalanını belirleyen noktalar:

- İki bağımsız proxy mekanizması vardır ve birlikte çalışmaz: kullanıcı proxy'si (12. adım, sonlandırıcı) ve Psiphon proxy servisi (adımların bir alt kümesi için doğrudan bağlantıların yerini alan SOCKS tüneli). Kullanıcı proxy'si ayarlıyken servis yapılandırması yok sayılır (`ConnectionSequence/socketConfigForUserProxy/skipping socks proxy in favor of user proxy`).
- Geçerli bir kullanıcı proxy'si varken dizinin tam olarak bir hedefi vardır. 12. adım 16'ya (tükendi) ilerler; doğrudan host'lara geri dönüş yoktur (found, `C37031dS.A0G`).
- `libgojni.so` indirilebilir modülün içinde teslim edilir. APK yalnızca modül manifestini içerir; tünel çevirme, protokol seçimi ve DPI karşıtı davranış unknown.

---

## 2. chatd bağlantı dizisindeki yeri

Adım numaraları Noise raporu bölüm 2.2'dekilerdir. Kaynak: `C37031dS.A0G`, `C37151de`, `C37061dV`.

| Koşul | Etki |
|-------|------|
| Debug adresi ayarlı | yalnızca 1. adım |
| Geçerli kullanıcı proxy'si (etkin, host geçerli, flag **2784**) | 0. adım 12'ye gider, o da sonlandırıcıdır; Psiphon yapılandırması yok sayılır |
| Kullanıcı proxy'si yok, Psiphon yapılandırması var (`C37061dV.A00 != null`) | 5, 8, 13. adımlar korunur; 6, 7, 9, 10, 11, 14, 15 atlanır (`ConnectionThread/Skipping sequence N due to active proxy`); 2, 3, 4 flag **23630** açık değilse atlanır |
| Kullanıcı proxy'si yok, Psiphon yapılandırması yok | değiştirilmemiş merdiven: 2, 3, 4, 5, 8, 9, [15], 13, 14, 6, 10, 7, 11 |

Atlama tablosu, `C37031dS.A0G` bytecode'undaki packed switch'tir (2 ile 15 arası adımlar tut / atla / flag'e bağlı olarak eşlenir). 8. adım yapılandırmasını proxy yapılandırması olmadan bir IP literalinden kurar; dolayısıyla proxy etkin bir çalıştırmada korunur ama muhtemelen doğrudan bağlanır (inferred). 5 ve 13. adımlar `C37151de.A03` üzerinden çözümlenir: Psiphon yapılandırması varsa ve kullanıcı proxy'si yoksa dönen soket yapılandırması `ProxyServiceConfig` (`C46661vS`) ve çözümlenmemiş bir host adı taşır, böylece DNS tünel çıkışında gerçekleşir (`DNSResolutionMethod` 7 `SOCKS_PROXY`, `C37181dh` içinde dahili kod 8).

Debug adresi yokken 0. adım sırası (found; 1. adım için çözülmüş Java dalı ters okunur, bytecode doğrular): kullanıcı proxy'si, sonra sunucunun verdiği override girdileri (2), sonra yapılandırılmış host dizesi (3), sonra 5.

---

## 3. WhatsApp Proxy (kullanıcı tarafından yapılandırılan)

### 3.1 Ayar girişi ve ekranlar (found)

| Ekran | Sınıf | İçerik |
|-------|-------|--------|
| Settings > Storage and data > Proxy | `SettingsUserProxyActivity` (manifest `com.whatsapp.settings.ui.proxy.*`, dışa açık değil) | `Use proxy` anahtarı, host satırı, sohbet ve medya durum satırları, paylaşım menü öğesi, bilgi metni (`Only use a proxy if you're unable to connect to WhatsApp. Your IP address may be visible to the proxy provider…`, bağlantı `whatsapp-proxy`) |
| Set up proxy | `SettingsSetupUserProxyActivity` | host girişi, `Ports (Optional)` altında `Chat port` (443 için `Default` gösterilir), `Media port` (587 için `Default`), `Use TLS`, kaydet düğmesi |
| Ayar arama girdisi | `C23869ARc` alt sınıfı `C215199Jq` | anahtar `proxy` |
| Silme | host satırında uzun basma (`ViewOnLongClickListenerC46012K9h`, `Delete Proxy?`), eylem `KZA` içinde | host'u temizler, medya portunu 587'ye ve TLS'yi true'ya sıfırlar, durumlar 0, `proxy_enabled` false |

Doğrulama: `K09.A01` (IP literal), `K09.A02` (isteğe bağlı `:port` ile host, regex `JRQ.A02`'den kurulur); hatalar `Enter a valid host`, `Enter a valid port`. IPv6 ayrıştırması `K09.A00` içinde vardır.

### 3.2 Depolama (found, `C12660bX`, `C12690ba`)

SharedPreferences dosyası `user_proxy_setting_pref`.

| Anahtar | Tür | Varsayılan | Kullanım |
|---------|-----|------------|----------|
| `proxy_enabled` | bool | false | anahtar durumu; yalnızca flag **2784** açıkken etkilidir (`C12690ba.A03`) |
| `proxy_ip_address` | string | yok | `host:chatPort` (`ProxySetting.A04`); port okunurken ayrıştırılır, varsayılan 443 |
| `proxy_media_port` | int | 587 | medya röle portu |
| `proxy_use_tls` | bool | true | sohbet soketi için TLS sarmalayıcı |
| `proxy_connection_status` | int | 0 | arayüzde gösterilen sohbet durumu (bölüm 3.5) |
| `proxy_media_connection_status` | int | 0 | arayüzde gösterilen medya durumu |

`ProxySetting` (`C45598Jv6`) = `domain`, `ip`, `chatPort`, `mediaPort`, `useChatTls`; IP literali olan bir host `ip`'ye, aksi halde `domain`'e gider. `C12660bX.A03()` onu yalnızca etkinse, flag **2784** açıksa ve host veya IP geçerliyse döndürür; bağlantı dizisinin aldığı nesne budur.

### 3.3 Paylaşım ve içe aktarma bağlantısı (found)

Paylaşım: menü öğesi `https://wa.me/proxy?host=<host>&chatPort=<n>&mediaPort=<n>&chatTLS=<true|false>` adresini, konu `WhatsApp Proxy` ve metin `Connect to WhatsApp using proxy. <url>` ile oluşturur.

İçe aktarma: `DeepLinkActivity` (tür `DEEP_LINK_PROXY`, log öneki `PROXY:`) flag **2784** gerektirir, `proxy_has_segments` red nedenine sahiptir (koşul addan çıkarıldı, inferred), ardından `SettingsSetupUserProxyActivity` etkinliğini `intent_host_name`, `intent_chat_port`, `intent_media_port`, `intent_use_tls`, `source=deeplink` extra'larıyla başlatır.

| Sorgu | Ayrıştırma | Varsayılan |
|-------|------------|------------|
| `host` | string | yok |
| `chatPort` | int | 443 |
| `mediaPort` | int | 587 |
| `chatTLS` | yok, `true` veya `1` true verir; başka her değer false | true |

İçe aktarma yalnızca kurulum ekranını önceden doldurur; kaydetmek yine kullanıcı gerektirir (found). `DeepLinkActivity` işleyicisi bytecode'dan okundu (Java'ya çözülmemiş).

### 3.4 chatd tarafından kullanımı (found)

12. adım (`C37151de.A02` case 12): host = `domain` veya `ip`, port = `chatPort`, TLS biti = `useChatTls`. Host normal çözümleyici zincirinden geçer (bölüm 6). Noise el sıkışması ardından bu soket üzerinde çalışır (`useChatTls` ise TLS içinde). Proxy'yi kaydetmek veya anahtarı değiştirmek `C11380Yq.A0C(...)` çağırır (zorunlu yeniden bağlanma) ve `wam_user_proxy_set` tetikler.

Proxy host'un akışla ne yaptığı istemci tarafında görünmez. Bir WhatsApp Proxy rölesinin ham chatd baytlarını ilettiği, herhangi bir SOCKS veya CONNECT alışverişinin yokluğundan çıkarılır (inferred).

### 3.5 Diğer tüketiciler (found)

| Tüketici | Davranış |
|----------|----------|
| Medya yükleme / indirme | flag **4073** medya authority'sini `proxy-host:mediaPort` yapar; sağlık kontrolü [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) içinde |
| WAM yükleme rotaları | native geri çağrı `jnidispatchO(0)`, flag **4074** açıkken `https://<proxy-host>:<mediaPort>/deidentified_telemetry` döndürür, flag **4020** açıkken ek olarak `media_conn` host'larını (bkz. [WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)) |
| Durum arayüzü | `C42103IXl.A00`: 1 `Connecting…`, 2 `Connected`, 3 `Couldn't connect to proxy`, 4 `Disconnected`, 5 `No network`, diğeri `Not Set`; sohbet durumunu bağlantı gözlemcisi `C28890Cgr` besler |
| Psiphon HTTP ve Tigon rotaları | kullanıcı proxy'si varken devre dışı (`C17420jn.A01`, `C12790bk`: `User proxy is set, skipping`) |
| Telemetri | `WamUserProxySet {connectionSuccess, proxySet}` (`C43286IuN`), durum 2 (true) veya 3 / 4 (false) olduğunda ve proxy değişikliklerinde gönderilir |

---

## 4. Proxy servisi (Psiphon)

### 4.1 Modül ve kütüphane (found)

| Öğe | Değer |
|-----|-------|
| Teslimat | Voltron modülü `proxyservice` ve `assets/app_modules.json` içinde ABI başına bölünmüş `proxyservice.config.{arm64_v8a,armeabi_v7a,x86,x86_64}`; modül manifesti `assets/proxyservice/libs.txt`, `assets/proxyservice/voltron_meta_embedded_server_entries` ve bölünmüş her paket için `lib/<abi>/libgojni.so` listeler |
| Java tarafı | `ca.psiphon.PsiphonTunnel` (upstream kütüphane, `loadLibrary("gojni")`, `Psi.start`, `importPushPayload`), host servis `S6G` / `C42448IfJ`, orkestratör `C12760bh`, modül yükleyici `C46743KbZ` |
| Mod | `localhost` üzerinde yerel HTTP ve SOCKS proxy; `VpnService` yok |
| Kütüphane yükleme | bölünmüş APK kütüphaneleri SoLoader kaynaklarına eklenir (`proxy_service/Added module SoSource`); log dizesi `libproxyservice.so` adını verir, oysa modül manifestinde yalnızca `libgojni.so` vardır |

`libgojni.so` APK içinde yok (modülle teslim edilir). İç yapısı (protokol kümesi, çevirme, `AdditionalParameters` kullanımı) unknown.

### 4.2 Yapılandırma kaynağı `res/raw/proxyservice_config.json` (found)

2.26.34.4'ten beri değişmedi. `C42448IfJ.getPsiphonConfig` tarafından okunur; `ClientVersion` biçim yer tutucusu uygulama versionCode'u (`264100600`) ile doldurulur.

| Alan | Değer / kullanım |
|------|------------------|
| `SponsorId`, `PropagationChannelId`, `ClientPlatform` | opak 16 hex kimlik; platform `meta` |
| `ServerEntrySignaturePublicKey`, `PushPayloadSignaturePublicKey`, `RemoteServerListSignaturePublicKey` | 32 bayt, 32 bayt ve 548 bayt (RSA boyutunda) base64 anahtarlar; doğrulama rolü adlardan çıkarıldı |
| `AdditionalParameters` | 5300 base64 karakter (3975 bayt), opak, çözülmedi |
| `Emit*` (istemci adresi, tanılama bildirimleri, ağ parametreleri), `DisableServerEntriesReporter` | hepsi true; `onClientAddress`, `onDiagnosticMessage` besler |
| `ConnectionWorkerPoolSize`, `EstablishTunnelTimeoutSeconds` | 30, 0 |
| `TransformHostNameProbability`, `TLSFragmentClientHelloProbability` | 0.9, 0.5 (native motor için DPI karşıtı ayarlar; etki adlardan çıkarıldı) |
| `EnableLightProxy`, `LightProxyLimitDestinationAddresses` | true; 80, 443, 5222 portlarında `g.whatsapp.net` ve `g-fallback.whatsapp.net` |

Çalışma zamanı değişiklikleri: flag **23879** (giriş öncesi flag kaynağı) veya **23846** (normal kaynak) kaynaklı bir JSON nesnesi anahtar anahtar dosyanın üzerine birleştirilir. PSL içe aktarma modu (`C42448IfJ.A03`) `DisableTunnels=true`, `EnableLightProxy=false` zorlar. Gömülü sunucu girdileri flag **23730** / **23731** açıkken `assets/proxyservice/voltron_meta_embedded_server_entries` (veya modül zip'i) içinden okunur; biçim: big-endian int32 adet, ardından adet kadar (int32 uzunluk, bayt), her girdi hex kodlu, satır başına bir (`C45480Jst.A01`).

İki flag kaynağı `C17280jY.A00` ile seçilir: oturum açmış hesap yoksa veya AB props hiç yenilenmediyse giriş öncesi küme seçilir. Dolayısıyla servis kayıttan önce de çalışacak şekilde tasarlanmıştır (yüklemden çıkarıldı, inferred).

### 4.3 Durum makinesi (found, `AbstractC17380jj`, `C12760bh.A0B`)

| Kod | Durum | Ne zaman ayarlanır |
|-----|-------|--------------------|
| 0 / 1 / 2 | `uninitialized` / `not_in_region_allowlist` / `initializing` | başlangıç / bölge reddedildi (neden bölgeyi taşır) / başlatma kabul edildi |
| 3 / 4 | `disabled` / `downloading_module` | `vpn_in_use` gibi bir kapı / Voltron indirmesi sürüyor |
| 5 / 6 / 7 | `connecting` / `connected` / `disconnected` | `onConnecting` / `BmZ` (portlar hazır) / `BpU` |
| 8 / 9 | `download_failed` / `library_load_failed` | modül kurulum hatası / `UnsatisfiedLinkError` |
| 10 | `shutdown` | `A04(reason)`, örneğin `country_check`, `has_external_connectivity` |

Durum 2, 4 veya 5 iken HTTP yığını proxy'yi bekler: `C17420jn.A05(true)` zaman aşımı flag **29362** olan (ms, varsayılan 0, yalnızca oturum açıkken) bir latch kurar.

### 4.4 Başlatma ve durdurma tetikleyicileri (found)

| Tetikleyici | Yol |
|-------------|-----|
| Mesaj işleyicisinin soğuk başlangıcı | `C1W6` default case `C12760bh.A03(…, null)` çağırır |
| Uygulamanın öne gelmesi | `C18980me`, `C28912ChD` `A0A()` çağırır (tüneli yeniden bildir veya durmuşsa yeniden başlat) |
| `psl` içeren engel kaldırma push'u | `C28912ChD.BIb`: `A03(…, C46772Kc2(psl))`; `psl` yoksa yalnızca `C17280jY.A02()` iken `A0A()` (flag **28186** / **28189**) |

`A03` içindeki başlatma kapıları:

1. Cihaz bölgesi = SIM ülkesi, yoksa ağ ülkesi, yoksa yerel ayar ülkesi (`AbstractC16510i9`); flag **18724** (giriş öncesi) / **18725** (`C17280jY.A03`) küçük harfli virgüllü listesinde olmalıdır. Aksi halde durum 1.
2. VPN kontrolü (`C17280jY.A01`, flag **24068** / **24067** onu atlar): VPN etkinse `vpn_in_use`, durum 3.
3. Flag **25452** sırayı belirler: açıksa VPN kapısı ve prober modül indirildikten sonra çalışır; kapalıysa önce.
4. Prober (flag **18875**, `Q53`): flag **18871** içindeki URL'ye normal yığın üzerinden HTTP GET (zaman aşımı **18874**, deneme **18873**, gecikme **18872**). Herhangi bir HTTP yanıtı başarı sayılır (`KUI.CF3`): `Probe succeeded. Removing proxy from http and tigon`, `A0N` (harici bağlantı) ayarlanır, proxy HTTP ve Tigon'dan temizlenir, kapatma kontrolü çalışır.
5. Başlatma işareti zaman aşımı: flag **25850** saniye (`init_timed_out` açıklaması).

Durdurma koşulları:

| Koşul | Sonuç |
|-------|-------|
| Psiphon'un bildirdiği istemci bölgesine izin yok (flag **19067** açık) | `country_check`, kapatma |
| Prober başarılı (`A0N`) ve iyi bir doğrudan chatd oturumu bildirildi (`A0O`), flag **19613** açık | `has_external_connectivity`, kapatma |
| İyi doğrudan chatd oturumu (`HandlerThreadC12340b0.A0e`: servis etkin, oturum flag **19372**'den uzun (varsayılan 5, birim çözülmedi), rota `SOCKS_PROXY` değil) | `C12760bh.A09()` artı `C37061dV.A00()`: proxy servisi süreç ömrü boyunca yok sayılır (`good_direct_chatd_session`) |
| Başlangıçta flag **19144** negatif | süreç ömrü boyunca yok sayılır (`abprop_config`) |

### 4.5 chatd ile entegrasyon (found)

`C37061dV` (`ConnectionProxyConfig`) broadcaster durumunu dizinin kullandığı `ProxyServiceConfig`'e dönüştürür.

| Alan | Kaynak |
|------|--------|
| `address` | ağır tünel veya hafif proxy ayaktaysa `localhost`, değilse boş |
| `port` | SOCKS portu (`ProxyServiceBroadcaster.A01(true)`: ağır, veya izin verilirse hafif) |
| `proxyServiceClientIP` | `onClientAddress` |
| `httpProxyHost`, `httpProxyPort` | `localhost` ve sıfır değilse HTTP portu |
| `isLightProxy` | `isLightProxy()` (hafif proxy ayakta, ağır tünel bağlı değil) |

Kurallar:

- Adres veya port boşsa (`updateProxyServiceConfig`) ya da Psiphon'un bildirdiği bölgeye izin verilmiyorsa (`dropping due to unsupported client region`) yapılandırma düşürülür.
- `C37061dV.A02` (her bağlantı başlangıcında çağrılır) yapılandırmayı yalnızca cihaz bölgesine izin veriliyorsa, VPN etkin değilse, servis kapatılmamışsa ve süreç ömrü yok sayma ayarı yoksa döndürür. Flag **24645** açıkken önbellekteki yapılandırma bu kontroller olmadan kullanılır.
- Henüz yapılandırma yoksa bağlantı iş parçacığı 5. adımdan önce yapılandırmayı beklemek için flag **19144** ms kadar bloke olabilir (`awaitProxyServiceConfig`).
- Değişen yapılandırma reset bayrağını ayarlar ve flag **36306** açıkken `proxy_service_update` nedeniyle yeniden bağlanır.

Soket (`C37031dS.A01` else dalı, sınıf `C48201yM` = `ConnectionSocketTunnel`):

```java
Socket s = new Socket(new Proxy(Proxy.Type.SOCKS, new InetSocketAddress(cfg.address, cfg.port)));
s.connect(InetSocketAddress.createUnresolved(host, port), 30000);   // g.whatsapp.net / g-fallback.whatsapp.net
c37861f7.A00(out, cfg.proxyServiceClientIP, port);                    // PROXY v2 header, skipped when flag 26334 is on
```

PROXY v2 başlığı (`C37861f7`, log `ProxyHeaderWriter`): 12 baytlık imza `0D 0A 0D 0A 00 0D 0A 51 55 49 54 0A`, `21`, aile `11` (IPv4) veya `21` (IPv6), 16 bit uzunluk, kaynak adres (istemci IP'si, ayrıştırılamazsa sıfır adres), sıfır hedef adres, kaynak port 0, hedef port = hedef port, ardından bir TLV `E8 00 01 50`. TLV anlamı unknown. Edge'in başlığı kabul edip etmediği veya gerektirip gerektirmediği yalnızca varlığından çıkarılır (inferred).

Deneme başına bağlantı zamanlama kayıtları `DNS`, `SOCKET`, `TLS` aşamalarını ve `PLATFORM`, `MNS`, `SOCKS_PROXY` yığınlarını kullanır (`C37811f2`, `EnumC37801f1`, `EnumC37821f3`).

### 4.6 Yerel proxy'nin diğer tüketicileri (found)

| Tüketici | Sınıf | Davranış |
|----------|-------|----------|
| WA HTTP yığını | `C17420jn` (`WaHttpUrlConnectionWithProxyService`) | `Proxy(HTTP, localhost:httpPort)`; `.whatsapp.net`, `.whatsapp.com`, `.fbcdn.net`, `.facebook.com`, `.instagram.com`, `.cdninstagram.com`, `.fbsbx.com` ile biten host'lar için `X-Forwarded-For: <client IP>` ve `using-wa-proxy-service: 1` ekler |
| Tigon (MNS) istemcileri | `C12790bk` (`WATigonProxyObserver`) | `setInAppProxyHostAndPort`; flag **26734** / **26735** (Tigon) veya **19905** / **19906** (WA proxy) açıksa, kullanıcı proxy'si varsa, `http.proxyHost` / `https.proxyHost` ayarlıysa veya prob zaten başarılıysa atlanır |
| VoIP | `CQO`, `JNIUtils.socksProxyPort` | flag **34525** izin verirse `Voip.updateProxy(socksPort)` (`Buh()` içinde ikinci kapı **36980**) |
| WebView | `C39826HXw` | flag **25539** içindeki alan adları için `PROXY_OVERRIDE` kuralı |
| Ağ bilgisi logu | `C12500bH` | `network_info_socks_proxy_active[...]`, `socks_proxy_connected` / `socks_proxy_disconnected` |

Tigon ayrıca sistem proxy özelliklerini de kendisi okur (`TigonHttpClientBase.setSystemProxyHostAndPort`), doğrudan yedek anahtarıyla; bu, servisten bağımsızdır.

### 4.7 Tanılama (found)

`C42448IfJ.onDiagnosticMessage`, `ConnectedServer:{json}` mesajını `candidate_number`, `protocol`, `client_replay_type` (`bootstrap`, `replay`, `non-replay`), `server_entry_source` alanlarına ayrıştırır. İşaretler 79499422 (başlatma), 79496324 (bağlanma), 79501264 (prober, `has_vpn`, `has_system_http_proxy` ile açıklanmış).

---

## 5. Yedek uç noktalar ve engel kaldırma push'u

### 5.1 `<ib><fbip>` (found, `C40581l4`, `C36821d6.A02`)

`<ib><fbip>text</fbip></ib>`: metin `,` üzerinde bölünür. Tek girdi `CLEAR` dosyayı siler. Her girdi altı `|` ayraçlı alandır:

```
ip|port|ts|ttl|secure|override       exp = (ts + ttl) * 1000
```

| Alan | Kullanım |
|------|----------|
| `ip`, `port` | uç nokta; çözümleyici kodu 4 (`FALLBACK`) |
| `ts`, `ttl` | ms cinsinden son kullanma; süresi dolan girdiler yüklemede silinir |
| `secure` | uç nokta için TLS sarmalayıcı biti |
| `override` | true girdiler 2. adıma gider (`g.whatsapp.net`'ten önce denenir), false girdiler 8. adıma (`:80`'den sonra) |

Kalıcılık: uygulama dosyaları dizininde `fbips` dosyası, JSON `{"fbips":[{"ip","port","exp","secure","override","resolver"}]}` (`C36821d6.A00`). Yükleme hataları `fallback-manager/load-error`, `save-error` olarak bildirilir.

### 5.2 Sabit kodlu tablo (found)

`AbstractC47101wK`: 18 host adı (`.whatsapp.net` altında `e1` ile `e16`, `g`, `v`; düz ve sondaki noktalı biçimler), her biri birkaç IPv4 adresiyle. 6 / 10. adımlar ve sabit kodlu çözümleyici tarafından kullanılır. `v.whatsapp.net` girdisi bu derlemede hiçbir çözümleyici tarafından kullanılmaz (çözümleyici stub'ı null döndürür).

### 5.3 Engel kaldırma push'u (found)

Push ayrıştırma (`CLl`, `PushPayloadParser/fromJSON`): `nt` değerleri `pre_reg`, `post_reg`, `voip_call_offer_1on1`, `voip_call_offer_group`, `call_terminate`, `message`, `group_message`, `wfac_ban`, `unblocking`. Loglanan taşımalar: `ADM`, `GCM`, `FBNS`. Payload çözülür (`PushEncryptionHelper`, alanlar `payload`, `IV`, `tag`, anahtar `push:push_pkey_data` içinden; şifre alan adlarından AES-GCM olarak çıkarıldı, inferred).

`nt` = `unblocking` şunları taşır (`UnblockingPushPayload`, `BQY`):

| JSON anahtarı | Alan | İşleme |
|---------------|------|--------|
| `fbips` | `fbips` | `,` üzerinde bölünür, `C36821d6.A02`'ye geçirilir (5.1 ile aynı biçim) |
| `unblocking_props` | `unblockingProps` | `version\|a\|b`; 0'dan büyük sürüm yok sayılır; `C27946CBo.A00` tarafından ayrıştırılan iki `id=value;id=value` haritası; `processPreChatdProps` `config_code` / `config_value` çiftlerini uygular, `processPostChatdProps` ikinci haritayı (haritaların aşamalara atanması kısmen inferred) |
| `psl` | `proxyServerList` | base64, `importPushPayload` ile Psiphon'a aktarılır (`C46772Kc2`) |

`psl` içe aktarma: tünel etkinse doğrudan aktarılır; tünel etkin değilse geçici bir tünel nesnesi PSL içe aktarma modunda (`DisableTunnels`) başlar, aktarır, durur (`Cold-importing push payload`). Durum `not_in_region_allowlist` ise atlanır. PSL'nin "push server list" olarak açılımı anahtardan ve `PushPayloadSignaturePublicKey` alanından çıkarılır (inferred).

---

## 6. DNS yedek zinciri (found)

`C36881dC.A03` önce bir önbelleğe bakar (`fbips` tarafından beslenir, süreli girdiler; bir flag ile kapılanır), ardından dört çözümleyiciyi sırayla dolaşır:

| # | Çözümleyici | Çözümleyici kodu | Notlar |
|---|-------------|------------------|--------|
| 0 | `v.whatsapp.net` için stub | yok | null döndürür |
| 1 | platform / MNS DNS (`DnsCache/resolveViaMnsDns`) | 5 / 6 / 7 | bir kez yeniden dener (`primary dns resolver failed, retrying...`) |
| 2 | ikincil: 8.8.8.8 ve 8.8.4.4 port 53'e elle kurulmuş UDP DNS (`QG1`) | 1 `GOOGLE` | düz UDP, DoH veya DoT yok |
| 3 | sabit kodlu tablo | 2 `HARDCODED` | eksikse `no hardcoded ips found for <host>` |

Flag **13545** (string) çözümleyicileri maskeler: `secondary` sabit kodluyu kapatır, `hardcoded` UDP çözümleyiciyi kapatır, `none` ikisini de kapatır (bit mantığı `C37151de.A01` içinde). Flag kontrollü bir anahtar ayarlıysa `EPERM` hataları yeniden fırlatılır. Çözümleyici kodları `ClientPayload.dnsSource` alanına ulaşır (Noise raporu bölüm 6.5).

---

## 7. Kayıt rölesi (found)

Kapsam: `https://v.whatsapp.net` adresine kayıt HTTP'si (`RegistrationHttpManager` = `K49`, `KotlinRegistrationBridge`, `RetryingHttpClient`). chatd'ye dokunmaz.

### 7.1 Sağlayıcı listesi

Kaynak `res/raw/domain_fronting_providers.tsv`, sütunlar `name`, `url template`, `host`:

| Ad | Şablon | Host |
|----|--------|------|
| `amazon` | `https://y9yrsygcg6.execute-api.us-east-1.amazonaws.com/s/s?_={PATH}&{QS}` | `y9yrsygcg6.execute-api.us-east-1.amazonaws.com` |
| `google` | `https://us-central1-propane-fusion-170222.cloudfunctions.net/s?_={PATH}&{QS}` | `us-central1-propane-fusion-170222.cloudfunctions.net` |

`C45421Jrl` onu yükler (3'ten az token içeren satırlar `domain-fronting-providers/load/bad-line` loglar) ve üç liste tutar: erişilebilir (`A05`), test edilmemiş (`A06`), erişilemez (`A04`). `K49.A0K` bunları her kayıt çağrısına bu sırayla verir.

### 7.2 Prob

`EULA.onCreate` probu en fazla her 900000 ms'de başlatır (`C06810Gk(930).A07()` ise atlanır, anlamı çözülmedi): `https://v.whatsapp.net` açılır; `IOException` olursa (`DomainFrontingManager/probe-regd/cant connect to regd`) sağlayıcılar karıştırılır ve her şablona `{PATH}=/` ve boş `{QS}` ile GET yapılır, 60 sn bağlanma ve okuma zaman aşımı, başlıklar `Host` = sağlayıcı host'u ve uygulama user agent'ı. HTTP 200 bir sağlayıcıyı erişilebilir listeye taşır, her hata erişilemez listeye taşır (`domainFrontingProvider/cant reach`).

### 7.3 Deneme stratejileri (`RetryingHttpClient`, `C44407JaE`, `C44975Jk4`)

| Strateji | İstek | 2.26.41.6'daki durum |
|----------|-------|----------------------|
| `ORIGINAL` | normal URL | her zaman 1. deneme |
| `HOST` | aynı URL, verilen bir IP ile | liste bu derlemede boş |
| `PROXY` | verilen bir proxy IP'si üzerinden | liste bu derlemede boş |
| `DOMAIN_FRONTING` | `{PATH}` ve `{QS}` yerine özgün yol ve ham sorgu konmuş şablon; başlıklar `Host` = sağlayıcı host'u, `X-Forwarded-Host` = özgün host | sağlayıcı listesi kadar |

Sıra: ORIGINAL, HOST girdileri, PROXY girdileri, sağlayıcılar; en fazla 4 deneme. URL host'u ve `Host` başlığı iki şablonda da eşittir; dolayısıyla bu, klasik SNI / Host fronting yerine bir cloud-function rölesidir (isteği sağlayıcı `X-Forwarded-Host`'a iletir, inferred).

Yeniden deneme kuralı: 2, 5, 7, 12 sonuç kodları yeniden denenemez (`non-retryable error`), diğer her hata devam eder (`failed attempt N ... reason`); kod anlamları çözülmedi. `n` > 1 numaralı denemeden önceki gecikme:

```
delay = clamp(r * (n*n - 1) * 4 * 1000, 0, 60000) ms      // r from a random double, assumed uniform in [0,1)
```

`RetryingHttpClient/executePostWithRetry/applying backoff`, `all retries exhausted`. Yol başına uç nokta attestation payload flag'leri `AbstractC44143JQf` içindedir ve röleyle ilgisizdir.

---

## 8. Tigon ve DGW

| Öğe | Durum | Katman |
|-----|-------|--------|
| Tigon HTTP (`TigonHttpClient`, MNS istemcileri) | HTTP(S) istemcisi; Psiphon HTTP proxy'sini ve sistem proxy özelliklerini alır (bölüm 4.6); chatd taşıması değil | found |
| DGW istemcisi (`AbstractC20460pC`) | alan adı `gateway.facebook.com`, yedek yapılandırma `null`, kişiselleştirme yapılandırması `null` ile kurulur | found |
| `DGWFallbackConfig` | `isFallbackEnabled`, `fallbackDomain`, `numFailuresForFallback`, `fallbackReasons`, `isHardcodedIpFallbackEnabled`; null hepsini kapalı yapar; Java builder onu hiç etkinleştirmez, native varsayılanlar unknown | found / unknown |
| DGW kullanıcıları | yalnızca `WaFalcoStreamingRegistration` (telemetri akışı); bkz. Noise raporu bölüm 13 | found |

Native dizeler (`distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, kısıtlama ve zero-rating etiketleri) DGW iç yapısını anlatır. Hiçbir şey DGW'yi engellenmiş chatd kurtarmasına bağlamaz (yokluktan çıkarıldı, inferred).

---

## 9. Bağlantı durumu takibi ve tanılama

| Öğe | Yer | İçerik |
|-----|-----|--------|
| Dizi kalıcılığı | prefs `connection_sequence_state`, `connection_sequence_attempts`, `last_successful_connection_step`, `_host`, `_port` | devam noktası, HISTORY adımı (Noise raporu 2.2) |
| Deneme başına kayıtlar | `C37811f2` | aşama `DNS` / `SOCKET` / `TLS`, yığın `PLATFORM` / `MNS` / `SOCKS_PROXY`, zamanlama, hata |
| Payload | `ClientPayload.dnsSource`, `connectAttemptCount` | soketi üreten çözümleyici veya rota |
| Proxy servisi | `C12760bh.A06()`, `A08()` | durum kodu (4.3); `A08()` `both`, `heavy`, `light` veya null döndürür |
| Kullanıcı proxy'si | `user_proxy_setting_pref` durumları, `wam_user_proxy_set` | arayüz ve analitik |
| Ağ bilgisi logu | `C12500bH` | `network_info_is_vpn`, `_is_airplane`, `_is_data_saver`, `_is_cellular_enabled`, `_socks_proxy_active`, `socks_proxy_connected` / `_disconnected` |
| Log etiketleri | `proxy_service/`, `ConnectionProxyConfig/`, `WaConnectivityProber/`, `WATigonProxyObserver/`, `ConnectionThread/Skipping sequence` | kapılar ve durum değişiklikleri |

---

## 10. Yeniden deneme ve backoff etkileşimi

Backoff'un kendisi (Fibonacci birimleri, 15 dakikalık sınır, alarmlar) Noise raporu bölüm 10'dadır. Bu özellik şunları ekler:

| Etkileşim | Etki |
|-----------|------|
| Kullanıcı proxy'si kaydedildi, değiştirildi, silindi | zorunlu yeniden bağlanma (`C11380Yq.A0C(...)`) |
| Proxy servisi yapılandırması değişir | dizi sıfırlanır; flag **36306** açıkken `proxy_service_update` ile yeniden bağlanma |
| Kullanıcı proxy'si ayarlı | tek adımlı dizi; her başarısız deneme tüm bağlanma backoff'una döner |
| Yapılandırma beklemesi / HTTP beklemesi | bağlantı iş parçacığı 5. adımdan önce flag **19144** ms kadar bloke olur; servis başlarken HTTP yığını flag **29362** ms kadar |
| Kayıt | 4 denemelik kendi sınırı ve ikinci dereceden gecikme (bölüm 7.3), chatd ile paylaşılmaz |

---

## 11. Feature flag'ler (kimlikler kodda okunduğu gibi; değerler sunucu tarafında)

| Id | Tür | Kontrol ettiği |
|----|-----|----------------|
| **2784** | bool | kullanıcı proxy'si özelliği (etkin durum, deep link) |
| **4020**, **4073**, **4074** | bool | native'e media_conn host'ları; kullanıcı proxy'si üzerinden medya; kullanıcı proxy'si üzerinden telemetri rotası |
| **18875** | bool | bağlantı prober'ı |
| **18871**-**18874** | string, int | prob URL'si, gecikme, deneme, zaman aşımı |
| **18724**, **18725** | string | izinli bölgeler (giriş öncesi / normal kaynak) |
| **19067** | bool | bağlanırken bölge yeniden kontrolü |
| **19613** | bool | harici bağlantıda kapatma |
| **19144** | int | yapılandırma bekleme ms; negatif servisi süreç boyunca yok sayar |
| **19372** | int | iyi oturum eşiği (varsayılan 5) |
| **19905**, **19906**, **26734**, **26735** | bool | HTTP / Tigon için WA proxy'sini devre dışı bırak (giriş öncesi / normal) |
| **23630** | bool | proxy altında 2-4. adımlara izin (varsayılan olarak açık bildirilmiş, inferred) |
| **23730**, **23731** | bool | gömülü sunucu girdileri (giriş öncesi / normal) |
| **23846**, **23879** | JSON | Psiphon yapılandırma override'ı (normal / giriş öncesi) |
| **24067**, **24068** | bool | VPN etkinken servise izin ver |
| **24645** | bool | önbellekteki servis yapılandırmasını kapılar olmadan kullan |
| **25452** | bool | VPN kapısı ve prober'ın modül indirmesine göre sırası |
| **25539** | string | WebView proxy alan adı izin listesi |
| **25850** | int | saniye cinsinden başlatma işareti zaman aşımı |
| **26334** | bool | PROXY v2 başlığını atla |
| **28186**, **28189** | bool | `psl` içermeyen push'ta servisi sürdür |
| **29362** | int | HTTP proxy bekleme ms |
| **34525**, **36980** | bool | SOCKS portunu VoIP'e ilet |
| **36306** | bool | proxy servisi güncellemesinde yeniden bağlan |
| **13545** | string | DNS çözümleyici maskesi |

Chatd merdiveni ve keepalive flag'leri (**20801**, **22916**, **30712**, **33512**, **7831**-**7834**, **15103**) Noise raporu bölüm 12'dedir.

---

## 12. Baileys (`baron-baileys-v2`, kaynağına karşı kontrol edildi)

| Yön | Baileys | Android 2.26.41.6 |
|-----|---------|-------------------|
| Taşıma | `wss://web.whatsapp.com/ws/chat` adresine `ws` WebSocket (`waWebSocketUrl`) | ham TCP Noise |
| Proxy | `new WebSocket(url, { agent })` içine geçirilen `config.agent`; yüklemeler `fetchAgent` kullanır | WhatsApp Proxy rölesi, Psiphon tüneli |
| Yedek host'lar | yapılandırılabilir tek URL | `g`, `g-fallback`, `eN` merdiveni, portlar 443 / 5222 / 80 |
| `<ib><fbip>`, engel kaldırma push'u | işlenmez | işlenir |

```ts
const sock = makeWASocket({ agent: new SocksProxyAgent(proxyUrl), fetchAgent: new SocksProxyAgent(proxyUrl) })
```

| Neden başarısız olur | Neden | Çözüm |
|----------------------|-------|-------|
| Bir Android WhatsApp Proxy host'u Baileys'i reddeder | röle sohbet portunda ham TCP Noise konuşur (inferred); Baileys WebSocket upgrade gönderir | `web.whatsapp.com`'a ulaşan bir HTTP veya SOCKS proxy kullan |
| Engellendikten sonra kurtarma yok | `fbip` işleme yok, push kanalı yok | yeni bir `agent` veya URL ver |

---

## 13. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| `Couldn't connect to proxy` | kullanıcı proxy host'una ulaşılamıyor veya TLS ayarı yanlış | host'u, `Chat port`'u, `Use TLS`'i kontrol et; dizide doğrudan yedek yok |
| `Enter a valid host` / `Enter a valid port` | `K09` içindeki doğrulama | girdiyi düzelt |
| Proxy bağlantısı hiçbir şey yapmıyor | flag **2784** kapalı veya ek yol segmentleri (`proxy_has_segments`) | istemci tarafında yok |
| `proxy_service/Proxy service detected user region not in region allowlist.` | Psiphon'un bildirdiği bölge flag **18724** / **18725** listesi tarafından reddedildi | istemci tarafında yok |
| Durum `disabled`, neden `vpn_in_use` | VPN etkin, flag **24067** / **24068** kapalı | VPN'i veya flag'i kapat |
| `RetryingHttpClient/executePostWithRetry/all retries exhausted` | tüm denemeler başarısız | bekle; sınır 4 |

---

## 14. Önemli ayrımlar

| Karıştırma | Ayrıntı |
|------------|---------|
| Kullanıcı proxy'si ve proxy servisi | kullanıcı proxy'si = seçilen host, 12. adım, sonlandırıcı, paylaşım bağlantısı; proxy servisi = 5 ve 13. adımlar için sunucu güdümlü Psiphon SOCKS tüneli; birbirlerini dışlarlar |
| `C48201yM` ve 12. adım | `C48201yM` proxy servisinin SOCKS tünel soketidir; 12. adım kullanıcı proxy'sidir ve düz veya TLS soket kullanır |
| Hafif proxy ve ağır tünel | hafif proxy listelenen altı `g` / `g-fallback` hedefiyle sınırlıdır; ağır tünel tam Psiphon oturumudur |
| `fbip` ve `fbips` push ve `fallback_*` | `<ib><fbip>` ve push `fbips` chatd yedek IP'lerini verir; `fallback_hostname` / `fallback_ip*` `media_conn` öznitelikleridir (Noise raporu bölüm 16) |
| Kayıt rölesi ve chatd | sağlayıcı listesi sohbet dizisini asla beslemez |
| WhatsApp Proxy ve sistem proxy'si | sistem proxy'si chatd için okunmaz |

---

## 15. Tam akış

```
[Operator]  push nt=unblocking {fbips, unblocking_props, psl}   or   <ib><fbip>...</fbip></ib>
     │  fbips file updated ; props applied ; psl imported (temporary tunnel if inactive)
     ▼
[Client]  C12760bh gates: region (SIM > network > locale), no VPN, flags ; Voltron proxyservice download
     │  PsiphonTunnel.startTunneling(embedded entries) ─► localhost SOCKS + HTTP ports ─► state 6
     ▼
[ProxyServiceBroadcaster]  C37061dV builds ProxyServiceConfig ─► sequence reset ("proxy_service_update")
     │
     ├── user proxy set ─► step 12 only: host:chatPort (+TLS) ─► Noise ─► end (no direct fallback)
     ▼
[ConnectionThread]  steps 5, 13 (2-4 if flag 23630) ─► SOCKS CONNECT g / g-fallback (unresolved host)
     │  PROXY v2 header (client IP) ─► Noise handshake (Noise report section 4)
     ▼
[Server]  login success; session > threshold and route != SOCKS_PROXY ─► proxy ignored for the process
     ▼
[Failure]  timeout / socket error ─► next step ─► exhausted ─► Fibonacci backoff (Noise report section 10)

[Registration]  v.whatsapp.net ─► ORIGINAL ─► relay providers (Host + X-Forwarded-Host) ─► <= 4 attempts
```

---

## 16. Bilinmeyenler

| Öğe | Durum |
|-----|-------|
| Herhangi bir ağ davranışı (tünel, PROXY v2 kabulü, röle yanıtı, WhatsApp Proxy iletimi) | hiçbir şey yakalanmadı; hiçbir öğe `tested` değil |
| `libgojni.so` iç yapısı, protokoller, `AdditionalParameters`, gömülü girdi içeriği | native modül APK içinde değil |
| İzinli bölge listesi içeriği, prob URL'si, tüm flag değerleri | sunucu tarafında |
| PROXY v2 başlığındaki TLV `E8 00 01 50` anlamı | unknown |
| İki `unblocking_props` haritasının chatd öncesi ve sonrası aşamalara eşlenmesi, push şifresi | kısmen inferred |
| Flag **19372** birimi, kayıt yeniden denemesindeki kod anlamları (2, 5, 7, 12), `C06810Gk(930).A07()` arkasındaki yüklem | çözülmedi |
| `DeepLinkActivity` öncesinde gelen `wa.me/proxy` yönlendirmesi (manifest filtreleri `wa.me`'yi kapsar) | etkinliğin ötesinde izlenmedi |
| Java tarafı DGW yedek yapılandırmasının native'de kapalı kalıp kalmadığı ve yalnızca native bir yedek olup olmadığı | unknown |
| Psiphon etkin bir çalıştırmada 8. adım girdilerinin davranışı | doğrudan olduğu inferred |
