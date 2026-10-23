<!-- src-sha1: c6955a2c041a57de36c902dfa247b0b65dc0b530 -->
# WhatsApp WAM Analytics — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** telemetría WAM ("WhatsApp Metrics") de Android — modelo de eventos (ids de evento, campos, canales REGULAR / REALTIME / PRIVATE / canal 3), pipeline de logging en Java, muestreo y pesos por evento, runtime nativo (`libwhatsapp.so`), atributos comunes, buffers en disco, formato de wire WAM, subida regular (IQ `w:stats`), subida privada (IQ de credencial + transporte separado), `wam_daily` y el cron diario, ids de private-stats y rotación, tratamiento de privacidad, feature flags, familias de eventos notables, comparación con Baileys, qué sigue siendo desconocido

---

## 1. Qué es WAM en este build

WAM es un pipeline de métricas del lado del cliente: los eventos tipados se crean en Java (o se convierten desde las estadísticas nativas de llamadas), se muestrean, se pasan a un runtime nativo que los serializa en buffers binarios almacenados en `files/wam/`, y se suben al servidor. Es solo telemetría saliente. Nada del protocolo de chat depende de ella. Todas las afirmaciones provienen de análisis estático del APK decompilado (`versionCode 264100600`), más las cadenas nativas de `libwhatsapp.so` y el layout de los archivos de buffer encontrados en un directorio de datos de la app de este build. Niveles: **found** = leído en código o en un archivo de buffer, **inferred** = deducido, **unknown** = no resoluble de forma estática. Los nombres ofuscados son específicos de cada build y se re-resolvieron a partir de cadenas estables en 2.26.41.6 (cadenas de log, nombres de eventos `wam_*`, valores de atributos de IQ).

| Entidad | Nombre en 2.26.41.6 | Función |
|---------|---------------------|---------|
| Clase base de evento | `C0Fc` | `code`, `samplingRate`, `bufferChannel`, `psId`; `getFieldsMap()` abstracto (ids numéricos), `getFieldsMapForFalco()` (nombres), `getEventNameForFalco()`, `validate()` |
| Tupla de muestreo | `C036300x` | niveles de peso; `A00` es el peso que usa el sampler |
| Resolvedor de muestreo | `C0Fg` + `C06580Fh` | override de peso por evento desde las prefs `field-stats-events-sampling` |
| Logger (fachada del runtime WAM) | `C06650Fo` (`InterfaceC06640Fn`); `C40098Hdb` distribuye hacia él y hacia el logger Falco en Java `C40099Hdc` | `CNW` publica, `CNI` publica con muestreo, `CXW` flush, `CUj` reset, `CXZ` flush y espera (2500 ms); init en `RunnableC29323CoA` case 33 |
| Puente JNI | `com.whatsapp.wamsys.JniBridge` | `jvidispatch*` de Java a nativo, `jnidispatch*` de nativo a Java |
| Atributos comunes | `C06590Fi` (`CYl(value, attrId, channel)`), init en `RunnableC29340CoR` case 0 | atributos globales por canal |
| Handler de AB-props | `C28894Cgv` | analiza `<props>` incl. `event_code` / `sampling_weight` |
| Evento diario | `C0Fp` (`wam_daily`, id 1158) | estado del dispositivo y de la app |
| Cron diario | `C28643Ccj` (`WamDailyEventDailyCron`), alarma en `BEL` (`DailyCronAction`) | construye y publica `C0Fp` |
| Evento de llamada | `com.whatsapp.fieldstats.events.WamCall` (id 462) | creado a partir de estadísticas nativas de llamada, publicado por `C24895Anr` |
| Runtime nativo | `libwhatsapp.so` (`WAMRuntime`, `WAMBufferStore`, `WAMTransportRegular`, `WAMTransportPrivate`, `WAMPSIDProfile`) | buffers, ids, subidas |

No es WAM, no confundir (ver 17): el logger sombra Falco del lado Java (`C40099Hdc`, `FFLogger`), el uploader de crashes y logs etiquetado `wam-event/<name>`, los tokens ACS de otros proyectos, y la palabra `fieldstats` usada por las estadísticas nativas de llamadas (`prepare_wa_call_fieldstats`).

Las señales de integridad del cliente que viajan dentro de WAM (`is_rooted`, `is_genymotion`, `is_whatsapp_plus_user`, atributos 6251 y 10255) se describen en [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) y aquí solo se referencian.

---

## 2. Modelo de eventos

### 2.1 Clase de evento (`C0Fc`)

Cada evento es una clase generada; el constructor es `super(code, samplingTuple, bufferChannel, psId)`, p. ej. `wam_daily`: `super(1158, new C036300x(1, 1, 1, false), 0, -1)`, `getEventNameForFalco() = "wam_daily"`, `internalFalcoMigrationBatchNumber() = 12`.

| Miembro | Significado | Tier |
|---------|-------------|------|
| `code` | id numérico de evento (1158 para `wam_daily`, 460 `wam_login`, 462 `wam_call`, 854 `wam_message_send`) | found |
| `samplingRate` | `C036300x(a, b, c, flag)` se almacena como `A02=a, A01=b, A00=b, A03=c`; el sampler usa `A00 = b`. Valor por defecto `C0Fc.DEFAULT_SAMPLING_RATE = (1, 20, 20)` | found |
| `bufferChannel` | 0..3, ver 2.2 | found |
| `psId` | `-1` = no privado; en otro caso, un hash de clave de private-stats, ver 2.3 | found |
| `getFieldsMap()` / `getFieldsMapForFalco()` | id numérico de campo a valor (se pasa a nativo) / nombre snake_case a valor | found |
| `validate()` | lista de violaciones (`.nonnull` y reglas similares), ver 3.2 | found |
| `serialize(C3T8)` | el cuerpo es `throw new NullPointerException("serialize")`; la serialización es nativa | found |

Los campos usan tipos boxed de Java (`Boolean`, `Integer`, `Long`, `Double`, `String`). Los enums y timers viajan como enteros (inferred a partir del setter de atributos, que solo acepta null / String / Integer / Long / Double / Boolean). `wam_daily` tiene 218 slots numéricos y 205 slots con nombre (13 slots numéricos son solo null), idéntico al conteo anterior de 2.26.35.8.

### 2.2 Canales

| `bufferChannel` | Eventos (analizados) | Nombre (etiquetas inferred; Java usa enteros simples) | Tier |
|-----------------|----------------------|------|------|
| 0 | 824 | REGULAR | found |
| 1 | 8 | REALTIME | found |
| 2 | 168 | PRIVATE (requiere un id de private-stats, ver 2.3) | found |
| 3 | 8 | realtime anónimo de private-stats, "RTPS" en las cadenas de log nativas (etiqueta inferred) | found / inferred |

Total analizado: 1,008 clases de evento con ids distintos. El mapeo se pasa sin cambios a nativo (argumento de canal 0..3 de `jvidispatchIIIIIOO`). Cualquier otro valor lanza `IllegalArgumentException("Unsupported channel type")`.

Eventos REALTIME (ids): 2098 `wam_ui_action_real_time`, 5504 `wam_wefr_client_exposure`, 5278 `wam_android_test_realtime`, 6640 `wam_wefr_group_client_exposure`, 6088 `wam_restore_contacts_realtime_event`, 4290 `wam_wa_fs_chat_transfer`, 2872 `wam_xplatform_migration_export`, 6266 `wam_cac_client_event` (found).

Eventos del canal 3: 5164 `wam_wam_test_anonymous_realtime`, 7312 `wam_mm_signal_undisclosed`, 7352 `wam_mm_signal_realtime`, 6160 `wam_wamo_video_event`, 6158 `wam_wamo_ctwa_1pd_conversion`, 7956 `wam_wamo_promo_pog_impression`, 5712 `wam_wamo_promo_reporting_events`, 7350 `wam_wamo_alv2_link_click` (found). `C06650Fo.A01` descarta un evento del canal 3 salvo que su código esté en dos arrays hard-coded (`AbstractC38512Gog.A00` 3 ids, `A01` 5 ids). Esos 8 ids son exactamente los 8 eventos del canal 3, por lo que en este build la comprobación no descarta nada (inferred a partir de los conjuntos de ids).

### 2.3 Ids de private-stats (`psId`)

| `psId` (int) | Cadena de clave en el archivo de perfil nativo | Rotación (días) | Eventos | Tier |
|--------------|-----------------------------------------------|-----------------|---------|------|
| `-1` | ninguna (no privado) | – | 832 (regular + realtime) | found |
| `0` | `none` (el global de buffer 6005 contiene la cadena `none`) | – | 94 (86 privados + 8 del canal 3) | found; mapeo "none" inferred |
| `113760892` | `default_ps_id` | nunca (`-1`) | 66 | found |
| `56300709` | `id_pre_metrics` | nunca (`-1`) | 1 (`wam_ps_app_launch`) | found |
| `248614979` | `id_ttl_daily` | 1 | 4 | found |
| `42196056` / `191000728` | `id_ttl_weekly` / `id_ttl_monthly` | 7 / 30 | 0 | found |
| `37887164` | `id_ttl_90_days` | 90 | 1 (`wam_clock_skew_difference_t`) | found |
| `152546501` | `group_exit_experience_id` | 30 | 4 | found |
| `216763284` | `group_safety_check_id` | 30 | 6 | found |

Las cadenas de clave y los días de rotación se leyeron de los ocho archivos `WAMMetadataPSIDProfile-*` (ver 6.3), los conteos de eventos de las clases de evento.

### 2.4 Pesos en todo el catálogo

Peso efectivo del esquema `A00` por evento (el evento se conserva con probabilidad 1/peso y el peso se almacena con el evento):

| Peso | Eventos | Miembros típicos |
|------|---------|------------------|
| 1 (siempre) | 826 | `wam_daily`, `wam_registration_complete`, `wam_blocking_funnel` |
| 5 / 10 | 6 / 12 | `wam_message_send` (5), `wam_message_context_menu_actions` (10), `wam_ui_action_real_time` (10) |
| 20 | 135 | `wam_message_delete_actions`, `wam_message_high_retry_count`, todos los eventos con `DEFAULT_SAMPLING_RATE` (81) |
| 100 / 200 | 4 / 2 | `wam_login_stage_reliability` (100) |
| 1000 | 17 | `wam_message_stanza_receive`, `wam_call_stanza_receive`, `wam_status_stanza_receive`, `wam_iq_send`, `wam_push_latency`, `wam_db_perf` |
| 10000 | 4 | `wam_receipt_stanza_receive`, `wam_android_profilo_usage`, `wam_android_message_target_perf`, `wam_notification_highlight_result` |

El peso no es un interruptor de funcionalidad: el servidor puede sobrescribirlo por evento (8.2). Un evento con un peso constante de build no se clasificó en ningún intervalo.

---

## 3. Pipeline de logging en Java

### 3.1 Ruta de publicación

`CNW` = `CNI(event, null, false)`: resuelve el peso (8.1), ejecuta la allowlist del canal 3 (`A01`), y luego ejecuta el runnable `X.1Fc` en el executor de WAM (`C06600Fj.A01`):

| Paso | Comportamiento | Tier |
|------|----------------|------|
| Latch del runtime | `C06650Fo.A0K` (`CountDownLatch`) bloquea el executor hasta que los atributos comunes estén inicializados ("wamruntime/initializeCommonAttributes: runtime initialized") | found |
| Validación | `event.validate()` se ejecuta solo para los canales 0 y 1 (no para la clase de evento de validación `C40251kT`). Cada violación se convierte en un `wam_wam_validation_error_event` (id 5560) con el código del evento infractor, un valor de sesión aleatorio y partes de la regla unidas con `;` | found |
| Modos del logger (`A04`) | `3`: para los códigos de un conjunto configurado escribe `traceIdInt` (64 bits aleatorio) en el evento por reflexión; `10`: para eventos que pasan `C06630Fm` (Falco migration batch 1..16, no en una lista de denegación) escribe `dedupKey` (64 bits aleatorio); `1` / `3`: además publican un evento Falco (`_test$<name>` / `<name>_shadow`) | found |
| Despacho | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fieldsMap)` tras asegurar que la librería esté cargada | found |
| Disparador de subida de logs | La AB string prop **31314** contiene `"code:N;code:M"`; si `Random.nextInt(N)==0` para el código publicado, se pide al reporter de crashes y logs que suba los logs del dispositivo con la etiqueta `wam-event/<falco name>`. Esto sube logs, no el buffer WAM | found |

`dedup_key` y `trace_id_int` son campos del esquema del evento (presentes en `wam_login`, `wam_app_launch`, `wam_message_send`); son aleatorios por evento y no son identificadores de usuario (inferred a partir del generador).

### 3.2 Reglas de validación

En `C0Fp` (`wam_daily`) el campo `ai_widget_installed` siempre se reporta como violación porque ningún miembro Java lo respalda (regla `daily .nonnull`), y `default_after_read_enabled` cuando su miembro es null. Consecuencia (inferred): cada evento diario en el canal 0 también produce eventos de validación (id 5560).

### 3.3 Disparadores de flush y ciclo de vida

| Disparador | Llamada | Op nativa | Tier |
|------------|---------|-----------|------|
| Connection handler conectado | `C0A4.BvO` -> `CKt(0)` | `jvidispatchIIO(4, 0, ctx)` | found |
| Conectando / desconectado | `BvP`, `BvQ` -> `CKt(1)` | `jvidispatchIIO(4, 1, ctx)` | found |
| Procesamiento de mensajes offline completo (`XmppStateManager/offlineProcessComplete`, también limpia `C0A2.A07`) | `BvR` -> `CXW(false)` solo si la AB prop **9654** | `jvidispatchIO(10, ctx)` (flush de buffers activos) | found |
| Flush explícito | `Bba()` -> `CXW(true)`; `CXZ()` hace flush y espera hasta 2500 ms | `jvidispatchIO(10, ctx)` | found |
| Fin de llamada | `C24895Anr.A02` publica `WamCall`, luego `Bba()` si la llamada está marcada o la AB prop **16047** | flush | found |
| Re-registro / eliminación de cuenta | `C25100xS` ("RegistrationManager/reregister/rm-me") -> `CUj()` | `jvidispatchIO(12, ctx)` ("wamruntime/resetruntime") | found |

El argumento de estado 0/1 es el estado de la conexión XMPP reflejado en los transportes nativos (cadena de log "wameta/transport/status - %d"). Que 0 = conectado se lee del mapeo de callbacks, no del código nativo (inferred). Estados de `C0A2.A04`: 1 conectando, 2 conectado, 3 desconectado, 4 detenido; `A07` es true desde la conexión hasta que termina el procesamiento offline, de modo que `A0N()` significa "conectado y aún drenando mensajes offline".

### 3.4 Superficie JNI

| Dirección | Firma | Propósito | Tier |
|-----------|-------|-----------|------|
| Java a nativo | `jvidispatchIOOOO(0, path, networkSession, ctx, config)` | inicializa el runtime (log "WAJContextInitWAMRuntime"), ver 4 | found |
| Java a nativo | `jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)` | registra un evento | found |
| Java a nativo | `jvidispatchIIIOO(0, channel, attrId, String, ctx)` / `jvidispatchIIIO(4, channel, attrId, ctx)` / `jvidispatchIIIIO(1, channel, attrId, bool, ctx)` / `jvidispatchIIIDO` / variantes int, long | establece un atributo común (null, string, boolean, double, integer) | found |
| Java a nativo | `jvidispatchIIO(4, state, ctx)` / `jvidispatchIO(10, ctx)` / `jvidispatchIO(12, ctx)` | estado de conexión / flush / reset | found |
| Java a nativo | `jvidispatchIOOOO(4, ctx, signedCredential, acsPublicKey, configId)` | resultado del IQ de credencial (todo null en caso de fallo) | found |
| Nativo a Java | `jnidispatchIO(6, byte[])` | envía un buffer regular como IQ `w:stats`, devuelve 1 con `result` | found |
| Nativo a Java | `jnidispatchIO(7, byte[32])` | envía la solicitud de credencial `privatestats` | found |

---

## 4. Inicialización del runtime

`RunnableC29323CoA` case 33 construye un mapa de configuración y llama a la init nativa una vez. La ruta es `<filesDir>/wam`.

| Clave de config | AB prop | Tipo | Significado probable | Tier |
|-----------------|---------|------|----------------------|------|
| `platform_code` | – | int `2` | id de plataforma Android | found |
| `beacon_probability` | **6977** | int | probabilidad del estado nativo de "beaconing" por evento (`WAMBeacon`) | found; significado inferred |
| `storage_size` | **9822** (x 1024) | long | tope de almacenamiento de buffers (KiB a bytes); el nativo registra "no-enough-storage" y descarta eventos | found; unidad inferred |
| `buffer_timeout` | **12399** | int | temporizador de rotación de buffers | found; significado inferred |
| `throttling_percentage` / `throttling_exempt` | **9457** / **9456** | int / string | throttling de subida y lista de exentos | found; significado inferred, formato unknown |
| `enable_extra_logging` | **14310** | bool | logging nativo detallado | found |
| `enable_ps_upload_v2` | **15205** | bool (solo cuando está activo) | "beginning upload v2 logic" nativo en el transporte privado | found |
| `enable_aggregation` / `aggregation_config` | **11981** / **11982** | bool (solo cuando está activo) / string | habilita `WAGAggregation` con sus reglas | found; formato unknown |

La misma llamada recibe un objeto `networkSession` creado por `C25810yb`; su uso por los wrappers HTTP nativos es inferred. Los valores por defecto de las AB props los entrega el servidor y no se resolvieron.

---

## 5. Atributos comunes (globales)

Los atributos globales los escribe `RunnableC29340CoR` case 0 mediante `C06590Fi.CYl(value, attrId, channel)` con los canales 0..3. Un helper establece los cuatro canales a la vez; otros solo establecen 0 y 1. Por tanto, los canales privados (2, 3) reciben un conjunto reducido.

| Id de attr | Origen del valor | Canales | Tier |
|------------|------------------|---------|------|
| 3 / 5 | MNC / MCC analizados de `TelephonyManager.getNetworkOperator()` (5 o 6 dígitos, solo GSM) | 0 1 2 3 | found |
| 11 / 1659 / 1657 | código de plataforma `2` / código de plataforma `2` / constante `3` | 0 1 2 3 | found |
| 13 / 15 / 17 / 21 | `Build.MODEL-Build.MANUFACTURER` / `Build.VERSION.RELEASE` (omitido con la AB prop **12637**) / versión de la app `2.26.41.6` / `true` (flag beta inferred; hard-coded en este APK beta) | 0 1 2 3 | found |
| 287 / 289 / 495 | `Build.MANUFACTURER` / `Build.MODEL` / una cadena de dispositivo (no resuelta) | 0 1 | found |
| 655 / 689 / 2617 | métricas de memoria y clase del dispositivo (`C38271gj`, `IJJ.A02/1048576`, `C38261gi`) | 0 1 2 3 | found; nombres inferred |
| 4473 | clave de configuración AB (`ab_key` de la última respuesta `<props>`, se restablece en cada actualización AB) | 0 1 | found |
| 5029 | ids de exposición a experimentos AB unidos por comas (`BxP`); con la AB prop **31830** un mapa combinado de `ab-props` y `ab-private-abprop` | 0 1; también presente en un buffer privado (canal 2) | found |
| 6251 / 10255 | verificación de firma de la app / flag del instalador Play | 6251: 0 1 2 3; 10255: 0 1 | found, ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |
| 12017, 12027, 14507, 15265, 15611, 23, 707, 7335, 13293, 23043 | valores variados de estado de la app (12027 boolean del objeto de estado de cuenta, 707 `primary_platform_name` solo cuando 12027 es true, 13293 = AB prop **3664**, 15611 constante WASafe (ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md)), 7335 `true` una vez que corrieron los hooks de init) | mayormente 0 1; 13293 los cuatro | found; significados inferred o unknown |
| 47 | hora de commit, int32 segundos, añadido de forma nativa | todos | found (archivo de buffer) |
| 6005 | valor del id de private-stats (cadena UUID o `none`), añadido de forma nativa | buffers privados | found (archivo de buffer) |
| 2795, 105 / 6833 | añadido de forma nativa, solo buffers regulares / valor de `C21730rv`, solo canales 2 y 3 | 0 / 2 3 | found; significados unknown |

Entre los atributos comunes escritos por Java no hay número de teléfono, JID ni id de cuenta. El transporte regular se vincula a la cuenta mediante la conexión autenticada por la que se envía (inferred, ver 9).

---

## 6. Almacenamiento nativo

Las cadenas de `libwhatsapp.so` (`WAMBufferStoreImpl`, `WAMPSIDProfileStoreImpl`, `WAMPrivateCredentialStoreImpl`, `WAMMetadataStoreImpl`) y los archivos de un directorio de datos instalado de 2.26.41.6 coinciden.

### 6.1 Directorio `files/wam/`

| Archivo | Contenido | Tier |
|---------|-----------|------|
| `wamt-a-<channel>-0-<seq>` | buffer activo, 65,559 bytes (preasignado, relleno con ceros); una cadena nativa `wamt-o` sugiere buffers rotados (inferred) | found |
| `wam-metadata` | contenedor `MTD` v4 con contadores por canal; la siguiente secuencia almacenada para el canal 0 es igual a la mayor secuencia de archivo más uno | found; layout inferred |
| `WAMMetadataPSIDProfile-<n>-<keyHash>` | un perfil de private-stats por hash de clave (se vieron 8 archivos) | found |
| `WAMMetadataPrivateCredential-<n>` | credencial almacenada para el transporte privado (`signed_credential`, clave, config id; v2, ~120 bytes) | found; layout inferred |

El tercer número del nombre de archivo es un id de stream (log "wameta/buffer/rotated stream id: %d, channel: %d, buffer sequenceNumber: %d"; siempre `0` en la muestra), el último es la secuencia del buffer.

### 6.2 Layout del archivo de buffer

```
off  0   "WMT" 03                      container magic, version 3
off  4   u32 LE  used length           = (end of used data) - 31   (checked in 2 files)
off  8   u32 LE  ?                     counter, meaning unknown
off 12   u32 LE  event count           equals the number of event markers decoded
off 16   u32 LE  ?                     close to the used length (+4, +6, +31 in samples)
off 20   u32     ?                     check value (inferred), algorithm unknown
off 24   "WAM" 05                      WAM header: magic + protocol version 5
off 28   u8  0                         flag byte (0 in all samples)
off 29   u16 LE  buffer sequence       equals the number in the file name
off 31   u8  channel                   0 regular, 2 private in samples
off 32   TLV entries                   globals first, then events
```

Found para cada byte listado con un valor; los campos marcados con "?" son unknown.

### 6.3 Perfil de private-stats

`WAMMetadataPSIDProfile-<n>-<keyHash>` (78 a 90 bytes), layout leído de los ocho archivos:

```
u8 version(2) │ i32 LE keyHash │ i32 LE rotationDays │ u8 ? │ float64 LE (timestamp, inferred) │ u32 ? (1) │
u32 keyLen │ u32 uuidLen(36) │ key string (e.g. "id_ttl_daily") │ UUID string
```

Días de rotación leídos de los archivos: -1 (`default_ps_id`, `id_pre_metrics`), 1, 7, 30, 30, 30, 90 (ver 2.3). Las cadenas nativas nombran las operaciones `WAMPSIDProfileRotatePSID`, "psid delegated rotation was not persisted" y comprobaciones de corrupción (`invalid rotationInDays`). El UUID es lo que va al global 6005 de los buffers privados. Si la rotación la dirige la hora local o el servidor es unknown.

---

## 7. Formato de wire WAM

Confirmado en buffers reales: un decodificador escrito a partir del esquema de tags de abajo analizó globales y eventos de dos buffers (regular y privado) sin restos.

### 7.1 Codificación de entradas

Cada entrada es `[tag][field id][payload]`.

| Parte | Codificación | Tier |
|-------|--------------|------|
| Nibble bajo del tag | rol: `0` global, `1` marcador de evento, `2` campo; OR `0x04` último del grupo; OR `0x08` el field id es `u16 LE` en lugar de `u8` | found |
| Nibble alto del tag | tipo de valor: `0x00` null, `0x10` int 0, `0x20` int 1, `0x30` int8, `0x40` int16 LE, `0x50` int32 LE, `0x60` int64 LE, `0x70` float64 LE, `0x80` string (longitud u8), `0x90` string (longitud u16 LE), `0xA0` string (longitud u32 LE) | found para int 0/1, int8, int16, int32, string u8 y u16 (todos decodificados de buffers); los demás son inferred a partir del esquema y del encoder de Baileys |
| Enteros, strings, orden de bytes | forma entera más pequeña (0 y 1 viven en el tag); strings UTF-8; little-endian en todas partes (el codec de stanzas es big-endian) | found |

### 7.2 Marcador de evento

Un marcador de evento es el rol `1` con el id del evento como field id. Su valor es el peso de muestreo, almacenado en positivo en los buffers: los eventos con peso de esquema 20 (`wam_secure_file_usage`, `wam_whatsapp_quick_promotion_client_eligibility_waterfall`) llevan 20, los eventos con peso 1 llevan 1 (found). Los campos siguen con el rol `2` (el flag de último campo `0x04` no se comprobó). Se escribe un bloque global (rol `0`) cuando cambian los atributos, de modo que los globales se repiten entre eventos (el commit time 47 se reescribe muchas veces, found).

El payload del IQ es de 4 a 126,976 bytes (9). Que sea igual al buffer desde el offset 24 (el header `WAM` en adelante) no lo muestra el código; es inferred a partir del layout y de que Baileys envía el mismo header (15).

---

## 8. Muestreo y pesos por evento

### 8.1 Resolución (`C0Fg.A00`, simplificado)

```
override = prefs(code == 1094 ? "app_launch_event_sampling_weight" : "field-stats-events-sampling"[code], 0)
weight   = override != 0 ? override : schema.A00         // sampler becomes (|w|,|w|,|w|,|w|) for an override
keep     = random.nextInt(sampler.A00) == 0              // 1-in-N; null return = "(dropped)"
```

| Elemento | Valor | Tier |
|----------|-------|------|
| Overrides locales | archivo de prefs `field-stats-events-sampling` (clave = código de evento) y `app_launch_event_sampling_weight` (evento 1094); el peso 1 siempre se conserva | found |
| Guarda nativa | "wameta/logger event weight exceeds max, dropped"; el límite es nativo | found; valor unknown |
| Muestreo por llamada | `WamCall`: el campo `logSampleRatio` (id 1120) del evento decide el peso, `new C036300x(i, i)` | found |

### 8.2 Entrega desde el servidor (respuesta de AB props)

`C28894Cgv.CFS` maneja el resultado de AB-props (nodo `<props>`). Cada hijo `<prop>` es una prop de configuración o una entrada de muestreo de evento:

```
<props ab_key hash refresh refresh_id delta_update>
  <prop config_code config_value config_expo_key/>    -> ab-props
  <prop event_code="854" sampling_weight="5"/>        -> field-stats-events-sampling
</props>
```

Cuando `hash` no está vacío, las prefs de muestreo se borran y se reescriben a partir de todos los pares `event_code`/`sampling_weight`; la entrada 1094 también escribe `app_launch_event_sampling_weight` (y la elimina cuando está ausente). Por tanto, el servidor controla los pesos por evento, y los pesos se envían de vuelta con cada evento para que el servidor pueda escalar los conteos (inferred a partir del campo que viaja con el evento; uso en el servidor unknown).

El servidor, por tanto, da forma a WAM mediante AB props, pesos de muestreo y la credencial privada; nada se empuja en el propio IQ de subida (el IQ solo recibe `result`).

---

## 9. Subida regular (`w:stats`)

Nativo llama a `JniBridge.jnidispatchIO(6, bytes)`. Java construye y envía:

```
<iq xmlns="w:stats" to="s.whatsapp.net" type="set" id="..">
  <add t="<unix seconds>">[binary: WAM buffer]</add>
</iq>
```

| Elemento | Valor | Tier |
|----------|-------|------|
| Transporte | el stream de chat autenticado normal (`C10140Tq`), igual que cualquier IQ | found |
| `t`, límites, timeout | `t` = segundos unix actuales (se añade solo dentro de 1,577,865,600..4,102,473,600); payload verificado contra 4..126,976 bytes; timeout del IQ 32,000 ms (espera síncrona) | found |
| Éxito | atributo de respuesta `type == "result"` -> contabilidad `C0VI.A02(len, 32)`, devuelve 1 | found |
| Fallo | otro tipo o interrupción -> log "FieldStatsXmppImpl/error sending fieldstats IQ", devuelve 0 (el nativo decide los reintentos; existe "_WAMTransportManagerUploadFailedPermanently") | found |
| Pospuesta durante una llamada | devuelve 0 con el log "WamJniBridge/upload postponed" si hay una llamada activa, salvo que la AB prop **15507** esté activa, o la llamada sea de grupo y la AB prop **468** esté activa | found (flujo del decompilador, se asume que el valor por defecto del flag de grupo es false) |
| Pospuesta durante el procesamiento offline | devuelve 0 si `C0A2.A0N()` (conectado y mensajes offline aún sin drenar) y la AB prop **9654** está activa; con 9654 desactivada el IQ se envía | found |
| Vínculo con la cuenta / compresión | sin id de cuenta en el payload, el servidor ve la sesión autenticada; sin compresión en la ruta Java | inferred / found |

La misma prop 9654 habilita el flush en `offlineProcessComplete` (3.3). En conjunto: con 9654 activa, las subidas esperan hasta que la cola de mensajes offline esté drenada y en ese momento se ejecuta un flush (inferred a partir de los dos puntos de llamada; el momento del reintento tras un intento pospuesto es nativo y unknown).

---

## 10. Subida privada

Los canales privados (2 y 3) no se envían como `w:stats`. El `WAMTransportPrivate` nativo sube por un transporte HTTP separado (`WCIHTTPImpl`) con una credencial anónima. Todo lo siguiente proviene de cadenas de log nativas y del handler de credenciales en Java.

### 10.1 Solicitud de credencial

```
<iq xmlns="privatestats" to="s.whatsapp.net" type="get" id="..">
  <sign_credential version="1">
    <blinded_credential>[32 bytes]</blinded_credential>
  </sign_credential>
</iq>
```

| Parte | Detalle | Tier |
|-------|---------|------|
| Emisor | `JniBridge.jnidispatchIO(7, byte[32])`; el código de error en el IQ tracker es 239, timeout 32,000 ms | found |
| Respuesta (`KRL.CFS`) | `<sign_credential t=..><signed_credential/><acs_public_key/><config_id/></sign_credential>`; los tres arrays de bytes se pasan a nativo con `jvidispatchIOOOO(4, ctx, ...)`; en caso de error o sin respuesta el nativo recibe nulls | found |
| Telemetría | evento 2242 `wam_sign_credential` (canal regular) con status 3 = fallo, 1 = éxito, y tiempo transcurrido | found |
| Verificación y almacenamiento | cadenas nativas "Invalid signature received from server", "fails validation" (el cliente valida la firma); almacenada en `WAMMetadataPrivateCredential-<n>`, renovada con 401 ("send failed, renew credentials") | found |
| Esquema | solicitud cegada (blinded), respuesta firmada, clave pública ACS: una credencial anónima, de modo que la credencial no vincula las subidas privadas con la cuenta | inferred |

Un sender genérico separado `C1N8` usa el mismo namespace con `<sign_credential version="2">` y `project_name` para otros proyectos ACS (prefs `acs_token_*`); no es la ruta de WAM.

### 10.2 Subida

| Elemento | Detalle | Tier |
|----------|---------|------|
| Endpoints | logs nativos "url/received", "fetch_endpoints/custom_endpoints - got endpoints: %d", "invalid_ps_endpoint, ignoring"; sin literal de URL en Java ni en `libwhatsapp.so` | found; origen de la lista unknown |
| Manejo de fallos y temporizador | "try next endpoint", "have next credentials", "401, no more endpoints"; el temporizador del transporte ("timer/started - interval: %.1f seconds") arranca en "connection_ready", se detiene en "connection_unavailable" | found; intervalo unknown |
| Realtime privado | buffers por evento: "create_buffer/realtime/buffer-created ... event id", "sendsingleeventimpl/realtime" | found |
| Headers, framing del cuerpo, compresión | no visible | unknown |

El logger Falco `C40099Hdc` con modo 9 descarta de su propia ruta los eventos con canal 2 o 3 o con psId y los cuenta como `wa:dropped_private_stats` (found), por lo que los eventos privados no se duplican en ese logger (inferred).

---

## 11. `wam_daily` y eventos periódicos

Id de evento 1158, nombre Falco `wam_daily`, canal 0, peso 1, 218 campos numéricos / 205 con nombre. Para los campos de root, emulador, ROM personalizada y cliente modificado, ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md); aquí solo se registra la mecánica.

### 11.1 Programación (found)

| Pieza | Detalle |
|-------|---------|
| Alarma | `BEL.A01`: próxima medianoche local + jitter aleatorio `nextInt(AB prop 5529)` (unidad convertida por `C20D.A02`), acción `com.whatsapp.action.DAILY_CRON` |
| Catch-up | acción `com.whatsapp.action.DAILY_CATCHUP_CRON`, reintentada cada 15 minutos mientras "last_daily_cron" no sea de hoy |
| Guarda | se omite con "too frequent" si el cron ya corrió hoy (pref `last_daily_cron`); omite todos los crons mientras hay una transferencia de chat en curso; los crons que necesitan el message store se omiten cuando no está listo |
| Executor | itera un conjunto DI de crons `InterfaceC29983D2n` (`Bo5`); `C28643Ccj` (tag `WamDailyEventDailyCron`) corre solo cuando `anonymousClass091.BS3()` (estado de cuenta, significado no resuelto) |

### 11.2 Población

`C28643Ccj.Bo5` crea `new C0Fp()`, llama a `C4k(C0Fp)` en cada populator de un conjunto DI (28 archivos definen un populator `C4k(C0Fp)`), luego `CNW(c0Fp)` con el peso de esquema por defecto. El populator de flags de dispositivo es solo smali en este build (`smali_classes7/X/Cdt.smali`; el decompilador falla con él) y lee y escribe la pref `last_daily_event` (ms de reloj de pared), asignando `time_delta_since_last_event`. La rama decompilada cambia el delta solo de 0 a 1, por lo que no se hace ninguna afirmación de unidad ni cadencia para ese campo. `last_daily_event` no es el programador (lo es la alarma de 11.1).

El mismo cron emite un evento solo-Falco `wam_daily_permission` (muestreado): estado del permiso de contactos, permiso de galería, permisos de cámara / grabación de audio / ubicación aproximada y precisa, ajuste de notificaciones del SO, tamaños de libreta de direcciones, conteos de threads opcionales (AB prop **25576**) y `profile_photo_is_set` (AB prop **34207**), `os_version` (found).

### 11.3 Otros eventos periódicos

Otros eventos de arranque de la app y periódicos: 1094 `wam_app_launch` (peso sobrescribible por `app_launch_event_sampling_weight`), 3300 `wam_ps_app_launch` (privado, `id_pre_metrics`), 3178 `wam_clock_skew_difference_t` (privado, `id_ttl_90_days`), la familia `*_daily` (5798 `wam_reaction_daily`, 3680 `wam_polls_daily_stats`; disparadores inferred).

---

## 12. Tratamiento de privacidad

| Aspecto | Hallazgo | Tier |
|---------|----------|------|
| Ids estables en los lotes | sin JID ni número de teléfono en los atributos comunes escritos por Java; `dedup_key` y `trace_id_int` son aleatorios por evento; el canal regular se autentica mediante el stream por el que viaja | found / inferred |
| Ids de private-stats | UUID por clave en `WAMMetadataPSIDProfile-*`, global 6005 en buffers privados; rotación de 1, 7, 30, 90 días o nunca | found |
| Credencial anónima | token cegado firmado por el servidor para las subidas privadas (10.1) | found; unlinkability inferred |
| Ids hasheados y en claro | existen campos de id hasheado (`hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids`, `message_key_hash`, `invited_user_hash`; función hash no trazada); también existen strings de tipo JID (`reported_jid`, `e2e_sender_jid`; hash antes del logging no trazado) | found (nombres), unknown |
| Reset | la eliminación de cuenta y el re-registro llaman al reset nativo (`jvidispatchIO(12)`); no se muestra que reinicie los perfiles PSID | found / unknown |
| Opt-out del usuario | no se encontró ningún ajuste, cadena o flag que desactive WAM; la única cadena de tipo consentimiento en los recursos concierne a diagnósticos de soporte. Puede existir un ajuste en rutas de código no buscadas | unknown |
| Control del servidor | pesos por evento (8.2), AB props (13), configuración `throttling_*` y `beacon_probability` (4); los algoritmos son nativos | found; unknown |

---

## 13. Feature flags (AB props tal como se leen en las rutas de código anteriores)

| Prop | Tipo | Controla |
|------|------|----------|
| **9654** | bool | flush al completar el procesamiento offline (3.3); subida pospuesta mientras se drenan los mensajes offline (9) |
| **15507** / **468** / **16047** | bool | subida no pospuesta durante una llamada / durante una llamada de grupo / flush tras eventos de llamada |
| **6977**, **9822**, **12399**, **9457**, **9456**, **14310**, **15205**, **11981**, **11982** | mixto | claves de config de init del runtime (sección 4) |
| **31314** | string | tasa del disparador de subida de logs `"code:N;..."` por código de evento |
| **5529** | int | jitter del cron diario |
| **12637** | bool | omite los atributos de versión del SO, fabricante y acompañantes (15, 287, 21, 12027, 707) |
| **31830** / **25576** / **34207** | bool | lista AB privada combinada en el atributo 5029 / campos opcionales de `wam_daily_permission` |
| **34494..34507, 35169, 35170** | – | array en `AbstractC38513Goh.A01` (16 ids, misma cantidad que los Falco migration batches 1..16); uso inferred |

Todos los valores los asigna el servidor; los valores por defecto no se resolvieron.

---

## 14. Familias de eventos notables

Los nombres son nombres Falco; los ids y canales provienen de las clases de evento. Las listas de campos son los campos con nombre de `getFieldsMapForFalco()`.

### 14.1 Mensajes

| Evento | id | Canal / peso | Campos notables |
|--------|----|--------------|-----------------|
| `wam_message_send` | 854 | 0 / 5 | 89 campos: `message_send_result`, `message_send_t`, `message_type_str`, `e2e_ciphertext_type`, `e2e_ciphertext_version`, `is_pq`, `is_lid`, `retry_count`, `resend_count`, `message_is_forward`, `message_is_fanout`, `message_distribution_type`, `participant_count`, `device_count`, `message_key_hash`, `is_view_once`, efimeridad, edición/revocación, campos de bot y de IA privada |
| `wam_message_receive` | 450 | 0 / 20 | 58 campos: `message_receive_t0..t2`, `message_queue_time`, `message_is_offline`, `offline_count`, `stanza_process_count`, `padding_bytes_size`, `message_addressing_mode`, `server_addressing_mode`, `session_scope`, campos de sticker y de tarjeta de contacto |
| `wam_e2e_message_send` / `_recv` | 476 / 478 | 0 / 20 | `e2e_successful`, `e2e_failure_reason`, `e2e_destination`, `group_encryption_state`, `enc_retry_count`, `pq_receive_gate_state` |
| `wam_e2e_message_decrypt_fail_sender` | 3524 | privado (ps `none`) | `e2e_sender_jid`, `e2e_failure_reason`, `retry_count` |

### 14.2 Llamadas

`WamCall` (id 462, canal 0) se crea a partir de estadísticas nativas (`ConvertFieldStats`, "can not construct com/whatsapp/fieldstats/events/WamCall") y tiene aproximadamente 1,700 campos con nombre (1,716 sitios `put` en el mapa Falco). `WamJoinableCall` es el id 2572. El muestreo es `logSampleRatio` (campo 1120), y el evento se hace flush al terminar la llamada (3.3). Otros eventos de llamada: 2582 `wam_call_stanza_receive` (peso 1000), 3452 `wam_call_critical_events`, 4568 `wam_call_user_journey`. La señalización de llamadas en sí está en [WA_CALL_SIGNALING.md](WA_CALL_SIGNALING.md).

### 14.3 Login y registro

| Evento | id | Campos |
|--------|----|--------|
| `wam_login` | 460 | `login_result`, `login_t`, `connection_origin`, `connection_t`, `login_dns_resolver`, `login_ip_source`, `login_port`, `login_resolved_pop`, `login_socket_provider`, `noise_protocol_version`, `retry_count`, `server_error_code`, `passive`, `long_connect`, `network_is_vpn`, `android_keystore_state`, `pending_acks_count`, `unprocessed_message_count` (30 slots); ver [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) |
| `wam_reg_init` / `wam_registration_complete` | 2046 / 1342 | tiempos de init (`contacts_sync_t`, `groups_init_t`, `total_t`); 30 campos incl. `registration_t`, `addressbook_size`, `contacts_permission_authorization_status`, `device_identifier`, `google_account_list_hashed_reg`, `invited_user_hash`, `is_new_jid`, campos de foto de perfil y de permisos |
| `wam_account_encryption_attestation` | 8164 | el nombre sugiere el resultado de una attestation (inferred); ver [WA_CLIENT_INTEGRITY.md](WA_CLIENT_INTEGRITY.md) |

### 14.4 Spam, reporte, bloqueo

Los flujos están en [WA_REPORTING.md](WA_REPORTING.md) y [WA_BAN_SYSTEM_DEEP_EN.md](WA_BAN_SYSTEM_DEEP_EN.md) (`wam_wfacp_ban_action`, id 5028); lado WAM:

| Evento | id | Canal | Campos |
|--------|----|-------|--------|
| `wam_spam_report_perf` | 6310 | 0 | `report_spam_flow`, `report_status`, `report_attempt_count`, `report_duration_ms`, `report_error_code` |
| `wam_report_conversation_context` | 4608 | 0 | `reported_jid`, `spam_flow`, `estimated_num_messages_sent/received`, `is_chat_maybe_suspicious`, `is_in_addressbook`, `first_entry_point`, `num_call_msgs_to_report` |
| `wam_blocking_funnel` / `wam_reporting_funnel` | 4920 / 4924 | 0 | `block_flow_action`, `hashed_blocked_conversation_jids`, `hashed_reported_conversation_jids` |
| `wam_reporting_token_validation_failure` | 5466 | 0 | `reporting_token_validation_failure_reason`, `reporting_token_version`, `is_part_of_group_history` |
| `wam_reporting_token_validation_failure_sender`, `wam_reporting_token_additional_client_validation` | 6094, 6702 | 2 (`default_ps_id`) | variantes del lado del emisor |
| `wam_message_template_blocks` | 3002 | 2 (`default_ps_id`) | motivos de bloqueo de plantillas de negocio |

### 14.5 Experimentos

`wam_wefr_client_exposure` (id 5504, realtime) registra la exposición con `exposure_key`, `device_exp_id`, `user_lid`, `guest_id`, `is_canonical_ent_present`, `sent_with_daily`. Lleva un campo de LID de usuario (found; uso en el servidor unknown). `wam_ui_action_real_time` (2098, peso 10) lleva solo `chatd_internet_connectivity` y `dedup_key`.

---

## 15. Baileys (`baron-baileys-v2`, comparado con su código fuente)

Baileys envía los buffers WAM con el mismo IQ que el cliente Android.

| Aspecto | Baileys (`src/Socket/socket.js`, `src/WAM/encode.js`) | Android 2.26.41.6 | Tier |
|---------|--------------------------------------------------------|-------------------|------|
| Stanza de subida | `<iq to=s.whatsapp.net xmlns="w:stats" type="set"><add t=…>buffer</add></iq>` | igual | found en ambos |
| Header | `"WAM"`, byte de versión 5, byte 4 = `1`, secuencia `u16 BE` en 5, canal `0` en 7 | `"WAM"`, versión 5, byte 4 = `0`, secuencia `u16 LE` en 29, canal en 31 (en el archivo con un contenedor `WMT` delante) | found en ambos |
| Codificación de valores | `0/1` en el tag, int8, int16/int32 LE, float64 LE, strings con longitud u8/u16 LE/u32 LE, flag de id ancho `0x08` | mismos bits | found en ambos |
| Peso del evento | escrito como `-weight` | almacenado en positivo en los archivos de buffer | found en ambos |
| Canales, flush | solo regular; flush cada 30 s y tras el login, los fallos solo se registran | 0..3; rotación y transportes nativos | found |

La diferencia en el orden de bytes de la secuencia y en el signo del peso no es un error demostrado por este reporte: los archivos en disco de Android no tienen por qué ser iguales a los bytes que sube el transporte nativo, y el parser del servidor no se observó. Nada en las rutas de código de chat leídas aquí espera al estado de WAM; si el servidor reacciona ante una subida ausente o inusual es unknown (19).

---

## 16. Casos de error

| Síntoma | Causa | Solución / nota |
|---------|-------|-----------------|
| Evento ausente en los buffers | falló el sorteo del peso (1-in-N), allowlist del canal 3, tope de almacenamiento, nativo "weight exceeds max", "have to drop event" | revisar el peso 2.4 y las AB props 8.2, 4 |
| El evento diario produce eventos de validación | la regla de `ai_widget_installed` falla en cada `wam_daily` (3.2) | esperado en este build |
| "WamJniBridge/upload postponed" | llamada activa sin 15507 / 468, o cola offline aún drenando con 9654 | transitorio; el nativo reintenta (inferred) |
| "FieldStatsXmppImpl/error sending fieldstats IQ" | error de IQ, timeout (32 s) o interrupción | ruta de reintento nativo / fallo permanente |
| "Cannot log before WAM runtime is initialized" / "after ... terminated" | orden del ciclo de vida nativo | Java espera en `A0K`; terminate es un estado nativo |
| La subida privada falla con 401 | credencial rechazada | renovar mediante el IQ `privatestats` (10.1) |

---

## 17. Distinciones clave

| Par | Diferencia |
|-----|------------|
| WAM vs Falco | los eventos WAM pasan por el runtime nativo y los buffers; el logger Falco en Java (`C40099Hdc`, `FFLogger`) es una ruta paralela que reutiliza las mismas clases de evento por nombre Falco. El Falco migration batch 1..16 es por evento (`internalFalcoMigrationBatchNumber`) |
| Peso de evento vs feature flag | peso = muestreo 1-in-N y un multiplicador enviado con el evento; los flags solo controlan el comportamiento del transporte |
| Subida regular vs privada | regular = IQ `w:stats` en el stream de chat; privada = transporte HTTP separado con una credencial cegada |
| `psId` vs global 6005 | `psId` es un hash de clave estático en la clase del evento; 6005 es un UUID rotativo escrito de forma nativa en los buffers privados |
| Field id vs global id | los espacios numéricos se solapan (47 es un global; el campo 47 de un evento es distinto); el rol del tag los desambigua |
| `wam-event/<name>` vs subida WAM | el primero sube logs del dispositivo mediante el crash reporter, la segunda sube buffers de métricas |
| Buffer en disco vs payload de wire | el archivo tiene un contenedor `WMT` y relleno; el layout del payload del IQ es inferred |

---

## 18. Flujo completo

```
[App code / native call stats]  new Event(...) / ConvertFieldStats -> WamCall
    ▼
[C06650Fo.CNW / CNI]  weight = override (prefs) or schema A00, keep 1-in-N ; validate (ch 0,1) -> event 5560
    ▼
[WAM executor]  jvidispatchIIIIIOO(code, weight, psId, channel, ctx, fields)
    ▼
[libwhatsapp.so WAMRuntime]  encode TLV (LE), add globals (47 commit time, 6005 psId UUID, common attrs)
    ▼
[files/wam/wamt-a-<channel>-0-<seq>]  "WMT" container + "WAM" 5 header, 64 KiB
    │  rotate (buffer_timeout) / flush (offline-complete with 9654, Bba, call end, CXZ)
    ├── channel 0, 1 ─────────────────────────────┬── channel 2, 3 ───────────────────────────────┐
    ▼                                             ▼                                              
jnidispatchIO(6, bytes)                       jnidispatchIO(7, 32 bytes blinded token)
    │  postponed in calls / offline drain          │  <iq xmlns="privatestats" type="get">
    ▼                                             ▼
<iq xmlns="w:stats" type="set"><add t=..>     [WA server] signed_credential, acs_public_key, config_id
  bytes</add></iq>  on the chat stream              │  stored, renewed on 401
    ▼                                             ▼
[WA server] type="result" -> return 1         HTTP upload, endpoint list source unknown -> [private-stats backend]

[WA server] <props> response: event_code -> sampling_weight, config_code -> AB props  ──►  prefs (8.2)
[DailyCronAction alarm: next local midnight + jitter(5529)] -> C28643Ccj populates C0Fp (wam_daily 1158) -> CNW (same path, channel 0)
```

---

## 19. Incógnitas

| Pregunta | Por qué es unknown |
|----------|--------------------|
| Bytes exactos del payload de subida frente al archivo de buffer | transporte nativo no desensamblado; solo se vieron los límites del IQ |
| Compresión y framing de header de las subidas privadas, origen de la lista de endpoints | sin literal en Java ni en las cadenas; ruta HTTP nativa no trazada |
| Intervalo de rotación nativo, calendario de reintentos, máximo de peso, reglas de descarte, algoritmo de beaconing | código nativo stripped, sin decompilador para la librería grande usada aquí |
| Significado de los atributos 495, 6833, 2795, 105 y de varios atributos flag; campos `WMT` en los offsets 8, 16, 20; campos `MTD` | fuentes no resueltas, solo valores |
| Si algún comportamiento del servidor depende de WAM ausente o inusual | lado del servidor |
| Hash de los campos `*_jid`; presencia de un opt-out visible para el usuario | no trazado por evento / no encontrado (la ausencia no es prueba) |
| Momento de reintento nativo, disparador de rotación de PSID (hora del cliente o instrucción del servidor), valores por defecto de AB props | lógica nativa no trazada; los valores por defecto vienen de la configuración del servidor |
| Disparador de crons diarios distintos de `wam_daily` | solo se leyeron el registro de crons y el cron de `wam_daily` |
