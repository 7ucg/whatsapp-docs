<!-- src-sha1: 6effa8dc57f2e12a66c37c7cae9d875028a5d55e -->
# WhatsApp Armazenamento Local — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-23
**Escopo:** bancos de dados SQLite (nomes, localização, engine, versionamento, framework de tabelas), tabelas e colunas principais de msgstore.db e wa.db, axolotl.db, sync.db e os bancos menores, backups crypt15 e arquivos de chave de backup, regras de auto-backup do Android e o content provider de migração, factory de SharedPreferences e inventário de chaves, layout de arquivos e cache, arquivos de log e telemetria, o que logout / unregister / reregister / exclusão de conta removem

---

## 1. O que é armazenado onde

Todas as afirmações vêm de análise estática do APK decompilado e de suas bibliotecas nativas embutidas. Nenhum dado de dispositivo foi lido. Tier: **found** = lido em código, manifest ou strings nativas; **inferred** = deduzido do código; **unknown** = não resolvido. Os nomes ofuscados são os exibidos pelo JADX para 2.26.41.6 e mudam a cada build.

### 1.1 Mapa de armazenamento

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

| Local | Conteúdo | Sobrevive ao auto-backup do Android |
|-------|----------|-------------------------------------|
| `databases/` | todos os arquivos SQLite | não: todos os domínios são excluídos (8.1) |
| `shared_prefs/` | configurações, flags, chaves | não |
| `files/`, `cache/` | arquivos de chave, caches, logs | não |
| raiz externa `Backups/` | backup criptografado de conversas (crypt15) | n/a: mecanismo de backup próprio (7) |

### 1.2 Fatos sobre a engine (found)

| Fato | Evidência |
|------|-----------|
| O SQLite é o build embutido `io.requery.android.database.sqlite`, não o do framework | pacote em `java_src` |
| Sem SQLCipher: nenhum `PRAGMA key`, nenhuma string `sqlcipher` em todo o `java_src` | grep; os arquivos de banco ficam em texto plano em repouso dentro da sandbox do app |
| WAL habilitado para todos os helpers baseados em `AbstractC11350Yn` (`setWriteAheadLoggingEnabled(true)`) | `AbstractC11350Yn`; checkpoint via `PRAGMA wal_checkpoint(FULL)` |
| msgstore abre com `PRAGMA synchronous=NORMAL`, `cache_size` opcional (flag **20777**), `PRAGMA secure_delete=1` | `C06980Hc.onOpen`; a falha ao habilitar secure_delete é reportada como `db-integrity/enable-secure-delete/error/not-enabled` |
| `PRAGMA foreign_keys=ON` é definido para sync.db, paa.db, daily_metrics.db, não para msgstore.db | `AbstractC12530bK`, `AbstractC197088a3`, `AbstractC16650iN`; msgstore faz cascata por triggers (2.3) |

---

## 2. Bancos de dados SQLite

### 2.1 Inventário

Os nomes de arquivo são literais (`getDatabasePath(...)` / construtores de helper). As contagens de tabelas são o número de classes de definição de tabela no módulo DI que alimenta o helper (2.3).

| Arquivo | Helper / módulo (2.26.41.6) | Versão / migração | Classes de tabela | Função | Tier |
|---------|-----------------------------|-------------------|-------------------|--------|------|
| `msgstore.db` | `C06980Hc` (factory `C0HH`) | `user_version` do SQLite fixo em 1; fingerprint do schema em `props` (2.4) | 306 (factory `C1S0`) | mensagens, chats, JIDs, recibos, chamadas, newsletters, integrity, AI, TEE | found / atribuição do conjunto inferred |
| `wa.db` | `C12650bW` | **95** (`creating contacts database version 95`) | 88 (implementadores de `C8ZL`) | contatos, listas de bloqueio, perfis business, tokens de contatos confiáveis, sinais de integrity | found |
| `axolotl.db` | `C44861sL`, tabelas `AbstractC11250Yd` | **40** | 15 | sessões Signal, prekeys, sender keys, filas de stanza | found |
| `sync.db` | `AbstractC12530bK` (helper `X.1sK`) | migrações `ALTER` graduais até pelo menos a v50; downgrade = reset | 10 | app-state sync, history sync, mensagens peer | found, versão unknown |
| `status.db` | `C41891nD` | **2** (`StatusDbHelper creating status database version 2`) | 29 (`AbstractC11620Zo`) | posts de status e interações | found |
| `backup.db` | `C44881sN` | **1** | `backups`, `backup_props` | controle de backup; `backup_props` guarda `wa_db_schema_version` | found |
| `chatsettings.db` | `C11200Xy("chatsettings.db")` | unknown | `settings` (inferred) | mute, pin, tom, wallpaper, tema por chat | nome found, tabela inferred |
| `stickers.db` | módulo `AbstractC149676Ty` | unknown | 18 (o módulo também registra `offloaded_media*`, `backups`, `backup_props`) | pacotes de stickers | found |
| `offloaded-media.db` | `CMN` (componente de backup) | unknown | `offloaded_media`, `offloaded_media_staging` (atribuição inferred) | índice de mídia offloaded | found / inferred |
| `payments.db` | helper anônimo `C1S0`, `AbstractC22520tH` | **5** | `contacts`, `methods`, `receipts`, `tmp_transactions` | métodos de pagamento | found |
| `commerce.db` | `C27743C3e` | unknown | unknown | dados de commerce; tem uma variante de backup `commerce_backup.db` | nome found |
| `companion_devices.db` | `C48701zE` | **27** | `devices` (+ outras) | dispositivos vinculados vistos a partir do primário | found |
| `paa.db` | `ManagedAccountDbHelper` (`AbstractC197088a3`) | migrações V1 a V7 | `paa_connection`, `contact_metadata`, `group_metadata` | dados de conta gerenciada (conta aprovada pelos pais) | found |
| `daily_metrics.db` | `AbstractC16650iN` | unknown | `poll_event_logging`, `poll_daily_participant`, `comments_event_logging`, `pnh_daily_event_logging`, `community_home_action_logging`, `snapl_payload` | contadores diários de eventos | found |
| `qp_payload.db`, `location.db`, `fa_events.db`, `media.db`, `account_switcher.db` | getters de caminho (`C23985AVo`, `C33961Wh`) | unknown | unknown | quick promotions, localização em tempo real, federated analytics, jobs de mídia (inferred), lista de contas | nome found |
| `sqlite_vec.db` | `MessageEmbeddingsStore` | unknown | tabelas vetoriais (unknown) | embeddings de mensagens no dispositivo; presente apenas se habilitado | found |
| `emojidictionary.db`, `hsmpacks.db`, `events.db` | `C8JP`, `C6UR` | unknown | unknown | dicionário de emoji, pacotes de templates, eventos | nome found |
| `wa-backup.db`, `msgstore.db-backup` | `CMN` / `C26042BNa`, `C0KE` | n/a | n/a | cópias locais de segurança de wa.db / msgstore | found |
| `migration_prefetcher.db`, `migration_import_metadata.db`, `migration_export_metadata.db` | `C23985AVo` | unknown | unknown | estado de transferência de conversas / migração de SO; `migration_prefetcher.db` é excluído por `C28152CMi` | nome found |
| `androidx.work.workdb` | WorkManager (`no_backup/`) | Room | padrão | fila de jobs | inferred a partir das classes Room (`room_master_table`) |

### 2.2 Qual DB guarda as tabelas citadas em outros relatórios

| Tabela | Arquivo DB | Classe da tabela | Evidência | Relatório |
|--------|------------|------------------|-----------|-----------|
| `wa_trusted_contacts`, `wa_trusted_contacts_send` | `wa.db` | `C23627AHs`, `C23628AHt` (`C8ZL`) | o helper de wa.db as recria; stores lidos via `C12810bn` do helper de wa.db | [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_biz_integrity_signals` | `wa.db` | `C53116Nmn` (`C8ZL`) | found | [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 5.1 |
| `start_chat_trust_signals` | `wa.db` | `AI0` (`C8ZL`), trigger em `wa_contacts` | found | relatório de ban 5.2 |
| `integrity_chat_info` | `msgstore.db` | `C08970Ox`, trigger `chat_bd_for_integrity_chat_info_trigger` em `chat` | found, atribuição pela FK para `chat` | relatório de ban 5.3 |
| `meta_ai_memory` | **`wa.db`** | `C23621AHm` (`C8ZL`) | found; colunas `memory_id`, `memory_content`, `bot_jid_row_id` | [WA_META_AI.md](WA_META_AI.md) |
| `bot_memory_metadata`, `bot_chat_info`, `ai_thread_info` | `msgstore.db` | `C08640Nq`, `C08610Nn`, `C0MO` | no conjunto de 306 classes | relatório Meta AI |

`meta_ai_memory` está em `wa.db`, não em `msgstore.db`: sua classe implementa `C8ZL`, que apenas o helper de wa.db itera (`C12650bW.onCreate` com `new C08050Lj("wa.db")`). `bot_jid_row_id` referencia uma linha `jid` de msgstore, portanto a coluna é uma referência suave entre bancos (inferred; não é possível ter foreign key entre arquivos).

### 2.3 Framework de tabelas (como os schemas são definidos)

As tabelas não são escritas como strings SQL. Cada tabela é uma classe que implementa `InterfaceC08060Lk` (wa.db: a subinterface `C8ZL`) com três hooks (found):

| Hook | Finalidade |
|------|------------|
| `ASa(ctx, builder)` | declarar colunas: builder `C08080Lm`, `.A02` = nome, `.A00` = tipo `EnumC08100Lo` (`INTEGER`, `TEXT`, `REAL`, `BLOB`, `LONG`, ...), flags de primary key / not null / default |
| `ASX(ctx, builder)` | declarar índices (`CRN`, `CRJ` = índice condicional) |
| `ASc(builder)` | declarar triggers (`CRg`, `CRf`) |

- 422 classes implementam `InterfaceC08060Lk` e outras 88 implementam `C8ZL`. São fornecidas em conjuntos DI; cada helper itera seu conjunto (`C06980Hc.A03`, `C12650bW.onCreate`, `C44881sN`, `C41891nD`).
- Exclusões em cascata são triggers, não foreign keys: `AbstractC08210Lz.A01` constrói `CREATE TRIGGER <parent>_bd_for_<child>_trigger BEFORE DELETE ON <parent> BEGIN DELETE FROM <child> WHERE ...; END` (found; exemplo: `message_add_on_reaction` é excluída quando as linhas de `message_add_on` somem).
- As listas de colunas abaixo são extraídas de `ASa` na ordem declarada. O decompilador omite algumas colunas construídas por helper (primeira coluna de algumas tabelas, valores default); estas são marcadas "(+ jid)" quando uma query ou trigger comprova a coluna. Os tipos são dados apenas onde o código os declara.
- A atribuição de DB das 306 classes de msgstore é pela factory DI `C1S0` (306 chamadas `new`, inclui `message`, `chat`, `jid`) e pelos triggers FK para `chat` / `message` / `jid` (inferred). Existem tabelas com o mesmo nome em dois módulos (`status`, `status_attribution`, `mms_thumbnail_metadata`, `quick_promotion_payload`: msgstore e status.db ou wa.db têm cada um uma classe).

### 2.4 Versionamento e migrações

| DB | Estratégia (found) |
|----|--------------------|
| `msgstore.db` | `onUpgrade` = `onCreate`; `setVersion(1)` sempre. A versão real é um hash guardado na tabela `props`: `msgtore_db_schema_version` e `msgtore_db_schema_indexes_version` = `Arrays.hashCode` sobre uma tag literal `Consumer-<hex>` e `MessageSchemaConfig=1;isGlobalChatDbMigrated=<bool>[;includeNewsletterInteractionTable=true]` (`C06980Hc.A04`). Declarativo: tabelas e índices são `CREATE ... IF NOT EXISTS` a partir do conjunto de classes. Outras chaves de `props`: `MessagesDBHelper_RestoredIndexesPending`, `MessagesDBHelper_CreateAsyncIndexesV2`, `..FailedAttempts` |
| `wa.db` | `onUpgrade` é um switch sobre a versão antiga de 3 a 94 que na maior parte descarta tabelas recriadas depois; versão antiga desconhecida cai em `onCreate`; downgrade = `onCreate`. `wa_db_schema_version` é gravada com uma tag `ConsumerBeta-<hex>`. A pref `force_wadb_check` (startup_prefs) força uma nova verificação. wa.db são dados reconstruíveis (contatos, tokens, caches) |
| `axolotl.db` | versionado (40); variantes antigas de DDL visíveis em `C44861sL` (p. ex. `identities` ganhou `recipient_type`, `next_kyber_prekey_id`, `account_encryption_attestation_type`; `sessions` ganhou `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope`; `sender_keys` ganhou `bucket_id`) |
| `sync.db` | `ALTER TABLE ... ADD` graduais (p. ex. `collection_versions.dirty_version`, `history_sync_companion.inline_payload`, `msg_history_sync.size_limit_bytes`); downgrade ou versão desconhecida chama `sync-db-helper/reset`, que recria as tabelas, de modo que o app state é ressincronizado (inferred) |
| `status.db` | v2; linha `schema_version` em `key_value_store` |
| `paa.db` | `runMigrationV1`..`V7` (adiciona colunas como `age_experience`, `snooze_status`, `common_groups_count`) |
| backups (`BD0`) | os metadados do crypt15 ainda carregam flags de "migration finished" por tabela (`message_main`, `receipt_user`, `jid_store`, ...), o histórico das migrações antigas do msgstore (7.2) |

---

## 3. msgstore.db: tabelas e colunas principais

### 3.1 Famílias de tabelas (found, 306 classes)

| Família | Tabelas (exemplos) |
|---------|--------------------|
| Identity | `jid`, `jid_map`, `lid_chat_state`, `lid_display_name`, `jid_user_metadata`, `integrator_display_name` |
| Chat | `chat`, `chat_ephemeral`, `chat_encryption_classification`, `community_chat`, `broadcast_chat_details`, `thread_messages`, `thread_id`, `draft_message_reminder` |
| Núcleo de mensagem | `message`, `message_text`, `message_media`, `message_quoted*` (14), `message_edit_info`, `message_revoked`, `message_forwarded`, `message_mentions`, `message_link`, `message_future`, `message_orphan`, `message_send_count`, `message_view_once_media`, `message_ephemeral*` |
| Mensagens de sistema | `message_system` + cerca de 35 tabelas de detalhe `message_system_*` (group, number_change, lid_change, username_change, device_change, privacy, ...) |
| Add-ons | `message_add_on` e `message_add_on_reaction`, `_poll_vote`, `_poll_vote_selected_option`, `_keep_in_chat`, `_pin_in_chat`, `_question_response`, `_event_response`, `_receipt_device`, `_receipt_coex`, `_status_*` |
| Recibos | `receipt_user`, `receipt_device`, `receipt_coex`, `receipt_orphaned`, `played_self_receipt`, `optimised_delivery_info` |
| Grupos | `group_participant_user`, `group_past_participant_user`, `group_participant_device`, `parent_group_participants`, `group_history_*`, `group_root_key_mapping`, `group_notification_version` |
| Dispositivos | `user_device`, `user_device_info`, `primary_device_version`, `agent_devices` |
| Mídia | `media_hash_thumbnail`, `media_content`, `mms_metadata`, `mms_thumbnail_metadata`, `extended_media_data`, `message_media_map`, `message_streaming_sidecar`, `media_refs`, `message_thumbnail`, `audio_data`, `voice_data` |
| Chamadas | `call_log`, `call_log_participant_v2`, `joinable_call_log`, `missed_call_logs`, `bcall_session`, `call_link`, `scheduled_calls` |
| Newsletters | `newsletter`, `newsletter_message`, `newsletter_message_reaction`, `newsletter_admin_profile`, `newsletter_subscribers`, `newsletter_pinned_message`, `newsletter_interaction` |
| Enquetes / eventos / labels | `message_poll`, `message_poll_option`, `poll_vote_*`, `event*`, `labels`, `labeled_jid`, `favorite`, `quick_replies*` |
| Pagamentos / commerce | `pay_transaction`, `payment_*`, `message_payment*`, `message_order`, `message_product`, `cart_item` |
| Integrity / reporting | `integrity_analysis_result`, `integrity_chat_info`, `integrity_input_feature`, `integrity_deleted_chat_*`, `message_quarantine`, `message_structure_analysis_result`, `reporting_info(_content)`, `scam_alert_events` |
| AI / TEE | `ai_thread_info`, `ai_rich_response_message_*`, `bot_*`, `agent_*`, `auth_agent_chat_metadata`, `tee_chat_request_table`, `tee_message_info_table`, `private_ai_*`, `embeddings_deletion_log` |

### 3.2 Identity: jid, mapeamento LID

| Tabela | Colunas (ordem declarada) | Notas |
|--------|---------------------------|-------|
| `jid` | `_id` (PK AUTOINCREMENT), `user`, `server`, `agent`, `device`, `type`, `raw_string` | índice único `jid_key_new_index` em (`user`,`server`,`agent`,`device`,`type`), único `jid_raw_string_index` em `raw_string`. `JidStore` (`C0W4`) grava `jid.getType()` / `getRawString()`. Toda outra tabela refere-se a um JID por `*_jid_row_id` = `jid._id` |
| `jid_map` | `lid_row_id`, `jid_row_id`, `sort_id` | linha LID para linha de JID do número de telefone (superfície da migração LID; trigger em `lid_row_id`) |
| `lid_chat_state` | `jid_row_id`, `is_pn_shared`, `pn_requested_ts`, `pnh_duplicate_lid_thread` (+ colunas apenas com default) | estado do compartilhamento do número de telefone por chat LID |
| `lid_display_name` | `lid_row_id`, `display_name`, `username` | o username exibido para um contato LID, ver [WA_USERNAME.md](WA_USERNAME.md) |

### 3.3 chat

`chat` (`C0OM`), 57 colunas declaradas. Índice único `chat_account_jid_row_id_unique_index` em `account_jid_row_id`.

| Grupo | Colunas |
|-------|---------|
| Chave | `_id`, `jid_row_id`, `account_jid_row_id` (conta proprietária; nova com multi-conta / LID), `chat_origin` |
| Exibição | `subject`, `created_timestamp`, `hidden`, `archived`, `sort_timestamp`, `group_type`, `group_member_count`, `is_contact`, `chat_lock` |
| Ponteiros para `message` | `display_message_row_id`, `last_message_row_id`, `last_read_message_row_id`, `last_read_receipt_sent_message_row_id`, `last_important_message_row_id`, `change_number_notified_message_row_id`, mais as variantes `*_sort_id` e `last_message_reaction_row_id`, `last_seen_message_reaction_row_id` |
| Contadores de não lidas | `unseen_message_count`, `unseen_important_message_count`, `unseen_missed_calls_count`, `unseen_row_count`, `unseen_message_reaction_count`, `unseen_comment_message_count`, `unseen_earliest_message_received_time` |
| Ephemeral | `ephemeral_expiration`, `ephemeral_setting_timestamp`, `ephemeral_displayed_exemptions`, `ephemeral_disappearing_messages_initiator`, `ephemeral_after_read_duration` |
| Crypto / política | `plaintext_disabled`, `chat_encryption_state`, `limited_sharing`, `limited_sharing_setting_timestamp`, `growth_lock_level`, `growth_lock_expiration_ts`, `spam_detection`, `business_chat_state`, `participation_status`, `history_sync_progress`, `chat_props` |

### 3.4 message e satélites

`message` (`C09540Re`), 24 colunas; índice único `message_key_index` em (`chat_row_id`,`from_me`,`key_id`,`sender_jid_row_id`).

| Coluna | Uso |
|--------|-----|
| `_id` | id da linha, referenciado como `message_row_id` em todo lugar |
| `chat_row_id`, `sender_jid_row_id` | chat, remetente (`jid._id`) |
| `from_me`, `key_id` | parte da chave da mensagem (id da stanza) |
| `status`, `broadcast`, `recipient_count`, `participant_hash` | estado de entrega e resumo do fan-out do grupo |
| `origination_flags`, `origin`, `view_mode`, `sort_id` | origem e ordenação |
| `timestamp`, `received_timestamp`, `receipt_server_timestamp`, `server_sts` | horários |
| `message_type`, `text_data`, `translated_text` | tipo e corpo em texto plano (o texto fica na própria linha) |
| `starred`, `view_replies_thread_id` | flags |
| `lookup_tables`, `message_add_on_flags` | bitmasks que indicam quais tabelas satélite têm linhas (inferred a partir de nomes e uso) |

| Satélite | Colunas principais |
|----------|--------------------|
| `message_text` | `message_row_id`, `description`, `page_title`, `url`, `font_style`, `text_color`, `background_color`, `preview_type`, `invite_link_group_type`, `counter_abuse_token`, `link_end_index` |
| `message_quoted` | `message_row_id`, `chat_row_id`, `parent_message_chat_row_id`, `from_me`, `sender_jid_row_id`, `key_id`, `timestamp`, `message_type`, `text_data`, `quoted_source`, `quoted_type` |
| `message_edit_info` | `message_row_id`, `original_key_id`, `edited_timestamp`, `sender_timestamp` |
| `message_revoked` | `message_row_id`, `revoked_key_id`, `admin_jid_row_id`, `revoke_timestamp` |
| `message_ephemeral` | `message_row_id`, `duration`, `expire_timestamp`, `keep_in_chat`, `ephemeral_trigger`, `ephemeral_initiated_by_me`, `after_read_duration` |
| `message_secret` | `message_row_id` (+ a coluna do secret, omitida pelo decompilador): secret por mensagem para a criptografia de add-ons (inferred) |
| `message_future` | `message_row_id`, `version`, `data`, `future_message_type`, `future_proof_stanza`, `edit_version`, `message_stanza_data` (mensagem não suportada guardada para depois) |
| `message_orphan` | `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_*`, `orphan_message_data`, `orphan_message_type`, `orphan_message_reason` (filha que chegou antes do pai) |
| `message_quarantine` | `message_row_id`, `chat_row_id`, `timestamp`, `original_protobuf`, `serialized_stanza`, `protobuf_type` |
| `reporting_info` | `message_row_id`, `reporting_tag`, `stanza_id`, `send_timestamp`, `receive_timestamp`, `stanza_id_text`, `receive_flow`, `is_message_add_on` (ver [WA_REPORTING.md](WA_REPORTING.md)) |
| `message_send_count` | `message_row_id`, `send_count` |

### 3.5 Recibos, reações, add-ons

| Tabela | Colunas | Notas |
|--------|---------|-------|
| `receipt_user` | `_id`, `message_row_id`, `receipt_user_jid_row_id`, `receipt_timestamp`, `read_timestamp`, `played_timestamp` | por destinatário (1:1 e grupo) |
| `receipt_device` | `_id`, `message_row_id`, `receipt_device_jid_row_id`, `receipt_device_timestamp`, `primary_device_version` | por dispositivo do destinatário |
| `receipt_orphaned` | `_id`, `chat_row_id`, `from_me`, `key_id`, `receipt_device_jid_row_id`, `receipt_recipient_jid_row_id`, `status`, `timestamp` | recibo antes da sua mensagem |
| `message_add_on` | `_id`, `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_message_row_id`, `timestamp`, `status`, `message_add_on_type`, `received_timestamp`, `expiry_duration_in_secs`, `server_timestamp`, `expiry_timestamp`, `expiry_type` | uma linha por reação / voto / pin / keep; a chave única é (`chat_row_id`,`key_id`,`from_me`) na query de lookup |
| `message_add_on_reaction` | `message_add_on_row_id` (PK), `reaction`, `sender_timestamp` | índice parcial `message_add_on_reaction_empty_reaction_index` em `reaction = ''` (string vazia = reação removida, inferred) |
| `message_poll` | `message_row_id`, `enc_key`, `selectable_options_count`, `invalid_state`, `poll_logging_id`, `poll_type`, `correct_option_id`, `content_type`, `hide_participant_names`, `end_time`, `allow_add_option` | |

`C09010Pb.A00` é o conjunto de colunas do add-on; `AbstractC41651mo.A01` seleciona o conjunto de colunas pelo id de tipo do add-on: 56 = reação (`C0PV`), 67 = voto de enquete (`C0PT`), outros 68, 74, 79, 86, 93, 121, 122, 125 (found: o switch; seu significado não foi rastreado).

### 3.6 Grupos e participantes

| Tabela | Colunas |
|--------|---------|
| `group_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `add_timestamp`, `label`, `join_method`, `group_history_send_state` |
| `group_past_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `is_leave`, `timestamp` |
| `group_participant_device` | `_id`, `group_participant_row_id`, `device_jid_row_id`, `sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket` (estado de distribuição de sender key por dispositivo) |
| `group_root_key_mapping` | `_id`, `group_jid_row_id`, `key_id`, `is_current` |
| `feature_key_store` | `_id`, `key_id`, `key_jid`, `key`, `key_type`, `creation_timestamp`, `expiry_timestamp` |

As configurações em nível de grupo (somente admin, announcement, ephemeral, aprovação de membros, toggles de histórico) ficam em **wa.db** `wa_group_admin_settings`, não aqui (4.3). Histórico de grupo: [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md).

### 3.7 Dispositivos

| Tabela | Colunas |
|--------|---------|
| `user_device` | `_id`, `user_jid_row_id`, `device_jid_row_id`, `key_index` |
| `user_device_info` | `user_jid_row_id`, `raw_id`, `timestamp`, `expected_timestamp`, `expected_ts_last_device_job_ts`, `expected_timestamp_update_ts`, `account_encryption_type` (estado ADV por usuário) |

### 3.8 Mídia, thumbnails, sidecar

| Tabela | Colunas | Nota |
|--------|---------|------|
| `message_media` | `message_row_id`, `chat_row_id`, `file_path`, `file_size`, `file_length`, `mime_type`, `media_name`, `media_key`, `media_key_timestamp`, `e2ee_media_key`, `file_hash`, `enc_file_hash`, `partial_media_hash`, `partial_media_enc_hash`, `original_file_hash`, `direct_path`, `message_url`, `metadata_url`, `media_duration`, `width`, `height`, `transferred`, `transcoded`, `is_offloaded`, `media_job_uuid`, `media_upload_handle`, `has_streaming_sidecar`, `media_caption`, `media_source_type`, `suspicious_content` | 55 colunas declaradas; `file_path` é guardado relativo à raiz de mídia (`C0KE.A0A` remove o prefixo da raiz, found). Campos de upload / download: [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| `message_thumbnail` | `message_row_id`, `thumbnail` | bytes do thumbnail dentro do DB |
| `message_streaming_sidecar` | `message_row_id`, `sidecar`, `chunk_lengths`, `timestamp` | streaming sidecar (dados de MAC de chunks para reprodução progressiva) no DB, não como arquivo |
| `media_hash_thumbnail` | `media_hash`, `thumbnail` | thumbnail indexado pelo hash do conteúdo |
| `media_refs` | `_id`, `path`, `ref_count` | contagem de referências por caminho de arquivo |
| `mms_thumbnail_metadata` | `message_row_id`, `direct_path`, `media_key`, `media_key_timestamp`, `enc_thumb_hash`, `thumb_hash`, `thumb_width`, `thumb_height`, `transferred`, `micro_thumbnail`, `insert_timestamp`, `handle` | |
| `extended_media_data` | `row_id`, `type`, `external_url`, `direct_path`, `preview_path`, `file_path`, `file_hash`, `media_key`, `enc_file_hash`, `mime_type`, `display_type` | |
| `offloaded_media` (offloaded-media.db) | `file_path`, `content_hash`, `file_size`, `media_source`, `media_state`, `is_offloadable`, `latest_reference_timestamp`, `refetch_timestamp`, `file_key` | |

### 3.9 Chamadas

| Tabela | Colunas |
|--------|---------|
| `call_log` | `_id`, `jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch` |
| `call_log_participant_v2` | `_id`, `call_log_row_id`, `jid_row_id`, `call_result` |

Sinalização de chamadas: [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md). As tabelas de newsletter (`newsletter`, `newsletter_message`, 45 e 17 colunas) são listadas apenas em 3.1.

### 3.10 Views e tabelas de integrity / AI

Views criadas em `C06980Hc.A0C` (found): `available_message_view`, `deleted_messages_view`, `deleted_messages_ids_view`, `chat_view` (duas variantes, escolhidas por `isGlobalChatDbMigrated`).

| Tabela | Colunas |
|--------|---------|
| `integrity_chat_info` | `chat_row_id` (PK), `is_reach_out`, `is_eligible_for_link_friction_banner` |
| `integrity_analysis_result` | `chat_row_id`, `last_message_row_id`, `result`, `timestamp`, `animation_played`, `trusted_timestamp`, `view_timestamp`, `holdout_group`, `experiment_group`, `chatting_untrusted_timestamp`, `replied_timestamp`, `block_logged_timestamp`, `trust_logged_timestamp`, `report_logged_timestamp` |
| `integrity_input_feature` | `chat_row_id`, `sender_reputation`, `country_mismatch`, `fetched_timestamp` |
| `tee_chat_request_table` | `message_row_id`, `chat_request_type`, `anchor_message_row_id`, `node_token`, `extra_data` |
| `tee_message_info_table` | `message_row_id`, `message_interaction_type`, `message_outgoing_status`, `message_source`, `message_replay_metadata` |
| `ai_thread_info` | `thread_id_row_id`, `title`, `creation_ts`, `variant`, `last_thread_messages_row_id`, `last_message_timestamp`, `title_source`, `unseen_message_count`, `origin_chat_row_id`, `selected_mode`, `selected_modes` |
| `bot_chat_info` | `chat_row_id`, `welcome_request_message_sent`, `bot_metrics_thread_origin` |
| `bot_memory_metadata` | `_id`, `message_row_id`, `memory_annotated_user_message_key_id`, `memory`, `memory_id`, `added`, `bot_jid_row_id` |

---

## 4. wa.db: contatos, listas de bloqueio, dados de confiança

### 4.1 Famílias (found, 88 classes)

| Família | Tabelas |
|---------|---------|
| Contatos | `wa_contacts`, `wa_contact_details`, `wa_contacts_created_within_wa`, `wa_contacts_pending_operations`, `wa_contact_refresh_pending`, `wa_contact_refresh_patch_log`, `wa_contact_storage_usage`, `wa_address_book`, `wa_org_contacts`, `wa_orgs`, `system_contacts_version_table` |
| Listas de bloqueio / permissão | `wa_block_list`, `wa_block_list_interop`, `wa_last_seen_block_list`, `wa_profile_photo_block_list`, `wa_about_block_list`, `wa_pix_block_list`, `wa_cover_photo_block_list`, `wa_status_view_allow_list`, `wa_status_view_black_list`, `wa_group_add_allow_list`, `wa_group_add_black_list`, `wa_stickers_allow_list`, `wa_profile_links_deny_list` |
| Business | `wa_biz_profiles` + 12 tabelas de detalhe `wa_biz_profiles_*` / `wa_biz_*`, `wa_vnames`, `wa_vnames_localized` |
| Grupos | `wa_group_admin_settings`, `wa_group_descriptions`, `group_membership_approval_requests`, `non_admin_group_membership_approval_requests`, `group_membership_count`, `group_membership_form_questions`, `group_relationship`, `subgroup_info`, `community_settings`, `member_suggested_groups_v2`, `group_suspension_appeal`, `group_non_wa_invites` |
| Trust / integrity | `wa_trusted_contacts`, `wa_trusted_contacts_send`, `wa_biz_integrity_signals`, `wa_biz_integrity_chat_settings`, `start_chat_trust_signals`, `wa_contact_server_signals` |
| Config | `wa_props`, `wa_newsletter_props`, `wa_coex_properties`, `wa_ml_models`, `wa_last_entry_point`, `wa_logging_entry_point` |
| AI / bots | `meta_ai_memory`, `wa_bot_profiles`, `wa_bot_commands`, `wa_subscriptions` |
| Outras | `status_ranking(_global)`, `wa_chat_ranking_scores`, `wa_storage_monitoring_data/_jobs`, `inbound_/outbound_connection_requests`, `dismissed_*`, `quick_promotion_payload` |

### 4.2 wa_contacts

36 colunas (`Nn5`), indexada por `jid` (TEXT, string JID bruta; um JID de telefone ou um JID `@lid`, não um id de linha `jid`):

`jid`, `is_whatsapp_user`, `status`, `status_timestamp`, `number`, `raw_contact_id`, `display_name`, `phone_type`, `phone_label`, `photo_ts`, `thumb_ts`, `photo_id_timestamp`, `given_name`, `family_name`, `wa_name`, `sort_name`, `nickname`, `company`, `title`, `status_autodownload_disabled`, `keep_timestamp`, `is_spam_reported`, `is_sidelist_synced`, `is_business_synced`, `disappearing_mode_duration`, `disappearing_mode_timestamp`, `disappearing_mode_support_disabled`, `history_sync_initial_phash`, `is_starred`, `is_wa_created_contact`, `sync_policy`, `status_emoji`, `is_contact_synced`, `is_reachable`, `external_user_state`, `fts_dirty_version`.

`wa_name` é o push name definido pelo contato; `display_name` / `given_name` vêm da agenda de endereços. Várias tabelas satélite usam triggers `BEFORE DELETE ON wa_contacts` (p. ex. `start_chat_trust_signals_contact_delete`, `contact_bd_for_business_integrity_signals`).

### 4.3 Outras tabelas de wa.db

| Tabela | Colunas |
|--------|---------|
| `wa_trusted_contacts` | (+ `jid`), `incoming_tc_token` BLOB, `incoming_tc_token_timestamp` LONG. Ver [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_trusted_contacts_send` | (+ `jid`), `sent_tc_token_timestamp` LONG, `real_issue_timestamp` LONG |
| `wa_biz_integrity_signals` | 17 colunas: `_id`, `jid`, `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `is_suspicious`, `join_date_ms`, `is_banned`, `phone_country_code`, `trust_tier`, `is_meta_verified`, `mv_friction_eligibility`, `integrity_tags`, `chat_row_id`, `last_sync_ts`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. Semântica completa no relatório de ban 5.1 |
| `start_chat_trust_signals` | (+ `jid`), `is_sender_suspicious`, `is_sender_new_account`, `created_ts` REAL |
| `meta_ai_memory` | `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER; índice `meta_ai_memory_memory_content_index` em `memory_content` |
| `wa_contact_server_signals` | `chat_jid`, `signal_type`, `value`, `update_ts` |
| `wa_group_admin_settings` | `jid`, `restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `creator_jid`, `is_suspended`, `group_state`, `require_membership_approval`, `member_add_mode`, `addressing_mode`, `history_enabled`, `group_history_toggle_mode`, `share_group_history_setting_mode`, `earliest_group_history_message_timestamp_ms`, `allow_member_labels`, ... (31 colunas) |
| `wa_storage_monitoring_data` | `db_name`, `table_name`, `table_size_bytes`, `index_size_bytes`, `table_unused_bytes`, `index_unused_bytes` (o cliente mede os tamanhos das próprias tabelas; ver 10.3) |

---

## 5. axolotl.db (estado Signal)

DDL atual (variantes mais recentes em `C44861sL`, tabelas registradas por `AbstractC11250Yd`; found). O material de chave é guardado em colunas BLOB `record`; nenhum byte de chave é documentado aqui.

| Tabela | Colunas | Função |
|--------|---------|--------|
| `identities` | `_id`, `recipient_id`, `recipient_type`, `device_id`, `registration_id`, `public_key`, `private_key`, `next_prekey_id`, `next_kyber_prekey_id`, `timestamp`, `account_encryption_attestation_type`, `mark_as_verified`, `mark_as_verified_action_seq`, ... | linha da própria identidade e identidades remotas (`recipient_type` separa contas de telefone e LID) |
| `sessions` | `_id`, `device_id`, `record`, `timestamp`, `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope` | sessões Double Ratchet |
| `prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `key_type` | prekeys de uso único |
| `signed_prekeys` | `_id`, `prekey_id` UNIQUE, `timestamp`, `record`, `key_type` | |
| `kyber_prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `last_resort_key` | prekeys pós-quânticas |
| `prekey_uploads` | `_id`, `upload_timestamp`, `key_type` | |
| `sender_keys` | `_id`, `group_id`, `device_id`, `record`, `timestamp`, `sender_account_id`, `sender_account_type`, `bucket_id` | sender keys de grupo |
| `message_base_key` | `_id`, `msg_key_remote_jid`, `msg_key_from_me`, `msg_key_id`, `recipient_id`, `recipient_type`, `device_id`, `last_alice_base_key`, `timestamp` | |
| `chat_stanza_queue`, `e2ee_stanza_queue`, `unordered_stanza_queue`, `preacks`, `stanza_sts` | `stanza_id`, `stanza_key` UNIQUE, `stanza_class`, `chat_jid`, `sender_jid`, `stanza_payload`, ... | persistência de stanzas recebidas antes do decrypt |

A camada Java do store Signal é código no estilo `signal_protocol_store` sobre essas tabelas. As prefs de crypto em nível de conta ficam em `keystore.xml` e `wacrypto.xml` (8.3), não aqui.

---

## 6. sync.db, companion_devices.db e os bancos menores

| DB | Tabelas e colunas principais |
|----|------------------------------|
| `sync.db` | `syncd_mutations` (`mutation_index` UNIQUE, `mutation_value` BLOB, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name`), `pending_mutations` (as mesmas mais `operation`, `is_ready_to_sync`), `collection_versions` (`collection_name` PK, `version`, `lt_hash` BLOB, `dirty_version`), `crypto_info` (`device_id`, `epoch`, `key_data`, `timestamp`, `fingerprint`, `stale_timestamp`), `missing_keys`, `msg_history_sync`, `history_sync_companion`, `peer_messages`, `placeholder_retry_message`, `rmr_response_error`. Protocolo: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md) |
| `companion_devices.db` | `devices`: `device_id`, `device_os`, `platform_type`, `last_active`, `login_time`, `logout_time`, `adv_key_index`, `full_sync_required`, `place_name`, `nickname`, ... Protocolo: [WA_LINKED_DEVICE_PAIRING.md](WA_LINKED_DEVICE_PAIRING.md) |
| `status.db` | `status`, `status_text`, `status_thumbnail`, `status_info`, `status_interactions`, `status_interactions_totals`, `status_seen_receipt`, `status_receipt_device`, `status_reply`, `status_send_part`, `status_privacy_custom_list`, `status_crossposting_v2/_v3`, ... mais `key_value_store` (`row_id`, `key`, `value`) |
| `backup.db` | `backups`, `backup_props` (`prop_name`, `prop_value`; linha `wa_db_schema_version`) |
| `chatsettings.db` | `settings`: `_id`, `jid`, `deleted`, `mute_end`, `muted_notifications`, `use_custom_notifications`, `message_tone`, `call_tone`, `status_muted`, `pinned`, `pinned_time`, `media_visibility`, `mute_reactions`, `wallpaper_*`, `auto_delete_media`, `transcription_locale`, `source_lang`, `target_lang`, `snooze_end_time`, `theme_id` (39 colunas) |
| `stickers.db` | `stickers` (`plain_file_hash`, `encrypted_file_hash`, `media_key`, `mime_type`, `sticker_pack_id`, `file_path`, `url`, `direct_path`, `emojis`, `is_lottie`, ...), `recent_stickers`, `starred_stickers`, `installed_sticker_packs`; `payments.db`: `methods` (`credential_id` PK, `country`, `issuer_name`, `type`, `balance_1000`), `contacts`, `receipts`, `tmp_transactions` |

---

## 7. Backups e crypt15

### 7.1 Arquivos de backup locais

| Padrão de nome (found, `AbstractC26994Bml`, `C29412Cpb`) | Conteúdo |
|----------------------------------------------------------|----------|
| `msgstore.db.crypt15`, `msgstore.db.crypt14` | backup completo do banco de conversas (regex `msgstore.db.crypt(\d+)`) |
| `msgstore-increment-<N>.db.crypt<V>` | backup incremental |
| `backup_settings.json.crypt<V>`, `status_backup.db.crypt<V>`, `commerce_backup.db.crypt<V>`, `chat_transfer_settings.json.crypt<V>` | configurações, status, commerce, configurações de transferência de conversas |
| `stickers.db.crypt<V>`, `chatsettingsbackup.db`, `wa-backup.db` | backups de stickers / configurações de chat / wa.db (nomes dos componentes abaixo) |

A raiz é `Backups/` sob a raiz externa de mídia (`C0KE.A02`; legado `Databases/`, `C0KE.A03`). A raiz é escolhida pela pref `external_storage_type` (o valor `scoped` é verificado em `C11160Xu.A07`; outros valores não enumerados); `EnumC046905z` pode resolver para `getExternalMediaDirs()[0]`, `getExternalStorageDirectory()`, diretórios externos específicos do app ou os diretórios internos. Contas secundárias usam `<root>/accounts/<dirId>` para caminhos `Media/WhatsApp ...` (`C0KE.A00`).

Componentes de backup (nomes `A0F` em subclasses de `CMN`, found): `stickers`, `stickers-db`, `wallpapers`, `payment-backgrounds-v2`, `chat-transfer`, `wa-db`, `commerce-db`, `status_db`, `offloaded-media.db`, `chatlock_backup`, `chat-settings`, `backup-settings`. `backup_prefs` mantém `<component>_backup_size` / `_backup_status` por componente (8.3).

Categorias de mídia na UI de backup (`EnumC26330BbW`, 17 valores): `CHAT_DB`, `SETTINGS`, `STATUS_DB`, `COMMERCE_DB`, `OTHER_DB`, `IMAGES`, `VIDEOS`, `AUDIO`, `VOICE_NOTES`, `VIDEO_NOTES`, `GIFS`, `DOCUMENTS`, `STICKERS`, `STICKER_PACKS`, `PROFILE_PHOTOS`, `EXCLUDED_STICKERS`, `OTHER`.

### 7.2 Prefixo de arquivo crypt15 (found)

`EnumC26325BbR`: `UNENCRYPTED` 0, `CRYPT14` 14, `CRYPT15` 15 (um sufixo `.crypt` sem número é a forma antiga; `CKv` casa com `.crypt`). O leitor crypt15 (`BN4.A09`) faz o parse de um protobuf delimitado `BackupPrefix` (`BCE`) antes do ciphertext:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `key_type_deprecated` | **1** | enum | tipo de chave antigo |
| `wa_provided_key_data` | **2** | bytes | dados de chave para chaves fornecidas pelo servidor |
| `e2ee_key_data` | **3** | message | dados de chave para backup com criptografia ponta a ponta |
| `backup_metadata` | **4** | `BD0` | ver abaixo |
| `passkey_encryption_metadata` | **5** | message | caminho de passkey (`parsePasskeyEncryptionMetadata`) |
| `key_type_new` | **6** | enum | tipo de chave atual |

Tipos de chave (`BdX`): `WA_PROVIDED` 0, `E2EE_DEPRECATED` 1, `E2EE_PASSWORD` 2, `E2EE_ENCRYPTION_KEY` 3, `E2EE_PASSKEY` 4.

Campos de `BackupMetadata` (`BD0`) (seleção): `app_version` **1**, `device_model` **2**, `jid_suffix` **3**, `backup_version` **4**, `backup_export_file_size` **38**, `cleaned_db` **39**, `backup_encrypted_hash_salt` **40**, `backup_encrypted_hash` **41**, `identifier_type` **42**, `lid_suffix` **43**, `display_suffix` **44**, mais cerca de 30 booleanos `*_migration_finished` (números 5 a 35). Na restauração, `EncBackupUtils` compara `jid_suffix` com o usuário registrado (`has-jid-user-mismatch`): um backup fica vinculado à conta que o criou.

O layout de cipher, KDF e MAC do ciphertext não foi lido aqui (unknown).

### 7.3 Material de chave de backup

| Arquivo (em `files/`) | Conteúdo | Evidência |
|-----------------------|----------|-----------|
| `encrypted_backup.key` | chave raiz de 32 bytes do backup com criptografia ponta a ponta (`C29861Ep.A09`, tamanho verificado == 32); gravada por `A04(...)`, possivelmente envolvida por uma chave de encapsulamento do KeyStore (`failed to load or create KeyStore encapsulation key`) | found |
| `encrypted_backup.key_id` | identificador da chave | found |
| `password_data.key`, `passkey_data.key` | estado das variantes de senha e passkey (os dados de passkey são JSON) | found |
| `vault_backup.key` | chave de vault de 32 bytes, gerada com `C00L.A0H(32)` e que se recusa a sobrescrever um arquivo ilegível (`vault backup key present but could not be read`) | found |
| `prf_derived_root_key.key`, `secret_code.key` | chave raiz derivada por PRF da passkey, chave do secret-code | nome found, conteúdo unknown |
| `backup_token`, `foa_backup_token` | arquivo de token (`CMc`, variante `foa_` para a conta do accounts-center) | found |

`AbstractC29801Ej` exclui `encrypted_backup.key(_id)`, `password_data.key`, `passkey_data.key`, `vault_backup.key` em conjunto (reset de chave).

### 7.4 Auto-backup do Android e o provider de migração (found)

| Item | Valor |
|------|-------|
| `android:allowBackup` | `true`, `fullBackupOnly=true`, backup agent `SystemBackupAgent` |
| `fullBackupContent` (`xml0003`) e `dataExtractionRules` (`xml0006`: cloud-backup e device-transfer) | excluem **todos** os domínios (`root`, `file`, `database`, `sharedpref`, `external`, `device_*`). Nada é transferido pela plataforma |
| `cross-platform-transfer platform="ios"` | declarado com o bundle id do iOS; a transferência passa por `OsMigrationAppDataService` (permissão `android.permission.BACKUP`) |
| `MigrationContentProvider` | exported, `readPermission com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` (protectionLevel `signature`), `grantUriPermissions=false`. URIs: `msg_store`, `unencrypted_msg_store`, `wa_db`, `chat_setting_store`, `sticker_store`, `wallpaper`, `share_preferences`, `media`, `chat_lock_passcode`. `DirectMigrationContentProvider` usa a mesma permissão. A finalidade (repasse ao app irmão do mesmo signer) é inferred |

---

## 8. SharedPreferences

### 8.1 Factory

`C00S` (SharedPreferencesFactory, `A04(C00G, name)`): retorna uma implementação customizada sobre `<dataDir>/shared_prefs/<name>.xml` (wrapper de arquivo `C052308r`; classes `C052408s` / `RRP`), recorrendo ao `getSharedPreferences(name, 0)` do sistema se o diretório não puder ser criado. Se os bytes em disco são XML padrão do Android não foi verificado no código (apenas a extensão do arquivo).

| Fato | Evidência |
|------|-----------|
| Conjuntos de nomes com tratamento especial em `AbstractC051008e` (`A02`, `A03`: feature flags da implementação; `A00`, `A01`, `A04`: conjuntos com escopo) | found; a semântica das flags de `C00G(boolean,boolean,boolean)` é unknown |
| O conjunto `A05` (`multi_account_metadata`, `group_history_usage`, `hatch_group_agent`, `hatch_group_agent_debug`, `smb_token_lockout_cooldown`) não deve ser criado por esta factory: mensagem `Pref not allowed to instantiate using SharedPreferencesFactory, use MultiAccountSharedPreferencesFactory` | found |
| Os nomes dos arquivos principais derivam de `AbstractC051108f`: `com.whatsapp_preferences` e `com.whatsapp_preferences_light` | found |
| `SharedPreferencesUsageRepository` (`C052508t`) registra tempos de carga por arquivo de prefs (`load`, `load2`), ignorando `ab-props`, `ab-props-back-up`, `ab-prechatd-props`, `ab-props-backup`, `dropped_wam_events`, `keystore` | found: telemetria sobre as próprias prefs |
| `C09E` (god-class obsoleta de "Me" e prefs) envolve `com.whatsapp_preferences_light` (`C1WL` case 23); muitos wrappers pequenos (`C1DH`, `C56902Wq`, `C0G1`) são visões desse mesmo arquivo | found |
| O `com.whatsapp_preferences` padrão é o arquivo Android simples; `chatCounts` é um arquivo separado (`RP5`) | found |

### 8.2 Arquivos por área (nomes encontrados no código)

| Área | Arquivos |
|------|----------|
| Core | `com.whatsapp_preferences`, `com.whatsapp_preferences_light`, `startup_prefs`, `reg_prefs`, `register_phone_prefs`, `registration.verifyphone.VerifyPhoneNumber`, `registration.app.phonenumberentry.RegisterPhone`, `registration.app.verifyphone.VerifyPhoneNumber`, `multi_account_metadata`, `account_linking_prefs`, `fb_credentials_prefs`, `fb_linked_account`, `accounts_center_registration_prefs` |
| Flags | `ab-props`, `ab-props-backup`, `ab-props-back-up`, `ab-prechatd-props`, `groupAbProps`, `network_resources_pref` |
| Crypto | `keystore`, `wacrypto`, `security_prefs`, `nc_prefs`, `chat_lock`, `migration_export`, `AccountDefenceLocalDataRepository_prefs` |
| Backup / sync | `backup_prefs`, `chat_transfer_prefs`, `syncd_prefs`, `contact_sync_prefs`, `device_capabilities`, `companion_mode_prefs` |
| Funcionalidades | `username_prefs`, `meta_ai_prefs`, `bonsai_prefs`, `paa_prefs`, `status_prefs`, `newsletter_prefs`, `voip_prefs`, `route_selector_prefs`, `interop_ui`, `interop_badge_prefs`, `avatar_prefs`, `bloks`, `privacy_disclosure_store`, `user_notice_prefs`, `tos_gating_prefs` |
| Telemetria | `critical_event_client_prefs`, `anr_shared_prefs`, `time_spent_prefs`, `dropped_wam_events`, `wam_prefs`, `chatCounts` |
| SDK de terceiros | `com.google.android.gms.appid`, `com.google.firebase.messaging`, `WebViewChromiumPrefs` (sistema) |

### 8.3 Chaves importantes (todos os nomes de chave encontrados em 2.26.41.6; valores não reproduzidos)

| Arquivo | Chave | Tipo / uso |
|---------|-------|-----------|
| `startup_prefs` | `registration_state` | int; predicados de `C06810Gk`: 0/1 inicial, 3, 4, 5, 8 (flash verify), 12, 15, 17 (OTP por e-mail), 20, 23 |
| | `startup_migrated_version` | int; alvo **20**, `WaStartupSharedPreferences` executa as migrações abaixo dele |
| | `push_name` | nome de exibição próprio |
| | `force_db_check`, `force_wadb_check` | forçam verificação de integridade de msgstore / wa.db (limpas por `C0HS.BoJ`, `C12650bW.onCreate`) |
| | `pending_repair_db_name`, `pending_repair_db_file_id`, `pending_repair_corruption_type`, `pending_repair_attempt_count`, `pending_repair_request_id`, `pending_repair_timestamp`, `pending_repair_gate_suppressed` | fila de reparo de banco de dados |
| | `privacy_fingerprint_enabled`, `night_mode`, `client_server_time_diff` (lida por `C050708b`) | |
| `com.whatsapp_preferences_light` | `registration_jid`, `registration_lid`, `cc`, `ph`, `self_lid`, `registration_initialized_time`, `registration_success_time_ms`, `registration_wipe_info_timestamp`, `reg_attempts_verify_code` | identidade desta instalação (limpas por `RegistrationManager.A0I`) |
| | `adv_raw_id`, `adv_current_key_index`, `adv_timestamp_sec`, `phoneid_id`, `phoneid_timestamp` | estado ADV / phone id |
| | `privacy_last_seen`, `privacy_profile_photo`, `privacy_status`, `privacy_online`, `read_receipts_enabled`, `privacy_token_batch_offset_sec` | configurações de privacidade (`C18260lS`, `C09E.A0S()`) |
| | `md_messaging_enabled`, `last_login_time`, `last_daily_cron`, `next_randomized_daily_cron`, `nct_salt` | flag multi-device, controle do cron, salt do tctoken ([WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md)) |
| `backup_prefs` | `gdrive_state`, `backup_provider`, `backup_encryption_method`, `encrypted_backup_fleet_migration_state`, `encrypted_backup_num_attempts_remaining`, `google_restore_result`, `msg_restore_timestamp`, `last_seen_app_version`, `device_backup_integration_enabled`, `blocking_restore_in_progress`, `cloud_api_type`, `restore_second_verification_needed` | estado de backup e restauração (`C22090sX`) |
| `keystore` | `server_static_public`, `server_static_pq_public`, `client_static_keypair_pwd_enc`, `client_static_keypair_enc_success`, `can_user_android_key_store`, `remaining_auth_key_rotation_attempts` | chaves estáticas do Noise ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md), [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md)) |
| `wacrypto` | `signed_prekey_id_seed_migration_completed` | migração do seed de id de prekey Signal |
| `ohai_key_config` (nome da pref em `C53596Nzj`) | `public_key` e campos de key-config | chave do gateway OHAI |
| `syncd_prefs` | `syncd_dirty`, `syncd_bootstrap_state`, `syncd_bootstrapped_mutations` (set), `mutation_counter` | bootstrap do app-state sync |
| `companion_mode_prefs` | `previously_logged_out_from_primary` | estado do companion |
| `username_prefs` | `username_reservation_state`, `username_pin` | ver [WA_USERNAME.md](WA_USERNAME.md) |
| `route_selector_prefs` | `media_conn` | rota de mídia em cache (lista de hosts e dados de auth; [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md)) |
| `ab-props` | chaves de string numéricas (códigos de config), `ab_props:sys:last_refresh_time`, `ab_props:sys:config_hash`, `ab_props:sys:last_version`; `com.whatsapp_preferences` guarda `ab_props:hash_v2` | cache de AB props; `ab-props-backup` é a cópia anterior |
| `chatCounts` | contadores por chat, `thread_user_secret` (32 bytes aleatórios, base64) | `WamThreadIdManager` aplica HMAC nos thread ids com ele; `RP5.A0w` o mantém após um reset |

---

## 9. Layout de arquivos, caches e mídia

### 9.1 `files/` interno (found, salvo indicação)

| Caminho | Conteúdo |
|---------|----------|
| `me` | registro `Me` serializado em Java (`C9V.A01`, campos incluem `cc`, `number`); `me.jpg` / `me_old.jpg` foto de perfil |
| `rc2` | valor aleatório de 160 bits criptografado com AES/OFB, gerado no primeiro uso a partir de duas strings de entrada (`K49.A0v`, `C00L.A0G`; inferred: código do país e número); finalidade inferred (secret de registro). Excluído pelos runnables de wipe `RunnableC29329CoG`, `RunnableC46625KYz` |
| `backup_token`, `foa_backup_token`, `encrypted_backup.key*`, `vault_backup.key` | seção 7.3 |
| `invalid_numbers`, `login_failed`, `customTSValues`, `emoji` | pequenos arquivos de estado (`IJU`, `C06850Go`) |
| `statistics.json`, `network_statistics.json` | contadores rx / tx (`C17B`, `C17J`; chaves `statistics`, `bytes`, `timestamp`, `rx_data`, `tx_data`) |
| `Logs/` | arquivos de log (10.1) |
| `decompressed/libs.spo/` (+ `.superpack_version`) | bibliotecas descompactadas em runtime por `C0EE`; **excluídas de todo wipe** |
| `mobileconfig/` | `mc_overrides.json`, `id_name_mapping.json` (`C053409d`) e o store de config |
| `falco/`, `wam/` | engines de telemetria (10) |
| `Stickers/`, `Drafts/`, `GroupHistory/`, `Payment Backgrounds/`, `Wallpapers/`, `.trash/`, `biz_directory/`, `privacy_disclosure/<version>/`, `downloadable/`, `NetworkResource/`, `MNSResolverCache/`, `app_state/` | caches de funcionalidades (`C0I1`, `C58398QKk`, `C27574Bxe`, `MNSStreamRuntime`, `C06110Cn`) |

Outros diretórios privados nomeados pelo switch de configuração de armazenamento (`AbstractC13030c9`): `lib-compressed`, `app_secure_shared`, `app_sigquit`, `modules`, `app_optsvc_analytics`, `app_overtheair`, `app_qpl`, `app_light_prefs`, `cache/secure_shared`, `files/secure_shared`, `app_minidumps`, `app_fb-forker-tmp`.

### 9.2 `cache/` (found)

| Dir | Nota |
|-----|------|
| `thumb_decoded_cache` | LRU em disco, **52428800 bytes (50 MiB)** (`C33000EZy`) |
| `webp_static_cache`, `stickers_cache`, `avatar-temporary`, `interop_image_cache`, `tigon_http_client`, `ML_MODEL`, `hatch_space_images`, `meta_ai_thread_photo_uploads` | caches de imagem / rede / modelo |
| `Profile Pictures/` | com escopo de conta (`C28025CFb.A01` retorna o diretório de cache; `QLH` constrói `Profile Pictures`) |

### 9.3 Contas secundárias (found)

`getDir("account_switching")` (= `app_account_switching/`) guarda `active_account` (o id do diretório ativo, `C00W`) e a lista de contas (`C25160AsA`). Os dados de uma conta secundária ficam em `<dataDir>/accounts/<dirId>/{databases,files,cache}` (`C28025CFb`) e sua mídia em `<root>/accounts/<dirId>`; a conta default usa os diretórios normais. `account_switcher.db` e as prefs de multi-conta são compartilhados.

### 9.4 Raiz externa de mídia (found)

`<root>/Media/WhatsApp <Category>/` com categorias `Images`, `Video`, `Audio`, `Documents`, `Voice Notes`, `Video Notes`, `Animated Gifs`, `Stickers`, `Sticker Packs`, `Profile Photos`, `Backup Excluded Stickers` (`AbstractC26994Bml`), subpastas `Sent`, `Private`, `.Thumbs` (`*.prog.thumb.jpg`, `C0I1.A08`), `.Shared`, marcadores `.nomedia`. `message_media.file_path` guarda a parte após a raiz.

---

## 10. Logs e telemetria mantidos no dispositivo

### 10.1 Logs (found)

| Arquivo | Detalhe |
|---------|---------|
| `files/Logs/whatsapp.log`, `whatsapp.tmp` | log em texto, cabeçalho `==== logfile version=2.26.41.6 level=4 ====`; a rotação compacta em `.gz` com data (`Log.rotate`, `AbstractC28128CKx.A00`). `C24971Ap6` reúne `Logs` com o diretório de db para exportação de suporte / bug-report |
| `app_minidumps/`, `<dir>/minidumps`, `crash_upload/` | dumps de crash nativos e a área de staging do upload (`C0FQ`, `JJ1`, `CKN`, `ExceptionsUploadService`) |
| `anr_report_<n>.dmp`, `anr_shared_prefs` | relatórios de ANR (`C45432Jrw`) |
| `cache/qpl`, `app_qpl` | traces do QuickPerformanceLogger |

### 10.2 Engines de telemetria

| Caminho | Engine | Evidência |
|---------|--------|-----------|
| `files/wam/` | diretório de runtime WAM passado a `WAJContextInitWAMRuntime` (JNI) | `RunnableC29323CoA`; prefs `dropped_wam_events` e `wam_prefs` |
| `files/falco/` | logger de eventos em `libffsingletonmerged.so` | strings nativas abaixo |
| `files/mobileconfig/` | store do Mobile Config | `C053409d` |

Arquivo SQLite do Falco `FFLogger.sql` (localização inferred: o Java cria `files/falco/`, o nome do arquivo é uma string na lib nativa): tabelas presentes nas strings de schema nativas (found): `event`, `buffer_event`, `upload` (`request_data`, `num_events`, `is_compressed`, `compression_method`), `claim` (`principal_subject_hash`, `claim`, `expires_at`), `collection_constraint`, `event_config` (`event_config_hash` UNIQUE, `event_name`, `sampling_rate`, `collection_constraint_ref`, `is_deidentified`), `checksum`, `amendment_outbox`, índice `event_0` em `event(requested_latency)`; `batch` faz join por `identities_hash`. `fflogger_health_counters.bin` guarda contadores de autoinstrumentação (`mobile_health_counters`). O lado Java apenas cria o diretório.

### 10.3 Automedição

`wa_storage_monitoring_data` / `_jobs` de wa.db (tamanhos por tabela e bytes não usados por `db_name`) e as estatísticas de carga de prefs (8.1) são telemetria que o cliente mantém sobre o próprio armazenamento. O pipeline de eventos WAM em si está fora do escopo aqui.

---

## 11. O que é apagado, e quando

### 11.1 Operações

| Operação | Entrada (2.26.41.6) | Efeito |
|----------|---------------------|--------|
| Excluir conta / reset de dados locais | `C25007Aph.A0L` depois `A02` (`removeDatabasesAndResetState`) | wipe local completo, 11.2 |
| Companion removido | `C25007Aph.A0M` (`deleteCompanionCleanup`) | `ActivityManager.clearApplicationUserData()` (fallback `pm clear <package>`, fallback para `A02`) |
| Re-register | `RegistrationManager.A06` (`reregister reason=`) | limpa as prefs de registro e `me`, 11.3 |
| Unregister do dispositivo | `RegistrationManager.A0F` | interrompe a conexão com `should_unregister=true`, exclui `me`, limpa o estado |
| Logout (primário, com multi-conta) | `LogoutManager` (`AccountLogoutMutation`, w:mex) | logout no servidor, conta marcada como logged out; os dados permanecem até o usuário remover a conta deslogada (11.4). Se o primeiro passo exclui algo localmente não foi rastreado (unknown) |
| Remover conta deslogada | `LogoutManager.removeLoggedOutAccountWithCleanup` | remove a entrada da conta, depois `deleteDefaultAccountDirectories` ou `deleteSecondaryAccountDirectories`, depois o estado de backup do GMS |

### 11.2 Exclusão de conta (`C25007Aph.A02`, found)

| Alvo | Ação |
|------|------|
| Stores em memória, gerenciadores de funcionalidades | limpos; `last_contact_full_sync` = -1 |
| Bancos de dados | o delete de cada helper (`A0D`, `A0N`): msgstore via `C0HC` (`msgstore-manager/deletedb/result`), wa.db (`deleteaccountconfirm/wa-db-delete-incomplete` é um erro se restarem arquivos), commerce, `emojidictionary`, store de language-pack, `MediaJobDataStore`, stores de history-sync, diretório business (`files/biz_directory`) |
| `files/` | todas as entradas exceto `decompressed`; `Logs` é mantido quando a flag `z` está definida (caminho companion) |
| Raiz externa | `Backups/` removido e recriado vazio, arquivos de `Databases/` removidos (`AbstractC28132CLd.A04`), somente se o estado do armazenamento externo for utilizável |
| `com.whatsapp_preferences` | `clear()` e depois `version` é regravada com `2.26.41.6` |
| `backup_prefs` | `clear()`, mas `last_seen_app_version` e `device_backup_integration_enabled` são restauradas |
| `chatCounts` | todas as chaves removidas exceto `thread_user_secret` (`RP5.A0A`) |
| Outras prefs | `avatar_prefs`, os arquivos de registro e VerifyPhone, registro de companion (`registration_device_id`, `companion_registration_state` = 0), algumas prefs de funcionalidades |
| WebView | cookies e web storage excluídos, também para perfis nomeados quando multi-perfil está disponível |

### 11.3 Reregister / unregister (found)

`RegistrationManager.A0I` remove `registration_jid`, `registration_lid`, `cc`, `ph` e o `registration_wipe_info_timestamp`; `A0A` limpa as prefs das duas telas de registro; o arquivo `me` é removido (`rm-me`).

### 11.4 Diálogo de conversas deslogadas (`FilesDeletionUtility`)

Exclui a raiz externa do usuário deslogado, `cacheDir`, toda entrada de `filesDir` exceto `decompressed`, o diretório de arquivos da conta secundária, e então chama o delete dos helpers de DB; uma falha na exclusão de wa.db lança exceção e o diálogo reporta um erro (`FilesDeletionUtility/deleteInternalFiles/wa-db-delete-incomplete`).

### 11.5 Exclusão de arquivos multi-conta (`AccountSwitchingFileManager.deleteDefaultAccountDirectories`)

Para a conta default: `shared_prefs` é excluído exceto uma allow-list; `databases` é excluído exceto `account_switcher.db` (e suas variantes de sufixo); os demais diretórios são removidos por inteiro.

---

## 12. Notas sobre Baileys (mapeamento inferred)

O Baileys mantém credenciais e um store por chave (`creds`, pre-key, session, sender-key, app-state-sync-key / -version, lid-mapping, device-list, tctoken). As contrapartes conceituais no Android (inferred; nenhum código as vincula):

| Estado do Baileys | Armazenamento no Android |
|-------------------|--------------------------|
| `session`, `pre-key`, signed pre-key | `axolotl.db` `sessions`, `prekeys`, `signed_prekeys` (+ `kyber_prekeys` no Android) |
| `sender-key`, `sender-key-memory` | `axolotl.db` `sender_keys`; distribuição por dispositivo em msgstore `group_participant_device` |
| app-state sync key / version | `sync.db` `crypto_info` (`key_data`, `epoch`), `collection_versions` (`lt_hash`) |
| lid mapping | msgstore `jid_map` (+ `lid_display_name`) |
| device list | msgstore `user_device`, `user_device_info` |
| `tctoken` | wa.db `wa_trusted_contacts(_send)` |
| `creds.me`, registration id, ADV | `files/me`, prefs `adv_*`, linha de `identities` |

Uma sessão Baileys não tem equivalente da tabela `message`; excluir seu auth state é a contraparte do wipe em 11 e exige um novo vínculo.

---

## 13. Casos de erro e pegadinhas

| Sintoma | Causa | Correção / nota |
|---------|-------|-----------------|
| `msgstore/upgrade version 1 to N` nunca aparece | o `user_version` de msgstore é sempre 1 | leia `props.msgtore_db_schema_version` para o estado real do schema |
| msgstore "restored-db-not-indexed" / `RestoredIndexesPending` | DB restaurado de um backup; índices criados de forma lazy | chaves `props` `MessagesDBHelper_*`; a execução termina de forma assíncrona |
| `still-corrupt-after-repair`, `delete-superseded-by-new-repair` | a verificação de integridade falhou (`C0HC.checkhealth`) | fila em `startup_prefs` `pending_repair_*`; `force_db_check` |
| wa.db fica vazio de repente após atualização | o switch de upgrade descartou tabelas (versões 3 a 94) ou o hash do schema mudou | wa.db é reconstruível a partir do servidor e da agenda de endereços |
| `deleteaccountconfirm/completion-blocked/wa-db-files-remain` | os arquivos de wa.db não puderam ser excluídos | tentar novamente; o wipe é abortado com `Be5` |
| A restauração recusa um backup (`has-jid-user-mismatch`) | `BackupMetadata.jid_suffix` difere da conta | restaurar com o mesmo número |
| `backup-file-crypt15/prefix null` | arquivo vazio ou não é crypt15 | verificar o prefixo delimitado (7.2) |
| `vault backup key present but could not be read` | `vault_backup.key` ilegível | o código se recusa a gerar um substituto para não sobrescrever um arquivo recuperável |
| `Pref not allowed to instantiate using SharedPreferencesFactory` | pref exclusiva de multi-conta criada com a factory errada | usar `MultiAccountSharedPreferencesFactory` |
| Os dados de uma conta deslogada permanecem | o logout não exclui os dados da conta (11.1) | remover a conta explicitamente |

---

## 14. Distinções importantes

| Não confundir | Diferença |
|---------------|-----------|
| `msgstore.db` vs `wa.db` | mensagens, chats e linhas `jid` vs contatos, listas de bloqueio, tokens de contatos confiáveis, caches de business e integrity; ids de linha de JID existem apenas em msgstore, as chaves de wa.db são strings JID brutas |
| `jid._id` vs JID bruto | as colunas `*_jid_row_id` são ids de linha de msgstore; as tabelas `wa_*` usam `jid` TEXT |
| `user_version` do SQLite vs versão do schema | msgstore sempre 1; wa.db 95; o schema é um hash em `props` (msgstore) ou uma tag (wa.db) |
| Auto-backup do Android vs backup de conversas | o auto-backup exclui tudo; o backup de conversas é o arquivo `crypt15` próprio do app na raiz externa |
| arquivo crypt15 vs arquivos de chave | ciphertext em `Backups/`; chaves em `files/*.key` (nunca na mesma pasta) |
| `com.whatsapp_preferences` vs `_light` | prefs Android simples (limpas até uma chave de versão) vs o arquivo da implementação customizada usado por `C09E` (identidade, privacidade, flags) |
| `ab-props` vs `wa_props` | códigos de experimento AB (prefs) vs props de conta do servidor (tabela de wa.db) |
| Logout vs exclusão de conta | o logout marca a conta; a exclusão apaga DBs, arquivos, Backups, prefs (11) |
| Falco vs WAM | Falco é o logger de eventos SQLite em uma lib nativa; `wam/` é o diretório de runtime WAM; ambos são telemetria |
| Arquivos de mods de terceiros | bancos extras, logs de stanza ou diagnósticos de hook não são criados pelo app original e não são cobertos |
---

## 15. Layout e ciclo de vida

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

## 16. Não coberto e unknown

| Tópico | Status |
|--------|--------|
| Atribuição de DB por tabela para as 306 + 422 classes de tabela além das verificadas | tamanhos dos conjuntos found; mapeamento de cada classe ao seu banco pelo grafo DI não rastreado (inferred por FKs e nomes) |
| Tipos de coluna, defaults e NOT NULL para tabelas construídas com funções helper | o decompilador omite alguns; apenas os nomes são listados |
| As cerca de 250 tabelas restantes de msgstore, as demais tabelas de wa.db e status.db | nomes listados nas famílias; colunas não extraídas |
| Formato do ciphertext crypt15, KDF, MAC; conteúdo das submensagens de `BackupPrefix` | unknown |
| Formato XML padrão em disco da implementação customizada de prefs | não verificado |
| Lista completa de chaves de cada arquivo de prefs (centenas de chaves) | apenas os arquivos e chaves nomeados em 8.3 |
| Significado das flags de `C00G`, ids de tipo de add-on, valores de `registration_state` | parcialmente nomeado |
| Versões de `sync.db`, `chatsettings.db`, `stickers.db`, `commerce.db`, `daily_metrics.db`, `location.db` | não resolvidas |
| Finalidade de `files/rc2`, `files/key` | `rc2` inferred; `key` não resolvido |
| Se o logout primário sozinho exclui dados locais | não rastreado |
| Comportamento em runtime, tamanhos de arquivo, conteúdo do WAL | apenas análise estática |
