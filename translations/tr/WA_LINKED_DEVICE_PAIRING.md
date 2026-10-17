<!-- src-sha1: 2c3f9604f03ccc7f3d3160d18810a86e62b8172f -->
# WhatsApp Bağlı Cihaz Eşleştirme — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** companion eşleştirmenin primary-cihaz tarafı, QR akışı, telefon numarası / eşleştirme kodu akışı, `pair-device` ve `pair-success` stanza'ları, anahtar materyali, ADV imzalı cihaz kimliği ve key-index listesi, cihaz listesi ve limitler, bağlantıyı kaldırma, hatalar, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

Bağlı cihaz (companion), aynı hesabın ikinci bir uç noktasıdır. Primary telefon, companion'ın identity key'i üzerinde bir ADV (account device verification) imzalı kimliği üreterek onu yetkilendirir. Tüm ifadeler çözülmüş (decompile edilmiş) APK'nın statik analizine dayanır; wire üzerinde hiçbir şey yakalanmadı. Kademe: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi.

Obfuscate edilmiş adlar derlemeye özgüdür ve 2.26.41.6'da kararlı string'lerden yeniden çözüldü.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| QR/eşleştirme orkestratörü | `C45850K0w` (log öneki `CompanionDeviceQrHandler`) | QR'ı ayrıştırır, ADV proto'larını oluşturur, `pair-device` gönderir |
| `pair-device` IQ oluşturucu | `RunnableC46606KYf` | IQ'yu oluşturur |
| `pair-device` istek/yanıt yardımcısı | `KRI` (`devicePairRequest/*`) | gönderir, yeniden dener, `device` / `companion-props` / retry ipuçlarını ayrıştırır |
| Hata yönlendirici | `C44661Jem` | sunucu hata kodunu UI callback'ine eşler |
| QR string ayrıştırıcı | `C45741Jxy` → `C45423Jrn` | QR payload'ından eşleştirme verisine |
| Ayrıştırılmış eşleştirme verisi | `C44423JaU` | ref, companion anahtarları, adv secret, platform |
| ADV util | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, key index, timestamp, key-index-list oluşturma ve imzalama |
| Key-index-list güncelleyici | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | imzalı listeyi sunucuya iter |
| ADV doğrulayıcı | `C24230w2` (`DeviceADVInfoHandler`) | wire üzerinde görülen kimlikleri ve listeleri doğrular |
| Cihaz listesi bildirim işleyicisi | `C1S0` içindeki anonim sınıf (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | `devices` bildirimi |
| Link-code bildirim işleyicisi | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | bildirim id 252 |
| Link-code yöneticisi (primary) | `KZ3` (kod girişi, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | eşleştirme kodu akışı |
| Link-code crypto util | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Cihaz yöneticisi | `C0XQ` (`companion-device-manager`) | liste, logout |
| Kaldırma yardımcısı | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Signal curve sarmalayıcısı | `C38851hm` | `org.whispersystems.curve25519` provider "best" |
| ADV proto sınıfları | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | bkz. bölüm 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `pair-device` sonucundaki `companion-props` |
| Client props | `C43107IrI` | `client-props` alt düğümü |
| Hesap/şifreleme türü | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

Primary UI'da üç giriş modu vardır (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

Aynı APK, companion-rolü kayıt kodunu da içerir (durum makinesi `C0YS`, `companion/registration/*` logları). Bu kapsam dışıdır; yalnızca primary'nin ne aldığını açıklamak için gereken kısımlar anlatılmıştır (bölüm 9.6).

---

## 2. Eşleştirme yollarına genel bakış

| Yol | Primary'de tetikleyici | Primary'nin gönderdiği | Primary ile companion'ı bağlayan sır |
|------|--------------------|---------------|----------------------------------------|
| QR | `https://wa.me/settings/linked_devices#<payload>` (veya `whatsapp://settings/linked_devices#<payload>`) taraması | `iq xmlns=md` `pair-device` | QR alanı 4'ten `adv secret` |
| Telefon numarası + kod | `notification` `link_code_companion_reg` aşama `companion_hello`, kullanıcı 8 karakterlik kodu yazar | `primary_hello`, daha sonra (`companion_finish` sonrası) aynı `pair-device` | iki X25519 sonucundan ve bir rastgele değerden türetilen `adv secret` (bölüm 4.4) |

Her iki yol da tek bir `C44423JaU` nesnesinde ve tek bir `pair-device` IQ'sunda birleşir (found: `KYB`, `companion_finish` paketinden `C44423JaU`'yu QR için `C45850K0w.A01`'in kullandığı aynı yapıcıyla oluşturur).

---

## 3. QR akışı (primary tarafı)

### 3.1 QR payload'ı

`C45741Jxy.A01`, `https://wa.me/settings/linked_devices#` veya `whatsapp://settings/linked_devices#` önekini çıkarır ve geri kalanı URL-decode eder. `A02`, `,` üzerinden böler (found):

| İdx | İçerik | Kodlama | Kullanım |
|-----|---------|----------|-----|
| 0 | `ref` | string | eşleştirme referansı; `CAPI_` ile başlayan bir ref reddedilir (`invalid ref`) |
| 1 | companion public key | base64 | `pub-key` olarak gönderilir, nonce anahtarı için salt (3.4). Ad inferred: Noise static key (kod yolunda `companion_server_auth_key_pub`) |
| 2 | companion identity key | base64, 32 bayt, ayrıştırıcı başa `0x05` (Curve25519 türü) ekler | hesap imzasıyla imzalanır |
| 3 | `adv secret` | base64 | ADV sarmalayıcısı için HMAC anahtarı |
| 4 | platform kodu (isteğe bağlı) | tek karakter | bir platform türüne eşlenir; `j` = hosted cihaz |

- 3'ten az parça: `qrData/processQR/error/invalid_code parts`. Identity key veya adv secret eksik (eski 3 alanlı QR): `invalid qr code, missing companion identity key or adv secret` → yerel kod **-9**.
- Platform karakter tablosu (`EnumC26221BZl`'den bağımsız, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Yalnızca hosted kontrolü ve loglama için kullanılır (3.2).

### 3.2 Herhangi bir şey gönderilmeden önceki yerel kontroller

| Kontrol | Kod | Yerel kod |
|-------|------|------------|
| QR'da identity key ve adv secret var | `C45850K0w.A01` | -9 |
| hosted flag'i tutarlı: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| başka bir eşleştirme zaten çalışıyor (`kri.A0N` veya companion-device yöneticisi meşgul) | `A04` | -17 |
| yerel ADV timestamp'i geçerli (`C24270w6.A00() != -1`) | `A04` | -8 |
| hosted companion | `A04`: `Hosted pairing is not supported` | -10 |
| defense-mode friction gerekli | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (challenge'larla yeniden dene) |

Hosted eşleştirme bu derlemede istemci tarafında engellenmiştir (`pairing for hosted device is not supported on the consumer build`).

### 3.3 IQ'dan önce: syncd temizliği ve key index

1. syncd durumu kirliyse (`sync-manager/shouldCleanUpSyncdOnPairing`), uygulama önce syncd'yi temizler, sonra devam eder (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (`RunnableC46617KYr` içinde):
   - saklı rawId veya index yok: yeni rastgele rawId, index 1;
   - bağlı companion yok: `rawId + 1`, index 1 kalır;
   - companion'lar var: `currentIndex + 1`; taşmada rawId + 1 ve tüm cihazların oturumu kapatılır (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (bölüm 5.4).

### 3.4 Ne oluşturulur

`C45850K0w.A00` içinde; `E` = companion identity key (32 B, ham), `P` = primary identity key çifti (Curve25519), `S` = adv secret:

| Adım | İşlem | Kademe |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | hesap imzası = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; önek `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` boş bırakılır: companion ekler) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = serialized step 3, hmac = HMAC-SHA256(key = S, data = step 3 bytes), accountType}`; hosted için veri `06 05 ‖ bytes` | found |
| 5 | `C24270w6.A01`'den `BCB` (ADVKeyIndexList), `A02` ile imzalanır → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | nonce anahtarı `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, `pem` alt düğümü olarak sarılır | found (türetme); amaç inferred |
| 7 | isteğe bağlı `encryption-metadata` (`C38898Gvq`): `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag`, `AuthProofHelper`'dan (hesap parolası şifrelemesi, `rsa2048` etiketi) | found (yapı); neyi kanıtladığı unknown |
| 8 | isteğe bağlı `client-props` (`C43107IrI`, bölüm 3.6) | found |

Adım 6 ayrıntısı: `pem` düğümü `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 days`, `key_id=1` ile etiketlenmiştir, ancak alt düğümü 32 baytlık HKDF çıktısının `key.getEncoded()` değerini taşır (`SecretKeySpec` algoritması `AES-GCM`). Etiket ve içerik uyuşmuyor; nedeni unknown. Sunucu kullanımı inferred (sunucu, cihaz başına bir nonce'u companion'a şifreler; bkz. `companion_meta_nonce` sütunu).

### 3.5 `pair-device` IQ'su (primary → sunucu)

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <pair-device>
    <ref>…</ref>                                    <!-- QR field 0 -->
    <pub-key>…</pub-key>                            <!-- QR field 1 -->
    <device-identity>ADVSignedDeviceIdentityHMAC</device-identity>
    <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
    <client-props>…</client-props>                  <!-- optional -->
    <pem version="1" algorithm="rsa2048"><pem>…</pem><ttl ts_s="432000"/><key_id>1</key_id></pem>
    <encryption-metadata version="1" algorithm="rsa2048">…</encryption-metadata>   <!-- optional -->
    <companion_qr_origin_source>1|2</companion_qr_origin_source>
    <challenges><supported><friction variant="1"/><passkey-create/></supported>
                <completed>…</completed></challenges>                              <!-- optional -->
  </pair-device>
</iq>
```

Found: tüm alt düğüm adları, `ts` öznitelik değeri (key-index-list timestamp'i), timeout **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source`, giriş değeri 3 için `1`, giriş değeri 5 için `2`'dir (giriş int'lerinin anlamı unknown). Alt düğüm sırası ve `companion_qr_origin_source` dalı decompiler tarafından kısmen bozulmuştur; sırayı doğrulanmamış kabul edin.

### 3.6 `client-props` (`C43107IrI`)

| Alan | Numara | Tür | Ayarlandığı durum |
|-------|--------|------|-----------|
| `isChatDbLidMigrated` | **1** | bool | chat DB LID geçişi tamamlandı |
| `isSyncdPureLidSession` | **2** | bool | syncd pure-LID flag'i mevcut |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | recovery flag'i |
| `isHsThumbnailSyncEnabled` | **4** | bool | history-sync thumbnail flag'i |
| `subscriptionSyncPayload` | **5** | bytes | md sync etkinken oluşturulur (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | bot JID DB geçişi tamamlandı |

### 3.7 Sonuç işleme (`KRI.CFS`)

Başarı sonucu alt düğümleri (found):

| Alt düğüm | Kullanım |
|-------|-----|
| `device` özniteliği `jid` | yeni companion `DeviceJid`; device id **99**, hosted platform girdisine eşlenir |
| `companion-props` | `DeviceProps` proto'su (`C43105IrG`): `os` **1** (string), `version` **2** (message), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (message) |
| `retry-ts` özniteliği `ts` | sunucu daha yeni bir timestamp ister; uygulama yeniden dener (`RunnableC46585KXj`) |
| `retry-after-challenges` | alt düğümler `friction` (öznitelik `variant`, `1` olmalı, isteğe bağlı `location` "lat,lon") veya `passkey-create` (öznitelik `created`) |
| `retry-with-method` | alt düğümler `qr-code` veya `shortcake-with-passkeys`; ikincisi varsa 32 baytlık handoff key (adv secret'ın HKDF'i, info `shortcake-passkey-handoff-v1`) saklanır (`PairingHandoffKeyHolder`), bir abprop ile kapılıdır |

Başarıda uygulama `CJY` cihaz kaydını saklar (rastgele 24 baytlık base64 string, `adv_key_index` = geçerli index, `requireFullSync`), key-index-list timestamp'ini `adv_timestamp_sec` olarak kaydeder (`C24270w6.A05`) ve history sync durumunu başlatır (`C8N`).

Teslim hatası (`Bog`): retry flag'i açıksa en fazla **3** yeniden deneme, gecikme `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s) (found); ardından hata callback'i.

---

## 4. Telefon numarası / eşleştirme kodu akışı (primary tarafı)

### 4.1 Adımlar

| # | Yön | Stanza / eylem | Sınıf |
|---|-----------|-----------------|-------|
| 1 | companion → sunucu → primary | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | primary | hello'yu saklar, push bildirimi gösterir → `CompanionHelloConfirmationActivity` / kod girme ekranı | `C10J`, `C77`, `JYJ` |
| 3 | kullanıcı | 8 karakterlik kodu yazar | `LinkedDevicesEnterCodeActivity` |
| 4 | primary → sunucu | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (timeout 120000 ms) |
| 5 | sunucu → primary | `notification` `stage=companion_finish` | `C10J` → `KYB` case 0 |
| 6 | primary → sunucu | `pair-device` IQ (bölüm 3.5) | `C45850K0w` |
| 7 | diğer aşamalar | `refresh_code` (primary kod yenileme ister, öznitelik `force_manual_refresh`) | `C10J` |

### 4.2 `companion_hello` bildirimi (found)

| Alt düğüm | Kullanım |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | kodla sarılmış companion ephemeral X25519 anahtarı (4.3) |
| `companion_server_auth_key_pub` | daha sonra `pair-device` içindeki `pub-key` olur |
| `link_code_pairing_ref` | oturum ref'i (string) |
| `companion_platform_id` | platform id string'i |
| `companion_platform_display` | görünen ad |
| öznitelik `should_show_push_notification` | `true` → push bildirimi |

Tutulan durum (`C77`/`CE4`, SharedPrefs JSON `companion_reg_with_link_code_companion_hello_info_json`): ref, platform id, sarılmış anahtar, sunucu auth anahtarı, son kullanma `now + min(360000, flag 3816 * 1000)` ms. Süresi dolmuş veya olmayan hello → "companion hello is null or expired" (UI durumu 2). Farklı bir ref ile gelen daha yeni bir hello, önceki ref'i iptal eder (`KRJ.A00(oldRef, "true")`).

### 4.3 Kod ve sarma crypto'su (found)

| Öğe | Değer |
|------|-------|
| Kod | 5 rastgele bayt → 8 karakter, karakter başına 5 bit, alfabe `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 sembol, `0 I O U` yok) (`K1T.A00`, companion tarafından üretilir) |
| Koddan anahtara | PBKDF2-HMAC-SHA256, **131072** iterasyon, 256 bit, parola = kod karakterleri, salt = sarılmış blob'un ilk 32 baytı (`K1T.A02`) |
| Sarılmış ephemeral anahtar | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, plaintext = 32 baytlık X25519 public key; uzunluk ≥ 48 olmalı |
| Primary yanıtı | primary kendi ephemeral anahtar çiftini üretir, public key'ini aynı şekilde sarar (yeni 32 B salt, 16 B IV, aynı kod) |

### 4.4 `primary_hello` ve `companion_finish`

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md">
  <link_code_companion_reg stage="primary_hello">
    <link_code_pairing_wrapped_primary_ephemeral_pub>salt32‖iv16‖ct</…>
    <primary_identity_pub>32 B primary identity key</primary_identity_pub>
    <link_code_pairing_ref>ref</link_code_pairing_ref>
  </link_code_companion_reg>
</iq>
```

`companion_finish` bildirimi alt düğümleri: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. `KYB` case 0 içinde primary işleme:

1. `eph = X25519(primary eph priv, companion eph pub)` (`primary_hello` anında saklanmıştı).
2. Paket düzeni `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, en az 44 bayt.
3. Anahtar = HKDF-SHA256(salt = paket salt'ı, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Kontroller: primary identity, kendi identity key'ine eşit olmalı; companion identity, bildirimdeki `companion_identity_public` ile eşit olmalı; aksi halde ref düşürülür ve UI bir hata durumu alır.
6. `adv secret = HKDF-SHA256(salt = 32 zero bytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Handoff key = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (ayrıca `C44423JaU` içinde saklanır).
8. `C44423JaU`, `pub-key` = `companion_server_auth_key_pub`, companion identity, adv secret ile oluşturulur → QR ile aynı `pair-device` IQ'su.

Dıştaki ephemeral ECDH mevcuttur (3. adımın HKDF IKM'sidir). Daha önceki bir derleme notu "bu aşamada ECDH yok" diyordu; bu derleme için yanlıştır.

Primary tarafındaki hata işaretleri: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. ADV imzalı cihaz kimliği

### 5.1 Proto alanları (found, lite-proto düzen string'lerinden)

| Mesaj | Sınıf | Alan | Numara | Tür |
|---------|-------|-------|--------|------|
| `ADVDeviceIdentity` | `C25815BBy` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `keyIndex` | **3** | uint32 |
| | | `accountType` | **4** | enum (`EnumC32116E1o`) |
| | | `deviceType` | **5** | enum (`EnumC32116E1o`) |
| `ADVSignedDeviceIdentity` | `C25792BBb` | `details` | **1** | bytes |
| | | `accountSignatureKey` | **2** | bytes |
| | | `accountSignature` | **3** | bytes |
| | | `deviceSignature` | **4** | bytes (companion tarafından ayarlanır) |
| `ADVSignedDeviceIdentityHMAC` | `C25785BAt` | `details` | **1** | bytes |
| | | `hmac` | **2** | bytes |
| | | `accountType` | **3** | enum |
| `ADVKeyIndexList` | `BCB` | `rawId` | **1** | uint32 |
| | | `timestamp` | **2** | uint64 |
| | | `currentIndex` | **3** | uint32 |
| | | `validIndexes` | **4** | packed uint32 |
| | | `accountType` | **5** | enum |
| `ADVSignedKeyIndexList` | `C25786BAu` | `details` | **1** | bytes |
| | | `accountSignature` | **2** | bytes |
| | | `accountSignatureKey` | **3** | bytes (yalnızca hosted) |

Alan numaraları ve wire türleri oluşturulmuş message info'dan okunur; adlar kanonik ADV mesajlarıyla eşleşir. Enum adları: `EnumC32116E1o` değerleri E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 İmza önekleri ve algoritmalar

| Önek | Sabit | İmzalanan / MAC'lenen veri | İmzalayan | Kademe |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | hesap imzası: `‖ details ‖ companion identity pub` | primary identity key | found |
| `06 05` | `A0G` | hesap imzasının hosted varyantı; hosted için ayrıca HMAC verisinin başına eklenir | primary identity key / adv secret | found |
| `06 01` | `A0H` | cihaz imzası: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | companion identity key | found (doğrulama tarafı) |
| `06 06` | `A0I` | cihaz imzasının hosted varyantı | companion identity key | found (doğrulama tarafı) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | primary identity key | found |
| `06 07` | `A0K` | non-E2EE ("hybrid") attestation (`AeaUtils`), key-index-list öneki değil | primary identity key | found |

- İmza ilkeli: `C38851hm.A00("best")`, `org.whispersystems.curve25519.OpportunisticCurve25519Provider` yükler; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (64 baytlık imza), `A02` = `calculateAgreement`. Anahtarlar 32 bayttır ve tür baytı `5`'tir. Yani Signal curve25519 kütüphanesinin Curve25519 imzaları (XEdDSA tarzı, algoritma adından değil kütüphaneden inferred). Provider seçimi (native veya Java) çalışma zamanında belirlenir (belirli bir cihazda hangisinin kullanıldığı unknown).
- HMAC: `javax.crypto.Mac` ile `HmacSHA256` (`AbstractC38971i1.A00`).

### 5.3 Key-index listesi

`C24270w6.A01`, `ADVKeyIndexList` oluşturur; `validIndexes` şunlardan oluşan bir kümedir (found): primary slotu için bir girdi (companion modunda değilken değer 0; dal koşulu inferred), saklanan her companion'ın `adv_key_index` değeri (`CJY.A07`) ve `currentIndex`. `A02`, `06 02 ‖ details` imzalar.

`C24250w4.A00` bunu şöyle iter:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout 32000 ms. Kapı `A02`: flag **477** sıfır değil, companion'lar mevcut (veya companion modu), companion modunda değil. Başarısızlıkta `adv_key_index_list_update_retry_count` artırılır; **5**'in üzerinde uygulama `adv-key-index-list-update … fails for more than 5 times` loglar ve tüm companion'ların oturumunu kapatır (`C24270w6.A03`). Başarı sayaçları temizler (`A05`).

### 5.4 Timestamp kuralı (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = NTP düzeltmeli saat, `srv` = sunucu zamanı. `ts = max(srv if |srv - now| <= 86400 else now, last + 1)`. `last + 1 > now + 86400` ise değer geçersizdir (-1, `getTimestampSec invalid ts` loglanır), bu da eşleştirmeyi yerel kod -8 ile engeller. Hesap başına monotonik (found).

### 5.5 Wire üzerinde doğrulama (`C24230w2`)

Primary'nin gördüğü her cihaz kimliği için (kendi ve kişilerin companion'ları) şunları sırayla kontrol eder (found):

1. primary identity key biliniyor (saklı veya listeden `accountSignatureKey`), değilse `no primary key`;
2. companion identity key ayrışıyor (`0x05`+32 B), değilse `invalid companion public key`;
3. `prefix ‖ details ‖ companion identity` üzerinde hesap imzası, değilse `fail to verify account signature`;
4. `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` üzerinde cihaz imzası (hosted `06 06`), değilse cihaz reddedilir;
5. key-index-list: primary key ile `06 02 ‖ details` üzerinde imza; listenin `adv timestamp`'i tutarlı olmalı (`advTimestampMismatch`, `advListTimestampInvalid`); uyuşmayan gelen key index yerel durumu sıfırlar (`incoming key-index not matching local state, resetting`); aynı cihaz için zaten mevcut daha büyük bir index, eski girdiyi düşürür (`filterDeviceWithKeyIndexList`).

---

## 6. Cihaz listesi, kayıt ve limitler

### 6.1 `devices` bildirimi (primary alır)

`add` veya `remove` alt düğümlü `notification` (başka her şey: `unknown type of device notification`). Öznitelikler ve alt düğümler (found): `device_hash`, isteğe bağlı `device_lid_hash` artı `lid`, `device` girdileri (jid, key index), isteğe bağlı `key-index-list` (bytes, öznitelikler `ts`, `expected_ts`). Bildirim `offline` özniteliği taşıyorsa kullanıcı sonraki sync için kuyruğa alınır; aksi halde bir sync işi çalışır (`SyncDeviceNotificationRunnable`). Liste yalnızca timestamp'i saklı `adv_timestamp_sec`'ten eski değilse kabul edilir (aksi halde `local ts is larger than notification one`).

### 6.2 Saklanan cihaz kaydı (`devices` tablosu, `C1h8`)

| Grup | Sütunlar (found) |
|-------|-----------------|
| Kimlik | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Zaman | `last_active`, `login_time`, `logout_time` |
| Sync | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Yetenek | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

`platform_type` değerleri `companion-props.platformType`'tan gelir (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Limitler ve flag'ler

| Flag / öğe | Anlam | Kademe |
|-------------|---------|------|
| **15550** | integer: azami bağlı cihaz sayısı (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max` "link a device" eylemini engeller; QR tarayıcı ek olarak `at_device_limit` alır; `OrbitCompanionLinkActivity` limite ulaşıldığında reddeder) | found (kullanım); varsayılan değer unknown (sunucudan gelen abprop); `md_linked_devices_max_devices_limit` metrik alanı mevcut |
| **3816** | `companion_hello`'nun geçerli kaldığı saniye, 360 s ile sınırlı | found |
| **477** | key-index-list güncellemeleri için kapı (sıfır olmayan) | found |
| **18193** | duyurulan `challenges/supported` içine `friction` (variant 1) ekler | found (kullanım); sunucudaki etkisi unknown |
| **28161** | duyurulan ikinci challenge'ı (`passkey-create`) ekler | inferred eşleme (decompiler dalı kaybetti) |
| **29500** | defense-mode kontrolünde kullanılan hosted-pairing kapısı | found (okuma), anlam inferred |
| **31019** | bazı nedenlerle remove-all'a `exclude_hosted_companion=true` özniteliğini ekler | found |

Sunucunun limiti istemci kontrolünden bağımsız olarak uygulayıp uygulamadığı unknown. Burada okunan kodda primary'nin companion'lar için istemci tarafı inaktivite timeout'u yoktur; boştaki companion'ların sunucu tarafı süre dolumu unknown.

---

## 7. Bağlantıyı kaldırma (primary tarafı)

### 7.1 Tek cihaz

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, timeout 32000 ms. Sonuç `coex_token` alt düğümünü taşıyabilir (coexistence işleyicisine iletilir). Teslim hatası veya hata, başarısızlık callback'ini -1 koduyla çağırır (found).

### 7.2 Tüm cihazlar

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Boş yerel liste doğrudan başarı callback'ine kısa devre yapar. Kodda görülen reason string'leri: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; liste daha uzun olabilir, kaynak ifade kesilmiş).

### 7.3 Otomatik bağlantı kaldırma tetikleyicileri (found)

| Tetikleyici | Neden |
|---------|--------|
| key-index-list güncellemesi 5'ten fazla kez başarısız oldu | `adv-key-index-list-update`, hepsini logout |
| key index taşması | `A03` sıfırlama |
| geçersiz ADV durumu / bilinmeyen companion (`KZD` case 43) | `invalid_adv_status` |
| hosted ↔ E2EE hesap türü geçişi | tüm cihazları atar (`handleADVMetadata` logu) |
| sunucu `remove` türünde `devices` bildirimi gönderir | yerel kayıt kaldırılır (inferred) |
| bağlı-cihazlar ekranında kullanıcı eylemi / `EavesdropMonitor/disconnectDevice` | `user_initiated` (monitor için found; UI yolu inferred) |

Hesabın bütünüyle kaldırılması (`urn:xmpp:whatsapp:account` `remove`) farklı bir IQ'dur ve companion bağlantısını kaldırmayla ilgisizdir.

---

## 8. Hata durumları

### 8.1 `C44661Jem.A01` tarafından işlenen sunucu kodları

| Kod | Callback | UI | Kademe |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | "companion too old" durumu | found |
| 404 / 405 / 443 / 445 | genel `C2w` | string eşlemesi `C44648JeY`: 405 ve 443'ün özel metinleri var; 404/405/443/445 tek bir başlığı paylaşır | found (id'ye göre string'ler); 404/443/445'in tam anlamı unknown |
| diğer | genel `C2w` | eşleştirme başarısız | found |

`InstrumentationAuthActivity` sonuç kodlarını adlandırır: 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, diğeri `PAIRING_FAILED` (found). Sunucu 405'in consumer/SMB durumuna eşlenmesi, string id'sinden inferred.

### 8.2 Yerel kodlar

| Kod | Neden | Çözüm |
|------|-------|-----|
| -8 | yerel ADV timestamp'i geçersiz (saat ile son saklanan ts + 1) | cihaz saatini düzeltin; UI string'i "invalid device time" |
| -9 | QR'da identity key / adv secret eksik | güncel bir QR kullanın |
| -10 | consumer derlemesinde hosted eşleştirme | n/a |
| -13 | platform ile hosted flag uyuşmazlığı | n/a |
| -17 | başka bir eşleştirme çalışıyor | bekleyin; istek en fazla 32 s yaşar |
| -20 | sunucu challenge istedi (`retry-after-challenges`) | friction / passkey challenge'ını tamamlayın |
| -1 | kaldırma isteği gönderilmedi veya başarısız oldu | yeniden deneyin |

### 8.3 Link-code hataları

| Belirti (log) | Neden |
|------------------|-------|
| `companion hello is null or expired` | kod süre dolduktan sonra yazıldı (flag 3816, en fazla 360 s) |
| `decryption fail` (hello) | yanlış kod (PBKDF2 anahtarı farklı; AES-CTR'de tag yok, bu yüzden yanlış kod anlamsız bir anahtar verir, sonraki adımlarda yakalanır; inferred) |
| `primary identity doesn't match` | paket başka bir primary anahtarı için oluşturulmuş |
| `companion identity doesn't match` | bildirim ve paket uyuşmuyor |
| `invalid-primary-adv-key-length` / `adv public key is 0` | primary ephemeral anahtarı üzerinde companion-rolü kontrolleri |

---

## 9. Temel ayrımlar

### 9.1 Karıştırılmaması gerekenler

| A | B |
|---|---|
| **primary** tarafından gönderilen `pair-device` (bu rapor) | companion-rolü bir uygulama tarafından **alınan** `pair-device` (işleyici `AbstractC40501kw`, id 242, QR için ref'leri taşır) |
| `ADVSignedDeviceIdentity` (imzalı, HMAC yok) | `ADVSignedDeviceIdentityHMAC` (`device-identity` içinde gönderilen sarmalayıcı) |
| `pair-device`'ın `device-identity` alt düğümü (HMAC sarmalayıcısı) | giden mesaj stanza'larındaki `device-identity` alt düğümü (bir companion tarafından eklenen hesap kimliği; `adv_signed_identity` pref'i) |
| hesap imzası (primary anahtar, önek `06 00`) | cihaz imzası (companion anahtarı, önek `06 01`) |
| key-index-list öneki `06 02` | `06 07` (non-E2EE attestation) |
| QR `pub-key` / `companion_server_auth_key_pub` | companion identity key (hesap imzasını alan) |
| `rawId` (sıfırlamada değişen hesap geneli id) | `keyIndex` (companion başına) |
| QR platform karakteri (`EnumC26332BbY`) | wire `DeviceProps.platformType` (`EnumC25120ArW`), farklı numaralandırma |

### 9.2 Hosted cihaz

JID device id **99** (`device_id should be 99 for hosted device`), kayıt/unpair işaretleyicisi `hosted_device_pairing`, imza önekleri `06 05` / `06 06`, `exclude_hosted_companion`. Primary bu derlemede hosted bir cihazı eşleştirmeyi reddeder (yerel -10). Bu string'lerin ötesindeki her şey unknown.

### 9.3 Shortcake

`retry-with-method`, `shortcake-with-passkeys` listeleyebilir; uygulama bunun üzerine bir handoff key saklar ve UI'yi değiştirir. `ShortcakeJni`, `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` ve `nativeResponderStart/Finish` sunar (found). El sıkışma transkripti native'dir ve burada decompile edilmedi: unknown.

### 9.4 Friction / defense mode

`pair-device`, desteklenen challenge'ları duyurur ve yeniden denemede `completed` olanları döndürür. Primary, defense mode açıkken (`C271211x.A0N()`) ve friction challenge'ı henüz tamamlanmamışken friction gerektirmeye yerel olarak karar verir; bu karar ilk IQ'dan önce verilir (`defense mode friction triggered`). `retry-after-challenges` gönderen sunucu tarafı politikası görünmez (unknown).

### 9.5 Companion'ın istemci attestation'ı yok

pair-device payload'ındaki hiçbir şey companion'ın hangi yazılımı çalıştırdığını kanıtlamaz: `ref`, `pub-key`, identity key, adv secret ve platform karakteri QR tarafından kendi beyanıdır. İmzaların kanıtladığı, bu primary hesabın o identity key'i yetkilendirdiğidir. Her "resmi istemci" kontrolü sunucu tarafındadır (465 kararı yalnızca istemci tarafında işlenir).

### 9.6 Aynı APK'daki companion-rolü kodu (kısaca)

| Öğe | Bulgu |
|------|---------|
| `companion_hello` IQ alt düğümleri | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; öznitelik `should_show_push_notification` (found, `C0YS`) |
| kod | 5 rastgele baytın `K1T.A00` base32'si (4.3) |
| QR döndürme | öznitelikleri `stage` 0/1/2 ve isteğe bağlı `sentinel`, alt düğümü `ref` olan IQ `pair-device-rotate-qr` |
| gelen md IQ'ları | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (id'ler 242, 243, 266, 278, 279) |
| `pair-success` içeriği ve companion `pair-device-sign` yanıtı | bu derlemede izlenmedi: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Yerel kaynakla karşılaştırıldı; yalnızca her iki tarafta kontrol edilen eşleşmeler ve bir fark.

| Öğe | APK 2.26.41.6 | `baron-baileys-v2` | Sonuç |
|------|---------------|--------------------|--------|
| QR payload'ı | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | eşleşir (4 alan) |
| Eşleştirme kodu türetme | PBKDF2-SHA256 131072 it., alfabe `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, aynı alfabe (`crypto.js`, `generics.js`) | eşleşir |
| Anahtar paketi | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, plaintext identity ‖ identity ‖ random32 | aynı düzen (`messages-recv.js`) | eşleşir |
| adv secret | HKDF(zero salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | eşleşir |
| HMAC sarmalayıcısı | HMAC-SHA256(adv secret, [hosted için 06 05 ‖] ADVSignedDeviceIdentity bytes) | aynı (`validate-connection.js`) | eşleşir |
| Hesap / cihaz imzası mesajları | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | aynı | eşleşir |
| Hosted key-index-list öneki | doğrulayıcı ve imzalayıcı her liste için `06 02` kullanır; `06 07` non-E2EE attestation önekidir | `accountType == HOSTED` iken `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` kullanılır (`chats.js`) | **farklı**; hosted akış bu consumer derlemesi tarafından çalıştırılmaz, bu yüzden farkın etkisi unknown |

Hiçbir "neden başarısız olur" iddiasında bulunulmaz: eşleşen satırları izleyen bir Baileys companion'ı, primary'nin burada ayrıştırdıklarıyla tutarlıdır; sunucunun kabulü statik olarak doğrulanamaz.

---

## 11. Eksiksiz akışlar

### 11.1 QR akışı

```
[Companion]  shows QR  https://wa.me/settings/linked_devices#ref,noisePub,identityPub,advSecret[,platform]
     │
     ▼
[Primary]    scan → C45741Jxy.A02 → C45423Jrn → C44423JaU
     │       checks: -9 / -13 / -17 / -8 / -10 ; defense mode → challenges (-20)
     │       incrementCurrentKeyIndex ; ts = C24270w6.A00()
     │       details  = ADVDeviceIdentity{rawId, ts, keyIndex, accountType, deviceType}
     │       accSig   = Curve25519.sign(P.priv, 06 00 ‖ details ‖ companionIdentity)
     │       signed   = ADVSignedDeviceIdentity{details, P.pub, accSig}
     │       wrapper  = ADVSignedDeviceIdentityHMAC{signed, HMAC-SHA256(advSecret, signed)}
     │       list     = ADVSignedKeyIndexList (sig 06 02)
     │       K        = HKDF(salt = noisePub, IKM = advSecret, "Canonical Ent Companion Nonce Encrypt")
     ▼
iq set xmlns=md  <pair-device> ref, pub-key, device-identity, key-index-list ts, client-props, pem, … </pair-device>
     │
     ▼
[WA Server]   (not observed) validates, creates device jid, sends pair-device / pair-success to the companion
     │
     ▼
Result to primary: <device jid/> <companion-props/>   (or retry-ts / retry-after-challenges / retry-with-method / error 465, 496, …)
     │
     ▼
[Primary]    store CJY record, adv_timestamp_sec = list ts, start history sync
     │
     ▼
[Server → Primary]  notification devices add{device_hash, device…, key-index-list ts}  → SyncDeviceNotificationRunnable → verify (5.5)
```

### 11.2 Eşleştirme kodu akışı

```
[Companion]  iq link_code_companion_reg stage=companion_hello
     │         wrapped_ephemeral = salt32 ‖ iv16 ‖ AES-CTR(PBKDF2(code, salt), ephPub)
     ▼
[WA Server]  → notification stage=companion_hello  → [Primary] C10J (id 252)
     │                                               store hello (ttl ≤ 360 s), push notification
     │                                               user types 8-char code
     ▼
[Primary]    unwrap companion eph pub ; make own eph pair ; eph = X25519(...)
     │         iq link_code_companion_reg stage=primary_hello
     │             wrapped_primary_ephemeral_pub, primary_identity_pub, link_code_pairing_ref
     ▼
[Companion]  eph = X25519(...) ; bundle = salt32 ‖ nonce12 ‖ GCM(HKDF(eph, salt), companionId ‖ primaryId ‖ random32)
     │         iq stage=companion_finish
     ▼
[WA Server]  → notification stage=companion_finish → [Primary] KYB
     │            decrypt, check both identities, advSecret = HKDF0(eph ‖ DH(id) ‖ random, "adv_secret")
     ▼
[Primary]    pair-device IQ (same as 11.1, pub-key = companion_server_auth_key_pub)
     ▼
(11.1 continues)
```

### 11.3 Bağlantıyı kaldırma

```
[Primary UI / auto trigger]
     │   remove-companion-device jid=… reason=…     (or all="true")
     ▼
iq set xmlns=md  →  [WA Server]  →  result (optional coex_token)
     │
     ▼
[Primary]   remove local record, new key-index-list on next update (iq key-index-list ts)
[Server → other devices]  notification devices remove{…}
```
