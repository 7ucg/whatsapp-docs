<!-- src-sha1: 6458e557973884f0b2c8c175f4607447365f03a6 -->
# WhatsApp Bağlı-Cihaz Eşleştirmesi — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** companion eşleştirmesinin primary-cihaz tarafı, QR akışı, telefon-numarası / eşleştirme-kodu akışı, `pair-device` ve `pair-success` stanza'ları, key materyali, ADV imzalı cihaz kimliği ve key-index listesi, cihaz listesi ve limitler, bağlantı kaldırma, hatalar, Baileys karşılaştırması

---

## 1. Teknik olarak ne

Bağlı bir cihaz (companion), aynı hesabın ikinci bir uç noktasıdır. Primary telefon, companion'ın identity key'i üzerinde bir ADV (account device verification) imzalı kimliği üreterek onu yetkilendirir. Tüm ifadeler decompile edilmiş APK'nın statik analizidir; hiçbir şey wire üzerinde yakalanmamıştır. Kademe: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi.

Obfuscated isimler build-başınadır ve 2.26.41.6'da stabil string'lerden yeniden çözülmüştür.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| QR/eşleştirme orkestratörü | `C45850K0w` (log öneki `CompanionDeviceQrHandler`) | QR'ı ayrıştırır, ADV proto'larını inşa eder, `pair-device`'ı gönderir |
| `pair-device` IQ builder'ı | `RunnableC46606KYf` | IQ'yu inşa eder |
| `pair-device` istek/yanıt yardımcısı | `KRI` (`devicePairRequest/*`) | gönderme, retry, `device` / `companion-props` / retry ipuçlarını ayrıştırma |
| Hata yönlendiricisi | `C44661Jem` | sunucu hata kodunu UI callback'ine eşler |
| QR string parser'ı | `C45741Jxy` → `C45423Jrn` | QR payload'unu eşleştirme verisine |
| Ayrıştırılmış eşleştirme verisi | `C44423JaU` | ref, companion key'leri, adv secret'i, platform |
| ADV yardımcısı | `C24270w6` (`CompanionDeviceAdvUtil`) | rawId, key index'i, zaman damgası, key-index-list inşası ve imzalaması |
| Key-index-list güncelleyicisi | `C24250w4` (`DeviceKeyIndexListUpdateHandler`) | imzalı listeyi sunucuya push eder |
| ADV doğrulayıcısı | `C24230w2` (`DeviceADVInfoHandler`) | wire'da görülen kimlikleri ve listeleri doğrular |
| Cihaz-listesi bildirim handler'ı | `C1S0`'da anonim sınıf (`DeviceUpdateNotificationHandler`), `RunnableC29334CoL` | `devices` bildirimi |
| Link-code bildirim handler'ı | `C10J` (`LinkCodeCompanionRegNotificationHandler`) | bildirim id'si 252 |
| Link-code yöneticisi (primary) | `KZ3` (giriş kodu, `primary_hello`), `KYB` (`companion_finish`), `C10L`, `C77` | eşleştirme-kodu akışı |
| Link-code kripto yardımcısı | `K1T` (`CompanionRegWithLinkCodeUtil`) | HKDF, PBKDF2, base32 |
| Cihaz yöneticisi | `C0XQ` (`companion-device-manager`) | liste, çıkış |
| Kaldırma yardımcısı | `C28905Ch6` (`DeviceRemoveRequestProtocolHelper`) | `remove-companion-device` |
| Signal curve wrapper'ı | `C38851hm` | `org.whispersystems.curve25519` sağlayıcısı "best" |
| ADV proto sınıfları | `C25815BBy`, `C25792BBb`, `C25785BAt`, `C25786BAu`, `BCB` | bkz bölüm 5 |
| DeviceProps | `C43105IrG` (enum `EnumC25120ArW`) | `pair-device` sonucunda `companion-props` |
| İstemci prop'ları | `C43107IrI` | `client-props` çocuğu |
| Hesap/şifreleme tipi | `EnumC32116E1o` | `E2EE` 0, `HOSTED` 1, `NON_E2EE` 2 |

Primary UI'sinde üç giriş modu mevcuttur (`EnumC26221BZl`): `QR_CODE`, `PHONE_NUMBER_AND_CODE`, `EXTERNAL_DEEPLINK_QR_CODE` (found).

Aynı APK, companion-rol kayıt kodunu da içerir (durum makinesi `C0YS`, `companion/registration/*` logları). Bu kapsam dışıdır; sadece primary'nin aldığı şeyi açıklamak için gereken parçalar açıklanır (bölüm 9.6).

---

## 2. Eşleştirme yolları özet

| Yol | Primary'de tetikleyici | Primary'nin gönderdiği | Primary ve companion'ı bağlayan sır |
|------|--------------------|---------------|----------------------------------------|
| QR | `https://wa.me/settings/linked_devices#<payload>` (veya `whatsapp://settings/linked_devices#<payload>`)'in taranması | `iq xmlns=md` `pair-device` | QR alanı 4'ten `adv secret` |
| Telefon numarası + kod | `notification` `link_code_companion_reg` aşaması `companion_hello`, kullanıcı 8-karakterlik kodu yazar | `primary_hello`, daha sonra (`companion_finish` sonrası) aynı `pair-device` | iki X25519 sonucu artı bir rastgele sayıdan türetilen `adv secret` (bölüm 4.4) |

Her iki yol da bir `C44423JaU` nesnesinde ve bir `pair-device` IQ'sunda birleşir (found: `KYB`, `companion_finish` bundle'ından `C44423JaU`'yu `C45850K0w.A01`'in QR için kullandığı aynı constructor'la inşa eder).

---

## 3. QR akışı (primary tarafı)

### 3.1 QR payload'u

`C45741Jxy.A01`, `https://wa.me/settings/linked_devices#` veya `whatsapp://settings/linked_devices#` önekini çıkarır ve kalanı URL-decode eder. `A02`, `,` üzerinde böler (found):

| Idx | İçerik | Kodlama | Kullanım |
|-----|---------|----------|-----|
| 0 | `ref` | string | eşleştirme referansı; `CAPI_` ile başlayan bir ref reddedilir (`invalid ref`) |
| 1 | companion public key'i | base64 | `pub-key` olarak gönderilir, nonce key'i için salt (3.4). Ad inferred: Noise static key'i (kod yolunda `companion_server_auth_key_pub`) |
| 2 | companion identity key'i | base64, 32 byte, parser `0x05`'i (Curve25519 tipi) öne ekler | hesap imzasıyla imzalanır |
| 3 | `adv secret` | base64 | ADV wrapper'ı için HMAC key'i |
| 4 | platform kodu (opsiyonel) | bir karakter | bir platform tipine eşlenir; `j` = hosted cihaz |

- 3'ten az parça: `qrData/processQR/error/invalid_code parts`. Eksik identity key veya adv secret (eski 3-alanlı QR): `invalid qr code, missing companion identity key or adv secret` → yerel kod **-9**.
- Platform karakter tablosu (`EnumC26221BZl`'den bağımsız, `EnumC26332BbY`): `0` UNKNOWN, `1` CHROME, `2` EDGE, `3` FIREFOX, `4` IE, `5` OPERA, `6` SAFARI, `7` DESKTOP, `8` UWP, `9` OTHER_WEB, `a` IOS_TABLET, `b` IOS_PHONE, `c` IOS_CATALYST, `d` ANDROID_TABLET, `e` ANDROID_PHONE, `f` ANDROID_AMBIGUOUS, `g` WEAR_OS, `i` AR_DEVICE, `j` HOSTED_DEVICE, `k` VR, `l` SMARTGLASSES, `n` WAIL_WAI, `o` WAIL_ALEXA (found). Sadece hosted kontrolü ve loglama için kullanılır (3.2).

### 3.2 Herhangi bir şey gönderilmeden önce yerel kontroller

| Kontrol | Kod | Yerel kod |
|-------|------|------------|
| QR'ın identity key'i ve adv secret'i var | `C45850K0w.A01` | -9 |
| hosted flag'i tutarlı: `(accountType == HOSTED) == (platform int == 20)` | `A01` | -13 |
| başka bir eşleştirme zaten çalışıyor (`kri.A0N`, veya companion-device yöneticisi meşgul) | `A04` | -17 |
| yerel ADV zaman damgası geçerli (`C24270w6.A00() != -1`) | `A04` | -8 |
| hosted companion | `A04`: `Hosted pairing is not supported` | -10 |
| defense-mode sürtünmesi gerekiyor | `RunnableC46606KYf`: `defense mode friction triggered` | -20 (challenge'larla yeniden dene) |

Hosted eşleştirme bu build'de istemci tarafında bloklanmıştır (`pairing for hosted device is not supported on the consumer build`).

### 3.3 IQ'dan önce: syncd temizliği ve key index'i

1. Syncd durumu kirliyse (`sync-manager/shouldCleanUpSyncdOnPairing`), uygulama önce syncd'yi temizler, sonra devam eder (`handleSyncdDirty clean syncD before companion dereg`) (found).
2. `incrementCurrentKeyIndex` (`RunnableC46617KYr`'de):
   - saklanmış rawId veya index yok: yeni rastgele rawId, index 1;
   - bağlı companion yok: `rawId + 1`, index 1 olarak kalır;
   - companion'lar mevcut: `currentIndex + 1`; overflow'da rawId + 1 ve tüm cihazlar çıkış yapar (`C24270w6.A03`).
3. `ts = C24270w6.A00()` (bölüm 5.4).

### 3.4 İnşa edilen şey

`C45850K0w.A00`'da, `E` = companion identity key'i (32 B, ham), `P` = primary identity key çifti (Curve25519), `S` = adv secret ile:

| Adım | Operasyon | Kademe |
|------|-----------|------|
| 1 | `ADVDeviceIdentity` `{rawId, timestamp=ts, keyIndex=currentIndex, accountType, deviceType}` | found |
| 2 | hesap imzası = `Curve25519 sign(P.priv, prefix ‖ details ‖ E)`; önek `06 00` (hosted `06 05`) | found |
| 3 | `ADVSignedDeviceIdentity` `{details, accountSignatureKey = P.pub, accountSignature}` (`deviceSignature` boş kalır: companion onu ekler) | found |
| 4 | `ADVSignedDeviceIdentityHMAC` `{details = adım 3'ün serileştirilmiş hali, hmac = HMAC-SHA256(key = S, data = adım 3 byte'ları), accountType}`; hosted için veri `06 05 ‖ bytes`'tır | found |
| 5 | `C24270w6.A01`'den `BCB` (ADVKeyIndexList), `A02` tarafından imzalanır → `ADVSignedKeyIndexList` (5.3) | found |
| 6 | nonce key'i `K = HKDF-SHA256(salt = pub-key, IKM = S, info = "Canonical Ent Companion Nonce Encrypt", 32 B)`, `pem` çocuğu olarak sarılır | found (türetim); amaç inferred |
| 7 | opsiyonel `encryption-metadata` (`C38898Gvq`): `AuthProofHelper`'dan (hesap şifresi şifrelemesi, `rsa2048` etiketi) `encrypted_key`, `nonce`, `encrypted_data`, `auth_tag` | found (yapı); neyi kanıtladığı unknown |
| 8 | opsiyonel `client-props` (`C43107IrI`, bölüm 3.6) | found |

Adım 6 üzerine detay: `pem` node'u `version=1`, `algorithm=rsa2048`, `ttl ts_s = 5 days`, `key_id=1` olarak etiketlenir, ama çocuğu 32-byte'lık HKDF çıktısının `key.getEncoded()`'ını taşır (`SecretKeySpec` algoritması `AES-GCM`). Etiket ve içerik eşleşmiyor; neden unknown'dır. Sunucu kullanımı inferred'dir (sunucu companion'a cihaz-başına bir nonce şifreler; bkz `companion_meta_nonce` kolonu).

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

Found: tüm çocuk adları, `ts` attribute değeri (key-index-list zaman damgası), timeout **32000 ms** (`c10140Tq.A0Q(…, 219, 32000L)`). `companion_qr_origin_source`, giriş değeri 3 için `1`'dir ve giriş değeri 5 için `2`'dir (giriş int'lerinin anlamı unknown). Tam çocuk sırası ve `companion_qr_origin_source` dalı decompiler tarafından kısmen bozulmuştur; sırayı doğrulanmamış olarak ele alın.

### 3.6 `client-props` (`C43107IrI`)

| Alan | Numara | Tip | Ayarlandığında |
|-------|--------|------|----------|
| `isChatDbLidMigrated` | **1** | bool | sohbet DB LID geçişi tamamlandı |
| `isSyncdPureLidSession` | **2** | bool | syncd pure-LID flag'i mevcut |
| `isSyncdSnapshotRecoveryEnabled` | **3** | bool | kurtarma flag'i |
| `isHsThumbnailSyncEnabled` | **4** | bool | geçmiş-senkronizasyonu küçük-resim flag'i |
| `subscriptionSyncPayload` | **5** | bytes | md senkronizasyonu etkinken inşa edilir (`buildSubscriptionSyncPayload`) |
| `isBotJidDbMigrated` | **6** | bool | bot JID DB'si geçirildi |

### 3.7 Sonuç işleme (`KRI.CFS`)

Başarı sonucu çocukları (found):

| Çocuk | Kullanım |
|-------|-----|
| `device` attr `jid` | yeni companion `DeviceJid`'i; cihaz id'si **99**, hosted platform girişine eşlenir |
| `companion-props` | `DeviceProps` proto'su (`C43105IrG`): `os` **1** (string), `version` **2** (mesaj), `platformType` **3** (enum), `requireFullSync` **4** (bool), `historySyncConfig` **5** (mesaj) |
| `retry-ts` attr `ts` | sunucu daha yeni bir zaman damgası ister; uygulama yeniden dener (`RunnableC46585KXj`) |
| `retry-after-challenges` | çocuklar `friction` (attr `variant`, `1` olmalı, opsiyonel `location` "lat,lon") veya `passkey-create` (attr `created`) |
| `retry-with-method` | çocuklar `qr-code` veya `shortcake-with-passkeys`; ikincisi mevcutsa 32-byte'lık handoff key'i (adv secret'in HKDF'si, info `shortcake-passkey-handoff-v1`) saklanır (`PairingHandoffKeyHolder`), bir abprop ile gated |

Başarıda uygulama `CJY` cihaz kaydını (rastgele 24-byte base64 string'i, `adv_key_index` = mevcut index, `requireFullSync`) saklar, key-index-list zaman damgasını `adv_timestamp_sec` olarak kaydeder (`C24270w6.A05`), ve geçmiş senkronizasyonu durumunu başlatır (`C8N`).

Teslimat başarısızlığı (`Bog`): retry flag'i açıksa, **3**'e kadar yeniden deneme, gecikme `3000 * 3^(n-1)` ms (3 s, 9 s, 27 s) (found); sonra hata callback'i.

---

## 4. Telefon-numarası / eşleştirme-kodu akışı (primary tarafı)

### 4.1 Adımlar

| # | Yön | Stanza / eylem | Sınıf |
|---|-----------|-----------------|-------|
| 1 | companion → sunucu → primary | `notification` `link_code_companion_reg`, `stage=companion_hello` | `C10J` (id 252) |
| 2 | primary | hello'yu saklar, push bildirimi gösterir → `CompanionHelloConfirmationActivity` / kod-girme ekranı | `C10J`, `C77`, `JYJ` |
| 3 | kullanıcı | 8-karakterlik kodu yazar | `LinkedDevicesEnterCodeActivity` |
| 4 | primary → sunucu | `iq xmlns=md type=set` `link_code_companion_reg stage=primary_hello` | `KZ3` (timeout 120000 ms) |
| 5 | sunucu → primary | `notification` `stage=companion_finish` | `C10J` → `KYB` durumu 0 |
| 6 | primary → sunucu | `pair-device` IQ'su (bölüm 3.5) | `C45850K0w` |
| 7 | diğer aşamalar | `refresh_code` (primary kod yenilemesi ister, attr `force_manual_refresh`) | `C10J` |

### 4.2 `companion_hello` bildirimi (found)

| Çocuk | Kullanım |
|-------|-----|
| `link_code_pairing_wrapped_companion_ephemeral_pub` | kodla sarılmış companion ephemeral X25519 key'i (4.3) |
| `companion_server_auth_key_pub` | daha sonra `pair-device`'teki `pub-key` olur |
| `link_code_pairing_ref` | oturum ref'i (string) |
| `companion_platform_id` | platform id string'i |
| `companion_platform_display` | görünen ad |
| attr `should_show_push_notification` | `true` → push bildirimi |

Tutulan durum (`C77`/`CE4`, SharedPrefs JSON `companion_reg_with_link_code_companion_hello_info_json`): ref, platform id'si, sarılı key, sunucu auth key'i, süre dolumu `now + min(360000, flag 3816 * 1000)` ms. Süresi dolmuş veya mevcut olmayan hello → "companion hello is null or expired" (UI durumu 2). Farklı bir ref'li daha yeni bir hello, önceki ref'i iptal eder (`KRJ.A00(oldRef, "true")`).

### 4.3 Kod ve sarma kriptosu (found)

| Öğe | Değer |
|------|-------|
| Kod | 5 rastgele byte → 8 karakter, her biri 5 bit, alfabe `123456789ABCDEFGHJKLMNPQRSTVWXYZ` (32 sembol, `0 I O U` yok) (`K1T.A00`, companion tarafından üretilir) |
| Kod → key | PBKDF2-HMAC-SHA256, **131072** iterasyon, 256-bit, parola = kod karakterleri, salt = sarılı blob'un ilk 32 byte'ı (`K1T.A02`) |
| Sarılı ephemeral key | `[salt 32 ‖ IV 16 ‖ AES-256-CTR ciphertext]`, plaintext = 32-byte'lık X25519 public key'i; uzunluk ≥ 48 olmalı |
| Primary yanıtı | primary kendi ephemeral key çiftini yapar, public key'ini aynı şekilde sarar (taze 32 B salt, 16 B IV, aynı kod) |

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

`companion_finish` bildirimi çocukları: `link_code_pairing_wrapped_key_bundle`, `companion_identity_public`, `link_code_pairing_ref`. `KYB` durumu 0'da primary işlemesi:

1. `eph = X25519(primary eph priv, companion eph pub)` (`primary_hello` zamanında saklanmış).
2. Bundle düzeni `[salt 32 ‖ nonce 12 ‖ AES-256-GCM ciphertext+tag]`, minimum 44 byte.
3. Key = HKDF-SHA256(salt = bundle salt'ı, IKM = `eph`, info = `link_code_pairing_key_bundle_encryption_key`, 32 B).
4. Plaintext = `companion identity pub (32) ‖ primary identity pub (32) ‖ random (32)`.
5. Kontroller: primary identity, kendi identity key'ine eşit olmalı; companion identity, bildirimdeki `companion_identity_public`'e eşit olmalı; aksi halde ref düşürülür ve UI bir hata durumu alır.
6. `adv secret = HKDF-SHA256(salt = 32 zero bytes, IKM = eph ‖ X25519(primary identity priv, companion identity pub) ‖ random, info = "adv_secret", 32 B)` (`K1T.A03`).
7. Handoff key'i = HKDF(adv secret, info `shortcake-passkey-handoff-v1`) (`C44423JaU`'da da saklanır).
8. `C44423JaU`, `pub-key` = `companion_server_auth_key_pub`, companion identity, adv secret ile inşa edilir → QR ile aynı `pair-device` IQ'su.

Dış ephemeral ECDH mevcuttur (adım 3'ün HKDF IKM'sidir). Daha önceki bir build notu "bu aşamada ECDH yok" demişti; bu build için bu yanlıştır.

Primary tarafındaki hata işaretleri: `getCompanionPairingDataOnCompanionFinish ref not exists`, `decryption fail`, `primary identity doesn't match`, `companion identity doesn't match`, `invalid linkCodePairingWrappedKeyBundleDecrypted` (found).

---

## 5. ADV imzalı cihaz kimliği

### 5.1 Proto alanları (found, lite-proto düzen string'lerinden)

| Mesaj | Sınıf | Alan | Numara | Tip |
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
| | | `accountSignatureKey` | **3** | bytes (sadece hosted) |

Alan numaraları ve wire tipleri, üretilen mesaj bilgisinden okunur; kanonik ADV mesajlarıyla eşleşen isimler. Enum adları: `EnumC32116E1o` değerleri E2EE 0, HOSTED 1, NON_E2EE 2.

### 5.2 İmza önekleri ve algoritmaları

| Önek | Sabit | İmzalanan / MAC'lenen veri | İmzalayan | Kademe |
|--------|----------|---------------------|--------|------|
| `06 00` | `AbstractC051108f.A0F` | hesap imzası: `‖ details ‖ companion identity pub` | primary identity key'i | found |
| `06 05` | `A0G` | hesap imzasının hosted varyantı; hosted için HMAC verisinin önüne de eklenir | primary identity key'i / adv secret | found |
| `06 01` | `A0H` | cihaz imzası: `‖ details ‖ companion identity pub ‖ accountSignatureKey` | companion identity key'i | found (doğrulama tarafı) |
| `06 06` | `A0I` | cihaz imzasının hosted varyantı | companion identity key'i | found (doğrulama tarafı) |
| `06 02` | `A0J` | `ADVSignedKeyIndexList`: `‖ details` | primary identity key'i | found |
| `06 07` | `A0K` | non-E2EE ("hybrid") attestation'ı (`AeaUtils`), bir key-index-list öneki değil | primary identity key'i | found |

- İmza ilkeli: `C38851hm.A00("best")`, `org.whispersystems.curve25519.OpportunisticCurve25519Provider`'ı yükler; `A03` = `calculateSignature(random 64 B, priv, msg)`, `A01` = `verifySignature` (64-byte imza), `A02` = `calculateAgreement`. Key'ler, tip byte'ı `5` olan 32 byte'tır. Yani Signal curve25519 kütüphanesinin Curve25519 imzaları (XEdDSA-tarzı, kütüphaneden inferred, algoritma adından değil). Sağlayıcı seçimi native vs Java, çalışma zamanında karar verilir (belirli bir cihazda hangisinin kullanıldığı unknown).
- HMAC: `javax.crypto.Mac` üzerinden `HmacSHA256` (`AbstractC38971i1.A00`).

### 5.3 Key-index listesi

`C24270w6.A01`, `ADVKeyIndexList`'i inşa eder; `validIndexes`, şunlardan oluşan bir kümedir (found): primary slot'u için bir girdi (companion modunda değilken değer 0; dal koşulu inferred), her saklanmış companion'ın `adv_key_index`'i (`CJY.A07`) ve `currentIndex`. `A02`, `06 02 ‖ details`'i imzalar.

`C24250w4.A00`, bunu şöyle push eder:

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <key-index-list ts="…">ADVSignedKeyIndexList</key-index-list>
</iq>
```

Timeout 32000 ms. Gate `A02`: flag **477** sıfır-olmayan, companion'lar mevcut (veya companion modu), companion modunda değil. Başarısızlıkta `adv_key_index_list_update_retry_count` artırılır; **5**'in üzerinde uygulama `adv-key-index-list-update … fails for more than 5 times`'i loglar ve tüm companion'ları çıkış yapar (`C24270w6.A03`). Başarı sayaçları temizler (`A05`).

### 5.4 Zaman damgası kuralı (`C24270w6.A00`)

`last` = SharedPrefs `adv_timestamp_sec`; `now` = NTP-düzeltilmiş saat, `srv` = sunucu zamanı. `ts = max(srv eğer |srv - now| <= 86400 ise, aksi halde now, last + 1)`. `last + 1 > now + 86400` ise değer geçersizdir (-1, `getTimestampSec invalid ts` loglanır), bu yerel kod -8 ile eşleştirmeyi bloklar. Hesap-başına monotonik (found).

### 5.5 Wire üzerinde doğrulama (`C24230w2`)

Primary'nin gördüğü herhangi bir cihaz kimliği için (kendi ve kişilerin companion'ları), bu sırayla kontrol eder (found):

1. primary identity key'i bilinen (saklanmış, veya listeden `accountSignatureKey`), aksi halde `no primary key`;
2. companion identity key'i ayrıştırılıyor (`0x05`+32 B), aksi halde `invalid companion public key`;
3. `prefix ‖ details ‖ companion identity` üzerinde hesap imzası, aksi halde `fail to verify account signature`;
4. `06 01 ‖ details ‖ companion identity ‖ accountSignatureKey` üzerinde cihaz imzası (hosted `06 06`), aksi halde cihaz reddedilir;
5. key-index-list: primary key ile `06 02 ‖ details` üzerinde imza; listenin `adv timestamp`'i tutarlı olmalı (`advTimestampMismatch`, `advListTimestampInvalid`); uyuşmayan gelen bir key index'i yerel durumu sıfırlar (`incoming key-index not matching local state, resetting`); aynı cihaz için zaten mevcut daha büyük bir index, eski girdiyi düşürür (`filterDeviceWithKeyIndexList`).

---

## 6. Cihaz listesi, kayıt ve limitler

### 6.1 `devices` bildirimi (primary alır)

Çocuğu `add` veya `remove` olan bir `notification` (başka herhangi bir şey: `unknown type of device notification`). Attribute'lar ve çocuklar (found): `device_hash`, opsiyonel `device_lid_hash` artı `lid`, `device` girdileri (jid, key index), opsiyonel `key-index-list` (byte'lar, attr `ts`, `expected_ts`). Bildirim attr `offline` taşıyorsa kullanıcı daha sonraki senkronizasyon için kuyruklanır; aksi halde bir senkronizasyon işi çalışır (`SyncDeviceNotificationRunnable`). Liste, zaman damgası saklanmış `adv_timestamp_sec`'ten daha eski değilse kabul edilir (aksi halde `local ts is larger than notification one`).

### 6.2 Saklanan cihaz kaydı (`devices` tablosu, `C1h8`)

| Grup | Kolonlar (found) |
|-------|-----------------|
| Kimlik | `device_id`, `platform_type`, `device_os`, `adv_key_index`, `companion_meta_nonce`, `instrumentation_device_id`, `nickname`, `place_name` |
| Zaman | `last_active`, `login_time`, `logout_time` |
| Senkronizasyon | `full_sync_required`, `full_sync_days_limit`, `full_sync_size_mb_limit`, `recent_sync_days_limit`, `storage_quota_mb`, `inline_initial_hist_sync_payload_enabled`, `history_sync_config_protobuf`, `history_sync_access_type`, `on_demand_ready` |
| Yetenek | `support_hosted_group_msg`, `support_biz_hosted_msg`, `support_group_history`, `support_call_log_history`, `support_message_association`, `support_add_on_history_sync_migration`, `support_guest_chat`, `support_bot_user_agent_chat_history`, `support_fbid_bot_chat_history`, `support_manus_history`, `support_hatch_history`, `support_cag_reactions_and_polls_history`, `support_recent_sync_chunk_message_tuning`, `supported_bot_channel_fbids` |

`platform_type` değerleri, `companion-props.platformType`'tan gelir (`EnumC25120ArW`): 0 UNKNOWN, 1 CHROME, 2 FIREFOX, 3 IE, 4 OPERA, 5 SAFARI, 6 EDGE, 7 DESKTOP, 8 IPAD, 9 ANDROID_TABLET, 10 OHANA, 11 ALOHA, 12 CATALINA, 13 TCL_TV, 14 IOS_PHONE, 15 IOS_CATALYST, 16 ANDROID_PHONE, 17 ANDROID_AMBIGUOUS, 18 WEAR_OS, 19 AR_WRIST, 20 AR_DEVICE, 21 UWP, 22 VR, 23 CLOUD_API, 24 SMARTGLASSES, 25 WAIL, 26 WASS, 27 BUSINESS_BACK_OFFICE, 28 WAIL_WAI, 29 WAIL_ALEXA, 30 AUTOMOTIVE (found).

### 6.3 Limitler ve flag'ler

| Flag / öğe | Anlam | Kademe |
|-------------|---------|------|
| **15550** | tamsayı: maksimum bağlı cihaz sayısı (`LinkedDevicesSharedViewModel.hasMaxDeviceLimitReached`: `loggedInDeviceCount >= max`, "link a device"'ı bloklar; QR tarayıcı ekstra `at_device_limit` alır; `OrbitCompanionLinkActivity`, limite ulaşıldığında reddeder) | found (kullanım); varsayılan değer unknown (sunucu-tarafından-teslim abprop'u); metrik alanı `md_linked_devices_max_devices_limit` mevcut |
| **3816** | `companion_hello`'nun geçerli kaldığı saniye, 360 s'de sınırlı | found |
| **477** | key-index-list güncellemeleri için gate (sıfır-olmayan) | found |
| **18193** | reklam edilen `challenges/supported`'a `friction`'ı (varyant 1) ekler | found (kullanım); sunucudaki etkisi unknown |
| **28161** | reklam edilen ikinci challenge'ı ekler (`passkey-create`) | eşleme inferred (decompiler dalı kaybetti) |
| **29500** | defense-mode kontrolünde kullanılan hosted-eşleştirme gate'i | found (okundu), anlam inferred |
| **31019** | bazı nedenler için remove-all'a `exclude_hosted_companion=true` attribute'unu ekler | found |

Sunucunun limiti istemci kontrolünden bağımsız olarak uygulayıp uygulamadığı unknown'dır. Burada okunan kodda primary'nin companion'lar için istemci-tarafı bir eylemsizlik timeout'u yoktur; boşta kalan companion'ların sunucu-tarafı süre dolumu unknown'dır.

---

## 7. Bağlantı kaldırma (primary tarafı)

### 7.1 Tek cihaz

```xml
<iq to="s.whatsapp.net" type="set" xmlns="md" id="…">
  <remove-companion-device jid="user:device@…" reason="user_initiated"/>
</iq>
```

`C28905Ch6.A00`, timeout 32000 ms. Sonuç çocuğu `coex_token`'ı taşıyabilir (coexistence handler'ına geçirilir). Teslimat başarısızlığı veya hata, başarısızlık callback'ini kod -1 ile çağırır (found).

### 7.2 Tüm cihazlar

`C0XQ.A0Y(reason, removeOnError, isEncryptionTypeTransitioning)`:

```xml
<remove-companion-device all="true" reason="…" [exclude_hosted_companion="true"]/>
```

Boş yerel liste, başarı callback'ine kısa-devre yapar. Kodda görülen neden string'leri: `user_initiated`, `unknown_companion`, `invalid_adv_status`, `lid_migration_peer_sync_limit_exceeded`, `lid_migration_peer_sync_message_failed`, `lid_migration_missing_mappings_in_peer_sync_message` (found; liste daha uzun olabilir, kaynak ifade kesilmiş).

### 7.3 Otomatik bağlantı-kaldırma tetikleyicileri (found)

| Tetikleyici | Neden |
|---------|-------|
| key-index-list güncellemesi 5'ten fazla kez başarısız oldu | `adv-key-index-list-update`, tümünü çıkış yapar |
| key index overflow'u | `A03` sıfırlaması |
| geçersiz ADV durumu / bilinmeyen companion (`KZD` durumu 43) | `invalid_adv_status` |
| hosted ↔ E2EE hesap tipi geçişi | tüm cihazları atar (`handleADVMetadata` log) |
| sunucu `devices` bildirimi tipi `remove` gönderir | yerel kayıt kaldırılır (inferred) |
| bağlı-cihazlar ekranında kullanıcı eylemi / `EavesdropMonitor/disconnectDevice` | `user_initiated` (monitor için found; UI yolu inferred) |

Bütün olarak hesap kaldırması (`urn:xmpp:whatsapp:account` `remove`), farklı bir IQ'dur ve companion bağlantı-kaldırmasıyla ilgisizdir.

---

## 8. Hata durumları

### 8.1 `C44661Jem.A01` tarafından ele alınan sunucu kodları

| Kod | Callback | UI | Kademe |
|------|----------|----|------|
| **465** | `Blp` → `onCompanionPlatformRestricted` | `CompanionPlatformRestrictedBottomSheet` | found |
| **496** | `Blv` → `onCompanionTooOld` | "companion too old" durumu | found |
| 404 / 405 / 443 / 445 | genel `C2w` | string eşlemesi `C44648JeY`: 405 ve 443'ün özel metinleri var; 404/405/443/445 bir başlığı paylaşır | found (id'ye göre string'ler); 404/443/445'in tam anlamı unknown |
| diğer | genel `C2w` | eşleştirme başarısız | found |

`InstrumentationAuthActivity`, sonuç kodlarını adlandırır: 1 `CONSUMER_SMB_CROSS_PAIRING`, 2 `UNSUPPORTED_PRIMARY_VERSION`, 3 `INVALID_QR_CODE`, 4 `COMPANION_PLATFORM_RESTRICTED`, 5 `COMPANION_TOO_OLD`, 6 `MAX_DEVICE_LIMIT_REACHED`, aksi halde `PAIRING_FAILED` (found). Sunucu 405'inin consumer/SMB durumuna eşlemesi, string id'sinden inferred'dir.

### 8.2 Yerel kodlar

| Kod | Neden | Düzeltme |
|------|-------|-----|
| -8 | yerel ADV zaman damgası geçersiz (saat vs son saklanan ts + 1) | cihaz saatini düzelt; UI string'i "invalid device time" |
| -9 | QR'da identity key'i / adv secret'i eksik | geçerli bir QR kullan |
| -10 | consumer build'de hosted eşleştirme | n/a |
| -13 | platform vs hosted flag'i uyuşmazlığı | n/a |
| -17 | başka bir eşleştirme çalışıyor | bekle; istek en fazla 32 s yaşar |
| -20 | sunucu challenge istedi (`retry-after-challenges`) | friction / passkey challenge'ını tamamla |
| -1 | kaldırma isteği gönderilmedi veya başarısız oldu | yeniden dene |

### 8.3 Link-code başarısızlıkları

| Belirti (log) | Neden |
|---------------|-------|
| `companion hello is null or expired` | süre dolumundan sonra girilen kod (flag 3816, maks 360 s) |
| `decryption fail` (hello) | yanlış kod (PBKDF2 key'i farklı; AES-CTR'nin tag'i yok, bu yüzden yanlış bir kod anlamsız bir key verir, sonraki adımlarda yakalanır; inferred) |
| `primary identity doesn't match` | bundle başka bir primary key için inşa edildi |
| `companion identity doesn't match` | bildirim ve bundle uyuşmuyor |
| `invalid-primary-adv-key-length` / `adv public key is 0` | primary ephemeral key üzerinde companion-rol kontrolleri |

---

## 9. Ayırt edilmesi gereken noktalar

### 9.1 Karıştırılmaması gerekenler

| A | B |
|---|---|
| **Primary** tarafından gönderilen `pair-device` (bu rapor) | bir companion-rol uygulaması tarafından **alınan** `pair-device` (handler `AbstractC40501kw`, id 242, QR için ref'leri taşır) |
| `ADVSignedDeviceIdentity` (imzalı, HMAC yok) | `ADVSignedDeviceIdentityHMAC` (`device-identity`'de gönderilen wrapper) |
| `pair-device`'in `device-identity` çocuğu (HMAC wrapper'ı) | çıkış mesajı stanza'larındaki `device-identity` çocuğu (bir companion tarafından eklenen hesap kimliği; `adv_signed_identity` pref'i) |
| hesap imzası (primary key'i, önek `06 00`) | cihaz imzası (companion key'i, önek `06 01`) |
| key-index-list öneki `06 02` | `06 07` (non-E2EE attestation) |
| QR `pub-key` / `companion_server_auth_key_pub` | companion identity key'i (hesap imzasını alan) |
| `rawId` (sıfırlamada değişen hesap-çapında id) | `keyIndex` (companion-başına) |
| QR platform karakteri (`EnumC26332BbY`) | wire `DeviceProps.platformType`'ı (`EnumC25120ArW`), farklı numaralandırma |

### 9.2 Hosted cihaz

JID cihaz id'si **99** (`device_id should be 99 for hosted device`), kayıt/bağlantı-kaldırma işaretçisi `hosted_device_pairing`, imza önekleri `06 05` / `06 06`, `exclude_hosted_companion`. Primary, bu build'de hosted bir cihazı eşleştirmeyi reddediyor (yerel -10). Bu string'lerin ötesindeki her şey unknown'dır.

### 9.3 Shortcake

`retry-with-method`, `shortcake-with-passkeys`'i listeleyebilir; uygulama sonra bir handoff key'i saklar ve UI'yi değiştirir. `ShortcakeJni`, `nativeMlkem768GenerateKeypair/Encapsulate/Decapsulate` ve `nativeResponderStart/Finish`'i açığa çıkarır (found). Handshake transcript'i native'dir ve burada decompile edilmedi: unknown.

#### 9.3a Silent linking — tethered/peripheral companion eşleştirmesi + epoch migration'ı (2.26.45.10'da yeni, found)

Yukarıdaki üçten (klasik ADV/QR, eşleştirme-kodu/CRSC, hosted cihaz) daha dar, **dördüncü** bir eşleştirme mekanizması: **tethered/peripheral companion'ların** sessiz bağlanması — giyilebilirler ve akıllı gözlükler, `DeviceProps.platformType` `WEAR_OS` / `AR_WRIST` / `AR_DEVICE` / `SMARTGLASSES`. Paket `com.whatsapp.instrumentation.product.silentlinking` (`SilentLinkingNativeRegistration`, `SilentLinkingSessionManager$Session`).

**"Silent" demek QR taraması yok demektir, kullanıcı etkileşimi yok demek değildir.** Telemetri string'leri (found), kısa-kod onayı akışını gösterir: `"code displayed to user"` → `"user confirmed code on primary"` → `"companion registration start"`. Peripheral kısa bir kod gösterir ve kullanıcı onu telefonda onaylar — eşleştirme-kodu akışıyla (§4) aynı kullanıcı-mevcudiyeti modeli, sadece QR görüntüsü olmadan. Giriş noktası, `SilentLinkingVerificationActivity`'yi (`android:exported="false"`, dahili-sadece, deep link yok) besleyen çağrı-sonrası giyilebilir upsell UI'sidir (`PostCallWearableUpsellBottomSheet`, `com.whatsapp.calling.wearableupsell`). Tetikleyici sadece istemci-UI'sidir: her iki sınıfta da hiçbir `AlarmManager`/`WorkManager`/sunucu-push giriş noktası bulunamadı, ve her ikisinde de hiçbir yerde `unlink`/`unpair`/"var olan cihaz" mantığı yok — bu bir bağlantı kurar, sessizce bir bağlantıyı kaldırmaz.

`SilentLinkingNativeRegistration`, ortaya çıkan identity kaydını taşımak için mevcut CRSC v2/v3 yan kanalından (`CompanionRegOverSideChannelV2Manager`/`V3Manager`, §4'ün aynı altyapısı) bir kayıt slotu kiralar. Gerçek companion key exchange'i, ayrı, önceden-belgelenmemiş bir protobuf ailesidir:

**Shortcake RPC zarf ailesi** (found, smali'den alan adları/numaraları, bağımsız olarak Java'ya decompile edilmemiş):

| Sınıf | Rol |
|-------|------|
| `LX/R9f` | Üst-seviye `oneof` zarfı: `protocolVersion`(1), `bootstrapAndHello`(2), `finishAndReady`(3), `peripheralAck`(4), `postCommitProofEnvelope`(5), `readinessRequestEnvelope`(6), `readinessResponseEnvelope`(7), `exactCleanupRequest`(8), `exactCleanupReceipt`(9) |
| `LX/RAN` | Bootstrap&Hello: `linkId`(1), `setupAttemptId`(2), `epochId`(3), `purpose`(4), `hnSignPub`(5), `hnEpoch1EphPub`(6, klasik ECDH ephemeral'ı), `hnMlkemPub`(7, ML-KEM-768 pubkey'i), `protocolVersion`(8), `selectedCapabilities`(9), `migrationContextHash`(10), `hnDeviceSerial`(11) |
| `LX/RA1` | Signal-ciphertext-sarılmış zarf: `signalCiphertext`(1), `signalMessageType`(2), `peripheralHello`(3), `signalRequestId`(4), `companionAdvFingerprint`(5), `primarySignalPeerFingerprint`(6) — handshake'i companion'ın kendi ADV identity fingerprint'ine (§5) bağlar |
| `LX/RAW` | İkinci `oneof` zarfı, epoch-migration tarafı: `rpcRequest`(1), `rpcResponse`(2), `primaryReady`(3), `peripheralAck`(4), `rotationControl`(5), `requestStatus`(6), `migrationPostCommitProof`(7), `migrationStatusRequest`(8), `migrationStatusResponse`(9), `migrationProbeRequest`(10), `migrationProbeResponse`(11) |
| `LX/RUe` | Enum `PERIPHERAL_PROPS_PLATFORM_{UNKNOWN,IOS,ANDROID}` — peripheral'ın kendi OS'i |

`RAN.hnEpoch1EphPub` (klasik), `RAN.hnMlkemPub` (ML-KEM-768) ile birlikte bir **hibrit klasik-ECDH + post-quantum key exchange'i** doğrular, sadece-PQ değil. Bu, **bu raporda belgelenen ilk post-quantum kripto mekanizmasıdır**: ML-KEM-768 (FIPS 203 / Kyber-768), native `ShortcakeJni` (liboqs `OQS_KEM_ml_kem_768`, libsignal'in `KEMPublicKey`/`KEMSecretKey`'i tarafından sarılı — ayrı bir geçişte native decompilasyonla found, bkz brain `research/2.26.36.1/shortcake-kem-native.md`) üzerinden çalıştırılır. Bu Java-tarafı schema, sadece native analizin unknown bıraktığı transcript framing'idir; byte-seviyesi Responder-Start/Finish handshake'inin kendisi native-sadece ve unknown kalır.

**HKDF context etiketleri** (found, `LX/SdB`'deki literal string'ler, KDF = HMAC-SHA256 / HKDF-SHA256, §4.3'teki link-code-wrap KDF'siyle aynı ilkel): `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_V1`, `WA_TETHERED_EPOCH1_HN_KEY_POP_V1`, `WA_TETHERED_EPOCH1_PERIPHERAL_HELLO_HASH_V1`, `WA_TETHERED_EPOCH1_PRIMARY_FINISH_V1`, `WA_TETHERED_EPOCH1_WA_KEY_POP_V1`, `WA_TETHERED_EPOCH1_HYBRID_KX_V1`, `WA_TETHERED_LINK_IDENTITY_CONTEXT_V1`. ("HN" = primary/telefon tarafı; ağaç içinde hiçbir yerde açılmamış, muhtemelen "Host/Home Network".)

**Epoch rotasyonu/migration'ı (found string'ler, inferred rol).** `LX/TIR`, kapsamlı bir migration-hata kelime dağarcığı taşır (`"Invalid migration frame version"`, `"Migration epoch mismatch"`, `"Migration shadow serial mismatch"`, `migration_shadow`, vb.), `RAN.epochId` ve `RAW`'ın rotation/migration-probe/status/post-commit-proof alanlarıyla birleşmiş. Birlikte okununca bu, zaten-kurulmuş bir tethered link için arka-plan bir **key-epoch rotasyon protokolüdür** — `SilentLinkingSessionManager$Session`, Shortcake key'lerini yeni bir `epochId` altında döndürmek için periyodik olarak `SilentLinkingNativeRegistration`'ı yeniden çağırır, bir probe/status/promotion/replay ve bir "shadow"-kaydı geri-alma yolu ile. Bu, found string'ler/alanlar üzerinde inferred bir anlatıdır; kaybolmuş bir klasik companion oturumu için bir kurtarma mekanizması değildir ve sunucu-tarafından-push edilmiş bir bağlantı-kaldırması değildir. Bir rotasyon döngüsünün somut tetikleme koşulu, ve `R9f`/`RAW` için tam wire transport'u (CRSC yan-kanal payload'u vs. özel bir stanza/IQ), unknown'dır.

**Baileys/velowa ilgisi sıfırdır.** Native `ShortcakeJni` kriptosunun ve sadece uygulama-içi UI'den erişilebilir dahili (`exported="false"`) bir activity'nin ardında gated, tamamen WhatsApp'ın kendi giyilebilir/akıllı-gözlük companion kategorisi kapsamındadır. Klasik ADV/CRSC companion eşleştirmesine (§2-§4, bir üçüncü-taraf multi-device istemcisinin uyguladığı şey) dokunmaz, ve bir Web/Desktop companion'ı bağlantıdan kaldıracağı veya sessizce yeniden bağlayacağı herhangi bir mekanizma bulunamadı.

### 9.4 Friction / defense modu

`pair-device`, desteklenen challenge'ları reklam eder ve retry'de tamamlanan olanları döndürür. Primary, defense modu açıkken (`C271211x.A0N()`) ve friction challenge'ı henüz tamamlanmamışken friction'ı gerektirmeye yerel olarak karar verir; bu karar ilk IQ'dan önce verilir (`defense mode friction triggered`). `retry-after-challenges`'i gönderen sunucu-tarafı politika görünür değildir (unknown).

### 9.5 Companion'ın hiçbir istemci attestation'ı yok

`pair-device` payload'unda hiçbir şey companion'ın hangi yazılımı çalıştırdığını kanıtlamaz: `ref`, `pub-key`, identity key, adv secret ve platform karakteri QR tarafından kendi-kendine-beyan edilmiştir. İmzaların kanıtladığı şey, bu primary hesabının o identity key'ini yetkilendirdiğidir. Herhangi bir "resmi istemci" kontrolü sunucu tarafındadır (465 hükmü sadece istemci tarafında ele alınır).

### 9.6 Aynı APK'daki companion-rol kodu (kısaca)

| Öğe | Bulgu |
|------|------|
| `companion_hello` IQ çocukları | `link_code_pairing_wrapped_companion_ephemeral_pub`, `companion_server_auth_key_pub`, `companion_platform_id`, `companion_platform_display`, `link_code_pairing_nonce`; attr `should_show_push_notification` (found, `C0YS`) |
| kod | `K1T.A00`, 5 rastgele byte'ın base32'si (4.3) |
| QR'ı döndürme | attr'ları `stage` 0/1/2 ve opsiyonel `sentinel` olan, çocuğu `ref` olan IQ `pair-device-rotate-qr` |
| gelen md IQ'ları | `pair-device`, `pair-success`, `ref`, `companion_reg_refresh`, `integrity` (id'ler 242, 243, 266, 278, 279) |
| `pair-success` içeriği ve companion `pair-device-sign` yanıtı | bu build'de izlenmedi: unknown |

---

## 10. Baileys (`baron-baileys-v2`)

Yerel kaynağa karşı karşılaştırıldı; sadece her iki tarafta da kontrol edilen eşleşmeler ve bir fark.

| Öğe | APK 2.26.41.6 | `baron-baileys-v2` | Sonuç |
|------|---------------|--------------------|--------|
| QR payload'u | `ref,noisePub,identityPub,advSecret[,platform]` | `[ref, noiseKeyB64, identityKeyB64, advB64].join(',')` (`socket.js`) | eşleşiyor (4 alan) |
| Eşleştirme-kodu türetimi | PBKDF2-SHA256 131072 iterasyon, alfabe `123456789ABCDEFGHJKLMNPQRSTVWXYZ` | `iterations: 2 << 16`, aynı alfabe (`crypto.js`, `generics.js`) | eşleşiyor |
| Key bundle'ı | `[salt32 ‖ nonce12 ‖ GCM]`, info `link_code_pairing_key_bundle_encryption_key`, plaintext identity ‖ identity ‖ random32 | aynı düzen (`messages-recv.js`) | eşleşiyor |
| adv secret | HKDF(sıfır salt, `eph ‖ DH(identity) ‖ random`, info `adv_secret`) | `hkdf(identityPayload, 32, {info:'adv_secret'})` | eşleşiyor |
| HMAC wrapper'ı | HMAC-SHA256(adv secret, [hosted için 06 05 ‖] ADVSignedDeviceIdentity byte'ları) | aynı (`validate-connection.js`) | eşleşiyor |
| Hesap / cihaz imza mesajları | `06 00 ‖ details ‖ companionIdentity`; `06 01 ‖ details ‖ companionIdentity ‖ accountSignatureKey` | aynı | eşleşiyor |
| Hosted key-index-list öneki | doğrulayıcı ve imzalayıcı her liste için `06 02` kullanır; `06 07` non-E2EE attestation önekidir | `accountType == HOSTED` olduğunda kullanılan `WA_ADV_HOSTED_KEY_INDEX_LIST_SIG_PREFIX = [6, 7]` (`chats.js`) | **farklı**; hosted akışı bu consumer build tarafından çalıştırılmaz, bu yüzden farkın etkisi unknown |

Hiçbir "neden başarısız olur" iddiası yapılmıyor: eşleşen satırları izleyen bir Baileys companion'ı, burada primary'nin ayrıştırdığıyla tutarlıdır; sunucu tarafından kabulü statik olarak doğrulanamaz.

---

## 11. Tam akışlar

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

### 11.2 Eşleştirme-kodu akışı

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

### 11.3 Bağlantı kaldırma

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
