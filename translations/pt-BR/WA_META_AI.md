<!-- src-sha1: 92bebfe6214e20e4e50526fbb6583d35cc44e808 -->
# WhatsApp Meta AI — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-10-17
**Escopo:** internos do Meta AI — JIDs, roteamento, campos proto, requisições de metadados Hatch, renderização de resposta, por que o Baileys falha, correção

---

## 1. O que é o Meta AI (tecnicamente)

O Meta AI é um contato bot endereçado por JIDs de bot especiais (servidor `bot`), com campos proto específicos de bot nos tipos de mensagem normais e um canal de requisição JSON separado ("metadados Hatch") carregado em um `ProtocolMessage`. Todas as afirmações são análise estática do APK decompilado. Tier: **found** = lido em código, **inferred** = deduzido do código, **unknown** = não resolvido.

Nomes neste relatório que estavam obfuscados na 2.26.26.4 (`C1A2`, `B2Y`, `B2C`, `Azz`, `C26654Bv8`) foram re-resolvidos a partir de âncoras estáveis; eles não existem sob esses nomes na 2.26.41.6.

| Entidade | Nome na 2.26.41.6 | Papel |
|--------|----------------|------|
| BotJid | `C24770wv` | classe JID, servidor `"bot"`, tipo 26, string numérica de 1-20 chars, sem zero à esquerda |
| Constantes de JID de bot | `AbstractC34361Xw` | constantes e conjuntos Hatch / Fallback / LID |
| Mapeamento de JID | `AbstractC24760wu` | mapeamento bot ↔ LID, conversão de alvo de saída |
| Gate | `C39311it` | gate por feature flag por JID (`A0E(Jid)`) |
| Gerenciador de requisição Hatch | `HF1` (`HatchMetadataRequestManager`) | requisições JSON, mapa de pendentes |
| Construtor de proto Hatch | `Hf6` | constrói `ProtocolMessage.aiMetadataOperation` |
| Message | `C30628DTw` | proto `Message` |
| WebMessageInfo | `C30626DTu` | proto `WebMessageInfo` |
| ProtocolMessage | `BD3` | proto `ProtocolMessage` |
| MessageContextInfo | `C30624DTs` | mantém `botMetadata` |
| BotMetadata | `C30615DTj` | metadados de bot por mensagem |
| Registro de perfil de bot | `C199348dm` | nome, descrição, string de ID de persona, thumb |

---

## 2. JIDs do Meta AI

### 2.1 JIDs encontrados no código

| Constante | Classe | Papel | Tier |
|----------|-------|------|------|
| `1807055946647697` | `C24770wv` (`bot`) via `AbstractC34361Xw.A00` | **Hatch**, primário. Perfil padrão construído em `C223219iv` a partir do payload da flag **26190** | found |
| `1807055946647698` | `C24770wv` (`bot`) via `AbstractC34361Xw.A01` | Fallback. Controlado pela flag 27083 | found |
| `165332417282214` | `C14080dr` (servidor `"lid"`) via `AbstractC34361Xw.A02` | Contraparte LID de `…698` | found |
| `1807055946647696` | nenhuma | Manus (legado na 2.26.26.4): **não presente** na 2.26.41.6 | found (ausente) |
| `1807055946647699` | `AbstractC33210EdN.A00` (`C24770wv`), mais `A01` = `DeviceJid` dispositivo 0 | JID de servidor-bot usado como alvo de sessão/dispositivo para um "envelope de bot" (handler de requisição de sincronização CoEx v2 `C53148Nnt` criptografa o payload de sincronização para seu dispositivo primário, log `coexv2 attached bot envelope`), adicionado a conjuntos de dispositivo destinatário (`C12M`), e tratado como remetente bot no tratamento de recibo de retry (`C33020EaI`). Não é uma persona de chat | found (uso); propósito além disso inferido |
| `2942131436135992` | `AbstractC24760wu.A00` (`C24770wv`) | JID do registro de perfil "Meta AI" padrão embutido (`C9i5.A00`: nome `Meta AI`, texto de introdução padrão). Membro do teste de JID-de-bot `AbstractC24760wu.A07` junto com a próxima linha | found |
| `867051314767696555` | `AbstractC24760wu.A01` (conjunto singleton, `C24770wv`) | Segundo membro do teste `A07` de JID-de-bot (`A07(jid)` = `C24770wv` igual a `…135992` ou neste conjunto); `A07` alimenta `AbstractC199328dk.A00` (um predicado de classe JID). Propósito adicional não resolvido | found (uso), propósito unknown |
| `17015557208` | `AbstractC24760wu.A04` | String de usuário de telefone. `A04(jid)` é true para o LID `165332417282214` ou para este usuário de telefone; usado com `A03` (qualquer JID bot `C24770wv`, ou PN nos intervalos 13135550000-13135559999 / 13165550000-13165550099) em `E76.A00` (classe 10 vs. 1) e no predicado de elegibilidade `C736539v.ARO`. Lê-se como a identidade PN do Meta AI; o que esses dois consumidores fazem com ela não está resolvido | found (uso), propósito unknown |

Conjuntos em `AbstractC34361Xw`: `A05 = {…697, …698}`; `A03 = {…697, …698, 165332417282214}`; mapa `A04`: `…697 → […697]`, `…698 → […698, 165332417282214]`.

Tipo de JID: o relatório da 2.26.26.4 listava todos os quatro como `@s.whatsapp.net`. Na 2.26.41.6 os JIDs de bot são `C24770wv` com `getServer() = "bot"`; o do grupo/LID é `C14080dr` com servidor `"lid"`. Não `s.whatsapp.net` (found).

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

Found: JID de bot `…698` ↔ LID `165332417282214`; contatos bot de número de telefone mapeiam para JIDs de bot. O método afirma "needs FBID migration" (found).

### 2.3 O sufixo `$1`: alterado

O relatório da 2.26.26.4 colocava `$1` no JID de roteamento ("formato de wire", `C1A2.A00()/A01()`). Não encontrado na 2.26.41.6:
- Nenhuma função de roteamento anexa `$1` a um JID. A conversão em 2.2 produz JIDs de bot simples.
- `$1` é anexado à string de ID de persona armazenada no registro de perfil do bot: `C24121Ab2` faz `personaIdString = botFbid + "$1"`; `C223219iv` fixa `"1807055946647697$1"` para o perfil padrão do Hatch (found).
- Essa string (`C199348dm.A0A`) é o que `C33473Ehf.A0G` escreve em `BotMetadata.personaId` (found).

Então `$1` pertence ao ID de persona, não ao JID de destino.

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

O ramo Manus (flag 25119) desapareceu. O significado de `BRD()` e a busca de capability (`C09L.A04`) não estão resolvidos (unknown).

---

## 3. Feature Flags

| ID da flag | Uso na 2.26.41.6 | Tier |
|---------|------------------|------|
| **25119** | Aparece apenas em tabelas de flag (`C06510El`, padrão `false` em `C08J`). Nenhum leitor encontrado. Nome antigo `ai_bot_integration_enabled` não encontrado como string | found |
| **26189** | Gate do Hatch em `C39311it.A02()`. Padrão `false` (`C08J`) | found |
| **27083** | Gate de Fallback / LID em `C39311it.A0E()`. Padrão `false` | found |
| **26190** | Config JSON (`name`, `description`, `profile_thumb`) para o perfil Hatch padrão, lida em `C223219iv` | found |
| **37227** | `C39311it.A03()`; `A05() = A02() && A03()`. Quando true, a capability `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) é divulgada ao Hatch (ver 5); `A05` também controla telemetria/UI de conector (`C28147CLx`, `C1427261o`, `C36186FnU`) | found |
| **37852** | `C39311it.A0A() = A02() && flag`. Divulga `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77); também controla a disponibilidade de conector (`AbstractC26695Bhv`) | found |
| **37054** | `C39311it.A0B() = A02() && flag`. Divulga `HATCH_ARTIFACT_CARD_ENABLED` (79); também lida por `HatchSpacesSync` e `C7WL` | found |

As strings `ai_hatch_integration_enabled`, `ai_maiba_wass_migration_receiving_enabled` não são nomes de flag. São entradas de uma lista de strings de recurso construída a partir das flags 26189 / 27083 em `C25056AqU` (junto com `username_supported`, `post_status_in_companion`, ...); `ai_fbid_migration_receiving_enabled` é adicionada incondicionalmente. O destinatário e o propósito da lista não foram verificados.

---

## 4. Campos Proto

### 4.1 Message (`C30628DTw`) nível superior

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botInvokeMessage` | **67** | `BD2` (campo único `message` = 1) | Mensagem de saída embrulhada para o bot; definida em `F2K`, `C33284Eea` |
| `botTaskMessage` | **100** | `BD2` | Tarefa de bot |
| `botForwardedMessage` | **104** | `BD2` | Embrulha uma mensagem contendo `richResponseMessage`; definida em `F3E` |
| `richResponseMessage` | **97** | `DSY` | Resposta de IA. Campos: `messageType` 1, `submessages` 2, `unifiedResponse` 3, `originalRecipientMetadata` 5 |
| `botPlatformRegistrationSuccessMessage` | **131** | `BD2` | Presente |
| `botGroupParticipantMessage` | **137** | `BD2` | Presente |
| `messageContextInfo` | **35** | `C30624DTs` | Carrega `botMetadata` |
| `protocolMessage` | **12** | `BD3` | Carrega `aiMetadataOperation` (31) |

O campo **77** é `commentMessage`, não `richResponseMessage` (o relatório da 2.26.26.4 tinha 77; errado para esta build, e consistente com a pesquisa separada de richResponseMessage: 97).

### 4.2 WebMessageInfo (`C30626DTu`), não ContextInfo

O relatório da 2.26.26.4 listava estes como campos de ContextInfo. Na 2.26.41.6 eles estão em `WebMessageInfo`:

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `botMessageInvokerJid` | **58** | string | Definido em `C34385EwW` a partir de `C0DZ.A09(userJid)` (usuário do dispositivo primário do invocador) |
| `isSupportAiMessage` | **70** | bool | Definido em `C34378EwP.C57` quando a mensagem tem o bit de flag `268435456` e uma verificação passa; relido em `C59`. Junto com `is1PBizBotMessage` (**56**) |
| `supportAiCitations` | **72** | mensagem repetida | Citações |
| `botTargetId` | **73** | string | Nenhum escritor no cliente: `botTargetId_` aparece apenas como padrão do construtor e na tabela de schema de `C30626DTu`, nunca atribuído em outro lugar (grep completo do código-fonte) |
| `agentId` | **47** | string | Presente, não analisado |

Se e como esses campos de WebMessageInfo aparecem no wire não está verificado (unknown). "`true` para todas as mensagens do Meta AI" não é suportado: é definido por flag de mensagem individual, não incondicionalmente.

### 4.3 MessageContextInfo (`C30624DTs`)

| Campo | Número | Tipo |
|-------|--------|------|
| `botMessageSecret` | **6** | bytes |
| `botMetadata` | **7** | `BotMetadata` (`C30615DTj`) |
| `teeBotMetadata` | **17** | bytes |

### 4.4 BotMetadata (`C30615DTj`)

| Campo | Número | Tipo | Uso |
|-------|--------|------|-----|
| `personaId` | **2** | string | Do registro de perfil do bot (`C199348dm.A0A`), ex. `1807055946647697$1`. Não é um `"meta_ai"` fixo |
| `pluginMetadata` | **3** | `DTL` | Config de plugin |
| `invokerJid` | **5** | string | Invocador |
| `aiConversationContext` | **20** | bytes | Estado da conversa |
| `botResponseId` | **26** | string | ID de resposta |

Outros campos presentes (nomes a partir de `*_FIELD_NUMBER`, tipos não lidos): `suggestedPromptMetadata` 4, `searchMetadata` 6, `memuMetadata` 7, `timezone` 8, `modelMetadata` 10, `messageDisclaimerText` 11, `progressIndicatorMetadata` 12, `capabilityMetadata` 13, `imagineMetadata` 14, `memoryMetadata` 15, `renderingMetadata` 16, `botMetricsMetadata` 17, `botLinkedAccountsMetadata` 18, `richResponseSourcesMetadata` 19, `botPromotionMessageMetadata` 21, `botModeSelectionMetadata` 22, `botQuotaMetadata` 23, `botAgeCollectionMetadata` 24, `conversationStarterPromptId` 25, `verificationMetadata` 27, `unifiedResponseMutation` 28, `botMessageOriginMetadata` 29, `inThreadSurveyMetadata` 30, `botThreadInfo` 31, `sessionTransparencyMetadata` 33, `botDocumentMessageMetadata` 34, `botGroupMetadata` 35, `botRenderingConfigMetadata` 36, `botInfrastructureDiagnostics` 37, `aiMediaCollectionMetadata` 38, `commandMetadata` 39, `resolvedToolCallMetadata` 40, `subscriptionUpsellMetadata` 41, `pttPromptMetadata` 42, `botHistoryShareMetadata` 43, `responseStoppedByUser` 44.

`personaId` é preenchido em `C33473Ehf.A0G`; ele retorna antecipadamente se o perfil não tiver nenhuma string de persona.

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

Constantes de `C4E0` (valor = ordinal do construtor; igualdade ao número proto é inferida): UNSET 0, ANIMATE 1, BACKDROP 2, EDIT 3, EDIT_FLASH 4, FEELS 5, FLASH 6, FLASH_TO_BASE 7, **IMAGINE 8**, **MEMU 9**, REIMAGINE 10, RESTYLE 11, SAM 12, STICKERS 13, VIDEO 14, **MEMU_AND_IMAGINE 15**, MEMU_STICKERS 16, IMAGINE_USER_UPLOADED_IMAGE 17. Os valores antigos 8/9/15 estão inalterados; o enum é maior.

### 4.6 oneof Action (`C61331Rfl`, enum de case `EnumC61601RkN`)

| Número | Case | Tier |
|--------|------|------|
| 1 | `ASK_META_AI_ACTION` | found |
| 2 | `CREATE_A_TASK_ACTION` | found |
| 3 | `CREATE_A_POLL_ACTION` | found |
| 0 | `ACTION_NOT_SET` | found |

Isto é um oneof de campos de ação, não um enum de valor simples. Onde ele é embutido não foi rastreado (unknown).

### 4.7 Operação de metadados de IA (transportador Hatch)

| Mensagem | Campo | Número | Tipo |
|---------|-------|--------|------|
| `ProtocolMessage` (`BD3`) | `aiMetadataOperation` | **31** | `C25754B9o` |
| `C25754B9o` | `hatchMetadataSync` | **1** | `BB2` |
| `C25754B9o` | `bizAiMetadataSync` | **2** | `C156236jd` (`serverEvent` = 1) |
| `BB2` | `data` | **1** | bytes |
| `BB2` | `timestampMs` | **2** | int64 |
| `BB2` | `requestId` | **3** | string |

---

## 5. Protocolo de requisição (metadados Hatch)

Requisições são construídas por `HF1` (`HatchMetadataRequestManager`), classe coroutine `HatchMetadataRequestManager$sendRequest$2`. O envelope JSON difere da 2.26.26.4: `method` e `params` ficam aninhados sob `payload`.

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

- Requisições pendentes: `HF1.A04` (`ConcurrentHashMap`, requestId → continuation) e `HF1.A03` (requestId → `GuR`). Ambos limpos em `finally`. O relatório da 2.26.26.4 nomeava apenas um mapa, `A02`.
- Timeout: retorna `GDB.A00` e loga `HatchMetadataRequestManager/sendRequest timed out method=`.
- O inteiro `138` passado a `C37393GKy` não está resolvido (unknown).
- O transportador é `ProtocolMessage.aiMetadataOperation` (campo 31), não uma mensagem de chat comum (alterado).
- O pacote `com.whatsapp.bot.infra.message.aimetadata` contém classes `Ideas*Wire` / `Idea*Wire` (found). Sua relação com os nomes de método é apenas inferida; os nomes de método não foram enumerados.
- O lado de recebimento que completa `A04` não foi rastreado. A correspondência de uma resposta com `requestId` é inferida a partir do mapa `A04` e de `BB2.requestId`.

Afirmação de **nenhum namespace XMPP personalizado**: nenhum tratamento de `w:ai` / `wa:ai` visto no caminho rastreado; baseada em ausência, não re-verificada exaustivamente.

**Divulgação de capability (found, `C33284Eea`):** quando o destino é o JID Hatch `…697` (`AbstractC34361Xw.A00`) e um gate passa, o cliente constrói `DPJ` (campo único repetido de enum `capabilities` = 1, valores `EnumC32144E2q`) e `C33473Ehf.A06` o armazena em `BotMetadata.capabilityMetadata` (13) da mensagem de saída, junto com `BotMetadata.timezone` (8) = o ID de `TimeZone` do dispositivo. Capabilities adicionadas por gate:

| Gate | Capability (número do enum) |
|------|--------------------------|
| `C39311it.A04()` | `HATCH_NOTIFICATION_METADATA_EVENT_ENABLED` (72) |
| flag **37227** | `HATCH_CONNECTOR_ACTION_CARD_ENABLED` (76) |
| flag **37852** | `HATCH_SECURE_CREDENTIAL_CARD_ENABLED` (77) |
| `C39311it.A0D(userJid)` | `HATCH_BROWSER_TASK_CARD_ENABLED` (78) |
| flag **37054** | `HATCH_ARTIFACT_CARD_ENABLED` (79) |
| `C39311it.A09()` | `AI_MUSE_JARVIS_SCHEMA_ENABLED` (81) |

Os números são o segundo argumento de construtor do enum; que sejam iguais a números proto é inferido. O enum também lista capabilities de rich-response (`RICH_RESPONSE_TABLE`, `RICH_RESPONSE_CODE`, `AI_MEMORY`, `PROGRESS_INDICATOR`, ...).

**Exemplos de requisição (found, chaves de `params` lidas nos pontos de chamada; o alvo é o JID Hatch `…697` salvo se o ponto de chamada usar o JID da conversa):**

| `method` | `params` |
|----------|----------|
| `ideas.detail` | `{"ideaCardId": "<id>"}` |
| `ideas.execute` | construído em `HatchIdeasManager$execute$job$1` (chaves não lidas); callback `onPart` anexado |
| `ideas.complete_all` | `IdeasCompleteAllParamsWire` serializado para JSON; callback `onPart` anexado |
| `channel.bootstrap` | `{"sections": [ ... ]}` |
| `hitl.approval.decide` | `{"approval_id": "...", "decision": "...", "always_scope": "..."}` (`always_scope` apenas quando não-vazio) |
| `hitl.payment.select` | `{"approval_id": "...", "payment_id": "..."}` |

Formato dos bytes em `BB2.data` (formato found, valores de exemplo):

```json
{"version":1,"type":"req","payload":{"method":"ideas.detail","params":{"ideaCardId":"<id>"},"accepts_encoding":["gzip"]}}
```

`accepts_encoding` é escrito apenas quando o `acceptsGzipResponse` do chamador é true; `params` apenas quando não-nulo. O callback `onPart` é registrado em `A03` apenas quando o chamador passa um.

**Mensagem de chat para o bot (partes found):**
- O `Message` de saída é re-embrulhado em `Message.botInvokeMessage` (`F2K`, `C33284Eea`), o wrapper `BD2` mantendo a mensagem no campo 1. Em `F2K` o embrulho é pulado (mensagem definida diretamente) quando `C13S.A00()` é false, o `A10` da mensagem é false, ou a flag **10646** está ativa (found).
- `BotMetadata` é construído por `C33473Ehf.A0E` / `A0G`. `A0G` busca o registro de perfil para o JID de bot alvo (`C199358dn.A06(userJid)`, string de persona `C199348dm.A0A`); se essa string estiver vazia o método retorna sem escrever metadados de bot, caso contrário define `personaId` (2) e, quando presentes, `suggestedPromptMetadata` (4) e outras sub-mensagens. A string de persona é armazenada quando o registro de perfil é criado (`C24121Ab2` constrói `<id>$1`; `C223219iv` fixa `1807055946647697$1` para o Hatch). Se `messageContextInfo` cai no `Message` externo ou na mensagem interna de `botInvokeMessage` não foi resolvido.
- `botMessageInvokerJid` / `isSupportAiMessage` são definidos em `WebMessageInfo` por hooks D36 (`C34385EwW`, `C34378EwP`).

---

## 6. Protocolo de resposta

### 6.1 Transporte

Não re-verificado como afirmado na 2.26.26.4 ("mensagens normais com bytes de `hatchMetadataSync`", classe `Azz`). Found: `hatchMetadataSync` vive em `C25754B9o` dentro de `ProtocolMessage.aiMetadataOperation`. Respostas Hatch presumivelmente chegam da mesma forma e correspondem por `requestId` (inferido). Requisições Hatch são chamadas de método; não está demonstrado que sejam o caminho das respostas de chat normais.

### 6.2 Streaming / chunks: não suportado como descrito

A tabela da 2.26.26.4 (`chunkOrder`, `isLastChunk`, `clientStreaming`, `serverStreaming`, `streamingSidecar`) como um único mecanismo de streaming do Meta AI não é suportada na 2.26.41.6:

| Campo | Onde está na 2.26.41.6 |
|-------|--------------------------|
| `chunkOrder` | campo **7** de `C25834BCt` (notificação de sincronização de histórico, `syncType`/`progress`/`oldestMsgInChunkTimestampSec`) e campo **5** de `C25838BCy` (sincronização de histórico) |
| `isLastChunk` | campo **8** de `C55285Ou6` (mensagem com `attestationBundles`, `teeModelConfig`, `violationSignal`; relacionado a TEE) |
| `streamingSidecar` | campo **18** em mensagens de imagem/vídeo/áudio (`C30607DTb`, `DTR`, `DTX`, `C30614DTi`) |
| `clientStreaming`, `serverStreaming` | não encontrados como campos proto |

Nenhuma remontagem de chunk de respostas do Meta AI foi encontrada. O que existe para o Hatch: `GuR(method, onPart)` — um callback `onPart` por requisição (found); que ele carregue resultados parciais é inferido do nome.

### 6.3 Resposta rica (campo 97)

`richResponseMessage` (`DSY`) = campo **97** em `Message`. Classes de renderização existem: `AiRichResponseFooterView` e `UnifiedResponseActionHandlerFactory` (pacote `com.whatsapp.conversationrow.botrichresponse`) (found). Citações: `WebMessageInfo.supportAiCitations` (72). Tipos de conteúdo (imagens, tabelas, código) não re-verificados aqui; ver a pesquisa separada de richResponseMessage.

### 6.4 Indicador de digitação

Saída (found, `C199098dN.A01`, log `HandleMeComposing/handleComposing`): estado de chat XMPP padrão, nenhum namespace personalizado no código lido.
- Caso simples (nenhum bot mencionado, ou um JID de bot resolvido para o padrão): `<chatstate to="[chat]"><composing [media="audio"]/></chatstate>`.
- Bot mencionado no chat: `<chatstate to="[chat]"><bot jid="[botJid]"/><composing [media="audio"]/></chatstate>`.
- Enviado através de `C10140Tq.A0X` com tipo de IQ int 4.

Entrada (found, handler de stanza `C40511kx`): um `<chatstate>` com um filho `composing` (opcional `media`) chama o callback de composing genérico com `from`/`participant`; `paused` chama o callback de paused. Nenhum ramo específico de bot foi encontrado neste handler, então um `composing` de JID de bot passa pelo mesmo caminho de qualquer contato (inferido; uma stanza de digitação de bot do lado do servidor não foi observada). `BotMetadata.progressIndicatorMetadata` (12) e a capability `PROGRESS_INDICATOR` existem como um mecanismo de progresso separado dentro da mensagem (apenas nomes, não rastreados).

### 6.5 Sincronização de perfil de bot

`BotProfileSyncManagerImpl` (`com.whatsapp.bot.home.sync`) agenda `BotProfileForChatListWorker` em `A03()`: uma requisição WorkManager marcada `BotProfileSyncManager` com `setBackoffCriteria(policy, 1, MINUTES)` e uma restrição (valor do tipo não resolvido). O 1 minuto é um **backoff** de retry, não um período. O "a cada ~1 minuto" da 2.26.26.4 não é suportado (alterado). `A02(groupJid, userJid)` solicita um único perfil (`requestBotProfileResult`). Não faz parte da sincronização normal de roster (inalterado).

Registro de perfil `C199348dm`: tipo de bot (`C1XY`), jid, nome de exibição (`A09`), descrição (`A07`), string de persona (`A0A`), thumbs, timestamp.

### 6.6 Strings de tipo de bot

`C718732k.A00(String)` mapeia: `meta_ai`, `meta_ai_thread`, `tee_meta_ai_group`, `side_chat`, `manus`, `hatch`, `muse`, `third_party`; qualquer outra coisa se torna `AnonymousClass399(str)`. São rótulos de tipo de bot (também usados em filtros de UI), não valores de `BotMetadata.personaId` (found).

---

## 7. Armazenamento

- `MetaAiMemoryStore`: nenhuma classe com esse nome na 2.26.41.6. O equivalente encontrado é uma tabela `meta_ai_memory` criada pela classe de schema `C23621AHm` (found): `memory_id` TEXT, `memory_content` TEXT, `bot_jid_row_id` INTEGER, índice `meta_ai_memory_memory_content_index` em `memory_content`. Qual arquivo de banco de dados a mantém não está resolvido. Relacionado (found): `com.whatsapp.bot.botmemory.MemoryDeprecatedActivity` (UI; o nome diz deprecated), SharedPrefs `meta_ai_memory_disclosure_seen` (tela de design de chamada de voz, `C29434Cpx`), enums de capability `AI_MEMORY` 4, `AI_SHARED_MEMORY` 40, `AI_STUDIO_UGC_MEMORY` 23 (`EnumC32144E2q`), e `BotMetadata.memoryMetadata` (15).
- Chave SharedPrefs `"meta_ai_forward_disclosure_seen"`: presente, booleano, lida em `C230589xr.A03` para `ForwardMessageToMetaAiBottomSheet` (`com.whatsapp.bot.product.conversation.p027ui`) (found).
- `MetaAiIncognitoSessionManager`: presente em `com.whatsapp.metaai.incognito.infra` (found).
- Armazenamento separado de chats do Meta AI fora do `msgstore.db` (2.26.26.4, não re-verificado): nenhuma classe de armazenamento de chat encontrada; `meta_ai_memory` mantém apenas fatos de memória, então a alegação não é suportada nem refutada.

### 7.1 Private Search como um tipo de thread de bot-chat (novo na 2.26.45.10, found)

Novas classes (`com.whatsapp.privateai.privatesearch`, `com.whatsapp.searchui.search.psisearch`):

| Classe | Papel |
|-------|------|
| `PrivateSearchSessionManager` | Rastreia a única thread de Private Search ativa/mais recente; recusa retomar uma thread substituída por uma busca mais nova |
| `PrivateSearchThreadsManager` | Cria uma thread de bot do tipo `PRIVATE_SEARCH`; estende `LX/1gu`, a mesma base `BotThreadsManager` que `IncognitoAiThreadsManager` (acima) já usa |
| `PsiSearchManager` (obfuscada `LX/JjA`) | Mantém o fluxo de envio de query/follow-up ("echo") |
| `PsiSearchDialogFragment` | UI de diálogo; um argumento `"kind"` de `"TURN_ON_PRIVATE_PROCESSING"` expõe o gate de opt-in de Private Processing inline |
| `PsiSearchUnifiedResponseRenderer` | Renderiza a resposta do bot |

Private Search é implementado como mais um **tipo de thread de bot-chat**, não um novo primitivo de rede. `PrivateSearchThreadsManager` chama o construtor de thread de bot compartilhado `LX/1gv;->A00(LX/2p4, ...)` com um enum de 5 valores `LX/2p4`: `UNKNOWN`(0) / `DEFAULT`(1) / `INCOGNITO`(2) / `SIDE_CHAT`(3) / `PRIVATE_SEARCH`(4). `PsiSearchManager` revalida o tipo de uma thread contra este discriminador antes de enviar, rejeitando uma query vazia ou uma thread não-`PRIVATE_SEARCH`.

**Caminho de envio de query (found).** `PsiSearchManager.onEchoSelected` constrói a mensagem de saída via o mesmo utilitário genérico de criação de mensagem que outros envios de chat usam, `LX/D1D;->A05(...)`, depois despacha o resultado através da fila de mensagens de saída comum (`LX/JjA;->A0H:LX/0JB;->D2A`). Nenhuma chamada GraphQL/MEX/IQ aparece em nenhum lugar deste caminho — é o mesmo mecanismo de embrulho-em-`botInvokeMessage` (campo 67) para JID de bot documentado em §11 ("Mensagem de chat para o bot"), reutilizado literalmente e não re-derivado aqui.

**O que permanece nativo (referência cruzada).** O pipeline de recuperação PSI/TEE que de fato responde à query — `TeeClientToolOrchestrator`, `PsiSearchToolHandler` (ferramenta de cliente `wa_search`), `IplsdHandshakeExecutor`, sustentado por `libpsi.so`/`libxplat_psi.so` nativos — está inalterado desde a 2.26.41.6 e documentado na pesquisa Labyrinth/TEE do brain (não re-derivado aqui); nada disso é tocado pelas cinco classes acima, que apenas constroem a mensagem de saída e renderizam a resposta.

**Veredito de alcançabilidade: envio alcançável, valor inalcançável.** O envio de iniciação de busca é alcançável por um cliente de terceiros exatamente no mesmo sentido que o chat do Meta AI já é (§8, §11) — nada novo a derrotar. O que não é alcançável é o valor real de preservação de privacidade do recurso: a busca PSI no dispositivo sobre o BD de chat local e a ida e volta de enclave atestado são nativas, e o `Message` de saída não carrega nenhum material PSI pré-computado. Um cliente de terceiros que enviasse texto simples ao JID de bot de Private Search receberia o que quer que o bot do lado do servidor faça com uma query em texto plano não-PSI'd, não a semântica de busca privada própria do WhatsApp (unknown, não verificado em nenhum dos dois sentidos).

### 7.2 Parada de geração movida para fora do caminho de wire-message (novo na 2.26.45.10)

A string de erro `promptMessageKey` (presente desde a 2.26.35.8, vinculada a `FMessageStopGeneration` / `ProtocolMessage.extraJson_`, tipo 26) tem **zero ocorrências** em todos os 14 arquivos DEX na 2.26.45.10 (found, varredura exaustiva de strings). O campo subjacente `extraJson_` ainda é declarado em `LX/DHC;` (a classe host `ProtocolMessage`) mas é referenciado apenas dentro da própria declaração de campo e do array de reflexão dessa classe — nenhum getter, nenhuma outra classe no app o lê (found). O D8 removeu completamente a informação de debug nesta build (zero nomes de arquivo `DBG_SET_FILE` recuperáveis em 34.255 métodos em `classes6.dex`), então a classe obfuscada que antes sustentava `FMessageStopGeneration` não pôde ser identificada a partir de metadados de debug; as três strings de nome de arquivo `.kt` para ela sobrevivem apenas como entradas órfãs do pool de strings, não como código alcançável (found).

Encontrado em vez disso: uma nova classe **não obfuscada** `com/meta/metaai/stopgeneration/data/StopGenerationRepository` cujo `A00(threadIdentifier, messageIdentifier, messageIdString, surface, mode, Continuation)` dispara uma mutation GraphQL Pando `MetaAIStopGenerationMutation` (op `xfb_genai_stop_generation`), com campos `thread_identifier`, `message_identifier`, `message_id_string`, `surface`, `mode`, validados por verificações nulas genéricas sem chave string (`LX/00m;->A09`) — nenhum texto de erro estilo `promptMessageKey`.

Melhor explicação (**inferred**, não comprovada): a parada de geração se mudou para esta mutation GraphQL para esta surface, em vez da antiga verificação de wire-message ter sido renomeada no lugar. Se o caminho legado `protocolMessage`/tipo-26/`extraJson_` agora é código morto, mantido para compatibilidade com clientes mais antigos, ou ainda alcançável a partir de algum chamador não rastreado é **unknown** — nenhum chamador foi encontrado nesta build, mas uma varredura estática de DEX único não pode provar remoção.

---

## 8. Por que o Baileys não recebe resposta

Todas as linhas são **inferred**: comparação estática dos requisitos do cliente com um caminho de envio de terceiros; nenhum teste em produção.

| Problema | Base na 2.26.41.6 | Tier |
|-------|--------------------|------|
| Tipo de JID alvo errado | JIDs de bot usam o servidor `bot` (`C24770wv`), não `s.whatsapp.net`; bots de número de telefone mapeiam através de uma tabela PN→FBID | found (classe JID), inferred (efeito) |
| `$1` no JID de roteamento | Não presente. `$1` está na string de ID de persona | found |
| Wrapper `botInvokeMessage` ausente | O cliente embrulha o `Message` de saída no campo 67 (`F2K`) | found, requisito inferido |
| `messageContextInfo.botMetadata` ausente | O cliente escreve `personaId`, `invokerJid`, etc. nele | found, requisito inferido |
| `personaId = "meta_ai"` | Não é o que o cliente envia; ele envia a string de persona do perfil (ex. `1807055946647697$1`) | found |
| `aiConversationContext` ausente | Campo 20 de `BotMetadata`; comportamento na primeira interação unknown | unknown |
| `isSupportAiMessage` / `botMessageInvokerJid` | Campos de WebMessageInfo definidos por hooks do cliente; requisito do servidor unknown | unknown |
| `botTargetId` | Nenhum escritor no código do cliente | found |
| Resposta não parseada | `richResponseMessage` é o campo 97 de `Message` | found |
| Remontagem de chunk | Não suportada pela evidência da 2.26.41.6 (ver 6.2) | found |

---

## 9. Verificação de assinatura de bot (autenticidade de conteúdo)

Separado de tudo acima: um mecanismo que permite ao cliente **receptor** verificar que o conteúdo de `richResponseMessage` veio genuinamente do backend de IA da Meta, independentemente de quem retransmitiu a mensagem. As descobertas estáticas abaixo são `found` no código da 2.26.41.6; o resultado do replay em 9.4 é `tested` (em produção, na própria conta do autor — não interceptação de tráfego, um cliente legítimo compondo e retransmitindo sua própria mensagem).

### 9.1 Localização no proto

`BotMetadata.verificationMetadata` — campo **27** (`messageContextInfo` (35) → `botMetadata` (7) → `verificationMetadata` (27)), tipo `DPC`/`BotSignatureVerificationMetadata` (toString revela o nome real): `proofs[]`, cada um um `BotSignatureVerificationUseCaseProof` com `version` (int), `useCase` (enum `WA_BOT_MSG` / `WA_TEE_BOT_MSG`), `signature` (bytes), `certificateChain` (bytes repetidos, DER X.509).

### 9.2 Algoritmo de verificação

Classe `C33259EeB`, nome interno `BotSignatureVerificationUtils` (a partir de strings de log):

1. **Validação da cadeia de certificado** de `certificateChain` contra uma ancoragem de confiança, via `HFg.A01(date, certs, true)`.
2. **Construção dos bytes assinados**: `"1" + <string de número de telefone> + <bytes de unifiedResponse>` — a assinatura vincula **conteúdo e um número de telefone juntos**, não apenas o conteúdo.
3. **Verificação EdDSA** (log: `"EdDSA signature verification result"`) usando a chave Ed25519 bruta extraída do SubjectPublicKeyInfo do certificado folha.
4. **Modo de imposição**, lido da config **19590**, enum `EnumC32057Dzg`: `NONE` (`"none"`, desativado, sempre passa), `LOG_ONLY` (`"log_only"`, verifica + loga, nunca bloqueia), `ENFORCE_BLOCKING` (`"enforce_blocking"`, uma verificação falhada retorna `false`). Resultado armazenado como `E05`: `UNKNOWN` / `VALID` / `FAILED` / `DOWNLOAD_CONSENT_ACCEPTED`, persistido na coluna SQLite `bot_message_info.signature_validation_status` (a tabela também tem `bot_client_public_key`).

### 9.3 Gate de renderização de linha

`C30085D6v.A00` (dispatcher de tipo de linha) e `EOK`/`C32608EKo`: se o status da assinatura é `FAILED` e a flag **27635** está ativa → linha mascarada `ConversationRowAiUnknownSenderMasked` ("signature verification failed"). Independentemente, se o JID do remetente não está presente no armazenamento de perfil de bot sincronizado localmente (`C224899mg`, a mesma sincronização de `BotProfileSyncManagerImpl`) e a flag **27355** está ativa → `ConversationRowAiUnknownSenderPreview` ("unknown sender with unconsented content"), uma pré-visualização com gate de consentimento em vez de um bloqueio rígido.

### 9.4 Captura real e replay em produção (tested)

Uma resposta genuína do Meta AI, capturada do lado do cliente em uma conversa real (própria conta, decriptada pelo próprio cliente do autor — não interceptação de tráfego), carregava:

- `botMetadata.verificationMetadata.proofs[0]`: `version: 1`, `useCase: "WA_BOT_MSG"`, uma `signature` de 64 bytes (tamanho Ed25519), uma `certificateChain` de 2 entradas.
- Certificado folha: `CN=svc:wa-bot-msg-leaf`, chave Ed25519, emitido por `Meta WA SS Int CA 2025-09`, encadeando até `Meta WA Feature Root CA` (`O=Meta Platforms Inc.`), validade ≈7 meses (certificado de serviço com auto-rotação) — a chave privada de assinatura existe apenas no backend da Meta.
- `botMetadata.botInfrastructureDiagnostics.botBackend: "CLIPPY"` — um nome de backend de bot não documentado anteriormente (ver também "Hatch" nas seções 1–6).
- `messageContextInfo.accountEncryptionAttestation.accountType: "NON_E2EE"`, um campo irmão de `botMetadata`.
- Formato de entrega: `protocolMessage` com `type: MESSAGE_EDIT`, `editedMessage.richResponseMessage` (a primeira resposta em uma thread chega pré-embrulhada como uma edição de um placeholder), `key.remoteJid` = o próprio JID do autor.

**Teste:** o exato `richResponseMessage` + `messageContextInfo.botMetadata` (assinatura e cadeia de certificado byte a byte inalterados) foi retransmitido via `relayMessage` a partir do próprio dispositivo do autor — não do JID de bot `867051314767696@bot` — para o próprio número do autor (o mesmo número já embutido nos bytes assinados).

**Resultado:** o conteúdo foi renderizado com estilização "AI" completa e o texto real, rotulado "Forwarded". Algumas entregas do mesmo payload idêntico mostraram em vez disso "WhatsApp can't verify the security of this media. Only download if you trust the sender." com uma ação Download; tocar em Download revelou o conteúdo idêntico, correspondendo ao status `DOWNLOAD_CONSENT_ACCEPTED` e ao caminho de código "unknown sender with unconsented content" em 9.3. Uma entrega mostrou um fallback genérico "your version of WhatsApp doesn't support it" em vez disso; a causa não foi estabelecida (unknown).

**Conclusão (tested):** a verificação criptográfica em 9.2 vincula a *(conteúdo, número de telefone)*, não à identidade ou JID do remetente real. Um `richResponseMessage` validamente assinado pode ser retransmitido a partir de um remetente não-bot e ainda passar a verificação de assinatura, desde que o número do destinatário corresponda ao número embutido na assinatura — o cliente receptor o renderiza como conteúdo de IA genuíno (no máximo com gate de uma etapa de consentimento cosmética de "remetente desconhecido", não um bloqueio rígido). Este é um mecanismo de autenticidade de conteúdo, não de autenticidade de remetente; a própria criptografia da camada Signal do WhatsApp, não esta assinatura, é o que autentica o remetente real.

### 9.5 Verificação de lista de revogação de certificado (CRL) (novo na 2.26.45.10, found)

A etapa de validação de cadeia em 9.2 (etapa 1, "validação da cadeia de certificado... via `HFg.A01`") ganhou uma verificação CRL tanto contra o certificado folha quanto o intermediário em `certificateChain`, antes da verificação de assinatura Ed25519-sobre-(telefone, conteúdo) (9.2 etapa 3). Classes: `BotPkiCrlGraphQLFetcher`/`BotPkiCrlManager` (`com/whatsapp/bot/infra/message/signature/`), chamadas pela classe de validação de cadeia da 2.26.45.10 `BotSignatureVerificationCertificateManager` (`LX/HEe` — sucessora renomeada de `BotSignatureVerificationUtils`/`C33259EeB` de 9.2; mesma classe, confirmado por strings de log compartilhadas `"Certificate chain validation successful"`/`"Parsed <n> certificates from chain"`).

- **Op GraphQL**: `FetchBotPKICRL` em `whatsapp-android-mex` — campo de requisição `crl_name`, resposta `xwa2FetchFeaturePkiCrl` contendo a CRL como um blob de bytes DER brutos (não uma lista pré-parseada de seriais revogados) mais timestamps `fetchedAt`/`nextUpdate` e uma contagem de entradas revogadas.
- **Duas CRLs em uso**, por nome: `whatsapp_simple_signal` para o certificado **folha**, `whatsapp_feature` para o certificado **intermediário** (strings de log `"...Leaf certificate CRL validation passed"` / `"...is revoked"` / `"...CRL unavailable..."`, mesmo par para "Intermediate").
- **Ancoragem de confiança**: um certificado raiz de 40 anos fixado como literal PEM dentro de `LX/HEe` — `CN=Meta WA Feature Root CA`, `O=Meta Platforms Inc.`, chave EC, válido de 2025-09-04 a 2065-09-04. A própria assinatura de cada CRL buscada é verificada contra a chave pública do emissor relevante (`X509CRL.verify(...)`) antes que sua lista de revogados seja confiada — exceto para `whatsapp_simple_signal`, que tem um caso especial pulando essa etapa de auto-verificação (motivo `inferred`, não resolvido).
- **Cache/atualização**: cache `SharedPreferences` por `crlName` (`crl-data`/`crl-fetched-at`/`crl-next-update`), pré-buscado uma vez na inicialização do app após o usuário estar registrado e o BD pronto (log: `"BotPkiCrlManager/...starting CRL prefetch"`), atualizado em um timer vinculado ao próprio `nextUpdate` da CRL (com piso de 60s), e buscado sob demanda com uma janela de backoff se o cache estiver ausente/obsoleto quando uma verificação roda.
- **Efeito**: um certificado folha ou intermediário revogado falha a validação de cadeia da mesma forma que um já expirado — isto alimenta o status `E05` existente (`FAILED`) e o gate `ENFORCE_BLOCKING`/`LOG_ONLY`/`NONE` de 9.2 etapa 4, não um novo caminho de imposição separado.
- **Tier**: found — op, namespace, ambos os crlNames, mecânica de cache/atualização, pontos de chamada, certificado raiz fixado. Inferred — o layout exato de bytes das entradas revogadas (serial vs. bytes completos do certificado) e o motivo de `whatsapp_simple_signal` pular a auto-verificação CRL. Tudo análise estática; nenhum certificado revogado foi observado na prática.
- **Superfície de cliente/Baileys**: `FetchBotPKICRL` é uma op MEX concreta e nomeada, alcançável da mesma forma que outras ops `whatsapp-android-mex`, mas ela só alimenta decisões de confiança do lado do cliente sobre certificados de mensagem de bot — não tem efeito sobre o que um remetente não-cliente pode retransmitir (o resultado do replay em 9.4 é inafetado: a revogação só muda os resultados para um certificado de fato revogado, o que isto nunca exercita).

---

## 10. Correção para o Baileys

Nenhuma implementação funcional é alegada. O que se segue é um esboço estrutural de onde os campos vivem conforme a 2.26.41.6, marcado **inferred**; não foi executado contra um servidor.

### 9.1 Alvo

```ts
// inferred: bot JIDs use server 'bot', not 's.whatsapp.net'
const META_AI_JID = '1807055946647697@bot'   // Hatch (C24770wv server "bot")
// Do NOT append '$1' to the JID; '$1' is part of the persona ID string (found).
```

Se a string de servidor `bot` funciona como um alvo de relay do Baileys, e como o servidor deriva o `to` final da stanza, é unknown.

### 9.2 Posicionamento de campo (apenas formato)

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

- A inclusão de `botMetadata` em `messageContextInfo` (campo 7) é **found**. `capabilityMetadata` (13) e `timezone` (8) são escritos pelo cliente apenas para destinos Hatch (found); seu requisito do lado do servidor é unknown. Se o proto do `baron-baileys-v2` já tem esses campos não foi verificado; se não, o proto deve ser estendido (inferred).
- `isSupportAiMessage` (70) e `botMessageInvokerJid` (58) são campos de `WebMessageInfo`. Se devem estar presentes no wire é unknown; não os coloque em `contextInfo` (isso estava errado no relatório da 2.26.26.4).
- `botTargetId`: nenhum escritor de cliente em nenhum lugar do código decompilado (found); não o defina.
- O embrulhamento exato (`botInvokeMessage.message` contendo a mensagem real vs. ao lado) segue o re-embrulhamento de `F2K` / `C33284Eea`; o resultado serializado exato não foi reproduzido (unknown).

### 9.3 Tratamento de resposta

- Respostas ricas: `Message.richResponseMessage` é o campo **97** (found). Faça o parse desse, não do campo 77.
- Remova o tratamento de chunk: `chunkOrder` / `isLastChunk` não são campos de streaming do Meta AI (6.2).
- `ProtocolMessage.aiMetadataOperation` (31) do Hatch é o canal de requisição JSON; não está demonstrado que respostas de chat normais o usem.

### 9.4 Contexto de conversa

`BotMetadata.aiConversationContext` (20) existe. Que o servidor retorne estado atualizado nas respostas e que ele deva ser ecoado de volta é **inferred** (do nome do campo e do relatório da 2.26.26.4); não verificado.

---

## 11. Fluxos

### 10.1 Mensagem de chat para o bot (found do lado do cliente, inferred do lado do servidor)

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

### 10.2 Requisição de metadados Hatch (found do lado do cliente)

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

## 12. Alterações em relação à 2.26.26.4

| Item | 2.26.26.4 | 2.26.41.6 |
|------|-----------|-----------|
| JID `1807055946647696` (Manus) | Legado, flag 25119 | Não presente. 25119 apenas em tabelas de flag, nenhum leitor |
| JIDs 697 / 698 / 165332417282214 | `@s.whatsapp.net` | 697, 698 são servidor `bot` (`C24770wv`); 165332417282214 é `lid` (`C14080dr`) |
| Novas constantes de JID | nenhuma listada | `1807055946647699` (envelope de bot CoEx v2 / alvo de conjunto de dispositivo), `2942131436135992` (JID de perfil Meta AI padrão, teste de JID-de-bot `A07`), `867051314767696555` (segundo membro de `A07`, propósito unknown), `17015557208` (PN do Meta AI, `A04`) |
| Sufixo `$1` | No JID de roteamento, `C1A2.A00/A01` | Não no JID; anexado à string de ID de persona (`C24121Ab2`, `C223219iv`) |
| Conversão de roteamento | anexo de `$1` | `AbstractC24760wu.A01`: LID `165332417282214` → bot `…698`, PN → bot via tabela FBID |
| Nomes de flag 25119/26189/27083 | nomes de flag `ai_*` | Strings são entradas de lista de recurso (`C25056AqU`); 26190 = JSON de perfil Hatch; 37227/37852/37054 controlam valores de capability Hatch 76 / 77 / 79 |
| `richResponseMessage` | Campo 77 | Campo 97 (77 = `commentMessage`) |
| `botInvokeMessage` / `botTaskMessage` / `botForwardedMessage` | 67 / 100 / 104 em "WebMessageInfo" | 67 / 100 / 104 em `Message`; também 131, 137 |
| `botMessageInvokerJid`, `isSupportAiMessage`, `supportAiCitations`, `botTargetId` | ContextInfo 58/70/72/73 | `WebMessageInfo` 58/70/72/73; `botTargetId` nunca escrito |
| Localização de BotMetadata | "embutido na mensagem" | `Message.messageContextInfo` (35) → `botMetadata` (7) |
| `personaId` | `"meta_ai"` | String de persona do perfil, ex. `1807055946647697$1`; `meta_ai` é um rótulo de tipo de bot |
| Tipos de plugin | 8, 9, 15 | Os mesmos, enum tem 18 valores (até 17) |
| Enum de ação | Enum de valor 1/2/3 | oneof 1/2/3 + `ACTION_NOT_SET` 0 |
| Envelope JSON Hatch | `method`, `params` no nível superior | Aninhados sob `payload`; adiciona `accepts_encoding` |
| Transportador Hatch | Mensagem padrão, classe `Azz` | `ProtocolMessage.aiMetadataOperation` (31) → `C25754B9o`; adiciona `bizAiMetadataSync` (2) |
| Verificação de assinatura de bot | não documentada | Novo: `BotMetadata.verificationMetadata` (27), EdDSA + cadeia de certificado X.509 sobre (conteúdo, número de telefone); testado em produção, vincula ao número de telefone não ao remetente real (seção 9) |
| Mapas de pendentes | Um (`A02`) | Dois: continuations `A04`, callbacks de parte `GuR` `A03` |
| Campos de streaming | Uma tabela de chunk do Meta AI | `chunkOrder` (sincronização de histórico), `isLastChunk` (mensagem TEE), `streamingSidecar` (mídia); `clientStreaming`/`serverStreaming` não encontrados |
| Intervalo de sincronização de perfil | "a cada ~1 min" | 1 min é backoff do WorkManager, não um período |
| `MetaAiMemoryStore` | Presente | Não encontrado pelo nome; tabela `meta_ai_memory` (`C23621AHm`: `memory_id`, `memory_content`, `bot_jid_row_id`) encontrada |
| `MetaAiIncognitoSessionManager`, `meta_ai_forward_disclosure_seen`, `AiRichResponseFooterView`, `UnifiedResponseActionHandlerFactory`, `BotProfileSyncManagerImpl`, `BotProfileForChatListWorker` | Presente | Presente |
| Indicador de digitação (chatstates) | Encontrado | Encontrado: saída `<chatstate><composing/></chatstate>`, com `<bot jid/>` quando um bot é mencionado (`C199098dN.A01`); entrada `composing`/`paused` via handler genérico `C40511kx`, sem ramo específico de bot |
| Divulgação de capability | não documentada | `BotMetadata.capabilityMetadata` (13) + `timezone` (8) para o Hatch; flags 37227 / 37852 / 37054 mapeiam para valores de enum 76 / 77 / 79 |
| Exemplos de requisição Hatch | não documentados | `ideas.detail`, `ideas.execute`, `ideas.complete_all`, `channel.bootstrap`, `hitl.approval.decide`, `hitl.payment.select` |
