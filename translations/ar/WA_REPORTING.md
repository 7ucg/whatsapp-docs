<!-- src-sha1: 09dd00f496c4831ec33afbfd78f4db63a78bf014 -->
# WhatsApp الإبلاغ — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** إبلاغ عن مستخدم/جهة اتصال، مجموعة، قناة، حالة، مكالمة ورسالة — stanzas من نوع `spam` في SMAX، `spam_list`، أنواع البلاغ، نقاط دخول `spam_flow`، رموز الإبلاغ، رفع المحتوى، واجهة البلاغ/الحظر، الإبلاغ للمشرف، stanza الحظر وقوائم الأسباب، أخطاء الخادم، إشارات إساءة من جانب العميل، Baileys

---

## 1. ما هو الإبلاغ (تقنياً)

البلاغ عبارة عن IQ واحدة من نوع `set` إلى `s.whatsapp.net` في النطاق `spam`. تحمل عقدة `spam_list` (الكيان المُبلَّغ عنه، الرسائل المُبلَّغ عنها، نقطة الدخول، سياق اكتشاف الأعمال). يعيد العميل تسلسل الرسائل المُبلَّغ عنها كـprotobuf نص صِرف ويرفعها إلى جوار رمز إبلاغ والمفتاح الذي يحقِّقه. الحظر stanza منفصلة (`blocklist`). الإبلاغ للمشرف stanza ثالثة غير مرتبطة (`w:g2`).

كل العبارات تحليل ساكن للـAPK المفكَّك. المستوى: **found** = مقروء في الكود، **inferred** = مُستنتَج من الكود، **unknown** = غير محسوم. لا شيء هنا تم التقاطه على السلك.

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| باني IQ (متعدد الأغراض، `$t` يختار الشكل) | `C9EN` | يبني كل IQ للبلاغ (الأنواع 0، 18-23) وكثيراً من IQs غير مرتبطة |
| عقدة السبب/نقطة الدخول | `C9E2` | `spam_list` بـ`spam_flow`، `wi_trace_id`، `is_known_chat`، ... (`xmlns="spam"`) |
| عنصر فرعي إعداد المجموعة | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| غلاف المحتوى | `C31080DfY` | `raw`، `content_validation`، `reporting_token`، `reporting_token_key` |
| عناصر متنوعة | `C31084Dfc`، `C31085Dfd` | أعلام (`multicast`، `url_text`، ...)، `biz_opt_out`، `reporting` |
| المُسلسِل ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`، تجميع الرمز |
| مدير SMAX | `SpamRPCManager` | `A01`-`A06`، واحدة لكل نوع بلاغ (اسم الحزمة غير مُشوَّش) |
| المستودع | `SpamReportRepo` | التوجيه بحسب فئة JID، آثار محلية جانبية |
| أغلفة RPC | `IndividualSpamReportRpc`، `GroupSpamReportRpc`، `NewsletterSpamReportRpc`، `StatusSpamReportRpc`، `ChannelStatusSpamReportRpc`، `EventSpamReportRpc` | الحزمة `com.whatsapp.reportinfra.rpc` |
| قائمة سماح المصدر | `C9ZJ` | تُحقِّق نقطة الدخول (78 قيمة) |
| الواجهة | `ReportSpamDialogFragment` (+ `reportAsSpam$1`، `triggerExtraAction$2`، `ReportSpamDialogViewModel`) | حوار البلاغ، حظر/مغادرة اختياري |
| مُنفِّذ الحظر | `C227489sZ` → `C34631Yx` | IQ من نوع `blocklist` |
| الإبلاغ للمشرف | `RtaXmppClient` | قائمة بلاغات `w:g2` |
| مخزن الرمز | `C23070uA` | الجدولان `reporting_info`، `reporting_info_content` |

تختلف الأسماء حسب البناء؛ كل اسم مُشوَّش أعلاه حُلَّ في 2.26.41.6 من سلاسل ثابتة (`spam_list`، `spam_flow`، `reporting_token_key`، `GET_REPORTING_INFO_LIST`، `blocklist`).

**أُعيد التحقق في 2.26.45.10** (found): `com.whatsapp.reportinfra.rpc.*` (أغلفة RPC الستة) و
`com.whatsapp.reportinfra.repo.SpamReportRepo` غير مُغيَّرة — نفس الأصناف الستة، نفس توجيه فئة JID، نفس
استدعاءات `SpamRPCManager.A01`-`A06`، نفس سلاسل الخطأ/السجل (فحص smali فقط، لا jadx في هذا التمرير). هذا ليس
سطح بلاغ جديداً؛ إنه نفس الحزمة الموثَّقة أعلاه، فقط أُعيد تأكيدها. خطّاف قياس أداء WAM
(`wam_spam_report_perf`، القسم 11.3) ينتقل الآن بشكل ظاهر عبر مساعد مُسمّى `ReportSpamPerfMetric$Companion`
بطبقة أقرب إلى `SpamReportRepo` — نفس القياس عن بُعد، لا حقول جديدة.

---

## 2. أنواع البلاغ

### 2.1 التوجيه (found)

يتفرَّع `SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` بحسب فئة JID:

| JID المُبلَّغ عنه | صنف RPC | `SpamRPCManager` | باني `$t` | صنف الاستجابة | وسم السجل |
|--------------|-----------|------------------|--------------|----------------|-----------|
| جسم حالة مختار (`AbstractC31014DeU` غير فارغ) على JID نشرة | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| مستخدم (PN، LID، interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| مجموعة | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| جسم حالة مختار على أي JID آخر، أو JID حالة بقائمة رسائل | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| نشرة/قناة | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| معرّف فعالية (سلسلة) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| أي شيء آخر | لا شيء | لا شيء | لا شيء | لا شيء | يُطرَح `SpamReportRepo: unrecognized jid`، يُعاد كفشل |
| دردشة بوت | لا شيء (انظر 3.3) | لا شيء | لا شيء | لا شيء | `C214999If` |

أشكال `C9EN` الأخرى التي ليست بلاغات spam: `$t=0` بلاغ للمشرفين و`$t=1` تبديل إعداد المجموعة (القسم 9)، `$t=2` اقتراحات مجموعة فرعية، `$t=24/25/26` عناصر `status`. تُستدعى RPC الفعالية من لامبدات coroutine (`AYs`، `Aaa`)؛ الواجهة المصدِّرة غير معروفة (نقطتا دخول الفعالية `event_home_report` / `event_info_report` موجودتان، فبلاغات الفعالية مستنتجة).

### 2.2 بلاغات المكالمة بلاغات مستخدم (found)

تستدعي `SpamReportRepo.triggerReportCallNonSuspend` (مصدر `call_spam_dialog_report`) `IndividualSpamReportRpc.A00` دون `jid` مُبلَّغ عنه، دون رسائل، وعنصر مكالمة واحد. عنصر المكالمة (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` تشمل `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` وأخطاء برنامج ترميز فادحة. العلم **36386** يختار شكل JID الخاص في `to` (`CUC()` مقابل `Ask()`، LID مستنتَج مقابل PN). بلاغ مستخدم من الواجهة بـ`shouldIncludeCallLogsInReport` يضيف حتى 5 عناصر سجل مكالمة (`C16430i1.A0B(jid, 5)`).

---

## 3. تدفق العميل

### 3.1 الحوار

`ReportSpamDialogFragment` (حوار سفلي). معطيات Fragment (found): `flow` (سلسلة نقطة الدخول، تصبح `spam_flow`)، `shouldDeleteChatOnBlock`، `notifyObservableDialogHost`، `upsellCheckboxActionDefault`، `shouldOpenHomeScreenAction`، `showLeaveCheckbox`. يُحمِّل `ReportSpamDialogViewModel.initializeSpamDialog$1` حالة الحوار.

عند التأكيد، يُشغِّل `reportAsSpam$1`:

1. دردشة بوت: تخطَّى RPC (3.3). وإلا `SpamReportRepo.A02(...)` بالرسالة المختارة في قائمة عنصر واحد (أو بلا شيء).
2. يحمل النجاح معرّف بلاغ اختياري؛ الخطأ يعرض toast `str3bf8` (أو `C227489sZ.A00`، سجل `spamreportmanager/spam/report/no-network-cannot-report`). تُملأ WAM `wam_spam_report_perf` (11.3).
3. إجراء إضافي اختياري `triggerExtraAction$2` (3.2)، حوار اكتمال من `H2U` (10.2)، كتابات محلية (3.3).

### 3.2 بلاغ فقط مقابل بلاغ + إجراء إضافي (found)

يُخطِّط مربع الاختيار إلى السلسلة `report` (غير مُعلَّم) أو `report_block` (مُعلَّم)، تُستخدَم للتحليلات (`asd.BaC` مقابل `BaD`) وtoast ما بعد البلاغ. يختلف الإجراء الإضافي بحسب الهدف:

| الهدف | الإجراء الإضافي عند التعليم |
|--------|--------------------------|
| مستخدم | حظر عبر `C227489sZ.A01` ← IQ `blocklist` من `C34631Yx` (القسم 8)، سبب الحظر `null`، نقطة الدخول = `flow`، `deleteChat` = معطى `shouldDeleteChatOnBlock` |
| مجموعة | مهمة مغادرة المجموعة (`C98C` / `C9CI`، تُشغَّل بـJID المجموعة؛ دلالات المغادرة مستنتجة) |
| قناة | إخفاء القناة المُبلَّغ عنها محلياً (`NewsletterReportCompletionListener`، العلم **25218**)، ثم تدفق خروج/إلغاء متابعة النشرة |

تُرسَل IQ البلاغ أولاً؛ يُشغَّل الحظر/المغادرة بعد عودة RPC، بصرف النظر عن نتيجته (مستنتج من مسار التحكم، لا فحص نجاح قبل `triggerExtraAction$2`).

### 3.3 دردشات البوت والآثار المحلية (found)

تتخطَّى دردشات البوت `SpamReportRepo`: يستدعي العميل `BotMessageHelper/reportUgc` (`E1J.GENERIC`، `C27847C7h`) ويعامله كنجاح (`C214999If`)؛ شكل السلك غير معروف. لدردشات أخرى تنفّذ `C24120Ab1` الحالة 4:

| الخطوة | الأثر |
|------|------|
| لا رسالة مختارة | تجمع آخر **5** رسائل من الدردشة (`C14680f4.A01(..., 5, true)`؛ صفوف من نوع النظام مُستبعَدة، لا فلتر `from_me` في هذه النسخة) كالمحتوى المُبلَّغ عنه |
| دردشة مستخدم | سجل محلي `S3q.A0C(jid, localCode(flow), ...)`، `OptimisedDeliveryConversionLoggingController/handleUserReport`؛ العلم **20085** يضبط `H0J.A00(jid, ...)` (الغرض غير معروف) |
| بعد RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`)، `C31S.A01(...)`، لا فحص لنتيجة RPC في التدفق الظاهر |

---

## 4. غلاف stanza والنطاق

### 4.1 عقدة السبب مدمَجة في IQ (found)

لا تُصدِر RPCs عقدتي `spam_list` أخويتين. تُدمَج `spam_list` الرئيسية (JID، الرسائل) وعقدة السبب `C9E2` (جزء `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>`) بواسطة `C10340Uk.A04`، التي تدمج السمات والعناصر الفرعية المتماثلة الاسم (قيم سمات متعارضة أو أعداد عناصر فرعية مختلفة تُلغي الدمج). النتيجة:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

الدليل: بناة `C9EN` للأنواع 18-23 يستدعون `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`؛ تبني `C9E2` الحالة 5 `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`؛ `C19380nJ.A00.getServer() = "s.whatsapp.net"`. معرّف IQ `id` يأتي من `MessageClientSmaxWrapper.A01()` (`n<hex counter>`، `C10140Tq.A0H`). مهلة الإرسال 32000 ms (`A0F(node, id, cont, type, 32000, ...)`)؛ استجابة فارغة (مهلة/فشل تسليم) تصبح `C216549Uq`.

تضبط الأنواع 0 و1 `xmlns="w:g2"` و`to=<group>` حرفياً؛ تبني الأنواع 18-23 `<iq type="set">` وتعتمد على الدمج لـ`to` و`xmlns`. معرّف النوع المُمرَّر إلى المُرسِل هو **98** (مجموعة، نشرة، فعالية) و**385** (الإبلاغ للمشرف).

### 4.2 الأخوات الاختيارية المدمَجة في `spam_list`

| العقدة/السمة | المصدر | البوّابة | المستوى |
|-----------|--------|------|------|
| `spam_flow` | `flow` المعطى مُطبَّع بـ`C9ZJ` | دائماً | found |
| `wi_trace_id` (24 حرفاً تماماً) | `$wiTraceId` الخاص بـ`reportAsSpam$1` | اختياري | found؛ مصدر القيمة غير معروف |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | العلم **22256**؛ مستخدم: فحص دفتر العناوين، مجموعة: فحص عضوية المجموعة | found |
| العنصر الفرعي `biz_opt_out` | `C33446EhE.A07` | يوجد سجل اكتشاف أعمال | found (انظر 8.3) |

---

## 5. Stanzas لكل نوع

`from`/`to` لعنصر `<message>`: لمسار المستخدم تضبط العقدة المجهولة `C9E4` `to=<jid>` عندما تكون الرسالة خارجة (`key.fromMe`) و`from=<jid>` وإلا. الأعداد بوّابات الباني (`AbstractC10350Ul.A07`).

### 5.1 المستخدم (النوع 20)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<userJid>" spam_flow="chat" wi_trace_id="...">   <!-- jid: UserJid or interop jid (C99O) -->
    <message from|to="<userJid>" t id deleted_reason>              <!-- 0..210 items -->
      <raw v="2" local_message_type="<int>" mediatype="<enum>"><proto bytes></raw>
      <content_validation type="e2e_proto_message|mms_retry|plaintext_v3">
        <reporting_token v="<n>"><tag, min 6 bytes></reporting_token>
        <reporting_token_key><key, 16-32 bytes></reporting_token_key>
      </content_validation>
    </message>
    <call .../>                                                    <!-- 0..5 items, section 2.2 -->
    <extension_screen extension_id session_id t name entry_point>  <!-- 0..5, business Flows context (A0B), data child -->
    <biz_opt_out business_discovery_timestamp business_discovery_id business_discovery_entry_point/>
  </spam_list>
</iq>
```

يأخذ الباني ثلاث قوائم عناصر بحدود أقصى 210 (الرسائل)، 5 (عناصر المكالمة)، 5 (عناصر Flows التجارية بلا رسالة، `C33446EhE.A0B`: آخر 5 إدخالات من المخزن الخاص بالأعمال `messageless_flow_ids_per_business_<jid>`، العقدة `extension_screen`). يُحقَّق `jid` فقط مقابل `UserJid` و`C99O`؛ لا `subject` في هذا المسار.

### 5.2 المجموعة (النوع 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` هو **المستخدم الذي أضاف المُبلِّغ إلى المجموعة**، لا المُبلِّغ. يُقرأ من رسالة النظام المحلية ("انضم أنا") بـSQL `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`، `action_type` 12/124/144/127، `is_me_joined = 1`). اختياري. (found)
- `subject` هو اسم عرض المجموعة من سجل جهة الاتصال (`C06290Dn.A07().A00.A0b`؛ معنى الحقل مستنتج)، سلسلة فارغة `""` للمجموعات الأم في المجتمعات أو عند غياب سجل (`Voip.REJECT_REASON_DECLINED` هي `""`). ليست سبباً. بوّابة طول 0..65536. (found)
- قائمة رابعة في الباني تطرح (`getNode`) إذا كانت غير فارغة؛ تمرِّر RPC قائمة فارغة.

### 5.3 النشرة (النوع 21) ومنشور الحالة (النوع 22)

```xml
<spam_list jid="<newsletterJid>" subject="<channel name or ''>" spam_flow="newsletter_info_report">
  <message from="<newsletterJid>">...</message>        <!-- 0..65 -->
</spam_list>
<spam_list jid="<statusPosterJid>" spam_flow="status_post_report">
  <message from="<posterJid>">...</message>           <!-- 1..2 items, only the first selected status is passed -->
  <biz_opt_out .../>                                   <!-- optional -->
</spam_list>
```

`subject` للنشرة = اسم القناة (`C2130898y.A0j`)، `""` إذا غير معروف (found). بلاغات الحالة تستخدم جدوليها الخاصين `status_reporting_info` / `status_reporting_content`.

### 5.4 حالة القناة V2 (النوع 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

تُحدَّد الحالة بـ`server_id` + طابع زمني، لا محتوى مُرفَع. محتوى العنصر الفرعي `status` (`InterfaceC35700FdB`) غير محسوم.

### 5.5 الفعالية (النوع 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`، لا `wi_trace_id` (مسار `C9E2(String)` بمعطى واحد). رسالة للمشرفين (النوع 0): القسم 9.1.

---

## 6. المحتوى المُبلَّغ عنه والرموز

### 6.1 ما يُرفَع (found)

يبني `C33446EhE.A0A(fmsg, entryPoint)` عنصر رسالة واحداً لكل رسالة مُبلَّغ عنها:

| الجزء | التفصيل |
|------|--------|
| سمات `<message>` | `t` (طابع زمني الرسالة، 0..2^53)، `id` (معرّف stanza)، JID `from`/`to`، `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | protobuf `Message` مُعاد تسلسله (`C30628DTw` بـ`MessageContextInfo` `C30624DTs`)؛ `local_message_type` = عدد صحيح نوع رسالة داخلي |
| `<content_validation>` | رمز + مفتاح (6.2) |
| أعلام meta | `<edit v="1">` (مُحرَّرة)، `<multicast/>` (علم البث 64)، `<url_number/>` (العلم 4)، `<url_text/>` (العلم 2)، معرّف القالب، `hsm` tid، `iab reported_link`، `original_sender` / `group_history_sender`، نسخ دفع `futureproof`/`request`/`send` (`pay`)، `reported_push_name` |
| العنصر الفرعي `<reporting>` | العلم **5718**: مبني من صفوف `reporting_info` الخاصة بالرسالة (`C23070uA.A03`)، حتى 1000 إدخال (`C31085Dfd` الحالة 28)؛ المخطط لكل إدخال لم يُقرأ كاملاً |
| نواقل بديلة | `<plaintext>`، `<enc type=msg|pkmsg|skmsg|media|text>`، `<reporting_content>` (`C31084Dfc`، `C31081DfZ`) |

`mediatype` (33 قيمة، found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

رسائل قالب OTP: يُستبدَل عنصر العلامة النائب `<code>` في عناوين الأزرار بالرمز الحقيقي قبل التسلسل (`AbstractC32303E8u.A00`). المرة الواحدة: عندما تكون الرسالة من نوع "مرة واحدة" وفُتحت/انتهت أصلاً والمصدر ليس `media_viewer` / `view_once_viewer`، تكون `A06` صحيحة ويُتخطَّى بلوك التسلسل. ما إذا كان العنصر يحمل بعد ذلك `raw` فارغاً أو غائباً مستنتج (الإعلان غير مُهيَّأ في الفك).

لا تُعاد الملفات الوسائطية رفعها بهذه stanza؛ تحمل الرسالة المُسلسَلة مراجع الوسائط (مستنتج؛ لا استدعاء رفع مُعثور عليه). تحمل stanza بروتو النص الصِّرف والمفتاح معاً، فيستطيع الخادم قراءة المحتوى: العناصر **مُعثور عليها**، قابلية القراءة **مستنتجة**.

### 6.2 رمز الإبلاغ والمفتاح (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

يُجمَّع في `C33446EhE.A03` من الصف المخزَّن (`C34539Ez0`): بايتات الرمز (`A05`)، النسخة (`A02`)، معرّف stanza (`A03`)، المفتاح (`A07`). إذا كان المفتاح غائباً يُعاد استخلاصه: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` ← الدالة الأصلية `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (معرّف حالة الاستخدام **5**؛ الدردشات غير الخاصة بمستخدم تمر عبر نسخ `JniBridge`). إذا كان كلا المفتاح ورمز بطول 6 بايت غائبين/صفريين يسجِّل العميل `ReportingToken/MissingFkAtReport` ويستخدم مفتاحاً بطول 32 بايت كلها أصفار. رمز غائب يُعيد `null` (`ReportingToken is null`، العنصر بلا `content_validation`).

### 6.3 دورة حياة الرمز (found إلا إذا أُشير إلى غيره)

| المرحلة | التفصيل |
|-------|--------|
| رسالة خارجة | باني `C35241aW.A00(token16, v)` ← `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. الرمز = أول 16 بايت من `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`، `AbstractC38971i1.A00`). `canonicalContent` = بروتو الرسالة بتصفية حقل معتمدة على النسخة (`A07`، تحذف حقولاً فرعية مختارة من الحقل 35؛ القراءة مستنتجة). مُستدعو الباني لم يُتعقَّبوا |
| مشاركة تاريخ المجموعة | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): لرسائل النوع 117 `<reporting>` بعنصر فرعي واحد لكل إدخال (سمة `id`، عنصر فرعي `<reporting_token v>`) |
| رسالة واردة | عنصر فرعي stanza `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>` يُحلِّله `C34764F6h` / `C1S0`، العلم **5718**؛ كلا الوسم والرمز اختياريان، الوسم مطلوب |
| التخزين | الجدولان `reporting_info` (`reporting_tag`، `stanza_id`، `is_message_add_on`، `send_timestamp`، `receive_flow`) و`reporting_info_content` (`reporting_token`، `reporting_token_content`، `reporting_token_version`، `reporting_token_key`)؛ `message_conditional_reveal.reporting_token_info` (blob)؛ `group_history_share_reporting_info`؛ `status_reporting_info` |
| التاريخ | حقل `WebMessageInfo.reportingTokenInfo` **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes، `reportingTagTimestamp` **2** uint64؛ العلم **6578** |
| التنظيف | تُحذَف صفوف `reporting_info*` عندما يكون `receive_timestamp` أقدم من عتبة قطع (`FP7` الحالة 6)؛ قيمة العتبة غير محسومة |
| عنصر تحقق بديل | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

من يُصدِر `reporting_tag` وكيف يتحقق الخادم من الرمز: من جهة الخادم، غير معروف. الإقران (الوسم في stanza، الرمز+المفتاح في البلاغ) مستنتج.

---

## 7. نقاط دخول `spam_flow`

97 قيمة (found، `C9E2` الحالة 5، الترتيب = ترتيب المصفوفة). يمر معطى `flow` عبر `C9ZJ.A00`، التي تقبل **78** منها وتطرح `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` وإلا. كل أغلفة RPC الستة تستدعيها، وتقبض `SpamReportRepo.A02` الاستثناء وتُعيد فشلاً (خطأ من جانب العميل، لا stanza مُرسَلة). الـ78 مجموعة فرعية صارمة من الـ97. القيم الـ19 المرفوضة: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. هذه على الأرجح مصادر خاصة بالحظر فقط أو بـRPC أخرى (مستنتج). `channel_status_report` موجودة في التعداد لكن مرفوضة بواسطة `C9ZJ`؛ أي تدفق يمرِّره مُستدعي حالة القناة غير معروف.

| السطح | القيم |
|---------|--------|
| الدردشة/الفردية | `chat`، `message_menu`، `overflow_menu`، `overflow_menu_report`، `overflow_menu_block`، `block_dialog`، `block_header_chat`، `chat_list_block`، `chat_list_context_menu_block`، `chat_list_noinsub_block`، `chat_list_swipe_delete_block_upsell`، `chat_list_swipe_delete_report_upsell`، `triggered_block`، `notification_block`، `missed_call_notification_block`، `feedback_not_interested_block`، `user_controls_stop_block`، `media_viewer`، `view_once_viewer`، `account_info`، `account_info_block`، `account_info_report`، `account_info_report_as_guest_user`، `album_media_menu_report`، `iab_menu_report`، `extension_menu_report`، `comment_actions_bottom_sheet`، `payment_transaction_report` |
| لافتات spam | `1_1_spam_banner_block`، `1_1_spam_banner_report`، `1_1_old_spam_banner_block`، `one_to_one_spam_banner_block_server_flagged_suspicious`، `user_initiated_chat_suspicious_banner_block`، `user_initiated_chat_suspicious_banner_safety_tools_block`، `user_initiated_chat_suspicious_banner_safety_tools_report`، `dependant_chat_request_banner_decline_report_upsell`، `dependant_unknown_conversation_trust_signals_block` |
| بطاقات أمان FMX | `chat_fmx_card_block`، `chat_fmx_card_block_suspicious`، `chat_fmx_card_block_server_flagged_suspicious`، `chat_fmx_card_report_as_guest_user`، `chat_fmx_card_safety_tools_block`، `..._block_suspicious`، `..._report`، `..._report_suspicious`، `user_initiated_chat_fmx_card_safety_tools_block`، `..._report`، `trust_question_bottomsheet_block_server_flagged_suspicious` |
| تحذيرات احتيال على الجهاز (ODML) | `odml_scam_alert_blocked_composer_block`، `odml_scam_alert_bottom_sheet_block`، `odml_scam_alert_bottom_sheet_trust`، `odml_scam_alert_fmx_card_block`، `odml_scam_alert_fmx_card_trust`، `odml_scam_alert_suspicious_banner_block`، `odml_scam_alert_suspicious_banner_trust` |
| المجموعة | `group_info`، `group_info_report`، `group_info_leave_report_upsell`، `group_spam_banner_exit`، `group_spam_banner_exit_group_history`، `group_spam_banner_report`، `left_group_spam_banner_report`، `group_safety_check_bottom_sheet`، `group_fmx_card_leave`، `group_fmx_card_leave_non_suspicious`، `group_chatlist_leave_report_upsell`، `group_chatlist_swipe_leave_report_upsell`، `group_overflow_menu_leave_report_upsell`، `community_home`، `community_announcement_group_suspicious_banner_exit_dialog`، `community_home_suspicious_banner_exit_dialog`، `overflow_menu_community_report` |
| المكالمات | `call_log`، `call_log_block`، `call_detail_overflow_report`، `call_detail_safety_tools_block`، `call_detail_safety_tools_report`، `call_spam_dialog_block`، `call_spam_dialog_report`، `guest_call_report`، `guest_call_participant_report` |
| القنوات/الحالة/الفعاليات | `newsletter_info_report`، `newsletter_question_response_report`، `channel_status_report`، `status_post_report`، `status_question_answer`، `wamo_channel_report`، `event_home_report`، `event_info_report` |
| الأعمال | `biz_account_info_block`، `biz_block_header_chat`، `biz_block_list`، `biz_call_log_block`، `biz_overflow_menu_block`، `biz_spam_banner_block`، `ent_client`، `frx` |

يُختار اختيار `*_suspicious` مقابل العادي لبطاقات FMX في `C230769yA.A05` من `A0D(userJid)` (جهة اتصال معروفة أم لا)؛ هذا المُسنَد مستنتج أنه فحص دفتر عناوين. تُختار نسخ `server_flagged` بحسب نوع البطاقة؛ من أين تأتي علامة الخادم غير معروف.

`wi_trace_id`: سمة اختيارية بطول 24 حرفاً، تمر من المُستدعي؛ مُولِّدها لم يُعثر عليه (غير معروف). إنها أيضاً حقل في WAM `wam_spam_report_perf` (11.3).

---

## 8. الحظر، الأسباب وسياق الأعمال

### 8.1 IQ الحظر (found، منطقة `C34631Yx.A0M`)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

تُصدَر `biz_opt_out` و`entry_point` فقط لـ`action="block"`. يُختار `jid` بين شكلي PN وLID بفحص إعداد (فرع `zA02`؛ القاعدة الدقيقة غير مقروءة كاملاً)؛ عند الحظر المُعرِّف الإضافي هو واحد من `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. مهلة 20000 ms. نقاط الدخول التي تبدأ بـ`odml_scam_alert_*` تُعاد كتابتها إلى `1_1_spam_banner_block` (`odml_scam_alert_fmx_card_block` ← `chat_fmx_card_block`). دردشات PSA تستخدم IQ مختلفة (`xmlns="w:comms:chat"`، `<blocking action>`). الجلب: `type="get"`، `<item dhash>` اختياري.

### 8.2 أسباب الحظر (found)

تخطيط سلسلة ثابتة ← عدد صحيح محلي في `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1، `no_sign_up` = 2، `spam` = 3، `offensive_messages` = 4، `otp_did_not_request` = 5، `scam_or_fraud` = 6، غيرها = 0. تُخطِّط `RunnableC40792Hpk` نفس السلاسل إلى مجموعة رموز ثانية. هذه الأعداد تُغذِّي استدعاءات سجل محلية؛ ما إذا كانت تصل إلى خادم غير معروف.

صحيفة حظر الأعمال (`C24126Ab7`): خريطة سبب الخادم إذا غير فارغة، وإلا `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`؛ دردشات قالب OTP: `no_longer_interested, otp_did_not_request, other`.

### 8.3 سياق اكتشاف الأعمال (found)

يقرأ `C33446EhE.A07` سجل اكتشاف الأعمال لـJID المُبلَّغ عنه (المخزن `LA8`): الطابع الزمني، المعرّف، نقطة الدخول. تعداد نقطة الدخول (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. تُرفَق بكلا البلاغات (`biz_opt_out` تحت `spam_list`) والحظر. هذه هي الإشارات الوحيدة عن كيفية بدء هذه الدردشة المُعثور عليها في العميل.

### 8.4 قوائم سبب البلاغ (found)

فقط إعلانات الأعمال تحمل قائمة قابلة للاختيار. تبدأ `ReportReasonListFragment` فارغة وتُملأ من `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (الاستجابة `mobile_config` > `list` بـ`name`، `v`، `country`). تعداد الحل البديل الثابت (`EnumC37888GeT`): `scam_or_fraud`، `pretending_impersonation`، `illegal_dangerous`، `inappropriate_hateful_violent`، `dont_like_ad`. متى يُستخدَم الحل البديل: مستنتج أنه عند غياب قائمة الخادم. لا يوجد مُنتقي سبب لبلاغات المستخدم/المجموعة/الرسالة العادية؛ "السبب" الوحيد على السلك هو `spam_flow`.

---

## 9. الإبلاغ لمشرفي المجموعة

### 9.1 الإرسال والجلب (found، `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

لا محتوى، رمز، أو `spam_flow` مُرسَل؛ فقط معرّف الرسالة. الأخطاء تسجِّل فقط `Rta::<op>/onError: <code>` أو `/onDeliveryFailure: Network Failure`.

### 9.2 مفتاح تبديل بلاغ العضو (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (تفعيل) أو `<not_allow_admin_reports/>` (تعطيل)، smax 384. العقدتان عنصران فرعيان مباشران لـIQ، لا مُغلَّفتان في عقدة `group`. يقبل الباني حتى أربع عقد إعداد أخوية في IQ واحدة.

---

## 10. استجابة الخادم وحوارات الاكتمال

### 10.1 الاستجابة (found)

النجاح (`type=result`): عنصر فرعي `report` بسمة `id` (حد أقصى 20 حرفاً) ← `C213959Ch.A01` ← يُعاد إلى الواجهة كمعرّف البلاغ. الأخطاء (`<error code text>`)، لكل صنف استجابة:

| الرمز | الاسم | فردي | مجموعة | نشرة | حالة | حالة V2 | فعالية |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 حوارات الاكتمال

يحسم `H2U` من معرّف البلاغ والبوّابات، ثم يبني `C5BD` الـfragment (`arg_report_id`، `arg_is_ad_report`):

| البوّابة | الحوار |
|------|------|
| العلم **25818**، دردشة مستخدم، رسالة حاضرة | `NciiCompletionDialogFragment` |
| العلم **6145** | `DsaCompletionDialogFragment` (الاتحاد الأوروبي) |
| العلم **14249** | `UkOsaCompletionDialogFragment` |
| الأعلام **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

كلها إلا NCII تحتاج معرّف بلاغ غير فارغ؛ لا معرّف يعني لا حوار.

---

## 11. إشارات الإساءة على العميل

### 11.1 ما يرسله العميل بما يتجاوز المحتوى (found)

نقاط الدخول بـ`*_server_flagged_suspicious` تعني أن البطاقة ظهرت لدردشة مُعلَّمة بإشارة غير فحص جهة الاتصال المحلي؛ كيف يعرف العميل تلك العلامة غير معروف. المُرسَل في البلاغات: `is_known_chat`، `biz_opt_out` (كيف بدأت الدردشة التجارية)، عناصر المكالمة (المدة، من أنهى، سبب الإنهاء)، سياق Flows التجاري `extension_screen`، `source` (من أضافني إلى المجموعة)، `reported_push_name`، أعلام إعادة التوجيه/البث/URL على كل رسالة، علم التحرير، حالة المرة الواحدة، نقطة الدخول، `wi_trace_id` اختياري.

### 11.2 اكتشاف احتيال على الجهاز (found، محدود النطاق)

تُشغِّل `com.whatsapp.integrityai` مجموعة نماذج مُنزَّلة (`scam_detection`) على الجهاز عبر ExecuTorch (`ScamDetectorImpl`، `EmbeddingProviderImpl`، `InputFeatureProviderImpl`؛ الميزات `mostRecentSenderScore`، `isCountryMismatch`). تُشغِّل النتائج لافتات/صحائف تحذير ونقاط الدخول `odml_scam_alert_*` أعلاه. يُكتَب سجل فحص JSON محلي (`outcome`، `inputs`، `model_info`، `verification`) إلى `FileStash` عندما يكون `integrity_warning_report_enabled` (`C57375Pog`). لا رفع لذلك السجل مُعثور عليه (غير معروف). مستقل عن stanza بلاغ `spam`.

### 11.3 القياس عن بُعد (found)

WAM `wam_spam_report_perf` (`C97R`، المعرّف 6310): `dedup_key`، `report_attempt_count`، `report_duration_ms`، `report_error_code`، `report_spam_flow`، `report_status`، `wi_trace_id`. تخطيط رمز الخطأ في `reportAsSpam$1`: الإلغاء -4، المهلة/لا استجابة -1، استثناء آخر -3، خطأ بروتوكول = رمز خطأ IQ.

---

## 12. Baileys

حزمة `baron-baileys-v2` لا تحمل واجهة بلاغ. الأشكال أدناه تأتي من العقد المُعثور عليها وغير مُختبَرة.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

أشكال بلاغ المستخدم/المجموعة/القناة تتبع القسم 5 (عقدة `spam_list` واحدة مدمَجة، `xmlns: 'spam'`، `to: 's.whatsapp.net'`).

| لماذا يفشل (كلها مستنتجة) | السبب | الحل |
|--------------|-------|-----|
| خطأ 548 أو عدم تنفيذ صامت | لا رمز/مفتاح إبلاغ صالح: يحذف Baileys العنصر الفرعي `<reporting>` من الرسائل الواردة ولا يستخلص المفتاح أبداً | يُحلَّل `reporting_tag`/`reporting_token` عند الاستلام، يُخزَّن لكل رسالة، يُستخلَص المفتاح من `messageSecret` (معرّف حالة استخدام 5) وقت البلاغ |
| 400 | `jid` من فئة خاطئة (يجب أن يكون مستخدم/interop للنوع 20)، أعداد عناصر تتجاوز الحدود، نوع `spam_flow` خاطئ | استخدام سلاسل `spam_flow` من القسم 7؛ البقاء تحت 210/5 عناصر |
| IQ مرفوضة | عقدتا `spam_list` أخويتان (السبب مُرسَل كعقدة ثانية) بدلاً من عقدة واحدة مدمَجة | إرسال `spam_list` واحدة بكل السمات |

كلا `wi_trace_id` و`is_known_chat` اختياريان في الباني؛ ما إذا كان الخادم يقبل بلاغات برموز مُفتعَلة غير معروف.

---

## 13. حالات الخطأ

| العرض | السبب | المستوى |
|---------|-------|------|
| toast `str3bf8`، لا شيء مُرسَل | رفضت `C9ZJ` قيمة `flow` (`Invalid BlockSpamReportOrigin value`) | found |
| فشل `unrecognized jid` | JID الدردشة ليس من أي نوع مستخدم/مجموعة/حالة/نشرة | found |
| البلاغ "يفشل" دون toast | خطأ خادم 548: تُعيد `C9ZI.A00` نفس جسم النتيجة غير الخاطئة كمسار البوت | found |
| toast فشل عام | 400/403/429/500/501، أو مهلة (32 ث) ← `C216549Uq` | found |
| محتوى البلاغ غائب | مرة واحدة فُتحت/انتهت والمصدر ليس عارضاً؛ الرسالة بلا رمز مخزَّن | found / inferred |
| الحالة المحلية تقول مُبلَّغاً، رفضه الخادم | يُكتَب `is_spam_reported` بعد RPC دون فحص نتيجة ظاهر | found (التدفق)، inferred (الأثر) |

---

## 14. فروق أساسية

| لا تخلط بين | و |
|----------------|------|
| `spam_list@source` | المُبلِّغ. إنه المستخدم الذي أضاف المُبلِّغ إلى المجموعة |
| `spam_list@subject` (مجموعة، قناة) | سبب. إنه اسم المجموعة/القناة |
| `spam_flow` | سبب البلاغ. إنه سطح الواجهة الذي حفَّز البلاغ (97 قيمة) |
| البلاغ (`xmlns` من نوع `spam`) | الحظر (`xmlns` من نوع `blocklist`)، الإبلاغ للمشرف (`xmlns` من نوع `w:g2`)، إلغاء الاشتراك التسويقي (`xmlns` من نوع `optoutlist`، `C31105Dfx`، لم يُحلَّل أكثر) |
| عقدتا `spam_list` | عقدة `spam_list` واحدة مدمَجة (السمات والعناصر الفرعية مُجمَّعة) |
| spam المكالمة | spam الفعالية. بلاغات المكالمة من النوع 20 بعنصر `call`؛ النوع 18 هو `event_id` |
| `reporting_tag` (يُصدِره الخادم، يُخزَّن عند الاستلام) | `reporting_token` (HMAC بطول 16 بايت، يُرسَل مع الرسائل الخارجة ويُرفَع في البلاغات) و`reporting_token_key` (مُستخلَص، يُرفَع) |
| الإبلاغ للمشرف | الإبلاغ لـWhatsApp. بلاغ المشرف يرسل فقط `message_id`؛ لا محتوى، لا رمز |
| `wi_trace_id` (معرّف تتبُّع يُرسِله العميل) | معرّف البلاغ، الذي يُعيده الخادم في `<report id>` |
| `report_block` | قيمة سلكية. إنها سلسلة تحليلات/toast خاصة بالعميل؛ الحظر IQ خاصة به |
| مفتاح تبديل `allow_admin_reports` (`$t=1`) | رسالة الإبلاغ للمشرف (`$t=0`) |

---

## 15. التدفق من البداية إلى النهاية

```
[User]                  [Client]                                        [WhatsApp server]
  │ Report / Block+Report    │                                               │
  ├────────────────────────▶│ ReportSpamDialogFragment(flow = spam_flow)     │
  │ confirm (+block/leave)   │ reportAsSpam$1                                │
  │                          │  bot chat ──▶ BotMessageHelper/reportUgc      │
  │                          │ SpamReportRepo.A02: route by JID class        │
  │                          │  C9ZJ(flow) ──✗ IllegalArgumentException      │
  │                          │  no message ──▶ last 5 messages from DB       │
  │                          │ serialize msgs (EhE) + token + key,           │
  │                          │ is_known_chat, biz_opt_out, call items        │
  │                          │ C9EN + C9E2 merged into ONE spam_list         │
  │                          │ ── iq set xmlns=spam to=s.whatsapp.net ─────▶│
  │                          │                                   verify token│
  │                          │◀── result <report id> | error 400/403/429/    │
  │                          │    500/501/548 (548 treated as success)       │
  │                          │ WAM wam_spam_report_perf                      │
  │                          │ contacts.is_spam_reported = 1                 │
  │                          │ extra action:                                 │
  │                          │  user ── iq set xmlns=blocklist (block) ────▶│
  │                          │  group ─ leave   channel ─ hide + exit        │
  │◀─ completion dialog (DSA / UK OSA / AU OSA / NCII; needs report id)      │
  │                                                                          │
  │ member: iq set xmlns=w:g2 to=group reports>report{message_id} ──────────▶│
  │ admin : iq get xmlns=w:g2 to=group <reports/> ◀── report > reporter      │
```

---

## 16. غير معروف

| العنصر | السبب |
|------|--------|
| تحقق الرمز من جهة الخادم، إصدار `reporting_tag`، كيف يُحسَم `server_flagged` | منطق الخادم، ليس في APK |
| مصدر `wi_trace_id` | المُولِّد لم يُوجَد في الفك |
| محفِّز واجهة بلاغ الفعالية، شكل سلك بلاغ دردشة البوت | فقط مُستدعو لامبدا (`AYs`، `Aaa`) / `reportUgc` لم يُتعقَّبا بعد `C33437Eh4` |
| سلسلة التدفق التي يمرِّرها مُستدعي بلاغ حالة القناة | `channel_status_report` مرفوضة بواسطة `C9ZJ` |
| عتبة قطع تنظيف `reporting_info*` | مُستدعي `FP7` الحالة 6 لم يُتعقَّب |
| رفع سجل فحص الاحتيال المحلي | لا مستهلك مُعثور عليه |
| مخطط كل إدخال من العنصر الفرعي `reporting` الخاص بكل رسالة والغرض من استدعاء العلم 20085 | مبني من صفوف قاعدة بيانات، منطق المستهلك لم يُقرأ |
| القبول الحي لأي stanza في القسم 12 | لم تُلتقط أي حركة |
