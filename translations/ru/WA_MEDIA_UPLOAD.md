<!-- src-sha1: a12736ca9c475f1c7c0195dbae0d18d5725a4440 -->
# WhatsApp Загрузка медиа — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** передача медиа на Android: IQ `media_conn` (хосты, авторизация, ttl, бакеты, резервные хосты), построение URL для загрузки и скачивания и HTTP-параметры, таблица типов медиа со строками HKDF info, генерация и вывод медиа-ключа, шифрование AES-CBC + HMAC, fileSha256 / fileEncSha256, mediaKeyTimestamp, прямой путь (direct path), миниатюры, потоковые sidecar для видео / аудио / прогрессивных изображений, докачиваемая загрузка, выбор маршрута, повторные попытки и backoff, коды ошибок загрузки и скачивания, квитанция media retry и уведомление `mediaretry`, медиа однократного просмотра и статусов, медиа канала (newsletter), express-путь, клиентская нативная защита парсеров медиа, сравнение с Baileys

---

## 1. Что это (технически)

Медиа никогда не передаётся внутри потока chatd (см. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Сообщение несёт только protobuf-ссылку (ключ, хэши, `directPath`); сами байты идут по отдельным HTTPS-соединениям к медиа-хостам. Chatd предоставляет одну вещь: IQ `media_conn`, который выдаёт имена хостов и короткоживущий токен авторизации загрузки. Все утверждения получены из статического анализа декомпилированного APK и распакованных нативных библиотек; ничего не было захвачено по протоколу. Уровни: **found** = прочитано в коде или строках, **inferred** = выведено, **unknown** = не разрешено.

| Слой | Имя в 2.26.41.6 | Роль |
|-------|----------------|------|
| Селектор маршрута | `RouteSelector` (`C10950Wx`) | хранит текущий результат `media_conn`, таймер обновления, throttle, фабрику маршрутов |
| Парсер `media_conn` | `C43951qe` (обработчик результата IQ), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | разбирает `<media_conn>` / `<host>` |
| Поставщик маршрута | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (статические поставщики) | выбирает хост на попытку, меняет токен авторизации |
| Драйвер повторов | `TransferRetries` (`C44566Jd2`) | цикл попыток вокруг одной передачи |
| Таблица типов медиа | `MmsType` (`C15530gU`) | на тип: строка пути, байты HKDF info, числовой id |
| Поставщик ключа | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF 80 байт, ключ домена не-E2EE |
| Потоки шифра | `M2I` (шифрование на выход), `M23` (шифрование на вход), `P9N` / `P1X` / `P1Y` (MAC-коды sidecar), `C51101MlN` (расшифровка по диапазону) | AES-CBC + HMAC |
| Драйвер загрузки | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (повторное использование ключа), `C57333Po0` (генерация ключа + хэши) | хэши, sidecar, оркестровка загрузки |
| URL загрузки | `C43489Iy4` | `/surface/type/hash?...` |
| URL скачивания | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) загрузка; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) скачивание | транспорт |
| Зонд докачки | `HttpResumeCheck` (`C59524QnW`) | спрашивает сервер, сколько байт у него уже есть |
| Квитанция повтора | `SendMediaErrorReceiptJob`, writer-кейсы 77 и 327 в `HandlerThreadC21920sG` | запрос повторной загрузки от отправителя |
| Уведомление повтора | `MediaRetryNotificationHandler` (`C1S0`, код уведомления 97) | обрабатывает ответ |
| Нативное | `libwhatsapp.so` (Rust-крейты для медиа, песочницы RLBox), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | парсеры и декодеры |

Моменты, определяющие остальную часть отчёта:

- Android выводит **80** байт из медиа-ключа (IV 16, ключ шифра 32, MAC-ключ 32), не 112 (раздел 4).
- HTTP-путь — `/{surface}/{type}/{urlSafeFileEncSha256}`, где `type` — строка `MmsType` медиа (`image`, `ptt`, `md-msg-hist`, ...), не грубый класс (раздел 8.1).
- Android-`token` загрузки — это не хэш файла; это SHA-256 от секрета, привязанного к инсталляции, и хэша файла (раздел 8.2).
- Медиа канала (newsletter) использует тот же код, но поверхность (surface) `newsletter` и случайный токен; оно не зашифровано (found для пути artwork, inferred для остального, раздел 13).
- Хосты скачивания фильтруются по бакету, выводимому из хэша файла (раздел 9.2).

---

## 2. IQ `media_conn`

### 2.1 Запрос (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Таймаут 32000 мс. Одновременно выполняется только один запрос (`inFlightMediaRoutingRequestTime`); второй вызов логирует `not sending request` и завершается. Глобальный throttle (`ChatdMediaThrottleManager`) может подавить вызов (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Ответ (found, `C43951qe.CFS`)

| Узел / атрибут | Тип | Использование |
|------------------|------|-----|
| `media_conn@auth` | строка, обязателен | токен авторизации загрузки (параметр запроса `auth`) |
| `@ttl` | секунды | срок жизни соединения; истечение = время отправки + ttl * 1000 |
| `@auth_ttl` | секунды | срок жизни токена авторизации; истечение = время отправки + auth_ttl * 1000 |
| `@max_buckets` | long, по умолчанию 0 | модуль для бакета скачивания (раздел 9.2) |
| `@is_new` | int, по умолчанию 1 | 1 = заменить список хостов; иначе сохранить предыдущие хосты и взять только токен и ttl (`previous hosts retained`) |
| `@id` | строка | сохраняется как `last_id`, отправляется обратно в следующем запросе |
| `@max_auto_download_retry` | int, по умолчанию 3 | бюджет повторов для автоматических скачиваний |
| `@max_manual_retry` | int, по умолчанию 3 | бюджет повторов для ручных скачиваний |
| `@ip_token`, `@set_ip_token` | строка, "0"/"1" | разбирается и кэшируется; `ip_token` используется только когда флаг **12149** включён и `set_ip_token` истинен (место использования: unknown) |
| `host` (повторяется) | узел | одна запись маршрута |

Атрибуты `host` (found): `hostname` (обязателен), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` или `fallback`; что-либо иное становится `primary`), `force_ip` (`"true"`). Дочерние элементы: `<upload>`, `<download>`, `<download_buckets>`; имена дочерних тегов — это записи возможностей. `upload` и `download` сохраняют только теги, входящие в фиксированный набор из 34 строк типов медиа (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, семья `newsletter-*`, и семья `thumbnail-*`); `download_buckets` хранится без фильтрации.

Хост маршрута пригоден к использованию только если его hostname заканчивается на `.whatsapp.net` (`Mms4RouteSupplier.A06`, применяется также к `fallback_hostname`).

### 2.3 Кэширование и обновление (found)

| Правило | Значение |
|------|-------|
| Сохранение | при флаге **149** результат хранится как JSON (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) под `route_selector_prefs` / `media_conn`; загружается один раз, используется только если авторизация ещё не истекла |
| Проверка обновления | перед передачей: если соединение или авторизация истекают в пределах 120000 мс, отправляется новый IQ и ожидание до 20000 мс (`requestroutesandwaitforauth`) |
| Таймер | `истечение auth - 60000 мс` после каждого результата; возврат на передний план (`BgG`) переустанавливает его |
| Сбой авторизации | HTTP 401 или 403 во время передачи запускает обновление (`onmediatransfererrororresponsecode`), максимум 2 смены токена за передачу (`JW1.A00 < 2`), затем попытка повторяется с новым `auth` |
| Авторизация перед попыткой | `refreshAuthBeforeAttempt` подменяет на более новый токен, когда кэшированный истекает в пределах 120000 мс (символ флага `PTU.A0D`) |

### 2.4 Ошибка IQ (found, `C43951qe.Brt`)

`<error code backoff>` внутри результата IQ:

| Код | Поведение |
|------|-----------|
| 503 | сброс throttle медиа; следующее обновление планируется после Фибоначчиева backoff с джиттером (`3/4 * t + rand(t/2)`) |
| 507 с backoff > 0 | throttle запросов медиа до `сейчас + min(backoff, 10800) с` |
| другое / 0 | игнорируется |

---

## 3. Типы медиа и строки HKDF info (found, статическая инициализация `MmsType` `C15530gU`)

Каждый `MmsType` хранит строку пути (`A02`), короткую метку типа файла (`A01`, например `IMG`), байты HKDF `info` (`A03`) и числовой id (`A00`). Байты `info` используются напрямую как HKDF info (без дополнительного префикса).

| HKDF info | Строки пути `MmsType` |
|-----------|------------------------|
| `WhatsApp Image Keys` | `image`, `sticker`, `kyc-id`, `biz-cover-photo`, `biz-flows`, `wamo-image`, `newsletter-image`, `newsletter-image-status`, `newsletter-sticker`, `newsletter-music-artwork` |
| `WhatsApp Video Keys` | `video`, `ptv`, `gif`, `wamo-video`, `newsletter-video`, `newsletter-video-status`, `newsletter-ptv`, `newsletter-gif`, `newsletter-gif-status` |
| `WhatsApp Audio Keys` | `audio`, `ptt`, `newsletter-audio`, `newsletter-audio-status`, `newsletter-ptt` |
| `WhatsApp Document Keys` | `document`, `biz-flows`, `maiba-file`, `db`, `newsletter-document` |
| `WhatsApp Image Thumbnail Keys` | `thumbnail-image`, `newsletter-thumbnail-image`, `newsletter-thumbnail-status` |
| `WhatsApp Video Thumbnail Keys` | `thumbnail-video`, `thumbnail-gif`, `newsletter-thumbnail-video` |
| `WhatsApp Document Thumbnail Keys` | `thumbnail-document` |
| `WhatsApp Link Thumbnail Keys` | `thumbnail-link`, `newsletter-thumbnail-link` |
| `WhatsApp Chat Wallpaper Keys` | `chat-wallpaper-image` |
| `WhatsApp App State Keys` | `md-app-state` |
| `WhatsApp History Keys` | `md-msg-hist` |
| `Group History` | `group-history` |
| `WhatsApp Sticker Pack Keys` | `sticker-pack`, `newsletter-sticker-pack` |
| `WhatsApp Sticker Pack Thumbnail Keys` | `thumbnail-sticker-pack`, `newsletter-thumbnail-sticker-pack` |
| `WhatsApp Payment Background Keys` | `payment-bg-image` |
| `WhatsApp Music Artwork Keys` | `music-artwork` |
| `waffle_hkdf_info` | `waffle-image`, `waffle-video`, `waffle-gif` |
| `PAYMENT_DOC_UPLOAD` | `payment-br-document` |
| `ads-image` / `ads-video` | `ads-image` / `ads-video` |

Примечания (found): `ptt` и `audio` делят Audio info, но являются разными строками пути; `sticker` использует Image info; `gif` и `ptv` используют Video info; существуют несколько строк `image` с разными числовыми id (1, 23, 25, 37, 42, 44, 57; `sticker` — 20) для разных точек вызова (значение id неизвестно); `group-history` — единственная запись, чей info не имеет формы `WhatsApp <X> Keys`. Фото профиля (`ppic`) появляется только в наборе возможностей маршрута и в вызовах генератора скачивания, не как `MmsType`.

---

## 4. Медиа-ключ и его вывод

### 4.1 Генерация ключа (found)

| Элемент | Значение |
|------|-------|
| Медиа-ключ | 32 случайных байта из `SecureRandom` (`C57333Po0`, `QIh.A0B` — это `new SecureRandom()`) |
| Повторное использование | `MediaKeyGen/reuse key from message contents`, когда ключ моложе `172800000 мс + SecureRandom.nextInt(86400000)` (2-3 дня, с джиттером), измеряется относительно сохранённой метки времени ключа; более старые ключи отбрасываются (`key expired`) и регенерируются |
| Домен | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `AbstractC38961i0.A00`, вызывается `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01` отклоняет любую другую длину (`Invalid length of derived secret`). Длина шифротекста: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (блоки с PKCS#5-дополнением плюс 10 байт MAC).

### 4.3 Медиа-ключ не-E2EE (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (поле **74**, сообщение `DQT`) несёт `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) и `e2eeMediaKey` (**2**). При флаге **24661** получатель проверяет, что ключ в сообщении соответствует домену (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); при несовпадении он откатывается к переданному ключу. Какие продукты используют домен NON_E2EE: unknown.

---

## 5. Шифрование, MAC и хэши

### 5.1 Шифр (found, `M2I`, `M23`, `N6U`)

| Шаг | Детали |
|------|--------|
| Шифр | `AES/CBC/PKCS5Padding`, ключ = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, обновляется сначала IV, затем каждым байтом шифротекста; первые **10** байт дайджеста добавляются к шифротексту |
| `fileSha256` | SHA-256 над открытым текстом (потоковый дайджест `P9M` по файлу) |
| `fileEncSha256` | SHA-256 над шифротекстом + 10 байт MAC |
| Вывод | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Сторона расшифровки (`P9N`, `M23`): MAC проверяется над IV + шифротекстом, затем сравнивается с завершающими 10 байтами. Расшифровка по диапазону (`C51101MlN`): когда начало диапазона не 0, первые прочитанные 16 байт используются как IV (предыдущий блок шифротекста); внутренние куски используют `AES/CBC/NoPadding`, последний кусок использует PKCS#5 (выведено из выбора шифра).

### 5.2 Метки времени и пути

| Поле | Значение |
|-------|-------|
| `mediaKeyTimestamp` | локальные часы в миллисекундах, хранятся в объекте ключа, записываются в protobuf в секундах (`C20H.A06` = `/1000`) |
| `directPath` | строка пути, возвращённая сервером, хранится в сообщении и в столбце БД `direct_path`; может нести параметры запроса (например, `_nc_hot` считывается из него) |
| `url` | устаревшее поле полного URL; всё ещё присутствует в proto-классах и в ответе загрузки, но генератор скачивания строится из `directPath` или из хэша (раздел 9.1) |

### 5.3 Оптимистичные проверки хэша

`MediaUpload/optimistic-hash-fail` и `optimistic-plaintext-hash-fail` (результат загрузки 12) логируются, когда хэш, который сообщает сервер, отличается от локально вычисленного. Оптимистичная загрузка (строка поверхности `optimistic`) загружает до того, как отправка подтверждена; её протокол сверх имени поверхности: unknown.

---

## 6. Поля сообщения с медиа

Номера полей считаны из сгенерированных protobuf-классов. Имена классов сопоставлены по раскладке полей (inferred); номера — found.

| Сообщение (класс) | Номера полей (имя = номер) |
|-----------------|-------------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| History bundle (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

Контейнер `Message` (`C30628DTw`), номера (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage` — поле **21** контейнера `BD3`.

### 6.1 Миниатюры

| Вид | Механизм (found, если не отмечено иначе) |
|------|---------------------------------|
| Встроенная | байты `jpegThumbnail` (**16**) в сообщении (изображение, видео, документ); `pngThumbnail` (**16**) в стикерах |
| Загруженная | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (изображение **26-28**, видео **21-23**, документ **13-15**); `MmsType` `thumbnail-*` со значениями Thumbnail HKDF info из раздела 3 |
| Ключ | у proto нет отдельного поля ключа миниатюры, так что миниатюра шифруется медиа-ключом своего сообщения (inferred) |
| Созданная сервером | параметр запроса загрузки `server_thumb_gen=1`; ответ загрузки может вернуть `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` |
| БД | таблица `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Потоковая передача и sidecar (found)

Sidecar — это список 10-байтных MAC-кодов, один на каждый кусок шифротекста, позволяющий плееру проверить диапазон без чтения всего файла.

| Элемент | Детали |
|------|--------|
| Алгоритм | `P9N.read`: на каждый кусок `HmacSHA256(macKey)` инициализируется **предыдущими 16 байтами шифротекста** (IV для первого куска), получает кусок, и первые 10 байт дайджеста сохраняются |
| Конкатенация | `C57228PmG.A00` объединяет все 10-байтные MAC-коды в один массив байтов |
| Видео / аудио | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); размер куска **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Прогрессивное изображение | `firstScanSidecar` (**18**) с `firstScanLength` (**19**): один кусок размером `ceil(len/16)*16` байт; `scansSidecar` (**21**) с `scanLengths` (**22**): куски переменного размера (`P1Y`) |
| Стикер | `firstFrameSidecar` (**12**) с `firstFrameLength` (**11**) |
| Настройки | серверное свойство `streaming_upload_chunk_size` — токен справочника; его эффект: unknown |
| Отсутствует | статус скачивания 30 `failed_no_sidecar` |
| Серверная потоковая передача | параметры запроса загрузки `stream=1` и `streaming=riff` вместе (раздел 8.1); DASH: `dashManifestUrl` (**33**), `metadataUrl` (**30**) в ответе |

---

## 8. Загрузка

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Часть | Значение |
|------|------|
| `surface` | `mms` (обычная), `newsletter` (каналы), `optimistic` (загрузка до отправки); `AbstractC58025Pzy` |
| `type` | строка пути `MmsType` (раздел 3), например `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | стандартный base64 от `fileEncSha256` с заменой `+` на `-` и `/` на `_`; дополнение `=` сохраняется (`StringUtils.A0B`) |
| `direct_ip` | 1, когда authority — IP (`ip4`, или в скобках `[ip6]`), иначе 0 |
| `auth` | токен авторизации `media_conn`; добавляется как параметр запроса `K19.A03` |
| `stream=1`, `streaming=riff` | оба устанавливаются, когда запрос — потоковая загрузка (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | только для `newsletter-image` / `-status` (флаг **11191**) и `newsletter-video` / `-status` (флаг **11192**) |
| `server_transcode=1` | `newsletter-video` с id запроса 10 и флагом **9096** |
| `_nc_rmr=1` | загрузки не для newsletter (флаг запроса `A0N`) |
| `_nc_cbep=1` | когда запрос это позволяет и флаг **17404** включён (значение неизвестно) |
| `type`, `media_id`, `media_id_upload` | `media_id` = наиболее значимые 63 бита UUID загрузки; `media_id_upload` = наименее значимые 63 бита, только когда у запроса есть дополнительные записи; `type` — строка вызывающей стороны (значение: unknown) |

Значение имён запросов `_nc_cbep` и `_nc_rmr` неизвестно (только имена).

### 8.2 Токен (found, `C43489Iy4.A00`)

| Случай | Токен |
|------|------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`, свежий на каждый запрос, не привязан к файлу |
| Прочее | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` — 32 байта из `SecureRandom`, создаётся один раз и хранится в настройках как `upload_token_random_bytes` (base64 без переноса строк, без дополнения) |

Если `fileEncSha256` не может быть декодирован, токен — это просто `SHA-256(installSecret)`. Назначение конструкции: предполагается как серверная проверка того, что загружающий знает хэш, без раскрытия его в пути.

### 8.3 HTTP-запрос (found, `HttpsFormPost` `C43478Ixt`)

| Элемент | Значение |
|------|------|
| Библиотека | `HttpsURLConnection` с собственным `SSLSocketFactory`; маркер `http_stack = HttpUrlConnection` |
| Метод | POST (`setDoOutput(true)` на `HttpURLConnection`; явного вызова метода нет) |
| Таймауты | подключение 15000 мс, чтение 60000 мс |
| Заголовки | `Host: <route hostname>` (authority может быть IP), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, опциональный `Companion_User_Secret` (необязательный non-null аргумент конструктора; семантика companion предполагается) |
| Тело (маршрут присутствует) | сырой поток шифротекста, только один файл (`MMS4 upload only supports a single file`); режим потоковой передачи фиксированной длины, когда длина известна, иначе chunked (`setChunkedStreamingMode(0)`); буфер 16384 байт |
| Тело (маршрута нет) | устаревший `multipart/form-data` с частями `Content-Disposition: form-data` |
| Прерывание | при прерывании потока или флаге отмены поток дополняется (`UploadRequest/Post streaming padding bytes=`), чтобы заявленная длина была завершена (назначение предполагается) |
| Ответ | читается до 1 МиБ; HTTP >= 400 возвращает код, тело идёт в `onError` |

### 8.4 Ответ (found, `MediaUploadTransfer` `C59523QnV`)

Считываемые ключи JSON: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (принимается только если соответствует `[A-Za-z0-9-]{1,64}`), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (вложенная строка JSON с `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. Ответ без `direct_path` этим парсером не считается ошибкой; более поздние стадии завершаются с `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Докачиваемая загрузка (found)

| Шаг | Детали |
|------|--------|
| Зонд | тот же URL загрузки плюс `resume=1` (`HttpResumeCheck`); JSON-ответ `{"resume": "complete"}` с `url`, `direct_path` (уже загружено) или `{"resume": <offset>}` |
| Продолжение | POST с `Content-Range: bytes <offset>-*/*`, поток сначала перематывается к `<offset>` |
| Резервные варианты | `ResumeCheck/attempting fallback MMS upload form post`, также после ошибки WATLS (TLS) |
| Ошибка разбора | статус `PBY.A03`, загрузка перезапускается |

### 8.6 Поставщик маршрута и повторы (found, `Mms4RouteSupplier`, `TransferRetries`)

| Правило | Детали |
|------|--------|
| Цикл попыток | `TransferRetries/run attempt = N; route = ...`; одна передача на маршрут; `no routes` завершает цикл |
| Выбор хоста | хост `type=primary`, в чьём наборе возможностей есть тип медиа; первые две попытки используют его; последующие попытки используют запись `type=fallback` и её поля `fallback_*` (порядок выведен из искажённого потока управления) |
| Попытки | по умолчанию 4 (`4 - extra`); с флагами **12545** и **12446** лимит может быть переопределён после попытки 3; `max_auto_download_retry` / `max_manual_retry` (по умолчанию по 3) питают зависящий от режима счётчик (сопоставление выведено) |
| Задержка | константа 1000 мс (`RouteSelector.A01`); с флагом **257** и дополнительными попытками, экспоненциальная: база 1000 мс, `2^n`, джиттер, ограничена 3000 мс |
| Ошибка авторизации 401 / 403 | не считается сбоем: ожидание более нового токена (бюджет `A0J`, по умолчанию 20000 мс), замена, повтор |
| Статус HTTP, подлежащий повтору | `QKS.A08`: < 400 да; 400-499 нет, за исключением 408 при флаге **13748**; >= 500 да, за исключением 505 и 507 |
| Прокси | при пользовательском прокси и флаге **4073** authority медиа становится хостом и портом прокси из `proxy_media_port` (по умолчанию 587) |
| Проверка здоровья | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, подключение 15000 мс, чтение 30000 мс |

---

## 9. Скачивание

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

Конструктору требуется хэш медиа, прямой путь или перекрёстная ссылка (`media hash, direct path, or cross reference is required`). `mode` — это `auto` или `manual`. `_nc_map=whatsapp-nofna` добавляется для типов из серверного списка `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (свойство AB, флаг **4836**). Параметр запроса `auth` добавляется на пути с флагом (`PTU.A03`) и заменяет существующий параметр `auth`. Фото профиля использует тип `ppic`; статические ассеты используют `/wa/static` с `_nc_cat`.

### 9.2 Выбор бакета и хоста (декомпилированный поток управления, частично искажён)

- Хосты фильтруются по возможности `download` и по тому, содержит ли `download_buckets` строку бакета.
- Бакет `1`, когда прямой путь несёт `_nc_hot=<seconds>`, моложе окна из флага **2136**; иначе, с флагом **2134** и `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); резервный бакет `0`.
- Типы newsletter и помеченные флагом случаи пропускают логику hot / hash.
- Выбранный бакет уходит как `_nc_cat`.

### 9.3 HTTP-запрос (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Элемент | Значение |
|------|------|
| Метод | GET (Tigon или `HttpURLConnection`) |
| Заголовки | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (под флагом), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (когда известен ETag) |
| Принимается | HTTP 200 и 206 |
| Частичное | предпросмотры используют префикс из 262144 байт (`Range: bytes=0-262143`) |
| 416 | считается завершённым, когда `Content-Range` равен `*/<size>` и совпадает с локальным размером; иначе перезапуск (флаг **29305**) или ошибка |
| Белый список | с символом флага `PTU.A04` хост должен быть в `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` (совпадение по суффиксу), если только у URL нет `category=PSA`; иначе `invalid_url` (8) / лог `host not in media CDN allow-list` |

### 9.4 Проверка (found)

Поток расшифровки проверяет MAC; стадии хэша сопоставляются со статусами 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; отсутствующие входные данные сопоставляются с 26-30 (раздел 10.2).

---

## 10. Коды ошибок

### 10.1 Обработка статуса HTTP

| Статус | Поведение |
|--------|-----------|
| 401, 403 | обновить `media_conn`, заменить авторизацию, повторить (максимум 2 замены) |
| 408 | повтор только с флагом **13748** |
| 416 | см. 9.3 |
| 507 | статус скачивания 12 `throttle`, не повторяется |
| 505 | не повторяется |
| прочие 4xx | не повторяются |
| 5xx, < 400 | повторяется в пределах бюджета попыток |

### 10.2 Статус скачивания (found, `QKK` `A03`)

| Код | Имя | Код | Имя |
|------|------|------|------|
| 0 | success | 17 | wamsys_failed |
| 1 | failed_generic | 18 | failed_network |
| 2 | dns_failure | 19 | failed_connect |
| 3 | timeout | 20 | host_switch_required |
| 4 | disk_full | 21 | suspicious_content |
| 5 | too_old | 23 | partial_image_downloaded |
| 6 | resume_failed | 24 | programmatic_cancel |
| 7 | hash_mismatch | 25 | failed_no_client_network |
| 8 | invalid_url | 26 | failed_no_encryption_algorithm |
| 9 | output_stream_fail | 27 | failed_no_encrypted_hash |
| 11 | no_route | 28 | failed_no_media_hash |
| 12 | throttle | 29 | failed_no_media_key |
| 13 | user_cancel | 30 | failed_no_sidecar |
| 14 | prefetch_end | 31 | failed_hash_verification |
| 15 | watls_error | 32 | enc_hash_mismatch |
| 16 | server_error | 34 | deduped |

Коды 10, 22, 33 и всё остальное печатают `invalid`. `QKK.A04` группирует 1, 2, 3, 11, 15, 16, 18, 19, 20 и 25 (сбои сетевого типа; метка предполагается).

### 10.3 Результат загрузки (found, имена метрик `media_upload_<NAME>`)

| Код | Имя | Код | Имя |
|------|------|------|------|
| 1 | CANCEL | 22 | FAILED_DNS_LOOKUP |
| 2 | FAILED_INSUFFICIENT_SPACE | 23 | FAILED_WAMSYS |
| 3 | FAILED_IO | 24 | FAILED_TOO_LARGE |
| 4 | FAILED_OOM | 25 | ERROR_NO_CLIENT_NETWORK |
| 5 | FAILED_BAD_MEDIA | 26 | HOST_SWITCH_REQUIRED |
| 6 | FAILED_NO_PERMISSIONS | 27 | SKIPPED_EP_NO_PRIMARY_HOST |
| 7 | FAILED_FNF | 28 | FAILED_CRONET |
| 8 | FAILED_SERVER | 29 | FAILED_NO_DIRECT_PATH |
| 9 | FAILED_REQUEST | 30 | FAILED_NO_MEDIA_KEY |
| 10 | FAILED_REQUEST_TIMEOUT | 31 | FAILED_UNKNOWN |
| 11 | FAILED_NOT_FINALIZED | 32 | CANCEL_PROGRAMMATIC |
| 12 | FAILED_OPTIMISTIC_HASH | 33 | FAILED_NO_ROUTE |
| 13 | FAILED_MEDIA_CONN | 34 | FAILED_CANNOT_TRANSCODE |
| 14 | FAILED_OPTIMISTIC_NETWORK_UNSAFE | 35 | FAILED_UNKNOWN_MIMETYPE |
| 15 | FAILED_THROTTLE | 36 | FAILED_SERVER_REJECTED_MEDIA |
| 16 | FAILED_NO_SUCH_ALGORITHM | 37 | FAILED_IO_ENCRYPTION |
| 17 | FAILED_NETWORK | 38 | FAILED_STREAMING_METADATA_TOO_LARGE |
| 18 | FAILED_WATLS | 39 | FAILED_MUSIC_REPORTING |
| 19 | FAILED_URL | 20 / 21 | FAILED_TRANSCODING_UNKNOWN / FAILED_FILE_FORMAT_UNSUPPORTED |

Сопоставление исключений в `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, прочий `IOException` 18 (сеть недоступна) или 3, `CancellationException` 1, `C7CL` 21, что-либо иное 31. После неуспешного результата с 5, 21, 24, 34, 35 или 36 кэшированные ключ и хэш (`A0B`, `A0C`) очищаются.

---

## 11. Media retry (запрос повторной загрузки)

Когда скачивание не удаётся, потому что объект исчез (обычно статус 5 `too_old`, или ответ класса 404), получатель просит телефон отправителя загрузить заново.

### 11.1 Запрос: квитанция `server-error` (found, `SendMediaErrorReceiptJob`)

| Вариант | Writer | Протокол |
|---------|--------|------|
| Multi-device (собственное основное устройство) | кейс 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Устаревший вариант | кейс 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (без `rmr`) |

`enc_iv` — 12 случайных байт; `enc_p` производится нативно (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) из сообщения, несущего id стансы. Нативная библиотека хранит HKDF info `WhatsApp Media Retry Notification`; AES-GCM с id стансы как AAD и 32-байтным HKDF-ключом предполагается из 12-байтного IV и из реализации Baileys. Серверные свойства `mms4_media_retry_notification_encryption_enabled` и `mms4_server_error_receipt_encryption_enabled` — токены справочника (эффект предполагается: управляют тем, отправляется ли `<encrypt>`).

### 11.2 Ответ: уведомление `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Шаг | Детали |
|------|--------|
| Проверка аккаунта | `rmr` от другого аккаунта логируется как `cross-account-rmr` и отбрасывается, если символ флага `PTV.A0F` не включён |
| Поиск | сообщение по `(chat, id, from_me)`; немедийные сообщения логируют `message is null or not media` |
| Расшифровка | нативная (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); модель результата даёт `directPath` (сохраняется в сообщение) и int результата |
| Результат | `<error code>` переопределяет результат; обработчик сравнивает значение с 2 и 3 (с публичной нумерацией proto `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, предполагается) |
| Продолжение | загрузчик получает новый прямой путь (`resume reuploading download`); при отсутствии активного загрузчика сообщение ставится в очередь на автоматическое скачивание |
| Отчётность | при флаге **5718** `reporting_token` сохраняется для сообщения |

---

## 12. Медиа однократного просмотра и статусов

| Тема | Факт (found) |
|-------|--------------|
| Крипто / транспорт | идентичны обычному медиа: тот же `MmsType`, тот же HKDF, те же URL; типа однократного просмотра в таблице нет |
| Флаг | `viewOnce` — поле в `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); контейнер `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Локальные правила | отправитель не может открыть собственное медиа однократного просмотра (`senders can not view their own media`); миниатюры однократного просмотра удаляются `EphemeralUpdateRunnable/deleteViewOnceThumbnails`; аудио однократного просмотра без медиа-ключа не отправляется (`unable to send encrypted media message due to missing mediaKey`) |
| Удаляет ли сервер объект после просмотра | unknown |
| Статус (`status@broadcast`) | использует обычные строки `MmsType` (image, video, gif, audio) с их собственными числовыми id; HKDF info для `status` не существует; единственные типы `*-status` — это типы newsletter (раздел 13) |
| Лимиты статуса | токены справочника `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` — серверные свойства (значения: unknown) |
| Скачивание статуса | `C59526QnY` хранит вариант `MediaDownload` и `StatusMediaDownload`; оба строят URL тем же генератором |

---

## 13. Медиа канала (newsletter)

| Аспект | Newsletter | Обычное |
|--------|-----------|---------|
| Поверхность в URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | обычные имена |
| Шифрование | нет: загрузчик artwork требует `artworkEncSha256` только для не-newsletter содержимого (`required fields missing - artworkEncSha256 is null for encrypted content`); для прочих типов существует сквозной поток `C59535Qnh` (тождественный). Строки `MmsType` всё же несут байты HKDF info (не используются, предполагается) |
| Токен загрузки | случайный, не привязан к хэшу (раздел 8.2) | секрет инсталляции + хэш |
| Фильтр маршрута | нет логики hot / hash-бакета для имён, начинающихся с `newsletter` | логика бакета (9.2) |
| ip token `media_conn` | `ip_token` применяется для newsletter независимо от `set_ip_token` (флаг **12149**) | только когда `set_ip_token` истинен |
| Серверная работа | `server_thumb_gen=1` (флаги **11191**, **11192**), `server_transcode=1` для видео (флаг **9096**) | не устанавливается |
| Флаг **27920** | считывается в пути newsletter у `C15490gQ`; эффект unknown | |

---

## 14. Express-путь и другие варианты загрузки

| Вариант | Доказательство |
|---------|----------|
| Express-путь | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) отправляется как E2E-сообщение (`FMessageMediaExpressPathNotify`, требует url, хэш и длину); `ExpressPathDownload` логирует `EP gain <ms> <bytes>`; лог загрузки `Use static route supplier for express path upload`; результат загрузки 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Серверное поведение: unknown |
| Оптимистичная загрузка | поверхность `optimistic`; повторная проверка хэша даёт результат 12; протокол: unknown |
| История / app state | `md-msg-hist`, `md-app-state` используют обычный конвейер со своими строками info |
| История группы | `group-history`, info `Group History`, mime `application/protobuf`, проверяется получателем (`C34677F2y`); путь следует разделу 8.1 (`/mms/group-history/...`, выведено из общей композиции) |

### 14.1 Отправка обоев темы чата (новое в 2.26.45.10, found)

Поток "отправить в чат" для темы конкретного чата идёт через этот обычный конвейер без изменений. Точка входа: `ChatThemeViewModel.sendThemeToChat` (корутина Kotlin; локальные переменные `targetJid`, `sentBundle`, `sharedTheme` из сохранённых отладочных метаданных) разрешает выбранный источник обоев (`DOWNLOADED`, `USER_PROVIDED`, `ANIMATED`, `GRADIENT`, `DEFAULT`, `NONE`) и вызывает `ChatThemeSettingSenderImpl.A06` → `A01`.

| Шаг | Детали (found) |
|------|-----------------|
| Локальная копия | исходный `File` обоев копируется в хранилище приложения под `chat_theme_sent_wallpapers/<uuid>.jpg` |
| Загрузка | `ChatWallpaperUploader.A00` оборачивает `MediaUploadCoordinatorImpl.A0G` (тот же конвейер `media_conn` → HKDF → AES-CBC → HMAC → POST, что и в разделах 1-8 выше), запрашивая режим шифрования `LX/8cp;->A02`, чьё поле `value` — литеральная строка `"E2EE"` |
| Копия результата | результат загрузки (`SGq`) копируется поле за полем в общий дескриптор медиа-вложения (`LX/8cr`): строка результата загрузки → прямой путь, байты медиа-ключа, метка времени и ещё три массива байтов хэша/HMAC |
| Поверхность сеттера | дескриптор передаётся через `LX/1iA` (расширяет `LX/19i`), **тот же общий интерфейс сеттера медиа-вложения**, который используют обычные конструкторы сообщений с изображением; его поля выстраиваются позиционно с `directPath` (**11**), `mediaKey` (**8**) и байтовыми полями `fileSha256`/`fileEncSha256` (**9**/**12**, раздел 6) у `imageMessage` |
| Mimetype | `image/jpeg` устанавливается явно тем же вызовом |

Это отправляется реальному собеседнику чата (`targetJid`), а не является синхронизацией локального предпочтения отображения: для тем на основе изображения сам битмап обоев перекодируется и загружается через стандартный путь медиа E2EE, так что принимающий клиент скачивает и расшифровывает настоящее изображение, а не применяет известный заданный тему-пресет. Для этого потока не найдено специального типа медиа при загрузке или переопределения HTTP-пути (в отличие от `/mms/group-history` для истории группы, раздел 14) — похоже, он повторно использует существующий `MmsType` (вероятно `image`, отдельно не подтверждено).

**Unknown**: точное поле oneof в `Message`, в которое в итоге попадает это вложение — `LX/19i`/`LX/1iA` — большие общие базовые классы, используемые многими типами исходящих сообщений, а конкретное место выделения после их сеттеров не было достигнуто в этом проходе. Также unknown: отправляется ли вообще выбор темы со сплошным цветом/без обоев (`DEFAULT`/`NONE`), или остаётся только локальным. Для этой функции не найдено нового типа сообщения protobuf или операции GraphQL/MEX (проверено по различиям proto и запросов между 2.26.41.6→2.26.45.10); наиболее обоснованная трактовка — что это идёт через существующее поле медиа-сообщения, скорее всего сам `imageMessage` — **inferred**, не подтверждено.

---

## 15. Нативная защита парсеров медиа (found, строки и экспорты распакованных библиотек)

81 shared object распаковывается из архива superpack. Небезопасные по памяти парсеры байтов, контролируемых атакующим, либо помещены в песочницу, либо заменены на Rust.

| Вход | Компонент | Защита |
|-------|-----------|-----------|
| WebP | `libstatic-webp.so` (43 КБ) | libwebp, скомпилированная в WebAssembly и приведённая к C через wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), обёртка `whatsapp::security::LibwebpSandbox` в потокно-локальной песочнице; Java-флаг `sWebPSandboxEnabled`; лог сбоя `sandboxed WebP decode failed: status=%d`; защитные проверки `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib в песочнице wasm2c / WASI-minrt (`GiflibSandbox`, `wasi::minrt`); классы JNI `SandboxedGifImage`, `SandboxedGifFrame`; защитная проверка `Called memcpy for memory larger than the sandbox` |
| Файлы Ogg / Opus | `libwhatsapp.so` | песочницы RLBox wasm2c для `libogg.wasm` и `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; лог перехвата `wasm2c sandbox trap: %s (code=%d)` |
| Разбор контейнеров и потоков | Rust-крейты `libwhatsapp.so` | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, DASH-сегментер, списки правок), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (значения IPTC digital-source-type, такие как `trainedAlgorithmicMedia`, C2PA) |
| Декодирование AV1 | `libdav1d.so` | dav1d **1.5.1** (строка версии); экспортирует API `dav1d_*` |
| Кодирование AV1 | `libwzav1.so` | версия 2.3.1; экспортирует только `wz_encoder_*` и `wz_codec_version*`; символов декодера нет, так что он не разбирает удалённые битстримы |
| Кадры H.264 / H.265 | платформенный `MediaCodec` | вне приложения |

Парсеры на Rust падают с паниками (`assertion failed: ...`, `While parsing field '...' in ...`) вместо повреждения памяти: найдено как строки, эффект предполагается. Песочница `rlbox` охватывает libogg и opusfile в `libwhatsapp.so`; другие библиотеки используют wasm2c без обёртки RLBox (выведено из символов). Достигает ли каждый входящий медиа-путь этих парсеров до взаимодействия с пользователем: unknown. Динамическое поведение (фаззинг, сбои в runtime): не проверялось.

---

## 16. Флаги функций (id, как прочитаны в точках вызова; имена не разрешены)

| Флаг | Где | Управляет |
|------|-------|----------|
| **149** | `RouteSelector`, `C43951qe` | сохранение и перезагрузка `media_conn` в настройках |
| **257** | конструктор `Mms4RouteSupplier` | объект экспоненциального backoff |
| **258** | `Mms4RouteSupplier.A03` | int: дополнительные попытки для режима 0 |
| **2134** | `A02` | бакет скачивания на основе хэша |
| **2136** | `A02` | окно "горячего" содержимого (long) |
| **4073** | `A00` | маршрутизация медиа через пользовательский прокси |
| **4836** | `Mms4DownloadUrlGenerator` | список типов с низкой частотой попадания (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | обработка токена отчётности |
| **9096** | `QBE` | `server_transcode=1` (видео newsletter) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` для изображения / видео newsletter |
| **12149** | `RouteSelector.A0L`, `A03` | использование `ip_token` |
| **12545** / **12446** | `A05` | переопределение лимита попыток после попытки 3 |
| **13748** | `QKS.A08` | повтор HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | точки входа `RouteSelector` | булево значение, передаваемое в выбор маршрута как флаг загрузки (семантика не разрешена) |
| **24661** | `MediaCryptoProvider` | проверка домена ключа не-E2EE |
| **29305** | `PlainDownloadTransfer` | обработка 416 |
| **37982**, **38437** | `C43481Ixw` | свойство Tigon, таймаут запроса |

---

## 17. Baileys (`baron-baileys-v2`, прочитан исходный код, ничего не проверено)

| Аспект | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Запрос `media_conn` | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; `Socket/chats.js` имеет опциональный вариант `last_id` | всегда `<media_conn>`, с `last_id`, когда есть предыдущий id |
| Разбираемые поля | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | `maxContentLengthBytes` не читается; добавляются `auth_ttl`, `max_buckets`, `is_new`, `id`, резервные поля, дочерние элементы возможностей, счётчики повторов, `ip_token` |
| Длина HKDF | `hkdf(key, 112, {info})`, использует байты 0-79 | 80 байт; первые 80 байт вывода HKDF не зависят от запрошенной длины, так что IV, ключ шифра и MAC-ключ идентичны |
| Строки info | `WhatsApp <X> Keys`; `gif` и `ptv` сопоставляются с Video, `ptt` с Audio, `sticker` с Image | те же строки и сопоставления |
| Шифр, MAC, хэши | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` добавляется, `fileSha256`, `fileEncSha256` над `ct + mac` | то же |
| URL загрузки | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Кодирование хэша | url-safe base64, дополнение `=` удалено, затем `encodeURIComponent` | url-safe base64, дополнение `=` сохраняется |
| Токен | url-safe `fileEncSha256` | `SHA-256(installSecret || fileEncSha256)` (newsletter: случайный) |
| Таблица путей | `sticker` и `thumbnail-link` в `/mms/image`, `ptv` в `/mms/video`, `md-msg-hist` в `/mms/md-app-state`, нет `ptt` | строка `MmsType` — это сегмент пути: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Заголовки | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | `Origin` не найден; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Повтор | пробует каждый хост по одному разу по порядку | поставщик маршрута с попытками, замена токена при 401 / 403, зонд докачки |
| Докачка | не найдена (`resume=1`, `Content-Range` отсутствуют) | зонд `resume=1` и `Content-Range` |
| Sidecar | генерация `streamingSidecar`, `firstScanSidecar` или `scansSidecar` в `src` не найдена | генерируются для видео, аудио, прогрессивных изображений |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | внутри в миллисекундах, в секундах в proto |
| Квитанция повтора | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = id стансы, IV 12 байт, HKDF info `WhatsApp Media Retry Notification` | writer-кейс 327 имеет ту же раскладку узлов; IV 12 байт и строка info — found; GCM / AAD — inferred |
| Сопоставление результата повтора | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | не применимо (сравнивает значения 2 и 3) |

Практические последствия (только чтение кода): загрузка объекта `md-msg-hist` в Baileys использует другую строку пути, чем Android-клиент; дополненный base64 в пути — видимое различие; какая-либо серверная терпимость к этим вариантам неизвестна.

---

## 18. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|-------|-----|
| Загрузка 401 / 403 | `auth` истёк или заменён | обновить `media_conn`, повторить отправку с новым `auth` |
| Загрузка не возвращает `direct_path` | загрузка отклонена или неполна | проверить статус; зонд докачки с `resume=1` |
| Скачивание 404 / статус 5 `too_old` | объект истёк на CDN | отправить квитанцию `server-error` (раздел 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | повреждённые байты или неверный `fileEncSha256` | повторная загрузка; проверить источник хэша |
| Проверка MAC не проходит | неверный медиа-ключ, неверный HKDF info (смешение типов) или обрезанный файл | использовать строку info правильного `MmsType`; не повторно использовать Image info для строк `sticker-pack` или `ptt` |
| `invalid_url` (8) | хост вне белого списка CDN | принимать только перечисленные суффиксы |
| `throttle` (12), HTTP 507 | throttle сервера | подождать `backoff` секунд (максимум 10800) |
| `no_route` (11) | нет пригодного хоста `media_conn` для типа | запросить `media_conn`, проверить теги возможностей |
| `failed_no_media_key` (29), `no_sidecar` (30) | отсутствует поле proto | требуется `mediaKey`; sidecar только для потоковой передачи |

---

## 19. Ключевые различия

| Не путать | Факт |
|----------------|------|
| список хостов `media_conn` vs URL загрузки | IQ даёт хосты и один `auth`; путь, токен и запрос URL строятся для каждой передачи |
| `auth` vs `token` | `auth` — токен уровня аккаунта из `media_conn`; `token` — на файл |
| HKDF 80 vs 112 байт | одинаковые ключи; Android выводит 80 |
| `fileSha256` vs `fileEncSha256` | хэш открытого текста vs хэш `ciphertext + mac10` |
| `fileEncSha256` в пути vs `directPath` | путь загрузки использует хэш; скачивание использует возвращённый сервером `directPath` |
| `mediaKeyTimestamp` vs окно повторного использования ключа | метка времени в секундах на проводе; окно повторного использования 2-3 дня на отправителе |
| Потоковый sidecar vs `fileEncSha256` | 10-байтные MAC-коды на кусок vs хэш всего файла |
| Media retry vs повторная отправка | отправитель заново загружает тот же объект и отвечает новым `directPath`; сообщение не отправляется повторно |
| Медиа newsletter vs обычное медиа | не зашифровано, поверхность `newsletter`, случайный токен |
| `libwzav1` vs `libdav1d` | кодер vs декодер; только декодер разбирает удалённые данные |

---

## 20. Полный поток (отправка и получение одного изображения)

```
[Sender app]  pick file → process (resize, strip) → MmsType "image"
     │
     ▼
[RouteSelector]  media_conn fresh? (conn/auth > 120 s left) ── no ──► <iq xmlns="w:m" type="set"><media_conn last_id/></iq>
     │                                                                   │ ◄── auth, ttl, auth_ttl, max_buckets, hosts
     ▼
[Uploader]  mediaKey = 32 B SecureRandom ; okm = HKDF(mediaKey, "WhatsApp Image Keys", 80)
     │  iv | cipherKey | macKey ; AES-CBC encrypt ; mac10 = HMAC(macKey, iv||ct)[0:10]
     │  fileSha256 (plain), fileEncSha256 (ct||mac10) ; optional sidecar / thumbnails
     ▼
[Mms4RouteSupplier]  host: type=primary, upload set has "image"
     │  POST https://host/mms/image/<hash>?direct_ip=0&token=<sha256(secret||hash)>&auth=<auth>
     │      Host, Accept-Encoding: identity, body = ct||mac10   (resume: ?resume=1, Content-Range)
     ▼
[Media server]  (not observed) ──► {"url","direct_path","handle","ts",...}
     │
     ▼
[Sender]  ImageMessage{mediaKey, fileSha256, fileEncSha256, directPath, mediaKeyTimestamp(s), jpegThumbnail, ...}
     │  Signal-encrypted message over chatd
     ▼
[Receiver]  host from media_conn (download set + bucket _nc_cat)
     │  GET https://host<directPath>?direct_ip=0&_nc_cat=<b>&mode=auto
     │      Range: bytes=0-   (200 or 206)
     ▼
[Receiver]  check enc hash → MAC → AES-CBC decrypt → check fileSha256 → store
     │
     ├── object gone (404 / too_old) ──► <receipt type="server-error"><encrypt enc_p enc_iv/><rmr/></receipt>
     │                                         │
     │                                [Sender phone] re-uploads, answers
     │                                         ▼
     └──────────────────────────────── <notification type="mediaretry"><encrypt enc_p enc_iv/></notification>
                                         → new directPath → resume download
```

---

## 21. Неизвестное

| Элемент | Статус |
|------|--------|
| Серверное поведение (валидация токена, дедупликация, срок жизни объекта, удаление однократного просмотра) | серверная сторона |
| Имена запросов `_nc_cbep`, `_nc_rmr`, `type`; флаг **21807** и идентификаторы `PTU.*` | имена или значение не разрешены |
| Числовые id в `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | значение не разрешено |
| Нативный шифр media-retry (AES-GCM, AAD, длина ключа) | строка info найдена; алгоритм предполагается |
| Использование `ip_token`, значение `X-FB-nc-oc`, источник `Companion_User_Secret` | не разрешено |
| Использование домена медиа-ключа NON_E2EE | не разрешено |
| Протоколы express-пути и оптимистичной загрузки | не разрешены |
| Точный порядок хостов между попытками и зависящие от режима счётчики попыток | декомпилированный поток управления искажён |
| Какое входящее медиа достигает какого парсера в песочнице до взаимодействия с пользователем | не отображено |
| Трафик | ничего не захвачено; динамического теста не было |
