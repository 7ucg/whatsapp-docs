<!-- src-sha1: f9c1d644c604d99d2f1b54082218c3f75d2cf8a7 -->
# WhatsApp Uygulama Durumu Senkronizasyonu — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android'de uygulama durumu senkronizasyonu (syncd): beş koleksiyon, `w:sync:app:state` IQ, patch / snapshot / harici blob'lar, SET/REMOVE mutasyonları, mutasyon anahtarı türetme ve kayıt şifreleme, index / value MAC'ler, LT-Hash, snapshot ve patch MAC'ler, sync anahtarları (üretim, paylaşım, istek, süre dolumu), giden ve gelen doğrulama, sync action kataloğu (96 action: chat, label, contact, nctSalt …), fatal hata ve yeniden deneme işleme, snapshot kurtarma, feature flag'ler, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

Uygulama durumu senkronizasyonu, hesaba ait küçük durum verilerini (sessize alma, sabitleme, arşivleme, yıldızlama, kişiler, etiketler, ayarlar …) birincil telefon ile bağlı tüm cihazlar arasında çoğaltır. Sunucu yalnızca uçtan uca şifreli kayıtları saklar, bunları koleksiyon başına sıralar ve sürümlü patch'ler sunar. Tüm ifadeler dekompile edilmiş APK'nın statik analizidir; ağ üzerinde hiçbir şey yakalanmadı. Seviye: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi. Obfuscate edilmiş adlar 2.26.41.6 içinde kararlı string'lerden (`WhatsApp Mutation Keys`, `WhatsApp Patch Integrity`, `w:sync:app:state`, koleksiyon adları, log önekleri) yeniden çözümlendi.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| Sync manager | `C12440bB` (`sync-manager/*`) | zamanlama, `A0S` fatal hata, `A0Q` tüm veriyi silme |
| İstek işleyici / IQ oluşturucu / ayrıştırıcı | `C53148Nnt` / `C46361ux` / `N90` | IQ gönderme, `<sync>` oluşturma, sonucu ayrıştırma |
| Eski yanıt işleyici | `SyncResponseHandler` (`consumer/companiondevice/p049iq`) | eski uygulama yolu, `A08` fatal hata işleme |
| KMP motoru | `com.whatsapp.kmp.syncd.syncdengine.*` | `OutgoingProcessor`, `IncomingProcessor`, `SyncdResponseHandler`, `SyncdResponseProcessor`, `CollectionHandler`, `crypto/*` |
| Koleksiyon enum'u / action enum'u | `EnumC24862AnK` / `EnumC24865AnN` | 5 koleksiyon / 96 action wire adı |
| Action'dan koleksiyona | `AbstractC24863AnL.A00` | ordinal switch |
| Mutasyon tabanı / handler tabanı | `AbstractC24864AnM` / `AbstractC25077Aqp` | bekleyen mutasyon / action handler |
| Anahtar yöneticisi / deposu | `C12800bm` (`SyncdKeyManager`) / `C13620d6` (tablo `crypto_info`) | anahtar üretme, paylaşma, isteme, süresini doldurma, kalıcı kaydetme |
| Anahtar id'si / anahtar / anahtar verisi | `CGH` / `C51259MoT` / `C51361MqC` | 6 baytlık id / id + veri / veri, `C8H` parmak izi, ts |
| Mutasyon anahtarları | `MhX` | HKDF çıktısı, 5 dilim |
| Paylaşım / istek taşıyıcıları | `C26102BPk` (FMessage 38) / `C26101BPj` (39) | peer mesajları |
| LT-Hash, HKDF | `AbstractC50511MVx.A00` + `KmpLtHash16`, `AbstractC38961i0` | 128 baytlık hash, RFC 5869 |
| Kripto (eski / KMP) | `C52959NkE` / `KmpSyncdCryptoHelper`, `KmpSyncdEncryptor`, `KmpSyncdDecryptor`, `KmpSyncdIncomingAntiTamperingValidator` | aynı formüller |
| Harici blob'lar | `C17650kB` (indirme), `KmpExternalMutationsUploaderImpl` | MMS tipi `md-app-state` |
| Bootstrap / tümünü silme / kurtarma | `C24986ApL` / `C17630k8` / `KmpSyncdFatalErrorRecovery` | durum makinesi, `delete_all_data`, snapshot sunma |
| Fatal türleri / eski exception | `Lx6` / `C49784Lv2` | 70 adlandırılmış tür / int `errorCode` |

Aynı protokolün iki uygulaması bir arada bulunur. KMP motoru, derleme varsayılanı **false** olan üç sunucu kontrollü boolean ile seçilir (**15909** kripto, **20682** gelen, **18234** giden, bölüm 12). Bir hesabın hangi yolu çalıştırdığı bilinmiyor. MAC ve şifreleme formülleri her ikisinde de aynıdır (`C52959NkE` ve `KmpSyncd*` içinde karşılaştırıldı).

Birincil cihaz ve companion aynı kodu çalıştırır. Bulunan farklar: yalnızca birincil cihaz `contact` / `lid_contact` mutasyonları oluşturur (`Companion cannot create contact mutations`); yalnızca companion `return_snapshot="true"` gönderir; fatal hata işleme farklıdır (11.3).

---

## 2. Koleksiyonlar

| Wire adı | Enum ordinal | Kritik | Log biti (`C17530jy.A00`) | Action'lar |
|-----------|--------------|--------|--------------------------|---------|
| `regular` | 0 | hayır | 3 | 35 |
| `regular_low` | 1 | hayır | 5 | 36 |
| `regular_high` | 2 | hayır | 4 | 19 |
| `critical_block` | 3 | evet | 1 | 4 |
| `critical_unblock_low` | 4 | evet | 2 | 2 |

Kritik küme = `{critical_block, critical_unblock_low}` (`EnumC24862AnK.A01`). `A00()` ordinal'i 1..5'e eşler; tüketicisi izlenmedi.

Android'de `critical_block` hesap ayarı action'larını (`setting_pushName`, `setting_locale`, `setting_securityNotification`, `generated_wui`) içerir, bir engelleme listesi **değildir**; `contact` ve `lid_contact` `critical_unblock_low` içinde yer alır. 96 girişli enum'da engellemeye göre adlandırılmış hiçbir action yoktur (found).

**Bootstrap (companion, kısmen inferred).** `syncd_bootstrap_state` (`C24986ApL`) 0 → 4 arasında çalışır. Found: kritik küme senkronize olur → durum 2 ve bir "critical blocking complete" sinyali; kritik olmayan tüm koleksiyonlar senkronize olur → durum 4; durum 3 history-sync adımıdır (inferred). Hata nedenleri: `critical_sync_timeout`, `history_sync_failure`, `syncd_failure`; watchdog logu `syncd-critical-bootstrap-timeout`. Birincil cihazda bir companion eşleştirmek `prepareCriticalDataUpload` çalıştırır: history sync, ardından `shareAllKeys`; anahtar yoksa ve flag **27528** açıksa önce bir anahtar üretilir.

---

## 3. IQ katmanı

### 3.1 İstek (found, `C46361ux`)

```xml
<iq to="s.whatsapp.net" xmlns="w:sync:app:state" type="set" id="…">
  <sync data_namespace="3">
    <collection name="regular_low" order="1" version="41" return_snapshot="true">
      <patch>…SyncdPatch bytes…</patch>
    </collection>
  </sync>
  <coex><bot>…enc node…</bot></coex>      <!-- optional -->
</iq>
```

| Öznitelik | Değer |
|-----------|-------|
| `data_namespace` | `<sync>` üzerinde sabit `3` |
| `order` | `critical_unblock_low` için `0`, diğerleri için `1`; anlamı bilinmiyor |
| `version` | yerel olarak saklanan koleksiyon sürümü (`C17540jz.A02`); yoksa atlanır |
| `return_snapshot` | yalnızca sürümü null veya 0 olan companion için `"true"` |
| `<patch>` | yalnızca bekleyen yerel mutasyon varsa |
| `<coex><bot>` | coexistence-v2: kullanılan sync anahtarları bir bot'a şifrelenir (`sync-request-handler/coexv2 *`); hata durumunda IQ bu olmadan gider ve anahtarlar bant dışı paylaşılır |

Zaman aşımı 32 sn; tek bir IQ birden fazla koleksiyon taşıyabilir.

### 3.2 Sonuç (found, `N90`)

```xml
<iq type="result"><sync>
  <collection name="X" type="error"><error code="409" text="…"/> [<patches>…]</collection>
  <collection name="X" version="42"/>                    <!-- outgoing patch acked -->
  <collection name="X" has_more_patches="true">
    <snapshot>ExternalBlobReference bytes</snapshot>    <!-- companion bootstrap -->
    <patches><patch>SyncdPatch bytes</patch>…</patches>
  </collection>
</sync></iq>
```

`<sync>` eksikse veya `<snapshot>` / `<patch>` gövdesi boşsa → geçici hata. Sürümü, patch'i ya da snapshot'ı olmayan bir koleksiyon yalın ad olarak tutulur (anlamı inferred: yeni bir şey yok). Snapshot gövdeleri her zaman bir `ExternalBlobReference`'tır, hiçbir zaman satır içi kayıt değildir.

Koleksiyon hataları (`M4T`): -1 `UNKNOWN` yeniden denenebilir; 400 / 404 / 405 / 406 fatal (`Xmpp*ForCollection`); 409 `CONFLICT` ekli patch'leri uygula sonra yeniden dene, aksi halde yeniden denenebilir (dal koşulu dekompilede belirsiz); 500 yeniden denenebilir.

Global IQ hatası (`C53148Nnt.Brt`, `backoff` saniye cinsinden):

| Kod | İşleme |
|------|----------|
| 400, 404, 405, 406 | fatal; eski kodlar 64, 65, 66, 67; KMP türleri 55-58 |
| diğer 4xx | yeniden deneme yok, `client_error:<code>` |
| 5xx | `max(server backoff, client delay)` sonra yeniden dene, `server_error:<code>` |
| diğer | `global_error:<code>` |

7 günden eski geçici hatalar (`first_transient_server_failure_timestamp` > 604 800 000 ms) fatal'a yükselir. Diğer fatal olmayan nedenler: `network_error`, `sqlite_full`, `unexpected_error`, `mms_local_io`, `mms_upload`.

---

## 4. Protobuf mesajları

Numaralar 2.26.41.6 sınıflarından çıkarıldı, bildirim sırasına ve mevcut olduğunda üretilen `*_FIELD_NUMBER` sabitlerine karşı kontrol edildi (`*`).

| Mesaj (sınıf) | Alanlar (numara) |
|-----------------|-----------------|
| `SyncdPatch` (`C49631LsW`, lite `Lp6`) | version **1** `SyncdVersion{uint64=1}`, mutations **2**, externalMutations **3** `ExternalBlobReference`, snapshotMac **4**, patchMac **5**, keyId **6** `KeyId{bytes id=1}`, exitCode **7** `ExitCode{uint64 code=1; string text=2}`, deviceIndex **8**, clientDebugData **9** |
| `SyncdMutation` (`C49601Ls2`) | operation **1** (`SET`=0, `REMOVE`=1), record **2** |
| `SyncdRecord` (`C49610LsB`) | index **1** `SyncdIndex{bytes blob=1}` (index MAC), value **2** `SyncdValue{bytes blob=1}`, keyId **3** |
| `SyncdMutations` (`C49583Lrk`) | mutations **1** (harici patch gövdesi) |
| `SyncdSnapshot` (`C49617LsI`, lite `C49419Lob`) | version **1**, records **2**, mac **3**, keyId **4** |
| `SyncActionData` (`C49612LsD`) | index **1** (UTF-8 JSON string dizisi), value **2** `SyncActionValue` (`BD4`), padding **3** (her zaman boş), version **4** int32 |
| `ExternalBlobReference` (`C49439Lov`) * | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `AppStateSyncKeyShare` (`C25704B7n`) * / `AppStateSyncKey` (`C25764B9y`) * | keys **1** / keyId **1** (`B89{keyId=1}`), keyData **2** |
| `AppStateSyncKeyData` (`BB9`) * | keyData **1** (32 bayt), fingerprint **2**, timestamp **3** (ms) |
| `AppStateSyncKeyFingerprint` (`BBU`) * | rawId **1**, currentIndex **2**, deviceIndexes **3** |
| `AppStateSyncKeyRequest` (`C25703B7m`) * | keyIds **1** |
| `AppStateFatalExceptionNotification` (`C25763B9x`) * | collectionNames **1**, timestamp **2** |
| `SyncDCollectionFatalRecoveryRequest` | collectionName **1**, timestamp **2** |
| `SyncDSnapshotFatalRecoveryResponse` | collectionSnapshot **1**, isCompressed **2** |
| `SyncdSnapshotRecovery` (`C49432Loo`) * / `SyncdPlainTextRecord` (`C49416LoY`) * | version **1**, collectionName **2**, mutationRecords **3**, collectionLthash **4** / value **1** `SyncActionData`, keyId **2**, mac **3** |
| `KeyExpiration` (`B8Y`) | expiredKeyEpoch **1** |
| `SyncActionValue` (`BD4`) * | timestamp **1** (int64; bunsuz bir SET başarısız olur), action başına bir alan (10.1) |

Taşıyıcılar (found, `*`): `ProtocolMessage` (`BD3`) `appStateSyncKeyShare` alan **7** / tip **6**, `appStateSyncKeyRequest` alan **8** / tip **7**, `appStateFatalExceptionNotification` alan **10** / tip **10** (`EnumC26463Bdz`). `PeerDataOperationRequestMessage.syncdCollectionFatalRecoveryRequest` alan **7**, istek tipi `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` = **8** (`EnumC26460Bdv`); yanıt `syncdSnapshotFatalRecoveryResponse` alan **8** (`C25828BCm`). Companion client-props (`C43107IrI`): `isSyncdPureLidSession` **2**, `isSyncdSnapshotRecoveryEnabled` **3**. Dahili FMessage numaraları: anahtar paylaşımı **38**, anahtar isteği **39**, fatal bildirimi **50**. Paylaşım ve istek tek bir `DeviceJid`'e peer mesajı olarak gider (`SendPeerMessageJob`), paylaşım önceliği `high`.

---

## 5. Mutasyon anahtarları ve kayıt şifreleme

### 5.1 Anahtar türetme (found, `MhX`, `C52959NkE` içinde aynı)

```
expanded = HKDF-SHA256(ikm = keyData(32), salt = 32 × 0x00, info = "WhatsApp Mutation Keys", L = 160)
```

| Baytlar | `MhX` alanı | Kullanım |
|-------|-------------|-----|
| 0-31 | `A00` | index anahtarı, HMAC-SHA256 |
| 32-63 | `A03` | value şifreleme anahtarı, AES-256-CBC |
| 64-95 | `A04` | value MAC anahtarı, HMAC-SHA512 |
| 96-127 | `A02` | snapshot MAC anahtarı, HMAC-SHA256 |
| 128-159 | `A01` | patch MAC anahtarı, HMAC-SHA256 |

HKDF `AbstractC38961i0.A00`'dır: extract = `HMAC-SHA256(32 zero bytes, ikm)`, expand RFC 5869'a göre. `C17930kd` `MhX` nesnelerini önbelleğe alır (5 giriş, inferred). Sync anahtarı rastgeledir (bölüm 7), Signal anahtarlarından türetilmez.

### 5.2 Bir mutasyonu şifreleme (found, `KmpSyncdEncryptor`, `C52959NkE`)

```
index    = JSON string array, element 0 = action wire name, e.g. ["mute","<jid>"]
plain    = SyncActionData{ index = UTF8(index), value = SyncActionValue, padding = "", version }
iv       = SecureRandom(16)
ct       = AES-256-CBC/PKCS5(valueEncKey, iv, plain)
aad      = op ‖ keyId(6)                 op: 0x01 SET, 0x02 REMOVE
valueMac = HMAC-SHA512(valueMacKey, aad ‖ iv ‖ ct ‖ len8)[0..32)      len8 = 8-byte big-endian aad length (7)
indexMac = HMAC-SHA256(indexKey, UTF8(index))
record   = SyncdRecord{ index.blob = indexMac, value.blob = iv ‖ ct ‖ valueMac, keyId }
```

Padding uzunluğu `max(0, −indexLen − valueLen)`'dir, her zaman boş. Minimum blob 48 bayt. SET→0x01, yerel işlem sabitinin SET için 0 olduğunu varsayar (inferred; wire SET=0). Bir REMOVE'un value içeriği boş kabul edilir (inferred, `mqt != null` dalı).

### 5.3 Şifre çözme (found, `KmpSyncdDecryptor`)

| Adım | Kontrol | Hata |
|------|-------|---------|
| 1 | `iv = [0..16)`, `ct = [16..n−32)`, `mac = [n−32..n)` olarak böl | `Cipher text too short` |
| 2 | anahtarı `record.keyId` ile çöz | anahtar hataları (7.2) |
| 3 | value MAC'i yeniden hesapla, karşılaştır | `Data MAC mismatch` (`DecryptionFailed`) |
| 4 | AES-CBC çöz, `SyncActionData` ayrıştır | `ActionDataProtobufDeserializationFailed` |
| 5 | index, version, (SET için) value ve timestamp mevcut | `MISSING_INDEX`, `MISSING_VERSION`, `MISSING_VALUE`, `MISSING_ACTION_TIMESTAMP` |
| 6 | index bir JSON `String[]`, boş değil, boş eleman yok | `keyArray length should have action name` |
| 7 | index MAC'i index string'i üzerinden yeniden hesapla | `Index MAC mismatch` |

Value MAC şifre çözmeden önce, index MAC en son kontrol edilir. Action daha sonra element 0 ile çözümlenir (`Unknown mutation name:`).

---

## 6. LT-Hash, snapshot MAC ve patch MAC

**LT-Hash** (found, `AbstractC50511MVx`, `KmpLtHash16`): 128 bayt, 64 little-endian u16 şerit olarak okunur; boş = 128 sıfır bayt.

```
expanded(valueMac) = HKDF-SHA256(ikm = valueMac(32), salt = 32 × 0x00, info = "WhatsApp Patch Integrity", L = 128)
lane'[i]           = (lane[i] ± expanded[i]) mod 2^16         + add, − subtract
```

Gelen güncelleme (`KmpSyncdCryptoHelper.A01`): patch'teki her index için mevcut kaydın saklanan `mutation_mac` değerini **çıkar**, ardından SET'lerin value MAC'lerini **ekle**. `checkLtHashConsistency` (`C17520jx`) hash'i saklanan tüm `mutation_mac` değerlerinden yeniden oluşturur ve saklanan hash ile karşılaştırır (`ltHashFromMutations` / `ltHashFromDb` loglar, flag **624** yoksa son 16 hex karakter); flag **1104** saat dolduğunda günlük cron'dan (varsayılan 0 = kapalı) ve flag **1783** ile bir snapshot-MAC uyuşmazlığından sonra çalışır.

**MAC'ler** (found):

```
version8    = 8-byte big-endian version
snapshotMac = HMAC-SHA256(snapshotMacKey, ltHash(128) ‖ version8 ‖ UTF8(collection))
patchMac    = HMAC-SHA256(patchMacKey,   snapshotMac ‖ valueMac₁ ‖ … ‖ valueMacₙ ‖ version8 ‖ UTF8(collection))
```

`valueMacᵢ` = her value blob'unun son 32 baytı, patch sırasına göre. Giden: her iki MAC için version = saklanan + 1 (`C50707Mbo(old + 1)`). Gelen patch MAC'i, patch'in taşıdığı `snapshot_mac` değerini kullanır; yeniden hesaplanan snapshot MAC ayrıca karşılaştırılır.

| Gelen kontrol | Uyuşmazlık |
|----------------|----------|
| patch MAC | fatal `MacMismatchPatch` (32) |
| snapshot içindeki snapshot MAC | fatal `SnapshotMacMismatchInSnapshot` (52) |
| patch içindeki snapshot MAC | KMP yolunda **fatal değil**: `snapshot mac mismatch but do not throw fatal`, fatal olmayan rapor kodu 60, isteğe bağlı tutarlılık kontrolü (**1783**); dönen flag'in tüketicisi çözümlenmedi |
| eksik `snapshot_mac` / `patch_mac` | fatal `MissingSnapshotMac` (39) / `MissingPatchSnapshotMac` (40) / `MissingPatchMac` (41) |

---

## 7. Sync anahtarları

### 7.1 Anahtar, üretim, aktif anahtar (found)

| Öğe | Değer |
|------|-------|
| Anahtar id'si (`CGH`) | 6 bayt: `deviceId` (2, BE) ‖ `epoch` (4, BE); `SyncdKeyId{deviceId=, epoch=}` |
| Anahtar verisi | 32 rastgele bayt |
| Tablo `crypto_info` | `device_id, epoch, key_data, timestamp, fingerprint, stale_timestamp` |
| Parmak izi | oluşturma anında hesabın ADV anahtar-index durumunun `rawId`, `currentIndex`, `deviceIndexes` değerleri |
| Üretim (`C12800bm.A05`) | `epoch = max(stored max, in-memory) + 1` (0 ise önce [0,65536) aralığında rastgele); yalnızca yolda yeni üretilmiş bir paylaşım yoksa; başka cihaz yoksa anahtar hemen kaydedilir, aksi halde her companion'a bir paylaşım (peer 38, `isNewlyGeneratedKey=true`) gider ve anahtar o mesaj **gönderildikten** sonra kalıcı kaydedilir (`CXB.Bss`) |
| Aktif anahtar | en son `crypto_info` satırı, **14488** günden (varsayılan 30) genç ve parmak izi geçerli, aksi halde bir sonraki yazmada yeni anahtar üretilir |
| Parmak izi kontrolü (`A0B`) | `rawId` yerel ADV raw id'ye eşit; `deviceIndexes ∪ (currentIndex+1 … local currentIndex)` yerel device-index kümesine eşit; aksi halde `one of a peer device is no longer registered` |
| Sentinel (`sentinel`, `KeyExpiration`) | `C25048AqM.A00` koleksiyon başına (beşi de) bir tane oluşturur, `expiredKeyEpoch` = en yüksek yerel epoch |
| `expireKeysWithEpochIfActive` (`A08`) | epoch'u verilen epoch'a eşit veya küçükse en son anahtarda `timestamp = 0` yapar; sentinel alındığında çağıran izlenmedi (inferred) |
| Eskimiş anahtarlar | günlük cron, `syncd_mutations` tarafından referans verilmeyen anahtarları işaretler, **14496** gün sonra siler (varsayılan 31) |
| Yeniden anahtarlama | farklı bir anahtar altında saklanan kayıt `findMutationWithExpiredKey` ile değiştirilir; tam REMOVE+SET biçimi inferred |

### 7.2 İstek ve eksik anahtarlar (found, `C12800bm.A07`)

1. Bilinmeyen anahtar id'leri `missing_keys(device_id, epoch, collection_name)` içinde saklanır ve diğer tüm kayıtlı cihazlara anahtar-isteği peer mesajlarıyla (tip 39) istenir; zaten bekleyen id'ler atlanır (`missing_key_counter`).
2. Yanıtlayan, sahip olduğu anahtarlar için bir paylaşım gönderir (`A0C`, `isNewlyGeneratedKey=false`).
3. **14492** gün yanıtsız kalırsa (varsayılan 7, en eski tip-39 peer mesajı, günlük cron) → fatal **31** (`TimeoutWhileWaitingForMissingKey`).
4. Kimse sağlayamıyorsa: `MissingKeyOnAllClients`; sorulacak kimse yoksa: `RequestingMissingKeyWithNoClients`; şifreleme için hiç yoksa: `MissingActiveKeyForEncryption`.

Paylaşımlar uçtan uca şifreli peer mesajlarının `ProtocolMessage` payload'larıdır (found). Gelen bir paylaşımın alıcı tarafındaki parmak izi doğrulaması bulunamadı (unknown).

---

## 8. Giden patch'ler ve harici blob'lar

**Oluşturma** (found, `OutgoingProcessor`, `KmpSyncdEncryptionProcessor`): bekleyen mutasyonlar (`pending_mutations`, `is_ready_to_sync=1`) koleksiyon başına bölünür; bir patch içinde tekrarlanan index reddedilir (`SameIndexForMultipleMutationsInOutgoingPatch`); aktif anahtar çözümlenir; her mutasyon şifrelenir (5.2); saklanan hash'ten yeni LT-Hash (6); saklanan + 1 sürümüyle `snapshotMac` / `patchMac`; `SyncdPatch{version, mutations | externalMutations, snapshotMac, patchMac, keyId, deviceIndex?, clientDebugData?}`; IQ (3.1); sonuç yeni sürümü taşır. `deviceIndex` (alan 8) varsayılanı true olan flag **14486** ile yönetilir (tüketici izlenmedi).

**Harici yükleme kuralı** (found, `OutgoingProcessor`): `(mutationCount > P14494 or bytes > P14495 × 1024) and bytes > P5097 × 1024`, varsayılanlar 100 / 10 / 0; yani 100 mutasyonu veya yaklaşık 10 KB'ı aşan her patch harici gider. Blob bir `SyncdMutations` mesajıdır; patch bu durumda `externalMutations` taşır ve satır içi `mutations` taşımaz (ikisinin birden bulunması reddedilir: `PatchWithBothInlineAndExternalMutations`). Yükleme hataları: `Upload transient network error`, `Upload local I/O failure`, `Upload failed`.

**Blob taşıma** (found, `C17650kB`, `C49831Lvs`, `C15530gU`):

| Öğe | Değer |
|------|-------|
| Medya tipi / media-key HKDF info | `md-app-state` (MMS yolu `mms`) / `WhatsApp App State Keys` |
| Zorunlu referans alanları | mediaKey, directPath, fileSha256, fileEncSha256 (her biri eksikse → `MissingExternalBlobReference*`) |
| İndirme durumu | 5 = süresi dolmuş (`ExternalPatchExpired` 3 / `SnapshotExpired` 49, fatal); geçici durumlar yeniden denenir; diğerleri fatal |
| İçerik | harici patch → `SyncdMutations`; snapshot → `SyncdSnapshot` |

Ortak media-key genişletme düzeni burada yeniden okunmadı (ortak olduğu inferred).

**Debug verisi** (found): `clientDebugData` = `PatchDebugData` (`C49633LsY`: `collection_name`, `current_lthash`, `new_lthash`, `new_lthash_subtract`, `patch_version`, `number_add/remove/override`, `sender_platform`, `is_sender_primary`, `first_four_bytes_from_a_hash_of_snapshot_mac_key`), yalnızca flag **6614** ile yazılır (varsayılan false); alıcı bunu patch-MAC uyuşmazlığından sonra loglar.

---

## 9. Gelen patch'ler ve snapshot'lar

| # | Kontrol (found) | Hata: KMP türü (id) / eski kod |
|---|---------------|--------------------------------------|
| 1 | patch'te `version` var | `MissingPatchVersion` (7) / 8 |
| 2 | bir yanıtta yinelenen sürüm yok | `DuplicatePatchVersionInCollection` (8) / 9 |
| 3 | hem satır içi hem harici mutasyon yok | `PatchWithBothInlineAndExternalMutations` (13) / 14 |
| 4 | `version == stored + 1` (`verifyCollectionVersion`) | `ServerDidNotSendAllPatches` (64) |
| 5 | patch `exit_code` mevcut | eski 36 (kod 100), 37 (101), 38 (diğer); KMP karşılığı çözümlenmedi |
| 6 | tüm mutasyonların şifresini çöz (5.3) | `DecryptionFailed` (6), biçim türleri |
| 7 | SET'ler veya REMOVE'lar arasında tekrarlanan index yok | `SameIndexForMultipleMutationsInPatch` (5) |
| 8 | index'ler arası bağımlılık döngüsü | `CyclicMutationDependencyInPatch` (37) |
| 9 | LT-Hash, patch MAC, snapshot MAC'i yeniden hesapla (6) | `MacMismatchPatch` (32) / fatal değil |
| 10 | action handler başına uygula (SQLite), sürümü + hash'i sakla | loglar `Cyclic mutation dependency`, `SQLite error` |

Snapshot'lar: yalnızca bootstrap yapan bir companion snapshot alır (`Only companion devices that are undergoing bootstrap should receive and handle snapshots`). Blob'u indir, kayıtların şifresini patch mutasyonları gibi çöz, tekrarlanan index'leri reddet (`SameIndexForMultipleMutationsInSnapshot`, 59), hash'i yeniden oluştur, `snapshot.mac` ile karşılaştır; ardından `has_more_patches` patch'lerini uygula. `applySnapshot keyMap contains null value, retry` anahtarları yeniden ister. Yetim mutasyonlar (üst chat eksik) `are_dependencies_missing=1` ile saklanır, `chat_jid` ile indekslenir ve daha sonra yeniden uygulanır (`SyncdCrossIndexDependencyUtil`).

---

## 10. Sync action tipleri

### 10.1 Katalog (found, `EnumC24865AnN` + `AbstractC24863AnL.A00`)

Numara = value'nun `SyncActionValue` alanı; `-` = `BD4` içinde eşleşen sabit yok (value alanı bilinmiyor). Index element 0 wire adıdır; diğer elementler action'a özgüdür ve sıralanmamıştır.

| Koleksiyon | Wire adı = alan |
|------------|-------------------|
| `critical_block` (4) | `setting_securityNotification` -, `setting_pushName` 7, `setting_locale` 16, `generated_wui` 52 |
| `critical_unblock_low` (2) | `contact` 3, `lid_contact` 61 |
| `regular_high` (19) | `star` 2, `mute` 4, `deleteMessageForMe` 18, `clearChat` 21, `deleteChat` 22, `userStatusMute` 29, `ugc_bot` 43, `status_privacy` 44, `favorites` 56, `waffle_account_link_state` 58, `ctwaPerCustomerDataSharing` 62, `maiba_ai_features_control` 68, `status_post_opt_in_notification_preferences_action` 71, `private_processing_setting` 74, **`nct_salt_sync` 80**, `biz_ai_settings_nudge` 87, `wasa_root_secret` 89, `shared_device_allowlist` 94, `ai_thread_delete` - |
| `regular` (35) | `quick_reply` 8, `label_message` -, `label_edit` 14, `label_jid` 15, `primary_feature` 24, `deviceAgent` 27, `subscription` 28, `agentChatAssignment` 35, `agentChatAssignmentOpenedStatus` 36, `pnForLidChat` 37, `marketingMessage` 38, `marketingMessageBroadcast` 39, `external_web_beta` 40, `setting_relayAllCalls` 41, `call_log` 42, `delete_individual_call_log` 46, `label_reordering` 47, `setting_disableLinkPreviews` 53, `usernameChatStartMode` 59, `notificationActivitySetting` 60, `setting_channels_personalised_recommendation_optout` -, `broadcast_jid` -, `detected_outcomes_status_action` 66, `business_broadcast_list` 69, `music_user_id` 70, `avatar_updated_action` 72, `galaxy_flow_action` -, `newsletter_saved_interests` 75, `business_broadcast_campaign` 81, `business_broadcast_insights_sync` 82, `subscriptions_sync_v2` 84, `label_sublist` 91, `ctwa_message_received` 93, `shareOwnPn` -, `broadcast` - |
| `regular_low` (36) | `pin_v1` 5, `recent_emoji_weights_action` 11, `archive` 17, `sentinel` 19, `markChatAsRead` 20, `setting_unarchiveChats` 23, `android_unsupported_actions` 26, `time_format` 30, `nux` 31, `primary_version` 32, `favoriteSticker` 33, `removeRecentSticker` 34, `bot_welcome_request` 45, `payment_info` 48, `custom_payment_methods` 49, `lock` 50, `setting_chatLock` 51, `device_capabilities` 54, `note_edit` 55, `merchant_payment_partner` 57, `payment_tos` 63, `ai_thread_rename` 76, `interactive_message_action` 77, `settings_sync` 78, `out_contact` 79, `customer_data` 83, `thread_pin` 85, `setting_autoOrganizeBusinessChat` 86, `coexV2Version` 88, `lock_message` 90, `device_capabilities_v2` 92, `contact_manager_metadata` 95, `business_folder_activation` 96, `group_history_toggle` 97, `bb_pro_pending_customer_base_action` 98, `community_nesting_state` 99 |

`BD4` içinde 6, 9, 10, 12, 13, 25, 65, 67, 73 alan numaraları için sabit yoktur. Amaç grupları (adlardan inferred): chat durumu (`mute`, `pin_v1`, `thread_pin`, `archive`, `markChatAsRead`, `clearChat`, `deleteChat`, `deleteMessageForMe`, `star`, `lock*`); etiketler (`label_*`); kişiler (`contact`, `lid_contact`, `out_contact`, `pnForLidChat`, `shareOwnPn`); hesap ayarları (`setting_*`, `time_format`, `status_privacy`); anahtarlar ve token'lar (`sentinel`, `nct_salt_sync`, `wasa_root_secret`, `generated_wui`, `shared_device_allowlist`); business, AI, aramalar, ödemeler (geri kalanı).

### 10.2 Seçilmiş değerler (found)

| Action | Değer |
|--------|-------|
| `nct_salt_sync` (ordinal 73, `regular_high`) | `SyncActionValue` alan **80** içinde `NctSaltSyncAction{bytes salt=1}`; birincil cihazın NCT salt'ı companion'lara iletme yolu, kaynağı ve kullanımı `WA_TCTOKEN_CSTOKEN.md` (3.2) içinde |
| `contact` (`ContactAction`) | fullName 1, firstName 2, lidJid 3, saveOnPrimaryAddressbook 4, pnJid 5, username 6, birthday 7; yalnızca birincil cihaz oluşturur, bu yüzden bootstrap yapan bir companion adres defterini herhangi bir `regular*` koleksiyondan önce alır |
| `mute` (`MuteAction`) | muted 1, muteEndTimestamp 2, autoMuted 3, muteEveryoneMentionEndTimestamp 4 |
| `sentinel` | `KeyExpiration{expiredKeyEpoch}` (7.1) |
| `android_unsupported_actions` (26), flag **14490** (varsayılan false) | bir "Android unsupported mutation" yolu; semantiği bilinmiyor |

---

## 11. Fatal hatalar, yeniden deneme ve kurtarma

### 11.1 KMP fatal türleri (found, `Lx6.A00`; id'ler dahilidir, wire değeri değildir)

| Grup | Id'ler ve adlar |
|-------|---------------|
| Taşıma | 53 `XmppBadRequestForCollection`, 54 `…NotFoundForCollection`, 55 `XmppBadRequestGlobalError`, 56 `…NotFoundGlobalError`, 57 `…BadMethodGlobalError`, 58 `…NotAcceptableGlobalError` |
| Patch / snapshot biçimi | 4 `MissingOrEmptyIndex`, 5 `SameIndexForMultipleMutationsInPatch`, 7 `MissingPatchVersion`, 8 `DuplicatePatchVersionInCollection`, 13 `PatchWithBothInlineAndExternalMutations`, 37 `CyclicMutationDependencyInPatch`, 38 `MissingSnapshotVersion`, 47 `MissingPatchKeyId`, 50 `MissingSnapshotKeyId`, 59 `SameIndexForMultipleMutationsInSnapshot`, 64 `ServerDidNotSendAllPatches`, 65 `ServerSentEarlierPatch`, 71 `InvalidSnapshotRecords` |
| Mutasyon / action biçimi | 10-12, 14-16, 19-24 (`MissingMutationVersion/Value/Index/Operation/Record/KeyId`, `MissingActionIndex/Value/Version/Timestamp`, `InvalidMutationIndex`, `InvalidActionIndex`) |
| Kripto | 6 `DecryptionFailed`, 9 `EncryptionFailed`, 31 `MacMismatchSnapshot`, 32 `MacMismatchPatch`, 39-41 `Missing*Mac`, 51 `SnapshotMacMismatchInPatch`, 52 `SnapshotMacMismatchInSnapshot` |
| Anahtarlar | 29 `MissingKeyOnAllClients`, 30 `TimeoutWhileWaitingForMissingKey`, 46 `InvalidKeyShareKeyId`, 48 `InvalidKeyShareKeyData`, 62, 66-69 (`RequestingMissingKeyWithNoClients`, `MissingKeyForMutationInLocalSnapshot`, `MissingActiveKeyAfterRotation`, `MissingActiveKeyForEncryption`, `MissingCurrentEpochForActiveKeyValidation`) |
| Blob'lar / protobuf | 3 `ExternalPatchExpired`, 49 `SnapshotExpired`, 42-45 ve 72 `MissingExternalBlobReference*`, 60 / 61 referans / snapshot ayrıştırma hatası, 17 / 18 / 25-28 (de)serileştirme türleri, 34-36 `TerminalPatch*` |
| Yerel | 33 `DbStoreNotReady`, 63 `DbStoreNotReadyLowDiskSpace`, 70 `SameIndexForMultipleMutationsInOutgoingPatch` |

### 11.2 Eski sayısal kodlar (found, `C49784Lv2.errorCode`, WAM `md_fatal_error` besler; ayrı numaralandırma)

8 / 9 / 14 (`N90`: sürüm yok / yinelenen sürüm / satır içi + harici), 18 / 69 (patch / snapshot ayrıştırma hatası), 36 / 37 / 38 (`exit_code` 100 / 101 / diğer), 64-67 (global IQ hataları 400 / 404 / 405 / 406), 71 (eksik anahtar isteğinden sonra anahtar çözümleme başarısız), 31 (anahtar bekleme zaman aşımı), 60 (patch içinde fatal olmayan snapshot-MAC uyuşmazlığı, `A0F(60, collection, false)`). KMP türleriyle eşleme çözümlenmedi.

### 11.3 Fatal hataya tepki (found, `SyncResponseHandler.A08`, `C12440bB.A0S/A0Q`)

| Rol | Eylem |
|------|--------|
| Hepsi | `app-state-sync-handle-fatal-exception` logla, WAM `md_fatal_error`, çalışan sync'i temizle |
| Flag **25799** | companion: `companion_syncd_dirty=true`; birincil: `C17630k8.A01(1)` (dirty nedeni 1, inferred) |
| Birincil | `A0Q(1)` tüm syncd verisini siler. Dirty makinesi (`C17630k8`, `A0Q`'dan zincir inferred): 4'e kadar `syncd_dirty` sayacı, `syncd_dirty_reason`, `<iq xmlns="w:sync:app:state" type="set"><delete_all_data/></iq>` (type özniteliği inferred), `logoutAllCompanionDevices` |
| Companion | `companion_syncd_dirty=true`, birincil cihaza (device 0) peer mesajı `AppStateFatalExceptionNotification` (FMessage 50), 5 sn bekleme, `syncd_failure` veya `syncd_error_during_bootstrap` ile logout |

Tümünü silme yeniden deneme penceresi **14493** dakika (varsayılan 360). Bir companion kaydı silindiğinde ve hiçbiri kalmadığında birincil cihaz temizlik yapar (`shouldCleanUpSyncd`).

### 11.4 Snapshot kurtarma (found, `KmpSyncdFatalErrorRecovery`)

client-prop `isSyncdSnapshotRecoveryEnabled` ile kapılanır. Companion, `SyncDCollectionFatalRecoveryRequest{collectionName}` ile peer data işlemi `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` (8) gönderir. Yanıtlayan, saklanan **düz metin** mutasyonlarından (`syncd_mutations`, `collection_versions.version / lt_hash`) bir `SyncdSnapshotRecovery` oluşturur, gzip'ler ve `SyncDSnapshotFatalRecoveryResponse` olarak döndürür. Redler: `Invalid collection name` (`critical_block` için istek), `Collection version/ltHash invalid`, `Snapshot keyId invalid`, `Mutation count (…) more than the limit`, `Mutation snapshot data size (…) more than the limit`, `Error encoding mutation data`, `Compression failed` (sınır props'ları çözümlenmedi). Düz metin, uçtan uca şifreli bir peer mesajının içinde taşınır. Companion tarafındaki uygulama izlenmedi (unknown).

---

## 12. Yerel durum ve feature flag'ler

| Depo | İçerik (found) |
|-------|-----------------|
| `syncd_mutations` | `mutation_index` (benzersiz), `mutation_value`, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name` |
| `collection_versions` / `pending_mutations` / `missing_keys` / `crypto_info` | `collection_name, version, lt_hash` / giden kuyruk (`is_ready_to_sync`) / anahtar istekleri / sync anahtarları |
| Prefs | `syncd_bootstrap_state`, `companion_syncd_critical_bootstrap_state`, `syncd_dirty`, `syncd_dirty_reason`, `companion_syncd_dirty`, `syncd_last_companion_dereg_time`, `syncd_last_lthash_consistency_check_time`, `first_transient_server_failure_timestamp` |

Günlük cron (`C46413KPv`) şu sayaçları raporlar: `mutation_counter`, `invalid_action_counter`, `upload_conflict_counter`, `unsupported_action_counter`, `cross_index_conflict_counter`, `unset_action_mutation_counter`, `key_rotation_remove_counter`, `missing_key_counter`.

| Flag ID | Tip / varsayılan | Kontrol ettiği |
|---------|-----------------|----------|
| **15909**, **20682**, **18234** | bool / false | `XplatSyncdEncryptionManager` ve varsayılan (`AbstractC17550k0`); KMP gelen (`RunnableC53542Nwj`); KMP giden (`C12440bB`). Yalnızca derleme varsayılanları, canlı değer bilinmiyor. 15909'un önceki derlemedeki adı: `KMP_SYNCD_ENGINE_CRYPTO_ENABLED` (ID yeniden kullanımı inferred) |
| **14488** / **14496** / **14492** | int / 30 / 31 / 7 | aktif anahtar yaşı, eskimiş anahtar saklama süresi, anahtar bekleme zaman aşımı (gün) |
| **14493** | int / 360 | tümünü silme / dereg penceresi (dakika) |
| **14494**, **14495**, **5097** | int / 100, 10, 0 | harici patch eşikleri |
| **14497** | int / 1000 | DB mutasyon yükleme sınırı (inferred) |
| **1104** / **1783** | int 0 / bool false | tutarlılık kontrolü aralığı (saat) / snapshot-MAC uyuşmazlığından sonra kontrol |
| **6614** | bool / false | patch'lerde `clientDebugData` |
| **25799** | bool / false | fatal hatada dirty-durum işleme |
| **27528** | bool / false | birincil cihazda anahtar yoksa anahtar üret |
| **14486** | bool / true | patch'lerde `deviceIndex` (tüketici izlenmedi) |
| **14489**, **14490**, **1221**, **624** | int 90 / bool false / bool false / bool | `C15310g7` içindeki `min()` sınırı (çözümlenmedi) / unsupported-mutation yolu / mutasyon istatistikleri / loglarda tam hash'ler |

---

## 13. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-----|
| `Data MAC mismatch` | yanlış anahtar, kurcalanmış blob, AAD içinde yanlış op baytı veya keyId | anahtar `record.keyId` ile belirlenir; AAD = `op ‖ keyId`, op 1 SET / 2 REMOVE |
| `Index MAC mismatch` | index string'i bayt bayt farklı (JSON boşlukları) | `SyncActionData.index` içindeki tam UTF-8 string'in MAC'ini al |
| fatal 64 `ServerDidNotSendAllPatches` | patch sürümü ≠ saklanan + 1 | saklanan sürümden yeniden senkronize et; durum kaybolduysa snapshot iste |
| patch MAC uyuşmazlığı (32) | LT-Hash kayması, version8 genişliği, yanlış kaynaktan snapshot MAC | önce patch'in `snapshot_mac` değerini kullan; sürüm 8 baytlık big-endian |
| `PatchWithBothInlineAndExternalMutations` | iki alan da set edilmiş | birini gönder |
| `MissingActionTimestamp` | SET'te `SyncActionValue.timestamp` yok | alan 1'i set et |
| anahtar eksik | paylaşım alınmadı | tip-39 isteği; 7 gün sonra fatal 31 |
| `one of a peer device is no longer registered` | cihaz listesi anahtar oluşturulduğundan beri değişti | anahtar aktif anahtar olarak kullanılamaz; yenisini üret |
| IQ hatası 400 / 404 / 405 / 406 | hatalı istek biçimi, bilinmeyen koleksiyon | fatal; isteği düzelt |
| `ExternalPatchExpired` / `SnapshotExpired` | blob durumu 5 | snapshot kurtarma veya yeniden bağlama |
| companion logout `syncd_failure` | kurtarılamaz fatal hata | yeniden eşleştir veya etkinse snapshot kurtarma |

---

## 14. Temel ayrımlar

| Karıştırma | Şununla |
|----------------|------|
| Sync anahtarı (device+epoch başına 32 rastgele bayt) | mutasyon anahtarları (HKDF çıktısı, beş dilim) |
| Index MAC (index string'i üzerinde HMAC-SHA256) | value MAC (AAD + iv + ct + len üzerinde 32'ye kırpılmış HMAC-SHA512) |
| Value MAC (mutasyon başına) | snapshot MAC (LT-Hash + version + koleksiyon) ve patch MAC (snapshot MAC + tüm value MAC'ler) |
| `<snapshot>` node'u (bir `ExternalBlobReference`) | `SyncdSnapshot` proto'su (blob içeriği); aynı şekilde `externalMutations` ve `SyncdMutations` |
| Android'de `critical_block` (hesap ayarları) | bir engelleme listesi koleksiyonu (bulunmadı) |
| `ProtocolMessage` tipleri 6 / 7 / 10 | alan numaraları 7 / 8 / 10 |
| Peer data istek alanı 7 | peer data yanıt alanı 8 |
| KMP tür id'leri (`Lx6`) | eski `errorCode` int'leri |
| `sentinel` (beş koleksiyonun tümünde anahtar-süre-dolumu işaretçisi) | `primary_version`, `android_unsupported_actions` |
| WhatsApp Web action / koleksiyon tabloları | buradaki Android tablosu (96 action, farklı atama) |

---

## 15. Baileys (`baron-baileys-v2` 1.5.17)

Yalnızca `src/Utils/chat-utils.js`, `src/Socket/chats.js`, `src/Utils/process-message.js` içinde okunan olgular. Hiçbir şey bir sunucuya karşı test edilmedi; hiçbir hata iddia edilmiyor.

| Konu | Baileys | Android |
|-------|---------|---------|
| Anahtar genişletme, LT-Hash | native köprü `expandAppStateKeys`, `LTHashAntiTampering` (128 bayt); aynı beş dilim adı | 5.1, 6 |
| Value MAC | `HMAC-SHA512(op ‖ keyId ‖ data ‖ 8 bytes, last = len)[0..32)`, op 1 / 2 | aynı |
| Snapshot / patch MAC | aynı girdiler ve sıra; `ver8` yalnızca düşük 32 biti yazar | tam 64 bit big-endian |
| Index, padding | `JSON.stringify(index)`, boş padding | aynı |
| Harici blob | `downloadContentFromMessage(blob, 'md-app-state')` | aynı medya tipi |
| Koleksiyonlar | `critical_block, critical_unblock_low, regular_high, regular_low, regular` | aynı adlar |
| İstek node'u | özniteliksiz `<sync>`; `<collection name version return_snapshot>`, `return_snapshot` her zaman `'true'`/`'false'` | `data_namespace="3"`, `order`, `return_snapshot` yalnızca true olduğunda |
| Patch gönderme | `version = state.version − 1`, `return_snapshot='false'` | saklanan sürüm |
| Sürüm sürekliliği | kontrol edilmez (`newState.version = patchVersion`); eksik patch sürümü koleksiyon sürümü + 1 olur | saklanan + 1'e eşit olmalı |
| Patch içindeki snapshot MAC | yeniden hesaplanır, `failed to verify LTHash` fırlatır | KMP yolunda fatal değil |
| Anahtar paylaşımı | base64 anahtar id'si başına yalnızca `keyData` saklar; `myAppStateKeyId` = mesajdaki son anahtar | parmak izi ve timestamp'i tutar, parmak izini doğrular, en son geçerli anahtarı seçer |
| Fatal bildirimi | loglanır, `app-state.sync-error` olarak yayınlanır | companion gönderir, birincil cihaz harekete geçer |
| Yeniden deneme | `MAX_SYNC_ATTEMPTS = 2`, zorunlu-snapshot yeniden denemesi, eksik anahtar koleksiyonu park eder | bölüm 11 |
| NCT salt | `nctSaltSyncAction.salt` `nct-salt` olarak saklanır | 10.2 |

Baileys kaynağında bulunmayanlar: `data_namespace`, `order`, `exit_code` işleme, snapshot kurtarma. Sunucudaki etkisi bilinmiyor.

---

## 16. Tam akışlar

### 16.1 Birincil cihaz bir değişiklik yazar (örnek `mute`)

```
[User]  → handler builds mutation  ["mute","<chatJid>"]  MuteAction  collection regular_high
     │
     ▼
[SyncManager C12440bB]  pending_mutations ; active key (≤ 30 d, fingerprint ok) else generate, share (peer 38)
     │
     ▼
[Encrypt]  iv ; AES-CBC ; aad = 01 ‖ keyId ; valueMac ; indexMac
     │     ltHash' = ltHash − oldValueMac + newValueMac ; ver = stored + 1 ; snapshotMac ; patchMac
     │     SyncdPatch inline, or externalMutations above the thresholds (md-app-state upload)
     ▼
iq set w:sync:app:state  <sync data_namespace=3><collection name order version><patch/></collection></sync>
     │
     ▼
[WA Server]  (not observed) orders patch, assigns version
     │
     ▼
Result <collection name version="N+1"/>  →  store version, hash, mutation_mac
     │
     ▼
[Companions]  sync (16.2)
```

### 16.2 Companion çeker

```
[Companion]  iq set  <collection name version=V [return_snapshot=true if V=0]/>
     │
     ▼
Result <collection has_more_patches?> [<snapshot ExternalBlobReference/>] <patches><patch/>…</patches>
     │
     ├─ snapshot ─► download md-app-state ─► SyncdSnapshot ─► decrypt ─► hash ─► snapshot MAC
     └─ each patch (V+1 …) ─► version check ─► external blob? download SyncdMutations
            │  key unknown ─► missing_keys + peer 39 ─► [Primary] peer 38 share
            │  decrypt (valueMac → AES → SyncActionData → indexMac) ; ltHash − old + new
            │  patchMac ; snapshotMac ; action handler apply (are_dependencies_missing for orphans)
            ▼
         store version, hash ; has_more_patches → repeat
```

### 16.3 Fatal hata

```
[Companion]  patch MAC mismatch / key timeout / version gap
     ├─ recovery enabled ─► peer data op 8 {collectionName} ─► [Primary] SyncdSnapshotRecovery (gzip)
     └─ else companion_syncd_dirty ; peer AppStateFatalExceptionNotification ; 5 s ; logout syncd_failure
               ▼
         [Primary]  delete syncd data ; iq <delete_all_data/> ; logout companions ; re-pair
```

---

## 17. Bilinmeyenler

| Öğe | Durum |
|------|--------|
| Hesap başına aktif motor (eski veya KMP) | sunucu flag'leri |
| `order` özniteliğinin anlamı | unknown |
| Gelen bir anahtar paylaşımının alıcı tarafı parmak izi kontrolü | bulunamadı |
| Alınan bir `sentinel`'in uygulama tarafı (`expireKeysWithEpochIfActive`) | izlenmedi |
| KMP türü ↔ eski kod eşlemesi; `ServerSentEarlierPatch` tetikleyicisi; `exit_code` 100 / 101 anlamı | çözümlenmedi |
| `-` ile işaretli 9 action'ın value alanı | unknown |
| Snapshot kurtarma uygulama tarafı, sınır props'ları | izlenmedi |
| Sunucu sıralaması, saklama, birleştirme kuralları | sunucu tarafı |
| Trafik | hiçbir şey yakalanmadı |
