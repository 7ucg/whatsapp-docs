<!-- src-sha1: 64389e16d6c478a5b57f43abf9ee01a01474f02f -->
# WhatsApp Meta AI — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** Internos de Meta AI — JIDs, enrutamiento, campos proto, solicitudes de metadatos Hatch, renderizado de respuestas, por qué falla Baileys, solución

---

## 1. Qué es Meta AI (técnicamente)

Meta AI es un contacto bot direccionado mediante JIDs de bot especiales (servidor `bot`), con campos proto específicos de bot en los tipos de mensaje normales y un canal de solicitudes JSON separado ("Hatch metadata") transportado en un `ProtocolMessage`. Todas las afirmaciones provienen de análisis estático del APK decompilado. Nivel: **found** = leído en el código, **inferred** = deducido del código, **unknown** = no resuelto.

Los nombres de este informe que estaban ofuscados en 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) se re-resolvieron a partir de anclas estables; no existen con esos nombres en 2.26.41.6.

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| BotJid | `C24770wv` | Clase JID, servidor `"bot"`, tipo 26, cadena numérica de 1-20 caracteres, sin 0 inicial |
| Constantes de JID de bot | `AbstractC34361Xw` | Constantes y conjuntos de Hatch / Fallback / LID |
| Mapeo de JID | `AbstractC24760wu` | mapeo bot ↔ LID, conversión del destino saliente |
| Gating | `C39311it` | gating por feature flag para cada JID (`A0E(Jid)`) |
| Gestor de solicitudes Hatch | `HF1` (`HatchMetadataRequestManager`) | solicitudes JSON, mapa de pendientes |
| Constructor proto de Hatch | `Hf6` | construye `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | contiene `botMetadata` |
| BotMetadata | `C30615DTj` | metadatos de bot por mensaje |
| Registro de perfil de bot | `C199348dm` | nombre, descripción, cadena de ID de persona, miniatura |

---

## 2. JIDs de Meta AI

### 2.1 JIDs encontrados en el código

| Constante | Clase | Rol | Nivel |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) mediante `AbstractC34361Xw.A00` | **Hatch**, primario. Perfil por defecto construido en `C223219iv` a partir del payload del flag **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) mediante `AbstractC34361Xw.A01` | Fallback. Controlado por el flag 27083 | found |
| `165332417282214` | `C14080dr` (servidor `"lid"`) mediante `AbstractC34361Xw.A02` | Contraparte LID de `…698` | found |
| `1807055946647696` | ninguna | Manus (heredado en 2.26.26.4): **no presente** en 2.26.41.6 | found (absent) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), más `A01` = `DeviceJid` dispositivo 0 | JID de servidor de bot usado como destino de sesión/dispositivo para un "bot envelope" (el handler de solicitud de sync CoEx v2 `C53148Nnt` cifra el payload de sync hacia su dispositivo primario, log `coexv2 attached bot envelope`), agregado a los conjuntos de dispositivos de destinatarios (`C12M`), y tratado como remitente bot en el manejo de retry-receipt (`C33020EaI`). No es una persona de chat | found (uso); propósito más allá de eso inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID del registro de perfil "Meta AI" por defecto incorporado (`C9i5.A00`: nombre `Meta AI`, texto de introducción por defecto). Miembro de la prueba de JID de bot `AbstractC24760wu.A07` junto con la fila siguiente | found |
| `867051314767696555` | `AbstractC24760wu.A01` (conjunto unitario, `C24770wv`) | Segundo miembro de la prueba de JID de bot `A07` (`A07(jid)` = `C24770wv` igual a `…135992` o en este conjunto); `A07` alimenta `AbstractC199328dk.A00` (un predicado de clase JID). Propósito adicional no resuelto | found (uso), propósito unknown |
| `17015557208` | `AbstractC24760wu.A04` | Cadena de usuario de teléfono. `A04(jid)` es true para el LID `165332417282214` o para este usuario de teléfono; usado con `A03` (cualquier JID de bot `C24770wv`, o PN en los rangos 13135550000-13135559999 / 13165550000-13165550099) en `E76.A00` (clase 10 vs 1) y en el predicado de elegibilidad `C736539v.ARO`. Se lee como la identidad PN de Meta AI; lo que hacen esos dos consumidores con ella no está resuelto | found (uso), propósito unknown |

Conjuntos en `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; mapa `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Tipo de JID: el informe de 2.26.26.4 listaba los cuatro como `@s.whatsapp.net`. En 2.26.41.6 los JIDs de bot son `C24770wv` con `getServer() = "bot"`; el de grupo/LID es `C14080dr` con servidor `"lid"`. No `s.whatsapp.net` (found).

Tabla de número de teléfono a FBID de bot: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, unas 200 entradas, p. ej. `13135550002 → 867051314767696`). Usada por `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

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

Found: JID de bot `…698` ↔ LID `165332417282214`; los contactos bot de número de teléfono se mapean a JIDs de bot. El método afirma "needs FBID migration" (found).

### 2.3 El sufijo `$1`: cambiado

El informe de 2.26.26.4 colocaba `$1` en el JID de enrutamiento ("wire format", `C1A2.A00()/A01()`). No se encontró en 2.26.41.6:
- Ninguna función de enrutamiento agrega `$1` a un JID. La conversión de 2.2 produce JIDs de bot simples.
- `$1` se agrega a la cadena de ID de persona almacenada en el registro de perfil de bot: `C24121Ab2` hace `personaIdString = botFbid + "$1"`; `C223219iv` fija `"1807055946647697$1"` para el perfil por defecto de Hatch (found).
- Esa cadena (`C199348dm.A0A`) es la que `C33473Ehf.A0G` escribe en `BotMetadata.personaId` (found).

Por lo tanto `$1` pertenece al ID de persona, no al JID de destino.

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

La rama Manus (flag 25119) ya no existe. El significado de `BRD()` y de la búsqueda de capability (`C09L.A04`) no está resuelto (unknown).

---

## 3. Feature Flags

| ID del flag | Uso en 2.26.41.6 | Nivel |
|---------|------------------|------|
| **25119** | Aparece solo en tablas de flags (`C06510El`, por defecto `false` en `C08J`). No se encontró lector. El nombre antiguo `ai_bot_integration_enabled` no se encontró como cadena | found |
| **26189** | Gate de Hatch en `C39311it.A02()`. Por defecto `false` (`C08J`) | found |
| **27083** | Gate de Fallback / LID en `C39311it.A0E()`. Por defecto `false` | found |
| **26190** | Config JSON (`name`, `description`, `profile_thumb`) para el perfil Hatch por defecto, leída en `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Cuando es true, la capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) se anuncia a Hatch (ver 5); `A05` también controla la telemetría/UI de conectores (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Anuncia `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); también controla la disponibilidad de conectores (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Anuncia `HATCH_ARTIFACT_CARD_ENABLED` (79); también leído por `HatchSpacesSync` y `C7WL` | found |

Las cadenas `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` no son nombres de flags. Son entradas de una lista de feature-strings construida a partir de los flags 26189 / 27083 en `C25056AqU` (junto con `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` se agrega incondicionalmente. Destinatario y propósito de la lista no verificados.

---

## 4. Campos proto

### 4.1 Message (`C30628DTw`) de nivel superior

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (campo único `message` = 1) | Mensaje saliente envuelto para el bot; establecido en `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Tarea del bot |
| `botForwardedMessage` | **104** | `BD2` | Envuelve un mensaje que contiene `richResponseMessage`; establecido en `F3E` |
| `richResponseMessage` | **97** | `DSY` | Respuesta de IA. Campos: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Presente |
| `botGroupParticipantMessage` | **137** | `BD2` | Presente |
| `messageContextInfo` | **35** | `C30624DTs` | Lleva `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Lleva `aiMetadataOperation` (31) |

El campo **77** es `commentMessage`, no `richResponseMessage` (el informe de 2.26.26.4 tenía 77; incorrecto para este build, y consistente con la investigación separada de richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), no ContextInfo

El informe de 2.26.26.4 listaba estos como campos de ContextInfo. En 2.26.41.6 están en `WebMessageInfo`:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Establecido en `C34385EwW` desde `C0DZ.A09(userJid)` (usuario del dispositivo primario del invocador) |
| `isSupportAiMessage` | **70** | bool | Establecido en `C34378EwP.C57` cuando el mensaje tiene el bit de flag `268435456` y pasa una verificación; leído de vuelta en `C59`. Junto con `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Citas |
| `botTargetId` | **73** | string | Sin escritor en el cliente: `botTargetId_` aparece solo como valor por defecto del constructor y en la tabla de esquema de `C30626DTu`, nunca asignado en otro lugar (grep de código fuente completo) |
| `agentId` | **47** | string | Presente, no analizado |

Si estos campos de WebMessageInfo aparecen en el wire, y cómo, no está verificado (unknown). "`true` para todos los mensajes de Meta AI" no está respaldado: se establece por flag de mensaje, no incondicionalmente.

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
| `pluginMetadata` | **3** | `DTL` | Config de plugin |
| `invokerJid` | **5** | string | Invocador |
| `aiConversationContext` | **20** | bytes | Estado de la conversación |
| `botResponseId` | **26** | string | ID de respuesta |

Otros campos presentes (nombres de `*_FIELD_NUMBER`, tipos no leídos): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` se rellena en `C33473Ehf.A0G`; retorna antes si el perfil no tiene cadena de persona.

### 4.5 PluginMetadata (`DTL`)

| Campo | Número | Tipo | Valor |
|-------|--------|------|-------|
| `provider` | **1** | int32 | ID del proveedor |
| `pluginType` | **2** | enum `C4E0` | Ver abajo |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

Constantes de `C4E0` (valor = ordinal del constructor; que sea igual al número proto es inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Los valores antiguos 8/9/15 no cambian; el enum es más grande.

### 4.6 Action oneof (`C61331Rfl`, enum de casos `EnumC61601RkN`)

| Número | Caso | Nivel |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Es un oneof de campos de acción, no un enum de valores simple. Dónde está embebido no se trazó (unknown).

### 4.7 Operación de metadatos de IA (portador de Hatch)

| Mensaje | Campo | Número | Tipo |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Protocolo de solicitud (Hatch metadata)

Las solicitudes las construye `HF1` (`HatchMetadataRequestManager`), clase de corrutina `HatchMetadataRequestManager$sendRequest$2`. El envelope JSON difiere de 2.26.26.4: `method` y `params` están anidados bajo `payload`.

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

`params` y `accepts_encoding` son opcionales (found). El ID de solicitud no está en el JSON; es `BB2.requestId` (una cadena aleatoria de `C20F.A0x()`).

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

- Solicitudes pendientes: `HF1.A04` (`ConcurrentHashMap`, requestId → continuación) y `HF1.A03` (requestId → `GuR`). Ambos se limpian en `finally`. El informe de 2.26.26.4 nombraba solo un mapa `A02`.
- Timeout: retorna `GDB.A00` y registra `HatchMetadataRequestManager/sendRequest timed out method=`.
- El entero `138` pasado a `C37393GKy` no está resuelto (unknown).
- El portador es `ProtocolMessage.aiMetadataOperation` (campo 31), no un mensaje de chat simple (cambiado).
- El paquete `com.whatsapp.bot.infra.message.aimetadata` contiene clases `Ideas*Wire` / `Idea*Wire` (found). Su relación con los nombres de método es solo inferred; los nombres de método no fueron enumerados.
- El lado de recepción que completa `A04` no se trazó. Que la respuesta se asocie con `requestId` es inferred a partir del mapa `A04` y de `BB2.requestId`.

**Sin namespace XMPP personalizado**: no se vio manejo de `w:ai` / `wa:ai` en la ruta trazada; basado en ausencia, no re-verificado exhaustivamente.

**Anuncio de capabilities (found, `C33284Eea`):** cuando el destino es el JID de Hatch `…697` (`AbstractC34361Xw.A00`) y pasa un gate, el cliente construye `DPJ` (campo enum repetido único `capabilities` = 1, valores `EnumC32144E2q`) y `C33473Ehf.A06` lo almacena en `BotMetadata.capabilityMetadata` (13) del mensaje saliente, junto con `BotMetadata.timezone` (8) = el ID de `TimeZone` del dispositivo. Capabilities agregadas por gate:

| Gate | Capability (número del enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Los números son el segundo argumento del constructor del enum; que sean iguales a los números proto es inferred. El enum también lista capabilities de respuesta rica (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Ejemplos de solicitud (found, claves de `params` leídas en los puntos de llamada; el destino es el JID de Hatch `…697` salvo que el punto de llamada use el JID de la conversación):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | construido en `HatchIdeasManager$execute$job$1` (claves no leídas); callback `onPart` adjunto |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` serializado a JSON; callback `onPart` adjunto |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` solo cuando no está vacío) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Forma de los bytes en `BB2.data` (forma found, valores de ejemplo):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` se escribe solo cuando `acceptsGzipResponse` del llamador es true; `params` solo cuando no es null. El callback `onPart` se registra en `A03` solo cuando el llamador pasa uno.

**Mensaje de chat al bot (partes found):**
- El `Message` saliente se re-envuelve en `Message.botInvokeMessage` (`F2K`, `C33284Eea`), con el wrapper `BD2` conteniendo el mensaje en el campo 1. En `F2K` el wrap se omite (mensaje establecido directamente) cuando `C13S.A00()` es false, el `A10` del mensaje es false, o el flag **10646** está activo (found).
- `BotMetadata` lo construye `C33473Ehf.A0E` / `A0G`. `A0G` busca el registro de perfil para el JID de bot destino (`C199358dn.A06(userJid)`, cadena de persona `C199348dm.A0A`); si esa cadena está vacía el método retorna sin escribir metadatos de bot, de lo contrario establece `personaId` (2) y, cuando está presente, `suggestedPromptMetadata` (4) y más submensajes. La cadena de persona se almacena cuando se crea el registro de perfil (`C24121Ab2` construye `<id>$1`; `C223219iv` fija `1807055946647697$1` para Hatch). Si `messageContextInfo` queda en el `Message` exterior o en el mensaje dentro de `botInvokeMessage` no se resolvió.
- `botMessageInvokerJid` / `isSupportAiMessage` se establecen en `WebMessageInfo` mediante hooks D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Protocolo de respuesta

### 6.1 Transporte

No re-verificado tal como se indicaba en 2.26.26.4 ("normal messages with `hatchMetadataSync` bytes", clase `Azz`). Found: `hatchMetadataSync` vive en `C25754B9o` dentro de `ProtocolMessage.aiMetadataOperation`. Las respuestas de Hatch presumiblemente llegan de la misma forma y se asocian por `requestId` (inferred). Las solicitudes de Hatch son llamadas a métodos; no se demuestra que sean la ruta de las respuestas de chat normales.

### 6.2 Streaming / chunks: no respaldado como se describía

La tabla de 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) como un único mecanismo de streaming de Meta AI no está respaldada en 2.26.41.6:

| Campo | Dónde está en 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` campo **7** (notificación de history-sync, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) y `C25838BCy` campo **5** (history sync) |
| `isLastChunk` | `C55285Ou6` campo **8** (mensaje con `attestationBundles`, `teeModelConfig`, `violationSignal`; relacionado con TEE) |
| `streamingSidecar` | campo **18** en mensajes de imagen/video/audio (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | no encontrados como campos proto |

No se encontró reensamblado de chunks de respuestas de Meta AI. Lo que existe para Hatch: `GuR(method, onPart)` — un callback `onPart` por solicitud (found); que transporte resultados parciales es inferred a partir del nombre.

### 6.3 Respuesta rica (campo 97)

`richResponseMessage` (`DSY`) = campo **97** en `Message`. Existen clases de renderizado: `AiRichResponseFooterView` y `UnifiedResponseActionHandlerFactory` (paquete `com.whatsapp.conversationrow.botrichresponse`) (found). Citas: `WebMessageInfo.supportAiCitations` (72). Los tipos de contenido (imágenes, tablas, código) no se re-verificaron aquí; ver la investigación separada de richResponseMessage.

### 6.4 Indicador de escritura

Saliente (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): chat state XMPP estándar, sin namespace personalizado en el código leído.
- Caso simple (sin bot mencionado, o un JID de bot resuelto al por defecto): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot mencionado en el chat: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Enviado mediante `C10140Tq.A0X` con IQ-type int 4.

Entrante (found, handler de stanza `C40511kx`): un `<chatstate>` con hijo `composing` (`media` opcional) invoca el callback genérico de composing con `from`/`participant`; `paused` invoca el callback de paused. No se encontró ninguna rama específica de bot en este handler, por lo que un `composing` de un JID de bot sigue la misma ruta que cualquier contacto (inferred; no se observó una stanza de escritura de bot del lado del servidor). `BotMetadata.progressIndicatorMetadata` (12) y la capability `PROGRESS_INDICATOR` existen como un mecanismo de progreso dentro del mensaje separado (solo nombres, no trazado).

### 6.5 Sincronización del perfil del bot

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) programa `BotProfileForChatListWorker` en `A03()`: una solicitud de WorkManager con tag `BotProfileSyncManager` con `setBackoffCriteria(policy, 1, MINUTES)` y una restricción (valor del tipo no resuelto). El minuto es un **backoff** de reintento, no un período. El "every ~1 minute" de 2.26.26.4 no está respaldado (cambiado). `A02(groupJid, userJid)` solicita un único perfil (`requestBotProfileResult`). No forma parte de la sincronización normal del roster (sin cambios).

Registro de perfil `C199348dm`: tipo de bot (`C1XY`), jid, nombre para mostrar (`A09`), descripción (`A07`), cadena de persona (`A0A`), miniaturas, marca de tiempo.

### 6.6 Cadenas de tipo de bot

`C718732k.A00(String)` mapea: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; cualquier otra cosa se convierte en `AnonymousClass399(str)`. Son etiquetas de tipo de bot (también usadas en filtros de UI), no valores de `BotMetadata.personaId` (found).

---

## 7. Almacenamiento

- `MetaAiMemoryStore`: no existe una clase con ese nombre en 2.26.41.6. El equivalente encontrado es una tabla `meta_ai_memory` creada por la clase de esquema `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, índice `meta_ai_memory_memory_content_index` sobre `memory_content`. No está resuelto qué archivo de base de datos la contiene. Relacionado (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; el nombre dice deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (pantalla de diseño de llamada de voz, `C29434Cpx`), enums de capability `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), y `BotMetadata.memoryMetadata` (15).
- Clave de SharedPrefs `"meta_ai_forward_disclosure_seen"`: presente, booleana, leída en `C230589xr.A03` para `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: presente en `com.whatsapp.metaai.incognito.infra` (found).
- Almacenamiento separado de los chats de Meta AI fuera de `msgstore.db` (2.26.26.4, no re-verificado): no se encontró clase de almacenamiento de chats; `meta_ai_memory` contiene solo hechos de memoria, por lo que la afirmación no está ni respaldada ni refutada.

---

## 8. Por qué Baileys no obtiene respuesta

Todas las filas son **inferred**: comparación estática de los requisitos del cliente con una ruta de envío de terceros; sin prueba en vivo.

| Problema | Base en 2.26.41.6 | Nivel |
|-------|--------------------|------|
| Tipo de JID de destino incorrecto | Los JIDs de bot usan el servidor `bot` (`C24770wv`), no `s.whatsapp.net`; los bots de número de teléfono se mapean mediante una tabla PN→FBID | found (clase JID), inferred (efecto) |
| `$1` en el JID de enrutamiento | No presente. `$1` está en la cadena de ID de persona | found |
| Falta el wrapper `botInvokeMessage` | El cliente envuelve el `Message` saliente en el campo 67 (`F2K`) | found, requisito inferred |
| Falta `messageContextInfo.botMetadata` | El cliente escribe en él `personaId`, `invokerJid`, etc. | found, requisito inferred |
| `personaId = "meta_ai"` | No es lo que envía el cliente; envía la cadena de persona del perfil (p. ej. `1807055946647697$1`) | found |
| Falta `aiConversationContext` | Campo 20 de `BotMetadata`; comportamiento en el primer turno unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Campos de WebMessageInfo establecidos por hooks del cliente; requisito del servidor unknown | unknown |
| `botTargetId` | Sin escritor en el código del cliente | found |
| Respuesta no parseada | `richResponseMessage` es el campo 97 de `Message` | found |
| Reensamblado de chunks | No respaldado por la evidencia de 2.26.41.6 (ver 6.2) | found |

---

## 9. Solución para Baileys

No se afirma ninguna implementación funcional. Lo que sigue es un esbozo estructural de dónde viven los campos según 2.26.41.6, marcado como **inferred**; no se ha ejecutado contra un servidor.

### 9.1 Destino

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Si la cadena de servidor `bot` funciona como destino de relay de Baileys, y cómo el servidor deriva el `to` final de la stanza, es unknown.

### 9.2 Ubicación de los campos (solo la forma)

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

- El embebido de `botMetadata` en `messageContextInfo` (campo 7) es **found**. `capabilityMetadata` (13) y `timezone` (8) los escribe el cliente solo para destinos Hatch (found); su requisito del lado del servidor es unknown. Si el proto de `baron-baileys-v2` ya tiene estos campos no se ha verificado; si no, hay que extender el proto (inferred).
- `isSupportAiMessage` (70) y `botMessageInvokerJid` (58) son campos de `WebMessageInfo`. Si deben estar presentes en el wire es unknown; no los ponga en `contextInfo` (eso era incorrecto en el informe de 2.26.26.4).
- `botTargetId`: ningún escritor del cliente en todo el código decompilado (found); no lo establezca.
- El wrapping exacto (`botInvokeMessage.message` conteniendo el mensaje real vs. junto a él) sigue el re-envoltorio de `F2K` / `C33284Eea`; el resultado serializado exacto no se reprodujo (unknown).

### 9.3 Manejo de respuestas

- Respuestas ricas: `Message.richResponseMessage` es el campo **97** (found). Parsee ese, no el campo 77.
- Elimine el manejo de chunks: `chunkOrder` / `isLastChunk` no son campos de streaming de Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) de Hatch es el canal de solicitudes JSON; no se demuestra que las respuestas de chat simples lo usen.

### 9.4 Contexto de la conversación

`BotMetadata.aiConversationContext` (20) existe. Que el servidor devuelva estado actualizado en las respuestas y que deba reenviarse de vuelta es **inferred** (a partir del nombre del campo y del informe de 2.26.26.4); no verificado.

---

## 10. Flujos

### 10.1 Mensaje de chat al bot (found en el cliente, inferred en el servidor)

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

### 10.2 Solicitud de metadatos Hatch (found en el cliente)

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

## 11. Cambios respecto a 2.26.26.4

| Elemento | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Heredado, flag 25119 | No presente. 25119 solo en tablas de flags, sin lector |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 son servidor `bot` (`C24770wv`); 165332417282214 es `lid` (`C14080dr`) |
| Nuevas constantes de JID | ninguna listada | `1807055946647699` (bot-envelope CoEx v2 / destino del conjunto de dispositivos), `2942131436135992` (JID del perfil Meta AI por defecto, prueba de JID de bot `A07`), `867051314767696555` (segundo miembro de `A07`, propósito unknown), `17015557208` (PN de Meta AI, `A04`) |
| Sufijo `$1` | En el JID de enrutamiento, `C1A2.A00/A01` | No en el JID; agregado a la cadena de ID de persona (`C24121Ab2`, `C223219iv`) |
| Conversión de enrutamiento | agregado de `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot mediante la tabla FBID |
| Nombres de flags 25119/26189/27083 | nombres de flag `ai_*` | Las cadenas son entradas de lista de features (`C25056AqU`); 26190 = JSON del perfil Hatch; 37227/37852/37054 controlan los valores de capability de Hatch 76 / 77 / 79 |
| `richResponseMessage` | Campo 77 | Campo 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 en "WebMessageInfo" | 67 / 100 / 104 en `Message`; también 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nunca escrito |
| Ubicación de BotMetadata | "embedded in message" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | Cadena de persona del perfil, p. ej. `1807055946647697$1`; `meta_ai` es una etiqueta de tipo de bot |
| Tipos de plugin | 8, 9, 15 | Iguales, el enum tiene 18 valores (hasta 17) |
| Enum de acción | Enum de valores 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Envelope JSON de Hatch | `method`, `params` en el nivel superior | Anidados bajo `payload`; agrega `accepts_encoding` |
| Portador de Hatch | Mensaje estándar, clase `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; agrega `bizAiMetadataSync` (2) |
| Mapas de pendientes | Uno (`A02`) | Dos: `A04` continuaciones, `A03` callbacks de partes `GuR` |
| Campos de streaming | Una tabla de chunks de Meta AI | `chunkOrder` (history sync), `isLastChunk` (mensaje TEE), `streamingSidecar` (media); `clientStreaming`/`serverStreaming` no encontrados |
| Intervalo de sincronización de perfil | "every ~1 min" | 1 min es backoff de WorkManager, no un período |
| `MetaAiMemoryStore` | Presente | No encontrado por nombre; tabla `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) encontrada |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Presente | Presente |
| Indicador de escritura (chatstates) | Found | Found: saliente `<chatstate><composing/></chatstate>`, con `<bot jid/>` cuando se menciona un bot (`C199098dN.A01`); entrante `composing`/`paused` mediante el handler genérico `C40511kx`, sin rama específica de bot |
| Anuncio de capabilities | no documentado | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) para Hatch; los flags 37227 / 37852 / 37054 mapean a los valores de enum 76 / 77 / 79 |
| Ejemplos de solicitud Hatch | no documentado | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
