<!-- src-sha1: 0c8270cd51a33a8c9e23ceb0a6129e273e5cb070 -->
# WhatsApp История группы — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** передача истории группы на Android (недавние сообщения группы, отправляемые новым участникам): настройка администратора `member_share_group_history_mode`, допустимость отправителя и получателя, поток добавления / одобрения и отложенное задание, выбор сообщений и лимиты, `MessageHistoryBundle` (поле 70) и `MessageHistoryNotice` (поле 102), внутренний proto `GroupHistory`, шифрование и загрузка медиа пакета, проверка и импорт на стороне получателя, метаданные группы (участники, адресация LID и PN, связи сообщества), использование sender-key, reporting-токены, HistorySync компаньонов (`HistorySyncConfig`, типы синхронизации, peer-операции по запросу), feature-флаги, Baileys

---

## 1. Что это (технически)

Передача истории группы позволяет участнику группы (администратору или любому участнику, если администратор разрешает) отправить только что добавленным людям пакет недавних сообщений группы, чтобы новичок видел контекст. Это обычное сквозно зашифрованное групповое сообщение, полезная нагрузка которого является медиафайлом (protobuf из записей `WebMessageInfo`). Это **не** HistorySync компаньон-устройств (раздел 11), хотя в обоих случаях встречается слово "history" и несколько общих capability-флагов.

Все утверждения получены статическим анализом декомпилированного APK; ничего не перехватывалось в сети. Уровни: **found** = прочитано в коде или ресурсах, **inferred** = выведено из кода, **unknown** = не выяснено. Обфусцированные имена заново определены в 2.26.41.6 по стабильным строкам (`FMessageGroupHistoryBundleProtobuf`, `GroupHistorySendPermissionChecker`, `PendingSendGroupHistoryJob`, `member_share_group_history_mode`, `Group History`).

| Сущность | Имя в 2.26.41.6 | Роль |
|----------|-----------------|------|
| Сообщение-пакет | `C213539Ar` (`FMessageGroupHistoryBundle`), тип FMessage **117** | внешнее медиасообщение, `Message.messageHistoryBundle` поле **70** |
| Сообщение-уведомление | `C213519Ap` (`FMessageGroupHistoryNotice`), тип FMessage **118** | строка "история отправлена", `Message.messageHistoryNotice` поле **102** |
| Сериализатор / парсер пакета | `C34677F2y` (`FMessageGroupHistoryBundleProtobuf`) | сборка и проверка внешнего сообщения |
| Сериализатор / парсер уведомления | `C34678F2z` (`FMessageGroupHistoryNoticeProtobuf`) | сборка и проверка уведомления |
| Построитель пакета | `C9mW.A00` (+ `C231239yy`, `FMessageGroupHistoryBundleFactory`) | выбор, упаковка, запись файла, создание медиасообщения |
| Выбор сообщений | `A0G` (`GroupHistoryMessageManager`) | SQL для подсчёта и строк |
| Допустимость | `A1W` (`GroupHistorySendPermissionChecker`), `C230099x1` (гейты) | проверки отправителя / получателя / точки входа |
| Отложенное задание | `PendingSendGroupHistoryJob`, `SendGroupHistoryJobRequirement` | долговечное задание после добавления |
| Поставщик условий | `C197318aR` (`SendGroupHistoryRequirementProvider`) | события добавления / одобрения освобождают задание |
| Получатель | `GroupHistoryBundleProcessor`, `GroupHistoryBundleFileProcessor` | загрузка, разбор, вставка |
| Валидаторы / вставка | `C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg` (`GroupHistoryMessageValidator` / `GroupHistoryMessageInserter`) | проверки каждого сообщения и вставка в БД |
| Строка типа медиа | `C15530gU.A0F` | `group-history`, `GROUP_HISTORY`, HKDF info `Group History`, id **117** |
| UI настроек | `com.whatsapp.grouphistory.setting.ui.*`, `GroupPermissionsActivity` (`C201678ic`) | диалог количества, переключатель в футере, переключатель разрешения |

При каждой отправке существуют два разных сообщения: **пакет** (несёт данные, отправляется в группу) и **уведомление** (несёт только количества и получателей, отправляется после того, как пакет покинул устройство, раздел 5.4).

---

## 2. Метаданные группы и настройки

### 2.1 Узел информации о группе (`<group>`, устаревший XMPP-путь `C23201A1a.A0C`)

Разбирается одним и тем же хелпером для запросов `w:g2` и групповых уведомлений; существует близнец MEX/SMAX (`AbstractC23204A1d`, `AN6`, `C23690AKd`). Только поля, относящиеся к теме и адресации:

| Атрибут / дочерний элемент | Тип | Назначение |
|----------------------------|-----|------------|
| `id`, `creation`, `subject`, `s_t`, `s_o`, `s_o_pn`, `creator`, `creator_pn` | attrs | идентификация; близнецы `_pn` несут телефонный JID рядом с LID |
| `addressing_mode` | `lid` или `pn` | хранится в `wa_group_admin_settings.addressing_mode`; всё, кроме `pn`, читается как `lid` (`AbstractC268510t`) |
| `<group_history/>` | пустой дочерний элемент | булево по наличию; хранится как `history_enabled`; смысл inferred (feature-флаг группы) |
| `<member_share_group_history_mode>` | текст | настройка администратора, 2.4 |
| `<member_add_mode>` | `all_member_add` / иное | `member_add_mode` 1 / 0 |
| `parent`, `default_sub_group`, `linked_parent jid`, `general_chat` | дочерние элементы | тип группы, 2.3 |

### 2.2 Участники и адресация (found)

`<participant jid lid phone_number type display_name username join_time group_history_sent>` (`C23201A1a.A05`, `C23205A1e.A0J`):

| Атрибут | Использование для истории группы |
|---------|----------------------------------|
| `jid` | участник, LID или PN в зависимости от `addressing_mode`; PN JID с атрибутом `phone_number` проверяется на несовпадение |
| `lid`, `phone_number` | другая форма адреса; сохраняется через репозиторий соответствий JID |
| `join_time` | положительный long (секунды, inferred); хранится для каждого участника; основа для "присоединился слишком давно" |
| `group_history_sent` | `"true"` / `"false"`, Boolean; питает `group_participant_user.group_history_send_state` (соответствие inferred, 3.2) |

Списки получателей и отправителей в метаданных пакета (раздел 6.2) являются строками JID. Задание нормализует их к режиму адресации группы перед использованием: `PendingSendGroupHistoryJob.A01` отображает каждого получателя в его **LID**, если группа адресуется по LID (`C30194DBb.A05`), иначе отображает LID в PN (`C0YH.A0G` / `AbstractC197018Zw.A0Y`). При добавлении участника задание принимает обе формы (`C0YH.A0J` возвращает парную) для сопоставления с наборами условий. Какая форма попадает в сеть, зависит от режима группы (inferred из кода отображения).

### 2.3 Связи сообщества и родительской группы

`C23201A1a.A01` классифицирует узел группы: **0** обычная, **1** родитель сообщества (`parent`), **2** связанная подгруппа (`linked_parent`), **3** подгруппа по умолчанию (`default_sub_group`), **6** общий чат. `A03` читает JID родителя из `linked_parent jid`. Значение по умолчанию `membership_approval_mode` для подгрупп берётся из `parent/default_membership_approval_mode="request_required"`.

Found: `A1W` проверяет только **тип JID** (типы 1 и 2 проходят `C0DZ.A0l`: группа `@g.us` и группа `@temp` `C99Q`), но не роль в сообществе. Получатель принимает только тип 1 (`C0DZ.A0b`). Исключается ли родительская группа / группа объявлений серверными или пергрупповыми экспериментальными гейтами (23245 / 30905 пергрупповые), unknown. Сообщения-комментарии (комментарии к объявлениям сообщества) и дочерние ассоциации идут в отдельных списках (6.1); получатель отбрасывает комментарий или дочерний элемент, родителя которого нет в пакете (`orphan_parent_not_in_bundle`, `invalid_comment`).

### 2.4 Настройка администратора `member_share_group_history_mode`

| Значение в сети | Enum (`EnumC216299Tq`) | Локальный int | Значение |
|-----------------|------------------------|---------------|----------|
| отсутствует / неизвестно | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE` 0 | 0 | не задано |
| `admin_share` | `ADMIN_SHARE` 1 | 1 | историю отправляют только администраторы |
| `all_member_share` | `ALL_MEMBER_SHARE` 2 | 2 | отправлять может любой участник |
| `all_member_share_toggle_on` | `ALL_MEMBER_SHARE_TOGGLE_ON` 3 | 2 | то же, что 2; вариант, встречающийся в уведомлениях (различие inferred) |

Отображение: `AbstractC227759t3.A01(String)` (строка в int), `A00(enum)` (enum в int, 2 и 3 в 2).

| Пункт | Детали (found) |
|-------|----------------|
| Установка | переключатель `GroupPermissionsActivity` (`C201678ic.A04`): операция MEX `SetGroupProperty` (клиент `whatsapp-android-mex`, входной класс `C204518nF`) с `member_share_group_history_mode` = `ALL_MEMBER_SHARE` или `ADMIN_SHARE`. Тот же ввод несёт также `allow_admin_reports`, `allow_non_admin_sub_group_creation`, `announcement`, `hidden_group`, `locked`, `member_add_mode`, `member_link_mode`, `membership_approval_mode_enabled`, `participant_label_enabled`, `subject` |
| Уведомление | групповое уведомление (`w:gp2`, inferred), дочерний элемент `member_share_group_history_mode` (`C22270sr`) вызывает `A0g(actor, group, mode int, ts)`: обновляет сохранённый режим и вставляет системное сообщение |
| Системное сообщение | "включил(а) / выключил(а) передачу недавней истории новым участникам" в шести вариантах (актор `%s`, "Recent history sharing was ...", "You ..."), каждый с "Tap to change" или "Tap to learn more" |
| History sync | `GroupShareGroupHistoryModeHistorySync` воссоздаёт системное сообщение для компаньонов; `GroupChangeHistoryEnabledHistorySync` делает то же для `history_enabled` |
| БД | `wa_group_admin_settings`: `share_group_history_setting_mode`, `group_history_toggle_mode`, `history_enabled`, `earliest_group_history_message_timestamp_ms` |

Значение `group_history_toggle_mode` (int, отдельно от режима передачи) не выяснено; столбец читается для групп, где он ненулевой и `group_state = 0`. Тексты UI: "Admins can choose if members are allowed to send message history", "Admins control if history is sent", "When adding someone to the group, members have the choice to send up to 100 recent messages".

---

## 3. Допустимость

### 3.1 Отправитель (`A1W.A03`, found)

| # | Условие | Иначе |
|---|---------|-------|
| 1 | включён kill switch **35987** (предпосылки отправителя) | `PREREQUISITES_DISABLED` |
| 2 | тип JID группы 1 или 2 | `GROUP_TYPE_NOT_ELIGIBLE` |
| 3 | строка контакта группы существует | `GROUP_NOT_FOUND` |
| 4 | я в группе, и либо я admin / superadmin, либо (`require_membership_approval` = false и `member_add_mode` = 1 и режим передачи = 2) | `SENDER_NOT_ELIGIBLE` (лог перечисляет три значения) |
| 5 | существует хотя бы одно сообщение, которым можно поделиться (счёт `A0G.A00` > 0) | `NO_SHAREABLE_MESSAGES` (также корректирует сохранённую самую раннюю метку времени, `A0A`) |
| 6 | гейт по точке входа `A1W.A02` (3.3) | `EXPERIMENT_DISABLED` |

Таким образом, обычный участник может отправлять только в группах, где любой может добавлять участников, одобрение не требуется и администратор включил `all_member_share`.

### 3.2 Получатель (для каждого добавленного пользователя, found)

| Проверка | Код результата |
|----------|----------------|
| получатель не бот (`AbstractC24760wu.A03`) | `RECEIVER_NOT_ELIGIBLE` |
| контакт получателя не "больше не активен" (`externalUserState`, `A07`) | `RECEIVER_INACTIVE` |
| строка участника для (группа, пользователь) существует | `NOT_IN_GROUP` |
| `now - join_time` меньше флага **30333** (единица не выяснена) и `group_history_send_state` равен null или 1 | `NOT_NEW_OR_ALREADY_SENT` |

`group_history_send_state` (столбец `group_participant_user`, записывается `C14850fN.A0R`): 1 = всё ещё допустим, 2 = уже отправлено (found по ветке "уже отправлено" и пути отмены, сбрасывающему 2 в 1). Соответствие атрибута сети `group_history_sent` состоянию inferred.

### 3.3 Гейты (`C230099x1`, `A1W.A02`)

Каждый гейт это `глобальный флаг OR пергрупповая экспозиция` (`C41861nA.A04(group, id)`):

| Хелпер | Глобальный | Id для группы | Использование |
|--------|------------|---------------|---------------|
| `A01` | **26451** | 30905 | точка входа `AFTER_JOIN` |
| `A02` | **15313** | 23245 | отправка истории при добавлении (`A1W.A0B`), также гейтит `onGroupParticipantsAdded` |
| `A03` | **29973** | 30906 | вызывающие не прослежены |

Точки входа (`C9SA`): `AFTER_JOIN`, `FROM_MENTION`, `FROM_CONTACT_MESSAGE`. `FROM_MENTION` и `FROM_CONTACT_MESSAGE` дополнительно привязаны к kill switch **35554** / **35555** и к гейту `A02`. Полярность комбинированной проверки не выяснена (поток декомпиляции искажён вокруг `A1W.A09`).

---

## 4. Поток присоединения (сторона отправителя)

### 4.1 Точки входа UI (found)

| Вход | Класс | Что происходит |
|------|-------|----------------|
| Выбор участников для добавления | `VoipParticipantPickerFragment` + `GroupHistoryAddMembersSettingFooterView` | футер "Send message history to approved members" с переключателем и ссылкой "recent messages"; нажатие открывает диалог количества; состояние переключателя запоминается (`is_group_history_toggled`) |
| Экран одобрения участия | `GroupMembershipApprovalRequestsFragment` (`C24002AWf`) | тот же диалог количества перед одобрением |
| Лист после присоединения | `GroupHistoryAfterJoinSendBottomSheetFragment` | "Send message history to %1$s?" (одно или два имени) |
| Упоминание / отправленный контакт | точки входа `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | только имена; поведение не прослежено |

Текст подтверждения при первом использовании: "Group history messages are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them." (счётчик `group_history_confirmation_dialog_confirmed_times`).

### 4.2 Варианты количества (`C229129vL.A00(n)`, found)

`n` = счёт из `A0G.A00` (сообщения, укладывающиеся в лимиты из 5.1).

| n | Варианты |
|---|----------|
| 0 | нет ("No message history to view") |
| 1..25 | один вариант, `n`, помеченный "all" ("Last %d (all)") |
| > 25 | `k = min(4, ceil(n/25))`, `step = max(25, n/k)`; варианты `step`, `2*step`, ... до `k-1` шагов, затем `n` (помечается "all" при условии на размер на последнем шаге; точное сравнение не выяснено) |

Затем список разворачивается `C0CG.A0Z` (inferred: сначала наибольший); первая запись выбрана заранее. Оговорка о закреплённых сообщениях ("All available pinned messages will be included") показывается всегда.

### 4.3 IQ добавления и связка событий (found)

```xml
<iq xmlns="w:g2" type="set" to="GROUP@g.us" id="…">
  <add>                                       <!-- optional transparency_acknowledged="true" -->
    <participant jid="USER"><privacy>bytes</privacy></participant>   <!-- privacy child optional -->
  </add>
</iq>
```

Found при чтении построителя (`C11410Yt`): в запрос добавления не вносится никакой атрибут, специфичный для истории; решение об истории чисто локальное. События, освобождающие отложенное задание (`C197318aR`, таймаут 32 с для самого IQ):

| Событие | Обработчик | Эффект |
|---------|------------|--------|
| История запрошена | `CCP(params, group, requestId, receivers, nonReceivers, approvedByMe)` | сохранить `PendingSendGroupHistoryJob`; запомнить выбранное количество в `A08[requestId]`; установить `group_history_usage_activated` |
| Ответ на IQ добавления | `BfO(C222169gu)` | сохранить карту результатов по запросу |
| Участники добавлены (уведомление) | `BvD` (только при гейте `A02`) | добавить в наборы "добавлено мной" / "добавлено другими" |
| Ответ на одобрение участия | `C05(group, user, requestId, approved)` | сохранить одобренного пользователя (или пустое) |

### 4.4 Отложенное задание (`PendingSendGroupHistoryJob`, found)

Поля: `permanentGroupRawJid`, `requestId`, `messageCount`, `lastMessageSortId`, `groupHistoryReceiverRawJids`, `groupHistoryNonReceiverRawJids`, `approvedByMeRawJids`, `jobScheduledServerTimeInMillis`, `expirationTimeInMins`. Постоянный id задания `group-pending-send-group-history`, условие `SendGroupHistoryJobRequirement` (все JID получателей должны разбираться, иначе `invalid group history receiver jid`).

| Шаг | Детали |
|-----|--------|
| Условие выполнено, когда | задание истекло; или пришёл результат добавления / одобрения для `requestId`; или получатель в наборе "добавлено другими" и не одобрен мной; или получатель уже участник (`A0r`) |
| Истечение | `scheduled + flag 19034` минут; истёкшее задание: отмена, сброс состояния участника 2 в 1 |
| Запуск | разделить получателей на уже присоединившихся и оставшихся; оставшиеся попадают в **новое** отложенное задание (тот же request id, не-получатели отфильтрованы); присоединившиеся получатели получают пакет (`C9mW.A00`) |
| Боты-получатели | получатель TEE-бот (`AbstractC197238aI.A00`) обрабатывается отдельным штампом передачи истории (`A04`, 5.5) |
| Защита от дубликатов | карта `C197318aR.A09` (группа, пользователь) во время отправки; записи старше `19034` минут (мин. 5) удаляются |

---

## 5. Выбор, лимиты и упаковка

### 5.1 Выбор строк (`A0G`, `AbstractC494421h.A00`, found)

```sql
SELECT … FROM available_message_view [ / with association join when 24033 ]
WHERE timestamp >= (scheduledTimeMs - flag18406 s)
  AND chat_row_id = ? AND sort_id <= ?                 -- anchor = last message at scheduling time
  AND view_mode IS NOT 1 AND view_mode IS NOT 3
  AND message_type IN (shareable types)                -- from the type registry, BUv()
  AND (association_type IS NULL OR association_type IN (supported))   -- only when 24033
  AND (from_me = 0 OR status NOT IN (-1,0,1,2,7,20,21,22))
  AND (expire_timestamp IS NULL OR expire_timestamp >= now OR keep_in_chat = 1)
ORDER BY sort_id DESC LIMIT n
```

| Параметр | Источник |
|----------|----------|
| `n` | запрос подсчёта использует флаг **18405** как LIMIT; запрос отправки использует выбранное пользователем количество |
| окно | флаг **18406** (секунды) до времени планирования; текст UI обещает "up to 100" сообщений |
| сообщения, которыми можно делиться | реестр по типам FMessage (`C222979iT.A00`, `C1ZP.BUv()` true), с переопределением для отдельного сообщения (`C30039D5b`); здесь не перечислены |
| собственные сообщения | только те, что покинули устройство (`status` не в наборе ожидающих / неудачных `AbstractC494421h.A00`) |
| исчезающие | истёкшие и не сохранённые сообщения пропускаются |

Если известен sort id после присоединения (`C14650f0.A05`), подсчёт привязывается к нему ("post-join query"); иначе к новейшему сообщению ("pre-join query").

### 5.2 Списки в пакете (found, `C9mW.A00`)

| Список | Содержимое | Лимит |
|--------|------------|-------|
| `messages` | выбранные строки (только те, которыми можно делиться) | `n` |
| `uncountedAssociatedMessageLists` | дочерние элементы, прикреплённые к выбранному родителю (элементы альбома, опросы, ...), сгруппированы по `(parent key, association type)`; только при **24033** | не входят в `messageCount` |
| `commentMessages` | комментарии к выбранным сообщениям (`C14780fG.A02(list, flag 6050, …)`) | флаг **6050** (inferred как предел) |
| `outOfWindowPinnedMessages` | закреплённые сообщения старше самого раннего выбранного; только не-медиа; фильтруются по набору допустимых | все доступные (строка-оговорка); предел получателя флаг **19811** (inferred) |

Типы ассоциации (`C13O`, 21 значение): `FUTURE` 0 (также запасное), `MEDIA_ALBUM` 1, `BOT_PLUGIN` 2, `EVENT_COVER_IMAGE` 3, `HD_VIDEO_DUAL_UPLOAD` 5, `STATUS_EXTERNAL_RESHARE` 6, `MEDIA_POLL` 7, `POLL_ADD_OPTION` 20, `STREAMED_HD_VIDEO_DUAL_UPLOAD` 22 и далее другие виды статусов / стикеров / dual-upload.

### 5.3 Упаковка (found)

1. Proto `GroupHistory` (6.1) сериализуется в файл с расширением `proto` (`File … A0Z(C15530gU.A0F, "proto")`); шаг сжатия не найден.
2. В чате группы создаётся новый FMessage типа 117 с файлом как медиа (`mimetype application/protobuf`) и передаётся в обычный конвейер отправки медиасообщений (загрузка и шифрование, раздел 7).
3. Локальные поля FMessage: количество сообщений, самая ранняя метка времени в окне (секунды), самая ранняя метка в целом (минимум с закреплёнными сообщениями), получатели, не-получатели, размеры упакованных списков сообщений, размер файла, время сборки (телеметрия).
4. Если включён **24741** и у сообщения нет secret, для него генерируется новый message secret, затем вычисляются reporting-токены для каждого исходного сообщения (раздел 9).

### 5.4 Уведомление после отправки (found, `ANQ.C0M`)

Когда пакет достигает статуса **1** (или **24**, если включён флаг **28787**) и уведомление ещё не отправлено (`A00 != 1`), устройство создаёт уведомление типа 118 в той же группе с количествами, метками времени и получателями пакета и отправляет его (`C33166Ecf.A06`). Его получает каждый участник группы; получатели, названные в `historyReceivers`, дополнительно помечают его (`AbstractC30028D4q.A1B`).

### 5.5 Передача истории TEE-боту (found, кратко)

Для бота-получателя `C9mW.A01` ставит на выбранные сообщения, несущие message secret, доказательство (`AbstractC33322EfC.A02(sender, botJid, "TEE History Share", stanzaId, secret)`) и отправляет уведомление, чей `botHistoryShareSyncMetadata` перечисляет `(stanzaId, messageSecretProof)`. Контекст ботов см. в отчёте Meta AI: [WA_META_AI.md](./WA_META_AI.md). Путь бота не загружает пакет.

---

## 6. Формат в сети

### 6.1 Внутренний файл: `GroupHistory` (`DSN`)

| Поле | Номер | Тип | Содержимое |
|------|-------|-----|------------|
| `messages` | **1** | repeated `WebMessageInfo` (`C30626DTu`) | учитываемые сообщения |
| `uncountedAssociatedMessageLists` | **2** | repeated `UncountedAssociatedMessageList` (`C30578DRy`) | `messages` **1** (repeated WebMessageInfo), `parentMessage` **2** (`MessageKey`, `BD5`), `associationType` **3** (enum `C13O`) |
| `commentMessages` | **3** | repeated `WebMessageInfo` | комментарии |
| `outOfWindowPinnedMessages` | **4** | repeated `WebMessageInfo` | закреплённые |

Получатель разбирает те же байты второй раз как `GroupHistoryWithMessageBytes` (`C30576DRw`: те же четыре номера полей; записи `C30543DQp` с `key` **1** (`MessageKey`) и `message` **2** (bytes); списки ассоциаций `DPH` читают только `messages` **1**). Этот вариант хранит исходные сериализованные байты каждого сообщения (используется для проверки reporting-токенов и работы с secret, inferred).

### 6.2 Внешнее сообщение: `Message.messageHistoryBundle` (`DT6`, поле **70**)

| Поле | Номер | Тип | Значение / использование |
|------|-------|-----|--------------------------|
| `mimetype` | **1** | string | должен равняться `application/protobuf` |
| `fileSha256` | **2** | bytes | 32 байта, хеш открытого текста |
| `mediaKey` | **3** | bytes | ключ медиа |
| `fileEncSha256` | **4** | bytes | 32 байта, хеш шифртекста |
| `directPath` | **5** | string | путь загрузки; пустое значение логируется, не фатально при разборе |
| `mediaKeyTimestamp` | **6** | int64 | секунды |
| `contextInfo` | **7** | `ContextInfo` | стандартный |
| `messageHistoryMetadata` | **8** | `MessageHistoryMetadata` (`C30583DSd`) | ниже |

`MessageHistoryMetadata`:

| Поле | Номер | Тип | Правило при получении |
|------|-------|-----|-----------------------|
| `historyReceivers` | **1** | repeated string | хотя бы один; текущий пользователь должен быть в списке |
| `oldestMessageTimestampInWindow` | **2** | int64 | присутствует и > 0 |
| `messageCount` | **3** | int64 | присутствует и > 0 |
| `nonHistoryReceivers` | **4** | repeated string | необязательно |
| `oldestMessageTimestampInBundle` | **5** | int64 | необязательно (включает закреплённые) |

### 6.3 Уведомление: `Message.messageHistoryNotice` (`DRY`, поле **102**)

`contextInfo` **1**, `messageHistoryMetadata` **2** (тот же тип, обязателен с правилами для получателей, метки времени и количества), `botHistoryShareSyncMetadata` **3** (`C25765B9z`: `botJid` **1**, `historyShareMessages` **3** repeated `BA2` = `stanzaId` **1**, `messageSecretProof` **2**). В lite-раскладке у `C25765B9z` нет поля **2**; отсечка существует только как локальное состояние (`C213519Ap.A03`).

### 6.4 Уровень stanza (found)

| Пункт | Пакет (117) | Уведомление (118) |
|-------|-------------|-------------------|
| stanza `type` | `media` | не специфичен для медиа |
| `<enc>` media type | `group_history` (`C30106D7q`; в разрешённом наборе enc media-type `C9E2` / `C33474Ehg`) | нет |
| `<meta appdata="…">` | **не задан** (`C213539Ar` не реализует `FZF`) | `group_history` (`C213519Ap.AVN`; пишет `F6K`) |
| проверка получателя | `A0O == "media"` и `A0J == "group_history"`, иначе ошибка 11 | `appdata == group_history`, иначе ошибка 76 |
| `<reporting>` | необязательно, раздел 9 | нет |

Обе проверки пропускаются, когда установлены флаги конверта `A0V` / `A0U` (значение не выяснено). Пакет, пришедший с media type `group_history`, но без соответствующего сообщения, и appdata уведомления на постороннем типе отклоняются `GroupHistoryBundleDeserializationValidator` / `GroupHistoryNoticeDeserializationValidator` (`F3b` / `F3c`).

### 6.5 Маркеры `WebMessageInfo` (`C30626DTu`, found)

| Поле | Номер | Тип | Использование |
|------|-------|-----|---------------|
| `isGroupHistoryMessage` | **57** | bool | сообщение импортировано из пакета |
| `reportingTokenInfo` | **62** | message | reporting-тег (см. отчёт Reporting) |
| `groupHistoryIndividualMessageInfo` | **74** | `C30549DQv` | `bundleMessageKey` **1** (`MessageKey`), `editedAfterReceivedAsHistory` **2** (bool) |
| `groupHistoryBundleInfo` | **75** | `C30548DQu` | `deprecatedMessageHistoryBundle` **1**, `processState` **2** (enum `EnumC32128E2a`) |

`processState`: `NOT_INJECTED` 0, `INJECTED` 1, `INJECTED_PARTIAL` 2, `INJECTION_FAILED` 3, `INJECTION_FAILED_NO_RETRY` 4, `DEDUPED` 5.

---

## 7. Шифрование и медиа

| Слой | Found |
|------|-------|
| Транспорт сообщения | обычная групповая рассылка: сообщение 117 шифруется как любое групповое (sender-key `skmsg` на группу плюс обычное распространение sender-key по устройствам). Основы здесь не повторяются; форма stanza `<enc>` описана в [WA_CALL_SIGNALING.md](./WA_CALL_SIGNALING.md), раздел про `<enc>`. Состояние sender-key по устройствам хранится в `group_participant_device` (`sent_sender_key`, `sent_add_on_sender_key`, `sent_sender_key_bucket`) |
| Строка медиа | `C15530gU.A0F`: тип загрузки `group-history`, тип файла `GROUP_HISTORY`, HKDF info `Group History`, id 117 |
| Ключ / шифр | случайный ключ медиа, HKDF-SHA256 с info `Group History`, AES-256-CBC, HMAC-SHA256, усечённый до 10 байт и добавленный в конец, `fileSha256` / `fileEncSha256` в proto: общая схема в [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md), раздел 6 (расширение до 80 байт на Android); применяется к этому типу через общий конвейер отправки (inferred, прочитана только строка типа) |
| URL загрузки | `https://<host>/mms/group-history/<hash>?…`; композиция `mms/<upload type>` found для таблицы (раздел 4 отчёта о медиа); буквальный путь для этого типа не перехвачен (inferred) |
| Скачивание | стандартное скачивание медиа с использованием `mediaKey`, `directPath`, хешей; текст ошибки `GroupHistoryBundleProcessor/download failed for … with reason …` |
| Повторное использование ключей | ключ медиа пакета не зависит от ключей сообщений внутри него |

Получатель всегда работает с `mediaKey` из proto; пакет, чьи хеши не имеют длины 32 байта, отклоняется (`bogus sha-256 hash received`, ошибка 14).

---

## 8. Получатель: проверка и импорт

### 8.1 Проверки при разборе (`C34677F2y.CM7`, found)

| Проверка | Ошибка |
|----------|--------|
| JID чата является группой (`A0l`) | 11 `chatJid is not a group` |
| конверт `media` + enc media type `group_history` | 11 |
| `mimetype == application/protobuf` | 11 |
| `fileSha256`, `mediaKey`, `fileEncSha256`, `mediaKeyTimestamp`, метаданные присутствуют | 11 |
| `historyReceivers` непуст, метка времени окна > 0, количество > 0 | 11 |
| текущий пользователь в `historyReceivers` (не для собственных сообщений) | 11 `current user is not in history receivers list` |
| гейт **15311** выключен | FMessage-заглушка `C35281aa` с кодом **82** ("Update to the latest version of WhatsApp to see it") |
| длины хешей 32 | 14 |

Уведомление (`C34678F2z`): групповой чат, appdata, метаданные с получателями / меткой времени / количеством; выключенный гейт **15722** даёт заглушку с кодом **10008**.

### 8.2 Обработка (`GroupHistoryBundleProcessor`, found, если не указано иначе)

1. Триггер: сообщение добавлено (`C0G`) и снова при состоянии медиа 3 (`C0M`). Кандидат это групповой чат (тип 1), не от меня, состояние 0 или 5, я в списке получателей, и моложе флага **25910** (единица не выяснена; иначе "Message history expired").
2. Дедупликация (флаг **30462**): если для той же сессии присоединения пакет уже обработан, новый помечается как дедуплицированный (`deduped_bundle_for_join_session`), UI: "%1$s also sent you message history, which you already got from someone else".
3. Скачивание медиа; сбой показывает "Couldn't download message history from %1$s".
4. Разбор файла дважды (`DSN`, `DRw`); сбой разбора: `protobuf_parse_failed`.
5. Поиск якоря: последнее сообщение о присоединении к группе ("failed to find latest group join message, adding messages before the first message in chat", если его нет); слишком старый якорь: `anchor_message_too_old`.
6. Проверка и вставка каждого сообщения (8.3); каждая вставленная строка связывается с пакетом (`group_history_bundle_association`: `bundle_message_key_id`, `message_row_id`, `message_sort_id`); отметка `isGroupHistoryMessage`.
7. Закреплённые вне окна: предел (флаг **19811**, inferred), применение общего состояния закрепления (`applySharedPin`).
8. Применение ожидающих штампов передачи истории боту (`BotHistoryShareHelper`), затем телеметрия (`group_history_receiver_user_journey`).

Импортированные строки размещаются перед якорем присоединения, поэтому они появляются выше строки "вас добавили" (inferred из логики якоря).

### 8.3 Проверка каждого сообщения (`C33241Eds`, `C34360Ew7`, `C34361Ew8`, `C33413Egg`, found)

| Причина пропуска | Причина |
|------------------|---------|
| `invalid_jid` | `key.remoteJid` отличается от чата пакета |
| `non_hex_id` | `key.id` не состоит только из hex |
| `timestamp_too_old` | `messageTimestamp` не новее допустимой нижней границы (поля лога `msgTs`, `allowedTs`, `diff`; граница выводится из локального состояния, формула не выяснена) |
| `parse_failed`, `pin_not_parsed` | proto записи не разобрался |
| `not_shareable` | тип сообщения не разрешён для импорта |
| `no_local_copy` | общее закрепление, сообщение которого было пропущено и не является локальным |
| `max_limit_reached` | достигнут предел |
| `timestamp_after_anchor` | сообщение новее якоря присоединения |
| `already_exists`, `duplicate`, `expired` | уже есть локально, дубликат в файле, исчезающее истекло и не сохранено |
| `orphan_parent_not_in_bundle`, `invalid_comment` | комментарий / дочерний элемент ассоциации без родителя в файле |
| `insert_exception`, `anchor_messages_failed`, `insert_messages_exception` | ошибки локальной БД |

Дополнительно: у сообщения должен быть сохранён `messageSecret` (логи `messageSecretLost`, `noMessageSecret`); локальная копия побеждает, если сообщение существует с другим содержимым (`keeping local …`).

Затрагиваемые таблицы (found): `group_history_bundle_association` (`bundle_message_key_id`, `message_row_id`, `message_sort_id`), `group_history_share_reporting_info` (`stanza_id`, `reporting_tag`, `send_timestamp`, `added_timestamp`, `reporting_token`, `reporting_token_version`, `is_send`, `validation_policy`), `group_participant_user.group_history_send_state`, `wa_group_admin_settings` (2.4).

---

## 9. Reporting-токены (кратко)

Секция stanza для пакета при включённом **24741** (`F6C`, `GhsReportingTokenMessageSendStanzaContributor`):

```xml
<reporting>
  <message id="ORIGINAL_STANZA_ID"><reporting_token v="N">16 bytes</reporting_token></message>
  …
</reporting>
```

Вывод и хранение токенов описаны в [WA_REPORTING.md](./WA_REPORTING.md) (раздел 6.2); часть вывода ключа выполняется в нативном коде, поэтому точные байты невозможно воспроизвести только по Java. При получении, когда включены **5718** и **24742**, отсутствие токена для импортированного сообщения порождает телеметрию `GROUP_HISTORY_MESSAGE_MISSING_FROM_PUBLIC_STANZA` (и, с **13063**, внутреннюю диагностическую строку); на этом пути сообщение всё равно вставляется (inferred из потока управления). Требует ли сервер токены: unknown.

---

## 10. HistorySync компаньон-устройств (связано, но не история группы)

Основы сопряжения и app-state описаны в [WA_LINKED_DEVICE_PAIRING.md](./WA_LINKED_DEVICE_PAIRING.md) и [WA_APPSTATE_SYNC.md](./WA_APPSTATE_SYNC.md). Только то, что относится к данным групп:

### 10.1 `HistorySyncConfig` (`C44601rs`, объявляет компаньон; номера полей из lite-раскладки)

| Поле | # | Значение компаньона (found) |
|------|---|------------------------------|
| `fullSyncDaysLimit`, `fullSyncSizeMbLimit` | 1, 2 | флаги **15284**, **15283** |
| `storageQuotaMb`, `initialSyncMaxMessagesPerChat` | 3, 20 | не задано в прослеженной ветке |
| `recentSyncDaysLimit` | 5 | 0 |
| `supportMessageAssociation`, `supportHostedGroupMsg`, `supportAddOnHistorySyncMigration` | 14, 11, 13 | true |
| `supportGroupHistory` | 15 | флаг **20658** |
| `onDemandReady` / `completeOnDemandReady` | 16 / 18 | `!` флаг **18953** / false |
| `thumbnailSyncDaysLimit` | 19 | флаг **21217** |
| `supportHatchHistory` / список каналов ботов | 22 / 23 | флаг **26445** / ветвление по **26614** |
| журнал звонков, история ботов и CAG, `supportNewsletter`, `supportInlineContacts`, ... | 4, 6-8, 12, 24-27 | true (остальные false) |

Остальные поля (`supportBizHostedMsg` 9, `supportRecentSyncChunkMessageCountTuning` 10, `supportGuestChat` 17, `supportManusHistory` 21, `supportUniversalReachChat` 26, `supportOmittedConversationIndex` 27) здесь не детализируются.

### 10.2 Типы синхронизации и сообщения

| Сообщение | Поле | Содержимое |
|-----------|------|------------|
| `HistorySync` (`C25838BCy`) | `syncType` **1**, `conversations` **2**, `statusV3Messages` **3**, `chunkOrder` **5**, `progress` **6**, `pushnames` **7**, `globalSettings` **8**, `threadIdUserSecret` **9**, `threadDsTimeframeOffset` **10**, `recentStickers` **11**, `pastParticipants` **12**, `callLogRecords` **13**, `aiWaitListState` **14**, `phoneNumberToLidMappings` **15**, `companionMetaNonce` **16**, `shareableChatIdentifierEncryptionKey` **17**, `accounts` **18**, `nctSalt` **19**, `inlineContacts` **20/21**, `omittedConversations` **23/24** | групповые беседы идут в `conversations`; `pastParticipants` (**12**) перечисляет бывших участников группы |
| `HistorySyncNotification` (`C25834BCt`) | `fileSha256` **1**, `fileLength` **2**, `mediaKey` **3**, `fileEncSha256` **4**, `directPath` **5**, `syncType` **6**, `chunkOrder` **7**, `originalMessageId` **8**, `progress` **9**, `oldestMsgInChunkTimestampSec` **10**, `initialHistBootstrapInlinePayload` **11**, `peerDataRequestSessionId` **12**, `fullHistorySyncOnDemandRequestMetadata` **13**, `encHandle` **14**, `messageAccessStatus` **15** | чанк, на который ссылается медиа; полезная нагрузка это `HistorySync` |

Типы синхронизации: `INITIAL_BOOTSTRAP` 0, `INITIAL_STATUS_V3` 1, `FULL` 2, `RECENT` 3, `PUSH_NAME` 4, `NON_BLOCKING_DATA` 5, `ON_DEMAND` 6, а в enum из 9 значений (`EnumC26456Bdr`) также `NO_HISTORY` 7 и `MESSAGE_ACCESS_STATUS` 8 (`EnumC26449Bdk` это вариант из 7 значений).

### 10.3 Peer-операции с данными по запросу (`EnumC26460Bdv`, found)

| Операция | Id | Поле запроса (`C25823BCh`) | Поле ответа (`C25828BCm`) |
|----------|----|----------------------------|---------------------------|
| `HISTORY_SYNC_ON_DEMAND` | 3 | `historySyncOnDemandRequest` **4** (`BCR`: `chatJid` **1**, `oldestMsgId` **2**, `oldestMsgFromMe` **3**, `onDemandMsgCount` **4**, `oldestMsgTimestampMs` **5**, `accountLid` **6**, `supportInlineResponse` **7**) | не определено; история приходит как `HistorySyncNotification` (inferred) |
| `FULL_HISTORY_SYNC_ON_DEMAND` | 6 | `fullHistorySyncOnDemandRequest` **6** (`BBB`: `requestMetadata` **1** `BBA`, `historySyncConfig` **2**, `fullHistorySyncOnDemandConfig` **3** `C156516k5`: `historyFromTimestamp` **1**, `historyDurationDays` **2**) | `fullHistorySyncOnDemandRequestResponse` **6** |
| `PLACEHOLDER_MESSAGE_RESEND` | 4 | **5** | **4** |
| `COMPANION_SYNCD_SNAPSHOT_FATAL_RECOVERY` | 8 | **7** | **8** |

Основное устройство хранит по одной строке на каждую синхронизацию в `msg_history_sync` (`device_id`, `sync_type`, `last_processed_msg_row_id`, `oldest_msg_row_id`, `sent_msgs_count`, `chunk_order`, `sent_bytes`, `last_chunk_timestamp`, `status`, `peer_msg_row_id`, `oldest_message_to_sync_row_id`, `session_id`, `size_limit_bytes`, `full_history_on_demand_request_id`, …). Серверные ограничения на размер чанка и количество сообщений не видны в прочитанном клиентском коде (unknown). Специальной операции по запросу для общей истории группы не существует.

### 10.4 История группы на компаньонах

| Пункт | Found |
|-------|-------|
| Capability | `supportGroupHistory` (флаг **20658**) в `companion-props`; хранится на основном устройстве как `support_group_history` (отчёт о сопряжении, раздел 6.2); потребитель не прослежен |
| Доставка пакета | пакет это обычное групповое сообщение, поэтому его получает каждое устройство получателя; строки для связанных устройств ("Open WhatsApp on your phone and visit this group to see it") указывают на заглушку там (inferred) |
| Сборка синхронизации на основном устройстве | `BuildHistorySyncParams` (`C33151EcQ`) несёт `supportGroupHistory`, `pullGroupHistoryUncountedChildren`, `maxCommentsToAdd`, `supportMessageAssociation`; потребители не прослежены |
| Системные сообщения | изменения режима передачи, history-enabled, режимов добавления участников / ссылок / одобрения воссоздаются для компаньонов классами `Group*HistorySync` |

---

## 11. Feature-флаги и лимиты

Id флагов выделены жирным; значения доставляются сервером, значения по умолчанию в коде не выяснены (текст UI говорит "up to 100" сообщений).

| Флаг | Тип | Что контролирует | Уровень |
|------|-----|------------------|---------|
| **35987** | bool | kill switch предпосылок отправителя | found |
| **15313** / 23245 | bool / group | гейт `A02`, отправка истории при добавлении | found |
| **26451** / 30905 | bool / group | гейт `A01`, точка входа `AFTER_JOIN` | found |
| **29973** / 30906 | bool / group | гейт `A03` | found (использование unknown) |
| **35554**, **35555** | bool | `FROM_MENTION`, `FROM_CONTACT_MESSAGE` | полярность inferred |
| **18405** | int | LIMIT запроса подсчёта (предел размера предложения) | found |
| **18406** | int, s | окно просмотра назад от времени планирования | found |
| **19034** | int, min | истечение отложенного задания, очистка дедупликации (мин. 5) | found |
| **30333** | long | максимальное время с момента присоединения для получателя | found (единица не выяснена) |
| **24033** | bool | списки ассоциаций и фильтр ассоциаций | found |
| **6050** | int | предел сбора комментариев | inferred |
| **24741** | bool | строить reporting-токены при отправке | found |
| **28787** | bool | триггер уведомления по статусу 24 вместо 1 | found |
| **20658** | bool | компаньон объявляет `supportGroupHistory` | found |
| **15311** | bool | получение: пакет принимается (выкл: заглушка 82) | found |
| **15722** | bool | получение: уведомление принимается (выкл: заглушка 10008) | found |
| **30462** | bool | получение: дедупликация по сессии присоединения | found |
| **25910** | long | получение: окно свежести пакета | found (единица не выяснена) |
| **19811** | int | получение: предел закреплённых вне окна | inferred |
| **24034** / **25037** | bool / int | получение: обработка дочерних элементов ассоциации и её int-параметр | inferred |
| **26039** | bool | гейт вставки (три места) | found (использование unknown) |
| **5718** + **24742** | bool | получение: проверка reporting-токенов | found |
| **13063** | bool | внутренняя диагностическая строка при отсутствии токена | found |

---

## 12. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| Нет опции "send history" | отправитель не допустим (3.1), группа не согласована по LID / PN или нет сообщений, которыми можно делиться | администратор включает `all_member_share`, режим добавления участников `all_member_add`, без одобрения; или отправлять как администратор |
| Получатель видит "Update to the latest version" | гейт 15311 / 15722 выключен или неизвестный тип | на клиенте ничего |
| Пакет отклонён, ошибка 11 | неверный MIME, тип конверта, media type, отсутствует поле, меня нет в `historyReceivers` | собирать по разделу 6 |
| Пакет отклонён, ошибка 14 | хеш не 32 байта | исправить хеши |
| Уведомление отклонено, ошибка 11 / 76 | appdata не `group_history` (разбор, 11); appdata уведомления на другом типе (валидатор, 76) | ставить `appdata=group_history` только на тип 118 |
| После импорта сообщения отсутствуют | причины пропуска из 8.3 (`timestamp_too_old`, `not_shareable`, `invalid_jid`) | ключи должны быть hex-id той же группы |
| "Couldn't download message history" | сбой скачивания медиа (истёкший `directPath`, несовпадение ключа) | повторить; отправить заново |
| Задание не запускается | событие добавления или одобрения не замечено, получатели так и не стали участниками, задание истекло (19034) | добавить заново и отправить повторно |

---

## 13. Ключевые различия

| Не путать | С |
|-----------|---|
| Пакет истории группы (тип 117, `application/protobuf`, `group-history`) | уведомление HistorySync компаньона (`HistorySyncNotification`, `md-msg-hist`) |
| Пакет (данные, без appdata) | уведомление (количества и получатели, `appdata=group_history`) |
| `member_share_group_history_mode` (кто может отправлять) | `group_history_toggle_mode` / `history_enabled` (значение не выяснено) |
| `historyReceivers` (получают данные) | `nonHistoryReceivers` (добавлены, но не получают) |
| `oldestMessageTimestampInWindow` (**2**) | `oldestMessageTimestampInBundle` (**5**, включает закреплённые вне окна) |
| количество `messages` (`messageCount`) | неучитываемые дочерние элементы ассоциации и комментарии |
| `supportGroupHistory` в `HistorySyncConfig` (capability устройства) | настройка администратора |

---

## 14. Baileys (`baron-baileys-v2` 1.5.17)

Только факты, прочитанные в `src/Utils/group-history.js`, `src/Socket/groups.js`, `src/Socket/messages-recv.js`, `src/Socket/aigroups.js`, `src/Utils/validate-connection.js`, `WAProto/index.js`. Ничего не тестировалось на сервере; сбои не утверждаются.

| Тема | Baileys | Android |
|------|---------|---------|
| Proto | `GroupHistory`, `GroupHistoryWithMessageBytes`, `GroupHistoryBundleInfo`, `GroupHistoryIndividualMessageInfo`, `Message.messageHistoryBundle`, `messageHistoryNotice`, `HistorySyncConfig.supportGroupHistory` присутствуют в `WAProto` | 6 |
| Декодер | `decodeGroupHistory` пробует `zlib.inflateSync`, при неудаче берёт сырые байты; необязательный режим `GroupHistoryWithMessageBytes`; `processGroupHistory` нормализует четыре списка | сжатие на Android не найдено; читается сырой protobuf |
| Получение пакета | нет кода, обрабатывающего `messageHistoryBundle` (скачивание медиа, проверка, вставка) | раздел 8 |
| Отправка пакета | нет | раздел 5 |
| Capability компаньона | `supportGroupHistory: true` в объявляемом `HistorySyncConfig` | флаг 20658 |
| Настройка группы | `member_share_group_history_mode` читается из метаданных группы; `groupSetProperty(jid, property, value)` через MEX; mex-уведомление `NotificationGroupMemberShareGroupHistoryModePropertyUpdate` порождает `groups.update { memberShareHistoryMode }` | 2.4 |
| `aiGroupCreate` | принимает `memberShareGroupHistoryMode` (по умолчанию `all_member_share`), но в прочитанном коде не помещает его в stanza создания | неприменимо |
| Атрибуты участников | `group_history_sent`, `join_time` не разбираются | 2.2 |
| Адресация | `addressing_mode` читается из узла группы, при отправке по умолчанию `lid` | 2.2 |

Вывод, ограниченный прочитанным: клиент Baileys, объявляющий `supportGroupHistory`, не может импортировать полученный пакет, потому что в исходниках нет потребителя. Отправитель должен следовать разделам 5-7 (отправка после добавления, тип `media` с enc media type `group_history`, media type `group-history` с HKDF info `Group History`, уведомление с appdata); принимает ли сервер пакет без reporting-токенов `<reporting>`, unknown.

---

## 15. Полный поток

```
[Admin]  switch "Send message history" ─► MEX SetGroupProperty member_share_group_history_mode=ALL_MEMBER_SHARE|ADMIN_SHARE
     │
     ▼
[WA Server]  w:gp2 notification member_share_group_history_mode ─► all members: store mode, system message

[Sender]  add members (picker / approval screen / post-join sheet)
     │   A1W.A09: gate 35987, group type, sender (admin or all_member_share + all_member_add + no approval),
     │            receiver (join age, send_state), shareable messages
     │   A0G.A00 count ─► amount options (<=25 one option, else up to 4)
     ▼
iq set w:g2 <add><participant jid/></add>          (no history attribute)
     │
     ▼
[WA Server]  result ─► BfO / C05 / BvD events ─► PendingSendGroupHistoryJob requirement met
     │
     ▼
[Sender]  A0M: split joined / remaining (remaining re-queued) ─► C9mW.A00
     │   rows: timestamp >= scheduled - 18406 s, sort_id <= anchor, LIMIT n
     │   + association lists (24033) + comments (6050) + out-of-window pins
     │   GroupHistory proto ─► file ─► FMessage 117, mimetype application/protobuf
     ▼
upload  /mms/group-history  (HKDF info "Group History", AES-CBC + HMAC-10)       [WA_MEDIA_UPLOAD]
     │
     ▼
group message  type=media, enc mediatype=group_history, Message.messageHistoryBundle(70)
     │          metadata: receivers, nonReceivers, oldest ts (window / bundle), count
     │          optional <reporting><message id><reporting_token v/></message></reporting> (24741)
     ▼
[Receivers' devices]  C34677F2y checks (group, media, MIME, hashes, me in historyReceivers, gate 15311)
     │   download + decrypt ─► parse DSN / DRw ─► dedupe (30462) ─► anchor = join message
     │   validate each WebMessageInfo (jid, hex id, timestamp, type) ─► insert before anchor
     │   group_history_bundle_association, isGroupHistoryMessage=57
     ▼
[Sender]  bundle status 1 (24 with 28787) ─► notice type 118, appdata group_history, same metadata
     │
     ▼
[All members]  system row "<name> sent message history that starts on <date>"
```

---

## 16. Неизвестное

| Пункт | Статус |
|-------|--------|
| Серверные правила приёма, хранение, ограничения размера, требование reporting-токена | на стороне сервера, не наблюдалось |
| Значения по умолчанию 18405, 18406, 19034, 25910, 30333 | доставляются сервером, значения по умолчанию не выяснены |
| Точная нижняя граница `timestamp_too_old` и единица 25910 / 30333 | не выяснено |
| Полярность `A1W.A02` по точкам входа; использование гейта `A03` и флага 26039 | искажённая декомпиляция / не прослежено |
| Значение столбца `group_history_toggle_mode` и дочернего элемента `<group_history/>` | имена найдены, семантика только inferred |
| Список типов сообщений, которыми можно делиться (реестр `BUv()`) | не перечислен |
| Отображение пакета на компаньоне; потребитель `support_group_history` на основном устройстве | не прослежено |
| Нативная часть вывода ключа reporting-токена | нативный код, не читался |
| Трафик | ничего не перехвачено; все потоки из кода |
