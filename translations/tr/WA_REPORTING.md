<!-- src-sha1: 09dd00f496c4831ec33afbfd78f4db63a78bf014 -->
# WhatsApp Raporlama — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Kullanıcı/kişi, grup, kanal, status, çağrı ve mesaj raporlama — SMAX `spam` stanza'ları, `spam_list`, rapor tipleri, `spam_flow` giriş noktaları, reporting token'ları, içerik yüklemesi, rapor/engelleme UI'si, yöneticiye-bildirme, engelleme stanza'sı ve neden listeleri, sunucu hataları, istemci-tarafı istismar sinyalleri, Baileys

---

## 1. Raporlama teknik olarak nedir

Bir rapor, `s.whatsapp.net`'e, `spam` namespace'inde bir IQ `set`'tir. Bir `spam_list` node'u (raporlanan varlık, raporlanan mesajlar, giriş noktası, business-discovery context'i) taşır. İstemci, raporlanan mesajları düz-metin protobuf olarak yeniden serileştirir ve onları bir reporting token'ı ve onu doğrulayan key ile birlikte yükler. Engelleme ayrı bir stanza'dır (`blocklist`). Yöneticiye-bildirme üçüncü, ilgisiz bir stanza'dır (`w:g2`).

Tüm ifadeler decompile edilmiş APK'nın statik analizidir. Kademe: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi. Burada hiçbir şey wire üzerinde yakalanmadı.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| IQ builder'ı (çok-amaçlı, `$t` şekli seçer) | `C9EN` | her rapor IQ'sunu (tipler 0, 18-23) ve birçok ilgisiz IQ'yu inşa eder |
| Neden/giriş-noktası node'u | `C9E2` | `spam_flow`, `wi_trace_id`, `is_known_chat`, ... ile `spam_list` (`xmlns="spam"`) |
| Grup ayarı çocuğu | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| İçerik wrapper'ı | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Çeşitli node'lar | `C31084Dfc`, `C31085Dfd` | flag'ler (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Serileştirici ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, token montajı |
| SMAX yöneticisi | `SpamRPCManager` | `A01`-`A06`, rapor türü başına bir (paket adı obfuscated değil) |
| Repo | `SpamReportRepo` | JID sınıfına göre yönlendirir, yerel yan etkiler |
| RPC wrapper'ları | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | paket `com.whatsapp.reportinfra.rpc` |
| Origin whitelist'i | `C9ZJ` | giriş noktasını doğrular (78 değer) |
| UI | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | rapor dialog'u, opsiyonel engelle/ayrıl |
| Engelleme yürütücüsü | `C227489sZ` → `C34631Yx` | `blocklist` IQ'su |
| Yöneticiye-bildirme | `RtaXmppClient` | `w:g2` rapor kuyruğu |
| Token deposu | `C23070uA` | tablolar `reporting_info`, `reporting_info_content` |

İsimler build-başına değişir; yukarıdaki her obfuscated ad, stabil string'lerden (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`) 2.26.41.6'da çözülmüştür.

**2.26.45.10'da yeniden doğrulandı** (found): `com.whatsapp.reportinfra.rpc.*` (altı RPC wrapper'ı) ve
`com.whatsapp.reportinfra.repo.SpamReportRepo` değişmemiştir — aynı altı sınıf, aynı JID-sınıfı yönlendirmesi, aynı
`SpamRPCManager.A01`-`A06` çağrıları, aynı hata/log string'leri (sadece-smali kontrol, bu geçişte jadx yok). Bu yeni bir
rapor yüzeyi değildir; yukarıda belgelenen aynı pakettir, sadece yeniden doğrulanmıştır. WAM perf-metrik hook'u
(`wam_spam_report_perf`, bölüm 11.3), artık `SpamReportRepo`'ya bir katman daha yakın, adlandırılmış bir
`ReportSpamPerfMetric$Companion` yardımcısı üzerinden görünür şekilde yönlendirilir — aynı telemetri, yeni alan yok.

---

## 2. Rapor tipleri

### 2.1 Yönlendirme (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)`, JID sınıfına göre dallanır:

| Raporlanan JID | RPC sınıfı | `SpamRPCManager` | Builder `$t` | Yanıt sınıfı | Log etiketi |
|--------------|-----------|------------------|--------------|----------------|-----------|
| bir newsletter JID'inde seçilen status nesnesi (`AbstractC31014DeU` null-olmayan) | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| kullanıcı (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| grup | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| başka herhangi bir JID'de seçilen status nesnesi, veya bir mesaj listeli status JID'i | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| newsletter/kanal | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| etkinlik id'si (string) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| başka herhangi bir şey | yok | yok | yok | yok | `SpamReportRepo: unrecognized jid` fırlatılır, başarısızlık olarak döndürülür |
| bot sohbeti | yok (bkz 3.3) | yok | yok | yok | `C214999If` |

Rapor olmayan diğer `C9EN` şekilleri: `$t=0` yöneticilere bildirme ve `$t=1` grup ayarı toggle'ı (bölüm 9), `$t=2` alt-grup önerileri, `$t=24/25/26` `status` node'ları. Event RPC'si coroutine lambda'larından (`AYs`, `Aaa`) çağrılır; kaynak UI unknown'dır (event giriş noktaları `event_home_report` / `event_info_report` mevcuttur, bu yüzden event raporları inferred'dir).

### 2.2 Çağrı raporları kullanıcı raporlarıdır (found)

`SpamReportRepo.triggerReportCallNonSuspend` (`call_spam_dialog_report` origin'i), raporlanan `jid` olmadan, mesaj olmadan ve bir çağrı öğesiyle `IndividualSpamReportRpc.A00`'ı çağırır. Çağrı öğesi (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` şunları içerir: `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` ve codec fatal hataları. Flag **36386**, `to`'daki kendi-JID formunu seçer (`CUC()` vs `Ask()`, inferred LID vs PN). `shouldIncludeCallLogsInReport`'lu bir UI kullanıcı raporu, 5'e kadar çağrı-log öğesi ekler (`C16430i1.A0B(jid, 5)`).

---

## 3. İstemci akışı

### 3.1 Dialog

`ReportSpamDialogFragment` (alt dialog). Fragment argümanları (found): `flow` (giriş-noktası string'i, `spam_flow` olur), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1`, dialog durumunu yükler.

Onayda, `reportAsSpam$1` çalışır:

1. Bot sohbeti: RPC'yi atla (3.3). Aksi halde seçilen mesajla bir-elemanlı bir listede (veya hiçbiriyle) `SpamReportRepo.A02(...)`.
2. Başarı opsiyonel bir rapor id'si taşır; hata toast `str3bf8`'i gösterir (veya `C227489sZ.A00`, log `spamreportmanager/spam/report/no-network-cannot-report`). WAM `wam_spam_report_perf` doldurulur (11.3).
3. Opsiyonel ekstra eylem `triggerExtraAction$2` (3.2), `H2U`'dan tamamlama dialog'u (10.2), yerel yazımlar (3.3).

### 3.2 Sadece rapor vs rapor + ekstra eylem (found)

Checkbox, analytics için kullanılan `report` (işaretsiz) veya `report_block` (işaretli) string'ine eşlenir (`asd.BaC` vs `BaD`) ve rapor-sonrası toast'a. Ekstra eylem hedefe göre farklıdır:

| Hedef | İşaretliyken ekstra eylem |
|--------|--------------------------|
| kullanıcı | `C227489sZ.A01` → `C34631Yx` `blocklist` IQ'su üzerinden engelleme (bölüm 8), engelleme nedeni `null`, giriş noktası = `flow`, `deleteChat` = argüman `shouldDeleteChatOnBlock` |
| grup | grup-ayrılma görevi (`C98C` / `C9CI`, grup JID'iyle çalıştırılır; ayrılma semantiği inferred) |
| kanal | raporlanan kanalı yerel olarak gizle (`NewsletterReportCompletionListener`, flag **25218**), sonra newsletter çıkış/takip-etmeme akışı |

Rapor IQ'su önce gönderilir; engelleme/ayrılma, sonucundan bağımsız olarak, RPC döndükten sonra çalışır (kontrol akışından inferred, `triggerExtraAction$2`'den önce başarı kontrolü yok).

### 3.3 Bot sohbetleri ve yerel etkiler (found)

Bot sohbetleri `SpamReportRepo`'yu atlar: istemci `BotMessageHelper/reportUgc`'yi (`E1J.GENERIC`, `C27847C7h`) çağırır ve onu başarı olarak ele alır (`C214999If`); wire formu unknown'dır. Diğer sohbetler için `C24120Ab1` durumu 4 şunları yapar:

| Adım | Etki |
|------|------|
| hiçbir mesaj seçilmedi | sohbetin en son **5** mesajını (`C14680f4.A01(..., 5, true)`; sistem-tipi satırlar hariç, bu varyantta `from_me` filtresi yok) raporlanan içerik olarak toplar |
| kullanıcı sohbeti | yerel log `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; flag **20085**, `H0J.A00(jid, ...)`'i gater (amaç unknown) |
| RPC sonrası | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, görünür akışta RPC sonucunun kontrolü yok |

---

## 4. Stanza zarfı ve namespace

### 4.1 Neden node'u IQ'ya birleştirilir (found)

RPC'ler iki `spam_list` sibling'i yaymaz. Ana `spam_list` (jid, mesajlar) ve neden node'u `C9E2` (bir `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>` parçası), attribute'ları ve aynı-adlı çocukları birleştiren `C10340Uk.A04` ile birleştirilir (çakışan attribute değerleri veya çocuk sayıları birleştirmeyi iptal eder). Sonuç:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Kanıt: 18-23 için `C9EN` constructor'ları `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`'u çağırır; `C9E2` durumu 5, `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`'u inşa eder; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. IQ `id`'si `MessageClientSmaxWrapper.A01()`'den gelir (`n<hex counter>`, `C10140Tq.A0H`). Gönderme timeout'u 32000 ms (`A0F(node, id, cont, type, 32000, ...)`); bir null yanıt (timeout/teslimat başarısızlığı), `C216549Uq` olur.

Tipler 0 ve 1, `xmlns="w:g2"` ve `to=<group>`'u literal olarak ayarlar; tipler 18-23, `<iq type="set">`'i inşa eder ve `to` ve `xmlns` için birleştirmeye güvenir. Gönderene geçirilen tip id'si **98**'dir (grup, newsletter, event) ve **385** (yöneticiye-bildirme).

### 4.2 `spam_list`'e birleştirilen opsiyonel sibling'ler

| Node/attr | Kaynak | Gate | Kademe |
|-----------|--------|------|------|
| `spam_flow` | `C9ZJ` tarafından normalize edilmiş `flow` argümanı | her zaman | found |
| `wi_trace_id` (tam 24 karakter) | `reportAsSpam$1`'in `$wiTraceId`'si | opsiyonel | found; değer kökeni unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | flag **22256**; kullanıcı: adres-defteri kontrolü, grup: grup üyeliği kontrolü | found |
| `biz_opt_out` çocuğu | `C33446EhE.A07` | business discovery kaydı mevcut | found (bkz 8.3) |

---

## 5. Tip-başına stanza'lar

Bir `<message>` öğesinin `from`/`to`'su: kullanıcı yolu için anonim node `C9E4`, mesaj çıkışsa (`key.fromMe`) `to=<jid>`'i, aksi halde `from=<jid>`'i ayarlar. Sayımlar builder gate'leridir (`AbstractC10350Ul.A07`).

### 5.1 Kullanıcı (tip 20)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<userJid>" spam_flow="chat" wi_trace_id="...">   <!-- jid: UserJid or interop jid (C99O) -->
    <message from|to="<userJid>" t id deleted_reason>              <!-- 0..210 items -->
      <raw v="2" local_message_type="<int>" mediatype="<enum>"><proto bytes></raw>
      <content_validation type="e2e_proto_message|mms_retry|plaintext_v3">
        <reporting_token v="<n>"><tag, min 6 bytes></reporting_token>
        <reporting_token_key><key, 16-32 bytes></reporting_token_key>
      </content_validation>
    </message>
    <call .../>                                                    <!-- 0..5 items, section 2.2 -->
    <extension_screen extension_id session_id t name entry_point>  <!-- 0..5, business Flows context (A0B), data child -->
    <biz_opt_out business_discovery_timestamp business_discovery_id business_discovery_entry_point/>
  </spam_list>
</iq>
```

Builder, 210 (mesajlar), 5 (çağrı öğeleri), 5 (mesajsız business-flow öğeleri, `C33446EhE.A0B`: business-başına deponun (`messageless_flow_ids_per_business_<jid>`) son 5 girdisi, node `extension_screen`) üst sınırlarıyla üç öğe listesi alır. `jid`, sadece `UserJid` ve `C99O`'ya karşı doğrulanır; bu yolda `subject` yoktur.

### 5.2 Grup (tip 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source`, raporlayan değil, **raporlayanı gruba ekleyen kullanıcıdır**. Yerel sistem mesajından ("me joined") SQL `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`) ile okunur. Opsiyonel. (found)
- `subject`, grubun kişi kaydından (`C06290Dn.A07().A00.A0b`; alan anlamı inferred) görünen adıdır, topluluk ana grupları için veya kayıt mevcut olmadığında boş string `""` olur (`Voip.REJECT_REASON_DECLINED`, `""`'dir). Bir neden değildir. Uzunluk gate'i 0..65536. (found)
- Constructor'da dördüncü bir liste, boş-olmayansa fırlatır (`getNode`); RPC boş bir liste geçirir.

### 5.3 Newsletter (tip 21) ve status gönderisi (tip 22)

```xml
<spam_list jid="<newsletterJid>" subject="<channel name or ''>" spam_flow="newsletter_info_report">
  <message from="<newsletterJid>">...</message>        <!-- 0..65 -->
</spam_list>
<spam_list jid="<statusPosterJid>" spam_flow="status_post_report">
  <message from="<posterJid>">...</message>           <!-- 1..2 items, only the first selected status is passed -->
  <biz_opt_out .../>                                   <!-- optional -->
</spam_list>
```

Newsletter `subject` = kanal adı (`C2130898y.A0j`), bilinmiyorsa `""` (found). Status raporları kendi token tablolarını kullanır: `status_reporting_info` / `status_reporting_content`.

### 5.4 Kanal status V2 (tip 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

Status, `server_id` + zaman damgasıyla tanımlanır, yüklenen içerik yok. `status` çocuğu içeriği (`InterfaceC35700FdB`) çözülmedi.

### 5.5 Etkinlik (tip 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`, `wi_trace_id` yok (tek-argümanlı `C9E2(String)` yolu). Yöneticilere mesaj (tip 0): bölüm 9.1.

---

## 6. Raporlanan içerik ve token'lar

### 6.1 Yüklenen şey (found)

`C33446EhE.A0A(fmsg, entryPoint)`, raporlanan mesaj başına bir öğe inşa eder:

| Parça | Detay |
|------|------|
| `<message>` attr'ları | `t` (mesaj zaman damgası, 0..2^53), `id` (stanza id'si), `from`/`to` jid, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | yeniden serileştirilmiş `Message` protobuf'u (`MessageContextInfo` `C30624DTs` ile `C30628DTw`); `local_message_type` = dahili mesaj tipi int'i |
| `<content_validation>` | token + key (6.2) |
| meta flag'leri | `<edit v="1">` (düzenlendi), `<multicast/>` (broadcast flag'i 64), `<url_number/>` (flag 4), `<url_text/>` (flag 2), template id'si, `hsm` tid, `iab reported_link`, `original_sender` / `group_history_sender`, `futureproof`/`request`/`send` ödeme varyantları (`pay`), `reported_push_name` |
| `<reporting>` çocuğu | flag **5718**: mesajın `reporting_info` satırlarından inşa edilir (`C23070uA.A03`), 1000 girdiye kadar (`C31085Dfd` durumu 28); girdi-başına schema tam olarak okunmadı |
| alternatif taşıyıcılar | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 değer, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

OTP template mesajları: buton başlıklarındaki `<code>` yer tutucusu, serileştirmeden önce gerçek kodla değiştirilir (`AbstractC32303E8u.A00`). View-once: mesaj view-once olduğunda ve zaten açılmış/süresi dolmuşken ve origin `media_viewer` / `view_once_viewer` değilken, `A06` doğrudur ve serileştirme bloğu atlanır. Öğenin bu durumda boş veya mevcut olmayan bir `raw` taşıyıp taşımadığı inferred'dir (deklarasyon decompile'de ilklendirilmemiş).

Medya dosyaları bu stanza tarafından yeniden yüklenmez; serileştirilmiş mesaj medya referanslarını taşır (inferred; hiçbir yükleme çağrısı bulunamadı). Stanza, düz-metin proto'yu ve key'i birlikte tutar, bu yüzden sunucu içeriği okuyabilir: node'lar **found**, okunabilirlik **inferred**.

### 6.2 Reporting token'ı ve key'i (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

`C33446EhE.A03`'te saklanmış satırdan (`C34539Ez0`) inşa edilir: token byte'ları (`A05`), versiyon (`A02`), stanza id'si (`A03`), key (`A07`). Key eksikse yeniden türetilir: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → native `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (kullanım senaryosu id'si **5**; kullanıcı-olmayan sohbetler `JniBridge` varyantlarından geçer). Hem key hem 6-byte'lık token eksik/sıfırsa, istemci `ReportingToken/MissingFkAtReport`'u loglar ve tamamen-sıfır 32-byte'lık bir key kullanır. Eksik bir token `null` döndürür (`ReportingToken is null`, öğenin `content_validation`'ı yoktur).

### 6.3 Token yaşam döngüsü (belirtilmedikçe found)

| Aşama | Detay |
|-------|------|
| Çıkış mesajı | builder `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Token = `HMAC-SHA256(key, canonicalContent)`'in ilk 16 byte'ı (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = versiyona-bağlı alan filtrelemesi olan mesaj proto'su (`A07`, alan 35'in seçili alt-alanlarını çıkarır; okuma inferred). Builder'ın çağıranları izlenmedi |
| Grup geçmişi paylaşımı | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): tip 117 mesajları için girdi-başına bir çocuklu `<reporting>` (attr `id`, çocuk `<reporting_token v>`) |
| Gelen mesaj | `C34764F6h` / `C1S0` tarafından ayrıştırılan stanza çocuğu `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>`, flag **5718**; hem tag hem token opsiyonel, tag gerekli |
| Depolama | tablolar `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) ve `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`); `message_conditional_reveal.reporting_token_info` (blob); `group_history_share_reporting_info`; `status_reporting_info` |
| Geçmiş | `WebMessageInfo.reportingTokenInfo` alanı **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; flag **6578** |
| Temizleme | `receive_timestamp`, bir kesim noktasından (`FP7` durumu 6) daha eskiyken `reporting_info*` satırları silinir; kesim değeri çözülmedi |
| Alternatif doğrulama node'u | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

`reporting_tag`'ı kimin yayınladığı ve sunucunun token'ı nasıl doğruladığı: sunucu tarafı, unknown. Eşleştirme (stanza'daki tag, rapordaki token+key) inferred'dir.

---

## 7. `spam_flow` giriş noktaları

97 değer (found, `C9E2` durumu 5, sıra = dizi sırası). `flow` argümanı, bunların **78**'ini kabul eden ve aksi halde `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` fırlatan `C9ZJ.A00`'dan geçer. Altı RPC wrapper'ının tümü onu çağırır ve `SpamReportRepo.A02`, exception'ı yakalar ve bir başarısızlık döndürür (istemci-tarafı hata, gönderilen stanza yok). 78, 97'nin sıkı bir alt-kümesidir. Reddedilen 19 değer: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. Bunlar muhtemelen sadece-engelleme veya diğer-RPC origin'leridir (inferred). `channel_status_report`, enum'da mevcuttur ama `C9ZJ` tarafından reddedilir; channel-status çağıranının hangi flow'u geçirdiği unknown'dır.

| Yüzey | Değerler |
|---------|--------|
| Sohbet / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Spam banner'ları | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| FMX güvenlik kartları | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| Cihaz-üzerinde dolandırıcılık uyarıları | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Grup | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Çağrılar | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Kanallar / status / etkinlikler | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Business | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

FMX kartları için `*_suspicious` vs düz seçimi, `A0D(userJid)`'den (kişi bilinen mi değil mi) `C230769yA.A05`'te yapılır; bu yüklem bir adres-defteri kontrolü olarak inferred'dir. `server_flagged` varyantları kart tipine göre seçilir; sunucu flag'inin nereden geldiği unknown'dır.

`wi_trace_id`: 24-karakter opsiyonel attribute, çağırandan geçirilir; üreteci bulunamadı (unknown). Ayrıca WAM `wam_spam_report_perf`'in (11.3) bir alanıdır.

---

## 8. Engelleme, nedenler ve business context'i

### 8.1 Engelleme IQ'su (found, `C34631Yx.A0M` bölgesi)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` ve `entry_point`, sadece `action="block"` için yayılır. `jid`, bir ayar kontrolü (`zA02` dalı; tam kural tam olarak okunmadı) tarafından PN ve LID formları arasında seçilir; bir engellemede ekstra tanımlayıcı `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`'dan biridir. Timeout 20000 ms. `odml_scam_alert_*` ile başlayan giriş noktaları `1_1_spam_banner_block`'a yeniden yazılır (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). PSA sohbetleri farklı bir IQ kullanır (`xmlns="w:comms:chat"`, `<blocking action>`). Fetch: `type="get"`, opsiyonel `<item dhash>`.

### 8.2 Engelleme nedenleri (found)

`AbstractC227579sl.A00`'da hardcoded string → yerel int: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, diğer = 0. `RunnableC40792Hpk`, aynı string'leri bir ikinci kod kümesine eşler. Bu int'ler yerel log çağrılarını besler; sunucuya ulaşıp ulaşmadığı unknown'dır.

Business engelleme sheet'i (`C24126Ab7`): boş-olmayansa sunucu neden haritası, aksi halde `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; OTP-template sohbetleri: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Business discovery context'i (found)

`C33446EhE.A07`, raporlanan JID için business-discovery kaydını okur (depo `LA8`): zaman damgası, id, giriş noktası. Giriş noktası enum'u (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. Hem raporlara (`spam_list` altında `biz_opt_out`) hem engellemelere eklenir. Bunlar, istemcide bulunan tek bu-sohbet-nasıl-başladı sinyalleridir.

### 8.4 Rapor neden listeleri (found)

Sadece business reklamları seçilebilir bir listeye sahiptir. `ReportReasonListFragment`, boş başlar ve `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>`'den doldurulur (yanıt `name`, `v`, `country`'li `mobile_config` > `list`). Hardcoded fallback enum'u (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. Fallback kullanıldığında: sunucu listesi kullanılamaz olarak inferred. Sıradan kullanıcı/grup/mesaj raporları için bir neden seçici yoktur; wire'daki tek "neden" `spam_flow`'dur.

---

## 9. Grup yöneticilerine bildirme

### 9.1 Gönderme ve çekme (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

Hiçbir içerik, token veya `spam_flow` gönderilmez; sadece mesaj id'si. Hatalar sadece `Rta::<op>/onError: <code>` veya `/onDeliveryFailure: Network Failure`'ı loglar.

### 9.2 Üye-raporu toggle'ı (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (etkinleştir) veya `<not_allow_admin_reports/>` (devre dışı bırak), smax 384. Node'lar IQ'nun doğrudan çocuklarıdır, bir `group` node'una sarılmamıştır. Builder, bir IQ'da dört sibling ayar node'una kadar kabul eder.

---

## 10. Sunucu yanıtı ve tamamlama dialog'ları

### 10.1 Yanıt (found)

Başarı (`type=result`): attribute `id`'li (maks 20 karakter) çocuk `report` → `C213959Ch.A01` → rapor id'si olarak UI'ye döndürülür. Hatalar (`<error code text>`), yanıt sınıfı başına:

| Kod | Ad | Individual | Group | Newsletter | Status | Status V2 | Event |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 Tamamlama dialog'ları

`H2U`, rapor id'sinden ve gate'lerden karar verir, sonra `C5BD`, fragment'i inşa eder (`arg_report_id`, `arg_is_ad_report`):

| Gate | Dialog |
|------|------|
| flag **25818**, kullanıcı sohbeti, mesaj mevcut | `NciiCompletionDialogFragment` |
| flag **6145** | `DsaCompletionDialogFragment` (AB) |
| flag **14249** | `UkOsaCompletionDialogFragment` |
| flag'ler **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

NCII hariç hepsi null-olmayan bir rapor id'si gerektirir; id yoksa dialog yoktur.

---

## 11. İstemcideki istismar sinyalleri

### 11.1 İstemcinin içerik dışında gönderdiği şey (found)

`*_server_flagged_suspicious`'lı giriş noktaları, kartın yerel kişi kontrolünden başka bir sinyalle işaretlenmiş bir sohbet için gösterildiği anlamına gelir; istemcinin o flag'i nasıl öğrendiği unknown'dır. Raporlarda gönderilen: `is_known_chat`, `biz_opt_out` (business sohbetinin nasıl başladığı), çağrı öğeleri (süre, kimin sonlandırdığı, sonlandırma nedeni), business Flows `extension_screen` context'i, `source` (beni gruba kimin eklediği), `reported_push_name`, her mesajda iletme/yayın/URL flag'leri, düzenlendi flag'i, view-once durumu, giriş noktası, opsiyonel `wi_trace_id`.

### 11.2 Cihaz-üzerinde dolandırıcılık algılama (found, kapsamlı)

`com.whatsapp.integrityai`, ExecuTorch aracılığıyla cihaz üzerinde indirilmiş bir model kümesini (`scam_detection`) çalıştırır (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; özellikler `mostRecentSenderScore`, `isCountryMismatch`). Sonuçlar uyarı banner'larını/sheet'lerini ve yukarıdaki `odml_scam_alert_*` giriş noktalarını sürer. Yerel bir JSON tarama kaydı (`outcome`, `inputs`, `model_info`, `verification`), `integrity_warning_report_enabled` (`C57375Pog`) olduğunda bir `FileStash`'a yazılır. O kaydın yüklemesi bulunamadı (unknown). `spam` rapor stanza'sından bağımsızdır.

### 11.3 Telemetri (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. `reportAsSpam$1`'de hata-kodu eşlemesi: iptal -4, timeout/yanıt yok -1, diğer exception -3, protokol hatası = IQ hata kodu.

---

## 12. Baileys

`baron-baileys-v2` paketinde bir rapor API'si yoktur. Aşağıdaki şekiller bulunan node'lardan gelir ve test edilmemiştir.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

Kullanıcı/grup/kanal rapor şekilleri bölüm 5'i takip eder (bir birleşmiş `spam_list`, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Neden başarısız olur (hepsi inferred) | Neden | Düzeltme |
|--------------|-------|-----|
| hata 548 veya sessiz no-op | geçerli bir reporting token/key yok: Baileys, gelen mesajların `<reporting>` çocuğunu düşürür ve hiçbir zaman key'i türetmez | alımda `reporting_tag`/`reporting_token`'ı ayrıştır, mesaj-başına sakla, rapor zamanı `messageSecret`'ten (kullanım senaryosu 5) key'i türet |
| 400 | yanlış sınıfın `jid`'i (tip 20 için kullanıcı/interop olmalı), üst sınırların üzerinde öğe sayıları, yanlış tipte `spam_flow` | bölüm 7'deki `spam_flow` string'lerini kullan; 210 / 5 öğenin altında kal |
| reddedilen IQ | tek bir birleşmiş node yerine iki `spam_list` sibling'i (neden ikinci bir node olarak gönderildi) | tüm attribute'larla bir `spam_list` gönder |

Hem `wi_trace_id` hem `is_known_chat`, builder'da opsiyoneldir; sunucunun icat edilmiş token'larla raporları kabul edip etmediği unknown'dır.

---

## 13. Hata durumları

| Belirti | Neden | Kademe |
|---------|-------|------|
| toast `str3bf8`, hiçbir şey gönderilmedi | `C9ZJ`, `flow` değerini reddetti (`Invalid BlockSpamReportOrigin value`) | found |
| `unrecognized jid` başarısızlığı | sohbet JID'i kullanıcı/grup/status/newsletter'dan hiçbiri değil | found |
| rapor hiçbir toast olmadan "başarısız oluyor" | sunucu hatası 548: `C9ZI.A00`, bot yoluyla aynı hata-olmayan sonuç nesnesini döndürür | found |
| genel başarısızlık toast'ı | 400/403/429/500/501, veya timeout (32 s) → `C216549Uq` | found |
| rapor içeriği eksik | view-once açılmış/süresi dolmuş ve origin bir viewer değil; mesajın saklanmış bir token'ı yok | found / inferred |
| yerel durum raporlandı diyor, sunucu reddetti | `is_spam_reported`, görünür bir sonuç kontrolü olmadan RPC'den sonra yazıldı | found (akış), inferred (sonuç) |

---

## 14. Ayırt edilmesi gereken noktalar

| Karıştırılmaması gereken | Bununla |
|----------------|------|
| `spam_list@source` | raporlayan. Raporlayanı gruba ekleyen kullanıcıdır |
| `spam_list@subject` (grup, kanal) | bir neden. Grup/kanal adıdır |
| `spam_flow` | bir rapor nedeni. Raporu tetikleyen UI yüzeyidir (97 değer) |
| rapor (xmlns `spam`) | engelleme (xmlns `blocklist`), yöneticiye-bildirme (xmlns `w:g2`), pazarlama opt-out'u (xmlns `optoutlist`, `C31105Dfx`, daha fazla analiz edilmedi) |
| iki `spam_list` node'u | bir birleşmiş `spam_list` (attribute'lar ve çocuklar birleştirilmiş) |
| çağrı spam'i | event spam'i. Çağrı raporları, bir `call` öğeli tip 20'dir; tip 18 `event_id`'dir |
| `reporting_tag` (sunucu-yayınlı, alımda saklanır) | `reporting_token` (16-byte HMAC, çıkış mesajlarıyla gönderilir ve raporlarda yüklenir) ve `reporting_token_key` (türetilmiş, yüklenir) |
| yöneticiye-bildirme | WhatsApp'a bildirme. Yönetici raporu sadece `message_id` gönderir; içerik yok, token yok |
| `wi_trace_id` (istemci-gönderimli iz id'si) | rapor id'si, sunucunun `<report id>`'de döndürdüğü |
| `report_block` | bir wire değeri. Bir istemci analytics/toast string'idir; engelleme kendi IQ'sudur |
| `allow_admin_reports` toggle'ı (`$t=1`) | yöneticiye-bildirme mesajı (`$t=0`) |

---

## 15. Baştan sona akış

```
[User]                  [Client]                                        [WhatsApp server]
  │ Report / Block+Report    │                                               │
  ├────────────────────────▶│ ReportSpamDialogFragment(flow = spam_flow)     │
  │ confirm (+block/leave)   │ reportAsSpam$1                                │
  │                          │  bot chat ──▶ BotMessageHelper/reportUgc      │
  │                          │ SpamReportRepo.A02: route by JID class        │
  │                          │  C9ZJ(flow) ──✗ IllegalArgumentException      │
  │                          │  no message ──▶ last 5 messages from DB       │
  │                          │ serialize msgs (EhE) + token + key,           │
  │                          │ is_known_chat, biz_opt_out, call items        │
  │                          │ C9EN + C9E2 merged into ONE spam_list         │
  │                          │ ── iq set xmlns=spam to=s.whatsapp.net ─────▶│
  │                          │                                   verify token│
  │                          │◀── result <report id> | error 400/403/429/    │
  │                          │    500/501/548 (548 treated as success)       │
  │                          │ WAM wam_spam_report_perf                      │
  │                          │ contacts.is_spam_reported = 1                 │
  │                          │ extra action:                                 │
  │                          │  user ── iq set xmlns=blocklist (block) ────▶│
  │                          │  group ─ leave   channel ─ hide + exit        │
  │◀─ completion dialog (DSA / UK OSA / AU OSA / NCII; needs report id)      │
  │                                                                          │
  │ member: iq set xmlns=w:g2 to=group reports>report{message_id} ──────────▶│
  │ admin : iq get xmlns=w:g2 to=group <reports/> ◀── report > reporter      │
```

---

## 16. Bilinmeyenler

| Öğe | Neden |
|------|--------|
| Sunucu-tarafı token doğrulaması, `reporting_tag` yayını, `server_flagged`'in nasıl belirlendiği | sunucu mantığı, APK'da değil |
| `wi_trace_id`'nin kökeni | üreteç decompile'de bulunamadı |
| Event rapor UI tetikleyicisi, bot-sohbet raporu wire formu | sadece lambda çağıranlar (`AYs`, `Aaa`) / `reportUgc`, `C33437Eh4`'ün ötesinde izlenmedi |
| Channel-status rapor çağıranının geçirdiği flow string'i | `channel_status_report`, `C9ZJ` tarafından reddediliyor |
| `reporting_info*` temizliğinin kesim noktası | `FP7` durumu 6'nın çağıranı izlenmedi |
| Yerel dolandırıcılık-tarama kaydının yüklemesi | tüketici bulunamadı |
| Mesaj-başına `reporting` çocuğunun girdi-başına schema'sı ve flag 20085 çağrısının amacı | DB satırlarından inşa edilmiş, tüketici mantığı okunmadı |
| Bölüm 12'deki herhangi bir stanza'nın canlı kabulü | hiçbir trafik yakalanmadı |
