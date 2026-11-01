<!-- src-sha1: acf9c9e68ca59b17d45a787d66ae2550607b66cc -->
# WhatsApp İstemci Modu Tespiti — Tam RE Raporu
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** Resmi olmayan/modlanmış Android istemcilerinin (GB WhatsApp ailesi repack'ler, Xposed/LSPosed hook modülleri — WaEnhancer gibi —, yeniden imzalanmış APK'lar) istemci taraflı tespiti — bulunan tek özel mod sezgiseli (`is_whatsapp_plus_user`), hook-framework iz araması (Xposed/Frida/Substrate), istemcinin `WA_CLIENT_INTEGRITY.md` içinde zaten kataloglanmış imza/kurulum-kaynağı/root telemetrisiyle yaptığı işlemler, WFAC ban arayüzünün sunucu tarafından gönderilen ban nedenlerini işleyişi ve bir üçüncü taraf hook modülünün (WaEnhancer) host süreç içinde hedeflediği bilinen saldırı yüzeyi

---

## 1. Genel Bakış

Bu rapor **mod/tamper tespiti** ile sınırlıdır, hesap doğrulaması (attestation) ile değil. Keystore attestation, Play Integrity, WASafe, imza öz-kontrolü (WAM **6251**) ve kurulum-kaynağı bayrağı (WAM **10255**) tam olarak [`WA_CLIENT_INTEGRITY.md`](WA_CLIENT_INTEGRITY.md) içinde belgelenmiştir; bu rapor bunların mod tespitine katkısını belirtir, mekaniklerini tekrar etmez.

| Mekanizma | Tespit Ettiği | Raporlandığı Yer | Bulunan Uygulama (Enforcement) |
|-----------|---------|-------------|--------------------|
| `is_whatsapp_plus_user` (reflective sınıf probu) | ACRA crash-reporter kütüphanesini içeren bir üçüncü taraf istemci | `wam_daily` telemetri alanı; contact-us içindeki `diagnostic` string'i (`nw-wap`) ve debug raporu (`NW-WAP-1`) | yok |
| Uygulama imza öz-kontrolü (`AbstractC38241gg` / `C27965CCj`) — bkz. integrity raporu §5 | Yeniden imzalanmış/repack edilmiş APK (imzalama sertifikası WhatsApp'ın gömülü değerinden farklı) | WAM ortak özniteliği **6251** | yok |
| Kurulum kaynağı bayrağı (`CHH`) — bkz. integrity raporu §5.4 | Sideload edilmiş / Play dışı kurulum | WAM **10255**, `install_source_official` | yalnızca modül-indirme yönlendirmesi, gate yok |
| Root / emülatör / özel-ROM bayrakları (`C00L`, `Cdt`) — bkz. integrity raporu §6 | Rootlu veya emüle edilmiş cihaz (yaygın bir kolaylaştırıcı, kendisi mod sinyali değil) | `wam_daily` | yok |
| Hook-framework iz string'leri (Xposed, Frida, Substrate, LSPosed, TracerPid) | — | — | bu derlemede **bulunamadı** (§3) |
| Native kütüphane / dex öz-checksum'u | — | — | bu derlemede **bulunamadı** (§3) |
| WFAC ban arayüzü (`WfacBanActivity`) | — | sunucu tarafından gönderilen `ban_violation_type` / `ban_violation_source` / `ban_violation_reason` değerlerini gösterir | sunucu kararı, istemci için opak (§5) |

Decompile edilmiş istemci içinde yukarıdakilerden herhangi biri nedeniyle çalışmayı reddeden, bir özelliği kısıtlayan veya bir eylemi engelleyen hiçbir kod yolu bulunamadı. Bulunan her mekanizma, hesap bütünlüğü için zaten ulaşılan sonuçla uyumlu şekilde **telemetridir**.

---

## 2. Bulunan tek özel mod sezgiseli: `is_whatsapp_plus_user`

### 2.1 Ne kontrol ediyor

Ortak bir yardımcı çağırmak yerine **aynı reflective probu** çalıştıran üç bağımsız nokta:

```smali
; smali_classes7/X/Cdt.smali, method C4k (fills LX/0Fp; = wam_daily event)
const-string v0, "org.acra.ACRA"
invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;
; ClassNotFoundException -> false, success -> true
iput-object v0, p1, LX/0Fp;->A0W:Ljava/lang/Boolean;   ; -> wam_daily.is_whatsapp_plus_user
```

```java
// C1Z.java (contact-us diagnostics)
try { Class.forName("org.acra.ACRA"); sbA0m.append("nw-wap "); } catch (ClassNotFoundException unused) {}

// C10V.java (debug report builder)
try { Class.forName("org.acra.ACRA"); sb10.append("NW-WAP-1 "); } catch (ClassNotFoundException unused2) {}
```

| Öğe | Değer | Katman |
|------|-------|------|
| Kontrol | `Class.forName("org.acra.ACRA")` başarılı (sınıf classpath'te mevcut) | found |
| Alan adı | `is_whatsapp_plus_user` (`LX/0Fp;->A0W`), `wam_daily` event | found |
| Çıkışlar (sinks) | `wam_daily` telemetrisi; contact-us `diagnostic` string'i (`nw-wap `); debug-report metni (`NW-WAP-1 `) | found |
| Gerekçe | ACRA (`org.acra`) üçüncü taraf bir crash-reporting kütüphanesidir; resmi WhatsApp bunu içermez. Tarihsel olarak "WhatsApp Plus" ailesi repack'ler kendi crash telemetrisi için bunu içermiştir (`inferred`: alan adı modun döndürdüğü bir değer değil, WhatsApp'ın kendi etiket seçimidir) | found (prob) / inferred (etiketin anlamı) |
| Decompile boşluğu | `Cdt.java`'nın kendisi decompile edilmedi (yalnızca kardeş sınıf `CDT.java` mevcut); kontrol smali'den okunmuştur | found |

### 2.2 Ne YAPMIYOR

- `com.gbwhatsapp`, `com.yowhatsapp`, `com.fmwhatsapp`, `com.wmods.wppenhacer`, … gibi mod paket adlarının hiçbir allowlist/denylist'i decompile edilmiş istemcinin hiçbir yerinde yoktur — bu string'lerden hiçbiri `java_src` veya `smali*` içinde geçmez.
- Prob tek bir reflective sınıf lookup'ıdır, bir imza, hash veya davranış kontrolü değildir. `org.acra.ACRA`'yı basitçe içermeyen (veya sınıfı shade/rename eden) bir mod bunu kolayca atlatır; bu rapor başka bir şey iddia etmemektedir.
- Üç çıkış da tanılama/telemetri metni ve günlük bir analitik olaydır. `A0W`/`is_whatsapp_plus_user` değerini okuyup istemci davranışını değiştiren hiçbir dal bulunamadı.

---

## 3. Hook-framework ve repack iz araması (bulunamadı)

2.26.41.6 için tüm decompile edilmiş ağaçta (`java_src/`, tüm `smali*/`) arandı:

| Anahtar string(ler) | Hedef | Sonuç |
|-------------------|--------|--------|
| `Xposed`, `XposedBridge`, `de.robv`, `LSPosed` | Xposed/LSPosed hook framework varlığı | bulunamadı |
| `frida`, `Frida`, `re.frida`, `frida-server`, port `27042` | Frida enstrümantasyon sunucusu | bulunamadı (tek `frida` alt-string eşleşmesi bir public-suffix/TLD regex literal'i içinde, ilgisiz) |
| `substrate`, `Substrate` | Cydia Substrate hook framework | bulunamadı |
| `TracerPid` | klasik `/proc/self/status` ptrace-tracer tespiti | bulunamadı |
| `GBWhatsApp`, `gbwhatsapp`, `com.gbwhatsapp`, `FMWhatsApp`, `YoWhatsApp`, `OGWhatsApp`, `com.wmods.wppenhacer` | adlandırılmış mod-istemci paket string'leri | bulunamadı |
| `modded`, `unofficial`, `tampered`, `fake whatsapp`, `clone app` | genel mod-tespiti düz metin/log string'leri | bulunamadı |
| `CRC32` kullanımları (10 eşleşme) | dex/asset öz-checksum'u | tümü multidex yüklemesinde (`dextricks`) veya crash-report zip paketlemesinde, hiçbiri bir app-tamper öz-kontrolü değil |
| `checkSignatures` (3 eşleşme) | imza karşılaştırması | tümü IPC/çağıran-güven kontrolleri (`FileSharingHelper` aynı-imza çağıran kontrolü, bir Pixel companion-app güven kontrolü), modlanmış bir WhatsApp istemcisini tespit etmekle ilgisiz |
| `isDebuggerConnected` | anti-debug | yalnızca ANR dedektöründe (`SigquitBasedANRDetector`) ve crash yardımcılarında, bir tamper gate'i değil (`WA_CLIENT_INTEGRITY.md` §6.4'ü doğrular) |
| `/proc/self/status` (4 eşleşme, `KGi`/`KGw`/`KH8`/`KGp`) | — | bellek-istatistiği okuyucuları (muhtemelen tanılama için `VmRSS` toplama); orada `TracerPid` ayrıştırması bulunamadı |

**Önceki bir araştırma notunun çerçevelemesine düzeltme:** önceki bir statik-analiz notu WaEnhancer'ı "resmi uygulamanın bütünlük sisteminin hedeflediği türden modlanmış/resmi olmayan istemciye tam olarak uyan" şeklinde tanımlıyor ama resmi uygulamanın bunu isimle tespit ettiğini iddia etmiyor — bu okuma burada doğrulanmıştır: 2.26.41.6'da WaEnhancer'a özgü, GB'ye özgü veya Xposed'e özgü hiçbir tespit kodu yoktur. Bir WaEnhancer kurulumunda tetiklenebilecek tek istemci taraflı sinyal, genel `is_whatsapp_plus_user` ACRA probudur, ve bu da yalnızca modül (veya içerdiği bir bağımlılık) o sınıfı barındırıyorsa tetiklenir — WaEnhancer için özel olarak doğrulanmamıştır (`unknown`).

Bu, `WA_CLIENT_INTEGRITY.md` §6.4'ü genişletir; orada dex/asset CRC "kapsamlı şekilde aranmadı" olarak işaretlenmişti — şimdi arandı ve halen bulunamadı.

---

## 4. İstemci tarafında görünen sunucu taraflı sonuçlar

### 4.1 WFAC ban arayüzü

`WfacBanActivity` (`com.whatsapp.waffle.wfac.p191ui`) sunucudan gelen üç extra'yı okur ve render eder; bir neden hesaplamaz:

```java
int violationType   = getIntent().getIntExtra("ban_violation_type", -1);
String violationReason = getIntent().getStringExtra("ban_violation_reason");
int violationSource  = getIntent().getIntExtra("ban_violation_source", -1);
```

| Öğe | Katman |
|------|------|
| `ban_violation_type` / `ban_violation_source` opak integer'lardır; bunları adlandırılmış nedenlere (örn. "modified client") çözen bir enum istemci tarafında bulunamadı | found (absence) |
| `ban_violation_reason` serbest metin bir string'tir, muhtemelen sunucu tarafında şablonlanmış | found |
| §1–§3'teki tespit sinyallerinden (`is_whatsapp_plus_user`, imza uyumsuzluğu, root, kurulum kaynağı) herhangi birini bir `ban_violation_*` değerine bağlayan hiçbir kod yolu bulunamadı | found (absence) |

Tam ban-durum makinesi, GraphQL (`BizIntegrityQuery`), güven katmanları ve XMPP hata stanza'ları [`WA_BAN_SYSTEM_DEEP_EN.md`](WA_BAN_SYSTEM_DEEP_EN.md) içindedir; bu rapor o içeriği tekrar etmez. Sunucunun §1'in telemetrisinden herhangi birini (imza uyumsuzluğu, `is_whatsapp_plus_user`, root) bir ban girdisi olarak kullanıp kullanmadığı **bilinmemektedir** — bu sunucu taraflıdır ve statik olarak gözlemlenemez, `WA_CLIENT_INTEGRITY.md` §13'teki sonuçla aynıdır.

### 4.2 Özellik kısıtlaması (gating)

§1'in sinyallerine dayanarak bir özelliği devre dışı bırakan hiçbir istemci taraflı dal bulunamadı. Bütünlük/mod yüzeyinde gözlemlenen tek "kısıtlama", attestation/token isteklerinin kendisinin throttling edilmesidir (ab-props, integrity raporunda belgelenmiştir) — bir mod tespitine verilen yanıt değildir.

---

## 5. Saldırı yüzeyi: bir hook modülünün hedeflediği şey (WaEnhancer, `com.wmods.wppenhacer`)

Bu bölüm sınırın diğer tarafını — temsili bir Xposed/LSPosed modülünün host süreç içinde neyi hook ettiğini — tanımlayarak (büyük ölçüde yok olan) istemci taraflı tespitin kapsaması gerekenleri çerçevelemektedir. Kanıt kaynağı: yakalanmış bir `wa-data-root/` test dizininde WaEnhancer ile modlanmış bir kurulumun bıraktığı izler (`Protocols/waenhancer-mod/info.md`), WhatsApp'ın kendi APK'sının statik analizi değil. Katmanlar orada kaydedildiği şekliyledir.

| Yetenek | Mekanizma | Katman |
|------------|-----------|------|
| Dağıtım | `com.whatsapp` süreci **içinde** çalışan Xposed/LSPosed modülü (ayrı bir uygulama değil, bir repack değil) | found |
| Obfuscation yönetimi | Çalışma zamanı "Unobfuscator"ı: WhatsApp'ın obfuscate edilmiş sınıf/method adlarını modül başlatılışında çözer ve çözülmüş handle'ları önbelleğe alır (`UnobfuscatorCache.xml`, `UnobfuscatorCacheStrings.xml`), WhatsApp'ın kendi sürüm adına bağlı olarak keylenir, böylece önbellek her iki tarafın güncellemesinde de geçersiz olur | found |
| Varlık gizleme ("ghost mode") | Presence ile ilgili metotları hook eder; ayar `WaGlobal.xml` içinde saklanır (`ghostmode`) | found (artifact) |
| Anti-revoke / anti-read-receipt | Herkes için silme ve okundu-bilgisi kod yollarını ele alır; kendi depolarında shadow kopyalar tutar (`com_waenhancer_message_history.db` ve Room tabanlı bir `MessageHistory.db` — WhatsApp'ın kendisi mesaj depolama için Room kullanmaz) | found |
| Ham protokol görünürlüğü | `StanzaLogger.logStanza(...)` giden/gelen XMPP stanza'larını düz metin bir dosyaya yazar (`wae_stanzas.txt`) — yani modül, istemcinin kendi stanza-gönderme/alma yolunu, Noise/E2E katmanı zaten şifreyi çözdükten sonra yakalar | found |
| Hook kayıt tutma | Hook sayısını (`devtrace_logs/*.jsonl`, `eventType:"hook_config_loaded"`, `payload.hookCount`) günlükleyen çalışma başına tanılama | found |
| Kapsam sınırı | Yalnızca Java/UI katmanını hook eder; native kriptoyu veya Noise/chatd taşımasını değiştirmiyor gibi görünmektedir (axolotl/Signal store, post-quantum prekey'ler, keystore, OHAI/OPAQUE/WAFFLE native'leri dokunulmamış) | inferred |

§3 ile birlikte okunduğunda: resmi istemcide yüklü Xposed/LSPosed modüllerini listeleyen, kendi süreç belleğini hook trampolinleri için tarayan veya enjekte edilmiş kütüphaneler için `TracerPid`/`/proc/self/maps`'i kontrol eden hiçbir kod yoktur. Bu saldırı yüzeyi ile tespit arasında duran tek şey, tek ve genel `is_whatsapp_plus_user` sınıf probudur (§2), ve bu da bir hook framework'ünü değil, bir crash-reporting kütüphanesini hedeflemektedir.

---

## 6. Hata durumları / tuzaklar

| Belirti | Neden | Not |
|---------|-------|------|
| `wam_daily` içinde `is_whatsapp_plus_user = true`, başka hiçbir istemci etkisi olmadan | `org.acra.ACRA` classpath'te çözümlenebilir durumda | tasarım gereği yalnızca telemetri |
| contact-us veya debug raporlarında `diagnostic` içinde `nw-wap` / `NW-WAP-1` | aynı ACRA probu, farklı çıkış | destek-akışı metni, bir gate değil |
| WFAC ban ekranında sayısal koddan başka hiçbir neden yok | `ban_violation_type`/`ban_violation_source`'ın istemci taraflı bir enum'u yok | sunucu kontrollü, statik olarak çözülemez |
| "Xposed"/"Frida" aramasında hiçbir şey çıkmıyor | doğru — bu derleme hiçbir hook-framework tespiti içermiyor | bu özel string'ler için bir decompile boşluğu değil (tüm-ağaç araması) |
| Bir WaEnhancer kurulumu, hiçbir WhatsApp taraflı log olmadan mesaj/okundu-bilgisi davranışını değiştiriyor | WaEnhancer, WhatsApp'ın kendi telemetrisi orijinal çağrıyı gözlemleyebilmeden önce Java katmanını hook ediyor | §5'in kapsamı göz önüne alındığında beklenen |

---

## 7. Karıştırılmaması gerekenler

| Karıştırılmamalı | Gerçek |
|-----------------|------|
| `is_whatsapp_plus_user` ile bir mod-istemci allowlist'i | tek bir üçüncü taraf kütüphane sınıfı için reflective prob; mod paket adlarının bir listesi yok |
| Mod/tamper tespiti (bu rapor) ile hesap attestation'ı (`WA_CLIENT_INTEGRITY.md`) | farklı problemler: bu rapor *modlanmış bir istemci binary/runtime'ının* tespit edilmesiyle ilgilidir; integrity raporu sunucuya *gerçek bir cihaz/anahtarın* attest edilmesiyle ilgilidir — sadece ikisinin de telemetri olup uygulama (enforcement) olmaması noktasında örtüşürler |
| WFAC ban arayüzü (`WfacBanActivity`) ile ban karar mantığı | activity sunucudan gelen kodları/string'leri render eder; bir ban nedenine karar vermez veya hesaplamaz |
| WaEnhancer'ın `StanzaLogger` yakalaması ile E2E şifrelemeyi kırmak | modül stanza'ları süreç içinde zaten şifresi çözülmüş haliyle okur; Signal/Noise kriptografisinin kendisine saldırmaz |
| `safety-net-attestation` / imza / kurulum-kaynağı telemetrisi | bunlar mevcuttur ve `WA_CLIENT_INTEGRITY.md` içinde belgelenmiştir; bu rapor bunlar için yeni bir mekanik eklemez, sadece hiçbirinin hiçbir şeyi kısıtlamadığını belirtir |
| Bu raporda "bulunamadı" | bu özel derlemenin (2.26.41.6) decompile edilmiş Java/smali/string'lerinde yok olduğu anlamına gelir; sunucu taraflı tespit hakkında bir iddia değildir, çünkü o statik olarak gözlemlenemez |

---

## 8. Uçtan uca akış

```
[Device boots WhatsApp, possibly under a hook module or with a bundled crash-reporter lib]
    │
    ▼
[Cdt.C4k / C1Z / C10V]  Class.forName("org.acra.ACRA")
    │  success ──► is_whatsapp_plus_user = true ─► wam_daily
    │  success ──► "nw-wap" / "NW-WAP-1" ─► contact-us / debug-report text
    │  (no further branch — nothing reacts to this value in the client)
    ▼
[AbstractC38241gg / C27965CCj]  signature self-check → WAM 6251   (see WA_CLIENT_INTEGRITY.md §5)
[CHH]                           install-source flag  → WAM 10255  (see WA_CLIENT_INTEGRITY.md §5.4)
[C00L / Cdt]                    root / emulator / custom-ROM     → wam_daily  (see WA_CLIENT_INTEGRITY.md §6)
    │
    ▼
[WA telemetry backend]  (server-side use of all of the above: unknown, not observable)
    │
    ▼
[If the server bans the account]
    │  ban_violation_type / ban_violation_source / ban_violation_reason sent as intent extras
    ▼
[WfacBanActivity]  displays the server's values verbatim — no client-side cause mapping
```

```
[Attack surface, other side of the boundary — not WhatsApp code]
[Xposed/LSPosed host process: com.whatsapp]
    │
    ▼
[WaEnhancer module loads] ─ Unobfuscator resolves WhatsApp's classes at runtime
    │
    ├─► hooks presence methods ──────► ghost mode (WaGlobal.xml)
    ├─► hooks delete/read-receipt ───► shadow stores (MessageHistory.db, com_waenhancer_message_history.db)
    └─► taps stanza send/receive ────► wae_stanzas.txt (post-decryption plaintext)
```

---

## 9. Bilinmeyenler

| Soru | Neden bilinmiyor |
|----------|-------------|
| Sunucunun `is_whatsapp_plus_user`, imza uyumsuzluğu (6251), kurulum kaynağı (10255) veya root bayraklarını ban/güven-skoru girdisi olarak kullanıp kullanmadığı | sunucu taraflı, trafik gözlemlenmedi |
| `org.acra.ACRA`'nın güncel bir WaEnhancer/GB WhatsApp derlemesinde gerçekten mevcut olup olmadığı (yani mevcut tek sezgiselin onda tetiklenip tetiklenmeyeceği) | bu geçişte canlı bir mod derlemesine karşı doğrulanmadı |
| `ban_violation_type` / `ban_violation_source` değerleri için adlandırılmış ban-nedeni eşlemesi | istemci tarafında hiçbir enum çözülmedi; sunucu tarafında tanımlı |
| `libwhatsapp.so`, `libwasafe.so` gibi herhangi bir native kodun, `WA_CLIENT_INTEGRITY.md`'nin zaten yok bulduğunun ötesinde hook/tamper tespiti yapıp yapmadığı | stripped native kütüphaneler bu rapor için §3'teki string aramasının ötesinde kapsamlı şekilde yeniden izlenmedi |
| Sunucunun bir WaEnhancer tarafından yakalanmış `wae_stanzas.txt` türü bir görünürlüğü işleyip işlemediği (yani sunucunun protokol seviyesinde hook edilmiş bir istemciyi gerçek bir istemciden ayırt edip edemediği) | statik olarak gözlemlenemez |
