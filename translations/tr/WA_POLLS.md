<!-- src-sha1: 287eecdda43f9253685bac27a2f3bea697aa3989 -->
# WhatsApp Anketler — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** anket mesajı ailesi (`pollCreationMessage`'dan `pollCreationMessageV6`'ya, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), sürüm geçmişi ve gönderme/alma seçim mantığı, oluşturma doğrulaması ve limitler, görüntü-anketi seçenek bağlama, oy seçimi ve gizlilik modeli, çoklu-seçim vs tekli-seçim, anket düzenleme, iletme-zamanı sonuç snapshot'ı, feature flag'leri

---

## 1. Bu ne

Bir anket, bir soru, bir seçenek listesi, bir seçim üst sınırı ve opsiyonel quiz/bitiş-zamanı/görünürlük ayarları taşıyan bir `Message` alt-nesnesidir (`PollCreationMessage`, altı versiyonlu üst-seviye alan boyunca değişmeden yeniden kullanılır). Oylar (`pollUpdateMessage`), eklenen seçenekler (`pollAddOptionMessage`) ve düzenlemeler (`secretEncryptedMessage`), oluşturma mesajının id'sine bağlı ve onun mesaj-başına sırrından key'lenmiş ayrı takip mesajlarıdır; bu şifreleme (HKDF kullanım senaryoları, AES-GCM, AAD, identity retry) [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)'de ele alınır ve burada tekrarlanmaz. Bu rapor mesaj-tipi katmanını kapsar: hangi alanın neyi taşıdığı, istemcinin bunlar arasında nasıl seçim yaptığı, doğrulama ve limitler, ve anket-özgü handler'ların çözülmüş payload'larla ne yaptığı. Tüm bulgular decompile edilmiş 2.26.41.6 APK'sının statik analizidir (`java_src/` altındaki Java kaynakları, artı `res/values/strings.xml`); hiçbir şey wire üzerinde yakalanmamıştır. Kademeler: **found** = kod/kaynaklarda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi.

| Varlık | `Message`'daki alan | Proto tipi | Rol |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | orijinal oluşturma slotu |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | bir topluluk varsayılan-alt-grup sohbetinde oluşturma |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | düz-anket oluşturma slotu (sıradan anketler için mevcut varsayılan) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | bir iç `Message.pollCreationMessage`'ı (alan 49) saran forward-compat wrapper'ı |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | quiz oluşturma slotu |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | genişletilmiş-anket slotu (bitiş zamanı / oy-veren-adını-gizle / seçenek-eklemeye-izin-ver) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | bir görüntü-anketi seçeneği görüntüsü, `messageAssociation` ile gelecekteki ankete bağlanır |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | mevcut bir ankete bir seçenek ekler |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | oy (şifreli) veya oy metadata'sı |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | statik sonuç snapshot'ı, anket başka bir sohbete iletildi |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | aynısı, quiz varyantı (oy sayıları sıfırlanmış) |

Alan numaraları, yukarıdaki tabloya eşleşen tüm on bir `POLL_*_FIELD_NUMBER` sabitini deklare eden `C30628DTw`'ye (`Message` proto sınıfı) doğrudan karşı doğrulanmıştır.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Alanlar (found)

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | wire'da mevcut ama bu geçişte okunan handler'lar tarafından kullanılmıyor (oylar bu alanı değil, mesaj-başına `messageSecret`'ı kullanır; bkz [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | anket sorusu, maks 5000 karakter, gerekli |
| `options` | **3** | repeated `Option` | yanıt seçenekleri |
| `selectableOptionsCount` | **4** | uint32 | seçim üst sınırı, gerekli (§11) |
| `contextInfo` | **5** | `ContextInfo` | standart context |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | quiz doğru-cevap seçeneği, `pollType=QUIZ` olduğunda gerekli |
| `endTime` | **9** | int64 | anket kapanış zaman damgası (ms) |
| `hideParticipantName` | **10** | bool | "Oy verenlerin adını gizle" (§10) |
| `allowAddOption` | **11** | bool | "Başkalarının seçenek eklemesine izin ver" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, sadece görüntü-anketi seçenekleri için doldurulur, §5).

### 2.2 Yerel temsil

İstemci, ayrıştırılmış bir anketi `C13J` olarak saklar (quiz görüntü varyantı `C13K`), seçenekler ham adı (`A04`), adın yerel olarak hesaplanmış bir SHA-256 digest'ini (`A02`, §9.1) ve, görüntü seçenekleri için, wire `optionHash`'ini (`A08`) taşıyan `C33283EeZ` nesneleri olarak.

---

## 3. Sürüm geçmişi

### 3.1 Göndermek için hangi alanın kullanıldığı (found, `F2N.A00`/`A02`)

```text
pollType == QUIZ (correct answer set)              -> pollCreationMessageV5
chat is a community default-subgroup (group_type 3) -> pollCreationMessageV2
else:
  hideParticipantName / endTime / allowAddOption set -> pollCreationMessageV6
  none of those set                                   -> pollCreationMessageV3
```

`pollCreationMessageV4`, bu geçişte okunan gönderme yolu tarafından hiçbir zaman doldurulmaz; sadece alımda görünür (§3.3). Topluluk kontrolü, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2'deki düz-metin-tepki fallback'iyle aynı `group_type == 3` yüklemini yeniden kullanır (`C0GQ.A0A(chat) == 3`, `isDefaultSubgroup_`'tan ayarlanır); bir varsayılan-alt-grup anketinin V3/V6 yerine kendi versiyonlu slotunu neden aldığı, burada okunan kodda açıklanmamıştır (inferred: tarihi rollout sıralaması, çünkü V2'nin alan numarası genişletilmiş kümenin en düşüğüdür).

Yani pratikte: **V3**, ekstra özelliği olmayan sıradan bir çoklu/tekli-seçim anketi için mevcut slottur, **V6**, bitiş zamanı, gizli oy-veren adları veya seçenek-ekleme kullanan bir anket için mevcuttur, **V5** quiz'ler için mevcuttur, ve **V2**, aynı temel şeklin bir topluluk-alt-grup-özgü varyantıdır. **V1** (versiyonlanmamış alan 49) ve **V4**, bu build'de gönderen tarafından seçilmez.

### 3.2 `pollCreationMessageV4` = forward-compat wrapper'ı (found, `F2N.CM7`)

V4'ün proto tipi `FutureProofMessage`'dır (`BD2`, tek alan `message` = bir iç `Message`). Alımda, V4 slotu doldurulmuşken istemci `BD2.message_`'ı açar ve *o* iç mesajın kendi `pollCreationMessage` alanını (49) gerçek `PollCreationMessage` olarak okur. Bu gerçek bir fallback zarfıdır, ölü bir alan değil: daha yeni/tanımsız bir anket varyantı yaymak gereken bir gönderen, temel (alan-49-şekilli) bir anketi V4 içine sarabilir, böylece sadece genel `FutureProofMessage` açmasını anlayan ve daha yeni slotu anlamayan eski istemciler hâlâ düz bir anket render eder. Bu geçişte hiçbir kod yolu V4'ü gönderimde doldurmaz, bu yüzden bu, istemci sürümleri arasındaki ileri/geri uyumluluk için vardır, 2.26.41.6 istemcisinin kendisinin yaydığı bir şey için değil (inferred).

### 3.3 Alım-tarafı seçimi ve düşürme (found, yaklaşık; decompiler bazı dal yapısını kaybetti)

`F2N.CM7`, `Message` bitfield'lerini V1 → V2 → V4 → V5 → V6 → V3-fallback sırasında kontrol eder ve hangi versiyonlu alan doluysa onu aynı validator'a (`F2N.A01`, §4) ayrıştırır. Alımda V6'nın ekstra alanlarının kabulünü gaten üç flag vardır; bir flag kapalıyken anket tamamen reddedilmek yerine **düşürülür** (bir anket bubble'ı yerine genel future-proof yer-tutucu olarak ayrıştırılır):

| Ekstra alan | Gate | Gate kapalıyken etki |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | `poll downgraded to FMessageFuture (receiving disabled)` loglanır, bir anket olarak render edilmez |
| `hideParticipantName` | AB int **24885** | düşürme (kontrolün tam polaritesi decompile edilmiş kontrol akışından tam olarak çözülmemiş) |
| `allowAddOption` | AB int **25758** | düşürme |

Bu üç koşulun tam yuvalanması tam olarak yeniden inşa edilemedi (JADX, `F2N.CM7`'de çoğaltılmış/erişilemez bloklar bildiriyor); gating flag'leri ve düşürme sonucu found'dur, kesin boolean kombinasyonu inferred'dir.

### 3.4 Görüntü-içerik kapısı

`pollContentType = IMAGE`, sadece `pollContentType` için bit ayarlandığında V3/V5 ayrıştırma yolunda onurlandırılır; ayarlanmış ama değer `IMAGE` değilse, mesaj sessizce metin olarak ele alınmak yerine reddedilir (`return null`, genel parser'a düşer).

---

## 4. Oluşturma doğrulaması (found, `F2N.A01`)

Tüm versiyonlu oluşturma alanları tarafından paylaşılan tek validator. Belirtilmedikçe hata kodu **11** ile fırlatır:

| Kontrol | Kural | Hata string'i |
|-------|------|--------------|
| Ad mevcut | `name` biti ayarlanmış olmalı | `poll_creation_missing_name` |
| Ad uzunluğu | 1–5000 karakter (esnek bir ayrıştırma context'i bunu atlamadıkça, §4.1) | `poll_creation_invalid_name` |
| Quiz doğru cevabı | eğer `pollType=QUIZ`, `correctAnswer` biti ayarlanmış olmalı | `poll_creation_missing_correct_answer` |
| Seçenekler mevcut | sıfır-seçenek bypass'ı (§4.1) uygulanmıyorsa en az bir seçenek | `poll_creation_missing_options` |
| Seçenek sayısı (alt) | ≥ 2 seçenek (bypass altında 0) | `poll_creation_invalid_options_count` |
| Seçenek sayısı (üst) | ≤ `min(AB int 1408, 12)` — sunucu değerinden bağımsız olarak 12 sert bir istemci üst sınırıdır | `poll_creation_invalid_options_count` |
| Seçenek adı uzunluğu | seçenek-başına 1–2500 karakter | `poll_creation_invalid_option` |
| Doğru-cevap adı | quiz ise, `correctAnswer.optionName` boş-olmayan olmalı | `poll_creation_missing_correct_answer_name` |
| Çoğaltılmış seçenekler | seçenek adları benzersiz olmalı | `poll_creation_duplicate_options` |
| Çoğaltılmış trim'lenmiş seçenekler | AB flag **25758** altında, boşluk-trim'lenmiş adlar da benzersiz olmalı | `poll_creation_duplicate_trimmed_options` |
| Doğru cevap bir seçenekle eşleşir | quiz doğru-cevap adı bir seçeneğin adına eşit olmalı | `poll_creation_unmatched_correct_answer` |
| Seçilebilir sayı mevcut | `selectableOptionsCount` biti ayarlanmış olmalı | `poll_creation_missing_selectable_options_count` |
| Seçilebilir sayı aralığı | `0 <= selectableOptionsCount <= options.size()` (bypass altında `<= min(1408,12)`) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Sıfır-seçenek / esnek bypass (found kod yolu, semantik inferred)

AB bool **37909**'dan hesaplanan yerel bir boolean (`z`), sadece bir dahili ayrıştırma-context sayacı 1'e eşit olduğunda danışılır, minimum seçenek sayısını 0'a gevşetir ve seçilebilir-sayı üst sınırını `options.size()` yerine ham `min(1408,12)` sınırına genişletir. Bunun karşılık geldiği ayrıştırma-context değeri (normal alım vs. başka bir ingestion yolu, örn. geçmiş senkronizasyonu) çözülmedi; bu, doğrulanmış bir kullanıcıya-görünür "seçeneksiz anket" özelliği olarak değil, found-ama-açıklanmamış olarak kaydedilmiştir.

### 4.2 Geçmiş-senkronizasyonu / esnek-ad bypass'ı

Ayrı bir context flag'i (`c33371Eg0.A0W`), hem ad-uzunluğu hem de (eşdeğer olarak, `F39`'da, §9) sonuç-snapshot ad-uzunluğu kontrolünü kısa devre yapar, ham string'i kontrolsüz kabul eder. Güvenilir-kaynak bir ayrıştırma yolu ile tutarlıdır (örn. yerel geçmiş yeniden-içe-aktarma), normal bir ağ alımı değil; bağımsız olarak doğrulanmamıştır.

---

## 5. Görüntü-anketi seçenekleri: `pollCreationOptionImageMessage`

### 5.1 Yapı ve bağlama (found)

`pollCreationOptionImageMessage` (alan 90), sıradan yüklenmiş bir `ImageMessage`'ı bir `FutureProofMessage` içine sarar — görüntü `PollCreationMessage.Option` içine gömülü **değildir**. Her seçenek görüntüsü kendi çocuk mesajı olarak gönderilir, (henüz-gönderilmemiş) anketle `MessageContextInfo.messageAssociation`, association tipi `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; bu build'in enum değeri — önceki bir build'de 7'ydi, sayısal değer sürümler arasında stabil değildir ve release-başına yeniden okunmalıdır) üzerinden ilişkilendirilir. "MediaPollAssociationProvider" gönderme-tarafı yardımcısı (`C20M` içinde), ana anketin satır id'si ve association tipi `6` için `message_association` satırlarını sayar; sayı seçenek sayısına ulaştığında, tüm seçenek görüntüleri yüklenmiş sayılır ve istemci anketin kendisini `pollContentType = IMAGE` ile göndermeye geçer.

### 5.2 Görüntü seçenekleri için seçenek hash'i (inferred, önceki bir build'den taşınmış, 2.26.41.6'da satır-satır yeniden türetilmemiş)

Düz metin seçenekleri için wire `optionHash` alanı boş bırakılır; düz metin bir seçenek için hesaplanan tek hash, yerel arama digest'idir `C13J.A00`:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(2.26.41.6'da doğrudan doğrulandı, §9.1 — bu, oy seçimlerini eşleştirmek için kullanılan hash'tir, proto `optionHash` alanı değil). **Görüntü** seçenekleri için proto `optionHash` alanı doldurulur; gönderme sırasının önceki-sürüm izi, seçenek adı hash'ini yüklenen görüntünün `fileSha256`'sıyla birleştirdiğini bulmuştur:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Bu formül, bu geçişte 2.26.41.6 koduna karşı yeniden doğrulanmadı (hesaplayan sınıf bulunamadı); inferred olarak taşınmıştır ve güvenilmeden önce yeniden kontrol edilmelidir.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, alan 121)

### 6.1 Alanlar (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, oyunkiyle aynı şekil, §7).

### 6.2 Gönderme (found, `F2L.ADr`)

Yeni addan (ve, görüntü anketleri için, hash'inden) bir `Option` inşa eder, kaynak anketin key'ini ekler, ve — 1:1 sohbetlerde, bir düzenleme context'i olmadığında — mesaj-sırrı katmanının diğer eklentiler için yaptığı aynı şekilde gönderenin kimliğini LID/PN sınırı boyunca çözer (bkz [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 adım 4). Bir `pollUpdateMessage`'ın olduğu gibi, seçenek bu katmanda kendisi sır-şifrelenmez: seçenek-ekleme payload'u normal bir mesaj alanı olarak seyahat eder; mesaj-sırrı şemasına binmesi gerektiğinde `secretEncryptedMessage`'a (tip `POLL_ADD_OPTION`) sarılan şey, bir bütün olarak seçenek-ekleme denemesidir (§8).

### 6.3 Alım doğrulaması (found, `F2L.CM7`)

| Kontrol | Hata |
|-------|-------|
| Feature gate: AB int **25758** sıfır-olmayan olmalı | hata **10017** |
| `pollCreationMessageKey` mevcut | `poll_add_option_missing_poll_message_key` |
| `addOption` mevcut | `poll_add_option_missing_poll_option` |
| Seçenek adı boş-olmayan, ≤ 2500 karakter | `poll_add_option_invalid_option` |

Ortaya çıkan yerel nesne, `Poll Add Option` kullanım senaryosu ile transport için sır-şifrelenir (association tag'i olarak `AnonymousClass122.POLL_ADD_OPTION` ile mesaj-sırrı yardımcısına doğrulanmış çağrı). Eklenen seçenekler, görüntü-anketi seçenekleriyle aynı şekilde mevcut-seçenek eşleştirmesi için takip edilir (association tipi `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (oy ve oy metadata'sı)

Tam kripto (HKDF kullanım senaryosu `Poll Vote`, AAD, AES-GCM, LID/PN identity retry), [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7'dedir; bu bölüm sadece anket-oyu handler'ının (`DUA`, `F2P`'yi extend eder) plaintext ile ne yaptığını kapsar.

### 7.1 İki gönderme/alma yolu (found)

AB bool **6772**, şunlar arasında seçim yapar:
- **açık** (mevcut): paylaşımlı bir şifreleme yardımcısı (`C33285Eeb`), ciphertext'i ve `MessageKey`'i inşa eder; bir oy, yeniden şifreleme yerine daha önce saklanmış bir `(iv, payload)` çiftinden yeniden denenir.
- **kapalı** (eski): `DUA`'daki inline bir dal, aynı HKDF/AES-GCM çağrısını doğrudan yapar, hedef gönderen kimliğini kendisi türetir (oy verenin kendi anketindeki oylar için kendi LID'i, aksi halde oy hedefinin çözülmüş JID'i).

### 7.2 Oy payload'u: `PollVoteMessage` (`DPF`)

Tek alan `selectedOptions` **1**, repeated bytes — her girdi bir index değil, 32-byte'lık bir SHA-256 seçenek-adı digest'idir (§9.1). `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`), çözülmüş seçimi doğrular:

| Kontrol | Kural | Log tag'i |
|-------|------|---------|
| Seçim boyutu | ≤ 12 **ve** ≤ anketin `selectableOptionsCount`'u (> 0 olduğunda) | `poll_vote_invalid_options_count` |
| Hash şekli | her seçilmiş hash tam olarak 32 byte'a çözülür | `poll_vote_invalid_option_hashes` |
| Çoğaltılanlar | bir oyda tekrarlanan hash yok | `poll_vote_duplicate_option_hashes` |
| Çözümleme | her seçilmiş hash, anketin bilinen (kaldırılmamış) seçenek hash'lerinden biriyle eşleşmeli | bir hata sonucu döndürür, eşleşme yok -> oy reddedilir |

### 7.3 Bitiş-zamanı ve metadata (found, `DUA.A01`)

`senderTimestampMs`'si anketin `endTime`'ından sonra olan bir oy reddedilir (`poll_update_past_end_time`); AB bool **2321** altında reddedilmiş-oy olayı ek olarak bir telemetri sayacını besler (`N0e`). Oy `metadata`'sı (`pollNameHash`, `lastEditStanzaId`), sadece AB bool **31593** altında gönderimde damgalanır; alımda, eksik/boş bir metadata bloğu `"unstamped"` olarak loglanır (kendisi reddedilmez) ama *uyuşmayan* bir damga (`C32977EZa` tarafından kontrol edilir) oyu `poll_update_tc_drop` ile düşürür. Bu metadata, bir istemcinin henüz düzenleme geçmişine yetişmediği bir ankete karşı oy verdiğini algılayabilmesi için var.

---

## 8. Anket düzenleme (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Genel `secretEncryptedMessage` wrapper'ı (alan 82) içinde taşınır, anket-özgü bir taşıyıcı değil; zarf, AAD ve hata-kodu tablosu (`poll_edit_message_stanza_invalid`, AB int **24886** gate'i, hata **10016**) için [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4'e bakın. Anket-özgü doğrulama (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) şunları gerektirir:

- iç mesaj FMessage tipi 66'dır ve düzenlemeden önce ve sonra bir ankettir;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` ve `pollType`, saklanmış anket ile düzenlenmiş olan arasında **değişmemiştir** — sadece soru metni ve/veya seçenek metinleri farklı olabilir;
- seçenek eşleştirmesi: sohbet-başına bir flag (`EOI.A01()`, id çözülmemiş) etkinken, düzenlenmiş seçenekler, seçeneklerin yerinde yeniden adlandırılmasına izin veren sıralı (sıra-koruyan) bir eşleşme üzerinden saklanmış bir yeniden-adlandırma geçmişine karşı eşleştirilir; yeniden-adlandırmayan karşılaştırma dalının tam davranışı inferred'dir (JADX kontrol akışının bir kısmını yine düşürüyor — fonksiyon, decompile edilmiş biçimde o dalda `poll_edit_invalid_edits`'e düşüyor, bu, bir no-op düzenleme için gerçek istemci davranışı olması pek olası değil).

Kaynaklarda bir `"Couldn't edit poll"` toast string'i mevcuttur, anket düzenlemenin bu build'de kullanıcıya-görünür olduğunu, sadece ayrılmış bir protokol yolu olmadığını doğrular.

### 8.1 Anket-düzenleme UI'si (2.26.45.10'da yeni) — wire operasyonu çözülmemiş

Yeni bir paket `com.whatsapp.polls.ui.edit`, `PollEditActivity`'yi artı destekleyici
dialog'ları (`PollEditDiscardChangesDialog`, `PollEditSendFailedDialog`,
`PollOptionRemoveConfirmationDialog`) gönderir, bir gönderenin zaten-gönderilmiş bir anketi
yeniden adlandırmasına veya ondan seçenek eklemesine/çıkarmasına izin verir. Statik smali
izlemesinden found ve unknown (mevcut smali'yi okumanın ötesinde decompile yok):

- **Found:** `PollEditActivity`, bir `SavedStateHandle`-tutulan düzenleme durumuyla (`LX/8kp`
  view model, `LX/A4G` düzenleme payload'u: ad/id, anket adı string'i, mevcut seçenek
  satırları, kaldırılan satır id'lerinin bir `Set<Long>`'u) desteklenir. Seçenek satırları
  (`LX/JZ8`), hiçbir kaldırma flag'i taşımaz — bir seçenek, canlı anket durumuna karşı
  diff'lenen son listede basitçe yoktur (`LX/8kp;->A03(LX/A4G;LX/9ei;LX/8kp;)LX/9oc;`).
  Seçenek kaldırma, aşamalı bir rollout kontrolü tarafından gated edilir,
  `LX/Ihb;->getPollRemoveOptionRollout()LX/1yG;` — bir istemci-tarafı feature gate'i, yeni
  bir wire operasyonunun kanıtı değil.
- **Found:** 2.26.41.6 ile 2.26.45.10 arasındaki proto-schema diff'i **sıfır**
  anket-ilgili değişiklik içeriyor — bu sürüm için çıkarılan schema'nın hiçbir yerinde
  yeniden-adlandırma veya seçenek-kaldırma için yeni veya yeniden-adlandırılmış bir alan
  görünmüyor.
- **Inferred:** bu UI'den bir seçenek eklemek, en olası olarak hâlâ mevcut
  `pollAddOptionMessage`'a (§6, alan 121) biniyor — UI'nin "satır ekle" özelliği bu
  mesajın şekliyle eşleşiyor ve bir yerine-geçen seçenek-ekleme ilkeli tanıtılmamış.
  Kaydetme handler'ının izlenmesiyle doğrulanmamıştır.
- **Unknown:** yeniden adlandırma ve seçenek kaldırmanın doğrulanmış bir wire ilkeli
  yoktur. İki doğrulanmamış aday vardır, mevcut kanıta göre biri diğerinden daha olası
  değildir: (1) `Message.editedMessage` üzerinden tam-anket değiştirmesi
  (`FutureProofMessage`, taze bir `pollCreationMessage`'ı sarıyor), veya (2)
  `pollUpdateMessage`'ın opak şifreli `vote` alanının (`PollEncValue`, §7) oy-olmayan bir
  güncelleme için yeniden kullanılması. Kaydet butonunun gerçek ağ çağrısı, ilgili `switch`
  dalı sadece smali'den izole edilemeyen, paylaşımlı, R8-birleştirilmiş bir
  `View.OnClickListener` dispatcher'ının (`LX/A50`) ardında yatıyor — bu özel bir engeldir,
  bir kapsam seçimi değil.

Bu, en iyi bir tahmine çözülmek yerine açık bırakılmıştır; daha sonraki bir sürüme karşı
bir proto diff'i yeni bir alan gösterdiğinde, veya `LX/A50` dispatch dalı izlendiğinde
yeniden kontrol edin.

---

## 9. Oy eşleştirme dahili işleyişi

### 9.1 Seçenek hash'i (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

Seçeneğin görünür metninin düz SHA-256'sı, key materyali yok. Bu, seçenek-başına yerel olarak saklanan değerdir (`C33283EeZ.A02`) ve bir oyun `selectedOptions` girdilerinin karşılaştırıldığı değerdir. Seçeneğin metnini bilen herhangi bir uygulama aynı hash'i hesaplayabilir — bir oyun gizliliği tamamen oy payload'unun mesaj-sırrı şifrelemesinden gelir (§7, ve [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), hash'in tahmin edilemez olmasından değil.

---

## 10. Oy gizliliği / anonimlik modeli

| İddia | Durum |
|-------|-------|
| Oylar oy-veren-başına, anket-başına uçtan-uca şifrelidir (HKDF `Poll Vote` kullanım senaryosu) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| Seçilen seçenek, bir index değil, bir içerik hash'iyle tanımlanır | found, §9.1 |
| `hideParticipantName` ("Oy verenlerin adını gizle"), UI'de kimin oy verdiğinin gösterimini bastırır | found (string `str2137`, `PollCreationMessage`'ın alanı 10) |
| `hideParticipantName`, oy vereni protokol seviyesinde sunucudan veya diğer istemcilerden gizler | **burada okunan kod tarafından desteklenmiyor** — zarf `participant`/`from` (yani, oy verenin kimliği), bu flag'den bağımsız olarak her eklenti için aynı şekilde teslim edilir ve doğrulanır (bkz [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName`, anket nesnesinde sadece-görüntü bir ayardır, bir yönlendirme veya şifreleme değişikliği değildir |
| Anket oluşturucusu kimin oy verdiğini her zaman belirleyebilir | inferred — oy-çözme yolundaki (§7, §9) hiçbir şey `hideParticipantName`'e bağlı değildir; oluşturucunun istemcisi her oyu oy verenin kimliğini modifier olarak çözer |

Kısaca: WhatsApp anketleri oluşturucu için anonim değildir. "Oy verenlerin adını gizle", sadece *diğer katılımcıların* ("Anket oyları" listesinde) kimin oy verdiğini görüp görmediğini kontrol eder; kriptografik olarak oya bağlı olan şeyi değiştirmez, ve sunucu her halükârda oy içeriğini öğrenmez (olağan E2E garantisi, bu flag'e özgü bir şey değil).

---

## 11. Çoklu-seçim vs tekli-seçim

`selectableOptionsCount` (alan 4), tek mekanizmadır: bu değerden daha fazla seçime sahip bir oy reddedilir (§7.2). Wire'da ayrı bir "çoklu-seçim mi" boolean'ı yoktur — tekli-seçim basitçe `selectableOptionsCount = 1`'dir. Oluşturma UI'si bunu tek bir toggle olarak sunar, **"Birden fazla cevaba izin ver"** (string `str425f`); kapalıyken istemcinin `selectableOptionsCount = 1` gönderdiği inferred'dir, açıkken `selectableOptionsCount = options.size()` gönderdiği inferred'dir (UI, keyfi bir sayısal üst sınır sunmuyor gibi görünüyor — tek bir boolean string'inden inferred, oluşturma-UI kodunda bağımsız olarak doğrulanmamış). Protokolün kendisi `0..options.size()` arasında herhangi bir değere izin verir (§4), bu yüzden stock UI onu sunmasa bile 1 veya "tüm seçenekler" dışında bir istemci-tarafı değer mümkündür. Quiz'ler örtük olarak tekli-seçimdir (bir doğru cevap; oy-verene-görünür string `"Quiz • Select one correct answer"`, `str57a5`).

Oy-verene-görünür etiketler iki modu doğrular: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: iletme-zamanı snapshot'ı

### 12.1 Amaç (found, `F1A`)

Canlı bir anketi başka bir sohbete iletmek, etkileşimli anketi iletmez. `F1A` (aynı dönüştürme arayüzünü uygulayan birkaç "iletme" dönüştürücüsünden biri — bu, birçok mesaj tipinde kullanılır; desteklenmeyen tipler için kardeş dönüştürücü `"Cannot forward message of type: ..."` fırlatır), canlı anketi (`C13J`) bir `Dd2` nesnesine dönüştürür: soru metni, her seçeneğin adı ve **mevcut yerel oy sayısı**, ve anket/quiz tipi. Bu daha sonra `pollResultSnapshotMessage` (düz anket) veya `pollResultSnapshotMessageV3` (quiz) olarak serileştirilir ve etkileşimli anket bubble'ından ayrı, özel bir view holder (`DWH`) ile render edilir.

### 12.2 Alanlar (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (repeated `PollVote` — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (oluşturmayla aynı `PollType` enum'u).

### 12.3 Doğrulama (found, `F39`)

Oluşturmayla aynı şekilde kontroller: ad 1–5000 karakter, en az 2 seçenek, en fazla `min(AB 1408, 12)` seçenek, her seçenek adı 1–2500 karakter. **Quiz** varyantı (`V3`) için, oy sayıları gönderimde 0'a zorlanır — iletilen bir quiz snapshot'ı asla sayımları ifşa etmez, sadece soruyu ve seçenek listesini.

---

## 13. Limitler özeti

| Öğe | Limit | Kaynak |
|------|-------|--------|
| Anket/soru adı uzunluğu | 1–5000 karakter | `F2N.A01`, `F39.A00` |
| Seçenek adı uzunluğu | 1–2500 karakter | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Seçenek sayısı (oluşturma, snapshot) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Oy-başına seçilen seçenekler | ≤ 12 ve ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| `selectableOptionsCount` aralığı | 0–options.size() (esnek-context bypass'ı altında 0–12, §4.1) | `F2N.A01` |
| Seçenek-hash boyutu (oy girdileri) | tam olarak 32 byte | `AbstractC33199EdC` |

---

## 14. Feature flag'leri (çağrı noktalarında okunan id'ler; isimler çözülmemiş)

| ID | Tip | Kontrol ettiği |
|----|------|----------|
| **1408** | int | sunucu-yapılandırılmış maks anket seçenek sayısı, değerden bağımsız olarak sert istemci üst sınırı 12 |
| **24884** | bool | genişletilmiş bir anketin (V5/V6) alımında `endTime`'ı onurlandır; kapalı -> future-proof yer-tutucuya düşürülür |
| **24885** | int | alımda `hideParticipantName`'in kabulünü gater (tam polarite çözülmemiş) |
| **24886** | int | anket düzenleme alımı gate'i; 0 -> reddedilir, hata 10016 |
| **25758** | int (truthy) | anket seçenek-ekleme alımı gate'i (hata 10017); oluşturmada çoğaltılmış-trim'lenmiş-seçenek reddini de gater |
| **31593** | bool | gidiş bir oya `pollNameHash`/`lastEditStanzaId` metadata'sını damgala |
| **6772** | bool | anket oyu: paylaşımlı şifreleme yardımcısı (açık) vs eski inline yol (kapalı) |
| **37909** | bool | belirli (çözülmemiş) bir ayrıştırma context'inde sıfır seçenekli bir ankete izin verir |
| **2321** | bool | bir oy anket bitiş zamanından sonra olarak reddedildiğinde loglanan ekstra telemetri detayı |

Anketleri de etkileyen mesaj-sırrı-katmanı flag'leri (düzenleme kullanım senaryosu gate'i **17811**, üretim gate'leri, vb.), [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16'da belgelenmiştir ve burada tekrarlanmamıştır.

---

## 15. Baileys (sadece doğrulanmış gerçekler)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17, `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`'i okuyarak, bir JavaScript uygulamasının (`baron-baileys-v2` 1.5.17) anketlerle ilgili kısımlarını zaten kapsıyor:

- HKDF türetimi ve `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` kullanım-senaryosu string'leri, `Poll Vote` için `id\0modifier` AAD'si dahil, Android istemcisinin literalleriyle tam olarak eşleşiyor.
- AAD, identity-retry (PN/LID) ve eksik-sır işleme (ham, çözülmemiş güncellemeye geri dönüş), bu raporda (§7) ve [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3'te açıklanan Android davranışıyla eşleşiyor.
- Okunan dosyalarda `pollUpdateMessage` (veya `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) için hiçbir gönderme-tarafı şifreleme yolu bulunamadı — yani o uygulama gelen bir oyu çözebiliyordu ama incelenen dosyalar birini şifreleyip gönderecek kod içermiyordu.

Bu geçişte, orada zaten belirtilenin ötesinde anket-özgü hiçbir şey bağımsız olarak yeniden doğrulanmadı (hiçbir Baileys anket-oluşturma, seçenek-hash veya anket-düzenleme kodu okunmadı); burada başka Baileys iddiası yapılmamıştır.

---

## 16. Hata durumları

| Belirti | Neden | Düzeltme |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | 2'den az veya `min(1408,12)`'den fazla seçenek | seçenekleri aralık içinde tut |
| `poll_creation_unmatched_correct_answer` | quiz `correctAnswer.optionName`, hiçbir seçeneğin adına eşit değil | doğru cevabı tam bir eşleşmeye ayarla |
| Anket sessizce gösterilmiyor (düşürülmüş) | V6 bir ankette `endTime`/`hideParticipantName`/`allowAddOption` ayarlanmış ama alıcıda eşleşen AB flag'i kapalı | gönderen-tarafı, içerikle düzeltilemez; alıcı yetenek boşluğu |
| `poll_vote_invalid_options_count` | oy, `selectableOptionsCount`'tan veya 12'den daha fazla seçenek seçiyor | anketin üst sınırına uy |
| `poll_update_past_end_time` | oy (veya seçenek-ekleme / düzenleme) zaman damgası `endTime`'dan sonra | anket kapanmadan önce oy ver |
| `poll_update_tc_drop` | oyun `pollNameHash`/`lastEditStanzaId`'si alıcının ankete bakış açısıyla eşleşmiyor | oy vermeden önce anket düzenleme geçmişini yeniden senkronize et |
| Seçenek-ekleme'de hata **10017** | alıcıda AB **25758** sıfır | alıcı yetenek boşluğu |
| Anket düzenlemede hata **10016** | alıcıda AB **24886** sıfır | alıcı yetenek boşluğu |
| `poll_add_option_past_end_time` | `endTime`'dan sonra eklenen seçenek | anket kapanmadan önce seçenek ekle |

---

## 17. Ayırt edilmesi gereken noktalar

| Bu | Bu değil |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (`PollCreationMessage` tipi) | `pollCreationMessageV4` (temel bir iç anketi saran `FutureProofMessage`) |
| `pollUpdateMessage` (oy, veya oy metadata'sı) | `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` ile `secretEncryptedMessage` (anket düzenleme / seçenek ekleme) |
| `pollAddOptionMessage` (yeni seçenek payload'u) | mesaj-sırrı-bağlı olduğunda onu wire üzerinden taşıyan `secretEncryptedMessage` wrapper'ı |
| `pollResultSnapshotMessage`/V3 (statik, iletilmiş) | canlı etkileşimli anket (`pollCreationMessage*`) |
| SHA-256(ad) hash'i ile seçenek seçimi | index ile seçim — WhatsApp anketleri hiçbir zaman pozisyonla seçim yapmaz |
| `hideParticipantName` (UI görüntü ayarı) | oy gönderen anonimliği (yok; oluşturucu her zaman oy vereni çözer) |
| `selectableOptionsCount` (tek çoklu/tekli-seçim sinyali) | ayrı bir "çoklu-seçim mi" boolean'ı (hiçbiri yok) |

---

## 18. Tam akış (oluşturma, görüntü seçeneği, oy, iletme)

```
[Creator]                                          [Server]                     [Participant]
   │ build PollCreationMessage                        │                              │
   │  (quiz? -> V5; community subgroup? -> V2;         │                              │
   │   extras(endTime/hide/addOpt)? -> V6; else V3)    │                              │
   │ [image poll]                                      │                              │
   │  send N × pollCreationOptionImageMessage           │                              │
   │   (messageAssociation MEDIA_POLL=6, parent key)───▶───────────────────────────▶ received,
   │  wait for all fileSha256                           │                              associated
   │  compute optionHash per option                     │                              │
   │ send pollCreationMessage* ─────────────────────────▶──────────────────────────▶ store poll,
   │                                                    │                              secret
   │                                                    │        select option(s)     │
   │                                                    │        hash = SHA256(name)  │
   │                                                    │        key = HKDF(secret,   │
   │                                                    │          pollId‖creator‖    │
   │                                                    │          voter‖"Poll Vote") │
   │                                                    │        pollUpdateMessage    │
   │◀────────────────────────────────────────────────────◀ {key, vote{ct,iv}, ts} ────│
   │ validate: end time, selection count/hash shape     │                              │
   │ decrypt, resolve hash -> known option              │                              │
   │ apply vote                                         │                              │
   │                                                    │                              │
   │ [user forwards the poll elsewhere]                 │                              │
   │ convert live poll -> Dd2 (name, per-option count)  │                              │
   │ quiz? zero the counts                              │                              │
   │ send pollResultSnapshotMessage[/V3] ───────────────▶──────────────────────────▶ static bubble,
   │                                                    │                              not interactive
```

---

## 19. Bilinmeyenler

| Öğe | Durum |
|------|--------|
| AB **24885**'in tam polaritesi (hideParticipantName kabul/düşürme) | decompile edilmiş dal yapısı eksik |
| 2.26.41.6 için görüntü-seçeneği hash formülü (`nameHash`+`imageHash`) | önceki bir build'den taşınmış, bu build'in kodunda yeniden türetilmemiş |
| Anket-düzenleme eşleştirmesinde kullanılan sohbet-başına "sıralı seçenek yeniden adlandırma" toggle'ının ardındaki AB flag id'si (`EOI.A01()`) | id çözülmemiş |
| Anket-düzenleme seçenek karşılaştırmasının yeniden-adlandırmayan dalı | decompiler kontrol akışının bir kısmını düşürüyor; literal decompile edilmiş biçim her zaman `poll_edit_invalid_edits`'e düşüyor, bu bir no-op düzenleme için gerçek davranış olması pek olası değil |
| Sıfır-seçenek bypass'ını (AB **37909**) etkinleştiren ayrıştırma-context değeri (`c33371Eg0.A00 == 1`) | tanımlanmamış (geçmiş senkronizasyonu vs. başka bir yol) |
| Stock oluşturma UI'sinin 1 veya "tüm seçenekler" dışında `selectableOptionsCount` değerleri gönderip gönderemediği | tek bir boolean toggle string'inden inferred, UI koduna karşı doğrulanmamış |
| `MEDIA_POLL` association sayısal değerinin sürümler arasında stabilliği | 2.26.41.6'da 6 olarak found; önceki bir build farklı bir değer kullandı, bu yüzden sürümler arasında hardcode etmeyin |
