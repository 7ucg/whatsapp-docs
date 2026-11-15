<!-- src-sha1: 8651b8d090e77403eb4a371175327e71510f2e61 -->
# WhatsApp نظام الحظر — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** مسار الحظر، دورة حياة WFAC، جمع إشارات السبام، بروتوكول GraphQL، نظام الاستئناف، وسم الحساب كمشبوه، الوقاية

---

## 1. نظرة عامة على البنية

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

**نتيجة حاسمة (صُحّحت في 2.26.41.6):** مزامنة حالة الحظر (WFAC) تعتمد على **السحب (pull) عبر MEX GraphQL**، أما *أحداث* الحظر والتحذير عند الاتصال فتصل عبر XMPP في عقدة `<failure>` الخاصة بتسجيل الدخول (reason 402/403/416/406، القسم 8.1). تحذير SMB soft-enforcement هو إشعار أعمال عبر XMPP. لم يُعثر على أي إشارة حظر عبر `<stream:error>` (هذا المعالج يتعامل فقط مع `code` 515/516 و`conflict type="device_removed"` وطرد `ack`).

---

## 2. دورة حياة حالة الحظر (WFAC)

### 2.1 آلة الحالات ذات الأربع حالات

| State | Value | Meaning |
|-------|-------|---------|
| `UNKNOWN_IN_CLIENT` | 0 | لا يوجد تخزين محلي (وهي أيضًا الحالة البديلة لأي سلسلة غير معروفة) |
| `CHECKPOINTED` | 1 | تقييد مخفف، قد يتطلب تحققًا. السلسلة `NO_APPEAL_OPENED` القادمة من الخادم تُحوَّل إلى `CHECKPOINTED` بواسطة `AbstractC38371GmM.A00` (جديد) |
| `BANNED` | 3 | حظر صارم، الحساب مقيّد، الاستئناف ممكن |
| `UNBANNED` | 2 | يعمل بالكامل |

### 2.2 SharedPreferences (MainPreferences)

```
wfac_ban_state              → "BANNED" | "CHECKPOINTED" | "UNBANNED" | "UNKNOWN_IN_CLIENT"
wfac_ban_status_token       → server token for status updates (must be non-empty)
wfac_ban_violation_type     → INT (violation category)
wfac_ban_violation_reason   → STRING
wfac_ban_violation_source   → INT (intent extra 0/1/2 kept, anything else -1; stored only for launch_source 2/3; default -1 via `HLK`; category names for 0/1/2 not found in 2.26.41.6, so the earlier SPAM/PHISHING/UNDERAGE mapping stays unverified)
wfac_last_ban_status_fetch_timestamp_ms → LONG (throttle, new)
```

غلاف التفضيلات: `HLK` (أداة قراءة الحالة تحلّل القيمة عبر `C36188FnW.A00`: سلسلة غير صالحة تُطلق "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 تسلسل انتقال الحالة

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

### 2.4 تسلسل إعادة ضبط الحظر

عند نجاح الاستئناف أو تحرير الحساب (`WfacBanViewModel.A0x` / `C36188FnW`، إعادة ضبط التسجيل):
1. يمسح: `wfac_ban_state`، `wfac_ban_status_token`، `wfac_ban_violation_*`، `wfac_last_ban_status_fetch_timestamp_ms`، `support_ban_appeal_user_banned_from_chat_disconnect` (جديد)
2. يسجّل خروج المستخدم (finishAffinity)
3. يعيد التوجيه إلى شاشة تسجيل الدخول

---

## 3. BizIntegrityQuery — بروتوكول GraphQL

### 3.1 تفاصيل تقنية

| Parameter | Value |
|-----------|-------|
| Query name | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (changed; was `25975613018777537`, rotated in 2.26.38.10, confirmed in 2.26.41.6 persist-id catalog; client_doc_id `14769534217004148908396994706`) |
| Schema | `whatsapp-android-mex` |
| Transport | MEX HTTP/2 POST → `/mex/query` |
| JID format | `<shortNum>@lid` (e.g. `1910@lid`) |

### 3.2 الطلب

2.26.41.6 (found, `BizIntegritySignalsGraphQLFetcher.A00`): كائن المدخلات `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`، صنف النتيجة `C48528LIw`. يُضاف `privacy_token` فقط عند تحقق بوّابة (`MZ4.A00`) ووجود TC-token مخزَّن. الاستجابة (found، `C51015Mjl`): الجذر `xwa2_fetch_wa_users[]`، ولكل مستخدم `integrity_signals_info` تحتوي `dhash`، `fb_linked_page_number_of_likes`، `ig_linked_age_number_of_followers` (كذا، المفتاح حرفي)، `is_banned`، `is_suspicious`، `is_suspicious_start_chat`، `join_date_ms` (سلسلة نصية، تُحلَّل إلى long)، `phone_country_code`، `trust_tier` (enum `M5B`)، `is_mv_subscribed` (تُخزَّن كـ `is_meta_verified`)، `meta_verified_info{mv_friction_eligibility}`، `integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}`، `hide_safety_tools_for_business`، `fmx_business_holdout_group`. قائمة الحقول أدناه هي إعادة بناء من 2.26.26.4 (inferred، غير مُعاد التحقق منها؛ شكل متغيرات الطلب `$userJids` يختلف عن شكل المدخلات في 2.26.41.6):

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

### 3.3 DTO الاستجابة — `BizIntegritySignals` (`C51530MtC`؛ كانت C39833Hhl في 2.26.26.4)

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

### 3.4 DTO لـ IntegrityTags

(`C51222Mno` قائمة من `C51359MqA`؛ التسلسل في `LwI`، الشكل بلا تغيير)

```
IntegrityTagInfo {
  tag         → String
  pipelineDS  → Date (originally Long ms)
  taggedDates → List<Date>
}
```

**تنسيق JSON في قاعدة البيانات:**
```json
[
  {
    "tag": "automation_bulk_messaging",
    "pipelineDS": 1700000000000,
    "taggedDates": [1699000000000, 1699500000000]
  }
]
```

### 3.5 أحداث التشغيل

| Trigger | Usecase string |
|---------|---------------|
| فتح محادثة | `"START_CHAT_CONTEXT"` (المشغّل الأساسي) |
| بعد إرسال رسالة | hook لاحق للإرسال |
| بدء التطبيق / تسجيل الدخول | مجدوِل في الخلفية |

### 3.6 أعلام الميزات

| Flag ID | Function |
|---------|---------|
| 11061 | مشغّل اكتشاف الحساب المشبوه (`N5r.A03`؛ موجود؛ يُقيَّم فقط لجهات الاتصال التي يبدأ مستوى اسمها المُوثَّق بـ `ent:`) |
| 11064 | أهلية إشارة الثقة عند بدء المحادثة (تشغيل/إيقاف) (`BizIntegritySignalsManager.A04`؛ موجود؛ الافتراضي false) |
| 11065 | مدة بقاء ذاكرة التخزين المؤقت لإشارة الثقة بالثواني (`C51855N0t.A00`؛ الافتراضي 86400، موجود في `C08J`) |
| 12709 | الأهلية لجهات الاتصال التي `hostStorage == 2` فيها للأعمال (`C197628ax.A06`)؛ الافتراضي false (موجود) |
| 16349 | مسار الاستعلام القسري في `BizIntegritySignalsManager.A04` (موجود؛ الافتراضي false) |
| 19793 | جديد في هذا الجدول: `N5r.A02`، يضبط إعادة استخدام الإشارات المخزَّنة في `C51855N0t.A02`؛ الغرض مُستنتج من الاستخدام؛ الافتراضي false |
| 12840 | تهيئة JSON مفهرسة بنوع المخالفة، الافتراضي `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`)؛ المستهلك (consumer) غير مُحدَّد؛ الغرض مُستنتج من أسماء المفاتيح (`max_dismiss_count`، `max_display_days`) ومن سلاسل النوع التي تستخدمها لافتة SMB soft-enforcement (7.4) |
| 19893 | تسجيل الرسالة النظامية لبطاقة FMX (موجود، `C198788cr`) |
| 26697 | BizIntegrity v2 (موجود، `C34735F5e`) |
| 27269 | تقسيم عدّاد الرسائل الواردة/الصادرة (موجود) |
| 34166 | معرّف حقن (injection id)، وليس علم ميزة (انظر WA_AB_PROPS.md)؛ تستخدمه الجهة الكاتبة لـ `start_chat_trust_signals` (`ContactInfoActivity`) |

ذاكرة تخزين مؤقت في الذاكرة داخل `BizIntegritySignalsManager.A02`: المدخلات صالحة لمدة 60000 ms (found).

---

## 4. وسم الحساب كمشبوه — متى، لماذا، كيف، الوقاية (أُعيد فحصه في 2.26.41.6؛ العناصر التي تعذّر تحديد موقعها مُشار إليها في مكانها)

> **النتيجة الجوهرية:** بالنسبة لأعلام BizIntegrity (`is_suspicious`، `trust_tier`، `is_banned`) لا يحسب العميل شيئًا: إنها تُحلَّل من استجابة GraphQL (`C51015Mjl`) وتُعرَض فقط. لم يُعثر على أي عتبة أو تقييم من جهة العميل لها. بشكل مستقل، نموذج محلي على الجهاز يُصدر أحكامًا محلية بخصوص الاحتيال (`odml_scam_alert_*`، 6.6، 7.6). طلب BizIntegrity يحمل فقط JIDs المستعلَم عنها، رمز خصوصية اختياري، وسياق تيليمتري (3.2)؛ أن يرفع العميل مقاييسه المحلية إلى مكان آخر غير موجود.

### 4.1 من يقرر؟

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

لا يوجد أي سهم من المقاييس المحلية إلى طلب BizIntegrity في العميل (3.2). أيّ من الإشارات من جهة الخادم يُولِّد الحكم غير ظاهر من ملف APK (التعلم الآلي من جهة الخادم مُستنتج). لا يملك العميل **أي عتبة محلية** على غرار "أكثر من X رسالة ← مشبوه" لأعلام BizIntegrity.

---

### 4.2 تدرُّج مستوى الثقة (مُحدَّد من الخادم)

مُوجَد في APK واتساب كـ enum مُجمَّع (`M5B` في 2.26.41.6؛ القيم بلا تغيير):

| Tier | Meaning | Effect |
|------|---------|--------|
| `SUSPICIOUS` | أعلى درجة خطورة — مُعلَّم بشكل نشط | كل التحذيرات نشطة، احتكاك في الواجهة، احتمال حجب الإرسال |
| `TIER_0` | أدنى مستوى شرعي (حسابات جديدة) | أهلية احتكاك مرتفعة |
| `TIER_1` | مستخدم قياسي | طبيعي |
| `TIER_2` | ثقة مرتفعة | احتكاك أقل |
| `TIER_3` | أعلى درجة ثقة شرعية | احتكاك أدنى |
| `UNTIERED` | لا تقييم | لا فحص يُطبَّق |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | غير معروف | احتياطي |

**فحص على مستوى الكود** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 الإشارات حول الحكم

لا يُرفِق العميل نقاط البيانات أدناه بطلب BizIntegrity (3.2). الجدول يسرد أين تظهر كل واحدة منها في العميل؛ أما تقييمها من الخادم فمُستنتج. عمود "Risk weight" من التقرير السابق لم يكن له دليل من جهة العميل وقد حُذِف.

| Signal | Where it appears in the client (2.26.41.6) | Role |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | ميزة على الجهاز (`integrityai.impl.InputFeatureProviderImpl`، علم 31535) | مدخل للنموذج المحلي على الجهاز، ليس للطلب |
| `mostRecentSenderScore` | ميزة على الجهاز (علم 31536) | نفس ما سبق |
| `dhash` | حقل استجابة، يُخزَّن كما هو | سلسلة معتمة مُقدَّمة من الخادم؛ لا يوجد كود عميل يُركِّبها (المعنى غير معروف؛ قراءة التقرير السابق "بصمة الجهاز" مُستنتجة) |
| `join_date_ms`, `phone_country_code` | حقول استجابة | تُخزَّن؛ لا عتبة من جهة العميل |
| عدادات FB/IG | حقول استجابة (`fb_linked_page_number_of_likes`، `ig_linked_age_number_of_followers`) | تُعرَض على بطاقة FMX (7.5) |
| `integrity_tags` | حقل استجابة `{tag, pipeline_date_ms, dates_ms[]}` | يُخزَّن كـ JSON؛ قيم الوسم معتمة لدى العميل |
| رمز الخصوصية | حقل طلب `privacy_token{tctoken, timestamp}` | اختياري، فقط عند تحقق بوّابة `MZ4.A00` ووجود TC-token مخزَّن |
| حجم الرسائل | عدّ محلي (`N54`، 6.2) | الرفع إلى الخادم غير موجود |
| حد الإذاعة (Broadcast) | علم 20278 الافتراضي `{"max_messages": 10000, "farthest_time_days": 30}` | المستهلك غير مُحدَّد (6.3) |

`isCountryMismatch` و`mostRecentSenderScore` هما ميزتا تعلم آلي ملموستان مُوجدتان في العميل (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`، 2.26.41.6). العلم 31535 يُغذّي isCountryMismatch، والعلم 31536 يُغذّي mostRecentSenderScore (found).

---

### 4.4 متى يُشغَّل فحص GraphQL؟

**بوّابة الأهلية** (found، `BizIntegritySignalsManager.A04`؛ JID المُستعلَم عنه هو نظير المحادثة):
1. علم الميزة **11064** مُفعَّل (الافتراضي false)
2. JID ليس من النوعين المستثنيين (`AbstractC24760wu.A03/A04`: JIDs البوتات وJID لرقم هاتف ثابت)
3. واحد من: جهة الاتصال حساب أعمال SMB (`N5r.A06`، مستوى الاسم المُوثَّق يبدأ بـ `smb:`)، أو العلم **12709** مُفعَّل و`hostStorage == 2` لجهة الاتصال (`C197628ax.A06`)، أو (مسار قسري، `A09`) العلم **16349** مُفعَّل و`N5r.A04/A06` صحيح (`A04` = `!A01 && !SMB && !ENT`؛ دلالات المساعد `N5r.A01` لم تُحسَم، فأي JIDs غير التجارية يسمح بها هذا المسار يبقى مفتوحًا)
4. للمسار غير القسري: انتهاء صلاحية التخزين المؤقت أو عدم وجوده (`C51855N0t`)

تصحيح مقابل التقرير السابق: في 2.26.41.6 البوّابة العادية لا تتجاوز حسابات الأعمال، بل تختارها (SMB أو مُستضافة)؛ المسار القسري (16349) قد يسمح بـ JIDs أخرى. تدفّق JADX لـ `A04` مُعاد بنيته جزئيًا، فهذه القراءة تأتي من شكل المُفكَّك مع أجساد المساعدين، لا من smali.

**مدة بقاء التخزين المؤقت:** علم الميزة **11065** بالثواني، الافتراضي **86400 (24 ساعة)** (found، `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**حجم الدفعة:** لا يوجد تقطيع لـ 975 JID في مسار جلب GraphQL (`BizIntegritySignalsManager.A03` يُمرِّر قائمة JIDs بلا تغيير). الثابت 975 يخص تقطيع عدّ الرسائل بـ SQL المحلي (6.2).

---

### 4.5 قيم integrity_tag المعروفة

السلسلتان `automation_bulk_messaging` و`spam` مُوجَدتان في `C35896FgX` و`ViewOnClickListenerC39711HTl`، لكنهما هناك تُقارَنان بـ `type` إشعار SMB soft-enforcement (`HAR.A07`، انظر 7.4)، ليس بـ `integrity_tags` من استجابة BizIntegrity. تظهران أيضًا كمفتاح لتهيئة العلم 12840 الافتراضية. العميل لا يُعدِّد قيم `integrity_tags` على الإطلاق؛ بلوبات JSON تُخزَّن معتمة. السلسلة `business_policy_violation` غير موجودة في java_src أو smali أو assets أو res لـ 2.26.41.6.

| Tag | Meaning |
|-----|---------|
| `automation_bulk_messaging` | نوع إشعار soft-enforcement (إرسال جماعي/آلي)؛ لم يثبت أنها قيمة لـ `integrity_tags` |
| `spam` | نوع إشعار soft-enforcement (سبام) |

---

### 4.6 ما يؤدي فعليًا إلى الاشتباه — مُستنتج من الكود

أُعيد الفحص في 2.26.41.6: العميل لا يحتوي على منطق أو عتبة أو وزن لأي صف أدناه، وطلب BizIntegrity لا يحمل أيًا من هذه المقاييس (3.2). الجدول كله يبقى **مُستنتجًا** (تخمين لسلوك الخادم بالاستناد إلى الإشارات الموجودة في العميل). صف "حساب جديد (< 24 ساعة)" بلا أي دعم: لا يوجد فحص لعمر الحساب في العميل (انظر 4.9 D).

| Behavior | Why it's risky | Weight |
|----------|---------------|--------|
| صادر مرتفع مقابل وارد منخفض (إرسال فقط، بلا ردود) | نمط توعية جماعية | عالٍ جدًا |
| بلد الهاتف ≠ بلد IP | `isCountryMismatch = 1.0` | عالٍ جدًا |
| نفس dhash على حسابات متعددة | مشغّل حظر الجهاز | عالٍ جدًا |
| إذاعة > 10,000 مستلم / 30 يومًا | حد صارم، تعليم فوري | عالٍ |
| `mostRecentSenderScore` مرتفع (مستلمون يبلّغون) | حلقة تغذية راجعة لتعلم آلي | عالٍ |
| حساب جديد (< 24 ساعة، بلا جهات اتصال) | مصداقية منخفضة (لا فحص عمر من جهة العميل) | عالٍ |
| بلا ربط FB/IG + نسبة إرسال مرتفعة | غياب دليل اجتماعي | متوسط |
| وجود integrity_tags سابقة | تأثير مخالفة سابقة | متوسط إلى عالٍ |
| `is_reach_out = 1` + بدء محادثات كثيرة مع مجهولين | نمط تواصل بارد | متوسط |

### 4.7 رموز سبب SpamWarning (تحذير قبل الحظر)

بلا تغيير في 2.26.41.6 (`SpamWarningActivity`: السبب الافتراضي 100، انتهاء الصلاحية الافتراضي -1؛ تبديل على 101، 102، 103، 104، 106، الافتراضي يشمل 105/غيره).

يُوصَّل عبر امتداد Intent `spam_warning_reason_key`، يُحدَّد من سمة `code` في `<failure reason="402">` من تسجيل دخول XMPP (>= 100) مع `expire`، `message`، `url` (found، `C0ZH.handleMessage` type 2؛ انظر 8.1):

| Code | Trigger | Countdown? |
|------|---------|-----------|
| 101 | نشاط سبام مُكتشَف | نعم |
| 102 | مخالفة إعادة توجيه | نعم |
| 103 | سبام في الحالة (status) | نعم |
| 104 | إعادة توجيه بوت | نعم |
| 105 | عام / افتراضي | دائم إذا كان الانتهاء = -1 |
| 106 | مخالفة أخرى | نعم |
| default | مخالفة غير معروفة | دائم إذا كان الانتهاء = -1، وإلا عدّ تنازلي |

`expiry_in_seconds == -1` + متصل: إنهاء فوري (الخادم رفع التحذير).

### 4.8 فئات SpamFlow ذات الصلة بوسم الاشتباه

97 فئة في APK (found: `C9E2`، مصفوفة من 96 عنصرًا بالإضافة إلى `1_1_spam_banner_report` المُلحَقة في النهاية، فهارس من 0 إلى 96؛ العدد السابق 92 والفهارس في الجدول تجاوزهما هذا). القائمة تُسلسَل بالاسم داخل عقدة SMAX `spam_list` (سمة `spam_flow` لكل مُدخَل، `wi_trace_id` اختياري من 24 حرفًا)، فالفهرس هو فقط موضع العنصر في مصفوفة العميل، وليس قيمة سلكية. جديد: `odml_scam_alert_blocked_composer_block`، `odml_scam_alert_suspicious_banner_block/_trust`، `odml_scam_alert_fmx_card_block/_trust`، `biz_spam_banner_block`، `1_1_spam_banner_block`، `chat_fmx_card_block`، `group_spam_banner_report`، `left_group_spam_banner_report`. العناصر المرتبطة مباشرة بحالة الاشتباه:

| Index | Category | Meaning |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | مُعلَّم من الخادم كمشبوه ← حجب FMX |
| 24 | `chat_fmx_card_block_suspicious` | محادثة محجوبة بسبب علم الاشتباه |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | أدوات أمان تُعرَض عند الاشتباه |
| 70 | `odml_scam_alert_bottom_sheet_block` | تعلم آلي على الجهاز للاحتيال ← حجب |
| 71 | `odml_scam_alert_bottom_sheet_trust` | تعلم آلي على الجهاز للاحتيال ← ثقة |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | لافتة سبام ثنائية (مُعلَّم من الخادم) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | سؤال ثقة (مُعلَّم من الخادم) |
| 89 | `user_initiated_chat_suspicious_banner_block` | لافتة اشتباه عند بدء محادثة |
| 94 | `1_1_old_spam_banner_block` | لافتة سبام قديمة |
| 96 | `1_1_spam_banner_report` | بلاغ سبام ثنائي |

### 4.9 آليات الحماية — ما تعرضه الواجهة

قائمة "عوامل الحماية" السابقة قراءة لتعلم آلي من جهة الخادم بلا أي دعم من جهة العميل. ما يحتويه 2.26.41.6 فعليًا:

#### A) حالة الأعمال
ليست تجاوزًا. بوّابة الأهلية العادية تختار جهات اتصال SMB (وجهات `hostStorage == 2` تحت العلم 12709)، انظر 4.4. العلم 2923 (سابقًا: "مفتاح تحقق غير الأعمال") لم يُحدَّد موقعه: لا يوجد فحص علم بهذا المعرف ولا تهيئة افتراضية له في java_src أو smali لـ 2.26.41.6.

#### B) Meta Verified (mvFrictionEligibility)
حقل استجابة `meta_verified_info.mv_friction_eligibility` (found، `C51015Mjl`)، يُخزَّن كـ `mv_friction_eligibility`. `is_mv_subscribed` يُخزَّن منفصلًا كـ `is_meta_verified`. بطاقة FMX (`C94p`) تقرأ العلم، ومع تفعيل العلم 15735 تضيف رابط "معرفة المزيد". نتيجة تخفيض عتبات الاحتكاك غير ظاهرة في العميل (مُستنتجة).

#### C) الحسابات الاجتماعية المرتبطة (FB/IG)
`fb_linked_page_number_of_likes` و`ig_linked_age_number_of_followers` تُحلَّلان كأعداد صحيحة (`optInt`) وتُعرَضان على بطاقة FMX (7.5). هما عدّادان، وليسا قيمتين منطقيتين (found). أن يُوزِنهما الخادم كعامل حماية مُستنتج.

#### D) فترة سماح عمر الحساب
غير موجود. المقارنة الوحيدة الشبيهة بالعمر هي مدة بقاء التخزين المؤقت على `last_sync_ts` مقابل العلم 11065 (4.4). `join_date_ms` يُخزَّن لكن لا يوجد منطق نافذة سماح في العميل.

#### E) قائمة بيضاء / قائمة تحقق (العلم 12709)
تغيّر: الفحص `C197628ax.A06(userJid)` هو `hostStorage == 2` على سجل الاسم المُوثَّق لجهة الاتصال (`AnonymousClass119`)، خاصية محلية، لا قائمة موافقة مسبقة من جهة الخادم. هذا يؤهّل جهة الاتصال للاستعلام؛ ولا يُعيد مبكرًا.

#### F) hideSafetyToolsForBusiness (حقل من الاستجابة)
حقل استجابة `hide_safety_tools_for_business`، يُخزَّن في `hide_safety_tools_for_business`. تأثيره على الواجهة لم يُعاد تتبّعه؛ قول التقرير السابق أنه يخفي واجهة التحذير فقط دون تغيير حالة الاشتباه غير مُتحقَّق منه.

---

### 4.10 الوقاية — ما يكشفه الكود

هذا الجزء نصيحة مُستمَدَّة من الحقول أعلاه. العميل لا يملك منطقًا يُثبِّت أيًا منها؛ عامِل كل عنصر كـ **مُستنتج**، إلا ما هو مُشار إليه كـ found.

**سلوكي (مُستنتج):**
- حافظ على توازن نسبة الصادر إلى الوارد
- تجنّب عدم تطابق البلد بين الرقم والشبكة (العميل يُغذّي `isCountryMismatch` إلى النموذج المحلي على الجهاز، found؛ استخدام الخادم مُستنتج)
- ابقَ تحت تهيئة الإذاعة للعلم 20278 (10,000 رسالة / 30 يومًا؛ المستهلك غير مُحدَّد)

**جودة الحساب (مُستنتج):**
- عدّادات FB/IG المرتبطة وMeta Verified تُعرَض أو تُخزَّن من العميل (found)؛ تأثيرها على الحكم مُستنتج
- نافذة حساب جديد (24 ساعة) والقائمة السوداء لـ dhash غير مدعومتين بأي كود عميل (انظر 4.9 D و4.3)

**تقني (found):**
- `privacy_token` (TC-token) يُضاف إلى طلب BizIntegrity فقط عند تحقق بوّابة `MZ4.A00` ووجود TC-token مخزَّن

**التوقيت (found):**
- الإشارات المخزَّنة مؤقتًا تُعاد استخدامها حتى يصبح `last_sync_ts` أقدم من العلم 11065 (الافتراضي 86400 ثانية)؛ المُدير يحتفظ بمدخل ذاكرة إضافي لمدة 60000 ms
- الإشارات تبقى في `wa_biz_integrity_signals` حتى تُستبدَل باستجابة جديدة

---

## 5. قواعد بيانات SQLite المحلية

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found، `C53116Nmn`، 17 عمودًا شاملة `_id`): تُضيف `is_meta_verified` و`fmx_business_holdout_group`؛ `fb_linked_page_number_of_likes`، `ig_linked_page_number_of_followers`، `join_date_ms`، `last_sync_ts` من نوع REAL، `mv_friction_eligibility` و`is_meta_verified` بلا افتراضي مُحدَّد. فهارس فريدة `biz_integrity_signals_jid_index`، `biz_integrity_signals_chat_row_id_index`؛ محفِّز `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). المتجر: `LwI` (تسميات `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`، `BizIntegritySignalsStore/saveBusinessIntegritySignals`). المخطط أدناه هو إصدار 2.26.26.4.

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

كاتب/قارئ: `LwI` (المتجر)، `BizIntegritySignalsManager.A06(UserJid)` يقرأ الخريطة `ConcurrentHashMap` في الذاكرة (found: `A06` يقرأ الخريطة في الذاكرة، `A07` يقرأها مع تحميل متأخر من قاعدة البيانات، `A0A` يُحدِّث ويُخزِّن؛ الأسماء السابقة `A08`/`A01` من 2.26.26.4 لم تعد موجودة)

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

قارئ: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`؛ كانت C2M7.A0K) ← يُعيد زوج `(is_sender_new_account, is_sender_suspicious)`

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

تسمية الاستعلام: `"GET_INTEGRITY_CHAT_INFO"` (استعلام دُفعي بـ `chat_row_id IN (...)`)، المتجر `C33O`، المخطط `C08970Ox` (فهرس `integrity_chat_info_chat_row_id_index`، محفِّز `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). بلا تغيير.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

مُوجَد في 2.26.41.6: المخطط `AHY` (أعمدة `jid`، `last_delivered_sort_id` LONG، `last_read_sort_id` LONG)، فهرس فريد `biz_integrity_chat_settings_index` على `jid`، محفِّز `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). الدور غير معروف.

---

## 6. جمع إشارات السبام (من جهة العميل)

(أُعيد فحصه في 2.26.41.6؛ العناصر التي تعذّر تحديد موقعها مُشار إليها في مكانها.)

### 6.1 dhash

`dhash` سلسلة نصية في استجابة BizIntegrity (`integrity_signals_info.dhash`)، تُخزَّن نصًّا صريحًا في `wa_biz_integrity_signals.dhash`. لا يوجد كود عميل يُركِّبها: لا مُدخَل من موديل الجهاز، نظام التشغيل، إصدار التطبيق، الرقم، المنطقة الزمنية، Android ID أو بصمة البناء، ولا شيء يرفعها. وصف التقرير السابق "بصمة جهاز / قائمة سوداء من جهة الخادم" غير مدعوم؛ المعنى غير معروف. سلاسل `dhash` الأخرى في APK (قائمة الحظر، إلغاء اشتراك الأعمال) تجزيئات أدلة لا صلة لها.

---

### 6.2 معدّل الرسائل

مُوجَد: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`، مساعد `N54`) يعدّ الرسائل محليًا على مدى زمني لقائمة JIDs، بأسماء بديلة SQL:
- `incoming_count`: الرسائل بـ `from_me = 0`
- `incoming_threads_count`: `chat_row_id` فريدة للرسائل الواردة
- `outgoing_count`: الرسائل بـ `from_me = 1`
- `outgoing_threads_count`: `chat_row_id` فريدة للرسائل المُرسَلة
- عدد الرسائل المحذوفة: `messages_count_after_privacy_token` (أيضًا `messages_count`، `outgoing_messages_count`) من `integrity_deleted_chat_message_count`

علم الميزة 27269 يتحكم بما إذا كانت الواردة/الصادرة تُعدّ منفصلة أو كمجموع مُدمَج (found في نفس المعالج).
حجم الدفعة: **975 JID** لكل نداء معالجة SQL (found: `C20H.A1A(list, 975)`، تقطيع لحد متغيرات SQLite، لا دفعة شبكة).
غير مُحدَّد: تقسيم يومي/ساعي، معدّل لكل جهة اتصال؛ وجهة العدّادات بعد العدّ لم تُتبَّع.

---

### 6.3 حدود الإذاعة (حسابات الأعمال)

تهيئة الميزة 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found كافتراضي في `C08J`/`C09W`).
- حد 10,000 رسالة لكل 30 يومًا هو القيمة الافتراضية في التهيئة؛ مستهلك هذا JSON (الكود الذي يُطبِّقه قبل الإرسال، `renewal_date`، تقييد لكل مستلم، تصنيف تسويقي مقابل عادي) لم يُحدَّد موقعه: سلاسل المفاتيح `max_messages`/`farthest_time_days` تظهر فقط في جداول الافتراضيات، و`renewal_date` لا تظهر في java_src.

---

### 6.4 تطبيق GAP (Global Abuse Prevention)

مُوجَد: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) يُتجاهَل عند إيقاف علم الميزة 14837، ويُخزِّن `LAST_MARKETING_MESSAGE_TIMESTAMP` في SharedPreferences (`C67902uK`) عند وصول رسالة تسويقية أحدث. العلم 25631 يضبط مسار مشغّل آخر. التوسيع "Global Abuse Prevention" غير موجود في الكود (تسمية غير مُتحقَّق منها).

الحالة المُتتبَّعة (`ChatDescription`، found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (التحليلات الموحَّدة/Federated Analytics)

مُوجَد: الحزمة `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`، `WaFaReportScheduler`، `FaReportRunner`، `WaFaReportSubmitter`، `FaTeeConnection`، `FaTeeAcsRepository`، `FaAcsWarmer`). التقارير تمر عبر اتصال TEE مُوثَّق بـ ACS (رؤوس `x-acs-token`، `x-acs-configid`، `x-acs-project-name`؛ جلب مفتاح عام OHAI). وقت التشغيل التالي في التفضيل `fa_next_report_run_timestamp`.
غير مُحدَّد: محتوى التقارير. قائمة المقاييس من التقرير السابق (تبنّي الميزات، الأعطال، الكمون، RAM/التخزين/نظام التشغيل، تحديد الموقع الجغرافي، بيانات الجلسة، نوع الاتصال) لم تُوجَد كـ كود؛ محتوى التقرير يُحدَّد عبر التهيئة، لذا لا يمكن قراءته من العميل.

---

### 6.6 استخراج ميزات تعلم آلي (اكتشاف احتيال على الجهاز)

ميزتان ملموستان مُوجَدتان في العميل المُفكَّك:
- `isCountryMismatch` (float 0.0/1.0): بلد المُرسِل ≠ بلد المُستلِم ← **خطر مرتفع**
- `mostRecentSenderScore` (float): درجة سُمعة تعلم آلي للمُرسِل

أعلام الميزات 31535/31536 تتحكم بقيمهما (found). إرسال النتائج إلى الخادم لتصنيف تعلم آلي ثانوي مُستنتج.

---

## 7. مكوّنات الواجهة: الاشتباه، التحذيرات، الحظر

(أُعيد فحصه في 2.26.41.6: `SpamWarningActivity` أصبحت الآن `com.whatsapp.userban.spamwarning`، `SuspiciousFmxBottomSheetFragment` أصبحت `com.whatsapp.fmx` بالإضافة إلى صنف فرعي جديد `SuspiciousSmbFmxBottomSheetFragment`. شروط التشغيل في 7.2 و7.4 و7.5 مُصحَّحة أدناه.)

### 7.1 SpamWarningActivity

معاملات Intent:
- `spam_warning_reason_key` (int): رمز السبب
- `expiry_in_seconds`: عدّ تنازلي (-1 = دائم)
- `spam_warning_message_key`: نص مخصَّص
- `faq_url_key`: رابط الأسئلة الشائعة

رموز الأسباب:

| Code | Meaning |
|------|---------|
| 100 | تحذير سبام عام |
| 101 | نشاط سبام مُكتشَف |
| 102 | مخالفة إعادة توجيه |
| 103 | سبام في الحالة (status) |
| 104 | إعادة توجيه بوت |
| 105 | عام / دائم |
| 106 | مخالفات أخرى |

إذا `expiry_in_seconds != -1` ← يُعرَض عدّاد تنازلي.
إذا كانت `-1` + متصل ← إنهاء فوري (الخادم رفع التحذير).

### 7.2 Suspicious FMX Bottom Sheet (`SuspiciousFmxBottomSheetFragment`)

مُوجَد: ورقة معلومات (روابط "معرفة المزيد" `about-blocking-reporting`، `examples-of-scams`)، ليست حاجبًا مُحكومًا بحالة. تُفتَح بالنقر على زر حالة الاشتباه على بطاقة FMX (`C93z.setupSuspiciousButtons`، النسخة الخاصة بـ SMB `C94p` تفتح `SuspiciousSmbFmxBottomSheetFragment`) ومن `C512928n` (نسخة SMB عندما تكون جهة الاتصال حساب أعمال، `A0T()`)، عبر المساعدين `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

شروط التشغيل الأربعة من التقرير السابق (`is_suspicious == 1`، `is_suspicious_start_chat == 1`، `is_reach_out == 1`، `chat_fmx_card_block_suspicious == 1` كحجب للإرسال) غير مدعومة: القطعة نفسها لا تقرأ أيًا منها، و`chat_fmx_card_block_suspicious` اسم فئة في SpamFlow (4.8)، وليس علمًا مخزَّنًا. ما هو مُوجَد: سياق بدء المحادثة يُعرَض عندما تكون `is_suspicious_start_chat` صحيحة (`StartChatContextUtils`)، وبطاقة FMX تحسب `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 واجهة حظر WFAC الصارم

| Class | Function |
|-------|---------|
| `WfacBanActivity` | نقطة الدخول، معلومات الحظر + زر الاستئناف |
| `WfacBanInfoFragment` | تفاصيل المخالفة + رابط الاستئناف |
| `WfacBanDecisionFragment` | إجراء المستخدم (تم تقديم الاستئناف) |
| `WfacUnbanDecisionFragment` | تأكيد ما بعد الاستئناف |

المشغّل (تغيّر): `Main.A5D()` لم يعد موجودًا؛ ما يُعادله هو `Main.A5W()`، الذي يقرأ `wfac_ban_state` عند البدء (تبديل على "UNBANNED" / "BANNED" / "CHECKPOINTED"، حالة تسجيل 21، سجلّ "main/me/wfac ban") ويبدأ `WfacBanActivity` عبر `HBC`. لم يُعثر على أي مستمع لتغيّر SharedPreferences. `wfac_ban_state` تُكتَب من معالج جلب حالة الحظر ومن `WfacBanActivity.onCreate` (2.3). مسار فشل تسجيل الدخول (403) يفتح الشاشة الأقدم `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`) بدلًا من ذلك. 2.26.41.6: الأصناف الآن في `com.whatsapp.waffle.wfac.ui` (أيضًا `WfacBanBaseFragment`)؛ النشاط يُفتَح عبر مساعد Intent `HBC` وانتقال شاشة `I1T` (`transitionToScreen`).

#### 7.3a تسخين مُسبَق لتوثيق Play Integrity في استئناف الحظر (جديد في 2.26.45.10، found)

`com.whatsapp.userban.ui.BanAppealActivity` (شاشة الاستئناف على مسار فشل تسجيل الدخول، أعلاه) تُطلق الآن **تسخينًا مُسبَقًا لتوثيق Play Integrity** كجزء من دورة حياتها، قبل تقديم الاستئناف الفعلي — ثلاثة أصناف جديدة تحت `com.whatsapp.userban.signals`:

| Class | Role |
|-------|------|
| `BanAppealPlayIntegrityPrewarmer` (جسم coroutine `$prewarm$1`) | يطلب/يُحضِّر رمز Google Play Integrity مبكرًا، قبل أن ينهي المستخدم نموذج الاستئناف |
| `BanAppealSignalsAggregator` | يُجمِّع الرمز المُسخَّن مسبقًا مع مصادر إشارات غير متزامنة أخرى (كل منها يُحَل عبر مؤجَّل من النوع `LX/05b;`) في مُجمَّع واحد |
| `BanAppealExistRequester` | يفحص وجود الاستئناف/الحظر، وهو الموضع الذي تعيش فيه `appeal_token` و`backup_token` وطلب `ban_appeal` نفسه (`no_appeal_token` كحالة فشل مُسجَّلة) |

`BanAppealActivity` تُنشئ `BanAppealPlayIntegrityPrewarmer$prewarm$1` مباشرة داخل طريقتها لمسار الاستئناف (المُعاد تسميتها في smali `A44`) وتُشغِّلها على نطاق coroutine — أي أن التسخين المُسبَق يبدأ بمجرد فتح شاشة الاستئناف، لا عند لحظة التقديم، بحيث يكون الرمز جاهزًا مسبقًا بحلول وقت نشر `BanAppealExistRequester` للاستئناف. المُسخِّن المسبق يُسجِّل أربع نتائج فشل مُسمَّاة كسلاسل نصية صريحة: `"BanAppealPlayIntegrityPrewarmer/prewarm nonpositive_timeout"`، `"...prepare_failed"`، `"...api_error"`، `"...unavailable"` — وهي الدليل البنيوي الوحيد على أنماط فشلها؛ لم يُعثر على سلسلة نصية مقابلة لمسار النجاح (الأرجح أنه مجرد كائن رمز مُخزَّن مؤقتًا بلا سجلّ).

**غير قابلة للوصول بشكل مستقل**: Play Integrity يُصدِر رمزًا مُوثَّقًا من Google، خاصًّا بكل جهاز/تطبيق، لا يمكن لعميل خارجي تزييفه أو إعادة استخدامه لجهاز آخر — هذا يرفع عتبة أتمتة الاستئناف، ولا يفتح سطحًا جديدًا للاستئناف. حالات الحظر `unbanReasonData`/`IN_REVIEW` وبقية مسار الاستئناف (7.3، جدول 7.3) بلا تغيير في طبيعتها؛ فقط مسار التقديم اكتسب خطوة التوثيق هذه.

### 7.4 التطبيق المخفَّف لـ SMB

تغيّر: المشغّل ليس `is_suspicious=true` + `integrity_tags` تحتوي `"business_policy_violation"` (هذه السلسلة غير موجودة في 2.26.41.6). إنه إشعار أعمال عبر XMPP (المعالج `AnonymousClass142`، معرّف الإشعار 202) بعنصر فرعي `biz_integrity_warning_notification > violation`:

| Attribute | Use |
|-----------|-----|
| `source` | مصدر المخالفة (مطلوب) |
| `type` | نوع المخالفة، مثل `automation_bulk_messaging`، `spam` (تُقارَن في `C35896FgX`) |
| `severity` | مثل `"severe"` يُغيِّر نص اللافتة (`C35896FgX`، `WABIEnforcementEducationFragment`) |
| `policy_url` | هدف الرابط (مطلوب) |
| `priority` | عدد صحيح >= 0 (مطلوب) |
| `status` | `active` (تُخزَّن، تُعاد ضبط العدّادات) أو `inactive` (تُزال) |

العميل يُنشئ `SMBSoftEnforcementNotification` (`HAR`) بـ `notificationType` ثابتة على `"warning"` و`bannerNotificationTimeStamp` = وقت الاستلام، ويُخزِّن مصفوفة JSON تحت التفضيل `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) بالمفاتيح أدناه. عدّادات لكل إشعار هي تفضيلات int: `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

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

JSON التقرير السابق (`notification_type: soft_enforcement`، `violation_type`، `education_url`، `action_required`) غير موجود في العميل. الواجهة: `SMBSoftEnforcementEducationFragment`، `WABIEnforcementEducationFragment` في `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 بطاقة FMX (بطاقة إشارة الثقة)

مُوجَد: رسالة نظامية من النوع 129 (`0x81`، `C57172Xr`) تُنشَأ في `C198788cr` ("Creating FMX card system message for chat"، "ContactsProcessor/added contact info message")؛ العلم 19893 يضبط فقط حدث تحليلات هناك. الكتابة غير المتزامنة إلى `start_chat_trust_signals` مضبوطة بـ `C1P2.A01()` (العلم غير مُحدَّد) وتجري عبر `C65972r0`. البطاقة (`C94p`) تعرض عدّادات لايكات FB وعدّادات متابعي IG وعلم احتكاك Meta Verified؛ `"SUSPICIOUS".equals(trust_tier)` تختار نسخة الاشتباه. عرض عمر الحساب وشرط عرض "حساب أعمال/جهة اتصال مجهولة" لم يُحدَّد موقعهما.

---

### 7.6 تنبيه ODML للاحتيال (تعلم آلي على الجهاز)

نموذج تعلم آلي قابل للتنزيل عبر رمز ACS `"WA_ODML"` (found في `OdmlModelDownloadClient`، `ODML_MODEL_DOWNLOAD`، معرّف `27301080136160169`، مدة البقاء 345600 ثانية = 4 أيام؛ حجم التخزين المؤقت 64 غير مُحدَّد). قابل للتبديل من قبل المستخدم عبر `ScamDetectionSettingsActivity`. القُمع (funnel) يُتبَّع عبر معرّف الجلسة / المصدر / امتدادات Intent لنقطة الدخول.

---

## 8. XMPP والعُقَد (سياق الحظر)

(أُعيد فحصه في 2.26.41.6 بقراءة معالجات تسجيل الدخول وخطأ البث؛ القسم 8.1 مُصحَّح. فحص سابق على 2.26.35.2 لم يرَ أي دفع حظر عبر XMPP؛ تلك الملاحظة تجاوزها مسار فشل تسجيل الدخول أدناه.)

### 8.1 `<failure>` تسجيل الدخول يحمل الحظر والتحذيرات

الدعوى السابقة "الحظر يأتي فقط عبر MEX GraphQL" خاطئة بالنسبة للأحداث عند وقت الاتصال. `HandlerThreadC12340b0.A13` تقرأ عقدة نتيجة تسجيل الدخول؛ لـ `<failure>` تأخذ `reason` (int) وتبني استثناء `C45351tB` (found):

| `reason` | Type | Attributes read | Client reaction (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | خطأ خادم، مسار إعادة المحاولة |
| 402 | 2 (default) | `code`، `expire`، `message`، `url`، `appeal_token`، `age_collection` | `SpamWarningActivity` بـ `spam_warning_reason_key` = `code` (>= 100)، `expiry_in_seconds`، نص، رابط الأسئلة الشائعة |
| 402 + `appeal_token` + `code` 106 | 13 | same | `ContextualAgeCollectionActivity` (امتدادات `appealToken`، `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | same | مسار "U13 Banned PAA Pending" (تفضيلات حساب مُدار، onboarding) |
| 403 | 7 | `is_eu`، `vt`، `violation_reason`، `appeal_token`، `reg_info` | حظر دائم: `HGB.startPermanentBanFlow` ← `BanAppealActivity` (بعد تأخير العلم 19714 بالمللي ثانية) |
| 405 | 3 | `t` (ثوان) | يكتب التفضيل `software_forced_expiration` |
| 406 | 5 | `code` | التفضيل `underage_account_banned` |
| 416 | 11 | `vt`، `violation_reason`، `source_acct`، `appeal_token` | `WfacManager.startUnderageBanFlow`؛ `violation_reason == "u13_checkpoint"` يضبط `support_ban_appeal_user_banned_from_chat_disconnect` |
| other | 0 | - | تسجيل خروج (مسار "exception-password") |

كل أنواع الفشل تقرأ أيضًا سمات واجهة تسجيل الخروج الاختيارية: `logout_message_header`، `logout_message_subtext`، `logout_message_locale`، `logout_main_button_text`، `logout_main_button_url`، `logout_secondary_button_text`، `logout_secondary_button_url`. `location` تُقرَأ من العقدة للتوجيه.

`<stream:error>` (مُعترِض قراءة مُرافِق، `C40601l6`): `code` 515 / 516، عنصر فرعي `conflict type="device_removed"` (إلغاء تسجيل)، عنصر فرعي `ack` (طرد). لم يُعثر على أي عنصر فرعي خاص بالحظر. `<presence type="unavailable">` وأكواد إغلاق WebSocket لم تُفحَص.

### 8.2 رموز خطأ XMPP (قاموس ثنائي)

قاموس `AbstractC40911lb` (`A00` لبايت واحد، `A01` لبايتين). وجود رموز جدول التقرير السابق:

| Token string | In dictionary |
|-------------|---------------|
| `stream:error` | نعم |
| `conflict` | نعم |
| `not-authorized` | نعم |
| `item-not-found` | نعم |
| `server-error` | نعم |
| `401` | نعم |
| `policy-violation` | غير موجود |
| `403` | غير موجود كرمز (قيمة `reason` 403 تُقرَأ كسمة int) |

عمود "Meaning" في التقرير السابق (مثلًا `403` = "Forbidden (ban-related)") كان مُستنتجًا؛ معنى 403 فقط مدعوم الآن من معالجة `<failure>` أعلاه. موجود أيضًا في القاموس: `404`، `407`، `failure`، `locked`.

### 8.3 استجابات IQ للحسابات المُقيَّدة

غير موجود. لا فضاء الأسماء `urn:ietf:params:xml:ns:xmpp-stanzas` ولا النصوص "Account restricted" / "User banned" موجودان في java_src أو الموارد لـ 2.26.41.6، ولا رموز `forbidden` / `service-unavailable` في القاموس. أمثلة XML من التقرير السابق غير مُتحقَّق منها ولا ينبغي الاعتماد عليها (قد تكون توضيحية). معالجة أخطاء IQ لكل استعلام (مثل محلِّلات `item-not-found`، `not-authorized` كـ `K3P`، `C23205A1e`) لم تُتبَّع للحسابات المُقيَّدة.

---

## 9. تدفق البيانات الكامل (من البداية إلى النهاية)

(أُعيد فحصه في 2.26.41.6: doc_id `28596420510007620`، شكل المدخلات `query_input`، أسماء الأصناف أعلاه. أسهم `isBanned` ← `wfac_ban_state` ← `Main.A5D()` من مخطط 2.26.26.4 أُزيلت لأن هذا الربط غير موجود في الكود؛ انظر القسمين 1 و2.3.)

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

## 10. طلب الاستئناف (2.26.41.6)

مُوجَد في `C37414GLt`: `variables` الطلب بصيغة JSON تحمل `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` و`app_id` (`"dev.app.id"`)؛ النص الصريح قبل التشفير هو `{token, debug_info, description}`؛ تسمية السياق `"WA_INAPP_BAN_APPEALS"` (معلومات اشتقاق المفتاح). النقل (found، `AbstractC40195HfH`): طلب Facebook Graph POST عادي إلى `https://<host>.facebook.com/graphql` بـ `doc_id` وحقل `access_token`، وليس MEX. `C37414GLt` يُمرِّر `doc_id` **38509456535312323** عندما يكون `hg3.A04.A00()` صحيحًا، وإلا **5473316762755318**. اسم العملية `submitBanAppeal` لا يظهر كسلسلة نصية في java_src أو smali أو assets أو res لـ 2.26.41.6، ولا doc_id موجود في كتالوج استعلامات المشروع، فالاسم غير مُتحقَّق منه. قبل التقديم، `C40191HfD` تُحلِّل استجابة أولى بـ `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}` التي تُوفِّر مادة المفتاح للتشفير.

---

## 11. التغييرات مقابل 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| BizIntegrityQuery doc_id | `25975613018777537` | `28596420510007620` (دُوِّر في 2.26.38.10) |
| شكل الطلب | قائمة `$userJids` (إعادة بناء) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| صنف DTO | `C39833Hhl` | `C51530MtC` (17 حقلًا: + `isMetaVerified`، `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 عمودًا | + `is_meta_verified`، `fmx_business_holdout_group`؛ العدّادات REAL |
| المتجر / المدير | `BizIntegritySignalsManager.A08/A01` | المتجر `LwI`، المخطط `C53116Nmn`، مدير A02 بذاكرة مؤقتة 60 ثانية |
| قارئ start_chat_trust_signals | `C2M7.A0K` | `C57342Yp` |
| enum مستوى الثقة | غير مُسجَّل، 7 قيم | `M5B`، نفس 7 القيم |
| حزمة واجهة WFAC | `com.whatsapp.waffle.wfac` (مسطَّحة) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| تفضيلات WFAC | 5 مفاتيح | + `wfac_last_ban_status_fetch_timestamp_ms` (تقييد تحديث 5 ثوان)، `support_ban_appeal_user_banned_from_chat_disconnect` تُمسَح عند إعادة الضبط |
| تحليل حالة الحظر | 4 حالات | نفسها؛ `NO_APPEAL_OPENED` تُحوَّل إلى `CHECKPOINTED` |
| Flags | 11061/11064/11065/12709/16349/19893/26697/27269 | جميعها موجودة؛ + 19793 (N5r.A02) |
| رموز SpamWarning 100-106 | نعم | بلا تغيير |
| integrity_tags | `automation_bulk_messaging`، `spam` | بلا تغيير |
| SpamFlow | 92 فئة | 97؛ `odml_scam_alert_*`، `biz_spam_banner_block`، أخرى أُضيفت |
| ميزات تعلم آلي | `isCountryMismatch`، `mostRecentSenderScore` (31535/31536) | بلا تغيير، في `integrityai.impl.InputFeatureProviderImpl` |
| حد الإذاعة 20278 | 10000 / 30 يومًا | بلا تغيير |
| أحداث الحظر/التحذير عند الاتصال | "لا إشارة حظر عبر XMPP" | `<failure>` تسجيل دخول XMPP: reason 402 (SpamWarning / U13)، 403 (حظر دائم ← `BanAppealActivity`)، 405، 406، 416 (WFAC تحت السن)؛ `C45351tB`، `C0ZH` |
| `Main.A5D()` | يتفاعل مع تغيّر `wfac_ban_state` | غير موجود؛ `Main.A5W()` تقرأ الحالة عند البدء (حالة تسجيل 21) وتفتح `WfacBanActivity` عبر `HBC` |
| كاتبو `wfac_ban_state` | غير مُسجَّل | معالج جلب حالة الحظر `C40191HfD`؛ `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED حسب مصدر التشغيل)؛ لا ربط من `is_banned` |
| أهلية BizIntegrity | "حسابات الأعمال تتجاوز الفحص" | تختار جهات اتصال SMB (مستوى `smb:`) أو `hostStorage == 2` (12709)؛ مسار قسري 16349؛ لا تقطيع لـ 975 JID في الجلب |
| دفعة 975 | دفعة GraphQL | تقطيع عدّ رسائل SQL محلي (`N54`) |
| العلم 12709 | قائمة بيضاء من جهة الخادم | فحص محلي `hostStorage == 2` |
| العلم 2923، فترة سماح عمر 24 ساعة، تركيب `dhash` | مُفترَضة | غير موجودة في 2.26.41.6 |
| قيم `integrity_tags` | `automation_bulk_messaging`، `spam` | هذه السلاسل هي قيم `type` لإشعار SMB soft-enforcement، وليست `integrity_tags` |
| تطبيق SMB المخفَّف | وسم `business_policy_violation` + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`؛ مفاتيح JSON المخزَّنة `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`؛ العلم 12840 |
| فهارس/عدد SpamFlow | 92، مثلًا `odml_scam_alert_bottom_sheet_block` = 65 | 97 عنصرًا (`C9E2`)، نفس الأسماء بفهارس منزاحة (70، 71، 76، 85، 89، 94، 96) |
| `SuspiciousFmxBottomSheetFragment` | تُفتَح بأربع شروط بيانات | ورقة معلومات تُفتَح من أزرار بطاقة FMX / `C512928n` |
| طلب الاستئناف | طفرة MEX `submitBanAppeal` | Graph `https://<host>.facebook.com/graphql` بـ doc_id 38509456535312323 / 5473316762755318، يسبقه جلب `purpose_public_keys`؛ اسم العملية غير موجود |
| `wa_biz_integrity_chat_settings` | غير مُحدَّد | مُوجَد (`AHY`) |
| رموز خطأ XMPP | رموز `policy-violation`، `403` | غير موجودة في القاموس؛ `forbidden`/`service-unavailable` ونصوص 8.3 غائبة |

لا يزال مفتوحًا في 2.26.41.6: أسماء الفئات خلف `wfac_ban_violation_source` 0/1/2؛ مستهلك العلم 20278 والعلم 12840؛ دلالات المساعد `N5r.A01`؛ محتوى تقارير WaFA؛ معالجة أخطاء IQ لكل استعلام للحسابات المُقيَّدة (8.3)؛ عرض عمر الحساب على بطاقة FMX؛ العلم خلف `C1P2.A01()`.
