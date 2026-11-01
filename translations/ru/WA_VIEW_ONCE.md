<!-- src-sha1: b9a264b89fe2f15a6ff3587c9bc5a6b3a47e10c0 -->
# WhatsApp View-Once — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-11-01
**Область:** обёртка `viewOnceMessage` / `viewOnceMessageV2` / `viewOnceMessageV2Extension` в сравнении с инлайн-полем `viewOnce` на `ImageMessage` / `VideoMessage` / `AudioMessage` / `ExtendedTextMessage`, общий механизм развёртывания обёрток сообщений, разделяемый с disappearing messages, типы сообщений и общий маркерный интерфейс, клиентские ограничения (блокировка скриншотов/записи экрана, запрет forward/share/save, блокировка просмотра собственного сообщения отправителем, зачистка медиа в цитате), локальное хранение и state machine (`message_view_once_media`, задача удаления), жизненный цикл media key (связан, не повторяется), wire-кейс `unavailable[type="view_once"]` и межустройственные токены read/write, feature-флаги, сравнение с Baileys

---

## 1. Что это такое

View-once — это атрибут отдельного сообщения, а не отдельный тип сообщения: любое изображение, видео, голосовое сообщение или (в последних сборках) текст можно помечать так, что клиент получателя удаляет локальную копию после первого открытия, а также блокирует скриншоты/запись экрана и скрывает forward/share/save, пока сообщение открыто. Все утверждения получены статическим анализом декомпилированного APK; на wire ничего не перехватывалось. Уровни: **found** = прочитано в коде, **inferred** = выведено из кода, **unknown** = не разрешено. Имена разрешены в 2.26.41.6 по стабильным строкам и лог-тегам (`AppDataManager/contributeMetaAppData`, `ConversationRowViewOnceMedia/`, `EphemeralUpdateRunnable/`, `ViewOnceMessageStore/`, идентификаторы строк UI).

| Сущность | Имя в 2.26.41.6 | Роль |
|--------|-----------------|------|
| Обёртка сообщения (одно поле, `message` **1**) | `BD2` | тело `viewOnceMessage` **37**, `viewOnceMessageV2` **55**, `viewOnceMessageV2Extension` **59** в `Message` (`C30628DTw`) |
| Инлайн-флаг на каждом типе медиа | `ImageMessage.viewOnce` **25**, `VideoMessage.viewOnce` **20**, `AudioMessage.viewOnce` **21**, `ExtendedTextMessage.viewOnce` **30** | устанавливается прямо на медиа-/текстовом сообщении, без обёртки |
| Переключатель инлайн/обёртка | флаг **8784** | on: только инлайн-поле; off: обёртка + инлайн-поле одновременно (6.3) |
| Обработчик view-once изображения | `C34670F2r` ("FMessageViewOnceImageProtobuf") | строит/читает `DdP`, тип сообщения **42** |
| Обработчик view-once видео | `C34671F2s` ("FMessageViewOnceVideoProtobuf") | строит/читает `C30972DdZ`, тип сообщения **43** |
| Обработчик view-once текста | `F33` ("FMessageViewOnceTextProtobuf") | строит/читает `C31208Dhd`, тип сообщения **78** |
| Обработчик view-once аудио | `C34669F2q` ("FMessageViewOnceAudioProtobuf") | строит/читает `C30963DdH`, тип сообщения **82** |
| Маркерный интерфейс | `InterfaceC24513Ahd` | реализуется всеми четырьмя FMessage-классами выше; используется для общего гейтинга поведения UI/меню |
| Таблица локального состояния | `message_view_once_media` | колонки `message_row_id`, `state` |
| Аксессор состояния | `C199158dT` ("ViewOnceMessageStore") | get/insert/update `state` |
| Задача удаления | `EphemeralUpdateRunnable` (анонимный класс в `C199218dZ`), тип задачи **3** | "`ViewOnceMessageStore/getViewOnceMessagesToDelete`" |
| Хелпер блокировки захвата экрана | `C66572s0` | `window.addFlags(8192)` = `FLAG_SECURE` |
| Гейт view-once для медиа-вьюера | `C1ZB.A0O(i)` | `i == 42 \|\| i == 43` |
| Отдельный вьюер (текст/аудио) | `ViewOnceViewerActivity`, `ViewOnceTextFragment`, `ViewOnceAudioFragment` | отдельная Activity, всегда `FLAG_SECURE` |
| Общий вьюер (изображение/видео) | `MediaViewFragment` / `MediaViewMenu` | обычный медиа-вьюер, `FLAG_SECURE` только когда `C1ZB.A0O` истинно |
| Обучающие шиты | `ViewOnceNuxBottomSheet`, `ViewOnceSecondaryNuxBottomSheet` | одноразовый объяснительный экран, показываемый отправителю/получателю |
| Зачистка медиа в цитате | `F43` ("QuotedMediaCleanupSerializationPostProcessor") | удаляет байты медиа из цитаты view-once сообщения, флаг **25572** |

---

## 2. Маркировка в proto

### 2.1 Инлайн-поле (found)

```text
ImageMessage.viewOnce         = 25  (bool)
VideoMessage.viewOnce         = 20  (bool)
AudioMessage.viewOnce         = 21  (bool)
ExtendedTextMessage.viewOnce  = 30  (bool, VIEW_ONCE_FIELD_NUMBER)
```

Каждое поле — обычный булев флаг на соответствующем медиа-/текстовом сообщении; отдельный контейнер для его переноса не требуется. Подтверждено чтением сгенерированных таблиц полей `C30612DTg` (Image), `C30614DTi` (Video), `DTX` (Audio), `C30613DTh` (ExtendedText).

### 2.2 Обёртка сообщения (found)

`viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**) и `viewOnceMessageV2Extension` (**59**) в `Message` все типизированы как `BD2`, а у `BD2` ровно одно поле — `message` **1**, само являющееся `Message`. Все три имени полей декомпилируются в один и тот же класс — это одна и та же форма обёртки, использованная трижды для трёх поколений протокола:

```java
public final class BD2 extends GeneratedMessageLite {
    public static final int MESSAGE_FIELD_NUMBER = 1;
    public C30628DTw message_;   // a full nested Message
}
```

### 2.3 Инлайн против обёртки: флаг 8784 (found)

Каждый обработчик по типу (`C34670F2r` изображение, `C34671F2s` видео, `F33` текст, `C34669F2q` аудио) строит одно и то же дважды и выбирает вариант по флагу:

```java
boolean zA15 = this.A00.A15(8784);
...
if (zA15) {
    dp5.A0R(c30612DTg);                 // inline viewOnce=true directly on the outer Message
    return;
}
dp5A0f.A0R(c30612DTg);                  // same media message, but inside the BD2 wrapper
BD2 bd2A0Q = ...;
c30628DTwA0j.viewOnceMessageV2_ = bd2A0Q;
```

При включённом флаге 2.26.41.6 никогда не выпускает обёртку для локально составленного view-once сообщения; обработчики приёма `CM7` (receive) в тех же классах смотрят только на инлайн-флаг (`c30612DTg.bitField0_ & ... && c30612DTg.viewOnce_`), а не на поля обёртки — развёртывание обёртки до инлайн-формы — отдельный, общий шаг (2.4).

### 2.4 Общее развёртывание обёртки (found)

Статическая таблица (`AbstractC33204EdH.A00`, 35 записей) сопоставляет предикат "есть такая обёртка" с экстрактором "получить внутренний `Message`" для каждой forward-compatibility обёртки, известной клиенту, включая `ephemeralMessage` (обёртка disappearing-сообщений), `viewOnceMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `documentWithCaptionMessage`, `botInvokeMessage`, `groupStatusMessage` и другие. `C34748F5r` (валидация native-flow/`<biz>`, `AbstractC33204EdH.A00`) рекурсивно обходит эту таблицу до глубины 10, чтобы найти классифицируемый контент независимо от того, сколько обёрток его окружает:

```java
for (EQR eqr : AbstractC33204EdH.A00) {
    if (hasWrapper(c30628DTw, eqr) &&
        A00(..., unwrap(c30628DTw, eqr), i + 1) != C02U.A00) {
        return result;
    }
}
```

`ephemeralMessage` и три обёртки view-once — равноправные записи в этой таблице: структурно это один и тот же механизм, поэтому view-once сообщение в принципе может быть вложено внутрь обёртки disappearing-сообщений или находиться рядом с ней (раздел 7). Это отражается в собственном списке `getFutureProofMessage()` Baileys в `message-inspect.js`, который перечисляет тот же набор имён полей обёрток.

---

## 3. Типы сообщений и маркерный интерфейс

| Тип | Класс медиа | Обработчик | Fragment/Activity |
|------|-------------|---------|--------------------|
| **42** | `DdP` (изображение) | `C34670F2r` | `MediaViewFragment` (общий вьюер изображений/видео) |
| **43** | `C30972DdZ` (видео) | `C34671F2s` | `MediaViewFragment` |
| **78** | `C31208Dhd` (текст) | `F33` | `ViewOnceTextFragment` внутри `ViewOnceViewerActivity` |
| **82** | `C30963DdH` (аудио/ptt) | `C34669F2q` | `ViewOnceAudioFragment` внутри `ViewOnceViewerActivity` |

Все четыре класса реализуют `InterfaceC24513Ahd` — единственный маркер, который остальная часть клиента проверяет ("это view-once сообщение") вместо того, чтобы повторять проверку по четырём типам везде. `C1ZB.A0O(i)` (`i==42 || i==43`) — более узкая проверка "только изображение/видео", используемая там, где общему `MediaViewFragment` нужно отличить view-once изображение/видео от всего остального, что он также отображает.

Набор типов `{42,43,78,82}` буквально повторяется в нескольких независимых точках вызова, найденных в этой сборке: производитель `<meta view_once="true">` (раздел 6.1), таблица соответствия имени типа (`AbstractC32316E9h`: `"viewOnceImage"`=42, `"viewOnceVideo"`=43, `"viewOnceAudio"`=82), и вспомогательные методы `C1ZB` для гейтинга сохранения/отображения.

---

## 4. Клиентские ограничения

### 4.1 Блокировка скриншота / записи экрана (found)

`C66572s0.A00(Window)` — однострочный хелпер:

```java
public final void A00(Window window) {
    if (window != null) {
        window.addFlags(8192);   // WindowManager.LayoutParams.FLAG_SECURE
    }
}
```

`8192` (`0x2000`) — числовое значение `FLAG_SECURE`; декомпилированные исходники используют числовую константу, а не символическое имя, поэтому текстовый поиск `FLAG_SECURE` ничего не находит — константу нужно сопоставлять по значению. `FLAG_SECURE` затемняет окно на скриншотах, в миниатюре recent-apps и во время записи/трансляции экрана на уровне ОС; это не WhatsApp-специфичное обнаружение, это стандартный Android-флаг secure-window.

Две точки вызова:

| Точка вызова | Условие | Область действия |
|-----------|-----------|-------|
| `MediaViewFragment` (общий медиа-вьюер) | `C1ZB.A0O(i)`, т.е. `i==42 \|\| i==43` | применяется только когда отображаемое сообщение — view-once изображение/видео; иначе обычный медиа-вьюер не защищается |
| `ViewOnceViewerActivity.onCreate` | безусловно | эта Activity запускается только для view-once текста (78) или аудио (82), поэтому каждый её экземпляр защищён |

Итоговый эффект: открытие любого из четырёх типов view-once устанавливает `FLAG_SECURE` на окне-хосте на всё время, пока оно открыто; закрытие вьюера (разрушение fragment/activity) удаляет окно, а вместе с ним и флаг. Доказательств механизма *обнаружения* скриншота (например, `FileObserver` на `Pictures/Screenshots` или content-observer `MediaStore`) не найдено; защита — это предотвращение на уровне ОС, а не обнаружение постфактум.

### 4.2 Запрет forward / share / save (found)

`ViewOnceViewerActivity.onCreateOptionsMenu` строит ровно четыре пункта меню — info, transcribe (только для аудио), delete, report — и никаких других; в этом меню нет ни forward, ни share, ни save, ни copy. В общем `MediaViewMenu` (используется для view-once изображения/видео через обычный медиа-вьюер) несколько булевых локальных переменных видимости пунктов меню вычисляются с явным исключением `instanceof InterfaceC24513Ahd`, например:

```java
if (i6 == 2 && !c36911dGA1I21.element && ... && !(abstractC34931a2 instanceof InterfaceC24513Ahd)) {
    z14 = !C0DZ.A0X(c0df);     // forward-related menu flag, left false (hidden) for view-once
}
...
z16 = abstractC34931a2 instanceof InterfaceC24513Ahd;
if (!z16) {
    z17 = !AbstractC24760wu.A07(c0df);   // another gated flag, defaults false for view-once
}
```

Поскольку каждый флаг по умолчанию `false` и получает рабочее значение только в не-view-once ветке, соответствующие пункты меню остаются скрытыми для `InterfaceC24513Ahd`-сообщений. Ограничение реализовано на уровне UI (построение меню), а не удалением исходного медиа с диска до открытия вьюером.

### 4.3 Отправитель не может повторно открыть собственное медиа (found)

`DYM` (компонент строки разговора для view-once медиа) содержит утверждение:

```java
C00K.A0C(false, "ConversationRowViewOnceMedia/senders can not view their own media");
```

на пути, которым бы воспользовалась строка собственного отправленного view-once сообщения отправителя для повторного открытия контента — т.е. инвариант "отправитель никогда не получает рабочий обработчик открытия для собственного view-once сообщения" реализован как жёсткое assertion, а не как условное скрытие в UI.

### 4.4 Цитирование удаляет медиа (found)

`F43` ("QuotedMediaCleanupSerializationPostProcessor", гейтится флагом **25572**) переписывает `imageMessage` / `videoMessage` / `documentMessage` / `audioMessage` цитируемого сообщения перед тем, как оно прикрепляется как `contextInfo.quotedMessage` к *новому* исходящему сообщению: он копирует неконтентные поля (mimetype, caption, размеры, thumbnail, сам бит `viewOnce`), но отбрасывает `mediaKey`, `fileSha256`/`fileEncSha256` и `directPath`. Поэтому цитирование view-once сообщения не может протащить оригинальный media key в ответ; цитата показывает только метаданные.

### 4.5 Обучающие шиты (found)

`ViewOnceNuxBottomSheet` показывается один раз на роль (отправитель/получатель — отслеживается ключами UXCam `ephemeral_view_once` / `ephemeral_view_once_receiver`) при первой отправке/получении view-once сообщения каждой стороной, с текстом, взятым напрямую из `res/values/strings.xml`:

| Id строки | Текст |
|-----------|------|
| `str4e56` | "View once messages give you more privacy" |
| `str4e55` | "For added privacy, the recipient can't share, forward, copy, save, or take a screenshot of it." |
| `str4e68` / `str4e5d` / `str4e7b` | варианты по типу: "This is a view once photo/message/video so it's more private" |
| `str4e69` / `str4e6a` / `str4e5c` | "Also, you can't share, forward, copy, save, or take a screenshot of it." |
| `str4e63` / `str4e64` | "View once photo, expired" / "View once photo, opened" (та же схема для видео/аудио/текста) |

Пары строк "expired"/"opened" для каждого типа (изображение, видео, аудио, текст) — видимая пользователю сторона локальной колонки `state` (раздел 5).

---

## 5. Локальное хранение и state machine

### 5.1 Таблица (found, `C199158dT`)

```sql
-- message_view_once_media(message_row_id, state)
SELECT state FROM message_view_once_media WHERE message_row_id = ?     -- GET_VIEW_ONCE_STATE_BY_MESSAGE_ROW_ID_SQL
UPDATE message_view_once_media SET state = ? WHERE message_row_id = ?  -- UPDATE_VIEW_ONCE_SQL
INSERT INTO message_view_once_media (message_row_id, state) VALUES (?, ?)  -- INSERT_VIEW_ONCE_SQL
```

Одна строка на view-once сообщение, независимо от общих таблиц `message` и `message_media` (которые всё так же хранят учёт строки/медиафайла, общий с обычными сообщениями).

### 5.2 Состояния (found значения строк, сопоставление имён частично inferred)

| Переход | Код | Триггер |
|------------|------|---------|
| Строка создана | `A02` (`BDk()` на FMessage, значение при создании) | сообщение отправлено/получено; начальное значение — то, что сообщает FMessage, что согласуется с "0 = не открыто", но именованная константа не найдена |
| Отмечено как открытое | `A03`: `state = 1` | статус сообщения (`B6u()`) достигает **8**, **9** или **10** (коды статуса, связанные с загрузкой/прочтением; точные имена не разрешены) |
| Прочитано без строки | fallback `i = 2` в `A01` | `GET_VIEW_ONCE_STATE...` не возвращает строку; код обрабатывает это как если бы сообщение уже истекло |

Итак, **1** = подтверждённое "открыто" (именованная точка вызова); **2** — fallback-значение для отсутствия записи/истечения срока; начальное значение/"не открыто" существует, но не привязано к литералу в этой сборке.

### 5.3 Удаление (found)

Тот же класс `EphemeralUpdateRunnable`, который истекает disappearing-сообщения (тип задачи 0, таблица `message_ephemeral`) и дополнения message-secret (тип задачи 4, таблица `message_add_on`), также запускает задачу типа **3**, логируемую как `ViewOnceMessageStore/getViewOnceMessagesToDelete`:

```sql
SELECT message.* FROM message_view_once_media AS view_once
  JOIN message AS message ON view_once.message_row_id = message._id
  JOIN message_media AS message_media ON message_media.message_row_id = message._id
WHERE message_media.file_size IS NOT NULL
  AND message_media.file_size IS NOT 0
  AND message.from_me = 0
  AND view_once.state IN (1, 2)
LIMIT ?
```
<sub>(упрощённый список колонок; `GET_EXPIRED_VIEW_ONCE_MESSAGES_SQL`)</sub>

Читая буквально: задача целится только на *полученное* view-once медиа (`from_me = 0`), у которого ещё есть файл на диске (`file_size` присутствует и не равно нулю), и чьё состояние — `1` (открыто) или `2` (то же fallback-значение, используемое для "нет строки"/истекло). Задача освобождает локальный медиафайл для строк, подходящих под этот запрос; саму строку сообщения она не удаляет (строка выживает, несёт метку "открыто"/"истекло" из UI, см. 4.5). **Отправленное** view-once медиа (`from_me = 1`) этим запросом не покрывается — это согласуется с тем, что отправитель никогда не может повторно открыть его (4.3), но соответствующая зачистка собственной копии отправителя не найдена; её хранение/удаление — **unknown**.

### 5.4 Жизненный цикл media key / криптографии (связан, не повторяется)

View-once медиа использует обычный медиа-пайплайн от начала до конца — та же таблица `MmsType`, тот же вывод ключей HKDF-80, тот же конверт AES-CBC+HMAC, те же URL загрузки/скачивания; отдельной `MmsType`-строки "view-once" не существует. См. [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) разделы 3-5 по криптографии и раздел 12 этого отчёта по заметкам, специфичным для view-once (assertion "отправитель не может просмотреть", лог-тег удаления миниатюры). Удаляет ли или помечает ли сервер самостоятельно загруженный объект после первого скачивания — **unknown** из этого статического анализа: клиентская гарантия — это удаление локального файла из 5.3, а не наблюдаемый клиентом серверный контракт.

---

## 6. "View once unavailable" / межустройственная сигнализация

### 6.1 Стенза `unavailable[type="view_once"]` (поправка к более ранней заметке исследования)

Более ранняя заметка исследования (2.26.35.2) прослеживала исходящую литеральную пару `view_once`/`true` до метода, логируемого как `AppDataManager/contributeMetaAppData`, и оставляла открытым вопрос, строит ли этот метод полный узел или только дополняет метаданные. В 2.26.41.6 тот же лог-тег (`"AppDataManager/contributeMetaAppData type="`) **не** является производителем `view_once`: он принадлежит другой, не связанной ветке `F6K` (общий построитель узла `<meta>`), которая ставит произвольный атрибут `appdata` для сообщений ботов/дополнений (`FZF.AVN()`). Фактический атрибут `view_once` в этой сборке строится несколькими строками раньше в *том же* методе `F6K`, независимо от этой лог-строки:

```java
if (c08j2.A15(11282) && (i == 42 || i == 43 || i == 82 || i == 78)) {
    EZV.A00(ezv, "view_once", "true");
}
```

Это выпускает `<meta view_once="true">` как дочерний/атрибут узла `<meta>` исходящей стензы `<message>` (а не дочерний узел `<unavailable type="view_once">`, который описывают заметка исследования и Baileys/whatsmeow). Оба могут быть истинны одновременно: `<meta view_once="true">` — это маркер в собственной стензе отправителя, что это сообщение view-once; `<unavailable type="view_once">` — это *другой* узел, наблюдаемый только на принимающей/Web-стороне, когда шифротекст не был разослан на это устройство. Статический анализ Android APK (у которого здесь нет роли Web/связанного устройства) не может показать, какая сторона собирает этот второй узел; этот отчёт не меняет сделанный ранее вывод средне-высокой уверенности, что он сервер-производный или нормализован сервером из состояния fanout отправителя. Baileys подтверждает приёмную сторону *более специфичным* литералом, чем общий: `src/Socket/messages-recv.js` проверяет `unavailableType === 'view_once_unavailable_fanout'` (наряду с `bot_unavailable_fanout`, `hosted_unavailable_fanout`), чтобы решить, пропускать ли запрос повторной отправки placeholder "по требованию", а `src/Utils/decode-wa-message.js` отдельно сопоставляет простой `attrs.type === 'view_once'` на дочернем узле `<unavailable>`, чтобы установить `isViewOnce`/`StubType.VIEWED_ONCE`. Это два разных пути кода для того, что более ранняя заметка исследования рассматривала как одну строку.

### 6.2 Токены `view_once="read"`/`"write"` (found токен, потребитель не разрешён)

Литералы `view_once_read` и `view_once_write` присутствуют в таблице словаря бинарных стенз Android-клиента (`AbstractC40911lb`, фиксированный список словаря wire-формата, используемый для компактного кодирования токенов) — в той же таблице, что несёт `unavailable`, `enc`, `polltype` и т.д. `decode-wa-message.js` Baileys читает значение `attrs.view_once`, равное `'read'` или `'write'`, на атрибутах уровня `<enc>` и сохраняет его как `fullMessage.viewOnceType`. В совокупности это согласуется с сигналом синхронизации "уже открыто" по собственным устройствам, едущим вместе с конвертом сообщения — предположительно именно так другие связанные устройства пользователя узнают, что view-once контент уже был открыт на одном из устройств — но ни одной точки вызова Android, которая *устанавливает* или *потребляет* этот атрибут, в 2.26.41.6 не найдено; здесь он зафиксирован как найденный wire-токен с неразрешённым потребителем на Android (**unknown**).

---

## 7. Взаимодействие с disappearing messages

View-once и disappearing messages (TTL сообщения на уровне чата) — независимые, ортогональные флаги, которые могут быть установлены на одном и том же сообщении одновременно:

- Они используют разные локальные таблицы: `message_ephemeral` (disappearing, ключ — `expire_timestamp`) против `message_view_once_media` (view-once, ключ — `state`).
- Оба истекают задачами на *том же* воркере `EphemeralUpdateRunnable` (тип задачи 0 для disappearing, тип задачи 3 для view-once, тип задачи 4 для дополнений message-secret) — общий путь планирования/выполнения, но различное состояние и SQL для каждой функции.
- На уровне proto `ephemeralMessage` — равноправная запись в той же самой общей таблице развёртывания обёрток, что и три обёртки view-once (раздел 2.4): сообщение может быть обёрнуто как `ephemeralMessage{message: viewOnceMessage{message: imageMessage{...}}}` или в обратном порядке вложенности, и рекурсивное развёртывание в `C34748F5r`, и `getFutureProofMessage()` Baileys обходят оба порядка.
- Удаление disappearing-сообщения убирает всё сообщение по истечении TTL чата независимо от того, было ли оно открыто; удаление view-once убирает только *медиафайл* после того, как сообщение было открыто (или попадает в fallback состояния 2), и оставляет строку сообщения (теперь показываемую как "открыто"/"истекло") на месте. Фотография view-once в чате с disappearing messages поэтому дополнительно подчиняется TTL чата сверх собственного правила "одно открытие — затем стирание".

---

## 8. Feature-флаги (id как прочитаны в точках вызова; имена не разрешены)

| ID | Тип | Контролирует |
|----|------|----------|
| **8784** | bool | отправлять view-once медиа только с инлайн-полем (on) против инлайн-поля + legacy-обёртки (off) |
| **11282** | bool | выпускать `<meta view_once="true">` для типов сообщений 42/43/78/82 |
| **25572** | bool | удалять поля медиа из цитируемого view-once сообщения (`F43`) |

(Флаги, управляющие общим медиа-пайплайном — HKDF, загрузка/скачивание, retry — перечислены в [WA_MEDIA_UPLOAD.md](./WA_MEDIA_UPLOAD.md) раздел 16 и не повторяются здесь.)

---

## 9. Baileys (`baron-baileys-v2`, источник прочитан, ничего не тестировалось)

| Тема | Baileys | Android 2.26.41.6 |
|-------|---------|---------------------|
| Маркировка на стороне отправки | всегда оборачивает: `{ viewOnceMessage \| viewOnceMessageV2 \| viewOnceMessageV2Extension: { message } }` в зависимости от опции `viewOnceVersion` (`src/Utils/messages.js`) | оборачивает только когда флаг 8784 выключен; по умолчанию (8784 включён) устанавливает инлайн-поле `viewOnce` прямо на медиа-/текстовом сообщении, без обёртки |
| Обёртка также используется для немедийных сообщений | `viewOnceMessage` дополнительно используется для futureproof-отправки `buttonsMessage`/`templateMessage`/`listMessage`/`interactiveMessage` (`src/Socket/messages-send.js`, `requiresViewOnce`) — не связано с приватностью самоуничтожения | тот же тип обёртки (`BD2`) переиспользуется в общей таблице развёртывания для `botInvokeMessage`, `editedMessage` и др. — та же роль "общего конверта" подтверждена независимо (2.4) |
| Список общего развёртывания | `getFutureProofMessage()` в `message-inspect.js`: `ephemeralMessage`, `viewOnceMessage`, `documentWithCaptionMessage`, `viewOnceMessageV2`, `viewOnceMessageV2Extension`, `editedMessage`, `groupMentionedMessage`, `botInvokeMessage`, ... | `AbstractC33204EdH.A00` (35 записей) — те же имена полей обёрток |
| Обработка приёма `unavailable` | две разные проверки литералов: `attrs.type === 'view_once'` (устанавливает `isViewOnce`) и `unavailableType === 'view_once_unavailable_fanout'` (пропускает повторную отправку placeholder) | только клиентский производитель `<meta view_once>` (6.1); сам узел `<unavailable>` — путь приёма/Web-сторона, здесь не прослежен |
| Токен чтения/записи `view_once` | декодирует `attrs.view_once === 'read' \| 'write'` на атрибутах `<enc>` в `viewOnceType` | токены присутствуют в словаре wire-формата клиента; потребитель на Android не найден (6.2) |
| Аналитика | `WAM/constants.js`: `viewOnceMessagesSent` (16), `viewOnceMessagesReceived` (17), `viewOnceMessagesOpened` (18) | не прослежено в этом отчёте; см. [WA_WAM_ANALYTICS.md](./WA_WAM_ANALYTICS.md) по механизму WAM в целом |
| Блокировка скриншота/forward | не реализовано — Baileys это backend-библиотека без UI, без окна, без меню для ограничения | `FLAG_SECURE` + скрытие пунктов меню (4.1-4.2); невоспроизводимо вне Android UI |
| Локальное удаление после открытия | неприменимо — у Baileys нет постоянной state machine медиа-вьюера; хранение — ответственность вызывающего | `message_view_once_media.state` + задача `EphemeralUpdateRunnable` типа 3 (5.1-5.3) |

---

## 10. Ошибки / подводные камни

| Симптом | Причина | Примечание |
|---------|---------|---------|
| View-once медиа отсутствует при повторном открытии вьюера | нормально: `state` достигло 1 (открыто) или строка отсутствовала (fallback 2), и задача удаления уже освободила файл | не баг; это задуманное поведение "одно открытие — затем стирание" |
| Собственное view-once медиа отправителя никогда не открывается из строки разговора | жёсткое assertion `DYM`: `senders can not view their own media` | по дизайну, не путь ошибки |
| Цитируемый view-once ответ не показывает медиа | `F43` удаляет `mediaKey`/хеши/`directPath` из цитаты, сохраняя только caption/размеры/thumbnail/бит `viewOnce` | ожидаемо; цитирование не может использоваться для повторного извлечения медиа |
| Вьюер view-once изображения/видео пропускает скриншоты на одних сборках, но не на других | `FLAG_SECURE` применяется только через `C1ZB.A0O(i)` (типы 42/43); любая регрессия в этом гейте (например, путь кода, открывающий общий вьюер для view-once элемента без прохождения через гейтируемый вызов) бесшумно снимает защиту | место гейта задокументировано в `MediaViewFragment` около строки 3120 (эта сборка) |
| Связанное устройство показывает view-once сообщение как уже открытое без того, чтобы пользователь открыл его там | возможная межустройственная синхронизация через wire-токены `view_once="read"/"write"` (6.2) | механизм не подтверждён на стороне Android; зафиксирован как unknown |

---

## 11. Ключевые различия

| Это | Не это |
|------|----------|
| Булево поле `viewOnce` на `ImageMessage`/`VideoMessage`/`AudioMessage`/`ExtendedTextMessage` | legacy-обёртка `viewOnceMessage`/`viewOnceMessageV2`/`viewOnceMessageV2Extension` вокруг того же сообщения |
| `viewOnceMessage` (`BD2`), используемый для приватности (самоуничтожение) | тот же тип обёртки `BD2`, переиспользуемый как общий конверт futureproofing для отправки buttons/template/list/interactive (Baileys) и для `botInvokeMessage`/`editedMessage` на Android |
| `message_view_once_media.state` (локальное, на сообщение, отслеживание открытия/истечения) | `message_ephemeral.expire_timestamp` (локальное, на сообщение, TTL чата с disappearing) — независимые таблицы, независимые задачи, один исполнитель |
| `<meta view_once="true">` — классификатор на стороне отправителя в исходящей стензе | `<unavailable type="view_once">` — другой узел, наблюдаемый на приёмной/Web-стороне, когда шифротекст не дошёл до этого устройства |
| `FLAG_SECURE` на окне вьюера (*предотвращение* скриншота/записи) | callback *обнаружения* скриншота — такой механизм не найден |
| Удаление локального *файла* медиа после открытия | удаление *строки* сообщения — строка выживает, помечена "открыто"/"истекло" |
| View-once (медиа стирается после одного открытия) | disappearing messages (всё сообщение удаляется после TTL на уровне чата) — ортогонально, может сочетаться |

---

## 12. Полный поток (фото view-once, чат 1:1)

```
[Sender]
   │ pick photo, mark "view once" in composer
   │ ImageMessage.viewOnce = true          (flag 8784 on: inline only)
   │ upload via normal media pipeline (WA_MEDIA_UPLOAD.md)
   │ flag 11282 on, type==42 → <meta view_once="true">
   ▼
[Server]  relays the E2E-encrypted stanza; cannot read viewOnce (it's inside the ciphertext)
   │
   ▼
[Receiver]
   │ decrypt → ImageMessage.viewOnce == true, message type 42 (DdP)
   │ INSERT message_view_once_media(message_row_id, state=<initial>)
   │ thumbnail shown in the conversation row; sender-side row asserts "can not view own media"
   │
   ├── user taps to open ──► MediaViewFragment, C1ZB.A0O(42) == true
   │                          → window.addFlags(FLAG_SECURE)
   │                          → forward/share/save menu items hidden (InterfaceC24513Ahd)
   │                          → status reaches 8/9/10 → state = 1 ("opened")
   │                          → window closed, FLAG_SECURE drops with it
   │
   ▼
[EphemeralUpdateRunnable, job type 3]
   │ SELECT ... FROM message_view_once_media JOIN message_media
   │   WHERE from_me=0 AND file_size IS NOT NULL AND state IN (1,2)
   ▼
local media file deleted; row kept, UI shows "View once photo, opened"
```

---

## 13. Неизвестное

| Пункт | Состояние |
|------|----------|
| Именованные константы для `state` 0 (начальное) и точное значение, общее между 2 (fallback без строки) и "истекло" | только у 1 ("открыто") есть именованная точка вызова; остальное выведено из fallback-значения и строк UI |
| Коды статуса 8/9/10, потребляемые `C199158dT.A03` для срабатывания "открыто" | не разрешены до именованных констант |
| Хранение/зачистка **собственной** копии отправленного view-once медиа отправителем | задача удаления целится только на `from_me = 0`; соответствующая зачистка на стороне отправителя не найдена |
| Удаление/пометка на стороне сервера загруженного объекта после первого скачивания | невозможно наблюдать из статического клиентского анализа |
| Построение узла `<unavailable type="view_once">` (клиентский placeholder против построенного сервером) | не разрешено; перенесено из более ранней заметки исследования, здесь заново не разрешено |
| Потребитель на Android wire-токенов `view_once="read"/"write"` | присутствие токена в таблице словаря подтверждено; точка вызова не найдена |
| Применяется ли `FLAG_SECURE` на каждом пути кода, который может показать view-once контент (например, превью уведомлений, виджет, Wear) | проверены только пути `MediaViewFragment` и `ViewOnceViewerActivity` |
