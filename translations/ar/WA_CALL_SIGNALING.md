<!-- src-sha1: 7c179c130d5822c6103aa9a9ae2e6751ec1b0bd8 -->
# WhatsApp إشارات المكالمات — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-10-24
**النطاق:** إشارات مكالمات الصوت/الفيديو في Android: غلاف `<call>` والإقرارات (acks)، وstanzas الإجراءات (offer، accept، preaccept، reject، terminate، transport، relaylatency، enc_rekey، mute_v2، group_info، group_update، lobby، link_*، waiting_room_*، bcall)، وحمولة offer (audio / video / capability / encopt / net)، ومفتاح المكالمة وتشفيره عبر Signal، وإعادة التشفير (rekey، الإصداران v2 / v3)، واشتقاق مفتاح الوسائط، واختيار relay والنقل، وICE / STUN / DTLS / SRTP مقابل مسار الوسائط الخاص بـ WhatsApp، والمكالمات الجماعية، وروابط المكالمات والمكالمات المجدولة، وسجل المكالمات ورسائل bcall، وأكواد nack لـ offer، وسلوك reject وterminate، وأعلام الميزات، ومقارنة مع Baileys

---

## 1. ما هو (تقنيًا)

إشارات المكالمات هي مجموعة من stanzas من نوع `<call>` على اتصال chatd العادي (انظر [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). كل stanza يحمل عنصرًا ابنًا واحدًا للإجراء بالضبط. طبقة Java لا تبني stanzas المكالمات ولا تحللها: محرك VoIP native هو من يفعل ذلك، وJava تقوم فقط بـ (أ) تغليف العناصر الأبناء الصادرة داخل `<call>`، (ب) تشفير مفتاح المكالمة عبر Signal لكل جهاز، (ج) تمرير الـ stanzas الواردة إلى المحرك، (د) التفاعل مع أحداث المحرك. الوسائط (حركة شبيهة بـ RTP نحو relays، وICE، وDTLS، وSRTP) ليست إشارات وتعمل على مقابس UDP/TCP يملكها المحرك. كل ما يرد مصدره التحليل الساكن؛ ولم يُلتقط شيء على السلك. المستويات: **found** = مقروء في Java أو في سلاسل native، **inferred** = مستنتج، **unknown** = غير محلول.

| الطبقة | الاسم في 2.26.41.6 | الدور |
|-------|----------------|------|
| واجهة JNI | `Voip` / `VoipNativeImpl` (`com.whatsapp.calling.voipcalling`) | 148 دالة native (`startCall`، `acceptCall`، `rejectCall`، `nativeHandleIncomingSignalingXmpp`، ...) |
| خطاف الصادر | `OutgoingSignalingHandler` ينفّذ `SignalingXmppCallback.sendCallStanza(Jid, callId, VoipStanzaChildNode)` | من المحرك إلى Java؛ معالجة لكل وسم، وتشفير مفتاح المكالمة |
| كاتب الغلاف | `CIX` (الطابور)، `C27410BtV` (stanza المكالمة)، الحالة 206 في خيط الكتابة داخل `HandlerThreadC21920sG` | يبني `<call to id>` |
| معالج الوارد | `C40641lA` (`CallStanzaHandler`)، `BQU` (stanza مكالمة محلَّل)، `C83` (فك التشفير)، `C28120CKj` / `RunnableC29343CoU` (التوزيع إلى المحرك) | تحليل الغلاف، فك تشفير `<enc>`، تغذية المحرك |
| أحداث المحرك | `VoipEventCallback`، `VoiceServiceEventCallback` (116 دالة رد نداء) | من المحرك إلى الواجهة / الحالة |
| رد نداء التشفير | `DefaultCryptoCallback`، `SignalIdentityCryptoCallback` (`CryptoCallback`) | HKDF / HMAC / عشوائي / توقيعات Ed للمحرك |
| إشارات HTTP | `VoiceTeeHttpSignalingHandler` (`SignalingHttpCallback`) | ناقل إشارات بديل، طلب TEE |
| المحرك native | `libwhatsapp.so` (يُفك من أرشيف superpack باسم `libs.so`؛ يصدّر `Java_com_whatsapp_calling_voipcalling_Voip_*`) | مُسلسِلات / مفكّكات stanzas، آلة حالة المكالمة، النقل، الوسائط |

نقاط تحسم بقية التقرير:

- قواعد stanza موجودة في الكود native: المُسلسِلات `serialize_*` (C/C++) وحزمة Rust باسم `call_control` (مسارات المصدر `xplat/wa-voip/rust/call_control/src/stanza_deserializer/...` في سلاسل panic الخاصة بها) لتحليل الوارد. تعذّر فك تجميع مكتبة voip؛ كل عبارة عن native تستند إلى السلاسل والأسماء المصدَّرة فقط (السلاسل found، والمعنى inferred).
- Java طبقة رقيقة، ولهذا فإن مجموعة الوسوم الظاهرة في Java (10 وسوم في `sendCallStanza`) أصغر بكثير من المجموعة التي يفهمها المحرك (القسم 4).
- مفتاح المكالمة يُنشأ ويُستخدم داخل المحرك؛ وJava تشفّره بجلسة Signal الثنائية العادية (القسم 6). شيفرة HKDF نفسها التي يحتاجها المحرك هي دالة رد نداء في Java (القسم 7).
- مسار الوسائط الخاص بـ WhatsApp (relay allocate/bind، حزم "WARP"، SRTP قفزة-بقفزة، SFrame للمكالمات الجماعية) يختلف عن مسار ICE/DTLS بنمط WebRTC، الموجود كنمط "web_p2p" (القسم 8).

---

## 2. واجهة Java / native

ردود النداء المسجّلة عند البدء (found): `SignalingXmppCallback.sendCallStanza(to, callId, node)` (من المحرك إلى Java، ابن واحد للمكالمة)؛ `CryptoCallback` (`generateE2EKeysV2`، `getSecureSsrc`، `hkdfSha256`، `hmacSha256`، `generateRandomBytes`؛ ويضيف `SignalIdentityCryptoCallback` الدالة `signWithIdentityKey` بتوقيع 64 بايت والدالة `verifySignature` بمفتاح 32 بايت)؛ `SignalingHttpCallback` (`sendMsg(callId, bytes, requestType)`، `cancelMsg`؛ الأنواع: جلسة صوت 0، avatar للـ codec 1)؛ `VoipEventCallback` (القسم 13). `VoipStanzaChildNode` هو الشجرة المرئية لـ JNI (الوسم، السمات، الأبناء، البيانات)؛ وتحوّلها Java من عقدة chatd وإليها، والتي يوصف ترميزها الثنائي في [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) القسم 8.

| مدخل JNI (found) | يُغذّى من | ملاحظات |
|-------------------|--------|-------|
| `nativeParseXmppOffer(CallOfferInfo[], ...)` | `preprocess_call_offer` (`AbstractC24816AmW`) | يحلل offer دون بدء مكالمة؛ حقول `CallOfferInfo`: callId، fromJid، groupJid، callLinkToken، isVideoCall، isAudioChat، isJoinableCall، isOfferExpired، isCallEnded، silenceReason، groupPhash، participantHash، callGroupInfo |
| `nativeHandleIncomingXmppOffer` | `C28120CKj` | يبدأ معالجة المكالمة الواردة |
| `nativeHandleIncomingSignalingXmpp` / `...Ack(from, type, errorCode, children, ..)` / `...Receipt` | `RunnableC29343CoU` (الرسالة 192) | كل إجراء ليس offer، وإقرارات الـ stanzas الخاصة، وإيصالات المكالمة (القيمة المعادة 70004 تُسجَّل كإقرار تالف) |
| `peekIncomingOffer`، `handleIncomingTerminatePush` | مسار push | قرار ما قبل الرنين، terminate يُسلَّم عبر push |
| `handleIncomingSignalingHttp(callId, bytes, ..)` | استجابة HTTP لـ TEE | ناقل بديل (11.3) |

---

## 3. الغلاف والإقرارات والإيصالات

### 3.1 `<call>` الصادر (found، `HandlerThreadC21920sG` الحالة 206)

```
<call to="<jid>" id="<stanza id>">
  <ACTION .../>                      exactly one child
</call>
```

يجب أن يجتاز `to` الدالة `C0DZ.A0R` (مستخدم وجهاز وبضعة أنواع JID أخرى؛ وإلا يرمي `C27410BtV` الخطأ `CallStanza:Wrong jid type`). يأتي id الخاص بالـ stanza من مولّد المعرفات المشترك. سطر السجل `WriterThread/write/call-stanza-<tag>`.

### 3.2 `<call>` الوارد (found، `C40641lA`)

| السمة | المعالجة |
|-----------|----------|
| `from` | يجب أن يكون JID صالحًا، وإلا `CallStanza from invalid jid`؛ ويُحوَّل JID المستخدم إلى جهازه الأساسي |
| `id` | id الـ stanza، يُستخدم في الإقرار |
| `t` | ثوانٍ، تُضرب في 1000 |
| `e` | ثوانٍ صحيحة، تُضرب في 1000 وتُمرَّر إلى المحرك بجانب `t` (المعنى الدقيق غير محلول؛ inferred أنه مدخل عمر / انتهاء صلاحية offer) |
| `offline` | عدد صحيح؛ وجوده يدل على التسليم من طابور offline |
| `notify`، `platform`، `version` | تُمرَّر كما هي (اسم push للمتصل، المنصة، إصدار التطبيق) |
| `participant` | JID جهاز المرسل في سياقات المجموعات؛ والقيمة المشوهة ترجع إلى `from` |
| `sender_lid` | يُقرأ عندما يكون `from` بنطاق LID |
| الابن `call-creator` | JID الجهاز (مطلوب لمنطق ما ليس offer) |
| الابن `call-id` | مطلوب؛ عدا الوسمين `reminder` و`bcall_*` اللذين يحصلان على call id فارغ |
| سمات أخرى | `caller_pn` (JID جهاز برقم الهاتف)، `username`، `caller_country_code`؛ تُقرأ فقط عندما يكون المنشئ LID والوسم ليس `offer` |

إذا كان `to` و`call-creator` في نطاقي عنونة مختلفين (أحدهما LID والآخر رقم هاتف) يسجّل العميل `CallStanzaHandler/call-mixed-domain/...` ويبلّغ المقياس `CallMixedDomainStanza` ثم يواصل (found). النطاقات المختلطة مسموح بها وليست مرفوضة.

### 3.3 الإقرارات (Acks)

| الحالة | السلوك (found) |
|------|------------------|
| الوسم ليس ضمن {offer، accept، reject، enc_rekey، terminate} | ترسل Java إقرارًا فورًا: `<ack class="call" type="<tag>" id to [participant]/>` (`AbstractC47181wT.A01`) |
| الوسم ضمن تلك المجموعة | لا إقرار فوري من Java؛ تذهب العقدة إلى مسار منفصل بانتظار الإقرار (`C36591ch.A0G`)؛ الدلالات غير محلولة |
| إقرار لـ stanza خاص | `nativeHandleIncomingSignalingXmppAck(from, type, errorCode, children, ...)`. أنواع الإقرار الظاهرة في Java: offer (يحمل بيانات relay، القسم 8)، accept، link_join، link_query، lobby؛ ويعالج native أيضًا link_create، link_edit، remove، remove_user، heartbeat، screen_share، add_extension، remove_extension، relaylatency، حالة الفيديو، waiting_room_* |
| إقرار offer بالخطأ 435 | إجراء إضافي يُجدوَل بعد الإقرار (الغرض غير محلول) |
| تسليم offer / accept | تنتظر Java إقرار التسليم من chatd مع مهلة (الأعلام 9257، 9431)؛ عند انتهاء المهلة يُسقط الـ stanza ويُسجَّل `Call stanza delivery timed out` |

### 3.4 رموز القاموس (found، `AbstractC40911lb`)

بايت واحد (`A00`): `call` 97، `call-id` 101، `call-creator` 68، `terminate` 208، `relaylatency` 70، `video` 86، `audio` 158، `capability` 177، `device-identity` 227، `privacy` 223، `te` 212، `te2` 198، `token` 194، `key` 155، `participant` 5، `user` 14، `remove` 172، `notify` 24، `registration` 170، `attribute_padding` 229، `relay_id` 130، `token_id` 143. القاموس الثانوي 0 (`A01[0]`): `offer` 28، `accept` 97، `preaccept` 18، `transport` 44، `mute_v2` 253، `group_info` 170، `group_update` 99، `net` 103، `medium` 36، `encopt` 21، `keygen` 26، `voip_settings` 10، `relay` 116، `joinable` 75، `heartbeat` 6، `transaction-id` 62، `uuid` 132، `self_pid` 71، `peer_pid` 76، `metadata` 118، `uncompressed` 20، `rate` 29، `dec` 73، `screen_width` 5، `reason` 46. الثانوي 1: `reject` 0، `enc_rekey` 205، `e` 235.

غير موجودة في أي قاموس في هذا البناء (سلاسل عادية على السلك): `lobby`، `flowcontrol`، `screen_share`، `link_*`، `peer_state`، `interruption`، `reminder`، `raise_hand`، `waiting_room_*`، `hbh_key`، `auth_token`، `lightweight`، `silence`، `scheduled-id`، `group-jid`، `link-token`، `caller_pn`، و`enc`.

---

## 4. تصنيف الإجراءات

الوسوم الواردة التي يوزّعها مفكّك native (found، قائمة سلاسل في `call_control`): `offer`، `accept`، `preaccept`، `reject`، `terminate`، `transport`، `relaylatency`، `enc_rekey`، `notify`، `flowcontrol`، `interruption`، `group_update`، `mute_v2`، `screen_share`، `raise_hand`، `reconfigure_bot`، `user_action`، `ready`، `relay_info_update`، `tos`، `screen`، `switchable`، `add_extension`، `waiting_room_update`، إضافة إلى `receipt`. الإقرارات المحلَّلة: offer، accept، حالة الفيديو، relaylatency، link_create / edit / query / join، lobby، heartbeat، remove، remove_user، screen_share، add_extension، remove_extension، waiting_room toggle / admit / deny / leave.

| الوسم | الاتجاه (found) | الغرض |
|-----|-------------------|---------|
| `offer` | صادر / وارد | بدء مكالمة (القسم 5)؛ في الوارد: أيضًا offers لمكالمات منتهية بالفعل مع `is_call_ended` و`terminate_hint` |
| `preaccept` | صادر / وارد | جهاز المستدعى عليه يرن / جاهز؛ حالة المحرك `PRE_ACCEPT_RECEIVED`، الحدث `preacceptReceived` |
| `accept` | صادر / وارد | المستدعى عليه يقبل؛ يحمل معاملات الوسائط وشهادة (سلاسل native `error parse voip params for accept`، `error parsing certificate for accept`) |
| `reject` | صادر / وارد | المستدعى عليه يرفض؛ سلاسل الأسباب في القسم 14.2 |
| `terminate` | صادر / وارد | إنهاء المكالمة؛ معرّف المعاملة و`call_summary` (القسم 14.3) |
| `transport` | صادر / وارد | المرشحون، بيانات اعتماد ICE، الشهادة، الصحة (القسم 8.5) |
| `relaylatency` | صادر / وارد | زمن relay المقاس (القسم 8.4)؛ له إقرار خاص به |
| `enc_rekey` | صادر / وارد | إعادة مشاركة مفتاح المكالمة (القسم 6.4) |
| `video` (الحالة) | صادر / وارد | تشغيل / إيقاف / ترقية الفيديو؛ قيم `kVideoState*` (القسم 13)؛ الإقرار يحمل معلومات relay |
| `notify`، `peer_state`، `flowcontrol`، `interruption`، `ready`، `heartbeat` | صادر / وارد | حالة داخل المكالمة: إشعارات النظير، صحة الشبكة، التحكم في التدفق، الانقطاعات، heartbeat المجموعة |
| `mute_v2`، `raise_hand`، `user_action`، `tos`، `reconfigure_bot` | صادر / وارد | طلب كتم في المكالمات الجماعية، رفع اليد، إجراءات المستخدم، TOS للمكالمة الجماعية، إعادة تهيئة البوت (السمة `req_id`) |
| `group_info`، `group_update` | وارد (ابن لـ offer / ack / update) | قائمة المشاركين (القسم 9) |
| `lobby` | صادر / وارد | استعلام / حالة ردهة المكالمة الجماعية؛ إقراره يحمل معلومات المجموعة |
| `screen`، `screen_share`، `switchable` | صادر / وارد | حالة مشاركة الشاشة؛ تبديل الجهاز (`switch_info`، `root_call_id`، `root_call_creator`، `peer_active_device`) |
| `add_extension`، `remove_extension` | صادر / وارد | إضافة نقطة وسائط ("extension") إلى مكالمة (القسم 9.4) |
| `remove`، `remove_user`، `cancel_offer` | صادر | إزالة مشاركين؛ إلغاء offer لمشاركين محددين |
| `link_create`، `link_edit`، `link_query`، `link_join` | صادر | روابط المكالمات (القسم 10) |
| `waiting_room_toggle`، `_admit`، `_deny`، `_leave`، `_update` | صادر / وارد | غرفة انتظار مكالمة الرابط (القسم 10.3) |
| `reminder`، `bcall_*` | وارد | تذكيرات الخادم؛ عائلة مكالمات الأعمال (القسم 11) |
| `dtmf`، `duration`، `connect_stat`، `group_call_duration`، `group_call_tos_accepted` | صادر | مُسلسِلات موجودة في المحرك |

الوسوم الظاهرة في Java ضمن `sendCallStanza` (found): `offer`، `accept`، `reject`، `terminate`، `video`، `enc_rekey`، `lobby`، `link_join`، `link_query`، `link_create`؛ وكل وسم آخر يسلك مسار الإرسال الافتراضي.

جدول معرّفات الرسائل الرقمية (85 نوعًا)، وتقسيم الآلية (ابن / إقرار / إيصال / داخلي)، وأطوال الترويسة الثابتة: غير موجودة في هذا البناء. يعرض المحرك الوسوم والمُسلسِلات لكل وسم، وليس تعدادًا للمعرّفات مرئيًا في السلاسل. اعتبر أي جدول معرّفات unknown في Android.

---

## 5. Offer

### 5.1 البناء والإرسال (found)

يجعل `startCall(...)` المحرك يُصدر `sendCallStanza(peer, callId, offerNode)`. في Java:

1. يخزّن `sendOfferStanza` معرّف الـ stanza (`outgoingCallOfferKey`)، وينتظر ما دامت مهمة pre-key لأي جهاز وجهة معلّقة، ثم يشفّر مفتاح المكالمة لكل جهاز على خيط عامل (`getBulkEncryptedE2EKeys`، القسم 6.1).
2. تُكتب النتيجة إما بالصيغة الجديدة (`<destination><to jid><enc/></to>...</destination>`، عبر `AbstractC33466EhY.A08`) أو بالصيغة القديمة (ابن `<enc>` واحد، صالح لجهاز واحد فقط؛ `cannot have multiple encrypted messages in old format!`).
3. إذا حصل أي جهاز على `pkmsg` يُلحَق `<device-identity>` (بايتات `adv_signed_identity` من تفضيلات الجهاز المرافق)؛ يحدث هذا فقط عندما يجتاز جهاز الذات `BRD()` (معرّف جهاز التسجيل غير صفري، أي جهاز مرافق؛ inferred).
4. يضع `CIX.A02` الـ stanza `<call>` في الطابور؛ يحدّ العلم **9257** (ms) انتظار التسليم.
5. بعد الإرسال يُجدوَل IQ ping للمكالمة (العلم **30890**، التأخير **30891** ms الافتراضي 3000، المحاولات **32651**)؛ إذا كان الاتصال منقطعًا يعيد العميل الاتصال، ما لم تعد المكالمة في الحالة `CALLING`.
6. إذا تعذّر تشفير الوجهات يبقى offer معلّقًا كـ `pendingCallOfferStanza` ويُرسل لاحقًا (`maybeSendPendingOffer` عند انتهاء مهمة pre-key، `sendPendingCallOfferStanza` عند terminate). ويُسقط `preSendTerminate` الـ offer غير المُقَرّ من طابور إعادة المحاولة قبل خروج terminate.

### 5.2 الأبناء والسمات

| العنصر | المصدر | السمات / المحتوى |
|---------|--------|----------------------|
| `<offer>` | إرسال | `call-id`، `call-creator` (JID الجهاز)؛ استقبال: `caller_pn`، `username`، `caller_country_code`، `group-jid`، `scheduled-id`، `joinable`، `lightweight` (`1` = رنين مجموعة خفيف / صوتي فقط)، `rering_ts`، `is_call_ended`، `type` |
| `<audio>` (يتكرر) | إرسال | `enc` (codec)، `rate` (معدل العينة)؛ `enc` و`rate` رموز قاموس |
| `<video>` | إرسال | `enc`، `dec`، `device_orientation`، `screen_width`، `screen_height`؛ السلاسل الظاهرة في المحرك: `h.264`، `vp8`، `vp8/h.264`؛ السمة `fps` موجودة أيضًا كسلسلة (سمة فيديو inferred) |
| `<net>` | إرسال | `medium` (نوع الشبكة)، ثم لاحقًا `health_status` في transport |
| `<capability>` | إرسال | `ver` + قناع بتات غير شفاف (`pjmedia_voip_capabilities_*`: الإصدار، `bit_mask_length`)؛ سلسلة `vid_dec` لكل جهاز تسرد codecs الفيديو القابلة لفك الترميز (`vid_codec_capability_str_to_bitmask`) |
| `<encopt>` | إرسال | `keygen` = إصدار توليد المفتاح؛ يرفض المحرك القيم الأخرى (`Unsupported keygen ver`)؛ الإصداران 2 و3 موجودان (القسم 6.4) |
| `<destination>` / `<to jid>` / `<enc>` | إرسال | مفتاح المكالمة المشفّر لكل جهاز (القسم 6.1)؛ قد يحمل `<to>` السمات `peer_recipient_lid`، `peer_recipient_pn`، `peer_recipient_username`، `eph_setting` |
| `<tctoken>` | إرسال | داخل `<to>`، مرة واحدة على الأكثر لكل مستخدم، عندما يكون العلم **20605** مفعّلًا وعدد المستخدمين الحاملين له أقل من **20606**؛ من عائلة الـ token نفسها في [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `<device-identity>` | إرسال | بايتات هوية ADV الموقّعة، انظر 5.1 الخطوة 3 |
| `<privacy>` | استقبال | token الخصوصية (اسم الـ token موجود في القاموس)؛ المحتوى لم يُتتبع |
| `<relay>` | استقبال / ack | قائمة relay (القسم 8) |
| `<voip_settings>` | استقبال / ack | معاملات المحرك المقدَّمة من الخادم؛ السمة `uncompressed`؛ الحمولات المضغوطة مرفوضة في مسار واحد (`unexpected compressed voip params`) و`zlib inflate` مربوطة (صيغة الضغط inferred) |
| `<metadata>` | استقبال | سمات دلو اختبار A/B للنظير (`peer_abtest_bucket`، `peer_abtest_bucket_id_list`) |
| `<silence reason>` | استقبال | offer صامت (بلا رنين)؛ `BQU.A02`؛ أعداد الأسباب `kOfferSilenceReason*` (القسم 13) |
| `<group_info>` | استقبال | قائمة مشاركي مكالمة جماعية (القسم 9) |
| `<terminate_hint>` / `<call_summary>` | استقبال | offer لمكالمة انتهت بالفعل (`is_call_ended=1`): `terminate_reason`، معرّف المعاملة، الملخص |
| `<link_info>`، `<waiting_room>`، `<bot>`، معلومات extension | استقبال | بيانات الرابط وغرفة الانتظار والبوت وextension |

القيم البايتية الدقيقة لـ `<capability>` ولأكواد `net medium` لم تُستخرج من هذا البناء (يُقتبس أحيانًا قناع من 7 بايت `01 05 F7 09 E4 BB 13` لعملاء الويب؛ وهو غير موجود كحرفي متصل في مكتبة Android، لذا اعتبر قيمة Android unknown). يضم المحرك الـ codecs التي تسميها سلاسله: Opus إضافة إلى codec داخلي منخفض معدل البت ("mlow"، بتأطير Opus)، وOpenH264، وVP8، وAV1 (`wzav1`)، وHEVC عبر MediaCodec.

### 5.3 مسار الاستقبال (found)

1. يبني `CallStanzaHandler` الكائن `BQU`؛ المقياس `CallStanzaHandler/handleStanza tag=... callId=...`؛ وتُرسل الرسالة 192 إلى الموزّع.
2. بالنسبة لـ offer يشغّل `preprocess_call_offer` الدالة `nativeParseXmppOffer`؛ القيمة غير الصفرية تُسقط الـ stanza. الـ offers المنتهية أو المنتهية صلاحيتها لا ترن.
3. يفك `C83.A00` تشفير `<enc>` (القسم 6.2)، ثم تبدأ `nativeHandleIncomingXmppOffer` المكالمة؛ الحالة `RECEIVED_CALL`.
4. `peekIncomingOffer` (فحص مسبق مدفوع بـ push) يتجاهل الـ offers الصامتة، وoffers المجموعات (وجود `group_info`)، وoffers ذات `is_call_ended=1`، وoffers 1:1 بلا `<enc>`، والـ offers أثناء انشغال الهاتف؛ العلم **4217** البت 1 يفعّل peeks الصوت، والبت 2 peeks الفيديو.
5. يُنهي `terminate` لاحق أو push `handleIncomingTerminatePush` عملية peek.

---

## 6. مفتاح المكالمة وتشفيره

### 6.1 الصادر (found، `getBulkEncryptedE2EKeys`)

يسلّم المحرك خريطة من JID الجهاز إلى بايتات مفتاح المكالمة الخام. لكل جهاز بلا مهمة pre-key معلّقة يبني العميل protobuf من نوع `Message` ويشفّره عبر Signal بالجلسة الثنائية الموجودة (`C83` / `CallableC29363Coo`):

| حقل Message.Call | الرقم | النوع | يُضبط عندما |
|--------------------|--------|------|----------|
| `callKey` | **1** | bytes | دائمًا (32 بايت خام) |
| `conversionSource` / `conversionData` / `conversionDelaySeconds` | **2** / **3** / **4** | string / bytes / uint32 | بيانات CTWA موجودة |
| `ctwaSignals` / `ctwaPayload` | **5** / **6** | string / bytes | بيانات CTWA موجودة |
| `contextInfo` | **7** | ContextInfo | علم CTWA (`externalAdReply.adType` مضبوط على قيمة ثابتة) |
| `nativeFlowCallButtonPayload` | **8** | string | بدأت المكالمة من زر native-flow |
| `deeplinkPayload` | **9** | string | بدأت المكالمة من deeplink |
| `messageContextInfo` | **10** | MessageContextInfo | إثراء لكل نظير بواسطة `AbstractC30999De0` (المحتوى لم يُتتبع) |
| `callEntryPoint` | **11** | uint32 | العلم **24935**، فقط في fanout الأولي (`i == 0`) |
| `callReason` | **12** | string | موجود في proto، غير مضبوط في هذا المسار |

`Message.call` هو الحقل **10** في `Message` (`C30628DTw`)، والصنف `Message.Call` = `C25827BCl`. بالنسبة لـ offer الأولي يضيف العلم **520** سياق إسناد الإعلان من محلّل CTWA (`C35832FfR`؛ inferred). يعمل fanout مع `i == 0` لـ offers و`i == 1` لعمليات rekey. التشفير حاجب مع مسار إلغاء؛ والحجب فوق 5000 ms يسجّل `voip_e2e_encryption_blocked`.

الصيغة السلكية لجهاز واحد (found، `AbstractC33466EhY.A03/A09`): `<enc v="<version>" type="msg|pkmsg|skmsg|frskmsg|msmsg" [count="<retry>"] [mediatype] [session_type="pq"] [bucket]>CIPHERTEXT</enc>`. تدل `session_type="pq"` على جلسة Signal ما بعد الكمّية؛ ويُحذف `count` عندما يكون 0. مفاتيح المكالمة ليست أبدًا رسائل sender-key جماعية في هذا المسار (النوع `skmsg` مقبول في الدالة المساعدة لكن لا يُنتجه أي مسار مكالمة؛ inferred).

أجهزة extension (بادئة مستخدم JID هي `01`) تستخدم `sendReKeyToExtension`: تُعالَج حزمة prekey مخزّنة مسبقًا، ويُشفَّر المفتاح كـ `pkmsg` مع `v="2"` (found).

### 6.2 الوارد (found، `C83.A00`)

| الخطوة | التفصيل |
|------|--------|
| الأبناء المقروءة | `registration` (يجب أن يكون 4 بايت؛ معرّف تسجيل Signal، يُستخدم في إعادة المحاولة)، `device-identity`، `enc` |
| التكرارات | `<enc>` ثانٍ يُسقط (`duplicate <enc>`) |
| عدّاد إعادة المحاولة | `count` على `<enc>`؛ القيمة المفقودة تُجهض (`invalid retry count`) |
| النوع | `msg` 0 أو `pkmsg` 1 مقبولان؛ الأرقام الأخرى تسجّل `unrecognized ciphertext type` |
| فك التشفير | فك تشفير Signal الثنائي (تُعالج رسالة pre-key بهوية جهاز المرسل)؛ تُحلَّل الحمولة كـ `Message`، ويُؤخذ `call.callKey`؛ ويُسجَّل `ExternalAdReplyInfo.adType` الخاص بـ CAWC |
| النتيجة | يُستبدل `<enc>` بعقدة `<enc>` عادية تحمل بايتات مفتاح المكالمة للمحرك |
| الفشل | الحدث `rejectedDecryptionFailure`، ويعيد `onPeerE2EDecryptionFailed` محاولة إعداد الجلسة (جلب pre-key جديد عندما يتساوى معرّف التسجيل ويتكرر المفتاح الأساسي)؛ ويُرسل سبب reject وهو `enc` عندما يتعذر فك تشفير المكالمة |

يغيّر العلم **24063** مسار نوع الجلسة المستخدم لنصوص مشفّرة من نوع hosted (inferred من الشرط `c33281EeX.A04`).

### 6.3 إعادة المحاولة

تجعل `sendOfferRetryRequest(device)` المحرك يعيد إرسال offer (`resendOfferOnDecryptionFailure`)؛ وتكرر `sendPendingRekeyRequest` طلب rekey ما دام بايت إعادة المحاولة المخزَّن ضمن 0..4. لذا يتراوح `count` بين 0 و4 (found، `sendPendingRekeyRequest`).

### 6.4 `enc_rekey`: ثلاث صيغ

| الصيغة | الدليل | المحتوى |
|-------|----------|---------|
| v2 أحادي الإرسال | `sendReKeyStanza` (Java) | يُصدر المحرك `<enc_rekey call-id call-creator transaction-id><enc count=N>RAW KEY</enc></enc_rekey>`؛ تستبدل Java الابن بـ `<enc>` المشفّر عبر Signal للجهاز الهدف (found) |
| v2 fanout | `sendReKeyFanoutStanza` | الهدف مجموعة؛ الابن `<destination><to jid><enc/></to>...`؛ كل إدخال يُشفَّر بشكل منفصل (found) |
| v3 | سلاسل native `handle_enc_rekey_v3`، `make_and_send_rekey_v3`، `ext_rekey: ...` | الحمولة protobuf بـ `wa.voip.RekeyKeyEntry` متكررة (نوع المفتاح + المفتاح)؛ للمفاتيح لكل نوع طول ثابت (`key type %d has unexpected length`)؛ يُختار عندما يكون keygen هو 3؛ يتطلب دعم extension (`kCallExtensionMV1`)؛ يُسجَّل الانتقال من v3 إلى v2 |

قواعد ظاهرة في السلاسل: تحمل عمليات rekey معرّف معاملة؛ تُتجاهل المعرّفات المبكرة أو القديمة أو المتساوية (`ignore old rekey msg with transaction id`)؛ في مكالمة واحد-لواحد يُتجاهل `enc_rekey` الوارد (`ignore rekey msg in one to one call`)؛ يطلب `request_keys` من المنشئ أو من extension إعادة إرسال المفاتيح (v3 فقط؛ `request_keys with unexpected keygen` يُتجاهل). أي جانب يبدأ rekey في مكالمة جماعية، والمُحفِّز الدقيق، غير محلولين.

---

## 7. اشتقاق مفتاح الوسائط

### 7.1 ردود نداء Java (found)

| رد النداء | الحساب |
|----------|-------------|
| `generateE2EKeysV2(callKey[32], out[46], info)` | HKDF-SHA256، salt = 32 بايت أصفار، IKM = مفتاح المكالمة، info = سلسلة `info` بترميز UTF-8 يوفرها المحرك، 46 بايت ناتج (`E2E_EXTENDED_V2_KEY_LENGTH`) |
| `hkdfSha256(salt, ikm, info, out)` | HKDF-SHA256 عام (الوسيط الأول salt، الثاني IKM، الثالث info؛ طول الناتج = `out.length`) |
| `getSecureSsrc(ikm, info, salt[4], out[4])` | HKDF-SHA256 إلى 4 بايت (`SECURE_SSRC_LENGTH`) |
| `hmacSha256(key, data, out[32])` | HMAC-SHA256 |
| `generateRandomBytes(out)` | `SecureRandom` (مصدر مفتاح المكالمة ذي 32 بايت؛ inferred) |

### 7.2 التسميات والسياقات في المحرك (سلاسل found، الدور inferred)

`e2e sframe key`، `hbh srtp key`، `uplink hbh srtcp key`، `downlink hbh srtcp key`، `warp auth key`؛ الدوال `derive_sframe_key`، `derive_hbh_srtp_key`، `derive_and_update_warp_mi_keys`، `derive_extension_per_media_key`؛ خانات المفاتيح `owner_e2e_key`، `extension_audio_key`، `extension_video_key`، `extension_appdata_key`.

| المفتاح | المصدر (inferred) | يحمي |
|-----|-------------------|----------|
| مادة E2E SRTP | ناتج `generateE2EKeysV2` (46 بايت)، لكل مشارك | الوسائط بين النقطتين الطرفيتين (1:1) |
| مفتاح SFrame | التسمية `e2e sframe key` | تشفير الإطارات في المكالمات الجماعية / SFU وقناة البيانات قفزة-بقفزة (`wa_sframe_encrypt`، `sframe_keyprovider_set_chainkey`) |
| hop-by-hop SRTP / SRTCP | `hbh_key` المقدَّم من relay (القسم 8.2) مع تسميات `hbh ...` | ضلع العميل إلى relay فقط |
| مفتاح WARP MI | التسمية `warp auth key` | وسم سلامة الرسالة لحزم WARP (`warp_mi_tag_len`) |

تخطيطات المفاتيح (أي من البايتات الـ 46 هو مفتاح أو salt، لكل اتجاه)، ومحتوى سلسلة `info`، وسلاسل HKDF الدقيقة لـ SFrame / قفزة-بقفزة لم تُستخرج: المستدعون موجودون في كود native تعذّر فك تجميعه. استخدام JID مؤهَّل بالجهاز كـ `info` أمر معقول لكنه غير متحقق منه (**unknown**).

---

## 8. Relay والنقل ومسار الوسائط

### 8.1 ما يستقبله العميل

تصل بيانات relay في إقرار offer (المتصل؛ `error during parsing relay info`، `Failed to parse relay info in offer ack`)، وفي offer نفسه (المستدعى عليه)، ولاحقًا في `relay_info_update` وفي إقرار تغيير حالة `video` (found).

### 8.2 قواعد `<relay>` (found، سلاسل `fill_relay_info`)

| البند | الاسم | ملاحظات |
|------|------|-------|
| سمات relay | `uuid`، `self_participant_uuid`، `conn_id`، `medium`، `warp_mi_tag_len`، `prefer_relay`، `prefer_ipv6`، `peer_dl`، `smart_transport_signal`، `attribute_padding` | لكل مجموعة relay |
| tokens | قائمة `<token>` (`token_id`)، مطلوب واحد على الأقل (`relay_token_list.num_tokens < 1`) | بيانات اعتماد relay؛ تُنسخ القائمة إلى طلب allocate |
| auth tokens | `<auth_token>` (`auth_token_id`) | يُستخدم بدل token عندما يكون المعرّف ضمن النطاق؛ وإلا "falling back to relay token" |
| المفتاح | `<key>` | مادة كلمة مرور relay |
| `hbh_key` | ابن بايتات خام أو base64 | مصدر مفتاح قفزة-بقفزة؛ يُفحص الحجم (`HBH Key of unexpected size`، "though warp_mi_tag_len = ...") |
| نقاط النهاية | `<te>` أو `<te2>` | لا الاثنان معًا (`can not receive both te and te2 endpoints`)؛ بايتات العنوان IPv4 أو IPv6 (`endpoint too short for an IPv6 address`)؛ العنوان الفارغ مرفوض |
| لكل نقطة نهاية | `relay_id`، `relay_name` (يُقتطع إن كان طويلًا)، `domain_name`، `latency`، `c2r_rtt`، `ul_bw`، `dl_bw`، `is_favored` | `latency` يغذّي اختيار relay |
| المشاركون | `<participant pid jid>` | يربط معرّفات المشاركين المستخدمة في حزم WARP / SFU |

تطبع سلاسل السجل عناوين relay عبر عنصر نائب `[MetaServiceIP]`، لذا تُعامل عناوين relay كعناوين IP للخدمة.

### 8.3 اختيار relay (سلاسل found، المنطق inferred)

1. يرتبط العميل بـ relays المعروضة (`wa_transport_p2p_start_relay_binds`؛ طلبات bind / alloc بنمط STUN، `wa_stun_*`، معرّفات المعاملة `tid=0x...`؛ يحتاج bind وunbind إلى سلامة الرسالة).
2. يُقاس الزمن بطلبات ping لكل relay (`Ping request sent to relay N`)، ومسبار TCP (`wa_transport_tcp_prober_*`) وأزمنة ذهاب وإياب allocate؛ ويصبح الأفضل "relay المنتخب" (`Elected relay idx=...`، `wa_transport_get_elected_relay_approximate_e2e_rtt`)؛ ويبدّل حَكَم (`wa_transport_path_arbiter_*`) المسارات، ويفرض `prefer_relay` استخدام relay.
3. يُسجَّل عنوان server reflexive المتعلَّم من استجابة allocate (`Server reflexive addr`).
4. تُجرَّب نقطة-إلى-نقطة بالتوازي عبر أزواج المرشحين (`p2p add_cand_pair`، `e2e bind probe`)؛ ويبقى relay كاحتياط.

### 8.4 `relaylatency` (found)

المُسلسِلات والمعالجات: `serialize_relay_latency`، `send_or_enqueue_relay_latency`، `handle_relay_latency`، `unpack_and_apply_relay_latency`، مع تجميع على دفعات (`prepare_batched_relay_latencies`)، وتحليل الإقرار `relaylatency ack: call_id is empty / has invalid type`. يبلّغ الـ stanza النظير بـ RTT المقاس لدى المرسل لكل فهرس relay، ويطبّقه النظير (`apply_relay_latencies`، العتبات `Ignored higher relay latency ...`). يُتخطى الزمن في offers المكالمات الجماعية (`Skip relay latency at call offer in group calls`).

### 8.5 `transport` (سلاسل found)

السمات والأبناء: `transport-message-type`، `p2p-cand-round` (إعادة التشغيل تزيد الجولة وتمسح المرشحين البعيدين)، `ice-ufrag`، `ice-pwd`، `<certificate algorithm fingerprint>` (`cert_algorithm`، `cert_fingerprint`)، `health_status`، إدخالات المرشحين (العنوان، الأولوية). تدل السلسلة `Web P2P: skipping type 13 send` على أن نوع الرسالة 13 ينتمي إلى تبادل ICE / DTLS الخاص بـ web-P2P. أرقام الأنواع الفرعية الأخرى لم تُستخرج (**unknown**).

### 8.6 مساران للوسائط

| الجانب | مسار relay الخاص بـ WhatsApp (الافتراضي) | مسار web-P2P |
|--------|-------------------------------|--------------|
| الإعداد | relay allocate / bind (بنمط STUN)، tokens من الإشارات | بيانات اعتماد ICE وبصمة شهادة DTLS تُتبادل في `transport`؛ `wa_ice_transport`، `CreateDtlsTransport` |
| شكل الحزمة | حزم WhatsApp بحمولة RTP ("WARP"، وسم سلامة `warp_mi`، piggyback، FEC، `warp_rtx`) | RTP عبر DTLS-SRTP |
| مفتاح القفزة | `hbh_key` الخاص بـ relay (SRTP / SRTCP قفزة-بقفزة، وDTLS قفزة-بقفزة إلى relay `hbh_dtls_handshake_*`) | مشتق من DTLS |
| E2E | E2E SRTP في 1:1، وSFrame في المجموعات (SFU) | SRTP |
| الغرض | مكالمات عادية من تطبيق إلى تطبيق | التشغيل البيني مع عميل الويب (`set_peer_is_web`، `handle_transport_web_p2p`)؛ inferred |
| مكدس TLS | mbedTLS مربوط ساكنًا (`mbedtls_ssl_*`، `mbedtls_gcm_*`، `mbedtls_hkdf`) | نفسه |

تستخدم المكالمات الجماعية SFU مع اشتراكات (`RxSubscriptions`، `SenderSubscriptions`، protobufs `wa.voip.*` داخل قناة البيانات) بدل مسارات لكل نظير؛ ويعمل تقدير عرض النطاق لكل مسار (`wa_warp_sfu_*`، "one side BWE").

---

## 9. المكالمات الجماعية

### 9.1 `group_info` (found، سلاسل `shared_elements/group.rs`)

| البند | الاسم | ملاحظات |
|------|------|-------|
| السمات | `connected-limit`، `phash`، `transaction-id`، `media`، `joinable` | hash القائمة ومعرّف الترتيب؛ `group_info has invalid connected_limit` |
| الأعضاء | `<user jid [user_pn push_name guest_name account_kind state ..]>` مع أبناء `<device jid ..>`، أو `<participant jid pid>`؛ `<bot jid>` | وجود `<user>` و`<participant>` معًا خطأ |
| لكل مستخدم | `state`، `pid`، `capability` (`ver`)، `rekey`، `terminated`، `connected`، `country_code`، `reason` | قوائم الأجهزة مطلوبة للمستخدمين غير المرفوضين بـ nack |
| extensions | `extension_creator`، `ext_creator_identity_key_sig`، `extension_id`، `hn_video`، `gen`، `cohost`، `scope` | بيانات extension / co-host |

### 9.2 السلوك

- الحد `Voip.kMaxSupportedGroupCallParticipants` = 64 (found)؛ ينهي المحرك مكالمة يتجاوز تحديثها الحد الأقصى.
- يحمل `group_update` وterminate المكالمة الجماعية معرّفات معاملة؛ تُتجاهل المتقادمة أو غير المرتبة؛ `kInitialGroupTransactionId` = -1 (found).
- لا يحمل offer الجماعي مفتاح مكالمة لكل جهاز؛ تُعاد مشاركة المفاتيح لكل جهاز بـ `enc_rekey` (inferred من `sendReKeyFanoutStanza`).
- إجراءات الرنين والقائمة: `invite`، `inviteToGroupCall`، `cancelInviteToGroupCall`، إعادة الرنين (`rering_ts`، `make_and_send_cancel_offer_for_participants`)، `sendRaiseHand`، `sendMutePeerRequestInGroupCall`، `sendRemoveRequest`؛ و`lobby` هي خطوة الانضمام لمكالمة جماعية جارية (`joinOngoingCall`).
- Extensions: يربط `add_extension` / `remove_extension` نقطة وسائط ثانية بالمكالمة (`wa_call_extension_jid_*`، مفاتيح المالك وextension في 7.2، `kCallExtensionMV1`؛ تعامل Java JIDs الخاصة بـ extension ذات بادئة المستخدم `01` معاملة خاصة، 6.1). فئة الجهاز غير محلولة (inferred: جهاز قابل للارتداء مقترن، إذ يشحن التطبيق `libsmartglasses-bundle.so` و`Voip.sendWearableAttribution`).

---

## 10. روابط المكالمات وغرفة الانتظار والمكالمات المجدولة

### 10.1 الروابط (found)

| البند | القيمة |
|------|-------|
| URL | `https://call.whatsapp.com/{voice|video}/{token}`؛ مضيف manifest هو `call.whatsapp.com` |
| طول token | `Voip.kCallLinkTokenLength` = 22 |
| الإنشاء | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` (السجل `actionCreateCallLink` / `actionCreateCallLinkForEvent`)؛ يرفض native الدالة `wa_call_link_create_v2` وقت بدء غير صالح |
| التعديل / المعاينة | `editCallLink(token, ..., startTime, int)`، `previewCallLink`، `queryCallLinkForLinkEdit`؛ الـ stanzas `link_edit`، `link_query` |
| الانضمام | يرسل `joinCallLink` الـ `link_join`؛ يحمل الإقرار `LinkJoinAck` الحقول `call-creator`، `group_info`، `voip_settings`، معلومات الرابط |
| حالات الرابط | `kCallLinkState`: None 0، QuerySent 1، QueryAcked 2، JoinSent 3، JoinAcked 4 |
| `CallLinkInfo` | creatorJid، token، videoEnabled، eventStartTsSec، isGuestEligible، linkState، waitingRoomState، self |
| أحداث nack | `linkCreateNacked`، `linkQueryNacked`، `linkJoinNacked`، `linkEditNacked` مع كود خطأ الإقرار |

تُوجَّه stanzas الروابط إلى JID بنطاق المكالمات (يسرد محلل JID في Rust القيمتين `callDomainJID` و`callJID`؛ ونوع JID المقبول في `C0DZ.A0R` المقابل لذلك لم يُحل).

### 10.2 مكالمات الأحداث (المجدولة)

مكالمة الحدث هي رابط مكالمة أُنشئ بـ `eventStartTimeSec` غير صفري (found). يحمل offer للمكالمة المجدولة `scheduled-id` (found في المحلل). تحمل `Message` رسالتي دردشة:

| حقل Message | الرقم | النوع | المحتوى (found) |
|---------------|--------|------|-----------------|
| `scheduledCallCreationMessage` | **61** | ScheduledCallCreationMessage | `scheduledTimestampMs` 1، `callType` 2 (UNKNOWN 0، VOICE 1، VIDEO 2)، `title` 3 |
| `scheduledCallEditMessage` | **65** | ScheduledCallEditMessage | `key` 1 (MessageKey)، `editType` 2 (UNKNOWN 0، CANCEL 1) |

الإلغاء هو التعديل الوحيد الموجود. التخزين المحلي (found): الجداول `message_scheduled_call` (`scheduled_timestamp_ms`، `call_type`، `title`)، `message_add_on_scheduled_call_edit` (`creation_message_row_id`، ...)، `message_system_scheduled_call_start` (`call_title`، `call_timestamp_ms`)، `scheduled_calls` (`key_chat_row_id`، `key_id`، `scheduled_timestamp`، `is_upcoming`، `call_log_row_id`). التذكير من جهة الخادم (ابن مكالمة `reminder`، و`kServerReminder*` أدناه) وكيفية ربط رسالة الإنشاء بـ token رابط المكالمة غير محلولين.

### 10.3 غرفة الانتظار

الـ stanzas `waiting_room_toggle` (`link-token`، `media`، `enabled`، نسخة المكالمة النشطة)، و`_admit`، و`_deny`، و`_leave`، و`_update`؛ حقول المستخدم المحلَّلة `jid`، `user_pn`، `push_name`، `guest_name`، `is_guest_eligible`، `state`. في Java: `waitingRoomAdmit`، `waitingRoomAdmitAll`، `waitingRoomDeny`، `waitingRoomToggle`؛ الأحداث `waitingRoomAdmitAcked`، `waitingRoomDenyAcked`، `waitingRoomStateChanged`، `waitingRoomDenied`. `kServerReminder`: Legacy 0، LinkJoinedCreator 1، LinkJoinedJoiner 2، LinkConnectedCreator 3، LinkMissedCreator 4، LinkCreatorWaitingRoomJoined 5، LinkCreatorWaitingRoomMultipleJoined 6.

---

## 11. bcall والبوت والنواقل البديلة

### 11.1 رسالة الدردشة `bcall` (found)

| الحقل | الرقم | النوع | الاستخدام |
|-------|--------|------|-----|
| `sessionId` | **1** | string | جلسة مكالمة الأعمال |
| `mediaType` | **2** | enum | UNKNOWN 0، AUDIO 1، VIDEO 2 |
| `masterKey` | **3** | bytes | مطلوب: غياب المفتاح يرمي `bcall message doesn't have master key` |
| `caption` | **4** | string | اختياري |

`Message.bcallMessage` = الحقل **72** (الصنف `DSA`)؛ يربط المعالج `F2V` (`FMessageBCallProtobuf`) الرسالة بنوع الرسالة 91 مع معرّف الجلسة ونوع الوسائط (0 unknown، 1 audio، 2 video) والتعليق وبايتات master key. الـ `master key` مفتاح يُسلَّم داخل رسالة دردشة مشفّرة من طرف إلى طرف؛ وما الذي يفتحه (inferred: وسائط مكالمة الأعمال) لم يُتتبع. أحداث المحرك `bCallCreated(callId, key, ...)`، `bCallJoined`، `bCallEnded`، `bCallAudienceUpdated`، `bCallCreateFailed`؛ `CallState.BCALL_STARTING`؛ أبناء `<call>` الواردة المسمّاة `bcall_*` تحصل على call id فارغ (3.2). توجد سلاسل native `bcall_start` و`bcall_notify`.

### 11.2 مكالمات البوت وإشارات HTTP / TEE

مكالمات البوت: `CallInfo.isBotCall`، عقد `<bot>` في `group_info`، `verifyIncomingBotIdentityKey`، `reconfigure_bot` (`req_id`)، تدفق TOS للبوت (nack 488)؛ يُدمج offer مع باني حمولة مخزَّن مؤقتًا. السياق: [WA_META_AI.md](WA_META_AI.md). وبشكل منفصل، تتيح `SignalingHttpCallback.sendMsg` للمحرك تبادل بايتات إشارات معتمة عبر `TeeRequestHandler` بدل chatd (`handle_http_tee_start_session_response`، `handle_http_create_extension_response`)؛ أنواع الطلب جلسة الصوت وavatar للـ codec. الأهلية وصيغة الحمولة **unknown** (inferred: جلسات البوت وavatar).

---

## 12. سجل المكالمات والتاريخ

### 12.1 `callLogMesssage` (حقل Message **69**، الصنف `C49434Loq`، found)

| الحقل | الرقم | النوع | القيم |
|-------|--------|------|--------|
| `isVideo` | **1** | bool | |
| `callOutcome` | **2** | enum | CONNECTED 0، MISSED 1، FAILED 2، REJECTED 3، ACCEPTED_ELSEWHERE 4، ONGOING 5، SILENCED_BY_DND 6، SILENCED_UNKNOWN_CALLER 7 |
| `durationSecs` | **3** | int64 | |
| `callType` | **4** | enum | REGULAR 0، SCHEDULED_CALL 1، VOICE_CHAT 2 |
| `participants` | **5** | `CallParticipant` متكرر | `jid` 1 (string)، `callOutcome` 2 (نفس enum) |

الباني `C53129Nna` (found): نتيجة سجل المكالمة من المحرك (`Voip.kCallLog*`) تُربط كما يلي.

| نتيجة `kCallLog` | `callOutcome` على السلك |
|-------------------|--------------------|
| Canceled 1، Missed 2 | MISSED |
| Unavailable 3 | FAILED |
| Rejected 4 | REJECTED |
| Connected 5 | CONNECTED |
| AcceptedElsewhere 6، ScreenedElsewhere 9 | ACCEPTED_ELSEWHERE |
| Invalid 0، Failed 7، ConnectedLonely 8، وغيرها | ONGOING (الفرع الافتراضي في الكود المفكَّك) |
| علم DND / علم متصل مجهول على السجل | SILENCED_BY_DND / SILENCED_UNKNOWN_CALLER (يُفحص أولًا) |

ربط Failed 7 بـ ONGOING يبدو خاطئًا لكنه الفرع الافتراضي في الكود المفكَّك؛ تعامل معه كما قُرئ وليس كسلوك متحقق منه. نوع المكالمة: النوع المحلي 1 يُربط بـ SCHEDULED_CALL، و2 أو 3 بـ VOICE_CHAT، وغير ذلك REGULAR. غياب نوع المكالمة يرمي `call log message missing call_type`.

### 12.2 قاعدة البيانات المحلية (found)

الجداول: `call_log` (`jid_row_id`، `from_me`، `call_id`، `transaction_id`، `timestamp`، `video_call`، `duration`، `call_result`، `is_dnd_mode_on`، `bytes_transferred`، `group_jid_row_id`، `is_joinable_group_call`، `call_creator_device_jid_row_id`، `call_random_id`، `call_link_row_id`، `call_type`، `offer_silence_reason`، `scheduled_id`، `telecom_uuid`، `terminated_by_device_switch`)، `call_log_participant_v2` (`call_log_row_id`، `jid_row_id`، `call_result`)، `joinable_call_log` (`call_id`، `joinable_video_call`، `group_jid_row_id`، `phash_identifier`، `self_other_device_connected`، `is_lgc_add`)، `message_call_log`، `call_unknown_caller`، `reminder`. الأحداث المغذّية: `callEnding(CallLogInfo, ..)`، `update1to1CallLog`، `updateJoinableCallLog` (`kUpdateJoinableCallLogType` Create 1، Update 2، Delete 3).

---

## 13. حالات المحرك والثوابت (found، `Voip.java`، `CallState`)

| المجموعة | القيم |
|-------|--------|
| `CallState` | NONE، CALLING، PRE_ACCEPT_RECEIVED، RECEIVED_CALL، ACCEPT_SENT، ACCEPT_RECEIVED، ACTIVE، ACTIVE_ELSEWHERE، REJOINING، LINK، CONNECTED_LONELY، PRECALLING، ENDING، BCALL_STARTING، SCREENING |
| `kCallLog*` | Invalid 0، Canceled 1، Missed 2، Unavailable 3، Rejected 4، Connected 5، AcceptedElsewhere 6، Failed 7، ConnectedLonely 8، ScreenedElsewhere 9 |
| `kCallEndReason*` | Unknown 0، Timeout 1، Self 2، RejectDoNotDisturb 3، RejectBlocked 4، MicPermissionDenied 5، CameraPermissionDenied 6 |
| `kFatalReason*` | Unknown 0، ParticipantAllocationFailure 1، CallSetupError 2، CallTxTimeout 3، CallRxTimeout 4، VideoStreamCreateError 5، VideoPortCreateFailed 6، NoSamplingRatesForAudioRecord 7، AudioInitError 8 |
| `kOfferSilenceReason*` | None 0، Privacy 2، Lightweight 3، ScreenSharing 4، AddedAsLinkCreator 9، AddedForDeviceSwitching 10، GroupChatAdd 11 |
| `kParticipant*` | Connected 1، Incoming 2، Ringing 3، Rejected 4، Terminated 5، TimedOut 6، CreatingCall 7، Invited 11 |
| `kVideoState*` | Disabled 0، Enabled 1، Paused 2، UpgradeRequest 3، UpgradeAccept 4، UpgradeReject 5، Stopped 6، UpgradeRejectByTimeout 7، UpgradeCancel 8، UpgradeCancelByTimeout 9، UnknownPeer 10، Xr2dCodecAvatarEnabled 12، Error 20 |
| `kStatus*` | Success 0، InvalidArgument 70004، Exists 70015، Ignored 70020، CallAlreadyStarted 670001، CallNotActive 670007، CallHasNoVideo 670018، GroupCallUserExists 670021، GroupCallPeerCodecMismatch 670033، GroupCallUserExistsNotInvited 670038، NotPermitted 670040، UserNotRemovable 670041، UserNotConnected 670042 |
| `kScreenShareVersion*` | Legacy 0، من 1 إلى 4 |
| `kNetworkHealth*` | Measuring 0، NoNetwork 1، Poor 2، Average 3، Good 4 |

أعداد `kCallEndReason` هي ما تراه الواجهة؛ أما السلاسل الموضوعة على السلك لـ terminate فليست ضمن سلاسل المكتبة (14.3).

---

## 14. الأخطاء وreject وterminate

### 14.1 أكواد nack لـ Offer (found، `VoiceServiceEventCallback.callOfferNacked`)

يستدعي إقرار offer المصحوب بأخطاء الدالة `callOfferNacked(errors[])`. الخطأ المفرد 304 أو 400 يُعامل كـ offer مكرر ويُتجاهل. يكون nack قاتلًا عندما تكون المكالمة `CALLING` / `CONNECTED_LONELY` ويُرفض كل المستلمين (أو الذات) بـ nack، أو عندما يكون الكود 432؛ وإلا فهو لكل مستلم وغير قاتل.

| الكود | المسار القاتل (فرع الكود المفكَّك) | المسار غير القاتل |
|------|-------------------------------|----------------|
| 401 | شاشة غير مسموح (معرّف السبب 3) | |
| 403 | شاشة غير مسموح، معرّف خاص بالفيديو عند الفيديو | |
| 404 | معرّف غير مسموح 16 | نص "contact unavailable" لكل مستلم |
| 405 | المعرّف 4 | |
| 406 | المعرّف 2 (صوت) / 11 (فيديو) | |
| 411 | المعرّف 11، أو 37 للخفيف | |
| 412 | المعرّف 10؛ تُحدَّث معلومات المجموعة عند عدم تطابق العضوية | |
| 426 | المعرّف 1 (صوت) / 9 (فيديو) | |
| 427 | المعرّف 12، أو 36 لـ 1:1 الخفيف | نص لكل مستلم؛ في المجموعات التي تتجاوز 4 مشاركين معرّف بديل |
| 428 | المعرّف 14 | نص لكل مستلم |
| 429 | حدث واجهة فقط | |
| 431 | المعرّف 15 | نص "not available" |
| 432 | المعرّف 2؛ قاتل دائمًا | |
| 435 | | نص لكل مستلم؛ وبعد إقرار offer يطلق أيضًا إجراءً إضافيًا |
| 460 / 463 | فيديو 10 / صوت 2؛ 463 المعرّف 17 | |
| 488 | TOS البوت غير مقبول: يفتح تدفق TOS للبوت | نفسه |
| 467، 468، 469 | | المعرّف 46 لعدة مستلمين |
| 500، 502 | | نص "not available" |
| 538 | | المعرّف 35 |
| غير ذلك | المعرّف الافتراضي (فيديو 8 / 0) | التأكيد `Unknown error code` |

الفرع القاتل في الكود المفكَّك فقد بعض عبارات return، لذا المعرّفات إرشادية فقط؛ أما قائمة الأكواد والتقسيم قاتل / غير قاتل فثابتان. معاني الأكواد وراء رد فعل العميل تخص الخادم (**unknown**). بعد nack لـ offer كامل لا يرسل المحرك أي stanza مكالمة سوى `terminate` (سلسلة found).

### 14.2 أسباب Reject (found، `Voip.REJECT_REASON_*`)

| السلسلة | المعنى / رد فعل العميل |
|--------|---------------------------|
| `` (فارغة) | رفض |
| `busy` | المستدعى عليه مشغول؛ نغمة انشغال، تنتهي المكالمة بعد تأخير |
| `unavailable` | ثابت معرَّف؛ الاستخدام الرئيسي موجود في كود الحضور / التوفر |
| `uncallable` | لا يمكن الاتصال بالنظير؛ شاشة غير مسموح |
| `tos` | النظير لم يقبل TOS؛ شاشة غير مسموح |
| `enc` | فشل فك تشفير مفتاح المكالمة |
| `server_conf_corrupted` | إعداد الخادم غير قابل للاستخدام |

`rejectCall(callId, reason, int)` و`rejectPendingCall` هما نقطتا الدخول؛ وتستهلك `callRejectReceived` الأسباب الواردة. تُربط أسباب reject بنتائج المكالمة المحلية (`reject_reason_to_call_result`، `set_call_term_reason_from_received_call_reject_reason`).

### 14.3 Terminate (سلاسل found)

- يحمل `terminate` معرّف معاملة وعقدة `call_summary` (حالات المستخدمين، المدة)؛ ويحمل offer لمكالمة منتهية `terminate_hint` مع `terminate_reason` و`call_summary` ومعرّف معاملة. هل لـ `terminate` نفسه سمة `terminate_reason` غير محلول.
- يتجاهل المحرك terminate القادم من جهاز مرافق؛ ويوزّع الجهاز الأساسي terminate على نظراء multi-device (`fanout_terminate_if_peer_is_md`).
- يُتجاهل terminate تبديل الجهاز في الحالة الخاطئة؛ وتُشتق نتائج "handled elsewhere" من السبب (`get_handled_elsewhere_outcome_from_terminate_reason`) وتُتجاهل النتائج المتعارضة لنفس call id.
- كما يُنهي RTCP BYE على مسار الوسائط المكالمة (`rtcp_bye_terminate_delay`)، وكذلك إزالة extension من جهة الخادم (`extension terminated by server`).
- ترسل Java `terminate` مع إعادة محاولة (في الطابور عبر عمليات إعادة الاتصال) عندما يكون العلم **8003** مفعّلًا والمكالمة ليست مكالمة بوت أو في حالة lonely؛ وإلا دون إعادة محاولة (الفرع غير واضح جزئيًا في المخرجات المفكَّكة).
- قيم سلسلة `reason` الخاصة بـ terminate (وأي ربط من `kCallEndReason`) ليست في سلاسل المكتبة ولم تُوجد في مكان آخر في APK (**unknown**).

---

## 15. أعلام الميزات (المعرّفات كما قُرئت في مواضع الاستدعاء؛ الأسماء غير محلولة)

| المعرّف | النوع | ما يتحكم به |
|----|------|----------|
| **9257** | long ms | مهلة تسليم offer؛ يُسقط الـ stanza عند انتهاء المهلة (`CIX.A02`) |
| **9431** | long ms | مهلة تسليم accept؛ ويتذكر أيضًا معرّف stanza الخاص بـ accept ليتمكن `preSendTerminate` من إلغائه |
| **9432** | bool | عند انتهاء مهلة accept يطلق إعادة اتصال |
| **8003** | bool | terminate مع إعادة محاولة (14.3) |
| **15125** | bool | الإبلاغ عن المقياس `call_stanza_drop` |
| **30890** | bool | إرسال ping للمكالمة الصادرة بعد offer |
| **30891** | long ms | مهلة ping، الافتراضي 3000 |
| **32651** | int | محاولات ping، الحد الأدنى 1 |
| **31086** | bool | متتبع offer الصادر |
| **24935** | bool | كتابة `callEntryPoint` في `Message.call` |
| **520** | bool | إضافة سياق إسناد الإعلان إلى `Message.call` (inferred) |
| **20605** / **20606** | bool / int | إضافة `<tctoken>` إلى وجهات المكالمة؛ حد أقصى للمستخدمين لكل stanza |
| **24063** | bool | اختيار نوع الجلسة عند فك التشفير لفئة نص مشفّر (inferred) |
| **4217** | int mask | peek للـ offers الواردة: البت 1 صوت، البت 2 فيديو |
| **3094** | int mask | البت 8 = أحداث المكالمة غير المتزامنة (`kFlagEnableCallEventAsync`)؛ مقترن بـ **9210** (bool) |
| **7481** | bool | حالة إشعار الكتم للمكالمات الجماعية المرتبطة |
| **13630** / **13804** | int / bool | أخذ عينات لمقياس فك التشفير (inferred) |

تأتي معاملات المحرك (`p->enable_sframe_tx`، `tp->web_p2p_bitmap`، `tp->enable_e2e_bind_probe_bitmap`، `options.wa_log_time_series`، ...) من `voip_settings` الخاصة بالخادم وتُقرأ عبر `Voip.getVoipParam`؛ أسماؤها سلاسل في المكتبة، أما قيمها فمن جهة الخادم.

---

## 16. Baileys (`baron-baileys-v2`، المصدر مقروء، لم يُختبر شيء)

| الموضوع | Baileys | Android |
|-------|---------|---------|
| Offer | `offerCall`: `call-id` عشوائي من 32 خانة hex، `call-creator` = المعرّف الخاص، `<audio enc=opus rate=16000/8000>`، `<video enc=vp8 dec=vp8 ...>` (فيديو)، `<net medium=3>`، `<capability ver=1>` 6 بايت `01 04 FF 83 CF 04`، `<encopt keygen=2>`، `<destination>` مع `Message{call{callKey}}` مشفّر عبر Signal، `count=0`، و`device-identity` عند إنتاج pkmsg | العناصر نفسها؛ تبني Android الـ offer في المحرك، وبايتات capability غير معروفة (5.2) |
| الغلاف | `<call id to>` لـ offer؛ يستخدم reject / accept / terminate السمتين `from` + `to` بلا `id` | `<call to id>` دائمًا (3.1) |
| accept | `<accept call-id call-creator count=0/>`، بلا أبناء | accept المحرك يحمل معاملات الوسائط وشهادة (القسم 4) |
| terminate | `reason="user-terminated"`، `count=0` | سلاسل الأسباب غير معروفة (14.3) |
| rekey | `<enc_rekey ...><enc v=2 type=msg/></enc_rekey>` | شكل v2 يطابق 6.4؛ v3 غائب |
| الوارد | يفك تشفير `<enc>` (`unpadRandomMax16`، `Message.decode`)، يخزّن offer مؤقتًا، يُصدر أحداث المكالمة؛ وسوم الوسائط / relay تُقَرّ فقط | تفك Android التشفير بالغلاف نفسه وتغذي المحرك |
| الروابط | `link_create media` (+ `event start_time`) إلى `@call`؛ `waiting_room_toggle`؛ `link_join token` | القواعد تطابق الأسماء الموجودة هنا؛ نوع JID الهدف غير محلول |
| حالات terminate | يربط سلاسل `terminate reason` وهي `Timeout`، `RejectDoNotDisturb`، `MicPermissionDenied`، `CameraPermissionDenied`، `RemoteBusy`، `RemoteOffline` | هذه السلاسل ليست في المكتبة؛ تشبه الأسماء `kCallEndReason` (رابط **inferred**) |

لا يملك Baileys تخصيص relay ولا WARP / SRTP / SFrame ولا محركًا، لذا يمكنه الإشارة والرنين لكنه لا يستطيع حمل الوسائط. لم يُختبر ما إذا كان النظير يقبل أو يرنّ offer بلا معاملات المحرك الكاملة.

---

## 17. حالات الخطأ

| العرض | السبب | الحل |
|---------|-------|-----|
| `Wrong jid type` لـ stanza مكالمة | `to` ليس JID مستخدم / جهاز / نطاق مكالمات | عنوِن JID الجهاز أو المستخدم |
| أُرسل offer بـ `without enc`، والنظير لا يرن | لم يُشفَّر مفتاح المكالمة (لا جلسة، مهمة pre-key معلّقة) | ابنِ الجلسات أولًا؛ تبقي Android الـ offer معلّقًا |
| `duplicate <enc>` / `invalid retry count` / `invalid registration` | `<enc>` مشوّه؛ `registration` ليس 4 بايت | `<enc>` واحد مع `count`؛ `registration` عند إعادة المحاولة فقط |
| nack لـ offer بـ 304 / 400 | offer مكرر | تجاهل |
| nack لـ offer بـ 401 / 403 / 463 | المتصل غير مسموح له بالاتصال بهذا النظير | لا شيء على العميل |
| nack لـ offer بـ 412 / 488 | عضوية المجموعة مختلفة / TOS البوت غير مقبول | حدّث معلومات المجموعة / اقبل TOS البوت |
| reject بـ `enc` | تعذّر على المستدعى عليه فك تشفير مفتاح المكالمة | أعد إرسال offer بعد إصلاح الجلسة (`count` > 0) |
| `Unsupported keygen ver`، `can not receive both te and te2`، `num_tokens < 1` | `encopt` أو نقاط نهاية relay أو tokens غير صالحة | أرسل keygen بقيمة 2 أو 3، وعائلة نقاط نهاية واحدة، وtoken واحدًا على الأقل |
| `bcall message doesn't have master key` | `masterKey` مفقود | أدرجه |
| `Call stanza delivery timed out` | لا إقرار من chatd ضمن العلم 9257 / 9431 | يُسقط الـ stanza؛ وقد يعيد accept الاتصال (العلم 9432) |

---

## 18. فروق أساسية

| لا تخلط | مع |
|----------------|------|
| `Message.call` (الحقل 10، مفتاح مكالمة E2E داخل رسالة Signal) | `callLogMesssage` (69، سجل النتيجة)، `bcallMessage` (72، مفتاح جلسة الأعمال) |
| `<enc>` في stanza مكالمة (نص مشفّر Signal ثنائي) | رسائل sender-key من نوع `skmsg` وتشفير الوسائط |
| مفاتيح E2E SRTP / SFrame (من مفتاح المكالمة) | مفاتيح قفزة-بقفزة (من `hbh_key` الخاص بـ relay) |
| `<token>` / `<auth_token>` الخاصان بـ relay (بيانات اعتماد التخصيص) | `<tctoken>` (token الخصوصية داخل `<to>`) |
| أعداد `kCallEndReason` (للواجهة)، `kCallLog*` (نتيجة المحرك) | سلاسل سبب terminate (على السلك، unknown)، enum `callOutcome` (على السلك) |
| `CallLogMessage.CallType` بالقيم REGULAR / SCHEDULED_CALL / VOICE_CHAT | `ScheduledCallCreationMessage.CallType` بالقيم UNKNOWN / VOICE / VIDEO |
| `enc_rekey` v2 (ابن `<enc>` عبر Signal) | `enc_rekey` v3 (قائمة protobuf من `RekeyKeyEntry`) |
| مسار relay الخاص بـ WhatsApp (WARP، SRTP قفزة-بقفزة) | مسار web-P2P (ICE + DTLS-SRTP) |
| مكالمة الحدث (رابط مع وقت بدء) | رسائل دردشة المكالمة المجدولة (61 / 65) |
| الإشارات عبر chatd | إشارات HTTP / TEE لجلسات البوت وavatar |

---

## 19. التدفق الكامل (مكالمة 1:1)

```
[Caller app]  startCall(callId, peer, video, ...)
     │
     ▼
[Native engine]  mints 32-byte callKey ; builds <offer> (audio, video, net, capability, encopt keygen)
     │  sendCallStanza(peer, callId, node)
     ▼
[OutgoingSignalingHandler]  per device: Message{call{callKey,...}} → Signal encrypt → <enc>
     │  <destination><to jid><enc/></to>…</destination> [tctoken] [device-identity if pkmsg]
     ▼
[CIX / writer]  <call to id><offer call-id call-creator>…</offer></call>     (delivery timeout, flag 9257)
     │
     ▼
[WA Server]  (not observed) enriches the offer: relay, voip_settings, metadata, privacy
     ├──────► [Caller]  offer ack: <relay> tokens, endpoints, hbh_key ; voip_settings ; or nack (14.1)
     ▼
[Callee]  <call from t e offline><offer/></call>
     │  CallStanzaHandler → nativeParseXmppOffer → C83 decrypt <enc> → callKey → ring (RECEIVED_CALL)
     ▼
[Callee]  preaccept ─► [Caller] PRE_ACCEPT_RECEIVED ;  accept (media params, certificate) ─► ACCEPT_RECEIVED
     │
     ▼
[Both engines]  relay allocate / bind with tokens ; transport / relaylatency / relay_info_update
     │  E2E keys from callKey (HKDF) ; hop-by-hop keys from hbh_key ; optional P2P pair or web_p2p DTLS
     ▼
[Media]  WARP packets via the elected relay or P2P ; ACTIVE ; in-call video, mute_v2, notify, heartbeat
     │
     ▼
[Either side]  terminate (transaction id, call_summary) ─► ack class="call" type="terminate"
     ▼
[Both]  callEnding(CallLogInfo) → call_log row / callLogMesssage ; teardown ; RTCP BYE
```

فروق المكالمة الجماعية: يحمل offer العنصر `group_info` ولا يحمل مفتاحًا لكل جهاز؛ ينضم المتأخرون عبر `lobby` / `link_join`؛ وتنتقل عمليات rekey كـ `enc_rekey` (v2 fanout أو v3) مع معرّفات معاملة؛ وتمر الوسائط عبر SFU مع SFrame.

---

## 20. غير المعروف

| البند | الحالة |
|------|--------|
| بُناة / محلِّلات stanzas native، سلاسل HKDF `info`، تخطيطات المفاتيح | لم تُفك مكتبة voip؛ سلاسل فقط |
| بايتات capability، أكواد `net medium`، القيم الافتراضية لمعاملات codec | لم تُستخرج |
| قيم `transport-message-type` عدا 13 | لم تُستخرج |
| سلاسل `reason` الخاصة بـ terminate، ربط reject بسبب الإنهاء | لم تُوجد |
| معنى `e` في الغلاف، الإجراء الجانبي لخطأ إقرار offer 435 | غير محلول |
| جدول معرّفات الرسائل الرقمي (85 نوعًا) | غير موجود في سلاسل هذا البناء |
| فئة جهاز extension، مُحفِّز v3 rekey، مُحفِّز rekey المجموعة | غير محلول |
| نوع JID لمكالمة الرابط، ربط المكالمة المجدولة بـ token | غير محلول |
| حمولة إشارات TEE / HTTP وأهليتها | غير محلول |
| سلوك الخادم (الإثراء، دلالات nack، اختيار relay) | من جهة الخادم |
| الحركة (Traffic) | لم يُلتقط شيء |
