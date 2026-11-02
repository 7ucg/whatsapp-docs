<!-- src-sha1: 5cbe81a4c1568d0ea9b8c065d2d8dc0fbf7e1afc -->
# WhatsApp Call Links — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-02
**Alcance:** Enlaces de llamada para invitados (`call.whatsapp.com/{voice|video}/{token}`): el handshake `link_query` / `link_join`, la sala de espera, el modelo de participante invitado / asignación de JID, y el material de relay y claves entregado a un invitado al ser admitido. Este informe cubre solo la capa de enlace/sala de espera/invitado; la gramática genérica del envoltorio `<call>`, offer/accept/terminate, la clave de llamada, la lógica de selección de relay y el path de medios se cubren en [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) y se referencian aquí, sin repetirse.

---

## 1. Qué es

Un call link es un token que permite a un participante unirse a una llamada sin ser invitado por JID. El servidor resuelve el token a una llamada en curso o iniciable y, si la llamada tiene sala de espera, mantiene ahí al que se une hasta que se le deja pasar. Todo lo que aparece a partir de la sección 3 debajo de las tablas con forma de stanza es **tested**: leído de una captura real de wire de un cliente uniéndose a su propio call link de prueba, descifrado y decodificado por el propio cliente que se une (no interceptación de tráfico de terceros). Los datos estáticos del APK (**found**) corroboran las partes que la captura no muestra, principalmente la creación del enlace. El razonamiento del lado del servidor es **unknown** salvo que se indique lo contrario.

| Entidad | Forma | Establecido por | Tier |
|--------|------|--------|------|
| URL del enlace | `https://call.whatsapp.com/{voice\|video}/{token}` | el cliente la genera con una plantilla alrededor de un token | found |
| Token | 22 caracteres, alfanumérico de mayúsculas y minúsculas mixtas (`Voip.kCallLinkTokenLength`=22) | el call-site de creación no tiene parámetro de token en Java; que lo asigne el servidor es la hipótesis de trabajo | found (longitud), inferred (origen) |
| Call-id | 32 caracteres hex (16 bytes), p. ej. `0076804DB4CA9D41EFCB547F08AE87BD` | servidor, devuelto en el ack de `link_join` | tested |
| `is_guest_eligible` | bool del enlace | el host lo elige al crearlo (`CallLinkInfo.isGuestEligible`) | found (campo), tested (valor en wire) |
| `waiting_room` `enabled` | bool del enlace | el host lo elige al crearlo (`Voip.createCallLink(..., waitingRoomEnabled)`) | found (campo), tested (valor en wire) |
| Participante invitado | una entrada de roster con `account_kind="guest"` y un JID asignado por el servidor | servidor, al admitir | tested |
| JID del dominio de llamada | dominio `call` desnudo antes de que exista un call-id, `<call-id>@call` después | servidor | tested |

---

## 2. Base de evidencia

Se capturaron de extremo a extremo dos joins de invitado independientes, ambos desde una conexión chatd ya autenticada (la sesión que se une tiene su propia identidad en el wire) que deliberadamente usa el path de enlace con un nombre para mostrar elegido por el usuario y sin identidad revelada, en lugar de unirse como el JID propio de la cuenta:

| | Enlace de video | Enlace solo de audio |
|---|---|---|
| Token | `7vEdtKy61dqCtbWAQ59zuO` | `ENcQnTAwKj7lQOdOHVJPmQ` |
| Call-id | `0076804DB4CA9D41EFCB547F08AE87BD` | `00BC509C0194CE83E26FA85A0319FD9C` |
| Creador de la llamada (host) | `48615137533978` dispositivo 24 | `21428363591910` dispositivo 0 |
| push_name del invitado enviado | `Baron als Gast ohne wa` | `Baron aus web testt` |

Ambas sesiones se dirigen al host y al propio creador del call-id con una forma de JID `type=1, domainType=1` y sin atributo `server` explícito; en otras partes de las mismas capturas, esa misma forma aparece, para la misma cuenta, junto con un `server="lid"` explícito (p. ej. en los acks de recibo de clase mensaje). Leído en conjunto: la señalización de llamada aquí corre sobre identidades LID, consistente con la nota del §3.2 de [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md) de que las stanzas de llamada toleran un `to` LID frente a un `call-creator` de dominio distinto.

Una tercera captura, de una sesión de navegador genuinamente sin cuenta (sin ningún login previo de WhatsApp, impulsada por un humano, nada automatizado), llena parte de ese vacío: muestra el paso de registro que produce la identidad que las secciones anteriores asumen que ya existe, y confirma que ese paso corre sobre el transporte web ordinario, no uno separado. Ver §14–§15. El contenido de stanza de invitado descifrado de esa sesión (si es idéntico byte a byte a las formas del §4) no se capturó — el canal Noise lo oculta a una vista de red pasiva, igual que para cualquier otro cliente.

---

## 3. Creación del enlace (found, APK; no capturado en el wire)

| Paso | Clase / método | Detalle |
|------|-----------------|--------|
| Puntos de entrada | `CreateCallLinkBottomSheet` (enlace independiente), `EventCallLinkManager.createCallLink` (enlace vinculado a un evento) | ambos convergen en un único manager |
| Manager | `CallLinkManager` (etiqueta de log), despacha `actionCreateCallLink` / `actionCreateCallLinkForEvent` | |
| Llamada nativa | `Voip.createCallLink(isVideo, eventStartTimeSec, waitingRoomEnabled)` | solo 3 parámetros — sin token, sin argumento explícito `media`/`guest` en la firma Java |
| Ensamblado de la stanza | nativo (`wa_call_link_create_v2`) | la IQ `link_create` en sí se construye por debajo del límite JNI, como cualquier otra stanza de llamada (§2 de WA_CALL_SIGNALING.md) |
| Resultado | `CallLinkInfo` (creatorJid, token, videoEnabled, eventStartTsSec, isGuestEligible, linkState, waitingRoomState, self), poblado desde un callback nativo | el token se lee de vuelta, no se suministra |
| URL | `AbstractC227619sp.A01(token, isVideo)`: `Uri.Builder().scheme("https").authority("call.whatsapp.com").appendPath(isVideo?"video":"voice").appendPath(token)` | el cliente genera la URL para compartir con una plantilla alrededor del token que recibió |

No hay generador `SecureRandom`/base62 cerca de `kCallLinkTokenLength` ni de `createCallLink` en Java, y la librería nativa no se pudo decompilar. **Unknown**: si el token de 22 caracteres se acuña del lado del cliente y se envía en `link_create`, o lo asigna el servidor y se devuelve en el ack — el call-site visible del cliente no lleva argumento de token, lo cual favorece la asignación por el servidor, pero esto es **inferred**, no probado. `connected-limit` (visto en `group_info`, §6) solo es devuelto por el servidor; no se encontró setter del lado del cliente. No se encontró límite de tasa del lado del cliente para la creación de enlaces.

---

## 4. Query y join (tested)

### 4.1 `link_query`

Se envía en vacío, antes de conocer ningún call-id, al JID de dominio de llamada sin parte de usuario (`to: {user: null, server: "call"}`):

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

`link_creator` identifica al host; `is_guest_eligible` y `waiting_room enabled` son los ajustes de creación del enlace (§3) devueltos como eco. Aún no hay call-id — este ack solo previsualiza el enlace.

### 4.2 `link_join`

Lleva el mismo `token`/`media`, más un `push_name` elegido y los hijos habituales con forma de oferta de medios:

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

`push_name` es texto libre que el invitado elige para este join; no es el nombre de visualización propio de WhatsApp de la cuenta (la cuenta que se une en ambas capturas es una sesión real con sesión iniciada, pero el nombre elegido difiere de su nombre de perfil normal — la identidad de invitado es solo de presentación en esta etapa). Los 7 bytes de `<capability>` observados (`01 05 F5 09 E0 BB 53` invitado de video, `01 05 F7 09 E0 3B 53` host) son valores específicos de la sesión, no una máscara general; WA_CALL_SIGNALING.md §5.2 ya marca los valores de byte de capacidad de Android como unknown en general y esto no resuelve eso.

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

Esto resuelve parte del §10.1 de WA_CALL_SIGNALING.md, que dejaba sin identificar el tipo del JID de dominio de llamada:

1. `link_query` / `link_join` se dirigen al dominio `call` desnudo — sin parte de usuario (`callDomainJID`).
2. En el momento en que el ack de `link_join` devuelve un `call-id`, el cliente empieza a dirigir las siguientes stanzas dentro de la llamada (heartbeat de sala de espera, y más tarde mute/transport/relaylatency/video) a `<call-id>@call` — un JID calificado por usuario bajo el mismo dominio (`callJID`).
3. El propio push de admisión del servidor (§5) llega más tarde `from="<call-id>@call"`, confirmando el mismo direccionamiento en el lado entrante.

Así que el call-id, una vez conocido, *es* la parte de usuario del JID para todo lo que sigue — no una clave de correlación separada que se transporta junto al direccionamiento.

---

## 5. Sala de espera (tested)

Mientras espera, el invitado unido-pero-no-admitido envía un heartbeat periódico al JID del call-id:

```
<call to="<call-id>@call" id="...">
  <heartbeat call-id="0076804DB4CA9D41EFCB547F08AE87BD" call-creator="<host jid>" type="waiting_room"/>
</call>
```
acuse inmediato (`<ack ... type="heartbeat"/>`, sin contenido).

**Advertencia sobre la admisión**: esta captura es unilateral — muestra solo la conexión propia del invitado. La acción del lado del host que admite a un invitado en espera (`waitingRoomAdmit`, enviando una stanza `waiting_room_toggle`/`_admit`, según WA_CALL_SIGNALING.md §10.3) corre en la conexión del *host* y no se observó aquí; este informe solo muestra su resultado. En ambas capturas, la admisión (§6) siguió al único heartbeat visible en bastante menos de un segundo — lo bastante rápido como para que sea **unknown** si esto refleja a un host atento pulsando Admitir de inmediato, o alguna condición de auto-admisión (p. ej. el host ya activo en la llamada); ninguna evidencia aquí distingue entre las dos.

---

## 6. Asignación de JID al invitado (tested)

La admisión llega como un push `group_update`/`group_info` ordinario desde `<call-id>@call`, con dos entradas `<user>` — host e invitado una junto a la otra:

| Campo | Entrada del host | Entrada del invitado |
|-------|-----------|--------------|
| `jid` | `48615137533978` (dispositivo 24 bajo `<device>`) | `29554559176938` (dispositivo 0) |
| `type` | `admin` | *(ausente — sin rol elevado)* |
| `account_kind` | *(ausente)* | `guest` |
| `push_name` | *(ausente en esta entrada)* | `Baron als Gast ohne wa` — el nombre enviado en `link_join` §4.2, copiado literalmente al roster |
| `state` | `connected` | `connected` |
| `platform` del dispositivo | `web` | `web` |
| `pid` del dispositivo | `0` | `1` |

El JID del invitado (`29554559176938`) está en la misma clase de forma de dirección (`type=1`, `domainType=1`, es decir, estilo LID, §2) que el del host, asignado de nuevo por el servidor para esta llamada — no es la identidad de cuenta propia de la sesión que se une. El `pid` del dispositivo (`1` para el invitado) coincide con `self_pid="1"` del bloque de relay en la misma stanza (§7) — el id de participante por dispositivo del roster y el propio id de participante del relay son el mismo número.

**Unknown**: si este JID de invitado se reutiliza en joins repetidos del mismo enlace por el mismo navegador/sesión, cuánto tiempo se retiene, o si es visible para el host más allá de `push_name` y `account_kind`.

---

## 7. Entrega de relay y claves al admitir (tested)

La misma stanza de admisión lleva un bloque `<relay>`, hermano de `<group_info>`, que da al invitado todo lo necesario para alcanzar el medio sin más viajes de ida y vuelta. Los campos coinciden con la gramática de WA_CALL_SIGNALING.md §8.2; esta sección añade detalle concreto a nivel de wire que ese informe dejaba abierto.

| Hijo | Cantidad vista | Notas |
|-------|-----------|-------|
| `<token id=N>` | 3 (ids 0, 1, 2) | binario sin formato, 194 bytes cada uno |
| `<auth_token id=0>` | 1 | binario sin formato, 70 bytes |
| `<key>` | 1 | 24 bytes en el wire — pero esos 24 bytes son en sí texto ASCII de una cadena base64, que al decodificarse de nuevo da una clave sin formato de 16 bytes |
| `<hbh_key>` | 1 | 40 bytes en el wire — mismo patrón: texto ASCII base64, que decodifica a 30 bytes sin formato |
| `<te2 relay_id auth_token_id token_id domain_name relay_name c2r_rtt>` | 6 (2 relays: `edgeray-ham3-1.wt.whatsapp.com`/`ham3c01`, `edgeray-ber1-1.wt.whatsapp.com`/`ber1c01`) | no hay `<te>` presente — confirma la regla de "nunca ambos", esta llamada usó `te2` |
| atributos de relay | `attribute_padding`, `transaction-id`, `self_pid`, `uuid`, `participant_uuid` | `self_pid="1"` se vincula con el propio `pid` de dispositivo del invitado en `group_info` (§6) |
| `<participant pid jid>` | no presente | el hijo de mapeo id-de-participante-a-JID del §8.2 no se vio en esta captura de 2 partes; se desconoce si aparece solo en llamadas de grupo mayores |

Solo `<key>` y `<hbh_key>` llevan la forma de doble codificación (nodo binario que contiene texto ASCII base64); `<token>` y `<auth_token>` son binario sin formato, de una sola decodificación. Qué aporta esta doble capa frente a enviar los bytes sin formato directamente es **unknown** (un resto de un transporte orientado a texto internamente, inferred).

Un hijo `<voip_settings uncompressed="1">`, también hermano de `<group_info>`/`<relay>`, lleva un blob JSON de parámetros del motor (no comprimido en esta captura, consistente con la nota del §5.2 de WA_CALL_SIGNALING.md de que los payloads comprimidos se rechazan al menos en un path). Dentro, bajo el objeto `fs` (feature-switch): `"guest_calling_logging_enabled": "true"` — la única clave específica de invitado encontrada en un documento de ajustes por lo demás genérico de ~32 KB (`aec`, `bwe`, `decode`, `encode`, `sfu`, `rc`, ... — todo ajuste genérico del motor de medios, sin relación con el ingreso de invitados). Los eventos de telemetría enviados por el cliente que se une alrededor de esta llamada usan independientemente la cadena de categoría `guest_calling` (vista en los propios blobs `w:stats`/WAM del cliente), coincidiendo con el nombre de la clave de ajustes.

Dos hermanos inocuos, `<uploadfieldstat/>` y `<userrate interval="0"/>`, viajan en la misma stanza; sin contenido específico de invitado.

El cliente envía inmediatamente un `<ack class="call" type="group_update">` plano para este push (sin contenido) — manejo ordinario según WA_CALL_SIGNALING.md §3.3 (group_update no está en el conjunto de etiquetas sin-ack-inmediato).

---

## 8. Tráfico tras la admisión (tested, breve)

Una vez admitido, el tráfico es indistinguible de una llamada normal en el mismo JID de call-id: `mute_v2` (el host silencia al invitado inmediatamente tras la admisión en esta captura), `transport` (`transport-message-type="4"`, un hijo `<net medium="2" protocol="0"/>`), `relaylatency` (en ambas direcciones, cada una con un `<te latency relay_name>` que referencia los nombres de relay del §7), y cambios de estado `video` (`state="6"`, es decir, `Stopped` según la tabla `kVideoState*` del §13 de WA_CALL_SIGNALING.md, repetido tres veces en rápida sucesión durante la configuración). Nada de esto es específico del enlace; ver WA_CALL_SIGNALING.md §§8, 13 para la semántica general.

---

## 9. Enlace de video vs. solo audio — diferencias observadas (tested)

| Aspecto | Enlace de video | Enlace solo de audio |
|--------|-----------|------------------|
| atributo `media` de `link_query`/`link_join` | `video` | `audio` |
| hijos de `link_join` | `<audio>`, `<video>`, `<net>`, `<capability>` | `<audio>`, `<net>`, `<capability>` — `<video>` omitido |
| `media` del ack de `waiting_room` | `video` | `audio` |
| Mecánica de sala de espera / elegibilidad de invitado | idéntica | idéntica |

No se observó ninguna otra diferencia de protocolo entre los dos; el tipo de medio se transporta de extremo a extremo como un atributo plano, no una familia distinta de stanzas.

---

## 10. Diferencias respecto a una llamada normal 1:1 o de grupo

| Aspecto | Llamada normal 1:1 / de grupo (WA_CALL_SIGNALING.md) | Join de invitado por enlace (este informe) |
|--------|------------------------------------------------|-------------------------------|
| Stanza de entrada | `offer` a un peer/JID de grupo conocido | `link_query` y luego `link_join` al dominio `call` desnudo |
| Clave de llamada | `Message.call.callKey` cifrado con Signal por dispositivo en la oferta | no se observó en la admisión de esta captura; el invitado recibe material de relay/clave (§7) directamente, no una clave de llamada envuelta en Signal — consistente con que un invitado no tenga sesión Signal por pares con el host |
| Identidad de quien llama/es llamado | ambos lados son JIDs conocidos antes de que empiece la llamada | la identidad real del lado que se une no se expone en el roster; el servidor asigna un JID nuevo y lo etiqueta `account_kind="guest"` |
| Admisión | ninguna — offer/accept es la única puerta | sala de espera opcional: `waiting_room enabled`, retenido hasta un admit (no observado, del lado del host) |
| Entrega del roster | `group_info` dentro de la oferta o una actualización posterior | push `group_update`/`group_info` desde `<call-id>@call`, agrupado con `<relay>` y `<voip_settings>` en la misma stanza |
| Direccionamiento de JID | JID de peer/grupo en todo momento | dominio `call` desnudo hasta que existe un call-id, luego `<call-id>@call` |

La ausencia de clave de llamada por dispositivo para el invitado (fila 2) es la diferencia más consecuente y es **tested** solo como una ausencia en esta captura — no confirmada como regla de protocolo; también es consistente con la nota del §9.2 de WA_CALL_SIGNALING.md de que las ofertas de grupo no llevan clave por dispositivo y las claves se reparten de nuevo fuera de banda (`enc_rekey`). Si un invitado alguna vez recibe un `enc_rekey` no se observó en ninguna de las dos ventanas de captura usadas aquí.

---

## 11. Casos de error / trampas

| Síntoma | Causa | Solución / nota |
|---------|-------|-----------|
| El ack de `link_query` no tiene `call-id` | el enlace aún no se ha resuelto a una llamada en curso/iniciable | normal para una vista previa en vacío; el call-id llega solo en el ack de `link_join` |
| El invitado se queda atascado tras el ack de `link_join`, solo se intercambian heartbeats | la sala de espera está activada y el host aún no ha admitido | se requiere acción del lado del host; no visible desde la conexión del invitado |
| `link_join` lleva un hijo `<video>` para un enlace solo de audio | bug del cliente — las dos capturas muestran que este hijo debe estar completamente ausente para `media="audio"` | omitir `<video>` en joins solo de audio |
| El JID de cuenta propio del invitado aparece en el roster de la llamada en lugar de un JID de invitado nuevo | path de join equivocado (`offer`/join de grupo ordinario en lugar de `link_join`) | usar `link_query`→`link_join` para obtener el manejo de `account_kind="guest"` |
| El invitado no recibe clave de llamada pero sí material de relay/clave | esperado para este path (§10) — el invitado no recibe una clave envuelta en Signal como lo haría un callee normal | no tratarlo como un fallo de descifrado |

---

## 12. Distinciones clave

| No confundir | Con |
|-----------------|------|
| **Token** de call-link (22 caracteres, de cara a la URL) | **Call-id** (32 caracteres hex, de cara al protocolo, aparece solo después de `link_join`) |
| JID de dominio `call` desnudo (antes del call-id) | `<call-id>@call` (después del call-id) — ambos son "el JID de dominio de llamada" en etapas distintas, no dos direcciones no relacionadas |
| `is_guest_eligible` (ajuste del enlace: puede *cualquiera* unirse a este enlace como invitado) | `waiting_room enabled` (ajuste del enlace: se retiene a los invitados para admisión) — flags independientes, ambos devueltos como eco en los mismos acks |
| `push_name` del invitado en `link_join` (texto libre, elegido por cada join) | el nombre de perfil propio de WhatsApp de la cuenta que se une (no lo que termina en el roster en un join de invitado) |
| Bytes en wire de `<key>` / `<hbh_key>` (nodo binario que contiene texto ASCII base64, se necesita doble decodificación) | Bytes en wire de `<token>` / `<auth_token>` (binario sin formato, decodificación única) |
| Asignación de JID de invitado (lado del servidor, al admitir, por llamada) | JIDs LID/PN normales (de nivel de cuenta, persistentes) |

---

## 13. Flujo completo (join de invitado, a partir de captura)

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

## 14. Registro de invitado (cliente web, tested)

Una sesión de navegador genuinamente sin cuenta — sin login previo de WhatsApp — registra una identidad desechable antes de enviar siquiera `link_query`. Evidencia: una captura CDP de una sesión impulsada por un humano abriendo un call link real en un navegador; nada en el flujo siguiente se automatizó ni se guionizó más allá del punto de abrir la página y escribir un nombre.

```
GET https://v.whatsapp.net/v2/guest_reg?...
```

| Parámetro | Ejemplo | Significado |
|-------|---------|---------|
| `mcc` / `mnc` | `310` / `999` | códigos de operadora ficticios |
| `lc` / `lg` | locale (p. ej. `DE`/`DE`) | locale de la UI |
| `device_id` | uuid | id de dispositivo generado por el navegador |
| `access_session_id` | uuid | id de sesión |
| `authkey` | base64, 32 bytes | clave pública estática Curve25519 de Noise |
| `e_regid` | base64, 4 bytes | id de registro |
| `e_keytype` | base64, 1 byte | `0x05` = Curve25519 |
| `e_ident` | base64, 32 bytes | clave pública de identidad Signal |
| `e_skey_id` / `e_skey_val` / `e_skey_sig` | — | id de prekey firmada, clave pública (32 B), firma (64 B) |
| `os_name` / `os_version` / `browser` / `browser_version` | hechos de UA | huella del cliente |
| `web_build_version` | p. ej. `2.3000.1052682108` | build del cliente |
| `guest_type` | `guest_calling` | marca esto como registro de invitado de call-link |
| `invite_code` | el token del enlace | qué enlace está uniéndose el invitado |
| `guest_name` | texto libre | el nombre para mostrar que el invitado escribió |
| `id` | 20 bytes sin formato | ocupa el lugar que un número de teléfono ocupa en el registro normal |
| `backup_token` | 20 bytes sin formato | igual a `id` en la captura |

La respuesta (200, cuerpo no capturado) devuelve las credenciales con las que el invitado inicia sesión. Estructuralmente este es el **mismo paquete de registro** (regid, clave de identidad, prekey firmada, firma) que el registro normal de WhatsApp — `guest_type`/`invite_code`/`guest_name` son las únicas adiciones específicas de invitado, y `guest_reg` es un endpoint distinto del path normal `/v2/reg` (**found**, hostnames/paths distintos observados; no contrastado aquí contra el propio código de registro de Android — ver la nota de alcance de `WA_MOBILE_REGISTRATION` si ese tema se cubre en otro lugar).

Había una entrada de lista blanca CSP para un proveedor de desafío anti-automatización en la página, y el código de bootstrap de invitado hace referencia a un concepto de captcha/desafío, pero no se requirió ni se envió ningún token de desafío en esta sesión de bajo volumen impulsada por un humano (**tested**: ausente aquí; **unknown**: bajo qué condiciones se dispara — la activación de control antiabuso basada en riesgo es la hipótesis de trabajo, no confirmada). Este informe no investiga más ese control; hacerlo implicaría sondear un mecanismo antiabuso, lo cual está fuera de alcance aquí.

Evidencia del lado del cliente de que esto es un path de código distinto y consciente del invitado (found, subconjunto representativo de muchos nombres de módulo similares vistos): un módulo de manejo de nombre de participante y un módulo de mensajería/persistencia de trabajos específico de invitado distinto de los equivalentes del cliente de chat normal, más un módulo literalmente nombrado por "si esta UI de llamada está corriendo para un invitado".

## 15. Transporte Noise para una sesión de invitado (tested)

La identidad de invitado registrada inicia sesión sobre el **mismo** transporte ya documentado en [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md): un WebSocket con prefijo de longitud a `wss://web.whatsapp.com/ws/chat` (puerto alterno observado `5222`), el prólogo `WA` + versión, y la misma secuencia de mensajes Noise XX (ClientHello → ServerHello con cadena de certificados → ClientFinish cifrado que lleva la clave estática/de identidad → el primer `ClientPayload` cifrado). Nada en el framing del handshake difiere para un invitado; esto confirma de forma independiente, desde una segunda plataforma de cliente (un navegador, no la app de Android cubierta en otras partes de este proyecto), que los invitados de call-link son clientes Noise XX ordinarios, no un protocolo ligero paralelo.

Un hecho a nivel de proto que esto añade: `ClientPayload` ya define un campo `AccountType` (`DEFAULT = 0`, `GUEST = 1`) en el esquema de proto compartido de WhatsApp. [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) encontró este campo presente pero sin escribir en Android (ningún path de código lo establece — Android nunca es un invitado). Una sesión de invitado en navegador es el cliente que realmente lo establece: `accountType = GUEST` es la única diferencia de `ClientPayload` entre una sesión de invitado y un login de cliente normal, sumado a que la identidad proviene de `guest_reg` (§14) en lugar del registro normal por teléfono y sin llevar datos de emparejamiento de dispositivo.

El detalle más profundo a nivel de función (el código exacto que construye un `ClientPayload` de invitado, y el cuerpo de la respuesta de `guest_reg`) se encuentra en bundles de script cargados de forma diferida y sujetos a sesión que caducan con la página; obtenerlo necesita una captura en vivo fresca con acceso al código fuente del script, no un fetch estático. Lo ya establecido arriba — el transporte es Noise XX sin modificar, el paquete de identidad es un paquete de registro normal, y el único campo marcado es `accountType = GUEST` — no depende de recuperar ese código fuente.

---

## 16. Desconocidos

| Elemento | Estado |
|------|--------|
| Sitio de generación del token (acuñado por el cliente vs. asignado por el servidor) | el call-site de `createCallLink` no lleva argumento de token (found); el origen real es nativo (unknown) |
| Si una sesión de navegador genuinamente sin cuenta produce la misma secuencia de stanza descifrada | parcialmente resuelto (§14–§15): la sesión se registra vía `guest_reg` e inicia sesión sobre el mismo transporte Noise XX con `ClientPayload.accountType = GUEST`; el contenido descifrado de `link_query`/`link_join` en sí no se capturó para esa sesión |
| Forma en el wire de la acción de admisión del lado del host (`waiting_room_toggle`/`_admit`) | no está en esta captura (unilateral); descrita solo a partir de los datos estáticos de WA_CALL_SIGNALING.md §10.3 |
| Por qué la admisión siguió tan rápido al único heartbeat observado | host atento vs. una condición de auto-admisión — no distinguible a partir de esta evidencia |
| Vida útil/reutilización del JID de invitado entre joins repetidos | no observado |
| Si un invitado alguna vez recibe `enc_rekey` o cualquier clave de llamada envuelta en Signal | no observado en ninguna de las dos ventanas de captura |
| Mapeo `<participant pid jid>` bajo `<relay>` | no presente en esta captura de 2 partes; se desconoce si las llamadas de grupo con invitados lo usan |
| Propósito de la doble codificación base64 en `<key>`/`<hbh_key>` frente a `<token>`/`<auth_token>` sin formato | unknown |
| `connected-limit` como límite configurable por el cliente vs. siempre asignado por el servidor | no se encontró setter del cliente (found: solo devuelto por el servidor) |
| Límites de tasa / controles antiabuso en la creación de enlaces o joins de invitado | nada encontrado del lado del cliente; comportamiento del servidor unknown |
