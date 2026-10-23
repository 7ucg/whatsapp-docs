<!-- src-sha1: 8e15828bcc50ba6f6a9c5388872afeef15451af0 -->
# WhatsApp USync — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** USync IQ (`xmlns="usync"`): modos, contextos y tipos de sync, estructura de los stanzas de solicitud y respuesta, protocolos de consulta (contact, sidelist, status, text_status, picture, business, devices, disappearing_mode, lid, username), búsqueda de contactos y descubrimiento de números de teléfono, sync de la lista de dispositivos, verificaciones de key-index y ADV, mapeo de LID, enriquecimiento con privacy-token, MEX `UsyncQuery` y enrutamiento por protocolo, límites de tasa y backoff, disparadores del cliente, feature flags, comparación con Baileys

---

## 1. Qué es (técnicamente)

USync es la consulta masiva "quién es este usuario". Un IQ lleva una lista de usuarios y una lista de protocolos (tipos de datos); el servidor responde por usuario y por protocolo. La misma forma de stanza sirve para cuatro tareas: subida y descarga de la libreta de direcciones, búsquedas individuales de números de teléfono, actualización de datos de perfil (status, picture, business, disappearing mode) y actualización de la lista de dispositivos para el fan-out de mensajes. Todas las afirmaciones provienen de análisis estático del APK decompilado; nada se capturó en la red. Niveles: **found** = leído en el código, **inferred** = deducido, **unknown** = no resuelto. Los nombres ofuscados son específicos de cada build y se volvieron a resolver en 2.26.41.6.

| Capa | Nombre en 2.26.41.6 | Función |
|-------|----------------|------|
| Constructor / parser de stanza | `C18670m9` (log tag `UniSyncProtocolHelper`): `A06` construye, `A07` envía, `CFS` resultado, `Brt` error de iq, `Bog` fallo de entrega | construye `<iq xmlns="usync">`, parsea el resultado `<usync>` |
| Modelo de solicitud | `A05` (tipo + usuarios + opciones), `A0A` (constructor por usuario), `C222649hm` (solicitud por usuario), `C222589hg` (solicitud pendiente, una por iq id) | qué preguntar |
| Tipo de sync | `EnumC21760rz` (30 valores), `EnumC21770s0` contexto, `EnumC21780s1` modo, `EnumC21790s3` alcance | origen de los atributos `mode` / `context` |
| Búsquedas individuales | `C23638AId` (`ContactQuerySync`) | número de teléfono, JID, username, LID a username |
| Sync por lotes | `C18580m0` (`ContactSyncHelper`), callback anónimo `X.0m7` | sync multiprotocolo, elección MEX vs clásico, prefs de backoff |
| Puntos de entrada públicos | `C18230lP` (`ContactSyncMethods`), constructor `C21810s5`, solicitud `C21830s7`, conjunto de protocolos `C21820s6`, motivo `EnumC21800s4` (77 valores) | todas las funciones los llaman |
| Aplicador de resultados | `N27` (`contactsyncresultupdater`), `C51909N4g` (`ContactSyncDevicesUpdater`) | escribe BD, mapa LID, dispositivos |
| Dispositivo / ADV | `C23310uY` (`DeviceSyncManager`), `SyncDevicesJob`, `C24230w2` (`DeviceADVInfoHandler`) | jobs de actualización de dispositivos, verificación de key-index |
| Enriquecimiento de privacidad | `C223659jg` (`ProfilePrivacyEnrichmentFetcher`), `C197138a8`, `C197148a9` | tctoken y grupo común por usuario |
| Variante MEX | `C229259vZ` (`MexUsyncQueryHelper`), `M4I` (ruta), `M5H` (bit de protocolo) | `UsyncQuery` y enrutamiento |
| Almacén de backoff | `C18800mM`, archivo de prefs `contact_sync_prefs` | `*_sync_backoff`, `*_full_sync_wait` |

Puntos decisivos:

- El constructor de Android emite diez hijos de consulta: `contact`, `sidelist`, `status`, `text_status`, `picture`, `business`, `devices`, `disappearing_mode`, `lid`, `username`. **No** tiene hijo `bot` ni hijo feature (found, todas son constantes string de `A06`). `reachability`, `linked_profiles`, `orgs` y `ddm` existen solo en la variante MEX (sección 8).
- Android tiene cuatro modos y diez contextos (sección 2); cada solicitud lleva `sid`, `index="0"`, `last="true"` en los puntos de entrada leídos.
- Los usuarios van en `<list>` (normal) o `<side_list>` (contactos fuera de la libreta de direcciones).
- Las solicitudes de perfil llevan una prueba de privacidad por usuario (tctoken almacenado, o un JID de grupo común), ver sección 7 y WA_TCTOKEN_CSTOKEN.md.
- Las búsquedas por username se tratan en WA_USERNAME.md; este informe solo registra las partes compartidas del stanza.

---

## 2. Envoltorio del stanza

### 2.1 Solicitud (found, `C18670m9.A06`)

```xml
<iq xmlns="usync" id="0AB1" type="get">                       <!-- `to` added by the sender, inferred -->
  <usync sid="sync_sid_query_<uuid>" index="0" last="true"
         mode="query" context="interactive" [allow_mutation="true"]>
    <query>                                                   <!-- protocol children, section 3 -->
      <contact [addressing_mode="lid"]/> <devices version="2"/> <picture type="preview" size="N"/> ...
    </query>
    <list>      <user jid="..." [common_gid="..."]> per-user children </user> ... </list>
    <side_list> <user jid="LID" pn_jid="PN"> ... </user> ... </side_list>
  </usync>
</iq>
```

| Parte | Regla (código) |
|------|-------------|
| iq `id` | `C10140Tq.A0G()`: `"0"` + hex de un contador, da la vuelta en 65536 (registra "iqId too large") |
| `sid` | `AbstractC43461pq.A00(prefix)` = prefijo + `_` + UUID aleatorio; prefijos `sync_sid_query`, `ContactSyncHelper/sync_sid_<scope>`, `..._mex_profile` |
| `index` / `last` | de la llamada: `A07` siempre pasa `0` y `true` |
| `mode`, `context` | `EnumC21780s1.modeString`, `EnumC21770s0.contextString` del tipo de sync |
| `allow_mutation="true"` | se establece cuando `A05.A04` es true: se construye para tipos full / delta cuando se cumple `C11980aQ.A0G()` (significado no trazado) |
| hijo contact | presente cuando alguna solicitud pide contact (`A05.A03`) o cuando no se pide ningún otro protocolo |
| contexto REGISTRATION | se envía mediante `C10140Tq.A0A(...)` en lugar de `A06(...)` (found); diferencia no trazada |
| Opciones de envío | argumento de timeout del iq 32000 ms (`ContactQuerySync`) o 128000 ms (`ContactSyncHelper`); el numérico `102` pasado al sender (significado unknown) |

### 2.2 Modos (found, `EnumC21780s1`)

| `mode` | Significado |
|--------|---------|
| `full` | resync completo del alcance |
| `delta` | solo los cambios desde el último sync |
| `query` | búsqueda de los usuarios listados, sin cambio de estado |
| `download` | descarga el conjunto de contactos del lado del servidor |

### 2.3 Contextos (found, `EnumC21770s0`)

`metadata`, `registration`, `interactive`, `background`, `notification`, `message`, `add`, `voip`, `snapshot`, `wamo`.

### 2.4 Tipos de sync (found, `EnumC21760rz`)

Nombre, código de wire, contexto / modo / alcance. Los códigos 10-15 y 17-20 no se usan. Alcance `PB` = libreta telefónica, `SL` = side list, `MP` = consulta multiprotocolo. El código se registra y se guarda en métricas; el stanza lleva solo contexto y modo.

| Nombres (código) | Contexto / modo | Alcance |
|--------------|----------------|-------|
| `REGISTRATION_FULL` (0) | registration / full | PB+SL |
| `INTERACTIVE_FULL` (1), `INTERACTIVE_DELTA` (2) | interactive / full, delta | PB+SL |
| `BACKGROUND_FULL` (3), `BACKGROUND_DELTA` (4) | background / full, delta | PB+SL |
| `NOTIFICATION_CONTACT` (5) | notification / delta | PB |
| `INTERACTIVE_QUERY` (6), `ADD_QUERY` (9) | interactive / query, add / query | PB |
| `NOTIFICATION_SIDELIST` (7) | notification / query | SL |
| `INTERACTIVE_DELTA_SIDELIST` (8) | interactive / delta | SL |
| `BACKGROUND_QUERY_PICTURES` (16), `BACKGROUND_MULTI_PROTOCOL_QUERY` (21), `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` (22) | background / query | MP |
| `REGISTRATION_COMPANION_MULTI_PROTOCOL_QUERY` (23) | registration / query | MP |
| `INTERACTIVE_MULTI_PROTOCOL_QUERY` (24), `MESSAGE_MULTI_PROTOCOL_QUERY` (25), `VOIP_MULTI_PROTOCOL_QUERY` (26) | interactive, message, voip / query | MP |
| `NOTIFICATION_MULTI_PROTOCOL_QUERY` (27), `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY` (28) | notification / query | MP |
| `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` (29), `WAMO_MULTI_PROTOCOL_QUERY` (38) | message, wamo / query | MP |
| `CONTACT_DONWLOAD` (30, sic) | background / download | PB |
| `CONTACT_FORCE_UPLOAD` (31) | metadata / delta | PB+SL |
| `CONTACT_UPLOAD` (32), `NATIVE_CONTACT_DELTA` (39) | background / delta | PB |
| `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` (33) | background / full | PB |
| `CONTACT_UPLOAD_SNAPSHOT` (34), `CONTACT_DOWNLOAD_SNAPSHOT` (35), `CONTACT_FULL_SYNC_SNAPSHOT` (36) | snapshot / delta, download, full | PB, PB, PB+SL |
| `CONTACT_RESTORE_FULL_SYNC` (37) | background / full | libreta de direcciones de WA |

Helpers: `A00()` = delta, `A01()` = full, `A02()` = full y registration. Solo `BACKGROUND_QUERY_PICTURES` hace que el tipo de consulta de picture sea `image`; todos los demás tipos piden `preview`.

---

## 3. Protocolos de consulta

### 3.1 Resumen (found)

| Protocolo | Hijo de `<query>` | Hijo de solicitud por usuario | Hijo de respuesta (por usuario) | Notas |
|----------|-----------------|------------------------|---------------------------|-------|
| contact | `<contact/>` | `<contact>+digits</contact>`, `<contact username=.. lid=.. pin=../>`, `<contact type="delete"/>`, `<contact/>` vacío | `<contact type="in\|out\|invalid">text</contact>` | solo en `<list>` |
| sidelist | `<sidelist [addressing_mode="lid"]/>` | `<sidelist type="delete"/>` | `<sidelist type=..>` en `<side_list>` | usuarios fuera de la libreta de direcciones |
| status | `<status/>` | `<status t="secs"/>` cuando existe una hora en caché | `<status t code type>text</status>` | texto de Info |
| text_status | `<text_status/>` | ninguno | `<text_status last_update_time ephemeral_duration_sec text><emoji content/></text_status>` | flag **5839** |
| picture | `<picture type="image\|preview" [size="N"]/>` | `<picture id="N"/>` id en caché | `<picture id direct_path hash/>` | enriquecido con privacidad |
| business | `<business><verified_name/><profile v="N"/></business>` | `<business><verified_name serial/><profile tag/></business>` | `<business pn_jid><verified_name verified_level host_storage actual_actors privacy_mode_ts>cert</verified_name>...</business>` | `v` = AB **471** & 0x3FFC (por defecto 1140) |
| devices | `<devices version="2"/>` | `<devices device_hash ts expected_ts/>` | `<devices><device-list><device id key-index is_hosted/></device-list><key-index-list ts expected_ts>bytes</key-index-list></devices>` | sección 5 |
| disappearing_mode | `<disappearing_mode/>` | ninguno | `<disappearing_mode duration t ephemerality_disabled/>` | `ephemerality_disabled` se lee solo con el flag **21235** |
| lid | `<lid/>` | `<lid jid="LID"/>` cuando el usuario PN tiene un LID conocido | `<lid val="LID"/>` | sección 6 |
| username | `<username/>` | `<username username="@known"/>` | `<username>text</username>` o `contact@username` | ver WA_USERNAME.md |

Atributos por usuario en `<user>`: `jid` (PN o LID), `pn_jid` (entradas de side list), `common_gid` (sección 7). Un usuario también puede contener un hijo `<tctoken>` con los bytes del token almacenado. En las respuestas `<user>` también tiene `pn_jid` y `new_jid`; el parser toma `jid` y recurre a `pn_jid` cuando falta `jid`.

### 3.2 Contact (found)

| Forma | Condición | Notas |
|------|-----------|-------|
| `<contact>+15550001111</contact>` | búsqueda por teléfono | la cadena del número se pasa tal como la entrega el llamador; en búsquedas basadas en JID, `C23638AId.A05` antepone `+` cuando el JID es un JID de número de teléfono y (`C11980aQ.A0M()` / AB **26739** está activo, o el tipo es `ADD_QUERY`) |
| `<contact>15550001111</contact>` | usuario PN con direccionamiento LID (`C11980aQ.A0L()`, AB **14565**) | dígitos sin `+` |
| `<contact username="u" [lid=".."] [pin=".."]/>` | búsqueda por username | `lid` / `pin` solo con AB **12402**, de lo contrario solo `username` |
| `<contact type="delete"/>` | solicitud marcada como eliminada | eliminación de la libreta de direcciones en el sync de subida |
| `<contact/>` | usuario LID sin username | marcador de posición |
| query `<contact addressing_mode="lid"/>` | AB **14565** | sync de contactos con direccionamiento LID |
| query `metadata_version="3"` | tipo delta y un flag interno | el flag solo se asigna desde una constante false en la ruta leída, por lo que probablemente nunca se envía (inferred) |

`type` de la respuesta: `in` = registrado (código interno 1), `out` = no registrado (2), `invalid` = número no válido (3); cualquier otro valor lanza un error de stream corrupto. El contenido de texto de cada `<contact>` se agrega a una lista por usuario.

`<result><contact version refresh integrity snapshot_recovery>` a nivel de resultado: `version` se conserva en el resultado, los segundos de `refresh` alimentan la espera del full sync (sección 9), `integrity` es `pass` (por defecto), `pending` o `timelock` (internos 1 / 2 / 3), `snapshot_recovery` (`pending` / `pass`) se lee solo con el flag **22410**.

### 3.3 Status y text status (found)

Manejo del resultado de `<status>`: `type="fail"` con `code` 401 / 403 / 404 = oculto por privacidad (estado interno 2); otro `fail` = fallo (0); texto no vacío sin error = establecido (1, `t` * 1000 = hora de establecimiento); vacío sin error y con el flag de text-status desactivado = ninguno (3). Los nombres de los estados son inferred.

Con el flag **5839** activo, un hijo `<text_status>` sobrescribe el estado 1 / 3: texto = `text`, emoji = `<emoji content>` (por defecto "" cuando falta), hora de establecimiento = segundos de `last_update_time`, expiración = hora de establecimiento + `ephemeral_duration_sec` cuando es mayor que 0 (estado 3). Un status oculto (estado 2) es un nodo de fallo con 401 / 403 / 404, no una cadena vacía.

### 3.4 Picture, business, disappearing mode (found)

| Protocolo | Detalle de la solicitud | Parseo de la respuesta |
|----------|----------------|------------------|
| picture | `type="preview"` más `size` solo cuando AB `AbstractC36291cD.A06` es mayor que 0 (limitado a 300); `id` por usuario solo cuando existe un id en caché | `id` (int, -1 cuando no hay `<picture>`), `direct_path`, `hash` |
| business | `profile v` = `C35756Fe7.A00()` = AB 471 & 16380; `serial` / `tag` por usuario solo de la fila business local | `pn_jid` (rellena el PN de un usuario LID y guarda el par LID-PN), `verified_name`: `verified_level`, `host_storage`, `actual_actors`, `privacy_mode_ts`, bytes del nodo = certificado |

---

## 4. Búsqueda de contactos y descubrimiento de números de teléfono

### 4.1 Búsquedas individuales (found, `C23638AId`)

| Método | Tipo | Construye | Resultado |
|--------|------|--------|--------|
| `A0E(userJid, type, n)` | solo `INTERACTIVE_QUERY` o `ADD_QUERY` | JID de usuario + contact, status, picture, business, disappearing_mode, lid, username; devices si **5751**; text_status si **5839** | `C43621q7` |
| `A0C` / `A0A(type, n, number)` | los mismos dos tipos | número de teléfono como `<contact>`; mismo conjunto (status solo cuando el llamador pasa true) | `Pair(result, user)` |
| `A0B(type, n, number)` ("Lightweight") | cualquiera | teléfono + contact, lid; devices si **5751** | `Pair` |
| `A0D(type, numbers)` | cualquiera | muchos números: contact, status, picture, business, disappearing_mode, lid; text_status si **5839** | arreglo de usuarios |
| `A0F(lid)` | `INTERACTIVE_QUERY` | `<user jid=LID/>` + `<contact/><username/>` | username de un LID |
| `A0G(username, key)` | `INTERACTIVE_QUERY` | username (+ key) como `<contact>`; además status, picture, business, disappearing_mode, lid, username solo si **33609** es false, text_status si **5839** | WA_USERNAME.md |

Guardas (found): comprobación de red (resultado `network_unavailable`), mapas de deduplicación en curso con clave JID o número (la segunda llamada devuelve "skip too frequent query", sin ventana de tiempo), `sid` por llamada, espera de hasta 32000 ms, luego resultado de timeout. Con AB **14565** desactivado, un JID LID con número de teléfono conocido se reescribe a ese número antes de construir la solicitud (`AbstractC197018Zw.A0Y`; dirección inferred a partir del paso de prefijo `+` que sigue).

### 4.2 Códigos de resultado (`C43621q7`, nombres inferred a partir del uso)

0 `A04` red no disponible; 1 `A08` omitido (nada que enviar o demasiado frecuente); 2 `A07` éxito con cambios (ruta de eliminación de contactos); 3 `A06` éxito; 4 `A03` fallo (resultado vacío, timeout, error); 5 `A05` limitado por tasa (error de resultado 429); 6 `A02` excepción. `A01()` es true para 1, 2, 3. Un `<list>` vacío con un error 429 del protocolo contact da 5, cualquier otra lista vacía da 4.

### 4.3 Qué funciones llegan a la libreta telefónica (found)

| Ruta | Entrada | Tipo | Protocolos (`C21820s6`) |
|------|-------|------|------------------------|
| Full sync en background (solo primary) | `C18230lP.A0F(reason)` | `BACKGROUND_FULL` | todo excepto orgs |
| Full sync forzado | helper `A01`, job periódico `RunnableC23953AUi` case 23 | `BACKGROUND_FULL`; companion: `BACKGROUND_COMPANION_MULTI_PROTOCOL_QUERY` | contact (`A0J`) o side list (`A0K`); companion: todo excepto contact / side list (`A0D`) |
| Subida forzada, subida delta, descarga | `A07(reason)`, `A0G(reason)`, `A0C()` | `CONTACT_FORCE_UPLOAD`, `CONTACT_UPLOAD`, `CONTACT_DONWLOAD` | contact + lid (`A0G`) |
| Contactos nativos cambiados | `A0J(reason, jids)` | `NATIVE_CONTACT_DELTA` | todo excepto orgs |
| Sync diferido posterior al registro | `A0L` (pref `registration_contact_sync_delayed`) | `CONTACTS_PROVIDER_WHATSAPP_ACCOUNT_SYNC` | contact + lid |
| Side contact en la primera visualización | `A0E(contact)` | primary: `INTERACTIVE_DELTA_SIDELIST`; companion: `INTERACTIVE_MULTI_PROTOCOL_QUERY` | todo excepto orgs / todo excepto contact, side list, orgs |

Conjuntos de protocolos (constantes de `C21820s6`, found): `A0S` username; `A0G` contact + lid; `A0P` status; `A0Q` text status; `A0O` picture; `A0F` business; `A0H` devices; `A0E` business + devices; `A0N` payment; `A0I` disappearing mode; `A0L` lid; `A0M` orgs; `A0D` todo excepto contact, side list, orgs; `A0R` como `A0D` sin lid; `A0J` contact + conjunto `A0D`; `A0K` side list + conjunto `A0D`; `A0C` todo excepto orgs. LID está implícito cuando se sincroniza contact o side list.

`C21830s7` (SyncRequest) persiste las opciones como JSON: `sync_is_urgent`, `sync_only_if_changed`, `sync_only_if_registered`, `sync_clear_whatsapp_sync_data`, `sync_should_retry` y un booleano `sync_<protocol>` por protocolo (found); int de reintento por defecto del builder 5 (significado inferred).

### 4.4 Búsquedas disparadas por notificaciones (found)

El servidor empuja un hash en lugar de un número; el cliente lo resuelve y ejecuta una consulta.

| Handler de notificación | Payload | Sync | Protocolos |
|----------------------|---------|------|-----------|
| `AnonymousClass145` (actualización de contacto), `add` | hasta 2 hijos hash de tipo `pn` (por defecto) o `lid`; solo primary | `NOTIFICATION_CONTACT` | todo excepto orgs |
| igual, update | hash base64 | `NOTIFICATION_SIDELIST` | status, picture, lid, username, text_status |
| notificación de status `C1S0` | atributo `hash` (base64) | `NOTIFICATION_SIDELIST` (motivo `NOTIFICATION_STATUS`) | solo status |
| notificación de picture `C1S0` | atributo `hash` | `NOTIFICATION_SIDELIST` (motivo `NOTIFICATION_PICTURE`) | solo picture |
| notificación de business `AnonymousClass142` (eliminación sin jid con `hash`) | hash base64 | `NOTIFICATION_SIDELIST` (motivo `NOTIFICATION_BUSINESS`) | conjunto business (constante no resuelta) |

El hash se compara con los usuarios locales mediante `digest(user + "WA_ADD_NOTIF")` comparado prefijo de bytes a prefijo de bytes (`AbstractC43461pq.A04`); el algoritmo de digest lo elige el llamador (no trazado). Un "forced sync" disparado por el servidor (`RunnableC23951AUg`, motivo `SERVER_FORACE_SYNC`) ejecuta `BACKGROUND_FULL` o el tipo companion.

### 4.5 Sync de contactos mediante mutaciones MEX (found, no USync)

Novedad en el build: el sync de contactos en Kotlin (`com.whatsapp.contact.sync.kmp`, `.handler`) usa mutaciones `w:mex` en lugar del IQ usync. Config `whatsapp-android-mex`, doc_ids del asset persist-id.

| Operación | doc_id | Variables (found) | Respuesta |
|-----------|--------|-------------------|----------|
| `ContactsDeltaSyncMutation` | `28247314474869813` | `context` (`SEARCH`, `OSAB_IMPORT`, `EMAIL_IMPORT`, `QR_SCAN`), `primary_contacts_add[]`, `primary_contacts_remove[]` (`lid`, `modifier` = `BEST_EFFORT_DOWNGRADE_TO_WA_SIDE_CONTACT`, `normalized_phone`), `side_contacts_add[]` | `xwa2_contacts_delta_sync`: `results[]` {`client_cached_lid`, `failed`, `detail` (unión: raw_pn / primary_normalized_phone / lid / phone_status; side_status; username_status; email_status; normalized_phone)}, `retry_after_seconds` |
| `PrimaryContactsFullSyncMutation` | `36963099086669113` | no leído | no leído |
| `SideContactsFullSyncMutation` | `26880700761604398` | `context`, `cursor`, `side_contacts[]` (`client_cached_lid`, `normalized_phone`) paginado | `results[]` como arriba, `retry_after_seconds` |

Qué decide entre esta ruta y la ruta usync no se encontró (unknown). `retry_after_seconds` es el equivalente MEX del `backoff` de usync.

---

## 5. Sync de la lista de dispositivos, key index, ADV

### 5.1 Solicitud y respuesta (found)

Solicitud: hijo de consulta `<devices version="2"/>`; por usuario `<devices device_hash="H" ts="T" expected_ts="E"/>`, enviado solo cuando existe un hash (`ts`, `expected_ts` solo cuando son mayores que 0 y `expected_ts` es mayor que `ts`). Los valores provienen de la fila local del dispositivo (`C15070fj.A07/A00/A04`).

Respuesta por usuario: `<devices>` contiene un `<error code text>` (el usuario recibe el estado -1, log "parseUser/partial error") o bien:

| Nodo | Atributos | Se parsea a |
|------|------------|-------------|
| `<device-list><device .../>` | `id` (int), `key-index`, `is_hosted` | `DeviceJid(user, id)` -> key index; una discrepancia entre el estado hosted del JID e `is_hosted` reporta `invalid-hosted-flag` |
| `<key-index-list ts expected_ts>` | `ts` (segundos), `expected_ts` (por defecto 0), bytes de contenido | lista de key-index firmada, almacenada en crudo |

El `<devices>` a nivel de resultado puede llevar `<error>` con backoff (sección 9). Ruta MEX: `include_devices` más `devices{hash, timestamp, expected_timestamp}`; etiquetas de log del cliente para resultados descartados: `devices_dropped_status_error`, `devices_status_indeterminate`, `devices_hash_match_noop`, `devices_dropped_empty_without_hash`, `devices_dropped_no_jid`, `devices_dropped_stale_timestamp`, `devices_dropped_adv_proto_missing`, `devices_dropped_adv_verify_failed`, `devices_dropped_adv_data_update_failed`, `devices_outcome_unset`.

### 5.2 Verificaciones de actualización (found, `C51909N4g`, `C24230w2`)

| Verificación | Comportamiento |
|-------|-----------|
| lista de key-index vacía | "update keyIndex is empty", sin actualización |
| `ts` de la respuesta más antiguo que el almacenado | "timestamp is less than existing one", descartado |
| reintento por expected-ts obsoleto | ts de la respuesta por debajo del almacenado, `expected_ts` igual al ts almacenado y valor almacenado más antiguo que la pref `adv_last_device_job_ts`: registra un error de fetch usync y emite el evento WAM `wam_adv_expected_ts_unavailable` (`C49716Ltt`), devuelve true (efecto en el llamador no trazado) |
| información de dispositivo nueva | `C51909N4g.A00` borra el expected ts almacenado cuando el nuevo ts es al menos el almacenado; tipo de cuenta derivado del conjunto de dispositivos (`C9U.A01`) |

### 5.3 Verificación firmada de key-index ADV (found, `C24230w2.A07`, `A04`)

| Paso | Detalle |
|------|--------|
| Parse | bytes de key-index -> `ADVSignedKeyIndexList` (`C25786BAu`): `details` (**1**), `account_signature` (**2**), `account_signature_key` (**3**, opcional) |
| Clave pública | identidad del dispositivo primary desde el almacén de identidades local; si el proto lleva `account_signature_key` y difiere de la clave local, se usa esa clave y se etiqueta `adv`; sin ninguna de las dos claves: advertencia "no primary identity" |
| Firma | verifica `account_signature` sobre `{0x06, 0x02} || details` con la clave elegida (`AbstractC30195DBc.A08`); el fallo registra "fail to verify account signature" y emite un evento WAM (`C55912St`, 1 = clave local, 2 = clave adv) |
| Details | `details` -> `ADVKeyIndexList` (`BCB`): `raw_id` (**1**), `timestamp` (**2**), `current_index` (**3**), `valid_indexes` (**4**), `account_type` (**5**) |
| Coincidencia de timestamp | `details.timestamp` debe ser igual al atributo `ts`, de lo contrario "advTimestampMismatch" + evento WAM `C2TD`, resultado rechazado |
| Antigüedad | si `ts` es más antiguo que `min(35, AB 730)` días (por defecto 35) y `valid_indexes` tiene más de 1 entrada: "advListTimestampInvalid", rechazado |
| Raw id | `raw_id` distinto del almacenado: "incoming key-index not matching local state, resetting"; la cuenta propia en un companion registra `device_self_invalid_index_list`; otros usuarios: `C15070fj.A0G(user, "adv_key_index_list_validation_failed")` cuando no se parseó ninguna lista nueva (efecto no trazado) |
| Filtrado | `filterDeviceWithKeyIndexList` (`C24230w2.A08`) conserva un dispositivo cuando es el primary, o su `key-index` es mayor que 0 y figura en `valid_indexes`; de lo contrario se descarta con un evento WAM (`C55932Sv`, 1 cuando el índice es 0). Un índice almacenado mayor solo produce una advertencia |

### 5.4 Jobs de sync de dispositivos (found)

`DeviceSyncManager.A03(jids, type)` encola `SyncDevicesJob` (omite usuarios ya en curso; los usuarios pendientes sobreviven a los reinicios en la pref `pending_users_to_sync_device`). `syncType` selecciona el tipo de sync:

| `syncType` | Tipo de sync | Contexto | Llamado desde (found) |
|------------|-----------|---------|---------------------|
| 0 / por defecto | `INTERACTIVE_MULTI_PROTOCOL_QUERY` | interactive | — |
| 1 | `MESSAGE_MULTI_PROTOCOL_QUERY` | message | `SyncDevicesAndSendInvisibleMessageJob` (ruta de envío a grupos `C22300su`, tamaño de grupo entre AB 934 y AB 1946, un job por message key) |
| 2 | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | notification | sync de cuenta de los dispositivos propios (`C41431mS`) |
| 3 | `BACKGROUND_MULTI_PROTOCOL_QUERY` | background | mensaje o status entrante cuya verificación de remitente ADV falló (`DecryptMessageRunnable` / `StatusProcessingRunnable`, log `invalid adv sender`), discrepancias de metadatos ADV (`C24230w2`), reproducción de usuarios pendientes |
| 4 | `VOIP_MULTI_PROTOCOL_QUERY` | voip | configuración de cifrado de llamada para un dispositivo no primary (`C1A`, log `voip/encryption/schedule usync`) |
| 5, 6 | `LID_MIGRATION_NOTIFICATION_MULTI_PROTOCOL_QUERY`, `LID_MIGRATION_MESSAGE_MULTI_PROTOCOL_QUERY` | notification, message | no trazado |

Las solicitudes solo de devices usan `C21820s6.A0H`. `handleADVMetadata` (`C24230w2.A0A`) también dispara una actualización de tipo 3 cuando los metadatos ADV de un mensaje entrante reportan un tipo de cuenta hosted que no coincide con el estado local (dispositivos borrados primero), o un timestamp más nuevo que el almacenado.

---

## 6. Mapeo de LID

| Mecanismo | Detalle (found) |
|-----------|----------------|
| protocolo `lid` | consulta `<lid/>`; `<lid jid=known LID/>` por usuario solo cuando un usuario PN ya tiene un LID almacenado; la respuesta `<lid val="LID"/>` se almacena en el resultado del usuario |
| Escritura del mapeo | `N27.A03(users)`: LID = `new_jid` (si es un JID de tipo LID), si no el resultado `lid`, si no el `jid` del usuario si es un LID; PN = `pn_jid`, si no el `jid` del usuario si es un PN; los pares van al almacén de mapeo LID-PN en un solo lote |
| Business `pn_jid` | un usuario LID sin PN obtiene el PN de `<business pn_jid>`; el par se almacena |
| Side list | los usuarios de la solicitud llevan `jid` = LID y `pn_jid` = PN cuando el direccionamiento LID está activo (`C11940aM.A05`, resuelto mediante `C11500Zc.A00`, id del flag no trazado); los fallbacks registran `Sidelist: No LID provided`, `waContact_null`, `usernameLid_null` |
| Reparación de LID faltante | `MissingLidHandler` (`C32M`): `requestSyncDevicesAndLidIfMissingLids` espera 32000 ms un `MESSAGE_MULTI_PROTOCOL_QUERY` con el protocolo lid antes de que un punto de entrada externo continúe |
| Observador de mapeo | `ContactJidMapObserver` (`C0ZA`): cuando aparece un par LID-PN y existe un contacto deprecated, agrega el contacto de reemplazo y encola un `BACKGROUND_DELTA` con el motivo `LID_REQUEST` |

Por qué importa un LID faltante: un contacto solo-PN no puede ser direccionado con el envío LID-first; la consulta completa el par sin un full sync (inferred a partir de los sitios de llamada).

---

## 7. Enriquecimiento de privacidad (tctoken, grupo común)

`ProfilePrivacyEnrichmentFetcher` (`C223659jg.A00`, etiqueta de log `ContactSyncHelper.privacyEnrichment`) se ejecuta sobre la lista de solicitudes antes del envío. Para cada usuario obtiene (a) el privacy token almacenado con su timestamp (`C14820fK.A0M`, descartado cuando es más antiguo que `C14820fK.A04.A02()`), (b) cuando no existe un token válido, un JID de grupo compartido con el usuario (`C197178aC.A04` / búsqueda masiva, requiere LID propio). Resultado `C197148a9{ token C9oI, commonGroup, flag }`.

| Salida | usync clásico | MEX `UsyncQuery` |
|--------|---------------|------------------|
| token | hijo `<tctoken>token bytes</tctoken>` de `<user>` | `privacy_token{tctoken, timestamp}` |
| grupo común | atributo `common_gid="..."` en `<user>` | `common_group` |

Se aplica solo a solicitudes que piden picture o status (AB **9667**, por defecto true), text status (**20798**, por defecto false), devices (**29769**), contact (**29770**), lid (**29771**) (los flags son false por defecto excepto 9667). Sin un token o un grupo común el servidor aún puede responder, pero puede omitir picture o status (inferred; regla del servidor unknown). La emisión de tokens y `cstoken` están en WA_TCTOKEN_CSTOKEN.md.

Relacionado: `PRIVACY_TOKEN_REFRESH` (`C735439k`) emite `BACKGROUND_QUERY_PICTURES` con el conjunto solo-picture `A0O` en lotes de 10 usuarios (found); que el propósito sea refrescar la asociación del token es inferred a partir del nombre del motivo.

---

## 8. MEX `UsyncQuery` y enrutamiento de protocolos

### 8.1 Operación (found, `C229259vZ.A01`)

Operación `w:mex` `UsyncQuery`, doc_id `38635300486116501` (asset persist-id), clase de respuesta `C2IQ`. Envoltorio como en WA_USERNAME.md 2.2.

| Variable | Origen |
|----------|--------|
| `query_input[]` | por usuario: JID, `client_known_username`, `about_status{dhash}`, `picture{id}`, `business{serial, tag}`, `devices{hash, timestamp, expected_timestamp}`, `privacy_token{tctoken, timestamp}`, `common_group` |
| `telemetry.context` | cadena de contexto en minúsculas |
| `include_username`, `include_reachability`, `include_linked_profiles`, `include_lid`, `include_about_status`, `include_picture`, `include_biz`, `include_ddm`, `include_devices`, `include_orgs` | booleanos establecidos cuando algún usuario solicita el protocolo |
| `picture_field_input` | `type` `IMAGE` o `PREVIEW`, `preview_px` para previews |
| `business_input` | `include_profile`, `include_vname`, `profile_version` |

No se transportan por MEX: contact y text_status. Solo MEX: reachability, linked profiles, orgs, ddm (disappearing mode). Los detalles de la respuesta más allá de username y lid (WA_USERNAME.md) no se leyeron (unknown).

### 8.2 Cuándo se usa MEX (found, `C18580m0`)

1. AB **37780** (int, por defecto 0) distinto de cero: enrutamiento por protocolo. Los 16 bits altos = máscara de bits enrutada por usync clásico (`SMAX`), los 16 bits bajos = máscara enrutada por MEX; `DROP` en caso contrario. Bits (`M5H`): status 4, picture 8, business 16, devices 32, disappearing_mode 128, username 512, text_status 1024, orgs 2048. Los bits a nivel de solicitud 1 (contact), 2 (`C70582ym.A07`, probablemente side list, inferred) y 256 viajan como la máscara "identity". Un protocolo que la ruta elegida no puede transportar se establece en `DROP`: text_status en MEX, orgs en SMAX. La línea de log es `ContactSyncHelper/read_route type=.. contacts=.. identity=..,.. failed=..`.
2. De lo contrario, con AB **33432** (por defecto false): consulta clásica para la solicitud principal, luego un "mex profile follow-up" (`..._mex_profile`) para devices, con un marcador de métricas anotado con `requested_users`, `is_delta_sync`, resultado `success`, `partial_success`, `no_result`, `timeout`, `exception`, `interrupted`.
3. De lo contrario `A0F` decide por solicitud: MEX se rechaza cuando la solicitud tiene contact o text_status ("cantUseMex"), necesita AB **9732** para business y AB **8421** para username; el resto puede ir por MEX (`C229259vZ`), con una espera de 128000 ms.

Estado por defecto de este build: 37780 = 0, 33432 = false, 9732 = false, 8421 = false, por lo que USync corre sobre el stanza clásico salvo que un override de AB del servidor lo cambie.

---

## 9. Límites de tasa, errores, backoff

### 9.1 Formas de error (found)

| Dónde | Forma | Parseado por |
|-------|-------|-----------|
| error de iq | `<iq type="error"><error code backoff/></iq>` | `Brt`: `code`, segundos de `backoff` * 1000 limitado a 3600000 ms (-1 cuando falta); llama a `BIz(type, sid, code, backoffMs)`, completa el future con null |
| fallo de entrega | callback de transporte | `Bog`: el future falla con `C216419Uc`; estado de sync por JID reiniciado (`C502424l.A01`) |
| error de protocolo | `<result><PROTO><error code text backoff/></PROTO></result>` | `C18670m9.A01`: segundos de `backoff` * 1000, por defecto 7200 s, límite 3600000 ms (1 h); registra `connection/unisynciq/parse/<proto>/error` |
| éxito de protocolo | `<PROTO refresh="n"/>` | segundos de `refresh` * 1000 |
| parcial a nivel de usuario | `<devices><error code text/></devices>` | estado -1, usuario conservado |
| error MEX | error GraphQL, campo de path `<proto>_info`, cadena de backoff opcional | `C229259vZ.A00`: backoff por defecto **7200**, límite 3600000, sin conversión * 1000 en esta ruta (unidades poco claras, unknown) |
| clave de username | códigos `42901` (requestor) y `42902` (requestee) en el resultado contact | `C23638AId.A0G`, ver WA_USERNAME.md |

Códigos vistos en la lógica del cliente: `429` (límite de tasa: resultado de sync 5), `503` (backoff global), `42901`, `42902`.

### 9.2 Almacén de backoff (found, archivo de prefs `contact_sync_prefs`, `C18800mM`)

| Clave | Se escribe cuando | Valor |
|-----|--------------|-------|
| `contact_sync_backoff` | cualquier error de iq / protocolo contact con backoff mayor que 0 (`X.0m7.BIz`, `AO4.BIz`) | ahora + backoff ms |
| `delta_sync_backoff` | igual, modo delta y código 429 | ahora + backoff |
| `global_backoff_time` | igual, código 503 | ahora + backoff |
| `sidelist_sync_backoff` | callback de `ContactQuerySync` `AO2.BIz` en **cualquier** error con backoff mayor que 0 | ahora + backoff; el código 503 también establece `global_backoff_time` (el nombre de la clave no coincide con el alcance del sync; found) |
| `contact_full_sync_wait`, `status_full_sync_wait`, `sidelist_full_sync_wait` | atributo `refresh` del resultado del protocolo | ms; sin establecer = 86400000 (24 h) |
| `status_`, `picture_`, `business_`, `devices_`, `disappearing_mode_`, `lid_`, `username_`, `text_status_`, `reachability_` `sync_backoff` | backoff de error del resultado por protocolo en `BJ0` | ahora + backoff |
| `last_contact_full_sync`, `last_status_full_sync`, `last_sidelist_full_sync` | finalización del full sync | timestamp |

`C18800mM.A02()` restablece a -1 las claves contact, sidelist, status, picture, business, devices, delta, disappearing_mode, lid, reachability y global; `username_sync_backoff` y `text_status_sync_backoff` no están en esa lista (found).

Lectores encontrados por búsqueda de strings: `reachability_sync_backoff` (`C18580m0`), `text_status_sync_backoff` (`C3MA`), las tres claves `*_full_sync_wait` y `last_*_full_sync` (job periódico: un full sync corresponde cuando `wait - now + last` es como máximo 1800000 ms, 30 min). No se encontró ningún lector de `contact_sync_backoff`, `delta_sync_backoff`, `global_backoff_time` ni de las demás claves por protocolo (unknown si la verificación construye la clave dinámicamente).

### 9.3 Límites locales (found)

Deduplicación en curso: un `querySyncJid` por JID, una consulta de teléfono por número. Timeouts: 32000 ms búsqueda individual, 128000 ms lote, 180 s para la espera del callback `C18230lP.A00` (sin límite cuando `C11980aQ.A09`). Límite de backoff 3600000 ms. Lotes de refresco de privacy-token de 10 usuarios. Los límites de consulta del servidor por cuenta y por número son unknown.

---

## 10. Qué dispara USync

Motivo = valor de `EnumC21800s4` (etiqueta del cliente, usada para programación y métricas). Tipo = tipo de sync.

| Función del cliente | Motivo | Tipo | Protocolos |
|----------------|--------|------|-----------|
| Registro terminado | `REGISTRATION_FULL` (`C25100xS`, `CJ8`) | `REGISTRATION_FULL` (código 0) | conjunto contact (variante companion no trazada) |
| Onboarding de contactos | `NC_ONBOARDING` | subida delta `A0G` (`CONTACT_UPLOAD`) | contact + lid |
| Libreta de direcciones del dispositivo cambiada (solo primary) | `DEVICE_ADDRESS_BOOK_CHANGE` | delta urgente por cambio (`C18230lP.A02`) | no trazado |
| Full sync periódico y forzado | `PERIODIC_FORCE_SYNC`, `FORCE_SYNC` | `BACKGROUND_FULL` | contact / side list |
| Apertura del selector de contactos | `CONTACT_PICKER_FULL_SYNC`, `CONTACT_PICKER_USYNC_RETRY` | `INTERACTIVE_FULL` | no trazado |
| Agregar contacto, nuevo chat por número, deep link, chat sin contacto | existen motivos `*_CONTACT_ADD`; no vinculados a la ruta de consulta | `ADD_QUERY` (`C9AA`) / `INTERACTIVE_QUERY` (`C9AQ`, `C9AY`, `AWR`, `A1P`) | ver 4.1 |
| Abrir un chat con un usuario o business no guardado | `CONVERSATION_SIDE_CONTACT`, `SIDELIST_REQUEST` | consulta de teléfono (`INTERACTIVE_QUERY`) cuando AB **20988** (por defecto true), de lo contrario `INTERACTIVE_DELTA_SIDELIST` | ver 4.1 / 4.3 |
| Enviar mensaje a lista de difusión | `LID_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | lid |
| Envío de mensaje a grupo (tamaño dentro de AB 934..1946) | `DEVICE_REQUEST` | `MESSAGE_MULTI_PROTOCOL_QUERY` | devices |
| Mensaje entrante con verificación de remitente ADV fallida, discrepancia de metadatos ADV | `DEVICE_REQUEST` | `BACKGROUND_MULTI_PROTOCOL_QUERY` | devices |
| Configuración de cifrado de llamada | `DEVICE_REQUEST` | `VOIP_MULTI_PROTOCOL_QUERY` | devices |
| Sync de la cuenta propia | `DEVICE_REQUEST` | `NOTIFICATION_MULTI_PROTOCOL_QUERY` | devices |
| Push del servidor: cambio de contact, status, picture, business, username | `NOTIFICATION_*`, `USERNAME_UPDATE_NOTIFICATION` | `NOTIFICATION_CONTACT` / `NOTIFICATION_SIDELIST` | según la notificación |
| Refresco de disappearing-mode y text-status | `DM_FORCE_REFRESH`, `TEXT_STATUS_FORCE_REFRESH` | `BACKGROUND_MULTI_PROTOCOL_QUERY` (text status también `BACKGROUND_FULL`) | disappearing_mode / text_status |
| Cambio de cuenta | `ACCOUNT_SWITCH_REFRESH` | `BACKGROUND_FULL` | no trazado |
| Refresco de privacy token | `PRIVACY_TOKEN_REFRESH` | `BACKGROUND_QUERY_PICTURES` | picture |
| Cambio de mapeo LID-PN | `LID_REQUEST` | `BACKGROUND_DELTA` | todo excepto orgs |
| Chat business (mensaje agregado, llamada) | `BUSINESS_CONTACT_CHAT` (`C0LX`, `RunnableC23932ATn`) | `BACKGROUND_MULTI_PROTOCOL_QUERY` / `VOIP_MULTI_PROTOCOL_QUERY` | no trazado |

---

## 11. Feature flags

IDs de AB-prop tal como se leen en los sitios de llamada; valores por defecto de las tablas de configuración de este build. IDs de flag en negrita.

| Flag | Tipo | Por defecto | Controla |
|------|------|---------|----------|
| **5751** | bool | false | solicitar devices en consultas de contacto y de número de teléfono |
| **5839** | bool | false | protocolo text_status (solicitud y parseo) |
| **9667** | bool | true | enriquecimiento de privacidad para solicitudes de picture / status |
| **20798** | bool | false | enriquecimiento de privacidad para text_status |
| **29769**, **29770**, **29771** | bool | false | enriquecimiento de privacidad para solicitudes de devices, contact, lid |
| **9732** | bool | false | business sobre MEX |
| **8421** | bool | false | username sobre MEX |
| **37780** | int | 0 | máscaras de enrutamiento por protocolo (16 altos SMAX, 16 bajos MEX) |
| **33432** | bool | false | dividir consulta clásica + seguimiento de perfil MEX |
| **12402** | bool | false | `lid` y `pin` en el `contact` de username |
| **14565** | bool | false | `addressing_mode="lid"` en contact, texto PN solo con dígitos |
| **26739** | bool | false | prefijo `+` en números de teléfono |
| **471** | int | 1140 | `profile v` de business (enmascarado con 0x3FFC) |
| **730** | int | 35 | antigüedad máxima del key-index ADV en días (limitada a 35) |
| **31261** | bool | false | agrega el `@username` conocido por usuario (`C223639je`) |
| **33609** | bool | true | cuando es true, la búsqueda de key-entry omite `<username/>` |
| **20988** | bool | true | consulta de teléfono en lugar de sync de side list en un chat business no guardado |

---

## 12. Baileys (`baron-baileys-v2`, comparado con su `src/WAUSync` y `Socket/socket.js`)

| Tema | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| envoltorio | `iq to=s.whatsapp.net type=get xmlns=usync` + `usync{context, mode, sid, last="true", index="0"}` | mismos atributos; `to` implícito |
| modos | `query` (por defecto), `delta` | también `full`, `download` |
| contextos | `interactive` (por defecto), `background`, `message`; `voip` aparece en su regla de backoff | más `registration`, `notification`, `add`, `voip`, `metadata`, `snapshot`, `wamo` |
| protocolos | agrega `bot`, `feature`, `sidelist` como hijo de consulta | sin hijo `bot` / `feature`; los usuarios de sidelist van en `<side_list>` |
| contact | `<contact>phone</contact>`, username con `pin` / `lid`, `type` | teléfono con `+`, `type="delete"`, username |
| status oculto | `code="401"` en `<status>` da `''` | `type="fail"` con 401 / 403 / 404 |
| prueba de privacidad | `<tctoken>` solo bajo el protocolo status, cuando el usuario lleva un token | `<tctoken>` para picture / status / otros y `common_gid` |
| backoff | segundos de `error backoff` * 1000, sin límite | limitado a 1 h |

| Síntoma (inferred) | Causa | Solución |
|--------------------|-------|-----|
| picture / status ausentes para no contactos | sin tctoken, sin `common_gid` | adjuntar el `<tctoken>` almacenado o un JID de grupo compartido por usuario |
| lista de dispositivos rechazada | verificaciones de `ts` / `raw_id` del key-index de la sección 5.3 | verificar que `ts` sea igual al `details.timestamp` firmado |
| backoff ignorado | Baileys usa el valor del servidor sin límite | limitar a 1 h, esperar por protocolo |

---

## 13. Casos de error

| Síntoma | Causa | Solución |
|---------|-------|-----|
| `ContactQuerySync/querySyncJid: rate-limit-error` | error 429 en el resultado contact, lista vacía | esperar el `backoff` devuelto, reducir la tasa de consultas |
| `connection/unisynciq/parse/<proto>/error` | nodo de error por protocolo | almacenar el `backoff` solo para ese protocolo |
| `handleSyncContactError ... code=503` | sobrecarga del servidor | backoff global, reintentar más tarde |
| `sidelist-jid-absent-from-response` | el servidor omitió un usuario de side list solicitado | el cliente marca al usuario como sincronizado para evitar un bucle |
| `contactsyncDevicesupdater/update/verifyADVSignedKeyIndexList fail` | falló la verificación de firma, proto o timestamp | fila de dispositivo no actualizada, refresco encolado |

---

## 14. Distinciones clave

| No confundir | Detalle |
|----------------|--------|
| tipo de sync vs motivo | el tipo (`EnumC21760rz`) elige modo, contexto, alcance; el motivo (`EnumC21800s4`) es solo una etiqueta para programación y métricas |
| `list` vs `side_list` | usuarios de la libreta de direcciones vs usuarios fuera de la libreta de direcciones (side contacts) |
| usync vs MEX `UsyncQuery` vs mutaciones MEX de contactos | tres transportes para datos relacionados; flags de enrutamiento en 8.2 y 4.5 |
| resultado `<devices>` vs key index firmado | la lista de dispositivos no es de confianza hasta que se verifica la lista firmada (5.3) |
| `refresh` vs `backoff` | `refresh` = cuánto tiempo puede reutilizarse un buen resultado, `backoff` = cuánto tiempo mantenerse alejado tras un error |

---

## 15. Flujo completo

```
[Feature]         [ContactSyncMethods]            [UniSync builder / MEX]                [Server]
  │ trigger (10)         │                                  │                               │
  ▼                      ▼                                  │                               │
 reason + type ──► SyncRequest (protocol set, users)        │                               │
                         │ enrich: tctoken / common_gid (7) │                               │
                         │ route per protocol (8)           ▼                               │
                         └──► classic: <iq xmlns=usync><usync sid index last mode context> ─►│
                         └──► MEX: w:mex UsyncQuery {query_input, include_*} ───────────────►│
                                                            │◄── <usync><result> per protocol│
                                                            │     <list> <side_list>         │
                                                            ▼                               │
                    parse: contact in/out, status, picture, business,                       │
                           devices + key-index-list, lid val, username                      │
                                  │                                                         │
        ┌─────────────────────────┼─────────────────────────┐                               │
        ▼                         ▼                         ▼                               │
 devices: verify ADV sig,   LID/PN pairs ──► mapping   result errors: 429 / 503 / backoff   │
 ts, raw_id, valid_indexes  store (N27.A03)            ──► prefs; refresh ──► full_sync_wait │
        │ ok                                                                                │
        ▼                                                                                   │
 device rows updated ──► message fan-out, call setup, side-list chats use the new data      │
```

---

## 16. Unknowns

| Tema | Razón |
|-------|--------|
| atributo `to` del iq | agregado por el sender; sender no trazado |
| Diferencia de `C10140Tq.A0A` (registration) vs `A06` | no trazado |
| Reglas del servidor sobre tasa de consultas, límites por número, qué protocolos puede leer un solicitante | el cliente solo ve códigos de error |
| Lectores de `contact_sync_backoff`, `global_backoff_time`, `delta_sync_backoff` | no se encontró ningún lector de string |
| Unidades del backoff MEX | sin `* 1000` en `C229259vZ.A00` |
| Qué ruta gana en producción | todos los flags de ruta están desactivados por defecto en este build; valores de AB del servidor unknown |
| Tráfico real | solo análisis estático |
