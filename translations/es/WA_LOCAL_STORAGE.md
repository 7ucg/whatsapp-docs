<!-- src-sha1: 6effa8dc57f2e12a66c37c7cae9d875028a5d55e -->
# WhatsApp Almacenamiento local — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** bases de datos SQLite (nombres, ubicación, motor, versionado, framework de tablas), tablas y columnas clave de msgstore.db y wa.db, axolotl.db, sync.db y las bases de datos menores, backups crypt15 y archivos de clave de backup, reglas de auto-backup de Android y el content provider de migración, factory de SharedPreferences e inventario de claves, estructura de archivos y caché, archivos de log y telemetría, qué eliminan logout / unregister / reregister / eliminación de cuenta

---

## 1. Qué se almacena dónde

Todas las afirmaciones provienen de análisis estático del APK decompilado y sus bibliotecas nativas incluidas. No se leyó ningún dato de un dispositivo. Tier: **found** = leído en código, manifest o strings nativos; **inferred** = deducido del código; **unknown** = no resuelto. Los nombres ofuscados son tal como los muestra JADX para 2.26.41.6 y cambian en cada build.

### 1.1 Mapa de almacenamiento

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

| Ubicación | Contenido | Sobrevive al auto-backup de Android |
|-----------|-----------|-------------------------------------|
| `databases/` | todos los archivos SQLite | no: todos los dominios están excluidos (8.1) |
| `shared_prefs/` | ajustes, flags, claves | no |
| `files/`, `cache/` | archivos de clave, cachés, logs | no |
| raíz externa `Backups/` | backup cifrado de chats (crypt15) | n/a: mecanismo de backup propio (7) |

### 1.2 Datos del motor (found)

| Hecho | Evidencia |
|-------|-----------|
| SQLite es el build incluido `io.requery.android.database.sqlite`, no el del framework | paquete en `java_src` |
| Sin SQLCipher: ningún `PRAGMA key`, ningún string `sqlcipher` en todo `java_src` | grep; los archivos de base de datos están en texto plano en reposo dentro del sandbox de la app |
| WAL habilitado para todos los helpers construidos sobre `AbstractC11350Yn` (`setWriteAheadLoggingEnabled(true)`) | `AbstractC11350Yn`; checkpoint mediante `PRAGMA wal_checkpoint(FULL)` |
| msgstore se abre con `PRAGMA synchronous=NORMAL`, `cache_size` opcional (flag **20777**), `PRAGMA secure_delete=1` | `C06980Hc.onOpen`; el fallo al habilitar secure_delete se reporta como `db-integrity/enable-secure-delete/error/not-enabled` |
| `PRAGMA foreign_keys=ON` se establece para sync.db, paa.db, daily_metrics.db, no para msgstore.db | `AbstractC12530bK`, `AbstractC197088a3`, `AbstractC16650iN`; msgstore hace cascadas mediante triggers (2.3) |

---

## 2. Bases de datos SQLite

### 2.1 Inventario

Los nombres de archivo son literales (`getDatabasePath(...)` / constructores de helpers). Los conteos de tablas son el número de clases de definición de tabla en el módulo DI que alimenta al helper (2.3).

| Archivo | Helper / módulo (2.26.41.6) | Versión / migración | Clases de tabla | Rol | Tier |
|---------|-----------------------------|---------------------|-----------------|-----|------|
| `msgstore.db` | `C06980Hc` (factory `C0HH`) | `user_version` de SQLite fijo en 1; huella del esquema en `props` (2.4) | 306 (factory `C1S0`) | mensajes, chats, JIDs, recibos, llamadas, newsletters, integridad, AI, TEE | found / atribución del conjunto inferred |
| `wa.db` | `C12650bW` | **95** (`creating contacts database version 95`) | 88 (implementadores de `C8ZL`) | contactos, listas de bloqueo, perfiles de negocio, tokens de contactos de confianza, señales de integridad | found |
| `axolotl.db` | `C44861sL`, tablas `AbstractC11250Yd` | **40** | 15 | sesiones Signal, prekeys, sender keys, colas de stanzas | found |
| `sync.db` | `AbstractC12530bK` (helper `X.1sK`) | migraciones `ALTER` escalonadas hasta al menos v50; downgrade = reset | 10 | app-state sync, history sync, mensajes peer | found, versión unknown |
| `status.db` | `C41891nD` | **2** (`StatusDbHelper creating status database version 2`) | 29 (`AbstractC11620Zo`) | publicaciones de estado e interacciones | found |
| `backup.db` | `C44881sN` | **1** | `backups`, `backup_props` | contabilidad de backups; `backup_props` contiene `wa_db_schema_version` | found |
| `chatsettings.db` | `C11200Xy("chatsettings.db")` | unknown | `settings` (inferred) | silencio, fijado, tono, fondo de pantalla, tema por chat | nombre found, tabla inferred |
| `stickers.db` | módulo `AbstractC149676Ty` | unknown | 18 (el módulo también registra `offloaded_media*`, `backups`, `backup_props`) | paquetes de stickers | found |
| `offloaded-media.db` | `CMN` (componente de backup) | unknown | `offloaded_media`, `offloaded_media_staging` (atribución inferred) | índice de media descargada del dispositivo | found / inferred |
| `payments.db` | helper anónimo `C1S0`, `AbstractC22520tH` | **5** | `contacts`, `methods`, `receipts`, `tmp_transactions` | métodos de pago | found |
| `commerce.db` | `C27743C3e` | unknown | unknown | datos de comercio; tiene una variante de backup `commerce_backup.db` | nombre found |
| `companion_devices.db` | `C48701zE` | **27** | `devices` (+ otras) | dispositivos vinculados vistos desde el primario | found |
| `paa.db` | `ManagedAccountDbHelper` (`AbstractC197088a3`) | migraciones V1 a V7 | `paa_connection`, `contact_metadata`, `group_metadata` | datos de cuenta administrada (cuenta aprobada por los padres) | found |
| `daily_metrics.db` | `AbstractC16650iN` | unknown | `poll_event_logging`, `poll_daily_participant`, `comments_event_logging`, `pnh_daily_event_logging`, `community_home_action_logging`, `snapl_payload` | contadores diarios de eventos | found |
| `qp_payload.db`, `location.db`, `fa_events.db`, `media.db`, `account_switcher.db` | getters de ruta (`C23985AVo`, `C33961Wh`) | unknown | unknown | promociones rápidas, ubicación en vivo, analítica federada, jobs de media (inferred), lista de cuentas | nombre found |
| `sqlite_vec.db` | `MessageEmbeddingsStore` | unknown | tablas vectoriales (unknown) | embeddings de mensajes en el dispositivo; presente solo si está habilitado | found |
| `emojidictionary.db`, `hsmpacks.db`, `events.db` | `C8JP`, `C6UR` | unknown | unknown | diccionario de emojis, paquetes de plantillas, eventos | nombre found |
| `wa-backup.db`, `msgstore.db-backup` | `CMN` / `C26042BNa`, `C0KE` | n/a | n/a | copias de seguridad locales de wa.db / msgstore | found |
| `migration_prefetcher.db`, `migration_import_metadata.db`, `migration_export_metadata.db` | `C23985AVo` | unknown | unknown | estado de transferencia de chats / migración de OS; `migration_prefetcher.db` es eliminado por `C28152CMi` | nombre found |
| `androidx.work.workdb` | WorkManager (`no_backup/`) | Room | estándar | cola de jobs | inferred a partir de clases Room (`room_master_table`) |

### 2.2 Qué DB contiene las tablas citadas en otros reportes

| Tabla | Archivo DB | Clase de tabla | Evidencia | Reporte |
|-------|-----------|----------------|-----------|---------|
| `wa_trusted_contacts`, `wa_trusted_contacts_send` | `wa.db` | `C23627AHs`, `C23628AHt` (`C8ZL`) | el helper de wa.db las recrea; los stores se leen mediante `C12810bn` del helper de wa.db | [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_biz_integrity_signals` | `wa.db` | `C53116Nmn` (`C8ZL`) | found | [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 5.1 |
| `start_chat_trust_signals` | `wa.db` | `AI0` (`C8ZL`), trigger sobre `wa_contacts` | found | reporte de ban 5.2 |
| `integrity_chat_info` | `msgstore.db` | `C08970Ox`, trigger `chat_bd_for_integrity_chat_info_trigger` sobre `chat` | found, atribución por la FK a `chat` | reporte de ban 5.3 |
| `meta_ai_memory` | **`wa.db`** | `C23621AHm` (`C8ZL`) | found; columnas `memory_id`, `memory_content`, `bot_jid_row_id` | [WA_META_AI.md](WA_META_AI.md) |
| `bot_memory_metadata`, `bot_chat_info`, `ai_thread_info` | `msgstore.db` | `C08640Nq`, `C08610Nn`, `C0MO` | en el conjunto de 306 clases | reporte de Meta AI |

`meta_ai_memory` está en `wa.db`, no en `msgstore.db`: su clase implementa `C8ZL`, que solo el helper de wa.db itera (`C12650bW.onCreate` con `new C08050Lj("wa.db")`). `bot_jid_row_id` referencia una fila `jid` de msgstore, por lo que la columna es una referencia suave entre bases de datos (inferred; no es posible una foreign key entre archivos).

### 2.3 Framework de tablas (cómo se definen los esquemas)

Las tablas no se escriben como strings SQL. Cada tabla es una clase que implementa `InterfaceC08060Lk` (wa.db: la subinterfaz `C8ZL`) con tres hooks (found):

| Hook | Propósito |
|------|-----------|
| `ASa(ctx, builder)` | declara columnas: builder `C08080Lm`, `.A02` = nombre, `.A00` = tipo `EnumC08100Lo` (`INTEGER`, `TEXT`, `REAL`, `BLOB`, `LONG`, ...), flags de clave primaria / not null / default |
| `ASX(ctx, builder)` | declara índices (`CRN`, `CRJ` = índice condicional) |
| `ASc(builder)` | declara triggers (`CRg`, `CRf`) |

- 422 clases implementan `InterfaceC08060Lk` y 88 más implementan `C8ZL`. Se proveen en conjuntos DI; cada helper itera su conjunto (`C06980Hc.A03`, `C12650bW.onCreate`, `C44881sN`, `C41891nD`).
- Los borrados en cascada son triggers, no foreign keys: `AbstractC08210Lz.A01` construye `CREATE TRIGGER <parent>_bd_for_<child>_trigger BEFORE DELETE ON <parent> BEGIN DELETE FROM <child> WHERE ...; END` (found; ejemplo: `message_add_on_reaction` se elimina cuando se van las filas de `message_add_on`).
- Las listas de columnas a continuación se extraen de `ASa` en el orden declarado. El decompilador omite algunas columnas construidas por helpers (primera columna de unas pocas tablas, valores default); estas se marcan como "(+ jid)" cuando una consulta o trigger prueba la columna. Los tipos se indican solo cuando el código los establece.
- La atribución a DB de las 306 clases de msgstore se hace por la factory DI `C1S0` (306 llamadas `new`, incluye `message`, `chat`, `jid`) y por los triggers FK hacia `chat` / `message` / `jid` (inferred). Existen tablas con el mismo nombre en dos módulos (`status`, `status_attribution`, `mms_thumbnail_metadata`, `quick_promotion_payload`: msgstore y status.db o wa.db tienen cada uno una clase).

### 2.4 Versionado y migraciones

| DB | Estrategia (found) |
|----|--------------------|
| `msgstore.db` | `onUpgrade` = `onCreate`; `setVersion(1)` siempre. La versión real es un hash almacenado en la tabla `props`: `msgtore_db_schema_version` y `msgtore_db_schema_indexes_version` = `Arrays.hashCode` sobre una etiqueta literal `Consumer-<hex>` y `MessageSchemaConfig=1;isGlobalChatDbMigrated=<bool>[;includeNewsletterInteractionTable=true]` (`C06980Hc.A04`). Declarativo: tablas e índices son `CREATE ... IF NOT EXISTS` a partir del conjunto de clases. Otras claves de `props`: `MessagesDBHelper_RestoredIndexesPending`, `MessagesDBHelper_CreateAsyncIndexesV2`, `..FailedAttempts` |
| `wa.db` | `onUpgrade` es un switch sobre la versión anterior 3 a 94 que en su mayoría elimina tablas recreadas después; una versión anterior desconocida cae en `onCreate`; downgrade = `onCreate`. `wa_db_schema_version` se escribe con una etiqueta `ConsumerBeta-<hex>`. El pref `force_wadb_check` (startup_prefs) fuerza una nueva verificación. wa.db son datos reconstruibles (contactos, tokens, cachés) |
| `axolotl.db` | versionada (40); variantes antiguas del DDL visibles en `C44861sL` (p. ej. `identities` ganó `recipient_type`, `next_kyber_prekey_id`, `account_encryption_attestation_type`; `sessions` ganó `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope`; `sender_keys` ganó `bucket_id`) |
| `sync.db` | `ALTER TABLE ... ADD` escalonados (p. ej. `collection_versions.dirty_version`, `history_sync_companion.inline_payload`, `msg_history_sync.size_limit_bytes`); downgrade o versión desconocida llama a `sync-db-helper/reset`, que recrea las tablas, por lo que el app state se resincroniza (inferred) |
| `status.db` | v2; fila `schema_version` de `key_value_store` |
| `paa.db` | `runMigrationV1`..`V7` (agrega columnas como `age_experience`, `snooze_status`, `common_groups_count`) |
| backups (`BD0`) | los metadatos de crypt15 aún contienen flags de "migración terminada" por tabla (`message_main`, `receipt_user`, `jid_store`, ...), el historial de las antiguas migraciones de msgstore (7.2) |

---

## 3. msgstore.db: tablas y columnas clave

### 3.1 Familias de tablas (found, 306 clases)

| Familia | Tablas (ejemplos) |
|---------|-------------------|
| Identidad | `jid`, `jid_map`, `lid_chat_state`, `lid_display_name`, `jid_user_metadata`, `integrator_display_name` |
| Chat | `chat`, `chat_ephemeral`, `chat_encryption_classification`, `community_chat`, `broadcast_chat_details`, `thread_messages`, `thread_id`, `draft_message_reminder` |
| Núcleo de mensajes | `message`, `message_text`, `message_media`, `message_quoted*` (14), `message_edit_info`, `message_revoked`, `message_forwarded`, `message_mentions`, `message_link`, `message_future`, `message_orphan`, `message_send_count`, `message_view_once_media`, `message_ephemeral*` |
| Mensajes de sistema | `message_system` + unas 35 tablas de detalle `message_system_*` (group, number_change, lid_change, username_change, device_change, privacy, ...) |
| Add-ons | `message_add_on` y `message_add_on_reaction`, `_poll_vote`, `_poll_vote_selected_option`, `_keep_in_chat`, `_pin_in_chat`, `_question_response`, `_event_response`, `_receipt_device`, `_receipt_coex`, `_status_*` |
| Recibos | `receipt_user`, `receipt_device`, `receipt_coex`, `receipt_orphaned`, `played_self_receipt`, `optimised_delivery_info` |
| Grupos | `group_participant_user`, `group_past_participant_user`, `group_participant_device`, `parent_group_participants`, `group_history_*`, `group_root_key_mapping`, `group_notification_version` |
| Dispositivos | `user_device`, `user_device_info`, `primary_device_version`, `agent_devices` |
| Media | `media_hash_thumbnail`, `media_content`, `mms_metadata`, `mms_thumbnail_metadata`, `extended_media_data`, `message_media_map`, `message_streaming_sidecar`, `media_refs`, `message_thumbnail`, `audio_data`, `voice_data` |
| Llamadas | `call_log`, `call_log_participant_v2`, `joinable_call_log`, `missed_call_logs`, `bcall_session`, `call_link`, `scheduled_calls` |
| Newsletters | `newsletter`, `newsletter_message`, `newsletter_message_reaction`, `newsletter_admin_profile`, `newsletter_subscribers`, `newsletter_pinned_message`, `newsletter_interaction` |
| Encuestas / eventos / etiquetas | `message_poll`, `message_poll_option`, `poll_vote_*`, `event*`, `labels`, `labeled_jid`, `favorite`, `quick_replies*` |
| Pagos / comercio | `pay_transaction`, `payment_*`, `message_payment*`, `message_order`, `message_product`, `cart_item` |
| Integridad / reportes | `integrity_analysis_result`, `integrity_chat_info`, `integrity_input_feature`, `integrity_deleted_chat_*`, `message_quarantine`, `message_structure_analysis_result`, `reporting_info(_content)`, `scam_alert_events` |
| AI / TEE | `ai_thread_info`, `ai_rich_response_message_*`, `bot_*`, `agent_*`, `auth_agent_chat_metadata`, `tee_chat_request_table`, `tee_message_info_table`, `private_ai_*`, `embeddings_deletion_log` |

### 3.2 Identidad: jid, mapeo LID

| Tabla | Columnas (orden declarado) | Notas |
|-------|----------------------------|-------|
| `jid` | `_id` (PK AUTOINCREMENT), `user`, `server`, `agent`, `device`, `type`, `raw_string` | índice único `jid_key_new_index` sobre (`user`,`server`,`agent`,`device`,`type`), único `jid_raw_string_index` sobre `raw_string`. `JidStore` (`C0W4`) escribe `jid.getType()` / `getRawString()`. Toda otra tabla refiere un JID mediante `*_jid_row_id` = `jid._id` |
| `jid_map` | `lid_row_id`, `jid_row_id`, `sort_id` | fila LID a fila JID de número de teléfono (superficie de migración LID; trigger sobre `lid_row_id`) |
| `lid_chat_state` | `jid_row_id`, `is_pn_shared`, `pn_requested_ts`, `pnh_duplicate_lid_thread` (+ columnas solo con default) | estado del compartir número de teléfono por chat LID |
| `lid_display_name` | `lid_row_id`, `display_name`, `username` | el username mostrado para un contacto LID, ver [WA_USERNAME.md](WA_USERNAME.md) |

### 3.3 chat

`chat` (`C0OM`), 57 columnas declaradas. Índice único `chat_account_jid_row_id_unique_index` sobre `account_jid_row_id`.

| Grupo | Columnas |
|-------|----------|
| Clave | `_id`, `jid_row_id`, `account_jid_row_id` (cuenta propietaria; nueva con multi-cuenta / LID), `chat_origin` |
| Visualización | `subject`, `created_timestamp`, `hidden`, `archived`, `sort_timestamp`, `group_type`, `group_member_count`, `is_contact`, `chat_lock` |
| Punteros hacia `message` | `display_message_row_id`, `last_message_row_id`, `last_read_message_row_id`, `last_read_receipt_sent_message_row_id`, `last_important_message_row_id`, `change_number_notified_message_row_id`, más variantes `*_sort_id` y `last_message_reaction_row_id`, `last_seen_message_reaction_row_id` |
| Contadores de no leídos | `unseen_message_count`, `unseen_important_message_count`, `unseen_missed_calls_count`, `unseen_row_count`, `unseen_message_reaction_count`, `unseen_comment_message_count`, `unseen_earliest_message_received_time` |
| Efímeros | `ephemeral_expiration`, `ephemeral_setting_timestamp`, `ephemeral_displayed_exemptions`, `ephemeral_disappearing_messages_initiator`, `ephemeral_after_read_duration` |
| Crypto / política | `plaintext_disabled`, `chat_encryption_state`, `limited_sharing`, `limited_sharing_setting_timestamp`, `growth_lock_level`, `growth_lock_expiration_ts`, `spam_detection`, `business_chat_state`, `participation_status`, `history_sync_progress`, `chat_props` |

### 3.4 message y satélites

`message` (`C09540Re`), 24 columnas; índice único `message_key_index` sobre (`chat_row_id`,`from_me`,`key_id`,`sender_jid_row_id`).

| Columna | Uso |
|---------|-----|
| `_id` | id de fila, referenciado como `message_row_id` en todas partes |
| `chat_row_id`, `sender_jid_row_id` | chat, remitente (`jid._id`) |
| `from_me`, `key_id` | parte de la clave del mensaje (id del stanza) |
| `status`, `broadcast`, `recipient_count`, `participant_hash` | estado de entrega y resumen del fan-out de grupo |
| `origination_flags`, `origin`, `view_mode`, `sort_id` | origen y ordenamiento |
| `timestamp`, `received_timestamp`, `receipt_server_timestamp`, `server_sts` | tiempos |
| `message_type`, `text_data`, `translated_text` | tipo y cuerpo de texto plano (el texto vive en la propia fila) |
| `starred`, `view_replies_thread_id` | flags |
| `lookup_tables`, `message_add_on_flags` | bitmasks que indican qué tablas satélite contienen filas (inferred a partir de nombres y uso) |

| Satélite | Columnas clave |
|----------|----------------|
| `message_text` | `message_row_id`, `description`, `page_title`, `url`, `font_style`, `text_color`, `background_color`, `preview_type`, `invite_link_group_type`, `counter_abuse_token`, `link_end_index` |
| `message_quoted` | `message_row_id`, `chat_row_id`, `parent_message_chat_row_id`, `from_me`, `sender_jid_row_id`, `key_id`, `timestamp`, `message_type`, `text_data`, `quoted_source`, `quoted_type` |
| `message_edit_info` | `message_row_id`, `original_key_id`, `edited_timestamp`, `sender_timestamp` |
| `message_revoked` | `message_row_id`, `revoked_key_id`, `admin_jid_row_id`, `revoke_timestamp` |
| `message_ephemeral` | `message_row_id`, `duration`, `expire_timestamp`, `keep_in_chat`, `ephemeral_trigger`, `ephemeral_initiated_by_me`, `after_read_duration` |
| `message_secret` | `message_row_id` (+ la columna del secreto, omitida por el decompilador): secreto por mensaje para el cifrado de add-ons (inferred) |
| `message_future` | `message_row_id`, `version`, `data`, `future_message_type`, `future_proof_stanza`, `edit_version`, `message_stanza_data` (mensaje no soportado conservado para más adelante) |
| `message_orphan` | `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_*`, `orphan_message_data`, `orphan_message_type`, `orphan_message_reason` (hijo que llegó antes que su padre) |
| `message_quarantine` | `message_row_id`, `chat_row_id`, `timestamp`, `original_protobuf`, `serialized_stanza`, `protobuf_type` |
| `reporting_info` | `message_row_id`, `reporting_tag`, `stanza_id`, `send_timestamp`, `receive_timestamp`, `stanza_id_text`, `receive_flow`, `is_message_add_on` (ver [WA_REPORTING.md](WA_REPORTING.md)) |
| `message_send_count` | `message_row_id`, `send_count` |

### 3.5 Recibos, reacciones, add-ons

| Tabla | Columnas | Notas |
|-------|----------|-------|
| `receipt_user` | `_id`, `message_row_id`, `receipt_user_jid_row_id`, `receipt_timestamp`, `read_timestamp`, `played_timestamp` | por destinatario (1:1 y grupo) |
| `receipt_device` | `_id`, `message_row_id`, `receipt_device_jid_row_id`, `receipt_device_timestamp`, `primary_device_version` | por dispositivo destinatario |
| `receipt_orphaned` | `_id`, `chat_row_id`, `from_me`, `key_id`, `receipt_device_jid_row_id`, `receipt_recipient_jid_row_id`, `status`, `timestamp` | recibo anterior a su mensaje |
| `message_add_on` | `_id`, `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_message_row_id`, `timestamp`, `status`, `message_add_on_type`, `received_timestamp`, `expiry_duration_in_secs`, `server_timestamp`, `expiry_timestamp`, `expiry_type` | una fila por reacción / voto / pin / keep; la clave única es (`chat_row_id`,`key_id`,`from_me`) en la consulta de búsqueda |
| `message_add_on_reaction` | `message_add_on_row_id` (PK), `reaction`, `sender_timestamp` | índice parcial `message_add_on_reaction_empty_reaction_index` sobre `reaction = ''` (string vacío = reacción eliminada, inferred) |
| `message_poll` | `message_row_id`, `enc_key`, `selectable_options_count`, `invalid_state`, `poll_logging_id`, `poll_type`, `correct_option_id`, `content_type`, `hide_participant_names`, `end_time`, `allow_add_option` | |

`C09010Pb.A00` es el conjunto de columnas de add-on; `AbstractC41651mo.A01` selecciona el conjunto de columnas según el id de tipo de add-on: 56 = reacción (`C0PV`), 67 = voto de encuesta (`C0PT`), otros 68, 74, 79, 86, 93, 121, 122, 125 (found: el switch; su significado no fue rastreado).

### 3.6 Grupos y participantes

| Tabla | Columnas |
|-------|----------|
| `group_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `add_timestamp`, `label`, `join_method`, `group_history_send_state` |
| `group_past_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `is_leave`, `timestamp` |
| `group_participant_device` | `_id`, `group_participant_row_id`, `device_jid_row_id`, `sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket` (estado de distribución de sender keys por dispositivo) |
| `group_root_key_mapping` | `_id`, `group_jid_row_id`, `key_id`, `is_current` |
| `feature_key_store` | `_id`, `key_id`, `key_jid`, `key`, `key_type`, `creation_timestamp`, `expiry_timestamp` |

Los ajustes a nivel de grupo (solo administradores, anuncios, efímeros, aprobación de membresía, toggles de historial) están en **wa.db** `wa_group_admin_settings`, no aquí (4.3). Historial de grupo: [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md).

### 3.7 Dispositivos

| Tabla | Columnas |
|-------|----------|
| `user_device` | `_id`, `user_jid_row_id`, `device_jid_row_id`, `key_index` |
| `user_device_info` | `user_jid_row_id`, `raw_id`, `timestamp`, `expected_timestamp`, `expected_ts_last_device_job_ts`, `expected_timestamp_update_ts`, `account_encryption_type` (estado ADV por usuario) |

### 3.8 Media, miniaturas, sidecar

| Tabla | Columnas | Nota |
|-------|----------|------|
| `message_media` | `message_row_id`, `chat_row_id`, `file_path`, `file_size`, `file_length`, `mime_type`, `media_name`, `media_key`, `media_key_timestamp`, `e2ee_media_key`, `file_hash`, `enc_file_hash`, `partial_media_hash`, `partial_media_enc_hash`, `original_file_hash`, `direct_path`, `message_url`, `metadata_url`, `media_duration`, `width`, `height`, `transferred`, `transcoded`, `is_offloaded`, `media_job_uuid`, `media_upload_handle`, `has_streaming_sidecar`, `media_caption`, `media_source_type`, `suspicious_content` | 55 columnas declaradas; `file_path` se almacena relativo a la raíz de media (`C0KE.A0A` elimina el prefijo de la raíz, found). Campos de subida / descarga: [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| `message_thumbnail` | `message_row_id`, `thumbnail` | bytes de la miniatura dentro de la DB |
| `message_streaming_sidecar` | `message_row_id`, `sidecar`, `chunk_lengths`, `timestamp` | sidecar de streaming (datos MAC de chunks para reproducción progresiva) en la DB, no como archivo |
| `media_hash_thumbnail` | `media_hash`, `thumbnail` | miniatura indexada por hash de contenido |
| `media_refs` | `_id`, `path`, `ref_count` | conteo de referencias por ruta de archivo |
| `mms_thumbnail_metadata` | `message_row_id`, `direct_path`, `media_key`, `media_key_timestamp`, `enc_thumb_hash`, `thumb_hash`, `thumb_width`, `thumb_height`, `transferred`, `micro_thumbnail`, `insert_timestamp`, `handle` | |
| `extended_media_data` | `row_id`, `type`, `external_url`, `direct_path`, `preview_path`, `file_path`, `file_hash`, `media_key`, `enc_file_hash`, `mime_type`, `display_type` | |
| `offloaded_media` (offloaded-media.db) | `file_path`, `content_hash`, `file_size`, `media_source`, `media_state`, `is_offloadable`, `latest_reference_timestamp`, `refetch_timestamp`, `file_key` | |

### 3.9 Llamadas

| Tabla | Columnas |
|-------|----------|
| `call_log` | `_id`, `jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch` |
| `call_log_participant_v2` | `_id`, `call_log_row_id`, `jid_row_id`, `call_result` |

Señalización de llamadas: [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md). Las tablas de newsletters (`newsletter`, `newsletter_message`, 45 y 17 columnas) solo se listan en 3.1.

### 3.10 Vistas y tablas de integridad / AI

Vistas creadas en `C06980Hc.A0C` (found): `available_message_view`, `deleted_messages_view`, `deleted_messages_ids_view`, `chat_view` (dos variantes, elegidas por `isGlobalChatDbMigrated`).

| Tabla | Columnas |
|-------|----------|
| `integrity_chat_info` | `chat_row_id` (PK), `is_reach_out`, `is_eligible_for_link_friction_banner` |
| `integrity_analysis_result` | `chat_row_id`, `last_message_row_id`, `result`, `timestamp`, `animation_played`, `trusted_timestamp`, `view_timestamp`, `holdout_group`, `experiment_group`, `chatting_untrusted_timestamp`, `replied_timestamp`, `block_logged_timestamp`, `trust_logged_timestamp`, `report_logged_timestamp` |
| `integrity_input_feature` | `chat_row_id`, `sender_reputation`, `country_mismatch`, `fetched_timestamp` |
| `tee_chat_request_table` | `message_row_id`, `chat_request_type`, `anchor_message_row_id`, `node_token`, `extra_data` |
| `tee_message_info_table` | `message_row_id`, `message_interaction_type`, `message_outgoing_status`, `message_source`, `message_replay_metadata` |
| `ai_thread_info` | `thread_id_row_id`, `title`, `creation_ts`, `variant`, `last_thread_messages_row_id`, `last_message_timestamp`, `title_source`, `unseen_message_count`, `origin_chat_row_id`, `selected_mode`, `selected_modes` |
| `bot_chat_info` | `chat_row_id`, `welcome_request_message_sent`, `bot_metrics_thread_origin` |
| `bot_memory_metadata` | `_id`, `message_row_id`, `memory_annotated_user_message_key_id`, `memory`, `memory_id`, `added`, `bot_jid_row_id` |

---

## 4. wa.db: contactos, listas de bloqueo, datos de confianza

### 4.1 Familias (found, 88 clases)

| Familia | Tablas |
|---------|--------|
| Contactos | `wa_contacts`, `wa_contact_details`, `wa_contacts_created_within_wa`, `wa_contacts_pending_operations`, `wa_contact_refresh_pending`, `wa_contact_refresh_patch_log`, `wa_contact_storage_usage`, `wa_address_book`, `wa_org_contacts`, `wa_orgs`, `system_contacts_version_table` |
| Listas de bloqueo / permitidos | `wa_block_list`, `wa_block_list_interop`, `wa_last_seen_block_list`, `wa_profile_photo_block_list`, `wa_about_block_list`, `wa_pix_block_list`, `wa_cover_photo_block_list`, `wa_status_view_allow_list`, `wa_status_view_black_list`, `wa_group_add_allow_list`, `wa_group_add_black_list`, `wa_stickers_allow_list`, `wa_profile_links_deny_list` |
| Negocio | `wa_biz_profiles` + 12 tablas de detalle `wa_biz_profiles_*` / `wa_biz_*`, `wa_vnames`, `wa_vnames_localized` |
| Grupos | `wa_group_admin_settings`, `wa_group_descriptions`, `group_membership_approval_requests`, `non_admin_group_membership_approval_requests`, `group_membership_count`, `group_membership_form_questions`, `group_relationship`, `subgroup_info`, `community_settings`, `member_suggested_groups_v2`, `group_suspension_appeal`, `group_non_wa_invites` |
| Confianza / integridad | `wa_trusted_contacts`, `wa_trusted_contacts_send`, `wa_biz_integrity_signals`, `wa_biz_integrity_chat_settings`, `start_chat_trust_signals`, `wa_contact_server_signals` |
| Configuración | `wa_props`, `wa_newsletter_props`, `wa_coex_properties`, `wa_ml_models`, `wa_last_entry_point`, `wa_logging_entry_point` |
| AI / bots | `meta_ai_memory`, `wa_bot_profiles`, `wa_bot_commands`, `wa_subscriptions` |
| Otras | `status_ranking(_global)`, `wa_chat_ranking_scores`, `wa_storage_monitoring_data/_jobs`, `inbound_/outbound_connection_requests`, `dismissed_*`, `quick_promotion_payload` |

### 4.2 wa_contacts

36 columnas (`Nn5`), con clave `jid` (TEXT, string JID crudo; un JID de teléfono o un JID `@lid`, no un id de fila `jid`):

`jid`, `is_whatsapp_user`, `status`, `status_timestamp`, `number`, `raw_contact_id`, `display_name`, `phone_type`, `phone_label`, `photo_ts`, `thumb_ts`, `photo_id_timestamp`, `given_name`, `family_name`, `wa_name`, `sort_name`, `nickname`, `company`, `title`, `status_autodownload_disabled`, `keep_timestamp`, `is_spam_reported`, `is_sidelist_synced`, `is_business_synced`, `disappearing_mode_duration`, `disappearing_mode_timestamp`, `disappearing_mode_support_disabled`, `history_sync_initial_phash`, `is_starred`, `is_wa_created_contact`, `sync_policy`, `status_emoji`, `is_contact_synced`, `is_reachable`, `external_user_state`, `fts_dirty_version`.

`wa_name` es el push name que estableció el contacto; `display_name` / `given_name` provienen de la libreta de direcciones. Varias tablas satélite usan triggers `BEFORE DELETE ON wa_contacts` (p. ej. `start_chat_trust_signals_contact_delete`, `contact_bd_for_business_integrity_signals`).

### 4.3 Otras tablas de wa.db

| Tabla | Columnas |
|-------|----------|
| `wa_trusted_contacts` | (+ `jid`), `incoming_tc_token` BLOB, `incoming_tc_token_timestamp` LONG. Ver [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_trusted_contacts_send` | (+ `jid`), `sent_tc_token_timestamp` LONG, `real_issue_timestamp` LONG |
| `wa_biz_integrity_signals` | 17 columnas: `_id`, `jid`, `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `is_suspicious`, `join_date_ms`, `is_banned`, `phone_country_code`, `trust_tier`, `is_meta_verified`, `mv_friction_eligibility`, `integrity_tags`, `chat_row_id`, `last_sync_ts`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Semántica completa en el reporte de ban 5.1 |
| `start_chat_trust_signals` | (+ `jid`), `is_sender_suspicious`, `is_sender_new_account`, `created_ts` REAL |
| `meta_ai_memory` | `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER; índice `meta_ai_memory_memory_content_index` sobre `memory_content` |
| `wa_contact_server_signals` | `chat_jid`, `signal_type`, `value`, `update_ts` |
| `wa_group_admin_settings` | `jid`, `restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `creator_jid`, `is_suspended`, `group_state`, `require_membership_approval`, `member_add_mode`, `addressing_mode`, `history_enabled`, `group_history_toggle_mode`, `share_group_history_setting_mode`, `earliest_group_history_message_timestamp_ms`, `allow_member_labels`, ... (31 columnas) |
| `wa_storage_monitoring_data` | `db_name`, `table_name`, `table_size_bytes`, `index_size_bytes`, `table_unused_bytes`, `index_unused_bytes` (el cliente mide los tamaños de sus propias tablas; ver 10.3) |

---

## 5. axolotl.db (estado Signal)

DDL actual (últimas variantes en `C44861sL`, tablas registradas por `AbstractC11250Yd`; found). El material de claves se almacena en columnas BLOB `record`; aquí no se documentan bytes de claves.

| Tabla | Columnas | Rol |
|-------|----------|-----|
| `identities` | `_id`, `recipient_id`, `recipient_type`, `device_id`, `registration_id`, `public_key`, `private_key`, `next_prekey_id`, `next_kyber_prekey_id`, `timestamp`, `account_encryption_attestation_type`, `mark_as_verified`, `mark_as_verified_action_seq`, ... | fila de identidad propia e identidades remotas (`recipient_type` separa cuentas de teléfono y LID) |
| `sessions` | `_id`, `device_id`, `record`, `timestamp`, `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope` | sesiones Double Ratchet |
| `prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `key_type` | prekeys de un solo uso |
| `signed_prekeys` | `_id`, `prekey_id` UNIQUE, `timestamp`, `record`, `key_type` | |
| `kyber_prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `last_resort_key` | prekeys post-cuánticas |
| `prekey_uploads` | `_id`, `upload_timestamp`, `key_type` | |
| `sender_keys` | `_id`, `group_id`, `device_id`, `record`, `timestamp`, `sender_account_id`, `sender_account_type`, `bucket_id` | sender keys de grupo |
| `message_base_key` | `_id`, `msg_key_remote_jid`, `msg_key_from_me`, `msg_key_id`, `recipient_id`, `recipient_type`, `device_id`, `last_alice_base_key`, `timestamp` | |
| `chat_stanza_queue`, `e2ee_stanza_queue`, `unordered_stanza_queue`, `preacks`, `stanza_sts` | `stanza_id`, `stanza_key` UNIQUE, `stanza_class`, `chat_jid`, `sender_jid`, `stanza_payload`, ... | persistencia de stanzas entrantes antes de descifrar |

La capa Java del store de Signal es código al estilo `signal_protocol_store` sobre estas tablas. Los prefs criptográficos a nivel de cuenta viven en `keystore.xml` y `wacrypto.xml` (8.3), no aquí.

---

## 6. sync.db, companion_devices.db y las bases de datos menores

| DB | Tablas y columnas clave |
|----|-------------------------|
| `sync.db` | `syncd_mutations` (`mutation_index` UNIQUE, `mutation_value` BLOB, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name`), `pending_mutations` (igual más `operation`, `is_ready_to_sync`), `collection_versions` (`collection_name` PK, `version`, `lt_hash` BLOB, `dirty_version`), `crypto_info` (`device_id`, `epoch`, `key_data`, `timestamp`, `fingerprint`, `stale_timestamp`), `missing_keys`, `msg_history_sync`, `history_sync_companion`, `peer_messages`, `placeholder_retry_message`, `rmr_response_error`. Protocolo: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md) |
| `companion_devices.db` | `devices`: `device_id`, `device_os`, `platform_type`, `last_active`, `login_time`, `logout_time`, `adv_key_index`, `full_sync_required`, `place_name`, `nickname`, ... Protocolo: [WA_LINKED_DEVICE_PAIRING.md](WA_LINKED_DEVICE_PAIRING.md) |
| `status.db` | `status`, `status_text`, `status_thumbnail`, `status_info`, `status_interactions`, `status_interactions_totals`, `status_seen_receipt`, `status_receipt_device`, `status_reply`, `status_send_part`, `status_privacy_custom_list`, `status_crossposting_v2/_v3`, ... más `key_value_store` (`row_id`, `key`, `value`) |
| `backup.db` | `backups`, `backup_props` (`prop_name`, `prop_value`; fila `wa_db_schema_version`) |
| `chatsettings.db` | `settings`: `_id`, `jid`, `deleted`, `mute_end`, `muted_notifications`, `use_custom_notifications`, `message_tone`, `call_tone`, `status_muted`, `pinned`, `pinned_time`, `media_visibility`, `mute_reactions`, `wallpaper_*`, `auto_delete_media`, `transcription_locale`, `source_lang`, `target_lang`, `snooze_end_time`, `theme_id` (39 columnas) |
| `stickers.db` | `stickers` (`plain_file_hash`, `encrypted_file_hash`, `media_key`, `mime_type`, `sticker_pack_id`, `file_path`, `url`, `direct_path`, `emojis`, `is_lottie`, ...), `recent_stickers`, `starred_stickers`, `installed_sticker_packs`; `payments.db`: `methods` (`credential_id` PK, `country`, `issuer_name`, `type`, `balance_1000`), `contacts`, `receipts`, `tmp_transactions` |

---

## 7. Backups y crypt15

### 7.1 Archivos de backup locales

| Patrón de nombre (found, `AbstractC26994Bml`, `C29412Cpb`) | Contenido |
|------------------------------------------------------------|-----------|
| `msgstore.db.crypt15`, `msgstore.db.crypt14` | backup completo de la base de datos de chats (regex `msgstore.db.crypt(\d+)`) |
| `msgstore-increment-<N>.db.crypt<V>` | backup incremental |
| `backup_settings.json.crypt<V>`, `status_backup.db.crypt<V>`, `commerce_backup.db.crypt<V>`, `chat_transfer_settings.json.crypt<V>` | ajustes, estados, comercio, ajustes de transferencia de chats |
| `stickers.db.crypt<V>`, `chatsettingsbackup.db`, `wa-backup.db` | backups de stickers / ajustes de chat / wa.db (nombres de componentes abajo) |

La raíz es `Backups/` bajo la raíz de media externa (`C0KE.A02`; legado `Databases/`, `C0KE.A03`). La raíz se elige mediante el pref `external_storage_type` (el valor `scoped` se verifica en `C11160Xu.A07`; otros valores no enumerados); `EnumC046905z` puede resolver a `getExternalMediaDirs()[0]`, `getExternalStorageDirectory()`, directorios externos específicos de la app o los directorios internos. Las cuentas secundarias usan `<root>/accounts/<dirId>` para rutas `Media/WhatsApp ...` (`C0KE.A00`).

Componentes de backup (nombres `A0F` en subclases de `CMN`, found): `stickers`, `stickers-db`, `wallpapers`, `payment-backgrounds-v2`, `chat-transfer`, `wa-db`, `commerce-db`, `status_db`, `offloaded-media.db`, `chatlock_backup`, `chat-settings`, `backup-settings`. `backup_prefs` conserva `<component>_backup_size` / `_backup_status` por componente (8.3).

Categorías de media en la UI de backup (`EnumC26330BbW`, 17 valores): `CHAT_DB`, `SETTINGS`, `STATUS_DB`, `COMMERCE_DB`, `OTHER_DB`, `IMAGES`, `VIDEOS`, `AUDIO`, `VOICE_NOTES`, `VIDEO_NOTES`, `GIFS`, `DOCUMENTS`, `STICKERS`, `STICKER_PACKS`, `PROFILE_PHOTOS`, `EXCLUDED_STICKERS`, `OTHER`.

### 7.2 Prefijo del archivo crypt15 (found)

`EnumC26325BbR`: `UNENCRYPTED` 0, `CRYPT14` 14, `CRYPT15` 15 (un sufijo `.crypt` sin número es la forma antigua; `CKv` coincide con `.crypt`). El lector de crypt15 (`BN4.A09`) analiza un protobuf delimitado `BackupPrefix` (`BCE`) antes del texto cifrado:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `key_type_deprecated` | **1** | enum | tipo de clave antiguo |
| `wa_provided_key_data` | **2** | bytes | datos de clave para claves provistas por el servidor |
| `e2ee_key_data` | **3** | message | datos de clave para backup cifrado de extremo a extremo |
| `backup_metadata` | **4** | `BD0` | ver abajo |
| `passkey_encryption_metadata` | **5** | message | ruta de passkey (`parsePasskeyEncryptionMetadata`) |
| `key_type_new` | **6** | enum | tipo de clave actual |

Tipos de clave (`BdX`): `WA_PROVIDED` 0, `E2EE_DEPRECATED` 1, `E2EE_PASSWORD` 2, `E2EE_ENCRYPTION_KEY` 3, `E2EE_PASSKEY` 4.

Campos de `BackupMetadata` (`BD0`) (selección): `app_version` **1**, `device_model` **2**, `jid_suffix` **3**, `backup_version` **4**, `backup_export_file_size` **38**, `cleaned_db` **39**, `backup_encrypted_hash_salt` **40**, `backup_encrypted_hash` **41**, `identifier_type` **42**, `lid_suffix` **43**, `display_suffix` **44**, más unos 30 booleanos `*_migration_finished` (números 5 a 35). Al restaurar, `EncBackupUtils` compara `jid_suffix` con el usuario registrado (`has-jid-user-mismatch`): un backup queda ligado a la cuenta que lo creó.

El cifrado, el KDF y el layout del MAC del texto cifrado no se leyeron aquí (unknown).

### 7.3 Material de clave de backup

| Archivo (en `files/`) | Contenido | Evidencia |
|-----------------------|-----------|-----------|
| `encrypted_backup.key` | clave raíz de 32 bytes del backup cifrado de extremo a extremo (`C29861Ep.A09`, longitud verificada == 32); escrita por `A04(...)`, posiblemente envuelta por una clave de encapsulación de KeyStore (`failed to load or create KeyStore encapsulation key`) | found |
| `encrypted_backup.key_id` | identificador de la clave | found |
| `password_data.key`, `passkey_data.key` | estado de las variantes de contraseña y passkey (los datos de passkey son JSON) | found |
| `vault_backup.key` | clave vault de 32 bytes, generada con `C00L.A0H(32)` y se niega a sobrescribir un archivo ilegible (`vault backup key present but could not be read`) | found |
| `prf_derived_root_key.key`, `secret_code.key` | clave raíz derivada por PRF de passkey, clave de código secreto | nombre found, contenido unknown |
| `backup_token`, `foa_backup_token` | archivo de token (`CMc`, variante `foa_` para la cuenta del centro de cuentas) | found |

`AbstractC29801Ej` elimina juntos `encrypted_backup.key(_id)`, `password_data.key`, `passkey_data.key`, `vault_backup.key` (reinicio de claves).

### 7.4 Auto-backup de Android y el provider de migración (found)

| Elemento | Valor |
|----------|-------|
| `android:allowBackup` | `true`, `fullBackupOnly=true`, backup agent `SystemBackupAgent` |
| `fullBackupContent` (`xml0003`) y `dataExtractionRules` (`xml0006`: cloud-backup y device-transfer) | excluyen **todos** los dominios (`root`, `file`, `database`, `sharedpref`, `external`, `device_*`). La plataforma no transfiere nada |
| `cross-platform-transfer platform="ios"` | declarado con el bundle id de iOS; la transferencia pasa por `OsMigrationAppDataService` (permiso `android.permission.BACKUP`) |
| `MigrationContentProvider` | exportado, `readPermission com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` (protectionLevel `signature`), `grantUriPermissions=false`. URIs: `msg_store`, `unencrypted_msg_store`, `wa_db`, `chat_setting_store`, `sticker_store`, `wallpaper`, `share_preferences`, `media`, `chat_lock_passcode`. `DirectMigrationContentProvider` usa el mismo permiso. El propósito (traspaso a la app hermana del mismo firmante) es inferred |

---

## 8. SharedPreferences

### 8.1 Factory

`C00S` (SharedPreferencesFactory, `A04(C00G, name)`): devuelve una implementación personalizada sobre `<dataDir>/shared_prefs/<name>.xml` (wrapper de archivo `C052308r`; clases `C052408s` / `RRP`), recurriendo al `getSharedPreferences(name, 0)` del sistema si no se puede crear el directorio. No se verificó en el código si los bytes en disco son XML estándar de Android (solo la extensión del archivo).

| Hecho | Evidencia |
|-------|-----------|
| Conjuntos de nombres con manejo especial en `AbstractC051008e` (`A02`, `A03`: flags de funcionalidad de la implementación; `A00`, `A01`, `A04`: conjuntos con alcance) | found; la semántica de los flags de `C00G(boolean,boolean,boolean)` es unknown |
| El conjunto `A05` (`multi_account_metadata`, `group_history_usage`, `hatch_group_agent`, `hatch_group_agent_debug`, `smb_token_lockout_cooldown`) no debe ser creado por esta factory: mensaje `Pref not allowed to instantiate using SharedPreferencesFactory, use MultiAccountSharedPreferencesFactory` | found |
| Los nombres de archivo principales derivan de `AbstractC051108f`: `com.whatsapp_preferences` y `com.whatsapp_preferences_light` | found |
| `SharedPreferencesUsageRepository` (`C052508t`) registra los tiempos de carga por archivo de prefs (`load`, `load2`), omitiendo `ab-props`, `ab-props-back-up`, `ab-prechatd-props`, `ab-props-backup`, `dropped_wam_events`, `keystore` | found: telemetría sobre los propios prefs |
| `C09E` (clase god-class deprecada de "Me" y prefs) envuelve `com.whatsapp_preferences_light` (`C1WL` caso 23); muchos wrappers pequeños (`C1DH`, `C56902Wq`, `C0G1`) son vistas de ese único archivo | found |
| El `com.whatsapp_preferences` por defecto es el archivo Android plano; `chatCounts` es un archivo aparte (`RP5`) | found |

### 8.2 Archivos por área (nombres encontrados en el código)

| Área | Archivos |
|------|----------|
| Núcleo | `com.whatsapp_preferences`, `com.whatsapp_preferences_light`, `startup_prefs`, `reg_prefs`, `register_phone_prefs`, `registration.verifyphone.VerifyPhoneNumber`, `registration.app.phonenumberentry.RegisterPhone`, `registration.app.verifyphone.VerifyPhoneNumber`, `multi_account_metadata`, `account_linking_prefs`, `fb_credentials_prefs`, `fb_linked_account`, `accounts_center_registration_prefs` |
| Flags | `ab-props`, `ab-props-backup`, `ab-props-back-up`, `ab-prechatd-props`, `groupAbProps`, `network_resources_pref` |
| Crypto | `keystore`, `wacrypto`, `security_prefs`, `nc_prefs`, `chat_lock`, `migration_export`, `AccountDefenceLocalDataRepository_prefs` |
| Backup / sync | `backup_prefs`, `chat_transfer_prefs`, `syncd_prefs`, `contact_sync_prefs`, `device_capabilities`, `companion_mode_prefs` |
| Funcionalidades | `username_prefs`, `meta_ai_prefs`, `bonsai_prefs`, `paa_prefs`, `status_prefs`, `newsletter_prefs`, `voip_prefs`, `route_selector_prefs`, `interop_ui`, `interop_badge_prefs`, `avatar_prefs`, `bloks`, `privacy_disclosure_store`, `user_notice_prefs`, `tos_gating_prefs` |
| Telemetría | `critical_event_client_prefs`, `anr_shared_prefs`, `time_spent_prefs`, `dropped_wam_events`, `wam_prefs`, `chatCounts` |
| SDK de terceros | `com.google.android.gms.appid`, `com.google.firebase.messaging`, `WebViewChromiumPrefs` (sistema) |

### 8.3 Claves importantes (todos los nombres de clave found en 2.26.41.6; no se reproducen los valores)

| Archivo | Clave | Tipo / uso |
|---------|-------|-----------|
| `startup_prefs` | `registration_state` | int; predicados de `C06810Gk`: 0/1 inicial, 3, 4, 5, 8 (flash verify), 12, 15, 17 (email OTP), 20, 23 |
| | `startup_migrated_version` | int; objetivo **20**, `WaStartupSharedPreferences` ejecuta migraciones por debajo de él |
| | `push_name` | nombre visible propio |
| | `force_db_check`, `force_wadb_check` | fuerzan la verificación de integridad de msgstore / wa.db (borrados por `C0HS.BoJ`, `C12650bW.onCreate`) |
| | `pending_repair_db_name`, `pending_repair_db_file_id`, `pending_repair_corruption_type`, `pending_repair_attempt_count`, `pending_repair_request_id`, `pending_repair_timestamp`, `pending_repair_gate_suppressed` | cola de reparación de bases de datos |
| | `privacy_fingerprint_enabled`, `night_mode`, `client_server_time_diff` (leído por `C050708b`) | |
| `com.whatsapp_preferences_light` | `registration_jid`, `registration_lid`, `cc`, `ph`, `self_lid`, `registration_initialized_time`, `registration_success_time_ms`, `registration_wipe_info_timestamp`, `reg_attempts_verify_code` | identidad de esta instalación (borrados por `RegistrationManager.A0I`) |
| | `adv_raw_id`, `adv_current_key_index`, `adv_timestamp_sec`, `phoneid_id`, `phoneid_timestamp` | estado ADV / phone id |
| | `privacy_last_seen`, `privacy_profile_photo`, `privacy_status`, `privacy_online`, `read_receipts_enabled`, `privacy_token_batch_offset_sec` | ajustes de privacidad (`C18260lS`, `C09E.A0S()`) |
| | `md_messaging_enabled`, `last_login_time`, `last_daily_cron`, `next_randomized_daily_cron`, `nct_salt` | flag multi-dispositivo, contabilidad de cron, salt del tctoken ([WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md)) |
| `backup_prefs` | `gdrive_state`, `backup_provider`, `backup_encryption_method`, `encrypted_backup_fleet_migration_state`, `encrypted_backup_num_attempts_remaining`, `google_restore_result`, `msg_restore_timestamp`, `last_seen_app_version`, `device_backup_integration_enabled`, `blocking_restore_in_progress`, `cloud_api_type`, `restore_second_verification_needed` | estado de backup y restauración (`C22090sX`) |
| `keystore` | `server_static_public`, `server_static_pq_public`, `client_static_keypair_pwd_enc`, `client_static_keypair_enc_success`, `can_user_android_key_store`, `remaining_auth_key_rotation_attempts` | claves estáticas Noise ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md), [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md)) |
| `wacrypto` | `signed_prekey_id_seed_migration_completed` | migración de la semilla de ids de prekey de Signal |
| `ohai_key_config` (nombre de pref en `C53596Nzj`) | `public_key` y campos de key-config | clave del gateway OHAI |
| `syncd_prefs` | `syncd_dirty`, `syncd_bootstrap_state`, `syncd_bootstrapped_mutations` (set), `mutation_counter` | bootstrap del app-state sync |
| `companion_mode_prefs` | `previously_logged_out_from_primary` | estado del companion |
| `username_prefs` | `username_reservation_state`, `username_pin` | ver [WA_USERNAME.md](WA_USERNAME.md) |
| `route_selector_prefs` | `media_conn` | ruta de media en caché (lista de hosts y datos de autenticación; [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md)) |
| `ab-props` | claves string numéricas (códigos de config), `ab_props:sys:last_refresh_time`, `ab_props:sys:config_hash`, `ab_props:sys:last_version`; `com.whatsapp_preferences` contiene `ab_props:hash_v2` | caché de AB props; `ab-props-backup` es la copia anterior |
| `chatCounts` | contadores por chat, `thread_user_secret` (32 bytes aleatorios, base64) | `WamThreadIdManager` aplica HMAC a los ids de hilo con él; `RP5.A0w` lo conserva tras un reset |

---

## 9. Archivos, cachés y estructura de media

### 9.1 `files/` interno (found salvo indicación)

| Ruta | Contenido |
|------|-----------|
| `me` | registro `Me` serializado en Java (`C9V.A01`, los campos incluyen `cc`, `number`); `me.jpg` / `me_old.jpg` foto de perfil |
| `rc2` | valor aleatorio de 160 bits cifrado con AES/OFB, generado en el primer uso a partir de dos entradas string (`K49.A0v`, `C00L.A0G`; inferred: código de país y número); propósito inferred (secreto de registro). Eliminado por los runnables de wipe `RunnableC29329CoG`, `RunnableC46625KYz` |
| `backup_token`, `foa_backup_token`, `encrypted_backup.key*`, `vault_backup.key` | sección 7.3 |
| `invalid_numbers`, `login_failed`, `customTSValues`, `emoji` | pequeños archivos de estado (`IJU`, `C06850Go`) |
| `statistics.json`, `network_statistics.json` | contadores rx / tx (`C17B`, `C17J`; claves `statistics`, `bytes`, `timestamp`, `rx_data`, `tx_data`) |
| `Logs/` | archivos de log (10.1) |
| `decompressed/libs.spo/` (+ `.superpack_version`) | bibliotecas descomprimidas en tiempo de ejecución por `C0EE`; **excluido de todo wipe** |
| `mobileconfig/` | `mc_overrides.json`, `id_name_mapping.json` (`C053409d`) y el store de configuración |
| `falco/`, `wam/` | motores de telemetría (10) |
| `Stickers/`, `Drafts/`, `GroupHistory/`, `Payment Backgrounds/`, `Wallpapers/`, `.trash/`, `biz_directory/`, `privacy_disclosure/<version>/`, `downloadable/`, `NetworkResource/`, `MNSResolverCache/`, `app_state/` | cachés de funcionalidades (`C0I1`, `C58398QKk`, `C27574Bxe`, `MNSStreamRuntime`, `C06110Cn`) |

Otros directorios privados nombrados por el switch de configuración de almacenamiento (`AbstractC13030c9`): `lib-compressed`, `app_secure_shared`, `app_sigquit`, `modules`, `app_optsvc_analytics`, `app_overtheair`, `app_qpl`, `app_light_prefs`, `cache/secure_shared`, `files/secure_shared`, `app_minidumps`, `app_fb-forker-tmp`.

### 9.2 `cache/` (found)

| Dir | Nota |
|-----|------|
| `thumb_decoded_cache` | LRU en disco, **52428800 bytes (50 MiB)** (`C33000EZy`) |
| `webp_static_cache`, `stickers_cache`, `avatar-temporary`, `interop_image_cache`, `tigon_http_client`, `ML_MODEL`, `hatch_space_images`, `meta_ai_thread_photo_uploads` | cachés de imágenes / red / modelos |
| `Profile Pictures/` | con alcance de cuenta (`C28025CFb.A01` devuelve el directorio de caché; `QLH` construye `Profile Pictures`) |

### 9.3 Cuentas secundarias (found)

`getDir("account_switching")` (= `app_account_switching/`) contiene `active_account` (el id del directorio activo, `C00W`) y la lista de cuentas (`C25160AsA`). Los datos de una cuenta secundaria viven en `<dataDir>/accounts/<dirId>/{databases,files,cache}` (`C28025CFb`) y su media bajo `<root>/accounts/<dirId>`; la cuenta por defecto usa los directorios normales. `account_switcher.db` y los prefs multi-cuenta son compartidos.

### 9.4 Raíz de media externa (found)

`<root>/Media/WhatsApp <Category>/` con categorías `Images`, `Video`, `Audio`, `Documents`, `Voice Notes`, `Video Notes`, `Animated Gifs`, `Stickers`, `Sticker Packs`, `Profile Photos`, `Backup Excluded Stickers` (`AbstractC26994Bml`), subcarpetas `Sent`, `Private`, `.Thumbs` (`*.prog.thumb.jpg`, `C0I1.A08`), `.Shared`, marcadores `.nomedia`. `message_media.file_path` almacena la parte posterior a la raíz.

---

## 10. Logs y telemetría conservados en el dispositivo

### 10.1 Logs (found)

| Archivo | Detalle |
|---------|---------|
| `files/Logs/whatsapp.log`, `whatsapp.tmp` | log de texto, cabecera `==== logfile version=2.26.41.6 level=4 ====`; la rotación comprime a `.gz` con una fecha (`Log.rotate`, `AbstractC28128CKx.A00`). `C24971Ap6` reúne `Logs` con el directorio de db para la exportación de soporte / reporte de bugs |
| `app_minidumps/`, `<dir>/minidumps`, `crash_upload/` | volcados de crashes nativos y el staging de subida (`C0FQ`, `JJ1`, `CKN`, `ExceptionsUploadService`) |
| `anr_report_<n>.dmp`, `anr_shared_prefs` | reportes ANR (`C45432Jrw`) |
| `cache/qpl`, `app_qpl` | trazas de QuickPerformanceLogger |

### 10.2 Motores de telemetría

| Ruta | Motor | Evidencia |
|------|-------|-----------|
| `files/wam/` | directorio de runtime WAM pasado a `WAJContextInitWAMRuntime` (JNI) | `RunnableC29323CoA`; prefs `dropped_wam_events` y `wam_prefs` |
| `files/falco/` | logger de eventos en `libffsingletonmerged.so` | strings nativos abajo |
| `files/mobileconfig/` | store de Mobile Config | `C053409d` |

Archivo SQLite de Falco `FFLogger.sql` (ubicación inferred: Java crea `files/falco/`, el nombre del archivo es un string en la lib nativa): tablas presentes en los strings del esquema nativo (found): `event`, `buffer_event`, `upload` (`request_data`, `num_events`, `is_compressed`, `compression_method`), `claim` (`principal_subject_hash`, `claim`, `expires_at`), `collection_constraint`, `event_config` (`event_config_hash` UNIQUE, `event_name`, `sampling_rate`, `collection_constraint_ref`, `is_deidentified`), `checksum`, `amendment_outbox`, índice `event_0` sobre `event(requested_latency)`; `batch` se une mediante `identities_hash`. `fflogger_health_counters.bin` contiene contadores de autoinstrumentación (`mobile_health_counters`). El lado Java solo crea el directorio.

### 10.3 Automedición

wa.db `wa_storage_monitoring_data` / `_jobs` (tamaños por tabla y bytes sin usar por `db_name`) y las estadísticas de carga de prefs (8.1) son telemetría que el cliente mantiene sobre su propio almacenamiento. El pipeline de eventos WAM en sí queda fuera del alcance aquí.

---

## 11. Qué se borra, y cuándo

### 11.1 Operaciones

| Operación | Entrada (2.26.41.6) | Efecto |
|-----------|---------------------|--------|
| Eliminar cuenta / reset de datos locales | `C25007Aph.A0L` y luego `A02` (`removeDatabasesAndResetState`) | wipe local completo, 11.2 |
| Companion eliminado | `C25007Aph.A0M` (`deleteCompanionCleanup`) | `ActivityManager.clearApplicationUserData()` (fallback `pm clear <package>`, fallback a `A02`) |
| Re-registro | `RegistrationManager.A06` (`reregister reason=`) | borra los prefs de registro y `me`, 11.3 |
| Unregister desde el dispositivo | `RegistrationManager.A0F` | detiene la conexión con `should_unregister=true`, elimina `me`, borra el estado |
| Logout (primario, con multi-cuenta) | `LogoutManager` (`AccountLogoutMutation`, w:mex) | logout en el servidor, cuenta marcada como desconectada; los datos permanecen hasta que el usuario elimine la cuenta desconectada (11.4). No se rastreó si el primer paso elimina algo localmente (unknown) |
| Eliminar cuenta desconectada | `LogoutManager.removeLoggedOutAccountWithCleanup` | elimina la entrada de la cuenta, luego `deleteDefaultAccountDirectories` o `deleteSecondaryAccountDirectories`, luego el estado de backup de GMS |

### 11.2 Eliminación de cuenta (`C25007Aph.A02`, found)

| Objetivo | Acción |
|----------|--------|
| Stores en memoria, gestores de funcionalidades | limpiados; `last_contact_full_sync` = -1 |
| Bases de datos | el delete de cada helper (`A0D`, `A0N`): msgstore mediante `C0HC` (`msgstore-manager/deletedb/result`), wa.db (`deleteaccountconfirm/wa-db-delete-incomplete` es un error si quedan archivos), commerce, `emojidictionary`, store de language packs, `MediaJobDataStore`, stores de history-sync, directorio de negocios (`files/biz_directory`) |
| `files/` | todas las entradas excepto `decompressed`; `Logs` se conserva cuando el flag `z` está establecido (ruta de companion) |
| Raíz externa | `Backups/` eliminado y recreado vacío, archivos de `Databases/` eliminados (`AbstractC28132CLd.A04`), solo si el estado del almacenamiento externo es utilizable |
| `com.whatsapp_preferences` | `clear()` y luego `version` se reescribe con `2.26.41.6` |
| `backup_prefs` | `clear()` pero `last_seen_app_version` y `device_backup_integration_enabled` se restauran |
| `chatCounts` | se eliminan todas las claves excepto `thread_user_secret` (`RP5.A0A`) |
| Otros prefs | `avatar_prefs`, los archivos de registro y VerifyPhone, registro de companion (`registration_device_id`, `companion_registration_state` = 0), algunos prefs de funcionalidades |
| WebView | cookies y web storage eliminados, también para perfiles con nombre cuando hay multi-perfil disponible |

### 11.3 Reregister / unregister (found)

`RegistrationManager.A0I` elimina `registration_jid`, `registration_lid`, `cc`, `ph` y el `registration_wipe_info_timestamp`; `A0A` borra los prefs de las dos pantallas de registro; el archivo `me` se elimina (`rm-me`).

### 11.4 Diálogo de chats desconectados (`FilesDeletionUtility`)

Elimina la raíz externa del usuario desconectado, `cacheDir`, cada entrada de `filesDir` excepto `decompressed`, el directorio de archivos de la cuenta secundaria, y luego llama a los deletes de los helpers de DB; un borrado fallido de wa.db lanza una excepción y el diálogo reporta un error (`FilesDeletionUtility/deleteInternalFiles/wa-db-delete-incomplete`).

### 11.5 Eliminación de archivos multi-cuenta (`AccountSwitchingFileManager.deleteDefaultAccountDirectories`)

Para la cuenta por defecto: `shared_prefs` se elimina excepto una lista de permitidos; `databases` se elimina excepto `account_switcher.db` (y sus variantes de sufijo); los demás directorios se eliminan completos.

---

## 12. Notas de Baileys (mapeo inferred)

Baileys conserva credenciales y un store con clave (`creds`, pre-key, session, sender-key, app-state-sync-key / -version, lid-mapping, device-list, tctoken). Las contrapartes conceptuales en Android (inferred; ningún código las vincula):

| Estado de Baileys | Almacenamiento en Android |
|-------------------|---------------------------|
| `session`, `pre-key`, signed pre-key | `axolotl.db` `sessions`, `prekeys`, `signed_prekeys` (+ `kyber_prekeys` en Android) |
| `sender-key`, `sender-key-memory` | `axolotl.db` `sender_keys`; distribución por dispositivo en msgstore `group_participant_device` |
| app-state sync key / version | `sync.db` `crypto_info` (`key_data`, `epoch`), `collection_versions` (`lt_hash`) |
| lid mapping | msgstore `jid_map` (+ `lid_display_name`) |
| device list | msgstore `user_device`, `user_device_info` |
| `tctoken` | wa.db `wa_trusted_contacts(_send)` |
| `creds.me`, registration id, ADV | `files/me`, prefs `adv_*`, fila de `identities` |

Una sesión de Baileys no tiene equivalente de la tabla `message`; eliminar su auth state es la contraparte del wipe en 11 y requiere una nueva vinculación.

---

## 13. Casos de error y gotchas

| Síntoma | Causa | Fix / nota |
|---------|-------|-----------|
| `msgstore/upgrade version 1 to N` nunca aparece | el `user_version` de msgstore es siempre 1 | leer `props.msgtore_db_schema_version` para el estado real del esquema |
| msgstore "restored-db-not-indexed" / `RestoredIndexesPending` | DB restaurada desde un backup; los índices se crean de forma diferida | claves de `props` `MessagesDBHelper_*`; la ejecución se completa de forma asíncrona |
| `still-corrupt-after-repair`, `delete-superseded-by-new-repair` | falló la verificación de integridad (`C0HC.checkhealth`) | cola en `startup_prefs` `pending_repair_*`; `force_db_check` |
| wa.db queda vacía de repente tras una actualización | el switch de upgrade eliminó tablas (versiones 3 a 94) o cambió el hash del esquema | wa.db es reconstruible desde el servidor y la libreta de direcciones |
| `deleteaccountconfirm/completion-blocked/wa-db-files-remain` | no se pudieron eliminar los archivos de wa.db | reintentar; el wipe se aborta con `Be5` |
| La restauración rechaza un backup (`has-jid-user-mismatch`) | `BackupMetadata.jid_suffix` difiere de la cuenta | restaurar con el mismo número |
| `backup-file-crypt15/prefix null` | archivo vacío o no es crypt15 | verificar el prefijo delimitado (7.2) |
| `vault backup key present but could not be read` | `vault_backup.key` ilegible | el código se niega a generar un reemplazo para evitar sobrescribir un archivo recuperable |
| `Pref not allowed to instantiate using SharedPreferencesFactory` | pref exclusivo de multi-cuenta creado con la factory equivocada | usar `MultiAccountSharedPreferencesFactory` |
| Permanecen los datos de una cuenta desconectada | el logout no elimina los datos de la cuenta (11.1) | eliminar la cuenta explícitamente |

---

## 14. Distinciones clave

| No confundir | Diferencia |
|--------------|-----------|
| `msgstore.db` vs `wa.db` | mensajes, chats y filas `jid` vs contactos, listas de bloqueo, tokens de contactos de confianza, cachés de negocio e integridad; los ids de fila JID existen solo en msgstore, las claves de wa.db son strings JID crudos |
| `jid._id` vs JID crudo | las columnas `*_jid_row_id` son ids de fila de msgstore; las tablas `wa_*` usan `jid` TEXT |
| `user_version` de SQLite vs versión del esquema | msgstore siempre 1; wa.db 95; el esquema es un hash en `props` (msgstore) o una etiqueta (wa.db) |
| Auto-backup de Android vs backup de chats | el auto-backup excluye todo; el backup de chats es el archivo `crypt15` propio de la app en la raíz externa |
| archivo crypt15 vs archivos de clave | texto cifrado en `Backups/`; claves en `files/*.key` (nunca en la misma carpeta) |
| `com.whatsapp_preferences` vs `_light` | prefs planos de Android (se limpian dejando una clave de versión) vs el archivo de implementación personalizada usado por `C09E` (identidad, privacidad, flags) |
| `ab-props` vs `wa_props` | códigos de experimentos AB (prefs) vs props de cuenta del servidor (tabla de wa.db) |
| Logout vs eliminación de cuenta | el logout marca la cuenta; la eliminación borra DBs, archivos, Backups, prefs (11) |
| Falco vs WAM | Falco es el logger de eventos SQLite en una lib nativa; `wam/` es el directorio de runtime WAM; ambos son telemetría |
| Archivos de mods de terceros | bases de datos extra, logs de stanzas o diagnósticos de hooks no los crea la app original y no están cubiertos |
---

## 15. Estructura y ciclo de vida

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

## 16. No cubierto y desconocido

| Tema | Estado |
|------|--------|
| Atribución a DB por tabla para las 306 + 422 clases de tabla más allá de las verificadas | tamaños de conjuntos found; el mapeo de cada clase a su base de datos por el grafo DI no fue rastreado (inferred por FKs y nombres) |
| Tipos de columna, defaults y NOT NULL de tablas construidas con funciones helper | el decompilador omite algunos; solo se listan nombres |
| Las ~250 tablas restantes de msgstore, las tablas restantes de wa.db y status.db | nombres listados en familias; columnas no extraídas |
| Formato del texto cifrado de crypt15, KDF, MAC; contenido de los submensajes de `BackupPrefix` | unknown |
| Formato XML estándar en disco de la implementación personalizada de prefs | no verificado |
| Lista completa de claves de cada archivo de prefs (cientos de claves) | solo los archivos y claves nombrados en 8.3 |
| Significado de los flags de `C00G`, ids de tipo de add-on, valores de `registration_state` | parcialmente nombrados |
| Versiones de `sync.db`, `chatsettings.db`, `stickers.db`, `commerce.db`, `daily_metrics.db`, `location.db` | no resueltas |
| Propósito de `files/rc2`, `files/key` | `rc2` inferred; `key` no resuelto |
| Si el logout del primario por sí solo elimina datos locales | no rastreado |
| Comportamiento en runtime, tamaños de archivo, contenido de WAL | solo análisis estático |
