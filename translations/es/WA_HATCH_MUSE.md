<!-- src-sha1: aacd3c372c813b12cfe335ddb7b3323c8eed3863 -->
# WhatsApp Agente de IA Hatch/Muse — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-11-15
**Alcance:** internals del agente de IA Hatch/Muse — transporte VM de Noise-gateway atestiguado, atestación nativa de carrier + SEV-SNP, control plane y onboarding WAFFLE, stream noVNC del agent-browser, workspace (spaces, feed, goals, ideas, artifacts, approvals, tareas programadas, conectores), almacén seguro de credenciales, identidad CVM/recuperación de PIN (`hatch/cvm`, Vesta OPAQUE), tier de suscripción pago, veredicto de alcanzabilidad, por qué Baileys/velowa no pueden implementarlo

---

## 1. Qué es Hatch/Muse

**Hatch** es el nombre en código interno del subsistema de agente de IA de WhatsApp; **Muse** es el nombre de cara al usuario del propio agente (`str29b7` "Muse manages emails, books tables, and more."). El agente no es solo una persona de chat (eso es Meta AI, cubierto en `WA_META_AI.md`): conduce una **VM confidencial remota ("CVM")** que puede navegar la web, correr tareas programadas, mantener su propio sistema de archivos, y llamar servicios de terceros en nombre del usuario. Todo en este informe es análisis estático `found`/`inferred` de 2.26.41.6 (`WA-APK-BETA/WhatsApp_2.26.41.6/`), con una sub-área corregida (§6, el sistema de identidad `hatch/cvm`) re-verificada contra smali de 2.26.45.10. **Nada en este informe es `tested`** — ninguna corrida de dispositivo/Frida respalda esto; los vacíos de confirmación dinámica se señalan en línea.

### 1.1 Entidades principales

| Entidad | Significado |
|--------|-----------|
| Hatch | Nombre en código interno para todo el subsistema de agente (VM, workspace, almacén de credenciales, capa de identidad/PIN) |
| Muse | Nombre/persona del agente de cara al usuario |
| CVM | "Cloud VM" / "VM confidencial" — el entorno de cómputo remoto del agente (AMD SEV-SNP) |
| `HatchVmEndpoint` (`C57830PwR`) | Struct de conexión VM resuelto: host, `auth_token`, expiración, token validado, mapa de parámetros `notary_token` |
| Noise gateway | Una sesión Noise separada y atestiguada a un "noise gateway" de Meta, transportada sobre Tigon, distinta de la sesión principal Noise_XX/chatd de WA |
| Agent spaces | Mini web apps que el agente construye y hospeda dentro de la CVM, reproxificadas a un WebView del teléfono |
| Connector | Un vínculo registrado entre el agente y un servicio de terceros (Gmail, calendario, Messenger, riel de pagos, endpoint personalizado) |
| `hatch/cvm` (Vesta) | El **sistema de identidad de dispositivo/VM y recuperación por atestación de chip** del agente, PAKE OPAQUE con compuerta de PIN — **no** es una bóveda de pagos (corrige una pasada de investigación anterior, ver §6) |
| Approval gate | Confirmación humana-en-el-loop antes de una acción riesgosa/irreversible del agente |

### 1.2 Relación con el chat de Meta AI

Se llega a Muse desde la misma superficie de chat que Meta AI, y comparte algo de plomería (anuncio de capacidad de bot-JID — ver §7) y el canal de metadata JSON de Hatch documentado en `WA_META_AI.md` §5 (`HF1`/`HatchMetadataRequestManager`, `ProtocolMessage.aiMetadataOperation`). Pero el sistema de agent-browser/VM/workspace que cubre este informe es un **subsistema separado, mucho más grande**: no viaja sobre la sesión chatd/Noise_XX en absoluto, tiene su propio transporte nativo, y persiste su propio estado (goals, feed, artifacts, approvals) del lado servidor en la CVM. Private Processing / el clúster TEE (Meta AI respondiendo preguntas sobre tus propios chats, Private Search) es un **tercer sistema, distinto** — ver §11 para la desambiguación completa.

---

## 2. Visión general de arquitectura

### 2.1 Mapa de paquetes

Todas las actividades Hatch/agente son `android:exported="false"` — sin punto de entrada entre apps; todo se lanza en proceso desde la superficie de chat/agente.

| Paquete | Rol |
|---------|------|
| `com.whatsapp.hatch.vm` (`p085vm`) | Control plane / ciclo de vida de VM: `HatchVmLifecycleCoordinator`, `HatchVmApiClient`, `HatchVmWaker`, `HatchVmLeaseGate`, `GraphQlHatchAbraTokenProvider`, `HatchAbraTokenRevoker` |
| `com.whatsapp.hatch.onboarding` | `HatchWaffleOnboarding`, `HatchPairingAuthBrowsingActivity`, `HatchMuseConnectionActivator` |
| `com.whatsapp.hatch.computer` / `.conversation.browser` / `.conversation.approval` | `HatchComputerActivity` (desktop completo de VM), `HatchBrowserStreamActivity` (navegador en vivo en el chat), `HatchBrowserPreviewActivity` (compuerta de aprobación) |
| `com.whatsapp.hatch.feed/goals/ideas/activity/approvalhistory` | UI del workspace: feed, goals + sub-goals, ideas, historial de aprobaciones |
| `com.whatsapp.hatch.artifacts/media` | Artifacts y archivos producidos por el agente |
| `com.whatsapp.hatch.connectors(.ui)` | Catálogo de conectores de terceros, flujos de conexión, acción de tarjeta virtual, modo de permiso por conector |
| `com.whatsapp.hatch.identity.ui` | Documentos "about me" del agente |
| `com.whatsapp.hatch.scheduledtasks.impl` | UI de tareas recurrentes de la VM del agente |
| `com.whatsapp.hatch.cvm` / `.cvm.pin` | **No es una bóveda** — recuperación de identidad de dispositivo/VM con compuerta de PIN (Vesta OPAQUE), §6 |
| `com.whatsapp.hatch.subscription(s).iap` | Flujo de compra del tier pago, §7 |
| `com.whatsapp.bot.agentspaces.*` | Host de "Spaces": `HatchSpaceActivity` + reverse-proxy `HatchSpaceTunnel`, adaptador `NoiseHatchVmTransport` |
| `com.whatsapp.bot.agentbrowser.*` | Motor de navegador + transporte VM: `BrowserSessionController` (WebView noVNC), `NoiseVmConnection`/`WaNoiseChannel`, `agentbrowser.noise.carrier.*` (JNI nativo) |
| `com.whatsapp.bot.securecredentials.*` | `SecureCredentialVault` — almacén de credenciales, del lado servidor en la CVM |
| `com.whatsapp.bot.agentactivity/agentfeed/agentgoals/agentapprovals` | Capa de datos/feed detrás de la UI `hatch.*` |
| `com.whatsapp.bot.infra.vmmedia` | Fetch crudo del sistema de archivos de la VM del agente (`/fs/raw/`, `/media/raw/`) |
| `com.whatsapp.bot.quiz` | `AiQuizViewerActivity` — visor de quiz richResponse, **no** es una función de VM (§2.3) |
| `com.crossapp.tigonhttp(.noise)` | **Tigon**, el stack HTTP nativo cross-app compartido de Meta + `NoiseChannelManagerHolder` |

### 2.2 Tres transportes distintos — no confundirlos

Este es el hecho estructural individual más importante, y una pasada de investigación anterior lo tuvo mal para uno de los tres (§6.1 lo corrige):

| # | Transporte | Lleva | Bloqueador para un cliente de terceros |
|---|-----------|---------|-----------------------------------|
| 1 | **Canal VM de Noise-gateway atestiguado** — `/v1/noise` sobre Tigon, `libwa-noise-gateway-carrier-jni.so` nativo | Todo lo interactivo con el agente: HTTP del browser-VM (`/api/*`, `/fs/*`, `/spaces/*`), stream de pantalla noVNC, funciones de workspace, CRUD de credenciales seguras | Carrier nativo Noise+WebSocket **y** onboarding de cliente-oficial WAFFLE — bloqueado de forma dura |
| 2 | **Control plane HTTPS plano** a `hatch-api.meta.ai` | Despertar VM, token bearer Abra, URL de pairing, **y** (corregido, §6) los endpoints de recuperación de identidad `hatch/vesta-auth/*` / `hatch/cvm-*` | El transporte es observable por MITM en principio (dispositivo rooteado, bypass de pinning); los endpoints de identidad además necesitan matemática nativa OPAQUE + post-cuántica (`libvesta_client_jni.so`) para producir cuerpos de solicitud válidos |
| 3 | **MEX/GraphQL plano** sobre el transporte ordinario `whatsapp-android-mex`/`whatsapp-android-www` de WhatsApp | Lecturas+eliminaciones de tarea programada/recordatorio (1:1 y grupo), lectura de info de cumplimiento de suscripción, acuñación de token de pagos de Hatch | Sin bloqueador nativo/atestiguado — alcanzable del mismo modo que cualquier otra op MEX |

El transporte 1 es lo que la pasada de investigación original (2.26.41.6) llama "el transporte VM de Hatch" y es la abrumadora mayoría de la superficie del subsistema. El transporte 3 es la **única** parte de Hatch que un cliente estilo Baileys/velowa puede plausiblemente conducir.

### 2.3 No forma parte de la VM — el enlace del quiz

`com.whatsapp.bot.quiz.AiQuizViewerActivity` es un visor a pantalla completa para un quiz embebido en un mensaje richResponse de bot almacenado (la primitiva de quiz richResponse "Jarvis" — territorio de `WA_META_AI.md` §4.3/§6.3, no Hatch). Carga el quiz **desde el almacén local de mensajes** por row id + key + sección (extras de intent `ai_quiz_viewer_message_row_id`, `ai_quiz_viewer_quiz_key`, `ai_quiz_viewer_section_index`) — sin llamada de red, sin transporte VM. Mencionado aquí solo para que no se confunda con una función de Hatch; ver §11 para la tabla de desambiguación completa.

---

## 3. Control plane y onboarding

### 3.1 Onboarding WAFFLE (`found`)

El primer uso de la superficie del agente corre **`HatchWaffleOnboarding`**: el cliente demuestra que es un build genuino, sin modificar, de WhatsApp vía atestación de integridad **WAFFLE** (la misma familia de atestación de cliente-oficial que la UI de ban `com.whatsapp.waffle.wfac` / vinculación de cuenta — ver `WA_CLIENT_INTEGRITY.md` §11 para el componente hermano WFAC). Migas de log: `"waffle-onboarding"`, `"vm-credentials"`, `"pairing-url"`, `"HatchWaffleOnboarding/link pairing-url-received="`. Un cliente de terceros no puede producir un token WAFFLE válido, así que no puede ni siquiera aprovisionar una VM — este es el bloqueador duro del lado onboarding, independiente del carrier de Noise-gateway.

### 3.2 Pairing (`found`)

`HatchPairingAuthBrowsingActivity` abre una **URL de pairing** estilo OAuth que vincula la cuenta de WhatsApp con el agente/cuenta de Meta AI; la finalización se registra como `pairing-url-received`.

### 3.3 Despertar de VM y el bearer Abra (`found`)

`GraphQlHatchAbraTokenProvider` acuña un token bearer de GraphQL "Abra" para la VM; `HatchVmApiClient` entonces hace:

```
POST https://hatch-api.meta.ai/hatch/vm/wake
{"vm_id": "...", "retry_count": N}
```

Esto es HTTPS ordinario, no el canal Noise. La respuesta alimenta la lógica de endpoint-en-caché de `HatchVmLifecycleCoordinator` ("connect cached-endpoint", "invalidateToken failed") y resuelve en un `HatchVmEndpoint` (`C57830PwR`): host/URL base, `auth_token`, `bearerExpiresAtMs`, flag de token validado, y un mapa de parámetros que lleva el `notary_token` de `/v1/noise`. `HatchAbraTokenRevoker` maneja la invalidación.

**Alcanzabilidad:** la llamada de despertar y la acuñación de token son HTTPS/GraphQL planos, observables por MITM en principio en un dispositivo rooteado con bypass de pinning — pero inútiles sin una cuenta aprovisionada por WAFFLE, ya que el servidor no entregará un endpoint de VM funcional a un cliente no reconocido (`inferred`; no confirmado independientemente del lado servidor).

---

## 4. El transporte VM atestiguado del agent-browser

Este es el hallazgo destacado del subsistema: la VM del agent-browser **no** viaja sobre la sesión principal Noise/XMPP de WhatsApp. Abre una **sesión Noise separada a un "noise gateway" de Meta**, transportada sobre el stack HTTP Tigon de Meta, a través de una biblioteca nativa dedicada, con un verificador de atestación y una clave opcional de auth-privado precompartida.

### 4.1 Handshake (`found`, `WaNoiseChannel`)

`WaNoiseChannel` toma el host del endpoint de VM y añade parámetros de query codificados en URL antes del handshake:

| Parámetro | Fuente |
|-------|--------|
| `auth_token` | `HatchVmEndpoint.auth_token` (bearer de VM) |
| `notary_token` | valor para la clave `/v1/noise` en el mapa de parámetros del endpoint, solo si no está en blanco |
| `app_id` | constante app-id de WA (`inferred`, no resuelto por literal) |
| `app_version` | literal hardcodeado `"2.26.41.6"` |

Ruta de handshake: **`/v1/noise`**. Timeout de handshake **20000 ms**; presupuesto de apertura de canal total **60000 ms** (`NoiseVmConnection`). Migas de log: `noise/open-start`, `noise/reused`, `noise/closed reason=...`, `noise/use-once`.

### 4.2 Carrier nativo y atestación (`found`)

`NoiseGatewayCarrier` es un objeto JNI `com.facebook.jni.HybridData` cargado por `NoiseGatewayCarrierSoLoader` como **`libwa-noise-gateway-carrier-jni.so`** — no es un archivo suelto en `lib/arm64-v8a/`, está empacado dentro del blob superpack `libs.so` (no hay extracción estática byte-exacta disponible).

Puntos de entrada nativos: `createNative(TigonServiceHolder, NoiseChannelManagerHolder)`, `start(endpoint, ..., byte[32]?, AttestationVerifierHolder, Stream0Listener)`, `sendWebsocketFrameNative`, `stopNative`, `cancelHandshakeNative`. Los callbacks de `Stream0Listener` (`onWebSocketUpgraded`, `onTransportReady`, `onReady(NoiseHandshakeOutcome)`, `onMessage`, `onClose/onFailure`) muestran que el canal es **Noise enmarcado dentro de un WebSocket**.

`AttestationVerifierHolder` tiene tres constructores nativos:

| Variante | Significado |
|---------|---------|
| `createNoOpNative()` | Sin atestación — la variante instanciada en la ruta decompilada vista en esta pasada |
| `createSnpNative(bool)` | Atestación de cómputo confidencial AMD SEV-SNP |
| `createSnpPinnedToChipsNative(chips[], bool)` | SNP fijada a IDs de chip permitidos específicos |

**Qué variante corre en runtime es `unknown`** desde esta pasada estática. La pasada de `hatch/cvm` de 2.26.45.10 (§6) encontró independientemente los endpoints concretos de control plane que listan/comprometen IDs de chip SEV-SNP (`/hatch/cvm-chip-allowlist`, `/hatch/cvm-chip-selection`), confirmando que el modo de atestación de chip fijado es infraestructura real, no solo una ruta de código inactiva.

`NoisePrivateAuthMode.REQUIRED` más una clave de 32 bytes es un modo "auth privado" opcional de clave precompartida (`inferred`: vinculación de canal); no poblado en la ruta vista, `unknown` si alguna vez se usa.

### 4.3 Transporte HTTP-sobre-Noise (`found`)

Una vez que el canal está activo, `WaVmHttpTransportImpl`/`VmHttpClient` envían solicitudes HTTP JSON ordinarias a través del túnel Noise vía Tigon. El adaptador de nivel app (`NoiseHatchVmTransport`, usado por cada función de workspace en §5) expone cuatro verbos:

| verbo | tag | uso |
|------|-----|-----|
| `CQ4(url, accept)` | `hatch_vm_read` | GET de lectura |
| `AEV(method,url,body,…)` | `hatch_vm_call` | llamada genérica de una vez |
| `CXY(method,url,headers,body,streaming)` | `hatch_vm_request` | solicitud en streaming (120 s, o ilimitada cuando `streaming`) |
| `Cly(url,body,…)` | `hatch_vm_subscribe` | suscripción SSE/dúplex de larga duración |

`NoiseChannelHolds` cuenta las referencias de "holds" abiertos; el canal se cierra tras liberarse el último hold (intervalo configurable). Superficie de rutas HTTP de VM (`found`, literales de string): `/v1/noise`, `/api/`, `/api/computer/subscribe`, `/api/artifacts/pin`, `/spaces/`, `/spaces/v2`, `/spaces/cvm/<slug>`, `/spaces/share/`, `/workspace/`, `/home/hatch/`, `/media/raw/`, `/fs/raw/`, más las rutas de credenciales en §5.9.

### 4.4 El stream de pantalla noVNC (`found`)

`assets/vmvnc/` incluye un cliente web **noVNC** real (`novnc-rfb.js`, `vnc.html`, `LICENSE.txt` MPL-2.0) — confirmado independientemente presente tanto en los builds 2.26.41.6 como 2.26.45.10 (`assets-sweep.md`). `BrowserSessionController` carga `https://appassets.androidplatform.net/assets/vmvnc/vnc.html` en un WebView. El HTML define un **`BridgedWebSocket`** que sobrescribe `window.WebSocket`: noVNC cree que abrió `wss://bridge.invalid/` (subprotocolo `binary`), pero cada frame RFB se transmite a través del puente JS de Android `window.AndroidVncBridge` (`socketSend`/`socketClose`/`socketOpen`, callbacks `window.__vncBridge.*`). El propio comentario del HTML embebido explica por qué: **el endpoint websockify real requiere `Authorization: Bearer <jwt>`**, que un WebSocket de WebView no puede fijar, así que el código nativo posee el socket real (abierto sobre Tigon con el bearer de VM) y el shim JS solo retransmite frames.

En resumen: el desktop/navegador de la VM se transmite al teléfono como **RFB (VNC) genuino sobre un WebSocket autenticado con bearer JWT**, en sí mismo tunelizado a través del gateway Noise atestiguado; noVNC lo renderiza en un WebView. El control de entrada (`isViewOnly`, `isInputEnabled`, `isPanModeEnabled`, métodos de zoom/viewport) y el tamaño (`BrowserViewerJson{width,height,devicePixelRatio}`) son controlados nativamente. `inferred`: frames fijos de "present"/preview más ligeros (`BrowserTaskScreenshotJson`, `BrowserTaskPresentationJson`) respaldan el `HatchBrowserStreamActivity` dentro del chat, con VNC interactivo completo reservado para `HatchComputerActivity`.

### 4.5 Lease de control (`found`)

`BrowserControlLeaseJson{controlOwner, taskId, controlExpiresAtMs}` + `BrowserControlGrantJson`/`BrowserControlEnvelopeJson` implementan quién conduce el navegador (agente vs. humano "tomar control"), acotado en el tiempo por `controlExpiresAtMs`. `BrowserViewerRequestJson` solicita un slot de visor. No confundir este **lease de control del navegador** con la "bid" de selección de chip SEV-SNP no relacionada de §6 — ver §11.

### 4.6 El enmarcado del túnel de agentspaces (`found`)

`HatchSpaceTunnel` reproxifica un WebView a apps "spaces" hospedadas en CVM en `/spaces/cvm/<slug>` sobre `hatch_vm_*`. El pequeño protocolo de envoltura JSON: `{"type":"http.res",id,status,streaming}`, `{"type":"http.end",…}`, `{"type":"http.err",…}`, más un push de invalidación de caché `{"type":"hatch:space:query-invalidated","spaceSlug":…,"payload":{"queryKeys":[…]}}`. **Elimina los encabezados hop-by-hop e identificadores** antes de retransmitir — la lista de bloqueo incluye `authorization, cookie, host, origin, x-forwarded-*, x-real-ip, x-noise-connection-id` — confirmando que el lado CVM termina un servidor HTTP real al que solo se llega a través del id de conexión Noise.

---

## 5. El workspace del agente

Cada función abajo se construye sobre los cuatro verbos `NoiseHatchVmTransport` de §4.3, es decir, cada literal de ruta abajo es una solicitud HTTP *dentro* del túnel Noise hacia la CVM. Bootstrap: `HatchBootstrapRequest` envía `{"sections":[…]}` en un método de suscripción `channel.bootstrap` y lee de vuelta `{"accepted":[…]}` — el cliente declara qué secciones de workspace quiere que se le empujen. `HatchSpacesSync` solo inicia cuando "Hatch está vinculado y existe un endpoint de VM" (guardas de log `found`).

### 5.1 Agent spaces

Un **space** es una mini web app/página de resultado interactiva hospedada por el agente, servida desde dentro de la CVM, direccionada por un `slug` de string. El teléfono nunca recibe el HTML directamente — un WebView local (`HatchSpaceActivity`) se apunta al túnel (§4.6), que retransmite las respuestas HTTP de la CVM cuadro por cuadro, así que un space puede ser una app en vivo y con estado en lugar de un artifact estático.

| acción | método + ruta | notas |
|--------|---------------|-------|
| catálogo | `GET /spaces/v2` | `{"spaces":[{"slug","preview_card_url","preview_image",…}]}` |
| estado de compartido | `GET /spaces/share/<slug>` | devuelve una URL de compartir si está compartido+público |
| publicar | multi-paso (`publish`/`post`/`poll`) | puede devolver "necesita confirmación" |
| despublicar | `DELETE /spaces/share/<slug>` | |
| eliminar | `DELETE /spaces/v2/<slug>?source=space` | |
| fijar/desfijar artifact | `POST /api/artifacts/pin {"artifact_ref":…,"pinned":bool}` | fija la salida de un space como artifact |

Ejemplo del mundo real (`inferred`): el usuario dice "rastrea vuelos a Lisboa por menos de €200"; Muse construye un space de rastreo; el usuario lo abre en vivo, publica un enlace compartible, y fija el mejor resultado como artifact.

### 5.2 Feed y actividad

`HatchFeedApi` decodifica un digest fechado de **ediciones**, cada una con **unidades** (`unit_id, title, kicker, emoji, body_md, days`) — el briefing periódico del agente. Respaldado por la línea de tiempo de actividad: `GET /api/activity?limit=200` en registros (`timestamp, type, status, title, subtitle, messageId, taskLabel, details.goal{…}`), enlazando cada registro con un mensaje de chat y opcionalmente con un goal. El punto de entrada independiente de Feed está detrás de una compuerta de debug en 41.6 (`str5508` "[Debug Only] Feed"); la línea de tiempo de actividad que lo alimenta no lo está.

### 5.3 Goals

`HatchGoalsApi`: lista `GET /api/goals?<query>`, detalle `GET /api/goals/<goal_id>`. Un goal es un objetivo duradero: `{goal_id, title, emoji, summary, momentum_status, sub_goals:[…], updates:[{text, effective_at}]}` — un objetivo permanente con un estado de salud y un log de actualizaciones con marca de tiempo al que el agente añade. La entrada está detrás de una compuerta de debug (`str5511` "[Debug Only] Goals").

### 5.4 Ideas

Acciones ejecutables propuestas por el agente que el usuario puede **Ejecutar** o **Cancelar** (`HatchIdeaDetailBottomSheet`). Strings: "This idea is already running.", "This idea isn't available anymore.", "No ideas right now. Check back later.", "Couldn't start that idea. Try again." Ejemplo: el agente sugiere "Redactar el recap de Q3"; tocar Ejecutar inicia una tarea en marcha registrada en feed/actividad.

### 5.5 Artifacts y media/archivos del workspace

Los artifacts son salidas producidas por el agente (documento, imagen, hoja de cálculo, el resultado de un space), fijados/desfijados vía `/api/artifacts/pin`. Los archivos del agente viven en un **sistema de archivos CVM por agente real** (`com.whatsapp.bot.infra.vmmedia.HatchWorkspaceMediaApi`):

| llamada | ruta | forma |
|------|------|-------|
| librería | `POST /fs/library {"preset":"media","limit":n,"offset":m}` | `{entries:[{path,size,modified_ms}],total,has_more}` |
| crudo | `GET /fs/raw/<path>` | bytes crudos |
| miniatura | `GET /fs/thumbnail/<path>?p=sm` | |
| eliminar | `POST /fs/delete {"path":…,"recursive":false}` | |

String de confirmación de eliminación: "This file will be removed from your agent's files. You can't undo this."

### 5.6 Documentos de identidad

Los documentos "about me" del agente se almacenan como **archivos de texto plano en el mismo sistema de archivos de VM**, no un almacén dedicado: `GET /fs/read {path,offset,len}` → `{text,bytes,eof,not_found}`; `POST /fs/write {path,text|bytes,offset,append,overwrite,create_parent}`. El usuario edita documentos que el agente luego lee como contexto persistente.

### 5.7 Aprobaciones e historial de aprobaciones

**Compuerta en vivo:** antes de una acción riesgosa/irreversible el agente levanta una aprobación (`HatchBrowserPreviewActivity`, `str54e1` "Approval required"). **Historial/auditoría:** `GET /approvals/history?record_schema=snapshot_v1&limit=50`, paginado vía `next_cursor`, en un registro estructurado por aprobación: `{approval_id, status, decision, outcome_label, summary_title, purpose_summary, scope_summary, requested_at_ms, permission_question, payload_preview, request_preview_document, display_name, icon_key, blocks, rows, fields, items, links, attachments, version, truncated}`. La entrada está detrás de una compuerta de debug (`str54e8` "[Debug Only] Approval history"), el log subyacente no lo está.

### 5.8 Tareas programadas — tres implementaciones distintas

| # | Superficie | Transporte | Ops | ¿Alcanzable por el cliente? |
|---|---------|-----------|-----|--------------------|
| a | Recordatorios 1:1 de Meta AI (`com.whatsapp.metaai.tasks`) | MEX plano sobre `whatsapp-android-www` | **`GetMetaAiReminders`**, **`DeleteMetaAiReminder`** | **Sí, más o menos** — persisted-query MEX basada en nombre, sin bloqueador nativo/atestiguado |
| b | Tareas programadas de grupo (`com.whatsapp.bot.group.groupinstructions.impl`, nueva en 41.6) | MEX plano sobre `whatsapp-android-www` | **`GetMetaAiGroupReminders`** (parámetro `groupId`), **`DeleteMetaAiGroupReminder`** (`groupId`, `reminderId`) | **Sí, más o menos** — mismo razonamiento |
| c | Tareas programadas de VM de Hatch (`com.whatsapp.hatch.scheduledtasks.impl`) | VM Noise | corridas recurrentes de la VM del agente, canceladas sobre el transporte VM | No — solo nativo |

9a/9b son las **únicas** ops de workspace que un cliente de terceros podría plausiblemente alcanzar, porque no tocan ni el carrier nativo de noise-gateway ni el onboarding WAFFLE. Crear un recordatorio parece suceder del lado del agente (vía tool-call de chat de Meta AI), no a través de una mutación visible para el cliente — solo están presentes las ops Get + Delete. Los `doc_id` numéricos para ambos pares son `unknown` (resolución de persisted-query basada en nombre; no capturada independientemente). La superficie de group-instructions también permite a un admin configurar el Meta AI del grupo (reglas, documentos de referencia, tono) vía `CustomizeGroupMetaAiActivity` — UI adyacente, no en sí misma una op de tarea programada.

### 5.9 Conectores y el almacén seguro de credenciales

Un **connector** es un vínculo registrado entre el agente y un servicio externo. El usuario se autentica una vez (OAuth / API key / usuario+contraseña / FoA / Stripe / Messenger), y la credencial resultante se almacena **del lado servidor dentro de la CVM, nunca en Android Keystore** — `SecureCredentialVault` realiza todas las operaciones como llamadas HTTP sobre el mismo transporte Noise-HTTP de VM. No existe ninguna referencia a `KeyStore`, `EncryptedSharedPreferences`, o `AndroidKeyStore` en ningún lugar de `securecredentials/`.

Endpoints de credenciales (`found`, sobre el canal Noise de VM):

| ruta | rol |
|------|------|
| `POST /v1/credentials/capture` | enviar una credencial capturada |
| `POST /v1/credentials/catalog/update` | upsert; campos vistos: `username`, `password`; permiso vía enum wireValue `JA9` |
| `POST /v1/credentials/catalog/delete` | `{id}` → `{ok}` |
| `GET /v1/custom-connectors/list` | |
| `POST /v1/custom-connectors/register` | forma de API-key `{connector, api_key:{key}, replace_existing}` o forma OAuth `{connector, oauth_bootstrap:{client_id, client_secret?,…}, replace_existing}` → `authorize_url` |

Catálogo de conectores + flujos de conexión (`found`, sobre el mismo canal): `GET /api/connectors?surface=settings&icon_cdn=whatsapp` → `{connectors:[{id,name,description,icon,state,is_custom,management_kind,supports_multiple_accounts,consent}]}`; info de conexión por conector (`/connectors/<id>/connect/info`) y rutas de auth específicas de tipo para OAuth, API key, usuario/contraseña (con `two_factor_required`/`attempts_remaining`/`login_timeout_remaining_secs`), **FoA** (cuentas Family-of-Apps), **compañero Messenger** (vinculación de chat con compuerta de PIN), y **enlace Stripe** (pagos). Los permisos son por conector (`GET/SET /permissions/connectors/<id>`, string de UI "Agent permissions"). Los conectores personalizados llevan una advertencia explícita de código no revisado ("Meta no revisa los conectores personalizados… supervisa el uso que hace tu agente").

Por diseño, el agente **no ve secretos crudos**: "Securely store passwords for your agent to use", "Shared with your agent without saving". La acción de **tarjeta virtual** (`HatchConnectorCardActionActivity`) acuña una tarjeta de un solo uso que el agente usa para pagos de modo que el número de tarjeta real nunca se expone ("The agent will never see your credit card"). `assets/api_key.txt` existe en la APK y se trata como material de credencial según el contrato de evidencia del brain — no abierto/citado aquí; `inferred` que es una clave API de nivel cliente/app para el control plane hatch-api/GraphQL, no un secreto por usuario.

**Alcanzabilidad para toda la §5:** solo nativo. Cada literal de ruta arriba es recuperable de la APK; nada de esto es conducible, observable (está cifrado dentro del túnel Noise), ni suplantable desde un cliente de terceros, porque cada una de estas llamadas necesita el transporte atestiguado de §4 más una VM aprovisionada por WAFFLE.

---

## 6. Recuperación de identidad CVM — el sistema de PIN OPAQUE Vesta (`hatch/cvm`)

### 6.1 Corrigiendo el encuadre de "bóveda de tarjeta virtual"

Una pasada de investigación anterior (2.26.45.10) describió `hatch/cvm` + `hatch/cvm/pin` como una "bóveda de tarjeta virtual con compuerta de PIN". **Ese encuadre está equivocado a nivel de la capa cripto.** Confunde dos subsistemas no relacionados:

- **`hatch.connectors` / `HatchConnectorCardActionActivity`** (§5.9) — un flujo real, separado, de concesión de conector para un riel de pago de terceros (casi seguramente Stripe). Tiene **cero referencias de código** a ninguna clase `com.whatsapp.hatch.cvm` o `com.facebook.vesta` (verificado: sin referencia cruzada desde el smali de `hatch.connectors` hacia `HatchCvmPinActivity`/`HatchCvmVestaClient`/`HatchCvmKeyService`).
- **`hatch.cvm` / `hatch.cvm.pin`** es el sistema de **inscripción de identidad de VM confidencial y atestación de chip** del agente, no un almacén de tarjetas. No almacena **ningún dato de pago de ningún tipo** — ningún campo de PAN/CVV/facturación en ninguna parte del paquete. Lo que protege es un **secreto de identidad de dispositivo/VM recuperado vía un intercambio de claves autenticado por contraseña OPAQUE, con el PIN como contraseña**, atado a la selección de chip de hardware AMD SEV-SNP para la CVM.

El PIN **no es un desbloqueo solo local**: la ruta de login de `HatchCvmKeyService` hace un round-trip de un intercambio OPAQUE real a un backend de Meta (`hatch-api.meta.ai/hatch/vesta-auth/*`, HTTPS plano) antes de que se derive/restaure cualquier material de clave local. Un PIN incorrecto falla **del lado servidor** ("wrong pin", "crypto failed"), no solo contra un hash local.

De forma crítica, este tráfico es **HTTPS plano a `hatch-api.meta.ai`** — el mismo host de control plane que `/hatch/vm/wake` (§3.3) — **no** el canal VM de Noise-gateway-sobre-Tigon atestiguado. Así que la afirmación general "mismos bloqueadores duros que el transporte" de §4/§5 no aplica aquí: el bloqueador real para este subsistema es criptográfico, no de transporte atestiguado.

### 6.2 La superficie nativa

`com.facebook.vesta.VestaClient` carga **`libvesta_client_jni.so`** (nueva en 2.26.45.10). Los 19 métodos nativos declarados sobre ella implementan un **PAKE OPAQUE con PIN-como-contraseña, además envuelto con una capa de KEM/firma post-cuántica**, más un paso de validación de "clave HSM" atada al dispositivo:

| método nativo | rol |
|---|---|
| `getApiVersionNative` / `getProtocolVersionNative` | negociación de versión |
| `beginLoginNative` / `finishLoginNative` (×2 sobrecargas) | pasos 1 y 2 de login OPAQUE (produce material de clave de sesión/exportación) |
| `beginRegisterNative` / `finishRegisterNative` / `finishRegisterProtoNative` | registro OPAQUE (inscripción de un nuevo PIN) |
| `unpackLoginPayloadNative` / `unpackLoginPayloadProtoNative` | decodificar el payload de login en depósito del servidor |
| `validateHsmKeyNative` / `validateHsmKeysWithOtaBundleNative` | validar un par de claves respaldado por hardware, opcionalmente con un bundle OTA de rotación de clave de dispositivo |
| `verifyRestoreHistoryNative` | verificar un registro de historial de restauración/recuperación previo |
| `pqWrapFinishLoginNative` / `pqWrapFinishRegisterNative` / `pqUnwrapFinishLoginResponseNative` | envolver/desenvolver post-cuántico de payloads de login/register |
| `pqWrapSchemeNative` | qué esquema PQ está en uso (valor de retorno `unknown` — necesita Frida) |

`libvesta_client_jni.so` está, como el carrier de noise-gateway, empacado dentro del blob opaco SUPERPACK — no fue posible extracción estática byte-exacta en esta pasada. `libvoprf-ed25519.so` (presente en el mismo build) es consistente con una primitiva OPRF/VOPRF (bloque de construcción central de OPAQUE) pero **no** se vinculó cruzadamente de forma independiente con `VestaClient` — registrado como una biblioteca adyacente plausible, no probado que sea la misma implementación (`unknown`).

### 6.3 Endpoints de cable — HTTPS plano a `hatch-api.meta.ai`

| ruta | rol |
|---|---|
| `POST /hatch/vesta-auth/begin-login` | paso 1 de login OPAQUE |
| `POST /hatch/vesta-auth/finish-login` | paso 2 de login OPAQUE, devuelve el payload en depósito |
| `POST /hatch/vesta-auth/begin-register` | paso 1 de registro OPAQUE (PIN nuevo/cambiado) |
| `POST /hatch/vesta-auth/finish-register` | paso 2 de registro OPAQUE |
| `GET /hatch/vesta-auth/user-info` | `is_registered` + contadores de intento/bloqueo |
| `GET /hatch/fetch_vms?notary_token=true[&vm_id=]` | listar/resolver la(s) CVM(s) del usuario |
| `POST /hatch/lease_vm` / `POST /hatch/cold-lease-cvm` | arrendar una instancia de CVM (caliente / fría) |
| `GET /hatch/cvm-replace-state?env_id=` | transición de máquina de estados de CVM |
| `GET /hatch/cvm-chip-allowlist?env_id=` | qué IDs de chip SEV-SNP están permitidos para esta CVM |
| `POST /hatch/cvm-chip-selection` | comprometer la selección/oferta de chip |
| `GET /hatch/onboarding_statuses` | chequeo de estado de onboarding |
| `POST /hatch/vm/wake` | despertar/reanudar la CVM (también §3.3) |

Ninguno de estos toca `/v1/noise` ni los verbos `hatch_vm_*` — confirmando la corrección de §6.1. `/hatch/cvm-chip-allowlist` y `/hatch/cvm-chip-selection` son la primera **evidencia de cable concreta** para el modo de atestación SEV-SNP "fijado a IDs de chip específicos" que §4.2 solo encontró como una firma de constructor nativo.

Los DTOs de cable (campos de nombre serial de `kotlinx.serialization`, no nombres de campo Java obfuscados) incluyen la propia nomenclatura de intercambio de tres mensajes **L1/L2/L3** de OPAQUE (`base64url_encoded_opaque_l1/l2/l3`, más variantes `_sig`), claves públicas RSA/Ed25519 "island" atadas al dispositivo (`unknown` la procedencia — HSM/Keystore vs. un formato interno de Vesta), y un journal local (`HatchCvmJournal`: `candidate_chip_ids`, `accepted_chip_ids`, enum `bid_state` `PENDING/ACCEPTED/RETIRED`, `abra_user_id` — la misma identidad bearer que `GraphQlHatchAbraTokenProvider`).

### 6.4 Qué protege realmente el PIN

`HatchCvmKeyService.A00` (la ruta de recuperación): (1) corre el login OPAQUE (`begin-login` luego `finish-login`, matemática nativa); (2) solo tras el éxito, `HatchCvmKeyProviderImpl` deriva/restaura el material de clave local real desde el payload de login en depósito; (3) existe una ruta de borrado para desajuste de clave de dispositivo o reset explícito. **Se requiere un PIN correcto para completar un intercambio OPAQUE cliente↔servidor real** — el servidor solo libera el payload en depósito ante un finish-login correcto, limitado por tasa y verificado del lado servidor (`attempts_remaining`, `login_timeout_remaining_secs` en cada respuesta). Un atacante con el dispositivo pero sin el PIN no puede forzar por fuerza bruta esto localmente. El secreto protegido es el **material de clave de identidad de CVM/dispositivo necesario para reanudar la sesión de VM confidencial de este usuario** — no una credencial de pago.

Por separado, `HatchCvmPinReminder` usa una clave AES/GCM **solo local** (alias `hatch:pin-reminder:v1:...`) puramente para cifrar un estado de notificación "recuérdame configurar un PIN" — no relacionado con el intercambio Vesta y la única pieza de cripto no observable en el cable de este subsistema.

### 6.5 Veredicto de alcanzabilidad para §6

Esquema de cable completamente recuperable (arriba); el transporte es HTTPS plano, observable por MITM en principio **sin** derrotar la atestación WAFFLE ni el carrier nativo de Noise-gateway. Pero **participar de verdad** (un login/register real) no es posible solo con la APK: cada campo de solicitud/respuesta es producido o consumido por operaciones nativas de envoltura/desenvoltura OPAQUE + post-cuántica dentro de `libvesta_client_jni.so`, empacado en el superpack sin extracción byte-exacta disponible. Un cliente podría capturar y reproducir la *forma* JSON en texto plano pero no puede calcular un `opaque_l1`/`l3` válido, una prueba de par de claves "island", o un payload envuelto en PQ — un bloqueador **criptográfico**, estructuralmente distinto del bloqueador de transporte atestiguado en §4.

---

## 7. Monetización — el tier de suscripción pago de Hatch

Un clúster de suscripción de la era 2.26.45.10 añade un tier real y facturado para Muse. El flujo de compra (cadena `inferred`, cada paso `found` individualmente):

1. El cliente verifica el feature flag **`ai_hatch_in_app_subscriptions_enabled`** (log: "`ai_hatch_in_app_subscriptions_enabled` is off"). No se encontró ningún ID de flag numérico para él — se referencia solo por nombre.
2. Constante de tier **`NME_SUBSCRIPTION`**; detalles de producto obtenidos por tier (`HatchSubscriptionPurchase$launch$2`, log "Fetching product details for tier"; nombre de tier interpolado, no un SKU hardcodeado).
3. Chequeo de cumplimiento: **`WamoSubGetComplianceInfo`** (`whatsapp-android-mex`, basado en nombre, sin campos de entrada fijados en el call site — solo delimitado por sesión/identidad).
4. Acuñación de token de pagos: **`HatchGenFrlPaymentsAccessTokenMutation`** (`GraphQlHatchFrlPaymentsTokenProvider`, namespace `whatsapp-android-www`; no se encontró la expansión de "FRL" en ningún string en esta pasada — `unknown`).
5. Lanzamiento de Google Play Billing (`HatchManageSubscriptionViewModel$openBilling$1`) — `BillingClient` Android estándar vía un SDK de comercio compartido de Meta (`com.facebook.payments.dcp.xapp.*`), etiquetado `app="WHATSAPP"`.
6. Al comprar, conciliación de cumplimiento del lado servidor (`HatchSubscriptionPurchaseReconciler`), probablemente vía **`DCPFulfillIAPTransactionsMutation`** (`pay_dcp_fulfill_iap_transactions`, solicitud directa a Pando, campos `platform`/`app`/`purchase_tokens`/`subscription_purchase_tokens`/`upl_session_id`, todos obligatorios en este call site) — no confirmado independientemente como la llamada exacta que usa este reconciliador (`unknown`).

Cuatro ops adicionales declaradas solo en el catálogo de persisted-query (`IACQueryProductInfo`, `IACQuoteDisplay`, `IACSandboxPlatformMode`, `DCPInternalSandboxCreateSessionMutation`) **no tienen ninguna clase llamante encontrada en ningún lugar del smali** — `unknown` si eso es código muerto/futuro, una compuerta de servidor/flag, o un call site concatenado por string que un grep plano no detecta.

**Alcanzabilidad:**

| op | namespace | necesita | ¿alcanzable por un cliente de terceros? |
|---|---|---|---|
| `WamoSubGetComplianceInfo` | `whatsapp-android-mex` | solo una sesión mex autenticada | **Sí, en principio** — query mex plana sin parámetros |
| `HatchGenFrlPaymentsAccessTokenMutation` | `whatsapp-android-www` | sesión autenticada | **Alcanzable a nivel de transporte**; el valor del token acuñado fuera del flujo previsto es `unknown` |
| `DCPFulfillIAPTransactionsMutation` | `whatsapp-schema` (Pando) | un token de compra/suscripción de Play Billing genuino, firmado por Google | **No** — la solicitud se puede dar forma, pero nada veraz se puede poner en ella sin una compra real de Play Billing a través de un contexto `com.whatsapp` firmado |
| `IAC*` / `DCPInternalSandboxCreateSessionMutation` | `whatsapp-schema` | unknown (no se encontró clase llamante) | **Unknown** |
| El propio Google Play Billing | n/a | Play Store + contexto de app firmado | **No** — ni siquiera es una llamada al servidor de WhatsApp |

---

## 8. Veredicto de alcanzabilidad

| Componente | Transporte | Bloqueador | ¿Alcanzable desde un cliente de terceros (Baileys/velowa)? |
|---|---|---|---|
| Agent spaces, feed/actividad, goals, ideas, artifacts, media/archivos del workspace, documentos de identidad, approvals+historial, tareas programadas de VM de Hatch, conectores (todos los flujos), almacén seguro de credenciales | Canal VM Noise atestiguado (§4) | carrier nativo de noise-gateway `.so` + onboarding WAFFLE | **No** |
| Control plane (despertar VM, token Abra, URL de pairing) | HTTPS plano a `hatch-api.meta.ai` | aprovisionamiento con compuerta WAFFLE (el servidor no emitirá una VM funcional sin él) | **No** (esquema observable por MITM; no conducible independientemente) |
| Identidad/recuperación de PIN de CVM (`hatch/cvm`, Vesta OPAQUE) | HTTPS plano a `hatch-api.meta.ai` | matemática nativa OPAQUE + post-cuántica en `libvesta_client_jni.so` | **No** — bloqueador criptográfico, no de transporte atestiguado |
| Recordatorios 1:1 — `GetMetaAiReminders` / `DeleteMetaAiReminder` | MEX plano, `whatsapp-android-www` | ninguno encontrado | **Sí, más o menos** (doc_id `unknown`) |
| Recordatorios de grupo — `GetMetaAiGroupReminders` / `DeleteMetaAiGroupReminder` | MEX plano, `whatsapp-android-www` | ninguno encontrado | **Sí, más o menos** (doc_id `unknown`) |
| Info de cumplimiento de suscripción — `WamoSubGetComplianceInfo` | MEX plano, `whatsapp-android-mex` | ninguno encontrado | **Sí, en principio** |
| Acuñación de token de pagos — `HatchGenFrlPaymentsAccessTokenMutation` | GraphQL plano, `whatsapp-android-www` | ninguno a nivel de transporte; el valor práctico del token en otro contexto es unknown | **Alcanzable a nivel de transporte** |
| Cumplimiento de IAP — `DCPFulfillIAPTransactionsMutation` | GraphQL Pando plano, `whatsapp-schema` | necesita un token de Play Billing firmado genuino | **No** (nada veraz que enviar) |
| Ops `IAC*` / IAP de sandbox | `whatsapp-schema` | no se encontró clase llamante | **Unknown** |
| Quiz richResponse (bot.quiz) | almacén local de mensajes | ninguno — no es una función de VM | payload recuperable; llega como un mensaje de bot normal |

Las filas "Sí, más o menos"/"Sí, en principio" son **toda** la superficie alcanzable por el cliente de este subsistema. Todo lo demás — que es la mayor parte del agente — requiere ya sea el carrier nativo de Noise-gateway más una atestación WAFFLE válida, o criptografía nativa OPAQUE/post-cuántica que no se puede extraer estáticamente de esta APK.

---

## 9. Baileys / velowa

**Veredicto: este subsistema es JS-imposible para un cliente de terceros, punto final — no una función faltante, sino estructural.** velowa (el proyecto de cliente activo detrás de estos documentos) no puede implementar la VM de agent-browser ni el workspace de Hatch/Muse por las mismas razones que dio la pasada de investigación original:

| Bloqueador | Por qué no se puede evadir en JS/WASM |
|---|---|
| `libwa-noise-gateway-carrier-jni.so` | Todo el handshake Noise y el enmarcado WebSocket para el canal de VM es código nativo dentro del blob opaco SUPERPACK. No hay documento de protocolo contra el cual reimplementar — la forma de cable (parámetros de query, ruta `/v1/noise`, verbos HTTP-sobre-Noise, subprotocolo RFB de noVNC) se recupera arriba, pero la criptografía Noise real (derivación de claves, autenticación de frame) solo existe compilada en ese `.so`. Reimplementarlo significa hacer ingeniería inversa de una biblioteca nativa stripeada, no escribir un cliente contra una spec. |
| Atestación de cliente-oficial WAFFLE | Controla el onboarding de VM antes de que siquiera se abra un canal Noise. Un cliente de terceros no puede producir un token WAFFLE válido, así que no puede aprovisionar una VM en primer lugar — esto bloquea incluso un intento del handshake Noise. |
| `libvesta_client_jni.so` (OPAQUE + PQ) | Separado de lo anterior: incluso donde el tráfico de recuperación de identidad (§6) es HTTPS plano y observable, la matemática OPAQUE del lado cliente (`opaque_l1`/`l3`, las pruebas de par de claves "island", la envoltura post-cuántica) es nativa. Capturar la forma JSON no te da nada con qué calcular una solicitud válida. |
| Atestación AMD SEV-SNP | Ortogonal al cliente — es la VM del *servidor* probándose genuina ante la app oficial — pero confirma que todo el diseño asume un par nativo y atestiguado en ambos extremos. |
| Tigon | El stack HTTP nativo cross-app interno de Meta lleva cada solicitud en §4 y §6; sus objetos de solicitud no son un formato de cable público y versionado. |

Lo que velowa (o cualquier cliente de protocolo) *podría* alcanzar sin tocar nada de lo anterior: las cuatro ops MEX de recordatorio basadas en nombre (§5.8) y las ops GraphQL de cumplimiento de suscripción/token de pagos (§7) — todas las cuales viajan sobre el mismo transporte MEX/GraphQL plano de WA que velowa ya habla para todo lo demás en este repositorio. No se da ningún ejemplo de código aquí porque ninguno del material fuente de este informe capturó una solicitud/respuesta concreta para esas ops más allá de los nombres de operación y formas de parámetro ya listados en §5.8/§7/§8; inventar bytes de payload tergiversaría el nivel de evidencia.

---

## 10. Casos de error / gotchas

| Síntoma | Causa | Nota |
|---|---|---|
| "Computer is turned off on this VM" | VM no aprovisionada/despierta para la superficie de desktop completa | string de `HatchComputerActivity` |
| "Approval required" nunca se resuelve en una acción | el usuario no confirmó la compuerta de aprobación | por diseño — humano en el loop |
| "This idea isn't available anymore." / "This idea is already running." | tarjeta de idea superada o ya ejecutándose | `HatchIdeaDetailBottomSheet` |
| "No goals yet" / "No ideas right now. Check back later." / "No approvals yet" | secciones de workspace vacías, no un error | |
| "Couldn't load your agent's files" | la llamada a `/fs/library` o `/fs/raw/` falló sobre el túnel Noise | |
| Estilo "thread superseded by a newer search, refusing" de `PrivateSearchSessionManager` (sistema TEE adyacente, no Hatch) | listado aquí en §11 solo para evitar la contaminación cruzada de strings de error entre los dos sistemas | ver Distinciones Clave |
| 400 "already exists; set replace_existing=true" | registro de conector personalizado sin el flag `replace_existing` | `HatchConnectorsListRequester` |
| "wrong pin" / "finish-login crypto failed" | login OPAQUE falló del lado servidor | limitado por tasa vía `attempts_remaining`/`login_timeout_remaining_secs` |
| "hsm key missing" / "hsm key invalid" / "hsm key check failed" | falló la validación de clave HSM atada al dispositivo dentro de la ruta de recuperación Vesta | §6.4 |
| `noise/gave-up limit=deadline` | se excedió el presupuesto de apertura de canal Noise de VM (60 s) | `NoiseVmConnection` |
| `NoiseHandshakeOutcome.VERIFICATION_FAILED` | falló el chequeo de atestación en el handshake de Noise-gateway | §4.2 |
| "`ai_hatch_in_app_subscriptions_enabled` is off" | feature flag de suscripción desactivado del lado servidor | §7 |
| "HatchSubscriptionPurchase/purchase no compliance data" | falta el resultado de `WamoSubGetComplianceInfo` antes de un intento de compra | §7 |

---

## 11. Distinciones clave — qué NO confundir

| No confundir | Hecho |
|---|---|
| Agente Hatch/Muse (este informe) vs. **chat de Meta AI** (`WA_META_AI.md`) | Meta AI es un contacto de bot al que se llega mediante `botInvokeMessage`/JIDs de bot en el proto de mensaje normal; Hatch/Muse es un agente separado que conduce una VM remota atestiguada. Comparten algo de plomería (canal de metadata JSON de Hatch vía `ProtocolMessage.aiMetadataOperation`, flags de capacidad anunciados al JID de bot de Hatch `1807055946647697@bot`) pero son subsistemas arquitectónicamente distintos |
| VM de Hatch/Muse vs. **Private Processing / clúster TEE** (IA de contexto de chat, Private Search) | El clúster TEE (`ClusterFetchPrekeyBundleConnection`, `IplsdHandshakeExecutor`, `PsiSearchToolHandler`, `TeePrefixCacheAnchor`) es Meta AI respondiendo preguntas **sobre tus propios chats locales** vía un enclave atestiguado + búsqueda PSI — no tiene nada que ver con la VM de agent-browser de Hatch. El *envío de consulta* de Private Search viaja sobre un mensaje de chat de bot plano (alcanzable), mientras que el cómputo PSI/enclave en sí mismo permanece nativo — una forma de alcanzabilidad distinta de cualquier cosa en este informe |
| `hatch.cvm` (identidad/recuperación de chip, §6) vs. `hatch.connectors` (tarjeta virtual / Stripe, §5.9) | Dos funciones separadas que solo comparten las palabras casuales "card"/"vault" en el encuadre de producto; sin dependencia de código entre ellas (verificado) |
| La clave AES/GCM local de `HatchCvmPinReminder` vs. el intercambio OPAQUE de Vesta | Cifrado de estado de notificación solo local vs. una recuperación de identidad real con round-trip al servidor — solo la segunda es compuerta de PIN "del lado servidor" |
| Campos "bid_state"/"chip" (§6) vs. el **lease de control** del navegador (§4.5) | Contabilidad de selección de chip de hardware SEV-SNP vs. quién conduce el navegador del agente (agente/humano) — tres usos distintos de vocabulario superpuesto ("bid"/"lease"/"control") en este código base |
| El control plane HTTPS plano de Vesta (§3, §6) vs. el canal VM de Noise-gateway atestiguado (§4) | Transportes distintos, bloqueadores distintos (matemática OPAQUE nativa vs. Noise nativo + atestación WAFFLE) — confundirlos exagera dónde aplica realmente el bloqueador de transporte atestiguado |
| Agent spaces (§5.1) vs. artifacts producidos por el agente (§5.5) | Un space es una app hospedada, en vivo y con estado; un artifact es una salida estática (el *resultado fijado* de un space se convierte en un artifact, pero el space en sí sigue corriendo) |
| `com.whatsapp.bot.quiz.AiQuizViewerActivity` vs. una función de Hatch | Lee un quiz richResponse ya entregado como un mensaje de bot normal desde el almacenamiento local — sin VM, sin llamada de red, no forma parte de este subsistema en absoluto |

---

## 12. Flujo de extremo a extremo — una sesión de tarea de agent-browser

```
[User, in chat]
    │  "book me a table for two tonight"
    ▼
[Onboarding, first use only]
    │  HatchWaffleOnboarding: official-client WAFFLE attestation
    │  HatchPairingAuthBrowsingActivity: pairing URL (account ↔ agent link)
    ▼
[Control plane]  plain HTTPS to hatch-api.meta.ai
    │  GraphQlHatchAbraTokenProvider → Abra bearer
    │  HatchVmApiClient: POST /hatch/vm/wake {vm_id, retry_count}
    │  → HatchVmEndpoint{host, auth_token, notary_token, ...}
    ▼
[Noise-gateway handshake]  native libwa-noise-gateway-carrier-jni.so over Tigon
    │  GET …<vmhost>…?auth_token&notary_token&app_id&app_version=2.26.41.6
    │  path /v1/noise, 20s handshake timeout, attestation verifier (noOp/SNP/SNP-pinned)
    ▼
[Attested Noise channel open]  (60s budget, ref-counted "holds")
    │
    ├──▶ hatch_vm_request /api/computer/subscribe  — live task state (SSE-style)
    │
    ├──▶ hatch_vm_call   — agent navigates the booking site inside the CVM
    │        │
    │        ▼
    │    [Phone shows it live]  noVNC (RFB) over JWT-bearer WebSocket, viewOnly
    │        unless user takes a BrowserControlLeaseJson "control lease"
    │
    ├──▶ Login needed → /v1/credentials/... fetched INSIDE the VM
    │        (SecureCredentialVault; raw secret never reaches the agent's
    │         reasoning context, per design)
    │
    ├──▶ Payment needed → HatchConnectorCardActionActivity mints a virtual card;
    │        real card number never exposed to the agent
    │
    ├──▶ Risky/irreversible step → HatchBrowserPreviewActivity "Approval required"
    │        user confirms → recorded in HatchApprovalHistoryApi
    │
    ▼
[Outcome]
    │  artifact/feed entry (hatch.artifacts / hatch.feed)
    │  optionally scheduled to recur (HatchScheduledTasksActivity, native VM path)
    ▼
[Noise channel teardown]  last "hold" released → noise/closed reason=unlink
```

Por separado (no es parte de la misma sesión, MEX/GraphQL plano, sin transporte atestiguado involucrado):

```
[Client]  GetMetaAiReminders / GetMetaAiGroupReminders
    │  whatsapp-android-www, name-based persisted query
    ▼
[WA server]  reminder list (status SCHEDULED/CLAIMED/FULFILLED)

[Client]  DeleteMetaAiReminder / DeleteMetaAiGroupReminder
    ▼
[WA server]  reminder removed
```
