<!-- src-sha1: 92bebfe6214e20e4e50526fbb6583d35cc44e808 -->
# WhatsApp Meta AI — Full RE Report
**Versión:** 2.26.41.6 | **Fecha:** 2026-10-17
**Alcance:** internals de Meta AI — JIDs, enrutamiento, campos proto, requests de metadata Hatch, renderizado de respuesta, por qué falla Baileys, arreglo

---

## 1. Qué es Meta AI (técnicamente)

Meta AI es un contacto de bot direccionado por JIDs de bot especiales (servidor `bot`), con campos proto específicos de bot en los tipos de mensaje normales y un canal de request JSON separado ("Hatch metadata") llevado en un `ProtocolMessage`. Todas las afirmaciones son análisis estático de la APK decompilada. Nivel: **found** = leído en código, **inferred** = deducido del código, **unknown** = no resuelto.

Los nombres en este informe que estaban obfuscados en 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) fueron re-resueltos a partir de anclas estables; no existen bajo esos nombres en 2.26.41.6.

| Entidad | Nombre en 2.26.41.6 | Rol |
|--------|----------------|------|
| BotJid | `C24770wv` | clase JID, servidor `"bot"`, tipo 26, string numérico de 1-20 caracteres, sin 0 inicial |
| Constantes de JID de bot | `AbstractC34361Xw` | constantes y conjuntos de Hatch / Fallback / LID |
| Mapeo de JID | `AbstractC24760wu` | mapeo bot ↔ LID, conversión de objetivo saliente |
| Compuerta | `C39311it` | compuerta de feature-flag por JID (`A0E(Jid)`) |
| Gestor de request de Hatch | `HF1` (`HatchMetadataRequestManager`) | requests JSON, mapa de pendientes |
| Constructor proto de Hatch | `Hf6` | construye `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | guarda `botMetadata` |
| BotMetadata | `C30615DTj` | metadata de bot por mensaje |
| Registro de perfil de bot | `C199348dm` | nombre, descripción, string de ID de persona, thumb |

---

## 2. JIDs de Meta AI

### 2.1 JIDs encontrados en el código

| Constante | Clase | Rol | Nivel |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) vía `AbstractC34361Xw.A00` | **Hatch**, primario. Perfil por defecto construido en `C223219iv` desde el payload del flag **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) vía `AbstractC34361Xw.A01` | Fallback. Controlado por el flag 27083 | found |
| `165332417282214` | `C14080dr` (servidor `"lid"`) vía `AbstractC34361Xw.A02` | Contraparte LID de `…698` | found |
| `1807055946647696` | ninguna | Manus (legacy en 2.26.26.4): **no presente** en 2.26.41.6 | found (ausente) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), más `A01` = `DeviceJid` dispositivo 0 | JID de servidor de bot usado como objetivo de sesión/dispositivo para un "envelope de bot" (manejador de request de sincronización CoEx v2 `C53148Nnt` cifra el payload de sync a su dispositivo primario, log `coexv2 attached bot envelope`), añadido a conjuntos de dispositivos destinatarios (`C12M`), y tratado como remitente de bot en el manejo de recibo de reintento (`C33020EaI`). No es una persona de chat | found (uso); propósito más allá de eso inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID del registro de perfil "Meta AI" por defecto incorporado (`C9i5.A00`: nombre `Meta AI`, texto de intro por defecto). Miembro de la prueba de JID de bot `AbstractC24760wu.A07` junto con la fila siguiente | found |
| `867051314767696555` | `AbstractC24760wu.A01` (conjunto singleton, `C24770wv`) | Segundo miembro de la prueba `A07` de JID de bot (`A07(jid)` = `C24770wv` igual a `…135992` o en este conjunto); `A07` alimenta `AbstractC199328dk.A00` (un predicado de clase JID). Propósito adicional no resuelto | found (uso), propósito unknown |
| `17015557208` | `AbstractC24760wu.A04` | String de usuario de teléfono. `A04(jid)` es true para el LID `165332417282214` o para este usuario de teléfono; usado con `A03` (cualquier JID de bot `C24770wv`, o PN en los rangos 13135550000-13135559999 / 13165550000-13165550099) en `E76.A00` (clase 10 vs 1) y en el predicado de elegibilidad `C736539v.ARO`. Se lee como la identidad PN de Meta AI; qué hacen esos dos consumidores con ella no está resuelto | found (uso), propósito unknown |

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

Found: JID de bot `…698` ↔ LID `165332417282214`; los contactos de bot de número de teléfono mapean a JIDs de bot. El método afirma "needs FBID migration" (found).

### 2.3 El sufijo `$1`: cambiado

El informe de 2.26.26.4 colocaba `$1` en el JID de enrutamiento ("formato de cable", `C1A2.A00()/A01()`). No encontrado en 2.26.41.6:
- Ninguna función de enrutamiento añade `$1` a un JID. La conversión en 2.2 produce JIDs de bot planos.
- `$1` se añade al string de ID de persona almacenado en el registro de perfil de bot: `C24121Ab2` hace `personaIdString = botFbid + "$1"`; `C223219iv` hardcodea `"1807055946647697$1"` para el perfil por defecto de Hatch (found).
- Ese string (`C199348dm.A0A`) es lo que `C33473Ehf.A0G` escribe en `BotMetadata.personaId` (found).

Así que `$1` pertenece al ID de persona, no al JID de destino.

### 2.4 Detección isMetaAI

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
| **25119** | Aparece solo en tablas de flags (`C06510El`, default `false` en `C08J`). No se encontró ningún lector. El nombre antiguo `ai_bot_integration_enabled` no se encontró como string | found |
| **26189** | Compuerta de Hatch en `C39311it.A02()`. Default `false` (`C08J`) | found |
| **27083** | Compuerta de Fallback / LID en `C39311it.A0E()`. Default `false` | found |
| **26190** | Config JSON (`name`, `description`, `profile_thumb`) para el perfil por defecto de Hatch, leído en `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Cuando es true, se anuncia la capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) a Hatch (ver 5); `A05` también controla la telemetría/UI de connector (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Anuncia `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); también controla la disponibilidad de connector (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Anuncia `HATCH_ARTIFACT_CARD_ENABLED` (79); también leído por `HatchSpacesSync` y `C7WL` | found |

Los strings `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` no son nombres de flag. Son entradas de una lista de strings de función construida a partir de los flags 26189 / 27083 en `C25056AqU` (junto a `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` se añade sin condición. El destinatario y propósito de la lista no fueron verificados.

---

## 4. Campos proto

### 4.1 Message (`C30628DTw`) de nivel superior

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (campo único `message` = 1) | Mensaje saliente envuelto para el bot; fijado en `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Tarea de bot |
| `botForwardedMessage` | **104** | `BD2` | Envuelve un mensaje que lleva `richResponseMessage`; fijado en `F3E` |
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
| `botMessageInvokerJid` | **58** | string | Fijado en `C34385EwW` desde `C0DZ.A09(userJid)` (usuario de dispositivo primario del invocador) |
| `isSupportAiMessage` | **70** | bool | Fijado en `C34378EwP.C57` cuando el mensaje tiene el bit de flag `268435456` y pasa un chequeo; leído de vuelta en `C59`. Junto a `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | mensaje repetido | Citas |
| `botTargetId` | **73** | string | Sin escritor en el cliente: `botTargetId_` aparece solo como el default del constructor y en la tabla de schema de `C30626DTu`, nunca asignado en ningún otro lugar (grep de código completo) |
| `agentId` | **47** | string | Presente, no analizado |

Si y cómo aparecen estos campos de WebMessageInfo en el cable no está verificado (unknown). "`true` para todos los mensajes de Meta AI" no está respaldado: se fija por flag de mensaje, no incondicionalmente.

### 4.3 MessageContextInfo (`C30624DTs`)

| Campo | Número | Tipo |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `personaId` | **2** | string | Del registro de perfil de bot (`C199348dm.A0A`), p. ej. `1807055946647697$1`. No un `"meta_ai"` fijo |
| `pluginMetadata` | **3** | `DTL` | Config de plugin |
| `invokerJid` | **5** | string | Invocador |
| `aiConversationContext` | **20** | bytes | Estado de conversación |
| `botResponseId` | **26** | string | ID de respuesta |

Otros campos presentes (nombres de `*_FIELD_NUMBER`, tipos no leídos): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` se llena en `C33473Ehf.A0G`; retorna temprano si el perfil no tiene string de persona.

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

Constantes de `C4E0` (valor = ordinal del constructor; que iguale al número proto es inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Los valores antiguos 8/9/15 no cambian; el enum es más grande.

### 4.6 Oneof de acción (`C61331Rfl`, enum de caso `EnumC61601RkN`)

| Número | Caso | Nivel |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Esto es un oneof de campos de acción, no un enum de valor plano. Dónde está embebido no fue rastreado (unknown).

### 4.7 Operación de metadata de IA (portador Hatch)

| Mensaje | Campo | Número | Tipo |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Protocolo de request (metadata Hatch)

Las requests se construyen con `HF1` (`HatchMetadataRequestManager`), clase corrutina `HatchMetadataRequestManager$sendRequest$2`. El envelope JSON difiere de 2.26.26.4: `method` y `params` están anidados bajo `payload`.

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

`params` y `accepts_encoding` son opcionales (found). El ID de la request no está en el JSON; es `BB2.requestId` (un string aleatorio de `C20F.A0x()`).

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

- Requests pendientes: `HF1.A04` (`ConcurrentHashMap`, requestId → continuación) y `HF1.A03` (requestId → `GuR`). Ambos limpiados en `finally`. El informe de 2.26.26.4 nombraba solo un mapa `A02`.
- Timeout: devuelve `GDB.A00` y registra `HatchMetadataRequestManager/sendRequest timed out method=`.
- El entero `138` pasado a `C37393GKy` no está resuelto (unknown).
- El portador es `ProtocolMessage.aiMetadataOperation` (campo 31), no un mensaje de chat plano (cambiado).
- El paquete `com.whatsapp.bot.infra.message.aimetadata` contiene clases `Ideas*Wire` / `Idea*Wire` (found). Su relación con los nombres de método es solo inferred; los nombres de método no fueron enumerados.
- El lado de recepción que completa `A04` no fue rastreado. Emparejar una respuesta con `requestId` es inferred a partir del mapa `A04` y `BB2.requestId`.

**Afirmación "sin namespace XMPP personalizado":** no se vio ningún manejo de `w:ai` / `wa:ai` en la ruta rastreada; basado en ausencia, no re-verificado exhaustivamente.

**Anuncio de capability (found, `C33284Eea`):** cuando el destino es el JID de Hatch `…697` (`AbstractC34361Xw.A00`) y una compuerta pasa, el cliente construye `DPJ` (campo único enum repetido `capabilities` = 1, valores `EnumC32144E2q`) y `C33473Ehf.A06` lo almacena en `BotMetadata.capabilityMetadata` (13) del mensaje saliente, junto con `BotMetadata.timezone` (8) = el ID de `TimeZone` del dispositivo. Capabilities añadidas por compuerta:

| Compuerta | Capability (número de enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Los números son el segundo argumento del constructor del enum; que igualen a números proto es inferred. El enum también lista capabilities de rich-response (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Ejemplos de request (found, claves de `params` leídas en los call sites; el objetivo es el JID de Hatch `…697` salvo que el call site use el JID de conversación):**

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

`accepts_encoding` se escribe solo cuando el `acceptsGzipResponse` del llamante es true; `params` solo cuando no es null. El callback `onPart` se registra en `A03` solo cuando el llamante pasa uno.

**Mensaje de chat al bot (partes found):**
- El `Message` saliente se re-envuelve en `Message.botInvokeMessage` (`F2K`, `C33284Eea`), el wrapper `BD2` llevando el mensaje en el campo 1. En `F2K` la envoltura se omite (el mensaje se fija directamente) cuando `C13S.A00()` es false, el `A10` del mensaje es false, o el flag **10646** está activado (found).
- `BotMetadata` se construye con `C33473Ehf.A0E` / `A0G`. `A0G` busca el registro de perfil para el JID de bot objetivo (`C199358dn.A06(userJid)`, string de persona `C199348dm.A0A`); si ese string está vacío el método retorna sin escribir metadata de bot, de otro modo fija `personaId` (2) y, cuando está presente, `suggestedPromptMetadata` (4) y más sub-mensajes. El string de persona se almacena cuando se crea el registro de perfil (`C24121Ab2` construye `<id>$1`; `C223219iv` hardcodea `1807055946647697$1` para Hatch). Si `messageContextInfo` cae en el `Message` externo o en el mensaje dentro de `botInvokeMessage` no fue resuelto.
- `botMessageInvokerJid` / `isSupportAiMessage` se fijan en `WebMessageInfo` por hooks D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Protocolo de respuesta

### 6.1 Transporte

No re-verificado como se afirmaba en 2.26.26.4 ("mensajes normales con bytes de `hatchMetadataSync`", clase `Azz`). Found: `hatchMetadataSync` vive en `C25754B9o` dentro de `ProtocolMessage.aiMetadataOperation`. Las respuestas de Hatch presumiblemente llegan del mismo modo y se emparejan por `requestId` (inferred). Las requests de Hatch son llamadas a método; no se muestra que sean la ruta de las respuestas de chat normales.

### 6.2 Streaming / chunks: no respaldado como se describía

La tabla de 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) como un único mecanismo de streaming de Meta AI no está respaldada en 2.26.41.6:

| Campo | Dónde está en 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` campo **7** (notificación de sincronización de historial, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) y `C25838BCy` campo **5** (sincronización de historial) |
| `isLastChunk` | `C55285Ou6` campo **8** (mensaje con `attestationBundles`, `teeModelConfig`, `violationSignal`; relacionado con TEE) |
| `streamingSidecar` | campo **18** en mensajes de imagen/video/audio (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | no encontrados como campos proto |

No se encontró ningún reensamblado de chunks de respuestas de Meta AI. Lo que existe para Hatch: `GuR(method, onPart)` — un callback `onPart` por request (found); que lleve resultados parciales es inferred del nombre.

### 6.3 Rich response (campo 97)

`richResponseMessage` (`DSY`) = campo **97** en `Message`. Existen clases de renderizado: `AiRichResponseFooterView` y `UnifiedResponseActionHandlerFactory` (paquete `com.whatsapp.conversationrow.botrichresponse`) (found). Citas: `WebMessageInfo.supportAiCitations` (72). Los tipos de contenido (imágenes, tablas, código) no se re-verificaron aquí; ver la investigación separada de richResponseMessage.

### 6.4 Indicador de escritura

Saliente (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): chat state XMPP estándar, sin namespace personalizado en el código leído.
- Caso plano (sin bot mencionado, o un JID de bot resuelto al por defecto): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot mencionado en el chat: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Enviado a través de `C10140Tq.A0X` con tipo IQ int 4.

Entrante (found, manejador de stanza `C40511kx`): un `<chatstate>` con un hijo `composing` (opcional `media`) llama al callback genérico de composing con `from`/`participant`; `paused` llama al callback de paused. No se encontró ninguna rama específica de bot en este manejador, así que un `composing` de JID de bot pasa por la misma ruta que cualquier contacto (inferred; no se observó ningún stanza de typing de bot del lado servidor). `BotMetadata.progressIndicatorMetadata` (12) y la capability `PROGRESS_INDICATOR` existen como un mecanismo de progreso en el mensaje separado (solo nombres, no rastreado).

### 6.5 Sincronización de perfil de bot

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) programa `BotProfileForChatListWorker` en `A03()`: una request de WorkManager etiquetada `BotProfileSyncManager` con `setBackoffCriteria(policy, 1, MINUTES)` y una restricción (valor de tipo no resuelto). El 1 minuto es un **backoff** de reintento, no un período. El "cada ~1 minuto" de 2.26.26.4 no está respaldado (cambiado). `A02(groupJid, userJid)` pide un único perfil (`requestBotProfileResult`). No forma parte de la sincronización normal del roster (sin cambios).

Registro de perfil `C199348dm`: tipo de bot (`C1XY`), jid, nombre visible (`A09`), descripción (`A07`), string de persona (`A0A`), thumbs, marca de tiempo.

### 6.6 Strings de tipo de bot

`C718732k.A00(String)` mapea: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; cualquier otra cosa se convierte en `AnonymousClass399(str)`. Estas son etiquetas de tipo de bot (también usadas en filtros de UI), no valores de `BotMetadata.personaId` (found).

---

## 7. Almacenamiento

- `MetaAiMemoryStore`: no existe ninguna clase con ese nombre en 2.26.41.6. El equivalente encontrado es una tabla `meta_ai_memory` creada por la clase de schema `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, índice `meta_ai_memory_memory_content_index` en `memory_content`. Qué archivo de base de datos la contiene no está resuelto. Relacionado (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; el nombre dice deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (pantalla de diseño de llamada de voz, `C29434Cpx`), enums de capability `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), y `BotMetadata.memoryMetadata` (15).
- Clave de SharedPrefs `"meta_ai_forward_disclosure_seen"`: presente, booleana, leída en `C230589xr.A03` para `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: presente en `com.whatsapp.metaai.incognito.infra` (found).
- Almacenamiento separado de chats de Meta AI fuera de `msgstore.db` (2.26.26.4, no re-verificado): no se encontró ninguna clase de almacén de chat; `meta_ai_memory` solo guarda hechos de memoria, así que la afirmación no está ni respaldada ni refutada.

### 7.1 Private Search como un tipo de hilo de chat de bot (nuevo en 2.26.45.10, found)

Clases nuevas (`com.whatsapp.privateai.privatesearch`, `com.whatsapp.searchui.search.psisearch`):

| Clase | Rol |
|-------|-----|
| `PrivateSearchSessionManager` | Rastrea el único hilo de Private Search activo/más reciente; se niega a reanudar un hilo superado por una búsqueda más nueva |
| `PrivateSearchThreadsManager` | Crea un hilo de bot de tipo `PRIVATE_SEARCH`; extiende `LX/1gu`, la misma base `BotThreadsManager` que ya usa `IncognitoAiThreadsManager` (arriba) |
| `PsiSearchManager` (obfuscado `LX/JjA`) | Posee el flujo de envío de consulta/seguimiento ("echo") |
| `PsiSearchDialogFragment` | UI de diálogo; un argumento `"kind"` de `"TURN_ON_PRIVATE_PROCESSING"` muestra la compuerta de opt-in de Private Processing en línea |
| `PsiSearchUnifiedResponseRenderer` | Renderiza la respuesta del bot |

Private Search se implementa como un **tipo de hilo de chat de bot** más, no una nueva primitiva de red. `PrivateSearchThreadsManager` llama al constructor de hilo de bot compartido `LX/1gv;->A00(LX/2p4, ...)` con un enum de 5 valores `LX/2p4`: `UNKNOWN`(0) / `DEFAULT`(1) / `INCOGNITO`(2) / `SIDE_CHAT`(3) / `PRIVATE_SEARCH`(4). `PsiSearchManager` re-valida el tipo de un hilo contra este discriminador antes de enviar, rechazando una consulta en blanco o un hilo que no sea `PRIVATE_SEARCH`.

**Ruta de envío de consulta (found).** `PsiSearchManager.onEchoSelected` construye el mensaje saliente vía la misma utilidad genérica de creación de mensaje que usan otros envíos de chat, `LX/D1D;->A05(...)`, luego despacha el resultado a través de la cola de mensaje saliente ordinaria (`LX/JjA;->A0H:LX/0JB;->D2A`). No aparece ninguna llamada GraphQL/MEX/IQ en ninguna parte de esta ruta — es el mismo mecanismo de envoltura `botInvokeMessage` (campo 67) hacia JID de bot documentado en §11 ("Mensaje de chat al bot"), reutilizado textualmente y no re-derivado aquí.

**Lo que permanece nativo (referencia cruzada).** El pipeline de recuperación PSI/TEE que realmente responde la consulta — `TeeClientToolOrchestrator`, `PsiSearchToolHandler` (herramienta de cliente `wa_search`), `IplsdHandshakeExecutor`, respaldado por `libpsi.so`/`libxplat_psi.so` nativos — no cambia respecto a 2.26.41.6 y está documentado en la investigación de Labyrinth/TEE del brain (no re-derivado aquí); ninguna de las cinco clases arriba lo toca, solo construyen el mensaje saliente y renderizan la respuesta.

**Veredicto de alcanzabilidad: envío alcanzable, valor inalcanzable.** El envío de inicio de búsqueda es alcanzable por un cliente de terceros exactamente en el mismo sentido en que ya lo es el chat de Meta AI (§8, §11) — nada nuevo que vencer. Lo que no es alcanzable es el valor real de preservación de privacidad de la función: la búsqueda PSI en el dispositivo sobre la BD de chat local y el round-trip de enclave atestiguado son nativos, y el `Message` saliente no lleva ningún material PSI precalculado. Un cliente de terceros que envíe texto plano al JID de bot de Private Search obtendría lo que sea que el bot del lado servidor haga con una consulta en texto plano sin PSI, no la semántica de búsqueda privada propia de WhatsApp (unknown, no verificado en ninguna dirección).

### 7.2 Dejar de generar movido fuera de la ruta de mensaje de cable (nuevo en 2.26.45.10)

El string de error `promptMessageKey` (presente desde 2.26.35.8, atado a `FMessageStopGeneration` / `ProtocolMessage.extraJson_`, tipo 26) tiene **cero coincidencias** en los 14 archivos DEX de 2.26.45.10 (found, escaneo exhaustivo de strings). El campo subyacente `extraJson_` todavía se declara en `LX/DHC;` (la clase anfitriona de `ProtocolMessage`) pero solo se referencia dentro de la propia declaración de campo de esa clase y el array de reflexión — sin getter, ninguna otra clase en la app lo lee (found). D8 eliminó completamente la información de debug en este build (cero nombres de archivo `DBG_SET_FILE` recuperables entre 34,255 métodos en `classes6.dex`), así que la clase obfuscada que antes respaldaba `FMessageStopGeneration` no pudo ser identificada a partir de la metadata de debug; los tres strings de nombre de archivo `.kt` para ella sobreviven solo como entradas huérfanas del pool de strings, no como código alcanzable (found).

En su lugar se encontró: una clase nueva, **sin obfuscar**, `com/meta/metaai/stopgeneration/data/StopGenerationRepository` cuyo `A00(threadIdentifier, messageIdentifier, messageIdString, surface, mode, Continuation)` dispara una mutación GraphQL de Pando `MetaAIStopGenerationMutation` (op `xfb_genai_stop_generation`), con campos `thread_identifier`, `message_identifier`, `message_id_string`, `surface`, `mode`, validados por chequeos de null genéricos no indexados por string (`LX/00m;->A09`) — sin texto de error estilo `promptMessageKey`.

Mejor explicación (**inferred**, no probada): dejar de generar se movió a esta mutación GraphQL para esta superficie, en lugar de que la vieja comprobación de mensaje de cable fuera renombrada in situ. Si la ruta legacy `protocolMessage`/tipo-26/`extraJson_` ahora es código muerto, se mantiene por compatibilidad con clientes antiguos, o todavía es alcanzable desde algún llamante no rastreado es **unknown** — no se encontró ningún llamante en este build, pero un escaneo estático de un solo DEX no puede probar su eliminación.

---

## 8. Por qué Baileys no obtiene respuesta

Todas las filas son **inferred**: comparación estática de los requisitos del cliente con una ruta de envío de terceros; sin prueba en vivo.

| Problema | Base en 2.26.41.6 | Nivel |
|-------|--------------------|------|
| Tipo de JID objetivo incorrecto | Los JIDs de bot usan servidor `bot` (`C24770wv`), no `s.whatsapp.net`; los bots de número de teléfono mapean a través de una tabla PN→FBID | found (clase JID), inferred (efecto) |
| `$1` en el JID de enrutamiento | No presente. `$1` está en el string de ID de persona | found |
| Falta la envoltura `botInvokeMessage` | El cliente envuelve el `Message` saliente en el campo 67 (`F2K`) | found, requisito inferred |
| Falta `messageContextInfo.botMetadata` | El cliente escribe `personaId`, `invokerJid`, etc. en él | found, requisito inferred |
| `personaId = "meta_ai"` | No es lo que envía el cliente; envía el string de persona del perfil (p. ej. `1807055946647697$1`) | found |
| Falta `aiConversationContext` | Campo 20 de `BotMetadata`; comportamiento en el primer turno unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Campos de WebMessageInfo fijados por hooks del cliente; requisito del servidor unknown | unknown |
| `botTargetId` | Sin escritor en el código del cliente | found |
| Respuesta no parseada | `richResponseMessage` es el campo 97 de `Message` | found |
| Reensamblado de chunks | No respaldado por la evidencia de 2.26.41.6 (ver 6.2) | found |

---

## 9. Verificación de firma de bot (autenticidad de contenido)

Separado de todo lo anterior: un mecanismo que permite al cliente **receptor** verificar que el contenido de `richResponseMessage` genuinamente vino del backend de IA de Meta, independientemente de quién relevó el mensaje. Los hallazgos estáticos abajo son `found` en el código de 2.26.41.6; el resultado del replay en 9.4 es `tested` (en vivo, en la propia cuenta del autor — no interceptación de tráfico, un cliente legítimo componiendo y relevando su propio mensaje).

### 9.1 Ubicación en el proto

`BotMetadata.verificationMetadata` — campo **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), tipo `DPC`/`BotSignatureVerificationMetadata` (el toString revela el nombre real): `proofs[]`, cada uno un `BotSignatureVerificationUseCaseProof` con `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (bytes repetidos, DER X.509).

### 9.2 Algoritmo de verificación

Clase `C33259EeB`, nombre interno `BotSignatureVerificationUtils` (de strings de log):

1. **Validación de cadena de certificado** de `certificateChain` contra un ancla de confianza, vía `HFg.A01(date, certs, true)`.
2. **Construcción de bytes firmados**: `"1" + <string de número de teléfono> + <bytes de unifiedResponse>` — la firma vincula **contenido y un número de teléfono juntos**, no solo el contenido.
3. **Verificación EdDSA** (log: `"EdDSA signature verification result"`) usando la clave Ed25519 cruda extraída del SubjectPublicKeyInfo del certificado hoja.
4. **Modo de aplicación**, leído de la config **19590**, enum `EnumC32057Dzg`: `NONE` (`"none"`, desactivado, siempre pasa), `LOG_ONLY` (`"log_only"`, verifica + registra, nunca bloquea), `ENFORCE_BLOCKING` (`"enforce_blocking"`, un chequeo fallido devuelve `false`). Resultado almacenado como `E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, persistido en la columna SQLite `bot_message_info.signature_validation_status` (la tabla también tiene `bot_client_public_key`).

### 9.3 Compuerta de renderizado de fila

`C30085D6v.A00` (despachador de tipo de fila) y `EOK`/`C32608EKo`: si el estado de firma es `FAILED` y el flag **27635** está activado → fila enmascarada `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Independientemente, si el JID del remitente no está presente en el almacén de perfil de bot sincronizado localmente (`C224899mg`, la misma sincronización que `BotProfileSyncManagerImpl`) y el flag **27355** está activado → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), una vista previa con compuerta de consentimiento en lugar de un bloqueo duro.

### 9.4 Captura real y replay en vivo (tested)

Una respuesta genuina de Meta AI, capturada del lado cliente en una conversación real (cuenta propia, descifrada por el propio cliente del autor — no interceptación de tráfico), llevaba:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, una `signature` de 64 bytes (tamaño Ed25519), una `certificateChain` de 2 entradas.
- Certificado hoja: `CN=svc:wa-bot-msg-leaf`, clave Ed25519, emitido por `Meta WA SS Int CA 2025-09`, encadenando a `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`), validez ≈7 meses (certificado de servicio auto-rotado) — la clave privada de firma solo existe en el backend de Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — un nombre de backend de bot no documentado previamente (ver también "Hatch" en las secciones 1–6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, un campo hermano de `botMetadata`.
- Forma de entrega: `protocolMessage` con `type: MESSAGE_EDIT`, `editedMessage.richResponseMessage` (la primera respuesta en un hilo llega pre-envuelta como una edición de un placeholder), `key.remoteJid` = el propio JID del autor.

**Prueba:** el exacto `richResponseMessage` + `messageContextInfo.botMetadata` (firma y cadena de certificado sin cambios byte por byte) fue relevado vía `relayMessage` desde el propio dispositivo del autor — no el JID de bot `867051314767696@bot` — al propio número del autor (el mismo número ya embebido en los bytes firmados).

**Resultado:** el contenido se renderizó con el estilo "IA" completo y el texto real, etiquetado "Forwarded". Algunas entregas del mismo payload idéntico mostraron en su lugar "WhatsApp can't verify the security of this media. Only download if you trust the sender." con una acción de Descargar; tocar Descargar revelaba el contenido idéntico, coincidiendo con el estado `DOWNLOAD_CONSENT_ACCEPTED` y la ruta de código "unknown sender with unconsented content" de 9.3. Una entrega mostró un fallback genérico "your version of WhatsApp doesn't support it" en su lugar; la causa no fue establecida (unknown).

**Conclusión (tested):** el chequeo criptográfico en 9.2 vincula a *(contenido, número de teléfono)*, no a la identidad o JID del remitente en vivo. Un `richResponseMessage` firmado válidamente puede ser relevado desde un remitente no-bot y aun así pasar la verificación de firma, siempre que el número del destinatario coincida con el número horneado en la firma — el cliente receptor lo renderiza como contenido de IA genuino (a lo sumo controlado por un paso de consentimiento "remitente desconocido" cosmético de un toque, no un bloqueo duro). Este es un mecanismo de autenticidad de contenido, no de autenticidad de remitente; el propio cifrado de capa Signal de WhatsApp, no esta firma, es lo que autentica al remitente en vivo.

### 9.5 Chequeo de lista de revocación de certificados (CRL) (nuevo en 2.26.45.10, found)

El paso de validación de cadena en 9.2 (paso 1, "validación de cadena de certificado... vía `HFg.A01`") ganó un chequeo CRL contra tanto el certificado hoja como el intermedio en `certificateChain`, antes del chequeo de firma Ed25519 sobre (teléfono, contenido) (9.2 paso 3). Clases: `BotPkiCrlGraphQLFetcher`/`BotPkiCrlManager` (`com/whatsapp/bot/infra/message/signature/`), llamadas desde la clase de validación de cadena de 2.26.45.10 `BotSignatureVerificationCertificateManager` (`LX/HEe` — sucesora renombrada de `BotSignatureVerificationUtils`/`C33259EeB` de 9.2; misma clase, confirmado por strings de log compartidos `"Certificate chain validation successful"`/`"Parsed <n> certificates from chain"`).

- **Op GraphQL**: `FetchBotPKICRL` en `whatsapp-android-mex` — campo de request `crl_name`, respuesta `xwa2FetchFeaturePkiCrl` que lleva el CRL como un blob de bytes DER crudo (no una lista de seriales revocados pre-parseada) más marcas de tiempo `fetchedAt`/`nextUpdate` y un conteo de entradas revocadas.
- **Dos CRLs en uso**, por nombre: `whatsapp_simple_signal` para el certificado **hoja**, `whatsapp_feature` para el certificado **intermedio** (strings de log `"...Leaf certificate CRL validation passed"` / `"...is revoked"` / `"...CRL unavailable..."`, mismo par para "Intermediate").
- **Ancla de confianza**: un certificado raíz de 40 años fijado como literal PEM dentro de `LX/HEe` — `CN=Meta WA Feature Root CA`, `O=Meta Platforms Inc.`, clave EC, válido de 2025-09-04 a 2065-09-04. La propia firma de cada CRL obtenido se verifica contra la clave pública del emisor correspondiente (`X509CRL.verify(...)`) antes de confiar en su lista de revocados — excepto para `whatsapp_simple_signal`, que tiene un caso especial que omite ese paso de auto-verificación (razón `inferred`, no resuelta).
- **Caché/refresco**: caché de `SharedPreferences` por `crlName` (`crl-data`/`crl-fetched-at`/`crl-next-update`), precargado una vez al inicio de la app tras que el usuario está registrado y la BD está lista (log: `"BotPkiCrlManager/...starting CRL prefetch"`), refrescado en un temporizador atado al propio `nextUpdate` del CRL (con un suelo de 60s), y obtenido a demanda con una ventana de backoff si la caché falta/está vencida cuando corre un chequeo.
- **Efecto**: un certificado hoja o intermedio revocado falla la validación de cadena del mismo modo que lo hacía uno ya expirado — esto alimenta el estado `E05` existente (`FAILED`) y la compuerta `ENFORCE_BLOCKING`/`LOG_ONLY`/`NONE` de 9.2 paso 4, no una ruta de aplicación nueva y separada.
- **Nivel**: found — op, namespace, ambos crlNames, mecánica de caché/refresco, call sites, certificado raíz fijado. Inferred — la disposición exacta de bytes de entrada revocada (serial vs. bytes de certificado completo) y la razón por la que `whatsapp_simple_signal` omite la auto-verificación de CRL. Todo análisis estático; no se observó ningún certificado revocado en la práctica.
- **Superficie de cliente/Baileys**: `FetchBotPKICRL` es una op MEX concreta y nombrada, alcanzable del mismo modo que otras ops `whatsapp-android-mex`, pero solo alimenta decisiones de confianza del lado cliente sobre certificados de mensaje de bot — no tiene efecto en lo que un remitente no-cliente puede relevar (el resultado de replay de 9.4 no se ve afectado: la revocación solo cambia los resultados para un certificado realmente revocado, lo cual esto nunca ejercita).

---

## 10. Arreglo de Baileys

No se afirma ninguna implementación funcional. Lo que sigue es un bosquejo estructural de dónde viven los campos según 2.26.41.6, marcado **inferred**; no se ha corrido contra un servidor.

### 9.1 Objetivo

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Si el string de servidor `bot` funciona como objetivo de relay de Baileys, y cómo deriva el servidor el `to` final del stanza, es unknown.

### 9.2 Colocación de campos (solo forma)

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

- La incorporación de `botMetadata` en `messageContextInfo` (campo 7) es **found**. `capabilityMetadata` (13) y `timezone` (8) son escritos por el cliente solo para destinos de Hatch (found); su requisito del lado servidor es unknown. Si el proto de `baron-baileys-v2` ya tiene estos campos no fue verificado; si no, el proto debe extenderse (inferred).
- `isSupportAiMessage` (70) y `botMessageInvokerJid` (58) son campos de `WebMessageInfo`. Si deben estar presentes en el cable es unknown; no los pongas en `contextInfo` (eso era incorrecto en el informe de 2.26.26.4).
- `botTargetId`: sin escritor del cliente en ningún lugar del código decompilado (found); no lo fijes.
- La envoltura exacta (`botInvokeMessage.message` conteniendo el mensaje real vs. junto a él) sigue el re-envolvimiento de `F2K` / `C33284Eea`; el resultado serializado exacto no fue reproducido (unknown).

### 9.3 Manejo de respuesta

- Respuestas enriquecidas: `Message.richResponseMessage` es el campo **97** (found). Parsear eso, no el campo 77.
- Eliminar el manejo de chunks: `chunkOrder` / `isLastChunk` no son campos de streaming de Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) de Hatch es el canal de request JSON; no se muestra que las respuestas de chat planas lo usen.

### 9.4 Contexto de conversación

`BotMetadata.aiConversationContext` (20) existe. Que el servidor devuelva estado actualizado en las respuestas y que deba ser repetido de vuelta es **inferred** (del nombre del campo y del informe de 2.26.26.4); no verificado.

---

## 11. Flujos

### 10.1 Mensaje de chat al bot (found del lado cliente, inferred del lado servidor)

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

### 10.2 Request de metadata Hatch (found del lado cliente)

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

## 12. Cambios vs 2.26.26.4

| Ítem | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legacy, flag 25119 | No presente. 25119 solo en tablas de flags, sin lector |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 son servidor `bot` (`C24770wv`); 165332417282214 es `lid` (`C14080dr`) |
| Nuevas constantes de JID | ninguna listada | `1807055946647699` (objetivo de envelope de bot/conjunto de dispositivo de CoEx v2), `2942131436135992` (JID de perfil de Meta AI por defecto, prueba de JID de bot `A07`), `867051314767696555` (segundo miembro de `A07`, propósito unknown), `17015557208` (PN de Meta AI, `A04`) |
| Sufijo `$1` | En el JID de enrutamiento, `C1A2.A00/A01` | No en el JID; añadido al string de ID de persona (`C24121Ab2`, `C223219iv`) |
| Conversión de enrutamiento | Añadir `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot vía tabla FBID |
| Nombres de flag 25119/26189/27083 | nombres de flag `ai_*` | Los strings son entradas de lista de función (`C25056AqU`); 26190 = JSON de perfil de Hatch; 37227/37852/37054 controlan los valores de capability de Hatch 76 / 77 / 79 |
| `richResponseMessage` | Campo 77 | Campo 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 en "WebMessageInfo" | 67 / 100 / 104 en `Message`; también 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nunca escrito |
| Ubicación de BotMetadata | "embebido en el mensaje" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | String de persona del perfil, p. ej. `1807055946647697$1`; `meta_ai` es una etiqueta de tipo de bot |
| Tipos de plugin | 8, 9, 15 | Iguales, el enum tiene 18 valores (hasta 17) |
| Enum de acción | Enum de valor 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Envelope JSON de Hatch | `method`, `params` de nivel superior | Anidados bajo `payload`; añade `accepts_encoding` |
| Portador de Hatch | Mensaje estándar, clase `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; añade `bizAiMetadataSync` (2) |
| Verificación de firma de bot | no documentado | Nuevo: `BotMetadata.verificationMetadata` (27), EdDSA + cadena de certificado X.509 sobre (contenido, número de teléfono); probado en vivo, vincula al número de teléfono no al remitente en vivo (sección 9) |
| Mapas pendientes | Uno (`A02`) | Dos: continuaciones `A04`, callbacks de parte `A03` `GuR` |
| Campos de streaming | Una tabla de chunk de Meta AI | `chunkOrder` (sincronización de historial), `isLastChunk` (mensaje TEE), `streamingSidecar` (media); `clientStreaming`/`serverStreaming` no encontrados |
| Intervalo de sincronización de perfil | "cada ~1 min" | 1 min es backoff de WorkManager, no un período |
| `MetaAiMemoryStore` | Presente | No encontrado por nombre; tabla `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) encontrada |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Presente | Presente |
| Indicador de escritura (chatstates) | Encontrado | Encontrado: saliente `<chatstate><composing/></chatstate>`, con `<bot jid/>` cuando se menciona un bot (`C199098dN.A01`); entrante `composing`/`paused` vía manejador genérico `C40511kx`, sin rama específica de bot |
| Anuncio de capability | no documentado | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) para Hatch; flags 37227 / 37852 / 37054 mapean a valores de enum 76 / 77 / 79 |
| Ejemplos de request de Hatch | no documentado | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
