<!-- src-sha1: 6effa8dc57f2e12a66c37c7cae9d875028a5d55e -->
# WhatsApp Yerel Depolama — Full RE Report
**Sürüm:** 2.26.41.6 | **Tarih:** 2026-10-23
**Kapsam:** SQLite veritabanları (adlar, konum, engine, sürümleme, tablo framework'ü), msgstore.db ve wa.db anahtar tabloları ile sütunları, axolotl.db, sync.db ve daha küçük veritabanları, crypt15 yedekleri ve yedek anahtar dosyaları, Android auto-backup kuralları ve migration content provider, SharedPreferences factory'si ve anahtar envanteri, dosya ve cache yapısı, log ve telemetri dosyaları, logout / unregister / reregister / hesap silme işlemlerinin neleri kaldırdığı

---

## 1. Neler nerede saklanıyor

Tüm ifadeler, decompile edilmiş APK'nın ve içindeki native kütüphanelerin statik analizine dayanır. Hiçbir cihaz verisi okunmadı. Tier: **found** = kodda, manifest'te veya native string'lerde okundu; **inferred** = koddan çıkarıldı; **unknown** = çözülemedi. Obfuscate edilmiş adlar 2.26.41.6 için JADX'in gösterdiği gibidir ve her build'de değişir.

### 1.1 Depolama haritası

```
/data/data/com.whatsapp/                      (default account; secondary accounts: see 11.5)
├── databases/        msgstore.db wa.db axolotl.db sync.db status.db chatsettings.db
│                     stickers.db backup.db payments.db commerce.db companion_devices.db
│                     paa.db location.db daily_metrics.db qp_payload.db media.db ...  (+ -wal/-shm, wa-backup.db, msgstore.db-backup)
├── shared_prefs/     <name>.xml                                  (section 8)
├── files/            me  rc2  backup_token  encrypted_backup.key  Logs/  falco/  wam/  mobileconfig/
│                     decompressed/libs.spo  Stickers/  Drafts/  GroupHistory/  Wallpapers/  statistics.json ...  (section 9)
├── cache/            thumb_decoded_cache  webp_static_cache  stickers_cache  Profile Pictures  tigon_http_client ...
├── no_backup/ app_account_switching/ app_qpl/ app_minidumps/ app_light_prefs/ modules/ lib-compressed/ app_webview/
└── (Android) /Android/media/com.whatsapp/WhatsApp/   Media/  Backups/  Databases/   (section 7, 9.4)
```

| Konum | İçerik | Android auto-backup'ta korunur mu |
|-------|--------|------------------------------|
| `databases/` | tüm SQLite dosyaları | hayır: her domain hariç tutulur (8.1) |
| `shared_prefs/` | ayarlar, flag'ler, anahtarlar | hayır |
| `files/`, `cache/` | anahtar dosyaları, cache'ler, log'lar | hayır |
| harici kök `Backups/` | şifreli sohbet yedeği (crypt15) | yok: kendi yedekleme mekanizması (7) |

### 1.2 Engine bilgileri (found)

| Bilgi | Kanıt |
|-------|-------|
| SQLite, framework'ün kendisi değil, paketlenmiş `io.requery.android.database.sqlite` build'idir | `java_src` içindeki paket |
| SQLCipher yok: `java_src` içinde hiçbir yerde `PRAGMA key` veya `sqlcipher` string'i yok | grep; veritabanı dosyaları uygulama sandbox'ı içinde diskte düz metindir |
| `AbstractC11350Yn` üzerine kurulu tüm helper'lar için WAL etkin (`setWriteAheadLoggingEnabled(true)`) | `AbstractC11350Yn`; checkpoint `PRAGMA wal_checkpoint(FULL)` ile |
| msgstore `PRAGMA synchronous=NORMAL`, isteğe bağlı `cache_size` (flag **20777**), `PRAGMA secure_delete=1` ile açılır | `C06980Hc.onOpen`; secure_delete'in etkinleştirilememesi `db-integrity/enable-secure-delete/error/not-enabled` olarak raporlanır |
| `PRAGMA foreign_keys=ON` sync.db, paa.db, daily_metrics.db için ayarlanır, msgstore.db için ayarlanmaz | `AbstractC12530bK`, `AbstractC197088a3`, `AbstractC16650iN`; msgstore cascade işlemlerini trigger'larla yapar (2.3) |

---

## 2. SQLite veritabanları

### 2.1 Envanter

Dosya adları literal'dir (`getDatabasePath(...)` / helper constructor'ları). Tablo sayıları, helper'ı besleyen DI modülündeki tablo tanım sınıflarının sayısıdır (2.3).

| Dosya | Helper / modül (2.26.41.6) | Sürüm / migration | Tablo sınıfları | Rol | Tier |
|------|-----------------------------|---------------------|---------------|------|------|
| `msgstore.db` | `C06980Hc` (factory `C0HH`) | SQLite `user_version` sabit 1; şema parmak izi `props` içinde (2.4) | 306 (factory `C1S0`) | mesajlar, sohbetler, JID'ler, receipt'ler, aramalar, newsletter'lar, integrity, AI, TEE | found / set attribution inferred |
| `wa.db` | `C12650bW` | **95** (`creating contacts database version 95`) | 88 (`C8ZL` implementor'ları) | kişiler, blocklist'ler, business profilleri, trusted-contact token'ları, integrity sinyalleri | found |
| `axolotl.db` | `C44861sL`, tablolar `AbstractC11250Yd` | **40** | 15 | Signal session'ları, prekey'ler, sender key'ler, stanza kuyrukları | found |
| `sync.db` | `AbstractC12530bK` (helper `X.1sK`) | en az v50'ye kadar adım adım `ALTER` migration'ları; downgrade = reset | 10 | app-state sync, history sync, peer mesajları | found, sürüm unknown |
| `status.db` | `C41891nD` | **2** (`StatusDbHelper creating status database version 2`) | 29 (`AbstractC11620Zo`) | status gönderileri ve etkileşimleri | found |
| `backup.db` | `C44881sN` | **1** | `backups`, `backup_props` | yedek kayıtları; `backup_props` `wa_db_schema_version` değerini tutar | found |
| `chatsettings.db` | `C11200Xy("chatsettings.db")` | unknown | `settings` (inferred) | sohbet başına sessize alma, sabitleme, ton, duvar kağıdı, tema | ad found, tablo inferred |
| `stickers.db` | modül `AbstractC149676Ty` | unknown | 18 (modül ayrıca `offloaded_media*`, `backups`, `backup_props` kaydeder) | sticker paketleri | found |
| `offloaded-media.db` | `CMN` (yedek bileşeni) | unknown | `offloaded_media`, `offloaded_media_staging` (attribution inferred) | offload edilmiş medya dizini | found / inferred |
| `payments.db` | `C1S0` anon helper, `AbstractC22520tH` | **5** | `contacts`, `methods`, `receipts`, `tmp_transactions` | ödeme yöntemleri | found |
| `commerce.db` | `C27743C3e` | unknown | unknown | commerce verisi; yedek varyantı `commerce_backup.db` | ad found |
| `companion_devices.db` | `C48701zE` | **27** | `devices` (+ diğerleri) | primary cihazdan görünen bağlı cihazlar | found |
| `paa.db` | `ManagedAccountDbHelper` (`AbstractC197088a3`) | migration'lar V1 ile V7 arası | `paa_connection`, `contact_metadata`, `group_metadata` | yönetilen hesap (ebeveyn onaylı hesap) verisi | found |
| `daily_metrics.db` | `AbstractC16650iN` | unknown | `poll_event_logging`, `poll_daily_participant`, `comments_event_logging`, `pnh_daily_event_logging`, `community_home_action_logging`, `snapl_payload` | günlük olay sayaçları | found |
| `qp_payload.db`, `location.db`, `fa_events.db`, `media.db`, `account_switcher.db` | path getter'ları (`C23985AVo`, `C33961Wh`) | unknown | unknown | quick promotion'lar, canlı konum, federated analytics, medya job'ları (inferred), hesap listesi | ad found |
| `sqlite_vec.db` | `MessageEmbeddingsStore` | unknown | vektör tabloları (unknown) | cihaz üstü mesaj embedding'leri; yalnızca etkinse bulunur | found |
| `emojidictionary.db`, `hsmpacks.db`, `events.db` | `C8JP`, `C6UR` | unknown | unknown | emoji sözlüğü, şablon paketleri, olaylar | ad found |
| `wa-backup.db`, `msgstore.db-backup` | `CMN` / `C26042BNa`, `C0KE` | yok | yok | wa.db / msgstore'un yerel güvenlik kopyaları | found |
| `migration_prefetcher.db`, `migration_import_metadata.db`, `migration_export_metadata.db` | `C23985AVo` | unknown | unknown | chat-transfer / OS migration durumu; `migration_prefetcher.db` `C28152CMi` tarafından silinir | ad found |
| `androidx.work.workdb` | WorkManager (`no_backup/`) | Room | standart | job kuyruğu | Room sınıflarından inferred (`room_master_table`) |

### 2.2 Diğer raporlarda anılan tabloları hangi DB tutar

| Tablo | DB dosyası | Tablo sınıfı | Kanıt | Rapor |
|-------|---------|-------------|----------|--------|
| `wa_trusted_contacts`, `wa_trusted_contacts_send` | `wa.db` | `C23627AHs`, `C23628AHt` (`C8ZL`) | wa.db helper'ı bunları yeniden oluşturur; store'lar wa.db helper'ının `C12810bn` sınıfı üzerinden okunur | [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_biz_integrity_signals` | `wa.db` | `C53116Nmn` (`C8ZL`) | found | [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 5.1 |
| `start_chat_trust_signals` | `wa.db` | `AI0` (`C8ZL`), `wa_contacts` üzerinde trigger | found | ban raporu 5.2 |
| `integrity_chat_info` | `msgstore.db` | `C08970Ox`, `chat` üzerinde trigger `chat_bd_for_integrity_chat_info_trigger` | found, attribution `chat`'e giden FK ile | ban raporu 5.3 |
| `meta_ai_memory` | **`wa.db`** | `C23621AHm` (`C8ZL`) | found; sütunlar `memory_id`, `memory_content`, `bot_jid_row_id` | [WA_META_AI.md](WA_META_AI.md) |
| `bot_memory_metadata`, `bot_chat_info`, `ai_thread_info` | `msgstore.db` | `C08640Nq`, `C08610Nn`, `C0MO` | 306 sınıflık kümede | Meta AI raporu |

`meta_ai_memory` `msgstore.db` içinde değil `wa.db` içindedir: sınıfı yalnızca wa.db helper'ının iterate ettiği `C8ZL`'yi implemente eder (`new C08050Lj("wa.db")` ile `C12650bW.onCreate`). `bot_jid_row_id` msgstore'daki bir `jid` satırına referans verir, dolayısıyla sütun veritabanları arası soft referanstır (inferred; dosyalar arası foreign key mümkün değildir).

### 2.3 Tablo framework'ü (şemalar nasıl tanımlanır)

Tablolar SQL string'i olarak yazılmaz. Her tablo, üç hook'lu `InterfaceC08060Lk` implemente eden bir sınıftır (wa.db: alt arayüz `C8ZL`) (found):

| Hook | Amaç |
|------|------|
| `ASa(ctx, builder)` | sütunları tanımlar: `C08080Lm` builder, `.A02` = ad, `.A00` = `EnumC08100Lo` türü (`INTEGER`, `TEXT`, `REAL`, `BLOB`, `LONG`, ...), primary key / not null / default için flag'ler |
| `ASX(ctx, builder)` | index'leri tanımlar (`CRN`, `CRJ` = koşullu index) |
| `ASc(builder)` | trigger'ları tanımlar (`CRg`, `CRf`) |

- 422 sınıf `InterfaceC08060Lk` implemente eder, ayrıca 88 sınıf `C8ZL` implemente eder. DI set'lerinde sağlanırlar; her helper kendi set'ini iterate eder (`C06980Hc.A03`, `C12650bW.onCreate`, `C44881sN`, `C41891nD`).
- Cascade silmeler foreign key değil trigger'dır: `AbstractC08210Lz.A01` `CREATE TRIGGER <parent>_bd_for_<child>_trigger BEFORE DELETE ON <parent> BEGIN DELETE FROM <child> WHERE ...; END` üretir (found; örnek: `message_add_on` satırları gidince `message_add_on_reaction` silinir).
- Aşağıdaki sütun listeleri `ASa` içinden, tanımlanma sırasıyla çıkarılmıştır. Decompiler helper ile oluşturulan bazı sütunları (birkaç tablonun ilk sütunu, default değerler) atlar; bir sorgu veya trigger sütunu kanıtlıyorsa bunlar "(+ jid)" ile işaretlenmiştir. Türler yalnızca kod belirttiğinde verilmiştir.
- 306 msgstore sınıfının DB attribution'ı DI factory `C1S0` (306 `new` çağrısı, `message`, `chat`, `jid` dahil) ve `chat` / `message` / `jid`'e giden FK trigger'larıyla yapılır (inferred). İki modülde aynı ada sahip tablolar vardır (`status`, `status_attribution`, `mms_thumbnail_metadata`, `quick_promotion_payload`: msgstore ile status.db veya wa.db'nin her birinde bir sınıf var).

### 2.4 Sürümleme ve migration'lar

| DB | Strateji (found) |
|----|------------------|
| `msgstore.db` | `onUpgrade` = `onCreate`; `setVersion(1)` her zaman. Gerçek sürüm `props` tablosunda saklanan bir hash'tir: `msgtore_db_schema_version` ve `msgtore_db_schema_indexes_version` = literal bir `Consumer-<hex>` tag'i ve `MessageSchemaConfig=1;isGlobalChatDbMigrated=<bool>[;includeNewsletterInteractionTable=true]` üzerinde `Arrays.hashCode` (`C06980Hc.A04`). Declarative: tablolar ve index'ler sınıf set'inden `CREATE ... IF NOT EXISTS` ile oluşturulur. Diğer `props` anahtarları: `MessagesDBHelper_RestoredIndexesPending`, `MessagesDBHelper_CreateAsyncIndexesV2`, `..FailedAttempts` |
| `wa.db` | `onUpgrade`, eski sürüm 3 ile 94 üzerinde bir switch'tir ve çoğunlukla sonradan yeniden oluşturulan tabloları düşürür; bilinmeyen eski sürüm `onCreate`'e düşer; downgrade = `onCreate`. `wa_db_schema_version` bir `ConsumerBeta-<hex>` tag'iyle yazılır. `force_wadb_check` pref'i (startup_prefs) yeniden kontrolü zorlar. wa.db yeniden oluşturulabilir veridir (kişiler, token'lar, cache'ler) |
| `axolotl.db` | sürümlü (40); eski DDL varyantları `C44861sL` içinde görülür (örn. `identities` şunları kazandı: `recipient_type`, `next_kyber_prekey_id`, `account_encryption_attestation_type`; `sessions` şunları kazandı: `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope`; `sender_keys` şunu kazandı: `bucket_id`) |
| `sync.db` | adım adım `ALTER TABLE ... ADD` (örn. `collection_versions.dirty_version`, `history_sync_companion.inline_payload`, `msg_history_sync.size_limit_bytes`); downgrade veya bilinmeyen sürüm tabloları yeniden oluşturan `sync-db-helper/reset` çağırır, dolayısıyla app state yeniden senkronize edilir (inferred) |
| `status.db` | v2; `key_value_store` satırı `schema_version` |
| `paa.db` | `runMigrationV1`..`V7` (`age_experience`, `snooze_status`, `common_groups_count` gibi sütunlar ekler) |
| yedekler (`BD0`) | crypt15 metadata'sı hâlâ tablo başına "migration finished" flag'lerini taşır (`message_main`, `receipt_user`, `jid_store`, ...), eski msgstore migration'larının geçmişi (7.2) |

---

## 3. msgstore.db: anahtar tablolar ve sütunlar

### 3.1 Tablo aileleri (found, 306 sınıf)

| Aile | Tablolar (örnekler) |
|--------|--------------------|
| Identity | `jid`, `jid_map`, `lid_chat_state`, `lid_display_name`, `jid_user_metadata`, `integrator_display_name` |
| Chat | `chat`, `chat_ephemeral`, `chat_encryption_classification`, `community_chat`, `broadcast_chat_details`, `thread_messages`, `thread_id`, `draft_message_reminder` |
| Message core | `message`, `message_text`, `message_media`, `message_quoted*` (14), `message_edit_info`, `message_revoked`, `message_forwarded`, `message_mentions`, `message_link`, `message_future`, `message_orphan`, `message_send_count`, `message_view_once_media`, `message_ephemeral*` |
| Sistem mesajları | `message_system` + yaklaşık 35 `message_system_*` detay tablosu (group, number_change, lid_change, username_change, device_change, privacy, ...) |
| Add-on'lar | `message_add_on` ve `message_add_on_reaction`, `_poll_vote`, `_poll_vote_selected_option`, `_keep_in_chat`, `_pin_in_chat`, `_question_response`, `_event_response`, `_receipt_device`, `_receipt_coex`, `_status_*` |
| Receipt'ler | `receipt_user`, `receipt_device`, `receipt_coex`, `receipt_orphaned`, `played_self_receipt`, `optimised_delivery_info` |
| Gruplar | `group_participant_user`, `group_past_participant_user`, `group_participant_device`, `parent_group_participants`, `group_history_*`, `group_root_key_mapping`, `group_notification_version` |
| Cihazlar | `user_device`, `user_device_info`, `primary_device_version`, `agent_devices` |
| Medya | `media_hash_thumbnail`, `media_content`, `mms_metadata`, `mms_thumbnail_metadata`, `extended_media_data`, `message_media_map`, `message_streaming_sidecar`, `media_refs`, `message_thumbnail`, `audio_data`, `voice_data` |
| Aramalar | `call_log`, `call_log_participant_v2`, `joinable_call_log`, `missed_call_logs`, `bcall_session`, `call_link`, `scheduled_calls` |
| Newsletter'lar | `newsletter`, `newsletter_message`, `newsletter_message_reaction`, `newsletter_admin_profile`, `newsletter_subscribers`, `newsletter_pinned_message`, `newsletter_interaction` |
| Poll'lar / etkinlikler / etiketler | `message_poll`, `message_poll_option`, `poll_vote_*`, `event*`, `labels`, `labeled_jid`, `favorite`, `quick_replies*` |
| Ödemeler / commerce | `pay_transaction`, `payment_*`, `message_payment*`, `message_order`, `message_product`, `cart_item` |
| Integrity / raporlama | `integrity_analysis_result`, `integrity_chat_info`, `integrity_input_feature`, `integrity_deleted_chat_*`, `message_quarantine`, `message_structure_analysis_result`, `reporting_info(_content)`, `scam_alert_events` |
| AI / TEE | `ai_thread_info`, `ai_rich_response_message_*`, `bot_*`, `agent_*`, `auth_agent_chat_metadata`, `tee_chat_request_table`, `tee_message_info_table`, `private_ai_*`, `embeddings_deletion_log` |

### 3.2 Identity: jid, LID eşlemesi

| Tablo | Sütunlar (tanım sırası) | Notlar |
|-------|--------------------------|-------|
| `jid` | `_id` (PK AUTOINCREMENT), `user`, `server`, `agent`, `device`, `type`, `raw_string` | (`user`,`server`,`agent`,`device`,`type`) üzerinde unique index `jid_key_new_index`, `raw_string` üzerinde unique `jid_raw_string_index`. `JidStore` (`C0W4`) `jid.getType()` / `getRawString()` yazar. Diğer her tablo bir JID'ye `*_jid_row_id` = `jid._id` ile başvurur |
| `jid_map` | `lid_row_id`, `jid_row_id`, `sort_id` | LID satırından telefon numarası JID satırına (LID migration yüzeyi; `lid_row_id` üzerinde trigger) |
| `lid_chat_state` | `jid_row_id`, `is_pn_shared`, `pn_requested_ts`, `pnh_duplicate_lid_thread` (+ yalnızca default'lu sütunlar) | her LID sohbeti için telefon numarası paylaşım durumu |
| `lid_display_name` | `lid_row_id`, `display_name`, `username` | bir LID kişisi için gösterilen username, bkz. [WA_USERNAME.md](WA_USERNAME.md) |

### 3.3 chat

`chat` (`C0OM`), 57 tanımlı sütun. `account_jid_row_id` üzerinde unique index `chat_account_jid_row_id_unique_index`.

| Grup | Sütunlar |
|-------|---------|
| Anahtar | `_id`, `jid_row_id`, `account_jid_row_id` (sahip hesap; multi-account / LID ile yeni), `chat_origin` |
| Görüntüleme | `subject`, `created_timestamp`, `hidden`, `archived`, `sort_timestamp`, `group_type`, `group_member_count`, `is_contact`, `chat_lock` |
| `message`'a işaretçiler | `display_message_row_id`, `last_message_row_id`, `last_read_message_row_id`, `last_read_receipt_sent_message_row_id`, `last_important_message_row_id`, `change_number_notified_message_row_id`, ayrıca `*_sort_id` varyantları ve `last_message_reaction_row_id`, `last_seen_message_reaction_row_id` |
| Okunmamış sayaçları | `unseen_message_count`, `unseen_important_message_count`, `unseen_missed_calls_count`, `unseen_row_count`, `unseen_message_reaction_count`, `unseen_comment_message_count`, `unseen_earliest_message_received_time` |
| Ephemeral | `ephemeral_expiration`, `ephemeral_setting_timestamp`, `ephemeral_displayed_exemptions`, `ephemeral_disappearing_messages_initiator`, `ephemeral_after_read_duration` |
| Crypto / politika | `plaintext_disabled`, `chat_encryption_state`, `limited_sharing`, `limited_sharing_setting_timestamp`, `growth_lock_level`, `growth_lock_expiration_ts`, `spam_detection`, `business_chat_state`, `participation_status`, `history_sync_progress`, `chat_props` |

### 3.4 message ve uydu tablolar

`message` (`C09540Re`), 24 sütun; (`chat_row_id`,`from_me`,`key_id`,`sender_jid_row_id`) üzerinde unique index `message_key_index`.

| Sütun | Kullanım |
|--------|-----|
| `_id` | satır id'si, her yerde `message_row_id` olarak başvurulur |
| `chat_row_id`, `sender_jid_row_id` | sohbet, gönderen (`jid._id`) |
| `from_me`, `key_id` | message key parçası (stanza id) |
| `status`, `broadcast`, `recipient_count`, `participant_hash` | teslimat durumu ve grup fan-out özeti |
| `origination_flags`, `origin`, `view_mode`, `sort_id` | köken ve sıralama |
| `timestamp`, `received_timestamp`, `receipt_server_timestamp`, `server_sts` | zamanlar |
| `message_type`, `text_data`, `translated_text` | tür ve düz metin gövdesi (metin satırın kendisinde durur) |
| `starred`, `view_replies_thread_id` | flag'ler |
| `lookup_tables`, `message_add_on_flags` | hangi uydu tabloların satır tuttuğunu söyleyen bitmask'ler (adlardan ve kullanımdan inferred) |

| Uydu | Anahtar sütunlar |
|-----------|-------------|
| `message_text` | `message_row_id`, `description`, `page_title`, `url`, `font_style`, `text_color`, `background_color`, `preview_type`, `invite_link_group_type`, `counter_abuse_token`, `link_end_index` |
| `message_quoted` | `message_row_id`, `chat_row_id`, `parent_message_chat_row_id`, `from_me`, `sender_jid_row_id`, `key_id`, `timestamp`, `message_type`, `text_data`, `quoted_source`, `quoted_type` |
| `message_edit_info` | `message_row_id`, `original_key_id`, `edited_timestamp`, `sender_timestamp` |
| `message_revoked` | `message_row_id`, `revoked_key_id`, `admin_jid_row_id`, `revoke_timestamp` |
| `message_ephemeral` | `message_row_id`, `duration`, `expire_timestamp`, `keep_in_chat`, `ephemeral_trigger`, `ephemeral_initiated_by_me`, `after_read_duration` |
| `message_secret` | `message_row_id` (+ decompiler'ın atladığı secret sütunu): add-on şifrelemesi için mesaj başına secret (inferred) |
| `message_future` | `message_row_id`, `version`, `data`, `future_message_type`, `future_proof_stanza`, `edit_version`, `message_stanza_data` (desteklenmeyen mesaj, sonrası için saklanır) |
| `message_orphan` | `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_*`, `orphan_message_data`, `orphan_message_type`, `orphan_message_reason` (parent'ından önce gelen child) |
| `message_quarantine` | `message_row_id`, `chat_row_id`, `timestamp`, `original_protobuf`, `serialized_stanza`, `protobuf_type` |
| `reporting_info` | `message_row_id`, `reporting_tag`, `stanza_id`, `send_timestamp`, `receive_timestamp`, `stanza_id_text`, `receive_flow`, `is_message_add_on` (bkz. [WA_REPORTING.md](WA_REPORTING.md)) |
| `message_send_count` | `message_row_id`, `send_count` |

### 3.5 Receipt'ler, reaction'lar, add-on'lar

| Tablo | Sütunlar | Notlar |
|-------|---------|-------|
| `receipt_user` | `_id`, `message_row_id`, `receipt_user_jid_row_id`, `receipt_timestamp`, `read_timestamp`, `played_timestamp` | alıcı başına (1:1 ve grup) |
| `receipt_device` | `_id`, `message_row_id`, `receipt_device_jid_row_id`, `receipt_device_timestamp`, `primary_device_version` | alıcı cihazı başına |
| `receipt_orphaned` | `_id`, `chat_row_id`, `from_me`, `key_id`, `receipt_device_jid_row_id`, `receipt_recipient_jid_row_id`, `status`, `timestamp` | mesajından önce gelen receipt |
| `message_add_on` | `_id`, `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_message_row_id`, `timestamp`, `status`, `message_add_on_type`, `received_timestamp`, `expiry_duration_in_secs`, `server_timestamp`, `expiry_timestamp`, `expiry_type` | reaction / vote / pin / keep başına bir satır; lookup sorgusunda unique anahtar (`chat_row_id`,`key_id`,`from_me`) |
| `message_add_on_reaction` | `message_add_on_row_id` (PK), `reaction`, `sender_timestamp` | `reaction = ''` üzerinde kısmi index `message_add_on_reaction_empty_reaction_index` (boş string = kaldırılmış reaction, inferred) |
| `message_poll` | `message_row_id`, `enc_key`, `selectable_options_count`, `invalid_state`, `poll_logging_id`, `poll_type`, `correct_option_id`, `content_type`, `hide_participant_names`, `end_time`, `allow_add_option` | |

`C09010Pb.A00` add-on sütun kümesidir; `AbstractC41651mo.A01` sütun kümesini add-on tür id'sine göre seçer: 56 = reaction (`C0PV`), 67 = poll vote (`C0PT`), diğerleri 68, 74, 79, 86, 93, 121, 122, 125 (found: switch; anlamları izlenmedi).

### 3.6 Gruplar ve katılımcılar

| Tablo | Sütunlar |
|-------|---------|
| `group_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `add_timestamp`, `label`, `join_method`, `group_history_send_state` |
| `group_past_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `is_leave`, `timestamp` |
| `group_participant_device` | `_id`, `group_participant_row_id`, `device_jid_row_id`, `sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket` (cihaz başına sender-key dağıtım durumu) |
| `group_root_key_mapping` | `_id`, `group_jid_row_id`, `key_id`, `is_current` |
| `feature_key_store` | `_id`, `key_id`, `key_jid`, `key`, `key_type`, `creation_timestamp`, `expiry_timestamp` |

Grup düzeyindeki ayarlar (yalnızca admin, announcement, ephemeral, üyelik onayı, geçmiş toggle'ları) burada değil **wa.db** `wa_group_admin_settings` içindedir (4.3). Grup geçmişi: [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md).

### 3.7 Cihazlar

| Tablo | Sütunlar |
|-------|---------|
| `user_device` | `_id`, `user_jid_row_id`, `device_jid_row_id`, `key_index` |
| `user_device_info` | `user_jid_row_id`, `raw_id`, `timestamp`, `expected_timestamp`, `expected_ts_last_device_job_ts`, `expected_timestamp_update_ts`, `account_encryption_type` (kullanıcı başına ADV durumu) |

### 3.8 Medya, thumbnail'ler, sidecar

| Tablo | Sütunlar | Not |
|-------|---------|------|
| `message_media` | `message_row_id`, `chat_row_id`, `file_path`, `file_size`, `file_length`, `mime_type`, `media_name`, `media_key`, `media_key_timestamp`, `e2ee_media_key`, `file_hash`, `enc_file_hash`, `partial_media_hash`, `partial_media_enc_hash`, `original_file_hash`, `direct_path`, `message_url`, `metadata_url`, `media_duration`, `width`, `height`, `transferred`, `transcoded`, `is_offloaded`, `media_job_uuid`, `media_upload_handle`, `has_streaming_sidecar`, `media_caption`, `media_source_type`, `suspicious_content` | 55 tanımlı sütun; `file_path` medya köküne göreli saklanır (`C0KE.A0A` kök önekini siler, found). Upload / download alanları: [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| `message_thumbnail` | `message_row_id`, `thumbnail` | thumbnail baytları DB içinde |
| `message_streaming_sidecar` | `message_row_id`, `sidecar`, `chunk_lengths`, `timestamp` | streaming sidecar (aşamalı oynatma için chunk MAC verisi) dosya olarak değil DB içinde |
| `media_hash_thumbnail` | `media_hash`, `thumbnail` | içerik hash'i ile anahtarlanan thumbnail |
| `media_refs` | `_id`, `path`, `ref_count` | dosya yolu başına referans sayısı |
| `mms_thumbnail_metadata` | `message_row_id`, `direct_path`, `media_key`, `media_key_timestamp`, `enc_thumb_hash`, `thumb_hash`, `thumb_width`, `thumb_height`, `transferred`, `micro_thumbnail`, `insert_timestamp`, `handle` | |
| `extended_media_data` | `row_id`, `type`, `external_url`, `direct_path`, `preview_path`, `file_path`, `file_hash`, `media_key`, `enc_file_hash`, `mime_type`, `display_type` | |
| `offloaded_media` (offloaded-media.db) | `file_path`, `content_hash`, `file_size`, `media_source`, `media_state`, `is_offloadable`, `latest_reference_timestamp`, `refetch_timestamp`, `file_key` | |

### 3.9 Aramalar

| Tablo | Sütunlar |
|-------|---------|
| `call_log` | `_id`, `jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch` |
| `call_log_participant_v2` | `_id`, `call_log_row_id`, `jid_row_id`, `call_result` |

Arama signaling'i: [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md). Newsletter tabloları (`newsletter`, `newsletter_message`, 45 ve 17 sütun) yalnızca 3.1'de listelenmiştir.

### 3.10 View'lar ile integrity / AI tabloları

`C06980Hc.A0C` içinde oluşturulan view'lar (found): `available_message_view`, `deleted_messages_view`, `deleted_messages_ids_view`, `chat_view` (iki varyant, `isGlobalChatDbMigrated` ile seçilir).

| Tablo | Sütunlar |
|-------|---------|
| `integrity_chat_info` | `chat_row_id` (PK), `is_reach_out`, `is_eligible_for_link_friction_banner` |
| `integrity_analysis_result` | `chat_row_id`, `last_message_row_id`, `result`, `timestamp`, `animation_played`, `trusted_timestamp`, `view_timestamp`, `holdout_group`, `experiment_group`, `chatting_untrusted_timestamp`, `replied_timestamp`, `block_logged_timestamp`, `trust_logged_timestamp`, `report_logged_timestamp` |
| `integrity_input_feature` | `chat_row_id`, `sender_reputation`, `country_mismatch`, `fetched_timestamp` |
| `tee_chat_request_table` | `message_row_id`, `chat_request_type`, `anchor_message_row_id`, `node_token`, `extra_data` |
| `tee_message_info_table` | `message_row_id`, `message_interaction_type`, `message_outgoing_status`, `message_source`, `message_replay_metadata` |
| `ai_thread_info` | `thread_id_row_id`, `title`, `creation_ts`, `variant`, `last_thread_messages_row_id`, `last_message_timestamp`, `title_source`, `unseen_message_count`, `origin_chat_row_id`, `selected_mode`, `selected_modes` |
| `bot_chat_info` | `chat_row_id`, `welcome_request_message_sent`, `bot_metrics_thread_origin` |
| `bot_memory_metadata` | `_id`, `message_row_id`, `memory_annotated_user_message_key_id`, `memory`, `memory_id`, `added`, `bot_jid_row_id` |

---

## 4. wa.db: kişiler, blocklist'ler, trust verisi

### 4.1 Aileler (found, 88 sınıf)

| Aile | Tablolar |
|--------|--------|
| Kişiler | `wa_contacts`, `wa_contact_details`, `wa_contacts_created_within_wa`, `wa_contacts_pending_operations`, `wa_contact_refresh_pending`, `wa_contact_refresh_patch_log`, `wa_contact_storage_usage`, `wa_address_book`, `wa_org_contacts`, `wa_orgs`, `system_contacts_version_table` |
| Blocklist'ler / allowlist'ler | `wa_block_list`, `wa_block_list_interop`, `wa_last_seen_block_list`, `wa_profile_photo_block_list`, `wa_about_block_list`, `wa_pix_block_list`, `wa_cover_photo_block_list`, `wa_status_view_allow_list`, `wa_status_view_black_list`, `wa_group_add_allow_list`, `wa_group_add_black_list`, `wa_stickers_allow_list`, `wa_profile_links_deny_list` |
| Business | `wa_biz_profiles` + 12 `wa_biz_profiles_*` / `wa_biz_*` detay tablosu, `wa_vnames`, `wa_vnames_localized` |
| Gruplar | `wa_group_admin_settings`, `wa_group_descriptions`, `group_membership_approval_requests`, `non_admin_group_membership_approval_requests`, `group_membership_count`, `group_membership_form_questions`, `group_relationship`, `subgroup_info`, `community_settings`, `member_suggested_groups_v2`, `group_suspension_appeal`, `group_non_wa_invites` |
| Trust / integrity | `wa_trusted_contacts`, `wa_trusted_contacts_send`, `wa_biz_integrity_signals`, `wa_biz_integrity_chat_settings`, `start_chat_trust_signals`, `wa_contact_server_signals` |
| Config | `wa_props`, `wa_newsletter_props`, `wa_coex_properties`, `wa_ml_models`, `wa_last_entry_point`, `wa_logging_entry_point` |
| AI / bot'lar | `meta_ai_memory`, `wa_bot_profiles`, `wa_bot_commands`, `wa_subscriptions` |
| Diğer | `status_ranking(_global)`, `wa_chat_ranking_scores`, `wa_storage_monitoring_data/_jobs`, `inbound_/outbound_connection_requests`, `dismissed_*`, `quick_promotion_payload` |

### 4.2 wa_contacts

36 sütun (`Nn5`), `jid` ile anahtarlanır (TEXT, ham JID string'i; bir telefon JID'si veya `@lid` JID'si, bir `jid` satır id'si değil):

`jid`, `is_whatsapp_user`, `status`, `status_timestamp`, `number`, `raw_contact_id`, `display_name`, `phone_type`, `phone_label`, `photo_ts`, `thumb_ts`, `photo_id_timestamp`, `given_name`, `family_name`, `wa_name`, `sort_name`, `nickname`, `company`, `title`, `status_autodownload_disabled`, `keep_timestamp`, `is_spam_reported`, `is_sidelist_synced`, `is_business_synced`, `disappearing_mode_duration`, `disappearing_mode_timestamp`, `disappearing_mode_support_disabled`, `history_sync_initial_phash`, `is_starred`, `is_wa_created_contact`, `sync_policy`, `status_emoji`, `is_contact_synced`, `is_reachable`, `external_user_state`, `fts_dirty_version`.

`wa_name` kişinin belirlediği push name'dir; `display_name` / `given_name` adres defterinden gelir. Birkaç uydu tablo `BEFORE DELETE ON wa_contacts` trigger'ları kullanır (örn. `start_chat_trust_signals_contact_delete`, `contact_bd_for_business_integrity_signals`).

### 4.3 Diğer wa.db tabloları

| Tablo | Sütunlar |
|-------|---------|
| `wa_trusted_contacts` | (+ `jid`), `incoming_tc_token` BLOB, `incoming_tc_token_timestamp` LONG. Bkz. [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_trusted_contacts_send` | (+ `jid`), `sent_tc_token_timestamp` LONG, `real_issue_timestamp` LONG |
| `wa_biz_integrity_signals` | 17 sütun: `_id`, `jid`, `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `is_suspicious`, `join_date_ms`, `is_banned`, `phone_country_code`, `trust_tier`, `is_meta_verified`, `mv_friction_eligibility`, `integrity_tags`, `chat_row_id`, `last_sync_ts`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Tam semantik ban raporu 5.1'de |
| `start_chat_trust_signals` | (+ `jid`), `is_sender_suspicious`, `is_sender_new_account`, `created_ts` REAL |
| `meta_ai_memory` | `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER; `memory_content` üzerinde index `meta_ai_memory_memory_content_index` |
| `wa_contact_server_signals` | `chat_jid`, `signal_type`, `value`, `update_ts` |
| `wa_group_admin_settings` | `jid`, `restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `creator_jid`, `is_suspended`, `group_state`, `require_membership_approval`, `member_add_mode`, `addressing_mode`, `history_enabled`, `group_history_toggle_mode`, `share_group_history_setting_mode`, `earliest_group_history_message_timestamp_ms`, `allow_member_labels`, ... (31 sütun) |
| `wa_storage_monitoring_data` | `db_name`, `table_name`, `table_size_bytes`, `index_size_bytes`, `table_unused_bytes`, `index_unused_bytes` (istemci kendi tablo boyutlarını ölçer; bkz. 10.3) |

---

## 5. axolotl.db (Signal durumu)

Güncel DDL (en yeni varyantlar `C44861sL` içinde, tablolar `AbstractC11250Yd` tarafından kaydedilir; found). Anahtar materyali BLOB `record` sütunlarında saklanır; burada hiçbir anahtar baytı belgelenmez.

| Tablo | Sütunlar | Rol |
|-------|---------|------|
| `identities` | `_id`, `recipient_id`, `recipient_type`, `device_id`, `registration_id`, `public_key`, `private_key`, `next_prekey_id`, `next_kyber_prekey_id`, `timestamp`, `account_encryption_attestation_type`, `mark_as_verified`, `mark_as_verified_action_seq`, ... | kendi identity satırı ve uzak identity'ler (`recipient_type` telefon ve LID hesaplarını ayırır) |
| `sessions` | `_id`, `device_id`, `record`, `timestamp`, `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope` | Double Ratchet session'ları |
| `prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `key_type` | tek kullanımlık prekey'ler |
| `signed_prekeys` | `_id`, `prekey_id` UNIQUE, `timestamp`, `record`, `key_type` | |
| `kyber_prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `last_resort_key` | post-quantum prekey'ler |
| `prekey_uploads` | `_id`, `upload_timestamp`, `key_type` | |
| `sender_keys` | `_id`, `group_id`, `device_id`, `record`, `timestamp`, `sender_account_id`, `sender_account_type`, `bucket_id` | grup sender key'leri |
| `message_base_key` | `_id`, `msg_key_remote_jid`, `msg_key_from_me`, `msg_key_id`, `recipient_id`, `recipient_type`, `device_id`, `last_alice_base_key`, `timestamp` | |
| `chat_stanza_queue`, `e2ee_stanza_queue`, `unordered_stanza_queue`, `preacks`, `stanza_sts` | `stanza_id`, `stanza_key` UNIQUE, `stanza_class`, `chat_jid`, `sender_jid`, `stanza_payload`, ... | decrypt öncesi gelen stanza'ların kalıcı saklanması |

Signal store'un Java katmanı bu tablolar üzerinde `signal_protocol_store` tarzı koddur. Hesap düzeyindeki crypto pref'leri burada değil `keystore.xml` ve `wacrypto.xml` içinde yaşar (8.3).

---

## 6. sync.db, companion_devices.db ve daha küçük veritabanları

| DB | Tablolar ve anahtar sütunlar |
|----|------------------------|
| `sync.db` | `syncd_mutations` (`mutation_index` UNIQUE, `mutation_value` BLOB, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name`), `pending_mutations` (aynısı artı `operation`, `is_ready_to_sync`), `collection_versions` (`collection_name` PK, `version`, `lt_hash` BLOB, `dirty_version`), `crypto_info` (`device_id`, `epoch`, `key_data`, `timestamp`, `fingerprint`, `stale_timestamp`), `missing_keys`, `msg_history_sync`, `history_sync_companion`, `peer_messages`, `placeholder_retry_message`, `rmr_response_error`. Protokol: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md) |
| `companion_devices.db` | `devices`: `device_id`, `device_os`, `platform_type`, `last_active`, `login_time`, `logout_time`, `adv_key_index`, `full_sync_required`, `place_name`, `nickname`, ... Protokol: [WA_LINKED_DEVICE_PAIRING.md](WA_LINKED_DEVICE_PAIRING.md) |
| `status.db` | `status`, `status_text`, `status_thumbnail`, `status_info`, `status_interactions`, `status_interactions_totals`, `status_seen_receipt`, `status_receipt_device`, `status_reply`, `status_send_part`, `status_privacy_custom_list`, `status_crossposting_v2/_v3`, ... artı `key_value_store` (`row_id`, `key`, `value`) |
| `backup.db` | `backups`, `backup_props` (`prop_name`, `prop_value`; satır `wa_db_schema_version`) |
| `chatsettings.db` | `settings`: `_id`, `jid`, `deleted`, `mute_end`, `muted_notifications`, `use_custom_notifications`, `message_tone`, `call_tone`, `status_muted`, `pinned`, `pinned_time`, `media_visibility`, `mute_reactions`, `wallpaper_*`, `auto_delete_media`, `transcription_locale`, `source_lang`, `target_lang`, `snooze_end_time`, `theme_id` (39 sütun) |
| `stickers.db` | `stickers` (`plain_file_hash`, `encrypted_file_hash`, `media_key`, `mime_type`, `sticker_pack_id`, `file_path`, `url`, `direct_path`, `emojis`, `is_lottie`, ...), `recent_stickers`, `starred_stickers`, `installed_sticker_packs`; `payments.db`: `methods` (`credential_id` PK, `country`, `issuer_name`, `type`, `balance_1000`), `contacts`, `receipts`, `tmp_transactions` |

---

## 7. Yedekler ve crypt15

### 7.1 Yerel yedek dosyaları

| Ad kalıbı (found, `AbstractC26994Bml`, `C29412Cpb`) | İçerik |
|--------------------------------------------------------|---------|
| `msgstore.db.crypt15`, `msgstore.db.crypt14` | tam sohbet veritabanı yedeği (regex `msgstore.db.crypt(\d+)`) |
| `msgstore-increment-<N>.db.crypt<V>` | artımlı yedek |
| `backup_settings.json.crypt<V>`, `status_backup.db.crypt<V>`, `commerce_backup.db.crypt<V>`, `chat_transfer_settings.json.crypt<V>` | ayarlar, status, commerce, chat-transfer ayarları |
| `stickers.db.crypt<V>`, `chatsettingsbackup.db`, `wa-backup.db` | sticker / sohbet ayarları / wa.db yedekleri (bileşen adları aşağıda) |

Kök, harici medya kökü altındaki `Backups/`'tır (`C0KE.A02`; eski `Databases/`, `C0KE.A03`). Kök `external_storage_type` pref'iyle seçilir (`scoped` değeri `C11160Xu.A07` içinde kontrol edilir; diğer değerler listelenmedi); `EnumC046905z` `getExternalMediaDirs()[0]`, `getExternalStorageDirectory()`, uygulamaya özel harici dizinler veya dahili dizinlere çözümlenebilir. İkincil hesaplar `Media/WhatsApp ...` yolları için `<root>/accounts/<dirId>` kullanır (`C0KE.A00`).

Yedek bileşenleri (`CMN` alt sınıflarındaki `A0F` adları, found): `stickers`, `stickers-db`, `wallpapers`, `payment-backgrounds-v2`, `chat-transfer`, `wa-db`, `commerce-db`, `status_db`, `offloaded-media.db`, `chatlock_backup`, `chat-settings`, `backup-settings`. `backup_prefs` her bileşen için `<component>_backup_size` / `_backup_status` tutar (8.3).

Yedek arayüzündeki medya kategorileri (`EnumC26330BbW`, 17 değer): `CHAT_DB`, `SETTINGS`, `STATUS_DB`, `COMMERCE_DB`, `OTHER_DB`, `IMAGES`, `VIDEOS`, `AUDIO`, `VOICE_NOTES`, `VIDEO_NOTES`, `GIFS`, `DOCUMENTS`, `STICKERS`, `STICKER_PACKS`, `PROFILE_PHOTOS`, `EXCLUDED_STICKERS`, `OTHER`.

### 7.2 crypt15 dosya öneki (found)

`EnumC26325BbR`: `UNENCRYPTED` 0, `CRYPT14` 14, `CRYPT15` 15 (numarasız bir `.crypt` soneki eski biçimdir; `CKv` `.crypt` ile eşleşir). crypt15 okuyucusu (`BN4.A09`), ciphertext'ten önce delimited bir protobuf `BackupPrefix` (`BCE`) ayrıştırır:

| Alan | Numara | Tür | Kullanım |
|-------|--------|------|-----|
| `key_type_deprecated` | **1** | enum | eski anahtar türü |
| `wa_provided_key_data` | **2** | bytes | sunucu tarafından sağlanan anahtarlar için anahtar verisi |
| `e2ee_key_data` | **3** | message | uçtan uca şifreli yedek için anahtar verisi |
| `backup_metadata` | **4** | `BD0` | aşağıya bakın |
| `passkey_encryption_metadata` | **5** | message | passkey yolu (`parsePasskeyEncryptionMetadata`) |
| `key_type_new` | **6** | enum | güncel anahtar türü |

Anahtar türleri (`BdX`): `WA_PROVIDED` 0, `E2EE_DEPRECATED` 1, `E2EE_PASSWORD` 2, `E2EE_ENCRYPTION_KEY` 3, `E2EE_PASSKEY` 4.

`BackupMetadata` (`BD0`) alanları (seçki): `app_version` **1**, `device_model` **2**, `jid_suffix` **3**, `backup_version` **4**, `backup_export_file_size` **38**, `cleaned_db` **39**, `backup_encrypted_hash_salt` **40**, `backup_encrypted_hash` **41**, `identifier_type` **42**, `lid_suffix` **43**, `display_suffix` **44**, ayrıca yaklaşık 30 `*_migration_finished` boolean'ı (numaralar 5 ile 35). Restore sırasında `EncBackupUtils`, `jid_suffix` değerini kayıtlı kullanıcıyla karşılaştırır (`has-jid-user-mismatch`): bir yedek, onu üreten hesaba bağlıdır.

Ciphertext'in cipher, KDF ve MAC düzeni burada okunmadı (unknown).

### 7.3 Yedek anahtar materyali

| Dosya (`files/` içinde) | İçerik | Kanıt |
|--------------------|---------|----------|
| `encrypted_backup.key` | uçtan uca şifreli yedeğin 32 baytlık kök anahtarı (`C29861Ep.A09`, uzunluk == 32 olarak kontrol edilir); `A04(...)` ile yazılır, muhtemelen bir KeyStore encapsulation anahtarıyla sarılır (`failed to load or create KeyStore encapsulation key`) | found |
| `encrypted_backup.key_id` | anahtar tanımlayıcısı | found |
| `password_data.key`, `passkey_data.key` | password ve passkey varyantlarının durumu (passkey verisi JSON'dur) | found |
| `vault_backup.key` | `C00L.A0H(32)` ile üretilen 32 baytlık vault anahtarı; okunamayan bir dosyanın üzerine yazmayı reddeder (`vault backup key present but could not be read`) | found |
| `prf_derived_root_key.key`, `secret_code.key` | passkey PRF'inden türetilen kök anahtar, secret-code anahtarı | ad found, içerik unknown |
| `backup_token`, `foa_backup_token` | token dosyası (`CMc`, accounts-center hesabı için `foa_` varyantı) | found |

`AbstractC29801Ej` `encrypted_backup.key(_id)`, `password_data.key`, `passkey_data.key`, `vault_backup.key` dosyalarını birlikte siler (anahtar sıfırlama).

### 7.4 Android auto-backup ve migration provider (found)

| Öğe | Değer |
|------|-------|
| `android:allowBackup` | `true`, `fullBackupOnly=true`, backup agent `SystemBackupAgent` |
| `fullBackupContent` (`xml0003`) ve `dataExtractionRules` (`xml0006`: cloud-backup ve device-transfer) | **her** domain'i hariç tutar (`root`, `file`, `database`, `sharedpref`, `external`, `device_*`). Platform tarafından hiçbir şey aktarılmaz |
| `cross-platform-transfer platform="ios"` | iOS bundle id'si ile tanımlı; aktarım `OsMigrationAppDataService` üzerinden gider (izin `android.permission.BACKUP`) |
| `MigrationContentProvider` | exported, `readPermission com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` (protectionLevel `signature`), `grantUriPermissions=false`. URI'ler: `msg_store`, `unencrypted_msg_store`, `wa_db`, `chat_setting_store`, `sticker_store`, `wallpaper`, `share_preferences`, `media`, `chat_lock_passcode`. `DirectMigrationContentProvider` aynı izni kullanır. Amaç (aynı imzalayıcıya ait kardeş uygulamaya devir) inferred |

---

## 8. SharedPreferences

### 8.1 Factory

`C00S` (SharedPreferencesFactory, `A04(C00G, name)`): `<dataDir>/shared_prefs/<name>.xml` üzerinde özel bir implementasyon döndürür (`C052308r` dosya wrapper'ı; sınıflar `C052408s` / `RRP`), dizin oluşturulamazsa sistemin `getSharedPreferences(name, 0)` çağrısına geri düşer. Diskteki baytların standart Android XML'i olup olmadığı kodda doğrulanmadı (yalnızca dosya uzantısı).

| Bilgi | Kanıt |
|------|----------|
| `AbstractC051008e` içinde özel işlem gören ad kümeleri (`A02`, `A03`: implementasyonun feature flag'leri; `A00`, `A01`, `A04`: kapsamlı kümeler) | found; `C00G(boolean,boolean,boolean)` flag semantiği unknown |
| `A05` kümesi (`multi_account_metadata`, `group_history_usage`, `hatch_group_agent`, `hatch_group_agent_debug`, `smb_token_lockout_cooldown`) bu factory tarafından oluşturulmamalıdır: mesaj `Pref not allowed to instantiate using SharedPreferencesFactory, use MultiAccountSharedPreferencesFactory` | found |
| Ana dosya adları `AbstractC051108f` içinden türer: `com.whatsapp_preferences` ve `com.whatsapp_preferences_light` | found |
| `SharedPreferencesUsageRepository` (`C052508t`) pref dosyası başına yükleme sürelerini kaydeder (`load`, `load2`); `ab-props`, `ab-props-back-up`, `ab-prechatd-props`, `ab-props-backup`, `dropped_wam_events`, `keystore` atlanır | found: pref'lerin kendileri hakkında telemetri |
| `C09E` (kullanımdan kalkmış "Me" ve pref god-class'ı) `com.whatsapp_preferences_light` dosyasını sarar (`C1WL` case 23); birçok küçük wrapper (`C1DH`, `C56902Wq`, `C0G1`) bu tek dosyanın görünümleridir | found |
| Default `com.whatsapp_preferences` düz Android dosyasıdır; `chatCounts` ayrı bir dosyadır (`RP5`) | found |

### 8.2 Alana göre dosyalar (adlar kodda bulundu)

| Alan | Dosyalar |
|------|-------|
| Core | `com.whatsapp_preferences`, `com.whatsapp_preferences_light`, `startup_prefs`, `reg_prefs`, `register_phone_prefs`, `registration.verifyphone.VerifyPhoneNumber`, `registration.app.phonenumberentry.RegisterPhone`, `registration.app.verifyphone.VerifyPhoneNumber`, `multi_account_metadata`, `account_linking_prefs`, `fb_credentials_prefs`, `fb_linked_account`, `accounts_center_registration_prefs` |
| Flag'ler | `ab-props`, `ab-props-backup`, `ab-props-back-up`, `ab-prechatd-props`, `groupAbProps`, `network_resources_pref` |
| Crypto | `keystore`, `wacrypto`, `security_prefs`, `nc_prefs`, `chat_lock`, `migration_export`, `AccountDefenceLocalDataRepository_prefs` |
| Yedek / sync | `backup_prefs`, `chat_transfer_prefs`, `syncd_prefs`, `contact_sync_prefs`, `device_capabilities`, `companion_mode_prefs` |
| Özellikler | `username_prefs`, `meta_ai_prefs`, `bonsai_prefs`, `paa_prefs`, `status_prefs`, `newsletter_prefs`, `voip_prefs`, `route_selector_prefs`, `interop_ui`, `interop_badge_prefs`, `avatar_prefs`, `bloks`, `privacy_disclosure_store`, `user_notice_prefs`, `tos_gating_prefs` |
| Telemetri | `critical_event_client_prefs`, `anr_shared_prefs`, `time_spent_prefs`, `dropped_wam_events`, `wam_prefs`, `chatCounts` |
| Üçüncü taraf SDK | `com.google.android.gms.appid`, `com.google.firebase.messaging`, `WebViewChromiumPrefs` (sistem) |

### 8.3 Önemli anahtarlar (tüm anahtar adları 2.26.41.6'da found; değerler yeniden üretilmedi)

| Dosya | Anahtar | Tür / kullanım |
|------|-----|-----------|
| `startup_prefs` | `registration_state` | int; `C06810Gk` predicate'leri: 0/1 initial, 3, 4, 5, 8 (flash verify), 12, 15, 17 (email OTP), 20, 23 |
| | `startup_migrated_version` | int; hedef **20**, `WaStartupSharedPreferences` bunun altındaki migration'ları çalıştırır |
| | `push_name` | kendi görünen adı |
| | `force_db_check`, `force_wadb_check` | msgstore / wa.db integrity kontrolünü zorlar (`C0HS.BoJ`, `C12650bW.onCreate` tarafından temizlenir) |
| | `pending_repair_db_name`, `pending_repair_db_file_id`, `pending_repair_corruption_type`, `pending_repair_attempt_count`, `pending_repair_request_id`, `pending_repair_timestamp`, `pending_repair_gate_suppressed` | veritabanı onarım kuyruğu |
| | `privacy_fingerprint_enabled`, `night_mode`, `client_server_time_diff` (`C050708b` tarafından okunur) | |
| `com.whatsapp_preferences_light` | `registration_jid`, `registration_lid`, `cc`, `ph`, `self_lid`, `registration_initialized_time`, `registration_success_time_ms`, `registration_wipe_info_timestamp`, `reg_attempts_verify_code` | bu kurulumun kimliği (`RegistrationManager.A0I` tarafından temizlenir) |
| | `adv_raw_id`, `adv_current_key_index`, `adv_timestamp_sec`, `phoneid_id`, `phoneid_timestamp` | ADV / phone id durumu |
| | `privacy_last_seen`, `privacy_profile_photo`, `privacy_status`, `privacy_online`, `read_receipts_enabled`, `privacy_token_batch_offset_sec` | gizlilik ayarları (`C18260lS`, `C09E.A0S()`) |
| | `md_messaging_enabled`, `last_login_time`, `last_daily_cron`, `next_randomized_daily_cron`, `nct_salt` | multi-device flag'i, cron kayıtları, tctoken salt'ı ([WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md)) |
| `backup_prefs` | `gdrive_state`, `backup_provider`, `backup_encryption_method`, `encrypted_backup_fleet_migration_state`, `encrypted_backup_num_attempts_remaining`, `google_restore_result`, `msg_restore_timestamp`, `last_seen_app_version`, `device_backup_integration_enabled`, `blocking_restore_in_progress`, `cloud_api_type`, `restore_second_verification_needed` | yedekleme ve restore durumu (`C22090sX`) |
| `keystore` | `server_static_public`, `server_static_pq_public`, `client_static_keypair_pwd_enc`, `client_static_keypair_enc_success`, `can_user_android_key_store`, `remaining_auth_key_rotation_attempts` | Noise static anahtarları ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md), [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md)) |
| `wacrypto` | `signed_prekey_id_seed_migration_completed` | Signal prekey id seed migration'ı |
| `ohai_key_config` (`C53596Nzj` içindeki pref adı) | `public_key` ve key-config alanları | OHAI gateway anahtarı |
| `syncd_prefs` | `syncd_dirty`, `syncd_bootstrap_state`, `syncd_bootstrapped_mutations` (set), `mutation_counter` | app-state sync bootstrap'i |
| `companion_mode_prefs` | `previously_logged_out_from_primary` | companion durumu |
| `username_prefs` | `username_reservation_state`, `username_pin` | bkz. [WA_USERNAME.md](WA_USERNAME.md) |
| `route_selector_prefs` | `media_conn` | cache'lenmiş medya rotası (host listesi ve auth verisi; [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md)) |
| `ab-props` | sayısal string anahtarlar (config kodları), `ab_props:sys:last_refresh_time`, `ab_props:sys:config_hash`, `ab_props:sys:last_version`; `com.whatsapp_preferences` `ab_props:hash_v2` tutar | AB prop cache'i; `ab-props-backup` önceki kopyadır |
| `chatCounts` | sohbet başına sayaçlar, `thread_user_secret` (32 rastgele bayt, base64) | `WamThreadIdManager` thread id'lerini bununla HMAC'ler; `RP5.A0w` bunu bir reset boyunca korur |

---

## 9. Файлы, кэши и структура медиа

### 9.1 Внутренний `files/` (found, если не помечено иначе)

| Путь | Содержимое |
|------|------------|
| `me` | сериализованная в Java запись `Me` (`C9V.A01`, поля включают `cc`, `number`); `me.jpg` / `me_old.jpg` — фото профиля |
| `rc2` | зашифрованное AES/OFB 160-битное случайное значение, генерируемое при первом использовании для двух строковых входов (`K49.A0v`, `C00L.A0G`; inferred: код страны и номер); назначение inferred (секрет регистрации). Удаляется wipe-runnable `RunnableC29329CoG`, `RunnableC46625KYz` |
| `backup_token`, `foa_backup_token`, `encrypted_backup.key*`, `vault_backup.key` | раздел 7.3 |
| `invalid_numbers`, `login_failed`, `customTSValues`, `emoji` | малые файлы состояния (`IJU`, `C06850Go`) |
| `statistics.json`, `network_statistics.json` | счётчики rx / tx (`C17B`, `C17J`; ключи `statistics`, `bytes`, `timestamp`, `rx_data`, `tx_data`) |
| `Logs/` | файлы логов (10.1) |
| `decompressed/libs.spo/` (+ `.superpack_version`) | библиотеки, распаковываемые в рантайме `C0EE`; **исключены из любого wipe** |
| `mobileconfig/` | `mc_overrides.json`, `id_name_mapping.json` (`C053409d`) и хранилище конфигурации |
| `falco/`, `wam/` | движки телеметрии (10) |
| `Stickers/`, `Drafts/`, `GroupHistory/`, `Payment Backgrounds/`, `Wallpapers/`, `.trash/`, `biz_directory/`, `privacy_disclosure/<version>/`, `downloadable/`, `NetworkResource/`, `MNSResolverCache/`, `app_state/` | кэши функций (`C0I1`, `C58398QKk`, `C27574Bxe`, `MNSStreamRuntime`, `C06110Cn`) |

Другие приватные каталоги, названные switch-ем конфигурации хранилища (`AbstractC13030c9`): `lib-compressed`, `app_secure_shared`, `app_sigquit`, `modules`, `app_optsvc_analytics`, `app_overtheair`, `app_qpl`, `app_light_prefs`, `cache/secure_shared`, `files/secure_shared`, `app_minidumps`, `app_fb-forker-tmp`.

### 9.2 `cache/` (found)

| Каталог | Примечание |
|---------|------------|
| `thumb_decoded_cache` | дисковый LRU, **52428800 байт (50 MiB)** (`C33000EZy`) |
| `webp_static_cache`, `stickers_cache`, `avatar-temporary`, `interop_image_cache`, `tigon_http_client`, `ML_MODEL`, `hatch_space_images`, `meta_ai_thread_photo_uploads` | кэши изображений / сети / моделей |
| `Profile Pictures/` | привязан к аккаунту (`C28025CFb.A01` возвращает каталог кэша; `QLH` строит `Profile Pictures`) |

### 9.3 Вторичные аккаунты (found)

`getDir("account_switching")` (= `app_account_switching/`) содержит `active_account` (id активного каталога, `C00W`) и список аккаунтов (`C25160AsA`). Данные вторичного аккаунта лежат в `<dataDir>/accounts/<dirId>/{databases,files,cache}` (`C28025CFb`), а его медиа — в `<root>/accounts/<dirId>`; аккаунт по умолчанию использует обычные каталоги. `account_switcher.db` и prefs multi-account являются общими.

### 9.4 Внешний медиа-корень (found)

`<root>/Media/WhatsApp <Category>/` с категориями `Images`, `Video`, `Audio`, `Documents`, `Voice Notes`, `Video Notes`, `Animated Gifs`, `Stickers`, `Sticker Packs`, `Profile Photos`, `Backup Excluded Stickers` (`AbstractC26994Bml`), подпапками `Sent`, `Private`, `.Thumbs` (`*.prog.thumb.jpg`, `C0I1.A08`), `.Shared`, маркерами `.nomedia`. `message_media.file_path` хранит часть после корня.

---

## 10. Логи и телеметрия, хранимые на устройстве

### 10.1 Логи (found)

| Файл | Деталь |
|------|--------|
| `files/Logs/whatsapp.log`, `whatsapp.tmp` | текстовый лог, заголовок `==== logfile version=2.26.41.6 level=4 ====`; при ротации сжимается в `.gz` с датой (`Log.rotate`, `AbstractC28128CKx.A00`). `C24971Ap6` собирает `Logs` вместе с каталогом db для экспорта в поддержку / баг-репорт |
| `app_minidumps/`, `<dir>/minidumps`, `crash_upload/` | нативные дампы падений и промежуточное хранилище загрузки (`C0FQ`, `JJ1`, `CKN`, `ExceptionsUploadService`) |
| `anr_report_<n>.dmp`, `anr_shared_prefs` | отчёты ANR (`C45432Jrw`) |
| `cache/qpl`, `app_qpl` | трассы QuickPerformanceLogger |

### 10.2 Движки телеметрии

| Путь | Движок | Свидетельство |
|------|--------|---------------|
| `files/wam/` | рабочий каталог WAM, передаваемый в `WAJContextInitWAMRuntime` (JNI) | `RunnableC29323CoA`; prefs `dropped_wam_events` и `wam_prefs` |
| `files/falco/` | логгер событий в `libffsingletonmerged.so` | нативные строки ниже |
| `files/mobileconfig/` | хранилище Mobile Config | `C053409d` |

Файл Falco SQLite `FFLogger.sql` (расположение inferred: Java создаёт `files/falco/`, имя файла — строка в нативной библиотеке): таблицы, присутствующие в нативных строках схемы (found): `event`, `buffer_event`, `upload` (`request_data`, `num_events`, `is_compressed`, `compression_method`), `claim` (`principal_subject_hash`, `claim`, `expires_at`), `collection_constraint`, `event_config` (`event_config_hash` UNIQUE, `event_name`, `sampling_rate`, `collection_constraint_ref`, `is_deidentified`), `checksum`, `amendment_outbox`, индекс `event_0` по `event(requested_latency)`; `batch` присоединяется по `identities_hash`. `fflogger_health_counters.bin` хранит счётчики самоинструментирования (`mobile_health_counters`). Java-сторона только создаёт каталог.

### 10.3 Самоизмерение

wa.db `wa_storage_monitoring_data` / `_jobs` (размеры по таблицам и неиспользуемые байты по `db_name`) и статистика загрузки prefs (8.1) — телеметрия, которую клиент ведёт о собственном хранилище. Сам конвейер событий WAM вне рамок этого отчёта.

---

## 11. Что и когда удаляется

### 11.1 Операции

| Операция | Точка входа (2.26.41.6) | Эффект |
|----------|-------------------------|--------|
| Удаление аккаунта / сброс локальных данных | `C25007Aph.A0L`, затем `A02` (`removeDatabasesAndResetState`) | полная локальная очистка, 11.2 |
| Companion удалён | `C25007Aph.A0M` (`deleteCompanionCleanup`) | `ActivityManager.clearApplicationUserData()` (запасной вариант `pm clear <package>`, затем запасной `A02`) |
| Повторная регистрация | `RegistrationManager.A06` (`reregister reason=`) | очищает prefs регистрации и `me`, 11.3 |
| Unregister с устройства | `RegistrationManager.A0F` | останавливает соединение с `should_unregister=true`, удаляет `me`, очищает состояние |
| Logout (основное устройство, с multi-account) | `LogoutManager` (`AccountLogoutMutation`, w:mex) | logout на сервере, аккаунт помечается вышедшим; данные остаются, пока пользователь не удалит вышедший аккаунт (11.4). Удаляет ли первый шаг что-либо локально, не прослежено (unknown) |
| Удаление вышедшего аккаунта | `LogoutManager.removeLoggedOutAccountWithCleanup` | удаляет запись аккаунта, затем `deleteDefaultAccountDirectories` или `deleteSecondaryAccountDirectories`, затем состояние резервного копирования GMS |

### 11.2 Удаление аккаунта (`C25007Aph.A02`, found)

| Цель | Действие |
|------|----------|
| Хранилища в памяти, менеджеры функций | очищаются; `last_contact_full_sync` = -1 |
| Базы данных | delete каждого helper-а (`A0D`, `A0N`): msgstore через `C0HC` (`msgstore-manager/deletedb/result`), wa.db (`deleteaccountconfirm/wa-db-delete-incomplete` — ошибка, если файлы остались), commerce, `emojidictionary`, хранилище языковых пакетов, `MediaJobDataStore`, хранилища history-sync, бизнес-каталог (`files/biz_directory`) |
| `files/` | все записи, кроме `decompressed`; `Logs` сохраняется, если установлен флаг `z` (путь companion) |
| Внешний корень | `Backups/` удаляется и создаётся пустым заново, файлы `Databases/` удаляются (`AbstractC28132CLd.A04`), только если состояние внешнего хранилища пригодно |
| `com.whatsapp_preferences` | `clear()`, затем `version` перезаписывается значением `2.26.41.6` |
| `backup_prefs` | `clear()`, но `last_seen_app_version` и `device_backup_integration_enabled` восстанавливаются |
| `chatCounts` | удаляются все ключи, кроме `thread_user_secret` (`RP5.A0A`) |
| Прочие prefs | `avatar_prefs`, файлы регистрации и VerifyPhone, регистрация companion (`registration_device_id`, `companion_registration_state` = 0), несколько prefs функций |
| WebView | cookies и web storage удаляются, также для именованных профилей при наличии multi-profile |

### 11.3 Reregister / unregister (found)

`RegistrationManager.A0I` удаляет `registration_jid`, `registration_lid`, `cc`, `ph` и `registration_wipe_info_timestamp`; `A0A` очищает prefs двух экранов регистрации; файл `me` удаляется (`rm-me`).

### 11.4 Диалог чатов вышедшего пользователя (`FilesDeletionUtility`)

Удаляет внешний корень вышедшего пользователя, `cacheDir`, каждую запись `filesDir`, кроме `decompressed`, каталог files вторичного аккаунта, затем вызывает delete у helper-ов БД; неудачное удаление wa.db выбрасывает исключение, и диалог сообщает об ошибке (`FilesDeletionUtility/deleteInternalFiles/wa-db-delete-incomplete`).

### 11.5 Удаление файлов multi-account (`AccountSwitchingFileManager.deleteDefaultAccountDirectories`)

Для аккаунта по умолчанию: `shared_prefs` удаляется, кроме allow-list; `databases` удаляется, кроме `account_switcher.db` (и его вариантов с суффиксами); остальные каталоги удаляются целиком.

---

## 12. Заметки о Baileys (inferred-маппинг)

Baileys хранит учётные данные и хранилище по ключам (`creds`, pre-key, session, sender-key, app-state-sync-key / -version, lid-mapping, device-list, tctoken). Концептуальные аналоги на Android (inferred; в коде они не связаны):

| Состояние Baileys | Хранилище Android |
|-------------------|-------------------|
| `session`, `pre-key`, signed pre-key | `axolotl.db` `sessions`, `prekeys`, `signed_prekeys` (+ `kyber_prekeys` на Android) |
| `sender-key`, `sender-key-memory` | `axolotl.db` `sender_keys`; распределение по устройствам в msgstore `group_participant_device` |
| ключ / версия app-state sync | `sync.db` `crypto_info` (`key_data`, `epoch`), `collection_versions` (`lt_hash`) |
| lid mapping | msgstore `jid_map` (+ `lid_display_name`) |
| device list | msgstore `user_device`, `user_device_info` |
| `tctoken` | wa.db `wa_trusted_contacts(_send)` |
| `creds.me`, registration id, ADV | `files/me`, prefs `adv_*`, строка `identities` |

У сессии Baileys нет эквивалента таблицы `message`; удаление её auth state — аналог wipe из 11 и требует новой привязки.

---

## 13. Ошибки и подводные камни

| Симптом | Причина | Исправление / примечание |
|---------|---------|--------------------------|
| `msgstore/upgrade version 1 to N` никогда не появляется | `user_version` msgstore всегда равен 1 | читайте `props.msgtore_db_schema_version` для реального состояния схемы |
| msgstore "restored-db-not-indexed" / `RestoredIndexesPending` | БД восстановлена из резервной копии; индексы создаются лениво | ключи `props` `MessagesDBHelper_*`; выполнение завершается асинхронно |
| `still-corrupt-after-repair`, `delete-superseded-by-new-repair` | проверка целостности не пройдена (`C0HC.checkhealth`) | очередь в `startup_prefs` `pending_repair_*`; `force_db_check` |
| wa.db внезапно пуста после обновления | switch обновления удалил таблицы (версии 3–94) или изменился хеш схемы | wa.db восстанавливается с сервера и из адресной книги |
| `deleteaccountconfirm/completion-blocked/wa-db-files-remain` | файлы wa.db не удалось удалить | повторить; очистка прерывается с `Be5` |
| Восстановление отклоняет резервную копию (`has-jid-user-mismatch`) | `BackupMetadata.jid_suffix` отличается от аккаунта | восстанавливать с тем же номером |
| `backup-file-crypt15/prefix null` | файл пуст или не crypt15 | проверить delimited-префикс (7.2) |
| `vault backup key present but could not be read` | `vault_backup.key` нечитаем | код отказывается создавать замену, чтобы не перезаписать восстановимый файл |
| `Pref not allowed to instantiate using SharedPreferencesFactory` | pref только для multi-account создан не той фабрикой | использовать `MultiAccountSharedPreferencesFactory` |
| Данные вышедшего аккаунта остаются | logout не удаляет данные аккаунта (11.1) | удалить аккаунт явно |

---

## 14. Ключевые различия

| Не путать | Различие |
|-----------|----------|
| `msgstore.db` и `wa.db` | сообщения, чаты и строки `jid` против контактов, блоклистов, токенов доверенных контактов, бизнес- и integrity-кэшей; id строк JID существуют только в msgstore, ключи wa.db — сырые строки JID |
| `jid._id` и сырой JID | столбцы `*_jid_row_id` — id строк msgstore; таблицы `wa_*` используют `jid` TEXT |
| SQLite `user_version` и версия схемы | у msgstore всегда 1; у wa.db 95; схема — хеш в `props` (msgstore) или тег (wa.db) |
| Автобэкап Android и резервная копия чатов | автобэкап исключает всё; резервная копия чатов — собственный файл приложения `crypt15` во внешнем корне |
| Файл crypt15 и файлы ключей | шифртекст в `Backups/`; ключи в `files/*.key` (никогда в одной папке) |
| `com.whatsapp_preferences` и `_light` | обычные prefs Android (при очистке сводятся к ключу версии) против файла собственной реализации, используемого `C09E` (идентичность, приватность, флаги) |
| `ab-props` и `wa_props` | коды AB-экспериментов (prefs) против серверных свойств аккаунта (таблица wa.db) |
| Logout и удаление аккаунта | logout помечает аккаунт; удаление стирает БД, файлы, Backups, prefs (11) |
| Falco и WAM | Falco — логгер событий SQLite в нативной библиотеке; `wam/` — рабочий каталог WAM; оба — телеметрия |
| Файлы от сторонних модов | дополнительные базы данных, логи stanza или диагностика хуков не создаются оригинальным приложением и здесь не рассматриваются |
---

## 15. Структура и жизненный цикл

```
[App start]
   │
   ▼
 SharedPreferencesFactory ── shared_prefs/<name>.xml
   │         startup_prefs: registration_state, startup_migrated_version (20)
   ▼
 DB helpers open (WAL, requery SQLite, no cipher)
   ├─ msgstore.db   user_version 1 ── props.msgtore_db_schema_version (hash) ── CREATE IF NOT EXISTS
   ├─ wa.db         v95 ── upgrade switch (3..94) | onCreate ── wa_db_schema_version
   ├─ axolotl.db    v40 ── Signal sessions / prekeys / kyber / sender keys
   └─ sync.db       stepwise ALTER | reset on downgrade
   │
   ▼
 Runtime
   ├─ message in/out ──► message + satellites + receipt_* + message_add_on*
   ├─ media ───────────► message_media / thumbnails in DB; files under <root>/Media/WhatsApp <Cat>/
   ├─ contacts / tokens ► wa_contacts, wa_trusted_contacts(_send), wa_biz_integrity_signals
   └─ telemetry ───────► Logs/whatsapp.log, falco/, wam/, daily_metrics.db
   │
   ▼
 [Backup]  msgstore.db ──► Backups/msgstore.db.crypt15 (BackupPrefix + ciphertext)
             keys ───────► files/encrypted_backup.key, vault_backup.key
   │
   ▼
 [Logout / delete]
   logout ───► AccountLogoutMutation, account marked logged out (data kept)
   delete ───► DB helpers delete, files/ (except decompressed), Backups/, prefs cleared,
               chatCounts keeps thread_user_secret, backup_prefs keeps 2 keys
```

---

## 16. Не охвачено и unknown

| Тема | Статус |
|------|--------|
| Атрибуция БД по таблицам для 306 + 422 классов таблиц, кроме проверенных | размеры наборов found; соответствие каждого класса своей базе по графу DI не прослежено (inferred по FK и именам) |
| Типы столбцов, значения по умолчанию и NOT NULL для таблиц, построенных вспомогательными функциями | декомпилятор часть пропускает; перечислены только имена |
| Оставшиеся ~250 таблиц msgstore, оставшиеся таблицы wa.db и status.db | имена перечислены в семействах; столбцы не извлекались |
| Формат шифртекста crypt15, KDF, MAC; содержимое вложенных сообщений `BackupPrefix` | unknown |
| Стандартный XML-формат на диске у собственной реализации prefs | не проверено |
| Полный список ключей каждого файла prefs (сотни ключей) | только файлы и ключи, названные в 8.3 |
| Смысл флагов `C00G`, id типов add-on, значений `registration_state` | частично названы |
| Версии `sync.db`, `chatsettings.db`, `stickers.db`, `commerce.db`, `daily_metrics.db`, `location.db` | не выяснены |
| Назначение `files/rc2`, `files/key` | `rc2` inferred; `key` не выяснен |
| Удаляет ли один лишь logout основного устройства локальные данные | не прослежено |
| Поведение в рантайме, размеры файлов, содержимое WAL | только статический анализ |
