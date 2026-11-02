<!-- src-sha1: 12b80567ad9e73698ea38209998c12bdf3666099 -->
# WhatsApp Call Links — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-02
**Alcance:** Enlaces de llamada para invitados (`call.whatsapp.com/{voice|video}/{token}`): el handshake `link_query` / `link_join`, la sala de espera, el modelo de participante invitado / asignación de JID, y el material de relay y claves entregado a un invitado al ser admitido. Este informe cubre solo la capa de enlace/sala de espera/invitado; la gramática genérica del envoltorio `<call>`, offer/accept/terminate, la clave de llamada, la lógica de selección de relay y el path de medios se cubren en [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) y se referencian aquí, sin repetirse.

---

## 1. Qué es

Un call link es un token que permite a un participante unirse a una llamada sin ser invitado por JID. El servidor resuelve el token a una llamada en curso o iniciable y, si la llamada tiene sala de espera, retiene al que se une ahí hasta que se le deje entrar. Todo en las secciones 3 en adelante, debajo de las tablas con forma de stanza, es **tested**: leído de una captura de wire real de un cliente uniéndose a su propia llamada de prueba mediante call link, descifrado y decodificado por el propio cliente que se une (no interceptación de tráfico de terceros). Los estáticos de la APK (**found**) corroboran las partes que la captura no muestra, principalmente la creación del enlace. El razonamiento del lado del servidor es **unknown** salvo que se indique lo contrario.

| Entidad | Forma | Establecido por | Tier |
|--------|------|--------|------|
| URL del enlace | `https://call.whatsapp.com/{voice\|video}/{token}` | el cliente la plantilla alrededor de un token | found |
| Token | 22 caracteres, alfanumérico mixto en mayúsculas/minúsculas (`Voip.kCallLinkTokenLength`=22) | el call-site de creación no tiene parámetro de token en Java; la asignación por el servidor es la hipótesis de trabajo | found (longitud), inferred (origen) |
| Call-id | 32 caracteres hex (16 bytes), p. ej. `0076804DB4CA9D41EFCB547F08AE87BD` | servidor, devuelto en el ack de `link_join` | tested |
| `is_guest_eligible` | bool en el enlace | el host lo elige al crear (`CallLinkInfo.isGuestEligible`) | found (campo), tested (valor en el wire) |
| `waiting_room` `enabled` | bool en el enlace | el host lo elige al crear (`Voip.createCallLink(..., waitingRoomEnabled)`) | found (campo), tested (valor en el wire) |
| Participante invitado | una entrada del roster con `account_kind="guest"` y un JID asignado por el servidor | servidor, al admitir | tested |
| JID de dominio de llamada | dominio `call` sin usuario antes de que exista un call-id, `<call-id>@call` después | servidor | tested |

---

## 2. Base de evidencia

Se capturaron de extremo a extremo dos uniones de invitado independientes, ambas desde una conexión chatd ya autenticada (la sesión que se une tiene su propia identidad en el wire) que deliberadamente llama al path del enlace con un nombre de visualización elegido por sí misma y sin identidad revelada, en lugar de unirse como el JID propio de la cuenta:

| | Enlace de video | Enlace solo de audio |
|---|---|---|
| Token | `7vEdtKy61dqCtbWAQ59zuO` | `ENcQnTAwKj7lQOdOHVJPmQ` |
| Call-id | `0076804DB4CA9D41EFCB547F08AE87BD` | `00BC509C0194CE83E26FA85A0319FD9C` |
| Creador de la llamada (host) | `48615137533978` dispositivo 24 | `21428363591910` dispositivo 0 |
| push_name del invitado enviado | `Baron als Gast ohne wa` | `Baron aus web testt` |

Ambas sesiones direccionan al host y al propio creador del call-id con una forma de JID `type=1, domainType=1` y sin atributo `server` explícito; en otras partes de las mismas capturas esa misma forma se asocia, para la misma cuenta, con un `server="lid"` explícito (p. ej., los acks de recibo de clase mensaje). Leído en conjunto: la señalización de llamadas aquí corre sobre identidades LID, consistente con la nota del §3.2 de [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) de que las stanzas de llamada toleran un `to` LID frente a un `call-creator` de dominio diferente.

Lo que esta captura no muestra: una sesión de navegador genuinamente sin cuenta (sin login previo a WhatsApp en absoluto) accediendo al mismo enlace. Las formas de stanza de abajo son el protocolo de la capa de señalización de llamadas para una unión de invitado; si el cliente de un visitante web anónimo produce stanzas idénticas byte a byte, o pasa primero por un paso de aprovisionamiento adicional, es **unknown**.

---

## 3. Creación del enlace (found, APK; no capturada en el wire)

| Paso | Clase / método | Detalle |
|------|-----------------|--------|
| Puntos de entrada | `CreateCallLinkBottomSheet` (enlace independiente), `EventCallLinkManager.createCallLink` (enlace vinculado a un evento) | ambos convergen en un único manager |
| Manager | `CallLinkManager` (tag de log), despacha `actionCreateCallLink` / `actionCreateCallLinkForEvent` | |
| Llamada nativa | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` | solo 3 parámetros — sin token, sin argumento explícito `media`/`guest` en la firma Java |
| Ensamblado de la stanza | nativo (`wa_call_link_create_v2`) | la IQ `link_create` en sí se construye bajo el límite JNI, como cualquier otra stanza de llamada (§2 de WA_CALL_SIGNALING.md) |
| Resultado | `CallLinkInfo` (creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self), poblado desde un callback nativo | el token se lee de vuelta, no se suministra |
| URL | `AbstractC227619sp.A01(token, isVideo)`: `Uri.Builder().scheme("https").authority("call.whatsapp.com").appendPath(isVideo?"video":"voice").appendPath(token)` | el cliente plantilla la URL de compartir alrededor del token que recibió |

No hay generador `SecureRandom`/base62 cerca de `kCallLinkTokenLength` o `createCallLink` en Java, y la librería nativa no se pudo descompilar. **Unknown**: si el token de 22 caracteres se genera en el cliente y se envía en `link_create`, o lo asigna el servidor y se devuelve en el ack — el call-site visible para el cliente no lleva argumento de token, lo que favorece la asignación por el servidor, pero esto es **inferred**, no probado. `connected-limit` (visto en `group_info`, §6) solo se devuelve desde el servidor; no se encontró setter en el cliente. No se encontró límite de tasa en el lado del cliente para la creación de enlaces.

---

## 4. Query y join (tested)

### 4.1 `link_query`

Enviado desnudo, antes de conocer ningún call-id, al JID de dominio de llamada sin parte de usuario (`to: {user: null, server: "call"}`):

```
<call to="@call" id="...">
  <link_query token="7vEdtKy61dqCtbWAQ59zuO" media="video"/>
</call>
```

Ack:

```
<ack from="@call" class="call" type="link_query" id="...">
  <link_query link_creator="<host jid>" media="video" token="...">
    <guest is_guest_eligible="1"/>
    <waiting_room enabled="1"/>
  </link_query>
</ack>
```

`link_creator` identifica al host; `is_guest_eligible` y `waiting_room enabled` son los ajustes de creación del enlace (§3) devueltos en eco. Todavía no hay call-id — este ack solo previsualiza el enlace.

### 4.2 `link_join`

Lleva el mismo `token`/`media`, más un `push_name` elegido y los hijos habituales con forma de media de oferta:

```
<call to="@call" id="...">
  <link_join token="7vEdtKy61dqCtbWAQ59zuO" media="video" push_name="Baron als Gast ohne wa">
    <audio enc="opus" rate="16000"/>
    <video dec="H264" device_orientation="0"/>
    <net medium="2"/>
    <capability ver="1">...7 bytes...</capability>
  </link_join>
</call>
```

El `link_join` del enlace solo de audio (segunda captura) omite por completo el hijo `<video>` — confirmado por comparación directa, no inferido:

```
<link_join token="ENcQnTAwKj7lQOdOHVJPmQ" media="audio" push_name="Baron aus web testt">
  <audio enc="opus" rate="16000"/>
  <net medium="2"/>
  <capability ver="1">...</capability>
</link_join>
```

`push_name` es texto libre que el invitado elige para esta unión; no es el nombre de visualización propio de la cuenta de WhatsApp (la cuenta que se une en ambas capturas es una sesión real con login, pero el nombre elegido difiere de su nombre de perfil normal — la identidad de invitado es solo de presentación en esta etapa). Los 7 bytes de `<capability>` observados (`01 05 F5 09 E0 BB 53` invitado en video, `01 05 F7 09 E0 3B 53` host) son valores específicos de la sesión, no una máscara general; WA_CALL_SIGNALING.md §5.2 ya marca los valores de byte de capability en Android como desconocidos en general y esto no lo resuelve.

El ack a `link_join` ya lleva un call-id — el servidor ha resuelto (o iniciado) la llamada:

```
<ack from="@call" class="call" type="link_join" id="...">
  <waiting_room link-token="7vEdtKy61dqCtbWAQ59zuO" media="video"
                call-id="0076804DB4CA9D41EFCB547F08AE87BD"
                call-creator="<host jid>" enabled="1"/>
  <guest is_guest_eligible="1"/>
</ack>
```

### 4.3 Direccionamiento del JID de dominio de llamada (tested)

Esto resuelve parte de WA_CALL_SIGNALING.md §10.1, que dejaba sin identificar el tipo del JID de dominio de llamada:

1. `link_query` / `link_join` direccionan al dominio desnudo `call` — sin parte de usuario (`callDomainJID`).
2. En el momento en que el ack de `link_join` devuelve un `call-id`, el cliente empieza a direccionar las siguientes stanzas dentro de la llamada (heartbeat de sala de espera, y más adelante mute/transport/relaylatency/video) a `<call-id>@call` — un JID calificado con usuario bajo el mismo dominio (`callJID`).
3. El propio push de admisión del servidor (§5) llega más tarde `from="<call-id>@call"`, confirmando el mismo direccionamiento en el lado entrante.

Así que el call-id, una vez conocido, *es* la parte de usuario del JID para todo lo que sigue — no una clave de correlación separada que se lleve junto al direccionamiento.

---

## 5. Sala de espera (tested)

Mientras espera, el invitado unido pero no admitido envía un heartbeat periódico al JID del call-id:

```
<call to="<call-id>@call" id="...">
  <heartbeat call-id="0076804DB4CA9D41EFCB547F08AE87BD" call-creator="<host jid>" type="waiting_room"/>
</call>
```
confirmado de inmediato (`<ack ... type="heartbeat"/>`, sin contenido).

**Advertencia sobre la admisión**: esta captura es de un solo extremo — muestra únicamente la propia conexión del invitado. La acción del lado del host que admite a un invitado en espera (`waitingRoomAdmit`, enviando una stanza `waiting_room_toggle`/`_admit`, según WA_CALL_SIGNALING.md §10.3) corre en la conexión del *host* y no se observó aquí; este informe solo muestra su resultado. En ambas capturas, la admisión (§6) siguió al único heartbeat visible en bastante menos de un segundo — lo bastante rápido como para que sea **unknown** si esto refleja a un host alerta pulsando Admitir de inmediato, o alguna condición de auto-admisión (p. ej., el host ya activo en la llamada); ninguna evidencia aquí distingue entre ambas.

---

## 6. Asignación del JID del invitado (tested)

La admisión llega como un push ordinario `group_update`/`group_info` desde `<call-id>@call`, con dos entradas `<user>` — host e invitado lado a lado:

| Campo | Entrada del host | Entrada del invitado |
|-------|-----------|--------------|
| `jid` | `48615137533978` (dispositivo 24 bajo `<device>`) | `29554559176938` (dispositivo 0) |
| `type` | `admin` | *(ausente — sin rol elevado)* |
| `account_kind` | *(ausente)* | `guest` |
| `push_name` | *(ausente en esta entrada)* | `Baron als Gast ohne wa` — el nombre enviado en `link_join` §4.2, copiado literal al roster |
| `state` | `connected` | `connected` |
| `platform` del dispositivo | `web` | `web` |
| `pid` del dispositivo | `0` | `1` |

El JID del invitado (`29554559176938`) está en la misma clase de forma de dirección (`type=1`, `domainType=1`, es decir, estilo LID, §2) que el del host, asignado de nuevo por el servidor para esta llamada — no es la identidad de cuenta propia de la sesión que se une. El `pid` de dispositivo (`1` para el invitado) coincide con `self_pid="1"` del bloque de relay en la misma stanza (§7) — el id de participante por dispositivo del roster y el propio id de participante del relay son el mismo número.

**Unknown**: si este JID de invitado se reutiliza entre uniones repetidas del mismo enlace por el mismo navegador/sesión, cuánto tiempo se retiene, o si es visible para el host más allá de `push_name` y `account_kind`.

---

## 7. Entrega de relay y claves al admitir (tested)

La misma stanza de admisión lleva un bloque `<relay>`, hermano de `<group_info>`, que da al invitado todo lo necesario para llegar a los medios sin más idas y vueltas. Los campos coinciden con la gramática de WA_CALL_SIGNALING.md §8.2; esta sección añade detalle concreto a nivel de wire que aquel informe dejaba abierto.

| Hijo | Cantidad vista | Notas |
|-------|-----------|-------|
| `<token id=N>` | 3 (ids 0, 1, 2) | binario sin procesar, 194 bytes cada uno |
| `<auth_token id=0>` | 1 | binario sin procesar, 70 bytes |
| `<key>` | 1 | 24 bytes en el wire — pero esos 24 bytes son a su vez texto ASCII de una cadena base64, que al decodificarse de nuevo da una clave sin procesar de 16 bytes |
| `<hbh_key>` | 1 | 40 bytes en el wire — mismo patrón: texto ASCII base64, que decodifica a 30 bytes sin procesar |
| `<te2 relay_id auth_token_id token_id domain_name relay_name c2r_rtt>` | 6 (2 relays: `edgeray-ham3-1.wt.whatsapp.com`/`ham3c01`, `edgeray-ber1-1.wt.whatsapp.com`/`ber1c01`) | sin `<te>` presente — confirma la regla "nunca ambos a la vez"; esta llamada usó `te2` |
| atributos del relay | `attribute_padding`, `transaction-id`, `self_pid`, `uuid`, `participant_uuid` | `self_pid="1"` se enlaza con el `pid` del propio dispositivo del invitado en `group_info` (§6) |
| `<participant pid jid>` | no presente | el hijo de mapeo de id de participante a JID del §8.2 no se vio en esta captura de 2 partes; se desconoce si aparece solo en llamadas de grupo más grandes |

Solo `<key>` y `<hbh_key>` llevan la forma de doble codificación (nodo binario que contiene texto ASCII base64); `<token>` y `<auth_token>` son binario sin procesar, de una sola decodificación. Qué aporta esta doble capa frente a enviar bytes sin procesar directamente es **unknown** (un resto de un transporte orientado a texto internamente, inferred).

Un hijo `<voip_settings uncompressed="1">`, también hermano de `<group_info>`/`<relay>`, lleva un blob JSON de parámetros de motor (no comprimido en esta captura, consistente con la nota de WA_CALL_SIGNALING.md §5.2 de que los payloads comprimidos se rechazan al menos en una ruta). Dentro de él, bajo el objeto `fs` (feature-switch): `"guest_calling_logging_enabled": "true"` — la única clave específica de invitado encontrada en un documento de ajustes por lo demás genérico de ~32 KB (`aec`, `bwe`, `decode`, `encode`, `sfu`, `rc`, ... — todo ajuste genérico del motor de medios, no relacionado con la unión de invitados). Los eventos de telemetría enviados por el cliente que se une alrededor de esta llamada usan independientemente la cadena de categoría `guest_calling` (vista en los propios blobs `w:stats`/WAM del cliente), coincidiendo con el nombre de la clave de ajustes.

Dos hermanos inocuos, `<uploadfieldstat/>` y `<userrate interval="0"/>`, viajan en la misma stanza; sin contenido específico de invitado.

El cliente envía de inmediato un `<ack class="call" type="group_update">` plano para este push (sin contenido) — manejo ordinario según WA_CALL_SIGNALING.md §3.3 (group_update no está en el conjunto de tags sin ack inmediato).

---

## 8. Tráfico posterior a la admisión (tested, breve)

Una vez admitido, el tráfico es indistinguible de una llamada normal en el mismo JID de call-id: `mute_v2` (el host silencia al invitado inmediatamente tras la admisión en esta captura), `transport` (`transport-message-type="4"`, un hijo `<net medium="2" protocol="0"/>`), `relaylatency` (en ambas direcciones, cada una con un `<te latency relay_name>` que referencia los nombres de relay del §7), y cambios de estado de `video` (`state="6"`, es decir, `Stopped` según la tabla `kVideoState*` de WA_CALL_SIGNALING.md §13, repetido tres veces en rápida sucesión durante el setup). Nada de esto es específico del enlace; ver WA_CALL_SIGNALING.md §§8, 13 para la semántica general.

---

## 9. Enlace de video vs. solo audio — diferencias observadas (tested)

| Aspecto | Enlace de video | Enlace solo de audio |
|--------|-----------|------------------|
| atributo `media` en `link_query`/`link_join` | `video` | `audio` |
| hijos de `link_join` | `<audio>`, `<video>`, `<net>`, `<capability>` | `<audio>`, `<net>`, `<capability>` — `<video>` omitido |
| `media` del ack `waiting_room` | `video` | `audio` |
| Mecánica de sala de espera / elegibilidad de invitado | idéntica | idéntica |

No se observó ninguna otra diferencia de protocolo entre ambos; el tipo de media se lleva de extremo a extremo como un atributo simple, no como una familia de stanza distinta.

---

## 10. Diferencias respecto a una llamada 1:1 o de grupo normal

| Aspecto | Llamada 1:1 / grupo normal (WA_CALL_SIGNALING.md) | Unión por enlace de invitado (este informe) |
|--------|------------------------------------------------|-------------------------------|
| Stanza de entrada | `offer` a un peer/JID de grupo conocido | `link_query` y luego `link_join` al dominio desnudo `call` |
| Clave de llamada | `Message.call.callKey` cifrada con Signal por dispositivo en la oferta | no observada en la admisión de esta captura; el invitado recibe material de relay/clave (§7) directamente, no una clave de llamada envuelta en Signal — consistente con que un invitado no tiene sesión Signal por pares con el host |
| Identidad de llamante/llamado | ambos lados son JIDs conocidos antes de que empiece la llamada | la identidad real del lado que se une no se expone en el roster; el servidor asigna un JID nuevo y lo etiqueta `account_kind="guest"` |
| Admisión | ninguna — offer/accept es la única puerta | sala de espera opcional: `waiting_room enabled`, retenido hasta una admisión (no observada, del lado del host) |
| Entrega del roster | `group_info` dentro de la oferta o una actualización posterior | push `group_update`/`group_info` desde `<call-id>@call`, empaquetado junto con `<relay>` y `<voip_settings>` en la misma stanza |
| Direccionamiento de JID | JID de peer/grupo en todo momento | dominio desnudo `call` hasta que existe un call-id, luego `<call-id>@call` |

La clave de llamada por dispositivo ausente para el invitado (fila 2) es la diferencia más consecuente y es **tested** solo como una ausencia en esta captura — no confirmada como regla de protocolo; también es consistente con la nota de WA_CALL_SIGNALING.md §9.2 de que las ofertas de grupo no llevan clave por dispositivo y las claves se reparten de nuevo fuera de banda (`enc_rekey`). Si un invitado alguna vez recibe un `enc_rekey` no se observó en ninguna de las dos ventanas de captura usadas aquí.

---

## 11. Casos de error / trampas

| Síntoma | Causa | Arreglo / nota |
|---------|-------|-----------|
| El ack de `link_query` no tiene `call-id` | el enlace aún no se ha resuelto a una llamada en curso/iniciable | normal para una previsualización desnuda; el call-id llega solo en el ack de `link_join` |
| Invitado atascado tras el ack de `link_join`, solo se intercambian heartbeats | la sala de espera está habilitada y el host todavía no ha admitido | se requiere acción del lado del host; no visible desde la conexión del invitado |
| `link_join` lleva un hijo `<video>` para un enlace solo de audio | bug del cliente — las dos capturas muestran que este hijo debe estar completamente ausente para `media="audio"` | omitir `<video>` en uniones solo de audio |
| El JID de la propia cuenta del invitado aparece en el roster de la llamada en lugar de un JID de invitado nuevo | path de unión incorrecto (`offer`/unión de grupo ordinaria en lugar de `link_join`) | usar `link_query`→`link_join` para obtener el manejo de `account_kind="guest"` |
| El invitado no recibe clave de llamada pero sí material de relay/clave | esperado para este path (§10) — el invitado no recibe una clave envuelta en Signal como un callee normal | no tratarlo como un fallo de descifrado |

---

## 12. Distinciones clave

| No confundir | Con |
|-----------------|------|
| **Token** de call-link (22 caracteres, de cara a la URL) | **Call-id** (32 caracteres hex, de cara al protocolo, aparece solo tras `link_join`) |
| JID de dominio `call` desnudo (previo al call-id) | `<call-id>@call` (posterior al call-id) — ambos son "el JID de dominio de llamada" en etapas distintas, no dos direcciones no relacionadas |
| `is_guest_eligible` (ajuste del enlace: si *cualquiera* puede unirse a este enlace como invitado) | `waiting_room enabled` (ajuste del enlace: si los invitados se retienen para admisión) — flags independientes, ambos devueltos en eco en los mismos acks |
| `push_name` del invitado en `link_join` (texto libre, elegido por cada unión) | el nombre de perfil propio de WhatsApp de la cuenta que se une (no lo que termina en el roster para una unión de invitado) |
| Bytes en el wire de `<key>` / `<hbh_key>` (nodo binario que contiene texto ASCII base64, requiere doble decodificación) | Bytes en el wire de `<token>` / `<auth_token>` (binario sin procesar, decodificación única) |
| Asignación de JID de invitado (lado del servidor, al admitir, por llamada) | JIDs LID/PN normales (a nivel de cuenta, persistentes) |

---

## 13. Flujo completo (unión de invitado, desde la captura)

```
[Guest client]  already has a chatd session (own identity, not used for the call)
     │  <call to="@call"><link_query token media/></call>
     ▼
[WA Server]  resolves the token
     │  ack: link_creator, media, token, <guest is_guest_eligible/>, <waiting_room enabled/>
     ▼
[Guest client]  <call to="@call"><link_join token media push_name><audio/>[<video/>]<net/><capability/></link_join></call>
     ▼
[WA Server]  starts/resolves the call
     │  ack: <waiting_room link-token media call-id call-creator enabled/>, <guest is_guest_eligible/>
     ▼
[Guest client]  learns call-id → addresses it as <call-id>@call from now on
     │  <call to="<call-id>@call"><heartbeat call-id call-creator type="waiting_room"/></call>  (repeats)
     ▼
[Host, out of band — not in this capture]  taps Admit (waiting_room_toggle/_admit)
     ▼
[WA Server]  <call from="<call-id>@call"><group_update><group_info ...>
                 <user host .../><user account_kind="guest" push_name jid=<allocated> .../>
              </group_info>
              <relay token×N auth_token key hbh_key te2×N/>
              <voip_settings uncompressed fs.guest_calling_logging_enabled=true/>
              </group_update></call>
     │  ack: <ack class="call" type="group_update"/>
     ▼
[Both]  ordinary call traffic on <call-id>@call: mute_v2, transport, relaylatency, video state
              (see WA_CALL_SIGNALING.md §§8, 13 for generic semantics)
```

---

## 14. Incógnitas

| Ítem | Estado |
|------|--------|
| Lugar de generación del token (acuñado en el cliente vs. asignado por el servidor) | el call-site de `createCallLink` no lleva argumento de token (found); el origen real es nativo (unknown) |
| Si una sesión de navegador genuinamente sin cuenta produce la misma secuencia de stanzas | no capturado — ambas capturas corrieron sobre una conexión ya autenticada que eligió unirse como invitado |
| Forma en el wire de la acción de admisión del lado del host (`waiting_room_toggle`/`_admit`) | no está en esta captura (de un solo extremo); descrita solo a partir de los estáticos de WA_CALL_SIGNALING.md §10.3 |
| Por qué la admisión siguió tan rápido al único heartbeat observado | host alerta vs. una condición de auto-admisión — no distinguible a partir de esta evidencia |
| Tiempo de vida / reutilización del JID de invitado entre uniones repetidas | no observado |
| Si un invitado alguna vez recibe `enc_rekey` o alguna clave de llamada envuelta en Signal | no observado en ninguna de las dos ventanas de captura |
| Mapeo `<participant pid jid>` bajo `<relay>` | no presente en esta captura de 2 partes; se desconoce si las llamadas de grupo con invitados lo usan |
| Propósito de la doble codificación base64 en `<key>`/`<hbh_key>` frente a `<token>`/`<auth_token>` sin procesar | unknown |
| `connected-limit` como tope configurable por el cliente vs. siempre asignado por el servidor | no se encontró setter en el cliente (found: devuelto solo por el servidor) |
| Límites de tasa / controles de abuso en la creación de enlaces o uniones de invitados | nada encontrado del lado del cliente; comportamiento del servidor desconocido |
