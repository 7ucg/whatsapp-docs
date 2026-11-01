<!-- src-sha1: 3f456309f1ce11a70a08dd912d84e40193c760ad -->
# WhatsApp الحساب المُدار — Full RE Report
**الإصدار:** 2.26.41.6 | **التاريخ:** 2026-11-01
**النطاق:** نظام الإشراف الأبوي ("الحساب المُدار") الظاهر للعميل (ربط الراعي/التابع، الأدوار، تجربة العمر، رمز PIN، إعدادات الخصوصية، فكّ الربط، عمليات w:mex، التخزين المحلي، أعلام الميزات)؛ مجموعة الإشارات المنفصلة وغير المرتبطة الخاصة بأرقام الأعمال التي يديرها مزوّد حل أعمال (Business Solution Provider) عبر Cloud API (جهة إصدار شهادة الاسم الموثّق، حقول host-storage/actual-actors، واجهة التعايش (coexistence)، نوع حساب الاستضافة متعدد الأجهزة)؛ كيفية التمييز بين الاثنين

---

## 1. ماذا يعني "مُدار" في هذا العميل

نظامان غير مرتبطين في 2.26.41.6 يستخدمان لغة قد يسمّيها قارئ خارجي "حساب مُدار". لا يتشاركان شيفرة، ولا proto، ولا مخطط w:mex. جميع العبارات هي تحليل ساكن لملف APK المفكوك؛ لم يُلتقط شيء على الشبكة. المستوى: **found** = قُرئ في الشيفرة أو الأصول، **inferred** = مستنتَج من الشيفرة، **unknown** = لم يُحسم.

| النظام | الاسم (الأسماء) الداخلي في الشيفرة | ما الذي يُدار | أين | القسم |
|---|---|---|---|---|
| الإشراف الأبوي | `com.whatsapp.managedaccount.*`، `com.whatsapp.pma.*`، `com.whatsapp.pmta.*`؛ الأسماء الرمزية الداخلية **PAA**، **PMA**، **PMTA** (موجودة في أسماء الحزم/الأصناف/التفضيلات، ولم تُشرح قط في أي سلسلة نصية) | حساب WhatsApp الخاص بالقاصر ("التابع")، تحت إشراف حساب ولي/وصي ("الراعي") | `w:mex`، SQLite/SharedPrefs المحلية | 2-8 |
| تفويض رقم أعمال لمزوّد | لا توجد سلسلة "BSP" أو "tech provider" في أي مكان من العميل؛ تسمّيه الواجهة "خدمة آمنة من Meta" أو "شركات أخرى" | رقم WhatsApp **تجاري**، تُستضاف أو تُعالَج رسائله عبر بنية تحتية سحابية تابعة لـ Meta و/أو مزوّد خارجي، بدلًا من جهاز الشركة الخاص | شهادة الاسم الموثّق (`w:biz`)، نوع حساب "مُستضاف" متعدد الأجهزة | 9 |

موارد السلاسل النصية `str2fc9`/`str3139` ("Managed account")، و`str30ae`، و`str3109`، و`str439d`/`str439f` وشاشة الإعدادات التي تنتمي إليها هي **جميعها** تخص نظام الإشراف الأبوي (القسم 2). لا توجد تسمية "Managed account" في أي مكان من العميل لحالة شركة تديرها BSP؛ تلك الحالة تُشار إليها فقط من خلال حقول الشهادة ولافتات المحادثة/المكالمة (القسم 9). هذا هو التصحيح الأساسي الذي يجب إجراؤه قبل استخدام المصطلح: أي ملاحظة أو تذكرة هندسة عكسية تقول "حساب مُدار" عن رقم *تجاري* تتحدث عن القسم 9، لا عن أي شيء مُسمّى `ManagedAccount*` في الشيفرة.

---

## 2. الإشراف الأبوي: الأدوار وعلاقة الحساب

### 2.1 الأدوار

`EnumC08540Ng` (found)، مع تسمية تصحيح لكل قيمة:

| الدور | تسمية التصحيح | من |
|---|---|---|
| `NONE` | "None" | لا توجد علاقة إشراف |
| `DEPENDENT` | "Dependent" | حساب القاصر نفسه |
| `SPONSOR` | "Sponsor" | حساب الولي/الوصي |
| `SPONSOR_ADMIN` | "Sponsor Admin" | راعٍ بصلاحيات مرفوعة (الصلاحيات الإضافية الدقيقة لم تُتَتبَّع) |

دور الجهاز الحالي يُقرأ من الحالة المحلية بواسطة `SharedPreferencesOnSharedPreferenceChangeListenerC08490Nb.A04()` ويُخزَّن مؤقتًا بواسطة `C08530Nf` ("ManagedAccountStartupPreferences"، الاسم مُستنتَج من وسم السجل `ManagedAccountStartupPreferences/...`).

### 2.2 العلاقة بين حسابين، لا بين جهازين

للتابع **رقم هاتفه الخاص وتسجيل WhatsApp الكامل الخاص به** (جهازه الأساسي الخاص، وأجهزته المرافقة متعددة الأجهزة إن وُجدت). والراعي بالمثل حساب مسجَّل بشكل عادي ومستقل. ما يربطهما هو سجل من جانب الخادم، يُنسخ محليًا على الشكل:

```
ManagedAccountConnection(
  connectionLid,      // C14080dr — the dependent's LID, found
  role,                // EnumC08540Ng, found
  linkTs,              // long, link creation time, found
  connectionPnJid,     // PhoneUserJid — the dependent's phone-number JID, found
  graduationState,      // C4DV, section 2.3
  ageExperience)        // EnumC96934Gf, section 2.3
```

(`AnonymousClass586`، found؛ الحقول مؤكَّدة من `toString` الخاصة به.) لا يوجد رمز QR إقران، ولا توقيع ADV، ولا تبادل مفاتيح جهاز مرافق في أي مكان من هذه الحزمة — قارن بروتوكول الجهاز المرافق الفعلي في `WA_LINKED_DEVICE_PAIRING.md` القسم 5، وهو غير ذي صلة. نقطة دخول الإعداد الأولي هي رابط عميق (deep link) تُعالجه `ManagedAccountSponsorOnboardingViewModel` (الحزمة `managedaccount.deeplink`، found)، وليست تدفقًا يعتمد على المسح.

### 2.3 تجربة العمر والتخرُّج

`EnumC96934Gf` (found): ‏`UNKNOWN`، `U13`، `U16_BR`، `U18_BR`، `U18`، `STANDARD` (للبرازيل نطاقات عمرية خاصة بها). الدالة `A00()` في هذا التعداد تُعيد true لـ `U16_BR`، `U18_BR`، `U18` — الحالات التي تعدّها الشيفرة "على وشك الخروج من النطاق العمري".

`C4DV` (حالة التخرُّج، found): ‏`PRE_GRADUATION`، `GRADUATION`، `PRE_GRADUATION_IMMINENT`، `UNKNOWN`. يقوم `ManagedAccountGraduationManager` ومسار `triggerTeenGraduationEagerly` الخاص به (found) بنقل التابع خارج الإشراف مع اقترابه من/تجاوزه عتبة عمرية؛ يعرض `ManagedAccountPmtaSponsorGraduationNuxActivity` و`ManagedAccountSponsorGraduationNuxActivity` واجهة NUX الخاصة بالراعي لهذا الانتقال.

تُعيد `ManagedAccountLinkingRepository.A00` (found) جلب تجربة العمر عند تعارض HTTP 409 من استدعاء الربط، أي أن الخادم يمكنه رفض الربط لأن تجربة العمر المخزَّنة قديمة ويجب على العميل إعادة الاستعلام من `WaAgeExperienceRepository` قبل إعادة المحاولة.

---

## 3. تدفق الربط وعمليات w:mex

### 3.1 فهرس العمليات

جميع أسماء العمليات التسع وقيم `doc_id` أدناه قُرئت مباشرةً من `assets/whatsapp-android-mex_client_persist_ids.json` في هذا البناء (found) — وليست مُستنتَجة من عميل خارجي. المخطط للعمليات التسع هو `whatsapp-android-mex` (مفتاح الأصل: `whatsapp_mex`).

| العملية | doc_id | موقع الاستدعاء الموجود | المتغيرات (في هذا البناء) |
|---|---|---|---|
| `ManagedAccountInitiateLinkingQuery` | `26671873552498548` | `MexManagedAccountInitiateLinkingApi.A00` | `input:{"dummy": null}` — **لا يُرسَل `phone_number`**؛ أي افتراض سابق بأن هذا الاستدعاء يحمل رقم التابع لا ينطبق على موقع الاستدعاء هذا |
| `ManagedAccountQuery` | `27232244463035262` | `ManagedAccountStateSynchronizer.A01` | `input:{"unused": null}` — **لا يوجد `jid`**؛ الاستعلام مرتبط بالجلسة، وليس مُعامَلًا بـ JID في موقع الاستدعاء هذا |
| `ManagedAccountValidateLinkingQuery` | `35449808311284430` | مُشار إليه (تطابق اسم في الأصول)؛ المتغيرات لم تُتَتبَّع إلى موقع استدعاء في هذا البناء | unknown |
| `ManagedAccountAcceptLinkingMutation` | `26708926155457677` | مُشار إليه؛ المتغيرات لم تُتَتبَّع | unknown |
| `ManagedAccountCompleteLinkingMutation` | `26866501363013203` | مُشار إليه؛ المتغيرات لم تُتَتبَّع | unknown |
| `ManagedAccountRevokeLinkingMutation` | `27435058196100677` | مُشار إليه؛ المتغيرات لم تُتَتبَّع | unknown |
| `ManagedAccountSyncActivities` | `26594352680227840` | مُشار إليه؛ المتغيرات لم تُتَتبَّع | unknown |
| `ManagedAccountUpdatePinMutation` | `27653949584193082` | مُشار إليه؛ المتغيرات لم تُتَتبَّع | unknown |
| `ManagedAccountGetSponsorAgeVerificationInfoQuery` | `26433623289634522` | مُشار إليه؛ المتغيرات لم تُتَتبَّع | unknown |

نصوص الاستجابة خارج أغلفة النجاح/الخطأ العامة لم تُقرأ لأي من العمليات التسع؛ نتيجة نجاح `ManagedAccountInitiateLinkingQuery` (`C135065o7`، ونصّ `toString()` حرفيًا "PAA Initiate Linking Success"، found) تحمل سلسلتين نصيتين وعددًا صحيحًا لم تُحسم أسماء حقولها — على الأرجح رمز/رابط ربط عميق ومدة انتهاء صلاحية، لكن هذا استنتاج وليس قراءة من حقل مُسمّى.

يوجد مسار منفصل غير مرتبط بـ mex: يُحلِّل `C14E.java` (`PaaAcceptLinkingIBHandler`) stanza/إشعارًا واردًا يحمل خاصية `sponsor_jid` (found) — وهذا دفع من الخادم يُظهِر الواجهة، وليس طلب `AcceptLinkingMutation` نفسه.

### 3.2 إعادة المحاولة عند فشل التسليم

تُعيد `MexManagedAccountInitiateLinkingApi.A01` محاولة استدعاء initiate حتى عدد مرات يحدده المستدعي عند رمز الخطأ **471** ("delivery failure")، وتسجّل `MexManagedAccountInitiateLinkingApi/requestSponsorLinkingMaterial delivery failure, retrying` (found).

---

## 4. نموذج الجهاز/الجلسة

**لا يوجد ربط جهاز على طراز الجهاز المرافق** بين الراعي والتابع، ولا بين أي من الحسابين وأي بنية تحتية تابعة لـ WhatsApp. كل جانب هو حساب WhatsApp عادي، مسجَّل بشكل مستقل (رقم هاتفه الخاص، وجهازه الأساسي الخاص، وأجهزته المرافقة الاختيارية الخاصة تحت نظام تعدد الأجهزة العادي الموصوف في `WA_LINKED_DEVICE_PAIRING.md`). علاقة الإشراف هي سجل من جانب الخادم مفتاحه LID الخاص بالتابع وJID رقم هاتفه (القسم 2.2)، تُزامَن لكلا الجانبين عبر `w:mex`، وليست جلسة أو إقرانًا أو هوية ADV جديدة.

هذا اختلاف بنيوي عن حالة BSP/Cloud API في القسم 9، حيث "جهاز" الرقم التجاري ليس هاتفًا على الإطلاق — انظر القسم 9.3 لكيفية تمثيل ذلك في نموذج تعدد الأجهزة الحالي بدلًا من ذلك.

---

## 5. الإعدادات والصلاحيات

### 5.1 شاشة خصوصية التابع

تُجمِّع `DependentAccountPrivacyActivity` (found) الإعدادات في ثلاثة أقسام عبر التعداد `C9SE`:

| القسم | ثابت `C9SE` | المحتوى |
|---|---|---|
| الظهور | `VISIBILITY` (0) | من يمكنه رؤية معلومات ملف التابع |
| التواصل | `CONTACT` (1) | من يمكنه التواصل مع التابع |
| تحكُّم الراعي | `SPONSOR_CONTROL` (2) | إعدادات يتحكم بها الراعي، لا التابع |

تُحيل الشاشة إلى "أدوات التحكم الأبوي" عبر السلسلة `str2fc8`: *"Your account is managed by your parent or guardian. They can make changes in parental controls."* توجد بوابة تفضيل محلية لإحدى تلك الأدوات: `privacy_dependent_account_messages` (عدد صحيح، الافتراضي `1`)، تُقرأ بواسطة `C08520Ne.A06()` وتُستشار فقط عندما يكون الحساب راعيًا (found) — أي أن مَن يُسمَح له بمراسلة التابع شيء تتحكم فيه حالة تطبيق **الراعي**، لا قيمة يضبطها التابع.

### 5.2 أدوات تحكُّم الراعي

`SponsorControlsHubActivity` (found) هي مركز الراعي، تسرد التابعين (الجزء/وسم السجل "sponsor-controls-dependents") مع مُحوِّل صورة جهة اتصال لكل تابع. تفتح `SponsorControlsDependentInfoActivity` تفاصيل تابع واحد. تُهيّئ وتُسلِّم `ManageNotificationsActivity`/`ManageNotificationsFragment` وكذلك `ActivityAlertsFragment`/`ManagedAccountDependentActivityAlertHandler` **تنبيهات النشاط** — إشعارات إلى الراعي بشأن نشاط التابع في التطبيق (`ManagedAccountSyncActivities`، القسم 3.1، هو مصدر البيانات، محكوم بالعلم **31562** في `ManagedAccountAlertInfoActivity`، found).

### 5.3 رمز PIN

تُنفِّذ `SponsorPinSetupFragment`، و`SponsorPinConfirmFragment`، و`ManagedAccountChangePinActivity`/`ManagedAccountChangePinFragment`/`ManagedAccountConfirmChangePinFragment` (found، بوجود الصنف) إنشاء وتغيير رمز PIN الذي يحدده الراعي؛ الطفرة (mutation) هي `ManagedAccountUpdatePinMutation` (القسم 3.1؛ أسماء حقلَي `old_pin`/`new_pin` الدقيقة غير مؤكَّدة في هذا البناء — unknown). يمكن لمزامنة جانب التابع أن تفشل خصيصًا بسبب غياب رمز PIN: تسجّل `ManagedAccountStateSynchronizer` العبارة "ManagedAccountStateSynchronizer/fetchAndSync missing sponsor PIN for child user" وتُعيد نتيجة خطأ عندما يكون نوع استجابة الخادم `C135095oA` (found) — أي أن مزامنة حالة التابع تعتمد على ضبط الراعي لرمز PIN.

### 5.4 فكّ الربط

تُظهِر `ManagedAccountUnlinkAccountSettingsActivity` (found) واحدًا من عدة نصوص تأكيد حسب الأعلام المحمولة في وسائط الجزء: `is_pmta` (نسخة فرعية "PMTA" مميَّزة)، و`is_teen_dependent`، وما إن كان للتابع اسم عرض — السلاسل `str49cb`…`str49d3`، مثل: *"Your account will no longer be managed by %1$s"* / *"...by your parent"*. تُعدّ `ManagedAccountRevokeLinkingMutation` (القسم 3.1) عملية الاتصال المُستنتَجة التي تدعم هذا الإجراء؛ لم يُتَتبَّع استدعاء النشاط نفسه لها مباشرةً في هذه الجولة.

### 5.5 بوابة إعادة التحقق

تستضيف `ManagedAccountAuthInterstitialActivity` الجزء `PmaAuthInterstitialFragment` (الحزمة `com.whatsapp.pma.product.dependent.fragments`، found) وتُشغَّل بسلسلة `extra_auth_entry_point` — خطوة إعادة تحقق تحكم الدخول إلى شاشات الحساب المُدار من نقطة دخول معيَّنة. آلية التحقق الدقيقة (رمز PIN للجهاز، البصمة الحيوية، كلمة مرور الحساب) لم تُتَتبَّع.

### 5.6 واجهات تصحيح

توجد `ManagedAccountDebugConnectionActivity` و`ManagedAccountDebugPinAuthActivity` في هذا البناء (found). لا شيء في هذه الجولة يحدد ما إن كانت قابلة للوصول من واجهة الإصدار أو من علم بناء داخلي/تصحيح فقط (inferred: تصحيح فقط، حسب اصطلاح التسمية وعدم وجود أي مسار تشغيل مُكتشَف من شاشات الإصدار).

---

## 6. التخزين

| المخزن | المفاتيح/الأعمدة | المحتوى |
|---|---|---|
| سجل العلاقة المحلي | `connectionLid`، `role`، `linkTs`، `connectionPnJid`، `graduationState`، `ageExperience` (القسم 2.2) | صف واحد لكل اتصال راعٍ↔تابع |
| SharedPrefs | `paa_graduation_nux_pending`، `paa_sponsor_blocked`، `paa_nux_education_banner_dismissed`، `paa_nux_education_banner_start_timestamp`، `paa_review_privacy_settings_banner_dismissed_dependent_<lid>`، `privacy_dependent_account_messages` | حالة رفض NUX/اللافتات، وعلم حظر الراعي، وبوابة المراسلة الوحيدة المؤكَّدة للتابع |

جميع المفاتيح موجودة حرفيًا في `C08530Nf`، و`ManagedAccountBannerManager`، و`C08520Ne`.

---

## 7. سلاسل مؤشرات الواجهة

| معرّف السلسلة | النص | أين تُستخدم |
|---|---|---|
| `str2629` | "Create a parent-managed account" | نقطة دخول الإعداد الأولي |
| `str2fc9` / `str3139` | "Managed account" | شارة/تسمية |
| `str30ae` | "Managed accounts can't see this message. Learn why" | محتوى مقيَّد |
| `str3109` | "This is a managed account. Learn more" | إشعار محادثة/ملف تعريف |
| `str3751` / `str3752` / `str3754` | رسائل عدم الأهلية ("isn't eligible for a parent-managed account"، "Couldn't create parent-managed account") | فشل الإعداد الأولي |
| `str439d` / `str439f` | "Settings for managed accounts" / "View activity and choose settings for managed accounts" | نقطة دخول الإعدادات |
| `str2fc8` | "Your account is managed by your parent or guardian..." | `DependentAccountPrivacyActivity` |
| `str49cb`-`str49d3` | نُسَخ تأكيد فكّ الربط | `ManagedAccountUnlinkAccountSettingsActivity` |

تدعم `ManagedAccountNotAvailableActivity` و`ManagedAccountAgeUnknownActivity` (found بوجود اسم الصنف) حالتين إضافيتين — عدم توفُّر الميزة، وعدم تحديد عمر الحساب — النص الدقيق لم يُحسم.

---

## 8. أعلام الميزات

| المعرّف | أين | يتحكَّم بـ |
|---|---|---|
| **30174** | `C08520Ne.A02`، `ManagedAccountSponsorUpsellActivity` | أهلية ترقية الراعي (sponsor-upsell) |
| **31562** | `ManagedAccountAlertInfoActivity` | بوابة ميزة تنبيهات النشاط |
| **34268** | `C08520Ne.A01` | فحص صلاحية إضافي (الدور غير محسوم خارج البوابة نفسها) |
| **16763** | `C08520Ne.A04` | بوابة بوليانية غير محسومة |
| **33355** | `C08520Ne.A05` | بوابة بوليانية غير محسومة، مشروطة بالتابع أو واجهة ثانوية |

---

## 9. أرقام الأعمال المُفوَّضة لمزوّد (Cloud API / BSP)

هذا هو النظام الذي يقابل فعليًا "حساب أعمال يُشغَّل بالوكالة (on-behalf-of) من قِبل مزوّد". لا يتشارك أي صنف أو proto أو مخطط w:mex مع القسم 2-8. لا توجد سلسلة نصية في هذا البناء تقول "BSP" أو "tech provider" أو "Business Solution Provider" أو "on-premises API" أو "Cloud API" للمستخدم؛ الإشارة بنيوية.

### 9.1 شهادة الاسم الموثّق: بادئة الجهة المُصدِرة وPrivacyMode

يخزِّن العميل سجل شهادة اسم موثّق محلي لكل JID تجاري بالأعمدة (found، `AbstractC218419al`): ‏`verified_name`، `industry`، `city`، `country`، `verified_level`، `cert_blob`، `identity_unconfirmed_since`، `host_storage`، `actual_actors`، `privacy_mode_ts`. تُحلَّل هذه الحقول الثلاثة الأخيرة من عنصر ابن على طراز `<biz host_storage="" actual_actors="" privacy_mode_ts=""/>` في stanza من نوع `w:biz` (found، عدة مواقع استدعاء، مثل `O0F.java`، `C18670m9.java`، `AbstractC24816AmW.java`) إلى `AnonymousClass118` ("`PrivacyMode`" حسب `toString()` الخاصة به)، وحقلاها الصحيحان هما:

| الحقل | القيم المرصودة في الشيفرة | المعنى |
|---|---|---|
| `hostStorage` | 0 (افتراضي/غير مضبوط)، 1، 2 | البنية التحتية التي تخزِّن/تُرحِّل رسائل الشركة؛ ربط **مُستنتَج** بمصطلحات WhatsApp Business Platform العامة: on-premises (مُستضاف ذاتيًا) مقابل Meta-hosted (Cloud API) مقابل حالة ثالثة انتقالية/مزدوجة — لا توجد ثوابت مُسمّاة في هذا العميل لهذه القيم الثلاث |
| `actualActors` | 0 (افتراضي/غير مضبوط)، 1، 2 | من يُشغِّل الحساب فعليًا يوميًا؛ ربط **مُستنتَج** بـ self-operated مقابل operated by a provider — مرة أخرى لا توجد ثوابت مُسمّاة في هذا العميل |

إشارة ثانية مكتشَفة بشكل مستقل على نفس غلاف الشهادة (`AnonymousClass119.A02()`/`A03()`) تقرأ سلسلة **الجهة المُصدِرة** للشهادة (الحقل `A07`) وتصنّفها حسب البادئة (found، الشيفرة الحرفية):

```java
public boolean A01() { return this.A01 == 2; }        // hostStorage == 2
public boolean A02() { return this.A07 != null && this.A07.startsWith("ent:"); }
public boolean A03() { return this.A07 != null && this.A07.startsWith("smb:"); }
```

‏`"ent:"` و`"smb:"` هما بادئتا الجهة المُصدِرة الوحيدتان اللتان يميّز بينهما هذا العميل (found، سلاسل حرفية). تطابق `smb:` شهادة صادرة لتطبيق WhatsApp Business العادي ذاتي التشغيل؛ وتطابق `ent:` شهادة صادرة لمسار مؤسسي متكامل مع API — وهذا أقرب مكافئ من الدرجة الأولى، على مستوى الشيفرة، لـ "حساب أعمال مُدار ذاتيًا" مقابل "حساب أعمال مُدار من BSP/Cloud API" (ربط البادئتين بهاتين الفئتين الحقيقيتين **مُستنتَج** من البادئتين نفسهما ومن كيفية استهلاكهما في `AbstractC198638cc.A00`، لا من أي سلسلة توثيق داخل العميل).

تُدمِج `AbstractC198638cc.A00` فحص الجهة المُصدِرة وقيمة بوليانية منفصلة (`A09`، معناها غير محسوم — ربما "الشهادة مفقودة/مُلغاة"، بما يتوافق مع نص "no longer an official business account" الظاهر للمستخدم في القسم 9.2) في رمز "client" بأربع قيم (found):

```java
public static final int A00(AnonymousClass119 c) {
    if (c != null) {
        if (c.A09) return 4;
        if (c.A03()) return 2;   // smb: issuer
        if (c.A02()) return 3;   // ent: issuer
    }
    return 1;                    // default / no certificate
}
```

### 9.2 لافتات التعايش ومعرّف `business_state_id`

تجمع `C198628cb` ("`BusinessState`" حسب `toString()` الخاصة بها) بين `PrivacyMode` الخاصة بالشهادة (القسم 9.1)، ورمز "client" ذا الأربع قيم، وقيمة بوليانية `isVerified` في عدد صحيح واحد مُسطَّح تسمّيه الواجهة `business_state_id` (found، يُضبط من `c198628cb.A02()` في `EncryptionChangeDialogFragment` ويُقرأ بالطريقة نفسها في `PrivacyInfoBottomSheet`/`ContactInfoActivity`). تطابق دالة الربط 18 مجموعة (tuple) صريحة من الشكل `(client, actualActors, hostStorage, flag)` مع معرّفات من **0 إلى 17**؛ تعذَّر إعادة بناء الجدول الكامل (يُظهِر JADX خطأ تجاوز منطقة (region-overflow) على هذه الدالة بالتحديد، وعدة فروع مُدمَجة من قِبل المُفكِّك)، لكن ما يلي مؤكَّد مباشرةً من الشيفرة:

- المعرّف **15** يُبلَغ إليه دائمًا عندما يساوي رمز "client" القيمة 4 (الشهادة مفقودة/مُلغاة)، بصرف النظر عن الحقول الأخرى.
- المعرّفات **5، 6، 9، 10** هي المعرّفات الوحيدة القابلة للوصول عندما تكون دالة بوابة جانبية `A05()` (فحص على طراز حظر/إسكات غير مرتبط بالمحادثة) صحيحة، وهي قابلة للوصول أيضًا عبر المسار العادي عندما تكون `hostStorage == 2` — وتُشغِّل باستمرار نصوص *"This business uses a secure service from Meta to manage this chat/call"* البسيطة (`str080d`/`str080f`/`str0c9c`/`str0f5a`، found، مواقع استدعاء مؤكَّدة بمعرّف المورد في `C23324A5w`/`ContactInfoActivity`).
- المعرّفان **16** و**17** هما الحالتان المتبقيتان (لا تطابقان مجموعة معروفة ولا المعرّف 15) وتُشغِّلان عائلة نصوص "multiple tools" / "no longer an official business account" (`str38ef`-`str38fb`، `str08b3`-`str08c7`): *"This business has chosen to use multiple tools to chat with its customers... Chats between only you and this business are managed by a secure service from Meta... this business is using the WhatsApp Business app"* — أي حالة **التعايش (coexistence)**، حيث يمكن الوصول إلى الرقم عبر تطبيق Business على جهاز وعبر مسار مُستضاف بـ API في الوقت نفسه، محكومة بالأعلام **12729**، **18047**، **23933**، **7131**، **29343** (found، في `PrivacyInfoBottomSheet`/`ContactInfoActivity`، يختار كل منها بين زوج نص أقدم وأحدث للحالة نفسها).

يمكن لنتيجة IQ الخاصة بـ `remove-companion-device` في تدفق تعدد الأجهزة غير المرتبط أن تحمل عنصرًا ابنًا `coex_token` (`WA_LINKED_DEVICE_PAIRING.md` §7.1) — نفس مفهوم "التعايش"، ولم يُتَتبَّع المستهلِك من ذلك الجانب أيضًا.

### 9.3 نموذج الجهاز/الجلسة لرقم مُستضاف من قِبل مزوّد

رقم تجاري مُستضاف بالكامل من Meta (حالة Cloud API بلا جهاز فعلي على الإطلاق) يُمثَّل داخل نظام تعدد الأجهزة **الحالي**، لا نظام جديد:

- نوع الحساب `HOSTED` (‏`EnumC32116E1o`، القيمة 1) ومعرّف الجهاز **99** محجوزان لهذه الحالة (`WA_LINKED_DEVICE_PAIRING.md` §5.1، §9.2).
- تعداد `companion-props.platformType` الذي يخزِّنه الجهاز الأساسي لأجهزته المرافقة الخاصة يتضمَّن القيمة **23 = `CLOUD_API`** (`WA_LINKED_DEVICE_PAIRING.md` §6.2)، إلى جانب **27 = `BUSINESS_BACK_OFFICE`** و**25/26 = `WAIL`/`WASS`** — جميعها أنواع منصات بنية تحتية للأعمال تقع في التعداد نفسه الذي يضم الهواتف وأجهزة سطح المكتب والويب العادية.
- يَرفُض بناء المستهلك في هذا التقرير فعليًا إقران جهاز مُستضاف من جانب الجهاز الأساسي (رمز خطأ محلي **-10**، `WA_LINKED_DEVICE_PAIRING.md` §3.2) — توفير الاستضافة/Cloud API ليس شيئًا يبدؤه هذا العميل؛ فهو فقط يرصد نوع الحساب ومؤشرات المنصة الناتجة على الحسابات التي لديها ذلك مسبقًا.

لم يُعثَر على أي إقران أو توقيع ADV أو تدفق مفتاح جهاز مرافق لعلاقة BSP/Cloud API نفسها في أي مكان من هذا APK؛ آلية المستخدم القانوني/كلمة المرور لأمان الحساب (`WA_ACCOUNT_SECURITY.md`) وآلية هوية تعدد الأجهزة كلاهما غير مرتبط بكيفية تولّي BSP تشغيل رقم ما — يحدث ذلك التوفير بالكامل من جانب الخادم / على منصة أعمال Meta ولا يترك أثرًا في هذا العميل سوى المؤشرات أعلاه.

### 9.4 التيليمتري

تحمل مناسبة التسجيل `wam_ts_navigation` (‏`C1EO`، found) ثلاث قيم بوليانية مستقلة لسياق الأعمال لكل عملية تنقُّل مُسجَّلة: `is_cloudapi`، `is_onpremises`، `is_smb`، إضافةً إلى `is_canonical_ent_present` و`is_meta_ai_thread`. تحمل `ChatDescription` (‏`com.whatsapp.gapenforcement.dto`) بشكل منفصل `isEnterpriseBusiness`. لا يُظهِر أي من الصنفين كيف تُحسَب هذه القيم البوليانية خارج ما يصفه القسم 9.1/9.2 أصلًا؛ وهي للتقرير فقط ولا تحكم أي سلوك ظاهر للمستخدم في الملفات المقروءة.

---

## 10. الفروق الأساسية

| أ | ب |
|---|---|
| "حساب مُدار" (‏`ManagedAccount*`، PAA/PMA/PMTA) — **حساب قاصر خاص به**، تحت إشراف ولي | رقم تجاري **يُشغِّله مزوّد** عبر Cloud API — لا توجد تسمية "managed account" في أي مكان لهذه الحالة |
| ربط راعٍ/تابع: حسابان WhatsApp مستقلان مسجَّلان بشكل عادي، بلا إقران جهاز | رقم تجاري مُستضاف: حساب واحد، `accountType=HOSTED`، معرّف الجهاز 99، بلا جهاز مرافق على الإطلاق |
| عمليات `w:mex` من نوع `ManagedAccount*`، مخطط `whatsapp-android-mex` (القسم 3.1) | حقول شهادة الاسم الموثّق عبر `w:biz` (‏`host_storage`، `actual_actors`) — stanza مختلفة، مخطط مختلف |
| لافتات تعايش `business_state_id` (تطبيق Business مُدار ذاتيًا **و**مُستضاف عبر API في الوقت نفسه) | أعمال مُدارة ذاتيًا بالكامل (تطبيق WhatsApp Business العادي على جهازه الخاص، بادئة الجهة المُصدِرة `smb:`) |
| علم تيليمتري `is_smb` (شركة صغيرة/متوسطة تستخدم تطبيق Business) | أعلام تيليمتري `is_cloudapi` / `is_onpremises` (استضافة من جانب API) |
| `ManagedAccountRevokeLinkingMutation` (ينهي الإشراف الأبوي) | `remove-companion-device` (غير مرتبط: يزيل جهازًا مرافقًا؛ انظر `WA_LINKED_DEVICE_PAIRING.md` §7) |

---

## 11. التدفقات الكاملة

### 11.1 الإشراف الأبوي: ربط تابع

```
[Sponsor]                                  [Server]                         [Dependent]
   │ deep link / in-app entry                  │                                 │
   ▼                                            │                                 │
ManagedAccountInitiateLinkingQuery (no vars) ──►│
   │◄── linking material (token/URL, expiry)    │
   │  share with dependent (deep link / code)   │
   │                                            │                                 │
   │                                            │◄── dependent opens link ───────│
   │                                            │   ManagedAccountValidateLinkingQuery {linking_token, sponsor_jid} (assets; call site not traced)
   │                                            │   ManagedAccountAcceptLinkingMutation {linking_token} (assets; call site not traced)
   │◄── notification: sponsor_jid (PaaAcceptLinkingIBHandler) ────────────────────│
   │                                            │   ManagedAccountCompleteLinkingMutation {linking_token} (assets; call site not traced)
   ▼                                            │                                 ▼
local ManagedAccountConnection row created on both sides (role=SPONSOR / DEPENDENT, connectionLid, connectionPnJid, linkTs)
   │                                            │                                 │
   ▼                                            │                                 ▼
periodic ManagedAccountQuery (no vars) + ManagedAccountSyncActivities ──────────► sponsor controls hub / activity alerts
```

### 11.2 رقم تجاري مُفوَّض لمزوّد: ما يراه عميل الطرف الآخر

```
[Peer opens a chat/profile/call with the business number]
   │
   ▼
local verified-name cert for that JID: host_storage, actual_actors, privacy_mode_ts, issuer (smb:/ent:)
   │
   ▼
C198628cb.A02() → business_state_id (0-17)
   │
   ├─ id 15 (certificate missing/revoked)          → "no longer an official business account" (str08b3 family)
   ├─ ids 5/6/9/10 (hostStorage==2, or chat-gated)  → "uses a secure service from Meta to manage this chat/call" (str080d/f family)
   └─ ids 16/17 (coexistence residual states)       → "uses multiple tools... Business app AND a secure service from Meta" (str38ef-fb family)
```

---

## 12. المجاهيل

| الموضوع | السبب |
|---|---|
| جدول `business_state_id`←tuple الكامل (جميع القيم 18) | خطأ تجاوز منطقة من المُفكِّك على `C198628cb.A02()`؛ عدة فروع مُدمَجة |
| المعنى العددي الدقيق لـ `hostStorage`/`actualActors` خارج بديل بادئة الجهة المُصدِرة `smb:`/`ent:` | لا توجد ثوابت مُسمّاة في هذا العميل؛ الربط بمصطلحات on-premises/Cloud-API/BSP مُستنتَج من مصطلحات WhatsApp Business Platform العامة، لا من الشيفرة |
| متغيرات/حقول استجابة `ManagedAccountValidateLinkingQuery`، `AcceptLinkingMutation`، `CompleteLinkingMutation`، `RevokeLinkingMutation`، `SyncActivities`، `UpdatePinMutation`، `GetSponsorAgeVerificationInfoQuery` | معرّفات doc_id مؤكَّدة في الأصول؛ لم يُعثَر على موقع استدعاء بأسماء متغيرات في هذا البناء |
| معنى القيمة البوليانية `A09` المُغذِّية لرمز "client" رقم 4 | تُستهلَك كبوابة فقط؛ لا اسم ولا تعليق |
| الصلاحيات الإضافية لـ `SPONSOR_ADMIN` مقابل `SPONSOR` | الدور موجود؛ السلوك المُفرِّق لم يُتَتبَّع |
| توسيع الأسماء الرمزية PAA / PMA / PMTA | لم تُشرح قط في سلاسل نصية أو تعليقات؛ سياق الاستخدام فقط |
| إمكانية الوصول إلى `ManagedAccountDebugConnectionActivity`/`DebugPinAuthActivity` من بناءات الإصدار | التسمية تشير إلى تصحيح فقط؛ لم يُعثَر على مسار تشغيل في أي اتجاه |
| التوفير من جانب الخادم لرقم مُستضاف عبر Cloud API (القسم 9.3) | يحدث بالكامل من جانب الخادم؛ هذا العميل لا يبدؤه مطلقًا ويرصد فقط المؤشرات الناتجة |
| ما إن كانت أي شيفرة في العميل قادرة على تمييز "تُشغِّله Meta مباشرةً" عن "يُشغِّله مزوّد BSP خارجي عبر Cloud API من Meta" | كلتا الحالتين تنهاران على ما يبدو في إشارات `hostStorage`/`actualActors`/نوع المنصة نفسها؛ لم يُعثَر على حقل مُعرِّف BSP منفصل |
| حركة المرور الفعلية | تحليل ساكن فقط |
