<!-- src-sha1: 193c35598b4e82f9c32a0c5d2cee4dbf2d708588 -->
# WhatsApp Interfaz impulsada por el servidor — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-23
**Alcance:** Pantallas y acciones impulsadas por el servidor en Android: máquina de estados de acciones Phoenix/FCS (IQ `xmlns="phoenix"`, tipos de estado, operadores de choice, registro de recursos), pantallas Bloks (obtención por GraphQL, doc ids y enrutamiento por app-id, payload JSON, ids de función Lispy, espacios de nombres de acciones, component queries, cachés), native flow messages (registro de botones NFM), WhatsApp Flows (puente WebView, política de host de SecureWebView, JSON del flow), respuesta enriquecida de IA y tarjeta FMX (lo que no es impulsado por el servidor), scripts del navegador integrado (puente iabjs y nonce), sandboxing y feature flags, relevancia para Baileys

---

## 1. Qué es (técnicamente)

WhatsApp Android no tiene un único motor de UI impulsada por el servidor. Existen cuatro mecanismos independientes; cada uno obtiene una descripción de un servidor (o la lee de un mensaje) y controla código nativo. Todas las afirmaciones provienen del análisis estático del APK decompilado; no se capturó nada en la red. Niveles: **found** = leído en código o datos, **inferred** = deducido, **unknown** = no resuelto. Los nombres ofuscados cambian en cada build y se volvieron a resolver en 2.26.41.6.

| Mecanismo | Describe | Portador | Renderizador / ejecutor | Dónde se usa |
|-----------|----------|----------|-------------------------|--------------|
| Phoenix (los nombres de clase dicen FCS "flow configuration service", etiqueta de log FDS) | Control de flujo: estados `resource` / `choice` / `pass` / `succeed` / `subflow` | IQ `<iq xmlns="phoenix">` con hijo `<fds>` | Máquina de estados `QKb`, manejadores de recursos (`AbstractC57917Pxu`) | Onboarding de pagos, address message, encuesta de negocio, flujos de tarjeta de Brasil |
| Bloks | Pantallas: árbol de componentes + scripts Lispy + component queries asíncronas | POST GraphQL por HTTPS a `graph.<domain>/graphql` | Actividades y fragmentos host Litho/RenderCore | Pagos, soporte, suscripciones, consentimiento, vinculación con Accounts Center, minishops, encuestas, consentimiento de negocio de Meta AI |
| Native flow messages (NFM) | Botones en mensajes interactivos (`nativeFlowInfo` name + JSON de params) | Mensaje (protobuf) | Despacho `C33370Efz` a unas 40 clases de acción | Botones CTA, `address_message`, `galaxy_message` (Flows) |
| Aplicación web WhatsApp Flows | JSON de flow renderizado por una aplicación web alojada | HTTPS (`flows.whatsapp.net`) en un `SecureWebView` + un canal de mensajes `WhatsAppBridge` | `WaFlowsWebViewBottomsheetModalActivity` / `FlowsWebBottomSheetContainer` | Formularios de negocio (`galaxy_message`, flexible checkout) |

Puntos decisivos:

- Phoenix es la capa de control, Bloks es la capa de vista. Un estado Phoenix `resource` con id `open_bloks_screen_graphql` abre una pantalla Bloks; las acciones Bloks `wa.action.phoenix.*` vuelven a la máquina de estados (sección 3.5; conexión inferida a partir de los nombres).
- Bloks no es MEX ni IQ. Es un POST GraphQL al estilo Meta (`doc_id` + `variables`) por HTTPS (found, `AbstractC40195HfH`). Phoenix es IQ. La clase de resultado de la consulta del endpoint de Flows (`AnonymousClass456`) comparte la base del parser de respuestas de Bloks; su transporte no está resuelto (sección 4.5).
- El contenido del servidor no puede nombrar código nativo arbitrario. Toda ruta pasa por un registro fijo: ids de recurso Phoenix (15 en el código), ids de función Bloks (681 con nombre), nombres de botón NFM (39), métodos del puente de Flows (30), lista de xmlns permitidos para IQ de Bloks (2 entradas).
- No se encontró verificación de firma de payload para los payloads de Bloks ni de Phoenix. `BloksTrustedPayload` (`verifiedRoot`) existe y tiene cero referencias (found, smali y Java).
- No impulsado por el servidor: la tarjeta de confianza FMX (mensaje de sistema creado por el cliente), la respuesta enriquecida de IA (conjunto fijo de componentes protobuf), los tres archivos `assets/json/bloks_*_template.json` (andamiajes de carga/error, no pantallas de producto).

Informes relacionados: AB props (IQ `abt`, ids de flag) en `WA_AB_PROPS.md`; respuesta enriquecida de IA en `WA_META_AI.md` sección 6.3. No se localizó ningún framework con nombre Genie (búsqueda de cadenas; ausencia no demostrada).

---

## 2. Máquina de estados de acciones Phoenix

### 2.1 Componentes (found, nombres de 2.26.41.6)

| Rol | Clase | Notas |
|-----|-------|-------|
| Runtime | `QKb` | Etiqueta de log `FcsStateMachine`; `A03` ejecuta un estado, `A04` sigue `next` o hace pop de la pila, `A05` termina |
| Gestor FDS | `C58392QJx` | Inicia una config (`A08`), envía el IQ (`A07`), construye el mapa de estados a partir de la respuesta (`A01`) |
| Constructor de IQ | `C31107Dfz` (ctor con `C9E1`), `C9E1`, `C31085Dfd` | `xmlns="phoenix"` |
| Parsers de respuesta | `F7J` (`<iq><fds>`), `F8I` (casos 17 a 20, 27, 28), `F7Y` resource, `F7Z` choice, `C34784F7b` pass, `C34783F7a` succeed, `C34785F7c` subflow, `C34786F7d` version_check | Parser genérico de esquema de atributos (`C197428ac`) |
| Estados parseados | `P2W` resource, `P2U` choice, `P2T` pass, `P2S` succeed, `P2V` subflow, `C31057DfB` version_check | Parte común `P2Q`: `name`, `input_path`, `input_selector`, `next`, `result_selector`, `result_path` (`C33411Ege.A03`) |
| Estados de runtime | `C55819P7c` resource, `C55817P7a` choice, `C55818P7b` pass, `P7Z` succeed, `C55820P7d` subflow | Mapeo en `C58392QJx.A01` |
| Base de recursos | `AbstractC57917Pxu` | `A02()` = id de recurso, `A04(...)` = ejecutar con mapa de parámetros, id por defecto `throw_error` |
| Binding / registro | `C51E` (id + manejador lazy), `InterfaceC148426Oz.CP3()`, unión `C138515tp` | Registros: `C135435oi`, `C135425oh`, `C135415og`, `C53207NpW`..`C53211Npa` |
| Operadores / errores / callback | `RsJ` (28 operadores), `AbstractC56245PPq`; `Q6G` (`catch`); `C57560Pry` (`A00(error, result)`, `A01(result)`) | |

### 2.2 Obtención: IQ (found, `C31107Dfz`, `C58392QJx.A07`)

```
<iq xmlns="phoenix" type="get|set" id="...">
  <fds config="<config name>" state="<start state>" parameters="<json>">
    <context ... parameters='{"session-id":"...","bloks-versioning-id":"13c6e3b8...(64 hex)"}'/>
  </fds>
</iq>
```

| Elemento | Valor | Tier |
|----------|-------|------|
| `type` | `get` al iniciar (`A08`), `get` o `set` para el recurso `send_fds_iq` | found |
| Enteros de tipo de IQ / timeout | 302 (get), 303 (set), 32000 ms | found |
| `state`, `parameters` | solo se escriben cuando no están vacíos; `parameters` = JSON de las entradas no nulas | found |
| `bloks-versioning-id` | cadena constante de 64 hex, mismo valor en todos los constructores de petición Bloks (sección 3.2) | found |
| Anidamiento del nodo context | `<context>` que lleva el JSON; anidamiento exacto del nodo interno no resuelto | unknown |

Respuesta (found, `F7J`, `F8I`):

| Elemento | Contenido | Usado para |
|----------|-----------|------------|
| `<fds>` attrs `state`, `parameters` | pista de inicio | parseado, no seguido más allá |
| `<states start_at="...">` + `<state ...>`+ | el programa (sección 2.3) | init de `QKb`, log `initializeStateMachine num_states` |
| `<next_screens>` + `<screen is_entry_screen app_id bloks_server_params sources>` | pantallas Bloks a precargar | `C58392QJx.A06` (precarga) |
| `<screen_data parameters>` | blob de datos de pantalla | parseado |
| `<persist_data>` + `<data ...>` | valores que el host conserva | `C58392QJx.A02` (callback por clave) |

Un error de IQ se devuelve al llamador como `error` (`BtN`) y se elimina la entrada pendiente del gestor.

### 2.3 Tipos de estado (found)

El parser acepta la lista de discriminadores `FDSResourceState|FDSChoiceState|FDSSucceedState|FDSPassState|FDSSubflowState|FDSVersionCheckState` (`F8I` caso 27). El atributo `type` es la cadena fija de la segunda columna.

| Tipo | `type` | Atributos propios | Comportamiento en runtime |
|------|--------|-------------------|---------------------------|
| Resource | `resource` | `id` (id de recurso), `parameters`, `merge`, `merge_param`, `catch` | Busca `id` en el registro; un id ausente da el error `ResourceNotFound`; ejecuta el manejador; resultado combinado según `merge`; pasa a `next` |
| Choice | `choice` | `default` (siguiente estado de respaldo), `catch`, hijos `<choice choice="{json}"/>`+ (una clave de operador + `next`) | Evalúa operadores sobre el JSON de entrada; gana la primera coincidencia, si no `default`; se requiere al menos un choice |
| Pass | `pass` | `parameters` | Reescribe datos y pasa a `next`, sin manejador |
| Succeed | `succeed` | ninguno | Éxito terminal (`A05` sin error) |
| Subflow | `subflow` | `launch_mode` (`child` o `embedded`), `config`, `parameters`, `catch` | `child`: nuevo gestor y máquina de estados; `embedded`: obtiene otra config en la misma sesión (inferred de `C55820P7d`) |
| Version check | `version_check` | `default`, hijo `<choice>` | Parseado (`C31057DfB`) pero sin rama en `C58392QJx.A01`; el estado se descarta (found); una transición hacia él fallaría con `state not found for name` (inferred) |

El parser no tiene estado `fail`; el manifiesto aún lista `fail` (2.7).

Selectores y datos (found):

- `input_selector` por defecto `"$"`; la cadena `"null"` lo desactiva (`C58392QJx.A01`). `result_selector` y la combinación de parámetros pasan por `AbstractC58328QFo`. Se usa un motor de estilo JSONPath para `catch` (`Q2G`, expresiones como `$.[i].error_equals`) (found); que los selectores usen el mismo motor es inferred.
- Modos de `merge` en `QKb.A03`: `replace` (por defecto), `merge`, `incremental_merge`, `wae_commerce_merge` (found).
- `catch` = array JSON de `{error_equals:[names], next:<state>}`; un `error_equals` vacío coincide con todo (found, `Q6G.A00`). Los errores sin coincidencia terminan la máquina con el error (`A05`).
- Errores lanzados por el propio intérprete: `ResourceNotFound`, `FailToResume`, `unsupportedComparisonTypes`, `comparingValuesWithDifferentTypes`, `genericChoiceStateError`; error por defecto del manejador `NOT_CATCHABLE_ERROR` (`C5I7.A03`) (found).

### 2.4 Operadores de choice (found, `RsJ.A00`)

28 clases. El manifiesto lista 21; siete nombres heredados solo están en el código.

| Grupo | Nombres |
|-------|---------|
| Boolean | `and`, `or`, `not`, `booleanEquals` |
| Equality | `eq`, `neq`, `eq_any`, `neq_any`, `eq_path`, `neq_path`, `eq_any_path`, `neq_any_path`, `stringEquals` |
| Ordering | `gt`, `gte`, `lt`, `lte`, `gt_path`, `gte_path`, `lt_path`, `lte_path`, `numericalEquals`, `numericalGreaterThan`, `numericalGreaterThanEqual`, `numericalLessThan`, `numericalLessThanEqual` |
| Other | `isPresent`, `regex_match` (`variable` + `regex_match`) |

Cada operador se selecciona por la presencia de su clave en el JSON del choice (`AbstractC56245PPq.A00`); una `JSONException` salta al siguiente operador. Las variantes `_path` comparan con un valor resuelto desde una ruta (inferred a partir del nombre); la resolución exacta no se leyó.

### 2.5 Registro de recursos (found)

Registrados mediante `InterfaceC148426Oz.CP3()`; los ids los mantienen proveedores `C05T.A00(n)`. Los registros `C53207NpW`..`C53211Npa` devuelven un conjunto solo cuando `L8E.A1T()` es true (`C18780mK.A03()` es igual a `C21610rj.A0E`); qué significa ese predicado es unknown.

| Id de recurso | Manejador | En `phoenix-features.json` | Comportamiento |
|---------------|-----------|----------------------------|----------------|
| `open_bloks_screen_graphql` | `C954246c` | sí | Abre una pantalla Bloks; el parámetro `app_id` es obligatorio (si no, falla el cast) |
| `open_bloks_screen` | `C954346d` | no | Igual, `fetch_channel` = `GRAPHQL` (usa `bloks_server_params`) o `STATIC` (usa `fetch_channel_params.static_url`, establece `should_load_bloks_through_cdn: true`); otros valores lanzan excepción |
| `send_fds_iq` | anon en `AbstractC79003We` | sí | Params `config`, `type` (`GET`/`SET`), `state`, `parameters`; necesita un gestor FDS vivo por job id; si falta el gestor o la config se registra un error y falla con `NOT_CATCHABLE_ERROR` |
| `abprop_fetch` | anon en `AbstractC79003We` | no | Params `code` (int), `abprop_type` (`string`/`json`/`boolean`/`float`/`integer`), `default_value`; devuelve `abprop_value` leído del almacén AB; no se vio lista de permitidos para `code` |
| `client_dasl_query` | `C954746h` | sí | Necesita el parámetro `query`, si no registra `No parameters` y falla; la consulta se ejecuta en un executor en segundo plano |
| `dismiss_bottom_sheet` | `C955346n` | sí | Cierra la hoja actual |
| `native_flow_call_manager` | `C954946j` | sí | Necesita `phone_number`; lo reduce a dígitos y `+`; inicia `ACTION_DIAL` (`tel:`) con `FLAG_ACTIVITY_NEW_TASK` (solo marcador, sin llamada automática) |
| `request_permission` | `C955046k` | no | Solicitud de permiso de Android (vínculo con `FcsRequestPermissionActivity` inferred) |
| `throw_error` | `C954446e` | no | Lanza el mapa `error`; busca el mensaje por `error_map_type` + `code` |
| `payment_encrypt_with_public_key` | `C31703Dr4` | sí | Params `data_value`, `data_type`, `key_scope`, `provider_name`, `network` (gated) |
| `br_verify_card_deeplink` | `C955446o` | sí | Envía un broadcast restringido a un paquete `com.whatsapp.payments.phoenix.action.launch_activity_for_phoenix_result` con `app_to_app_partner_app_package`, `app_to_app_partner_intent_action`, `app_to_app_request_payload` (gated) |
| `br_verify_card_check_if_app_exists` | `C31702Dr3` | no | Gated |
| `native_br_compliance`, `native_br_p2m_checkout_address`, `native_card_encryption_resource` | `C955146l`, `C955246m`, anon | no | Pagos de Brasil, gated excepto el de tarjeta |

Nombres solo del manifiesto (sin entrada de registro en este build): `error_response`, `native_flow_npci_common_library` (subárbol `mode.collect`), `native_p2m_lite_compliance`, `native_p2m_lite_hpp_checkout`, `open_bloks_screen_static`. `open_bloks_screen_static` no tiene manejador; la ruta STATIC vive dentro de `open_bloks_screen` como `fetch_channel`.

### 2.6 Puntos de lanzamiento (found)

`new C57778Pva(config, params, startState)` se construye en: `address_message` (`C31337Djk`, NFM), `biz_survey` (`C57417PpS`), `br_merchant_onboarding` (`C33140EcF`), `br_p2m_checkout_add_card`, `br_p2p_verify_card` (`C32703EOj`), y una entrada por deep link que pasa una config con nombre del servidor con estado inicial `DeepLink` (`RunnableC46615KYo` caso 18, referral `deeplink`). Existen las cadenas `add_card_phoenix`, `verify_card_phoenix`; su papel como nombres de config es inferred. El programa de la config viene del servidor; no se distribuye ninguno salvo el manifiesto de capacidades.

### 2.7 Manifiesto de capacidades

`assets/versioning/phoenix-features.json` (1,218 B, idéntico a la copia de 2.26.34.4): `pass` de nivel superior, `choice` (21 operadores), `resource` (12 ids más `input_selector`, `parameters`, `result_selector`, `result_path`), `succeed`, `fail`. Su uso en runtime no se localizó (no se encontró referencia de cadena); tratar como lista de nombres. El código es la autoridad (2.4, 2.5).

---

## 3. Bloks

### 3.1 Superficies host (found)

| Host | Rol |
|------|-----|
| `WaBloksActivity`, `WaBloksBottomSheetActivity`, `BloksCDSBottomSheetActivity`, `BloksCDSPreloadCDSBottomSheetActivity` | Pantalla completa, bottom sheet, hojas CDS (sistema de diseño) |
| `WaSqBloksActivity`, `WaBloksScreenQueryFragment` | Hosts de screen-query (tipos `screen_query` vs `legacy_screen`) |
| `WaFcsModalActivity`, `WaFcsBottomSheetModalActivity`, `WaFcsPreloadedBloksActivity`; `SurveyCanonicalBloksActivity` (+ sheet) | Pantallas alojadas por Phoenix; encuestas |
| Hosts de producto | `CommonBloksActivity`, `SupportBloksActivity`, `BrazilPayBloksActivity`, `ConsumerSubscriptionBloksActivity`, `DigitalCommerceDcpBloksActivity`, `CsatSurveyBloksActivity`, `AppointmentBloksHostActivity` (exported false), `WaBackupStorageBloksActivity` (exported false) |

Ninguna actividad de Bloks, Flows o Phoenix declara un intent filter; `targetSdkVersion` es 36, por lo que las actividades sin `android:exported` no se exportan (found, manifiesto). Bloks también puede incrustar un componente `WebView` (`AndroidBridge.updateSize`, acción `bk.action.WebViewWithOnChange`) (found).

### 3.2 Obtención: GraphQL por HTTPS (found, `AbstractC40195HfH`, `C45J`)

| Elemento | Valor |
|----------|-------|
| URL | `https://graph.<domain>/graphql<path>`; `<domain>` = pref `pref_graphql_domain`, por defecto `whatsapp.com`; varias clases de petición fuerzan `facebook.com`; `<path>` vacío, o `/extensions` para la variante de Flows |
| Query string | `?_emp=1` añadido cuando la AB prop **549** está activa (por defecto false) |
| Cuerpo | JSON `{"variables": "<json string>", "access_token": ..., "doc_id": <long>, "lang": ..., "Content-Type": "application/json"}` |
| Token | token por petición si está definido, si no una cadena de token estática con ámbito de app embebida en el cliente (valor no reproducido) |
| Cabeceras | `X-FB-Friendly-Name: WABloksAppRootQuery-<app_id>`, `X-FB-Request-Analytics-Tags` |
| `variables` | `app_id`, clave de versión, `params` (cadena JSON), `bloks_theme_params` |
| Nombre de la clave de versión | `version`, `versioning_id` o `bloks_version` según la clase de petición; el valor es la misma constante de 64 hex que en Phoenix |
| Variante pre-consentimiento (`C136975rF`) | añade `app_version`, `locale`, `df_token`, `enc_token`, `disclosure_id`, `is_paused`, `country_code`, `encrypted_rid` |
| Variante extensions (`C132735kG` caso 2) | `extension_id` (= `flow_id` para flow message versions 2, 3, 4), `business_jid`, `screen_id`, `bloks_version` |
| Errores | `errors[].extensions.error_code` (por defecto 417), `is_retryable`; `error.code` 3489039 dispara una comprobación de integridad y reintento, 1675012 da `Bad Request` (ruta pre-consentimiento) |

Campos raíz de la respuesta (`AnonymousClass451.A05`): el payload es `data.<root>.payload` (una cadena JSON).

| Doc id | Campo raíz | Usado por (found) |
|--------|------------|-------------------|
| 3651100555017197 | `whatsapp_bloks_getlayout` | ruta por defecto; minishops link/pdp/storefront |
| 3958953970834604 | `whatsapp_bloks_getprivatelayout` | por defecto para `C5LX.A00()`; aviso de privacidad de minishops, vista previa de productos |
| 9404809712971896 | `whatsapp_bloks_getlayout` | familias enrutadas por regex (3.3) |
| 9943385105682204 | `whatsapp_bloks_getprivatelayout` | `logged_out.cxthelp.whatsapp` |
| 6019334944816363 | Layout de Flows (la raíz `whatsapp_galaxy_bloks_getflowlayout` existe en `AnonymousClass424`; vínculo entre ambos inferred) | `com.bloks.www.whatsapp.galaxy.flow.v2`, `...commerce.galaxy_message`, `...commerce.extensions_message_v2` |
| 36103976949247233 | `wamo_bloks_get_layout` | superficies WAMO |
| 9676557989071413 | no mapeado a un campo raíz | payments sample/care, `novi.care.*`, consentimiento `whatsapp.ai.biz.*` |

Los doc ids 26891716230495873 (pix playground) y 25865201793138751 aparecen en las tablas de enrutamiento sin campo raíz resuelto.

### 3.3 Enrutamiento por app-id (found)

Una pantalla se direcciona por `app_id` (un nombre con puntos, `com.bloks.www.*`). Las tablas de enrutamiento mapean un `app_id` a un descriptor de consulta `C5LX(doc id, request-factory variant)`: diez tablas de conjunto fijo (`InterfaceC148576Pp`: `C132235jS`..`C132335jc`) y tablas regex (`InterfaceC148726Qe`: `C132345jd`..`C132465jp`).

| Familia | Patrón o ejemplo | Doc id |
|---------|------------------|--------|
| Hub de pedidos / pagos | `orders_hub(\..+)*`, `fbpay_hub`, `payment.mft.wallet.fbpay_hub`, `(payment.)?mft.wallet.*`, `payment.(bloks.(commerce|ecp).checkout|fbpay.ecp).*` | 9404809712971896 |
| `gai` / `sna` / stickers de IA (significado de la familia inferred a partir de los nombres) | `bloks.nme.gai`, `wa.nme.gai`, `wa.sna`, `whatsapp.ai.stickers.*` | 9404809712971896 |
| Suscripciones | `dcp.subscriptions?(\..+)*` | 9404809712971896 |
| Soporte | `(csf|cxthelp)(\..+)+` | 9404809712971896 |
| Minishops | `minishops.link.app`, `.whatsapp.pdp`, `.storefront.wa` | 3651100555017197 |
| Consentimiento de IA de negocio | `whatsapp.ai.biz.{learn_more,consent,assistant_consent,third_party_consent,meta_ai_consent}` | 9676557989071413 |
| Playground / debug | `wa.playground.payments.br.pix.*` (variante 9) ; `whatsapp.payments.phoenix.{debug,demo_*,multi_*}`, `payments.whatsapp.f2care`, `novi.care.*` (variante 10) | 26891716230495873 ; 9676557989071413 |

87 ids literales distintos `com.bloks.www.*` están en el código; el resto llega del servidor y se enruta por las familias regex. Existen dos guardas de patrón en `AnonymousClass514`: los ids `consent(...)` pueden llevar `extra_params_json.whatsapp_bloks_networking_feature_override`; `payment.mft.security.*` con `ptt_use_case = WALLET` selecciona el helper de petición `wallet_canonical` (found).

### 3.4 Formato del payload (found)

Parser JSON en streaming `AbstractC122255Jb`; el objeto superior tiene `payload` (cadena) y `layout.bloks_payload`.

| Clave de `bloks_payload` | Significado |
|--------------------------|-------------|
| `tree` | Componente raíz (sección siguiente); `action` en lugar de `tree` para payloads solo de acción |
| `ft` | Tabla de funciones: id a cadena de expresión |
| `data`, `values`, `templates`, `props` | Registros de datos (`id`, `type`, `data`, `scoped`), expresiones de valor, plantillas, tabla de nombres de props |
| `embedded_payloads`, `hoisted_async_components` | Payloads anidados por id |
| `referenced`, `referenced_external`, `referenced_embedded_payloads`, `referenced_templates`, `referenced_ft_entries`, `referenced_values`, `referenced_ct`, `ct` | Listas de dependencias para payloads parciales/en streaming |
| `component_queries` | Component queries asíncronas (`id`, `app_id_expr`, `params`, `client_params`, `targets`, `cache_ttl_expr`, `disk_cache_enabled`, `is_scoped`) |
| `error_attribution` | `logging_id`, `source_map_id` |
| `depth`, `step_debugger_metadata.breakpoints` | Profundidad de streaming, depurador |

Codificación del árbol (`C5AN`): un nodo es un objeto cuya única clave es un code point; ese code point es el id del componente (`AbstractC105654gT.A00` = `codePointAt(0)`); las claves de atributo también son code points únicos (`!`=33 id, `#`=35 hijo, `&`=38, `+`=43 para el componente shadow 13347). El mapa de id de componente a nombre no está en los assets (unknown).

Ids de función ("Lispy", `C122545Ki`): un nodo de script es un array JSON cuyo primer elemento es la función: `"#<name>"` con nombre, un nombre con puntos resuelto mediante la tabla de nombres `AbstractC111054pC.A01`, o una cadena en base 36 parseada con `Integer.parseInt(s, 36)`. Las constantes tipadas tienen ids fijos: 17809 `bool.Const`, 18327 `f32.Const`, 18338 `f64.Const`, 19222 `i32.Const`, 19237 `i64.Const`. La tabla de nombres tiene 681 entradas, ids 17293 a 26071.

Decodificado a partir de las plantillas distribuidas (token base 36, id, nombre de tabla; found): `e2a` 18226 `core.If`; `e25` 18221 `core.GetArg`; `e2f` 18231 `core.TakeLast`; `e1w` 18212 `core.Apply`; `dng` 17692 `bloks.GetParameter`; `dnt` 17705 `bloks.GetVariable2`; `f4g` 19600 `map.Get`; `f6m` 19678 `mins.CallRuntime`; `igq` 23930 `core.AsNonnull`; `fjm` 20146 `screen.callback.DidFetchSucceed`; `foz` 20339 `ttrc.MarkerStart` (todos bajo `bk.action.`); `h9h` 22373 aparece con el nombre literal `null`.

La forma de texto `\t(...)` en `ft` y en las cadenas de expresión es una serialización distinta; que use los mismos ids base 36 se deduce de que las decodificaciones anteriores son coherentes (inferred). El parser de texto no se leyó.

Negociación de capacidades (inferred): el `bloks-versioning-id` de 64 hex se envía con cada petición; la tabla contiene 50 nombres de capacidad `bk.versioning.*` (por ejemplo `SupportsFunctionTables`, `TemplatePayloads`, `AsyncComponentBatchedWireProtocol`, `SupportsLispySignatureMinification`). Que el hash identifique este conjunto de capacidades es inferred.

Assets distribuidos (`assets/json/bloks_screen_template.json`, `bloks_bottomsheet_template.json`, `bloks_cds_base_screen_template.json`, 9,028 / 9,124 / 11,443 B, idénticos a 2.26.34.4): plantilla raíz con un `tree` de spinner, una entrada de `component_queries` cuyo target es `genScreenContent`, y un fallback de error en `embedded_payloads` (`Something went wrong` / `Please try again later` en dos de los tres). Son andamiajes; las pantallas de producto vienen del resultado de la consulta.

### 3.5 Espacios de nombres de acciones (found, `AbstractC111054pC`)

| Prefijo | Cantidad en la tabla de ids | Ejemplos |
|---------|-----------------------------|----------|
| `bk.action.core/bool/num/i32/i64/f32/string/array/map/math` | 113 | `core.If`, `core.Let`, `core.While`, `array.Map`, `string.*` |
| `bk.action.mins.*` | 36 | `CallRuntime`, `PutByVal`, `Raise` (VM minscript) |
| `bk.action.bloks.*` | 61 | `OpenScreen`, `OpenBottomSheet`, `Inflate`, `FetchAsyncComponents`, `WriteLocalState`, `ReplaceChildren`, `WriteGlobalConsistencyStore` |
| `bk.action.cds.*`, `bk.callbacks.cds.*` | 13 + | `OpenCdsBottomSheet`, `PushCdsBottomSheet`, `UnwindToScreen` |
| `bk.action.animated/animation/timer/collection/textinput/text_input/video` | 58 | Comportamiento de UI |
| `bk.action.qpl/ttrc/trace` | 14 / 11 / 2 | Marcadores de latencia (`ttrc.MarkerStart`) |
| `bk.action.privacy.consent.*` | 10 | `OpenFlow`, `LaunchConsent`, `ShutdownExperience` |
| `bk.action.waffle.*`, `bk.fx.*`, `bk.waffle.*` | 37 / 11 / 2 | Vinculación con Accounts Center: `EncryptPassword`, `DeleteLocalUserCredentials`, `GetProfilePictureUrl`, `UnpauseWithNativeAuthBlob`, `PregenerateAndCacheRSAKeyPairs` |
| `bk.action.mft.*`, `bk.action.frontier.*`, `bk.action.apt.PleEncrypt`, `bk.action.commerce.GetPaymentToken`, `bk.action.payments.GetCreditCardMetaData` | 5 / 5 / 1 / 1 / 1 | Pagos: `ModularGeneratePTT`, `LaunchGooglePaySheet`, `IsLuhnCompliant` |
| `bk.action.navigation.OpenUrl`, `bk.fx.action.OpenURLInIAB`, `bk.action.acp.OpenUrlExternally`, `bk.action.OpenUniversalLink`, `bk.action.DeeplinkToOtherAppOrDirectToAppStore`, `bk.action.bloks.IsAppInstalled` | 6 | Navegación fuera de Bloks |
| `bk.action.io.clipboard.SetString`, `bk.action.RequestPermission`, `bk.action.media.LoadAlbums`, `bk.fx.action.media.OpenMediaPicker`, `bk.action.foa.media.OpenCamera` | 5 | Acceso a dispositivo |
| `wa.action.*` | 75 | Acciones host de WhatsApp (tabla siguiente) |
| `wa.callbacks.*` | 10 | `FormInputOnTextChange`, `CodeInputOnTextChange`, `DatePickerOnDateSet`, `CameraViewOnMediaCaptured`, `ListViewItemSelected` |
| `bk.versioning.*`, `wa.versioning.image.base64` | 50 / 1 | Nombres de capacidad |

`wa.action.*` destacadas (ids 22391 a 26071):

| Grupo | Nombres |
|-------|---------|
| Network | `IQRequest`, `AsyncRequest`, `UploadMedia`, `UploadProfilePicture` |
| Puente Phoenix | `phoenix.FdsIq`, `FdsIqV2`, `FcsReturnResult`, `FcsReturnResultV2`, `FcsReturnResumableData`, `statemachine.GoBack`, `GoBackV2` |
| Estado de la app | `GetAbPropValue`, `GetAppType`, `GetIntentParameter`, `LoadScreenParam`, `SaveScreenParam`, `IsDarkModeEnabled` |
| Navegación | `OpenUrl`, `RouteToNativeScreen`, `RouteToNativeBenefitDetail(V2)`, `navigation.OpenChat`, `OpenContactInfo`, `OpenNativeActionSheet`, `FinishActivity(WithResult)`, `PopScreen` |
| Mensajería / comercio | `commerce.SendNFMReplyMessage`, `commerce.ActionWithCallback`, `share.Text`, `bonsai.SubmitFeedback`, `care.OpenContactSupport`, `care.OpenReportThisPayment` |
| Telemetría | `SendFieldStat(V2)`, `StartFieldStatTimer`, `GetFieldStatEventId`, `perf.TrackPerformance`, `novi.EncryptLogEvent(V2)` |
| Deeplink | `RegDeeplinkListener`, `DeregDeeplinkListener` |

Guarda encontrada en la acción IQ de Bloks (`C129575f5.A0Y`, log `IQRequestHelper/sendIQRequest: Invalid XMLNS`): solo pasan los xmlns `w:pay` y `urn:xmpp:whatsapp:account` (`C33327EfH.A02`); cualquier otro llama al callback `on_failure`. Por tanto, los scripts de Bloks solo pueden enviar IQs en esos dos espacios de nombres (found). Las implementaciones de manejador de la mayoría de las demás ids `wa.action.*` no se trazaron (su código se alcanza por id numérico).

### 3.6 Component queries y caché (found)

- Un `component_query` obtiene un componente asíncrono por `app_id` a través de la misma ruta GraphQL (gestor `C5L9`, etiqueta de log `BloksComponentQueryManager`); `app_id_expr`, `params`, `client_params` y `cache_ttl_expr` son expresiones Lispy evaluadas en el cliente.
- Dos niveles de caché: una caché en memoria (`cache_src: memory`, `cache_age`) y una caché en disco con clave por consulta (`BloksComponentQueryDiskCache`; clases `C5NA`, `C5NN`, `C136885r6`). Los registros en disco están serializados con Java (`ComponentQueryDiskCacheRecord`: `DiskCacheData{initialResponse, extensions}`, `responseTimestampMs`, `BloksComponentQueryResources`); los metadatos viven bajo `__disk_metadata`; un `Bloks_ACQ_ReadWriteThread` hace la E/S. `disk_cache_enabled` es un interruptor por consulta.
- Las acciones `bk.action.AsyncComponentCacheWrite`, `bloks.ClearCachedAsyncComponents`, `bloks.InvalidateCachedAsyncComponents` permiten a un payload gestionar la caché.
- Directorio, límite de tamaño y expulsión de la caché en disco: unknown. La deserialización Java de registros de caché influidos por el servidor ocurre solo desde la propia caché de la app (inferred a partir de la ruta de código).

---

## 4. Native flow messages y WhatsApp Flows

### 4.1 Registro de botones NFM (found, `AbstractC30032D4u` caso 442, clase `EYT`)

Un mensaje interactivo lleva botones con `nativeFlowInfo.name` y un JSON de params. Despacho: `C33370Efz.A05` busca el nombre en un mapa (`C0VA`) de unas 40 subclases de `AbstractC33168Ech`; los nombres desconocidos registran `can not recognize NFM action` y se descartan; una acción puede desactivarse por gate (contadores `wa:nfm_dispatch_gate_blocked` / `_observed`).

| Conjunto | Nombres |
|----------|---------|
| Nombres de botón soportados (39) | `cta_catalog`, `review_and_pay`, `review_and_pay_v2`, `cta_call`, `cta_url`, `cta_copy`, `cta_pix_code_copy`, `offer_payment_account`, `form_message`, `open_webview`, `catalog_message`, `voice_call`, `video_call`, `landline_call`, `quick_reply`, `single_select`, `view_product`, `call_permission_request`, `cta_app_link`, `appointment`, `automated_greeting_message_view_catalog`, `send_location`, `order_status`, `booking_confirmation`, `booking_status`, `psi_nux_opt_in`, `psi_tos_opt_in`, `psi_opt_outs`, `account_authentication_request`, `request_contact_info`, `agent_api_key`, `otp`, `payment_reminder`, `cta_reminder`, `payment_request`, `api_signup`, `inapp_signup`, `split_payment`, `send_payment` |
| Segundo conjunto | `address_message`, `galaxy_message` (lanzan flows; rol inferred por el uso) |
| Lista de permitidos mixta/quick-reply | `C33370Efz.A08`: `cta_url`, `cta_call`, `voice_call`, `video_call`, `cta_copy`, `menu_options`, `cta_reminder`, `view_product`, `cta_app_link`, `galaxy_message`, `otp`, `booking_*`, ... |

- `address_message` inicia la config Phoenix `address_message` (`C31337Djk`, found).
- `galaxy_message` abre WhatsApp Flows (4.2).
- Las respuestas de flow se almacenan en `message_ui_elements_reply` (`flow_id`, `element_type` 8) y `interactive_message_bloks_widget` (found, SQL).

### 4.2 Params y lanzamiento de `galaxy_message` (found, `C31338Djl`, `C31337Djk`)

| Clave en el JSON de params | Uso |
|----------------------------|-----|
| `flow_id` | debe coincidir con `\d+` para la acción Flows v2 |
| `flow_token`, `flow_cta` | obligatorios con `flow_id` (ruta Flows v2) |
| `flow_message_version` | `2`, `3`, `4` seleccionan las variables de extensión de la consulta Bloks |
| `flow_action` (`navigate` por defecto, `data_exchange`), `flow_action_payload` (objeto) | primera pantalla / canal de datos |
| `mode` | `draft` marca un flow borrador (`is_draft`) |
| `form_type` | enruta a `FlexCheckoutNativeFormActivity` (flexible checkout) |
| `flow_token_signature`, `www_proxy_secret` | reenviados a la página solo cuando la AB prop **14825** está activa |

El JID de negocio remitente viene del chat (`FlowsV2Action`); sin él el lanzamiento se aborta (`cannot launch flow without business jid`). Existen dos renderizadores: la aplicación web (4.3) y una ruta Bloks (`com.bloks.www.whatsapp.galaxy.flow.v2`, sección 3.2). Cuál toma un mensaje dado no está resuelto; las AB props **22787** (actividad separada vs bottom sheet) y **14222** se leen en la ruta web.

### 4.3 Aplicación web de Flows (found)

| Elemento | Valor |
|----------|-------|
| URLs base (AB string props) | **7153** `https://flows.whatsapp.net/flows` (precarga, `C35814Ff9`), **6060** mismo valor por defecto (obtención del JSON del flow `EP6`: base + `/json/` + flow id, inferred por el orden del constructor), **7125** `.../flows/cache_management/` (limpiador de caché `C39066GzF`, intervalo **7126** = 1382400), **16723** `.../flows-app/catalog` (catálogo) |
| Host | `SecureWebView` (`com.facebook.secure.securewebview`): acceso a archivos y contenido desactivado; la carga se permite solo si el esquema es `https` Y el host es igual al host de la URL de lanzamiento o un subdominio de él (`GAP.A00`, `H26`, combinados con AND en `GAL`); si no, log `Uri is blocked` |
| URL de lanzamiento | del bundle (`url`, por defecto `about:blank`); la base es una AB prop, por lo que el servidor puede moverla; la política de host sigue a la URL de lanzamiento (consecuencia inferred) |
| Precarga | `FlowsWebPreloader` carga AB **7153** en un WebView oculto (`setCacheMode(2)`); versión de caché del service worker rastreada mediante `flows_service_workers_cache_version` |
| Inyección en la página | etiqueta `meta` con viewport, `layoutDirection`, `locale`, `timeZone`, `supportedStyles` |
| Puente | `window.WhatsAppBridge.invoke(method, data, cb)`; el nativo crea un `MessageChannel` y envía `init-port` con el puerto 1 (`HQD`); los mensajes son JSON `{method, data, callbackID}`; respuestas `{callbackID, responseData}` |
| Vinculación de origen | El script del puente se inyecta con `evaluateJavascript` en lo que muestre el WebView; el puerto se envía al destino `Uri.EMPTY`; el filtrado depende de la política de URL de SecureWebView (inferred) |
| JSON del flow | `flow_json` obtenido por `EP6.A01` (HTTP GET, almacenado en disco como cadena serializada, clave `<id>_<id2>`), solo cuando AB **8552** está activa; `FlowsWebViewDataRepository` construye el bundle (`flow_json`, `flow_action_payload`, `creation_source`, ids de sesión) |
| Clave pública | `WAExtensionsGetPublicKey` devuelve la clave pública del endpoint obtenida mediante una llamada GraphQL de metadatos (errores `extensions-metadata-graphql-*`, modo `required` u `optional`); el uso para cifrar datos se hace del lado de la página (inferred) |

Métodos del puente manejados de forma nativa (30; `C41342Hyk`, `FlowsWebBottomSheetContainer.CKc`):

| Grupo | Métodos |
|-------|---------|
| Sesión | `WAExtensionsGetFlowData`, `WAExtensionsDataChannelExchange`, `WAExtensionsNavigate`, `WAExtensionsComplete`, `WAExtensionsClose`, `WAExtensionsGetPublicKey`, `WAExtensionsGetClientAbProps` |
| UI | `WAFlowsShowNativeInputDialogComponent`, `WAExtensionsConfigureNavBar`, `WAFlowsMediaSelect`, `WAFlowsMediaRetry`, `WAFlowsMediaDelete`, `WAFlowsCopyText`, `WAFlowsOpenURL`, `WAExtensionsLearnMore`, `WAExtensionsContextualHelp` |
| Negocio | `WAExtensionsSpamReport`, `WAExtensionsReportItem`, `WAFlowsDownloadResponse`, `WAFlowsMarketingDisclosureState`, `WAFlowsMarketingDisclosureUserAction` |
| Carrito | `WAFlowsStoreShoppingFlowContext`, `WAFlowsGetCart`, `WAFlowsSetCartItem`, `WAFlowsClearCart` |
| Telemetría | `WAMLogger`, `WAQPLLogger.start`, `.end`, `.annotate`, `.point` |

Notas de manejo: `WAFlowsOpenURL` inicia `ACTION_VIEW` solo para URLs `https`, si no muestra un snackbar; `WAExtensionsGetClientAbProps` devuelve cualquier AB prop por código y tipo (`bool`, `int`, `float`, `string`, `json`) sin lista de permitidos visible (`C37367GJs`); los métodos desconocidos van a un manejador por defecto (`GJW`); una entrada que no se puede parsear produce `extensions-bridge-api-input-parse-error`.

### 4.4 Finalización del flow

`WAExtensionsComplete` termina la sesión y el cliente envía un mensaje de respuesta native-flow (columnas `native_flow_response_*`; los params llevan `wa_flow_response_params`, `flow_creation_source`, `response_message`) (found por los nombres; ruta de envío no trazada).

### 4.5 Consulta del endpoint de Flows

La clase de resultado `AnonymousClass456` lee la raíz `whatsapp_galaxy_forward_flow_data_response` o `xwa_flows_make_flow_endpoint_request` y un `status_code`: 200 ok, 421 y 504 mapeados a resultados distintos, otros fallo genérico (found). Si esto corre sobre MEX o sobre la pila GraphQL por HTTPS es unknown (la base del parser se comparte con Bloks).

---

## 5. Superficies que no son UI descrita por el servidor

### 5.1 Respuesta enriquecida de IA (portada por el mensaje, componentes fijos)

Protobuf `richResponseMessage` (ver `WA_META_AI.md` sección 6.3). Enum de tipo de submensaje `EnumC32139E2l` (found): `AI_RICH_RESPONSE_UNKNOWN` 0, `GRID_IMAGE` 1, `TEXT` 2, `INLINE_IMAGE` 3, `TABLE` 4, `CODE` 5, `DYNAMIC` 6, `MAP` 7, `LATEX` 8, `CONTENT_ITEMS` 9; clases de resaltado de código (`KEYWORD`, `STRING`, `NUMBER`, `METHOD`, `COMMENT`, `DEFAULT`); metadatos dinámicos `IMAGE`, `GIF`. El cliente renderiza un conjunto fijo; las acciones son descarga / reenvío de archivo (`UnifiedResponseActionHandlerFactory`). Sin lenguaje de script, sin DSL de acciones.

### 5.2 Tarjeta FMX

La tarjeta FMX (`LE7`, fábrica de view-model `fmxViewModelFactory`, etiqueta de avatar `fmx-card-v2`) la crea el cliente como mensaje de sistema (`C198788cr`: `Creating FMX card system message for chat`); contadores como `fmxBizEnterpriseSenders`, `fmxMissingLidMapping`, `fmxSuspiciousBottomSheetCacheMiss` muestran que se controla por señales locales. Si el servidor aporta algún texto de la tarjeta es unknown. Tratar como UI nativa.

### 5.3 Scripts del navegador integrado (iabjs)

`res/raw/iabjs_*` tiene 15 scripts en 2.26.41.6 (cuatro más que el conjunto de 2.26.34.4): `autofill_execute_callback`, `autofill_language_detect`, `autofill_payment_detection`, `otp_autofill` son nuevos. Host `WaInAppBrowsingActivity` (exported false).

| Elemento | Valor (found) |
|----------|---------------|
| Objeto puente | `iabjs_unified_bridge`: `addWebMessageListener(name, allowedOrigins, listener, jsWorld)` en el mundo JS aislado `iab_js` cuando está soportado (`HJY.A05`); fallback `addJavascriptInterface("iabjs_unified_bridge")` (`RunnableC40709HoJ`) |
| Lado de la página | `window.__call_iabjs_unified_bridge(method, nonce, payload)` envía `{method, payload, nonce}`; el nonce se sustituye en `window.__iabjs_unified_bridge_nonce="%s"` en la inyección |
| Comprobación nativa | `C39590HNn`: el `nonce` del JSON debe ser igual al nonce almacenado del manejador (generado una vez por manejador mediante `AbstractC48382LBd.A00().toString()`, tipo UUID, inferred); una discrepancia registra `invalid_nonce` y descarta la llamada; el método `iabjs_register_proxy` registra el mundo; otros métodos van a listeners indexados por (world, method) |
| Novedad en este build | `iabjs_autofill_payment_detection` clasifica campos en `cc-number`, `cc-exp`, `cc-exp-month`, `cc-exp-year`, `cc-csc`, `cc-name` por `autocomplete` o regex sobre name/id/placeholder; `iabjs_otp_autofill` rellena `input[autocomplete="one-time-code"]`; `iabjs_autofill_language_detect` envía `languageDetermined` |
| Conjunto de orígenes permitidos | `Set` proporcionado por el llamador; contenido no trazado (unknown) |
| Fallback heredado | `addJavascriptInterface` no tiene filtro por origen (comportamiento de la plataforma, inferred) |

Ocho de los 11 scripts anteriores son idénticos byte a byte a las copias de 2.26.34.4; `detect_login_forms`, `navigation_performance_logger_android`, `iabjs_bridge_init` cambiaron (453 B vs 433 B para el init del puente).

---

## 6. Sandboxing y resumen de seguridad

| Control | Dónde | Tier |
|---------|-------|------|
| Ids de recurso Phoenix fijos en el código; un id desconocido da `ResourceNotFound` | `QKb.A03` | found |
| Operadores Phoenix fijos (28); operador sin coincidencia omitido | `RsJ`, `AbstractC56245PPq` | found |
| Acción IQ de Bloks limitada a los xmlns `w:pay`, `urn:xmpp:whatsapp:account` | `C33327EfH.A02` | found |
| Ids de función Bloks fijos (681 con nombre) | `AbstractC111054pC`, `C122545Ki` | found |
| Nombres NFM fijos (39 + 2); los desconocidos se descartan | `AbstractC30032D4u`, `C33370Efz` | found |
| Host de Flows: solo https + host de lanzamiento (o subdominio), sin acceso a archivos/contenido | `SecureWebView`, `GAP`, `H26` | found |
| Puente de Flows: lista fija de métodos; `WAFlowsOpenURL` solo https | `FlowsWebBottomSheetContainer` | found |
| iabjs: comprobación de nonce, mundo aislado, conjunto de orígenes | `C39590HNn`, `HJY` | found |
| Broadcast Phoenix `br_verify_card_deeplink` restringido al propio paquete | `C955446o` | found |
| Todas las actividades Bloks, Flows, Phoenix carecen de intent filters; targetSdk 36 | manifiesto | found |
| Verificación de firma o hash del contenido Bloks/Phoenix | ninguna localizada; `BloksTrustedPayload` sin referencias | found (ausencia en las rutas buscadas) |
| El servidor puede leer AB props por código (`abprop_fetch`, `WAExtensionsGetClientAbProps`) | sin lista de permitidos visible | found |
| Confianza del transporte (TLS pinning, manejo de tokens para peticiones graph) | no analizado | unknown |

Consecuencia (inferred): la confianza descansa en el transporte y en los registros anteriores; un programa del lado del servidor comprometido o malicioso está limitado a esos registros, pero los registros incluyen helpers de cifrado de pagos, manejo de credenciales para Accounts Center, `ACTION_DIAL`, apertura de URLs y lecturas de AB.

---

## 7. Caché y precarga

Component queries de Bloks: memoria + disco, TTL por `cache_ttl_expr` (3.6). Phoenix: los `next_screens` listados por el servidor se precargan en `WaFcsPreloadedBloksActivity`; las entradas `persist_data` van a listeners por clave (found). Flows web: WebView de precarga, versión de caché del service worker, limpiador programado (AB 7125/7126), caché en disco del JSON del flow, marcador de bloqueo de metadatos `extensions_metadata_banned_<id>_<id>` en prefs (found).

---

## 8. Feature flags (valores por defecto de `C08J`; significados a partir del sitio de lectura)

| ID | Tipo | Por defecto | Leído en | Efecto |
|----|------|-------------|----------|--------|
| **549** | bool | false | `AbstractC40195HfH.A03` | Añade `?_emp=1` a la URL GraphQL (salvo `C0GD.A02()`) |
| **7153** | string | `https://flows.whatsapp.net/flows` | `C35814Ff9` | URL de precarga de Flows |
| **6060** | string | igual | `EP6`, `C33350Efe` | Base de Flows para `/json/<id>` |
| **7125** | string | `.../flows/cache_management/` | `C39066GzF` | URL del limpiador de caché de Flows |
| **7126** | int | 1382400 | `C39066GzF` | Intervalo/activación del limpiador (unidad unknown; > 0 activa) |
| **8552** | bool | false | `FlowsWebViewDataRepository.A07` | Obtener el JSON del flow de forma nativa y pasarlo a la página |
| **14825** | bool | false | `FlowsWebViewDataRepository.A06` | Pasar `www_proxy_secret` y `flow_token_signature` |
| **22787** | bool | false | `C31338Djl` | Flows en una actividad separada vs bottom sheet |
| **24781** | bool | false | `FlowsWebBottomSheetContainer` | Sin ella, una hoja restaurada se cierra sola |
| **14222** | bool | false | `C31338Djl` | Gate en la ruta de lanzamiento de Flows (efecto exacto unknown) |
| **5333**, **1319** | bool | false / false | variante Flows de `C45J` | Ambas activas: los errores de layout de Flows se reportan como `extensions-layout-unexpected-error` |

Los ids de flag usan el espacio numérico de `WA_AB_PROPS.md`.

---

## 9. Baileys (`baron-baileys-v2`)

Un cliente Baileys no tiene renderizador, por lo que Bloks y Flows web quedan fuera de alcance. Lo que puede tocar es la parte portada por el mensaje y, en principio, el IQ.

| Objetivo | Qué funciona | Por qué puede fallar | Fix |
|----------|--------------|----------------------|-----|
| Enviar un botón de Flow | `interactiveMessage.nativeFlowMessage.buttons[]` con `name: 'galaxy_message'` y `buttonParamsJson` con las claves de 4.2 (`flow_message_version`, `flow_id`, `flow_token`, `flow_cta`, `flow_action`, `flow_action_payload`) | El receptor necesita contexto de JID de negocio, `flow_id` numérico, `flow_token`, `flow_cta`; es improbable que se respeten remitentes usuarios (no negocio) (inferred) | Enviar desde una cuenta registrada como negocio; mantener `flow_id` numérico |
| Usar un nombre de botón desconocido | ninguno | `C33370Efz` descarta nombres fuera de los 39 + 2 | Usar un nombre de 4.1 |
| Obtener un programa Phoenix | `<iq xmlns="phoenix" type="get"><fds config=... /></iq>` | El servidor decide según el estado de cuenta/app; contenido de la respuesta nunca capturado | No intentado; tratar como unknown |
| Leer una pantalla Bloks | no aplicable | Necesita el token graph, el doc id y `bloks-versioning-id`; sin ruta en Baileys | Fuera de alcance |

---

## 10. Casos de error

| Síntoma | Causa | Fix |
|---------|-------|-----|
| `ResourceNotFound` y el flow termina | el estado `resource` nombra un id que no está en el registro (o un id gated de Brasil en un build que no coincide) | Usar ids de 2.5 |
| `state not found for name: <x>` | `next` apunta a un estado inexistente, o a un estado `version_check` (descartado por `C58392QJx.A01`) | Declarar el destino como un tipo soportado |
| `unsupportedComparisonTypes` / `comparingValuesWithDifferentTypes` | Operador aplicado a tipos incorrectos | Hacer coincidir los tipos; usar `catch`; `NOT_CATCHABLE_ERROR` no se puede capturar |
| `FdsIqResource/execute: can't find FdsManager from the job_id` | `send_fds_iq` fuera de una sesión viva | Ejecutar dentro de la sesión que lo inició |
| Bloks `Invalid XMLNS` | `wa.action.IQRequest` con un xmlns fuera de la lista de permitidos | Solo `w:pay`, `urn:xmpp:whatsapp:account` |
| `FcsScreenOpenerBloksDelegate: app_id is not present` | `open_bloks_screen*` sin `app_id` | Pasar `app_id` |
| `error.code` 3489039 | Se exige comprobación de integridad (obtención pre-consentimiento) | El cliente reintenta tras la comprobación |
| Página de Flows en blanco, log `Uri is blocked` | La navegación salió del host de lanzamiento o usó un esquema no https | Mantener el contenido en el host de lanzamiento |
| `extensions-bridge-api-input-parse-error` | El mensaje del puente no es JSON válido con la forma esperada | Enviar `{method, data, callbackID}` |
| iabjs `invalid_nonce` | Nonce incorrecto o ausente | Usar el `__iabjs_unified_bridge_nonce` inyectado |

---

## 11. Distinciones clave

| No confundir | Diferencia |
|--------------|------------|
| Phoenix vs Bloks | Phoenix = flujo de control sobre IQ; Bloks = pantallas sobre GraphQL; se encuentran en `open_bloks_screen*` y `wa.action.phoenix.*` |
| FCS vs FDS | Aparecen ambos: `flowconfigurationservice` (paquete, `FcsStateMachine`) y `FDS` (gestor de IQ, `<fds>`, log `FDSManage`); la expansión de "FDS" no está en el código |
| Manifiesto vs código | `phoenix-features.json` lista 12 ids de recurso y 21 operadores; el código tiene 15 ids de recurso y 28 operadores; gana el código |
| `open_bloks_screen_static` vs `open_bloks_screen` + `fetch_channel=STATIC` | Solo el segundo tiene manejador |
| Claves del árbol Bloks vs opcodes | Las claves del árbol son code points de componente; las cabezas de script son ids de función (base 36) |
| Flows web vs Flows Bloks | Dos renderizadores para `galaxy_message`: WebView (`flows.whatsapp.net`) y `com.bloks.www.whatsapp.galaxy.flow.v2` |
| Bloks GraphQL vs MEX | Bloks hace POST a `graph.<domain>/graphql` con `doc_id`; MEX es la capa de consultas transportada por XMPP usada en otros lugares |
| Nonce de iabjs vs puente de Flows | iabjs usa un nonce por manejador en el envelope; el puente de Flows no tiene nonce, depende del handshake del puerto y de la política de URL |
| Respuesta enriquecida vs Bloks | La respuesta enriquecida es un conjunto protobuf fijo; Bloks es un árbol programable |

---

## 12. Flujo completo

```
[Server]                                          [WhatsApp client]
   │  message: interactive nativeFlowInfo name        │
   ├─────────────────────────────────────────────────►│ C33370Efz: name in registry? gated?
   │        address_message              galaxy_message│
   │             ▼                              ▼      │
   │  Phoenix start C58392QJx.A08       Flows launch C31338Djl: SecureWebView (https, launch host)
   │  IQ <iq xmlns="phoenix"><fds config>      + MessageChannel init-port, or Bloks galaxy.flow.v2
   │◄────────────────────────────────────────────────┤
   │  <fds><states start_at><state type=..>           │
   ├─────────────────────────────────────────────────►│ QKb.A03 loop: resource | choice(28 ops) | pass | subflow | succeed
   │                                                  │ resource -> registry: open_bloks_screen_graphql, send_fds_iq, abprop_fetch, ...
   │  POST graph.<domain>/graphql {doc_id, variables{app_id, versioning id, params}}  (route by app_id: C5LX)
   │◄────────────────────────────────────────────────┤
   │  layout.bloks_payload {tree, ft, component_queries, ...}
   ├─────────────────────────────────────────────────►│ AbstractC122255Jb: tree (code-point keys) + Lispy (base-36 ids)
   │                                                  │ user action -> bk.* / wa.* function id
   │◄── IQ (w:pay | urn:xmpp:whatsapp:account only) ──┤ wa.action.IQRequest
   │                                                  │ wa.action.phoenix.FdsIq / FcsReturnResult -> back into QKb (next / catch / end)
   │◄── WAExtensionsComplete -> native-flow response ─┤
```

---

## 13. Incógnitas

| Elemento | Estado |
|----------|--------|
| Expansión de "FDS"; significado del gate `L8E.A1T()` | unknown |
| Mapa de code point de componente a nombre; nombres Lispy más allá de los 681 listados; parser de la forma de texto | unknown |
| Código de manejador de la mayoría de ids `wa.action.*` / `bk.action.*` (alcanzados por id numérico) | unknown |
| Contenido real del servidor: no se capturó ningún programa Phoenix ni pantalla Bloks | unknown (solo estático) |
| Transporte de `xwa_flows_make_flow_endpoint_request`; renderizador que toma un `galaxy_message`; efecto de AB **14222** | unknown |
| Ubicación, tamaño y expulsión de la caché en disco; conjunto de orígenes permitidos de iabjs; integridad del lado del servidor más allá de TLS | unknown |
| Si existe un framework estilo Genie en otro build | unknown |
