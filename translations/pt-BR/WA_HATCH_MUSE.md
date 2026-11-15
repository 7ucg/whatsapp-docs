<!-- src-sha1: aacd3c372c813b12cfe335ddb7b3323c8eed3863 -->
# WhatsApp Agente de IA Hatch/Muse — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-15
**Escopo:** internos do agente de IA Hatch/Muse — transporte de VM via gateway Noise atestado, atestação nativa de carrier + SEV-SNP, control plane e onboarding WAFFLE, stream noVNC do agent-browser, workspace (spaces, feed, goals, ideas, artifacts, approvals, tarefas agendadas, conectores), armazenamento seguro de credenciais, recuperação de identidade/PIN CVM (`hatch/cvm`, Vesta OPAQUE), tier de assinatura paga, veredito de alcançabilidade, por que Baileys/velowa não conseguem implementá-lo

---

## 1. O que é Hatch/Muse

**Hatch** é o codinome interno para o subsistema de agente de IA do WhatsApp; **Muse** é o nome voltado ao usuário do próprio agente (`str29b7` "Muse manages emails, books tables, and more."). O agente não é apenas uma persona de chat (isso é o Meta AI, coberto em `WA_META_AI.md`): ele controla uma **VM confidencial remota ("CVM")** que pode navegar na web, executar tarefas agendadas, manter seu próprio sistema de arquivos, e chamar serviços de terceiros em nome do usuário. Tudo neste relatório é análise estática `found`/`inferred` da 2.26.41.6 (`WA-APK-BETA/WhatsApp_2.26.41.6/`), com uma subárea corrigida (§6, o sistema de identidade `hatch/cvm`) re-verificada contra smali da 2.26.45.10. **Nada neste relatório é `tested`** — nenhuma execução em dispositivo/Frida sustenta nada disso; lacunas de confirmação dinâmica estão sinalizadas inline.

### 1.1 Entidades principais

| Entidade | Significado |
|--------|---------|
| Hatch | Codinome interno para todo o subsistema de agente (VM, workspace, armazenamento de credenciais, camada de identidade/PIN) |
| Muse | Nome/persona do agente voltado ao usuário |
| CVM | "Cloud VM" / "VM confidencial" — o ambiente de computação remoto do agente (AMD SEV-SNP) |
| `HatchVmEndpoint` (`C57830PwR`) | Struct de conexão de VM resolvido: host, `auth_token`, expiração, token validado, mapa de parâmetros `notary_token` |
| Noise gateway | Uma sessão Noise atestada separada para um "noise gateway" da Meta, carregada sobre Tigon, distinta da sessão principal Noise_XX/chatd do WA |
| Agent spaces | Mini web apps que o agente constrói e hospeda dentro da CVM, com proxy reverso para uma WebView no telefone |
| Connector | Um vínculo registrado entre o agente e um serviço de terceiros (Gmail, calendário, rede de pagamento, endpoint personalizado) |
| `hatch/cvm` (Vesta) | O sistema de **identidade de dispositivo/VM e recuperação por atestação de chip** do agente, com PAKE OPAQUE protegido por PIN — **não** é um cofre de pagamentos (corrige uma passagem de pesquisa anterior, ver §6) |
| Approval gate | Confirmação humana-no-loop antes de uma ação de risco/irreversível do agente |

### 1.2 Relação com o chat do Meta AI

Muse é acessado pela mesma superfície de chat que o Meta AI, e compartilha parte da infraestrutura (divulgação de capability no JID do bot — ver §7) e o canal de metadados JSON do Hatch documentado em `WA_META_AI.md` §5 (`HF1`/`HatchMetadataRequestManager`, `ProtocolMessage.aiMetadataOperation`). Mas o sistema de agent-browser/VM/workspace coberto por este relatório é um **subsistema separado, muito maior**: ele não trafega na sessão chatd/Noise_XX de forma alguma, tem seu próprio transporte nativo, e persiste seu próprio estado (goals, feed, artifacts, approvals) do lado do servidor na CVM. O Private Processing / o cluster TEE (o Meta AI respondendo perguntas sobre seus próprios chats, Private Search) é um **terceiro sistema, distinto** — ver §11 para a desambiguação completa.

---

## 2. Visão geral da arquitetura

### 2.1 Mapa de pacotes

Todas as activities Hatch/agente são `android:exported="false"` — nenhum ponto de entrada entre apps; tudo é iniciado in-process a partir da superfície de chat/agente.

| Pacote | Papel |
|---------|------|
| `com.whatsapp.hatch.vm` (`p085vm`) | Control plane/ciclo de vida da VM: `HatchVmLifecycleCoordinator`, `HatchVmApiClient`, `HatchVmWaker`, `HatchVmLeaseGate`, `GraphQlHatchAbraTokenProvider`, `HatchAbraTokenRevoker` |
| `com.whatsapp.hatch.onboarding` | `HatchWaffleOnboarding`, `HatchPairingAuthBrowsingActivity`, `HatchMuseConnectionActivator` |
| `com.whatsapp.hatch.computer` / `.conversation.browser` / `.conversation.approval` | `HatchComputerActivity` (desktop completo da VM), `HatchBrowserStreamActivity` (navegador ao vivo dentro do chat), `HatchBrowserPreviewActivity` (approval gate) |
| `com.whatsapp.hatch.feed/goals/ideas/activity/approvalhistory` | UI do workspace: feed, goals + sub-goals, ideas, histórico de aprovações |
| `com.whatsapp.hatch.artifacts/media` | Artefatos e arquivos produzidos pelo agente |
| `com.whatsapp.hatch.connectors(.ui)` | Catálogo de conectores de terceiros, fluxos de conexão, ação de cartão virtual, modo de permissão por conector |
| `com.whatsapp.hatch.identity.ui` | Documentos "sobre mim" do agente |
| `com.whatsapp.hatch.scheduledtasks.impl` | UI de tarefa recorrente da VM do agente |
| `com.whatsapp.hatch.cvm` / `.cvm.pin` | **Não é um cofre** — recuperação de identidade de dispositivo/VM protegida por PIN (Vesta OPAQUE), §6 |
| `com.whatsapp.hatch.subscription(s).iap` | Fluxo de compra do tier pago, §7 |
| `com.whatsapp.bot.agentspaces.*` | Host de "Spaces": `HatchSpaceActivity` + proxy reverso `HatchSpaceTunnel`, adaptador `NoiseHatchVmTransport` |
| `com.whatsapp.bot.agentbrowser.*` | Engine de navegador + transporte de VM: `BrowserSessionController` (WebView noVNC), `NoiseVmConnection`/`WaNoiseChannel`, `agentbrowser.noise.carrier.*` (JNI nativo) |
| `com.whatsapp.bot.securecredentials.*` | `SecureCredentialVault` — armazenamento de credenciais, do lado do servidor na CVM |
| `com.whatsapp.bot.agentactivity/agentfeed/agentgoals/agentapprovals` | Camada de dados/feed por trás da UI `hatch.*` |
| `com.whatsapp.bot.infra.vmmedia` | Busca bruta do sistema de arquivos da VM do agente (`/fs/raw/`, `/media/raw/`) |
| `com.whatsapp.bot.quiz` | `AiQuizViewerActivity` — visualizador de quiz richResponse, **não** é um recurso de VM (§2.3) |
| `com.crossapp.tigonhttp(.noise)` | Pilha HTTP nativa compartilhada entre apps da Meta, **Tigon** + `NoiseChannelManagerHolder` |

### 2.2 Três transportes distintos — não os confunda

Este é o fato estrutural mais importante de todos, e uma passagem de pesquisa anterior errou em um dos três (§6.1 corrige isso):

| # | Transporte | Carrega | Bloqueador para um cliente de terceiros |
|---|-----------|---------|-----------------------------------|
| 1 | **Canal de VM via gateway Noise atestado** — `/v1/noise` sobre Tigon, `libwa-noise-gateway-carrier-jni.so` nativo | Tudo interativo com o agente: HTTP da VM do navegador (`/api/*`, `/fs/*`, `/spaces/*`), stream de tela noVNC, recursos do workspace, CRUD de credencial segura | Carrier nativo Noise+WebSocket **e** onboarding de cliente oficial WAFFLE — bloqueado de forma definitiva |
| 2 | **Control plane HTTPS simples** para `hatch-api.meta.ai` | Despertar da VM, token bearer Abra, URL de pareamento, **e** (corrigido, §6) os endpoints de recuperação de identidade `hatch/vesta-auth/*` / `hatch/cvm-*` | O transporte é observável via MITM em princípio (dispositivo rooteado, bypass de pinning); os endpoints de identidade adicionalmente precisam de matemática OPAQUE nativa + pós-quântica (`libvesta_client_jni.so`) para produzir corpos de requisição válidos |
| 3 | **MEX/GraphQL simples** sobre o transporte comum `whatsapp-android-mex`/`whatsapp-android-www` do WhatsApp | Leituras+exclusões de tarefa agendada/lembrete (1:1 e grupo), leitura de info de compliance de assinatura, cunhagem de token de pagamentos do Hatch | Nenhum bloqueador nativo/atestado — alcançável da mesma forma que qualquer outra op MEX |

O transporte 1 é o que a passagem de pesquisa original (2.26.41.6) chama de "o transporte de VM do Hatch" e é a vasta maioria da superfície do subsistema. O transporte 3 é a **única** parte do Hatch que um cliente estilo Baileys/velowa pode plausivelmente operar.

### 2.3 Não faz parte da VM — a ligação com o quiz

`com.whatsapp.bot.quiz.AiQuizViewerActivity` é um visualizador em tela cheia para um quiz embutido em uma mensagem rich-response armazenada do bot (o primitivo de quiz "Jarvis" do richResponse — território de `WA_META_AI.md` §4.3/§6.3, não Hatch). Ele carrega o quiz **a partir do armazenamento local de mensagens** por row id + key + índice de seção (extras de intent `ai_quiz_viewer_message_row_id`, `ai_quiz_viewer_quiz_key`, `ai_quiz_viewer_section_index`) — nenhuma chamada de rede, nenhum transporte de VM. Mencionado aqui apenas para que não seja confundido com um recurso do Hatch; ver §11 para a tabela completa de desambiguação.

---

## 3. Control plane e onboarding

### 3.1 Onboarding WAFFLE (`found`)

O primeiro uso da superfície do agente executa **`HatchWaffleOnboarding`**: o cliente prova que é uma build genuína e não modificada do WhatsApp via atestação de integridade **WAFFLE** (a mesma família de atestação de cliente oficial do `com.whatsapp.waffle.wfac` da UI de banimento/vinculação de conta — ver `WA_CLIENT_INTEGRITY.md` §11 para o componente irmão WFAC). Breadcrumbs de log: `"waffle-onboarding"`, `"vm-credentials"`, `"pairing-url"`, `"HatchWaffleOnboarding/link pairing-url-received="`. Um cliente de terceiros não pode produzir um token WAFFLE válido, então nem consegue provisionar uma VM — este é o bloqueador rígido do lado do onboarding, independente do carrier do Noise gateway.

### 3.2 Pareamento (`found`)

`HatchPairingAuthBrowsingActivity` abre uma **URL de pareamento** estilo OAuth que vincula a conta WhatsApp ao agente Meta AI/conta Meta; a conclusão é logada como `pairing-url-received`.

### 3.3 Despertar da VM e o bearer Abra (`found`)

`GraphQlHatchAbraTokenProvider` cunha um token bearer GraphQL "Abra" para a VM; `HatchVmApiClient` então faz:

```
POST https://hatch-api.meta.ai/hatch/vm/wake
{"vm_id": "...", "retry_count": N}
```

Isso é HTTPS comum, não o canal Noise. A resposta alimenta a lógica de endpoint em cache de `HatchVmLifecycleCoordinator` ("connect cached-endpoint", "invalidateToken failed") e resolve em um `HatchVmEndpoint` (`C57830PwR`): host/URL base, `auth_token`, `bearerExpiresAtMs`, flag de token validado, e um mapa de parâmetros carregando o `notary_token` para `/v1/noise`. `HatchAbraTokenRevoker` trata a invalidação.

**Alcançabilidade:** a chamada de wake e a cunhagem do token são HTTPS/GraphQL comuns, em princípio observáveis via MITM em um dispositivo rooteado com bypass de pinning — mas inúteis sem uma conta provisionada via WAFFLE, já que o servidor não entrega um endpoint de VM funcional a um cliente não reconhecido (`inferred`; não confirmado independentemente do lado do servidor).

---

## 4. O transporte de VM atestado do agent-browser

Esta é a descoberta mais marcante do subsistema: a VM do agent-browser **não** trafega na sessão Noise/XMPP principal do WhatsApp. Ela abre uma **sessão Noise separada para um "noise gateway" da Meta**, carregada sobre a pilha HTTP Tigon da Meta, através de uma biblioteca nativa dedicada, com um verificador de atestação e uma chave opcional de autenticação privada pré-compartilhada.

### 4.1 Handshake (`found`, `WaNoiseChannel`)

`WaNoiseChannel` recebe o host do endpoint da VM e anexa parâmetros de query codificados em URL antes do handshake:

| Parâmetro | Origem |
|-------|--------|
| `auth_token` | `HatchVmEndpoint.auth_token` (bearer da VM) |
| `notary_token` | valor para a chave `/v1/noise` no mapa de parâmetros do endpoint, só se não vazio |
| `app_id` | constante de app-id do WA (`inferred`, não resolvido por literal) |
| `app_version` | literal fixo `"2.26.41.6"` |

Caminho do handshake: **`/v1/noise`**. Timeout do handshake **20000 ms**; orçamento total de abertura do canal **60000 ms** (`NoiseVmConnection`). Breadcrumbs de log: `noise/open-start`, `noise/reused`, `noise/closed reason=...`, `noise/use-once`.

### 4.2 Carrier nativo e atestação (`found`)

`NoiseGatewayCarrier` é um objeto JNI `com.facebook.jni.HybridData` carregado por `NoiseGatewayCarrierSoLoader` como **`libwa-noise-gateway-carrier-jni.so`** — não um arquivo solto em `lib/arm64-v8a/`, ele vem empacotado dentro do blob superpack `libs.so` (nenhuma extração estática byte-exata disponível).

Pontos de entrada nativos: `createNative(TigonServiceHolder, NoiseChannelManagerHolder)`, `start(endpoint, ..., byte[32]?, AttestationVerifierHolder, Stream0Listener)`, `sendWebsocketFrameNative`, `stopNative`, `cancelHandshakeNative`. Os callbacks de `Stream0Listener` (`onWebSocketUpgraded`, `onTransportReady`, `onReady(NoiseHandshakeOutcome)`, `onMessage`, `onClose/onFailure`) mostram que o canal é **Noise encapsulado dentro de um WebSocket**.

`AttestationVerifierHolder` tem três construtores nativos:

| Variante | Significado |
|---------|---------|
| `createNoOpNative()` | Sem atestação — a variante instanciada no caminho decompilado visto nesta passagem |
| `createSnpNative(bool)` | Atestação de computação confidencial AMD SEV-SNP |
| `createSnpPinnedToChipsNative(chips[], bool)` | SNP fixado a IDs de chip permitidos específicos |

**Qual variante roda em runtime é `unknown`** a partir desta passagem estática. A passagem `hatch/cvm` da 2.26.45.10 (§6) encontrou independentemente os endpoints concretos de control plane que colocam/confirmam IDs de chip SEV-SNP em allowlist (`/hatch/cvm-chip-allowlist`, `/hatch/cvm-chip-selection`), confirmando que o modo de atestação fixada a chip é infraestrutura real, não apenas um caminho de código adormecido.

`NoisePrivateAuthMode.REQUIRED` mais uma chave de 32 bytes é um modo opcional de "autenticação privada" com chave pré-compartilhada (`inferred`: vinculação de canal); não populado no caminho visto, `unknown` se é algum dia usado.

### 4.3 Transporte HTTP-sobre-Noise (`found`)

Uma vez o canal aberto, `WaVmHttpTransportImpl`/`VmHttpClient` enviam requisições HTTP JSON comuns através do túnel Noise via Tigon. O adaptador de nível de app (`NoiseHatchVmTransport`, usado por todo recurso do workspace em §5) expõe quatro verbos:

| verbo | tag | uso |
|------|-----|-----|
| `CQ4(url, accept)` | `hatch_vm_read` | leitura GET |
| `AEV(method,url,body,…)` | `hatch_vm_call` | chamada genérica única |
| `CXY(method,url,headers,body,streaming)` | `hatch_vm_request` | requisição em stream (120 s, ou ilimitado quando `streaming`) |
| `Cly(url,body,…)` | `hatch_vm_subscribe` | subscribe de longa duração SSE/duplex |

`NoiseChannelHolds` conta referências de "holds" abertos; o canal é desmontado após a liberação do último hold (intervalo configurável). Superfície de caminhos HTTP da VM (`found`, literais string): `/v1/noise`, `/api/`, `/api/computer/subscribe`, `/api/artifacts/pin`, `/spaces/`, `/spaces/v2`, `/spaces/cvm/<slug>`, `/spaces/share/`, `/workspace/`, `/home/hatch/`, `/media/raw/`, `/fs/raw/`, mais caminhos de credencial em §5.9.

### 4.4 O stream de tela noVNC (`found`)

`assets/vmvnc/` embute um cliente web **noVNC** real (`novnc-rfb.js`, `vnc.html`, `LICENSE.txt` MPL-2.0) — confirmado independentemente presente tanto nas builds 2.26.41.6 quanto 2.26.45.10 (`assets-sweep.md`). `BrowserSessionController` carrega `https://appassets.androidplatform.net/assets/vmvnc/vnc.html` em uma WebView. O HTML define um **`BridgedWebSocket`** sobrescrevendo `window.WebSocket`: o noVNC acredita que abriu `wss://bridge.invalid/` (subprotocolo `binary`), mas todo frame RFB é retransmitido através da bridge JS do Android `window.AndroidVncBridge` (`socketSend`/`socketClose`/`socketOpen`, callbacks `window.__vncBridge.*`). O próprio comentário no HTML embarcado explica por quê: **o endpoint websockify real exige `Authorization: Bearer <jwt>`**, que um WebSocket de WebView não pode definir, então o código nativo possui o socket real (aberto sobre Tigon com o bearer da VM) e o shim JS apenas retransmite frames.

Resumo: o desktop/navegador da VM é transmitido para o telefone como **RFB (VNC) genuíno sobre um WebSocket autenticado por bearer JWT**, ele próprio tunelado através do gateway Noise atestado; o noVNC renderiza em uma WebView. O controle de entrada (`isViewOnly`, `isInputEnabled`, `isPanModeEnabled`, métodos de zoom/viewport) e dimensionamento (`BrowserViewerJson{width,height,devicePixelRatio}`) são controlados nativamente. `inferred`: frames de "presente"/preview mais leves (`BrowserTaskScreenshotJson`, `BrowserTaskPresentationJson`) sustentam o `HatchBrowserStreamActivity` dentro do chat, com o VNC interativo completo reservado para `HatchComputerActivity`.

### 4.5 Lease de controle (`found`)

`BrowserControlLeaseJson{controlOwner, taskId, controlExpiresAtMs}` + `BrowserControlGrantJson`/`BrowserControlEnvelopeJson` implementam quem está dirigindo o navegador (agente vs. humano "assumir controle"), com tempo limitado por `controlExpiresAtMs`. `BrowserViewerRequestJson` solicita um slot de visualizador. Não confunda este **lease de controle do navegador** com o "lance" de **seleção de chip** SEV-SNP não relacionado em §6 — ver §11.

### 4.6 O framing do túnel agentspaces (`found`)

`HatchSpaceTunnel` faz proxy de uma WebView para apps "spaces" hospedados na CVM em `/spaces/cvm/<slug>` sobre `hatch_vm_*`. O pequeno protocolo de envelope JSON: `{"type":"http.res",id,status,streaming}`, `{"type":"http.end",…}`, `{"type":"http.err",…}`, mais um push de invalidação de cache `{"type":"hatch:space:query-invalidated","spaceSlug":…,"payload":{"queryKeys":[…]}}`. Ele **remove headers hop-by-hop e identificadores** antes de retransmitir — a blocklist inclui `authorization, cookie, host, origin, x-forwarded-*, x-real-ip, x-noise-connection-id` — confirmando que o lado da CVM termina um servidor HTTP real alcançável apenas através do id de conexão Noise.

---

## 5. O workspace do agente

Todo recurso abaixo é construído sobre os quatro verbos `NoiseHatchVmTransport` do §4.3, ou seja, todo literal de caminho abaixo é uma requisição HTTP *dentro* do túnel Noise para a CVM. Bootstrap: `HatchBootstrapRequest` posta `{"sections":[…]}` em um método de subscribe `channel.bootstrap` e lê de volta `{"accepted":[…]}` — o cliente declara quais seções de workspace deseja receber via push. `HatchSpacesSync` só inicia quando "Hatch is linked and a VM endpoint exists" (guardas de log `found`).

### 5.1 Agent spaces

Um **space** é um mini web app/página de resultado interativa hospedada pelo agente dentro da CVM, endereçada por uma string `slug`. O telefone nunca recebe o HTML diretamente — uma WebView local (`HatchSpaceActivity`) é apontada para o túnel (§4.6), que retransmite as respostas HTTP da CVM frame a frame, de forma que um space pode ser um app ativo e stateful, não um artefato estático.

| ação | método + caminho | notas |
|--------|---------------|-------|
| catálogo | `GET /spaces/v2` | `{"spaces":[{"slug","preview_card_url","preview_image",…}]}` |
| status de compartilhamento | `GET /spaces/share/<slug>` | retorna uma URL de compartilhamento se compartilhado+público |
| publicar | múltiplas etapas (`publish`/`post`/`poll`) | pode retornar "needs confirmation" |
| despublicar | `DELETE /spaces/share/<slug>` | |
| excluir | `DELETE /spaces/v2/<slug>?source=space` | |
| fixar / desfixar artefato | `POST /api/artifacts/pin {"artifact_ref":…,"pinned":bool}` | fixa a saída de um space como um artefato |

Exemplo do mundo real (`inferred`): o usuário diz "monitorar voos para Lisboa abaixo de €200"; o Muse constrói um space de monitoramento; o usuário o abre ao vivo, publica um link compartilhável, e fixa o melhor resultado como um artefato.

### 5.2 Feed e atividade

`HatchFeedApi` decodifica um digest datado de **edições**, cada uma contendo **unidades** (`unit_id, title, kicker, emoji, body_md, days`) — o briefing periódico do agente. Sustentado pela linha do tempo de atividade: `GET /api/activity?limit=200` em registros (`timestamp, type, status, title, subtitle, messageId, taskLabel, details.goal{…}`), vinculando cada registro a uma mensagem de chat e opcionalmente a um goal. O ponto de entrada autônomo do Feed está com gate de debug na 41.6 (`str5508` "[Debug Only] Feed"); a linha do tempo de atividade que o alimenta não está.

### 5.3 Goals

`HatchGoalsApi`: listar `GET /api/goals?<query>`, detalhe `GET /api/goals/<goal_id>`. Um goal é um objetivo durável: `{goal_id, title, emoji, summary, momentum_status, sub_goals:[…], updates:[{text, effective_at}]}` — um objetivo permanente com um status de saúde e um log de atualizações com timestamp que o agente anexa. A entrada está com gate de debug (`str5511` "[Debug Only] Goals").

### 5.4 Ideas

Ações propostas pelo agente e executáveis que o usuário pode **Executar** ou **Cancelar** (`HatchIdeaDetailBottomSheet`). Strings: "This idea is already running.", "This idea isn't available anymore.", "No ideas right now. Check back later.", "Couldn't start that idea. Try again." Exemplo: o agente sugere "Rascunhar o resumo do Q3"; tocar em Executar inicia uma tarefa em execução registrada no feed/atividade.

### 5.5 Artifacts e mídia/arquivos do workspace

Artifacts são saídas produzidas pelo agente (documento, imagem, planilha, o resultado de um space), fixados/desfixados via `/api/artifacts/pin`. Os arquivos do agente vivem em um **sistema de arquivos real da CVM por agente** (`com.whatsapp.bot.infra.vmmedia.HatchWorkspaceMediaApi`):

| chamada | caminho | formato |
|------|------|-------|
| biblioteca | `POST /fs/library {"preset":"media","limit":n,"offset":m}` | `{entries:[{path,size,modified_ms}],total,has_more}` |
| bruto | `GET /fs/raw/<path>` | bytes brutos |
| miniatura | `GET /fs/thumbnail/<path>?p=sm` | |
| excluir | `POST /fs/delete {"path":…,"recursive":false}` | |

String de confirmação de exclusão: "This file will be removed from your agent's files. You can't undo this."

### 5.6 Documentos de identidade

Os documentos "sobre mim" do agente são armazenados como **arquivos de texto puro no mesmo sistema de arquivos da VM**, não um armazenamento dedicado: `GET /fs/read {path,offset,len}` → `{text,bytes,eof,not_found}`; `POST /fs/write {path,text|bytes,offset,append,overwrite,create_parent}`. O usuário edita documentos que o agente depois lê como contexto persistente.

### 5.7 Approvals e histórico de aprovações

**Gate ao vivo:** antes de uma ação de risco/irreversível, o agente levanta uma aprovação (`HatchBrowserPreviewActivity`, `str54e1` "Approval required"). **Histórico/auditoria:** `GET /approvals/history?record_schema=snapshot_v1&limit=50`, paginado via `next_cursor`, em um registro estruturado por aprovação: `{approval_id, status, decision, outcome_label, summary_title, purpose_summary, scope_summary, requested_at_ms, permission_question, payload_preview, request_preview_document, display_name, icon_key, blocks, rows, fields, items, links, attachments, version, truncated}`. A entrada está com gate de debug (`str54e8` "[Debug Only] Approval history"), o log subjacente não está.

### 5.8 Tarefas agendadas — três implementações distintas

| # | Superfície | Transporte | Ops | Alcançável por cliente? |
|---|---------|-----------|-----|--------------------|
| a | Lembretes 1:1 do Meta AI (`com.whatsapp.metaai.tasks`) | MEX simples sobre `whatsapp-android-www` | **`GetMetaAiReminders`**, **`DeleteMetaAiReminder`** | **Mais ou menos sim** — MEX de persisted-query baseado em nome, sem bloqueador nativo/atestado |
| b | Tarefas agendadas de grupo (`com.whatsapp.bot.group.groupinstructions.impl`, novo na 41.6) | MEX simples sobre `whatsapp-android-www` | **`GetMetaAiGroupReminders`** (parâmetro `groupId`), **`DeleteMetaAiGroupReminder`** (`groupId`, `reminderId`) | **Mais ou menos sim** — mesmo raciocínio |
| c | Tarefas agendadas da VM Hatch (`com.whatsapp.hatch.scheduledtasks.impl`) | VM Noise | execuções recorrentes da VM do agente, canceladas sobre o transporte de VM | Não — apenas nativo |

9a/9b são as **únicas** ops de workspace que um cliente de terceiros poderia plausivelmente alcançar, porque não tocam nem o carrier nativo noise-gateway nem o onboarding WAFFLE. Criar um lembrete parece acontecer do lado do agente (via tool-call do chat do Meta AI), não através de uma mutation visível ao cliente — apenas ops de Get + Delete estão presentes. Os `doc_id`s numéricos de ambos os pares são `unknown` (resolução de persisted-query baseada em nome; não capturados independentemente). A superfície de group-instructions também permite que um admin configure o Meta AI do grupo (regras, documentos de referência, tom) via `CustomizeGroupMetaAiActivity` — UI adjacente, não em si uma op de tarefa agendada.

### 5.9 Conectores e o armazenamento seguro de credenciais

Um **connector** é um vínculo registrado entre o agente e um serviço externo. O usuário se autentica uma vez (OAuth / chave de API / usuário+senha / FoA / Stripe / Messenger), e a credencial resultante é armazenada **do lado do servidor dentro da CVM, nunca no Android Keystore** — `SecureCredentialVault` executa todas as operações como chamadas HTTP sobre o mesmo transporte VM Noise-HTTP. Não existe nenhuma referência a `KeyStore`, `EncryptedSharedPreferences`, ou `AndroidKeyStore` em nenhum lugar de `securecredentials/`.

Endpoints de credencial (`found`, sobre o canal Noise da VM):

| caminho | papel |
|------|------|
| `POST /v1/credentials/capture` | enviar uma credencial capturada |
| `POST /v1/credentials/catalog/update` | upsert; campos vistos: `username`, `password`; permissão via enum wireValue `JA9` |
| `POST /v1/credentials/catalog/delete` | `{id}` → `{ok}` |
| `GET /v1/custom-connectors/list` | |
| `POST /v1/custom-connectors/register` | formato chave de API `{connector, api_key:{key}, replace_existing}` ou formato OAuth `{connector, oauth_bootstrap:{client_id, client_secret?,…}, replace_existing}` → `authorize_url` |

Catálogo de conectores + fluxos de conexão (`found`, sobre o mesmo canal): `GET /api/connectors?surface=settings&icon_cdn=whatsapp` → `{connectors:[{id,name,description,icon,state,is_custom,management_kind,supports_multiple_accounts,consent}]}`; info de conexão por conector (`/connectors/<id>/connect/info`) e caminhos de autenticação específicos por tipo para OAuth, chave de API, usuário/senha (com `two_factor_required`/`attempts_remaining`/`login_timeout_remaining_secs`), **FoA** (contas Family-of-Apps), **companheiro Messenger** (vinculação de chat protegida por PIN), e **link Stripe** (pagamentos). Permissões são por conector (`GET/SET /permissions/connectors/<id>`, string de UI "Agent permissions"). Conectores personalizados carregam um aviso explícito de código não revisado ("Meta doesn't review custom connectors… supervise your agent's use").

Por design, o agente **não vê segredos brutos**: "Securely store passwords for your agent to use", "Shared with your agent without saving". A ação de **cartão virtual** (`HatchConnectorCardActionActivity`) cunha um cartão de uso único que o agente usa para pagamentos, de forma que o número real do cartão nunca é exposto ("The agent will never see your credit card"). `assets/api_key.txt` existe no APK e é tratado como material de credencial conforme o contrato de evidência do brain — não aberto/citado aqui; `inferred` ser uma chave de API de nível cliente/app para o control plane hatch-api/GraphQL, não um segredo por usuário.

**Alcançabilidade para todo o §5:** apenas nativo. Todo literal de caminho acima é recuperável do APK; nada disso é operável, observável (está criptografado dentro do túnel Noise), ou imitável a partir de um cliente de terceiros, porque cada uma dessas chamadas precisa do transporte atestado do §4 mais uma VM provisionada via WAFFLE.

---

## 6. Recuperação de identidade CVM — o sistema de PIN Vesta OPAQUE (`hatch/cvm`)

### 6.1 Corrigindo o enquadramento de "cofre de cartão virtual"

Uma passagem de pesquisa anterior (2.26.45.10) descreveu `hatch/cvm` + `hatch/cvm/pin` como um "cofre de cartão virtual protegido por PIN". **Esse enquadramento está errado na camada criptográfica.** Ele confunde dois subsistemas não relacionados:

- **`hatch.connectors` / `HatchConnectorCardActionActivity`** (§5.9) — um fluxo de concessão de conector real e separado para uma rede de pagamento de terceiros (quase certamente Stripe). Ele tem **zero referências de código** a qualquer classe `com.whatsapp.hatch.cvm` ou `com.facebook.vesta` (verificado: nenhuma referência cruzada do smali de `hatch.connectors` para `HatchCvmPinActivity`/`HatchCvmVestaClient`/`HatchCvmKeyService`).
- **`hatch.cvm` / `hatch.cvm.pin`** é o sistema de **identidade de VM confidencial e matrícula de atestação de chip** do agente, não um armazenamento de cartão. Ele não armazena **nenhum dado de pagamento de nenhum tipo** — nenhum campo PAN/CVV/faturamento em nenhum lugar do pacote. O que ele protege é um **segredo de identidade de dispositivo/VM recuperado via uma troca de chave autenticada por senha OPAQUE, com o PIN como senha**, vinculado à seleção de chip de hardware AMD SEV-SNP para a CVM.

O PIN **não é um desbloqueio apenas local**: o caminho de login de `HatchCvmKeyService` faz uma ida e volta real de troca OPAQUE para um backend da Meta (`hatch-api.meta.ai/hatch/vesta-auth/*`, HTTPS simples) antes que qualquer material de chave local seja derivado/restaurado. Um PIN errado falha **do lado do servidor** ("wrong pin", "crypto failed"), não apenas contra um hash local.

Criticamente, esse tráfego é **HTTPS simples para `hatch-api.meta.ai`** — o mesmo host de control plane que `/hatch/vm/wake` (§3.3) — **não** o canal de VM atestado via gateway Noise sobre Tigon. Então a afirmação genérica de "mesmos bloqueadores rígidos do transporte" do §4/§5 não se aplica aqui: o bloqueador real para este subsistema é criptográfico, não de transporte atestado.

### 6.2 A superfície nativa

`com.facebook.vesta.VestaClient` carrega **`libvesta_client_jni.so`** (novo na 2.26.45.10). Todos os 19 métodos nativos declarados nele implementam um **PAKE OPAQUE com PIN-como-senha, adicionalmente embrulhado com uma camada de KEM/assinatura pós-quântica**, mais uma etapa de validação de "chave HSM" vinculada ao dispositivo:

| método nativo | papel |
|---|---|
| `getApiVersionNative` / `getProtocolVersionNative` | negociação de versão |
| `beginLoginNative` / `finishLoginNative` (×2 sobrecargas) | etapas 1 e 2 do login OPAQUE (produz material de chave de sessão/export) |
| `beginRegisterNative` / `finishRegisterNative` / `finishRegisterProtoNative` | registro OPAQUE (cadastrando um novo PIN) |
| `unpackLoginPayloadNative` / `unpackLoginPayloadProtoNative` | decodificar o payload de login custodiado do servidor |
| `validateHsmKeyNative` / `validateHsmKeysWithOtaBundleNative` | validar um par de chaves apoiado por hardware, opcionalmente com um bundle OTA de rotação de chave de dispositivo |
| `verifyRestoreHistoryNative` | verificar um registro de histórico de restauração/recuperação anterior |
| `pqWrapFinishLoginNative` / `pqWrapFinishRegisterNative` / `pqUnwrapFinishLoginResponseNative` | empacotar/desempacotar pós-quântico de payloads de login/registro |
| `pqWrapSchemeNative` | qual esquema PQ está em uso (valor de retorno `unknown` — precisa de Frida) |

`libvesta_client_jni.so` está, assim como o carrier do noise-gateway, empacotado dentro do blob opaco SUPERPACK — nenhuma extração estática byte-exata foi possível nesta passagem. `libvoprf-ed25519.so` (presente na mesma build) é consistente com um primitivo OPRF/VOPRF (o bloco de construção central do OPAQUE) mas **não** foi vinculado independentemente a `VestaClient` — registrado como uma biblioteca adjacente plausível, não provado ser a mesma implementação (`unknown`).

### 6.3 Endpoints de wire — HTTPS simples para `hatch-api.meta.ai`

| caminho | papel |
|---|---|
| `POST /hatch/vesta-auth/begin-login` | etapa 1 do login OPAQUE |
| `POST /hatch/vesta-auth/finish-login` | etapa 2 do login OPAQUE, retorna o payload custodiado |
| `POST /hatch/vesta-auth/begin-register` | etapa 1 do registro OPAQUE (PIN novo/alterado) |
| `POST /hatch/vesta-auth/finish-register` | etapa 2 do registro OPAQUE |
| `GET /hatch/vesta-auth/user-info` | `is_registered` + contadores de tentativa/bloqueio |
| `GET /hatch/fetch_vms?notary_token=true[&vm_id=]` | listar/resolver a(s) CVM(s) do usuário |
| `POST /hatch/lease_vm` / `POST /hatch/cold-lease-cvm` | alugar uma instância de CVM (quente / fria) |
| `GET /hatch/cvm-replace-state?env_id=` | transição de máquina de estados da CVM |
| `GET /hatch/cvm-chip-allowlist?env_id=` | quais IDs de chip SEV-SNP são permitidos para esta CVM |
| `POST /hatch/cvm-chip-selection` | confirmar a seleção/lance de chip |
| `GET /hatch/onboarding_statuses` | verificação de status de onboarding |
| `POST /hatch/vm/wake` | despertar/retomar a CVM (também §3.3) |

Nenhum desses toca `/v1/noise` ou os verbos `hatch_vm_*` — confirmando a correção do §6.1. `/hatch/cvm-chip-allowlist` e `/hatch/cvm-chip-selection` são a primeira **evidência concreta de wire** para o modo de atestação SEV-SNP "fixado a IDs de chip específicos" que o §4.2 encontrou apenas como assinatura de construtor nativo.

DTOs de wire (campos de serial-name `kotlinx.serialization`, não nomes de campo Java obfuscados) incluem a própria nomenclatura de troca de três mensagens **L1/L2/L3** do OPAQUE (`base64url_encoded_opaque_l1/l2/l3`, mais variantes `_sig`), **chaves públicas RSA/Ed25519 de "island"** vinculadas ao dispositivo (proveniência `unknown` — HSM/Keystore vs. um formato interno da Vesta), e um journal local (`HatchCvmJournal`: `candidate_chip_ids`, `accepted_chip_ids`, enum `bid_state` `PENDING/ACCEPTED/RETIRED`, `abra_user_id` — a mesma identidade bearer de `GraphQlHatchAbraTokenProvider`).

### 6.4 O que o PIN realmente protege

`HatchCvmKeyService.A00` (o caminho de recuperação): (1) executa login OPAQUE (`begin-login` depois `finish-login`, matemática nativa); (2) só em caso de sucesso, `HatchCvmKeyProviderImpl` deriva/restaura o material de chave local real a partir do payload de login custodiado; (3) existe um caminho de wipe para incompatibilidade de chave de dispositivo ou reset explícito. **Um PIN correto é necessário para completar uma troca OPAQUE cliente↔servidor real** — o servidor só libera o payload custodiado em um finish-login correto, limitado por taxa e verificado do lado do servidor (`attempts_remaining`, `login_timeout_remaining_secs` em toda resposta). Um atacante com o dispositivo mas sem o PIN não pode forçar isso localmente. O segredo protegido é **o material de chave de identidade de CVM/dispositivo necessário para retomar a sessão de VM confidencial deste usuário** — não uma credencial de pagamento.

Separadamente, `HatchCvmPinReminder` usa uma chave AES/GCM **apenas local** (alias `hatch:pin-reminder:v1:...`) puramente para criptografar um estado de notificação "lembre-me de definir um PIN" — não relacionado à troca Vesta e a única peça de criptografia não observável no wire deste subsistema.

### 6.5 Veredito de alcançabilidade para o §6

O schema de wire é totalmente recuperável (acima); o transporte é HTTPS simples, em princípio observável via MITM **sem** derrotar a atestação WAFFLE ou o carrier nativo do noise-gateway. Mas **participar de fato** (um login/registro real) não é possível a partir do APK por si só: cada campo de requisição/resposta é produzido ou consumido por operações nativas de embrulho/desembrulho OPAQUE + pós-quântico dentro de `libvesta_client_jni.so`, empacotado no superpack sem extração byte-exata disponível. Um cliente poderia capturar e repetir o *formato* JSON em texto puro, mas não pode computar um `opaque_l1`/`l3` válido, uma prova de par de chaves "island", ou um payload embrulhado com PQ — um bloqueador **criptográfico**, estruturalmente diferente do bloqueador de transporte atestado do §4.

---

## 7. Monetização — o tier de assinatura paga do Hatch

Um cluster de assinatura da era 2.26.45.10 adiciona um tier real e cobrado para o Muse. O fluxo de compra (cadeia `inferred`, cada etapa `found` individualmente):

1. O cliente verifica a feature flag **`ai_hatch_in_app_subscriptions_enabled`** (log: "`ai_hatch_in_app_subscriptions_enabled` is off"). Nenhum ID numérico de flag foi encontrado para ela — ela é referenciada apenas por nome.
2. Constante de tier **`NME_SUBSCRIPTION`**; detalhes do produto buscados por tier (`HatchSubscriptionPurchase$launch$2`, log "Fetching product details for tier"; nome do tier interpolado, não um SKU fixo).
3. Verificação de compliance: **`WamoSubGetComplianceInfo`** (`whatsapp-android-mex`, baseado em nome, nenhum campo de entrada definido no ponto de chamada — escopo apenas de sessão/identidade).
4. Cunhagem de token de pagamentos: **`HatchGenFrlPaymentsAccessTokenMutation`** (`GraphQlHatchFrlPaymentsTokenProvider`, namespace `whatsapp-android-www`; expansão de "FRL" não encontrada em nenhuma string nesta passagem — `unknown`).
5. Lançamento do Google Play Billing (`HatchManageSubscriptionViewModel$openBilling$1`) — `BillingClient` Android padrão via um SDK de comércio compartilhado da Meta (`com.facebook.payments.dcp.xapp.*`), marcado `app="WHATSAPP"`.
6. Na compra, reconciliação de cumprimento do lado do servidor (`HatchSubscriptionPurchaseReconciler`), provavelmente via **`DCPFulfillIAPTransactionsMutation`** (`pay_dcp_fulfill_iap_transactions`, requisição Pando direta, campos `platform`/`app`/`purchase_tokens`/`subscription_purchase_tokens`/`upl_session_id`, todos obrigatórios neste ponto de chamada) — não confirmado independentemente ser exatamente a chamada que este reconciliador usa (`unknown`).

Quatro operações adicionais declaradas apenas no catálogo de persisted-query (`IACQueryProductInfo`, `IACQuoteDisplay`, `IACSandboxPlatformMode`, `DCPInternalSandboxCreateSessionMutation`) **não têm nenhuma classe chamadora encontrada em lugar algum no smali** — `unknown` se isso é código morto/futuro, um gate de servidor/flag, ou um ponto de chamada concatenado por string que um grep simples não detecta.

**Alcançabilidade:**

| op | namespace | precisa | alcançável por um cliente de terceiros? |
|---|---|---|---|
| `WamoSubGetComplianceInfo` | `whatsapp-android-mex` | apenas uma sessão mex autenticada | **Sim, em princípio** — query mex simples sem parâmetros |
| `HatchGenFrlPaymentsAccessTokenMutation` | `whatsapp-android-www` | sessão autenticada | **Alcançável no transporte**; o valor do token cunhado fora do fluxo pretendido é `unknown` |
| `DCPFulfillIAPTransactionsMutation` | `whatsapp-schema` (Pando) | um token de compra/assinatura do Play Billing assinado genuinamente pelo Google | **Não** — a requisição pode ser montada, mas nada verdadeiro pode ser colocado nela sem uma compra real via Play Billing através de um contexto `com.whatsapp` assinado |
| `IAC*` / `DCPInternalSandboxCreateSessionMutation` | `whatsapp-schema` | unknown (nenhuma classe chamadora encontrada) | **Unknown** |
| O próprio Google Play Billing | n/a | Play Store + contexto de app assinado | **Não** — nem mesmo uma chamada ao servidor do WhatsApp |

---

## 8. Veredito de alcançabilidade

| Componente | Transporte | Bloqueador | Alcançável de um cliente de terceiros (Baileys/velowa)? |
|---|---|---|---|
| Agent spaces, feed/atividade, goals, ideas, artifacts, mídia/arquivos do workspace, documentos de identidade, approvals+histórico, tarefas agendadas da VM Hatch, conectores (todos os fluxos), armazenamento seguro de credenciais | Canal de VM Noise atestado (§4) | carrier nativo noise-gateway `.so` + onboarding WAFFLE | **Não** |
| Control plane (despertar da VM, token Abra, URL de pareamento) | HTTPS simples para `hatch-api.meta.ai` | provisionamento com gate WAFFLE (o servidor não emite uma VM funcional sem ele) | **Não** (schema observável via MITM; não operável independentemente) |
| Recuperação de identidade/PIN CVM (`hatch/cvm`, Vesta OPAQUE) | HTTPS simples para `hatch-api.meta.ai` | matemática OPAQUE + pós-quântica nativa em `libvesta_client_jni.so` | **Não** — bloqueador criptográfico, não de transporte atestado |
| Lembretes 1:1 — `GetMetaAiReminders` / `DeleteMetaAiReminder` | MEX simples, `whatsapp-android-www` | nenhum encontrado | **Mais ou menos sim** (doc_id `unknown`) |
| Lembretes de grupo — `GetMetaAiGroupReminders` / `DeleteMetaAiGroupReminder` | MEX simples, `whatsapp-android-www` | nenhum encontrado | **Mais ou menos sim** (doc_id `unknown`) |
| Info de compliance de assinatura — `WamoSubGetComplianceInfo` | MEX simples, `whatsapp-android-mex` | nenhum encontrado | **Sim, em princípio** |
| Cunhagem de token de pagamentos — `HatchGenFrlPaymentsAccessTokenMutation` | GraphQL simples, `whatsapp-android-www` | nenhum no nível de transporte; valor prático do token em outro lugar unknown | **Alcançável no transporte** |
| Cumprimento IAP — `DCPFulfillIAPTransactionsMutation` | GraphQL Pando simples, `whatsapp-schema` | precisa de um token de Play Billing genuinamente assinado | **Não** (nada verdadeiro para enviar) |
| Ops `IAC*` / sandbox IAP | `whatsapp-schema` | nenhuma classe chamadora encontrada | **Unknown** |
| quiz richResponse (bot.quiz) | armazenamento local de mensagens | nenhum — não é um recurso de VM | payload recuperável; chega como uma mensagem de bot normal |

As linhas "Mais ou menos sim"/"Sim, em princípio" são **toda** a superfície alcançável por cliente deste subsistema. Todo o resto — que é a maior parte do agente — exige ou o carrier nativo do noise-gateway mais uma atestação WAFFLE válida, ou criptografia nativa OPAQUE/pós-quântica que não pode ser extraída estaticamente deste APK.

---

## 9. Baileys / velowa

**Veredito: este subsistema é impossível em JS para um cliente de terceiros, ponto final — não é um recurso faltante, é estrutural.** A velowa (o projeto de cliente ativo por trás destes documentos) não pode implementar a VM de agent-browser ou o workspace do Hatch/Muse pelas mesmas razões que a passagem de pesquisa original deu:

| Bloqueador | Por que não pode ser contornado em JS/WASM |
|---|---|
| `libwa-noise-gateway-carrier-jni.so` | Todo o handshake Noise e framing WebSocket para o canal de VM é código nativo dentro do blob opaco SUPERPACK. Não existe um documento de protocolo para reimplementar contra ele — o formato de wire (parâmetros de query, caminho `/v1/noise`, verbos HTTP-sobre-Noise, subprotocolo RFB noVNC) foi recuperado acima, mas a criptografia Noise real (derivação de chave, autenticação de frame) só existe compilada dentro daquele `.so`. Reimplementá-la significa fazer engenharia reversa de uma biblioteca nativa stripped, não escrever um cliente contra uma spec. |
| Atestação de cliente oficial WAFFLE | Impede o onboarding da VM antes mesmo de qualquer canal Noise ser aberto. Um cliente de terceiros não pode produzir um token WAFFLE válido, então nem consegue provisionar uma VM antes de qualquer coisa — isso bloqueia até mesmo uma tentativa do handshake Noise. |
| `libvesta_client_jni.so` (OPAQUE + PQ) | Separado do anterior: mesmo onde o tráfego de recuperação de identidade (§6) é HTTPS simples e observável, a matemática OPAQUE do lado do cliente (`opaque_l1`/`l3`, as provas de par de chaves "island", o embrulho pós-quântico) é nativa. Capturar o formato JSON não dá nada para computar uma requisição válida. |
| Atestação AMD SEV-SNP | Ortogonal ao cliente — é a VM do *servidor* provando ser genuína ao app oficial — mas confirma que todo o design pressupõe um peer nativo e atestado em ambas as pontas. |
| Tigon | A pilha HTTP nativa interna entre apps da Meta carrega toda requisição em §4 e §6; seus objetos de requisição não são um formato de wire público e versionado. |

O que a velowa (ou qualquer cliente de protocolo) *conseguiria* alcançar sem tocar em nada do acima: as quatro ops MEX de lembrete baseadas em nome (§5.8) e as ops GraphQL de compliance de assinatura/cunhagem de token de pagamentos (§7) — todas trafegando sobre o mesmo transporte MEX/GraphQL comum do WA que a velowa já fala para tudo mais neste repositório. Nenhum exemplo de código é dado aqui porque nenhum material-fonte deste relatório capturou uma requisição/resposta concreta para essas ops além dos nomes de operação e formatos de parâmetro já listados em §5.8/§7/§8; inventar bytes de payload representaria mal o tier de evidência.

---

## 10. Casos de erro / pegadinhas

| Sintoma | Causa | Nota |
|---|---|---|
| "Computer is turned off on this VM" | VM não provisionada/desperta para a superfície completa do desktop | string de `HatchComputerActivity` |
| "Approval required" nunca se resolve em uma ação | o usuário não confirmou o approval gate | por design — humano-no-loop |
| "This idea isn't available anymore." / "This idea is already running." | cartão de idea substituído ou já em execução | `HatchIdeaDetailBottomSheet` |
| "No goals yet" / "No ideas right now. Check back later." / "No approvals yet" | seções de workspace vazias, não um erro | |
| "Couldn't load your agent's files" | chamada `/fs/library` ou `/fs/raw/` falhou sobre o túnel Noise | |
| estilo `PrivateSearchSessionManager` "thread superseded by a newer search, refusing" (sistema TEE adjacente, não Hatch) | listado em §11 apenas para evitar contaminação cruzada de strings de erro entre os dois sistemas | ver Distinções Importantes |
| 400 "already exists; set replace_existing=true" | registro de conector personalizado sem a flag `replace_existing` | `HatchConnectorsListRequester` |
| "wrong pin" / "finish-login crypto failed" | login OPAQUE falhou do lado do servidor | limitado por taxa via `attempts_remaining`/`login_timeout_remaining_secs` |
| "hsm key missing" / "hsm key invalid" / "hsm key check failed" | validação de chave HSM vinculada ao dispositivo falhou dentro do caminho de recuperação Vesta | §6.4 |
| `noise/gave-up limit=deadline` | orçamento de abertura do canal Noise da VM (60 s) excedido | `NoiseVmConnection` |
| `NoiseHandshakeOutcome.VERIFICATION_FAILED` | verificação de atestação falhou no handshake do noise-gateway | §4.2 |
| "`ai_hatch_in_app_subscriptions_enabled` is off" | feature flag de assinatura desativada do lado do servidor | §7 |
| "HatchSubscriptionPurchase/purchase no compliance data" | resultado de `WamoSubGetComplianceInfo` ausente antes de uma tentativa de compra | §7 |

---

## 11. Distinções importantes — o que NÃO confundir

| Não confundir | Fato |
|---|---|
| Agente Hatch/Muse (este relatório) vs. **chat do Meta AI** (`WA_META_AI.md`) | O Meta AI é um contato bot alcançado por `botInvokeMessage`/JIDs de bot no proto de mensagem normal; Hatch/Muse é um agente separado que controla uma VM remota atestada. Eles compartilham parte da infraestrutura (canal de metadados JSON do Hatch via `ProtocolMessage.aiMetadataOperation`, flags de capability divulgadas ao JID do bot Hatch `1807055946647697@bot`) mas são subsistemas arquiteturalmente distintos |
| VM Hatch/Muse vs. **Private Processing / cluster TEE** (IA de contexto de chat, Private Search) | O cluster TEE (`ClusterFetchPrekeyBundleConnection`, `IplsdHandshakeExecutor`, `PsiSearchToolHandler`, `TeePrefixCacheAnchor`) é o Meta AI respondendo perguntas **sobre seus próprios chats locais** via um enclave atestado + busca PSI — não tem nada a ver com a VM de agent-browser do Hatch. O *envio de query* do Private Search trafega em uma mensagem de bot-chat simples (alcançável), enquanto a computação PSI/enclave em si permanece nativa — um formato de alcançabilidade diferente de qualquer coisa neste relatório |
| `hatch.cvm` (identidade/recuperação de chip, §6) vs. `hatch.connectors` (cartão virtual / Stripe, §5.9) | Dois recursos separados compartilhando apenas as palavras casuais "cartão"/"cofre" no enquadramento de produto; nenhuma dependência de código entre eles (verificado) |
| A chave AES/GCM local de `HatchCvmPinReminder` vs. a troca Vesta OPAQUE | Criptografia de estado de notificação apenas local vs. uma recuperação de identidade real com ida e volta ao servidor — apenas a última é gate de PIN "do lado do servidor" |
| Campos "bid_state"/"chip" (§6) vs. o **lease de controle** do navegador (§4.5) | Contabilidade de seleção de chip de hardware SEV-SNP vs. quem está dirigindo o navegador do agente (agente/humano) — três usos diferentes de vocabulário sobreposto ("lance"/"lease"/"controle") nesta base de código |
| O control plane HTTPS simples da Vesta (§3, §6) vs. o canal de VM via gateway Noise atestado (§4) | Transportes diferentes, bloqueadores diferentes (matemática OPAQUE nativa vs. Noise nativo + atestação WAFFLE) — confundi-los exagera onde o bloqueador de transporte atestado de fato se aplica |
| Agent spaces (§5.1) vs. artifacts produzidos pelo agente (§5.5) | Um space é um app ativo, stateful, hospedado; um artifact é uma saída estática (o *resultado fixado* de um space se torna um artifact, mas o space em si continua rodando) |
| `com.whatsapp.bot.quiz.AiQuizViewerActivity` vs. um recurso Hatch | Lê um quiz richResponse já entregue como uma mensagem de bot normal a partir do armazenamento local — nenhuma VM, nenhuma chamada de rede, não faz parte deste subsistema de forma alguma |

---

## 12. Fluxo de ponta a ponta — uma sessão de tarefa de agent-browser

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

Separadamente (não parte da mesma sessão, MEX/GraphQL simples, sem transporte atestado envolvido):

```
[Client]  GetMetaAiReminders / GetMetaAiGroupReminders
    │  whatsapp-android-www, name-based persisted query
    ▼
[WA server]  reminder list (status SCHEDULED/CLAIMED/FULFILLED)

[Client]  DeleteMetaAiReminder / DeleteMetaAiGroupReminder
    ▼
[WA server]  reminder removed
```
