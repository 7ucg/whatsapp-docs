<!-- src-sha1: 7c179c130d5822c6103aa9a9ae2e6751ec1b0bd8 -->
# WhatsApp Call Signaling — Full RE Report
**Версия:** 2.26.41.6 | **Дата:** 2026-10-24
**Область:** сигнализация голосовых и видеозвонков Android: конверт `<call>` и ack, action-станзы (offer, accept, preaccept, reject, terminate, transport, relaylatency, enc_rekey, mute_v2, group_info, group_update, lobby, link_*, waiting_room_*, bcall), payload offer (audio / video / capability / encopt / net), ключ звонка и его шифрование через Signal, rekey (v2 / v3), вывод медиаключей, выбор relay и транспорта, ICE / STUN / DTLS / SRTP в сравнении с медиапутём WhatsApp, групповые звонки, ссылки на звонки и запланированные звонки, журнал звонков и сообщения bcall, коды nack для offer, поведение reject и terminate, feature-флаги, сравнение с Baileys

---

## 1. Что это (технически)

Сигнализация звонков — набор станз `<call>` в обычном соединении chatd (см. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Каждая станза несёт ровно один дочерний элемент-действие. Java-слой не собирает и не разбирает станзы звонков: это делает нативный VoIP-движок, а Java только (а) оборачивает исходящие дочерние элементы в `<call>`, (б) шифрует ключ звонка через Signal для каждого устройства, (в) передаёт входящие станзы движку, (г) реагирует на события движка. Медиа (RTP-подобный трафик к relay, ICE, DTLS, SRTP) не относится к сигнализации и идёт по UDP/TCP-сокетам, которыми владеет движок. Все утверждения получены статическим анализом; на проводе ничего не перехватывалось. Уровни: **found** = прочитано в Java или в нативных строках, **inferred** = выведено, **unknown** = не выяснено.

| Слой | Имя в 2.26.41.6 | Роль |
|------|-----------------|------|
| JNI-фасад | `Voip` / `VoipNativeImpl` (`com.whatsapp.calling.voipcalling`) | 148 нативных методов (`startCall`, `acceptCall`, `rejectCall`, `nativeHandleIncomingSignalingXmpp`, ...) |
| Исходящий хук | `OutgoingSignalingHandler` реализует `SignalingXmppCallback.sendCallStanza(Jid, callId, VoipStanzaChildNode)` | от движка к Java; обработка по тегам, шифрование ключа звонка |
| Запись конверта | `CIX` (очередь), `C27410BtV` (станза звонка), case 206 writer-потока в `HandlerThreadC21920sG` | собирает `<call to id>` |
| Входящий обработчик | `C40641lA` (`CallStanzaHandler`), `BQU` (разобранная станза звонка), `C83` (расшифровка), `C28120CKj` / `RunnableC29343CoU` (передача движку) | разбор конверта, расшифровка `<enc>`, подача движку |
| События движка | `VoipEventCallback`, `VoiceServiceEventCallback` (116 колбэков) | от движка к UI / состоянию |
| Крипто-колбэк | `DefaultCryptoCallback`, `SignalIdentityCryptoCallback` (`CryptoCallback`) | HKDF / HMAC / random / подписи Ed для движка |
| HTTP-сигнализация | `VoiceTeeHttpSignalingHandler` (`SignalingHttpCallback`) | альтернативный носитель сигнализации, TEE-запрос |
| Нативный движок | `libwhatsapp.so` (распаковывается из архива superpack `libs.so`; экспортирует `Java_com_whatsapp_calling_voipcalling_Voip_*`) | сериализаторы / десериализаторы станз, автомат состояний звонка, транспорт, медиа |

Положения, определяющие остальной отчёт:

- Грамматика станз живёт в нативном коде: сериализаторы `serialize_*` (C/C++) и Rust-крейт `call_control` (пути исходников `xplat/wa-voip/rust/call_control/src/stanza_deserializer/...` в его panic-строках) для входящего разбора. Voip-библиотеку декомпилировать не удалось; каждое нативное утверждение опирается только на строки и экспортированные имена (found строки, inferred смысл).
- Java — тонкая прослойка, поэтому набор тегов, видимый в Java (10 тегов в `sendCallStanza`), намного меньше набора, который понимает движок (раздел 4).
- Ключ звонка создаётся и используется движком; Java шифрует его обычной парной сессией Signal (раздел 6). Тот же код HKDF, который нужен движку, является Java-колбэком (раздел 7).
- Медиапуть WhatsApp (relay allocate/bind, пакеты "WARP", hop-by-hop SRTP, SFrame для групповых звонков) отличается от пути ICE/DTLS в стиле WebRTC, который существует как режим "web_p2p" (раздел 8).

---

## 2. Интерфейс Java / нативный код

Колбэки, регистрируемые при старте (found): `SignalingXmppCallback.sendCallStanza(to, callId, node)` (от движка к Java, один дочерний элемент call); `CryptoCallback` (`generateE2EKeysV2`, `getSecureSsrc`, `hkdfSha256`, `hmacSha256`, `generateRandomBytes`; `SignalIdentityCryptoCallback` добавляет `signWithIdentityKey` с 64-байтной подписью и `verifySignature` с 32-байтным ключом); `SignalingHttpCallback` (`sendMsg(callId, bytes, requestType)`, `cancelMsg`; типы: voice session 0, codec avatar 1); `VoipEventCallback` (раздел 13). `VoipStanzaChildNode` — дерево, видимое через JNI (тег, атрибуты, дочерние элементы, данные); Java преобразует его в узел chatd и обратно, бинарное кодирование которого описано в [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md), раздел 8.

| Точка входа JNI (found) | Чем питается | Примечания |
|-------------------------|--------------|------------|
| `nativeParseXmppOffer(CallOfferInfo[], ...)` | `preprocess_call_offer` (`AbstractC24816AmW`) | разбирает offer без запуска звонка; `CallOfferInfo`: callId, fromJid, groupJid, callLinkToken, isVideoCall, isAudioChat, isJoinableCall, isOfferExpired, isCallEnded, silenceReason, groupPhash, participantHash, callGroupInfo |
| `nativeHandleIncomingXmppOffer` | `C28120CKj` | запускает обработку входящего звонка |
| `nativeHandleIncomingSignalingXmpp` / `...Ack(from, type, errorCode, children, ..)` / `...Receipt` | `RunnableC29343CoU` (сообщение 192) | каждое действие кроме offer, ack на собственные станзы (возврат 70004 логируется как повреждённый ack), квитанции звонков |
| `peekIncomingOffer`, `handleIncomingTerminatePush` | путь push | решение до начала звонка, terminate, доставленный через push |
| `handleIncomingSignalingHttp(callId, bytes, ..)` | HTTP-ответ TEE | альтернативный носитель (11.3) |

---

## 3. Конверт, ack, квитанции

### 3.1 Исходящий `<call>` (found, `HandlerThreadC21920sG` case 206)

```
<call to="<jid>" id="<stanza id>">
  <ACTION .../>                      exactly one child
</call>
```

`to` должен пройти `C0DZ.A0R` (user, device и ещё несколько типов JID; иначе `C27410BtV` бросает `CallStanza:Wrong jid type`). Id станзы берётся из общего генератора id. Строка лога `WriterThread/write/call-stanza-<tag>`.

### 3.2 Входящий `<call>` (found, `C40641lA`)

| Атрибут | Обработка |
|---------|-----------|
| `from` | должен быть валидным JID, иначе `CallStanza from invalid jid`; user JID сопоставляется с основным устройством |
| `id` | id станзы, используется для ack |
| `t` | секунды, умножаются на 1000 |
| `e` | целое число секунд, умножается на 1000 и передаётся движку рядом с `t` (точный смысл не выяснен; inferred: возраст offer / входной параметр срока действия) |
| `offline` | целое; наличие означает доставку из офлайн-очереди |
| `notify`, `platform`, `version` | передаются дальше (push-имя звонящего, платформа, версия приложения) |
| `participant` | device JID отправителя в групповых контекстах; некорректное значение заменяется на `from` |
| `sender_lid` | читается, когда `from` — JID домена LID |
| дочерний `call-creator` | device JID (обязателен для логики не-offer) |
| дочерний `call-id` | обязателен; кроме тегов `reminder` и `bcall_*`, которым присваивается пустой call id |
| прочие атрибуты | `caller_pn` (device JID с номером телефона), `username`, `caller_country_code`; читаются только если создатель — LID и тег не `offer` |

Если `to` и `call-creator` находятся в разных адресных доменах (один LID, другой номер телефона), клиент логирует `CallStanzaHandler/call-mixed-domain/...`, сообщает метрику `CallMixedDomainStanza` и продолжает работу (found). Смешанные домены допускаются, а не отклоняются.

### 3.3 Ack

| Случай | Поведение (found) |
|--------|-------------------|
| тег не из {offer, accept, reject, enc_rekey, terminate} | Java сразу отправляет ack: `<ack class="call" type="<tag>" id to [participant]/>` (`AbstractC47181wT.A01`) |
| тег из этого набора | немедленного ack от Java нет; узел идёт по отдельному пути отложенного ack (`C36591ch.A0G`); семантика не выяснена |
| ack на собственную станзу | `nativeHandleIncomingSignalingXmppAck(from, type, errorCode, children, ...)`. Типы ack, видимые в Java: offer (несёт данные relay, раздел 8), accept, link_join, link_query, lobby; нативный код также обрабатывает link_create, link_edit, remove, remove_user, heartbeat, screen_share, add_extension, remove_extension, relaylatency, video state, waiting_room_* |
| ack на offer с ошибкой 435 | после ack планируется дополнительное действие (назначение не выяснено) |
| доставка offer / accept | Java ждёт ack доставки от chatd с таймаутом (флаги 9257, 9431); по таймауту станза отбрасывается и логируется `Call stanza delivery timed out` |

### 3.4 Токены словаря (found, `AbstractC40911lb`)

Однобайтовые (`A00`): `call` 97, `call-id` 101, `call-creator` 68, `terminate` 208, `relaylatency` 70, `video` 86, `audio` 158, `capability` 177, `device-identity` 227, `privacy` 223, `te` 212, `te2` 198, `token` 194, `key` 155, `participant` 5, `user` 14, `remove` 172, `notify` 24, `registration` 170, `attribute_padding` 229, `relay_id` 130, `token_id` 143. Вторичный словарь 0 (`A01[0]`): `offer` 28, `accept` 97, `preaccept` 18, `transport` 44, `mute_v2` 253, `group_info` 170, `group_update` 99, `net` 103, `medium` 36, `encopt` 21, `keygen` 26, `voip_settings` 10, `relay` 116, `joinable` 75, `heartbeat` 6, `transaction-id` 62, `uuid` 132, `self_pid` 71, `peer_pid` 76, `metadata` 118, `uncompressed` 20, `rate` 29, `dec` 73, `screen_width` 5, `reason` 46. Вторичный 1: `reject` 0, `enc_rekey` 205, `e` 235.

Нет ни в одном словаре этой сборки (простые строки на проводе): `lobby`, `flowcontrol`, `screen_share`, `link_*`, `peer_state`, `interruption`, `reminder`, `raise_hand`, `waiting_room_*`, `hbh_key`, `auth_token`, `lightweight`, `silence`, `scheduled-id`, `group-jid`, `link-token`, `caller_pn` и `enc`.

---

## 4. Таксономия действий

Входящие теги, которые диспетчеризует нативный десериализатор (found, список строк в `call_control`): `offer`, `accept`, `preaccept`, `reject`, `terminate`, `transport`, `relaylatency`, `enc_rekey`, `notify`, `flowcontrol`, `interruption`, `group_update`, `mute_v2`, `screen_share`, `raise_hand`, `reconfigure_bot`, `user_action`, `ready`, `relay_info_update`, `tos`, `screen`, `switchable`, `add_extension`, `waiting_room_update`, а также `receipt`. Разбираемые ack: offer, accept, video state, relaylatency, link_create / edit / query / join, lobby, heartbeat, remove, remove_user, screen_share, add_extension, remove_extension, waiting_room toggle / admit / deny / leave.

| Тег | Направление (found) | Назначение |
|-----|---------------------|------------|
| `offer` | out / in | начало звонка (раздел 5); in: также offer для уже завершённых звонков с `is_call_ended` и `terminate_hint` |
| `preaccept` | out / in | устройство вызываемого звонит / готово; состояние движка `PRE_ACCEPT_RECEIVED`, событие `preacceptReceived` |
| `accept` | out / in | вызываемый принимает; несёт медиапараметры и сертификат (нативные строки `error parse voip params for accept`, `error parsing certificate for accept`) |
| `reject` | out / in | вызываемый отклоняет; строки причин в разделе 14.2 |
| `terminate` | out / in | завершение звонка; id транзакции и `call_summary` (раздел 14.3) |
| `transport` | out / in | кандидаты, учётные данные ICE, сертификат, состояние сети (раздел 8.5) |
| `relaylatency` | out / in | измеренные задержки relay (раздел 8.4); имеет собственный ack |
| `enc_rekey` | out / in | повторная передача ключа звонка (раздел 6.4) |
| `video` (state) | out / in | видео вкл / выкл / апгрейд; значения `kVideoState*` (раздел 13); ack несёт информацию о relay |
| `notify`, `peer_state`, `flowcontrol`, `interruption`, `ready`, `heartbeat` | out / in | состояние внутри звонка: уведомления пира, здоровье сети, управление потоком, прерывания, heartbeat группы |
| `mute_v2`, `raise_hand`, `user_action`, `tos`, `reconfigure_bot` | out / in | запрос отключения микрофона в групповых звонках, поднятие руки, действия пользователя, TOS группового звонка, реконфигурация бота (атрибут `req_id`) |
| `group_info`, `group_update` | in (дочерний элемент offer / ack / update) | состав участников (раздел 9) |
| `lobby` | out / in | запрос / состояние лобби группового звонка; его ack несёт информацию о группе |
| `screen`, `screen_share`, `switchable` | out / in | состояние показа экрана; переключение устройства (`switch_info`, `root_call_id`, `root_call_creator`, `peer_active_device`) |
| `add_extension`, `remove_extension` | out / in | добавление медиаэндпоинта ("extension") к звонку (раздел 9.4) |
| `remove`, `remove_user`, `cancel_offer` | out | удаление участников; отмена offer для выбранных участников |
| `link_create`, `link_edit`, `link_query`, `link_join` | out | ссылки на звонки (раздел 10) |
| `waiting_room_toggle`, `_admit`, `_deny`, `_leave`, `_update` | out / in | зал ожидания link-звонка (раздел 10.3) |
| `reminder`, `bcall_*` | in | серверные напоминания; семейство business-call (раздел 11) |
| `dtmf`, `duration`, `connect_stat`, `group_call_duration`, `group_call_tos_accepted` | out | сериализаторы есть в движке |

Теги, видимые в Java в `sendCallStanza` (found): `offer`, `accept`, `reject`, `terminate`, `video`, `enc_rekey`, `lobby`, `link_join`, `link_query`, `link_create`; любой другой тег идёт по стандартному пути отправки.

Таблица числовых id сообщений (85 типов), разделение по механизмам (child / ack / receipt / internal) и фиксированные длины заголовков: в этой сборке не найдены. Движок экспонирует теги и сериализаторы по тегам, а не enum id, видимый в строках. Любую таблицу id для Android считать unknown.

---

## 5. Offer

### 5.1 Сборка и отправка (found)

`startCall(...)` заставляет движок выдать `sendCallStanza(peer, callId, offerNode)`. Java:

1. `sendOfferStanza` сохраняет id станзы (`outgoingCallOfferKey`), ждёт, пока выполняется задача pre-key для любого устройства назначения, затем шифрует ключ звонка для каждого устройства в рабочем потоке (`getBulkEncryptedE2EKeys`, раздел 6.1).
2. Результат записывается либо в новом формате (`<destination><to jid><enc/></to>...</destination>`, через `AbstractC33466EhY.A08`), либо в старом (один дочерний `<enc>`, допустим только для одного устройства; `cannot have multiple encrypted messages in old format!`).
3. Если хотя бы одно устройство получило `pkmsg`, добавляется `<device-identity>` (байты `adv_signed_identity` из настроек companion); это происходит только когда собственное устройство проходит `BRD()` (id регистрации устройства ненулевой, т.е. companion; inferred).
4. `CIX.A02` ставит станзу `<call>` в очередь; флаг **9257** (мс) ограничивает ожидание доставки.
5. После отправки планируется ping IQ звонка (флаг **30890**, задержка **30891** мс, по умолчанию 3000, число попыток **32651**); если соединение разорвано, клиент переподключается, если только звонок уже не вышел из состояния `CALLING`.
6. Если для назначений шифрование невозможно, offer сохраняется как `pendingCallOfferStanza` и отправляется позже (`maybeSendPendingOffer` по окончании задачи pre-key, `sendPendingCallOfferStanza` при terminate). `preSendTerminate` убирает неподтверждённый offer из очереди повторов до отправки terminate.

### 5.2 Дочерние элементы и атрибуты

| Элемент | Источник | Атрибуты / содержимое |
|---------|----------|------------------------|
| `<offer>` | отправка | `call-id`, `call-creator` (device JID); приём: `caller_pn`, `username`, `caller_country_code`, `group-jid`, `scheduled-id`, `joinable`, `lightweight` (`1` = облегчённый / только аудио групповой вызов), `rering_ts`, `is_call_ended`, `type` |
| `<audio>` (повторяется) | отправка | `enc` (кодек), `rate` (частота дискретизации); `enc` и `rate` — токены словаря |
| `<video>` | отправка | `enc`, `dec`, `device_orientation`, `screen_width`, `screen_height`; строковые значения в движке: `h.264`, `vp8`, `vp8/h.264`; атрибут `fps` также присутствует как строка (inferred видеоатрибут) |
| `<net>` | отправка | `medium` (тип сети), позднее `health_status` в transport |
| `<capability>` | отправка | `ver` + непрозрачная битовая маска (`pjmedia_voip_capabilities_*`: версия, `bit_mask_length`); строка `vid_dec` для каждого устройства перечисляет декодируемые видеокодеки (`vid_codec_capability_str_to_bitmask`) |
| `<encopt>` | отправка | `keygen` = версия генерации ключа; движок отклоняет другие значения (`Unsupported keygen ver`); существуют версии 2 и 3 (раздел 6.4) |
| `<destination>` / `<to jid>` / `<enc>` | отправка | зашифрованный ключ звонка для каждого устройства (раздел 6.1); `<to>` может нести `peer_recipient_lid`, `peer_recipient_pn`, `peer_recipient_username`, `eph_setting` |
| `<tctoken>` | отправка | внутри `<to>`, не более одного раза на пользователя, когда флаг **20605** включён и менее **20606** пользователей уже несут его; то же семейство токенов, что в [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `<device-identity>` | отправка | байты подписанной ADV-идентичности, см. 5.1 шаг 3 |
| `<privacy>` | приём | токен приватности (имя токена есть в словаре); содержимое не прослежено |
| `<relay>` | приём / ack | список relay (раздел 8) |
| `<voip_settings>` | приём / ack | параметры движка от сервера; атрибут `uncompressed`; сжатые payload в одном из путей отклоняются (`unexpected compressed voip params`), и `zlib inflate` слинкован (формат сжатия inferred) |
| `<metadata>` | приём | атрибуты A/B-бакета пира (`peer_abtest_bucket`, `peer_abtest_bucket_id_list`) |
| `<silence reason>` | приём | offer беззвучный (без звонка); `BQU.A02`; целочисленные причины `kOfferSilenceReason*` (раздел 13) |
| `<group_info>` | приём | состав группового звонка (раздел 9) |
| `<terminate_hint>` / `<call_summary>` | приём | offer для уже завершённого звонка (`is_call_ended=1`): `terminate_reason`, id транзакции, сводка |
| `<link_info>`, `<waiting_room>`, `<bot>`, информация о расширениях | приём | данные ссылки, зала ожидания, бота и расширений |

Точные байтовые значения `<capability>` и коды `net medium` в этой сборке не восстановлены (7-байтовая маска `01 05 F7 09 E4 BB 13` иногда цитируется для веб-клиентов; в библиотеке Android она не встречается как непрерывный литерал, поэтому значение для Android считать unknown). Движок включает кодеки, названные в строках: Opus плюс собственный низкобитрейтный кодек ("mlow", с фреймингом Opus), OpenH264, VP8, AV1 (`wzav1`) и HEVC через MediaCodec.

### 5.3 Путь приёма (found)

1. `CallStanzaHandler` строит `BQU`; метрика `CallStanzaHandler/handleStanza tag=... callId=...`; сообщение 192 отправляется диспетчеру.
2. Для offer `preprocess_call_offer` запускает `nativeParseXmppOffer`; ненулевой возврат отбрасывает станзу. Просроченные или завершённые offer не звонят.
3. `C83.A00` расшифровывает `<enc>` (раздел 6.2), затем `nativeHandleIncomingXmppOffer` запускает звонок; состояние `RECEIVED_CALL`.
4. `peekIncomingOffer` (предпроверка по push) игнорирует беззвучные offer, групповые offer (есть `group_info`), offer с `is_call_ended=1`, 1:1 offer без `<enc>` и offer, пока телефон занят; флаг **4217** бит 1 включает голосовые peek, бит 2 — видео peek.
5. Последующий `terminate` или push `handleIncomingTerminatePush` завершает peek.

---

## 6. Ключ звонка и его шифрование

### 6.1 Исходящее (found, `getBulkEncryptedE2EKeys`)

Движок передаёт map: device JID -> сырые байты ключа звонка. Для каждого устройства без ожидающей задачи pre-key клиент собирает protobuf `Message` и шифрует его через Signal существующей парной сессией (`C83` / `CallableC29363Coo`):

| Поле Message.Call | Номер | Тип | Когда задаётся |
|-------------------|-------|-----|----------------|
| `callKey` | **1** | bytes | всегда (32 сырых байта) |
| `conversionSource` / `conversionData` / `conversionDelaySeconds` | **2** / **3** / **4** | string / bytes / uint32 | есть данные CTWA |
| `ctwaSignals` / `ctwaPayload` | **5** / **6** | string / bytes | есть данные CTWA |
| `contextInfo` | **7** | ContextInfo | флаг CTWA (`externalAdReply.adType` выставляется в фиксированное значение) |
| `nativeFlowCallButtonPayload` | **8** | string | звонок начат из кнопки native-flow |
| `deeplinkPayload` | **9** | string | звонок начат из deeplink |
| `messageContextInfo` | **10** | MessageContextInfo | обогащение для каждого пира через `AbstractC30999De0` (содержимое не прослежено) |
| `callEntryPoint` | **11** | uint32 | флаг **24935**, только при начальном fanout (`i == 0`) |
| `callReason` | **12** | string | есть в proto, в этом пути не задаётся |

`Message.call` — поле **10** в `Message` (`C30628DTw`), класс `Message.Call` = `C25827BCl`. Для начального offer флаг **520** добавляет контекст атрибуции рекламы из CTWA-резолвера (`C35832FfR`; inferred). Fanout выполняется с `i == 0` для offer и `i == 1` для rekey. Шифрование блокирующее, с путём отмены; блокировка свыше 5000 мс логируется как `voip_e2e_encryption_blocked`.

Проводная форма для одного устройства (found, `AbstractC33466EhY.A03/A09`): `<enc v="<version>" type="msg|pkmsg|skmsg|frskmsg|msmsg" [count="<retry>"] [mediatype] [session_type="pq"] [bucket]>CIPHERTEXT</enc>`. `session_type="pq"` помечает постквантовую сессию Signal; `count` опускается, когда равен 0. Ключи звонков в этом пути никогда не являются групповыми сообщениями sender-key (тип `skmsg` принимается хелпером, но ни один путь звонка его не порождает; inferred).

Устройства-расширения (префикс user в JID `01`) используют `sendReKeyToExtension`: ранее буферизованный prekey bundle обрабатывается, ключ шифруется как `pkmsg` с `v="2"` (found).

### 6.2 Входящее (found, `C83.A00`)

| Шаг | Детали |
|-----|--------|
| читаемые дочерние элементы | `registration` (должен быть 4 байта; id регистрации Signal, используется для retry), `device-identity`, `enc` |
| дубликаты | второй `<enc>` отбрасывается (`duplicate <enc>`) |
| счётчик retry | `count` в `<enc>`; отсутствие значения прерывает обработку (`invalid retry count`) |
| тип | принимаются `msg` 0 или `pkmsg` 1; другие числа логируют `unrecognized ciphertext type` |
| расшифровка | парная расшифровка Signal (pre-key сообщение обрабатывается с идентичностью устройства отправителя); payload разбирается как `Message`, берётся `call.callKey`; `ExternalAdReplyInfo.adType` в CAWC логируется |
| результат | `<enc>` заменяется простым узлом `<enc>` с байтами ключа звонка для движка |
| сбой | событие `rejectedDecryptionFailure`, `onPeerE2EDecryptionFailed` повторяет установку сессии (запрос нового pre-key, когда id регистрации совпадает и base key повторяется); причина reject `enc` отправляется, если звонок невозможно расшифровать |

Флаг **24063** меняет путь выбора типа сессии для шифртекстов hosted-типа (inferred из условия `c33281EeX.A04`).

### 6.3 Retry

`sendOfferRetryRequest(device)` заставляет движок повторно отправить offer (`resendOfferOnDecryptionFailure`); `sendPendingRekeyRequest` повторяет запрос rekey, пока сохранённый байт retry находится в диапазоне 0..4. Таким образом, `count` лежит в диапазоне от 0 до 4 (found, `sendPendingRekeyRequest`).

### 6.4 `enc_rekey`: три формы

| Форма | Свидетельство | Содержимое |
|-------|---------------|------------|
| v2 unicast | `sendReKeyStanza` (Java) | движок выдаёт `<enc_rekey call-id call-creator transaction-id><enc count=N>RAW KEY</enc></enc_rekey>`; Java заменяет дочерний элемент на зашифрованный через Signal `<enc>` для целевого устройства (found) |
| v2 fanout | `sendReKeyFanoutStanza` | цель — группа; дочерний `<destination><to jid><enc/></to>...`; каждая запись шифруется отдельно (found) |
| v3 | нативные строки `handle_enc_rekey_v3`, `make_and_send_rekey_v3`, `ext_rekey: ...` | payload — protobuf с повторяющимися `wa.voip.RekeyKeyEntry` (тип ключа + ключ); ключи каждого типа имеют фиксированную длину (`key type %d has unexpected length`); выбирается при keygen 3; требует поддержки расширений (`kCallExtensionMV1`); переход v3 -> v2 логируется |

Правила, видимые в строках: rekey несут id транзакции; ранние, старые или равные id игнорируются (`ignore old rekey msg with transaction id`); в звонке один-на-один входящий `enc_rekey` игнорируется (`ignore rekey msg in one to one call`); `request_keys` просит создателя или расширение переслать ключи (только v3; `request_keys with unexpected keygen` игнорируется). Какая сторона начинает rekey в групповом звонке и точный триггер не выяснены.

---

## 7. Вывод медиаключей

### 7.1 Java-колбэки (found)

| Колбэк | Вычисление |
|--------|------------|
| `generateE2EKeysV2(callKey[32], out[46], info)` | HKDF-SHA256, salt = 32 нулевых байта, IKM = ключ звонка, info = UTF-8 строка `info`, поставляемая движком, 46 выходных байт (`E2E_EXTENDED_V2_KEY_LENGTH`) |
| `hkdfSha256(salt, ikm, info, out)` | универсальный HKDF-SHA256 (первый аргумент salt, второй IKM, третий info; длина вывода = `out.length`) |
| `getSecureSsrc(ikm, info, salt[4], out[4])` | HKDF-SHA256 до 4 байт (`SECURE_SSRC_LENGTH`) |
| `hmacSha256(key, data, out[32])` | HMAC-SHA256 |
| `generateRandomBytes(out)` | `SecureRandom` (источник 32-байтного ключа звонка; inferred) |

### 7.2 Метки и контексты в движке (found строки, роль inferred)

`e2e sframe key`, `hbh srtp key`, `uplink hbh srtcp key`, `downlink hbh srtcp key`, `warp auth key`; функции `derive_sframe_key`, `derive_hbh_srtp_key`, `derive_and_update_warp_mi_keys`, `derive_extension_per_media_key`; слоты ключей `owner_e2e_key`, `extension_audio_key`, `extension_video_key`, `extension_appdata_key`.

| Ключ | Источник (inferred) | Что защищает |
|------|---------------------|--------------|
| материал E2E SRTP | вывод `generateE2EKeysV2` (46 байт), для каждого участника | медиа между эндпоинтами (1:1) |
| ключ SFrame | метка `e2e sframe key` | шифрование кадров в групповых / SFU звонках и канал данных hop-by-hop (`wa_sframe_encrypt`, `sframe_keyprovider_set_chainkey`) |
| hop-by-hop SRTP / SRTCP | выданный relay `hbh_key` (раздел 8.2) с метками `hbh ...` | только участок клиент — relay |
| ключ WARP MI | метка `warp auth key` | тег целостности сообщений пакетов WARP (`warp_mi_tag_len`) |

Раскладки ключей (какие из 46 байт — ключ или salt, по направлениям), содержимое строки `info` и точные цепочки HKDF для SFrame / hop-by-hop не восстановлены: вызывающий код находится в нативном коде, который декомпилировать не удалось. Device-qualified JID в качестве `info` правдоподобен, но не подтверждён (**unknown**).

---

## 8. Relay, транспорт и медиапуть

### 8.1 Что получает клиент

Данные relay приходят в ack на offer (звонящий; `error during parsing relay info`, `Failed to parse relay info in offer ack`), в самом offer (вызываемый), а позже — в `relay_info_update` и в ack на смену состояния `video` (found).

### 8.2 Грамматика `<relay>` (found, строки `fill_relay_info`)

| Элемент | Имя | Примечания |
|---------|-----|------------|
| атрибуты relay | `uuid`, `self_participant_uuid`, `conn_id`, `medium`, `warp_mi_tag_len`, `prefer_relay`, `prefer_ipv6`, `peer_dl`, `smart_transport_signal`, `attribute_padding` | для каждого набора relay |
| токены | список `<token>` (`token_id`), нужен хотя бы один (`relay_token_list.num_tokens < 1`) | учётные данные relay; список копируется в запрос allocate |
| auth-токены | `<auth_token>` (`auth_token_id`) | используется вместо токена, когда id в допустимом диапазоне; иначе "falling back to relay token" |
| ключ | `<key>` | материал пароля relay |
| `hbh_key` | дочерний элемент с сырыми байтами или base64 | источник hop-by-hop ключа; размер проверяется (`HBH Key of unexpected size`, "though warp_mi_tag_len = ...") |
| эндпоинты | `<te>` или `<te2>` | никогда оба (`can not receive both te and te2 endpoints`); байты адреса IPv4 или IPv6 (`endpoint too short for an IPv6 address`); пустой адрес отклоняется |
| на эндпоинт | `relay_id`, `relay_name` (обрезается, если слишком длинное), `domain_name`, `latency`, `c2r_rtt`, `ul_bw`, `dl_bw`, `is_favored` | `latency` задаёт начальное значение выбора relay |
| участники | `<participant pid jid>` | сопоставляет id участников, используемые в пакетах WARP / SFU |

Строки лога печатают адреса relay через заполнитель `[MetaServiceIP]`, поэтому адреса relay считаются сервисными IP.

### 8.3 Выбор relay (found строки, логика inferred)

1. Клиент привязывается к предложенным relay (`wa_transport_p2p_start_relay_binds`; запросы bind / alloc в стиле STUN, `wa_stun_*`, id транзакций `tid=0x...`; bind и unbind требуют проверки целостности сообщения).
2. Задержка измеряется ping-запросами к каждому relay (`Ping request sent to relay N`), TCP-пробером (`wa_transport_tcp_prober_*`) и круговыми обходами allocate; лучший становится "elected relay" (`Elected relay idx=...`, `wa_transport_get_elected_relay_approximate_e2e_rtt`); арбитр (`wa_transport_path_arbiter_*`) переключает пути, а `prefer_relay` принудительно задаёт использование relay.
3. Server reflexive адрес, полученный из ответа allocate, логируется (`Server reflexive addr`).
4. Peer-to-peer пробуется параллельно по парам кандидатов (`p2p add_cand_pair`, `e2e bind probe`); relay остаётся запасным вариантом.

### 8.4 `relaylatency` (found)

Сериализаторы и обработчики: `serialize_relay_latency`, `send_or_enqueue_relay_latency`, `handle_relay_latency`, `unpack_and_apply_relay_latency`, пакетная отправка (`prepare_batched_relay_latencies`), с разбором ack `relaylatency ack: call_id is empty / has invalid type`. Станза сообщает пиру измеренный отправителем RTT для каждого индекса relay, пир применяет его (`apply_relay_latencies`, пороги `Ignored higher relay latency ...`). В offer групповых звонков задержка пропускается (`Skip relay latency at call offer in group calls`).

### 8.5 `transport` (found строки)

Атрибуты и дочерние элементы: `transport-message-type`, `p2p-cand-round` (перезапуск увеличивает раунд и очищает удалённых кандидатов), `ice-ufrag`, `ice-pwd`, `<certificate algorithm fingerprint>` (`cert_algorithm`, `cert_fingerprint`), `health_status`, записи кандидатов (адрес, приоритет). Строка `Web P2P: skipping type 13 send` показывает, что тип сообщения 13 относится к обмену ICE / DTLS web-P2P. Остальные номера подтипов не восстановлены (**unknown**).

### 8.6 Два медиапути

| Аспект | Путь relay WhatsApp (по умолчанию) | путь web-P2P |
|--------|------------------------------------|--------------|
| Установка | relay allocate / bind (в стиле STUN), токены из сигнализации | учётные данные ICE и отпечаток сертификата DTLS обмениваются в `transport`; `wa_ice_transport`, `CreateDtlsTransport` |
| Форма пакета | пакеты WhatsApp с RTP-payload ("WARP", тег целостности `warp_mi`, piggyback, FEC, `warp_rtx`) | RTP поверх DTLS-SRTP |
| Hop-ключ | relay `hbh_key` (hop-by-hop SRTP / SRTCP, hop-by-hop DTLS к relay `hbh_dtls_handshake_*`) | выводится из DTLS |
| E2E | E2E SRTP в 1:1, SFrame в группе (SFU) | SRTP |
| Назначение | обычные звонки приложение-приложение | взаимодействие с веб-клиентом (`set_peer_is_web`, `handle_transport_web_p2p`); inferred |
| Стек TLS | статически слинкованный mbedTLS (`mbedtls_ssl_*`, `mbedtls_gcm_*`, `mbedtls_hkdf`) | тот же |

Групповые звонки используют SFU с подписками (`RxSubscriptions`, `SenderSubscriptions`, protobuf `wa.voip.*` внутри канала данных), а не пути для каждого пира; оценка пропускной способности работает по каждому пути (`wa_warp_sfu_*`, "one side BWE").

---

## 9. Групповые звонки

### 9.1 `group_info` (found, строки `shared_elements/group.rs`)

| Элемент | Имя | Примечания |
|---------|-----|------------|
| атрибуты | `connected-limit`, `phash`, `transaction-id`, `media`, `joinable` | хеш состава и id порядка; `group_info has invalid connected_limit` |
| участники | `<user jid [user_pn push_name guest_name account_kind state ..]>` с дочерними `<device jid ..>`, либо `<participant jid pid>`; `<bot jid>` | `<user>` и `<participant>` одновременно — ошибка |
| на пользователя | `state`, `pid`, `capability` (`ver`), `rekey`, `terminated`, `connected`, `country_code`, `reason` | списки устройств обязательны для пользователей без nack |
| расширения | `extension_creator`, `ext_creator_identity_key_sig`, `extension_id`, `hn_video`, `gen`, `cohost`, `scope` | данные расширений / соведущих |

### 9.2 Поведение

- Лимит `Voip.kMaxSupportedGroupCallParticipants` = 64 (found); движок завершает звонок, чей update превышает максимум.
- `group_update` и `terminate` группового звонка несут id транзакций; устаревшие или пришедшие не по порядку игнорируются; `kInitialGroupTransactionId` = -1 (found).
- Групповой offer не несёт ключа звонка для каждого устройства; ключи повторно раздаются для каждого устройства через `enc_rekey` (inferred из `sendReKeyFanoutStanza`).
- Действия звонка и состава: `invite`, `inviteToGroupCall`, `cancelInviteToGroupCall`, повторный звонок (`rering_ts`, `make_and_send_cancel_offer_for_participants`), `sendRaiseHand`, `sendMutePeerRequestInGroupCall`, `sendRemoveRequest`; `lobby` — шаг присоединения к идущему групповому звонку (`joinOngoingCall`).
- Расширения: `add_extension` / `remove_extension` подключают к звонку второй медиаэндпоинт (`wa_call_extension_jid_*`, ключи owner и extension в 7.2, `kCallExtensionMV1`; Java особо обрабатывает JID расширений с префиксом user `01`, 6.1). Класс устройства не выяснен (inferred: спаренное носимое устройство, приложение содержит `libsmartglasses-bundle.so` и `Voip.sendWearableAttribution`).

---

## 10. Ссылки на звонки, зал ожидания, запланированные звонки

### 10.1 Ссылки (found)

| Элемент | Значение |
|---------|----------|
| URL | `https://call.whatsapp.com/{voice|video}/{token}`; хост в манифесте `call.whatsapp.com` |
| длина токена | `Voip.kCallLinkTokenLength` = 22 |
| создание | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` (лог `actionCreateCallLink` / `actionCreateCallLinkForEvent`); нативный `wa_call_link_create_v2` отклоняет неверное время начала |
| правка / предпросмотр | `editCallLink(token, ..., startTime, int)`, `previewCallLink`, `queryCallLinkForLinkEdit`; станзы `link_edit`, `link_query` |
| присоединение | `joinCallLink` отправляет `link_join`; ack `LinkJoinAck` несёт `call-creator`, `group_info`, `voip_settings`, информацию о ссылке |
| состояния ссылки | `kCallLinkState`: None 0, QuerySent 1, QueryAcked 2, JoinSent 3, JoinAcked 4 |
| `CallLinkInfo` | creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self |
| события nack | `linkCreateNacked`, `linkQueryNacked`, `linkJoinNacked`, `linkEditNacked` с кодом ошибки ack |

Станзы ссылок адресуются JID домена звонков (Rust-парсер JID перечисляет `callDomainJID` и `callJID`; соответствующий ему тип JID, принимаемый `C0DZ.A0R`, не выяснен).

### 10.2 Звонки-события (запланированные)

Звонок-событие — это ссылка на звонок, созданная с ненулевым `eventStartTimeSec` (found). Offer для запланированного звонка несёт `scheduled-id` (found в парсере). `Message` содержит два чат-сообщения:

| Поле Message | Номер | Тип | Содержимое (found) |
|--------------|-------|-----|--------------------|
| `scheduledCallCreationMessage` | **61** | ScheduledCallCreationMessage | `scheduledTimestampMs` 1, `callType` 2 (UNKNOWN 0, VOICE 1, VIDEO 2), `title` 3 |
| `scheduledCallEditMessage` | **65** | ScheduledCallEditMessage | `key` 1 (MessageKey), `editType` 2 (UNKNOWN 0, CANCEL 1) |

В качестве правки существует только отмена. Локальное хранилище (found): таблицы `message_scheduled_call` (`scheduled_timestamp_ms`, `call_type`, `title`), `message_add_on_scheduled_call_edit` (`creation_message_row_id`, ...), `message_system_scheduled_call_start` (`call_title`, `call_timestamp_ms`), `scheduled_calls` (`key_chat_row_id`, `key_id`, `scheduled_timestamp`, `is_upcoming`, `call_log_row_id`). Серверное напоминание (дочерний элемент call `reminder`, `kServerReminder*` ниже) и то, как сообщение о создании связано с токеном ссылки на звонок, не выяснены.

### 10.3 Зал ожидания

Станзы `waiting_room_toggle` (`link-token`, `media`, `enabled`, вариант для активного звонка), `_admit`, `_deny`, `_leave`, `_update`; разбираемые поля пользователя `jid`, `user_pn`, `push_name`, `guest_name`, `is_guest_eligible`, `state`. Java: `waitingRoomAdmit`, `waitingRoomAdmitAll`, `waitingRoomDeny`, `waitingRoomToggle`; события `waitingRoomAdmitAcked`, `waitingRoomDenyAcked`, `waitingRoomStateChanged`, `waitingRoomDenied`. `kServerReminder`: Legacy 0, LinkJoinedCreator 1, LinkJoinedJoiner 2, LinkConnectedCreator 3, LinkMissedCreator 4, LinkCreatorWaitingRoomJoined 5, LinkCreatorWaitingRoomMultipleJoined 6.

---

## 11. bcall, бот и альтернативные носители

### 11.1 Чат-сообщение `bcall` (found)

| Поле | Номер | Тип | Назначение |
|------|-------|-----|------------|
| `sessionId` | **1** | string | сессия business-звонка |
| `mediaType` | **2** | enum | UNKNOWN 0, AUDIO 1, VIDEO 2 |
| `masterKey` | **3** | bytes | обязателен: отсутствие ключа бросает `bcall message doesn't have master key` |
| `caption` | **4** | string | необязательно |

`Message.bcallMessage` = поле **72** (класс `DSA`); обработчик `F2V` (`FMessageBCallProtobuf`) сопоставляет его с типом сообщения 91 с id сессии, типом медиа (0 unknown, 1 audio, 2 video), подписью и байтами master key. `master key` — ключ, доставляемый внутри сквозно зашифрованного чат-сообщения; что именно он шифрует (inferred: медиа business-звонка), не прослежено. События движка `bCallCreated(callId, key, ...)`, `bCallJoined`, `bCallEnded`, `bCallAudienceUpdated`, `bCallCreateFailed`; `CallState.BCALL_STARTING`; входящие дочерние элементы `<call>` с именами `bcall_*` получают пустой call id (3.2). Нативные строки `bcall_start`, `bcall_notify` существуют.

### 11.2 Звонки ботов и HTTP / TEE-сигнализация

Звонки ботов: `CallInfo.isBotCall`, узлы `<bot>` в `group_info`, `verifyIncomingBotIdentityKey`, `reconfigure_bot` (`req_id`), процесс bot TOS (nack 488); offer объединяется с кэшированным построителем payload. Контекст: [WA_META_AI.md](WA_META_AI.md). Отдельно, `SignalingHttpCallback.sendMsg` позволяет движку обмениваться непрозрачными байтами сигнализации через `TeeRequestHandler` вместо chatd (`handle_http_tee_start_session_response`, `handle_http_create_extension_response`); типы запросов voice session и codec avatar. Условия допуска и формат payload **unknown** (inferred: сессии ботов и аватаров).

---

## 12. Журнал и история звонков

### 12.1 `callLogMesssage` (поле **69** в Message, класс `C49434Loq`, found)

| Поле | Номер | Тип | Значения |
|------|-------|-----|----------|
| `isVideo` | **1** | bool | |
| `callOutcome` | **2** | enum | CONNECTED 0, MISSED 1, FAILED 2, REJECTED 3, ACCEPTED_ELSEWHERE 4, ONGOING 5, SILENCED_BY_DND 6, SILENCED_UNKNOWN_CALLER 7 |
| `durationSecs` | **3** | int64 | |
| `callType` | **4** | enum | REGULAR 0, SCHEDULED_CALL 1, VOICE_CHAT 2 |
| `participants` | **5** | repeated `CallParticipant` | `jid` 1 (string), `callOutcome` 2 (тот же enum) |

Построитель `C53129Nna` (found): результат журнала звонка от движка (`Voip.kCallLog*`) сопоставляется так.

| Результат `kCallLog` | `callOutcome` на проводе |
|----------------------|--------------------------|
| Canceled 1, Missed 2 | MISSED |
| Unavailable 3 | FAILED |
| Rejected 4 | REJECTED |
| Connected 5 | CONNECTED |
| AcceptedElsewhere 6, ScreenedElsewhere 9 | ACCEPTED_ELSEWHERE |
| Invalid 0, Failed 7, ConnectedLonely 8, прочие | ONGOING (ветка по умолчанию в декомпилированном коде) |
| флаг DND / флаг неизвестного звонящего в записи | SILENCED_BY_DND / SILENCED_UNKNOWN_CALLER (проверяется первым) |

Сопоставление Failed 7 с ONGOING выглядит ошибочным, но это ветка по умолчанию в декомпилированном коде; считать это прочитанным, а не подтверждённым поведением. Тип звонка: локальный тип 1 соответствует SCHEDULED_CALL, 2 или 3 — VOICE_CHAT, иначе REGULAR. Отсутствие типа звонка бросает `call log message missing call_type`.

### 12.2 Локальная база данных (found)

Таблицы: `call_log` (`jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch`), `call_log_participant_v2` (`call_log_row_id`, `jid_row_id`, `call_result`), `joinable_call_log` (`call_id`, `joinable_video_call`, `group_jid_row_id`, `phash_identifier`, `self_other_device_connected`, `is_lgc_add`), `message_call_log`, `call_unknown_caller`, `reminder`. Питающие события: `callEnding(CallLogInfo, ..)`, `update1to1CallLog`, `updateJoinableCallLog` (`kUpdateJoinableCallLogType` Create 1, Update 2, Delete 3).

---

## 13. Состояния и константы движка (found, `Voip.java`, `CallState`)

| Группа | Значения |
|--------|----------|
| `CallState` | NONE, CALLING, PRE_ACCEPT_RECEIVED, RECEIVED_CALL, ACCEPT_SENT, ACCEPT_RECEIVED, ACTIVE, ACTIVE_ELSEWHERE, REJOINING, LINK, CONNECTED_LONELY, PRECALLING, ENDING, BCALL_STARTING, SCREENING |
| `kCallLog*` | Invalid 0, Canceled 1, Missed 2, Unavailable 3, Rejected 4, Connected 5, AcceptedElsewhere 6, Failed 7, ConnectedLonely 8, ScreenedElsewhere 9 |
| `kCallEndReason*` | Unknown 0, Timeout 1, Self 2, RejectDoNotDisturb 3, RejectBlocked 4, MicPermissionDenied 5, CameraPermissionDenied 6 |
| `kFatalReason*` | Unknown 0, ParticipantAllocationFailure 1, CallSetupError 2, CallTxTimeout 3, CallRxTimeout 4, VideoStreamCreateError 5, VideoPortCreateFailed 6, NoSamplingRatesForAudioRecord 7, AudioInitError 8 |
| `kOfferSilenceReason*` | None 0, Privacy 2, Lightweight 3, ScreenSharing 4, AddedAsLinkCreator 9, AddedForDeviceSwitching 10, GroupChatAdd 11 |
| `kParticipant*` | Connected 1, Incoming 2, Ringing 3, Rejected 4, Terminated 5, TimedOut 6, CreatingCall 7, Invited 11 |
| `kVideoState*` | Disabled 0, Enabled 1, Paused 2, UpgradeRequest 3, UpgradeAccept 4, UpgradeReject 5, Stopped 6, UpgradeRejectByTimeout 7, UpgradeCancel 8, UpgradeCancelByTimeout 9, UnknownPeer 10, Xr2dCodecAvatarEnabled 12, Error 20 |
| `kStatus*` | Success 0, InvalidArgument 70004, Exists 70015, Ignored 70020, CallAlreadyStarted 670001, CallNotActive 670007, CallHasNoVideo 670018, GroupCallUserExists 670021, GroupCallPeerCodecMismatch 670033, GroupCallUserExistsNotInvited 670038, NotPermitted 670040, UserNotRemovable 670041, UserNotConnected 670042 |
| `kScreenShareVersion*` | Legacy 0, 1 to 4 |
| `kNetworkHealth*` | Measuring 0, NoNetwork 1, Poor 2, Average 3, Good 4 |

Целые `kCallEndReason` — то, что видит UI; строки, помещаемые на провод при terminate, среди строк библиотеки отсутствуют (14.3).

---

## 14. Ошибки, reject, terminate

### 14.1 Коды nack для offer (found, `VoiceServiceEventCallback.callOfferNacked`)

Ack на offer с ошибками вызывает `callOfferNacked(errors[])`. Одиночная ошибка 304 или 400 считается дубликатом offer и игнорируется. Nack фатален, когда звонок в состоянии `CALLING` / `CONNECTED_LONELY` и nack получили все получатели (или сам звонящий), либо код равен 432; иначе он применяется к отдельным получателям и нефатален.

| Код | Фатальный путь (ветка в декомпилированном коде) | Нефатальный путь |
|-----|--------------------------------------------------|------------------|
| 401 | экран "not-allowed" (id причины 3) | |
| 403 | экран "not-allowed", id для видео, когда звонок видео | |
| 404 | not-allowed id 16 | текст "contact unavailable" для каждого получателя |
| 405 | id 4 | |
| 406 | id 2 (аудио) / 11 (видео) | |
| 411 | id 11 или 37 для lightweight | |
| 412 | id 10; информация о группе обновляется при несовпадении состава | |
| 426 | id 1 (аудио) / 9 (видео) | |
| 427 | id 12 или 36 для lightweight 1:1 | текст для каждого получателя; в группах свыше 4 участников альтернативный id |
| 428 | id 14 | текст для каждого получателя |
| 429 | только событие UI | |
| 431 | id 15 | текст "not available" |
| 432 | id 2; всегда фатален | |
| 435 | | текст для каждого получателя; после ack на offer также вызывает дополнительное действие |
| 460 / 463 | видео 10 / аудио 2; 463 id 17 | |
| 488 | bot TOS не принят: открывает процесс bot TOS | то же |
| 467, 468, 469 | | id 46 для нескольких получателей |
| 500, 502 | | текст "not available" |
| 538 | | id 35 |
| другие | id по умолчанию (видео 8 / 0) | assertion `Unknown error code` |

В декомпилированной фатальной ветке часть return потеряна, поэтому id лишь ориентировочные; список кодов и разделение на фатальные / нефатальные надёжны. Значения кодов помимо реакции клиента определяются на стороне сервера (**unknown**). После nack на полный offer движок не отправляет ни одной станзы звонка, кроме `terminate` (found строка).

### 14.2 Причины reject (found, `Voip.REJECT_REASON_*`)

| Строка | Значение / реакция клиента |
|--------|----------------------------|
| `` (пусто) | отклонено |
| `busy` | вызываемый занят; сигнал занятости, звонок завершается после задержки |
| `unavailable` | константа определена; основное использование найдено в коде присутствия / доступности |
| `uncallable` | пиру нельзя позвонить; экран not-allowed |
| `tos` | пир не принял TOS; экран not-allowed |
| `enc` | не удалось расшифровать ключ звонка |
| `server_conf_corrupted` | конфигурация сервера непригодна |

`rejectCall(callId, reason, int)` и `rejectPendingCall` — точки входа; `callRejectReceived` обрабатывает входящие причины. Причины reject сопоставляются с локальными результатами звонка (`reject_reason_to_call_result`, `set_call_term_reason_from_received_call_reject_reason`).

### 14.3 Terminate (found строки)

- `terminate` несёт id транзакции и узел `call_summary` (состояния пользователей, длительность); offer для завершённого звонка несёт `terminate_hint` с `terminate_reason`, `call_summary` и id транзакции. Есть ли у самого `terminate` атрибут `terminate_reason`, не выяснено.
- Terminate от companion-устройства движком игнорируется; основное устройство рассылает terminate multi-device пирам (`fanout_terminate_if_peer_is_md`).
- Terminate при переключении устройства в неверном состоянии игнорируется; исходы "handled elsewhere" выводятся из причины (`get_handled_elsewhere_outcome_from_terminate_reason`), а конфликтующие исходы для одного call id игнорируются.
- RTCP BYE на медиапути также завершает звонок (`rtcp_bye_terminate_delay`), как и удаление расширения сервером (`extension terminated by server`).
- Java отправляет `terminate` с повтором (очередь сохраняется между переподключениями), когда флаг **8003** включён, а звонок не является звонком бота и не находится в состоянии lonely; иначе без повтора (ветка частично неясна в декомпилированном выводе).
- Строковые значения `reason` в terminate (и любое сопоставление с `kCallEndReason`) не найдены ни в строках библиотеки, ни в других местах APK (**unknown**).

---

## 15. Feature-флаги (id как прочитаны в местах вызова; имена не выяснены)

| ID | Тип | Что контролирует |
|----|-----|------------------|
| **9257** | long мс | таймаут доставки offer; по таймауту станза отбрасывается (`CIX.A02`) |
| **9431** | long мс | таймаут доставки accept; также запоминает id станзы accept, чтобы `preSendTerminate` мог её отменить |
| **9432** | bool | при таймауте accept запускает переподключение |
| **8003** | bool | terminate с повтором (14.3) |
| **15125** | bool | сообщать метрику `call_stanza_drop` |
| **30890** | bool | отправлять ping исходящего звонка после offer |
| **30891** | long мс | таймаут ping, по умолчанию 3000 |
| **32651** | int | число попыток ping, минимум 1 |
| **31086** | bool | трекер исходящих offer |
| **24935** | bool | записывать `callEntryPoint` в `Message.call` |
| **520** | bool | добавлять контекст атрибуции рекламы в `Message.call` (inferred) |
| **20605** / **20606** | bool / int | добавлять `<tctoken>` в назначения звонка; ограничение числа пользователей на станзу |
| **24063** | bool | выбор типа сессии при расшифровке для класса шифртекстов (inferred) |
| **4217** | int mask | peek входящих offer: бит 1 голос, бит 2 видео |
| **3094** | int mask | бит 8 = асинхронные события звонка (`kFlagEnableCallEventAsync`); в паре с **9210** (bool) |
| **7481** | bool | состояние уведомления о заглушении группового звонка для связанных групповых звонков |
| **13630** / **13804** | int / bool | выборка для метрики расшифровки (inferred) |

Параметры движка (`p->enable_sframe_tx`, `tp->web_p2p_bitmap`, `tp->enable_e2e_bind_probe_bitmap`, `options.wa_log_time_series`, ...) приходят из серверного `voip_settings` и читаются через `Voip.getVoipParam`; их имена — строки в библиотеке, значения определяются сервером.

---

## 16. Baileys (`baron-baileys-v2`, исходники прочитаны, ничего не тестировалось)

| Тема | Baileys | Android |
|------|---------|---------|
| Offer | `offerCall`: случайный 32-hex `call-id`, `call-creator` = собственный id, `<audio enc=opus rate=16000/8000>`, `<video enc=vp8 dec=vp8 ...>` (видео), `<net medium=3>`, `<capability ver=1>` 6 байт `01 04 FF 83 CF 04`, `<encopt keygen=2>`, `<destination>` с зашифрованным через Signal `Message{call{callKey}}`, `count=0`, `device-identity`, когда порождается pkmsg | те же элементы; Android собирает offer в движке, байты capability неизвестны (5.2) |
| Конверт | `<call id to>` для offer; reject / accept / terminate используют `from` + `to` без `id` | всегда `<call to id>` (3.1) |
| accept | `<accept call-id call-creator count=0/>`, без дочерних элементов | accept движка несёт медиапараметры и сертификат (раздел 4) |
| terminate | `reason="user-terminated"`, `count=0` | строки причин неизвестны (14.3) |
| rekey | `<enc_rekey ...><enc v=2 type=msg/></enc_rekey>` | форма v2 соответствует 6.4; v3 отсутствует |
| Входящее | расшифровывает `<enc>` (`unpadRandomMax16`, `Message.decode`), кэширует offer, выдаёт события звонка; теги media / relay только подтверждаются ack | Android расшифровывает с тем же конвертом и передаёт движку |
| Ссылки | `link_create media` (+ `event start_time`) на `@call`; `waiting_room_toggle`; `link_join token` | грамматика совпадает с найденными здесь именами; тип целевого JID не выяснен |
| Статусы terminate | сопоставляет строки `terminate reason` `Timeout`, `RejectDoNotDisturb`, `MicPermissionDenied`, `CameraPermissionDenied`, `RemoteBusy`, `RemoteOffline` | этих строк нет в библиотеке; имена напоминают `kCallEndReason` (**inferred** связь) |

В Baileys нет выделения relay, нет WARP / SRTP / SFrame и нет движка, поэтому он может сигнализировать и вызывать звонок, но не может передавать медиа. Принимается ли и звонит ли у пира offer без полных параметров движка, не тестировалось.

---

## 17. Случаи ошибок

| Симптом | Причина | Исправление |
|---------|---------|-------------|
| `Wrong jid type` для станзы звонка | `to` не является JID user / device / домена звонков | адресовать JID устройства или пользователя |
| offer отправлен `without enc`, пир не звонит | ключ звонка не зашифрован (нет сессии, задача pre-key в ожидании) | сначала построить сессии; Android держит offer в ожидании |
| `duplicate <enc>` / `invalid retry count` / `invalid registration` | некорректный `<enc>`; `registration` не 4 байта | один `<enc>` с `count`; `registration` только при retry |
| nack offer 304 / 400 | дубликат offer | игнорировать |
| nack offer 401 / 403 / 463 | звонящему нельзя звонить этому пиру | на клиенте ничего |
| nack offer 412 / 488 | состав группы отличается / bot TOS не принят | обновить информацию о группе / принять bot TOS |
| reject `enc` | вызываемый не смог расшифровать ключ звонка | повторно отправить offer после восстановления сессии (`count` > 0) |
| `Unsupported keygen ver`, `can not receive both te and te2`, `num_tokens < 1` | недопустимые `encopt`, эндпоинты relay или токены | отправлять keygen 2 или 3, одно семейство эндпоинтов, хотя бы один токен |
| `bcall message doesn't have master key` | отсутствует `masterKey` | включить его |
| `Call stanza delivery timed out` | нет ack от chatd в пределах флага 9257 / 9431 | станза отброшена; accept может переподключиться (флаг 9432) |

---

## 18. Ключевые различия

| Не путать | С |
|-----------|---|
| `Message.call` (поле 10, E2E-ключ звонка внутри сообщения Signal) | `callLogMesssage` (69, запись исхода), `bcallMessage` (72, ключ сессии business) |
| `<enc>` в станзе звонка (парный шифртекст Signal) | сообщения sender-key `skmsg` и шифрование медиа |
| ключи E2E SRTP / SFrame (из ключа звонка) | hop-by-hop ключи (из `hbh_key` relay) |
| `<token>` / `<auth_token>` relay (учётные данные выделения) | `<tctoken>` (токен приватности внутри `<to>`) |
| целые `kCallEndReason` (UI), `kCallLog*` (результат движка) | строки причин terminate (на проводе, unknown), enum `callOutcome` (на проводе) |
| `CallLogMessage.CallType` REGULAR / SCHEDULED_CALL / VOICE_CHAT | `ScheduledCallCreationMessage.CallType` UNKNOWN / VOICE / VIDEO |
| `enc_rekey` v2 (дочерний `<enc>` Signal) | `enc_rekey` v3 (список protobuf `RekeyKeyEntry`) |
| путь relay WhatsApp (WARP, hop-by-hop SRTP) | путь web-P2P (ICE + DTLS-SRTP) |
| звонок-событие (ссылка со временем начала) | чат-сообщения о запланированных звонках (61 / 65) |
| сигнализация через chatd | HTTP / TEE-сигнализация для сессий ботов и аватаров |

---

## 19. Полный поток (звонок 1:1)

```
[Caller app]  startCall(callId, peer, video, ...)
     │
     ▼
[Native engine]  mints 32-byte callKey ; builds <offer> (audio, video, net, capability, encopt keygen)
     │  sendCallStanza(peer, callId, node)
     ▼
[OutgoingSignalingHandler]  per device: Message{call{callKey,...}} → Signal encrypt → <enc>
     │  <destination><to jid><enc/></to>…</destination> [tctoken] [device-identity if pkmsg]
     ▼
[CIX / writer]  <call to id><offer call-id call-creator>…</offer></call>     (delivery timeout, flag 9257)
     │
     ▼
[WA Server]  (not observed) enriches the offer: relay, voip_settings, metadata, privacy
     ├──────► [Caller]  offer ack: <relay> tokens, endpoints, hbh_key ; voip_settings ; or nack (14.1)
     ▼
[Callee]  <call from t e offline><offer/></call>
     │  CallStanzaHandler → nativeParseXmppOffer → C83 decrypt <enc> → callKey → ring (RECEIVED_CALL)
     ▼
[Callee]  preaccept ─► [Caller] PRE_ACCEPT_RECEIVED ;  accept (media params, certificate) ─► ACCEPT_RECEIVED
     │
     ▼
[Both engines]  relay allocate / bind with tokens ; transport / relaylatency / relay_info_update
     │  E2E keys from callKey (HKDF) ; hop-by-hop keys from hbh_key ; optional P2P pair or web_p2p DTLS
     ▼
[Media]  WARP packets via the elected relay or P2P ; ACTIVE ; in-call video, mute_v2, notify, heartbeat
     │
     ▼
[Either side]  terminate (transaction id, call_summary) ─► ack class="call" type="terminate"
     ▼
[Both]  callEnding(CallLogInfo) → call_log row / callLogMesssage ; teardown ; RTCP BYE
```

Отличия группового звонка: offer несёт `group_info` и не несёт ключа для каждого устройства; поздние участники используют `lobby` / `link_join`; rekey идут как `enc_rekey` (v2 fanout или v3) с id транзакций; медиа идёт через SFU с SFrame.

---

## 20. Неизвестное

| Элемент | Статус |
|---------|--------|
| Нативные построители / парсеры станз, строки `info` для HKDF, раскладки ключей | voip-библиотека не декомпилирована; только строки |
| Байты capability, коды `net medium`, значения параметров кодеков по умолчанию | не восстановлены |
| Значения `transport-message-type`, кроме 13 | не восстановлены |
| Строки `reason` в terminate, сопоставление reject -> причина завершения | не найдены |
| Смысл `e` в конверте, побочное действие при ошибке 435 в ack на offer | не выяснены |
| Таблица числовых id сообщений на 85 типов | отсутствует в строках этой сборки |
| Класс устройства-расширения, триггер rekey v3, триггер rekey группы | не выяснены |
| Тип JID link-звонка, связь запланированного звонка с токеном | не выяснены |
| Payload и допуск TEE / HTTP-сигнализации | не выяснены |
| Поведение сервера (обогащение, семантика nack, выбор relay) | на стороне сервера |
| Трафик | ничего не перехвачено |
