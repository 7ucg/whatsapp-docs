<!-- src-sha1: a94958787eccb3db407fbb92cf700d9a4d424f4a -->
# WhatsApp Media Upload — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** передача медиа в Android: IQ `media_conn` (хосты, auth, ttl, buckets, fallback-хосты), построение URL загрузки и скачивания и HTTP-параметры, таблица типов медиа с HKDF info-строками, генерация и вывод media key, шифрование AES-CBC + HMAC, fileSha256 / fileEncSha256, mediaKeyTimestamp, direct path, миниатюры, streaming sidecar для видео / аудио / прогрессивных изображений, возобновляемая загрузка, выбор маршрута, retry и backoff, коды ошибок загрузки и скачивания, media retry receipt и уведомление `mediaretry`, view-once и status media, медиа newsletter (каналов), express path, нативное усиление парсеров медиа на стороне клиента, сравнение с Baileys

---

## 1. Что это (технически)

Медиа никогда не передаётся внутри потока chatd (см. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Сообщение несёт только protobuf-ссылку (ключ, хеши, `directPath`); байты идут по отдельным HTTPS-соединениям к медиа-хостам. Chatd даёт одно: IQ `media_conn`, который выдаёт имена хостов и короткоживущий токен авторизации загрузки. Все утверждения получены статическим анализом декомпилированного APK и распакованных нативных библиотек; на wire ничего не перехватывалось. Уровни: **found** = прочитано в коде или строках, **inferred** = выведено, **unknown** = не разрешено.

| Слой | Имя в 2.26.41.6 | Роль |
|------|-----------------|------|
| Route selector | `RouteSelector` (`C10950Wx`) | хранит текущий результат `media_conn`, таймер обновления, throttle, фабрику маршрутов |
| Парсер `media_conn` | `C43951qe` (обработчик IQ-результата), `C41561mf` (RoutingResponse), `C41441mT` (RouteHost) | разбирает `<media_conn>` / `<host>` |
| Route supplier | `Mms4RouteSupplier` (`C46433KQw`), `C46435KQy` / `C46436KQz` (статические supplier) | выбирает хост на каждую попытку, подменяет auth-токен |
| Retry driver | `TransferRetries` (`C44566Jd2`) | цикл попыток вокруг одной передачи |
| Таблица типов медиа | `MmsType` (`C15530gU`) | на тип: строка пути, байты HKDF info, числовой id |
| Провайдер ключей | `MmsImageCipherKeyProvider` (`C59530Qnc`), `MediaCryptoProvider` (`C58155Q5r`) | HKDF 80 байт, ключ домена non-E2EE |
| Потоки шифра | `M2I` (шифрование на выходе), `M23` (шифрование на входе), `P9N` / `P1X` / `P1Y` (MAC sidecar), `C51101MlN` (дешифрование по диапазону) | AES-CBC + HMAC |
| Драйвер загрузки | `MediaUploadUtils` (`QIh`), `QBE`, `Q52` (повторное использование ключа), `C57333Po0` (генерация ключа + хеши) | хеши, sidecar, оркестрация загрузки |
| URL загрузки | `C43489Iy4` | `/surface/type/hash?...` |
| URL скачивания | `Mms4DownloadUrlGenerator` (`C43488Iy3`) | `directPath?...` |
| HTTP | `HttpsFormPost` (`C43478Ixt`, `K19`) загрузка; `PlainDownloadTransfer` (`CallableC60106QxW`), `C17660kC`, `C43481Ixw` (Tigon) скачивание | транспорт |
| Resume probe | `HttpResumeCheck` (`C59524QnW`) | спрашивает сервер, сколько байт у него уже есть |
| Retry receipt | `SendMediaErrorReceiptJob`, writer cases 77 и 327 в `HandlerThreadC21920sG` | запрашивает повторную загрузку у отправителя |
| Retry notification | `MediaRetryNotificationHandler` (`C1S0`, notification code 97) | обрабатывает ответ |
| Нативные | `libwhatsapp.so` (Rust-крейты медиа, песочницы RLBox), `libstatic-webp.so`, `libwa_sandboxed_gifimage.so`, `libdav1d.so` | парсеры и декодеры |

Моменты, определяющие остальной отчёт:

- Android выводит из media key **80** байт (IV 16, ключ шифра 32, ключ MAC 32), а не 112 (раздел 4).
- HTTP-путь: `/{surface}/{type}/{urlSafeFileEncSha256}`, где `type` — строка `MmsType` медиа (`image`, `ptt`, `md-msg-hist`, ...), а не грубый класс (раздел 8.1).
- Android-`token` загрузки — не хеш файла, а SHA-256 от секрета установки и хеша файла (раздел 8.2).
- Медиа newsletter (каналов) использует тот же код, но поверхность `newsletter` и случайный токен; оно не шифруется (found для пути artwork, inferred для остального, раздел 13).
- Хосты скачивания фильтруются по bucket, выведенному из хеша файла (раздел 9.2).

---

## 2. IQ `media_conn`

### 2.1 Запрос (found, `RouteSelector.A07`)

```
<iq to="s.whatsapp.net" id="<id>" xmlns="w:m" type="set">
  <media_conn [last_id="<id of previous result>"]/>
</iq>
```

Таймаут 32000 мс. В полёте только один запрос (`inFlightMediaRoutingRequestTime`); второй вызов логирует `not sending request` и возвращается. Глобальный throttle (`ChatdMediaThrottleManager`) может подавить вызов (`routeselector/requestupdatedroutinginfo throttled`).

### 2.2 Ответ (found, `C43951qe.CFS`)

| Узел / атрибут | Тип | Назначение |
|----------------|-----|------------|
| `media_conn@auth` | string, обязателен | токен авторизации загрузки (query-параметр `auth`) |
| `@ttl` | секунды | время жизни соединения; истечение = время отправки + ttl * 1000 |
| `@auth_ttl` | секунды | время жизни auth-токена; истечение = время отправки + auth_ttl * 1000 |
| `@max_buckets` | long, по умолчанию 0 | модуль для bucket скачивания (раздел 9.2) |
| `@is_new` | int, по умолчанию 1 | 1 = заменить список хостов; иначе сохранить прежние хосты и взять только токен и ttl (`previous hosts retained`) |
| `@id` | string | сохраняется как `last_id`, отправляется обратно в следующем запросе |
| `@max_auto_download_retry` | int, по умолчанию 3 | бюджет retry для автоматических скачиваний |
| `@max_manual_retry` | int, по умолчанию 3 | бюджет retry для ручных скачиваний |
| `@ip_token`, `@set_ip_token` | string, "0"/"1" | разбираются и кешируются; `ip_token` используется только когда флаг **12149** включён и `set_ip_token` равен true (место потребления: unknown) |
| `host` (повторяется) | node | одна запись маршрута |

Атрибуты `host` (found): `hostname` (обязателен), `ip4`, `ip6`, `class`, `fallback_hostname`, `fallback_ip4`, `fallback_ip6`, `fallback_class`, `type` (`primary` или `fallback`; всё остальное становится `primary`), `force_ip` (`"true"`). Дочерние: `<upload>`, `<download>`, `<download_buckets>`; имена дочерних тегов — это записи возможностей. `upload` и `download` оставляют только теги из фиксированного набора из 34 строк типов медиа (`audio`, `image`, `chat-wallpaper-image`, `video`, `ptv`, `kyc-id`, `sticker`, `document`, `ptt`, `gif`, `md-app-state`, `md-msg-hist`, `ppic`, семейство `newsletter-*` и семейство `thumbnail-*`); `download_buckets` остаётся без фильтрации.

Маршрутный хост пригоден, только если его hostname заканчивается на `.whatsapp.net` (`Mms4RouteSupplier.A06`, применяется и к `fallback_hostname`).

### 2.3 Кеширование и обновление (found)

| Правило | Значение |
|---------|----------|
| Сохранение | при флаге **149** результат сохраняется как JSON (`auth_token`, `conn_ttl`, `auth_ttl`, `max_buckets`, `hosts`, `last_id`, `is_new`, `max_autodownload_retry`, `max_manual_retry`, `ip_token`, `set_ip_token`, `send_time_abs_ms`) в `route_selector_prefs` / `media_conn`; загружается один раз, используется только если auth ещё не истёк |
| Проверка обновления | перед передачей: если соединение или auth истекает в течение 120000 мс, отправить новый IQ и ждать до 20000 мс (`requestroutesandwaitforauth`) |
| Таймер | `auth expiry - 60000 ms` после каждого результата; foreground (`BgG`) перевзводит его |
| Ошибка auth | HTTP 401 или 403 при передаче запускает обновление (`onmediatransfererrororresponsecode`), максимум 2 подмены токена на передачу (`JW1.A00 < 2`), затем попытка повторяется с новым `auth` |
| Auth перед попыткой | `refreshAuthBeforeAttempt` подставляет более новый токен, когда кешированный в пределах 120000 мс от истечения (символ флага `PTU.A0D`) |

### 2.4 Ошибка IQ (found, `C43951qe.Brt`)

`<error code backoff>` внутри IQ-результата:

| Код | Поведение |
|-----|-----------|
| 503 | сбросить media throttle; запланировать следующее обновление после backoff по Фибоначчи с jitter (`3/4 * t + rand(t/2)`) |
| 507 при backoff > 0 | throttle медиа-запросов до `now + min(backoff, 10800) s` |
| другое / 0 | игнорируется |

---

## 3. Типы медиа и HKDF info-строки (found, статическая инициализация `MmsType` `C15530gU`)

Каждый `MmsType` хранит строку пути (`A02`), короткую метку типа файла (`A01`, напр. `IMG`), байты HKDF `info` (`A03`) и числовой id (`A00`). Байты `info` используются как есть в качестве HKDF info (без дополнительного префикса).

| HKDF info | Строки пути `MmsType` |
|-----------|-----------------------|
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

Примечания (found): `ptt` и `audio` используют общий Audio info, но это разные строки пути; `sticker` использует Image info; `gif` и `ptv` используют Video info; существует несколько строк `image` с разными числовыми id (1, 23, 25, 37, 42, 44, 57; у `sticker` — 20) для разных мест вызова (смысл id unknown); `group-history` — единственная запись, чей info не имеет вида `WhatsApp <X> Keys`. Фото профиля (`ppic`) встречаются только в наборе возможностей маршрута и в вызовах генератора скачивания, не как `MmsType`.

---

## 4. Media key и вывод ключей

### 4.1 Генерация ключа (found)

| Элемент | Значение |
|---------|----------|
| Media key | 32 случайных байта из `SecureRandom` (`C57333Po0`, `QIh.A0B` — это `new SecureRandom()`) |
| Повторное использование | `MediaKeyGen/reuse key from message contents`, когда ключ моложе `172800000 ms + SecureRandom.nextInt(86400000)` (2–3 дня, с jitter), отсчитывая от сохранённой метки времени ключа; более старые ключи отбрасываются (`key expired`) и генерируются заново |
| Домен | `D5C`: `E2EE` (0), `NON_E2EE` (1), `UNKNOWN` (-1) |

### 4.2 HKDF (found, `AbstractC38961i0.A00`, вызывается из `C59530Qnc.AM1`)

```java
byte[] okm = hkdfV3(mediaKey, info = mmsType.A03, length = 80);   // salt = 32 zero bytes
// extract: prk = HMAC-SHA256(key = 32 zero bytes, data = mediaKey)
// expand : T(i) = HMAC-SHA256(prk, T(i-1) || info || i), i = 1..3, truncated to 80
iv        = okm[0..16)
cipherKey = okm[16..48)
macKey    = okm[48..80)
```

`N6U.A01` отвергает любую другую длину (`Invalid length of derived secret`). Длина шифртекста: `N6U.A00(n) = floor(n/16)*16 + 16 + 10` (блоки с PKCS#5-дополнением плюс 10 байт MAC).

### 4.3 Media key non-E2EE (found, `MediaCryptoProvider` `C58155Q5r`)

```
nonE2eeKey = HKDF(e2eeKey, salt = 32 zero bytes, info = "non-e2ee-media-key", L = 32)
```

`ContextInfo.mediaDomainInfo` (поле **74**, сообщение `DQT`) несёт `mediaKeyDomain` (**1**: 0 UNKNOWN, 1 E2EE, 2 NON_E2EE) и `e2eeMediaKey` (**2**). При флаге **24661** получатель проверяет, что ключ в сообщении соответствует домену (`resolveKeyForDomain: mismatched e2eeMediaKey domain=`); при несовпадении используется ключ как есть. Какие продукты используют домен NON_E2EE: unknown.

---

## 5. Шифрование, MAC и хеши

### 5.1 Шифр (found, `M2I`, `M23`, `N6U`)

| Шаг | Деталь |
|-----|--------|
| Шифр | `AES/CBC/PKCS5Padding`, ключ = cipherKey, IV = iv |
| MAC | `HmacSHA256(macKey)`, обновляется сначала IV, затем каждым байтом шифртекста; первые **10** байт дайджеста дописываются к шифртексту |
| `fileSha256` | SHA-256 от открытого текста (поток дайджеста `P9M` поверх файла) |
| `fileEncSha256` | SHA-256 от шифртекста + 10 байт MAC |
| Выход | `ciphertext || mac10`; `Content-Length` = `N6U.A00(plaintextLength)` |

Сторона дешифрования (`P9N`, `M23`): MAC проверяется по IV + шифртекст, затем сравнивается с замыкающими 10 байтами. Дешифрование по диапазону (`C51101MlN`): если начало диапазона не 0, первые прочитанные 16 байт используются как IV (предыдущий блок шифртекста); внутренние чанки используют `AES/CBC/NoPadding`, последний чанк использует PKCS#5 (inferred из выбора шифра).

### 5.2 Метки времени и пути

| Поле | Значение |
|------|----------|
| `mediaKeyTimestamp` | локальные часы в миллисекундах, хранятся в объекте ключа, записываются в protobuf в секундах (`C20H.A06` = `/1000`) |
| `directPath` | строка пути, возвращённая сервером, хранится в сообщении и в колонке БД `direct_path`; может нести query-параметры (напр. из него читается `_nc_hot`) |
| `url` | устаревшее поле полного URL; всё ещё присутствует в proto-классах и в ответе загрузки, но генератор скачивания строится из `directPath` или из хеша (раздел 9.1) |

### 5.3 Оптимистичные проверки хеша

`MediaUpload/optimistic-hash-fail` и `optimistic-plaintext-hash-fail` (результат загрузки 12) логируются, когда хеш, сообщённый сервером, отличается от вычисленного локально. Оптимистичная загрузка (строка поверхности `optimistic`) загружает до фиксации отправки; её протокол помимо имени поверхности: unknown.

---

## 6. Поля медиа-сообщений

Номера полей прочитаны из сгенерированных protobuf-классов. Имена классов сопоставлены по раскладке полей (inferred); номера found.

| Сообщение (класс) | Номера полей (имя = номер) |
|-------------------|----------------------------|
| `ImageMessage` (`C30612DTg`) | url **1**, mimetype **2**, caption **3**, fileSha256 **4**, fileLength **5**, height **6**, width **7**, mediaKey **8**, fileEncSha256 **9**, directPath **11**, mediaKeyTimestamp **12**, jpegThumbnail **16**, contextInfo **17**, firstScanSidecar **18**, firstScanLength **19**, experimentGroupId **20**, scansSidecar **21**, scanLengths **22**, midQualityFileSha256 **23**, midQualityFileEncSha256 **24**, viewOnce **25**, thumbnailDirectPath **26**, thumbnailSha256 **27**, thumbnailEncSha256 **28**, staticUrl **29**, imageSourceType **31**, accessibilityLabel **32**, qrUrl **34** |
| `VideoMessage` (`C30614DTi`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, mediaKey **6**, caption **7**, gifPlayback **8**, height **9**, width **10**, fileEncSha256 **11**, directPath **13**, mediaKeyTimestamp **14**, jpegThumbnail **16**, contextInfo **17**, streamingSidecar **18**, gifAttribution **19**, viewOnce **20**, thumbnailDirectPath **21**, thumbnailSha256 **22**, thumbnailEncSha256 **23**, staticUrl **24**, processedVideos **27**, metadataUrl **30**, videoSourceType **31**, dashManifestUrl **33**, smartThumbnailTs **34** |
| `AudioMessage` (`DTX`) | url **1**, mimetype **2**, fileSha256 **3**, fileLength **4**, seconds **5**, ptt **6**, mediaKey **7**, fileEncSha256 **8**, directPath **9**, mediaKeyTimestamp **10**, contextInfo **17**, streamingSidecar **18**, waveform **19**, backgroundArgb **20**, viewOnce **21**, accessibilityLabel **22** |
| `DocumentMessage` (`C30609DTd`) | url **1**, mimetype **2**, title **3**, fileSha256 **4**, fileLength **5**, pageCount **6**, mediaKey **7**, fileName **8**, fileEncSha256 **9**, directPath **10**, mediaKeyTimestamp **11**, thumbnailDirectPath **13**, thumbnailSha256 **14**, thumbnailEncSha256 **15**, jpegThumbnail **16**, contextInfo **17**, thumbnailHeight **18**, thumbnailWidth **19**, caption **20** |
| `StickerMessage` (`C30611DTf`) | url **1**, fileSha256 **2**, fileEncSha256 **3**, mediaKey **4**, mimetype **5**, height **6**, width **7**, directPath **8**, fileLength **9**, mediaKeyTimestamp **10**, firstFrameLength **11**, firstFrameSidecar **12**, isAnimated **13**, pngThumbnail **16**, contextInfo **17**, stickerSentTs **18**, isAvatar **19**, isAiSticker **20**, isLottie **21** |
| `HistorySyncNotification` (`C25834BCt`) | fileSha256 **1**, fileLength **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, syncType **6**, chunkOrder **7**, encHandle **14** |
| `ExternalBlobReference` (`C49439Lov`) | mediaKey **1**, directPath **2**, handle **3**, fileSizeBytes **4**, fileSha256 **5**, fileEncSha256 **6** |
| `MediaNotifyMessage` (`DRJ`) | expressPathUrl **1**, fileEncSha256 **2**, fileLength **3** |
| History bundle (`DT6`) | mimetype **1**, fileSha256 **2**, mediaKey **3**, fileEncSha256 **4**, directPath **5**, mediaKeyTimestamp **6**, contextInfo **7**, messageHistoryMetadata **8** |

Номера контейнера `Message` (`C30628DTw`) (found): imageMessage **3**, documentMessage **7**, audioMessage **8**, videoMessage **9**, stickerMessage **26**, viewOnceMessage **37**, viewOnceMessageV2 **55**, viewOnceMessageV2Extension **59**, ptvMessage **66**, stickerPackMessage **86**, musicMessage **129**; `mediaNotifyMessage` — поле **21** контейнера `BD3`.

### 6.1 Миниатюры

| Вид | Механизм (found, если не указано иное) |
|-----|----------------------------------------|
| Inline | байты `jpegThumbnail` (**16**) в сообщении (изображение, видео, документ); `pngThumbnail` (**16**) в стикерах |
| Загружаемая | `thumbnailDirectPath`, `thumbnailSha256`, `thumbnailEncSha256` (изображение **26-28**, видео **21-23**, документ **13-15**); `MmsType` `thumbnail-*` с Thumbnail HKDF info из раздела 3 |
| Ключ | в proto нет отдельного поля ключа миниатюры, поэтому миниатюра шифруется media key своего сообщения (inferred) |
| Создаётся сервером | query загрузки `server_thumb_gen=1`; ответ загрузки может вернуть `thumbnail_info` = JSON `{thumbnail_direct_path, thumbnail_sha256}` |
| БД | таблица `mms_thumbnail_metadata` (directPath, mediaKey, mediaKeyTimestampMs, encThumbHash, thumbHash, width, height) |

---

## 7. Streaming и sidecar (found)

Sidecar — это список 10-байтовых MAC, по одному на чанк шифртекста, позволяющий плееру проверять диапазон без чтения всего файла.

| Элемент | Деталь |
|---------|--------|
| Алгоритм | `P9N.read`: на каждый чанк `HmacSHA256(macKey)` инициализируется **предыдущими 16 байтами шифртекста** (IV для первого чанка), получает чанк, и первые 10 байт дайджеста сохраняются |
| Конкатенация | `C57228PmG.A00` склеивает все 10-байтовые MAC в один массив байт |
| Видео / аудио | `VideoMessage.streamingSidecar` (**18**), `AudioMessage.streamingSidecar` (**18**); размер чанка **65536** (`QBE`, `QIh.A00(..., 65536)`) |
| Прогрессивное изображение | `firstScanSidecar` (**18**) с `firstScanLength` (**19**): один чанк из `ceil(len/16)*16` байт; `scansSidecar` (**21**) с `scanLengths` (**22**): чанки переменного размера (`P1Y`) |
| Стикер | `firstFrameSidecar` (**12**) с `firstFrameLength` (**11**) |
| Настройки | серверное свойство `streaming_upload_chunk_size` — токен словаря; его эффект: unknown |
| Отсутствует | статус скачивания 30 `failed_no_sidecar` |
| Серверный streaming | query загрузки `stream=1` и `streaming=riff` вместе (раздел 8.1); DASH: `dashManifestUrl` (**33**), `metadataUrl` (**30**) в ответе |

---

## 8. Загрузка

### 8.1 URL (found, `C43489Iy4`, `AbstractC46434KQx.A01`)

```
https://<route authority>/<surface>/<type>/<urlSafeFileEncSha256>
        ?direct_ip=<0|1>&token=<token>[&stream=1][&type=<x>][&media_id=<n>][&media_id_upload=<n>]
        [&streaming=riff][&server_transcode=1][&server_thumb_gen=1][&_nc_cbep=1][&_nc_rmr=1]&auth=<auth>
```

| Часть | Значение |
|-------|----------|
| `surface` | `mms` (обычная), `newsletter` (каналы), `optimistic` (загрузка до отправки); `AbstractC58025Pzy` |
| `type` | строка пути `MmsType` (раздел 3), напр. `image`, `ptt`, `md-msg-hist` |
| `urlSafeFileEncSha256` | стандартный base64 от `fileEncSha256` с заменой `+` на `-` и `/` на `_`; дополнение `=` сохраняется (`StringUtils.A0B`) |
| `direct_ip` | 1, когда authority — IP (`ip4` или `[ip6]` в скобках), иначе 0 |
| `auth` | auth-токен `media_conn`; добавляется как query-параметр в `K19.A03` |
| `stream=1`, `streaming=riff` | оба устанавливаются, когда запрос — потоковая загрузка (`c59651Qpf.A06()`) |
| `server_thumb_gen=1` | только для `newsletter-image` / `-status` (флаг **11191**) и `newsletter-video` / `-status` (флаг **11192**) |
| `server_transcode=1` | `newsletter-video` с request id 10 и флагом **9096** |
| `_nc_rmr=1` | загрузки не из newsletter (флаг запроса `A0N`) |
| `_nc_cbep=1` | когда запрос это допускает и флаг **17404** включён (смысл unknown) |
| `type`, `media_id`, `media_id_upload` | `media_id` = старшие 63 бита UUID загрузки; `media_id_upload` = младшие 63 бита, только когда у запроса есть дополнительные записи; `type` — строка вызывающего (смысл: unknown) |

Смысл имён query `_nc_cbep` и `_nc_rmr` unknown (известны только имена).

### 8.2 Токен (found, `C43489Iy4.A00`)

| Случай | Токен |
|--------|-------|
| Newsletter | `urlsafeBase64(SHA-256(32 bytes from java.util.Random))`, новый на каждый запрос, не привязан к файлу |
| Прочие | `urlsafeBase64(SHA-256(installSecret(32) || base64decode(fileEncSha256)))`; `installSecret` — 32 байта из `SecureRandom`, создаётся один раз и хранится в preferences как `upload_token_random_bytes` (base64 no-wrap, no-padding) |

Если `fileEncSha256` не удаётся декодировать, токен равен просто `SHA-256(installSecret)`. Назначение конструкции: inferred как серверная проверка того, что загружающий знает хеш, без раскрытия его в пути.

### 8.3 HTTP-запрос (found, `HttpsFormPost` `C43478Ixt`)

| Элемент | Значение |
|---------|----------|
| Библиотека | `HttpsURLConnection` с собственной `SSLSocketFactory`; маркер `http_stack = HttpUrlConnection` |
| Метод | POST (`setDoOutput(true)` на `HttpURLConnection`; явного вызова метода нет) |
| Таймауты | connect 15000 мс, read 60000 мс |
| Заголовки | `Host: <route hostname>` (authority может быть IP), `User-Agent`, `Accept-Encoding: identity`, `X-FB-Request-Analytics-Tags`, опциональный `Companion_User_Secret` (ненулевой аргумент конструктора; семантика companion inferred) |
| Тело (маршрут есть) | сырой поток шифртекста, только один файл (`MMS4 upload only supports a single file`); режим фиксированной длины, когда длина известна, иначе chunked (`setChunkedStreamingMode(0)`); буфер 16384 байта |
| Тело (маршрута нет) | устаревший `multipart/form-data` с частями `Content-Disposition: form-data` |
| Прерывание | при interrupt потока или флаге отмены поток дополняется (`UploadRequest/Post streaming padding bytes=`), чтобы заявленная длина была выполнена (назначение inferred) |
| Ответ | читается до 1 MiB; HTTP >= 400 возвращает код, тело уходит в `onError` |

### 8.4 Ответ (found, `MediaUploadTransfer` `C59523QnV`)

Читаемые JSON-ключи: `url`, `direct_path`, `handle`, `enc_handle`, `mcs_request_id` (принимается только если соответствует `[A-Za-z0-9-]{1,64}`), `meta_hmac`, `fbid`, `ts`, `thumbnail_info` (вложенная JSON-строка с `thumbnail_direct_path`, `thumbnail_sha256`), `metadata_url`, `dash_manifest_url`. Ответ без `direct_path` этим парсером не считается ошибкой; более поздние стадии падают с `FAILED_NO_DIRECT_PATH` (29).

### 8.5 Возобновляемая загрузка (found)

| Шаг | Деталь |
|-----|--------|
| Probe | тот же URL загрузки плюс `resume=1` (`HttpResumeCheck`); JSON-ответ `{"resume": "complete"}` с `url`, `direct_path` (уже загружено) или `{"resume": <offset>}` |
| Продолжение | POST с `Content-Range: bytes <offset>-*/*`, поток сначала пропускается до `<offset>` |
| Fallback | `ResumeCheck/attempting fallback MMS upload form post`, также после ошибки WATLS (TLS) |
| Ошибка разбора | статус `PBY.A03`, загрузка перезапускается |

### 8.6 Route supplier и retry (found, `Mms4RouteSupplier`, `TransferRetries`)

| Правило | Деталь |
|---------|--------|
| Цикл попыток | `TransferRetries/run attempt = N; route = ...`; одна передача на маршрут; `no routes` завершает цикл |
| Выбор хоста | хост `type=primary`, чей набор возможностей содержит тип медиа; первые две попытки используют его; последующие попытки используют запись `type=fallback` и её поля `fallback_*` (порядок inferred из запутанного control flow) |
| Попытки | по умолчанию 4 (`4 - extra`); при флагах **12545** и **12446** лимит можно переопределить после попытки 3; `max_auto_download_retry` / `max_manual_retry` (по умолчанию по 3) задают число, зависящее от режима (соответствие inferred) |
| Задержка | константа 1000 мс (`RouteSelector.A01`); при флаге **257** и дополнительных попытках — экспоненциальная: база 1000 мс, `2^n`, jitter, потолок 3000 мс |
| Ошибка auth 401 / 403 | не считается неудачей: ждать более новый токен (бюджет `A0J`, 20000 мс по умолчанию), подменить, повторить |
| Повторяемый HTTP-статус | `QKS.A08`: < 400 да; 400-499 нет, кроме 408 при флаге **13748**; >= 500 да, кроме 505 и 507 |
| Proxy | при пользовательском proxy и флаге **4073** media authority становится хостом proxy и портом из `proxy_media_port` (по умолчанию 587) |
| Health check | `MediaHealthChecker`: `POST https://<proxy>:<port>/mms/HEALTHCHECK`, `Host: mmg.whatsapp.net`, connect 15000 мс, read 30000 мс |

---

## 9. Скачивание

### 9.1 URL (found, `Mms4DownloadUrlGenerator` `C43488Iy3`)

```
https://<route authority><directPath>?direct_ip=<0|1>[&auth=<..>][&hash=<..>][&_nc_cat=<bucket>][&mode=<auto|manual>][&_nc_map=whatsapp-nofna]
(no directPath)  https://<authority>/<surface>/<type>/<urlSafeFileEncSha256>?direct_ip=...
```

Конструктор требует хеш медиа, direct path или cross reference (`media hash, direct path, or cross reference is required`). `mode` — `auto` или `manual`. `_nc_map=whatsapp-nofna` добавляется для типов из серверного списка `LOW_CACHE_HIT_RATE_MEDIA_TYPES` (AB prop, флаг **4836**). Query `auth` добавляется на пути под флагом (`PTU.A03`) и заменяет существующий параметр `auth`. Фото профиля используют тип `ppic`; статические ресурсы используют `/wa/static` с `_nc_cat`.

### 9.2 Bucket и выбор хоста (декомпилированный control flow, частично запутан)

- Хосты фильтруются по возможности `download` и по тому, содержит ли `download_buckets` строку bucket.
- Bucket `1`, когда direct path несёт `_nc_hot=<seconds>` моложе окна из флага **2136**; иначе, при флаге **2134** и `max_buckets > 0`: `100 + (base64decode(fileEncSha256) mod max_buckets)` (`BigInteger`); запасной bucket `0`.
- Типы newsletter и случаи под флагами пропускают логику hot / hash.
- Выбранный bucket уходит как `_nc_cat`.

### 9.3 HTTP-запрос (found, `C17660kC`, `C43481Ixw`, `PlainDownloadTransfer`)

| Элемент | Значение |
|---------|----------|
| Метод | GET (Tigon или `HttpURLConnection`) |
| Заголовки | `Host: <route hostname>`, `Accept-Encoding: identity`, `Range: bytes=<start>-<end>`, `User-Agent`, `X-FB-Socket-Option: TCP_CONGESTION=bbr` (под флагом), `X-FB-nc-oc`, `X-FB-Pad`, `If-None-Match` (когда известен ETag) |
| Принимается | HTTP 200 и 206 |
| Частичное | превью используют префикс 262144 байта (`Range: bytes=0-262143`) |
| 416 | считается завершённым, когда `Content-Range` равен `*/<size>` и совпадает с локальным размером; иначе перезапуск (флаг **29305**) или ошибка |
| Allow-list | при символе флага `PTU.A04` хост должен быть в `whatsapp.net`, `whatsapp.com`, `facebook.net`, `facebook.com`, `instagram.net`, `instagram.com`, `fbcdn.net`, `fbcdn.com`, `cdninstagram.net`, `cdninstagram.com` (совпадение по суффиксу), если только URL не содержит `category=PSA`; иначе `invalid_url` (8) / лог `host not in media CDN allow-list` |

### 9.4 Проверка (found)

Поток дешифрования проверяет MAC; стадии хеша отображаются в статусы 7 `hash_mismatch`, 31 `failed_hash_verification`, 32 `enc_hash_mismatch`; отсутствующие входные данные отображаются в 26-30 (раздел 10.2).

---

## 10. Коды ошибок

### 10.1 Обработка HTTP-статусов

| Статус | Поведение |
|--------|-----------|
| 401, 403 | обновить `media_conn`, подменить auth, повторить (максимум 2 подмены) |
| 408 | повтор только при флаге **13748** |
| 416 | см. 9.3 |
| 507 | статус скачивания 12 `throttle`, не повторяется |
| 505 | не повторяется |
| прочие 4xx | не повторяются |
| 5xx, < 400 | повторяются в пределах бюджета попыток |

### 10.2 Статус скачивания (found, `QKK` `A03`)

| Код | Имя | Код | Имя |
|-----|-----|-----|-----|
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

Коды 10, 22, 33 и всё остальное печатаются как `invalid`. `QKK.A04` группирует 1, 2, 3, 11, 15, 16, 18, 19, 20 и 25 (сбои сетевого типа; метка inferred).

### 10.3 Результат загрузки (found, имена метрик `media_upload_<NAME>`)

| Код | Имя | Код | Имя |
|-----|-----|-----|-----|
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

Отображение исключений в `QBE.A00` (found): `FileNotFoundException` 7, `NoSuchAlgorithmException` 16, `SocketTimeoutException` 10, `UnknownHostException` 22, прочий `IOException` 18 (сеть недоступна) или 3, `CancellationException` 1, `C7CL` 21, всё остальное 31. После неуспешного результата 5, 21, 24, 34, 35 или 36 кешированные ключ и хеш (`A0B`, `A0C`) очищаются.

---

## 11. Media retry (запрос повторной загрузки)

Когда скачивание не удаётся, потому что объекта больше нет (обычно статус 5 `too_old` или ответ класса 404), получатель просит телефон отправителя загрузить заново.

### 11.1 Запрос: receipt `server-error` (found, `SendMediaErrorReceiptJob`)

| Вариант | Writer | Wire |
|---------|--------|------|
| Multi-device (собственный primary) | case 327 | `<receipt to=<own primary jid> id=<stanza id> type="server-error"><encrypt><enc_p>..</enc_p><enc_iv>..</enc_iv></encrypt><rmr jid=<chat> from_me="true\|false" [participant=..]/></receipt>` |
| Legacy | case 77 | `<receipt to=<chat jid> id type="server-error" [participant] category="peer">[<encrypt>..</encrypt>]</receipt>` (без `rmr`) |

`enc_iv` — 12 случайных байт; `enc_p` создаётся нативно (`JniBridge.jvidispatchOOOOO(0, stanzaId, model, mediaKey, iv)`) из сообщения, несущего stanza id. Нативная библиотека содержит HKDF info `WhatsApp Media Retry Notification`; AES-GCM с stanza id в качестве AAD и 32-байтовым ключом HKDF — inferred из 12-байтового IV и из реализации Baileys. Серверные свойства `mms4_media_retry_notification_encryption_enabled` и `mms4_server_error_receipt_encryption_enabled` — токены словаря (эффект inferred: управляют тем, отправляется ли `<encrypt>`).

### 11.2 Ответ: notification `mediaretry` (found, `MediaRetryNotificationHandler`)

```
<notification type="mediaretry" id=<stanza id> t=..>
  <rmr jid=<chat> from_me="true|false"/>
  <encrypt><enc_p/><enc_iv/></encrypt>            or   <error code="N"/>
  [<reporting><reporting_tag/><reporting_token v/></reporting>]
</notification>
```

| Шаг | Деталь |
|-----|--------|
| Проверка аккаунта | `rmr` от другого аккаунта логирует `cross-account-rmr` и отбрасывается, если не включён символ флага `PTV.A0F` |
| Поиск | сообщение по `(chat, id, from_me)`; не-медиа сообщения логируют `message is null or not media` |
| Дешифрование | нативно (`jvidispatchOOOOO(3, stanzaId, enc_p, mediaKey, enc_iv)`); модель результата даёт `directPath` (сохраняется в сообщение) и int результата |
| Результат | `<error code>` переопределяет результат; обработчик сравнивает значение с 2 и 3 (при публичной нумерации proto `NOT_FOUND` = 2, `DECRYPTION_ERROR` = 3, inferred) |
| Продолжение | загрузчик получает новый direct path (`resume reuploading download`); при отсутствии активного загрузчика сообщение ставится в очередь на автоскачивание |
| Reporting | при флаге **5718** `reporting_token` сохраняется для сообщения |

---

## 12. View-once и status media

| Тема | Факт (found) |
|------|--------------|
| Криптография / транспорт | идентичны обычному медиа: тот же `MmsType`, тот же HKDF, те же URL; типа view-once в таблице нет |
| Флаг | `viewOnce` — поле в `ImageMessage` (**25**), `VideoMessage` (**20**), `AudioMessage` (**21**); контейнер `viewOnceMessage` (**37**), `viewOnceMessageV2` (**55**), `viewOnceMessageV2Extension` (**59**) |
| Локальные правила | отправитель не может открыть собственное view-once медиа (`senders can not view their own media`); миниатюры view-once удаляются `EphemeralUpdateRunnable/deleteViewOnceThumbnails`; view-once аудио без media key не отправляется (`unable to send encrypted media message due to missing mediaKey`) |
| Удаляет ли сервер объект после просмотра | unknown |
| Status (`status@broadcast`) | использует обычные строки `MmsType` (image, video, gif, audio) со своими числовыми id; HKDF info для `status` не существует; единственные типы `*-status` — типы newsletter (раздел 13) |
| Лимиты status | токены словаря `status_video_max_duration`, `status_video_max_bitrate`, `status_image_max_edge`, `status_image_quality` — серверные свойства (значения: unknown) |
| Скачивание status | `C59526QnY` содержит вариант `MediaDownload` и вариант `StatusMediaDownload`; оба строят URL одним генератором |

---

## 13. Медиа newsletter (каналов)

| Аспект | Newsletter | Обычное |
|--------|-----------|---------|
| Surface в URL | `newsletter` | `mms` |
| `MmsType` | `newsletter-image`, `-video`, `-ptt`, `-ptv`, `-audio`, `-document`, `-gif`, `-sticker`, `-sticker-pack`, `-music-artwork`, `-image-status`, `-video-status`, `-gif-status`, `-audio-status`, `-thumbnail-*` | простые имена |
| Шифрование | нет: загрузчик artwork требует `artworkEncSha256` только для не-newsletter контента (`required fields missing - artworkEncSha256 is null for encrypted content`); для остальных типов существует passthrough-поток `C59535Qnh` (identity). Строки `MmsType` всё же несут байты HKDF info (не используются, inferred) |
| Токен загрузки | случайный, не привязан к хешу (раздел 8.2) | секрет установки + хеш |
| Фильтр маршрута | нет логики hot / hash bucket для имён, начинающихся с `newsletter` | логика bucket (9.2) |
| `media_conn` ip token | `ip_token` применяется для newsletter независимо от `set_ip_token` (флаг **12149**) | только когда `set_ip_token` равен true |
| Работа сервера | `server_thumb_gen=1` (флаги **11191**, **11192**), `server_transcode=1` для видео (флаг **9096**) | не устанавливается |
| Флаг **27920** | читается в newsletter-пути `C15490gQ`; эффект unknown | |

---

## 14. Express path и другие варианты загрузки

| Вариант | Свидетельство |
|---------|---------------|
| Express path | `MediaNotifyMessage` (`expressPathUrl`, `fileEncSha256`, `fileLength`) отправляется как E2E-сообщение (`FMessageMediaExpressPathNotify`, требует url, хеш и длину); `ExpressPathDownload` логирует `EP gain <ms> <bytes>`; лог загрузки `Use static route supplier for express path upload`; результат загрузки 27 `SKIPPED_EP_NO_PRIMARY_HOST`. Поведение на стороне сервера: unknown |
| Оптимистичная загрузка | surface `optimistic`; повторная проверка хеша — результаты 12; протокол: unknown |
| History / app state | `md-msg-hist`, `md-app-state` используют обычный конвейер со своими info-строками |
| Group history | `group-history`, info `Group History`, mime `application/protobuf` проверяется получателем (`C34677F2y`); путь следует разделу 8.1 (`/mms/group-history/...`, inferred из общей композиции) |

---

## 15. Нативное усиление парсеров медиа (found, строки и экспорты распакованных библиотек)

81 shared object распаковывается из архива superpack. Небезопасные по памяти парсеры байт, контролируемых атакующим, либо изолированы в песочнице, либо заменены Rust.

| Вход | Компонент | Усиление |
|------|-----------|----------|
| WebP | `libstatic-webp.so` (43 KB) | libwebp, скомпилированный в WebAssembly и преобразованный в C через wasm2c (`w2c_$webp.wasm_webp_decode_premul_helper`, `wasm2c_$webp.wasm_instantiate`), обёртка `whatsapp::security::LibwebpSandbox` в thread-local песочнице; Java-флаг `sWebPSandboxEnabled`; лог сбоя `sandboxed WebP decode failed: status=%d`; защиты `Malloc returned pointer outside the sandbox memory` |
| GIF | `libwa_sandboxed_gifimage.so` | giflib в песочнице wasm2c / WASI-minrt (`GiflibSandbox`, `wasi::minrt`); JNI-классы `SandboxedGifImage`, `SandboxedGifFrame`; защита `Called memcpy for memory larger than the sandbox` |
| Файлы Ogg / Opus | `libwhatsapp.so` | песочницы RLBox wasm2c для `libogg.wasm` и `opusfile.wasm` (`rlbox_wasm2c_sandbox`), `SandboxedOpusMultistreamDecoder`, `wa_ogg_opus::SandboxedOggFile`; JNI `opusSetSandboxingEnabled`; лог trap `wasm2c sandbox trap: %s (code=%d)` |
| Разбор контейнеров и потоков | Rust-крейты `libwhatsapp.so` | `libmp4operations-rs` (tkhd, mvhd, mdhd, stsc, stts, stz2, ctts, hvcc, clap, sidx, emsg, mfhd, hdlr, DASH segmenter, edit lists), `libwamediastreams-rs` (amr, av1 OBU, flac, h264, h265, mp3 / ID3, ogg, opus, qcelp, speex, theora, vorbis, vp8, xmp, avc SPS), `libwaimageoperations-rs` (exif, gif, jpeg, png, webp), `libwamediacommon-rs` (`jpegrepair.rs`, `errorcodes.rs`), `libwamediaprovenance-rs` (значения IPTC digital-source-type, такие как `trainedAlgorithmicMedia`, C2PA) |
| Декодирование AV1 | `libdav1d.so` | dav1d **1.5.1** (строка версии); экспортирует API `dav1d_*` |
| Кодирование AV1 | `libwzav1.so` | версия 2.3.1; экспортирует только `wz_encoder_*` и `wz_codec_version*`; символов декодера нет, поэтому удалённые битстримы он не разбирает |
| Кадры H.264 / H.265 | платформенный `MediaCodec` | вне приложения |

Парсеры на Rust при ошибках паникуют (`assertion failed: ...`, `While parsing field '...' in ...`) вместо повреждения памяти: found как строки, эффект inferred. Песочница `rlbox` покрывает libogg и opusfile в `libwhatsapp.so`; остальные библиотеки используют wasm2c без обёртки RLBox (inferred из символов). Доходит ли каждый путь входящего медиа до этих парсеров до взаимодействия пользователя: unknown. Динамическое поведение (fuzzing, runtime-краши): не тестировалось.

---

## 16. Feature flags (id как прочитаны в местах вызова; имена не разрешены)

| Флаг | Где | Что управляет |
|------|-----|---------------|
| **149** | `RouteSelector`, `C43951qe` | сохранение и перезагрузка `media_conn` в preferences |
| **257** | конструктор `Mms4RouteSupplier` | объект экспоненциального backoff |
| **258** | `Mms4RouteSupplier.A03` | int: дополнительные попытки для режима 0 |
| **2134** | `A02` | bucket скачивания на основе хеша |
| **2136** | `A02` | окно hot-контента (long) |
| **4073** | `A00` | маршрутизация медиа через пользовательский proxy |
| **4836** | `Mms4DownloadUrlGenerator` | список типов с низким hit rate (`_nc_map=whatsapp-nofna`) |
| **5718** | `MediaRetryNotificationHandler` | обработка reporting token |
| **9096** | `QBE` | `server_transcode=1` (видео newsletter) |
| **11191** / **11192** | `C14210e6.A08` | `server_thumb_gen=1` для изображения / видео newsletter |
| **12149** | `RouteSelector.A0L`, `A03` | использовать `ip_token` |
| **12545** / **12446** | `A05` | переопределить лимит попыток после попытки 3 |
| **13748** | `QKS.A08` | повторять HTTP 408 |
| **17404** | `QBE` | `_nc_cbep=1` |
| **21807** | точки входа `RouteSelector` | boolean, передаваемый в выбор маршрута как флаг загрузки (семантика не разрешена) |
| **24661** | `MediaCryptoProvider` | проверка домена ключа non-E2EE |
| **29305** | `PlainDownloadTransfer` | обработка 416 |
| **37982**, **38437** | `C43481Ixw` | свойство Tigon, таймаут запроса |

---

## 17. Baileys (`baron-baileys-v2`, исходный код прочитан, ничего не тестировалось)

| Аспект | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Запрос `media_conn` | `<media_conn/>`, `w:m`, `set`, `s.whatsapp.net`; в `Socket/chats.js` есть необязательный вариант с `last_id` | всегда `<media_conn>`, с `last_id`, когда есть предыдущий id |
| Разбираемые поля | `hostname`, `maxContentLengthBytes`, `auth`, `ttl` | `maxContentLengthBytes` не читается; добавлены `auth_ttl`, `max_buckets`, `is_new`, `id`, fallback-поля, дочерние узлы возможностей, счётчики retry, `ip_token` |
| Длина HKDF | `hkdf(key, 112, {info})`, использует байты 0-79 | 80 байт; первые 80 байт выхода HKDF не зависят от запрошенной длины, поэтому IV, ключ шифра и ключ MAC идентичны |
| Info-строки | `WhatsApp <X> Keys`; `gif` и `ptv` соответствуют Video, `ptt` — Audio, `sticker` — Image | те же строки и соответствия |
| Шифр, MAC, хеши | AES-256-CBC, `HMAC-SHA256(macKey, iv + ct)[0:10]` дописывается, `fileSha256`, `fileEncSha256` от `ct + mac` | то же |
| URL загрузки | `https://{host}{MEDIA_PATH_MAP[type]}/{hash}?auth={auth}&token={hash}` | `https://{host}/{surface}/{type}/{hash}?direct_ip=..&token=..&auth=..` |
| Кодирование хеша | url-safe base64, дополнение `=` убрано, затем `encodeURIComponent` | url-safe base64, дополнение `=` сохранено |
| Токен | url-safe `fileEncSha256` | `SHA-256(installSecret || fileEncSha256)` (newsletter: случайный) |
| Таблица путей | `sticker` и `thumbnail-link` в `/mms/image`, `ptv` в `/mms/video`, `md-msg-hist` в `/mms/md-app-state`, нет `ptt` | строка `MmsType` — сегмент пути: `sticker`, `thumbnail-link`, `ptv`, `md-msg-hist`, `ptt` |
| Заголовки | `Content-Type: application/octet-stream`, `Origin: https://web.whatsapp.com` | `Origin` не найден; `Host`, `Accept-Encoding: identity`, `User-Agent`, `X-FB-*` |
| Retry | пробует каждый хост по одному разу по порядку | route supplier с попытками, подмена токена при 401 / 403, resume probe |
| Resume | не найдено (`resume=1`, `Content-Range` отсутствуют) | probe `resume=1` и `Content-Range` |
| Sidecar | генерации `streamingSidecar`, `firstScanSidecar` или `scansSidecar` в `src` не найдено | генерируются для видео, аудио, прогрессивных изображений |
| `mediaKeyTimestamp` | `unixTimestampSeconds()` | внутри миллисекунды, в proto секунды |
| Retry receipt | `<receipt id to=<own jid> type="server-error"><encrypt>..</encrypt><rmr jid from_me [participant]/></receipt>`, GCM, AAD = stanza id, IV 12 байт, HKDF info `WhatsApp Media Retry Notification` | writer case 327 имеет ту же раскладку узла; IV 12 байт и info-строка found; GCM / AAD inferred |
| Карта результатов retry | `SUCCESS` 200, `DECRYPTION_ERROR` 412, `NOT_FOUND` 404, `GENERAL_ERROR` 418 | неприменимо (сравнивает значения 2 и 3) |

Практические следствия (только чтение кода): загрузка объекта `md-msg-hist` через Baileys использует иную строку пути, чем клиент Android; base64 с дополнением в пути — видимое отличие; допускает ли сервер эти варианты: unknown.

---

## 18. Случаи ошибок

| Симптом | Причина | Решение |
|---------|---------|---------|
| Загрузка 401 / 403 | `auth` истёк или заменён | обновить `media_conn`, отправить заново с новым `auth` |
| Загрузка не возвращает `direct_path` | загрузка отклонена или не завершена | проверить статус; resume probe с `resume=1` |
| Скачивание 404 / статус 5 `too_old` | объект истёк на CDN | отправить receipt `server-error` (раздел 11) |
| `hash_mismatch` (7) / `enc_hash_mismatch` (32) | повреждённые байты или неверный `fileEncSha256` | скачать заново; проверить источник хеша |
| Проверка MAC не проходит | неверный media key, неверный HKDF info (путаница типов) или обрезанный файл | использовать info-строку нужного `MmsType`; не применять Image info для строк `sticker-pack` или `ptt` |
| `invalid_url` (8) | хост вне allow-list CDN | принимать только перечисленные суффиксы |
| `throttle` (12), HTTP 507 | серверный throttle | ждать `backoff` секунд (максимум 10800) |
| `no_route` (11) | нет пригодного хоста `media_conn` для типа | запросить `media_conn`, проверить теги возможностей |
| `failed_no_media_key` (29), `no_sidecar` (30) | отсутствует поле proto | требовать `mediaKey`; sidecar только для streaming |

---

## 19. Ключевые различия

| Не путать | Факт |
|-----------|------|
| список хостов `media_conn` vs URL загрузки | IQ даёт хосты и один `auth`; путь URL, токен и query строятся на каждую передачу |
| `auth` vs `token` | `auth` — токен уровня аккаунта из `media_conn`; `token` — на файл |
| HKDF 80 vs 112 байт | те же ключи; Android выводит 80 |
| `fileSha256` vs `fileEncSha256` | хеш открытого текста vs хеш `ciphertext + mac10` |
| `fileEncSha256` в пути vs `directPath` | путь загрузки использует хеш; скачивание использует `directPath`, возвращённый сервером |
| `mediaKeyTimestamp` vs окно повторного использования ключа | метка времени в секундах на wire; окно повторного использования 2-3 дня у отправителя |
| Streaming sidecar vs `fileEncSha256` | 10-байтовые MAC на чанк vs хеш всего файла |
| Media retry vs повторная отправка | отправитель заново загружает тот же объект и отвечает новым `directPath`; сообщение не отправляется повторно |
| Медиа newsletter vs обычное медиа | не шифруется, surface `newsletter`, случайный токен |
| `libwzav1` vs `libdav1d` | кодер vs декодер; удалённые данные разбирает только декодер |

---

## 20. Полный flow (отправка и получение одного изображения)

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

## 21. Unknowns

| Элемент | Статус |
|---------|--------|
| Поведение сервера (проверка токена, дедупликация, время жизни объекта, удаление view-once) | на стороне сервера |
| Имена query `_nc_cbep`, `_nc_rmr`, `type`; флаг **21807** и id `PTU.*` | имена или смысл не разрешены |
| Числовые id в `MmsType` (1, 20, 23, 25, 37, 42, 44, 57, ...) | смысл не разрешён |
| Нативный шифр media-retry (AES-GCM, AAD, длина ключа) | info-строка found; алгоритм inferred |
| Потребление `ip_token`, значение `X-FB-nc-oc`, источник `Companion_User_Secret` | не разрешено |
| Использование домена ключа NON_E2EE media | не разрешено |
| Протоколы express path и оптимистичной загрузки | не разрешено |
| Точный порядок хостов по попыткам и зависящие от режима числа попыток | декомпилированный control flow запутан |
| Какое входящее медиа доходит до какого изолированного парсера до взаимодействия пользователя | не сопоставлено |
| Трафик | ничего не перехвачено; динамического теста нет |
