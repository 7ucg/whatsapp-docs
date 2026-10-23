<!-- src-sha1: 7c179c130d5822c6103aa9a9ae2e6751ec1b0bd8 -->
# WhatsApp Çağrı Sinyalleşmesi — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-24
**Kapsam:** Android sesli/görüntülü çağrı sinyalleşmesi: `<call>` zarfı ve ack'ler, action stanza'ları (offer, accept, preaccept, reject, terminate, transport, relaylatency, enc_rekey, mute_v2, group_info, group_update, lobby, link_*, waiting_room_*, bcall), offer payload'ı (audio / video / capability / encopt / net), çağrı anahtarı ve Signal şifrelemesi, rekey (v2 / v3), medya anahtarı türetimi, relay ve taşıma seçimi, ICE / STUN / DTLS / SRTP ile WhatsApp'a özgü medya yolu karşılaştırması, grup çağrıları, çağrı bağlantıları ve zamanlanmış çağrılar, çağrı kaydı ve bcall mesajları, offer nack kodları, reject ve terminate davranışı, feature flag'leri, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

Çağrı sinyalleşmesi, normal chatd bağlantısı üzerindeki bir `<call>` stanza kümesidir (bkz. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Her stanza tam olarak bir action child taşır. Java katmanı çağrı stanza'larını oluşturmaz ve ayrıştırmaz: bunu native bir VoIP motoru yapar; Java yalnızca (a) giden child'ları `<call>` içine sarar, (b) çağrı anahtarını her cihaz için Signal ile şifreler, (c) gelen stanza'ları motora iletir, (d) motor olaylarına tepki verir. Medya (relay'lere RTP benzeri trafik, ICE, DTLS, SRTP) sinyalleşme değildir ve motorun sahip olduğu UDP/TCP soketleri üzerinde çalışır. Tüm ifadeler statik analizden gelir; ağ üzerinde hiçbir şey yakalanmadı. Kademeler: **found** = Java'da veya native string'lerde okundu, **inferred** = çıkarım, **unknown** = çözülemedi.

| Katman | 2.26.41.6 adı | Rol |
|--------|---------------|-----|
| JNI cephesi | `Voip` / `VoipNativeImpl` (`com.whatsapp.calling.voipcalling`) | 148 native metot (`startCall`, `acceptCall`, `rejectCall`, `nativeHandleIncomingSignalingXmpp`, ...) |
| Giden hook | `OutgoingSignalingHandler`, `SignalingXmppCallback.sendCallStanza(Jid, callId, VoipStanzaChildNode)` arayüzünü uygular | motordan Java'ya; tag başına işleme, çağrı anahtarı şifreleme |
| Zarf yazıcı | `CIX` (kuyruk), `C27410BtV` (çağrı stanza'sı), `HandlerThreadC21920sG` içinde writer-thread case 206 | `<call to id>` oluşturur |
| Gelen işleyici | `C40641lA` (`CallStanzaHandler`), `BQU` (ayrıştırılmış çağrı stanza'sı), `C83` (decrypt), `C28120CKj` / `RunnableC29343CoU` (motora dispatch) | zarfı ayrıştırır, `<enc>` çözer, motora besler |
| Motor olayları | `VoipEventCallback`, `VoiceServiceEventCallback` (116 callback) | motordan UI / duruma |
| Crypto callback | `DefaultCryptoCallback`, `SignalIdentityCryptoCallback` (`CryptoCallback`) | motor için HKDF / HMAC / random / Ed imzaları |
| HTTP sinyalleşme | `VoiceTeeHttpSignalingHandler` (`SignalingHttpCallback`) | alternatif sinyalleşme taşıyıcısı, TEE isteği |
| Native motor | `libwhatsapp.so` (superpack arşivi `libs.so` içinden açılır; `Java_com_whatsapp_calling_voipcalling_Voip_*` export eder) | stanza serializer'ları / deserializer'ları, çağrı durum makinesi, taşıma, medya |

Raporun geri kalanını belirleyen noktalar:

- Stanza grameri native kodda yaşar: `serialize_*` serializer'ları (C/C++) ve gelen ayrıştırma için bir Rust crate'i `call_control` (panic string'lerinde kaynak yolları `xplat/wa-voip/rust/call_control/src/stanza_deserializer/...`). Voip kütüphanesi decompile edilemedi; her native ifade yalnızca string'lere ve export edilen adlara dayanır (string'ler found, anlamı inferred).
- Java ince bir katmandır; bu yüzden Java'da görülen tag kümesi (`sendCallStanza` içinde 10 tag) motorun anladığı kümeden çok daha küçüktür (bölüm 4).
- Çağrı anahtarı motor tarafından üretilir ve kullanılır; Java onu olağan pairwise Signal oturumuyla şifreler (bölüm 6). Motorun ihtiyaç duyduğu aynı HKDF kodu bir Java callback'idir (bölüm 7).
- WhatsApp'a özgü medya yolu (relay allocate/bind, "WARP" paketleri, hop-by-hop SRTP, grup çağrıları için SFrame), "web_p2p" modu olarak var olan WebRTC tarzı ICE/DTLS yolundan farklıdır (bölüm 8).

---

## 2. Java / native arayüzü

Başlangıçta kaydedilen callback'ler (found): `SignalingXmppCallback.sendCallStanza(to, callId, node)` (motordan Java'ya, bir çağrı child'ı); `CryptoCallback` (`generateE2EKeysV2`, `getSecureSsrc`, `hkdfSha256`, `hmacSha256`, `generateRandomBytes`; `SignalIdentityCryptoCallback` ek olarak 64 baytlık imzayla `signWithIdentityKey` ve 32 baytlık anahtarla `verifySignature` ekler); `SignalingHttpCallback` (`sendMsg(callId, bytes, requestType)`, `cancelMsg`; türler: voice session 0, codec avatar 1); `VoipEventCallback` (bölüm 13). `VoipStanzaChildNode`, JNI'den görülebilen ağaçtır (tag, attribute'lar, child'lar, data); Java onu chatd node'una çevirir ve geri çevirir, binary kodlaması [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) bölüm 8'de anlatılır.

| JNI girişi (found) | Besleyen | Notlar |
|--------------------|----------|--------|
| `nativeParseXmppOffer(CallOfferInfo[], ...)` | `preprocess_call_offer` (`AbstractC24816AmW`) | çağrı başlatmadan bir offer'ı ayrıştırır; `CallOfferInfo`: callId, fromJid, groupJid, callLinkToken, isVideoCall, isAudioChat, isJoinableCall, isOfferExpired, isCallEnded, silenceReason, groupPhash, participantHash, callGroupInfo |
| `nativeHandleIncomingXmppOffer` | `C28120CKj` | gelen çağrı işlemeyi başlatır |
| `nativeHandleIncomingSignalingXmpp` / `...Ack(from, type, errorCode, children, ..)` / `...Receipt` | `RunnableC29343CoU` (mesaj 192) | offer olmayan her action, kendi stanza'larının ack'leri (dönüş 70004 bozuk ack olarak loglanır), çağrı receipt'leri |
| `peekIncomingOffer`, `handleIncomingTerminatePush` | push yolu | zil öncesi karar, push ile teslim edilen terminate |
| `handleIncomingSignalingHttp(callId, bytes, ..)` | TEE HTTP yanıtı | alternatif taşıyıcı (11.3) |

---

## 3. Zarf, ack'ler, receipt'ler

### 3.1 Giden `<call>` (found, `HandlerThreadC21920sG` case 206)

```
<call to="<jid>" id="<stanza id>">
  <ACTION .../>                      exactly one child
</call>
```

`to`, `C0DZ.A0R` kontrolünden geçmelidir (user, device ve birkaç başka JID türü; aksi halde `C27410BtV` `CallStanza:Wrong jid type` fırlatır). Stanza id'si ortak id üretecinden gelir. Log satırı `WriterThread/write/call-stanza-<tag>`.

### 3.2 Gelen `<call>` (found, `C40641lA`)

| Attribute | İşleme |
|-----------|--------|
| `from` | geçerli bir JID olmalı, aksi halde `CallStanza from invalid jid`; bir user JID'i birincil cihazına eşlenir |
| `id` | stanza id'si, ack için kullanılır |
| `t` | saniye, 1000 ile çarpılır |
| `e` | tam sayı saniye, 1000 ile çarpılır ve `t` yanında motora geçirilir (tam anlamı çözülemedi; inferred offer yaşı / geçerlilik girdisi) |
| `offline` | tam sayı; varlığı offline kuyruğundan teslimi işaretler |
| `notify`, `platform`, `version` | olduğu gibi iletilir (arayan push adı, platform, uygulama sürümü) |
| `participant` | grup bağlamlarında göndericinin device JID'i; hatalı değer `from`'a düşer |
| `sender_lid` | `from` bir LID alan adlı JID olduğunda okunur |
| child `call-creator` | device JID'i (offer olmayan mantık için zorunlu) |
| child `call-id` | zorunlu; `reminder` ve `bcall_*` tag'leri hariç, bunlara boş call id verilir |
| diğer attribute'lar | `caller_pn` (telefon numarası device JID'i), `username`, `caller_country_code`; yalnızca creator LID ve tag `offer` değilken okunur |

`to` ve `call-creator` farklı adres alan adlarındaysa (biri LID, biri telefon numarası) istemci `CallStanzaHandler/call-mixed-domain/...` loglar ve `CallMixedDomainStanza` metriğini raporlar, sonra devam eder (found). Karışık alan adları reddedilmez, tolere edilir.

### 3.3 Ack'ler

| Durum | Davranış (found) |
|-------|------------------|
| tag {offer, accept, reject, enc_rekey, terminate} içinde değil | Java hemen ack gönderir: `<ack class="call" type="<tag>" id to [participant]/>` (`AbstractC47181wT.A01`) |
| tag bu kümede | Java'dan anında ack yok; node ayrı bir bekleyen-ack yoluna gider (`C36591ch.A0G`); anlamı çözülemedi |
| kendi stanza'sının ack'i | `nativeHandleIncomingSignalingXmppAck(from, type, errorCode, children, ...)`. Java'da görülen ack türleri: offer (relay verisi taşır, bölüm 8), accept, link_join, link_query, lobby; native ayrıca link_create, link_edit, remove, remove_user, heartbeat, screen_share, add_extension, remove_extension, relaylatency, video state, waiting_room_* işler |
| hata 435'li offer ack'i | ack sonrası ek bir action zamanlanır (amacı çözülemedi) |
| offer / accept teslimi | Java, chatd teslim ack'ini zaman aşımıyla bekler (flags 9257, 9431); zaman aşımında stanza düşürülür ve `Call stanza delivery timed out` loglanır |

### 3.4 Sözlük token'ları (found, `AbstractC40911lb`)

Tek bayt (`A00`): `call` 97, `call-id` 101, `call-creator` 68, `terminate` 208, `relaylatency` 70, `video` 86, `audio` 158, `capability` 177, `device-identity` 227, `privacy` 223, `te` 212, `te2` 198, `token` 194, `key` 155, `participant` 5, `user` 14, `remove` 172, `notify` 24, `registration` 170, `attribute_padding` 229, `relay_id` 130, `token_id` 143. İkincil sözlük 0 (`A01[0]`): `offer` 28, `accept` 97, `preaccept` 18, `transport` 44, `mute_v2` 253, `group_info` 170, `group_update` 99, `net` 103, `medium` 36, `encopt` 21, `keygen` 26, `voip_settings` 10, `relay` 116, `joinable` 75, `heartbeat` 6, `transaction-id` 62, `uuid` 132, `self_pid` 71, `peer_pid` 76, `metadata` 118, `uncompressed` 20, `rate` 29, `dec` 73, `screen_width` 5, `reason` 46. İkincil 1: `reject` 0, `enc_rekey` 205, `e` 235.

Bu build'in hiçbir sözlüğünde olmayanlar (wire üzerinde düz string): `lobby`, `flowcontrol`, `screen_share`, `link_*`, `peer_state`, `interruption`, `reminder`, `raise_hand`, `waiting_room_*`, `hbh_key`, `auth_token`, `lightweight`, `silence`, `scheduled-id`, `group-jid`, `link-token`, `caller_pn` ve `enc`.

---

## 4. Action sınıflandırması

Native deserializer'ın dispatch ettiği gelen tag'ler (found, `call_control` içindeki string listesi): `offer`, `accept`, `preaccept`, `reject`, `terminate`, `transport`, `relaylatency`, `enc_rekey`, `notify`, `flowcontrol`, `interruption`, `group_update`, `mute_v2`, `screen_share`, `raise_hand`, `reconfigure_bot`, `user_action`, `ready`, `relay_info_update`, `tos`, `screen`, `switchable`, `add_extension`, `waiting_room_update`, ayrıca `receipt`. Ayrıştırılan ack'ler: offer, accept, video state, relaylatency, link_create / edit / query / join, lobby, heartbeat, remove, remove_user, screen_share, add_extension, remove_extension, waiting_room toggle / admit / deny / leave.

| Tag | Yön (found) | Amaç |
|-----|-------------|------|
| `offer` | out / in | çağrı başlatır (bölüm 5); in: ayrıca `is_call_ended` ve `terminate_hint` ile zaten bitmiş çağrılar için offer'lar |
| `preaccept` | out / in | callee cihazı çalıyor / hazır; motor durumu `PRE_ACCEPT_RECEIVED`, olay `preacceptReceived` |
| `accept` | out / in | callee kabul eder; medya parametreleri ve bir sertifika taşır (native string'ler `error parse voip params for accept`, `error parsing certificate for accept`) |
| `reject` | out / in | callee reddeder; neden string'leri bölüm 14.2'de |
| `terminate` | out / in | çağrıyı bitirir; transaction id ve `call_summary` (bölüm 14.3) |
| `transport` | out / in | adaylar, ICE kimlik bilgileri, sertifika, sağlık (bölüm 8.5) |
| `relaylatency` | out / in | ölçülen relay gecikmeleri (bölüm 8.4); kendi ack'i var |
| `enc_rekey` | out / in | çağrı anahtarının yeniden paylaşımı (bölüm 6.4) |
| `video` (state) | out / in | video açık / kapalı / yükseltme; `kVideoState*` değerleri (bölüm 13); ack relay bilgisi taşır |
| `notify`, `peer_state`, `flowcontrol`, `interruption`, `ready`, `heartbeat` | out / in | çağrı içi durum: peer bildirimleri, ağ sağlığı, akış kontrolü, kesintiler, grup heartbeat'i |
| `mute_v2`, `raise_hand`, `user_action`, `tos`, `reconfigure_bot` | out / in | grup çağrılarında sessize alma isteği, el kaldırma, kullanıcı action'ları, grup çağrısı TOS'u, bot yeniden yapılandırma (`req_id` attr) |
| `group_info`, `group_update` | in (offer / ack / update child'ı) | katılımcı listesi (bölüm 9) |
| `lobby` | out / in | grup çağrısı lobby sorgusu / durumu; ack'i grup bilgisi taşır |
| `screen`, `screen_share`, `switchable` | out / in | ekran paylaşımı durumu; cihaz değiştirme (`switch_info`, `root_call_id`, `root_call_creator`, `peer_active_device`) |
| `add_extension`, `remove_extension` | out / in | çağrıya bir medya uç noktası ("extension") ekler (bölüm 9.4) |
| `remove`, `remove_user`, `cancel_offer` | out | katılımcıları çıkarır; seçilen katılımcılar için bir offer'ı iptal eder |
| `link_create`, `link_edit`, `link_query`, `link_join` | out | çağrı bağlantıları (bölüm 10) |
| `waiting_room_toggle`, `_admit`, `_deny`, `_leave`, `_update` | out / in | bağlantı çağrısı bekleme odası (bölüm 10.3) |
| `reminder`, `bcall_*` | in | sunucu hatırlatıcıları; business-call ailesi (bölüm 11) |
| `dtmf`, `duration`, `connect_stat`, `group_call_duration`, `group_call_tos_accepted` | out | motorda bulunan serializer'lar |

`sendCallStanza` içinde Java'dan görülen tag'ler (found): `offer`, `accept`, `reject`, `terminate`, `video`, `enc_rekey`, `lobby`, `link_join`, `link_query`, `link_create`; diğer her tag varsayılan gönderim yolunu izler.

Sayısal mesaj-id tablosu (85 tür), mekanizma ayrımı (child / ack / receipt / internal) ve sabit başlık uzunlukları: bu build'de bulunamadı. Motor, string'lerde görünen bir id enum'u değil, tag'leri ve tag başına serializer'ları açığa çıkarır. Android için herhangi bir id tablosunu unknown say.

---

## 5. Offer

### 5.1 Oluşturma ve gönderme (found)

`startCall(...)`, motorun `sendCallStanza(peer, callId, offerNode)` yayınlamasını sağlar. Java:

1. `sendOfferStanza` stanza id'sini saklar (`outgoingCallOfferKey`), herhangi bir hedef cihaz için bekleyen bir pre-key işi varken bekler, sonra çağrı anahtarını bir worker üzerinde cihaz başına şifreler (`getBulkEncryptedE2EKeys`, bölüm 6.1).
2. Sonuç ya yeni formatta (`<destination><to jid><enc/></to>...</destination>`, `AbstractC33466EhY.A08` ile) ya da eski formatta (tek `<enc>` child'ı, yalnızca bir cihaz için geçerli; `cannot have multiple encrypted messages in old format!`) yazılır.
3. Herhangi bir cihaz `pkmsg` aldıysa `<device-identity>` eklenir (companion tercihlerinden `adv_signed_identity` baytları); bu yalnızca self cihaz `BRD()` kontrolünden geçtiğinde olur (registration device id sıfırdan farklı, yani bir companion; inferred).
4. `CIX.A02` `<call>` stanza'sını kuyruğa alır; flag **9257** (ms) teslim beklemesini sınırlar.
5. Gönderimden sonra bir çağrı ping IQ'su zamanlanır (flag **30890**, gecikme **30891** ms varsayılan 3000, deneme sayısı **32651**); bağlantı kopuksa istemci yeniden bağlanır, çağrı artık `CALLING` durumunda değilse bağlanmaz.
6. Hedefler şifrelenemezse offer `pendingCallOfferStanza` olarak tutulur ve sonra gönderilir (bir pre-key işi bittiğinde `maybeSendPendingOffer`, terminate'te `sendPendingCallOfferStanza`). `preSendTerminate`, terminate çıkmadan önce ack'lenmemiş bir offer'ı yeniden deneme kuyruğundan düşürür.

### 5.2 Child'lar ve attribute'lar

| Eleman | Kaynak | Attribute'lar / içerik |
|--------|--------|------------------------|
| `<offer>` | send | `call-id`, `call-creator` (device JID'i); receive: `caller_pn`, `username`, `caller_country_code`, `group-jid`, `scheduled-id`, `joinable`, `lightweight` (`1` = lightweight / yalnızca sesli grup çağrısı), `rering_ts`, `is_call_ended`, `type` |
| `<audio>` (tekrarlanır) | send | `enc` (codec), `rate` (örnekleme hızı); `enc` ve `rate` sözlük token'larıdır |
| `<video>` | send | `enc`, `dec`, `device_orientation`, `screen_width`, `screen_height`; motorda görülen değer string'leri: `h.264`, `vp8`, `vp8/h.264`; `fps` attribute'u da string olarak mevcut (inferred video attribute'u) |
| `<net>` | send | `medium` (ağ türü), sonra transport içinde `health_status` |
| `<capability>` | send | `ver` + opak bit maskesi (`pjmedia_voip_capabilities_*`: sürüm, `bit_mask_length`); cihaz başına `vid_dec` string'i çözülebilen video codec'lerini listeler (`vid_codec_capability_str_to_bitmask`) |
| `<encopt>` | send | `keygen` = anahtar üretim sürümü; motor diğer değerleri reddeder (`Unsupported keygen ver`); 2 ve 3 sürümleri var (bölüm 6.4) |
| `<destination>` / `<to jid>` / `<enc>` | send | cihaz başına şifrelenmiş çağrı anahtarı (bölüm 6.1); `<to>` `peer_recipient_lid`, `peer_recipient_pn`, `peer_recipient_username`, `eph_setting` taşıyabilir |
| `<tctoken>` | send | `<to>` içinde, kullanıcı başına en fazla bir kez, flag **20605** açıkken ve henüz bir tane taşıyan kullanıcı sayısı **20606**'dan azken; [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) ile aynı token ailesi |
| `<device-identity>` | send | ADV imzalı kimlik baytları, bkz. 5.1 adım 3 |
| `<privacy>` | receive | privacy token'ı (token adı sözlükte mevcut); içeriği izlenmedi |
| `<relay>` | receive / ack | relay listesi (bölüm 8) |
| `<voip_settings>` | receive / ack | sunucunun verdiği motor parametreleri; attribute `uncompressed`; sıkıştırılmış payload'lar bir yolda reddedilir (`unexpected compressed voip params`) ve `zlib inflate` bağlıdır (sıkıştırma formatı inferred) |
| `<metadata>` | receive | peer A/B test bucket attribute'ları (`peer_abtest_bucket`, `peer_abtest_bucket_id_list`) |
| `<silence reason>` | receive | offer sessiz (zil yok); `BQU.A02`; neden int'leri `kOfferSilenceReason*` (bölüm 13) |
| `<group_info>` | receive | grup çağrısı katılımcı listesi (bölüm 9) |
| `<terminate_hint>` / `<call_summary>` | receive | zaten bitmiş bir çağrının offer'ı (`is_call_ended=1`): `terminate_reason`, transaction id, özet |
| `<link_info>`, `<waiting_room>`, `<bot>`, extension info | receive | bağlantı, bekleme odası, bot ve extension verisi |

`<capability>` ve `net medium` kodlarının tam bayt değerleri bu build'den çıkarılamadı (web istemcileri için bazen 7 baytlık `01 05 F7 09 E4 BB 13` maskesi anılır; Android kütüphanesinde bitişik bir literal olarak yok, bu yüzden Android değerini unknown say). Motor, string'lerde adını verdiği codec'leri içinde taşır: Opus ve ek olarak şirket içi düşük bit hızlı bir codec ("mlow", Opus çerçeveli), OpenH264, VP8, AV1 (`wzav1`) ve MediaCodec üzerinden HEVC.

### 5.3 Alma yolu (found)

1. `CallStanzaHandler` `BQU` oluşturur; metrik `CallStanzaHandler/handleStanza tag=... callId=...`; mesaj 192 dispatcher'a gönderilir.
2. Bir offer için `preprocess_call_offer` `nativeParseXmppOffer` çalıştırır; sıfırdan farklı dönüş stanza'yı düşürür. Süresi dolmuş veya bitmiş offer'lar çaldırılmaz.
3. `C83.A00` `<enc>` çözer (bölüm 6.2), sonra `nativeHandleIncomingXmppOffer` çağrıyı başlatır; durum `RECEIVED_CALL`.
4. `peekIncomingOffer` (push güdümlü ön kontrol) sessize alınmış offer'ları, grup offer'larını (`group_info` mevcut), `is_call_ended=1` offer'ları, `<enc>` içermeyen 1:1 offer'ları ve telefon meşgulken gelen offer'ları yok sayar; flag **4217** bit 1 sesli peek'leri, bit 2 görüntülü peek'leri etkinleştirir.
5. Sonraki bir `terminate` veya push `handleIncomingTerminatePush` bir peek'i bitirir.

---

## 6. Çağrı anahtarı ve şifrelenmesi

### 6.1 Giden (found, `getBulkEncryptedE2EKeys`)

Motor, device JID'den ham çağrı anahtarı baytlarına bir map verir. Bekleyen pre-key işi olmayan her cihaz için istemci bir `Message` protobuf oluşturur ve mevcut pairwise oturumla Signal ile şifreler (`C83` / `CallableC29363Coo`):

| Message.Call alanı | Numara | Tür | Ne zaman ayarlanır |
|--------------------|--------|-----|--------------------|
| `callKey` | **1** | bytes | her zaman (32 ham bayt) |
| `conversionSource` / `conversionData` / `conversionDelaySeconds` | **2** / **3** / **4** | string / bytes / uint32 | CTWA verisi mevcut |
| `ctwaSignals` / `ctwaPayload` | **5** / **6** | string / bytes | CTWA verisi mevcut |
| `contextInfo` | **7** | ContextInfo | CTWA flag'i (`externalAdReply.adType` sabit bir değere ayarlanır) |
| `nativeFlowCallButtonPayload` | **8** | string | çağrı bir native-flow düğmesinden başlatıldı |
| `deeplinkPayload` | **9** | string | çağrı bir deeplink'ten başlatıldı |
| `messageContextInfo` | **10** | MessageContextInfo | `AbstractC30999De0` ile peer başına zenginleştirme (içerik izlenmedi) |
| `callEntryPoint` | **11** | uint32 | flag **24935**, yalnızca ilk fanout'ta (`i == 0`) |
| `callReason` | **12** | string | proto'da var, bu yolda ayarlanmıyor |

`Message.call`, `Message` içinde (`C30628DTw`) alan **10**'dur, `Message.Call` sınıfı = `C25827BCl`. İlk offer için flag **520**, CTWA çözücüsünden (`C35832FfR`; inferred) reklam-atıf bağlamı ekler. Fanout, offer'larda `i == 0`, rekey'lerde `i == 1` ile çalışır. Şifreleme iptal yolu olan bloklayıcıdır; 5000 ms üzerindeki bir blok `voip_e2e_encryption_blocked` loglar.

Bir cihazın wire biçimi (found, `AbstractC33466EhY.A03/A09`): `<enc v="<version>" type="msg|pkmsg|skmsg|frskmsg|msmsg" [count="<retry>"] [mediatype] [session_type="pq"] [bucket]>CIPHERTEXT</enc>`. `session_type="pq"` post-quantum Signal oturumunu işaretler; `count` 0 iken atlanır. Çağrı anahtarları bu yolda hiçbir zaman grup sender-key mesajı değildir (`skmsg` türü yardımcı tarafından kabul edilir ama hiçbir çağrı yolu onu üretmez; inferred).

Extension cihazları (JID user öneki `01`) `sendReKeyToExtension` kullanır: önceden tamponlanmış bir prekey bundle işlenir, anahtar `v="2"` ile `pkmsg` olarak şifrelenir (found).

### 6.2 Gelen (found, `C83.A00`)

| Adım | Ayrıntı |
|------|---------|
| okunan child'lar | `registration` (4 bayt olmalı, Signal registration id'si, retry için kullanılır), `device-identity`, `enc` |
| yinelenenler | ikinci bir `<enc>` düşürülür (`duplicate <enc>`) |
| retry sayısı | `<enc>` üzerinde `count`; eksik değer işlemi iptal eder (`invalid retry count`) |
| tür | `msg` 0 veya `pkmsg` 1 kabul edilir; diğer numaralar `unrecognized ciphertext type` loglar |
| decrypt | pairwise Signal decrypt (pre-key mesajı göndericinin device kimliğiyle işlenir); payload `Message` olarak ayrıştırılır, `call.callKey` alınır; CAWC'nin `ExternalAdReplyInfo.adType` değeri loglanır |
| sonuç | `<enc>`, motor için çağrı anahtarı baytlarını tutan düz bir `<enc>` node'u ile değiştirilir |
| hata | `rejectedDecryptionFailure` olayı, `onPeerE2EDecryptionFailed` oturum kurulumunu yeniden dener (registration id eşitse ve base key tekrarlıyorsa yeni bir pre-key çek); çağrı çözülemediğinde reject nedeni `enc` gönderilir |

Flag **24063**, hosted türü ciphertext'ler için kullanılan oturum türü yolunu değiştirir (`c33281EeX.A04` koşulundan inferred).

### 6.3 Retry

`sendOfferRetryRequest(device)` motorun offer'ı yeniden göndermesini sağlar (`resendOfferOnDecryptionFailure`); `sendPendingRekeyRequest`, saklanan retry baytı 0..4 aralığındayken bir rekey isteğini tekrarlar. Dolayısıyla `count` 0 ile 4 arasındadır (found, `sendPendingRekeyRequest`).

### 6.4 `enc_rekey`: üç biçim

| Biçim | Kanıt | İçerik |
|-------|-------|--------|
| v2 unicast | `sendReKeyStanza` (Java) | motor `<enc_rekey call-id call-creator transaction-id><enc count=N>RAW KEY</enc></enc_rekey>` yayınlar; Java child'ı hedef cihaz için Signal ile şifrelenmiş `<enc>` ile değiştirir (found) |
| v2 fanout | `sendReKeyFanoutStanza` | hedef bir gruptur; child `<destination><to jid><enc/></to>...`; her giriş ayrı şifrelenir (found) |
| v3 | native string'ler `handle_enc_rekey_v3`, `make_and_send_rekey_v3`, `ext_rekey: ...` | payload, tekrarlanan `wa.voip.RekeyKeyEntry` (anahtar türü + anahtar) içeren bir protobuf'tur; tür başına anahtarların sabit uzunluğu vardır (`key type %d has unexpected length`); keygen 3 olduğunda seçilir; extension desteği gerektirir (`kCallExtensionMV1`); v3'ten v2'ye geçiş loglanır |

String'lerde görünen kurallar: rekey'ler transaction id taşır; erken, eski veya eşit id'ler yok sayılır (`ignore old rekey msg with transaction id`); bire bir çağrıda gelen `enc_rekey` yok sayılır (`ignore rekey msg in one to one call`); `request_keys`, creator'dan veya bir extension'dan anahtarları yeniden göndermesini ister (yalnızca v3; `request_keys with unexpected keygen` yok sayılır). Bir grup çağrısında rekey'i hangi tarafın başlattığı ve tam tetikleyici çözülemedi.

---

## 7. Medya anahtarı türetimi

### 7.1 Java callback'leri (found)

| Callback | Hesaplama |
|----------|-----------|
| `generateE2EKeysV2(callKey[32], out[46], info)` | HKDF-SHA256, salt = 32 sıfır bayt, IKM = çağrı anahtarı, info = motorun verdiği UTF-8 `info` string'i, 46 bayt çıktı (`E2E_EXTENDED_V2_KEY_LENGTH`) |
| `hkdfSha256(salt, ikm, info, out)` | genel HKDF-SHA256 (birinci arg salt, ikinci IKM, üçüncü info; çıktı uzunluğu = `out.length`) |
| `getSecureSsrc(ikm, info, salt[4], out[4])` | 4 bayta HKDF-SHA256 (`SECURE_SSRC_LENGTH`) |
| `hmacSha256(key, data, out[32])` | HMAC-SHA256 |
| `generateRandomBytes(out)` | `SecureRandom` (32 baytlık çağrı anahtarının kaynağı; inferred) |

### 7.2 Motordaki etiketler ve bağlamlar (found string'ler, rol inferred)

`e2e sframe key`, `hbh srtp key`, `uplink hbh srtcp key`, `downlink hbh srtcp key`, `warp auth key`; fonksiyonlar `derive_sframe_key`, `derive_hbh_srtp_key`, `derive_and_update_warp_mi_keys`, `derive_extension_per_media_key`; anahtar slotları `owner_e2e_key`, `extension_audio_key`, `extension_video_key`, `extension_appdata_key`.

| Anahtar | Kaynak (inferred) | Neyi korur |
|---------|-------------------|------------|
| E2E SRTP materyali | `generateE2EKeysV2` çıktısı (46 bayt), katılımcı başına | uç noktalar arası medya (1:1) |
| SFrame anahtarı | etiket `e2e sframe key` | grup / SFU çağrılarında kare şifreleme ve hop-by-hop veri kanalı (`wa_sframe_encrypt`, `sframe_keyprovider_set_chainkey`) |
| hop-by-hop SRTP / SRTCP | `hbh ...` etiketleriyle relay'in verdiği `hbh_key` (bölüm 8.2) | yalnızca istemci-relay bacağı |
| WARP MI anahtarı | etiket `warp auth key` | WARP paketlerinin mesaj bütünlüğü etiketi (`warp_mi_tag_len`) |

Anahtar yerleşimleri (46 baytın hangisi anahtar, hangisi salt, yön başına), `info` string içeriği ve SFrame / hop-by-hop için tam HKDF zincirleri çıkarılamadı: çağıranlar decompile edilemeyen native koddadır. `info` olarak cihaz nitelikli bir JID makuldür ama doğrulanmadı (**unknown**).

---

## 8. Relay, taşıma ve medya yolu

### 8.1 İstemcinin aldığı

Relay verisi offer ack'inde (arayan; `error during parsing relay info`, `Failed to parse relay info in offer ack`), offer'ın kendisinde (callee) ve daha sonra `relay_info_update` içinde ve bir `video` durum değişikliğinin ack'inde gelir (found).

### 8.2 `<relay>` gramer (found, `fill_relay_info` string'leri)

| Öğe | Ad | Notlar |
|-----|----|--------|
| relay attr'ları | `uuid`, `self_participant_uuid`, `conn_id`, `medium`, `warp_mi_tag_len`, `prefer_relay`, `prefer_ipv6`, `peer_dl`, `smart_transport_signal`, `attribute_padding` | relay kümesi başına |
| token'lar | `<token>` (`token_id`) listesi, en az biri zorunlu (`relay_token_list.num_tokens < 1`) | relay kimlik bilgisi; liste allocate isteğine kopyalanır |
| auth token'lar | `<auth_token>` (`auth_token_id`) | id aralık içindeyse token yerine kullanılır; aksi halde "falling back to relay token" |
| key | `<key>` | relay parola materyali |
| `hbh_key` | ham veya base64 baytlı child | hop-by-hop anahtar kaynağı; boyut kontrol edilir (`HBH Key of unexpected size`, "though warp_mi_tag_len = ...") |
| uç noktalar | `<te>` veya `<te2>` | asla ikisi birden değil (`can not receive both te and te2 endpoints`); adres baytları IPv4 veya IPv6 (`endpoint too short for an IPv6 address`); boş adres reddedilir |
| uç nokta başına | `relay_id`, `relay_name` (çok uzunsa kısaltılır), `domain_name`, `latency`, `c2r_rtt`, `ul_bw`, `dl_bw`, `is_favored` | `latency` relay seçimini besler |
| katılımcılar | `<participant pid jid>` | WARP / SFU paketlerinde kullanılan katılımcı id'lerini eşler |

Log string'leri relay adreslerini `[MetaServiceIP]` yer tutucusuyla basar; bu yüzden relay adresleri servis IP'si olarak ele alınır.

### 8.3 Relay seçimi (found string'ler, mantık inferred)

1. İstemci sunulan relay'lere bağlanır (`wa_transport_p2p_start_relay_binds`; bind / alloc istekleri STUN tarzıdır, `wa_stun_*`, transaction id'leri `tid=0x...`; bind ve unbind mesaj bütünlüğü gerektirir).
2. Gecikme, relay başına ping istekleriyle (`Ping request sent to relay N`), bir TCP prober'ıyla (`wa_transport_tcp_prober_*`) ve allocate gidiş-dönüşleriyle ölçülür; en iyisi "elected relay" olur (`Elected relay idx=...`, `wa_transport_get_elected_relay_approximate_e2e_rtt`); bir arbiter (`wa_transport_path_arbiter_*`) yol değiştirir ve `prefer_relay` relay kullanımını zorlar.
3. Allocate yanıtından öğrenilen server reflexive adres loglanır (`Server reflexive addr`).
4. Peer-to-peer, aday çiftleriyle paralel denenir (`p2p add_cand_pair`, `e2e bind probe`); relay yedek olarak kalır.

### 8.4 `relaylatency` (found)

Serializer'lar ve işleyiciler: `serialize_relay_latency`, `send_or_enqueue_relay_latency`, `handle_relay_latency`, `unpack_and_apply_relay_latency`, toplu (`prepare_batched_relay_latencies`), ack ayrıştırma `relaylatency ack: call_id is empty / has invalid type` ile. Stanza, göndericinin relay indeksi başına ölçtüğü RTT'yi peer'e bildirir; peer onu uygular (`apply_relay_latencies`, eşikler `Ignored higher relay latency ...`). Grup çağrısı offer'larında gecikme atlanır (`Skip relay latency at call offer in group calls`).

### 8.5 `transport` (found string'ler)

Attribute'lar ve child'lar: `transport-message-type`, `p2p-cand-round` (yeniden başlatma turu artırır ve uzak adayları temizler), `ice-ufrag`, `ice-pwd`, `<certificate algorithm fingerprint>` (`cert_algorithm`, `cert_fingerprint`), `health_status`, aday girişleri (adres, öncelik). `Web P2P: skipping type 13 send` string'i, mesaj türü 13'ün web-P2P ICE / DTLS alışverişine ait olduğunu gösterir. Diğer alt tür numaraları çıkarılamadı (**unknown**).

### 8.6 İki medya yolu

| Yön | WhatsApp relay yolu (varsayılan) | web-P2P yolu |
|-----|----------------------------------|--------------|
| Kurulum | relay allocate / bind (STUN tarzı), sinyalleşmeden gelen token'lar | ICE kimlik bilgileri ve DTLS sertifika parmak izi `transport` içinde değiş tokuş edilir; `wa_ice_transport`, `CreateDtlsTransport` |
| Paket biçimi | RTP payload'lı WhatsApp paketleri ("WARP", `warp_mi` bütünlük etiketi, piggyback, FEC, `warp_rtx`) | DTLS-SRTP üzerinden RTP |
| Hop anahtarı | relay `hbh_key` (hop-by-hop SRTP / SRTCP, relay'e hop-by-hop DTLS `hbh_dtls_handshake_*`) | DTLS'ten türetilmiş |
| E2E | 1:1'de E2E SRTP, grupta SFrame (SFU) | SRTP |
| Amaç | normal uygulamadan uygulamaya çağrılar | web istemcisiyle birlikte çalışabilirlik (`set_peer_is_web`, `handle_transport_web_p2p`); inferred |
| TLS yığını | statik bağlı mbedTLS (`mbedtls_ssl_*`, `mbedtls_gcm_*`, `mbedtls_hkdf`) | aynı |

Grup çağrıları, peer başına yollar yerine abonelikli bir SFU kullanır (`RxSubscriptions`, `SenderSubscriptions`, veri kanalı içinde `wa.voip.*` protobuf'ları); bant genişliği tahmini yol başına çalışır (`wa_warp_sfu_*`, "one side BWE").

---

## 9. Grup çağrıları

### 9.1 `group_info` (found, `shared_elements/group.rs` string'leri)

| Öğe | Ad | Notlar |
|-----|----|--------|
| attr'lar | `connected-limit`, `phash`, `transaction-id`, `media`, `joinable` | katılımcı listesi hash'i ve sıralama id'si; `group_info has invalid connected_limit` |
| üyeler | `<user jid [user_pn push_name guest_name account_kind state ..]>` ve `<device jid ..>` child'ları, veya `<participant jid pid>`; `<bot jid>` | `<user>` ve `<participant>` birlikte hatadır |
| kullanıcı başına | `state`, `pid`, `capability` (`ver`), `rekey`, `terminated`, `connected`, `country_code`, `reason` | nack'lenmemiş kullanıcılar için cihaz listeleri zorunlu |
| extension'lar | `extension_creator`, `ext_creator_identity_key_sig`, `extension_id`, `hn_video`, `gen`, `cohost`, `scope` | extension / co-host verisi |

### 9.2 Davranış

- Sınır `Voip.kMaxSupportedGroupCallParticipants` = 64 (found); güncellemesi maksimumu aşan bir çağrıyı motor sonlandırır.
- `group_update` ve grup çağrısı `terminate` transaction id taşır; eski veya sıra dışı olanlar yok sayılır; `kInitialGroupTransactionId` = -1 (found).
- Grup offer'ı cihaz başına çağrı anahtarı taşımaz; anahtarlar `enc_rekey` ile cihaz başına yeniden paylaşılır (`sendReKeyFanoutStanza`'dan inferred).
- Çaldırma ve katılımcı listesi action'ları: `invite`, `inviteToGroupCall`, `cancelInviteToGroupCall`, yeniden çaldırma (`rering_ts`, `make_and_send_cancel_offer_for_participants`), `sendRaiseHand`, `sendMutePeerRequestInGroupCall`, `sendRemoveRequest`; `lobby`, süren bir grup çağrısının katılım adımıdır (`joinOngoingCall`).
- Extension'lar: `add_extension` / `remove_extension` bir çağrıya ikinci bir medya uç noktası ekler (`wa_call_extension_jid_*`, sahip ve extension anahtarları 7.2'de, `kCallExtensionMV1`; Java, user öneki `01` olan extension JID'lerine özel davranır, 6.1). Cihaz sınıfı çözülemedi (inferred: eşleştirilmiş bir giyilebilir cihaz, uygulama `libsmartglasses-bundle.so` ve `Voip.sendWearableAttribution` taşıyor).

---

## 10. Çağrı bağlantıları, bekleme odası, zamanlanmış çağrılar

### 10.1 Bağlantılar (found)

| Öğe | Değer |
|-----|-------|
| URL | `https://call.whatsapp.com/{voice|video}/{token}`; manifest host'u `call.whatsapp.com` |
| token uzunluğu | `Voip.kCallLinkTokenLength` = 22 |
| create | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` (log `actionCreateCallLink` / `actionCreateCallLinkForEvent`); native `wa_call_link_create_v2` hatalı başlangıç zamanını reddeder |
| edit / preview | `editCallLink(token, ..., startTime, int)`, `previewCallLink`, `queryCallLinkForLinkEdit`; stanza'lar `link_edit`, `link_query` |
| join | `joinCallLink` `link_join` gönderir; ack `LinkJoinAck` `call-creator`, `group_info`, `voip_settings`, bağlantı bilgisi taşır |
| bağlantı durumları | `kCallLinkState`: None 0, QuerySent 1, QueryAcked 2, JoinSent 3, JoinAcked 4 |
| `CallLinkInfo` | creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self |
| nack olayları | ack hata koduyla `linkCreateNacked`, `linkQueryNacked`, `linkJoinNacked`, `linkEditNacked` |

Bağlantı stanza'ları bir çağrı alan adı JID'ine gönderilir (Rust JID ayrıştırıcısı `callDomainJID` ve `callJID` listeler; `C0DZ.A0R` tarafından kabul edilen ve ona karşılık gelen JID türü çözülemedi).

### 10.2 Etkinlik (zamanlanmış) çağrıları

Etkinlik çağrısı, sıfırdan farklı `eventStartTimeSec` ile oluşturulan bir çağrı bağlantısıdır (found). Zamanlanmış bir çağrının offer'ı `scheduled-id` taşır (ayrıştırıcıda bulundu). `Message` iki sohbet mesajı taşır:

| Message alanı | Numara | Tür | İçerik (found) |
|---------------|--------|-----|----------------|
| `scheduledCallCreationMessage` | **61** | ScheduledCallCreationMessage | `scheduledTimestampMs` 1, `callType` 2 (UNKNOWN 0, VOICE 1, VIDEO 2), `title` 3 |
| `scheduledCallEditMessage` | **65** | ScheduledCallEditMessage | `key` 1 (MessageKey), `editType` 2 (UNKNOWN 0, CANCEL 1) |

Edit olarak yalnızca cancel var. Yerel depolama (found): tablolar `message_scheduled_call` (`scheduled_timestamp_ms`, `call_type`, `title`), `message_add_on_scheduled_call_edit` (`creation_message_row_id`, ...), `message_system_scheduled_call_start` (`call_title`, `call_timestamp_ms`), `scheduled_calls` (`key_chat_row_id`, `key_id`, `scheduled_timestamp`, `is_upcoming`, `call_log_row_id`). Sunucu tarafı hatırlatıcı (bir `reminder` call child'ı, aşağıda `kServerReminder*`) ve oluşturma mesajının çağrı bağlantısı token'ına nasıl bağlandığı çözülemedi.

### 10.3 Bekleme odası

Stanza'lar `waiting_room_toggle` (`link-token`, `media`, `enabled`, aktif çağrı varyantı), `_admit`, `_deny`, `_leave`, `_update`; ayrıştırılan kullanıcı alanları `jid`, `user_pn`, `push_name`, `guest_name`, `is_guest_eligible`, `state`. Java: `waitingRoomAdmit`, `waitingRoomAdmitAll`, `waitingRoomDeny`, `waitingRoomToggle`; olaylar `waitingRoomAdmitAcked`, `waitingRoomDenyAcked`, `waitingRoomStateChanged`, `waitingRoomDenied`. `kServerReminder`: Legacy 0, LinkJoinedCreator 1, LinkJoinedJoiner 2, LinkConnectedCreator 3, LinkMissedCreator 4, LinkCreatorWaitingRoomJoined 5, LinkCreatorWaitingRoomMultipleJoined 6.

---

## 11. bcall, bot ve alternatif taşıyıcılar

### 11.1 `bcall` sohbet mesajı (found)

| Alan | Numara | Tür | Kullanım |
|------|--------|-----|----------|
| `sessionId` | **1** | string | business-call oturumu |
| `mediaType` | **2** | enum | UNKNOWN 0, AUDIO 1, VIDEO 2 |
| `masterKey` | **3** | bytes | zorunlu: eksik anahtar `bcall message doesn't have master key` fırlatır |
| `caption` | **4** | string | isteğe bağlı |

`Message.bcallMessage` = alan **72** (sınıf `DSA`); işleyici `F2V` (`FMessageBCallProtobuf`) onu oturum id'si, medya türü (0 unknown, 1 audio, 2 video), caption ve master key baytlarıyla mesaj türü 91'e eşler. `master key`, uçtan uca şifreli bir sohbet mesajı içinde teslim edilen bir anahtardır; neyi anahtarladığı (inferred: bir business çağrısının medyası) izlenmedi. Motor olayları `bCallCreated(callId, key, ...)`, `bCallJoined`, `bCallEnded`, `bCallAudienceUpdated`, `bCallCreateFailed`; `CallState.BCALL_STARTING`; gelen `<call>` child'larından `bcall_*` adlıları boş call id alır (3.2). Native `bcall_start`, `bcall_notify` string'leri var.

### 11.2 Bot çağrıları ve HTTP / TEE sinyalleşme

Bot çağrıları: `CallInfo.isBotCall`, `group_info` içinde `<bot>` node'ları, `verifyIncomingBotIdentityKey`, `reconfigure_bot` (`req_id`), bot TOS akışı (nack 488); offer, önbelleğe alınmış bir payload oluşturucuyla birleştirilir. Bağlam: [WA_META_AI.md](WA_META_AI.md). Ayrıca `SignalingHttpCallback.sendMsg`, motorun chatd yerine `TeeRequestHandler` üzerinden opak sinyalleşme baytları alışverişi yapmasını sağlar (`handle_http_tee_start_session_response`, `handle_http_create_extension_response`); istek türleri voice session ve codec avatar. Uygunluk ve payload formatı **unknown** (inferred: bot ve avatar oturumları).

---

## 12. Çağrı kaydı ve geçmiş

### 12.1 `callLogMesssage` (Message alanı **69**, sınıf `C49434Loq`, found)

| Alan | Numara | Tür | Değerler |
|------|--------|-----|----------|
| `isVideo` | **1** | bool | |
| `callOutcome` | **2** | enum | CONNECTED 0, MISSED 1, FAILED 2, REJECTED 3, ACCEPTED_ELSEWHERE 4, ONGOING 5, SILENCED_BY_DND 6, SILENCED_UNKNOWN_CALLER 7 |
| `durationSecs` | **3** | int64 | |
| `callType` | **4** | enum | REGULAR 0, SCHEDULED_CALL 1, VOICE_CHAT 2 |
| `participants` | **5** | repeated `CallParticipant` | `jid` 1 (string), `callOutcome` 2 (aynı enum) |

Oluşturucu `C53129Nna` (found): motorun çağrı kaydı sonucu (`Voip.kCallLog*`) şöyle eşlenir.

| `kCallLog` sonucu | Wire `callOutcome` |
|-------------------|--------------------|
| Canceled 1, Missed 2 | MISSED |
| Unavailable 3 | FAILED |
| Rejected 4 | REJECTED |
| Connected 5 | CONNECTED |
| AcceptedElsewhere 6, ScreenedElsewhere 9 | ACCEPTED_ELSEWHERE |
| Invalid 0, Failed 7, ConnectedLonely 8, diğerleri | ONGOING (decompile edilmiş varsayılan dal) |
| kayıttaki DND flag'i / bilinmeyen arayan flag'i | SILENCED_BY_DND / SILENCED_UNKNOWN_CALLER (önce kontrol edilir) |

Failed 7'nin ONGOING'e eşlenmesi yanlış görünür ama decompile edilmiş varsayılan daldır; okunduğu gibi ele al, doğrulanmış davranış olarak değil. Çağrı türü: yerel tür 1 SCHEDULED_CALL'a, 2 veya 3 VOICE_CHAT'e eşlenir, aksi halde REGULAR. Eksik çağrı türü `call log message missing call_type` fırlatır.

### 12.2 Yerel veritabanı (found)

Tablolar: `call_log` (`jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch`), `call_log_participant_v2` (`call_log_row_id`, `jid_row_id`, `call_result`), `joinable_call_log` (`call_id`, `joinable_video_call`, `group_jid_row_id`, `phash_identifier`, `self_other_device_connected`, `is_lgc_add`), `message_call_log`, `call_unknown_caller`, `reminder`. Besleyen olaylar: `callEnding(CallLogInfo, ..)`, `update1to1CallLog`, `updateJoinableCallLog` (`kUpdateJoinableCallLogType` Create 1, Update 2, Delete 3).

---

## 13. Motor durumları ve sabitler (found, `Voip.java`, `CallState`)

| Grup | Değerler |
|------|----------|
| `CallState` | NONE, CALLING, PRE_ACCEPT_RECEIVED, RECEIVED_CALL, ACCEPT_SENT, ACCEPT_RECEIVED, ACTIVE, ACTIVE_ELSEWHERE, REJOINING, LINK, CONNECTED_LONELY, PRECALLING, ENDING, BCALL_STARTING, SCREENING |
| `kCallLog*` | Invalid 0, Canceled 1, Missed 2, Unavailable 3, Rejected 4, Connected 5, AcceptedElsewhere 6, Failed 7, ConnectedLonely 8, ScreenedElsewhere 9 |
| `kCallEndReason*` | Unknown 0, Timeout 1, Self 2, RejectDoNotDisturb 3, RejectBlocked 4, MicPermissionDenied 5, CameraPermissionDenied 6 |
| `kFatalReason*` | Unknown 0, ParticipantAllocationFailure 1, CallSetupError 2, CallTxTimeout 3, CallRxTimeout 4, VideoStreamCreateError 5, VideoPortCreateFailed 6, NoSamplingRatesForAudioRecord 7, AudioInitError 8 |
| `kOfferSilenceReason*` | None 0, Privacy 2, Lightweight 3, ScreenSharing 4, AddedAsLinkCreator 9, AddedForDeviceSwitching 10, GroupChatAdd 11 |
| `kParticipant*` | Connected 1, Incoming 2, Ringing 3, Rejected 4, Terminated 5, TimedOut 6, CreatingCall 7, Invited 11 |
| `kVideoState*` | Disabled 0, Enabled 1, Paused 2, UpgradeRequest 3, UpgradeAccept 4, UpgradeReject 5, Stopped 6, UpgradeRejectByTimeout 7, UpgradeCancel 8, UpgradeCancelByTimeout 9, UnknownPeer 10, Xr2dCodecAvatarEnabled 12, Error 20 |
| `kStatus*` | Success 0, InvalidArgument 70004, Exists 70015, Ignored 70020, CallAlreadyStarted 670001, CallNotActive 670007, CallHasNoVideo 670018, GroupCallUserExists 670021, GroupCallPeerCodecMismatch 670033, GroupCallUserExistsNotInvited 670038, NotPermitted 670040, UserNotRemovable 670041, UserNotConnected 670042 |
| `kScreenShareVersion*` | Legacy 0, 1 ile 4 arası |
| `kNetworkHealth*` | Measuring 0, NoNetwork 1, Poor 2, Average 3, Good 4 |

`kCallEndReason` int'leri UI'nin gördüğüdür; terminate için wire'a konan string'ler kütüphane string'leri arasında yoktur (14.3).

---

## 14. Hatalar, reject, terminate

### 14.1 Offer nack kodları (found, `VoiceServiceEventCallback.callOfferNacked`)

Hatalı bir offer ack'i `callOfferNacked(errors[])` çağırır. Tek bir 304 veya 400 hatası yinelenen offer sayılır ve yok sayılır. Nack, çağrı `CALLING` / `CONNECTED_LONELY` durumundayken ve tüm alıcılar (veya self) nack'lendiğinde, ya da kod 432 olduğunda ölümcüldür; aksi halde alıcı başınadır ve ölümcül değildir.

| Kod | Ölümcül yol (decompile edilmiş dal) | Ölümcül olmayan yol |
|-----|-------------------------------------|---------------------|
| 401 | not-allowed ekranı (neden id 3) | |
| 403 | not-allowed ekranı, video ise videoya özgü id | |
| 404 | not-allowed id 16 | alıcı başına "contact unavailable" metni |
| 405 | id 4 | |
| 406 | id 2 (audio) / 11 (video) | |
| 411 | id 11, lightweight için 37 | |
| 412 | id 10; üyelik uyuşmazlığında grup bilgisi yenilenir | |
| 426 | id 1 (audio) / 9 (video) | |
| 427 | id 12, lightweight 1:1 için 36 | alıcı başına metin; 4'ten fazla katılımcılı gruplarda alternatif id |
| 428 | id 14 | alıcı başına metin |
| 429 | yalnızca UI olayı | |
| 431 | id 15 | "not available" metni |
| 432 | id 2; her zaman ölümcül | |
| 435 | | alıcı başına metin; offer ack'inden sonra ayrıca ek bir action tetikler |
| 460 / 463 | video 10 / audio 2; 463 id 17 | |
| 488 | bot TOS kabul edilmedi: bot TOS akışını açar | aynı |
| 467, 468, 469 | | birden fazla alıcı için id 46 |
| 500, 502 | | "not available" metni |
| 538 | | id 35 |
| diğer | varsayılan id (video 8 / 0) | assertion `Unknown error code` |

Decompile edilmiş ölümcül dal bazı return'leri kaybetmiştir, bu yüzden id'ler yalnızca gösterge niteliğindedir; kod listesi ve ölümcül / ölümcül olmayan ayrımı sağlamdır. Kodların istemci tepkisinin ötesindeki anlamları sunucu tarafındadır (**unknown**). Tam bir offer nack'inden sonra motor `terminate` dışında hiçbir çağrı stanza'sı göndermez (found string).

### 14.2 Reject nedenleri (found, `Voip.REJECT_REASON_*`)

| String | Anlam / istemci tepkisi |
|--------|-------------------------|
| `` (boş) | reddedildi |
| `busy` | callee meşgul; meşgul tonu, çağrı bir gecikmeden sonra biter |
| `unavailable` | sabit tanımlı; asıl kullanımı presence / uygunluk kodunda bulundu |
| `uncallable` | peer aranamaz; not-allowed ekranı |
| `tos` | peer TOS'u kabul etmedi; not-allowed ekranı |
| `enc` | çağrı anahtarının decrypt'i başarısız oldu |
| `server_conf_corrupted` | sunucu yapılandırması kullanılamaz |

`rejectCall(callId, reason, int)` ve `rejectPendingCall` giriş noktalarıdır; `callRejectReceived` gelen nedenleri tüketir. Reject nedenleri yerel çağrı sonuçlarına eşlenir (`reject_reason_to_call_result`, `set_call_term_reason_from_received_call_reject_reason`).

### 14.3 Terminate (found string'ler)

- `terminate` bir transaction id ve bir `call_summary` node'u (kullanıcı durumları, süre) taşır; bitmiş bir çağrının offer'ı `terminate_reason`, `call_summary` ve transaction id içeren `terminate_hint` taşır. `terminate`'in kendisinin bir `terminate_reason` attribute'u olup olmadığı çözülemedi.
- Bir companion cihazdan gelen terminate motor tarafından yok sayılır; birincil cihaz terminate'i multi-device peer'lere dağıtır (`fanout_terminate_if_peer_is_md`).
- Yanlış durumdaki bir cihaz değiştirme terminate'i yok sayılır; "handled elsewhere" sonuçları nedenden türetilir (`get_handled_elsewhere_outcome_from_terminate_reason`) ve aynı call id için çakışan sonuçlar yok sayılır.
- Medya yolundaki RTCP BYE de çağrıyı bitirir (`rtcp_bye_terminate_delay`), sunucu tarafı extension kaldırma da öyle (`extension terminated by server`).
- Java, flag **8003** açıkken ve çağrı bir bot çağrısı veya lonely durumunda değilken `terminate`'i retry ile gönderir (yeniden bağlanmalar boyunca kuyruğa alınır); aksi halde retry olmadan (dal decompile çıktısında kısmen belirsiz).
- Terminate `reason` string değerleri (ve `kCallEndReason`'dan herhangi bir eşleme) kütüphane string'lerinde yok ve APK'nın başka yerinde bulunamadı (**unknown**).

---

## 15. Feature flag'leri (id'ler çağrı noktalarında okunduğu gibi; adlar çözülmedi)

| ID | Tür | Neyi kontrol eder |
|----|-----|-------------------|
| **9257** | long ms | offer teslim zaman aşımı; zaman aşımında stanza düşürülür (`CIX.A02`) |
| **9431** | long ms | accept teslim zaman aşımı; ayrıca `preSendTerminate` iptal edebilsin diye accept stanza id'sini hatırlar |
| **9432** | bool | accept zaman aşımında yeniden bağlanmayı tetikler |
| **8003** | bool | retry ile terminate (14.3) |
| **15125** | bool | `call_stanza_drop` metriğini raporlar |
| **30890** | bool | offer sonrası giden-çağrı ping'i gönderir |
| **30891** | long ms | ping zaman aşımı, varsayılan 3000 |
| **32651** | int | ping deneme sayısı, minimum 1 |
| **31086** | bool | giden offer izleyicisi |
| **24935** | bool | `callEntryPoint`'i `Message.call` içine yazar |
| **520** | bool | `Message.call`'a reklam-atıf bağlamı ekler (inferred) |
| **20605** / **20606** | bool / int | çağrı hedeflerine `<tctoken>` ekler; stanza başına kullanıcı üst sınırı |
| **24063** | bool | bir ciphertext sınıfı için decrypt oturum türü seçimi (inferred) |
| **4217** | int mask | gelen offer'ları peek et: bit 1 sesli, bit 2 görüntülü |
| **3094** | int mask | bit 8 = async çağrı olayları (`kFlagEnableCallEventAsync`); **9210** (bool) ile eşli |
| **7481** | bool | bağlantılı grup çağrıları için grup çağrısı sessize alındı bildirim durumu |
| **13630** / **13804** | int / bool | bir decrypt metriği için örnekleme (inferred) |

Motor parametreleri (`p->enable_sframe_tx`, `tp->web_p2p_bitmap`, `tp->enable_e2e_bind_probe_bitmap`, `options.wa_log_time_series`, ...) sunucunun `voip_settings` verisinden gelir ve `Voip.getVoipParam` ile okunur; adları kütüphanedeki string'lerdir, değerleri sunucu tarafındadır.

---

## 16. Baileys (`baron-baileys-v2`, kaynak okundu, hiçbir şey test edilmedi)

| Konu | Baileys | Android |
|------|---------|---------|
| Offer | `offerCall`: rastgele 32 hex `call-id`, `call-creator` = kendi id'si, `<audio enc=opus rate=16000/8000>`, `<video enc=vp8 dec=vp8 ...>` (video), `<net medium=3>`, `<capability ver=1>` 6 bayt `01 04 FF 83 CF 04`, `<encopt keygen=2>`, Signal ile şifrelenmiş `Message{call{callKey}}` içeren `<destination>`, `count=0`, pkmsg üretildiğinde `device-identity` | aynı elemanlar; Android offer'ı motorda oluşturur, capability baytları unknown (5.2) |
| Zarf | offer için `<call id to>`; reject / accept / terminate `id` olmadan `from` + `to` kullanır | her zaman `<call to id>` (3.1) |
| accept | `<accept call-id call-creator count=0/>`, child yok | motor accept'i medya parametreleri ve bir sertifika taşır (bölüm 4) |
| terminate | `reason="user-terminated"`, `count=0` | reason string'leri unknown (14.3) |
| rekey | `<enc_rekey ...><enc v=2 type=msg/></enc_rekey>` | v2 biçimi 6.4 ile uyuşur; v3 yok |
| Gelen | `<enc>` çözer (`unpadRandomMax16`, `Message.decode`), offer'ı önbelleğe alır, çağrı olayları yayınlar; medya / relay tag'leri yalnızca ack'lenir | Android aynı zarfla decrypt eder ve motora besler |
| Bağlantılar | `@call`'a `link_create media` (+ `event start_time`); `waiting_room_toggle`; `link_join token` | gramer burada bulunan adlarla uyuşur; hedef JID türü çözülemedi |
| Terminate durumları | `terminate reason` string'lerini eşler: `Timeout`, `RejectDoNotDisturb`, `MicPermissionDenied`, `CameraPermissionDenied`, `RemoteBusy`, `RemoteOffline` | bu string'ler kütüphanede yok; adlar `kCallEndReason`'a benzer (**inferred** bağlantı) |

Baileys'te relay allocation, WARP / SRTP / SFrame ve motor yoktur; bu yüzden sinyalleşebilir ve çaldırabilir ama medya taşıyamaz. Tam motor parametreleri olmayan bir offer'ın peer tarafından kabul edilip edilmediği veya çaldırılıp çaldırılmadığı test edilmedi.

---

## 17. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-------|
| bir çağrı stanza'sı için `Wrong jid type` | `to` bir user / device / call-domain JID'i değil | device veya user JID'ine gönder |
| offer `without enc` gönderildi, peer çalmıyor | çağrı anahtarı şifrelenmedi (oturum yok, pre-key işi bekliyor) | önce oturumları kur; Android offer'ı bekletir |
| `duplicate <enc>` / `invalid retry count` / `invalid registration` | hatalı `<enc>`; `registration` 4 bayt değil | `count` ile tek `<enc>`; `registration` yalnızca retry'da |
| offer nack 304 / 400 | yinelenen offer | yok say |
| offer nack 401 / 403 / 463 | arayan bu peer'i arayamaz | istemcide yapılacak bir şey yok |
| offer nack 412 / 488 | grup üyeliği farklı / bot TOS kabul edilmedi | grup bilgisini yenile / bot TOS'u kabul et |
| reject `enc` | callee çağrı anahtarını decrypt edemedi | oturum onarımından sonra offer'ı yeniden gönder (`count` > 0) |
| `Unsupported keygen ver`, `can not receive both te and te2`, `num_tokens < 1` | geçersiz `encopt`, relay uç noktaları veya token'lar | keygen 2 veya 3 gönder, tek uç nokta ailesi, en az bir token |
| `bcall message doesn't have master key` | `masterKey` eksik | ekle |
| `Call stanza delivery timed out` | flag 9257 / 9431 içinde chatd ack'i yok | stanza düşürülür; accept yeniden bağlanabilir (flag 9432) |

---

## 18. Temel ayrımlar

| Karıştırma | Şununla |
|------------|---------|
| `Message.call` (alan 10, Signal mesajı içinde E2E çağrı anahtarı) | `callLogMesssage` (69, sonuç kaydı), `bcallMessage` (72, business oturum anahtarı) |
| Çağrı stanza'sındaki `<enc>` (pairwise Signal ciphertext) | `skmsg` sender-key mesajları ve medya şifrelemesi |
| E2E SRTP / SFrame anahtarları (çağrı anahtarından) | hop-by-hop anahtarlar (relay `hbh_key`'inden) |
| Relay `<token>` / `<auth_token>` (allocation kimlik bilgileri) | `<tctoken>` (`<to>` içindeki privacy token'ı) |
| `kCallEndReason` int'leri (UI), `kCallLog*` (motor sonucu) | terminate reason string'leri (wire, unknown), `callOutcome` enum'u (wire) |
| `CallLogMessage.CallType` REGULAR / SCHEDULED_CALL / VOICE_CHAT | `ScheduledCallCreationMessage.CallType` UNKNOWN / VOICE / VIDEO |
| `enc_rekey` v2 (Signal `<enc>` child'ı) | `enc_rekey` v3 (protobuf `RekeyKeyEntry` listesi) |
| WhatsApp relay yolu (WARP, hop-by-hop SRTP) | web-P2P yolu (ICE + DTLS-SRTP) |
| Etkinlik çağrısı (başlangıç zamanlı bağlantı) | zamanlanmış-çağrı sohbet mesajları (61 / 65) |
| chatd üzerinden sinyalleşme | bot ve avatar oturumları için HTTP / TEE sinyalleşme |

---

## 19. Tam akış (1:1 çağrı)

```
[Caller app]  startCall(callId, peer, video, ...)
     │
     ▼
[Native engine]  mints 32-byte callKey ; builds <offer> (audio, video, net, capability, encopt keygen)
     │  sendCallStanza(peer, callId, node)
     ▼
[OutgoingSignalingHandler]  per device: Message{call{callKey,...}} → Signal encrypt → <enc>
     │  <destination><to jid><enc/></to>…</destination> [tctoken] [device-identity if pkmsg]
     ▼
[CIX / writer]  <call to id><offer call-id call-creator>…</offer></call>     (delivery timeout, flag 9257)
     │
     ▼
[WA Server]  (not observed) enriches the offer: relay, voip_settings, metadata, privacy
     ├──────► [Caller]  offer ack: <relay> tokens, endpoints, hbh_key ; voip_settings ; or nack (14.1)
     ▼
[Callee]  <call from t e offline><offer/></call>
     │  CallStanzaHandler → nativeParseXmppOffer → C83 decrypt <enc> → callKey → ring (RECEIVED_CALL)
     ▼
[Callee]  preaccept ─► [Caller] PRE_ACCEPT_RECEIVED ;  accept (media params, certificate) ─► ACCEPT_RECEIVED
     │
     ▼
[Both engines]  relay allocate / bind with tokens ; transport / relaylatency / relay_info_update
     │  E2E keys from callKey (HKDF) ; hop-by-hop keys from hbh_key ; optional P2P pair or web_p2p DTLS
     ▼
[Media]  WARP packets via the elected relay or P2P ; ACTIVE ; in-call video, mute_v2, notify, heartbeat
     │
     ▼
[Either side]  terminate (transaction id, call_summary) ─► ack class="call" type="terminate"
     ▼
[Both]  callEnding(CallLogInfo) → call_log row / callLogMesssage ; teardown ; RTCP BYE
```

Grup çağrısı farkları: offer `group_info` taşır ve cihaz başına anahtar taşımaz; geç katılanlar `lobby` / `link_join` kullanır; rekey'ler transaction id'lerle `enc_rekey` olarak (v2 fanout veya v3) gider; medya SFrame ile bir SFU üzerinden akar.

---

## 20. Bilinmeyenler

| Öğe | Durum |
|-----|-------|
| Native stanza oluşturucuları / ayrıştırıcıları, HKDF `info` string'leri, anahtar yerleşimleri | voip kütüphanesi decompile edilmedi; yalnızca string'ler |
| Capability baytları, `net medium` kodları, codec parametre varsayılanları | çıkarılamadı |
| 13 dışındaki `transport-message-type` değerleri | çıkarılamadı |
| Terminate `reason` string'leri, reject'ten end-reason'a eşleme | bulunamadı |
| Zarf `e` anlamı, offer ack hata 435 yan action'ı | çözülemedi |
| 85 türlü sayısal mesaj-id tablosu | bu build'in string'lerinde yok |
| Extension cihaz sınıfı, v3 rekey tetikleyicisi, grup rekey tetikleyicisi | çözülemedi |
| Bağlantı-çağrısı JID türü, zamanlanmış çağrının token'a bağlantısı | çözülemedi |
| TEE / HTTP sinyalleşme payload'ı ve uygunluk | çözülemedi |
| Sunucu davranışı (zenginleştirme, nack anlamları, relay seçimi) | sunucu tarafı |
| Trafik | hiçbir şey yakalanmadı |
