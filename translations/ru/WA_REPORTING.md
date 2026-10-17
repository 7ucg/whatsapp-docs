<!-- src-sha1: 27b3b625c1ca67d873007881de02f13ba8cbf277 -->
# WhatsApp Reporting — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-17
**Область:** жалобы на пользователей/контакты, группы, каналы, статусы, звонки и сообщения — stanza SMAX `spam`, `spam_list`, типы жалоб, точки входа `spam_flow`, reporting-токены, загрузка содержимого, UI жалобы/блокировки, report-to-admin, stanza блокировки и списки причин, ошибки сервера, клиентские сигналы злоупотреблений, Baileys

---

## 1. Что такое жалоба (технически)

Жалоба — это один IQ `set` на `s.whatsapp.net` в пространстве имён `spam`. Он несёт узел `spam_list` (объект жалобы, сообщения, на которые жалуются, точка входа, контекст business-discovery). Клиент заново сериализует сообщения, на которые поступила жалоба, в plaintext protobuf и загружает их вместе с reporting-токеном и ключом, который его проверяет. Блокировка — отдельная stanza (`blocklist`). Report-to-admin — третья, не связанная с ними stanza (`w:g2`).

Все утверждения основаны на статическом анализе декомпилированного APK. Уровень: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не выяснено. Ничего из этого не было перехвачено в сети.

| Сущность | Имя в 2.26.41.6 | Роль |
|----------|-----------------|------|
| Построитель IQ (многоцелевой, `$t` выбирает форму) | `C9EN` | строит каждый IQ жалобы (типы 0, 18-23) и много несвязанных IQ |
| Узел причины/точки входа | `C9E2` | `spam_list` с `spam_flow`, `wi_trace_id`, `is_known_chat`, ... (`xmlns="spam"`) |
| Дочерний элемент настройки группы | `C9E1` | `allow_admin_reports` / `not_allow_admin_reports` |
| Обёртка содержимого | `C31080DfY` | `raw`, `content_validation`, `reporting_token`, `reporting_token_key` |
| Прочие узлы | `C31084Dfc`, `C31085Dfd` | флаги (`multicast`, `url_text`, ...), `biz_opt_out`, `reporting` |
| Сериализатор ("ReportRpcUtils") | `C33446EhE` | `getMessageMixin` / `getMessageRaw`, сборка токена |
| Менеджер SMAX | `SpamRPCManager` | `A01`-`A06`, по одному на каждый вид жалобы (имя пакета не обфусцировано) |
| Репозиторий | `SpamReportRepo` | маршрутизирует по классу JID, локальные побочные эффекты |
| Обёртки RPC | `IndividualSpamReportRpc`, `GroupSpamReportRpc`, `NewsletterSpamReportRpc`, `StatusSpamReportRpc`, `ChannelStatusSpamReportRpc`, `EventSpamReportRpc` | пакет `com.whatsapp.reportinfra.rpc` |
| Белый список origin | `C9ZJ` | проверяет точку входа (78 значений) |
| UI | `ReportSpamDialogFragment` (+ `reportAsSpam$1`, `triggerExtraAction$2`, `ReportSpamDialogViewModel`) | диалог жалобы, опциональная блокировка/выход |
| Исполнитель блокировки | `C227489sZ` → `C34631Yx` | IQ `blocklist` |
| Report-to-admin | `RtaXmppClient` | очередь отчётов `w:g2` |
| Хранилище токенов | `C23070uA` | таблицы `reporting_info`, `reporting_info_content` |

Имена различаются между сборками; каждое обфусцированное имя выше было определено в 2.26.41.6 по стабильным строкам (`spam_list`, `spam_flow`, `reporting_token_key`, `GET_REPORTING_INFO_LIST`, `blocklist`).

---

## 2. Типы жалоб

### 2.1 Маршрутизация (found)

`SpamReportRepo.A02(contact, status, entryPoint, wiTraceId, messages, includeCallLogs)` ветвится по классу JID:

| JID, на который жалоба | Класс RPC | `SpamRPCManager` | Builder `$t` | Класс ответа | Метка лога |
|------------------------|-----------|------------------|--------------|--------------|------------|
| выбранный объект статуса (`AbstractC31014DeU` не null) на JID newsletter | `ChannelStatusSpamReportRpc` | `A02` | 23 | `C43535Iyq` | StatusReportV2 |
| пользователь (PN, LID, interop) | `IndividualSpamReportRpc` | `A01` | 20 | `C43534Iyp` | IndividualReport |
| группа | `GroupSpamReportRpc` | `A04` | 19 | `C43538Iyt` | GroupReport |
| выбранный объект статуса на любом другом JID или JID статуса со списком сообщений | `StatusSpamReportRpc` | `A05` | 22 | `C43533Iyo` | StatusReport |
| newsletter/канал | `NewsletterSpamReportRpc` | `A03` | 21 | `C43536Iyr` | NewsletterReport |
| id события (строка) | `EventSpamReportRpc` | `A06` | 18 | `C43537Iys` | EventReport |
| всё остальное | нет | нет | нет | нет | выбрасывается `SpamReportRepo: unrecognized jid`, возвращается как сбой |
| чат с ботом | нет (см. 3.3) | нет | нет | нет | `C214999If` |

Другие формы `C9EN`, не являющиеся жалобами на спам: `$t=0` жалоба админам и `$t=1` переключатель настройки группы (раздел 9), `$t=2` предложения подгрупп, `$t=24/25/26` узлы `status`. RPC события вызывается из лямбд корутин (`AYs`, `Aaa`); исходный UI unknown (точки входа события `event_home_report` / `event_info_report` существуют, поэтому жалобы на события — inferred).

### 2.2 Жалобы на звонки — это жалобы на пользователей (found)

`SpamReportRepo.triggerReportCallNonSuspend` (origin `call_spam_dialog_report`) вызывает `IndividualSpamReportRpc.A00` без `jid` жалобы, без сообщений и с одним элементом звонка. Элемент звонка (`C31082Dfa`):

```xml
<call from="<callerJid>" id="<callId>" to="<ownJid>">
  <call_info duration="<s>" terminator="<jid>" start_time="<ts>" adder="<jid>" creator="<jid>"
             terminate_reason="<enum>" reason="<enum>" mediatype="audio|video"/>
</call>
```

`terminate_reason` включает `crash, detect_identity_change, ended_by_peer, ended_by_self, ended_by_user, reconnecting, timeout, unknown` и фатальные ошибки кодека. Flag **36386** выбирает форму собственного JID в `to` (`CUC()` против `Ask()`, inferred LID против PN). Жалоба пользователя из UI с `shouldIncludeCallLogsInReport` добавляет до 5 элементов журнала звонков (`C16430i1.A0B(jid, 5)`).

---

## 3. Клиентский процесс

### 3.1 Диалог

`ReportSpamDialogFragment` (нижний диалог). Аргументы фрагмента (found): `flow` (строка точки входа, становится `spam_flow`), `shouldDeleteChatOnBlock`, `notifyObservableDialogHost`, `upsellCheckboxActionDefault`, `shouldOpenHomeScreenAction`, `showLeaveCheckbox`. `ReportSpamDialogViewModel.initializeSpamDialog$1` загружает состояние диалога.

При подтверждении выполняется `reportAsSpam$1`:

1. Чат с ботом: RPC пропускается (3.3). Иначе `SpamReportRepo.A02(...)` с выбранным сообщением в списке из одного элемента (или без него).
2. Успех несёт необязательный id жалобы; ошибка показывает toast `str3bf8` (или `C227489sZ.A00`, лог `spamreportmanager/spam/report/no-network-cannot-report`). Заполняется WAM `wam_spam_report_perf` (11.3).
3. Необязательное дополнительное действие `triggerExtraAction$2` (3.2), диалог завершения из `H2U` (10.2), локальные записи (3.3).

### 3.2 Только жалоба против жалобы + дополнительное действие (found)

Флажок соответствует строке `report` (не отмечен) или `report_block` (отмечен), используется для аналитики (`asd.BaC` против `BaD`) и toast после жалобы. Дополнительное действие зависит от цели:

| Цель | Дополнительное действие при отметке |
|------|-------------------------------------|
| пользователь | блокировка через `C227489sZ.A01` → IQ `blocklist` `C34631Yx` (раздел 8), причина блокировки `null`, точка входа = `flow`, `deleteChat` = аргумент `shouldDeleteChatOnBlock` |
| группа | задача выхода из группы (`C98C` / `C9CI`, запускается с JID группы; семантика выхода inferred) |
| канал | локально скрыть канал, на который поступила жалоба (`NewsletterReportCompletionListener`, flag **25218**), затем процесс выхода/отписки от newsletter |

IQ жалобы отправляется первым; блокировка/выход выполняется после возврата RPC независимо от его результата (inferred из потока управления, проверки успеха перед `triggerExtraAction$2` нет).

### 3.3 Чаты с ботами и локальные эффекты (found)

Чаты с ботами пропускают `SpamReportRepo`: клиент вызывает `BotMessageHelper/reportUgc` (`E1J.GENERIC`, `C27847C7h`) и считает это успехом (`C214999If`); формат в сети unknown. Для остальных чатов `C24120Ab1` case 4 делает следующее:

| Шаг | Эффект |
|-----|--------|
| сообщение не выбрано | собирает последние **5** сообщений чата (`C14680f4.A01(..., 5, true)`; строки системного типа исключены, фильтра `from_me` в этом варианте нет) как содержимое жалобы |
| чат с пользователем | локальный лог `S3q.A0C(jid, localCode(flow), ...)`, `OptimisedDeliveryConversionLoggingController/handleUserReport`; flag **20085** управляет `H0J.A00(jid, ...)` (назначение unknown) |
| после RPC | `contacts.is_spam_reported = true` (`ContactManagerDatabase/updateIsReportedSpam`), `C31S.A01(...)`, проверки результата RPC в видимом потоке нет |

---

## 4. Конверт stanza и пространство имён

### 4.1 Узел причины сливается в IQ (found)

RPC не выдают два соседних `spam_list`. Основной `spam_list` (jid, сообщения) и узел причины `C9E2` (фрагмент `<iq to="s.whatsapp.net" xmlns="spam"><spam_list .../></iq>`) объединяются через `C10340Uk.A04`, который сливает атрибуты и одноимённые дочерние элементы (конфликтующие значения атрибутов или количества дочерних прерывают слияние). Результат:

```xml
<iq type="set" id="<n..>" to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<reported>" spam_flow="<entry point>" wi_trace_id="<24 chars>">
    ...children...
  </spam_list>
</iq>
```

Доказательство: конструкторы `C9EN` для 18-23 вызывают `C9E2.A00(iq, reasonNode)` = `iq.A04(node)`; `C9E2` case 5 строит `iq{to, xmlns="spam"} > spam_list{wi_trace_id, spam_flow}`; `C19380nJ.A00.getServer() = "s.whatsapp.net"`. `id` IQ берётся из `MessageClientSmaxWrapper.A01()` (`n<hex counter>`, `C10140Tq.A0H`). Таймаут отправки 32000 мс (`A0F(node, id, cont, type, 32000, ...)`); null-ответ (таймаут/сбой доставки) превращается в `C216549Uq`.

Типы 0 и 1 буквально задают `xmlns="w:g2"` и `to=<group>`; типы 18-23 строят `<iq type="set">` и полагаются на слияние для `to` и `xmlns`. Id типа, передаваемый отправителю, — **98** (группа, newsletter, событие) и **385** (report-to-admin).

### 4.2 Необязательные соседние элементы, сливаемые в `spam_list`

| Узел/атрибут | Источник | Условие | Уровень |
|--------------|----------|---------|---------|
| `spam_flow` | аргумент `flow`, нормализованный `C9ZJ` | всегда | found |
| `wi_trace_id` (ровно 24 символа) | `$wiTraceId` из `reportAsSpam$1` | опционально | found; происхождение значения unknown |
| `is_known_chat` = `"true"`/`"false"` | `C33446EhE.A09` | flag **22256**; пользователь: проверка адресной книги, группа: проверка членства в группе | found |
| дочерний `biz_opt_out` | `C33446EhE.A07` | существует запись business discovery | found (см. 8.3) |

---

## 5. Stanza по типам

`from`/`to` элемента `<message>`: для пути пользователя анонимный узел `C9E4` задаёт `to=<jid>`, когда сообщение исходящее (`key.fromMe`), и `from=<jid>` в остальных случаях. Количества — ограничения builder (`AbstractC10350Ul.A07`).

### 5.1 Пользователь (тип 20)

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

Builder принимает три списка элементов с ограничениями 210 (сообщения), 5 (элементы звонков), 5 (бессообщенческие элементы business-flow, `C33446EhE.A0B`: последние 5 записей из хранилища по бизнесу `messageless_flow_ids_per_business_<jid>`, узел `extension_screen`). `jid` проверяется только на `UserJid` и `C99O`; `subject` на этом пути нет.

### 5.2 Группа (тип 19)

```xml
<iq type="set" id to="s.whatsapp.net" xmlns="spam">
  <spam_list jid="<groupJid>" source="<adderJid?>" subject="<group name>" spam_flow="group_info_report">
    <message from="<senderJid>" t id>...</message>     <!-- 0..210 -->
  </spam_list>
</iq>
```

- `source` — это **пользователь, добавивший автора жалобы в группу**, а не сам автор жалобы. Читается из локального системного сообщения ("me joined") SQL-запросом `GET_GROUP_ADDER_JID_SQL` (`C16100hT.A01`, `action_type` 12/124/144/127, `is_me_joined = 1`). Опционально. (found)
- `subject` — отображаемое имя группы из записи контакта (`C06290Dn.A07().A00.A0b`; смысл поля inferred), пустая строка `""` для родительских групп сообществ или когда записи нет (`Voip.REJECT_REASON_DECLINED` равно `""`). Это не причина. Ограничение длины 0..65536. (found)
- Четвёртый список в конструкторе выбрасывает исключение (`getNode`), если не пуст; RPC передаёт пустой список.

### 5.3 Newsletter (тип 21) и пост статуса (тип 22)

```xml
<spam_list jid="<newsletterJid>" subject="<channel name or ''>" spam_flow="newsletter_info_report">
  <message from="<newsletterJid>">...</message>        <!-- 0..65 -->
</spam_list>
<spam_list jid="<statusPosterJid>" spam_flow="status_post_report">
  <message from="<posterJid>">...</message>           <!-- 1..2 items, only the first selected status is passed -->
  <biz_opt_out .../>                                   <!-- optional -->
</spam_list>
```

`subject` newsletter = имя канала (`C2130898y.A0j`), `""` если неизвестно (found). Жалобы на статусы используют собственные таблицы токенов `status_reporting_info` / `status_reporting_content`.

### 5.4 Статус канала V2 (тип 23)

```xml
<spam_list jid="<newsletterJid>" spam_flow="...">
  <status server_id="<99..2147476647>" t="<1577865600..4102473600>">...</status>
</spam_list>
```

Статус идентифицируется по `server_id` + временной метке, загруженного содержимого нет. Содержимое дочернего `status` (`InterfaceC35700FdB`) не выяснено.

### 5.5 Событие (тип 18)

`<spam_list event_id="<1..64 chars>" spam_flow="..."/>`, без `wi_trace_id` (путь `C9E2(String)` с одним аргументом). Сообщение админам (тип 0): раздел 9.1.

---

## 6. Содержимое жалобы и токены

### 6.1 Что загружается (found)

`C33446EhE.A0A(fmsg, entryPoint)` строит один элемент сообщения на каждое сообщение, на которое поступила жалоба:

| Часть | Подробности |
|-------|-------------|
| атрибуты `<message>` | `t` (временная метка сообщения, 0..2^53), `id` (id stanza), jid `from`/`to`, `deleted_reason` = `view_once_opened` / `view_once_expired` |
| `<raw v="2" local_message_type mediatype>` | заново сериализованный protobuf `Message` (`C30628DTw` с `MessageContextInfo` `C30624DTs`); `local_message_type` = внутренний int типа сообщения |
| `<content_validation>` | токен + ключ (6.2) |
| мета-флаги | `<edit v="1">` (изменено), `<multicast/>` (флаг broadcast 64), `<url_number/>` (флаг 4), `<url_text/>` (флаг 2), id шаблона, `hsm` tid, `iab reported_link`, `original_sender` / `group_history_sender`, варианты платежей `futureproof`/`request`/`send` (`pay`), `reported_push_name` |
| дочерний `<reporting>` | flag **5718**: строится из строк `reporting_info` сообщения (`C23070uA.A03`), до 1000 записей (`C31085Dfd` case 28); схема отдельной записи прочитана не полностью |
| альтернативные носители | `<plaintext>`, `<enc type=msg|pkmsg|skmsg|media|text>`, `<reporting_content>` (`C31084Dfc`, `C31081DfZ`) |

`mediatype` (33 значения, found): `audio, avatar_sticker, buttons_response, catalog, cataloglink, collection, contact, contact_array, document, genai_sticker, gif, image, invite, list, list_response, livelocation, location, native_flow_response, order, product, productlink, product_list, ptt, ptv, sticker, sticker_pack, system, unknown, url, user_created_sticker, vcard, video, 1p_sticker`.

Шаблонные сообщения OTP: заполнитель `<code>` в заголовках кнопок заменяется реальным кодом перед сериализацией (`AbstractC32303E8u.A00`). View-once: когда сообщение view-once, уже открыто/истекло, а origin не `media_viewer` / `view_once_viewer`, `A06` истинно и блок сериализации пропускается. Несёт ли элемент после этого пустой или отсутствующий `raw` — inferred (объявление не инициализировано в декомпиляции).

Медиафайлы этой stanza повторно не загружаются; сериализованное сообщение несёт ссылки на медиа (inferred; вызова загрузки не найдено). Stanza содержит plaintext proto и ключ вместе, поэтому сервер может прочитать содержимое: узлы **found**, читаемость **inferred**.

### 6.2 Reporting-токен и ключ (found)

```xml
<content_validation type="e2e_proto_message">          <!-- "mms_retry" when the stored token row has retry mode 1 -->
  <reporting_token v="<int>"><tag, >=6 bytes></reporting_token>
  <reporting_token_key><key, 16..32 bytes></reporting_token_key>
</content_validation>
```

Собирается в `C33446EhE.A03` из сохранённой строки (`C34539Ez0`): байты токена (`A05`), версия (`A02`), id stanza (`A03`), ключ (`A07`). Если ключ отсутствует, он выводится заново: `C33364Efs.A06(chat, sender, stanzaId, messageSecret)` → native `WCMMessageSecretAPIUsecaseCreateDerived(secret, stanzaId, sender, receiver, 5)` (id use case **5**; не-пользовательские чаты идут через варианты `JniBridge`). Если и ключ, и 6-байтовый токен отсутствуют/нулевые, клиент пишет в лог `ReportingToken/MissingFkAtReport` и использует нулевой 32-байтовый ключ. Отсутствующий токен возвращает `null` (`ReportingToken is null`, у элемента нет `content_validation`).

### 6.3 Жизненный цикл токена (found, если не указано иное)

| Этап | Подробности |
|------|-------------|
| Исходящее сообщение | builder `C35241aW.A00(token16, v)` → `<reporting><reporting_token v="<n>">16 bytes</reporting_token></reporting>`. Токен = первые 16 байт `HMAC-SHA256(key, canonicalContent)` (`C35241aW.A04`, `AbstractC38971i1.A00`). `canonicalContent` = proto сообщения с зависящей от версии фильтрацией полей (`A07`, убирает выбранные подполя поля 35; прочтение inferred). Вызывающие builder не прослежены |
| Передача истории группы | `F6C` (`GhsReportingTokenMessageSendStanzaContributor`): для сообщений типа 117 `<reporting>` с одним дочерним на запись (атрибут `id`, дочерний `<reporting_token v>`) |
| Входящее сообщение | дочерний элемент stanza `<reporting validation_policy?><reporting_tag>BYTES</reporting_tag><reporting_token v>BYTES</reporting_token></reporting>` разбирается `C34764F6h` / `C1S0`, flag **5718**; и tag, и token опциональны, tag обязателен |
| Хранение | таблицы `reporting_info` (`reporting_tag`, `stanza_id`, `is_message_add_on`, `send_timestamp`, `receive_flow`) и `reporting_info_content` (`reporting_token`, `reporting_token_content`, `reporting_token_version`, `reporting_token_key`); `message_conditional_reveal.reporting_token_info` (blob); `group_history_share_reporting_info`; `status_reporting_info` |
| История | `WebMessageInfo.reportingTokenInfo` поле **62** = `ReportingTokenInfo` (`DR0`): `reportingTag` **1** bytes, `reportingTagTimestamp` **2** uint64; flag **6578** |
| Очистка | строки `reporting_info*` удаляются, когда `receive_timestamp` старше порога (`FP7` case 6); значение порога не выяснено |
| Альтернативный узел проверки | `<reporting_validation><reporting_tag id ts_s participant>bytes</reporting_tag></reporting_validation>` (`C31081DfZ`) |

Кто выдаёт `reporting_tag` и как сервер проверяет токен: на стороне сервера, unknown. Связка (tag в stanza, token+key в жалобе) — inferred.

---

## 7. Точки входа `spam_flow`

97 значений (found, `C9E2` case 5, порядок = порядок массива). Аргумент `flow` проходит через `C9ZJ.A00`, который принимает **78** из них и в противном случае выбрасывает `IllegalArgumentException("Invalid BlockSpamReportOrigin value")`. Все шесть обёрток RPC вызывают его, а `SpamReportRepo.A02` перехватывает исключение и возвращает сбой (клиентская ошибка, stanza не отправляется). 78 — строгое подмножество 97. 19 отклоняемых значений: `account_info, account_info_report_as_guest_user, block_dialog, call_log, call_spam_dialog_block, channel_status_report, chat_fmx_card_report_as_guest_user, chat_list_context_menu_block, chat_list_swipe_delete_block_upsell, chat_list_swipe_delete_report_upsell, ent_client, frx, group_chatlist_swipe_leave_report_upsell, group_info, guest_call_participant_report, guest_call_report, overflow_menu, overflow_menu_community_report, payment_transaction_report`. Вероятно, это origin только для блокировки или для других RPC (inferred). `channel_status_report` есть в enum, но отклоняется `C9ZJ`; какой flow передаёт вызывающий статус канала — unknown.

| Поверхность | Значения |
|-------------|----------|
| Чат / 1:1 | `chat`, `message_menu`, `overflow_menu`, `overflow_menu_report`, `overflow_menu_block`, `block_dialog`, `block_header_chat`, `chat_list_block`, `chat_list_context_menu_block`, `chat_list_noinsub_block`, `chat_list_swipe_delete_block_upsell`, `chat_list_swipe_delete_report_upsell`, `triggered_block`, `notification_block`, `missed_call_notification_block`, `feedback_not_interested_block`, `user_controls_stop_block`, `media_viewer`, `view_once_viewer`, `account_info`, `account_info_block`, `account_info_report`, `account_info_report_as_guest_user`, `album_media_menu_report`, `iab_menu_report`, `extension_menu_report`, `comment_actions_bottom_sheet`, `payment_transaction_report` |
| Спам-баннеры | `1_1_spam_banner_block`, `1_1_spam_banner_report`, `1_1_old_spam_banner_block`, `one_to_one_spam_banner_block_server_flagged_suspicious`, `user_initiated_chat_suspicious_banner_block`, `user_initiated_chat_suspicious_banner_safety_tools_block`, `user_initiated_chat_suspicious_banner_safety_tools_report`, `dependant_chat_request_banner_decline_report_upsell`, `dependant_unknown_conversation_trust_signals_block` |
| Карточки безопасности FMX | `chat_fmx_card_block`, `chat_fmx_card_block_suspicious`, `chat_fmx_card_block_server_flagged_suspicious`, `chat_fmx_card_report_as_guest_user`, `chat_fmx_card_safety_tools_block`, `..._block_suspicious`, `..._report`, `..._report_suspicious`, `user_initiated_chat_fmx_card_safety_tools_block`, `..._report`, `trust_question_bottomsheet_block_server_flagged_suspicious` |
| Оповещения о мошенничестве на устройстве | `odml_scam_alert_blocked_composer_block`, `odml_scam_alert_bottom_sheet_block`, `odml_scam_alert_bottom_sheet_trust`, `odml_scam_alert_fmx_card_block`, `odml_scam_alert_fmx_card_trust`, `odml_scam_alert_suspicious_banner_block`, `odml_scam_alert_suspicious_banner_trust` |
| Группа | `group_info`, `group_info_report`, `group_info_leave_report_upsell`, `group_spam_banner_exit`, `group_spam_banner_exit_group_history`, `group_spam_banner_report`, `left_group_spam_banner_report`, `group_safety_check_bottom_sheet`, `group_fmx_card_leave`, `group_fmx_card_leave_non_suspicious`, `group_chatlist_leave_report_upsell`, `group_chatlist_swipe_leave_report_upsell`, `group_overflow_menu_leave_report_upsell`, `community_home`, `community_announcement_group_suspicious_banner_exit_dialog`, `community_home_suspicious_banner_exit_dialog`, `overflow_menu_community_report` |
| Звонки | `call_log`, `call_log_block`, `call_detail_overflow_report`, `call_detail_safety_tools_block`, `call_detail_safety_tools_report`, `call_spam_dialog_block`, `call_spam_dialog_report`, `guest_call_report`, `guest_call_participant_report` |
| Каналы / статус / события | `newsletter_info_report`, `newsletter_question_response_report`, `channel_status_report`, `status_post_report`, `status_question_answer`, `wamo_channel_report`, `event_home_report`, `event_info_report` |
| Бизнес | `biz_account_info_block`, `biz_block_header_chat`, `biz_block_list`, `biz_call_log_block`, `biz_overflow_menu_block`, `biz_spam_banner_block`, `ent_client`, `frx` |

Выбор между `*_suspicious` и обычным для карточек FMX делается в `C230769yA.A05` по `A0D(userJid)` (известен контакт или нет); этот предикат, по выводу, является проверкой адресной книги (inferred). Варианты `server_flagged` выбираются по типу карточки; откуда берётся серверный флаг — unknown.

`wi_trace_id`: необязательный атрибут из 24 символов, передаётся от вызывающего; его генератор не найден (unknown). Это также поле WAM `wam_spam_report_perf` (11.3).

---

## 8. Блокировка, причины и бизнес-контекст

### 8.1 IQ блокировки (found, область `C34631Yx.A0M`)

```xml
<iq to="s.whatsapp.net" id="<id>" type="set" xmlns="blocklist">
  <item action="block|unblock" jid="<chat jid>" dhash="<list hash?>" pn_jid|username|display_name|unknown_identifier="...">
    <biz_opt_out first_message="true|false|none" reason="<code>" reason_description="<text>"
                 entry_point="<flow>" business_discovery_entry_point business_discovery_timestamp business_discovery_id/>
  </item>
  <entry_point source="<flow>"/>
</iq>
```

`biz_opt_out` и `entry_point` выдаются только для `action="block"`. `jid` выбирается между формами PN и LID проверкой настройки (ветка `zA02`; точное правило прочитано не полностью); при блокировке дополнительный идентификатор — один из `pn_jid` / `username` / `display_name` / `unknown_identifier="true"`. Таймаут 20000 мс. Точки входа, начинающиеся с `odml_scam_alert_*`, переписываются в `1_1_spam_banner_block` (`odml_scam_alert_fmx_card_block` → `chat_fmx_card_block`). Чаты PSA используют другой IQ (`xmlns="w:comms:chat"`, `<blocking action>`). Получение: `type="get"`, опциональный `<item dhash>`.

### 8.2 Причины блокировки (found)

Жёстко заданная строка → локальный int в `AbstractC227579sl.A00`: `no_longer_needed`/`no_longer_interested` = 1, `no_sign_up` = 2, `spam` = 3, `offensive_messages` = 4, `otp_did_not_request` = 5, `scam_or_fraud` = 6, прочее = 0. `RunnableC40792Hpk` сопоставляет те же строки со вторым набором кодов. Эти int идут в вызовы локального лога; доходят ли они до сервера — unknown.

Лист блокировки бизнеса (`C24126Ab7`): серверная карта причин, если не пуста, иначе `no_longer_needed, no_sign_up, spam, scam_or_fraud, other`; чаты шаблонов OTP: `no_longer_interested, otp_did_not_request, other`.

### 8.3 Контекст business discovery (found)

`C33446EhE.A07` читает запись business-discovery для JID, на который жалоба (хранилище `LA8`): временная метка, id, точка входа. Enum точки входа (18 + `unknown`): `biz_profile, broadcast_list_context_menu, catalog_link, click_to_chat_link, contact_card, contact_search, ctwa, global_search_new_chat, group_participant_list, message_short_link, other_qbm, otp_qbm, phone_number_hyperlink, product_link, promotional_qbm, qr_code, status, transactional_qbm`. Прикрепляется и к жалобам (`biz_opt_out` под `spam_list`), и к блокировкам. Это единственные сигналы «как начался этот чат», найденные в клиенте.

### 8.4 Списки причин жалобы (found)

Выбираемый список есть только у бизнес-рекламы. `ReportReasonListFragment` начинает пустым и заполняется из `<iq xmlns="w:biz" type="get"><mobile_config name="biz_report_reasons" v="1" report_type="status_ad|business_user"/></iq>` (ответ `mobile_config` > `list` с `name`, `v`, `country`). Жёстко заданный резервный enum (`EnumC37888GeT`): `scam_or_fraud`, `pretending_impersonation`, `illegal_dangerous`, `inappropriate_hateful_violent`, `dont_like_ad`. Когда используется резерв: inferred как недоступность серверного списка. Для обычных жалоб на пользователя/группу/сообщение выбора причины нет; единственная «причина» в сети — `spam_flow`.

---

## 9. Жалоба админам группы

### 9.1 Отправка и получение (found, `RtaXmppClient`)

```xml
<!-- reportMessageToAdmin, type 0, smax 385 -->
<iq to="<groupJid>" type="set" xmlns="w:g2" id><reports><report message_id="<stanza id>"/></reports></iq>

<!-- getReportedMessages, admin side -->
<iq to="<groupJid>" type="get" xmlns="w:g2" id><reports/></iq>
<!-- response: report{message_id} > reporter{jid, timestamp} x1..19999 -->
```

Содержимое, токен и `spam_flow` не отправляются; только id сообщения. Ошибки лишь пишут в лог `Rta::<op>/onError: <code>` или `/onDeliveryFailure: Network Failure`.

### 9.2 Переключатель жалоб участников (found)

`$t=1`: `<iq to="<groupJid>" type="set" xmlns="w:g2"><allow_admin_reports/></iq>` (включить) или `<not_allow_admin_reports/>` (выключить), smax 384. Узлы являются прямыми дочерними IQ, не обёрнуты в узел `group`. Builder принимает до четырёх соседних узлов настроек в одном IQ.

---

## 10. Ответ сервера и диалоги завершения

### 10.1 Ответ (found)

Успех (`type=result`): дочерний `report` с атрибутом `id` (максимум 20 символов) → `C213959Ch.A01` → возвращается в UI как id жалобы. Ошибки (`<error code text>`) по классам ответа:

| Код | Имя | Individual | Group | Newsletter | Status | Status V2 | Event |
|-----|-----|------------|-------|------------|--------|-----------|-------|
| 400 | `bad-request` | x | x | x | x | x | x |
| 403 | `forbidden` | x | | | x | x | |
| 429 | `rate-overlimit` | x | | | x | x | |
| 500 | `internal-server-error` | x | x | x | x | x | x |
| 501 | `feature-not-implemented` | x | x | | | | x |
| 548 | `report-token-validation-fail` | x | x | | x | | x |

### 10.2 Диалоги завершения

`H2U` решает по id жалобы и условиям, затем `C5BD` строит фрагмент (`arg_report_id`, `arg_is_ad_report`):

| Условие | Диалог |
|---------|--------|
| flag **25818**, чат с пользователем, сообщение присутствует | `NciiCompletionDialogFragment` |
| flag **6145** | `DsaCompletionDialogFragment` (ЕС) |
| flag **14249** | `UkOsaCompletionDialogFragment` |
| flags **12987** / **12990** | `AustraliaOsaCompletionDialogFragment` |

Всем, кроме NCII, нужен не-null id жалобы; нет id — нет диалога.

---

## 11. Сигналы злоупотреблений на клиенте

### 11.1 Что клиент отправляет помимо содержимого (found)

Точки входа с `*_server_flagged_suspicious` означают, что карточка была показана для чата, помеченного сигналом, отличным от локальной проверки контакта; как клиент узнаёт этот флаг — unknown. В жалобах отправляются: `is_known_chat`, `biz_opt_out` (как начался бизнес-чат), элементы звонков (длительность, кто завершил, terminate reason), контекст бизнес-Flows `extension_screen`, `source` (кто добавил меня в группу), `reported_push_name`, флаги forward/broadcast/URL на каждом сообщении, флаг изменения, состояние view-once, точка входа, опциональный `wi_trace_id`.

### 11.2 Обнаружение мошенничества на устройстве (found, ограниченно)

`com.whatsapp.integrityai` запускает загруженный набор моделей (`scam_detection`) на устройстве через ExecuTorch (`ScamDetectorImpl`, `EmbeddingProviderImpl`, `InputFeatureProviderImpl`; признаки `mostRecentSenderScore`, `isCountryMismatch`). Результаты управляют предупреждающими баннерами/листами и точками входа `odml_scam_alert_*` выше. Локальная JSON-запись сканирования (`outcome`, `inputs`, `model_info`, `verification`) записывается в `FileStash`, когда `integrity_warning_report_enabled` (`C57375Pog`). Загрузки этой записи не найдено (unknown). Она не зависит от stanza жалобы `spam`.

### 11.3 Телеметрия (found)

WAM `wam_spam_report_perf` (`C97R`, id 6310): `dedup_key`, `report_attempt_count`, `report_duration_ms`, `report_error_code`, `report_spam_flow`, `report_status`, `wi_trace_id`. Сопоставление кодов ошибок в `reportAsSpam$1`: отмена -4, таймаут/нет ответа -1, прочее исключение -3, ошибка протокола = код ошибки IQ.

---

## 12. Baileys

В пакете `baron-baileys-v2` нет API жалоб. Формы ниже получены из найденных узлов и untested.

```ts
// report to group admins (smallest, no token needed)
await sock.query({
  tag: 'iq',
  attrs: { to: groupJid, type: 'set', xmlns: 'w:g2' },
  content: [{ tag: 'reports', attrs: {}, content: [
    { tag: 'report', attrs: { message_id: stanzaId } } ] }]
})
```

Формы жалоб на пользователя/группу/канал соответствуют разделу 5 (один слитый `spam_list`, `xmlns: 'spam'`, `to: 's.whatsapp.net'`).

| Почему не работает (всё inferred) | Причина | Исправление |
|--------------|-------|-----|
| ошибка 548 или молчаливое отсутствие эффекта | нет действительного reporting-токена/ключа: Baileys отбрасывает дочерний `<reporting>` входящих сообщений и никогда не выводит ключ | разбирать `reporting_tag`/`reporting_token` при получении, хранить на сообщение, выводить ключ из `messageSecret` (use case 5) в момент жалобы |
| 400 | `jid` неверного класса (для типа 20 должен быть user/interop), количества элементов выше ограничений, `spam_flow` неверного типа | использовать строки `spam_flow` из раздела 7; оставаться в пределах 210 / 5 элементов |
| IQ отклонён | два соседних `spam_list` (причина отправлена вторым узлом) вместо одного слитого узла | отправлять один `spam_list` со всеми атрибутами |

И `wi_trace_id`, и `is_known_chat` в builder опциональны; принимает ли сервер жалобы с подделанными токенами — unknown.

---

## 13. Случаи ошибок

| Симптом | Причина | Уровень |
|---------|---------|---------|
| toast `str3bf8`, ничего не отправлено | `C9ZJ` отклонил значение `flow` (`Invalid BlockSpamReportOrigin value`) | found |
| сбой `unrecognized jid` | JID чата не является пользователем/группой/статусом/newsletter | found |
| жалоба «не удаётся» без toast | ошибка сервера 548: `C9ZI.A00` возвращает тот же объект результата без ошибки, что и путь бота | found |
| общий toast сбоя | 400/403/429/500/501 или таймаут (32 с) → `C216549Uq` | found |
| содержимое жалобы отсутствует | view-once открыто/истекло, а origin не viewer; у сообщения нет сохранённого токена | found / inferred |
| локальное состояние говорит «жалоба отправлена», сервер отклонил | `is_spam_reported` записывается после RPC без видимой проверки результата | found (поток), inferred (следствие) |

---

## 14. Ключевые различия

| Не путать | С |
|-----------|---|
| `spam_list@source` | автором жалобы. Это пользователь, добавивший автора жалобы в группу |
| `spam_list@subject` (группа, канал) | причиной. Это имя группы/канала |
| `spam_flow` | причиной жалобы. Это поверхность UI, вызвавшая жалобу (97 значений) |
| жалоба (xmlns `spam`) | блокировкой (xmlns `blocklist`), report-to-admin (xmlns `w:g2`), маркетинговым отказом (xmlns `optoutlist`, `C31105Dfx`, дальше не анализировалось) |
| два узла `spam_list` | один слитый `spam_list` (атрибуты и дочерние объединены) |
| спам звонков | спам событий. Жалобы на звонки — тип 20 с элементом `call`; тип 18 — это `event_id` |
| `reporting_tag` (выдаётся сервером, сохраняется при получении) | `reporting_token` (16-байтовый HMAC, отправляется с исходящими сообщениями и загружается в жалобах) и `reporting_token_key` (выводимый, загружается) |
| report-to-admin | жалобой в WhatsApp. Жалоба админу отправляет только `message_id`; ни содержимого, ни токена |
| `wi_trace_id` (id трассировки, отправляемый клиентом) | id жалобы, который сервер возвращает в `<report id>` |
| `report_block` | значением в сети. Это строка аналитики/toast клиента; блокировка — отдельный IQ |
| переключатель `allow_admin_reports` (`$t=1`) | сообщением report-to-admin (`$t=0`) |

---

## 15. Сквозной процесс

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

| Элемент | Причина |
|---------|---------|
| Серверная проверка токена, выдача `reporting_tag`, как решается `server_flagged` | серверная логика, нет в APK |
| Происхождение `wi_trace_id` | генератор не найден в декомпиляции |
| Триггер UI жалобы на событие, формат жалобы чата с ботом в сети | только вызывающие лямбды (`AYs`, `Aaa`) / `reportUgc` не прослежен дальше `C33437Eh4` |
| Строка flow, которую передаёт вызывающий жалобы на статус канала | `channel_status_report` отклоняется `C9ZJ` |
| Порог очистки `reporting_info*` | вызывающий `FP7` case 6 не прослежен |
| Загрузка локальной записи сканирования на мошенничество | потребитель не найден |
| Схема отдельной записи дочернего `reporting` на сообщение и назначение вызова flag 20085 | строится из строк БД, логика потребителя не прочитана |
| Реальное принятие любой stanza из раздела 12 | трафик не перехватывался |
