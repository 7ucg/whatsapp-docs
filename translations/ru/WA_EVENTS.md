<!-- src-sha1: c9f42e3645bee848584358bb7a4660a293218e2e -->
# WhatsApp Events — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-11-01
**Область:** событие в стиле календаря (`eventMessage`, `eventInviteMessage`, `eventCoverImage`), зашифрованный RSVP (`encEventResponseMessage` / `EventResponseMessage`), подсистема приложения "Events v2" (`com.whatsapp.eventsv2.*`: локальная БД, синхронизация через GraphQL, push-уведомления через MEX, конвейер обложки, ссылка-приглашение/QR), жизненный цикл (создание/редактирование/отмена/удаление/выход), статусы RSVP, правила видимости гостей/локации, контекст группы vs 1:1 vs сообщества, ограничение на companion-устройствах, каталог GraphQL-операций, напоминания

---

## 1. Что это

"Event" (событие) — объект в стиле календаря (название, описание, временное окно, локация, опциональная ссылка на видео/голосовой звонок), который можно опубликовать в чат 1:1, в группу или расшарить отдельной ссылкой/QR-кодом, при этом гости могут ответить RSVP (Going / Maybe / Not going). Функция работает сразу по двум сетевым каналам: обычное E2E-зашифрованное сообщение в чате (`Message.eventMessage` / `Message.eventInviteMessage`), которое отображает карточку приглашения в переписке, и параллельная плоскость управления GraphQL + MEX-push (`com.whatsapp.eventsv2.*`, пакет новый в 2.26.41.6), которая держит локальную базу событий синхронизированной независимо от истории чата. Криптография RSVP (HKDF use case "Event Response", AES-GCM) общая с реакциями/опросами/комментариями и документирована в `WA_MESSAGE_SECRETS.md`; этот отчёт покрывает только модель событий и слой жизненного цикла.

| Сущность | Поле `Message` | Тип (обф.) | Роль |
|--------|-----------------|-------------|------|
| `eventMessage` | **75** | `EventMessage` | базовое событие, публикуется в чат |
| `encEventResponseMessage` | **76** | `EncEventResponseMessage` (`DRN`) | зашифрованный follow-up RSVP |
| `eventCoverImage` | **85** | `FutureProofMessage` | универсальная обёртка, несёт обложку как вложенный `imageMessage` |
| `eventInviteMessage` | **122** | `EventInviteMessage` (`DTQ`) | карточка-приглашение "Events v2", надмножество `eventMessage` |
| `eventResponses` (repeated) | **61**, на хосте, эквивалентном `WebMessageInfo` (`C30626DTu`) | `EventResponse` | свод RSVP по каждому гостю, переносится в history sync |
| `eventAdditionalMetadata` | **64**, тот же хост | `EventAdditionalMetadata` | единственный bool `isStale` |

Все поля proto и поля плейнтекста RSVP ниже были прочитаны напрямую из классов 2.26.41.6 (`DRP`, `DRN`, `DU9`, `E2D`, `C9T8` — **found**) и перекрёстно сверены с корневым контейнером `Message` в `Tools/proto-extractor/research/2.26.41.6/whatsapp-deobfuscated.proto`. Уровни: **found** = прочитано в коде/строках, **inferred** = выведено, **unknown** = не разрешено.

---

## 2. `EventMessage` (поле 75) — базовое событие

Не изменилось с эпохи 2.26.35.2; в 2.26.41.6 всё те же 12 полей.

| Поле | # | Тип | Примечания |
|-------|---|------|-------|
| `contextInfo` | 1 | `ContextInfo` | стандартный носитель цитирования/упоминаний |
| `isCanceled` | 2 | bool | устанавливается действием отмены |
| `name` | 3 | string | название события |
| `description` | 4 | string | |
| `location` | 5 | `Message.LocationMessage` | статический пин локации (lat/long/имя/адрес), *не* live |
| `joinLink` | 6 | string | обычный URL присоединения (легаси-поле; заменено ссылкой-приглашением Events v2 для новых событий) |
| `startTime` | 7 | int64 | unix-секунды |
| `endTime` | 8 | int64 | unix-секунды |
| `extraGuestsAllowed` | 9 | bool | переключатель "+1" |
| `isScheduleCall` | 10 | bool | та же модель, используемая для точки входа "Schedule a call" |
| `hasReminder` | 11 | bool | |
| `reminderOffsetSec` | 12 | int64 | секунды до `startTime` |

`reminderOffsetSec` заполняется из фиксированного пикера (`EventReminderBottomSheet`, строки **found**): "Never", "Time of event", "15 minutes before", "30 minutes before", "1 hour before", "1 day before". Маппинг 0/900/1800/3600/86400 секунд — **inferred** (не прочитан как литералы; таблица соответствия опции пикера и секунд находится в классе — `BXa`/`C27637BzN` — чей пул констант jadx не разрешил).

---

## 3. `EventInviteMessage` (поле 122, обф. `DTQ`) — приглашение "Events v2"

Выросло с 9 до 13 полей по релизам; 2.26.41.6 несёт все 13. **Поправка к исходному материалу**: закоммиченный `Messages/eventInviteMessage/info.md` (зафиксирован на 2.26.35.2) останавливается на поле 9 (`callLink`) и не содержит поля 10–13, которые подтверждены присутствующими в этой сборке прямым чтением `DTQ`:

| Поле | # | Тип | Добавлено | Примечания |
|-------|---|------|-------|-------|
| `contextInfo` | 1 | `ContextInfo` | базовое | |
| `eventId` | 2 | string | базовое | id события, назначаемый сервером |
| `eventTitle` | 3 | string | базовое | |
| `jpegThumbnail` | 4 | bytes | базовое | встроенная миниатюра обложки |
| `startTime` | 5 | int64 | базовое | |
| `caption` | 6 | string | базовое | |
| `isCanceled` | 7 | bool | базовое | |
| `endTime` | 8 | int64 | базовое | |
| `callLink` | 9 | string | базовое | формата `https://call.whatsapp.com/video/...` |
| `coverImageHandle` | 10 | string | 2.26.38.10 | ссылка на media-handle, альтернатива встроенному `jpegThumbnail` |
| `locationName` | 11 | string | 2.26.38.10 | человекочитаемая метка локации |
| `lastUpdatedTsUsec` | 12 | int64 | 2.26.38.10 | микросекунды; увеличивается при каждом `UpdateEvent` |
| `status` | 13 | int32 (open enum) | **2.26.41.6** | статус на уровне события; класс enum статически не восстановлен |

`status` (13) — единственное новое wire-поле в этом релизе. Имена членов его enum на уровне proto — **unknown**: jadx не смог восстановить класс-носитель этого open-enum int32. Однако GraphQL-ориентированный словарь статусов для связанных переменных `rsvp_status`/`UpdateEvent.status` был восстановлен независимо (§6) и является вероятным, но неподтверждённым кандидатом на то же значение; не доказано, что эти два разделяют одно wire-представление.

---

## 4. `eventCoverImage` (поле 85) — обёртка обложки

`FutureProofMessage { optional Message message = 1; }` — та же универсальная обёртка, что используется для `lottieStickerMessage`, `statusMentionMessage` и т.д. Нет специфичных для события полей; вложенный `message` несёт обычный `imageMessage`. Код потребителя (`EventCoverImageLoader`, `EventCoverImageThumbnailCreator`, `EventCoverImageUrlResolver`) обрабатывает это как обычное вложение-изображение — дополнительной валидации сверх общей распаковки обёртки не найдено.

Events v2 также поддерживает **предустановленные** обложки (`EventPresetCoverImagesRepository`, каталог, получаемый через GraphQL, переменные `cover_image_blob`/`is_preset_image` у `CreateEvent`/`UpdateEvent`) как альтернативу фото, загруженному пользователем.

---

## 5. RSVP: `encEventResponseMessage` и `EventResponseMessage`

### 5.1 Wire-формат (found, `DRN`/`DRP`/`E2D` прочитаны напрямую)

| Носитель | Поле | # | Тип |
|---------|-------|---|------|
| `EncEventResponseMessage` (`DRN`, поле 76) | `eventCreationMessageKey` | 1 | `MessageKey` (`BD5`) |
| | `encPayload` | 2 | bytes |
| | `encIv` | 3 | bytes |
| `EventResponseMessage` (`DRP`, плейнтекст AES-GCM) | `response` | 1 | enum `E2D` |
| | `timestampMs` | 2 | int64 |
| | `extraGuestCount` | 3 | int32 |

Значения `E2D` (found, `E2D.java`): **0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE**.

Это напрямую подтверждает `WA_MESSAGE_SECRETS.md` §"encEventResponseMessage **76**" и разрешает конфликт в автоматически извлечённом дампе proto (`Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`, который — из-за баги восстановления имён полей, отмеченной в его же тексте, "missing name slot at field #3" — указывает `EventResponseMessage` как `timestampMs=1, extraGuestCount=2, field3=3`). Прямое чтение класса (строка порядка полей `BUILD_MESSAGE_INFO` у `DRP` и константы `RESPONSE_FIELD_NUMBER=1`/`TIMESTAMP_MS_FIELD_NUMBER=2`/`EXTRA_GUEST_COUNT_FIELD_NUMBER=3`) закрывает вопрос: **`response` — это поле 1, а не 3.**

### 5.2 Путь отправки (found, `DU9.ADr`)

`DU9` (обработчик use case ответа на событие, наследует `F2P`) строит `DRP` из прикладного enum `C9T8` (`UNKNOWN=0, GOING=1, NOT_GOING=2, MAYBE=3` — численно идентично `E2D`, что подтверждает прямое зеркалирование 1:1 через конвертер `EW0.A01`), плюс timestamp и int `extraGuestCount`, шифрует это HKDF use case `"Event Response"` через `MessageSecretCryptoHelper` (`C33285Eeb.A03`) и оборачивает шифротекст/IV/ключ исходного сообщения в `DRN`. `AAl()` ставит в исходящей станзе атрибут `<meta event_type="response">`. Детали криптографии (вывод HKDF, AES-GCM, AAD = `targetId‖0x00‖modifier`, повтор отправитель/LID) здесь **не повторяются** — см. `WA_MESSAGE_SECRETS.md` §2–9, 16.

### 5.3 Ещё три enum в форме RSVP-статуса (found) — подводный камень

Помимо wire-enum `E2D` и его зеркала `C9T8`, приложение определяет как минимум три *других* перечисления статуса RSVP с **разным порядком членов**, каждое используется в своём слое:

| Enum (обф.) | Члены (ordinal) | Используется для |
|---|---|---|
| `E2D` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | wire-плейнтекст `EventResponseMessage.response` |
| `C9T8` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | прикладное зеркало `E2D`, передаётся в `DU9.ADr` |
| `C9T6` | 0 GOING, 1 NOT_GOING, 2 MAYBE, 3 NO_RESPONSE | локальный порядок `dbValue` (`EventRsvpBottomSheet`, локальная БД), **без слота UNKNOWN**, вместо него `NO_RESPONSE` |
| `C9U0` | строки `serverValue`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `GOING`, `MAYBE`, `NOT_GOING`, `NO_RESPONSE` | переменная GraphQL `rsvp_status` (`UpdateEventRsvp`, `JoinEventViaLink`) |

Это разрешает часть пробела "RSVP enum unknown", отмеченного для поверхности GraphQL в `Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`: переменная **GraphQL** `rsvp_status` принимает буквальные строки `GOING` / `MAYBE` / `NOT_GOING` / `NO_RESPONSE` (found, `C9U0.serverValue`, потребитель `C207188s3.B2x()`, читающий ключ `"rsvp_status"`). Класс enum wire-proto `EventInviteMessage.status` (поле 13, §3) остаётся не восстановленным, и **не доказано**, что он разделяет этот словарь.

Пятый, отдельный набор целочисленных значений "status label" (found, `C2115191e.A00`, используется для чипа предпросмотра пересылки в чат) отображает `1 GOING, 2 GOING_WITH_GUEST, 3 NOT_GOING, 4 MAYBE, 5 NOT_RESPONDED, 6 CANCELED, default CREATOR` — набор отображаемых UI debug-меток, а не wire-значений.

---

## 6. GraphQL-поверхность Events v2 (схема `www`, найденные doc_id)

В поставленном `whatsapp-android-www_client_persist_ids.json` существует 16 persisted-операций; переменные восстановлены из точек вызова APK (документированы в `Querys/www/guides/events.md`, который этот отчёт перекрёстно сверил, а не вывел заново).

| Операция | doc_id | Операция | doc_id |
|----|--------|----|--------|
| `CreateEvent` | `27122934507384369` | `UpdateEvent` | `27442441785378771` |
| `DeleteEvent` | `24671535952543811` | `UpdateEventRsvp` | `27592470423757790` |
| `GetEvent` | `27529572846713636` | `ListEvents` | `27633532006268526` |
| `GetEventCoverImage` | `28048111841543330` | `AddEventInvitations` | `28162575909992756` |
| `GetEventLinkPreview` | `27639296169058396` | `RemoveEventInvitations` | `27696932319970038` |
| `GetOrCreateEventInviteLink` | `26392982740362906` | `RemoveSelfEventInvitation` | `27063717026648637` |
| `JoinEventViaLink` | `27669318929396727` | `RotateEventInviteLink` | `27134834146102810` |
| `ValidateCachedEventIDs` | `27508030125525954` | mex `LogEventInviteCreate` | `27409709725288255` |

Восстановленные ключевые переменные (found): `CreateEvent`/`UpdateEvent` принимают `chat_jid`, `description`, `max_additional_guests`, `is_group_based_event`, `is_shareable`, `cover_image_handle`/`cover_image_blob`/`is_preset_image`, `location_address`/`location_web_url`, `call_link_media_type`, `call_link_waiting_room_enabled`; `UpdateEvent` дополнительно принимает `clear_location`, `clear_location_coordinates`, `hide_invitee_list`, `link_id`, `status`. `UpdateEventRsvp`/`JoinEventViaLink` принимают `event_id`/`link_token`, `rsvp_status`, `extra_guest_count`. Транспорт — `inferred` (POST с persisted-`doc_id`, тот же паттерн, что и у других операций `www`); трафик не перехватывался.

### 6.1 Push-уведомления MEX (found, отдельно от GraphQL-pull выше)

`DefaultEventsNotificationRepository` разбирает две схемы push-payload **MEX** — `xwa2_notify_event_on_invite` и `xwa2_notify_event_on_update` (буквальные имена узлов в выбрасываемых исключениях, found) — несущие `start_ts_sec`, `cover_image.handle`/`cover_image.uri`, локацию и поля call-link, и вставляет их напрямую в локальную БД событий (`DefaultLocalEventsDataSource.upsertEvents`). Это означает, что событие может появиться в локальном списке Events на устройстве **без** того, чтобы устройство когда-либо получало плоскость сообщения чата (`eventMessage`/`eventInviteMessage`) для него — сервер активно пушит уведомления о приглашении/обновлении через MEX независимо от доставки чата. При первом приглашении локальный статус RSVP по умолчанию равен `NO_RESPONSE` (`C9T6.A05.dbValue`).

---

## 7. Локальное хранилище и мост к легаси

`EventsDatabaseDataSource` (локальная БД в стиле Room) — каноническое хранилище Events v2; `GraphqlEventsDataSource` заполняет её из операций §6; `FMessageEventsDataSource` соединяет **более старую** модель только на базе сообщений чата (`eventMessage`/`eventInviteMessage` как обычные строки `FMessage`, класс `C213509Ao` — он же класс, управляющий генерацией `messageSecret` для сообщений события согласно `WA_MESSAGE_SECRETS.md` §"prepare send") с тем же потоком `observeEventPreviews()`, который потребляет UI. На практике: событие, созданное более старым клиентом (или до появления Events v2), всё ещё рендерится из сообщения чата; событие, созданное в Events v2, хранится в БД и синхронизируется через GraphQL, а сообщение чата выступает как расшариваемая карточка-приглашение.

---

## 8. Действия жизненного цикла

| Действие | Кто | Механизм | Эффект |
|--------|-----|-----------|--------|
| **Создание** | любой участник чата (группа) / любая из сторон (1:1) / кто угодно в контексте, допускающем QR | `CreateEvent` (GraphQL), затем в чат публикуется `eventInviteMessage` | сервер назначает `eventId`; `EventComposerFragment` собирает название/описание/время/локацию/обложку/напоминание/переключатель гостей/тип медиа звонка |
| **Обновление** | хост | `UpdateEvent` (GraphQL); `lastUpdatedTsUsec` (поле 12) увеличивается | текст уведомления зависит от того, какие поля изменились: "Event date has been updated.", "...date and location...", "...date and time...", "...date, time and location...", "...location has been updated.", "...time has been updated.", "...time and location..." (все найдены, разные строки по diff) |
| **Отмена** | хост | устанавливает `isCanceled`/`status`; диалог подтверждения "Cancel event" / "Are you sure you want to cancel this event?" | "Event canceled"; текст push "%1$s canceled %2$s"; "Guests can no longer respond to the event." / "You can no longer respond to the event." — RSVP закрывается |
| **Удаление** | хост | `DeleteEvent` (GraphQL) | удаляется из локального списка событий хоста; сообщения-приглашения в чате остаются видимыми; "People on the guest list will see the event has been deleted." |
| **Выход** | гость | локальное действие, без подразумеваемого изменения RSVP | гость перестаёт получать дальнейшие обновления события: "You can only see event changes made before you left." |
| **Удаление гостя** | хост | удаляет гостя; **сбрасывает ссылку-приглашение** (`RotateEventInviteLink`) | "Guest removed and event link reset" — явная мера против повторного присоединения, чтобы копия ссылки удалённого гостя перестала работать; удаление гостя, присоединившегося по ссылке, **не** задним числом делает недействительной ссылку для других, кто уже её использовал |
| **Пожаловаться на событие** | гость | отправляет отзыв в WhatsApp | "No one in the event will know about this report."; может также привести к выходу из события |
| **Приостановка** (модерация) | сервер (принудительное применение политики) | отличается от отмены | "Event suspended", "can't be changed right now"; заблокированное состояние, из которого хост не может выйти редактированием |

Удаление приглашённых по отдельности (`RemoveEventInvitations`) отличается от удаления присоединившегося гостя (`RemoveEventGuestUseCase`); `AddEventInvitations`/`RemoveSelfEventInvitation` дополняют управление списком приглашений.

---

## 9. UI RSVP и статусы

`EventRsvpBottomSheet` предлагает четыре радио-опции, привязанные к resource id `rsvp_going_btn`, `rsvp_going_with_guest_btn` (показывается только когда установлен `extraGuestsAllowed` и наблюдатель выбирает количество гостей > 0), `rsvp_not_going_btn`, `rsvp_maybe_btn`; ни одна кнопка не отмечена для состояния без ответа/`NO_RESPONSE`. Подписи (found, strings.xml): "Going", "Going with guest", "Maybe", "Not going". Гость может дополнительно указать количество "+1" (`extraGuestCount`, wire-поле 3 у `EventResponseMessage`), что обусловлено `EventMessage.extraGuestsAllowed` (поле 9) / "You can't turn off 'Allow guests' for this event." после того, как гости уже ответили RSVP с "+1".

RSVP от не-пользователя WhatsApp явно поддержан через ссылку-приглашение: "Guests can respond even if they're not on WhatsApp." — `JoinEventViaLink` принимает `rsvp_status` напрямую без аутентифицированной сессии WA, т.е. зашифрованный путь `encEventResponseMessage` не единственный канал RSVP; RSVP по ссылке идёт через плейнтекстовый GraphQL.

---

## 10. Модель видимости и приватности

Это самый важный факт "не путать" про Events: в отличие от обычного содержимого чата, **метаданные события явно раскрываются серверу**, а не являются чисто E2E-непрозрачными.

| Строка (found) | Ресурс | Значение |
|---|---|---|
| "Event details will be visible to guests and WhatsApp." | `str19d9` | название/описание/время/локация читаемы на стороне сервера (согласуется с тем, что это переменные GraphQL `CreateEvent`/`UpdateEvent`, а не только зашифрованные байты proto) |
| "Event details are visible to guests and WhatsApp. Your personal messages and calls remain end-to-end encrypted." | `str1a3f` | явное ограничение: гарантия E2EE *не* распространяется на детали события |
| "Your name and response will be visible to other guests and WhatsApp." | `str1a08` | идентичность + ответ RSVP также видны серверу (согласуется с тем, что `UpdateEventRsvp` — это плейнтекстовая мутация GraphQL, отдельная от зашифрованного эха `encEventResponseMessage` в плоскости чата) |
| "Respond to see the event location and more." / "Respond to see location" | `str19c7`/`str19c4` | локация **закрыта до RSVP** для гостей, которые ещё не ответили |
| "You can only see guests in your contacts or who you've messaged on WhatsApp." | `str1974` | видимость списка гостей ограничена собственным графом контактов/чатов наблюдателя, а не полным ростером |
| "Anyone with the link can see the event and share it with others, even if they're not on WhatsApp." | `str198b` | ссылка-приглашение/QR полностью минует членство — обладание ссылкой само является контролем доступа |

Итого: E2E-шифрование `encEventResponseMessage` (HKDF + AES-GCM, §5, `WA_MESSAGE_SECRETS.md`) защищает payload RSVP **в переписке чата / от relay**, но тот же ответ RSVP и собственные метаданные события независимо отправляются серверу в плейнтексте через плоскость управления GraphQL для синхронизации, обнаружения и гостей по ссылке (не-WA). Эти две плоскости не являются взаимоисключающими — они сосуществуют для одного и того же события.

---

## 11. Контекст группы vs 1:1 vs сообщества

- **Чат 1:1**: создать событие может любая из сторон; переменная GraphQL `is_group_based_event` равна false.
- **Групповой чат**: `is_group_based_event: true`; композер показывает "Created for:" с указанием группы; приглашения можно дополнительно брать из членства в группе (`EventInviteFromGroupsLoadController`, `EventInviteGroupFetcher`), позволяя хосту приглашать людей из других общих групп.
- **Сообщество**: Events отображаются и на уровне сообщества — "Events in announcements", "Community events", "See all community events" (найденные строки) — список событий всего сообщества, отдельный от событий одной группы.
- **Автономное / по ссылке**: событие не обязано быть привязано к какому-либо чату; `GetOrCreateEventInviteLink` + `EventInviteLinkQrActivity` создают расшариваемую ссылку/QR независимо от членства в чате (§10, `str198b`).

Классификация поддержки companion у `eventMessage` (`WA_MESSAGE_SECRETS.md` §15, `CompanionSupportVerifier`) допускает станзу `type="event"` на связанном (companion) устройстве — т.е. карточка приглашения всё ещё может быть *получена и сохранена* там — но взаимодействие с ней блокируется: `EventsCompanionRedirectDialog` + строка "To view or respond to this event, use WhatsApp on your primary device." (found) перенаправляет пользователей companion-устройства прочь от UI Events v2 целиком. Это осознанное разделение: доставка на уровне станзы безопасна для companion, взаимодействие на уровне функции — только для основного устройства.

---

## 12. Напоминания и уведомления

| Механизм | Триггер | Found/Inferred |
|---|---|---|
| `hasReminder`/`reminderOffsetSec` (wire-поля 11/12 у `EventMessage`) | настраивается хостом, опции пикера Never / Time of event / 15 min / 30 min / 1 hour / 1 day before start | found (строки UI); маппинг секунд inferred |
| Всегда включённое уведомление о начале | "Guests also get notified at the time of the event." (`str1a47`) | found — независимо от пользовательского напоминания, каждый гость получает уведомление при начале события |
| "Allow precise event reminders" | запрос разрешения ОС для точных по времени будильников | found |
| Уведомления об обновлении | текст зависит от того, какие поля изменились (§8) | found |
| Уведомление об отмене | "%1$s canceled %2$s. See event" | found |
| Push MEX (`xwa2_notify_event_on_invite`/`_on_update`) | серверная синхронизация, независимая от доставки чата | found (§6.1) |

---

## 13. Feature flags

В этом проходе не было найдено числовых ID feature flag, управляющих поведением Events v2 — в отличие от изолированных булевых/int-проверок gatekeeper в `WA_MESSAGE_SECRETS.md`, аксессоры dependency injection у пакета `eventsv2.*` (`C05T.A00(NNNNN)`, `C05Z.A00(NNNNN)`) — это id для lookup компонента/синглтона, а не чтения флагов, и не найдено булевой проверки в стиле `AbstractC...Gatekeeper`, привязанной к числовому флагу, которая охраняла бы создание события, RSVP или редирект companion. Релевантными остаются два флага, уже документированных для общего пути криптографии RSVP: **15791** (модификатор конвертации LID→PN для event-response в чатах 1:1) и механизм allowlist для companion/классификатора типа сообщения в `WA_MESSAGE_SECRETS.md` §15–16. Неизвестно, существует ли отдельный kill-switch, управляющий самим UI Events v2.

---

## 14. Baileys

В `baron-baileys-v2` 1.5.17 не найдено обработки отправки или приёма `eventMessage`/`eventInviteMessage`, а также шифрования RSVP `encEventResponseMessage`, сверх того, что уже документировано в `WA_MESSAGE_SECRETS.md` §17 для общего пути криптографии add-on (расшифровать входящий `encEventResponseMessage` можно с помощью общей таблицы use case, но кода отправителя или модели события, специфичного для события, не существует). `eventMessage` и `eventInviteMessage` в остальном являются обычными полями `Message` и отправляются через `snowi.sendjson` со скалярными полями из §2/§3 — для составления такого сообщения вообще не требуется крипто-хелпер, только `encEventResponseMessage` (RSVP) требует его. Клиента GraphQL для операций `www` из §6 в Baileys не существует; они требуют пути POST с persisted-`doc_id` GraphQL, который не реализован.

| Тема | Baileys | Android |
|---|---|---|
| Отправка `eventMessage`/`eventInviteMessage` | обычное поле `Message`, достижимо через `snowi.sendjson` | то же |
| Шифрование `encEventResponseMessage` | не реализовано (только расшифровка, общий путь use case) | `DU9.ADr` + `MessageSecretCryptoHelper` |
| Операции GraphQL Events v2 (§6) | не реализовано | `GraphqlEventsDataSource` |
| Push-синхронизация MEX (§6.1) | не реализовано | `DefaultEventsNotificationRepository` |

---

## 15. Ошибки / подводные камни

| Симптом | Причина | Примечание |
|---|---|---|
| Расшифровка RSVP не удаётся / ошибка 51 | неверный ключ исходного сообщения, или несовпадение пространства имён отправитель/цель (PN vs LID) | общее с путём голоса в опросе / комментария, см. `WA_MESSAGE_SECRETS.md` §18 |
| Событие видно в списке Events, но никогда не появлялось в чате | push MEX (`xwa2_notify_event_on_invite`) синхронизировал его независимо от доставки чата | §6.1 |
| Отсутствует локация/список гостей для приглашённого | ещё не ответил RSVP (локация закрыта), или гость не в контактах/истории чата наблюдателя (список гостей ограничен) | §10 |
| Удалённый гость всё ещё может ответить RSVP по старой ссылке | удаление гостя сбрасывает ссылку только *для этого* гостя; другие держатели уже расшаренной ссылки не затронуты | §8, `str19ed` |
| "Can't change event" / событие заблокировано | событие приостановлено по причинам политики, а не просто отменено | §8 |
| Устройство-companion не может открыть событие | взаимодействие Events v2 доступно только на основном устройстве, хотя сама станза доставляется на companion | §11 |
| `EventInviteMessage.status` (13) нельзя точно разобрать/сформировать | класс enum статически не восстановлен; **не доказано**, что идентичен словарю GraphQL `rsvp_status`/`status` | §3, §5.3 |

---

## 16. Ключевые различия

| Это | Не это |
|---|---|
| `eventMessage` (поле 75, базовое, 12 полей, неизменно до 41.6) | `eventInviteMessage` (поле 122, `DTQ`, 13 полей, активная карточка "Events v2") |
| `encEventResponseMessage` (E2E-зашифрованное эхо RSVP в чате) | `UpdateEventRsvp`/`JoinEventViaLink` (плейнтекстовый RSVP через GraphQL, видимый серверу) |
| Отмена (устанавливает `isCanceled`, закрывает RSVP, событие остаётся видимым) | Удаление (убирает из списка хоста; приглашения в чате остаются, помечены как удалённые) |
| Удаление (инициировано хостом, затрагивает копию хоста + помечает удалённым для остальных) | Выход (инициирован гостем, гость перестаёт видеть дальнейшие обновления) |
| Приостановка (блокировка модерацией сервера) | Отмена (действие хоста) |
| Удаление гостя + сброс ссылки (хост, делает недействительной копию ссылки *этого* гостя) | Удаление приглашения (хост, до того как гость присоединился) |
| wire-зеркалирующий enum RSVP `E2D`/`C9T8` (GOING=1, NOT_GOING=2, MAYBE=3, UNKNOWN=0) | локальный enum БД `C9T6` (GOING=0, NOT_GOING=1, MAYBE=2, NO_RESPONSE=3) — другой порядок, та же концепция |
| строковый enum GraphQL `rsvp_status` `C9U0` (`GOING`/`MAYBE`/`NOT_GOING`/`NO_RESPONSE`) | `EventInviteMessage.status` (поле 13) wire int32 open enum — не восстановлен, не доказано совпадение |
| Видимость списка гостей (ограничена контактами наблюдателя) | Видимость события по ссылке/QR (открыта любому, у кого есть ссылка) |

---

## 17. Полный поток (групповое событие, создание → RSVP → обновление)

```
[Host]                                   [WhatsApp server / GraphQL+MEX]           [Guest]
   │ CreateEvent (GraphQL, www)                   │                                   │
   │  chat_jid, description, location, cover──────▶ stores event, assigns eventId     │
   │◀──────────────────────────────────────────── eventId                             │
   │ compose eventInviteMessage (eventId,          │                                   │
   │   coverImageHandle, locationName, ...)        │                                   │
   │ <message type="event"> (E2E, chat plane)──────┼──────────────────────────────────▶ renders invite card
   │                                                │  xwa2_notify_event_on_invite      │
   │                                                ├──────────────────────────────────▶ event appears in
   │                                                │  (MEX push, independent of chat)    Events list too
   │                                                │                                   │ opens EventRsvpBottomSheet
   │                                                │                                   │ picks Going/Maybe/Not going
   │                                                │◀───────── UpdateEventRsvp (GraphQL, plaintext rsvp_status)
   │                                                │◀───────── encEventResponseMessage (E2E, chat plane)
   │  guest list / "Going" badge updates            │  xwa2_notify_event_on_update?     │
   │  (location now visible to guest)               │  (on edits)                       │
   │                                                │                                   │
   │ UpdateEvent (change location/time)─────────────▶ lastUpdatedTsUsec advances         │
   │                                                ├──────────────────────────────────▶ "Event date and location
   │                                                │                                      have been updated."
```

---

## 18. Неизвестное

| Элемент | Состояние |
|---|---|
| Имена членов enum `EventInviteMessage.status` (поле 13) | статически не восстановимо; строки GraphQL `rsvp_status`/`status` (§5.3) — вероятный, но неподтверждённый аналог |
| Точные секунды `reminderOffsetSec` по опции пикера | inferred (0/900/1800/3600/86400), пул констант не разрешён |
| Формат URL ссылки-приглашения / QR (`chat.whatsapp.com/event/...` или похожий) | не найден в строках или intent-фильтрах манифеста в этом проходе |
| Числовые ID feature flag, управляющих созданием/RSVP/редиректом companion у Events v2 | не найдено (см. §13) |
| Точная связь между `EventInviteMessage.status` и локальными прикладными enum `C9T6`/`C9T8` | не прослежено |
| Поведение "Require approval to join" (`str1a34`) | строка найдена; код не прослежен |
| Заполняются ли поля history-sync `eventResponses`(61)/`eventAdditionalMetadata`(64) при исходящей синхронизации, входящей, или обеих | не прослежено |
