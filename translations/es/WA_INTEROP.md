<!-- src-sha1: 8d1c772149420abe245fd6a70c2b6615d2ab4fc5 -->
# WhatsApp Interop — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** interoperabilidad de chat con terceros en Android (estilo DMA): control de funciones y flags AB, aviso de consentimiento y opt-in, lista de integradores, dominios JID interop y tag JID binario, descubrimiento de usuarios (`w:interop` FetchUsers), IQ set `w:interop`, texto plano restringido `InteropMessage` y tipos de mensaje soportados, diferencias de cifrado y stanza, grupos interop (operaciones MEX, notificaciones, privacidad de adición), ping de alcanzabilidad, bloqueo y denuncia, almacenamiento, casos de error, diferencias con los chats nativos, comparación con Baileys

---

## 1. Qué es (técnicamente)

Interop permite que una cuenta de WhatsApp intercambie mensajes 1:1 y de grupo con cuentas de otras apps de mensajería ("integrators"). El cliente nunca habla con esas apps. Habla con los servidores de WhatsApp, que exponen cada cuenta de terceros como un JID sintético en el dominio `interop` (grupos: `interop.g.us`). Todas las afirmaciones provienen del análisis estático del APK decompilado; no se capturó nada en la red ni se ejecutó contra un servidor. Niveles: **found** = leído en código o recursos, **inferred** = deducido del código, **unknown** = no resuelto. Los nombres ofuscados son específicos de cada build y se re-resolvieron en 2.26.41.6 a partir de strings estables (`InteropOptInManager/`, `InteropChatMessageHandler/`, `IntegratorManager/`, `w:interop`, `integrator_display_name`, `xwa2_interop_*`).

Estado en este build:

| Parte | Estado en 2.26.41.6 |
|------|--------------------|
| Código | **Presente y completo**: UI (10 activities más fragments y diálogos), cliente IQ, operaciones MEX de grupo y privacidad, pipeline de recepción estricto, almacenamiento, handler de notificaciones |
| Interruptor del servidor | **Desactivado por defecto**: el flag AB raíz **7495** tiene por defecto `false`; todos los flags interop leídos en el código tienen por defecto `false` (sección 2) |
| Región | El texto del producto lo limita a usuarios con un número de teléfono de la Región Europea; **no se encontró ninguna comprobación de país en el cliente** (la aplicación se infiere en el servidor, mediante el flag 7495 y la lista de integradores) |
| Integradores | **Ninguno codificado de forma fija**: ningún nombre de integrador ni id fijo de integrador en código, recursos o assets; la lista viene del servidor (sección 4) |

| Entidad | Nombre en 2.26.41.6 | Función |
|--------|----------------|------|
| Gate (`InteropRolloutManager`, nombre inferido de un getter) | `C32001Oa` | `A01` elegible, `A02` elegible y primario, `A00` grupos, `A03` bandeja unificada |
| Cliente IQ / builders / parsers | `DmaInteropRPCManager` (`com.whatsapp.infra.smax.generated.dmainterop.outgoing`); `C31107Dfz` (casos 20-23), `C31106Dfy`; `C214369Ee`, `C9EQ`, `C9EP`, `C214389Eg`, `A1J` | cinco RPC `w:interop`, parseo estricto del esquema |
| Integradores | `C227409sQ` manager, `C23765ANa` store, `A3X` (`IntegratorInfo`), `InteropUiCache` = `SharedPreferencesOnSharedPreferenceChangeListenerC20390p5` (prefs `interop_ui`) | lista, estado de opt-in, caché de UI |
| JIDs | `C99O` usuario, `C41021lm` dispositivo, `C55529Oy6` grupo, `C9YC` parser; writer `C40411kn.A00`, reader `C24610wf` (tag 244) | sección 3 |
| Recepción | `ENP` -> `C34471Exu` (`DecryptionCallbackInterop`) -> `C34720F4p` (`InteropChatMessageHandler`); `DTF` (texto plano de 9 campos), `EUQ` (`ParseInteropMessageParams`) | pipeline estricto |
| Registro de tipos | `C32718EOz`; `FBN` texto, `FBK` imagen, `FBL` video, `FBJ` GIF, `FBH` audio, `FBI` documento, `FBM` reacción, `FBG` no soportado | protobuf <-> FMessage |
| Envío | `C33446EhE` (rama), `F6P` (`E2eMessageEncryptor`), `F6K` (`<meta>`) | saliente |
| Grupos / privacidad | `InteropGroupsManager`, `C3R2`, `C3Rb` / `C3Qh` solo en smali; `C0WQ` (notificaciones); `InteropPrivacySettingsManager`, `C3Q4` / `C3Q1` / `C29664Cuh` | MEX |
| Opt-in | `C229349vm` (`InteropOptInManager`), `ARH`, `A4N`, `C224669lg` / `C24380wI` (aviso), `PaaInteropMigrator` | asistente, consentimiento |
| Ping | `X.0xL` anónimo en `C1S0` (`InteropNotificationHandler`), id 270 en `AbstractC32331E9w` | notificación |
| Analítica | `AnonymousClass590` | WAM 6684, 7044, 7168, 6680 |

---

## 2. Control de funciones (feature gating)

### 2.1 Cadena de gates (found, `C32001Oa`)

| Método | Condición | Usado para |
|--------|-----------|----------|
| `A01()` | la cuenta no es una cuenta dependiente bajo reglas de experiencia por edad (`C14980fa.A00` -> `C08520Ne.A03()` -> `C08530Nf.A03()` false; tipo dependiente `EnumC08540Ng.DEPENDENT`) **y** AB **7495** | todo; carpeta de la lista de chats, badge, redactar |
| `A02()` | `A01()` y no es un companion (`AnonymousClass091.BRD()` false, es decir `registration_device_id` es 0) | manager de opt-in, ajustes, selección de integrador, handler de notificaciones |
| `A00()` | `A01()` y AB **15732** | entrada "New group", paso de privacidad de grupo |
| `A03()` | `A01()` y AB **11479** | paso de bandeja unificada y bandeja combinada |

`InteropSettingsActivity.onResume` (llama a `finish()`), `InteropOptInSelectIntegratorsActivity.onCreate`, `InteropOptInManager` y el handler de notificaciones `w:interop` vuelven a comprobar `A02()`.

### 2.2 Flags AB (found: id, valor por defecto y sitios de llamada; nombres de la tabla de nombres de un build anterior, coincidencia por id, **inferred**)

| Flag | Nombre heredado (inferred) | Por defecto | Leído en | Controla |
|------|------------------------|---------|---------|----------|
| **7495** | `IS_USER_INTEROP_ELIGIBLE` | false | `C32001Oa.A01`, `C224669lg.A01`, `C230679y0` (badge), `RunnableC23952AUh` (Home), `C0Y5` | gate raíz; estado del badge en Home |
| **15732** | `INTEROP_GROUP_MESSAGING_ENABLED` | false | `C32001Oa.A00` | creación de grupos, paso de privacidad de grupo |
| **11479** | `WA_INTEROP_UNIFIED_INBOX_ENABLED` | false | `C32001Oa.A03`; id también registrado en `C33251Ee2` | paso de tipo de bandeja, bandeja combinada |
| **25512** | `INTEROP_CONTACT_MASTER_ENABLED` | false | `C0ZT`, `C51044MkK`, `C201508iH`, `C93z`, `InteropSelectChatTypeActivity` | entrada "New contact", contactos interop guardados, resolución de nombres |
| **5760** | `INTEROP_PROTOBUF_VALIDATION_ENABLED` | false | `ENP.A00` | enruta los JIDs interop al pipeline estricto `InteropMessage` (8.1) |
| **38723** | sin nombre | false | `EA0.A00` (descriptor) | distribución de sender key dentro de grupos interop (string de log `interop_group_skdm_processing_enabled`) |
| **23701** | `DMA_INFLATE_VIEW_ONDEMAND_ANDROID` | true | `C1R9` | inflado bajo demanda de la cabecera interop de la lista de chats |

Definidos con valores por defecto pero sin lector literal encontrado (uso unknown): **3953** `INTEROP_CLIENT_UX_ENABLED`, **5759** `INTEROP_BOOTSTRAP_ENABLED`, **6613** `INTEROP_WS8_ENABLED`, **18670** `INTEROP_ADD_GROUP_PARTICIPANT_CLIENT_ENABLED`, **20999**, **11518**, **13532**, **14070** (todos false); **22752**, **24016**, **24256**, **23652**, **24275**, **24098** (ajuste de UI `DMA_*`, todos true). El flag **11619** (`ENABLE_DMA_GROUP_JID`) no tiene entrada en las tablas de valores por defecto. Mecanismo: WA_AB_PROPS.md.

### 2.3 Gates que no son AB (found)

- Aviso de consentimiento **20240306** en la etapa **160** (`C24380wI.A0D`): los ajustes muestran la pantalla de configuración solo cuando está aceptado; si no, la pantalla de inicio de opt-in (5.1).
- Cuenta dependiente (`C14980fa`): no elegible; `PaaInteropMigrator` abandona los grupos interop y reinicia el aviso (5.5).
- Dispositivo primario (`A02()`): los companions no pueden hacer opt-in ni configurar.

---

## 3. Identidad: JIDs y dominios

### 3.1 Dominios (found)

| Tipo | Clase | Tipo de JID | Formato | Validación |
|------|-------|----------|--------|------------|
| Usuario interop | `C99O` (`InteropUserJid`) | **22** | `{integrator}-{account}@interop` | un guion (el último divide); integrator de 1-3 dígitos, sin `0` inicial, parseado como int; account de 1-15 dígitos, sin `0` inicial |
| Dispositivo interop | `C41021lm` | **23** | `{integrator}-{account}:{device}@interop` | el índice de dispositivo debe ser **0**, si no `C09B` ("Interop device JIDs must have device index 0") |
| Grupo interop | `C55529Oy6` (`GroupJid`) | **28** | `{gid}@interop.g.us` | gid de 1-20 dígitos, primer dígito 1-9, sin `-` |

- `C0DZ.A0W` = tipo 22, `A0X` = 22 o 23 (1:1), `A0V` = 28, `A0U` = `A0X` o `A0V` (cualquier chat interop); usado en 128 clases. `C41021lm.getRawString()` siempre imprime `:0`. La factory (`UserJid.JID_FACTORY.A04(str, "interop")`, `C9YC.A00`) lanza `C09B` ("Invalid interop JID: ...") ante cualquier violación de reglas.
- Los ids de integrador en las respuestas IQ están acotados a 1-999 (igual que la regla de 3 dígitos). Los ids de grupo no tienen la forma heredada `creator-timestamp`; las operaciones MEX de grupo toman el gid sin dominio (`InteropGroupsManager.A00` elimina `@...`).

### 3.2 Token binario (found)

Tag **244** `JID_INTEROP` (writer `C40411kn.A00`, lector de atributos `C24610wf`): string `user` (id de cuenta, o gid para grupos) -> u16 **device** -> u16 **integrator** -> byte **domain**.

Byte de dominio: **0** = `interop`, **2** = `interop.g.us`; cualquier otro valor lanza excepción ("invalid domain received for JID_INTEROP tuple"). Una tupla de grupo debe llevar device 0 e integrator 0 (si no, "invalid interop group jid"). El reader renderiza el dominio 0 como `{integrator}-{user}[:{device}]@interop` (device omitido cuando es 0). El tag **245** (una forma de JID interop separada en otros clientes) no tiene handler en este build (grep de `C24610wf` / `C40411kn`).

### 3.3 Mapeo y visualización (found)

| Tema | Hecho |
|-------|------|
| LID / PN | `WaJidMapRepository/setJidMapping refused mapping for interop JID`; un JID interop es su propia dirección Signal y su propio id de chat |
| Nombre | fuente de nombre `INTEROP_NAME` (`C0Y7`), valor del campo `display_name` del contacto (`c06290Dn.A07().A00.A0b`); el parser de stanza de mensaje lee `notify` y `display_name` en cada mensaje (`AbstractC33377Eg6.A02`); el uso de `display_name` como push name interop es inferred |
| Miembros de grupo | el parseo de participantes `w:g2` conserva el JID interop en el registro del participante (`C23201A1a` -> `C228499uF.A00(c99o, ...)`), además de `display_name`, `lid`, `phone_number`, `join_time` |
| Datos de perfil | sin foto ni nombre de perfil: "Profile name and photo are not available in third-party chats" (string); solo icono del integrador (caché de 8 MiB `cache/interop_image_cache`, loader `interop_image_loader`) |

---

## 4. Integradores

### 4.1 Modelo (found)

No existe en código, `res/` ni `assets/` ningún nombre de integrador, id fijo ni tabla de tipos de identificador; el servidor decide qué integradores existen, sus ids, nombres y capacidad de grupos. `A3X`: `A00` id, `A03` nombre, `A02` estado (`ONBOARDING`, `ACTIVE`, `REMOVED`), `A04` URL del icono, `A05` optedIn, `A01` tipo de identificador (`USERNAME`, `PHONE`, `EMAIL`), `A06` supportsGroupMessaging. Integrador de un JID: `C99O.A00` -> `C227409sQ.A00` -> `A3X`.

### 4.2 Fetch (found, `C31107Dfz` caso 20, parser `C214369Ee`)

Solicitud `<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><integrator fetch="all"/></iq>` (`to` = JID del servidor, clase `C19380nJ.A00`). Resultado: `<integrator_list opted_in="true"><integrator id status identifier_type name icon opted_in><features group_messaging/></integrator>...</integrator_list>` (nombres de atributos found; la forma del nodo `features` es inferred a partir de la ruta `features/group_messaging`).

Mapa de atributos: `status` = `onboarding` / `active` / `removed`; `identifier_type` = `username` / `pn` / `email`; `features` -> `group_messaging` = `true` / `false`; `opted_in` por defecto `true`. Límites del parser: 0-999 integradores, id 1-999; una entrada sin `name` o `icon` se descarta; un estado o tipo de identificador desconocido lanza excepción. Errores IQ: `bad-request` (400), `internal-server-error` (500) (`A1J.A02` / `A04`).

La corrutina de refresco (`C24110Aar` caso 34, log `IntegratorManager/refreshIntegrators`) escribe la tabla (5.6) y la pref `group_capable_integrators`. Disparadores encontrados: abrir la pantalla de opt-in; el handler genérico `<ack error>` (`C13X`) elimina todas las filas `integrator_display_name` cuando se rechaza un mensaje interop 1:1 (`C24110Aar` caso 35). Otros disparadores no se resolvieron.

---

## 5. Consentimiento, opt-in, ajustes

### 5.1 Aviso de consentimiento (found)

El id de aviso **20240306** es una divulgación de privacidad (`C24380wI`, clase `PrivacyDisclosureDataManager`). Etapa **160** = aceptado (`A0D`); las etapas 105-399 cuentan como "elegible/mostrado" (`A02`). `InteropOptInManager.A01` (`C229349vm`):

```
A02() false -> log "interop is not enabled, stop"
notice 20240306 != 160 -> render notice (C32411Pr.A05); ARH.onUserOptedIn sets has_previously_onboarded and continues; dismiss / deny / error stop
else -> InteropOptInSelectIntegratorsActivity(entryPoint)
```

La etapa **162** la escribe `PaaInteropMigrator` (`C24380wI.A09(null, 20240306, 162, false)`); significado unknown (no es 160, por lo que el aviso cuenta como no aceptado después).

### 5.2 Asistente (found, `A4N`, `InteropOptInSelectIntegratorsActivity`)

```
Select integrators (list from table, header "Select the third-party apps you want people to message you from.")
   ▼
[AB 11479] Unified inbox option (COMBINED | SEPARATED) ──► else skip
   ▼
[AB 15732] Group privacy setting ("Who can add me to third-party groups") ──► else skip
   ▼
InteropOptInManager.A01: notice not accepted -> consent notice (5.1); accepted -> straight on
   ▼  onUserOptedIn
SetOptInIntegrators IQ (full list)
```

Si el aviso ya está aceptado (edición desde ajustes), la pantalla de selección oculta sus botones de cancelar y continuar y `C201718ig.A00` guarda directamente (guardado al cambiar: inferred); el tipo de bandeja y la privacidad de grupo son filas separadas del fragment de configuración. Se infiere que el paso de privacidad de grupo termina en `A01` (log `BaseInteropOptInViewModel onOptInContinue`). Los puntos de entrada son un int (`entryPoint`) registrado en WAM (5.6).

### 5.3 SetOptInIntegrators (found, `C31107Dfz` caso 23, parser `C9EP`)

```xml
<iq type="set" xmlns="w:interop" to="s.whatsapp.net" id=".."><opt_in_integrators><integrator_list>
  <integrator id="12"/> ...      <!-- 0..999 entries, the full desired state -->
</integrator_list></opt_in_integrators></iq>   <!-- result: integrator_list/integrator[@id], each with an optional error child -->
```

Manejo en el cliente (`C24113Aau` caso 40): los errores por integrador se recogen; la tabla se reescribe en una sola transacción (`opt_in_status` borrado para todos, luego establecido para los solicitados menos los ids fallidos). El opt-out no tiene stanza propia: los diálogos de opt-out y la ruta "turn off" usan el mismo set con una lista más corta (inferred por la ausencia de cualquier otra stanza de opt-out; la ruta de lista vacía no se trazó).

Mapeo de errores en UI (`InteropOptInSelectIntegratorsActivity.A0X`): los códigos **500**, **810**, **800** -> "Apps can't be saved right now. Please try again later."; cualquier otro código o nulo -> "Apps can't be saved right now."

### 5.4 Pantallas de ajustes (found, `AndroidManifest.xml`)

Pantallas (todas en `AndroidManifest.xml`): `InteropSettingsActivity` con fragments Main / Optin / Config (inicio cuando el aviso no está aceptado, si no configuración; FAQ de ayuda `317021344671277`); `InteropOptInSelectIntegratorsActivity` (apps); `InteropUnifiedInboxOptionActivity` ("Manage inbox", COMBINED vs SEPARATED); `InteropGroupPrivacySettingUpdateActivity` y `...AddBlocklistPickerActivity` (9.4); `InteropReachNotificationSettingsActivity` ("Third-party chat requests", 6.3); `InteropOptOutDialogFragment` / `...IntegratorDialogFragment` ("Turn off third-party chats?"); `InteropConversationsActivity` (lista de la carpeta); `InteropComposeSelectIntegratorActivity`, `...EnterInfoActivity`, `InteropSelectChatTypeActivity` (nuevo chat / grupo / contacto).

### 5.5 Opt-out y migrator (found)

Con opt-out: los chats existentes pasan a solo lectura (banner del composer "Third-party chats are turned off. You can't send messages in this chat, and you won't receive messages."). `PaaInteropMigrator` (`C0q`): se ejecuta cuando la cuenta es una cuenta dependiente (`C20K.A1W` = restricted) **y** el aviso está aceptado; llama a `LeaveInteropGroup` (`groups_to_leave`, los códigos de respuesta en {200, 400, 401, 403, 404, 405} cuentan como completados), luego escribe la etapa de aviso 162. La expansión de "PAA" es inferred (experiencia por edad); el vínculo con cuenta dependiente es found.

### 5.6 Estado almacenado y analítica (found)

| Almacén | Claves / esquema |
|-------|---------------|
| prefs `interop_ui` | `unified_inbox_option` (UNKNOWN / COMBINED / SEPARATED), `who_can_add_me_to_interop_groups` (int), `who_can_add_me_to_interop_groups_hash`, `who_can_add_me_to_interop_groups_deny_list` (set), `optedInIntegratorNames` (set) + claves de nombre por id, `interop_reach_enabled` (por defecto true), `interop_reach_integrators` (array de int), `interop_reach_notifs` (set de `id:name:display_name:t`), `suspended_interop_groups` (set de gids), `has_previously_onboarded`, `group_capable_integrators`; prefs `interop_badge_prefs`: `pref_interop_badge_disabled`, `pref_interop_badge_account_state`, `pref_interop_badge_third_party_chats_state` |
| tabla `integrator_display_name` | `integrator_id` INTEGER PK, `display_name` TEXT, `status` INTEGER, `icon_path` TEXT por defecto `''`, `opt_in_status` INTEGER por defecto 0, `identifier_type` INTEGER por defecto 0, `group_messaging_supported` INTEGER; índice `integrator_opt_in_index` sobre `opt_in_status` |
| otras tablas | `wa_block_list_interop` (índice único sobre `jid`); filas `wa_address_book` con `raw_contact_id = -5` y `jid LIKE '{id}-%@interop'` (`SAVED_INTEROP_CONTACTS`), no escritas en los contactos del teléfono |
| WAM | 6684 (entrega de banner), 7044 (flujo de onboarding, id de sesión `InteropOnboardingSessionIdManager`), 7168 (acción del usuario), 6680 (bandeja de terceros); el evento 1158 lleva `interopContactsSize`, `interopContactsSizePerIntegrator` |

---

## 6. IQ set `w:interop`

Los cinco RPC de `DmaInteropRPCManager` pasan por `MessageClientSmaxWrapper`; cada IQ lleva `type`, `xmlns="w:interop"`, `to` = JID del servidor, `id`.

| Operación | Tipo | Cuerpo | Límite | Resultado |
|-----------|------|------|-------|--------|
| FetchIntegrators | get | `<integrator fetch="all"/>` | - | 4.2 |
| FetchUsers | get | `<users><user external_id integrator_id/></users>` | **1-20 usuarios** | 7.2 |
| SetOptInIntegrators | set | `<opt_in_integrators><integrator_list><integrator id/>` | 0-999 | 5.3 |
| GetReachabilitySettings | get | `<reachability_settings/>` | - | 6.3 |
| SetReachabilitySettings | set | `<reachability_settings enabled="true\|false"><integrator id/>...` | 0-999 | resultado / error |
| Block / unblock | set | `<blocklist><item action="block\|unblock" jid="{interop JID}"/></blocklist>` | - | resultado; errores `IQErrorBadRequest`, `IQErrorInternalServerError` |

### 6.1 Bloqueo y denuncia (found)

El bloqueo interop usa `xmlns="w:interop"` (`C31106Dfy`, helper `C9EF`, log `InteropBlocklistHelper/getInteropBlocklist/error code:`) y la tabla `wa_block_list_interop`. UI: "Blocked in third-party chats"; el diálogo de bloqueo dice que las personas bloqueadas en WhatsApp aún podrían contactar al usuario en la app de terceros. La denuncia de spam usa el flujo genérico de spam (`spam_flow`, `C9E2`) con texto de diálogo por integrador. Enrutamiento de notificaciones: `AbstractC32331E9w` mapea el xmlns `w:interop` al handler id **270**; `EnumC32096E0u.NOTIFICATION_W_INTEROP` = `"w:interop"`.

### 6.2 Notificación ping (found, `X.0xL` anónimo en `C1S0`)

`<notification xmlns="w:interop" t=".."><ping display_name=".."><X id=".." name=".."/></ping></notification>` (el código no comprueba el tag `X` del primer hijo de `ping`).

Solo se acepta un primer hijo llamado `ping` (si no, log `unknown tag=`). Con `A02()` true añade `id:name:display_name:t` a la pref `interop_reach_notifs`, publica una notificación local en el canal `critical_app_alerts@1` (cuerpo "Chatting with people on third-party apps is an optional WhatsApp feature in the European Region.", acción "Manage requests", receiver de descarte `InteropNotificationDismissReceiver`) y registra WAM 6684. El disparador del servidor (alguien de un integrador intentó contactar al usuario) es inferred a partir del texto de ajustes "Get notified when someone wants to message you from a third-party app."

### 6.3 Alcanzabilidad (found)

Los ajustes son por **integrator** (hijos `<integrator id>`, límite 0-999), no por usuario. El valor por defecto de `enabled` es `true` en `interop_reach_enabled`. No se encontró código de suscripción de presencia para JIDs interop (inferred: la alcanzabilidad la sustituye).

---

## 7. Descubrimiento de usuarios

### 7.1 FetchUsers (found, `C31107Dfz` caso 21, parser `C9EQ`)

Los JIDs interop provienen solo de este IQ; USync no tiene protocolo interop (WA_USYNC.md).

```xml
<iq type="get" xmlns="w:interop" to="s.whatsapp.net" id=".."><users>
  <user external_id="alice@example.org" integrator_id="12"/>          <!-- 1..20 -->
</users></iq>
<!-- result -->
<users>
  <user jid="12-105012705411308@interop" external_id=".." normalized_external_id=".." integrator_id="12"/>
  <user external_id=".." normalized_external_id=".." integrator_id="12"><error code="404" text="item-not-found"/></user>
</users>
```

Resultados por usuario: éxito `user[@jid]` (`C9DG`, jid parseado como `C99O`); `item-not-found` código por defecto **404** (`C9DH`); `forbidden` por defecto **403** (`C9DF`); `internal-server-error` (`C9DE`).

Errores del IQ completo: `bad-request`, `internal-server-error`. Listas de resultado en `C9FA`: no encontrado, forbidden, error de servidor, mapa resuelto `{(external_id, integrator) -> UserJid}`. Tanto la solicitud como la respuesta rechazan 0 o más de **20** usuarios.

### 7.2 Entrada de identificador y contactos guardados (found, `InteropComposeEnterInfoActivity`)

| Tipo de identificador | UI | Valor enviado como `external_id` |
|-----------------|----|------------------------------|
| `USERNAME` | un campo ("Enter Username") | texto |
| `PHONE` | selector de país + número | código de país y número concatenados (filtro por carácter, regla no trazada) |
| `EMAIL` | un campo | texto |

Flujo: elegir app (`InteropComposeSelectIntegratorActivity`, integradores con opt-in de la tabla) -> tipo de chat (`InteropSelectChatTypeActivity`: "New chat", "New group" si AB 15732 y el integrador soporta grupos, "New contact" si AB 25512) -> introducir id -> FetchUsers -> abrir chat con el JID devuelto. Strings: "This user can't be found" (no encontrado), "This user is already a group member" (alta en grupo), "Couldn't create the chat. Please try again.".

Con AB 25512, `ContactFormActivity.verifyInteropIdentifierAndSave` resuelve el id mediante FetchUsers (`C24113Aau` caso 41) y guarda una fila `wa_address_book` (raw_contact_id -5); "Usernames and contacts added to third-party chats will not save to your phone."

---

## 8. Mensajería

### 8.1 Selección del pipeline (found)

Descifrado (`ENP.A00`): cuando AB **5760** está activo y el JID del chat cumple `A0U` (interop 1:1 o grupo interop), el texto cifrado lo maneja `C34471Exu` (`DecryptionCallbackInterop`); si no, se ejecutan los callbacks normales. Los tipos de texto cifrado que maneja `ENP` son los comunes: **0** (`msg`), **1** (`pkmsg`), **2** (`skmsg`, sender key), **4** (ruta de bot, no interop). Por tanto, interop usa las mismas sesiones Signal y sender keys que los chats nativos.

```
<message from="12-123[:0]@interop" ..><enc type=pkmsg|msg|skmsg v=2>...</enc></message>
   │  ENP.decryptMessage (Signal / sender key)
   ▼
C34471Exu.handlePlaintext
   │  remove padding (last byte = pad length; empty / zero / >= length fails, log DecryptUtil/removePadding)
   │  C33369Efy.A03(E0T.INTEROP_MESSAGE, ...)          ── message pipeline type "interop_message"
   ▼
C34720F4p (InteropChatMessageHandler)
   │  parse bytes as DTF (InteropMessage subset)
   │  unknown-field check -> failure 70
   │  C32718EOz.A00(EUQ) -> FMessage via type handlers; SKDM (group) processed if AB 38723
   ▼
store, receipt, notification
```

Reporte de fallos: `C34720F4p.A00` devuelve `C33063Eaz(reason)` y llama a `A0Y(null, key, reason, 491)` en la ruta del recibo; `C34471Exu` llama a `C33369Efy.A07(.., 491, reason, ..)` para texto plano inválido. El literal **491** es común a ambos (significado sin resolver).

### 8.2 Subconjunto de texto plano `InteropMessage` (found, `DTF`)

El texto plano **no** es el `Message` completo. `DTF` declara exactamente estos campos, numerados como en el `Message` completo:

| Campo | Número | Tipo | Handler | Notas |
|-------|--------|------|---------|-------|
| `conversation` | **1** | string | `FBN` | texto plano |
| `senderKeyDistributionMessage` | **2** | message | `C34720F4p` | id de grupo + SKDM axolotl; el id de grupo debe ser igual al chat cuando el chat es un grupo |
| `imageMessage` | **3** | message | `FBK` | |
| `extendedTextMessage` | **6** | message | `FBN` | campos de vista previa de enlace |
| `documentMessage` | **7** | message | `FBI` | no cuando el `type` de la stanza es `medianotify` |
| `audioMessage` | **8** | message | `FBH` | notas de voz mediante `ptt` |
| `videoMessage` | **9** | message | `FBL` (sin `gifPlayback`) / `FBJ` (`gifPlayback`) | |
| `reactionMessage` | **46** | message | `FBM` | |
| `ptvMessage` | **66** | message | ninguno encontrado | aceptado por el esquema y validado en busca de campos desconocidos; no existe parser FMessage en el registro (recepción de video-note sin resolver) |

La comprobación de campos desconocidos lee por reflexión el conteo de campos desconocidos de `DTF` y de los submensajes de imagen, video, PTV, audio, documento, extended text y reacción; un conteo de 1 o más devuelve el fallo **70**. Por tanto, los campos fuera de `DTF` hacen fallar el mensaje: por ejemplo `messageContextInfo` (35), `protocolMessage` (12), sticker, contacto, ubicación, encuesta (inferred a partir del esquema; no se ejercitó el efecto de un campo concreto).

### 8.3 Tipos de mensaje soportados y límites (found)

| Tipo | Reglas aplicadas en la recepción (motivo de fallo) |
|------|--------------------------------------------|
| Texto, video | `conversation` o `extendedTextMessage.text`, truncado a **65536** caracteres; vista previa de enlace solo si `matchedText` es una URL válida contenida en el texto; título y descripción truncados a 65536; tipo de vista previa mapeado a 0, 1, 4, 5, 6, 7; video y GIF comparten el parser de media `C33395EgO.A05` (`gifPlayback` elige `FBJ`) |
| Imagen | `mediaKey` obligatorio (16); `fileLength` >= 0 (13); `fileSha256` de 32 bytes (14); `fileEncSha256` de 32 bytes si está presente (14); mime **solo `image/jpeg` o `image/png`** (17); `directPath`, width, height copiados; triple de miniatura (direct path, sha, enc sha) opcional; scans progresivos aceptados cuando hay 2-20 longitudes de scan y la longitud de `scansSidecar` / 10 es igual al conteo y la suma cabe en un int |
| Audio | `mediaKey` obligatorio (16); `fileLength` > 0 (13); hashes de 32 bytes (14); el mime debe ser un tipo de audio conocido (17); flag `ptt`; `waveform` se conserva solo si tiene 1-192 bytes; `backgroundArgb`; `seconds` |
| Documento | `mediaKey` obligatorio (16); `fileLength` >= 0 (13); hashes de 32 bytes (14); `title` truncado a 65536; la miniatura JPEG se conserva si pasa la comprobación de tamaño |
| Reacción | `key.id` y `key.remoteJid` no vacíos; `text` más una versión de edición distinta de cero se rechaza (warning `edit version and text message are both set`); `senderTimestampMs` se conserva; una stanza con `type="reaction"` debe producir un mensaje de reacción (si no, fallo **76**) |
| Respuesta / cita | `ContextInfo` con `stanzaId`, `participant`, mensaje citado (parseado de nuevo como `DTF`, `ContextInfoProtobufInterop`), `quotedType`; en el lado emisor `InteropContextInfoBuilder` serializa el mensaje citado de forma recursiva |

No aceptados (fuera de los 9 campos): stickers, contactos, ubicaciones, encuestas, eventos, plantillas, view-once. El selector de adjuntos oculta las entradas de contacto, ubicación, encuesta, evento, group status, imagine, pago, pix y remesa para los chats interop (comprobaciones `A0L`, `A0M`, `A0P`, `A0Q`, `A0R`, `A0T`, `A0U`, `A0X` de `ConversationAttachmentContentView`); documento, cámara, galería y audio no están condicionados por comprobaciones interop (se infiere que permanecen). Los mensajes temporales no están soportados ("disappearing messages are not supported in third-party chats", también excluidos del ajuste de temporizador por defecto). Los bytes de media viajan por la ruta normal de media de WhatsApp (clave, hashes y `directPath` en el mensaje; valor de analítica de origen de descarga 15 = `interop`).

### 8.4 Lado de envío (found)

| Paso | Comportamiento |
|------|-----------|
| Serializador | `C33446EhE`: el JID de chat de tipo 22/23 (`A0X`) usa el serializador interop (`C32718EOz.A01` con `ADs` por tipo, logs `buildE2eInteropMessage`); los demás chats usan el builder normal, por lo que los **grupos** interop (tipo 28) usan el builder normal |
| Clase FMessage no soportada | handler `FBG` -> lanza `E3G` 70 antes del envío; clase incorrecta para un handler -> `E3G` 0 |
| Comprobaciones de imagen | mime `image/jpeg` o `image/png`, si no `E3G` 17 (`null` pasa a `image/jpeg`); hash que no es de 32 bytes `E3G` 14; falta la media key `E3G` 16; los contribuyentes de stanza `F6B`, `F6G`, `F6I`, `F68`, `F69`, `F6H`, `F6M`, `F6X` no tienen rama interop (adjunto sin resolver) |
| Encryptor (`F6P`) | para chats interop (`A0U`) el encryptor omite `C33284Eea.A02` (añade metadatos de lista de dispositivos mediante `AbstractC30999De0.A03`, inferred) y omite `paddingBytes` (tamaño de AB 1723) |
| `<meta>` (`F6K`) | `content_type="add_on"` se omite para chats interop |
| Reporting token (`F6L`) | se omite cuando el destino es un JID de dispositivo interop |
| Lista de dispositivos / ADV | el índice de dispositivo interop es siempre 0; `DeviceADVInfoHandler` tiene una comprobación interop en su entrada (`C24230w2`, salida anticipada inferred); no es posible fan-out multidispositivo (inferred: un dispositivo por contacto) |

Más diferencias con los mensajes nativos: los chats interop usan el tipo de pipeline `interop_message` (`E0T`) en lugar de los tipos texto / media / reacción; valor de tipo de chat WAM 5 en el evento de descifrado (`AbstractC33424Egr`) y 6 en el evento `FNR` (nativo 3 / 1); los add-ons de message-secret (votos de encuesta, reacciones cifradas, ver WA_MESSAGE_SECRETS.md) no están entre los 9 campos, por lo que no pueden llegar a chats interop (inferred).

---

## 9. Grupos interop

### 9.1 Modelo (found)

Un grupo es `{gid}@interop.g.us` (tipo 28). Los miembros son cuentas de WhatsApp (añadidas como JIDs de usuario **LID**; found en la ruta de adición, la ruta de creación es inferred igual) y JIDs interop. Los metadatos del grupo vienen de MEX en lugar de `w:g2`: `C11410Yt.A0F` llama a `GroupXmppMethods/sendGetInteropGroupInfo` para el tipo 28. El estado es `UNSET`, `ACTIVE`, `SUSPENDED`; los gids suspendidos se guardan en la pref `suspended_interop_groups`. Banners del composer: grupo suspendido "You can't send messages to this group because all third-party members have left."; con opt-out o eliminado "... because you're no longer a member."

### 9.2 Operaciones MEX (found; doc ids de `assets/whatsapp-android-mex_client_persist_ids.json`)

| Operación | doc_id | Campo raíz | Entrada | Salida / notas |
|-----------|--------|-----------|-------|----------------|
| `GroupsCreateInteropGroup` | `25726817620301611` | `xwa2_interop_group_create` | `input.participants[{jid}]` | `group`: `gid`, `creation_time`, `creator_v2`, `display_name`, `participants_v2`; no se envía asunto |
| `LeaveInteropGroup` | `25346167795013271` | `xwa2_interop_group_leave` | `input.groups_to_leave[{gid}]` | `response_code` por grupo; {200, 400, 401, 403, 404, 405} tratados como finales |
| `AddParticipantsToInteropGroup` | `25732168276369451` | `xwa2_interop_add_participants_to_group` | `input.gid`, `input.participants[{jid}]` | los miembros de WhatsApp se mapean primero de PN a LID; un LID `null` aborta la llamada |
| `QueryInteropGroupInfo` | `32734144032867938` | `xwa2_interop_group_query_by_id` | `group_input.gid` | `state`, `gid`, `creation_time`, `creator_v2`, `participants_v2` |
| `InteropPrivacySettingsQuery` | `24849123668112654` | `xwa2_fetch_wa_users` -> `interop_privacy_settings` | `interop_privacy_settings_query_input{feature, dhash}` para el LID propio | `settings_data`, `dhash`, `denied_contacts[{jid}]` |
| `InteropPrivacySettingsUpdate` | `25421856497452763` | `xwa2_interop_privacy_setting_update` | `feature`, `setting` | `success` |
| `InteropPrivacySettingWithContactListUpdate` | `24913399124998598` | `xwa2_interop_privacy_setting_with_contact_list_update` | `contact_list_type`, `contacts`, `dhash` (`none` si falta), `feature`, `setting` | `success` |

Los errores de creación y adición aparecen como "This group couldn't be created" / "Make sure everyone you add to this group has third-party chats turned on." / "A group with these members already exists." (strings found). Crear un grupo requiere al menos un usuario del integrador elegido ("To create this third-party group, you need to select at least one %1$s user.").

### 9.3 Notificaciones MEX (found, `C0WQ`)

| Notificación | Handler | Efecto |
|--------------|---------|--------|
| `NotificationInteropGroupCreateUpdate` | rama `AbstractC23194A0r` (log `CreateInteropGroupNotificationHandler/`) | crea el grupo local a partir de `gid`, creador y participantes |
| `NotificationInteropGroupParticipantsUpdate` (`Xwa2NotifyInteropGroupOnParticipantChange`) | `A0B` | añade participantes con source `general_chat_auto_add`, elimina los participantes que se fueron; retorna antes (`no updates needed to gid=`) cuando `C22300su.A15()` es false |
| `NotificationInteropGroupPropertyUpdate` | `A0C` | `state` ACTIVE o SUSPENDED -> `suspended_interop_groups` |

### 9.4 Quién puede añadirme (found, feature `GROUPADD`)

Enum de ajuste `C9U8`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `ALL`, `MYCONTACTS`, `MYCONTACTSEXCEPT`, `MYCONTACTS_AND_ENABLED_INTEROP_INTEGRATORS`, `NONE`. La variante con lista de contactos lleva la lista de denegados (`contact_list_type`, `contacts`). Texto: "You can only be added to third-party chats by people who either use or have selected the same messaging app." El ajuste se almacena por LID propio y se cachea con `dhash`; la aplicación es del lado del servidor (inferred), el cliente solo presenta el ajuste.

---

## 10. Lista de chats, modelo de hilo, UI

| Elemento | Hecho (found) |
|------|--------------|
| Hilo | un chat por JID interop (1:1) o por gid; almacenado en las tablas de chat normales; sin tabla de hilos separada |
| Carpeta | `InteropConversationsActivity` / `Fragment`; vista de cabecera `InteropView` en la lista de chats (`C31071Ju`, log `ChatListInteropChatsDelegate/`); se muestra cuando es elegible y el aviso está aceptado, o cuando ya existen chats interop; oculta cuando la bandeja es COMBINED |
| Modo de bandeja | SEPARATED: carpeta dentro de la bandeja principal o el menú "More"; COMBINED: chats interop listados en la pestaña Chats (chip de filtro `interop` en los filtros de chat, `THIRD_PARTY_FILTER`) |
| Fila / búsqueda | etiqueta con el nombre del integrador e insignia de icono en el avatar; los chats de terceros no se incluyen en los resultados de búsqueda |
| Banner / badge | "You're messaging someone outside of WhatsApp. Third-party apps may have different security."; badge de Home desde `pref_interop_badge_*`, condicionado por AB 7495 (`C230679y0`) |

---

## 11. Baileys (`baron-baileys-v2` 1.5.17, `src/Socket/interop.js`, `WABinary/decode.js`, código fuente leído, nada probado)

| Tema | Baileys | Android 2.26.41.6 |
|-------|---------|-------------------|
| Integradores | `12` (BirdyChat, email) y `13` (Haiket, pn) codificados de forma fija | ninguno en el cliente; lista del servidor |
| Búsqueda por lotes | `INTEROP_BATCH_MAX = 256` | **20** (builder de la solicitud y parser de la respuesta) |
| Opt-out | `<opt_out_integrators><integrator_list>` | no existe tal nodo; IQ de opt-in con una lista más corta |
| Reachability set | `<reachability_settings enabled><user external_id integrator_id/>` | hijos `<integrator id/>` |
| Consentimiento | IQ `tos` `trackable id=20240306 result=105`, luego `160` | aviso 20240306 etapa 160 = aceptado (found); forma en la red del IQ del aviso no trazada |
| JID binario | el lector de la tupla 244 lanza excepción salvo que domain = 0; tag 245 manejado | tag 244 con domain 0 **y** 2 (grupos); sin tag 245 |
| Notificaciones | `type="interop"` con `stella_interop_enabled`, `peer_device_presence`, `ig_profile`, fbid | el handler `w:interop` id 270 maneja solo `ping` |
| Envío / recepción | texto plano como `conversation`, reporting token omitido; comentario en `Defaults/index.js`: recepción interop no implementada | serializador restringido a los 9 campos; parser estricto `InteropMessage`; ids MEX de grupo y notificaciones idénticos en alcance |

Por qué falla (inferred a partir del código comparado arriba):

| Síntoma | Causa | Solución |
|---------|-------|-----|
| Error de decodificación en JID de grupo interop | el lector de tuplas rechaza el byte de dominio 2 | aceptar el dominio 2 -> `{gid}@interop.g.us`, exigir device e integrator 0 |
| El peer descarta el mensaje con un fallo de campo desconocido | cualquier campo fuera de los 9 (por ejemplo `messageContextInfo` con un `messageSecret`, `protocolMessage`) falla si el peer ejecuta el mismo parseo estricto (inferred; los envíos interop de Baileys no se trazaron para estos campos) | construir `Message` solo con los campos 1, 2, 3, 6, 7, 8, 9, 46 (y 66) |
| El opt-out no tiene efecto | `opt_out_integrators` no existe en el cliente | enviar SetOptInIntegrators con los ids restantes |
| No llega nada a las sesiones companion | los contactos interop solo tienen device 0 | mantener interop en la sesión primaria |

---

## 12. Casos de error

| Síntoma | Causa | Dónde |
|---------|-------|-------|
| Las pantallas interop se cierran de inmediato o nunca aparecen | `C32001Oa.A02()` false: flag 7495 desactivado, cuenta dependiente o dispositivo companion | 2.1 |
| "Apps can't be saved right now" | fallo de SetOptInIntegrators; los códigos 500 / 810 / 800 reciben el texto "try again later" | 5.3 |
| "This user can't be found" | FetchUsers `item-not-found` (404) | 7.1 |
| Excepción de JID interop inválido | integrator que no tiene 1-3 dígitos / `0` inicial, account que no tiene 1-15 dígitos, índice de dispositivo distinto de 0 | 3.1 |
| Grupo no creado / composer deshabilitado | error MEX de creación o conjunto de miembros duplicado / opt-out, grupo suspendido, ya no es miembro | 9.1, 9.2 |
| Mensaje entrante descartado, motivo 70 / 13 / 14 / 16 / 17 / 76 / 26 | campo desconocido o tipo sin handler / tamaño incorrecto / longitud de hash incorrecta / falta la media key / mime inválido / discrepancia de tipo de reacción / excepción de parseo | 8.2, 8.3 |
| SKDM de grupo ignorado | AB 38723 desactivado (log `sender key distribution message skipped`) | 8.1 |
| Faltan nombres de integrador tras un error de envío | el ack error borró `integrator_display_name` | 4.2 |

---

## 13. Distinciones clave

| No confundir | Hecho |
|----------------|------|
| `w:interop` vs USync | el descubrimiento de contactos es FetchUsers sobre `w:interop` (máx. 20), no un protocolo USync |
| `@interop` / `@interop.g.us` / `@g.us` | usuario y dispositivo, grupo, grupo nativo; un JID interop nunca se mapea a LID ni a PN |
| `InteropMessage` vs `Message` | la recepción acepta 9 campos; el envío omite contexto y padding para interop |
| privacy token `trusted_contact` | job genérico de privacy token (WA_TCTOKEN_CSTOKEN.md); no se encontró código específico de interop en este build |
| "interop" de UPI | `IndiaUpiInterOpHybridActivity`, `IndiaUpiInteropSendToUpiActivity`, los flags de nota de pago `isInterop` son funciones de pagos, sin relación |
| "interop" de Compose / EXIF | `androidx.compose.ui.viewinterop`, `InteroperabilityIFDPointer` son librerías |
| Elegible vs con opt-in vs consentimiento | flag 7495 = elegible; `opted_in` por integrador viene del servidor; consentimiento = aviso 20240306 etapa 160 |

---

## 14. Flujo completo

```
[User]              [Client]                                   [WA server]              [Integrator app]
  │ Settings > Third-party chats
  ├──────────────────► A02(): flag 7495, primary, not dependent
  │                    notice 20240306 != 160 ──► show ──► accept ──► stage 160
  │ apps (+ inbox type, + group privacy)
  ├──────────────────► SetOptInIntegrators ─────────────────► opted_in list; table rewritten
  │ New chat > app > id
  ├──────────────────► FetchUsers (1..20) ──────────────────► jid 12-<account>@interop / 404 / 403 / 500
  │ send text / image / video / audio / doc / reaction
  ├──────────────────► restricted Message (no context, no padding), Signal encrypt, device 0
  │                    <message to=..@interop> ─────────────► bridge (inferred) ───► [Integrator app]
  │                    <message from=..@interop><enc/> ◄──────────────────────────── reply
  │                    ENP -> DecryptionCallbackInterop -> DTF parse (unknown field -> 70) -> FBx -> FMessage
  │ ◄──────────────── chat row, notification
  │                    <notification xmlns=w:interop><ping/> ◄─ server (trigger inferred)
  │ ◄──────────────── local notification "Manage requests"; reachability per integrator
  │ New group (flag 15732)
  ├──────────────────► GroupsCreateInteropGroup (LID + interop JIDs) ──► gid@interop.g.us
  │                    MEX notifications: create / participants / property; SUSPENDED -> composer blocked
```

---

## 15. Desconocidos

| Tema | Estado |
|-------|-------|
| Forma en la red del IQ del aviso de consentimiento | no trazada; solo se conocen las etapas 160 (aceptado) y 162 (escrita por el migrator) |
| Bridge del lado del servidor, entrega al integrador, manejo de claves en ese lado | no visible en el cliente; el cliente usa sesiones Signal y sender keys ordinarias |
| Cambio de identidad / número de seguridad para contactos interop | no trazado |
| Llamadas, encuestas, ediciones, revocaciones, cambio de identidad / número de seguridad para chats interop | no se encontró ruta de código interop (ningún string interop en el código de llamadas); no trazado |
| Recepción de PTV (`ptvMessage`) | campo aceptado, ningún parser encontrado |
| Literal 491 en la ruta de fallo; códigos de error 810 / 800; disparadores de FetchIntegrators distintos de la pantalla de opt-in | sin resolver |
| Lectores de los flags 3953, 5759, 6613, 18670, 20999, 11518, 13532, 14070 | sin lector literal; pueden leerse mediante descriptores |
| Confirmaciones de lectura hacia contactos interop | `ClientPayload.interopData` (campo **38**, `C38671hT`: `accountId` 1, `token` 2, `enableReadReceipts` 3) existe en el esquema; nada en este build lo rellena |
| Si el servidor aplica la regla de la Región Europea | solo texto de UI; sin comprobación en el cliente |
