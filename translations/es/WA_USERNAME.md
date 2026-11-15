<!-- src-sha1: 73855f4f8148d9b0ef853f43cef4adbe0cb996a5 -->
# WhatsApp Username — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** verificación/fijación/reserva/eliminación de username, clave de username (PIN), relación con LID, privacidad y visibilidad, operaciones GraphQL w:mex (doc_ids, variables, respuestas), notificaciones, búsqueda USync, reglas de validación, feature flags, notas de Baileys

---

## 1. Qué es un username (técnicamente)

Un username es un handle del lado servidor atado a una cuenta, usado para que un contacto pueda ser alcanzado sin exponer el número de teléfono. Todas las afirmaciones son análisis estático de la APK decompilada. Nivel: **found** = leído en código o assets, **inferred** = deducido del código, **unknown** = no resuelto.

La función se construye sobre tres capas:

| Capa | Transporte | Usada para |
|-------|-----------|----------|
| Gestión propia | IQ `w:mex`, GraphQL persistido (config `whatsapp-android-mex`) | verificar, fijar/reservar/eliminar, obtener, fijar/eliminar clave (PIN), multi-verificación |
| Búsqueda de otros | USync (`xmlns="usync"`) y la variante MEX `UsyncQuery` | resolver `@username` (+ clave) a un LID, obtener el username de un JID conocido |
| Push | notificaciones MEX | `UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification` |
| Entre dispositivos | sincronización de app-state (`SyncActionValue`) | `username_chat_start_mode`, `lid_contact_action` (lleva `username`) |

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| Gestor de username | `C122815Lj` | llamadas `UsernameGet`, `UsernameSet`, actualización de estado local, hook de rate-limit |
| Verificación de disponibilidad | `C67402tT` | llamada `UsernameCheck` + mapeo de respuesta |
| Multi-verificación | `C76333Kg` | `UsernameCheckMulti`, en lotes de 10 |
| API de clave | `MexUsernamePinProtocolApi` | `UsernamePinSet` (fijar/eliminar clave) |
| Estado local / prefs | `C5Q8` | `username_reservation_state`, `username_pin`, `is_username_revoked` |
| Enum de estado | `C4DU` | `UNSET`, `RESERVED`, `ACTIVATED`, `CREATED` |
| Modo de elegibilidad | `C224069kP.A00()` -> `C9SR` | `CREATION`, `RESERVATION`, `COMPANION_READ_ONLY`, `DISABLED` |
| Almacén de rate-limit | `C67942uO` | backoff tras 429 / 503 / 529 |
| Validador local | `C82003fB.A04`, `C1187754z` | longitud, charset, reglas de punto, regex |
| Validador de clave | `C1176550d` (+ `AbstractC111284pZ`) | formato de clave |
| VM de entrada de clave | `UsernamePinEntryViewModel` | enviar clave para un username ajeno |
| Cliente USync | `C23638AId` (`querySyncUsernameWithErrorInfo`), `C18670m9` | constructor/parser de stanza usync clásico |
| USync MEX | `C229259vZ`, `O0F` | `UsyncQuery` con `include_username` |
| Manejadores de notificación | `C49822Lvi`, `C49821Lvh`, anónimo `X.2YG` en `AbstractC20380p4` | fijar/eliminar/actualizar |

Nomenclatura: el nombre visible al usuario del PIN es **clave de username** (strings "Username key", "Add a username key to control who can contact you"). El cable y el código dicen `pin`.

---

## 2. Operaciones MEX (doc_ids)

### 2.1 Dónde viven los doc_ids

Los doc_ids no son literales en `java_src`. El cliente envía el nombre de la operación (`"UsernameSet"`, ...) con el nombre de config `"whatsapp-android-mex"` (found, `C16880is`). El id numérico se lee de `assets/whatsapp-android-mex_client_persist_ids.json`: `EnumC17010j7.WHATSAPP_ANDROID_MEX` mapea a ese archivo, `C17040jA.CMg(op)` devuelve el campo `doc_id`, `AGb(op)` el campo `client_doc_id` (found). Cuál de los dos accesores llena el atributo `query_id` no fue rastreado hasta el final (unknown); capturas anteriores en 2.26.26.4 muestran `query_id` igual a `doc_id`.

Los doc_ids abajo son **found** en el asset de 2.26.41.6:

| Operación | doc_id | Tipo | Call site | Clase de respuesta |
|-----------|--------|------|-----------|----------------|
| `UsernameCheck` | `26124072630599518` | query | `C67402tT.A00` | `C2IG` |
| `UsernameCheckMulti` | `27134626522840286` | query | `C76333Kg.A00` | `C2IE` |
| `UsernameGet` | `32618050064506055` | query | `C122815Lj.A02` | `C87173nz` |
| `UsernameSet` | `27108705368767936` | mutation | `C122815Lj.A00` | `C87183o0` |
| `UsernamePinSet` | `25529696019976770` | mutation | `MexUsernamePinProtocolApi.A00` | `C48557LJz` |
| `UsernameGetRecommendationsQuery` | `26077456248616957` | query | ninguno encontrado | unknown |
| `UsyncQuery` | `38635300486116501` | query | `C229259vZ.A01` | `C2IQ` |

Notas:
- `UsernameGetRecommendationsQuery`: el nombre aparece solo en el JSON del asset. Ninguna clase en `java_src` lo referencia por string (found). Variables y respuesta son unknown.
- Los tres nombres de notificación (`UsernameSetNotification`, `UsernameUpdateNotification`, `UsernameDeleteNotification`) no tienen entrada en el asset de persist-id. Son tipos de notificación, no requests (ver 7).
- El asset tiene `operation_name_hash`, `operation_text_hash` y `client_doc_id` por op. Ejemplo `UsernameSet`: `client_doc_id` `427995565715419341100134328918` (found).

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
| `type` | `get` para cada operación, incluidas las mutaciones |
| atributo `query_id` | fijado solo si tiene entre 1 y 20 caracteres |
| cuerpo | JSON `{"queryId": ..., "variables": {...}}`, de 1 a 8448000 bytes |
| variables null | `C16770ig.A03(k, null)` y `A02(k, null)` omiten la clave, así que un valor ausente significa que la clave no se envía |

Los stanzas de cable de sesiones en vivo no se reproducen aquí; este build se analizó solo estáticamente.

---

## 3. Operaciones en detalle

### 3.1 UsernameCheck

Variables (found, `C67402tT.A00`):

| Variable | Tipo | Condición |
|----------|------|-----------|
| `username` | string | siempre |
| `include_suggestions` | bool | siempre (la UI pasa `false` en la ruta de verificación tipada `C64H` case 21) |
| `source` | string | solo si no es null |
| `session_id` | string | solo si no es null |

Mapeo de `source` (`AbstractC78993Wd.A0U`): int 1 -> `FB`, 2 -> `IG`, 3 -> `USER_INPUT`, 4 -> `SUGGESTION`, otro -> null (no se envía).

Ruta de respuesta (found, rama por defecto de `C77183Np`): `data.xwa2_username_check`

| Campo | Tipo | Uso |
|-------|------|-----|
| `result` | enum `EnumC59782gh` | `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `INVALID`, `SUCCESS` |
| `suggestions` | list<string> | leído solo cuando `INVALID` |
| `rejection_reasons` | lista de `C4G8` | leído solo cuando `INVALID` |
| `suggestions_eligible` | bool | por defecto `true` cuando el campo es null |

Valores de `C4G8` (found): `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALREADY_TAKEN`, `REQUIRE_FB_ACCOUNT_LINKING`, `REQUIRE_FB_CONSUMER_ACCOUNT_LINKING`, `REQUIRE_IG_ACCOUNT_LINKING`, `REQUIRE_IG_CONSUMER_ACCOUNT_LINKING`.

Mapeo: `SUCCESS` -> `C76283Kb` (disponible); `INVALID` -> `C76303Kd` (no disponible, lleva sugerencias + razones); `UNSET` -> ninguna rama asigna un resultado (el callback recibe la variable previa/null; comportamiento unknown). Backoff local activo -> `C76293Kc` (error con código de rate-limit desde prefs, ver 5.3); el callback de fallo de la request misma no fue leído.

Las razones de rechazo conducen el texto de vinculación de cuenta ("Este username coincide con una cuenta en Facebook/Instagram. Para usarlo... añade tus cuentas al Centro de cuentas", `C82003fB`). En `C82003fB` cualquier razón distinta de `UNSET` dispara la ruta de error local con código 40601 (`A08(40601L)`); una lista vacía o solo-`UNSET` muestra "Username isn't allowed." El flujo de control exacto alrededor del bucle solo está parcialmente decompilado (inferred).

### 3.2 UsernameCheckMulti

| Variable | Tipo | Notas |
|----------|------|-------|
| `usernames` | **list<string>** | array vía `A00.A0B("usernames", list)`; el catálogo de doc_id lo tipa como `str`, el código envía una lista |

Loteado (`C76333Kg.AG5`): la lista se divide en los primeros 10 y el resto; el resto se procesa tras un retraso del flag **29327** (por defecto 60, unidad no resuelta). Una lista vacía devuelve un mapa vacío sin request.

Ruta de respuesta `data.xwa2_username_check_multi.results[]` (found): cada ítem tiene `username` y `response.result` (mismo `EnumC59782gh`). Mapeo: `SUCCESS` -> disponible, `INVALID` -> no disponible (sin sugerencias, `suggestions_eligible=false`), cualquier otra cosa -> error. Los nombres faltantes del resultado se marcan como error.

Consumidor: `UsernameAvailabilityCache` almacena `EnumC59192fk` (`UNKNOWN`, `AVAILABLE`, `UNAVAILABLE`) por nombre. El propósito (prefetch para sugerencias de username de Facebook/Instagram, string `foa_username_prefetch_cache`) es inferred.

### 3.3 UsernameSet (crear / cambiar / reservar / eliminar)

Variables (found, `C122815Lj.A00`):

| Variable | Tipo | Condición |
|----------|------|-----------|
| `username` | string | omitido cuando es null (**eliminar**) |
| `reserved` | bool | siempre enviado |
| `session_id` | string | solo si no está vacío (`C1YW.A08`) |
| `source` | string | solo si el int de source no es null (ver 3.1) |
| `pin` | string | solo si no es null |

`reserved` es calculado, no constante (found). Argumento `z` (force) = true da `false`. De otro modo: estado actual `ACTIVATED` o `CREATED` da `false`; estado actual `RESERVED` o modo de elegibilidad `RESERVATION` da `true`; todos los demás casos dan `false`. Así que `reserved:true` solo se envía para cuentas en modo de reserva o que ya tienen una reserva.

Eliminar es un modo de la misma operación: `username == null` -> tag de log `delete`, de otro modo `set` (también en `MexUsernamePinProtocolApi` para la clave). Con un username null la clave `username` no está en las variables (found).

Guardia del lado cliente: antes de enviar, si el almacén de rate-limit reporta un backoff activo, la llamada falla localmente con `username_creation_rate_limit_error_code` y el texto "rate limit expiration time not reached" (found, `C122815Lj.A03`).

Manejo de éxito (`C122815Lj.A01`, found):

| Condición | Estado local escrito (`username_reservation_state`) |
|-----------|----------------------------------------------------|
| username null o vacío | `UNSET`, pref de clave limpiada |
| `reserved` era true | `RESERVED` |
| flag de activación | `ACTIVATED` |
| de otro modo | `ACTIVATED` si el estado era `ACTIVATED` y el nombre iguala el nombre almacenado, de otro modo `CREATED` |
| el int de `source` es 1 o 2 | pref `username_set_via_account_linking` = (int == 2) |
| `pin` enviado | pref `username_pin` actualizada |
| flag de adolescente | pref `is_teen_account` = true |

La escritura de la pref es `Voip.REJECT_REASON_DECLINED`, que es el string vacío `""` en este build (found).

Manejo de error (`C138725uA` case 2):

| Código estilo HTTP | Acción del cliente |
|----------------|---------------|
| 429, 503, 529 | backoff almacenado (5.3) |
| 304 | tratado como éxito ("not modified"), el estado local se actualiza igual |
| sin conexión (`C213639Bb`) | resultado `C4BO` "no network" |
| otro | `C4BN(code, message)` |

### 3.4 UsernameGet

Variables: ninguna (la llamada construye un conjunto de variables vacío, found, `C122815Lj.A02`). Marcado `@Deprecated`, reemplazado por una variante suspend.

Respuesta (found, `C138815uJ` case 34): `data.xwa2_username_get.username_info`

| Campo | Uso |
|-------|-----|
| `username` | almacenado; string vacío si ausente |
| `state` | `C4FC`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ACTIVE`, `RESERVED` |
| `pin` | **la clave se devuelve en claro y se almacena en la pref `username_pin`**; string vacío si ausente |

Mapeo de estado: `RESERVED` -> `C4DU.RESERVED`; `ACTIVE` -> `ACTIVATED` si el username almacenado iguala el devuelto y el estado local era `RESERVED` o `ACTIVATED`, de otro modo `CREATED`; estado null o `username_info` null -> `UNSET`.

El caso de error 404 del servidor limpia el username local, la clave y el estado (log `clearSelfUsernameData NOT_FOUND`).

Si la llamada se usa como heartbeat es unknown; la nota antigua "polling heartbeat" no está respaldada por el código de este build.

### 3.5 UsernamePinSet (clave de username)

Variables (found): `pin` (string), omitido cuando es null.

| Acción | Variables |
|--------|-----------|
| fijar clave | `{"pin": "<key>"}` |
| eliminar clave | `{}` (`A02` llama a `A00(null)`) |

El nombre de operación para ambos es `UsernamePinSet`; no existe una operación de verificación separada. La verificación de una clave ajena se hace en USync (4). No conectado: devuelve `C213639Bb("UsernamePinSet")` sin request.

La clave también puede viajar en `UsernameSet` (variable `pin`). `C81793ej.A0x` usa `UsernameSet` con el username existente y el nuevo `pin` cuando ya hay un username almacenado localmente (`A00 != null`), y `UsernamePinSet` de otro modo (found).

La clase de respuesta `C48557LJz` no tiene acceso de campo en los archivos leídos; la forma de respuesta es unknown.

---

## 4. Búsqueda de otros usuarios

### 4.1 USync clásico por username (flujo de clave)

Construido en `C18670m9.A06` (jadx falló en este método, leído de smali `X/0m9.smali`). Por entrada de request `C222649hm`: campo `A0C` = username, `A0D` = clave, `A05` = LID.

Atributos del hijo contact (found en smali): `username` siempre; `lid` cuando se conoce un LID localmente; `pin` cuando se fija una clave. Los atributos extra están controlados por el flag **12402** (por defecto `false`): cuando el flag está apagado, solo se escribe `username` (found). El nombre de nodo `contact` se infiere del parser de respuesta, que lee el hijo `contact` y su atributo `username` (`C18670m9` líneas ~969-975).

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

Punto de entrada: `C23638AId.A0G(username, key)` (`querySyncUsernameWithErrorInfo`), llamado por `submitPinForUsername`. Tipo de sync `EnumC21760rz.A0J`, timeout 32000 ms. El conjunto de atributos `contact`, `pin`, `username` está en los conjuntos de redacción de log de `AbstractC40921lc` (found).

Pre-resolución local: `A0M.Aol(username)` busca `lid_row_id` en la tabla `lid_display_name` donde `UPPER(username) = UPPER(?)`, fila más nueva primero (found, `C1S0`). El LID, si se conoce, va al atributo `lid`.

### 4.2 Evaluación de resultado (entrada de clave)

`UsernamePinEntryViewModel$submitPinForUsername$1` (found):

| Resultado | Condición |
|---------|---------|
| clave correcta | el resultado `UserJid` es un LID (`C14080dr`) |
| clave incorrecta | el resultado no tiene LID: log `[un-pin] incorrect PIN`, texto de error "Wrong key entered" |
| sin red | `C9qA` código 1 |
| error genérico de infra | `C9qA` código 2 |
| rate limit del solicitante | `C225769os.A01` true: "Too many attempts made. Try later." |
| rate limit del solicitado | `C225769os.A00` true: "This account can't be reached with their key right now..." |

El chequeo de rate-limit cacheado del lado cliente corre primero cuando el flag **16033** está activado y la config JSON **21995** tiene `enable_key_rate_limit` true (por defecto true): `C30P.A00` contra el propio LID y contra el username objetivo. Al username se le quita el `@` (`C0CX.A0i(username, '@')`).

Con éxito el resultado es un **LID**, el chat se dirige entonces al LID (inferido del chequeo `C14080dr`; el paso de apertura de chat no fue rastreado).

### 4.3 Obtener username de un LID conocido

`C23638AId` (línea ~600-650) construye un usync con `<list><user jid="LID"/></list><query><contact/><username/></query>`, modo/contexto desde `EnumC21760rz.A0J` (found). El parser lee `username` como un hijo del resultado de `<usync>` (`C18670m9` línea 586, solo cuando la request lo pidió).

### 4.4 USync MEX (`UsyncQuery`)

`C229259vZ.A01` construye `UsyncQuery` (doc_id arriba). Partes relevantes (found):

| Variable | Uso |
|----------|-----|
| `query_input[]` | una entrada por usuario: JID (`C493020r.A0C`), opcional `client_known_username` (solo cuando se pide el username y no está vacío) |
| `include_username` | bool, fijado cuando alguna entrada pide el username |
| `include_lid` | bool, pide `lid_info` |
| `telemetry.context` | contexto de USync en minúsculas |

Respuesta por usuario: `jid`, `username_info`, `lid_info` (`O0F`). `username_info` es polimórfico por hash de tipo: un tipo de valor que lleva `username`, o un tipo de estado con `status` de `EnumC216389Tz`: `EMPTY`, `NOT_ALLOWED`, `NO_CHANGE` (+ sin fijar). `NOT_ALLOWED` se registra como "username not allowed to be queried" y limpia el username almacenado; `NO_CHANGE` lo conserva. `lid_info.lid_jid` lleva el LID.

Compuerta: `ContactSyncHelper` rechaza la ruta MEX con el log "cantUseMex as username ab prop is off" a menos que el flag **8421** esté activado cuando se pide un username (found; por defecto `false`).

---

## 5. Validación, límites, errores

### 5.1 Formato de username (local)

Validador `C82003fB.A04` (found), chequeos en este orden:

| Orden | Chequeo | Id de error (`C02U`) | String de mensaje |
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

El case no se normaliza por el validador; la búsqueda local `Aol` compara con `UPPER()`, así que el emparejamiento es insensible a mayúsculas/minúsculas localmente (found). Si el servidor trata los nombres de forma insensible a mayúsculas/minúsculas es unknown. Un guion bajo inicial está permitido por la regex; el texto de la UI dice "comenzar con una letra", que es más estricto que la regex (found, discrepancia).

La UI también rechaza enlaces web: "Enter only your username, not a web link" (string presente, chequeo no rastreado).

### 5.2 Formato de la clave de username

`C1176550d.A00` (found): el flag **34350** es un string de regex, por defecto `^([0-9]{4}|[A-Z0-9]{6})$`. Si el string del flag está vacío, el fallback es exactamente cuatro dígitos. Una regex inválida registra `[un-pin] invalid username_key_regex` y acepta cualquier cosa. Los flags de límite de longitud **34347** (mín, 4) y **34348** (máx, 6) alimentan solo la ruta de mensaje de error en `UsernamePinEntryViewModel.A0w`. Las reglas del lado servidor son unknown.

Así que la nota antigua "PIN de 4 dígitos" está incompleta: el default de fábrica acepta cuatro dígitos o seis alfanuméricos en mayúsculas.

### 5.3 Rate limits y backoff

`C67942uO` (found), activo solo con el flag **28678** (por defecto `false`):

| Ítem | Valor |
|------|-------|
| disparador | `UsernameSet` error 429, 503 o 529 |
| duración | string estilo `Retry-After` parseado como int segundos (`C23680AJt.A00`), de otro modo flag **28127** (por defecto 30) segundos |
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

40601 a 40603 están en el conjunto permitido `AbstractC111104pH.A01` (solo 40603 visible en el código leído). Su semántica del lado servidor es unknown más allá del texto del cliente.

---

## 6. Relación con LID

Todo found salvo que se indique.

| Hecho | Evidencia |
|------|----------|
| Las búsquedas de username resuelven a un **LID**, no a un JID de teléfono | prueba de éxito de clave `userJid instanceof C14080dr` (clase LID); `lid_info.lid_jid` en usync MEX |
| Mapa local username -> LID | tabla `lid_display_name` (columnas `username`, `lid_row_id`), query en `C1S0` |
| Las notificaciones identifican al usuario por LID | los manejadores de fijar/eliminar parsean `LidUserJid` (texto de error "Failed to parse LidUserJid") |
| La notificación de eliminación puede llevar un JID de teléfono | el manejador verifica `isPnPresent`; con PN presente castea un JID de PN y actúa, sin PN retorna |
| Acción de sincronización de contacto | `ContactAction` tiene `username` (6) junto a `lid_jid` (3), `pn_jid` (5); también `LidContactAction` (`lid_contact`, campo 61 de SyncActionValue) |
| Modo de inicio de chat | campo **59** de SyncActionValue `username_chat_start_mode`, enum `EnumC50053M6w`: `LID` = 1, `PN` = 2. Solo se encontró el codec de sync; ningún consumidor en código de UI (unknown) |
| String de función de companion | al vincular un companion el primario añade `username_supported` (flag 4745 o 20189), `username_reservation_only_mode` (solo 20189), `username_account_linking_enabled` (flag 21199) a su lista de funciones (`C25056AqU`) |

Inferred: un usuario que existe solo como username es alcanzable solo a través del LID hasta que el dueño comparta el número de teléfono; los strings "Si continúas, tu número de teléfono se mostrará en los chats y llamadas de username existentes" (diálogo de eliminación) respaldan esto pero la ruta de exposición de PN no fue rastreada.

---

## 7. Notificaciones

Los manejadores extienden `AbstractC23194A0r` y se registran en `AbstractC20380p4` (found):

| Notificación | Manejador | Comportamiento |
|--------------|---------|-----------|
| `UsernameSetNotification` | `C49822Lvi` | payload `xwa2_notify_username_on_change`: lee LID (hash de campo 107143) y username; almacena vía `InterfaceC11470Yz.BNU(lid, username)`; si el contacto existe y es del tipo correspondiente, refresca el contacto (`C12440bB.A0W`) |
| `UsernameDeleteNotification` | `C49821Lvh` | payload `xwa2_notify_username_delete`: lee LID y PN (hash -983979708); con PN presente ejecuta la actualización de eliminación (`C53594Nzh`) |
| `UsernameUpdateNotification` | anónimo `X.2YG` | lee un hash en base64 del payload, construye una request USync con razón `USERNAME_UPDATE_NOTIFICATION` y `EnumC21760rz.A0Q` (contexto `NOTIFICATION_SIDELIST`, modo `query`; ver WA_USYNC.md), log `usync triggered for hash` |

Texto mostrado al usuario: "Your username has changed", "WhatsApp has assigned you a new username (%1$s)", es decir, el servidor puede reasignar un username (revocación, pref `is_username_revoked`, `revocation_banner_dismissed_<username>`).

---

## 8. Feature flags

Los IDs de flag son ids de AB-prop leídos a través de `C08J` (defaults de las tablas `C08J`). Todos los defaults abajo se leyeron de este build.

| Flag | Tipo | Default | Controla |
|------|------|---------|----------|
| **4745** | bool | false | primario: creación de username (modo `CREATION`); también anunciado como `username_supported` |
| **20189** | bool | false | primario: modo solo-reserva (`RESERVATION`); `username_supported` |
| **23817** | bool | false | companion: funciones de username en absoluto (de otro modo `DISABLED`) |
| **21199** | bool | false | vinculación de cuenta (FB / IG) activada, anunciada como `username_account_linking_enabled` |
| **16033** | bool | false | compuerta maestra para funciones de clave (`C79343Xx.A00`): rate limit de clave, upsell de clave, vista de username WABI |
| **21995** | JSON | `{}` | `enable_key_rate_limit`, `enable_key_upsell_flows`, `enable_wabi_username_view` (todos por defecto true cuando la clave JSON está ausente) |
| **8421** | bool | false | permite `UsyncQuery` MEX para requests de username |
| **12402** | bool | false | añade atributos `lid` y `pin` al nodo `contact` de usync |
| **20494** / **20459** | int | 3 / 35 | longitud mín / máx de username |
| **34350** | string | `^([0-9]{4}\|[A-Z0-9]{6})$` | regex de clave |
| **34347** / **34348** | int | 4 / 6 | límites de longitud de clave (mensaje de error) |
| **28678** | bool | false | activa el almacén de backoff de rate-limit |
| **28127** | int | 30 | segundos de backoff por defecto |
| **29327** | int | 60 | retraso antes del segundo lote de `UsernameCheckMulti` |

Elegibilidad de companion (`C224069kP.A00`, lectura a nivel de bytecode):

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

Las tres prefs `*_on_primary` solo se leen aquí; dónde se escriben no fue encontrado (unknown).

---

## 9. Privacidad y visibilidad

| Aspecto | Hallazgo | Nivel |
|--------|---------|------|
| Propósito | "Keep your phone number private with a username"; las personas que no tienen el número guardado ven el username en su lugar | found (strings) |
| Primer contacto | con una clave fijada, las personas "con las que no has interactuado" deben ingresar la clave antes de contactar el username | found (strings) |
| Compartir clave | la acción de compartir username puede incluir la clave (pref `username_share_include_pin`, migrada en `C138535tr`); strings "Share your username and key" | found |
| Dónde se oculta el número | los admins de comunidad y de canal ven el número a menos que se fije un username; los seguidores de canal no ven ninguno | found (strings) |
| Telemetría de grupo/hilo | campos `has_username`, `has_username_pin`, `is_username_thread` en la telemetría de envío de mensaje (`DZ1`, `RQG`) | found |
| Clave en reposo | la propia clave es devuelta por `UsernameGet` y almacenada en prefs planas `username_pin` | found |
| Chats de terceros | "Usernames and contacts added to third-party chats will not save to your phone" | found (string) |
| Business | "This username is only available on WhatsApp Business" aparece como texto de rechazo | found (string) |
| Quién puede consultar | el estado de usync MEX `NOT_ALLOWED` muestra que el servidor puede rechazar la divulgación del username por solicitante | found (enum), regla unknown |
| Menores | pref `is_teen_account`; textos para padres "Your child created the username ..." | found |

Las reglas de visibilidad aplicadas por el servidor (quién puede resolver un username, rate limits de clave, reasignación) son unknown desde el cliente.

### 9a. Controles de audiencia de compartir número de teléfono (nuevo en 2.26.45.10, found)

Un paquete separado `com.whatsapp.pnsharing` controla quién puede ver el número de teléfono de la cuenta, independiente de las propias reglas de visibilidad del username en 9. Dos nuevas operaciones de `whatsapp-android-mex`, ambas `found` a partir de literales `const-string` planos en smali (sin necesidad de decompile, `PnSharingAudienceUpdater.smali` / `PnSharingListFetcher.smali` / `PnSharingListUpdater.smali`):

| Operación | doc_id | Tipo |
|-----------|--------|------|
| `UsernamePhoneNumberPrivacyUpdateMutation` | `28835748819379698` | mutation |
| `UsernamePhoneNumberPrivacyGetQuery` | `29264643203229836` | query |

El ajuste de audiencia es uno de 4 valores del enum compartido, no específico de pnsharing, `LX/BWW` (13 miembros en total, solo estos 4 alcanzables desde esta ruta de llamada):

| ordinal | miembro de `LX/BWW` | valor de `setting` |
|---|---|---|
| 0 | `A02` | `ALL` |
| 1 | `A07` | `MYCONTACTS` |
| 2 | `A08` | `MYCONTACTSEXCEPT` |
| 3 | `A09` | `NONE` |

**`UsernamePhoneNumberPrivacyUpdateMutation` es incremental, no de reemplazo completo.** Dos call sites la alimentan:

- `PnSharingAudienceUpdater.A00` — solo cambio de ajuste de nivel superior, sin entradas de lista.
- `PnSharingListUpdater.A01` — añadir/eliminar por entrada contra una de las tres listas de audiencia.

Campos de nivel superior (found):

| Campo | Tipo | Significado |
|-------|------|---------|
| `setting` | string | `ALL` / `MYCONTACTS` / `MYCONTACTSEXCEPT` / `NONE`, ver tabla arriba |
| `input` | objeto | payload anidado, ver abajo |

Campos de `input` (found, anidados bajo `allow_list` / `contact_exclude_list` / `deny_list` dependiendo de cuál de los 3 ajustes no-`MYCONTACTS` está activo — `MYCONTACTS` no envía ninguna clave de lista):

| Campo | Tipo | Significado |
|-------|------|---------|
| `dhash` | string | hash de contenido de la lista de audiencia, usado para invalidación de caché / detección de conflicto (string de log "...changed since it was read" junto a él) |
| `entries` | lista de objetos | entradas incrementales ADD/DEL, no un reemplazo de lista completo |

Campos del ítem `entries[]` (found, construidos por `PnSharingListUpdater.A00(Integer, Integer)`):

| Campo | Tipo | Significado |
|-------|------|---------|
| `entry_type` | string | `USER` o `GROUP` |
| `operation` | string | `ADD` o `DEL` |
| `group_jid` | string, nullable | fijado solo cuando `entry_type=GROUP` |
| `pn_jid` | string, nullable | fijado cuando la entrada es un número de teléfono plano (`PhoneUserJid`) |
| `user_jid` | string, nullable | fijado cuando la entrada es un `Jid` de contacto resuelto |
| `username` | string, nullable | el campo existe en el schema pero ningún call site observado lo pobla; propósito `inferred`: emparejar un número de teléfono que aún no es contacto con un nombre visible, consistente con excepciones estilo `UsernameSet` — `unknown` si algún llamante realmente lo fija |

Exactamente uno de `group_jid` / `pn_jid` / `user_jid` se llena por entrada (found); los otros dos se quedan null.

`UsernamePhoneNumberPrivacyGetQuery` es la contraparte del lado lectura (found, `PnSharingListFetcher.smali`): un único round trip en lote que obtiene las 3 listas de audiencia a la vez, cada una indexada por su propio `dhash` (hash cacheado localmente, o el string literal `"none"` si ausente) para validación de caché.

**doc_id no resuelto:** el catálogo de persisted-query también lista `PnSharingPhoneNumberFetch` (doc_id `29229648029980096`, tipo query). Un grep sobre todo el árbol smali decodificado de 2.26.45.10 (todos los shards, no solo `com/whatsapp/pnsharing/`) para este literal no arroja ningún call site — solo el asset enviado `whatsapp-android-mex_client_persist_ids.json` lo referencia. Qué lo llama y qué envía son **unknown**. Candidato probable solo por nombre (**inferred**, no más): un fetch de visibilidad de número de teléfono por contacto/por grupo, es decir, la contraparte de un solo ítem de la query de 3 listas en lote de arriba — no confirmado.

---

## 10. Notas de Baileys

El envelope en 2.2 es genérico; un cliente Baileys puede construirlo. Esto es **inferred**, no probado aquí.

```ts
const variables = { username: 'name', include_suggestions: false, source: 'USER_INPUT', session_id: uuid }
await sock.query({
  tag: 'iq',
  attrs: { to: 's.whatsapp.net', type: 'get', xmlns: 'w:mex' },
  content: [{ tag: 'query', attrs: { query_id: '26124072630599518' },
    content: Buffer.from(JSON.stringify({ queryId: '26124072630599518', variables })) }]
})
```

| Riesgo | Razón |
|------|--------|
| Deriva de doc_id | los ids pertenecen al asset de este build; otros builds pueden diferir (unknown) |
| `session_id` | el código lo envía cuando está presente; si el servidor requiere el mismo valor para verificar y fijar es unknown |
| atributos de clave | `lid` / `pin` en `contact` están detrás del flag 12402; el servidor puede ignorarlos para clientes sin el flag (unknown) |
| reglas locales | las reglas de longitud, charset y punto son del lado cliente; las reglas del servidor son unknown |

---

## 11. Distinciones clave

| No confundir | Diferencia |
|----------------|------------|
| Clave de username vs PIN de cuenta / 2FA | La clave de username (`pin` en `UsernamePinSet`, pref `username_pin`) controla el primer contacto vía username. No está relacionada con el 2FA de registro |
| Variable `reserved` vs `UsernamePinSet` | `reserved` pertenece a `UsernameSet` y marca una reserva; la clave tiene su propia op |
| Estado `RESERVED` | el local `C4DU.RESERVED` / servidor `state=RESERVED` es un nombre retenido aún no usable; `ACTIVATED` y `CREATED` son usables |
| Eliminar | no existe ninguna op de eliminación; `UsernameSet` sin `username` elimina; la eliminación de clave es `UsernamePinSet` con `{}` |
| Resultado de verificación `INVALID` | cubre tomado, vinculación-requerida y problemas de formato; el detalle está en `rejection_reasons` |
| Username vs LID | el username es un handle; la identidad de direccionamiento es el LID |
| Ints de `source` | 1 `FB`, 2 `IG`, 3 `USER_INPUT`, 4 `SUGGESTION`; no son los mismos ints que los ids de error de `C02U` |
| doc_id vs `client_doc_id` | ambos están en el asset; los ids capturados igualan a `doc_id` |
| Notificaciones vs ops | los tres tipos `Username*Notification` son manejadores de push, no requests |
| Etiquetas entre repositorios | `25975613018777537` está ausente del asset de persist-id de este build; `25741205615468935` es `GetTextStatusList` en este build. Ninguna de las dos es una operación de username aquí |

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

## 13. Incógnitas

| Tema | Razón |
|-------|--------|
| Accesor exacto que alimenta `query_id` | consumidor de `doc_id` vs `client_doc_id` no rastreado hasta el constructor del IQ |
| Forma de respuesta de `UsernamePinSet`, `UsernameSet` | las clases de respuesta no tienen acceso de campo en el código leído |
| `UsernameGetRecommendationsQuery` | sin call site, sin variables |
| Reglas de username y clave del lado servidor | el cliente solo valida localmente |
| Significado de 40601-40603 en el servidor | solo se encontraron strings del cliente |
| Origen de las prefs `*_on_primary` | no se encontró ningún escritor |
| Efecto de `username_chat_start_mode` | no se encontró ningún consumidor |
| Patrón de uso de `UsernameGet` (heartbeat) | no respaldado por el código leído |
| Paso de apertura de chat tras una clave correcta | no rastreado más allá del chequeo de LID |
| Tráfico real | solo análisis estático |
