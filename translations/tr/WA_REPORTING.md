<!-- src-sha1: 27b3b625c1ca67d873007881de02f13ba8cbf277 -->
# WhatsApp Reporting — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Kullanıcı/kişi, grup, kanal, status, arama ve mesaj raporlama — SMAX `spam` stanza'ları, `spam_list`, rapor tipleri, `spam_flow` giriş noktaları, raporlama token'ları, içerik yükleme, rapor/engelleme arayüzü, yöneticiye bildirme, engelleme stanza'sı ve neden listeleri, sunucu hataları, istemci tarafı kötüye kullanım sinyalleri, Baileys

---

## 1. Raporlama nedir (teknik olarak)

Rapor, `spam` ad alanında `s.whatsapp.net` adresine giden tek bir IQ `set`'tir. Bir `spam_list` node'u taşır (raporlanan varlık, raporlanan mesajlar, giriş noktası, business-discovery bağlamı). İstemci raporlanan mesajları düz metin protobuf olarak yeniden serileştirir ve bunları bir raporlama token'ı ve onu doğrulayan anahtarla birlikte yükler. Engelleme ayrı bir stanza'dır (`blocklist`). Yöneticiye bildirme (report-to-admin) üçüncü, ilgisiz bir stanza'dır (`w:g2`).

Tüm ifadeler dekompile edilmiş APK'nın statik analizidir. Seviye: **found** = kodda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülmedi. Burada hiçbir şey ağ üzerinde yakalanmadı.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|-----|
| IQ builder (çok amaçlı, `$t` şekli seçer) | `C9EN` | her rapor IQ'sunu (tipler 0, 18-23) ve birçok ilgisiz IQ'yu oluşturur |
| Neden/giriş noktası node'u | `C9E2` | `spam_flow`, `wi_trace_id`, `is_known_chat`, ... içeren `spam_list` (`xmlns="spam"`) |
| Grup ayarı çocuğu | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| İçerik sarmalayıcı | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Çeşitli node'lar | `C31084Dfc`, `C31085Dfd` | flag'ler (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Serileştirici ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, token birleştirme |
| SMAX manager | `SpamRPCManager` | `A01`-`A06`, rapor türü başına bir tane (paket adı obfuscate edilmemiş) |
| Repo | `SpamReportRepo` | JID sınıfına göre yönlendirir, yerel yan etkiler |
| RPC sarmalayıcıları | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | paket `com.whatsapp.reportinfra.rpc` |
| Origin beyaz listesi | `C9ZJ` | giriş noktasını doğrular (78 değer) |
| Arayüz | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | rapor diyaloğu, isteğe bağlı engelle/ayrıl |
| Engelleme yürütücüsü | `C227489sZ` → `C34631Yx` | `blocklist` IQ'su |
| Yöneticiye bildirme | `RtaXmppClient` | `w:g2` raporlar kuyruğu |
| Token deposu | `C23070uA` | `reporting_info`, `reporting_info_content` tabloları |

İsimler build'e göre değişir; yukarıdaki her obfuscate isim 2.26.41.6'da kararlı dizelerden (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`) çözümlendi.

---

## 2. Rapor tipleri

### 2.1 Yönlendirme (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` JID sınıfına göre dallanır:

| Raporlanan JID | RPC sınıfı | `SpamRPCManager` | Builder `$t` | Yanıt sınıfı | Log etiketi |
|--------------|-----------|------------------|--------------|---------------|-----------|
| newsletter JID üzerinde seçili status nesnesi (`AbstractC31014DeU` null değil) | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| kullanıcı (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| grup | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| başka herhangi bir JID üzerinde seçili status nesnesi veya mesaj listeli status JID'si | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| newsletter/kanal | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| event id (string) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| diğer her şey | yok | yok | yok | yok | `SpamReportRepo: unrecognized jid` fırlatılır, başarısızlık olarak döner |
| bot sohbeti | yok (bkz. 3.3) | yok | yok | yok | `C214999If` |

Spam raporu olmayan diğer `C9EN` şekilleri: `$t=0` yöneticilere bildirme ve `$t=1` grup ayarı geçişi (bölüm 9), `$t=2` alt grup önerileri, `$t=24/25/26` `status` node'ları. Event RPC'si coroutine lambdalarından (`AYs`, `Aaa`) çağrılır; kaynak arayüz unknown (event giriş noktaları `event_home_report` / `event_info_report` mevcut, dolayısıyla event raporları inferred).

### 2.2 Arama raporları kullanıcı raporlarıdır (found)

`SpamReportRepo.triggerReportCallNonSuspend` (`call_spam_dialog_report` origin'i) `IndividualSpamReportRpc.A00`'ı raporlanan `jid` olmadan, mesajsız ve tek bir arama öğesiyle çağırır. Arama öğesi (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` şunları içerir: `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` ve codec ölümcül hataları. Flag **36386**, `to` içindeki kendi JID biçimini seçer (`CUC()` vs `Ask()`, inferred LID vs PN). `shouldIncludeCallLogsInReport` olan bir arayüz kullanıcı raporu en fazla 5 arama kaydı öğesi ekler (`C16430i1.A0B(jid, 5)`).

---

## 3. İstemci akışı

### 3.1 Diyalog

`ReportSpamDialogFragment` (alt diyalog). Fragment argümanları (found): `flow` (giriş noktası dizesi, `spam_flow` olur), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` diyalog durumunu yükler.

Onaylandığında `reportAsSpam$1` çalışır:

1. Bot sohbeti: RPC atlanır (3.3). Aksi halde seçili mesaj tek öğeli bir listede (veya hiç olmadan) `SpamReportRepo.A02(...)` çağrılır.
2. Başarı, isteğe bağlı bir rapor id'si taşır; hata `str3bf8` toast'unu gösterir (veya `C227489sZ.A00`, log `spamreportmanager/spam/report/no-network-cannot-report`). WAM `wam_spam_report_perf` doldurulur (11.3).
3. İsteğe bağlı ek eylem `triggerExtraAction$2` (3.2), `H2U`'dan tamamlama diyaloğu (10.2), yerel yazmalar (3.3).

### 3.2 Yalnızca rapor vs rapor + ek eylem (found)

Onay kutusu, analitik (`asd.BaC` vs `BaD`) ve rapor sonrası toast için kullanılan `report` (işaretsiz) veya `report_block` (işaretli) dizesine eşlenir. Ek eylem hedefe göre değişir:

| Hedef | İşaretliyken ek eylem |
|-------|-----------------------|
| kullanıcı | `C227489sZ.A01` → `C34631Yx` `blocklist` IQ'su ile engelleme (bölüm 8), engelleme nedeni `null`, giriş noktası = `flow`, `deleteChat` = `shouldDeleteChatOnBlock` argümanı |
| grup | gruptan ayrılma görevi (`C98C` / `C9CI`, grup JID'siyle çalışır; ayrılma semantiği inferred) |
| kanal | raporlanan kanalı yerelde gizle (`NewsletterReportCompletionListener`, flag **25218**), ardından newsletter çıkış/takibi bırakma akışı |

Rapor IQ'su önce gönderilir; engelleme/ayrılma, sonucundan bağımsız olarak RPC döndükten sonra çalışır (kontrol akışından inferred, `triggerExtraAction$2` öncesinde başarı kontrolü yok).

### 3.3 Bot sohbetleri ve yerel etkiler (found)

Bot sohbetleri `SpamReportRepo`'yu atlar: istemci `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) çağırır ve bunu başarı sayar (`C214999If`); wire biçimi unknown. Diğer sohbetler için `C24120Ab1` case 4 şunu yapar:

| Adım | Etki |
|------|------|
| mesaj seçilmemiş | sohbetin son **5** mesajını raporlanan içerik olarak toplar (`C14680f4.A01(..., 5, true)`; sistem tipi satırlar hariç, bu varyantta `from_me` filtresi yok) |
| kullanıcı sohbeti | yerel log `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; flag **20085** `H0J.A00(jid, ...)` çağrısını kapılar (amaç unknown) |
| RPC sonrası | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, görünen akışta RPC sonucu kontrol edilmez |

---

## 4. Stanza zarfı ve ad alanı

### 4.1 Neden node'u IQ'ya birleştirilir (found)

RPC'ler iki kardeş `spam_list` yaymaz. Ana `spam_list` (jid, mesajlar) ve neden node'u `C9E2` (bir `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>` parçası) `C10340Uk.A04` ile birleştirilir; bu, öznitelikleri ve aynı adlı çocukları birleştirir (çakışan öznitelik değerleri veya çocuk sayıları birleştirmeyi iptal eder). Sonuç:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Kanıt: 18-23 için `C9EN` ctor'ları `C9E2.A00(iq, reasonNode)` = `iq.A04(node)` çağırır; `C9E2` case 5 `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}` oluşturur; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. IQ `id` değeri `MessageClientSmaxWrapper.A01()` kaynaklıdır (`n<hex counter>`, `C10140Tq.A0H`). Gönderim zaman aşımı 32000 ms (`A0F(node, id, cont, type, 32000, ...)`); null yanıt (zaman aşımı/teslim hatası) `C216549Uq` olur.

Tip 0 ve 1, `xmlns="w:g2"` ve `to=<group>` değerlerini doğrudan atar; tip 18-23 `<iq type="set">` oluşturur ve `to` ile `xmlns` için birleştirmeye güvenir. Göndericiye geçirilen tip id'si **98** (grup, newsletter, event) ve **385**'tir (yöneticiye bildirme).

### 4.2 `spam_list` içine birleştirilen isteğe bağlı kardeşler

| Node/öznitelik | Kaynak | Kapı | Seviye |
|----------------|--------|------|--------|
| `spam_flow` | `C9ZJ` ile normalize edilen `flow` argümanı | her zaman | found |
| `wi_trace_id` (tam 24 karakter) | `reportAsSpam$1`'in `$wiTraceId` değeri | isteğe bağlı | found; değerin kaynağı unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | flag **22256**; kullanıcı: adres defteri kontrolü, grup: grup üyeliği kontrolü | found |
| `biz_opt_out` çocuğu | `C33446EhE.A07` | business discovery kaydı mevcut | found (bkz. 8.3) |

---

## 5. Tip başına stanza'lar

Bir `<message>` öğesinin `from`/`to` değeri: kullanıcı yolunda anonim node `C9E4`, mesaj giden ise (`key.fromMe`) `to=<jid>`, değilse `from=<jid>` atar. Sayılar builder kapılarıdır (`AbstractC10350Ul.A07`).

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

Builder üç öğe listesi alır; üst sınırlar 210 (mesajlar), 5 (arama öğeleri), 5 (mesajsız business-flow öğeleri, `C33446EhE.A0B`: `messageless_flow_ids_per_business_<jid>` işletme başına deposunun son 5 girdisi, node `extension_screen`). `jid` yalnızca `UserJid` ve `C99O` ile doğrulanır; bu yolda `subject` yok.

### 5.2 Grup (tip 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source`, **raporlayanı gruba ekleyen kullanıcıdır**, raporlayan değil. Yerel sistem mesajından ("me joined") `GET_GROUP_ADDER_JID_SQL` SQL'i ile okunur (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`). İsteğe bağlı. (found)
- `subject`, kişi kaydından gelen grubun görünen adıdır (`C06290Dn.A07().A00.A0b`; alan anlamı inferred), topluluk üst grupları için veya kayıt yoksa boş dize `""` (`Voip.REJECT_REASON_DECLINED` değeri `""`). Bir neden değildir. Uzunluk kapısı 0..65536. (found)
- Ctor'daki dördüncü liste boş değilse fırlatır (`getNode`); RPC boş bir liste geçirir.

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

Status, `server_id` + zaman damgasıyla tanımlanır, yüklenen içerik yok. `status` çocuk içeriği (`InterfaceC35700FdB`) çözümlenmedi.

### 5.5 Event (tip 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`, `wi_trace_id` yok (tek argümanlı `C9E2(String)` yolu). Yöneticilere mesaj (tip 0): bölüm 9.1.

---

## 6. Raporlanan içerik ve token'lar

### 6.1 Neler yüklenir (found)

`C33446EhE.A0A(fmsg, entryPoint)` raporlanan her mesaj için bir mesaj öğesi oluşturur:

| Parça | Ayrıntı |
|-------|---------|
| `<message>` öznitelikleri | `t` (mesaj zaman damgası, 0..2^53), `id` (stanza id), `from`/`to` jid, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | yeniden serileştirilmiş `Message` protobuf (`MessageContextInfo` `C30624DTs` ile `C30628DTw`); `local_message_type` = dahili mesaj tipi int'i |
| `<content_validation>` | token + anahtar (6.2) |
| meta flag'ler | `<edit v="1">` (düzenlenmiş), `<multicast/>` (broadcast flag 64), `<url_number/>` (flag 4), `<url_text/>` (flag 2), şablon id, `hsm` tid, `iab reported_link`, `original_sender` / `group_history_sender`, `futureproof`/`request`/`send` ödeme varyantları (`pay`), `reported_push_name` |
| `<reporting>` çocuğu | flag **5718**: mesajın `reporting_info` satırlarından oluşturulur (`C23070uA.A03`), en fazla 1000 girdi (`C31085Dfd` case 28); girdi başına şema tam okunmadı |
| alternatif taşıyıcılar | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 değer, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

OTP şablon mesajları: buton başlıklarındaki `<code>` yer tutucusu serileştirmeden önce gerçek kodla değiştirilir (`AbstractC32303E8u.A00`). View-once: mesaj view-once ise ve zaten açılmış/süresi dolmuşsa ve origin `media_viewer` / `view_once_viewer` değilse `A06` true olur ve serileştirme bloğu atlanır. Öğenin bu durumda boş mu yoksa var olmayan bir `raw` mı taşıdığı inferred'dir (bildirim dekompilede başlatılmamış).

Medya dosyaları bu stanza ile yeniden yüklenmez; serileştirilmiş mesaj medya referanslarını taşır (inferred; yükleme çağrısı bulunamadı). Stanza düz metin proto'yu ve anahtarı birlikte tutar, dolayısıyla sunucu içeriği okuyabilir: node'lar **found**, okunabilirlik **inferred**.

### 6.2 Raporlama token'ı ve anahtarı (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

`C33446EhE.A03` içinde saklanan satırdan (`C34539Ez0`) birleştirilir: token baytları (`A05`), sürüm (`A02`), stanza id (`A03`), anahtar (`A07`). Anahtar eksikse yeniden türetilir: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → native `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (use case id **5**; kullanıcı olmayan sohbetler `JniBridge` varyantlarından geçer). Hem anahtar hem 6 baytlık token yoksa/sıfırsa istemci `ReportingToken/MissingFkAtReport` loglar ve tümü sıfır olan 32 baytlık bir anahtar kullanır. Eksik token `null` döndürür (`ReportingToken is null`, öğede `content_validation` yok).

### 6.3 Token yaşam döngüsü (aksi belirtilmedikçe found)

| Aşama | Ayrıntı |
|-------|---------|
| Giden mesaj | builder `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Token = `HMAC-SHA256(key, canonicalContent)`'in ilk 16 baytı (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = sürüme bağlı alan filtrelemeli mesaj proto'su (`A07`, alan 35'in seçili alt alanlarını çıkarır; okuma inferred). Builder'ın çağıranları izlenmedi |
| Grup geçmişi paylaşımı | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): tip 117 mesajlar için girdi başına bir çocuklu `<reporting>` (öznitelik `id`, çocuk `<reporting_token v>`) |
| Gelen mesaj | stanza çocuğu `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>`, `C34764F6h` / `C1S0` tarafından ayrıştırılır, flag **5718**; tag ve token isteğe bağlı, tag zorunlu |
| Depolama | `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) ve `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`) tabloları; `message_conditional_reveal.reporting_token_info` (blob); `group_history_share_reporting_info`; `status_reporting_info` |
| Geçmiş | `WebMessageInfo.reportingTokenInfo` alan **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; flag **6578** |
| Temizlik | `receive_timestamp` bir eşikten eskiyse `reporting_info*` satırları silinir (`FP7` case 6); eşik değeri çözümlenmedi |
| Alternatif doğrulama node'u | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

`reporting_tag`'i kimin verdiği ve sunucunun token'ı nasıl doğruladığı: sunucu tarafı, unknown. Eşleşme (stanza'da tag, raporda token+anahtar) inferred'dir.

---

## 7. `spam_flow` giriş noktaları

97 değer (found, `C9E2` case 5, sıra = dizi sırası). `flow` argümanı, bunlardan **78**'ini kabul eden `C9ZJ.A00`'dan geçirilir; aksi halde `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` fırlatır. Altı RPC sarmalayıcısının tümü bunu çağırır ve `SpamReportRepo.A02` istisnayı yakalayıp başarısızlık döndürür (istemci tarafı hata, stanza gönderilmez). 78 değer, 97'nin kesin alt kümesidir. Reddedilen 19 değer: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. Bunlar büyük olasılıkla yalnızca engelleme veya başka RPC origin'leridir (inferred). `channel_status_report` enum'da var ama `C9ZJ` tarafından reddedilir; kanal-status çağıranının hangi flow'u geçirdiği unknown.

| Yüzey | Değerler |
|-------|----------|
| Sohbet / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Spam banner'ları | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| FMX güvenlik kartları | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| Cihaz üstü dolandırıcılık uyarıları | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Grup | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Aramalar | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Kanallar / status / event'ler | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Business | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

FMX kartları için `*_suspicious` vs düz seçimi `C230769yA.A05` içinde `A0D(userJid)` (kişi biliniyor mu) ile yapılır; bu predicate'in adres defteri kontrolü olduğu inferred. `server_flagged` varyantları kart tipine göre seçilir; sunucu flag'inin nereden geldiği unknown.

`wi_trace_id`: 24 karakterlik isteğe bağlı öznitelik, çağırandan aynen geçirilir; üreticisi bulunamadı (unknown). Aynı zamanda WAM `wam_spam_report_perf` alanıdır (11.3).

---

## 8. Engelleme, nedenler ve business bağlamı

### 8.1 Engelleme IQ'su (found, `C34631Yx.A0M` çevresi)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` ve `entry_point` yalnızca `action="block"` için yayılır. `jid`, PN ve LID biçimleri arasından bir ayar kontrolüyle seçilir (`zA02` dalı; kesin kural tam okunmadı); engellemede ek tanımlayıcı `pn_jid` / `username` / `display_name` / `unknown_identifier="true"` değerlerinden biridir. Zaman aşımı 20000 ms. `odml_scam_alert_*` ile başlayan giriş noktaları `1_1_spam_banner_block` olarak yeniden yazılır (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). PSA sohbetleri farklı bir IQ kullanır (`xmlns="w:comms:chat"`, `<blocking action>`). Getirme: `type="get"`, isteğe bağlı `<item dhash>`.

### 8.2 Engelleme nedenleri (found)

`AbstractC227579sl.A00` içinde sabit kodlu dize → yerel int: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, diğer = 0. `RunnableC40792Hpk` aynı dizeleri ikinci bir kod kümesine eşler. Bu int'ler yerel log çağrılarına gider; bir sunucuya ulaşıp ulaşmadıkları unknown.

Business engelleme sayfası (`C24126Ab7`): boş değilse sunucu neden haritası, değilse `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; OTP şablonlu sohbetler: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Business discovery bağlamı (found)

`C33446EhE.A07`, raporlanan JID için business-discovery kaydını okur (depo `LA8`): zaman damgası, id, giriş noktası. Giriş noktası enum'u (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. Hem raporlara (`spam_list` altında `biz_opt_out`) hem engellemelere eklenir. İstemcide bulunan, sohbetin nasıl başladığına dair tek sinyaller bunlardır.

### 8.4 Rapor neden listeleri (found)

Yalnızca business reklamlarında seçilebilir bir liste vardır. `ReportReasonListFragment` boş başlar ve `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` ile doldurulur (yanıt `mobile_config` > `list`, `name`, `v`, `country` ile). Sabit kodlu yedek enum (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. Yedek kullanıldığında: sunucu listesi mevcut değil olarak inferred. Sıradan kullanıcı/grup/mesaj raporları için neden seçici yoktur; wire üzerindeki tek "neden" `spam_flow`'dur.

---

## 9. Grup yöneticilerine bildirme

### 9.1 Gönderme ve getirme (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

İçerik, token veya `spam_flow` gönderilmez; yalnızca mesaj id'si. Hatalar yalnızca `Rta::<op>/onError: <code>` veya `/onDeliveryFailure: Network Failure` loglar.

### 9.2 Üye-raporu geçişi (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (etkinleştir) veya `<not_allow_admin_reports/>` (devre dışı bırak), smax 384. Node'lar IQ'nun doğrudan çocuklarıdır, bir `group` node'una sarılmaz. Builder tek IQ'da dört kardeş ayar node'una kadar kabul eder.

---

## 10. Sunucu yanıtı ve tamamlama diyalogları

### 10.1 Yanıt (found)

Başarı (`type=result`): `id` özniteliği olan (maks. 20 karakter) `report` çocuğu → `C213959Ch.A01` → arayüze rapor id'si olarak döner. Hatalar (`<error code text>`), yanıt sınıfına göre:

| Kod | Ad | Individual | Group | Newsletter | Status | Status V2 | Event |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 Tamamlama diyalogları

`H2U` rapor id'sinden ve kapılardan karar verir, ardından `C5BD` fragment'i oluşturur (`arg_report_id`, `arg_is_ad_report`):

| Kapı | Diyalog |
|------|---------|
| flag **25818**, kullanıcı sohbeti, mesaj mevcut | `NciiCompletionDialogFragment` |
| flag **6145** | `DsaCompletionDialogFragment` (AB) |
| flag **14249** | `UkOsaCompletionDialogFragment` |
| flag'ler **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

NCII dışındakilerin tümü null olmayan bir rapor id'si gerektirir; id yoksa diyalog yoktur.

---

## 11. İstemcideki kötüye kullanım sinyalleri

### 11.1 İstemcinin içeriğin ötesinde gönderdikleri (found)

`*_server_flagged_suspicious` içeren giriş noktaları, kartın yerel kişi kontrolü dışında bir sinyalle işaretlenmiş bir sohbet için gösterildiği anlamına gelir; istemcinin bu flag'i nasıl öğrendiği unknown. Raporlarda gönderilenler: `is_known_chat`, `biz_opt_out` (business sohbetinin nasıl başladığı), arama öğeleri (süre, kimin bitirdiği, sonlandırma nedeni), business Flows `extension_screen` bağlamı, `source` (beni gruba kimin eklediği), `reported_push_name`, her mesajda iletme/broadcast/URL flag'leri, düzenlenmiş flag'i, view-once durumu, giriş noktası, isteğe bağlı `wi_trace_id`.

### 11.2 Cihaz üstü dolandırıcılık tespiti (found, kapsamlı)

`com.whatsapp.integrityai`, indirilmiş bir model kümesini (`scam_detection`) cihaz üzerinde ExecuTorch ile çalıştırır (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; özellikler `mostRecentSenderScore`, `isCountryMismatch`). Sonuçlar uyarı banner'larını/sayfalarını ve yukarıdaki `odml_scam_alert_*` giriş noktalarını tetikler. `integrity_warning_report_enabled` olduğunda (`C57375Pog`) bir `FileStash`'e yerel bir JSON tarama kaydı (`outcome`, `inputs`, `model_info`, `verification`) yazılır. Bu kaydın yüklendiği bulunamadı (unknown). `spam` rapor stanza'sından bağımsızdır.

### 11.3 Telemetri (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. `reportAsSpam$1` içindeki hata kodu eşlemesi: iptal -4, zaman aşımı/yanıt yok -1, diğer istisna -3, protokol hatası = IQ hata kodu.

---

## 12. Baileys

`baron-baileys-v2` paketinde rapor API'si yok. Aşağıdaki şekiller found node'lardan gelir ve tested değildir.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

Kullanıcı/grup/kanal rapor şekilleri bölüm 5'i izler (tek birleştirilmiş `spam_list`, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Neden başarısız olur (tümü inferred) | Sebep | Çözüm |
|--------------|-------|-------|
| hata 548 veya sessiz no-op | geçerli raporlama token'ı/anahtarı yok: Baileys gelen mesajların `<reporting>` çocuğunu atar ve anahtarı hiç türetmez | alırken `reporting_tag`/`reporting_token` ayrıştırın, mesaj başına saklayın, rapor anında anahtarı `messageSecret`'tan türetin (use case 5) |
| 400 | yanlış sınıfta `jid` (tip 20 için kullanıcı/interop olmalı), üst sınırı aşan öğe sayıları, yanlış tipte `spam_flow` | bölüm 7'deki `spam_flow` dizelerini kullanın; 210 / 5 öğenin altında kalın |
| reddedilen IQ | tek birleştirilmiş node yerine iki kardeş `spam_list` (neden ikinci bir node olarak gönderilmiş) | tüm özniteliklerle tek bir `spam_list` gönderin |

`wi_trace_id` ve `is_known_chat` builder'da isteğe bağlıdır; sunucunun uydurma token'lı raporları kabul edip etmediği unknown.

---

## 13. Hata durumları

| Belirti | Sebep | Seviye |
|---------|-------|--------|
| toast `str3bf8`, hiçbir şey gönderilmedi | `C9ZJ`, `flow` değerini reddetti (`Invalid BlockSpamReportOrigin value`) | found |
| `unrecognized jid` başarısızlığı | sohbet JID'si kullanıcı/grup/status/newsletter'dan hiçbiri değil | found |
| rapor toast'suz "başarısız olur" | sunucu hatası 548: `C9ZI.A00`, bot yoluyla aynı hata olmayan sonuç nesnesini döndürür | found |
| genel başarısızlık toast'u | 400/403/429/500/501 veya zaman aşımı (32 sn) → `C216549Uq` | found |
| rapor içeriği eksik | view-once açılmış/süresi dolmuş ve origin bir görüntüleyici değil; mesajın saklanmış token'ı yok | found / inferred |
| yerel durum raporlandı diyor, sunucu reddetti | `is_spam_reported` görünür sonuç kontrolü olmadan RPC'den sonra yazılır | found (akış), inferred (sonuç) |

---

## 14. Temel ayrımlar

| Karıştırmayın | Şununla |
|----------------|---------|
| `spam_list@source` | raporlayan. Raporlayanı gruba ekleyen kullanıcıdır |
| `spam_list@subject` (grup, kanal) | bir neden. Grup/kanal adıdır |
| `spam_flow` | bir rapor nedeni. Raporu tetikleyen arayüz yüzeyidir (97 değer) |
| rapor (xmlns `spam`) | engelleme (xmlns `blocklist`), yöneticiye bildirme (xmlns `w:g2`), pazarlama opt-out'u (xmlns `optoutlist`, `C31105Dfx`, daha fazla analiz edilmedi) |
| iki `spam_list` node'u | tek birleştirilmiş `spam_list` (öznitelikler ve çocuklar birleştirilmiş) |
| arama spam'i | event spam'i. Arama raporları `call` öğeli tip 20'dir; tip 18 `event_id`'dir |
| `reporting_tag` (sunucu tarafından verilir, alırken saklanır) | `reporting_token` (16 baytlık HMAC, giden mesajlarla gönderilir ve raporlarda yüklenir) ve `reporting_token_key` (türetilmiş, yüklenir) |
| yöneticiye bildirme | WhatsApp'a bildirme. Yönetici raporu yalnızca `message_id` gönderir; içerik yok, token yok |
| `wi_trace_id` (istemcinin gönderdiği trace id) | sunucunun `<report id>` içinde döndürdüğü rapor id'si |
| `report_block` | bir wire değeri. İstemci analitik/toast dizesidir; engelleme kendi IQ'sudur |
| `allow_admin_reports` geçişi (`$t=1`) | yöneticiye bildirme mesajı (`$t=0`) |

---

## 15. Uçtan uca akış

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

## 16. Unknown

| Öğe | Sebep |
|-----|-------|
| Sunucu tarafı token doğrulaması, `reporting_tag` verilmesi, `server_flagged` kararının nasıl verildiği | sunucu mantığı, APK'da yok |
| `wi_trace_id` kaynağı | üretici dekompilede bulunamadı |
| Event raporu arayüz tetikleyicisi, bot-chat rapor wire biçimi | yalnızca lambda çağıranlar (`AYs`, `Aaa`) / `reportUgc` `C33437Eh4` ötesine izlenmedi |
| Kanal-status raporu çağıranının geçirdiği flow dizesi | `channel_status_report` `C9ZJ` tarafından reddedilir |
| `reporting_info*` temizliğinin eşiği | `FP7` case 6'nın çağıranı izlenmedi |
| Yerel dolandırıcılık tarama kaydının yüklenmesi | tüketici bulunamadı |
| Mesaj başına `reporting` çocuğunun girdi başına şeması ve flag 20085 çağrısının amacı | DB satırlarından oluşturulur, tüketici mantığı okunmadı |
| Bölüm 12'deki herhangi bir stanza'nın canlı kabulü | hiç trafik yakalanmadı |
