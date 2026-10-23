<!-- src-sha1: c6955a2c041a57de36c902dfa247b0b65dc0b530 -->
# WhatsApp WAM Analytics — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** Android WAM ("WhatsApp Metrics") telemetrisi — event modeli (event id'leri, alanlar, kanallar REGULAR / REALTIME / PRIVATE / kanal 3), Java loglama hattı, örnekleme ve event başına ağırlıklar, native runtime (`libwhatsapp.so`), ortak öznitelikler, diskteki buffer'lar, WAM wire formatı, düzenli yükleme (`w:stats` IQ), özel yükleme (credential IQ + ayrı transport), `wam_daily` ve günlük cron, private-stats id'leri ve rotasyonu, gizlilik yönetimi, feature flag'ler, öne çıkan event aileleri, Baileys karşılaştırması, bilinmeyenler

---

## 1. Bu build'de WAM nedir

WAM, istemci tarafında çalışan bir metrik hattıdır: tipli event'ler Java'da oluşturulur (veya native çağrı istatistiklerinden dönüştürülür), örneklenir, `files/wam/` altında saklanan ikili buffer'lara serileştiren bir native runtime'a verilir ve sunucuya yüklenir. Yalnızca giden telemetridir. Sohbet protokolündeki hiçbir şey ona bağlı değildir. Tüm ifadeler, decompile edilmiş APK'nın (`versionCode 264100600`), `libwhatsapp.so` içindeki native string'lerin ve bu build'in bir uygulama veri dizininde bulunan buffer dosyalarının yapısının statik analizine dayanır. Tier'lar: **found** = kodda veya bir buffer dosyasında okundu, **inferred** = çıkarım, **unknown** = statik olarak çözülemedi. Obfuscate edilmiş isimler build'e özgüdür ve 2.26.41.6 içinde kararlı string'lerden (log string'leri, `wam_*` event isimleri, IQ öznitelik değerleri) yeniden çözüldü.

| Varlık | 2.26.41.6 adı | Rol |
|--------|----------------|------|
| Event temel sınıfı | `C0Fc` | `code`, `samplingRate`, `bufferChannel`, `psId`; soyut `getFieldsMap()` (sayısal id'ler), `getFieldsMapForFalco()` (isimler), `getEventNameForFalco()`, `validate()` |
| Örnekleme tuple'ı | `C036300x` | ağırlık kademeleri; `A00` örnekleyicinin kullandığı ağırlıktır |
| Örnekleme çözümleyici | `C0Fg` + `C06580Fh` | `field-stats-events-sampling` prefs'inden event başına ağırlık override'ı |
| Logger (WAM runtime facade) | `C06650Fo` (`InterfaceC06640Fn`); `C40098Hdb` hem ona hem de Java Falco logger'ı `C40099Hdc`'ye dağıtır | `CNW` post, `CNI` örneklemeli post, `CXW` flush, `CUj` reset, `CXZ` flush ve bekle (2500 ms); init `RunnableC29323CoA` case 33 içinde |
| JNI köprüsü | `com.whatsapp.wamsys.JniBridge` | `jvidispatch*` Java'dan native'e, `jnidispatch*` native'den Java'ya |
| Ortak öznitelikler | `C06590Fi` (`CYl(value, attrId, channel)`), init `RunnableC29340CoR` case 0 içinde | kanal başına global öznitelikler |
| AB-props handler | `C28894Cgv` | `event_code` / `sampling_weight` dahil `<props>` ayrıştırır |
| Günlük event | `C0Fp` (`wam_daily`, id 1158) | cihaz ve uygulama durumu |
| Günlük cron | `C28643Ccj` (`WamDailyEventDailyCron`), alarm `BEL` içinde (`DailyCronAction`) | `C0Fp`'yi oluşturur ve post eder |
| Çağrı event'i | `com.whatsapp.fieldstats.events.WamCall` (id 462) | native çağrı istatistiklerinden oluşturulur, `C24895Anr` tarafından post edilir |
| Native runtime | `libwhatsapp.so` (`WAMRuntime`, `WAMBufferStore`, `WAMTransportRegular`, `WAMTransportPrivate`, `WAMPSIDProfile`) | buffer'lar, id'ler, yüklemeler |

WAM değildir, karıştırmayın (bkz. 17): Java tarafındaki Falco gölge logger'ı (`C40099Hdc`, `FFLogger`), `wam-event/<name>` etiketli crash ve log yükleyici, diğer projeler için ACS token'ları ve native çağrı istatistiklerinin kullandığı `fieldstats` sözcüğü (`prepare_wa_call_fieldstats`).

WAM içinde taşınan istemci bütünlüğü sinyalleri (`is_rooted`, `is_genymotion`, `is_whatsapp_plus_user`, öznitelikler 6251 ve 10255) [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) içinde açıklanır ve burada yalnızca referans verilir.

---

## 2. Event modeli

### 2.1 Event sınıfı (`C0Fc`)

Her event üretilmiş bir sınıftır; constructor `super(code, samplingTuple, bufferChannel, psId)` biçimindedir, örn. `wam_daily`: `super(1158, new C036300x(1, 1, 1, false), 0, -1)`, `getEventNameForFalco() = "wam_daily"`, `internalFalcoMigrationBatchNumber() = 12`.

| Üye | Anlam | Tier |
|--------|---------|------|
| `code` | sayısal event id'si (`wam_daily` için 1158, 460 `wam_login`, 462 `wam_call`, 854 `wam_message_send`) | found |
| `samplingRate` | `C036300x(a, b, c, flag)` şu şekilde saklanır: `A02=a, A01=b, A00=b, A03=c`; örnekleyici `A00 = b` kullanır. Varsayılan `C0Fc.DEFAULT_SAMPLING_RATE = (1, 20, 20)` | found |
| `bufferChannel` | 0..3, bkz. 2.2 | found |
| `psId` | `-1` = özel değil; aksi halde private-stats anahtar hash'i, bkz. 2.3 | found |
| `getFieldsMap()` / `getFieldsMapForFalco()` | sayısal alan id'sinden değere (native'e geçirilir) / snake_case isimden değere | found |
| `validate()` | ihlal listesi (`.nonnull` ve benzeri kurallar), bkz. 3.2 | found |
| `serialize(C3T8)` | gövde `throw new NullPointerException("serialize")`; serileştirme native'dir | found |

Alanlar Java kutulu tiplerini (`Boolean`, `Integer`, `Long`, `Double`, `String`) kullanır. Enum'lar ve timer'lar tamsayı olarak taşınır (yalnızca null / String / Integer / Long / Double / Boolean kabul eden öznitelik setter'ından çıkarım, inferred). `wam_daily` 218 sayısal ve 205 isimli slot içerir (13 sayısal slot yalnızca null'dur); önceki 2.26.35.8 sayımıyla aynıdır.

### 2.2 Kanallar

| `bufferChannel` | Event'ler (ayrıştırılan) | İsim (etiketler inferred; Java düz int kullanır) | Tier |
|-----------------|-----------------|------|------|
| 0 | 824 | REGULAR | found |
| 1 | 8 | REALTIME | found |
| 2 | 168 | PRIVATE (private-stats id gerekir, bkz. 2.3) | found |
| 3 | 8 | anonim realtime private-stats, native log string'lerinde "RTPS" (etiket inferred) | found / inferred |

Ayrıştırılan toplam: ayrı id'lere sahip 1,008 event sınıfı. Eşleme native'e değiştirilmeden geçirilir (`jvidispatchIIIIIOO` kanal argümanı 0..3). Başka herhangi bir değer `IllegalArgumentException("Unsupported channel type")` fırlatır.

REALTIME event'ler (id'ler): 2098 `wam_ui_action_real_time`, 5504 `wam_wefr_client_exposure`, 5278 `wam_android_test_realtime`, 6640 `wam_wefr_group_client_exposure`, 6088 `wam_restore_contacts_realtime_event`, 4290 `wam_wa_fs_chat_transfer`, 2872 `wam_xplatform_migration_export`, 6266 `wam_cac_client_event` (found).

Kanal 3 event'leri: 5164 `wam_wam_test_anonymous_realtime`, 7312 `wam_mm_signal_undisclosed`, 7352 `wam_mm_signal_realtime`, 6160 `wam_wamo_video_event`, 6158 `wam_wamo_ctwa_1pd_conversion`, 7956 `wam_wamo_promo_pog_impression`, 5712 `wam_wamo_promo_reporting_events`, 7350 `wam_wamo_alv2_link_click` (found). `C06650Fo.A01`, kodu iki sabit dizide (`AbstractC38512Gog.A00` 3 id, `A01` 5 id) bulunmayan bir kanal-3 event'ini düşürür. Bu 8 id tam olarak 8 kanal-3 event'idir, dolayısıyla bu build'de kontrol hiçbir şey düşürmez (id kümelerinden çıkarım, inferred).

### 2.3 Private-stats id'leri (`psId`)

| `psId` (int) | Native profil dosyasındaki anahtar string'i | Rotasyon (gün) | Event'ler | Tier |
|--------------|-----------------------------------|-----------------|--------|------|
| `-1` | yok (özel değil) | – | 832 (regular + realtime) | found |
| `0` | `none` (buffer global 6005 `none` string'ini tutar) | – | 94 (86 özel + 8 kanal 3) | found; "none" eşlemesi inferred |
| `113760892` | `default_ps_id` | asla (`-1`) | 66 | found |
| `56300709` | `id_pre_metrics` | asla (`-1`) | 1 (`wam_ps_app_launch`) | found |
| `248614979` | `id_ttl_daily` | 1 | 4 | found |
| `42196056` / `191000728` | `id_ttl_weekly` / `id_ttl_monthly` | 7 / 30 | 0 | found |
| `37887164` | `id_ttl_90_days` | 90 | 1 (`wam_clock_skew_difference_t`) | found |
| `152546501` | `group_exit_experience_id` | 30 | 4 | found |
| `216763284` | `group_safety_check_id` | 30 | 6 | found |

Anahtar string'leri ve rotasyon günleri sekiz `WAMMetadataPSIDProfile-*` dosyasından (bkz. 6.3), event sayıları ise event sınıflarından okundu.

### 2.4 Katalog genelinde ağırlıklar

Event başına etkin şema ağırlığı `A00` (event 1/ağırlık olasılığıyla tutulur ve ağırlık event ile birlikte saklanır):

| Ağırlık | Event'ler | Tipik örnekler |
|--------|--------|-----------------|
| 1 (her zaman) | 826 | `wam_daily`, `wam_registration_complete`, `wam_blocking_funnel` |
| 5 / 10 | 6 / 12 | `wam_message_send` (5), `wam_message_context_menu_actions` (10), `wam_ui_action_real_time` (10) |
| 20 | 135 | `wam_message_delete_actions`, `wam_message_high_retry_count`, `DEFAULT_SAMPLING_RATE` kullanan tüm event'ler (81) |
| 100 / 200 | 4 / 2 | `wam_login_stage_reliability` (100) |
| 1000 | 17 | `wam_message_stanza_receive`, `wam_call_stanza_receive`, `wam_status_stanza_receive`, `wam_iq_send`, `wam_push_latency`, `wam_db_perf` |
| 10000 | 4 | `wam_receipt_stanza_receive`, `wam_android_profilo_usage`, `wam_android_message_target_perf`, `wam_notification_highlight_result` |

Ağırlık bir feature switch değildir: sunucu bunu event başına override edebilir (8.2). Build-sabiti ağırlığa sahip bir event sınıflandırılmadı.

---

## 3. Java loglama hattı

### 3.1 Post yolu

`CNW` = `CNI(event, null, false)`: ağırlığı çöz (8.1), kanal-3 allowlist'ini çalıştır (`A01`), ardından WAM executor üzerinde (`C06600Fj.A01`) `X.1Fc` runnable'ını yürüt:

| Adım | Davranış | Tier |
|------|-----------|------|
| Runtime latch | `C06650Fo.A0K` (`CountDownLatch`) ortak öznitelikler başlatılana kadar executor'ı bloklar ("wamruntime/initializeCommonAttributes: runtime initialized") | found |
| Doğrulama | `event.validate()` yalnızca kanal 0 ve 1 için çalışır (doğrulama event sınıfı `C40251kT` için çalışmaz). Her ihlal, ihlal eden event kodu, rastgele bir oturum değeri ve `;` ile birleştirilmiş kural parçalarıyla bir `wam_wam_validation_error_event` (id 5560) olur | found |
| Logger modları (`A04`) | `3`: yapılandırılmış bir kod kümesindeki kodlar için reflection ile event'e `traceIdInt` (rastgele 64-bit) yazar; `10`: `C06630Fm`'den geçen event'ler için (Falco migration batch 1..16, deny list'te değil) `dedupKey` (rastgele 64-bit) yazar; `1` / `3`: ek olarak bir Falco event'i post eder (`_test$<name>` / `<name>_shadow`) | found |
| Dispatch | kütüphanenin yüklendiğinden emin olunduktan sonra `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fieldsMap)` | found |
| Log yükleme tetikleyicisi | AB string prop **31314** `"code:N;code:M"` tutar; post edilen kod için `Random.nextInt(N)==0` ise crash ve log reporter'dan `wam-event/<falco name>` etiketiyle cihaz loglarını yüklemesi istenir. Bu logları yükler, WAM buffer'ını değil | found |

`dedup_key` ve `trace_id_int` event şemasının alanlarıdır (`wam_login`, `wam_app_launch`, `wam_message_send` içinde bulunur); event başına rastgeledir ve kullanıcı tanımlayıcısı değildir (üreticiden çıkarım, inferred).

### 3.2 Doğrulama kuralları

`C0Fp` (`wam_daily`) içinde `ai_widget_installed` alanı, onu destekleyen bir Java üyesi olmadığı için her zaman ihlal olarak raporlanır (kural `daily .nonnull`), `default_after_read_enabled` ise üyesi null olduğunda raporlanır. Sonuç (inferred): kanal 0 üzerindeki her günlük event ayrıca doğrulama event'leri (id 5560) üretir.

### 3.3 Flush ve yaşam döngüsü tetikleyicileri

| Tetikleyici | Çağrı | Native işlem | Tier |
|---------|------|-----------|------|
| Bağlantı handler'ı bağlandı | `C0A4.BvO` -> `CKt(0)` | `jvidispatchIIO(4, 0, ctx)` | found |
| Bağlanıyor / bağlantı koptu | `BvP`, `BvQ` -> `CKt(1)` | `jvidispatchIIO(4, 1, ctx)` | found |
| Offline mesaj işleme tamamlandı (`XmppStateManager/offlineProcessComplete`, ayrıca `C0A2.A07`'yi temizler) | `BvR` -> `CXW(false)` yalnızca AB prop **9654** ise | `jvidispatchIO(10, ctx)` (aktif buffer'ları flush et) | found |
| Açık flush | `Bba()` -> `CXW(true)`; `CXZ()` flush eder ve 2500 ms'ye kadar bekler | `jvidispatchIO(10, ctx)` | found |
| Çağrı sonu | `C24895Anr.A02` `WamCall` post eder, ardından çağrı işaretliyse veya AB prop **16047** varsa `Bba()` | flush | found |
| Yeniden kayıt / hesap kaldırma | `C25100xS` ("RegistrationManager/reregister/rm-me") -> `CUj()` | `jvidispatchIO(12, ctx)` ("wamruntime/resetruntime") | found |

0/1 durum argümanı, native transport'lara yansıtılan XMPP bağlantı durumudur (log string'i "wameta/transport/status - %d"). 0 = bağlı anlamı native koddan değil callback eşlemesinden okunmuştur (inferred). `C0A2.A04` durumları: 1 bağlanıyor, 2 bağlandı, 3 bağlantı koptu, 4 durduruldu; `A07` bağlanmadan offline işleme tamamlanana kadar true'dur, dolayısıyla `A0N()` "bağlı ve hâlâ offline mesajları boşaltıyor" anlamına gelir.

### 3.4 JNI yüzeyi

| Yön | İmza | Amaç | Tier |
|-----------|-----------|---------|------|
| Java'dan native'e | `jvidispatchIOOOO(0, path, networkSession, ctx, config)` | runtime'ı başlat (log "WAJContextInitWAMRuntime"), bkz. 4 | found |
| Java'dan native'e | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)` | event logla | found |
| Java'dan native'e | `jvidispatchIIIOO(0, channel, attrId, String, ctx)` / `jvidispatchIIIO(4, channel, attrId, ctx)` / `jvidispatchIIIIO(1, channel, attrId, bool, ctx)` / `jvidispatchIIIDO` / int, long varyantları | ortak öznitelik ayarla (null, string, boolean, double, integer) | found |
| Java'dan native'e | `jvidispatchIIO(4, state, ctx)` / `jvidispatchIO(10, ctx)` / `jvidispatchIO(12, ctx)` | bağlantı durumu / flush / reset | found |
| Java'dan native'e | `jvidispatchIOOOO(4, ctx, signedCredential, acsPublicKey, configId)` | credential IQ'nun sonucu (hatada hepsi null) | found |
| Native'den Java'ya | `jnidispatchIO(6, byte[])` | bir regular buffer'ı `w:stats` IQ olarak gönder, `result` durumunda 1 döner | found |
| Native'den Java'ya | `jnidispatchIO(7, byte[32])` | `privatestats` credential isteğini gönder | found |

---

## 4. Runtime başlatma

`RunnableC29323CoA` case 33 bir config map oluşturur ve native init'i bir kez çağırır. Yol `<filesDir>/wam`.

| Config anahtarı | AB prop | Tip | Olası anlam | Tier |
|------------|---------|------|----------------|------|
| `platform_code` | – | int `2` | Android platform id'si | found |
| `beacon_probability` | **6977** | int | event başına native "beaconing" durumu için olasılık (`WAMBeacon`) | found; anlam inferred |
| `storage_size` | **9822** (x 1024) | long | buffer depolama üst sınırı (KiB'den bayta); native "no-enough-storage" loglar ve event'leri düşürür | found; birim inferred |
| `buffer_timeout` | **12399** | int | buffer rotasyon zamanlayıcısı | found; anlam inferred |
| `throttling_percentage` / `throttling_exempt` | **9457** / **9456** | int / string | yükleme kısıtlaması ve muaf listesi | found; anlam inferred, format unknown |
| `enable_extra_logging` | **14310** | bool | ayrıntılı native loglama | found |
| `enable_ps_upload_v2` | **15205** | bool (yalnızca açıkken) | özel transport üzerinde native "beginning upload v2 logic" | found |
| `enable_aggregation` / `aggregation_config` | **11981** / **11982** | bool (yalnızca açıkken) / string | kurallarıyla birlikte `WAGAggregation`'ı etkinleştirir | found; format unknown |

Aynı çağrı, `C25810yb` tarafından oluşturulan bir `networkSession` nesnesi alır; native HTTP wrapper'ları tarafından kullanımı inferred'dır. AB prop'larının varsayılanları sunucu tarafından iletilir ve çözülmedi.

---

## 5. Ortak (global) öznitelikler

Global öznitelikler `RunnableC29340CoR` case 0 tarafından `C06590Fi.CYl(value, attrId, channel)` ile, kanallar 0..3 için yazılır. Bir yardımcı dört kanalı birden ayarlar; diğerleri yalnızca 0 ve 1'i ayarlar. Bu nedenle özel kanallar (2, 3) daha küçük bir küme alır.

| Öznitelik id | Değer kaynağı | Kanallar | Tier |
|--------------|--------------|----------|------|
| 3 / 5 | `TelephonyManager.getNetworkOperator()` içinden ayrıştırılan MNC / MCC (5 veya 6 hane, yalnızca GSM) | 0 1 2 3 | found |
| 11 / 1659 / 1657 | platform kodu `2` / platform kodu `2` / sabit `3` | 0 1 2 3 | found |
| 13 / 15 / 17 / 21 | `Build.MODEL-Build.MANUFACTURER` / `Build.VERSION.RELEASE` (AB prop **12637** ile atlanır) / uygulama sürümü `2.26.41.6` / `true` (beta flag'i inferred; bu beta APK'da hard-coded) | 0 1 2 3 | found |
| 287 / 289 / 495 | `Build.MANUFACTURER` / `Build.MODEL` / bir cihaz string'i (çözülmedi) | 0 1 | found |
| 655 / 689 / 2617 | cihaz belleği ve sınıf metrikleri (`C38271gj`, `IJJ.A02/1048576`, `C38261gi`) | 0 1 2 3 | found; isimler inferred |
| 4473 | AB config anahtarı (son `<props>` yanıtındaki `ab_key`, her AB güncellemesinde yeniden ayarlanır) | 0 1 | found |
| 5029 | virgülle birleştirilmiş AB deney maruziyet id'leri (`BxP`); AB prop **31830** ile `ab-props` ve `ab-private-abprop`'un birleştirilmiş map'i | 0 1; ayrıca bir özel buffer'da (kanal 2) bulunur | found |
| 6251 / 10255 | uygulama imza kontrolü / Play installer flag'i | 6251: 0 1 2 3; 10255: 0 1 | found, bkz. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |
| 12017, 12027, 14507, 15265, 15611, 23, 707, 7335, 13293, 23043 | çeşitli uygulama durumu değerleri (12027 hesap durumu nesnesinden boolean, 707 `primary_platform_name` yalnızca 12027 true iken, 13293 = AB prop **3664**, 15611 WASafe sabiti (bkz. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)), 7335 init hook'ları çalıştıktan sonra `true`) | çoğunlukla 0 1; 13293 dördü de | found; anlamlar inferred veya unknown |
| 47 | commit zamanı, int32 saniye, native olarak eklenir | tümü | found (buffer dosyası) |
| 6005 | private-stats id değeri (UUID string veya `none`), native olarak eklenir | özel buffer'lar | found (buffer dosyası) |
| 2795, 105 / 6833 | native tarafından eklenir, yalnızca regular buffer'lar / `C21730rv`'den değer, yalnızca kanal 2 ve 3 | 0 / 2 3 | found; anlamlar unknown |

Java tarafından yazılan ortak öznitelikler arasında telefon numarası, JID veya hesap id'si yoktur. Regular transport, üzerinden gönderildiği kimliği doğrulanmış bağlantı aracılığıyla hesaba bağlanır (inferred, bkz. 9).

---

## 6. Native depolama

`libwhatsapp.so` string'leri (`WAMBufferStoreImpl`, `WAMPSIDProfileStoreImpl`, `WAMPrivateCredentialStoreImpl`, `WAMMetadataStoreImpl`) ve kurulu bir 2.26.41.6 veri dizininin dosyaları birbiriyle uyumludur.

### 6.1 Dizin `files/wam/`

| Dosya | İçerik | Tier |
|------|---------|------|
| `wamt-a-<channel>-0-<seq>` | aktif buffer, 65,559 bayt (önceden ayrılmış, sıfırla doldurulmuş); native string `wamt-o` rotasyona uğramış buffer'lara işaret eder (inferred) | found |
| `wam-metadata` | kanal başına sayaçlı `MTD` v4 container'ı; kanal 0 için saklanan sonraki sıra numarası, en yüksek dosya sıra numarası artı bire eşittir | found; yapı inferred |
| `WAMMetadataPSIDProfile-<n>-<keyHash>` | anahtar hash'i başına bir private-stats profili (8 dosya görüldü) | found |
| `WAMMetadataPrivateCredential-<n>` | özel transport için saklanan credential (`signed_credential`, anahtar, config id; v2, ~120 bayt) | found; yapı inferred |

Dosya adındaki üçüncü sayı bir stream id'sidir (log "wameta/buffer/rotated stream id: %d, channel: %d, buffer sequenceNumber: %d"; örnekte her zaman `0`), sonuncusu buffer sıra numarasıdır.

### 6.2 Buffer dosya düzeni

```
off  0   "WMT" 03                      container magic, version 3
off  4   u32 LE  used length           = (end of used data) - 31   (checked in 2 files)
off  8   u32 LE  ?                     counter, meaning unknown
off 12   u32 LE  event count           equals the number of event markers decoded
off 16   u32 LE  ?                     close to the used length (+4, +6, +31 in samples)
off 20   u32     ?                     check value (inferred), algorithm unknown
off 24   "WAM" 05                      WAM header: magic + protocol version 5
off 28   u8  0                         flag byte (0 in all samples)
off 29   u16 LE  buffer sequence       equals the number in the file name
off 31   u8  channel                   0 regular, 2 private in samples
off 32   TLV entries                   globals first, then events
```

Değer verilen her bayt için found; "?" ile işaretli alanlar unknown.

### 6.3 Private-stats profili

`WAMMetadataPSIDProfile-<n>-<keyHash>` (78 ila 90 bayt), düzen sekiz dosyanın hepsinden okundu:

```
u8 version(2) │ i32 LE keyHash │ i32 LE rotationDays │ u8 ? │ float64 LE (timestamp, inferred) │ u32 ? (1) │
u32 keyLen │ u32 uuidLen(36) │ key string (e.g. "id_ttl_daily") │ UUID string
```

Dosyalardan okunan rotasyon günleri: -1 (`default_ps_id`, `id_pre_metrics`), 1, 7, 30, 30, 30, 90 (bkz. 2.3). Native string'ler işlemleri `WAMPSIDProfileRotatePSID`, "psid delegated rotation was not persisted" ve bozulma kontrolleri (`invalid rotationInDays`) olarak adlandırır. UUID, özel buffer'ların global 6005'ine giren değerdir. Rotasyonun yerel saat mi yoksa sunucu tarafından mı yönlendirildiği unknown.

---

## 7. WAM wire formatı

Gerçek buffer'lar üzerinde doğrulandı: aşağıdaki tag şemasından yazılan bir decoder, iki buffer'ın (regular ve özel) global'lerini ve event'lerini artık bayt kalmadan ayrıştırdı.

### 7.1 Entry kodlaması

Her entry `[tag][field id][payload]` biçimindedir.

| Parça | Kodlama | Tier |
|------|----------|------|
| Tag alt nibble'ı | rol: `0` global, `1` event marker, `2` alan; VEYA `0x04` grubun sonuncusu; VEYA `0x08` alan id'si `u8` yerine `u16 LE` | found |
| Tag üst nibble'ı | değer tipi: `0x00` null, `0x10` int 0, `0x20` int 1, `0x30` int8, `0x40` int16 LE, `0x50` int32 LE, `0x60` int64 LE, `0x70` float64 LE, `0x80` string (u8 uzunluk), `0x90` string (u16 LE uzunluk), `0xA0` string (u32 LE uzunluk) | int 0/1, int8, int16, int32, string u8 ve u16 için found (hepsi buffer'lardan çözüldü); diğerleri şemadan ve Baileys encoder'ından inferred |
| Tamsayılar, string'ler, bayt sırası | en küçük tamsayı biçimi (0 ve 1 tag içinde yer alır); UTF-8 string'ler; her yerde little-endian (stanza codec'i big-endian'dır) | found |

### 7.2 Event marker

Bir event marker, alan id'si olarak event id'sini taşıyan rol `1`'dir. Değeri, buffer'larda pozitif saklanan örnekleme ağırlığıdır: şema ağırlığı 20 olan event'ler (`wam_secure_file_usage`, `wam_whatsapp_quick_promotion_client_eligibility_waterfall`) 20, ağırlığı 1 olanlar 1 taşır (found). Alanlar rol `2` ile izler (`0x04` son-alan flag'i kontrol edilmedi). Öznitelikler değiştiğinde bir global blok (rol `0`) yazılır, dolayısıyla global'ler event'ler arasında tekrarlanır (commit zamanı 47 defalarca yeniden yazılır, found).

IQ payload'ı 4 ila 126,976 bayttır (9). Bunun buffer'ın offset 24'ünden itibaren (`WAM` header'ından itibaren) olana eşit olduğu kodla gösterilmemiştir; düzenden ve Baileys'in aynı header'ı göndermesinden çıkarılmıştır (15) (inferred).

---

## 8. Örnekleme ve event başına ağırlıklar

### 8.1 Çözümleme (`C0Fg.A00`, sadeleştirilmiş)

```
override = prefs(code == 1094 ? "app_launch_event_sampling_weight" : "field-stats-events-sampling"[code], 0)
weight   = override != 0 ? override : schema.A00         // sampler becomes (|w|,|w|,|w|,|w|) for an override
keep     = random.nextInt(sampler.A00) == 0              // 1-in-N; null return = "(dropped)"
```

| Öğe | Değer | Tier |
|------|-------|------|
| Yerel override'lar | prefs dosyası `field-stats-events-sampling` (anahtar = event kodu) ve `app_launch_event_sampling_weight` (event 1094); ağırlık 1 her zaman tutulur | found |
| Native koruma | "wameta/logger event weight exceeds max, dropped"; limit native'dedir | found; değer unknown |
| Çağrı başına örnekleme | `WamCall`: event'in `logSampleRatio` alanı (id 1120) ağırlığı belirler, `new C036300x(i, i)` | found |

### 8.2 Sunucu iletimi (AB props yanıtı)

`C28894Cgv.CFS` AB-props sonucunu (`<props>` node'u) işler. Her `<prop>` çocuğu ya bir config prop'u ya da bir event örnekleme girdisidir:

```
<props ab_key hash refresh refresh_id delta_update>
  <prop config_code config_value config_expo_key/>    -> ab-props
  <prop event_code="854" sampling_weight="5"/>        -> field-stats-events-sampling
</props>
```

`hash` boş değilse örnekleme prefs'leri temizlenir ve tüm `event_code`/`sampling_weight` çiftlerinden yeniden yazılır; 1094 girdisi ayrıca `app_launch_event_sampling_weight` yazar (yoksa kaldırır). Yani sunucu event başına ağırlıkları kontrol eder ve ağırlıklar her event ile geri gönderilir, böylece sunucu sayıları ölçekleyebilir (alanın event ile birlikte taşınmasından çıkarım, inferred; sunucu kullanımı unknown).

Dolayısıyla sunucu WAM'ı AB props, örnekleme ağırlıkları ve özel credential aracılığıyla şekillendirir; yükleme IQ'sunun kendisinde hiçbir şey push edilmez (IQ yalnızca `result` alır).

---

## 9. Düzenli yükleme (`w:stats`)

Native, `JniBridge.jnidispatchIO(6, bytes)` çağırır. Java oluşturur ve gönderir:

```
<iq xmlns="w:stats" to="s.whatsapp.net" type="set" id="..">
  <add t="<unix seconds>">[binary: WAM buffer]</add>
</iq>
```

| Öğe | Değer | Tier |
|------|-------|------|
| Transport | normal kimliği doğrulanmış sohbet stream'i (`C10140Tq`), her IQ ile aynı | found |
| `t`, sınırlar, timeout | `t` = geçerli unix saniyesi (yalnızca 1,577,865,600..4,102,473,600 aralığında eklenir); payload 4..126,976 bayta karşı kontrol edilir; IQ timeout'u 32,000 ms (senkron bekleme) | found |
| Başarı | yanıt özniteliği `type == "result"` -> muhasebe `C0VI.A02(len, 32)`, 1 döner | found |
| Hata | diğer tip veya interrupt -> log "FieldStatsXmppImpl/error sending fieldstats IQ", 0 döner (yeniden denemeye native karar verir; "_WAMTransportManagerUploadFailedPermanently" mevcuttur) | found |
| Çağrı sırasında ertelenir | bir çağrı aktifse log "WamJniBridge/upload postponed" ile 0 döner; AB prop **15507** açıksa veya çağrı bir grup çağrısıysa ve AB prop **468** açıksa hariç | found (decompiler akışı, grup flag'inin varsayılanının false olduğu varsayıldı) |
| Offline işleme sırasında ertelenir | `C0A2.A0N()` (bağlı ve offline mesajlar henüz boşaltılmadı) ve AB prop **9654** açıksa 0 döner; 9654 kapalıyken IQ gönderilir | found |
| Hesap bağlantısı / sıkıştırma | payload'da hesap id'si yok, sunucu kimliği doğrulanmış oturumu görür; Java yolunda sıkıştırma yok | inferred / found |

Aynı prop 9654, `offlineProcessComplete` anındaki flush'ı da etkinleştirir (3.3). Birlikte: 9654 açıkken yüklemeler offline mesaj kuyruğu boşalana kadar bekler ve o anda bir flush çalışır (iki çağrı noktasından çıkarım, inferred; ertelenen bir denemeden sonraki yeniden deneme zamanlaması native'dir ve unknown).

---

## 10. Özel yükleme

Özel kanallar (2 ve 3) `w:stats` olarak gönderilmez. Native `WAMTransportPrivate`, anonim bir credential ile ayrı bir HTTP transport'u (`WCIHTTPImpl`) üzerinden yükler. Aşağıdaki her şey native log string'lerinden ve Java credential handler'ından gelir.

### 10.1 Credential isteği

```
<iq xmlns="privatestats" to="s.whatsapp.net" type="get" id="..">
  <sign_credential version="1">
    <blinded_credential>[32 bytes]</blinded_credential>
  </sign_credential>
</iq>
```

| Parça | Ayrıntı | Tier |
|------|--------|------|
| Gönderen | `JniBridge.jnidispatchIO(7, byte[32])`; IQ tracker'daki hata kodu 239, timeout 32,000 ms | found |
| Yanıt (`KRL.CFS`) | `<sign_credential t=..><signed_credential/><acs_public_key/><config_id/></sign_credential>`; üç bayt dizisi `jvidispatchIOOOO(4, ctx, ...)` ile native'e verilir; hata veya yanıt yokluğunda native null alır | found |
| Telemetri | event 2242 `wam_sign_credential` (regular kanal), durum 3 = hata, 1 = başarı ve geçen süre | found |
| Doğrulama ve depolama | native string'ler "Invalid signature received from server", "fails validation" (istemci imzayı doğrular); `WAMMetadataPrivateCredential-<n>` içinde saklanır, 401'de yenilenir ("send failed, renew credentials") | found |
| Şema | kör (blinded) istek, imzalı yanıt, ACS public key: anonim bir credential, dolayısıyla credential özel yüklemeleri hesaba bağlamaz | inferred |

Ayrı bir genel gönderici `C1N8`, diğer ACS projeleri için aynı namespace'i `<sign_credential version="2">` ve `project_name` ile kullanır (prefs `acs_token_*`); WAM yolu değildir.

### 10.2 Yükleme

| Öğe | Ayrıntı | Tier |
|------|--------|------|
| Endpoint'ler | native loglar "url/received", "fetch_endpoints/custom_endpoints - got endpoints: %d", "invalid_ps_endpoint, ignoring"; Java'da veya `libwhatsapp.so` içinde URL literal'i yok | found; listenin kaynağı unknown |
| Hata yönetimi ve zamanlayıcı | "try next endpoint", "have next credentials", "401, no more endpoints"; transport zamanlayıcısı ("timer/started - interval: %.1f seconds") "connection_ready" üzerine başlar, "connection_unavailable" üzerine durur | found; aralık unknown |
| Realtime özel | event başına buffer'lar: "create_buffer/realtime/buffer-created ... event id", "sendsingleeventimpl/realtime" | found |
| Header'lar, gövde çerçeveleme, sıkıştırma | görünmüyor | unknown |

Mod 9'daki Falco logger'ı `C40099Hdc`, kanal 2 veya 3 ya da bir psId'ye sahip event'leri kendi yolundan düşürür ve `wa:dropped_private_stats` olarak sayar (found), dolayısıyla özel event'ler o logger'a kopyalanmaz (inferred).

---

## 11. `wam_daily` ve periyodik event'ler

Event id 1158, Falco adı `wam_daily`, kanal 0, ağırlık 1, 218 sayısal / 205 isimli alan. Root, emulator, custom-ROM ve mod-client alanları için bkz. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md); burada yalnızca tesisat kaydedilir.

### 11.1 Zamanlama (found)

| Parça | Ayrıntı |
|-------|--------|
| Alarm | `BEL.A01`: sonraki yerel gece yarısı + rastgele jitter `nextInt(AB prop 5529)` (birim `C20D.A02` ile dönüştürülür), action `com.whatsapp.action.DAILY_CRON` |
| Telafi | action `com.whatsapp.action.DAILY_CATCHUP_CRON`, "last_daily_cron" bugünden olmadığı sürece 15 dakikada bir yeniden denenir |
| Koruma | cron bugün zaten çalıştıysa "too frequent" ile atlar (pref `last_daily_cron`); bir sohbet aktarımı sürerken tüm cron'ları atlar; mesaj deposuna ihtiyaç duyan cron'lar hazır değilse atlanır |
| Executor | bir DI `InterfaceC29983D2n` cron kümesi üzerinde yineler (`Bo5`); `C28643Ccj` (tag `WamDailyEventDailyCron`) yalnızca `anonymousClass091.BS3()` iken çalışır (hesap durumu, anlam çözülmedi) |

### 11.2 Doldurma

`C28643Ccj.Bo5` `new C0Fp()` oluşturur, bir DI kümesindeki her populator üzerinde `C4k(C0Fp)` çağırır (28 dosya bir `C4k(C0Fp)` populator'ı tanımlar), ardından varsayılan şema ağırlığıyla `CNW(c0Fp)` çağırır. Cihaz-flag populator'ı bu build'de yalnızca smali'dir (`smali_classes7/X/Cdt.smali`; decompiler başarısız olur) ve `last_daily_event` pref'ini (duvar saati ms) okuyup yazar, `time_delta_since_last_event` değerini atar. Decompile edilmiş dal delta'yı yalnızca 0'dan 1'e değiştirir, dolayısıyla bu alan için birim veya kadans iddiası yapılmaz. `last_daily_event` zamanlayıcı değildir (zamanlayıcı 11.1'deki alarmdır).

Aynı cron yalnızca Falco'ya ait bir `wam_daily_permission` event'i yayar (örneklenmiş): kişiler izin durumu, galeri izni, kamera / ses kaydı / kaba ve ince konum izinleri, OS bildirim ayarı, rehber boyutları, isteğe bağlı thread sayıları (AB prop **25576**) ve `profile_photo_is_set` (AB prop **34207**), `os_version` (found).

### 11.3 Diğer periyodik event'ler

Diğer uygulama başlangıcı ve periyodik event'ler: 1094 `wam_app_launch` (ağırlık `app_launch_event_sampling_weight` ile override edilebilir), 3300 `wam_ps_app_launch` (özel, `id_pre_metrics`), 3178 `wam_clock_skew_difference_t` (özel, `id_ttl_90_days`), `*_daily` ailesi (5798 `wam_reaction_daily`, 3680 `wam_polls_daily_stats`; tetikleyiciler inferred).

---

## 12. Gizlilik yönetimi

| Konu | Bulgu | Tier |
|--------|---------|------|
| Batch'lerde kalıcı id'ler | Java tarafından yazılan ortak özniteliklerde JID veya telefon numarası yok; `dedup_key` ve `trace_id_int` event başına rastgele; regular kanalın kimliği üzerinden taşındığı stream ile doğrulanır | found / inferred |
| Private-stats id'leri | `WAMMetadataPSIDProfile-*` içinde anahtar başına UUID, özel buffer'larda global 6005; rotasyon 1, 7, 30, 90 gün veya asla | found |
| Anonim credential | özel yüklemeler için sunucu tarafından imzalanmış kör token (10.1) | found; unlinkability inferred |
| Hash'lenmiş ve düz id'ler | hash'lenmiş id alanları mevcut (`hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids`, `message_key_hash`, `invited_user_hash`; hash fonksiyonu izlenmedi); JID tipli string'ler de mevcut (`reported_jid`, `e2e_sender_jid`; loglamadan önce hash'leme izlenmedi) | found (isimler), unknown |
| Reset | hesap kaldırma ve yeniden kayıt native reset'i çağırır (`jvidispatchIO(12)`); bununla PSID profillerinin sıfırlandığı gösterilmemiştir | found / unknown |
| Kullanıcı opt-out'u | WAM'ı devre dışı bırakan hiçbir ayar, string veya flag bulunamadı; resource'lardaki tek onay benzeri string destek tanılamalarıyla ilgilidir. Aranmayan kod yollarında bir ayar bulunabilir | unknown |
| Sunucu kontrolü | event başına ağırlıklar (8.2), AB props (13), `throttling_*` ve `beacon_probability` config'i (4); algoritmalar native | found; unknown |

---

## 13. Feature flag'ler (yukarıdaki kod yollarında okunan AB props)

| Prop | Tip | Kontrol ettiği |
|------|------|----------|
| **9654** | bool | offline işleme tamamlandığında flush (3.3); offline mesajlar boşalırken yükleme ertelenir (9) |
| **15507** / **468** / **16047** | bool | çağrı sırasında / grup çağrısı sırasında yükleme ertelenmez / çağrı event'lerinden sonra flush |
| **6977**, **9822**, **12399**, **9457**, **9456**, **14310**, **15205**, **11981**, **11982** | karışık | runtime init config anahtarları (bölüm 4) |
| **31314** | string | event kodu başına `"code:N;..."` log yükleme tetikleyici oranı |
| **5529** | int | günlük cron jitter'ı |
| **12637** | bool | OS sürümü, üretici ve eşlik eden öznitelikleri atlar (15, 287, 21, 12027, 707) |
| **31830** / **25576** / **34207** | bool | öznitelik 5029'da birleştirilmiş özel AB listesi / isteğe bağlı `wam_daily_permission` alanları |
| **34494..34507, 35169, 35170** | – | `AbstractC38513Goh.A01` içindeki dizi (16 id, Falco migration batch'leri 1..16 ile aynı sayı); kullanım inferred |

Tüm değerler sunucu tarafından atanır; varsayılanlar çözülmedi.

---

## 14. Öne çıkan event aileleri

İsimler Falco isimleridir; id'ler ve kanallar event sınıflarındandır. Alan listeleri `getFieldsMapForFalco()` içindeki isimli alanlardır.

### 14.1 Mesajlar

| Event | id | Kanal / ağırlık | Öne çıkan alanlar |
|-------|----|-----------------|------------------|
| `wam_message_send` | 854 | 0 / 5 | 89 alan: `message_send_result`, `message_send_t`, `message_type_str`, `e2e_ciphertext_type`, `e2e_ciphertext_version`, `is_pq`, `is_lid`, `retry_count`, `resend_count`, `message_is_forward`, `message_is_fanout`, `message_distribution_type`, `participant_count`, `device_count`, `message_key_hash`, `is_view_once`, ephemerality, edit/revoke, bot ve private-AI alanları |
| `wam_message_receive` | 450 | 0 / 20 | 58 alan: `message_receive_t0..t2`, `message_queue_time`, `message_is_offline`, `offline_count`, `stanza_process_count`, `padding_bytes_size`, `message_addressing_mode`, `server_addressing_mode`, `session_scope`, sticker ve kişi kartı alanları |
| `wam_e2e_message_send` / `_recv` | 476 / 478 | 0 / 20 | `e2e_successful`, `e2e_failure_reason`, `e2e_destination`, `group_encryption_state`, `enc_retry_count`, `pq_receive_gate_state` |
| `wam_e2e_message_decrypt_fail_sender` | 3524 | özel (ps `none`) | `e2e_sender_jid`, `e2e_failure_reason`, `retry_count` |

### 14.2 Çağrılar

`WamCall` (id 462, kanal 0) native istatistiklerden oluşturulur (`ConvertFieldStats`, "can not construct com/whatsapp/fieldstats/events/WamCall") ve yaklaşık 1,700 isimli alana sahiptir (Falco map'inde 1,716 `put` noktası). `WamJoinableCall` id 2572'dir. Örnekleme `logSampleRatio`'dur (alan 1120) ve event çağrı sonunda flush edilir (3.3). Diğer çağrı event'leri: 2582 `wam_call_stanza_receive` (ağırlık 1000), 3452 `wam_call_critical_events`, 4568 `wam_call_user_journey`. Çağrı signaling'in kendisi [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) içindedir.

### 14.3 Login ve kayıt

| Event | id | Alanlar |
|-------|----|--------|
| `wam_login` | 460 | `login_result`, `login_t`, `connection_origin`, `connection_t`, `login_dns_resolver`, `login_ip_source`, `login_port`, `login_resolved_pop`, `login_socket_provider`, `noise_protocol_version`, `retry_count`, `server_error_code`, `passive`, `long_connect`, `network_is_vpn`, `android_keystore_state`, `pending_acks_count`, `unprocessed_message_count` (30 slot); bkz. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) |
| `wam_reg_init` / `wam_registration_complete` | 2046 / 1342 | init zamanlamaları (`contacts_sync_t`, `groups_init_t`, `total_t`); `registration_t`, `addressbook_size`, `contacts_permission_authorization_status`, `device_identifier`, `google_account_list_hashed_reg`, `invited_user_hash`, `is_new_jid`, profil resmi ve izin alanları dahil 30 alan |
| `wam_account_encryption_attestation` | 8164 | ad attestation sonucuna işaret ediyor (inferred); bkz. [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |

### 14.4 Spam, report, block

Akışlar [WA_REPORTING.md](WA_REPORTING.md) ve [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) içindedir (`wam_wfacp_ban_action`, id 5028); WAM tarafı:

| Event | id | Kanal | Alanlar |
|-------|----|---------|--------|
| `wam_spam_report_perf` | 6310 | 0 | `report_spam_flow`, `report_status`, `report_attempt_count`, `report_duration_ms`, `report_error_code` |
| `wam_report_conversation_context` | 4608 | 0 | `reported_jid`, `spam_flow`, `estimated_num_messages_sent/received`, `is_chat_maybe_suspicious`, `is_in_addressbook`, `first_entry_point`, `num_call_msgs_to_report` |
| `wam_blocking_funnel` / `wam_reporting_funnel` | 4920 / 4924 | 0 | `block_flow_action`, `hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids` |
| `wam_reporting_token_validation_failure` | 5466 | 0 | `reporting_token_validation_failure_reason`, `reporting_token_version`, `is_part_of_group_history` |
| `wam_reporting_token_validation_failure_sender`, `wam_reporting_token_additional_client_validation` | 6094, 6702 | 2 (`default_ps_id`) | gönderen tarafı varyantları |
| `wam_message_template_blocks` | 3002 | 2 (`default_ps_id`) | business template engelleme nedenleri |

### 14.5 Deneyler

`wam_wefr_client_exposure` (id 5504, realtime) maruziyeti `exposure_key`, `device_exp_id`, `user_lid`, `guest_id`, `is_canonical_ent_present`, `sent_with_daily` ile loglar. Bir kullanıcı LID alanı taşır (found; sunucu kullanımı unknown). `wam_ui_action_real_time` (2098, ağırlık 10) yalnızca `chatd_internet_connectivity` ve `dedup_key` taşır.

---

## 15. Baileys (`baron-baileys-v2`, kaynağıyla karşılaştırıldı)

Baileys, WAM buffer'larını Android istemcisiyle aynı IQ ile gönderir.

| Konu | Baileys (`src/Socket/socket.js`, `src/WAM/encode.js`) | Android 2.26.41.6 | Tier |
|--------|--------------------------------------------------------|-------------------|------|
| Yükleme stanza'sı | `<iq to=s.whatsapp.net xmlns="w:stats" type="set"><add t=…>buffer</add></iq>` | aynı | ikisinde de found |
| Header | `"WAM"`, sürüm baytı 5, bayt 4 = `1`, 5'te `u16 BE` sıra numarası, 7'de kanal `0` | `"WAM"`, sürüm 5, bayt 4 = `0`, 29'da `u16 LE` sıra numarası, 31'de kanal (dosyada önünde bir `WMT` container'ı ile) | ikisinde de found |
| Değer kodlaması | tag'de `0/1`, int8, int16/int32 LE, float64 LE, u8/u16 LE/u32 LE uzunluklu string'ler, geniş id flag'i `0x08` | aynı bitler | ikisinde de found |
| Event ağırlığı | `-weight` olarak yazılır | buffer dosyalarında pozitif saklanır | ikisinde de found |
| Kanallar, flush | yalnızca regular; 30 sn'de bir ve login sonrasında flush, hatalar yalnızca loglanır | 0..3; native rotasyon ve transport'lar | found |

Sıra numarası bayt sırasındaki ve ağırlık işaretindeki fark, bu rapor tarafından kanıtlanmış bir hata değildir: Android'in diskteki dosyaları native transport'un yüklediği baytlara eşit olmak zorunda değildir ve sunucunun ayrıştırıcısı gözlemlenmedi. Burada okunan sohbet kod yollarında hiçbir şey WAM durumunu beklemez; sunucunun eksik veya olağandışı bir yüklemeye tepki verip vermediği unknown (19).

---

## 16. Hata durumları

| Belirti | Neden | Çözüm / not |
|---------|-------|------------|
| Buffer'larda event eksik | ağırlık zarı tutmadı (1-in-N), kanal-3 allowlist'i, depolama üst sınırı, native "weight exceeds max", "have to drop event" | ağırlığı 2.4 ve AB props'u 8.2, 4 içinde kontrol et |
| Günlük event doğrulama event'leri üretir | `ai_widget_installed` kuralı her `wam_daily` için başarısız olur (3.2) | bu build'de beklenen |
| "WamJniBridge/upload postponed" | 15507 / 468 olmadan çağrı aktif, veya 9654 ile offline kuyruk hâlâ boşalıyor | geçici; native yeniden dener (inferred) |
| "FieldStatsXmppImpl/error sending fieldstats IQ" | IQ hatası, timeout (32 sn) veya interrupt | native yeniden deneme / kalıcı hata yolu |
| "Cannot log before WAM runtime is initialized" / "after ... terminated" | native yaşam döngüsü sırası | Java `A0K` üzerinde bekler; terminate bir native durumdur |
| Özel yükleme 401 ile başarısız olur | credential reddedildi | `privatestats` IQ ile yenile (10.1) |

---

## 17. Temel ayrımlar

| Çift | Fark |
|------|------------|
| WAM vs Falco | WAM event'leri native runtime ve buffer'lar üzerinden gider; Java Falco logger'ı (`C40099Hdc`, `FFLogger`) aynı event sınıflarını Falco adıyla yeniden kullanan paralel bir yoldur. Falco migration batch 1..16 event başınadır (`internalFalcoMigrationBatchNumber`) |
| Event ağırlığı vs feature flag | ağırlık = 1-in-N örnekleme ve event ile gönderilen bir çarpan; flag'ler yalnızca transport davranışını kapılar |
| Regular vs özel yükleme | regular = sohbet stream'inde `w:stats` IQ; özel = kör credential ile ayrı HTTP transport'u |
| `psId` vs global 6005 | `psId` event sınıfındaki statik bir anahtar hash'idir; 6005 native olarak özel buffer'lara yazılan dönen bir UUID'dir |
| Alan id vs global id | sayısal uzaylar çakışır (47 bir global'dir; bir event'in 47. alanı farklıdır); tag rolü ayrım yapar |
| `wam-event/<name>` vs WAM yükleme | birincisi cihaz loglarını crash reporter ile yükler, ikincisi metrik buffer'larını yükler |
| Diskteki buffer vs wire payload | dosyada bir `WMT` container'ı ve dolgu var; IQ payload düzeni inferred |

---

## 18. Tam akış

```
[App code / native call stats]  new Event(...) / ConvertFieldStats -> WamCall
    ▼
[C06650Fo.CNW / CNI]  weight = override (prefs) or schema A00, keep 1-in-N ; validate (ch 0,1) -> event 5560
    ▼
[WAM executor]  jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)
    ▼
[libwhatsapp.so WAMRuntime]  encode TLV (LE), add globals (47 commit time, 6005 psId UUID, common attrs)
    ▼
[files/wam/wamt-a-<channel>-0-<seq>]  "WMT" container + "WAM" 5 header, 64 KiB
    │  rotate (buffer_timeout) / flush (offline-complete with 9654, Bba, call end, CXZ)
    ├── channel 0, 1 ─────────────────────────────┬── channel 2, 3 ───────────────────────────────┐
    ▼                                             ▼                                              
jnidispatchIO(6, bytes)                       jnidispatchIO(7, 32 bytes blinded token)
    │  postponed in calls / offline drain          │  <iq xmlns="privatestats" type="get">
    ▼                                             ▼
<iq xmlns="w:stats" type="set"><add t=..>     [WA server] signed_credential, acs_public_key, config_id
  bytes</add></iq>  on the chat stream              │  stored, renewed on 401
    ▼                                             ▼
[WA server] type="result" -> return 1         HTTP upload, endpoint list source unknown -> [private-stats backend]

[WA server] <props> response: event_code -> sampling_weight, config_code -> AB props  ──►  prefs (8.2)
[DailyCronAction alarm: next local midnight + jitter(5529)] -> C28643Ccj populates C0Fp (wam_daily 1158) -> CNW (same path, channel 0)
```

---

## 19. Bilinmeyenler

| Soru | Neden unknown |
|----------|-------------|
| Yükleme payload'ının tam baytları ile buffer dosyası karşılaştırması | native transport disassemble edilmedi; yalnızca IQ sınırları görüldü |
| Özel yüklemelerin sıkıştırması ve header çerçevelemesi, endpoint listesi kaynağı | Java'da veya string'lerde literal yok; native HTTP yolu izlenmedi |
| Native rotasyon aralığı, yeniden deneme çizelgesi, ağırlık maksimumu, düşürme kuralları, beaconing algoritması | strip edilmiş native kod, büyük kütüphane için burada kullanılan bir decompiler yok |
| 495, 6833, 2795, 105 özniteliklerinin ve çeşitli flag özniteliklerinin anlamı; offset 8, 16, 20'deki `WMT` alanları; `MTD` alanları | kaynaklar çözülmedi, yalnızca değerler |
| Herhangi bir sunucu davranışının eksik veya olağandışı WAM'a bağlı olup olmadığı | sunucu tarafı |
| `*_jid` alanlarının hash'lenmesi; kullanıcıya dönük bir opt-out'un varlığı | event başına izlenmedi / bulunamadı (yokluk kanıt değildir) |
| Native yeniden deneme zamanlaması, PSID rotasyon tetikleyicisi (istemci zamanı veya sunucu talimatı), AB prop varsayılanları | native mantık izlenmedi; varsayılanlar sunucu config'inden gelir |
| `wam_daily` dışındaki günlük cron'ların tetikleyicisi | yalnızca cron kayıt defteri ve `wam_daily` cron'u okundu |
