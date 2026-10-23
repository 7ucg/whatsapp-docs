<!-- src-sha1: 7c179c130d5822c6103aa9a9ae2e6751ec1b0bd8 -->
# WhatsApp Señalización de llamadas — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-24
**Alcance:** señalización de llamadas de voz/video en Android: envoltorio `<call>` y acks, stanzas de acción (offer, accept, preaccept, reject, terminate, transport, relaylatency, enc_rekey, mute_v2, group_info, group_update, lobby, link_*, waiting_room_*, bcall), payload del offer (audio / video / capability / encopt / net), clave de llamada y su cifrado Signal, rekey (v2 / v3), derivación de claves de medios, selección de relay y transporte, ICE / STUN / DTLS / SRTP frente a la ruta de medios específica de WhatsApp, llamadas grupales, enlaces de llamada y llamadas programadas, registro de llamadas y mensajes bcall, códigos nack del offer, comportamiento de reject y terminate, feature flags, comparación con Baileys

---

## 1. Qué es (técnicamente)

La señalización de llamadas es un conjunto de stanzas `<call>` sobre la conexión chatd normal (ver [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md)). Cada stanza lleva exactamente un hijo de acción. La capa Java no construye ni analiza stanzas de llamada: lo hace un motor VoIP nativo, y Java solo (a) envuelve los hijos salientes en `<call>`, (b) cifra con Signal la clave de llamada para cada dispositivo, (c) entrega las stanzas entrantes al motor, (d) reacciona a los eventos del motor. Los medios (tráfico tipo RTP hacia los relays, ICE, DTLS, SRTP) no son señalización y se ejecutan en sockets UDP/TCP propiedad del motor. Todas las afirmaciones provienen de análisis estático; no se capturó nada en la red. Niveles: **found** = leído en Java o en strings nativos, **inferred** = deducido, **unknown** = no resuelto.

| Capa | Nombre en 2.26.41.6 | Función |
|------|----------------|------|
| Fachada JNI | `Voip` / `VoipNativeImpl` (`com.whatsapp.calling.voipcalling`) | 148 métodos nativos (`startCall`, `acceptCall`, `rejectCall`, `nativeHandleIncomingSignalingXmpp`, ...) |
| Hook de salida | `OutgoingSignalingHandler` implementa `SignalingXmppCallback.sendCallStanza(Jid, callId, VoipStanzaChildNode)` | motor hacia Java; manejo por tag, cifrado de la clave de llamada |
| Escritor del envoltorio | `CIX` (cola), `C27410BtV` (stanza de llamada), caso 206 del writer-thread en `HandlerThreadC21920sG` | construye `<call to id>` |
| Handler de entrada | `C40641lA` (`CallStanzaHandler`), `BQU` (stanza de llamada analizada), `C83` (descifrado), `C28120CKj` / `RunnableC29343CoU` (despacho al motor) | analiza el envoltorio, descifra `<enc>`, alimenta el motor |
| Eventos del motor | `VoipEventCallback`, `VoiceServiceEventCallback` (116 callbacks) | motor hacia UI / estado |
| Callback de cifrado | `DefaultCryptoCallback`, `SignalIdentityCryptoCallback` (`CryptoCallback`) | HKDF / HMAC / aleatorios / firmas Ed para el motor |
| Señalización HTTP | `VoiceTeeHttpSignalingHandler` (`SignalingHttpCallback`) | portador de señalización alternativo, solicitud TEE |
| Motor nativo | `libwhatsapp.so` (desempaquetada del archivo superpack `libs.so`; exporta `Java_com_whatsapp_calling_voipcalling_Voip_*`) | serializadores / deserializadores de stanzas, máquina de estados de la llamada, transporte, medios |

Puntos que determinan el resto del informe:

- La gramática de las stanzas vive en código nativo: serializadores `serialize_*` (C/C++) y un crate de Rust `call_control` (rutas de código fuente `xplat/wa-voip/rust/call_control/src/stanza_deserializer/...` en sus strings de panic) para el análisis de entrada. La librería voip no se pudo decompilar; toda afirmación nativa se apoya solo en strings y nombres exportados (strings found, significado inferred).
- Java es una capa fina, por eso el conjunto de tags visto en Java (10 tags en `sendCallStanza`) es mucho menor que el que entiende el motor (sección 4).
- La clave de llamada la genera y usa el motor; Java la cifra con la sesión Signal pairwise ordinaria (sección 6). El mismo código HKDF que necesita el motor es un callback de Java (sección 7).
- La ruta de medios específica de WhatsApp (relay allocate/bind, paquetes "WARP", SRTP salto a salto, SFrame para llamadas grupales) es distinta de la ruta ICE/DTLS estilo WebRTC, que existe como modo "web_p2p" (sección 8).

---

## 2. Interfaz Java / nativa

Callbacks registrados al inicio (found): `SignalingXmppCallback.sendCallStanza(to, callId, node)` (motor hacia Java, un hijo de llamada); `CryptoCallback` (`generateE2EKeysV2`, `getSecureSsrc`, `hkdfSha256`, `hmacSha256`, `generateRandomBytes`; `SignalIdentityCryptoCallback` añade `signWithIdentityKey` con una firma de 64 bytes y `verifySignature` con una clave de 32 bytes); `SignalingHttpCallback` (`sendMsg(callId, bytes, requestType)`, `cancelMsg`; tipos voice session 0, codec avatar 1); `VoipEventCallback` (sección 13). `VoipStanzaChildNode` es el árbol visible por JNI (tag, atributos, hijos, datos); Java lo convierte desde y hacia el nodo chatd cuya codificación binaria se describe en [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) sección 8.

| Entrada JNI (found) | Alimentada por | Notas |
|-------------------|--------|-------|
| `nativeParseXmppOffer(CallOfferInfo[], ...)` | `preprocess_call_offer` (`AbstractC24816AmW`) | analiza un offer sin iniciar una llamada; `CallOfferInfo`: callId, fromJid, groupJid, callLinkToken, isVideoCall, isAudioChat, isJoinableCall, isOfferExpired, isCallEnded, silenceReason, groupPhash, participantHash, callGroupInfo |
| `nativeHandleIncomingXmppOffer` | `C28120CKj` | inicia el manejo de la llamada entrante |
| `nativeHandleIncomingSignalingXmpp` / `...Ack(from, type, errorCode, children, ..)` / `...Receipt` | `RunnableC29343CoU` (mensaje 192) | toda acción que no sea offer, acks de stanzas propias (el retorno 70004 se registra como ack corrupto), recibos de llamada |
| `peekIncomingOffer`, `handleIncomingTerminatePush` | ruta push | decisión previa al timbre, terminate entregado por push |
| `handleIncomingSignalingHttp(callId, bytes, ..)` | respuesta HTTP TEE | portador alternativo (11.3) |

---

## 3. Envoltorio, acks, recibos

### 3.1 `<call>` saliente (found, `HandlerThreadC21920sG` caso 206)

```
<call to="<jid>" id="<stanza id>">
  <ACTION .../>                      exactly one child
</call>
```

`to` debe pasar `C0DZ.A0R` (user, device y algunos otros tipos de JID; de lo contrario `C27410BtV` lanza `CallStanza:Wrong jid type`). El id de la stanza proviene del generador de ids compartido. Línea de log `WriterThread/write/call-stanza-<tag>`.

### 3.2 `<call>` entrante (found, `C40641lA`)

| Atributo | Manejo |
|-----------|----------|
| `from` | debe ser un JID válido, si no `CallStanza from invalid jid`; un JID de usuario se asigna a su dispositivo primario |
| `id` | id de la stanza, usado para el ack |
| `t` | segundos, multiplicados por 1000 |
| `e` | segundos enteros, multiplicados por 1000 y pasados al motor junto a `t` (significado exacto sin resolver; inferred: edad / entrada de expiración del offer) |
| `offline` | entero; su presencia marca la entrega desde la cola offline |
| `notify`, `platform`, `version` | se transmiten (push name del llamante, plataforma, versión de la app) |
| `participant` | JID de dispositivo del remitente en contextos de grupo; un valor mal formado recurre a `from` |
| `sender_lid` | se lee cuando `from` es un JID de dominio LID |
| hijo `call-creator` | JID de dispositivo (requerido para la lógica que no es offer) |
| hijo `call-id` | requerido; excepto los tags `reminder` y `bcall_*`, que reciben un call id vacío |
| otros atributos | `caller_pn` (JID de dispositivo con número de teléfono), `username`, `caller_country_code`; solo se leen cuando el creador es LID y el tag no es `offer` |

Si `to` y `call-creator` están en dominios de direcciones distintos (uno LID, otro número de teléfono), el cliente registra `CallStanzaHandler/call-mixed-domain/...` e informa la métrica `CallMixedDomainStanza`, y continúa (found). Los dominios mixtos se toleran, no se rechazan.

### 3.3 Acks

| Caso | Comportamiento (found) |
|------|-------------------|
| tag fuera de {offer, accept, reject, enc_rekey, terminate} | Java envía un ack de inmediato: `<ack class="call" type="<tag>" id to [participant]/>` (`AbstractC47181wT.A01`) |
| tag dentro de ese conjunto | sin ack inmediato de Java; el nodo pasa a una ruta separada de ack pendiente (`C36591ch.A0G`); semántica sin resolver |
| ack a una stanza propia | `nativeHandleIncomingSignalingXmppAck(from, type, errorCode, children, ...)`. Tipos de ack vistos en Java: offer (lleva datos de relay, sección 8), accept, link_join, link_query, lobby; el motor nativo también maneja link_create, link_edit, remove, remove_user, heartbeat, screen_share, add_extension, remove_extension, relaylatency, estado de video, waiting_room_* |
| ack de offer con error 435 | acción extra programada tras el ack (propósito sin resolver) |
| entrega de offer / accept | Java espera el ack de entrega de chatd con un timeout (flags 9257, 9431); al agotarse, la stanza se descarta y se registra `Call stanza delivery timed out` |

### 3.4 Tokens del diccionario (found, `AbstractC40911lb`)

De un solo byte (`A00`): `call` 97, `call-id` 101, `call-creator` 68, `terminate` 208, `relaylatency` 70, `video` 86, `audio` 158, `capability` 177, `device-identity` 227, `privacy` 223, `te` 212, `te2` 198, `token` 194, `key` 155, `participant` 5, `user` 14, `remove` 172, `notify` 24, `registration` 170, `attribute_padding` 229, `relay_id` 130, `token_id` 143. Diccionario secundario 0 (`A01[0]`): `offer` 28, `accept` 97, `preaccept` 18, `transport` 44, `mute_v2` 253, `group_info` 170, `group_update` 99, `net` 103, `medium` 36, `encopt` 21, `keygen` 26, `voip_settings` 10, `relay` 116, `joinable` 75, `heartbeat` 6, `transaction-id` 62, `uuid` 132, `self_pid` 71, `peer_pid` 76, `metadata` 118, `uncompressed` 20, `rate` 29, `dec` 73, `screen_width` 5, `reason` 46. Secundario 1: `reject` 0, `enc_rekey` 205, `e` 235.

No están en ningún diccionario de este build (strings planos en la red): `lobby`, `flowcontrol`, `screen_share`, `link_*`, `peer_state`, `interruption`, `reminder`, `raise_hand`, `waiting_room_*`, `hbh_key`, `auth_token`, `lightweight`, `silence`, `scheduled-id`, `group-jid`, `link-token`, `caller_pn` y `enc`.

---

## 4. Taxonomía de acciones

Tags entrantes que despacha el deserializador nativo (found, lista de strings en `call_control`): `offer`, `accept`, `preaccept`, `reject`, `terminate`, `transport`, `relaylatency`, `enc_rekey`, `notify`, `flowcontrol`, `interruption`, `group_update`, `mute_v2`, `screen_share`, `raise_hand`, `reconfigure_bot`, `user_action`, `ready`, `relay_info_update`, `tos`, `screen`, `switchable`, `add_extension`, `waiting_room_update`, más `receipt`. Acks analizados: offer, accept, estado de video, relaylatency, link_create / edit / query / join, lobby, heartbeat, remove, remove_user, screen_share, add_extension, remove_extension, waiting_room toggle / admit / deny / leave.

| Tag | Dirección (found) | Propósito |
|-----|-------------------|---------|
| `offer` | salida / entrada | iniciar una llamada (sección 5); entrada: también offers de llamadas ya terminadas con `is_call_ended` y `terminate_hint` |
| `preaccept` | salida / entrada | el dispositivo del destinatario está sonando / listo; estado del motor `PRE_ACCEPT_RECEIVED`, evento `preacceptReceived` |
| `accept` | salida / entrada | el destinatario acepta; lleva parámetros de medios y un certificado (strings nativos `error parse voip params for accept`, `error parsing certificate for accept`) |
| `reject` | salida / entrada | el destinatario rechaza; strings de motivo en la sección 14.2 |
| `terminate` | salida / entrada | terminar la llamada; id de transacción y `call_summary` (sección 14.3) |
| `transport` | salida / entrada | candidatos, credenciales ICE, certificado, salud (sección 8.5) |
| `relaylatency` | salida / entrada | latencias de relay medidas (sección 8.4); tiene su propio ack |
| `enc_rekey` | salida / entrada | recompartir la clave de llamada (sección 6.4) |
| `video` (estado) | salida / entrada | video activado / desactivado / mejora; valores `kVideoState*` (sección 13); el ack lleva información de relay |
| `notify`, `peer_state`, `flowcontrol`, `interruption`, `ready`, `heartbeat` | salida / entrada | estado en llamada: avisos del par, salud de red, control de flujo, interrupciones, heartbeat de grupo |
| `mute_v2`, `raise_hand`, `user_action`, `tos`, `reconfigure_bot` | salida / entrada | solicitud de silenciar en llamadas grupales, levantar la mano, acciones de usuario, TOS de llamada grupal, reconfiguración de bot (atributo `req_id`) |
| `group_info`, `group_update` | entrada (hijo de offer / ack / update) | roster (sección 9) |
| `lobby` | salida / entrada | consulta / estado del lobby de llamada grupal; su ack lleva información de grupo |
| `screen`, `screen_share`, `switchable` | salida / entrada | estado de compartir pantalla; cambio de dispositivo (`switch_info`, `root_call_id`, `root_call_creator`, `peer_active_device`) |
| `add_extension`, `remove_extension` | salida / entrada | añadir un endpoint de medios ("extensión") a una llamada (sección 9.4) |
| `remove`, `remove_user`, `cancel_offer` | salida | quitar participantes; cancelar un offer para participantes elegidos |
| `link_create`, `link_edit`, `link_query`, `link_join` | salida | enlaces de llamada (sección 10) |
| `waiting_room_toggle`, `_admit`, `_deny`, `_leave`, `_update` | salida / entrada | sala de espera de llamadas por enlace (sección 10.3) |
| `reminder`, `bcall_*` | entrada | recordatorios del servidor; familia de llamadas de negocio (sección 11) |
| `dtmf`, `duration`, `connect_stat`, `group_call_duration`, `group_call_tos_accepted` | salida | serializadores presentes en el motor |

Tags visibles en Java en `sendCallStanza` (found): `offer`, `accept`, `reject`, `terminate`, `video`, `enc_rekey`, `lobby`, `link_join`, `link_query`, `link_create`; todos los demás tags toman la ruta de envío por defecto.

Tabla numérica de ids de mensaje (85 tipos), división por mecanismo (hijo / ack / recibo / interno) y longitudes fijas de cabecera: no encontradas en este build. El motor expone tags y serializadores por tag, no un enum de ids visible en strings. Considerar cualquier tabla de ids como unknown para Android.

---

## 5. Offer

### 5.1 Construcción y envío (found)

`startCall(...)` hace que el motor emita `sendCallStanza(peer, callId, offerNode)`. Java:

1. `sendOfferStanza` guarda el id de la stanza (`outgoingCallOfferKey`), espera mientras haya un job de pre-key pendiente para algún dispositivo destino y luego cifra la clave de llamada por dispositivo en un worker (`getBulkEncryptedE2EKeys`, sección 6.1).
2. El resultado se escribe en el formato nuevo (`<destination><to jid><enc/></to>...</destination>`, vía `AbstractC33466EhY.A08`) o en el formato antiguo (un único hijo `<enc>`, válido solo para un dispositivo; `cannot have multiple encrypted messages in old format!`).
3. Si algún dispositivo recibió un `pkmsg`, se añade `<device-identity>` (bytes de `adv_signed_identity` de las preferencias del companion); esto ocurre solo cuando el dispositivo propio pasa `BRD()` (id de dispositivo de registro distinto de cero, es decir un companion; inferred).
4. `CIX.A02` encola la stanza `<call>`; el flag **9257** (ms) acota la espera de entrega.
5. Tras el envío se programa un IQ de ping de llamada (flag **30890**, retardo **30891** ms por defecto 3000, intentos **32651**); si la conexión está caída el cliente reconecta, salvo que la llamada ya no esté en estado `CALLING`.
6. Si los destinos no se pueden cifrar, el offer se conserva como `pendingCallOfferStanza` y se envía después (`maybeSendPendingOffer` cuando termina un job de pre-key, `sendPendingCallOfferStanza` en terminate). `preSendTerminate` saca de la cola de reintentos un offer sin ack antes de que salga un terminate.

### 5.2 Hijos y atributos

| Elemento | Origen | Atributos / contenido |
|---------|--------|----------------------|
| `<offer>` | envío | `call-id`, `call-creator` (JID de dispositivo); recepción: `caller_pn`, `username`, `caller_country_code`, `group-jid`, `scheduled-id`, `joinable`, `lightweight` (`1` = timbre de grupo ligero / solo audio), `rering_ts`, `is_call_ended`, `type` |
| `<audio>` (se repite) | envío | `enc` (códec), `rate` (frecuencia de muestreo); `enc` y `rate` son tokens del diccionario |
| `<video>` | envío | `enc`, `dec`, `device_orientation`, `screen_width`, `screen_height`; strings de valor vistos en el motor: `h.264`, `vp8`, `vp8/h.264`; el atributo `fps` también aparece como string (atributo de video inferred) |
| `<net>` | envío | `medium` (tipo de red), más tarde `health_status` en transport |
| `<capability>` | envío | `ver` + máscara de bits opaca (`pjmedia_voip_capabilities_*`: versión, `bit_mask_length`); el string `vid_dec` por dispositivo lista los códecs de video decodificables (`vid_codec_capability_str_to_bitmask`) |
| `<encopt>` | envío | `keygen` = versión de generación de clave; el motor rechaza otros valores (`Unsupported keygen ver`); existen las versiones 2 y 3 (sección 6.4) |
| `<destination>` / `<to jid>` / `<enc>` | envío | clave de llamada cifrada por dispositivo (sección 6.1); `<to>` puede llevar `peer_recipient_lid`, `peer_recipient_pn`, `peer_recipient_username`, `eph_setting` |
| `<tctoken>` | envío | dentro de `<to>`, como máximo una vez por usuario, cuando el flag **20605** está activo y menos de **20606** usuarios ya llevan uno; misma familia de token que [WA_TCTOKEN_CSTOKEN.md](WA_TCTOKEN_CSTOKEN.md) |
| `<device-identity>` | envío | bytes de la identidad firmada ADV, ver 5.1 paso 3 |
| `<privacy>` | recepción | token de privacidad (el nombre del token está en el diccionario); contenido no rastreado |
| `<relay>` | recepción / ack | lista de relays (sección 8) |
| `<voip_settings>` | recepción / ack | parámetros del motor provistos por el servidor; atributo `uncompressed`; los payloads comprimidos se rechazan en una ruta (`unexpected compressed voip params`) y `zlib inflate` está enlazado (formato de compresión inferred) |
| `<metadata>` | recepción | atributos del bucket de A/B test del par (`peer_abtest_bucket`, `peer_abtest_bucket_id_list`) |
| `<silence reason>` | recepción | el offer es silencioso (sin timbre); `BQU.A02`; enteros de motivo `kOfferSilenceReason*` (sección 13) |
| `<group_info>` | recepción | roster de una llamada grupal (sección 9) |
| `<terminate_hint>` / `<call_summary>` | recepción | un offer de una llamada que ya terminó (`is_call_ended=1`): `terminate_reason`, id de transacción, resumen |
| `<link_info>`, `<waiting_room>`, `<bot>`, info de extensión | recepción | datos de enlace, sala de espera, bot y extensión |

Los valores de byte exactos de `<capability>` y de los códigos de `net medium` no se recuperaron de este build (a veces se cita para clientes web una máscara de 7 bytes `01 05 F7 09 E4 BB 13`; no aparece como literal contiguo en la librería de Android, así que el valor de Android debe tratarse como unknown). El motor incluye los códecs que nombra en strings: Opus más un códec propio de baja tasa de bits ("mlow", con framing Opus), OpenH264, VP8, AV1 (`wzav1`) y HEVC mediante MediaCodec.

### 5.3 Ruta de recepción (found)

1. `CallStanzaHandler` construye `BQU`; métrica `CallStanzaHandler/handleStanza tag=... callId=...`; el mensaje 192 se publica en el dispatcher.
2. Para un offer, `preprocess_call_offer` ejecuta `nativeParseXmppOffer`; un retorno distinto de cero descarta la stanza. Los offers expirados o terminados no suenan.
3. `C83.A00` descifra el `<enc>` (sección 6.2), luego `nativeHandleIncomingXmppOffer` inicia la llamada; estado `RECEIVED_CALL`.
4. `peekIncomingOffer` (verificación previa guiada por push) ignora offers silenciados, offers de grupo (con `group_info`), offers con `is_call_ended=1`, offers 1:1 sin `<enc>` y offers mientras el teléfono está ocupado; el flag **4217** bit 1 habilita peeks de voz, bit 2 peeks de video.
5. Un `terminate` posterior o el push `handleIncomingTerminatePush` finaliza un peek.

---

## 6. Clave de llamada y su cifrado

### 6.1 Saliente (found, `getBulkEncryptedE2EKeys`)

El motor entrega un mapa de JID de dispositivo a bytes de la clave de llamada en crudo. Para cada dispositivo sin job de pre-key pendiente, el cliente construye un protobuf `Message` y lo cifra con Signal usando la sesión pairwise existente (`C83` / `CallableC29363Coo`):

| Campo de Message.Call | Número | Tipo | Se establece cuando |
|--------------------|--------|------|---------|
| `callKey` | **1** | bytes | siempre (32 bytes en crudo) |
| `conversionSource` / `conversionData` / `conversionDelaySeconds` | **2** / **3** / **4** | string / bytes / uint32 | hay datos CTWA |
| `ctwaSignals` / `ctwaPayload` | **5** / **6** | string / bytes | hay datos CTWA |
| `contextInfo` | **7** | ContextInfo | flag CTWA (`externalAdReply.adType` fijado a un valor fijo) |
| `nativeFlowCallButtonPayload` | **8** | string | llamada iniciada desde un botón native-flow |
| `deeplinkPayload` | **9** | string | llamada iniciada desde un deeplink |
| `messageContextInfo` | **10** | MessageContextInfo | enriquecimiento por par realizado por `AbstractC30999De0` (contenido no rastreado) |
| `callEntryPoint` | **11** | uint32 | flag **24935**, solo en el fanout inicial (`i == 0`) |
| `callReason` | **12** | string | presente en el proto, no se establece en esta ruta |

`Message.call` es el campo **10** de `Message` (`C30628DTw`), la clase `Message.Call` = `C25827BCl`. Para el offer inicial, el flag **520** añade contexto de atribución de anuncios desde el resolvedor CTWA (`C35832FfR`; inferred). Un fanout se ejecuta con `i == 0` para offers e `i == 1` para rekeys. El cifrado es bloqueante con ruta de cancelación; un bloqueo superior a 5000 ms registra `voip_e2e_encryption_blocked`.

Forma en la red de un dispositivo (found, `AbstractC33466EhY.A03/A09`): `<enc v="<version>" type="msg|pkmsg|skmsg|frskmsg|msmsg" [count="<retry>"] [mediatype] [session_type="pq"] [bucket]>CIPHERTEXT</enc>`. `session_type="pq"` marca una sesión Signal post-cuántica; `count` se omite cuando es 0. Las claves de llamada nunca son mensajes sender-key de grupo en esta ruta (el tipo `skmsg` lo acepta el helper pero ninguna ruta de llamada lo produce; inferred).

Los dispositivos de extensión (prefijo de usuario del JID `01`) usan `sendReKeyToExtension`: se procesa un prekey bundle almacenado antes, y la clave se cifra como `pkmsg` con `v="2"` (found).

### 6.2 Entrante (found, `C83.A00`)

| Paso | Detalle |
|------|--------|
| hijos leídos | `registration` (debe ser de 4 bytes; id de registro Signal, usado para reintento), `device-identity`, `enc` |
| duplicados | un segundo `<enc>` se descarta (`duplicate <enc>`) |
| contador de reintentos | `count` en `<enc>`; si falta el valor se aborta (`invalid retry count`) |
| tipo | se aceptan `msg` 0 o `pkmsg` 1; otros números registran `unrecognized ciphertext type` |
| descifrado | descifrado Signal pairwise (mensaje de pre-key procesado con la identidad de dispositivo del remitente); payload analizado como `Message`, se toma `call.callKey`; se registra `ExternalAdReplyInfo.adType` de CAWC |
| resultado | `<enc>` se reemplaza por un nodo `<enc>` plano con los bytes de la clave de llamada para el motor |
| fallo | evento `rejectedDecryptionFailure`, `onPeerE2EDecryptionFailed` reintenta el establecimiento de sesión (obtener una pre-key nueva cuando el id de registro es igual y la base key se repite); el motivo de reject `enc` se envía cuando la llamada no se puede descifrar |

El flag **24063** cambia la ruta de tipo de sesión usada para ciphertexts de tipo hosted (inferred a partir de la condición `c33281EeX.A04`).

### 6.3 Reintento

`sendOfferRetryRequest(device)` hace que el motor reenvíe el offer (`resendOfferOnDecryptionFailure`); `sendPendingRekeyRequest` repite una solicitud de rekey mientras el byte de reintento almacenado esté en 0..4. Por tanto `count` va de 0 a 4 (found, `sendPendingRekeyRequest`).

### 6.4 `enc_rekey`: tres formas

| Forma | Evidencia | Contenido |
|-------|----------|---------|
| v2 unicast | `sendReKeyStanza` (Java) | el motor emite `<enc_rekey call-id call-creator transaction-id><enc count=N>RAW KEY</enc></enc_rekey>`; Java reemplaza el hijo por el `<enc>` cifrado con Signal para el dispositivo destino (found) |
| v2 fanout | `sendReKeyFanoutStanza` | el destino es un grupo; hijo `<destination><to jid><enc/></to>...`; cada entrada se cifra por separado (found) |
| v3 | strings nativos `handle_enc_rekey_v3`, `make_and_send_rekey_v3`, `ext_rekey: ...` | el payload es un protobuf con `wa.voip.RekeyKeyEntry` repetidos (tipo de clave + clave); las claves por tipo tienen longitud fija (`key type %d has unexpected length`); se selecciona cuando keygen es 3; requiere soporte de extensiones (`kCallExtensionMV1`); se registra la transición de v3 a v2 |

Reglas visibles en strings: los rekeys llevan un id de transacción; los ids tempranos, antiguos o iguales se ignoran (`ignore old rekey msg with transaction id`); en una llamada uno a uno el `enc_rekey` entrante se ignora (`ignore rekey msg in one to one call`); `request_keys` pide al creador o a una extensión que reenvíe las claves (solo v3; `request_keys with unexpected keygen` se ignora). Qué lado inicia un rekey en una llamada grupal, y el disparador exacto, no están resueltos.

---

## 7. Derivación de claves de medios

### 7.1 Callbacks de Java (found)

| Callback | Cálculo |
|----------|-------------|
| `generateE2EKeysV2(callKey[32], out[46], info)` | HKDF-SHA256, salt = 32 bytes cero, IKM = clave de llamada, info = string UTF-8 `info` suministrado por el motor, 46 bytes de salida (`E2E_EXTENDED_V2_KEY_LENGTH`) |
| `hkdfSha256(salt, ikm, info, out)` | HKDF-SHA256 genérico (primer argumento salt, segundo IKM, tercero info; longitud de salida = `out.length`) |
| `getSecureSsrc(ikm, info, salt[4], out[4])` | HKDF-SHA256 a 4 bytes (`SECURE_SSRC_LENGTH`) |
| `hmacSha256(key, data, out[32])` | HMAC-SHA256 |
| `generateRandomBytes(out)` | `SecureRandom` (origen de la clave de llamada de 32 bytes; inferred) |

### 7.2 Etiquetas y contextos en el motor (strings found, función inferred)

`e2e sframe key`, `hbh srtp key`, `uplink hbh srtcp key`, `downlink hbh srtcp key`, `warp auth key`; funciones `derive_sframe_key`, `derive_hbh_srtp_key`, `derive_and_update_warp_mi_keys`, `derive_extension_per_media_key`; slots de clave `owner_e2e_key`, `extension_audio_key`, `extension_video_key`, `extension_appdata_key`.

| Clave | Origen (inferred) | Protege |
|-----|-------------------|----------|
| Material E2E SRTP | salida de `generateE2EKeysV2` (46 bytes), por participante | medios entre endpoints (1:1) |
| Clave SFrame | etiqueta `e2e sframe key` | cifrado de frames en llamadas grupales / SFU y el canal de datos salto a salto (`wa_sframe_encrypt`, `sframe_keyprovider_set_chainkey`) |
| SRTP / SRTCP salto a salto | `hbh_key` provista por el relay (sección 8.2) con las etiquetas `hbh ...` | solo el tramo cliente a relay |
| Clave WARP MI | etiqueta `warp auth key` | tag de integridad de mensajes de los paquetes WARP (`warp_mi_tag_len`) |

Los layouts de clave (cuál de los 46 bytes es clave o salt, por dirección), el contenido del string `info` y las cadenas HKDF exactas para SFrame / salto a salto no se recuperaron: los llamadores están en código nativo que no se pudo decompilar. Un JID calificado por dispositivo como `info` es plausible pero no verificado (**unknown**).

---

## 8. Relay, transporte y ruta de medios

### 8.1 Qué recibe el cliente

Los datos de relay llegan en el ack del offer (llamante; `error during parsing relay info`, `Failed to parse relay info in offer ack`), en el propio offer (destinatario), y más tarde en `relay_info_update` y en el ack de un cambio de estado `video` (found).

### 8.2 Gramática de `<relay>` (found, strings de `fill_relay_info`)

| Elemento | Nombre | Notas |
|------|------|-------|
| atributos del relay | `uuid`, `self_participant_uuid`, `conn_id`, `medium`, `warp_mi_tag_len`, `prefer_relay`, `prefer_ipv6`, `peer_dl`, `smart_transport_signal`, `attribute_padding` | por conjunto de relays |
| tokens | lista de `<token>` (`token_id`), al menos uno requerido (`relay_token_list.num_tokens < 1`) | credencial del relay; la lista se copia en la solicitud allocate |
| auth tokens | `<auth_token>` (`auth_token_id`) | se usa en lugar de un token cuando el id está en rango; si no, "falling back to relay token" |
| clave | `<key>` | material de contraseña del relay |
| `hbh_key` | hijo con bytes en crudo o base64 | origen de la clave salto a salto; se comprueba el tamaño (`HBH Key of unexpected size`, "though warp_mi_tag_len = ...") |
| endpoints | `<te>` o `<te2>` | nunca ambos (`can not receive both te and te2 endpoints`); bytes de dirección IPv4 o IPv6 (`endpoint too short for an IPv6 address`); dirección vacía rechazada |
| por endpoint | `relay_id`, `relay_name` (truncado si es demasiado largo), `domain_name`, `latency`, `c2r_rtt`, `ul_bw`, `dl_bw`, `is_favored` | `latency` alimenta la elección de relay |
| participantes | `<participant pid jid>` | asigna los ids de participante usados en paquetes WARP / SFU |

Las cadenas de log imprimen direcciones de relay mediante un marcador `[MetaServiceIP]`, por lo que las direcciones de relay se tratan como IPs de servicio.

### 8.3 Selección de relay (strings found, lógica inferred)

1. El cliente se vincula (bind) a los relays ofrecidos (`wa_transport_p2p_start_relay_binds`; las solicitudes bind / alloc son estilo STUN, `wa_stun_*`, ids de transacción `tid=0x...`; bind y unbind requieren message integrity).
2. La latencia se mide mediante solicitudes ping por relay (`Ping request sent to relay N`), un prober TCP (`wa_transport_tcp_prober_*`) y round trips de allocate; el mejor pasa a ser el "elected relay" (`Elected relay idx=...`, `wa_transport_get_elected_relay_approximate_e2e_rtt`); un árbitro (`wa_transport_path_arbiter_*`) cambia de ruta, y `prefer_relay` fuerza el uso del relay.
3. Se registra una dirección server reflexive aprendida de la respuesta allocate (`Server reflexive addr`).
4. Peer-to-peer se intenta en paralelo mediante pares de candidatos (`p2p add_cand_pair`, `e2e bind probe`); el relay queda como respaldo.

### 8.4 `relaylatency` (found)

Serializadores y handlers: `serialize_relay_latency`, `send_or_enqueue_relay_latency`, `handle_relay_latency`, `unpack_and_apply_relay_latency`, por lotes (`prepare_batched_relay_latencies`), con análisis de ack `relaylatency ack: call_id is empty / has invalid type`. La stanza informa al par del RTT medido por el remitente por cada índice de relay, y el par lo aplica (`apply_relay_latencies`, umbrales `Ignored higher relay latency ...`). La latencia se omite en offers de llamadas grupales (`Skip relay latency at call offer in group calls`).

### 8.5 `transport` (strings found)

Atributos e hijos: `transport-message-type`, `p2p-cand-round` (un reinicio incrementa la ronda y borra los candidatos remotos), `ice-ufrag`, `ice-pwd`, `<certificate algorithm fingerprint>` (`cert_algorithm`, `cert_fingerprint`), `health_status`, entradas de candidatos (dirección, prioridad). El string `Web P2P: skipping type 13 send` muestra que el tipo de mensaje 13 pertenece al intercambio ICE / DTLS de web-P2P. Los demás números de subtipo no se recuperaron (**unknown**).

### 8.6 Dos rutas de medios

| Aspecto | Ruta de relay de WhatsApp (por defecto) | Ruta web-P2P |
|--------|-------------------------------|--------------|
| Establecimiento | relay allocate / bind (estilo STUN), tokens desde la señalización | credenciales ICE y huella del certificado DTLS intercambiadas en `transport`; `wa_ice_transport`, `CreateDtlsTransport` |
| Forma del paquete | paquetes de WhatsApp con payload RTP ("WARP", tag de integridad `warp_mi`, piggyback, FEC, `warp_rtx`) | RTP sobre DTLS-SRTP |
| Clave de salto | `hbh_key` del relay (SRTP / SRTCP salto a salto, DTLS salto a salto hacia el relay `hbh_dtls_handshake_*`) | derivada de DTLS |
| E2E | E2E SRTP en 1:1, SFrame en grupo (SFU) | SRTP |
| Propósito | llamadas normales app a app | interoperabilidad con el cliente web (`set_peer_is_web`, `handle_transport_web_p2p`); inferred |
| Stack TLS | mbedTLS enlazado estáticamente (`mbedtls_ssl_*`, `mbedtls_gcm_*`, `mbedtls_hkdf`) | igual |

Las llamadas grupales usan un SFU con suscripciones (`RxSubscriptions`, `SenderSubscriptions`, protobufs `wa.voip.*` dentro del canal de datos) en lugar de rutas por par; la estimación de ancho de banda corre por ruta (`wa_warp_sfu_*`, "one side BWE").

---

## 9. Llamadas grupales

### 9.1 `group_info` (found, strings de `shared_elements/group.rs`)

| Elemento | Nombre | Notas |
|------|------|-------|
| atributos | `connected-limit`, `phash`, `transaction-id`, `media`, `joinable` | hash del roster e id de ordenamiento; `group_info has invalid connected_limit` |
| miembros | `<user jid [user_pn push_name guest_name account_kind state ..]>` con hijos `<device jid ..>`, o `<participant jid pid>`; `<bot jid>` | `<user>` y `<participant>` juntos es un error |
| por usuario | `state`, `pid`, `capability` (`ver`), `rekey`, `terminated`, `connected`, `country_code`, `reason` | listas de dispositivos requeridas para usuarios sin nack |
| extensiones | `extension_creator`, `ext_creator_identity_key_sig`, `extension_id`, `hn_video`, `gen`, `cohost`, `scope` | datos de extensión / co-host |

### 9.2 Comportamiento

- Límite `Voip.kMaxSupportedGroupCallParticipants` = 64 (found); el motor termina una llamada cuya actualización excede el máximo.
- `group_update` y el `terminate` de llamada grupal llevan ids de transacción; los obsoletos o fuera de orden se ignoran; `kInitialGroupTransactionId` = -1 (found).
- El offer grupal no lleva clave de llamada por dispositivo; las claves se recomparten por dispositivo con `enc_rekey` (inferred a partir de `sendReKeyFanoutStanza`).
- Acciones de timbre y roster: `invite`, `inviteToGroupCall`, `cancelInviteToGroupCall`, re-ring (`rering_ts`, `make_and_send_cancel_offer_for_participants`), `sendRaiseHand`, `sendMutePeerRequestInGroupCall`, `sendRemoveRequest`; `lobby` es el paso de unión de una llamada grupal en curso (`joinOngoingCall`).
- Extensiones: `add_extension` / `remove_extension` adjuntan un segundo endpoint de medios a una llamada (`wa_call_extension_jid_*`, claves de owner y extensión en 7.2, `kCallExtensionMV1`; Java trata de forma especial los JIDs de extensión con prefijo de usuario `01`, 6.1). La clase de dispositivo no está resuelta (inferred: un wearable emparejado, la app incluye `libsmartglasses-bundle.so` y `Voip.sendWearableAttribution`).

---

## 10. Enlaces de llamada, sala de espera, llamadas programadas

### 10.1 Enlaces (found)

| Elemento | Valor |
|------|-------|
| URL | `https://call.whatsapp.com/{voice|video}/{token}`; host del manifest `call.whatsapp.com` |
| longitud del token | `Voip.kCallLinkTokenLength` = 22 |
| crear | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` (log `actionCreateCallLink` / `actionCreateCallLinkForEvent`); el nativo `wa_call_link_create_v2` rechaza una hora de inicio incorrecta |
| editar / vista previa | `editCallLink(token, ..., startTime, int)`, `previewCallLink`, `queryCallLinkForLinkEdit`; stanzas `link_edit`, `link_query` |
| unirse | `joinCallLink` envía `link_join`; el ack `LinkJoinAck` lleva `call-creator`, `group_info`, `voip_settings`, info del enlace |
| estados del enlace | `kCallLinkState`: None 0, QuerySent 1, QueryAcked 2, JoinSent 3, JoinAcked 4 |
| `CallLinkInfo` | creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self |
| eventos nack | `linkCreateNacked`, `linkQueryNacked`, `linkJoinNacked`, `linkEditNacked` con el código de error del ack |

Las stanzas de enlace se dirigen a un JID de dominio de llamada (el parser de JID en Rust lista `callDomainJID` y `callJID`; el tipo de JID aceptado por `C0DZ.A0R` que le corresponde no se resolvió).

### 10.2 Llamadas de evento (programadas)

Una llamada de evento es un enlace de llamada creado con un `eventStartTimeSec` distinto de cero (found). El offer de una llamada programada lleva `scheduled-id` (found en el parser). `Message` lleva dos mensajes de chat:

| Campo de Message | Número | Tipo | Contenido (found) |
|---------------|--------|------|-----------------|
| `scheduledCallCreationMessage` | **61** | ScheduledCallCreationMessage | `scheduledTimestampMs` 1, `callType` 2 (UNKNOWN 0, VOICE 1, VIDEO 2), `title` 3 |
| `scheduledCallEditMessage` | **65** | ScheduledCallEditMessage | `key` 1 (MessageKey), `editType` 2 (UNKNOWN 0, CANCEL 1) |

Solo existe cancelar como edición. Almacenamiento local (found): tablas `message_scheduled_call` (`scheduled_timestamp_ms`, `call_type`, `title`), `message_add_on_scheduled_call_edit` (`creation_message_row_id`, ...), `message_system_scheduled_call_start` (`call_title`, `call_timestamp_ms`), `scheduled_calls` (`key_chat_row_id`, `key_id`, `scheduled_timestamp`, `is_upcoming`, `call_log_row_id`). El recordatorio del lado del servidor (un hijo de llamada `reminder`, `kServerReminder*` más abajo) y cómo el mensaje de creación se vincula con el token del enlace de llamada no están resueltos.

### 10.3 Sala de espera

Stanzas `waiting_room_toggle` (`link-token`, `media`, `enabled`, variante de llamada activa), `_admit`, `_deny`, `_leave`, `_update`; campos de usuario analizados `jid`, `user_pn`, `push_name`, `guest_name`, `is_guest_eligible`, `state`. Java: `waitingRoomAdmit`, `waitingRoomAdmitAll`, `waitingRoomDeny`, `waitingRoomToggle`; eventos `waitingRoomAdmitAcked`, `waitingRoomDenyAcked`, `waitingRoomStateChanged`, `waitingRoomDenied`. `kServerReminder`: Legacy 0, LinkJoinedCreator 1, LinkJoinedJoiner 2, LinkConnectedCreator 3, LinkMissedCreator 4, LinkCreatorWaitingRoomJoined 5, LinkCreatorWaitingRoomMultipleJoined 6.

---

## 11. bcall, bot y portadores alternativos

### 11.1 Mensaje de chat `bcall` (found)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `sessionId` | **1** | string | sesión de llamada de negocio |
| `mediaType` | **2** | enum | UNKNOWN 0, AUDIO 1, VIDEO 2 |
| `masterKey` | **3** | bytes | requerido: si falta la clave se lanza `bcall message doesn't have master key` |
| `caption` | **4** | string | opcional |

`Message.bcallMessage` = campo **72** (clase `DSA`); el handler `F2V` (`FMessageBCallProtobuf`) lo asigna al tipo de mensaje 91 con id de sesión, tipo de medio (0 unknown, 1 audio, 2 video), caption y bytes de la master key. La `master key` es una clave entregada dentro de un mensaje de chat con cifrado de extremo a extremo; qué cifra (inferred: los medios de una llamada de negocio) no se rastreó. Eventos del motor `bCallCreated(callId, key, ...)`, `bCallJoined`, `bCallEnded`, `bCallAudienceUpdated`, `bCallCreateFailed`; `CallState.BCALL_STARTING`; los hijos `<call>` entrantes llamados `bcall_*` reciben un call id vacío (3.2). Existen strings nativos `bcall_start`, `bcall_notify`.

### 11.2 Llamadas de bot y señalización HTTP / TEE

Llamadas de bot: `CallInfo.isBotCall`, nodos `<bot>` en `group_info`, `verifyIncomingBotIdentityKey`, `reconfigure_bot` (`req_id`), flujo de TOS del bot (nack 488); el offer se fusiona con un constructor de payload en caché. Contexto: [WA_META_AI.md](WA_META_AI.md). Por separado, `SignalingHttpCallback.sendMsg` permite al motor intercambiar bytes de señalización opacos mediante `TeeRequestHandler` en lugar de chatd (`handle_http_tee_start_session_response`, `handle_http_create_extension_response`); tipos de solicitud voice session y codec avatar. La elegibilidad y el formato del payload son **unknown** (inferred: sesiones de bot y avatar).

---

## 12. Registro de llamadas e historial

### 12.1 `callLogMesssage` (campo **69** de Message, clase `C49434Loq`, found)

| Campo | Número | Tipo | Valores |
|-------|--------|------|--------|
| `isVideo` | **1** | bool | |
| `callOutcome` | **2** | enum | CONNECTED 0, MISSED 1, FAILED 2, REJECTED 3, ACCEPTED_ELSEWHERE 4, ONGOING 5, SILENCED_BY_DND 6, SILENCED_UNKNOWN_CALLER 7 |
| `durationSecs` | **3** | int64 | |
| `callType` | **4** | enum | REGULAR 0, SCHEDULED_CALL 1, VOICE_CHAT 2 |
| `participants` | **5** | `CallParticipant` repetido | `jid` 1 (string), `callOutcome` 2 (mismo enum) |

Builder `C53129Nna` (found): el resultado del registro de llamadas del motor (`Voip.kCallLog*`) se asigna así.

| Resultado `kCallLog` | `callOutcome` en la red |
|-------------------|--------------------|
| Canceled 1, Missed 2 | MISSED |
| Unavailable 3 | FAILED |
| Rejected 4 | REJECTED |
| Connected 5 | CONNECTED |
| AcceptedElsewhere 6, ScreenedElsewhere 9 | ACCEPTED_ELSEWHERE |
| Invalid 0, Failed 7, ConnectedLonely 8, otros | ONGOING (rama por defecto decompilada) |
| flag DND / flag de llamante desconocido en el registro | SILENCED_BY_DND / SILENCED_UNKNOWN_CALLER (se comprueba primero) |

Que Failed 7 se asigne a ONGOING parece incorrecto pero es la rama por defecto decompilada; tratar como leído, no como comportamiento verificado. Tipo de llamada: el tipo local 1 se asigna a SCHEDULED_CALL, 2 o 3 a VOICE_CHAT, el resto a REGULAR. La falta de tipo de llamada lanza `call log message missing call_type`.

### 12.2 Base de datos local (found)

Tablas: `call_log` (`jid_row_id`, `from_me`, `call_id`, `transaction_id`, `timestamp`, `video_call`, `duration`, `call_result`, `is_dnd_mode_on`, `bytes_transferred`, `group_jid_row_id`, `is_joinable_group_call`, `call_creator_device_jid_row_id`, `call_random_id`, `call_link_row_id`, `call_type`, `offer_silence_reason`, `scheduled_id`, `telecom_uuid`, `terminated_by_device_switch`), `call_log_participant_v2` (`call_log_row_id`, `jid_row_id`, `call_result`), `joinable_call_log` (`call_id`, `joinable_video_call`, `group_jid_row_id`, `phash_identifier`, `self_other_device_connected`, `is_lgc_add`), `message_call_log`, `call_unknown_caller`, `reminder`. Eventos de alimentación: `callEnding(CallLogInfo, ..)`, `update1to1CallLog`, `updateJoinableCallLog` (`kUpdateJoinableCallLogType` Create 1, Update 2, Delete 3).

---

## 13. Estados y constantes del motor (found, `Voip.java`, `CallState`)

| Grupo | Valores |
|-------|--------|
| `CallState` | NONE, CALLING, PRE_ACCEPT_RECEIVED, RECEIVED_CALL, ACCEPT_SENT, ACCEPT_RECEIVED, ACTIVE, ACTIVE_ELSEWHERE, REJOINING, LINK, CONNECTED_LONELY, PRECALLING, ENDING, BCALL_STARTING, SCREENING |
| `kCallLog*` | Invalid 0, Canceled 1, Missed 2, Unavailable 3, Rejected 4, Connected 5, AcceptedElsewhere 6, Failed 7, ConnectedLonely 8, ScreenedElsewhere 9 |
| `kCallEndReason*` | Unknown 0, Timeout 1, Self 2, RejectDoNotDisturb 3, RejectBlocked 4, MicPermissionDenied 5, CameraPermissionDenied 6 |
| `kFatalReason*` | Unknown 0, ParticipantAllocationFailure 1, CallSetupError 2, CallTxTimeout 3, CallRxTimeout 4, VideoStreamCreateError 5, VideoPortCreateFailed 6, NoSamplingRatesForAudioRecord 7, AudioInitError 8 |
| `kOfferSilenceReason*` | None 0, Privacy 2, Lightweight 3, ScreenSharing 4, AddedAsLinkCreator 9, AddedForDeviceSwitching 10, GroupChatAdd 11 |
| `kParticipant*` | Connected 1, Incoming 2, Ringing 3, Rejected 4, Terminated 5, TimedOut 6, CreatingCall 7, Invited 11 |
| `kVideoState*` | Disabled 0, Enabled 1, Paused 2, UpgradeRequest 3, UpgradeAccept 4, UpgradeReject 5, Stopped 6, UpgradeRejectByTimeout 7, UpgradeCancel 8, UpgradeCancelByTimeout 9, UnknownPeer 10, Xr2dCodecAvatarEnabled 12, Error 20 |
| `kStatus*` | Success 0, InvalidArgument 70004, Exists 70015, Ignored 70020, CallAlreadyStarted 670001, CallNotActive 670007, CallHasNoVideo 670018, GroupCallUserExists 670021, GroupCallPeerCodecMismatch 670033, GroupCallUserExistsNotInvited 670038, NotPermitted 670040, UserNotRemovable 670041, UserNotConnected 670042 |
| `kScreenShareVersion*` | Legacy 0, 1 a 4 |
| `kNetworkHealth*` | Measuring 0, NoNetwork 1, Poor 2, Average 3, Good 4 |

Los enteros `kCallEndReason` son lo que ve la UI; los strings que se colocan en la red para terminate no están entre los strings de la librería (14.3).

---

## 14. Errores, reject, terminate

### 14.1 Códigos nack del offer (found, `VoiceServiceEventCallback.callOfferNacked`)

Un ack de offer con errores llama a `callOfferNacked(errors[])`. Un único error 304 o 400 se trata como offer duplicado y se ignora. El nack es fatal cuando la llamada está en `CALLING` / `CONNECTED_LONELY` y todos los destinatarios (o uno mismo) recibieron nack, o el código es 432; en otro caso es por destinatario y no fatal.

| Código | Ruta fatal (rama decompilada) | Ruta no fatal |
|------|-------------------------------|----------------|
| 401 | pantalla de no permitido (id de motivo 3) | |
| 403 | pantalla de no permitido, id específico de video cuando es video | |
| 404 | no permitido id 16 | texto "contact unavailable" por destinatario |
| 405 | id 4 | |
| 406 | id 2 (audio) / 11 (video) | |
| 411 | id 11, o 37 para lightweight | |
| 412 | id 10; la info de grupo se refresca ante discrepancia de membresía | |
| 426 | id 1 (audio) / 9 (video) | |
| 427 | id 12, o 36 para 1:1 lightweight | texto por destinatario; en grupos de más de 4 participantes un id alternativo |
| 428 | id 14 | texto por destinatario |
| 429 | solo evento de UI | |
| 431 | id 15 | texto "not available" |
| 432 | id 2; siempre fatal | |
| 435 | | texto por destinatario; tras un ack de offer también dispara una acción extra |
| 460 / 463 | video 10 / audio 2; 463 id 17 | |
| 488 | TOS del bot no aceptado: abre el flujo de TOS del bot | igual |
| 467, 468, 469 | | id 46 para múltiples destinatarios |
| 500, 502 | | texto "not available" |
| 538 | | id 35 |
| otro | id por defecto (video 8 / 0) | aserción `Unknown error code` |

La rama fatal decompilada perdió algunos returns, así que los ids son solo indicativos; la lista de códigos y la división fatal / no fatal son firmes. El significado de los códigos más allá de la reacción del cliente es del lado del servidor (**unknown**). Tras un nack de offer completo el motor no envía ninguna stanza de llamada excepto `terminate` (string found).

### 14.2 Motivos de reject (found, `Voip.REJECT_REASON_*`)

| String | Significado / reacción del cliente |
|--------|---------------------------|
| `` (vacío) | rechazada |
| `busy` | destinatario ocupado; tono de ocupado, la llamada termina tras un retardo |
| `unavailable` | constante definida; el uso principal se encontró en código de presencia / disponibilidad |
| `uncallable` | el par no puede ser llamado; pantalla de no permitido |
| `tos` | el par no ha aceptado el TOS; pantalla de no permitido |
| `enc` | falló el descifrado de la clave de llamada |
| `server_conf_corrupted` | configuración del servidor inutilizable |

`rejectCall(callId, reason, int)` y `rejectPendingCall` son los puntos de entrada; `callRejectReceived` consume los motivos entrantes. Los motivos de reject se asignan a resultados de llamada locales (`reject_reason_to_call_result`, `set_call_term_reason_from_received_call_reject_reason`).

### 14.3 Terminate (strings found)

- `terminate` lleva un id de transacción y un nodo `call_summary` (estados de usuario, duración); un offer de una llamada terminada lleva `terminate_hint` con `terminate_reason`, `call_summary` y un id de transacción. No está resuelto si el propio `terminate` tiene un atributo `terminate_reason`.
- El motor ignora un terminate de un dispositivo companion; el primario hace fanout de un terminate a los pares multi-dispositivo (`fanout_terminate_if_peer_is_md`).
- Un terminate de cambio de dispositivo en el estado equivocado se ignora; los resultados "handled elsewhere" se derivan del motivo (`get_handled_elsewhere_outcome_from_terminate_reason`) y los resultados conflictivos para el mismo call id se ignoran.
- Un RTCP BYE en la ruta de medios también termina una llamada (`rtcp_bye_terminate_delay`), al igual que la eliminación de extensión por parte del servidor (`extension terminated by server`).
- Java envía `terminate` con reintento (en cola a través de reconexiones) cuando el flag **8003** está activo y la llamada no es una llamada de bot ni está en estado lonely; en otro caso sin reintento (rama parcialmente poco clara en la salida decompilada).
- Los valores del string `reason` de terminate (y cualquier asignación desde `kCallEndReason`) no están en los strings de la librería y no se encontraron en otra parte del APK (**unknown**).

---

## 15. Feature flags (ids tal como se leen en los puntos de llamada; nombres sin resolver)

| ID | Tipo | Controla |
|----|------|----------|
| **9257** | long ms | timeout de entrega del offer; la stanza se descarta al agotarse (`CIX.A02`) |
| **9431** | long ms | timeout de entrega del accept; además recuerda el id de la stanza accept para que `preSendTerminate` pueda cancelarla |
| **9432** | bool | ante timeout del accept, disparar una reconexión |
| **8003** | bool | terminate con reintento (14.3) |
| **15125** | bool | informar la métrica `call_stanza_drop` |
| **30890** | bool | enviar ping de llamada saliente tras el offer |
| **30891** | long ms | timeout del ping, por defecto 3000 |
| **32651** | int | intentos de ping, mínimo 1 |
| **31086** | bool | tracker de offer saliente |
| **24935** | bool | escribir `callEntryPoint` en `Message.call` |
| **520** | bool | añadir contexto de atribución de anuncios a `Message.call` (inferred) |
| **20605** / **20606** | bool / int | añadir `<tctoken>` a los destinos de la llamada; tope de usuarios por stanza |
| **24063** | bool | selección del tipo de sesión de descifrado para una clase de ciphertext (inferred) |
| **4217** | máscara int | peek de offers entrantes: bit 1 voz, bit 2 video |
| **3094** | máscara int | bit 8 = eventos de llamada asíncronos (`kFlagEnableCallEventAsync`); emparejado con **9210** (bool) |
| **7481** | bool | estado de notificación silenciada de llamada grupal para llamadas grupales vinculadas |
| **13630** / **13804** | int / bool | muestreo para una métrica de descifrado (inferred) |

Los parámetros del motor (`p->enable_sframe_tx`, `tp->web_p2p_bitmap`, `tp->enable_e2e_bind_probe_bitmap`, `options.wa_log_time_series`, ...) provienen del `voip_settings` del servidor y se leen mediante `Voip.getVoipParam`; sus nombres son strings en la librería, sus valores son del lado del servidor.

---

## 16. Baileys (`baron-baileys-v2`, código fuente leído, nada probado)

| Tema | Baileys | Android |
|-------|---------|---------|
| Offer | `offerCall`: `call-id` aleatorio de 32 hex, `call-creator` = id propio, `<audio enc=opus rate=16000/8000>`, `<video enc=vp8 dec=vp8 ...>` (video), `<net medium=3>`, `<capability ver=1>` 6 bytes `01 04 FF 83 CF 04`, `<encopt keygen=2>`, `<destination>` con `Message{call{callKey}}` cifrado con Signal, `count=0`, `device-identity` cuando se produce un pkmsg | mismos elementos; Android construye el offer en el motor, bytes de capability desconocidos (5.2) |
| Envoltorio | `<call id to>` para offer; reject / accept / terminate usan `from` + `to` sin `id` | `<call to id>` siempre (3.1) |
| accept | `<accept call-id call-creator count=0/>`, sin hijos | el accept del motor lleva parámetros de medios y un certificado (sección 4) |
| terminate | `reason="user-terminated"`, `count=0` | strings de motivo desconocidos (14.3) |
| rekey | `<enc_rekey ...><enc v=2 type=msg/></enc_rekey>` | la forma v2 coincide con 6.4; v3 ausente |
| Entrada | descifra `<enc>` (`unpadRandomMax16`, `Message.decode`), guarda en caché el offer, emite eventos de llamada; tags de medios / relay solo con ack | Android descifra con el mismo envoltorio y alimenta el motor |
| Enlaces | `link_create media` (+ `event start_time`) hacia `@call`; `waiting_room_toggle`; `link_join token` | la gramática coincide con los nombres encontrados aquí; tipo de JID destino sin resolver |
| Estados de terminate | asigna los strings `terminate reason` `Timeout`, `RejectDoNotDisturb`, `MicPermissionDenied`, `CameraPermissionDenied`, `RemoteBusy`, `RemoteOffline` | estos strings no están en la librería; los nombres se parecen a `kCallEndReason` (vínculo **inferred**) |

Baileys no tiene asignación de relay, ni WARP / SRTP / SFrame, ni motor, así que puede señalizar y hacer sonar pero no puede transportar medios. No se probó si el par acepta o hace sonar un offer sin los parámetros completos del motor.

---

## 17. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `Wrong jid type` para una stanza de llamada | `to` no es un JID de usuario / dispositivo / dominio de llamada | dirigir al JID de dispositivo o de usuario |
| offer enviado `without enc`, el par no suena | clave de llamada no cifrada (sin sesión, job de pre-key pendiente) | construir las sesiones primero; Android mantiene el offer pendiente |
| `duplicate <enc>` / `invalid retry count` / `invalid registration` | `<enc>` mal formado; `registration` no es de 4 bytes | un único `<enc>` con `count`; `registration` solo en reintento |
| nack de offer 304 / 400 | offer duplicado | ignorar |
| nack de offer 401 / 403 / 463 | el llamante no tiene permitido llamar a este par | ninguna en el cliente |
| nack de offer 412 / 488 | la membresía del grupo difiere / TOS del bot no aceptado | refrescar la info del grupo / aceptar el TOS del bot |
| reject `enc` | el destinatario no pudo descifrar la clave de llamada | reenviar el offer tras reparar la sesión (`count` > 0) |
| `Unsupported keygen ver`, `can not receive both te and te2`, `num_tokens < 1` | `encopt`, endpoints de relay o tokens no válidos | enviar keygen 2 o 3, una familia de endpoints, al menos un token |
| `bcall message doesn't have master key` | falta `masterKey` | incluirla |
| `Call stanza delivery timed out` | sin ack de chatd dentro del flag 9257 / 9431 | stanza descartada; accept puede reconectar (flag 9432) |

---

## 18. Distinciones clave

| No confundir | Con |
|----------------|------|
| `Message.call` (campo 10, clave de llamada E2E dentro de un mensaje Signal) | `callLogMesssage` (69, registro de resultado), `bcallMessage` (72, clave de sesión de negocio) |
| `<enc>` en una stanza de llamada (ciphertext Signal pairwise) | mensajes sender-key `skmsg` y cifrado de medios |
| Claves E2E SRTP / SFrame (derivadas de la clave de llamada) | claves salto a salto (derivadas del `hbh_key` del relay) |
| `<token>` / `<auth_token>` del relay (credenciales de asignación) | `<tctoken>` (token de privacidad dentro de `<to>`) |
| enteros `kCallEndReason` (UI), `kCallLog*` (resultado del motor) | strings de motivo de terminate (red, unknown), enum `callOutcome` (red) |
| `CallLogMessage.CallType` REGULAR / SCHEDULED_CALL / VOICE_CHAT | `ScheduledCallCreationMessage.CallType` UNKNOWN / VOICE / VIDEO |
| `enc_rekey` v2 (hijo `<enc>` Signal) | `enc_rekey` v3 (lista protobuf `RekeyKeyEntry`) |
| Ruta de relay de WhatsApp (WARP, SRTP salto a salto) | ruta web-P2P (ICE + DTLS-SRTP) |
| Llamada de evento (enlace con hora de inicio) | mensajes de chat de llamada programada (61 / 65) |
| Señalización sobre chatd | señalización HTTP / TEE para sesiones de bot y avatar |

---

## 19. Flujo completo (llamada 1:1)

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

Diferencias en llamadas grupales: el offer lleva `group_info` y ninguna clave por dispositivo; quienes se unen tarde usan `lobby` / `link_join`; los rekeys viajan como `enc_rekey` (fanout v2 o v3) con ids de transacción; los medios pasan por un SFU con SFrame.

---

## 20. Unknowns

| Elemento | Estado |
|------|--------|
| Constructores / parsers nativos de stanzas, strings `info` de HKDF, layouts de claves | librería voip no decompilada; solo strings |
| Bytes de capability, códigos de `net medium`, valores por defecto de parámetros de códec | no recuperados |
| Valores de `transport-message-type` distintos de 13 | no recuperados |
| Strings `reason` de terminate, asignación de reject a motivo de fin | no encontrados |
| Significado de `e` en el envoltorio, acción secundaria del error 435 en el ack del offer | sin resolver |
| Tabla numérica de 85 tipos de id de mensaje | no presente en los strings de este build |
| Clase de dispositivo de extensión, disparador del rekey v3, disparador del rekey grupal | sin resolver |
| Tipo de JID de llamada por enlace, vínculo entre llamada programada y token | sin resolver |
| Payload y elegibilidad de la señalización TEE / HTTP | sin resolver |
| Comportamiento del servidor (enriquecimiento, semántica de nack, elección de relay) | del lado del servidor |
| Tráfico | nada capturado |
