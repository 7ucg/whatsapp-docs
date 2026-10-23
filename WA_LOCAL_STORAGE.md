# WhatsApp Local Storage — Full RE Report
**Version:** 2.26.41.6 | **Date:** 2026-10-23
**Scope:** SQLite databases (names, location, engine, versioning, table framework), msgstore.db and wa.db key tables and columns, axolotl.db, sync.db and the smaller databases, crypt15 backups and backup key files, Android auto-backup rules and the migration content provider, SharedPreferences factory and key inventory, file and cache layout, log and telemetry files, what logout / unregister / reregister / account deletion remove

---

## 1. What is stored where

All statements are static analysis of the decompiled APK and its bundled native libraries. No device data was read. Tier: **found** = read in code, manifest or native strings; **inferred** = deduced from code; **unknown** = not resolved. Obfuscated names are as JADX shows them for 2.26.41.6 and change every build.

### 1.1 Storage map

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

| Location | Content | Survives Android auto-backup |
|----------|---------|------------------------------|
| `databases/` | all SQLite files | no: every domain is excluded (8.1) |
| `shared_prefs/` | settings, flags, keys | no |
| `files/`, `cache/` | key files, caches, logs | no |
| external root `Backups/` | encrypted chat backup (crypt15) | n/a: own backup mechanism (7) |

### 1.2 Engine facts (found)

| Fact | Evidence |
|------|----------|
| SQLite is the bundled `io.requery.android.database.sqlite` build, not the framework one | package in `java_src` |
| No SQLCipher: no `PRAGMA key`, no `sqlcipher` string anywhere in `java_src` | grep; database files are plaintext at rest inside the app sandbox |
| WAL enabled for all helpers built on `AbstractC11350Yn` (`setWriteAheadLoggingEnabled(true)`) | `AbstractC11350Yn`; checkpoint via `PRAGMA wal_checkpoint(FULL)` |
| msgstore opens with `PRAGMA synchronous=NORMAL`, optional `cache_size` (flag **20777**), `PRAGMA secure_delete=1` | `C06980Hc.onOpen`; failure to enable secure_delete is reported as `db-integrity/enable-secure-delete/error/not-enabled` |
| `PRAGMA foreign_keys=ON` is set for sync.db, paa.db, daily_metrics.db, not for msgstore.db | `AbstractC12530bK`, `AbstractC197088a3`, `AbstractC16650iN`; msgstore cascades through triggers (2.3) |

---

## 2. SQLite databases

### 2.1 Inventory

File names are literals (`getDatabasePath(...)` / helper constructors). Table counts are the number of table-definition classes in the DI module that feeds the helper (2.3).

| File | Helper / module (2.26.41.6) | Version / migration | Table classes | Role | Tier |
|------|-----------------------------|---------------------|---------------|------|------|
| `msgstore.db` | `C06980Hc` (factory `C0HH`) | SQLite `user_version` fixed at 1; schema fingerprint in `props` (2.4) | 306 (factory `C1S0`) | messages, chats, JIDs, receipts, calls, newsletters, integrity, AI, TEE | found / set attribution inferred |
| `wa.db` | `C12650bW` | **95** (`creating contacts database version 95`) | 88 (`C8ZL` implementors) | contacts, blocklists, business profiles, trusted-contact tokens, integrity signals | found |
| `axolotl.db` | `C44861sL`, tables `AbstractC11250Yd` | **40** | 15 | Signal sessions, prekeys, sender keys, stanza queues | found |
| `sync.db` | `AbstractC12530bK` (helper `X.1sK`) | stepwise `ALTER` migrations up to at least v50; downgrade = reset | 10 | app-state sync, history sync, peer messages | found, version unknown |
| `status.db` | `C41891nD` | **2** (`StatusDbHelper creating status database version 2`) | 29 (`AbstractC11620Zo`) | status posts and interactions | found |
| `backup.db` | `C44881sN` | **1** | `backups`, `backup_props` | backup bookkeeping; `backup_props` holds `wa_db_schema_version` | found |
| `chatsettings.db` | `C11200Xy("chatsettings.db")` | unknown | `settings` (inferred) | per-chat mute, pin, tone, wallpaper, theme | name found, table inferred |
| `stickers.db` | module `AbstractC149676Ty` | unknown | 18 (module also registers `offloaded_media*`, `backups`, `backup_props`) | sticker packs | found |
| `offloaded-media.db` | `CMN` (backup component) | unknown | `offloaded_media`, `offloaded_media_staging` (inferred attribution) | offloaded media index | found / inferred |
| `payments.db` | `C1S0` anon helper, `AbstractC22520tH` | **5** | `contacts`, `methods`, `receipts`, `tmp_transactions` | payment methods | found |
| `commerce.db` | `C27743C3e` | unknown | unknown | commerce data; has a backup variant `commerce_backup.db` | name found |
| `companion_devices.db` | `C48701zE` | **27** | `devices` (+ others) | linked devices as seen from the primary | found |
| `paa.db` | `ManagedAccountDbHelper` (`AbstractC197088a3`) | migrations V1 to V7 | `paa_connection`, `contact_metadata`, `group_metadata` | managed-account (parent-approved account) data | found |
| `daily_metrics.db` | `AbstractC16650iN` | unknown | `poll_event_logging`, `poll_daily_participant`, `comments_event_logging`, `pnh_daily_event_logging`, `community_home_action_logging`, `snapl_payload` | daily event counters | found |
| `qp_payload.db`, `location.db`, `fa_events.db`, `media.db`, `account_switcher.db` | path getters (`C23985AVo`, `C33961Wh`) | unknown | unknown | quick promotions, live location, federated analytics, media jobs (inferred), account list | name found |
| `sqlite_vec.db` | `MessageEmbeddingsStore` | unknown | vector tables (unknown) | on-device message embeddings; present only if enabled | found |
| `emojidictionary.db`, `hsmpacks.db`, `events.db` | `C8JP`, `C6UR` | unknown | unknown | emoji dictionary, template packs, events | name found |
| `wa-backup.db`, `msgstore.db-backup` | `CMN` / `C26042BNa`, `C0KE` | n/a | n/a | local safety copies of wa.db / msgstore | found |
| `migration_prefetcher.db`, `migration_import_metadata.db`, `migration_export_metadata.db` | `C23985AVo` | unknown | unknown | chat-transfer / OS migration state; `migration_prefetcher.db` is deleted by `C28152CMi` | name found |
| `androidx.work.workdb` | WorkManager (`no_backup/`) | Room | standard | job queue | inferred from Room classes (`room_master_table`) |

### 2.2 Which DB holds the tables cited in other reports

| Table | DB file | Table class | Evidence | Report |
|-------|---------|-------------|----------|--------|
| `wa_trusted_contacts`, `wa_trusted_contacts_send` | `wa.db` | `C23627AHs`, `C23628AHt` (`C8ZL`) | wa.db helper recreates them; stores read via `C12810bn` of the wa.db helper | [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_biz_integrity_signals` | `wa.db` | `C53116Nmn` (`C8ZL`) | found | [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 5.1 |
| `start_chat_trust_signals` | `wa.db` | `AI0` (`C8ZL`), trigger on `wa_contacts` | found | ban report 5.2 |
| `integrity_chat_info` | `msgstore.db` | `C08970Ox`, trigger `chat_bd_for_integrity_chat_info_trigger` on `chat` | found, attribution by the FK to `chat` | ban report 5.3 |
| `meta_ai_memory` | **`wa.db`** | `C23621AHm` (`C8ZL`) | found; columns `memory_id`, `memory_content`, `bot_jid_row_id` | [WA_META_AI.md](WA_META_AI.md) |
| `bot_memory_metadata`, `bot_chat_info`, `ai_thread_info` | `msgstore.db` | `C08640Nq`, `C08610Nn`, `C0MO` | in the 306-class set | Meta AI report |

`meta_ai_memory` is in `wa.db`, not in `msgstore.db`: its class implements `C8ZL`, which only the wa.db helper iterates (`C12650bW.onCreate` with `new C08050Lj("wa.db")`). `bot_jid_row_id` references a `jid` row of msgstore, so the column is a cross-database soft reference (inferred; no foreign key is possible across files).

### 2.3 Table framework (how schemas are defined)

Tables are not written as SQL strings. Each table is a class implementing `InterfaceC08060Lk` (wa.db: the sub-interface `C8ZL`) with three hooks (found):

| Hook | Purpose |
|------|---------|
| `ASa(ctx, builder)` | declare columns: `C08080Lm` builder, `.A02` = name, `.A00` = `EnumC08100Lo` type (`INTEGER`, `TEXT`, `REAL`, `BLOB`, `LONG`, ...), flags for primary key / not null / default |
| `ASX(ctx, builder)` | declare indexes (`CRN`, `CRJ` = conditional index) |
| `ASc(builder)` | declare triggers (`CRg`, `CRf`) |

- 422 classes implement `InterfaceC08060Lk` plus 88 implement `C8ZL`. They are provided in DI sets; each helper iterates its set (`C06980Hc.A03`, `C12650bW.onCreate`, `C44881sN`, `C41891nD`).
- Cascade deletes are triggers, not foreign keys: `AbstractC08210Lz.A01` builds `CREATE TRIGGER <parent>_bd_for_<child>_trigger BEFORE DELETE ON <parent> BEGIN DELETE FROM <child> WHERE ...; END` (found; example `message_add_on_reaction` deleted when `message_add_on` rows go).
- Column lists below are extracted from `ASa` in declared order. The decompiler elides some helper-built columns (first column of a few tables, default values); those are marked "(+ jid)" where a query or trigger proves the column. Types are given only where the code states them.
- DB attribution of the 306 msgstore classes is by DI factory `C1S0` (306 `new` calls, includes `message`, `chat`, `jid`) and by the FK triggers to `chat` / `message` / `jid` (inferred). Tables with the same name in two modules exist (`status`, `status_attribution`, `mms_thumbnail_metadata`, `quick_promotion_payload`: msgstore and status.db or wa.db each have a class).

### 2.4 Versioning and migrations

| DB | Strategy (found) |
|----|------------------|
| `msgstore.db` | `onUpgrade` = `onCreate`; `setVersion(1)` always. Real version is a hash stored in table `props`: `msgtore_db_schema_version` and `msgtore_db_schema_indexes_version` = `Arrays.hashCode` over a literal `Consumer-<hex>` tag and `MessageSchemaConfig=1;isGlobalChatDbMigrated=<bool>[;includeNewsletterInteractionTable=true]` (`C06980Hc.A04`). Declarative: tables and indexes are `CREATE ... IF NOT EXISTS` from the class set. Other `props` keys: `MessagesDBHelper_RestoredIndexesPending`, `MessagesDBHelper_CreateAsyncIndexesV2`, `..FailedAttempts` |
| `wa.db` | `onUpgrade` is a switch on old version 3 to 94 that mostly drops tables later recreated; unknown old version falls to `onCreate`; downgrade = `onCreate`. `wa_db_schema_version` is written with a `ConsumerBeta-<hex>` tag. Pref `force_wadb_check` (startup_prefs) forces a re-check. wa.db is rebuildable data (contacts, tokens, caches) |
| `axolotl.db` | versioned (40); old DDL variants visible in `C44861sL` (e.g. `identities` gained `recipient_type`, `next_kyber_prekey_id`, `account_encryption_attestation_type`; `sessions` gained `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope`; `sender_keys` gained `bucket_id`) |
| `sync.db` | stepwise `ALTER TABLE ... ADD` (e.g. `collection_versions.dirty_version`, `history_sync_companion.inline_payload`, `msg_history_sync.size_limit_bytes`); downgrade or unknown version calls `sync-db-helper/reset` which recreates tables, so app state is resynced (inferred) |
| `status.db` | v2; `key_value_store` row `schema_version` |
| `paa.db` | `runMigrationV1`..`V7` (adds columns such as `age_experience`, `snooze_status`, `common_groups_count`) |
| backups (`BD0`) | the crypt15 metadata still carries per-table "migration finished" flags (`message_main`, `receipt_user`, `jid_store`, ...), the history of the old msgstore migrations (7.2) |

---

## 3. msgstore.db: key tables and columns

### 3.1 Table families (found, 306 classes)

| Family | Tables (examples) |
|--------|-------------------|
| Identity | `jid`, `jid_map`, `lid_chat_state`, `lid_display_name`, `jid_user_metadata`, `integrator_display_name` |
| Chat | `chat`, `chat_ephemeral`, `chat_encryption_classification`, `community_chat`, `broadcast_chat_details`, `thread_messages`, `thread_id`, `draft_message_reminder` |
| Message core | `message`, `message_text`, `message_media`, `message_quoted*` (14), `message_edit_info`, `message_revoked`, `message_forwarded`, `message_mentions`, `message_link`, `message_future`, `message_orphan`, `message_send_count`, `message_view_once_media`, `message_ephemeral*` |
| System messages | `message_system` + about 35 `message_system_*` detail tables (group, number_change, lid_change, username_change, device_change, privacy, ...) |
| Add-ons | `message_add_on` and `message_add_on_reaction`, `_poll_vote`, `_poll_vote_selected_option`, `_keep_in_chat`, `_pin_in_chat`, `_question_response`, `_event_response`, `_receipt_device`, `_receipt_coex`, `_status_*` |
| Receipts | `receipt_user`, `receipt_device`, `receipt_coex`, `receipt_orphaned`, `played_self_receipt`, `optimised_delivery_info` |
| Groups | `group_participant_user`, `group_past_participant_user`, `group_participant_device`, `parent_group_participants`, `group_history_*`, `group_root_key_mapping`, `group_notification_version` |
| Devices | `user_device`, `user_device_info`, `primary_device_version`, `agent_devices` |
| Media | `media_hash_thumbnail`, `media_content`, `mms_metadata`, `mms_thumbnail_metadata`, `extended_media_data`, `message_media_map`, `message_streaming_sidecar`, `media_refs`, `message_thumbnail`, `audio_data`, `voice_data` |
| Calls | `call_log`, `call_log_participant_v2`, `joinable_call_log`, `missed_call_logs`, `bcall_session`, `call_link`, `scheduled_calls` |
| Newsletters | `newsletter`, `newsletter_message`, `newsletter_message_reaction`, `newsletter_admin_profile`, `newsletter_subscribers`, `newsletter_pinned_message`, `newsletter_interaction` |
| Polls / events / labels | `message_poll`, `message_poll_option`, `poll_vote_*`, `event*`, `labels`, `labeled_jid`, `favorite`, `quick_replies*` |
| Payments / commerce | `pay_transaction`, `payment_*`, `message_payment*`, `message_order`, `message_product`, `cart_item` |
| Integrity / reporting | `integrity_analysis_result`, `integrity_chat_info`, `integrity_input_feature`, `integrity_deleted_chat_*`, `message_quarantine`, `message_structure_analysis_result`, `reporting_info(_content)`, `scam_alert_events` |
| AI / TEE | `ai_thread_info`, `ai_rich_response_message_*`, `bot_*`, `agent_*`, `auth_agent_chat_metadata`, `tee_chat_request_table`, `tee_message_info_table`, `private_ai_*`, `embeddings_deletion_log` |

### 3.2 Identity: jid, LID mapping

| Table | Columns (declared order) | Notes |
|-------|--------------------------|-------|
| `jid` | `_id` (PK AUTOINCREMENT), `user`, `server`, `agent`, `device`, `type`, `raw_string` | unique index `jid_key_new_index` on (`user`,`server`,`agent`,`device`,`type`), unique `jid_raw_string_index` on `raw_string`. `JidStore` (`C0W4`) writes `jid.getType()` / `getRawString()`. Every other table refers to a JID by `*_jid_row_id` = `jid._id` |
| `jid_map` | `lid_row_id`, `jid_row_id`, `sort_id` | LID row to phone-number JID row (LID migration surface; trigger on `lid_row_id`) |
| `lid_chat_state` | `jid_row_id`, `is_pn_shared`, `pn_requested_ts`, `pnh_duplicate_lid_thread` (+ default-only columns) | state of phone-number sharing per LID chat |
| `lid_display_name` | `lid_row_id`, `display_name`, `username` | the username shown for a LID contact, see [WA_USERNAME.md](WA_USERNAME.md) |

### 3.3 chat

`chat` (`C0OM`), 57 declared columns. Unique index `chat_account_jid_row_id_unique_index` on `account_jid_row_id`.

| Group | Columns |
|-------|---------|
| Key | `_id`, `jid_row_id`, `account_jid_row_id` (owning account; new with multi-account / LID), `chat_origin` |
| Display | `subject`, `created_timestamp`, `hidden`, `archived`, `sort_timestamp`, `group_type`, `group_member_count`, `is_contact`, `chat_lock` |
| Pointers into `message` | `display_message_row_id`, `last_message_row_id`, `last_read_message_row_id`, `last_read_receipt_sent_message_row_id`, `last_important_message_row_id`, `change_number_notified_message_row_id`, plus `*_sort_id` variants and `last_message_reaction_row_id`, `last_seen_message_reaction_row_id` |
| Unread counters | `unseen_message_count`, `unseen_important_message_count`, `unseen_missed_calls_count`, `unseen_row_count`, `unseen_message_reaction_count`, `unseen_comment_message_count`, `unseen_earliest_message_received_time` |
| Ephemeral | `ephemeral_expiration`, `ephemeral_setting_timestamp`, `ephemeral_displayed_exemptions`, `ephemeral_disappearing_messages_initiator`, `ephemeral_after_read_duration` |
| Crypto / policy | `plaintext_disabled`, `chat_encryption_state`, `limited_sharing`, `limited_sharing_setting_timestamp`, `growth_lock_level`, `growth_lock_expiration_ts`, `spam_detection`, `business_chat_state`, `participation_status`, `history_sync_progress`, `chat_props` |

### 3.4 message and satellites

`message` (`C09540Re`), 24 columns; unique index `message_key_index` on (`chat_row_id`,`from_me`,`key_id`,`sender_jid_row_id`).

| Column | Use |
|--------|-----|
| `_id` | row id, referenced as `message_row_id` everywhere |
| `chat_row_id`, `sender_jid_row_id` | chat, sender (`jid._id`) |
| `from_me`, `key_id` | message key part (stanza id) |
| `status`, `broadcast`, `recipient_count`, `participant_hash` | delivery state and group fan-out summary |
| `origination_flags`, `origin`, `view_mode`, `sort_id` | origin and ordering |
| `timestamp`, `received_timestamp`, `receipt_server_timestamp`, `server_sts` | times |
| `message_type`, `text_data`, `translated_text` | type and plain text body (text lives in the row itself) |
| `starred`, `view_replies_thread_id` | flags |
| `lookup_tables`, `message_add_on_flags` | bitmasks that tell which satellite tables hold rows (inferred from names and use) |

| Satellite | Key columns |
|-----------|-------------|
| `message_text` | `message_row_id`, `description`, `page_title`, `url`, `font_style`, `text_color`, `background_color`, `preview_type`, `invite_link_group_type`, `counter_abuse_token`, `link_end_index` |
| `message_quoted` | `message_row_id`, `chat_row_id`, `parent_message_chat_row_id`, `from_me`, `sender_jid_row_id`, `key_id`, `timestamp`, `message_type`, `text_data`, `quoted_source`, `quoted_type` |
| `message_edit_info` | `message_row_id`, `original_key_id`, `edited_timestamp`, `sender_timestamp` |
| `message_revoked` | `message_row_id`, `revoked_key_id`, `admin_jid_row_id`, `revoke_timestamp` |
| `message_ephemeral` | `message_row_id`, `duration`, `expire_timestamp`, `keep_in_chat`, `ephemeral_trigger`, `ephemeral_initiated_by_me`, `after_read_duration` |
| `message_secret` | `message_row_id` (+ the secret column, elided by the decompiler): per-message secret for add-on encryption (inferred) |
| `message_future` | `message_row_id`, `version`, `data`, `future_message_type`, `future_proof_stanza`, `edit_version`, `message_stanza_data` (unsupported message kept for later) |
| `message_orphan` | `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_*`, `orphan_message_data`, `orphan_message_type`, `orphan_message_reason` (child that arrived before its parent) |
| `message_quarantine` | `message_row_id`, `chat_row_id`, `timestamp`, `original_protobuf`, `serialized_stanza`, `protobuf_type` |
| `reporting_info` | `message_row_id`, `reporting_tag`, `stanza_id`, `send_timestamp`, `receive_timestamp`, `stanza_id_text`, `receive_flow`, `is_message_add_on` (see [WA_REPORTING.md](WA_REPORTING.md)) |
| `message_send_count` | `message_row_id`, `send_count` |

### 3.5 Receipts, reactions, add-ons

| Table | Columns | Notes |
|-------|---------|-------|
| `receipt_user` | `_id`, `message_row_id`, `receipt_user_jid_row_id`, `receipt_timestamp`, `read_timestamp`, `played_timestamp` | per recipient (1:1 and group) |
| `receipt_device` | `_id`, `message_row_id`, `receipt_device_jid_row_id`, `receipt_device_timestamp`, `primary_device_version` | per recipient device |
| `receipt_orphaned` | `_id`, `chat_row_id`, `from_me`, `key_id`, `receipt_device_jid_row_id`, `receipt_recipient_jid_row_id`, `status`, `timestamp` | receipt before its message |
| `message_add_on` | `_id`, `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_message_row_id`, `timestamp`, `status`, `message_add_on_type`, `received_timestamp`, `expiry_duration_in_secs`, `server_timestamp`, `expiry_timestamp`, `expiry_type` | one row per reaction / vote / pin / keep; unique key is (`chat_row_id`,`key_id`,`from_me`) in the lookup query |
| `message_add_on_reaction` | `message_add_on_row_id` (PK), `reaction`, `sender_timestamp` | partial index `message_add_on_reaction_empty_reaction_index` on `reaction = ''` (empty string = removed reaction, inferred) |
| `message_poll` | `message_row_id`, `enc_key`, `selectable_options_count`, `invalid_state`, `poll_logging_id`, `poll_type`, `correct_option_id`, `content_type`, `hide_participant_names`, `end_time`, `allow_add_option` | |

`C09010Pb.A00` is the add-on column set; `AbstractC41651mo.A01` selects the column set by add-on type id: 56 = reaction (`C0PV`), 67 = poll vote (`C0PT`), others 68, 74, 79, 86, 93, 121, 122, 125 (found: the switch; their meaning was not traced).

### 3.6 Groups and participants

| Table | Columns |
|-------|---------|
| `group_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `add_timestamp`, `label`, `join_method`, `group_history_send_state` |
| `group_past_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `is_leave`, `timestamp` |
| `group_participant_device` | `_id`, `group_participant_row_id`, `device_jid_row_id`, `sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket` (per-device sender-key distribution state) |
| `group_root_key_mapping` | `_id`, `group_jid_row_id`, `key_id`, `is_current` |
| `feature_key_store` | `_id`, `key_id`, `key_jid`, `key`, `key_type`, `creation_timestamp`, `expiry_timestamp` |

Group-level settings (admin-only, announcement, ephemeral, membership approval, history toggles) are in **wa.db** `wa_group_admin_settings`, not here (4.3). Group history: [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md).

### 3.7 Devices

| Table | Columns |
|-------|---------|
| `user_device` | `_id`, `user_jid_row_id`, `device_jid_row_id`, `key_index` |
| `user_device_info` | `user_jid_row_id`, `raw_id`, `timestamp`, `expected_timestamp`, `expected_ts_last_device_job_ts`, `expected_timestamp_update_ts`, `account_encryption_type` (ADV state per user) |

### 3.8 Media, thumbnails, sidecar

| Table | Columns | Note |
|-------|---------|------|
| `message_media` | `message_row_id`, `chat_row_id`, `file_path`, `file_size`, `file_length`, `mime_type`, `media_name`, `media_key`, `media_key_timestamp`, `e2ee_media_key`, `file_hash`, `enc_file_hash`, `partial_media_hash`, `partial_media_enc_hash`, `original_file_hash`, `direct_path`, `message_url`, `metadata_url`, `media_duration`, `width`, `height`, `transferred`, `transcoded`, `is_offloaded`, `media_job_uuid`, `media_upload_handle`, `has_streaming_sidecar`, `media_caption`, `media_source_type`, `suspicious_content` | 55 declared columns; `file_path` is stored relative to the media root (`C0KE.A0A` strips the root prefix, found). Upload / download fields: [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| `message_thumbnail` | `message_row_id`, `thumbnail` | thumbnail bytes inside the DB |
| `message_streaming_sidecar` | `message_row_id`, `sidecar`, `chunk_lengths`, `timestamp` | streaming sidecar (chunk MAC data for progressive playback) in the DB, not as a file |
| `media_hash_thumbnail` | `media_hash`, `thumbnail` | thumbnail keyed by content hash |
| `media_refs` | `_id`, `path`, `ref_count` | reference count per file path |
| `mms_thumbnail_metadata` | `message_row_id`, `direct_path`, `media_key`, `media_key_timestamp`, `enc_thumb_hash`, `thumb_hash`, `thumb_width`, `thumb_height`, `transferred`, `micro_thumbnail`, `insert_timestamp`, `handle` | |
| `extended_media_data` | `row_id`, `type`, `external_url`, `direct_path`, `preview_path`, `file_path`, `file_hash`, `media_key`, `enc_file_hash`, `mime_type`, `display_type` | |
| `offloaded_media` (offloaded-media.db) | `file_path`, `content_hash`, `file_size`, `media_source`, `media_state`, `is_offloadable`, `latest_reference_timestamp`, `refetch_timestamp`, `file_key` | |

### 3.9 Calls

| Table | Columns |
|-------|---------|
| `call_log` | `_id`, `jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch` |
| `call_log_participant_v2` | `_id`, `call_log_row_id`, `jid_row_id`, `call_result` |

Call signaling: [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md). Newsletter tables (`newsletter`, `newsletter_message`, 45 and 17 columns) are listed in 3.1 only.

### 3.10 Views and integrity / AI tables

Views created in `C06980Hc.A0C` (found): `available_message_view`, `deleted_messages_view`, `deleted_messages_ids_view`, `chat_view` (two variants, chosen by `isGlobalChatDbMigrated`).

| Table | Columns |
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

## 4. wa.db: contacts, blocklists, trust data

### 4.1 Families (found, 88 classes)

| Family | Tables |
|--------|--------|
| Contacts | `wa_contacts`, `wa_contact_details`, `wa_contacts_created_within_wa`, `wa_contacts_pending_operations`, `wa_contact_refresh_pending`, `wa_contact_refresh_patch_log`, `wa_contact_storage_usage`, `wa_address_book`, `wa_org_contacts`, `wa_orgs`, `system_contacts_version_table` |
| Blocklists / allowlists | `wa_block_list`, `wa_block_list_interop`, `wa_last_seen_block_list`, `wa_profile_photo_block_list`, `wa_about_block_list`, `wa_pix_block_list`, `wa_cover_photo_block_list`, `wa_status_view_allow_list`, `wa_status_view_black_list`, `wa_group_add_allow_list`, `wa_group_add_black_list`, `wa_stickers_allow_list`, `wa_profile_links_deny_list` |
| Business | `wa_biz_profiles` + 12 `wa_biz_profiles_*` / `wa_biz_*` detail tables, `wa_vnames`, `wa_vnames_localized` |
| Groups | `wa_group_admin_settings`, `wa_group_descriptions`, `group_membership_approval_requests`, `non_admin_group_membership_approval_requests`, `group_membership_count`, `group_membership_form_questions`, `group_relationship`, `subgroup_info`, `community_settings`, `member_suggested_groups_v2`, `group_suspension_appeal`, `group_non_wa_invites` |
| Trust / integrity | `wa_trusted_contacts`, `wa_trusted_contacts_send`, `wa_biz_integrity_signals`, `wa_biz_integrity_chat_settings`, `start_chat_trust_signals`, `wa_contact_server_signals` |
| Config | `wa_props`, `wa_newsletter_props`, `wa_coex_properties`, `wa_ml_models`, `wa_last_entry_point`, `wa_logging_entry_point` |
| AI / bots | `meta_ai_memory`, `wa_bot_profiles`, `wa_bot_commands`, `wa_subscriptions` |
| Other | `status_ranking(_global)`, `wa_chat_ranking_scores`, `wa_storage_monitoring_data/_jobs`, `inbound_/outbound_connection_requests`, `dismissed_*`, `quick_promotion_payload` |

### 4.2 wa_contacts

36 columns (`Nn5`), keyed by `jid` (TEXT, raw JID string; a phone JID or a `@lid` JID, not a `jid` row id):

`jid`, `is_whatsapp_user`, `status`, `status_timestamp`, `number`, `raw_contact_id`, `display_name`, `phone_type`, `phone_label`, `photo_ts`, `thumb_ts`, `photo_id_timestamp`, `given_name`, `family_name`, `wa_name`, `sort_name`, `nickname`, `company`, `title`, `status_autodownload_disabled`, `keep_timestamp`, `is_spam_reported`, `is_sidelist_synced`, `is_business_synced`, `disappearing_mode_duration`, `disappearing_mode_timestamp`, `disappearing_mode_support_disabled`, `history_sync_initial_phash`, `is_starred`, `is_wa_created_contact`, `sync_policy`, `status_emoji`, `is_contact_synced`, `is_reachable`, `external_user_state`, `fts_dirty_version`.

`wa_name` is the push name the contact set; `display_name` / `given_name` come from the address book. Several satellite tables use `BEFORE DELETE ON wa_contacts` triggers (e.g. `start_chat_trust_signals_contact_delete`, `contact_bd_for_business_integrity_signals`).

### 4.3 Other wa.db tables

| Table | Columns |
|-------|---------|
| `wa_trusted_contacts` | (+ `jid`), `incoming_tc_token` BLOB, `incoming_tc_token_timestamp` LONG. See [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_trusted_contacts_send` | (+ `jid`), `sent_tc_token_timestamp` LONG, `real_issue_timestamp` LONG |
| `wa_biz_integrity_signals` | 17 columns: `_id`, `jid`, `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `is_suspicious`, `join_date_ms`, `is_banned`, `phone_country_code`, `trust_tier`, `is_meta_verified`, `mv_friction_eligibility`, `integrity_tags`, `chat_row_id`, `last_sync_ts`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Full semantics in the ban report 5.1 |
| `start_chat_trust_signals` | (+ `jid`), `is_sender_suspicious`, `is_sender_new_account`, `created_ts` REAL |
| `meta_ai_memory` | `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER; index `meta_ai_memory_memory_content_index` on `memory_content` |
| `wa_contact_server_signals` | `chat_jid`, `signal_type`, `value`, `update_ts` |
| `wa_group_admin_settings` | `jid`, `restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `creator_jid`, `is_suspended`, `group_state`, `require_membership_approval`, `member_add_mode`, `addressing_mode`, `history_enabled`, `group_history_toggle_mode`, `share_group_history_setting_mode`, `earliest_group_history_message_timestamp_ms`, `allow_member_labels`, ... (31 columns) |
| `wa_storage_monitoring_data` | `db_name`, `table_name`, `table_size_bytes`, `index_size_bytes`, `table_unused_bytes`, `index_unused_bytes` (the client measures its own table sizes; see 10.3) |

---

## 5. axolotl.db (Signal state)

Current DDL (latest variants in `C44861sL`, tables registered by `AbstractC11250Yd`; found). Key material is stored as BLOB `record` columns; no key bytes are documented here.

| Table | Columns | Role |
|-------|---------|------|
| `identities` | `_id`, `recipient_id`, `recipient_type`, `device_id`, `registration_id`, `public_key`, `private_key`, `next_prekey_id`, `next_kyber_prekey_id`, `timestamp`, `account_encryption_attestation_type`, `mark_as_verified`, `mark_as_verified_action_seq`, ... | own identity row and remote identities (`recipient_type` separates phone and LID accounts) |
| `sessions` | `_id`, `device_id`, `record`, `timestamp`, `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope` | Double Ratchet sessions |
| `prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `key_type` | one-time prekeys |
| `signed_prekeys` | `_id`, `prekey_id` UNIQUE, `timestamp`, `record`, `key_type` | |
| `kyber_prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `last_resort_key` | post-quantum prekeys |
| `prekey_uploads` | `_id`, `upload_timestamp`, `key_type` | |
| `sender_keys` | `_id`, `group_id`, `device_id`, `record`, `timestamp`, `sender_account_id`, `sender_account_type`, `bucket_id` | group sender keys |
| `message_base_key` | `_id`, `msg_key_remote_jid`, `msg_key_from_me`, `msg_key_id`, `recipient_id`, `recipient_type`, `device_id`, `last_alice_base_key`, `timestamp` | |
| `chat_stanza_queue`, `e2ee_stanza_queue`, `unordered_stanza_queue`, `preacks`, `stanza_sts` | `stanza_id`, `stanza_key` UNIQUE, `stanza_class`, `chat_jid`, `sender_jid`, `stanza_payload`, ... | incoming stanza persistence before decrypt |

The Java layer of the Signal store is `signal_protocol_store`-style code over these tables. Account-level crypto prefs live in `keystore.xml` and `wacrypto.xml` (8.3), not here.

---

## 6. sync.db, companion_devices.db and the smaller databases

| DB | Tables and key columns |
|----|------------------------|
| `sync.db` | `syncd_mutations` (`mutation_index` UNIQUE, `mutation_value` BLOB, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name`), `pending_mutations` (same plus `operation`, `is_ready_to_sync`), `collection_versions` (`collection_name` PK, `version`, `lt_hash` BLOB, `dirty_version`), `crypto_info` (`device_id`, `epoch`, `key_data`, `timestamp`, `fingerprint`, `stale_timestamp`), `missing_keys`, `msg_history_sync`, `history_sync_companion`, `peer_messages`, `placeholder_retry_message`, `rmr_response_error`. Protocol: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md) |
| `companion_devices.db` | `devices`: `device_id`, `device_os`, `platform_type`, `last_active`, `login_time`, `logout_time`, `adv_key_index`, `full_sync_required`, `place_name`, `nickname`, ... Protocol: [WA_LINKED_DEVICE_PAIRING.md](WA_LINKED_DEVICE_PAIRING.md) |
| `status.db` | `status`, `status_text`, `status_thumbnail`, `status_info`, `status_interactions`, `status_interactions_totals`, `status_seen_receipt`, `status_receipt_device`, `status_reply`, `status_send_part`, `status_privacy_custom_list`, `status_crossposting_v2/_v3`, ... plus `key_value_store` (`row_id`, `key`, `value`) |
| `backup.db` | `backups`, `backup_props` (`prop_name`, `prop_value`; row `wa_db_schema_version`) |
| `chatsettings.db` | `settings`: `_id`, `jid`, `deleted`, `mute_end`, `muted_notifications`, `use_custom_notifications`, `message_tone`, `call_tone`, `status_muted`, `pinned`, `pinned_time`, `media_visibility`, `mute_reactions`, `wallpaper_*`, `auto_delete_media`, `transcription_locale`, `source_lang`, `target_lang`, `snooze_end_time`, `theme_id` (39 columns) |
| `stickers.db` | `stickers` (`plain_file_hash`, `encrypted_file_hash`, `media_key`, `mime_type`, `sticker_pack_id`, `file_path`, `url`, `direct_path`, `emojis`, `is_lottie`, ...), `recent_stickers`, `starred_stickers`, `installed_sticker_packs`; `payments.db`: `methods` (`credential_id` PK, `country`, `issuer_name`, `type`, `balance_1000`), `contacts`, `receipts`, `tmp_transactions` |

---

## 7. Backups and crypt15

### 7.1 Local backup files

| Name pattern (found, `AbstractC26994Bml`, `C29412Cpb`) | Content |
|--------------------------------------------------------|---------|
| `msgstore.db.crypt15`, `msgstore.db.crypt14` | full chat database backup (regex `msgstore.db.crypt(\d+)`) |
| `msgstore-increment-<N>.db.crypt<V>` | incremental backup |
| `backup_settings.json.crypt<V>`, `status_backup.db.crypt<V>`, `commerce_backup.db.crypt<V>`, `chat_transfer_settings.json.crypt<V>` | settings, status, commerce, chat-transfer settings |
| `stickers.db.crypt<V>`, `chatsettingsbackup.db`, `wa-backup.db` | sticker / chat-settings / wa.db backups (component names below) |

Root is `Backups/` under the external media root (`C0KE.A02`; legacy `Databases/`, `C0KE.A03`). The root is chosen by pref `external_storage_type` (value `scoped` is checked in `C11160Xu.A07`; other values not enumerated); `EnumC046905z` can resolve to `getExternalMediaDirs()[0]`, `getExternalStorageDirectory()`, app-specific external dirs or the internal dirs. Secondary accounts use `<root>/accounts/<dirId>` for `Media/WhatsApp ...` paths (`C0KE.A00`).

Backup components (`A0F` names in `CMN` subclasses, found): `stickers`, `stickers-db`, `wallpapers`, `payment-backgrounds-v2`, `chat-transfer`, `wa-db`, `commerce-db`, `status_db`, `offloaded-media.db`, `chatlock_backup`, `chat-settings`, `backup-settings`. `backup_prefs` keeps `<component>_backup_size` / `_backup_status` per component (8.3).

Media categories in the backup UI (`EnumC26330BbW`, 17 values): `CHAT_DB`, `SETTINGS`, `STATUS_DB`, `COMMERCE_DB`, `OTHER_DB`, `IMAGES`, `VIDEOS`, `AUDIO`, `VOICE_NOTES`, `VIDEO_NOTES`, `GIFS`, `DOCUMENTS`, `STICKERS`, `STICKER_PACKS`, `PROFILE_PHOTOS`, `EXCLUDED_STICKERS`, `OTHER`.

### 7.2 crypt15 file prefix (found)

`EnumC26325BbR`: `UNENCRYPTED` 0, `CRYPT14` 14, `CRYPT15` 15 (a `.crypt` suffix without a number is the old form; `CKv` matches `.crypt`). The crypt15 reader (`BN4.A09`) parses a delimited protobuf `BackupPrefix` (`BCE`) before the ciphertext:

| Field | Number | Type | Use |
|-------|--------|------|-----|
| `key_type_deprecated` | **1** | enum | old key type |
| `wa_provided_key_data` | **2** | bytes | key data for server-provided keys |
| `e2ee_key_data` | **3** | message | key data for end-to-end encrypted backup |
| `backup_metadata` | **4** | `BD0` | see below |
| `passkey_encryption_metadata` | **5** | message | passkey path (`parsePasskeyEncryptionMetadata`) |
| `key_type_new` | **6** | enum | current key type |

Key types (`BdX`): `WA_PROVIDED` 0, `E2EE_DEPRECATED` 1, `E2EE_PASSWORD` 2, `E2EE_ENCRYPTION_KEY` 3, `E2EE_PASSKEY` 4.

`BackupMetadata` (`BD0`) fields (selection): `app_version` **1**, `device_model` **2**, `jid_suffix` **3**, `backup_version` **4**, `backup_export_file_size` **38**, `cleaned_db` **39**, `backup_encrypted_hash_salt` **40**, `backup_encrypted_hash` **41**, `identifier_type` **42**, `lid_suffix` **43**, `display_suffix` **44**, plus about 30 `*_migration_finished` booleans (numbers 5 to 35). On restore, `EncBackupUtils` compares `jid_suffix` with the registered user (`has-jid-user-mismatch`): a backup is bound to the account that made it.

The cipher, KDF and MAC layout of the ciphertext was not read here (unknown).

### 7.3 Backup key material

| File (in `files/`) | Content | Evidence |
|--------------------|---------|----------|
| `encrypted_backup.key` | 32-byte root key of the end-to-end encrypted backup (`C29861Ep.A09`, length checked == 32); written by `A04(...)`, possibly wrapped by a KeyStore encapsulation key (`failed to load or create KeyStore encapsulation key`) | found |
| `encrypted_backup.key_id` | key identifier | found |
| `password_data.key`, `passkey_data.key` | state for the password and passkey variants (passkey data is JSON) | found |
| `vault_backup.key` | 32-byte vault key, generated with `C00L.A0H(32)` and refuses to overwrite an unreadable file (`vault backup key present but could not be read`) | found |
| `prf_derived_root_key.key`, `secret_code.key` | passkey PRF-derived root key, secret-code key | name found, content unknown |
| `backup_token`, `foa_backup_token` | token file (`CMc`, `foa_` variant for the accounts-center account) | found |

`AbstractC29801Ej` deletes `encrypted_backup.key(_id)`, `password_data.key`, `passkey_data.key`, `vault_backup.key` together (key reset).

### 7.4 Android auto-backup and the migration provider (found)

| Item | Value |
|------|-------|
| `android:allowBackup` | `true`, `fullBackupOnly=true`, backup agent `SystemBackupAgent` |
| `fullBackupContent` (`xml0003`) and `dataExtractionRules` (`xml0006`: cloud-backup and device-transfer) | exclude **every** domain (`root`, `file`, `database`, `sharedpref`, `external`, `device_*`). Nothing is transferred by the platform |
| `cross-platform-transfer platform="ios"` | declared with the iOS bundle id; the transfer goes through `OsMigrationAppDataService` (permission `android.permission.BACKUP`) |
| `MigrationContentProvider` | exported, `readPermission com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` (protectionLevel `signature`), `grantUriPermissions=false`. URIs: `msg_store`, `unencrypted_msg_store`, `wa_db`, `chat_setting_store`, `sticker_store`, `wallpaper`, `share_preferences`, `media`, `chat_lock_passcode`. `DirectMigrationContentProvider` uses the same permission. Purpose (hand-over to the sibling app of the same signer) is inferred |

---

## 8. SharedPreferences

### 8.1 Factory

`C00S` (SharedPreferencesFactory, `A04(C00G, name)`): returns a custom implementation over `<dataDir>/shared_prefs/<name>.xml` (`C052308r` file wrapper; classes `C052408s` / `RRP`), falling back to the system `getSharedPreferences(name, 0)` if the directory cannot be created. Whether the on-disk bytes are standard Android XML was not verified in code (file extension only).

| Fact | Evidence |
|------|----------|
| Name sets with special handling in `AbstractC051008e` (`A02`, `A03`: feature flags of the implementation; `A00`, `A01`, `A04`: scoped sets) | found; flag semantics of `C00G(boolean,boolean,boolean)` unknown |
| `A05` set (`multi_account_metadata`, `group_history_usage`, `hatch_group_agent`, `hatch_group_agent_debug`, `smb_token_lockout_cooldown`) must not be created by this factory: message `Pref not allowed to instantiate using SharedPreferencesFactory, use MultiAccountSharedPreferencesFactory` | found |
| Main file names derive from `AbstractC051108f`: `com.whatsapp_preferences` and `com.whatsapp_preferences_light` | found |
| `SharedPreferencesUsageRepository` (`C052508t`) records load times per prefs file (`load`, `load2`), skipping `ab-props`, `ab-props-back-up`, `ab-prechatd-props`, `ab-props-backup`, `dropped_wam_events`, `keystore` | found: telemetry about the prefs themselves |
| `C09E` (deprecated "Me" and prefs god-class) wraps `com.whatsapp_preferences_light` (`C1WL` case 23); many small wrappers (`C1DH`, `C56902Wq`, `C0G1`) are views of that one file | found |
| Default `com.whatsapp_preferences` is the plain Android file; `chatCounts` is a separate file (`RP5`) | found |

### 8.2 Files by area (names found in code)

| Area | Files |
|------|-------|
| Core | `com.whatsapp_preferences`, `com.whatsapp_preferences_light`, `startup_prefs`, `reg_prefs`, `register_phone_prefs`, `registration.verifyphone.VerifyPhoneNumber`, `registration.app.phonenumberentry.RegisterPhone`, `registration.app.verifyphone.VerifyPhoneNumber`, `multi_account_metadata`, `account_linking_prefs`, `fb_credentials_prefs`, `fb_linked_account`, `accounts_center_registration_prefs` |
| Flags | `ab-props`, `ab-props-backup`, `ab-props-back-up`, `ab-prechatd-props`, `groupAbProps`, `network_resources_pref` |
| Crypto | `keystore`, `wacrypto`, `security_prefs`, `nc_prefs`, `chat_lock`, `migration_export`, `AccountDefenceLocalDataRepository_prefs` |
| Backup / sync | `backup_prefs`, `chat_transfer_prefs`, `syncd_prefs`, `contact_sync_prefs`, `device_capabilities`, `companion_mode_prefs` |
| Features | `username_prefs`, `meta_ai_prefs`, `bonsai_prefs`, `paa_prefs`, `status_prefs`, `newsletter_prefs`, `voip_prefs`, `route_selector_prefs`, `interop_ui`, `interop_badge_prefs`, `avatar_prefs`, `bloks`, `privacy_disclosure_store`, `user_notice_prefs`, `tos_gating_prefs` |
| Telemetry | `critical_event_client_prefs`, `anr_shared_prefs`, `time_spent_prefs`, `dropped_wam_events`, `wam_prefs`, `chatCounts` |
| Third-party SDK | `com.google.android.gms.appid`, `com.google.firebase.messaging`, `WebViewChromiumPrefs` (system) |

### 8.3 Important keys (all key names found in 2.26.41.6; values not reproduced)

| File | Key | Type / use |
|------|-----|-----------|
| `startup_prefs` | `registration_state` | int; `C06810Gk` predicates: 0/1 initial, 3, 4, 5, 8 (flash verify), 12, 15, 17 (email OTP), 20, 23 |
| | `startup_migrated_version` | int; target **20**, `WaStartupSharedPreferences` runs migrations below it |
| | `push_name` | own display name |
| | `force_db_check`, `force_wadb_check` | force integrity check of msgstore / wa.db (cleared by `C0HS.BoJ`, `C12650bW.onCreate`) |
| | `pending_repair_db_name`, `pending_repair_db_file_id`, `pending_repair_corruption_type`, `pending_repair_attempt_count`, `pending_repair_request_id`, `pending_repair_timestamp`, `pending_repair_gate_suppressed` | database repair queue |
| | `privacy_fingerprint_enabled`, `night_mode`, `client_server_time_diff` (read by `C050708b`) | |
| `com.whatsapp_preferences_light` | `registration_jid`, `registration_lid`, `cc`, `ph`, `self_lid`, `registration_initialized_time`, `registration_success_time_ms`, `registration_wipe_info_timestamp`, `reg_attempts_verify_code` | identity of this install (cleared by `RegistrationManager.A0I`) |
| | `adv_raw_id`, `adv_current_key_index`, `adv_timestamp_sec`, `phoneid_id`, `phoneid_timestamp` | ADV / phone id state |
| | `privacy_last_seen`, `privacy_profile_photo`, `privacy_status`, `privacy_online`, `read_receipts_enabled`, `privacy_token_batch_offset_sec` | privacy settings (`C18260lS`, `C09E.A0S()`) |
| | `md_messaging_enabled`, `last_login_time`, `last_daily_cron`, `next_randomized_daily_cron`, `nct_salt` | multi-device flag, cron bookkeeping, tctoken salt ([WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md)) |
| `backup_prefs` | `gdrive_state`, `backup_provider`, `backup_encryption_method`, `encrypted_backup_fleet_migration_state`, `encrypted_backup_num_attempts_remaining`, `google_restore_result`, `msg_restore_timestamp`, `last_seen_app_version`, `device_backup_integration_enabled`, `blocking_restore_in_progress`, `cloud_api_type`, `restore_second_verification_needed` | backup and restore state (`C22090sX`) |
| `keystore` | `server_static_public`, `server_static_pq_public`, `client_static_keypair_pwd_enc`, `client_static_keypair_enc_success`, `can_user_android_key_store`, `remaining_auth_key_rotation_attempts` | Noise static keys ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md), [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md)) |
| `wacrypto` | `signed_prekey_id_seed_migration_completed` | Signal prekey id seed migration |
| `ohai_key_config` (pref name in `C53596Nzj`) | `public_key` and key-config fields | OHAI gateway key |
| `syncd_prefs` | `syncd_dirty`, `syncd_bootstrap_state`, `syncd_bootstrapped_mutations` (set), `mutation_counter` | app-state sync bootstrap |
| `companion_mode_prefs` | `previously_logged_out_from_primary` | companion state |
| `username_prefs` | `username_reservation_state`, `username_pin` | see [WA_USERNAME.md](WA_USERNAME.md) |
| `route_selector_prefs` | `media_conn` | cached media route (host list and auth data; [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md)) |
| `ab-props` | numeric string keys (config codes), `ab_props:sys:last_refresh_time`, `ab_props:sys:config_hash`, `ab_props:sys:last_version`; `com.whatsapp_preferences` holds `ab_props:hash_v2` | AB prop cache; `ab-props-backup` is the previous copy |
| `chatCounts` | per-chat counters, `thread_user_secret` (32 random bytes, base64) | `WamThreadIdManager` HMACs thread ids with it; `RP5.A0w` keeps it across a reset |

---

## 9. Files, caches and media layout

### 9.1 Internal `files/` (found unless marked)

| Path | Content |
|------|---------|
| `me` | Java-serialized `Me` record (`C9V.A01`, fields include `cc`, `number`); `me.jpg` / `me_old.jpg` profile photo |
| `rc2` | AES/OFB-encrypted 160-bit random value generated on first use for two string inputs (`K49.A0v`, `C00L.A0G`; inferred: country code and number); purpose inferred (registration secret). Deleted by the wipe runnables `RunnableC29329CoG`, `RunnableC46625KYz` |
| `backup_token`, `foa_backup_token`, `encrypted_backup.key*`, `vault_backup.key` | section 7.3 |
| `invalid_numbers`, `login_failed`, `customTSValues`, `emoji` | small state files (`IJU`, `C06850Go`) |
| `statistics.json`, `network_statistics.json` | rx / tx counters (`C17B`, `C17J`; keys `statistics`, `bytes`, `timestamp`, `rx_data`, `tx_data`) |
| `Logs/` | log files (10.1) |
| `decompressed/libs.spo/` (+ `.superpack_version`) | libraries unpacked at runtime by `C0EE`; **excluded from every wipe** |
| `mobileconfig/` | `mc_overrides.json`, `id_name_mapping.json` (`C053409d`) and the config store |
| `falco/`, `wam/` | telemetry engines (10) |
| `Stickers/`, `Drafts/`, `GroupHistory/`, `Payment Backgrounds/`, `Wallpapers/`, `.trash/`, `biz_directory/`, `privacy_disclosure/<version>/`, `downloadable/`, `NetworkResource/`, `MNSResolverCache/`, `app_state/` | feature caches (`C0I1`, `C58398QKk`, `C27574Bxe`, `MNSStreamRuntime`, `C06110Cn`) |

Other private dirs named by the storage-config switch (`AbstractC13030c9`): `lib-compressed`, `app_secure_shared`, `app_sigquit`, `modules`, `app_optsvc_analytics`, `app_overtheair`, `app_qpl`, `app_light_prefs`, `cache/secure_shared`, `files/secure_shared`, `app_minidumps`, `app_fb-forker-tmp`.

### 9.2 `cache/` (found)

| Dir | Note |
|-----|------|
| `thumb_decoded_cache` | disk LRU, **52428800 bytes (50 MiB)** (`C33000EZy`) |
| `webp_static_cache`, `stickers_cache`, `avatar-temporary`, `interop_image_cache`, `tigon_http_client`, `ML_MODEL`, `hatch_space_images`, `meta_ai_thread_photo_uploads` | image / network / model caches |
| `Profile Pictures/` | account-scoped (`C28025CFb.A01` returns the cache dir; `QLH` builds `Profile Pictures`) |

### 9.3 Secondary accounts (found)

`getDir("account_switching")` (= `app_account_switching/`) holds `active_account` (the active dir id, `C00W`) and the account list (`C25160AsA`). A secondary account's data lives in `<dataDir>/accounts/<dirId>/{databases,files,cache}` (`C28025CFb`) and its media under `<root>/accounts/<dirId>`; the default account uses the normal directories. `account_switcher.db` and the multi-account prefs are shared.

### 9.4 External media root (found)

`<root>/Media/WhatsApp <Category>/` with categories `Images`, `Video`, `Audio`, `Documents`, `Voice Notes`, `Video Notes`, `Animated Gifs`, `Stickers`, `Sticker Packs`, `Profile Photos`, `Backup Excluded Stickers` (`AbstractC26994Bml`), sub-folders `Sent`, `Private`, `.Thumbs` (`*.prog.thumb.jpg`, `C0I1.A08`), `.Shared`, `.nomedia` markers. `message_media.file_path` stores the part after the root.

---

## 10. Logs and telemetry kept on device

### 10.1 Logs (found)

| File | Detail |
|------|--------|
| `files/Logs/whatsapp.log`, `whatsapp.tmp` | text log, header `==== logfile version=2.26.41.6 level=4 ====`; rotation compresses to `.gz` with a date (`Log.rotate`, `AbstractC28128CKx.A00`). `C24971Ap6` gathers `Logs` with the db directory for support / bug-report export |
| `app_minidumps/`, `<dir>/minidumps`, `crash_upload/` | native crash dumps and the upload staging (`C0FQ`, `JJ1`, `CKN`, `ExceptionsUploadService`) |
| `anr_report_<n>.dmp`, `anr_shared_prefs` | ANR reports (`C45432Jrw`) |
| `cache/qpl`, `app_qpl` | QuickPerformanceLogger traces |

### 10.2 Telemetry engines

| Path | Engine | Evidence |
|------|--------|----------|
| `files/wam/` | WAM runtime directory passed to `WAJContextInitWAMRuntime` (JNI) | `RunnableC29323CoA`; `dropped_wam_events` and `wam_prefs` prefs |
| `files/falco/` | event logger in `libffsingletonmerged.so` | native strings below |
| `files/mobileconfig/` | Mobile Config store | `C053409d` |

Falco SQLite file `FFLogger.sql` (location inferred: Java creates `files/falco/`, the file name is a string in the native lib): tables present in the native schema strings (found): `event`, `buffer_event`, `upload` (`request_data`, `num_events`, `is_compressed`, `compression_method`), `claim` (`principal_subject_hash`, `claim`, `expires_at`), `collection_constraint`, `event_config` (`event_config_hash` UNIQUE, `event_name`, `sampling_rate`, `collection_constraint_ref`, `is_deidentified`), `checksum`, `amendment_outbox`, index `event_0` on `event(requested_latency)`; `batch` joins by `identities_hash`. `fflogger_health_counters.bin` holds self-instrumentation counters (`mobile_health_counters`). The Java side only creates the directory.

### 10.3 Self-measurement

wa.db `wa_storage_monitoring_data` / `_jobs` (per-table sizes and unused bytes by `db_name`) and the prefs-load statistics (8.1) are telemetry the client keeps about its own storage. The WAM event pipeline itself is out of scope here.

---

## 11. What is wiped, and when

### 11.1 Operations

| Operation | Entry (2.26.41.6) | Effect |
|-----------|-------------------|--------|
| Delete account / local data reset | `C25007Aph.A0L` then `A02` (`removeDatabasesAndResetState`) | full local wipe, 11.2 |
| Companion removed | `C25007Aph.A0M` (`deleteCompanionCleanup`) | `ActivityManager.clearApplicationUserData()` (fallback `pm clear <package>`, fallback to `A02`) |
| Re-register | `RegistrationManager.A06` (`reregister reason=`) | clears registration prefs and `me`, 11.3 |
| Unregister from device | `RegistrationManager.A0F` | stops the connection with `should_unregister=true`, deletes `me`, clears state |
| Logout (primary, with multi-account) | `LogoutManager` (`AccountLogoutMutation`, w:mex) | server logout, account marked logged out; data stays until the user removes the logged-out account (11.4). Whether the first step deletes anything locally was not traced (unknown) |
| Remove logged-out account | `LogoutManager.removeLoggedOutAccountWithCleanup` | removes the account entry, then `deleteDefaultAccountDirectories` or `deleteSecondaryAccountDirectories`, then GMS backup state |

### 11.2 Account deletion (`C25007Aph.A02`, found)

| Target | Action |
|--------|--------|
| In-memory stores, feature managers | cleared; `last_contact_full_sync` = -1 |
| Databases | each helper's delete (`A0D`, `A0N`): msgstore via `C0HC` (`msgstore-manager/deletedb/result`), wa.db (`deleteaccountconfirm/wa-db-delete-incomplete` is an error if files remain), commerce, `emojidictionary`, language-pack store, `MediaJobDataStore`, history-sync stores, business directory (`files/biz_directory`) |
| `files/` | all entries except `decompressed`; `Logs` is kept when the flag `z` is set (companion path) |
| External root | `Backups/` removed and recreated empty, `Databases/` files removed (`AbstractC28132CLd.A04`), only if external storage state is usable |
| `com.whatsapp_preferences` | `clear()` then `version` is rewritten with `2.26.41.6` |
| `backup_prefs` | `clear()` but `last_seen_app_version` and `device_backup_integration_enabled` are restored |
| `chatCounts` | all keys removed except `thread_user_secret` (`RP5.A0A`) |
| Other prefs | `avatar_prefs`, the registration and VerifyPhone files, companion registration (`registration_device_id`, `companion_registration_state` = 0), a few feature prefs |
| WebView | cookies and web storage deleted, also for named profiles when multi-profile is available |

### 11.3 Reregister / unregister (found)

`RegistrationManager.A0I` removes `registration_jid`, `registration_lid`, `cc`, `ph` and the `registration_wipe_info_timestamp`; `A0A` clears the two registration screens' prefs; the `me` file is removed (`rm-me`).

### 11.4 Logged-out chats dialog (`FilesDeletionUtility`)

Deletes the external root of the logged-out user, `cacheDir`, every entry of `filesDir` except `decompressed`, the secondary-account files dir, then calls the DB helpers' delete; a failed wa.db deletion throws and the dialog reports an error (`FilesDeletionUtility/deleteInternalFiles/wa-db-delete-incomplete`).

### 11.5 Multi-account file deletion (`AccountSwitchingFileManager.deleteDefaultAccountDirectories`)

For the default account: `shared_prefs` is deleted except an allow-list; `databases` is deleted except `account_switcher.db` (and its suffix variants); other dirs are removed whole.

---

## 12. Baileys notes (inferred mapping)

Baileys keeps credentials and a keyed store (`creds`, pre-key, session, sender-key, app-state-sync-key / -version, lid-mapping, device-list, tctoken). The conceptual counterparts on Android (inferred; no code ties them):

| Baileys state | Android storage |
|---------------|-----------------|
| `session`, `pre-key`, signed pre-key | `axolotl.db` `sessions`, `prekeys`, `signed_prekeys` (+ `kyber_prekeys` on Android) |
| `sender-key`, `sender-key-memory` | `axolotl.db` `sender_keys`; per-device distribution in msgstore `group_participant_device` |
| app-state sync key / version | `sync.db` `crypto_info` (`key_data`, `epoch`), `collection_versions` (`lt_hash`) |
| lid mapping | msgstore `jid_map` (+ `lid_display_name`) |
| device list | msgstore `user_device`, `user_device_info` |
| `tctoken` | wa.db `wa_trusted_contacts(_send)` |
| `creds.me`, registration id, ADV | `files/me`, prefs `adv_*`, `identities` row |

A Baileys session has no equivalent of the `message` table; deleting its auth state is the counterpart of the wipe in 11 and requires a new link.

---

## 13. Error cases and gotchas

| Symptom | Cause | Fix / note |
|---------|-------|-----------|
| `msgstore/upgrade version 1 to N` never appears | msgstore `user_version` is always 1 | read `props.msgtore_db_schema_version` for the real schema state |
| msgstore "restored-db-not-indexed" / `RestoredIndexesPending` | DB restored from backup; indexes created lazily | `props` keys `MessagesDBHelper_*`; run completes asynchronously |
| `still-corrupt-after-repair`, `delete-superseded-by-new-repair` | integrity check failed (`C0HC.checkhealth`) | queue in `startup_prefs` `pending_repair_*`; `force_db_check` |
| wa.db suddenly empty after update | upgrade switch dropped tables (versions 3 to 94) or schema hash changed | wa.db is rebuildable from server and address book |
| `deleteaccountconfirm/completion-blocked/wa-db-files-remain` | wa.db files could not be deleted | retry; the wipe aborts with `Be5` |
| Restore refuses a backup (`has-jid-user-mismatch`) | `BackupMetadata.jid_suffix` differs from the account | restore with the same number |
| `backup-file-crypt15/prefix null` | file empty or not crypt15 | check the delimited prefix (7.2) |
| `vault backup key present but could not be read` | `vault_backup.key` unreadable | the code refuses to mint a replacement to avoid overwriting a recoverable file |
| `Pref not allowed to instantiate using SharedPreferencesFactory` | multi-account-only pref created with the wrong factory | use `MultiAccountSharedPreferencesFactory` |
| Data of a logged-out account remains | logout does not delete account data (11.1) | remove the account explicitly |

---

## 14. Key distinctions

| Do not confuse | Difference |
|----------------|-----------|
| `msgstore.db` vs `wa.db` | messages, chats and `jid` rows vs contacts, blocklists, trusted-contact tokens, business and integrity caches; JID row ids exist only in msgstore, wa.db keys are raw JID strings |
| `jid._id` vs raw JID | `*_jid_row_id` columns are msgstore row ids; `wa_*` tables use `jid` TEXT |
| SQLite `user_version` vs schema version | msgstore always 1; wa.db 95; the schema is a hash in `props` (msgstore) or a tag (wa.db) |
| Android auto-backup vs chat backup | auto-backup excludes everything; chat backup is the app's own `crypt15` file in the external root |
| crypt15 file vs key files | ciphertext in `Backups/`; keys in `files/*.key` (never in the same folder) |
| `com.whatsapp_preferences` vs `_light` | plain Android prefs (wiped to a version key) vs the custom-implementation file used by `C09E` (identity, privacy, flags) |
| `ab-props` vs `wa_props` | AB experiment codes (prefs) vs server account props (wa.db table) |
| Logout vs account deletion | logout marks the account; deletion wipes DBs, files, Backups, prefs (11) |
| Falco vs WAM | Falco is the SQLite event logger in a native lib; `wam/` is the WAM runtime directory; both are telemetry |
| Files from third-party mods | extra databases, stanza logs or hook diagnostics are not created by the stock app and are not covered |
---

## 15. Layout and lifecycle

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

## 16. Not covered and unknown

| Topic | Status |
|-------|--------|
| Per-table DB attribution for the 306 + 422 table classes beyond the checked ones | set sizes found; mapping of each class to its database by the DI graph not traced (inferred by FKs and names) |
| Column types, defaults and NOT NULL for tables built with helper functions | decompiler elides some; only names are listed |
| Remaining ~250 msgstore tables, remaining wa.db and status.db tables | names listed in families; columns not extracted |
| crypt15 ciphertext format, KDF, MAC; contents of `BackupPrefix` sub-messages | unknown |
| Standard-XML on-disk format of the custom prefs implementation | not verified |
| Complete key list of each prefs file (hundreds of keys) | only the files and keys named in 8.3 |
| Meaning of `C00G` flags, add-on type ids, `registration_state` values | partly named |
| Versions of `sync.db`, `chatsettings.db`, `stickers.db`, `commerce.db`, `daily_metrics.db`, `location.db` | not resolved |
| Purpose of `files/rc2`, `files/key` | `rc2` inferred; `key` not resolved |
| Whether primary logout alone deletes local data | not traced |
| Runtime behaviour, file sizes, WAL contents | static analysis only |
