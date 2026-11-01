<!-- src-sha1: 4a0b884541f4221f33fe16d1a5659612eb6bac89 -->
# WhatsApp Meta AI — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** Internos do Meta AI — JIDs, roteamento, campos proto, requisições de metadados do Hatch, renderização de respostas, por que o Baileys falha, correção

---

## 1. O que é o Meta AI (tecnicamente)

Meta AI é um contato bot endereçado por JIDs de bot especiais (servidor `bot`), com campos proto específicos de bot nos tipos normais de mensagem e um canal de requisição JSON separado ("Hatch metadata") transportado em um `ProtocolMessage`. Todas as afirmações são análise estática do APK decompilado. Tier: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido.

Nomes neste relatório que estavam obfuscados em 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) foram re-resolvidos a partir de âncoras estáveis; eles não existem com esses nomes em 2.26.41.6.

| Entity | Nome em 2.26.41.6 | Papel |
|--------|----------------|------|
| BotJid | `C24770wv` | Classe JID, servidor `"bot"`, tipo 26, string numérica de 1-20 caracteres, sem zero à esquerda |
| Constantes de JID de bot | `AbstractC34361Xw` | Constantes e conjuntos de Hatch / Fallback / LID |
| Mapeamento de JID | `AbstractC24760wu` | Mapeamento bot ↔ LID, conversão do destino de saída |
| Gating | `C39311it` | Gating por feature-flag por JID (`A0E(Jid)`) |
| Gerenciador de requisição Hatch | `HF1` (`HatchMetadataRequestManager`) | Requisições JSON, mapa de pendentes |
| Construtor de proto Hatch | `Hf6` | Constrói `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | Contém `botMetadata` |
| BotMetadata | `C30615DTj` | Metadados de bot por mensagem |
| Registro de perfil de bot | `C199348dm` | Nome, descrição, string de ID de persona, thumb |

---

## 2. JIDs do Meta AI

### 2.1 JIDs encontrados no código

| Constant | Classe | Papel | Tier |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) via `AbstractC34361Xw.A00` | **Hatch**, principal. Perfil padrão construído em `C223219iv` a partir do payload da flag **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) via `AbstractC34361Xw.A01` | Fallback. Controlado pela flag 27083 | found |
| `165332417282214` | `C14080dr` (servidor `"lid"`) via `AbstractC34361Xw.A02` | Contraparte LID de `…698` | found |
| `1807055946647696` | nenhuma | Manus (legado em 2.26.26.4): **não presente** em 2.26.41.6 | found (ausente) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), mais `A01` = `DeviceJid` dispositivo 0 | JID de servidor de bot usado como alvo de sessão/dispositivo para um "envelope de bot" (handler de requisição de sync do CoEx v2 `C53148Nnt` cifra o payload de sync para o seu dispositivo primário, log `coexv2 attached bot envelope`), adicionado aos conjuntos de dispositivos destinatários (`C12M`), e tratado como remetente de bot no tratamento de recibo de retry (`C33020EaI`). Não é uma persona de chat | found (uso); propósito além disso inferido |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID do registro de perfil "Meta AI" padrão embutido (`C9i5.A00`: nome `Meta AI`, texto de introdução padrão). Membro do teste de JID de bot `AbstractC24760wu.A07` junto com a linha seguinte | found |
| `867051314767696555` | `AbstractC24760wu.A01` (conjunto singleton, `C24770wv`) | Segundo membro do teste `A07` de JID de bot (`A07(jid)` = `C24770wv` igual a `…135992` ou presente neste conjunto); `A07` alimenta `AbstractC199328dk.A00` (um predicado de classe de JID). Propósito adicional não resolvido | found (uso), propósito desconhecido |
| `17015557208` | `AbstractC24760wu.A04` | String de usuário de telefone. `A04(jid)` é verdadeiro para o LID `165332417282214` ou para este usuário de telefone; usado com `A03` (qualquer JID de bot `C24770wv`, ou PN nas faixas 13135550000-13135559999 / 13165550000-13165550099) em `E76.A00` (classe 10 vs 1) e no predicado de elegibilidade `C736539v.ARO`. Lê-se como a identidade PN do Meta AI; o que esses dois consumidores fazem com isso não está resolvido | found (uso), propósito desconhecido |

Conjuntos em `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; mapa `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Tipo de JID: o relatório de 2.26.26.4 listava os quatro como `@s.whatsapp.net`. Em 2.26.41.6 os JIDs de bot são `C24770wv` com `getServer() = "bot"`; o do grupo/LID é `C14080dr` com servidor `"lid"`. Não `s.whatsapp.net` (found).

Tabela de número de telefone para bot-FBID: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, cerca de 200 entradas, ex. `13135550002 → 867051314767696`). Usada por `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

### 2.2 Conversão de roteamento

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

Found: JID de bot `…698` ↔ LID `165332417282214`; contatos de bot por número de telefone mapeiam para JIDs de bot. O método afirma "needs FBID migration" (found).

### 2.3 O sufixo `$1`: mudou

O relatório de 2.26.26.4 colocava `$1` no JID de roteamento ("formato de wire", `C1A2.A00()/A01()`). Não encontrado em 2.26.41.6:
- Nenhuma função de roteamento acrescenta `$1` a um JID. A conversão em 2.2 produz JIDs de bot simples.
- `$1` é acrescentado à string de ID de persona armazenada no registro de perfil do bot: `C24121Ab2` faz `personaIdString = botFbid + "$1"`; `C223219iv` fixa `"1807055946647697$1"` para o perfil padrão do Hatch (found).
- Essa string (`C199348dm.A0A`) é o que `C33473Ehf.A0G` grava em `BotMetadata.personaId` (found).

Portanto `$1` pertence ao ID de persona, não ao JID de destino.

### 2.4 Detecção isMetaAI

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

O ramo Manus (flag 25119) desapareceu. O significado de `BRD()` e a consulta de capability (`C09L.A04`) não estão resolvidos (unknown).

---

## 3. Feature Flags

| Flag ID | Uso em 2.26.41.6 | Tier |
|---------|------------------|------|
| **25119** | Aparece apenas em tabelas de flags (`C06510El`, padrão `false` em `C08J`). Nenhum leitor encontrado. Nome antigo `ai_bot_integration_enabled` não encontrado como string | found |
| **26189** | Gate do Hatch em `C39311it.A02()`. Padrão `false` (`C08J`) | found |
| **27083** | Gate de Fallback / LID em `C39311it.A0E()`. Padrão `false` | found |
| **26190** | Configuração JSON (`name`, `description`, `profile_thumb`) para o perfil padrão do Hatch, lida em `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Quando verdadeiro, a capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) é anunciada ao Hatch (ver 5); `A05` também controla telemetria/UI do connector (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Anuncia `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); também controla a disponibilidade do connector (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Anuncia `HATCH_ARTIFACT_CARD_ENABLED` (79); também lida por `HatchSpacesSync` e `C7WL` | found |

Strings `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` não são nomes de flag. São entradas de uma lista de feature-strings construída a partir das flags 26189 / 27083 em `C25056AqU` (junto com `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` é adicionada incondicionalmente. Destinatário e propósito da lista não verificados.

---

## 4. Campos Proto

### 4.1 Message (`C30628DTw`) nível superior

| Field | Number | Type | Uso |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (campo único `message` = 1) | Mensagem de saída envolvida para o bot; definida em `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Tarefa do bot |
| `botForwardedMessage` | **104** | `BD2` | Envolve uma mensagem contendo `richResponseMessage`; definida em `F3E` |
| `richResponseMessage` | **97** | `DSY` | Resposta de AI. Campos: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Presente |
| `botGroupParticipantMessage` | **137** | `BD2` | Presente |
| `messageContextInfo` | **35** | `C30624DTs` | Contém `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Contém `aiMetadataOperation` (31) |

O campo **77** é `commentMessage`, não `richResponseMessage` (o relatório de 2.26.26.4 tinha 77; errado para este build, e consistente com a pesquisa separada do richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), não ContextInfo

O relatório de 2.26.26.4 listava estes como campos de ContextInfo. Em 2.26.41.6 eles estão em `WebMessageInfo`:

| Field | Number | Type | Uso |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Definido em `C34385EwW` a partir de `C0DZ.A09(userJid)` (usuário do dispositivo primário do invocador) |
| `isSupportAiMessage` | **70** | bool | Definido em `C34378EwP.C57` quando a mensagem tem o bit de flag `268435456` e uma verificação passa; lido de volta em `C59`. Junto com `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Citações |
| `botTargetId` | **73** | string | Nenhum escritor no cliente: `botTargetId_` aparece apenas como o valor padrão do construtor e na tabela de schema de `C30626DTu`, nunca atribuído em nenhum outro lugar (grep no código-fonte completo) |
| `agentId` | **47** | string | Presente, não analisado |

Se e como esses campos de WebMessageInfo aparecem na wire não está verificado (unknown). "`true` para todas as mensagens do Meta AI" não é sustentado: é definido por flag de mensagem, não incondicionalmente.

### 4.3 MessageContextInfo (`C30624DTs`)

| Field | Number | Type |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Field | Number | Type | Uso |
|-------|--------|------|-----|
| `personaId` | **2** | string | Do registro de perfil do bot (`C199348dm.A0A`), ex. `1807055946647697$1`. Não é um `"meta_ai"` fixo |
| `pluginMetadata` | **3** | `DTL` | Configuração do plugin |
| `invokerJid` | **5** | string | Invocador |
| `aiConversationContext` | **20** | bytes | Estado da conversa |
| `botResponseId` | **26** | string | ID da resposta |

Outros campos presentes (nomes vindos de `*_FIELD_NUMBER`, tipos não lidos): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` é preenchido em `C33473Ehf.A0G`; retorna antecipadamente se o perfil não tiver string de persona.

### 4.5 PluginMetadata (`DTL`)

| Field | Number | Type | Value |
|-------|--------|------|-------|
| `provider` | **1** | int32 | ID do provedor |
| `pluginType` | **2** | enum `C4E0` | Ver abaixo |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

Constantes `C4E0` (valor = ordinal do construtor; igualdade ao número do proto é inferida): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Os valores antigos 8/9/15 estão inalterados; o enum é maior.

### 4.6 Oneof de ação (`C61331Rfl`, enum de case `EnumC61601RkN`)

| Number | Case | Tier |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Isto é um oneof de campos de ação, não um enum de valor simples. Onde está embutido não foi rastreado (unknown).

### 4.7 Operação de metadados de AI (transportador Hatch)

| Message | Field | Number | Type |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Protocolo de Requisição (Hatch metadata)

As requisições são construídas por `HF1` (`HatchMetadataRequestManager`), classe de coroutine `HatchMetadataRequestManager$sendRequest$2`. O envelope JSON difere do de 2.26.26.4: `method` e `params` estão aninhados sob `payload`.

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

`params` e `accepts_encoding` são opcionais (found). O request ID não está no JSON; é `BB2.requestId` (uma string aleatória de `C20F.A0x()`).

Caminho de envio (found):
```
HF1.A01(jid, method, ..., params, viewMode, timeoutMs)
  → sendRequest$2: registers onPart callback in A03[requestId] = GuR(method, onPart)
  → JSON → bytes
  → C02381: A04[requestId] = continuation
  → GwX "HatchMetadataSyncHelper/sendMetadataToHatch" → C37393GKy(jidTo, 138, timestampMs)
       .A02 = payload bytes, .A01 = requestId, .A0M = viewMode
  → Hf6: ProtocolMessage.aiMetadataOperation.hatchMetadataSync = BB2{data, timestampMs, requestId}
```

- Requisições pendentes: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) e `HF1.A03` (requestId → `GuR`). Ambos limpos em `finally`. O relatório de 2.26.26.4 nomeava apenas um mapa `A02`.
- Timeout: retorna `GDB.A00` e registra `HatchMetadataRequestManager/sendRequest timed out method=`.
- O inteiro `138` passado para `C37393GKy` não está resolvido (unknown).
- O transportador é `ProtocolMessage.aiMetadataOperation` (campo 31), não uma mensagem de chat simples (mudou).
- O pacote `com.whatsapp.bot.infra.message.aimetadata` contém classes `Ideas*Wire` / `Idea*Wire` (found). A relação delas com os nomes de método é apenas inferida; os nomes de método não foram enumerados.
- O lado de recebimento que completa `A04` não foi rastreado. A correspondência entre uma resposta e o `requestId` é inferida a partir do mapa `A04` e de `BB2.requestId`.

Afirmação de **nenhum namespace XMPP customizado**: nenhum tratamento de `w:ai` / `wa:ai` visto no caminho rastreado; baseado em ausência, não re-verificado exaustivamente.

**Anúncio de capability (found, `C33284Eea`):** quando o destino é o JID do Hatch `…697` (`AbstractC34361Xw.A00`) e um gate passa, o cliente constrói `DPJ` (campo único enum repetido `capabilities` = 1, valores `EnumC32144E2q`) e `C33473Ehf.A06` armazena isso em `BotMetadata.capabilityMetadata` (13) da mensagem de saída, junto com `BotMetadata.timezone` (8) = o ID de `TimeZone` do dispositivo. Capabilities adicionadas por gate:

| Gate | Capability (número do enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Os números são o segundo argumento do construtor do enum; que sejam iguais aos números do proto é inferido. O enum também lista capabilities de rich-response (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Exemplos de requisição (found, chaves de `params` lidas nos pontos de chamada; o destino é o JID do Hatch `…697` salvo quando o ponto de chamada usa o JID da conversa):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | construído em `HatchIdeasManager$execute$job$1` (chaves não lidas); callback `onPart` anexado |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` serializado para JSON; callback `onPart` anexado |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` apenas quando não vazio) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Formato dos bytes em `BB2.data` (found shape, valores de exemplo):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` só é escrito quando o `acceptsGzipResponse` do chamador é verdadeiro; `params` apenas quando não nulo. O callback `onPart` só é registrado em `A03` quando o chamador passa um.

**Mensagem de chat para o bot (found parts):**
- A `Message` de saída é re-envolvida em `Message.botInvokeMessage` (`F2K`, `C33284Eea`), com o wrapper `BD2` contendo a mensagem no campo 1. Em `F2K` o wrap é pulado (a mensagem é definida diretamente) quando `C13S.A00()` é falso, o `A10` da mensagem é falso, ou a flag **10646** está ativa (found).
- `BotMetadata` é construído por `C33473Ehf.A0E` / `A0G`. `A0G` busca o registro de perfil para o JID do bot de destino (`C199358dn.A06(userJid)`, string de persona `C199348dm.A0A`); se essa string estiver vazia, o método retorna sem gravar metadados de bot; caso contrário define `personaId` (2) e, quando presente, `suggestedPromptMetadata` (4) e outras sub-mensagens. A string de persona é armazenada quando o registro de perfil é criado (`C24121Ab2` constrói `<id>$1`; `C223219iv` fixa `1807055946647697$1` para o Hatch). Se `messageContextInfo` fica na `Message` externa ou na mensagem dentro de `botInvokeMessage` não foi resolvido.
- `botMessageInvokerJid` / `isSupportAiMessage` são definidos em `WebMessageInfo` por hooks D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Protocolo de Resposta

### 6.1 Transporte

Não re-verificado conforme afirmado em 2.26.26.4 ("mensagens normais com bytes de `hatchMetadataSync`", classe `Azz`). Found: `hatchMetadataSync` vive em `C25754B9o` dentro de `ProtocolMessage.aiMetadataOperation`. Presumivelmente as respostas do Hatch chegam pelo mesmo caminho e são correspondidas por `requestId` (inferred). Requisições Hatch são chamadas de método; não está demonstrado que sejam o caminho das respostas normais de chat.

### 6.2 Streaming / chunks: não suportado como descrito

A tabela de 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) como um único mecanismo de streaming do Meta AI não é suportada em 2.26.41.6:

| Field | Onde está em 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | `C25834BCt` campo **7** (notificação de history-sync, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) e `C25838BCy` campo **5** (history sync) |
| `isLastChunk` | `C55285Ou6` campo **8** (mensagem com `attestationBundles`, `teeModelConfig`, `violationSignal`; relacionado a TEE) |
| `streamingSidecar` | campo **18** em mensagens de imagem/vídeo/áudio (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | não encontrados como campos proto |

Nenhuma reconstrução de chunks de respostas do Meta AI foi encontrada. O que existe para o Hatch: `GuR(method, onPart)` — um callback `onPart` por requisição (found); que ele carregue resultados parciais é inferido a partir do nome.

### 6.3 Resposta rica (campo 97)

`richResponseMessage` (`DSY`) = campo **97** em `Message`. Existem classes de renderização: `AiRichResponseFooterView` e `UnifiedResponseActionHandlerFactory` (pacote `com.whatsapp.conversationrow.botrichresponse`) (found). Citações: `WebMessageInfo.supportAiCitations` (72). Tipos de conteúdo (imagens, tabelas, código) não re-verificados aqui; ver a pesquisa separada de richResponseMessage.

### 6.4 Indicador de digitação

Saída (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): estado de chat XMPP padrão, sem namespace customizado no código lido.
- Caso simples (sem bot mencionado, ou um JID de bot resolvido para o padrão): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot mencionado no chat: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Enviado via `C10140Tq.A0X` com IQ-type int 4.

Entrada (found, handler de stanza `C40511kx`): um `<chatstate>` com um filho `composing` (opcionalmente `media`) chama o callback genérico de composing com `from`/`participant`; `paused` chama o callback de paused. Nenhum ramo específico de bot foi encontrado neste handler, portanto um `composing` de JID de bot segue o mesmo caminho de qualquer contato (inferred; uma stanza de digitação de bot do lado do servidor não foi observada). `BotMetadata.progressIndicatorMetadata` (12) e a capability `PROGRESS_INDICATOR` existem como um mecanismo de progresso separado dentro da mensagem (apenas nomes, não rastreados).

### 6.5 Sincronização de perfil do bot

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) agenda `BotProfileForChatListWorker` em `A03()`: uma requisição WorkManager marcada `BotProfileSyncManager` com `setBackoffCriteria(policy, 1, MINUTES)` e uma constraint (valor do tipo não resolvido). O 1 minuto é um **backoff** de retry, não um período. O "cerca de ~1 minuto" de 2.26.26.4 não é sustentado (mudou). `A02(groupJid, userJid)` requisita um único perfil (`requestBotProfileResult`). Não faz parte da sincronização normal de roster (inalterado).

Registro de perfil `C199348dm`: tipo de bot (`C1XY`), jid, nome de exibição (`A09`), descrição (`A07`), string de persona (`A0A`), thumbs, timestamp.

### 6.6 Strings de tipo de bot

`C718732k.A00(String)` mapeia: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; qualquer outra coisa se torna `AnonymousClass399(str)`. São rótulos de tipo de bot (também usados em filtros de UI), não valores de `BotMetadata.personaId` (found).

---

## 7. Armazenamento

- `MetaAiMemoryStore`: nenhuma classe com esse nome em 2.26.41.6. O equivalente encontrado é uma tabela `meta_ai_memory` criada pela classe de schema `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, índice `meta_ai_memory_memory_content_index` em `memory_content`. Qual arquivo de banco de dados a contém não está resolvido. Relacionado (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; o nome diz deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (tela de design de chamada de voz, `C29434Cpx`), enums de capability `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), e `BotMetadata.memoryMetadata` (15).
- Chave SharedPrefs `"meta_ai_forward_disclosure_seen"`: presente, booleana, lida em `C230589xr.A03` para `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: presente em `com.whatsapp.metaai.incognito.infra` (found).
- Armazenamento separado dos chats do Meta AI fora de `msgstore.db` (2.26.26.4, não re-verificado): nenhuma classe de chat-store encontrada; `meta_ai_memory` contém apenas fatos de memória, portanto a afirmação não é sustentada nem refutada.

---

## 8. Por que o Baileys não recebe resposta

Todas as linhas são **inferred**: comparação estática entre os requisitos do cliente e um caminho de envio de terceiros; sem teste em produção.

| Issue | Basis in 2.26.41.6 | Tier |
|-------|--------------------|------|
| JID de destino errado | JIDs de bot usam o servidor `bot` (`C24770wv`), não `s.whatsapp.net`; bots por número de telefone mapeiam por uma tabela PN→FBID | found (classe de JID), inferred (efeito) |
| `$1` no JID de roteamento | Não presente. `$1` está na string de ID de persona | found |
| Falta do wrapper `botInvokeMessage` | O cliente envolve a `Message` de saída no campo 67 (`F2K`) | found, requisito inferido |
| Falta de `messageContextInfo.botMetadata` | O cliente grava `personaId`, `invokerJid`, etc. nele | found, requisito inferido |
| `personaId = "meta_ai"` | Não é o que o cliente envia; ele envia a string de persona do perfil (ex. `1807055946647697$1`) | found |
| Falta de `aiConversationContext` | Campo 20 de `BotMetadata`; comportamento no primeiro turno desconhecido | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Campos de WebMessageInfo definidos por hooks do cliente; requisito do servidor desconhecido | unknown |
| `botTargetId` | Nenhum escritor no código do cliente | found |
| Resposta não parseada | `richResponseMessage` é o campo 97 de `Message` | found |
| Reconstrução de chunks | Não suportada pela evidência de 2.26.41.6 (ver 6.2) | found |

---

## 9. Verificação de Assinatura de Bot (autenticidade de conteúdo)

Separado de tudo acima: um mecanismo que permite ao cliente **receptor** verificar que o conteúdo de `richResponseMessage` genuinamente veio do backend de AI da Meta, independentemente de quem retransmitiu a mensagem. As descobertas estáticas abaixo são `found` no código de 2.26.41.6; o resultado do replay em 9.4 é `tested` (ao vivo, na própria conta do autor — não interceptação de tráfego, um cliente legítimo compondo e retransmitindo sua própria mensagem).

### 9.1 Localização no proto

`BotMetadata.verificationMetadata` — campo **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), tipo `DPC`/`BotSignatureVerificationMetadata` (o toString revela o nome real): `proofs[]`, cada uma uma `BotSignatureVerificationUseCaseProof` com `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (bytes repetidos, DER X.509).

### 9.2 Algoritmo de verificação

Classe `C33259EeB`, nome interno `BotSignatureVerificationUtils` (a partir de strings de log):

1. **Validação da cadeia de certificados** de `certificateChain` contra uma trust anchor, via `HFg.A01(date, certs, true)`.
2. **Construção dos bytes assinados**: `"1" + <string do número de telefone> + <bytes de unifiedResponse>` — a assinatura vincula **conteúdo e um número de telefone juntos**, não o conteúdo isoladamente.
3. **Verificação EdDSA** (log: `"EdDSA signature verification result"`) usando a chave Ed25519 bruta extraída do SubjectPublicKeyInfo do certificado folha.
4. **Modo de enforcement**, lido da config **19590**, enum `EnumC32057Dzg`: `NONE` (`"none"`, desativado, sempre passa), `LOG_ONLY` (`"log_only"`, verifica + registra, nunca bloqueia), `ENFORCE_BLOCKING` (`"enforce_blocking"`, uma verificação falha retorna `false`). Resultado armazenado como `E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, persistido na coluna SQLite `bot_message_info.signature_validation_status` (a tabela também tem `bot_client_public_key`).

### 9.3 Gate de renderização de linha

`C30085D6v.A00` (dispatcher de tipo de linha) e `EOK`/`C32608EKo`: se o status da assinatura é `FAILED` e a flag **27635** está ativa → linha mascarada `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Independentemente, se o JID do remetente não está presente no armazenamento de perfis de bot sincronizados localmente (`C224899mg`, a mesma sincronização de `BotProfileSyncManagerImpl`) e a flag **27355** está ativa → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), uma preview com gate de consentimento em vez de um bloqueio rígido.

### 9.4 Captura real e replay ao vivo (tested)

Uma resposta genuína do Meta AI, capturada no lado do cliente em uma conversa real (própria conta, decifrada pelo próprio cliente do autor — não interceptação de tráfego), trazia:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, uma `signature` de 64 bytes (tamanho Ed25519), uma `certificateChain` com 2 entradas.
- Certificado folha: `CN=svc:wa-bot-msg-leaf`, chave Ed25519, emitido por `Meta WA SS Int CA 2025-09`, encadeando até `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`), validade de ≈7 meses (certificado de serviço com rotação automática) — a chave privada de assinatura existe apenas no backend da Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — um nome de backend de bot não documentado anteriormente (ver também "Hatch" nas seções 1–6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, um campo irmão de `botMetadata`.
- Formato de entrega: `protocolMessage` com `type: MESSAGE_EDIT`, `editedMessage.richResponseMessage` (a primeira resposta em uma thread chega pré-envolvida como uma edição de um placeholder), `key.remoteJid` = o próprio JID do autor.

**Teste:** o `richResponseMessage` + `messageContextInfo.botMetadata` exatos (assinatura e cadeia de certificados byte a byte inalteradas) foram retransmitidos via `relayMessage` a partir do próprio dispositivo do autor — não do JID do bot `867051314767696@bot` — para o próprio número do autor (o mesmo número já embutido nos bytes assinados).

**Resultado:** o conteúdo foi renderizado com o estilo "AI" completo e o texto real, rotulado "Forwarded". Algumas entregas do mesmo payload idêntico mostraram em vez disso "WhatsApp can't verify the security of this media. Only download if you trust the sender." com uma ação Download; tocar em Download revelou o conteúdo idêntico, correspondendo ao status `DOWNLOAD_CONSENT_ACCEPTED` e ao caminho de código "unknown sender with unconsented content" de 9.3. Uma entrega mostrou um fallback genérico "your version of WhatsApp doesn't support it" em vez disso; causa não estabelecida (unknown).

**Conclusão (tested):** a verificação criptográfica em 9.2 vincula-se a *(conteúdo, número de telefone)*, não à identidade ou ao JID do remetente ao vivo. Um `richResponseMessage` validamente assinado pode ser reproduzido (replay) a partir de um remetente que não é o bot e ainda passar a verificação de assinatura, desde que o número do destinatário corresponda ao número embutido na assinatura — o cliente receptor o renderiza como conteúdo de AI genuíno (no máximo com um passo de consentimento cosmético de um toque, "unknown sender", não um bloqueio rígido). Isto é um mecanismo de autenticidade de conteúdo, não de autenticidade de remetente; a própria criptografia da camada Signal do WhatsApp, não esta assinatura, é o que autentica o remetente ao vivo.

---

## 10. Correção para o Baileys

Nenhuma implementação funcional é reivindicada. O que segue é um esboço estrutural de onde os campos vivem conforme 2.26.41.6, marcado como **inferred**; não foi executado contra um servidor.

### 9.1 Destino

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Se a string de servidor `bot` funciona como um alvo de relay do Baileys, e como o servidor deriva o `to` final da stanza, é desconhecido.

### 9.2 Posicionamento de campos (apenas formato)

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

- A inclusão de `botMetadata` em `messageContextInfo` (campo 7) é **found**. `capabilityMetadata` (13) e `timezone` (8) são escritos pelo cliente apenas para destinos Hatch (found); seu requisito do lado do servidor é desconhecido. Se o proto do `baron-baileys-v2` já tem esses campos não foi verificado; se não, o proto precisa ser estendido (inferred).
- `isSupportAiMessage` (70) e `botMessageInvokerJid` (58) são campos de `WebMessageInfo`. Se precisam estar presentes na wire é desconhecido; não os coloque em `contextInfo` (isso estava errado no relatório de 2.26.26.4).
- `botTargetId`: nenhum escritor do cliente em nenhum lugar do código decompilado (found); não defina esse campo.
- Envolvimento exato (`botInvokeMessage.message` contendo a mensagem real vs. ao lado dela) segue o re-wrapping de `F2K` / `C33284Eea`; o resultado serializado exato não foi reproduzido (unknown).

### 9.3 Tratamento de resposta

- Respostas ricas: `Message.richResponseMessage` é o campo **97** (found). Parseie esse campo, não o 77.
- Remover tratamento de chunks: `chunkOrder` / `isLastChunk` não são campos de streaming do Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) do Hatch é o canal de requisição JSON; não está demonstrado que respostas de chat normais usem esse canal.

### 9.4 Contexto de conversa

`BotMetadata.aiConversationContext` (20) existe. Que o servidor retorne estado atualizado nas respostas e que ele precise ser ecoado de volta é **inferred** (a partir do nome do campo e do relatório de 2.26.26.4); não verificado.

---

## 11. Fluxos

### 10.1 Mensagem de chat para o bot (found no lado do cliente, inferred no lado do servidor)

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

### 10.2 Requisição de metadados Hatch (found no lado do cliente)

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

## 12. Mudanças em relação a 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legado, flag 25119 | Não presente. 25119 apenas em tabelas de flag, nenhum leitor |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 são servidor `bot` (`C24770wv`); 165332417282214 é `lid` (`C14080dr`) |
| Novas constantes de JID | nenhuma listada | `1807055946647699` (envelope de bot do CoEx v2 / alvo de conjunto de dispositivos), `2942131436135992` (JID do perfil Meta AI padrão, teste de JID de bot `A07`), `867051314767696555` (segundo membro de `A07`, propósito desconhecido), `17015557208` (PN do Meta AI, `A04`) |
| Sufixo `$1` | No JID de roteamento, `C1A2.A00/A01` | Não no JID; acrescentado à string de ID de persona (`C24121Ab2`, `C223219iv`) |
| Conversão de roteamento | Append de `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot via tabela FBID |
| Nomes de flag 25119/26189/27083 | Nomes de flag `ai_*` | As strings são entradas de lista de features (`C25056AqU`); 26190 = JSON do perfil Hatch; 37227/37852/37054 controlam os valores de capability Hatch 76 / 77 / 79 |
| `richResponseMessage` | Campo 77 | Campo 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 em "WebMessageInfo" | 67 / 100 / 104 em `Message`; também 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nunca escrito |
| Localização de BotMetadata | "embutido na mensagem" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | String de persona do perfil, ex. `1807055946647697$1`; `meta_ai` é um rótulo de tipo de bot |
| Tipos de plugin | 8, 9, 15 | Os mesmos, enum tem 18 valores (até 17) |
| Enum de ação | Enum de valor 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Envelope JSON do Hatch | `method`, `params` no nível superior | Aninhados sob `payload`; adiciona `accepts_encoding` |
| Transportador do Hatch | Mensagem padrão, classe `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; adiciona `bizAiMetadataSync` (2) |
| Verificação de assinatura de bot | não documentado | Novo: `BotMetadata.verificationMetadata` (27), EdDSA + cadeia de certificado X.509 sobre (conteúdo, número de telefone); testado ao vivo, vincula-se ao número de telefone, não ao remetente ao vivo (seção 9) |
| Mapas de pendentes | Um (`A02`) | Dois: continuations `A04`, callbacks de parte `GuR` em `A03` |
| Campos de streaming | Uma tabela de chunk do Meta AI | `chunkOrder` (history sync), `isLastChunk` (mensagem TEE), `streamingSidecar` (mídia); `clientStreaming`/`serverStreaming` não encontrados |
| Intervalo de sync de perfil | "a cada ~1 min" | 1 min é backoff do WorkManager, não um período |
| `MetaAiMemoryStore` | Presente | Não encontrado por esse nome; tabela `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) encontrada |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Presente | Presente |
| Indicador de digitação (chatstates) | Encontrado | Encontrado: saída `<chatstate><composing/></chatstate>`, com `<bot jid/>` quando um bot é mencionado (`C199098dN.A01`); entrada `composing`/`paused` via handler genérico `C40511kx`, sem ramo específico de bot |
| Anúncio de capability | não documentado | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) para o Hatch; flags 37227 / 37852 / 37054 mapeiam para os valores de enum 76 / 77 / 79 |
| Exemplos de requisição Hatch | não documentado | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
