<!-- src-sha1: 95a792ca8e841aadc06a8e3fae785590574c4eba -->
# WhatsApp Noise Transport — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-23
**Область:** транспорт чатов Android (chatd): эндпоинты и последовательность подключения, edge-маршрутизация, TCP-фрейминг, рукопожатие Noise XX / IK / PQ, проверки цепочки сертификатов, ClientPayload (UserAgent, DevicePairingData, connect type / reason), транспортный шифр и счётчики, бинарное кодирование узлов, результат логина и коды ошибок, keepalive, backoff при переподключении, stream:error, feature-флаги, смежные транспорты (Tigon HTTP, DistribGW, канал Tigon Noise, MQTT), сравнение с Baileys

---

## 1. Что это (технически)

chatd — единственное долгоживущее соединение, по которому идёт каждая stanza (сообщения, квитанции, IQ, presence, уведомления). На Android это обычный TCP-сокет (не WebSocket), на котором выполняется рукопожатие Noise, затем AES-GCM-фреймы с префиксом длины, каждый из которых содержит один бинарно закодированный узел. Все утверждения основаны на статическом анализе декомпилированного APK; на проводе ничего не перехватывалось. Уровни: **found** = прочитано в коде, **inferred** = выведено, **unknown** = не выяснено. Обфусцированные имена привязаны к сборке и заново определены в 2.26.41.6.

| Слой | Имя в 2.26.41.6 | Роль |
|------|-----------------|------|
| Поток соединения | `HandlerThreadC12340b0` (тег лога `ConnectionThread`) | подключение, рукопожатие, логин, цикл чтения, отключение |
| Последовательность подключения / DNS | `C37151de` (состояния), `C37031dS` (`A0G` переход, `A0D` фабрика сокетов), `C36881dC`, `AbstractC47101wK` (жёстко заданная таблица хост → IP), `C36821d6` (запасные IP) | какой хост / порт / прокси следующий |
| Драйвер рукопожатия | `C38791hg` (логи `NoiseSocket/*`) | вводные байты, ClientHello, ServerHello, проверки сертификатов, ClientFinish |
| Состояние Noise | `C38921hv` (+ `C38941hx` хеш, `C38981i2` AES-GCM, `AbstractC38961i0` HKDF), `C40331kf` (транспортные ключи + счётчики) | чистая Java |
| Ввод-вывод фреймов, кодек узлов | `C38891hs` / `C38901ht`; `C40411kn` (кодировщик), `C24610wf` (декодер), `AbstractC40911lb` (словарь) | фрейминг, бинарный XML |
| Proto | `C39211ii`, `C39161id`, `C39231ik`, `C39241il` (рукопожатие); `C24843Amz`, `C24842Amy`, `C24841Amx`, `C25757B9r`, `BC0` (сертификаты); `C38001fP`, `C38051fp`, `C38661hS` (payload) | сообщения на проводе |
| Доверие, PQ | `AbstractC44011qk` (закреплённый корень); `C38811hi`, `AbstractC38821hj`, `AbstractC38831hk`, `C38761hd` (конфигурация PQ, статические ключи сервера) | идентичность сервера, гибрид ML-KEM-512 |
| Сборщик payload | контрибьюторы в `AbstractC43901qZ`, собираемые `C37991fK` | ClientPayload |
| Keepalive, таймеры, переподключение | `C14U` (`ClientPingManager`), `C9EN` (ping IQ), `HandlerC21850s9`, `C11380Yq` (`MessageHandler`), `C0X9` (backoff) | ping, таймауты, повторы |
| Входящее управление | `C40581l4` (`<ib>`), `C40601l6` / `C37961fH.A1B` (`stream:error`) | уведомления сервера |

Пункты, определяющие остальную часть отчёта:

- Конечный автомат Noise, HKDF, AES-GCM и кодек фреймов написаны на **Java**. Нативными являются только Curve25519 (`org.whispersystems.curve25519`, `OpportunisticCurve25519Provider`, нативный код с запасным вариантом на Java) и вызовы ML-KEM (`KEMKeyPair.generateNative`, `KEMSecretKey.decapsulateNative`). Нативной реализации chatd для реверса нет (found).
- Вводный заголовок в этой сборке — константа `WA 06 03` (раздел 3.1). Целое число версии протокола, передаваемое в `C38791hg`, жёстко задано равным 6 в единственном месте вызова, поэтому ветка с плоским сертификатом версии 5 на практике недостижима (found; достижимость inferred по единственному вызову с константой).
- `devicePairingData` отправляется только соединением без user JID, которое `ConnectionThread` допускает лишь при регистрации companion-устройства. В этой сборке это не артефакт регистрации основного телефона (раздел 6.4).
- Исходящие stanza на основном пути отправки сжимаются DEFLATE (флаги `3`), а не только входящие (раздел 8.1).

---

## 2. Эндпоинты и последовательность подключения

### 2.1 Хосты и порты (found)

| Хост | Где | Примечания |
|------|-----|------------|
| `g.whatsapp.net` | `C37151de` шаги 5, 9; `C36881dC.A01` (жёстко заданные IP) | основной хост чата |
| `g-fallback.whatsapp.net` | шаги 13, 14 | второй хост |
| `e1` ... `e16.whatsapp.net` | `C37151de.A0F` (16 записей), шаги 7 и 11 | `ConnectionSequence/getEdgeHost`; случайный выбор либо хост из истории |
| жёстко заданная таблица IP | `AbstractC47101wK.A00`, шаги 6 и 10 | отображение хоста в список IP, охватывает хосты `eN` и `g.whatsapp.net` |
| список `<ib><fbip>` | `C40581l4` в `C36821d6.A02` | IP через запятую, сохраняются менеджером запасных адресов (вход для шагов 2 / 8, inferred) |
| пользовательский прокси / SOCKS | шаг 12, `C48201yM` | `java.net.Proxy.Type.SOCKS`, таймаут подключения 30000 мс |

Порты: 443 и 5222 (случайный выбор на каждую попытку, `C37151de.A00`; конструктор также бросает одну монету, задающую порядок портов для шагов 3 и 4) и 80 для шагов `:80`. Порт последнего успешного подключения переиспользуется, когда включён флаг **33512** (found).

### 2.2 Состояния последовательности (found, `C37151de.A02`, переход в `C37031dS.A0G`)

| Шаг | Цель |
|-----|------|
| 0 | старт, выбирает первый применимый шаг |
| 1 | отладочный / переопределённый `InetSocketAddress` (терминальный) |
| 2 | записи эндпоинтов от сервера с установленным битом `A04` (список `A0A`), по одной; каждая запись несёт собственный TLS-бит `A05` |
| 3, 4 | настроенная строка хоста `A07` на двух портах (443 / 5222 в случайном порядке) |
| 5 | `g.whatsapp.net` на 443 (флаг **20801**) либо случайный 443 / 5222 |
| 8 | записи от сервера без бита `A04` (список `A09`); порядок ветвей в декомпилированном коде неясен |
| 9 | `g.whatsapp.net:80` |
| 15 | HISTORY: повтор шага / хоста / порта, сохранённых последним успехом (вставляется после 9, когда шаг истории валиден и флаг **22916** выключен) |
| 13, 14 | `g-fallback.whatsapp.net` на 443 / 5222, затем `:80` |
| 6, 10 | жёстко заданный IP для `g.whatsapp.net`, затем `:80` |
| 7, 11 | случайный edge-хост `eN.whatsapp.net`, затем `:80` |
| 12 | пользовательский прокси (терминальный) |
| 16 | исчерпано |

Порядок после шага 9 (found): 9, [15], 13, 14, 6, 10, 7, 11, 16. Последний успех сохраняется в preferences `last_successful_connection_step`, `_host`, `_port` (found, `C37031dS.A00`). Шаги 2–4 пишут в лог `Skipping sequence ... due to active proxy`, пока активна конфигурация сервиса SOCKS и флаг **23630** выключен (семантика пропуска inferred).

### 2.3 Сокет (found, `C37031dS.A0D`)

| Аспект | Значение |
|--------|----------|
| Сокет | обычный TCP; Happy Eyeballs, когда существуют адреса и IPv4, и IPv6 (`ConnectionSocketFactory/try_connect/using-happyEyeball`) |
| TLS-обёртка | бит конфигурации `A07` выбирает `SSLSocketFactory`; задаётся для каждой записи от сервера (`A05`), для шага 1 на порту 443 и для edge-хостов (шаг 7) на порту 443. Шаг 5 (`g.whatsapp.net`) создаётся с выключенным битом |
| Таймаут сокета | 30000 мс, задаётся через `CeF(30000)` (семантика inferred: таймаут чтения) |
| TCP keepalive | `configureTcpKeepalive`: когда флаг **7831** включён и сокет это поддерживает, keepalive включается и применяются три целых числа из флагов **7832** (по умолчанию 2), **7833** (по умолчанию 10), **7834** (по умолчанию 10) (idle / interval / count по выводу) |
| Буферизация вывода | когда флаг **33751** включён, writer оборачивается в `BufferedOutputStream`, чтобы вводные байты и ClientHello уходили одной записью (found) |

То, несут ли эндпоинты с TLS-обёрткой внутри TLS те же байты Noise, выведено из пути кода (`C38791hg` получает только потоки); метрика с именем `chatd_non_secure_tls_wrapper_resumption` существует в нативной библиотеке.

### 2.4 DNS-резолвинг (found)

`DNSResolutionMethod` сообщается в `ClientPayload.dnsSource` (раздел 6.5): `SYSTEM`, `GOOGLE`, `HARDCODED`, `OVERRIDE`, `FALLBACK`, `MNS`, `MNS_SECONDARY`, `SOCKS_PROXY`. Флаг **13545** (строка; значения `secondary`, `hardcoded`, `none` распознаются в `C37151de.A01`) настраивает цепочку резолверов. Кэшированные ответы прежних запросов используются до истечения срока, прежде чем выполняется новый запрос (`C36881dC.A03`).

---

## 3. Фрейминг

### 3.1 Байты перед первым фреймом (found, `C38791hg`)

```
[ 'E' 'D' 00 01 | len24 | routing_info ]     only when routing_info is non-empty
[ 'W' 'A' 06 03 ]                             always
[ len24 | HandshakeMessage{clientHello} ]     first frame
```

- Edge-заголовок: магическое значение `45 44 00 01` (`C38791hg.A0B`), 3-байтовая длина блоба в big-endian, затем байты `routing_info` (preference, base64 без паддинга и переносов; сохраняется `C38801hh.A00`, максимум 256 байт: "The routing info should be smaller than 256 bytes."). Отправляется как есть в сокет, вне транскрипта Noise.
- Intro: `57 41 06 03` = "WA", протокол 6, словарь 3 (`C38791hg.A04`); также пролог Noise (4.2). Ветка else возвращает `57 41 05 03`, но конструктор фиксирует версию 6.

### 3.2 Структура фрейма (found)

Каждый фрейм — это 3-байтовая длина в big-endian (`AbstractC38721hZ.A04` / `A00`; записываемое значение должно быть меньше 2^24, иначе `data too large to write`), за которой следует тело: protobuf рукопожатия во время рукопожатия, шифртекст AES-GCM после него.

Читатель (`C38891hs`): ровно 3 байта длины, затем тело. При чтении ServerHello три байта длины, равные ASCII `GOA` (`47 4F 41`, `C38891hs.A01`), приводят к исключению `X.1sn` (лог `socket/goaway`); путь чтения после рукопожатия (`C24610wf.Be0`) такой проверки не имеет. Пустые расшифрованные фреймы пропускаются; расшифрованный фрейм в 1 байт бросает `header only frame received`. Stanza больше необязательного лимита размера (`InterfaceC40421ko.AqJ`) бросает `C31990DyW` при кодировании.

### 3.3 Сообщения рукопожатия (found, номера полей из protobuf-классов)

| Сообщение (класс) | Поля (номер выделен) |
|-------------------|----------------------|
| `HandshakeMessage` (`C39211ii`) | clientHello **2**, serverHello **3**, clientFinish **4** |
| `ClientHello` (`C39161id`) | ephemeral **1**, static **2**, payload **3**, useExtended **4**, extendedCiphertext **5**, paddedBytes **6**, sendServerHelloPaddedBytes **7**, simulateXxkemFs **8**, pqMode **9**, extendedEphemeral **10** |
| `ServerHello` (`C39231ik`) | ephemeral **1**, static **2**, payload **3**, extendedStatic **4**, paddingBytes **5**, extendedCiphertext **6** |
| `ClientFinish` (`C39241il`) | static **1**, payload **2**, extendedCiphertext **3**, paddedBytes **4**, simulateXxkemFs **5** |

Сеттеры, замеченные в драйвере: полный ClientHello XX задаёт `ephemeral` (+ `pqMode` в PQ-вариантах); ClientHello при возобновлении задаёт `ephemeral`, `static`, `payload`, `extendedCiphertext`, `extendedEphemeral`, `pqMode`; ClientFinish задаёт `static`, `payload`, `extendedCiphertext`. Поля padding и simulate определены, но сеттеров в драйвере не найдено (назначение unknown).

---

## 4. Рукопожатие Noise

### 4.1 Имена паттернов (found, статические поля `C38921hv`)

| Константа | Имя | Когда используется |
|-----------|-----|--------------------|
| `A07` | `Noise_XX_25519_AESGCM_SHA256` (дополнено NUL до 32 байт) | полное рукопожатие, PQ none |
| `A0H` | `Noise_IK_25519_AESGCM_SHA256` (дополнено до 32) | возобновление с кэшированным статическим ключом сервера, PQ none |
| `A06` | `Noise_XXfallback_25519_AESGCM_SHA256` | IK отклонён сервером (4.4) |
| `A0E`, `A0C`, `A08` | `Noise_XXkem_`, `Noise_XXkem-FS_`, `Noise_XXkemEph_` + `25519_MLKEM512_AESGCM_SHA256` | полное, PQ включён |
| `A0F`, `A0D`, `A0G` | `Noise_IKkem+`, `Noise_IKkem-FS+`, `Noise_IKkem2+` + `X25519+MLKEM512+AESGCM256+SHA256` | возобновление, PQ включён |
| `A09`, `A0B`, `A0A` | `Noise_XXkemfallback_`, `Noise_XXkem-FSfallback_`, `Noise_XXkemEphfallback_` + `25519_MLKEM512_AESGCM_SHA256` | PQ-фолбэки |

Имя длиннее 32 байт хешируется SHA-256, иначе начальным хешем служит 32-байтовое дополненное значение (found, конструктор `C38921hv`).

Конфигурация PQ (`NoisePQConfig`): режим `NONE` / `ENABLE` / `ENFORCE` (флаг **20161**, int: 1 enable, 2–4 enforce, иначе none); вариант `IKKEM`, `IKKEM_FS`, `XXKEM_EPH_IKKEM2`, `XXKEM_EPH_ONLY` (флаг **34536**, строка, по умолчанию `IKKEM`). Полное рукопожатие: режим PQ `NONE` использует `A07`; иначе вариант `IKKEM_FS` выбирает `A0C`, `XXKEM_EPH_ONLY` и `XXKEM_EPH_IKKEM2` выбирают `A08`, `IKKEM` выбирает `A0E` (found в конструкторе `C38791hg`). Имена `IKkem*` относятся к пути возобновления; их точное отображение на варианты не прослежено.

### 4.2 Симметричное состояние (found, `C38921hv`)

```
h  = name (padded, or SHA256(name) if > 32 bytes)         // C38941hx.A00 = name
ck = h                                                    // A02
h  = SHA256(h || prologue)                                // prologue = WA 06 03
mixHash(d):  h = SHA256(h || d)
mixKey(dh):  okm = HKDF-SHA256(salt = ck, ikm = dh, info = none, 64)
             ck  = okm[0:32] ; k = AES-256-GCM key okm[32:64] ; n = 0
encrypt(p):  c = AES-GCM(k, iv = 00000000 || n_be64, aad = h, p) ; n++ ; mixHash(c)
decrypt(c):  p = AES-GCM(k, iv = 00000000 || n_be64, aad = h, c) ; n++ ; mixHash(c)
             (no key yet: encrypt / decrypt pass through and only mixHash)
split():     okm = HKDF-SHA256(salt = ck, ikm = empty, info = none, 64)
             sendKey = okm[0:32] ; recvKey = okm[32:64]
```

HKDF написан вручную (`AbstractC38961i0`): extract = `HMAC(key = salt, data = ikm)`, expand с однобайтовым счётчиком. IV: 12 байт, первые 4 нулевые, последние 8 — счётчик в big-endian (`AbstractC38721hZ.A02`). Тег 128 бит (GCM в стиле BouncyCastle `C39061iT`). DH — это Curve25519 `calculateAgreement` через `C38851hm.A00("best")`.

### 4.3 Полная последовательность XX (found)

| # | Направление | Содержимое | Операции над состоянием |
|---|-------------|------------|-------------------------|
| 1 | C to S | `ClientHello{ephemeral}` (+ `pqMode` в PQ-вариантах) | `mixHash(e_c)` |
| 2 | S to C | `ServerHello{ephemeral, static, payload}` | `mixHash(e_s)`; `mixKey(DH(e_c, e_s))`; `s_s = decrypt(static)`; `mixKey(DH(e_c, s_s))`; `cert = decrypt(payload)` |
| 3 | локально | проверки сертификата (раздел 5) | ключ в cert должен совпадать с `s_s` |
| 4 | C to S | `ClientFinish{static, payload}` | `static = encrypt(s_c)`; `mixKey(DH(s_c, e_s))`; `payload = encrypt(ClientPayload)` |
| 5 | локально | split | `sendKey`, `recvKey`, оба счётчика 0 |

Порядок в `C38791hg.A03` (smali) соответствует стандартному транскрипту XX. Статический ключ клиента `s_c` и эфемерный ключ берутся из пар ключей `C38711hY`; статический предоставляется `C38771he.A01` (постоянный Noise-ключ клиента, "authKey" в логах отключения). То, что он равен ключу, загруженному при регистрации, — inferred.

### 4.4 Возобновление (IK) и фолбэк (found структура, детали шагов inferred)

Когда существуют кэшированные статические ключи сервера (`C38771he.A00` не null, `C38761hd`), драйвер пишет в лог `NoiseSocket/handshakeStart mode=... rs=...` и выполняет `handshakeResume`: кэшированный публичный статический ключ сервера хешируется в состояние (`C38921hv.A06`), ClientHello несёт эфемерный ключ, зашифрованный статический ключ клиента и зашифрованный `ClientPayload` в одном сообщении (раздел 3.3). Если сервер отвечает статическим ключом, в лог пишется `handshakeResume server hello has static key, falling back`, а `C38791hg` бросает `X.1t8` с ServerHello, что выбирает имена `Noise_XXfallback_*`. Точный транскрипт фолбэка — inferred по стандартному модификатору fallback в Noise. Статические ключи сервера сохраняются после успешного логина, если они изменились (`A1m`: классический ключ через `Ce3`, PQ-ключ через `Ce2`).

### 4.5 Постквантовый материал (found как присутствующий; детали на проводе частично unknown)

- KEM: ML-KEM-512 (строка алгоритма `MLKEM512`, `C38791hg.A0C`). TLV публичного PQ-ключа сервера: тип `0x02`, длина 800; заголовок TLV тип `0x01`, несущий имя алгоритма; TLV шифртекста FS тип `0x04`, длина 768 (из строк ошибок `Expected TLV PK type 0x02`, `length 800`, `Expected TLV header type 0x01`, `Expected FS ciphertext length 768`).
- Инкапсуляция (`C38921hv.A07`): `KEMPublicKey.A00()` выдаёт шифртекст + общий секрет; шифртекст идёт в `mixHash`, общий секрет — в `mixKey`. Декапсуляция: `KEMSecretKey.decapsulateNative`.
- Доставка: `<success static_pq_key="base64">` читается только когда режим PQ не `NONE` и вариант `IKKEM_FS` (`A18`); без него в лог пишется `handshake missing serverStaticPQ forcing full handshake` (`C38791hg.A01`).

Ширина поля длины TLV и точное размещение внутри `ServerHello.payload` не декодированы. Нативные функции ML-KEM происходят из классов Signal KEM; библиотека, которая их реализует, не определена.

---

## 5. Проверки сертификата сервера (found, `C38791hg.A03`)

Протокол версии 6 (единственное используемое значение) разбирает `ServerHello.payload` как `CertChain`:

`CertChain` (`C24843Amz`): leaf **1**, intermediate **2**. Каждый — `NoiseCertificate` (`C24842Amy`): details **1** (bytes), signature **2** (bytes). `details` разбирается как `Details` цепочки (`C24841Amx`): serial **1**, issuerSerial **2**, key **3**, notBefore **4**, notAfter **5**.

Проверки (префикс лога `wa6:`; порядок вычисления восстановлен не полностью, декомпилированный метод неполон):

1. Оба `details` разбираются как `Details` цепочки.
2. `intermediate.issuerSerial == 0` и `leaf.issuerSerial == intermediate.serial`.
3. `leaf.key` равен статическому ключу сервера из рукопожатия `s_s` ("noise certificate key does not match proposed server static key").
4. Подпись intermediate проверяется над `intermediate.details` закреплённым корневым ключом для издателя `WhatsAppLongTerm1` (`AbstractC44011qk.A00`).
5. Подпись leaf проверяется над `leaf.details` ключом `key` из intermediate.

`notBefore` / `notAfter` в пути цепочки не читаются. Сбой бросает `X.1so` (лог `socket/invalid-certificate-exception`).

Закреплённый корень (публичный ключ, found, `AbstractC44011qk.A01`): `142375574d0a587166aae71ebe516437c4a28b73e3695c6ce1f7f9545da8ee6b`.

Плоская форма (мёртвый код при константной версии 6): `NoiseCertificate{details = 1, signature = 2}` (`C25757B9r`), плоский `Details{serial = 1, issuer = 2, expires = 3, subject = 4, key = 5}` (`BC0`). Код проверяет единственную подпись закреплённым ключом по имени издателя, сравнивает `key` с `s_s` и отклоняет, когда `expires` (секунды) меньше текущего времени (лог `noise certificate expired`).

---

## 6. ClientPayload

### 6.1 Поля (found, `C38001fP`; номера из дескриптора)

| Поле | Номер | Тип | Кем задаётся в 2.26.41.6 |
|------|-------|-----|--------------------------|
| username | **1** | int64 | числовая часть user в JID логина (LID user для LID-логина) |
| passive | **3** | bool | флаг режима соединения из информации о сессии (7.2) |
| userAgent | **5** | `UserAgent` | 6.2 |
| webInfo | **6** | `WebInfo` | не задаётся прочитанными контрибьюторами |
| pushName | **7** | string | push name аккаунта, если не пуст |
| sessionId | **9** | int32 | id сессии на подключение (`C37121db`) |
| shortConnect | **10** | bool | `C11750a1.A03()` |
| connectType / connectReason | **12** / **13** | enum | 6.5 |
| shards | **14** | repeated int32 | не задаётся |
| dnsSource | **15** | message | `dnsMethod` **15**, `appCached` **16** |
| connectAttemptCount | **16** | int32 | число попыток к настоящему моменту |
| device | **18** | int32 | режим companion: preference `registration_device_id` |
| devicePairingData | **19** | message | 6.3 / 6.4 |
| product | **20** | enum | `WHATSAPP_LID` для LID-логина, иначе по умолчанию `WHATSAPP` |
| oc / lc | **23** / **24** | bool / int32 | `oc`: результат проверки сборки или подписи (`AbstractC38241gg`, имя не раскрыто); `lc`: preference `connection_lc` |
| pull | **33** | bool | **в этой сборке никогда не задаётся** (записи не найдено) |
| yearClass / memClass | **36** / **37** | int32 | эвристики класса устройства (`C38261gi`, `C38271gj`) |
| trafficAnonymization | **40** | enum | `STANDARD`, когда `C17830kT.A0L()`, иначе `OFF` |
| lidDbMigrated | **41** | bool | только с user JID и не companion |
| connectionSequenceInfo | **43** | int32 | счётчик 0–31, выводимый из шага последовательности |
| paaLink | **44** | bool | `C0NZ.A02()` |
| preacksCount / processingQueueSize | **45** / **46** | int32 | состояние очереди (флаги **20485** / **22413**) |
| pairedPeripherals | **47** | repeated string | `smart_glasses`, `garmin` |
| messageSts | **49** | int64 | временная метка последнего сообщения, если известна |

Определены, но здесь не задаются: fbCat **21**, fbUserAgent **22**, iosAppExtension **30**, fbAppId **31**, fbDeviceId **32**, paddingBytes **34**, interopData **38** (`accountId` **1**, `token` **2**, `enableReadReceipts` **3**), accountType **42**, testIsolationId **48**.

### 6.2 UserAgent (found, `C38051fp`)

| Поле | Номер | Значение в этой сборке |
|------|-------|------------------------|
| platform | **1** | `ANDROID` (0), константа |
| appVersion | **2** | `{primary 1, secondary 2, tertiary 3, quaternary 4}`, разобрано из `2.26.41.6` |
| mcc / mnc | **3** / **4** | `getNetworkOperator()`, по умолчанию `000` |
| osVersion / manufacturer / device / osBuildNumber | **5** / **6** / **7** / **8** | системные строки |
| phoneId | **9** | id уровня устройства (`C38141gV`) |
| releaseChannel | **10** | `BETA` (1) в этой бета-сборке; `RELEASE 0, BETA 1, ALPHA 2, DEBUG 3` |
| localeLanguageIso6391 / localeCountryIso31661Alpha2 | **11** / **12** | пропускаются для `zz` / `ZZ` |
| deviceBoard / deviceExpId | **13** / **14** | строка board, если не пуста; id эксперимента |
| deviceType | **15** | `PHONE`, `TABLET`, `DESKTOP`, `VR` по классу устройства |
| deviceModelType | **16** | |
| distributionChannel | **17** | не задаётся |

`UserAgent.Platform` (`EnumC38071fr`, 0–40): 0 ANDROID, 1 IOS, 10 SMB_ANDROID, 12 SMB_IOS, 13 WINDOWS, 14 WEB, 24 MACOS, 29 WEAROS, 33 IPAD, 35 SMART_GLASSES, 39 WORK_ANDROID, 40 WORK_IOS (остальные опущены).

### 6.3 DevicePairingRegistrationData (found, `C38661hS`)

Поля `DevicePairingRegistrationData`: eRegid **1** (4-байтовый registration id), eKeytype **2** (`05`), eIdent **3** (публичный identity-ключ), eSkeyId **4**, eSkeyVal **5**, eSkeySig **6** (id signed prekey, публичный ключ, подпись), buildHash **7**, deviceProps **8** (сериализованный `DeviceProps`).

`buildHash`: код вычисляет `Base64.decode(hexMD5("2.26.41.6"), 0)` (`C00L.A04` возвращает 32-символьный hex MD5 в нижнем регистре, который затем подаётся в декодер base64), что даёт 24 байта, а не 16-байтовый дайджест (found как прочитано).

`DeviceProps` (`C43105IrG`): os **1** (строка ОС), version **2** (`AppVersion`), platformType **3**, requireFullSync **4** (= true), historySyncConfig **5**. Блок history-sync собирается классом, который пишет в лог как `CompanionRegInfoProvider`; его поля (дни / лимиты размера полной синхронизации, недавняя синхронизация, синхронизация миниатюр, флаги поддержки, такие как журналы звонков, история ботов, история групп) управляются флагами **15284**, **15283**, **21217**, **20658**, **18953**, **26445**, **26614**.

### 6.4 Какой вариант отправляется (found)

- Логин, основное устройство (user JID известен): username, passive, userAgent, pushName, sessionId, shortConnect, connectType, connectReason, dnsSource, connectAttemptCount, connectionSequenceInfo, lc, oc, yearClass, memClass, trafficAnonymization, lidDbMigrated, messageSts, счётчики очереди, paaLink, pairedPeripherals; `product = WHATSAPP_LID` для LID-логинов.
- Логин, companion: то же плюс `device = registration_device_id`.
- Регистрация companion (user JID null): без username; `devicePairingData` (набор ключей + `DeviceProps`) и `device`.

`ConnectionThread/connect/ignored/jid null and not in companion reg` показывает, что null JID отклоняется вне регистрации companion. Основной телефон регистрируется по HTTPS `/v2/*` (см. отчёт по безопасности аккаунта); использования `devicePairingData` при регистрации основного устройства не найдено.

### 6.5 Используемые enum (found)

| Enum | Значения |
|------|----------|
| `ConnectReason` (`EnumC38391gv`) | 0 PUSH, 1 USER_ACTIVATED, 2 SCHEDULED, 3 ERROR_RECONNECT, 4 NETWORK_SWITCH, 5 PING_RECONNECT, 6 UNKNOWN |
| `ConnectType` (`EnumC38311gn`) | 0 CELLULAR_UNKNOWN, 1 WIFI_UNKNOWN, 100 EDGE, 101 IDEN, 112 HSPAP; остальные сотовые имена (UMTS, EVDO, GPRS, HSDPA, HSUPA, HSPA, CDMA, ...) берут номера из косвенных констант, которые не были разрешены |
| `Product` (`EnumC38561hI`) | 0 WHATSAPP, 1 MESSENGER, 2 INTEROP, 3 INTEROP_MSGR, 4 WHATSAPP_LID |
| `DNSResolutionMethod` (`EnumC38321go`) | 0 SYSTEM, 1 GOOGLE, 2 HARDCODED, 3 OVERRIDE, 4 FALLBACK, 5 MNS, 6 MNS_SECONDARY, 7 SOCKS_PROXY |

Connect reason в том виде, как записывается в этой сборке: по умолчанию `UNKNOWN`; когда временная метка информации о сессии укладывается в 10 с, состояние 1 даёт `USER_ACTIVATED`, состояние 2 даёт `PUSH`. Остальные значения определены, но этот контрибьютор их не выбирает.

---

## 7. После рукопожатия

### 7.1 Результат логина (found, `HandlerThreadC12340b0.A13`)

Первые входящие узлы читаются в цикле. `web` принимается, только если был отправлен web ref (иначе `web node given during login without any web ref provided`). Всё, кроме `web`, `success`, `failure`, бросает `unexpected node received during login sequence`.

Читаемые атрибуты `<success>`:

Читаемые атрибуты: `t` (время сервера в секундах, сохраняется; нечисловое значение бросает `invalid server time`), `props`, `abprops`, `mc_ep_version` (счётчики версий конфигурации), `lid` (LID аккаунта, сравнивается с сохранённым LID; несовпадение сообщает `lid-chatd-lid-mismatch`), `pn` (JID пользователя-телефона), `static_pq_key` (серверный PQ-ключ в base64, 4.5).

### 7.2 Пассивный и активный режим (found)

`passive` в payload берётся из информации о сессии (`C37981fJ.A0A`); поля лога `forcePassiveMode`, `enablePassiveModeBasedOnQueueSize`, `duplexActive`. После логина клиент выходит из пассивного режима set-IQ, построенным `AbstractC44071qq`:

```xml
<iq id="..." xmlns="passive" type="set" to="s.whatsapp.net"><active/></iq>   <!-- or <passive/> -->
```

Pre-ack отправляются первыми, если стоят в очереди (`ConnectionThread/send preacks`). Таймер 32000 мс (`HandlerC21850s9.A02`) запускается при отправке; если сигнал активности соединения не приходит, срабатывает причина 10 (`connection active timeout`).

### 7.3 Информационные бюллетени (found, `C40581l4`)

Обрабатываемые дочерние элементы `<ib>`: `edge_routing` (дочерний `routing_info`, сохраняется, раздел 3.1), `fbip` (IP через запятую в менеджер запасных адресов), `client_expiration` (`t`, секунды, переводятся в мс), `dirty`, `offline_preview`, `location`, `notice`, `recovery_nonce`, `safetynet`, `sonar` (`url`), `streamdebug`, `thread_metadata`, `gpia`, `age_experience`, `accept_paa_link`, `peer_device_presence`. `dns_domain` отсутствует (в клиенте Android его нет).

---

## 8. Бинарное кодирование узлов

### 8.1 Содержимое фрейма и флаги (found, `C40411kn.Csv`, `C24610wf.Be0`)

После расшифровки AES-GCM открытый текст начинается с одного байта флагов:

| Бит | Значение |
|-----|----------|
| `2` | остальное — поток zlib (DEFLATE); декодер распаковывает его и сохраняет байт флагов |
| `1` | фрагментация; декодер бросает `server to client stanza fragmentation not supported` |

Кодировщик: `Csv(node, flags)` при `flags & 2` сжимает (`DeflaterOutputStream`) и добавляет префикс `02`; иначе записывает байт флагов `00`. Основные пути отправки в `HandlerThreadC12340b0` и поток записи `HandlerThreadC21920sG` вызывают `Csv(node, 3)`, поэтому эти stanza сжимаются. `Csu(node)` (= флаги 1, без сжатия) вызывается из `C40851lV`, который выглядит как отправитель стадии логина (inferred). Маркер конца потока: `00` + list(1) + токен `02` (`Clp`, `xmlstreamend`).

### 8.2 Байты тегов (found)

| Байт | Имя | Тело |
|------|-----|------|
| 0 | пустой список / отсутствует | нет |
| 1, 2 | `xmlstreamstart`, `xmlstreamend` | декодер отклоняет их как строки |
| 3..235 | однобайтовый токен | индекс в таблице `A00` из 236 записей |
| 236..239 | словарь 0..3 | 1 байт индекса в `A01[tag - 236]` (по 256 записей) |
| 244 / 247 | JID_INTEROP / AD_JID | `user:str, device:u16, integrator:u16, domain:u8` / `domain:u8, device:u8, user:str` |
| 248 / 249 | LIST_8 / LIST_16 | `count:u8` / `count:u16` |
| 250 | JID_PAIR | `user:str or 00, server:str` |
| 251 / 255 | HEX_8 / NIBBLE_8 | `lenAndOdd:u8` + упакованные полубайты |
| 252 / 253 / 254 | BINARY_8 / _20 / _32 | `len:u8` / `len:u20` (3 байта) / `len:u32`, затем байты |

Тегов 245 и 246 в этом кодеке нет. Все многобайтовые целые — big-endian.

### 8.3 Структура узла (found, `C40411kn.A01`)

```
list(size)  description  (key value)*  [content]
size = 1 + 2 * attrCount + (content ? 1 : 0)
```

Нечётный размер означает отсутствие содержимого. Декодер: число атрибутов = `((size - 2) + size % 2) / 2`. Содержимое — либо байтовый блоб (`252 / 253 / 254`), либо список потомков. Узел с блобом и потомками одновременно бросает `more than one source of inner data`. Заголовок списка: 0 для пустого, 248 при менее чем 256 записях, 249 при менее чем 65536, иначе `list too long`.

### 8.4 Лестница строк (found, `C40411kn.A05` / `A06`)

| Слот | Порядок попыток |
|------|-----------------|
| description | токен, словарь, JID (если разбирается), UTF-8 с префиксом длины |
| ключ атрибута | токен, словарь, UTF-8 |
| значение атрибута | токен, словарь, JID, packed, UTF-8 |
| байты содержимого | сырой BINARY (`A06(bytes, false)`), никогда не токенизируется и не упаковывается |

Упаковка (`A06` с флагом packed, только значения атрибутов): длина меньше 128 и все символы из `[0-9-.]` даёт NIBBLE_8 (`255`; `0-9` = 0..9, `-` = 10, `.` = 11); длина меньше 128 и все символы из `[0-9A-F]` даёт HEX_8 (`251`); бит нечётной длины — `0x80` в байте длины. Длины от 256 и выше используют BINARY_20 до 1 МиБ, BINARY_32 сверх этого. Карта полубайтов в декодере: 10 `-`, 11 `.`, 12 `:` (кодировщик никогда не выдаёт 12).

### 8.5 JID (found, `C40411kn.A00`, `C24610wf.A02`)

| JID | Кодирование |
|-----|-------------|
| interop user (`C99O`, тип 22) | `244, user, device u16, integrator u16, 00`; декодируется в `{integrator}-{user}[:device]@interop` |
| interop group (`C55529Oy6`, тип 28, сервер `interop.g.us`) | `244, user, 0000, 0000, 02`; декодер требует device и integrator равных 0 |
| присутствует agent или device | `247, domainByte, device, user`; бит domainByte `1` = LID, бит `128` = hosted |
| иначе | `250, user (or 00), server` |

Отображение сервера AD_JID: `0` `s.whatsapp.net`, `1` `lid`, `128` `hosted`, `129` `hosted.lid`. Device `99` ожидается ровно тогда, когда установлен бит hosted; несовпадение логируется, и JID всё равно принимается. Несоответствующие JID бросают `failed to write jid`.

### 8.6 Словарь (found, `AbstractC40911lb`)

236 однобайтовых токенов (индекс 0 — null) и четыре словаря по 256 записей; версия словаря — последний вводный байт, `03`. Индексы, заново определённые в этой сборке:

| Токен | Индекс | Токен | Индекс |
|-------|--------|-------|--------|
| `s.whatsapp.net` | 3 | `iq` / `ack` / `message` | 25 / 27 / 19 |
| `type`, `id`, `from`, `to` | 4, 8, 6, 17 | `get` / `set` / `result` / `error` | 41 / 90 / 20 / 168 |
| `routing_info` / `edge_routing` | 39 / 40 | `urn:xmpp:ping` / `ping` / `w:p` | 43 / 86 / 87 |
| `handshake` / `success` | 53 / 76 | `stream:error` / `not-authorized` | 157 / 209 |
| dict 0: `active` / `conflict` / `replaced` / `passive` | 1 / 14 / 17 / 24 | dict 1: `dirty` / `server-error` / `pair-device` | 1 / 145 / 238 |
| dict 2: `failure` / `rate-overlimit` | 60 / 239 | `call` / `usync` / `w:m` | 100 / 121 / 194 |

Ряд токенов в таблице — это Java-константы, импортированные из других классов (например `enc`); этот список индексов их не разрешил. Индексы меняются между сборками; не переиспользуйте их между версиями.

---

## 9. Keepalive и таймеры

| Таймер | Значение | Tier |
|--------|----------|------|
| Client ping | `<iq type="get" xmlns="w:p" to="s.whatsapp.net"/>` (`C9EN`); ответ должен содержать `from`, `id`, `t` в диапазоне 1577865600..4102473600 и `type="result"` (`C14U`) | found |
| Таймаут ping | `clamp(flag 15103, 8000, 32000)` мс; по таймауту `C14R.CY1()` выполняется один раз на ping (реакция переподключения inferred) | found / inferred |
| Интервал ping | флаг **15270** (первый), **15183** (последующие); отложенный runnable или alarm `com.whatsapp.alarm.CLIENT_PING_TIMEOUT`, выбор по флагу **6493** | found, значения на стороне сервера |
| Server ping | `<iq type="get" xmlns="urn:xmpp:ping" t="...">` (`AbstractC40501kw`) | found |
| Ack активного режима | 32000 мс, затем отключение с причиной 10 | found |
| Квитанция сообщения | через 45000 мс после отправки, если всё ещё не подтверждено: переподключение с причиной 9 (`HandlerC21850s9`) | found |
| Таймаут выхода / таймаут сокета | 10000 мс / 30000 мс | found |

---

## 10. Переподключение и backoff (found, `C11380Yq.A07`, `C0X9`)

`C11380Yq` планирует переподключение через `AlarmManager` (`com.whatsapp.MessageHandler.RECONNECT_ACTION`, extra `connect_reason` равен 3). Единица задержки — 10 с (0x2710 мс в smali).

| Шаг | Правило |
|-----|---------|
| Счётчик | `C0X9(1, 17280)`: Фибоначчи в единицах, последовательность 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 ... с ограничением 17280 единиц (48 ч) |
| Первый повтор | 0 единиц: `scheduleReconnect/immediate` |
| Джиттер | `d = units * 10 s`; задержка равномерно в `[d / 2, 1.5 d)` |
| Ограничение | когда флаг вызывающего установлен, задержки свыше 15 мин становятся 15 мин плюс случайное смещение в `-30 .. +29` мс (`backoff clamped to ~15mins`) |
| Сброс | `A02()` сбрасывает счётчик при запросе переподключения `reset` |
| Переопределения | `force` очищает ожидающий дедлайн; `force_no_ongoing_backoff` пропускает ожидание; `reset` сбрасывает счётчик |
| Нет сети | `handleDisconnected/retry/network_unavailable` ждёт появления связи (alarm `CONNECTIVITY_RETRY_ACTION`) |

В рамках одной попытки последовательность подключения из раздела 2.2 обходит хосты и порты; backoff применяется между неудачными попытками всего подключения.

---

## 11. Ошибки потока и коды сбоев

### 11.1 `<failure reason="N">` при логине (found, `A13`)

| Reason | Обработка | Дополнительные читаемые атрибуты |
|--------|-----------|----------------------------------|
| 5xx | повторяемый сбой сервера, `C45351tB(type 4)` | нет |
| 402 | семейство бана; type 13 (код 106 с `appeal_token`), 14 (код 107), 15 (код 109), иначе 2 | `appeal_token`, `code`, `expire`, `message`, `url`, `age_collection` |
| 403 | type 7 | `is_eu`, `vt`, `violation_reason`, `appeal_token`, `reg_info` |
| 405 | type 3, `expiration_time = t * 1000` | `t` |
| 406 | type 5 | `code` |
| 416 | type 11 | `vt`, `violation_reason`, `source_acct`, `appeal_token` |
| другое | type 0 (общий путь выхода из аккаунта) | нет |

Каждый сбой также читает необязательные поля UI выхода `logout_message_header`, `logout_message_subtext`, `logout_message_locale`, `logout_main_button_text` / `_url`, `logout_secondary_button_text` / `_url` (`A17`). Отображение целых type на экраны для пользователя не прослежено; семантика бана аккаунта описана в отчёте по бану.

### 11.2 `<stream:error code="N">` (found, `C40601l6`, `C37961fH.A1B`)

| Случай | Обработка |
|--------|-----------|
| Любой `stream:error` | `ConnectionThreadRequestsImpl/stream/error` пишется в лог с первым потомком; сообщение с `errorCode` отправляется в `MessageHandler` |
| Код 500–599 | `MessageHandler` устанавливает флаг и запускает проход переподключения (`onConnectionStreamError`) |
| Потомок `ack` | трактуется как ack-kick: ищется ожидающая stanza с этим id, отправляются метрики, соединение останавливается (бросается `1t7`) |
| Потомок `conflict type="device_removed"` | только companion: дерегистрация (`C24100vp.A02`), если не состояние 9 |
| 515 / 516 (путь companion) | пересылаются как типизированные сообщения; декомпилированная ветка для 515 неясна |
| `<error code="479">` | сообщается `smax-invalid` (`SmaxInvalidError`) |
| `<error class="status" id=...>` | завершает неудачей колбэк ожидающего status ack |

### 11.3 Сбои рукопожатия и сокета (found как теги логов, реакции частично прослежены)

| Тег лога | Причина |
|----------|---------|
| `socket/goaway` (`X.1sn`) | байты длины ServerHello равны `GOA` |
| `socket/invalid-certificate-exception` (`X.1so`) | проверка цепочки сертификатов не пройдена (5); вызывает `C37031dS.A0C` |
| `socket/disconnect/invalid-server-static-key` (`X.1sp`), `.../authKey` (`X.1sm`) | статический ключ сервера отклонён; проблема статического ключа клиента |
| `socket/disconnect/noise` (`X.1sr`) | исключение протокола (неверные данные рукопожатия, размеры TLV); сбой AEAD `X.1t9` и ошибка входа KEM `X.1tC` перебрасываются в это семейство |
| `socket/disconnect/io`, `socket/closed`, `socket/error/EPERM` | ошибки ввода-вывода, заблокированная сеть |
| `connect/not-allowed/clock`, `software-expired`, `login-failed`, `quit-flag-set` | шлюзы перед подключением |
| `ReaderThread/corrupt-stream-error` | повреждённый поток узлов; `next-port/corrupt-stream-exception` переходит к следующему порту |

---

## 12. Feature-флаги (id по `AbstractC36791d3` и местам вызова)

| Id | Тип | Что контролирует |
|----|-----|------------------|
| **20161**, **34536** | int, string | режим PQ (1 enable, 2–4 enforce), вариант PQ (по умолчанию `IKKEM`) |
| **38643**, **15716** | string, bool | выбор KEM (распознаётся `MLKEM768`), шлюз для него; эффект не выяснен |
| **33751** | bool | буферизованный writer для intro + ClientHello |
| **22916**, **30712**, **33512** | bool | отключение шага HISTORY; загрузка записи о последнем успехе; переиспользование сохранённого порта |
| **20801**, **23630**, **24645** | bool | шаг 5 с фиксированным 443; шаги 2–4 при конфигурации SOCKS; источник конфигурации сервиса SOCKS |
| **13545** | string | режим DNS-резолвера (`secondary` / `hardcoded` / `none`) |
| **7831**-**7834** | bool, ints | включение TCP keepalive и его параметры |
| **15103**, **15270**, **15183**, **6493** | int, bool | таймаут ping, интервалы, способ планирования |
| **20485**, **22413** | bool | состояние очереди в payload |

Все значения задаются сервером; значения по умолчанию — скомпилированные в объявлениях флагов.

---

## 13. Другие транспорты

| Транспорт | Состояние в 2.26.41.6 | Tier |
|-----------|-----------------------|------|
| Клиент Tigon HTTP | `com/crossapp/tigonhttp/TigonHttpClient*`, `com/facebook/tigon/**`, `com/whatsapp/infra/tigon/WAHucClient`, авторизация через `WATigonAsyncAuthServiceHolder`; строки HTTP/2 и HTTP/3 (`MNS/mvfst-mobile`, `MNS/ngtcp2`) в `libwhatsappmerged.so` | классы и строки found; использование по функциям inferred |
| DistribGW (DGW) | `com/facebook/distribgw/client/*`, `RequestStreamDGWBuilder`; найдена только регистрация на стороне приложения: `WaFalcoStreamingRegistration.nativeRegisterStreaming(DGWClient)`; строки `distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, `XPLAT_RS_MQTT`, `XPLAT_RS_STARGATE`, `wa_request_stream` | found; формат на проводе unknown |
| Клиент MQTT | нет; `mqtt` встречается только в названиях событий аналитики и метках типов потоков DGW | found |
| GraphQL поверх chatd | `com.whatsapp.pando.chatd.WAChatdGraphQLClient`, `WAChatdGraphQLCallbacks`, `WATigonMexdServiceHolder` | имена found; идёт поверх chatd как путь w:mex (inferred) |

### 13.1 Канал Tigon Noise (второй стек Noise, нативный)

Это другой транспорт, нежели chatd. Свидетельства — строки и имена классов, а не декомпилированная логика.

- Носитель: WebSocket поверх сетевого стека MNS (`NoiseCarrierWebSocket`, `Stream0Listener`); нумерованные потоки с управляющим потоком 0 и сборкой чанков (`noise.framer.*`).
- Исходы рукопожатия (`NoiseHandshakeOutcome`): `LEGACY_PEER_VERIFIED`, `PRIVATE_AUTH_PEER_VERIFIED`, `ENROLLMENT_REQUIRED`, `KEY_REQUIRED`, `VERIFICATION_FAILED`; `NoisePrivateAuthMode`: `MIGRATION`, `REQUIRED`; ошибки вроде `noise.handshake.attestation_failed`, `chip_binding_rejected`, `private_auth.vm_proof_failed`.
- Аттестация: верификатор AMD SEV-SNP (`NoiseSevSnpAttestationVerifier`, проверки цепочки VCEK / ASK / ARK, привязка к chip id); метки `hatch.noise-auth.key.v1`, `.client-proof.v1`, `.vm-proof.v1`.
- Контроль спроса: `NoiseConnectionDemandRejectionReason` `OFFLINE`, `BACKGROUND`, `PAUSED`, `SESSION_ENDED`, `RETRY_EXHAUSTED`, `INTERNAL`.
- Пользователи на Java: `WaVmHttpTransportImpl`, `NoiseVmConnection` (путь `/v1/noise`, шаги `hatch-noise status=opening` / `result=ready`), `NoiseGatewayCarrier`. Назначение (HTTP поверх Noise к VM конфиденциальных вычислений для браузера агента) выведено из имён и строк аттестации (inferred).

Здесь нет общего кода с рукопожатием chatd из раздела 4; одинаковое имя паттерна не означает одинаковый фрейминг, пролог или payload.

---

## 14. Baileys (`baron-baileys-v2`, подтверждено по его исходному коду)

| Аспект | Baileys | Android 2.26.41.6 |
|--------|---------|-------------------|
| Вводный заголовок | `NOISE_WA_HEADER = [87, 65, 6, 3]` | `57 41 06 03` |
| Паттерн | `NOISE_MODE = 'Noise_XX_25519_AESGCM_SHA256\0\0\0\0'` | то же 32-байтовое дополненное имя |
| Сертификат сервера | декодирование `CertChain`; подпись leaf проверяется ключом intermediate; intermediate проверяется закреплённым корнем `142375574d0a...da8ee6b`; `issuerSerial` должен быть 0 | та же цепочка и те же байты корня; APK дополнительно требует `leaf.issuerSerial == intermediate.serial` |
| Edge-маршрутизация | сохраняет `routing_info` из `<ib><edge_routing>`; добавляет его как query `ED=<base64url>` к `wss://web.whatsapp.com/ws/chat` | сохраняет его (максимум 256 байт); отправляет `45 44 00 01 len24 blob` как есть перед intro |
| Keepalive | `<iq type="get" xmlns="w:p"/>` без потомков, интервал по умолчанию 30000 мс, таймаут подключения 20000 мс | тот же IQ; интервал и таймаут из серверных флагов |
| Payload логина | `passive`, `pull` true, `username`, `device`, `connectType WIFI_UNKNOWN`, `connectReason USER_ACTIVATED`, `lidDbMigrated false`, `releaseChannel RELEASE` | без `pull`, `connectReason` из состояния сессии, `releaseChannel BETA` в этой сборке |
| Payload регистрации | `passive false`, `pull false`, `devicePairingData` | `devicePairingData` только для подключения регистрации companion |
| Транспорт | фреймы WebSocket | сырой TCP, фреймы с 3-байтовой длиной |

Подтверждённые различия, важные для транспорта в стиле Android: edge-подсказка в Baileys — параметр запроса в URL WebSocket, а на Android — сырой заголовок перед intro; Baileys не требует `leaf.issuerSerial == intermediate.serial`; Baileys отправляет `pull` и `passive` как true при логине, тогда как в payload Android `pull` нет. Baileys сохраняет статический ключ сервера для быстрого переподключения (комментарий в коде называет `NoiseIkSession`), что по замыслу соответствует возобновлению IK из раздела 4.4; его форма на проводе не сравнивалась.

---

## 15. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| `GOA` в первых трёх байтах | goaway сервера во время рукопожатия | попробовать следующий эндпоинт |
| `Handshake message does not contain server hello!` | первый фрейм сервера не является ServerHello | проверить пролог и edge-заголовок |
| `noise certificate key does not match proposed server static key` | ключ leaf отличается от статического ключа рукопожатия | проверять цепочку до ClientFinish |
| `server to client stanza fragmentation not supported` | установлен бит флагов `1` | клиентом не поддерживается |
| `unexpected node received during login sequence` | первый узел не `web`, `success`, `failure` | нет |
| `noise-pq-static-key-decode-failed` | `static_pq_key` не является корректным base64 | ключ не сохраняется, сообщается один раз |
| `scheduleReconnect backoff=...` | повторяющиеся сбои | дождаться окончания backoff либо принудительно переподключиться |

---

## 16. Ключевые различия

| Не путать | Деталь |
|-----------|--------|
| Noise chatd и канал Tigon Noise | Java и нативный код, носитель TCP и WebSocket, разное назначение; одинаковое имя паттерна ничего не говорит о фрейминге или payload |
| Вводный заголовок и edge-заголовок | `WA 06 03` хешируется как пролог; `ED 00 01 len blob` не входит в транскрипт |
| Edge-хост `eN.whatsapp.net` и `routing_info` | хосты берутся из последовательности клиента; `routing_info` — непрозрачный блоб, повторяемый в edge-заголовке |
| `fallback_hostname` / `fallback_ip4` / `fallback_ip6` | атрибуты хостов `media_conn` (CDN), а не фолбэки chatd; фолбэки chatd берутся из `<ib><fbip>` и жёстко заданной таблицы |
| Флаг payload `passive` и IQ `<passive/>` | флаг задаётся при подключении; IQ затем переключает в активный режим |
| `devicePairingData` и HTTP-регистрация | pairing data относится к подключению регистрации companion |
| Длина фрейма и размер списка | 3-байтовая длина оборачивает шифртекст; размер списка считает слоты узла |
| Версия протокола и версия словаря | обе в intro: `06` и `03` |
| `stream:error` и `failure` | `failure` отвечает на логин; `stream:error` может прийти в любой момент |

---

## 17. Полный поток

```
[Connection thread]  C37031dS.A0G picks step (history, g, g-fallback, hard-coded, eN, proxy)
     │  DNS ─► TCP connect ─► optional TLS wrapper
     ▼
[Client]  write [ED 00 01 len24 routing_info]?  [WA 06 03]        h = SHA256(name) ; h = SHA256(h || WA 06 03)
     │  frame1: HandshakeMessage{clientHello{ephemeral}}           mixHash(e_c)    (resume: + static + payload)
     ▼
[Server]  frame2: serverHello{ephemeral, static, payload}
     │  mixHash(e_s) ; mixKey(ee) ; s_s = decrypt(static) ; mixKey(es) ; cert = decrypt(payload)
     │  CertChain: leaf.key == s_s ; intermediate by pinned root ; leaf by intermediate
     ▼
[Client]  frame3: clientFinish{static = enc(s_c), payload = enc(ClientPayload)}      mixKey(se) ; split
     ▼
[Server]  [len24 | AES-GCM(flags | node)] ─► <success t props abprops lid pn static_pq_key/>  or  <failure reason/>
     ▼
[Client]  <iq xmlns="passive" type="set"><active/></iq> (+ pre-acks) ; steady state both ways, own counter per direction
     │  ping <iq xmlns="w:p"/> ; ib / notification / message / receipt / call ...
     ▼
[Failure]  stream:error / ping timeout / socket error ─► disconnect ─► Fibonacci backoff ─► next attempt
```

---

## 18. Неизвестное

| Пункт | Статус |
|-------|--------|
| Трафик на проводе любого рода | ничего не перехвачено; ни один пункт не `tested` |
| Транскрипт возобновления IK и фолбэка | структура found, шаги inferred |
| Размещение PQ-ключа в `ServerHello.payload`, ширина длины TLV, библиотека за вызовами ML-KEM | не декодировано / не определено |
| Что несут эндпоинты с TLS-обёрткой внутри TLS | inferred по пути кода |
| Значения ping и TCP-keepalive | серверные флаги |
| Целые type сбоев 0–15 и экраны клиента; эффект флагов **38643**, **15716** | не прослежено / не выяснено |
| Поля payload без записи (`webInfo`, `shards`, `fb*`, `accountType`, `testIsolationId`, `paddingBytes`, `pull`) | в этой сборке не найдено |
| Рукопожатие и фрейминг канала Tigon Noise; протокол DGW на проводе и его пользователи | нативный код, только строки |
| Строки словаря, являющиеся импортированными Java-константами (например `enc`) | не разрешены в списке индексов |
