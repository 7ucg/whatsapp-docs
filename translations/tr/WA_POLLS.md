<!-- src-sha1: 4123b5a528529c4f17625135c9cbbdbd63f1dc08 -->
# WhatsApp Anketler — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** anket mesaj ailesi (`pollCreationMessage`'dan `pollCreationMessageV6`'ya, `pollCreationOptionImageMessage`, `pollAddOptionMessage`, `pollUpdateMessage`, `pollResultSnapshotMessage`/`V3`), sürüm geçmişi ve gönderme/alma seçim mantığı, oluşturma doğrulaması ve limitler, resimli anket seçeneği bağlama, oy seçimi ve gizlilik modeli, çoklu seçim vs tekli seçim, anket düzenleme, geri dönüşsüz (forward-time) sonuç anlık görüntüsü, feature flag'ler

---

## 1. Nedir

Bir anket, soru, seçenek listesi, seçim üst sınırı ve isteğe bağlı quiz/bitiş zamanı/görünürlük ayarları taşıyan bir `Message` alt nesnesidir (`PollCreationMessage`, altı sürümlü üst seviye alanda değişmeden tekrar kullanılır). Oylar (`pollUpdateMessage`), eklenen seçenekler (`pollAddOptionMessage`) ve düzenlemeler (`secretEncryptedMessage`) ayrı takip mesajlarıdır; oluşturma mesajının id'sine ve mesaj başına secret'ına bağlıdır. Bu şifreleme (HKDF use case'leri, AES-GCM, AAD, kimlik retry) [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) içinde ele alınır ve burada tekrarlanmaz. Bu rapor mesaj-tipi katmanını kapsar: hangi alan neyi taşır, client ikisi arasında nasıl seçim yapar, doğrulama ve limitler, ve anket-özel handler'lar şifresi çözülmüş payload ile ne yapar. Tüm bulgular decompile edilmiş 2.26.41.6 APK'nın statik analizidir (`java_src/` altındaki Java kaynakları, ayrıca `res/values/strings.xml`); wire üzerinde hiçbir şey yakalanmadı. Tier'lar: **found** = kodda/kaynaklarda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi.

| Varlık | `Message` içinde alan | Proto tipi | Rol |
|--------|--------------------|-----------|------|
| `pollCreationMessage` | **49** | `PollCreationMessage` (`DTM`) | orijinal oluşturma yuvası |
| `pollCreationMessageV2` | **60** | `PollCreationMessage` | bir community default-subgroup sohbetinde oluşturma |
| `pollCreationMessageV3` | **64** | `PollCreationMessage` | düz anket oluşturma yuvası (sıradan anketler için mevcut varsayılan) |
| `pollCreationMessageV4` | **93** | `FutureProofMessage` (`BD2`) | bir iç `Message.pollCreationMessage` (alan 49) etrafındaki ileriye-uyumlu wrapper |
| `pollCreationMessageV5` | **111** | `PollCreationMessage` | quiz oluşturma yuvası |
| `pollCreationMessageV6` | **119** | `PollCreationMessage` | genişletilmiş anket yuvası (bitiş zamanı / oy verenleri gizle / seçenek ekleme izni) |
| `pollCreationOptionImageMessage` | **90** | `FutureProofMessage` | bir resimli anket seçeneği görseli, `messageAssociation` ile henüz-gönderilmemiş ankete bağlanır |
| `pollAddOptionMessage` | **121** | `PollAddOptionMessage` (`C30556DRc`) | mevcut bir ankete bir seçenek ekler |
| `pollUpdateMessage` | **50** | `PollUpdateMessage` (`DSG`) | oy (şifreli) veya oy metadata'sı |
| `pollResultSnapshotMessage` | **88** | `PollResultSnapshotMessage` (`DSF`) | statik sonuç anlık görüntüsü, anket başka bir sohbete yönlendirildiğinde |
| `pollResultSnapshotMessageV3` | **115** | `PollResultSnapshotMessage` | aynısı, quiz varyantı (oy sayıları sıfırlanmış) |

Alan numaraları doğrudan `C30628DTw` (`Message` proto sınıfı) üzerinden doğrulandı; bu sınıf yukarıdaki tabloyla eşleşen on bir `POLL_*_FIELD_NUMBER` sabitini tanımlıyor.

---

## 2. `PollCreationMessage` (`DTM`)

### 2.1 Alanlar (found)

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `encKey` | **1** | bytes | wire üzerinde mevcut ama bu pass'te okunan handler'lar tarafından kullanılmıyor (oylar bu alanı değil, mesaj başına `messageSecret`'ı kullanır; bkz. [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3) |
| `name` | **2** | string | anket sorusu, en fazla 5000 karakter, zorunlu |
| `options` | **3** | repeated `Option` | cevap seçenekleri |
| `selectableOptionsCount` | **4** | uint32 | seçim üst sınırı, zorunlu (§11) |
| `contextInfo` | **5** | `ContextInfo` | standart context |
| `pollContentType` | **6** | enum `PollContentType` (`E25`) | `UNKNOWN`=0 (`A03`), `TEXT`=1 (`A02`), `IMAGE`=2 (`A01`) |
| `pollType` | **7** | enum `PollType` (`EnumC32108E1g`) | `POLL`=0 (`A01`), `QUIZ`=1 (`A02`) |
| `correctAnswer` | **8** | `Option` | quiz doğru cevap seçeneği, `pollType=QUIZ` olduğunda zorunlu |
| `endTime` | **9** | int64 | anket kapanış zaman damgası (ms) |
| `hideParticipantName` | **10** | bool | "Oy verenlerin adlarını gizle" (§10) |
| `allowAddOption` | **11** | bool | "Başkalarının seçenek eklemesine izin ver" (§6) |

`PollCreationMessage.Option` (`C30529DQb`): `optionName` **1** (string), `optionHash` **2** (string, yalnızca resimli anket seçenekleri için doldurulur, §5).

### 2.2 Yerel temsil

Client ayrıştırılmış bir anketi `C13J` (quiz resim varyantı `C13K`) olarak depolar; seçenekler `C33283EeZ` nesneleri olarak ham ismi (`A04`), isim için yerel olarak hesaplanmış SHA-256 özetini (`A02`, §9.1) ve resimli seçenekler için wire `optionHash`'ini (`A08`) taşır.

---

## 3. Sürüm geçmişi

### 3.1 Göndermede hangi alan kullanılır (found, `F2N.A00`/`A02`)

```text
pollType == QUIZ (correct answer set)              -> pollCreationMessageV5
chat is a community default-subgroup (group_type 3) -> pollCreationMessageV2
else:
  hideParticipantName / endTime / allowAddOption set -> pollCreationMessageV6
  none of those set                                   -> pollCreationMessageV3
```

`pollCreationMessageV4` bu pass'te okunan gönderme yolunda hiç doldurulmaz; sadece almada görünür (§3.3). Community kontrolü, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.2'deki düz-metin-reaksiyon fallback'iyle aynı `group_type == 3` yüklemini yeniden kullanır (`C0GQ.A0A(chat) == 3`, `isDefaultSubgroup_`'tan ayarlanır); neden bir default-subgroup anketinin V3/V6 yerine kendi versiyonlu yuvasını aldığı burada okunan kodda açıklanmıyor (inferred: tarihsel rollout sıralaması, çünkü V2'nin alan numarası genişletilmiş kümenin en düşüğü).

Pratikte: ekstra içermeyen sıradan bir çok-seçimli/tekli-seçimli anket için şu an kullanılan yuva **V3**'tür, bitiş zamanı, gizli oy veren adları veya seçenek ekleme kullanan bir anket için şu an kullanılan **V6**'dır, quizler için şu an kullanılan **V5**'tir ve **V2** aynı temel şeklin bir community-subgroup'a özel varyantıdır. **V1** (versiyonsuz alan 49) ve **V4**, bu build'de gönderici tarafından seçilmez.

### 3.2 `pollCreationMessageV4` = ileriye-uyumlu wrapper (found, `F2N.CM7`)

V4'ün proto tipi `FutureProofMessage`'dır (`BD2`, tek alan `message` = bir iç `Message`). Almada, V4 yuvası doldurulduğunda client `BD2.message_`'ı açar ve *o* iç mesajın kendi `pollCreationMessage` alanını (49) gerçek `PollCreationMessage` olarak okur. Bu gerçek bir fallback zarfıdır, ölü bir alan değil: daha yeni/tanımsız bir anket varyantı göndermesi gereken bir gönderici, temel (alan-49-şekilli) bir anketi V4 içine sarabilir, böylece eski client'lar — sadece genel `FutureProofMessage` unwrap'ini anlayan, yeni yuvayı değil — yine düz bir anket gösterir. Bu pass'te hiçbir kod yolu V4'ü göndermede doldurmuyor, dolayısıyla bu client sürümleri arasındaki ileri/geri uyumluluk için var, 2.26.41.6 client'ının kendisinin yaydığı bir şey için değil (inferred).

### 3.3 Alma tarafı seçim ve downgrade (found, yaklaşık; decompiler bazı branch yapısını kaybetti)

`F2N.CM7`, `Message` bitfield'larını V1 → V2 → V4 → V5 → V6 → V3-fallback sırasında kontrol eder ve doldurulmuş olan versiyonlu alanı aynı validator'a (`F2N.A01`, §4) ayrıştırır. Üç flag, V6'nın ekstra alanlarının almada kabulünü kapılar; bir flag kapalıyken anket tamamen reddedilmek yerine **downgrade** edilir (anket balonu yerine genel ileriye-uyumlu placeholder olarak ayrıştırılır):

| Ekstra alan | Kapı | Flag kapalıyken etki |
|-------------|------|--------------------------|
| `endTime` | AB int **24884** (`receivingEnabled`) | loglanır `poll downgraded to FMessageFuture (receiving disabled)`, anket olarak render edilmez |
| `hideParticipantName` | AB int **24885** | downgrade (kontrolün tam polaritesi decompiled kontrol akışından tam çözülemedi) |
| `allowAddOption` | AB int **25758** | downgrade |

Bu üç koşulun kesin iç içeliği tam yeniden kurulamadı (JADX `F2N.CM7` içinde tekrarlanmış/erişilemez bloklar rapor ediyor); kapı flag'leri ve downgrade sonucu found, kesin boolean kombinasyonu inferred.

### 3.4 Resim-içerik kapısı

`pollContentType = IMAGE`, sadece `pollContentType` için bit set edildiğinde V3/V5 ayrıştırma yolunda onurlandırılır; bit set ama değer `IMAGE` değilse, mesaj (sessizce metin olarak işlenmek yerine) reddedilir (`return null`, genel parser'a düşer).

---

## 4. Oluşturma doğrulaması (found, `F2N.A01`)

Tüm versiyonlu oluşturma alanları tarafından paylaşılan tek validator. Belirtilmedikçe hata kodu **11** ile throw eder:

| Kontrol | Kural | Hata string'i |
|-------|------|--------------|
| İsim mevcut | `name` biti set edilmeli | `poll_creation_missing_name` |
| İsim uzunluğu | 1–5000 karakter (bir lenient ayrıştırma context'i bypass etmedikçe, §4.1) | `poll_creation_invalid_name` |
| Quiz doğru cevap | `pollType=QUIZ` ise, `correctAnswer` biti set edilmeli | `poll_creation_missing_correct_answer` |
| Seçenekler mevcut | sıfır-seçenek bypass'ı uygulanmadıkça en az bir seçenek (§4.1) | `poll_creation_missing_options` |
| Seçenek sayısı (alt sınır) | ≥ 2 seçenek (bypass altında 0) | `poll_creation_invalid_options_count` |
| Seçenek sayısı (üst sınır) | ≤ `min(AB int 1408, 12)` — 12, sunucu değerinden bağımsız sert bir client üst sınırı | `poll_creation_invalid_options_count` |
| Seçenek ismi uzunluğu | seçenek başına 1–2500 karakter | `poll_creation_invalid_option` |
| Doğru cevap ismi | quiz ise, `correctAnswer.optionName` boş olmamalı | `poll_creation_missing_correct_answer_name` |
| Tekrarlanan seçenekler | seçenek isimleri benzersiz olmalı | `poll_creation_duplicate_options` |
| Tekrarlanan trim'lenmiş seçenekler | AB flag **25758** altında, boşluk-trim'lenmiş isimler de benzersiz olmalı | `poll_creation_duplicate_trimmed_options` |
| Doğru cevap bir seçenekle eşleşiyor | quiz doğru-cevap ismi bir seçeneğin ismine eşit olmalı | `poll_creation_unmatched_correct_answer` |
| Seçilebilir sayı mevcut | `selectableOptionsCount` biti set edilmeli | `poll_creation_missing_selectable_options_count` |
| Seçilebilir sayı aralığı | `0 <= selectableOptionsCount <= options.size()` (veya bypass altında `<= min(1408,12)`) | `poll_creation_invalid_selectable_options_count` |

### 4.1 Sıfır-seçenek / lenient bypass (found kod yolu, semantik inferred)

AB bool **37909**'dan hesaplanan yerel bir boolean (`z`), yalnızca iç bir ayrıştırma-context sayacı 1'e eşit olduğunda dikkate alınır ve minimum seçenek sayısını 0'a gevşetir, seçilebilir-sayı üst sınırını `options.size()` yerine ham `min(1408,12)` sınırına genişletir. Bunun karşılık geldiği ayrıştırma-context değeri (normal alma vs. başka bir ingestion yolu, örn. history sync) çözülemedi; bu, onaylanmış kullanıcıya-görünür bir "seçeneksiz anket" özelliği değil, found-ama-açıklanamamış olarak kaydedildi.

### 4.2 History-sync / lenient-isim bypass

Ayrı bir context flag'i (`c33371Eg0.A0W`), hem isim-uzunluğu kontrolünü hem de (eşdeğer olarak, `F39`'da, §9) sonuç-anlık-görüntüsü isim-uzunluğu kontrolünü kısa devre yapar, ham string'i kontrolsüz kabul eder. Güvenilir-kaynak bir ayrıştırma yoluyla (örn. yerel history re-import) uyumlu, normal network alma ile değil; bağımsız olarak onaylanmadı.

---

## 5. Resimli anket seçenekleri: `pollCreationOptionImageMessage`

### 5.1 Yapı ve bağlama (found)

`pollCreationOptionImageMessage` (alan 90), sıradan bir yüklenmiş `ImageMessage`'ı bir `FutureProofMessage` içinde sarar — görsel `PollCreationMessage.Option` içine gömülü **değildir**. Her seçenek görseli kendi çocuk mesajı olarak gönderilir, (henüz gönderilmemiş) anketle `MessageContextInfo.messageAssociation` üzerinden ilişkilendirilir, association tipi `MEDIA_POLL = 6` (`AnonymousClass122.MEDIA_POLL`; bu build'in enum değeri — önceki bir build'de 7'deydi, sayısal değer sürümler arasında stabil değil ve sürüm başına yeniden okunmalı). "MediaPollAssociationProvider" gönderme-tarafı yardımcısı (`C20M` içinde), üst anketin satır id'si ve association tipi `6` için `message_association` satırlarını sayar; sayı seçenek sayısına ulaştığında, tüm seçenek görsellerinin yüklendiği kabul edilir ve client anketin kendisini `pollContentType = IMAGE` ile göndermeye geçer.

### 5.2 Resimli seçenekler için seçenek hash'i (inferred, önceki bir build'den taşındı, 2.26.41.6'da satır satır yeniden türetilmedi)

Düz metin seçenekler için wire `optionHash` alanı boş bırakılır; düz metin seçeneği için hesaplanan tek hash, yerel lookup özeti `C13J.A00`'dur:

```text
optionHash(text option) = Base64(SHA-256(UTF8(optionName)))
```

(doğrudan 2.26.41.6'da onaylandı, §9.1 — bu, oy seçimlerini eşleştirmek için kullanılan değerdir, proto `optionHash` alanı değil). **Resimli** seçenekler için proto `optionHash` alanı doldurulur; önceki bir sürümün gönderme dizisi izlemesi, seçenek ismi hash'ini yüklenen görselin `fileSha256`'sıyla birleştirdiğini buldu:

```text
nameHash   = lowerHex(SHA-256(UTF8(optionName)))
imageHash  = base64(imageMessage.fileSha256)
optionHash = lowerHex(SHA-256(UTF8(nameHash + imageHash)))
```

Bu formül bu pass'te 2.26.41.6 koduna karşı yeniden doğrulanmadı (hesaplayan sınıf bulunamadı); inferred olarak taşınır ve güvenilmeden önce yeniden kontrol edilmelidir.

---

## 6. `pollAddOptionMessage` (`C30556DRc`, alan 121)

### 6.1 Alanlar (found)

`pollCreationMessageKey` **1** (`MessageKey`), `addOption` **2** (`PollCreationMessage.Option`), `metadata` **3** (`PollUpdateMessageMetadata`, oyunkiyle aynı şekil, §7).

### 6.2 Gönderme (found, `F2L.ADr`)

Yeni isimden (ve, resimli anketler için, hash'inden) bir `Option` oluşturur, kaynak anketin anahtarını ekler, ve — 1:1 sohbetlerde, bir düzenleme context'i değilken — gönderici kimliğini, mesaj-secret katmanının diğer ekler için yaptığı şekilde LID/PN sınırında çözümler (bkz. [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §6.1 adım 4). Seçenek, bu katmanda bir `pollUpdateMessage`'ın olduğu gibi secret ile şifrelenmiş *değildir*: add-option payload'ı normal bir mesaj alanı olarak yolculuk eder; `secretEncryptedMessage` (tip `POLL_ADD_OPTION`) içine sarılan şey, mesaj-secret şemasına binmek zorunda olduğunda add-option girişiminin bütünüdür (§8).

### 6.3 Alma doğrulaması (found, `F2L.CM7`)

| Kontrol | Hata |
|-------|-------|
| Feature kapısı: AB int **25758** sıfır olmamalı | hata **10017** |
| `pollCreationMessageKey` mevcut | `poll_add_option_missing_poll_message_key` |
| `addOption` mevcut | `poll_add_option_missing_poll_option` |
| Seçenek ismi boş değil, ≤ 2500 karakter | `poll_add_option_invalid_option` |

Oluşan yerel nesne, use case `Poll Add Option` kullanılarak taşıma için secret ile şifrelenir (mesaj-secret yardımcısına `AnonymousClass122.POLL_ADD_OPTION` association tag'i ile çağrı onaylandı). Eklenen seçenekler, resimli anket seçeneklerinin takip edildiği şekilde mevcut-seçenek eşleştirmesi için takip edilir (association tipi `POLL_ADD_OPTION = 18`).

---

## 7. `pollUpdateMessage` (oy ve oy metadata'sı)

Tam kripto (HKDF use case `Poll Vote`, AAD, AES-GCM, LID/PN kimlik retry) [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3–§7'de; bu bölüm sadece anket-oyu handler'ının (`DUA`, `F2P`'yi extend eder) düz metinle ne yaptığını kapsar.

### 7.1 İki gönderme/alma yolu (found)

AB bool **6772**, şunlar arasında seçim yapar:
- **açık** (şu an): paylaşılan bir şifreleme yardımcısı (`C33285Eeb`) ciphertext ve `MessageKey`'i oluşturur; oy, mevcut olduğunda yeniden şifrelemek yerine önceden depolanmış bir `(iv, payload)` çiftinden yeniden denenir.
- **kapalı** (eski): `DUA` içindeki satır içi bir branch, aynı HKDF/AES-GCM çağrısını doğrudan yapar, hedef gönderici kimliğini kendisi türetir (kendi anketindeki oylar için kendi LID'i, aksi halde oy hedefinin çözümlenmiş JID'i).

### 7.2 Oy payload'ı: `PollVoteMessage` (`DPF`)

Tek alan `selectedOptions` **1**, repeated bytes — her giriş 32 baytlık bir SHA-256 seçenek-ismi özetidir (§9.1), bir indeks değil. `MessageAddOnPollVoteUtils` (`AbstractC33199EdC`), şifresi çözülmüş seçimi doğrular:

| Kontrol | Kural | Log tag'i |
|-------|------|---------|
| Seçim boyutu | ≤ 12 **ve** ≤ anketin `selectableOptionsCount`'u (> 0 olduğunda) | `poll_vote_invalid_options_count` |
| Hash şekli | seçilen her hash tam olarak 32 bayt olarak decode edilmeli | `poll_vote_invalid_option_hashes` |
| Tekrarlar | bir oyda tekrarlanan hash olmamalı | `poll_vote_duplicate_option_hashes` |
| Çözümleme | seçilen her hash, anketin bilinen (kaldırılmamış) seçenek hash'lerinden biriyle eşleşmeli | bir hata sonucu döner, eşleşme yoksa -> oy reddedilir |

### 7.3 Bitiş zamanı ve metadata (found, `DUA.A01`)

`senderTimestampMs`'i anketin `endTime`'ından sonra olan bir oy reddedilir (`poll_update_past_end_time`); AB bool **2321** altında reddedilen-oy olayı ayrıca bir telemetri sayacını (`N0e`) besler. Oy `metadata`'sı (`pollNameHash`, `lastEditStanzaId`) sadece AB bool **31593** altında göndermede damgalanır; almada, eksik/boş bir metadata bloğu `"unstamped"` olarak loglanır (kendi başına reddedilmez), *uyuşmayan* bir damga ise (`C32977EZa` tarafından kontrol edilir) oyu `poll_update_tc_drop` ile düşürür. Bu metadata, bir client'ın henüz yakalamadığı bir düzenleme geçmişine sahip bir ankete karşı oy verdiğini tespit edebilmesi için vardır.

---

## 8. Anket düzenleme (`secretEncryptedMessage`, `secretEncType = POLL_EDIT`)

Genel `secretEncryptedMessage` wrapper'ı içinde taşınır (alan 82), anket-özel bir taşıyıcı değil; zarf, AAD ve hata-kodu tablosu (`poll_edit_message_stanza_invalid`, AB int **24886** kapısı, hata **10016**) için [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §5/§7.4'e bakın. Anket-özel doğrulama (`F3Y`, `SecretEncryptedMessageDeserializationValidator`) şunları gerektirir:

- iç mesaj FMessage tip 66'dır ve düzenlemeden önce de sonra da bir ankettir;
- `endTime`, `hideParticipantName`, `allowAddOption`, `selectableOptionsCount` ve `pollType`, depolanan anket ile düzenlenmiş anket arasında **değişmemiştir** — sadece soru metni ve/veya seçenek metinleri farklı olabilir;
- seçenek eşleştirmesi: sohbet başına bir flag (`EOI.A01()`, id çözülemedi) etkinken, düzenlenmiş seçenekler sıralı (sıra-koruyan) bir eşleşme üzerinden depolanmış bir yeniden adlandırma geçmişine karşı eşleştirilir, böylece seçeneklerin yerinde yeniden adlandırılmasına izin verilir; yeniden-adlandırmayan karşılaştırma branch'inin kesin davranışı inferred'dır (JADX burada da kontrol akışının bir kısmını düşürüyor — fonksiyon decompiled formda o branch'te `poll_edit_invalid_edits`'e düşüyor, bu da bir no-op düzenleme için gerçek client davranışı olması pek muhtemel değil).

Kaynaklarda bir `"Couldn't edit poll"` toast string'i mevcut, bu da bu build'de anket düzenlemenin sadece saklı bir protokol yolu değil, kullanıcıya görünür olduğunu onaylıyor.

---

## 9. Oy eşleştirme dahili işleyişi

### 9.1 Seçenek hash'i (found, `C13J.A00`)

```text
optionHash = Base64(SHA-256(UTF8(optionName)))
```

Seçeneğin görünür metninin düz SHA-256'sı, anahtar malzemesi yok. Bu, her yerel seçenek için depolanan değerdir (`C33283EeZ.A02`) ve bir oyun `selectedOptions` girdilerinin karşılaştırıldığı değerdir. Seçeneğin metnini bilen herhangi bir uygulama aynı hash'i hesaplayabilir — bir oyun gizliliği tamamen oy payload'ının mesaj-secret şifrelemesinden gelir (§7, ve [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md)), hash'in tahmin edilemez olmasından değil.

---

## 10. Oy gizliliği / anonimlik modeli

| İddia | Durum |
|-------|-------|
| Oylar oy veren başına, anket başına uçtan uca şifrelidir (HKDF `Poll Vote` use case) | found, [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §3 |
| Seçilen seçenek bir içerik hash'iyle tanımlanır, bir indeksle değil | found, §9.1 |
| `hideParticipantName` ("Oy verenlerin adlarını gizle"), UI'da kimin oy verdiğinin gösterimini bastırır | found (string `str2137`, `PollCreationMessage`'ın 10. alanı) |
| `hideParticipantName`, oy vereni sunucudan veya diğer client'lardan protokol seviyesinde gizler | **burada okunan kod tarafından desteklenmiyor** — zarf `participant`/`from` (yani oy verenin kimliği) bu flag'den bağımsız olarak her eklenti için aynı şekilde iletilir ve kimlik doğrulanır (bkz. [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §8); `hideParticipantName`, anket nesnesinde sadece görünüm ayarıdır, bir yönlendirme veya şifreleme değişikliği değil |
| Anket oluşturucu her zaman kimin oy verdiğini belirleyebilir | inferred — oy-şifre-çözme yolundaki (§7, §9) hiçbir şey `hideParticipantName`'e bağlı değil; oluşturucunun client'ı her oyun şifresini oy verenin kimliğini modifier olarak çözer |

Kısaca: WhatsApp anketleri oluşturucuya karşı anonim değildir. "Oy verenlerin adlarını gizle" sadece *diğer katılımcıların* ("Anket oyları" listesinde) kimin oy verdiğini görüp görmediğini kontrol eder; oyun içine kriptografik olarak bağlanan şeyi değiştirmez, ve sunucu her halükarda oy içeriğini öğrenmez (bu flag'e özgü bir şey değil, olağan E2E garantisi).

---

## 11. Çoklu seçim vs tekli seçim

`selectableOptionsCount` (alan 4) tek mekanizmadır: bu değerden fazla seçim yapan bir oy reddedilir (§7.2). Wire üzerinde ayrı bir "çoklu-seçim mi" boolean'ı yoktur — tekli-seçim basitçe `selectableOptionsCount = 1`'dir. Oluşturma UI'si bunu tek bir toggle olarak gösterir, **"Birden fazla cevaba izin ver"** (string `str425f`); kapalıyken client'ın `selectableOptionsCount = 1` gönderdiği, açıkken `selectableOptionsCount = options.size()` gönderdiği çıkarılır (inferred) (UI, keyfi bir sayısal üst sınır göstermiyor gibi — tek bir boolean string'inden çıkarıldı, oluşturma-UI kodunda bağımsız olarak onaylanmadı). Protokolün kendisi herhangi bir `0..options.size()` değerine izin verir (§4), dolayısıyla stok UI sunmasa da 1 veya "tüm seçenekler" dışında bir client-tarafı değeri mümkündür. Quizler örtük olarak tekli-seçimlidir (bir doğru cevap; oy-verene-görünür string `"Quiz • Select one correct answer"`, `str57a5`).

Oy-verene-görünür etiketler iki modu onaylar: `"Select one"` (`str3865`) vs. `"Select one or more"` (`str3866`).

---

## 12. `pollResultSnapshotMessage` / `V3`: geri dönüşsüz anlık görüntü

### 12.1 Amaç (found, `F1A`)

Canlı bir anketi başka bir sohbete yönlendirmek interaktif anketi yönlendir**mez**. `F1A` (aynı dönüştürme arayüzünü uygulayan birkaç "yönlendirme" dönüştürücüsünden biri, mesaj tipleri arasında kullanılan — desteklenmeyen tipler için sibling dönüştürücü `"Cannot forward message of type: ..."` throw eder), canlı anketi (`C13J`) bir `Dd2` nesnesine dönüştürür: soru metni, her seçeneğin ismi ve **o anki yerel oy sayısı**, ve anket/quiz tipi. Bu daha sonra `pollResultSnapshotMessage` (düz anket) veya `pollResultSnapshotMessageV3` (quiz) olarak serialize edilir ve özel bir view holder (`DWH`) ile render edilir, interaktif anket balonundan ayrı.

### 12.2 Alanlar (found, `DSF`)

`name` **1** (string), `pollVotes` **2** (repeated `PollVote` — `optionName` **1**, `optionVoteCount` **2**), `contextInfo` **3**, `pollType` **4** (oluşturmadaki aynı `PollType` enum'u).

### 12.3 Doğrulama (found, `F39`)

Oluşturmayla aynı şekilde kontroller: isim 1–5000 karakter, en az 2 seçenek, en fazla `min(AB 1408, 12)` seçenek, her seçenek ismi 1–2500 karakter. **Quiz** varyantı (`V3`) için, oy sayıları göndermede 0'a zorlanır — yönlendirilen bir quiz anlık görüntüsü hiçbir zaman sonuçları açığa çıkarmaz, sadece soru ve seçenek listesini.

---

## 13. Limit özeti

| Öğe | Limit | Kaynak |
|------|-------|--------|
| Anket/soru ismi uzunluğu | 1–5000 karakter | `F2N.A01`, `F39.A00` |
| Seçenek ismi uzunluğu | 1–2500 karakter | `F2N.A01`, `F2L.CM7`, `F39.A00` |
| Seçenek sayısı (oluşturma, anlık görüntü) | 2–min(AB **1408**, 12) | `F2N.A01`, `F39.A00` |
| Oy başına seçilen seçenekler | ≤ 12 ve ≤ `selectableOptionsCount` | `AbstractC33199EdC.A02` |
| `selectableOptionsCount` aralığı | 0–options.size() (lenient-context bypass altında 0–12, §4.1) | `F2N.A01` |
| Seçenek-hash boyutu (oy girdileri) | tam olarak 32 bayt | `AbstractC33199EdC` |

---

## 14. Feature flag'ler (id'ler çağrı noktalarında okunduğu gibi; isimler çözülmemiş)

| ID | Tip | Kontrol ettiği |
|----|------|----------|
| **1408** | int | sunucu-tarafından-ayarlanan maksimum anket seçeneği sayısı, değerden bağımsız sert client üst sınırı 12 |
| **24884** | bool | genişletilmiş bir anketin (V5/V6) almasında `endTime`'ı onurlandır; kapalı -> ileriye-uyumlu bir placeholder'a downgrade edilir |
| **24885** | int | almada `hideParticipantName` kabulünü kapılar (kesin polarite çözülmemiş) |
| **24886** | int | anket düzenleme alma kapısı; 0 -> reddedilir, hata 10016 |
| **25758** | int (truthy) | anket seçenek-ekleme alma kapısı (hata 10017); oluşturmada da tekrarlanan-trim'lenmiş-seçenek reddini kapılar |
| **31593** | bool | giden bir oyda `pollNameHash`/`lastEditStanzaId` metadata'sını damgala |
| **6772** | bool | anket oyu: paylaşılan şifreleme yardımcısı (açık) vs eski satır içi yol (kapalı) |
| **37909** | bool | belirli bir (çözülmemiş) ayrıştırma context'inde sıfır seçenekli bir ankete izin verir |
| **2321** | bool | bir oy, anket bitiş zamanından sonra olduğu için reddedildiğinde ekstra loglanan telemetri detayı |

Anketleri de etkileyen mesaj-secret-katmanı flag'leri (düzenleme use case kapısı **17811**, üretim kapıları, vb.) [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §16'da belgelenmiştir ve burada tekrarlanmaz.

---

## 15. Baileys (sadece onaylanmış gerçekler)

[WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §17, bir JavaScript implementasyonunun (`baron-baileys-v2` 1.5.17) anketlerle ilgili kısımlarını zaten kapsıyor; `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js` okunarak:

- HKDF türetimi ve `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option` use-case string'leri, `Poll Vote` için `id\0modifier` AAD'si dahil, Android client'ının literal'leriyle tam olarak eşleşiyor.
- AAD, kimlik-retry (PN/LID) ve eksik-secret işleme (ham, şifresi çözülmemiş update'e geri dönüş), bu raporda (§7) ve [WA_MESSAGE_SECRETS.md](./WA_MESSAGE_SECRETS.md) §7.2–§7.3'te açıklanan Android davranışıyla eşleşiyor.
- Okunan dosyalarda `pollUpdateMessage` (veya `encReactionMessage`, `encEventResponseMessage`, `encCommentMessage`) için bir gönderme-tarafı şifreleme yolu bulunamadı — yani o implementasyon gelen bir oyun şifresini çözebilir ama incelenen dosyalar birini şifreleyip göndermek için kod içermiyordu.

Burada zaten belirtilenlerin dışında anket-özel hiçbir şey bu pass'te bağımsız olarak yeniden doğrulanmadı (anket-oluşturma, seçenek-hash veya anket-düzenleme Baileys kodu okunmadı); burada daha fazla Baileys iddiası yapılmıyor.

---

## 16. Hata durumları

| Semptom | Sebep | Çözüm |
|---------|-------|-----|
| `poll_creation_invalid_options_count` | 2'den az veya `min(1408,12)`'den fazla seçenek | seçenekleri aralık içinde tut |
| `poll_creation_unmatched_correct_answer` | quiz `correctAnswer.optionName`, hiçbir seçeneğin ismine eşit değil | doğru cevabı tam bir eşleşmeye ayarla |
| Anket sessizce gösterilmiyor (downgrade) | bir V6 ankette `endTime`/`hideParticipantName`/`allowAddOption` ayarlı ama alıcıda eşleşen AB flag'i kapalı | gönderici-tarafı, içerikle düzeltilemez; alıcı yetenek eksikliği |
| `poll_vote_invalid_options_count` | oy, `selectableOptionsCount`'tan veya 12'den fazla seçenek seçiyor | anketin üst sınırına uy |
| `poll_update_past_end_time` | oy (veya seçenek ekleme / düzenleme) zaman damgası `endTime`'dan sonra | anket kapanmadan önce oy ver |
| `poll_update_tc_drop` | oyun `pollNameHash`/`lastEditStanzaId`'si alıcının anket görüşüyle eşleşmiyor | oy vermeden önce anket düzenleme geçmişini senkronize et |
| add-option'da hata **10017** | alıcıda AB **25758** sıfır | alıcı yetenek eksikliği |
| anket düzenlemede hata **10016** | alıcıda AB **24886** sıfır | alıcı yetenek eksikliği |
| `poll_add_option_past_end_time` | `endTime`'dan sonra eklenen seçenek | anket kapanmadan önce seçenek ekle |

---

## 17. Önemli ayrımlar

| Bu | Bununla karıştırma |
|------|----------|
| `pollCreationMessage`/V2/V3/V5/V6 (`PollCreationMessage` tipi) | `pollCreationMessageV4` (temel anketi saran `FutureProofMessage`) |
| `pollUpdateMessage` (oy, veya oy metadata'sı) | `secretEncryptedMessage`, `secretEncType=POLL_EDIT`/`POLL_ADD_OPTION` ile (anket düzenleme / seçenek ekleme) |
| `pollAddOptionMessage` (yeni seçenek payload'ı) | mesaj-secret'a bağlı olduğunda onu wire üzerinde taşıyan `secretEncryptedMessage` wrapper'ı |
| `pollResultSnapshotMessage`/V3 (statik, yönlendirilmiş) | canlı interaktif anket (`pollCreationMessage*`) |
| Seçim SHA-256(isim) hash'iyle | seçim indeksle — WhatsApp anketleri hiçbir zaman pozisyonla seçim yapmaz |
| `hideParticipantName` (UI görünüm ayarı) | oy veren anonimliği (yok — oluşturucu her zaman oy vereni çözümler) |
| `selectableOptionsCount` (tek çoklu/tekli-seçim sinyali) | ayrı bir "çoklu-seçim mi" boolean'ı (böyle bir şey yok) |

---

## 18. Komple akış (oluşturma, resimli seçenek, oy, yönlendirme)

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
|------|-------|
| AB **24885**'in kesin polaritesi (hideParticipantName kabul/downgrade) | decompiled branch yapısı tamamlanmamış |
| 2.26.41.6 için resimli-seçenek hash formülü (`nameHash`+`imageHash`) | önceki bir build'den taşındı, bu build'in kodunda yeniden türetilmedi |
| Anket-düzenleme eşleştirmesinde kullanılan sohbet-başına "sıralı seçenek yeniden adlandırma" toggle'ının arkasındaki AB flag id'si (`EOI.A01()`) | id çözülemedi |
| Anket-düzenleme seçenek karşılaştırmasının yeniden-adlandırmayan branch'i | decompiler kontrol akışının bir kısmını düşürüyor; literal decompiled form her zaman `poll_edit_invalid_edits`'e düşüyor, bu da bir no-op düzenleme için gerçek davranış olması pek muhtemel değil |
| Sıfır-seçenek bypass'ını (AB **37909**) etkinleştiren ayrıştırma-context değeri (`c33371Eg0.A00 == 1`) | tanımlanmadı (history sync vs. başka bir yol) |
| Stok oluşturma UI'sinin 1 veya "tüm seçenekler" dışında `selectableOptionsCount` değerleri gönderip gönderemediği | tek bir boolean toggle string'inden çıkarıldı, UI koduna karşı onaylanmadı |
| `MEDIA_POLL` association sayısal değerinin sürümler arasında stabilliği | 2.26.41.6'da 6 olarak bulundu; önceki bir build farklı bir değer kullandı, dolayısıyla sürümler arasında sabitlenmemeli |
</content>
