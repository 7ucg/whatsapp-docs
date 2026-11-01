<!-- src-sha1: b9a264b89fe2f15a6ff3587c9bc5a6b3a47e10c0 -->
# WhatsApp View-Once — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-01
**Kapsam:** `viewOnceMessage` / `viewOnceMessageV2` / `viewOnceMessageV2Extension` wrapper'ı ile `ImageMessage` / `VideoMessage` / `AudioMessage` / `ExtendedTextMessage` üzerindeki satır içi (inline) `viewOnce` alanı arasındaki fark, disappearing message'larla paylaşılan genel mesaj-wrapper açma (unwrap) mekanizması, mesaj türleri ve ortak marker interface, istemci tarafı zorlama (screenshot/ekran kaydı engeli, forward/paylaşma/kaydetme kısıtlaması, gönderenin kendi görüntülemesini engelleme, alıntılanan medyanın (quoted media) ayıklanması), yerel depolama ve durum makinesi (`message_view_once_media`, silme job'ı), medya anahtarı yaşam döngüsü (bağlantılı, tekrar edilmiyor), `unavailable[type="view_once"]` wire case'i ve cihazlar arası okuma/yazma token'ları, feature flag'ler, Baileys karşılaştırması

---

## 1. Ne olduğu

View-once ayrı bir mesaj türü değil, mesaj başına bir özelliktir: herhangi bir görüntü, video, sesli mesaj veya (son build'lerde) metin, alıcının istemcisinin bir kez açıldıktan sonra yerel kopyayı silmesi için işaretlenebilir; istemci ayrıca açıkken screenshot/ekran kaydını engeller ve forward/paylaş/kaydet'i gizler. Tüm ifadeler çözülmüş (decompile edilmiş) APK'nın statik analizidir; ağ üzerinde hiçbir şey yakalanmadı. Kademeler: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi. Adlar 2.26.41.6'da sabit string'ler ve log tag'lerinden çözüldü (`AppDataManager/contributeMetaAppData`, `ConversationRowViewOnceMedia/`, `EphemeralUpdateRunnable/`, `ViewOnceMessageStore/`, UI string id'leri).

| Varlık | 2.26.41.6 adı | Rol |
|--------|-----------------|-----|
| Wrapper mesajı (bir alan, `message` **1**) | `BD2` | `Message` (`C30628DTw`) üzerinde `viewOnceMessage` **37**, `viewOnceMessageV2` **55**, `viewOnceMessageV2Extension` **59**'un gövdesi |
| Medya türü başına satır içi flag | `ImageMessage.viewOnce` **25**, `VideoMessage.viewOnce` **20**, `AudioMessage.viewOnce` **21**, `ExtendedTextMessage.viewOnce` **30** | medya/metin mesajı üzerinde doğrudan set edilir, wrapper yok |
| Satır içi/wrapper anahtarı | flag **8784** | açık: sadece satır içi alan; kapalı: wrapper + satır içi alan ikisi de set edilir (6.3) |
| View-once görüntü handler'ı | `C34670F2r` ("FMessageViewOnceImageProtobuf") | `DdP`'yi oluşturur/okur, mesaj türü **42** |
| View-once video handler'ı | `C34671F2s` ("FMessageViewOnceVideoProtobuf") | `C30972DdZ`'yi oluşturur/okur, mesaj türü **43** |
| View-once metin handler'ı | `F33` ("FMessageViewOnceTextProtobuf") | `C31208Dhd`'yi oluşturur/okur, mesaj türü **78** |
| View-once ses handler'ı | `C34669F2q` ("FMessageViewOnceAudioProtobuf") | `C30963DdH`'ı oluşturur/okur, mesaj türü **82** |
| Marker interface | `InterfaceC24513Ahd` | yukarıdaki dört FMessage sınıfının tümü tarafından implemente edilir; UI/menü davranışını genel olarak kapılamak için kullanılır |
| Yerel durum tablosu | `message_view_once_media` | sütunlar `message_row_id`, `state` |
| Durum erişimcisi | `C199158dT` ("ViewOnceMessageStore") | `state`'i get/insert/update eder |
| Silme job'ı | `EphemeralUpdateRunnable` (`C199218dZ` içindeki anonim sınıf), job türü **3** | "`ViewOnceMessageStore/getViewOnceMessagesToDelete`" |
| Ekran yakalama engelleme yardımcısı | `C66572s0` | `window.addFlags(8192)` = `FLAG_SECURE` |
| Medya görüntüleyici için view-once kapısı | `C1ZB.A0O(i)` | `i == 42 \|\| i == 43` |
| Özel görüntüleyici (metin/ses) | `ViewOnceViewerActivity`, `ViewOnceTextFragment`, `ViewOnceAudioFragment` | ayrı Activity, her zaman `FLAG_SECURE` |
| Paylaşılan görüntüleyici (görüntü/video) | `MediaViewFragment` / `MediaViewMenu` | normal medya görüntüleyici, sadece `C1ZB.A0O` true olduğunda `FLAG_SECURE` |
| Bilgilendirme sheet'leri | `ViewOnceNuxBottomSheet`, `ViewOnceSecondaryNuxBottomSheet` | gönderene/alıcıya bir kez gösterilen açıklayıcı |
| Alıntılanan medya ayıklayıcısı | `F43` ("QuotedMediaCleanupSerializationPostProcessor") | bir view-once mesajının alıntısından medya baytlarını kaldırır, flag **25572** |

---

## 2. Proto işaretlemesi

### 2.1 Satır içi alan (found)

```text
ImageMessage.viewOnce         = 25  (bool)
VideoMessage.viewOnce         = 20  (bool)
AudioMessage.viewOnce         = 21  (bool)
ExtendedTextMessage.viewOnce  = 30  (bool, VIEW_ONCE_FIELD_NUMBER)
```

Her biri normal medya/metin mesajı üzerinde düz bir boolean'dır; taşımak için ayrı bir container gerekmez. `C30612DTg` (Image), `C30614DTi` (Video), `DTX` (Audio), `C30613DTh` (ExtendedText)'in üretilmiş alan tabloları okunarak doğrulandı.

### 2.2 Wrapper mesajı (found)

`Message` üzerindeki `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**) ve `viewOnceMessageV2Extension` (**59**)'un tümü `BD2` türündedir ve `BD2`'nin tam olarak bir alanı vardır, `message` **1**, kendisi bir `Message`. Üç alan adı da aynı sınıfa decompile edilir — bu, üç protokol nesli için üç kez kullanılan aynı wrapper şeklidir:

```java
public final class BD2 extends GeneratedMessageLite {
    public static final int MESSAGE_FIELD_NUMBER = 1;
    public C30628DTw message_;   // a full nested Message
}
```

### 2.3 Satır içi mi wrapper mı: flag 8784 (found)

Her medya türü başına handler (`C34670F2r` görüntü, `C34671F2s` video, `F33` metin, `C34669F2q` ses) aynı şeyi iki kez oluşturur ve bir flag'e göre birini seçer:

```java
boolean zA15 = this.A00.A15(8784);
...
if (zA15) {
    dp5.A0R(c30612DTg);                 // inline viewOnce=true directly on the outer Message
    return;
}
dp5A0f.A0R(c30612DTg);                  // same media message, but inside the BD2 wrapper
BD2 bd2A0Q = ...;
c30628DTwA0j.viewOnceMessageV2_ = bd2A0Q;
```

Flag açıkken, 2.26.41.6 yerel olarak oluşturulan bir view-once mesajı için asla wrapper üretmez; aynı sınıflardaki alıcı tarafı `CM7` (receive) handler'ları sadece satır içi flag'e bakar (`c30612DTg.bitField0_ & ... && c30612DTg.viewOnce_`), wrapper alanlarına bakmaz — bir wrapper'ı satır içi şekle açmak (unwrap) ayrı, genel bir adımdır (2.4).

### 2.4 Genel wrapper açma (unwrap) (found)

Statik bir tablo (`AbstractC33204EdH.A00`, 35 giriş) istemcinin bildiği her geriye dönük uyumluluk wrapper'ı için bir "bu wrapper'a sahip mi" koşulu ile bir "iç `Message`'ı al" extractor'ını eşleştirir; bunlar arasında `ephemeralMessage` (disappearing message wrapper'ı), `viewOnceMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `documentWithCaptionMessage`, `botInvokeMessage`, `groupStatusMessage` ve diğerleri bulunur. `C34748F5r` (native-flow/`<biz>` doğrulaması, `AbstractC33204EdH.A00`) sınıflandırılabilir içeriği, kaç wrapper'ın etrafı sardığından bağımsız bulmak için bu tabloda 10 derinliğe kadar yineler (recurse):

```java
for (EQR eqr : AbstractC33204EdH.A00) {
    if (hasWrapper(c30628DTw, eqr) &&
        A00(..., unwrap(c30628DTw, eqr), i + 1) != C02U.A00) {
        return result;
    }
}
```

`ephemeralMessage` ve üç view-once wrapper'ı bu tabloda eşdeğer girişlerdir — yapısal olarak aynı mekanizma, yani bir view-once mesajı prensipte bir disappearing message wrapper'ının içine veya yanına yerleştirilebilir (bölüm 7). Bu, Baileys'in kendi `message-inspect.js` içindeki `getFutureProofMessage()` listesini yansıtır; bu liste aynı wrapper alan adları kümesini sıralar.

---

## 3. Mesaj türleri ve marker interface

| Tür | Medya sınıfı | Handler | Fragment/Activity |
|------|-------------|---------|--------------------|
| **42** | `DdP` (görüntü) | `C34670F2r` | `MediaViewFragment` (paylaşılan görüntü/video görüntüleyici) |
| **43** | `C30972DdZ` (video) | `C34671F2s` | `MediaViewFragment` |
| **78** | `C31208Dhd` (metin) | `F33` | `ViewOnceViewerActivity` içindeki `ViewOnceTextFragment` |
| **82** | `C30963DdH` (ses/ptt) | `C34669F2q` | `ViewOnceViewerActivity` içindeki `ViewOnceAudioFragment` |

Dört sınıfın tümü `InterfaceC24513Ahd`'yi implemente eder; bu, istemcinin her yerde dört türlük kontrolü tekrarlamak yerine test ettiği tek marker'dır ("bu bir view-once mesajı mı"). `C1ZB.A0O(i)` (`i==42 || i==43`), paylaşılan `MediaViewFragment`'in view-once görüntü/videoyu render ettiği diğer her şeyden ayırt etmesi gerektiğinde kullanılan daha dar görüntü/video-özel testtir.

Tür kümesi `{42,43,78,82}` bu build'de bulunan birkaç bağımsız çağrı noktasında kelimesi kelimesine tekrarlanır: `<meta view_once="true">` üreticisi (bölüm 6.1), tür-adı arama tablosu (`AbstractC32316E9h`: `"viewOnceImage"`=42, `"viewOnceVideo"`=43, `"viewOnceAudio"`=82) ve kaydetme/gösterme kapılaması için `C1ZB` yardımcı metotları.

---

## 4. İstemci tarafı zorlama

### 4.1 Screenshot / ekran kaydı engeli (found)

`C66572s0.A00(Window)` tek satırlık bir yardımcıdır:

```java
public final void A00(Window window) {
    if (window != null) {
        window.addFlags(8192);   // WindowManager.LayoutParams.FLAG_SECURE
    }
}
```

`8192` (`0x2000`), `FLAG_SECURE`'in ham değeridir; decompile edilmiş kaynaklar sembolik adı değil sayısal sabiti kullanır, bu nedenle `FLAG_SECURE` için bir metin araması hiçbir şey bulamaz — sabit değer üzerinden eşleştirilmelidir. `FLAG_SECURE`, pencereyi screenshot'larda, recent-apps küçük resminde ve OS seviyesinde ekran kaydı/yansıtma sırasında karartır; bu WhatsApp'a özel bir tespit değildir, standart Android güvenli pencere flag'idir.

İki çağrı noktası:

| Çağrı noktası | Koşul | Kapsam |
|-----------|-----------|-------|
| `MediaViewFragment` (genel medya görüntüleyici) | `C1ZB.A0O(i)` yani `i==42 \|\| i==43` | sadece gösterilen mesaj view-once görüntü/video olduğunda uygulanır; aksi halde normal medya görüntüleyici güvenli hale getirilmez |
| `ViewOnceViewerActivity.onCreate` | koşulsuz | bu Activity sadece view-once metin (78) veya ses (82) için başlatılır, dolayısıyla her örneği güvenli hale getirilir |

Net etki: dört view-once türünden birinin açılması, açık olduğu sürece barındıran pencerede `FLAG_SECURE`'u set eder; görüntüleyicinin kapatılması (fragment/activity'nin yıkılması) pencereyi kaldırır, bu da flag'i onunla birlikte düşürür. Bir screenshot *tespit* mekanizmasına (örn. `Pictures/Screenshots` üzerinde bir `FileObserver` veya bir `MediaStore` içerik gözlemcisi) ait kanıt bulunamadı; koruma OS seviyesinde önlemedir, sonradan tespit değildir.

### 4.2 Forward / paylaşma / kaydetme yok (found)

`ViewOnceViewerActivity.onCreateOptionsMenu`, tam olarak dört menü girişi oluşturur — bilgi, transkript (sadece ses), sil, bildir — ve başka hiçbiri; bu menüde forward, paylaş, kaydet veya kopyala girişi hiç yoktur. Paylaşılan `MediaViewMenu`'de (normal medya görüntüleyici üzerinden view-once görüntü/video için kullanılır), birkaç boolean menü-görünürlük yerel değişkeni açık bir `instanceof InterfaceC24513Ahd` dışlaması ile hesaplanır, örn.:

```java
if (i6 == 2 && !c36911dGA1I21.element && ... && !(abstractC34931a2 instanceof InterfaceC24513Ahd)) {
    z14 = !C0DZ.A0X(c0df);     // forward-related menu flag, left false (hidden) for view-once
}
...
z16 = abstractC34931a2 instanceof InterfaceC24513Ahd;
if (!z16) {
    z17 = !AbstractC24760wu.A07(c0df);   // another gated flag, defaults false for view-once
}
```

Her flag varsayılan olarak `false` olduğundan ve kullanılabilir bir değer sadece view-once-olmayan dalda atandığından, karşılık gelen menü öğeleri `InterfaceC24513Ahd` mesajları için gizli kalır. Kısıtlama UI katmanında (menü oluşturma) uygulanır, görüntüleyici açmadan önce alttaki medyayı yerel diskten kaldırarak değil.

### 4.3 Gönderen kendi medyasını yeniden açamaz (found)

`DYM` (view-once medya için conversation-row bileşeni) şunu doğrular:

```java
C00K.A0C(false, "ConversationRowViewOnceMedia/senders can not view their own media");
```

bu, bir gönderenin kendi gönderdiği view-once satırının içeriği yeniden açmak için kullanacağı yol üzerindedir — yani "bir gönderen kendi view-once mesajı için asla çalışan bir açma handler'ı almaz" değişmezi (invariant), koşullu bir UI gizlemesi olarak değil, sert bir assertion olarak uygulanır.

### 4.4 Alıntılama medyayı ayıklar (found)

`F43` ("QuotedMediaCleanupSerializationPostProcessor", flag **25572** ile kapılı), alıntılanan bir mesajın `imageMessage` / `videoMessage` / `documentMessage` / `audioMessage`'ını, *yeni* bir giden mesaja `contextInfo.quotedMessage` olarak eklenmeden önce yeniden yazar: içerik olmayan alanları (mimetype, caption, boyutlar, thumbnail, `viewOnce` bitinin kendisi) kopyalar ama `mediaKey`, `fileSha256`/`fileEncSha256` ve `directPath`'i düşürür. Bir view-once mesajı alıntılamak, bu nedenle orijinal medya anahtarını bir yanıta kaçırmak (smuggle) için kullanılamaz; alıntı sadece metadata gösterir.

### 4.5 Bilgilendirme sheet'leri (found)

`ViewOnceNuxBottomSheet`, her tarafın (gönderen/alıcı — UXCam anahtarları `ephemeral_view_once` / `ephemeral_view_once_receiver` ile takip edilir) bir view-once mesajı ilk gönderdiği/aldığı seferde rol başına bir kez gösterilir, metni doğrudan `res/values/strings.xml`'den alınır:

| String id | Metin |
|-----------|------|
| `str4e56` | "View once messages give you more privacy" |
| `str4e55` | "For added privacy, the recipient can't share, forward, copy, save, or take a screenshot of it." |
| `str4e68` / `str4e5d` / `str4e7b` | tür başına varyantlar: "This is a view once photo/message/video so it's more private" |
| `str4e69` / `str4e6a` / `str4e5c` | "Also, you can't share, forward, copy, save, or take a screenshot of it." |
| `str4e63` / `str4e64` | "View once photo, expired" / "View once photo, opened" (video/ses/metin için aynı desen) |

"expired"/"opened" string çiftleri tür başına (görüntü, video, ses, metin), yerel `state` sütununun (bölüm 5) kullanıcıya görünen yüzüdür.

---

## 5. Yerel depolama ve durum makinesi

### 5.1 Tablo (found, `C199158dT`)

```sql
-- message_view_once_media(message_row_id, state)
SELECT state FROM message_view_once_media WHERE message_row_id = ?     -- GET_VIEW_ONCE_STATE_BY_MESSAGE_ROW_ID_SQL
UPDATE message_view_once_media SET state = ? WHERE message_row_id = ?  -- UPDATE_VIEW_ONCE_SQL
INSERT INTO message_view_once_media (message_row_id, state) VALUES (?, ?)  -- INSERT_VIEW_ONCE_SQL
```

View-once mesajı başına bir satır, genel `message` ve `message_media` tablolarından (bunlar hâlâ normal mesajlarla paylaşılan satır/medya-dosyası bookkeeping'ini tutar) bağımsız.

### 5.2 Durumlar (found satır değerleri, ad eşlemesi kısmen inferred)

| Geçiş | Kod | Tetikleyici |
|------------|------|---------|
| Satır oluşturuldu | `A02` (FMessage üzerinde `BDk()`, oluşturma anındaki değer) | mesaj gönderildi/alındı; başlangıç değeri FMessage'ın raporladığı her ne ise odur — "0 = açılmamış" ile tutarlı ama isimli bir sabit bulunamadı |
| Açıldı olarak işaretlendi | `A03`: `state = 1` | mesaj durumu (`B6u()`) **8**, **9** veya **10**'a ulaşır (indirme/okuma ile ilgili durum kodları; kesin adlar çözülmedi) |
| Satırsız okuma | `A01` içindeki fallback `i = 2` | `GET_VIEW_ONCE_STATE...` satır döndürmez; kod bunu mesaj sanki zaten süresi dolmuş gibi ele alır |

Yani **1** = doğrulanmış "opened" (isimli çağrı noktası); **2**, kayıt-yok/süresi-dolmuş fallback'idir; bir başlangıç/"açılmamış" değeri var ama bu build'de bir literal'e sabitlenmedi.

### 5.3 Silme (found)

Disappearing message'ları süresi dolduran (job türü 0, tablo `message_ephemeral`) ve message-secret eklentilerini (job türü 4, tablo `message_add_on`) süresi dolduran aynı `EphemeralUpdateRunnable` sınıfı, `ViewOnceMessageStore/getViewOnceMessagesToDelete` olarak loglanan job türü **3**'ü de çalıştırır:

```sql
SELECT message.* FROM message_view_once_media AS view_once
  JOIN message AS message ON view_once.message_row_id = message._id
  JOIN message_media AS message_media ON message_media.message_row_id = message._id
WHERE message_media.file_size IS NOT NULL
  AND message_media.file_size IS NOT 0
  AND message.from_me = 0
  AND view_once.state IN (1, 2)
LIMIT ?
```
<sub>(basitleştirilmiş sütun listesi; `GET_EXPIRED_VIEW_ONCE_MESSAGES_SQL`)</sub>

Harfiyen okunursa: job sadece hâlâ diskte bir dosyası olan (`file_size` mevcut ve sıfır değil) ve durumu `1` (opened) veya `2` (aynı "satır yok"/süresi dolmuş fallback değeri) olan *alınmış* view-once medyasını (`from_me = 0`) hedefler. Job, sorguyla eşleşen satırlar için yerel medya dosyasını serbest bırakır; mesaj satırını silmez (satır hayatta kalır, 4.5'teki "opened"/"expired" UI etiketini taşır). **Gönderilen** view-once medyası (`from_me = 1`) bu sorgu tarafından kapsanmaz — gönderenin bunu yeniden açmasına asla izin verilmemesiyle tutarlı (4.3), ama gönderenin kendi kopyası için karşılık gelen bir temizleme bulunamadı; bunun saklanması/silinmesi **unknown**.

### 5.4 Medya anahtarı / kripto yaşam döngüsü (bağlantılı, tekrar edilmiyor)

View-once medyası baştan sona normal medya pipeline'ını kullanır — aynı `MmsType` tablosu, aynı HKDF-80 anahtar türetimi, aynı AES-CBC+HMAC zarfı, aynı yükleme/indirme URL'leri; ayrı bir "view-once" `MmsType` satırı yoktur. Kripto için [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) bölüm 3-5'e ve view-once'a özel notlar için o raporun bölüm 12'sine bakın (gönderen-göremez assertion'ı, thumbnail silme log tag'i). Sunucunun ilk indirmeden sonra yüklenen nesneyi bağımsız olarak silip silmediği veya işaretleyip işaretlemediği bu statik analizden **unknown** — istemci tarafı garanti 5.3'teki yerel-dosya silmesidir, istemcinin gözlemleyebileceği bir sunucu sözleşmesi değil.

---

## 6. "View once unavailable" / cihazlar arası sinyalleşme

### 6.1 `unavailable[type="view_once"]` stanza'sı (daha önceki bir araştırma notuna düzeltme)

Daha önceki bir araştırma notu (2.26.35.2), giden `view_once`/`true` literal çiftini `AppDataManager/contributeMetaAppData` olarak loglanan bir metoda izlemişti ve bu metodun tam bir node mu oluşturduğu yoksa sadece metadata'ya mı katkıda bulunduğu açık bırakılmıştı. 2.26.41.6'da aynı log tag'i (`"AppDataManager/contributeMetaAppData type="`), `view_once` üreticisi **değildir**: bu, `F6K`'nın (genel `<meta>`-node oluşturucusu) farklı, ilgisiz bir dalına aittir ve bot/eklenti mesajları için özgür biçimli bir `appdata` özniteliği damgalar (`FZF.AVN()`). Bu build'deki gerçek `view_once` özniteliği, bu log satırından bağımsız olarak, *aynı* `F6K` metodunda birkaç satır önce oluşturulur:

```java
if (c08j2.A15(11282) && (i == 42 || i == 43 || i == 82 || i == 78)) {
    EZV.A00(ezv, "view_once", "true");
}
```

Bu, giden `<message>` stanza'sının `<meta>` node'unun bir alt öğesi/özniteliği olarak `<meta view_once="true">` yayar (araştırma notunun ve Baileys/whatsmeow'un tanımladığı `<unavailable type="view_once">` alt öğesi değil). Her ikisi de aynı anda doğru olabilir: `<meta view_once="true">`, bu mesajın view-once olduğuna dair gönderenin kendi-stanza işaretçisidir; `<unavailable type="view_once">` ise, o cihaza hiç ciphertext yayılmadığında sadece alım/Web tarafında gözlenen *farklı* bir node'dur. Android APK'sının statik analizi (burada Web/bağlı-cihaz rolü olmayan) bu ikinci node'u hangi tarafın oluşturduğunu gösteremez; bu rapor, bunun sunucu tarafından üretildiği veya gönderenin fanout durumundan sunucu tarafından normalleştirildiği şeklindeki daha önceki orta-yüksek güvenli sonucu değiştirmez. Baileys, alım tarafını genel literal'den *daha spesifik* bir literal ile doğrular: `src/Socket/messages-recv.js`, bir on-demand placeholder-yeniden-gönderme isteğini atlamaya karar vermek için `unavailableType === 'view_once_unavailable_fanout'`'u (`bot_unavailable_fanout`, `hosted_unavailable_fanout` ile birlikte) kontrol ederken, `src/Utils/decode-wa-message.js` ayrıca `isViewOnce`/`StubType.VIEWED_ONCE`'ı set etmek için bir `<unavailable>` alt öğesi üzerinde düz `attrs.type === 'view_once'`'u eşleştirir. Bunlar, daha önceki araştırma notunun bir string olarak ele aldığı şey için iki farklı kod yoludur.

### 6.2 `view_once="read"`/`"write"` token'ları (found token, çözülmemiş consumer)

`view_once_read` ve `view_once_write` literal'leri, Android istemcisinin binary-stanza sözlük tablosunda (`AbstractC40911lb`, kompakt token kodlaması için kullanılan sabit wire-vocabulary listesi) bulunur — `unavailable`, `enc`, `polltype` gibi öğeleri taşıyan tablonun aynısı. Baileys'in `decode-wa-message.js`'i, `<enc>`-seviye öznitelikleri üzerinde `'read'` veya `'write'` değerinde bir `attrs.view_once` okur ve bunu `fullMessage.viewOnceType` olarak saklar. Bu ikisi birlikte, mesaj zarfıyla birlikte giden kendi-cihaz-başına bir "zaten açıldı" senkronizasyon sinyaliyle tutarlıdır — muhtemelen bir kullanıcının diğer bağlı cihazlarının view-once içeriğinin bir cihazda zaten açıldığını öğrenme şekli — ama 2.26.41.6'da bu özniteliği *set eden* veya *tüketen* bir Android çağrı noktası bulunamadı; burada çözülmemiş bir Android consumer'ı olan bulunmuş bir wire token'ı olarak kaydediliyor (**unknown**).

---

## 7. Disappearing message'larla etkileşim

View-once ve disappearing message'lar (chat başına mesaj TTL'i), aynı mesaj üzerinde ikisi de set edilebilen bağımsız, ortogonal flag'lerdir:

- Ayrı yerel tablolar kullanırlar: `message_ephemeral` (disappearing, `expire_timestamp` ile anahtarlanmış) vs. `message_view_once_media` (view-once, `state` ile anahtarlanmış).
- Her ikisi de *aynı* `EphemeralUpdateRunnable` worker'ındaki job'larla süresi doldurulur (disappearing için job türü 0, view-once için job türü 3, message-secret eklentileri için job türü 4) — paylaşılan bir zamanlama/yürütme yolu, feature başına ayrı durum ve SQL.
- Proto seviyesinde, `ephemeralMessage`, üç view-once wrapper'ıyla tam olarak aynı genel wrapper-açma (unwrap) tablosunda eşdeğer bir giriştir (bölüm 2.4): bir mesaj `ephemeralMessage{message: viewOnceMessage{message: imageMessage{...}}}` olarak veya ters sırayla iç içe yerleştirilebilir, ve `C34748F5r`'daki özyinelemeli açma (unwrap) ile Baileys'in `getFutureProofMessage()`'ı her iki sırayı da yürür.
- Disappearing-message silmesi, açılıp açılmadığına bakmaksızın chat'in TTL'inden sonra tüm mesajı kaldırır; view-once silmesi ise mesaj açıldıktan (veya durum-2 fallback'ine düştükten) sonra sadece *medya dosyasını* kaldırır ve mesaj satırını (şimdi "opened"/"expired" olarak gösterilir) yerinde bırakır. Dolayısıyla disappearing bir chat içindeki bir view-once fotoğraf, kendi bir-kez-aç-sonra-sil kuralının üzerine chat'in TTL'ine de tabidir.

---

## 8. Feature flag'ler (id'ler çağrı noktalarında okunduğu şekliyle; adlar çözülmedi)

| ID | Tür | Kontrol ettiği |
|----|------|----------|
| **8784** | bool | view-once medyasını sadece satır içi alanla (açık) vs. satır içi alan + eski wrapper ile (kapalı) gönderme |
| **11282** | bool | mesaj türleri 42/43/78/82 için `<meta view_once="true">` yayma |
| **25572** | bool | alıntılanan bir view-once mesajından medya alanlarını ayıklama (`F43`) |

(Paylaşılan medya pipeline'ını yöneten flag'ler — HKDF, yükleme/indirme, yeniden deneme — [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) bölüm 16'da listelenmiştir ve burada tekrarlanmaz.)

---

## 9. Baileys (`baron-baileys-v2`, kaynak okundu, hiçbir şey test edilmedi)

| Konu | Baileys | Android 2.26.41.6 |
|-------|---------|---------------------|
| Gönderme tarafı işaretleme | her zaman wrap eder: bir `viewOnceVersion` seçeneğine bağlı olarak `{ viewOnceMessage \| viewOnceMessageV2 \| viewOnceMessageV2Extension: { message } }` (`src/Utils/messages.js`) | flag 8784 kapalıyken sadece wrap eder; varsayılan (8784 açık), satır içi `viewOnce` alanını medya/metin mesajı üzerinde doğrudan set eder, wrapper yok |
| Wrapper medya-olmayan için de kullanılıyor | `viewOnceMessage`, ayrıca `buttonsMessage`/`templateMessage`/`listMessage`/`interactiveMessage` gönderimlerini futureproof etmek için kullanılır (`src/Socket/messages-send.js`, `requiresViewOnce`) — gizlilik odaklı self-destruct ile ilgisiz | aynı wrapper türü (`BD2`), genel unwrap tablosu tarafından `botInvokeMessage`, `editedMessage` vb. için yeniden kullanılır — aynı "genel zarf" rolü bağımsız olarak doğrulandı (2.4) |
| Genel unwrap listesi | `message-inspect.js` içindeki `getFutureProofMessage()`: `ephemeralMessage`, `viewOnceMessage`, `documentWithCaptionMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `groupMentionedMessage`, `botInvokeMessage`, ... | `AbstractC33204EdH.A00` (35 giriş) — aynı wrapper alan adları |
| `unavailable` alım işleme | iki farklı literal kontrolü: `attrs.type === 'view_once'` (`isViewOnce`'ı set eder) ve `unavailableType === 'view_once_unavailable_fanout'` (placeholder yeniden gönderimini atlar) | sadece istemci tarafı `<meta view_once>` üreticisi (6.1); `<unavailable>` node'unun kendisi alım-yolu/Web-tarafı, burada izlenmedi |
| `view_once` okuma/yazma token'ı | `<enc>` öznitelikleri üzerinde `attrs.view_once === 'read' \| 'write'`'i `viewOnceType`'a decode eder | token'lar istemcinin wire sözlüğünde mevcut; Android consumer'ı bulunamadı (6.2) |
| Analitik | `WAM/constants.js`: `viewOnceMessagesSent` (16), `viewOnceMessagesReceived` (17), `viewOnceMessagesOpened` (18) | bu raporda izlenmedi; WAM mekanizması genel olarak için [WA_WAM_ANALYTICS.md](./WA_WAM_ANALYTICS.md)'e bakın |
| Screenshot/forward engelleme | implemente edilmemiş — Baileys, UI'sı, penceresi, kısıtlanacak menüsü olmayan bir backend kütüphanesidir | `FLAG_SECURE` + menü-öğesi çıkarılması (4.1-4.2); Android UI dışında yeniden üretilemez |
| Açıldıktan sonra yerel silme | uygulanamaz — Baileys'in kalıcı medya-görüntüleyici durum makinesi yoktur; çağıranlar kendi depolamalarından sorumludur | `message_view_once_media.state` + `EphemeralUpdateRunnable` job türü 3 (5.1-5.3) |

---

## 10. Hata durumları / tuhaflıklar

| Belirti | Neden | Not |
|---------|-------|------|
| Görüntüleyici yeniden açıldığında view-once medyası kaybolmuş | normal: `state` 1'e (opened) ulaştı veya satır mevcut değildi (fallback 2), ve silme job'ı dosyayı zaten serbest bıraktı | bir hata değil; bu amaçlanan bir-kez-aç-sonra-sil davranışıdır |
| Gönderenin kendi view-once medyası conversation satırından hiç açılmıyor | `DYM` sert assertion'ı `senders can not view their own media` | tasarım gereği, bir hata yolu değil |
| Alıntılanan view-once yanıtı medya göstermiyor | `F43`, alıntıdan `mediaKey`/hash'leri/`directPath`'i ayıklar, sadece caption/boyutlar/thumbnail/`viewOnce` bitini tutar | beklenen; alıntılama medyayı yeniden çıkarmak için kullanılamaz |
| View-once görüntü/video görüntüleyici bazı build'lerde screenshot'lara izin veriyor, bazılarında vermiyor | `FLAG_SECURE` sadece `C1ZB.A0O(i)` (tür 42/43) üzerinden uygulanır; bu kapıdaki herhangi bir regresyon (örn. bu kapıdan geçmeden bir view-once öğesi için paylaşılan görüntüleyiciyi açan bir kod yolu) korumayı sessizce düşürür | kapı konumu belgelenmiştir `MediaViewFragment` satır ~3120 (bu build) |
| Bağlı bir cihaz, kullanıcı orada açmadan bir view-once mesajını zaten açılmış olarak gösteriyor | `view_once="read"/"write"` wire token'ları üzerinden olası cihazlar arası senkronizasyon (6.2) | mekanizma Android tarafında doğrulanmadı; unknown olarak kaydedildi |

---

## 11. Önemli ayrımlar

| Bu | Bununla karıştırma |
|------|----------|
| `ImageMessage`/`VideoMessage`/`AudioMessage`/`ExtendedTextMessage` üzerindeki `viewOnce` boolean alanı | aynı mesajın etrafındaki eski `viewOnceMessage`/`viewOnceMessageV2`/`viewOnceMessageV2Extension` wrapper'ı |
| Gizlilik (self-destruct) için kullanılan `viewOnceMessage` (`BD2`) | aynı `BD2` wrapper türünün buttons/template/list/interactive gönderimleri için (Baileys) ve Android'de `botInvokeMessage`/`editedMessage` için genel futureproofing zarfı olarak yeniden kullanılması |
| `message_view_once_media.state` (yerel, mesaj başına, açma/süresi-dolma takibi) | `message_ephemeral.expire_timestamp` (yerel, mesaj başına, disappearing-chat TTL'i) — bağımsız tablolar, bağımsız job'lar, aynı runner |
| `<meta view_once="true">` — giden stanza üzerinde gönderen tarafı sınıflandırıcı | `<unavailable type="view_once">` — o cihaza hiç ciphertext ulaşmadığında alım/Web tarafında görülen farklı bir node |
| Görüntüleyici penceresi üzerinde `FLAG_SECURE` (screenshot/kayıt *önleme*) | bir screenshot *tespit* callback'i — böyle bir mekanizma bulunamadı |
| Açıldıktan sonra yerel medya *dosyasının* silinmesi | mesaj *satırının* silinmesi — satır hayatta kalır, "opened"/"expired" olarak etiketlenir |
| View-once (medya bir açıştan sonra silinir) | disappearing message'lar (tüm mesaj chat-seviyesi bir TTL'den sonra kaldırılır) — ortogonal, birleşebilir |

---

## 12. Tam akış (view-once fotoğraf, 1:1 chat)

```
[Sender]
   │ pick photo, mark "view once" in composer
   │ ImageMessage.viewOnce = true          (flag 8784 on: inline only)
   │ upload via normal media pipeline (WA_MEDIA_UPLOAD.md)
   │ flag 11282 on, type==42 → <meta view_once="true">
   ▼
[Server]  relays the E2E-encrypted stanza; cannot read viewOnce (it's inside the ciphertext)
   │
   ▼
[Receiver]
   │ decrypt → ImageMessage.viewOnce == true, message type 42 (DdP)
   │ INSERT message_view_once_media(message_row_id, state=<initial>)
   │ thumbnail shown in the conversation row; sender-side row asserts "can not view own media"
   │
   ├── user taps to open ──► MediaViewFragment, C1ZB.A0O(42) == true
   │                          → window.addFlags(FLAG_SECURE)
   │                          → forward/share/save menu items hidden (InterfaceC24513Ahd)
   │                          → status reaches 8/9/10 → state = 1 ("opened")
   │                          → window closed, FLAG_SECURE drops with it
   │
   ▼
[EphemeralUpdateRunnable, job type 3]
   │ SELECT ... FROM message_view_once_media JOIN message_media
   │   WHERE from_me=0 AND file_size IS NOT NULL AND state IN (1,2)
   ▼
local media file deleted; row kept, UI shows "View once photo, opened"
```

---

## 13. Bilinmeyenler

| Öğe | Durum |
|------|-------|
| `state` 0 (başlangıç) için isimli sabitler ve 2 (satır-yok fallback'i) ile "expired" arasında paylaşılan kesin anlam | sadece 1'in ("opened") isimli bir çağrı noktası var; gerisi fallback değerinden ve UI string'lerinden çıkarılmıştır (inferred) |
| `C199158dT.A03`'ün "opened"'ı tetiklemek için tükettiği durum kodları 8/9/10 | isimli sabitlere çözülmedi |
| Gönderilen view-once medyasının **gönderenin kendi** kopyasının saklanması/temizlenmesi | silme job'ı sadece `from_me = 0`'ı hedefler; karşılık gelen gönderen-tarafı temizleme bulunamadı |
| İlk indirmeden sonra yüklenen nesnenin sunucu tarafında silinmesi/işaretlenmesi | statik istemci analizinden gözlemlenemez |
| `<unavailable type="view_once">` node'unun oluşturulması (istemci placeholder'ı mı sunucu tarafından mı oluşturulmuş) | çözülmedi; daha önceki araştırmadan taşındı, burada yeni çözülmedi |
| `view_once="read"/"write"` wire token'larının Android consumer'ı | token varlığı sözlük tablosunda doğrulandı; çağrı noktası bulunamadı |
| `FLAG_SECURE`'ün view-once içeriği sunabilen her kod yolunda uygulanıp uygulanmadığı (örn. bildirim önizlemeleri, widget, Wear) | sadece `MediaViewFragment` ve `ViewOnceViewerActivity` yolları kontrol edildi |
</content>
