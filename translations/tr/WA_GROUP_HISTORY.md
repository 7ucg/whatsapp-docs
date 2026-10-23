<!-- src-sha1: 0c8270cd51a33a8c9e23ceb0a6129e273e5cb070 -->
# WhatsApp Grup Geçmişi — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android'de grup geçmişi paylaşımı (yeni üyelere gönderilen son grup mesajları): yönetici ayarı `member_share_group_history_mode`, gönderici ve alıcı uygunluğu, ekleme / onay ile katılma akışı ve bekleyen job, mesaj seçimi ve limitler, `MessageHistoryBundle` (alan 70) ve `MessageHistoryNotice` (alan 102), iç `GroupHistory` proto'su, bundle medya şifrelemesi ve yükleme, alıcı tarafında doğrulama ve içe aktarma, grup metadata'sı (katılımcılar, LID ve PN adresleme, topluluk ilişkileri), sender-key kullanımı, reporting token'ları, eşlenmiş cihaz HistorySync'i (`HistorySyncConfig`, sync türleri, isteğe bağlı peer işlemleri), feature flag'ler, Baileys

---

## 1. Nedir (teknik olarak)

Grup geçmişi paylaşımı, bir grup üyesinin (yönetici veya yönetici izin verirse herhangi bir üye) yeni eklenen kişilere yakın tarihli grup mesajlarından oluşan bir bundle göndermesini sağlar; böylece yeni gelen bağlamı görür. Yükü bir medya dosyası (`WebMessageInfo` kayıtlarından oluşan bir protobuf) olan normal, uçtan uca şifreli bir grup mesajıdır. Her ikisi de "history" sözcüğünü ve birkaç capability flag'ini paylaşsa da eşlenmiş cihaz HistorySync'i **değildir** (bölüm 11).

Tüm ifadeler çözülmüş (decompile) APK'nın statik analizinden gelir; ağ üzerinde hiçbir şey yakalanmadı. Katmanlar: **found** = kodda veya kaynaklarda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi. Obfuscate edilmiş adlar 2.26.41.6'da kararlı string'lerden yeniden çözüldü (`FMessageGroupHistoryBundleProtobuf`, `GroupHistorySendPermissionChecker`, `PendingSendGroupHistoryJob`, `member_share_group_history_mode`, `Group History`).

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| Bundle mesajı | `C213539Ar` (`FMessageGroupHistoryBundle`), FMessage türü **117** | dış medya mesajı, `Message.messageHistoryBundle` alan **70** |
| Notice mesajı | `C213519Ap` (`FMessageGroupHistoryNotice`), FMessage türü **118** | "geçmiş gönderildi" satırı, `Message.messageHistoryNotice` alan **102** |
| Bundle serileştirici / ayrıştırıcı | `C34677F2y` (`FMessageGroupHistoryBundleProtobuf`) | dış mesajı oluşturur ve doğrular |
| Notice serileştirici / ayrıştırıcı | `C34678F2z` (`FMessageGroupHistoryNoticeProtobuf`) | notice'i oluşturur ve doğrular |
| Bundle oluşturucu | `C9mW.A00` (+ `C231239yy`, `FMessageGroupHistoryBundleFactory`) | seçer, paketler, dosyayı yazar, medya mesajını oluşturur |
| Mesaj seçimi | `A0G` (`GroupHistoryMessageManager`) | sayım ve satırlar için SQL |
| Uygunluk | `A1W` (`GroupHistorySendPermissionChecker`), `C230099x1` (gate'ler) | gönderici / alıcı / giriş noktası kontrolleri |
| Bekleyen job | `PendingSendGroupHistoryJob`, `SendGroupHistoryJobRequirement` | ekleme sonrası kalıcı job |
| Requirement provider | `C197318aR` (`SendGroupHistoryRequirementProvider`) | ekleme / onay olayları job'u serbest bırakır |
| Alıcı | `GroupHistoryBundleProcessor`, `GroupHistoryBundleFileProcessor` | indirir, ayrıştırır, ekler |
| Doğrulayıcılar / ekleyici | `C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg` (`GroupHistoryMessageValidator` / `GroupHistoryMessageInserter`) | mesaj başına kontroller ve DB'ye ekleme |
| Medya türü satırı | `C15530gU.A0F` | `group-history`, `GROUP_HISTORY`, HKDF info `Group History`, id **117** |
| Ayarlar arayüzü | `com.whatsapp.grouphistory.setting.ui.*`, `GroupPermissionsActivity` (`C201678ic`) | miktar diyaloğu, alt bilgi anahtarı, izin anahtarı |

Her paylaşım için iki ayrı mesaj vardır: **bundle** (veriyi taşır, gruba gönderilir) ve **notice** (yalnızca sayıları ve alıcıları taşır, bundle cihazdan çıktıktan sonra gönderilir, bölüm 5.4).

---

## 2. Grup metadata'sı ve ayarları

### 2.1 Grup bilgi node'u (`<group>`, eski XMPP yolu `C23201A1a.A0C`)

`w:g2` sorguları ve grup bildirimleri için aynı yardımcı tarafından ayrıştırılır; bir MEX/SMAX eşi de vardır (`AbstractC23204A1d`, `AN6`, `C23690AKd`). Yalnızca burada ve adresleme için ilgili alanlar:

| Öznitelik / alt node | Tür | Kullanım |
|-------------------|------|-----|
| `id`, `creation`, `subject`, `s_t`, `s_o`, `s_o_pn`, `creator`, `creator_pn` | öznitelikler | kimlik; `_pn` eşleri, LID'in yanında telefon JID'ini taşır |
| `addressing_mode` | `lid` veya `pn` | `wa_group_admin_settings.addressing_mode` içinde saklanır; `pn` dışındaki her şey `lid` olarak okunur (`AbstractC268510t`) |
| `<group_history/>` | boş alt node | boolean varlık; `history_enabled` olarak saklanır; anlamı inferred (grubun feature flag'i) |
| `<member_share_group_history_mode>` | metin | yönetici ayarı, 2.4 |
| `<member_add_mode>` | `all_member_add` / diğer | `member_add_mode` 1 / 0 |
| `parent`, `default_sub_group`, `linked_parent jid`, `general_chat` | alt node'lar | grup türü, 2.3 |

### 2.2 Katılımcılar ve adresleme (found)

`<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`):

| Öznitelik | Grup geçmişi için kullanım |
|-----------|-----------------------|
| `jid` | katılımcı, `addressing_mode`'a göre LID veya PN; `phone_number` özniteliği olan bir PN JID uyuşmazlık için kontrol edilir |
| `lid`, `phone_number` | diğer adres biçimi; JID eşleme deposu üzerinden saklanır |
| `join_time` | pozitif long (saniye, inferred); katılımcı başına saklanır; "çok önce katıldı" için temel |
| `group_history_sent` | `"true"` / `"false"`, Boolean; `group_participant_user.group_history_send_state` alanını besler (eşleme inferred, 3.2) |

Bundle metadata'sındaki alıcı ve gönderici listeleri (bölüm 6.2) JID string'leridir. Job bunları kullanmadan önce grubun adresleme moduna normalleştirir: `PendingSendGroupHistoryJob.A01`, grup LID adresliyse her alıcıyı **LID**'ine eşler (`C30194DBb.A05`), değilse LID'i PN'ye eşler (`C0YH.A0G` / `AbstractC197018Zw.A0Y`). Bir katılımcı eklendiğinde job her iki biçimi de kabul eder (`C0YH.A0J` karşılığını verir), böylece requirement kümeleriyle eşleşir. Ağ üzerinde hangi biçimin bulunduğu grup moduna bağlıdır (eşleme kodundan inferred).

### 2.3 Topluluk ve üst grup ilişkileri

`C23201A1a.A01` bir grup node'unu sınıflandırır: **0** normal, **1** topluluk üst grubu (`parent`), **2** bağlı alt grup (`linked_parent`), **3** varsayılan alt grup (`default_sub_group`), **6** genel sohbet. `A03`, üst JID'i `linked_parent jid` içinden okur. Alt gruplar için `membership_approval_mode` varsayılanı `parent/default_membership_approval_mode="request_required"` değerinden gelir.

Found: `A1W` yalnızca **JID türünü** kontrol eder (tür 1 ve 2, `C0DZ.A0l` geçer: `@g.us` grubu ve `@temp` grubu `C99Q`), topluluk rolünü kontrol etmez. Alıcı yalnızca tür 1'i kabul eder (`C0DZ.A0b`). Bir üst / duyuru grubunun sunucu tarafı veya grup başına deney gate'leri (23245 / 30905 grup başınadır) ile dışlanıp dışlanmadığı unknown. Yorum mesajları (topluluk duyuru yorumları) ve ilişkilendirme alt öğeleri ayrı listelerde taşınır (6.1); alıcı, üstü bundle içinde olmayan bir yorumu veya alt öğeyi atar (`orphan_parent_not_in_bundle`, `invalid_comment`).

### 2.4 Yönetici ayarı `member_share_group_history_mode`

| Ağ değeri | Enum (`EnumC216299Tq`) | Yerel int | Anlam |
|------------|------------------------|-----------|---------|
| yok / bilinmeyen | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` 0 | 0 | ayarlanmamış |
| `admin_share` | `ADMIN_SHARE` 1 | 1 | geçmişi yalnızca yöneticiler gönderir |
| `all_member_share` | `ALL_MEMBER_SHARE` 2 | 2 | herhangi bir üye gönderebilir |
| `all_member_share_toggle_on` | `ALL_MEMBER_SHARE_TOGGLE_ON` 3 | 2 | 2 ile aynı; bildirimlerde görülen varyant (ayrım inferred) |

Eşleme: `AbstractC227759t3.A01(String)` (string'den int'e), `A00(enum)` (enum'dan int'e, 2 ve 3 için 2).

| Öğe | Ayrıntı (found) |
|------|----------------|
| Ayarlama | `GroupPermissionsActivity` anahtarı (`C201678ic.A04`): MEX işlemi `SetGroupProperty` (istemci `whatsapp-android-mex`, girdi sınıfı `C204518nF`), `member_share_group_history_mode` = `ALL_MEMBER_SHARE` veya `ADMIN_SHARE`. Aynı girdi ayrıca `allow_admin_reports`, `allow_non_admin_sub_group_creation`, `announcement`, `hidden_group`, `locked`, `member_add_mode`, `member_link_mode`, `membership_approval_mode_enabled`, `participant_label_enabled`, `subject` taşır |
| Bildirim | grup bildirimi (`w:gp2`, inferred) alt node'u `member_share_group_history_mode` (`C22270sr`), `A0g(actor, group, mode int, ts)` çağırır: saklanan modu günceller ve bir sistem mesajı ekler |
| Sistem mesajı | "yeni üyeler için son geçmiş paylaşımı açıldı / kapatıldı", altı varyant (actor `%s`, "Recent history sharing was ...", "You ..."), her biri "Tap to change" veya "Tap to learn more" ile |
| History sync | `GroupShareGroupHistoryModeHistorySync`, eşlenmiş cihazlar için sistem mesajını yeniden oluşturur; `GroupChangeHistoryEnabledHistorySync` aynısını `history_enabled` için yapar |
| DB | `wa_group_admin_settings`: `share_group_history_setting_mode`, `group_history_toggle_mode`, `history_enabled`, `earliest_group_history_message_timestamp_ms` |

`group_history_toggle_mode` (int, paylaşım modundan ayrı) anlamı çözülemedi; sütun, sıfır olmayan ve `group_state = 0` olan gruplar için okunur. Arayüz metni: "Admins can choose if members are allowed to send message history", "Admins control if history is sent", "When adding someone to the group, members have the choice to send up to 100 recent messages".

---

## 3. Uygunluk

### 3.1 Gönderici (`A1W.A03`, found)

| # | Koşul | Aksi halde |
|---|-----------|------|
| 1 | kill switch **35987** açık (gönderici ön koşulları) | `PREREQUISITES_DISABLED` |
| 2 | grup JID türü 1 veya 2 | `GROUP_TYPE_NOT_ELIGIBLE` |
| 3 | grup contact satırı mevcut | `GROUP_NOT_FOUND` |
| 4 | grubun içindeyim ve ya yönetici / süperyöneticiyim ya da (`require_membership_approval` = false ve `member_add_mode` = 1 ve paylaşım modu = 2) | `SENDER_NOT_ELIGIBLE` (log üç değeri listeler) |
| 5 | paylaşılabilir en az bir mesaj var (`A0G.A00` sayımı > 0) | `NO_SHAREABLE_MESSAGES` (ayrıca saklanan en erken zaman damgasını düzeltir, `A0A`) |
| 6 | giriş noktası başına gate `A1W.A02` (3.3) | `EXPERIMENT_DISABLED` |

Yani sıradan bir üye yalnızca herkesin üye ekleyebildiği, onay gerekmeyen ve yöneticinin `all_member_share`'i etkinleştirdiği gruplarda gönderebilir.

### 3.2 Alıcı (eklenen kullanıcı başına, found)

| Kontrol | Sonuç kodu |
|-------|-------------|
| alıcı bot değil (`AbstractC24760wu.A03`) | `RECEIVER_NOT_ELIGIBLE` |
| alıcı contact'ı "artık aktif değil" durumunda değil (`externalUserState`, `A07`) | `RECEIVER_INACTIVE` |
| (grup, kullanıcı) için katılımcı satırı mevcut | `NOT_IN_GROUP` |
| `now - join_time`, flag **30333** altında (birim çözülemedi) ve `group_history_send_state` null veya 1 | `NOT_NEW_OR_ALREADY_SENT` |

`group_history_send_state` (`group_participant_user` sütunu, `C14850fN.A0R` tarafından yazılır): 1 = hâlâ uygun, 2 = zaten gönderildi ("zaten gönderildi" dalından ve 2'yi 1'e sıfırlayan iptal yolundan found). Ağ özniteliği `group_history_sent`'in duruma eşlenmesi inferred.

### 3.3 Gate'ler (`C230099x1`, `A1W.A02`)

Her gate `global flag OR grup başına maruz kalma`dır (`C41861nA.A04(group, id)`):

| Yardımcı | Global | Grup başına id | Kullanım |
|----------|--------|----------------|-----|
| `A01` | **26451** | 30905 | giriş noktası `AFTER_JOIN` |
| `A02` | **15313** | 23245 | ekleme sırasında geçmiş gönderme (`A1W.A0B`), ayrıca `onGroupParticipantsAdded`'i gate'ler |
| `A03` | **29973** | 30906 | çağıranlar izlenmedi |

Giriş noktaları (`C9SA`): `AFTER_JOIN`, `FROM_MENTION`, `FROM_CONTACT_MESSAGE`. `FROM_MENTION` ve `FROM_CONTACT_MESSAGE` ayrıca kill switch **35554** / **35555**'e ve gate `A02`'ye bağlıdır. Birleşik kontrolün polaritesi çözülemedi (decompile akışı `A1W.A09` çevresinde bozuk).

---

## 4. Katılma akışı (gönderici tarafı)

### 4.1 Arayüz giriş noktaları (found)

| Giriş | Sınıf | Ne olur |
|-------|-------|--------------|
| Üye ekleme seçici | `VoipParticipantPickerFragment` + `GroupHistoryAddMembersSettingFooterView` | alt bilgi "Send message history to approved members", bir anahtar ve bir "recent messages" bağlantısı ile; dokunmak miktar diyaloğunu açar; anahtar durumu hatırlanır (`is_group_history_toggled`) |
| Üyelik onayı ekranı | `GroupMembershipApprovalRequestsFragment` (`C24002AWf`) | onaylamadan önce aynı miktar diyaloğu |
| Katılım sonrası sayfa | `GroupHistoryAfterJoinSendBottomSheetFragment` | "Send message history to %1$s?" (bir veya iki isim) |
| Mention / paylaşılan contact | giriş noktaları `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | yalnızca adlar; davranış izlenmedi |

İlk kullanımda onay metni: "Group history messages are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them." (`group_history_confirmation_dialog_confirmed_times` sayacı).

### 4.2 Miktar seçenekleri (`C229129vL.A00(n)`, found)

`n` = `A0G.A00` sayımı (5.1'deki limitlere sığan mesajlar).

| n | Seçenekler |
|---|---------|
| 0 | yok ("No message history to view") |
| 1..25 | tek seçenek, `n`, "all" olarak işaretli ("Last %d (all)") |
| > 25 | `k = min(4, ceil(n/25))`, `step = max(25, n/k)`; seçenekler `step`, `2*step`, ... `k-1` adıma kadar, sonra `n` (son adımda bir boyut koşulu altında "all" olarak işaretlenir; tam karşılaştırma çözülemedi) |

Liste daha sonra `C0CG.A0Z` ile tersine çevrilir (inferred: en büyük önce); ilk girdi önceden seçilidir. Sabitlenmiş mesaj uyarısı ("All available pinned messages will be included") her zaman gösterilir.

### 4.3 Add IQ ve olay bağlantıları (found)

```xml
<iq xmlns="w:g2" type="set" to="GROUP@g.us" id="…">
  <add>                                       <!-- optional transparency_acknowledged="true" -->
    <participant jid="USER"><privacy>bytes</privacy></participant>   <!-- privacy child optional -->
  </add>
</iq>
```

Oluşturucu okunarak bulundu (`C11410Yt`): ekleme isteğine geçmişe özgü hiçbir öznitelik eklenmez; geçmiş kararı tamamen yereldir. Bekleyen job'u serbest bırakan olaylar (`C197318aR`, IQ'nun kendisi için zaman aşımı 32 sn):

| Olay | Handler | Etki |
|-------|---------|--------|
| Geçmiş istendi | `CCP(params, group, requestId, receivers, nonReceivers, approvedByMe)` | `PendingSendGroupHistoryJob`'u kalıcılaştırır; seçilen sayıyı `A08[requestId]` içinde hatırlar; `group_history_usage_activated` ayarlar |
| Add IQ yanıtlandı | `BfO(C222169gu)` | istek başına sonuç haritasını saklar |
| Katılımcılar eklendi (bildirim) | `BvD` (yalnızca gate `A02` iken) | "benim eklediklerim" / "başkalarının eklediği" kümelerine ekler |
| Üyelik onayı yanıtlandı | `C05(group, user, requestId, approved)` | onaylanan kullanıcıyı (veya boş) saklar |

### 4.4 Bekleyen job (`PendingSendGroupHistoryJob`, found)

Alanlar: `permanentGroupRawJid`, `requestId`, `messageCount`, `lastMessageSortId`, `groupHistoryReceiverRawJids`, `groupHistoryNonReceiverRawJids`, `approvedByMeRawJids`, `jobScheduledServerTimeInMillis`, `expirationTimeInMins`. Kalıcı job id'si `group-pending-send-group-history`, requirement `SendGroupHistoryJobRequirement` (tüm alıcı JID'leri ayrıştırılabilmeli, aksi halde `invalid group history receiver jid`).

| Adım | Ayrıntı |
|------|--------|
| Requirement karşılanır, eğer | job süresi dolmuşsa; veya `requestId` için ekleme / onay sonucu geldiyse; veya bir alıcı "başkalarının eklediği" kümesinde ve benim tarafımdan onaylanmamışsa; veya bir alıcı artık katılımcıysa (`A0r`) |
| Süre dolumu | `scheduled + flag 19034` dakika; süresi dolan job: iptal edilir, katılımcı durumu 2'den 1'e sıfırlanır |
| Çalıştırma | alıcıları zaten katılmış ve kalan olarak ayırır; kalanlar **yeni** bir bekleyen job'a gider (aynı request id, alıcı olmayanlar filtrelenmiş); katılan alıcılar bundle'ı alır (`C9mW.A00`) |
| Bot alıcılar | bir TEE bot alıcısı (`AbstractC197238aI.A00`) ayrı bir geçmiş paylaşım damgasıyla işlenir (`A04`, 5.5) |
| Mükerrer koruması | `C197318aR.A09` haritası (grup, kullanıcı) gönderim zamanına; `19034` dakikadan eski girdiler (en az 5) temizlenir |

---

## 5. Seçim, limitler ve paketleme

### 5.1 Satır seçimi (`A0G`, `AbstractC494421h.A00`, found)

```sql
SELECT … FROM available_message_view [ / with association join when 24033 ]
WHERE timestamp >= (scheduledTimeMs - flag18406 s)
  AND chat_row_id = ? AND sort_id <= ?                 -- anchor = last message at scheduling time
  AND view_mode IS NOT 1 AND view_mode IS NOT 3
  AND message_type IN (shareable types)                -- from the type registry, BUv()
  AND (association_type IS NULL OR association_type IN (supported))   -- only when 24033
  AND (from_me = 0 OR status NOT IN (-1,0,1,2,7,20,21,22))
  AND (expire_timestamp IS NULL OR expire_timestamp >= now OR keep_in_chat = 1)
ORDER BY sort_id DESC LIMIT n
```

| Parametre | Kaynak |
|-----------|--------|
| `n` | sayım sorgusu LIMIT olarak flag **18405** kullanır; gönderim sorgusu kullanıcının seçtiği sayıyı kullanır |
| pencere | zamanlama zamanından önce flag **18406** (saniye); arayüz metni "up to 100" mesaj vaat eder |
| paylaşılabilir türler | FMessage türü başına kayıt (`C222979iT.A00`, `C1ZP.BUv()` true), mesaj başına geçersiz kılma ile (`C30039D5b`); burada listelenmedi |
| kendi mesajları | yalnızca cihazdan çıkmış olanlar (`status` bekleyen / başarısız kümesinde değil, `AbstractC494421h.A00`) |
| ephemeral | süresi dolmuş ve saklanmamış mesajlar atlanır |

Katılım sonrası bir sort id biliniyorsa (`C14650f0.A05`), sayım buna demirlenir ("post-join query"); aksi halde en yeni mesaja demirlenir ("pre-join query").

### 5.2 Bundle içindeki listeler (found, `C9mW.A00`)

| Liste | İçerik | Limit |
|------|---------|-------|
| `messages` | seçilen satırlar (yalnızca paylaşılabilir) | `n` |
| `uncountedAssociatedMessageLists` | seçilen bir üst mesaja bağlı alt öğeler (albüm öğeleri, anketler, ...), `(parent key, association type)` ile gruplanmış; yalnızca **24033** iken | `messageCount` içinde sayılmaz |
| `commentMessages` | seçilen mesajlara yapılan yorumlar (`C14780fG.A02(list, flag 6050, …)`) | flag **6050** (üst sınır olarak inferred) |
| `outOfWindowPinnedMessages` | seçilen en eski mesajdan daha eski sabitlenmiş mesajlar; yalnızca medya olmayanlar; paylaşılabilir kümeyle filtrelenmiş | mevcut tümü (uyarı string'i); alıcı üst sınırı flag **19811** (inferred) |

İlişkilendirme türleri (`C13O`, 21 değer): `FUTURE` 0 (aynı zamanda yedek değer), `MEDIA_ALBUM` 1, `BOT_PLUGIN` 2, `EVENT_COVER_IMAGE` 3, `HD_VIDEO_DUAL_UPLOAD` 5, `STATUS_EXTERNAL_RESHARE` 6, `MEDIA_POLL` 7, `POLL_ADD_OPTION` 20, `STREAMED_HD_VIDEO_DUAL_UPLOAD` 22 ve başka durum / sticker / dual-upload türleri.

### 5.3 Paketleme (found)

1. `GroupHistory` proto'su (6.1) uzantısı `proto` olan bir dosyaya serileştirilir (`File … A0Z(C15530gU.A0F, "proto")`); sıkıştırma adımı bulunmadı.
2. Grup sohbetinde dosya medya olarak (`mimetype application/protobuf`) olan 117 türünde yeni bir FMessage oluşturulur ve normal medya mesajı gönderim hattına verilir (yükleme ve şifreleme, bölüm 7).
3. FMessage üzerindeki yerel alanlar: mesaj sayısı, penceredeki en eski zaman damgası (saniye), genel en eski zaman damgası (sabitlenmiş mesajlarla min), alıcılar, alıcı olmayanlar, paketlenen mesaj listelerinin boyutları, dosya boyutu, oluşturma süresi (telemetri).
4. **24741** açıksa ve mesajın secret'ı yoksa, ona yeni bir message secret üretilir, ardından orijinal mesaj başına reporting token'ları hesaplanır (bölüm 9).

### 5.4 Gönderimden sonra notice (found, `ANQ.C0M`)

Bundle durum **1**'e ulaştığında (flag **28787** açıksa **24**) ve notice henüz gönderilmediyse (`A00 != 1`), cihaz aynı grupta bundle'ın sayıları, zaman damgaları ve alıcılarıyla 118 türünde bir notice oluşturur ve gönderir (`C33166Ecf.A06`). Her grup üyesi onu alır; `historyReceivers` içinde adı geçen alıcılar ayrıca onu işaretler (`AbstractC30028D4q.A1B`).

### 5.5 TEE bot geçmiş paylaşımı (found, kısa)

Bir bot alıcı için `C9mW.A01`, message secret taşıyan seçili mesajları bir kanıtla damgalar (`AbstractC33322EfC.A02(sender, botJid, "TEE History Share", stanzaId, secret)`) ve `botHistoryShareSyncMetadata` içinde `(stanzaId, messageSecretProof)` listeleyen bir notice gönderir. Bot bağlamı için Meta AI raporuna bakın: [WA_META_AI.md](./WA_META_AI.md). Bot yolu bir bundle yüklemez.

---

## 6. Ağ formatı

### 6.1 İç dosya: `GroupHistory` (`DSN`)

| Alan | Numara | Tür | İçerik |
|-------|--------|------|---------|
| `messages` | **1** | repeated `WebMessageInfo` (`C30626DTu`) | sayılan mesajlar |
| `uncountedAssociatedMessageLists` | **2** | repeated `UncountedAssociatedMessageList` (`C30578DRy`) | `messages` **1** (repeated WebMessageInfo), `parentMessage` **2** (`MessageKey`, `BD5`), `associationType` **3** (enum `C13O`) |
| `commentMessages` | **3** | repeated `WebMessageInfo` | yorumlar |
| `outOfWindowPinnedMessages` | **4** | repeated `WebMessageInfo` | sabitlenmişler |

Alıcı aynı baytları ikinci kez `GroupHistoryWithMessageBytes` olarak ayrıştırır (`C30576DRw`: aynı dört alan numarası; girdiler `C30543DQp`, `key` **1** (`MessageKey`) ve `message` **2** (bytes); ilişkilendirme listeleri `DPH` yalnızca `messages` **1** olarak okunur). Bu varyant mesaj başına orijinal serileştirilmiş baytları tutar (reporting token doğrulaması ve secret işleme için kullanılır, inferred).

### 6.2 Dış mesaj: `Message.messageHistoryBundle` (`DT6`, alan **70**)

| Alan | Numara | Tür | Değer / kullanım |
|-------|--------|------|-------------|
| `mimetype` | **1** | string | `application/protobuf`'a eşit olmalı |
| `fileSha256` | **2** | bytes | 32 bayt, düz metin hash'i |
| `mediaKey` | **3** | bytes | medya anahtarı |
| `fileEncSha256` | **4** | bytes | 32 bayt, şifreli metin hash'i |
| `directPath` | **5** | string | yükleme yolu; boş olması loglanır, ayrıştırma zamanında ölümcül değildir |
| `mediaKeyTimestamp` | **6** | int64 | saniye |
| `contextInfo` | **7** | `ContextInfo` | standart |
| `messageHistoryMetadata` | **8** | `MessageHistoryMetadata` (`C30583DSd`) | aşağıda |

`MessageHistoryMetadata`:

| Alan | Numara | Tür | Alımda kural |
|-------|--------|------|-----------------|
| `historyReceivers` | **1** | repeated string | en az bir; mevcut kullanıcı listede olmalı |
| `oldestMessageTimestampInWindow` | **2** | int64 | mevcut ve > 0 |
| `messageCount` | **3** | int64 | mevcut ve > 0 |
| `nonHistoryReceivers` | **4** | repeated string | isteğe bağlı |
| `oldestMessageTimestampInBundle` | **5** | int64 | isteğe bağlı (sabitlenmişleri içerir) |

### 6.3 Notice: `Message.messageHistoryNotice` (`DRY`, alan **102**)

`contextInfo` **1**, `messageHistoryMetadata` **2** (aynı tür, alıcılar, zaman damgası ve sayı kurallarıyla zorunlu), `botHistoryShareSyncMetadata` **3** (`C25765B9z`: `botJid` **1**, `historyShareMessages` **3** repeated `BA2` = `stanzaId` **1**, `messageSecretProof` **2**). Lite düzeninde `C25765B9z` içinde alan **2** yoktur; bir cutoff yalnızca yerel durum olarak vardır (`C213519Ap.A03`).

### 6.4 Stanza düzeyi (found)

| Öğe | Bundle (117) | Notice (118) |
|------|--------------|--------------|
| stanza `type` | `media` | medyaya özgü değil |
| `<enc>` medya türü | `group_history` (`C30106D7q`; izin verilen enc medya türü kümesinde `C9E2` / `C33474Ehg`) | yok |
| `<meta appdata="…">` | **ayarlanmaz** (`C213539Ar`, `FZF`'yi uygulamaz) | `group_history` (`C213519Ap.AVN`; `F6K` yazar) |
| alıcı kontrolü | `A0O == "media"` ve `A0J == "group_history"`, aksi halde hata 11 | `appdata == group_history`, aksi halde hata 76 |
| `<reporting>` | isteğe bağlı, bölüm 9 | yok |

Her iki kontrol de zarf flag'leri `A0V` / `A0U` ayarlıysa atlanır (anlamı çözülemedi). Medya türü `group_history` ile gelen ancak eşleşen mesajı olmayan bir bundle ve yabancı bir türde notice appdata'sı `GroupHistoryBundleDeserializationValidator` / `GroupHistoryNoticeDeserializationValidator` tarafından reddedilir (`F3b` / `F3c`).

### 6.5 `WebMessageInfo` işaretleri (`C30626DTu`, found)

| Alan | Numara | Tür | Kullanım |
|-------|--------|------|-----|
| `isGroupHistoryMessage` | **57** | bool | mesaj bir bundle'dan içe aktarıldı |
| `reportingTokenInfo` | **62** | message | reporting etiketi (Reporting raporuna bakın) |
| `groupHistoryIndividualMessageInfo` | **74** | `C30549DQv` | `bundleMessageKey` **1** (`MessageKey`), `editedAfterReceivedAsHistory` **2** (bool) |
| `groupHistoryBundleInfo` | **75** | `C30548DQu` | `deprecatedMessageHistoryBundle` **1**, `processState` **2** (enum `EnumC32128E2a`) |

`processState`: `NOT_INJECTED` 0, `INJECTED` 1, `INJECTED_PARTIAL` 2, `INJECTION_FAILED` 3, `INJECTION_FAILED_NO_RETRY` 4, `DEDUPED` 5.

---

## 7. Şifreleme ve medya

| Katman | Found |
|-------|-------|
| Mesaj taşıma | normal grup fan-out'u: 117 mesajı her grup mesajı gibi şifrelenir (grup başına sender-key `skmsg` ve cihazlara olağan sender-key dağıtımı). Temeller burada tekrarlanmaz; stanza `<enc>` biçimi [WA_CALL_SIGNALING.md](./WA_CALL_SIGNALING.md) içinde `<enc>` bölümündedir. Cihaz başına sender-key durumu `group_participant_device` içinde yaşar (`sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket`) |
| Medya satırı | `C15530gU.A0F`: yükleme türü `group-history`, dosya türü `GROUP_HISTORY`, HKDF info `Group History`, id 117 |
| Anahtar / şifre | rastgele medya anahtarı, info `Group History` ile HKDF-SHA256, AES-256-CBC, 10 bayta kısaltılmış HMAC-SHA256 eklenir, proto'da `fileSha256` / `fileEncSha256`: [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) bölüm 6'daki genel şema (Android'de 80 baytlık genişletme); bu türe ortak gönderim hattı üzerinden uygulanır (inferred, yalnızca tür satırı okundu) |
| Yükleme URL'si | `https://<host>/mms/group-history/<hash>?…`; `mms/<upload type>` bileşimi tablo için found (medya raporu bölüm 4); bu tür için gerçek yol yakalanmadı (inferred) |
| İndirme | `mediaKey`, `directPath`, hash'ler kullanılan standart medya indirmesi; hata metni `GroupHistoryBundleProcessor/download failed for … with reason …` |
| Anahtar yeniden kullanımı | bundle medya anahtarı, içerdiği mesajların mesaj anahtarlarından bağımsızdır |

Alıcı her zaman proto'daki `mediaKey` ile çalışır; hash'leri 32 bayt olmayan bir bundle reddedilir (`bogus sha-256 hash received`, hata 14).

---

## 8. Alıcı: doğrulama ve içe aktarma

### 8.1 Ayrıştırma zamanı kontrolleri (`C34677F2y.CM7`, found)

| Kontrol | Hata |
|-------|-------|
| sohbet JID'i bir grup (`A0l`) | 11 `chatJid is not a group` |
| zarf `media` + enc medya türü `group_history` | 11 |
| `mimetype == application/protobuf` | 11 |
| `fileSha256`, `mediaKey`, `fileEncSha256`, `mediaKeyTimestamp`, metadata mevcut | 11 |
| `historyReceivers` boş değil, pencere zaman damgası > 0, sayı > 0 | 11 |
| mevcut kullanıcı `historyReceivers` içinde (kendi mesajları için değil) | 11 `current user is not in history receivers list` |
| gate **15311** kapalı | yer tutucu FMessage `C35281aa`, kod **82** ("Update to the latest version of WhatsApp to see it") |
| hash uzunlukları 32 | 14 |

Notice (`C34678F2z`): grup sohbeti, appdata, alıcılar / zaman damgası / sayı içeren metadata; gate **15722** kapalıysa yer tutucu kodu **10008**.

### 8.2 İşleme (`GroupHistoryBundleProcessor`, aksi belirtilmedikçe found)

1. Tetikleyici: mesaj eklendi (`C0G`) ve medya durumu 3'te tekrar (`C0M`). Aday; grup sohbeti (tür 1), benden değil, durum 0 veya 5, alıcı listesinde ben varım ve flag **25910**'dan daha genç (birim çözülemedi; aksi halde "Message history expired").
2. Tekilleştirme (flag **30462**): aynı katılım oturumu için zaten bir bundle işlendiyse yenisi deduped olarak işaretlenir (`deduped_bundle_for_join_session`), arayüz: "%1$s also sent you message history, which you already got from someone else".
3. Medyayı indir; hata "Couldn't download message history from %1$s" gösterir.
4. Dosyayı iki kez ayrıştır (`DSN`, `DRw`); ayrıştırma hatası: `protobuf_parse_failed`.
5. Çapayı bul: en son grup katılım mesajı (hiçbiri yoksa "failed to find latest group join message, adding messages before the first message in chat"); çok eski bir çapa: `anchor_message_too_old`.
6. Her mesajı doğrula ve ekle (8.3); eklenen her satırı bundle ile ilişkilendir (`group_history_bundle_association`: `bundle_message_key_id`, `message_row_id`, `message_sort_id`); `isGroupHistoryMessage` işaretle.
7. Pencere dışı sabitlenmişler: üst sınır (flag **19811**, inferred), paylaşılan sabitleme durumunu uygula (`applySharedPin`).
8. Bekleyen bot geçmiş paylaşım damgalarını uygula (`BotHistoryShareHelper`), ardından telemetri (`group_history_receiver_user_journey`).

İçe aktarılan satırlar katılım çapasından önce yerleştirilir, dolayısıyla "eklendiniz" satırının üstünde görünürler (çapa mantığından inferred).

### 8.3 Mesaj başına doğrulama (`C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg`, found)

| Atlama nedeni | Sebep |
|-------------|-------|
| `invalid_jid` | `key.remoteJid` bundle sohbetinden farklı |
| `non_hex_id` | `key.id` yalnızca hex değil |
| `timestamp_too_old` | `messageTimestamp` izin verilen alt sınırdan yeni değil (log alanları `msgTs`, `allowedTs`, `diff`; sınır yerel durumdan türetilir, formül çözülemedi) |
| `parse_failed`, `pin_not_parsed` | girdinin proto'su ayrıştırılamadı |
| `not_shareable` | mesaj türüne içe aktarma için izin verilmiyor |
| `no_local_copy` | mesajı atlanmış ve yerelde olmayan paylaşılan sabitleme |
| `max_limit_reached` | üst sınıra ulaşıldı |
| `timestamp_after_anchor` | mesaj katılım çapasından yeni |
| `already_exists`, `duplicate`, `expired` | yerelde zaten var, dosyada mükerrer, ephemeral süresi dolmuş ve saklanmamış |
| `orphan_parent_not_in_bundle`, `invalid_comment` | üstü dosyada olmayan yorum / ilişkilendirme alt öğesi |
| `insert_exception`, `anchor_messages_failed`, `insert_messages_exception` | yerel DB hataları |

Ayrıca: bir mesajın `messageSecret`'ının korunması gerekir (`messageSecretLost`, `noMessageSecret` logları); farklı içerikle yerelde bir mesaj varsa yerel kopya kazanır (`keeping local …`).

Dokunulan tablolar (found): `group_history_bundle_association` (`bundle_message_key_id`, `message_row_id`, `message_sort_id`), `group_history_share_reporting_info` (`stanza_id`, `reporting_tag`, `send_timestamp`, `added_timestamp`, `reporting_token`, `reporting_token_version`, `is_send`, `validation_policy`), `group_participant_user.group_history_send_state`, `wa_group_admin_settings` (2.4).

---

## 9. Reporting token'ları (kısa)

**24741** açıkken bir bundle için stanza bölümü (`F6C`, `GhsReportingTokenMessageSendStanzaContributor`):

```xml
<reporting>
  <message id="ORIGINAL_STANZA_ID"><reporting_token v="N">16 bytes</reporting_token></message>
  …
</reporting>
```

Token türetimi ve saklanması [WA_REPORTING.md](./WA_REPORTING.md) içindedir (bölüm 6.2); anahtar türetiminin bir kısmı native kodda çalışır, dolayısıyla kesin baytlar yalnızca Java'dan yeniden üretilemez. Alımda, **5718** ve **24742** açıkken, içe aktarılan bir mesaj için eksik token `GROUP_HISTORY_MESSAGE_MISSING_FROM_PUBLIC_STANZA` telemetrisini üretir (**13063** ile ayrıca bir dahili tanılama satırı); bu yolda mesaj yine de eklenir (kontrol akışından inferred). Sunucunun token'ları zorunlu kılıp kılmadığı: unknown.

---

## 10. Eşlenmiş cihazların HistorySync'i (ilişkili, grup geçmişi değil)

Eşleme ve app-state temelleri [WA_LINKED_DEVICE_PAIRING.md](./WA_LINKED_DEVICE_PAIRING.md) ve [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md) içindedir. Yalnızca grup verisini ilgilendirenler:

### 10.1 `HistorySyncConfig` (`C44601rs`, eşlenmiş cihaz bildirir; alan numaraları lite düzeninden)

| Alan | # | Eşlenmiş cihaz değeri (found) |
|-------|---|-------------------------|
| `fullSyncDaysLimit`, `fullSyncSizeMbLimit` | 1, 2 | flag'ler **15284**, **15283** |
| `storageQuotaMb`, `initialSyncMaxMessagesPerChat` | 3, 20 | izlenen dalda ayarlanmamış |
| `recentSyncDaysLimit` | 5 | 0 |
| `supportMessageAssociation`, `supportHostedGroupMsg`, `supportAddOnHistorySyncMigration` | 14, 11, 13 | true |
| `supportGroupHistory` | 15 | flag **20658** |
| `onDemandReady` / `completeOnDemandReady` | 16 / 18 | `!` flag **18953** / false |
| `thumbnailSyncDaysLimit` | 19 | flag **21217** |
| `supportHatchHistory` / bot kanal listesi | 22 / 23 | flag **26445** / **26614** üzerinde dal |
| çağrı kaydı, bot ve CAG geçmişi, `supportNewsletter`, `supportInlineContacts`, ... | 4, 6-8, 12, 24-27 | true (diğerleri false) |

Kalan alanlar (`supportBizHostedMsg` 9, `supportRecentSyncChunkMessageCountTuning` 10, `supportGuestChat` 17, `supportManusHistory` 21, `supportUniversalReachChat` 26, `supportOmittedConversationIndex` 27) burada ayrıntılandırılmamıştır.

### 10.2 Sync türleri ve mesajlar

| Mesaj | Alan | İçerik |
|---------|-------|---------|
| `HistorySync` (`C25838BCy`) | `syncType` **1**, `conversations` **2**, `statusV3Messages` **3**, `chunkOrder` **5**, `progress` **6**, `pushnames` **7**, `globalSettings` **8**, `threadIdUserSecret` **9**, `threadDsTimeframeOffset` **10**, `recentStickers` **11**, `pastParticipants` **12**, `callLogRecords` **13**, `aiWaitListState` **14**, `phoneNumberToLidMappings` **15**, `companionMetaNonce` **16**, `shareableChatIdentifierEncryptionKey` **17**, `accounts` **18**, `nctSalt` **19**, `inlineContacts` **20/21**, `omittedConversations` **23/24** | grup sohbetleri `conversations` içinde taşınır; `pastParticipants` (**12**) eski grup üyelerini listeler |
| `HistorySyncNotification` (`C25834BCt`) | `fileSha256` **1**, `fileLength` **2**, `mediaKey` **3**, `fileEncSha256` **4**, `directPath` **5**, `syncType` **6**, `chunkOrder` **7**, `originalMessageId` **8**, `progress` **9**, `oldestMsgInChunkTimestampSec` **10**, `initialHistBootstrapInlinePayload` **11**, `peerDataRequestSessionId` **12**, `fullHistorySyncOnDemandRequestMetadata` **13**, `encHandle` **14**, `messageAccessStatus` **15** | medya referanslı chunk; yük `HistorySync`'tir |

Sync türleri: `INITIAL_BOOTSTRAP` 0, `INITIAL_STATUS_V3` 1, `FULL` 2, `RECENT` 3, `PUSH_NAME` 4, `NON_BLOCKING_DATA` 5, `ON_DEMAND` 6 ve 9 değerli enum'da (`EnumC26456Bdr`) ayrıca `NO_HISTORY` 7 ve `MESSAGE_ACCESS_STATUS` 8 (`EnumC26449Bdk` 7 değerli varyanttır).

### 10.3 İsteğe bağlı peer veri işlemleri (`EnumC26460Bdv`, found)

| İşlem | Id | İstek alanı (`C25823BCh`) | Yanıt alanı (`C25828BCm`) |
|-----------|----|-----------------------------|------------------------------|
| `HISTORY_SYNC_ON_DEMAND` | 3 | `historySyncOnDemandRequest` **4** (`BCR`: `chatJid` **1**, `oldestMsgId` **2**, `oldestMsgFromMe` **3**, `onDemandMsgCount` **4**, `oldestMsgTimestampMs` **5**, `accountLid` **6**, `supportInlineResponse` **7**) | tanımlı değil; geçmiş bir `HistorySyncNotification` olarak gelir (inferred) |
| `FULL_HISTORY_SYNC_ON_DEMAND` | 6 | `fullHistorySyncOnDemandRequest` **6** (`BBB`: `requestMetadata` **1** `BBA`, `historySyncConfig` **2**, `fullHistorySyncOnDemandConfig` **3** `C156516k5`: `historyFromTimestamp` **1**, `historyDurationDays` **2**) | `fullHistorySyncOnDemandRequestResponse` **6** |
| `PLACEHOLDER_MESSAGE_RESEND` | 4 | **5** | **4** |
| `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` | 8 | **7** | **8** |

Primary her sync için `msg_history_sync` içinde bir satır tutar (`device_id`, `sync_type`, `last_processed_msg_row_id`, `oldest_msg_row_id`, `sent_msgs_count`, `chunk_order`, `sent_bytes`, `last_chunk_timestamp`, `status`, `peer_msg_row_id`, `oldest_message_to_sync_row_id`, `session_id`, `size_limit_bytes`, `full_history_on_demand_request_id`, …). Chunk boyutu ve mesaj sayıları için sunucu tarafı üst sınırları burada okunan istemci kodunda görünmez (unknown). Bir grubun paylaşılan geçmişine özgü bir isteğe bağlı işlem yoktur.

### 10.4 Eşlenmiş cihazlarda grup geçmişi

| Öğe | Found |
|------|-------|
| Capability | `companion-props` içinde `supportGroupHistory` (flag **20658**); primary üzerinde `support_group_history` olarak saklanır (eşleme raporu, bölüm 6.2); tüketici izlenmedi |
| Bundle teslimi | bundle normal bir grup mesajıdır, dolayısıyla bir alıcının her cihazı onu alır; eşlenmiş cihazlar için string'ler ("Open WhatsApp on your phone and visit this group to see it") orada bir yer tutucuya işaret eder (inferred) |
| Primary sync oluşturma | `BuildHistorySyncParams` (`C33151EcQ`) `supportGroupHistory`, `pullGroupHistoryUncountedChildren`, `maxCommentsToAdd`, `supportMessageAssociation` taşır; tüketiciler izlenmedi |
| Sistem mesajları | paylaşım modu, history-enabled, üye ekleme / bağlantı / onay modu değişiklikleri eşlenmiş cihazlar için `Group*HistorySync` sınıfları tarafından yeniden oluşturulur |

---

## 11. Feature flag'ler ve limitler

Flag id'leri kalın yazılmıştır; değerler sunucudan iletilir, derlenmiş varsayılanlar çözülemedi (arayüz metni "up to 100" mesaj der).

| Flag | Tür | Kontrol ettiği | Katman |
|------|------|----------|------|
| **35987** | bool | gönderici ön koşulları kill switch'i | found |
| **15313** / 23245 | bool / grup | gate `A02`, ekleme sırasında geçmiş gönderme | found |
| **26451** / 30905 | bool / grup | gate `A01`, giriş noktası `AFTER_JOIN` | found |
| **29973** / 30906 | bool / grup | gate `A03` | found (kullanım unknown) |
| **35554**, **35555** | bool | `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | polarite inferred |
| **18405** | int | sayım sorgusunun LIMIT'i (teklif boyutu üst sınırı) | found |
| **18406** | int, s | zamanlama zamanından önceki geriye bakış penceresi | found |
| **19034** | int, dk | bekleyen job süre dolumu, mükerrer temizliği (en az 5) | found |
| **30333** | long | bir alıcı için katılımdan itibaren azami süre | found (birim çözülemedi) |
| **24033** | bool | ilişkilendirme listeleri ve ilişkilendirme filtresi | found |
| **6050** | int | yorum toplama üst sınırı | inferred |
| **24741** | bool | gönderimde reporting token'larını oluşturur | found |
| **28787** | bool | notice tetikleyici durumu 1 yerine 24 | found |
| **20658** | bool | eşlenmiş cihaz `supportGroupHistory` bildirir | found |
| **15311** | bool | alım: bundle kabul edilir (kapalı: yer tutucu 82) | found |
| **15722** | bool | alım: notice kabul edilir (kapalı: yer tutucu 10008) | found |
| **30462** | bool | alım: katılım oturumu başına tekilleştirme | found |
| **25910** | long | alım: bir bundle'ın tazelik penceresi | found (birim çözülemedi) |
| **19811** | int | alım: pencere dışı sabitleme üst sınırı | inferred |
| **24034** / **25037** | bool / int | alım: ilişkilendirme alt öğesi işleme ve int parametresi | inferred |
| **26039** | bool | ekleyici gate'i (üç yer) | found (kullanım unknown) |
| **5718** + **24742** | bool | alım: reporting token doğrulaması | found |
| **13063** | bool | eksik token'da dahili tanılama satırı | found |

---

## 12. Hata durumları

| Belirti | Neden | Çözüm |
|---------|-------|-----|
| "Send history" seçeneği yok | gönderici uygun değil (3.1), grup LID / PN tutarlı değil veya paylaşılabilir mesaj yok | yönetici `all_member_share`'i, üye ekleme modu `all_member_add`'i etkinleştirir, onay yok; veya yönetici olarak gönderin |
| Alıcı "Update to the latest version" gösterir | gate 15311 / 15722 kapalı veya bilinmeyen tür | istemcide yok |
| Bundle reddedildi, hata 11 | yanlış MIME, zarf türü, medya türü, eksik alan, ben `historyReceivers` içinde değilim | bölüm 6'ya göre oluşturun |
| Bundle reddedildi, hata 14 | hash 32 bayt değil | hash'leri düzeltin |
| Notice reddedildi, hata 11 / 76 | appdata `group_history` değil (ayrıştırma, 11); başka bir türde notice appdata'sı (doğrulayıcı, 76) | `appdata=group_history` yalnızca 118 türünde ayarlanmalı |
| İçe aktarmadan sonra mesajlar eksik | 8.3'teki atlama nedenleri (`timestamp_too_old`, `not_shareable`, `invalid_jid`) | anahtarlar aynı grubun hex id'leri olmalı |
| "Couldn't download message history" | medya indirme başarısız (süresi dolmuş `directPath`, anahtar uyuşmazlığı) | yeniden deneyin; tekrar gönderin |
| Job asla çalışmaz | ekleme veya onay olayı görülmedi, alıcılar hiç katılımcı olmadı, job süresi doldu (19034) | yeniden ekleyin ve tekrar gönderin |

---

## 13. Temel ayrımlar

| Karıştırmayın | Şununla |
|----------------|------|
| Grup geçmişi bundle'ı (tür 117, `application/protobuf`, `group-history`) | eşlenmiş cihaz HistorySync notification'ı (`HistorySyncNotification`, `md-msg-hist`) |
| Bundle (veri, appdata yok) | notice (sayılar ve alıcılar, `appdata=group_history`) |
| `member_share_group_history_mode` (kimin gönderebileceği) | `group_history_toggle_mode` / `history_enabled` (anlamı çözülemedi) |
| `historyReceivers` (veriyi alır) | `nonHistoryReceivers` (eklendi, almaz) |
| `oldestMessageTimestampInWindow` (**2**) | `oldestMessageTimestampInBundle` (**5**, pencere dışı sabitlenmişleri içerir) |
| `messages` sayısı (`messageCount`) | sayılmayan ilişkilendirme alt öğeleri ve yorumlar |
| `HistorySyncConfig` içindeki `supportGroupHistory` (cihaz capability'si) | yönetici ayarı |

---

## 14. Baileys (`baron-baileys-v2` 1.5.17)

Yalnızca `src/Utils/group-history.js`, `src/Socket/groups.js`, `src/Socket/messages-recv.js`, `src/Socket/aigroups.js`, `src/Utils/validate-connection.js`, `WAProto/index.js` içinde okunan olgular. Hiçbir şey bir sunucuya karşı test edilmedi; hiçbir hata iddia edilmiyor.

| Konu | Baileys | Android |
|-------|---------|---------|
| Proto | `GroupHistory`, `GroupHistoryWithMessageBytes`, `GroupHistoryBundleInfo`, `GroupHistoryIndividualMessageInfo`, `Message.messageHistoryBundle`, `messageHistoryNotice`, `HistorySyncConfig.supportGroupHistory` `WAProto` içinde mevcut | 6 |
| Çözücü | `decodeGroupHistory` `zlib.inflateSync` dener, ham baytlara geri döner; isteğe bağlı `GroupHistoryWithMessageBytes` modu; `processGroupHistory` dört listeyi normalleştirir | Android'de sıkıştırma bulunmadı; ham protobuf okunur |
| Bundle alımı | `messageHistoryBundle`'ı işleyen kod yok (medya indirme, doğrulama, ekleme) | bölüm 8 |
| Bundle gönderimi | yok | bölüm 5 |
| Companion capability | bildirilen `HistorySyncConfig` içinde `supportGroupHistory: true` | flag 20658 |
| Grup ayarı | `member_share_group_history_mode` grup metadata'sından okunur; MEX üzerinden `groupSetProperty(jid, property, value)`; mex bildirimi `NotificationGroupMemberShareGroupHistoryModePropertyUpdate` `groups.update { memberShareHistoryMode }` yayar | 2.4 |
| `aiGroupCreate` | `memberShareGroupHistoryMode` kabul eder (varsayılan `all_member_share`) ancak okunan kodda bunu oluşturma stanza'sına koymaz | uygulanamaz |
| Katılımcı öznitelikleri | `group_history_sent`, `join_time` ayrıştırılmaz | 2.2 |
| Adresleme | `addressing_mode` grup node'undan okunur, gönderirken varsayılan `lid` | 2.2 |

Okunanlarla sınırlı sonuç: `supportGroupHistory` bildiren bir Baileys istemcisi, alınan bir bundle'ı içe aktaramaz, çünkü kaynakta tüketici yoktur. Bir gönderici bölüm 5 ile 7'yi izlemelidir (ekleme sonrası gönderim, enc medya türü `group_history` olan `media` türü, HKDF info `Group History` olan medya türü `group-history`, appdata'lı notice); sunucunun `<reporting>` token'ları olmayan bir bundle'ı kabul edip etmediği unknown.

---

## 15. Tam akış

```
[Admin]  switch "Send message history" ─► MEX SetGroupProperty member_share_group_history_mode=ALL_MEMBER_SHARE|ADMIN_SHARE
     │
     ▼
[WA Server]  w:gp2 notification member_share_group_history_mode ─► all members: store mode, system message

[Sender]  add members (picker / approval screen / post-join sheet)
     │   A1W.A09: gate 35987, group type, sender (admin or all_member_share + all_member_add + no approval),
     │            receiver (join age, send_state), shareable messages
     │   A0G.A00 count ─► amount options (<=25 one option, else up to 4)
     ▼
iq set w:g2 <add><participant jid/></add>          (no history attribute)
     │
     ▼
[WA Server]  result ─► BfO / C05 / BvD events ─► PendingSendGroupHistoryJob requirement met
     │
     ▼
[Sender]  A0M: split joined / remaining (remaining re-queued) ─► C9mW.A00
     │   rows: timestamp >= scheduled - 18406 s, sort_id <= anchor, LIMIT n
     │   + association lists (24033) + comments (6050) + out-of-window pins
     │   GroupHistory proto ─► file ─► FMessage 117, mimetype application/protobuf
     ▼
upload  /mms/group-history  (HKDF info "Group History", AES-CBC + HMAC-10)       [WA_MEDIA_UPLOAD]
     │
     ▼
group message  type=media, enc mediatype=group_history, Message.messageHistoryBundle(70)
     │          metadata: receivers, nonReceivers, oldest ts (window / bundle), count
     │          optional <reporting><message id><reporting_token v/></message></reporting> (24741)
     ▼
[Receivers' devices]  C34677F2y checks (group, media, MIME, hashes, me in historyReceivers, gate 15311)
     │   download + decrypt ─► parse DSN / DRw ─► dedupe (30462) ─► anchor = join message
     │   validate each WebMessageInfo (jid, hex id, timestamp, type) ─► insert before anchor
     │   group_history_bundle_association, isGroupHistoryMessage=57
     ▼
[Sender]  bundle status 1 (24 with 28787) ─► notice type 118, appdata group_history, same metadata
     │
     ▼
[All members]  system row "<name> sent message history that starts on <date>"
```

---

## 16. Bilinmeyenler

| Öğe | Durum |
|------|--------|
| Sunucu tarafı kabul kuralları, saklama, boyut üst sınırları, reporting-token zorunluluğu | sunucu tarafı, gözlemlenmedi |
| 18405, 18406, 19034, 25910, 30333 varsayılan değerleri | sunucudan iletilir, varsayılanlar çözülemedi |
| `timestamp_too_old` için kesin alt sınır ve 25910 / 30333 birimi | çözülemedi |
| Giriş noktası başına `A1W.A02` polaritesi; gate `A03` ve flag 26039 kullanımı | bozuk decompile / izlenmedi |
| `group_history_toggle_mode` sütununun ve `<group_history/>` alt node'unun anlamı | adlar bulundu, anlam yalnızca inferred |
| Paylaşılabilir mesaj türü listesi (`BUv()` kaydı) | listelenmedi |
| Bir bundle'ın eşlenmiş cihazda görüntülenmesi; primary üzerinde `support_group_history` tüketicisi | izlenmedi |
| Reporting-token anahtar türetiminin native kısmı | native, okunmadı |
| Trafik | hiçbir şey yakalanmadı; tüm akışlar koddan |
