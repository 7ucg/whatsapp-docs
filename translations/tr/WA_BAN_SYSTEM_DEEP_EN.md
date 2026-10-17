<!-- src-sha1: 7460884998f14495a9fdb811db77f25ed82ce6f6 -->
# WhatsApp Ban System — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-17
**Kapsam:** Ban akışı, WFAC yaşam döngüsü, spam sinyali toplama, GraphQL protokolü, itiraz sistemi, şüpheli işaretleme, önleme

---

## 1. Mimariye Genel Bakış

```
                         [Server]
                             │
       ┌─────────────────────┴──────────────────────────────┐
       ▼                                                     ▼
XMPP login <failure reason=…>                   MEX GraphQL (pull-based)
(HandlerThreadC12340b0.A13 → C45351tB,            │
 handled in C0ZH.handleMessage)                   ├── BizIntegrityQuery ──► BizIntegritySignalsManager
  │                                               │        └─► wa_biz_integrity_signals (SQLite, wa.db)
  ├─ 403 perm-ban ─► HGB.startPermanentBanFlow    │              ├── is_banned (INT)   (stored; no reader found)
  │      └─► BanAppealActivity (userban.ui)       │              ├── is_suspicious (INT)
  ├─ 416 / 402+code 106|107|109 (underage/U13)    │              ├── trust_tier (TEXT)
  │      └─► WfacManager.startUnderageBanFlow     │              ├── dhash (TEXT, server-supplied, opaque)
  ├─ 402 otherwise ─► SpamWarningActivity         │              ├── is_meta_verified (new in 2.26.41.6 vs report)
  ├─ 405 ─► pref software_forced_expiration (`t`)      │              ├── fmx_business_holdout_group (TEXT, new)
  └─ 406 ─► pref underage_account_banned            │              └── integrity_tags (JSON)
                                                  │
                                                  └── ban-status fetch (xwa2_fetch_wa_users, token)
                                                           └─► WfacBanRepository ──► SharedPreferences
                                                                 ├── wfac_ban_state = "BANNED" | "CHECKPOINTED" | "UNBANNED"
                                                                 ├── wfac_ban_violation_type
                                                                 ├── wfac_ban_violation_reason
                                                                 ├── wfac_ban_violation_source
                                                                 ├── wfac_last_ban_status_fetch_timestamp_ms (new)
                                                                 └── wfac_ban_status_token

  Main.A5W() (2.26.26.4: `Main.A5D()`; reads wfac_ban_state at start, registration state 21, log "main/me/wfac ban")
      └─► WfacBanActivity (hard ban UI; now `com.whatsapp.waffle.wfac.ui`, JADX pkg `p191ui`; intent built by `HBC`)

  SpamWarningActivity (pre-ban warning)       ◄── XMPP <failure reason=402> (C0ZH, type 2)
  SuspiciousFmxBottomSheetFragment (info sheet, opened from the FMX card buttons, see 7.2)
  SMB soft-enforcement banner                 ◄── XMPP business notification `biz_integrity_warning_notification` (see 7.4)
```

**Kritik bulgu (2.26.41.6'da düzeltildi):** ban durumu senkronizasyonu (WFAC) **MEX GraphQL üzerinden pull tabanlıdır**; ancak bağlantı anındaki ban ve uyarı *olayları* XMPP üzerinden, login `<failure>` node'unda gelir (reason 402/403/416/406, bölüm 8.1). SMB soft-enforcement uyarısı bir XMPP business bildirimidir. `<stream:error>` üzerinden ban sinyali bulunamadı (bu işleyici yalnızca `code` 515/516, `conflict type="device_removed"` ve `ack` kick'leriyle ilgilenir).

---

## 2. Ban Durumu Yaşam Döngüsü (WFAC)

### 2.1 Dört Durumlu Makine

| Durum | Değer | Anlamı |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | Yerel önbellek yok (tanınmayan herhangi bir string için de fallback) |
| `CHECKPOINTED` | 1 | Yumuşak kısıtlama, doğrulama gerektirebilir. Sunucu string'i `NO_APPEAL_OPENED`, `AbstractC38371GmM.A00` tarafından `CHECKPOINTED`'a eşlenir (yeni) |
| `BANNED` | 3 | Kesin ban, hesap kısıtlı, itiraz mümkün |
| `UNBANNED` | 2 | Tamamen işlevsel |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (intent extra 0/1/2 kept, anything else -1; stored only for launch_source 2/3; default -1 via `HLK`; category names for 0/1/2 not found in 2.26.41.6, so the earlier SPAM/PHISHING/UNDERAGE mapping stays unverified)
wfac_last_ban_status_fetch_timestamp_ms → LONG (throttle, new)
```

Prefs wrapper'ı: `HLK` (durum getter'ı `C36188FnW.A00` ile ayrıştırır: geçersiz string "Invalid BanState" fırlatır). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 Durum Geçiş Akışı

```
Client connects
    │
    ▼
wfac_ban_status_token present? → NO → UNKNOWN_IN_CLIENT (no check)
    │ YES
    ▼
Registration state == 21? (fully registered)
    │ YES
    ▼
GraphQL: xwa2_fetch_wa_users (with token) (still present, `AWS`, `C46770Kc0`)
    │
    ▼
Throttle: skip if last fetch < 5000 ms ago (refreshInterval) or a fetch is in flight (generation counter); 60 s timeout runnable (new)
    │
    ▼
Response parsed by handler `C40191HfD` (obfuscated name 2.26.41.6; response class `C42252Ic7` / `C204538nH`)
    │
    ├── Stores via SharedPreferences: "wfac_ban_state" = state_string (stale generation responses discarded)
    ├── Error codes 1-4 logged separately; unknown → -1 (found, `C40191HfD`)
    └── Writers of `wfac_ban_state`: this handler (server string stored as is, `WfacBanRepository/storeBanState`), and `WfacBanActivity.onCreate` (launch_source 2/3 → "CHECKPOINTED"; launch_source 4 with `appeal_decision` "banned"/"unbanned" → "BANNED"/"UNBANNED"). No code path from `is_banned` (BizIntegrity) to `wfac_ban_state` was found.
```

### 2.4 Ban Sıfırlama Sırası

Başarılı itiraz veya hesap serbest bırakıldığında (`WfacBanViewModel.A0x` / `C36188FnW`, resetRegistration):
1. Temizler: `wfac_ban_state`, `wfac_ban_status_token`, `wfac_ban_violation_*`, `wfac_last_ban_status_fetch_timestamp_ms`, `support_ban_appeal_user_banned_from_chat_disconnect` (yeni)
2. Kullanıcının oturumunu kapatır (finishAffinity)
3. Login ekranına yönlendirir

---

## 3. BizIntegrityQuery — GraphQL Protokolü

### 3.1 Teknik Ayrıntılar

| Parametre | Değer |
|-----------|-------|
| Query adı | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (değişti; önceden `25975613018777537`, 2.26.38.10'da rotasyona girdi, 2.26.41.6 persist-id kataloğunda doğrulandı; client_doc_id `14769534217004148908396994706`) |
| Şema | `whatsapp-android-mex` |
| Taşıma | MEX HTTP/2 POST → `/mex/query` |
| JID biçimi | `<shortNum>@lid` (örn. `1910@lid`) |

### 3.2 İstek

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): girdi nesnesi `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`, sonuç sınıfı `C48528LIw`. `privacy_token` yalnızca bir gate (`MZ4.A00`) eşleştiğinde ve saklı bir TC-token olduğunda eklenir. Yanıt (found, `C51015Mjl`): kök `xwa2_fetch_wa_users[]`, kullanıcı başına `integrity_signals_info` içinde `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers` (sic, birebir anahtar), `is_banned`, `is_suspicious`, `is_suspicious_start_chat`, `join_date_ms` (string, long'a ayrıştırılır), `phone_country_code`, `trust_tier` (enum `M5B`), `is_mv_subscribed` (`is_meta_verified` olarak saklanır), `meta_verified_info{mv_friction_eligibility}`, `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Aşağıdaki alan listesi 2.26.26.4 yeniden yapılandırmasıdır (inferred, yeniden doğrulanmadı; istek-değişkeni biçimi `$userJids`, 2.26.41.6 girdi biçiminden farklıdır):

```graphql
query BizIntegrityQuery($userJids: [ID!]!) {
  bizIntegrityQuery(jids: $userJids) {
    jid
    is_banned
    trust_tier
    is_suspicious
    is_suspicious_start_chat
    integrity_tags { tag, pipelineDS, taggedDates }
    dhash
    phone_country_code
    join_date_ms
    fb_linked_page_number_of_likes
    ig_linked_page_number_of_followers
    mv_friction_eligibility
    hide_safety_tools_for_business
    chat_row_id
    last_sync_ts
  }
}
```

### 3.3 Yanıt DTO'su — `BizIntegritySignals` (`C51530MtC`; 2.26.26.4'te C39833Hhl idi)

```
BizIntegritySignals(
  userJid, dhash, fbLinkedPageNumberOfLikes,
  igLinkedPageNumberOfFollowers, isBanned, isSuspicious,
  isSuspiciousStartChat, joinDateMs, phoneCountryCode,
  trustTier, isMetaVerified, mvFrictionEligibility, integrityTags,
  chatRowId, lastSyncTs, hideSafetyToolsForBusiness, fmxBusinessHoldoutGroup
)

Fields:
  integrityTags           → List of IntegrityTagInfo
  userJid                 → UserJid
  hideSafetyToolsForBiz   → Boolean
  isBanned                → Boolean  ← HARD BAN FLAG
  isSuspicious            → Boolean  ← SOFT ENFORCEMENT
  isSuspiciousStartChat   → Boolean
  isMetaVerified          → Boolean  (new)
  mvFrictionEligibility   → Boolean
  fmxBusinessHoldoutGroup → String   (new; stored as fmx_business_holdout_group, purpose unknown)
  chatRowId               → Long
  fbLinkedPageLikes       → Long (stored as REAL)
  igLinkedFollowers       → Long (stored as REAL)
  joinDateMs              → Long (stored as REAL)
  lastSyncTs              → Long
  dhash                   → String
  phoneCountryCode        → String
  trustTier               → String: "SUSPICIOUS" | "UNTIERED" | "TRUSTED"
```

### 3.4 IntegrityTags DTO'su

(`C51359MqA` listesi olan `C51222Mno`; serileştirme `LwI` içinde, biçim değişmedi)

```
IntegrityTagInfo {
  tag         → String
  pipelineDS  → Date (originally Long ms)
  taggedDates → List<Date>
}
```

**DB'deki JSON biçimi:**
```json
[
  {
    "tag": "automation_bulk_messaging",
    "pipelineDS": 1700000000000,
    "taggedDates": [1699000000000, 1699500000000]
  }
]
```

### 3.5 Tetikleyici Olaylar

| Tetikleyici | Usecase string'i |
|---------|---------------|
| Sohbet açma | `"START_CHAT_CONTEXT"` (birincil tetikleyici) |
| Mesaj gönderdikten sonra | gönderim sonrası hook |
| Uygulama başlangıcı / login | arka plan zamanlayıcısı |

### 3.6 Feature Flag'ler

| Flag ID | İşlev |
|---------|---------|
| 11061 | Şüpheli hesap tespiti tetikleyicisi (`N5r.A03`; mevcut; yalnızca doğrulanmış-ad seviyesi `ent:` ile başlayan kişiler için değerlendirilir) |
| 11064 | Start-chat güven sinyali uygunluğu (açık/kapalı) (`BizIntegritySignalsManager.A04`; mevcut; varsayılan false) |
| 11065 | Güven sinyali önbellek TTL'si, saniye cinsinden (`C51855N0t.A00`; varsayılan 86400, `C08J` içinde bulundu) |
| 12709 | İşletmesinin `hostStorage == 2` olduğu kişiler için uygunluk (`C197628ax.A06`); varsayılan false (mevcut) |
| 16349 | `BizIntegritySignalsManager.A04` içinde zorunlu-sorgu yolu (mevcut; varsayılan false) |
| 19793 | Bu tabloda yeni: `N5r.A02`, `C51855N0t.A02` içinde saklı sinyallerin yeniden kullanımını kapılar; amaç kullanımdan inferred; varsayılan false |
| 12840 | İhlal tipine göre anahtarlanmış JSON config, varsayılan `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`); tüketici bulunamadı; amaç anahtar adlarından (`max_dismiss_count`, `max_display_days`) ve SMB soft-enforcement banner'ının kullandığı tip string'lerinden (7.4) inferred |
| 19893 | FMX kartı sistem mesajı loglama (mevcut, `C198788cr`) |
| 26697 | BizIntegrity v2 (mevcut, `C34735F5e`) |
| 27269 | Gelen/giden mesaj sayısını ayırma (mevcut) |
| 34166 | start_chat_trust_signals yazıcısı (mevcut, `ContactInfoActivity`) |

`BizIntegritySignalsManager.A02` içindeki bellek önbelleği: girdiler 60000 ms geçerli (found).

---

## 4. Şüpheli İşaretleme — Ne Zaman, Neden, Nasıl, Önleme (2.26.41.6'da yeniden kontrol edildi; bulunamayan öğeler yerinde işaretlendi)

> **Ana bulgu:** BizIntegrity flag'leri (`is_suspicious`, `trust_tier`, `is_banned`) için istemci hiçbir şey hesaplamaz: bunlar GraphQL yanıtından (`C51015Mjl`) ayrıştırılır ve yalnızca render edilir. Bunlar için istemci tarafında eşik veya puanlama bulunamadı. Ayrıca, cihaz üstü bir model yerel scam kararları üretir (`odml_scam_alert_*`, 6.6, 7.6). BizIntegrity isteği yalnızca sorgulanan JID'leri, isteğe bağlı bir privacy token'ı ve bir telemetri bağlamını taşır (3.2); istemcinin yerel metriklerini başka bir yere yüklediği bulunamadı.

### 4.1 Kim karar verir?

```
Local inputs on the device (found):             Server response (found, 3.3):
────────────────────────────────                ──────────────────────────────
• message counts (in/out/threads)               • trust_tier
  via N54 logger (6.2)                          • is_suspicious / is_suspicious_start_chat
• on-device features isCountryMismatch,         • is_banned (stored, no reader found)
  mostRecentSenderScore (6.6)                   • integrity_tags, dhash, join_date_ms,
• BizIntegrity request: jid(s) +                  phone_country_code, FB/IG counts,
  optional privacy_token (TC-token)               is_mv_subscribed, mv_friction_eligibility
```

Yerel metriklerden BizIntegrity isteğine giden hiçbir ok istemcide yoktur (3.2). Kararı hangi sunucu tarafı sinyallerin ürettiği APK'dan görünmez (sunucu tarafı ML inferred). İstemcide BizIntegrity flag'leri için "X'ten fazla mesaj -> şüpheli" gibi **yerel eşik yoktur**.

---

### 4.2 Trust Tier Hiyerarşisi (sunucu tarafından atanır)

WhatsApp APK'sında derlenmiş enum olarak bulundu (2.26.41.6'da `M5B`; değerler değişmedi):

| Tier | Anlamı | Etki |
|------|---------|--------|
| `SUSPICIOUS` | En yüksek risk — aktif olarak işaretlenmiş | Tüm uyarılar aktif, UI sürtünmesi, olası gönderim engeli |
| `TIER_0` | En düşük meşru seviye (yeni hesaplar) | Yükseltilmiş sürtünme uygunluğu |
| `TIER_1` | Standart kullanıcı | Normal |
| `TIER_2` | Yükseltilmiş güven | Daha az sürtünme |
| `TIER_3` | En yüksek meşru güven | Minimum sürtünme |
| `UNTIERED` | Değerlendirme yok | Kontrol uygulanmaz |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | Bilinmeyen | Fallback |

**Kod düzeyinde kontrol** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 Kararın çevresindeki sinyaller

İstemci aşağıdaki veri noktalarını BizIntegrity isteğine eklemez (3.2). Tablo, her birinin istemcide nerede göründüğünü listeler; sunucunun bunları değerlendirip değerlendirmediği inferred. Önceki raporun "Risk weight" sütununun istemci tarafında kanıtı yoktu ve çıkarıldı.

| Sinyal | İstemcide göründüğü yer (2.26.41.6) | Rol |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | cihaz üstü feature (`integrityai.impl.InputFeatureProviderImpl`, flag 31535) | İsteğin değil, cihaz üstü modelin girdisi |
| `mostRecentSenderScore` | cihaz üstü feature (flag 31536) | Aynı |
| `dhash` | yanıt alanı, olduğu gibi saklanır | Sunucunun sağladığı opak string; hiçbir istemci kodu onu oluşturmaz (anlamı unknown; raporun önceki "device fingerprint" okuması inferred) |
| `join_date_ms`, `phone_country_code` | yanıt alanları | Saklanır; istemci eşiği yok |
| FB/IG sayıları | yanıt alanları (`fb_linked_page_number_of_likes`, `ig_linked_age_number_of_followers`) | FMX kartında gösterilir (7.5) |
| `integrity_tags` | yanıt alanı `{tag, pipeline_date_ms, dates_ms[]}` | JSON olarak saklanır; tag değerleri istemciye opaktır |
| Privacy token | istek alanı `privacy_token{tctoken, timestamp}` | İsteğe bağlı, yalnızca gate `MZ4.A00` eşleştiğinde ve bir TC-token saklıysa |
| Mesaj hacmi | yerel sayım (`N54`, 6.2) | Sunucuya yükleme bulunamadı |
| Broadcast limiti | flag 20278 varsayılan `{"max_messages": 10000, "farthest_time_days": 30}` | Tüketici bulunamadı (6.3) |

`isCountryMismatch` ve `mostRecentSenderScore`, istemcide bulunan iki somut ML feature'ıdır (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`, 2.26.41.6). Flag 31535 isCountryMismatch'i, 31536 mostRecentSenderScore'u sağlar (found).

---

### 4.4 GraphQL kontrolü ne zaman tetiklenir?

**Uygunluk gate'i** (found, `BizIntegritySignalsManager.A04`; sorgulanan JID sohbetin karşı tarafıdır):
1. Feature flag **11064** etkin (varsayılan false)
2. JID, hariç tutulan iki tipten biri değil (`AbstractC24760wu.A03/A04`: bot JID'leri ve sabit bir telefon numarası JID'si)
3. Şunlardan biri: kişi bir SMB işletmesidir (`N5r.A06`, doğrulanmış-ad seviyesi `smb:` ile başlar), veya flag **12709** açık ve kişinin işletmesinin `hostStorage == 2` değeri var (`C197628ax.A06`), veya (zorunlu çağrı, `A09`) flag **16349** açık ve `N5r.A04/A06` geçerli (`A04` = `!A01 && !SMB && !ENT`; yardımcı `N5r.A01`'in semantiği çözülmedi, dolayısıyla bunun hangi işletme olmayan JID'leri kabul ettiği açık)
4. Zorunlu olmayan yol için: önbellek süresi dolmuş veya yerel önbellek yok (`C51855N0t`)

Önceki rapora göre düzeltme: 2.26.41.6'da normal gate işletme hesaplarını atlamaz, onları seçer (SMB veya hosted); zorunlu yol (16349) başka JID'leri kabul edebilir. `A04`'ün JADX akışı kısmen yeniden yapılandırılmış, dolayısıyla bu okuma smali'den değil, derlenmiş şekilden ve yardımcı gövdelerinden gelir.

**Önbellek TTL'si:** Feature flag **11065**, saniye cinsinden, varsayılan **86400 (24 saat)** (found, `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**Batch boyutu:** GraphQL fetch yolunda 975-JID'lik parçalama yoktur (`BizIntegritySignalsManager.A03` JID listesini değiştirmeden iletir). 975 sabiti yerel SQL mesaj sayımı batch'ine aittir (6.2).

---

### 4.5 Bilinen integrity_tag değerleri

`automation_bulk_messaging` ve `spam` string'leri `C35896FgX` ve `ViewOnClickListenerC39711HTl` içinde bulunur; ancak orada BizIntegrity yanıtındaki `integrity_tags` ile değil, SMB soft-enforcement bildiriminin `type` değeriyle (`HAR.A07`, bkz. 7.4) karşılaştırılırlar. Ayrıca flag 12840 varsayılanının anahtarı olarak görünürler. İstemci `integrity_tags` değerlerini hiç sıralamaz; JSON blob'ları opak saklanır. `business_policy_violation`, 2.26.41.6'nın java_src, smali, assets veya res'inin hiçbir yerinde string olarak yoktur.

| Tag | Anlamı |
|-----|---------|
| `automation_bulk_messaging` | Soft-enforcement bildirim tipi (toplu/otomatik gönderim); bir `integrity_tags` değeri olduğu gösterilmedi |
| `spam` | Soft-enforcement bildirim tipi (spam) |

---

### 4.6 Somut olarak neyin şüpheliye yol açtığı — koddan inferred

2.26.41.6'da yeniden kontrol edildi: istemci aşağıdaki satırların hiçbiri için mantık, eşik veya ağırlık içermez ve BizIntegrity isteği bu metriklerin hiçbirini taşımaz (3.2). Tablonun tamamı **inferred** kalır (istemcide hangi sinyallerin var olduğundan sunucu tarafı davranışı üzerine bir tahmin). "Yeni hesap (< 24 sa)" satırının desteği yok: istemcide hesap yaşı kontrolü yoktur (bkz. 4.9 D).

| Davranış | Neden riskli | Ağırlık |
|----------|---------------|--------|
| Yüksek giden vs. gelen (yalnızca gönderme, yanıt yok) | Toplu erişim örüntüsü | Çok yüksek |
| Telefon ülkesi ≠ IP ülkesi | `isCountryMismatch = 1.0` | Çok yüksek |
| Birden fazla hesapta aynı dhash | Cihaz ban tetikleyicisi | Çok yüksek |
| Broadcast > 10.000 alıcı / 30 gün | Kesin limit, anında işaret | Yüksek |
| Yüksek `mostRecentSenderScore` (alıcıların şikayet etmesi) | ML geri bildirim döngüsü | Yüksek |
| Yeni hesap (< 24 sa, kişi yok) | Düşük güvenilirlik (istemci tarafında yaş kontrolü bulunamadı) | Yüksek |
| FB/IG bağlantısı yok + yüksek giden oranı | Eksik sosyal kanıt | Orta |
| Mevcut integrity_tags | Önceki ihlal etkisi | Orta–Yüksek |
| `is_reach_out = 1` + çok sayıda bilinmeyen sohbet başlatma | Soğuk iletişim örüntüsü | Orta |

### 4.7 SpamWarning neden kodları (ban öncesi uyarı)

2.26.41.6'da değişmedi (`SpamWarningActivity`: varsayılan neden 100, expiry varsayılanı -1; 101, 102, 103, 104, 106 üzerinde switch, default 105/diğerlerini kapsar).

Intent extra `spam_warning_reason_key` ile iletilir; XMPP login `<failure reason="402">` içindeki `code` özniteliğinden (>= 100) `expire`, `message`, `url` ile birlikte ayarlanır (found, `C0ZH.handleMessage` tip 2; bkz. 8.1):

| Kod | Tetikleyici | Geri sayım? |
|------|---------|-----------|
| 101 | Spam etkinliği tespit edildi | Evet |
| 102 | Forward ihlali | Evet |
| 103 | Status spam'i | Evet |
| 104 | Bot forward'ı | Evet |
| 105 | Genel / varsayılan | expiry = -1 ise kalıcı |
| 106 | Diğer ihlal | Evet |
| default | Bilinmeyen ihlal | expiry = -1 ise kalıcı, aksi halde geri sayım |

`expiry_in_seconds == -1` + çevrimiçi: anında finish (sunucu uyarıyı kaldırdı).

### 4.8 Şüpheli işaretlemeyle ilgili SpamFlow kategorileri

APK'da 97 kategori (found: `C9E2`, 96 girdilik dizi artı en sona eklenen `1_1_spam_banner_report`, indeksler 0 ila 96; önceki 92 sayısı ve tablodaki indeksler geçersizdir). Liste, SMAX node'u `spam_list` içinde ad ile serileştirilir (girdi başına `spam_flow` özniteliği, isteğe bağlı 24 karakterlik `wi_trace_id`), dolayısıyla indeks yalnızca istemci dizisindeki konumdur, wire değeri değildir. Yeni: `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_suspicious_banner_block/_trust`, `odml_scam_alert_fmx_card_block/_trust`, `biz_spam_banner_block`, `1_1_spam_banner_block`, `chat_fmx_card_block`, `group_spam_banner_report`, `left_group_spam_banner_report`. Doğrudan şüpheli durumuna bağlı olanlar:

| İndeks | Kategori | Anlamı |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | Sunucu tarafından şüpheli işaretlendi → FMX block |
| 24 | `chat_fmx_card_block_suspicious` | Şüpheli flag'i nedeniyle sohbet engellendi |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | Şüpheli için güvenlik araçları gösterildi |
| 70 | `odml_scam_alert_bottom_sheet_block` | Cihaz üstü ML scam → block |
| 71 | `odml_scam_alert_bottom_sheet_trust` | Cihaz üstü ML scam → trust |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | 1:1 spam banner'ı (sunucu tarafından işaretlendi) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | Güven sorusu (sunucu tarafından işaretlendi) |
| 89 | `user_initiated_chat_suspicious_banner_block` | Sohbet başlatma şüpheli banner'ı |
| 94 | `1_1_old_spam_banner_block` | Eski spam banner'ı |
| 96 | `1_1_spam_banner_report` | 1:1 spam şikayeti |

### 4.9 Koruma mekanizmaları — istemcinin gösterdikleri

Önceki "koruyucu faktörler" listesi, istemci tarafında desteği olmayan bir sunucu-ML okumasıdır. 2.26.41.6'nın gerçekte içerdiği:

#### A) İşletme durumu
Atlama değil. Normal uygunluk gate'i SMB kişilerini (ve flag 12709 altında `hostStorage == 2` kişilerini) seçer, bkz. 4.4. Flag 2923 (önceden: "işletme olmayan doğrulama anahtarı") bulunamadı: 2.26.41.6'nın java_src veya smali'sinde bu ID ile flag kontrolü ve config varsayılanı yok.

#### B) Meta Verified (mvFrictionEligibility)
Yanıt alanı `meta_verified_info.mv_friction_eligibility` (found, `C51015Mjl`), `mv_friction_eligibility` olarak saklanır. `is_mv_subscribed` ayrı olarak `is_meta_verified` şeklinde saklanır. FMX kartı (`C94p`) flag'i okur ve flag 15735 açıkken bir "learn more" bağlantısı ekler. Bunun sürtünme eşiklerini düşürdüğü istemcide görünmez (inferred).

#### C) Bağlı sosyal hesaplar (FB/IG)
`fb_linked_page_number_of_likes` ve `ig_linked_age_number_of_followers` tamsayı olarak ayrıştırılır (`optInt`) ve FMX kartında gösterilir (7.5). Boolean değil, sayıdır (found). Sunucunun bunları koruyucu olarak tarttığı inferred.

#### D) Hesap yaşı tolerans süresi
Bulunamadı. Yaşa benzeyen tek karşılaştırma, `last_sync_ts` üzerindeki önbellek TTL'sinin flag 11065 ile karşılaştırılmasıdır (4.4). `join_date_ms` saklanır ancak istemcide tolerans penceresi mantığı yoktur.

#### E) Whitelist / doğrulama listesi (flag 12709)
Değişti: `C197628ax.A06(userJid)` kontrolü, kişinin doğrulanmış-ad kaydındaki (`AnonymousClass119`) `hostStorage == 2` değeridir; sunucu tarafı bir ön onay listesi değil, yerel bir özelliktir. Kişiyi sorguya uygun yapar; erken dönmez.

#### F) hideSafetyToolsForBusiness (yanıttan alan)
Yanıt alanı `hide_safety_tools_for_business`, `hide_safety_tools_for_business` içinde saklanır. UI üzerindeki etkisi yeniden izlenmedi; yalnızca uyarı UI'ını gizlediği ve şüpheli durumunu değiştirmediği yönündeki önceki ifade doğrulanmadı.

---

### 4.10 Önleme — kodun ortaya koydukları

Bu bölüm, yukarıdaki alanlardan türetilmiş tavsiyedir. İstemcide bunların hiçbirini doğrulayan mantık yoktur; found olarak işaretlenenler dışında her öğeyi **inferred** sayın.

**Davranışsal (inferred):**
- Giden/gelen oranını dengeli tutun
- Numara ile ağ arasında ülke uyumsuzluğundan kaçının (istemci `isCountryMismatch`'i cihaz üstü modele besler, found; sunucu kullanımı inferred)
- Flag 20278'in broadcast config'inin altında kalın (10.000 mesaj / 30 gün; tüketici bulunamadı)

**Hesap kalitesi (inferred):**
- Bağlı FB/IG sayıları ve Meta Verified istemci tarafından gösterilir veya saklanır (found); karar üzerindeki etkileri inferred
- Yeni hesap penceresi (24 sa) ve dhash kara listeleme, hiçbir istemci kodu tarafından desteklenmiyor (bkz. 4.9 D ve 4.3)

**Teknik (found):**
- `privacy_token` (TC-token) BizIntegrity isteğine yalnızca gate `MZ4.A00` eşleştiğinde ve bir TC-token saklıysa eklenir

**Zamanlama (found):**
- Önbelleğe alınmış sinyaller, `last_sync_ts` flag 11065'ten (varsayılan 86400 sn) daha eski olana kadar yeniden kullanılır; manager ek olarak 60000 ms'lik bir bellek girdisi tutar
- Sinyaller, yeni bir yanıtla üzerine yazılana kadar `wa_biz_integrity_signals` içinde kalır

---

## 5. Yerel SQLite Veritabanları

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found, `C53116Nmn`, `_id` dahil 17 sütun): `is_meta_verified` ve `fmx_business_holdout_group` eklenir; `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `join_date_ms`, `last_sync_ts` REAL'dir, `mv_friction_eligibility` ve `is_meta_verified` için belirtilmiş varsayılan yoktur. Unique indeksler `biz_integrity_signals_jid_index`, `biz_integrity_signals_chat_row_id_index`; trigger `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). Store: `LwI` (etiketler `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`, `BizIntegritySignalsStore/saveBusinessIntegritySignals`). Aşağıdaki şema 2.26.26.4 sürümüdür.

```sql
CREATE TABLE wa_biz_integrity_signals (
  jid                               TEXT PRIMARY KEY,
  join_date_ms                      LONG,
  trust_tier                        TEXT,     -- "SUSPICIOUS" | "TRUSTED" | ...
  is_suspicious                     INTEGER,  -- 0/1
  is_banned                         INTEGER,  -- 0/1
  dhash                             TEXT,     -- device fingerprint
  phone_country_code                TEXT,
  ig_linked_page_number_of_followers INTEGER,
  fb_linked_page_number_of_likes    INTEGER,
  is_meta_verified                  INTEGER,  -- new in 2.26.41.6
  mv_friction_eligibility           TEXT,
  integrity_tags                    TEXT,     -- JSON array
  chat_row_id                       LONG,
  last_sync_ts                      LONG,
  hide_safety_tools_for_business    INTEGER,  -- 0/1
  fmx_business_holdout_group        TEXT      -- new in 2.26.41.6
);
```

Yazıcı/okuyucu: `LwI` (store), `BizIntegritySignalsManager.A06(UserJid)` bellek içi `ConcurrentHashMap`'i okur (found: `A06` bellek içi haritayı okur, `A07` lazy DB yüklemesiyle okur, `A0A` upsert yapıp kalıcılaştırır; 2.26.26.4'teki `A08`/`A01` adları kalktı)

### 5.2 `wa.db` — `start_chat_trust_signals`

```sql
CREATE TABLE start_chat_trust_signals (  -- schema `AI0`, columns unchanged (is_sender_suspicious, is_sender_new_account, created_ts); writer `C198788cr`
  jid                   TEXT PRIMARY KEY,  -- FK to wa_contacts
  is_sender_suspicious  INTEGER,           -- 0/1
  is_sender_new_account INTEGER,           -- 0/1
  created_ts            LONG
);

CREATE TRIGGER start_chat_trust_signals_contact_delete
  BEFORE DELETE ON wa_contacts
  BEGIN DELETE FROM start_chat_trust_signals WHERE jid = old.jid; END;
```

Okuyucu: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`; C2M7.A0K idi) → `(is_sender_new_account, is_sender_suspicious)` tuple'ı döndürür

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

Sorgu etiketi: `"GET_INTEGRITY_CHAT_INFO"` (`chat_row_id IN (...)` ile batch sorgu), store `C33O`, şema `C08970Ox` (indeks `integrity_chat_info_chat_row_id_index`, trigger `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). Değişmedi.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

2.26.41.6'da bulundu: şema `AHY` (sütunlar `jid`, `last_delivered_sort_id` LONG, `last_read_sort_id` LONG), `jid` üzerinde unique indeks `biz_integrity_chat_settings_index`, trigger `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). Rolü unknown.

---

## 6. Spam Sinyali Toplama (İstemci tarafı)

(2.26.41.6'da yeniden kontrol edildi; bulunamayan öğeler yerinde işaretlendi.)

### 6.1 dhash

`dhash`, BizIntegrity yanıtında (`integrity_signals_info.dhash`) bir string'dir ve `wa_biz_integrity_signals.dhash` içinde düz metin olarak saklanır. Hiçbir istemci kodu onu oluşturmaz: cihaz modeli, OS, uygulama sürümü, numara, saat dilimi, Android ID veya build-fingerprint girdisi bulunamadı ve hiçbir şey bunlardan birini yüklemez. Önceki "device fingerprint / sunucu tarafı kara liste" tanımı desteklenmiyor; anlamı unknown. APK'daki diğer `dhash` string'leri (block list, business opt-out) ilgisiz dizin hash'leridir.

---

### 6.2 Mesaj hızı

Found: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`, yardımcı `N54`) bir JID listesi için belirli bir zaman aralığında mesajları yerel olarak sayar, SQL alias'ları ile:
- `incoming_count`: `from_me = 0` olan mesajlar
- `incoming_threads_count`: alınan mesajlar için benzersiz `chat_row_id`
- `outgoing_count`: `from_me = 1` olan mesajlar
- `outgoing_threads_count`: gönderilen mesajlar için benzersiz `chat_row_id`
- Silinen mesaj sayısı: `integrity_deleted_chat_message_count` içinden `messages_count_after_privacy_token` (ayrıca `messages_count`, `outgoing_messages_count`)

Feature flag 27269, gelen/giden sayısının ayrı mı yoksa birleşik toplam olarak mı sayılacağını kontrol eder (aynı işleyicide bulundu).
Batch boyutu: SQL işleme çağrısı başına **975 JID** (found: `C20H.A1A(list, 975)`, bir SQLite değişken limiti parçasıdır, ağ batch'i değil).
Bulunamadı: günlük/saatlik gruplama, kişi başına oran; sayımdan sonra sayıların nereye gittiği izlenmedi.

---

### 6.3 Broadcast limitleri (işletme hesapları)

Feature config 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (`C08J`/`C09W` içinde varsayılan olarak bulundu).
- 30 günde 10.000 mesaj limiti config varsayılanıdır; bu JSON'un tüketicisi (gönderimden önce limiti uygulayan kod, `renewal_date`, alıcı başına throttling, pazarlama vs normal sınıflandırması) bulunamadı: `max_messages`/`farthest_time_days` anahtar string'leri yalnızca varsayılan tablolarda geçer ve `renewal_date` java_src içinde geçmez.

---

### 6.4 GAP enforcement (Global Abuse Prevention)

Found: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) feature flag 14837 kapalıyken atlanır ve daha yeni bir pazarlama mesajı geldiğinde SharedPreferences'ta (`C67902uK`) `LAST_MARKETING_MESSAGE_TIMESTAMP` saklar. Flag 25631 başka bir tetikleyici yolunu kapılar. "Global Abuse Prevention" açılımı kodda yok (adlandırma doğrulanmadı).

İzlenen durum (`ChatDescription`, found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Found: paket `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`, `WaFaReportScheduler`, `FaReportRunner`, `WaFaReportSubmitter`, `FaTeeConnection`, `FaTeeAcsRepository`, `FaAcsWarmer`). Raporlar ACS ile doğrulanan bir TEE bağlantısı üzerinden gider (`x-acs-token`, `x-acs-configid`, `x-acs-project-name` header'ları; OHAI public key fetch). Sonraki çalışma zamanı pref `fa_next_report_run_timestamp` içinde.
Bulunamadı: raporların içeriği. Önceki raporun metrik listesi (feature benimsenmesi, crash'ler, gecikme, RAM/depolama/OS, geofencing, oturum verisi, bağlantı tipi) kod olarak bulunamadı; rapor içeriği config tabanlıdır, dolayısıyla istemciden okunamaz.

---

### 6.6 ML feature çıkarımı (cihaz üstü scam tespiti)

Derlenmiş istemcide bulunan iki somut feature:
- `isCountryMismatch` (float 0.0/1.0): gönderici ülkesi ≠ alıcı ülkesi → **YÜKSEK RİSK**
- `mostRecentSenderScore` (float): gönderici için ML itibar puanı

Feature flag'leri 31535/31536 değerlerini kontrol eder (found). Sonuçlar ikincil ML puanlaması için sunucuya gönderilir (inferred).

---

## 7. UI Bileşenleri: Şüpheli, Uyarılar, Ban

(2.26.41.6'da yeniden kontrol edildi: `SpamWarningActivity` artık `com.whatsapp.userban.spamwarning`, `SuspiciousFmxBottomSheetFragment` `com.whatsapp.fmx` ve yeni alt sınıf `SuspiciousSmbFmxBottomSheetFragment`. 7.2, 7.4 ve 7.5 tetikleyici koşulları aşağıda düzeltilmiştir.)

### 7.1 SpamWarningActivity

Intent parametreleri:
- `spam_warning_reason_key` (int): neden kodu
- `expiry_in_seconds`: geri sayım (-1 = kalıcı)
- `spam_warning_message_key`: özel metin
- `faq_url_key`: FAQ bağlantısı

Neden kodları:

| Kod | Anlamı |
|------|---------|
| 100 | Genel spam uyarısı |
| 101 | Spam etkinliği tespit edildi |
| 102 | Forward ihlali |
| 103 | Status spam'i |
| 104 | Bot forward'ı |
| 105 | Genel / kalıcı |
| 106 | Diğer ihlaller |

`expiry_in_seconds != -1` → geri sayım sayacı gösterilir.
`-1` + çevrimiçi → anında finish (sunucu uyarıyı kaldırdı).

### 7.2 Suspicious FMX Bottom Sheet (`SuspiciousFmxBottomSheetFragment`)

Found: bir bilgi sayfası ("learn more" bağlantıları `about-blocking-reporting`, `examples-of-scams`), durum güdümlü bir engelleyici değil. FMX kartındaki şüpheli-durum düğmesine dokunarak açılır (`C93z.setupSuspiciousButtons`, SMB varyantı `C94p` `SuspiciousSmbFmxBottomSheetFragment`'ı açar) ve `C512928n` içinden (kişi bir işletmeyse SMB varyantı, `A0T()`), `AbstractC61092ir.A00` / `AbstractC61102is.A00` yardımcıları üzerinden.

Önceki raporun dört tetikleyici koşulu (`is_suspicious == 1`, `is_suspicious_start_chat == 1`, `is_reach_out == 1`, gönderim engeli olarak `chat_fmx_card_block_suspicious == 1`) desteklenmiyor: fragment'ın kendisi bunların hiçbirini okumaz ve `chat_fmx_card_block_suspicious` saklanan bir flag değil, bir SpamFlow kategori adıdır (4.8). Bulunanlar: `is_suspicious_start_chat` true olduğunda start-chat bağlamı gösterilir (`StartChatContextUtils`) ve FMX kartı `"SUSPICIOUS".equals(trust_tier)` hesaplar (`C94p`).

---

### 7.3 WFAC Kesin Ban UI'ı

| Sınıf | İşlev |
|-------|---------|
| `WfacBanActivity` | Giriş noktası, ban bilgisi + itiraz düğmesi |
| `WfacBanInfoFragment` | İhlal ayrıntıları + itiraz bağlantısı |
| `WfacBanDecisionFragment` | Kullanıcı eylemi (itiraz gönderildi) |
| `WfacUnbanDecisionFragment` | İtiraz sonrası onay |

Tetikleyici (değişti): `Main.A5D()` kalktı; eşdeğeri `Main.A5W()`'dir, başlangıçta `wfac_ban_state`'i okur ("UNBANNED" / "BANNED" / "CHECKPOINTED" üzerinde switch, kayıt durumu 21, log "main/me/wfac ban") ve `HBC` üzerinden `WfacBanActivity`'yi başlatır. Hiçbir SharedPreferences değişiklik dinleyicisi bulunamadı. `wfac_ban_state`, ban-durumu fetch işleyicisi ve `WfacBanActivity.onCreate` tarafından yazılır (2.3). Login-failure yolu (403) bunun yerine daha eski `com.whatsapp.userban.ui.BanAppealActivity`'yi (`HBB`) açar. 2.26.41.6: sınıflar artık `com.whatsapp.waffle.wfac.ui` içinde (ayrıca `WfacBanBaseFragment`); activity `HBC` intent yardımcısı ve `I1T` ekran geçişi (`transitionToScreen`) ile açılır.

### 7.4 SMB Soft Enforcement

Değişti: tetikleyici, `is_suspicious=true` + `"business_policy_violation"` içeren `integrity_tags` değildir (bu string 2.26.41.6'da yok). Bu, `biz_integrity_warning_notification > violation` çocuğu olan bir XMPP business bildirimidir (işleyici `AnonymousClass142`, bildirim id 202):

| Öznitelik | Kullanım |
|-----------|-----|
| `source` | ihlalin kaynağı (zorunlu) |
| `type` | ihlal tipi, örn. `automation_bulk_messaging`, `spam` (`C35896FgX` içinde karşılaştırılır) |
| `severity` | örn. `"severe"` banner metnini değiştirir (`C35896FgX`, `WABIEnforcementEducationFragment`) |
| `policy_url` | bağlantı hedefi (zorunlu) |
| `priority` | int >= 0 (zorunlu) |
| `status` | `active` (saklanır, sayaçlar sıfırlanır) veya `inactive` (kaldırılır) |

İstemci, `notificationType` değeri `"warning"` olarak sabit ve `bannerNotificationTimeStamp` = alınma zamanı olan bir `SMBSoftEnforcementNotification` (`HAR`) oluşturur ve aşağıdaki anahtarlarla bir JSON dizisini `smb_soft_enforcement_banner-all-json-<notificationType>` tercihi altında kalıcılaştırır (`C35894FgV`). Bildirim başına sayaçlar `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count` int tercihleridir.

```json
[{
  "source": "...",
  "type": "automation_bulk_messaging",
  "severity": "severe",
  "notificationType": "warning",
  "policyUrl": "https://...",
  "status": "active",
  "bannerNotificationTimeStamp": 1700000000000,
  "priority": 1
}]
```

Önceki raporun JSON'u (`notification_type: soft_enforcement`, `violation_type`, `education_url`, `action_required`) istemcide yoktur. UI: `com.whatsapp.banner.softenforcementsmb` içinde `SMBSoftEnforcementEducationFragment`, `WABIEnforcementEducationFragment`.

---

### 7.5 FMX Kartı (Trust Signal Card)

Found: tip 129 (`0x81`, `C57172Xr`) bir sistem mesajı `C198788cr` içinde oluşturulur ("Creating FMX card system message for chat", "ContactsProcessor/added contact info message"); flag 19893 orada yalnızca bir analitik olayını kapılar. `start_chat_trust_signals`'a asenkron yazma `C1P2.A01()` ile kapılanır (flag çözülmedi) ve `C65972r0` üzerinden çalışır. Kart (`C94p`) FB beğeni ve IG takipçi sayılarını ve Meta Verified sürtünme flag'ini render eder; `"SUSPICIOUS".equals(trust_tier)` şüpheli varyantı seçer. Hesap yaşı gösterimi ve "işletme/bilinmeyen kişi" gösterim koşulu bulunamadı.

---

### 7.6 ODML Scam Alert (cihaz üstü ML)

ACS token `"WA_ODML"` ile indirilebilir ML modeli (`OdmlModelDownloadClient` içinde bulundu, `ODML_MODEL_DOWNLOAD`, id `27301080136160169`, TTL 345600 sn = 4 gün; önbellek boyutu 64 bulunamadı). `ScamDetectionSettingsActivity` ile kullanıcı tarafından açılıp kapatılabilir. Huni, oturum ID'si / kaynak / giriş noktası intent extra'ları ile izlenir.

---

## 8. XMPP ve Stanza'lar (ban bağlamı)

(2.26.41.6'da login ve stream-error işleyicileri okunarak yeniden kontrol edildi; bölüm 8.1 düzeltildi. Önceki bir 2.26.35.2 kontrolü XMPP ban push'u görmemişti; bu gözlem aşağıdaki login-failure yoluyla geçersiz kılındı.)

### 8.1 Login `<failure>` ban ve uyarıları taşır

"Banlar yalnızca MEX GraphQL ile gelir" şeklindeki önceki iddia, bağlantı anındaki olaylar için yanlıştır. `HandlerThreadC12340b0.A13` login sonuç node'unu okur; `<failure>` için `reason` (int) alır ve bir `C45351tB` exception'ı oluşturur (found):

| `reason` | Tip | Okunan öznitelikler | İstemci tepkisi (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | Sunucu hatası, retry yolu |
| 402 | 2 (default) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `spam_warning_reason_key` = `code` (>= 100), `expiry_in_seconds`, metin, FAQ url ile `SpamWarningActivity` |
| 402 + `appeal_token` + `code` 106 | 13 | aynı | `ContextualAgeCollectionActivity` (extra'lar `appealToken`, `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | aynı | "U13 Banned PAA Pending" yolu (yönetilen-hesap prefs'leri, onboarding) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | Kalıcı ban: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (flag 19714 gecikmesinden sonra, ms cinsinden) |
| 405 | 3 | `t` (saniye) | `software_forced_expiration` pref'ini yazar |
| 406 | 5 | `code` | Pref `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`; `violation_reason == "u13_checkpoint"` `support_ban_appeal_user_banned_from_chat_disconnect`'i ayarlar |
| diğer | 0 | - | Logout ("exception-password" yolu) |

Tüm failure tipleri ayrıca isteğe bağlı logout UI özniteliklerini okur: `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text`, `logout_main_button_url`, `logout_secondary_button_text`, `logout_secondary_button_url`. `location`, yönlendirme için node'dan okunur.

`<stream:error>` (companion read interceptor, `C40601l6`): `code` 515 / 516, çocuk `conflict type="device_removed"` (deregister), çocuk `ack` (kick). Bana özgü çocuk bulunamadı. `<presence type="unavailable">` ve WebSocket kapatma kodları incelenmedi.

### 8.2 XMPP hata token'ları (binary sözlük)

Sözlük `AbstractC40911lb` (tek byte'lık `A00`, çift byte'lık `A01`). Önceki tablodaki token'ların varlığı:

| Token string'i | Sözlükte |
|-------------|---------------|
| `stream:error` | evet |
| `conflict` | evet |
| `not-authorized` | evet |
| `item-not-found` | evet |
| `server-error` | evet |
| `401` | evet |
| `policy-violation` | bulunamadı |
| `403` | token olarak bulunamadı (`reason` değeri 403 int öznitelik olarak okunur) |

Önceki raporun "Meaning" sütunu (örn. `403` = "Forbidden (ban-related)") inferred idi; yalnızca 403 anlamı artık yukarıdaki `<failure>` işlemeyle destekleniyor. Sözlükte ayrıca: `404`, `407`, `failure`, `locked`.

### 8.3 Kısıtlı hesaplar için IQ yanıtları

Bulunamadı. 2.26.41.6'nın java_src veya kaynaklarında ne `urn:ietf:params:xml:ns:xmpp-stanzas` namespace'i ne de "Account restricted" / "User banned" metinleri var ve sözlükte `forbidden` / `service-unavailable` token'ları yok. Önceki raporun XML örnekleri doğrulanmadı ve güvenilmemeli (açıklayıcı olabilirler). IQ başına hata işleme (örn. `item-not-found`, `not-authorized` ayrıştırıcıları `K3P`, `C23205A1e` gibi) kısıtlı hesaplar için izlenmedi.

---

## 9. Tam Veri Akışı (Uçtan Uca)

(2.26.41.6'da yeniden kontrol edildi: doc_id `28596420510007620`, girdi biçimi `query_input`, yukarıdaki sınıf adları. 2.26.26.4 diyagramındaki `isBanned` -> `wfac_ban_state` -> `Main.A5D()` okları, kodda böyle bir bağlantı olmadığı için kaldırıldı; bkz. bölüm 1 ve 2.3.)

```
[Open chat / send message]
           │
           ▼
  Check integrity_chat_info (is_reach_out?)
           │
           ▼
  Lookup start_chat_trust_signals (is_sender_suspicious? is_sender_new_account?)
           │
           ▼
  BizIntegritySignalsManager eligibility check — feature flag 11064
           │
    Flag active?
     YES │
         ▼
  BizIntegritySignalsGraphQLFetcher
    → HTTP/2 POST /mex/query
    → Variables: input{query_input:[{jid, privacy_token?}], telemetry{context:"INTERACTIVE"}}
    → doc_id: 28596420510007620
           │
           ▼
  Response → BizIntegritySignals DTO
           │
  wa_biz_integrity_signals (SQLite write, incl. is_banned, is_suspicious)
           │
    is_suspicious_start_chat? ──► start-chat context
    trust_tier == "SUSPICIOUS" ──► suspicious FMX card variant
           │                         └─► tap -> SuspiciousFmxBottomSheet (info only)
           ▼
  (is_banned: stored, no reader found)

  Separate path: XMPP login <failure reason=402|403|416> -> SpamWarningActivity /
  BanAppealActivity / WfacManager; WFAC state: Main.A5W -> WfacBanActivity
           │
           ▼
  [User submits appeal]
           │
           ▼
  Fetch purpose_public_keys (purpose_public_ek/ik/ik_sig, dummy ciphertext/nonce)
           │
           ▼
  Encrypt(form_data JSON {token, debug_info, description}, info "WA_INAPP_BAN_APPEALS", `C37414GLt`)
           │
           ▼
  Graph request to https://<host>.facebook.com/graphql by doc_id (section 10)
           │
           ▼
  Server review → wfac_ban_state update → WfacUnbanDecisionFragment
```

---

## 10. İtiraz İsteği (2.26.41.6)

`C37414GLt` içinde bulundu: istek `variables` JSON'u `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` ve `app_id` (`"dev.app.id"`) taşır; şifrelemeden önceki düz metin `{token, debug_info, description}`'dır; bağlam etiketi `"WA_INAPP_BAN_APPEALS"` (anahtar türetme info'su). Taşıma (found, `AbstractC40195HfH`): MEX değil, `doc_id` ve bir `access_token` alanı ile `https://<host>.facebook.com/graphql` adresine düz bir Facebook Graph POST'u. `C37414GLt`, `hg3.A04.A00()` true ise `doc_id` **38509456535312323**, aksi halde **5473316762755318** geçirir. `submitBanAppeal` işlem adı 2.26.41.6'nın java_src, smali, assets veya res'inde string olarak geçmez ve her iki doc_id de projenin sorgu kataloğunda yoktur, dolayısıyla ad doğrulanmadı. Gönderimden önce `C40191HfD`, şifreleme için anahtar materyalini sağlayan `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}` içeren ilk bir yanıtı ayrıştırır.

---

## 11. 2.26.26.4'e göre değişiklikler

| Öğe | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| BizIntegrityQuery doc_id | `25975613018777537` | `28596420510007620` (2.26.38.10'da rotasyona girdi) |
| İstek biçimi | `$userJids` listesi (yeniden yapılandırılmış) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| DTO sınıfı | `C39833Hhl` | `C51530MtC` (17 alan: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 sütun | + `is_meta_verified`, `fmx_business_holdout_group`; sayılar REAL |
| Store / manager | `BizIntegritySignalsManager.A08/A01` | store `LwI`, şema `C53116Nmn`, manager A02 60 sn bellek önbelleği |
| start_chat_trust_signals okuyucusu | `C2M7.A0K` | `C57342Yp` |
| Trust tier enum | kaydedilmedi, 7 değer | `M5B`, aynı 7 değer |
| WFAC UI paketi | `com.whatsapp.waffle.wfac` (düz) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| WFAC prefs | 5 anahtar | + `wfac_last_ban_status_fetch_timestamp_ms` (5 sn yenileme throttle'ı), sıfırlamada `support_ban_appeal_user_banned_from_chat_disconnect` temizlenir |
| Ban durumu ayrıştırma | 4 durum | aynı; `NO_APPEAL_OPENED` `CHECKPOINTED`'a eşlenir |
| Flag'ler | 11061/11064/11065/12709/16349/19893/26697/27269/34166 | hepsi mevcut; + 19793 (N5r.A02) |
| SpamWarning kodları 100-106 | evet | değişmedi |
| integrity_tags | `automation_bulk_messaging`, `spam` | değişmedi |
| SpamFlow | 92 kategori | 97; `odml_scam_alert_*`, `biz_spam_banner_block`, diğerleri eklendi |
| ML feature'ları | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | değişmedi, `integrityai.impl.InputFeatureProviderImpl` içinde |
| Broadcast limiti 20278 | 10000 / 30 gün | değişmedi |
| Bağlantı anındaki ban/uyarı olayları | "XMPP ban sinyali yok" | XMPP login `<failure>`: reason 402 (SpamWarning / U13), 403 (kalıcı ban -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | `wfac_ban_state` değişikliğine tepki verir | kalktı; `Main.A5W()` durumu başlangıçta okur (kayıt durumu 21) ve `HBC` ile `WfacBanActivity`'yi açar |
| `wfac_ban_state` yazıcıları | kaydedilmedi | ban-durumu fetch işleyicisi `C40191HfD`; `WfacBanActivity.onCreate` (launch source'a göre CHECKPOINTED / BANNED / UNBANNED); `is_banned`'dan bağlantı yok |
| BizIntegrity uygunluğu | "işletme hesapları kontrolü atlar" | SMB kişilerini (`smb:` seviyesi) veya `hostStorage == 2` (12709) seçer; zorunlu yol 16349; fetch'te 975-JID parçalama yok |
| 975 batch | GraphQL batch'i | yerel SQL mesaj-sayımı parçası (`N54`) |
| Flag 12709 | sunucu tarafı whitelist | yerel `hostStorage == 2` kontrolü |
| Flag 2923, 24 sa hesap yaşı toleransı, `dhash` oluşturma | iddia edilmişti | 2.26.41.6'da bulunamadı |
| `integrity_tags` değerleri | `automation_bulk_messaging`, `spam` | bu string'ler SMB soft-enforcement bildirim `type` değerleridir, `integrity_tags` değil |
| SMB soft enforcement | `business_policy_violation` tag'i + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`; saklanan JSON anahtarları `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`; flag 12840 |
| SpamFlow indeksleri/sayısı | 92, örn. `odml_scam_alert_bottom_sheet_block` = 65 | 97 girdi (`C9E2`), aynı adlar kaymış indekslerde (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | 4 veri koşuluyla açılır | FMX kartı düğmelerinden / `C512928n` içinden açılan bilgi sayfası |
| İtiraz isteği | MEX `submitBanAppeal` mutation'ı | Graph `https://<host>.facebook.com/graphql`, doc_id 38509456535312323 / 5473316762755318 ile, öncesinde `purpose_public_keys` fetch'i; işlem adı bulunamadı |
| `wa_biz_integrity_chat_settings` | bulunamadı | bulundu (`AHY`) |
| XMPP hata token'ları | `policy-violation`, `403` token'ları | sözlükte yok; `forbidden`/`service-unavailable` ve 8.3 metinleri yok |

2.26.41.6'da hâlâ açık: `wfac_ban_violation_source` 0/1/2 arkasındaki kategori adları; flag 20278 ve flag 12840'ın tüketicisi; yardımcı `N5r.A01`'in semantiği; WaFA raporlarının içeriği; kısıtlı hesaplar için IQ başına hata işleme (8.3); FMX kartında hesap yaşı gösterimi; `C1P2.A01()` arkasındaki flag.
