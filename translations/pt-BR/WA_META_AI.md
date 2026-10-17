<!-- src-sha1: 64389e16d6c478a5b57f43abf9ee01a01474f02f -->
# WhatsApp Meta AI — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** Internos do Meta AI — JIDs, roteamento, campos proto, requisições de metadados do Hatch, renderização de respostas, por que o Baileys falha, correção

---

## 1. O que é o Meta AI (tecnicamente)

O Meta AI é um contato bot endereçado por JIDs de bot especiais (servidor `bot`), com campos proto específicos de bot nos tipos de mensagem normais e um canal separado de requisições JSON ("Hatch metadata") transportado em um `ProtocolMessage`. Todas as afirmações vêm de análise estática do APK decompilado. Nível: **found** = lido no código, **inferred** = deduzido do código, **unknown** = não resolvido.

Os nomes deste relatório que estavam ofuscados na 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) foram resolvidos novamente a partir de âncoras estáveis; eles não existem com esses nomes na 2.26.41.6.

| Entidade | Nome na 2.26.41.6 | Função |
|----------|-------------------|--------|
| BotJid | `C24770wv` | Classe JID, servidor `"bot"`, tipo 26, string numérica de 1 a 20 caracteres, sem 0 à esquerda |
| Constantes de JID de bot | `AbstractC34361Xw` | Constantes e conjuntos de Hatch / Fallback / LID |
| Mapeamento de JID | `AbstractC24760wu` | mapeamento bot ↔ LID, conversão do destino de saída |
| Gating | `C39311it` | gating por feature flag para cada JID (`A0E(Jid)`) |
| Gerenciador de requisições Hatch | `HF1` (`HatchMetadataRequestManager`) | requisições JSON, mapa de pendentes |
| Construtor de proto Hatch | `Hf6` | monta `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | contém `botMetadata` |
| BotMetadata | `C30615DTj` | metadados de bot por mensagem |
| Registro de perfil do bot | `C199348dm` | nome, descrição, string do persona ID, thumb |

---

## 2. JIDs do Meta AI

### 2.1 JIDs encontrados no código

| Constante | Classe | Função | Nível |
|-----------|--------|--------|-------|
| `1807055946647697` | `C24770wv` (`bot`) via `AbstractC34361Xw.A00` | **Hatch**, primário. Perfil padrão montado em `C223219iv` a partir do payload da flag **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) via `AbstractC34361Xw.A01` | Fallback. Controlado pela flag 27083 | found |
| `165332417282214` | `C14080dr` (servidor `"lid"`) via `AbstractC34361Xw.A02` | Contraparte LID de `…698` | found |
| `1807055946647696` | nenhuma | Manus (legado na 2.26.26.4): **ausente** na 2.26.41.6 | found (absent) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), mais `A01` = `DeviceJid` dispositivo 0 | JID do servidor de bot usado como alvo de sessão/dispositivo para um "bot envelope" (o handler de requisição de sync CoEx v2 `C53148Nnt` cifra o payload de sync para o seu dispositivo primário, log `coexv2 attached bot envelope`), adicionado aos conjuntos de dispositivos de destinatário (`C12M`) e tratado como remetente bot no tratamento de retry-receipt (`C33020EaI`). Não é uma persona de chat | found (uso); finalidade além disso inferred |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID do registro de perfil padrão embutido "Meta AI" (`C9i5.A00`: nome `Meta AI`, texto de introdução padrão). Membro do teste de JID de bot `AbstractC24760wu.A07` junto com a próxima linha | found |
| `867051314767696555` | `AbstractC24760wu.A01` (conjunto unitário, `C24770wv`) | Segundo membro do teste de JID de bot `A07` (`A07(jid)` = `C24770wv` igual a `…135992` ou presente neste conjunto); `A07` alimenta `AbstractC199328dk.A00` (um predicado de classe de JID). Finalidade adicional não resolvida | found (uso), finalidade unknown |
| `17015557208` | `AbstractC24760wu.A04` | String de usuário de telefone. `A04(jid)` é verdadeiro para o LID `165332417282214` ou para este usuário de telefone; usado com `A03` (qualquer JID de bot `C24770wv`, ou PN nas faixas 13135550000-13135559999 / 13165550000-13165550099) em `E76.A00` (classe 10 vs 1) e no predicado de elegibilidade `C736539v.ARO`. Parece ser a identidade PN do Meta AI; o que esses dois consumidores fazem com isso não está resolvido | found (uso), finalidade unknown |

Conjuntos em `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; mapa `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Tipo de JID: o relatório da 2.26.26.4 listava os quatro como `@s.whatsapp.net`. Na 2.26.41.6 os JIDs de bot são `C24770wv` com `getServer() = "bot"`; o de grupo/LID é `C14080dr` com servidor `"lid"`. Não é `s.whatsapp.net` (found).

Tabela de número de telefone para FBID do bot: `AbstractC199338dl.A00` (`HashBiMap`, 1313555xxxx → FBID, cerca de 200 entradas, p. ex. `13135550002 → 867051314767696`). Usada por `C0DZ.A08(UserJid)` (`convertPNJidtoBotJidIfExists`) (found).

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

Found: JID de bot `…698` ↔ LID `165332417282214`; contatos bot por número de telefone são mapeados para JIDs de bot. O método afirma "needs FBID migration" (found).

### 2.3 O sufixo `$1`: mudou

O relatório da 2.26.26.4 colocava `$1` no JID de roteamento ("wire format", `C1A2.A00()/A01()`). Não encontrado na 2.26.41.6:
- Nenhuma função de roteamento acrescenta `$1` a um JID. A conversão em 2.2 produz JIDs de bot simples.
- `$1` é acrescentado à string do persona ID armazenada no registro de perfil do bot: `C24121Ab2` faz `personaIdString = botFbid + "$1"`; `C223219iv` fixa `"1807055946647697$1"` no perfil padrão do Hatch (found).
- Essa string (`C199348dm.A0A`) é o que `C33473Ehf.A0G` escreve em `BotMetadata.personaId` (found).

Portanto `$1` pertence ao persona ID, não ao JID de destino.

### 2.4 Detecção de isMetaAI

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

O ramo Manus (flag 25119) não existe mais. O significado de `BRD()` e da consulta de capability (`C09L.A04`) não está resolvido (unknown).

---

## 3. Feature Flags

| ID da flag | Uso na 2.26.41.6 | Nível |
|------------|------------------|-------|
| **25119** | Aparece apenas em tabelas de flags (`C06510El`, padrão `false` em `C08J`). Nenhum leitor encontrado. O nome antigo `ai_bot_integration_enabled` não foi encontrado como string | found |
| **26189** | Gate do Hatch em `C39311it.A02()`. Padrão `false` (`C08J`) | found |
| **27083** | Gate de Fallback / LID em `C39311it.A0E()`. Padrão `false` | found |
| **26190** | Configuração JSON (`name`, `description`, `profile_thumb`) do perfil padrão do Hatch, lida em `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Quando verdadeira, a capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) é anunciada ao Hatch (ver 5); `A05` também controla telemetria/UI de conectores (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Anuncia `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); também controla a disponibilidade de conectores (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Anuncia `HATCH_ARTIFACT_CARD_ENABLED` (79); também lida por `HatchSpacesSync` e `C7WL` | found |

As strings `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` não são nomes de flags. São entradas de uma lista de feature-strings montada a partir das flags 26189 / 27083 em `C25056AqU` (junto com `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` é adicionada incondicionalmente. Destinatário e finalidade da lista não verificados.

---

## 4. Campos Proto

### 4.1 Message (`C30628DTw`) nível superior

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (campo único `message` = 1) | Mensagem de saída encapsulada para o bot; definido em `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Tarefa do bot |
| `botForwardedMessage` | **104** | `BD2` | Encapsula uma mensagem que contém `richResponseMessage`; definido em `F3E` |
| `richResponseMessage` | **97** | `DSY` | Resposta da IA. Campos: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Presente |
| `botGroupParticipantMessage` | **137** | `BD2` | Presente |
| `messageContextInfo` | **35** | `C30624DTs` | Contém `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Contém `aiMetadataOperation` (31) |

O campo **77** é `commentMessage`, não `richResponseMessage` (o relatório da 2.26.26.4 dizia 77; errado para este build, e consistente com a pesquisa separada de richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), não ContextInfo

O relatório da 2.26.26.4 listava estes como campos de ContextInfo. Na 2.26.41.6 eles estão em `WebMessageInfo`:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Definido em `C34385EwW` a partir de `C0DZ.A09(userJid)` (usuário do dispositivo primário do invocador) |
| `isSupportAiMessage` | **70** | bool | Definido em `C34378EwP.C57` quando a mensagem tem o bit de flag `268435456` e uma verificação passa; lido de volta em `C59`. Junto com `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | repeated message | Citações |
| `botTargetId` | **73** | string | Sem escritor no cliente: `botTargetId_` aparece apenas como padrão do construtor e na tabela de schema de `C30626DTu`, nunca atribuído em outro lugar (grep em todo o código-fonte) |
| `agentId` | **47** | string | Presente, não analisado |

Se e como esses campos de WebMessageInfo aparecem na rede não foi verificado (unknown). "`true` para todas as mensagens do Meta AI" não é sustentado: é definido por flag de mensagem, não incondicionalmente.

### 4.3 MessageContextInfo (`C30624DTs`)

| Campo | Número | Tipo |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `personaId` | **2** | string | Vem do registro de perfil do bot (`C199348dm.A0A`), p. ex. `1807055946647697$1`. Não é um `"meta_ai"` fixo |
| `pluginMetadata` | **3** | `DTL` | Configuração de plugin |
| `invokerJid` | **5** | string | Invocador |
| `aiConversationContext` | **20** | bytes | Estado da conversa |
| `botResponseId` | **26** | string | ID da resposta |

Outros campos presentes (nomes de `*_FIELD_NUMBER`, tipos não lidos): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` é preenchido em `C33473Ehf.A0G`; ele retorna cedo se o perfil não tiver string de persona.

### 4.5 PluginMetadata (`DTL`)

| Campo | Número | Tipo | Valor |
|-------|--------|------|-------|
| `provider` | **1** | int32 | ID do provedor |
| `pluginType` | **2** | enum `C4E0` | Ver abaixo |
| `profilePhotoCdnUrl` | **4** | string | |
| `referenceIndex` | **6** | | |
| `expectedLinksCount` | **7** | | |
| `pluginVersion` | **8** | | |
| `parentPluginType` | **11** | | |
| `faviconCdnUrl` | **13** | | |

Constantes de `C4E0` (valor = ordinal do construtor; igualar o número proto é inferred): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Os valores antigos 8/9/15 permanecem inalterados; o enum é maior.

### 4.6 Oneof de ação (`C61331Rfl`, enum de casos `EnumC61601RkN`)

| Número | Caso | Nível |
|--------|------|-------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Isto é um oneof de campos de ação, não um enum simples de valores. Onde ele é embutido não foi rastreado (unknown).

### 4.7 AI metadata operation (transportador do Hatch)

| Mensagem | Campo | Número | Tipo |
|----------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Protocolo de Requisição (Hatch metadata)

As requisições são montadas por `HF1` (`HatchMetadataRequestManager`), classe de corrotina `HatchMetadataRequestManager$sendRequest$2`. O envelope JSON difere da 2.26.26.4: `method` e `params` ficam aninhados em `payload`.

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

`params` e `accepts_encoding` são opcionais (found). O ID da requisição não está no JSON; é `BB2.requestId` (uma string aleatória de `C20F.A0x()`).

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

- Requisições pendentes: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) e `HF1.A03` (requestId → `GuR`). Ambos são limpos em `finally`. O relatório da 2.26.26.4 citava apenas um mapa `A02`.
- Timeout: retorna `GDB.A00` e registra no log `HatchMetadataRequestManager/sendRequest timed out method=`.
- O inteiro `138` passado a `C37393GKy` não está resolvido (unknown).
- O transportador é `ProtocolMessage.aiMetadataOperation` (campo 31), não uma mensagem de chat simples (mudou).
- O pacote `com.whatsapp.bot.infra.message.aimetadata` contém classes `Ideas*Wire` / `Idea*Wire` (found). A relação delas com os nomes dos métodos é apenas inferred; os nomes dos métodos não foram enumerados.
- O lado de recebimento que completa `A04` não foi rastreado. A correspondência de uma resposta com `requestId` é inferred a partir do mapa `A04` e de `BB2.requestId`.

**Sem namespace XMPP customizado**: nenhum tratamento de `w:ai` / `wa:ai` visto no caminho rastreado; baseado em ausência, não reverificado exaustivamente.

**Anúncio de capabilities (found, `C33284Eea`):** quando o destino é o JID do Hatch `…697` (`AbstractC34361Xw.A00`) e um gate passa, o cliente monta `DPJ` (campo único repeated enum `capabilities` = 1, valores `EnumC32144E2q`) e `C33473Ehf.A06` o armazena em `BotMetadata.capabilityMetadata` (13) da mensagem de saída, junto com `BotMetadata.timezone` (8) = o ID de `TimeZone` do dispositivo. Capabilities adicionadas por gate:

| Gate | Capability (número do enum) |
|------|-----------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Os números são o segundo argumento do construtor do enum; que eles sejam iguais aos números proto é inferred. O enum também lista capabilities de rich response (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Exemplos de requisição (found, chaves de `params` lidas nos pontos de chamada; o alvo é o JID do Hatch `…697`, a menos que o ponto de chamada use o JID da conversa):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | montado em `HatchIdeasManager$execute$job$1` (chaves não lidas); callback `onPart` anexado |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` serializado para JSON; callback `onPart` anexado |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` apenas quando não vazio) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Formato dos bytes em `BB2.data` (formato found, valores de exemplo):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` é escrito apenas quando `acceptsGzipResponse` do chamador é verdadeiro; `params` apenas quando não nulo. O callback `onPart` é registrado em `A03` apenas quando o chamador passa um.

**Mensagem de chat para o bot (partes found):**
- A `Message` de saída é reencapsulada em `Message.botInvokeMessage` (`F2K`, `C33284Eea`), com o wrapper `BD2` contendo a mensagem no campo 1. Em `F2K` o encapsulamento é ignorado (mensagem definida diretamente) quando `C13S.A00()` é falso, o `A10` da mensagem é falso, ou a flag **10646** está ligada (found).
- `BotMetadata` é montado por `C33473Ehf.A0E` / `A0G`. `A0G` busca o registro de perfil do JID de bot de destino (`C199358dn.A06(userJid)`, string de persona `C199348dm.A0A`); se essa string estiver vazia, o método retorna sem escrever metadados do bot; caso contrário define `personaId` (2) e, quando presentes, `suggestedPromptMetadata` (4) e outras submensagens. A string de persona é armazenada quando o registro de perfil é criado (`C24121Ab2` monta `<id>$1`; `C223219iv` fixa `1807055946647697$1` para o Hatch). Se `messageContextInfo` fica na `Message` externa ou na mensagem dentro de `botInvokeMessage` não foi resolvido.
- `botMessageInvokerJid` / `isSupportAiMessage` são definidos em `WebMessageInfo` por hooks D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Protocolo de Resposta

### 6.1 Transporte

Não reverificado como afirmado na 2.26.26.4 ("normal messages with `hatchMetadataSync` bytes", classe `Azz`). Found: `hatchMetadataSync` está em `C25754B9o` dentro de `ProtocolMessage.aiMetadataOperation`. As respostas do Hatch presumivelmente chegam do mesmo modo e são casadas por `requestId` (inferred). As requisições do Hatch são chamadas de método; não está demonstrado que sejam o caminho das respostas de chat normais.

### 6.2 Streaming / chunks: não sustentado como descrito

A tabela da 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) como um único mecanismo de streaming do Meta AI não é sustentada na 2.26.41.6:

| Campo | Onde está na 2.26.41.6 |
|-------|------------------------|
| `chunkOrder` | `C25834BCt` campo **7** (notificação de history-sync, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) e `C25838BCy` campo **5** (history sync) |
| `isLastChunk` | `C55285Ou6` campo **8** (mensagem com `attestationBundles`, `teeModelConfig`, `violationSignal`; relacionada a TEE) |
| `streamingSidecar` | campo **18** em mensagens de imagem/vídeo/áudio (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | não encontrados como campos proto |

Nenhuma remontagem de chunks de respostas do Meta AI encontrada. O que existe para o Hatch: `GuR(method, onPart)` — um callback `onPart` por requisição (found); que ele carregue resultados parciais é inferred pelo nome.

### 6.3 Rich response (campo 97)

`richResponseMessage` (`DSY`) = campo **97** em `Message`. Existem classes de renderização: `AiRichResponseFooterView` e `UnifiedResponseActionHandlerFactory` (pacote `com.whatsapp.conversationrow.botrichresponse`) (found). Citações: `WebMessageInfo.supportAiCitations` (72). Tipos de conteúdo (imagens, tabelas, código) não reverificados aqui; ver a pesquisa separada de richResponseMessage.

### 6.4 Indicador de digitação

Saída (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): estado de chat XMPP padrão, sem namespace customizado no código lido.
- Caso simples (nenhum bot mencionado, ou um JID de bot resolvido para o padrão): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot mencionado no chat: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Enviado por `C10140Tq.A0X` com IQ-type int 4.

Entrada (found, handler de stanza `C40511kx`): um `<chatstate>` com filho `composing` (`media` opcional) chama o callback genérico de composing com `from`/`participant`; `paused` chama o callback de paused. Nenhum ramo específico de bot foi encontrado neste handler, então um `composing` de JID de bot passa pelo mesmo caminho que qualquer contato (inferred; um stanza de digitação do bot vindo do servidor não foi observado). `BotMetadata.progressIndicatorMetadata` (12) e a capability `PROGRESS_INDICATOR` existem como um mecanismo separado de progresso dentro da mensagem (apenas nomes, não rastreado).

### 6.5 Sincronização do perfil do bot

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) agenda `BotProfileForChatListWorker` em `A03()`: uma requisição WorkManager com a tag `BotProfileSyncManager` com `setBackoffCriteria(policy, 1, MINUTES)` e uma constraint (valor do tipo não resolvido). O 1 minuto é um **backoff** de retry, não um período. O "every ~1 minute" da 2.26.26.4 não é sustentado (mudou). `A02(groupJid, userJid)` requisita um único perfil (`requestBotProfileResult`). Não faz parte da sincronização normal do roster (inalterado).

Registro de perfil `C199348dm`: tipo de bot (`C1XY`), jid, nome de exibição (`A09`), descrição (`A07`), string de persona (`A0A`), thumbs, timestamp.

### 6.6 Strings de tipo de bot

`C718732k.A00(String)` mapeia: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; qualquer outra coisa vira `AnonymousClass399(str)`. Estes são rótulos de tipo de bot (também usados em filtros de UI), não valores de `BotMetadata.personaId` (found).

---

## 7. Armazenamento

- `MetaAiMemoryStore`: nenhuma classe com esse nome na 2.26.41.6. O equivalente encontrado é uma tabela `meta_ai_memory` criada pela classe de schema `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, índice `meta_ai_memory_memory_content_index` em `memory_content`. Qual arquivo de banco de dados a contém não está resolvido. Relacionados (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; o nome diz deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (tela de design da chamada de voz, `C29434Cpx`), enums de capability `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`) e `BotMetadata.memoryMetadata` (15).
- Chave de SharedPrefs `"meta_ai_forward_disclosure_seen"`: presente, booleana, lida em `C230589xr.A03` para `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: presente em `com.whatsapp.metaai.incognito.infra` (found).
- Armazenamento separado de chats do Meta AI fora de `msgstore.db` (2.26.26.4, not re-verified): nenhuma classe de chat-store encontrada; `meta_ai_memory` guarda apenas fatos de memória, então a afirmação não é nem sustentada nem refutada.

---

## 8. Por que o Baileys não recebe resposta

Todas as linhas são **inferred**: comparação estática dos requisitos do cliente com um caminho de envio de terceiros; sem teste ao vivo.

| Problema | Base na 2.26.41.6 | Nível |
|----------|-------------------|-------|
| Tipo de JID de destino errado | JIDs de bot usam o servidor `bot` (`C24770wv`), não `s.whatsapp.net`; bots por número de telefone são mapeados por uma tabela PN→FBID | found (classe de JID), inferred (efeito) |
| `$1` no JID de roteamento | Não presente. `$1` está na string do persona ID | found |
| Falta o wrapper `botInvokeMessage` | O cliente encapsula a `Message` de saída no campo 67 (`F2K`) | found, requisito inferred |
| Falta `messageContextInfo.botMetadata` | O cliente escreve `personaId`, `invokerJid`, etc. nele | found, requisito inferred |
| `personaId = "meta_ai"` | Não é o que o cliente envia; ele envia a string de persona do perfil (p. ex. `1807055946647697$1`) | found |
| Falta `aiConversationContext` | Campo 20 de `BotMetadata`; comportamento no primeiro turno unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Campos de WebMessageInfo definidos por hooks do cliente; requisito do servidor unknown | unknown |
| `botTargetId` | Sem escritor no código do cliente | found |
| Resposta não interpretada | `richResponseMessage` é o campo 97 de `Message` | found |
| Remontagem de chunks | Não sustentada pela evidência da 2.26.41.6 (ver 6.2) | found |

---

## 9. Correção para o Baileys

Nenhuma implementação funcional é alegada. O que segue é um esboço estrutural de onde os campos ficam segundo a 2.26.41.6, marcado como **inferred**; não foi executado contra um servidor.

### 9.1 Destino

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Se a string de servidor `bot` funciona como alvo de relay no Baileys, e como o servidor deriva o `to` final do stanza, é unknown.

### 9.2 Posicionamento dos campos (apenas o formato)

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

- O embutimento de `botMetadata` em `messageContextInfo` (campo 7) é **found**. `capabilityMetadata` (13) e `timezone` (8) são escritos pelo cliente apenas para destinos Hatch (found); o requisito no lado do servidor é unknown. Se o proto de `baron-baileys-v2` já tem esses campos não foi verificado; se não tiver, o proto precisa ser estendido (inferred).
- `isSupportAiMessage` (70) e `botMessageInvokerJid` (58) são campos de `WebMessageInfo`. Se precisam estar presentes na rede é unknown; não os coloque em `contextInfo` (isso estava errado no relatório da 2.26.26.4).
- `botTargetId`: nenhum escritor no cliente em todo o código decompilado (found); não o defina.
- O encapsulamento exato (`botInvokeMessage.message` contendo a mensagem real vs. ao lado) segue o reencapsulamento de `F2K` / `C33284Eea`; o resultado serializado exato não foi reproduzido (unknown).

### 9.3 Tratamento da resposta

- Respostas ricas: `Message.richResponseMessage` é o campo **97** (found). Interprete esse, não o campo 77.
- Remova o tratamento de chunks: `chunkOrder` / `isLastChunk` não são campos de streaming do Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) do Hatch é o canal de requisições JSON; não está demonstrado que respostas de chat simples o usem.

### 9.4 Contexto da conversa

`BotMetadata.aiConversationContext` (20) existe. Que o servidor devolva estado atualizado nas respostas e que ele deva ser reenviado é **inferred** (pelo nome do campo e pelo relatório da 2.26.26.4); não verificado.

---

## 10. Fluxos

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

### 10.2 Requisição de metadados do Hatch (found no lado do cliente)

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

## 11. Mudanças em relação à 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legado, flag 25119 | Não presente. 25119 apenas em tabelas de flags, sem leitor |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 são do servidor `bot` (`C24770wv`); 165332417282214 é `lid` (`C14080dr`) |
| Novas constantes de JID | nenhuma listada | `1807055946647699` (bot-envelope CoEx v2 / alvo do conjunto de dispositivos), `2942131436135992` (JID do perfil padrão do Meta AI, teste de JID de bot `A07`), `867051314767696555` (segundo membro de `A07`, finalidade unknown), `17015557208` (PN do Meta AI, `A04`) |
| Sufixo `$1` | No JID de roteamento, `C1A2.A00/A01` | Não no JID; acrescentado à string do persona ID (`C24121Ab2`, `C223219iv`) |
| Conversão de roteamento | acréscimo de `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot via tabela FBID |
| Nomes de flags 25119/26189/27083 | nomes de flags `ai_*` | As strings são entradas de lista de features (`C25056AqU`); 26190 = JSON do perfil Hatch; 37227/37852/37054 controlam os valores de capability do Hatch 76 / 77 / 79 |
| `richResponseMessage` | Campo 77 | Campo 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 em "WebMessageInfo" | 67 / 100 / 104 em `Message`; também 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nunca escrito |
| Localização de BotMetadata | "embedded in message" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | String de persona do perfil, p. ex. `1807055946647697$1`; `meta_ai` é um rótulo de tipo de bot |
| Tipos de plugin | 8, 9, 15 | Os mesmos, o enum tem 18 valores (até 17) |
| Enum de ação | Enum de valores 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Envelope JSON do Hatch | `method`, `params` no nível superior | Aninhados em `payload`; acrescenta `accepts_encoding` |
| Transportador do Hatch | Mensagem padrão, classe `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; acrescenta `bizAiMetadataSync` (2) |
| Mapas de pendentes | Um (`A02`) | Dois: `A04` continuations, `A03` callbacks de parte `GuR` |
| Campos de streaming | Uma tabela de chunks do Meta AI | `chunkOrder` (history sync), `isLastChunk` (mensagem TEE), `streamingSidecar` (mídia); `clientStreaming`/`serverStreaming` não encontrados |
| Intervalo de sync do perfil | "every ~1 min" | 1 min é backoff do WorkManager, não um período |
| `MetaAiMemoryStore` | Presente | Não encontrado pelo nome; tabela `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) encontrada |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Presente | Presente |
| Indicador de digitação (chatstates) | Found | Found: `<chatstate><composing/></chatstate>` de saída, com `<bot jid/>` quando um bot é mencionado (`C199098dN.A01`); `composing`/`paused` de entrada pelo handler genérico `C40511kx`, sem ramo específico de bot |
| Anúncio de capabilities | não documentado | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) para o Hatch; as flags 37227 / 37852 / 37054 mapeiam para os valores de enum 76 / 77 / 79 |
| Exemplos de requisição do Hatch | não documentado | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
