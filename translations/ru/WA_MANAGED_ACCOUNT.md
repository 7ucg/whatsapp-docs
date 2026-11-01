<!-- src-sha1: 3f456309f1ce11a70a08dd912d84e40193c760ad -->
# WhatsApp Управляемый аккаунт — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-11-01
**Область:** видимая клиенту система родительского контроля «managed account» (привязка sponsor/dependent, роли, age experience, PIN, настройки приватности, отвязка, операции w:mex, локальное хранение, feature flags); отдельный, не связанный набор сигналов для бизнес-номеров, которыми управляет Business Solution Provider через Cloud API (issuer сертификата verified-name, поля host-storage/actual-actors, coexistence UI, тип аккаунта hosted multi-device); как эти два различаются

---

## 1. Что в этом клиенте означает «managed»

В 2.26.41.6 есть две не связанные между собой системы, которые внешний читатель назвал бы «managed account». Они не делят ни код, ни proto, ни схему w:mex. Все утверждения — статический анализ декомпилированного APK; на проводе ничего не захватывалось. Уровни: **found** = прочитано в коде или assets, **inferred** = выведено из кода, **unknown** = не выяснено.

| Система | Внутреннее название(я) в коде | Что здесь «managed» | Где | Раздел |
|---|---|---|---|---|
| Родительский контроль | `com.whatsapp.managedaccount.*`, `com.whatsapp.pma.*`, `com.whatsapp.pmta.*`; внутренние кодовые названия **PAA**, **PMA**, **PMTA** (found в именах пакетов/классов/preferences, никогда не раскрываются в строках) | собственный аккаунт WhatsApp несовершеннолетнего («dependent»), под контролем аккаунта родителя/опекуна («sponsor») | `w:mex`, локальные SQLite/SharedPrefs | 2-8 |
| Делегирование бизнес-номера провайдеру | в клиенте нигде нет строки «BSP» или «tech provider»; UI называет это «a secure service from Meta» или «other companies» | номер WhatsApp **бизнеса**, чьи сообщения хостятся/обрабатываются облачной инфраструктурой Meta и/или сторонним провайдером вместо собственного устройства бизнеса | сертификат verified-name (`w:biz`), тип аккаунта multi-device «hosted» | 9 |

Строковые ресурсы `str2fc9`/`str3139` ("Managed account"), `str30ae`, `str3109`, `str439d`/`str439f` и экран настроек, к которому они относятся, — **все** относятся к родительской системе (раздел 2). Нигде в клиенте нет метки "Managed account" для бизнеса, которым управляет BSP; этот случай сигнализируется исключительно полями сертификата и баннерами чата/звонка (раздел 9). Это ключевая поправка, которую нужно сделать перед использованием термина: заметка по реверс-инжинирингу или тикет, где говорится "managed account" про номер *бизнеса*, имеет в виду раздел 9, а не что-либо с именем `ManagedAccount*` в коде.

---

## 2. Родительский контроль: роли и связь аккаунтов

### 2.1 Роли

`EnumC08540Ng` (found), с debug-меткой для каждой константы:

| Роль | Debug-метка | Кто |
|---|---|---|
| `NONE` | "None" | нет отношения контроля |
| `DEPENDENT` | "Dependent" | собственный аккаунт несовершеннолетнего |
| `SPONSOR` | "Sponsor" | аккаунт родителя/опекуна |
| `SPONSOR_ADMIN` | "Sponsor Admin" | sponsor с расширенными правами (точные дополнительные права не прослежены) |

Роль текущего устройства считывается из локального состояния методом `SharedPreferencesOnSharedPreferenceChangeListenerC08490Nb.A04()` и кэшируется `C08530Nf` ("ManagedAccountStartupPreferences", имя выведено (inferred) из его лог-тега `ManagedAccountStartupPreferences/...`).

### 2.2 Связь — между аккаунтами, а не между устройствами

У dependent есть **свой собственный номер телефона и своя полноценная регистрация WhatsApp** (своё основное устройство, свои companion-устройства multi-device, если они есть). Sponsor аналогично — обычный, независимо зарегистрированный аккаунт. Их связывает серверная запись, которая локально отражается как:

```
ManagedAccountConnection(
  connectionLid,      // C14080dr — the dependent's LID, found
  role,                // EnumC08540Ng, found
  linkTs,              // long, link creation time, found
  connectionPnJid,     // PhoneUserJid — the dependent's phone-number JID, found
  graduationState,      // C4DV, section 2.3
  ageExperience)        // EnumC96934Gf, section 2.3
```

(`AnonymousClass586`, found; поля подтверждены его `toString`.) В этом пакете нигде нет pairing QR, ADV-подписи, обмена companion-ключами — сравните с реальным протоколом companion-устройств в `WA_LINKED_DEVICE_PAIRING.md`, раздел 5, который не связан с этим. Точка входа онбординга — deep link, обрабатываемый `ManagedAccountSponsorOnboardingViewModel` (пакет `managedaccount.deeplink`, found), а не поток на основе сканирования.

### 2.3 Age experience и graduation

`EnumC96934Gf` (found): `UNKNOWN`, `U13`, `U16_BR`, `U18_BR`, `U18`, `STANDARD` (у Бразилии свои возрастные диапазоны). `A00()` для этого enum возвращает true для `U16_BR`, `U18_BR`, `U18` — состояний, которые код считает «приближающимися к выходу из возрастных ограничений».

`C4DV` (graduation state, found): `PRE_GRADUATION`, `GRADUATION`, `PRE_GRADUATION_IMMINENT`, `UNKNOWN`. `ManagedAccountGraduationManager` и его путь `triggerTeenGraduationEagerly` (found) выводят dependent из-под контроля по мере приближения к возрастному порогу или его пересечения; `ManagedAccountPmtaSponsorGraduationNuxActivity` и `ManagedAccountSponsorGraduationNuxActivity` показывают sponsor-сторонний NUX для этого перехода.

`ManagedAccountLinkingRepository.A00` (found) повторно запрашивает age experience при HTTP-конфликте 409 от вызова linking, т.е. сервер может отклонить linking, потому что сохранённый age experience устарел, и клиент должен повторно запросить `WaAgeExperienceRepository` перед повторной попыткой.

---

## 3. Поток linking и операции w:mex

### 3.1 Каталог операций

Все девять имён операций и значения `doc_id` ниже прочитаны напрямую из `assets/whatsapp-android-mex_client_persist_ids.json` в этой сборке (found) — не выведены из стороннего клиента. Схема для всех девяти — `whatsapp-android-mex` (ключ asset: `whatsapp_mex`).

| Операция | doc_id | Место вызова найдено | Переменные (в этой сборке) |
|---|---|---|---|
| `ManagedAccountInitiateLinkingQuery` | `26671873552498548` | `MexManagedAccountInitiateLinkingApi.A00` | `input:{"dummy": null}` — **`phone_number` не передаётся**; предыдущее предположение, что этот вызов несёт номер dependent, не подтверждается для данного места вызова |
| `ManagedAccountQuery` | `27232244463035262` | `ManagedAccountStateSynchronizer.A01` | `input:{"unused": null}` — **`jid` отсутствует**; запрос привязан к сессии, а не параметризован JID в этом месте вызова |
| `ManagedAccountValidateLinkingQuery` | `35449808311284430` | упомянут (совпадение по имени в assets); переменные не прослежены до места вызова в этой сборке | unknown |
| `ManagedAccountAcceptLinkingMutation` | `26708926155457677` | упомянут; переменные не прослежены | unknown |
| `ManagedAccountCompleteLinkingMutation` | `26866501363013203` | упомянут; переменные не прослежены | unknown |
| `ManagedAccountRevokeLinkingMutation` | `27435058196100677` | упомянут; переменные не прослежены | unknown |
| `ManagedAccountSyncActivities` | `26594352680227840` | упомянут; переменные не прослежены | unknown |
| `ManagedAccountUpdatePinMutation` | `27653949584193082` | упомянут; переменные не прослежены | unknown |
| `ManagedAccountGetSponsorAgeVerificationInfoQuery` | `26433623289634522` | упомянут; переменные не прослежены | unknown |

Тела ответов за пределами общих success/error-оболочек не были прочитаны ни для одной из девяти; результат успеха `ManagedAccountInitiateLinkingQuery` (`C135065o7`, `toString()` буквально `"PAA Initiate Linking Success"`, found) несёт две строки и int, имена полей которых не определены — почти наверняка это linking-токен/deep-link URL и срок действия, но это inferred, а не прочитано из именованного поля.

Существует отдельный, не-mex путь: `C14E.java` (`PaaAcceptLinkingIBHandler`) разбирает входящую станзу/уведомление, несущее атрибут `sponsor_jid` (found) — это серверный push, который вызывает UI, а не собственный запрос `AcceptLinkingMutation`.

### 3.2 Повтор при ошибке доставки

`MexManagedAccountInitiateLinkingApi.A01` повторяет вызов initiate до заданного вызывающей стороной количества раз при коде ошибки **471** ("delivery failure"), логируя `MexManagedAccountInitiateLinkingApi/requestSponsorLinkingMaterial delivery failure, retrying` (found).

---

## 4. Модель устройства/сессии

Между sponsor и dependent **нет связи устройств companion-типа**, и нет её между любым из аккаунтов и какой-либо инфраструктурой, управляемой WhatsApp. Каждая сторона — обычный, независимо зарегистрированный аккаунт WhatsApp (свой номер телефона, своё основное устройство, свои опциональные linked-устройства в рамках обычной системы multi-device, описанной в `WA_LINKED_DEVICE_PAIRING.md`). Отношение контроля — это серверная запись, ключом которой служат LID и phone-number JID dependent (раздел 2.2), синхронизируемая на обе стороны через `w:mex`, а не новая сессия, pairing или ADV-идентичность.

Это структурное отличие от случая BSP/Cloud-API в разделе 9, где «устройство» бизнес-номера — это вообще не телефон; см. раздел 9.3 о том, как это представлено в существующей модели multi-device.

---

## 5. Настройки и права

### 5.1 Экран приватности на стороне dependent

`DependentAccountPrivacyActivity` (found) группирует настройки в три раздела через enum `C9SE`:

| Раздел | Константа `C9SE` | Содержимое |
|---|---|---|
| Видимость | `VISIBILITY` (0) | кто может видеть информацию профиля dependent |
| Контакт | `CONTACT` (1) | кто может связаться с dependent |
| Контроль sponsor | `SPONSOR_CONTROL` (2) | настройки, которые контролирует sponsor, а не dependent |

Экран ведёт к «parental controls» через строку `str2fc8`: *"Your account is managed by your parent or guardian. They can make changes in parental controls."* Для одного такого элемента управления существует локальный pref-гейт: `privacy_dependent_account_messages` (int, default `1`), считывается `C08520Ne.A06()` и учитывается только когда аккаунт является sponsor (found) — т.е. кто может писать dependent, определяется состоянием приложения **sponsor**, а не значением, которое задаёт dependent.

### 5.2 Элементы управления на стороне sponsor

`SponsorControlsHubActivity` (found) — это хаб sponsor, показывающий список dependent (fragment/лог-тег `"sponsor-controls-dependents"`) с адаптером фото контакта для каждого dependent. `SponsorControlsDependentInfoActivity` открывает детали одного dependent. `ManageNotificationsActivity` / `ManageNotificationsFragment` и `ActivityAlertsFragment` / `ManagedAccountDependentActivityAlertHandler` настраивают и доставляют **activity alerts** — уведомления sponsor об активности dependent в приложении (`ManagedAccountSyncActivities`, раздел 3.1, — источник данных, за флагом **31562** в `ManagedAccountAlertInfoActivity`, found).

### 5.3 PIN

`SponsorPinSetupFragment`, `SponsorPinConfirmFragment`, `ManagedAccountChangePinActivity`/`ManagedAccountChangePinFragment`/`ManagedAccountConfirmChangePinFragment` (found, по наличию класса) реализуют создание и смену PIN, задаваемого sponsor; мутация — `ManagedAccountUpdatePinMutation` (раздел 3.1; точные имена полей `old_pin`/`new_pin` не подтверждены в этой сборке — unknown). Синхронизация на стороне dependent может провалиться именно из-за отсутствующего PIN: `ManagedAccountStateSynchronizer` логирует `"ManagedAccountStateSynchronizer/fetchAndSync missing sponsor PIN for child user"` и возвращает результат с ошибкой, когда тип сервера/ответа — `C135095oA` (found) — синхронизация состояния dependent зависит от того, задан ли PIN у sponsor.

### 5.4 Отвязка (Unlink)

`ManagedAccountUnlinkAccountSettingsActivity` (found) показывает один из нескольких текстов подтверждения в зависимости от флагов, переданных в аргументах fragment: `is_pmta` (отдельный под-вариант "PMTA"), `is_teen_dependent`, и наличия push-имени у dependent — строки `str49cb`…`str49d3`, например *"Your account will no longer be managed by %1$s"* / *"...by your parent"*. `ManagedAccountRevokeLinkingMutation` (раздел 3.1) — это проводная (wire) операция, которая, предположительно (inferred), стоит за этим действием; в этом проходе не было прослежено, что сама activity вызывает её напрямую.

### 5.5 Шлюз повторной аутентификации

`ManagedAccountAuthInterstitialActivity` хостит `PmaAuthInterstitialFragment` (пакет `com.whatsapp.pma.product.dependent.fragments`, found) и запускается со строкой `extra_auth_entry_point` — шаг повторной аутентификации, закрывающий доступ к экранам managed-аккаунта из заданной точки входа. Точный механизм аутентификации (PIN устройства, биометрия, пароль аккаунта) не прослежен.

### 5.6 Debug-поверхности

`ManagedAccountDebugConnectionActivity` и `ManagedAccountDebugPinAuthActivity` существуют в этой сборке (found). Этот проход не устанавливает, достижимы ли они из release UI или только из внутреннего/debug build-флага (inferred: только для debug, по соглашению об именовании и отсутствию найденного пути запуска из production-экранов).

---

## 6. Хранение

| Хранилище | Ключи / столбцы | Содержимое |
|---|---|---|
| Локальная запись отношения | `connectionLid`, `role`, `linkTs`, `connectionPnJid`, `graduationState`, `ageExperience` (раздел 2.2) | одна строка на каждую связь sponsor↔dependent |
| SharedPrefs | `paa_graduation_nux_pending`, `paa_sponsor_blocked`, `paa_nux_education_banner_dismissed`, `paa_nux_education_banner_start_timestamp`, `paa_review_privacy_settings_banner_dismissed_dependent_<lid>`, `privacy_dependent_account_messages` | состояние закрытия NUX/баннера, флаг sponsor-blocked, единственный подтверждённый гейт сообщений для dependent |

Все ключи найдены буквально в `C08530Nf`, `ManagedAccountBannerManager`, `C08520Ne`.

---

## 7. Строки UI-индикаторов

| Id строки | Текст | Где используется |
|---|---|---|
| `str2629` | "Create a parent-managed account" | точка входа онбординга |
| `str2fc9` / `str3139` | "Managed account" | badge/метка |
| `str30ae` | "Managed accounts can't see this message. Learn why" | ограниченный контент |
| `str3109` | "This is a managed account. Learn more" | уведомление в чате/профиле |
| `str3751` / `str3752` / `str3754` | сообщения о неподходящести ("isn't eligible for a parent-managed account", "Couldn't create parent-managed account") | ошибка онбординга |
| `str439d` / `str439f` | "Settings for managed accounts" / "View activity and choose settings for managed accounts" | точка входа в настройки |
| `str2fc8` | "Your account is managed by your parent or guardian..." | `DependentAccountPrivacyActivity` |
| `str49cb`-`str49d3` | варианты подтверждения отвязки | `ManagedAccountUnlinkAccountSettingsActivity` |

`ManagedAccountNotAvailableActivity` и `ManagedAccountAgeUnknownActivity` (found по имени класса) стоят за ещё двумя состояниями — функция не предлагается, и возраст аккаунта не определён — точный текст не установлен.

---

## 8. Feature flags

| ID | Где | Управляет |
|---|---|---|
| **30174** | `C08520Ne.A02`, `ManagedAccountSponsorUpsellActivity` | допустимость sponsor-upsell |
| **31562** | `ManagedAccountAlertInfoActivity` | гейт функции activity-alerts |
| **34268** | `C08520Ne.A01` | дополнительная проверка прав (роль не определена помимо самого гейта) |
| **16763** | `C08520Ne.A04` | неопределённый булев гейт |
| **33355** | `C08520Ne.A05` | неопределённый булев гейт, зависящий от dependent или второго интерфейса |

---

## 9. Бизнес-номера, делегированные провайдеру (Cloud API / BSP)

Это система, которая на самом деле соответствует понятию «бизнес-аккаунт, которым от его имени управляет провайдер». Она не делит ни один класс, proto или схему w:mex с разделами 2-8. Ни одна строка в этой сборке не говорит пользователю «BSP», «tech provider», «Business Solution Provider», «on-premises API» или «Cloud API»; сигнал — структурный.

### 9.1 Сертификат verified-name: префикс issuer и `PrivacyMode`

Клиент хранит локальную запись сертификата verified-name на каждый бизнес-JID со столбцами (found, `AbstractC218419al`): `verified_name`, `industry`, `city`, `country`, `verified_level`, `cert_blob`, `identity_unconfirmed_since`, `host_storage`, `actual_actors`, `privacy_mode_ts`. Эти последние три поля разбираются из дочернего элемента станзы `w:biz` вида `<biz host_storage="" actual_actors="" privacy_mode_ts=""/>` (found, несколько мест вызова, например `O0F.java`, `C18670m9.java`, `AbstractC24816AmW.java`) в `AnonymousClass118` («`PrivacyMode`» по собственному `toString()`), у которого два целочисленных поля:

| Поле | Значения, встреченные в коде | Значение |
|---|---|---|
| `hostStorage` | 0 (по умолчанию/не задано), 1, 2 | какая инфраструктура хранит/передаёт сообщения бизнеса; **inferred** сопоставление с публичными терминами WhatsApp Business Platform: on-premises (self-hosted) vs. Meta-hosted (Cloud API) vs. третье, двойное/переходное состояние — у клиента нет именованных констант для этих трёх значений |
| `actualActors` | 0 (по умолчанию/не задано), 1, 2 | кто фактически управляет аккаунтом в повседневности; **inferred** сопоставление с self-operated vs. operated by a provider — снова без именованных констант в этом клиенте |

Второй, независимо найденный сигнал на той же обёртке сертификата (`AnonymousClass119.A02()`/`A03()`) читает **строку issuer** сертификата (поле `A07`) и классифицирует её по префиксу (found, точный код):

```java
public boolean A01() { return this.A01 == 2; }        // hostStorage == 2
public boolean A02() { return this.A07 != null && this.A07.startsWith("ent:"); }
public boolean A03() { return this.A07 != null && this.A07.startsWith("smb:"); }
```

`"ent:"` и `"smb:"` — два префикса issuer, которые этот клиент различает (found, литеральные строки). `smb:` соответствует сертификату, выданному для обычного, self-operated приложения WhatsApp Business; `ent:` соответствует сертификату, выданному для enterprise/API-интегрированного пути — это ближайший первично-клиентский, кодовый эквивалент «self-managed business account» vs. «BSP/Cloud-API-managed business account» (сопоставление этих префиксов с двумя реальными категориями — **inferred**, выведено из самих префиксов и из того, как они потребляются в `AbstractC198638cc.A00`, а не из какой-либо строки документации внутри клиента).

`AbstractC198638cc.A00` сворачивает проверку issuer и отдельный булев флаг (`A09`, значение не определено — возможно, «сертификат отсутствует/отозван», что согласуется с пользовательским текстом «no longer an official business account» в разделе 9.2) в 4-значный код «client» (found):

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

### 9.2 Баннеры coexistence и `business_state_id`

`C198628cb` («`BusinessState`» по его `toString()`) объединяет `PrivacyMode` сертификата (9.1), 4-значный код «client» и булев `isVerified` в одно сведённое целое число, которое UI называет `business_state_id` (found, задаётся через `c198628cb.A02()` в `EncryptionChangeDialogFragment` и читается так же в `PrivacyInfoBottomSheet`/`ContactInfoActivity`). Функция сопоставления сверяет 18 явных кортежей `(client, actualActors, hostStorage, flag)` с id **0-17**; полную таблицу восстановить не удалось (JADX сообщает об ошибке region-overflow для этого конкретного метода, и несколько веток слиты декомпилятором), но следующее установлено непосредственно из кода:

- id **15** достигается всякий раз, когда код «client» равен 4 (сертификат отсутствует/отозван), независимо от других полей.
- ids **5, 6, 9, 10** — единственные id, достижимые, когда боковой метод-гейт `A05()` (несвязанная проверка block/mute-стиля на чате) истинен, а также достижимые обычным путём при `hostStorage == 2` — они стабильно управляют простыми строками *"This business uses a secure service from Meta to manage this chat/call"* (`str080d`/`str080f`/`str0c9c`/`str0f5a`, found, места вызова проверены по resource-id в `C23324A5w`/`ContactInfoActivity`).
- ids **16** и **17** — остаточные случаи (не известный кортеж и не id 15) и управляют семейством строк "multiple tools" / "no longer an official business account" (`str38ef`-`str38fb`, `str08b3`-`str08c7`): *"This business has chosen to use multiple tools to chat with its customers... Chats between only you and this business are managed by a secure service from Meta... this business is using the WhatsApp Business app"* — т.е. состояние **coexistence**, когда номер одновременно достижим и через приложение Business на устройстве, и через API-hosted путь, за флагами **12729**, **18047**, **23933**, **7131**, **29343** (found, в `PrivacyInfoBottomSheet`/`ContactInfoActivity`, каждый выбирает между старой и новой парой строк для одного и того же состояния).

Результат IQ `remove-companion-device` в несвязанном потоке multi-device может нести дочерний элемент `coex_token` (`WA_LINKED_DEVICE_PAIRING.md` §7.1) — та же концепция «coexistence», потребитель также не прослежен с этой стороны.

### 9.3 Модель устройства/сессии для номера, hosted провайдером

Бизнес-номер, полностью hosted Meta (случай Cloud API без какого-либо физического устройства), представлен внутри **существующей** системы multi-device, а не новой:

- тип аккаунта `HOSTED` (`EnumC32116E1o`, значение 1) и device id **99** зарезервированы для этого случая (`WA_LINKED_DEVICE_PAIRING.md` §5.1, §9.2).
- перечисление `companion-props.platformType`, которое primary хранит для своих linked-устройств, включает значение **23 = `CLOUD_API`** (`WA_LINKED_DEVICE_PAIRING.md` §6.2), рядом с **27 = `BUSINESS_BACK_OFFICE`** и **25/26 = `WAIL`/`WASS`** — все типы платформ бизнес-инфраструктуры сидят в том же enum, что и обычные телефоны/десктопы/web.
- потребительская (consumer) сборка в этом отчёте активно **отказывается** привязывать hosted-устройство со стороны primary (локальный код ошибки **-10**, `WA_LINKED_DEVICE_PAIRING.md` §3.2) — hosted/Cloud-API provisioning — это не то, что инициирует данный клиент; он лишь наблюдает итоговый тип аккаунта и маркеры платформы на аккаунтах, у которых это уже есть.

Ни pairing, ни ADV-подпись, ни поток companion-ключей для самого отношения BSP/Cloud-API не были найдены нигде в этом APK; механизм canonical-user/пароля из account security (`WA_ACCOUNT_SECURITY.md`) и механизм идентичности multi-device оба не связаны с тем, как BSP начинает управлять номером — этот provisioning происходит целиком на стороне сервера / на бизнес-платформе Meta и не оставляет следа в этом клиенте, кроме указанных выше маркеров.

### 9.4 Телеметрия

Событие логирования `wam_ts_navigation` (`C1EO`, found) несёт три независимых булевых поля бизнес-контекста на каждую залогированную навигацию: `is_cloudapi`, `is_onpremises`, `is_smb`, плюс `is_canonical_ent_present` и `is_meta_ai_thread`. `ChatDescription` (`com.whatsapp.gapenforcement.dto`) отдельно несёт `isEnterpriseBusiness`. Ни один из классов не раскрывает, как вычисляются эти булевы значения, помимо того, что уже описано в разделах 9.1/9.2; они только для отчётности и не управляют каким-либо видимым пользователю поведением в прочитанных файлах.

---

## 10. Ключевые различия

| A | B |
|---|---|
| «Managed account» (`ManagedAccount*`, PAA/PMA/PMTA) — **собственный аккаунт несовершеннолетнего**, под контролем родителя | бизнес-номер, **управляемый провайдером** через Cloud API — для этого случая нигде нет строки «managed account» |
| Связь sponsor/dependent: два независимых, обычно зарегистрированных аккаунта WhatsApp, без pairing устройств | hosted бизнес-номер: один аккаунт, `accountType=HOSTED`, device id 99, вообще без companion-устройства |
| Операции `w:mex` `ManagedAccount*`, схема `whatsapp-android-mex` (раздел 3.1) | поля сертификата verified-name через `w:biz` (`host_storage`, `actual_actors`) — другая станза, другая схема |
| Баннеры coexistence `business_state_id` (self-managed приложение Business **и** API-hosted одновременно) | чисто self-managed бизнес (обычное приложение WhatsApp Business на своём устройстве, префикс issuer `smb:`) |
| Флаг телеметрии `is_smb` (малый/средний бизнес, использующий приложение Business) | Флаги телеметрии `is_cloudapi` / `is_onpremises` (хостинг на стороне API) |
| `ManagedAccountRevokeLinkingMutation` (завершает родительский контроль) | `remove-companion-device` (не связано: удаляет linked-устройство; см. `WA_LINKED_DEVICE_PAIRING.md` §7) |

---

## 11. Полные потоки

### 11.1 Родительский контроль: привязка dependent

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

### 11.2 Бизнес-номер, делегированный провайдеру: что видит клиент собеседника

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

## 12. Неизвестное

| Тема | Причина |
|---|---|
| Полная таблица tuple→`business_state_id` (все 18 значений) | region-overflow декомпилятора на `C198628cb.A02()`; несколько веток слиты |
| Точное числовое значение `hostStorage`/`actualActors` помимо суррогата через префикс issuer `smb:`/`ent:` | в этом клиенте нет именованных констант; сопоставление с терминами on-premises/Cloud-API/BSP — inferred из публичной терминологии Business Platform, не прочитано из кода |
| Переменные/поля ответа `ManagedAccountValidateLinkingQuery`, `AcceptLinkingMutation`, `CompleteLinkingMutation`, `RevokeLinkingMutation`, `SyncActivities`, `UpdatePinMutation`, `GetSponsorAgeVerificationInfoQuery` | doc_id подтверждены в assets; в этой сборке не найдено место вызова с именами переменных |
| Значение булевого `A09`, питающего код «client» 4 | потребляется только как гейт; без имени или комментария |
| Дополнительные права `SPONSOR_ADMIN` по сравнению с `SPONSOR` | роль существует; дифференцированное поведение не прослежено |
| Расшифровка кодовых названий PAA / PMA / PMTA | никогда не раскрывается в строках или комментариях; только контекст использования |
| Достижимость `ManagedAccountDebugConnectionActivity`/`DebugPinAuthActivity` из release-сборок | по именованию похоже на debug-only; путь запуска не найден ни в одну, ни в другую сторону |
| Серверный provisioning номера, hosted через Cloud-API (раздел 9.3) | целиком на стороне сервера; этот клиент никогда не инициирует это и только наблюдает итоговые маркеры |
| Может ли какой-либо код клиента отличить «управляется Meta напрямую» от «управляется сторонним BSP через Cloud API Meta» | оба случая, похоже, сводятся к одним и тем же сигналам `hostStorage`/`actualActors`/platform-type; отдельное поле-идентификатор BSP не найдено |
| Реальный трафик | только статический анализ |
