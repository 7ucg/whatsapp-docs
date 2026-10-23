<!-- src-sha1: 6effa8dc57f2e12a66c37c7cae9d875028a5d55e -->
# WhatsApp التخزين المحلي — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-23
**النطاق:** قواعد بيانات SQLite (الأسماء، الموقع، المحرك، الإصدارات، إطار الجداول)، الجداول والأعمدة الرئيسية في msgstore.db وwa.db، وaxolotl.db وsync.db والقواعد الأصغر، نسخ crypt15 الاحتياطية وملفات مفاتيح النسخ الاحتياطي، قواعد النسخ الاحتياطي التلقائي في Android وموفّر المحتوى (content provider) الخاص بالترحيل، مصنع SharedPreferences وجرد المفاتيح، بنية الملفات والذاكرة المؤقتة (cache)، ملفات السجلات والقياس عن بُعد (telemetry)، ما تزيله عمليات تسجيل الخروج / إلغاء التسجيل / إعادة التسجيل / حذف الحساب

---

## 1. ما الذي يُخزَّن وأين

جميع العبارات مستمدة من التحليل الساكن لـ APK المفكَّك ومكتباته الأصلية المرفقة. لم تُقرأ أي بيانات من جهاز. المستوى: **found** = مقروء في الشيفرة أو manifest أو سلاسل المكتبات الأصلية؛ **inferred** = مستنتج من الشيفرة؛ **unknown** = غير محسوم. الأسماء المشوَّشة (obfuscated) كما يعرضها JADX للإصدار 2.26.41.6 وتتغير في كل بناء.

### 1.1 خريطة التخزين

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

| الموقع | المحتوى | يبقى بعد النسخ الاحتياطي التلقائي في Android |
|----------|---------|------------------------------|
| `databases/` | جميع ملفات SQLite | لا: كل النطاقات (domains) مستثناة (8.1) |
| `shared_prefs/` | الإعدادات، الـ flags، المفاتيح | لا |
| `files/`, `cache/` | ملفات المفاتيح، الذاكرة المؤقتة، السجلات | لا |
| الجذر الخارجي `Backups/` | نسخة احتياطية مشفرة للمحادثات (crypt15) | غير منطبق: آلية نسخ احتياطي خاصة بالتطبيق (7) |

### 1.2 حقائق المحرك (found)

| الحقيقة | الدليل |
|------|----------|
| SQLite هو البناء المرفق `io.requery.android.database.sqlite` وليس بناء الإطار (framework) | الحزمة في `java_src` |
| لا يوجد SQLCipher: لا `PRAGMA key` ولا سلسلة `sqlcipher` في أي مكان في `java_src` | grep؛ ملفات قواعد البيانات نص صريح (plaintext) في حالة السكون داخل sandbox التطبيق |
| WAL مفعّل لكل المساعدات (helpers) المبنية على `AbstractC11350Yn` (`setWriteAheadLoggingEnabled(true)`) | `AbstractC11350Yn`؛ نقطة فحص (checkpoint) عبر `PRAGMA wal_checkpoint(FULL)` |
| msgstore يُفتح مع `PRAGMA synchronous=NORMAL` و`cache_size` اختياري (flag **20777**) و`PRAGMA secure_delete=1` | `C06980Hc.onOpen`؛ يُبلَّغ عن فشل تفعيل secure_delete بالرسالة `db-integrity/enable-secure-delete/error/not-enabled` |
| `PRAGMA foreign_keys=ON` مضبوط لـ sync.db وpaa.db وdaily_metrics.db، وليس لـ msgstore.db | `AbstractC12530bK`, `AbstractC197088a3`, `AbstractC16650iN`؛ msgstore يمرّر الحذف المتسلسل (cascade) عبر triggers (2.3) |

---

## 2. قواعد بيانات SQLite

### 2.1 الجرد

أسماء الملفات literals (`getDatabasePath(...)` / مُنشئات الـ helpers). أعداد الجداول هي عدد فئات تعريف الجداول في وحدة DI التي تغذي الـ helper (2.3).

| الملف | Helper / الوحدة (2.26.41.6) | الإصدار / الترحيل | فئات الجداول | الدور | المستوى |
|------|-----------------------------|---------------------|---------------|------|------|
| `msgstore.db` | `C06980Hc` (factory `C0HH`) | `user_version` في SQLite ثابت عند 1؛ بصمة المخطط (schema fingerprint) في `props` (2.4) | 306 (factory `C1S0`) | الرسائل، المحادثات، JIDs، الإيصالات، المكالمات، القنوات الإخبارية (newsletters)، النزاهة (integrity)، الذكاء الاصطناعي، TEE | found / نسبة المجموعة inferred |
| `wa.db` | `C12650bW` | **95** (`creating contacts database version 95`) | 88 (منفِّذو `C8ZL`) | جهات الاتصال، قوائم الحظر، ملفات الأعمال، رموز جهات الاتصال الموثوقة، إشارات النزاهة | found |
| `axolotl.db` | `C44861sL`، الجداول `AbstractC11250Yd` | **40** | 15 | جلسات Signal، prekeys، sender keys، طوابير stanza | found |
| `sync.db` | `AbstractC12530bK` (helper `X.1sK`) | ترحيلات `ALTER` تدريجية حتى v50 على الأقل؛ الرجوع لإصدار أقدم = إعادة ضبط | 10 | مزامنة حالة التطبيق، مزامنة السجل، رسائل الأقران (peer) | found، الإصدار unknown |
| `status.db` | `C41891nD` | **2** (`StatusDbHelper creating status database version 2`) | 29 (`AbstractC11620Zo`) | منشورات الحالة وتفاعلاتها | found |
| `backup.db` | `C44881sN` | **1** | `backups`, `backup_props` | محاسبة النسخ الاحتياطي؛ `backup_props` يحوي `wa_db_schema_version` | found |
| `chatsettings.db` | `C11200Xy("chatsettings.db")` | unknown | `settings` (inferred) | كتم/تثبيت/نغمة/خلفية/سمة لكل محادثة | الاسم found، الجدول inferred |
| `stickers.db` | الوحدة `AbstractC149676Ty` | unknown | 18 (الوحدة تسجّل أيضًا `offloaded_media*` و`backups` و`backup_props`) | حزم الملصقات | found |
| `offloaded-media.db` | `CMN` (مكوّن النسخ الاحتياطي) | unknown | `offloaded_media`, `offloaded_media_staging` (النسبة inferred) | فهرس الوسائط المُفرَّغة (offloaded) | found / inferred |
| `payments.db` | helper مجهول من `C1S0`، `AbstractC22520tH` | **5** | `contacts`, `methods`, `receipts`, `tmp_transactions` | وسائل الدفع | found |
| `commerce.db` | `C27743C3e` | unknown | unknown | بيانات التجارة؛ له نسخة احتياطية `commerce_backup.db` | الاسم found |
| `companion_devices.db` | `C48701zE` | **27** | `devices` (+ أخرى) | الأجهزة المرتبطة كما يراها الجهاز الرئيسي | found |
| `paa.db` | `ManagedAccountDbHelper` (`AbstractC197088a3`) | ترحيلات V1 إلى V7 | `paa_connection`, `contact_metadata`, `group_metadata` | بيانات الحساب المُدار (حساب بموافقة الوالدين) | found |
| `daily_metrics.db` | `AbstractC16650iN` | unknown | `poll_event_logging`, `poll_daily_participant`, `comments_event_logging`, `pnh_daily_event_logging`, `community_home_action_logging`, `snapl_payload` | عدّادات أحداث يومية | found |
| `qp_payload.db`, `location.db`, `fa_events.db`, `media.db`, `account_switcher.db` | دوال جلب المسار (`C23985AVo`, `C33961Wh`) | unknown | unknown | الترقيات السريعة، الموقع المباشر، التحليلات الموحَّدة (federated)، مهام الوسائط (inferred)، قائمة الحسابات | الاسم found |
| `sqlite_vec.db` | `MessageEmbeddingsStore` | unknown | جداول المتجهات (unknown) | تضمينات الرسائل (embeddings) على الجهاز؛ موجودة فقط عند التفعيل | found |
| `emojidictionary.db`, `hsmpacks.db`, `events.db` | `C8JP`, `C6UR` | unknown | unknown | قاموس الإيموجي، حزم القوالب، الأحداث | الاسم found |
| `wa-backup.db`, `msgstore.db-backup` | `CMN` / `C26042BNa`, `C0KE` | غير منطبق | غير منطبق | نسخ أمان محلية من wa.db / msgstore | found |
| `migration_prefetcher.db`, `migration_import_metadata.db`, `migration_export_metadata.db` | `C23985AVo` | unknown | unknown | حالة نقل المحادثات / ترحيل نظام التشغيل؛ `migration_prefetcher.db` يحذفه `C28152CMi` | الاسم found |
| `androidx.work.workdb` | WorkManager (`no_backup/`) | Room | قياسي | طابور المهام | inferred من فئات Room (`room_master_table`) |

### 2.2 أي قاعدة بيانات تحوي الجداول المذكورة في التقارير الأخرى

| الجدول | ملف DB | فئة الجدول | الدليل | التقرير |
|-------|---------|-------------|----------|--------|
| `wa_trusted_contacts`, `wa_trusted_contacts_send` | `wa.db` | `C23627AHs`, `C23628AHt` (`C8ZL`) | helper الخاص بـ wa.db يعيد إنشاءها؛ المخازن تقرأ عبر `C12810bn` من helper الخاص بـ wa.db | [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_biz_integrity_signals` | `wa.db` | `C53116Nmn` (`C8ZL`) | found | [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) 5.1 |
| `start_chat_trust_signals` | `wa.db` | `AI0` (`C8ZL`)، trigger على `wa_contacts` | found | تقرير الحظر 5.2 |
| `integrity_chat_info` | `msgstore.db` | `C08970Ox`، trigger `chat_bd_for_integrity_chat_info_trigger` على `chat` | found، النسبة عبر FK إلى `chat` | تقرير الحظر 5.3 |
| `meta_ai_memory` | **`wa.db`** | `C23621AHm` (`C8ZL`) | found؛ الأعمدة `memory_id`, `memory_content`, `bot_jid_row_id` | [WA_META_AI.md](WA_META_AI.md) |
| `bot_memory_metadata`, `bot_chat_info`, `ai_thread_info` | `msgstore.db` | `C08640Nq`, `C08610Nn`, `C0MO` | ضمن مجموعة الـ 306 فئة | تقرير Meta AI |

`meta_ai_memory` موجود في `wa.db` وليس في `msgstore.db`: فئته تنفّذ `C8ZL` الذي لا يمرّ عليه إلا helper الخاص بـ wa.db (`C12650bW.onCreate` مع `new C08050Lj("wa.db")`). العمود `bot_jid_row_id` يشير إلى صف `jid` في msgstore، فهو مرجع ناعم (soft reference) عبر قواعد بيانات مختلفة (inferred؛ لا يمكن وجود foreign key عبر ملفات).

### 2.3 إطار الجداول (كيف تُعرَّف المخططات)

الجداول ليست مكتوبة كسلاسل SQL. كل جدول فئة تنفّذ `InterfaceC08060Lk` (في wa.db: الواجهة الفرعية `C8ZL`) بثلاث دوال hooks (found):

| Hook | الغرض |
|------|---------|
| `ASa(ctx, builder)` | تعريف الأعمدة: بنّاء `C08080Lm`، `.A02` = الاسم، `.A00` = النوع `EnumC08100Lo` (`INTEGER`, `TEXT`, `REAL`, `BLOB`, `LONG`, ...)، وأعلام للمفتاح الأساسي / not null / القيمة الافتراضية |
| `ASX(ctx, builder)` | تعريف الفهارس (`CRN`, `CRJ` = فهرس شرطي) |
| `ASc(builder)` | تعريف triggers (`CRg`, `CRf`) |

- 422 فئة تنفّذ `InterfaceC08060Lk` و88 أخرى تنفّذ `C8ZL`. تُوفَّر في مجموعات DI؛ وكل helper يمرّ على مجموعته (`C06980Hc.A03`, `C12650bW.onCreate`, `C44881sN`, `C41891nD`).
- الحذف المتسلسل (cascade) يتم عبر triggers وليس foreign keys: `AbstractC08210Lz.A01` يبني `CREATE TRIGGER <parent>_bd_for_<child>_trigger BEFORE DELETE ON <parent> BEGIN DELETE FROM <child> WHERE ...; END` (found؛ مثال: `message_add_on_reaction` يُحذف عند حذف صفوف `message_add_on`).
- قوائم الأعمدة أدناه مستخرجة من `ASa` بترتيب التعريف. المفكِّك (decompiler) يحذف بعض الأعمدة المبنية بدوال مساعدة (العمود الأول في بعض الجداول، القيم الافتراضية)؛ هذه موسومة بـ "(+ jid)" حيث يثبت استعلام أو trigger وجود العمود. الأنواع مذكورة فقط حيث تنص عليها الشيفرة.
- نسبة فئات msgstore الـ 306 إلى قاعدتها تتم عبر factory الـ DI `C1S0` (306 استدعاء `new`، تشمل `message` و`chat` و`jid`) وعبر triggers الـ FK إلى `chat` / `message` / `jid` (inferred). توجد جداول بنفس الاسم في وحدتين (`status`, `status_attribution`, `mms_thumbnail_metadata`, `quick_promotion_payload`: لكل من msgstore وstatus.db أو wa.db فئة).

### 2.4 الإصدارات والترحيلات

| DB | الاستراتيجية (found) |
|----|------------------|
| `msgstore.db` | `onUpgrade` = `onCreate`؛ `setVersion(1)` دائمًا. الإصدار الحقيقي هو hash مخزَّن في الجدول `props`: `msgtore_db_schema_version` و`msgtore_db_schema_indexes_version` = `Arrays.hashCode` على وسم literal بصيغة `Consumer-<hex>` و`MessageSchemaConfig=1;isGlobalChatDbMigrated=<bool>[;includeNewsletterInteractionTable=true]` (`C06980Hc.A04`). تصريحي (declarative): الجداول والفهارس هي `CREATE ... IF NOT EXISTS` من مجموعة الفئات. مفاتيح `props` الأخرى: `MessagesDBHelper_RestoredIndexesPending`, `MessagesDBHelper_CreateAsyncIndexesV2`, `..FailedAttempts` |
| `wa.db` | `onUpgrade` هو switch على الإصدار القديم من 3 إلى 94 يُسقط في الغالب جداول تُعاد إنشاؤها لاحقًا؛ الإصدار القديم المجهول يذهب إلى `onCreate`؛ الرجوع لإصدار أقدم = `onCreate`. يُكتب `wa_db_schema_version` بوسم `ConsumerBeta-<hex>`. التفضيل `force_wadb_check` (في startup_prefs) يفرض إعادة فحص. wa.db بيانات قابلة لإعادة البناء (جهات اتصال، رموز، caches) |
| `axolotl.db` | بإصدارات (40)؛ صيغ DDL القديمة ظاهرة في `C44861sL` (مثلًا `identities` اكتسب `recipient_type` و`next_kyber_prekey_id` و`account_encryption_attestation_type`؛ و`sessions` اكتسب `recipient_account_id` و`recipient_account_type` و`session_type` و`session_scope`؛ و`sender_keys` اكتسب `bucket_id`) |
| `sync.db` | `ALTER TABLE ... ADD` تدريجي (مثلًا `collection_versions.dirty_version` و`history_sync_companion.inline_payload` و`msg_history_sync.size_limit_bytes`)؛ الرجوع لإصدار أقدم أو إصدار مجهول يستدعي `sync-db-helper/reset` الذي يعيد إنشاء الجداول، فتُعاد مزامنة حالة التطبيق (inferred) |
| `status.db` | v2؛ الصف `schema_version` في `key_value_store` |
| `paa.db` | `runMigrationV1`..`V7` (يضيف أعمدة مثل `age_experience` و`snooze_status` و`common_groups_count`) |
| النسخ الاحتياطية (`BD0`) | بيانات crypt15 الوصفية ما زالت تحمل أعلام "انتهى الترحيل" لكل جدول (`message_main`, `receipt_user`, `jid_store`, ...)، أي تاريخ ترحيلات msgstore القديمة (7.2) |

---

## 3. msgstore.db: الجداول والأعمدة الرئيسية

### 3.1 عائلات الجداول (found، 306 فئة)

| العائلة | الجداول (أمثلة) |
|--------|------------------|
| الهوية | `jid`, `jid_map`, `lid_chat_state`, `lid_display_name`, `jid_user_metadata`, `integrator_display_name` |
| المحادثة | `chat`, `chat_ephemeral`, `chat_encryption_classification`, `community_chat`, `broadcast_chat_details`, `thread_messages`, `thread_id`, `draft_message_reminder` |
| صلب الرسالة | `message`, `message_text`, `message_media`, `message_quoted*` (14)، `message_edit_info`, `message_revoked`, `message_forwarded`, `message_mentions`, `message_link`, `message_future`, `message_orphan`, `message_send_count`, `message_view_once_media`, `message_ephemeral*` |
| رسائل النظام | `message_system` + نحو 35 جدول تفاصيل `message_system_*` (group, number_change, lid_change, username_change, device_change, privacy, ...) |
| الإضافات (Add-ons) | `message_add_on` و`message_add_on_reaction` و`_poll_vote` و`_poll_vote_selected_option` و`_keep_in_chat` و`_pin_in_chat` و`_question_response` و`_event_response` و`_receipt_device` و`_receipt_coex` و`_status_*` |
| الإيصالات | `receipt_user`, `receipt_device`, `receipt_coex`, `receipt_orphaned`, `played_self_receipt`, `optimised_delivery_info` |
| المجموعات | `group_participant_user`, `group_past_participant_user`, `group_participant_device`, `parent_group_participants`, `group_history_*`, `group_root_key_mapping`, `group_notification_version` |
| الأجهزة | `user_device`, `user_device_info`, `primary_device_version`, `agent_devices` |
| الوسائط | `media_hash_thumbnail`, `media_content`, `mms_metadata`, `mms_thumbnail_metadata`, `extended_media_data`, `message_media_map`, `message_streaming_sidecar`, `media_refs`, `message_thumbnail`, `audio_data`, `voice_data` |
| المكالمات | `call_log`, `call_log_participant_v2`, `joinable_call_log`, `missed_call_logs`, `bcall_session`, `call_link`, `scheduled_calls` |
| القنوات الإخبارية | `newsletter`, `newsletter_message`, `newsletter_message_reaction`, `newsletter_admin_profile`, `newsletter_subscribers`, `newsletter_pinned_message`, `newsletter_interaction` |
| الاستطلاعات / الأحداث / التصنيفات | `message_poll`, `message_poll_option`, `poll_vote_*`, `event*`, `labels`, `labeled_jid`, `favorite`, `quick_replies*` |
| المدفوعات / التجارة | `pay_transaction`, `payment_*`, `message_payment*`, `message_order`, `message_product`, `cart_item` |
| النزاهة / الإبلاغ | `integrity_analysis_result`, `integrity_chat_info`, `integrity_input_feature`, `integrity_deleted_chat_*`, `message_quarantine`, `message_structure_analysis_result`, `reporting_info(_content)`, `scam_alert_events` |
| الذكاء الاصطناعي / TEE | `ai_thread_info`, `ai_rich_response_message_*`, `bot_*`, `agent_*`, `auth_agent_chat_metadata`, `tee_chat_request_table`, `tee_message_info_table`, `private_ai_*`, `embeddings_deletion_log` |

### 3.2 الهوية: jid وربط LID

| الجدول | الأعمدة (بترتيب التعريف) | ملاحظات |
|-------|--------------------------|-------|
| `jid` | `_id` (PK AUTOINCREMENT), `user`, `server`, `agent`, `device`, `type`, `raw_string` | فهرس فريد `jid_key_new_index` على (`user`,`server`,`agent`,`device`,`type`)، وفهرس فريد `jid_raw_string_index` على `raw_string`. `JidStore` (`C0W4`) يكتب `jid.getType()` / `getRawString()`. كل جدول آخر يشير إلى JID عبر `*_jid_row_id` = `jid._id` |
| `jid_map` | `lid_row_id`, `jid_row_id`, `sort_id` | من صف LID إلى صف JID لرقم الهاتف (سطح ترحيل LID؛ trigger على `lid_row_id`) |
| `lid_chat_state` | `jid_row_id`, `is_pn_shared`, `pn_requested_ts`, `pnh_duplicate_lid_thread` (+ أعمدة بقيم افتراضية فقط) | حالة مشاركة رقم الهاتف لكل محادثة LID |
| `lid_display_name` | `lid_row_id`, `display_name`, `username` | اسم المستخدم (username) المعروض لجهة اتصال LID، انظر [WA_USERNAME.md](WA_USERNAME.md) |

### 3.3 chat

`chat` (`C0OM`)، 57 عمودًا معرَّفًا. فهرس فريد `chat_account_jid_row_id_unique_index` على `account_jid_row_id`.

| المجموعة | الأعمدة |
|-------|---------|
| المفتاح | `_id`, `jid_row_id`, `account_jid_row_id` (الحساب المالك؛ جديد مع تعدد الحسابات / LID)، `chat_origin` |
| العرض | `subject`, `created_timestamp`, `hidden`, `archived`, `sort_timestamp`, `group_type`, `group_member_count`, `is_contact`, `chat_lock` |
| مؤشرات إلى `message` | `display_message_row_id`, `last_message_row_id`, `last_read_message_row_id`, `last_read_receipt_sent_message_row_id`, `last_important_message_row_id`, `change_number_notified_message_row_id`، إضافة إلى صيغ `*_sort_id` و`last_message_reaction_row_id` و`last_seen_message_reaction_row_id` |
| عدّادات غير المقروء | `unseen_message_count`, `unseen_important_message_count`, `unseen_missed_calls_count`, `unseen_row_count`, `unseen_message_reaction_count`, `unseen_comment_message_count`, `unseen_earliest_message_received_time` |
| المؤقتة (Ephemeral) | `ephemeral_expiration`, `ephemeral_setting_timestamp`, `ephemeral_displayed_exemptions`, `ephemeral_disappearing_messages_initiator`, `ephemeral_after_read_duration` |
| التشفير / السياسة | `plaintext_disabled`, `chat_encryption_state`, `limited_sharing`, `limited_sharing_setting_timestamp`, `growth_lock_level`, `growth_lock_expiration_ts`, `spam_detection`, `business_chat_state`, `participation_status`, `history_sync_progress`, `chat_props` |

### 3.4 message وجداولها التابعة

`message` (`C09540Re`)، 24 عمودًا؛ فهرس فريد `message_key_index` على (`chat_row_id`,`from_me`,`key_id`,`sender_jid_row_id`).

| العمود | الاستخدام |
|--------|-----|
| `_id` | معرّف الصف، يُشار إليه بـ `message_row_id` في كل مكان |
| `chat_row_id`, `sender_jid_row_id` | المحادثة، المرسل (`jid._id`) |
| `from_me`, `key_id` | جزء مفتاح الرسالة (stanza id) |
| `status`, `broadcast`, `recipient_count`, `participant_hash` | حالة التسليم وملخص التوزيع (fan-out) في المجموعات |
| `origination_flags`, `origin`, `view_mode`, `sort_id` | المصدر والترتيب |
| `timestamp`, `received_timestamp`, `receipt_server_timestamp`, `server_sts` | الأوقات |
| `message_type`, `text_data`, `translated_text` | النوع ونص الرسالة العادي (النص موجود في الصف نفسه) |
| `starred`, `view_replies_thread_id` | أعلام |
| `lookup_tables`, `message_add_on_flags` | bitmasks تحدد أي الجداول التابعة تحوي صفوفًا (inferred من الأسماء والاستخدام) |

| الجدول التابع | الأعمدة الرئيسية |
|-----------|-------------|
| `message_text` | `message_row_id`, `description`, `page_title`, `url`, `font_style`, `text_color`, `background_color`, `preview_type`, `invite_link_group_type`, `counter_abuse_token`, `link_end_index` |
| `message_quoted` | `message_row_id`, `chat_row_id`, `parent_message_chat_row_id`, `from_me`, `sender_jid_row_id`, `key_id`, `timestamp`, `message_type`, `text_data`, `quoted_source`, `quoted_type` |
| `message_edit_info` | `message_row_id`, `original_key_id`, `edited_timestamp`, `sender_timestamp` |
| `message_revoked` | `message_row_id`, `revoked_key_id`, `admin_jid_row_id`, `revoke_timestamp` |
| `message_ephemeral` | `message_row_id`, `duration`, `expire_timestamp`, `keep_in_chat`, `ephemeral_trigger`, `ephemeral_initiated_by_me`, `after_read_duration` |
| `message_secret` | `message_row_id` (+ عمود السر، يحذفه المفكِّك): سر لكل رسالة لتشفير الإضافات (inferred) |
| `message_future` | `message_row_id`, `version`, `data`, `future_message_type`, `future_proof_stanza`, `edit_version`, `message_stanza_data` (رسالة غير مدعومة تُحفظ لوقت لاحق) |
| `message_orphan` | `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_*`, `orphan_message_data`, `orphan_message_type`, `orphan_message_reason` (رسالة فرعية وصلت قبل أصلها) |
| `message_quarantine` | `message_row_id`, `chat_row_id`, `timestamp`, `original_protobuf`, `serialized_stanza`, `protobuf_type` |
| `reporting_info` | `message_row_id`, `reporting_tag`, `stanza_id`, `send_timestamp`, `receive_timestamp`, `stanza_id_text`, `receive_flow`, `is_message_add_on` (انظر [WA_REPORTING.md](WA_REPORTING.md)) |
| `message_send_count` | `message_row_id`, `send_count` |

### 3.5 الإيصالات والتفاعلات والإضافات

| الجدول | الأعمدة | ملاحظات |
|-------|---------|-------|
| `receipt_user` | `_id`, `message_row_id`, `receipt_user_jid_row_id`, `receipt_timestamp`, `read_timestamp`, `played_timestamp` | لكل مستلِم (محادثات فردية ومجموعات) |
| `receipt_device` | `_id`, `message_row_id`, `receipt_device_jid_row_id`, `receipt_device_timestamp`, `primary_device_version` | لكل جهاز مستلِم |
| `receipt_orphaned` | `_id`, `chat_row_id`, `from_me`, `key_id`, `receipt_device_jid_row_id`, `receipt_recipient_jid_row_id`, `status`, `timestamp` | إيصال وصل قبل رسالته |
| `message_add_on` | `_id`, `chat_row_id`, `from_me`, `key_id`, `sender_jid_row_id`, `parent_message_row_id`, `timestamp`, `status`, `message_add_on_type`, `received_timestamp`, `expiry_duration_in_secs`, `server_timestamp`, `expiry_timestamp`, `expiry_type` | صف واحد لكل تفاعل / تصويت / تثبيت / إبقاء؛ المفتاح الفريد هو (`chat_row_id`,`key_id`,`from_me`) في استعلام البحث |
| `message_add_on_reaction` | `message_add_on_row_id` (PK), `reaction`, `sender_timestamp` | فهرس جزئي `message_add_on_reaction_empty_reaction_index` على `reaction = ''` (السلسلة الفارغة = تفاعل أُزيل، inferred) |
| `message_poll` | `message_row_id`, `enc_key`, `selectable_options_count`, `invalid_state`, `poll_logging_id`, `poll_type`, `correct_option_id`, `content_type`, `hide_participant_names`, `end_time`, `allow_add_option` | |

`C09010Pb.A00` هو مجموعة أعمدة الإضافات؛ و`AbstractC41651mo.A01` يختار مجموعة الأعمدة حسب معرّف نوع الإضافة: 56 = تفاعل (`C0PV`)، 67 = تصويت استطلاع (`C0PT`)، وأخرى 68 و74 و79 و86 و93 و121 و122 و125 (found: الـ switch؛ لم يُتتبَّع معناها).

### 3.6 المجموعات والمشاركون

| الجدول | الأعمدة |
|-------|---------|
| `group_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `rank`, `pending`, `add_timestamp`, `label`, `join_method`, `group_history_send_state` |
| `group_past_participant_user` | `_id`, `group_jid_row_id`, `user_jid_row_id`, `is_leave`, `timestamp` |
| `group_participant_device` | `_id`, `group_participant_row_id`, `device_jid_row_id`, `sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket` (حالة توزيع sender-key لكل جهاز) |
| `group_root_key_mapping` | `_id`, `group_jid_row_id`, `key_id`, `is_current` |
| `feature_key_store` | `_id`, `key_id`, `key_jid`, `key`, `key_type`, `creation_timestamp`, `expiry_timestamp` |

إعدادات مستوى المجموعة (للمشرفين فقط، الإعلانات، المؤقتة، الموافقة على العضوية، مفاتيح تبديل السجل) موجودة في **wa.db** `wa_group_admin_settings` وليس هنا (4.3). سجل المجموعة: [WA_GROUP_HISTORY.md](WA_GROUP_HISTORY.md).

### 3.7 الأجهزة

| الجدول | الأعمدة |
|-------|---------|
| `user_device` | `_id`, `user_jid_row_id`, `device_jid_row_id`, `key_index` |
| `user_device_info` | `user_jid_row_id`, `raw_id`, `timestamp`, `expected_timestamp`, `expected_ts_last_device_job_ts`, `expected_timestamp_update_ts`, `account_encryption_type` (حالة ADV لكل مستخدم) |

### 3.8 الوسائط والصور المصغرة وsidecar

| الجدول | الأعمدة | ملاحظة |
|-------|---------|------|
| `message_media` | `message_row_id`, `chat_row_id`, `file_path`, `file_size`, `file_length`, `mime_type`, `media_name`, `media_key`, `media_key_timestamp`, `e2ee_media_key`, `file_hash`, `enc_file_hash`, `partial_media_hash`, `partial_media_enc_hash`, `original_file_hash`, `direct_path`, `message_url`, `metadata_url`, `media_duration`, `width`, `height`, `transferred`, `transcoded`, `is_offloaded`, `media_job_uuid`, `media_upload_handle`, `has_streaming_sidecar`, `media_caption`, `media_source_type`, `suspicious_content` | 55 عمودًا معرَّفًا؛ `file_path` يُخزَّن نسبةً إلى جذر الوسائط (`C0KE.A0A` يزيل بادئة الجذر، found). حقول الرفع / التنزيل: [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| `message_thumbnail` | `message_row_id`, `thumbnail` | بايتات الصورة المصغرة داخل DB |
| `message_streaming_sidecar` | `message_row_id`, `sidecar`, `chunk_lengths`, `timestamp` | streaming sidecar (بيانات MAC للأجزاء للتشغيل التدريجي) داخل DB وليس كملف |
| `media_hash_thumbnail` | `media_hash`, `thumbnail` | صورة مصغرة مفهرسة بـ hash المحتوى |
| `media_refs` | `_id`, `path`, `ref_count` | عدّاد المراجع لكل مسار ملف |
| `mms_thumbnail_metadata` | `message_row_id`, `direct_path`, `media_key`, `media_key_timestamp`, `enc_thumb_hash`, `thumb_hash`, `thumb_width`, `thumb_height`, `transferred`, `micro_thumbnail`, `insert_timestamp`, `handle` | |
| `extended_media_data` | `row_id`, `type`, `external_url`, `direct_path`, `preview_path`, `file_path`, `file_hash`, `media_key`, `enc_file_hash`, `mime_type`, `display_type` | |
| `offloaded_media` (offloaded-media.db) | `file_path`, `content_hash`, `file_size`, `media_source`, `media_state`, `is_offloadable`, `latest_reference_timestamp`, `refetch_timestamp`, `file_key` | |

### 3.9 المكالمات

| الجدول | الأعمدة |
|-------|---------|
| `call_log` | `_id`, `jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch` |
| `call_log_participant_v2` | `_id`, `call_log_row_id`, `jid_row_id`, `call_result` |

إشارات المكالمات (signaling): [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md). جداول القنوات الإخبارية (`newsletter` و`newsletter_message`، بـ 45 و17 عمودًا) مذكورة في 3.1 فقط.

### 3.10 العروض (Views) وجداول النزاهة / الذكاء الاصطناعي

العروض المنشأة في `C06980Hc.A0C` (found): `available_message_view`, `deleted_messages_view`, `deleted_messages_ids_view`, `chat_view` (صيغتان، تُختاران حسب `isGlobalChatDbMigrated`).

| الجدول | الأعمدة |
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

## 4. wa.db: جهات الاتصال وقوائم الحظر وبيانات الثقة

### 4.1 العائلات (found، 88 فئة)

| العائلة | الجداول |
|--------|--------|
| جهات الاتصال | `wa_contacts`, `wa_contact_details`, `wa_contacts_created_within_wa`, `wa_contacts_pending_operations`, `wa_contact_refresh_pending`, `wa_contact_refresh_patch_log`, `wa_contact_storage_usage`, `wa_address_book`, `wa_org_contacts`, `wa_orgs`, `system_contacts_version_table` |
| قوائم الحظر / السماح | `wa_block_list`, `wa_block_list_interop`, `wa_last_seen_block_list`, `wa_profile_photo_block_list`, `wa_about_block_list`, `wa_pix_block_list`, `wa_cover_photo_block_list`, `wa_status_view_allow_list`, `wa_status_view_black_list`, `wa_group_add_allow_list`, `wa_group_add_black_list`, `wa_stickers_allow_list`, `wa_profile_links_deny_list` |
| الأعمال | `wa_biz_profiles` + 12 جدول تفاصيل `wa_biz_profiles_*` / `wa_biz_*`، `wa_vnames`, `wa_vnames_localized` |
| المجموعات | `wa_group_admin_settings`, `wa_group_descriptions`, `group_membership_approval_requests`, `non_admin_group_membership_approval_requests`, `group_membership_count`, `group_membership_form_questions`, `group_relationship`, `subgroup_info`, `community_settings`, `member_suggested_groups_v2`, `group_suspension_appeal`, `group_non_wa_invites` |
| الثقة / النزاهة | `wa_trusted_contacts`, `wa_trusted_contacts_send`, `wa_biz_integrity_signals`, `wa_biz_integrity_chat_settings`, `start_chat_trust_signals`, `wa_contact_server_signals` |
| الإعدادات (Config) | `wa_props`, `wa_newsletter_props`, `wa_coex_properties`, `wa_ml_models`, `wa_last_entry_point`, `wa_logging_entry_point` |
| الذكاء الاصطناعي / البوتات | `meta_ai_memory`, `wa_bot_profiles`, `wa_bot_commands`, `wa_subscriptions` |
| أخرى | `status_ranking(_global)`, `wa_chat_ranking_scores`, `wa_storage_monitoring_data/_jobs`, `inbound_/outbound_connection_requests`, `dismissed_*`, `quick_promotion_payload` |

### 4.2 wa_contacts

36 عمودًا (`Nn5`)، المفتاح `jid` (TEXT، سلسلة JID الخام؛ JID هاتف أو JID من نوع `@lid`، وليس معرّف صف `jid`):

`jid`, `is_whatsapp_user`, `status`, `status_timestamp`, `number`, `raw_contact_id`, `display_name`, `phone_type`, `phone_label`, `photo_ts`, `thumb_ts`, `photo_id_timestamp`, `given_name`, `family_name`, `wa_name`, `sort_name`, `nickname`, `company`, `title`, `status_autodownload_disabled`, `keep_timestamp`, `is_spam_reported`, `is_sidelist_synced`, `is_business_synced`, `disappearing_mode_duration`, `disappearing_mode_timestamp`, `disappearing_mode_support_disabled`, `history_sync_initial_phash`, `is_starred`, `is_wa_created_contact`, `sync_policy`, `status_emoji`, `is_contact_synced`, `is_reachable`, `external_user_state`, `fts_dirty_version`.

`wa_name` هو الاسم الظاهر (push name) الذي ضبطه الطرف؛ أما `display_name` / `given_name` فمصدرهما دفتر العناوين. عدة جداول تابعة تستخدم triggers من نوع `BEFORE DELETE ON wa_contacts` (مثلًا `start_chat_trust_signals_contact_delete` و`contact_bd_for_business_integrity_signals`).

### 4.3 جداول wa.db الأخرى

| الجدول | الأعمدة |
|-------|---------|
| `wa_trusted_contacts` | (+ `jid`)، `incoming_tc_token` BLOB، `incoming_tc_token_timestamp` LONG. انظر [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `wa_trusted_contacts_send` | (+ `jid`)، `sent_tc_token_timestamp` LONG، `real_issue_timestamp` LONG |
| `wa_biz_integrity_signals` | 17 عمودًا: `_id`, `jid`, `dhash`, `fb_linked_page_number_of_likes`, `ig_linked_page_number_of_followers`, `is_suspicious`, `join_date_ms`, `is_banned`, `phone_country_code`, `trust_tier`, `is_meta_verified`, `mv_friction_eligibility`, `integrity_tags`, `chat_row_id`, `last_sync_ts`, `hide_safety_tools_for_business`, `fmx_business_holdout_group`. الدلالات الكاملة في تقرير الحظر 5.1 |
| `start_chat_trust_signals` | (+ `jid`)، `is_sender_suspicious`, `is_sender_new_account`, `created_ts` REAL |
| `meta_ai_memory` | `memory_id` TEXT، `memory_content` TEXT، `bot_jid_row_id` INTEGER؛ فهرس `meta_ai_memory_memory_content_index` على `memory_content` |
| `wa_contact_server_signals` | `chat_jid`, `signal_type`, `value`, `update_ts` |
| `wa_group_admin_settings` | `jid`, `restrict_mode`, `announcement_group`, `no_frequently_forwarded`, `ephemeral_duration`, `creator_jid`, `is_suspended`, `group_state`, `require_membership_approval`, `member_add_mode`, `addressing_mode`, `history_enabled`, `group_history_toggle_mode`, `share_group_history_setting_mode`, `earliest_group_history_message_timestamp_ms`, `allow_member_labels`, ... (31 عمودًا) |
| `wa_storage_monitoring_data` | `db_name`, `table_name`, `table_size_bytes`, `index_size_bytes`, `table_unused_bytes`, `index_unused_bytes` (العميل يقيس أحجام جداوله بنفسه؛ انظر 10.3) |

---

## 5. axolotl.db (حالة Signal)

DDL الحالي (أحدث الصيغ في `C44861sL`، والجداول مسجَّلة عبر `AbstractC11250Yd`؛ found). مواد المفاتيح مخزَّنة في أعمدة BLOB باسم `record`؛ لا تُوثَّق هنا أي بايتات مفاتيح.

| الجدول | الأعمدة | الدور |
|-------|---------|------|
| `identities` | `_id`, `recipient_id`, `recipient_type`, `device_id`, `registration_id`, `public_key`, `private_key`, `next_prekey_id`, `next_kyber_prekey_id`, `timestamp`, `account_encryption_attestation_type`, `mark_as_verified`, `mark_as_verified_action_seq`, ... | صف الهوية الخاصة وهويات الأطراف البعيدة (`recipient_type` يفرّق بين حسابات الهاتف وحسابات LID) |
| `sessions` | `_id`, `device_id`, `record`, `timestamp`, `recipient_account_id`, `recipient_account_type`, `session_type`, `session_scope` | جلسات Double Ratchet |
| `prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `key_type` | prekeys للاستخدام مرة واحدة |
| `signed_prekeys` | `_id`, `prekey_id` UNIQUE, `timestamp`, `record`, `key_type` | |
| `kyber_prekeys` | `_id`, `prekey_id` UNIQUE, `sent_to_server`, `record`, `direct_distribution`, `upload_timestamp`, `last_resort_key` | prekeys ما بعد الكم (post-quantum) |
| `prekey_uploads` | `_id`, `upload_timestamp`, `key_type` | |
| `sender_keys` | `_id`, `group_id`, `device_id`, `record`, `timestamp`, `sender_account_id`, `sender_account_type`, `bucket_id` | sender keys للمجموعات |
| `message_base_key` | `_id`, `msg_key_remote_jid`, `msg_key_from_me`, `msg_key_id`, `recipient_id`, `recipient_type`, `device_id`, `last_alice_base_key`, `timestamp` | |
| `chat_stanza_queue`, `e2ee_stanza_queue`, `unordered_stanza_queue`, `preacks`, `stanza_sts` | `stanza_id`, `stanza_key` UNIQUE, `stanza_class`, `chat_jid`, `sender_jid`, `stanza_payload`, ... | حفظ stanza الواردة قبل فك التشفير |

طبقة Java الخاصة بمخزن Signal هي شيفرة بأسلوب `signal_protocol_store` فوق هذه الجداول. تفضيلات التشفير على مستوى الحساب موجودة في `keystore.xml` و`wacrypto.xml` (8.3)، وليس هنا.

---

## 6. sync.db وcompanion_devices.db والقواعد الأصغر

| DB | الجداول والأعمدة الرئيسية |
|----|------------------------|
| `sync.db` | `syncd_mutations` (`mutation_index` UNIQUE, `mutation_value` BLOB, `mutation_version`, `collection_name`, `are_dependencies_missing`, `mutation_mac`, `device_id`, `epoch`, `chat_jid`, `mutation_name`)، `pending_mutations` (نفسها مع `operation` و`is_ready_to_sync`)، `collection_versions` (`collection_name` PK, `version`, `lt_hash` BLOB, `dirty_version`)، `crypto_info` (`device_id`, `epoch`, `key_data`, `timestamp`, `fingerprint`, `stale_timestamp`)، `missing_keys`, `msg_history_sync`, `history_sync_companion`, `peer_messages`, `placeholder_retry_message`, `rmr_response_error`. البروتوكول: [WA_APPSTATE_SYNC.md](WA_APPSTATE_SYNC.md) |
| `companion_devices.db` | `devices`: `device_id`, `device_os`, `platform_type`, `last_active`, `login_time`, `logout_time`, `adv_key_index`, `full_sync_required`, `place_name`, `nickname`, ... البروتوكول: [WA_LINKED_DEVICE_PAIRING.md](WA_LINKED_DEVICE_PAIRING.md) |
| `status.db` | `status`, `status_text`, `status_thumbnail`, `status_info`, `status_interactions`, `status_interactions_totals`, `status_seen_receipt`, `status_receipt_device`, `status_reply`, `status_send_part`, `status_privacy_custom_list`, `status_crossposting_v2/_v3`, ... إضافة إلى `key_value_store` (`row_id`, `key`, `value`) |
| `backup.db` | `backups`, `backup_props` (`prop_name`, `prop_value`؛ الصف `wa_db_schema_version`) |
| `chatsettings.db` | `settings`: `_id`, `jid`, `deleted`, `mute_end`, `muted_notifications`, `use_custom_notifications`, `message_tone`, `call_tone`, `status_muted`, `pinned`, `pinned_time`, `media_visibility`, `mute_reactions`, `wallpaper_*`, `auto_delete_media`, `transcription_locale`, `source_lang`, `target_lang`, `snooze_end_time`, `theme_id` (39 عمودًا) |
| `stickers.db` | `stickers` (`plain_file_hash`, `encrypted_file_hash`, `media_key`, `mime_type`, `sticker_pack_id`, `file_path`, `url`, `direct_path`, `emojis`, `is_lottie`, ...)، `recent_stickers`, `starred_stickers`, `installed_sticker_packs`؛ `payments.db`: `methods` (`credential_id` PK, `country`, `issuer_name`, `type`, `balance_1000`)، `contacts`, `receipts`, `tmp_transactions` |

---

## 7. النسخ الاحتياطية وcrypt15

### 7.1 ملفات النسخ الاحتياطي المحلية

| نمط الاسم (found، `AbstractC26994Bml`, `C29412Cpb`) | المحتوى |
|--------------------------------------------------------|---------|
| `msgstore.db.crypt15`, `msgstore.db.crypt14` | نسخة احتياطية كاملة لقاعدة بيانات المحادثات (regex `msgstore.db.crypt(\d+)`) |
| `msgstore-increment-<N>.db.crypt<V>` | نسخة احتياطية تزايدية |
| `backup_settings.json.crypt<V>`, `status_backup.db.crypt<V>`, `commerce_backup.db.crypt<V>`, `chat_transfer_settings.json.crypt<V>` | الإعدادات، الحالة، التجارة، إعدادات نقل المحادثات |
| `stickers.db.crypt<V>`, `chatsettingsbackup.db`, `wa-backup.db` | نسخ احتياطية للملصقات / إعدادات المحادثات / wa.db (أسماء المكونات أدناه) |

الجذر هو `Backups/` تحت جذر الوسائط الخارجي (`C0KE.A02`؛ والقديم `Databases/`، `C0KE.A03`). يُختار الجذر بالتفضيل `external_storage_type` (القيمة `scoped` تُفحص في `C11160Xu.A07`؛ القيم الأخرى لم تُحصَ)؛ و`EnumC046905z` يمكن أن يحلّ إلى `getExternalMediaDirs()[0]` أو `getExternalStorageDirectory()` أو أدلة خارجية خاصة بالتطبيق أو الأدلة الداخلية. الحسابات الثانوية تستخدم `<root>/accounts/<dirId>` لمسارات `Media/WhatsApp ...` (`C0KE.A00`).

مكوّنات النسخ الاحتياطي (أسماء `A0F` في الفئات الفرعية من `CMN`، found): `stickers`, `stickers-db`, `wallpapers`, `payment-backgrounds-v2`, `chat-transfer`, `wa-db`, `commerce-db`, `status_db`, `offloaded-media.db`, `chatlock_backup`, `chat-settings`, `backup-settings`. التفضيل `backup_prefs` يحتفظ بـ `<component>_backup_size` / `_backup_status` لكل مكوّن (8.3).

فئات الوسائط في واجهة النسخ الاحتياطي (`EnumC26330BbW`، 17 قيمة): `CHAT_DB`, `SETTINGS`, `STATUS_DB`, `COMMERCE_DB`, `OTHER_DB`, `IMAGES`, `VIDEOS`, `AUDIO`, `VOICE_NOTES`, `VIDEO_NOTES`, `GIFS`, `DOCUMENTS`, `STICKERS`, `STICKER_PACKS`, `PROFILE_PHOTOS`, `EXCLUDED_STICKERS`, `OTHER`.

### 7.2 بادئة ملف crypt15 (found)

`EnumC26325BbR`: `UNENCRYPTED` 0، `CRYPT14` 14، `CRYPT15` 15 (اللاحقة `.crypt` بلا رقم هي الصيغة القديمة؛ و`CKv` يطابق `.crypt`). قارئ crypt15 (`BN4.A09`) يحلّل protobuf محدَّدًا (delimited) باسم `BackupPrefix` (`BCE`) قبل النص المشفَّر:

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `key_type_deprecated` | **1** | enum | نوع المفتاح القديم |
| `wa_provided_key_data` | **2** | bytes | بيانات المفتاح للمفاتيح المقدَّمة من الخادم |
| `e2ee_key_data` | **3** | message | بيانات المفتاح للنسخ الاحتياطي المشفَّر من طرف إلى طرف |
| `backup_metadata` | **4** | `BD0` | انظر أدناه |
| `passkey_encryption_metadata` | **5** | message | مسار passkey (`parsePasskeyEncryptionMetadata`) |
| `key_type_new` | **6** | enum | نوع المفتاح الحالي |

أنواع المفاتيح (`BdX`): `WA_PROVIDED` 0، `E2EE_DEPRECATED` 1، `E2EE_PASSWORD` 2، `E2EE_ENCRYPTION_KEY` 3، `E2EE_PASSKEY` 4.

حقول `BackupMetadata` (`BD0`) (مختارة): `app_version` **1**، `device_model` **2**، `jid_suffix` **3**، `backup_version` **4**، `backup_export_file_size` **38**، `cleaned_db` **39**، `backup_encrypted_hash_salt` **40**، `backup_encrypted_hash` **41**، `identifier_type` **42**، `lid_suffix` **43**، `display_suffix` **44**، إضافة إلى نحو 30 قيمة منطقية `*_migration_finished` (الأرقام من 5 إلى 35). عند الاستعادة يقارن `EncBackupUtils` قيمة `jid_suffix` بالمستخدم المسجَّل (`has-jid-user-mismatch`): النسخة الاحتياطية مرتبطة بالحساب الذي أنشأها.

بنية الشيفرة (cipher) والـ KDF والـ MAC للنص المشفَّر لم تُقرأ هنا (unknown).

### 7.3 مواد مفاتيح النسخ الاحتياطي

| الملف (في `files/`) | المحتوى | الدليل |
|--------------------|---------|----------|
| `encrypted_backup.key` | المفتاح الجذر بطول 32 بايت للنسخ الاحتياطي المشفَّر من طرف إلى طرف (`C29861Ep.A09`، يُفحص الطول == 32)؛ يُكتب بـ `A04(...)`، وربما يُغلَّف بمفتاح تغليف من KeyStore (`failed to load or create KeyStore encapsulation key`) | found |
| `encrypted_backup.key_id` | معرّف المفتاح | found |
| `password_data.key`, `passkey_data.key` | حالة صيغتَي كلمة المرور وpasskey (بيانات passkey بصيغة JSON) | found |
| `vault_backup.key` | مفتاح vault بطول 32 بايت، يُولَّد بـ `C00L.A0H(32)` ويرفض الكتابة فوق ملف غير مقروء (`vault backup key present but could not be read`) | found |
| `prf_derived_root_key.key`, `secret_code.key` | المفتاح الجذر المشتق من PRF الخاص بـ passkey، ومفتاح الرمز السري | الاسم found، المحتوى unknown |
| `backup_token`, `foa_backup_token` | ملف الرمز (`CMc`، والصيغة `foa_` لحساب مركز الحسابات) | found |

`AbstractC29801Ej` يحذف `encrypted_backup.key(_id)` و`password_data.key` و`passkey_data.key` و`vault_backup.key` معًا (إعادة ضبط المفاتيح).

### 7.4 النسخ الاحتياطي التلقائي في Android وموفّر الترحيل (found)

| البند | القيمة |
|------|-------|
| `android:allowBackup` | `true`، `fullBackupOnly=true`، وكيل النسخ الاحتياطي `SystemBackupAgent` |
| `fullBackupContent` (`xml0003`) و`dataExtractionRules` (`xml0006`: النسخ الاحتياطي السحابي ونقل الجهاز) | يستثنيان **كل** نطاق (`root`, `file`, `database`, `sharedpref`, `external`, `device_*`). لا شيء تنقله المنصة |
| `cross-platform-transfer platform="ios"` | معلَن مع معرّف حزمة iOS؛ النقل يمر عبر `OsMigrationAppDataService` (الإذن `android.permission.BACKUP`) |
| `MigrationContentProvider` | مُصدَّر (exported)، `readPermission com.whatsapp.permission.MIGRATION_CONTENT_PROVIDER` (protectionLevel `signature`)، `grantUriPermissions=false`. الـ URIs: `msg_store`, `unencrypted_msg_store`, `wa_db`, `chat_setting_store`, `sticker_store`, `wallpaper`, `share_preferences`, `media`, `chat_lock_passcode`. `DirectMigrationContentProvider` يستخدم الإذن نفسه. الغرض (التسليم إلى التطبيق الشقيق الموقَّع بالتوقيع نفسه) inferred |

---

## 8. SharedPreferences

### 8.1 المصنع (Factory)

`C00S` (SharedPreferencesFactory، `A04(C00G, name)`): يُرجع تنفيذًا مخصصًا فوق `<dataDir>/shared_prefs/<name>.xml` (غلاف الملف `C052308r`؛ الفئات `C052408s` / `RRP`)، ويرجع إلى `getSharedPreferences(name, 0)` الخاص بالنظام إذا تعذّر إنشاء الدليل. لم يُتحقَّق في الشيفرة من كون البايتات على القرص XML قياسيًا في Android (اللاحقة فقط).

| الحقيقة | الدليل |
|------|----------|
| مجموعات أسماء ذات معالجة خاصة في `AbstractC051008e` (`A02`, `A03`: أعلام ميزات للتنفيذ؛ `A00`, `A01`, `A04`: مجموعات ذات نطاق) | found؛ دلالات أعلام `C00G(boolean,boolean,boolean)` unknown |
| المجموعة `A05` (`multi_account_metadata`, `group_history_usage`, `hatch_group_agent`, `hatch_group_agent_debug`, `smb_token_lockout_cooldown`) يجب ألا ينشئها هذا المصنع: الرسالة `Pref not allowed to instantiate using SharedPreferencesFactory, use MultiAccountSharedPreferencesFactory` | found |
| أسماء الملفات الرئيسية مشتقة من `AbstractC051108f`: `com.whatsapp_preferences` و`com.whatsapp_preferences_light` | found |
| `SharedPreferencesUsageRepository` (`C052508t`) يسجّل أزمنة التحميل لكل ملف prefs (`load`, `load2`)، ويتخطى `ab-props` و`ab-props-back-up` و`ab-prechatd-props` و`ab-props-backup` و`dropped_wam_events` و`keystore` | found: قياس عن بُعد حول الـ prefs نفسها |
| `C09E` (فئة "Me" والـ prefs المهملة الضخمة god-class) يغلّف `com.whatsapp_preferences_light` (الحالة 23 في `C1WL`)؛ وكثير من الأغلفة الصغيرة (`C1DH`, `C56902Wq`, `C0G1`) هي عروض لذلك الملف الواحد | found |
| الملف الافتراضي `com.whatsapp_preferences` هو ملف Android العادي؛ و`chatCounts` ملف منفصل (`RP5`) | found |

### 8.2 الملفات حسب المجال (الأسماء found في الشيفرة)

| المجال | الملفات |
|------|-------|
| الأساس | `com.whatsapp_preferences`, `com.whatsapp_preferences_light`, `startup_prefs`, `reg_prefs`, `register_phone_prefs`, `registration.verifyphone.VerifyPhoneNumber`, `registration.app.phonenumberentry.RegisterPhone`, `registration.app.verifyphone.VerifyPhoneNumber`, `multi_account_metadata`, `account_linking_prefs`, `fb_credentials_prefs`, `fb_linked_account`, `accounts_center_registration_prefs` |
| الأعلام (Flags) | `ab-props`, `ab-props-backup`, `ab-props-back-up`, `ab-prechatd-props`, `groupAbProps`, `network_resources_pref` |
| التشفير | `keystore`, `wacrypto`, `security_prefs`, `nc_prefs`, `chat_lock`, `migration_export`, `AccountDefenceLocalDataRepository_prefs` |
| النسخ الاحتياطي / المزامنة | `backup_prefs`, `chat_transfer_prefs`, `syncd_prefs`, `contact_sync_prefs`, `device_capabilities`, `companion_mode_prefs` |
| الميزات | `username_prefs`, `meta_ai_prefs`, `bonsai_prefs`, `paa_prefs`, `status_prefs`, `newsletter_prefs`, `voip_prefs`, `route_selector_prefs`, `interop_ui`, `interop_badge_prefs`, `avatar_prefs`, `bloks`, `privacy_disclosure_store`, `user_notice_prefs`, `tos_gating_prefs` |
| القياس عن بُعد | `critical_event_client_prefs`, `anr_shared_prefs`, `time_spent_prefs`, `dropped_wam_events`, `wam_prefs`, `chatCounts` |
| حزم SDK من أطراف ثالثة | `com.google.android.gms.appid`, `com.google.firebase.messaging`, `WebViewChromiumPrefs` (النظام) |

### 8.3 المفاتيح المهمة (كل أسماء المفاتيح found في 2.26.41.6؛ القيم غير مُعادة)

| الملف | المفتاح | النوع / الاستخدام |
|------|-----|-----------|
| `startup_prefs` | `registration_state` | int؛ محمولات `C06810Gk`: 0/1 ابتدائي، 3، 4، 5، 8 (flash verify)، 12، 15، 17 (email OTP)، 20، 23 |
| | `startup_migrated_version` | int؛ الهدف **20**، و`WaStartupSharedPreferences` يشغّل الترحيلات الأدنى منه |
| | `push_name` | اسم العرض الخاص بالمستخدم |
| | `force_db_check`, `force_wadb_check` | يفرضان فحص سلامة msgstore / wa.db (يُمسحان بـ `C0HS.BoJ`, `C12650bW.onCreate`) |
| | `pending_repair_db_name`, `pending_repair_db_file_id`, `pending_repair_corruption_type`, `pending_repair_attempt_count`, `pending_repair_request_id`, `pending_repair_timestamp`, `pending_repair_gate_suppressed` | طابور إصلاح قواعد البيانات |
| | `privacy_fingerprint_enabled`, `night_mode`, `client_server_time_diff` (يقرؤه `C050708b`) | |
| `com.whatsapp_preferences_light` | `registration_jid`, `registration_lid`, `cc`, `ph`, `self_lid`, `registration_initialized_time`, `registration_success_time_ms`, `registration_wipe_info_timestamp`, `reg_attempts_verify_code` | هوية هذا التثبيت (يُمسح بـ `RegistrationManager.A0I`) |
| | `adv_raw_id`, `adv_current_key_index`, `adv_timestamp_sec`, `phoneid_id`, `phoneid_timestamp` | حالة ADV / phone id |
| | `privacy_last_seen`, `privacy_profile_photo`, `privacy_status`, `privacy_online`, `read_receipts_enabled`, `privacy_token_batch_offset_sec` | إعدادات الخصوصية (`C18260lS`, `C09E.A0S()`) |
| | `md_messaging_enabled`, `last_login_time`, `last_daily_cron`, `next_randomized_daily_cron`, `nct_salt` | علم تعدد الأجهزة، محاسبة cron، salt الخاص بـ tctoken ([WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md)) |
| `backup_prefs` | `gdrive_state`, `backup_provider`, `backup_encryption_method`, `encrypted_backup_fleet_migration_state`, `encrypted_backup_num_attempts_remaining`, `google_restore_result`, `msg_restore_timestamp`, `last_seen_app_version`, `device_backup_integration_enabled`, `blocking_restore_in_progress`, `cloud_api_type`, `restore_second_verification_needed` | حالة النسخ الاحتياطي والاستعادة (`C22090sX`) |
| `keystore` | `server_static_public`, `server_static_pq_public`, `client_static_keypair_pwd_enc`, `client_static_keypair_enc_success`, `can_user_android_key_store`, `remaining_auth_key_rotation_attempts` | مفاتيح Noise الثابتة ([WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)، [WA_ACCOUNT_SECURITY.md](WA_ACCOUNT_SECURITY.md)) |
| `wacrypto` | `signed_prekey_id_seed_migration_completed` | ترحيل seed معرّف prekey الخاص بـ Signal |
| `ohai_key_config` (اسم pref في `C53596Nzj`) | `public_key` وحقول إعداد المفتاح | مفتاح بوابة OHAI |
| `syncd_prefs` | `syncd_dirty`, `syncd_bootstrap_state`, `syncd_bootstrapped_mutations` (set)، `mutation_counter` | تهيئة (bootstrap) مزامنة حالة التطبيق |
| `companion_mode_prefs` | `previously_logged_out_from_primary` | حالة الجهاز المرافق (companion) |
| `username_prefs` | `username_reservation_state`, `username_pin` | انظر [WA_USERNAME.md](WA_USERNAME.md) |
| `route_selector_prefs` | `media_conn` | مسار وسائط مخزَّن مؤقتًا (قائمة المضيفين وبيانات المصادقة؛ [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md)) |
| `ab-props` | مفاتيح نصية رقمية (رموز الإعداد)، `ab_props:sys:last_refresh_time`, `ab_props:sys:config_hash`, `ab_props:sys:last_version`؛ و`com.whatsapp_preferences` يحوي `ab_props:hash_v2` | ذاكرة AB props المؤقتة؛ `ab-props-backup` هو النسخة السابقة |
| `chatCounts` | عدّادات لكل محادثة، `thread_user_secret` (32 بايتًا عشوائيًا، base64) | `WamThreadIdManager` يطبّق HMAC على معرّفات thread به؛ و`RP5.A0w` يحتفظ به عبر إعادة الضبط |

---

## 9. الملفات والذاكرة المؤقتة وبنية الوسائط

### 9.1 `files/` الداخلي (found ما لم يُوسَم خلاف ذلك)

| المسار | المحتوى |
|------|---------|
| `me` | سجل `Me` مُسلسَل بـ Java (`C9V.A01`، الحقول تشمل `cc` و`number`)؛ `me.jpg` / `me_old.jpg` صورة الملف الشخصي |
| `rc2` | قيمة عشوائية بطول 160 بت مشفَّرة بـ AES/OFB تُولَّد عند أول استخدام من مدخلَي سلسلة (`K49.A0v`, `C00L.A0G`؛ inferred: رمز الدولة والرقم)؛ الغرض inferred (سر تسجيل). يحذفها runnables المسح `RunnableC29329CoG`, `RunnableC46625KYz` |
| `backup_token`, `foa_backup_token`, `encrypted_backup.key*`, `vault_backup.key` | القسم 7.3 |
| `invalid_numbers`, `login_failed`, `customTSValues`, `emoji` | ملفات حالة صغيرة (`IJU`, `C06850Go`) |
| `statistics.json`, `network_statistics.json` | عدّادات rx / tx (`C17B`, `C17J`؛ المفاتيح `statistics`, `bytes`, `timestamp`, `rx_data`, `tx_data`) |
| `Logs/` | ملفات السجل (10.1) |
| `decompressed/libs.spo/` (+ `.superpack_version`) | مكتبات تُفكّ أثناء التشغيل بواسطة `C0EE`؛ **مستثناة من كل عمليات المسح** |
| `mobileconfig/` | `mc_overrides.json`, `id_name_mapping.json` (`C053409d`) ومخزن الإعدادات |
| `falco/`, `wam/` | محركات القياس عن بُعد (10) |
| `Stickers/`, `Drafts/`, `GroupHistory/`, `Payment Backgrounds/`, `Wallpapers/`, `.trash/`, `biz_directory/`, `privacy_disclosure/<version>/`, `downloadable/`, `NetworkResource/`, `MNSResolverCache/`, `app_state/` | ذاكرات مؤقتة للميزات (`C0I1`, `C58398QKk`, `C27574Bxe`, `MNSStreamRuntime`, `C06110Cn`) |

أدلة خاصة أخرى مسمّاة في switch إعداد التخزين (`AbstractC13030c9`): `lib-compressed`, `app_secure_shared`, `app_sigquit`, `modules`, `app_optsvc_analytics`, `app_overtheair`, `app_qpl`, `app_light_prefs`, `cache/secure_shared`, `files/secure_shared`, `app_minidumps`, `app_fb-forker-tmp`.

### 9.2 `cache/` (found)

| الدليل | ملاحظة |
|-----|------|
| `thumb_decoded_cache` | LRU على القرص، **52428800 بايت (50 MiB)** (`C33000EZy`) |
| `webp_static_cache`, `stickers_cache`, `avatar-temporary`, `interop_image_cache`, `tigon_http_client`, `ML_MODEL`, `hatch_space_images`, `meta_ai_thread_photo_uploads` | ذاكرات مؤقتة للصور / الشبكة / النماذج |
| `Profile Pictures/` | بنطاق الحساب (`C28025CFb.A01` يُرجع دليل cache؛ و`QLH` يبني `Profile Pictures`) |

### 9.3 الحسابات الثانوية (found)

`getDir("account_switching")` (= `app_account_switching/`) يحوي `active_account` (معرّف الدليل النشط، `C00W`) وقائمة الحسابات (`C25160AsA`). بيانات الحساب الثانوي موجودة في `<dataDir>/accounts/<dirId>/{databases,files,cache}` (`C28025CFb`) ووسائطه تحت `<root>/accounts/<dirId>`؛ أما الحساب الافتراضي فيستخدم الأدلة العادية. `account_switcher.db` وprefs تعدد الحسابات مشتركة.

### 9.4 جذر الوسائط الخارجي (found)

`<root>/Media/WhatsApp <Category>/` مع الفئات `Images`, `Video`, `Audio`, `Documents`, `Voice Notes`, `Video Notes`, `Animated Gifs`, `Stickers`, `Sticker Packs`, `Profile Photos`, `Backup Excluded Stickers` (`AbstractC26994Bml`)، والمجلدات الفرعية `Sent`, `Private`, `.Thumbs` (`*.prog.thumb.jpg`، `C0I1.A08`)، `.Shared`، وعلامات `.nomedia`. العمود `message_media.file_path` يخزّن الجزء الذي يلي الجذر.

---

## 10. السجلات والقياس عن بُعد المحفوظة على الجهاز

### 10.1 السجلات (found)

| الملف | التفاصيل |
|------|--------|
| `files/Logs/whatsapp.log`, `whatsapp.tmp` | سجل نصي، الترويسة `==== logfile version=2.26.41.6 level=4 ====`؛ التدوير يضغط إلى `.gz` مع تاريخ (`Log.rotate`, `AbstractC28128CKx.A00`). `C24971Ap6` يجمع `Logs` مع دليل DB لتصدير الدعم / تقرير الأخطاء |
| `app_minidumps/`, `<dir>/minidumps`, `crash_upload/` | تفريغات الانهيار الأصلية (native crash dumps) ومنطقة التجهيز للرفع (`C0FQ`, `JJ1`, `CKN`, `ExceptionsUploadService`) |
| `anr_report_<n>.dmp`, `anr_shared_prefs` | تقارير ANR (`C45432Jrw`) |
| `cache/qpl`, `app_qpl` | آثار QuickPerformanceLogger |

### 10.2 محركات القياس عن بُعد

| المسار | المحرك | الدليل |
|------|--------|----------|
| `files/wam/` | دليل تشغيل WAM الممرَّر إلى `WAJContextInitWAMRuntime` (JNI) | `RunnableC29323CoA`؛ تفضيلا `dropped_wam_events` و`wam_prefs` |
| `files/falco/` | مسجِّل أحداث في `libffsingletonmerged.so` | السلاسل الأصلية أدناه |
| `files/mobileconfig/` | مخزن Mobile Config | `C053409d` |

ملف Falco بصيغة SQLite هو `FFLogger.sql` (الموقع inferred: Java تنشئ `files/falco/`، واسم الملف سلسلة داخل المكتبة الأصلية): الجداول الموجودة في سلاسل المخطط الأصلي (found): `event`, `buffer_event`, `upload` (`request_data`, `num_events`, `is_compressed`, `compression_method`)، `claim` (`principal_subject_hash`, `claim`, `expires_at`)، `collection_constraint`, `event_config` (`event_config_hash` UNIQUE, `event_name`, `sampling_rate`, `collection_constraint_ref`, `is_deidentified`)، `checksum`, `amendment_outbox`، الفهرس `event_0` على `event(requested_latency)`؛ و`batch` يرتبط عبر `identities_hash`. الملف `fflogger_health_counters.bin` يحوي عدّادات القياس الذاتي (`mobile_health_counters`). جانب Java ينشئ الدليل فقط.

### 10.3 القياس الذاتي

الجدولان `wa_storage_monitoring_data` / `_jobs` في wa.db (أحجام لكل جدول وبايتات غير مستخدمة حسب `db_name`) وإحصاءات تحميل الـ prefs (8.1) هي قياس عن بُعد يحتفظ به العميل عن تخزينه الخاص. مسار أحداث WAM نفسه خارج نطاق هذا التقرير.

---

## 11. ما الذي يُمسح ومتى

### 11.1 العمليات

| العملية | نقطة الدخول (2.26.41.6) | الأثر |
|-----------|-------------------|--------|
| حذف الحساب / إعادة ضبط البيانات المحلية | `C25007Aph.A0L` ثم `A02` (`removeDatabasesAndResetState`) | مسح محلي كامل، 11.2 |
| إزالة الجهاز المرافق (companion) | `C25007Aph.A0M` (`deleteCompanionCleanup`) | `ActivityManager.clearApplicationUserData()` (بديل `pm clear <package>`، وبديله `A02`) |
| إعادة التسجيل | `RegistrationManager.A06` (`reregister reason=`) | يمسح prefs التسجيل و`me`، 11.3 |
| إلغاء التسجيل من الجهاز | `RegistrationManager.A0F` | يوقف الاتصال مع `should_unregister=true`، ويحذف `me`، ويمسح الحالة |
| تسجيل الخروج (الرئيسي، مع تعدد الحسابات) | `LogoutManager` (`AccountLogoutMutation`, w:mex) | تسجيل خروج على الخادم، يُوسَم الحساب كمسجَّل الخروج؛ تبقى البيانات حتى يزيل المستخدم الحساب المسجَّل خروجه (11.4). لم يُتتبَّع ما إذا كانت الخطوة الأولى تحذف شيئًا محليًا (unknown) |
| إزالة حساب مسجَّل الخروج | `LogoutManager.removeLoggedOutAccountWithCleanup` | يزيل مدخل الحساب، ثم `deleteDefaultAccountDirectories` أو `deleteSecondaryAccountDirectories`، ثم حالة النسخ الاحتياطي في GMS |

### 11.2 حذف الحساب (`C25007Aph.A02`، found)

| الهدف | الإجراء |
|--------|--------|
| المخازن في الذاكرة، مديرو الميزات | تُمسح؛ `last_contact_full_sync` = -1 |
| قواعد البيانات | حذف كل helper (`A0D`, `A0N`): msgstore عبر `C0HC` (`msgstore-manager/deletedb/result`)، وwa.db (`deleteaccountconfirm/wa-db-delete-incomplete` خطأ إذا بقيت ملفات)، وcommerce، و`emojidictionary`، ومخزن حزم اللغات، و`MediaJobDataStore`، ومخازن مزامنة السجل، ودليل الأعمال (`files/biz_directory`) |
| `files/` | كل المدخلات عدا `decompressed`؛ و`Logs` تبقى عند ضبط العلم `z` (مسار companion) |
| الجذر الخارجي | يُزال `Backups/` ويُعاد إنشاؤه فارغًا، وتُزال ملفات `Databases/` (`AbstractC28132CLd.A04`)، فقط إذا كانت حالة التخزين الخارجي قابلة للاستخدام |
| `com.whatsapp_preferences` | `clear()` ثم يُعاد كتابة `version` بالقيمة `2.26.41.6` |
| `backup_prefs` | `clear()` لكن تُستعاد `last_seen_app_version` و`device_backup_integration_enabled` |
| `chatCounts` | تُزال كل المفاتيح عدا `thread_user_secret` (`RP5.A0A`) |
| prefs أخرى | `avatar_prefs`، وملفات التسجيل وVerifyPhone، وتسجيل companion (`registration_device_id`, `companion_registration_state` = 0)، وبعض prefs الميزات |
| WebView | تُحذف ملفات تعريف الارتباط (cookies) وتخزين الويب، وكذلك للملفات الشخصية المسمّاة عند توفر تعدد الملفات الشخصية |

### 11.3 إعادة التسجيل / إلغاء التسجيل (found)

`RegistrationManager.A0I` يزيل `registration_jid` و`registration_lid` و`cc` و`ph` و`registration_wipe_info_timestamp`؛ و`A0A` يمسح prefs شاشتَي التسجيل؛ ويُزال ملف `me` (`rm-me`).

### 11.4 حوار المحادثات المسجَّل خروجها (`FilesDeletionUtility`)

يحذف الجذر الخارجي للمستخدم المسجَّل خروجه، و`cacheDir`، وكل مدخل في `filesDir` عدا `decompressed`، ودليل ملفات الحساب الثانوي، ثم يستدعي دوال الحذف في DB helpers؛ وفشل حذف wa.db يرمي استثناءً ويبلّغ الحوار عن خطأ (`FilesDeletionUtility/deleteInternalFiles/wa-db-delete-incomplete`).

### 11.5 حذف ملفات تعدد الحسابات (`AccountSwitchingFileManager.deleteDefaultAccountDirectories`)

للحساب الافتراضي: يُحذف `shared_prefs` عدا قائمة سماح؛ ويُحذف `databases` عدا `account_switcher.db` (وصيغ لاحقاته)؛ وتُزال الأدلة الأخرى بالكامل.

---

## 12. ملاحظات Baileys (ربط inferred)

يحتفظ Baileys ببيانات الاعتماد وبمخزن بمفاتيح (`creds`, pre-key, session, sender-key, app-state-sync-key / -version, lid-mapping, device-list, tctoken). النظائر المفاهيمية على Android (inferred؛ لا شيفرة تربطها):

| حالة Baileys | التخزين على Android |
|---------------|-----------------|
| `session`, `pre-key`, signed pre-key | `axolotl.db` `sessions`, `prekeys`, `signed_prekeys` (+ `kyber_prekeys` على Android) |
| `sender-key`, `sender-key-memory` | `axolotl.db` `sender_keys`؛ والتوزيع لكل جهاز في msgstore `group_participant_device` |
| app-state sync key / version | `sync.db` `crypto_info` (`key_data`, `epoch`)، `collection_versions` (`lt_hash`) |
| lid mapping | msgstore `jid_map` (+ `lid_display_name`) |
| device list | msgstore `user_device`, `user_device_info` |
| `tctoken` | wa.db `wa_trusted_contacts(_send)` |
| `creds.me`, registration id, ADV | `files/me`، prefs `adv_*`، صف `identities` |

جلسة Baileys لا تملك مقابلًا لجدول `message`؛ وحذف حالة المصادقة فيها هو نظير المسح في 11 ويتطلب ربطًا جديدًا.

---

## 13. حالات الخطأ والمزالق

| العَرَض | السبب | الإصلاح / ملاحظة |
|---------|-------|-----------|
| الرسالة `msgstore/upgrade version 1 to N` لا تظهر أبدًا | `user_version` في msgstore دائمًا 1 | اقرأ `props.msgtore_db_schema_version` لمعرفة حالة المخطط الحقيقية |
| msgstore "restored-db-not-indexed" / `RestoredIndexesPending` | DB استُعيدت من نسخة احتياطية؛ الفهارس تُنشأ بكسل (lazily) | مفاتيح `props` `MessagesDBHelper_*`؛ يكتمل التشغيل بشكل غير متزامن |
| `still-corrupt-after-repair`, `delete-superseded-by-new-repair` | فشل فحص السلامة (`C0HC.checkhealth`) | الطابور في `startup_prefs` `pending_repair_*`؛ `force_db_check` |
| wa.db فارغة فجأة بعد التحديث | switch الترقية أسقط جداول (الإصدارات 3 إلى 94) أو تغيّر hash المخطط | wa.db قابلة لإعادة البناء من الخادم ودفتر العناوين |
| `deleteaccountconfirm/completion-blocked/wa-db-files-remain` | تعذّر حذف ملفات wa.db | أعد المحاولة؛ يُجهَض المسح بـ `Be5` |
| الاستعادة ترفض نسخة احتياطية (`has-jid-user-mismatch`) | `BackupMetadata.jid_suffix` يختلف عن الحساب | استعد بالرقم نفسه |
| `backup-file-crypt15/prefix null` | الملف فارغ أو ليس crypt15 | افحص البادئة المحدَّدة (7.2) |
| `vault backup key present but could not be read` | `vault_backup.key` غير مقروء | الشيفرة ترفض توليد بديل لتفادي الكتابة فوق ملف قابل للاسترداد |
| `Pref not allowed to instantiate using SharedPreferencesFactory` | pref خاصة بتعدد الحسابات أُنشئت بالمصنع الخاطئ | استخدم `MultiAccountSharedPreferencesFactory` |
| بيانات حساب مسجَّل خروجه ما زالت موجودة | تسجيل الخروج لا يحذف بيانات الحساب (11.1) | أزل الحساب صراحةً |

---

## 14. فروق جوهرية

| لا تخلط بين | الفرق |
|----------------|-----------|
| `msgstore.db` مقابل `wa.db` | الرسائل والمحادثات وصفوف `jid` مقابل جهات الاتصال وقوائم الحظر ورموز جهات الاتصال الموثوقة وذاكرات الأعمال والنزاهة المؤقتة؛ معرّفات صفوف JID موجودة في msgstore فقط، ومفاتيح wa.db هي سلاسل JID خام |
| `jid._id` مقابل JID الخام | أعمدة `*_jid_row_id` هي معرّفات صفوف msgstore؛ وجداول `wa_*` تستخدم `jid` من نوع TEXT |
| `user_version` في SQLite مقابل إصدار المخطط | msgstore دائمًا 1؛ وwa.db 95؛ والمخطط hash في `props` (msgstore) أو وسم (wa.db) |
| النسخ الاحتياطي التلقائي في Android مقابل نسخ المحادثات الاحتياطي | النسخ التلقائي يستثني كل شيء؛ ونسخ المحادثات هو ملف `crypt15` الخاص بالتطبيق في الجذر الخارجي |
| ملف crypt15 مقابل ملفات المفاتيح | النص المشفَّر في `Backups/`؛ والمفاتيح في `files/*.key` (لا تكون أبدًا في المجلد نفسه) |
| `com.whatsapp_preferences` مقابل `_light` | prefs Android العادية (تُمسح إلى مفتاح إصدار) مقابل ملف التنفيذ المخصص الذي يستخدمه `C09E` (الهوية، الخصوصية، الأعلام) |
| `ab-props` مقابل `wa_props` | رموز تجارب AB (prefs) مقابل خصائص الحساب من الخادم (جدول في wa.db) |
| تسجيل الخروج مقابل حذف الحساب | تسجيل الخروج يوسم الحساب؛ والحذف يمسح DBs والملفات وBackups وprefs (11) |
| Falco مقابل WAM | Falco هو مسجِّل أحداث SQLite داخل مكتبة أصلية؛ و`wam/` هو دليل تشغيل WAM؛ كلاهما قياس عن بُعد |
| ملفات من تعديلات (mods) أطراف ثالثة | قواعد بيانات إضافية أو سجلات stanza أو تشخيصات hook لا ينشئها التطبيق الأصلي وغير مشمولة |
---

## 15. البنية ودورة الحياة

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

## 16. غير مغطّى وغير معروف

| الموضوع | الحالة |
|-------|--------|
| نسبة كل جدول إلى قاعدته لفئات الجداول الـ 306 + 422 عدا التي فُحصت | أحجام المجموعات found؛ ربط كل فئة بقاعدتها عبر graph الـ DI لم يُتتبَّع (inferred عبر FKs والأسماء) |
| أنواع الأعمدة والقيم الافتراضية وNOT NULL للجداول المبنية بدوال مساعدة | المفكِّك يحذف بعضها؛ تُدرج الأسماء فقط |
| نحو 250 جدولًا متبقيًا في msgstore، وجداول wa.db وstatus.db المتبقية | الأسماء مدرجة ضمن العائلات؛ لم تُستخرج الأعمدة |
| صيغة النص المشفَّر في crypt15 وKDF وMAC؛ ومحتويات الرسائل الفرعية في `BackupPrefix` | unknown |
| صيغة XML القياسية على القرص لتنفيذ prefs المخصص | لم يُتحقَّق |
| القائمة الكاملة لمفاتيح كل ملف prefs (مئات المفاتيح) | فقط الملفات والمفاتيح المذكورة في 8.3 |
| معنى أعلام `C00G` ومعرّفات أنواع الإضافات وقيم `registration_state` | مسمّاة جزئيًا |
| إصدارات `sync.db` و`chatsettings.db` و`stickers.db` و`commerce.db` و`daily_metrics.db` و`location.db` | غير محسومة |
| غرض `files/rc2` و`files/key` | `rc2` inferred؛ `key` غير محسوم |
| هل تسجيل الخروج الرئيسي وحده يحذف البيانات المحلية | لم يُتتبَّع |
| سلوك وقت التشغيل وأحجام الملفات ومحتويات WAL | تحليل ساكن فقط |
