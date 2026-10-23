<!-- src-sha1: 4762669c756eee4725aaf5af56633f2b59edd479 -->
# WhatsApp AB Props — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** AB props / feature flags en Android: ids numéricos de flag y tablas de valores por defecto tipadas, lectores tipados y opciones de lectura, capa MobileConfig (Stable IDs, tipos de unidad, `params_map_v4_u*`, `MetaConfigFetchMutation`), IQ de sincronización de props (`xmlns="abt"`: hash, refresh, refresh_id, delta, expo keys, pesos de muestreo), props a nivel de grupo, props previas al registro, experimentos en el dispositivo (offline), almacenamiento en el dispositivo, registro de exposición, rutas de override y depuración, relación con los ids de flag citados en otros reportes, catálogo de flags por área, comparación con Baileys

---

## 1. Qué es (técnicamente)

Las AB props son los feature flags del cliente controlados por el servidor. Cada flag se identifica únicamente por un **config code** numérico (p. ej. `20548`); en el APK no existe ningún nombre de flag. El cliente incluye una tabla de valores por defecto tipada por cada código, pide al servidor los overrides mediante un IQ, guarda la respuesta en SharedPreferences y la lee a través de una única clase lectora abstracta. Una segunda capa derivada de Meta (MobileConfig) corre en paralelo y puede convertirse en la fuente de verdad. Todas las afirmaciones provienen del análisis estático del APK descompilado; no se capturó nada en la red. Niveles: **found** = leído en código o datos, **inferred** = deducido, **unknown** = no resuelto. Los nombres ofuscados son específicos de cada build y se volvieron a resolver en 2.26.41.6.

| Capa | Nombre en 2.26.41.6 | Función |
|------|----------------|------|
| Base del lector | `C00D` (abstract) | accesores tipados, cachés, exposición, interruptor de MobileConfig |
| Almacén principal | `C08J` (`extends C00D`, prefs `ab-props`) | contiene los cinco mapas de valores por defecto, lee todos los flags normales |
| Almacén pre-chatd | `C0D9` (prefs `ab-prechatd-props`) | flags obtenidos por HTTP antes de que la cuenta esté conectada |
| Almacén privado | `C0ER` (prefs `ab-private-abprop`) | valores de experimentos en el dispositivo, mismos defaults que `C08J` |
| Opciones de lectura | `C00F` (`AbPropsOptions`) | modo de exposición + fijado del primer acceso |
| Descriptores tipados | `C054909t` ABPropBoolean, `C055109v` ABPropInt, `C1OT` ABPropFloat, `C055009u` ABPropString, `C055209w` ABPropJson | id + default en el punto de llamada |
| Gestor de sincronización | `C0D2` (`ABPropsManager`) | almacenamiento, hash, refresh, backup, actualización pre-chatd |
| Solicitud / respuesta | `C27646BzW` (solicitud), `C28894Cgv` (respuesta + error) | `<iq xmlns="abt">` |
| Disparador | rama default de `RunnableC48591z1` (log `MessageHandler/maybeGetNewAbProps`), `C1S0` handler de `<... abprops/>` | cuándo se envía una consulta |
| Props de grupo | `C41861nA` (`GroupAbPropsManager`), `C502324k` (disparador), `C28900Ch1` (respuesta) | valores por grupo |
| MobileConfig | `C053409d` (factory), `C054709r` (`InterfaceC054609q`), `C06510El` (tabla de Stable IDs), `C34081Wt` / `C34091Wu` (lambdas tipadas), `C06460Eg`, `C053809h` (tabla de overrides), `CQN` + `C29448CqB` (fetcher), `C41251mA` (coordinador de fetch) | motor con soporte nativo, fetch por MEX |
| Exposición | `C42831om`, `BxP`, `C27952CBv`, evento WAM `C44051qo` (5504) | claves de exposición |
| AB offline | `C24976ApB`, `C27629BzE`, `C60839RQl`, `ON0` / `ON1` / `C53973OMy`, `ConfigVariable` | asignación local de experimentos |
| Observadores | `C0NE` (3 callbacks), 46 implementadores, p. ej. `CY8` | reaccionan a valores modificados |

Puntos decisivos:

- El espacio de ids de flag es un único espacio numérico (id máximo **39140**, 21.424 ids con default). `C05Z.A00(n)`, `C1XG.A0I(n)`, los enteros de tipo de IQ y los ids de WAM son espacios numéricos distintos (sección 12).
- Los nombres nunca llegan al cliente. Ni en las tablas de defaults, ni en la respuesta de sincronización (solo `config_code`), ni en un recurso.
- Existen tres rutas de sincronización paralelas: el IQ `abt` (nivel de usuario), el IQ `abt` con `group=` (nivel de grupo) y el fetch MEX de MobileConfig (sección 4).

---

## 2. Modelo de flags

### 2.1 Tipos y tablas de defaults (found, `C08J`)

Cinco mapas inmutables se construyen en el constructor de `C08J` (`buildKeepingLast`, por lo que los puts duplicados en la descompilación son inocuos). Los conteos son ids únicos por mapa:

| Tipo | Mapa | Accesores en `C00D` | Ids | Ejemplo |
|------|-----|---------------------|-----|---------|
| bool | `A1A()` | `A15(id)`, `A18(ABPropBoolean)`, `A0E(...)` | 16.668 (1.237 con default `true`) | `9667` true |
| int | `A1C()` | `A0b(id)`, `A0f(ABPropInt)`, `A02(...)` | 3.530 | `996` 604800 |
| float | `A1B()` | `A0Z(id)`, `A0a(ABPropFloat)`, `A00(...)` | 177 | `31535` 0.0 |
| string | `A1E()` | `A0j(id)`, `A0n(ABPropString)`, `A08(...)` | 867 | `34350` regex |
| JSON | `A1D()` | `A0p(id)`, `A0r(ABPropJson)`, `A09(...)` | 182 | `21995` `{}` |

Ningún id está en dos mapas. Lecturas con literal estático (`A15(n)`, `A0b(n)`, `A0j(n)`, `A0Z(n)`, `A0p(n)`): 16.355 puntos de llamada en `p000X` y `com`; las lecturas mediante descriptor se suman a esa cifra (sitios de construcción: 492 ABPropBoolean, 482 de ellos distintos, 259 ABPropInt, 30 ABPropFloat, 66 ABPropString, 12 ABPropJson).

Resolución del default (found, `C00D.A0D`, `A01`):

| Paso | Regla |
|------|------|
| 1 | valor en caché en memoria para este proceso |
| 2 | valor del servidor almacenado en prefs `ab-props` bajo la clave `String.valueOf(id)` |
| 3 | default del mapa del tipo del id |
| 4 | default en el punto de llamada de un descriptor ABPropX (solo cuando el mapa no tiene entrada) |
| 5 | ninguno: `IllegalArgumentException("Unknown BooleanField: <id>")` (int: `Unknown IntField`) |

Para los 482 descriptores ABPropBoolean distintos, el id existe en el mapa y el default de producción del descriptor es igual al default del mapa. `debugDefaultValue` de ABPropBoolean difiere del default de producción en 182 de ellos, pero no se lee en ningún lugar salvo en `equals` / `hashCode` / `toString` (smali: el campo `A02` se referencia solo dentro de `09t`; los accesores usan únicamente el id y el default de producción). No tiene efecto en tiempo de ejecución en este build.

### 2.2 Parseo del valor al almacenar (found, `C0D2.A00`)

| Mapa del id | Almacenado como | Parseo |
|---------------|-----------|-------|
| bool | `putBoolean` | `Integer.parseInt(config_value) != 0` (forma en el wire `"1"` / `"0"`) |
| int | `putInt` | `Integer.parseInt` |
| float | `putFloat` | `Float.parseFloat` |
| string | `putString` | tal cual |
| JSON | `putString` | validado con `new JSONObject(...)`; si falla, registra `ABPropsManager/invalid format for config; configCode=...` y la prop no se almacena |
| id en ningún mapa | `putString` | almacenado como string; una lectura tipada de dicho id no tiene default y lanza excepción (2.1 paso 5) |

A diferencia de la tabla de WA Web (los códigos desconocidos se descartan), Android conserva los códigos desconocidos como strings (found).

### 2.3 Opciones de lectura (found, `C00F` = `AbPropsOptions`)

| Constante | exposureOptions | firstAccessValue | Uso |
|----------|-----------------|------------------|---------|
| `A03` | WITH_EXPOSURE_LOGGING (1) | false | default para todas las lecturas simples (`A15`, `A0b`, ...) |
| `A02` | WITH_EXPOSURE_LOGGING | true | `A19(...)`, `A16`, lecturas de arranque de MobileConfig |
| `A06` / `A05` | WITHOUT_EXPOSURE_LOGGING (0) | false / true | `A00()` las deriva |
| `A04` | WITH_URGENT_EXPOSURE_LOGGING (2) | false | almacén pre-chatd cuando el flag **24317** está activo |

`firstAccessValue = true` fija el primer valor leído en el proceso en `C00D.A07` (ConcurrentHashMap); las lecturas posteriores de ese id devuelven el valor fijado incluso después de una sincronización (found, `C00D.A0D`, `A0i`). Las lecturas simples usan la caché `A0P`, que `A0s()` vacía después de cada sincronización.

### 2.4 Ruta de lectura y fuente de verdad (found, `C00D.A07` smali; nombres de los interruptores inferidos por su uso)

```
read(id)
  ├─ A14() true  (A0E && A0b && !A0S)  and A08 set  and MobileConfig context present
  │      └─► MobileConfig value via C34081Wt/C34091Wu  (Stable ID lookup, C054709r.B6F)
  └─ else
         ├─ legacy value: cache A0P ► prefs "ab-props" ► default map
         └─ if A0E && A0G (shadow): also read MobileConfig and compare (A0C)
```

| Campo | Fuente | Significado (inferred) |
|-------|--------|--------------------|
| `A0F` | pref `23048` (bool), solo `C08J` | MobileConfig inicializado para esta cuenta |
| `A0E` | `A0F` o pref `27668` (int) > 0 | MobileConfig activo (solo `C08J`; false para `C0D9`, `C0ER`) |
| `A0b` | pref `24896` | MobileConfig es la fuente de verdad |
| `A0S` | pref `25403`, releída en `A0s()` | override de vuelta a la ruta legacy |
| `A0G` | pref `22646` | comparación shadow activada |
| `A0c` | pref `38895` == 1 | caché por lectura `A0d` para valores de MobileConfig |
| `A08` | AtomicBoolean, establecido en `C054709r.BN4` (init de MobileConfig) | MobileConfig listo; solo entonces se toma la ruta de MobileConfig (found); se restablece a false en el constructor |

Los seis son AB props en sí mismos, leídos directamente del archivo de prefs en la construcción (found). El modo shadow construye un registro de comparación `N25` y envía un evento de field-stats (`C56612Vl`, valor `mobile_config_inconsistent_value`) muestreado 1 de cada flag **22647** (default 10) (found). Cuando MobileConfig es la fuente y un id no tiene Stable ID, la lambda tipada devuelve `false` / `0` / `""` con fuente de valor `INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`, no el valor del mapa de defaults (found en `C34081Wt`; efecto sobre los 70 ids solo con default inferred).

---

## 3. Capa MobileConfig

### 3.1 Stable IDs (found, `C06510El.A0J`)

`long[39141]` indexado por config code, 21.380 entradas distintas de cero. `C054709r.B6F(id)` devuelve la entrada (0 = ninguna). 21.354 ids existen tanto en los mapas de defaults como en esta tabla; 70 ids solo tienen default, 26 solo tienen Stable ID.

| Bits | Campo | Evidencia |
|------|-------|----------|
| 0-15 | índice de slot | `C053809h.A00`: `j & 65535`; significado inferred |
| 32-47 | índice de config, `0..20780`, uno por entrada en orden de id | `C06460Eg.A00`: `(j >>> 32) & 65535`, `C053409d.A08(int)` |
| 48-53 | tipo de valor: 1 bool, 2 int, 3 string o JSON, 4 float | tabulación cruzada contra los mapas de defaults, sin excepciones |
| 54-59 | tipo de unidad: 1 SESSIONLESS (564 ids), 2 SESSIONBASED (20.781), 6 GROUP (35) | tabulación cruzada; sección 3.2 |
| 60-63 | valor `2` si y solo si el default bool es `true` | 1.231 de 1.231 ids; 6 ids con default true no tienen Stable ID |

### 3.2 Tipos de unidad y `params_map_v4_u*` (found)

`assets/params_map_v4_u<N>.txt` lo carga `N3E` con `N` = tipo de unidad de MobileConfig (`AbstractC24817AmY.A00`): 0 NULL_VALUE, 1 SESSIONLESS, 2 SESSIONBASED, 3 PAGEID, 4 ADMINID, 6 GROUP, 7 FAMILY_DEVICE_ID, 8 FRLID, 9 AD_ACCOUNT_ID, 10 WEARABLE_DEVICE_OWNER_ID. El sufijo es el tipo de unidad, no un ancho de valor. La librería nativa contiene el mismo string de formato `params_map_v4_u%d.txt` (`libmobileconfig-jni.so`).

| Archivo | Unidad | Entradas | Clave de versión | Ids dentro del rango de códigos de WA |
|------|------|---------|-------------|------------------------------|
| `u1` | SESSIONLESS (utilizable antes del login) | 575 | 565 | 564 |
| `u2` | SESSIONBASED | 20.844 | 20785 | 20.781 |
| `u4` | ADMINID | 72 | 2 | 0 (ids 112607..121623) |
| `u6` | GROUP | 35 | 35 | 35 |

Entrada (8 bytes, dos u32 little-endian, disposición de la cabecera según el archivo: magic `v4`, comprobación `0x7fff`, clave de versión, conteo, hash de 32 caracteres):

| Campo | Hallazgo |
|-------|---------|
| `int2 >> 12` | el config code de WA: para `u1`/`u2`/`u6` coincide con la tabla de Stable IDs (564 / 20.781 / 35 coincidencias) y con los mapas de defaults; los 12 bits bajos son 0 salvo en unas pocas entradas |
| `int1` 16 bits bajos | máscara de tipo de valor: `0x881` bool, `0x1001` int, `0x1801` string/JSON, `0x2001` float (`u2`); el bit 15 está activo exactamente para los defaults bool `true` (25 + 1.206 = 1.231) |
| `int1 >> 16` | número de slot correlativo (inferred) |
| ids de `u4` | fuera del rango de códigos de WA; propósito desconocido |

Los 9 bits bajos de `int1` son solo 1 o 129; no son un id de parámetro.

Los 35 ids GROUP (found): 18205, 23245, 23246, 23397, 23398, 24075, 26013, 26269, 26270, 26862, 27009, 27025, 27247, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 33673, 34075, 34277, 34333, 35211, 35227, 35639, 35772, 36156, 36504, 36505, 37523, 37524, 38082, 38083. El flag **18205** lo lee `GroupAbPropsManager` por grupo (sección 4.7).

### 3.3 Fetch de MobileConfig por MEX (found, `CQN`, `C29448CqB`)

Mutación MEX `MetaConfigFetchMutation`, schema `whatsapp-android-www`, doc_id **28207206725568030**, campo raíz `xwa2_mobile_config_fetch`. Campos de entrada establecidos en `CQN`: `api_version`, `fetch_type`, `unit_type`, `unit_id`, `device_id`, `query_hash`, `query_string`, `bln_queries`, `mc_debug_id`, `mobile_app_universe_type`; siempre nulos en las rutas leídas: `batch_size`, `bln_li_hashes`, `bool_opt_policy`, `contact_point`. Log: `WAMobileConfigFetcher/fetchWwwConfigs/request unit_type=...`. Respuesta: un blob de configuración entregado al gestor nativo (`onComplete(true, blob)`), más `ep_refresh_id` y `ab_key`. `ab_key` se almacena como `mc_expo:sys:ab_key`.

`C41251mA` (`MobileConfigFetchCoordinatorImpl`) decide cuándo se ejecuta este fetch tras un fetch de AB props: ABPropInt **36185** (default 0) selecciona la opción: el valor 2 espera a la reanudación offline (`waiting for offline resume`), cualquier otro valor hace el fetch de inmediato; el valor 1 compara una versión de fetch almacenada por unidad con la versión de `abprops` (`C054709r.A01`), una solicitud delta compara la versión de la app del último handle con `2.26.41.6`. `C054709r.CpO` llama a `updateConfigs`, log del callback `WAMobileConfigFetcher/updateConfigs() callback: succeeded=`; el éxito almacena `last_full_fetch_ms:<unit>:<key>`.

El stanza `<success>` del login también lleva `mc_ep_version` (versión de emergency-push de MobileConfig) junto a `props` y `abprops` (found, `HandlerThreadC12340b0`); consumidor no trazado.

---

## 4. Sincronización de props

### 4.1 Solicitud (found, `C27646BzW.A00(boolean force, boolean delta, int refreshId)`)

```xml
<iq to="s.whatsapp.net" type="get" id="..." xmlns="abt">
  <props protocol="1" hash="<stored config_hash | empty>" [refresh_id="<last_version>"]/>
</iq>
```

| Atributo | Regla |
|-----------|------|
| `protocol` | constante `1` |
| `hash` | `ab_props:sys:config_hash` almacenado; string vacío cuando `force` o `delta` está activo, o no hay nada almacenado |
| `refresh_id` | solo cuando `delta` está activo y `refreshId > 0`; valor = `ab_props:sys:last_version` almacenado |
| envío | `MessageClient.A0W(callback, node, id, 220, 32000L)`: entero de tipo de solicitud IQ 220, timeout 32.000 ms |

### 4.2 Respuesta (found, `C28894Cgv.CFS`)

```xml
<iq type="result"><props ab_key="..." hash="..." refresh="86400" refresh_id="N" [delta_update="true"]>
  <prop config_code="20548" config_value="1" config_expo_key="..."/>     <!-- one per changed flag -->
  <prop event_code="1094" sampling_weight="N"/>                         <!-- event sampling, no config_code -->
</props><erid>...</erid></iq>
```

| Elemento | Manejo |
|------|----------|
| `config_code` + `config_value` | almacén tipado según 2.2, con clave `String.valueOf(code)` |
| `config_expo_key` | almacenado como `<code>_expo_key` cuando no está vacío y el valor fue almacenado (clave de exposición del experimento / grupo en el que está la cuenta; formato de la clave desconocido) |
| `ab_key` | almacenado `ab_props:sys:config_key`; establecido como atributo WAM **4473** (ambos canales) cuando MobileConfig no es la fuente |
| `hash` | hash de contenido de todo el conjunto; almacenado `ab_props:sys:config_hash`; una respuesta sin hash y sin `delta_update` no cambia ningún valor |
| `refresh` | segundos, default 86400; almacenado x 1000 ms en `ab_props:sys:refresh`, mínimo 600.000 ms; no se actualiza con un delta |
| `refresh_id` | versión del conjunto; almacenado `ab_props:sys:last_version` (también tras un delta) |
| `delta_update="true"` | se fusiona con los prefs existentes; hash, key, refresh y `last_refresh_time` no se tocan |
| hash presente | prefs anteriores copiados a `ab-props-backup` (se vacía primero) |
| actualización completa (hash presente, no delta) | almacén vaciado (conservando `refresh` y `last_exposure_keys`), se escriben todas las props |
| `event_code` + `sampling_weight` | filas sin `config_code`; reescritas en prefs `field-stats-events-sampling` (clave = código de evento, valor = peso); el código **1094** también establece `app_launch_event_sampling_weight` |
| `<erid>` | rid cifrado: con el flag **3664** activo se borra, con **6084** activo y un valor cambiado se almacena como `encrypted_rid` |

Tras una actualización completa exitosa: `last_refresh_time` = ahora (ms), `fetch_app_version` = `2.26.41.6`, contadores de error restablecidos, observadores notificados (4.8).

### 4.3 Disparadores (found salvo indicación)

| Disparador | Condición |
|---------|-----------|
| login `<success abprops="N">` (también `props`, `mc_ep_version`) | versión `N` > `last_version` almacenado: solicitud con `force` + `delta` + `refresh_id`; modo DELTA (log `versionMismatch`) |
| misma ruta | `last_refresh_time + refresh < now`, o `now < last_refresh_time` (reloj retrasado; rama leída en smali, la descompilación omite el else): solicitud normal con el hash almacenado; modo FULL (log `AB Props too old`) |
| hijo entrante `<... abprops/>` (enrutado junto con los hijos `log` y `push-config`; padre `ib` inferred) | `forceFetchABPropsAndMobileConfig`: `A00(true, false, 0)` (hash vacío, completo) cuando el envío de mensajes está listo; luego MobileConfig `BMu` + `CpO` |
| registro | fetch pre-chatd (4.6); asignación offline (6) |

### 4.4 Intervalo de refresh y errores (found)

| Elemento | Valor |
|------|-------|
| intervalo por defecto | `ab_props:sys:refresh` default 86.400.000 ms |
| `refresh` del servidor | segundos, x 1000, mínimo 600.000 ms |
| códigos de error contabilizados | 207, 304, 400-503 (`C28894Cgv.Brt`); otros códigos solo registran `unknown error code` |
| contabilidad de reintentos | `fetch_attemp_count` +1 por error; al llegar a 3 `last_refresh_time` = ahora y el contador se restablece, por lo que el siguiente intento espera un intervalo |
| último error | `ab_props:sys:last_error_code`, borrado en caso de éxito |
| fallo de entrega (`Bog`) | no-op |

### 4.5 Lecturas durante la ventana de fetch

`<props>` puede llegar después de que las primeras pantallas lean flags. La primera lectura de un id antes de que existan datos usa el default; con el fijado de `firstAccessValue` (2.3) el default fijado permanece durante el proceso (found); las pantallas de registro esperan con un timeout a las props online (strings de log `RegisterPhoneViewModel/cancelOnlineAbPropsTimeout`, `OnlineAbpropsAsyncStatus`, found; espera exacta desconocida).

### 4.6 Props pre-chatd (found, `C44707Jfc`, `C43414Iwr`, `K49`, `C0D2.A08`)

Antes de que la cuenta esté conectada, el cliente HTTP de registro llama a `checkPreChatdABProps` (`reg-onboard-abprop-request`) con `ab_hash` (pref `pref_pre_chatd_ab_hash`). El resultado lleva un nuevo hash, un array JSON `expConfigs` de `{config_code, config_value, config_expo_key}`, un `ab_key` y un retardo hasta el siguiente fetch (`pref_pre_chatd_ab_next_fetch_time` = ahora + retardo). `C0D2.A08` vacía el almacén pre-chatd (`A04`) y lo reescribe con las mismas reglas de tipado (2.2) en prefs `ab-prechatd-props`. La exposición se conserva en `pref_expo_keys` (array JSON de `<expo_key>,<timestamp>`) y se envía a través del log de embudo de registro (`abprop_exposure` / `ab_prechatd_exposure`, con `ab_key` de `pref_pre_chatd_ab_key`), no mediante WAM 5504. Las lecturas pre-chatd usan las opciones `A04` (urgent) cuando el flag **24317** está activo, y `A03` en caso contrario.

### 4.7 Props a nivel de grupo (found, `C41861nA`, `C502324k`, `C28900Ch1`)

```xml
<iq to="s.whatsapp.net" type="get" xmlns="abt"><props group="<group jid>" hash="<cached | empty>"/></iq>
```

Mismo tipo 220 y 32.000 ms que 4.1. El array de atributos de la solicitud tiene dos entradas: `group` y `hash` (smali). Condición: flag **16206** (maestro) y que se abra una conversación de grupo (`COK` / `Bnc`); se omite con `reason=cacheValid` hasta `_nextRefreshTimeInSeconds`, o con `reason=disabled`. Respuesta: `hash`, `refresh` acotado a 600..604.800 s (default 86.400), `refresh_id`, `<prop config_code config_value config_expo_key>`, tipado por los mismos mapas de defaults (bool, int, float, de lo contrario string). Los ids están en el espacio de ids compartido; el tipo de unidad GROUP (3.2) marca los 35 ids destinados a ello, y el flag leído para un grupo es `A04(groupJid, id)`. Las lecturas devuelven `null` cuando el grupo no tiene valor almacenado (el llamador recurre entonces a un fallback, no trazado). Claves en los prefs de grupo (`groupAbProps`, nombre inferred de `C00E`): `<jid>_<id>_value`, `<jid>_<id>_exposureKey`, `<jid>_exposureKeysSet`, `<jid>_nextRefreshTimeInSeconds`, `<jid>_lastRefreshHash`. No hay tipo JSON para valores de grupo.

### 4.8 Observadores (found)

`C0NE` tiene tres callbacks: `BhX` antes de escribir los nuevos valores (evento 34), `Bfk` y `C2K` después (eventos 33, 32). Ejemplo `CY8` (`PQKeysUploadABPropsObserver`): recuerda el flag **21198** en `BhX`; si pasó de `true` a `false` en `Bfk`, registra `PQ_KEYS_UPLOAD_CODE changed from true to false, deleting all kyber prekeys` y encola `DeleteKyberPreKeysJob`. 46 clases implementan `C0NE` (conteo con grep).

---

## 5. Almacenamiento en el dispositivo

| Archivo de prefs / clave | Contenido |
|-----------------|---------|
| `ab-props` (`C08J`, `C0D2.A00`) | valor `<id>`, `<id>_expo_key` y las claves `ab_props:sys:*` de abajo |
| `ab_props:sys:config_hash`, `config_key`, `last_version`, `refresh`, `last_refresh_time`, `fetch_app_version`, `fetch_attemp_count`, `last_error_code` | estado de sincronización |
| `ab_props:sys:last_exposure_keys` (string set), `last_daily_expo_key_update` | estado de exposición |
| `ab_props:sys:private_experimentation_id` | id aleatorio para experimentos en el dispositivo (6) |
| `ab_offline_props:offline_exposure_strings`, `ab_offline_props:offline_exposure_hash_strings` | exposición de experimentos offline (en `ab-props`) |
| `ab-props-backup` | copia del almacén anterior, reescrita en cada actualización completa |
| `ab-prechatd-props` | valores pre-chatd más `pref_expo_keys` |
| `ab-private-abprop` | `last_read_time_ms` (actualizado como máximo cada hora) y valores privados |
| `mc_expo:sys:ab_key`, `mc_expo:sys:last_exposure_keys`, `mc_expo:sys:last_exposure_keys_without_logging` | estado de exposición del lado de MobileConfig |
| `field-stats-events-sampling` | código de evento a peso de muestreo |
| `groupAbProps` | valores de grupo (4.7) |
| `<dataDir>/mobileconfig/mc_overrides.json`, `id_name_mapping.json` | tabla de overrides de MobileConfig, mapa id-nombre (nombres de archivo found en `C053409d`; ausentes del APK) |
| `pref_pre_chatd_ab_hash`, `pref_pre_chatd_ab_key`, `pref_pre_chatd_ab_next_fetch_time`, `pref_is_blocking_prechatd_exposure` | estado pre-chatd (prefs de registro) |

Todos los archivos se abren mediante `C00S.A05(name)` (un handle `SharedPreferences` en el directorio de datos privado de la app); no se comprobó si esa factory añade cifrado u ofuscación (unknown).

---

## 6. Exposición, experimentos, grupos

### 6.1 Registro de exposición (found)

| Paso | Detalle |
|------|--------|
| 1 | una lectura con registro de exposición (2.3) llama a `A0B(options, this, "<id>_expo_key")` -> `A12` |
| 2 | clave expo no vacía que aún no está en `last_exposure_keys`: se añade y se persiste |
| 3 | almacén principal: `C42831om.A01` publica el evento WAM **5504** `WamWefrClientExposure` (`wam_wefr_client_exposure`), con debounce de al menos 1 s; `BxP` llama al runtime de WAM (`C0D6.CYl(value, 5029, ...)`; "attribute" inferred por la forma de la llamada) con las claves unidas por comas (fusión por fuente cuando el flag **31830** está activo) |
| 4 | tras una sincronización completa solo permanecen en el conjunto las claves que la nueva respuesta sigue llevando |
| 5 | reenvío diario: en el callback de primer plano `A0A0.BvR`, cuando han pasado más de 24 h desde `last_daily_expo_key_update` (`sent_with_daily` = true) |
| 6 | pre-chatd: el hilo de pulso `C27952CBv` envía el log de embudo (4.6); el modo URGENT lo dispara de inmediato |

Campos de WAM 5504 (nombres Falco): `dedup_key`, `device_exp_id`, `exposure_key`, `from_metaconfig`, `sent_with_daily`. `device_exp_id` es un string derivado del objeto de identidad del dispositivo (`C09E.A0J().A03()`); derivación no trazada (unknown).

### 6.2 Ids de experimento y de grupo

| Id | Dónde | Significado |
|----|-------|---------|
| `config_expo_key` | por `<prop>` | clave de exposición de la rama del experimento; opaca para el cliente, solo se compara y se registra |
| `ab_key` | atributo de `<props>` | clave de todo el conjunto asignado; atributo WAM 4473 |
| `refresh_id` | atributo de `<props>` | versión del conjunto; se compara con `abprops` del `<success>` de login |
| `hash` | atributo de `<props>` | hash de contenido usado para "sin cambios" |
| `private_experimentation_id` | local | id aleatorio usado como unidad para experimentos en el dispositivo |
| `device_id`, `unit_id` | fetch MEX | identidad de unidad de MobileConfig |

La segmentación del lado del servidor (país, cohorte, porcentaje) no es visible; el cliente solo ve los valores resultantes (unknown).

### 6.3 Pesos de muestreo (found)

Las filas `<prop event_code sampling_weight>` alimentan el logger de field-stats: por evento, un peso de muestreo de 1 entre N. El evento **1094** (app launch) se refleja en `app_launch_event_sampling_weight`. La clave es un código de evento WAM, no un id de flag.

---

## 7. Evaluación local, overrides, rutas de depuración

### 7.1 AB offline (found, `C24976ApB`, `C27629BzE`, `C60839RQl`)

Los experimentos compilados dentro del APK (`C60839RQl.A00`, lista de `ON0` -> `ON1` -> `C53973OMy` -> `ConfigVariable{id, name, value, type}`) se evalúan contra un mapa local de información de usuario y se escriben en el almacén `ab-props` con las mismas reglas de tipado. Las condiciones (árbol `RM2`) solo pueden usar las propiedades `platform`, `app_version`, `app_build`, `release_channel`, `os_version` (`C0ER.A0B`). Claves de información de usuario: `device_id`, `app_build`, `release_channel`, `app_version`, `os_version`, `platform`, `country` (país de la SIM), `private_experimentation_id`. En esta beta `app_build` y `release_channel` son la constante `beta`. Al asignar, se eliminan las claves de sincronización (`config_hash`, `last_refresh_time`, `fetch_app_version`, `last_version`) para que el siguiente fetch online sea completo, y se dispara un log crítico `abprops-offline-assigned-after-registration-verified` cuando la asignación ocurre con `registration_state == 3`. Las definiciones de experimentos no se enumeran aquí (unknown).

### 7.2 Overrides de MobileConfig (found, efecto inferred)

`C053809h` carga `mc_overrides.json` (`hasOverridesFile`, `boolOverrideForParam`, `intOverrideForParam`, `stringOverrideForParam`, `doubleOverrideForParam`, con clave el Stable ID empaquetado de 64 bits), `C053409d.getOrCreateOverridesTable` se lo devuelve al motor. Los overrides se aplican solo a la ruta de MobileConfig, no a la ruta legacy de prefs. Si el motor consulta la tabla en un build de release es desconocido; no hay evidencia de una prueba en ejecución.

### 7.3 Deep link `override-abprops` (found)

Host del manifest `whatsapp-consumer://override-abprops` (alias exportado de `DeepLinkActivity`). `IJB` lo mapea al id de destino 154. `DeepLinkActivity.A0w` parsea el segmento de ruta `bugbash` y los parámetros de consulta `feature_name`, `feature_id`, `category`, `min_app_version`, `ready_to_test_time` y `variants` (array JSON en base64 de `{label, abprops:[{abprop_key, abprop_value}]}`) en `BugBashSession` / `BugBashVariant`. Existe un motivo de error `abprop_override_not_allowed`. No se encontró ningún código que escriba `abprop_key` / `abprop_value` en algún almacén de props: `BugBashVariant` solo es referenciado por el parser y su serializador, y `bugbash_session` solo se lee (`C51723Mxj`). La condición de activación y la ruta de aplicación son desconocidas.

### 7.4 Otros

| Ruta | Detalle |
|------|--------|
| ABPropBoolean `debugDefaultValue` | declarado (182 difieren), nunca leído (2.1) |
| UI de depuración | `com.whatsapp.backup.debugscreen.BackupAbPropsUiState` (solo nombre de clase, pantalla de depuración de backup) |
| Profiler por lectura | prefs `31165` (int) y `32010` (bool) alimentan `C00D.A0H/A0I/A0J` y una clase contador (`Pr8`); propósito no resuelto |

---

## 8. Ids de flag citados en otros reportes (verificados en 2.26.41.6)

Cada id se buscó en los mapas de defaults y en la tabla de Stable IDs. Los tipos son los tipos de mapa.

| Reporte | Resultado |
|--------|--------|
| `WA_BAN_SYSTEM_DEEP_EN.md` | 11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 presentes, bool default false; 12840 y 20278 son mapas **JSON** (los defaults coinciden); 31535 / 31536 son **float**, default 0.0. **34166 no es un flag**: sin default, sin Stable ID; `ContactInfoActivity.A0K = C1XG.A0I(34166)` es un id de inyección (los vecinos 34165, 34168, 34169 son del mismo tipo). 2923 ausente (como se reportó) |
| `WA_TCTOKEN_CSTOKEN.md` | los 16 ids presentes; defaults: 996 / 865 / 26897 = 604800, 997 / 909 = 4, 3802 / 22012 = 26, 4063 = 0, 20606 = 2000, todos los ids bool false. `299` es el entero de tipo de solicitud del IQ de privacy-token, no un flag |
| `WA_META_AI.md` | 25119, 26189, 27083, 37227, 37852, 37054 bool false; **26190 es JSON**, default `""` |
| `WA_USERNAME.md` | los 18 presentes con los defaults documentados; **34350 es una entrada de mapa string** (regex), **21995 una entrada de mapa JSON** |
| `WA_USYNC.md` | los 21 ids de flag presentes con los defaults documentados (730 = 35, 471 = 1140, 9667 / 33609 / 20988 = true) |

El mismo espacio de códigos aparece en WA Web: para 11 nombres de prop conocidos de la tabla pública de props de WA Web, la entrada de Android tiene el mismo código, tipo y default (p. ej. 22797 JSON `{}`, 32276 string `info_card, list_card`, 26270 int 1209600, 35639 int -1, 12539 bool true, 25071 / 1133 / 23245 / 28357 / 27009 / 6939 bool false) (found para el lado Android, inferred para "misma prop"). Los ids exclusivos de Web (3042, 30590, 24037, 25322) no tienen default en Android. 12 de los 16 ids de nivel de grupo de Web son los ids de unidad GROUP de Android (3.2).

---

## 9. Nombres y categorías

| Tema | Hallazgo |
|-------|---------|
| Nombres | no se encontró ninguna tabla de nombres legibles en dex ni assets (una búsqueda de dos nombres de flag legacy conocidos solo coincidió con strings de log); `id_name_mapping.json` es solo un nombre de archivo en tiempo de ejecución en `C053409d` |
| Nombres en logs | unos pocos strings de log reutilizan nombres: `PQ_KEYS_UPLOAD_CODE` (21198), `abprop_override_not_allowed`; los nombres de builds anteriores o de WA Web son la única vía hacia la semántica |
| Categorías | no hay campo de categoría. La estructura proviene del tipo de unidad (SESSIONLESS 564, SESSIONBASED 20.781, GROUP 35) y del tipo de valor |
| Más leídos | los ids literales más leídos: **20548** (bool true, 511 sitios), **9970** (false, 312), **1107** (false, 151), **12267** (true, 147), **1600** (string `{"allowed_product_type":"none"}`, 146), **27008** (false, 104), **13989** (int 7, 87). Semántica sin resolver |

---

## 10. Catálogo de flags por área (defaults found en `C08J`; uso leído de los otros reportes y re-verificado aquí)

### 10.1 Infraestructura de sincronización y MobileConfig

| Flag | Tipo | Default | Controla |
|------|------|---------|----------|
| **23048** | bool | false | MobileConfig inicializado (`A0F`) |
| **27668** | int | 0 | `AbstractC06100Cm.A0E`; > 0 activa MobileConfig (`A0E`) |
| **24896** | bool | false | MobileConfig es la fuente de verdad (inferred) |
| **25403** | bool | false | vuelta a la fuente legacy (inferred) |
| **22646** | bool | false | comparación shadow |
| **22647** | int | 10 | muestreo del log shadow |
| **38895** | int | 0 | `== 1`: caché de MobileConfig por lectura |
| **26524**, **28443**, **30441**, **30556** | bool | false | opciones de la factory de MobileConfig (`CbW`, `BMu`) |
| **26525** | int | 600 | opción de la factory de MobileConfig (`CbW`), unidad sin resolver |
| **26640** | bool | false | parámetro de init de MobileConfig (`BN4`) |
| **35778** / **36185** | int | 0 | fase de init / opción de temporización del fetch (`C054709r.APn`, `C41251mA.A00`) |
| **24317** | bool (SESSIONLESS) | false | las lecturas pre-chatd usan exposición urgent |
| **31830** | bool | false | fusión por fuente del atributo de exposición 5029 |
| **16206** | bool | false | puerta maestra de las props de grupo |
| **18205** | bool (GROUP) | false | lectura por grupo en `GroupAbPropsManager` |
| **3664** / **6084** | bool | false | borrar / establecer `encrypted_rid` |
| **21198** | bool | false | `PQ_KEYS_UPLOAD`: subida de prekeys Kyber; `true` a `false` las elimina |

### 10.2 Ban e integridad (`WA_BAN_SYSTEM_DEEP_EN.md`)

11061, 11064, 11065 (int 86400), 12709, 16349, 19793, 19893, 26697, 27269, 14837, 25631 (bool false); 12840 (JSON `{"automation_bulk_messaging":{"max_dismiss_count":7,"max_display_days":7}}`); 20278 (JSON `{"max_messages": 10000, "farthest_time_days": 30}`); 31535 / 31536 (float 0.0).

### 10.3 Privacy token y cstoken (`WA_TCTOKEN_CSTOKEN.md`)

| Flag | Tipo | Default |
|------|------|---------|
| **996** / **997** | int | 604800 / 4 |
| **865** / **909** | int | 604800 / 4 |
| **4063** | int | 0 |
| **3802** / **22012** | int | 26 / 26 |
| **20605** / **14303** / **15491** | bool | false |
| **20606** | int | 2000 |
| **24915** / **24941** / **18639** / **25253** | bool | false |
| **26897** | int | 604800 |

### 10.4 Meta AI, username, USync

| Reporte | Flags (default) |
|--------|-----------------|
| `WA_META_AI.md` | **26189**, **27083**, **25119** (sin lector), **37227**, **37852**, **37054**: bool false; **26190** JSON `""` |
| `WA_USERNAME.md` | **4745**, **20189**, **23817**, **21199**, **16033**, **8421**, **12402**, **28678**: bool false; **21995** JSON `{}`; **20494** 3, **20459** 35, **34347** 4, **34348** 6, **28127** 30, **29327** 60; **34350** string `^([0-9]{4}\|[A-Z0-9]{6})$` |
| `WA_USYNC.md` | **5751**, **5839**, **20798**, **29769**-**29771**, **9732**, **33432**, **14565**, **26739**, **31261**: bool false; **9667**, **33609**, **20988**: true; **730** 35, **471** 1140, **37780** 0 |

### 10.5 Nivel de grupo (unidad GROUP, 35 ids)

Bool false: 18205, 23245, 23246, 26013, 26269, 26862, 27009, 27025, 28357, 28358, 29275, 30905, 30906, 31456, 32501, 34075, 35211, 35772, 36156, 36504, 36505, 38082, 38083. Int: 26270 (1209600 s = 14 días), 27247 (0), 23397 / 23398 / 24075 / 34277 / 34333 / 35227 / 35639 / 37523 / 37524 (-1). String: 33673 (`none`). Los nombres de 26270, 23245, 23246, 26269, 30905, 30906, 28357, 28358, 27009, 27025, 35639, 35772 provienen de WA Web (historial de grupo y ajustes de encuestas; inferred).

---

## 11. Baileys (`baron-baileys-v2`, `src/Socket/chats.js`)

| Tema | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| solicitud de usuario | `fetchABProps(protocol='1', hash, refreshId)`: `<props protocol hash? refresh_id?>` en `xmlns="abt"` | misma forma; `hash` siempre presente (vacío cuando se fuerza), `refresh_id` solo con delta |
| solicitud de grupo | solo `{ group }` | `group` + `hash` (array de 2 en smali) |
| claves de respuesta | `reduceBinaryNodeToDictionary(props, 'prop')`: diccionario `config_code` -> `config_value` | almacén tipado; se usan `config_expo_key`, filas `event_code`, `hash`, `refresh`, `refresh_id`, `delta_update` |
| consulta | por nombre de flag (`abProps['stella_interop_enabled']`) | solo por código numérico |
| props legacy | `fetchProps`: `xmlns="w"` `<props protocol="2" hash>` props con nombre | no se encontró ningún builder; los nombres aparecen solo en el diccionario de tokens de stanza (`AbstractC40911lb`) |
| refresh | ninguno (una vez por conexión) | intervalo + comprobación de versión + push |

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `abProps['<name>']` es `undefined` | la respuesta `abt` solo lleva `config_code` | usar el código como clave; el espacio de códigos es el de la sección 8 |
| aparece una clave `undefined` en el diccionario | las filas `event_code` / `sampling_weight` no tienen `config_code` | omitir las filas sin `config_code` |
| valores obsoletos | sin manejo de hash / refresh / `refresh_id`, sin delta | almacenar `hash`, `refresh`, `refresh_id`; enviar `hash` y `refresh_id` en la siguiente solicitud |
| bool leído como string truthy | `config_value` es `"1"` / `"0"` | parsear según el tipo (`!= 0`) |

---

## 12. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `ABPropsManager/onABPropError; unknown error code: N` | error fuera de 207 / 304 / 400-503 | ninguna; el contador no avanza |
| 3 fetches fallidos, sin reintento durante un día | `fetch_attemp_count` llegó a 3, `last_refresh_time` = ahora | esperar un intervalo o un incremento de versión `abprops` en el login |
| `AbPropProtocolHelper/onReceiveABProps failed to parse response` (`C49828Lvo`) | `<props>` malformado | excepción relanzada, almacén intacto |
| `ABPropsManager/invalid format for config; configCode=N; value=V` | int/float no numérico o JSON inválido | esa prop se omite |
| `IllegalArgumentException: Unknown BooleanField: N` | lectura tipada de un id sin default en el mapa ni default en descriptor | añadir default; `N` es un config code |
| una lectura de MobileConfig devuelve `false` / `0` / `""` | el id no tiene Stable ID (`INVALID_SPECIFIER_MISSING_IN_WA_LOOKUP_MAP`) | leer por la ruta legacy |
| `WAMCEvaluation/invalid json format; key=N` | valor de flag JSON no parseable en la ruta de MobileConfig | se devuelve un `JSONObject` vacío |
| `GroupAbPropsClient/malformedResponse ... noPropsChild` / `parseFailed` | respuesta de grupo sin `<props>` o parseo fallido | no se almacena valor de grupo |
| `GroupAbProps/fetchSkip reason=cacheValid` / `disabled` | antes de `_nextRefreshTimeInSeconds` / flag 16206 desactivado | ninguna |
| `ABPreChatdProps/exception ... error add expo key` | JSON `pref_expo_keys` corrupto | la clave no se añade |

---

## 13. Distinciones clave

| No confundir | Detalle |
|----------------|--------|
| config code vs id de inyección | `A15(20548)` es un flag; `C05Z.A00(66)`, `C1XG.A0I(34166)`, `C00C.A02(61)` son ids de dependencia |
| config code vs tipo de solicitud IQ | `A0W(..., 220, 32000L)` (220 aquí, 299 en el IQ de privacy-token) es un entero de tipo de solicitud |
| config code vs ids de WAM | 5504 es un evento, 5029 y 4473 son atributos WAM, 1094 es un código de evento en las filas de muestreo |
| config code vs Stable ID | el código (<= 39140) indexa la tabla; el Stable ID es un specifier de MobileConfig de 64 bits |
| IQ `abt` vs props `w` vs tabla `props` de la BD | `abt` = AB props numéricas; props `w` legacy = props de servidor con nombre; la tabla SQL `props` = almacén clave-valor local |
| props de usuario vs props de grupo | mismo espacio de ids, mismos mapas; los valores de grupo viven en `groupAbProps`, con clave jid de grupo, unidad GROUP |
| `ab_key` vs `config_expo_key` vs `hash` vs `refresh_id` | clave del conjunto / clave de experimento por prop / hash de contenido / versión |
| `abprops` del login vs `<props refresh_id>` | versión actual del servidor vs versión almacenada de la última respuesta |
| MEX `MetaConfigFetchMutation` vs `abt` | blob de MobileConfig vs props numéricas legacy; ambos corren cuando MobileConfig está activo |
| default de producción vs default de debug | solo se lee el default de producción |
| fijado del primer acceso vs caché normal | los valores fijados sobreviven a las sincronizaciones hasta el fin del proceso |
| asignación offline vs online | los experimentos offline escriben en el mismo almacén y luego fuerzan un fetch online completo |

---

## 14. Flujo completo

```
[Server]            [Login]                 [C0D2 / C27646BzW]               [C08J reads]         [WAM]
   │ <success abprops=N props mc_ep_version>   │                                   │                 │
   ├──────────────────►│ N > last_version? or  │                                   │                 │
   │                   │ last_refresh+refresh<now                                  │                 │
   │                   ├──────────────────────►│ <iq xmlns=abt>                    │                 │
   │◄───────────────────────────────────────── │  <props protocol=1 hash [refresh_id]>             │
   │ <props ab_key hash refresh refresh_id [delta_update]>                          │                 │
   │   <prop config_code config_value config_expo_key/> ... <prop event_code sampling_weight/>      │
   ├──────────────────────────────────────────►│ typed store per id (bool/int/float/string/JSON)   │
   │                                           │ backup, hash, refresh, last_version, ab_key       │
   │                                           ├─ observers BhX ► write ► Bfk / C2K ──────────────►│
   │                                           │ A0s(): clear read cache                           │
   │                                           │                                   │                 │
   │ <ib><abprops/>  (force, empty hash) ─────►│                                   │                 │
   │                                           │                                   │                 │
   │                                      A15(id) / A0b(id) / A0j(id)...           │                 │
   │                                           │          cache ► prefs ► default map ► (descriptor)│
   │                                           │          MobileConfig path if A0E && A0b && !A0S   │
   │                                           │                                   ├ first read ────►│ 5504 exposure
   │                                           │                                   │ + 24 h resend   │ 5029, 4473
   │                                           │                                   │                 │
   │ MEX MetaConfigFetchMutation ◄─────────────┼── C41251mA (option 36185) ────────┤                 │
   │ xwa2_mobile_config_fetch {blob, ep_refresh_id, ab_key} ───► native MobileConfig, Stable IDs    │
   │                                           │                                   │                 │
   │ <iq xmlns=abt><props group hash> (group opened, flag 16206) ► groupAbProps ► A04(groupJid,id)   │
```

---

## 15. Incógnitas

| Tema | Motivo |
|-------|--------|
| Semántica de los flags | sin nombres; semántica solo donde un punto de llamada u otro reporte la resuelve |
| Asignación del lado del servidor | la segmentación, los porcentajes de despliegue y las definiciones de experimentos no están en el cliente |
| Stanza padre del hijo push `abprops` | handler registrado bajo el código de mensaje 235; `ib` inferred |
| Vínculo entre `abprops` del login y el argumento de versión del disparador | el disparador recibe un `Integer`; el parseo del login establece un `AtomicReference`; conexión inferred |
| `mc_overrides.json` de MobileConfig en builds de release | existe el código de la tabla; sin evidencia de que se consulte ni de que el usuario de la app pueda escribirla |
| Condición de activación y ruta de aplicación de `override-abprops` | existe el motivo `abprop_override_not_allowed`; no se encontró ningún escritor hacia un almacén de props |
| derivación de `device_exp_id`, formato de `config_expo_key` | no trazado |
| Bits 0-15 del Stable ID, entradas de unidad `u4`, `int1 >> 16` | significado sin resolver |
| Prefs `31165`, `32010`, flag `35778`, valores `36185` 1 / 2 | leídos parcialmente (`Pr8`, coordinador) |
| Comportamiento de los 70 ids solo con default bajo MobileConfig | la lambda tipada devuelve valores cero (found); efecto sobre las funciones no trazado |
| Semántica del delta del lado del servidor | qué props lleva un delta |
| Tráfico real y valores servidos en vivo | solo análisis estático |
