<!-- src-sha1: a1b0d0e9f7c1a5fa3cd781b21b55668d3205ba24 -->
# WhatsApp Nombre de usuario — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** comprobar / establecer / reservar / eliminar nombre de usuario, clave de usuario (PIN), relación con LID, privacidad y visibilidad, operaciones GraphQL de w:mex (doc_ids, variables, respuestas), notificaciones, búsqueda USync, reglas de validación, feature flags, notas sobre Baileys

---

## 1. Qué es un nombre de usuario (técnicamente)

Un nombre de usuario es un identificador del lado del servidor, vinculado a una cuenta, que sirve para poder contactar a alguien sin exponer el número de teléfono. Todas las afirmaciones son análisis estático del APK descompilado. Nivel: **found** = leído en código o assets, **inferred** = deducido del código, **unknown** = no resuelto.

La función se construye sobre tres capas:

| Capa | Transporte | Usada para |
|-------|-----------|----------|
| Gestión propia | IQ `w:mex`, GraphQL persistido (config `whatsapp-android-mex`) | check, set / reserve / delete, get, key (PIN) set / delete, multi-check |
| Búsqueda de otros | USync (`xmlns="usync"`) y la variante MEX `UsyncQuery` | resolver `@username` (+ key) a un LID, obtener el username de un JID conocido |
| Push | notificaciones MEX | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Entre dispositivos | app-state sync (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (lleva `username`) |

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Gestor de username | `C122815Lj` | llamadas `UsernameGet`, `UsernameSet`, actualización de estado local, hook de rate-limit |
| Comprobación de disponibilidad | `C67402tT` | llamada `UsernameCheck` + mapeo de la respuesta |
| Multi check | `C76333Kg` | `UsernameCheckMulti`, bloques de 10 |
| API de key | `MexUsernamePinProtocolApi` | `UsernamePinSet` (set / delete key) |
| Estado local / prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| Enum de estado | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Modo de elegibilidad | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Almacén de rate-limit | `C67942uO` | backoff tras 429 / 503 / 529 |
| Validador local | `C82003fB.A04`, `C1187754z` | longitud, charset, reglas de puntos, regex |
| Validador de key | `C1176550d` (+ `AbstractC111284pZ`) | formato de la key |
| VM de ingreso de key | `UsernamePinEntryViewModel` | enviar la key de un username ajeno |
| Cliente USync | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | constructor / parser de la stanza usync clásica |
| MEX USync | `C229259vZ`, `O0F` | `UsyncQuery` con `include_username` |
| Handlers de notificación | `C49822Lvi`, `C49821Lvh`, anon `X.2YG` en `AbstractC20380p4` | set / delete / update |

Nomenclatura: el nombre de cara al usuario del PIN es **username key** (strings "Username key", "Add a username key to control who can contact you"). En la red y en el código se dice `pin`.

---

## 2. Operaciones MEX (doc_ids)

### 2.1 Dónde viven los doc_ids

Los doc_ids no son literales en `java_src`. El cliente envía el nombre de la operación (`"UsernameSet"`, ...) con el nombre de config `"whatsapp-android-mex"` (found, `C16880is`). El id numérico se lee de `assets/whatsapp-android-mex_client_persist_ids.json`: `EnumC17010j7.WHATSAPP_ANDROID_MEX` apunta a ese archivo, `C17040jA.CMg(op)` devuelve el campo `doc_id`, `AGb(op)` el campo `client_doc_id` (found). Cuál de los dos accesores rellena el atributo `query_id` no se trazó hasta el final (unknown); capturas anteriores en 2.26.26.4 muestran `query_id` igual a `doc_id`.

Los doc_ids siguientes están **found** en el asset de 2.26.41.6:

| Operación | doc_id | Tipo | Punto de llamada | Clase de respuesta |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | none found | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Notas:
- `UsernameGetRecommendationsQuery`: el nombre aparece solo en el JSON del asset. Ninguna clase de `java_src` lo referencia por string (found). Las variables y la respuesta son unknown.
- Los tres nombres de notificación (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) no tienen entrada en el asset de persist-ids. Son tipos de notificación, no solicitudes (ver 7).
- El asset tiene `operation_name_hash`, `operation_text_hash` y `client_doc_id` por operación. Ejemplo `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

### 2.2 Envelope

Construido en `C19370nI` / `C19310nC` (found):

```xml
<iq to="[server jid]" xmlns="w:mex" type="get" id="...">
  <query query_id="DOC_ID">{"queryId":"DOC_ID","variables":{...}}</query>
</iq>
```

| Campo | Regla (código) |
|-------|-------------|
| `xmlns` | `w:mex` |
| `type` | `get` para toda operación, incluidas las mutations |
| atributo `query_id` | se establece solo si tiene de 1 a 20 caracteres |
| cuerpo | JSON `{"queryId": ..., "variables": {...}}`, de 1 a 8448000 bytes |
| variables nulas | `C16770ig.A03(k, null)` y `A02(k, null)` omiten la clave, por lo que un valor ausente significa que la clave no se envía |

Aquí no se reproducen stanzas de red de sesiones en vivo; este build se analizó solo de forma estática.

---

## 3. Operaciones en detalle

### 3.1 UsernameCheck

Variables (found, `C67402tT.A00`):

| Variable | Tipo | Condición |
|----------|------|-----------|
| `username` | string | siempre |
| `include_suggestions` | bool | siempre (la UI pasa `false` en la ruta de comprobación por tecleo `C64H` case 21) |
| `source` | string | solo si no es null |
| `session_id` | string | solo si no es null |

Mapeo de `source` (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, otro -> null (no se envía).

Ruta de la respuesta (found, rama por defecto de `C77183Np`): `data.xwa2_username_check`

| Campo | Tipo | Uso |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | se lee solo con `INVALID` |
| `rejection_reasons` | lista de `C4G8` | se lee solo con `INVALID` |
| `suggestions_eligible` | bool | por defecto `true` cuando el campo es null |

Valores de `C4G8` (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Mapeo: `SUCCESS` -> `C76283Kb` (disponible); `INVALID` -> `C76303Kd` (no disponible, lleva suggestions + reasons); `UNSET` -> ninguna rama asigna un resultado (el callback recibe la variable anterior/null; comportamiento unknown). Backoff local activo -> `C76293Kc` (error con código de rate-limit de las prefs, ver 5.3); el callback de fallo de la solicitud en sí no se leyó.

Los motivos de rechazo controlan el texto de vinculación de cuentas ("This username matches an account on Facebook/Instagram. To use it ... add your accounts to Accounts Center", `C82003fB`). En `C82003fB` cualquier motivo distinto de `UNSET` activa la ruta de error local con código 40601 (`A08(40601L)`); una lista vacía o solo con `UNSET` muestra "Username isn't allowed." El flujo de control exacto alrededor del bucle está solo parcialmente descompilado (inferred).

### 3.2 UsernameCheckMulti

| Variable | Tipo | Notas |
|----------|------|-------|
| `usernames` | **list<string>** | array vía `A00.A0B("usernames", list)`; el catálogo de doc_ids lo tipa como `str`, el código envía una lista |

Batching (`C76333Kg.AG5`): la lista se divide en los primeros 10 y el resto; el resto se procesa tras un retardo del flag **29327** (por defecto 60, unidad no resuelta). Una lista vacía devuelve un mapa vacío sin solicitud.

Ruta de la respuesta `data.xwa2_username_check_multi.results[]` (found): cada elemento tiene `username` y `response.result` (mismo `EnumC59782gh`). Mapeo: `SUCCESS` -> disponible, `INVALID` -> no disponible (sin suggestions, `suggestions_eligible=false`), cualquier otro -> error. Los nombres ausentes del resultado se marcan como error.

Consumidor: `UsernameAvailabilityCache` almacena `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) por nombre. El propósito (prefetch para sugerencias de username de Facebook / Instagram, string `foa_username_prefetch_cache`) es inferred.

### 3.3 UsernameSet (crear / cambiar / reservar / eliminar)

Variables (found, `C122815Lj.A00`):

| Variable | Tipo | Condición |
|----------|------|-----------|
| `username` | string | se omite cuando es null (**delete**) |
| `reserved` | bool | siempre se envía |
| `session_id` | string | solo si no está vacío (`C1YW.A08`) |
| `source` | string | solo si el int de source no es null (ver 3.1) |
| `pin` | string | solo si no es null |

`reserved` se calcula, no es constante (found). El argumento `z` (force) = true da `false`. En otro caso: estado actual `ACTIVATED` o `CREATED` da `false`; estado actual `RESERVED` o modo de elegibilidad `RESERVATION` da `true`; todos los demás casos dan `false`. Así que `reserved:true` solo se envía para cuentas en modo de reserva o que ya tienen una reserva.

Delete es un modo de la misma operación: `username == null` -> tag de log `delete`, en otro caso `set` (también en `MexUsernamePinProtocolApi` para la key). Con username null la clave `username` no está en las variables (found).

Guarda del lado del cliente: antes de enviar, si el almacén de rate-limit informa de un backoff activo, la llamada falla localmente con `username_creation_rate_limit_error_code` y el texto "rate limit expiration time not reached" (found, `C122815Lj.A03`).

Manejo del éxito (`C122815Lj.A01`, found):

| Condición | Estado local escrito (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username null o vacío | `UNSET`, pref de key borrada |
| `reserved` era true | `RESERVED` |
| flag de activación | `ACTIVATED` |
| otro | `ACTIVATED` si el estado era `ACTIVATED` y el nombre es igual al almacenado, en otro caso `CREATED` |
| el int de `source` es 1 o 2 | pref `username_set_via_account_linking` = (int == 2) |
| `pin` enviado | pref `username_pin` actualizada |
| flag teen | pref `is_teen_account` = true |

La escritura de la pref es `Voip.REJECT_REASON_DECLINED`, que es el string vacío `""` en este build (found).

Manejo de errores (`C138725uA` case 2):

| Código tipo HTTP | Acción del cliente |
|----------------|---------------|
| 429, 503, 529 | backoff almacenado (5.3) |
| 304 | tratado como éxito ("not modified"), el estado local se actualiza igualmente |
| sin conexión (`C213639Bb`) | resultado "no network" `C4BO` |
| otro | `C4BN(code, message)` |

### 3.4 UsernameGet

Variables: ninguna (la llamada construye un conjunto de variables vacío, found, `C122815Lj.A02`). Marcada `@Deprecated`, reemplazada por una variante suspend.

Respuesta (found, `C138815uJ` case 34): `data.xwa2_username_get.username_info`

| Campo | Uso |
|-------|-----|
| `username` | almacenado; string vacío si está ausente |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **la key se devuelve en claro y se almacena en la pref `username_pin`**; string vacío si está ausente |

Mapeo de estado: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED` si el username almacenado es igual al devuelto y el estado local era `RESERVED` o `ACTIVATED`, en otro caso `CREATED`; state null o `username_info` null -> `UNSET`.

El error 404 del servidor borra el username, la key y el estado locales (log `clearSelfUsernameData NOT_FOUND`).

Si la llamada se usa como heartbeat es unknown; la antigua nota "polling heartbeat" no está respaldada por el código de este build.

### 3.5 UsernamePinSet (username key)

Variables (found): `pin` (string), se omite cuando es null.

| Acción | Variables |
|--------|-----------|
| set key | `{"pin": "<key>"}` |
| delete key | `{}` (`A02` llama a `A00(null)`) |

El nombre de operación para ambas es `UsernamePinSet`; no hay una operación de verificación separada. La verificación de una key ajena se hace en USync (4). Sin conexión: devuelve `C213639Bb("UsernamePinSet")` sin solicitud.

La key también puede viajar en `UsernameSet` (variable `pin`). `C81793ej.A0x` usa `UsernameSet` con el username existente y el nuevo `pin` cuando ya hay un username almacenado localmente (`A00 != null`), y `UsernamePinSet` en caso contrario (found).

La clase de respuesta `C48557LJz` no tiene acceso a campos en los archivos leídos; la forma de la respuesta es unknown.

---

## 4. Búsqueda de otros usuarios

### 4.1 USync clásico por username (flujo de key)

Construido en `C18670m9.A06` (jadx falló en este método, leído de smali `X/0m9.smali`). Por entrada de solicitud `C222649hm`: campo `A0C` = username, `A0D` = key, `A05` = LID.

Atributos del hijo contact (found en smali): `username` siempre; `lid` cuando se conoce un LID localmente; `pin` cuando hay una key establecida. Los atributos adicionales están condicionados por el flag **12402** (por defecto `false`): cuando el flag está apagado, solo se escribe `username` (found). El nombre de nodo `contact` es inferred a partir del parser de la respuesta, que lee el hijo `contact` y su atributo `username` (`C18670m9` líneas ~969-975).

```xml
<iq xmlns="usync" to="[server]" type="get">
  <usync mode="query" context="interactive" sid="..." index="0" last="true">
    <list>
      <user><contact username="name" lid="LID" pin="KEY"/></user>
    </list>
    <query><contact/> ... </query>
  </usync>
</iq>
```

Punto de entrada: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), llamado por `submitPinForUsername`. Tipo de sync `EnumC21760rz.A0J`, timeout 32000 ms. El conjunto de atributos `contact`, `pin`, `username` está en los conjuntos de redacción de logs de `AbstractC40921lc` (found).

Pre-resolución local: `A0M.Aol(username)` busca `lid_row_id` en la tabla `lid_display_name` donde `UPPER(username) = UPPER(?)`, fila más reciente primero (found, `C1S0`). El LID, si se conoce, va en el atributo `lid`.

### 4.2 Evaluación del resultado (ingreso de key)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Resultado | Condición |
|---------|-----------|
| key correcta | el `UserJid` del resultado es un LID (`C14080dr`) |
| key incorrecta | el resultado no tiene LID: log `[un-pin] incorrect PIN`, texto de error "Wrong key entered" |
| sin red | `C9qA` código 1 |
| error genérico de infraestructura | `C9qA` código 2 |
| rate limit del solicitante | `C225769os.A01` true: "Too many attempts made. Try later." |
| rate limit del solicitado | `C225769os.A00` true: "This account can't be reached with their key right now..." |

La comprobación de rate-limit en caché del lado del cliente se ejecuta primero cuando el flag **16033** está activo y la config JSON **21995** tiene `enable_key_rate_limit` en true (por defecto true): `C30P.A00` contra el LID propio y contra el username objetivo. Al username se le quita el `@` (`C0CX.A0i(username, '@')`).

En caso de éxito el resultado es un **LID**; el chat se dirige entonces al LID (inferred a partir de la comprobación `C14080dr`; el paso de apertura del chat no se trazó).

### 4.3 Obtener el username de un LID conocido

`C23638AId` (línea ~600-650) construye un usync con `<list><user jid="LID"/></list><query><contact/><username/></query>`, modo/contexto de `EnumC21760rz.A0J` (found). El parser lee `username` como hijo del resultado `<usync>` (`C18670m9` línea 586, solo cuando la solicitud lo pidió).

### 4.4 MEX USync (`UsyncQuery`)

`C229259vZ.A01` construye `UsyncQuery` (doc_id arriba). Partes relevantes (found):

| Variable | Uso |
|----------|-----|
| `query_input[]` | una entrada por usuario: JID (`C493020r.A0C`), `client_known_username` opcional (solo cuando se solicita el username y no está vacío) |
| `include_username` | bool, se establece cuando alguna entrada solicita el username |
| `include_lid` | bool, solicita `lid_info` |
| `telemetry.context` | contexto USync en minúsculas |

Respuesta por usuario: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` es polimórfico según el hash de tipo: un tipo de valor que contiene `username`, o un tipo de estado con `status` de `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ unset). `NOT_ALLOWED` se registra como "username not allowed to be queried" y borra el username almacenado; `NO_CHANGE` lo conserva. `lid_info.lid_jid` lleva el LID.

Puerta: `ContactSyncHelper` rechaza la ruta MEX con el log "cantUseMex as username ab prop is off" salvo que el flag **8421** esté activo cuando se solicita un username (found; por defecto `false`).

---

## 5. Validación, límites, errores

### 5.1 Formato del username (local)

Validador `C82003fB.A04` (found), comprobaciones en este orden:

| Orden | Comprobación | Id de error (`C02U`) | String del mensaje |
|-------|-------|-------------------|----------------|
| 1 | cada carácter en `[A-Za-z0-9_.]` | 2 | "must start with a letter and can only contain letters, digits, periods and underscores" |
| 2 | longitud >= mín (flag **20494**, por defecto 3) | 0 | "Use between %1$d-%2$d characters" |
| 3 | longitud <= máx (flag **20459**, por defecto 35) | 1 | mismo string |
| 4 | sin `.` inicial, sin `.` final, sin `..` | 3 | "can't start or end with a period or have 2 periods in a row" |
| 5 | al menos una letra ASCII | 4 | "Choose a username with at least one letter" |
| 6 | regex (abajo) | pasa o falla con 2 | n/a |

Regex construida por `C1187754z.A02()` (found):

```
^(?!.*\.\.)(?=.*[a-zA-Z])[a-zA-Z0-9_][a-zA-Z0-9_.]{MIN-1,MAX-1}(?<![.])$
```

El validador no normaliza mayúsculas/minúsculas; la búsqueda local `Aol` compara con `UPPER()`, por lo que la coincidencia es insensible a mayúsculas localmente (found). Si el servidor trata los nombres sin distinguir mayúsculas es unknown. La regex permite un guion bajo inicial; el texto de la UI dice "start with a letter", que es más estricto que la regex (found, discrepancia).

La UI también rechaza enlaces web: "Enter only your username, not a web link" (string presente, comprobación no trazada).

### 5.2 Formato de la username key

`C1176550d.A00` (found): el flag **34350** es un string regex, por defecto `^([0-9]{4}|[A-Z0-9]{6})$`. Si el string del flag está vacío, el fallback es exactamente cuatro dígitos. Una regex inválida registra `[un-pin] invalid username_key_regex` y acepta cualquier cosa. Los límites de longitud, flags **34347** (mín, 4) y **34348** (máx, 6), alimentan solo la ruta del mensaje de error en `UsernamePinEntryViewModel.A0w`. Las reglas del servidor son unknown.

Por tanto, la antigua nota "4-digit PIN" está incompleta: el valor por defecto distribuido acepta cuatro dígitos o seis caracteres alfanuméricos en mayúsculas.

### 5.3 Rate limits y backoff

`C67942uO` (found), activo solo con el flag **28678** (por defecto `false`):

| Elemento | Valor |
|------|-------|
| disparador | error 429, 503 o 529 de `UsernameSet` |
| duración | string tipo `Retry-After` analizado como int de segundos (`C23680AJt.A00`), en otro caso flag **28127** (por defecto 30) segundos |
| almacenamiento | prefs `username_creation_rate_limit_backoff_expiry` (ms), `username_creation_rate_limit_error_code` |
| efecto | `UsernameCheck`, `UsernameCheckMulti`, `UsernameSet` fallan localmente hasta la expiración |

### 5.4 Código de error a mensaje (`C82003fB.A02`, found)

| Código | Mensaje |
|------|---------|
| 400 | "Couldn't save your username. Try again." |
| 403, 404, 429 | "Couldn't complete your request. Try again." |
| 500, 529 | "We couldn't complete your request. Try again later." |
| 503 | "... Please try again later." |
| 406, 40601 | "This username is not available." |
| 40602 | "You can't make more changes to your username. Try again later." |
| 40603 | "You can't make changes to your username right now. Try again later." |
| otro | "We couldn't complete your request. Try again." |

40601 a 40603 están en el conjunto permitido `AbstractC111104pH.A01` (en el código leído solo se muestra 40603). Su semántica en el servidor es unknown más allá del texto del cliente.

---

## 6. Relación con LID

Todo found salvo indicación contraria.

| Hecho | Evidencia |
|------|----------|
| Las búsquedas de username resuelven a un **LID**, no a un JID de teléfono | prueba de éxito de la key `userJid instanceof C14080dr` (clase LID); `lid_info.lid_jid` en MEX usync |
| Mapa local username -> LID | tabla `lid_display_name` (columnas `username`, `lid_row_id`), consulta en `C1S0` |
| Las notificaciones identifican al usuario por LID | los handlers de set / delete analizan `LidUserJid` (texto de error "Failed to parse LidUserJid") |
| La notificación de delete puede llevar un JID de teléfono | el handler comprueba `isPnPresent`; con PN presente hace cast a un JID PN y actúa, sin PN retorna |
| Acción de sync de contacto | `ContactAction` tiene `username` (6) junto a `lid_jid` (3), `pn_jid` (5); también `LidContactAction` (`lid_contact`, campo 61 de SyncActionValue) |
| Modo de inicio de chat | campo **59** de SyncActionValue `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Solo se encontró el códec de sync; sin consumidor en el código de UI (unknown) |
| String de feature del companion | al vincular un companion el primario añade `username_supported` (flag 4745 o 20189), `username_reservation_only_mode` (solo 20189), `username_account_linking_enabled` (flag 21199) a su lista de features (`C25056AqU`) |

Inferred: un usuario que existe solo como username solo es alcanzable a través del LID hasta que el propietario comparte el número de teléfono; los strings "If you continue, your phone number will show in existing username chats and calls" (diálogo de delete) lo respaldan, pero la ruta de exposición del PN no se trazó.

---

## 7. Notificaciones

Los handlers extienden `AbstractC23194A0r` y se registran en `AbstractC20380p4` (found):

| Notificación | Handler | Comportamiento |
|--------------|---------|----------------|
| `UsernameSetNotification` | `C49822Lvi` | payload `xwa2_notify_username_on_change`: lee el LID (field hash 107143) y el username; almacena vía `InterfaceC11470Yz.BNU(lid, username)`; si el contacto existe y es del tipo correspondiente, refresca el contacto (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | payload `xwa2_notify_username_delete`: lee LID y PN (hash -983979708); con PN presente ejecuta la actualización de delete (`C53594Nzh`) |
| `UsernameUpdateNotification` | anon `X.2YG` | lee un hash base64 del payload, construye una solicitud USync con motivo `USERNAME_UPDATE_NOTIFICATION` y `EnumC21760rz.A0Q` (contexto `NOTIFICATION_SIDELIST`, modo `query`; ver WA_USYNC.md), log `usync triggered for hash` |

Texto mostrado al usuario: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", es decir, el servidor puede reasignar un username (revocación, pref `is_username_revoked`, `revocation_banner_dismissed_<username>`).

---

## 8. Feature flags

Los IDs de flag son ids de AB-prop leídos mediante `C08J` (valores por defecto de las tablas de `C08J`). Todos los valores por defecto de abajo se leyeron de este build.

| Flag | Tipo | Por defecto | Controla |
|------|------|---------|----------|
| **4745** | bool | false | primario: creación de username (modo `CREATION`); también anunciado como `username_supported` |
| **20189** | bool | false | primario: modo solo reserva (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: funciones de username en absoluto (si no, `DISABLED`) |
| **21199** | bool | false | vinculación de cuentas (FB / IG) habilitada, anunciada como `username_account_linking_enabled` |
| **16033** | bool | false | puerta maestra para las funciones de key (`C79343Xx.A00`): rate limit de key, upsell de key, vista WABI de username |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (todos true por defecto cuando falta la clave JSON) |
| **8421** | bool | false | permite `UsyncQuery` MEX para solicitudes de username |
| **12402** | bool | false | añade los atributos `lid` y `pin` al nodo `contact` de usync |
| **20494** / **20459** | int | 3 / 35 | longitud mín / máx del username |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | regex de la key |
| **34347** / **34348** | int | 4 / 6 | límites de longitud de la key (mensaje de error) |
| **28678** | bool | false | habilita el almacén de backoff de rate-limit |
| **28127** | int | 30 | segundos de backoff por defecto |
| **29327** | int | 60 | retardo antes del segundo lote de `UsernameCheckMulti` |

Elegibilidad del companion (`C224069kP.A00`, lectura a nivel de bytecode):

```
companion (identity of the A02 check inferred from the "open WhatsApp on your primary device" strings):
  23817 off, or pref username_reservation_creation_supported_on_primary false  -> DISABLED
  pref username_account_linking_enabled_on_primary true                         -> COMPANION_READ_ONLY
  state RESERVED                                                                -> COMPANION_READ_ONLY
  state not UNSET                                                               -> CREATION
  state UNSET and pref username_reservation_only_mode_on_primary true           -> COMPANION_READ_ONLY
  state UNSET otherwise                                                         -> CREATION
primary:
  4745 on -> CREATION;  else 20189 on -> RESERVATION;  else DISABLED
```

Las tres prefs `*_on_primary` solo se leen aquí; dónde se escriben no se encontró (unknown).

---

## 9. Privacidad y visibilidad

| Aspecto | Hallazgo | Nivel |
|--------|---------|------|
| Propósito | "Keep your phone number private with a username"; las personas que no tienen el número guardado ven el username en su lugar | found (strings) |
| Primer contacto | con una key establecida, las personas con las que "you haven't interacted with" deben introducir la key antes de contactar al username | found (strings) |
| Compartir la key | la acción de compartir username puede incluir la key (pref `username_share_include_pin`, migrada en `C138535tr`); strings "Share your username and key" | found |
| Dónde se oculta el número | los admins de comunidades y de canales ven el número salvo que se establezca un username; los seguidores de canales no ven ninguno de los dos | found (strings) |
| Telemetría de grupo / hilo | campos `has_username`, `has_username_pin`, `is_username_thread` en la telemetría de envío de mensajes (`DZ1`, `RQG`) | found |
| Key en reposo | la key propia la devuelve `UsernameGet` y se almacena en prefs planas `username_pin` | found |
| Chats de terceros | "Usernames and contacts added to third-party chats will not save to your phone" | found (string) |
| Business | "This username is only available on WhatsApp Business" aparece como texto de rechazo | found (string) |
| Quién puede consultar | el estado `NOT_ALLOWED` de MEX usync muestra que el servidor puede negar la divulgación del username por solicitante | found (enum), regla unknown |
| Menores | pref `is_teen_account`; textos para padres "Your child created the username ..." | found |

Las reglas de visibilidad aplicadas por el servidor (quién puede resolver un username, rate limits de key, reasignación) son unknown desde el cliente.

---

## 10. Notas sobre Baileys

El envelope de 2.2 es genérico; un cliente Baileys puede construirlo. Esto es **inferred**, no se probó aquí.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| Riesgo | Motivo |
|------|--------|
| deriva de doc_id | los ids pertenecen al asset de este build; otros builds pueden diferir (unknown) |
| `session_id` | el código lo envía cuando está presente; si el servidor exige el mismo valor para check y set es unknown |
| atributos de key | `lid` / `pin` en `contact` están tras el flag 12402; el servidor puede ignorarlos para clientes sin el flag (unknown) |
| reglas locales | las reglas de longitud, charset y puntos son del lado del cliente; las reglas del servidor son unknown |

---

## 11. Distinciones clave

| No confundir | Diferencia |
|----------------|------------|
| Username key vs PIN de cuenta / 2FA | La username key (`pin` en `UsernamePinSet`, pref `username_pin`) controla el primer contacto vía username. No tiene relación con el 2FA del registro |
| variable `reserved` vs `UsernamePinSet` | `reserved` pertenece a `UsernameSet` y marca una reserva; la key tiene su propia operación |
| estado `RESERVED` | `C4DU.RESERVED` local / `state=RESERVED` del servidor es un nombre retenido aún no utilizable; `ACTIVATED` y `CREATED` son utilizables |
| Delete | no hay operación delete; `UsernameSet` sin `username` elimina; el delete de la key es `UsernamePinSet` con `{}` |
| Resultado de check `INVALID` | cubre ocupado, vinculación requerida y problemas de formato; el detalle está en `rejection_reasons` |
| Username vs LID | el username es un identificador; la identidad de direccionamiento es el LID |
| ints de `source` | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; no son los mismos ints que los ids de error de `C02U` |
| doc_id vs `client_doc_id` | ambos están en el asset; los ids capturados son iguales a `doc_id` |
| Notificaciones vs operaciones | los tres tipos `Username*Notification` son handlers push, no solicitudes |
| Etiquetas entre repos | `25975613018777537` está ausente del asset de persist-ids de este build; `25741205615468935` es `GetTextStatusList` en este build. Ninguno es una operación de username aquí |

---

## 12. Flujo de extremo a extremo

```
[User]                [Client]                              [Server]
  │ type name           │                                      │
  ▼                     │                                      │
 local validate ────────┤ charset, 3..35, dots, regex (5.1)    │
  │ ok                  ▼                                      │
  │              UsernameCheck {username, include_suggestions,  │
  │                             source, session_id}  ─────────►│
  │                     │◄──── xwa2_username_check {result,    │
  │                     │       suggestions, rejection_reasons}│
  │ SUCCESS             │                                      │
  ▼                     ▼                                      │
 confirm ─────────► UsernameSet {username, reserved,           │
                      session_id, source, [pin]} ─────────────►│
                        │◄──── ok | 304 | 40601..40603 | 429/503/529
                        ▼                                      │
                  write prefs: state, username_pin             │
                  429/503/529 -> backoff (flag 28678)          │
                                                               │
 [Owner sets key] ► UsernamePinSet {pin} | {} (delete) ───────►│

 [Other user, first contact]
  │ enter @name + key
  ▼
 validate key (flag 34350) ► usync contact{username,[lid],[pin]} ──►[Server]
                        │◄──── user jid (LID) | no LID | rate-limit flags
                        ▼
              LID  = open chat addressed to the LID
              none = "Wrong key entered"
              limit = "Too many attempts" / "can't be reached"

 [Server push]
   UsernameSetNotification (lid, username)  -> update local map
   UsernameDeleteNotification (lid, pn)     -> update contact
   UsernameUpdateNotification (hash)        -> usync delta
```

---

## 13. Unknowns

| Tema | Motivo |
|-------|--------|
| Accesor exacto que alimenta `query_id` | el consumidor de `doc_id` vs `client_doc_id` no se trazó hasta el constructor del IQ |
| Forma de la respuesta de `UsernamePinSet`, `UsernameSet` | las clases de respuesta no tienen acceso a campos en el código leído |
| `UsernameGetRecommendationsQuery` | sin punto de llamada, sin variables |
| Reglas del servidor para username y key | el cliente solo valida localmente |
| Significado de 40601-40603 en el servidor | solo se encontraron strings del cliente |
| Origen de las prefs `*_on_primary` | no se encontró ningún escritor |
| Efecto de `username_chat_start_mode` | no se encontró ningún consumidor |
| Patrón de uso de `UsernameGet` (heartbeat) | no respaldado por el código leído |
| Paso de apertura del chat tras una key correcta | no trazado más allá de la comprobación del LID |
| Tráfico real | solo análisis estático |
