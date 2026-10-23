<!-- src-sha1: e4fe5d62fca781d0449295a5d549413929d95191 -->
# WhatsApp Broadcast Lists — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android'de klasik broadcast listeleri ve status broadcast'leri: `@broadcast` JID modeli (list / status / location), liste oluşturma, üyelik limitleri ve alıcı kuralları, `w:b` IQ'ları (listeleri alma, liste silme, kota), app-state `business_broadcast_list`, LID migrasyonu, yerel depolama, alıcı başına clone-on-insert, gönderim stanza'sı (sender-key fan-out, `phash`, `bucketing`, `<cap>`, alıcı başına ephemeral ayarları), ack ve receipt birleştirme, aylık broadcast kotası, spam-warning ban'ları, GAP, `status@broadcast` paylaşımı (`SendE2eStatusJob`, parçalar, manuel bucket'lar), status gizlilik modları, yakın arkadaşlar ve özel hedef kitleler, status yanıt / tepki / mention / notify, status tabloları, feature flag'ler, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

Üç sunucu `broadcast` JID'i vardır. Hepsi "multi-participant" JID'dir (`AbstractC20660pZ`, gruplarla aynı taban) ve tek bir gönderim hattını paylaşır: gönderen bir kez sender key ile şifreler ve anahtarı her alıcı cihaza pairwise iletir. Tüm ifadeler derlenmiş APK'nın statik analizine dayanır; ağ üzerinde hiçbir şey yakalanmadı. Tier: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi. Burada hiçbir şey **tested** değildir. Obfuscated isimler 2.26.41.6'da sabit string'lerden yeniden çözüldü (`BroadcastListManager/…`, `BroadcastXmppMethods/…`, `StatusParticipantUserManager/…`, `SendE2eStatusJob/…`, tablo ve pref isimleri).

| Varlık | JID biçimi | `Jid.getType()` | Sınıf | Rol |
|--------|------------|-----------------|-------|-----|
| Klasik broadcast listesi | `<id>@broadcast` | 3 | `C99P` | birincil cihaz listesi, alıcılar 1:1 kopya alır |
| Status broadcast | `status@broadcast` | 5 | `C199018dF` | status paylaşımları, hedef kitle paylaşım başına seçilir |
| Location broadcast | `location@broadcast` | 6 | `BOC` | JID modelinde var; kullanımı izlenmedi (canlı konum addan çıkarıldı, inferred) |
| Kendi status sahte kullanıcısı | `status_me` (yerel) | 11 | `C0Dh` | yalnızca yerel takma ad, wire JID değil (rol inferred) |

Kapsam dışı: newsletter'lar (`SendNewsletterStatusJob` ayrı bir job'dur), Business kampanyaları ve insights, Android OS broadcast'leri.

| Bileşen | 2.26.41.6 adı | Rol |
|---------|---------------|-----|
| JID parser / yardımcılar | `C0DJ.A00` / `C0DZ.A0P`, `A0Q`, `A0h` | `broadcast` sunucusu: user `location` → `BOC`, `status` → `C199018dF`, aksi halde `C99P`; yardımcılar herhangi bir broadcast (3, 5, 6) / list (3) / status (5) için true döner |
| Liste ayırıcı / yönetici | `C0YJ.A0E` / `A0K` (`BroadcastListManager`) | yeni liste id'si / katılımcı ekleme ve çıkarma |
| LID filtresi ve migrasyonu | `C70552yj` (`BroadcastListLidMigrationHelper`), `C0UV` (migrasyon görevi) | PN → LID |
| Katılımcı yöneticisi / store | `C22300su` (`A0j` ekle, `A0k` çıkar), `C14850fN` (`ParticipantUserStore`) | gruplarla ortak |
| Liste IQ'ları | `C18240lQ` (`BroadcastXmppMethods`), `AKU` (sonuç işleyici), `BroadcastListQuotaProtocol` + `C9EN` | listeleri alma, liste silme, kota |
| Kota istemcisi | `C720733k` (repository), `C2EX` (view model), `C74823Ej` (mesaj listener'ı) | aylık limit |
| App-state mutation | `C224469lG` (dispatch), `C26057BNq` (`BusinessBroadcastListMutation`) | `business_broadcast_list` |
| Clone-on-insert | `C231399zG` (`BroadcastCloneOnInsertProcessor`), `AJO` | alıcı başına yerel kopyalar |
| Ack / receipt'ler | `C22500tF`, `C22790ti` (`MainMessageStore`), `C269411e` (`MessageStatusStore`) | sunucu ack'i, receipt ayrıştırma |
| Şifreleyici / job'lar | `F6P` (`E2eMessageEncryptor`), `SendE2EMessageJob`, `SendE2eStatusJob` | sender key, SKDM, stanza oluşturma |
| Gelen doğrulayıcı | `C34757F6a` (`CompanionSupportVerifier`) | companion'larda liste kopyalarını düşürür |
| Status hedef kitlesi | `C11550Zh` (`StatusInfoStore`), `C182877r0` (dağıtım bilgisi), `C23140uH` (`StatusParticipantUserManager`), `C1889082i` (`StatusCustomListStore`), `C23340ub` (bucketing yapılandırması) | gizlilik modları, listeler, bucket'lar |
| Status gizlilik senkronizasyonu | `C48386LBh` (`StatusPrivacySyncMutation`), `C49626LsR` (Wire `StatusPrivacyAction`), `M7H` (mod enum'u) | app-state action 44 |

---

## 2. JID modeli

### 2.1 Ayrıştırma (found)

| Kural | Değer |
|-------|-------|
| Sunucu | `broadcast` |
| User `status` / `location` | singleton'lar `C199018dF` / `BOC` |
| Diğer herhangi bir user | `C99P`: uzunluk 1..20, ilk karakter `1`..`9`, kalan karakterler `0`..`9`, aksi halde `C09B` fırlatılır |

Baştaki sıfır olmaması kuralı `C99P` constructor'ından okunur (smali `0x31`/`0x39` ile karşılaştırır, kalanı `0x30`..`0x39`). Liste `g.us` değildir, ancak grup katılımcı mekanizmasını yeniden kullanır (3.5).

### 2.2 Ayırma (found, `C0YJ.A0E`)

Id, `System.currentTimeMillis() / 1000` değerinin ardından `@broadcast` şeklindedir; bu id'ye sahip bir liste yerelde varsa bir saniye artırılır. Benzersizlik yalnızca yerel sohbet listesine karşı denetlenir; ayırmadan önce sunucu çağrısı yoktur (create IQ yoktur, 3.3). Sunucunun keyfi bir id'yi kabul edip etmediği statik olarak belirlenemez.

---

## 3. Liste yaşam döngüsü

### 3.1 Oluşturma (found, kısmen inferred)

```
[Picker]  "New broadcast" (menu item hidden when BRD() = companion mode), max 256 selected
     ▼
createBroadcastList callback (C222519hZ):
     │   C0YJ.A0E()                                allocate <seconds>@broadcast
     │   A0K.A04(jid, users): C70552yj.A00 → LID filter ; C22300su.A0h → local participants ; contact entry (name "")
     ▼
compose flow opens; system message "You created broadcast list "X" with N recipients"
```

`A0K.A04` hiçbir IQ ve app-state mutation yaymaz (found). Sunucu tarafından görülen ilk olay, liste JID'ine yapılan ilk gönderimdir (4.2); sunucunun liste durumunu buradan türettiği inferred'dır. Aynı ayırma newsletter takipçi davetleri için yeniden kullanılır (`userActionSendNewsletterFollowerInviteMessages`, found).

### 3.2 Üyelik limitleri ve alıcı kuralları

| Kural | Değer | Tier |
|-------|-------|------|
| Maksimum alıcı | 256: `ContactPickerFragmentKt.A39` `selected.size() > 256` durumunu reddeder (`Broadcast to a maximum of %d people at a time`); picker sınırı `min(256, groupLimit - 1)` | found |
| Alıcı kaynağı | kişi seçici; izin metni `To create a broadcast … allow WhatsApp access to your contacts`; engellenen kişiler: `To add to broadcast list, unblock %s` | found |
| Alıcıda gönderenin kayıtlı olması gerekir | yalnızca UI metni (`Only contacts who have you in their address book will receive your broadcast messages.`); uygulama sunucu tarafındadır | found (metin), unknown (uygulama) |
| LID adresleme | `A0K.A01` her zaman `lid` döndürür; LID eşlemesi olmayan PN katılımcıları düşürülür (`lid-broadcast-filtered-participants`) | found |
| Gönderimde eksik eşleme | `missing_pn_lid_mapping_for_broadcast`: clone atlanır, encryptor `E39(device, 4)` fırlatır | found |
| Boş katılımcı kümesi | `saveGroupParticipants/broadcast_would_be_cleared`; flag **30111** ile (varsayılan true) saklanan katılımcılar korunur | found |

### 3.3 Sunucu IQ'ları (found)

Listelere yalnızca üç IQ dokunur. Create veya edit IQ'su yoktur.

```xml
<!-- restore: BroadcastXmppMethods/sendGetBroadcastLists -->
<iq to="s.whatsapp.net" xmlns="w:b" type="get" id="…"><lists/></iq>
<iq type="result"><lists>
  <list id="1760000000@broadcast" name="Family">
    <recipient jid="<lid>@lid" pn_jid="<pn>@s.whatsapp.net" username="…"/>   <!-- pn_jid, username read for LID recipients -->
  </list>
</lists></iq>

<!-- delete: sendDeleteBroadcastList -->
<iq to="s.whatsapp.net" xmlns="w:b" type="set" id="…"><delete><list id="1760000000@broadcast"/></delete></iq>

<!-- quota (5.1) -->
<iq to="s.whatsapp.net" xmlns="w:b" smax_id="143" type="get" id="…"/>
```

Üçü de 32 sn timeout kullanır. `AKU` (get sonucu), yerel sohbeti veya kişi girdisi olmayan her `<list>` için sohbeti (`A0K.A00`, sistem mesajı tipi 9) ve bir kişi girdisini oluşturur, ayrıca `pn_jid` ve `username` eşlemelerini saklar. Silme `C18240lQ.A01` tarafından gönderilir ve ardından bir app-state REMOVE gelir (3.4).

Geri yükleme tetikleyicisi (found): `RegistrationInitializer/shouldrefreshlists`, pref `refresh_broadcast_lists=true` değerini ayarlar ve kayıttan sonra get-lists gönderir (get-privacy-settings ile birlikte); `MessageHandlerCallback/ready`, pref true olduğu sürece bunu tekrarlar; `AKU` temizler. Dolayısıyla sunucu listeleri hesap başına saklar (found, çıkarım yoluyla). Sunucunun bir listeyi nasıl öğrendiği istemci tarafında görünmez (unknown, bkz. 3.1).

### 3.4 App-state mutation (found)

| Öğe | Değer |
|-----|-------|
| Action | `BusinessBroadcastListAction`, wire adı `business_broadcast_list` (`EnumC24865AnN.A0H`, ordinal 62), `SyncActionValue` alanı **69**, collection `regular`, API sürümü 7 |
| Index | `["business_broadcast_list", "<list jid>"]` |
| İşlem | ekleme, çıkarma, yeniden adlandırmada SET; liste silinirken `deleted=true`, boş katılımcılar, ad `""` ile REMOVE (`A0T`, `syncBusinessBroadcastListRemoval`) |
| Gate | `C12440bB.A0b()` (syncd engellenmemiş veya companion-dirty); Business hook'ları (`storeForBroadcast`, `onAudienceChanged`, `getCustomAudienceFbidForBroadcast`) bu APK'da yoktur |
| Çağıranlar | `A0K.A03` / `A05` (ekle / çıkar), `BroadcastListChatInfoActivity` içinde yeniden adlandırma, `C24085AaS` (katılımcı kümesi) |
| Uygulama tarafı | hiçbir handler `EnumC24865AnN.A0H` referansı vermez; yalnızca yazıcı (`C26057BNq`) ve `BD4` içindeki alan erişimcisi vardır, dolayısıyla tüketici tarafının apply davranışı unknown'dır |

| Alan | Numara | Tip | Değer / kullanım |
|------|--------|-----|------------------|
| `deleted` | **1** | bool | liste kaldırıldı |
| `participants` | **2** | repeated `BroadcastListParticipant` | hedef kitle (`lid_jid` **1** zorunlu, `pn_jid` **2**) |
| `list_name` | **3** | string | konu |
| `label_ids` | **4** | repeated string | label hedef kitlesi (participants'a alternatif, asla ikisi birlikte) |
| `audience_expression` | **5** | string | dinamik hedef kitle (Business) |
| `custom_audience_fbid` | **6** | string | yalnızca Business |

Aynı collection: `BusinessBroadcastCampaignAction` (81), `BusinessBroadcastInsightsAction` (82), `MarketingMessageBroadcastAction` (39); yalnızca enum olanlar `BusinessBroadcastAssociationAction` (59) ve `BusinessBroadcastAction` (94). Temeller: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md).

### 3.5 LID migrasyonu, depolama, companion'lar

`BroadcastListLidMigrationTask` (`C0UV`) her listeyi PN'den LID katılımcılarına dönüştürür: eksik LID'ler için bir usync (hata `usync_failed` olarak loglanır, görev devam eder), ardından `C70552yj.A03` PN katılımcılarını kaldırır ve LID kümesini tek bir transaction'da ekler.

| Store | İçerik | Tier |
|-------|--------|------|
| `chat` / `chat_view`, `jid.type = 3`, `subject`, `created_timestamp`, `hidden` | liste sohbeti (`C222989iV`) | found |
| `group_participant_user` (`group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `label`, `add_timestamp`), `group_participant_device` | alıcılar, gruplarla ortak | found |
| `wa_group_admin_settings` (`jid`, `addressing_mode`, `group_state`) | liste başına adresleme modu (telemetri `@broadcast` satırlarını sayar) | found |
| `message` sütunları `broadcast`, `recipient_count`, `participant_hash`, `key_id`, `chat_row_id`, `from_me` | liste mesajı ve ack verisi | found |
| `message_broadcast_ephemeral` (`message_row_id`, `shared_secret`) | liste kaybolan mesajları için mesaj başına secret | found |

Companion'lar (found): `New broadcast` / `Broadcast lists` menü öğeleri yalnızca `BRD()` false iken eklenir; `C34757F6a`, `<participants>` taşıyan kendi hesabına ait bir liste kopyası için `E3A(415, "received peer broadcast message on companion-mode, dropping", 18)` fırlatır; action 69'un apply handler'ı yoktur.

---

## 4. Listeye gönderim

### 4.1 Yerel fan-out (found, `C231399zG`)

```java
// A02(msg): msg.fromMe, not one of two excluded message classes, status 0 or 2 (or 4 with flag 26867)
msg.A0Z = true;                                   // message.broadcast = 1
for (recipient : msg.A0A())                       // recipient list stored on the FMessage
    normalized = lidMapper.A0C(recipient);        // null → missing_pn_lid_mapping_for_broadcast, skip
    store.add(cloneFactory.A00(msg, new C1ZA(normalized, msg.key.id, true)));   // own row in the recipient's 1:1 chat
```

| Özellik | Değer |
|---------|-------|
| Mesaj id'si | liste mesajı ve her clone için aynı (`key_id` kopyalanır, yalnızca sohbet farklıdır) |
| Sayaçlar | liste satırında `recipient_count` (`FMessage.A06`); medya dosyası referans sayısı clone sayısı kadar artar |
| Yinelenenler | mevcut bir clone anahtarında `SQLiteConstraintException` loglanır ve atlanır |
| Kaybolan mesajlar | clone, alıcı başına ayarı ephemeral map'ten alır (alıcının birincil cihazına göre anahtarlanır); süre sonu satırları `message_ephemeral` içinde |

### 4.2 Wire formatı (found, kısmen inferred)

Liste JID'ine adreslenen tek bir stanza (örnek, öznitelik değerleri açıklayıcıdır). Şifreleme grup yolunu yeniden kullanır (`F6P`, `AbstractC20660pZ` üzerinde tiplenmiştir): bir sender-key ciphertext artı cihaz başına sender-key distribution message'lar. Sender-key ve session temelleri burada tekrarlanmaz.

```xml
<message to="1760000000@broadcast" type="text" id="3EB0…" t="…" phash="2:AbCdEf==" addressing_mode="lid">
  <participants>
    <to jid="<recipient device jid>"><enc v="2" type="pkmsg|msg" …/></to>   <!-- SKDM wrapped pairwise -->
  </participants>
  <enc v="2" type="skmsg" …/>                                                <!-- message under the sender key -->
  <cap client_capping_ready="true|false"/>                                   <!-- flag 16656 only -->
</message>
```

| Öznitelik | Kaynak | Notlar |
|-----------|--------|--------|
| `to`, `type`, `id`, `t` | sohbet JID'i (`C33150EcP.A07`), `AbstractC30999De0.A02`, `C1ZA.A01`, `originalTimestamp` | `to` liste JID'idir (ortak builder'dan inferred); `t` yalnızca sıfırdan farklıysa |
| `phash` | `groupParticipantHash` | 4.3 |
| `bucketing` | `eva.A05` | flag **28183** ve katılımcı sayısı ≥ **28185** (512) iken `primcomp`; listeler (≤ 256) pratikte ayarsız kalır (inferred) |
| `addressing_mode` | `lid` | type-28 JID'ler için atlanır |
| `participant`, `recipient`, `recipient_pn`, `peer_recipient_pn`, `peer_recipient_username` | job alanları | peer / retry / DSM gönderimleri |
| `edit`, `expiration`, `device_fanout="false"`, `privacy_sensitive="1"` | job alanları | isteğe bağlı |

Çocuklar contributor'lardan gelir (`InterfaceC35538FaZ.ASY`, `processStanzaNodeParamsUsingNewFramework`). `F69`, flag **16656** açıkken liste sohbetleri için `<cap client_capping_ready="…"/>` ekler; değer flag **13537**'dir.

| Adım | Ayrıntı | Tier |
|------|---------|------|
| Alıcı cihazlar | katılımcı yöneticisi kümesi eksi cihaz tipleri 26 / 27 (`F6P.A07`, hosted devices inferred); liste sohbetlerinde `AxolotlMultiDeviceSessionRequirement`, kendi companion cihazlarını (`BPE`: kendi user'ı, birincil olmayan) SKDM hedef kümesine ekler | found / inferred |
| Sender key adı | (kendi cihaz adresi, `groupId` string'i `A0J`); `A0J`, `SenderKeyDistributionMessage.groupId` içine yazılır; `encryptForGroup`'tan gelen `-1002` durumu = geçersiz sender key, döndürülür | found |
| Alıcı başına ephemeral blob'lar | `F6P.A0A` (`buildBroadcastListEphemeralSettings`): pairwise map'te eksik olan her alıcı cihaz için (kendi companion'ları atlanır) `EphemeralSetting(expiration or afterReadDuration, timestamp)` oluşturur ve mesajın `shared_secret` değeriyle native olarak şifreler (`JniBridge.jvidispatchOOOOOOO`); eksik ayar `E39(device, 4)` fırlatır. Amaç (tek stanza içinde alıcı başına zamanlayıcılar) inferred | found / inferred |
| Kendi cihazları | mesaj `destinationJid = list` ve alıcı cihazların `phash` değeri ile `DeviceSentMessage` içine sarılır (`C33284Eea.A01`) | found |
| Boyut | `BoundedStanzaSizeException` → `stanza-too-large` / `large payload` | found |

### 4.3 `phash` (found, `AbstractC44221r5`)

`<version>:` + sıralanmış alıcı cihazlar üzerindeki SHA-256'nın ilk 6 baytının base64'ü (`NO_WRAP`, padding korunur). Sürüm `2:`, `user.0:device@server` string'lerini hash'ler (flag **16731** false, varsayılan); sürüm `3:`, cihaz ham string'lerini hash'ler (flag **16731** true). Grup, liste ve status stanza'larında kullanılır.

### 4.4 Ack ve receipt'ler (found)

| Olay | İşleme |
|------|--------|
| Sunucu ack'i | `C22500tF` → `C22790ti.A04`: liste sohbetleri için (status değil) `chat_row_id IN (liste sohbeti, her clone sohbeti) AND from_me = 1 AND key_id = ?` koşuluyla `message` tablosunu `status`, `receipt_server_timestamp`, `recipient_count` ile günceller; alıcı listesi `recipient_count` değerinden kısa olduğunda `timestamp/from_me/key_id` ile taramaya geri düşer (`UPDATE_RCV_BROADCAST_SERVER_SQL`, log `message-table-scan`) |
| Alıcı receipt'i | `MessageStatusStore.splitStatusUpdateReceipts`: liste anahtarı için gelen receipt, clone'a `(normalized recipient, same id, fromMe)` olarak eşlenir ve clone'a (`broadcast-individual`) ile multi mesaja uygulanır; status düşürmeleri atılır (`broadcast-statusdowngrade`); bilinmeyen clone `nosuchmessage for broadcast` loglar |

Liste satırının özet status kuralı ve alıcının telefonunda görünen durum çözülmemiştir (unknown).

---

## 5. Limitler ve kötüye kullanım kontrolleri

### 5.1 Aylık broadcast kotası (found, tüketici yolu)

```
iq get xmlns=w:b smax_id=143
  → <limits is_heavy_sender="true|false" messages_left="N" total_limit="M"/>
    <timeframe start_ts_s="…" reset_ts_s="…" end_ts_s="…"/>
```

İstemci aralık kontrolleri: `messages_left` 0..300, `total_limit` 1..300, zaman damgaları 2020-01-01..2100-01-01. Hata IQ kodları istemci sonuçlarına şöyle eşlenir: `400` → 3, `401` → 4, `403` → 5, `500` → 1, diğerleri → 0, bağlantı yok veya teslim hatası → 2 (`consumer_broadcast_capping_iq_error_response`).

| Mekanizma | Ayrıntı |
|-----------|---------|
| Cache | pref'ler `broadcast_quota_messages_left`, `_message_limit`, `_last_timestamp_fetched_ms`, `_heavy_sender`, `_start_timestamp`, `_end_timestamp`, `_reset_timestamp` |
| Yenileme | son fetch'ten bu yana geçen süre flag **13818** dakikayı (varsayılan 1440) aştığında veya now ≥ `reset_ts_s` olduğunda (kombinasyon decompile'da bozuk, OR inferred) |
| Azaltma / artırma | `C74823Ej`: `broadcast` işaretli ve muaf mesaj tipi kümesinde (`C2EX.A00`) olmayan her eklenen liste mesajı için, alıcı başına değil mesaj başına; gönderilmemiş liste mesajları silindiğinde `total_limit` ile sınırlı olarak geri artırılır |
| Gönderim öncesi engel | `C20M` içindeki predicate: liste sohbeti ve flag'ler **16585** ve **13537** ve `messages_left == 0` → gönderim reddedilir, bottom sheet `You've reached the broadcast limit for this month` |
| UI / telemetri | `Send up to %d broadcasts per month`, heavy sender'lar için onboarding sheet (`CappingBroadcastManager`); `wam_broadcast_list` (`blLimit`, `currentBlSends`, `numBlLists`, `broadcastListSize`) |

Limit değeri sunucu tarafından sağlanır; istemcide yalnızca aralık kontrolü vardır. Business tarafı hook'ları (`isSmbPremiumBroadcastCappingEnabled`) bu APK'da stub'dır.

### 5.2 Spam-warning ban'ları (found)

`SpamWarningActivity` bir sunucu kodu (`spam_warning_reason_key`), `expiry_in_seconds`, isteğe bağlı sunucu metni ve FAQ URL'si alır. Kodlar: **101** adres defterinde göndereni bulunmayan kişilere mesajlar, **102** çok fazla engelleme, **103** göndereni kayıtlı olmayan kişilerle gruplar, **104** aynı mesajın çok fazla kişiye gönderilmesi, **106** bir broadcast listesine çok fazla mesaj; diğerleri genel hizmet şartları ban'ını gösterir. Teslim yolu ve ban yüzeyinin geri kalanı: [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md). Eşikler sunucu tarafındadır (unknown).

### 5.3 Config 20278 ve GAP

- Config **20278** yalnızca iki varsayılan tabloda `{"max_messages": 10000, "farthest_time_days": 30}` varsayılan string'i olarak bulunur. Tüketici kodunda `max_messages` / `farthest_time_days` için başka referans yoktur, dolayısıyla okuyucu bulunmadı. Tüketici liste limiti değildir (5.1); kullanımı unknown'dır (Business tarafı varsayılanı).
- GAP (`com.whatsapp.gapenforcement`, flag **14837**, varsayılan false) alım tarafındadır: `GapEnforcementTrigger.onMarketingMessageReceived` ve `RulesManager`, marketing-message thread'leri için inbox kurallarını değerlendirir (`parseMaxMmThreadsInTopInboxSize`, `parseNoConsecutiveInTopInboxSize`, `parseMinNUpdatedP`) ve doğruluk sonuçlarını loglar; companion'larda çalışmaz ve listelerden gönderimleri sınırlamaz. Kısaltmanın açılımı APK'da yoktur (unknown).

---

## 6. status@broadcast

### 6.1 Gönderim hattı (found)

`SendE2eStatusJob` bir tipe sahiptir (`EnumC32060Dzj`): `STATUS` 0 (paylaşımın kendisi, tablo `status`), `STATUS_ADD_ON` 1 (tepkiler ve diğer eklentiler, `status_add_on`), `STATUS_NOTIFY` 2 (yanıt / yeniden paylaşım / mention bildirimleri, `status_notify`). Stanza, 4.2'deki öznitelik builder'ını ve `<meta>` contributor'larını kullanır (örnek, öznitelik değerleri açıklayıcıdır):

```xml
<message to="status@broadcast" type="media" id="3EB0…" phash="2:…" bucketing="manual" addressing_mode="lid">
  <participants><to jid="<device>"><enc v="2" type="pkmsg|msg"/></to>…</participants>
  <enc v="2" type="skmsg" bucket="f1"/>                      <!-- one per bucket when bucketed -->
  <meta status_setting="contacts" session_scope="status"/>
</message>
```

| Öznitelik | Kabul edilen değerler (stanza değer kümeleri, `C9E2`) |
|-----------|-------------------------------------------------------|
| `status_setting` | `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist` |
| `content_type` | `add_on`, `status_notify` |
| `message_association_type` | `av1_video_dual_upload`, `hd_image_dual_upload`, `hd_video_dual_upload`, `hevc_video_dual_upload` |
| `interaction_type` | `question`, `question_reshare` (`parent_server_id`, `response_server_id` ile) |
| `bucketing` | `manual`, `primcomp`, `threebuckets` (`threebuckets` yalnızca değer kümesinde) |

| Öğe | Ayrıntı |
|-----|---------|
| Ack timeout | 300000 ms (`no ack within 300000ms`) |
| Parçalar | büyük hedef kitleler bölünür: `status_send_part` (`status_row_id`, `part_code`, `is_first_part`, `device_count`, `state`, `sent_timestamp`, `ack_timestamp`, `error_code`, `stanza_devices_hash`); cihaz takibi `status_receipt_device` içinde (`uuid`, `receipt_device_jid`, `receipt_device_timestamp`, `primary_device_version`, `part_code`) |
| Grup status'u | `buildGroupStatus called with non-PermanentGroupJid`; `is_group_status`; Message alanları 92 / 96 / 103 |
| Oluşturma hataları | `StatusStanzaBuildFailureReason`: `MISSING_RETRY_CIPHERTEXT`, `TARGETS_UNRESOLVABLE`, `PART_ATTEMPT_PERSISTENCE_FAILED`, `CANONICAL_ACK_PENDING`, `EMPTY_FANOUT`, `NON_CURRENT_BATCH`, `MISSING_SENDER_KEY_CIPHERTEXT`, `UNKNOWN` |
| Job hataları | `encryption_limit`, `out_of_memory`, `payload_too_large`, `stanza_error`, `stanza_too_large` (flag **29113** açıkken işlenir), `unrecoverable_error` |

### 6.2 Hedef kitle: gizlilik modları (found)

Hedef kitle gönderen tarafında çözülür ve açık alıcı cihazlara genişletilir; `status_setting` özniteliği yalnızca modu etiketler. Yerel durum: `C11550Zh` (pref'ler `status_distribution`, `status_distribution_modes`, `status_white_list`, `status_black_list`).

| Yerel mod | Ad | `status_setting` | Wire `M7H` (app-state) |
|-----------|----|------------------|------------------------|
| 0 | My contacts | `contacts` | `CONTACTS` 2 |
| 1 | Only share with | `allowlist` | `ALLOW_LIST` 0 |
| 2 | My contacts except | `denylist` | `DENY_LIST` 1 |
| 3 | `C182877r0.A01()` ayarsız fallback'i; sync mutation tarafından reddedilir (`StatusPrivacySyncMutation invalid status setting`) | | |
| 4 | özel hedef kitle / yakın arkadaşlar | `customlist` / `closefriends` (inferred) | `CUSTOM_LIST` 4 (`CLOSE_FRIENDS` 3 enum'da var, üretilmez) |

Yerelden wire'a eşleme (found, `C48386LBh.A04`): 1 → 0, 2 → 1, 4 → 4, aksi halde 2. 0..2 modlarının adları gönderim job'ı tarafından da `contacts` / `allowlist` / `denylist` olarak loglanır.

Sunucu gizlilik listeleri `privacy` IQ'sunu, kategori `status` ile kullanır (kategori adı `AboutStatusPrivacyActivity` içinden):

```xml
<iq to="s.whatsapp.net" xmlns="privacy" type="get" id="…">
  <privacy addressing_mode="lid"><list name="status" value="contact_allowlist|contact_blacklist" dhash="…"/></privacy>
</iq>
<iq xmlns="privacy" type="set"><privacy><category name="status" value="contacts|contact_blacklist|contact_allowlist"/></privacy></iq>
```

(`AbstractC230749y7.A02`, `C228009tS`, `C18260lS.A0P`; get flag **23463**'e göre MEX / SMAX / shadow'dur, set **23639** ile MEX üzerinden, aksi halde SMAX.)

### 6.3 Özel hedef kitleler ve yakın arkadaşlar (found)

UI string'leri: `New: Close friends`, `People you include see a purple ring on your status`, `Create audience`, `Choose name & emoji`.

| Öğe | Değer |
|-----|-------|
| Tablo `status_privacy_custom_list` | `row_id` (PK), `list_id` (unique), `name`, `emoji`, `is_selected` (varsayılan 0), `member_jids`, `source_group_jids`, `allow_list_selected`; hem mesaj store'unda hem status store'unda tutulur (`*_MSGSTORE_DB`, `*_STATUS_DB`) |
| App-state | `status_privacy` (ordinal 38, `regular_high`, alan **44**); `StatusPrivacyAction`: `mode` **1**, `user_jid` **2**, `shareToFB` **3**, `shareToIG` **4**, `custom_lists` **5**, `modes` **6**; `StatusCustomList`: `list_id` **1**, `name` **2**, `emoji` **3**, `is_selected` **4**, `user_jid` **5** |
| Paylaşım başına kayıt | `status_message_info`: `status_distribution_mode`, `selected_audience_list`, `audience_type`, `status_audience_custom_list_name`, `_emoji` |
| Doğrulama | `StatusParticipantUserManager/validateAudience` (`wa_contacts` üzerinde bir `HAS_STATUS_AUDIENCE` kontrolü içerir), composer'larda `StatusEmptyAudienceGuard` |

İlgili: `userStatusMute` (ordinal 23, alan 29, `muted`). Aynı anda birden fazla mod flag **28731**, özel liste store'u **27031** gerektirir (ikisi de varsayılan false; status-config yardımcıları `A0F` / `A0I` de bunu kapılar, çözülmemiş).

### 6.4 Manuel sender-key bucket'ları (found)

| Öğe | Ayrıntı |
|-----|---------|
| Tablo `manual_user_group_bucket` | `row_id`, `user_jid_row_id`, `multi_participant_jid_row_id`, `status_audience`, `bucket`; user + group üzerinde unique index |
| Hedef kitle adları / bucket önekleri | `contacts` → `c`, `close_friends` → `f`, `allow_list` → `a`, `close_friends:<id>` → türetilmiş önek; diğer adlar `Unknown manual SKB audience name` fırlatır |
| Store / planlama | `ManualBucketStore/assignUsersToBuckets`, `deleteRowsForBuckets`, `getHoldersByBucketForGroup`; `ManualBucketingUtils/planSend`, `trimToEncBudget`; `SenderKeyBucketingRollback/cleanupBucketedState` |
| Flag'ler | **28184** + rollout sınırı **34545** (0 = hepsi) status için manuel bucketing'i etkinleştirir (`C23340ub.A01`) |

### 6.5 Yanıt, tepki, mention, notify (found)

| Etkileşim | Mekanizma |
|-----------|-----------|
| Yanıt | status'u alıntılayan normal 1:1 mesaj (`status_reply`: `status_row_id`, `ref_id`, `reply_timestamp`); soru yanıtları için `Message.statusQuotedMessage` (alan **109**) |
| Tepki / eklenti | job tipi `STATUS_ADD_ON`; `status_add_on` (`status_row_id`, `type`, `uuid`, `sender_user_jid`, `state`, `sender_timestamp`, `is_revoked`, `content_proto`, `secret`); paylaşım başına gate'ler `cannot_receive_reactions`, `can_receive_multi_reactions` |
| Mention | `status_message_info.is_mentioned`, `status_mentions`, `status_mention_source`; `Message.statusMentionMessage` (alan **87**) tek alanlı bir wrapper'dır (`message` **1**), `viewOnceMessage` gibi açılır (`C35228FOg`); ek semantik inferred |
| Notify | `Message.statusNotificationMessage` (alan **98**): `responseMessageKey` **1**, `originalMessageKey` **2**, `type` **3** (1 seninkini ekle, 2 yeniden paylaşım, 3 soru-cevap yeniden paylaşımı, 4 grup status yanıtı); `status_notify` içinde saklanır |
| İlgili alanlar | `groupStatusMentionMessage` **92**, `groupStatusMessage` **96**, `groupStatusMessageV2` **103**, `statusQuestionAnswerMessage` **105**, `statusStickerInteractionMessage` **110** |

### 6.6 Status depolama (found)

| Tablo | Anahtar sütunlar |
|-------|------------------|
| `status` (status store) | `uuid`, `sender_user_jid`, `status_info_row_id`, `type`, `timestamp`, `server_receipt_timestamp`, `state`, `secret`, `content_proto`, `origin`, `flags`, `audience_type`, `stanza_xml`, `batch_state` |
| `status` (mesaj store'u, eski özet), `status_info` | `jid_row_id` / `chat_jid`, `unseen_count` / `unread_count`, `total_count`, `unread_count_close_friends` |
| `status_message_info` | `message_row_id`, `status_distribution_mode` (ayarsızken 3), mention / tepki / yeniden paylaşım gate'leri, `is_group_status`, `ranking_version`, hedef kitle sütunları (6.3) |
| `status_send_part`, `status_receipt_device`, `manual_user_group_bucket` | gönderim durumu (6.1, 6.4) |

`status` adlı iki tablonun sütunları ayrıktır ve farklı veritabanlarında yaşar (`MSGSTORE_DB` / `STATUS_DB` etiketlerinden inferred). Diğer tablolar (`status_media_link`, `status_seen_receipt`, `status_ranking*`, `status_interactions*`) yalnızca adıyla listelenir.

---

## 7. Feature flag'ler

Id'ler çağrı noktalarında okunduğu gibidir; varsayılanlar derlenmiş varsayılan tablolardandır.

| ID | Varsayılan | Kontrol ettiği |
|----|------------|----------------|
| **13537** | false | tüketici broadcast capping'i: liste ana sayfası, kota fetch / azaltma, `client_capping_ready` değeri |
| **16585** | true | `messages_left == 0` iken liste gönderimlerini engelle |
| **16656** | false | liste stanza'larına `<cap client_capping_ready/>` ekler |
| **13818** | 1440 | kota yenileme aralığı (dakika) |
| **15515** | true | capping UI yardımcısı (`C33z.A08`, 13537 ile) |
| **19790** | false | true iken clone-on-insert alıntılanmış mesaj eşlemesini atlar |
| **26867** | true | status-4 gönderilmiş mesajlar için clone-on-insert dalı (anlamı çözülmemiş) |
| **30111** | true | bir kayıt katılımcıları temizleyecekse saklanan liste katılımcılarını koru |
| **16731** | false | `2:` yerine `phash` varyantı `3:` |
| **28183** / **28184** | false / false | `primcomp` bucketing ana flag'i / manuel status bucketing |
| **28185** / **28199** / **34545** | 512 / 2 / 0 | bucketing katılımcı eşiği / ikinci int (çözülmemiş) / rollout sınırı |
| **28731** / **27031** | false / false | çoklu status modları / özel liste store'u |
| **29113** | false | status için stanza-too-large işleme |
| **23463** / **23639** / **23874** | 0 / false / false | privacy get protokolü (1 MEX, 2 shadow, aksi halde SMAX) / MEX ile privacy set / privacy liste fetch yolu |
| **14837** | false | GAP enforcement |
| **20278** (string) | `{"max_messages": 10000, "farthest_time_days": 30}` | Business broadcast limiti varsayılanı, tüketici okuyucusu yok |

---

## 8. Baileys (`baron-baileys-v2`, kaynağına karşı kontrol edildi)

| Alan | Uygulama | 2.26.41.6'ya karşı hüküm |
|------|----------|--------------------------|
| Status gönderimi | `messages-send.js`: `isStatus`, katılımcı listesine eklenen `statusJidList`, `<meta status_setting session_scope="status">` | 6.1 / 6.2 ile uyuşur; `statusPrivacy` doğrulanmaz (geçerli: `allowlist`, `closefriends`, `contacts`, `customlist`, `denylist`) |
| Hedef kitle ölçeği | açık `statusJidList`, bucket yok, `bucketing` özniteliği yok | büyük hedef kitleler stanza limitlerine çarpar (6.1) |
| Liste silme | `deleteBroadcastList`: `w:b` set, `<delete><list id/></delete>` | 3.3 ile uyuşur |
| Kota | `fetchBroadcastListQuota`: `xmlns="w:biz"` ve çocuk `<broadcast_list_quota/>` | istek uyuşmaz (`w:b`, `smax_id=143`, çocuk yok); yanıt ayrıştırma uyuşur |
| Listeleri alma / app-state / liste gönderimi | uygulanmamış / `businessBroadcastListAction` `settings.update` olarak yayılır / `isJidBroadcast` yalnızca çözme için | aşağıya bakın |

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| klasik liste gönderimi düşürüldü veya reddedildi | listeler birincil cihaz durumudur: companion'lar özelliği gizler, `participants` taşıyan kendi hesap liste kopyalarını düşürür (415), create IQ yoktur | companion'dan liste JID'lerini hedefleme; alıcı başına 1:1 mesaj gönder veya `statusJidList` ile `status@broadcast` kullan |
| alıcılar çözümlenemiyor | companion'larda listeler için üye sorgusu yoktur; katılımcılar LID adreslidir ve eşlemeye göre filtrelenir | önce LID'leri usync ile çöz |
| kota isteği hataları | yanlış namespace | `xmlns="w:b"`, `smax_id` 143, `type="get"`, `to="s.whatsapp.net"` |

Ayrı 1:1 gönderimler transport açısından uyumludur ancak klasik liste değildir (liste sohbeti, ortak id veya kota yok).

---

## 9. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| `missing_pn_lid_mapping_for_broadcast`, `lid-broadcast-filtered-participants` | alıcı PN'sinin LID eşlemesi yok | eklemeden veya göndermeden önce LID'leri al (usync) |
| 415 `received peer broadcast message on companion-mode` | companion'da `participants` taşıyan liste kopyası | beklenen davranış, companion'lar liste gönderimlerini işlemez |
| gönderim engellendi, limit sheet'i | 13537 ve 16585 ile `messages_left == 0` | `reset_ts_s` bekle, gönderilmemiş liste mesajlarını sil |
| ban kodu 106 | bir broadcast listesine çok fazla mesaj | `expiry_in_seconds` bekle |
| `broadcast_would_be_cleared` | boş kümeyle katılımcı kaydı | flag 30111 katılımcıları korur |
| `EMPTY_FANOUT` | hedef kitle sıfır cihaza çözüldü | hedef kitleyi düzelt, `StatusEmptyAudienceGuard` daha önce engellemeli |
| `stanza_too_large`, `payload_too_large` | çok fazla cihaz veya payload | parçalar / bucket'lar (6.1, 6.4), flag 29113 |

---

## 10. Temel ayrımlar

| Karıştırılmaması gerekenler | Fark |
|-----------------------------|------|
| Liste (type 3) vs `status@broadcast` (type 5) | liste: saklanan alıcılar, alıcı başına clone'lar, aylık kota; status: paylaşım başına hedef kitle, clone yok, kendi tabloları |
| Liste vs grup | aynı katılımcı store'u ve sender-key yolu; liste yalnızca birincil cihazdadır, alıcılar üye değildir ve 1:1 sohbetler görür |
| Sunucu `w:b` listeleri vs app-state action 69 | `w:b` kayıttan sonra listeleri geri yükler; action 69 senkronizasyon için yazılır ve tüketici apply handler'ı yoktur |
| Kota (`w:b` smax 143, ≤ 300) vs config 20278 (10,000 / 30 gün) | kota sunucu tarafından sağlanır ve UI tarafından uygulanır; 20278'in tüketici okuyucusu yoktur |
| Kota vs ban kodu 106 vs GAP | UI ile yumuşak limit / sunucu tarafından verilen geçici ban / alım tarafı inbox kuralları |
| `privacy` IQ vs özel hedef kitleler | IQ üç sunucu modunu tutar; özel listeler ve yakın arkadaşlar yerel artı app-state action 44'tür |

---

## 11. Uçtan uca akış

```
[User]  New broadcast → select ≤ 256 contacts
     ▼
[Client]  C0YJ.A0E → <seconds>@broadcast ; A0K.A04 → LID filter, group_participant_user rows
     │     send → message.broadcast = 1 ; C231399zG clones into each recipient chat (same key id)
     │     quota gate: 13537 + 16585, messages_left > 0
     ▼
[SendE2EMessageJob]  F6P: skmsg + SKDM per device (pkmsg/msg) + ephemeral blobs ; DSM to own devices (phash)
     ▼
<message to="<id>@broadcast" phash id><participants>…</participants><enc type="skmsg"/><cap/></message>
     ▼
[WA Server]  (not observed) fan-out, ack
     ▼
ack → C22500tF updates list row + all clones ; receipts → splitStatusUpdateReceipts ; quota decremented on add

[User]  status: choose audience (contacts / allow / deny / close friends / custom)
     ▼
[Client]  validateAudience → StatusEmptyAudienceGuard ; users → LID → devices ; buckets c / f / a when 28184 on
     ▼
[SendE2eStatusJob]  type STATUS ; status_send_part rows ; sender key per bucket
     ▼
<message to="status@broadcast" phash bucketing><participants>…</participants><enc type="skmsg" bucket/><meta status_setting session_scope/></message>
     ▼
[WA Server]  (not observed) ack within 300 s ; viewers reply / react
     ▼
status_add_on / status_notify / status_reply rows ; status_receipt_device bookkeeping
```

---

## 12. Bilinmeyenler

| Öğe | Durum |
|-----|-------|
| Sunucunun bir listeyi nasıl kaydettiği (yalnızca get / delete / quota IQ'ları vardır) | gönderim anında kayıt inferred |
| Alıcıların göndereni kayıtlı tutması gerektiği sunucu kuralı; liste boyutu ve kota değerleri | sunucu tarafı (yalnızca UI metni ve aralık kontrolleri) |
| App-state action 69'un tüketici apply davranışı | handler bulunamadı |
| Alıcıların bir liste mesajı için ne aldığı; liste satırının özet receipt kuralı | göndericiden görünmez |
| Kota yenileme kombinasyonu, muaf mesaj tipi kümesi | decompile bozuk / izlenmedi |
| Yerel status modu 3, `threebuckets`, flag'ler 28199, 26867, 15515, status-config `A0F` / `A0I` | çözülmemiş |
| `location@broadcast` kullanımı; "GAP" açılımı | izlenmedi / APK'da yok |
| Trafik | hiçbir şey yakalanmadı |
