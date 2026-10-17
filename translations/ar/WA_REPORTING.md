<!-- src-sha1: 27b3b625c1ca67d873007881de02f13ba8cbf277 -->
# WhatsApp Reporting — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-17
**النطاق:** الإبلاغ عن المستخدم/جهة الاتصال والمجموعة والقناة والحالة والمكالمة والرسالة — stanzas من نوع SMAX `spam`، و `spam_list`، وأنواع البلاغات، ونقاط دخول `spam_flow`، وtokens الإبلاغ، ورفع المحتوى، وواجهة الإبلاغ/الحظر، والإبلاغ إلى المشرف، وstanza الحظر وقوائم الأسباب، وأخطاء الخادم، وإشارات إساءة الاستخدام من جهة العميل، وBaileys

---

## 1. ما هو الإبلاغ (تقنيًا)

البلاغ هو IQ واحد من نوع `set` إلى `s.whatsapp.net` في مساحة الأسماء `spam`. يحمل عقدة `spam_list` (الكيان المُبلَّغ عنه، والرسائل المُبلَّغ عنها، ونقطة الدخول، وسياق اكتشاف الأعمال). يعيد العميل تسلسل الرسائل المُبلَّغ عنها كـ protobuf نصي صريح ويرفعها مع reporting token والمفتاح الذي يتحقق منه. الحظر stanza منفصل (`blocklist`). الإبلاغ إلى المشرف stanza ثالث غير مرتبط (`w:g2`).

كل العبارات تحليل ثابت لـ APK المفكوك. المستوى: **found** = قُرئ في الكود، **inferred** = مستنتج من الكود، **unknown** = غير محسوم. لم يُلتقط شيء هنا على الشبكة.

| الكيان | الاسم في 2.26.41.6 | الدور |
|--------|----------------|------|
| باني IQ (متعدد الأغراض، `$t` يحدد الشكل) | `C9EN` | يبني كل IQ بلاغ (الأنواع 0 و 18-23) وكثيرًا من IQ غير ذات صلة |
| عقدة السبب/نقطة الدخول | `C9E2` | `spam_list` مع `spam_flow` و `wi_trace_id` و `is_known_chat` ... (`xmlns="spam"`) |
| عنصر فرعي لإعداد المجموعة | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| غلاف المحتوى | `C31080DfY` | `raw` و `content_validation` و `reporting_token` و `reporting_token_key` |
| عقد متنوعة | `C31084Dfc`, `C31085Dfd` | flags (`multicast`, `url_text`, ...)، و `biz_opt_out`، و `reporting` |
| المُسلسِل ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`، وتجميع الـ token |
| مدير SMAX | `SpamRPCManager` | `A01`-`A06`، واحدة لكل نوع بلاغ (اسم الحزمة غير مشوَّش) |
| المستودع | `SpamReportRepo` | يوجّه حسب فئة JID، والآثار الجانبية المحلية |
| أغلفة RPC | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | الحزمة `com.whatsapp.reportinfra.rpc` |
| القائمة البيضاء للأصل | `C9ZJ` | يتحقق من نقطة الدخول (78 قيمة) |
| الواجهة | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | حوار البلاغ، مع حظر/مغادرة اختيارية |
| منفِّذ الحظر | `C227489sZ` → `C34631Yx` | IQ من نوع `blocklist` |
| الإبلاغ إلى المشرف | `RtaXmppClient` | طابور بلاغات `w:g2` |
| مخزن الـ token | `C23070uA` | الجدولان `reporting_info`, `reporting_info_content` |

تختلف الأسماء بين الإصدارات؛ وكل اسم مشوَّش أعلاه حُلَّ في 2.26.41.6 من سلاسل ثابتة (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`).

---

## 2. أنواع البلاغات

### 2.1 التوجيه (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` يتفرع حسب فئة JID:

| JID المُبلَّغ عنه | فئة RPC | `SpamRPCManager` | الباني `$t` | فئة الاستجابة | تسمية السجل |
|--------------|-----------|------------------|--------------|----------------|-----------|
| كائن حالة محدد (`AbstractC31014DeU` غير فارغ) على JID لنشرة/قناة | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| مستخدم (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| مجموعة | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| كائن حالة محدد على أي JID آخر، أو JID حالة مع قائمة رسائل | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| نشرة/قناة | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| معرّف حدث (سلسلة) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| أي شيء آخر | لا شيء | لا شيء | لا شيء | لا شيء | يُطلق `SpamReportRepo: unrecognized jid` ويُعاد كفشل |
| محادثة bot | لا شيء (انظر 3.3) | لا شيء | لا شيء | لا شيء | `C214999If` |

أشكال `C9EN` الأخرى التي ليست بلاغات spam: `$t=0` بلاغ إلى المشرفين و `$t=1` تبديل إعداد المجموعة (القسم 9)، و `$t=2` اقتراحات المجموعات الفرعية، و `$t=24/25/26` عقد `status`. يُستدعى RPC الحدث من lambdas الـ coroutine (`AYs`, `Aaa`)؛ والواجهة الأصلية unknown (توجد نقاط دخول الحدث `event_home_report` / `event_info_report`، لذا بلاغات الحدث inferred).

### 2.2 بلاغات المكالمات هي بلاغات مستخدم (found)

`SpamReportRepo.triggerReportCallNonSuspend` (الأصل `call_spam_dialog_report`) تستدعي `IndividualSpamReportRpc.A00` دون `jid` مُبلَّغ عنه ودون رسائل ومع عنصر مكالمة واحد. عنصر المكالمة (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

يتضمن `terminate_reason` القيم `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` وأخطاء الـ codec القاتلة. الـ flag **36386** يختار شكل JID الخاص في `to` (`CUC()` مقابل `Ask()`، LID مقابل PN inferred). بلاغ مستخدم من الواجهة مع `shouldIncludeCallLogsInReport` يضيف حتى 5 عناصر من سجل المكالمات (`C16430i1.A0B(jid, 5)`).

---

## 3. مسار العميل

### 3.1 الحوار

`ReportSpamDialogFragment` (حوار سفلي). وسائط الـ Fragment (found): `flow` (سلسلة نقطة الدخول، تصبح `spam_flow`)، `shouldDeleteChatOnBlock`، `notifyObservableDialogHost`، `upsellCheckboxActionDefault`، `shouldOpenHomeScreenAction`، `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` يحمّل حالة الحوار.

عند التأكيد يعمل `reportAsSpam$1`:

1. محادثة bot: يتخطى RPC (3.3). وإلا `SpamReportRepo.A02(...)` مع الرسالة المحددة في قائمة من عنصر واحد (أو بدونها).
2. النجاح يحمل معرّف بلاغ اختياريًا؛ والخطأ يعرض toast `str3bf8` (أو `C227489sZ.A00`، السجل `spamreportmanager/spam/report/no-network-cannot-report`). يُملأ WAM `wam_spam_report_perf` (11.3).
3. إجراء إضافي اختياري `triggerExtraAction$2` (3.2)، وحوار الإكمال من `H2U` (10.2)، وكتابات محلية (3.3).

### 3.2 الإبلاغ فقط مقابل الإبلاغ + إجراء إضافي (found)

يُترجم مربع الاختيار إلى السلسلة `report` (غير محدد) أو `report_block` (محدد)، وتُستخدم للتحليلات ولـ toast ما بعد البلاغ (`asd.BaC` مقابل `BaD`). يختلف الإجراء الإضافي حسب الهدف:

| الهدف | الإجراء الإضافي عند التحديد |
|--------|--------------------------|
| مستخدم | حظر عبر `C227489sZ.A01` → IQ `blocklist` من `C34631Yx` (القسم 8)، سبب الحظر `null`، نقطة الدخول = `flow`، و `deleteChat` = الوسيط `shouldDeleteChatOnBlock` |
| مجموعة | مهمة مغادرة المجموعة (`C98C` / `C9CI`، تعمل بـ JID المجموعة؛ دلالات المغادرة inferred) |
| قناة | إخفاء القناة المُبلَّغ عنها محليًا (`NewsletterReportCompletionListener`، الـ flag **25218**)، ثم مسار الخروج/إلغاء المتابعة للنشرة |

يُرسل IQ البلاغ أولًا؛ ويعمل الحظر/المغادرة بعد عودة RPC بغض النظر عن نتيجته (inferred من تدفق التحكم، لا فحص للنجاح قبل `triggerExtraAction$2`).

### 3.3 محادثات bot والآثار المحلية (found)

محادثات bot تتخطى `SpamReportRepo`: يستدعي العميل `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) ويعامله كنجاح (`C214999If`)؛ الشكل على الشبكة unknown. بالنسبة للمحادثات الأخرى تقوم `C24120Ab1` الحالة 4 بما يلي:

| الخطوة | الأثر |
|------|--------|
| لم تُحدد رسالة | تجمع أحدث **5** رسائل في المحادثة (`C14680f4.A01(..., 5, true)`؛ صفوف نوع النظام مستثناة، ولا فلتر `from_me` في هذا المتغير) بوصفها المحتوى المُبلَّغ عنه |
| محادثة مستخدم | سجل محلي `S3q.A0C(jid, localCode(flow), ...)`، `OptimisedDeliveryConversionLoggingController/handleUserReport`؛ الـ flag **20085** يتحكم في `H0J.A00(jid, ...)` (الغرض unknown) |
| بعد RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`)، `C31S.A01(...)`، دون فحص نتيجة RPC في المسار المرئي |

---

## 4. غلاف الـ stanza ومساحة الأسماء

### 4.1 عقدة السبب مدمجة في الـ IQ (found)

لا تُصدر RPCs عقدتي `spam_list` شقيقتين. تُدمج `spam_list` الرئيسية (jid، الرسائل) وعقدة السبب `C9E2` (مقطع `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>`) بـ `C10340Uk.A04` التي تدمج السمات والعناصر الفرعية المتماثلة الاسم (قيم سمات متعارضة أو أعداد عناصر فرعية متعارضة تُجهض الدمج). النتيجة:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

الدليل: بانيات `C9EN` للأنواع 18-23 تستدعي `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`؛ و `C9E2` الحالة 5 تبني `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`؛ و `C19380nJ.A00.getServer() = "s.whatsapp.net"`. يأتي `id` الخاص بالـ IQ من `MessageClientSmaxWrapper.A01()` (`n<hex counter>`، `C10140Tq.A0H`). مهلة الإرسال 32000 ms (`A0F(node, id, cont, type, 32000, ...)`)؛ والاستجابة الفارغة (مهلة/فشل تسليم) تصبح `C216549Uq`.

النوعان 0 و 1 يضبطان `xmlns="w:g2"` و `to=<group>` حرفيًا؛ أما الأنواع 18-23 فتبني `<iq type="set">` وتعتمد على الدمج لـ `to` و `xmlns`. معرّف النوع الممرَّر إلى المُرسِل هو **98** (مجموعة، نشرة، حدث) و **385** (الإبلاغ إلى المشرف).

### 4.2 عناصر شقيقة اختيارية مدمجة في `spam_list`

| العقدة/السمة | المصدر | البوابة | المستوى |
|-----------|--------|------|------|
| `spam_flow` | وسيط `flow` مطبَّع بواسطة `C9ZJ` | دائمًا | found |
| `wi_trace_id` (24 حرفًا بالضبط) | `$wiTraceId` الخاص بـ `reportAsSpam$1` | اختياري | found؛ أصل القيمة unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | الـ flag **22256**؛ مستخدم: فحص دفتر العناوين، مجموعة: فحص العضوية في المجموعة | found |
| العنصر الفرعي `biz_opt_out` | `C33446EhE.A07` | وجود سجل اكتشاف أعمال | found (انظر 8.3) |

---

## 5. stanzas حسب النوع

`from`/`to` لعنصر `<message>`: في مسار المستخدم تضبط العقدة المجهولة `C9E4` القيمة `to=<jid>` عندما تكون الرسالة صادرة (`key.fromMe`) و `from=<jid>` خلاف ذلك. الأعداد بوابات في الباني (`AbstractC10350Ul.A07`).

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

يأخذ الباني ثلاث قوائم عناصر بسقوف 210 (رسائل)، 5 (عناصر مكالمات)، 5 (عناصر تدفق أعمال دون رسائل، `C33446EhE.A0B`: آخر 5 إدخالات من مخزن كل نشاط تجاري `messageless_flow_ids_per_business_<jid>`، العقدة `extension_screen`). يُتحقق من `jid` مقابل `UserJid` و `C99O` فقط؛ ولا `subject` في هذا المسار.

### 5.2 المجموعة (النوع 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` هو **المستخدم الذي أضاف المُبلِّغ إلى المجموعة**، وليس المُبلِّغ. يُقرأ من رسالة النظام المحلية ("me joined") بالاستعلام `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`، `action_type` 12/124/144/127، `is_me_joined = 1`). اختياري. (found)
- `subject` هو اسم العرض للمجموعة من سجل جهة الاتصال (`C06290Dn.A07().A00.A0b`؛ معنى الحقل inferred)، وسلسلة فارغة `""` لمجموعات المجتمع الأم أو عند عدم وجود سجل (`Voip.REJECT_REASON_DECLINED` هو `""`). وليس سببًا. بوابة الطول 0..65536. (found)
- قائمة رابعة في الـ ctor ترمي استثناء (`getNode`) إذا لم تكن فارغة؛ ويمرر RPC قائمة فارغة.

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

`subject` للنشرة = اسم القناة (`C2130898y.A0j`)، و `""` إن لم يكن معروفًا (found). بلاغات الحالة تستخدم جداول tokens خاصة بها `status_reporting_info` / `status_reporting_content`.

### 5.4 حالة القناة V2 (النوع 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

تُعرَّف الحالة بـ `server_id` + الطابع الزمني، دون محتوى مرفوع. محتوى العنصر الفرعي `status` (`InterfaceC35700FdB`) غير محسوم.

### 5.5 الحدث (النوع 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`، دون `wi_trace_id` (مسار `C9E2(String)` بوسيط واحد). الرسالة إلى المشرفين (النوع 0): القسم 9.1.

---

## 6. المحتوى المُبلَّغ عنه والـ tokens

### 6.1 ما الذي يُرفع (found)

`C33446EhE.A0A(fmsg, entryPoint)` يبني عنصر رسالة واحدًا لكل رسالة مُبلَّغ عنها:

| الجزء | التفصيل |
|------|--------|
| سمات `<message>` | `t` (الطابع الزمني للرسالة، 0..2^53)، `id` (معرّف stanza)، `from`/`to` jid، `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | protobuf `Message` معاد تسلسله (`C30628DTw` مع `MessageContextInfo` `C30624DTs`)؛ `local_message_type` = int نوع الرسالة الداخلي |
| `<content_validation>` | token + مفتاح (6.2) |
| flags وصفية | `<edit v="1">` (معدّلة)، `<multicast/>` (flag البث 64)، `<url_number/>` (flag 4)، `<url_text/>` (flag 2)، معرّف القالب، `hsm` tid، `iab reported_link`، `original_sender` / `group_history_sender`، متغيرات الدفع `futureproof`/`request`/`send` (`pay`)، `reported_push_name` |
| العنصر الفرعي `<reporting>` | الـ flag **5718**: يُبنى من صفوف `reporting_info` للرسالة (`C23070uA.A03`)، حتى 1000 إدخال (`C31085Dfd` الحالة 28)؛ مخطط كل إدخال لم يُقرأ بالكامل |
| حوامل بديلة | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 قيمة، found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

رسائل قوالب OTP: يُستبدل العنصر النائب `<code>` في عناوين الأزرار بالرمز الحقيقي قبل التسلسل (`AbstractC32303E8u.A00`). العرض لمرة واحدة: عندما تكون الرسالة view-once ومفتوحة/منتهية بالفعل والأصل ليس `media_viewer` / `view_once_viewer`، تكون `A06` صحيحة ويُتخطى مقطع التسلسل. وما إذا كان العنصر يحمل حينها `raw` فارغًا أو غائبًا فهو inferred (التصريح غير مُهيَّأ في الفك).

لا تُعاد رفع ملفات الوسائط بهذا الـ stanza؛ الرسالة المُسلسلة تحمل مراجع الوسائط (inferred؛ لم يُعثر على استدعاء رفع). يحوي الـ stanza الـ proto النصي الصريح والمفتاح معًا، فيستطيع الخادم قراءة المحتوى: العقد **found**، وإمكانية القراءة **inferred**.

### 6.2 reporting token والمفتاح (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

يُجمَّع في `C33446EhE.A03` من الصف المخزّن (`C34539Ez0`): بايتات الـ token (`A05`)، والإصدار (`A02`)، ومعرّف stanza (`A03`)، والمفتاح (`A07`). إذا كان المفتاح مفقودًا يُشتق من جديد: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → الدالة native `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (معرّف حالة الاستخدام **5**؛ المحادثات غير المستخدم تمر عبر متغيرات `JniBridge`). إذا كان المفتاح و token من 6 بايتات كلاهما غائبًا/صفريًا يسجّل العميل `ReportingToken/MissingFkAtReport` ويستخدم مفتاحًا كله أصفار بطول 32 بايت. token مفقود يُرجع `null` (`ReportingToken is null`، العنصر بلا `content_validation`).

### 6.3 دورة حياة الـ token (found ما لم يُذكر غير ذلك)

| المرحلة | التفصيل |
|-------|--------|
| رسالة صادرة | الباني `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. الـ token = أول 16 بايتًا من `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = proto الرسالة مع تصفية حقول تعتمد على الإصدار (`A07`، تزيل حقولًا فرعية محددة من الحقل 35؛ القراءة inferred). مستدعو الباني لم تُتتبع |
| مشاركة سجل المجموعة | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): لرسائل النوع 117 `<reporting>` بعنصر فرعي لكل إدخال (السمة `id`، والعنصر الفرعي `<reporting_token v>`) |
| رسالة واردة | العنصر الفرعي في stanza `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>` تحلله `C34764F6h` / `C1S0`، الـ flag **5718**؛ كل من tag و token اختياري، ولكن tag مطلوب |
| التخزين | الجدولان `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) و `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`)؛ و `message_conditional_reveal.reporting_token_info` (blob)؛ و `group_history_share_reporting_info`؛ و `status_reporting_info` |
| السجل | `WebMessageInfo.reportingTokenInfo` الحقل **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes، `reportingTagTimestamp` **2** uint64؛ الـ flag **6578** |
| التنظيف | تُحذف صفوف `reporting_info*` عندما يكون `receive_timestamp` أقدم من حد فاصل (`FP7` الحالة 6)؛ قيمة الحد غير محسومة |
| عقدة تحقق بديلة | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

من يُصدر `reporting_tag` وكيف يتحقق الخادم من الـ token: جهة الخادم، unknown. الاقتران (tag في stanza، وtoken+key في البلاغ) inferred.

---

## 7. نقاط دخول `spam_flow`

97 قيمة (found، `C9E2` الحالة 5، الترتيب = ترتيب المصفوفة). يمرر الوسيط `flow` عبر `C9ZJ.A00` التي تقبل **78** منها وترمي `IllegalArgumentException("Invalid BlockSpamReportOrigin value")` خلاف ذلك. تستدعيها كل أغلفة RPC الستة، و `SpamReportRepo.A02` تلتقط الاستثناء وتعيد فشلًا (خطأ من جهة العميل، لا يُرسل stanza). الـ 78 مجموعة جزئية صارمة من الـ 97. القيم التسع عشرة المرفوضة: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. هذه على الأرجح أصول للحظر فقط أو لـ RPC أخرى (inferred). `channel_status_report` موجودة في enum لكن `C9ZJ` ترفضها؛ أي تدفق يمرره مستدعي حالة القناة unknown.

| السطح | القيم |
|---------|--------|
| محادثة / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| لافتات البريد المزعج | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| بطاقات FMX للسلامة | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| تنبيهات الاحتيال على الجهاز | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| المجموعة | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| المكالمات | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| القنوات / الحالة / الأحداث | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| الأعمال | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

الاختيار بين `*_suspicious` والعادي لبطاقات FMX يتم في `C230769yA.A05` انطلاقًا من `A0D(userJid)` (جهة اتصال معروفة أم لا)؛ وهذا الشرط inferred أنه فحص لدفتر العناوين. المتغيرات `server_flagged` تُختار حسب نوع البطاقة؛ ومصدر flag الخادم unknown.

`wi_trace_id`: سمة اختيارية من 24 حرفًا، تُمرَّر من المستدعي؛ ولم يُعثر على مولّدها (unknown). وهي أيضًا حقل في WAM `wam_spam_report_perf` (11.3).

---

## 8. الحظر والأسباب وسياق الأعمال

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

`biz_opt_out` و `entry_point` يصدران فقط مع `action="block"`. يُختار `jid` بين شكلي PN و LID بفحص إعداد (فرع `zA02`؛ القاعدة الدقيقة لم تُقرأ بالكامل)؛ وعند الحظر يكون المعرّف الإضافي واحدًا من `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. المهلة 20000 ms. نقاط الدخول التي تبدأ بـ `odml_scam_alert_*` تُعاد كتابتها إلى `1_1_spam_banner_block` (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). محادثات PSA تستخدم IQ مختلفًا (`xmlns="w:comms:chat"`، `<blocking action>`). الجلب: `type="get"`، مع `<item dhash>` اختياري.

### 8.2 أسباب الحظر (found)

سلسلة مضمّنة في الكود → int محلي في `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1، `no_sign_up` = 2، `spam` = 3، `offensive_messages` = 4، `otp_did_not_request` = 5، `scam_or_fraud` = 6، غير ذلك = 0. و `RunnableC40792Hpk` يحوّل السلاسل نفسها إلى مجموعة رموز ثانية. هذه الأعداد تغذي استدعاءات سجل محلية؛ وهل تصل إلى خادم unknown.

ورقة حظر الأعمال (`C24126Ab7`): خريطة أسباب الخادم إن لم تكن فارغة، وإلا `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`؛ ومحادثات قوالب OTP: `no_longer_interested, otp_did_not_request, other`.

### 8.3 سياق اكتشاف الأعمال (found)

`C33446EhE.A07` يقرأ سجل اكتشاف الأعمال للـ JID المُبلَّغ عنه (المخزن `LA8`): الطابع الزمني والمعرّف ونقطة الدخول. enum نقطة الدخول (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. يُرفق بالبلاغات (`biz_opt_out` تحت `spam_list`) وبعمليات الحظر. هذه هي إشارات "كيف بدأت هذه المحادثة" الوحيدة التي وُجدت في العميل.

### 8.4 قوائم أسباب البلاغ (found)

إعلانات الأعمال وحدها لها قائمة قابلة للاختيار. يبدأ `ReportReasonListFragment` فارغًا ويُملأ من `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (الاستجابة `mobile_config` > `list` مع `name`, `v`, `country`). enum احتياطي مضمّن (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. عند استخدام الاحتياطي: inferred أن قائمة الخادم غير متاحة. لا يوجد منتقي أسباب لبلاغات المستخدم/المجموعة/الرسالة العادية؛ و"السبب" الوحيد على الشبكة هو `spam_flow`.

---

## 9. الإبلاغ إلى مشرفي المجموعة

### 9.1 الإرسال والجلب (found، `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

لا يُرسل محتوى ولا token ولا `spam_flow`؛ بل معرّف الرسالة فقط. الأخطاء تسجّل فقط `Rta::<op>/onError: <code>` أو `/onDeliveryFailure: Network Failure`.

### 9.2 تبديل بلاغ الأعضاء (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (تفعيل) أو `<not_allow_admin_reports/>` (تعطيل)، smax 384. العقد أبناء مباشرون للـ IQ، وليست ملفوفة في عقدة `group`. يقبل الباني حتى أربع عقد إعدادات شقيقة في IQ واحد.

---

## 10. استجابة الخادم وحوارات الإكمال

### 10.1 الاستجابة (found)

النجاح (`type=result`): عنصر فرعي `report` بالسمة `id` (بحد أقصى 20 حرفًا) → `C213959Ch.A01` → يُعاد إلى الواجهة كمعرّف البلاغ. الأخطاء (`<error code text>`)، حسب فئة الاستجابة:

| الرمز | الاسم | Individual | Group | Newsletter | Status | Status V2 | Event |
|------|------|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 حوارات الإكمال

يقرر `H2U` انطلاقًا من معرّف البلاغ والبوابات، ثم يبني `C5BD` الـ fragment (`arg_report_id`, `arg_is_ad_report`):

| البوابة | الحوار |
|------|--------|
| الـ flag **25818**، محادثة مستخدم، الرسالة موجودة | `NciiCompletionDialogFragment` |
| الـ flag **6145** | `DsaCompletionDialogFragment` (الاتحاد الأوروبي) |
| الـ flag **14249** | `UkOsaCompletionDialogFragment` |
| الـ flags **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

كلها عدا NCII تحتاج معرّف بلاغ غير فارغ؛ وغياب المعرّف يعني عدم ظهور حوار.

---

## 11. إشارات إساءة الاستخدام على العميل

### 11.1 ما يرسله العميل إضافة إلى المحتوى (found)

نقاط الدخول ذات `*_server_flagged_suspicious` تعني أن البطاقة عُرضت لمحادثة عُلِّمت بإشارة غير فحص جهة الاتصال المحلي؛ وكيف يعرف العميل ذلك الـ flag unknown. المرسل في البلاغات: `is_known_chat`، و `biz_opt_out` (كيف بدأت محادثة العمل)، وعناصر المكالمات (المدة، ومن أنهى، وسبب الإنهاء)، وسياق Flows للأعمال `extension_screen`، و `source` (من أضافني إلى المجموعة)، و `reported_push_name`، وflags إعادة التوجيه/البث/URL على كل رسالة، وflag التعديل، وحالة view-once، ونقطة الدخول، و `wi_trace_id` الاختياري.

### 11.2 كشف الاحتيال على الجهاز (found، محدود النطاق)

يشغّل `com.whatsapp.integrityai` مجموعة نماذج منزَّلة (`scam_detection`) على الجهاز عبر ExecuTorch (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`؛ الميزات `mostRecentSenderScore`, `isCountryMismatch`). تقود النتائج لافتات/أوراق التحذير ونقاط الدخول `odml_scam_alert_*` أعلاه. يُكتب سجل مسح JSON محلي (`outcome`, `inputs`, `model_info`, `verification`) في `FileStash` عندما `integrity_warning_report_enabled` (`C57375Pog`). لم يُعثر على رفع لهذا السجل (unknown). وهو مستقل عن stanza البلاغ `spam`.

### 11.3 القياس عن بعد (found)

WAM `wam_spam_report_perf` (`C97R`، المعرّف 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. تعيين رمز الخطأ في `reportAsSpam$1`: الإلغاء -4، المهلة/عدم وجود استجابة -1، استثناء آخر -3، خطأ البروتوكول = رمز خطأ IQ.

---

## 12. Baileys

الحزمة `baron-baileys-v2` لا تحوي API للبلاغات. الأشكال أدناه مستمدة من العقد found وغير مختبرة.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

أشكال بلاغات المستخدم/المجموعة/القناة تتبع القسم 5 (`spam_list` واحدة مدمجة، `xmlns: 'spam'`، `to: 's.whatsapp.net'`).

| لماذا يفشل (كله inferred) | السبب | الحل |
|--------------|-------|-----|
| الخطأ 548 أو لا شيء يحدث بصمت | لا reporting token/key صالح: Baileys يُسقط العنصر الفرعي `<reporting>` للرسائل الواردة ولا يشتق المفتاح أبدًا | حلّل `reporting_tag`/`reporting_token` عند الاستقبال، وخزّنهما لكل رسالة، واشتق المفتاح من `messageSecret` (حالة الاستخدام 5) وقت البلاغ |
| 400 | `jid` من فئة خاطئة (يجب أن يكون مستخدم/interop للنوع 20)، أو أعداد العناصر فوق السقوف، أو نوع `spam_flow` خاطئ | استخدم سلاسل `spam_flow` من القسم 7؛ وابقَ تحت 210 / 5 عناصر |
| IQ مرفوض | عقدتا `spam_list` شقيقتان (السبب أُرسل كعقدة ثانية) بدل عقدة واحدة مدمجة | أرسل `spam_list` واحدة بكل السمات |

كل من `wi_trace_id` و `is_known_chat` اختياري في الباني؛ وهل يقبل الخادم بلاغات بـ tokens مفبركة unknown.

---

## 13. حالات الخطأ

| العَرَض | السبب | المستوى |
|---------|-------|------|
| toast `str3bf8`، لم يُرسل شيء | `C9ZJ` رفضت قيمة `flow` (`Invalid BlockSpamReportOrigin value`) | found |
| فشل `unrecognized jid` | JID المحادثة ليس مستخدمًا ولا مجموعة ولا حالة ولا نشرة | found |
| البلاغ "يفشل" دون toast | خطأ الخادم 548: `C9ZI.A00` تعيد كائن النتيجة غير الخطأ نفسه كما في مسار bot | found |
| toast فشل عام | 400/403/429/500/501، أو مهلة (32 ث) → `C216549Uq` | found |
| محتوى البلاغ مفقود | view-once مفتوحة/منتهية والأصل ليس عارضًا؛ الرسالة بلا token مخزّن | found / inferred |
| الحالة المحلية تقول إنه مُبلَّغ، والخادم رفض | يُكتب `is_spam_reported` بعد RPC دون فحص مرئي للنتيجة | found (التدفق)، inferred (النتيجة) |

---

## 14. فروق أساسية

| لا تخلط بين | وبين |
|----------------|------|
| `spam_list@source` | المُبلِّغ. هو المستخدم الذي أضاف المُبلِّغ إلى المجموعة |
| `spam_list@subject` (مجموعة، قناة) | سبب. هو اسم المجموعة/القناة |
| `spam_flow` | سبب البلاغ. هو سطح الواجهة الذي أطلق البلاغ (97 قيمة) |
| البلاغ (xmlns `spam`) | الحظر (xmlns `blocklist`)، والإبلاغ إلى المشرف (xmlns `w:g2`)، وإلغاء الاشتراك التسويقي (xmlns `optoutlist`، `C31105Dfx`، لم يُحلَّل أكثر) |
| عقدتا `spam_list` | `spam_list` واحدة مدمجة (السمات والعناصر الفرعية مجمَّعة) |
| بريد المكالمات المزعج | بريد الأحداث المزعج. بلاغات المكالمات من النوع 20 مع عنصر `call`؛ والنوع 18 هو `event_id` |
| `reporting_tag` (يصدره الخادم، ويُخزَّن عند الاستقبال) | `reporting_token` (HMAC من 16 بايتًا، يُرسل مع الرسائل الصادرة ويُرفع في البلاغات) و `reporting_token_key` (مشتق، يُرفع) |
| الإبلاغ إلى المشرف | الإبلاغ إلى WhatsApp. بلاغ المشرف يرسل `message_id` فقط؛ دون محتوى ودون token |
| `wi_trace_id` (معرّف تتبع يرسله العميل) | معرّف البلاغ الذي يعيده الخادم في `<report id>` |
| `report_block` | قيمة على الشبكة. هي سلسلة تحليلات/toast في العميل؛ والحظر IQ مستقل |
| تبديل `allow_admin_reports` (`$t=1`) | رسالة الإبلاغ إلى المشرف (`$t=0`) |

---

## 15. المسار الكامل

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

## 16. Unknown

| البند | السبب |
|------|--------|
| تحقق الخادم من الـ token، وإصدار `reporting_tag`، وكيفية تحديد `server_flagged` | منطق جهة الخادم، ليس في APK |
| أصل `wi_trace_id` | لم يُعثر على المولّد في الفك |
| مُشغِّل واجهة بلاغ الحدث، وشكل بلاغ محادثة bot على الشبكة | مستدعو lambda فقط (`AYs`, `Aaa`) / `reportUgc` لم يُتتبع بعد `C33437Eh4` |
| سلسلة التدفق التي يمررها مستدعي بلاغ حالة القناة | `channel_status_report` ترفضها `C9ZJ` |
| حد تنظيف `reporting_info*` | مستدعي `FP7` الحالة 6 لم يُتتبع |
| رفع سجل مسح الاحتيال المحلي | لم يُعثر على مستهلك |
| مخطط كل إدخال في العنصر الفرعي `reporting` لكل رسالة، والغرض من استدعاء الـ flag 20085 | يُبنى من صفوف DB، ومنطق المستهلك لم يُقرأ |
| القبول الحي لأي stanza في القسم 12 | لم تُلتقط حركة شبكة |
