<!-- src-sha1: b8f7c5d44373d4a7bc19be29e7bd26af81a86f85 -->
# WhatsApp Mesaj Sırları — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** mesaj-başına `messageSecret` (üretim, `MessageContextInfo`, yerel depo, geçmiş senkronizasyonu), kullanım-senaryosu key türetimi (HKDF), AES-GCM IV / AAD, şifreli eklentiler (`encReactionMessage`, `pollUpdateMessage`, `encEventResponseMessage`, `encCommentMessage`, `secretEncryptedMessage` düzenlemeleri), gönderen / hedef kimlik bağlama ve LID / PN retry, yetimler ve eksik-sır fallback'leri, `<message>` stanza eklentileri (attribute'lar, `<enc>` attribute'ları, `<meta>`, `<biz>`, `<bot>`, `<hsm>`, `<reporting>`, `<cap>`, padding, companion desteği kontrolü), feature flag'leri, Baileys karşılaştırması

---

## 1. Teknik olarak ne

Daha sonra şifreli bir takip alabilecek her mesaj, kendi uçtan-uca şifreli payload'unda (`MessageContextInfo.messageSecret`) rastgele 32-byte'lık bir sır taşır. Bir takip (tepki, anket oyu, etkinlik yanıtı, yorum, düzenleme), o sırdan, orijinal mesajın id'sinden, orijinal gönderenden ve modifier'dan türetilen bir key ile şifrelenir. Sunucu takibi sıradan bir E2E mesajı olarak relay eder ama GCM doğrulamasını bozmadan onu okuyamaz veya başka bir hedefe, kullanıcıya veya kullanım senaryosuna taşıyamaz. Tüm ifadeler decompile edilmiş APK'nın statik analizidir; hiçbir şey wire üzerinde yakalanmamıştır. Kademeler: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi. Obfuscated isimler 2.26.41.6'da stabil string'lerden yeniden çözülmüştür (`MessageSecretCryptoHelper/`, `MessageEncUtils/`, kullanım-senaryosu string'leri, `FMessage*Protobuf/`, `SecretEncryptedMessagePreProcessor/`, `CompanionSupportVerifier/`).

Aynı release ayrıca `<message>` stanza eklentilerini de tanımlar (bölüm 10'dan itibaren): bir mesajı sınıflandıran ve yönlendiren ama içeriğini taşımayan attribute'lar ve çocuk node'lar. Burada gruplanmıştır çünkü `<meta polltype>` / `<meta event_type>`, sır-şifreli payload'la (7.4) uyuşmalıdır.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| Kripto yardımcısı (`MessageSecretCryptoHelper`) | `C33285Eeb` | `A03` şifreleme, `A04` çözme (identity retry), `A02` hedef-key çözümlemesi |
| Şifreleme / çözme parametre taşıyıcıları | `C32833ETl` / `C32854EUg` | veri, gönderen, hedef key, kullanım senaryosu / IV, payload, key'ler, gönderen |
| Key türetimi | `AbstractC33322EfC.A02` + `AbstractC38961i0.A00` | HKDF-SHA256, sıfır salt |
| AES-GCM | `JniBridge.WCIAPIGcmAesCreateEncryptedCiphertext`, `AbstractC32243E6m.A00` (`MessageEncUtils`) | native, 16-byte tag |
| AAD sağlayıcıları | `FXU`: `C34633F1g` (Poll Vote), `C34632F1f` (Event Response), `C34634F1h` (WASA), `C34631F1e` (yok) | ek veri |
| Sır üreticisi | `AbstractC33322EfC.A01` | `SecureRandom`, 32 byte |
| Sır deposu (`MessageSecretStore`) / bellek-içi ekstra | `C35311ad` (tablo `message_secret`) / mesaj `C13G`'de `C35171aP` | kalıcı hale getirme ve taşıma |
| Orijinal-key eşleyicisi (`ReferentialKeyUtil`) | `C43661qB.A03` | düzenlenmemiş orijinal mesajın key'i |
| Tepki handler'ları | `DU8` (gönderme), `F2P` dalı (alma) | `reactionMessage` / `encReactionMessage` |
| Anket oyu / etkinlik yanıtı / yorum | `DUA` / `DU9` / `F3W` | `pollUpdateMessage` / `encEventResponseMessage` / `encCommentMessage` |
| Sır-şifreli düzenlemeler (`SecretEncryptedMessagePreProcessor`) | `F3Y`, enum `E2Q` | `secretEncryptedMessage` |
| Anket / etkinlik oluşturma (alımda alınan sır) | `F2N` / `F2M` | `messageSecret`'ı FMessage'a okur |
| Proto: context / mesaj / key | `C30624DTs` / `C30628DTw` / `BD5` | `MessageContextInfo` / `Message` / `MessageKey` |
| Stanza `type` seçicisi | `AbstractC30999De0.A02` | `text media reaction poll event pay medianotify scheduled-call` |
| Çıkış stanza katkıcıları | `InterfaceC35538FaZ`: `F6K` (meta), `F6M` (bot), `F68` flag'ler, `F69` cap, `F6H` padding, `F6L` / `F6C` reporting, `F6G` cstoken, `F6I` tctoken, `F6B` device-identity, `F6X` hsm | `<message>`'ın çocuklarını inşa eder |
| `<meta>` biriktiricisi | `EZV` (attribute'lar `A01`, çocuklar `A00`) | bir `<meta>` node'u |
| `<enc>` attribute builder'ı | `AbstractC33466EhY.A09` | `v type count mediatype ...` |
| Companion desteği kontrolü | `C34757F6a` + `AbstractC32927EXc` | tip ve çocuk allowlist'i |
| Gelen spec parser'ları | `C33474Ehg` (status / normal), `C23206A1f` (newsletter), `C34747F5q` (bot), `C34748F5r` (biz) | attribute ve çocuk çıkarımı |
| WAM hata olayı | `DZ7` / `C273212s` | `wam_message_secret_errors` |

---

## 2. Mesaj-başına sır

### 2.1 Nerede yaşıyor (found)

`MessageContextInfo` (`C30624DTs`), `Message`'ın (`C30628DTw`) alanı **35**'tir. Burada ilgili alanlar:

| Alan | Numara | Tip | Kullanım |
|-------|--------|------|-----|
| `deviceListMetadata` / `deviceListMetadataVersion` | **1** / **2** | mesaj / int | cihaz listesi ipucu (sırla ilgisiz) |
| `messageSecret` | **3** | bytes (32) | mesaj-başına sır |
| `paddingBytes` | **4** | bytes | padding |
| `messageAddOnDurationInSecs` | **5** | uint32 | eklenti ömrü (pin: unpin için 0 olmalı) |
| `botMessageSecret` | **6** | bytes (32) | sırrın bot varyantı |
| `botMetadata` | **7** | mesaj | bot context'i |
| `reportingTokenVersion` | **8** | uint32 | bu mesajın reporting token versiyonu |
| `messageAddOnExpiryType` | **9** | enum | eklenti süresi dolumu |
| `messageAssociation` | **10** | mesaj | ilişki |

Geçmiş-senkronizasyonu taşıyıcısı `WebMessageInfo` (`C30626DTu`), yeni bir companion'a mesajlar dışa aktarıldığında kullanılan (bölüm 2.4) kendi `messageSecret` alanı **49**'a sahiptir (found).

### 2.2 Üretim (found, koşullar kısmen inferred)

Sır, `SecureRandom.nextBytes(byte[32])`'dir (`AbstractC33322EfC.A01`). Mesaj serileştirilmeden önce eklenir:

| Yer | Koşul |
|-------|-----------|
| `C33166Ecf.A06` (gönderime hazırlama) | mesajın sırrı yok ve şunlardan en az biri doğru: anket sınıfı `C13J`; `EZN.A01(msg)` (bot / eklenti sınıfı, sohbet-tipi flag'leriyle **2200**, **11104**, **19303**); sohbet-sınıfı gate'leri: flag **3143**'lü grup, **3144**'lü yayın listesi, **3145**'li status, sınıf gate'i **3146**; `C35201aS.A00` (flag **3142**, kendi / bot sohbeti); etkinlik mesajı `C213509Ao` |
| `AJ0` (gönderme işleyicisi) | reporting-token versiyonu `C35241aW.A05()` (AB int **8860**, `AbstractC35301ac.A00` tarafından sınırlanır) sıfır-olmayan ve mesaj sınıfı `C35241aW.A02` tarafından hariç tutulmuyor (status, newsletter, seçili eklenti sınıfları) |
| `C72h`, `C34455Exe`, `EPA` | status nesneleri (`AbstractC34478Ey1.A0R`), oluşturulduğunda taze bir sır alır |
| `C33437Eh4` | bot "request welcome" mesajı, sadece çağıranı isteyince |
| `C9mW` | mesaj tipi 117, flag **24741**, hiçbiri mevcut olmadığında |

`EZN.A01`, `C35201aS.A00` ve `3142`..`3146` gate'lerinin arkasındaki yüklemler tam olarak çözülmedi; yukarıdaki liste kodun neyi kontrol ettiğini söyler, hangi kullanıcıya-görünür mesajların uygun olduğunu değil. Sırrı olmayan mesajlar bu istemciden şifreli eklenti alamaz (bölüm 9).

### 2.3 Yerel depolama (found)

`C35311ad`, `message_secret(message_row_id, message_secret)`'i replace semantiğiyle yazar (`MessageSecretStore/insertMessageSecret`) ve bir `message_row_id` için son satırı okur. FMessage onu ekstra `C35171aP` olarak tutar (`A0L` ayarlar, `A0c` alır, `A0Q` = boş-olmayan). `AbstractC17240jU`'daki iki işleyici (`C35161aO` ve anonim biri), ekstra kirliyken ve sohbet uygunsa onu yazar.

### 2.4 Alım-tarafı doğrulaması ve transfer (found)

| Adım | Davranış |
|------|-----------|
| Proto validator `C33475Ehh.A0V` | `message_secret` tam olarak **32** byte olmalı, hata kodu **67**; bot varyantı (`bot_message_secret`, grup `whatsapp_security`) aynı şekilde doğrulanır |
| Anket oluşturma `F2N` | `messageSecret_`'i yeni FMessage'a kopyalar (`A0L`) |
| Status soru cevapları `C34838F9e` | `statusQuestionAnswerMessage` için aynı kopya |
| Geçmiş senkronizasyonu dışa aktarma `C34388EwZ.A00` | saklanan sırrı `WebMessageInfo.messageSecret`'a (49) yazar |
| Geçmiş senkronizasyonu içe aktarma `C34388EwZ.C59` | onu geri kopyalar (`A0L`) |
| Yorumlar `C34387EwY` | yorum thread'i için `WebMessageInfo.messageSecret`'tan bir `MessageContextInfo` yeniden inşa eder |

`wam_message_secret_errors` (`DZ7`, `C273212s.A00`), bir sır gerektiren mesajlar için `message_secret_error` **0** = eksik (hata koduna 66 eşlenir) veya **1** = geçersiz uzunluk (67) olarak loglar (`AbstractC33322EfC.A00`: flag'e sahip ve sınıf `C35281aa` değil).

---

## 3. Kullanım-senaryosu key türetimi

### 3.1 Formül (found, `AbstractC33322EfC.A02`)

```text
info = UTF8(originalMessageId) ‖ UTF8(targetSender.rawString) ‖ UTF8(modifier.rawString) ‖ UTF8(useCase)
prk  = HMAC-SHA256(key = 32 × 0x00, data = messageSecret)          // HKDF extract
key  = HMAC-SHA256(key = prk, data = info ‖ 0x01)                  // HKDF expand, L = 32, one block
```

`AbstractC38961i0.A00(secret, info, 32)` = 32-byte'lık sıfır salt ile extract (`AbstractC38971i1.A00(ikm, salt)`), sonra RFC 5869 expand döngüsü. HKDF temelleri: [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) bölüm 5.1. 32-byte'lık çıktı bir AES-256 key'i olarak kullanılır (uzunluktan inferred; native çağrı key'i `byte[]` olarak alır).

Girdiler:

| Girdi | Kaynak | Notlar |
|-------|--------|-------|
| `originalMessageId` | şifrelemede `ReferentialKeyUtil`'den (`C43661qB.A03`) sonra hedefin key id'si; çözmede proto `targetMessageKey`'den key id'si | düzenlenmiş bir hedef için bu **orijinal** mesaj id'sidir (`getOriginalKey` logu) |
| `targetSender` | orijinal mesajın yazarı: saklanmış gönderen (`C12300aw.A01`) | `UserJid`, cihaz eki yok (tip-seviyesi; `user@server` string formu inferred'dir) |
| `modifier` | eklentinin yazarı: gönderimde kendi hesap JID'i (`C09A.A0G`, bir LID, `CUC()` / `Ash()` tarafından döndürülür), alımda zarfın gönderen JID'i | |
| `useCase` | 3.2'den string | dört bileşen arasında ayırıcı yok |

Kendi JID, bir LID hesap JID'idir (`C14080dr`, sunucu `lid`, "Invalid LID" kontrolü). Hem `AnonymousClass091.Ash()` hem `CUC()` aynı alanı döndürür.

### 3.2 Kullanım-senaryosu string'leri (found)

| Kullanım senaryosu | Taşıyıcı | AAD | 2.26.41.6'daki Java literal'i |
|----------|---------|-----|---------------------------|
| `Enc Reaction` | `encReactionMessage` | yok | `DU8`, `F2P` |
| `Poll Vote` | `pollUpdateMessage.vote` | `targetId ‖ 0x00 ‖ modifier` | `DUA`, `C0ZG`, `C33285Eeb.A00` |
| `Event Response` | `encEventResponseMessage` | `targetId ‖ 0x00 ‖ modifier` | `DU9`, `F2P`, `C33285Eeb.A00` |
| `Enc Comment` | `encCommentMessage` | yok | `F3W` |
| `Event Edit` | `secretEncryptedMessage` tip 1 | yok | `F3Y.A00` |
| `Message Edit` | `secretEncryptedMessage` tip 2 | yok | `F3Y.A00`, sadece flag **17811** ile |
| `Poll Edit` | `secretEncryptedMessage` tip 4 | yok | `F3Y.A00` |
| `Poll Add Option` | `secretEncryptedMessage` tip 5 | yok | `F3Y.A00` |
| `WASA` | bot yolu (`C33284Eea`) | `keyId ‖ 0x00 ‖ jid` | iki-aşamalı, 3.3 |
| `Report Token` | reporting token key'i | native | Java literal'i yok; `libwhatsapp.so`'da mevcut, native türetilmiş (3.4) |

### 3.3 Bot / WASA varyantı (found, detaylar inferred)

`WASA` kullanım senaryosu için türetim iki aşamalıdır ve ikincisinde bir kullanım-senaryosu string'i yoktur:

```text
k1  = HKDF-SHA256(secret, salt = 0×32, info = "Bot Message", L = 32)      // AbstractC33322EfC.A00
key = HKDF-SHA256(k1,     salt = 0×32, info = id ‖ jidA.raw ‖ jidB.raw, L = 32)
AAD = UTF8(keyId) ‖ 0x00 ‖ UTF8(modifier.raw)                              // C34634F1h
```

`jidA`, modifier'dır ve `jidB`, bir `UserJid` olması gereken uzak (sohbet) JID'idir (`WASA info jid must be a UserJid (hatch_jid)`); id, mevcutsa şu anki mesaj key'i, aksi halde hedef key'dir (`C33285Eeb.A03` lambda'sı). Native karşılığı: `WcmBotMessageSecretAPICreateWithMessageSecret`. Meta AI context'i: [WA_META_AI.md](./WA_META_AI.md).

### 3.4 Reporting token key'i (found / inferred)

`C33364Efs.A06` ve `C33421Ego`, `JniBridge.WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)`'i çağırır: native nesne, kullanım-senaryosu id **5** için key'i türetir; Java tarafı sadece JID ham string'lerini geçirir. `Report Token` string'i native kütüphanede mevcuttur; id 5'in o string'e eşlemesi inferred'dir. Token ve yükleme: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 4. AEAD düzeni

| Öğe | Değer | Kademe |
|------|-------|------|
| Cipher | AES-GCM, native (`WCIAPIGcmAesCreateEncryptedCiphertext(key, iv, plaintext, aad, 16)`; çözme `jvidispatchOIOOOOO(6, 16L, ctx, key, iv, ciphertext, aad)`) | found |
| Key | bölüm 3'ten 32 byte | found |
| IV | şifreleme-başına **12** rastgele byte (`SecureRandom`); çözme başka herhangi bir boyutu reddeder | found |
| Tag | 16 byte; sabit 16 her iki çağrıda da geçirilir; konumu (ciphertext'e eklenir) Baileys çözmesinden inferred | found / inferred |
| AAD | kullanım senaryosu başına (3.2); sağlayıcı `C34631F1e` olduğunda `null` | found |
| Plaintext | serileştirilmiş iç proto (tablo 5) | found |
| Çıktı | `(encIv, encPayload, targetMessageKey)` üçlüsü (`C53966OMp`) | found |
| Boş sonuç | `encryption values are invalid` log'u, hata `Encryption using iJniBridge failed` | found |

Anket-oyu retry'i: oy zaten IV ve payload'u tutuyorsa (`C30957Dd6.A03` / `A04`), yeniden şifreleme yerine aynı ciphertext yeniden gönderilir (found, `DUA` eski dalı).

---

## 5. Taşıyıcılar ve plaintext'ler

| Taşıyıcı (`Message`'daki alan) | Sınıf | Alanlar | Çözülmüş plaintext |
|------------------------------|-------|--------|---------------------|
| `encReactionMessage` **56** | `DRO` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `ReactionMessage` (`DSH`): `key` **1** (şifrelemeden önce temizlenir), `text` **2**, `groupingKey` **3**, `senderTimestampMs` **4** |
| `pollUpdateMessage` **50** | `DSG` | `pollCreationMessageKey` **1**, `vote` **2** (`PollEncValue` `C30530DQc`: `encPayload` **1**, `encIv` **2**), `metadata` **3** (`C30532DQe`: `pollNameHash` **1**, `lastEditStanzaId` **2**), `senderTimestampMs` **4** | `PollVoteMessage` (`DPF`): `selectedOptions` **1** (repeated bytes, seçenek hash'leri) |
| `encEventResponseMessage` **76** | `DRN` | `eventCreationMessageKey` **1**, `encPayload` **2**, `encIv` **3** | `EventResponseMessage` (`DRP`): `response` **1** (`E2D`: 0 bilinmiyor, 1 gidiyor, 2 gitmiyor, 3 belki), `timestampMs` **2**, `extraGuestCount` **3** |
| `encCommentMessage` **71** | `DRM` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3** | tam `Message` (yorum gövdesi); plaintext form `commentMessage` **77**'dir (`DQV`: `message` **1**, `targetMessageKey` **2**) |
| `secretEncryptedMessage` **82** | `DSI` | `targetMessageKey` **1**, `encPayload` **2**, `encIv` **3**, `secretEncType` **4** | tam `Message` |
| `reactionMessage` **46** | `DSH` | plaintext form | düz tepki |
| `conditionalRevealMessage` **120** | n/a | mesaj-sırrı şeması değil (bölüm 14.1) | zamanlanmış mesajlar |

`SecretEncType` (`E2Q`): `UNKNOWN` 0, `EVENT_EDIT` **1**, `MESSAGE_EDIT` **2**, `POLL_EDIT` **4**, `POLL_ADD_OPTION` **5**. Değer 3 bu build'de mevcut değildir (`forNumber(3)` null döndürür, bilinmeyen olarak ele alınır ve reddedilir).

`MessageKey` (`BD5`): `remoteJid` **1**, `fromMe` **2**, `id` **3**, `participant` **4**.

---

## 6. Gönderen tarafı

### 6.1 Ortak yol (found, `C33285Eeb.A03`)

1. Hedef FMessage'ı key ile çözümle (`target message not found. Cannot proceed further` -> hata 71).
2. Sırrını `message_secret`'ten oku; null veya uzunluk != 32 -> `message secret missing or invalid` (66).
3. `C43661qB.A03` üzerinden orijinal key (null -> hata 0). `C12300aw.A01` üzerinden hedef gönderen.
4. 1:1 bir sohbette (`C0DZ.A0k(chat)`), hedef gönderen modifier'ın namespace'ine dönüştürülür: modifier LID ve hedef PN -> hedef, PN'den LID'e eşlenir; modifier PN ve hedef LID -> hedef, LID'den PN'e eşlenir. Gruplarda dönüşüm yoktur.
5. Sadece Event Response: flag **15791**, 1:1 sohbet ve bir hesap-tipi modifier -> modifier PN'e dönüştürülür.
6. Rastgele 12-byte IV, key türetimi (3.1), kullanım-senaryosu AAD'siyle AES-GCM.
7. Dış `MessageKey`'i hedef gönderenden ve orijinal key'den inşa et (`C32717EOy.A01`); taşıyıcı `targetMessageKey`, `encIv`, `encPayload`'ı tutar.

### 6.2 Taşıyıcı başına (found)

| Taşıyıcı | Gönderimde gate |
|---------|--------------|
| Tepki (`DU8.ADr`) | **sadece** sohbet `group_type == 3`'lü (`C0GQ.A0A`; `CMP`'de `isDefaultSubgroup_`'tan ayarlanır, yani bir topluluk varsayılan alt-grubu, yorum inferred'dir) bir grupsa (`C0DZ.A0l`) ve serileştirme-context'i flag'i `A09` yanlışsa şifrelenir. Diğer her sohbette düz `reactionMessage` gönderilir. `ReactionMessage.key`, şifrelemeden önce null'lanır (key dış `targetMessageKey`'e taşınır) |
| Anket oyu (`DUA.ADr`) | flag **6772** açık: paylaşımlı yardımcı, her zaman şifreli; kapalı: aynı türetim ve AAD ile eski inline dal (hedef gönderen = kendi anketleri için kendi LID'i, aksi halde oyun hedef key'inden türetilen JID; modifier = kendi LID'i). `metadata` (`pollNameHash`, opsiyonel `lastEditStanzaId`), flag **31593** açıkken damgalanır |
| Etkinlik yanıtı (`DU9.ADr`) | her zaman şifreli; plaintext `EventResponseMessage`'ın `response`, `timestampMs`, `extraGuestCount`'u vardır |
| Yorum (`F3W.ADr`) | her zaman şifreli; plaintext, tüm yorum `Message`'ıdır; hedef `CommentMessageInfo` ana key'idir |
| Sır-şifreli düzenleme (`F3Y.C5S`) | sadece mesaj `E2Q` tipinde düzenleme bilgisine sahipken ve serileştirme context'i iletilmemiş / yetim değilken; `MESSAGE_EDIT` ek olarak flag **17811**'e ihtiyaç duyar (aksi halde `getUseCase` fırlatır). Kendi-mesajı düzenlemeleri için iki log satırı (`sending the Message Yourself edit unwrapped`, `sending the agent reply edit unwrapped`), düz düzenlemeler olarak gönderilen durumları gösterir; tam koşul (flag'ler **37948**, **35457**) decompilasyonda kayboldu |

Nested sır-şifreli payload'lar her iki tarafta da reddedilir (`nested_secret_encrypted_message`).

---

## 7. Alıcı tarafı

### 7.1 Çözme (found, `C33285Eeb.A04`)

```text
target key  = A02(remoteSender, messageKey, proto.targetMessageKey)       // perspective flip, Ddz.A00
parent      = message store lookup (ReferentialKeyUtil)
secret      = message_secret[parent.row]                                   // null -> 66, len != 32 -> 67
checks      = IV == 12 bytes, payload non-empty (else 11), senderUserJid != null, targetSender != null
key, aad    = section 3 / 4
plaintext   = AES-GCM-decrypt(key, iv, payload, aad)                       // fail -> identity retry
```

Taşıyıcı başına `senderUserJid` (modifier): zarf kendimdense kendi LID'i; anket: gönderen JID'i (`c0df` veya `B4g()`); etkinlik yanıtı: 1:1'de sohbet kullanıcısı, aksi halde zarf kullanıcısı; yorum: sadece LID (`C0DZ.A0Y`: tip 18, 19, 25), bir PN gönderen hata 0 ile başarısız olur; tepki: sadece bir LID ise zarf gönderen, aksi halde null.

### 7.2 LID / PN identity retry (found yapı, kuyruk inferred)

İlk deneme JID'leri verildiği gibi kullanır. Başarısızlıkta yardımcı, her iki JID'i de diğer namespace'e eşler (`C0YH.A0I` LID->PN, `A0F` PN->LID) ve bir kez yeniden dener; ikisi de zaten LID'se veya eşleme eksikse sonuç hata **51**'dir (decrypt başarısız). Retry'ın decompile edilmiş kuyruğu kısmen kaybolmuştur, bu yüzden denenen çiftlerin tam kümesi inferred'dir. Kontrol GCM doğrulamasıdır: yanlış bir çift başarısız olur, doğru olanı çözer.

### 7.3 Ana eksik: yetimler (found)

| Taşıyıcı | Ana bulunamadığında veya bir placeholder olduğunda davranış |
|---------|-----------------------------------------------------------|
| Tepki | FMessage tipi **56**, ham `Message` byte'larıyla saklanır (`DdA(key, 56, ts).A02`); çözme ertelenir |
| Anket oyu | `C30957Dd6.A02 = Message.toByteArray()`; çözülmemiş saklanır |
| Etkinlik yanıtı | `Dd7(key, target, bytes, ts)`, çözülmemiş saklanır |
| Yorum | ana key ve satır `-1` ile placeholder `C34671Zb` |
| Sır-şifreli düzenleme | yetim tipi **5**, neden **1** (ana yok) veya **2** (placeholder) ile `DeD(MessageOrphan)` |

Ana geldiğinde replay beklenir (yetimler ham byte'larla kalıcı hale getirilir) ama replay tetikleyicisi izlenmedi (inferred).

### 7.4 Çözme sonrası doğrulama (found)

| Durum | Kontrol | Başarısızlık |
|------|-------|---------|
| Stanza `type=poll` + `<meta polltype="edit">` | `secretEncType`, `POLL_EDIT` olmalı | `poll_edit_message_stanza_invalid` (76) |
| `polltype="add_option"` | tip `POLL_ADD_OPTION` ve `poll_add_option`'a eşit ikinci bir stanza alanı (alan çözülmemiş) | `poll_add_option_stanza_invalid` (76) |
| Etkinlik düzenleme | iç mesaj tipi 92, ortaya çıkan key dış key'e eşit | `invalid secret encrypted message` (76) / `the resulting message key does not match outer key` |
| Anket düzenleme | iç tip 66, her iki mesaj da anket, aynı bitiş zamanı ve flag'ler, seçenek düzenlemeleri saklanan seçeneklerle tutarlı, zaman damgası bitiş zamanından sonra değil | `poll_edit_invalid_edits`, `poll_edit_invalid_option_edits`, `poll_edit_invalid_time` |
| Anket seçenek-ekleme | iç tip 137, ana bir anket, hedef key dış key'e eşit, bitiş zamanından sonra değil | `poll_add_option_past_end_time` |
| Anket düzenleme alımı | AB int **24886** sıfır-olmayan olmalı | hata 10016 ("futureproofing") |
| Anket seçenek-ekleme alımı | AB **25758** sıfır-olmayan olmalı | hata 10017 |
| Anket oyu | seçim, anket için geçerli olmalı (`AbstractC33199EdC.A02`); oy zaman damgası anket bitiş zamanından sonra değil | `poll_update_past_end_time`, `invalid poll vote selection` |
| Anket oyu metadata'sı | `pollNameHash` + `lastEditStanzaId`, saklanan ankete karşı kontrol edilir (`C32977EZa.A01`); yoksa "unstamped"; uyuşmazlık oyu düşürür | `poll_update_tc_drop` |
| Anket oyu şekli | IV tam olarak 12 (`poll_update_invalid_vote_enc_iv`), payload mevcut, gönderen zaman damgası mevcut | hata 11 |
| Etkinlik yanıtı | key, IV (12), payload mevcut; ana bir etkinlik veya bir gönderen-iptali mesajı olmalı | `parent message is not event message nor sender revoke` |

---

## 8. Gönderen / hedef bağlama

| Key tarafından bağlanan | Etki |
|------------------|--------|
| Orijinal mesaj id'si | bir ciphertext başka bir mesajda yeniden kullanılamaz |
| Hedef gönderen JID'i | farklı bir orijinal yazara atfedilemez |
| Modifier JID'i | başka bir kullanıcının eklentisi olarak replay edilemez |
| Kullanım-senaryosu string'i | bir tepki ciphertext'i bir oy, yorum veya düzenleme olarak çözülmez |
| AAD (anket oyu, etkinlik yanıtı) | ek olarak `targetId`'yi ve modifier'ı tag'e bağlar |

Bağlanmayan: sohbet JID'i, zaman damgası, thread'de ciphertext pozisyonu, önceki eklenti sayısı. Zarf `participant` / `from`, alıcının modifier olarak kullandığı şeydir; sırla değil, E2E oturumuyla doğrulanır. Orijinal sırra sahip herkes (bir grupta, orijinal mesajı alan her katılımcı), herhangi bir modifier için key türetebilir; şema relay-tarafı yeniden-hedeflemeyi engeller, grup üyeleri tarafından taklit edilmeyi değil (inşadan inferred).

---

## 9. Eksik-sır fallback'leri (işaretlenmediyse found)

| Durum | Gönderen | Alıcı |
|-----------|--------|----------|
| Orijinalin sırrı yok | şifreleme başarısız olur (66); anket eski yolu: `invalid message_secret secretSize` | ana mevcut, sır null: hata **66**, `parentMsgRowId`, `parentType`, `parentHasSecret` ile hata raportörüne loglanır; `wam_message_secret_errors` kodu 0 |
| Sır 32 byte değil | şifreleme reddedilir | hata **67**, WAM kodu 1 |
| Ana bulunamadı | şifreleme hatası 71 | yetim olarak saklanır (7.3) |
| Varsayılan-olmayan-alt-grup bir sohbette tepki | bunun yerine plaintext `reactionMessage` gönderilir (sır gerekmez) | düz dal tarafından ele alınır |
| Flag 17811 olmadan mesaj düzenlemesi | `getUseCase` fırlatır (`unknown message secret encrypted type`, kod 0); flag kapalıyken gönderenin tipi atlayıp atlamadığı çözülmedi | aynı fırlatma |
| Eklenti çözmesi başarısız | n/a | eklenti gizli / kullanılamaz kalır; hiçbir görünür fallback metni bulunamadı (unknown) |
| Orijinal olmadan yeni companion | n/a | geçmiş senkronizasyonu sırrı `WebMessageInfo.messageSecret`'te taşır (2.4) |
| `<enc decrypt-fail="hide">` | düzenleme bilgisi olan mesajlarda ayarlanır (12.3) | alıcıya bir başarısızlık placeholder'ı göstermemesini söyler; flag'in tüketicisi çözülmedi |

---

## 10. `<message>` stanza'sı: istemcinin eklediği şey

Çıkış çocukları, stanza builder'ına (`C33150EcP`) ekleyen bağımsız katkıcılar (`InterfaceC35538FaZ`) tarafından inşa edilir.

### 10.1 Attribute'lar (found)

| Attribute | Üretici / tüketici | Değerler / anlam |
|-----------|--------------------|-------------------|
| `type` | `AbstractC30999De0.A02` | `text`, `media`, `reaction`, `poll`, `event`, `pay`, `medianotify`, `scheduled-call` (proto'dan): `EVENT_EDIT`'li `secretEncryptedMessage` -> `event`, `POLL_EDIT` / `POLL_ADD_OPTION`'lı -> `poll`; `MESSAGE_EDIT`, `text` / `media`'ya düşer; tepki alanları (düz veya enc) -> `reaction`; anket güncelleme / oluşturma -> `poll`; `encEventResponseMessage` ve etkinlik -> `event` |
| `edit` | alım spec'leri `C33474Ehg` (node tag'i `status` gerektirir; düz `<message>` stanza'sıyla ilişkisi çözülmemiş), `C23206A1f` (newsletter); ack'ler `AbstractC33465EhX.A05` | `C33474Ehg`'de `1`, `7`, `8`; newsletter spec'inde `3` ve `8`; ack'ler `0` / boş olmadıkça onu yankılar; bkz 10.2 |
| `category` | stanza, ack'ler, retry receipt'leri | `peer`, eş-mesajı yolunu seçer |
| `device_fanout` | `F6M` | hedeflenmiş bire-bir retry'larda `"false"` |
| `addressing_mode`, `participant`, `recipient`, `expiration`, `offline`, `dhash`, `sts` | transport | kimlik / yaşam döngüsü, içerik değil |
| `peer_recipient_pn`, `peer_recipient_lid`, `peer_recipient_username`, `recipient_latest_lid`, `participant_username`, `sender_account_kind`, `sender_country_code`, `eph_setting` | kimlik parser'ları (`AbstractC33466EhY`, `C34763F6g`) | PN / LID / kullanıcı adı takma adları |

### 10.2 `edit` değerleri

| Değer | Context | Kademe |
|-------|---------|------|
| `1` | gönderilmiş bir mesajın düzenlemesi (`C33474Ehg.A0L`'de ayrıştırılır) | found |
| `2` | sohbette pinleme: alım yolu dahili düzenleme versiyonu 2'yi gerektirir (`Invalid edited version`) | attribute'a eşleme inferred |
| `3` | newsletter mesajı düzenlemesi: sadece newsletter spec'inde ayrıştırılır (`C23206A1f.A0G`), ve `EWW.A01`, sohbet bir newsletter olduğunda (JID tipi 21, sunucu `newsletter`) düzenleme versiyonu 3'ü ayarlar | found (bu, önceki "unknown 3"'ü çözer) |
| `7` | gönderen tarafından iptal (`C33474Ehg.A0M`) | found |
| `8` | yönetici silmesi (`C33474Ehg.A0S`, newsletter spec'i `A0H`) | found |
| `0` / boş | normal mesaj; ack'lerden çıkarılır | found |

Dahili düzenleme versiyonu (`EWW.A01`), normal sohbetler için `1`'dir ve newsletter'lar için `3`'tür; normal-sohbet düzenlemeleri ayrıca `decrypt-fail` gizleme flag'ini ayarlar (12.3).

### 10.3 Doğrudan çocuklar (found)

| Çocuk | Üretici | Anlam |
|-------|----------|---------|
| `enc` | şifreleme katmanı | ciphertext, bkz bölüm 11 |
| `participants` / `to` | `F6E` ve fanout | cihaz-başına ciphertext'ler |
| `device-identity` | `F6B` | imzalı cihaz kimliği |
| `registration` | parser `C33474Ehg.A04` | tam olarak 4 byte |
| `tctoken` | `F6I`, `AbstractC33466EhY.A01` | stanza-başına en fazla AB int **20606**, **20605** ile etkinleştirilir |
| `cstoken` | `F6G` | cold-contact token'ı |
| `padding` | `F6H` | rastgele byte'lar, `retryCount × 1571` uzunluğunda, flag'ler **8311**, **9209** (`ta_pad` de mevcut) |
| `reporting` | `F6L` / `F6C` | `<reporting><reporting_token v>` (16-byte HMAC), bkz [WA_REPORTING.md](./WA_REPORTING.md) |
| `meta` | `F6K` | bölüm 12 |
| `bot` | `F6M` | 13.2 |
| `hsm` | `F6X` | `category`: `OTP`, `TRANSACTIONAL`, `NON_TRANSACTIONAL`, `OTHER`; `tag`: `AUTHENTICATION`, `UTILITY`, `MARKETING` |
| `biz` | business işleyicisi `C34748F5r` | 13.1 |
| `automated`, `multicast`, `url_text`, `url_number` | `F68` | builder'daki bir bitmask'tan boş flag node'ları: `2` url_text, `4` url_number, `64` multicast, `128` automated |
| `rcat` | parser | opak binary kategori (status) |
| `cap` | `F69` | JID tipi 3'e (yayın listesi, inferred) gönderimlerde `<cap client_capping_ready="true|false">`, flag'ler **16656** (yayma) ve **13537** (değer) |
| `verified_name` | business | doğrulanmış-business sertifikası |
| `unavailable`, `bypassed` | parser | işaretçi node'ları; `unavailable` literal'i 2.26.41.6'da eşleşmedi (sabit-tabanlı), semantik burada doğrulanmadı |

---

## 11. `<enc>` node'u

### 11.1 Attribute'lar (found, `AbstractC33466EhY.A09`)

| Attribute | Değer | Koşul |
|-----------|-------|-----------|
| `v` | `2` veya `3` | ciphertext versiyonu (alım parser'ı `EncVersion2`, `EncVersion3`, futureproof kabul eder) |
| `type` | `msg`, `pkmsg`, `skmsg`, `frskmsg`, `msmsg`, `none` | Signal mesajı, prekey mesajı, sender key, `frskmsg`, bot `msmsg`, plaintext işaretçisi |
| `count` | retry sayısı | 0 olduğunda atlanır |
| `mediatype` | bkz 11.2 | medya / etkileşimli sınıflandırma |
| `native_flow_name` | flow adı | native-flow mesajları |
| `duration` | int >= 0 | canlı konum |
| `decrypt-fail` | `hide` | mesaj gizlenebilir olarak işaretlendi (12.3) |
| `state` | `false` | ciphertext taşıyıcısındaki bir flag altında `pkmsg` gönderimleri |
| `session_type` | `pq` | post-quantum oturum taşıyıcı flag'i |
| `bucket` | string | ciphertext taşıyıcısında ayarlandığında |

Alım kontrolleri (`C33013EaB`): bir mesajdaki iki `<enc>` node'u, retry sayısı ve ciphertext versiyonunda uyuşmalıdır; bir newsletter'da `enc` reddedilir (`Received enc message for newsletters`); `decrypt-fail=hide`, sadece kategori `peer` değilken ve sohbet yüklemi `C1ZB.A0L` yanlışken onurlandırılır.

### 11.2 Spec tarafından kabul edilen `mediatype` değerleri (found, 37 girdi)

`audio`, `avatar_sticker`, `buttons_response`, `cataloglink`, `collection`, `contact`, `contact_array`, `document`, `feed_reshare`, `genai_sticker`, `gif`, `group_history`, `history`, `image`, `instant_image`, `list_response`, `location`, `motion_photo`, `motion_video`, `music`, `native_flow_response`, `order`, `product`, `productlink`, `ptt`, `ptv`, `request_location`, `request_location_update`, `sticker`, `sticker_pack`, `story_reply`, `url`, `user_created_sticker`, `vcard`, `video`, `xma`, `1p_sticker`. `native_flow_name` enum'u (8 girdi): `a2ui_reply_action`, `account_authentication_request`, `address_message`, `api_signup`, `call_permission_request`, `form_message`, `galaxy_message`, `menu_options`. `sticker_type`: `avatar`.

---

## 12. `<meta>` node'u

Tüm attribute'lar ve çocuklar, `F6K`'nin çağırdığı handler'lar tarafından (mesaj sınıfı başına `FXq.AAl`, eklenti başına `FZH.AAl`) `EZV`'de biriktirilir ve tek bir `<meta>` olarak yayılır (`C33150EcP.A00`). Boş bir biriktirici hiçbir şey yaymaz.

### 12.1 Operasyon sınıflandırıcıları (found)

| Attribute | Değerler | Üretici |
|-----------|--------|----------|
| `polltype` | `creation`, `edit` (`F2N`), `vote` (`DUA`), `add_option` (`F2L`, `F4E`) | anket handler'ları |
| `event_type` | `creation`, `edit` (`F2M`), **`response`** (`DU9`) | etkinlik handler'ları |
| `content_type` | `C0DZ.A0U` yanlış olan sohbetlerde eklenti sınıfı `AbstractC35181aQ` (tepkiler dahil; oylar / yanıtlar inferred) için `add_on`; status bildirimleri için `status_notify` / `add_on` | `F6K` |
| `type` | `st` (saniye, unschedule mesaj sınıfı için atlanır) ve çocuk `<key rkid="...">` (bu sınıf için key byte'ları atlanır) ile `scheduled_message` | `F6K`, koşullu reveal |
| `appdata` | `FZF.AVN()`'nin serbest string'i; appdata düzenlemesi reddedilir | `F6K` |
| `tag_reason` | `user_update`, `new_member`, `rereg_recovery_request`, `rereg_recovery_response`, `user_delete` | üye-etiketi mesajı `F3F` |
| `context_source` | `channels_invitation`, `event_invitation` (ve diğerleri) | `AJR` |
| `message_association_type` | ilişki token'ı, artı status yüklemelerinde `hd_image_dual_upload`, `hevc_video_dual_upload`, `av1_video_dual_upload` | `F4G`, `F4H` |
| `premium_type` | `1` | `F4F` |
| `thread_msg_id`, `thread_msg_sender_jid` | ana id / JID | `AJT` |
| `is_status_mention` / `is_group_status_mention` | `true` | `AJS` |
| `status_setting` | `contacts`, `allowlist`, `denylist`, `customlist`; `is_group_status` `true`; çocuk `mentioned_users/to` | `F4H` |
| `origin` | `ctwa`, `group_status`, `general`, artı Meta AI giriş-noktası string'leri (`favicon`, `chat_list`, `nullstate_*`, `typeahead_*`, ...) | `F6K`, `EnumC14320eI`, `C198208bu` |
| `acp` | flag **36091** altında 1:1 sohbetler için `2` (anlamı çözülmemiş) | `F6K` |
| `view_once` | flag **11282** altında view-once tipleri için `true` | `F6K` |
| `sender_intent` | `hosted` | `F6K` |
| `usecase` | `migration` (mesaj tipi 108) | `F6K` |
| `share_pn` | `true` (mesaj tipi 73) | `F6K` |
| `receiver_account_kind` | `guest` | `F6K` |
| `collection_type` | `document`, `image`, `video`, `mixed` | `F6K` |
| `destination_id`, `conversation_thread_id`, `thread_origin`, `peripheral` | bot / thread yönlendirmesi | `F6K` |

### 12.2 Alımda ayrıştırılan (found)

İstemcinin okuduğu `<meta>` girdileri: `polltype`, `event_type`, `target_id`, `target_sender_jid`, `target_chat_jid`, `target_chat_jid_lid`, `from`, `capi` (sadece grup sohbetleri), `thread_msg_id`, `message_association_type`, `status_mentioned`, `push_eligible`, `session_scope`, `content_type`, `tm_csat_exp_ts`, `tm_csat_cooldown` (saniye, ms olarak saklanır), `is_wamo_sub`, `original_msg_t`, `msg_edit_t`, ve çocuklar `mention_source/to`, `mentioned_users/to`. Newsletter meta'ları `admin_profile`, `paid_partnership`, `ai_content`'i ekler (önceki katalogdan listelenmiştir; burada yeniden okunmadı, doğrulanmamış). `deprecated_lid_session`, 2.26.45.10 itibarıyla yokluğu doğrulanmıştır: tam decode edilmiş 2.26.45.10 ağacı ve WA Business 2.26.45.7 boyunca büyük/küçük-harf-duyarsız kapsamlı grep hiçbir tam veya yakın eşleşme bulmadı (`found`); geçişken PN→LID migration flag'inin kasıtlı bir kaldırılması olduğu inferred'dir, yeniden adlandırma değil (`inferred`).

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

Alıcı, flow adını okur (`native_flow_name` veya nested `name`), sonra sınıflandırır: `buttons` mevcut, `list` mevcut, veya native flow; bir isim ve bir `hsm` sibling'i ile bir template olur. Doğrulama başarısızlıkları şöyle adlandırılır: `InvalidTemplateMessage`, `InvalidListMessage`, `InvalidButtonMessage`, `InvalidInconsistentFlowName`, `InvalidFlowNotOwned`, `InvalidDeeplyNested`: şifreli payload'la uyuşmayan bir `biz` sınıflandırıcısı, farklı bir mesaj tipi değil, bir doğrulama başarısızlığıdır. Başka yerde okunan diğer `biz` attribute'ları: `campaign_id`, `notification_cta`, `privacy_mode_ts`, `host_storage`, `actual_actors`, `biz_bot`, `decision_source`'lu çocuk `quality_control`.

### 13.2 `<bot>` (found)

Çıkış (`F6M`): attribute'lar `type` (`request_welcome`, `prompt`, `command`, `search`, `memu_onboarding`, `memu_invoke`, `voice`, `voice_background`, `text_input`, `live_ai`, `feedback`), `client_thread_id`, `mode_selected`, `persona_type` (`1p`, `ugc`, `3p`), `local_automated_type` (`1p_partial`), `agent_engagement_type`, `is_lid`, çocuk `tee_routing` (`tee_routing_token`, `tee_ik_id`). Gelen (`C34747F5q`): `<bot edit="full|...">` varsayılan `full`, `edit_target_id`, `sender_timestamp_ms`, `type`, `client_thread_id`; `<meta target_id>` olmadan mesaj bir bot yanıtı olarak ele alınmaz. Detaylar: [WA_META_AI.md](./WA_META_AI.md).

---

## 14. Mesaj-sırrı olmayan ilgili şemalar

### 14.1 Koşullu açığa çıkarma (zamanlanmış mesajlar)

`conditionalRevealMessage` (alan **120**), ayrı bir rastgele açığa-çıkarma key'i kullanır (`<meta type="scheduled_message" st><key rkid>`); sunucu açığa çıkarmayı kontrol eder. `messageSecret`'ten HKDF yok. Açığa-çıkarma protokolü dahili işleyişi izlenmedi (unknown).

### 14.2 Reporting token'ı

`reportingTokenVersion` (alan **8**) ve 16-byte'lık `<reporting_token>`, Java HKDF değil, native kullanım-senaryosu id 5 key'ini (3.4) kullanır. Token içeriği: [WA_REPORTING.md](./WA_REPORTING.md).

---

## 15. Companion desteği doğrulayıcısı (found)

`CompanionSupportVerifier` (`C34757F6a`, sadece bir companion'da, bir flag'in ardında): `peer`-olmayan mesajlar, sadece `type`, `{text, media, reaction, poll, event}` içindeyse (veya bir remittance `transaction` / `pay` çocuğuyla `pay`) ve her doğrudan çocuk, `{registration, enc, device-identity, verified_name, url_text, url_number, padding, biz, meta, automated, multicast, rcat, reporting, bot, hsm}` içindeyse kabul edilir. Aksi halde `unsupported child node=` / `unsupported message type=` loglar ve mesaj companion'da desteklenmiyor olarak sınıflandırılır. Bir companion'da `participants`'lı bir eş yayını düşürülür (`received peer broadcast message on companion-mode, dropping`, nack 415 / 18). Yeni `cap` çocuğu ve `tctoken` / `cstoken` listede değildir; bu kontrolden önce nasıl ele alındıkları çözülmedi. `unavailable` ve `participants` kendi yollarından geçer.

---

## 16. Feature flag'leri (çağrı noktalarında okunan id'ler; isimler çözülmemiş)

| ID | Tip | Kontrol ettiği |
|----|------|----------|
| **6772** | bool | anket oyu: paylaşımlı yardımcı vs eski inline şifreleme |
| **31593** | bool | anket oyu `metadata` damgalaması |
| **17811** | bool | `Message Edit` kullanım senaryosu (gönderme ve alma) |
| **37948**, **35457** | bool | kendi mesaj düzenlemelerini sarma koşulları |
| **24886** | int | anket düzenleme alımı (0 = reddedildi, 10016) |
| **25758** | int | anket seçenek-ekleme alımı (0 = reddedildi, 10017) |
| **15791** | bool | 1:1 sohbetlerde etkinlik yanıtı modifier LID -> PN |
| **3142**-**3146**, **2200**, **11104**, **19303** | bool | sohbet sınıfına göre sır üretimi |
| **8860** | int | maksimum reporting-token versiyonu (sır üretimi) |
| **24741** | bool | mesaj tipi 117 için sır |
| **36091** | bool | `meta acp="2"` |
| **11282** | bool | `meta view_once` |
| **16656**, **13537** | bool | `cap` çocuğu ve değeri |
| **8311**, **9209** | bool | padding |
| **20605**, **20606** | bool / int | `tctoken` etkinleştirme / stanza-başına üst sınır |

---

## 17. Baileys (`baron-baileys-v2` 1.5.17, kaynak okundu, hiçbir şey test edilmedi)

Sadece `src/Utils/process-message.js`, `src/Utils/reporting-utils.js`, `src/Utils/messages.js`, `src/Socket/messages-send.js`'de okunan gerçekler.

| Konu | Baileys | Android |
|-------|---------|---------|
| Key | `key0 = HMAC-SHA256(key = 0×32, secret)`; `decKey = HMAC-SHA256(key = key0, id ‖ creator ‖ modifier ‖ useCase ‖ 0x01)` | özdeş (3.1) |
| Kullanım senaryoları | `Poll Vote`, `Event Response`, `Enc Comment`, `Enc Reaction`, `Event Edit`, `Message Edit`, `Poll Edit`, `Poll Add Option`, artı enum 3 için `Message Schedule` | aynı string'ler; değer 3, 2.26.41.6'da tanımlanmamış |
| AAD | anket ve etkinlik için `id\0modifier`, düzenleme / yorum / tepki için boş | aynı |
| Kimlik | yaratıcının ve modifier'ın PN ve LID adaylarını dener, GCM doğru çifti doğrular | aynı mantık (7.2) |
| Eksik sır | loglar, ham `encReactionMessage` / `pollUpdateMessage` güncellemesini yayar, çözme yok | yetim olarak saklanır |
| Sır üretimi | anket, etkinlik ve `messageContextInfo.messageSecret` eksikken `randomBytes(32)` | 2.2 |
| Reporting key'i | `hkdf(secret, 32, { info: id ‖ sender ‖ modifier ‖ 'Report Token' })`; reporting tepkiler, `encReactionMessage`, `encEventResponseMessage`, `pollUpdateMessage` için atlanır | native id 5 (3.4) |
| Gönderme tarafı | okunan dosyalarda `pollUpdateMessage`, `encReactionMessage`, `encEventResponseMessage` veya `encCommentMessage` için hiçbir gönderen bulunamadı | Android dördünü de gönderir |

Koddan okunan sonuç: Baileys, aldığı takipleri çözebilir ama okunan dosyalar onlar için hiçbir şifreleme içermiyor. Bir gönderme yardımcısının başka yerde var olup olmadığı araştırılmadı.

---

## 18. Hata durumları

| Belirti | Neden | Düzeltme |
|---------|-------|-----|
| Hata 11 | IV 12 byte değil veya boş payload / eksik alan | `encIv`'i kontrol et (alan 3, veya `PollEncValue` için 2) |
| Hata 51 | yanlış gönderen / hedef JID namespace'i (PN vs LID), yanlış orijinal id | her iki namespace'i de yeniden dene, orijinal (düzenlenmemiş) mesaj id'sini kullan |
| Düzenlenmiş bir anket için oy başarısız olur | key id, orijinal anket id'si olmalı, en son düzenleme id'si değil | orijinal key'i çözümle |
| Bir PN göndereninden yorum başarısız olur | yorum çözme bir LID gönderen gerektirir | LID'i kullan |
| Anket düzenleme / seçenek-ekleme reddedildi | flag'ler **24886** / **25758** kapalı, veya stanza `polltype`, `secretEncType`'la uyuşmuyor | eşleşen `<meta polltype>` ve tipi gönderin |
| Bir companion'da mesaj göz ardı edildi | bilinmeyen çocuk node'u veya `type` | allowlist'e uyun (bölüm 15) |
| `<biz>` mesajı desteklenmiyor | sınıflandırıcı payload'la uyuşmuyor | sınıflandırıcıyı payload'dan türetin |

---

## 19. Ayırt edilmesi gereken noktalar

| Bu | Bu değil |
|------|----------|
| `messageSecret` (mesaj-başına, rastgele, 32 byte) | medya key'i, sender key'i, app-state senkronizasyon key'i, çağrı key'i |
| Kullanım-senaryosu key'i (HKDF, hedef / kullanıcı / kullanım senaryosu başına) | sırrın kendisi |
| `secretEncryptedMessage` (tam bir `Message`'ı sarar) | `encReactionMessage` (bir `ReactionMessage`'ı sarar) |
| `Poll Vote` / `Event Response` AAD = id + NUL + modifier | boş AAD'li düzenleme / yorum / tepki |
| Dış taşıyıcıdaki `targetMessageKey` | plaintext içindeki `ReactionMessage.key` (gönderimde temizlenir) |
| `meta polltype` / `event_type` (sınıflandırıcı) | şifreli payload (içerik) |
| `edit` stanza attribute'u | `secretEncType` (şifreleme kullanım senaryosu) |
| `<enc>` üzerinde `decrypt-fail="hide"` | retry receipt'i / `retry` node'u |

---

## 20. Tam akış (anket oyu, 1:1 veya grup)

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
|------|-------|
| `EZN.A01`, `C35201aS.A00`, flag'ler 3142-3146 için tam yüklemler | sohbet-sınıfı-başına gating görüldü, kullanıcıya-görünür küme çözülmedi |
| Native kullanım-senaryosu id tablosu (5 = Report Token dışındaki isimler-id eşlemeleri) | okunmadı |
| GCM tag konumu ve AES key boyutu | sabitlerden ve Baileys'ten inferred |
| Kendi `MESSAGE_EDIT`'in sarılmış vs düz gönderilmesi için tam koşul (flag'ler 37948, 35457) | decompiler kontrol akışını kaybetti |
| `acp="2"`'nin anlamı, serileştirme flag'i `A09`, ikinci anket-seçenek-ekleme stanza alanı | çözülmedi |
| Ayrıştırılan zarfta `decrypt-fail="hide"`'ın tüketicisi | flag zarfa taşındı, etki izlenmedi |
| Kalıcı olarak çözülemeyen bir eklentinin kullanıcıya-görünür sonucu | hiçbir fallback metni bulunamadı |
| `unavailable`, `bypassed` | 2.26.41.6'da yeniden doğrulanmadı |
| `deprecated_lid_session` | 2.26.45.10 itibarıyla yokluğu doğrulandı (kapsamlı grep, hem WhatsApp hem WA Business ağaçları); kaldırma vs. yeniden adlandırma `inferred`'dir, kanıtlanmamış |
