<!-- src-sha1: 6effa8dc57f2e12a66c37c7cae9d875028a5d55e -->
# WhatsApp Lokaler Speicher — Full RE Report
**Version:** 2.26.41.6 | **Datum:** 2026-10-23
**Umfang:** SQLite-Datenbanken (Namen, Speicherort, Engine, Versionierung, Tabellen-Framework), Schlüsseltabellen und -spalten von msgstore.db und wa.db, axolotl.db, sync.db und die kleineren Datenbanken, crypt15-Backups und Backup-Schlüsseldateien, Android-Auto-Backup-Regeln und der Migrations-Content-Provider, SharedPreferences-Factory und Schlüsselinventar, Datei- und Cache-Layout, Log- und Telemetriedateien, was Logout / Unregister / Reregister / Kontolöschung entfernen

---

## 1. Was wo gespeichert ist

Alle Aussagen beruhen auf statischer Analyse der dekompilierten APK und ihrer mitgelieferten nativen Bibliotheken. Es wurden keine Gerätedaten gelesen. Stufe: **found** = im Code, Manifest oder in nativen Strings gelesen; **inferred** = aus dem Code abgeleitet; **unknown** = nicht aufgelöst. Obfuskierte Namen entsprechen der JADX-Ausgabe für 2.26.41.6 und ändern sich mit jedem Build.

### 1.1 Speicherübersicht

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

| Speicherort | Inhalt | Überlebt Android-Auto-Backup |
|-------------|--------|------------------------------|
| `databases/` | alle SQLite-Dateien | nein: jede Domain ist ausgeschlossen (8.1) |
| `shared_prefs/` | Einstellungen, Flags, Schlüssel | nein |
| `files/`, `cache/` | Schlüsseldateien, Caches, Logs | nein |
| externes Root `Backups/` | verschlüsseltes Chat-Backup (crypt15) | n/a: eigener Backup-Mechanismus (7) |

### 1.2 Engine-Fakten (found)

| Fakt | Beleg |
|------|-------|
| SQLite ist der mitgelieferte Build `io.requery.android.database.sqlite`, nicht der des Frameworks | Package in `java_src` |
| Kein SQLCipher: kein `PRAGMA key`, kein `sqlcipher`-String irgendwo in `java_src` | grep; Datenbankdateien liegen innerhalb der App-Sandbox im Klartext vor |
| WAL ist für alle auf `AbstractC11350Yn` aufbauenden Helper aktiviert (`setWriteAheadLoggingEnabled(true)`) | `AbstractC11350Yn`; Checkpoint über `PRAGMA wal_checkpoint(FULL)` |
| msgstore öffnet mit `PRAGMA synchronous=NORMAL`, optionalem `cache_size` (Flag **20777**), `PRAGMA secure_delete=1` | `C06980Hc.onOpen`; ein fehlgeschlagenes Aktivieren von secure_delete wird als `db-integrity/enable-secure-delete/error/not-enabled` gemeldet |
| `PRAGMA foreign_keys=ON` ist für sync.db, paa.db, daily_metrics.db gesetzt, nicht für msgstore.db | `AbstractC12530bK`, `AbstractC197088a3`, `AbstractC16650iN`; msgstore kaskadiert über Trigger (2.3) |

---

## 2. SQLite-Datenbanken

### 2.1 Inventar

Dateinamen sind Literale (`getDatabasePath(...)` / Helper-Konstruktoren). Tabellenanzahlen entsprechen der Anzahl der Tabellendefinitions-Klassen im DI-Modul, das den Helper speist (2.3).

| Datei | Helper / Modul (2.26.41.6) | Version / Migration | Tabellenklassen | Rolle | Tier |
|-------|----------------------------|---------------------|-----------------|-------|------|
| `msgstore.db` | `C06980Hc` (Factory `C0HH`) | SQLite-`user_version` fest auf 1; Schema-Fingerprint in `props` (2.4) | 306 (Factory `C1S0`) | Nachrichten, Chats, JIDs, Receipts, Anrufe, Newsletter, Integrity, AI, TEE | found / Zuordnung der Menge inferred |
| `wa.db` | `C12650bW` | **95** (`creating contacts database version 95`) | 88 (`C8ZL`-Implementierer) | Kontakte, Blocklisten, Business-Profile, Trusted-Contact-Tokens, Integrity-Signale | found |
| `axolotl.db` | `C44861sL`, Tabellen `AbstractC11250Yd` | **40** | 15 | Signal-Sessions, Prekeys, Sender Keys, Stanza-Queues | found |
| `sync.db` | `AbstractC12530bK` (Helper `X.1sK`) | schrittweise `ALTER`-Migrationen bis mindestens v50; Downgrade = Reset | 10 | App-State-Sync, History-Sync, Peer-Nachrichten | found, Version unknown |
| `status.db` | `C41891nD` | **2** (`StatusDbHelper creating status database version 2`) | 29 (`AbstractC11620Zo`) | Status-Posts und Interaktionen | found |
| `backup.db` | `C44881sN` | **1** | `backups`, `backup_props` | Backup-Buchführung; `backup_props` enthält `wa_db_schema_version` | found |
| `chatsettings.db` | `C11200Xy("chatsettings.db")` | unknown | `settings` (inferred) | Stummschaltung, Pin, Ton, Hintergrund, Theme pro Chat | Name found, Tabelle inferred |
| `stickers.db` | Modul `AbstractC149676Ty` | unknown | 18 (Modul registriert außerdem `offloaded_media*`, `backups`, `backup_props`) | Sticker-Packs | found |
| `offloaded-media.db` | `CMN` (Backup-Komponente) | unknown | `offloaded_media`, `offloaded_media_staging` (Zuordnung inferred) | Index ausgelagerter Medien | found / inferred |
| `payments.db` | `C1S0`-anonymer Helper, `AbstractC22520tH` | **5** | `contacts`, `methods`, `receipts`, `tmp_transactions` | Zahlungsmethoden | found |
| `commerce.db` | `C27743C3e` | unknown | unknown | Commerce-Daten; hat eine Backup-Variante `commerce_backup.db` | Name found |
| `companion_devices.db` | `C48701zE` | **27** | `devices` (+ weitere) | verknüpfte Geräte aus Sicht des Primärgeräts | found |
| `paa.db` | `ManagedAccountDbHelper` (`AbstractC197088a3`) | Migrationen V1 bis V7 | `paa_connection`, `contact_metadata`, `group_metadata` | Daten verwalteter Konten (Parent-approved Account) | found |
| `daily_metrics.db` | `AbstractC16650iN` | unknown | `poll_event_logging`, `poll_daily_participant`, `comments_event_logging`, `pnh_daily_event_logging`, `community_home_action_logging`, `snapl_payload` | tägliche Ereigniszähler | found |
| `qp_payload.db`, `location.db`, `fa_events.db`, `media.db`, `account_switcher.db` | Pfad-Getter (`C23985AVo`, `C33961Wh`) | unknown | unknown | Quick Promotions, Live-Standort, Federated Analytics, Media-Jobs (inferred), Kontoliste | Name found |
| `sqlite_vec.db` | `MessageEmbeddingsStore` | unknown | Vektortabellen (unknown) | On-Device-Nachrichten-Embeddings; nur vorhanden, wenn aktiviert | found |
| `emojidictionary.db`, `hsmpacks.db`, `events.db` | `C8JP`, `C6UR` | unknown | unknown | Emoji-Wörterbuch, Template-Packs, Events | Name found |
| `wa-backup.db`, `msgstore.db-backup` | `CMN` / `C26042BNa`, `C0KE` | n/a | n/a | lokale Sicherheitskopien von wa.db / msgstore | found |
| `migration_prefetcher.db`, `migration_import_metadata.db`, `migration_export_metadata.db` | `C23985AVo` | unknown | unknown | Zustand von Chat-Transfer / OS-Migration; `migration_prefetcher.db` wird von `C28152CMi` gelöscht | Name found |
| `androidx.work.workdb` | WorkManager (`no_backup/`) | Room | Standard | Job-Queue | inferred aus Room-Klassen (`room_master_table`) |

### 2.2 Welche DB hält die in anderen Reports zitierten Tabellen

| Tabelle | DB-Datei | Tabellenklasse | Beleg | Report |
|---------|----------|----------------|-------|--------|
| `wa_trusted_contacts`, `wa_trusted_contacts_send` | `wa.db` | `C23627AHs`, `C23628AHt` (`C8ZL`) | wa.db-Helper legt sie neu an; Stores werden über `C12810bn` des wa.db-Helpers gelesen | [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_biz_integrity_signals` | `wa.db` | `C53116Nmn` (`C8ZL`) | found | [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 5.1 |
| `start_chat_trust_signals` | `wa.db` | `AI0` (`C8ZL`), Trigger auf `wa_contacts` | found | Ban-Report 5.2 |
| `integrity_chat_info` | `msgstore.db` | `C08970Ox`, Trigger `chat_bd_for_integrity_chat_info_trigger` auf `chat` | found, Zuordnung über den FK auf `chat` | Ban-Report 5.3 |
| `meta_ai_memory` | **`wa.db`** | `C23621AHm` (`C8ZL`) | found; Spalten `memory_id`, `memory_content`, `bot_jid_row_id` | [WA_META_AI.md](WA_META_AI.md) |
| `bot_memory_metadata`, `bot_chat_info`, `ai_thread_info` | `msgstore.db` | `C08640Nq`, `C08610Nn`, `C0MO` | in der Menge der 306 Klassen | Meta-AI-Report |

`meta_ai_memory` liegt in `wa.db`, nicht in `msgstore.db`: Die Klasse implementiert `C8ZL`, das nur der wa.db-Helper iteriert (`C12650bW.onCreate` mit `new C08050Lj("wa.db")`). `bot_jid_row_id` verweist auf eine `jid`-Zeile von msgstore, die Spalte ist also eine datenbankübergreifende weiche Referenz (inferred; über Dateigrenzen hinweg ist kein Foreign Key möglich).

### 2.3 Tabellen-Framework (wie Schemas definiert werden)

Tabellen sind nicht als SQL-Strings geschrieben. Jede Tabelle ist eine Klasse, die `InterfaceC08060Lk` implementiert (wa.db: das Sub-Interface `C8ZL`) mit drei Hooks (found):

| Hook | Zweck |
|------|-------|
| `ASa(ctx, builder)` | Spalten deklarieren: `C08080Lm`-Builder, `.A02` = Name, `.A00` = `EnumC08100Lo`-Typ (`INTEGER`, `TEXT`, `REAL`, `BLOB`, `LONG`, ...), Flags für Primary Key / not null / Default |
| `ASX(ctx, builder)` | Indizes deklarieren (`CRN`, `CRJ` = bedingter Index) |
| `ASc(builder)` | Trigger deklarieren (`CRg`, `CRf`) |

- 422 Klassen implementieren `InterfaceC08060Lk`, weitere 88 implementieren `C8ZL`. Sie werden in DI-Sets bereitgestellt; jeder Helper iteriert sein Set (`C06980Hc.A03`, `C12650bW.onCreate`, `C44881sN`, `C41891nD`).
- Kaskadierende Löschungen sind Trigger, keine Foreign Keys: `AbstractC08210Lz.A01` baut `CREATE TRIGGER <parent>_bd_for_<child>_trigger BEFORE DELETE ON <parent> BEGIN DELETE FROM <child> WHERE ...; END` (found; Beispiel: `message_add_on_reaction` wird gelöscht, wenn `message_add_on`-Zeilen verschwinden).
- Die Spaltenlisten unten stammen aus `ASa` in deklarierter Reihenfolge. Der Decompiler lässt einige vom Helper gebaute Spalten aus (erste Spalte einiger Tabellen, Defaultwerte); diese sind mit "(+ jid)" markiert, wo eine Query oder ein Trigger die Spalte belegt. Typen sind nur angegeben, wo der Code sie nennt.
- Die DB-Zuordnung der 306 msgstore-Klassen erfolgt über die DI-Factory `C1S0` (306 `new`-Aufrufe, enthält `message`, `chat`, `jid`) und über die FK-Trigger auf `chat` / `message` / `jid` (inferred). Tabellen mit gleichem Namen in zwei Modulen existieren (`status`, `status_attribution`, `mms_thumbnail_metadata`, `quick_promotion_payload`: msgstore und status.db bzw. wa.db haben jeweils eine Klasse).

### 2.4 Versionierung und Migrationen

| DB | Strategie (found) |
|----|-------------------|
| `msgstore.db` | `onUpgrade` = `onCreate`; `setVersion(1)` immer. Die echte Version ist ein Hash in der Tabelle `props`: `msgtore_db_schema_version` und `msgtore_db_schema_indexes_version` = `Arrays.hashCode` über ein literales `Consumer-<hex>`-Tag und `MessageSchemaConfig=1;isGlobalChatDbMigrated=<bool>[;includeNewsletterInteractionTable=true]` (`C06980Hc.A04`). Deklarativ: Tabellen und Indizes sind `CREATE ... IF NOT EXISTS` aus dem Klassenset. Weitere `props`-Keys: `MessagesDBHelper_RestoredIndexesPending`, `MessagesDBHelper_CreateAsyncIndexesV2`, `..FailedAttempts` |
| `wa.db` | `onUpgrade` ist ein Switch über alte Versionen 3 bis 94, der meist Tabellen verwirft, die später neu angelegt werden; unbekannte alte Version fällt auf `onCreate`; Downgrade = `onCreate`. `wa_db_schema_version` wird mit einem `ConsumerBeta-<hex>`-Tag geschrieben. Pref `force_wadb_check` (startup_prefs) erzwingt eine erneute Prüfung. wa.db enthält wiederherstellbare Daten (Kontakte, Tokens, Caches) |
| `axolotl.db` | versioniert (40); alte DDL-Varianten in `C44861sL` sichtbar (z. B. `identities` erhielt `recipient_type`, `next_kyber_prekey_id`, `account_encryption_attestation_type`; `sessions` erhielt `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope`; `sender_keys` erhielt `bucket_id`) |
| `sync.db` | schrittweise `ALTER TABLE ... ADD` (z. B. `collection_versions.dirty_version`, `history_sync_companion.inline_payload`, `msg_history_sync.size_limit_bytes`); Downgrade oder unbekannte Version ruft `sync-db-helper/reset` auf, das die Tabellen neu anlegt, sodass der App-State neu synchronisiert wird (inferred) |
| `status.db` | v2; `key_value_store`-Zeile `schema_version` |
| `paa.db` | `runMigrationV1`..`V7` (fügt Spalten wie `age_experience`, `snooze_status`, `common_groups_count` hinzu) |
| Backups (`BD0`) | die crypt15-Metadaten tragen weiterhin Flags "Migration abgeschlossen" pro Tabelle (`message_main`, `receipt_user`, `jid_store`, ...), die Historie der alten msgstore-Migrationen (7.2) |

---

## 3. msgstore.db: Schlüsseltabellen und -spalten

### 3.1 Tabellenfamilien (found, 306 Klassen)

| Familie | Tabellen (Beispiele) |
|---------|----------------------|
| Identität | `jid`, `jid_map`, `lid_chat_state`, `lid_display_name`, `jid_user_metadata`, `integrator_display_name` |
| Chat | `chat`, `chat_ephemeral`, `chat_encryption_classification`, `community_chat`, `broadcast_chat_details`, `thread_messages`, `thread_id`, `draft_message_reminder` |
| Nachrichtenkern | `message`, `message_text`, `message_media`, `message_quoted*` (14), `message_edit_info`, `message_revoked`, `message_forwarded`, `message_mentions`, `message_link`, `message_future`, `message_orphan`, `message_send_count`, `message_view_once_media`, `message_ephemeral*` |
| Systemnachrichten | `message_system` + etwa 35 `message_system_*`-Detailtabellen (group, number_change, lid_change, username_change, device_change, privacy, ...) |
| Add-ons | `message_add_on` und `message_add_on_reaction`, `_poll_vote`, `_poll_vote_selected_option`, `_keep_in_chat`, `_pin_in_chat`, `_question_response`, `_event_response`, `_receipt_device`, `_receipt_coex`, `_status_*` |
| Receipts | `receipt_user`, `receipt_device`, `receipt_coex`, `receipt_orphaned`, `played_self_receipt`, `optimised_delivery_info` |
| Gruppen | `group_participant_user`, `group_past_participant_user`, `group_participant_device`, `parent_group_participants`, `group_history_*`, `group_root_key_mapping`, `group_notification_version` |
| Geräte | `user_device`, `user_device_info`, `primary_device_version`, `agent_devices` |
| Medien | `media_hash_thumbnail`, `media_content`, `mms_metadata`, `mms_thumbnail_metadata`, `extended_media_data`, `message_media_map`, `message_streaming_sidecar`, `media_refs`, `message_thumbnail`, `audio_data`, `voice_data` |
| Anrufe | `call_log`, `call_log_participant_v2`, `joinable_call_log`, `missed_call_logs`, `bcall_session`, `call_link`, `scheduled_calls` |
| Newsletter | `newsletter`, `newsletter_message`, `newsletter_message_reaction`, `newsletter_admin_profile`, `newsletter_subscribers`, `newsletter_pinned_message`, `newsletter_interaction` |
| Polls / Events / Labels | `message_poll`, `message_poll_option`, `poll_vote_*`, `event*`, `labels`, `labeled_jid`, `favorite`, `quick_replies*` |
| Zahlungen / Commerce | `pay_transaction`, `payment_*`, `message_payment*`, `message_order`, `message_product`, `cart_item` |
| Integrity / Reporting | `integrity_analysis_result`, `integrity_chat_info`, `integrity_input_feature`, `integrity_deleted_chat_*`, `message_quarantine`, `message_structure_analysis_result`, `reporting_info(_content)`, `scam_alert_events` |
| AI / TEE | `ai_thread_info`, `ai_rich_response_message_*`, `bot_*`, `agent_*`, `auth_agent_chat_metadata`, `tee_chat_request_table`, `tee_message_info_table`, `private_ai_*`, `embeddings_deletion_log` |

### 3.2 Identität: jid, LID-Mapping

| Tabelle | Spalten (deklarierte Reihenfolge) | Hinweise |
|---------|-----------------------------------|----------|
| `jid` | `_id` (PK AUTOINCREMENT), `user`, `server`, `agent`, `device`, `type`, `raw_string` | eindeutiger Index `jid_key_new_index` auf (`user`,`server`,`agent`,`device`,`type`), eindeutiger `jid_raw_string_index` auf `raw_string`. `JidStore` (`C0W4`) schreibt `jid.getType()` / `getRawString()`. Jede andere Tabelle verweist über `*_jid_row_id` = `jid._id` auf eine JID |
| `jid_map` | `lid_row_id`, `jid_row_id`, `sort_id` | LID-Zeile auf Telefonnummern-JID-Zeile (LID-Migrationsfläche; Trigger auf `lid_row_id`) |
| `lid_chat_state` | `jid_row_id`, `is_pn_shared`, `pn_requested_ts`, `pnh_duplicate_lid_thread` (+ Spalten nur mit Default) | Zustand der Telefonnummern-Freigabe pro LID-Chat |
| `lid_display_name` | `lid_row_id`, `display_name`, `username` | der für einen LID-Kontakt angezeigte Username, siehe [WA_USERNAME.md](WA_USERNAME.md) |

### 3.3 chat

`chat` (`C0OM`), 57 deklarierte Spalten. Eindeutiger Index `chat_account_jid_row_id_unique_index` auf `account_jid_row_id`.

| Gruppe | Spalten |
|--------|---------|
| Schlüssel | `_id`, `jid_row_id`, `account_jid_row_id` (besitzendes Konto; neu mit Multi-Account / LID), `chat_origin` |
| Anzeige | `subject`, `created_timestamp`, `hidden`, `archived`, `sort_timestamp`, `group_type`, `group_member_count`, `is_contact`, `chat_lock` |
| Zeiger in `message` | `display_message_row_id`, `last_message_row_id`, `last_read_message_row_id`, `last_read_receipt_sent_message_row_id`, `last_important_message_row_id`, `change_number_notified_message_row_id`, dazu `*_sort_id`-Varianten sowie `last_message_reaction_row_id`, `last_seen_message_reaction_row_id` |
| Ungelesen-Zähler | `unseen_message_count`, `unseen_important_message_count`, `unseen_missed_calls_count`, `unseen_row_count`, `unseen_message_reaction_count`, `unseen_comment_message_count`, `unseen_earliest_message_received_time` |
| Ephemeral | `ephemeral_expiration`, `ephemeral_setting_timestamp`, `ephemeral_displayed_exemptions`, `ephemeral_disappearing_messages_initiator`, `ephemeral_after_read_duration` |
| Krypto / Policy | `plaintext_disabled`, `chat_encryption_state`, `limited_sharing`, `limited_sharing_setting_timestamp`, `growth_lock_level`, `growth_lock_expiration_ts`, `spam_detection`, `business_chat_state`, `participation_status`, `history_sync_progress`, `chat_props` |

### 3.4 message und Satelliten

`message` (`C09540Re`), 24 Spalten; eindeutiger Index `message_key_index` auf (`chat_row_id`,`from_me`,`key_id`,`sender_jid_row_id`).

| Spalte | Verwendung |
|--------|------------|
| `_id` | Zeilen-ID, überall als `message_row_id` referenziert |
| `chat_row_id`, `sender_jid_row_id` | Chat, Absender (`jid._id`) |
| `from_me`, `key_id` | Teil des Message Key (Stanza-ID) |
| `status`, `broadcast`, `recipient_count`, `participant_hash` | Zustellstatus und Zusammenfassung des Gruppen-Fan-outs |
| `origination_flags`, `origin`, `view_mode`, `sort_id` | Herkunft und Sortierung |
| `timestamp`, `received_timestamp`, `receipt_server_timestamp`, `server_sts` | Zeiten |
| `message_type`, `text_data`, `translated_text` | Typ und Klartext-Body (Text liegt in der Zeile selbst) |
| `starred`, `view_replies_thread_id` | Flags |
| `lookup_tables`, `message_add_on_flags` | Bitmasken, die angeben, welche Satellitentabellen Zeilen halten (inferred aus Namen und Verwendung) |

| Satellit | Schlüsselspalten |
|----------|------------------|
| `message_text` | `message_row_id`, `description`, `page_title`, `url`, `font_style`, `text_color`, `background_color`, `preview_type`, `invite_link_group_type`, `counter_abuse_token`, `link_end_index` |
| `message_quoted` | `message_row_id`, `chat_row_id`, `parent_message_chat_row_id`, `from_me`, `sender_jid_row_id`, `key_id`, `timestamp`, `message_type`, `text_data`, `quoted_source`, `quoted_type` |
| `message_edit_info` | `message_row_id`, `original_key_id`, `edited_timestamp`, `sender_timestamp` |
| `message_revoked` | `message_row_id`, `revoked_key_id`, `admin_jid_row_id`, `revoke_timestamp` |
| `message_ephemeral` | `message_row_id`, `duration`, `expire_timestamp`, `keep_in_chat`, `ephemeral_trigger`, `ephemeral_initiated_by_me`, `after_read_duration` |
| `message_secret` | `message_row_id` (+ die Secret-Spalte, vom Decompiler ausgelassen): Secret pro Nachricht für die Add-on-Verschlüsselung (inferred) |
| `message_future` | `message_row_id`, `version`, `data`, `future_message_type`, `future_proof_stanza`, `edit_version`, `message_stanza_data` (nicht unterstützte Nachricht, für später aufbewahrt) |
| `message_orphan` | `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_*`, `orphan_message_data`, `orphan_message_type`, `orphan_message_reason` (Kind, das vor seinem Parent eintraf) |
| `message_quarantine` | `message_row_id`, `chat_row_id`, `timestamp`, `original_protobuf`, `serialized_stanza`, `protobuf_type` |
| `reporting_info` | `message_row_id`, `reporting_tag`, `stanza_id`, `send_timestamp`, `receive_timestamp`, `stanza_id_text`, `receive_flow`, `is_message_add_on` (siehe [WA_REPORTING.md](WA_REPORTING.md)) |
| `message_send_count` | `message_row_id`, `send_count` |

### 3.5 Receipts, Reactions, Add-ons

| Tabelle | Spalten | Hinweise |
|---------|---------|----------|
| `receipt_user` | `_id`, `message_row_id`, `receipt_user_jid_row_id`, `receipt_timestamp`, `read_timestamp`, `played_timestamp` | pro Empfänger (1:1 und Gruppe) |
| `receipt_device` | `_id`, `message_row_id`, `receipt_device_jid_row_id`, `receipt_device_timestamp`, `primary_device_version` | pro Empfängergerät |
| `receipt_orphaned` | `_id`, `chat_row_id`, `from_me`, `key_id`, `receipt_device_jid_row_id`, `receipt_recipient_jid_row_id`, `status`, `timestamp` | Receipt vor seiner Nachricht |
| `message_add_on` | `_id`, `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_message_row_id`, `timestamp`, `status`, `message_add_on_type`, `received_timestamp`, `expiry_duration_in_secs`, `server_timestamp`, `expiry_timestamp`, `expiry_type` | eine Zeile pro Reaction / Vote / Pin / Keep; der eindeutige Schlüssel ist (`chat_row_id`,`key_id`,`from_me`) in der Lookup-Query |
| `message_add_on_reaction` | `message_add_on_row_id` (PK), `reaction`, `sender_timestamp` | partieller Index `message_add_on_reaction_empty_reaction_index` auf `reaction = ''` (leerer String = entfernte Reaction, inferred) |
| `message_poll` | `message_row_id`, `enc_key`, `selectable_options_count`, `invalid_state`, `poll_logging_id`, `poll_type`, `correct_option_id`, `content_type`, `hide_participant_names`, `end_time`, `allow_add_option` | |

`C09010Pb.A00` ist die Add-on-Spaltenmenge; `AbstractC41651mo.A01` wählt die Spaltenmenge nach Add-on-Typ-ID: 56 = Reaction (`C0PV`), 67 = Poll-Vote (`C0PT`), weitere 68, 74, 79, 86, 93, 121, 122, 125 (found: der Switch; ihre Bedeutung wurde nicht nachverfolgt).

### 3.6 Gruppen und Teilnehmer

| Tabelle | Spalten |
|---------|---------|
| `group_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `add_timestamp`, `label`, `join_method`, `group_history_send_state` |
| `group_past_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `is_leave`, `timestamp` |
| `group_participant_device` | `_id`, `group_participant_row_id`, `device_jid_row_id`, `sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket` (Zustand der Sender-Key-Verteilung pro Gerät) |
| `group_root_key_mapping` | `_id`, `group_jid_row_id`, `key_id`, `is_current` |
| `feature_key_store` | `_id`, `key_id`, `key_jid`, `key`, `key_type`, `creation_timestamp`, `expiry_timestamp` |

Einstellungen auf Gruppenebene (nur Admins, Announcement, Ephemeral, Mitgliedschaftsfreigabe, History-Schalter) liegen in **wa.db** `wa_group_admin_settings`, nicht hier (4.3). Gruppen-History: [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md).

### 3.7 Geräte

| Tabelle | Spalten |
|---------|---------|
| `user_device` | `_id`, `user_jid_row_id`, `device_jid_row_id`, `key_index` |
| `user_device_info` | `user_jid_row_id`, `raw_id`, `timestamp`, `expected_timestamp`, `expected_ts_last_device_job_ts`, `expected_timestamp_update_ts`, `account_encryption_type` (ADV-Zustand pro Nutzer) |

### 3.8 Medien, Thumbnails, Sidecar

| Tabelle | Spalten | Hinweis |
|---------|---------|---------|
| `message_media` | `message_row_id`, `chat_row_id`, `file_path`, `file_size`, `file_length`, `mime_type`, `media_name`, `media_key`, `media_key_timestamp`, `e2ee_media_key`, `file_hash`, `enc_file_hash`, `partial_media_hash`, `partial_media_enc_hash`, `original_file_hash`, `direct_path`, `message_url`, `metadata_url`, `media_duration`, `width`, `height`, `transferred`, `transcoded`, `is_offloaded`, `media_job_uuid`, `media_upload_handle`, `has_streaming_sidecar`, `media_caption`, `media_source_type`, `suspicious_content` | 55 deklarierte Spalten; `file_path` wird relativ zum Media-Root gespeichert (`C0KE.A0A` entfernt das Root-Präfix, found). Upload- / Download-Felder: [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| `message_thumbnail` | `message_row_id`, `thumbnail` | Thumbnail-Bytes in der DB |
| `message_streaming_sidecar` | `message_row_id`, `sidecar`, `chunk_lengths`, `timestamp` | Streaming-Sidecar (Chunk-MAC-Daten für progressive Wiedergabe) in der DB, nicht als Datei |
| `media_hash_thumbnail` | `media_hash`, `thumbnail` | Thumbnail, per Content-Hash adressiert |
| `media_refs` | `_id`, `path`, `ref_count` | Referenzzähler pro Dateipfad |
| `mms_thumbnail_metadata` | `message_row_id`, `direct_path`, `media_key`, `media_key_timestamp`, `enc_thumb_hash`, `thumb_hash`, `thumb_width`, `thumb_height`, `transferred`, `micro_thumbnail`, `insert_timestamp`, `handle` | |
| `extended_media_data` | `row_id`, `type`, `external_url`, `direct_path`, `preview_path`, `file_path`, `file_hash`, `media_key`, `enc_file_hash`, `mime_type`, `display_type` | |
| `offloaded_media` (offloaded-media.db) | `file_path`, `content_hash`, `file_size`, `media_source`, `media_state`, `is_offloadable`, `latest_reference_timestamp`, `refetch_timestamp`, `file_key` | |

### 3.9 Anrufe

| Tabelle | Spalten |
|---------|---------|
| `call_log` | `_id`, `jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch` |
| `call_log_participant_v2` | `_id`, `call_log_row_id`, `jid_row_id`, `call_result` |

Call-Signaling: [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md). Newsletter-Tabellen (`newsletter`, `newsletter_message`, 45 und 17 Spalten) sind nur in 3.1 aufgeführt.

### 3.10 Views und Integrity- / AI-Tabellen

In `C06980Hc.A0C` erzeugte Views (found): `available_message_view`, `deleted_messages_view`, `deleted_messages_ids_view`, `chat_view` (zwei Varianten, gewählt über `isGlobalChatDbMigrated`).

| Tabelle | Spalten |
|---------|---------|
| `integrity_chat_info` | `chat_row_id` (PK), `is_reach_out`, `is_eligible_for_link_friction_banner` |
| `integrity_analysis_result` | `chat_row_id`, `last_message_row_id`, `result`, `timestamp`, `animation_played`, `trusted_timestamp`, `view_timestamp`, `holdout_group`, `experiment_group`, `chatting_untrusted_timestamp`, `replied_timestamp`, `block_logged_timestamp`, `trust_logged_timestamp`, `report_logged_timestamp` |
| `integrity_input_feature` | `chat_row_id`, `sender_reputation`, `country_mismatch`, `fetched_timestamp` |
| `tee_chat_request_table` | `message_row_id`, `chat_request_type`, `anchor_message_row_id`, `node_token`, `extra_data` |
| `tee_message_info_table` | `message_row_id`, `message_interaction_type`, `message_outgoing_status`, `message_source`, `message_replay_metadata` |
| `ai_thread_info` | `thread_id_row_id`, `title`, `creation_ts`, `variant`, `last_thread_messages_row_id`, `last_message_timestamp`, `title_source`, `unseen_message_count`, `origin_chat_row_id`, `selected_mode`, `selected_modes` |
| `bot_chat_info` | `chat_row_id`, `welcome_request_message_sent`, `bot_metrics_thread_origin` |
| `bot_memory_metadata` | `_id`, `message_row_id`, `memory_annotated_user_message_key_id`, `memory`, `memory_id`, `added`, `bot_jid_row_id` |

---

## 4. wa.db: Kontakte, Blocklisten, Trust-Daten

### 4.1 Familien (found, 88 Klassen)

| Familie | Tabellen |
|---------|----------|
| Kontakte | `wa_contacts`, `wa_contact_details`, `wa_contacts_created_within_wa`, `wa_contacts_pending_operations`, `wa_contact_refresh_pending`, `wa_contact_refresh_patch_log`, `wa_contact_storage_usage`, `wa_address_book`, `wa_org_contacts`, `wa_orgs`, `system_contacts_version_table` |
| Blocklisten / Allowlisten | `wa_block_list`, `wa_block_list_interop`, `wa_last_seen_block_list`, `wa_profile_photo_block_list`, `wa_about_block_list`, `wa_pix_block_list`, `wa_cover_photo_block_list`, `wa_status_view_allow_list`, `wa_status_view_black_list`, `wa_group_add_allow_list`, `wa_group_add_black_list`, `wa_stickers_allow_list`, `wa_profile_links_deny_list` |
| Business | `wa_biz_profiles` + 12 `wa_biz_profiles_*` / `wa_biz_*`-Detailtabellen, `wa_vnames`, `wa_vnames_localized` |
| Gruppen | `wa_group_admin_settings`, `wa_group_descriptions`, `group_membership_approval_requests`, `non_admin_group_membership_approval_requests`, `group_membership_count`, `group_membership_form_questions`, `group_relationship`, `subgroup_info`, `community_settings`, `member_suggested_groups_v2`, `group_suspension_appeal`, `group_non_wa_invites` |
| Trust / Integrity | `wa_trusted_contacts`, `wa_trusted_contacts_send`, `wa_biz_integrity_signals`, `wa_biz_integrity_chat_settings`, `start_chat_trust_signals`, `wa_contact_server_signals` |
| Konfiguration | `wa_props`, `wa_newsletter_props`, `wa_coex_properties`, `wa_ml_models`, `wa_last_entry_point`, `wa_logging_entry_point` |
| AI / Bots | `meta_ai_memory`, `wa_bot_profiles`, `wa_bot_commands`, `wa_subscriptions` |
| Sonstiges | `status_ranking(_global)`, `wa_chat_ranking_scores`, `wa_storage_monitoring_data/_jobs`, `inbound_/outbound_connection_requests`, `dismissed_*`, `quick_promotion_payload` |

### 4.2 wa_contacts

36 Spalten (`Nn5`), geschlüsselt über `jid` (TEXT, rohe JID-String; eine Telefon-JID oder eine `@lid`-JID, keine `jid`-Zeilen-ID):

`jid`, `is_whatsapp_user`, `status`, `status_timestamp`, `number`, `raw_contact_id`, `display_name`, `phone_type`, `phone_label`, `photo_ts`, `thumb_ts`, `photo_id_timestamp`, `given_name`, `family_name`, `wa_name`, `sort_name`, `nickname`, `company`, `title`, `status_autodownload_disabled`, `keep_timestamp`, `is_spam_reported`, `is_sidelist_synced`, `is_business_synced`, `disappearing_mode_duration`, `disappearing_mode_timestamp`, `disappearing_mode_support_disabled`, `history_sync_initial_phash`, `is_starred`, `is_wa_created_contact`, `sync_policy`, `status_emoji`, `is_contact_synced`, `is_reachable`, `external_user_state`, `fts_dirty_version`.

`wa_name` ist der vom Kontakt gesetzte Push-Name; `display_name` / `given_name` stammen aus dem Adressbuch. Mehrere Satellitentabellen verwenden `BEFORE DELETE ON wa_contacts`-Trigger (z. B. `start_chat_trust_signals_contact_delete`, `contact_bd_for_business_integrity_signals`).

### 4.3 Weitere wa.db-Tabellen

| Tabelle | Spalten |
|---------|---------|
| `wa_trusted_contacts` | (+ `jid`), `incoming_tc_token` BLOB, `incoming_tc_token_timestamp` LONG. Siehe [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_trusted_contacts_send` | (+ `jid`), `sent_tc_token_timestamp` LONG, `real_issue_timestamp` LONG |
| `wa_biz_integrity_signals` | 17 Spalten: `_id`, `jid`, `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `is_suspicious`, `join_date_ms`, `is_banned`, `phone_country_code`, `trust_tier`, `is_meta_verified`, `mv_friction_eligibility`, `integrity_tags`, `chat_row_id`, `last_sync_ts`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Vollständige Semantik im Ban-Report 5.1 |
| `start_chat_trust_signals` | (+ `jid`), `is_sender_suspicious`, `is_sender_new_account`, `created_ts` REAL |
| `meta_ai_memory` | `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER; Index `meta_ai_memory_memory_content_index` auf `memory_content` |
| `wa_contact_server_signals` | `chat_jid`, `signal_type`, `value`, `update_ts` |
| `wa_group_admin_settings` | `jid`, `restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `creator_jid`, `is_suspended`, `group_state`, `require_membership_approval`, `member_add_mode`, `addressing_mode`, `history_enabled`, `group_history_toggle_mode`, `share_group_history_setting_mode`, `earliest_group_history_message_timestamp_ms`, `allow_member_labels`, ... (31 Spalten) |
| `wa_storage_monitoring_data` | `db_name`, `table_name`, `table_size_bytes`, `index_size_bytes`, `table_unused_bytes`, `index_unused_bytes` (der Client misst seine eigenen Tabellengrößen; siehe 10.3) |

---

## 5. axolotl.db (Signal-State)

Aktuelle DDL (neueste Varianten in `C44861sL`, Tabellen registriert durch `AbstractC11250Yd`; found). Schlüsselmaterial wird in BLOB-`record`-Spalten gespeichert; hier sind keine Schlüssel-Bytes dokumentiert.

| Tabelle | Spalten | Rolle |
|---------|---------|-------|
| `identities` | `_id`, `recipient_id`, `recipient_type`, `device_id`, `registration_id`, `public_key`, `private_key`, `next_prekey_id`, `next_kyber_prekey_id`, `timestamp`, `account_encryption_attestation_type`, `mark_as_verified`, `mark_as_verified_action_seq`, ... | eigene Identitätszeile und entfernte Identitäten (`recipient_type` trennt Telefon- und LID-Konten) |
| `sessions` | `_id`, `device_id`, `record`, `timestamp`, `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope` | Double-Ratchet-Sessions |
| `prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `key_type` | One-Time-Prekeys |
| `signed_prekeys` | `_id`, `prekey_id` UNIQUE, `timestamp`, `record`, `key_type` | |
| `kyber_prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `last_resort_key` | Post-Quantum-Prekeys |
| `prekey_uploads` | `_id`, `upload_timestamp`, `key_type` | |
| `sender_keys` | `_id`, `group_id`, `device_id`, `record`, `timestamp`, `sender_account_id`, `sender_account_type`, `bucket_id` | Gruppen-Sender-Keys |
| `message_base_key` | `_id`, `msg_key_remote_jid`, `msg_key_from_me`, `msg_key_id`, `recipient_id`, `recipient_type`, `device_id`, `last_alice_base_key`, `timestamp` | |
| `chat_stanza_queue`, `e2ee_stanza_queue`, `unordered_stanza_queue`, `preacks`, `stanza_sts` | `stanza_id`, `stanza_key` UNIQUE, `stanza_class`, `chat_jid`, `sender_jid`, `stanza_payload`, ... | Persistenz eingehender Stanzas vor der Entschlüsselung |

Die Java-Schicht des Signal-Stores ist Code im Stil von `signal_protocol_store` über diesen Tabellen. Krypto-Prefs auf Kontoebene liegen in `keystore.xml` und `wacrypto.xml` (8.3), nicht hier.

---

## 6. sync.db, companion_devices.db und die kleineren Datenbanken

| DB | Tabellen und Schlüsselspalten |
|----|-------------------------------|
| `sync.db` | `syncd_mutations` (`mutation_index` UNIQUE, `mutation_value` BLOB, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name`), `pending_mutations` (gleich plus `operation`, `is_ready_to_sync`), `collection_versions` (`collection_name` PK, `version`, `lt_hash` BLOB, `dirty_version`), `crypto_info` (`device_id`, `epoch`, `key_data`, `timestamp`, `fingerprint`, `stale_timestamp`), `missing_keys`, `msg_history_sync`, `history_sync_companion`, `peer_messages`, `placeholder_retry_message`, `rmr_response_error`. Protokoll: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md) |
| `companion_devices.db` | `devices`: `device_id`, `device_os`, `platform_type`, `last_active`, `login_time`, `logout_time`, `adv_key_index`, `full_sync_required`, `place_name`, `nickname`, ... Protokoll: [WA_LINKED_DEVICE_PAIRING.md](WA_LINKED_DEVICE_PAIRING.md) |
| `status.db` | `status`, `status_text`, `status_thumbnail`, `status_info`, `status_interactions`, `status_interactions_totals`, `status_seen_receipt`, `status_receipt_device`, `status_reply`, `status_send_part`, `status_privacy_custom_list`, `status_crossposting_v2/_v3`, ... plus `key_value_store` (`row_id`, `key`, `value`) |
| `backup.db` | `backups`, `backup_props` (`prop_name`, `prop_value`; Zeile `wa_db_schema_version`) |
| `chatsettings.db` | `settings`: `_id`, `jid`, `deleted`, `mute_end`, `muted_notifications`, `use_custom_notifications`, `message_tone`, `call_tone`, `status_muted`, `pinned`, `pinned_time`, `media_visibility`, `mute_reactions`, `wallpaper_*`, `auto_delete_media`, `transcription_locale`, `source_lang`, `target_lang`, `snooze_end_time`, `theme_id` (39 Spalten) |
| `stickers.db` | `stickers` (`plain_file_hash`, `encrypted_file_hash`, `media_key`, `mime_type`, `sticker_pack_id`, `file_path`, `url`, `direct_path`, `emojis`, `is_lottie`, ...), `recent_stickers`, `starred_stickers`, `installed_sticker_packs`; `payments.db`: `methods` (`credential_id` PK, `country`, `issuer_name`, `type`, `balance_1000`), `contacts`, `receipts`, `tmp_transactions` |

---

## 7. Backups und crypt15

### 7.1 Lokale Backup-Dateien

| Namensmuster (found, `AbstractC26994Bml`, `C29412Cpb`) | Inhalt |
|--------------------------------------------------------|--------|
| `msgstore.db.crypt15`, `msgstore.db.crypt14` | vollständiges Backup der Chat-Datenbank (Regex `msgstore.db.crypt(\d+)`) |
| `msgstore-increment-<N>.db.crypt<V>` | inkrementelles Backup |
| `backup_settings.json.crypt<V>`, `status_backup.db.crypt<V>`, `commerce_backup.db.crypt<V>`, `chat_transfer_settings.json.crypt<V>` | Einstellungen, Status, Commerce, Chat-Transfer-Einstellungen |
| `stickers.db.crypt<V>`, `chatsettingsbackup.db`, `wa-backup.db` | Backups von Stickern / Chat-Einstellungen / wa.db (Komponentennamen unten) |

Das Root ist `Backups/` unter dem externen Media-Root (`C0KE.A02`; veraltet `Databases/`, `C0KE.A03`). Das Root wird über die Pref `external_storage_type` gewählt (der Wert `scoped` wird in `C11160Xu.A07` geprüft; andere Werte nicht aufgezählt); `EnumC046905z` kann zu `getExternalMediaDirs()[0]`, `getExternalStorageDirectory()`, app-spezifischen externen Verzeichnissen oder den internen Verzeichnissen auflösen. Sekundäre Konten verwenden `<root>/accounts/<dirId>` für `Media/WhatsApp ...`-Pfade (`C0KE.A00`).

Backup-Komponenten (`A0F`-Namen in `CMN`-Subklassen, found): `stickers`, `stickers-db`, `wallpapers`, `payment-backgrounds-v2`, `chat-transfer`, `wa-db`, `commerce-db`, `status_db`, `offloaded-media.db`, `chatlock_backup`, `chat-settings`, `backup-settings`. `backup_prefs` führt pro Komponente `<component>_backup_size` / `_backup_status` (8.3).

Medienkategorien in der Backup-UI (`EnumC26330BbW`, 17 Werte): `CHAT_DB`, `SETTINGS`, `STATUS_DB`, `COMMERCE_DB`, `OTHER_DB`, `IMAGES`, `VIDEOS`, `AUDIO`, `VOICE_NOTES`, `VIDEO_NOTES`, `GIFS`, `DOCUMENTS`, `STICKERS`, `STICKER_PACKS`, `PROFILE_PHOTOS`, `EXCLUDED_STICKERS`, `OTHER`.

### 7.2 crypt15-Dateipräfix (found)

`EnumC26325BbR`: `UNENCRYPTED` 0, `CRYPT14` 14, `CRYPT15` 15 (ein `.crypt`-Suffix ohne Zahl ist die alte Form; `CKv` matcht `.crypt`). Der crypt15-Reader (`BN4.A09`) parst vor dem Ciphertext ein length-delimited Protobuf `BackupPrefix` (`BCE`):

| Feld | Nummer | Typ | Verwendung |
|------|--------|-----|------------|
| `key_type_deprecated` | **1** | enum | alter Key-Typ |
| `wa_provided_key_data` | **2** | bytes | Schlüsseldaten für vom Server bereitgestellte Schlüssel |
| `e2ee_key_data` | **3** | message | Schlüsseldaten für Ende-zu-Ende-verschlüsseltes Backup |
| `backup_metadata` | **4** | `BD0` | siehe unten |
| `passkey_encryption_metadata` | **5** | message | Passkey-Pfad (`parsePasskeyEncryptionMetadata`) |
| `key_type_new` | **6** | enum | aktueller Key-Typ |

Key-Typen (`BdX`): `WA_PROVIDED` 0, `E2EE_DEPRECATED` 1, `E2EE_PASSWORD` 2, `E2EE_ENCRYPTION_KEY` 3, `E2EE_PASSKEY` 4.

Felder von `BackupMetadata` (`BD0`) (Auswahl): `app_version` **1**, `device_model` **2**, `jid_suffix` **3**, `backup_version` **4**, `backup_export_file_size` **38**, `cleaned_db` **39**, `backup_encrypted_hash_salt` **40**, `backup_encrypted_hash` **41**, `identifier_type` **42**, `lid_suffix` **43**, `display_suffix` **44**, dazu etwa 30 `*_migration_finished`-Booleans (Nummern 5 bis 35). Beim Restore vergleicht `EncBackupUtils` `jid_suffix` mit dem registrierten Nutzer (`has-jid-user-mismatch`): Ein Backup ist an das Konto gebunden, das es erzeugt hat.

Cipher, KDF und MAC-Layout des Ciphertexts wurden hier nicht gelesen (unknown).

### 7.3 Backup-Schlüsselmaterial

| Datei (in `files/`) | Inhalt | Beleg |
|---------------------|--------|-------|
| `encrypted_backup.key` | 32-Byte-Root-Key des Ende-zu-Ende-verschlüsselten Backups (`C29861Ep.A09`, Länge geprüft == 32); geschrieben von `A04(...)`, möglicherweise von einem KeyStore-Encapsulation-Key umhüllt (`failed to load or create KeyStore encapsulation key`) | found |
| `encrypted_backup.key_id` | Schlüsselkennung | found |
| `password_data.key`, `passkey_data.key` | Zustand für die Passwort- und Passkey-Varianten (Passkey-Daten sind JSON) | found |
| `vault_backup.key` | 32-Byte-Vault-Key, erzeugt mit `C00L.A0H(32)`; weigert sich, eine unlesbare Datei zu überschreiben (`vault backup key present but could not be read`) | found |
| `prf_derived_root_key.key`, `secret_code.key` | aus Passkey-PRF abgeleiteter Root-Key, Secret-Code-Key | Name found, Inhalt unknown |
| `backup_token`, `foa_backup_token` | Token-Datei (`CMc`, `foa_`-Variante für das Accounts-Center-Konto) | found |

`AbstractC29801Ej` löscht `encrypted_backup.key(_id)`, `password_data.key`, `passkey_data.key`, `vault_backup.key` gemeinsam (Key-Reset).

### 7.4 Android-Auto-Backup und der Migrations-Provider (found)

| Element | Wert |
|---------|------|
| `android:allowBackup` | `true`, `fullBackupOnly=true`, Backup-Agent `SystemBackupAgent` |
| `fullBackupContent` (`xml0003`) und `dataExtractionRules` (`xml0006`: Cloud-Backup und Device-Transfer) | schließen **jede** Domain aus (`root`, `file`, `database`, `sharedpref`, `external`, `device_*`). Die Plattform überträgt nichts |
| `cross-platform-transfer platform="ios"` | mit der iOS-Bundle-ID deklariert; der Transfer läuft über `OsMigrationAppDataService` (Berechtigung `android.permission.BACKUP`) |
| `MigrationContentProvider` | exported, `readPermission com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` (protectionLevel `signature`), `grantUriPermissions=false`. URIs: `msg_store`, `unencrypted_msg_store`, `wa_db`, `chat_setting_store`, `sticker_store`, `wallpaper`, `share_preferences`, `media`, `chat_lock_passcode`. `DirectMigrationContentProvider` verwendet dieselbe Berechtigung. Der Zweck (Übergabe an die Schwester-App mit derselben Signatur) ist inferred |

---

## 8. SharedPreferences

### 8.1 Factory

`C00S` (SharedPreferencesFactory, `A04(C00G, name)`): liefert eine eigene Implementierung über `<dataDir>/shared_prefs/<name>.xml` (`C052308r`-Datei-Wrapper; Klassen `C052408s` / `RRP`), mit Fallback auf das System-`getSharedPreferences(name, 0)`, falls das Verzeichnis nicht angelegt werden kann. Ob die Bytes auf der Platte Standard-Android-XML sind, wurde im Code nicht verifiziert (nur die Dateiendung).

| Fakt | Beleg |
|------|-------|
| Namensmengen mit Sonderbehandlung in `AbstractC051008e` (`A02`, `A03`: Feature-Flags der Implementierung; `A00`, `A01`, `A04`: Scoped-Mengen) | found; Flag-Semantik von `C00G(boolean,boolean,boolean)` unknown |
| Die Menge `A05` (`multi_account_metadata`, `group_history_usage`, `hatch_group_agent`, `hatch_group_agent_debug`, `smb_token_lockout_cooldown`) darf von dieser Factory nicht angelegt werden: Meldung `Pref not allowed to instantiate using SharedPreferencesFactory, use MultiAccountSharedPreferencesFactory` | found |
| Haupt-Dateinamen leiten sich von `AbstractC051108f` ab: `com.whatsapp_preferences` und `com.whatsapp_preferences_light` | found |
| `SharedPreferencesUsageRepository` (`C052508t`) erfasst Ladezeiten pro Prefs-Datei (`load`, `load2`) und überspringt `ab-props`, `ab-props-back-up`, `ab-prechatd-props`, `ab-props-backup`, `dropped_wam_events`, `keystore` | found: Telemetrie über die Prefs selbst |
| `C09E` (veraltete "Me"- und Prefs-God-Class) umhüllt `com.whatsapp_preferences_light` (`C1WL` Case 23); viele kleine Wrapper (`C1DH`, `C56902Wq`, `C0G1`) sind Sichten auf diese eine Datei | found |
| Die Standard-Datei `com.whatsapp_preferences` ist die normale Android-Datei; `chatCounts` ist eine separate Datei (`RP5`) | found |

### 8.2 Dateien nach Bereich (Namen im Code gefunden)

| Bereich | Dateien |
|---------|---------|
| Core | `com.whatsapp_preferences`, `com.whatsapp_preferences_light`, `startup_prefs`, `reg_prefs`, `register_phone_prefs`, `registration.verifyphone.VerifyPhoneNumber`, `registration.app.phonenumberentry.RegisterPhone`, `registration.app.verifyphone.VerifyPhoneNumber`, `multi_account_metadata`, `account_linking_prefs`, `fb_credentials_prefs`, `fb_linked_account`, `accounts_center_registration_prefs` |
| Flags | `ab-props`, `ab-props-backup`, `ab-props-back-up`, `ab-prechatd-props`, `groupAbProps`, `network_resources_pref` |
| Krypto | `keystore`, `wacrypto`, `security_prefs`, `nc_prefs`, `chat_lock`, `migration_export`, `AccountDefenceLocalDataRepository_prefs` |
| Backup / Sync | `backup_prefs`, `chat_transfer_prefs`, `syncd_prefs`, `contact_sync_prefs`, `device_capabilities`, `companion_mode_prefs` |
| Features | `username_prefs`, `meta_ai_prefs`, `bonsai_prefs`, `paa_prefs`, `status_prefs`, `newsletter_prefs`, `voip_prefs`, `route_selector_prefs`, `interop_ui`, `interop_badge_prefs`, `avatar_prefs`, `bloks`, `privacy_disclosure_store`, `user_notice_prefs`, `tos_gating_prefs` |
| Telemetrie | `critical_event_client_prefs`, `anr_shared_prefs`, `time_spent_prefs`, `dropped_wam_events`, `wam_prefs`, `chatCounts` |
| Drittanbieter-SDK | `com.google.android.gms.appid`, `com.google.firebase.messaging`, `WebViewChromiumPrefs` (System) |

### 8.3 Wichtige Keys (alle Key-Namen in 2.26.41.6 gefunden; Werte nicht wiedergegeben)

| Datei | Key | Typ / Verwendung |
|-------|-----|------------------|
| `startup_prefs` | `registration_state` | int; `C06810Gk`-Prädikate: 0/1 initial, 3, 4, 5, 8 (Flash-Verify), 12, 15, 17 (E-Mail-OTP), 20, 23 |
| | `startup_migrated_version` | int; Ziel **20**, `WaStartupSharedPreferences` führt darunterliegende Migrationen aus |
| | `push_name` | eigener Anzeigename |
| | `force_db_check`, `force_wadb_check` | erzwingen Integritätsprüfung von msgstore / wa.db (gelöscht durch `C0HS.BoJ`, `C12650bW.onCreate`) |
| | `pending_repair_db_name`, `pending_repair_db_file_id`, `pending_repair_corruption_type`, `pending_repair_attempt_count`, `pending_repair_request_id`, `pending_repair_timestamp`, `pending_repair_gate_suppressed` | Warteschlange für Datenbankreparatur |
| | `privacy_fingerprint_enabled`, `night_mode`, `client_server_time_diff` (gelesen von `C050708b`) | |
| `com.whatsapp_preferences_light` | `registration_jid`, `registration_lid`, `cc`, `ph`, `self_lid`, `registration_initialized_time`, `registration_success_time_ms`, `registration_wipe_info_timestamp`, `reg_attempts_verify_code` | Identität dieser Installation (gelöscht durch `RegistrationManager.A0I`) |
| | `adv_raw_id`, `adv_current_key_index`, `adv_timestamp_sec`, `phoneid_id`, `phoneid_timestamp` | ADV- / Phone-ID-Zustand |
| | `privacy_last_seen`, `privacy_profile_photo`, `privacy_status`, `privacy_online`, `read_receipts_enabled`, `privacy_token_batch_offset_sec` | Privatsphäre-Einstellungen (`C18260lS`, `C09E.A0S()`) |
| | `md_messaging_enabled`, `last_login_time`, `last_daily_cron`, `next_randomized_daily_cron`, `nct_salt` | Multi-Device-Flag, Cron-Buchführung, tctoken-Salt ([WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md)) |
| `backup_prefs` | `gdrive_state`, `backup_provider`, `backup_encryption_method`, `encrypted_backup_fleet_migration_state`, `encrypted_backup_num_attempts_remaining`, `google_restore_result`, `msg_restore_timestamp`, `last_seen_app_version`, `device_backup_integration_enabled`, `blocking_restore_in_progress`, `cloud_api_type`, `restore_second_verification_needed` | Backup- und Restore-Zustand (`C22090sX`) |
| `keystore` | `server_static_public`, `server_static_pq_public`, `client_static_keypair_pwd_enc`, `client_static_keypair_enc_success`, `can_user_android_key_store`, `remaining_auth_key_rotation_attempts` | Noise-Static-Keys ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md), [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md)) |
| `wacrypto` | `signed_prekey_id_seed_migration_completed` | Migration des Signal-Prekey-ID-Seeds |
| `ohai_key_config` (Pref-Name in `C53596Nzj`) | `public_key` und Key-Config-Felder | OHAI-Gateway-Key |
| `syncd_prefs` | `syncd_dirty`, `syncd_bootstrap_state`, `syncd_bootstrapped_mutations` (Set), `mutation_counter` | Bootstrap des App-State-Sync |
| `companion_mode_prefs` | `previously_logged_out_from_primary` | Companion-Zustand |
| `username_prefs` | `username_reservation_state`, `username_pin` | siehe [WA_USERNAME.md](WA_USERNAME.md) |
| `route_selector_prefs` | `media_conn` | gecachte Media-Route (Hostliste und Auth-Daten; [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md)) |
| `ab-props` | numerische String-Keys (Config-Codes), `ab_props:sys:last_refresh_time`, `ab_props:sys:config_hash`, `ab_props:sys:last_version`; `com.whatsapp_preferences` enthält `ab_props:hash_v2` | AB-Prop-Cache; `ab-props-backup` ist die vorherige Kopie |
| `chatCounts` | Zähler pro Chat, `thread_user_secret` (32 Zufallsbytes, base64) | `WamThreadIdManager` bildet damit HMACs der Thread-IDs; `RP5.A0w` behält es über einen Reset hinweg |

---

## 9. Dateien, Caches und Media-Layout

### 9.1 Internes `files/` (found, sofern nicht anders markiert)

| Pfad | Inhalt |
|------|--------|
| `me` | Java-serialisierter `Me`-Record (`C9V.A01`, Felder u. a. `cc`, `number`); `me.jpg` / `me_old.jpg` Profilfoto |
| `rc2` | AES/OFB-verschlüsselter 160-Bit-Zufallswert, bei erster Verwendung für zwei String-Eingaben erzeugt (`K49.A0v`, `C00L.A0G`; inferred: Ländercode und Nummer); Zweck inferred (Registrierungs-Secret). Gelöscht durch die Wipe-Runnables `RunnableC29329CoG`, `RunnableC46625KYz` |
| `backup_token`, `foa_backup_token`, `encrypted_backup.key*`, `vault_backup.key` | Abschnitt 7.3 |
| `invalid_numbers`, `login_failed`, `customTSValues`, `emoji` | kleine Zustandsdateien (`IJU`, `C06850Go`) |
| `statistics.json`, `network_statistics.json` | rx- / tx-Zähler (`C17B`, `C17J`; Keys `statistics`, `bytes`, `timestamp`, `rx_data`, `tx_data`) |
| `Logs/` | Logdateien (10.1) |
| `decompressed/libs.spo/` (+ `.superpack_version`) | zur Laufzeit von `C0EE` entpackte Bibliotheken; **von jedem Wipe ausgenommen** |
| `mobileconfig/` | `mc_overrides.json`, `id_name_mapping.json` (`C053409d`) und der Config-Store |
| `falco/`, `wam/` | Telemetrie-Engines (10) |
| `Stickers/`, `Drafts/`, `GroupHistory/`, `Payment Backgrounds/`, `Wallpapers/`, `.trash/`, `biz_directory/`, `privacy_disclosure/<version>/`, `downloadable/`, `NetworkResource/`, `MNSResolverCache/`, `app_state/` | Feature-Caches (`C0I1`, `C58398QKk`, `C27574Bxe`, `MNSStreamRuntime`, `C06110Cn`) |

Weitere private Verzeichnisse, die der Storage-Config-Switch (`AbstractC13030c9`) nennt: `lib-compressed`, `app_secure_shared`, `app_sigquit`, `modules`, `app_optsvc_analytics`, `app_overtheair`, `app_qpl`, `app_light_prefs`, `cache/secure_shared`, `files/secure_shared`, `app_minidumps`, `app_fb-forker-tmp`.

### 9.2 `cache/` (found)

| Verz. | Hinweis |
|-------|---------|
| `thumb_decoded_cache` | Disk-LRU, **52428800 Bytes (50 MiB)** (`C33000EZy`) |
| `webp_static_cache`, `stickers_cache`, `avatar-temporary`, `interop_image_cache`, `tigon_http_client`, `ML_MODEL`, `hatch_space_images`, `meta_ai_thread_photo_uploads` | Bild- / Netzwerk- / Modell-Caches |
| `Profile Pictures/` | kontobezogen (`C28025CFb.A01` liefert das Cache-Verzeichnis; `QLH` baut `Profile Pictures`) |

### 9.3 Sekundäre Konten (found)

`getDir("account_switching")` (= `app_account_switching/`) enthält `active_account` (die ID des aktiven Verzeichnisses, `C00W`) und die Kontoliste (`C25160AsA`). Die Daten eines sekundären Kontos liegen in `<dataDir>/accounts/<dirId>/{databases,files,cache}` (`C28025CFb`) und seine Medien unter `<root>/accounts/<dirId>`; das Standardkonto nutzt die normalen Verzeichnisse. `account_switcher.db` und die Multi-Account-Prefs werden geteilt.

### 9.4 Externes Media-Root (found)

`<root>/Media/WhatsApp <Category>/` mit den Kategorien `Images`, `Video`, `Audio`, `Documents`, `Voice Notes`, `Video Notes`, `Animated Gifs`, `Stickers`, `Sticker Packs`, `Profile Photos`, `Backup Excluded Stickers` (`AbstractC26994Bml`), Unterordnern `Sent`, `Private`, `.Thumbs` (`*.prog.thumb.jpg`, `C0I1.A08`), `.Shared`, `.nomedia`-Markern. `message_media.file_path` speichert den Teil nach dem Root.

---

## 10. Auf dem Gerät gehaltene Logs und Telemetrie

### 10.1 Logs (found)

| Datei | Detail |
|-------|--------|
| `files/Logs/whatsapp.log`, `whatsapp.tmp` | Textlog, Header `==== logfile version=2.26.41.6 level=4 ====`; die Rotation komprimiert zu `.gz` mit Datum (`Log.rotate`, `AbstractC28128CKx.A00`). `C24971Ap6` sammelt `Logs` zusammen mit dem DB-Verzeichnis für den Support- / Bugreport-Export |
| `app_minidumps/`, `<dir>/minidumps`, `crash_upload/` | native Crash-Dumps und das Upload-Staging (`C0FQ`, `JJ1`, `CKN`, `ExceptionsUploadService`) |
| `anr_report_<n>.dmp`, `anr_shared_prefs` | ANR-Reports (`C45432Jrw`) |
| `cache/qpl`, `app_qpl` | QuickPerformanceLogger-Traces |

### 10.2 Telemetrie-Engines

| Pfad | Engine | Beleg |
|------|--------|-------|
| `files/wam/` | WAM-Runtime-Verzeichnis, an `WAJContextInitWAMRuntime` (JNI) übergeben | `RunnableC29323CoA`; Prefs `dropped_wam_events` und `wam_prefs` |
| `files/falco/` | Event-Logger in `libffsingletonmerged.so` | native Strings unten |
| `files/mobileconfig/` | Mobile-Config-Store | `C053409d` |

Falco-SQLite-Datei `FFLogger.sql` (Ort inferred: Java legt `files/falco/` an, der Dateiname ist ein String in der nativen Lib): in den nativen Schema-Strings vorhandene Tabellen (found): `event`, `buffer_event`, `upload` (`request_data`, `num_events`, `is_compressed`, `compression_method`), `claim` (`principal_subject_hash`, `claim`, `expires_at`), `collection_constraint`, `event_config` (`event_config_hash` UNIQUE, `event_name`, `sampling_rate`, `collection_constraint_ref`, `is_deidentified`), `checksum`, `amendment_outbox`, Index `event_0` auf `event(requested_latency)`; `batch` joint über `identities_hash`. `fflogger_health_counters.bin` hält Zähler der Selbstinstrumentierung (`mobile_health_counters`). Die Java-Seite legt nur das Verzeichnis an.

### 10.3 Selbstmessung

wa.db `wa_storage_monitoring_data` / `_jobs` (Größen pro Tabelle und ungenutzte Bytes je `db_name`) und die Prefs-Ladestatistiken (8.1) sind Telemetrie, die der Client über seinen eigenen Speicher führt. Die WAM-Event-Pipeline selbst liegt hier außerhalb des Umfangs.

---

## 11. Was wann gelöscht wird

### 11.1 Operationen

| Operation | Einstieg (2.26.41.6) | Effekt |
|-----------|----------------------|--------|
| Konto löschen / lokaler Daten-Reset | `C25007Aph.A0L` dann `A02` (`removeDatabasesAndResetState`) | vollständiger lokaler Wipe, 11.2 |
| Companion entfernt | `C25007Aph.A0M` (`deleteCompanionCleanup`) | `ActivityManager.clearApplicationUserData()` (Fallback `pm clear <package>`, Fallback auf `A02`) |
| Re-Register | `RegistrationManager.A06` (`reregister reason=`) | löscht Registrierungs-Prefs und `me`, 11.3 |
| Unregister vom Gerät | `RegistrationManager.A0F` | stoppt die Verbindung mit `should_unregister=true`, löscht `me`, setzt den Zustand zurück |
| Logout (Primärgerät, mit Multi-Account) | `LogoutManager` (`AccountLogoutMutation`, w:mex) | Server-Logout, Konto als ausgeloggt markiert; Daten bleiben, bis der Nutzer das ausgeloggte Konto entfernt (11.4). Ob der erste Schritt lokal etwas löscht, wurde nicht nachverfolgt (unknown) |
| Ausgeloggtes Konto entfernen | `LogoutManager.removeLoggedOutAccountWithCleanup` | entfernt den Konto-Eintrag, dann `deleteDefaultAccountDirectories` oder `deleteSecondaryAccountDirectories`, dann GMS-Backup-Zustand |

### 11.2 Kontolöschung (`C25007Aph.A02`, found)

| Ziel | Aktion |
|------|--------|
| In-Memory-Stores, Feature-Manager | geleert; `last_contact_full_sync` = -1 |
| Datenbanken | Delete jedes Helpers (`A0D`, `A0N`): msgstore über `C0HC` (`msgstore-manager/deletedb/result`), wa.db (`deleteaccountconfirm/wa-db-delete-incomplete` ist ein Fehler, falls Dateien übrig bleiben), commerce, `emojidictionary`, Sprachpaket-Store, `MediaJobDataStore`, History-Sync-Stores, Business-Verzeichnis (`files/biz_directory`) |
| `files/` | alle Einträge außer `decompressed`; `Logs` bleibt erhalten, wenn das Flag `z` gesetzt ist (Companion-Pfad) |
| Externes Root | `Backups/` entfernt und leer neu angelegt, `Databases/`-Dateien entfernt (`AbstractC28132CLd.A04`), nur wenn der externe Speicherzustand nutzbar ist |
| `com.whatsapp_preferences` | `clear()`, danach wird `version` mit `2.26.41.6` neu geschrieben |
| `backup_prefs` | `clear()`, aber `last_seen_app_version` und `device_backup_integration_enabled` werden wiederhergestellt |
| `chatCounts` | alle Keys entfernt außer `thread_user_secret` (`RP5.A0A`) |
| Weitere Prefs | `avatar_prefs`, die Registrierungs- und VerifyPhone-Dateien, Companion-Registrierung (`registration_device_id`, `companion_registration_state` = 0), einige Feature-Prefs |
| WebView | Cookies und Web-Storage gelöscht, auch für benannte Profile, wenn Multi-Profile verfügbar ist |

### 11.3 Reregister / Unregister (found)

`RegistrationManager.A0I` entfernt `registration_jid`, `registration_lid`, `cc`, `ph` und `registration_wipe_info_timestamp`; `A0A` leert die Prefs der beiden Registrierungsbildschirme; die Datei `me` wird entfernt (`rm-me`).

### 11.4 Dialog "Ausgeloggte Chats" (`FilesDeletionUtility`)

Löscht das externe Root des ausgeloggten Nutzers, `cacheDir`, jeden Eintrag von `filesDir` außer `decompressed`, das Files-Verzeichnis des sekundären Kontos und ruft dann das Delete der DB-Helper auf; ein fehlgeschlagenes Löschen von wa.db wirft eine Exception, und der Dialog meldet einen Fehler (`FilesDeletionUtility/deleteInternalFiles/wa-db-delete-incomplete`).

### 11.5 Datei-Löschung bei Multi-Account (`AccountSwitchingFileManager.deleteDefaultAccountDirectories`)

Für das Standardkonto: `shared_prefs` wird bis auf eine Allow-List gelöscht; `databases` wird bis auf `account_switcher.db` (und seine Suffix-Varianten) gelöscht; andere Verzeichnisse werden komplett entfernt.

---

## 12. Baileys-Hinweise (inferred Mapping)

Baileys hält Credentials und einen Key-Store (`creds`, pre-key, session, sender-key, app-state-sync-key / -version, lid-mapping, device-list, tctoken). Die konzeptionellen Gegenstücke auf Android (inferred; kein Code verknüpft sie):

| Baileys-State | Android-Speicher |
|---------------|------------------|
| `session`, `pre-key`, signed pre-key | `axolotl.db` `sessions`, `prekeys`, `signed_prekeys` (+ `kyber_prekeys` auf Android) |
| `sender-key`, `sender-key-memory` | `axolotl.db` `sender_keys`; Verteilung pro Gerät in msgstore `group_participant_device` |
| app-state sync key / version | `sync.db` `crypto_info` (`key_data`, `epoch`), `collection_versions` (`lt_hash`) |
| lid mapping | msgstore `jid_map` (+ `lid_display_name`) |
| device list | msgstore `user_device`, `user_device_info` |
| `tctoken` | wa.db `wa_trusted_contacts(_send)` |
| `creds.me`, registration id, ADV | `files/me`, Prefs `adv_*`, `identities`-Zeile |

Eine Baileys-Session hat kein Äquivalent zur `message`-Tabelle; das Löschen ihres Auth-States ist das Gegenstück zum Wipe in 11 und erfordert ein neues Linking.

---

## 13. Fehlerfälle und Fallstricke

| Symptom | Ursache | Fix / Hinweis |
|---------|---------|---------------|
| `msgstore/upgrade version 1 to N` erscheint nie | msgstore-`user_version` ist immer 1 | den echten Schemazustand aus `props.msgtore_db_schema_version` lesen |
| msgstore "restored-db-not-indexed" / `RestoredIndexesPending` | DB aus Backup wiederhergestellt; Indizes werden verzögert angelegt | `props`-Keys `MessagesDBHelper_*`; der Lauf endet asynchron |
| `still-corrupt-after-repair`, `delete-superseded-by-new-repair` | Integritätsprüfung fehlgeschlagen (`C0HC.checkhealth`) | Queue in `startup_prefs` `pending_repair_*`; `force_db_check` |
| wa.db nach Update plötzlich leer | Upgrade-Switch hat Tabellen verworfen (Versionen 3 bis 94) oder Schema-Hash hat sich geändert | wa.db ist aus Server und Adressbuch wiederherstellbar |
| `deleteaccountconfirm/completion-blocked/wa-db-files-remain` | wa.db-Dateien konnten nicht gelöscht werden | erneut versuchen; der Wipe bricht mit `Be5` ab |
| Restore lehnt ein Backup ab (`has-jid-user-mismatch`) | `BackupMetadata.jid_suffix` weicht vom Konto ab | mit derselben Nummer wiederherstellen |
| `backup-file-crypt15/prefix null` | Datei leer oder nicht crypt15 | das length-delimited Präfix prüfen (7.2) |
| `vault backup key present but could not be read` | `vault_backup.key` unlesbar | der Code erzeugt keinen Ersatz, um keine wiederherstellbare Datei zu überschreiben |
| `Pref not allowed to instantiate using SharedPreferencesFactory` | Pref nur für Multi-Account mit der falschen Factory angelegt | `MultiAccountSharedPreferencesFactory` verwenden |
| Daten eines ausgeloggten Kontos bleiben bestehen | Logout löscht keine Kontodaten (11.1) | das Konto explizit entfernen |

---

## 14. Wichtige Unterscheidungen

| Nicht verwechseln | Unterschied |
|-------------------|-------------|
| `msgstore.db` vs `wa.db` | Nachrichten, Chats und `jid`-Zeilen vs Kontakte, Blocklisten, Trusted-Contact-Tokens, Business- und Integrity-Caches; JID-Zeilen-IDs gibt es nur in msgstore, wa.db-Keys sind rohe JID-Strings |
| `jid._id` vs rohe JID | `*_jid_row_id`-Spalten sind msgstore-Zeilen-IDs; `wa_*`-Tabellen verwenden `jid` TEXT |
| SQLite-`user_version` vs Schemaversion | msgstore immer 1; wa.db 95; das Schema ist ein Hash in `props` (msgstore) oder ein Tag (wa.db) |
| Android-Auto-Backup vs Chat-Backup | Auto-Backup schließt alles aus; das Chat-Backup ist die eigene `crypt15`-Datei der App im externen Root |
| crypt15-Datei vs Schlüsseldateien | Ciphertext in `Backups/`; Schlüssel in `files/*.key` (nie im selben Ordner) |
| `com.whatsapp_preferences` vs `_light` | normale Android-Prefs (beim Wipe auf einen Versions-Key reduziert) vs die Datei der eigenen Implementierung, die `C09E` nutzt (Identität, Privatsphäre, Flags) |
| `ab-props` vs `wa_props` | AB-Experiment-Codes (Prefs) vs Server-Account-Props (wa.db-Tabelle) |
| Logout vs Kontolöschung | Logout markiert das Konto; Löschung wischt DBs, Dateien, Backups, Prefs (11) |
| Falco vs WAM | Falco ist der SQLite-Event-Logger in einer nativen Lib; `wam/` ist das WAM-Runtime-Verzeichnis; beides ist Telemetrie |
| Dateien aus Drittanbieter-Mods | zusätzliche Datenbanken, Stanza-Logs oder Hook-Diagnosen werden von der Stock-App nicht erzeugt und sind nicht abgedeckt |
---

## 15. Layout und Lebenszyklus

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

## 16. Nicht abgedeckt und unbekannt

| Thema | Status |
|-------|--------|
| DB-Zuordnung pro Tabelle für die 306 + 422 Tabellenklassen über die geprüften hinaus | Setgrößen found; Zuordnung jeder Klasse zu ihrer Datenbank über den DI-Graphen nicht nachverfolgt (inferred über FKs und Namen) |
| Spaltentypen, Defaults und NOT NULL bei mit Helper-Funktionen gebauten Tabellen | der Decompiler lässt einiges aus; nur Namen sind aufgelistet |
| Verbleibende ca. 250 msgstore-Tabellen, verbleibende wa.db- und status.db-Tabellen | Namen in Familien aufgelistet; Spalten nicht extrahiert |
| crypt15-Ciphertext-Format, KDF, MAC; Inhalt der Sub-Messages von `BackupPrefix` | unknown |
| Standard-XML-Format der eigenen Prefs-Implementierung auf der Platte | nicht verifiziert |
| Vollständige Key-Liste jeder Prefs-Datei (hunderte Keys) | nur die in 8.3 genannten Dateien und Keys |
| Bedeutung der `C00G`-Flags, Add-on-Typ-IDs, `registration_state`-Werte | teilweise benannt |
| Versionen von `sync.db`, `chatsettings.db`, `stickers.db`, `commerce.db`, `daily_metrics.db`, `location.db` | nicht aufgelöst |
| Zweck von `files/rc2`, `files/key` | `rc2` inferred; `key` nicht aufgelöst |
| Ob allein der Logout am Primärgerät lokale Daten löscht | nicht nachverfolgt |
| Laufzeitverhalten, Dateigrößen, WAL-Inhalte | nur statische Analyse |
