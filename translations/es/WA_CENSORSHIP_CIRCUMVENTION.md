<!-- src-sha1: 5428e0461d6ea8f961256e4ead0fe3df30ea4164 -->
# WhatsApp Elusión de la censura — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** Alternativas de conectividad en Android cuando chatd está bloqueado: WhatsApp Proxy configurado por el usuario (interfaz de ajustes, almacenamiento, enlace para compartir, uso en chatd y media), servicio de proxy dirigido por el servidor (túnel Psiphon, módulo Voltron, restricciones de región y VPN, túnel SOCKS con cabecera PROXY v2), lista de IP de respaldo (`<ib><fbip>`, archivo `fbips`), push de desbloqueo (`fbips`, `unblocking_props`, `psl`), cadena de respaldo DNS, proveedores de relay de registro y estrategias de reintento, roles de Tigon y DGW, seguimiento del estado de conexión y diagnósticos, interacción de reintentos, feature flags, mecanismos ausentes, comparación con Baileys

---

## 1. Qué hay presente en esta compilación

Todas las afirmaciones provienen del análisis estático del APK decompilado; no se capturó nada en la red. Niveles: **found** = leído en código o recursos, **inferred** = deducido, **unknown** = no resuelto. Los nombres ofuscados son específicos de cada compilación y se volvieron a resolver en 2.26.41.6. El transporte de chatd, el handshake, la escalera de hosts y el backoff están en [WA_NOISE_TRANSPORT.md](WA_NOISE_TRANSPORT.md) y no se repiten aquí.

| Mecanismo | Estado | Puntos de entrada | Tier |
|-----------|--------|-------------------|------|
| WhatsApp Proxy (relay de chat y media configurado por el usuario) | presente, UI de usuario, bajo feature flag | `SettingsUserProxyActivity`, `SettingsSetupUserProxyActivity`, `C12660bX`, `C12690ba`, paso 12 de la secuencia de chatd | found |
| Servicio de proxy (túnel Psiphon, módulo Voltron `proxyservice`) | presente, dirigido por el servidor, sin UI de usuario | `C12760bh` (orquestador), `C42448IfJ` / `S6G`, `ca.psiphon.PsiphonTunnel`, `ProxyServiceBroadcaster` | found; la biblioteca nativa no está en el APK |
| Lista de IP de respaldo | presente | `<ib><fbip>` en `C40581l4`, `C36821d6`, archivo `fbips` | found |
| Tabla fija de host a IP, escalera de hosts | presente | `AbstractC47101wK` (18 nombres de host), `C37151de` | found |
| Cadena de respaldo DNS (plataforma / MNS, UDP a 8.8.8.8 y 8.8.4.4, fija en el código) | presente | `C36881dC`, `QG1` | found |
| Push de desbloqueo (`nt` = `unblocking`) | presente | `CLl` parser, `C28139CLl`, `C28912ChD`, `C27946CBo` | found |
| Relay de registro (proveedores de funciones en la nube) y estrategias de reintento | presente, solo para registro | `res/raw/domain_fronting_providers.tsv`, `C45421Jrl`, `RetryingHttpClient` | found |
| Tigon / DGW como respaldo de chatd | no presente | la configuración de respaldo de DGW existe pero se construye deshabilitada | found |

No presente en esta compilación (found como ausencia en el Java decompilado, el manifest y los recursos; el código nativo no se inspeccionó):

| Ausente | Evidencia |
|---------|-----------|
| chatd sobre WebSocket, HTTP long-poll o MQTT | ningún literal `wss://` ni `/ws/chat` en Java; `mqtt` solo en etiquetas de analítica y de streams de DGW (ver sección 13 del informe Noise) |
| `VpnService` de Android | ningún servicio ni `BIND_VPN_SERVICE` en el manifest; Psiphon funciona en modo de proxy local |
| Proxy SOCKS o HTTP-CONNECT configurable por el usuario para chatd | el paso 12 construye un socket directo a `host:chatPort`, sin handshake de proxy |
| Proxy del sistema (`http.proxyHost`, `https.proxyHost`) para chatd | no lo leen la secuencia ni el código de sockets; solo lo leen Tigon y una protección (sección 4.6) |
| Domain fronting o relay para chatd | la lista de proveedores solo la consume el cliente de registro (sección 7) |
| Tor, Snowflake, otros pluggable transports | no se encontró código ni recurso |

Puntos que determinan el resto del informe:

- Existen dos mecanismos de proxy independientes que nunca se ejecutan juntos: el proxy de usuario (paso 12, terminal) y el servicio de proxy Psiphon (túnel SOCKS que reemplaza las conexiones directas en un subconjunto de pasos). Con un proxy de usuario configurado, se ignora la configuración del servicio (`ConnectionSequence/socketConfigForUserProxy/skipping socks proxy in favor of user proxy`).
- Con un proxy de usuario válido la secuencia tiene exactamente un destino. El paso 12 avanza al 16 (agotada); no hay retroceso a hosts directos (found, `C37031dS.A0G`).
- `libgojni.so` se entrega dentro del módulo descargable. El APK contiene solo el manifest del módulo; el marcado del túnel, la selección de protocolo y el comportamiento anti-DPI son unknown.

---

## 2. Ubicación en la secuencia de conexión de chatd

Los números de paso son los de la sección 2.2 del informe Noise. Fuente: `C37031dS.A0G`, `C37151de`, `C37061dV`.

| Condición | Efecto |
|-----------|--------|
| Dirección de depuración definida | solo el paso 1 |
| Proxy de usuario válido (habilitado, host válido, flag **2784**) | el paso 0 va al 12, que es terminal; se ignora la configuración de Psiphon |
| Sin proxy de usuario, con configuración de Psiphon (`C37061dV.A00 != null`) | se conservan los pasos 5, 8, 13; se omiten 6, 7, 9, 10, 11, 14, 15 (`ConnectionThread/Skipping sequence N due to active proxy`); se omiten 2, 3, 4 salvo que el flag **23630** esté activo |
| Sin proxy de usuario, sin configuración de Psiphon | escalera sin modificar: 2, 3, 4, 5, 8, 9, [15], 13, 14, 6, 10, 7, 11 |

La tabla de omisión es el packed switch del bytecode de `C37031dS.A0G` (pasos 2 a 15 asignados a conservar / omitir / dependiente de flag). El paso 8 construye su configuración a partir de un literal IP sin la configuración de proxy, así que dentro de una ejecución con proxy activo se conserva pero presumiblemente se conecta de forma directa (inferred). Los pasos 5 y 13 resuelven mediante `C37151de.A03`: con configuración de Psiphon y sin proxy de usuario, la configuración de socket devuelta lleva el `ProxyServiceConfig` (`C46661vS`) y un nombre de host sin resolver, por lo que el DNS ocurre en la salida del túnel (`DNSResolutionMethod` 7 `SOCKS_PROXY`, código interno 8 en `C37181dh`).

Orden del paso 0 cuando no existe dirección de depuración (found; la rama Java decompilada del paso 1 aparece invertida, el bytecode lo confirma): proxy de usuario, luego entradas de override suministradas por el servidor (2), luego cadena de host configurada (3), luego 5.

---

## 3. WhatsApp Proxy (configurado por el usuario)

### 3.1 Entrada de ajustes y pantallas (found)

| Pantalla | Clase | Contenido |
|----------|-------|-----------|
| Settings > Storage and data > Proxy | `SettingsUserProxyActivity` (manifest `com.whatsapp.settings.ui.proxy.*`, no exportada) | interruptor `Use proxy`, línea de host, filas de estado de chat y media, elemento de menú para compartir, texto informativo (`Only use a proxy if you're unable to connect to WhatsApp. Your IP address may be visible to the proxy provider…`, enlace `whatsapp-proxy`) |
| Set up proxy | `SettingsSetupUserProxyActivity` | entrada de host, `Ports (Optional)` con `Chat port` (se muestra `Default` para 443 por defecto), `Media port` (`Default` para 587), `Use TLS`, botón de guardar |
| Entrada de búsqueda en ajustes | `C23869ARc` subclase `C215199Jq` | clave `proxy` |
| Eliminar | pulsación larga en la fila del host (`ViewOnLongClickListenerC46012K9h`, `Delete Proxy?`), acción en `KZA` | borra el host, restablece el puerto de media 587 y TLS true, estados 0, `proxy_enabled` false |

Validación: `K09.A01` (literal IP), `K09.A02` (host con `:port` opcional, regex construida a partir de `JRQ.A02`); errores `Enter a valid host`, `Enter a valid port`. El análisis de IPv6 existe en `K09.A00`.

### 3.2 Almacenamiento (found, `C12660bX`, `C12690ba`)

Archivo SharedPreferences `user_proxy_setting_pref`.

| Clave | Tipo | Valor por defecto | Uso |
|-------|------|-------------------|-----|
| `proxy_enabled` | bool | false | estado del interruptor; efectivo solo cuando el flag **2784** está activo (`C12690ba.A03`) |
| `proxy_ip_address` | string | ninguno | `host:chatPort` (`ProxySetting.A04`); el puerto se analiza al leer, por defecto 443 |
| `proxy_media_port` | int | 587 | puerto del relay de media |
| `proxy_use_tls` | bool | true | envoltorio TLS para el socket de chat |
| `proxy_connection_status` | int | 0 | estado del chat mostrado en la UI (sección 3.5) |
| `proxy_media_connection_status` | int | 0 | estado de media mostrado en la UI |

`ProxySetting` (`C45598Jv6`) = `domain`, `ip`, `chatPort`, `mediaPort`, `useChatTls`; un host que es un literal IP va a `ip`, en caso contrario a `domain`. `C12660bX.A03()` lo devuelve solo cuando está habilitado, el flag **2784** está activo y el host o la IP son válidos; este es el objeto que recibe la secuencia de conexión.

### 3.3 Enlace para compartir e importar (found)

Compartir: el elemento de menú construye `https://wa.me/proxy?host=<host>&chatPort=<n>&mediaPort=<n>&chatTLS=<true|false>` con asunto `WhatsApp Proxy` y texto `Connect to WhatsApp using proxy. <url>`.

Importar: `DeepLinkActivity` (tipo `DEEP_LINK_PROXY`, prefijo de log `PROXY:`) requiere el flag **2784**, tiene un motivo de rechazo `proxy_has_segments` (condición inferred a partir del nombre), y luego inicia `SettingsSetupUserProxyActivity` con extras `intent_host_name`, `intent_chat_port`, `intent_media_port`, `intent_use_tls`, `source=deeplink`.

| Query | Análisis | Valor por defecto |
|-------|----------|-------------------|
| `host` | string | ninguno |
| `chatPort` | int | 443 |
| `mediaPort` | int | 587 |
| `chatTLS` | ausente, `true` o `1` da true; cualquier otro valor da false | true |

La importación solo rellena previamente la pantalla de configuración; guardar sigue requiriendo al usuario (found). El manejador de `DeepLinkActivity` se leyó desde el bytecode (no se decompila a Java).

### 3.4 Uso por chatd (found)

Paso 12 (`C37151de.A02` case 12): host = `domain` o `ip`, puerto = `chatPort`, bit TLS = `useChatTls`. El host pasa por la cadena de resolvers normal (sección 6). El handshake Noise se ejecuta entonces sobre este socket (dentro de TLS cuando `useChatTls`). Guardar el proxy o conmutar el interruptor llama a `C11380Yq.A0C(...)` (reconexión forzada) y dispara `wam_user_proxy_set`.

Lo que el host del proxy hace con el stream no es visible desde el cliente. Que un relay de WhatsApp Proxy reenvía bytes de chatd en bruto se infiere (inferred) de la ausencia de cualquier intercambio SOCKS o CONNECT.

### 3.5 Otros consumidores (found)

| Consumidor | Comportamiento |
|------------|----------------|
| Subida / descarga de media | el flag **4073** hace que la autoridad de media sea `proxy-host:mediaPort`; comprobación de salud en [WA_MEDIA_UPLOAD.md](WA_MEDIA_UPLOAD.md) |
| Rutas de subida de WAM | el callback nativo `jnidispatchO(0)` devuelve `https://<proxy-host>:<mediaPort>/deidentified_telemetry` cuando el flag **4074** está activo, más los hosts de `media_conn` cuando el flag **4020** está activo (ver [WA_WAM_ANALYTICS.md](WA_WAM_ANALYTICS.md)) |
| UI de estado | `C42103IXl.A00`: 1 `Connecting…`, 2 `Connected`, 3 `Couldn't connect to proxy`, 4 `Disconnected`, 5 `No network`, otro `Not Set`; estado del chat alimentado por el observador de conexión `C28890Cgr` |
| Rutas HTTP y Tigon de Psiphon | deshabilitadas mientras exista un proxy de usuario (`C17420jn.A01`, `C12790bk`: `User proxy is set, skipping`) |
| Telemetría | `WamUserProxySet {connectionSuccess, proxySet}` (`C43286IuN`) enviado cuando el estado pasa a 2 (true) o 3 / 4 (false) y en los cambios de proxy |

---

## 4. Servicio de proxy (Psiphon)

### 4.1 Módulo y biblioteca (found)

| Elemento | Valor |
|----------|-------|
| Entrega | módulo Voltron `proxyservice` más splits por ABI `proxyservice.config.{arm64_v8a,armeabi_v7a,x86,x86_64}` en `assets/app_modules.json`; el manifest del módulo lista `assets/proxyservice/libs.txt`, `assets/proxyservice/voltron_meta_embedded_server_entries` y `lib/<abi>/libgojni.so` por split |
| Lado Java | `ca.psiphon.PsiphonTunnel` (biblioteca upstream, `loadLibrary("gojni")`, `Psi.start`, `importPushPayload`), servicio host `S6G` / `C42448IfJ`, orquestador `C12760bh`, cargador de módulo `C46743KbZ` |
| Modo | proxy HTTP y SOCKS local en `localhost`; sin `VpnService` |
| Carga de biblioteca | las bibliotecas del APK split se añaden a las fuentes de SoLoader (`proxy_service/Added module SoSource`); la cadena de log nombra `libproxyservice.so` aunque el manifest del módulo solo tiene `libgojni.so` |

`libgojni.so` no está presente en el APK (se entrega con el módulo). Su funcionamiento interno (conjunto de protocolos, marcado, cómo se usa `AdditionalParameters`) es unknown.

### 4.2 Recurso de configuración `res/raw/proxyservice_config.json` (found)

Sin cambios desde 2.26.34.4. Lo lee `C42448IfJ.getPsiphonConfig`; el marcador de formato `ClientVersion` se rellena con el versionCode de la app (`264100600`).

| Campo | Valor / uso |
|-------|-------------|
| `SponsorId`, `PropagationChannelId`, `ClientPlatform` | ids opacos de 16 hex; plataforma `meta` |
| `ServerEntrySignaturePublicKey`, `PushPayloadSignaturePublicKey`, `RemoteServerListSignaturePublicKey` | claves base64 de 32 bytes, 32 bytes y 548 bytes (tamaño RSA); el rol de verificación se infiere de los nombres |
| `AdditionalParameters` | 5300 caracteres base64 (3975 bytes), opaco, no decodificado |
| `Emit*` (dirección del cliente, avisos de diagnóstico, parámetros de red), `DisableServerEntriesReporter` | todos true; alimentan `onClientAddress`, `onDiagnosticMessage` |
| `ConnectionWorkerPoolSize`, `EstablishTunnelTimeoutSeconds` | 30, 0 |
| `TransformHostNameProbability`, `TLSFragmentClientHelloProbability` | 0.9, 0.5 (parámetros anti-DPI para el motor nativo; efecto inferred a partir de los nombres) |
| `EnableLightProxy`, `LightProxyLimitDestinationAddresses` | true; `g.whatsapp.net` y `g-fallback.whatsapp.net` en los puertos 80, 443, 5222 |

Cambios en tiempo de ejecución: un objeto JSON del flag **23879** (fuente de flags previa al login) o **23846** (fuente regular) se fusiona clave por clave sobre el archivo. El modo de importación PSL (`C42448IfJ.A03`) fuerza `DisableTunnels=true`, `EnableLightProxy=false`. Las entradas de servidor embebidas se leen de `assets/proxyservice/voltron_meta_embedded_server_entries` (o del zip del módulo) cuando el flag **23730** / **23731** está activo; formato: int32 big-endian con el recuento, luego recuento veces (longitud int32, bytes), cada entrada codificada en hex, una por línea (`C45480Jst.A01`).

Las dos fuentes de flags las elige `C17280jY.A00`: sin cuenta con sesión iniciada, o con AB props nunca refrescadas, se selecciona el conjunto previo al login. Por tanto, el servicio está diseñado para funcionar también antes del registro (inferred a partir del predicado).

### 4.3 Máquina de estados (found, `AbstractC17380jj`, `C12760bh.A0B`)

| Código | Estado | Se establece cuando |
|--------|--------|---------------------|
| 0 / 1 / 2 | `uninitialized` / `not_in_region_allowlist` / `initializing` | inicial / región rechazada (el motivo lleva la región) / inicio aceptado |
| 3 / 4 | `disabled` / `downloading_module` | restricción como `vpn_in_use` / descarga de Voltron en curso |
| 5 / 6 / 7 | `connecting` / `connected` / `disconnected` | `onConnecting` / `BmZ` (puertos listos) / `BpU` |
| 8 / 9 | `download_failed` / `library_load_failed` | fallo de instalación del módulo / `UnsatisfiedLinkError` |
| 10 | `shutdown` | `A04(reason)`, por ejemplo `country_check`, `has_external_connectivity` |

Mientras el estado es 2, 4 o 5 la pila HTTP espera al proxy: `C17420jn.A05(true)` arma un latch cuyo timeout es el flag **29362** (ms, por defecto 0, solo con sesión iniciada).

### 4.4 Disparadores de inicio y parada (found)

| Disparador | Ruta |
|------------|------|
| Arranque en frío del manejador de mensajes | el caso por defecto de `C1W6` llama a `C12760bh.A03(…, null)` |
| Reanudación de la app | `C18980me`, `C28912ChD` llaman a `A0A()` (re-notificar el túnel, o reiniciar si está detenido) |
| Push de desbloqueo con `psl` | `C28912ChD.BIb`: `A03(…, C46772Kc2(psl))`; sin `psl`, solo `A0A()` cuando `C17280jY.A02()` (flags **28186** / **28189**) |

Restricciones de inicio en `A03`:

1. Región del dispositivo = país de la SIM, si no país de la red, si no país del locale (`AbstractC16510i9`); debe estar en la lista en minúsculas separada por comas del flag **18724** (previo al login) / **18725** (`C17280jY.A03`). En caso contrario, estado 1.
2. Comprobación de VPN (`C17280jY.A01`, los flags **24068** / **24067** la omiten): una VPN activa da `vpn_in_use`, estado 3.
3. El flag **25452** decide el orden: activo, la restricción de VPN y el prober se ejecutan después de descargar el módulo; inactivo, antes.
4. Prober (flag **18875**, `Q53`): HTTP GET de la URL del flag **18871** (timeout **18874**, intentos **18873**, retraso **18872**) sobre la pila normal. Cualquier respuesta HTTP cuenta como éxito (`KUI.CF3`): `Probe succeeded. Removing proxy from http and tigon`, se establece `A0N` (conectividad externa), se retira el proxy de HTTP y Tigon, se ejecuta la comprobación de apagado.
5. Timeout del marcador de inicio: flag **25850** segundos (anotación `init_timed_out`).

Condiciones de parada:

| Condición | Resultado |
|-----------|-----------|
| Región del cliente informada por Psiphon no permitida (flag **19067** activo) | `country_check`, apagado |
| Prober exitoso (`A0N`) y sesión directa buena de chatd informada (`A0O`), flag **19613** activo | `has_external_connectivity`, apagado |
| Sesión directa buena de chatd (`HandlerThreadC12340b0.A0e`: servicio activo, sesión más larga que el flag **19372** (por defecto 5, unidad sin resolver), ruta distinta de `SOCKS_PROXY`) | `C12760bh.A09()` más `C37061dV.A00()`: servicio de proxy ignorado durante la vida del proceso (`good_direct_chatd_session`) |
| Flag **19144** negativo al inicio | ignorado durante la vida del proceso (`abprop_config`) |

### 4.5 Integración con chatd (found)

`C37061dV` (`ConnectionProxyConfig`) convierte el estado del broadcaster en el `ProxyServiceConfig` que usa la secuencia.

| Campo | Fuente |
|-------|--------|
| `address` | `localhost` cuando el túnel pesado o el proxy ligero está activo, si no vacío |
| `port` | puerto SOCKS (`ProxyServiceBroadcaster.A01(true)`: pesado, o ligero cuando está permitido) |
| `proxyServiceClientIP` | `onClientAddress` |
| `httpProxyHost`, `httpProxyPort` | `localhost` y el puerto HTTP cuando no es cero |
| `isLightProxy` | `isLightProxy()` (proxy ligero activo, túnel pesado no conectado) |

Reglas:

- La configuración se descarta cuando address o port están vacíos (`updateProxyServiceConfig`), o la región informada por Psiphon no está permitida (`dropping due to unsupported client region`).
- `C37061dV.A02` (llamado en cada inicio de conexión) devuelve la configuración solo cuando la región del dispositivo está permitida, no hay VPN activa, el servicio no está apagado y la ignorancia por vida del proceso no está activada. Cuando el flag **24645** está activo se usa la configuración en caché sin estas comprobaciones.
- El hilo de conexión puede bloquearse durante el flag **19144** ms (`awaitProxyServiceConfig`) esperando la configuración antes del paso 5 cuando aún no existe configuración.
- Una configuración cambiada activa el flag de reinicio y, cuando el flag **36306** está activo, reconecta con el motivo `proxy_service_update`.

Socket (rama else de `C37031dS.A01`, clase `C48201yM` = `ConnectionSocketTunnel`):

```java
Socket s = new Socket(new Proxy(Proxy.Type.SOCKS, new InetSocketAddress(cfg.address, cfg.port)));
s.connect(InetSocketAddress.createUnresolved(host, port), 30000);   // g.whatsapp.net / g-fallback.whatsapp.net
c37861f7.A00(out, cfg.proxyServiceClientIP, port);                    // PROXY v2 header, skipped when flag 26334 is on
```

Cabecera PROXY v2 (`C37861f7`, log `ProxyHeaderWriter`): firma de 12 bytes `0D 0A 0D 0A 00 0D 0A 51 55 49 54 0A`, `21`, familia `11` (IPv4) o `21` (IPv6), longitud de 16 bits, dirección de origen (la IP del cliente, dirección cero cuando no se puede analizar), dirección de destino cero, puerto de origen 0, puerto de destino = puerto objetivo, luego un TLV `E8 00 01 50`. El significado del TLV es unknown. Que el edge acepte o requiera la cabecera se infiere (inferred) únicamente de su presencia.

Los registros de tiempos de conexión por intento usan las etapas `DNS`, `SOCKET`, `TLS` y las pilas `PLATFORM`, `MNS`, `SOCKS_PROXY` (`C37811f2`, `EnumC37801f1`, `EnumC37821f3`).

### 4.6 Otros consumidores del proxy local (found)

| Consumidor | Clase | Comportamiento |
|------------|-------|----------------|
| Pila HTTP de WA | `C17420jn` (`WaHttpUrlConnectionWithProxyService`) | `Proxy(HTTP, localhost:httpPort)`; para hosts que terminan en `.whatsapp.net`, `.whatsapp.com`, `.fbcdn.net`, `.facebook.com`, `.instagram.com`, `.cdninstagram.com`, `.fbsbx.com` añade `X-Forwarded-For: <client IP>` y `using-wa-proxy-service: 1` |
| Clientes Tigon (MNS) | `C12790bk` (`WATigonProxyObserver`) | `setInAppProxyHostAndPort`; se omite cuando los flags **26734** / **26735** (Tigon) o **19905** / **19906** (proxy de WA) están activos, existe un proxy de usuario, `http.proxyHost` / `https.proxyHost` está definido, o el probe ya tuvo éxito |
| VoIP | `CQO`, `JNIUtils.socksProxyPort` | `Voip.updateProxy(socksPort)` cuando el flag **34525** lo permite (segunda restricción **36980** en `Buh()`) |
| WebView | `C39826HXw` | regla `PROXY_OVERRIDE` para los dominios del flag **25539** |
| Log de información de red | `C12500bH` | `network_info_socks_proxy_active[...]`, `socks_proxy_connected` / `socks_proxy_disconnected` |

Tigon también lee por sí mismo las propiedades de proxy del sistema (`TigonHttpClientBase.setSystemProxyHostAndPort`) con un interruptor de respaldo directo; esto es independiente del servicio.

### 4.7 Diagnósticos (found)

`C42448IfJ.onDiagnosticMessage` analiza `ConnectedServer:{json}` en `candidate_number`, `protocol`, `client_replay_type` (`bootstrap`, `replay`, `non-replay`), `server_entry_source`. Marcadores 79499422 (inicio), 79496324 (conexión), 79501264 (prober, anotado `has_vpn`, `has_system_http_proxy`).

---

## 5. Endpoints de respaldo y push de desbloqueo

### 5.1 `<ib><fbip>` (found, `C40581l4`, `C36821d6.A02`)

`<ib><fbip>text</fbip></ib>`: el texto se divide por `,`. Una única entrada `CLEAR` elimina el archivo. Cada entrada tiene seis campos separados por `|`:

```
ip|port|ts|ttl|secure|override       exp = (ts + ttl) * 1000
```

| Campo | Uso |
|-------|-----|
| `ip`, `port` | endpoint; código de resolver 4 (`FALLBACK`) |
| `ts`, `ttl` | expiración en ms; las entradas expiradas se eliminan al cargar |
| `secure` | bit de envoltorio TLS para el endpoint |
| `override` | las entradas true van al paso 2 (se prueban antes de `g.whatsapp.net`), las false al paso 8 (después de `:80`) |

Persistencia: archivo `fbips` en el directorio de archivos de la app, JSON `{"fbips":[{"ip","port","exp","secure","override","resolver"}]}` (`C36821d6.A00`). Los errores de carga se informan como `fallback-manager/load-error`, `save-error`.

### 5.2 Tabla fija (found)

`AbstractC47101wK`: 18 nombres de host (`e1` a `e16`, `g`, `v` bajo `.whatsapp.net`, en forma simple y con punto final), cada uno con varias direcciones IPv4. Usada por los pasos 6 / 10 y el resolver fijo. La entrada `v.whatsapp.net` no la usa ningún resolver en esta compilación (su stub de resolver devuelve null).

### 5.3 Push de desbloqueo (found)

Análisis del push (`CLl`, `PushPayloadParser/fromJSON`): valores de `nt` `pre_reg`, `post_reg`, `voip_call_offer_1on1`, `voip_call_offer_group`, `call_terminate`, `message`, `group_message`, `wfac_ban`, `unblocking`. Transportes registrados: `ADM`, `GCM`, `FBNS`. El payload se descifra (`PushEncryptionHelper`, campos `payload`, `IV`, `tag`, clave de `push:push_pkey_data`; cifrado AES-GCM inferred a partir de los nombres de campo).

`nt` = `unblocking` lleva (`UnblockingPushPayload`, `BQY`):

| Clave JSON | Campo | Tratamiento |
|------------|-------|-------------|
| `fbips` | `fbips` | dividido por `,`, pasado a `C36821d6.A02` (mismo formato que 5.1) |
| `unblocking_props` | `unblockingProps` | `version\|a\|b`; una versión mayor que 0 se ignora; dos mapas `id=value;id=value` analizados por `C27946CBo.A00`; `processPreChatdProps` aplica pares `config_code` / `config_value`, `processPostChatdProps` el segundo mapa (la asignación de mapas a fases es en parte inferred) |
| `psl` | `proxyServerList` | base64, importado en Psiphon con `importPushPayload` (`C46772Kc2`) |

Importación de `psl`: túnel activo, se importa directamente; túnel inactivo, un objeto de túnel temporal se inicia en modo de importación PSL (`DisableTunnels`), importa y se detiene (`Cold-importing push payload`). Se omite cuando el estado es `not_in_region_allowlist`. La expansión de PSL como "push server list" es inferred a partir de la clave y del campo `PushPayloadSignaturePublicKey`.

---

## 6. Cadena de respaldo DNS (found)

`C36881dC.A03` consulta primero una caché (alimentada por `fbips`, entradas con expiración; controlada por un flag), luego recorre cuatro resolvers en orden:

| # | Resolver | Código de resolver | Notas |
|---|----------|--------------------|-------|
| 0 | stub para `v.whatsapp.net` | ninguno | devuelve null |
| 1 | DNS de plataforma / MNS (`DnsCache/resolveViaMnsDns`) | 5 / 6 / 7 | reintenta una vez (`primary dns resolver failed, retrying...`) |
| 2 | secundario: DNS UDP construido a mano hacia 8.8.8.8 y 8.8.4.4 puerto 53 (`QG1`) | 1 `GOOGLE` | UDP plano, sin DoH ni DoT |
| 3 | tabla fija | 2 `HARDCODED` | `no hardcoded ips found for <host>` cuando falta |

El flag **13545** (string) enmascara resolvers: `secondary` desactiva el fijo, `hardcoded` desactiva el resolver UDP, `none` desactiva ambos (lógica de bits en `C37151de.A01`). Los errores `EPERM` se relanzan cuando un interruptor controlado por flag está activo. Los códigos de resolver llegan a `ClientPayload.dnsSource` (sección 6.5 del informe Noise).

---

## 7. Relay de registro (found)

Alcance: HTTP de registro (`RegistrationHttpManager` = `K49`, `KotlinRegistrationBridge`, `RetryingHttpClient`) hacia `https://v.whatsapp.net`. No toca chatd.

### 7.1 Lista de proveedores

Recurso `res/raw/domain_fronting_providers.tsv`, columnas `name`, `url template`, `host`:

| Nombre | Plantilla | Host |
|--------|-----------|------|
| `amazon` | `https://y9yrsygcg6.execute-api.us-east-1.amazonaws.com/s/s?_={PATH}&{QS}` | `y9yrsygcg6.execute-api.us-east-1.amazonaws.com` |
| `google` | `https://us-central1-propane-fusion-170222.cloudfunctions.net/s?_={PATH}&{QS}` | `us-central1-propane-fusion-170222.cloudfunctions.net` |

`C45421Jrl` la carga (las líneas con menos de 3 tokens registran `domain-fronting-providers/load/bad-line`) y mantiene tres listas: alcanzables (`A05`), sin probar (`A06`), inalcanzables (`A04`). `K49.A0K` las entrega a cada llamada de registro en ese orden.

### 7.2 Probe

`EULA.onCreate` inicia el probe como máximo cada 900000 ms (se omite cuando `C06810Gk(930).A07()`, significado sin resolver): abre `https://v.whatsapp.net`; ante `IOException` (`DomainFrontingManager/probe-regd/cant connect to regd`) baraja los proveedores y hace GET a cada plantilla con `{PATH}=/` y `{QS}` vacío, timeout de conexión y lectura de 60 s, cabeceras `Host` = host del proveedor y el user agent de la app. HTTP 200 mueve un proveedor a la lista de alcanzables, cualquier fallo a la de inalcanzables (`domainFrontingProvider/cant reach`).

### 7.3 Estrategias de intento (`RetryingHttpClient`, `C44407JaE`, `C44975Jk4`)

| Estrategia | Solicitud | Estado en 2.26.41.6 |
|------------|-----------|---------------------|
| `ORIGINAL` | URL normal | siempre el intento 1 |
| `HOST` | misma URL con una IP dada | la lista está vacía en esta compilación |
| `PROXY` | a través de una IP de proxy dada | la lista está vacía en esta compilación |
| `DOMAIN_FRONTING` | plantilla con `{PATH}` y `{QS}` reemplazados por la ruta original y la query en bruto; cabeceras `Host` = host del proveedor, `X-Forwarded-Host` = host original | hasta la lista de proveedores |

Orden: ORIGINAL, entradas HOST, entradas PROXY, proveedores; como máximo 4 intentos. El host de la URL y la cabecera `Host` son iguales en ambas plantillas, por lo que es un relay mediante funciones en la nube (solicitud reenviada por el proveedor a `X-Forwarded-Host`, inferred) y no un fronting clásico de SNI / Host.

Regla de reintento: los códigos de resultado 2, 5, 7, 12 no son reintentables (`non-retryable error`), cualquier otro fallo continúa (`failed attempt N ... reason`); el significado de los códigos está sin resolver. Retraso antes del intento `n` > 1:

```
delay = clamp(r * (n*n - 1) * 4 * 1000, 0, 60000) ms      // r from a random double, assumed uniform in [0,1)
```

`RetryingHttpClient/executePostWithRetry/applying backoff`, `all retries exhausted`. Los flags de payload de atestación de endpoint por ruta están en `AbstractC44143JQf` y no guardan relación con el relay.

---

## 8. Tigon y DGW

| Elemento | Estado | Tier |
|----------|--------|------|
| Tigon HTTP (`TigonHttpClient`, clientes MNS) | cliente HTTP(S); toma el proxy HTTP de Psiphon y las propiedades de proxy del sistema (sección 4.6); no es un transporte de chatd | found |
| Cliente DGW (`AbstractC20460pC`) | construido con dominio `gateway.facebook.com`, configuración de respaldo `null`, configuración de personalización `null` | found |
| `DGWFallbackConfig` | `isFallbackEnabled`, `fallbackDomain`, `numFailuresForFallback`, `fallbackReasons`, `isHardcodedIpFallbackEnabled`; null produce todo desactivado; el builder Java nunca lo habilita, los valores por defecto nativos son unknown | found / unknown |
| Usuarios de DGW | solo `WaFalcoStreamingRegistration` (streaming de telemetría); ver sección 13 del informe Noise | found |

Las cadenas nativas (`distribgw_tigon_tunnel`, `DGW_MQTTBYPASS`, etiquetas de throttling y zero-rating) describen el funcionamiento interno de DGW. Nada vincula DGW con la recuperación de un chatd bloqueado (inferred por ausencia).

---

## 9. Seguimiento del estado de conexión y diagnósticos

| Elemento | Dónde | Contenido |
|----------|-------|-----------|
| Persistencia de la secuencia | prefs `connection_sequence_state`, `connection_sequence_attempts`, `last_successful_connection_step`, `_host`, `_port` | punto de reanudación, paso HISTORY (Noise report 2.2) |
| Registros por intento | `C37811f2` | etapa `DNS` / `SOCKET` / `TLS`, pila `PLATFORM` / `MNS` / `SOCKS_PROXY`, tiempos, error |
| Payload | `ClientPayload.dnsSource`, `connectAttemptCount` | resolver o ruta que produjo el socket |
| Servicio de proxy | `C12760bh.A06()`, `A08()` | código de estado (4.3); `A08()` devuelve `both`, `heavy`, `light` o null |
| Proxy de usuario | estados de `user_proxy_setting_pref`, `wam_user_proxy_set` | UI y analítica |
| Log de información de red | `C12500bH` | `network_info_is_vpn`, `_is_airplane`, `_is_data_saver`, `_is_cellular_enabled`, `_socks_proxy_active`, `socks_proxy_connected` / `_disconnected` |
| Etiquetas de log | `proxy_service/`, `ConnectionProxyConfig/`, `WaConnectivityProber/`, `WATigonProxyObserver/`, `ConnectionThread/Skipping sequence` | restricciones y cambios de estado |

---

## 10. Interacción de reintentos y backoff

El backoff en sí (unidades Fibonacci, límite de 15 minutos, alarmas) está en la sección 10 del informe Noise. Esta función añade:

| Interacción | Efecto |
|-------------|--------|
| Proxy de usuario guardado, conmutado, eliminado | reconexión forzada (`C11380Yq.A0C(...)`) |
| Cambios en la configuración del servicio de proxy | reinicio de la secuencia; reconexión `proxy_service_update` cuando el flag **36306** está activo |
| Proxy de usuario definido | secuencia de un paso; cada intento fallido vuelve al backoff de conexión completa |
| Espera de configuración / espera HTTP | el hilo de conexión se bloquea hasta el flag **19144** ms antes del paso 5; la pila HTTP hasta el flag **29362** ms mientras el servicio arranca |
| Registro | límite propio de 4 intentos y retraso cuadrático (sección 7.3), no compartido con chatd |

---

## 11. Feature flags (ids tal como se leen en el código; los valores son del lado del servidor)

| Id | Tipo | Controla |
|----|------|----------|
| **2784** | bool | función de proxy de usuario (estado habilitado, deep link) |
| **4020**, **4073**, **4074** | bool | hosts de media_conn hacia nativo; media vía proxy de usuario; ruta de telemetría vía proxy de usuario |
| **18875** | bool | prober de conectividad |
| **18871**-**18874** | string, ints | URL del probe, retraso, intentos, timeout |
| **18724**, **18725** | string | regiones permitidas (previo al login / fuente regular) |
| **19067** | bool | recomprobación de región al conectar |
| **19613** | bool | apagado ante conectividad externa |
| **19144** | int | espera de configuración en ms; negativo ignora el servicio durante el proceso |
| **19372** | int | umbral de sesión buena (por defecto 5) |
| **19905**, **19906**, **26734**, **26735** | bool | deshabilitan el proxy de WA para HTTP / Tigon (previo al login / regular) |
| **23630** | bool | pasos 2-4 permitidos bajo proxy (declarado activo por defecto, inferred) |
| **23730**, **23731** | bool | entradas de servidor embebidas (previo al login / regular) |
| **23846**, **23879** | JSON | override de la configuración de Psiphon (regular / previo al login) |
| **24067**, **24068** | bool | permiten el servicio mientras hay una VPN activa |
| **24645** | bool | usar la configuración de servicio en caché sin restricciones |
| **25452** | bool | orden de la restricción de VPN y el prober respecto a la descarga del módulo |
| **25539** | string | lista de dominios permitidos del proxy de WebView |
| **25850** | int | timeout del marcador de inicio en segundos |
| **26334** | bool | omitir la cabecera PROXY v2 |
| **28186**, **28189** | bool | reanudar el servicio en push sin `psl` |
| **29362** | int | espera HTTP por el proxy en ms |
| **34525**, **36980** | bool | pasar el puerto SOCKS a VoIP |
| **36306** | bool | reconectar ante actualización del servicio de proxy |
| **13545** | string | máscara de resolvers DNS |

Los flags de la escalera de chatd y de keepalive (**20801**, **22916**, **30712**, **33512**, **7831**-**7834**, **15103**) están en la sección 12 del informe Noise.

---

## 12. Baileys (`baron-baileys-v2`, verificado contra su código fuente)

| Aspecto | Baileys | Android 2.26.41.6 |
|---------|---------|-------------------|
| Transporte | WebSocket `ws` hacia `wss://web.whatsapp.com/ws/chat` (`waWebSocketUrl`) | TCP Noise en bruto |
| Proxy | `config.agent` pasado a `new WebSocket(url, { agent })`; las subidas usan `fetchAgent` | relay de WhatsApp Proxy, túnel Psiphon |
| Hosts de respaldo | una URL configurable | escalera de `g`, `g-fallback`, `eN`, puertos 443 / 5222 / 80 |
| `<ib><fbip>`, push de desbloqueo | no gestionado | gestionado |

```ts
const sock = makeWASocket({ agent: new SocksProxyAgent(proxyUrl), fetchAgent: new SocksProxyAgent(proxyUrl) })
```

| Por qué falla | Causa | Solución |
|---------------|-------|----------|
| Un host de WhatsApp Proxy de Android rechaza a Baileys | el relay habla TCP Noise en bruto en el puerto de chat (inferred); Baileys envía un upgrade de WebSocket | usar un proxy HTTP o SOCKS que llegue a `web.whatsapp.com` |
| Sin recuperación tras un bloqueo | sin gestión de `fbip`, sin canal push | proporcionar un nuevo `agent` o URL |

---

## 13. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `Couldn't connect to proxy` | host del proxy de usuario inalcanzable o ajuste TLS incorrecto | comprobar host, `Chat port`, `Use TLS`; la secuencia no tiene respaldo directo |
| `Enter a valid host` / `Enter a valid port` | validación en `K09` | corregir la entrada |
| El enlace de proxy no hace nada | flag **2784** desactivado, o segmentos de ruta adicionales (`proxy_has_segments`) | ninguna del lado del cliente |
| `proxy_service/Proxy service detected user region not in region allowlist.` | región informada por Psiphon rechazada por la lista del flag **18724** / **18725** | ninguna del lado del cliente |
| Estado `disabled`, motivo `vpn_in_use` | VPN activa, flags **24067** / **24068** desactivados | desactivar la VPN o el flag |
| `RetryingHttpClient/executePostWithRetry/all retries exhausted` | todos los intentos fallaron | esperar; el límite es 4 |

---

## 14. Distinciones clave

| No confundir | Detalle |
|--------------|---------|
| Proxy de usuario vs servicio de proxy | proxy de usuario = host elegido, paso 12, terminal, enlace para compartir; servicio de proxy = túnel SOCKS Psiphon dirigido por el servidor para los pasos 5 y 13; se excluyen mutuamente |
| `C48201yM` vs paso 12 | `C48201yM` es el socket de túnel SOCKS del servicio de proxy; el paso 12 es el proxy de usuario y usa un socket plano o TLS |
| Proxy ligero vs túnel pesado | el proxy ligero se limita a los seis destinos `g` / `g-fallback` listados; el túnel pesado es la sesión Psiphon completa |
| `fbip` vs push `fbips` vs `fallback_*` | `<ib><fbip>` y el push `fbips` dan IP de respaldo de chatd; `fallback_hostname` / `fallback_ip*` son atributos de `media_conn` (sección 16 del informe Noise) |
| Relay de registro vs chatd | la lista de proveedores nunca alimenta la secuencia de chat |
| WhatsApp Proxy vs proxy del sistema | el proxy del sistema no se lee para chatd |

---

## 15. Flujo completo

```
[Operator]  push nt=unblocking {fbips, unblocking_props, psl}   or   <ib><fbip>...</fbip></ib>
     │  fbips file updated ; props applied ; psl imported (temporary tunnel if inactive)
     ▼
[Client]  C12760bh gates: region (SIM > network > locale), no VPN, flags ; Voltron proxyservice download
     │  PsiphonTunnel.startTunneling(embedded entries) ─► localhost SOCKS + HTTP ports ─► state 6
     ▼
[ProxyServiceBroadcaster]  C37061dV builds ProxyServiceConfig ─► sequence reset ("proxy_service_update")
     │
     ├── user proxy set ─► step 12 only: host:chatPort (+TLS) ─► Noise ─► end (no direct fallback)
     ▼
[ConnectionThread]  steps 5, 13 (2-4 if flag 23630) ─► SOCKS CONNECT g / g-fallback (unresolved host)
     │  PROXY v2 header (client IP) ─► Noise handshake (Noise report section 4)
     ▼
[Server]  login success; session > threshold and route != SOCKS_PROXY ─► proxy ignored for the process
     ▼
[Failure]  timeout / socket error ─► next step ─► exhausted ─► Fibonacci backoff (Noise report section 10)

[Registration]  v.whatsapp.net ─► ORIGINAL ─► relay providers (Host + X-Forwarded-Host) ─► <= 4 attempts
```

---

## 16. Unknowns

| Elemento | Estado |
|----------|--------|
| Cualquier comportamiento en la red (túnel, aceptación de PROXY v2, respuesta del relay, reenvío de WhatsApp Proxy) | no se capturó nada; ningún elemento es `tested` |
| Funcionamiento interno de `libgojni.so`, protocolos, `AdditionalParameters`, contenido de las entradas embebidas | módulo nativo no incluido en el APK |
| Contenido de la lista de regiones permitidas, URL del probe, todos los valores de flags | del lado del servidor |
| Significado del TLV `E8 00 01 50` en la cabecera PROXY v2 | unknown |
| Asignación de los dos mapas de `unblocking_props` a las fases pre y post chatd, cifrado del push | en parte inferred |
| Unidad del flag **19372**, significado de los códigos en el reintento de registro (2, 5, 7, 12), predicado detrás de `C06810Gk(930).A07()` | sin resolver |
| Enrutamiento entrante de `wa.me/proxy` antes de `DeepLinkActivity` (los filtros del manifest cubren `wa.me`) | no rastreado más allá de la activity |
| Si la configuración de respaldo de DGW del lado Java permanece desactivada en nativo, y cualquier respaldo solo nativo | unknown |
| Comportamiento de las entradas del paso 8 dentro de una ejecución con Psiphon activo | inferred directo |
