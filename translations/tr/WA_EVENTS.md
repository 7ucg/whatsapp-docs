<!-- src-sha1: c9f42e3645bee848584358bb7a4660a293218e2e -->
# WhatsApp Etkinlikler — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** takvim tarzı Etkinlikler (`eventMessage`, `eventInviteMessage`, `eventCoverImage`), şifreli RSVP (`encEventResponseMessage` / `EventResponseMessage`), "Events v2" uygulama alt sistemi (`com.whatsapp.eventsv2.*`: yerel DB, GraphQL senkronizasyonu, MEX push bildirimleri, kapak resmi pipeline'ı, davet-linki/QR), yaşam döngüsü (oluşturma/düzenleme/iptal/silme/ayrılma), RSVP durumları, davetli/konum görünürlük kuralları, grup vs 1:1 vs community bağlamı, companion-cihaz kısıtlaması, GraphQL op kataloğu, hatırlatıcılar

---

## 1. Nedir

Bir "Etkinlik" (`Event`), bir 1:1 sohbete, bir gruba gönderilebilen veya bağımsız bir link/QR ile paylaşılabilen, davetlilerin RSVP (Katılıyorum / Belki / Katılmıyorum) verebildiği takvim tarzı bir nesnedir (ad, açıklama, zaman aralığı, konum, isteğe bağlı video/sesli arama linki). Özellik aynı anda iki wire yüzeyi üzerinden gönderilir: transkriptte davet kartını render eden sıradan bir E2E-şifreli sohbet mesajı (`Message.eventMessage` / `Message.eventInviteMessage`) ve sohbet geçmişinden bağımsız olarak yerel bir etkinlikler veritabanını senkronize tutan paralel bir GraphQL + MEX-push kontrol düzlemi (`com.whatsapp.eventsv2.*`, 2.26.41.6'da yeni paket). RSVP kriptografisi (HKDF use case "Event Response", AES-GCM) reaksiyonlar/anketler/yorumlarla paylaşılır ve `WA_MESSAGE_SECRETS.md` içinde belgelenmiştir; bu rapor yalnızca etkinlik-modeli ve yaşam döngüsü katmanını kapsar.

| Varlık | `Message` alanı | Tip (obf.) | Rol |
|--------|-----------------|-------------|------|
| `eventMessage` | **75** | `EventMessage` | temel takvim etkinliği, bir sohbete gönderilir |
| `encEventResponseMessage` | **76** | `EncEventResponseMessage` (`DRN`) | şifreli RSVP takip mesajı |
| `eventCoverImage` | **85** | `FutureProofMessage` | genel wrapper, kapak fotoğrafını iç içe bir `imageMessage` olarak taşır |
| `eventInviteMessage` | **122** | `EventInviteMessage` (`DTQ`) | "Events v2" davet kartı, `eventMessage`'ın üst kümesi |
| `eventResponses` (repeated) | **61**, `WebMessageInfo`-eşdeğeri üzerinde (`C30626DTu`) | `EventResponse` | history sync'te taşınan davetli-başına RSVP özeti |
| `eventAdditionalMetadata` | **64**, aynı host | `EventAdditionalMetadata` | tek bir `isStale` bool |

Tüm proto alanları ve aşağıdaki RSVP plaintext alanları, 2.26.41.6 sınıflarından (`DRP`, `DRN`, `DU9`, `E2D`, `C9T8` — **found**) doğrudan yeniden okundu ve `Tools/proto-extractor/research/2.26.41.6/whatsapp-deobfuscated.proto` içindeki üst seviye `Message` konteyneriyle çapraz kontrol edildi. Tier'lar: **found** = kodda/string'lerde okundu, **inferred** = çıkarıldı, **unknown** = çözülemedi.

---

## 2. `EventMessage` (alan 75) — temel etkinlik

2.26.35.2 dönemi kataloğundan değişmedi; 2.26.41.6'da hâlâ 12 alan.

| Alan | # | Tip | Notlar |
|-------|---|------|-------|
| `contextInfo` | 1 | `ContextInfo` | standart alıntılama/mention taşıyıcısı |
| `isCanceled` | 2 | bool | iptal eylemi tarafından ayarlanır |
| `name` | 3 | string | etkinlik başlığı |
| `description` | 4 | string | |
| `location` | 5 | `Message.LocationMessage` | statik konum pini (lat/long/ad/adres), *canlı değil* |
| `joinLink` | 6 | string | genel katılma URL'si (legacy alan; yeni etkinlikler için Events v2 davet linki tarafından ikame edilir) |
| `startTime` | 7 | int64 | unix saniye |
| `endTime` | 8 | int64 | unix saniye |
| `extraGuestsAllowed` | 9 | bool | "+1" anahtarı |
| `isScheduleCall` | 10 | bool | "Bir arama planla" giriş noktası için kullanılan aynı model |
| `hasReminder` | 11 | bool | |
| `reminderOffsetSec` | 12 | int64 | `startTime`'dan önceki saniye |

`reminderOffsetSec`, sabit bir picker'dan (`EventReminderBottomSheet`, string'ler **found**) doldurulur: "Asla", "Etkinlik zamanı", "15 dakika önce", "30 dakika önce", "1 saat önce", "1 gün önce". 0/900/1800/3600/86400-saniye eşlemesi **inferred**'dir (literal olarak okunmadı; picker'ın seçenek-saniye tablosu, jadx'in constant pool'unu çözemediği bir sınıfta — `BXa`/`C27637BzN` — yer alıyor).

---

## 3. `EventInviteMessage` (alan 122, obf. `DTQ`) — "Events v2" daveti

Sürümler arasında 9'dan 13 alana büyüdü; 2.26.41.6 13'ünü de taşıyor. **Başlangıç materyaline düzeltme**: commit edilmiş `Messages/eventInviteMessage/info.md` (2.26.35.2'de yakalanmış) alan 9'da (`callLink`) duruyor ve 10–13 alanlarından yoksun; bu alanların bu build'de mevcut olduğu `DTQ`'nun doğrudan okunmasıyla doğrulandı:

| Alan | # | Tip | Eklendi | Notlar |
|-------|---|------|-------|-------|
| `contextInfo` | 1 | `ContextInfo` | base | |
| `eventId` | 2 | string | base | sunucu tarafından atanan etkinlik id'si |
| `eventTitle` | 3 | string | base | |
| `jpegThumbnail` | 4 | bytes | base | satır içi kapak küçük resmi |
| `startTime` | 5 | int64 | base | |
| `caption` | 6 | string | base | |
| `isCanceled` | 7 | bool | base | |
| `endTime` | 8 | int64 | base | |
| `callLink` | 9 | string | base | `https://call.whatsapp.com/video/...` tarzı |
| `coverImageHandle` | 10 | string | 2.26.38.10 | satır içi `jpegThumbnail`'a alternatif, medya-handle referansı |
| `locationName` | 11 | string | 2.26.38.10 | okunabilir konum etiketi |
| `lastUpdatedTsUsec` | 12 | int64 | 2.26.38.10 | mikrosaniye; her `UpdateEvent`'te ilerler |
| `status` | 13 | int32 (açık enum) | **2.26.41.6** | etkinlik seviyesi durum; enum sınıfı statik olarak kurtarılamıyor |

`status` (13), bu sürümdeki tek yeni wire alanı. Enum üye adları proto seviyesinde **unknown** — jadx bu açık-enum int32'nin arkasındaki sınıfı kurtaramadı. Ancak ilgili `rsvp_status`/`UpdateEvent.status` değişkenleri için kullanılan GraphQL-yüzü durum kelime dağarcığı bağımsız olarak kurtarıldı (§6) ve aynı semantik için makul ama doğrulanmamış bir kandidat; ikisinin aynı wire gösterimini paylaştığı kanıtlanmış değil.

---

## 4. `eventCoverImage` (alan 85) — kapak fotoğrafı wrapper'ı

`FutureProofMessage { optional Message message = 1; }` — `lottieStickerMessage`, `statusMentionMessage` vb. için kullanılan aynı genel wrapper. Etkinliğe özgü alan yok; iç içe `message` sıradan bir `imageMessage` taşır. Tüketici kodu (`EventCoverImageLoader`, `EventCoverImageThumbnailCreator`, `EventCoverImageUrlResolver`) bunu normal bir resim eki olarak ele alır — genel wrapper açma dışında ek bir doğrulama bulunamadı.

Events v2 ayrıca kullanıcı-yüklemeli bir fotoğrafa alternatif olarak **preset** kapak resimlerini destekler (`EventPresetCoverImagesRepository`, GraphQL ile çekilen katalog, `CreateEvent`/`UpdateEvent` üzerindeki `cover_image_blob`/`is_preset_image` değişkenleri).

---

## 5. RSVP: `encEventResponseMessage` ve `EventResponseMessage`

### 5.1 Wire şekli (found, `DRN`/`DRP`/`E2D` doğrudan okundu)

| Taşıyıcı | Alan | # | Tip |
|---------|-------|---|------|
| `EncEventResponseMessage` (`DRN`, alan 76) | `eventCreationMessageKey` | 1 | `MessageKey` (`BD5`) |
| | `encPayload` | 2 | bytes |
| | `encIv` | 3 | bytes |
| `EventResponseMessage` (`DRP`, AES-GCM plaintext'i) | `response` | 1 | enum `E2D` |
| | `timestampMs` | 2 | int64 |
| | `extraGuestCount` | 3 | int32 |

`E2D` değerleri (found, `E2D.java`): **0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE**.

Bu, doğrudan `WA_MESSAGE_SECRETS.md` §"encEventResponseMessage **76**"'yı doğrular ve otomatik çıkarılmış proto dump'ındaki (`Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`, kendi metninde belirtilen bir alan-adı-kurtarma hatası nedeniyle — "alan #3'te eksik ad yuvası" — `EventResponseMessage`'ı `timestampMs=1, extraGuestCount=2, field3=3` olarak listeleyen) bir çatışmayı çözer. Doğrudan sınıf okuması (`DRP`'nin `BUILD_MESSAGE_INFO` alan-sırası string'i ve `RESPONSE_FIELD_NUMBER=1`/`TIMESTAMP_MS_FIELD_NUMBER=2`/`EXTRA_GUEST_COUNT_FIELD_NUMBER=3` sabitleri) bunu çözüme kavuşturur: **`response` alan 1'dir, alan 3 değil.**

### 5.2 Gönderme yolu (found, `DU9.ADr`)

`DU9` (event-response use-case handler'ı, `F2P`'yi extend eder), bir uygulama-seviyesi `C9T8` enum'undan (`UNKNOWN=0, GOING=1, NOT_GOING=2, MAYBE=3` — `E2D` ile sayısal olarak aynı, `EW0.A01` converter'ı üzerinden düz bir 1:1 mirror olduğunu doğrular) ve bir timestamp ile `extraGuestCount` int'inden bir `DRP` inşa eder, bunu `MessageSecretCryptoHelper` (`C33285Eeb.A03`) üzerinden HKDF use case `"Event Response"` ile şifreler, ve ciphertext/IV/orijinal-mesaj-key'ini bir `DRN`'ye sarar. `AAl()`, giden stanza'nın `<meta event_type="response">`'unu damgalar. Kripto detayı (HKDF türetimi, AES-GCM, AAD = `targetId‖0x00‖modifier`, sender/LID retry) **burada tekrarlanmıyor** — bkz. `WA_MESSAGE_SECRETS.md` §2–9, 16.

### 5.3 Üç RSVP-şekilli enum daha (found) — bir gotcha

Wire enum'u `E2D` ve onun mirror'ı `C9T8`'in yanında, uygulama **farklı üye sıralamalarına** sahip en az üç *başka* RSVP-durumu enum'u tanımlıyor, her biri farklı bir katmanda kullanılıyor:

| Enum (obf.) | Üyeler (ordinal) | Kullanım yeri |
|---|---|---|
| `E2D` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | wire plaintext'i `EventResponseMessage.response` |
| `C9T8` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | `E2D`'nin uygulama-seviyesi mirror'ı, `DU9.ADr`'a geçirilir |
| `C9T6` | 0 GOING, 1 NOT_GOING, 2 MAYBE, 3 NO_RESPONSE | yerel `dbValue` sıralaması (`EventRsvpBottomSheet`, yerel DB), **UNKNOWN yuvası yok**, onun yerine `NO_RESPONSE` var |
| `C9U0` | `serverValue` string'leri: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `GOING`, `MAYBE`, `NOT_GOING`, `NO_RESPONSE` | GraphQL `rsvp_status` değişkeni (`UpdateEventRsvp`, `JoinEventViaLink`) |

Bu, `Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`'de GraphQL yüzeyi için belirtilen "RSVP enum unknown" boşluğunun bir kısmını çözer: `rsvp_status` **GraphQL** değişkeni literal string'leri `GOING` / `MAYBE` / `NOT_GOING` / `NO_RESPONSE` alır (found, `C9U0.serverValue`, `"rsvp_status"` anahtarını okuyan tüketici `C207188s3.B2x()`). Wire-proto `EventInviteMessage.status` (alan 13, §3) enum sınıfı kurtarılamamış durumda ve bu kelime dağarcığını paylaştığı **kanıtlanmamış**.

Beşinci, ayrı bir integer "durum etiketi" değerleri seti (found, `C2115191e.A00`, sohbet-yönlendirme/önizleme çipi için kullanılır) `1 GOING, 2 GOING_WITH_GUEST, 3 NOT_GOING, 4 MAYBE, 5 NOT_RESPONDED, 6 CANCELED, default CREATOR`'ı eşler — bir wire değeri değil, bir UI debug/görüntüleme etiketi seti.

---

## 6. Events v2 GraphQL yüzeyi (`www` şeması, found doc_id'ler)

Yayınlanan `whatsapp-android-www_client_persist_ids.json`'da 16 persisted operasyon mevcut; değişkenler APK call site'larından kurtarıldı (bu raporun yeniden türetmek yerine çapraz kontrol ettiği `Querys/www/guides/events.md`'de belgelenmiştir).

| Op | doc_id | Op | doc_id |
|----|--------|----|--------|
| `CreateEvent` | `27122934507384369` | `UpdateEvent` | `27442441785378771` |
| `DeleteEvent` | `24671535952543811` | `UpdateEventRsvp` | `27592470423757790` |
| `GetEvent` | `27529572846713636` | `ListEvents` | `27633532006268526` |
| `GetEventCoverImage` | `28048111841543330` | `AddEventInvitations` | `28162575909992756` |
| `GetEventLinkPreview` | `27639296169058396` | `RemoveEventInvitations` | `27696932319970038` |
| `GetOrCreateEventInviteLink` | `26392982740362906` | `RemoveSelfEventInvitation` | `27063717026648637` |
| `JoinEventViaLink` | `27669318929396727` | `RotateEventInviteLink` | `27134834146102810` |
| `ValidateCachedEventIDs` | `27508030125525954` | mex `LogEventInviteCreate` | `27409709725288255` |

Kurtarılan önemli değişkenler (found): `CreateEvent`/`UpdateEvent`, `chat_jid`, `description`, `max_additional_guests`, `is_group_based_event`, `is_shareable`, `cover_image_handle`/`cover_image_blob`/`is_preset_image`, `location_address`/`location_web_url`, `call_link_media_type`, `call_link_waiting_room_enabled` alır; `UpdateEvent` ek olarak `clear_location`, `clear_location_coordinates`, `hide_invitee_list`, `link_id`, `status` alır. `UpdateEventRsvp`/`JoinEventViaLink`, `event_id`/`link_token`, `rsvp_status`, `extra_guest_count` alır. Taşıma `inferred`'dir (persisted-`doc_id` POST, diğer `www` op'larıyla aynı desen); hiçbir trafik yakalanmadı.

### 6.1 MEX push bildirimleri (found, yukarıdaki GraphQL pull'dan ayrı)

`DefaultEventsNotificationRepository`, iki **MEX** push payload şemasını ayrıştırır — `xwa2_notify_event_on_invite` ve `xwa2_notify_event_on_update` (throw edilen exception'larda literal node adları, found) — `start_ts_sec`, `cover_image.handle`/`cover_image.uri`, konum ve call-link alanlarını taşır, ve bunları doğrudan yerel etkinlikler DB'sine upsert eder (`DefaultLocalEventsDataSource.upsertEvents`). Bu, bir etkinliğin bir cihazın yerel Etkinlikler listesinde, cihaz onun için sohbet-mesajı düzlemini (`eventMessage`/`eventInviteMessage`) **hiç almadan** görünebileceği anlamına gelir — sunucu, sohbet teslimatından bağımsız olarak davet/güncelleme bildirimlerini MEX üzerinden aktif olarak push eder. İlk davette, yerel RSVP durumu varsayılan olarak `NO_RESPONSE`'a döner (`C9T6.A05.dbValue`).

---

## 7. Yerel depolama ve legacy bridge

`EventsDatabaseDataSource` (Room tarzı yerel DB), Events v2 için kanonik store'dur; `GraphqlEventsDataSource`, §6'daki op'lardan onu doldurur; `FMessageEventsDataSource`, **eski** sohbet-mesajı-sadece modelini (`eventMessage`/`eventInviteMessage`, düz `FMessage` satırları olarak, sınıf `C213509Ao` — ayrıca `WA_MESSAGE_SECRETS.md` §"prepare send"e göre etkinlik mesajları için `messageSecret` üretimini gate'leyen sınıf) UI'nın tükettiği aynı `observeEventPreviews()` stream'ine bridge'ler. Pratikte: daha eski bir client tarafından (veya Events v2 var olmadan önce) oluşturulan bir etkinlik hâlâ sohbet mesajından render edilir; bir Events-v2 ile oluşturulan etkinlik DB-destekli ve GraphQL-senkronizeli'dir, sohbet mesajı paylaşılabilir davet kartı olarak işlev görür.

---

## 8. Yaşam döngüsü eylemleri

| Eylem | Kim | Mekanizma | Etki |
|--------|-----|-----------|--------|
| **Oluşturma** | herhangi bir sohbet üyesi (grup) / her iki taraf (1:1) / QR-uygun bir bağlama sahip herkes | `CreateEvent` (GraphQL), ardından sohbete gönderilen `eventInviteMessage` | sunucu `eventId` atar; `EventComposerFragment` ad/açıklama/zaman/konum/kapak/hatırlatıcı/davetli anahtarı/call-link medya tipini toplar |
| **Güncelleme** | host | `UpdateEvent` (GraphQL); `lastUpdatedTsUsec` (alan 12) ilerler | hangi alanların değiştiğine bağlı hedefli bildirim metni: "Etkinlik tarihi güncellendi.", "...tarih ve konum...", "...tarih ve saat...", "...tarih, saat ve konum...", "...konum güncellendi.", "...saat güncellendi.", "...saat ve konum..." (hepsi found, diff'e göre farklı string'ler) |
| **İptal** | host | `isCanceled`/`status`'u ayarlar; onay diyaloğu "Etkinliği iptal et" / "Bu etkinliği iptal etmek istediğinizden emin misiniz?" | "Etkinlik iptal edildi"; push metni "%1$s %2$s'i iptal etti"; "Davetliler artık etkinliğe yanıt veremez." / "Artık etkinliğe yanıt veremezsiniz." — RSVP kapanır |
| **Silme** | host | `DeleteEvent` (GraphQL) | host'un yerel etkinlik listesinden kaldırılır; sohbet davet mesajı/mesajları görünür kalır; "Davetli listesindeki kişiler etkinliğin silindiğini görecek." |
| **Ayrılma** | davetli | yerel eylem, RSVP değişikliği ima edilmez | davetli artık etkinlik güncellemelerini almaz: "Sadece ayrılmadan önce yapılan etkinlik değişikliklerini görebilirsiniz." |
| **Davetliyi kaldır** | host | davetliyi kaldırır; **davet linkini sıfırlar** (`RotateEventInviteLink`) | "Davetli kaldırıldı ve etkinlik linki sıfırlandı" — kaldırılan bir davetlinin link kopyasının çalışmayı durdurması için açık bir yeniden-katılma-önleme tedbiri; link üzerinden katılmış bir davetliyi kaldırmak, o linki daha önce kullanmış diğerlerini **geriye dönük olarak** geçersiz kılmaz |
| **Etkinliği bildir** | davetli | WhatsApp'a rapor gönderir | "Etkinlikteki hiç kimse bu rapor hakkında bilgi sahibi olmayacak."; etkinlikten ayrılmayı da tetikleyebilir |
| **Askıya alma** (moderasyon) | sunucu tarafı (politika uygulaması) | iptalden ayrı | "Etkinlik askıya alındı", "şu anda değiştirilemez"; host'un dışına çıkamayacağı kilitli bir durum |

Davetlileri tek tek kaldırmak (`RemoveEventInvitations`), katılmış bir davetliyi kaldırmaktan (`RemoveEventGuestUseCase`) ayrıdır; `AddEventInvitations`/`RemoveSelfEventInvitation`, davet-listesi yönetimini tamamlar.

---

## 9. RSVP UI'ı ve durumları

`EventRsvpBottomSheet`, resource id'lerine bağlı dört radio seçeneği sunar: `rsvp_going_btn`, `rsvp_going_with_guest_btn` (sadece `extraGuestsAllowed` ayarlıyken ve görüntüleyici 0'dan büyük bir davetli sayısı seçtiğinde gösterilir), `rsvp_not_going_btn`, `rsvp_maybe_btn`; yanıtsız/`NO_RESPONSE` durumu için hiçbir buton seçili değildir. Etiketler (found, strings.xml): "Katılıyorum", "Davetliyle katılıyorum", "Belki", "Katılmıyorum". Bir davetli ayrıca bir plus-one sayısı getirebilir (`extraGuestCount`, `EventResponseMessage`'ın wire alanı 3), `EventMessage.extraGuestsAllowed` (alan 9) tarafından gate'lenir / davetliler plus-one ile zaten RSVP verdiğinde `"Bu etkinlik için 'Davetlilere izin ver'i kapatamazsınız."`

WhatsApp kullanıcısı olmayanların RSVP'si, katılma linki üzerinden açıkça desteklenir: `"Davetliler WhatsApp'ta olmasalar bile yanıt verebilir."` — `JoinEventViaLink`, kimlik doğrulanmış bir WA oturumu olmadan `rsvp_status`'u doğrudan alır, yani şifreli `encEventResponseMessage` yolu tek RSVP kanalı değildir; link-tabanlı RSVP'ler onun yerine plaintext GraphQL üzerinden gider.

---

## 10. Görünürlük ve gizlilik modeli

Bu, Etkinlikler hakkında en önemli "karıştırmayın" gerçeğidir: sıradan sohbet içeriğinin aksine, **etkinlik metadata'sı sunucuya açıkça ifşa edilir**, salt E2E-opak değildir.

| String (found) | Resource | Anlamı |
|---|---|---|
| "Etkinlik ayrıntıları davetlilere ve WhatsApp'a görünür olacak." | `str19d9` | ad/açıklama/zaman/konum sunucu tarafında okunabilir (GraphQL `CreateEvent`/`UpdateEvent` değişkenleri olmalarıyla, sadece şifreli proto byte'ları olmamalarıyla tutarlı) |
| "Etkinlik ayrıntıları davetlilere ve WhatsApp'a görünür. Kişisel mesajlarınız ve aramalarınız uçtan uca şifreli kalır." | `str1a3f` | açık kapsam belirleme: E2EE garantisi etkinlik ayrıntılarına *genişletilmemiştir* |
| "Adınız ve yanıtınız diğer davetlilere ve WhatsApp'a görünür olacak." | `str1a08` | RSVP kimliği + yanıt da sunucuya görünür (`UpdateEventRsvp`'nin, şifreli `encEventResponseMessage` sohbet-düzlemi yankısından ayrı, plaintext bir GraphQL mutation olmasıyla tutarlı) |
| "Etkinlik konumunu ve daha fazlasını görmek için yanıt verin." / "Konumu görmek için yanıt verin" | `str19c7`/`str19c4` | konum, henüz yanıt vermemiş davetliler için RSVP'nin ardına gate'lenmiştir |
| "Sadece rehberinizde olan veya WhatsApp'ta mesajlaştığınız davetlileri görebilirsiniz." | `str1974` | davetli-listesi görünürlüğü, tam bir listeyle değil, görüntüleyicinin kendi rehber/sohbet grafiğiyle sınırlıdır |
| "Linke sahip olan herkes etkinliği görebilir ve WhatsApp'ta olmasalar bile başkalarıyla paylaşabilir." | `str198b` | davet linki/QR, üyeliği tamamen atlar — linke sahip olmak erişim kontrolüdür |

Yani: `encEventResponseMessage` E2E şifrelemesi (HKDF + AES-GCM, §5, `WA_MESSAGE_SECRETS.md`), RSVP payload'ını **sohbet transkriptinde / relay'e karşı** korur, ama aynı RSVP yanıtı ve etkinliğin kendi metadata'sı, senkronizasyon, keşif ve link-tabanlı (WA-olmayan) davetliler için bağımsız olarak GraphQL kontrol düzlemi üzerinden sunucuya plaintext olarak gönderilir. İki düzlem birbirini dışlamaz — aynı etkinlik için bir arada bulunurlar.

---

## 11. Grup vs 1:1 vs community bağlamı

- **1:1 sohbet**: her iki taraf da bir etkinlik oluşturabilir; `is_group_based_event` GraphQL değişkeni false'tur.
- **Grup sohbeti**: `is_group_based_event: true`; composer, grubu tanımlayarak "Şunun için oluşturuldu:" gösterir; davetliler ayrıca grup üyeliğinden kaynaklanabilir (`EventInviteFromGroupsLoadController`, `EventInviteGroupFetcher`), bu da host'un diğer paylaşılan gruplardan kişileri davet etmesine izin verir.
- **Community**: Etkinlikler community seviyesinde de yüzeye çıkar — "Duyurulardaki etkinlikler", "Community etkinlikleri", "Tüm community etkinliklerini gör" (found string'ler) — tek bir grubun etkinliklerinden ayrı, community-geniş bir etkinlik listesi.
- **Bağımsız / link-tabanlı**: bir etkinliğin herhangi bir sohbete bağlı olması gerekmez; `GetOrCreateEventInviteLink` + `EventInviteLinkQrActivity`, sohbet üyeliğinden bağımsız paylaşılabilir bir link/QR üretir (§10, `str198b`).

`eventMessage`'ın companion-destek sınıflandırması (`WA_MESSAGE_SECRETS.md` §15, `CompanionSupportVerifier`), stanza `type="event"`'in bağlı (companion) bir cihazda izin verilmesine olanak tanır — yani davet balonu orada hâlâ *alınabilir ve saklanabilir* — ama onunla etkileşim engellenir: `EventsCompanionRedirectDialog` + string `"Bu etkinliği görüntülemek veya yanıtlamak için birincil cihazınızda WhatsApp'ı kullanın."` (found), companion-cihaz kullanıcılarını Events v2 UI'ından tamamen yönlendirir. Bu kasıtlı bir ayrımdır: stanza-seviyesi teslimat companion-güvenlidir, özellik-seviyesi etkileşim sadece-birincil-cihazdır.

---

## 12. Hatırlatıcılar ve bildirimler

| Mekanizma | Tetikleyici | Found/Inferred |
|---|---|---|
| `hasReminder`/`reminderOffsetSec` (`EventMessage`'ın wire alanları 11/12) | host tarafından yapılandırılır, picker seçenekleri: Asla / Etkinlik zamanı / başlangıçtan 15 dk / 30 dk / 1 saat / 1 gün önce | found (UI string'leri); saniye eşlemesi inferred |
| Her zaman açık başlangıç bildirimi | "Davetliler ayrıca etkinlik zamanında bildirim alır." (`str1a47`) | found — özel hatırlatıcıdan bağımsız olarak, etkinlik başladığında her davetli bir bildirim alır |
| "Hassas etkinlik hatırlatıcılarına izin ver" | tam-zamanlı alarmlar için OS izin istemi | found |
| Güncelleme bildirimleri | metin, hangi alanların değiştiğine göre değişir (§8) | found |
| İptal bildirimi | "%1$s %2$s'i iptal etti. Etkinliği gör" | found |
| MEX push (`xwa2_notify_event_on_invite`/`_on_update`) | sunucu-başlatımlı senkronizasyon, sohbet teslimatından bağımsız | found (§6.1) |

---

## 13. Feature flag'ler

Bu pass'te Events v2 davranışını gate'leyen sayısal feature-flag ID'si kurtarılmadı — `WA_MESSAGE_SECRETS.md`'nin izole boolean/int gatekeeper call site'larının aksine, `eventsv2.*` paketinin dependency-injection accessor'ları (`C05T.A00(NNNNN)`, `C05Z.A00(NNNNN)`) flag okumaları değil, component/singleton lookup id'leridir, ve etkinlik oluşturmayı, RSVP'yi veya companion yönlendirmesini koruyan sayısal bir flag'e bağlı `AbstractC...Gatekeeper` tarzı bir boolean kontrolü bulunamadı. Paylaşılan RSVP kripto yolu için zaten belgelenmiş iki flag ilgili olanlar olarak kalıyor: **15791** (1:1 sohbetlerde event-response modifier LID→PN dönüşümü) ve `WA_MESSAGE_SECRETS.md` §15–16'daki companion-allowlist/mesaj-tipi-classifier makinesi. Events v2 UI'ının kendisini gate'leyen ayrı bir kill-switch olup olmadığı unknown.

---

## 14. Baileys

`baron-baileys-v2` 1.5.17'de, `WA_MESSAGE_SECRETS.md` §17'nin paylaşılan add-on kripto yolu için zaten belgeledikleri dışında `eventMessage`/`eventInviteMessage` gönderme veya alma işleme, ve `encEventResponseMessage` RSVP şifrelemesi bulunamadı (gelen bir `encEventResponseMessage`'ı genel use-case tablosunu kullanarak decrypt edebiliyor, ama etkinliğe özgü bir sender veya etkinlik-modeli kodu yok). `eventMessage` ve `eventInviteMessage`, aksi halde düz `Message` alanlarıdır ve §2/§3'teki scalar alanlarla `snowi.sendjson` üzerinden gönderilebilir — birini oluşturmak kripto helper'ını hiç gerektirmez, sadece `encEventResponseMessage` (RSVP) gerektirir. §6'daki `www` op'ları için Baileys'te hiçbir GraphQL client'ı yok; bunlar implemente edilmemiş bir persisted-`doc_id` GraphQL POST yolu gerektirir.

| Konu | Baileys | Android |
|---|---|---|
| `eventMessage`/`eventInviteMessage` gönder | düz `Message` alanı, `snowi.sendjson` üzerinden erişilebilir | aynı |
| `encEventResponseMessage`'ı şifrele | implemente edilmemiş (sadece-decrypt, genel use-case yolu) | `DU9.ADr` + `MessageSecretCryptoHelper` |
| Events v2 GraphQL op'ları (§6) | implemente edilmemiş | `GraphqlEventsDataSource` |
| MEX push senkronizasyonu (§6.1) | implemente edilmemiş | `DefaultEventsNotificationRepository` |

---

## 15. Hata durumları / gotcha'lar

| Belirti | Neden | Not |
|---|---|---|
| RSVP decrypt başarısız / hata 51 | yanlış orijinal-mesaj key'i, veya sender/target namespace (PN vs LID) uyuşmazlığı | poll oyu / yorum yoluyla paylaşılır, bkz. `WA_MESSAGE_SECRETS.md` §18 |
| Etkinlik Etkinlikler listesinde görünür ama sohbette hiç görünmedi | MEX push (`xwa2_notify_event_on_invite`) onu sohbet teslimatından bağımsız olarak senkronize etti | §6.1 |
| Bir davetli için konum/davetli-listesi eksik | henüz RSVP vermemiş (konum gate'li), veya davetli görüntüleyicinin rehberinde/sohbet geçmişinde yok (davetli-listesi sınırlı) | §10 |
| Kaldırılmış bir davetli eski link üzerinden hâlâ RSVP verebiliyor | davetli kaldırma, *o* davetlinin kaydı için linki sıfırlar ama zaten paylaşılmış linkin diğer sahipleri etkilenmez | §8, `str19ed` |
| "Etkinlik değiştirilemiyor" / etkinlik kilitli | etkinlik politika nedenleriyle askıya alınmış, sadece iptal edilmemiş | §8 |
| Companion cihaz etkinliği açamıyor | stanza'nın kendisi companion-teslim edilebilir olsa da Events v2 etkileşimi sadece-birincil-cihazdır | §11 |
| `EventInviteMessage.status` (13) kesin olarak parse/üretilemiyor | enum sınıfı statik olarak kurtarılamıyor; GraphQL `rsvp_status`/`status` kelime dağarcığıyla aynı olduğu **kanıtlanmamış** | §3, §5.3 |

---

## 16. Temel ayrımlar

| Bu | Şu değil |
|---|---|
| `eventMessage` (alan 75, temel, 12 alan, 41.6-öncesinden değişmedi) | `eventInviteMessage` (alan 122, `DTQ`, 13 alan, aktif "Events v2" kartı) |
| `encEventResponseMessage` (sohbette E2E-şifreli RSVP yankısı) | `UpdateEventRsvp`/`JoinEventViaLink` (plaintext GraphQL RSVP, sunucuya görünür) |
| İptal (`isCanceled`'ı ayarlar, RSVP'yi kapatır, etkinlik görünür kalır) | Silme (host'un listesinden kaldırır; sohbet davetleri kalır, silindi olarak işaretlenir) |
| Silme (host-başlatımlı, host'un kopyasını etkiler + diğerleri için silindi olarak işaretler) | Ayrılma (davetli-başlatımlı, davetli daha fazla güncelleme görmeyi durdurur) |
| Askıya alma (sunucu moderasyon kilidi) | İptal (host eylemi) |
| Davetliyi kaldır + linki sıfırla (host, *o* davetlinin link kopyasını geçersiz kılar) | Daveti kaldır (host, davetli katılmadan önce) |
| `E2D`/`C9T8` wire-mirror RSVP enum'u (GOING=1, NOT_GOING=2, MAYBE=3, UNKNOWN=0) | `C9T6` yerel-DB enum'u (GOING=0, NOT_GOING=1, MAYBE=2, NO_RESPONSE=3) — farklı sıralama, aynı kavram |
| `C9U0` GraphQL `rsvp_status` string enum'u (`GOING`/`MAYBE`/`NOT_GOING`/`NO_RESPONSE`) | `EventInviteMessage.status` (alan 13) wire int32 açık enum'u — kurtarılamadı, eşleştiği kanıtlanmadı |
| Davetli-listesi görünürlüğü (görüntüleyicinin rehberiyle sınırlı) | Link/QR üzerinden etkinlik görünürlüğü (linke sahip olan herkese açık) |

---

## 17. Eksiksiz akış (grup etkinliği, oluşturma → RSVP → güncelleme)

```
[Host]                                   [WhatsApp server / GraphQL+MEX]           [Guest]
   │ CreateEvent (GraphQL, www)                   │                                   │
   │  chat_jid, description, location, cover──────▶ stores event, assigns eventId     │
   │◀──────────────────────────────────────────── eventId                             │
   │ compose eventInviteMessage (eventId,          │                                   │
   │   coverImageHandle, locationName, ...)        │                                   │
   │ <message type="event"> (E2E, chat plane)──────┼──────────────────────────────────▶ renders invite card
   │                                                │  xwa2_notify_event_on_invite      │
   │                                                ├──────────────────────────────────▶ event appears in
   │                                                │  (MEX push, independent of chat)    Events list too
   │                                                │                                   │ opens EventRsvpBottomSheet
   │                                                │                                   │ picks Going/Maybe/Not going
   │                                                │◀───────── UpdateEventRsvp (GraphQL, plaintext rsvp_status)
   │                                                │◀───────── encEventResponseMessage (E2E, chat plane)
   │  guest list / "Going" badge updates            │  xwa2_notify_event_on_update?     │
   │  (location now visible to guest)               │  (on edits)                       │
   │                                                │                                   │
   │ UpdateEvent (change location/time)─────────────▶ lastUpdatedTsUsec advances         │
   │                                                ├──────────────────────────────────▶ "Event date and location
   │                                                │                                      have been updated."
```

---

## 18. Bilinmeyenler

| Öğe | Durum |
|---|---|
| `EventInviteMessage.status` (alan 13) enum üye adları | statik olarak kurtarılamıyor; GraphQL `rsvp_status`/`status` string'leri (§5.3) makul ama doğrulanmamış bir analog |
| Picker seçeneği başına `reminderOffsetSec`'in kesin saniyesi | inferred (0/900/1800/3600/86400), constant pool çözülemedi |
| Katılma-linki / QR URL formatı (`chat.whatsapp.com/event/...` veya benzeri) | bu pass'te string'lerde veya manifest intent filter'larında bulunamadı |
| Events v2 oluşturma/RSVP/companion-yönlendirmesini gate'leyen sayısal feature-flag ID'leri | bulunamadı (bkz. §13) |
| `EventInviteMessage.status` ile yerel `C9T6`/`C9T8` uygulama enum'ları arasındaki kesin ilişki | izlenmedi |
| "Katılmak için onay gerektir" (`str1a34`) davranışı | string found; kod yolu izlenmedi |
| `eventResponses`(61)/`eventAdditionalMetadata`(64) history-sync alanlarının giden history sync'te, gelen'de, yoksa her ikisinde de doldurulup doldurulmadığı | izlenmedi |
