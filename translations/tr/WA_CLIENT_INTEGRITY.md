<!-- src-sha1: 4ca6293d8bc9da2aebc5db6f104c88b12dce1bd0 -->
# WhatsApp Client Integrity — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Android istemci bütünlüğü ve attestation — Keystore key attestation ("blacknoise"), Play Integrity (Java standard API ve native classic API), WASafe native token kütüphanesi, `integrity_payload` / `keystore_attestation` stanza'ları, kayıt `gpia` parametresi, uygulama imzası öz-kontrolü, kurulum kaynağı flag'i, root / emülatör / modlanmış istemci telemetrisi (`wam_daily`), nelerin kapılandığı vs yalnızca raporlandığı, nelerin unknown kaldığı

---

## 1. Bu build'de "client integrity" nedir

Tek bir kapı yoktur. İstemci birbirinden bağımsız birkaç kanıt ve sinyal üretir; bunların her biri cihazda oluşturulur ve sunucuya gönderilir. Değiştirilmiş, root'lu veya yeniden imzalanmış bir istemcide çalışmayı reddeden hiçbir istemci tarafı kodu bulunmadı. Tüm ifadeler dekompile edilmiş APK'nın statik analizidir (`versionCode 264100600`). Seviyeler: **found** = kodda okundu, **inferred** = çıkarıldı, **unknown** = statik olarak çözülemez.

Obfuscate isimler build'e özeldir ve 2.26.41.6'da kararlı dizelerden yeniden çözümlendi.

| Mekanizma | Üretir | Şu olarak gönderilir | Sunucu kullanımı |
|-----------|--------|----------------------|------------------|
| Keystore key attestation, dahili log etiketi `blacknoise` (`C25730yT`) | Attestation challenge'lı bir `AndroidKeyStore` EC anahtarının DER sertifika zinciri | `<ib><keystore_attestation>` stanza'sı; kayıt zamanında native'e devir; passkey ve companion-eşleştirme yolları | unknown (gözlemlenemez) |
| Play Integrity, Java standard API (`C45007Jkc`) | Standard Integrity token (`gpia`) | HTTP kayıt parametresi `gpia`; companion eşleştirme ("md-pairing") token'ı | unknown |
| Play Integrity, native classic API (`libwhatsapp.so`, `WAJIntegrityGpiaStatusRequest`) | JNI üzerinden Classic Integrity token | `<ib><integrity_payload>` (Java alıcısı found; native üreticiye bağlantı inferred) | unknown |
| WASafe (`libwasafe.so`, `libwasafedeps.so`) | Çağıranın verdiği verinin ECIES tarzı şifrelenmiş blob'u, base64 | unknown alıcı | unknown |
| Uygulama imzası öz-kontrolü (`AbstractC38241gg`, `C27965CCj`) | 0/1 değeri | WAM ortak özniteliği **6251** | unknown |
| Kurulum kaynağı flag'i (`CHH`) | `com.android.vending` kurucusu boolean'ı | WAM öznitelikleri `install_source_official`, **10255** | unknown |
| Cihaz durumu flag'leri (`Cdt` → `C0Fp`) | `is_rooted`, `is_genymotion`, `is_monkeyrunner_running`, `is_using_custom_rom`, `is_whatsapp_plus_user` | WAM event'i `wam_daily` | unknown |
| Destek tanılamaları (`C00L.A0F`) | "rted" etiketi | contact-us / hata ayıklama raporu dizeleri | yalnızca destek |

Client attestation değildir, karıştırmayın (bkz. 11): `com.whatsapp.integrityai` (cihaz üstü dolandırıcılık tespiti), `bizintegritysignals`, WFAC ban arayüzü (`com.whatsapp.waffle.wfac`), hesap bağlama (`com.whatsapp.waffle`).

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|-----|
| Keystore attestation | `C25730yT` | anahtar çifti, sertifika zinciri, imzalama (`A00`/`A01` alias, `A02` üretim, `A03` zincir, `A07` imza) |
| Attestation modu enum'u | `C02U` | `C02U.A00` = dynamic, `C02U.A01` = static |
| Stanza gönderen runnable | `RunnableC48591z1` case 3, `C41141ly` üzerinden | `keystore_attestation` gönderir |
| Connected handler | bağlantı handler'ında `A01` (`smali/X/0Yq`) | `sendKeystoreAttestation` zamanlar |
| Kayıt zamanı işi | `C25810yb`, `KZ2` case 39, `K49.A0s` | native'e static attestation, etiket `regtime_ka` |
| Companion ön ısıtma | `H1K` (attestation), `H1J` (Play Integrity) | eşleştirme için zinciri / token'ı önbelleğe alır |
| Play Integrity sarmalayıcı | `C45007Jkc` | standard-API prepare + request |
| Kayıt HTTP | `K49` | istek parametrelerine `gpia` ekler |
| JNI köprüsü | `com.whatsapp.wamsys.JniBridge` | `sendAttestationResult`, `jnidispatch*` callback'leri, `wsafeplatform_context` |
| İmza kapısı | `AbstractC38241gg` | sürüm penceresi + imzalama sertifikasının SHA-1'i |
| İmza doğrulayıcı | `C27965CCj` | paket adı + imzalama sertifikasının SHA-256'sı vs gömülü değerler |
| Kurulum kaynağı future'ı | `CHH` | `install_source_official` |
| WAM daily event | `C0Fp` (`getEventNameForFalco()` = `wam_daily`) | cihaz flag'leri |
| WAM flag doldurucu | `Cdt` (smali) | `C0Fp` boolean'larını doldurur |
| Root / emülatör yardımcıları | `C00L` | `A0F` root, `A0C` emülatör, `A0B` özel ROM, `A0D` test-otomasyonu |

---

## 2. Keystore key attestation ("blacknoise")

### 2.1 Anahtar üretimi (`C25730yT.A02`)

Hepsi ab-prop **1934** ile kapılanır (`A06()`, varsayılan `true`).

| Öğe | Değer | Seviye |
|-----|-------|--------|
| Keystore | `AndroidKeyStore` | found |
| Anahtar amacı | `4` (`PURPOSE_SIGN`), digest'ler `SHA-256`, `SHA-512`, kullanıcı kimlik doğrulaması gerekmez | found |
| Algoritma | ab-prop **2076**, varsayılan `"EC"`; `"RSA"` `PKCS1` padding ekler | found |
| İmza algoritması | ab-prop **2075**, varsayılan `"SHA256withECDSA"` | found |
| Alias tabanı | ab-prop **2074**, varsayılan `the_well_of_wishes_awaits_in_the_crypt_of_decay`; prop null olduğunda sabit kodlu yedek `my_personal_mini_pony` | found |
| Alias | dynamic: `<base>[_<suffix>]`; static: `<base>_static[_<suffix>]`; suffix = `ka_key_store_dynamic_alias_suffix` / `ka_key_store_static_alias_suffix` pref'lerinde saklanan rastgele UUID, yeniden üretim mevcut bir suffix bulduğunda döndürülür | found |
| Sertifika geçerliliği | now + ab-prop **2079** saniye (varsayılan 86400) | found |
| Attestation challenge | yalnızca SDK >= 24'te ayarlanır | found |
| Cihaz özellikleri attestation'ı | SDK >= 31'de `setDevicePropertiesAttestationIncluded(true)`; `ProviderException` olursa onsuz yeniden denenir (log `blacknoise/disbabling device ids att`) | found |

Attestation challenge düzeni (found):

```
challenge = BE64(unix_seconds) ‖ 0x1F ‖ nonce
nonce     = caller-supplied bytes, else SecureRandom(ab-prop 2078 bytes, default 32)
```

### 2.2 Yenileme ve kısıtlama

| Pref / prop | Anlam | Varsayılan | Seviye |
|-------------|-------|------------|--------|
| `ka_refresh_ts` + ab-prop **2079** | dynamic anahtar bundan daha eskiyse yeniden oluşturulur | 86400 s | found |
| `ka_static_refresh_ts` + ab-prop **4878** | static anahtar yenileme | 600 s | found |
| `ka_retried_ts` + ab-prop **2427** | dynamic: yeniden üretim çok erken denendi -> log `regeneration attempted too soon, waiting` | 600 s | found |
| `A04()` | her iki alias'ı siler ve tüm `ka_*` pref'lerini sıfırlar | – | found |

### 2.3 Sertifika zinciri (`C25730yT.A03`)

`keyStore.getCertificateChain(alias)`, her sertifika `getEncoded()` (DER), ters sırayla (önce root, en son leaf) tek bir bayt dizisinde birleştirilir. Boş zincir `empty list of certificates found` loglar. Hatalar hata raporlayıcıya `attestation-creation`, `attestation-nocertchain`, `attestation-nosign` olarak raporlanır (found). Zamanlama `att-gen` / `att-sign` olarak loglanır (found).

### 2.4 İmzalama (`C25730yT.A07`)

Static anahtarla bir çağıran payload'u üzerinde `Signature.getInstance(prop 2075)`. Eksik anahtar girdisi -> `attestation-nosign` "cannot sign payload, att pair missing". `A07`'nin çağıranları dekompile kodda bulunamadı (dekompile boşlukları olabilir); imzanın nereye gönderileceği unknown.

### 2.5 Zincirin dört tüketicisi

| # | Tetikleyici | Mod | Nonce | Alıcı | Seviye |
|---|-------------|-----|-------|-------|--------|
| 1 | Sunucu bağlandı (bağlantı handler'ında `handleConnected`, job adı `sendKeystoreAttestation`) | dynamic (`C02U.A00`) | istemci static (Noise) public key (`C25710yR.A0H()`) | `C10140Tq.A0X(node, 6)` ile `<ib><keystore_attestation>chain</keystore_attestation></ib>` | found |
| 2 | Kayıt (`K49.A0s`, job `regtime_ka`, runnable `KZ2` case 39) | static (`C02U.A01`) | istemci static public key | `JniBridge.jvidispatchIOO(1, ctx, chain)` ile native'e, retry/backoff ile (ab-prop'lar **2863** 1000 ms, **2864** 5 deneme); `K49.A0s` istendiğinde ab-prop **4696**'ya (1880 ms) kadar bekler | found (native kullanım unknown) |
| 3 | Companion kaydı başlangıcı (`C0YS` `startcompanionreg` -> `H1K.A00`) | dynamic | istemci static public key | `H1K` içinde önbelleğe alınır (alan `A02`), `KeyAttestationLifetimeManager` tarzı yardımcıyla yenilenir; ab-prop'lar **6430** (varsayılan `true`), **7217** (bucket), aralık **6431** (600000 ms), yeniden denemeler **6433**/**6434** ile kapılanır | found (önbellek); önbelleğe alınan baytların tüketicisi çözülmedi: unknown |
| 4 | Passkey sunucu API'si (`I16` case 18, `PasskeyServerApiImpl`) | dynamic | sunucunun verdiği baytlar | passkey çağıranına döndürülür | found (çağıranın ne yaptığı unknown) |

#1 için stanza kapısı: `A06()` ve ab-prop **1935** (varsayılan `true`), ve ab-prop **2067** saniyede (varsayılan 86400) en fazla bir kez, `ka_stanza_sent_ts` pref'inde saklanır. Null zincir `blacknoise: got null attestation chain in custom stanza` loglar ve hiçbir şey göndermez (found).

Stanza şekli (found):

```
<ib>
  <keystore_attestation>[binary: DER certs, root first]</keystore_attestation>
</ib>
```

`keystore_attestation` aynı zamanda bir sözlük token'ıdır (ikinci sözlük, `AbstractC40911lb.A01[0]`), dolayısıyla wire üzerinde token olarak kodlanır (found).

Bağlama: #1 ile #3'teki nonce istemcinin kendi Noise static public key'i olduğundan, sertifika zincirinin challenge uzantısı kimlik anahtarını taşır; bu da donanım anahtarını hesabın static anahtarına bağlar (nonce seçiminden inferred; sunucu kontrolü unknown).

---

## 3. Play Integrity

### 3.1 Java standard API (`C45007Jkc`)

| Öğe | Değer | Seviye |
|-----|-------|--------|
| API | `IntegrityManagerFactory.createStandard` -> `StandardIntegrityManager` | found |
| Cloud project numarası | `293955441834` (`PrepareIntegrityTokenRequest.setCloudProjectNumber`) | found |
| Prepare (`A00(callback, tag)`) | etiketli; token sağlayıcısı zaten varsa atlanır; ağ yoksa reddeder; 60 sn'de en fazla 5 prepare (pref `pref_gpia_prepare_call_count_in_last_interval`) | found |
| Request (`A01(callback, nonce, tag)`) | `StandardIntegrityTokenRequest.setRequestHash(nonce)`; sağlayıcı yoksa 1003 ile başarısız olur | found |
| Dahili hata kodları (`JCX`) | 1001 ağ yok, 1002 çok fazla prepare çağrısı, 1003 hazırlanmamış, 1004 zaman aşımı (`C47238Kk7`), 1005 static anahtar yok (`Kmc`) | found |
| Hata raporlayıcı event'leri (`GKY`) | `ka_at_md_generate_attestation`, `gpia_at_md_prepare`, `gpia_at_md_generate_attestation` | found |

Prepare çağrı noktaları (found): `RegisterPhone` (etiket `register_phone`), `VerifyPhoneNumber` (etiket `verify_phone`), companion eşleştirme (etiket `md-pairing`, `H1J`), ayrıca `C41354Hz3` içinde bir yeniden deneme yolu.

### 3.2 Kayıt HTTP parametresi `gpia`

`K49.A0V`, kayıt HTTP istek haritasına bir alan ekler:

```java
if (!flag(3753)) return;               // default false
nonce = Base64(static_public_key, NO_PADDING|NO_WRAP);   // C47343Kmc case 48
token = request(nonce, tag="reg");     // timeout ab-prop 4263, default 1800
map.put("gpia", token);
```

| Öğe | Değer | Seviye |
|-----|-------|--------|
| Kapı | ab-prop **3753**, varsayılan `false` | found |
| Nonce | istemci static public key'in base64'ü (flag'ler 3) (`C25710yR.A0H()`); null anahtar -> hata 1005 | found |
| Eklendiği yer | `checkIfExists` (iki kod yolu), `verifySecurityCode` | found |
| Diğer istekler (kod isteği, son kayıt) | dekompile kodda orada `A0V` çağrılmıyor | found (dekompilede yokluk) |
| Zamanlama metriği | `gpia-param-prepare` | found |

Varsayılan `false`, parametrenin yalnızca sunucu prop 3753'ü etkinleştirdiğinde gönderildiği anlamına gelir. Kayıt sunucusunun bunu zorunlu kılıp kılmadığı: unknown.

### 3.3 Companion eşleştirme token'ı

`H1J` (`A07(...)` ile kapılanır, prop **7006** varsayılan `false`, aralık **7007** = 21600000 ms) hazırlar ("md-pairing") ve `I16` case 3, nonce = base64(static public key, flag'ler 3), zaman aşımı prop **7010** (1000 ms) ile bir token ister. Hatalar `gpia_at_md_prepare` / `gpia_at_md_generate_attestation` olarak loglanır. Token'ın tüketicisi çözülmedi (unknown).

### 3.4 Native classic API ve `integrity_payload`

`libwhatsapp.so` içindeki dizeler (found): `WAJIntegrityGpiaStatusRequest`, `WAJIntegrityGpiaStatusRequestAttributes`, `_WAJIntegrityTriggerGPIAWithRequestAttributes`, `_WAJIntegritySendResponseOrRetry`, `_WCAAPIGenerateGPIAParamOnMain` ve `IntegrityManagerFactory.create(Context)`, `IntegrityTokenRequest.Builder` (`setNonce`, `setCloudProjectNumber`), `IntegrityManager.requestIntegrityToken` için JNI imzaları. Dolayısıyla native kod Play Integrity'yi (classic request) JNI üzerinden kendisi yönetir.

Java alıcısı (found):

```java
// JniBridge.jnidispatch... case 3  (callback "sendAttestationResult")
node = <ib><integrity_payload>{string}</integrity_payload></ib>   // C10140Tq.A0X(node, 194)
metric type "safety-net-attestation", result "success"/"failed"
```

`safety-net-attestation` metrik tip dizesi eski bir etikettir; hiçbir SafetyNet API'si kullanılmaz (bkz. 10). "Native `WAJIntegrityGpiaStatusRequest` `integrity_payload` dizesini üretir" ifadesi isimlerden **inferred**'dir; stripped native kod içindeki çağrı zinciri izlenmedi. Native bir status isteğinin neyin tetiklediği (istemci zamanlaması vs sunucu isteği) unknown.

Native, ab-prop'ları `jnidispatchIII(feature, kind)` ile okur; eşlenen ID'ler (found): kind 0: 12->13178, 13->13456, 15->22925, 16->24048; kind 1: 13->13455. `jnidispatchO(1)` ab-prop dizesi **10266**'yı döndürür (varsayılan boş). Bu prop'ların amacı unknown.

### 3.5 Diğer Play Integrity kullanıcıları

| Sınıf | Kullanım | Seviye |
|-------|----------|--------|
| `JK4`, `KM0` ailesi | kendi `StandardIntegrityManager`'ı olan reCAPTCHA Enterprise SDK'sı (`recaptcha.net`); varsa sonuç HTTP parametresi `recaptcha`'ya gider (`K49.A0Z`) | found |
| `KLL`, `KLN`, `C42885In8`… | paketlenmiş Play Core integrity implementasyonu (kütüphane kodu) | found |

---

## 4. WASafe native kütüphanesi

### 4.1 Java tarafı

| Hook | Davranış | Seviye |
|------|----------|--------|
| `jnidispatchI(4)` | `libwasafe.so` yükler (`"wasafe"`), `UnsatisfiedLinkError` durumunda `WCAAPIEnsureSafeLibraryLoaded libwasafe.so load failed` loglar | found |
| `jnidispatchI(5)` | `wsafeplatform_context` SharedPreferences'ından `runtime_override` pref'ini döndürür, yoksa `1090327562` sabitini | found |
| WAM özniteliği **15611** | aynı sabit, ortak özniteliklerde `1090327562` dizesi olarak yazılır | found |

`1090327562` değerinin anlamı unknown (aday: WASafe runtime / tespit tipi değeri, doğrulanmadı).

### 4.2 `libwasafe.so` (14480 bayt, arm64, stripped)

Export'lar: `WASafeSignalsCreate`, `WASafeSignalsConfigure`, `WASafeSignalsPrepare`, `WASafeSignalsGetBase64EncodedData`, `WASafeSignalsRelease`, `WASafeStatus`. Import'lar: libc (`stat`, `rand`, `srand`, `gettimeofday`, `malloc`…) ve `libwasafedeps.so`'dan `WASafeDepsCrypto*`.

| Fonksiyon | Dekompile davranış | Seviye |
|-----------|--------------------|--------|
| `WASafeSignalsConfigure(x)` | `x`'i (tespit tipi) bir global'de saklar, ikinci bir global'i temizler | found |
| `WASafeSignalsPrepare()` | bir global'e `0x1092` durum sabitini yazar; başka iş yok | found |
| `WASafeSignalsGetBase64EncodedData()` | bağlamın veri/uzunluğunu encrypt+base64'ten geçirir (`sub_6a00`) ve `{ptr, len}` döndürür | found |

`libwasafe.so`'nun bu build'i sinyal toplama içermez: root, debugger, hook, emülatör veya dosya yolu dizeleri yok ve tek dosya sistemi import'u `stat`'tır. `libwhatsapp.so` ayrıca bir `WASafeSignalsStub` dizesi ve `safesignals/prepare` ile `safesignals/generate` log etiketli `WAIntegrityPrepareSafeSignals(WASafeDetectionType)` içerir (found). Şifrelenen verinin nereden geldiği unknown.

### 4.3 `libwasafedeps.so`

`WASafeDepsCryptoInputCreate`, `...SetServerPublicKey`, `...SetData`, `...EncryptBase64`, `...ResultGetData/GetLength/Release` export eder; mbedtls import eder (`ctr_drbg`, `entropy`, `gcm_setkey`, `gcm_crypt_and_tag`). Yapı (import'lardan ve isimlerden found): rastgele ephemeral anahtar, sunucu public key'i ile paylaşılan sır, AES-GCM, base64. Kesin eğri ve KDF bu build için yeniden dekompile edilmedi; Curve25519 ECDH + AES-GCM yapısı **inferred**'dir. Sunucu public key değeri ve rotasyonu: unknown.

---

## 5. Uygulama imzası öz-kontrolü ve kurulum kaynağı

### 5.1 Kapı (`AbstractC38241gg.A00`)

```java
long vc = versionCode;
if (vc < 264100600 || vc > 264100608) return 0;          // outside window
sha1 = Base64(SHA-1(signatures[0]), 11);
return "OKD31QX-GP7GT780Psqq8xDb15k".equals(sha1) ? 1 : 0;
```

Sürüm penceresi bu build'in `versionCode` değerinde (264100600) başlar. Sonuç bir static'te önbelleğe alınır.

### 5.2 Doğrulayıcı (`C27965CCj.A00(pkg, certBytes)`)

| Adım | Davranış | Seviye |
|------|----------|--------|
| 1 | Paket adı 5 baytlık bir anahtarla XOR maskelenir ve `com.whatsapp` ile `com.whatsapp.w4b` değerlerine çözülen iki gömülü bayt dizisiyle karşılaştırılır | found |
| 2 | Paket ikisinden de değilse: hemen `true` döndürür | found |
| 3 | Aksi halde sertifika baytlarının SHA-256'sı, XOR maskelenip iki gömülü 32 baytlık değerle karşılaştırılır; eşleşme -> `false`, eşleşmeme -> `true` | found |

Bu metodun dekompilesi başarısız oldu; adımlar talimat dökümünden okundu.

### 5.3 Tüketici

WAM `initializeCommonAttributes` içinde (runnable `RunnableC29340CoR`):

```java
long r = AbstractC38241gg.A00(ctx);          // 1 only when version window + SHA-1 match
if (r == 1) r = verifier(pkg, cert) ? 0 : 1;
common attribute 6251 = r;                   // 1 = both checks passed, 0 = otherwise
```

Yani **6251 = 1**, "imzalama sertifikası WhatsApp'ın gömülü değerleriyle eşleşiyor" anlamına gelir (found); 0, uyuşmazlık veya pencere dışı build anlamına gelir (found). Değer yalnızca telemetride raporlanır. İstemcide hiçbir şey buna tepki vermez (sonucu okuyup engelleyen veya düşüren kod yolu bulunamadı). Sunucu kullanımı: unknown.

### 5.4 Kurulum kaynağı

`getInstallSourceInfo().getInstallingPackageName()` (SDK >= 30, değilse `getInstallerPackageName`) `com.android.vending` ile karşılaştırılır (`C18970md`, `RunnableC29340CoR`): `CHH.A01` future'ında saklanır. WAM özniteliği **10255** olarak ve logging öznitelik kümelerinde `install_source_official` olarak raporlanır (`HO4`, `C08650Nr`, `AbstractC35718FdU`). Ayrıca `C0Fp` alanı `install_source` (`wam_daily`). Aynı karşılaştırmanın ayrı kullanımları Voltron modül kurucusunu seçer (`AbstractC12860bs`) (found). Sonuç telemetri artı modül-indirme yönlendirmesidir; uygulama zorlaması bulunamadı.

---

## 6. Root, emülatör ve modlanmış istemci sinyalleri

### 6.1 `wam_daily` cihaz flag'leri

`C0Fp`, `wam_daily` event'idir (`getEventNameForFalco()`); aşağıdaki alanları `Cdt` içinde (smali) doldurulur. Raporlanır, zorlanmaz (found).

| Alan | Kaynak | Seviye |
|------|--------|--------|
| `is_rooted` | `C00L.A0F(telephony helper)` | found |
| `is_using_custom_rom` | `C00L.A0B()` (kernel/üretici/görüntü dizeleri: cyanogen, debug, Darky, XDAndroid, MIUI…) | found |
| `is_whatsapp_plus_user` | `Class.forName("org.acra.ACRA")` başarılı olur (sınıf bu APK'da yok; tipik olarak üçüncü taraf istemcilerce paketlenir) | found (kontrol); "tipik olarak paketlenir" inferred |
| `is_genymotion` | `Cdt` içinde `com.genymotion.superuser` bölgesi için paket yoklaması; kesin koşul kısmen izlendi | found (yoklama), mantık inferred |
| `is_monkeyrunner_running` | kaynak çözülmedi | unknown |
| `google_play_services_available`, `google_play_services_version`, `install_source` | aynı event'te mevcut | found |

### 6.2 `C00L.A0F` root sezgisi

Static olarak önbelleğe alınır. Şunlardan herhangi biri olduğunda true: `Build.TAGS` `test-keys` içerir; `/system/app/Superuser.apk` var; `/system/bin/su` veya `/system/xbin/su` konumunda `su` çalıştırılabilir (`canExecute`), ek loglama `app/dly` ile; emülatör benzeri ürün/model/üretici (`sdk`) veya SIM/telephony yok (`z` flag'i yalnızca log son eki için kullanılır, found). İlgili yardımcılar: `A0C` emülatör (`generic` marka/cihaz, `goldfish`, `ranchu`, `google_sdk`, `Emulator`, `Android SDK built for x86`, `Genymotion`), `A0D` test otomasyonu (`fb.running_sapienz` sistem özelliği).

### 6.3 `A0F` nerede tüketilir

| Tüketici | Kullanım | Seviye |
|----------|----------|--------|
| `C10V` hata ayıklama raporu oluşturucu | tanılama metnine `DC-RTED` (root) ve `DC-BACRM` (özel ROM) ekler | found |
| `C1Z` contact-us tanılama haritası | anahtar `diagnostic` = `rted ` (ve `org.acra.ACRA` varsa `nw-wap `) | found |
| `C28049CFz` (doğrulama akışı durumu) | telefon numarası ekranında contact-us bağlamı `register-phone-rtd` | found |
| `Cdt` | `wam_daily.is_rooted` | found |
| `KH2` (crash raporlayıcı `lacrima`) | `ExtraDeviceInfoCollector` root flag'ini (`test-keys`, `Superuser.apk`, `PATH` üzerinde `su`) crash raporlarına yazar | found |

Bunların hiçbiri kaydı veya mesajlaşmayı engellemez (found: bu boolean'lar üzerinde akışı sonlandıran dal yok). Sunucunun `wam_daily` flag'lerini değerlendirip değerlendirmediği: unknown.

### 6.4 Bulunamayanlar

| Kontrol | Sonuç |
|---------|-------|
| WhatsApp kodunda Magisk, Xposed (`de.robv`), Substrate, Frida dizeleri (`libwhatsapp.so`, Java) | bulunamadı |
| `ro.kernel.qemu`, `FLAG_DEBUGGABLE` öz-kontrolü | bulunamadı |
| Adlandırılmış mod istemcileri (GB, FM, Plus) için yasaklı paket listesi | bulunamadı |
| dex / asset CRC öz-kontrolü | bu geçişte bulunamadı (kapsamlı aranmadı) |
| WhatsApp'ın kendi attestation kodunda donanım destekli anahtar kontrolü (`KeyInfo.isInsideSecureHardware`) | bulunamadı (yalnızca kütüphane sınıflarında `BinderC48420LDc`, `C51962N8y`) |
| `FetchIntegritySignals`, `IntegrityChallengeResponse`, `relax_integrity_constraints_for_bb_wa_tenured_accounts` | APK'nın hiçbir yerinde bulunamadı (Java, smali, asset'ler, native) |
| `SafetyNet` API | bulunamadı |

`isDebuggerConnected` yalnızca ANR dedektöründe (`SigquitBasedANRDetector`) ve crash yardımcılarında görünür.

---

## 7. Feature flag'ler ve ab-prop'lar

| ID | Değer / varsayılan | Neyi kontrol eder |
|----|--------------------|-------------------|
| **1934** | `true` | blacknoise ana kapısı (`C25730yT.A06`) |
| **1935** | `true` | bağlandıktan sonra `keystore_attestation` stanza'sını gönder |
| **2067** | 86400 | stanza gönderimleri arası asgari saniye |
| **2074** | `the_well_of_wishes_awaits_in_the_crypt_of_decay` | anahtar alias tabanı |
| **2075** | `SHA256withECDSA` | imza algoritması |
| **2076** | `EC` | anahtar algoritması |
| **2078** | 32 | rastgele nonce uzunluğu |
| **2079** | 86400 | sertifika geçerliliği ve dynamic yenileme saniyeleri |
| **2427** | 600 | dynamic yeniden üretimler arası asgari saniye |
| **4878** | 600 | static yenileme saniyeleri |
| **2863** / **2864** | 1000 / 5 | kayıt zamanı backoff tabanı (ms) / deneme sayısı |
| **4696** | 1880 | kayıtta attestation için bekleme (ms) |
| **3753** | `false` | kayıt `gpia` parametresi |
| **4263** | 1800 | `gpia` istek zaman aşımı |
| **6430** | `true` | companion attestation ön ısıtma (`H1K`) |
| **6431** | 600000 | companion attestation önbellek yaşı (ms) |
| **6433** / **6434** | 5 / 1000 | companion attestation lifetime-manager deneme sayısı / zaman aşımı |
| **7217** | 1 | companion attestation bucket modülü |
| **7006** | `false` | companion Play Integrity ön ısıtma (`H1J`) |
| **7007** | 21600000 | companion token önbellek yaşı (ms) |
| **7009** / **7010** | 5 / 1000 | companion Play Integrity deneme sayısı / zaman aşımı |
| **10266** | boş dize | `jnidispatchO(1)` ile native'e verilen dize |
| **26215** | `false` | `K49` içinde alternatif verifySecurityCode yolu (integrity'ye özgü değil) |

Varsayılanlar derlemeye gömülü değerlerdir; sunucu ab-prop'ları geçersiz kılabilir (found: prop tablosu; sunucu değerleri unknown).

---

## 8. Hata durumları

| Belirti | Sebep | Çözüm / not |
|---------|-------|-------------|
| `keystore_attestation` stanza'sı yok | prop 1934 veya 1935 false; son 2067 sn içinde gönderildi; null zincir | tasarım gereği |
| `attestation-creation` hata raporu | anahtar üretimi başarısız (`ProviderException`, TEE yok) | sonra yeniden denenir, 2427 ile kısıtlanır |
| `attestation-nocertchain` | `getCertificateChain` başarısız veya boş | – |
| `attestation-nosign` | `A07` static anahtar girdisi olmadan çağrıldı | – |
| `blacknoise/regeneration attempted too soon, waiting` | `ka_retried_ts` 600 sn içinde | bekleyin |
| `blacknoise: not boostrapped for reg` | kayıt zamanında `C25810yb.A00` false | o kayıt için attestation atlandı |
| Play Integrity 1001 / 1002 / 1003 / 1004 / 1005 | ağ yok / 60 sn'de > 5 prepare / hazırlanmamış / zaman aşımı / static anahtar yok | dahili kodlar (`JCX`) |
| kayıt isteğinde `gpia` eksik | prop 3753 false veya istek başarısız (null sonuç boş olarak konur) | bkz. 3.2 |
| `libwasafe.so load failed` | `UnsatisfiedLinkError` | yalnızca loglanır |
| İmza özniteliği 6251 = 0 | yeniden imzalanmış APK, farklı sertifika veya `264100600..264100608` dışı build | yalnızca telemetri |

---

## 9. Baileys / protokol istemcileri

| Öğe | İfade | Seviye |
|-----|-------|--------|
| Uygulama tarafı kontroller | Saf protokol istemcisi yukarıdaki kodun hiçbirini çalıştırmaz | found (tanım gereği) |
| `keystore_attestation` / `integrity_payload` stanza'ları | Bunları atlayan bir istemci onları basitçe göndermez; sunucunun bu tür hesapları reddedip, sınırlayıp veya işaretleyip işaretlemediği: unknown | unknown |
| `gpia` kayıt parametresi | Varsayılan olarak isteğe bağlı (prop 3753 `false`); bölge/hesap başına sunucu tarafı zorlaması: unknown | unknown |
| Attestation taklidi | Zincir donanım/Google root'larına dayanmalı ve challenge'ı taşımalıdır; kopyalanacak istemci sırrı yok, doğrulama sunucuda yaşar | inferred |
| Bilinen risk | Sunucu tarafı politika, bu raporun gözlemleyemediği verilere (davranış, hesap yaşı) bağlıdır | unknown |

Çözüm: statik olarak türetilebilir bir şey yok. Uydurma değerler göndermeyi destekleyen hiçbir kanıt burada bulunmadı.

---

## 10. Temel ayrımlar

| Karıştırmayın | Gerçek |
|----------------|--------|
| `safety-net-attestation` metrik dizesi vs SafetyNet | yalnızca etiket; payload Play Integrity'den gelir; kodda SafetyNet API'si yok |
| `keystore_attestation` vs `integrity_payload` | farklı stanza'lar: DER sertifika zinciri (bayt) vs Play Integrity token dizesi; farklı üreticiler (Java/Keystore vs native/Play) |
| Java `gpia` (standard API, request hash) vs native classic GPIA | farklı API'ler ve alıcılar (HTTP parametresi vs `<ib>`); native varyantın nonce oluşturması izlenmedi |
| Static vs dynamic attestation | static alias `..._static` (kayıt), dynamic alias (bağlantı sonrası, companion, passkey) |
| Nonce | üç tüketicide istemci static public key; passkey tüketicisinde sunucu baytları |
| `blacknoise` vs WASafe | Keystore attestation (Java) vs native şifrelenmiş-blob kütüphanesi |
| WASafe vs "signals" | bu build'in `libwasafe.so`'su hiçbir şey toplamaz; isim sinyalleri ima eder, kod etmez |
| 6251 vs 10255 | imza eşleşmesi vs Play kurucusu |
| `is_whatsapp_plus_user` vs mod-istemci izin listesi | tek bir reflection sınıf yoklaması; izin listesi yok |
| `integrityai`, `bizintegritysignals` | içerik / business güvenlik özellikleri (dolandırıcılık tespiti, business sinyalleri arayüzü), client attestation değil |
| WFAC / `waffle` | ban arayüzü ve hesap bağlama, attestation bileşeni değil |
| Raporlama vs zorlama | bulunan tüm root, emülatör, imza ve kurucu sonuçları telemetri veya destek metnidir |

---

## 11. Client attestation olmayan ilgili bileşenler

| Bileşen | Gerçekler | Seviye |
|---------|-----------|--------|
| `com.whatsapp.integrityai` | `IntegrityAiOrchestrator`, `ScamDetectorImpl`, model indirme (`IntegrityAiModelDownloadCoordinator`, cihaz katmanı), opt-in arayüzü `ScamDetectionSettingsActivity`; sonuç deposu etiketi `IntegrityAi/ScamDetectionResultStore`; `kaleidoscope` adlı bir native sınıflandırıcı bu build'de yeniden doğrulanmadı | found (yapı); native kısım unknown |
| `com.whatsapp.bizintegritysignals` | arayüzde gösterilen business integrity sinyalleri için GraphQL fetcher ve manager | found |
| `com.whatsapp.waffle.wfac` | ban kararı arayüzü (`WfacBanActivity`, `WfacBanDecisionFragment`, `WfacUnbanDecisionFragment`) | found |
| `com.whatsapp.waffle.accountlinking` ve kardeşleri | hesap bağlama, SSO, crossposting, yaş kontrolü | found |

---

## 12. Uçtan uca akış

```
[Registration screens: RegisterPhone / VerifyPhoneNumber]
    │  C45007Jkc.A00  prepareIntegrityToken (cloud project 293955441834, tag register_phone / verify_phone)
    │  K49.A0s  "regtime_ka": C25730yT.A03(static)  nonce = static pubkey
    │      └── JniBridge.jvidispatchIOO(1, ctx, chain)  ──►  [native wamsys]  (use unknown)
    ▼
[K49 HTTP: exist / verifySecurityCode]
    │  if ab-prop 3753:  gpia = standard-API token, requestHash = b64(static pubkey)
    ▼
[WA registration server]  (validation not observed)

[Connected session]
    │  handleConnected ─► job "sendKeystoreAttestation"
    │  ab-props 1934 && 1935, once per 86400 s
    │  C25730yT.A03(dynamic, nonce = static pubkey) ─ AndroidKeyStore EC key, challenge = ts ‖ 0x1F ‖ nonce
    ▼
<ib><keystore_attestation>DER chain, root first</keystore_attestation></ib>
    ▼
[WA server]  (use unknown)

[Native libwhatsapp]  WAJIntegrityGpiaStatusRequest ─► classic IntegrityManager via JNI   (inferred link)
    │  JniBridge callback sendAttestationResult
    ▼
<ib><integrity_payload>token</integrity_payload></ib>   (node code 194)
    ▼
[WA server]  (use unknown)

[Companion pairing]
    │  C0YS startcompanionreg ─► H1K (chain cache) + H1J (GPIA token, tag md-pairing)
    ▼  consumer of cached bytes/token: unknown

[Telemetry, daily and common attributes]
    │  6251 signature match, 10255 Play installer, 15611 wasafe constant
    │  wam_daily: is_rooted, is_genymotion, is_using_custom_rom, is_whatsapp_plus_user, install_source
    ▼
[WA server]  (use unknown)
```

---

## 13. Unknown'lar

| Soru | Neden unknown |
|------|---------------|
| Herhangi bir token'ın sunucu doğrulaması ve zorlaması | sunucu tarafı, trafik gözlemlenmedi |
| Native `WAJIntegrityGpiaStatusRequest`'i neyin tetiklediği ve nonce'ın nasıl oluşturulduğu | stripped native kod izlenmedi (büyük kütüphane için dekompiler burada mevcut değil) |
| WASafe girdi verisinin nereden geldiği ve `1090327562`'nin ne anlama geldiği | stripped native'lerde üretici bulunamadı |
| Kayıt zamanı attestation baytlarının native kullanımı | yalnızca JNI girişi (`jvidispatchIOO(1)`) görünür |
| `H1K` önbelleğe alınmış zincir ve `H1J` token tüketicileri | çağrı noktaları dekompile kodda çözülmedi |
| ab-prop 10266'nın ve `jnidispatchIII` feature ID'lerinin anlamı | yalnızca değerler |
| `is_monkeyrunner_running` kaynağı, kesin `is_genymotion` koşulu | izlenmedi |
| `C25730yT.A07` (imzalama) çağıranları | hiçbiri bulunamadı; dekompile boşlukları olabilir |
| Telemetri flag'leri için herhangi bir zorlama olup olmadığı | istemci dalı bulunamadı; sunucu unknown |
