<!-- src-sha1: 95a792ca8e841aadc06a8e3fae785590574c4eba -->
# WhatsApp Noise Transport — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android sohbet taşıması (chatd): endpoint'ler ve bağlantı sırası, edge yönlendirme, TCP çerçeveleme, Noise XX / IK / PQ handshake, sertifika zinciri kontrolleri, ClientPayload (UserAgent, DevicePairingData, connect type / reason), taşıma şifresi ve sayaçlar, binary node kodlaması, login sonucu ve hata kodları, keepalive, yeniden bağlanma backoff'u, stream:error, feature flag'leri, ilgili taşımalar (Tigon HTTP, DistribGW, Tigon Noise kanalı, MQTT), Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

chatd, her stanza'yı (mesajlar, receipt'ler, IQ, presence, bildirimler) taşıyan tek uzun ömürlü bağlantıdır. Android'de düz bir TCP soketidir (WebSocket değil); üzerinde bir Noise handshake çalışır, ardından her biri tek bir binary kodlanmış node içeren, uzunluk önekli AES-GCM çerçeveleri gelir. Tüm ifadeler çözülmüş (decompile edilmiş) APK'nın statik analizinden gelir; ağ üzerinde hiçbir şey yakalanmadı. Kademeler: **found** = kodda okundu, **inferred** = çıkarım, **unknown** = çözülemedi. Gizlenmiş (obfuscated) adlar build'e özgüdür ve 2.26.41.6 içinde yeniden çözümlendi.

| Katman | 2.26.41.6 adı | Rol |
|--------|---------------|-----|
| Bağlantı thread'i | `HandlerThreadC12340b0` (log etiketi `ConnectionThread`) | bağlanma, handshake, login, okuma döngüsü, bağlantıyı kesme |
| Bağlantı sırası / DNS | `C37151de` (durumlar), `C37031dS` (`A0G` ilerletme, `A0D` soket fabrikası), `C36881dC`, `AbstractC47101wK` (sabit kodlu host-IP tablosu), `C36821d6` (yedek IP'ler) | sıradaki host / port / proxy |
| Handshake sürücüsü | `C38791hg` (`NoiseSocket/*` logları) | intro baytları, ClientHello, ServerHello, sertifika kontrolleri, ClientFinish |
| Noise durumu | `C38921hv` (+ `C38941hx` hash, `C38981i2` AES-GCM, `AbstractC38961i0` HKDF), `C40331kf` (taşıma anahtarları + sayaçlar) | saf Java |
| Çerçeve I/O, node codec'i | `C38891hs` / `C38901ht`; `C40411kn` (encoder), `C24610wf` (decoder), `AbstractC40911lb` (sözlük) | çerçeveleme, binary XML |
| Proto'lar | `C39211ii`, `C39161id`, `C39231ik`, `C39241il` (handshake); `C24843Amz`, `C24842Amy`, `C24841Amx`, `C25757B9r`, `BC0` (sertifikalar); `C38001fP`, `C38051fp`, `C38661hS` (payload) | wire mesajları |
| Güven, PQ | `AbstractC44011qk` (sabitlenmiş kök); `C38811hi`, `AbstractC38821hj`, `AbstractC38831hk`, `C38761hd` (PQ yapılandırması, sunucu statik anahtarları) | sunucu kimliği, ML-KEM-512 hibrit |
| Payload oluşturucu | `C37991fK` tarafından toplanan `AbstractC43901qZ` içindeki katkıcılar | ClientPayload |
| Keepalive, zamanlayıcılar, yeniden bağlanma | `C14U` (`ClientPingManager`), `C9EN` (ping IQ), `HandlerC21850s9`, `C11380Yq` (`MessageHandler`), `C0X9` (backoff) | ping, zaman aşımları, yeniden deneme |
| Gelen kontrol | `C40581l4` (`<ib>`), `C40601l6` / `C37961fH.A1B` (`stream:error`) | sunucu bildirimleri |

Raporun geri kalanını belirleyen noktalar:

- Noise durum makinesi, HKDF, AES-GCM ve çerçeve codec'i **Java**'dır. Yalnızca Curve25519 (`org.whispersystems.curve25519`, `OpportunisticCurve25519Provider`, native, Java yedekli) ve ML-KEM çağrıları (`KEMKeyPair.generateNative`, `KEMSecretKey.decapsulateNative`) native'dir. Tersine mühendislik yapılacak native bir chatd uygulaması yok (found).
- Intro başlığı bu build'de `WA 06 03` sabitidir (bölüm 3.1). `C38791hg`'ye geçirilen protokol sürümü int'i tek çağrı noktasında sabit 6'dır; bu yüzden sürüm 5 düz sertifika dalına pratikte ulaşılamaz (found; ulaşılamazlık tek sabit çağrı noktasından inferred).
- `devicePairingData` yalnızca user JID'i olmayan bir bağlantı tarafından gönderilir; `ConnectionThread` buna yalnızca companion kaydında izin verir. Bu build'de birincil telefon kaydının bir parçası değildir (bölüm 6.4).
- Ana gönderim yolundaki giden stanza'lar yalnızca gelenler değil, DEFLATE ile sıkıştırılır (flags `3`) (bölüm 8.1).

---

## 2. Endpoint'ler ve bağlantı sırası

### 2.1 Host'lar ve port'lar (found)

| Host | Nerede | Notlar |
|------|--------|--------|
| `g.whatsapp.net` | `C37151de` adım 5, 9; `C36881dC.A01` (sabit kodlu IP'ler) | birincil sohbet host'u |
| `g-fallback.whatsapp.net` | adım 13, 14 | ikinci host |
| `e1` ... `e16.whatsapp.net` | `C37151de.A0F` (16 giriş), adım 7 ve 11 | `ConnectionSequence/getEdgeHost`; rastgele seçim veya geçmişte saklanan host |
| sabit kodlu IP tablosu | `AbstractC47101wK.A00`, adım 6 ve 10 | host'u IP listesine eşler, `eN` host'larını ve `g.whatsapp.net`'i kapsar |
| `<ib><fbip>` listesi | `C40581l4` ile `C36821d6.A02` | virgülle ayrılmış IP'ler, yedek yöneticisi tarafından saklanır (adım 2 / 8 girdisi, inferred) |
| kullanıcı proxy'si / SOCKS | adım 12, `C48201yM` | `java.net.Proxy.Type.SOCKS`, bağlantı zaman aşımı 30000 ms |

Port'lar: 443 ve 5222 (her denemede rastgele seçim, `C37151de.A00`; constructor ayrıca 3. ve 4. adımların port sırasını belirleyen bir yazı-tura atar) ve `:80` adımları için 80. Son başarılı bağlantının port'u flag **33512** açıkken yeniden kullanılır (found).

### 2.2 Sıra durumları (found, `C37151de.A02`, ilerletme `C37031dS.A0G` içinde)

| Adım | Hedef |
|------|-------|
| 0 | başlangıç, uygulanabilir ilk adımı seçer |
| 1 | debug / override `InetSocketAddress` (terminal) |
| 2 | `A04` biti set edilmiş, sunucunun verdiği endpoint girişleri (liste `A0A`), tek tek; her giriş kendi TLS bitini `A05` taşır |
| 3, 4 | yapılandırılmış host string'i `A07`, iki port üzerinde (443 / 5222 rastgele sırayla) |
| 5 | 443 üzerinde `g.whatsapp.net` (flag **20801**) veya rastgele 443 / 5222 |
| 8 | `A04` biti olmayan, sunucunun verdiği girişler (liste `A09`); decompile edilmiş dal sırası belirsiz |
| 9 | `g.whatsapp.net:80` |
| 15 | HISTORY: son başarıda saklanan adımı / host'u / port'u yeniden dene (history adımı geçerliyse ve flag **22916** kapalıysa 9'dan sonra eklenir) |
| 13, 14 | 443 / 5222 üzerinde `g-fallback.whatsapp.net`, ardından `:80` |
| 6, 10 | `g.whatsapp.net` için sabit kodlu IP, ardından `:80` |
| 7, 11 | rastgele edge host `eN.whatsapp.net`, ardından `:80` |
| 12 | kullanıcı proxy'si (terminal) |
| 16 | tükendi |

9. adımdan sonraki sıra (found): 9, [15], 13, 14, 6, 10, 7, 11, 16. Son başarı `last_successful_connection_step`, `_host`, `_port` tercihlerinde saklanır (found, `C37031dS.A00`). Bir SOCKS servis yapılandırması etkinken ve flag **23630** kapalıyken 2. ila 4. adımlar `Skipping sequence ... due to active proxy` loglar (atlama semantiği inferred).

### 2.3 Soket (found, `C37031dS.A0D`)

| Yön | Değer |
|-----|-------|
| Soket | düz TCP; hem IPv4 hem IPv6 adresleri varsa Happy Eyeballs (`ConnectionSocketFactory/try_connect/using-happyEyeball`) |
| TLS sarmalayıcı | yapılandırma biti `A07` bir `SSLSocketFactory` seçer; sunucunun verdiği her giriş için (`A05`), 443 portundaki adım 1 için ve 443 portundaki edge host'lar (adım 7) için ayarlanır. Adım 5 (`g.whatsapp.net`) bit kapalı olarak oluşturulur |
| Soket zaman aşımı | `CeF(30000)` ile ayarlanan 30000 ms (semantik inferred: okuma zaman aşımı) |
| TCP keepalive | `configureTcpKeepalive`: flag **7831** açıksa ve soket destekliyorsa keepalive etkinleştirilir ve flag **7832** (varsayılan 2), **7833** (varsayılan 10), **7834** (varsayılan 10) değerlerinden üç int uygulanır (idle / interval / count, çıkarımla) |
| Çıktı tamponlama | flag **33751** açıksa yazıcı bir `BufferedOutputStream` ile sarılır, böylece intro baytları ve ClientHello tek yazmada çıkar (found) |

TLS ile sarılmış endpoint'lerin TLS içinde aynı Noise baytlarını taşıyıp taşımadığı kod yolundan inferred'dır (`C38791hg` yalnızca stream alır); bir native lib içinde `chatd_non_secure_tls_wrapper_resumption` adlı bir metrik var.

### 2.4 DNS çözümleme (found)

`DNSResolutionMethod`, `ClientPayload.dnsSource` içinde bildirilir (bölüm 6.5): `SYSTEM`, `GOOGLE`, `HARDCODED`, `OVERRIDE`, `FALLBACK`, `MNS`, `MNS_SECONDARY`, `SOCKS_PROXY`. Flag **13545** (string; `C37151de.A01` tarafından tanınan değerler `secondary`, `hardcoded`, `none`) çözümleyici zincirini ayarlar. Önceki sorgulardan önbelleğe alınmış yanıtlar, yeni bir sorgudan önce süreleri dolana kadar kullanılır (`C36881dC.A03`).

---

## 3. Çerçeveleme

### 3.1 İlk çerçeveden önceki baytlar (found, `C38791hg`)

```
[ 'E' 'D' 00 01 | len24 | routing_info ]     only when routing_info is non-empty
[ 'W' 'A' 06 03 ]                             always
[ len24 | HandshakeMessage{clientHello} ]     first frame
```

- Edge başlığı: magic `45 44 00 01` (`C38791hg.A0B`), 3 baytlık big-endian blob uzunluğu, ardından `routing_info` baytları (tercih, dolgusuz ve satır kaydırmasız base64; `C38801hh.A00` tarafından saklanır, en fazla 256 bayt: "The routing info should be smaller than 256 bytes."). Soket üzerinde ham, Noise transkriptinin dışında.
- Intro: `57 41 06 03` = "WA", protokol 6, sözlük 3 (`C38791hg.A04`); aynı zamanda Noise prologue'u (4.2). else dalı `57 41 05 03` döndürür, ancak constructor sürümü 6'ya sabitler.

### 3.2 Çerçeve yapısı (found)

Her çerçeve 3 baytlık big-endian bir uzunluk (`AbstractC38721hZ.A04` / `A00`; yazmalar 2^24'ün altında olmalı, aksi halde `data too large to write`) ve ardından gövdeden oluşur: handshake sırasında handshake protobuf'u, sonrasında AES-GCM şifreli metni.

Okuyucu (`C38891hs`): tam olarak 3 uzunluk baytı, ardından gövde. ServerHello okunurken ASCII `GOA`'ya (`47 4F 41`, `C38891hs.A01`) eşit üç uzunluk baytı `X.1sn` fırlatır (log `socket/goaway`); handshake sonrası okuma yolunda (`C24610wf.Be0`) böyle bir kontrol yoktur. Boş çözülmüş çerçeveler atlanır; 1 baytlık çözülmüş çerçeve `header only frame received` fırlatır. İsteğe bağlı boyut sınırını (`InterfaceC40421ko.AqJ`) aşan bir stanza, kodlama sırasında `C31990DyW` fırlatır.

### 3.3 Handshake mesajları (found, alan numaraları protobuf sınıflarından)

| Mesaj (sınıf) | Alanlar (numara kalın) |
|---------------|------------------------|
| `HandshakeMessage` (`C39211ii`) | clientHello **2**, serverHello **3**, clientFinish **4** |
| `ClientHello` (`C39161id`) | ephemeral **1**, static **2**, payload **3**, useExtended **4**, extendedCiphertext **5**, paddedBytes **6**, sendServerHelloPaddedBytes **7**, simulateXxkemFs **8**, pqMode **9**, extendedEphemeral **10** |
| `ServerHello` (`C39231ik`) | ephemeral **1**, static **2**, payload **3**, extendedStatic **4**, paddingBytes **5**, extendedCiphertext **6** |
| `ClientFinish` (`C39241il`) | static **1**, payload **2**, extendedCiphertext **3**, paddedBytes **4**, simulateXxkemFs **5** |

Sürücüde görülen setter'lar: tam XX ClientHello `ephemeral` ayarlar (PQ varyantlarında + `pqMode`); resume ClientHello `ephemeral`, `static`, `payload`, `extendedCiphertext`, `extendedEphemeral`, `pqMode` ayarlar; ClientFinish `static`, `payload`, `extendedCiphertext` ayarlar. Padding ve simulate alanları tanımlıdır ancak sürücüde setter bulunamadı (kullanımı unknown).

---

## 4. Noise handshake

### 4.1 Pattern adları (found, `C38921hv` statik alanları)

| Sabit | Ad | Ne zaman kullanılır |
|-------|----|---------------------|
| `A07` | `Noise_XX_25519_AESGCM_SHA256` (32 bayta NUL ile dolgulu) | tam handshake, PQ none |
| `A0H` | `Noise_IK_25519_AESGCM_SHA256` (32'ye dolgulu) | önbellekteki sunucu static'i ile resume, PQ none |
| `A06` | `Noise_XXfallback_25519_AESGCM_SHA256` | IK sunucu tarafından reddedildi (4.4) |
| `A0E`, `A0C`, `A08` | `Noise_XXkem_`, `Noise_XXkem-FS_`, `Noise_XXkemEph_` + `25519_MLKEM512_AESGCM_SHA256` | tam, PQ açık |
| `A0F`, `A0D`, `A0G` | `Noise_IKkem+`, `Noise_IKkem-FS+`, `Noise_IKkem2+` + `X25519+MLKEM512+AESGCM256+SHA256` | resume, PQ açık |
| `A09`, `A0B`, `A0A` | `Noise_XXkemfallback_`, `Noise_XXkem-FSfallback_`, `Noise_XXkemEphfallback_` + `25519_MLKEM512_AESGCM_SHA256` | PQ fallback'leri |

32 bayttan uzun bir ad SHA-256 ile hash'lenir, aksi halde 32 baytlık dolgulu değer başlangıç hash'idir (found, `C38921hv` constructor'ı).

PQ yapılandırması (`NoisePQConfig`): mod `NONE` / `ENABLE` / `ENFORCE` (flag **20161**, int: 1 enable, 2 ila 4 enforce, aksi halde none); varyant `IKKEM`, `IKKEM_FS`, `XXKEM_EPH_IKKEM2`, `XXKEM_EPH_ONLY` (flag **34536**, string, varsayılan `IKKEM`). Tam handshake: PQ modu `NONE` `A07` kullanır; aksi halde varyant `IKKEM_FS` `A0C`, `XXKEM_EPH_ONLY` ve `XXKEM_EPH_IKKEM2` `A08`, `IKKEM` `A0E` seçer (found, `C38791hg` constructor'ında). `IKkem*` adları resume yolu ile eşleşir; kesin varyant eşlemesi izlenmedi.

### 4.2 Simetrik durum (found, `C38921hv`)

```
h  = name (padded, or SHA256(name) if > 32 bytes)         // C38941hx.A00 = name
ck = h                                                    // A02
h  = SHA256(h || prologue)                                // prologue = WA 06 03
mixHash(d):  h = SHA256(h || d)
mixKey(dh):  okm = HKDF-SHA256(salt = ck, ikm = dh, info = none, 64)
             ck  = okm[0:32] ; k = AES-256-GCM key okm[32:64] ; n = 0
encrypt(p):  c = AES-GCM(k, iv = 00000000 || n_be64, aad = h, p) ; n++ ; mixHash(c)
decrypt(c):  p = AES-GCM(k, iv = 00000000 || n_be64, aad = h, c) ; n++ ; mixHash(c)
             (no key yet: encrypt / decrypt pass through and only mixHash)
split():     okm = HKDF-SHA256(salt = ck, ikm = empty, info = none, 64)
             sendKey = okm[0:32] ; recvKey = okm[32:64]
```

HKDF elle yazılmıştır (`AbstractC38961i0`): extract = `HMAC(key = salt, data = ikm)`, expand tek baytlık sayaçla. IV: 12 bayt, ilk 4'ü sıfır, son 8'i big-endian sayaç (`AbstractC38721hZ.A02`). Tag 128 bit (BouncyCastle tarzı GCM `C39061iT`). DH, `C38851hm.A00("best")` üzerinden Curve25519 `calculateAgreement`'tır.

### 4.3 Tam XX sırası (found)

| # | Yön | İçerik | Durum işlemleri |
|---|-----|--------|-----------------|
| 1 | C to S | `ClientHello{ephemeral}` (PQ varyantlarında + `pqMode`) | `mixHash(e_c)` |
| 2 | S to C | `ServerHello{ephemeral, static, payload}` | `mixHash(e_s)`; `mixKey(DH(e_c, e_s))`; `s_s = decrypt(static)`; `mixKey(DH(e_c, s_s))`; `cert = decrypt(payload)` |
| 3 | yerel | sertifika kontrolleri (bölüm 5) | sertifikadaki anahtar `s_s`'ye eşit olmalı |
| 4 | C to S | `ClientFinish{static, payload}` | `static = encrypt(s_c)`; `mixKey(DH(s_c, e_s))`; `payload = encrypt(ClientPayload)` |
| 5 | yerel | split | `sendKey`, `recvKey`, her iki sayaç 0 |

`C38791hg.A03` (smali) içindeki sıra standart XX transkriptiyle uyuşur. Client static `s_c` ve ephemeral, `C38711hY` anahtar çiftlerinden gelir; static, `C38771he.A01` tarafından sağlanır (kalıcı client Noise anahtarı, disconnect loglarında "authKey"). Kayıtta yüklenen anahtarla aynı olduğu inferred'dır.

### 4.4 Resume (IK) ve fallback (yapı found, adım ayrıntısı inferred)

Önbellekte sunucu static anahtarları varsa (`C38771he.A00` null değil, `C38761hd`) sürücü `NoiseSocket/handshakeStart mode=... rs=...` loglar ve `handshakeResume` çalıştırır: önbellekteki sunucu static public anahtarı duruma hash'lenir (`C38921hv.A06`), ClientHello ephemeral'ı, şifrelenmiş client static'ini ve şifrelenmiş `ClientPayload`'u tek mesajda taşır (bölüm 3.3). Sunucu bir static anahtarla yanıt verirse log `handshakeResume server hello has static key, falling back` olur ve `C38791hg`, ServerHello'yu taşıyan `X.1t8` fırlatır; bu, `Noise_XXfallback_*` adlarını seçer. Kesin fallback transkripti standart Noise fallback değiştiricisinden inferred'dır. Sunucu static anahtarları, değiştiklerinde başarılı bir login sonrası saklanır (`A1m`: klasik anahtar `Ce3` ile, PQ anahtarı `Ce2` ile).

### 4.5 Post-kuantum materyali (mevcut olarak found; wire ayrıntısı kısmen unknown)

- KEM: ML-KEM-512 (algoritma string'i `MLKEM512`, `C38791hg.A0C`). Sunucu PQ public anahtarı TLV: tip `0x02`, uzunluk 800; algoritma adını taşıyan TLV başlık tipi `0x01`; FS şifreli metin TLV tipi `0x04`, uzunluk 768 (hata string'lerinden: `Expected TLV PK type 0x02`, `length 800`, `Expected TLV header type 0x01`, `Expected FS ciphertext length 768`).
- Encapsulation (`C38921hv.A07`): `KEMPublicKey.A00()` şifreli metin + paylaşılan sır üretir; şifreli metin `mixHash`'e, paylaşılan sır `mixKey`'e gider. Decapsulation: `KEMSecretKey.decapsulateNative`.
- Teslimat: `<success static_pq_key="base64">` yalnızca PQ modu `NONE` değilse ve varyant `IKKEM_FS` ise okunur (`A18`); yoksa log `handshake missing serverStaticPQ forcing full handshake` olur (`C38791hg.A01`).

TLV uzunluk alanı genişliği ve `ServerHello.payload` içindeki kesin yerleşim çözülmedi. ML-KEM native'leri Signal KEM sınıflarından gelir; bunları uygulayan kütüphane tanımlanmadı.

---

## 5. Sunucu sertifika kontrolleri (found, `C38791hg.A03`)

Protokol sürümü 6 (kullanılan tek değer), `ServerHello.payload`'u bir `CertChain` olarak ayrıştırır:

`CertChain` (`C24843Amz`): leaf **1**, intermediate **2**. Her biri bir `NoiseCertificate`'tir (`C24842Amy`): details **1** (bytes), signature **2** (bytes). `details`, zincir `Details` olarak ayrıştırılır (`C24841Amx`): serial **1**, issuerSerial **2**, key **3**, notBefore **4**, notAfter **5**.

Kontroller (log öneki `wa6:`; değerlendirme sırası tam kurtarılamadı, decompile edilmiş metot eksik):

1. Her iki `details` da zincir `Details` olarak ayrıştırılır.
2. `intermediate.issuerSerial == 0` ve `leaf.issuerSerial == intermediate.serial`.
3. `leaf.key`, handshake sunucu static'i `s_s`'ye eşittir ("noise certificate key does not match proposed server static key").
4. Intermediate imzası, `WhatsAppLongTerm1` issuer'ı için sabitlenmiş kök anahtarla `intermediate.details` üzerinde doğrulanır (`AbstractC44011qk.A00`).
5. Leaf imzası, intermediate `key` ile `leaf.details` üzerinde doğrulanır.

`notBefore` / `notAfter` zincir yolunda okunmaz. Bir hata `X.1so` fırlatır (log `socket/invalid-certificate-exception`).

Sabitlenmiş kök (public anahtar, found, `AbstractC44011qk.A01`): `142375574d0a587166aae71ebe516437c4a28b73e3695c6ce1f7f9545da8ee6b`.

Düz biçim (sabit sürüm 6'da ölü kod): `NoiseCertificate{details = 1, signature = 2}` (`C25757B9r`), düz `Details{serial = 1, issuer = 2, expires = 3, subject = 4, key = 5}` (`BC0`). Kod, tek imzayı issuer adına göre sabitlenmiş anahtara karşı doğrular, `key`'i `s_s` ile karşılaştırır ve `expires` (saniye) geçerli zamanın altındaysa reddeder (log `noise certificate expired`).

---

## 6. ClientPayload

### 6.1 Alanlar (found, `C38001fP`; numaralar descriptor'dan)

| Alan | Numara | Tip | 2.26.41.6'da kim ayarlıyor |
|------|--------|-----|----------------------------|
| username | **1** | int64 | login JID'inin sayısal user kısmı (LID login için LID user) |
| passive | **3** | bool | oturum bilgisinin bağlantı modu flag'i (7.2) |
| userAgent | **5** | `UserAgent` | 6.2 |
| webInfo | **6** | `WebInfo` | okunan katkıcılar tarafından ayarlanmıyor |
| pushName | **7** | string | hesap push name'i, boş değilse |
| sessionId | **9** | int32 | bağlantı başına oturum id'si (`C37121db`) |
| shortConnect | **10** | bool | `C11750a1.A03()` |
| connectType / connectReason | **12** / **13** | enum | 6.5 |
| shards | **14** | repeated int32 | ayarlanmıyor |
| dnsSource | **15** | message | `dnsMethod` **15**, `appCached` **16** |
| connectAttemptCount | **16** | int32 | şimdiye kadarki denemeler |
| device | **18** | int32 | companion modu: `registration_device_id` tercihi |
| devicePairingData | **19** | message | 6.3 / 6.4 |
| product | **20** | enum | LID login için `WHATSAPP_LID`, aksi halde varsayılan `WHATSAPP` |
| oc / lc | **23** / **24** | bool / int32 | `oc`: build veya imza kontrolü sonucu (`AbstractC38241gg`, ad açılmadı); `lc`: `connection_lc` tercihi |
| pull | **33** | bool | **bu build'de hiç ayarlanmıyor** (yazıcı bulunamadı) |
| yearClass / memClass | **36** / **37** | int32 | cihaz sınıfı sezgileri (`C38261gi`, `C38271gj`) |
| trafficAnonymization | **40** | enum | `C17830kT.A0L()` ise `STANDARD`, değilse `OFF` |
| lidDbMigrated | **41** | bool | yalnızca user JID varken ve companion değilken |
| connectionSequenceInfo | **43** | int32 | sıra adımından türetilen 0-31 sayacı |
| paaLink | **44** | bool | `C0NZ.A02()` |
| preacksCount / processingQueueSize | **45** / **46** | int32 | kuyruk durumu (flag'ler **20485** / **22413**) |
| pairedPeripherals | **47** | repeated string | `smart_glasses`, `garmin` |
| messageSts | **49** | int64 | biliniyorsa son mesaj zaman damgası |

Tanımlı ancak burada ayarlanmayanlar: fbCat **21**, fbUserAgent **22**, iosAppExtension **30**, fbAppId **31**, fbDeviceId **32**, paddingBytes **34**, interopData **38** (`accountId` **1**, `token` **2**, `enableReadReceipts` **3**), accountType **42**, testIsolationId **48**.

### 6.2 UserAgent (found, `C38051fp`)

| Alan | Numara | Bu build'deki değer |
|------|--------|---------------------|
| platform | **1** | `ANDROID` (0), sabit |
| appVersion | **2** | `2.26.41.6`'dan ayrıştırılan `{primary 1, secondary 2, tertiary 3, quaternary 4}` |
| mcc / mnc | **3** / **4** | `getNetworkOperator()`, varsayılan `000` |
| osVersion / manufacturer / device / osBuildNumber | **5** / **6** / **7** / **8** | sistem string'leri |
| phoneId | **9** | cihaz düzeyi id (`C38141gV`) |
| releaseChannel | **10** | bu beta build'de `BETA` (1); `RELEASE 0, BETA 1, ALPHA 2, DEBUG 3` |
| localeLanguageIso6391 / localeCountryIso31661Alpha2 | **11** / **12** | `zz` / `ZZ` için atlanır |
| deviceBoard / deviceExpId | **13** / **14** | boş değilse board string'i; deney id'si |
| deviceType | **15** | cihaz sınıfından `PHONE`, `TABLET`, `DESKTOP`, `VR` |
| deviceModelType | **16** | |
| distributionChannel | **17** | ayarlanmıyor |

`UserAgent.Platform` (`EnumC38071fr`, 0-40): 0 ANDROID, 1 IOS, 10 SMB_ANDROID, 12 SMB_IOS, 13 WINDOWS, 14 WEB, 24 MACOS, 29 WEAROS, 33 IPAD, 35 SMART_GLASSES, 39 WORK_ANDROID, 40 WORK_IOS (diğerleri atlandı).

### 6.3 DevicePairingRegistrationData (found, `C38661hS`)

`DevicePairingRegistrationData` alanları: eRegid **1** (4 baytlık registration id), eKeytype **2** (`05`), eIdent **3** (identity public anahtarı), eSkeyId **4**, eSkeyVal **5**, eSkeySig **6** (signed prekey id'si, public, imza), buildHash **7**, deviceProps **8** (serileştirilmiş `DeviceProps`).

`buildHash`: kod `Base64.decode(hexMD5("2.26.41.6"), 0)` hesaplar (`C00L.A04`, 32 karakterlik küçük harfli hex MD5 döndürür; bu da base64 decoder'a verilir), 16 baytlık digest değil, 24 bayt ortaya çıkar (found, okunduğu şekliyle).

`DeviceProps` (`C43105IrG`): os **1** (OS string'i), version **2** (`AppVersion`), platformType **3**, requireFullSync **4** (= true), historySyncConfig **5**. History-sync bloğu, `CompanionRegInfoProvider` olarak loglayan bir sınıf tarafından oluşturulur; alanları (tam senkron günleri / boyut sınırları, yakın zamanlı senkron, küçük resim senkronu, çağrı kayıtları, bot geçmişi, grup geçmişi gibi destek flag'leri) flag'ler **15284**, **15283**, **21217**, **20658**, **18953**, **26445**, **26614** tarafından yönetilir.

### 6.4 Hangi varyant gönderilir (found)

- Login, birincil (user JID biliniyor): username, passive, userAgent, pushName, sessionId, shortConnect, connectType, connectReason, dnsSource, connectAttemptCount, connectionSequenceInfo, lc, oc, yearClass, memClass, trafficAnonymization, lidDbMigrated, messageSts, kuyruk sayaçları, paaLink, pairedPeripherals; LID login'lerde `product = WHATSAPP_LID`.
- Login, companion: aynısı artı `device = registration_device_id`.
- Companion kaydı (user JID null): username yok; `devicePairingData` (anahtar paketi + `DeviceProps`) ve `device`.

`ConnectionThread/connect/ignored/jid null and not in companion reg`, null bir JID'in companion kaydı dışında reddedildiğini gösterir. Birincil telefon HTTPS `/v2/*` üzerinden kayıt olur (bkz. account-security raporu); `devicePairingData`'nın birincil kayıtta kullanımı bulunamadı.

### 6.5 Kullanılan enum'lar (found)

| Enum | Değerler |
|------|----------|
| `ConnectReason` (`EnumC38391gv`) | 0 PUSH, 1 USER_ACTIVATED, 2 SCHEDULED, 3 ERROR_RECONNECT, 4 NETWORK_SWITCH, 5 PING_RECONNECT, 6 UNKNOWN |
| `ConnectType` (`EnumC38311gn`) | 0 CELLULAR_UNKNOWN, 1 WIFI_UNKNOWN, 100 EDGE, 101 IDEN, 112 HSPAP; diğer hücresel adlar (UMTS, EVDO, GPRS, HSDPA, HSUPA, HSPA, CDMA, ...) numaralarını çözümlenmemiş dolaylı sabitlerden alır |
| `Product` (`EnumC38561hI`) | 0 WHATSAPP, 1 MESSENGER, 2 INTEROP, 3 INTEROP_MSGR, 4 WHATSAPP_LID |
| `DNSResolutionMethod` (`EnumC38321go`) | 0 SYSTEM, 1 GOOGLE, 2 HARDCODED, 3 OVERRIDE, 4 FALLBACK, 5 MNS, 6 MNS_SECONDARY, 7 SOCKS_PROXY |

Bu build'de yazıldığı şekliyle connect reason: varsayılan `UNKNOWN`; oturum bilgisi zaman damgası 10 sn içindeyse durum 1 `USER_ACTIVATED`, durum 2 `PUSH` verir. Diğer değerler tanımlıdır ancak bu katkıcı onları seçmez.

---

## 7. Handshake sonrası

### 7.1 Login sonucu (found, `HandlerThreadC12340b0.A13`)

İlk gelen node'lar bir döngüde okunur. `web` yalnızca bir web ref gönderildiyse kabul edilir (aksi halde `web node given during login without any web ref provided`). `web`, `success`, `failure` dışındaki her şey `unexpected node received during login sequence` fırlatır.

`<success>` içinde okunan attribute'lar:

Okunan attribute'lar: `t` (saniye cinsinden sunucu zamanı, saklanır; sayısal olmayan `invalid server time` fırlatır), `props`, `abprops`, `mc_ep_version` (yapılandırma sürüm sayaçları), `lid` (hesap LID'i, saklanan LID ile karşılaştırılır; uyuşmazlık `lid-chatd-lid-mismatch` bildirir), `pn` (telefon user JID'i), `static_pq_key` (base64 sunucu PQ anahtarı, 4.5).

### 7.2 Passive ve active mod (found)

Payload'daki `passive`, oturum bilgisinden gelir (`C37981fJ.A0A`); log alanları `forcePassiveMode`, `enablePassiveModeBasedOnQueueSize`, `duplexActive`. Login sonrası client, `AbstractC44071qq` ile oluşturulan bir set IQ'su ile passive moddan çıkar:

```xml
<iq id="..." xmlns="passive" type="set" to="s.whatsapp.net"><active/></iq>   <!-- or <passive/> -->
```

Kuyrukta varsa önce pre-ack'ler gönderilir (`ConnectionThread/send preacks`). 32000 ms'lik bir zamanlayıcı (`HandlerC21850s9.A02`) gönderimde kurulur; bağlantı-etkin sinyali gelmezse neden 10 ile tetiklenir (`connection active timeout`).

### 7.3 Bilgi bültenleri (found, `C40581l4`)

İşlenen `<ib>` çocukları: `edge_routing` (çocuk `routing_info`, saklanır, bölüm 3.1), `fbip` (yedek yöneticisine virgülle ayrılmış IP'ler), `client_expiration` (`t`, saniye, ms'ye çevrilir), `dirty`, `offline_preview`, `location`, `notice`, `recovery_nonce`, `safetynet`, `sonar` (`url`), `streamdebug`, `thread_metadata`, `gpia`, `age_experience`, `accept_paa_link`, `peer_device_presence`. `dns_domain` yok (Android client'ında bulunmuyor).

---

## 8. Binary node kodlaması

### 8.1 Çerçeve içeriği ve flag'ler (found, `C40411kn.Csv`, `C24610wf.Be0`)

AES-GCM çözmeden sonra düz metin tek bir flags baytıyla başlar:

| Bit | Anlam |
|-----|-------|
| `2` | geri kalan bir zlib (DEFLATE) akışıdır; decoder açar ve flags baytını tutar |
| `1` | parçalama; decoder `server to client stanza fragmentation not supported` fırlatır |

Encoder: `Csv(node, flags)`, `flags & 2` ile deflate eder (`DeflaterOutputStream`) ve `02` öneki ekler; aksi halde `00` flags baytı yazar. `HandlerThreadC12340b0` içindeki ana gönderim yolları ve yazıcı thread `HandlerThreadC21920sG`, `Csv(node, 3)` çağırır, dolayısıyla bu stanza'lar sıkıştırılır. `Csu(node)` (= flags 1, sıkıştırılmamış), login aşaması göndericisine benzeyen `C40851lV` tarafından çağrılır (inferred). Akış sonu işaretçisi `00` + list(1) + token `02`'dir (`Clp`, `xmlstreamend`).

### 8.2 Tag baytları (found)

| Bayt | Ad | Gövde |
|------|----|-------|
| 0 | boş liste / yok | yok |
| 1, 2 | `xmlstreamstart`, `xmlstreamend` | decoder bunları string olarak reddeder |
| 3..235 | tek baytlık token | 236 girişli `A00` tablosuna indeks |
| 236..239 | sözlük 0..3 | `A01[tag - 236]` içine 1 indeks baytı (her biri 256 giriş) |
| 244 / 247 | JID_INTEROP / AD_JID | `user:str, device:u16, integrator:u16, domain:u8` / `domain:u8, device:u8, user:str` |
| 248 / 249 | LIST_8 / LIST_16 | `count:u8` / `count:u16` |
| 250 | JID_PAIR | `user:str or 00, server:str` |
| 251 / 255 | HEX_8 / NIBBLE_8 | `lenAndOdd:u8` + paketlenmiş nibble'lar |
| 252 / 253 / 254 | BINARY_8 / _20 / _32 | `len:u8` / `len:u20` (3 bayt) / `len:u32`, ardından baytlar |

245 ve 246 tag'leri bu codec'te yoktur. Tüm çok baytlı tamsayılar big-endian'dır.

### 8.3 Node yapısı (found, `C40411kn.A01`)

```
list(size)  description  (key value)*  [content]
size = 1 + 2 * attrCount + (content ? 1 : 0)
```

Tek sayılı size, içerik olmadığı anlamına gelir. Decoder: attribute sayısı = `((size - 2) + size % 2) / 2`. İçerik ya bir bayt blob'udur (`252 / 253 / 254`) ya da bir çocuk listesidir. Hem blob hem çocukları olan bir node `more than one source of inner data` fırlatır. Liste başlığı: boş için 0, 256 girişin altında 248, 65536'nın altında 249, aksi halde `list too long`.

### 8.4 String merdiveni (found, `C40411kn.A05` / `A06`)

| Yuva | Denenme sırası |
|------|----------------|
| description | token, sözlük, JID (ayrıştırılabiliyorsa), uzunluk önekli UTF-8 |
| attribute key | token, sözlük, UTF-8 |
| attribute value | token, sözlük, JID, paketlenmiş, UTF-8 |
| içerik baytları | ham BINARY (`A06(bytes, false)`), asla token'laştırılmaz veya paketlenmez |

Paketleme (packed flag'li `A06`, yalnızca attribute value'lar): uzunluk 128'in altında ve tüm karakterler `[0-9-.]` içindeyse NIBBLE_8 (`255`; `0-9` = 0..9, `-` = 10, `.` = 11); uzunluk 128'in altında ve tüm karakterler `[0-9A-F]` içindeyse HEX_8 (`251`); tek uzunluk biti uzunluk baytında `0x80`'dir. 256 ve üzeri uzunluklar 1 MiB'a kadar BINARY_20, ötesinde BINARY_32 kullanır. Decoder nibble eşlemesi: 10 `-`, 11 `.`, 12 `:` (encoder 12'yi hiç üretmez).

### 8.5 JID'ler (found, `C40411kn.A00`, `C24610wf.A02`)

| JID | Kodlama |
|-----|---------|
| interop user (`C99O`, tip 22) | `244, user, device u16, integrator u16, 00`; `{integrator}-{user}[:device]@interop` olarak çözülür |
| interop group (`C55529Oy6`, tip 28, server `interop.g.us`) | `244, user, 0000, 0000, 02`; decoder device ve integrator'ın 0 olmasını ister |
| agent veya device mevcut | `247, domainByte, device, user`; domainByte biti `1` = LID, bit `128` = hosted |
| diğer durumlar | `250, user (or 00), server` |

AD_JID server eşlemesi: `0` `s.whatsapp.net`, `1` `lid`, `128` `hosted`, `129` `hosted.lid`. Device `99`, hosted biti set edildiğinde tam olarak beklenir; uyuşmazlık loglanır ve JID yine de kabul edilir. Uyumsuz JID'ler `failed to write jid` fırlatır.

### 8.6 Sözlük (found, `AbstractC40911lb`)

236 tek baytlık token (indeks 0 null) ve dört adet 256 girişli sözlük; sözlük sürümü son intro baytıdır, `03`. Bu build'de yeniden çözümlenen indeksler:

| Token | İndeks | Token | İndeks |
|-------|--------|-------|--------|
| `s.whatsapp.net` | 3 | `iq` / `ack` / `message` | 25 / 27 / 19 |
| `type`, `id`, `from`, `to` | 4, 8, 6, 17 | `get` / `set` / `result` / `error` | 41 / 90 / 20 / 168 |
| `routing_info` / `edge_routing` | 39 / 40 | `urn:xmpp:ping` / `ping` / `w:p` | 43 / 86 / 87 |
| `handshake` / `success` | 53 / 76 | `stream:error` / `not-authorized` | 157 / 209 |
| dict 0: `active` / `conflict` / `replaced` / `passive` | 1 / 14 / 17 / 24 | dict 1: `dirty` / `server-error` / `pair-device` | 1 / 145 / 238 |
| dict 2: `failure` / `rate-overlimit` | 60 / 239 | `call` / `usync` / `w:m` | 100 / 121 / 194 |

Tablodaki birkaç token, başka sınıflardan içe aktarılan Java sabitleridir (örneğin `enc`); bu indeks listesiyle çözümlenmediler. İndeksler build'ler arasında değişir; sürümler arasında yeniden kullanmayın.

---

## 9. Keepalive ve zamanlayıcılar

| Zamanlayıcı | Değer | Kademe |
|-------------|-------|--------|
| Client ping | `<iq type="get" xmlns="w:p" to="s.whatsapp.net"/>` (`C9EN`); yanıt `from`, `id`, `t` (1577865600..4102473600 aralığında) ve `type="result"` taşımalıdır (`C14U`) | found |
| Ping zaman aşımı | `clamp(flag 15103, 8000, 32000)` ms; zaman aşımında ping başına bir kez `C14R.CY1()` çalışır (yeniden bağlanma tepkisi inferred) | found / inferred |
| Ping aralığı | flag **15270** (ilk), **15183** (sonrakiler); gecikmeli runnable veya alarm `com.whatsapp.alarm.CLIENT_PING_TIMEOUT`, flag **6493** ile seçilir | found, değerler sunucu tarafında |
| Sunucu ping'i | `<iq type="get" xmlns="urn:xmpp:ping" t="...">` (`AbstractC40501kw`) | found |
| Active-mode ack | 32000 ms, ardından disconnect reason 10 | found |
| Mesaj receipt'i | gönderimden 45000 ms sonra hâlâ onaylanmamışsa: reconnect reason 9 (`HandlerC21850s9`) | found |
| Logout zaman aşımı / soket zaman aşımı | 10000 ms / 30000 ms | found |

---

## 10. Yeniden bağlanma ve backoff (found, `C11380Yq.A07`, `C0X9`)

`C11380Yq`, `AlarmManager` üzerinden bir yeniden bağlanma zamanlar (`com.whatsapp.MessageHandler.RECONNECT_ACTION`, `connect_reason` extra'sı 3). Gecikme birimi 10 sn'dir (smali'de 0x2710 ms).

| Adım | Kural |
|------|-------|
| Sayaç | `C0X9(1, 17280)`: birim cinsinden Fibonacci, dizi 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ... 17280 birimle (48 sa) sınırlı |
| İlk yeniden deneme | 0 birim: `scheduleReconnect/immediate` |
| Jitter | `d = units * 10 s`; gecikme `[d / 2, 1.5 d)` aralığında düzgün dağılımlı |
| Clamp | çağıran flag'i set edilmişse, 15 dk'yı aşan gecikmeler 15 dk artı `-30 .. +29` ms aralığında rastgele bir ofset olur (`backoff clamped to ~15mins`) |
| Sıfırlama | `A02()`, bir `reset` yeniden bağlanma isteğinde sayacı sıfırlar |
| Override'lar | `force` bekleyen son tarihi temizler; `force_no_ongoing_backoff` beklemeyi atlar; `reset` sayacı sıfırlar |
| Ağ yok | `handleDisconnected/retry/network_unavailable` bağlantıyı bekler (alarm `CONNECTIVITY_RETRY_ACTION`) |

Tek bir deneme içinde bölüm 2.2'deki bağlantı sırası host'ları ve port'ları dolaşır; backoff, tüm bağlantının başarısız denemeleri arasında uygulanır.

---

## 11. Stream hataları ve hata kodları

### 11.1 Login'de `<failure reason="N">` (found, `A13`)

| Reason | İşleme | Okunan ek attribute'lar |
|--------|--------|-------------------------|
| 5xx | yeniden denenebilir sunucu hatası, `C45351tB(type 4)` | yok |
| 402 | ban ailesi; tip 13 (`appeal_token` ile kod 106), 14 (kod 107), 15 (kod 109), aksi halde 2 | `appeal_token`, `code`, `expire`, `message`, `url`, `age_collection` |
| 403 | tip 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` |
| 405 | tip 3, `expiration_time = t * 1000` | `t` |
| 406 | tip 5 | `code` |
| 416 | tip 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` |
| diğer | tip 0 (genel logout yolu) | yok |

Her failure ayrıca isteğe bağlı logout UI alanlarını okur: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text` / `_url`, `logout_secondary_button_text` / `_url` (`A17`). Tip int'lerinin kullanıcıya dönük ekranlarla eşlemesi izlenmedi; hesap-ban semantiği ban raporunda ele alınmıştır.

### 11.2 `<stream:error code="N">` (found, `C40601l6`, `C37961fH.A1B`)

| Durum | İşleme |
|-------|--------|
| Herhangi bir `stream:error` | `ConnectionThreadRequestsImpl/stream/error` ilk çocukla loglanır; `errorCode` içeren bir mesaj `MessageHandler`'a gönderilir |
| Kod 500-599 | `MessageHandler` bir flag ayarlar ve bir yeniden bağlanma geçişi çalıştırır (`onConnectionStreamError`) |
| Çocuk `ack` | ack-kick olarak ele alınır: o id'ye sahip bekleyen stanza aranır, metrikler yayılır, bağlantı durur (`1t7` fırlatılır) |
| Çocuk `conflict type="device_removed"` | yalnızca companion: kaydı sil (`C24100vp.A02`), durum 9 değilse |
| 515 / 516 (companion yolu) | tipli mesajlar olarak iletilir; 515 için decompile edilmiş dal belirsiz |
| `<error code="479">` | `smax-invalid` bildirilir (`SmaxInvalidError`) |
| `<error class="status" id=...>` | bekleyen status ack callback'ini başarısız kılar |

### 11.3 Handshake ve soket hataları (log etiketleri olarak found, tepkiler kısmen izlendi)

| Log etiketi | Neden |
|-------------|-------|
| `socket/goaway` (`X.1sn`) | ServerHello uzunluk baytları `GOA`'ya eşit |
| `socket/invalid-certificate-exception` (`X.1so`) | sertifika zinciri kontrolü başarısız (5); `C37031dS.A0C` çağırır |
| `socket/disconnect/invalid-server-static-key` (`X.1sp`), `.../authKey` (`X.1sm`) | sunucu static'i reddedildi; client static anahtar sorunu |
| `socket/disconnect/noise` (`X.1sr`) | protokol istisnası (hatalı handshake verisi, TLV boyutları); AEAD hatası `X.1t9` ve KEM girdi hatası `X.1tC` bu aileye yeniden fırlatılır |
| `socket/disconnect/io`, `socket/closed`, `socket/error/EPERM` | I/O hataları, engellenmiş ağ |
| `connect/not-allowed/clock`, `software-expired`, `login-failed`, `quit-flag-set` | bağlanma öncesi kapılar |
| `ReaderThread/corrupt-stream-error` | hatalı node akışı; `next-port/corrupt-stream-exception` port'u ilerletir |

---

## 12. Feature flag'leri (id'ler `AbstractC36791d3` ve çağrı noktalarında okunduğu şekliyle)

| Id | Tip | Neyi kontrol eder |
|----|-----|-------------------|
| **20161**, **34536** | int, string | PQ modu (1 enable, 2-4 enforce), PQ varyantı (varsayılan `IKKEM`) |
| **38643**, **15716** | string, bool | KEM seçimi (`MLKEM768` tanınıyor), buna kapı; etki çözümlenmedi |
| **33751** | bool | intro + ClientHello için tamponlu yazıcı |
| **22916**, **30712**, **33512** | bool | HISTORY adımını devre dışı bırak; son başarı kaydını yükle; saklanan port'u yeniden kullan |
| **20801**, **23630**, **24645** | bool | adım 5 sabit 443; SOCKS yapılandırması altında adım 2-4; SOCKS servis yapılandırması kaynağı |
| **13545** | string | DNS çözümleyici modu (`secondary` / `hardcoded` / `none`) |
| **7831**-**7834** | bool, int'ler | TCP keepalive etkinleştirme ve parametreleri |
| **15103**, **15270**, **15183**, **6493** | int, bool | ping zaman aşımı, aralıklar, zamanlama yöntemi |
| **20485**, **22413** | bool | payload içindeki kuyruk durumu |

Tüm değerler sunucu tarafındadır; varsayılanlar flag bildirimlerindeki derlenmiş değerlerdir.

---

## 13. Diğer taşımalar

| Taşıma | 2.26.41.6'daki durum | Kademe |
|--------|----------------------|--------|
| Tigon HTTP client | `com/crossapp/tigonhttp/TigonHttpClient*`, `com/facebook/tigon/**`, `com/whatsapp/infra/tigon/WAHucClient`, kimlik doğrulama `WATigonAsyncAuthServiceHolder` üzerinden; `libwhatsappmerged.so` içinde HTTP/2 ve HTTP/3 string'leri (`MNS/mvfst-mobile`, `MNS/ngtcp2`) | sınıflar ve string'ler found; özellik başına kullanım inferred |
| DistribGW (DGW) | `com/facebook/distribgw/client/*`, `RequestStreamDGWBuilder`; yalnızca uygulama tarafı kaydı bulundu: `WaFalcoStreamingRegistration.nativeRegisterStreaming(DGWClient)`; string'ler `distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, `XPLAT_RS_MQTT`, `XPLAT_RS_STARGATE`, `wa_request_stream` | found; wire formatı unknown |
| MQTT client | yok; `mqtt` yalnızca analitik olay adlarında ve DGW stream-tipi etiketlerinde geçer | found |
| chatd üzerinden GraphQL | `com.whatsapp.pando.chatd.WAChatdGraphQLClient`, `WAChatdGraphQLCallbacks`, `WATigonMexdServiceHolder` | adlar found; inferred bir w:mex yolu olarak chatd üzerinden gider |

### 13.1 Tigon Noise kanalı (ikinci Noise yığını, native)

Bu, chatd'den farklı bir taşımadır. Kanıt, decompile edilmiş mantık değil, string'ler ve sınıf adlarıdır.

- Taşıyıcı: MNS ağ yığını üzerinden WebSocket (`NoiseCarrierWebSocket`, `Stream0Listener`); kontrol stream'i 0 olan numaralı stream'ler ve chunk yeniden birleştirme (`noise.framer.*`).
- Handshake sonuçları (`NoiseHandshakeOutcome`): `LEGACY_PEER_VERIFIED`, `PRIVATE_AUTH_PEER_VERIFIED`, `ENROLLMENT_REQUIRED`, `KEY_REQUIRED`, `VERIFICATION_FAILED`; `NoisePrivateAuthMode`: `MIGRATION`, `REQUIRED`; `noise.handshake.attestation_failed`, `chip_binding_rejected`, `private_auth.vm_proof_failed` gibi hatalar.
- Attestation: AMD SEV-SNP doğrulayıcısı (`NoiseSevSnpAttestationVerifier`, VCEK / ASK / ARK zincir kontrolleri, chip id bağlama); etiketler `hatch.noise-auth.key.v1`, `.client-proof.v1`, `.vm-proof.v1`.
- Talep kontrolü: `NoiseConnectionDemandRejectionReason` `OFFLINE`, `BACKGROUND`, `PAUSED`, `SESSION_ENDED`, `RETRY_EXHAUSTED`, `INTERNAL`.
- Java kullanıcıları: `WaVmHttpTransportImpl`, `NoiseVmConnection` (yol `/v1/noise`, adımlar `hatch-noise status=opening` / `result=ready`), `NoiseGatewayCarrier`. Amaç (agent tarayıcısı için gizli hesaplama VM'ine HTTP-over-Noise) adlardan ve attestation string'lerinden inferred'dır.

Buradaki hiçbir şey chatd handshake'i ile bölüm 4'te kod paylaşmaz; aynı pattern adı, aynı çerçeveleme, prologue veya payload anlamına gelmez.

---

## 14. Baileys (`baron-baileys-v2`, kaynağına karşı doğrulandı)

| Yön | Baileys | Android 2.26.41.6 |
|-----|---------|-------------------|
| Intro başlığı | `NOISE_WA_HEADER = [87, 65, 6, 3]` | `57 41 06 03` |
| Pattern | `NOISE_MODE = 'Noise_XX_25519_AESGCM_SHA256\0\0\0\0'` | aynı 32 baytlık dolgulu ad |
| Sunucu sertifikası | `CertChain` decode; leaf imzası intermediate anahtarıyla kontrol edilir; intermediate, sabitlenmiş kök `142375574d0a...da8ee6b` ile kontrol edilir; `issuerSerial` 0 olmalı | aynı zincir ve aynı kök baytları; APK ek olarak `leaf.issuerSerial == intermediate.serial` ister |
| Edge routing | `<ib><edge_routing>` içinden `routing_info` saklar; `wss://web.whatsapp.com/ws/chat` adresine `ED=<base64url>` sorgusu olarak ekler | saklar (en fazla 256 bayt); intro'dan önce ham olarak `45 44 00 01 len24 blob` gönderir |
| Keepalive | çocuksuz `<iq type="get" xmlns="w:p"/>`, varsayılan aralık 30000 ms, bağlantı zaman aşımı 20000 ms | aynı IQ; aralık ve zaman aşımı sunucu flag'lerinden |
| Login payload | `passive`, `pull` true, `username`, `device`, `connectType WIFI_UNKNOWN`, `connectReason USER_ACTIVATED`, `lidDbMigrated false`, `releaseChannel RELEASE` | `pull` yok, `connectReason` oturum durumundan, bu build'de `releaseChannel BETA` |
| Kayıt payload'ı | `passive false`, `pull false`, `devicePairingData` | `devicePairingData` yalnızca companion kayıt bağlantısı için |
| Taşıma | WebSocket çerçeveleri | ham TCP, 3 baytlık uzunluklu çerçeveler |

Android tarzı bir taşıma için önemli olan doğrulanmış farklar: edge ipucu Baileys'te WebSocket URL'sinde bir sorgu parametresidir, Android'de ise intro'dan önce ham bir başlıktır; Baileys `leaf.issuerSerial == intermediate.serial` koşulunu zorunlu kılmaz; Baileys login'de `pull` ve `passive`'i true gönderir, Android payload'ında ise `pull` yoktur. Baileys hızlı yeniden bağlanma için sunucu static anahtarını tutar (bir kod yorumu `NoiseIkSession` adını verir); bu, yalnızca amaç bakımından bölüm 4.4'teki IK resume ile eşleşir; wire biçimi karşılaştırılmadı.

---

## 15. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| İlk üç baytta `GOA` | handshake sırasında sunucu goaway'i | sonraki endpoint'i dene |
| `Handshake message does not contain server hello!` | ilk sunucu çerçevesi ServerHello değil | prologue'u ve edge başlığını kontrol et |
| `noise certificate key does not match proposed server static key` | leaf anahtarı handshake static'inden farklı | ClientFinish'ten önce zinciri doğrula |
| `server to client stanza fragmentation not supported` | flags biti `1` set | client tarafından desteklenmiyor |
| `unexpected node received during login sequence` | ilk node `web`, `success`, `failure` değil | yok |
| `noise-pq-static-key-decode-failed` | `static_pq_key` geçerli base64 değil | anahtar saklanmaz, bir kez bildirilir |
| `scheduleReconnect backoff=...` | tekrarlayan hatalar | backoff'un bitmesini bekle veya yeniden bağlanmayı zorla |

---

## 16. Temel ayrımlar

| Karıştırılmaması gerekenler | Ayrıntı |
|-----------------------------|---------|
| chatd Noise ve Tigon Noise kanalı | Java ve native, TCP ve WebSocket taşıyıcı, farklı amaç; aynı pattern adı çerçeveleme veya payload hakkında hiçbir şey ifade etmez |
| Intro başlığı ve edge başlığı | `WA 06 03` prologue olarak hash'lenir; `ED 00 01 len blob` transkriptin parçası değildir |
| Edge host `eN.whatsapp.net` ve `routing_info` | host'lar client sırasından gelir; `routing_info`, edge başlığında tekrar oynatılan opak bir blob'dur |
| `fallback_hostname` / `fallback_ip4` / `fallback_ip6` | `media_conn` host'larının (CDN) attribute'ları, chatd yedekleri değil; chatd yedekleri `<ib><fbip>`'ten ve sabit kodlu tablodan gelir |
| `passive` payload flag'i ve `<passive/>` IQ | flag bağlanırken ayarlanır; IQ sonrasında active moda geçirir |
| `devicePairingData` ve HTTP kaydı | pairing verisi companion kayıt bağlantısına aittir |
| Çerçeve uzunluğu ve liste size'ı | 3 baytlık uzunluk şifreli metni sarar; liste size'ı node yuvalarını sayar |
| Protokol ve sözlük sürümü | ikisi de intro'da: `06` ve `03` |
| `stream:error` ve `failure` | `failure` login'e yanıt verir; `stream:error` her an gelebilir |

---

## 17. Tam akış

```
[Connection thread]  C37031dS.A0G picks step (history, g, g-fallback, hard-coded, eN, proxy)
     │  DNS ─► TCP connect ─► optional TLS wrapper
     ▼
[Client]  write [ED 00 01 len24 routing_info]?  [WA 06 03]        h = SHA256(name) ; h = SHA256(h || WA 06 03)
     │  frame1: HandshakeMessage{clientHello{ephemeral}}           mixHash(e_c)    (resume: + static + payload)
     ▼
[Server]  frame2: serverHello{ephemeral, static, payload}
     │  mixHash(e_s) ; mixKey(ee) ; s_s = decrypt(static) ; mixKey(es) ; cert = decrypt(payload)
     │  CertChain: leaf.key == s_s ; intermediate by pinned root ; leaf by intermediate
     ▼
[Client]  frame3: clientFinish{static = enc(s_c), payload = enc(ClientPayload)}      mixKey(se) ; split
     ▼
[Server]  [len24 | AES-GCM(flags | node)] ─► <success t props abprops lid pn static_pq_key/>  or  <failure reason/>
     ▼
[Client]  <iq xmlns="passive" type="set"><active/></iq> (+ pre-acks) ; steady state both ways, own counter per direction
     │  ping <iq xmlns="w:p"/> ; ib / notification / message / receipt / call ...
     ▼
[Failure]  stream:error / ping timeout / socket error ─► disconnect ─► Fibonacci backoff ─► next attempt
```

---

## 18. Bilinmeyenler

| Öğe | Durum |
|-----|-------|
| Herhangi bir türde wire trafiği | hiçbir şey yakalanmadı; hiçbir öğe `tested` değil |
| IK resume ve fallback transkripti | yapı found, adımlar inferred |
| `ServerHello.payload` içindeki PQ anahtarı yerleşimi, TLV uzunluk genişliği, ML-KEM çağrılarının arkasındaki kütüphane | çözülmedi / tanımlanmadı |
| TLS ile sarılmış endpoint'lerin TLS içinde ne taşıdığı | kod yolundan inferred |
| Ping ve TCP-keepalive değerleri | sunucu flag'leri |
| Failure tip int'leri 0-15'in client ekranlarına eşlenmesi; flag'ler **38643**, **15716** etkisi | izlenmedi / çözümlenmedi |
| Yazıcısı olmayan payload alanları (`webInfo`, `shards`, `fb*`, `accountType`, `testIsolationId`, `paddingBytes`, `pull`) | bu build'de hiçbiri bulunamadı |
| Tigon Noise kanalı handshake'i, çerçevelemesi; DGW wire protokolü ve kullanıcıları | native, yalnızca string'ler |
| İçe aktarılan Java sabiti olan sözlük string'leri (örneğin `enc`) | indeks listesinde çözümlenmedi |
