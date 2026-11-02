<!-- src-sha1: 12b80567ad9e73698ea38209998c12bdf3666099 -->
# WhatsApp Çağrı Bağlantıları — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-11-02
**Kapsam:** Misafir çağrı bağlantıları (`call.whatsapp.com/{voice|video}/{token}`): `link_query` / `link_join` el sıkışması, bekleme odası, misafir katılımcı / JID tahsis modeli ve misafire kabul anında verilen röle ve anahtar materyali. Bu rapor sadece bağlantı/bekleme-odası/misafir katmanını kapsar; genel `<call>` zarf dilbilgisi, offer/accept/terminate, çağrı anahtarı, röle seçim mantığı ve medya yolu [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) içinde ele alınır ve burada sadece referans verilir, tekrar edilmez.

---

## 1. Nedir

Çağrı bağlantısı, bir katılımcının JID ile davet edilmeden bir çağrıya katılmasını sağlayan bir token'dır. Sunucu token'ı çalışan veya başlatılabilir bir çağrıya çözer ve çağrının bir bekleme odası varsa, içeri alınana kadar katılımcıyı orada tutar. Aşağıda bölüm 3'ten itibaren stanza-şekli tablolarının altındaki her şey **tested**'dir: kendi test çağrı bağlantısına katılan bir istemcinin gerçek bir tel yakalamasından okunmuş, katılan istemcinin kendisi tarafından şifresi çözülüp decode edilmiştir (üçüncü taraf trafiğinin dinlenmesi değil). APK statikleri (**found**) yakalamanın göstermediği kısımları, başlıca bağlantı oluşturmayı, doğrular. Sunucu tarafı akıl yürütme, belirtilmedikçe **unknown**'dır.

| Varlık | Form | Kim belirler | Katman |
|--------|------|--------|------|
| Bağlantı URL'si | `https://call.whatsapp.com/{voice\|video}/{token}` | istemci bunu bir token etrafında şablonlar | found |
| Token | 22 karakter, karışık büyük/küçük harf alfanümerik (`Voip.kCallLinkTokenLength`=22) | oluşturma çağrı noktasının Java'da token parametresi yok; sunucu tarafından atandığı çalışma varsayımı | found (uzunluk), inferred (köken) |
| Call-id | 32 hex karakter (16 bayt), örn. `0076804DB4CA9D41EFCB547F08AE87BD` | sunucu, `link_join` ack'inde döner | tested |
| `is_guest_eligible` | bağlantı üzerinde bool | host oluşturma anında seçer (`CallLinkInfo.isGuestEligible`) | found (alan), tested (tel değeri) |
| `waiting_room` `enabled` | bağlantı üzerinde bool | host oluşturma anında seçer (`Voip.createCallLink(..., waitingRoomEnabled)`) | found (alan), tested (tel değeri) |
| Misafir katılımcı | `account_kind="guest"` ve sunucu tarafından tahsis edilmiş bir JID'e sahip roster girişi | sunucu, kabul anında | tested |
| Call-domain JID | call-id var olmadan önce boş `call` alanı, call-id oluştuktan sonra `<call-id>@call` | sunucu | tested |

---

## 2. Kanıt tabanı

Zaten kimlik doğrulanmış bir chatd bağlantısından (katılan oturumun tel üzerinde kendi kimliği vardır) kasıtlı olarak kendi seçtiği bir görünen ad ve açıklanmış bir kimlik olmadan bağlantı yolunu çağıran, hesabın kendi JID'i olarak katılmak yerine, baştan sona iki bağımsız misafir katılımı yakalandı:

| | Video bağlantısı | Sadece-sesli bağlantı |
|---|---|---|
| Token | `7vEdtKy61dqCtbWAQ59zuO` | `ENcQnTAwKj7lQOdOHVJPmQ` |
| Call-id | `0076804DB4CA9D41EFCB547F08AE87BD` | `00BC509C0194CE83E26FA85A0319FD9C` |
| Çağrı oluşturucu (host) | `48615137533978` cihaz 24 | `21428363591910` cihaz 0 |
| Gönderilen misafir push_name | `Baron als Gast ohne wa` | `Baron aus web testt` |

Her iki oturum da host'u ve call-id'nin kendi oluşturucusunu `type=1, domainType=1` şeklinde bir JID ile ve açık bir `server` özniteliği olmadan adresliyor; aynı yakalamalarda başka yerlerde aynı şekil, aynı hesap için, açık bir `server="lid"` ile eşleştiriliyor (örn. mesaj-sınıfı alındı onayları). Birlikte okunduğunda: buradaki çağrı sinyalizasyonu LID kimlikleri üzerinden çalışıyor, bu da [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) §3.2'nin çağrı stanza'larının farklı-alan bir `call-creator`'a karşı LID bir `to`'ya tolerans gösterdiği notuyla tutarlı.

Bu yakalamanın göstermediği: gerçekten hesapsız bir tarayıcı oturumunun (önceden hiç WhatsApp girişi olmadan) aynı bağlantıya ulaşması. Aşağıdaki stanza şekilleri bir misafir katılımı için çağrı-sinyalizasyon-katmanı protokolüdür; anonim bir web ziyaretçisinin istemcisinin bayt-eşdeğeri stanza'lar üretip üretmediği, veya önce ekstra bir sağlama adımından geçip geçmediği **unknown**'dır.

---

## 3. Bağlantı oluşturma (found, APK; tel üzerinde yakalanmadı)

| Adım | Sınıf / metot | Detay |
|------|-----------------|--------|
| Giriş noktaları | `CreateCallLinkBottomSheet` (bağımsız bağlantı), `EventCallLinkManager.createCallLink` (etkinliğe bağlı bağlantı) | her ikisi de tek bir yöneticiye akar |
| Yönetici | `CallLinkManager` (log etiketi), `actionCreateCallLink` / `actionCreateCallLinkForEvent`'i gönderir | |
| Native çağrı | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` | sadece 3 parametre — Java imzasında ne token ne de açık `media`/`guest` argümanı yok |
| Stanza derlemesi | native (`wa_call_link_create_v2`) | `link_create` IQ'nun kendisi, diğer tüm çağrı stanza'ları gibi (WA_CALL_SIGNALING.md §2) JNI sınırının altında oluşturulur |
| Sonuç | `CallLinkInfo` (creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self), native bir geri çağırmadan doldurulur | token geri okunur, sağlanmaz |
| URL | `AbstractC227619sp.A01(token, isVideo)`: `Uri.Builder().scheme("https").authority("call.whatsapp.com").appendPath(isVideo?"video":"voice").appendPath(token)` | istemci paylaşım URL'sini geri aldığı token etrafında şablonlar |

`kCallLinkTokenLength` veya `createCallLink`'in yakınında hiçbir `SecureRandom`/base62 üretici kodu yok, ve native kütüphane decompile edilemedi. **Unknown**: 22 karakterlik token'ın istemci tarafında üretilip `link_create`'de gönderildiği mi, yoksa sunucu tarafından atanıp ack'te döndürüldüğü mü — istemci-görünür çağrı noktasının token argümanı taşımaması sunucu-atanmışı destekler, ama bu kanıtlanmış değil, **inferred**'dir. `connected-limit` (`group_info`'da görülür, §6) sadece sunucu tarafından döndürülür; istemci tarafı setter bulunamadı. Bağlantı oluşturmada istemci tarafı hız sınırı bulunamadı.

---

## 4. Sorgu ve katılım (tested)

### 4.1 `link_query`

Herhangi bir call-id bilinmeden önce, kullanıcı kısmı olmayan call-domain JID'ine (`to: {user: null, server: "call"}`) çıplak gönderilir:

```
<call to="@call" id="...">
  <link_query token="7vEdtKy61dqCtbWAQ59zuO" media="video"/>
</call>
```

Ack:

```
<ack from="@call" class="call" type="link_query" id="...">
  <link_query link_creator="<host jid>" media="video" token="...">
    <guest is_guest_eligible="1"/>
    <waiting_room enabled="1"/>
  </link_query>
</ack>
```

`link_creator` host'u tanımlar; `is_guest_eligible` ve `waiting_room enabled`, bağlantının oluşturma anındaki ayarlarıdır (§3) ve geri yankılanır. Henüz call-id yok — bu ack sadece bağlantıyı önizler.

### 4.2 `link_join`

Aynı `token`/`media`'yı, seçilen bir `push_name` ve olağan offer-şekilli medya çocuklarıyla birlikte taşır:

```
<call to="@call" id="...">
  <link_join token="7vEdtKy61dqCtbWAQ59zuO" media="video" push_name="Baron als Gast ohne wa">
    <audio enc="opus" rate="16000"/>
    <video dec="H264" device_orientation="0"/>
    <net medium="2"/>
    <capability ver="1">...7 bytes...</capability>
  </link_join>
</call>
```

Sadece-sesli bağlantının `link_join`'i (ikinci yakalama) `<video>` çocuğunu tamamen atlar — doğrudan karşılaştırmayla doğrulandı, çıkarsanmadı:

```
<link_join token="ENcQnTAwKj7lQOdOHVJPmQ" media="audio" push_name="Baron aus web testt">
  <audio enc="opus" rate="16000"/>
  <net medium="2"/>
  <capability ver="1">...</capability>
</link_join>
```

`push_name`, misafirin bu katılım için seçtiği özgür metindir; hesabın kendi WhatsApp görünen adı değildir (her iki yakalamada da katılan hesap gerçek bir giriş yapılmış oturumdur, ama seçilen ad normal profil adından farklıdır — misafir kimliği bu aşamada sadece sunumsaldır). Gözlemlenen `<capability>` 7 baytı (`01 05 F5 09 E0 BB 53` video misafir, `01 05 F7 09 E0 3B 53` host) oturuma özgü değerlerdir, genel bir maske değil; WA_CALL_SIGNALING.md §5.2 Android capability bayt değerlerini genel olarak zaten unknown işaretlemiştir ve bu durum bunu çözmez.

`link_join`'in ack'i artık bir call-id taşır — sunucu çağrıyı çözmüş (veya başlatmış) demektir:

```
<ack from="@call" class="call" type="link_join" id="...">
  <waiting_room link-token="7vEdtKy61dqCtbWAQ59zuO" media="video"
                call-id="0076804DB4CA9D41EFCB547F08AE87BD"
                call-creator="<host jid>" enabled="1"/>
  <guest is_guest_eligible="1"/>
</ack>
```

### 4.3 Call-domain JID adresleme (tested)

Bu, WA_CALL_SIGNALING.md §10.1'de call-domain JID tipini tanımsız bırakan kısmı çözer:

1. `link_query` / `link_join` çıplak `call` alanını adresler — kullanıcı kısmı yok (`callDomainJID`).
2. `link_join` ack'inin bir `call-id` döndürdüğü anda, istemci sonraki in-call stanza'ları (bekleme-odası heartbeat'i, ve sonra mute/transport/relaylatency/video) `<call-id>@call`'a adreslemeye başlar — aynı alan altında kullanıcı-nitelikli bir JID (`callJID`).
3. Sunucunun kendi kabul push'u (§5) daha sonra `from="<call-id>@call"` ile gelir, gelen tarafta da aynı adresleme doğrulanır.

Yani call-id, öğrenildiği anda, sonrasında gelen her şey için *kendisi* JID kullanıcı-kısmıdır — adreslemenin yanında taşınan ayrı bir eşleştirme anahtarı değil.

---

## 5. Bekleme odası (tested)

Beklerken, katılmış ama henüz kabul edilmemiş misafir, call-id JID'ine periyodik bir heartbeat gönderir:

```
<call to="<call-id>@call" id="...">
  <heartbeat call-id="0076804DB4CA9D41EFCB547F08AE87BD" call-creator="<host jid>" type="waiting_room"/>
</call>
```
hemen onaylanır (`<ack ... type="heartbeat"/>`, içerik yok).

**Kabul üzerine ihtiyat**: bu yakalama tek-uçludur — sadece misafirin kendi bağlantısını gösterir. Bekleyen bir misafiri kabul eden host-tarafı eylem (`waitingRoomAdmit`, bir `waiting_room_toggle`/`_admit` stanza'sı gönderir, WA_CALL_SIGNALING.md §10.3'e göre) *host'un* bağlantısında çalışır ve burada gözlemlenmedi; bu rapor sadece sonucunu gösterir. Her iki yakalamada da kabul (§6), görünen tek heartbeat'ten çok kısa bir süre sonra (bir saniyenin çok altında) geldi — bu, uyanık bir host'un hemen Kabul'e dokunmasını mı yoksa bir otomatik-kabul koşulunu mu (örn. host zaten çağrıda etkin) yansıttığının **unknown** olduğu kadar hızlı; buradaki hiçbir kanıt ikisini birbirinden ayırmaz.

---

## 6. Misafir JID tahsisi (tested)

Kabul, `<call-id>@call`'dan sıradan bir `group_update`/`group_info` push'u olarak, yan yana iki `<user>` girişiyle — host ve misafir — gelir:

| Alan | Host girişi | Misafir girişi |
|-------|-----------|--------------|
| `jid` | `48615137533978` (`<device>` altında cihaz 24) | `29554559176938` (cihaz 0) |
| `type` | `admin` | *(yok — yükseltilmiş rol yok)* |
| `account_kind` | *(yok)* | `guest` |
| `push_name` | *(bu girişte yok)* | `Baron als Gast ohne wa` — §4.2'deki `link_join`'de gönderilen ad, roster'a harfiyen kopyalandı |
| `state` | `connected` | `connected` |
| cihaz `platform` | `web` | `web` |
| cihaz `pid` | `0` | `1` |

Misafirin JID'i (`29554559176938`), host'unkiyle aynı adres-şekli sınıfındadır (`type=1`, `domainType=1`, yani LID-tarzı, §2), bu çağrı için sunucu tarafından yeni tahsis edilmiştir — katılan oturumun kendi hesap kimliği değildir. Cihaz `pid`'i (misafir için `1`) aynı stanza'daki röle bloğunun `self_pid="1"`'ine (§7) uyar — roster'ın cihaz-başına katılımcı id'si ile röle'nin kendi katılımcı id'si aynı numaradır.

**Unknown**: bu misafir JID'inin aynı tarayıcı/oturum tarafından aynı bağlantının tekrarlanan katılımları arasında yeniden kullanılıp kullanılmadığı, ne kadar süre tutulduğu, veya host'a `push_name` ve `account_kind`'ın ötesinde görünür olup olmadığı.

---

## 7. Kabulde röle ve anahtar teslimi (tested)

Aynı kabul stanza'sı, `<group_info>`'nun kardeşi olan bir `<relay>` bloğu taşır, misafire medyaya daha fazla gidiş-dönüş olmadan erişmesi için gereken her şeyi verir. Alanlar WA_CALL_SIGNALING.md §8.2'deki dilbilgisiyle eşleşir; bu bölüm o raporun açık bıraktığı somut tel-seviyesi detayı ekler.

| Çocuk | Görülen sayı | Notlar |
|-------|-----------|-------|
| `<token id=N>` | 3 (id 0, 1, 2) | ham ikili, her biri 194 bayt |
| `<auth_token id=0>` | 1 | ham ikili, 70 bayt |
| `<key>` | 1 | 24 tel baytı — ama bu 24 bayt kendisi bir base64 dizesinin ASCII metnidir, bu da tekrar decode edildiğinde 16 baytlık ham bir anahtara dönüşür |
| `<hbh_key>` | 1 | 40 tel baytı — aynı desen: ASCII base64 metni, decode edilince 30 ham bayt |
| `<te2 relay_id auth_token_id token_id domain_name relay_name c2r_rtt>` | 6 (2 röle: `edgeray-ham3-1.wt.whatsapp.com`/`ham3c01`, `edgeray-ber1-1.wt.whatsapp.com`/`ber1c01`) | `<te>` yok — "ikisi birden asla" kuralını doğrular, bu çağrı `te2` kullandı |
| röle öznitelikleri | `attribute_padding`, `transaction-id`, `self_pid`, `uuid`, `participant_uuid` | `self_pid="1"`, `group_info`'daki (§6) misafirin kendi cihaz `pid`'ine bağlanır |
| `<participant pid jid>` | yok | 8.2'deki participant-id-JID eşleştirme çocuğu bu 2-taraflı yakalamada görülmedi; daha büyük grup çağrılarında sadece orada mı göründüğü unknown |

Sadece `<key>` ve `<hbh_key>`, çift-kodlanmış (ASCII base64 tutan ikili düğüm) formu taşır; `<token>` ve `<auth_token>` düz ham ikilidir. Bu çift katmanın ham baytları doğrudan göndermeye kıyasla ne kazandırdığı **unknown**'dır (metin-odaklı bir taşımanın kalıntısı, inferred).

`<group_info>`/`<relay>`'in de kardeşi olan bir `<voip_settings uncompressed="1">` çocuğu, bir motor-parametresi JSON blob'u taşır (bu yakalamada sıkıştırılmamış, WA_CALL_SIGNALING.md §5.2'nin sıkıştırılmış yüklerin en az bir yolda reddedildiği notuyla tutarlı). İçinde, `fs` (feature-switch) nesnesi altında: `"guest_calling_logging_enabled": "true"` — aksi halde genel ~32 KB'lik ayarlar belgesinde bulunan tek misafir-özel anahtar (`aec`, `bwe`, `decode`, `encode`, `sfu`, `rc`, ... — tümü genel medya-motoru ayarı, misafir katılımıyla ilgisiz). Bu çağrı etrafında katılan istemci tarafından gönderilen telemetri olayları bağımsız olarak `guest_calling` kategori dizesini kullanır (istemcinin kendi `w:stats`/WAM blob'larında görülür), bu da ayarlar anahtarının adlandırmasıyla eşleşir.

İki zararsız kardeş, `<uploadfieldstat/>` ve `<userrate interval="0"/>`, aynı stanza'da birlikte gider; misafire özel bir içerik yok.

İstemci bu push için hemen düz bir `<ack class="call" type="group_update">` gönderir (içerik yok) — WA_CALL_SIGNALING.md §3.3'e göre sıradan işleme (group_update, anında-ack-yok etiket setinde değil).

---

## 8. Kabul sonrası trafik (tested, kısa)

Kabul edildikten sonra, trafik aynı call-id JID'inde normal bir çağrıdan ayırt edilemez: `mute_v2` (bu yakalamada host, kabulden hemen sonra misafiri susturur), `transport` (`transport-message-type="4"`, bir `<net medium="2" protocol="0"/>` çocuğu), `relaylatency` (her iki yönde, her biri §7'deki röle adlarına referans veren bir `<te latency relay_name>` taşıyor), ve `video` durum değişiklikleri (`state="6"`, yani WA_CALL_SIGNALING.md §13'ün `kVideoState*` tablosuna göre `Stopped`, kurulum sırasında hızlıca üç kez tekrarlanıyor). Bunların hiçbiri bağlantıya özgü değil; genel semantik için WA_CALL_SIGNALING.md §§8, 13'e bakın.

---

## 9. Video ve sadece-sesli bağlantı — gözlemlenen farklar (tested)

| Yön | Video bağlantısı | Sadece-sesli bağlantı |
|--------|-----------|------------------|
| `link_query`/`link_join` `media` özniteliği | `video` | `audio` |
| `link_join` çocukları | `<audio>`, `<video>`, `<net>`, `<capability>` | `<audio>`, `<net>`, `<capability>` — `<video>` atlanır |
| `waiting_room` ack `media` | `video` | `audio` |
| Bekleme odası / misafir uygunluk mekaniği | aynı | aynı |

İki arasında başka bir protokol farkı gözlemlenmedi; medya tipi baştan sona düz bir öznitelik olarak taşınır, farklı bir stanza ailesi değil.

---

## 10. Normal 1:1 veya grup çağrısından farklar

| Yön | Normal 1:1 / grup çağrısı (WA_CALL_SIGNALING.md) | Misafir bağlantı katılımı (bu rapor) |
|--------|------------------------------------------------|-------------------------------|
| Giriş stanza'sı | bilinen bir eş/grup JID'ine `offer` | çıplak `call` alanına `link_query` sonra `link_join` |
| Çağrı anahtarı | offer içinde cihaz-başına Signal-şifreli `Message.call.callKey` | bu yakalamanın kabulünde gözlemlenmedi; misafir röle/anahtar materyalini (§7) doğrudan alır, Signal-sarmalanmış bir çağrı anahtarı değil — misafirin host ile eşli bir Signal oturumu olmamasıyla tutarlı |
| Arayan/aranan kimliği | çağrı başlamadan önce her iki taraf da bilinen JID'dir | katılan tarafın gerçek kimliği roster'da ifşa edilmez; sunucu yeni bir JID tahsis eder ve `account_kind="guest"` ile etiketler |
| Kabul | yok — offer/accept tek kapıdır | isteğe bağlı bekleme odası: `waiting_room enabled`, (gözlemlenmemiş, host-tarafı) bir kabul'e kadar tutulur |
| Roster teslimi | offer içinde veya daha sonraki bir güncellemede `group_info` | `<call-id>@call`'dan bir `group_update`/`group_info` push'u, aynı stanza'da `<relay>` ve `<voip_settings>` ile paketlenmiş |
| JID adresleme | baştan sona eş/grup JID'i | call-id oluşana kadar çıplak `call` alanı, sonra `<call-id>@call` |

Misafir için eksik olan cihaz-başına çağrı anahtarı (satır 2) en önemli farktır ve sadece bu yakalamada bir yokluk olarak **tested**'dir — bir protokol kuralı olarak doğrulanmamıştır; bu, WA_CALL_SIGNALING.md §9.2'nin grup offer'larının cihaz-başına anahtar taşımadığı ve anahtarların bant-dışı yeniden paylaşıldığı (`enc_rekey`) notuyla da tutarlıdır. Bir misafirin hiç `enc_rekey` alıp almadığı, burada kullanılan iki yakalama penceresinde de gözlemlenmedi.

---

## 11. Hata durumları / tuzaklar

| Belirti | Sebep | Çözüm / not |
|---------|-------|-----------|
| `link_query` ack'inin call-id'si yok | bağlantı henüz çalışan/başlatılabilir bir çağrıya çözülmedi | çıplak önizleme için normal; call-id sadece `link_join` ack'inde gelir |
| `link_join` ack'inden sonra misafir sıkışıp kalıyor, sadece heartbeat alışverişi oluyor | bekleme odası etkin ve host henüz kabul etmedi | host-tarafı eylem gerekli; misafirin bağlantısından görünür değil |
| `link_join`, sadece-sesli bir bağlantı için `<video>` çocuğu taşıyor | istemci hatası — iki yakalama bu çocuğun `media="audio"` için tamamen yok olması gerektiğini gösteriyor | sadece-sesli katılımlar için `<video>`'yu atla |
| Misafirin kendi hesap JID'i, yeni bir misafir JID'i yerine çağrı roster'ında görünüyor | yanlış katılım yolu (`link_join` yerine sıradan `offer`/grup katılımı) | `account_kind="guest"` işlemesi için `link_query`→`link_join` kullan |
| Misafir çağrı anahtarı almıyor ama röle/anahtar materyali var | bu yol için beklenen durum (§10) — misafir normal bir aranan gibi Signal-sarmalanmış bir anahtar almıyor | bunu bir şifre çözme hatası olarak ele alma |

---

## 12. Önemli ayrımlar

| Karıştırılmamalı | Şununla |
|-----------------|------|
| Çağrı-bağlantısı **token**'ı (22 karakter, URL'e dönük) | Call-**id** (32 hex karakter, protokole dönük, sadece `link_join`'den sonra görünür) |
| Çıplak `call` alan JID'i (call-id öncesi) | `<call-id>@call` (call-id sonrası) — ikisi de farklı aşamalarda "call-domain JID"dir, iki ilgisiz adres değil |
| `is_guest_eligible` (bağlantı ayarı: bu bağlantıya *herkes* misafir olarak katılabilir mi) | `waiting_room enabled` (bağlantı ayarı: misafirler kabul için tutulur mu) — bağımsız bayraklar, her ikisi de aynı ack'lerde yankılanır |
| `link_join` üzerindeki misafir `push_name`'i (özgür metin, katılım başına seçilir) | katılan hesabın kendi WhatsApp profil adı (bir misafir katılımı için roster'a girmeyen şey) |
| `<key>` / `<hbh_key>` tel baytları (ASCII base64 metni içeren ikili düğüm, çift-decode gerekli) | `<token>` / `<auth_token>` tel baytları (düz ham ikili, tek decode) |
| Misafir JID tahsisi (sunucu tarafı, kabul anında, çağrı başına) | normal LID/PN JID'leri (hesap seviyesinde, kalıcı) |

---

## 13. Tam akış (misafir katılımı, yakalamadan)

```
[Guest client]  already has a chatd session (own identity, not used for the call)
     │  <call to="@call"><link_query token media/></call>
     ▼
[WA Server]  resolves the token
     │  ack: link_creator, media, token, <guest is_guest_eligible/>, <waiting_room enabled/>
     ▼
[Guest client]  <call to="@call"><link_join token media push_name><audio/>[<video/>]<net/><capability/></link_join></call>
     ▼
[WA Server]  starts/resolves the call
     │  ack: <waiting_room link-token media call-id call-creator enabled/>, <guest is_guest_eligible/>
     ▼
[Guest client]  learns call-id → addresses it as <call-id>@call from now on
     │  <call to="<call-id>@call"><heartbeat call-id call-creator type="waiting_room"/></call>  (repeats)
     ▼
[Host, out of band — not in this capture]  taps Admit (waiting_room_toggle/_admit)
     ▼
[WA Server]  <call from="<call-id>@call"><group_update><group_info ...>
                 <user host .../><user account_kind="guest" push_name jid=<allocated> .../>
              </group_info>
              <relay token×N auth_token key hbh_key te2×N/>
              <voip_settings uncompressed fs.guest_calling_logging_enabled=true/>
              </group_update></call>
     │  ack: <ack class="call" type="group_update"/>
     ▼
[Both]  ordinary call traffic on <call-id>@call: mute_v2, transport, relaylatency, video state
              (see WA_CALL_SIGNALING.md §§8, 13 for generic semantics)
```

---

## 14. Bilinmeyenler

| Öğe | Durum |
|------|--------|
| Token üretim yeri (istemci-üretimli vs. sunucu-atanmış) | `createCallLink` çağrı noktasının token argümanı yok (found); gerçek köken native'dir (unknown) |
| Gerçekten hesapsız bir tarayıcı oturumunun aynı stanza dizisini üretip üretmediği | yakalanmadı — her iki yakalama da zaten kimlik doğrulanmış bir bağlantı üzerinde, misafir olarak katılmayı seçerek çalıştı |
| Host-tarafı kabul eylemi (`waiting_room_toggle`/`_admit`) tel şekli | bu yakalamada yok (tek-uçlu); sadece WA_CALL_SIGNALING.md §10.3 statiklerinden anlatılır |
| Kabulün görülen tek heartbeat'ten neden bu kadar hızlı geldiği | uyanık host mu yoksa bir otomatik-kabul koşulu mu — bu kanıttan ayırt edilemiyor |
| Misafir JID ömrü / tekrarlanan katılımlar arasında yeniden kullanım | gözlemlenmedi |
| Bir misafirin hiç `enc_rekey` veya herhangi bir Signal-sarmalanmış çağrı anahtarı alıp almadığı | her iki yakalama penceresinde de gözlemlenmedi |
| `<relay>` altındaki `<participant pid jid>` eşleştirmesi | bu 2-taraflı yakalamada yok; misafirli grup çağrılarının onu kullanıp kullanmadığı unknown |
| `<key>`/`<hbh_key>`'de çift base64 kodlamasının amacı, ham `<token>`/`<auth_token>`'a kıyasla | unknown |
| `connected-limit`'in istemci tarafından ayarlanabilir bir sınır mı yoksa her zaman sunucu tarafından mı atandığı | istemci tarafı setter bulunamadı (found: sadece sunucu tarafından döndürülür) |
| Bağlantı oluşturma veya misafir katılımlarında hız sınırları / kötüye kullanım kontrolleri | istemci tarafında hiçbir şey bulunamadı; sunucu davranışı unknown |
