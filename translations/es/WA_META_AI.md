<!-- src-sha1: 4a0b884541f4221f33fe16d1a5659612eb6bac89 -->
# WhatsApp Meta AI — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** Internos de Meta AI — JIDs, enrutamiento, campos proto, solicitudes de metadatos Hatch, renderizado de respuestas, por qué falla Baileys, solución

---

## 1. Qué es Meta AI (técnicamente)

Meta AI es un contacto bot direccionado por JIDs de bot especiales (servidor `bot`), con campos proto específicos de bot sobre los tipos de mensaje normales y un canal de solicitud JSON separado ("metadatos Hatch") transportado en un `ProtocolMessage`. Todas las afirmaciones son análisis estático del APK decompilado. Nivel: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto.

Los nombres de este informe que estaban ofuscados en 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) se volvieron a resolver desde anclas estables; no existen bajo esos nombres en 2.26.41.6.

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| BotJid | `C24770wv` | Clase JID, servidor `"bot"`, tipo 26, cadena numérica de 1 a 20 caracteres, sin cero inicial |
| Constantes de JID de bot | `AbstractC34361Xw` | Constantes y conjuntos de Hatch / Fallback / LID |
| Mapeo de JID | `AbstractC24760wu` | Mapeo bot ↔ LID, conversión del destino saliente |
| Gating | `C39311it` | Habilitación por feature flag según JID (`A0E(Jid)`) |
| Gestor de solicitudes Hatch | `HF1` (`HatchMetadataRequestManager`) | Solicitudes JSON, mapa de pendientes |
| Constructor proto de Hatch | `Hf6` | Construye `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | `Message` proto |
| WebMessageInfo | `C30626DTu` | `WebMessageInfo` proto |
| ProtocolMessage | `BD3` | `ProtocolMessage` proto |
| MessageContextInfo | `C30624DTs` | Contiene `botMetadata` |
| BotMetadata | `C30615DTj` | Metadatos de bot por mensaje |
| Registro de perfil de bot | `C199348dm` | Nombre, descripción, cadena de ID de persona, miniatura |

---

## 2. JIDs de Meta AI

### 2.1 JIDs encontrados en el código

| Constante | Clase | Rol | Nivel |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) vía `AbstractC34361Xw.A00` | **Hatch**, primario. Perfil por defecto construido en `C223219iv` a partir del payload del flag **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) vía `AbstractC34361Xw.A01` | Fallback. Habilitado por el flag 27083 | found |
| `165332417282214` | `C14080dr` (servidor `"lid"`) vía `AbstractC34361Xw.A02` | Contraparte LID de `…698` | found |
| `1807055946647696` | ninguna | Manus (legado en 2.26.26.4): **no presente** en 2.26.41.6 | found (ausente) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), más `A01` = `DeviceJid` dispositivo 0 | JID del servidor bot usado como destino de sesión/dispositivo para un "envoltorio de bot" (manejador de solicitud de sincronización CoEx v2 `C53148Nnt` cifra el payload de sincronización a su dispositivo primario, log `coexv2 attached bot envelope`), añadido a conjuntos de dispositivos destinatarios (`C12M`), y tratado como remitente bot en el manejo de recibos de reintento (`C33020EaI`). No es una persona de chat | found (uso); propósito más allá de eso inferido |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID del registro de perfil "Meta AI" por defecto incorporado (`C9i5.A00`: nombre `Meta AI`, texto de introducción por defecto). Miembro del test de JID de bot `AbstractC24760wu.A07` junto con la siguiente fila | found |
| `867051314767696555` | `AbstractC24760wu.A01` (conjunto singleton, `C24770wv`) | Segundo miembro del test `A07` de JID de bot (`A07(jid)` = `C24770wv` igual a `…135992` o en este conjunto); `A07` alimenta `AbstractC199328dk.A00` (un predicado de clase JID). Propósito adicional no resuelto | found (uso), propósito desconocido |
| `17015557208` | `AbstractC24760wu.A04` | Cadena de usuario de teléfono. `A04(jid)` es verdadero para el LID `165332417282214` o para este usuario de teléfono; usado junto con `A03` (cualquier JID de bot `C24770wv`, o PN en los rangos 13135550000-13135559999 / 13165550000-13165550099) en `E76.A00` (clase 10 vs 1) y en el predicado de elegibilidad `C736539v.ARO`. Se lee como la identidad PN de Meta AI; qué hacen esos dos consumidores con ella no está resuelto | found (uso), propósito desconocido |

Conjuntos en `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; mapa `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Tipo de JID: el informe de 2.26.26.4 listaba las cuatro como `@s.whatsapp.net`. En 2.26.41.6 los JIDs de bot son `C24770wv` con `getServer() = "bot"`; el de grupo/LID es `C14080dr` con servidor `"lid"`. No `s.whatsapp.net` (found).

Tabla de número de teléfono a FBID de bot: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, alrededor de 200 entradas, p. ej. `13135550002 → 867051314767696`). Usada por `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 Conversión de enrutamiento

```java
// AbstractC24760wu.A01  (getRemoteTargetJidForOutgoingMessage)
if (A08(jid))   // LID jid with user 165332417282214
    return new C24770wv("1807055946647698");
else            // phone jid
    return C0DZ.A08((UserJid) jid);   // PN -> bot JID via AbstractC199338dl table

// AbstractC24760wu.A00
if (jid is bot "1807055946647698") return new C14080dr("165332417282214");  // bot -> LID
if (jid is bot)                      return C0DZ.A07(userJid);              // bot -> phone jid
```

Found: JID de bot `…698` ↔ LID `165332417282214`; los contactos de bot con número de teléfono se mapean a JIDs de bot. El método afirma "needs FBID migration" (found).

### 2.3 El sufijo `$1`: cambiado

El informe de 2.26.26.4 colocaba `$1` en el JID de enrutamiento ("wire format", `C1A2.A00()/A01()`). No encontrado en 2.26.41.6:
- Ninguna función de enrutamiento añade `$1` a un JID. La conversión de 2.2 produce JIDs de bot simples.
- `$1` se añade a la cadena de ID de persona almacenada en el registro de perfil de bot: `C24121Ab2` hace `personaIdString = botFbid + "$1"`; `C223219iv` codifica `"1807055946647697$1"` para el perfil por defecto de Hatch (found).
- Esa cadena (`C199348dm.A0A`) es lo que `C33473Ehf.A0G` escribe en `BotMetadata.personaId` (found).

Entonces `$1` pertenece al ID de persona, no al JID de destino.

### 2.4 Detección de isMetaAI

```java
// C39311it
boolean A02() {                       // Hatch
  if (!BRD() || capability("ai_hatch_integration_enabled")) return flag(26189);
  return false;
}
boolean A0E(Jid jid) {
  if (jid == HATCH_697)                 return A02();
  if (jid == FALLBACK_698 || jid == LID_165332417282214) {
    if (!BRD() || capability("ai_maiba_wass_migration_receiving_enabled")) return flag(27083);
  }
  return false;
}
```

La rama de Manus (flag 25119) desapareció. El significado de `BRD()` y la búsqueda de capability (`C09L.A04`) no está resuelto (unknown).

---

## 3. Feature Flags

| ID de flag | Uso en 2.26.41.6 | Nivel |
|---------|------------------|------|
| **25119** | Aparece solo en tablas de flags (`C06510El`, por defecto `false` en `C08J`). No se encontró lector. El nombre antiguo `ai_bot_integration_enabled` no se encontró como cadena | found |
| **26189** | Gate de Hatch en `C39311it.A02()`. Por defecto `false` (`C08J`) | found |
| **27083** | Gate de Fallback / LID en `C39311it.A0E()`. Por defecto `false` | found |
| **26190** | Configuración JSON (`name`, `description`, `profile_thumb`) para el perfil de Hatch por defecto, leída en `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Cuando es verdadero, la capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) se anuncia a Hatch (ver 5); `A05` también habilita telemetría/UI del connector (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Anuncia `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); también habilita la disponibilidad del connector (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Anuncia `HATCH_ARTIFACT_CARD_ENABLED` (79); también leída por `HatchSpacesSync` y `C7WL` | found |

Las cadenas `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` no son nombres de flags. Son entradas de una lista de cadenas de funciones construida a partir de los flags 26189 / 27083 en `C25056AqU` (junto con `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` se añade incondicionalmente. El destinatario y el propósito de la lista no están verificados.

---

## 4. Campos proto

### 4.1 Message (`C30628DTw`) de nivel superior

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (campo único `message` = 1) | Mensaje saliente envuelto para el bot; fijado en `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Tarea de bot |
| `botForwardedMessage` | **104** | `BD2` | Envuelve un mensaje que contiene `richResponseMessage`; fijado en `F3E` |
| `richResponseMessage` | **97** | `DSY` | Respuesta de IA. Campos: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Presente |
| `botGroupParticipantMessage` | **137** | `BD2` | Presente |
| `messageContextInfo` | **35** | `C30624DTs` | Contiene `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Contiene `aiMetadataOperation` (31) |

El campo **77** es `commentMessage`, no `richResponseMessage` (el informe de 2.26.26.4 tenía 77; incorrecto para esta build, y consistente con la investigación separada de richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), no ContextInfo

El informe de 2.26.26.4 listaba estos como campos de ContextInfo. En 2.26.41.6 están en `WebMessageInfo`:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Fijado en `C34385EwW` a partir de `C0DZ.A09(userJid)` (usuario del dispositivo primario del invocador) |
| `isSupportAiMessage` | **70** | bool | Fijado en `C34378EwP.C57` cuando el mensaje tiene el bit de flag `268435456` y pasa una comprobación; leído de vuelta en `C59`. Junto con `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | mensaje repetido | Citas |
| `botTargetId` | **73** | string | Sin escritor en el cliente: `botTargetId_` aparece solo como valor por defecto del constructor y en la tabla de esquema de `C30626DTu`, nunca asignado en otro lugar (grep del código fuente completo) |
| `agentId` | **47** | string | Presente, no analizado |

Si y cómo estos campos de WebMessageInfo aparecen en el wire no está verificado (unknown). La afirmación "`true` para todos los mensajes de Meta AI" no se sostiene: se fija según el flag del mensaje, no de forma incondicional.

### 4.3 MessageContextInfo (`C30624DTs`)

| Campo | Número | Tipo |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `personaId` | **2** | string | Del registro de perfil de bot (`C199348dm.A0A`), p. ej. `1807055946647697$1`. No es un `"meta_ai"` fijo |
| `pluginMetadata` | **3** | `DTL` | Configuración de plugin |
| `invokerJid` | **5** | string | Invocador |
| `aiConversationContext` | **20** | bytes | Estado de la conversación |
| `botResponseId` | **26** | string | ID de respuesta |

Otros campos presentes (nombres de `*_FIELD_NUMBER`, tipos no leídos): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` se rellena en `C33473Ehf.A0G`; retorna temprano si el perfil no tiene cadena de persona.

### 4.5 PluginMetadata (`DTL`)

| Campo | Número | Tipo | Valor |
|-------|--------|------|-------|
| `provider` | **1** | int32 | ID de proveedor |
| `pluginType` | **2** | enum `C4E0` | Ver abajo |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

Constantes de `C4E0` (valor = ordinal del constructor; que sea igual al número proto es inferido): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Los valores antiguos 8/9/15 no cambiaron; el enum es más grande.

### 4.6 oneof de acción (`C61331Rfl`, enum de caso `EnumC61601RkN`)

| Número | Caso | Nivel |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Esto es un oneof de campos de acción, no un enum de valor simple. Dónde está embebido no se ha rastreado (unknown).

### 4.7 Operación de metadatos de IA (transporte de Hatch)

| Mensaje | Campo | Número | Tipo |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Protocolo de solicitud (metadatos Hatch)

Las solicitudes se construyen en `HF1` (`HatchMetadataRequestManager`), clase de corrutina `HatchMetadataRequestManager$sendRequest$2`. El envoltorio JSON difiere de 2.26.26.4: `method` y `params` están anidados bajo `payload`.

```json
{
  "version": 1,
  "type": "req",
  "payload": {
    "method": "<method_name>",
    "params": { },
    "accepts_encoding": ["gzip"]
  }
}
```

`params` y `accepts_encoding` son opcionales (found). El ID de la solicitud no está en el JSON; es `BB2.requestId` (una cadena aleatoria de `C20F.A0x()`).

Ruta de envío (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Solicitudes pendientes: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) y `HF1.A03` (requestId → `GuR`). Ambas se limpian en `finally`. El informe de 2.26.26.4 nombraba un solo mapa `A02`.
- Timeout: devuelve `GDB.A00` y registra `HatchMetadataRequestManager/sendRequest timed out method=`.
- El entero `138` pasado a `C37393GKy` no está resuelto (unknown).
- El transporte es `ProtocolMessage.aiMetadataOperation` (campo 31), no un mensaje de chat simple (cambiado).
- El paquete `com.whatsapp.bot.infra.message.aimetadata` contiene clases `Ideas*Wire` / `Idea*Wire` (found). Su relación con los nombres de método es solo inferida; los nombres de método no fueron enumerados.
- El lado de recepción que completa `A04` no fue rastreado. Hacer coincidir una respuesta con `requestId` se infiere del mapa `A04` y de `BB2.requestId`.

**Afirmación de "sin namespace XMPP personalizado"**: no se vio manejo de `w:ai` / `wa:ai` en la ruta rastreada; es una afirmación basada en ausencia, no reverificada exhaustivamente.

**Anuncio de capabilities (found, `C33284Eea`):** cuando el destino es el JID de Hatch `…697` (`AbstractC34361Xw.A00`) y un gate pasa, el cliente construye `DPJ` (campo único enum repetido `capabilities` = 1, valores `EnumC32144E2q`) y `C33473Ehf.A06` lo almacena en `BotMetadata.capabilityMetadata` (13) del mensaje saliente, junto con `BotMetadata.timezone` (8) = el ID de `TimeZone` del dispositivo. Capabilities añadidas por gate:

| Gate | Capability (número de enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Los números son el segundo argumento del constructor del enum; que sean iguales a los números proto es inferido. El enum también lista capabilities de respuesta enriquecida (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Ejemplos de solicitudes (found, claves de `params` leídas en los puntos de llamada; el destino es el JID de Hatch `…697` salvo que el punto de llamada use el JID de la conversación):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | construido en `HatchIdeasManager$execute$job$1` (claves no leídas); callback `onPart` adjuntado |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` serializado a JSON; callback `onPart` adjuntado |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` solo cuando no está vacío) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Forma de los bytes en `BB2.data` (forma found, valores de ejemplo):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` solo se escribe cuando el `acceptsGzipResponse` del llamador es verdadero; `params` solo cuando no es nulo. El callback `onPart` se registra en `A03` solo cuando el llamador pasa uno.

**Mensaje de chat al bot (partes found):**
- El `Message` saliente se vuelve a envolver en `Message.botInvokeMessage` (`F2K`, `C33284Eea`), el envoltorio `BD2` contiene el mensaje en el campo 1. En `F2K` el envoltorio se omite (el mensaje se fija directamente) cuando `C13S.A00()` es falso, el `A10` del mensaje es falso, o el flag **10646** está activo (found).
- `BotMetadata` se construye en `C33473Ehf.A0E` / `A0G`. `A0G` busca el registro de perfil para el JID de bot destino (`C199358dn.A06(userJid)`, cadena de persona `C199348dm.A0A`); si esa cadena está vacía el método retorna sin escribir metadatos de bot, en caso contrario fija `personaId` (2) y, cuando está presente, `suggestedPromptMetadata` (4) y otros submensajes. La cadena de persona se almacena cuando se crea el registro de perfil (`C24121Ab2` construye `<id>$1`; `C223219iv` codifica `1807055946647697$1` para Hatch). No se resolvió si `messageContextInfo` cae en el `Message` externo o en el mensaje dentro de `botInvokeMessage`.
- `botMessageInvokerJid` / `isSupportAiMessage` se fijan en `WebMessageInfo` mediante hooks D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Protocolo de respuesta

### 6.1 Transporte

No reverificado tal como se afirmaba en 2.26.26.4 ("mensajes normales con bytes de `hatchMetadataSync`", clase `Azz`). Found: `hatchMetadataSync` vive en `C25754B9o` dentro de `ProtocolMessage.aiMetadataOperation`. Las respuestas de Hatch presuntamente llegan por la misma vía y se emparejan por `requestId` (inferred). Las solicitudes de Hatch son llamadas a método; no se demuestra que sean la ruta de las respuestas de chat normales.

### 6.2 Streaming / fragmentos: no soportado como se describía

La tabla de 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) como un único mecanismo de streaming de Meta AI no se sostiene en 2.26.41.6:

| Campo | Dónde está en 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` campo **7** (notificación de sincronización de historial, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) y `C25838BCy` campo **5** (sincronización de historial) |
| `isLastChunk` | `C55285Ou6` campo **8** (mensaje con `attestationBundles`, `teeModelConfig`, `violationSignal`; relacionado con TEE) |
| `streamingSidecar` | campo **18** en mensajes de imagen/video/audio (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | no encontrados como campos proto |

No se encontró reensamblaje de fragmentos para respuestas de Meta AI. Lo que existe para Hatch: `GuR(method, onPart)` — un callback `onPart` por solicitud (found); que transporte resultados parciales es inferido a partir del nombre.

### 6.3 Respuesta enriquecida (campo 97)

`richResponseMessage` (`DSY`) = campo **97** en `Message`. Existen clases de renderizado: `AiRichResponseFooterView` y `UnifiedResponseActionHandlerFactory` (paquete `com.whatsapp.conversationrow.botrichresponse`) (found). Citas: `WebMessageInfo.supportAiCitations` (72). Los tipos de contenido (imágenes, tablas, código) no se reverificaron aquí; ver la investigación separada de richResponseMessage.

### 6.4 Indicador de escritura

Saliente (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): estado de chat XMPP estándar, sin namespace personalizado en el código leído.
- Caso simple (sin bot mencionado, o un JID de bot resuelto al por defecto): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot mencionado en el chat: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Enviado a través de `C10140Tq.A0X` con IQ-type int 4.

Entrante (found, manejador de stanza `C40511kx`): un `<chatstate>` con un hijo `composing` (opcional `media`) invoca el callback genérico de composing con `from`/`participant`; `paused` invoca el callback de paused. No se encontró ninguna rama específica de bot en este manejador, así que un `composing` de JID de bot sigue la misma ruta que cualquier contacto (inferred; no se observó un stanza de escritura de bot del lado del servidor). `BotMetadata.progressIndicatorMetadata` (12) y la capability `PROGRESS_INDICATOR` existen como un mecanismo de progreso en el mensaje separado (solo nombres, no rastreado).

### 6.5 Sincronización del perfil de bot

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) programa `BotProfileForChatListWorker` en `A03()`: una solicitud de WorkManager etiquetada `BotProfileSyncManager` con `setBackoffCriteria(policy, 1, MINUTES)` y una restricción (valor de tipo no resuelto). El 1 minuto es un **backoff** de reintento, no un período. El "cada ~1 minuto" de 2.26.26.4 no se sostiene (cambiado). `A02(groupJid, userJid)` solicita un único perfil (`requestBotProfileResult`). No forma parte de la sincronización normal de roster (sin cambios).

Registro de perfil `C199348dm`: tipo de bot (`C1XY`), jid, nombre visible (`A09`), descripción (`A07`), cadena de persona (`A0A`), miniaturas, timestamp.

### 6.6 Cadenas de tipo de bot

`C718732k.A00(String)` mapea: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; cualquier otra cosa se convierte en `AnonymousClass399(str)`. Son etiquetas de tipo de bot (también usadas en filtros de UI), no valores de `BotMetadata.personaId` (found).

---

## 7. Almacenamiento

- `MetaAiMemoryStore`: no existe clase con ese nombre en 2.26.41.6. El equivalente encontrado es una tabla `meta_ai_memory` creada por la clase de esquema `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, índice `meta_ai_memory_memory_content_index` sobre `memory_content`. Qué archivo de base de datos la contiene no está resuelto. Relacionado (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; el nombre dice "deprecated"), SharedPrefs `meta_ai_memory_disclosure_seen` (pantalla de diseño de llamada de voz, `C29434Cpx`), enums de capability `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), y `BotMetadata.memoryMetadata` (15).
- Clave SharedPrefs `"meta_ai_forward_disclosure_seen"`: presente, booleana, leída en `C230589xr.A03` para `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: presente en `com.whatsapp.metaai.incognito.infra` (found).
- Almacenamiento separado de chats de Meta AI fuera de `msgstore.db` (2.26.26.4, no reverificado): no se encontró clase de almacén de chat; `meta_ai_memory` contiene solo hechos de memoria, así que la afirmación no se sostiene ni se refuta.

---

## 8. Por qué Baileys no obtiene respuesta

Todas las filas son **inferred**: comparación estática de los requisitos del cliente con una ruta de envío de terceros; sin prueba en vivo.

| Problema | Base en 2.26.41.6 | Nivel |
|-------|--------------------|------|
| Tipo de JID de destino incorrecto | Los JIDs de bot usan el servidor `bot` (`C24770wv`), no `s.whatsapp.net`; los bots con número de teléfono se mapean mediante una tabla PN→FBID | found (clase JID), inferred (efecto) |
| `$1` en el JID de enrutamiento | No está presente. `$1` está en la cadena de ID de persona | found |
| Falta el envoltorio `botInvokeMessage` | El cliente envuelve el `Message` saliente en el campo 67 (`F2K`) | found, requisito inferido |
| Falta `messageContextInfo.botMetadata` | El cliente escribe `personaId`, `invokerJid`, etc. en él | found, requisito inferido |
| `personaId = "meta_ai"` | No es lo que envía el cliente; envía la cadena de persona del perfil (p. ej. `1807055946647697$1`) | found |
| Falta `aiConversationContext` | Campo 20 de `BotMetadata`; comportamiento en el primer turno desconocido | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Campos de WebMessageInfo fijados por hooks del cliente; requisito del servidor desconocido | unknown |
| `botTargetId` | Sin escritor en el código del cliente | found |
| Respuesta no analizada | `richResponseMessage` es el campo 97 de `Message` | found |
| Reensamblaje de fragmentos | No soportado según la evidencia de 2.26.41.6 (ver 6.2) | found |

---

## 9. Verificación de firma de bot (autenticidad de contenido)

Separado de todo lo anterior: un mecanismo que permite al cliente **receptor** verificar que el contenido de `richResponseMessage` provino genuinamente del backend de IA de Meta, independientemente de quién retransmitió el mensaje. Los hallazgos estáticos a continuación son `found` en el código de 2.26.41.6; el resultado de la repetición en 9.4 es `tested` (en vivo, en la propia cuenta del autor — no interceptación de tráfico, un cliente legítimo que compone y retransmite su propio mensaje).

### 9.1 Ubicación en el proto

`BotMetadata.verificationMetadata` — campo **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), tipo `DPC`/`BotSignatureVerificationMetadata` (el toString revela el nombre real): `proofs[]`, cada una un `BotSignatureVerificationUseCaseProof` con `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (bytes repetidos, X.509 DER).

### 9.2 Algoritmo de verificación

Clase `C33259EeB`, nombre interno `BotSignatureVerificationUtils` (según cadenas de log):

1. **Validación de la cadena de certificados** de `certificateChain` contra un ancla de confianza, vía `HFg.A01(date, certs, true)`.
2. **Construcción de los bytes firmados**: `"1" + <cadena de número de teléfono> + <bytes de unifiedResponse>` — la firma vincula **contenido y número de teléfono juntos**, no solo el contenido.
3. **Verificación EdDSA** (log: `"EdDSA signature verification result"`) usando la clave Ed25519 en bruto extraída del SubjectPublicKeyInfo del certificado hoja.
4. **Modo de aplicación**, leído de la configuración **19590**, enum `EnumC32057Dzg`: `NONE` (`"none"`, deshabilitado, siempre pasa), `LOG_ONLY` (`"log_only"`, verifica y registra, nunca bloquea), `ENFORCE_BLOCKING` (`"enforce_blocking"`, una comprobación fallida devuelve `false`). El resultado se almacena como `E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, persistido en la columna SQLite `bot_message_info.signature_validation_status` (la tabla también tiene `bot_client_public_key`).

### 9.3 Compuerta de renderizado de fila

`C30085D6v.A00` (despachador de tipo de fila) y `EOK`/`C32608EKo`: si el estado de la firma es `FAILED` y el flag **27635** está activo → fila enmascarada `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). De forma independiente, si el JID del remitente no está presente en el almacén de perfiles de bot sincronizado localmente (`C224899mg`, la misma sincronización que `BotProfileSyncManagerImpl`) y el flag **27355** está activo → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), una vista previa con compuerta de consentimiento en lugar de un bloqueo duro.

### 9.4 Captura real y repetición en vivo (tested)

Una respuesta genuina de Meta AI, capturada del lado del cliente en una conversación real (cuenta propia, descifrada por el propio cliente del autor — no interceptación de tráfico), contenía:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, una `signature` de 64 bytes (tamaño Ed25519), un `certificateChain` de 2 entradas.
- Certificado hoja: `CN=svc:wa-bot-msg-leaf`, clave Ed25519, emitido por `Meta WA SS Int CA 2025-09`, encadenando a `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`), validez de aproximadamente 7 meses (certificado de servicio rotado automáticamente) — la clave privada de firma solo existe en el backend de Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — un nombre de backend de bot no documentado previamente (ver también "Hatch" en las secciones 1-6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, un campo hermano de `botMetadata`.
- Forma de entrega: `protocolMessage` con `type: MESSAGE_EDIT`, `editedMessage.richResponseMessage` (la primera respuesta en un hilo llega preenvuelta como una edición de un marcador de posición), `key.remoteJid` = el propio JID del autor.

**Prueba:** el `richResponseMessage` exacto + `messageContextInfo.botMetadata` (firma y cadena de certificados byte por byte sin cambios) se retransmitió vía `relayMessage` desde el propio dispositivo del autor — no el JID de bot `867051314767696@bot` — hacia el propio número del autor (el mismo número ya embebido en los bytes firmados).

**Resultado:** el contenido se renderizó con el estilo "IA" completo y el texto real, etiquetado "Forwarded". Algunas entregas de la misma carga útil mostraron en cambio "WhatsApp can't verify the security of this media. Only download if you trust the sender." con una acción de Download; al pulsar Download se revelaba el contenido idéntico, lo cual coincide con el estado `DOWNLOAD_CONSENT_ACCEPTED` y la ruta de código "unknown sender with unconsented content" de 9.3. Una entrega mostró en su lugar un fallback genérico de "your version of WhatsApp doesn't support it"; la causa no se estableció (unknown).

**Conclusión (tested):** la comprobación criptográfica de 9.2 vincula el *(contenido, número de teléfono)*, no la identidad o el JID del remitente en vivo. Un `richResponseMessage` válidamente firmado puede repetirse desde un remitente que no es el bot y aún pasar la verificación de firma, siempre que el número del destinatario coincida con el número incorporado en la firma — el cliente receptor lo renderiza como contenido de IA genuino (como máximo con una compuerta de un solo toque, un paso de consentimiento cosmético de "remitente desconocido", no un bloqueo duro). Este es un mecanismo de autenticidad de contenido, no de autenticidad de remitente; es el propio cifrado de la capa Signal de WhatsApp, no esta firma, lo que autentica al remitente en vivo.

---

## 10. Solución para Baileys

No se afirma una implementación funcional. Lo que sigue es un bosquejo estructural de dónde viven los campos según 2.26.41.6, marcado como **inferred**; no se ha ejecutado contra un servidor.

### 9.1 Destino

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Si la cadena del servidor `bot` funciona como destino de retransmisión de Baileys, y cómo deriva el servidor el `to` final del stanza, es desconocido.

### 9.2 Ubicación de campos (solo la forma)

```ts
// inferred shape, field numbers found in 2.26.41.6
const content = {
  botInvokeMessage: {            // Message 67, wrapper with message = 1 (found; wrap is conditional, see 5)
    message: {
      extendedTextMessage: { text }
    }
  },
  // Placement of messageContextInfo (outer Message vs. inner message) is unresolved.
  messageContextInfo: {          // Message 35
    botMetadata: {               // MessageContextInfo 7
      personaId: '1807055946647697$1', // BotMetadata 2: profile persona string (found in C223219iv for Hatch)
      invokerJid: yourJid,             // BotMetadata 5: field exists; writer not read
      timezone: 'Europe/Berlin',       // BotMetadata 8: client sets the TimeZone ID when advertising capabilities (Hatch)
      capabilityMetadata: { capabilities: [/* EnumC32144E2q numbers, Hatch only */] } // BotMetadata 13
      // aiConversationContext (20): field exists; client write not traced, do not invent a value
    }
  }
}
```

- La incrustación de `botMetadata` en `messageContextInfo` (campo 7) es **found**. `capabilityMetadata` (13) y `timezone` (8) son escritos por el cliente solo para destinos Hatch (found); su requisito del lado del servidor es desconocido. No se comprobó si el proto de `baron-baileys-v2` ya tiene estos campos; si no, el proto debe extenderse (inferred).
- `isSupportAiMessage` (70) y `botMessageInvokerJid` (58) son campos de `WebMessageInfo`. Si deben estar presentes en el wire es desconocido; no los pongas en `contextInfo` (eso era incorrecto en el informe de 2.26.26.4).
- `botTargetId`: sin escritor del cliente en ninguna parte del código decompilado (found); no lo fijes.
- Envoltorio exacto (`botInvokeMessage.message` conteniendo el mensaje real frente a estar al lado) sigue el reenvoltorio de `F2K` / `C33284Eea`; el resultado serializado exacto no se reprodujo (unknown).

### 9.3 Manejo de la respuesta

- Respuestas enriquecidas: `Message.richResponseMessage` es el campo **97** (found). Analiza eso, no el campo 77.
- Elimina el manejo de fragmentos: `chunkOrder` / `isLastChunk` no son campos de streaming de Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) de Hatch es el canal de solicitud JSON; no se demuestra que las respuestas de chat simples lo usen.

### 9.4 Contexto de conversación

`BotMetadata.aiConversationContext` (20) existe. Que el servidor devuelva el estado actualizado en las respuestas y que deba ser reflejado de vuelta es **inferred** (del nombre del campo y del informe de 2.26.26.4); no verificado.

---

## 11. Flujos

### 10.1 Mensaje de chat al bot (found del lado del cliente, inferred del lado del servidor)

```
[Client] outgoing Message
    │  F2K / C33284Eea: Message.botInvokeMessage = BD2{ message = original }
    │  C33473Ehf: messageContextInfo.botMetadata{ personaId = profile.A0A, ... }
    │  D36 hooks: WebMessageInfo.botMessageInvokerJid (58), isSupportAiMessage (70)
    ▼
[Routing] AbstractC24760wu.A01: LID 165332417282214 → bot 1807055946647698
    │  phone JID → bot JID via PN→FBID table
    ▼
[WA Server] (not observed; inferred) → Meta AI backend
    ▼
[Client] incoming Message.richResponseMessage (97)  →  AiRichResponseFooterView / UnifiedResponseActionHandlerFactory
```

### 10.2 Solicitud de metadatos Hatch (found del lado del cliente)

```
[Feature code] HF1.A01(jid, method, params)
    │  requestId = random; A03[requestId] = GuR(method, onPart); A04[requestId] = continuation
    ▼
JSON {"version":1,"type":"req","payload":{"method","params","accepts_encoding"}} → bytes
    ▼
Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
    ▼
[WA Server] (not observed)
    ▼
Response: matched by requestId (inferred) → continuation resumes; timeout → GDB.A00
```

---

## 12. Cambios frente a 2.26.26.4

| Elemento | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legado, flag 25119 | No presente. 25119 solo en tablas de flags, sin lector |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 son servidor `bot` (`C24770wv`); 165332417282214 es `lid` (`C14080dr`) |
| Nuevas constantes de JID | ninguna listada | `1807055946647699` (envoltorio de bot CoEx v2 / destino de conjunto de dispositivos), `2942131436135992` (JID de perfil de Meta AI por defecto, test de JID de bot `A07`), `867051314767696555` (segundo miembro de `A07`, propósito desconocido), `17015557208` (PN de Meta AI, `A04`) |
| Sufijo `$1` | En el JID de enrutamiento, `C1A2.A00/A01` | No en el JID; añadido a la cadena de ID de persona (`C24121Ab2`, `C223219iv`) |
| Conversión de enrutamiento | adición de `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot vía tabla FBID |
| Nombres de flags 25119/26189/27083 | nombres de flag `ai_*` | Las cadenas son entradas de lista de funciones (`C25056AqU`); 26190 = JSON de perfil de Hatch; 37227/37852/37054 habilitan valores de capability de Hatch 76 / 77 / 79 |
| `richResponseMessage` | Campo 77 | Campo 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 en "WebMessageInfo" | 67 / 100 / 104 en `Message`; también 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nunca escrito |
| Ubicación de BotMetadata | "embebido en el mensaje" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Cadena de persona del perfil, p. ej. `1807055946647697$1`; `meta_ai` es una etiqueta de tipo de bot |
| Tipos de plugin | 8, 9, 15 | Iguales, el enum tiene 18 valores (hasta 17) |
| Enum de acción | Enum de valor 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Envoltorio JSON de Hatch | `method`, `params` de nivel superior | Anidados bajo `payload`; añade `accepts_encoding` |
| Transporte de Hatch | Mensaje estándar, clase `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; añade `bizAiMetadataSync` (2) |
| Verificación de firma de bot | no documentada | Nuevo: `BotMetadata.verificationMetadata` (27), EdDSA + cadena de certificados X.509 sobre (contenido, número de teléfono); probado en vivo, vincula al número de teléfono, no al remitente en vivo (sección 9) |
| Mapas de pendientes | Uno (`A02`) | Dos: continuaciones `A04`, callbacks de parte `GuR` `A03` |
| Campos de streaming | Una tabla de fragmentos de Meta AI | `chunkOrder` (sincronización de historial), `isLastChunk` (mensaje TEE), `streamingSidecar` (medios); `clientStreaming`/`serverStreaming` no encontrados |
| Intervalo de sincronización de perfil | "cada ~1 min" | 1 min es el backoff de WorkManager, no un período |
| `MetaAiMemoryStore` | Presente | No encontrado por nombre; tabla `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) encontrada |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Presente | Presente |
| Indicador de escritura (chatstates) | Encontrado | Encontrado: saliente `<chatstate><composing/></chatstate>`, con `<bot jid/>` cuando se menciona un bot (`C199098dN.A01`); entrante `composing`/`paused` vía manejador genérico `C40511kx`, sin rama específica de bot |
| Anuncio de capabilities | no documentado | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) para Hatch; los flags 37227 / 37852 / 37054 mapean a valores de enum 76 / 77 / 79 |
| Ejemplos de solicitudes Hatch | no documentado | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
</content>
</invoke>
