<!-- src-sha1: 8d1c772149420abe245fd6a70c2b6615d2ab4fc5 -->
# WhatsApp Interop — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android'de üçüncü taraf sohbet birlikte çalışabilirliği (DMA tarzı): özellik geçidi ve AB flag'leri, onay bildirimi ve opt-in, integrator listesi, interop JID domain'leri ve binary JID tag'i, kullanıcı keşfi (`w:interop` FetchUsers), `w:interop` IQ set, kısıtlı `InteropMessage` plaintext'i ve desteklenen mesaj türleri, şifreleme ve stanza farkları, interop grupları (MEX op'ları, bildirimler, ekleme gizliliği), erişilebilirlik ping'i, engelleme ve bildirme, depolama, hata durumları, yerel sohbetlerden farklar, Baileys karşılaştırması

---

## 1. Nedir (teknik olarak)

Interop, bir WhatsApp hesabının diğer mesajlaşma uygulamalarının ("integrator'lar") hesaplarıyla 1:1 ve grup mesajları alıp vermesini sağlar. İstemci bu uygulamalarla hiç konuşmaz. WhatsApp sunucularıyla konuşur; sunucular her üçüncü taraf hesabını `interop` domain'inde (gruplar: `interop.g.us`) sentetik bir JID olarak sunar. Tüm ifadeler çözülmüş (decompile) APK'nın statik analizinden gelir; hiçbir şey ağ üzerinde yakalanmadı veya bir sunucuya karşı çalıştırılmadı. Katmanlar: **found** = kodda veya kaynaklarda okundu, **inferred** = koddan çıkarıldı, **unknown** = çözülemedi. Obfuscate edilmiş adlar build'e özgüdür ve 2.26.41.6'da sabit string'lerden yeniden çözüldü (`InteropOptInManager/`, `InteropChatMessageHandler/`, `IntegratorManager/`, `w:interop`, `integrator_display_name`, `xwa2_interop_*`).

Bu build'deki durum:

| Parça | 2.26.41.6'daki durum |
|-------|----------------------|
| Kod | **Mevcut ve eksiksiz**: UI (10 activity artı fragment'lar ve dialog'lar), IQ istemcisi, MEX grup ve gizlilik op'ları, katı alma pipeline'ı, depolama, bildirim handler'ı |
| Sunucu anahtarı | **Varsayılan olarak kapalı**: kök AB flag'i **7495** varsayılanı `false`; kodda okunan her interop flag'inin varsayılanı `false` (bölüm 2) |
| Bölge | Ürün metni bunu Avrupa Bölgesi telefon numarasına sahip kullanıcılarla sınırlar; **istemci tarafında ülke kontrolü bulunmadı** (uygulama sunucu tarafında, flag 7495 ve integrator listesi üzerinden olduğu inferred) |
| Integrator'lar | **Koda gömülü yok**: kodda, kaynaklarda veya asset'lerde integrator adı ya da sabit integrator id'si yok; liste sunucudan gelir (bölüm 4) |

| Varlık | 2.26.41.6 adı | Rol |
|--------|---------------|-----|
| Geçit (`InteropRolloutManager`, ad bir getter'dan inferred) | `C32001Oa` | `A01` uygun, `A02` uygun ve birincil, `A00` gruplar, `A03` birleşik gelen kutusu |
| IQ istemcisi / builder'lar / parser'lar | `DmaInteropRPCManager` (`com.whatsapp.infra.smax.generated.dmainterop.outgoing`); `C31107Dfz` (case 20-23), `C31106Dfy`; `C214369Ee`, `C9EQ`, `C9EP`, `C214389Eg`, `A1J` | beş `w:interop` RPC'si, katı şema parse'ı |
| Integrator'lar | `C227409sQ` manager, `C23765ANa` store, `A3X` (`IntegratorInfo`), `InteropUiCache` = `SharedPreferencesOnSharedPreferenceChangeListenerC20390p5` (prefs `interop_ui`) | liste, opt-in durumu, UI önbelleği |
| JID'ler | `C99O` kullanıcı, `C41021lm` cihaz, `C55529Oy6` grup, `C9YC` parser; writer `C40411kn.A00`, reader `C24610wf` (tag 244) | bölüm 3 |
| Alma | `ENP` -> `C34471Exu` (`DecryptionCallbackInterop`) -> `C34720F4p` (`InteropChatMessageHandler`); `DTF` (9 alanlı plaintext), `EUQ` (`ParseInteropMessageParams`) | katı pipeline |
| Tür kaydı | `C32718EOz`; `FBN` metin, `FBK` görsel, `FBL` video, `FBJ` GIF, `FBH` ses, `FBI` belge, `FBM` tepki, `FBG` desteklenmeyen | protobuf <-> FMessage |
| Gönderme | `C33446EhE` (dal), `F6P` (`E2eMessageEncryptor`), `F6K` (`<meta>`) | giden |
| Gruplar / gizlilik | `InteropGroupsManager`, `C3R2`, yalnızca smali `C3Rb` / `C3Qh`; `C0WQ` (bildirimler); `InteropPrivacySettingsManager`, `C3Q4` / `C3Q1` / `C29664Cuh` | MEX |
| Opt-in | `C229349vm` (`InteropOptInManager`), `ARH`, `A4N`, `C224669lg` / `C24380wI` (bildirim), `PaaInteropMigrator` | sihirbaz, onay |
| Ping | `C1S0` içindeki anonim `X.0xL` (`InteropNotificationHandler`), `AbstractC32331E9w` içinde id 270 | bildirim |
| Analitik | `AnonymousClass590` | WAM 6684, 7044, 7168, 6680 |

---

## 2. Özellik geçidi

### 2.1 Geçit zinciri (found, `C32001Oa`)

| Metot | Koşul | Kullanım |
|-------|-------|----------|
| `A01()` | hesap, yaş deneyimi kuralları kapsamında bağımlı (dependent) hesap değil (`C14980fa.A00` -> `C08520Ne.A03()` -> `C08530Nf.A03()` false; bağımlı tür `EnumC08540Ng.DEPENDENT`) **ve** AB **7495** | her şey; sohbet listesi klasörü, rozet, oluşturma |
| `A02()` | `A01()` ve companion değil (`AnonymousClass091.BRD()` false, yani `registration_device_id` 0) | opt-in manager, ayarlar, integrator seçimi, bildirim handler'ı |
| `A00()` | `A01()` ve AB **15732** | "Yeni grup" girişi, grup gizliliği adımı |
| `A03()` | `A01()` ve AB **11479** | birleşik gelen kutusu adımı ve birleşik gelen kutusu |

`InteropSettingsActivity.onResume` (`finish()` çağırır), `InteropOptInSelectIntegratorsActivity.onCreate`, `InteropOptInManager` ve `w:interop` bildirim handler'ı `A02()`'yi yeniden kontrol eder.

### 2.2 AB flag'leri (found: id, varsayılan ve çağrı yerleri; adlar eski bir build'in ad tablosundan, id eşleşmeli, **inferred**)

| Flag | Eski ad (inferred) | Varsayılan | Okunduğu yer | Kontrol ettiği |
|------|--------------------|------------|--------------|----------------|
| **7495** | `IS_USER_INTEROP_ELIGIBLE` | false | `C32001Oa.A01`, `C224669lg.A01`, `C230679y0` (rozet), `RunnableC23952AUh` (Home), `C0Y5` | kök geçit; Home rozet durumu |
| **15732** | `INTEROP_GROUP_MESSAGING_ENABLED` | false | `C32001Oa.A00` | grup oluşturma, grup gizliliği adımı |
| **11479** | `WA_INTEROP_UNIFIED_INBOX_ENABLED` | false | `C32001Oa.A03`; id ayrıca `C33251Ee2` içinde kayıtlı | gelen kutusu türü adımı, birleşik gelen kutusu |
| **25512** | `INTEROP_CONTACT_MASTER_ENABLED` | false | `C0ZT`, `C51044MkK`, `C201508iH`, `C93z`, `InteropSelectChatTypeActivity` | "Yeni kişi" girişi, kayıtlı interop kişileri, ad çözümleme |
| **5760** | `INTEROP_PROTOBUF_VALIDATION_ENABLED` | false | `ENP.A00` | interop JID'lerini katı `InteropMessage` pipeline'ına yönlendirir (8.1) |
| **38723** | adsız | false | `EA0.A00` (descriptor) | interop grupları içinde sender key dağıtımı (log string'i `interop_group_skdm_processing_enabled`) |
| **23701** | `DMA_INFLATE_VIEW_ONDEMAND_ANDROID` | true | `C1R9` | sohbet listesi interop başlığının isteğe bağlı inflate edilmesi |

Varsayılanlarla tanımlı ama literal okuyucusu bulunmayan flag'ler (kullanım unknown): **3953** `INTEROP_CLIENT_UX_ENABLED`, **5759** `INTEROP_BOOTSTRAP_ENABLED`, **6613** `INTEROP_WS8_ENABLED`, **18670** `INTEROP_ADD_GROUP_PARTICIPANT_CLIENT_ENABLED`, **20999**, **11518**, **13532**, **14070** (hepsi false); **22752**, **24016**, **24256**, **23652**, **24275**, **24098** (`DMA_*` UI ayarı, hepsi true). Flag **11619** (`ENABLE_DMA_GROUP_JID`) varsayılan tablolarda yer almıyor. Mekanizma: WA_AB_PROPS.md.

### 2.3 AB dışı geçitler (found)

- Aşama **160**'ta onay bildirimi **20240306** (`C24380wI.A0D`): ayarlar yapılandırma ekranını yalnızca kabul edilmişse gösterir, aksi halde opt-in açılış ekranını gösterir (5.1).
- Bağımlı hesap (`C14980fa`): uygun değil; `PaaInteropMigrator` interop gruplarından ayrılır ve bildirimi sıfırlar (5.5).
- Birincil cihaz (`A02()`): companion'lar opt-in yapamaz veya yapılandıramaz.

---

## 3. Kimlik: JID'ler ve domain'ler

### 3.1 Domain'ler (found)

| Tür | Sınıf | JID türü | Format | Doğrulama |
|-----|-------|----------|--------|-----------|
| Interop kullanıcısı | `C99O` (`InteropUserJid`) | **22** | `{integrator}-{account}@interop` | bir tire (sonuncusu böler); integrator 1-3 basamak, başta `0` yok, int olarak parse edilir; account 1-15 basamak, başta `0` yok |
| Interop cihazı | `C41021lm` | **23** | `{integrator}-{account}:{device}@interop` | cihaz indeksi **0** olmalı, aksi halde `C09B` ("Interop device JIDs must have device index 0") |
| Interop grubu | `C55529Oy6` (`GroupJid`) | **28** | `{gid}@interop.g.us` | gid 1-20 basamak, ilk basamak 1-9, `-` yok |

- `C0DZ.A0W` = tür 22, `A0X` = 22 veya 23 (1:1), `A0V` = 28, `A0U` = `A0X` veya `A0V` (herhangi bir interop sohbeti); 128 sınıfta kullanılır. `C41021lm.getRawString()` her zaman `:0` yazdırır. Factory (`UserJid.JID_FACTORY.A04(str, "interop")`, `C9YC.A00`) herhangi bir kural ihlalinde `C09B` ("Invalid interop JID: ...") fırlatır.
- IQ yanıtlarındaki integrator id'leri 1-999 ile sınırlıdır (3 basamak kuralıyla aynı). Grup id'leri eski `creator-timestamp` biçiminde değildir; MEX grup op'ları gid'yi domain olmadan alır (`InteropGroupsManager.A00` `@...` kısmını atar).

### 3.2 Binary token (found)

Tag **244** `JID_INTEROP` (writer `C40411kn.A00`, attribute reader `C24610wf`): string `user` (hesap id'si veya gruplar için gid) -> u16 **device** -> u16 **integrator** -> byte **domain**.

Domain byte'ı: **0** = `interop`, **2** = `interop.g.us`; başka herhangi bir değer fırlatır ("invalid domain received for JID_INTEROP tuple"). Bir grup tuple'ı device 0 ve integrator 0 taşımalıdır (aksi halde "invalid interop group jid"). Reader, domain 0'ı `{integrator}-{user}[:{device}]@interop` olarak çevirir (device 0 ise atlanır). Tag **245** (diğer istemcilerde ayrı bir interop JID biçimi) bu build'de handler'a sahip değil (`C24610wf` / `C40411kn` grep'i).

### 3.3 Eşleme ve gösterim (found)

| Konu | Olgu |
|------|------|
| LID / PN | `WaJidMapRepository/setJidMapping refused mapping for interop JID`; bir interop JID kendi signal adresi ve sohbet id'sidir |
| Ad | ad kaynağı `INTEROP_NAME` (`C0Y7`), değer kişinin `display_name` alanından (`c06290Dn.A07().A00.A0b`); mesaj stanza parser'ı her mesaj için `notify` ve `display_name` okur (`AbstractC33377Eg6.A02`); interop push adları için `display_name` kullanımı inferred |
| Grup üyeleri | `w:g2` katılımcı parse'ı interop JID'yi katılımcı kaydında tutar (`C23201A1a` -> `C228499uF.A00(c99o, ...)`), ayrıca `display_name`, `lid`, `phone_number`, `join_time` |
| Profil verisi | profil fotoğrafı veya adı yok: "Profile name and photo are not available in third-party chats" (string); yalnızca integrator ikonu (8 MiB önbellek `cache/interop_image_cache`, loader `interop_image_loader`) |

---

## 4. Integrator'lar

### 4.1 Model (found)

Kodda, `res/` veya `assets/` içinde integrator adı, sabit id veya tanımlayıcı türü tablosu yoktur; hangi integrator'ların var olduğuna, id'lerine, adlarına ve grup yeteneğine sunucu karar verir. `A3X`: `A00` id, `A03` ad, `A02` durum (`ONBOARDING`, `ACTIVE`, `REMOVED`), `A04` ikon URL'si, `A05` optedIn, `A01` tanımlayıcı türü (`USERNAME`, `PHONE`, `EMAIL`), `A06` supportsGroupMessaging. Bir JID'nin integrator'ı: `C99O.A00` -> `C227409sQ.A00` -> `A3X`.

### 4.2 Getirme (found, `C31107Dfz` case 20, parser `C214369Ee`)

İstek `<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><integrator fetch="all"/></iq>` (`to` = sunucu JID'si, sınıf `C19380nJ.A00`). Sonuç: `<integrator_list opted_in="true"><integrator id status identifier_type name icon opted_in><features group_messaging/></integrator>...</integrator_list>` (attribute adları found; `features` node şekli `features/group_messaging` yolundan inferred).

Attribute eşlemesi: `status` = `onboarding` / `active` / `removed`; `identifier_type` = `username` / `pn` / `email`; `features` -> `group_messaging` = `true` / `false`; `opted_in` varsayılanı `true`. Parser sınırları: 0-999 integrator, id 1-999; `name` veya `icon` içermeyen girdi atılır; bilinmeyen durum veya tanımlayıcı türü fırlatır. IQ hataları: `bad-request` (400), `internal-server-error` (500) (`A1J.A02` / `A04`).

Yenileme coroutine'i (`C24110Aar` case 34, log `IntegratorManager/refreshIntegrators`) tabloyu (5.6) ve `group_capable_integrators` pref'ini yazar. Bulunan tetikleyiciler: opt-in ekranının açılması; genel `<ack error>` handler'ı (`C13X`), bir interop 1:1 mesajı reddedildiğinde tüm `integrator_display_name` satırlarını siler (`C24110Aar` case 35). Diğer tetikleyiciler çözülemedi.

---

## 5. Onay, opt-in, ayarlar

### 5.1 Onay bildirimi (found)

Bildirim id'si **20240306** bir gizlilik beyanıdır (`C24380wI`, sınıf `PrivacyDisclosureDataManager`). Aşama **160** = kabul edildi (`A0D`); 105-399 aşamaları "uygun/gösterildi" sayılır (`A02`). `InteropOptInManager.A01` (`C229349vm`):

```
A02() false -> log "interop is not enabled, stop"
notice 20240306 != 160 -> render notice (C32411Pr.A05); ARH.onUserOptedIn sets has_previously_onboarded and continues; dismiss / deny / error stop
else -> InteropOptInSelectIntegratorsActivity(entryPoint)
```

Aşama **162**'yi `PaaInteropMigrator` yazar (`C24380wI.A09(null, 20240306, 162, false)`); anlamı unknown (160 değil, dolayısıyla bildirim sonrasında kabul edilmemiş sayılır).

### 5.2 Sihirbaz (found, `A4N`, `InteropOptInSelectIntegratorsActivity`)

```
Select integrators (list from table, header "Select the third-party apps you want people to message you from.")
   ▼
[AB 11479] Unified inbox option (COMBINED | SEPARATED) ──► else skip
   ▼
[AB 15732] Group privacy setting ("Who can add me to third-party groups") ──► else skip
   ▼
InteropOptInManager.A01: notice not accepted -> consent notice (5.1); accepted -> straight on
   ▼  onUserOptedIn
SetOptInIntegrators IQ (full list)
```

Bildirim zaten kabul edilmişse (ayarlardan düzenleme), seçim ekranı iptal ve devam düğmelerini gizler ve `C201718ig.A00` doğrudan kaydeder (değişiklikte kaydetme inferred); gelen kutusu türü ve grup gizliliği yapılandırma fragment'ında ayrı satırlardır. Grup gizliliği adımının `A01` ile bittiği inferred (log `BaseInteropOptInViewModel onOptInContinue`). Giriş noktaları bir int'tir (`entryPoint`) ve WAM'a loglanır (5.6).

### 5.3 SetOptInIntegrators (found, `C31107Dfz` case 23, parser `C9EP`)

```xml
<iq type="set" xmlns="w:interop" to="s.whatsapp.net" id=".."><opt_in_integrators><integrator_list>
  <integrator id="12"/> ...      <!-- 0..999 entries, the full desired state -->
</integrator_list></opt_in_integrators></iq>   <!-- result: integrator_list/integrator[@id], each with an optional error child -->
```

İstemci işleme (`C24113Aau` case 40): integrator başına hatalar toplanır; tablo tek bir transaction'da yeniden yazılır (`opt_in_status` hepsi için temizlenir, sonra istenenler eksi başarısız id'ler için ayarlanır). Opt-out için ayrı bir stanza yoktur: opt-out dialog'ları ve "turn off" yolu aynı set'i daha kısa bir listeyle kullanır (başka opt-out stanza'sı bulunmamasından inferred; boş liste yolu izlenmedi).

UI hata eşlemesi (`InteropOptInSelectIntegratorsActivity.A0X`): **500**, **810**, **800** kodları -> "Apps can't be saved right now. Please try again later."; diğer veya null kod -> "Apps can't be saved right now."

### 5.4 Ayar ekranları (found, `AndroidManifest.xml`)

Ekranlar (hepsi `AndroidManifest.xml` içinde): Main / Optin / Config fragment'larıyla `InteropSettingsActivity` (bildirim kabul edilmemişse açılış, aksi halde yapılandırma; yardım FAQ'su `317021344671277`); `InteropOptInSelectIntegratorsActivity` (uygulamalar); `InteropUnifiedInboxOptionActivity` ("Manage inbox", COMBINED vs SEPARATED); `InteropGroupPrivacySettingUpdateActivity` ve `...AddBlocklistPickerActivity` (9.4); `InteropReachNotificationSettingsActivity` ("Third-party chat requests", 6.3); `InteropOptOutDialogFragment` / `...IntegratorDialogFragment` ("Turn off third-party chats?"); `InteropConversationsActivity` (klasör listesi); `InteropComposeSelectIntegratorActivity`, `...EnterInfoActivity`, `InteropSelectChatTypeActivity` (yeni sohbet / grup / kişi).

### 5.5 Opt-out ve migrator (found)

Opt-out yapıldığında mevcut sohbetler salt okunur olur (composer banner'ı "Third-party chats are turned off. You can't send messages in this chat, and you won't receive messages."). `PaaInteropMigrator` (`C0q`): hesap bağımlı hesap olduğunda (`C20K.A1W` = kısıtlı) **ve** bildirim kabul edildiğinde çalışır; `LeaveInteropGroup` çağırır (`groups_to_leave`, {200, 400, 401, 403, 404, 405} içindeki yanıt kodları tamamlandı sayılır), ardından bildirim aşaması 162'yi yazar. "PAA" açılımı inferred (yaş deneyimi); bağımlı bağlantısı found.

### 5.6 Saklanan durum ve analitik (found)

| Depo | Anahtarlar / şema |
|------|-------------------|
| prefs `interop_ui` | `unified_inbox_option` (UNKNOWN / COMBINED / SEPARATED), `who_can_add_me_to_interop_groups` (int), `who_can_add_me_to_interop_groups_hash`, `who_can_add_me_to_interop_groups_deny_list` (set), `optedInIntegratorNames` (set) + id başına ad anahtarları, `interop_reach_enabled` (varsayılan true), `interop_reach_integrators` (int dizisi), `interop_reach_notifs` (`id:name:display_name:t` set'i), `suspended_interop_groups` (gid set'i), `has_previously_onboarded`, `group_capable_integrators`; prefs `interop_badge_prefs`: `pref_interop_badge_disabled`, `pref_interop_badge_account_state`, `pref_interop_badge_third_party_chats_state` |
| tablo `integrator_display_name` | `integrator_id` INTEGER PK, `display_name` TEXT, `status` INTEGER, `icon_path` TEXT varsayılan `''`, `opt_in_status` INTEGER varsayılan 0, `identifier_type` INTEGER varsayılan 0, `group_messaging_supported` INTEGER; `opt_in_status` üzerinde index `integrator_opt_in_index` |
| diğer tablolar | `wa_block_list_interop` (`jid` üzerinde unique index); `raw_contact_id = -5` ve `jid LIKE '{id}-%@interop'` olan `wa_address_book` satırları (`SAVED_INTEROP_CONTACTS`), telefonun kişilerine yazılmaz |
| WAM | 6684 (banner teslimi), 7044 (onboarding akışı, oturum id'si `InteropOnboardingSessionIdManager`), 7168 (kullanıcı eylemi), 6680 (üçüncü taraf gelen kutusu); event 1158 `interopContactsSize`, `interopContactsSizePerIntegrator` taşır |

---

## 6. `w:interop` IQ set

`DmaInteropRPCManager`'ın beş RPC'si `MessageClientSmaxWrapper` üzerinden gider; her IQ `type`, `xmlns="w:interop"`, `to` = sunucu JID'si, `id` taşır.

| İşlem | Tür | Gövde | Sınır | Sonuç |
|-------|-----|-------|-------|-------|
| FetchIntegrators | get | `<integrator fetch="all"/>` | - | 4.2 |
| FetchUsers | get | `<users><user external_id integrator_id/></users>` | **1-20 kullanıcı** | 7.2 |
| SetOptInIntegrators | set | `<opt_in_integrators><integrator_list><integrator id/>` | 0-999 | 5.3 |
| GetReachabilitySettings | get | `<reachability_settings/>` | - | 6.3 |
| SetReachabilitySettings | set | `<reachability_settings enabled="true\|false"><integrator id/>...` | 0-999 | sonuç / hata |
| Block / unblock | set | `<blocklist><item action="block\|unblock" jid="{interop JID}"/></blocklist>` | - | sonuç; hatalar `IQErrorBadRequest`, `IQErrorInternalServerError` |

### 6.1 Engelleme ve bildirme (found)

Interop engellemesi `xmlns="w:interop"` kullanır (`C31106Dfy`, yardımcı `C9EF`, log `InteropBlocklistHelper/getInteropBlocklist/error code:`) ve `wa_block_list_interop` tablosunu kullanır. UI: "Blocked in third-party chats"; engelleme dialog'u, WhatsApp'ta engellenen kişilerin üçüncü taraf uygulamada kullanıcıya yine de ulaşabileceğini söyler. Spam bildirme genel spam akışını kullanır (`spam_flow`, `C9E2`) ve integrator başına dialog metni içerir. Bildirim yönlendirmesi: `AbstractC32331E9w` xmlns `w:interop`'u handler id **270**'e eşler; `EnumC32096E0u.NOTIFICATION_W_INTEROP` = `"w:interop"`.

### 6.2 Ping bildirimi (found, `C1S0` içindeki anonim `X.0xL`)

`<notification xmlns="w:interop" t=".."><ping display_name=".."><X id=".." name=".."/></ping></notification>` (`ping`'in ilk çocuğunun `X` tag'i kod tarafından kontrol edilmez).

Yalnızca `ping` adlı ilk çocuk kabul edilir (aksi halde log `unknown tag=`). `A02()` true iken `id:name:display_name:t` değerini `interop_reach_notifs` pref'ine ekler, `critical_app_alerts@1` kanalında yerel bir bildirim gönderir (gövde "Chatting with people on third-party apps is an optional WhatsApp feature in the European Region.", eylem "Manage requests", kapatma receiver'ı `InteropNotificationDismissReceiver`) ve WAM 6684 loglar. Sunucu tetikleyicisinin (bir integrator'dan biri kullanıcıya ulaşmaya çalıştı) olduğu, ayar metni "Get notified when someone wants to message you from a third-party app." üzerinden inferred.

### 6.3 Erişilebilirlik (found)

Ayarlar kullanıcı başına değil **integrator** başınadır (çocuklar `<integrator id>`, sınır 0-999). `enabled` varsayılanı `interop_reach_enabled` içinde `true`'dur. Interop JID'leri için presence abonelik kodu bulunmadı (inferred: erişilebilirlik onun yerini alır).

---

## 7. Kullanıcı keşfi

### 7.1 FetchUsers (found, `C31107Dfz` case 21, parser `C9EQ`)

Interop JID'leri yalnızca bu IQ'dan gelir; USync'in interop protokolü yoktur (WA_USYNC.md).

```xml
<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><users>
  <user external_id="alice@example.org" integrator_id="12"/>          <!-- 1..20 -->
</users></iq>
<!-- result -->
<users>
  <user jid="12-105012705411308@interop" external_id=".." normalized_external_id=".." integrator_id="12"/>
  <user external_id=".." normalized_external_id=".." integrator_id="12"><error code="404" text="item-not-found"/></user>
</users>
```

Kullanıcı başına sonuçlar: başarı `user[@jid]` (`C9DG`, jid `C99O` olarak parse edilir); `item-not-found` kod varsayılanı **404** (`C9DH`); `forbidden` varsayılanı **403** (`C9DF`); `internal-server-error` (`C9DE`).

Tüm IQ hataları: `bad-request`, `internal-server-error`. Sonuç listeleri `C9FA` içinde: bulunamadı, forbidden, sunucu hatası, çözümlenmiş harita `{(external_id, integrator) -> UserJid}`. İstek ve yanıt, 0 veya **20**'den fazla kullanıcıyı reddeder.

### 7.2 Tanımlayıcı girişi ve kayıtlı kişiler (found, `InteropComposeEnterInfoActivity`)

| Tanımlayıcı türü | UI | `external_id` olarak gönderilen değer |
|------------------|----|---------------------------------------|
| `USERNAME` | tek alan ("Enter Username") | metin |
| `PHONE` | ülke seçici + numara | ülke kodu ve numara birleştirilir (karakter başına filtre, kural izlenmedi) |
| `EMAIL` | tek alan | metin |

Akış: uygulama seç (`InteropComposeSelectIntegratorActivity`, tablodaki opt-in yapılmış integrator'lar) -> sohbet türü (`InteropSelectChatTypeActivity`: "New chat", AB 15732 ve integrator grupları destekliyorsa "New group", AB 25512 ise "New contact") -> id gir -> FetchUsers -> dönen JID'de sohbeti aç. String'ler: "This user can't be found" (bulunamadı), "This user is already a group member" (grup ekleme), "Couldn't create the chat. Please try again.".

AB 25512 ile `ContactFormActivity.verifyInteropIdentifierAndSave` id'yi FetchUsers ile çözer (`C24113Aau` case 41) ve bir `wa_address_book` satırı kaydeder (raw_contact_id -5); "Usernames and contacts added to third-party chats will not save to your phone."

---

## 8. Mesajlaşma

### 8.1 Pipeline seçimi (found)

Şifre çözme (`ENP.A00`): AB **5760** açıksa ve sohbet JID'si `A0U`'yu sağlıyorsa (interop 1:1 veya interop grubu), ciphertext `C34471Exu` (`DecryptionCallbackInterop`) tarafından işlenir; aksi halde normal callback'ler çalışır. `ENP`'nin işlediği ciphertext türleri yaygın olanlardır: **0** (`msg`), **1** (`pkmsg`), **2** (`skmsg`, sender key), **4** (bot yolu, interop değil). Dolayısıyla interop, yerel sohbetlerle aynı Signal oturumlarını ve sender key'lerini kullanır.

```
<message from="12-123[:0]@interop" ..><enc type=pkmsg|msg|skmsg v=2>...</enc></message>
   │  ENP.decryptMessage (Signal / sender key)
   ▼
C34471Exu.handlePlaintext
   │  remove padding (last byte = pad length; empty / zero / >= length fails, log DecryptUtil/removePadding)
   │  C33369Efy.A03(E0T.INTEROP_MESSAGE, ...)          ── message pipeline type "interop_message"
   ▼
C34720F4p (InteropChatMessageHandler)
   │  parse bytes as DTF (InteropMessage subset)
   │  unknown-field check -> failure 70
   │  C32718EOz.A00(EUQ) -> FMessage via type handlers; SKDM (group) processed if AB 38723
   ▼
store, receipt, notification
```

Hata raporlama: `C34720F4p.A00` `C33063Eaz(reason)` döndürür ve receipt yolunda `A0Y(null, key, reason, 491)` çağırır; `C34471Exu` geçersiz plaintext için `C33369Efy.A07(.., 491, reason, ..)` çağırır. **491** literal'i ikisinde de ortaktır (anlamı çözülemedi).

### 8.2 `InteropMessage` plaintext alt kümesi (found, `DTF`)

Plaintext tam `Message` **değildir**. `DTF` tam olarak şu alanları bildirir, numaraları tam `Message` ile aynıdır:

| Alan | Numara | Tür | Handler | Notlar |
|------|--------|-----|---------|--------|
| `conversation` | **1** | string | `FBN` | düz metin |
| `senderKeyDistributionMessage` | **2** | message | `C34720F4p` | grup id'si + axolotl SKDM; sohbet bir grupsa grup id'si sohbete eşit olmalı |
| `imageMessage` | **3** | message | `FBK` | |
| `extendedTextMessage` | **6** | message | `FBN` | link önizleme alanları |
| `documentMessage` | **7** | message | `FBI` | stanza `type` değeri `medianotify` iken değil |
| `audioMessage` | **8** | message | `FBH` | `ptt` ile sesli notlar |
| `videoMessage` | **9** | message | `FBL` (`gifPlayback` yok) / `FBJ` (`gifPlayback`) | |
| `reactionMessage` | **46** | message | `FBM` | |
| `ptvMessage` | **66** | message | bulunamadı | şema tarafından kabul edilir ve bilinmeyen alanlar için doğrulanır; kayıtta FMessage parser'ı yok (video-note alımı çözülemedi) |

Bilinmeyen alan kontrolü, bilinmeyen alan sayısını `DTF`'den ve görsel, video, PTV, ses, belge, extended text ve reaction alt mesajlarından reflection ile okur; 1 veya daha fazla sayı **70** hatasını döndürür. Dolayısıyla `DTF` dışındaki alanlar mesajı başarısız kılar: örneğin `messageContextInfo` (35), `protocolMessage` (12), sticker, contact, location, poll (şemadan inferred; belirli bir alanın etkisi denenmedi).

### 8.3 Desteklenen mesaj türleri ve sınırlar (found)

| Tür | Alma sırasında uygulanan kurallar (hata nedeni) |
|-----|--------------------------------------------------|
| Metin, video | `conversation` veya `extendedTextMessage.text`, **65536** karaktere kırpılır; link önizleme yalnızca `matchedText` metinde bulunan geçerli bir URL ise; başlık ve açıklama 65536'ya kırpılır; önizleme türü 0, 1, 4, 5, 6, 7'ye eşlenir; video ve GIF ortak medya parser'ı `C33395EgO.A05`'i paylaşır (`gifPlayback` `FBJ`'yi seçer) |
| Görsel | `mediaKey` zorunlu (16); `fileLength` >= 0 (13); `fileSha256` 32 byte (14); ayarlıysa `fileEncSha256` 32 byte (14); mime **yalnızca `image/jpeg` veya `image/png`** (17); `directPath`, genişlik, yükseklik kopyalanır; thumbnail üçlüsü (direct path, sha, enc sha) isteğe bağlı; progressive scan'ler 2-20 scan uzunluğu olduğunda ve `scansSidecar` uzunluğu / 10 sayıya eşit olduğunda ve toplam bir int'e sığdığında kabul edilir |
| Ses | `mediaKey` zorunlu (16); `fileLength` > 0 (13); hash'ler 32 byte (14); mime bilinen bir ses türü olmalı (17); `ptt` flag'i; `waveform` yalnızca 1-192 byte ise tutulur; `backgroundArgb`; `seconds` |
| Belge | `mediaKey` zorunlu (16); `fileLength` >= 0 (13); hash'ler 32 byte (14); `title` 65536'ya kırpılır; JPEG thumbnail boyut kontrolünü geçerse tutulur |
| Tepki | `key.id` ve `key.remoteJid` boş değil; `text` artı sıfırdan farklı bir edit version reddedilir (uyarı `edit version and text message are both set`); `senderTimestampMs` tutulur; `type="reaction"` olan bir stanza bir reaction mesajı üretmelidir (aksi halde hata **76**) |
| Yanıt / alıntı | `stanzaId`, `participant`, alıntılanan mesaj (yine `DTF` olarak parse edilir, `ContextInfoProtobufInterop`), `quotedType` içeren `ContextInfo`; gönderen tarafta `InteropContextInfoBuilder` alıntılanan mesajı özyinelemeli serileştirir |

Kabul edilmeyenler (9 alanın dışında): sticker'lar, kişiler, konumlar, anketler, etkinlikler, şablonlar, view-once. Ek seçici, interop sohbetleri için kişi, konum, anket, etkinlik, grup durumu, imagine, ödeme, pix ve remittance girişlerini gizler (`ConversationAttachmentContentView`'in `A0L`, `A0M`, `A0P`, `A0Q`, `A0R`, `A0T`, `A0U`, `A0X` kontrolleri); belge, kamera, galeri ve ses interop kontrolleriyle kapatılmaz (kaldığı inferred). Kaybolan mesajlar desteklenmez ("disappearing messages are not supported in third-party chats", varsayılan zamanlayıcı ayarından da hariç tutulur). Medya byte'ları normal WhatsApp medya yolundan gider (anahtar, hash'ler ve `directPath` mesajın içinde; indirme kaynağı analitik değeri 15 = `interop`).

### 8.4 Gönderme tarafı (found)

| Adım | Davranış |
|------|----------|
| Serializer | `C33446EhE`: sohbet JID'si tür 22/23 (`A0X`) interop serializer'ını kullanır (`C32718EOz.A01`, tür başına `ADs` ile, loglar `buildE2eInteropMessage`); diğer sohbetler normal builder'ı kullanır, dolayısıyla interop **grupları** (tür 28) normal builder'ı kullanır |
| Desteklenmeyen FMessage sınıfı | handler `FBG` -> göndermeden önce `E3G` 70 fırlatır; bir handler için yanlış sınıf -> `E3G` 0 |
| Görsel kontrolleri | mime `image/jpeg` veya `image/png` değilse `E3G` 17 (`null` `image/jpeg` olur); hash 32 byte değilse `E3G` 14; medya anahtarı yoksa `E3G` 16; stanza katkıcıları `F6B`, `F6G`, `F6I`, `F68`, `F69`, `F6H`, `F6M`, `F6X` için interop dalı yok (ekleme çözülemedi) |
| Encryptor (`F6P`) | interop sohbetleri (`A0U`) için encryptor `C33284Eea.A02`'yi atlar (cihaz listesi metadata'sını `AbstractC30999De0.A03` üzerinden ekler, inferred) ve `paddingBytes`'ı atlar (boyut AB 1723'ten) |
| `<meta>` (`F6K`) | interop sohbetleri için `content_type="add_on"` atlanır |
| Raporlama token'ı (`F6L`) | hedef bir interop cihaz JID'si olduğunda atlanır |
| Cihaz listesi / ADV | interop cihaz indeksi her zaman 0'dır; `DeviceADVInfoHandler` girişinde bir interop kontrolü içerir (`C24230w2`, erken çıkış inferred); çoklu cihaz fan-out mümkün değildir (inferred: kişi başına bir cihaz) |

Yerel mesajlardan diğer farklar: interop sohbetleri metin / medya / tepki türleri yerine `interop_message` pipeline türünü (`E0T`) kullanır; decrypt event'inde WAM sohbet türü değeri 5 (`AbstractC33424Egr`) ve `FNR` event'inde 6 (yerel 3 / 1); message-secret add-on'ları (anket oyları, şifreli tepkiler, bkz. WA_MESSAGE_SECRETS.md) 9 alan arasında olmadığından interop sohbetlerine ulaşamaz (inferred).

---

## 9. Interop grupları

### 9.1 Model (found)

Bir grup `{gid}@interop.g.us`'dir (tür 28). Üyeler WhatsApp hesapları (**LID** kullanıcı JID'leri olarak eklenir; ekleme yolunda found, oluşturma yolunun aynı olduğu inferred) ve interop JID'leridir. Grup metadata'sı `w:g2` yerine MEX'ten gelir: `C11410Yt.A0F` tür 28 için `GroupXmppMethods/sendGetInteropGroupInfo` çağırır. Durum `UNSET`, `ACTIVE`, `SUSPENDED`; askıya alınmış gid'ler `suspended_interop_groups` pref'inde tutulur. Composer banner'ları: askıya alınmış grup "You can't send messages to this group because all third-party members have left."; opt-out yapılmış veya çıkarılmış "... because you're no longer a member."

### 9.2 MEX operasyonları (found; doc id'leri `assets/whatsapp-android-mex_client_persist_ids.json` dosyasından)

| Operasyon | doc_id | Kök alan | Girdi | Çıktı / notlar |
|-----------|--------|----------|-------|----------------|
| `GroupsCreateInteropGroup` | `25726817620301611` | `xwa2_interop_group_create` | `input.participants[{jid}]` | `group`: `gid`, `creation_time`, `creator_v2`, `display_name`, `participants_v2`; konu gönderilmez |
| `LeaveInteropGroup` | `25346167795013271` | `xwa2_interop_group_leave` | `input.groups_to_leave[{gid}]` | grup başına `response_code`; {200, 400, 401, 403, 404, 405} nihai sayılır |
| `AddParticipantsToInteropGroup` | `25732168276369451` | `xwa2_interop_add_participants_to_group` | `input.gid`, `input.participants[{jid}]` | WhatsApp üyeleri önce PN'den LID'ye eşlenir; `null` LID çağrıyı iptal eder |
| `QueryInteropGroupInfo` | `32734144032867938` | `xwa2_interop_group_query_by_id` | `group_input.gid` | `state`, `gid`, `creation_time`, `creator_v2`, `participants_v2` |
| `InteropPrivacySettingsQuery` | `24849123668112654` | `xwa2_fetch_wa_users` -> `interop_privacy_settings` | kendi LID'si için `interop_privacy_settings_query_input{feature, dhash}` | `settings_data`, `dhash`, `denied_contacts[{jid}]` |
| `InteropPrivacySettingsUpdate` | `25421856497452763` | `xwa2_interop_privacy_setting_update` | `feature`, `setting` | `success` |
| `InteropPrivacySettingWithContactListUpdate` | `24913399124998598` | `xwa2_interop_privacy_setting_with_contact_list_update` | `contact_list_type`, `contacts`, `dhash` (yoksa `none`), `feature`, `setting` | `success` |

Oluşturma ve ekleme hataları "This group couldn't be created" / "Make sure everyone you add to this group has third-party chats turned on." / "A group with these members already exists." olarak yüzeye çıkar (string'ler found). Grup oluşturmak, seçilen integrator'dan en az bir kullanıcı gerektirir ("To create this third-party group, you need to select at least one %1$s user.").

### 9.3 MEX bildirimleri (found, `C0WQ`)

| Bildirim | Handler | Etki |
|----------|---------|------|
| `NotificationInteropGroupCreateUpdate` | `AbstractC23194A0r` dalı (log `CreateInteropGroupNotificationHandler/`) | yerel grubu `gid`, oluşturan ve katılımcılardan oluşturur |
| `NotificationInteropGroupParticipantsUpdate` (`Xwa2NotifyInteropGroupOnParticipantChange`) | `A0B` | katılımcıları `general_chat_auto_add` kaynağıyla ekler, ayrılan katılımcıları çıkarır; `C22300su.A15()` false ise erken döner (`no updates needed to gid=`) |
| `NotificationInteropGroupPropertyUpdate` | `A0C` | `state` ACTIVE veya SUSPENDED -> `suspended_interop_groups` |

### 9.4 Beni kim ekleyebilir (found, feature `GROUPADD`)

`C9U8` ayar enum'u: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `MYCONTACTS`, `MYCONTACTSEXCEPT`, `MYCONTACTS_AND_ENABLED_INTEROP_INTEGRATORS`, `NONE`. Kişi listesi varyantı yasak listesini taşır (`contact_list_type`, `contacts`). Metin: "You can only be added to third-party chats by people who either use or have selected the same messaging app." Ayar kendi LID'si başına saklanır ve `dhash` ile önbelleğe alınır; uygulama sunucu tarafındadır (inferred), istemci yalnızca ayarı sunar.

---

## 10. Sohbet listesi, thread modeli, UI

| Öğe | Olgu (found) |
|-----|--------------|
| Thread | interop JID başına (1:1) veya gid başına bir sohbet; normal sohbet tablolarında saklanır; ayrı thread tablosu yok |
| Klasör | `InteropConversationsActivity` / `Fragment`; sohbet listesinde başlık view'ı `InteropView` (`C31071Ju`, log `ChatListInteropChatsDelegate/`); uygun ve bildirim kabul edilmişse veya interop sohbetleri zaten varsa gösterilir; gelen kutusu COMBINED iken gizlenir |
| Gelen kutusu modu | SEPARATED: ana gelen kutusunda veya "More" menüsünde klasör; COMBINED: interop sohbetleri Chats sekmesinde listelenir (sohbet filtrelerinde `interop` filtre chip'i, `THIRD_PARTY_FILTER`) |
| Satır / arama | avatar üzerinde integrator adı etiketi ve ikon rozeti; üçüncü taraf sohbetleri arama sonuçlarına dahil edilmez |
| Banner / rozet | "You're messaging someone outside of WhatsApp. Third-party apps may have different security."; Home rozeti `pref_interop_badge_*` üzerinden, AB 7495 ile geçitlenir (`C230679y0`) |

---

## 11. Baileys (`baron-baileys-v2` 1.5.17, `src/Socket/interop.js`, `WABinary/decode.js`, kaynak okundu, hiçbir şey test edilmedi)

| Konu | Baileys | Android 2.26.41.6 |
|------|---------|-------------------|
| Integrator'lar | gömülü `12` (BirdyChat, email) ve `13` (Haiket, pn) | istemcide yok; sunucu listesi |
| Toplu sorgu | `INTEROP_BATCH_MAX = 256` | **20** (istek builder'ı ve yanıt parser'ı) |
| Opt-out | `<opt_out_integrators><integrator_list>` | böyle bir node yok; daha kısa listeyle opt-in IQ'su |
| Reachability set | `<reachability_settings enabled><user external_id integrator_id/>` | `<integrator id/>` çocukları |
| Onay | `tos` IQ `trackable id=20240306 result=105`, ardından `160` | bildirim 20240306 aşama 160 = kabul edildi (found); bildirim IQ'sunun wire biçimi izlenmedi |
| Binary JID | tuple 244 reader'ı domain = 0 değilse fırlatır; tag 245 işlenir | domain 0 **ve** 2 (gruplar) ile tag 244; tag 245 yok |
| Bildirimler | `stella_interop_enabled`, `peer_device_presence`, `ig_profile`, fbid ile `type="interop"` | `w:interop` handler id 270 yalnızca `ping`'i işler |
| Gönderme / alma | düz metin `conversation` olarak, raporlama token'ı atlanır; `Defaults/index.js` içindeki yorum: interop alımı uygulanmadı | 9 alanla sınırlı serializer; katı `InteropMessage` parser'ı; grup MEX id'leri ve bildirimleri kapsam olarak aynı |

Neden başarısız olur (yukarıda karşılaştırılan koddan inferred):

| Belirti | Neden | Düzeltme |
|---------|-------|----------|
| Interop grup JID'sinde decode hatası | tuple reader domain byte'ı 2'yi reddeder | domain 2'yi kabul et -> `{gid}@interop.g.us`, device ve integrator 0 iste |
| Karşı taraf mesajı bilinmeyen alan hatasıyla düşürür | 9'un dışındaki herhangi bir alan (örneğin `messageSecret` içeren `messageContextInfo`, `protocolMessage`) karşı taraf aynı katı parse'ı çalıştırıyorsa başarısız olur (inferred; Baileys interop gönderimleri bu alanlar için izlenmedi) | `Message`'ı yalnızca 1, 2, 3, 6, 7, 8, 9, 46 (ve 66) alanlarıyla oluştur |
| Opt-out etkisiz | `opt_out_integrators` istemcide yok | kalan id'lerle SetOptInIntegrators gönder |
| Companion oturumlarına hiçbir şey ulaşmaz | interop kişilerinin yalnızca device 0'ı var | interop'u birincil oturumda tut |

---

## 12. Hata durumları

| Belirti | Neden | Yer |
|---------|-------|-----|
| Interop ekranları hemen kapanır veya hiç görünmez | `C32001Oa.A02()` false: flag 7495 kapalı, bağımlı hesap veya companion cihaz | 2.1 |
| "Apps can't be saved right now" | SetOptInIntegrators hatası; 500 / 810 / 800 kodları "try again later" metnini alır | 5.3 |
| "This user can't be found" | FetchUsers `item-not-found` (404) | 7.1 |
| Geçersiz interop JID istisnası | integrator 1-3 basamak değil / başta 0, account 1-15 basamak değil, cihaz indeksi 0 değil | 3.1 |
| Grup oluşturulmadı / composer devre dışı | MEX oluşturma hatası veya yinelenen üye kümesi / opt-out yapılmış, grup askıya alınmış, artık üye değil | 9.1, 9.2 |
| Gelen mesaj düşürüldü, neden 70 / 13 / 14 / 16 / 17 / 76 / 26 | bilinmeyen alan veya handler'sız tür / kötü boyut / kötü hash uzunluğu / eksik medya anahtarı / geçersiz mime / reaction türü uyuşmazlığı / parse istisnası | 8.2, 8.3 |
| Grup SKDM'si yok sayıldı | AB 38723 kapalı (log `sender key distribution message skipped`) | 8.1 |
| Gönderme hatasından sonra integrator adları eksik | ack hatası `integrator_display_name`'i sildi | 4.2 |

---

## 13. Temel ayrımlar

| Karıştırma | Olgu |
|------------|------|
| `w:interop` vs USync | kişi keşfi `w:interop` üzerinde FetchUsers'tır (en fazla 20), bir USync protokolü değildir |
| `@interop` / `@interop.g.us` / `@g.us` | kullanıcı ve cihaz, grup, yerel grup; bir interop JID asla LID veya PN'ye eşlenmez |
| `InteropMessage` vs `Message` | alma 9 alan kabul eder; gönderme interop için context ve padding'i atlar |
| `trusted_contact` gizlilik token'ı | genel gizlilik-token işi (WA_TCTOKEN_CSTOKEN.md); bu build'de interop'a özgü kod bulunmadı |
| UPI "interop" | `IndiaUpiInterOpHybridActivity`, `IndiaUpiInteropSendToUpiActivity`, `isInterop` ödeme notu flag'leri ödeme özellikleridir, ilgisizdir |
| Compose / EXIF "interop" | `androidx.compose.ui.viewinterop`, `InteroperabilityIFDPointer` kütüphanelerdir |
| Uygun vs opt-in yapılmış vs onay | flag 7495 = uygun; integrator başına `opted_in` sunucudan gelir; onay = bildirim 20240306 aşama 160 |

---

## 14. Eksiksiz akış

```
[User]              [Client]                                   [WA server]              [Integrator app]
  │ Settings > Third-party chats
  ├──────────────────► A02(): flag 7495, primary, not dependent
  │                    notice 20240306 != 160 ──► show ──► accept ──► stage 160
  │ apps (+ inbox type, + group privacy)
  ├──────────────────► SetOptInIntegrators ─────────────────► opted_in list; table rewritten
  │ New chat > app > id
  ├──────────────────► FetchUsers (1..20) ──────────────────► jid 12-<account>@interop / 404 / 403 / 500
  │ send text / image / video / audio / doc / reaction
  ├──────────────────► restricted Message (no context, no padding), Signal encrypt, device 0
  │                    <message to=..@interop> ─────────────► bridge (inferred) ───► [Integrator app]
  │                    <message from=..@interop><enc/> ◄──────────────────────────── reply
  │                    ENP -> DecryptionCallbackInterop -> DTF parse (unknown field -> 70) -> FBx -> FMessage
  │ ◄──────────────── chat row, notification
  │                    <notification xmlns=w:interop><ping/> ◄─ server (trigger inferred)
  │ ◄──────────────── local notification "Manage requests"; reachability per integrator
  │ New group (flag 15732)
  ├──────────────────► GroupsCreateInteropGroup (LID + interop JIDs) ──► gid@interop.g.us
  │                    MEX notifications: create / participants / property; SUSPENDED -> composer blocked
```

---

## 15. Bilinmeyenler

| Konu | Durum |
|------|-------|
| Onay bildirimi IQ'sunun wire biçimi | izlenmedi; yalnızca aşama 160 (kabul edildi) ve 162 (migrator tarafından yazılır) biliniyor |
| Sunucu tarafı köprü, integrator'a teslimat, o taraftaki anahtar işleme | istemcide görünmez; istemci sıradan Signal oturumlarını ve sender key'leri kullanır |
| Interop kişileri için kimlik değişikliği / güvenlik numarası | izlenmedi |
| Interop sohbetleri için aramalar, anketler, düzenlemeler, geri almalar, kimlik değişikliği / güvenlik numarası | interop kod yolu bulunmadı (arama kodunda interop string'i yok); izlenmedi |
| PTV (`ptvMessage`) alımı | alan kabul edilir, parser bulunamadı |
| Hata yolundaki 491 literal'i; 810 / 800 hata kodları; opt-in ekranı dışındaki FetchIntegrators tetikleyicileri | çözülemedi |
| 3953, 5759, 6613, 18670, 20999, 11518, 13532, 14070 flag'lerinin okuyucuları | literal okuyucu yok; descriptor'lar üzerinden okunuyor olabilir |
| Interop kişilerine yönelik okundu bilgileri | `ClientPayload.interopData` (alan **38**, `C38671hT`: `accountId` 1, `token` 2, `enableReadReceipts` 3) şemada mevcut; bu build'de hiçbir şey onu doldurmuyor |
| Sunucunun Avrupa Bölgesi kuralını uygulayıp uygulamadığı | yalnızca UI metni; istemci kontrolü yok |
