<!-- src-sha1: d4ba76d600d4bfecb03ea6dfec4064e9d1ae1733 -->
# WhatsApp Стикеры — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-11-01
**Область:** прото `Message.StickerMessage` (метаданные изображения/Lottie, флаги аватара/AI/премиум, `emojis`, `accessibilityLabel`), встроенные звуковые стикеры (`StickerMessage.audioMessage`), универсальные обёртки `lottieStickerMessage` / `audioStickerMessage`, `stickerPackMessage` (обмен паками стикеров), локальное хранение пака стикеров и формат ZIP `.was`/Lottie, `stickerSyncRmrMessage` (подтверждённо отсутствует), контракт интентов и content-provider сторонних паков стикеров, встроенный провайдер генерации AI-стикеров, локальный поиск стикеров, флаги функций; криптография медиа не повторяется (см. [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md))

---

## 1. Обзор

«Стикер» на Android — это одновременно один из нескольких типов проводных сообщений и большая первая подсистема приложения (магазин, локальные недавние, поиск, AI-генерация), а также публичная поверхность интеграции со сторонними приложениями (интенты + content-провайдеры). Все байты медиа (изображение стикера, ZIP пака, миниатюры) проходят через тот же зашифрованный медиапайплайн, что и любое другое вложение — см. [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md), раздел 3, строки `MmsType` (`sticker`, `sticker-pack`, `thumbnail-sticker-pack`, `newsletter-sticker`, `newsletter-sticker-pack`).

| Сущность | Поле `Message` | Тип wire | Роль |
|--------|------------------|-----------|------|
| Одиночный стикер | `stickerMessage` | **26**, `StickerMessage` (`C30611DTf`) | один стикер-изображение/анимация, отправленный в чате |
| Звуковой стикер (встроенный) | `StickerMessage.audioMessage` | **26** внутри `StickerMessage`, `oneof audio` → `AudioMessage` | короткая голосовая запись, прикреплённая к отправке стикера |
| Lottie-обёртка | `lottieStickerMessage` | **74**, `FutureProofMessage` (`BD2`) | универсальный конверт, название подразумевает Lottie-специфичную нагрузку; вложенное содержимое не разрешено |
| Обёртка audio-стикера | `audioStickerMessage` | **134**, `FutureProofMessage` (`BD2`) | тот же паттерн универсального конверта, новое в этой сборке; вложенное содержимое не разрешено |
| Пак стикеров | `stickerPackMessage` | **86**, `StickerPackMessage` (`C30610DTe`) | делится/устанавливает пак (ZIP со стикерами) |
| Запрос синхронизации стикеров | `stickerSyncRmrMessage` | **47** (старые сборки) | **отсутствует** в прото `Message` в 2.26.41.6 (см. раздел 7) |
| Реакция-стикер статуса | `statusStickerInteractionMessage` | **110**, `StatusStickerInteractionMessage` (`C30560DRg`) | стикер-реакция на пост статуса; вне области этого отчёта, кроме этого упоминания |
| Добавление пака сторонним приложением | Android `Intent` | `com.whatsapp.intent.action.ENABLE_STICKER_PACK` | внешнее приложение просит WhatsApp импортировать пак, который оно хостит |
| Отправка сторонним приложением | Android `Intent` | `com.whatsapp.intent.action.SEND_STICKER` | внешнее приложение передаёт одиночный WebP-стикер в пикер WhatsApp |
| Контракт содержимого пака | `ContentProvider` (собственный, стороннего приложения) | `content://<authority>/metadata`, `/stickers`, `/stickers_asset` | как WhatsApp читает пак стороннего приложения |
| AI-генерация стикеров | `ContentProvider` (собственный, WhatsApp) | `content://com.whatsapp.provider.sticker_command/generate` | встроенное создание GenAI-стикеров в приложении, используется через вызовы content-provider, а не через сообщение чата |

Уровни достоверности следуют `IMPORTANT.md`: **found** = прочитано непосредственно в декомпилированном коде/строках/манифесте, **inferred** = выведено из структуры кода, **unknown** = не разрешено. Все доказательства здесь статические (декомпилированный APK + манифест); ничего не было захвачено на проводе.

---

## 2. `Message.StickerMessage` (поле 26)

### 2.1 Поля (found, `C30611DTf`)

| Поле | № | Тип | Использование |
|-------|---|------|-----|
| `url` | 1 | string | устаревший полный URL |
| `fileSha256` | 2 | bytes | хеш открытого текста |
| `fileEncSha256` | 3 | bytes | хеш шифротекста+MAC, также хеш пути загрузки |
| `mediaKey` | 4 | bytes | 32-байтовый ключ, HKDF info `WhatsApp Image Keys` (медиапайплайн, здесь не повторяется) |
| `mimetype` | 5 | string | `image/webp` для обычных стикеров |
| `height` / `width` | 6 / 7 | uint32 | пиксельные размеры |
| `directPath` | 8 | string | путь скачивания |
| `fileLength` | 9 | uint64 | длина шифротекста |
| `mediaKeyTimestamp` | 10 | int64 | секунды |
| `firstFrameLength` / `firstFrameSidecar` | 11 / 12 | uint32 / bytes | sidecar для первого кадра анимации (см. [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md), раздел 7) |
| `isAnimated` | 13 | bool | анимированный WebP |
| `pngThumbnail` | 16 | bytes | встроенная миниатюра |
| `contextInfo` | 17 | `ContextInfo` | метаданные цитаты/ответа/рекламы |
| `stickerSentTs` | 18 | int64 | временная метка отправки |
| `isAvatar` | 19 | bool | стикер-аватар |
| `isAiSticker` | 20 | bool | AI-сгенерированный стикер |
| `isLottie` | 21 | bool | нагрузка стикера — Lottie-анимация, а не обычный WebP (см. раздел 4) |
| `accessibilityLabel` | 22 | string | текст для экранного диктора |
| `premium` | 24 | int32 | не разрешено (потребитель не найден) |
| `emojis` | 25 | string | **найденное использование**: локальный тег поиска, см. раздел 9 |
| `audioMessage` | 26 | `AudioMessage` (`oneof audio`) | встроенный звуковой клип стикера, см. раздел 3 |

Пропуски номеров полей 14, 15, 23: нет заданного поля; прежнее использование неизвестно. Это исправляет исходную заметку `Messages/stickerMessage`, которая указывает `emojis` (25) как последнее поле и вовсе не содержит поле 26 (`audioMessage`) — подтверждённо присутствует в `C30611DTf` в 2.26.41.6 (`AUDIO_MESSAGE_FIELD_NUMBER = 26`) и совпадает с блоком `oneof audio` в текущем прото `baron-baileys-v2`.

### 2.2 Классификация по строке типа сообщения (found)

Наблюдаемые строки типа, привязанные к отправке `StickerMessage`/`StickerPackMessage`, собраны из диспетчера аналитики (`C21880sC`) и хелпера типа стикера: `sticker`, `avatar_sticker`, `genai_sticker`, `1p_sticker`, `user_created_sticker`, `sticker_pack`. `avatar_sticker` и `genai_sticker` берутся из `isAvatar`/`isAiSticker`; `1p_sticker` и `user_created_sticker` соответствуют перечислению `StickerPackOrigin` (раздел 5), но точная функция принятия решения, которая выбирает между `sticker`, `1p_sticker` и `user_created_sticker`, в этом проходе не выделена (приоритет неизвестен). Baileys (`messages-send.js`) проверяет `isLottie` перед `isAvatar` при выводе этой строки на стороне клиента; делает ли Android то же самое, не подтверждено.

### 2.3 `emojis` и `accessibilityLabel` (found, расширено по сравнению с исходным материалом)

- `emojis` (25): используется `EmojiGroupMapper`/`StickerSearchManager` как строка тега локального поиска — подтверждает её назначение сверх имени поля (раздел 9). Не запрашивается с сервера.
- `accessibilityLabel` на *отправленном стикере* и `sticker_accessibility_text` на *стикере стороннего пака* (`StickerContentProviderFetcher`, раздел 8) оба ограничены **125** символами для статического стикера и **250** для анимированного (`ThirdPartyStickerFetcher`, литералы 125/250; JADX неверно отображает ветку 125 как несвязанное поле `C30628DTw.SPLIT_PAYMENT_MESSAGE_FIELD_NUMBER`, потому что это поле также случайно содержит значение 125 — артефакт именования декомпилятора, само числовое значение считывается непосредственно из байт-кода).

---

## 3. Звуковые стикеры: `StickerMessage.audioMessage` и `audioStickerMessage` (134)

Два различных, найденных механизма, не путать их:

| Механизм | Поле | Доказательство |
|-----------|-------|----------|
| Встроенный клип | `StickerMessage.audioMessage` (26, `oneof audio`) | присутствует в `C30611DTf`; точно совпадает с `WAProto.proto` из `baron-baileys-v2` (`oneof audio { Message.AudioMessage audioMessage = 26; }`) |
| Отдельная обёртка | `Message.audioStickerMessage` (134, `FutureProofMessage`/`BD2`) | новое поле в `C30628DTw` для 2.26.41.6, отсутствует в исходном материале `Messages/`; тот же паттерн универсального конверта, что у `lottieStickerMessage` (раздел 1), вложенное содержимое неизвестно |

Клиентский пакет поддержки `com.whatsapp.stickers.sound` подтверждает функцию авторства «звукового стикера»: `StickerOpusEncoder` (`nativeEncode(short[] pcm, String outPath)`, native-кодирование Opus записанного клипа) и `SoundStickerAudioDownloader` (обеспечивает получение прикреплённого аудио перед воспроизведением, маршрутизирует через обычный медиапайплайн). Это согласуется со встраиванием короткой голосовой заметки через поле 26, а не (или вместе с) более новой обёрткой поля 134.

---

## 4. Форматы файлов стикеров

### 4.1 Обычный и анимированный WebP (found)

`mimetype = image/webp`; `isAnimated` помечает анимированный WebP. Декодирование проходит через изолированный (sandboxed) libwebp в `libstatic-webp.so` (см. [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md), раздел 15).

### 4.2 Lottie-стикеры — ZIP-контейнер `.was` (found, `LottieStickerZipEntrySaver` / `C161836tL`)

Когда установлен `isLottie`, медиафайл стикера не WebP: это ZIP-архив, сохраняемый и считываемый через `LottieStickerZipEntrySaver`, который должен содержать:

| Запись | Роль |
|-------|------|
| `animation/animation.json` | JSON-анимация Lottie (bodymovin), основная |
| `animation/animation.json.trust_token` | сопутствующий токен доверия/подписи для JSON |
| `animation/animation_secondary.json` + `.trust_token` | опциональный вторичный вариант анимации |

Общий экстрактор на уровне пака (`C161826tK`, лог-тег `StickerPackZipEntrySaver`, базовый класс `SafeZipEntrySaver`) дополнительно разрешает только расширения извлекаемых файлов `png`, `webp` и `was` — то есть публичное расширение файла `.was` («WhatsApp Animated Sticker») является маркером этого Lottie-контейнера на диске/в ZIP-записи, проверяемым против заявленного MIME (`application/was`) через сниффер содержимого перед принятием.

### 4.3 Лимиты извлечения ZIP пака (found, конструктор `C161826tK`)

| Лимит | Значение |
|-------|-------|
| Макс. количество записей в ZIP пака | **65** (жёстко задано) |
| Макс. байт на запись | токен словаря (ID флага **1900**, KB) × 1024 |
| Макс. суммарных байт на пак | тот же токен × 1024 × 65 |
| Обход пути (path traversal) | целевой путь каждой записи канонизируется и должен разрешаться внутри собственного каталога пака («Zip entry is attempting to save outside of current directory») до записи любого байта — защита от zip-slip |
| Отклонённая запись | удаляется после неуспешной проверки типа содержимого, логируется `StickerPackZipEntrySaver/file in zip is not valid` |

Это подтверждает и расширяет исходную заметку `Messages/stickerPackMessage` (которая цитировала «ZIP extraction and file validation» и «validates sticker files reside within extracted ZIP boundaries» из 2.26.34.4 только как ссылку на лог, без лимитов).

---

## 5. `Message.StickerPackMessage` (поле 86)

### 5.1 Поля (found, `C30610DTe`) — точно совпадают с исходным материалом и `baron-baileys-v2`

| Поле | № | Тип |
|-------|---|------|
| `stickerPackId` | 1 | string |
| `name` | 2 | string |
| `publisher` | 3 | string |
| `stickers` | 4 | repeated `Sticker` |
| `fileLength` / `fileSha256` / `fileEncSha256` / `mediaKey` / `directPath` / `mediaKeyTimestamp` | 5, 6, 7, 8, 9, 13 | ссылка на медиа ZIP пака (`MmsType` `sticker-pack`, HKDF info `WhatsApp Sticker Pack Keys`) |
| `caption` | 10 | string |
| `contextInfo` | 11 | `ContextInfo` |
| `packDescription` | 12 | string |
| `trayIconFileName` | 14 | string |
| `thumbnailDirectPath` / `thumbnailSha256` / `thumbnailEncSha256` / `thumbnailHeight` / `thumbnailWidth` | 15–19 | миниатюра пака (`MmsType` `thumbnail-sticker-pack`) |
| `imageDataHash` | 20 | string |
| `stickerPackSize` | 21 | uint64 |
| `stickerPackOrigin` | 22 | enum `StickerPackOrigin` |

Вложенный `Sticker`: `fileName` (1), `isAnimated` (2), `emojis` (3, repeated), `accessibilityLabel` (4), `isLottie` (5), `mimetype` (6), `premium` (7).

`StickerPackOrigin`: `FIRST_PARTY` = 0, `THIRD_PARTY` = 1, `USER_CREATED` = 2.

### 5.2 Локальное хранение (found, `AbstractC149676Ty.java`, `C1888782f.java`, `C0R5.java`)

| Таблица | Столбцы |
|-------|---------|
| `message_sticker_pack` | `message_row_id`, `sticker_pack_id`, `pack_name`, `pack_description`, `publisher`, `tray_icon_file_name`, `image_data_hash`, `sticker_pack_size`, `sticker_pack_origin`; индексирована по `pack_name` и `publisher` |
| `message_sticker_pack_stickers` | `_id`, `message_row_id`, `file_name`, `is_animated`, `emojis`, `accessibility_label`, `is_lottie`, `mimetype` |

Это заменяет указание исходного материала на версию 2.26.34.4 (`StickerPackMessageMapper` / `message_sticker_pack`, процитировано только по строке лога) конкретным списком столбцов для 2.26.41.6.

---

## 6. `stickerSyncRmrMessage` — подтверждённо отсутствует в 2.26.41.6

Поле 47 (`StickerSyncRMRMessage`: `filehash` repeated string, `rmrSource` string, `requestTimestamp` int64) **не** появляется в `C30628DTw` (контейнере `Message`) для 2.26.41.6: ни один номер поля 47 не сопоставлен с ним, и ни одного класса или строки, содержащей `StickerSyncRMR`/`stickerSyncRmr`, не существует нигде в декомпилированном дереве. Это совпадает с собственным наблюдением исходного материала о том, что поле уже отсутствовало в 2.26.36.1, и расширяет его — оно остаётся отсутствующим пятью сборками позже. По условиям доказательственного контракта это **наблюдаемое отсутствие**, а не подтверждённое удаление: было ли оно переименовано, перемещено в другой прото или полностью убрано — неизвестно.

Таблица, ключуемая по `filehash`, всё же существует, но для несвязанной цели: `RecentStickerDBStorage` (`C6VB`, `C17460jr`, `C6V8`) отслеживает локально отправленные/полученные стикеры по хешу файла для лотка недавних — это локальный учёт, а не сообщение синхронизации по проводу, и его не следует путать с ним.

---

## 7. API сторонних паков стикеров

Это публичная, документированная по соглашению поверхность интеграции (семейство прав доступа `com.whatsapp.sticker.READ`); всё нижеследующее найдено в `AndroidManifest.xml` и обслуживающих классах.

### 7.1 Поверхность манифеста

| Компонент | Декларация |
|-----------|-------------|
| Право доступа | `com.whatsapp.sticker.READ` — требуемое `android:readPermission` на собственном content-провайдере стороннего приложения, прежде чем WhatsApp его запросит |
| Activity добавления пака | `com.whatsapp.stickers.ui.thirdpartystickers.AddThirdPartyStickerPackActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.ENABLE_STICKER_PACK` + `category DEFAULT` |
| Устаревший алиас добавления пака | `activity-alias` `com.whatsapp.stickers.thirdpartystickers.AddThirdPartyStickerPackActivity` → та же цель (сохранён для приложений, собранных против имени пакета до рефакторинга) |
| Activity отправки одиночного стикера | `com.whatsapp.stickers.command.send.SendStickerCommandActivity`, `exported="true"`, intent-filter `action com.whatsapp.intent.action.SEND_STICKER` + `category DEFAULT` + `data mimeType="image/webp"` |
| Провайдер проверки белого списка | `com.whatsapp.provider.sticker_whitelist_check` → `WhitelistPackQueryContentProvider`, `exported="true"` |
| Deep link | `whatsapp://stickerpack` (`<data android:host="stickerpack" android:scheme="whatsapp"/>`); целевая activity/маршрутизация для этого конкретного хоста в этом проходе не выделена (неизвестно) |

### 7.2 Контракт интента `ENABLE_STICKER_PACK` (found, `AddThirdPartyStickerPackActivity`)

Extras запроса (`String`): `sticker_pack_id`, `sticker_pack_authority`, `sticker_pack_name`.

Проверка перед тем, как что-либо будет получено:
1. `getCallingActivity()` должен быть не null (интент должен приходить через `startActivityForResult`, а не через запуск в стиле простого broadcast).
2. `PackageManager.resolveContentProvider(sticker_pack_authority, …)` должен разрешиться до провайдера.
3. Пакет разрешённого провайдера должен совпадать с пакетом вызывающей activity — **приложение может ручаться только за принадлежащие ему authority**.

Extras результата в возвращённом `Intent` (один из): `add_successful=true`, `already_added=true`, `validation_error=<string>`, или `CancelReason.USER_CANCELLED=true` (пользователь отменил диалог добавления).

### 7.3 Контракт content-провайдера пака (found, `StickerContentProviderFetcher`/`C179697lN`, `C175327dG`)

WhatsApp читает пак стороннего приложения, запрашивая *собственный провайдер вызывающего приложения* по заданной authority, с проверкой `readPermission == "com.whatsapp.sticker.READ"` на этом провайдере:

| URI | Возвращаемые столбцы |
|-----|-------------------|
| `content://<authority>/metadata/<identifier>` | `sticker_pack_identifier`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_icon`, `android_play_store_link`, `ios_app_download_link`, `image_data_version`, `whatsapp_will_not_cache_stickers`, `animated_sticker_pack` |
| `content://<authority>/stickers/<identifier>` | `sticker_file_name`, `sticker_emoji`, `sticker_accessibility_text` |
| `content://<authority>/stickers_asset/<identifier>/<filename>` | открываемый поток (иконка лотка или отдельный файл стикера) |

Проверки, найденные в fetcher: `authority`/`identifier` отклоняют недопустимые символы; `identifier` ≤ 128 символов; возвращённый `sticker_pack_identifier` должен совпадать с запрошенным identifier; имя файла `sticker_pack_icon` ≤ 128 символов; `android_play_store_link` должен содержать `play.google.com`, `ios_app_download_link` должен содержать `itunes.apple.com` или `apps.apple.com`; `publisher`/`name` непусты и ≤ 128 символов; id `tray` непуст; количество стикеров должно попадать в диапазон `[flag 17124, flag 17327]` включительно (границы токена словаря, числовые значения в этом проходе не разрешены); каждый полученный ресурс стикера ограничен **~103424 байт (101 КБ)** для статического пака или **~512512 байт (500.5 КБ)** для анимированного (`Math.min(animated ? 500 : 100, 1024) + 1) * 1024`; слишком большие или нечитаемые потоки отбрасываются с файлом, установленным в null, а не прерывают весь пак. Соответствующий путь `app may have been deleted` / `third_party_sticker_app_deleted` обрабатывает исчезновение пакета провайдера в середине выборки.

Отдельный булев флаг (**13081**) управляет тем, повторно ли уже внесённый в белый список пак запрашивается у content-провайдера или обслуживается из кеша, а флаг **22198** переключается между старым синхронным диалог-ориентированным потоком добавления и прямой маршрутизацией на экран предпросмотра пака стикеров; флаг **13711** выбирает между двумя внутренними вариантами установки (`C175327dG.A00` против `A01`) при установке через путь ярлыка content-провайдера (раздел 7.5), а не через activity.

### 7.4 Контракт интента `SEND_STICKER` (found, `SendStickerCommandActivity`)

Данные: URI `content://` из собственного провайдера вызывающего приложения, чья authority должна разрешаться в тот же вызывающий пакет. Указанный файл должен декодироваться ровно как **512×512** WebP и быть ≤ **500000 байт**; клиент пересобирает его через обычный пайплайн стикеров (хеш, хранение, прикрепление) и добавляет следующие extras `Intent` как метаданные пака `Sticker`, если они присутствуют: `sticker_accessibility_text`, `sticker_pack_id`, `sticker_pack_name`, `sticker_pack_publisher`, `sticker_pack_ios_store_link`, `sticker_pack_play_store_link` (обе ссылки на магазины проверяются теми же проверками домена, что в разделе 7.3).

### 7.5 Провайдер проверки белого списка (found, `WhitelistPackQueryContentProvider`)

`content://com.whatsapp.provider.sticker_whitelist_check/<match>?authority=<pkg-authority>&identifier=<pack-id>` — курсор из одной строки и одного столбца (`result`, `0`/`1`), отвечающий на вопрос «этот пак уже добавлен». Проверка вызывающей стороны отражает 7.2: вызывающий пакет должен совпадать с пакетом, владеющим запрошенной `authority`. Тип MIME, возвращаемый `getType()`: `vnd.android.cursor.item/vnd.com.whatsapp.provider.sticker_whitelist_check.is_whitelisted`.

### 7.6 Внутренний провайдер команд стикеров (found, `StickerCommandProvider`, `com.whatsapp.provider.sticker_command`, `exported="true"`)

Не часть контракта сторонних приложений выше — это собственный провайдер WhatsApp, запрашиваемый собственными UI/ассистент-поверхностями WhatsApp, с диспетчеризацией по последнему сегменту пути URI:

| Путь | Поведение |
|------|----------|
| `installPack?authority=&identifier=` | устанавливает пак через тот же путь выборки/проверки `C175327dG`, что в разделе 7.3, минуя UI activity |
| `removePack?authority=&identifier=` | удаляет ранее добавленный пак |
| `generate?prompt=` | AI-генерация стикеров (раздел 8); длина prompt должна быть 3–200 символов после обрезки пробелов |
| `availability` | возвращает `{available, consent_required}` для AI-генерации стикеров |
| `image/<token>` (через `openFile`) | передаёт обратно сгенерированный PNG/WebP стикера по непрозрачному токену, MIME `image/webp` |

---

## 8. AI-сгенерированные стикеры (found, `AiStickerCommands`, `StickerCommandProvider`)

`isAiSticker` (поле 20) помечает `StickerMessage` как AI-сгенерированный; строка типа — `genai_sticker` (раздел 2.2). Сама генерация запускается локальным UI через путь провайдера `generate` (7.6): перед любым вызовом генерации проверяются шлюзы права (`C174467bs.A00`) и согласия (`A02`); результаты возвращаются как список непрозрачных `token`, позже разрешаемых через `image/<token>`. Фактический backend генерации (на устройстве или на сервере) из этого пути кода неизвестен — разрешена только клиентская сантехника прав/согласия/токенов.

---

## 9. Поиск стикеров (found, `StickerSearchManager`, `EmojiGroupMapper`, пакет контекстных предложений)

Полностью локальный, не серверный запрос. `StickerSearchManager.A00` берёт свободнотекстовый запрос, разрешает его в набор символов эмодзи через `EmojiGroupMapper`, объединяет их в строку через пробел и сопоставляет эту строку с **локально хранимым** полем `emojis` каждого `StickerMessage`/пакового `Sticker` (раздел 2.3) плюс недавно использованными/избранными кандидатами, разбивая результаты на корзины «точное совпадение эмодзи» и «прочее» и урезая до лимита результатов из токена словаря (флаг **22573**). Флаг `includeAvatarResults` отдельно управляет тем, участвуют ли стикеры-аватары, за собственной проверкой доступности. Это подтверждает — и повышает с «может содержать… неизвестно» до found — что строковое поле `emojis` прото является клиентским индексным ключом поиска, а не тегом только для отображения.

---

## 10. Шифрование медиа (ссылка, не повторяется)

Каждая медиа-ссылка со стикером (`stickerMessage`, `stickerPackMessage`, их миниатюры) проходит через тот же идентичный медиапайплайн, документированный в [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md): 32-байтовый случайный медиа-ключ, HKDF-80 (`WhatsApp Image Keys` для `sticker`, `WhatsApp Sticker Pack Keys` для `sticker-pack`, `WhatsApp Sticker Pack Thumbnail Keys` для миниатюры пака, обработка в стиле `WhatsApp Image Thumbnail Keys` здесь не используется — у миниатюр стикера и пака свои собственные выделенные info-строки), AES-CBC + усечённый до 10 байт HMAC-SHA256, `fileSha256`/`fileEncSha256`, хосты, выдаваемые `media_conn`, и форма URL загрузки `/mms/<type>/<hash>`. Ничего специфичного для стикеров не меняет что-либо из этого; см. разделы 2–9 того отчёта для полных таблиц вывода, повторов и кодов ошибок.

---

## 11. Флаги функций (id как считаны в точках вызова; имена не разрешены)

| Флаг | Где | Управляет |
|------|-------|----------|
| **1900** | конструктор `C161826tK` | бюджет размера извлечения ZIP пака на запись и суммарный (KB) |
| **13081** | `AddThirdPartyStickerPackActivity` | повторная выборка против кеша для уже внесённого в белый список пака стороннего приложения |
| **13711** | `StickerCommandProvider`, `AddThirdPartyStickerPackActivity` | выбирает вариант пути установки (`C175327dG.A00` против `A01`) |
| **17124** / **17327** | `StickerContentProviderFetcher` | мин. / макс. количество стикеров, принимаемое от стороннего пака |
| **22198** | `AddThirdPartyStickerPackActivity` | асинхронный диалог-ориентированный поток добавления против прямой маршрутизации на экран предпросмотра |
| **22573** | `StickerSearchManager` | лимит результатов локального поиска |

---

## 12. Baileys (`baron-baileys-v2`, исходный код прочитан, ничего не тестировалось)

| Аспект | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Поля `Message.StickerMessage` | идентичный набор полей, включая `audioMessage` (26, `oneof audio`) — исходный код прото точно совпадает с декомпилированной раскладкой 2.26.41.6 поле за полем | то же (раздел 2.1) |
| Поля `Message.StickerPackMessage` | идентичный набор полей (1–22) | то же (раздел 5.1) |
| Отправка стикера | `prepareWAMessageMedia({ sticker })` строит `stickerMessage` через общий путь подготовки медиа (`MmsType` `sticker`, HKDF info Image); опция `stickerAudio` прикрепляет подготовленный `audioMessage` к `m.stickerMessage.audioMessage` | тот же медиапайплайн согласно [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md), раздел 17 |
| Отправка пака | ввод `stickerPackMessage`/`stickerPack` пропускается через `StickerPackMessage.fromObject` без дополнительной проверки | клиент дополнительно проверяет через ZIP-экстрактор и ограничения БД (разделы 5, 6), прежде чем принять пак, который строит сам |
| Декодирование | `decode-wa-message.js` сопоставляет `isAvatar`→`avatar_sticker`, `isAiSticker`/`isGenAI`→`genai_sticker`; `messages-send.js` сопоставляет `isLottie`→`1p_sticker` перед `isAvatar`/обычным `sticker` при выводе исходящей строки типа | те же три строки типа сообщения найдены в диспетчере аналитики Android (`avatar_sticker`, `genai_sticker`, плюс `1p_sticker`/`user_created_sticker`); точный порядок приоритета Android не подтверждён (раздел 2.2) |
| Интенты/провайдеры сторонних паков | не реализовано — у Baileys нет поверхности Android `Intent`/`ContentProvider` | полная поверхность, раздел 7 |
| Обёртки `lottieStickerMessage` / `audioStickerMessage` | присутствуют только как обычное поле `FutureProofMessage` в прото; выделенный путь кодирования/декодирования не найден | тот же обычный конверт, обработка, специфичная для поля, тоже не найдена (раздел 3) |

---

## 13. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|---------|-----|
| `ENABLE_STICKER_PACK` возвращает `validation_error` «cannot find the provider for authority» | строка `authority` стороннего приложения не разрешается ни к одному установленному провайдеру | приложение-издатель пака стикеров должно объявить и экспортировать свой провайдер под этой точной authority |
| `ENABLE_STICKER_PACK` возвращает «does not own authority» | вызывающий пакет отличается от пакета разрешённого провайдера | приложение может ручаться только за authority внутри собственного пакета |
| Добавление пака тихо завершается с «sticker count should be between X and Y» | запрос `stickers` пака вернул количество строк вне `[flag 17124, flag 17327]` | держать курсор `/stickers/<id>` стороннего приложения в пределах, заданных сервером |
| `SafeZipEntrySaver: File being unzipped is too big` / «Too many files to unzip» | ZIP пака превышает бюджет байт на запись/суммарный или лимит 65 записей | уменьшить пак или разделить стикеры на несколько паков |
| `tray image name invalid` / ошибка длины имени | `sticker_pack_icon` стороннего приложения содержит недопустимые символы или превышает 128 символов | санитизировать и сократить имя файла лотка |
| `StickerPackZipEntrySaver/file in zip is not valid` | тип содержимого, определённый сниффером у извлечённой записи, не совпадает с заявленным расширением/MIME | поставлять записи, чьи байты действительно соответствуют `png`/`webp`/`was` |
| `the sticker is not a 512px WebP` (`SEND_STICKER`) | изображение интента одиночного стикера не ровно 512×512 | изменить размер перед отправкой интента |

---

## 14. Ключевые различия

| Не путать | Факт |
|----------------|------|
| `StickerMessage.audioMessage` (поле 26) против `Message.audioStickerMessage` (поле 134) | первое — подтверждённый встроенный `AudioMessage` внутри отправки стикера; второе — отдельное, пока непрозрачное верхнеуровневое поле-обёртка, новое в этой сборке |
| `isLottie` (флаг на стикер) против `Message.lottieStickerMessage` (поле 74, обёртка) | флаг привязан к конкретному найденному формату файла (ZIP `.was` с `animation/animation.json`); вложенная нагрузка поля-обёртки ещё не разрешена — не показано, что это один и тот же механизм |
| `stickerSyncRmrMessage` (сообщение по проводу, отсутствует) против `RecentStickerDBStorage` (локальная таблица, ключуемая по `filehash`) | первое больше не существует на проводе в этой сборке; второе — несвязанный локальный учёт, который случайно также ключуется по хешу файла |
| Контракт стороннего пака (разделы 7.2–7.5, провайдер внешнего приложения) против `StickerCommandProvider` (раздел 7.6, собственный провайдер WhatsApp) | оба умеют «устанавливать пак по authority+identifier», но первое — это WhatsApp, *читающий провайдер другого приложения*, второе — внутренний ярлык WhatsApp вокруг собственного UI activity |
| AI-генерация стикеров (`isAiSticker`, локальный поток GenAI) против сторонних AI/приложений стикеров | первое — собственная встроенная функция WhatsApp за `StickerCommandProvider`; она не имеет ничего общего с контрактом content-провайдера сторонних приложений |

---

## 15. Поток: добавление стороннего пака стикеров

```
[Third-party app]  exports ContentProvider at authority X, readPermission=com.whatsapp.sticker.READ
     │  startActivityForResult(ACTION_ENABLE_STICKER_PACK, extras: sticker_pack_id, sticker_pack_authority=X, sticker_pack_name)
     ▼
[AddThirdPartyStickerPackActivity]  getCallingActivity() != null?
     │  resolveContentProvider(X) exists?  calling package == provider's package?
     ▼  (all pass)
[StickerContentProviderFetcher]  query content://X/metadata/<id>
     │  validate identifier echo, name/publisher length, tray icon name, store links
     ▼
[StickerContentProviderFetcher]  query content://X/stickers/<id>  (sticker_file_name, sticker_emoji, sticker_accessibility_text)
     │  validate count in [flag 17124, flag 17327], accessibility text ≤ 125/250 chars
     ▼
[StickerContentProviderFetcher]  openInputStream content://X/stickers_asset/<id>/<file>  per sticker + tray icon
     │  cap ~101 KB (static) / ~500.5 KB (animated) per asset
     ▼
[Client]  store pack + stickers, mark whitelisted (ThirdPartyWhitelistedPacksStore)
     │
     ▼
[AddThirdPartyStickerPackActivity]  result Intent: add_successful=true | already_added=true | validation_error=<reason>
     │
     ▼
[Third-party app]  onActivityResult()
```

---

## 16. Неизвестные

| Пункт | Статус |
|------|--------|
| Вложенная нагрузка `lottieStickerMessage` (74) и `audioStickerMessage` (134) | поле существует, обычная обёртка `FutureProofMessage`, содержимое не разрешено |
| Точный приоритет Android для строк типа `sticker` против `1p_sticker` против `user_created_sticker` | найдено только сопоставление байт-кода аналитики, не функция выбора |
| Поле `premium` (24) на `StickerMessage`/`Sticker` | потребитель не найден |
| Числовые значения за флагами-токенами словаря 1900, 17124, 17327, 22573 | id токенов найдены, актуальные значения статически не разрешены |
| Целевая activity deep-link `whatsapp://stickerpack` | хост объявлен в общем deep-link intent-filter манифеста; какой внутренний экран его потребляет, не выделено |
| Backend AI-генерации стикеров (на устройстве или на сервере) | разрешена только клиентская сантехника права/согласия/токенов |
| Применяет ли сервер собственные лимиты размера/количества пака сверх клиентских | на стороне сервера, неизвестно |
| Судьба `stickerSyncRmrMessage` (переименовано, перемещено или убрано) | подтверждённо отсутствует в прото по проводу с 2.26.36.1 по 2.26.41.6; удаление не подтверждено |
| Трафик | ничего не захвачено; динамического теста не было |
