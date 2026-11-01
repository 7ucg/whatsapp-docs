<!-- src-sha1: acf9c9e68ca59b17d45a787d66ae2550607b66cc -->
# WhatsApp اكتشاف العملاء المعدَّلة — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-01
**النطاق:** الاكتشاف من جانب العميل للعملاء غير الرسمية/المعدَّلة على أندرويد (عائلة إعادة التحزيم GB WhatsApp، وحدات ربط Xposed/LSPosed مثل WaEnhancer، ملفات APK المعاد توقيعها) — الاستدلال المخصَّص الواحد الذي وُجد (`is_whatsapp_plus_user`)، والبحث عن آثار أطر الربط (Xposed/Frida/Substrate)، وما يفعله العميل بتليمتري التوقيع/مصدر التثبيت/الروت الموثّق مسبقًا في `WA_CLIENT_INTEGRITY.md`، وتعامل واجهة حظر WFAC مع أسباب الحظر المرسلة من الخادم، وسطح الهجوم الذي تستهدفه وحدة ربط من طرف ثالث (WaEnhancer) داخل العملية المستضيفة

---

## 1. نظرة عامة

يقتصر هذا التقرير على **اكتشاف التعديل/العبث**، لا على التصديق على الحساب. توثَّق توثيقًا كاملًا في [`WA_CLIENT_INTEGRITY.md`](WA_CLIENT_INTEGRITY.md): التصديق المخزَّن في Keystore، وPlay Integrity، وWASafe، والفحص الذاتي للتوقيع (WAM **6251**)، وعلامة مصدر التثبيت (WAM **10255**)؛ لا يذكر هذا التقرير إلا ما تساهم به هذه الآليات في اكتشاف التعديل، ولا يكرر آلياتها.

| الآلية | تكتشف | تُرفَع كـ | الإنفاذ الموجود |
|-----------|---------|-------------|--------------------|
| `is_whatsapp_plus_user` (تحرٍّ انعكاسي عن الصنف) | عميل من طرف ثالث يضمّن مكتبة الإبلاغ عن الأعطال ACRA | حقل تليمتري `wam_daily`؛ سلسلة `diagnostic` في "اتصل بنا" (`nw-wap`) وتقرير التصحيح (`NW-WAP-1`) | لا يوجد |
| الفحص الذاتي لتوقيع التطبيق (`AbstractC38241gg` / `C27965CCj`) — انظر تقرير السلامة §5 | APK معاد توقيعه/معاد تحزيمه (شهادة التوقيع ≠ قيمة WhatsApp المضمَّنة) | سمة WAM المشتركة **6251** | لا يوجد |
| علامة مصدر التثبيت (`CHH`) — انظر تقرير السلامة §5.4 | تثبيت بالتحميل الجانبي / غير من Play | WAM **10255**، `install_source_official` | توجيه تنزيل الوحدات فقط، بلا بوّابة منع |
| أعلام الروت / المحاكي / ROM المخصَّص (`C00L`، `Cdt`) — انظر تقرير السلامة §6 | جهاز مُجذَّر أو مُحاكى (عامل تمكين شائع، وليس إشارة تعديل بذاته) | `wam_daily` | لا يوجد |
| سلاسل آثار أطر الربط (Xposed، Frida، Substrate، LSPosed، TracerPid) | — | — | **غير موجود** في هذا الإصدار (§3) |
| التحقق الذاتي من المجموع الاختباري (checksum) للمكتبة الأصلية/ملف dex | — | — | **غير موجود** في هذا الإصدار (§3) |
| واجهة حظر WFAC (`WfacBanActivity`) | — | تعرض `ban_violation_type` / `ban_violation_source` / `ban_violation_reason` المرسلة من الخادم | قرار من جانب الخادم، معتم على العميل (§5) |

لم يُعثر على أي مسار شيفرة في العميل المفكوك يرفض التشغيل، أو يُنزل مستوى ميزة، أو يمنع إجراءً بسبب أي مما سبق. كل آلية وُجدت هي **تليمتري**، وهو ما يتوافق مع الاستنتاج الذي سبق التوصل إليه بشأن سلامة الحساب.

---

## 2. الاستدلال المخصَّص الواحد لاكتشاف التعديل: `is_whatsapp_plus_user`

### 2.1 ما يفحصه

ثلاثة مواضع مستقلة، كل منها يشغّل **نفس التحرّي الانعكاسي** بدلًا من استدعاء مساعد مشترك:

```smali
; smali_classes7/X/Cdt.smali, method C4k (fills LX/0Fp; = wam_daily event)
const-string v0, "org.acra.ACRA"
invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;
; ClassNotFoundException -> false, success -> true
iput-object v0, p1, LX/0Fp;->A0W:Ljava/lang/Boolean;   ; -> wam_daily.is_whatsapp_plus_user
```

```java
// C1Z.java (contact-us diagnostics)
try { Class.forName("org.acra.ACRA"); sbA0m.append("nw-wap "); } catch (ClassNotFoundException unused) {}

// C10V.java (debug report builder)
try { Class.forName("org.acra.ACRA"); sb10.append("NW-WAP-1 "); } catch (ClassNotFoundException unused2) {}
```

| العنصر | القيمة | الدرجة |
|------|-------|------|
| الفحص | نجاح `Class.forName("org.acra.ACRA")` (الصنف موجود في classpath) | found |
| اسم الحقل | `is_whatsapp_plus_user` (`LX/0Fp;->A0W`)، حدث `wam_daily` | found |
| المصارف (sinks) | تليمتري `wam_daily`؛ سلسلة `diagnostic` في "اتصل بنا" (`nw-wap `)؛ نص تقرير التصحيح (`NW-WAP-1 `) | found |
| المنطق | ACRA (`org.acra`) مكتبة إبلاغ أعطال من طرف ثالث؛ لا تضمّنها نسخة WhatsApp الرسمية. ضمّنتها تاريخيًا عائلة إعادة التحزيم "WhatsApp Plus" لتليمتري أعطالها الخاص (`inferred`: اسم الحقل هو تسمية WhatsApp الخاصة، وليس قيمة مقروءة من التعديل نفسه) | found (التحرّي) / inferred (معنى التسمية) |
| ثغرة في الفك | لم يُفكَّك `Cdt.java` نفسه (يوجد فقط الصنف الأخ `CDT.java`)؛ قُرئ الفحص من smali | found |

### 2.2 ما لا يفعله

- لا توجد قائمة سماح/حظر بأسماء حزم العملاء المعدَّلة (`com.gbwhatsapp`، `com.yowhatsapp`، `com.fmwhatsapp`، `com.wmods.wppenhacer`، …) في أي مكان من العميل المفكوك — لا تظهر هذه السلاسل في `java_src` ولا في `smali*`.
- التحرّي هو بحث انعكاسي واحد عن صنف، لا توقيع أو هاش أو فحص سلوك. أي تعديل لا يضمّن `org.acra.ACRA` فقط (أو يظلّل/يعيد تسمية الصنف) يتجاوز الفحص بسهولة؛ لا يزعم هذا التقرير عكس ذلك.
- المصارف الثلاثة نصوص تشخيص/تليمتري وحدث تحليلي يومي. لم يُعثر على أي فرع يقرأ `A0W`/`is_whatsapp_plus_user` ويغيّر سلوك العميل.

---

## 3. البحث عن آثار أطر الربط وإعادة التحزيم (غير موجود)

بحث في الشجرة المفكوكة كاملة (`java_src/`، وكل `smali*/`) لإصدار 2.26.41.6:

| السلسلة (السلاسل) المرجعية | الهدف | النتيجة |
|-------------------|--------|--------|
| `Xposed`، `XposedBridge`، `de.robv`، `LSPosed` | وجود إطار ربط Xposed/LSPosed | غير موجود |
| `frida`، `Frida`، `re.frida`، `frida-server`، المنفذ `27042` | خادم تنصّت Frida | غير موجود (الإصابة الوحيدة لسلسلة `frida` داخل عبارة نمطية (regex) لنطاقات عامة/TLD، غير ذات صلة) |
| `substrate`، `Substrate` | إطار ربط Cydia Substrate | غير موجود |
| `TracerPid` | اكتشاف تعقّب ptrace الكلاسيكي من `/proc/self/status` | غير موجود |
| `GBWhatsApp`، `gbwhatsapp`، `com.gbwhatsapp`، `FMWhatsApp`، `YoWhatsApp`، `OGWhatsApp`، `com.wmods.wppenhacer` | سلاسل أسماء حزم عملاء معدَّلة محدَّدة | غير موجود |
| `modded`، `unofficial`، `tampered`، `fake whatsapp`، `clone app` | نصوص سجلّ/عرض عامة لاكتشاف التعديل | غير موجود |
| استخدامات `CRC32` (10 إصابات) | فحص ذاتي لمجموع اختباري لـ dex/الأصول | كلها في تحميل multidex (`dextricks`) أو تحزيم ملفات zip لتقارير الأعطال، وليس أي منها فحصًا ذاتيًا للعبث بالتطبيق |
| `checkSignatures` (3 إصابات) | مقارنة التوقيع | كلها فحوصات ثقة IPC/المستدعي (فحص ثقة المستدعي بنفس التوقيع في `FileSharingHelper`، وفحص ثقة تطبيق مرافق Pixel) ولا صلة لها باكتشاف عميل WhatsApp معدَّل |
| `isDebuggerConnected` | مقاومة التصحيح | فقط في كاشف ANR (`SigquitBasedANRDetector`) ومساعدات الأعطال، وليست بوّابة عبث (يؤكد `WA_CLIENT_INTEGRITY.md` §6.4) |
| `/proc/self/status` (4 إصابات، `KGi`/`KGw`/`KH8`/`KGp`) | — | قارئات إحصاءات الذاكرة (يُحتمل جمع `VmRSS` للتشخيص)؛ لم يُعثر على تحليل لـ `TracerPid` هناك |

**تصحيح لصياغة ملاحظة بحث ساكن سابقة:** تصف ملاحظة بحث ساكن سابقة WaEnhancer بأنه "تحديدًا نوع العميل المعدَّل/غير الرسمي الذي يستهدفه نظام سلامة التطبيق الرسمي"، لكنها لا تزعم أن التطبيق الرسمي يكتشفه بالاسم — وهذه القراءة تتأكد هنا: لا توجد شيفرة اكتشاف خاصة بـ WaEnhancer أو بـ GB أو بـ Xposed في إصدار 2.26.41.6. الإشارة الوحيدة من جانب العميل التي قد تنطلق عند تثبيت WaEnhancer هي تحرّي ACRA العام `is_whatsapp_plus_user`، وفقط إن كانت الوحدة (أو تبعية مضمَّنة فيها) تضمّن ذلك الصنف — غير محقَّق في أي اتجاه بخصوص WaEnhancer تحديدًا (`unknown`).

هذا يوسّع `WA_CLIENT_INTEGRITY.md` §6.4، التي أشارت إلى أن المجموع الاختباري لـ dex/الأصول "لم يُبحث فيه بشكل مستوفٍ" — وقد بُحث فيه الآن وما زال غير موجود.

---

## 4. تبعات من جانب الخادم مرئية من جانب العميل

### 4.1 واجهة حظر WFAC

تقرأ `WfacBanActivity` (`com.whatsapp.waffle.wfac.p191ui`) ثلاث قيم إضافية (extras) مرسَلة من الخادم وتعرضها؛ لا تحسب سببًا:

```java
int violationType   = getIntent().getIntExtra("ban_violation_type", -1);
String violationReason = getIntent().getStringExtra("ban_violation_reason");
int violationSource  = getIntent().getIntExtra("ban_violation_source", -1);
```

| العنصر | الدرجة |
|------|------|
| `ban_violation_type` / `ban_violation_source` أعداد صحيحة معتمة؛ لم يُعثر على أي تعداد (enum) من جانب العميل يحلّها إلى أسباب مسمَّاة (مثل "عميل معدَّل") | found (absence) |
| `ban_violation_reason` سلسلة نصية حرة، يُفترض أنها مولَّدة من قالب خادم | found |
| لا يربط أي مسار شيفرة أي إشارة من إشارات الاكتشاف في §1–§3 (`is_whatsapp_plus_user`، عدم تطابق التوقيع، الروت، مصدر التثبيت) بقيمة `ban_violation_*` | found (absence) |

آلة حالة الحظر الكاملة، وGraphQL (`BizIntegrityQuery`)، ومستويات الثقة، وstanzas فشل XMPP موجودة في [`WA_BAN_SYSTEM_DEEP_EN.md`](WA_BAN_SYSTEM_DEEP_EN.md)؛ لا يكرر هذا التقرير ذلك المحتوى. استخدام الخادم لأي من تليمتري §1 (عدم تطابق التوقيع، `is_whatsapp_plus_user`، الروت) كمدخل للحظر/درجة الثقة **غير معروف** — فهو من جانب الخادم وغير قابل للمراقبة سكونيًا، وهو نفس الاستنتاج في `WA_CLIENT_INTEGRITY.md` §13.

### 4.2 تقييد الميزات

لم يُعثر على أي فرع من جانب العميل يعطّل ميزة بناءً على إشارات §1. الوحيد "التقييد" المرصود في كل سطح السلامة/التعديل هو تقنين (throttling) طلبات التصديق/الرمز نفسها (ab-props، موثَّق في تقرير السلامة) — ليس ردًّا على اكتشاف تعديل.

---

## 5. سطح الهجوم: ما تستهدفه وحدة ربط (WaEnhancer، `com.wmods.wppenhacer`)

يصف هذا القسم الجانب الآخر من الحد — ما تربطه وحدة Xposed/LSPosed نموذجية داخل العملية المستضيفة — لتحديد ما يحتاجه الاكتشاف من جانب العميل (الغائب في معظمه) ليغطّيه. مصدر الدليل: آثار تركها تثبيت معدَّل بـ WaEnhancer في دليل اختبار `wa-data-root/` مُلتقَط (`Protocols/waenhancer-mod/info.md`)، وليس تحليلًا ساكنًا لملف APK الخاص بـ WhatsApp نفسه. الدرجات كما سُجِّلت هناك.

| القدرة | الآلية | الدرجة |
|------------|-----------|------|
| التسليم | وحدة Xposed/LSPosed تعمل **داخل** عملية `com.whatsapp` (ليست تطبيقًا منفصلًا، ولا إعادة تحزيم) | found |
| معالجة التعتيم (obfuscation) | "Unobfuscator" في زمن التشغيل: يحلّ أسماء أصناف/دوال WhatsApp المعتَّمة عند بدء تشغيل الوحدة ويخزّن المقابض المحلولة مؤقتًا (`UnobfuscatorCache.xml`، `UnobfuscatorCacheStrings.xml`)، مرتبطة باسم إصدار WhatsApp نفسه بحيث يُبطَل التخزين المؤقت عند تحديث أي من الجانبين | found |
| إخفاء الحضور ("الوضع الشبحي") | يربط دوالًا متعلقة بالحضور؛ الإعداد مخزَّن في `WaGlobal.xml` (`ghostmode`) | found (artifact) |
| منع الحذف/إيصالات القراءة | يعترض مسارات شيفرة "الحذف للجميع" وإيصالات القراءة؛ يحفظ نسخًا ظلّية في مخازنه الخاصة (`com_waenhancer_message_history.db`، وقاعدة بيانات مدعومة بـ Room هي `MessageHistory.db` — لا يستخدم WhatsApp نفسه Room لتخزين الرسائل) | found |
| رؤية البروتوكول الخام | تكتب `StanzaLogger.logStanza(...)` stanzas XMPP الصادرة/الواردة إلى ملف نصي صريح (`wae_stanzas.txt`) — أي أن الوحدة تتنصّت على مسار إرسال/استقبال stanza الخاص بالعميل نفسه بعد أن تكون طبقة Noise/E2E قد فكّت التشفير فعلًا | found |
| تسجيل عمليات الربط | تسجيل تشخيصي لكل تشغيل يحصي عدد الربط (`devtrace_logs/*.jsonl`، `eventType:"hook_config_loaded"`، `payload.hookCount`) | found |
| حدود النطاق | يربط طبقة Java/واجهة المستخدم فقط؛ لا يبدو أنه يستبدل التشفير الأصلي أو نقل Noise/chatd (مخزن axolotl/Signal، مفاتيح ما بعد الكم المسبقة، Keystore، ونظم OHAI/OPAQUE/WAFFLE الأصلية تبقى بلا تغيير) | inferred |

بقراءته مع §3: لا تملك النسخة الرسمية من العميل شيفرة تعدّ وحدات Xposed/LSPosed المحمَّلة، أو تفحص ذاكرة عمليتها الخاصة عن قفزات ربط (trampolines)، أو تفحص `TracerPid`/`/proc/self/maps` عن مكتبات مُحقَنة. الشيء الوحيد الذي يقف بين سطح الهجوم هذا والاكتشاف هو تحرّي `is_whatsapp_plus_user` العام الواحد (§2)، الذي يستهدف مكتبة إبلاغ عن أعطال، لا إطار ربط.

---

## 6. حالات الخطأ / المزالق

| العارض | السبب | ملاحظة |
|---------|-------|------|
| `is_whatsapp_plus_user = true` في `wam_daily` بلا أي أثر إضافي من جانب العميل | إمكانية حلّ `org.acra.ACRA` على classpath | تليمتري فقط، بالتصميم |
| تحتوي `diagnostic` على `nw-wap` / `NW-WAP-1` في "اتصل بنا" أو تقارير التصحيح | نفس تحرّي ACRA، مصرف مختلف | نص مسار دعم، لا بوّابة |
| لا سبب لشاشة حظر WFAC يتجاوز رمزًا عدديًا | `ban_violation_type`/`ban_violation_source` بلا تعداد (enum) من جانب العميل | يتحكم فيه الخادم، لا يمكن حله سكونيًا |
| البحث عن "Xposed"/"Frida" لا يُظهر شيئًا | صحيح — هذا الإصدار لا يحتوي على اكتشاف إطار ربط | ليست ثغرة فك لهذه السلاسل تحديدًا (بحث في الشجرة كاملة) |
| تثبيت WaEnhancer يغيّر سلوك الرسائل/إيصالات القراءة بلا أي سجل من جانب WhatsApp | يربط WaEnhancer طبقة Java قبل أن يتمكن تليمتري WhatsApp نفسه من رصد الاستدعاء الأصلي | متوقَّع بالنظر إلى نطاق §5 |

---

## 7. تمييزات أساسية

| لا تخلط بين | الحقيقة |
|-----------------|------|
| `is_whatsapp_plus_user` وقائمة سماح لعملاء معدَّلة | تحرّي انعكاسي واحد عن صنف مكتبة طرف ثالث؛ لا توجد قائمة بأسماء حزم معدَّلة |
| اكتشاف التعديل/العبث (هذا التقرير) وتصديق الحساب (`WA_CLIENT_INTEGRITY.md`) | مشكلتان مختلفتان: هذا التقرير عن اكتشاف *ثنائية/بيئة تشغيل عميل معدَّلة*؛ تقرير السلامة عن *تصديق جهاز/مفتاح حقيقي* للخادم — يتداخلان فقط في كون كلاهما تليمتري، لا إنفاذ |
| واجهة حظر WFAC (`WfacBanActivity`) ومنطق قرار الحظر | الواجهة تعرض رموزًا/سلاسل مرسلة من الخادم؛ لا تقرر أو تحسب سبب الحظر |
| تنصّت `StanzaLogger` الخاص بـ WaEnhancer وكسر تشفير E2E | تقرأ الوحدة stanzas داخل عملية العميل المفكوكة التشفير أصلًا؛ لا تهاجم تشفير Signal/Noise نفسه |
| تليمتري `safety-net-attestation` / التوقيع / مصدر التثبيت | موجودة وموثَّقة في `WA_CLIENT_INTEGRITY.md`؛ لا يضيف هذا التقرير آليات جديدة لها، بل يذكر فقط أن أيًا منها لا يمنع شيئًا |
| "غير موجود" في هذا التقرير | يعني الغياب من شيفرة Java/smali/السلاسل النصية المفكوكة لهذا الإصدار تحديدًا (2.26.41.6)؛ ليس زعمًا عن اكتشاف من جانب الخادم، وهو غير قابل للمراقبة سكونيًا |

---

## 8. التدفق من البداية إلى النهاية

```
[Device boots WhatsApp, possibly under a hook module or with a bundled crash-reporter lib]
    │
    ▼
[Cdt.C4k / C1Z / C10V]  Class.forName("org.acra.ACRA")
    │  success ──► is_whatsapp_plus_user = true ─► wam_daily
    │  success ──► "nw-wap" / "NW-WAP-1" ─► contact-us / debug-report text
    │  (no further branch — nothing reacts to this value in the client)
    ▼
[AbstractC38241gg / C27965CCj]  signature self-check → WAM 6251   (see WA_CLIENT_INTEGRITY.md §5)
[CHH]                           install-source flag  → WAM 10255  (see WA_CLIENT_INTEGRITY.md §5.4)
[C00L / Cdt]                    root / emulator / custom-ROM     → wam_daily  (see WA_CLIENT_INTEGRITY.md §6)
    │
    ▼
[WA telemetry backend]  (server-side use of all of the above: unknown, not observable)
    │
    ▼
[If the server bans the account]
    │  ban_violation_type / ban_violation_source / ban_violation_reason sent as intent extras
    ▼
[WfacBanActivity]  displays the server's values verbatim — no client-side cause mapping
```

```
[Attack surface, other side of the boundary — not WhatsApp code]
[Xposed/LSPosed host process: com.whatsapp]
    │
    ▼
[WaEnhancer module loads] ─ Unobfuscator resolves WhatsApp's classes at runtime
    │
    ├─► hooks presence methods ──────► ghost mode (WaGlobal.xml)
    ├─► hooks delete/read-receipt ───► shadow stores (MessageHistory.db, com_waenhancer_message_history.db)
    └─► taps stanza send/receive ────► wae_stanzas.txt (post-decryption plaintext)
```

---

## 9. المجاهيل

| السؤال | سبب كونه مجهولًا |
|----------|-------------|
| هل يستخدم الخادم `is_whatsapp_plus_user`، أو عدم تطابق التوقيع (6251)، أو مصدر التثبيت (10255)، أو أعلام الروت كمدخلات للحظر/درجة الثقة | من جانب الخادم، لم تُرصَد أي حركة شبكة |
| هل يوجد `org.acra.ACRA` فعلًا في إصدار WaEnhancer/GB WhatsApp حالي (أي هل الاستدلال الوحيد الموجود سينطلق أصلًا عليه) | غير محقَّق على إصدار تعديل فعلي في هذا التمرير |
| تخصيص اسم سبب الحظر لقيم `ban_violation_type` / `ban_violation_source` | لا تعداد (enum) محلول من جانب العميل؛ يحدده الخادم |
| هل يقوم أي كود أصلي (`libwhatsapp.so`، `libwasafe.so`) باكتشاف ربط/عبث بما يتجاوز ما وجده `WA_CLIENT_INTEGRITY.md` غائبًا فعلًا | لم تُعاد تتبّع المكتبات الأصلية المجرَّدة بشكل مستوفٍ لهذا التقرير بما يتجاوز بحث السلاسل في §3 |
| التعامل من جانب الخادم مع رؤية على طراز `wae_stanzas.txt` التي يتنصّت عليها WaEnhancer (أي هل يمكن للخادم تمييز عميل مربوط عن عميل حقيقي على مستوى البروتوكول) | غير قابل للمراقبة سكونيًا |
