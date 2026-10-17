<!-- src-sha1: 7460884998f14495a9fdb811db77f25ed82ce6f6 -->
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

غلاف التفضيلات: `HLK` (قارئ الحالة يحلل عبر `C36188FnW.A00`: السلسلة غير الصالحة تُطلق "Invalid BanState"). ViewModel: `C36188FnW` (WfacBanViewModel).

### 2.3 مسار انتقال الحالة

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

عند نجاح الاستئناف أو تحرير الحساب (`WfacBanViewModel.A0x` / `C36188FnW`، resetRegistration):
1. يمسح: `wfac_ban_state`، `wfac_ban_status_token`، `wfac_ban_violation_*`، `wfac_last_ban_status_fetch_timestamp_ms`، `support_ban_appeal_user_banned_from_chat_disconnect` (جديد)
2. يسجّل خروج المستخدم (finishAffinity)
3. يعيد التوجيه إلى شاشة تسجيل الدخول

---

## 3. BizIntegrityQuery — بروتوكول GraphQL

### 3.1 التفاصيل التقنية

| Parameter | Value |
|-----------|-------|
| Query name | `BizIntegrityQuery` |
| doc_id | `28596420510007620` (تغيّر؛ كان `25975613018777537`، دُوِّر في 2.26.38.10، وأُكّد في كتالوج persist-id في 2.26.41.6؛ client_doc_id `14769534217004148908396994706`) |
| Schema | `whatsapp-android-mex` |
| Transport | MEX HTTP/2 POST → `/mex/query` |
| JID format | `<shortNum>@lid` (e.g. `1910@lid`) |

### 3.2 الطلب

2.26.41.6 (found، `BizIntegritySignalsGraphQLFetcher.A00`): كائن الإدخال `input { query_input: [ {jid, privacy_token{tctoken, timestamp}?} ], telemetry{context:"INTERACTIVE"} }`، وفئة النتيجة `C48528LIw`. يُضاف `privacy_token` فقط عند تطابق بوابة (`MZ4.A00`) ووجود TC-token مخزَّن. الاستجابة (found، `C51015Mjl`): الجذر `xwa2_fetch_wa_users[]`، ولكل مستخدم `integrity_signals_info` يحوي `dhash` و`fb_linked_page_number_of_likes` و`ig_linked_age_number_of_followers` (sic، مفتاح حرفي) و`is_banned` و`is_suspicious` و`is_suspicious_start_chat` و`join_date_ms` (سلسلة، تُحلَّل إلى long) و`phone_country_code` و`trust_tier` (enum `M5B`) و`is_mv_subscribed` (يُخزَّن باسم `is_meta_verified`) و`meta_verified_info{mv_friction_eligibility}` و`integrity_tags[]{tag, pipeline_date_ms, dates_ms[]}` و`hide_safety_tools_for_business` و`fmx_business_holdout_group`. قائمة الحقول أدناه هي إعادة بناء 2.26.26.4 (inferred، لم يُعاد التحقق منها؛ شكل متغير الطلب `$userJids` يختلف عن شكل الإدخال في 2.26.41.6):

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

### 3.3 DTO الاستجابة — `BizIntegritySignals` (`C51530MtC`؛ كان C39833Hhl في 2.26.26.4)

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

### 3.4 IntegrityTags DTO

(`C51222Mno` قائمة من `C51359MqA`؛ التسلسل في `LwI`، الشكل لم يتغير)

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
| بعد إرسال رسالة | post-send hook |
| بدء التطبيق / تسجيل الدخول | background scheduler |

### 3.6 أعلام الميزات (Feature Flags)

| Flag ID | Function |
|---------|---------|
| 11061 | مشغّل اكتشاف الحساب المشبوه (`N5r.A03`؛ present؛ يُقيَّم فقط لجهات الاتصال التي يبدأ مستوى الاسم الموثّق لديها بـ `ent:`) |
| 11064 | أهلية إشارة الثقة عند بدء المحادثة (تشغيل/إيقاف) (`BizIntegritySignalsManager.A04`؛ present؛ الافتراضي false) |
| 11065 | مدة صلاحية ذاكرة إشارات الثقة بالثواني (`C51855N0t.A00`؛ الافتراضي 86400، found في `C08J`) |
| 12709 | أهلية جهات الاتصال التي يكون `hostStorage == 2` لنشاطها التجاري (`C197628ax.A06`)؛ الافتراضي false (present) |
| 16349 | مسار الاستعلام القسري في `BizIntegritySignalsManager.A04` (present؛ الافتراضي false) |
| 19793 | جديد في هذا الجدول: `N5r.A02`، يتحكم في إعادة استخدام الإشارات المخزنة في `C51855N0t.A02`؛ الغرض inferred من الاستخدام؛ الافتراضي false |
| 12840 | إعداد JSON مفتاحه نوع المخالفة، الافتراضي `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}` (`C08J`)؛ لم يُحدَّد المستهلك؛ الغرض inferred من أسماء المفاتيح (`max_dismiss_count`، `max_display_days`) ومن سلاسل الأنواع التي يستخدمها شريط SMB soft-enforcement (7.4) |
| 19893 | تسجيل رسالة النظام لبطاقة FMX (present، `C198788cr`) |
| 26697 | BizIntegrity v2 (present، `C34735F5e`) |
| 27269 | فصل عدّ الرسائل الواردة/الصادرة (present) |
| 34166 | كاتب start_chat_trust_signals (present، `ContactInfoActivity`) |

ذاكرة مؤقتة داخل الذاكرة في `BizIntegritySignalsManager.A02`: الإدخالات صالحة لمدة 60000 ms (found).

---

## 4. وسم الحساب كمشبوه — متى ولماذا وكيف والوقاية (أُعيد فحصه في 2.26.41.6؛ ما تعذّر تحديد موضعه موسوم في مكانه)

> **النتيجة الأساسية:** بالنسبة لأعلام BizIntegrity (`is_suspicious`، `trust_tier`، `is_banned`) لا يحسب العميل شيئًا: تُحلَّل من استجابة GraphQL (`C51015Mjl`) وتُعرض فقط. لم يُعثر على أي عتبة أو تسجيل نقاط على جهة العميل لها. بشكل منفصل، يُنتج نموذج على الجهاز أحكام احتيال محلية (`odml_scam_alert_*`، 6.6، 7.6). يحمل طلب BizIntegrity فقط الـ JIDs المستعلَم عنها، ورمز خصوصية اختياريًا، وسياق telemetry (3.2)؛ أما رفع العميل لمقاييسه المحلية إلى جهة أخرى فلم يُعثر عليه (not found).

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

لا يوجد في العميل سهم من المقاييس المحلية إلى طلب BizIntegrity (3.2). أي إشارات على جانب الخادم تُنتج الحكم غير ظاهر من APK (تعلّم آلي على الخادم: inferred). ليس لدى العميل **أي عتبة محلية** من نوع "أكثر من X رسالة -> مشبوه" لأعلام BizIntegrity.

---

### 4.2 تسلسل مستويات الثقة (يعيّنها الخادم)

موجود في APK الخاص بـ WhatsApp كـ enum مُترجَم (`M5B` في 2.26.41.6؛ القيم لم تتغير):

| Tier | Meaning | Effect |
|------|---------|--------|
| `SUSPICIOUS` | أعلى خطورة — موسوم بنشاط | جميع التحذيرات فعّالة، احتكاك في الواجهة، احتمال حظر الإرسال |
| `TIER_0` | أدنى مستوى مشروع (حسابات جديدة) | أهلية احتكاك مرتفعة |
| `TIER_1` | مستخدم عادي | عادي |
| `TIER_2` | ثقة مرتفعة | احتكاك أقل |
| `TIER_3` | أعلى ثقة مشروعة | احتكاك أدنى |
| `UNTIERED` | لا تقييم | لا يُطبَّق فحص |
| `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` | غير معروف | قيمة بديلة |

**فحص على مستوى الشيفرة** (`BizIntegritySignalsManager`):
```java
"SUSPICIOUS".equals(trustTier)  // → triggers UI flow
```

### 4.3 الإشارات المحيطة بالحكم

لا يُرفق العميل نقاط البيانات أدناه بطلب BizIntegrity (3.2). يسرد الجدول موضع ظهور كل منها في العميل؛ أما تقييم الخادم لها فهو inferred. عمود "Risk weight" من التقرير السابق لا يستند إلى دليل على جهة العميل وقد حُذف.

| Signal | Where it appears in the client (2.26.41.6) | Role |
|--------|---------------------------------------------|------|
| `isCountryMismatch` | ميزة على الجهاز (`integrityai.impl.InputFeatureProviderImpl`، العلم 31535) | مُدخل للنموذج على الجهاز، وليس للطلب |
| `mostRecentSenderScore` | ميزة على الجهاز (العلم 31536) | نفسه |
| `dhash` | حقل في الاستجابة، يُخزَّن كما هو | سلسلة معتمة يوفرها الخادم؛ لا شيفرة في العميل تركّبها (المعنى unknown؛ قراءة التقرير السابق "بصمة الجهاز" هي inferred) |
| `join_date_ms`, `phone_country_code` | حقول في الاستجابة | تُخزَّن؛ لا عتبة في العميل |
| FB/IG counts | حقول في الاستجابة (`fb_linked_page_number_of_likes`، `ig_linked_age_number_of_followers`) | تُعرض على بطاقة FMX (7.5) |
| `integrity_tags` | حقل في الاستجابة `{tag, pipeline_date_ms, dates_ms[]}` | يُخزَّن كـ JSON؛ قيم الوسوم معتمة بالنسبة للعميل |
| Privacy token | حقل في الطلب `privacy_token{tctoken, timestamp}` | اختياري، فقط عند تطابق البوابة `MZ4.A00` ووجود TC-token مخزَّن |
| Message volume | عدّ محلي (`N54`، 6.2) | الرفع إلى الخادم لم يُعثر عليه |
| Broadcast limit | العلم 20278 الافتراضي `{"max_messages": 10000, "farthest_time_days": 30}` | المستهلك لم يُحدَّد (6.3) |

`isCountryMismatch` و`mostRecentSenderScore` هما الميزتان الملموستان الوحيدتان للتعلم الآلي المعثور عليهما في العميل (`com.whatsapp.integrityai.impl.InputFeatureProviderImpl`، 2.26.41.6). العلم 31535 يزوّد isCountryMismatch، و31536 يزوّد mostRecentSenderScore (found).

---

### 4.4 متى يُشغَّل فحص GraphQL؟

**بوابة الأهلية** (found، `BizIntegritySignalsManager.A04`؛ الـ JID المستعلَم عنه هو الطرف المقابل في المحادثة):
1. العلم **11064** مفعّل (الافتراضي false)
2. الـ JID ليس من النوعين المستثنيين (`AbstractC24760wu.A03/A04`: JIDs البوتات و JID ثابت لرقم هاتف)
3. أحد الشروط: جهة الاتصال نشاط تجاري SMB (`N5r.A06`، مستوى الاسم الموثّق يبدأ بـ `smb:`)، أو العلم **12709** مفعّل و`hostStorage == 2` للنشاط التجاري لجهة الاتصال (`C197628ax.A06`)، أو (استدعاء قسري، `A09`) العلم **16349** مفعّل و`N5r.A04/A06` محقق (`A04` = `!A01 && !SMB && !ENT`؛ دلالات الدالة المساعدة `N5r.A01` لم تُحل، فأي JIDs غير تجارية تقبلها يبقى مفتوحًا)
4. للمسار غير القسري: الذاكرة المؤقتة منتهية أو لا توجد ذاكرة محلية (`C51855N0t`)

تصحيح مقابل التقرير السابق: في 2.26.41.6 لا تتخطى البوابة العادية الحسابات التجارية، بل تختارها (SMB أو المستضافة)؛ والمسار القسري (16349) قد يقبل JIDs أخرى. تدفق JADX لـ `A04` أُعيدت هيكلته جزئيًا، فهذه القراءة مستمدة من الشكل المفكَّك وأجسام الدوال المساعدة، وليس من smali.

**TTL للذاكرة المؤقتة:** العلم **11065** بالثواني، الافتراضي **86400 (24 ساعة)** (found، `C08J`)
```java
long timeout_ms = TimeUnit.SECONDS.toMillis(remoteConfigValue(11065));
if (current_time - lastSyncTs > timeout_ms) {   // C51855N0t.A00
    // cache expired -> new GraphQL call required
}
```

**حجم الدفعة:** لا يوجد تقسيم إلى 975 JID في مسار جلب GraphQL (`BizIntegritySignalsManager.A03` يمرر قائمة الـ JIDs كما هي). الثابت 975 يخص تجميع عدّ الرسائل المحلي عبر SQL (6.2).

---

### 4.5 قيم integrity_tag المعروفة

السلسلتان `automation_bulk_messaging` و`spam` موجودتان (found) في `C35896FgX` و`ViewOnClickListenerC39711HTl`، لكنهما تُقارَنان هناك مع `type` إشعار SMB soft-enforcement (`HAR.A07`، انظر 7.4)، وليس مع `integrity_tags` من استجابة BizIntegrity. وتظهران أيضًا كمفتاح القيمة الافتراضية للعلم 12840. لا يعدّد العميل قيم `integrity_tags` إطلاقًا؛ تُخزَّن كتل JSON معتمة. السلسلة `business_policy_violation` غير موجودة في أي مكان ضمن java_src أو smali أو assets أو res في 2.26.41.6.

| Tag | Meaning |
|-----|---------|
| `automation_bulk_messaging` | نوع إشعار soft-enforcement (الإرسال الجماعي/الآلي)؛ لم يثبت أنه قيمة في `integrity_tags` |
| `spam` | نوع إشعار soft-enforcement (سبام) |

---

### 4.6 ما الذي يؤدي فعليًا إلى وسم "مشبوه" — inferred من الشيفرة

أُعيد فحصه في 2.26.41.6: لا يحتوي العميل على أي منطق أو عتبة أو وزن لأي صف أدناه، ولا يحمل طلب BizIntegrity أيًا من هذه المقاييس (3.2). يبقى الجدول كله **inferred** (تخمين لسلوك الخادم انطلاقًا من الإشارات الموجودة في العميل). صف "New account (< 24h)" بلا سند: لا يوجد فحص لعمر الحساب في العميل (انظر 4.9 D).

| Behavior | Why it's risky | Weight |
|----------|---------------|--------|
| صادر مرتفع مقابل وارد (إرسال فقط دون ردود) | نمط تواصل جماعي | مرتفع جدًا |
| بلد الهاتف ≠ بلد IP | `isCountryMismatch = 1.0` | مرتفع جدًا |
| dhash نفسه على عدة حسابات | مشغّل حظر الجهاز | مرتفع جدًا |
| بث > 10,000 مستلم / 30 يومًا | حد صارم، وسم فوري | مرتفع |
| `mostRecentSenderScore` مرتفع (إبلاغ المستلمين) | حلقة تغذية راجعة للتعلم الآلي | مرتفع |
| حساب جديد (< 24h، بلا جهات اتصال) | مصداقية منخفضة (لم يُعثر على فحص عمر في العميل) | مرتفع |
| لا ربط FB/IG + معدل صادر مرتفع | غياب الإثبات الاجتماعي | متوسط |
| integrity_tags موجودة | أثر مخالفة سابقة | متوسط–مرتفع |
| `is_reach_out = 1` + بدء محادثات كثيرة مع غير معروفين | نمط تواصل بارد | متوسط |

### 4.7 رموز أسباب SpamWarning (تحذير ما قبل الحظر)

دون تغيير في 2.26.41.6 (`SpamWarningActivity`: السبب الافتراضي 100، الانتهاء الافتراضي -1؛ switch على 101 و102 و103 و104 و106، والافتراضي يغطي 105/غيره).

تُسلَّم عبر intent extra `spam_warning_reason_key`، وتُعيَّن من السمة `code` (>= 100) في `<failure reason="402">` الخاص بتسجيل الدخول في XMPP مع `expire` و`message` و`url` (found، `C0ZH.handleMessage` النوع 2؛ انظر 8.1):

| Code | Trigger | Countdown? |
|------|---------|-----------|
| 101 | اكتشاف نشاط سبام | نعم |
| 102 | مخالفة إعادة التوجيه | نعم |
| 103 | سبام الحالة (Status) | نعم |
| 104 | إعادة توجيه البوتات | نعم |
| 105 | عام / افتراضي | دائم إذا expiry = -1 |
| 106 | مخالفة أخرى | نعم |
| default | مخالفة غير معروفة | دائم إذا expiry = -1، وإلا عدّ تنازلي |

`expiry_in_seconds == -1` + متصل: إنهاء فوري (رفع الخادم التحذير).

### 4.8 فئات SpamFlow المتعلقة بالوسم كمشبوه

97 فئة في APK (found: `C9E2`، مصفوفة من 96 إدخالًا مع إلحاق `1_1_spam_banner_report` أخيرًا، الفهارس من 0 إلى 96؛ العدد السابق 92 والفهارس في الجدول حلّت محلها هذه). تُسلسل القائمة بالاسم داخل عقدة SMAX `spam_list` (السمة `spam_flow` لكل إدخال، و`wi_trace_id` اختياري من 24 محرفًا)، فالفهرس مجرد موضع في مصفوفة العميل وليس قيمة على السلك. جديد: `odml_scam_alert_blocked_composer_block`، `odml_scam_alert_suspicious_banner_block/_trust`، `odml_scam_alert_fmx_card_block/_trust`، `biz_spam_banner_block`، `1_1_spam_banner_block`، `chat_fmx_card_block`، `group_spam_banner_report`، `left_group_spam_banner_report`. المرتبطة مباشرة بحالة "مشبوه":

| Index | Category | Meaning |
|-------|----------|---------|
| 23 | `chat_fmx_card_block_server_flagged_suspicious` | وسمه الخادم كمشبوه → حظر FMX |
| 24 | `chat_fmx_card_block_suspicious` | حُظرت المحادثة بسبب علم "مشبوه" |
| 27 | `chat_fmx_card_safety_tools_block_suspicious` | أدوات السلامة تُعرض للمشبوه |
| 70 | `odml_scam_alert_bottom_sheet_block` | احتيال بالتعلم الآلي على الجهاز → حظر |
| 71 | `odml_scam_alert_bottom_sheet_trust` | احتيال بالتعلم الآلي على الجهاز → ثقة |
| 76 | `one_to_one_spam_banner_block_server_flagged_suspicious` | شريط سبام 1:1 (وسمه الخادم) |
| 85 | `trust_question_bottomsheet_block_server_flagged_suspicious` | سؤال الثقة (وسمه الخادم) |
| 89 | `user_initiated_chat_suspicious_banner_block` | شريط "مشبوه" عند بدء المحادثة |
| 94 | `1_1_old_spam_banner_block` | شريط سبام قديم |
| 96 | `1_1_spam_banner_report` | بلاغ سبام 1:1 |

### 4.9 آليات الحماية — ما يعرضه العميل

قائمة "عوامل الحماية" السابقة قراءة لتعلم آلي على الخادم بلا سند على جهة العميل. ما يحتويه 2.26.41.6 فعليًا:

#### A) Business status
ليس تخطيًا. بوابة الأهلية العادية تختار جهات اتصال SMB (وجهات `hostStorage == 2` تحت العلم 12709)، انظر 4.4. العلم 2923 (سابقًا: "non-business validation toggle") لم يُحدَّد موضعه: لا يوجد فحص علم بهذا المعرّف ولا قيمة افتراضية له في java_src أو smali في 2.26.41.6.

#### B) Meta Verified (mvFrictionEligibility)
حقل الاستجابة `meta_verified_info.mv_friction_eligibility` (found، `C51015Mjl`)، يُخزَّن باسم `mv_friction_eligibility`. و`is_mv_subscribed` يُخزَّن منفصلًا باسم `is_meta_verified`. تقرأ بطاقة FMX (`C94p`) العلم، ومع تفعيل العلم 15735 تضيف رابط "learn more". أما أن ذلك يخفض عتبات الاحتكاك فغير ظاهر في العميل (inferred).

#### C) Linked social accounts (FB/IG)
`fb_linked_page_number_of_likes` و`ig_linked_age_number_of_followers` تُحلَّل كأعداد صحيحة (`optInt`) وتُعرض على بطاقة FMX (7.5). هي أعداد وليست قيمًا منطقية (found). أن الخادم يعدّها عامل حماية هو inferred.

#### D) Account age grace period
غير موجود (not found). المقارنة الوحيدة الشبيهة بالعمر هي TTL الذاكرة المؤقتة على `last_sync_ts` مقابل العلم 11065 (4.4). `join_date_ms` يُخزَّن لكن لا يوجد منطق نافذة سماح في العميل.

#### E) Whitelist / validation list (flag 12709)
تغيّر: الفحص `C197628ax.A06(userJid)` هو `hostStorage == 2` في سجل الاسم الموثّق لجهة الاتصال (`AnonymousClass119`)، وهي خاصية محلية وليست قائمة موافقة مسبقة على الخادم. يجعل جهة الاتصال مؤهلة للاستعلام؛ ولا يعود مبكرًا.

#### F) hideSafetyToolsForBusiness (field from response)
حقل الاستجابة `hide_safety_tools_for_business`، يُخزَّن في `hide_safety_tools_for_business`. أثره على الواجهة لم يُتتبَّع مجددًا؛ والقول السابق بأنه يخفي واجهة التحذير فقط دون تغيير حالة "مشبوه" غير موثّق.

---

### 4.10 الوقاية — ما تكشفه الشيفرة

هذا الجزء نصائح مشتقة من الحقول أعلاه. لا يوجد منطق في العميل يؤكد أيًا منها؛ عامِل كل بند على أنه **inferred**، إلا حيث وُسم found.

**سلوكي (inferred):**
- حافظ على توازن نسبة الصادر/الوارد
- تجنب عدم تطابق البلد بين الرقم والشبكة (يغذّي العميل النموذج على الجهاز بـ `isCountryMismatch`، found؛ استخدام الخادم inferred)
- ابقَ تحت إعداد البث للعلم 20278 (10,000 رسالة / 30 يومًا؛ المستهلك لم يُحدَّد)

**جودة الحساب (inferred):**
- أعداد FB/IG المرتبطة وMeta Verified يعرضها العميل أو يخزنها (found)؛ أثرها على الحكم inferred
- نافذة الحساب الجديد (24h) ووضع dhash في قائمة سوداء لا يسندهما أي كود في العميل (انظر 4.9 D و4.3)

**تقني (found):**
- يُضاف `privacy_token` (TC-token) إلى طلب BizIntegrity فقط عند تطابق البوابة `MZ4.A00` ووجود TC-token مخزَّن

**التوقيت (found):**
- تُعاد استخدام الإشارات المخزنة حتى يصبح `last_sync_ts` أقدم من العلم 11065 (الافتراضي 86400 s)؛ ويحتفظ المدير بإدخال ذاكرة إضافي مدته 60000 ms
- تبقى الإشارات في `wa_biz_integrity_signals` حتى تُستبدل باستجابة جديدة

---

## 5. قواعد بيانات SQLite المحلية

### 5.1 `wa.db` — `wa_biz_integrity_signals`

2.26.41.6 (found، `C53116Nmn`، 17 عمودًا بما فيها `_id`): يضيف `is_meta_verified` و`fmx_business_holdout_group`؛ و`fb_linked_page_number_of_likes` و`ig_linked_page_number_of_followers` و`join_date_ms` و`last_sync_ts` من نوع REAL، و`mv_friction_eligibility` و`is_meta_verified` بلا قيمة افتراضية معلنة. فهارس فريدة `biz_integrity_signals_jid_index` و`biz_integrity_signals_chat_row_id_index`؛ ومشغّل `contact_bd_for_business_integrity_signals` (BEFORE DELETE ON wa_contacts). المخزن: `LwI` (التسميات `QUERY_BIZ_INTEGRITY_SIGNALS_BY_JID` / `_BY_ROW_ID`، `BizIntegritySignalsStore/saveBusinessIntegritySignals`). المخطط أدناه هو نسخة 2.26.26.4.

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

الكاتب/القارئ: `LwI` (المخزن)، و`BizIntegritySignalsManager.A06(UserJid)` يقرأ `ConcurrentHashMap` في الذاكرة (found: `A06` يقرأ الخريطة في الذاكرة، و`A07` يقرؤها مع تحميل كسول من قاعدة البيانات، و`A0A` يُحدِّث/يُدرج ويحفظ؛ الاسمان `A08`/`A01` من 2.26.26.4 اختفيا)

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

القارئ: `C57342Yp` (`SELECT * ... QUERY_START_CHAT_TRUST_SIGNALS_BY_JID`؛ كان C2M7.A0K) → يعيد الصف `(is_sender_new_account, is_sender_suspicious)`

### 5.3 `msgstore.db` — `integrity_chat_info`

```sql
CREATE TABLE integrity_chat_info (
  chat_row_id                        LONG PRIMARY KEY,
  is_reach_out                       INTEGER,  -- 1 = unknown contact initiated
  is_eligible_for_link_friction_banner INTEGER
);
```

تسمية الاستعلام: `"GET_INTEGRITY_CHAT_INFO"` (استعلام دفعي بـ `chat_row_id IN (...)`)، المخزن `C33O`، المخطط `C08970Ox` (الفهرس `integrity_chat_info_chat_row_id_index`، المشغّل `chat_bd_for_integrity_chat_info_trigger` BEFORE DELETE ON chat). دون تغيير.

### 5.4 `wa.db` — `wa_biz_integrity_chat_settings`

found في 2.26.41.6: المخطط `AHY` (الأعمدة `jid` و`last_delivered_sort_id` LONG و`last_read_sort_id` LONG)، فهرس فريد `biz_integrity_chat_settings_index` على `jid`، والمشغّل `contact_bd_for_biz_integrity_chat_settings` (BEFORE DELETE ON wa_contacts). الدور unknown.

---

## 6. جمع إشارات السبام (جهة العميل)

(أُعيد فحصه في 2.26.41.6؛ ما تعذّر تحديد موضعه موسوم في مكانه.)

### 6.1 dhash

`dhash` سلسلة في استجابة BizIntegrity (`integrity_signals_info.dhash`)، تُخزَّن نصًا صريحًا في `wa_biz_integrity_signals.dhash`. لا شيفرة في العميل تركّبها: لم يُعثر على مُدخل من طراز الجهاز أو نظام التشغيل أو إصدار التطبيق أو الرقم أو المنطقة الزمنية أو Android ID أو بصمة البناء، ولا شيء يرفع واحدًا منها. وصف "بصمة الجهاز / قائمة سوداء على الخادم" السابق غير مسنود؛ المعنى unknown. سلاسل `dhash` الأخرى في APK (قائمة الحظر، إلغاء اشتراك الأعمال) هي تجزئات دليل لا علاقة لها.

---

### 6.2 معدل الرسائل

Found: `com.whatsapp.bizintegrity.logger.receiver.handler` (`C0236xdea74a22`، المساعد `N54`) يعدّ الرسائل محليًا خلال فترة زمنية لقائمة JIDs، بأسماء SQL مستعارة:
- `incoming_count`: الرسائل ذات `from_me = 0`
- `incoming_threads_count`: قيم `chat_row_id` الفريدة للرسائل المستلمة
- `outgoing_count`: الرسائل ذات `from_me = 1`
- `outgoing_threads_count`: قيم `chat_row_id` الفريدة للرسائل المرسلة
- عدد الرسائل المحذوفة: `messages_count_after_privacy_token` (وأيضًا `messages_count` و`outgoing_messages_count`) من `integrity_deleted_chat_message_count`

العلم 27269 يتحكم في ما إذا كان الوارد/الصادر يُعدّان منفصلين أو كإجمالي موحد (found في المعالج نفسه).
حجم الدفعة: **975 JID** لكل استدعاء معالجة SQL (found: `C20H.A1A(list, 975)`، تقسيم بحسب حد متغيرات SQLite، وليس دفعة شبكية).
لم يُحدَّد: التجميع اليومي/الساعي، المعدل لكل جهة اتصال؛ وإلى أين تذهب الأعداد بعد العدّ لم يُتتبَّع.

---

### 6.3 حدود البث (حسابات الأعمال)

إعداد الميزة 20278: `{"max_messages": 10000, "farthest_time_days": 30}` (found كقيمة افتراضية في `C08J`/`C09W`).
- حد 10,000 رسالة لكل 30 يومًا هو القيمة الافتراضية للإعداد؛ أما مستهلك هذا JSON (الشيفرة التي تفرضه قبل الإرسال، و`renewal_date`، والتقييد لكل مستلم، وتصنيف تسويقي مقابل عادي) فلم يُحدَّد: سلسلتا المفتاحين `max_messages`/`farthest_time_days` ترِدان فقط في جداول القيم الافتراضية، و`renewal_date` لا ترد في java_src.

---

### 6.4 تطبيق GAP (Global Abuse Prevention)

Found: `com.whatsapp.gapenforcement.triggers.GapEnforcementTrigger.A03` (`onMarketingMessageReceived`) يُتخطى عند إيقاف علم الميزة 14837، ويخزّن `LAST_MARKETING_MESSAGE_TIMESTAMP` في SharedPreferences (`C67902uK`) عند وصول رسالة تسويقية أحدث. العلم 25631 يتحكم في مسار مشغّل آخر. التوسعة "Global Abuse Prevention" غير موجودة في الشيفرة (تسمية غير موثّقة).

الحالة المتتبَّعة (`ChatDescription`، found):
- `isEnterpriseBusiness` (Boolean)
- `isMarketingMessageThread` (Boolean)
- `sortTimestamp` (Long)
- `chatJid` (UserJid)

---

### 6.5 WaFA (Federated Analytics)

Found: الحزمة `com.whatsapp.federatedanalytics.impl` (`WaFaConfigFetcher`، `WaFaReportScheduler`، `FaReportRunner`، `WaFaReportSubmitter`، `FaTeeConnection`، `FaTeeAcsRepository`، `FaAcsWarmer`). تمر التقارير عبر اتصال TEE موثَّق بـ ACS (ترويسات `x-acs-token` و`x-acs-configid` و`x-acs-project-name`؛ جلب مفتاح OHAI العام). وقت التشغيل التالي في التفضيل `fa_next_report_run_timestamp`.
لم يُحدَّد: محتوى التقارير. قائمة المقاييس في التقرير السابق (تبنّي الميزات، الأعطال، زمن الاستجابة، RAM/التخزين/OS، geofencing، بيانات الجلسة، نوع الاتصال) لم يُعثر عليها كشيفرة؛ المحتوى يقوده الإعداد، فلا يمكن قراءته من العميل.

---

### 6.6 استخراج ميزات التعلم الآلي (كشف الاحتيال على الجهاز)

ميزتان ملموستان معثور عليهما في العميل المفكَّك:
- `isCountryMismatch` (float 0.0/1.0): بلد المرسل ≠ بلد المستلم → **خطورة عالية**
- `mostRecentSenderScore` (float): درجة سمعة المرسل بالتعلم الآلي

العلمان 31535/31536 يتحكمان بقيمهما (found). النتائج تُرسل إلى الخادم لتسجيل ثانوي بالتعلم الآلي (inferred).

---

## 7. مكونات الواجهة: المشبوه والتحذيرات والحظر

(أُعيد فحصه في 2.26.41.6: `SpamWarningActivity` أصبحت `com.whatsapp.userban.spamwarning`، و`SuspiciousFmxBottomSheetFragment` في `com.whatsapp.fmx` مع فئة فرعية جديدة `SuspiciousSmbFmxBottomSheetFragment`. شروط التشغيل في 7.2 و7.4 و7.5 مصحَّحة أدناه.)

### 7.1 SpamWarningActivity

معاملات Intent:
- `spam_warning_reason_key` (int): رمز السبب
- `expiry_in_seconds`: العدّ التنازلي (-1 = دائم)
- `spam_warning_message_key`: نص مخصص
- `faq_url_key`: رابط الأسئلة الشائعة

رموز الأسباب:

| Code | Meaning |
|------|---------|
| 100 | تحذير سبام عام |
| 101 | اكتشاف نشاط سبام |
| 102 | مخالفة إعادة التوجيه |
| 103 | سبام الحالة (Status) |
| 104 | إعادة توجيه البوتات |
| 105 | عام / دائم |
| 106 | مخالفات أخرى |

إذا كان `expiry_in_seconds != -1` → يظهر مؤقت العدّ التنازلي.
إذا كان `-1` + متصل → إنهاء فوري (رفع الخادم التحذير).

### 7.2 الورقة السفلية Suspicious FMX (`SuspiciousFmxBottomSheetFragment`)

Found: ورقة معلومات (روابط "learn more" `about-blocking-reporting` و`examples-of-scams`)، وليست مانعًا مدفوعًا بالحالة. تُفتح بالضغط على زر حالة "مشبوه" في بطاقة FMX (`C93z.setupSuspiciousButtons`، ونسخة SMB `C94p` تفتح `SuspiciousSmbFmxBottomSheetFragment`) ومن `C512928n` (نسخة SMB عندما تكون جهة الاتصال نشاطًا تجاريًا، `A0T()`)، عبر الدالتين المساعدتين `AbstractC61092ir.A00` / `AbstractC61102is.A00`.

شروط التشغيل الأربعة في التقرير السابق (`is_suspicious == 1` و`is_suspicious_start_chat == 1` و`is_reach_out == 1` و`chat_fmx_card_block_suspicious == 1` كحظر إرسال) غير مسنودة: الفئة نفسها لا تقرأ أيًا منها، و`chat_fmx_card_block_suspicious` اسم فئة SpamFlow (4.8) وليس علمًا مخزنًا. المعثور عليه: يُعرض سياق بدء المحادثة عندما يكون `is_suspicious_start_chat` صحيحًا (`StartChatContextUtils`)، وتحسب بطاقة FMX `"SUSPICIOUS".equals(trust_tier)` (`C94p`).

---

### 7.3 واجهة الحظر الصارم WFAC

| Class | Function |
|-------|---------|
| `WfacBanActivity` | نقطة الدخول، معلومات الحظر + زر الاستئناف |
| `WfacBanInfoFragment` | تفاصيل المخالفة + رابط الاستئناف |
| `WfacBanDecisionFragment` | إجراء المستخدم (تقديم الاستئناف) |
| `WfacUnbanDecisionFragment` | تأكيد ما بعد الاستئناف |

المشغّل (تغيّر): `Main.A5D()` اختفت؛ ومعادلها `Main.A5W()` الذي يقرأ `wfac_ban_state` عند البدء (switch على "UNBANNED" / "BANNED" / "CHECKPOINTED"، حالة التسجيل 21، السجل "main/me/wfac ban") ويبدأ `WfacBanActivity` عبر `HBC`. لم يُعثر على مستمع لتغيّر SharedPreferences. تُكتب `wfac_ban_state` بواسطة معالج جلب حالة الحظر وبواسطة `WfacBanActivity.onCreate` (2.3). مسار فشل تسجيل الدخول (403) يفتح `com.whatsapp.userban.ui.BanAppealActivity` (`HBB`) الأقدم بدلًا من ذلك. 2.26.41.6: الفئات الآن في `com.whatsapp.waffle.wfac.ui` (وكذلك `WfacBanBaseFragment`)؛ تُفتح الواجهة عبر المساعد `HBC` للـ intent والانتقال بين الشاشات `I1T` (`transitionToScreen`).

### 7.4 SMB Soft Enforcement

تغيّر: المشغّل ليس `is_suspicious=true` + احتواء `integrity_tags` على `"business_policy_violation"` (هذه السلسلة غير موجودة في 2.26.41.6). بل هو إشعار أعمال XMPP (المعالج `AnonymousClass142`، معرّف الإشعار 202) بالابن `biz_integrity_warning_notification > violation`:

| Attribute | Use |
|-----------|-----|
| `source` | مصدر المخالفة (مطلوب) |
| `type` | نوع المخالفة، مثل `automation_bulk_messaging` و`spam` (يُقارن في `C35896FgX`) |
| `severity` | مثل `"severe"` يغيّر نص الشريط (`C35896FgX`، `WABIEnforcementEducationFragment`) |
| `policy_url` | هدف الرابط (مطلوب) |
| `priority` | int >= 0 (مطلوب) |
| `status` | `active` (يُخزَّن، تُصفَّر العدادات) أو `inactive` (يُزال) |

يبني العميل `SMBSoftEnforcementNotification` (`HAR`) مع `notificationType` ثابت `"warning"` و`bannerNotificationTimeStamp` = وقت الاستلام، ويحفظ مصفوفة JSON تحت التفضيل `smb_soft_enforcement_banner-all-json-<notificationType>` (`C35894FgV`) بالمفاتيح أدناه. العدادات لكل إشعار هي تفضيلات int: `smb_soft_enforcement_banner-<notificationType>-<source>-<severity>-<type>-total_days|click_count|dismiss_count`.

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

JSON التقرير السابق (`notification_type: soft_enforcement` و`violation_type` و`education_url` و`action_required`) غير موجود في العميل. الواجهة: `SMBSoftEnforcementEducationFragment` و`WABIEnforcementEducationFragment` في `com.whatsapp.banner.softenforcementsmb`.

---

### 7.5 بطاقة FMX (بطاقة إشارة الثقة)

Found: تُنشأ رسالة نظام من النوع 129 (`0x81`، `C57172Xr`) في `C198788cr` ("Creating FMX card system message for chat"، "ContactsProcessor/added contact info message")؛ العلم 19893 يتحكم فقط بحدث تحليلات هناك. الكتابة غير المتزامنة إلى `start_chat_trust_signals` تتحكم بها `C1P2.A01()` (العلم غير محلول) وتجري عبر `C65972r0`. تعرض البطاقة (`C94p`) أعداد إعجابات FB ومتابعي IG وعلم احتكاك Meta Verified؛ و`"SUSPICIOUS".equals(trust_tier)` يختار النسخة المشبوهة. عرض عمر الحساب وشرط عرض "نشاط تجاري/جهة اتصال غير معروفة" لم يُحدَّدا.

---

### 7.6 ODML Scam Alert (تعلم آلي على الجهاز)

نموذج تعلم آلي قابل للتنزيل عبر رمز ACS `"WA_ODML"` (found في `OdmlModelDownloadClient`، `ODML_MODEL_DOWNLOAD`، المعرّف `27301080136160169`، TTL 345600 s = 4 أيام؛ حجم الذاكرة المؤقتة 64 لم يُحدَّد). يمكن للمستخدم تبديله عبر `ScamDetectionSettingsActivity`. يُتتبَّع المسار عبر extras الـ intent: معرّف الجلسة / المصدر / نقطة الدخول.

---

## 8. XMPP و Stanzas (سياق الحظر)

(أُعيد فحصه في 2.26.41.6 بقراءة معالجات تسجيل الدخول وأخطاء stream؛ القسم 8.1 مصحَّح. فحص سابق في 2.26.35.2 لم يرَ دفعة حظر عبر XMPP؛ هذه الملاحظة حلّ محلها مسار فشل تسجيل الدخول أدناه.)

### 8.1 `<failure>` في تسجيل الدخول يحمل الحظر والتحذيرات

الادعاء السابق "الحظر يأتي فقط عبر MEX GraphQL" خاطئ بالنسبة للأحداث عند الاتصال. `HandlerThreadC12340b0.A13` يقرأ عقدة نتيجة تسجيل الدخول؛ وعند `<failure>` يأخذ `reason` (int) ويبني استثناء `C45351tB` (found):

| `reason` | Type | Attributes read | Client reaction (`C0ZH.handleMessage`) |
|----------|------|-----------------|-----------------------------------------|
| 5xx | 4 | - | خطأ خادم، مسار إعادة المحاولة |
| 402 | 2 (default) | `code`, `expire`, `message`, `url`, `appeal_token`, `age_collection` | `SpamWarningActivity` مع `spam_warning_reason_key` = `code` (>= 100) و`expiry_in_seconds` والنص ورابط الأسئلة الشائعة |
| 402 + `appeal_token` + `code` 106 | 13 | same | `ContextualAgeCollectionActivity` (extras `appealToken`، `expireTimeout`) |
| 402 + `appeal_token` + `code` 107 / `code` 109 | 14 / 15 | same | مسار "U13 Banned PAA Pending" (تفضيلات الحساب المُدار، onboarding) |
| 403 | 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` | حظر دائم: `HGB.startPermanentBanFlow` -> `BanAppealActivity` (بعد تأخير العلم 19714 بالمللي ثانية) |
| 405 | 3 | `t` (seconds) | يكتب التفضيل `software_forced_expiration` |
| 406 | 5 | `code` | التفضيل `underage_account_banned` |
| 416 | 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` | `WfacManager.startUnderageBanFlow`؛ و`violation_reason == "u13_checkpoint"` يعيّن `support_ban_appeal_user_banned_from_chat_disconnect` |
| other | 0 | - | تسجيل خروج (مسار "exception-password") |

تقرأ جميع أنواع الفشل أيضًا سمات اختيارية لواجهة تسجيل الخروج: `logout_message_header`، `logout_message_subtext`، `logout_message_locale`، `logout_main_button_text`، `logout_main_button_url`، `logout_secondary_button_text`، `logout_secondary_button_url`. تُقرأ `location` من العقدة للتوجيه.

`<stream:error>` (معترض القراءة المرافق، `C40601l6`): `code` 515 / 516، الابن `conflict type="device_removed"` (إلغاء تسجيل)، الابن `ack` (طرد). لم يُعثر على ابن خاص بالحظر. لم يُفحص `<presence type="unavailable">` ولا رموز إغلاق WebSocket.

### 8.2 رموز أخطاء XMPP (القاموس الثنائي)

القاموس `AbstractC40911lb` (بايت واحد `A00`، بايتان `A01`). وجود رموز الجدول السابق:

| Token string | In dictionary |
|-------------|---------------|
| `stream:error` | yes |
| `conflict` | yes |
| `not-authorized` | yes |
| `item-not-found` | yes |
| `server-error` | yes |
| `401` | yes |
| `policy-violation` | not found |
| `403` | not found as a token (the `reason` value 403 is read as an int attribute) |

عمود "Meaning" في التقرير السابق (مثل `403` = "Forbidden (ban-related)") كان inferred؛ ومعنى 403 فقط مسنود الآن بمعالجة `<failure>` أعلاه. وفي القاموس أيضًا: `404` و`407` و`failure` و`locked`.

### 8.3 ردود IQ للحسابات المقيّدة

غير موجود (not found). لا فضاء الأسماء `urn:ietf:params:xml:ns:xmpp-stanzas` ولا النصان "Account restricted" / "User banned" موجودان في java_src أو الموارد في 2.26.41.6، ولا رمزا `forbidden` / `service-unavailable` في القاموس. أمثلة XML في التقرير السابق غير موثّقة ولا ينبغي الاعتماد عليها (قد تكون توضيحية). معالجة الأخطاء لكل IQ (مثل محللات `item-not-found` و`not-authorized` مثل `K3P` و`C23205A1e`) لم تُتتبَّع للحسابات المقيّدة.

---

## 9. تدفق البيانات الكامل (من البداية إلى النهاية)

(أُعيد فحصه في 2.26.41.6: doc_id `28596420510007620`، شكل الإدخال `query_input`، أسماء الفئات أعلاه. أسهم `isBanned` -> `wfac_ban_state` -> `Main.A5D()` في مخطط 2.26.26.4 أُزيلت لأنه لا يوجد رابط كهذا في الشيفرة؛ انظر القسمين 1 و2.3.)

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

Found في `C37414GLt`: يحمل JSON الخاص بـ `variables` في الطلب `user_request{client_ephemeral_pub_key_base64, ciphertext_base64, encryption_nonce_base64}` و`app_id` (`"dev.app.id"`)؛ النص الصريح قبل التشفير هو `{token, debug_info, description}`؛ وتسمية السياق `"WA_INAPP_BAN_APPEALS"` (info اشتقاق المفتاح). النقل (found، `AbstractC40195HfH`): طلب POST عادي إلى Facebook Graph على `https://<host>.facebook.com/graphql` مع `doc_id` وحقل `access_token`، وليس MEX. تمرر `C37414GLt` القيمة `doc_id` **38509456535312323** عندما تكون `hg3.A04.A00()` صحيحة، وإلا **5473316762755318**. اسم العملية `submitBanAppeal` لا يرد كسلسلة في java_src أو smali أو assets أو res في 2.26.41.6، وليس أي من القيمتين في كتالوج استعلامات المشروع، فالاسم غير موثّق. قبل الإرسال، يحلل `C40191HfD` استجابة أولى بـ `data.purpose_public_keys{purpose_public_ek, purpose_public_ik, purpose_public_ik_sig, purpose_dummy_ciphertext, purpose_dummy_nonce}` توفر مادة المفاتيح للتشفير.

---

## 11. التغييرات مقابل 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| BizIntegrityQuery doc_id | `25975613018777537` | `28596420510007620` (rotated 2.26.38.10) |
| Request shape | قائمة `$userJids` (معاد بناؤها) | `input{query_input[{jid, privacy_token{tctoken,timestamp}}], telemetry{context}}` |
| DTO class | `C39833Hhl` | `C51530MtC` (17 حقلًا: + `isMetaVerified`, `fmxBusinessHoldoutGroup`) |
| `wa_biz_integrity_signals` | 14 عمودًا | + `is_meta_verified`, `fmx_business_holdout_group`; الأعداد REAL |
| Store / manager | `BizIntegritySignalsManager.A08/A01` | المخزن `LwI`، المخطط `C53116Nmn`، المدير A02 ذاكرة مؤقتة 60 s في الذاكرة |
| start_chat_trust_signals reader | `C2M7.A0K` | `C57342Yp` |
| Trust tier enum | غير مسجَّل، 7 قيم | `M5B`، 7 قيم نفسها |
| WFAC UI package | `com.whatsapp.waffle.wfac` (flat) | `com.whatsapp.waffle.wfac.ui` (+ `WfacBanBaseFragment`) |
| WFAC prefs | 5 مفاتيح | + `wfac_last_ban_status_fetch_timestamp_ms` (تقييد التحديث 5 s)، و`support_ban_appeal_user_banned_from_chat_disconnect` يُمسح عند إعادة الضبط |
| Ban state parsing | 4 حالات | نفسها؛ `NO_APPEAL_OPENED` تُحوَّل إلى `CHECKPOINTED` |
| Flags | 11061/11064/11065/12709/16349/19893/26697/27269/34166 | كلها موجودة؛ + 19793 (N5r.A02) |
| SpamWarning codes 100-106 | نعم | دون تغيير |
| integrity_tags | `automation_bulk_messaging`, `spam` | دون تغيير |
| SpamFlow | 92 فئة | 97؛ أُضيفت `odml_scam_alert_*` و`biz_spam_banner_block` وغيرها |
| ML features | `isCountryMismatch`, `mostRecentSenderScore` (31535/31536) | دون تغيير، في `integrityai.impl.InputFeatureProviderImpl` |
| Broadcast limit 20278 | 10000 / 30 يومًا | دون تغيير |
| Ban/warning events at connect time | "no XMPP ban signalling" | XMPP login `<failure>`: reason 402 (SpamWarning / U13), 403 (perm ban -> `BanAppealActivity`), 405, 406, 416 (WFAC underage); `C45351tB`, `C0ZH` |
| `Main.A5D()` | يتفاعل مع تغيّر `wfac_ban_state` | اختفت؛ `Main.A5W()` يقرأ الحالة عند البدء (حالة التسجيل 21) ويفتح `WfacBanActivity` عبر `HBC` |
| `wfac_ban_state` writers | غير مسجَّلة | معالج جلب حالة الحظر `C40191HfD`؛ `WfacBanActivity.onCreate` (CHECKPOINTED / BANNED / UNBANNED بحسب مصدر الإطلاق)؛ لا رابط من `is_banned` |
| BizIntegrity eligibility | "الحسابات التجارية تتخطى الفحص" | يختار جهات SMB (مستوى `smb:`) أو `hostStorage == 2` (12709)؛ مسار قسري 16349؛ لا تقسيم 975-JID في الجلب |
| 975 batch | دفعة GraphQL | تقسيم محلي لعدّ الرسائل في SQL (`N54`) |
| Flag 12709 | قائمة بيضاء على الخادم | فحص محلي `hostStorage == 2` |
| Flag 2923, 24h account-age grace, `dhash` composition | مدَّعاة | غير موجودة في 2.26.41.6 |
| `integrity_tags` values | `automation_bulk_messaging`, `spam` | هذه السلاسل هي قيم `type` لإشعار SMB soft-enforcement، وليست قيم `integrity_tags` |
| SMB soft enforcement | وسم `business_policy_violation` + JSON `notification_type`/`education_url` | XMPP `biz_integrity_warning_notification > violation{source,type,severity,policy_url,priority,status}`؛ مفاتيح JSON المخزنة `source,type,severity,notificationType,policyUrl,status,bannerNotificationTimeStamp,priority`؛ العلم 12840 |
| SpamFlow indices/count | 92، مثلًا `odml_scam_alert_bottom_sheet_block` = 65 | 97 إدخالًا (`C9E2`)، الأسماء نفسها بفهارس مُزاحة (70, 71, 76, 85, 89, 94, 96) |
| `SuspiciousFmxBottomSheetFragment` | تُفتح بـ 4 شروط بيانات | ورقة معلومات تُفتح من أزرار بطاقة FMX / `C512928n` |
| Appeal request | عملية MEX `submitBanAppeal` | Graph `https://<host>.facebook.com/graphql` بـ doc_id 38509456535312323 / 5473316762755318، يسبقه جلب `purpose_public_keys`؛ اسم العملية غير موجود |
| `wa_biz_integrity_chat_settings` | لم يُحدَّد | موجود (`AHY`) |
| XMPP error tokens | رمزا `policy-violation` و`403` | ليسا في القاموس؛ `forbidden`/`service-unavailable` ونصوص 8.3 غائبة |

لا يزال مفتوحًا في 2.26.41.6: أسماء الفئات وراء `wfac_ban_violation_source` 0/1/2؛ مستهلك العلم 20278 والعلم 12840؛ دلالات الدالة المساعدة `N5r.A01`؛ محتوى تقارير WaFA؛ معالجة الأخطاء لكل IQ للحسابات المقيّدة (8.3)؛ عرض عمر الحساب على بطاقة FMX؛ العلم وراء `C1P2.A01()`.
