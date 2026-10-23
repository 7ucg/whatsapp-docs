<!-- src-sha1: 7a4b50013c0f196c95c57808469516becf9a34b7 -->
# WhatsApp Message Secrets — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** mesaj başına `messageSecret` (üretim, `MessageContextInfo`, yerel depo, history sync), use-case anahtar türetimi (HKDF), AES-GCM IV / AAD, şifreli eklentiler (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, `secretEncryptedMessage` düzenlemeleri), gönderen / hedef kimlik bağlama ve LID / PN retry, orphan'lar ve eksik secret fallback'leri, `<message>` stanza uzantıları (öznitelikler, `<enc>` öznitelikleri, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, companion destek kontrolü), feature flag'ler, Baileys karşılaştırması

---

## 1. Teknik olarak nedir

Daha sonra şifreli bir takip mesajı alabilecek her mesaj, kendi uçtan uca şifreli payload'ı içinde rastgele 32 baytlık bir secret taşır (`MessageContextInfo.messageSecret`). Bir takip mesajı (reaction, poll oyu, event yanıtı, yorum, düzenleme), bu secret'tan, orijinal mesajın id'sinden, orijinal göndericiden ve değiştiriciden (modifier) türetilen bir anahtarla şifrelenir. Sunucu takip mesajını sıradan bir E2E mesajı olarak iletir; ancak GCM kimlik doğrulamasını bozmadan onu okuyamaz, başka bir hedefe, kullanıcıya veya use case'e taşıyamaz. Tüm ifadeler decompile edilmiş APK'nın statik analizine dayanır; wire üzerinde hiçbir şey yakalanmadı. Tier'lar: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi. Obfuscate edilmiş isimler 2.26.41.6 içinde kararlı string'lerden yeniden çözüldü (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, use-case string'leri, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

Aynı sürüm ayrıca `<message>` stanza uzantılarını tanımlar (bölüm 10 ve sonrası): bir mesajı sınıflandıran ve yönlendiren ancak içeriğini taşımayan öznitelikler ve alt node'lar. `<meta polltype>` / `<meta event_type>` secret ile şifrelenmiş payload ile uyumlu olmak zorunda olduğundan burada birlikte ele alınırlar (7.4).

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| Crypto helper (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` şifreleme, `A04` şifre çözme (kimlik retry), `A02` hedef anahtar çözümleme |
| Şifreleme / şifre çözme parametre taşıyıcıları | `C32833ETl` / `C32854EUg` | veri, gönderen, hedef anahtar, use case / IV, payload, anahtarlar, gönderen |
| Anahtar türetimi | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, sıfır salt |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | native, 16 baytlık tag |
| AAD sağlayıcıları | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (yok) | ek veri |
| Secret üreteci | `AbstractC33322EfC.A01` | `SecureRandom`, 32 bayt |
| Secret deposu (`MessageSecretStore`) / bellekteki extra | `C35311ad` (tablo `message_secret`) / `C13G` mesajı üzerinde `C35171aP` | kalıcı kılma ve taşıma |
| Orijinal anahtar eşleyici (`ReferentialKeyUtil`) | `C43661qB.A03` | düzenlenmemiş orijinal mesajın anahtarı |
| Reaction handler'ları | `DU8` (gönderme), `F2P` dalı (alma) | `reactionMessage` / `encReactionMessage` |
| Poll oyu / event yanıtı / yorum | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Secret ile şifrelenmiş düzenlemeler (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Poll / event oluşturma (secret alma sırasında alınır) | `F2N` / `F2M` | `messageSecret` değerini FMessage içine okur |
| Proto: context / message / key | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Stanza `type` seçici | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Giden stanza katkıcıları | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` flag'ler, `F69` cap, `F6H` padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | `<message>` alt node'larını oluşturur |
| `<meta>` biriktirici | `EZV` (öznitelikler `A01`, alt node'lar `A00`) | tek bir `<meta>` node'u |
| `<enc>` öznitelik oluşturucu | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Companion destek kontrolü | `C34757F6a` + `AbstractC32927EXc` | type ve alt node izin listesi |
| Gelen spec parser'ları | `C33474Ehg` (status / regular), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | öznitelik ve alt node çıkarımı |
| WAM hata event'i | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. Mesaj başına secret

### 2.1 Nerede durur (found)

`MessageContextInfo` (`C30624DTs`), `Message` (`C30628DTw`) içinde alan **35**'tir. Burada ilgili alanlar:

| Alan | Numara | Tür | Kullanım |
|------|--------|-----|----------|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | message / int | cihaz listesi ipucu (secret ile ilgili değil) |
| `messageSecret` | **3** | bytes (32) | mesaj başına secret |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | eklenti ömrü (pin: unpin için 0 olmalı) |
| `botMessageSecret` | **6** | bytes (32) | secret'ın bot varyantı |
| `botMetadata` | **7** | message | bot bağlamı |
| `reportingTokenVersion` | **8** | uint32 | bu mesajın reporting token sürümü |
| `messageAddOnExpiryType` | **9** | enum | eklenti süre sonu |
| `messageAssociation` | **10** | message | ilişkilendirme |

History-sync taşıyıcısı `WebMessageInfo` (`C30626DTu`) kendi `messageSecret` alanına **49** sahiptir (found); mesajlar yeni bir companion'a aktarılırken kullanılır (bölüm 2.4).

### 2.2 Üretim (found, koşullar kısmen inferred)

Secret, `SecureRandom.nextBytes(byte[32])` ile üretilir (`AbstractC33322EfC.A01`). Mesaj serileştirilmeden önce eklenir:

| Yer | Koşul |
|-----|-------|
| `C33166Ecf.A06` (gönderime hazırlık) | mesajın secret'ı yok ve şunlardan en az biri: poll sınıfı `C13J`; `EZN.A01(msg)` (bot / eklenti sınıfı, chat-type flag'leri **2200**, **11104**, **19303** ile); chat sınıfı kapıları: flag **3143** ile grup, **3144** ile broadcast list, **3145** ile status, sınıf kapısı **3146**; `C35201aS.A00` (flag **3142**, self / bot chat); event mesajı `C213509Ao` |
| `AJ0` (gönderim işlemcisi) | reporting-token sürümü `C35241aW.A05()` (AB int **8860**, `AbstractC35301ac.A00` ile sınırlı) sıfırdan farklı ve mesaj sınıfı `C35241aW.A02` tarafından hariç tutulmamış (status, newsletter, seçili eklenti sınıfları) |
| `C72h`, `C34455Exe`, `EPA` | status nesneleri (`AbstractC34478Ey1.A0R`) oluşturulurken yeni bir secret alır |
| `C33437Eh4` | bot "request welcome" mesajı, yalnızca çağıranı isterse |
| `C9mW` | mesaj type 117, flag **24741**, secret yoksa |

`EZN.A01`, `C35201aS.A00` ve `3142`..`3146` kapılarının arkasındaki predicate'ler tam olarak çözülemedi; yukarıdaki liste kodun neyi kontrol ettiğini söyler, hangi kullanıcıya görünür mesajların uygun olduğunu söylemez. Secret'ı olmayan mesajlar bu istemciden şifreli eklenti alamaz (bölüm 9).

### 2.3 Yerel depolama (found)

`C35311ad`, replace semantiğiyle `message_secret(message_row_id, message_secret)` yazar (`MessageSecretStore/insertMessageSecret`) ve bir `message_row_id` için son satırı okur. FMessage onu `C35171aP` extra'sı olarak tutar (`A0L` set, `A0c` get, `A0Q` = boş değil). `AbstractC17240jU` içindeki iki işlemci (`C35161aO` ve bir anonim olan), extra dirty olduğunda ve chat uygun olduğunda onu yazar.

### 2.4 Alma tarafı doğrulama ve aktarım (found)

| Adım | Davranış |
|------|----------|
| Proto doğrulayıcı `C33475Ehh.A0V` | `message_secret` tam olarak **32** bayt olmalı, hata kodu **67**; bot varyantı (`bot_message_secret`, grup `whatsapp_security`) aynı şekilde doğrulanır |
| Poll oluşturma `F2N` | `messageSecret_` değerini yeni FMessage içine kopyalar (`A0L`) |
| Status soru yanıtları `C34838F9e` | `statusQuestionAnswerMessage` için aynı kopya |
| History sync dışa aktarım `C34388EwZ.A00` | saklanan secret'ı `WebMessageInfo.messageSecret` (49) içine yazar |
| History sync içe aktarım `C34388EwZ.C59` | onu geri kopyalar (`A0L`) |
| Yorumlar `C34387EwY` | yorum thread'i için `WebMessageInfo.messageSecret` değerinden bir `MessageContextInfo` yeniden oluşturur |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`), secret gerektiren mesajlar için (`AbstractC33322EfC.A00`: flag'e sahip ve sınıf `C35281aa` değil) `message_secret_error` **0** = eksik (hata kodu 66'ya eşlenir) veya **1** = geçersiz uzunluk (67) kaydeder.

---

## 3. Use-case anahtar türetimi

### 3.1 Formül (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = 32 baytlık sıfır salt ile extract (`AbstractC38971i1.A00(ikm, salt)`), ardından RFC 5869 expand döngüsü. HKDF temelleri: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) bölüm 5.1. 32 baytlık çıktı AES-256 anahtarı olarak kullanılır (uzunluktan çıkarım; native çağrı anahtarı `byte[]` olarak alır).

Girdiler:

| Girdi | Kaynak | Notlar |
|-------|--------|--------|
| `originalMessageId` | şifrelemede `ReferentialKeyUtil` (`C43661qB.A03`) sonrası hedefin anahtar id'si; şifre çözmede proto `targetMessageKey` içindeki anahtar id'si | düzenlenmiş bir hedef için bu **orijinal** mesaj id'sidir (`getOriginalKey` log'u) |
| `targetSender` | orijinal mesajın yazarı: saklanan gönderen (`C12300aw.A01`) | `UserJid`, yani cihaz soneki yok (tür düzeyinde; `user@server` string formu inferred) |
| `modifier` | eklentinin yazarı: gönderirken kendi hesap JID'i (`C09A.A0G`, bir LID, `CUC()` / `Ash()` ile döner), alırken zarfın gönderen JID'i | |
| `useCase` | 3.2'deki string | dört bileşen arasında ayırıcı yok |

Kendi JID'i bir LID hesap JID'idir (`C14080dr`, server `lid`, "Invalid LID" kontrolü). Hem `AnonymousClass091.Ash()` hem `CUC()` aynı alanı döndürür.

### 3.2 Use-case string'leri (found)

| Use case | Taşıyıcı | AAD | 2.26.41.6'daki Java literal'i |
|----------|----------|-----|-------------------------------|
| `Enc Reaction` | `encReactionMessage` | yok | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | yok | `F3W` |
| `Event Edit` | `secretEncryptedMessage` type 1 | yok | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` type 2 | yok | `F3Y.A00`, yalnızca flag **17811** ile |
| `Poll Edit` | `secretEncryptedMessage` type 4 | yok | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` type 5 | yok | `F3Y.A00` |
| `WASA` | bot yolu (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | iki aşamalı, 3.3 |
| `Report Token` | reporting token anahtarı | native | Java literal'i yok; `libwhatsapp.so` içinde mevcut, native olarak türetilir (3.4) |

### 3.3 Bot / WASA varyantı (found, ayrıntılar inferred)

`WASA` use case'i için türetim iki aşamalıdır ve ikincisinde use-case string'i yoktur:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA` modifier'dır, `jidB` uzak (chat) JID'dir ve bir `UserJid` olmalıdır (`WASA info jid must be a UserJid (hatch_jid)`); id, mevcutsa güncel mesaj anahtarı, yoksa hedef anahtardır (`C33285Eeb.A03` lambda'sı). Native karşılığı: `WcmBotMessageSecretAPICreateWithMessageSecret`. Meta AI bağlamı: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Reporting token anahtarı (found / inferred)

`C33364Efs.A06` ve `C33421Ego`, `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` çağırır: native nesne use case id **5** için anahtarı türetir; Java tarafı yalnızca JID raw string'lerini geçirir. `Report Token` string'i native kütüphanede bulunur; id 5'in bu string'e eşlenmesi inferred. Token ve yükleme: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. AEAD yapısı

| Öğe | Değer | Tier |
|-----|-------|------|
| Cipher | AES-GCM, native (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; şifre çözme `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Anahtar | bölüm 3'ten 32 bayt | found |
| IV | şifreleme başına **12** rastgele bayt (`SecureRandom`); şifre çözme başka her boyutu reddeder | found |
| Tag | 16 bayt; 16 sabiti her iki çağrıda da geçirilir; konum (ciphertext'e eklenmiş) Baileys decrypt'inden çıkarım | found / inferred |
| AAD | use case'e göre (3.2); sağlayıcı `C34631F1e` olduğunda `null` | found |
| Plaintext | serileştirilmiş iç proto (tablo 5) | found |
| Çıktı | `(encIv, encPayload, targetMessageKey)` üçlüsü (`C53966OMp`) | found |
| Boş sonuç | `encryption values are invalid` log'u, hata `Encryption using iJniBridge failed` | found |

Poll oyu retry'ı: oy zaten IV ve payload içeriyorsa (`C30957Dd6.A03` / `A04`) yeniden şifrelemek yerine aynı ciphertext tekrar gönderilir (found, `DUA` legacy dalı).

---

## 5. Taşıyıcılar ve plaintext'ler

| Taşıyıcı (`Message` içindeki alan) | Sınıf | Alanlar | Çözülen plaintext |
|------------------------------------|-------|---------|-------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (şifrelemeden önce temizlenir), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (repeated bytes, seçenek hash'leri) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 unknown, 1 going, 2 not going, 3 maybe), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | tam `Message` (yorum gövdesi); plaintext formu `commentMessage` **77** (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | tam `Message` |
| `reactionMessage` **46** | `DSH` | plaintext formu | düz reaction |
| `conditionalRevealMessage` **120** | yok | message-secret şeması değil (bölüm 14.1) | zamanlanmış mesajlar |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. 3 değeri bu build'de yoktur (`forNumber(3)` null döndürür, unknown sayılır ve reddedilir).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Gönderen tarafı

### 6.1 Ortak yol (found, `C33285Eeb.A03`)

1. Hedef FMessage'ı anahtarla çöz (`target message not found. Cannot proceed further` -> hata 71).
2. Secret'ını `message_secret` içinden oku; null veya uzunluk != 32 -> `message secret missing or invalid` (66).
3. Orijinal anahtar `C43661qB.A03` ile (null -> hata 0). Hedef gönderen `C12300aw.A01` ile.
4. 1:1 chat'te (`C0DZ.A0k(chat)`) hedef gönderen, modifier'ın namespace'ine dönüştürülür: modifier LID ve hedef PN -> hedef PN'den LID'e eşlenir; modifier PN ve hedef LID -> hedef LID'den PN'e eşlenir. Gruplarda dönüşüm yok.
5. Yalnızca Event Response: flag **15791**, 1:1 chat ve hesap türünde bir modifier -> modifier PN'e dönüştürülür.
6. Rastgele 12 baytlık IV, anahtarı türet (3.1), use-case AAD'si ile AES-GCM.
7. Dış `MessageKey`'i hedef gönderen ve orijinal anahtardan oluştur (`C32717EOy.A01`); taşıyıcı `targetMessageKey`, `encIv`, `encPayload` içerir.

### 6.2 Taşıyıcı başına (found)

| Taşıyıcı | Gönderimde kapı |
|----------|-----------------|
| Reaction (`DU8.ADr`) | **yalnızca** chat bir grupsa (`C0DZ.A0l`) ve `group_type == 3` ise (`C0GQ.A0A`; `CMP` içinde `isDefaultSubgroup_` değerinden set edilir, yani bir community varsayılan alt grubu, yorum inferred) ve serialization-context flag'i `A09` false ise şifrelenir. Diğer tüm chat'lerde düz `reactionMessage` gönderilir. `ReactionMessage.key` şifrelemeden önce null'lanır (anahtar dış `targetMessageKey`'e taşınır) |
| Poll oyu (`DUA.ADr`) | flag **6772** açık: paylaşılan helper, her zaman şifreli; kapalı: aynı türetim ve AAD ile legacy inline dal (hedef gönderen = kendi poll'ları için kendi LID'i, aksi halde oyun hedef anahtarından türetilen JID; modifier = kendi LID'i). `metadata` (`pollNameHash`, opsiyonel `lastEditStanzaId`) flag **31593** açıkken damgalanır |
| Event yanıtı (`DU9.ADr`) | her zaman şifreli; plaintext `EventResponseMessage` içinde `response`, `timestampMs`, `extraGuestCount` vardır |
| Yorum (`F3W.ADr`) | her zaman şifreli; plaintext tüm yorum `Message`'ıdır; hedef `CommentMessageInfo` üst anahtarıdır |
| Secret ile şifrelenmiş düzenleme (`F3Y.C5S`) | yalnızca mesajın `E2Q` türünde düzenleme bilgisi varsa ve serialization context forwarded / orphan değilse; `MESSAGE_EDIT` ayrıca flag **17811** gerektirir (aksi halde `getUseCase` fırlatır). Kendi mesaj düzenlemeleri için iki log satırı (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`) düz düzenleme olarak gönderilen durumları gösterir; tam koşul (flag'ler **37948**, **35457**) decompile sırasında kayboldu |

İç içe secret ile şifrelenmiş payload'lar her iki tarafta da reddedilir (`nested_secret_encrypted_message`).

---

## 7. Alıcı tarafı

### 7.1 Şifre çözme (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

`senderUserJid` (modifier) taşıyıcıya göre: zarf benden geliyorsa kendi LID'im; poll: gönderen JID (`c0df` veya `B4g()`); event yanıtı: 1:1'de chat kullanıcısı, aksi halde zarf kullanıcısı; yorum: yalnızca LID (`C0DZ.A0Y`: type 18, 19, 25), PN gönderen hata 0 ile başarısız olur; reaction: zarf göndereni yalnızca LID ise, aksi halde null.

### 7.2 LID / PN kimlik retry'ı (found yapı, kuyruk inferred)

İlk deneme JID'leri verildiği gibi kullanır. Başarısızlıkta helper her iki JID'i diğer namespace'e eşler (`C0YH.A0I` LID->PN, `A0F` PN->LID) ve bir kez yeniden dener; ikisi de zaten LID ise veya eşleme eksikse sonuç hata **51**'dir (decrypt failed). Retry'ın decompile edilmiş kuyruğu kısmen kayıp, bu yüzden denenen çiftlerin tam kümesi inferred. Kontrol GCM kimlik doğrulamasıdır: yanlış çift başarısız olur, doğru olan çözer.

### 7.3 Üst mesaj eksik: orphan'lar (found)

| Taşıyıcı | Üst mesaj bulunmadığında veya placeholder olduğunda davranış |
|----------|--------------------------------------------------------------|
| Reaction | FMessage type **56** ham `Message` baytlarıyla saklanır (`DdA(key, 56, ts).A02`); şifre çözme ertelenir |
| Poll oyu | `C30957Dd6.A02 = Message.toByteArray()`; çözülmeden saklanır |
| Event yanıtı | `Dd7(key, target, bytes, ts)` çözülmeden saklanır |
| Yorum | üst anahtar ve satır `-1` ile placeholder `C34671Zb` |
| Secret ile şifrelenmiş düzenleme | orphan type **5**, reason **1** (üst yok) veya **2** (placeholder) ile `DeD(MessageOrphan)` |

Üst mesaj geldiğinde yeniden oynatma beklenir (orphan'lar ham baytlarla kalıcı kılınır) ancak yeniden oynatma tetikleyicisi izlenmedi (inferred).

### 7.4 Şifre çözme sonrası doğrulama (found)

| Durum | Kontrol | Başarısızlık |
|-------|---------|--------------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType` `POLL_EDIT` olmalı | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | type `POLL_ADD_OPTION` ve `poll_add_option`'a eşit ikinci bir stanza alanı (alan çözülemedi) | `poll_add_option_stanza_invalid` (76) |
| Event düzenleme | iç mesaj type 92, ortaya çıkan anahtar dış anahtara eşit | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Poll düzenleme | iç type 66, her iki mesaj poll, aynı bitiş zamanı ve flag'ler, seçenek düzenlemeleri saklanan seçeneklerle tutarlı, zaman damgası bitiş zamanından sonra değil | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Poll seçenek ekleme | iç type 137, üst mesaj bir poll, hedef anahtar dış anahtara eşit, bitiş zamanından sonra değil | `poll_add_option_past_end_time` |
| Poll düzenleme alma | AB int **24886** sıfırdan farklı olmalı | hata 10016 ("futureproofing") |
| Poll seçenek ekleme alma | AB **25758** sıfırdan farklı olmalı | hata 10017 |
| Poll oyu | seçim poll için geçerli olmalı (`AbstractC33199EdC.A02`); oy zaman damgası poll bitiş zamanından sonra değil | `poll_update_past_end_time`, `invalid poll vote selection` |
| Poll oyu metadata'sı | `pollNameHash` + `lastEditStanzaId` saklanan poll'a karşı kontrol edilir (`C32977EZa.A01`); yokken "unstamped"; uyumsuzluk oyu düşürür | `poll_update_tc_drop` |
| Poll oyu şekli | IV tam 12 (`poll_update_invalid_vote_enc_iv`), payload mevcut, gönderen zaman damgası mevcut | hata 11 |
| Event yanıtı | anahtar, IV (12), payload mevcut; üst mesaj bir event veya sender-revoke mesajı olmalı | `parent message is not event message nor sender revoke` |

---

## 8. Gönderen / hedef bağlama

| Anahtarla bağlanan | Etki |
|--------------------|------|
| Orijinal mesaj id'si | bir ciphertext başka bir mesajda yeniden kullanılamaz |
| Hedef gönderen JID'i | farklı bir orijinal yazara atfedilemez |
| Modifier JID'i | başka bir kullanıcının eklentisi olarak replay edilemez |
| Use-case string'i | bir reaction ciphertext'i oy, yorum veya düzenleme olarak çözülmez |
| AAD (poll oyu, event yanıtı) | ayrıca `targetId` ve modifier'ı tag'e bağlar |

Bağlanmayanlar: chat JID'i, zaman damgası, ciphertext'in thread içindeki konumu, önceki eklenti sayısı. Alıcının modifier olarak kullandığı şey zarf `participant` / `from` değeridir; secret tarafından değil, E2E oturumu tarafından doğrulanır. Orijinal secret'a sahip olan herkes (bir grupta orijinal mesajı alan her katılımcı) herhangi bir modifier için anahtar türetebilir; şema relay tarafı yeniden hedeflemeyi önler, grup üyelerinin taklit etmesini (impersonation) önlemez (yapıdan çıkarım, inferred).

---

## 9. Eksik secret fallback'leri (işaretlenmedikçe found)

| Durum | Gönderen | Alıcı |
|-------|----------|-------|
| Orijinalin secret'ı yok | şifreleme başarısız (66); poll legacy yolu: `invalid message_secret secretSize` | üst mesaj mevcut, secret null: hata **66**, `parentMsgRowId`, `parentType`, `parentHasSecret` ile hata raporlayıcıya loglanır; `wam_message_secret_errors` kodu 0 |
| Secret 32 bayt değil | şifreleme reddedilir | hata **67**, WAM kodu 1 |
| Üst mesaj bulunamadı | şifreleme hatası 71 | orphan olarak saklanır (7.3) |
| Varsayılan alt grup olmayan chat'te reaction | bunun yerine düz `reactionMessage` gönderilir (secret gerekmez) | düz dal tarafından işlenir |
| flag 17811 olmadan mesaj düzenleme | `getUseCase` fırlatır (`unknown message secret encrypted type`, kod 0); flag kapalıyken gönderenin bu türden kaçınıp kaçınmadığı çözülmedi | aynı fırlatma |
| Eklenti şifre çözme başarısız | yok | eklenti gizli / kullanılamaz kalır; görünür fallback metni bulunamadı (unknown) |
| Orijinal olmadan yeni companion | yok | history sync secret'ı `WebMessageInfo.messageSecret` içinde taşır (2.4) |
| `<enc decrypt-fail="hide">` | düzenleme bilgisi olan mesajlarda set edilir (12.3) | alıcıya başarısızlık placeholder'ı göstermemesini söyler; flag'in tüketicisi çözülmedi |

---

## 10. `<message>` stanza: istemcinin eklediği şeyler

Giden alt node'lar, `C33150EcP` stanza oluşturucusuna ekleme yapan bağımsız katkıcılar (`InterfaceC35538FaZ`) tarafından oluşturulur.

### 10.1 Öznitelikler (found)

| Öznitelik | Üretici / tüketici | Değerler / anlam |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (proto'dan): `EVENT_EDIT` ile `secretEncryptedMessage` -> `event`, `POLL_EDIT` / `POLL_ADD_OPTION` ile -> `poll`; `MESSAGE_EDIT` `text` / `media`'ya düşer; reaction alanları (düz veya enc) -> `reaction`; poll güncelleme / oluşturma -> `poll`; `encEventResponseMessage` ve event -> `event` |
| `edit` | alma spec'leri `C33474Ehg` (node tag `status` gerektirir; düz `<message>` stanza'sı ile ilişkisi çözülmedi), `C23206A1f` (newsletter); ack'ler `AbstractC33465EhX.A05` | `C33474Ehg` içinde `1`, `7`, `8`; newsletter spec'inde `3` ve `8`; ack'ler `0` / boş değilse onu yansıtır; bkz. 10.2 |
| `category` | stanza, ack'ler, retry receipt'leri | `peer` peer-message yolunu seçer |
| `device_fanout` | `F6M` | hedefli birebir retry'larda `"false"` |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | transport | kimlik / yaşam döngüsü, içerik değil |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | kimlik parser'ları (`AbstractC33466EhY`, `C34763F6g`) | PN / LID / username takma adları |

### 10.2 `edit` değerleri

| Değer | Bağlam | Tier |
|-------|--------|------|
| `1` | gönderilmiş bir mesajın düzenlenmesi (`C33474Ehg.A0L` içinde parse edilir) | found |
| `2` | chat'te pin: alma yolu iç düzenleme sürümü 2'yi gerektirir (`Invalid edited version`) | özniteliğe eşleme inferred |
| `3` | newsletter mesaj düzenleme: yalnızca newsletter spec'inde parse edilir (`C23206A1f.A0G`) ve chat bir newsletter olduğunda `EWW.A01` düzenleme sürümünü 3 yapar (JID type 21, server `newsletter`) | found (önceki "unknown 3"ü çözer) |
| `7` | gönderen tarafından revoke (`C33474Ehg.A0M`) | found |
| `8` | admin silme (`C33474Ehg.A0S`, newsletter spec'i `A0H`) | found |
| `0` / boş | normal mesaj; ack'lerden çıkarılır | found |

İç düzenleme sürümü (`EWW.A01`) normal chat'ler için `1`, newsletter'lar için `3`'tür; normal chat düzenlemeleri ayrıca `decrypt-fail` hide flag'ini set eder (12.3).

### 10.3 Doğrudan alt node'lar (found)

| Alt node | Üretici | Anlam |
|----------|---------|-------|
| `enc` | şifreleme katmanı | ciphertext, bkz. bölüm 11 |
| `participants` / `to` | `F6E` ve fanout | cihaz başına ciphertext'ler |
| `device-identity` | `F6B` | imzalı cihaz kimliği |
| `registration` | parser `C33474Ehg.A04` | tam olarak 4 bayt |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | stanza başına en fazla AB int **20606**, **20605** ile etkinleştirilir |
| `cstoken` | `F6G` | cold-contact token'ı |
| `padding` | `F6H` | rastgele baytlar, `retryCount × 1571` uzunluğunda, flag'ler **8311**, **9209** (`ta_pad` de mevcut) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (16 baytlık HMAC), bkz. [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | bölüm 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | business işlemcisi `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | oluşturucudaki bir bitmask'ten boş flag node'ları: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | parser | opak ikili kategori (status) |
| `cap` | `F69` | JID type 3'e gönderimlerde `<cap client_capping_ready="true|false">` (broadcast list, inferred), flag'ler **16656** (emit) ve **13537** (değer) |
| `verified_name` | business | doğrulanmış business sertifikası |
| `unavailable`, `bypassed` | parser | işaretleyici node'lar; `unavailable` literal'i 2.26.41.6'da eşleşmedi (sabit tabanlı), burada semantiği doğrulanmadı |

---

## 11. `<enc>` node'u

### 11.1 Öznitelikler (found, `AbstractC33466EhY.A09`)

| Öznitelik | Değer | Koşul |
|-----------|-------|-------|
| `v` | `2` veya `3` | ciphertext sürümü (alma parser'ı `EncVersion2`, `EncVersion3`, futureproof kabul eder) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | Signal mesajı, prekey mesajı, sender key, `frskmsg`, bot `msmsg`, plaintext işaretleyicisi |
| `count` | retry sayısı | 0 olduğunda atlanır |
| `mediatype` | bkz. 11.2 | media / interactive sınıflandırması |
| `native_flow_name` | flow adı | native-flow mesajları |
| `duration` | int >= 0 | canlı konum |
| `decrypt-fail` | `hide` | mesaj gizlenebilir olarak işaretlenmiş (12.3) |
| `state` | `false` | ciphertext taşıyıcısındaki bir flag altında `pkmsg` gönderimleri |
| `session_type` | `pq` | post-quantum oturum taşıyıcı flag'i |
| `bucket` | string | ciphertext taşıyıcısında set edildiğinde |

Alma kontrolleri (`C33013EaB`): bir mesajdaki iki `<enc>` node'u retry sayısı ve ciphertext sürümü konusunda uyuşmalıdır; bir newsletter üzerindeki `enc` reddedilir (`Received enc message for newsletters`); `decrypt-fail=hide` yalnızca kategori `peer` değilse ve chat predicate'i `C1ZB.A0L` false ise dikkate alınır.

### 11.2 Spec tarafından kabul edilen `mediatype` değerleri (found, 37 giriş)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. `native_flow_name` enum'u (8 giriş): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. `<meta>` node'u

Tüm öznitelikler ve alt node'lar, `F6K`'nın çağırdığı handler'lar tarafından (mesaj sınıfı başına `FXq.AAl`, eklenti başına `FZH.AAl`) `EZV` içinde biriktirilir ve tek bir `<meta>` olarak yayılır (`C33150EcP.A00`). Boş biriktirici hiçbir şey yaymaz.

### 12.1 İşlem sınıflandırıcıları (found)

| Öznitelik | Değerler | Üretici |
|-----------|----------|---------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | poll handler'ları |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | event handler'ları |
| `content_type` | `C0DZ.A0U`'nun false olduğu chat'lerde eklenti sınıfı `AbstractC35181aQ` için `add_on` (reaction'ları içerir; oylar / yanıtlar inferred); status bildirimleri için `status_notify` / `add_on` | `F6K` |
| `type` | `st` (saniye, unschedule mesaj sınıfı için atlanır) ve alt node `<key rkid="...">` (anahtar baytları o sınıf için atlanır) ile `scheduled_message` | `F6K`, conditional reveal |
| `appdata` | `FZF.AVN()` serbest string'i; appdata düzenleme reddedilir | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | member-tag mesajı `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (ve diğerleri) | `AJR` |
| `message_association_type` | ilişkilendirme token'ı, ayrıca status yüklemelerinde `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | üst id / JID | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; alt node `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, ayrıca Meta AI giriş noktası string'leri (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | flag **36091** altında 1:1 chat'ler için `2` (anlamı çözülmedi) | `F6K` |
| `view_once` | flag **11282** altında view-once türleri için `true` | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (mesaj type 108) | `F6K` |
| `share_pn` | `true` (mesaj type 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | bot / thread yönlendirme | `F6K` |

### 12.2 Alırken parse edilenler (found)

İstemcinin okuduğu `<meta>` girdileri: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (yalnızca grup chat'leri), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (saniye, ms olarak saklanır), `is_wamo_sub`, `original_msg_t`, `msg_edit_t` ve alt node'lar `mention_source/to`, `mentioned_users/to`. Newsletter meta'ları ayrıca `admin_profile`, `paid_partnership`, `ai_content` ekler (önceki katalogdan listelendi; burada yeniden okunmadı, doğrulanmadı). `deprecated_lid_session` 2.26.41.6'da bulunamadı.

---

## 13. `<biz>`, `<bot>`

### 13.1 `<biz>` (found, `C34748F5r.CM3`)

```xml
<biz native_flow_name="...">                       <!-- or -->
<biz>
  <interactive type="native_flow">
    <native_flow name="..."/>
  </interactive>
  <buttons/> | <list/>
</biz>
<hsm category="..." tag="..."/>                    <!-- sibling, template classification -->
```

Alıcı flow adını okur (`native_flow_name` veya iç içe `name`), ardından sınıflandırır: `buttons` mevcut, `list` mevcut veya native flow; bir ad ve bir `hsm` kardeşi ile template olur. Doğrulama başarısızlıkları `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested` olarak adlandırılır: şifreli payload ile uyuşmayan bir `biz` sınıflandırıcısı farklı bir mesaj türü değil, bir doğrulama başarısızlığıdır. Başka yerlerde okunan diğer `biz` öznitelikleri: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, `decision_source` ile alt node `quality_control`.

### 13.2 `<bot>` (found)

Giden (`F6M`): öznitelikler `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, alt node `tee_routing` (`tee_routing_token`, `tee_ik_id`). Gelen (`C34747F5q`): `<bot edit="full|...">` varsayılan `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; `<meta target_id>` olmadan mesaj bir bot yanıtı olarak işlenmez. Ayrıntılar: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Message-secret olmayan ilgili şemalar

### 14.1 Conditional reveal (zamanlanmış mesajlar)

`conditionalRevealMessage` (alan **120**) ayrı bir rastgele reveal anahtarı kullanır (`<meta type="scheduled_message" st><key rkid>`); reveal'ı sunucu kontrol eder. `messageSecret`'tan HKDF yok. Reveal protokolünün iç işleyişi izlenmedi (unknown).

### 14.2 Reporting token

`reportingTokenVersion` (alan **8**) ve 16 baytlık `<reporting_token>`, Java HKDF'si değil, native use-case id 5 anahtarını kullanır (3.4). Token içeriği: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Companion destek doğrulayıcısı (found)

`CompanionSupportVerifier` (`C34757F6a`, yalnızca bir companion üzerinde, bir flag arkasında): `peer` olmayan mesajlar yalnızca `type` `{text, media, reaction, poll, event}` içindeyse (veya remittance `transaction` / `pay` alt node'u ile `pay`) ve her doğrudan alt node `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}` içindeyse kabul edilir. Aksi halde `unsupported child node=` / `unsupported message type=` loglar ve mesaj companion üzerinde desteklenmeyen olarak sınıflandırılır. Bir companion üzerinde `participants` içeren peer broadcast düşürülür (`received peer broadcast message on companion-mode, dropping`, nack 415 / 18). Yeni `cap` alt node'u ve `tctoken` / `cstoken` listede yoktur; bu kontrolden önce nerede işlendikleri çözülmedi. `unavailable` ve `participants` kendi yollarından geçer.

---

## 16. Feature flag'ler (id'ler çağrı noktalarında okunduğu gibi; isimler çözülmedi)

| ID | Tür | Kontrol ettiği |
|----|-----|----------------|
| **6772** | bool | poll oyu: paylaşılan helper ve legacy inline şifreleme |
| **31593** | bool | poll oyu `metadata` damgalama |
| **17811** | bool | `Message Edit` use case'i (gönderme ve alma) |
| **37948**, **35457** | bool | kendi mesaj düzenlemelerini sarmalama koşulları |
| **24886** | int | poll düzenleme alma (0 = reddedilir, 10016) |
| **25758** | int | poll seçenek ekleme alma (0 = reddedilir, 10017) |
| **15791** | bool | 1:1 chat'lerde event yanıtı modifier LID -> PN |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | chat sınıfına göre secret üretimi |
| **8860** | int | maksimum reporting-token sürümü (secret üretimi) |
| **24741** | bool | mesaj type 117 için secret |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | `cap` alt node'u ve değeri |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool / int | `tctoken` etkinleştirme / stanza başına üst sınır |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, kaynak okundu, hiçbir şey test edilmedi)

Yalnızca `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js` içinde okunan olgular.

| Konu | Baileys | Android |
|------|---------|---------|
| Anahtar | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | aynı (3.1) |
| Use case'ler | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, ayrıca enum 3 için `Message Schedule` | aynı string'ler; 3 değeri 2.26.41.6'da tanımlı değil |
| AAD | poll ve event için `id\0modifier`, düzenleme / yorum / reaction için boş | aynı |
| Kimlik | creator ve modifier'ın PN ve LID adaylarını dener, GCM doğru çifti doğrular | aynı fikir (7.2) |
| Eksik secret | loglar, ham `encReactionMessage` / `pollUpdateMessage` güncellemesini yayar, decrypt yok | orphan olarak saklanır |
| Secret üretimi | poll, event için ve `messageContextInfo.messageSecret` eksik olduğunda `randomBytes(32)` | 2.2 |
| Reporting anahtarı | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; reaction'lar, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` için reporting atlanır | native id 5 (3.4) |
| Gönderme tarafı | okunan dosyalarda `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` veya `encCommentMessage` için gönderici bulunmadı | Android dördünü de gönderir |

Koddan okunan sonuç: Baileys aldığı takip mesajlarını çözebilir ancak okunan dosyalar onlar için şifreleme içermez. Başka bir yerde bir gönderme helper'ının olup olmadığı aranmadı.

---

## 18. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| Hata 11 | IV 12 bayt değil veya boş payload / eksik alan | `encIv` kontrol et (alan 3, `PollEncValue` için 2) |
| Hata 51 | yanlış gönderen / hedef JID namespace'i (PN vs LID), yanlış orijinal id | her iki namespace'i de dene, orijinal (düzenlenmemiş) mesaj id'sini kullan |
| Düzenlenmiş bir poll için oy başarısız | anahtar id'si son düzenleme id'si değil, orijinal poll id'si olmalı | orijinal anahtarı çöz |
| PN göndericiden yorum başarısız | yorum şifre çözme LID gönderen gerektirir | LID kullan |
| Poll düzenleme / seçenek ekleme reddedildi | flag'ler **24886** / **25758** kapalı veya stanza `polltype` `secretEncType` ile uyuşmuyor | eşleşen `<meta polltype>` ve type gönder |
| Bir companion üzerinde mesaj yok sayıldı | bilinmeyen alt node veya `type` | izin listesine uy (bölüm 15) |
| `<biz>` mesajı desteklenmiyor | sınıflandırıcı payload ile uyuşmuyor | sınıflandırıcıyı payload'dan türet |

---

## 19. Temel ayrımlar

| Bu | Şu değil |
|----|----------|
| `messageSecret` (mesaj başına, rastgele, 32 bayt) | media key, sender key, app-state sync key, call key |
| Use-case anahtarı (HKDF, hedef / kullanıcı / use case başına) | secret'ın kendisi |
| `secretEncryptedMessage` (tam bir `Message` sarar) | `encReactionMessage` (bir `ReactionMessage` sarar) |
| `Poll Vote` / `Event Response` AAD = id + NUL + modifier | boş AAD'li düzenleme / yorum / reaction |
| Dış taşıyıcıdaki `targetMessageKey` | plaintext içindeki `ReactionMessage.key` (gönderimde temizlenir) |
| `meta polltype` / `event_type` (sınıflandırıcı) | şifreli payload (içerik) |
| `edit` stanza özniteliği | `secretEncType` (şifreleme use case'i) |
| `<enc>` üzerinde `decrypt-fail="hide"` | retry receipt / `retry` node'u |

---

## 20. Tam akış (poll oyu, 1:1 veya grup)

```
[Creator]                                            [Server]                      [Voter]
   │ poll creation Message                              │                             │
   │ messageContextInfo.messageSecret = random 32       │                             │
   │ store message_secret[row]                          │                             │
   │ <message type="poll"><meta polltype="creation">────▶────────────────────────────▶ stores secret
   │                                                    │                             │
   │                                                    │      select options (hashes)│
   │                                                    │      secret = store[poll]   │
   │                                                    │      key = HKDF(secret,     │
   │                                                    │        pollId‖creator‖voter │
   │                                                    │        ‖"Poll Vote")        │
   │                                                    │      iv = random 12         │
   │                                                    │      ct = GCM(key, iv,      │
   │                                                    │        PollVoteMessage,     │
   │                                                    │        aad = pollId\0voter) │
   │              <message type="poll"><meta polltype="vote">                         │
   │◀────────────────────────────────────────────────────◀ pollUpdateMessage{key,vote{ct,iv},metadata,ts}
   │ parent found? no -> orphan, keep raw bytes         │                             │
   │ validate end time, enc iv = 12                     │                             │
   │ key = HKDF(secret, pollId‖creator‖voter‖"Poll Vote")                              │
   │ GCM-decrypt, fail -> retry PN/LID pair, else 51    │                             │
   │ check option hashes ⊂ poll options, stamp match    │                             │
   │ apply vote                                         │                             │
```

---

## 21. Bilinmeyenler

| Öğe | Durum |
|-----|-------|
| `EZN.A01`, `C35201aS.A00`, flag'ler 3142-3146 için kesin predicate'ler | chat sınıfı başına kapılama görüldü, kullanıcıya görünür küme çözülmedi |
| Native use-case id tablosu (5 = Report Token dışındaki isimlerden id'lere) | okunmadı |
| GCM tag konumu ve AES anahtar boyutu | sabitlerden ve Baileys'ten çıkarım |
| Kendi `MESSAGE_EDIT`'ini sarmalı ve düz gönderme için tam koşul (flag'ler 37948, 35457) | decompiler kontrol akışını kaybetti |
| `acp="2"`, serialization flag'i `A09`, ikinci poll-add-option stanza alanının anlamı | çözülmedi |
| Parse edilmiş zarftaki `decrypt-fail="hide"` tüketicisi | flag zarfa taşınır, etkisi izlenmedi |
| Kalıcı olarak çözülemeyen bir eklentinin kullanıcıya görünür sonucu | fallback metni bulunamadı |
| `unavailable`, `bypassed`, `deprecated_lid_session` | 2.26.41.6'da yeniden doğrulanmadı |
