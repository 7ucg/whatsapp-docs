<!-- src-sha1: 42c77add3dafd5b90522b32d91692dff968b2f54 -->
# WhatsApp Каналы и Newsletter — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-11-01
**Область:** домен JID `@newsletter` и внутреннее название "newsletter", подписка/отписка, создание канала, роли администраторов и передача прав, шесть proto-полей `newsletterAdmin*`/`newsletterFollower*`/`newsletterScheduledMessage`, метаданные канала (имя, описание, фото, верификация, состояние), реакции на посты, счётчики просмотров/подписчиков, поток приглашения/отзыва/принятия администратора, операции GraphQL/MEX newsletter (doc_id), локальное хранилище, feature-флаги, случаи ошибок

---

## 1. Что это (технически)

"Канал" — это потребительское название того, что клиент внутренне называет **newsletter**: JID типа "один-ко-многим" для вещания с хранением на стороне сервера (не E2E), небольшим набором ролей (владелец/администратор/подписчик/гость), и большинство операций control-plane передаются через GraphQL `w:mex`, а не через классические XMPP IQ. Доставка контента (получение постов, получение статусов, запланированные сообщения, подписка на живые обновления) всё ещё использует выделенное пространство имён XMPP IQ, `xmlns="newsletter"`. Все утверждения — это статический анализ декомпилированного APK; на канале связи ничего не перехватывалось. Уровни достоверности: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не выяснено. В отличие от большинства обфусцированных отчётов этого репозитория, клиентский пакет newsletter (`com.whatsapp.newsletter.*`, 122 файла) поставляется с **читаемыми именами классов и методов** в 2.26.41.6; обфусцирована только общая инфраструктура (JID, message proto, построители IQ), и она здесь заново выяснена по стабильным строкам.

Вне области: классические broadcast-листы и `status@broadcast` — см. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md). Механика поиска контактов/устройств, повторно используемая каналами (не специфична для newsletter) — см. [WA_USYNC.md](WA_USYNC.md).

| Сущность | Значение | Уровень |
|--------|-------|------|
| JID-сервер | `newsletter` (например, `120363000000000000@newsletter`) | found |
| `Jid.getType()` | **21** | found |
| Шифрование | `EnumC14260eC.NON_E2EE` — контент канала **не** сквозно зашифрован | found |
| Класс локальной модели | `C2130898y` ("NewsletterInfo"), наследует от общей строки чата `C14220e7` | found |
| Класс JID | `C1Y7` (`NewsletterJid`) | found |
| Ссылка-приглашение | `https://whatsapp.com/channel/<invite_code>` | found |
| Локальная таблица БД | `newsletter` (столбцы включают `membership`, `invite_code`, индексированы) | found |

| Компонент | Имя в 2.26.41.6 | Роль |
|-----------|----------------|------|
| Парсер JID | `C0DL.A03` (switch по строке сервера), `C1Y7` (JID), `C1Y8` (компаньон/кэш JID) | валидирует числовой id, без ведущего нуля, строит/кэширует `C1Y7` |
| Предикаты JID | `C0DZ.A0a(jid)` = `getType()==21`; `C0DZ.A0M` включает тип 21 в набор, который также содержит группы (18), broadcast list (3), status (5) и т.д. | isNewsletter / набор "многополучательных" |
| Локальная модель | `C2130898y` | роль, верификация, mute, настройка реакций, состояние, счётчики |
| Роли | `C9U5` (локальный enum), `C9U4` (wire string enum) | раздел 4 |
| Задача метаданных | `BaseMetadataNewsletterGraphqlJob`, `GetNewsletterAdminMetadataJob` | `NewsletterMetadata` / `NewsletterAdminMetadataQuery` |
| Задача обновления | `UpdateNewsletterGraphqlJob` | `NewsletterMetadataUpdate` |
| Задача создания/удаления | в `com.whatsapp.newsletter.editcreate`, `com.whatsapp.newsletter.delete` | `NewsletterCreate(Verified)` / `NewsletterDelete` |
| Получение сообщений | `GetNewsletterMessagesJob`, `GetNewsletterMessagesUpdatesJob`, `GetNewsletterMyAddOnMessagesJob`, `SendNewsletterMessageJob`, `SendViewReceiptJob` | `com.whatsapp.newsletter.messages.job` |
| Получение статусов (обновлений канала) | `GetNewsletterStatusesJob`, `GetNewsletterStatusUpdatesJob`, `GetStatusMyAddOnsJob` | `com.whatsapp.newsletter.status.job` |
| Построитель IQ | `C9EN` (конструкторы `xmlns="newsletter"`), `C9E2` (наборы значений view-role / дочерних узлов) | раздел 6 |
| Отправка приглашения администратора | `C9m6` (`UserActionsNewsletterMessaging`), `C213489Am` | раздел 5.4 |
| Хранилище реакций | `C12H`, `C23768ANd` → таблица `newsletter_message_reaction` | раздел 7 |

---

## 2. JID и домен

### 2.1 Парсинг (found, `C0DL.A03`)

```java
// X.0DL (C0DL)
public C1Y7 A03(String str, String str2) throws C09B {
    String strTrim = str.trim();
    if (strTrim.isEmpty() || "0".equals(strTrim) || strTrim.indexOf("0") == 0)
        throw new C09B("Identifier must be a valid number starting with non-zero");
    if (!"newsletter".equals(str2)) throw new C09B(...);
    // cache lookup/insert, returns C1Y7(str)
}
```

`C1Y7.getServer()` возвращает буквальную строку `"newsletter"`; `getType()` возвращает `21`. Такое же правило числового id без ведущего нуля, как у других многопользовательских типов JID (группы, broadcast list — см. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §2.1). Общий маршрутизатор JID `C0DZ.A01` в качестве варианта по умолчанию переходит к `C1Y7.A03.A02(str)`, когда строка не является ни известным синглтоном, ни `UserJid`, ни `GroupJid` — то есть `@newsletter` является резервным доменом в этом парсере (found).

### 2.2 Принадлежность к набору типов (found, `C0DZ.java`)

```java
public static boolean A0a(Jid jid) { return jid != null && jid.getType() == 21; }   // isNewsletter
public static boolean A0M(Jid jid) {
    int type = jid.getType();
    return type==0||type==1||type==18||type==22||type==3||type==7||type==21||type==26||type==28;
}
```
`A0a` — выделенный предикат newsletter. `A0M` группирует тип 21 вместе с группами (18/22), broadcast list (3), community (7) и другими в более широкий набор "способных на несколько участников" (точное назначение этой группировки не прослежено до конца; предполагается, что он управляет общей инфраструктурой участников/сессий).

---

## 3. Подписка / отписка

Подписка — это **не** подписка через stanza; это мутация `w:mex`, и локальная роль (`C9U5`) переключается между `GUEST` и `SUBSCRIBED`.

| Операция | doc_id | Переменные (found) |
|-----------|--------|--------------------|
| `NewsletterJoin` | `24658527423838739` | `entry_point`, `record`, `recipient_account_id`, `sessions`, `jid`, `fetch_and_validate_vname`, `call_offer`, `request_bottom_sheet_fragment` |
| `NewsletterLeave` | `25758579043742316` | форма идентична `NewsletterJoin` |

Обе строятся одним и тем же классом, `X/RunnableC24381AnW.java` (found). Общий набор переменных (`entry_point`, `call_offer`, `request_bottom_sheet_fragment`) предполагает, что join/leave повторно используют универсальную обёртку мутации "действие в чате", также используемую для звонков и действий, инициируемых bottom-sheet, в других частях приложения (inferred).

Переходы локальной роли на объекте `C2130898y` ("NewsletterInfo"):

| Хелпер | Условие | Значение |
|--------|--------|---------|
| `A0p()` | `!muted && role==ADMIN` | является администратором |
| `A0q()` | `!muted && (role==ADMIN \|\| role==OWNER)` | является администратором или владельцем |
| `A0r()` | `role==SUBSCRIBED` | подписан |
| `A0s()` | `role==GUEST` | не подписан (используется, чтобы принудительно установить `fetch_viewer_metadata=true` при обновлении метаданных — found в `BaseMetadataNewsletterGraphqlJob`) |
| `A0u()` | `!muted && role==OWNER` | является владельцем |

Строка ошибки UI при неудачной подписке: `str1c0d` "Couldn't follow channel", `str1c0e` "Couldn't follow channel. Check your device's internet connection and try again." (found, `res/values/strings.xml`).

---

## 4. Роли

Существуют два параллельных enum-а ролей: локальный персистентный enum и wire string enum, используемый в переменных/ответах GraphQL.

### 4.1 Локальная роль (found, `C9U5`)

```java
GUEST=0 (A03), SUBSCRIBED=1 (A05), ADMIN=2 (A02), OWNER=3 (A04)
```
`C9U5.A00()` отображает ординал → приоритетный ранг: GUEST→4, SUBSCRIBED→3, ADMIN→2, OWNER→1 (меньше = более высокие права; назначение — порядок сортировки для списков администраторов — inferred).

### 4.2 Wire-роль (found, `C9U4`, `serverValue` = имя enum-а)

```
UNSET_OR_UNRECOGNIZED_ENUM_VALUE, ADMIN, GUEST, OWNER, SUBSCRIBER
```
Используется как значение атрибута `view_role` на дочернем узле `smax:any` у XMPP IQ newsletter (раздел 6) и как значение `viewer_metadata.role` в GraphQL (раздел 8).

### 4.3 Возможности и передача прав

| Действие | GraphQL-операция | doc_id |
|--------|-----------|--------|
| Пригласить пользователя как администратора | `NewsletterAdminInvite` | `26278681041745438` |
| Отозвать ожидающее приглашение администратора | `NewsletterAdminInviteRevoke` | `24369392486051948` |
| Принять приглашение администратора | `NewsletterAcceptAdminInvite` | `24934958956134858` |
| Понизить администратора | `NewsletterAdminDemote` | `25054538847517281` |
| Передать право собственности | `NewsletterChangeOwner` | `24737692515842078` |
| Пакетное получение профилей администраторов | `NewsletterAdminProfilesQuery` | `28089989690595314` |
| Обновление профиля администратора (имя/фото) | `NewsletterAdminProfileUpdate` | `25959584293627630` |
| Метаданные администратора (полные, только для администратора поля) | `NewsletterAdminMetadataQuery` | `26882701001369256` |
| Шлюз возможностей | `NewslettersAdminCapabilitiesQuery` | `27579307995002556` |

Enum действий потока приглашения администратора (found, `EnumC215899Sc`, используется `AdminInviteErrorDialog`): `NOT_SUPPORTED=0`, `INVITE=1`, `ACCEPT_INVITE=2`, `REVOKE=3`, `DISMISS=4`.

Строки ошибок UI (found): `str0095` "Couldn't accept the admin invite. Please try again.", `str106c`/`str2bed` "Couldn't transfer ownership. Please try again(.)/ later.", `str2300`/`str2abd` "Channel admin invite", `str22fb` "Invite %s as admin?", `str2bd8` "Invite as channel admin".

---

## 5. Приглашение администратора — сообщение клиент-клиент, а не только GraphQL

UX приглашения администратора имеет **два** отдельных механизма, работающих одновременно: мутация MEX (`NewsletterAdminInvite`, выдача прав на стороне сервера) и обычное сквозно зашифрованное **личное сообщение (1:1)**, несущее payload приглашения получателю, построенное независимо от MEX.

### 5.1 Proto (found, подтверждает и расширяет исходный материал `Messages/newsletterAdminInviteMessage`)

`Message.newsletterAdminInviteMessage` — поле **78** структуры `Message` (`C30628DTw`), тип `NewsletterAdminInviteMessage` (обфусцировано как `C30596DSq` в 2.26.41.6; константы JADX на самом классе, а не номер поля на `Message`, поскольку константа поля admin-invite не входила в выгруженный набор грепа; поле 78 совпадает с более ранней ссылкой на WAProto.proto и независимо подтверждается тем, что каждое другое поле ниже разрешается именно так, как документировано):

| Поле | Номер | Тип |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `inviteExpiration` | **5** | int64 |
| `contextInfo` | **6** | `ContextInfo` |

Подтверждённые константы номеров полей `CAPTION_FIELD_NUMBER=4`, `CONTEXT_INFO_FIELD_NUMBER=6`, `INVITE_EXPIRATION_FIELD_NUMBER=5`, `JPEG_THUMBNAIL_FIELD_NUMBER=3`, `NEWSLETTER_JID_FIELD_NUMBER=1`, `NEWSLETTER_NAME_FIELD_NUMBER=2` прочитаны непосредственно с `C30596DSq` (found) — точно совпадает с более ранней картой полей для этой версии.

### 5.2 Путь отправки (found, `C9m6` = `UserActionsNewsletterMessaging`)

```java
public final void A00(Context context, C1Y7 c1y7, String name, String caption, HashMap userJidToExpiration) {
    byte[] thumbnail = A01(context, c1y7);           // JPEG of the channel picture, quality 80
    for (entry in userJidToExpiration) {
        C213489Am item = new C213489Am(..., 94, ...); // message-type tag 94
        item.A01 = c1y7;          // newsletterJid
        item.A03 = name;          // newsletterName
        item.A00 = entry.value;   // inviteExpiration
        item.A02 = caption;
        item.A0O(thumbnail, false);
        // enqueued as a normal E2E message to the invitee's UserJid
    }
}
```
Строка лога: `"UserActionsNewsletterMessaging/userActionSendNewsletterAdminInviteMessages"`. Одно сообщение отправляется на каждого приглашаемого, каждое со своим временем истечения — т.е. приглашение представляет собой **сообщение E2E для каждого получателя отдельно**, в то время как операция MEX `NewsletterAdminInvite` (на стороне сервера) является авторитетной записью выдачи прав (inferred связь между двумя путями; оба присутствуют в коде, порядок/зависимость не прослежены).

### 5.3 Принятие

Клиент приглашённого вызывает `NewsletterAcceptAdminInvite` (MEX). Его запрос уже несёт полный набор переменных для получения метаданных (`fetch_followers_count`, `fetch_state`, `fetch_verification`, `fetch_viewer_metadata`, …) — принятие приглашения и повторное получение метаданных канала составляют один круговой запрос (found, переменные из `X/AbstractC23610Aaw.java`).

---

## 6. Другие сообщения newsletter: приглашение подписчика, профиль администратора, запланированные

### 6.1 `newsletterFollowerInviteMessage` / `newsletterFollowerInviteMessageV2`

Подтверждено в 2.26.41.6 точно так, как указано в исходном материале, и независимо перепроверено здесь: оба поля `Message` существуют (`NEWSLETTER_FOLLOWER_INVITE_MESSAGE_FIELD_NUMBER` = **108**, `NEWSLETTER_FOLLOWER_INVITE_MESSAGE_V2_FIELD_NUMBER` = **113**, обе найдены как именованные константы на `C30628DTw`), и **оба отображаются на идентичный тип подсообщения**, `C30585DSf`:

| Поле | Номер | Тип |
|-------|--------|------|
| `newsletterJid` | **1** | string |
| `newsletterName` | **2** | string |
| `jpegThumbnail` | **3** | bytes |
| `caption` | **4** | string |
| `contextInfo` | **5** | `ContextInfo` |

Почему существуют оба номера поля для одного типа, по-прежнему **unknown** — поведенческое различие на уровне Java не найдено и в этом проходе (согласуется с более ранней находкой).

### 6.2 `newsletterAdminProfileMessage` / `newsletterAdminProfileStatusMessage` / `newsletterScheduledMessage`

Все три подтверждены как именованные константы на `C30628DTw` (`NEWSLETTER_ADMIN_PROFILE_MESSAGE_FIELD_NUMBER` = **116**, `NEWSLETTER_ADMIN_PROFILE_STATUS_MESSAGE_FIELD_NUMBER` = **126**, `NEWSLETTER_SCHEDULED_MESSAGE_FIELD_NUMBER` = **132**), и все три отображаются на один и тот же общий однопольный тип-обёртку, `BD2` (= `FutureProofMessage`):

```java
public final class BD2 { public C30628DTw message_; }   // field "message", number 1, type Message (recursive)
```

Специального класса рендера/валидатора для какого-либо из этих трёх полей не существует (found, совпадает с более ранней заметкой для `newsletterAdminProfileMessage` и `newsletterScheduledMessage`). У `newsletterScheduledMessage` при этом есть выделенная поверхность вне proto: локальная таблица `newsletter_scheduled_message` (`chat_row_id`, `scheduled_server_id`, с уникальным индексом) и дочерний узел IQ по каналу связи `<scheduled_messages/>` (раздел 6.3) — сама *функция* планирования реальна и прослежена; только proto-поле `Message.newsletterScheduledMessage` остаётся нераскрытой обёрткой.

### 6.3 Связанные локальные таблицы

`newsletter_scheduled_message`, `newsletter_admin_profile` (`chat_row_id`, `admin_profile_id`, `timestamp`) поддерживают `NewsletterAdminProfilesQuery`/`NewsletterAdminProfileUpdate` и, соответственно, UI планирования (found, `C0SG.java`, `C0S3.java`).

---

## 7. Посты канала: получение, отправка, реакции, счётчики просмотров

### 7.1 Пространство имён XMPP IQ `newsletter` (found, `C9EN`)

Получение контента и несколько действий записи используют выделенное пространство имён IQ, отдельное от MEX:

```xml
<iq xmlns="newsletter" type="get" to="<jid>@newsletter" id="…">
  <messages count="N">
    <smax:any type="jid" jid="<jid>@newsletter" view_role="admin|guest|owner|subscriber"/>
    <before count="N"/> <!-- or <after count="N"/> -->
  </messages>
</iq>
```

| Дочерний элемент | Конструктор | Назначение |
|---------------|-------------|---------|
| `<messages count/>` + `<before>`/`<after>` | `C9EN(C9EB, C9E2, id, count)` | пагинация постов канала |
| `<message_updates count since/>` | `C9EN(C1Y7, C9E8, Long, id, count)` | дельта-синхронизация изменённых/удалённых постов |
| `<statuses count/>` | `C9EN(C9E9, C9E2, id, count)` | получение статусов/обновлений канала |
| `<status_updates count since/>` | `C9EN(C1Y7, C9EA, Long, id, count)` | дельта-синхронизация постов-статусов |
| `<scheduled_messages count/>` | `C9EN(C1Y7, C31085Dfd, id, count)` | ожидающие запланированные посты |
| `<question_responses server_id count/>` (обычный и `type="status"`) | `C9EN(...)` | ответы на опрос/вопрос в посте |
| `<my_question_responses server_id/>` | `C9EN(C1Y7, String, long)` | собственные ответы вызывающего |
| `<my_addons type="status" limit jid/>` | `C9EN(C1Y7, String, int, long)` | собственные реакции/аддоны вызывающего |
| `<live_updates/>` (`type="set"`) | `C9EN(C1Y7, String)` | подписка на push в реальном времени для канала |

Атрибут `view_role` на `smax:any` несёт собственную строку роли `C9U4` вызывающего (admin/guest/owner/subscriber) с каждым IQ получения контента — похоже, что сервер ограничивает содержимое ответа (например, поля, доступные только администратору) для каждого запроса отдельно, а не исключительно по состоянию сессии (inferred).

### 7.2 Отправка (found, `SendNewsletterMessageJob`) и квитанции о просмотре

Публикация в канал повторно использует стандартный конвейер отправки (здесь не детализируется подробнее; задача оборачивает обычную машинерию stanza `<message>`). Просмотр поста явный и отделён от квитанций доставки/прочтения:

```java
// com.whatsapp.newsletter.messages.job.SendViewReceiptJob
<receipt to="<jid>@newsletter" id="…" type="view">
  <list><item server_id="…"/> …</list>
</receipt>
```
Одна квитанция `view` объединяет несколько id сообщений сервера. Это механизм, который питает **счётчик просмотров** на пост, показываемый в UI канала (found; сам счётчик агрегируется на сервере — клиент только сообщает, но никогда не считывает значение обратно через этот IQ).

### 7.3 Реакции (found)

Реакции на посты канала в локальном хранилище **агрегированы, а не привязаны к пользователю**:

```sql
CREATE UNIQUE INDEX newsletter_message_reaction_index
  ON newsletter_message_reaction (message_row_id, reaction);
-- columns include: reaction, reaction_count
```
т.е. одна строка на пару `(сообщение, эмодзи)` с текущим счётчиком, а не одна строка на реагирующего пользователя — что соответствует UI канала, показывающему агрегированный счётчик на эмодзи, а не список реагирующих, как у обычных пользователей. `newsletter_my_reaction_orphan_message` (`chat_row_id`, `server_message_id`, с уникальным индексом) хранит **собственную** реакцию вызывающего, если она приходит раньше поста, на который направлена, для согласования, когда пост доходит.

Кто реагировал видно только администраторам, через выделенный MEX-запрос:

| Операция | doc_id | Переменные |
|-----------|--------|-----------|
| `NewsletterReactionSendersList` | `25219734117717032` | `server_id` |

Политика реакций настраивается для каждого канала (раздел 8.2, `reaction_codes`): `ALL`, `BASIC`, `BLOCKLIST`, `NONE` (wire-строки, см. `C9U3`/`C9TA` ниже).

### 7.4 Счётчики подписчиков / просмотров в метаданных

`thread_metadata.followers_count` возвращается как часть `NewsletterMetadata` (раздел 8.1). Также существует выделенная операция с пагинацией:

| Операция | doc_id | Переменные |
|-----------|--------|-----------|
| `NewsletterFollowers` | `25646542368289354` | `newsletter_id`, `count` |

Счётчики просмотров на пост не возвращаются документированной отдельной операцией в этом проходе; предполагается, что они находятся внутри метаданных отдельного сообщения, возвращаемых IQ `messages`/`message_updates` (раздел 7.1), что не было раскрыто далее здесь (точное имя поля unknown).

---

## 8. Метаданные канала (форма ответа GraphQL)

### 8.1 Ответ `NewsletterMetadata` (found, цепочка `C208048tR → C208038tQ → C208028tP`, узел GraphQL `xwa2_newsletter`)

```
xwa2_newsletter {
  id
  refresh_after_interval_sec
  state { type }                                    // C9UA
  status_metadata { last_status_sent_time, last_status_server_id }
  thread_metadata {
    creation_time
    description { text, id }
    followers_count
    handle
    invite                                           // invite code / link token
    name { text, id }
    picture { direct_path, type, url, id }
    pinned_messages[]
    preview
    settings { reaction_codes { value } }            // C9U3
    verification                                     // EnumC216369Tx
    verification_source                              // EnumC216219Ti
    wamo_sub { plan_id }
  }
  viewer_metadata {
    role                                             // C9U4
    settings[]                                       // { type, value } = EnumC216349Tv / EnumC216359Tw
    wamo_sub_status                                  // EnumC216229Tj
  }
}
```

### 8.2 Enum-ы (found)

| Enum | Значения (wire-строки, где применимо) |
|------|---|
| `state.type` (`C9UA`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `DELETED`, `GEOSUSPENDED`, `NON_EXISTING`, `SUSPENDED` |
| `verification` (`EnumC216369Tx`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `UNVERIFIED`, `VERIFIED` |
| `verification_source` (`EnumC216219Ti`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `LEGACY_MANUAL_REVIEW`, `META_VERIFIED_SUBSCRIPTION` |
| `viewer_metadata.role` (`C9U4`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ADMIN`, `GUEST`, `OWNER`, `SUBSCRIBER` |
| `wamo_sub_status` (`EnumC216229Tj`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `INACTIVE` |
| `settings[].type` (`EnumC216349Tv`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `MUTE_ADMIN_ACTIVITY`, `MUTE_FOLLOWER_ACTIVITY` |
| `settings[].value` (`EnumC216359Tw`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `OFF`, `ON` |
| `reaction_codes.value` (`C9U3`) | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `BASIC`, `BLOCKLIST`, `NONE` |

Локальные отражения на `C2130898y` ("NewsletterInfo"): состояние верификации `EnumC216079Su` (`NOT_VERIFIED=0`, `VERIFIED=1`), источник верификации `C9T1` (`UNKNOWN_VERIFICATION_SOURCE=0`, `META_VERIFIED_SUBSCRIPTION=1`, `LEGACY_MANUAL_REVIEW=2`), состояние применения санкций `C9T2` (`NOT_ENFORCED`, `SUSPENDED`, `GEOSUSPENDED` — чтение закрыто флагом **3877** в `A0w`/`A0x`), локальное состояние "активен" `C9T3` (`NOT_SET`, `INACTIVE`, `ACTIVE`), прогресс миграции/создания `C9T9` (`NOT_STARTED`, `IN_PROGRESS`, `FAILED`, `COMPLETED`), видимость в каталоге `EnumC216039Sq` (`PUBLIC`, `PRIVATE`) и локальная настройка реакций `C9TA` (`DEFAULT=0`→wire `"BASIC"`, `ALL=1`→`"ALL"`, `NONE=2`→`"NONE"`, `BLOCKLIST=3`→`"BLOCKLIST"` — отображение прочитано из `UpdateNewsletterGraphqlJob.A0M`).

### 8.3 Обновление (found, `UpdateNewsletterGraphqlJob` → `NewsletterMetadataUpdate`)

```js
// GraphQl input built for doc_id 27150690864552229
updates: {
  description?: string,   // "" clears
  name?: string,
  picture?: base64,        // "" clears
  admin_profiles_enabled?: { settings: { admin_profiles_enabled, reaction_codes: { value: "ALL"|"BASIC"|"NONE"|"BLOCKLIST" } } }
}
newsletter_id: <jid>
fetch_image: true, fetch_preview: true, fetch_name: true,
fetch_viewer_metadata / fetch_state / fetch_verification / fetch_followers_count: <bool, usually mirrors viewer role>
```

### 8.4 Строки UI верификации (found)

`str136f` "New verified channel", `str2be2`/`str2be3` "Create verified channel"/иконка, `str2c51` "Verified channels", `str2c78` "Your verified badge will be removed from this channel. Your Meta Verified subscription will remain active.", `str2ca9` "Sorry, you cannot change the name of a verified channel from the app. Please contact customer support for assistance." — т.е. у верифицированных каналов имя неизменяемо с принуждением на стороне сервера (UX только на стороне клиента; применение на другой стороне unknown).

---

## 9. Операции GraphQL / MEX newsletter (doc_id)

Все doc_id ниже были независимо перепроверены для этой сборки по `assets/whatsapp-android-mex_client_persist_ids.json` внутри `WhatsApp_2.26.41.6.apk` (found — doc_id являются статичными записями ассета, не обфусцированы, и стабильны при сравнении версий, предпринятом здесь). В этом ассете всего существует 46 операций `Newsletter*`; те, что не детализированы в других разделах этого отчёта:

| Операция | doc_id | Назначение (inferred по имени/переменным) |
|-----------|--------|------------------------------------------|
| `NewsletterCreate` | `27009199332109318` | создать канал |
| `NewsletterCreateVerified` | `27777918425146464` | создать предварительно верифицированный канал (привилегированные аккаунты) |
| `NewsletterDelete` | `31838460859131915` | удалить канал |
| `NewsletterUpdateVerification` | `27133493439664458` | запрос/обновление состояния верификации |
| `NewsletterHide` / `NewsletterUnhide` | `25033614912931367` / `24551592861177484` | переключатель видимости в каталоге (локальный `EnumC216039Sq`) |
| `NewsletterFollowing` | `26856957210673444` | список каналов, на которые подписан аккаунт |
| `NewsletterDirectoryList` / `Search` / `CategoryPreview` | `27480627564903390` / `27887355094203575` / `27432651036395658` | просмотр публичного каталога |
| `NewsletterSimilar` / `NewsletterRecommended` | `36410329795280256` / `26638880912457992` | обнаружение |
| `NewsletterInsights` | `24672564052397921` | аналитика владельца/администратора |
| `NewsletterPinMessages` / `NewsletterUnpinMessages` | `28521965914059511` / `37386851567568720` | управление закреплёнными постами (`message_ids`) |
| `NewsletterBlockUser` | `25106066249006236` | заблокировать подписчика |
| `NewsletterLogExposures` | `24606408825709914` | телеметрия показов в каталоге |
| `NewsletterLinkPreviewCheck` | `24188786150796507` | проверка доменов превью ссылок в постах |
| `NewsletterPollVoterList` | `24803802869271956` | голосовавшие в опросе на посте (`jid`, `vote_hash`) |
| `NewsletterQuestionResponseStateUpdate` | `24896618076668076` | состояние модерации Q&A |
| `NewsletterLabelAiContent` / `NewsletterLabelPaidPartnership` | `27470054215955630` / `26221505494211174` | метка AI-контента / платного партнёрства для поста |
| `NewsletterChangeWamoSub` / `Enable`/`DisableWamoSub` | `25201342542835866` / `25122474967344830` / `31916794074578680` | состояние подписки монетизации WhatsApp |
| `NewsletterUserReports` / `NewsletterCreateReportAppeal` | `27149305681394065` / `27792557363683798` | жалоба на нарушение / апелляция |
| `NewsletterEnforcements` / `NewsletterEnforcementAlertStates` | `27089116857425014` / `27640745535604048` | состояние санкций/приостановки (собственный пакет `com.whatsapp.newsletterenforcements`) |
| `NewsletterUpdateUserSetting` | `24935528202764688` | пользовательская настройка UI (например, счётчик подсказки в выборе контакта) |
| `FetchNewsletterRankingFeatures` | `24742757908756088` | получение сигналов ранжирования (каталог/рекомендации) |

Все — это IQ `w:mex` (`type="get"`), схема `whatsapp_mex`, транспорт подтверждён общим паттерном вызова `C16880is`/`TreeWithGraphQL`, наблюдаемым в §5–8 (found). Формы ответа, кроме `NewsletterMetadata` из §8, в этом проходе не раскрывались (unknown).

---

## 10. Хранилище

| Таблица | Ключевые столбцы (found) |
|-------|----------------------|
| `newsletter` | `membership` (индексирован), `invite_code` (индексирован) |
| `newsletter_message` | уникальный индекс по `(chat_row_id, server_message_id)`; `is_autodelete_eligible` (индексирован) |
| `newsletter_message_reaction` | уникальный индекс по `(message_row_id, reaction)`; `reaction`, `reaction_count` |
| `newsletter_my_reaction_orphan_message` | уникальный индекс по `(chat_row_id, server_message_id)` — собственная реакция вызывающего, приходящая раньше её поста |
| `newsletter_admin_profile` | уникальный индекс по `(chat_row_id, admin_profile_id)`; `timestamp` (индексирован) |
| `newsletter_subscribers` | индексирован по `(chat_row_id, type_of_fetch)` |
| `newsletter_scheduled_message` | уникальный индекс по `(chat_row_id, scheduled_server_id)` |
| `newsletter_interaction` | индексирован по `timestamp_ms` и `(newsletter_jid_row_id, timestamp_ms)` |
| `newsletter_linked_account` | индексирован по `chat_row_id` |
| `newsletter_pinned_message` | индексирован по `(chat_row_id, pin_timestamp_ms)` |
| `newsletter_media_clear` | уникальный индекс по `(chat_row_id, media_type)` |

Общая инфраструктура чата (`chat`/`chat_view`, базовые столбцы `message`) повторно используется, как для любого чата с типом `Jid`, так же как для групп/broadcast-листов (см. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) §3.5) — здесь повторно не детализируется.

---

## 11. Feature-флаги

ID, как прочитаны в точках вызова в `com.whatsapp.newsletter.*`; значения по умолчанию не все выяснены в этом проходе (отмечено там, где известны).

| ID | Управляет |
|----|----------|
| **3877** | закрывает чтение локальных хелперов состояния санкций `A0w`/`A0x` (проверки `SUSPENDED`/`GEOSUSPENDED`) на `C2130898y` |
| **1777** | выбор страны в фильтрах каталога |
| **5276** | представление идентичности канала во время UI миграции newsletter→что-то |
| **6445** | `ShareNewsletterInviteLinkActivity` |
| **6618** | `ViewNewsletterProfilePhoto` |
| **7237** | `NewsletterStatusView` |
| **9096** | `SendNewsletterMessageJob` |
| **12989** | `NewsletterDirectoryCategoriesActivity` |
| **15754** | маркер perf-tracker "messages_fetch_end" в `GetNewsletterMessagesJob` |
| **17985** | `ForwardCounterAcsRepository` (счётчик пересланных постов) |
| **19889** | `ForwardCounterApi` |
| **23797** | `NewsletterDescriptionView` |

Точные значения по умолчанию и полный охват управляемого поведения не прослежены дальше, чем "класс достижим только когда флаг включён" (inferred по форме точки вызова); считайте эту таблицу картой того, куда смотреть, а не подтверждёнными значениями по умолчанию (unknown для большинства строк).

---

## 12. Случаи ошибок

| Симптом | Причина | Исправление / ожидаемое поведение |
|---------|-------|--------------------------|
| "Couldn't follow channel" (`str1c0d`/`str1c0e`) | `NewsletterJoin` завершился неудачей или нет соединения | повторить попытку; проверить соединение |
| "Couldn't accept the admin invite. Please try again." (`str0095`) | `NewsletterAcceptAdminInvite` завершился неудачей | повторить попытку |
| "Couldn't transfer ownership…" (`str106c`/`str2bed`) | `NewsletterChangeOwner` завершился неудачей | повторить попытку позже |
| "Sorry, you cannot change the name of a verified channel from the app." (`str2ca9`) | канал `VERIFIED`; имя неизменяемо на стороне клиента | обратиться в поддержку (на стороне сервера; точное применение unknown) |
| Собственная реакция не имеет соответствующего поста | stanza/событие реакции обогнало доставку самого поста | хранится в `newsletter_my_reaction_orphan_message` до тех пор, пока пост не доходит, затем согласуется |
| `state.type` = `SUSPENDED`/`GEOSUSPENDED` | действие санкций против канала | получение контента всё ещё возвращает `state`; публикация/действия администратора предположительно блокируются на стороне сервера (точный шлюз unknown) |
| `state.type` = `DELETED`/`NON_EXISTING` | канал удалён или никогда не существовал | клиент должен удалить локальную строку `newsletter` (путь применения не прослежен) |
| Действие приглашения администратора = `NOT_SUPPORTED` (`EnumC215899Sc`) | попытка приглашения/принятия/отзыва в неподдерживаемом контексте (например, роль, сборка) | общий диалог ошибки, без кнопки повтора (`str5735`) |

---

## 13. Ключевые различия

| Не путать | Отличие |
|----------------|------------|
| Newsletter (`@newsletter`, тип 21) vs broadcast list (`@broadcast`, тип 3) | newsletter: хранится на сервере, не E2E, публичная модель подписки, роли; broadcast list: E2E-рассылка sender-key только сохранённым контактам — см. [WA_BROADCAST_LISTS.md](WA_BROADCAST_LISTS.md) |
| IQ `xmlns="newsletter"` vs операции GraphQL `w:mex` `Newsletter*` | IQ = получение/пагинация/подписка на контент (сообщения, статусы, запланированные, live-updates); MEX = метаданные, роли, каталог, модерация, монетизация |
| `newsletterAdminInviteMessage` (E2E личное сообщение, поле 78) vs `NewsletterAdminInvite` (мутация MEX) | сообщение — это уведомление для каждого получателя со своим временем истечения; операция MEX — выдача прав на стороне сервера — оба существуют, связь inferred |
| `newsletterFollowerInviteMessage` (поле 108) vs `newsletterFollowerInviteMessageV2` (поле 113) | идентичный тип payload (`C30585DSf`); причина дублирования unknown |
| Локальная роль `C9U5` (GUEST/SUBSCRIBED/ADMIN/OWNER) vs wire-роль `C9U4` (…GUEST/ADMIN/OWNER/SUBSCRIBER) | одни и те же четыре роли, разный порядок ординалов и разный регистр/порядок строк — не предполагать совместимость ординалов |
| wire-значение `reaction_codes` (`ALL`/`BASIC`/`BLOCKLIST`/`NONE`, из `C9U3`) vs локальная карта ординал-строка `C9TA` | локальный ординал 0 (`DEFAULT`) сериализуется в wire-строку `"BASIC"`, а не `"DEFAULT"` |
| Хранение реакций на пост (`newsletter_message_reaction`, агрегированный счётчик) vs обычные реакции на сообщения | каналы хранят одну строку на пару `(сообщение, эмодзи)` со счётчиком, а не одну строку на реагирующего пользователя |

---

## 14. Полный поток

```
[Admin]  create channel
    │   NewsletterCreate / NewsletterCreateVerified (MEX) ──► [WA Server] allocates <id>@newsletter
    ▼
[Admin]  set name/description/picture, reaction policy
    │   UpdateNewsletterGraphqlJob ──► NewsletterMetadataUpdate (MEX)
    ▼
[Admin]  invite co-admin
    │   C9m6: per-recipient E2E message (newsletterAdminInviteMessage, field 78, own expiration)
    │   + NewsletterAdminInvite (MEX, server-side grant)
    ▼
[Invitee]  NewsletterAcceptAdminInvite (MEX) ──► role GUEST/SUBSCRIBED → ADMIN (C9U5)

[User]  discover channel (directory / shared link https://whatsapp.com/channel/<code>)
    ▼
[Client]  NewsletterJoin (MEX) ──► role → SUBSCRIBED
    ▼
[Client]  <iq xmlns="newsletter" type="get"><messages count view_role=subscriber/></iq>
    │◄── posts, paginated by before/after server_id
    ▼
[User]  views post ──► <receipt type="view"><list><item server_id/></list></receipt> (view count)
[User]  reacts ──► newsletter_message_reaction (aggregate count, own reaction may be orphaned until post lands)

[Admin]  moderates: NewsletterReactionSendersList (who reacted), NewsletterBlockUser,
         NewsletterPinMessages/Unpin, NewsletterUpdateVerification, NewsletterChangeOwner
    ▼
[Owner]  delete channel ──► NewsletterDelete (MEX)
```

---

## 15. Неизвестное

| Пункт | Причина |
|------|--------|
| Точная связь/порядок между E2E-сообщением приглашения администратора и выдачей прав MEX `NewsletterAdminInvite` | оба существуют в коде; что является авторитетным, или запускает ли одно другое — не прослежено |
| Почему `newsletterFollowerInviteMessage` (108) и `…V2` (113) используют один proto-тип | поведенческое различие на уровне Java не найдено |
| Имя/расположение поля счётчика просмотров на пост в ответе получения сообщений | предполагается, что существует внутри payload IQ `messages`/`message_updates`; не раскрыто |
| Применение неизменяемости имени для верифицированных каналов на стороне сервера | клиент только показывает статичную строку ошибки |
| Полная форма ответа большинства операций MEX, кроме `NewsletterMetadata` | не прочитана в этом проходе |
| Значения по умолчанию для большинства feature-флагов в §11 | только достижимость класса, состояние по умолчанию не подтверждено |
| Трафик / поведение живого сервера | ничего не перехвачено; только статический анализ |

---

## 16. Baileys

Не охвачено: у `baron-baileys-v2` (форк Baileys, используемый как базовая линия сравнения в других отчётах этого репозитория) на момент написания нет подтверждённой, проверенной против этого APK реализации newsletter/канала для сравнения. Код Baileys для этого отчёта не инспектировался. Добавление раздела Baileys без проверенных фактов нарушило бы правила доказательности этого репозитория. Если/когда `baron-baileys-v2` добавит поддержку newsletter, этот раздел следует заполнить относительно JID (тип 21, сервер `newsletter`), IQ `xmlns="newsletter"` из §7.1 и doc_id MEX из §9.
